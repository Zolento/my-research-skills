#!/usr/bin/env python3
"""Zotero 原生全文检索 + 附件访问 + PDF 页级抽取 + 缓存（P3 + P5）。

本模块对应 `references/zotero-local-api.md` §3.1 的全文与附件端点约定，
只读、仅标准库 + 既有 `pypdf`，不引入向量数据库或新依赖。

三条不可违反的纪律
------------------

1. **索引命中不是页码证据。**
   `GET /items/{key}/fulltext` 的 `content` 是**扁平文本，没有页码边界**
   （实测只有 `content` / `indexedPages` / `totalPages`）。因此索引命中一律标
   `indexed_fulltext`，**永远不得**升级为 `page_verified`，也**不得**给出页码。
   页码只能来自真实 PDF 解析（`extract_pages` / `search_pdf_pages`）。

2. **物理页 ≠ 印刷页码。**
   `extract_pages` 返回的 `page` 是 1 起算的**物理 PDF 页**；
   `printed_page` 是页面上**真实印出来的**页码标签，取不到就是 `None`。
   两者**不得**互相假设。pypdf 的 `reader.page_labels` 在 PDF 未定义
   `/PageLabels` 时会**伪造** `["1", "2", ...]`，本模块识别并拒绝这种默认值。

3. **绝不伪造文本。**
   抽不到就返回空串并标 `empty` / `scanned` / `low_text`；
   页码级命中只返回真实抽取文本的片段。

命中归并规则（硬要求 1）
------------------------

`qmode=everything` 会**同时**返回附件与其父条目。归并规则：

- 有 `data.parentItem` 的条目（附件 / 笔记 / 标注）归并到父条目 key，按 key 去重。
- 父条目也在结果里 → 用父条目元数据；父条目缺失 → 尝试 `get_item` 补取；
  仍取不到 → 用**不含任何编造字段**的占位记录（`parent_metadata_missing=True`）。
- **孤儿附件**（`itemType=attachment` 且**无** `parentItem`）作为独立条目保留，
  标 `orphan_attachment=True`，以附件 key 作为 `zotero_key`；
  既不静默丢弃，也不与父条目重复计数。

缓存（硬要求 6）
----------------

缓存身份 = **Server ID + Library ID + Item Key + Attachment Key + 内容指纹(sha256)**，
落盘路径 `<cache_root>/<server_id>/<library_id>/<item_key>/<attachment_key>/<sha256>.json`。
Server ID 变化 → 目录整体不命中（等价于整库缓存失效）；
PDF 内容变化 → 指纹变化 → 新文件、旧文本不再被读取。

缓存根目录默认 `.research-idea-pipeline/zotero-fulltext-cache/`，
该路径已在 `research-idea-pipeline/.gitignore` 中被忽略（`git check-ignore` 实测通过），
**绝不**把受版权保护的全文放进版本库。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zotero_client  # noqa: E402  （同目录模块，只读原语；本模块**不修改**它）

__all__ = [
    "PdfUnavailable",
    "LEVEL_METADATA",
    "LEVEL_ABSTRACT",
    "LEVEL_INDEXED",
    "LEVEL_PDF_TEXT",
    "LEVEL_PAGE",
    "LEVEL_INSUFFICIENT",
    "search_indexed",
    "attachment_fulltext",
    "resolve_attachment_path",
    "resolve_server_id",
    "extract_pages",
    "search_pdf_pages",
    "search_extracted_pages",
    "cache_path",
    "cache_get",
    "cache_put",
    "get_text_cache",
    "invalidate_by_fingerprint",
    "default_cache_root",
    "search_two_layer",
]

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

#: 验证级别（与 `zotero_deepread.VERIFICATION_LEVELS` 命名一致；本模块只负责前三档与降级）。
#: `INDEXED` 来自扁平索引；`PAGE` 只能由真实 PDF 页解析产生。
LEVEL_METADATA = "metadata_only"
LEVEL_ABSTRACT = "abstract_only"
LEVEL_INDEXED = "indexed_fulltext"
LEVEL_PDF_TEXT = "pdf_text_verified"
LEVEL_PAGE = "page_verified"
LEVEL_INSUFFICIENT = "insufficient_evidence"

#: 个人库 ID（Local API 路径 `/users/0`）。
DEFAULT_LIBRARY_ID = "0"

#: 缓存根目录环境变量（覆盖默认位置，便于测试与多实例隔离）。
CACHE_ROOT_ENV = "RESEARCH_ZOTERO_FULLTEXT_CACHE"
#: Zotero storage 目录环境变量（回退路径用，兼容非默认安装）。
STORAGE_DIR_ENV = "ZOTERO_STORAGE_DIR"
#: 链接附件基准目录环境变量（`linked_file` 的相对路径回退）。
LINKED_BASE_ENV = "ZOTERO_LINKED_ATTACHMENT_BASE"

#: 缓存记录版本；结构变化时递增，旧记录自然失效。
CACHE_VERSION = 1

#: 单页有效文本的下限（去空白后字符数）。低于此值标 `low_text`。
LOW_TEXT_CHARS = 100

#: 两栏阅读顺序启发式阈值。
TWO_COLUMN_MIN_FRAGMENTS = 6      # 少于 6 个文本片段不判断
TWO_COLUMN_MIN_SPAN_RATIO = 0.25  # 片段 x 跨度小于页宽 25% 视为单栏
TWO_COLUMN_GAP_RATIO = 0.15       # 两簇之间空隙小于页宽 15% 不视为分栏
TWO_COLUMN_ALTERNATION = 0.5      # 相邻片段跨簇跳变比例 >= 阈值 ⇒ 疑似阅读顺序错乱

#: 页码标签最多接受的字符数（避免把整行正文当页码）。
_PRINTED_LABEL_MAX_LEN = 24

_PAGE_ONLY_RE = re.compile(r"^[\-–—(\[]*\s*(\d{1,4})\s*[\-–—)\]]*$")
_PAGE_PREFIX_RE = re.compile(r"^(?:page|p|pp)\.?\s*[\-–—]?\s*(\d{1,4})$", re.IGNORECASE)
_PAGE_OF_RE = re.compile(r"^(\d{1,4})\s*(?:/|of)\s*(\d{1,4})$")
_WS_RE = re.compile(r"\s+")

_ROMAN_LABELS = frozenset(
    "i ii iii iv v vi vii viii ix x xi xii xiii xiv xv xvi xvii xviii xix xx "
    "xxi xxii xxiii xxiv xxv xxvi xxvii xxviii xxix xxx".split()
)


class PdfUnavailable(RuntimeError):
    """PDF 不存在 / 无法解析 / 无读取权限。

    调用方（例如 `search_two_layer`）**必须**捕获它并降级该条目的证据级别，
    不得让整批检索失败。
    """


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------

def _clean(value: Any) -> Optional[str]:
    """去空白；空串与 None 归一为 None。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _kw(base_url: Optional[str]) -> Dict[str, str]:
    """仅在显式给出 `base_url` 时才作为关键字参数透传。"""
    return {"base_url": base_url} if base_url else {}


