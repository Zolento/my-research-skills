#!/usr/bin/env python3
"""zotero_refs.py — 把本地 Zotero 库导出成流水线旧的 `docs/refs/` 格式。

为什么要它
----------
`literature_search.py::search_local` 只认 `docs/refs/papers/*.json` sidecar；
而本项目真实的 744 篇文献在本地 Zotero 里。本脚本把 Zotero 的元数据落成
sidecar（喂本地检索），并在需要时把 Zotero storage 里的 PDF **软链**进来，
交给 `refs_index.py` 建索引。**绝不复制 PDF**（约 6.3 GB）。

两种模式
--------
1. 默认（元数据模式）：只写 `<refs-dir>/papers/<paper_id>.json`，
   **不碰 `index.json`**。没有 PDF 就没有索引义务，`refs_index.py --check` 仍成立。
2. `--link-pdfs`：额外建软链 `<refs-dir>/papers/<paper_id>.pdf` →
   `<storage>/<attachmentKey>/<filename>`，然后用 `refs_index.build_index`
   重建 `index.json`。索引永远只覆盖**磁盘上真实存在**的 PDF，
   因此不会出现指向幽灵文件的条目。

用法：
    python3 scripts/zotero_refs.py                       # 只导出 sidecar
    python3 scripts/zotero_refs.py --link-pdfs           # sidecar + 软链 + 重建索引
    python3 scripts/zotero_refs.py --check               # 只检查漂移，不写入
    python3 scripts/zotero_refs.py --dry-run --limit 5   # 预演前 5 条
    python3 scripts/zotero_refs.py --link-pdfs --json    # 机器可读摘要

退出码（与 refs_index.py / literature_search.py 保持一致）：
    0  正常（导出完成；--check 下与 Zotero 一致）
    1  硬错误（参数错误、写入失败）
    3  --check 模式发现漂移（缺 sidecar / 内容过期 / 孤儿 sidecar）
    4  Zotero 不可达（未运行 / 地址错误 / 超时）—— 不是"没人做过"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:  # 允许 `python3 scripts/zotero_refs.py` 直接跑
    sys.path.insert(0, str(SCRIPTS_DIR))

import refs_index as ri  # noqa: E402
import zotero_client as zc  # noqa: E402

# ---------------------------------------------------------------------------
# 常量与退出码
# ---------------------------------------------------------------------------

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_STALE = 3
EXIT_ENV = 4

#: 参考文献库根目录（与 literature_search.py 的默认一致）。
DEFAULT_REFS_DIR = os.environ.get("RESEARCH_LOCAL_LITERATURE", "./docs/refs")

#: Zotero 存储根目录：`<root>/<attachmentKey>/<filename>`。
DEFAULT_STORAGE_DIR = os.environ.get("ZOTERO_STORAGE", "~/Zotero/storage")

#: 本地 API 地址；显式给 `--zotero-url` 时优先。
DEFAULT_ZOTERO_URL = os.environ.get("ZOTERO_LOCAL_API")

#: sidecar 子目录名（§7 约定）。
SIDECAR_DIRNAME = "papers"

#: `file` / `size_bytes` / `sha256` **只在真正链上 PDF 时**才写。
PDF_ONLY_FIELDS = ("file", "size_bytes", "sha256")

#: sidecar 字段顺序（保证同一输入产生逐字节相同的文件）。
SIDECAR_FIELD_ORDER = (
    "paper_id", "zotero_key", "title", "authors", "year", "venue",
    "arxiv_id", "doi", "url", "abstract", "keywords",
    "file", "size_bytes", "sha256",
    "added_at", "source", "metadata_from", "needs_verification",
)

#: paper_id 里不允许出现的字符（`/` 会在 DOI 中大量出现，必须替换）。
_UNSAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_PAPER_ID = 180


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def _log_stderr(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _noop_log(message: str) -> None:
    pass


def _item_key(item: Dict[str, Any]) -> str:
    return str((item or {}).get("key") or "")


def safe_paper_id(raw: Any) -> Optional[str]:
    """把 arXiv ID / DOI / Zotero key 归一成**确定且文件系统安全**的 paper_id。

    规则：
    * `/` 与其他不安全字符统一替换为 `_`（DOI 形如 `10.1000/xyz` 必须处理）；
    * 去掉首尾的点、下划线、连字符，避免隐藏文件与穿越；
    * 过长时截断并追加内容哈希，保证仍然确定、不碰撞且不超文件名上限。
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    text = text.replace("/", "_")
    text = _UNSAFE_RE.sub("_", text)
    text = text.strip("._-")
    text = text.replace("..", "_").strip("._-")
    if not text:
        return None
    if len(text) > _MAX_PAPER_ID:
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
        text = f"{text[: _MAX_PAPER_ID - 9]}-{digest}"
    return text


