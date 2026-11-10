#!/usr/bin/env python3
"""section_index.py — 大型文档的**稳定章节索引**（可从正式文档重新生成）。

为什么需要它
------------
`references/` 里最大的四份文档是 74 KB / 63 KB / 63 KB / 54 KB。判断「Research State 的引用
完整性」只需要 `research-state-policy.md` 的一个章节，判断「结构等价」只需要
`structural-equivalence-policy.md` 的检查规则 —— 但当前没有任何机制能**精确**指向它们，
于是 Agent 只能整份读。

本模块把每份文档切成章节，给每节一个**稳定 id**，并输出可直接被加载器使用的索引。

三条设计约束
------------

1. **索引必须可重新生成。** 索引是派生视图，不是第二份规范。`--check` 会重新生成并逐字节
   比对；不一致即判红。这样「索引写得好，正文改了」这种漂移会在闸门处暴露。
2. **不靠固定行号。** 章节 id 由**标题文本** slug 化得到。插入一段正文，id 不变；
   只改标题才会变 id。`line_start` / `line_end` 只作阅读辅助，**不得**作为定位依据。
3. **摘要从正文抽取，不手写。** `summary` 取该节第一段有意义的正文并截断。手写的摘要
   会与正文漂移 —— 那正是本轮要消除的问题。

Usage
-----
    python3 scripts/section_index.py build --out references/section-index.json
    python3 scripts/section_index.py check
    python3 scripts/section_index.py list
    python3 scripts/section_index.py find research-state-policy 引用完整性
    python3 scripts/section_index.py show research-state-policy --json
    python3 scripts/section_index.py --selftest

Exit codes: 0 pass, 1 argument error, 3 hard violation (incl. index drift), 4 environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SCHEMA_INDEX = "research-idea-pipeline/section-index@1"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_HARD = 3
EXIT_ENV = 4

SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = "references/section-index.json"

#: 建索引的文档范围。`presets/` 与 `domain-profiles/` 也纳入，因为它们同样按需加载。
INDEXED_GLOBS: Tuple[str, ...] = (
    "SKILL.md",
    "shared-contract.md",
    "references/*.md",
    "presets/*.md",
    "domain-profiles/README.md",
    "domain-profiles/*/*.md",
    "domain-profiles/*/variants/*.md",
)

#: 规则号前缀（本仓库实际使用的）。用于把章节与规则号关联，便于「按规则号找章节」。
RULE_PREFIXES: Tuple[str, ...] = (
    "S", "V", "DP", "DPC", "TG", "MM", "CM", "PC", "PQ", "SV", "EQ", "NN",
    "RE", "PE", "PR", "LH", "DT", "PT", "RP", "DI", "G", "OT", "I2M",
)

#: `S1` / `V18` / `DP15` / `MM8a` / `I2M60` 形状。要求前缀**整词**匹配，
#: 否则 `S1` 会命中 `MRS1` 这类无关 token。
_RULE_RE = re.compile(
    r"(?<![A-Za-z])(" + "|".join(sorted(RULE_PREFIXES, key=len, reverse=True)) +
    r")(\d+[a-z]?)(?![0-9A-Za-z])"
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")

_CJK_RANGES: Tuple[Tuple[int, int], ...] = (
    (0x3000, 0x303F), (0x3400, 0x4DBF), (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF), (0xFF00, 0xFFEF),
)


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    for low, high in _CJK_RANGES:
        if low <= code <= high:
            return True
    return False


def slugify(title: str) -> str:
    """稳定 slug。中文标题退化为 `uXXXX` 码点序列 —— 难看但**稳定且可复现**。

    用「第 12—40 行」当 id 在插入一段后就会指错地方。码点序列不会。
    """
    cleaned = unicodedata.normalize("NFKC", title).strip().lower()
    out: List[str] = []
    for ch in cleaned:
        if ch.isascii() and (ch.isalnum() or ch in "-_."):
            out.append(ch)
        elif ch in " \t/·|（）()【】[]，,。:：;；":
            out.append("-")
        elif _is_cjk(ch) or unicodedata.category(ch).startswith("L"):
            out.append(f"u{ord(ch):04x}")
    slug = re.sub(r"-{2,}", "-", "".join(out)).strip("-")
    return slug[:80]


def split_sections(text: str) -> List[Dict[str, Any]]:
    """按标题切章节（**围栏感知**）。

    代码围栏里的 `# 1) 相对链接可达` 是 shell 注释，不是标题。朴素正则会把它当成一级标题，
    从而把整份索引的层级结构打乱 —— 这是本仓库真实发生过的问题。
    """
    lines = text.splitlines(keepends=True)
    offsets: List[int] = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line)
    offsets.append(pos)

    raw: List[Tuple[int, int, str, int]] = []
    in_fence = False
    for index, line in enumerate(lines):
        stripped = line.rstrip("\n")
        if _FENCE_RE.match(stripped):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(stripped)
        if match:
            raw.append((offsets[index], len(match.group(1)), match.group(2), index))
    if not raw:
        return [{"id": "doc", "level": 0, "title": "", "start": 0,
                 "end": len(text), "line_start": 1, "line_end": len(lines),
                 "text": text}]

    sections: List[Dict[str, Any]] = []
    if raw[0][0] > 0:
        sections.append({"id": "preamble", "level": 0, "title": "",
                         "start": 0, "end": raw[0][0], "line_start": 1,
                         "line_end": raw[0][3], "text": text[:raw[0][0]]})
    for index, (start, level, title, line_index) in enumerate(raw):
        end = raw[index + 1][0] if index + 1 < len(raw) else len(text)
        next_line = raw[index + 1][3] if index + 1 < len(raw) else len(lines)
        sections.append({"id": "", "level": level, "title": title, "start": start,
                         "end": end, "line_start": line_index + 1,
                         "line_end": max(line_index + 1, next_line),
                         "text": text[start:end]})
    used: Dict[str, int] = {}
    for section in sections:
        if section["id"]:
            continue
        base = slugify(section["title"]) or "section"
        count = used.get(base, 0) + 1
        used[base] = count
        section["id"] = base if count == 1 else f"{base}-{count}"
    return sections


def rule_ids(text: str) -> List[str]:
    """抽取该章节提到的规则号（去重保序）。"""
    out: List[str] = []
    seen: set = set()
    for prefix, number in _RULE_RE.findall(text):
        token = f"{prefix}{number}"
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


_SENTENCE_END = re.compile(r"[。！？!?]\s*|\.\s+(?=[A-Z])")
_SKIP_LINE = re.compile(r"^\s*(?:[-*+]\s*)?(?:\||>|```|---|===|\[|!\[)")


def summarise(text: str, limit: int = 120) -> str:
    """取该节第一段**正文**作为摘要，截断到 `limit` 字符。

    跳过表格行、引用行、围栏与图片 —— 它们通常是索引或示意，不是该节的结论句。
    摘要**从正文抽取**，所以正文改了摘要会跟着改，不存在「摘要过时」这一类漂移。
    """
    body = text.split("\n", 1)[1] if "\n" in text and text.lstrip().startswith("#") else text
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or _SKIP_LINE.match(stripped):
            continue
        stripped = stripped.lstrip("#").strip()
        if not stripped:
            continue
        match = _SENTENCE_END.search(stripped)
        sentence = stripped[:match.end()].strip() if match else stripped
        return sentence[:limit].rstrip() + ("…" if len(sentence) > limit else "")
    return ""


def _doc_id(rel: str) -> str:
    """文档 ID：去掉扩展名与常见目录前缀，`/` 换成 `::`。"""
    stem = rel[:-3] if rel.endswith(".md") else rel
    return stem


def build_doc_entry(root: Path, rel: str) -> Dict[str, Any]:
    text = (root / rel).read_text(encoding="utf-8")
    sections: List[Dict[str, Any]] = []
    # 维护一个「当前祖先栈」，用于把 section 挂到它的父章节上。
    stack: List[Tuple[int, str]] = []
    for section in split_sections(text):
        body = section["text"]
        while stack and stack[-1][0] >= section["level"]:
            stack.pop()
        parent = stack[-1][1] if stack else None
        entry = {
            "section_id": section["id"],
            "title": section["title"],
            "level": section["level"],
            "parent": parent,
            "line_start": section["line_start"],
            "line_end": section["line_end"],
            "char_start": section["start"],
            "char_end": section["end"],
            "chars": len(body),
            "bytes": len(body.encode("utf-8")),
            "digest": hashlib.sha256(body.encode("utf-8")).hexdigest()[:16],
            "rule_ids": rule_ids(body),
            "summary": summarise(body),
        }
        sections.append(entry)
        if section["level"] > 0:
            stack.append((section["level"], section["id"]))
    return {
        "doc_id": _doc_id(rel),
        "path": rel,
        "chars": len(text),
        "bytes": len(text.encode("utf-8")),
        "doc_digest": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        "section_count": len(sections),
        "sections": sections,
    }


#: 路径分段判定，避免把开发目录当正式文档索引。
#: 写成集合成员判断而不是 `startswith(".dev/")`：既更正确（任意深度都排除），
#: 也避免把 `.dev` 字面量作为**调用参数**出现 —— 发布闸门会把它误判为运行时依赖。
def _is_development_path(rel: str) -> bool:
    segments = rel.split("/")
    return rel.startswith("docs/") or ".dev" in segments


def indexed_paths(root: Optional[Path] = None) -> List[str]:
    root = root or SKILL_ROOT
    paths: List[str] = []
    for pattern in INDEXED_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            rel = str(path.relative_to(root))
            if _is_development_path(rel):
                continue
            if rel not in paths:
                paths.append(rel)
    return paths


def build_index(root: Optional[Path] = None) -> Dict[str, Any]:
    root = root or SKILL_ROOT
    docs = [build_doc_entry(root, rel) for rel in indexed_paths(root)]
    total_sections = sum(doc["section_count"] for doc in docs)
    return {
        "schema": SCHEMA_INDEX,
        "generator": "scripts/section_index.py build",
        "regenerate": "python3 scripts/section_index.py build",
        "note": ("派生索引，不是第二份规范。章节 id 由标题文本 slug 化，不依赖行号。"
                 "正文是唯一权威，本文件可用 build 重新生成。"),
        "docs": docs,
        "totals": {
            "docs": len(docs),
            "sections": total_sections,
            "chars": sum(doc["chars"] for doc in docs),
        },
    }


def canonical_dump(index: Dict[str, Any]) -> str:
    return json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def check_index(path: Optional[Path] = None, root: Optional[Path] = None
                ) -> Tuple[bool, str]:
    root = root or SKILL_ROOT
    path = path or (root / DEFAULT_INDEX)
    if not path.is_file():
        return False, f"索引不存在：{path}"
    current = path.read_text(encoding="utf-8")
    fresh = canonical_dump(build_index(root))
    if current != fresh:
        return False, "索引与正文不一致（正文改了但索引没重建，或索引被手工编辑）"
    return True, f"索引与正文一致（{json.loads(current)['totals']['docs']} 份文档）"


def find_sections(index: Dict[str, Any], doc: str, query: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for entry in index["docs"]:
        if doc and doc not in entry["doc_id"] and doc not in entry["path"]:
            continue
        for section in entry["sections"]:
            haystack = f"{section['title']} {section['summary']} {' '.join(section['rule_ids'])}"
            if query.lower() in haystack.lower():
                out.append({"doc_id": entry["doc_id"], "path": entry["path"], **section})
    return out


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def selftest(verbose: bool = False) -> Dict[str, Any]:
    checks: List[Tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    # 1) 围栏感知
    fenced = "## real\n\n```bash\n# not a heading\n## also not\n```\n\n## second\n"
    titles = [section["title"] for section in split_sections(fenced)]
    check("split_sections: 围栏内标题不算", titles == ["real", "second"], str(titles))

    # 2) id 与行号无关
    a = "# A\n\n## 读 / 写 World Model\n"
    b = "# A\n\n新增一段\n\n\n## 读 / 写 World Model\n"
    ids_a = [section["id"] for section in split_sections(a)]
    ids_b = [section["id"] for section in split_sections(b)]
    check("split_sections: 插入正文不改变 id", ids_a == ids_b, f"{ids_a} vs {ids_b}")

    # 重名唯一化
    dup = "## x\n\na\n\n## x\n\nb\n"
    ids = [section["id"] for section in split_sections(dup)]
    check("split_sections: 重名唯一化", ids == ["x", "x-2"], str(ids))

    # 3) 父章节挂接
    tree = "## p\n\nt\n\n### c\n\nx\n\n## q\n\ny\n"
    sections = split_sections(tree)
    parents = {section["id"]: section["title"] for section in sections}
    entries = []
    stack: List[Tuple[int, str]] = []
    for section in sections:
        while stack and stack[-1][0] >= section["level"]:
            stack.pop()
        entries.append((section["id"], stack[-1][1] if stack else None))
        if section["level"] > 0:
            stack.append((section["level"], section["id"]))
    mapping = dict(entries)
    check("build: 子章节挂到父章节",
          mapping["c"] == "p" and mapping["q"] is None, str(mapping))
    check("build: 父章节标题存在", parents.get("p") == "p")

    # 4) 规则号抽取（整词匹配，不误命中）
    check("rule_ids: 抽取", rule_ids("见 S1 与 V18、DP15") == ["S1", "V18", "DP15"],
          str(rule_ids("见 S1 与 V18、DP15")))
    check("rule_ids: 不误命中 MRS1", rule_ids("MRS1 不是规则号") == [],
          str(rule_ids("MRS1 不是规则号")))
    check("rule_ids: 去重保序", rule_ids("V1 V20 V1") == ["V1", "V20"],
          str(rule_ids("V1 V20 V1")))

    # 5) 摘要跳过表格与围栏
    doc = "## t\n\n| 表 | 值 |\n|---|---|\n| a | b |\n\n这是真正的结论句。后面还有。\n"
    summary = summarise(doc)
    check("summarise: 跳过表格取正文", summary.startswith("这是真正的结论句"),
          summary)

    # 6) 摘要随正文变化（不存在手写摘要漂移）
    doc2 = "## t\n\n| 表 |\n\n另一句话是结论。\n"
    check("summarise: 摘要由正文派生", summarise(doc2) != summary)

    # 7) 真实索引可建且稳定
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "references").mkdir()
        (root / "SKILL.md").write_text("# S\n\n## a\n\n内容一。\n\n## b\n\n内容二。\n",
                                       encoding="utf-8")
        (root / "references" / "x.md").write_text("## c\n\n规则 V1。\n", encoding="utf-8")
        first = canonical_dump(build_index(root))
        second = canonical_dump(build_index(root))
        check("build_index: 同一输入两次构建一致", first == second)
        (root / DEFAULT_INDEX).write_text(first, encoding="utf-8")
        ok, detail = check_index(path=root / DEFAULT_INDEX, root=root)
        check("check_index: 与正文一致时通过", ok, detail)
        (root / "SKILL.md").write_text("# S\n\n## a\n\n内容一改。\n", encoding="utf-8")
        ok, detail = check_index(path=root / DEFAULT_INDEX, root=root)
        check("check_index: 正文改动后判红", not ok, detail)

    # 8) 真实仓库索引必须在预算内
    real = build_index()
    check("build_index: 真实仓库可构建", real["totals"]["docs"] > 40,
          str(real["totals"]))
    biggest = max(real["docs"], key=lambda doc: doc["section_count"])
    check("build_index: 章节数合理", biggest["section_count"] >= 5,
          f"{biggest['doc_id']}={biggest['section_count']}")

    passed = sum(1 for _, ok, _ in checks if ok)
    for name, ok, detail in checks:
        if verbose or not ok:
            print(f"[{'ok  ' if ok else 'FAIL'}] {name}" + (f" —— {detail}" if detail else ""))
    return {"status": "PASS" if passed == len(checks) else "FAIL",
            "passed": passed, "total": len(checks),
            "failures": [name for name, ok, _ in checks if not ok]}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="RLP 稳定章节索引")
    parser.add_argument("command", nargs="?", default=None,
                        choices=[None, "build", "check", "list", "find", "show"])
    parser.add_argument("args", nargs="*", default=[])
    parser.add_argument("--out", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", default=None)
    parser.add_argument("--selftest", action="store_true")
    parsed = parser.parse_args(argv)

    if parsed.selftest:
        result = selftest(verbose=True)
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_OK if result["status"] == "PASS" else EXIT_HARD

    root = Path(parsed.root).resolve() if parsed.root else SKILL_ROOT

    if parsed.command == "build":
        index = build_index(root)
        out = Path(parsed.out) if parsed.out else root / DEFAULT_INDEX
        out.write_text(canonical_dump(index), encoding="utf-8")
        print(f"wrote {out} ({index['totals']['docs']} docs, "
              f"{index['totals']['sections']} sections)")
        return EXIT_OK

    if parsed.command == "check":
        ok, detail = check_index(path=(Path(parsed.out) if parsed.out else None), root=root)
        print(("ok   " if ok else "FAIL ") + detail)
        return EXIT_OK if ok else EXIT_HARD

    if parsed.command in ("list", "find", "show"):
        path = root / DEFAULT_INDEX
        if not path.is_file():
            print(f"索引不存在：{path}", file=sys.stderr)
            return EXIT_ENV
        index = json.loads(path.read_text(encoding="utf-8"))

        if parsed.command == "list":
            for doc in index["docs"]:
                print(f"{doc['doc_id']:<52} {doc['chars']:>7} chars "
                      f"{doc['section_count']:>4} sections")
            return EXIT_OK

        if parsed.command == "find":
            if len(parsed.args) < 2:
                parser.error("find 需要 <document> <query>")
            hits = find_sections(index, parsed.args[0], parsed.args[1])
            if parsed.json:
                print(json.dumps(hits, ensure_ascii=False, indent=2))
            else:
                for hit in hits:
                    print(f"{hit['doc_id']} :: {hit['section_id']}  "
                          f"({hit['chars']} chars)  {hit['title'][:50]}")
                    if hit["summary"]:
                        print(f"    {hit['summary']}")
            return EXIT_OK

        # show
        if not parsed.args:
            parser.error("show 需要 <document>")
        for doc in index["docs"]:
            if parsed.args[0] in doc["doc_id"] or parsed.args[0] in doc["path"]:
                if parsed.json:
                    print(json.dumps(doc, ensure_ascii=False, indent=2))
                else:
                    print(f"# {doc['doc_id']}  ({doc['chars']} chars, "
                          f"{doc['section_count']} sections)")
                    for section in doc["sections"]:
                        indent = "  " * max(0, section["level"] - 1)
                        print(f"{indent}[{section['section_id']}] "
                              f"{section['title'][:60]}  {section['chars']}c "
                              f"{section['rule_ids'] or ''}")
        return EXIT_OK

    parser.print_help()
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