def _client_fn(client: Any, name: str):
    """取 client 上的只读方法。

    `client is None` → 用 `zotero_client` 模块的对应函数（真实本地 API）。
    显式传入 client 时**只**用 client 自己的方法：缺方法就返回 None，
    绝不偷偷回落到真实网络（测试与隔离都依赖这一点）。
    """
    if client is None:
        return getattr(zotero_client, name, None)
    fn = getattr(client, name, None)
    return fn if callable(fn) else None


def _int_or_none(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _sha256_file(path: Path, *, chunk: int = 1 << 20) -> Optional[str]:
    """文件内容指纹（sha256）；读取失败返回 None（不抛异常）。"""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            while True:
                block = fh.read(chunk)
                if not block:
                    break
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


def _file_url_to_path(url: Optional[str]) -> Optional[str]:
    """`file://` URL → 本地路径；**任何非 file 协议一律拒绝**（不发起网络请求）。"""
    if not url or not isinstance(url, str):
        return None
    if not url.startswith("file://"):
        return None
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "file":
        return None
    try:
        return urllib.request.url2pathname(parsed.path)
    except (ValueError, OSError):
        return None


# ---------------------------------------------------------------------------
# 分词 / 年份过滤：与 literature_search 保持兼容
# ---------------------------------------------------------------------------

_LS_MODULE: Any = None
_LS_TRIED = False

#: literature_search.tokenize 的等价回落（lazy import 失败时使用）。
_FALLBACK_LATIN_RE = re.compile(r"[a-z0-9][a-z0-9\-]+", re.IGNORECASE)
_FALLBACK_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
_FALLBACK_STOPWORDS = frozenset({
    "the", "a", "an", "of", "for", "and", "or", "to", "in", "on", "with",
    "via", "using", "use", "from", "by", "is", "are", "be", "as", "at",
    "we", "our", "this", "that", "these", "those", "it", "its",
})


def _literature_search():
    """惰性导入 `literature_search` 以复用其分词与年份语义。

    顶层**不能**导入：Lead 会在 `literature_search` 里接线本模块，顶层互导会成环。
    导入失败时返回 None，由本模块的等价回落兜底。
    """
    global _LS_MODULE, _LS_TRIED
    if not _LS_TRIED:
        _LS_TRIED = True
        try:
            import literature_search as _ls  # noqa: PLC0415
            _LS_MODULE = _ls
        except Exception:  # noqa: BLE001 —— 缺依赖也必须能跑本地抽取
            _LS_MODULE = None
    return _LS_MODULE


def _fallback_tokenize(text: str) -> List[str]:
    if not text:
        return []
    low = text.lower()
    latin = [t for t in _FALLBACK_LATIN_RE.findall(low) if t not in _FALLBACK_STOPWORDS]
    cjk: List[str] = []
    for run in _FALLBACK_CJK_RE.findall(low):
        cjk.append(run)
        if len(run) > 2:
            cjk.extend(run[i:i + 2] for i in range(len(run) - 1))
    return latin + cjk


def _tokenize(text: str) -> List[str]:
    """与 `literature_search.tokenize` 一致的分词；不可用时用等价回落。"""
    module = _literature_search()
    if module is not None and hasattr(module, "tokenize"):
        return list(module.tokenize(text))
    return _fallback_tokenize(text)


def _coerce_year(value: Any) -> Optional[int]:
    """2019 / \"2019\" / \"2019-05\" → int；无法解析返回 None（与 literature_search 一致）。"""
    module = _literature_search()
    if module is not None and hasattr(module, "_coerce_year"):
        return module._coerce_year(value)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        match = re.search(r"(?:19|20)\d{2}", value)
        return int(match.group(0)) if match else None
    return None


def _in_year_range(
    year: Optional[int], from_year: Optional[int], to_year: Optional[int],
) -> bool:
    """年份过滤。

    ⚠️ 启用过滤时，**年份未知的条目一律排除**（与 `literature_search._in_year_range`
    完全一致）：否则过滤会被静默跳过，用户以为筛了年份其实没筛。
    """
    module = _literature_search()
    if module is not None and hasattr(module, "_in_year_range"):
        return module._in_year_range(year, from_year, to_year)
    if from_year is None and to_year is None:
        return True
    if year is None:
        return False
    if from_year is not None and year < from_year:
        return False
    if to_year is not None and year > to_year:
        return False
    return True


def _keywords_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value if v)
    return ""


# ---------------------------------------------------------------------------
# 第 1 层：Zotero 原生索引检索 + 按 parentItem 归并
# ---------------------------------------------------------------------------

def attachment_fulltext(
    client: Any, attachment_key: str, *, base_url: Optional[str] = None,
) -> Optional[dict]:
    """`GET /items/{attachmentKey}/fulltext` → 规范化后的索引信息。

    返回 `{content, indexedPages, totalPages, indexed, partial, chars}`；
    附件未建索引、key 为空或任何读取失败 → None（**不抛异常**，单条降级）。

    ⚠️ `content` 没有页码边界：调用方只能把它当检索资料，**不得**据此声称页码证据。
    """
    if not attachment_key:
        return None
    fn = _client_fn(client, "item_fulltext")
    if fn is None:
        return None
    try:
        payload = fn(attachment_key, **_kw(base_url))
    except Exception:  # noqa: BLE001 —— 单个附件失败不能拖垮整批
        return None
    if not isinstance(payload, dict):
        return None

    content = payload.get("content")
    content = str(content) if content is not None else ""
    indexed_pages = _int_or_none(payload.get("indexedPages"))
    total_pages = _int_or_none(payload.get("totalPages"))
    return {
        "content": content,
        "indexedPages": indexed_pages,
        "totalPages": total_pages,
        "indexed": bool(content.strip()) or bool(indexed_pages),
        "partial": (indexed_pages is not None and total_pages is not None
                    and indexed_pages != total_pages),
        "chars": len(content),
    }


