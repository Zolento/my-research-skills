#!/usr/bin/env python3
"""refs_index.py — 为 docs/refs/ 下的 PDF 建立索引（references/literature-policy.md §7）

规约：**`docs/refs/` 下的每一个 PDF 都必须在 `docs/refs/index.json` 里有一条记录。**
索引是**可进版本库的元数据**，PDF 本身是大文件、不进版本库。

用法：
    python3 refs_index.py                        # 扫描 ./docs/refs，写入 ./docs/refs/index.json
    python3 refs_index.py --check                # 只校验不写入；不一致时退出码 3
    python3 refs_index.py --migrate              # 旧 schema → 当前 schema（保留旧字段，标 migrated_from）
    python3 refs_index.py --refs-dir ./refs --json
    python3 refs_index.py --no-hash              # 跳过 sha256（大库提速）

迁移（--migrate）：
    旧版索引可能不是 `{"schema":…, "pdfs":[…]}` 形状（例如平铺列表，或按文件名做键的字典），
    此时 `--check` 会报「索引缺少 pdfs 数组」而**无法直接重建**（重建会丢掉旧字段）。
    `--migrate` 的语义：**保留旧条目里已有的字段**，补齐当前 schema 所需字段，
    并在索引顶层写入 `migrated_from`（旧 schema 字符串）与 `migrated_at`。
    迁移后请仍用 `--check` 确认一致；元数据缺口由 `needs_verification` 标出。

元数据来源优先级：
    1. sidecar 元数据 `<refs-dir>/papers/{paper_id}.json`（由检索脚本写入，最准）
    2. PDF 内嵌元数据（pypdf；缺失时回退命令行 pdfinfo）
    3. 文件名解析（仅作兜底，会标记 needs_verification = true）

退出码：
    0  正常（已写入；或 --check 下已是最新）
    1  硬错误（参数错误、目录不可读、写入失败）
    3  --check 模式下索引与 PDF 集合不一致（缺条目 / 条目过期 / 文件已删）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA = "research-idea-pipeline/refs-index@1"
DEFAULT_REFS_DIR = os.environ.get("RESEARCH_LOCAL_LITERATURE", "./docs/refs")
INDEX_NAME = "index.json"

# arXiv 新式编号 YYMM.NNNNN；旧式 category/NNNNNNN 也认
_ARXIV_NEW_RE = re.compile(r"(?:arXiv[:\s]*)?\b(\d{4}\.\d{4,5})\b", re.IGNORECASE)
_ARXIV_OLD_RE = re.compile(r"\b([a-z-]+(?:\.[A-Z]{2})?/\d{7})\b")
_CREATION_DATE_RE = re.compile(r"D:(\d{4})")

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_STALE = 3


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def _log_stderr(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _noop_log(message: str) -> None:
    pass


def _sha256(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _clean_str(value: Any) -> Optional[str]:
    """把 PDF 元数据里的脏值（空串、None、b'...'、'untitled'）归一成 None。"""
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    text = str(value).strip().strip("\x00").strip()
    if not text:
        return None
    if text.lower() in {"untitled", "unknown", "none", "null", "(anonymous)"}:
        return None
    return re.sub(r"\s+", " ", text)


def _split_authors(raw: Optional[str]) -> List[str]:
    """拆作者。`A and B` / `A; B` 优先；否则逗号数 ≥2 时按逗号拆。"""
    text = _clean_str(raw)
    if not text:
        return []
    for sep in (";", " and "):
        if sep in text:
            parts = [p.strip() for p in text.split(sep)]
            return [p for p in parts if p]
    if text.count(",") >= 2:
        parts = [p.strip() for p in text.split(",")]
        return [p for p in parts if p]
    return [text]


def _split_keywords(raw: Any) -> List[str]:
    """关键词归一：None → []；字符串按 ; 与 , 拆分并去空白。"""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        parts = [str(item) for item in raw]
    else:
        parts = re.split(r"[;,]", str(raw))
    return [part.strip() for part in parts if part.strip()]


def _arxiv_id_from(text: Optional[str]) -> Optional[str]:
    text = _clean_str(text)
    if not text:
        return None
    match = _ARXIV_NEW_RE.search(text) or _ARXIV_OLD_RE.search(text.lower())
    return match.group(1) if match else None


def _year_from_arxiv_id(arxiv_id: Optional[str]) -> Optional[int]:
    """YYMM.NNNNN → 20YY；旧式 category/NNNNNNN 无法判定，返回 None。"""
    if not arxiv_id:
        return None
    head = arxiv_id.split(".")[0]
    if "/" in head:  # 旧式 cs/0601001，没有年份信息
        return None
    if len(head) == 4 and head.isdigit():
        yy = int(head[:2])
        return 2000 + yy if yy < 90 else 1900 + yy
    return None


def _year_from_creation(value: Optional[str]) -> Optional[int]:
    text = _clean_str(value)
    if not text:
        return None
    match = _CREATION_DATE_RE.search(text)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return int(match.group(0)) if match else None


def _title_from_filename(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"^(arxiv[_-]?)?(\d{4}\.\d{4,5})(v\d+)?[_-]?", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem or path.stem


# ---------------------------------------------------------------------------
# PDF 元数据抽取
# ---------------------------------------------------------------------------

def _meta_from_pypdf(path: Path) -> Optional[Dict[str, Any]]:
    """用 pypdf 读内嵌元数据 + 页数 + 首页 arXiv 编号。失败返回 None。"""
    try:
        import pypdf  # type: ignore
    except ImportError:
        return None

    try:
        import logging
        logging.getLogger("pypdf").setLevel(logging.ERROR)
    except Exception:  # noqa: BLE001
        pass

    try:
        with open(path, "rb") as handle:
            reader = pypdf.PdfReader(handle)
            pages = len(reader.pages)
            raw = getattr(reader, "metadata", None) or {}

            def field(name: str) -> Optional[str]:
                try:
                    return _clean_str(raw.get(name))
                except Exception:  # noqa: BLE001
                    return None

            title = field("/Title")
            author = field("/Author")
            keywords = field("/Keywords")
            created = field("/CreationDate")
            first_page_text = ""
            if reader.pages:
                try:
                    first_page_text = reader.pages[0].extract_text() or ""
                except Exception:  # noqa: BLE001
                    first_page_text = ""
    except Exception:  # noqa: BLE001
        return None

    return {
        "title": title,
        "authors": _split_authors(author),
        "keywords": _split_keywords(keywords),
        "year": _year_from_creation(created),
        "pages": pages,
        "arxiv_id": _arxiv_id_from(first_page_text),
    }


def _meta_from_pdfinfo(path: Path) -> Optional[Dict[str, Any]]:
    """回退：poppler 的 pdfinfo 命令行。"""
    binary = shutil.which("pdfinfo")
    if not binary:
        return None
    try:
        proc = subprocess.run(
            [binary, str(path)], capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None

    fields: Dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip().lower()] = value.strip()

    pages_raw = fields.get("pages")
    return {
        "title": _clean_str(fields.get("title")),
        "authors": _split_authors(fields.get("author")),
        "keywords": _split_keywords(fields.get("keywords")),
        "year": _year_from_creation(fields.get("creationdate")),
        "pages": int(pages_raw) if pages_raw and pages_raw.isdigit() else None,
        "arxiv_id": None,
    }


def _sidecar_for(refs_dir: Path, pdf: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """查找同名 sidecar 元数据。返回 (元数据, 相对路径)。"""
    candidates = [
        pdf.with_suffix(".json"),
        refs_dir / "papers" / f"{pdf.stem}.json",
    ]
    for candidate in candidates:
        if candidate.is_file() and candidate != pdf:
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                return data, candidate.relative_to(refs_dir).as_posix()
    return None, None


# ---------------------------------------------------------------------------
# 单条记录
# ---------------------------------------------------------------------------

def build_entry(
    pdf: Path, refs_dir: Path, with_hash: bool, previous: Dict[str, Any],
) -> Dict[str, Any]:
    rel = pdf.relative_to(refs_dir).as_posix()
    sidecar, sidecar_rel = _sidecar_for(refs_dir, pdf)

    embedded = _meta_from_pypdf(pdf) or _meta_from_pdfinfo(pdf)
    embedded_from = "pdf" if embedded else None

    def pick(key: str, default: Any = None) -> Any:
        if sidecar and sidecar.get(key) not in (None, "", [], {}):
            return sidecar[key]
        if embedded and embedded.get(key) not in (None, "", []):
            return embedded[key]
        # ★ 最低优先级：继承旧索引里的字段（--migrate 的"保留旧字段"就靠这一条）
        if previous and previous.get(key) not in (None, "", [], {}):
            return previous[key]
        return default

    arxiv_id = _arxiv_id_from(pick("arxiv_id")) or _arxiv_id_from(pdf.stem) \
        or _arxiv_id_from(str(pick("url") or ""))

    title = _clean_str(pick("title"))
    metadata_from = "sidecar" if (sidecar and sidecar.get("title")) else embedded_from
    if not title:
        title = _title_from_filename(pdf)
        metadata_from = "filename"
    elif metadata_from is None:
        # 标题只可能来自旧索引（sidecar/embedded 都没有）
        metadata_from = "legacy"

    authors = pick("authors")
    if not isinstance(authors, list):
        authors = _split_authors(authors)

    keywords = _split_keywords(pick("keywords"))

    year = pick("year")
    if not isinstance(year, int):
        year = _year_from_arxiv_id(arxiv_id) or (
            embedded.get("year") if embedded else None
        )
    if not isinstance(year, int):
        year = None

    url = pick("url")
    if not url and arxiv_id:
        url = f"https://arxiv.org/abs/{arxiv_id}"

    notes_path = pdf.with_suffix(".md")
    stats = pdf.stat()

    sha = previous.get("sha256") if previous else None
    if with_hash:
        sha = _sha256(pdf)
    elif not sha:
        sha = None

    added_at = previous.get("added_at") if previous else None
    if not added_at or (with_hash and previous and previous.get("sha256") != sha):
        added_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")

    return {
        "file": rel,
        "paper_id": _clean_str(pick("paper_id")) or arxiv_id or pdf.stem,
        "title": title,
        "authors": authors,
        "year": year,
        "venue": _clean_str(pick("venue")),
        "arxiv_id": arxiv_id,
        "doi": _clean_str(pick("doi")),
        "url": url,
        "abstract": _clean_str(pick("abstract")),
        "keywords": keywords,
        "pages": pick("pages"),
        "size_bytes": stats.st_size,
        "sha256": sha,
        "added_at": added_at,
        "source": _clean_str(pick("source")) or "local",
        "metadata_from": metadata_from,
        # 继承来的旧元数据同样不算"已核实"——除非旧条目自己已明确核实过
        "needs_verification": (
            (previous.get("needs_verification") is True)
            if metadata_from == "legacy" and isinstance(previous.get("needs_verification"), bool)
            else (metadata_from in {"filename", "legacy"} or year is None)
        ),
        "sidecar_path": sidecar_rel,
        "notes_path": notes_path.relative_to(refs_dir).as_posix() if notes_path.is_file() else None,
    }


# ---------------------------------------------------------------------------
# 索引读写
# ---------------------------------------------------------------------------

def load_previous(output: Path) -> Dict[str, Dict[str, Any]]:
    if not output.is_file():
        return {}
    try:
        data = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    entries = data.get("pdfs") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return {}
    return {
        entry["file"]: entry
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("file"), str)
    }


# 旧索引可能用过的"文件路径"字段名（按优先级）
_LEGACY_PATH_KEYS = ("file", "path", "rel", "relative_path", "filename", "pdf", "name")


def harvest_legacy(data: Any) -> Dict[str, Dict[str, Any]]:
    """从**任意形状**的旧索引里抽出 {相对路径: 记录}。抽不出就返回 {}。

    支持三类旧形状：
      1. 平铺列表：`[{"file": "a.pdf", ...}, ...]`
      2. 具名列表：`{"records"|"entries"|"papers"|"items": [...]}`
      3. 以文件名为键的字典：`{"a.pdf": {...}, ...}`
    """
    def _pick(record: Dict[str, Any], fallback_key: Optional[str] = None) -> Optional[str]:
        for key in _LEGACY_PATH_KEYS:
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return fallback_key if fallback_key else None

    harvested: Dict[str, Dict[str, Any]] = {}

    def _consume(records: Dict[str, Dict[str, Any]], keyed: bool) -> None:
        for key, record in records.items():
            if not isinstance(record, dict):
                continue
            rel = _pick(record, key if keyed else None)
            if rel:
                harvested[rel.lstrip("./")] = record

    if isinstance(data, list):
        _consume({str(i): r for i, r in enumerate(data)}, keyed=False)
        return harvested

    if not isinstance(data, dict):
        return harvested

    for list_key in ("records", "entries", "papers", "items", "pdfs"):
        value = data.get(list_key)
        if isinstance(value, list):
            _consume({str(i): r for i, r in enumerate(value)}, keyed=False)
            return harvested

    # 以文件名为键的字典（排除元信息键）
    meta_keys = {"schema", "version", "generated_at", "count", "migrated_from", "migrated_at"}
    _consume(
        {k: v for k, v in data.items() if k not in meta_keys},
        keyed=True,
    )
    return harvested


def legacy_schema_of(data: Any) -> Optional[str]:
    """取旧索引自称的 schema 字符串；没有就返回 `unknown`。"""
    if isinstance(data, dict):
        for key in ("schema", "_schema", "version"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "unknown" if data else None


def scan_pdfs(refs_dir: Path) -> List[Path]:
    return sorted(
        (p for p in refs_dir.rglob("*.pdf") if p.is_file()),
        key=lambda p: p.relative_to(refs_dir).as_posix(),
    )


def build_index(
    refs_dir: Path,
    with_hash: bool,
    previous_override: Optional[Dict[str, Dict[str, Any]]] = None,
    migrated_from: Optional[str] = None,
) -> Dict[str, Any]:
    previous = (
        previous_override
        if previous_override is not None
        else load_previous(refs_dir / INDEX_NAME)
    )
    entries = [
        build_entry(pdf, refs_dir, with_hash, previous.get(pdf.relative_to(refs_dir).as_posix(), {}))
        for pdf in scan_pdfs(refs_dir)
    ]
    index: Dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "count": len(entries),
        # ★ 不写 refs_dir：索引本身就在 refs 目录内，写绝对路径会导致换机器后失效
        "pdfs": entries,
    }
    if migrated_from:
        index["migrated_from"] = migrated_from
        index["migrated_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        index["_migrate_note"] = (
            "本索引由 refs_index.py --migrate 从旧 schema 迁移而来；"
            "旧字段已尽量保留，缺失字段由 needs_verification 标出，请人工补齐后重建。"
        )
    return index


def check_index(refs_dir: Path, index: Dict[str, Any]) -> List[str]:
    """比对索引文件与磁盘。返回问题列表（空 = 一致）。"""
    problems: List[str] = []
    raw_entries = index.get("pdfs") if isinstance(index, dict) else None
    if not isinstance(raw_entries, list):
        return [
            "索引缺少 pdfs 数组（schema 不符）—— 旧版索引请先迁移："
            "`python3 refs_index.py --migrate`（保留旧字段），再跑 --check"
        ]

    indexed: Dict[str, Dict[str, Any]] = {}
    for entry in raw_entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
            problems.append(f"索引条目缺少 file 字段：{str(entry)[:80]}")
            continue
        indexed[entry["file"]] = entry

    on_disk = {p.relative_to(refs_dir).as_posix(): p for p in scan_pdfs(refs_dir)}

    for rel in sorted(set(on_disk) - set(indexed)):
        problems.append(f"缺索引条目：{rel}")
    for rel in sorted(set(indexed) - set(on_disk)):
        problems.append(f"索引指向已不存在的文件：{rel}")
    for rel in sorted(set(on_disk) & set(indexed)):
        want = indexed[rel].get("sha256")
        if not want:
            problems.append(f"索引缺少 sha256：{rel}（重建时不要用 --no-hash）")
            continue
        got = _sha256(on_disk[rel])
        if want != got:
            problems.append(f"文件已变更但索引未更新：{rel}")
    return problems


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    """参数错误退出码必须是 1，不能与"索引过期(3)"混淆。"""

    def error(self, message: str):  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="refs_index.py",
        description="为 docs/refs/ 下的 PDF 建立索引（references/literature-policy.md §7）",
    )
    parser.add_argument("--refs-dir", default=DEFAULT_REFS_DIR,
                        help=f"参考文献库根目录（默认 {DEFAULT_REFS_DIR}）")
    parser.add_argument("--output", default=None,
                        help=f"索引输出路径（默认 <refs-dir>/{INDEX_NAME}）")
    parser.add_argument("--check", action="store_true",
                        help="只校验索引与 PDF 集合是否一致，不写入；不一致退出码 3")
    parser.add_argument("--migrate", action="store_true",
                        help="旧 schema → 当前 schema：保留旧条目字段，补 migrated_from/migrated_at")
    parser.add_argument("--no-hash", action="store_true",
                        help="跳过 sha256 计算（大库提速；--check 下会报缺少 sha256）")
    parser.add_argument("--json", action="store_true", help="把索引打印到 stdout")
    parser.add_argument("--quiet", action="store_true", help="不输出过程日志")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    log = _noop_log if args.quiet else _log_stderr

    refs_dir = Path(args.refs_dir).expanduser().resolve()
    if not refs_dir.is_dir():
        log(f"[error] 参考文献库目录不存在：{refs_dir}")
        return EXIT_ERROR

    output = Path(args.output).expanduser().resolve() if args.output else refs_dir / INDEX_NAME
    with_hash = not args.no_hash

    if args.check:
        if not output.is_file():
            log(f"[stale] 索引文件不存在：{output}")
            return EXIT_STALE
        try:
            on_disk_index = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log(f"[error] 索引文件无法解析：{exc}")
            return EXIT_ERROR
        try:
            problems = check_index(refs_dir, on_disk_index)
        except OSError as exc:
            log(f"[error] 校验失败：{exc}")
            return EXIT_ERROR
        if problems:
            for line in problems:
                log(f"[stale] {line}")
            schema_mismatch = any("pdfs 数组" in line for line in problems)
            hint = ("python3 %s --refs-dir %s --migrate" % (Path(__file__).name, refs_dir)
                    if schema_mismatch
                    else "python3 %s --refs-dir %s" % (Path(__file__).name, refs_dir))
            log(f"[stale] 共 {len(problems)} 处不一致；请运行：{hint}")
            return EXIT_STALE
        log(f"[ok] 索引与 {len(on_disk_index.get('pdfs', []))} 个 PDF 一致")
        return EXIT_OK

    try:
        if args.migrate:
            raw: Any = None
            if output.is_file():
                try:
                    raw = json.loads(output.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    log(f"[error] 旧索引无法解析，无法迁移：{exc}")
                    return EXIT_ERROR
            harvested = harvest_legacy(raw)
            old_schema = legacy_schema_of(raw)
            if raw is not None and old_schema == SCHEMA:
                log(f"[ok] 已是当前 schema（{SCHEMA}），无需迁移；如需重建请直接运行不加 --migrate")
                return EXIT_OK
            index = build_index(
                refs_dir,
                with_hash=with_hash,
                previous_override=harvested,
                # 索引本来就不存在时，这是「首次建立」而不是「迁移」，不得标 migrated_from
                migrated_from=(old_schema or "unknown") if raw is not None else None,
            )
            if raw is None:
                log(f"[migrate] 无既有索引，按当前 schema 直接建立（{index['count']} 条）")
            else:
                log(f"[migrate] 旧 schema = {old_schema or 'unknown'}；"
                    f"保留 {len(harvested)} 条旧记录，扫描到 {index['count']} 个 PDF")
        else:
            index = build_index(refs_dir, with_hash=with_hash)
    except OSError as exc:
        log(f"[error] 扫描失败：{exc}")
        return EXIT_ERROR

    if args.json:
        print(json.dumps(index, ensure_ascii=False, indent=2))
        return EXIT_OK

    try:
        output.write_text(
            json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
    except OSError as exc:
        log(f"[error] 写入索引失败：{exc}")
        return EXIT_ERROR

    flagged = sum(1 for entry in index["pdfs"] if entry.get("needs_verification"))
    log(f"[ok] 已写入 {output}（{index['count']} 条 PDF"
        + (f"，其中 {flagged} 条待核实" if flagged else "") + "）")
    if flagged:
        log("[warn] 存在 needs_verification=true 的条目：元数据来自文件名兜底，"
            "请人工补齐 title/authors/year 后重建索引")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
