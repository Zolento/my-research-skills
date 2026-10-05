#!/usr/bin/env python3
"""refs_index.py — 为 docs/refs/ 下的 PDF 建立索引（references/literature-policy.md §7）

规约：**`docs/refs/` 下的每一个 PDF 都必须在 `docs/refs/index.json` 里有一条记录。**
索引是**可进版本库的元数据**，PDF 本身是大文件、不进版本库。

用法：
    python3 refs_index.py                        # 扫描 ./docs/refs，写入 ./docs/refs/index.json
    python3 refs_index.py --check                # 只校验不写入；不一致时退出码 3
    python3 refs_index.py --refs-dir ./refs --json
    python3 refs_index.py --no-hash              # 跳过 sha256（大库提速）

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
        return default

    arxiv_id = _arxiv_id_from(pick("arxiv_id")) or _arxiv_id_from(pdf.stem) \
        or _arxiv_id_from(str(pick("url") or ""))

    title = _clean_str(pick("title"))
    metadata_from = "sidecar" if (sidecar and sidecar.get("title")) else embedded_from
    if not title:
        title = _title_from_filename(pdf)
        metadata_from = "filename"

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
        "needs_verification": metadata_from == "filename" or year is None,
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


def scan_pdfs(refs_dir: Path) -> List[Path]:
    return sorted(
        (p for p in refs_dir.rglob("*.pdf") if p.is_file()),
        key=lambda p: p.relative_to(refs_dir).as_posix(),
    )


def build_index(refs_dir: Path, with_hash: bool) -> Dict[str, Any]:
    previous = load_previous(refs_dir / INDEX_NAME)
    entries = [
        build_entry(pdf, refs_dir, with_hash, previous.get(pdf.relative_to(refs_dir).as_posix(), {}))
        for pdf in scan_pdfs(refs_dir)
    ]
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "count": len(entries),
        # ★ 不写 refs_dir：索引本身就在 refs 目录内，写绝对路径会导致换机器后失效
        "pdfs": entries,
    }


def check_index(refs_dir: Path, index: Dict[str, Any]) -> List[str]:
    """比对索引文件与磁盘。返回问题列表（空 = 一致）。"""
    problems: List[str] = []
    raw_entries = index.get("pdfs") if isinstance(index, dict) else None
    if not isinstance(raw_entries, list):
        return ["索引缺少 pdfs 数组（schema 不符）"]

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
            log(f"[stale] 共 {len(problems)} 处不一致；请运行："
                f"python3 {Path(__file__).name} --refs-dir {refs_dir}")
            return EXIT_STALE
        log(f"[ok] 索引与 {len(on_disk_index.get('pdfs', []))} 个 PDF 一致")
        return EXIT_OK

    try:
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