def _partial_index(fulltext: Optional[dict]) -> bool:
    if not fulltext:
        return False
    indexed_pages = fulltext.get("indexedPages")
    total_pages = fulltext.get("totalPages")
    return indexed_pages is not None and total_pages is not None and indexed_pages != total_pages


def _child_stub_record(item: dict) -> dict:
    """孤儿附件 / 独立笔记的占位记录：只带真实存在的字段，绝不编造标题或年份。"""
    data = item.get("data") or {}
    item_type = data.get("itemType")
    key = item.get("key")
    title = _clean(data.get("title"))
    title_source = "title"
    if not title:
        title = _clean(data.get("filename"))
        title_source = "filename" if title else None
    record: Dict[str, Any] = {
        "title": title,
        "authors": [],
        "abstract": _clean(data.get("abstractNote")),
        "year": _coerce_year(data.get("date")),
        "venue": None,
        "url": _clean(data.get("url")),
        "doi": zotero_client.normalize_doi(data.get("DOI")),
        "arxiv_id": zotero_client.arxiv_id(data),
        "keywords": [],
        "sources": ["local"],
        "zotero_key": key,
        "paper_id": key,
        "title_source": title_source,
        "item_type": item_type,
    }
    if item_type == "attachment":
        record["orphan_attachment"] = True
        record["link_mode"] = data.get("linkMode")
        record["content_type"] = data.get("contentType")
    else:
        record["orphan_child"] = True
    return record


def _stub_record(paper_key: str) -> dict:
    """父条目元数据取不到时的占位记录：字段全部为 None，绝不编造。"""
    return {
        "title": None,
        "authors": [],
        "abstract": None,
        "year": None,
        "venue": None,
        "url": None,
        "doi": None,
        "arxiv_id": None,
        "keywords": [],
        "sources": ["local"],
        "zotero_key": paper_key,
        "paper_id": paper_key,
    }


def _fetch_parent(client: Any, parent_key: str, base_url: Optional[str]) -> Optional[dict]:
    fn = _client_fn(client, "get_item")
    if fn is None:
        return None
    try:
        item = fn(parent_key, **_kw(base_url))
    except Exception:  # noqa: BLE001
        return None
    if isinstance(item, dict) and isinstance(item.get("data"), dict):
        return item
    return None


def _score_record(
    record: dict, index_text: str, query: str, q_tokens: set,
) -> Tuple[float, set]:
    """字段权重与 `literature_search.search_local` 完全一致：

    标题 3.0 > 关键词 2.5 > 摘要 1.5 > 全文 1.0；短语整体命中额外 +5.0。
    """
    score = 0.0
    matched: set = set()
    weighted_fields = [
        (record.get("title") or "", 3.0),
        (_keywords_text(record.get("keywords")), 2.5),
        (record.get("abstract") or "", 1.5),
        (index_text or "", 1.0),
    ]
    for text, weight in weighted_fields:
        overlap = q_tokens & set(_tokenize(str(text)))
        if overlap:
            matched |= overlap
            score += weight * len(overlap)

    haystack = " ".join([
        str(record.get("title") or ""), str(record.get("abstract") or ""), index_text or "",
    ]).lower()
    if query.strip().lower() in haystack:
        score += 5.0
    return score, matched


def _merge_index_hits(
    client: Any,
    raw_items: Sequence[dict],
    query: str,
    *,
    limit: int,
    from_year: Optional[int],
    to_year: Optional[int],
    base_url: Optional[str],
    include_index_text: bool,
) -> List[dict]:
    """把 `qmode=everything` 的原始命中归并回论文条目并去重。

    归并键是**父条目 key**：附件与父条目命中同一个 key → 只产出一条记录。
    孤儿附件（无 `parentItem`）以自身 key 独立成条，标 `orphan_attachment=True`。
    """
    by_key: Dict[str, dict] = {}
    for item in raw_items:
        if isinstance(item, dict) and item.get("key"):
            by_key[item["key"]] = item

    groups: Dict[str, Dict[str, Any]] = {}
    for key, item in by_key.items():
        data = item.get("data") or {}
        parent = _clean(data.get("parentItem"))
        if parent:
            group = groups.setdefault(parent, {"parent": None, "children": []})
            group["children"].append(item)
        else:
            group = groups.setdefault(key, {"parent": None, "children": []})
            group["parent"] = item

    q_tokens = set(_tokenize(query))
    out: List[dict] = []
    for paper_key, group in groups.items():
        parent_item = group["parent"]
        child_items: List[dict] = group["children"]

        if parent_item is not None:
            parent_type = (parent_item.get("data") or {}).get("itemType")
            if parent_type in ("attachment", "note", "annotation"):
                # 孤儿附件 / 独立笔记：不是可引用论文，但只要被检索命中就不能丢。
                record = _child_stub_record(parent_item)
            else:
                record = zotero_client.item_to_record(parent_item)
        else:
            fetched = _fetch_parent(client, paper_key, base_url)
            if fetched is not None:
                record = zotero_client.item_to_record(fetched)
            else:
                record = _stub_record(paper_key)
                record["parent_metadata_missing"] = True

        record["zotero_key"] = paper_key
        if not record.get("paper_id"):
            record["paper_id"] = paper_key
        record["source"] = "local"
        record.setdefault("sources", ["local"])

        # 附件候选：子条目里的 attachment + 孤儿附件自身
        attachment_items: List[dict] = []
        if (isinstance(parent_item, dict)
                and (parent_item.get("data") or {}).get("itemType") == "attachment"):
            attachment_items.append(parent_item)
        for child in child_items:
            if (child.get("data") or {}).get("itemType") == "attachment":
                attachment_items.append(child)

        seen_att: set = set()
        attachments: List[dict] = []
        index_parts: List[str] = []
        for att in attachment_items:
            data = att.get("data") or {}
            att_key = att.get("key")
            if not att_key or att_key in seen_att:
                continue
            seen_att.add(att_key)
            fulltext = attachment_fulltext(client, att_key, base_url=base_url) \
                if include_index_text else None
            indexed = bool(fulltext and fulltext.get("indexed"))
            attachments.append({
                "attachment_key": att_key,
                "item_key": paper_key,
                "filename": _clean(data.get("filename")),
                "title": _clean(data.get("title")),
                "content_type": _clean(data.get("contentType")),
                "link_mode": _clean(data.get("linkMode")),
                # resolve_attachment_path 读取的是 Zotero 原始字段名，这里保留一份。
                "linkMode": _clean(data.get("linkMode")),
                "path": _clean(data.get("path")),
                "indexed": indexed,
                "indexed_pages": (fulltext or {}).get("indexedPages"),
                "total_pages": (fulltext or {}).get("totalPages"),
                "partial_index": _partial_index(fulltext),
                "index_chars": (fulltext or {}).get("chars", 0),
            })
            if indexed:
                index_parts.append(fulltext["content"])
        record["attachments"] = attachments
        index_text = "\n".join(index_parts)

        record["year"] = _coerce_year(record.get("year"))
        if not _in_year_range(record["year"], from_year, to_year):
            continue

        score, matched = _score_record(record, index_text, query, q_tokens)
        if score == 0.0:
            # 命中来自 Zotero 索引（可能用了词干/字段索引），本模块分词未重合也**不丢**。
            record["matched_via"] = "zotero_index"
        record["_score"] = round(score, 3)
        record["matched_terms"] = sorted(matched)

        has_index = any(a["indexed"] for a in attachments)
        record["verification"] = (
            LEVEL_INDEXED if has_index
            else (LEVEL_ABSTRACT if record.get("abstract") else LEVEL_METADATA)
        )
        out.append(record)

    out.sort(key=lambda rec: (-rec.get("_score", 0.0), str(rec.get("zotero_key"))))
    if limit is not None and limit >= 0:
        out = out[:limit]
    return [{k: v for k, v in rec.items() if not k.startswith("_") or k == "_score"}
            for rec in out]