def assign_paper_ids(bib: List[Dict[str, Any]]) -> Dict[str, str]:
    """给每条可引用条目分配 paper_id；同 ID 冲突时按 Zotero key 稳定消歧。

    优先级沿用 `zotero_client.item_to_sidecar`：arXiv ID → DOI → Zotero key。
    """
    by_base: Dict[str, List[Dict[str, Any]]] = {}
    for item in bib:
        base = safe_paper_id(zc.item_to_sidecar(item).get("paper_id"))
        base = base or safe_paper_id(_item_key(item)) or "item"
        by_base.setdefault(base, []).append(item)

    assigned: Dict[str, str] = {}
    for base, group in by_base.items():
        if len(group) == 1:
            assigned[_item_key(group[0])] = base
            continue
        # 两条不同文献算出同一个 paper_id：保留 key 最小者拿 base，其余带后缀。
        for index, item in enumerate(sorted(group, key=_item_key)):
            key = _item_key(item)
            if index == 0:
                assigned[key] = base
            else:
                assigned[key] = safe_paper_id(f"{base}-{key}") or f"{base}-{index}"
    return assigned


def _serialize(payload: Dict[str, Any]) -> str:
    """sidecar 的标准序列化形式（缩进 2、UTF-8 原文、结尾换行）。"""
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _ordered(payload: Dict[str, Any]) -> Dict[str, Any]:
    """按固定字段序重排，保证逐字节可重现。"""
    ordered = {key: payload[key] for key in SIDECAR_FIELD_ORDER if key in payload}
    for key, value in payload.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def _load_sidecar(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def attachment_relpath(att: Dict[str, Any]) -> Optional[str]:
    """附件在 storage 内的相对路径。

    Zotero 本地 API 对 `imported_file` 往往只给 `filename`（`path` 为 null），
    因此先认 `path=storage:...`，缺失时退回 `filename`。
    """
    data = (att or {}).get("data") or {}
    raw = data.get("path")
    if isinstance(raw, str) and raw.startswith("storage:"):
        inner = raw[len("storage:"):].strip()
        if inner:
            return inner
    filename = data.get("filename")
    if isinstance(filename, str) and filename.strip():
        return os.path.basename(filename.strip())
    return None


def attachment_path(att: Dict[str, Any], storage_dir: Path) -> Optional[Path]:
    """把附件映射到真实文件路径；无法安全映射时返回 None。"""
    key = _item_key(att)
    rel = attachment_relpath(att)
    if not key or not rel:
        return None
    if os.path.isabs(rel) or ".." in Path(rel).parts:
        return None
    return storage_dir / key / rel


# ---------------------------------------------------------------------------
# 计划（导出 / 检查共用同一份"期望状态"）
# ---------------------------------------------------------------------------

def _pick_pdf(
    parent_key: str,
    children: Dict[str, List[Dict[str, Any]]],
    storage_dir: Path,
) -> Tuple[Optional[Dict[str, Any]], Optional[Path]]:
    """取该父条目第一个**真实存在**的 PDF 附件（按附件 key 稳定排序）。"""
    for att in sorted(children.get(parent_key, []), key=_item_key):
        target = attachment_path(att, storage_dir)
        if target is not None and target.is_file():
            return att, target
    return None, None


def _desired_payload(
    item: Dict[str, Any],
    paper_id: str,
    pdf_rel: Optional[str],
    target: Optional[Path],
    existing: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """构造该条目**应该**写出的 sidecar 内容。"""
    payload = zc.item_to_sidecar(item)
    payload["paper_id"] = paper_id
    payload.pop("notes_path", None)  # 本脚本不产出 .md 全文

    if pdf_rel is None or target is None:
        for field in PDF_ONLY_FIELDS:
            payload.pop(field, None)
    else:
        size = target.stat().st_size
        sha = None
        # 目标未变（同一相对路径 + 同一大小）时复用旧 sha256，避免每次重读 6.3 GB。
        # 索引里的 sha256 由 refs_index.py 权威计算，不受此影响。
        if (
            isinstance(existing, dict)
            and existing.get("file") == pdf_rel
            and existing.get("size_bytes") == size
            and isinstance(existing.get("sha256"), str)
            and existing.get("sha256")
        ):
            sha = existing["sha256"]
        if not sha:
            sha = ri._sha256(target)
        payload["file"] = pdf_rel
        payload["size_bytes"] = size
        payload["sha256"] = sha
    return _ordered(payload)


def build_plan(
    items: List[Dict[str, Any]],
    refs_dir: Path,
    storage_dir: Path,
    *,
    link_pdfs: bool,
    include_without_pdf: bool,
    limit: Optional[int],
) -> Dict[str, Any]:
    """计算"期望落盘状态"，导出与 `--check` 共用。"""
    bib = sorted(zc.bibliographic_items(items), key=_item_key)
    total_bib = len(bib)
    considered = bib[:limit] if (limit is not None and limit >= 0) else bib

    children = zc.pdf_children(items)
    # 冲突消歧用全量，保证 `--limit` 不影响 paper_id 的稳定性。
    paper_ids = assign_paper_ids(bib)

    papers_dir = refs_dir / SIDECAR_DIRNAME
    entries: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for item in considered:
        key = _item_key(item)
        paper_id = paper_ids.get(key) or safe_paper_id(key) or "item"
        sidecar_path = papers_dir / f"{paper_id}.json"
        existing = _load_sidecar(sidecar_path)

        pdf_rel: Optional[str] = None
        target: Optional[Path] = None
        if link_pdfs:
            _att, target = _pick_pdf(key, children, storage_dir)
            if target is not None:
                pdf_rel = f"{SIDECAR_DIRNAME}/{paper_id}.pdf"
            elif not include_without_pdf:
                skipped.append({
                    "zotero_key": key,
                    "paper_id": paper_id,
                    "reason": "Zotero 中无可用 PDF 实体文件",
                })
                continue

        payload = _desired_payload(item, paper_id, pdf_rel, target, existing)
        entries.append({
            "zotero_key": key,
            "paper_id": paper_id,
            "item": item,
            "sidecar_path": sidecar_path,
            "existing": existing,
            "payload": payload,
            "bytes": _serialize(payload).encode("utf-8"),
            "pdf_rel": pdf_rel,
            "pdf_target": target,
        })

    return {
        "bibliographic_total": total_bib,
        "considered": len(considered),
        "entries": entries,
        "skipped": skipped,
        "paper_ids": paper_ids,
    }


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------

def _ensure_symlink(link_path: Path, target: Path) -> str:
    """把 `<paper_id>.pdf` 指向真实文件。返回 created/updated/kept/skipped。"""
    if link_path.is_symlink():
        try:
            if Path(os.readlink(link_path)) == target:
                return "kept"
        except OSError:
            pass
        link_path.unlink()
        link_path.symlink_to(target)
        return "updated"
    if link_path.exists():
        # 已经是一份真实 PDF（用户自己下载的），不覆盖。
        return "skipped"
    link_path.symlink_to(target)
    return "created"


def export(
    plan: Dict[str, Any],
    refs_dir: Path,
    storage_dir: Path,
    *,
    link_pdfs: bool,
    dry_run: bool,
    log,
) -> Dict[str, Any]:
    """把计划落盘；返回统计。`dry_run=True` 时只记动作。"""
    papers_dir = refs_dir / SIDECAR_DIRNAME
    created = updated = unchanged = 0
    linked = kept_links = skipped_links = 0
    missing_targets: List[str] = []

    for entry in plan["entries"]:
        sidecar_path: Path = entry["sidecar_path"]
        rel = sidecar_path.name
        if entry["existing"] is None:
            action = "create"
            created += 1
        else:
            try:
                current = sidecar_path.read_bytes()
            except OSError:
                current = None
            if current == entry["bytes"]:
                action = "unchanged"
                unchanged += 1
            else:
                action = "update"
                updated += 1

        link_action = None
        if link_pdfs and entry["pdf_rel"]:
            link_path = refs_dir / entry["pdf_rel"]
            target: Optional[Path] = entry["pdf_target"]
            if target is None or not target.is_file():
                # 理论上到不了这里（计划阶段已校验存在），保底再查一次。
                missing_targets.append(entry["pdf_rel"])
                link_action = "missing"
            elif link_path.is_symlink() and _read_link(link_path) == target:
                link_action = "kept"
                kept_links += 1
            else:
                link_action = "link"
                linked += 1

        if dry_run:
            if action != "unchanged":
                log(f"[dry-run] 将{'创建' if action == 'create' else '更新'} sidecar：{rel}")
            if link_action == "link":
                log(f"[dry-run] 将建立软链：{entry['pdf_rel']} -> {entry['pdf_target']}")
            continue

        if action != "unchanged":
            papers_dir.mkdir(parents=True, exist_ok=True)
            sidecar_path.write_bytes(entry["bytes"])

        if link_action == "link":
            papers_dir.mkdir(parents=True, exist_ok=True)
            outcome = _ensure_symlink(link_path, target)  # type: ignore[arg-type]
            if outcome == "skipped":
                skipped_links += 1
                log(f"[warn] {entry['pdf_rel']} 已是真实文件，未覆盖为软链")
            elif outcome == "kept":
                kept_links += 1
            else:
                log(f"[link] {entry['pdf_rel']} -> {target}")

    stats: Dict[str, Any] = {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "linked": linked,
        "kept_links": kept_links,
        "skipped_links": skipped_links,
        "missing_targets": missing_targets,
    }

    if link_pdfs:
        if dry_run:
            log("[dry-run] 将依据磁盘上的 PDF 重建 index.json")
            stats["index_written"] = False
            stats["index_count"] = None
        else:
            refs_dir.mkdir(parents=True, exist_ok=True)
            index = ri.build_index(refs_dir, with_hash=True)
            (refs_dir / ri.INDEX_NAME).write_text(
                json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
            )
            stats["index_written"] = True
            stats["index_count"] = index["count"]
            log(f"[ok] 已重建 {ri.INDEX_NAME}（{index['count']} 条 PDF）")
    else:
        stats["index_written"] = False
        stats["index_count"] = None

    return stats


def _read_link(path: Path) -> Optional[Path]:
    try:
        raw = os.readlink(path)
    except OSError:
        return None
    link = Path(raw)
    return link if link.is_absolute() else (path.parent / link).resolve()


# ---------------------------------------------------------------------------
# 检查
# ---------------------------------------------------------------------------

def run_check(
    plan: Dict[str, Any],
    refs_dir: Path,
    *,
    link_pdfs: bool,
    log,
) -> List[str]:
    """比对 Zotero 与已导出 sidecar；返回问题列表（空 = 一致）。"""
    problems: List[str] = []
    entries = plan["entries"]
    desired_by_key: Dict[str, str] = dict(plan["paper_ids"])

    for entry in entries:
        rel = entry["sidecar_path"].relative_to(refs_dir).as_posix()
        if entry["existing"] is None:
            problems.append(f"缺少 sidecar：{rel}")
            continue
        try:
            current = entry["sidecar_path"].read_bytes()
        except OSError as exc:
            problems.append(f"sidecar 不可读：{rel}（{exc}）")
            continue
        if current != entry["bytes"]:
            problems.append(f"sidecar 与 Zotero 不一致：{rel}")

    # 孤儿 / paper_id 漂移：只看本脚本产出的 sidecar（带 zotero_key）。
    papers_dir = refs_dir / SIDECAR_DIRNAME
    if papers_dir.is_dir():
        planned_paths = {entry["sidecar_path"] for entry in entries}
        for path in sorted(papers_dir.glob("*.json")):
            if path in planned_paths:
                continue
            data = _load_sidecar(path)
            if not data or not data.get("zotero_key"):
                continue  # 非本脚本产出，不判孤儿
            key = str(data["zotero_key"])
            if key not in desired_by_key:
                problems.append(
                    f"孤儿 sidecar（Zotero 中已无此条目）："
                    f"{path.relative_to(refs_dir).as_posix()}"
                )
            elif data.get("paper_id") != desired_by_key[key]:
                problems.append(
                    f"paper_id 已漂移：{path.relative_to(refs_dir).as_posix()} "
                    f"应为 {desired_by_key[key]}"
                )

    if link_pdfs:
        index_path = refs_dir / ri.INDEX_NAME
        if not index_path.is_file():
            problems.append(f"缺少索引文件：{ri.INDEX_NAME}（--link-pdfs 模式必需）")
        else:
            try:
                index = json.loads(index_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                problems.append(f"索引无法解析：{exc}")
            else:
                problems.extend(ri.check_index(refs_dir, index))
    return problems


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    """参数错误退出码必须是 1，不能与"漂移(3)"混淆。"""

    def error(self, message: str):  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="zotero_refs.py",
        description="把本地 Zotero 库导出成 docs/refs/ sidecar（可选软链 PDF 并重建索引）",
    )
    parser.add_argument("--zotero-url", default=DEFAULT_ZOTERO_URL,
                        help=f"Zotero 本地 API（默认 {zc.DEFAULT_LOCAL_API}）")
    parser.add_argument("--zotero-storage", default=DEFAULT_STORAGE_DIR,
                        help=f"Zotero storage 根目录（默认 {DEFAULT_STORAGE_DIR}）")
    parser.add_argument("--refs-dir", default=DEFAULT_REFS_DIR,
                        help=f"参考文献库根目录（默认 {DEFAULT_REFS_DIR}）")
    parser.add_argument("--link-pdfs", action="store_true",
                        help="额外建立 PDF 软链并重建 index.json（默认只写元数据）")
    parser.add_argument("--include-without-pdf", action="store_true",
                        help="--link-pdfs 下也为无 PDF 条目写 sidecar（不进索引）")
    parser.add_argument("--limit", type=int, default=None, metavar="N",
                        help="只处理前 N 条可引用条目")
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印将要发生的变更，不写任何文件")
    parser.add_argument("--check", action="store_true",
                        help="只检查 Zotero 与 sidecar 的漂移，不写入；有漂移退出码 3")
    parser.add_argument("--json", action="store_true", help="输出机器可读摘要")
    parser.add_argument("--quiet", action="store_true", help="不输出过程日志")
    return parser


def _summary_base(args, refs_dir: Path, storage_dir: Path) -> Dict[str, Any]:
    return {
        "zotero_url": args.zotero_url or zc.DEFAULT_LOCAL_API,
        "refs_dir": str(refs_dir),
        "storage_dir": str(storage_dir),
        "mode": "metadata",
        "dry_run": bool(args.dry_run),
        "check": bool(args.check),
        "limit": args.limit,
    }


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    log = _noop_log if args.quiet else _log_stderr

    refs_dir = Path(args.refs_dir).expanduser().resolve()
    storage_dir = Path(args.zotero_storage).expanduser().resolve()
    summary = _summary_base(args, refs_dir, storage_dir)

    if args.limit is not None and args.limit < 0:
        log(f"[error] --limit 不能为负数：{args.limit}")
        return EXIT_ERROR

    # ---- 可达性：不可达必须"清晰报错 + 非零退出"，绝不 traceback ----
    server_id = zc.probe(args.zotero_url)
    if not server_id:
        endpoint = args.zotero_url or zc.DEFAULT_LOCAL_API
        log(f"[error] Zotero 本地 API 不可达：{endpoint}")
        log("[error] 请确认 Zotero 桌面端正在运行，或用 --zotero-url 指定地址。"
            "本脚本不复制 PDF、只读取元数据。")
        summary["exit"] = EXIT_ENV
        summary["error"] = "zotero_unreachable"
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        return EXIT_ENV

    try:
        items = zc.fetch_items(args.zotero_url)
    except zc.ZoteroUnavailable as exc:
        log(f"[error] 拉取 Zotero 条目失败：{exc}")
        summary["exit"] = EXIT_ENV
        summary["error"] = "zotero_fetch_failed"
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        return EXIT_ENV

    summary["server_id"] = server_id
    summary["items_total"] = len(items)

    try:
        plan = build_plan(
            items, refs_dir, storage_dir,
            link_pdfs=args.link_pdfs,
            include_without_pdf=args.include_without_pdf,
            limit=args.limit,
        )
    except OSError as exc:
        log(f"[error] 规划失败：{exc}")
        summary["exit"] = EXIT_ERROR
        summary["error"] = f"plan_failed: {exc}"
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        return EXIT_ERROR

    summary["bibliographic_total"] = plan["bibliographic_total"]
    summary["considered"] = plan["considered"]
    summary["without_pdf"] = len(plan["skipped"])

    # ---- 检查模式 ----
    if args.check:
        problems = run_check(plan, refs_dir, link_pdfs=args.link_pdfs, log=log)
        summary["mode"] = "check"
        summary["drift"] = problems
        if problems:
            for line in problems:
                log(f"[stale] {line}")
            log(f"[stale] 共 {len(problems)} 处漂移；"
                f"请运行：python3 zotero_refs.py --refs-dir {refs_dir}"
                + (" --link-pdfs" if args.link_pdfs else ""))
            summary["exit"] = EXIT_STALE
            if args.json:
                print(json.dumps(summary, ensure_ascii=False, indent=2))
            return EXIT_STALE
        log(f"[ok] {plan['considered']} 条 sidecar 与 Zotero 一致")
        summary["exit"] = EXIT_OK
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        return EXIT_OK

    # ---- 导出模式 ----
    summary["mode"] = "link-pdfs" if args.link_pdfs else "metadata"
    try:
        stats = export(
            plan, refs_dir, storage_dir,
            link_pdfs=args.link_pdfs, dry_run=args.dry_run, log=log,
        )
    except OSError as exc:
        log(f"[error] 写入失败：{exc}")
        summary["exit"] = EXIT_ERROR
        summary["error"] = f"write_failed: {exc}"
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        return EXIT_ERROR

    summary.update(stats)
    if args.dry_run:
        log(f"[dry-run] 可引用 {plan['bibliographic_total']} 条，"
            f"本次考察 {plan['considered']} 条："
            f"新建 {stats['created']}，更新 {stats['updated']}，"
            f"不变 {stats['unchanged']}，无 PDF 跳过 {len(plan['skipped'])}")
        if args.link_pdfs:
            log(f"[dry-run] 将建立 {stats['linked']} 个 PDF 软链")
    else:
        log(f"[ok] sidecar：新建 {stats['created']}，更新 {stats['updated']}，"
            f"不变 {stats['unchanged']}；输出目录 {refs_dir / SIDECAR_DIRNAME}")
        if plan["skipped"]:
            log(f"[warn] {len(plan['skipped'])} 条因无 PDF 实体文件被跳过"
                f"（加 --include-without-pdf 可只导出元数据）")
        if not args.link_pdfs:
            log("[ok] 元数据模式：未改动 index.json（无 PDF 即无索引义务）")

    summary["exit"] = EXIT_OK
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