def search_indexed(
    client: Any,
    query: str,
    *,
    limit: int = 50,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    base_url: Optional[str] = None,
    include_index_text: bool = True,
) -> List[dict]:
    """Zotero 原生索引检索（`qmode=everything`），归并回论文并去重。

    返回的记录与 `literature_search.search_local` 形状兼容：
    含 `source="local"`、`_score`、`matched_terms`，并额外携带
    `attachments`（含索引状态）与 `verification`（索引命中固定为 `indexed_fulltext`）。

    Raises:
        RuntimeError: client 未提供 `search_items`。
        zotero_client.ZoteroUnavailable: 交由调用方决定是否回落 refs。
    """
    fn = _client_fn(client, "search_items")
    if fn is None:
        raise RuntimeError("client 未提供 search_items，无法执行 Zotero 索引检索")
    raw = fn(query, qmode="everything", **_kw(base_url))
    if not isinstance(raw, list):
        raw = []
    return _merge_index_hits(
        client, raw, query,
        limit=limit, from_year=from_year, to_year=to_year,
        base_url=base_url, include_index_text=include_index_text,
    )


# ---------------------------------------------------------------------------
# 附件本地路径解析（只读；绝不移动/重命名/删除；绝不跟随非 file:// URL）
# ---------------------------------------------------------------------------

def resolve_attachment_path(
    client: Any,
    attachment: dict,
    *,
    storage_dir: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Optional[str]:
    """解析附件的本地文件路径。

    顺序：

    1. Local API `file/view/url`（**优先** —— 用户可能用第三方云盘，
       PDF 不一定在 `~/Zotero/storage/`）。只接受 `file://`。
    2. `linked_file` 的绝对 `path`（及可选 `ZOTERO_LINKED_ATTACHMENT_BASE` 相对路径）。
    3. `storage/<attachmentKey>/<filename>` 回退（`imported_file` / `imported_url`）。

    `linked_url` / 网页附件**返回 None**，绝不发起网络请求。
    任何权限错误、路径穿越、文件缺失都返回 None。**不移动、不重命名、不删除文件。**
    """
    data = attachment.get("data") if isinstance(attachment.get("data"), dict) else {}
    key = _clean(attachment.get("key")) or _clean(data.get("key"))
    link_mode = _clean(data.get("linkMode"))

    # 1) Local API file/view/url（优先）
    fn = _client_fn(client, "file_view_url")
    if key and fn is not None:
        url = None
        try:
            url = fn(key, **_kw(base_url))
        except Exception:  # noqa: BLE001
            url = None
        path = _file_url_to_path(url)
        if path:
            try:
                if os.path.isfile(path):
                    return path
            except OSError:
                pass

    # 2) linked_file 显式路径（linked_url 绝不联网、绝不当作本地文件）
    if link_mode == "linked_file":
        raw_path = _clean(data.get("path"))
        if raw_path:
            candidate = Path(raw_path).expanduser()
            try:
                if candidate.is_absolute():
                    if candidate.is_file():
                        return str(candidate)
                else:
                    base = _clean(os.environ.get(LINKED_BASE_ENV))
                    if base:
                        joined = (Path(base).expanduser() / raw_path)
                        if joined.is_file():
                            return str(joined)
            except OSError:
                pass
        return None
    if link_mode == "linked_url":
        return None

    # 3) storage/<key>/<filename> 回退
    filename = _clean(data.get("filename"))
    if key and filename:
        root_value = storage_dir or os.environ.get(STORAGE_DIR_ENV)
        root = Path(root_value).expanduser() if root_value else (Path.home() / "Zotero" / "storage")
        att_dir = root / key
        candidate = att_dir / filename
        try:
            # 防路径穿越：filename 不得逃出 <root>/<key>/
            candidate.resolve().relative_to(att_dir.resolve())
        except (ValueError, OSError):
            return None
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            return None
    return None


# ---------------------------------------------------------------------------
# 第 2 层：PDF 页级抽取
# ---------------------------------------------------------------------------

def _extract_page_text(page: Any) -> Tuple[str, List[float]]:
    """抽取单页文本，并顺带收集每个文本片段的 x 坐标（用于分栏启发式）。

    用 `visitor_operand_before` 在 `Tj/TJ/'/"` 操作处取当前文本矩阵的 x：
    `visitor_text` 的 tm 在 pypdf 里是**整组文本的首个位置**，不足以判断分栏。
    """
    xs: List[float] = []

    def _before(operator: bytes, _operands: Any, _cm: Any, tm: Any) -> None:
        if operator in (b"Tj", b"TJ", b"'", b'"'):
            try:
                xs.append(float(tm[4]))
            except (TypeError, ValueError, IndexError):
                pass

    text = page.extract_text(visitor_operand_before=_before) or ""
    return text, xs


def _page_has_image(page: Any) -> bool:
    """页面是否含图像 XObject（用于区分「扫描件」与「空白页」）。"""
    try:
        images = getattr(page, "images", None)
        return bool(images)
    except Exception:  # noqa: BLE001 —— 损坏的 XObject 不影响文本抽取
        return False


def _column_signal(xs: Sequence[float], page: Any) -> Tuple[int, bool]:
    """启发式判断两栏与阅读顺序。

    返回 `(列数, 是否疑似阅读顺序错乱)`。只在证据充分时才报 2 栏：

    - 文本片段数 >= `TWO_COLUMN_MIN_FRAGMENTS`；
    - x 跨度 >= 页宽的 25%；
    - 以中点分成两簇，两簇各 >= 3 个片段且簇间空隙 >= 页宽的 15%；
    - 片段序列在两簇间跳变比例 >= `TWO_COLUMN_ALTERNATION` ⇒ 阅读顺序可疑
      （按栏连续输出则跳变很少，阅读顺序正常）。
    """
    if len(xs) < TWO_COLUMN_MIN_FRAGMENTS:
        return 1, False
    try:
        width = float(page.mediabox.width)
    except Exception:  # noqa: BLE001
        width = 612.0
    if width <= 0:
        width = 612.0

    lo, hi = min(xs), max(xs)
    if (hi - lo) < width * TWO_COLUMN_MIN_SPAN_RATIO:
        return 1, False

    mid = (lo + hi) / 2.0
    left = [x for x in xs if x < mid]
    right = [x for x in xs if x >= mid]
    if len(left) < 3 or len(right) < 3:
        return 1, False
    if (min(right) - max(left)) < width * TWO_COLUMN_GAP_RATIO:
        return 1, False

    labels = [0 if x < mid else 1 for x in xs]
    transitions = sum(1 for a, b in zip(labels, labels[1:]) if a != b)
    fraction = transitions / max(len(labels) - 1, 1)
    return 2, fraction >= TWO_COLUMN_ALTERNATION


def page_quality(text: str, *, has_image: bool = False, columns: int = 1,
                 interleaved: bool = False) -> Tuple[str, List[str]]:
    """页面质量判定（纯函数，便于单测）。

    - 无文本 + 有图像 → `scanned`（疑似扫描件，需 OCR，**绝不编造内容**）
    - 无文本 + 无图像 → `empty`
    - 疑似两栏阅读顺序错乱 → `two_column_order`
    - 去空白字符数 < `LOW_TEXT_CHARS` → `low_text`
    - 否则 `ok`
    """
    flags: List[str] = []
    stripped = (text or "").strip()
    if not stripped:
        quality = "scanned" if has_image else "empty"
        flags.append(quality)
        return quality, flags
    if interleaved:
        flags.append("two_column_order")
        return "two_column_order", flags
    if len(stripped) < LOW_TEXT_CHARS:
        flags.append("low_text")
        return "low_text", flags
    if columns >= 2:
        flags.append("two_column")
    return "ok", flags


def _explicit_page_labels(reader: Any, num_pages: int) -> Optional[List[str]]:
    """真实的 PDF `/PageLabels`；未定义时返回 None。

    ⚠️ pypdf 的 `reader.page_labels` 在未定义 `/PageLabels` 时会**伪造**
    `["1", "2", ...]`。把它当印刷页码就等于假设「物理页 == 印刷页」，
    正是本模块禁止的做法。因此只有标签**不等于**默认物理序列时才采用。
    """
    try:
        labels = [str(x) for x in reader.page_labels]
    except Exception:  # noqa: BLE001
        return None
    if len(labels) != num_pages:
        return None
    if labels == [str(i + 1) for i in range(num_pages)]:
        return None
    return labels


def _printed_page_token(line: str) -> Optional[str]:
    """从一行短文本中提取真实印出的页码标签；提取不到返回 None。"""
    text = line.strip()
    if not text or len(text) > _PRINTED_LABEL_MAX_LEN:
        return None
    match = _PAGE_PREFIX_RE.match(text)
    if match:
        return _reject_year(match.group(1))
    match = _PAGE_ONLY_RE.match(text)
    if match:
        return _reject_year(match.group(1))
    match = _PAGE_OF_RE.match(text)
    if match:
        return _reject_year(match.group(1))
    lowered = text.lower()
    if lowered in _ROMAN_LABELS:
        return lowered
    return None


def _reject_year(token: str) -> Optional[str]:
    """排除 1900—2099 的 4 位数：更可能是年份/编号而不是页码。"""
    if len(token) == 4 and token.isdigit() and 1900 <= int(token) <= 2099:
        return None
    return token


def _printed_page_from_text(text: str) -> Optional[str]:
    """best-effort：从页眉前 3 行 / 页脚后 5 行里找印刷页码标签。

    取不到就是 None —— **绝不**回落到物理页号冒充印刷页码。
    """
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return None
    for line in lines[:3] + lines[-5:]:
        token = _printed_page_token(line)
        if token:
            return token
    return None


def _safe_extract_page(page: Any) -> Tuple[str, List[float]]:
    try:
        return _extract_page_text(page)
    except Exception:  # noqa: BLE001 —— 单页失败降级为空文本，不中断整篇
        return "", []


def extract_pages(pdf_path: Any, *, sha256: bool = True) -> dict:
    """逐页抽取真实 PDF 文本。

    返回::

        {
          "path", "sha256", "num_pages", "text_chars",
          "quality": 整篇质量概览,
          "pages": [
            {"page": 1 起算物理页, "printed_page": 印刷页码或 None,
             "text", "char_offset", "chars", "quality", "flags", "columns"},
            ...
          ],
        }

    `char_offset` 是 `"\\n".join(page["text"])` 中的起始下标，
    满足 `concat[offset:offset+len(text)] == text`。

    Raises:
        FileNotFoundError: 文件不存在。
        PdfUnavailable: 文件不可读 / 不是可解析的 PDF / 加密无法解密。
    """
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF 不存在：{pdf_path}")
    fingerprint = _sha256_file(path) if sha256 else None

    try:
        import pypdf  # noqa: PLC0415 —— 仅在真正解析时导入
    except ImportError as exc:  # pragma: no cover
        raise PdfUnavailable(f"缺少 pypdf，无法解析 PDF：{exc}") from exc

    try:
        reader = pypdf.PdfReader(str(path))
        if getattr(reader, "is_encrypted", False):
            try:
                reader.decrypt("")
            except Exception:  # noqa: BLE001
                pass
        num_pages = len(reader.pages)
    except Exception as exc:  # noqa: BLE001
        raise PdfUnavailable(f"无法解析 PDF：{path}（{type(exc).__name__}: {exc}）") from exc

    label_map = _explicit_page_labels(reader, num_pages)
    pages: List[dict] = []
    offset = 0
    for index in range(num_pages):
        page = reader.pages[index]
        text, xs = _safe_extract_page(page)
        columns, interleaved = _column_signal(xs, page) if text.strip() else (1, False)
        quality, flags = page_quality(
            text, has_image=_page_has_image(page), columns=columns, interleaved=interleaved)
        printed_page = label_map[index] if label_map is not None else _printed_page_from_text(text)
        pages.append({
            "page": index + 1,
            "printed_page": printed_page,
            "text": text,
            "char_offset": offset,
            "chars": len(text.strip()),
            "quality": quality,
            "flags": flags,
            "columns": columns,
        })
        offset += len(text) + 1

    return {
        "path": str(path),
        "sha256": fingerprint,
        "num_pages": num_pages,
        "text_chars": sum(p["chars"] for p in pages),
        "quality": _overall_quality(pages),
        "pages": pages,
    }


def _overall_quality(pages: Sequence[dict]) -> str:
    """整篇质量概览：全部无文本 → empty；有 ok → ok；否则取最差档。"""
    if not pages:
        return "empty"
    qualities = [p.get("quality") for p in pages]
    if all(q in ("empty", "scanned") for q in qualities):
        return "empty"
    if "two_column_order" in qualities:
        return "two_column_order"
    if "low_text" in qualities and "ok" not in qualities:
        return "low_text"
    return "ok"


def _make_snippet(text: str, query: str, q_tokens: set, *, width: int = 200) -> str:
    """从真实文本里截取命中窗口（先规范化空白）；截不到就返回开头一段。"""
    normalized = _WS_RE.sub(" ", text or "").strip()
    if not normalized:
        return ""
    lowered = normalized.lower()
    start = lowered.find(query.strip().lower()) if query.strip() else -1
    if start < 0:
        for token in sorted(q_tokens):
            start = lowered.find(token)
            if start >= 0:
                break
    if start < 0:
        start = 0
    begin = max(0, start - width // 3)
    end = min(len(normalized), begin + width)
    snippet = normalized[begin:end]
    if begin > 0:
        snippet = "…" + snippet
    if end < len(normalized):
        snippet = snippet + "…"
    return snippet


def search_extracted_pages(
    extracted: dict,
    query: str,
    *,
    pages: Optional[Iterable[int]] = None,
) -> List[dict]:
    """在已抽取的页结果里做页级匹配（**页码只来自真实 PDF**）。

    `pages` 是 1 起算的物理页过滤集合。命中标 `verification="page_verified"`
    并带真实 `page` / `printed_page` / `snippet`。
    """
    q_tokens = set(_tokenize(query))
    if not q_tokens:
        return []

    page_filter: Optional[set] = None
    if pages is not None:
        page_filter = {int(p) for p in pages}

    hits: List[dict] = []
    for page in extracted.get("pages") or []:
        number = page.get("page")
        if page_filter is not None and number not in page_filter:
            continue
        text = page.get("text") or ""
        if not text.strip():
            continue
        overlap = q_tokens & set(_tokenize(text))
        phrase = bool(query.strip()) and query.strip().lower() in text.lower()
        if not overlap and not phrase:
            continue
        score = float(len(overlap)) + (5.0 if phrase else 0.0)
        hits.append({
            "page": number,
            "printed_page": page.get("printed_page"),
            "snippet": _make_snippet(text, query, overlap),
            "matched_terms": sorted(overlap),
            "phrase_match": phrase,
            "score": round(score, 3),
            "char_offset": page.get("char_offset"),
            "quality": page.get("quality"),
            "verification": LEVEL_PAGE,
        })

    hits.sort(key=lambda hit: (-hit["score"], hit["page"]))
    return hits


def search_pdf_pages(
    pdf_path: Any, query: str, *, pages: Optional[Iterable[int]] = None,
) -> List[dict]:
    """打开真实 PDF，返回页级命中（含物理页码与印刷页码）。"""
    extracted = extract_pages(pdf_path, sha256=False)
    return search_extracted_pages(extracted, query, pages=pages)


# ---------------------------------------------------------------------------
# 缓存（Server ID + Library ID + Item Key + Attachment Key + 内容指纹）
# ---------------------------------------------------------------------------

def default_cache_root() -> Path:
    """默认缓存根目录。

    默认 `<组件根>/.research-idea-pipeline/zotero-fulltext-cache`，该路径已被
    `research-idea-pipeline/.gitignore` 忽略（缓存全文绝不进版本库）。
    可用环境变量 `RESEARCH_ZOTERO_FULLTEXT_CACHE` 覆盖。
    """
    override = _clean(os.environ.get(CACHE_ROOT_ENV))
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parent.parent / ".research-idea-pipeline" / "zotero-fulltext-cache"


def _safe_component(value: Any) -> str:
    """把身份分量净化成安全的单层目录名（防路径穿越）。"""
    text = str(value).strip() if value is not None else ""
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._")
    if not text or text in (".", ".."):
        return "unknown"
    return text[:120]


def cache_path(
    cache_root: Optional[Any] = None,
    *,
    server_id: Optional[str],
    library_id: Optional[str] = DEFAULT_LIBRARY_ID,
    item_key: Optional[str],
    attachment_key: Optional[str],
    fingerprint: Optional[str] = None,
) -> Path:
    """缓存文件路径。

    Server ID 是路径第一层：Server ID 变化 ⇒ 目录整体不同 ⇒ 整库缓存自动失效。
    """
    root = Path(cache_root).expanduser() if cache_root else default_cache_root()
    return (root / _safe_component(server_id) / _safe_component(library_id)
            / _safe_component(item_key) / _safe_component(attachment_key)
            / f"{_safe_component(fingerprint) if fingerprint else 'nofp'}.json")


def cache_get(
    cache_root: Optional[Any] = None,
    *,
    server_id: Optional[str],
    library_id: Optional[str] = DEFAULT_LIBRARY_ID,
    item_key: Optional[str],
    attachment_key: Optional[str],
    fingerprint: Optional[str] = None,
) -> Optional[dict]:
    """按身份读取缓存内容；不存在 / 身份不匹配 / 解析失败 → None。"""
    path = cache_path(cache_root, server_id=server_id, library_id=library_id,
                      item_key=item_key, attachment_key=attachment_key,
                      fingerprint=fingerprint)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    identity = data.get("identity") or {}
    if identity.get("fingerprint") != fingerprint:
        return None
    if identity.get("server_id") != server_id:
        return None
    if identity.get("library_id") != (library_id or DEFAULT_LIBRARY_ID):
        return None
    if identity.get("item_key") != item_key:
        return None
    if identity.get("attachment_key") != attachment_key:
        return None

    payload = data.get("payload")
    return payload if isinstance(payload, dict) else None


def cache_put(
    cache_root: Optional[Any] = None,
    *,
    server_id: Optional[str],
    library_id: Optional[str] = DEFAULT_LIBRARY_ID,
    item_key: Optional[str],
    attachment_key: Optional[str],
    fingerprint: Optional[str] = None,
    payload: dict,
) -> Optional[str]:
    """按身份写入缓存（原子替换，权限 0600）；失败返回 None（不抛异常）。"""
    path = cache_path(cache_root, server_id=server_id, library_id=library_id,
                      item_key=item_key, attachment_key=attachment_key,
                      fingerprint=fingerprint)
    record = {
        "cache_version": CACHE_VERSION,
        "identity": {
            "server_id": server_id,
            "library_id": library_id or DEFAULT_LIBRARY_ID,
            "item_key": item_key,
            "attachment_key": attachment_key,
            "fingerprint": fingerprint,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(record, ensure_ascii=False)
    except (OSError, TypeError, ValueError):
        return None

    tmp_name: Optional[str] = None
    try:
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
        return str(path)
    except OSError:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        return None


#: 旧命名别名（架构草案曾写作 get_text_cache；保留以兼容调用方）。
get_text_cache = cache_get


def _prune_empty_dirs(base: Path) -> None:
    """删除 scope 下的空目录；不触碰 scope 本身。"""
    try:
        dirs = sorted((p for p in base.rglob("*") if p.is_dir()),
                      key=lambda p: len(p.parts), reverse=True)
    except OSError:
        return
    for directory in dirs:
        try:
            directory.rmdir()
        except OSError:
            pass


def invalidate_by_fingerprint(
    cache_root: Optional[Any] = None,
    *,
    server_id: Optional[str] = None,
    library_id: Optional[str] = None,
    item_key: Optional[str] = None,
    attachment_key: Optional[str] = None,
    fingerprint: Optional[str] = None,
) -> int:
    """按身份 / 指纹清理缓存，返回删除的文件数。

    - 给定 `fingerprint`：删除该 scope 内指纹**不匹配**的记录（PDF 变化时清理旧文本）。
    - 未给 `fingerprint` 也未给 `server_id`：删除整个 scope。
    - 给定 `server_id`：删除该 scope 内 server 不匹配的记录。

    只删除缓存目录内的 `*.json`，不触碰任何 PDF 或 Zotero 数据。
    """
    root = Path(cache_root).expanduser() if cache_root else default_cache_root()
    if not root.is_dir():
        return 0

    base = root
    for component in (server_id, library_id, item_key, attachment_key):
        if component is None:
            break
        base = base / _safe_component(component)
    if not base.is_dir():
        return 0

    removed = 0
    try:
        candidates = list(base.rglob("*.json"))
    except OSError:
        return 0
    for path in candidates:
        identity: Dict[str, Any] = {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                identity = data.get("identity") or {}
        except (OSError, ValueError):
            identity = {}
        drop = False
        if fingerprint is not None and identity.get("fingerprint") != fingerprint:
            drop = True
        if server_id is not None and identity.get("server_id") != server_id:
            drop = True
        if fingerprint is None and server_id is None:
            drop = True
        if drop:
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass

    _prune_empty_dirs(base)
    return removed


# ---------------------------------------------------------------------------
# 两层检索编排
# ---------------------------------------------------------------------------

def resolve_server_id(client: Any, *, base_url: Optional[str] = None) -> Optional[str]:
    """解析 Zotero Server ID：client 属性 → client.probe() → `zotero_client.probe()`。"""
    if client is not None:
        value = getattr(client, "server_id", None)
        if callable(value):
            try:
                value = value()
            except Exception:  # noqa: BLE001
                value = None
        if value:
            return str(value)

    probe = None
    if client is not None:
        probe = getattr(client, "probe", None)
    else:
        probe = getattr(zotero_client, "probe", None)
    if callable(probe):
        try:
            result = probe(base_url) if base_url else probe()
        except TypeError:
            try:
                result = probe()
            except Exception:  # noqa: BLE001
                return None
        except Exception:  # noqa: BLE001
            return None
        if result:
            return str(result)
    return None


def _deep_check_attachments(
    client: Any,
    record: dict,
    query: str,
    *,
    base_url: Optional[str],
    cache_root: Optional[Any],
    storage_dir: Optional[str],
    server_id: Optional[str],
    library_id: str,
    pages: Optional[Iterable[int]],
    warnings: List[str],
    cache_stats: Dict[str, int],
) -> Tuple[List[dict], dict]:
    """对一个条目的全部附件做页级深读；单个附件失败只降级，不抛异常。"""
    page_evidence: List[dict] = []
    pdf_info = {"readable": False, "text_chars": 0, "num_pages": 0, "sha256": None}
    item_key = record.get("zotero_key")

    for attachment in record.get("attachments") or []:
        att_key = attachment.get("attachment_key")
        if not att_key:
            continue
        path = resolve_attachment_path(
            client, {"key": att_key, "data": attachment},
            storage_dir=storage_dir, base_url=base_url)
        if not path:
            attachment["readable"] = False
            attachment["error"] = "文件不可访问"
            warnings.append(f"[zotero-fulltext] 附件不可访问：{att_key}（{item_key}）")
            continue

        attachment["path"] = path
        fingerprint = _sha256_file(Path(path))
        attachment["sha256"] = fingerprint

        extracted: Optional[dict] = None
        if fingerprint:
            cached = cache_get(
                cache_root, server_id=server_id, library_id=library_id,
                item_key=item_key, attachment_key=att_key, fingerprint=fingerprint)
            if isinstance(cached, dict):
                extracted = cached
                cache_stats["hits"] = cache_stats.get("hits", 0) + 1
        if extracted is None:
            if fingerprint:
                cache_stats["misses"] = cache_stats.get("misses", 0) + 1
            try:
                extracted = extract_pages(path, sha256=False)
            except (PdfUnavailable, FileNotFoundError, OSError) as exc:
                attachment["readable"] = False
                attachment["error"] = f"{type(exc).__name__}: {exc}"
                warnings.append(f"[zotero-fulltext] PDF 读取失败：{att_key}（{exc}）")
                continue
            extracted["sha256"] = fingerprint
            if fingerprint:
                cache_put(
                    cache_root, server_id=server_id, library_id=library_id,
                    item_key=item_key, attachment_key=att_key,
                    fingerprint=fingerprint, payload=extracted)

        attachment["readable"] = True
        attachment["num_pages"] = extracted.get("num_pages")
        attachment["text_chars"] = extracted.get("text_chars")
        attachment["pdf_quality"] = extracted.get("quality")
        pdf_info["readable"] = True
        pdf_info["text_chars"] += extracted.get("text_chars") or 0
        pdf_info["num_pages"] = max(pdf_info["num_pages"], extracted.get("num_pages") or 0)
        if fingerprint:
            pdf_info["sha256"] = fingerprint

        if (extracted.get("text_chars") or 0) <= 0:
            warnings.append(f"[zotero-fulltext] PDF 无可抽取文本（疑似扫描件）：{att_key}")
            continue

        for hit in search_extracted_pages(extracted, query, pages=pages):
            enriched = dict(hit)
            enriched["paper_key"] = item_key
            enriched["attachment_key"] = att_key
            page_evidence.append(enriched)

    return page_evidence, pdf_info


def search_two_layer(
    client: Any,
    query: str,
    *,
    limit: int = 50,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    deep: bool = False,
    base_url: Optional[str] = None,
    cache_root: Optional[Any] = None,
    storage_dir: Optional[str] = None,
    library_id: str = DEFAULT_LIBRARY_ID,
    pages: Optional[Iterable[int]] = None,
) -> dict:
    """两层检索：第 1 层 Zotero 原生索引；第 2 层（`deep=True`）真实 PDF 页级验证。

    返回::

        {
          "query", "deep",
          "results": [记录...],       # 每条含 verification / attachments / (deep) page_evidence
          "page_hits": [页级证据...], # 扁平列表，deep 时空
          "stats": {...},
          "warnings": [...],
          "cache": {"root", "hits", "misses"},
        }

    级别规则（页码纪律）：

    - 索引命中 → `indexed_fulltext`，**绝不**给页码。
    - 只有真实 PDF 页命中 → `page_verified`（带物理页与印刷页码）。
    - PDF 可读但未命中页、且原本不是索引命中 → `pdf_text_verified`。
    - 附件存在但不可读 / 无文本、且无索引 → `insufficient_evidence`。

    单个附件缺失 / 损坏 / 超时只降级该条目并进 `warnings`，**绝不让整批失败**。
    """
    warnings: List[str] = []
    cache_stats: Dict[str, Any] = {
        "root": str(cache_root or default_cache_root()), "hits": 0, "misses": 0,
    }

    try:
        results = search_indexed(
            client, query, limit=limit, from_year=from_year, to_year=to_year,
            base_url=base_url)
    except Exception as exc:  # noqa: BLE001 —— 检索整体失败也返回结构化结果
        return {
            "query": query,
            "deep": deep,
            "results": [],
            "page_hits": [],
            "stats": {"papers": 0, "page_hits": 0},
            "warnings": [f"[zotero-fulltext] 索引检索失败：{type(exc).__name__}: {exc}"],
            "cache": cache_stats,
        }

    server_id = resolve_server_id(client, base_url=base_url)
    page_hits: List[dict] = []

    for record in results:
        if not deep:
            continue
        evidence, pdf_info = _deep_check_attachments(
            client, record, query,
            base_url=base_url, cache_root=cache_root, storage_dir=storage_dir,
            server_id=server_id, library_id=library_id, pages=pages,
            warnings=warnings, cache_stats=cache_stats)
        record["page_evidence"] = evidence
        record["pdf"] = pdf_info
        page_hits.extend(evidence)

        if evidence:
            record["verification"] = LEVEL_PAGE
        elif record.get("verification") == LEVEL_INDEXED:
            # ★ 索引命中 + 深读没找到页命中 → 保持 indexed_fulltext，绝不升级。
            record["verification"] = LEVEL_INDEXED
        elif pdf_info["readable"] and pdf_info["text_chars"] > 0:
            record["verification"] = LEVEL_PDF_TEXT
        elif record.get("attachments") and (
                not pdf_info["readable"] or pdf_info["text_chars"] <= 0):
            # 附件存在但不可读 / 无任何可抽取文本（扫描件）：证据不足，绝不编造。
            record["verification"] = LEVEL_INSUFFICIENT

    stats = {
        "papers": len(results),
        "page_hits": len(page_hits),
        "page_verified": sum(1 for r in results if r.get("verification") == LEVEL_PAGE),
        "indexed_fulltext": sum(1 for r in results if r.get("verification") == LEVEL_INDEXED),
        "pdf_text_verified": sum(1 for r in results if r.get("verification") == LEVEL_PDF_TEXT),
        "insufficient_evidence": sum(
            1 for r in results if r.get("verification") == LEVEL_INSUFFICIENT),
        "attachments": sum(len(r.get("attachments") or []) for r in results),
        "attachments_unreadable": sum(
            1 for r in results for a in (r.get("attachments") or []) if a.get("readable") is False),
    }

    return {
        "query": query,
        "deep": deep,
        "results": results,
        "page_hits": page_hits,
        "stats": stats,
        "warnings": warnings,
        "cache": cache_stats,
    }


# ---------------------------------------------------------------------------
# 自检 CLI
# ---------------------------------------------------------------------------

def _main(argv: Optional[List[str]] = None) -> int:
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Zotero 全文检索 / PDF 页级抽取自检")
    parser.add_argument("pdf", nargs="?", help="要抽取的本地 PDF")
    parser.add_argument("--query", default=None, help="在 PDF 中做页级检索")
    parser.add_argument("--cache-root", default=None, help="覆盖缓存根目录")
    args = parser.parse_args(argv)

    if not args.pdf:
        parser.print_help()
        print(f"\n默认缓存目录：{default_cache_root()}")
        return 0

    extracted = extract_pages(args.pdf)
    print(f"pages={extracted['num_pages']} chars={extracted['text_chars']} "
          f"quality={extracted['quality']} sha256={extracted['sha256']}")
    if args.query:
        for hit in search_pdf_pages(args.pdf, args.query):
            print(json.dumps(hit, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
