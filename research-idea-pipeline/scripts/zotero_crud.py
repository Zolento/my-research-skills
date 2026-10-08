#!/usr/bin/env python3
"""Zotero 文献库 CRUD（P1）与安全删除（P2）。

本模块只负责**语义层**：去重、版本安全、集合合并、笔记追加、删除影响评估。
真正的写传输由 `zotero_write.WriteClient` 负责（本模块只调用，不复制它的逻辑）；
读取原语复用只读客户端 `zotero_client`。

与 Local API 相关的硬事实（Zotero 10.0.3，
`server_localAPI.js` 逐行核实）：

1. **写请求体是「条目数据字段」本身，不带 `data` 包装。**
   Local API 的 `writeSingleObject` / `writeMultipleObjects` 直接对
   `obj.toJSON()` 做顶层浅合并，再交给 `obj.fromJSON(json)`。Web API 的
   `{"data": {...}}` 包装在 Local API 上会被当作未知键忽略。因此本模块提交的
   payload 始终是 `{"itemType": ..., "title": ...}` 这种**扁平**结构。
2. **PATCH 是顶层浅合并，数组整体替换。** `mergePatchJSON()` 对每个出现的键
   直接覆盖，所以 `tags` / `collections` 必须提交**完整结果数组**。本模块对
   这两个字段执行**集合并集**，绝不提交半数组。
3. **单对象 DELETE 是 `eraseTx()` —— 永久抹除，不是移入回收站。**
   且必须先给出 `If-Unmodified-Since-Version`，否则 `428`。因此删除不可逆，
   默认 dry-run，且**永不批量删除**。
4. **一对象一次写。** 本模块不发数组型写请求（POST 只发单元素列表，DELETE 只
   发单 key），以配合「不得批量删除」的安全规则。

安全不变量：

- **DOI 去重优先。** `create_paper` 先按归一化 DOI → arXiv ID → 归一化标题+年份
  检索；命中即返回 `created=False`，不创建。预印本 vs 已发表版本**不算**精确重复，
  但同样默认拒建并报告 `version_relation`，交人工裁决（`allow_related_version=True`
  可显式放行）。
- **更新一律先读后写。** 版本号来自新鲜 `GET`，经 `WriteClient` 的
  `If-Unmodified-Since-Version` 提交；`412` 冲突时重新读取并报告，**不盲目覆盖**。
- **不丢字段。** 只提交调用方点名的字段；`tags` / `collections` 取并集。
- **不覆盖用户笔记。** 代理笔记带专用 tag 与正文标记，且**只新增**；
  `update_paper` 拒绝改写任何 note 正文。
- **删除凭据三闸门。** `dry_run=False` + `confirm=True` + 客户端确实可写；
  若被 Research State 的 `LIT<n>` 引用（可 `force=True` 显式越过）则拒绝。
- **失败即报告。** 不抛「成功」假象；超时只在幂等操作（PATCH/DELETE）上重试，
  POST 超时改为重新去重核对，避免制造重复条目。
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import zotero_client as zc
import zotero_write as zw

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

#: 代理笔记的专用标签（可与用户自建标签区分）。
AGENT_NOTE_TAG = "agent-note"

#: 代理笔记正文开头的显式标记（即使标签被用户改动也能识别）。
AGENT_NOTE_MARKER = "[agent-note]"

#: 单次写重试上限（仅对超时 / 5xx 这类可重试错误生效）。
MAX_WRITE_RETRIES = 2
RETRY_BACKOFF = 0.5

#: 测试可注入的 sleep（避免真实等待）。
_sleep = time.sleep

#: 版本关系取值（冻结；用于区分「精确重复」与「不同发表版本」）。
VERSION_EXACT = "exact-duplicate"
VERSION_NEW_IS_PREPRINT = "new-is-preprint-of-existing"
VERSION_NEW_IS_PUBLISHED = "new-is-published-version-of-existing"
VERSION_SAME_WORK = "same-work-different-record"
VERSION_DISTINCT = "distinct"

#: 视为「不同发表版本」的关系（不得当作精确重复自动合并/创建）。
RELATED_VERSION_RELATIONS = frozenset({
    VERSION_NEW_IS_PREPRINT, VERSION_NEW_IS_PUBLISHED, VERSION_SAME_WORK,
})

#: 写失败中**不得**重试的异常（协议要求 412 不得盲目重试；403/401 需重新授权）。
_NON_RETRYABLE = (
    zw.ZoteroConflict,
    zw.ZoteroForbidden,
    zw.ZoteroAuthDenied,
    zw.ZoteroAuthRequired,
    zw.ZoteroPrecondition,
)

#: record（`item_to_record` 形状）专有键：不得直接塞进 Zotero 写 payload。
_RECORD_ONLY_KEYS = frozenset({
    "authors", "year", "venue", "keywords", "sources", "abstract", "doi",
    "arxiv_id", "openalex_id", "cited_by_count", "references", "zotero_key",
    "needs_verification", "file", "sha256", "size_bytes", "added_at",
    "source", "metadata_from", "notes_path", "paper_id", "matched_on",
})

#: 已在 `_build_item_payload` 中显式处理的键。
_HANDLED_KEYS = frozenset({
    "itemType", "title", "abstract", "abstractNote", "doi", "DOI", "year",
    "date", "venue", "authors", "creators", "keywords", "tags", "collections",
    "arxiv_id", "archiveID", "url", "publicationTitle", "proceedingsTitle",
    "bookTitle", "libraryCatalog",
}) | _RECORD_ONLY_KEYS

#: Zotero 条目标量字段的宽松白名单；不在此表内的键会被**原样透传**并记入
#: `unmapped_fields` 警告（Local API 用 `fromJSON(strict:false)`，未知键通常忽略）。
_KNOWN_ZOTERO_FIELDS = frozenset({
    "title", "abstractNote", "date", "DOI", "url", "extra", "archive",
    "archiveLocation", "libraryCatalog", "callNumber", "rights", "language",
    "shortTitle", "volume", "issue", "pages", "edition", "series", "seriesTitle",
    "seriesText", "journalAbbreviation", "publicationTitle", "proceedingsTitle",
    "bookTitle", "encyclopediaTitle", "dictionaryTitle", "conferenceName",
    "university", "institution", "publisher", "place", "websiteTitle",
    "blogTitle", "programTitle", "network", "reportNumber", "reportType",
    "versionNumber", "system", "company", "country", "assignee", "patentNumber",
    "filingDate", "issuingAuthority", "legalStatus", "code", "codeNumber",
    "section", "session", "committee", "legislativeBody", "documentNumber",
    "repository", "repositoryLocation", "audioFileType", "runningTime", "scale",
    "mapType", "latitude", "longitude", "altTitle", "numberOfVolumes", "PMID",
    "PMCID", "ISBN", "ISSN", "numPages", "medium", "genre", "studio",
    "distributor", "label", "postType", "forumTitle", "episodeNumber",
    "podcastTitle", "audioRecordingFormat", "videoRecordingFormat", "format",
    "casting", "numberOfPages", "accessibility", "anatomicalLocation", "status",
    "filingDate", "applicationNumber", "priorityNumbers", "references",
    "dateAdded", "dateModified", "parentItem",
})

#: 条目类型 → 会议/期刊名字段。
_VENUE_FIELD_BY_TYPE = {
    "journalArticle": "publicationTitle",
    "conferencePaper": "proceedingsTitle",
    "book": "bookTitle",
    "bookSection": "bookTitle",
    "encyclopediaArticle": "encyclopediaTitle",
    "dictionaryEntry": "dictionaryTitle",
    "preprint": "repository",
    "report": "institution",
    "thesis": "university",
}

_LIT_TOKEN_RE = re.compile(r"\bLIT\d+\b")
_ARXIV_VERSION_RE = re.compile(r"v\d+$", re.IGNORECASE)
_ARXIV_DOI_RE = re.compile(r"^10\.48550/arxiv\.", re.IGNORECASE)

#: 命中原因优先级：DOI > arXiv ID > 标题+年份（`matches[0]` 取最强命中）。
_REASON_PRIORITY = {"doi": 0, "arxiv": 1, "title+year": 2}


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def _clean(value: Any) -> Optional[str]:
    """去空白；空串与 None 都归一为 None。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_arxiv_id(value: Optional[str]) -> Optional[str]:
    """arXiv 标识标准化：去 `arXiv:` 前缀、去 URL、去版本后缀、转小写。"""
    text = _clean(value)
    if not text:
        return None
    text = re.sub(r"^https?://arxiv\.org/(?:abs|pdf)/", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^10\.48550/arxiv\.", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^arxiv[.:/\s]*", "", text, flags=re.IGNORECASE)
    text = _ARXIV_VERSION_RE.sub("", text.strip())
    return text.lower() or None


def normalize_title(value: Optional[str]) -> Optional[str]:
    """标题标准化：仅保留字母/数字/CJK，压平空白，用于等价比较。"""
    text = _clean(value)
    if not text:
        return None
    text = text.casefold()
    text = re.sub(r"[^0-9a-z\u3400-\u4dbf\u4e00-\u9fff]+", " ", text)
    return " ".join(text.split()) or None


def _year_from(value: Any) -> Optional[int]:
    """从字符串 / 数字 / dict 取年份。"""
    if isinstance(value, dict):
        value = value.get("year") or value.get("date")
    if isinstance(value, int):
        return value if 1000 <= value <= 2999 else None
    text = _clean(value)
    if not text:
        return None
    match = re.search(r"(19|20)\d{2}", text)
    return int(match.group(0)) if match else None


def _item_key(item: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(item, dict):
        return None
    return _clean(item.get("key")) or _clean((item.get("data") or {}).get("key"))


def _item_version(item: Optional[Dict[str, Any]]) -> Optional[int]:
    if not isinstance(item, dict):
        return None
    version = item.get("version")
    if isinstance(version, bool):
        return None
    if isinstance(version, int):
        return version
    try:
        return int(version) if version is not None else None
    except (TypeError, ValueError):
        return None


def _item_data(item: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    data = item.get("data")
    return data if isinstance(data, dict) else {}


def _is_bibliographic(item: Dict[str, Any]) -> bool:
    """顶层可引用条目（排除附件 / 笔记 / 标注与其子条目）。"""
    data = _item_data(item)
    if data.get("itemType") in ("attachment", "note", "annotation"):
        return False
    return not data.get("parentItem")


def _tag_name(entry: Any) -> Optional[str]:
    if isinstance(entry, dict):
        return _clean(entry.get("tag"))
    return _clean(entry)


def _normalize_tag_entry(entry: Any) -> Optional[Dict[str, Any]]:
    """保留 tag 字典的其它键（如 `type`），只标准化名字。"""
    if isinstance(entry, dict):
        name = _clean(entry.get("tag"))
        if not name:
            return None
        out = dict(entry)
        out["tag"] = name
        return out
    name = _clean(entry)
    return {"tag": name} if name else None


def _tag_names(value: Any) -> List[str]:
    out: List[str] = []
    for entry in value or []:
        name = _tag_name(entry)
        if name and name not in out:
            out.append(name)
    return out


def _normalize_tags(value: Any) -> List[Dict[str, Any]]:
    """去重（大小写不敏感，保留首次出现的写法）。"""
    out: List[Dict[str, Any]] = []
    seen = set()
    for entry in value or []:
        normalized = _normalize_tag_entry(entry)
        if not normalized:
            continue
        low = normalized["tag"].casefold()
        if low in seen:
            continue
        seen.add(low)
        out.append(normalized)
    return out


def _union_tags(current: Any, incoming: Any) -> List[Dict[str, Any]]:
    """`tags` 的集合并集（PATCH 浅合并下必须提交完整数组）。"""
    return _normalize_tags(list(current or []) + list(incoming or []))


def _normalize_collections(value: Any) -> List[str]:
    out: List[str] = []
    for entry in value or []:
        key = _clean(entry)
        if key and key not in out:
            out.append(key)
    return out


def _union_collections(current: Any, incoming: Any) -> List[str]:
    return _normalize_collections(list(current or []) + list(incoming or []))


# ---------------------------------------------------------------------------
# 读面适配（duck-typed client）
# ---------------------------------------------------------------------------

def _read_item(client: Any, key: str) -> Optional[Dict[str, Any]]:
    """读单个条目：优先用 client 自带的读方法，否则回落 `zotero_client`。

    这是让测试可以注入**内存假客户端**的关键：`WriteClient` 本身没有读面，
    测试替身用同名方法补齐即可，绝不触网。
    """
    if not key:
        return None
    getter = getattr(client, "get_item", None)
    if callable(getter):
        try:
            return getter(key)
        except Exception:  # noqa: BLE001 —— 读面失败按「读不到」处理并如实上报
            return None
    base = getattr(client, "base_url", None)
    try:
        return zc.get_item(key, base_url=base)
    except zc.ZoteroUnavailable:
        return None


def _read_children(client: Any, key: str) -> List[Dict[str, Any]]:
    getter = getattr(client, "get_children", None)
    if callable(getter):
        try:
            children = getter(key)
        except Exception:  # noqa: BLE001
            return []
        return [c for c in children or [] if isinstance(c, dict)]
    base = getattr(client, "base_url", None)
    try:
        return zc.get_children(key, base_url=base)
    except zc.ZoteroUnavailable:
        return []


def _load_items(client: Any) -> Optional[List[Dict[str, Any]]]:
    """拉全库条目；不可读返回 None（调用方**不得**在 None 上继续写入）。"""
    fetcher = getattr(client, "fetch_items", None)
    if callable(fetcher):
        try:
            items = fetcher()
        except Exception:  # noqa: BLE001
            return None
        return [i for i in items or [] if isinstance(i, dict)]
    base = getattr(client, "base_url", None)
    try:
        return zc.fetch_items(base)
    except zc.ZoteroUnavailable:
        return None


def _library_id(client: Any) -> str:
    return _clean(getattr(client, "user", None)) or zc.DEFAULT_USER


def _writability(client: Any) -> Tuple[Optional[bool], Optional[str]]:
    """判定客户端是否真的可写。`None` = 无法判定（删除闸门会据此拒绝）。"""
    capability = getattr(client, "capability", None)
    if callable(capability):
        try:
            info = capability()
        except Exception as exc:  # noqa: BLE001
            return None, f"capability() 失败：{type(exc).__name__}: {exc}"
        if isinstance(info, dict) and "writable" in info:
            return bool(info["writable"]), _clean(info.get("reason"))
    has_key = getattr(client, "has_key", None)
    if has_key is not None:
        try:
            return bool(has_key), "has_key"
        except Exception as exc:  # noqa: BLE001
            return None, f"has_key 读取失败：{type(exc).__name__}: {exc}"
    return None, "无法判定写入能力（缺少 capability()/has_key）"


def _with_retry(call: Any, *, retries: int = MAX_WRITE_RETRIES) -> Tuple[Any, int]:
    """执行一次写调用，对超时 / 5xx 这类可重试错误做有限退避重试。

    返回 `(结果, 实际尝试次数)`。`412` / `403` / `401` / `428` **不重试**。
    """
    attempt = 0
    while True:
        try:
            return call(), attempt
        except _NON_RETRYABLE:
            raise
        except zw.ZoteroWriteError:
            if attempt >= retries:
                raise
            _sleep(RETRY_BACKOFF * (2 ** attempt))
            attempt += 1


# ---------------------------------------------------------------------------
# 元数据 → 条目 payload
# ---------------------------------------------------------------------------

def _venue_from_metadata(metadata: Dict[str, Any]) -> Optional[str]:
    for field in ("venue", "publicationTitle", "proceedingsTitle", "bookTitle",
                  "conferenceName", "publisher", "repository"):
        value = _clean(metadata.get(field))
        if value:
            return value
    return None


def _metadata_is_preprint(metadata: Dict[str, Any]) -> bool:
    if (_clean(metadata.get("itemType")) or "").lower() == "preprint":
        return True
    doi = zc.normalize_doi(metadata.get("DOI") or metadata.get("doi")) or ""
    if _ARXIV_DOI_RE.match(doi):
        return True
    if _clean(metadata.get("arxiv_id")) and not _venue_from_metadata(metadata):
        return True
    if (_clean(metadata.get("libraryCatalog")) or "").lower().startswith("arxiv"):
        return True
    return False


def _item_is_preprint(item: Dict[str, Any]) -> bool:
    data = _item_data(item)
    if (_clean(data.get("itemType")) or "").lower() == "preprint":
        return True
    doi = zc.normalize_doi(data.get("DOI")) or ""
    if _ARXIV_DOI_RE.match(doi):
        return True
    if (_clean(data.get("libraryCatalog")) or "").lower().startswith("arxiv"):
        return True
    return False


def _item_form(item: Dict[str, Any]) -> str:
    """`preprint` / `published` / `unknown`。"""
    data = _item_data(item)
    if _item_is_preprint(item):
        return "preprint"
    if data.get("publicationTitle") or data.get("proceedingsTitle") or data.get("bookTitle"):
        return "published"
    if data.get("itemType") in ("journalArticle", "conferencePaper", "book", "bookSection"):
        return "published"
    return "unknown"


def _metadata_form(metadata: Dict[str, Any]) -> str:
    if _metadata_is_preprint(metadata):
        return "preprint"
    if _venue_from_metadata(metadata):
        return "published"
    item_type = (_clean(metadata.get("itemType")) or "").lower()
    if item_type in ("journalarticle", "conferencepaper", "book", "booksection"):
        return "published"
    doi = zc.normalize_doi(metadata.get("DOI") or metadata.get("doi")) or ""
    if doi and not _ARXIV_DOI_RE.match(doi):
        return "published"
    return "unknown"


def _default_item_type(metadata: Dict[str, Any]) -> str:
    if _metadata_is_preprint(metadata):
        return "preprint"
    if _venue_from_metadata(metadata):
        return "journalArticle"
    doi = zc.normalize_doi(metadata.get("DOI") or metadata.get("doi")) or ""
    if doi:
        return "journalArticle"
    return "document"


def _split_creator(name: str) -> Dict[str, Any]:
    text = _clean(name) or ""
    parts = text.split()
    if len(parts) >= 2:
        return {"creatorType": "author", "firstName": " ".join(parts[:-1]),
                "lastName": parts[-1]}
    return {"creatorType": "author", "lastName": text}


def _creators_from_metadata(metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    creators = metadata.get("creators")
    out: List[Dict[str, Any]] = []
    if isinstance(creators, list) and creators:
        for entry in creators:
            if isinstance(entry, dict):
                creator = {"creatorType": _clean(entry.get("creatorType")) or "author"}
                if _clean(entry.get("name")):
                    creator["name"] = _clean(entry.get("name"))
                else:
                    creator["firstName"] = _clean(entry.get("firstName")) or ""
                    creator["lastName"] = _clean(entry.get("lastName")) or ""
                if creator.get("name") or creator.get("lastName"):
                    out.append(creator)
            elif isinstance(entry, str) and entry.strip():
                out.append(_split_creator(entry))
        return out
    authors = metadata.get("authors")
    if isinstance(authors, list):
        for entry in authors:
            if isinstance(entry, str) and entry.strip():
                out.append(_split_creator(entry))
            elif isinstance(entry, dict):
                out.extend(_creators_from_metadata({"creators": [entry]}))
    return out


def _metadata_authors(metadata: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for creator in _creators_from_metadata(metadata):
        if creator.get("name"):
            names.append(creator["name"])
        else:
            joined = " ".join(p for p in (creator.get("firstName"), creator.get("lastName")) if p)
            if joined:
                names.append(joined)
    return names


def _build_item_payload(metadata: Dict[str, Any], *, collections: Any = None,
                        tags: Any = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """把 record / Zotero 混合形状的元数据转成 Local API 可写的**扁平** payload。

    Returns:
        `(payload, unmapped)`：`unmapped` 是不在 Zotero 已知字段表内的键，
        原样透传但作为警告上报。
    """
    if not isinstance(metadata, dict):
        raise zw.ZoteroWriteError("metadata 必须是 dict")

    item_type = _clean(metadata.get("itemType")) or _default_item_type(metadata)
    payload: Dict[str, Any] = {"itemType": item_type}
    unmapped: Dict[str, Any] = {}

    for key, value in metadata.items():
        if key in _HANDLED_KEYS:
            continue
        canonical = "DOI" if key == "doi" else ("abstractNote" if key == "abstract" else key)
        if value is None:
            continue
        payload[canonical] = value
        if canonical not in _KNOWN_ZOTERO_FIELDS:
            unmapped[canonical] = value

    title = _clean(metadata.get("title"))
    if title:
        payload["title"] = title

    abstract = _clean(metadata.get("abstract") or metadata.get("abstractNote"))
    if abstract:
        payload["abstractNote"] = abstract

    doi = zc.normalize_doi(metadata.get("DOI") or metadata.get("doi"))
    if doi:
        payload["DOI"] = doi

    date = _clean(metadata.get("date"))
    year = _year_from(metadata.get("year") or metadata.get("date"))
    if date:
        payload["date"] = date
    elif year:
        payload["date"] = str(year)

    url = _clean(metadata.get("url"))
    if url:
        payload["url"] = url

    arxiv = normalize_arxiv_id(metadata.get("arxiv_id")) or normalize_arxiv_id(
        metadata.get("archiveID"))
    if arxiv:
        payload["archiveID"] = arxiv
        payload.setdefault("libraryCatalog", "arXiv.org")
        if payload.get("itemType") == "preprint":
            payload.setdefault("repository", "arXiv")
        if not payload.get("url"):
            payload["url"] = f"https://arxiv.org/abs/{arxiv}"

    venue = _venue_from_metadata(metadata)
    if venue:
        venue_field = _VENUE_FIELD_BY_TYPE.get(item_type, "publicationTitle")
        payload.setdefault(venue_field, venue)

    creators = _creators_from_metadata(metadata)
    if creators:
        payload["creators"] = creators

    payload["tags"] = _normalize_tags(tags) if tags else _normalize_tags(
        metadata.get("tags") or metadata.get("keywords"))
    merged_collections = _union_collections(
        collections if collections else metadata.get("collections"), None)
    payload["collections"] = merged_collections

    return payload, unmapped


def _metadata_record(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """未落库元数据的 record 视图（dry-run 与测试用，不伪造 Zotero key）。"""
    return {
        "title": _clean(metadata.get("title")),
        "authors": _metadata_authors(metadata),
        "abstract": _clean(metadata.get("abstract") or metadata.get("abstractNote")),
        "year": _year_from(metadata.get("year") or metadata.get("date")),
        "venue": _venue_from_metadata(metadata),
        "url": _clean(metadata.get("url")),
        "doi": zc.normalize_doi(metadata.get("DOI") or metadata.get("doi")),
        "arxiv_id": normalize_arxiv_id(metadata.get("arxiv_id")),
        "openalex_id": None,
        "cited_by_count": None,
        "references": [],
        "keywords": _tag_names(metadata.get("keywords") or metadata.get("tags")),
        "sources": ["local"],
        "zotero_key": None,
    }


# ---------------------------------------------------------------------------
# 检索 / 去重
# ---------------------------------------------------------------------------

def _record_view(item: Dict[str, Any]) -> Dict[str, Any]:
    return zc.item_to_record(item)


def _match_reasons(item: Dict[str, Any], *, doi: Optional[str], arxiv: Optional[str],
                   title: Optional[str], year: Optional[int]) -> List[str]:
    """返回命中原因列表（空列表 = 不命中）。优先级：DOI > arXiv > 标题+年份。"""
    data = _item_data(item)
    reasons: List[str] = []
    if doi:
        item_doi = zc.normalize_doi(data.get("DOI"))
        if item_doi and item_doi == doi:
            reasons.append("doi")
    if arxiv:
        item_arxiv = normalize_arxiv_id(zc.arxiv_id(data))
        if item_arxiv and item_arxiv == arxiv:
            reasons.append("arxiv")
    if title and not reasons:
        item_title = normalize_title(data.get("title"))
        if item_title and item_title == title:
            item_year = _year_from(data.get("date"))
            if year is None or item_year is None or item_year == year:
                reasons.append("title+year")
    return reasons


def _classify_relation(item: Dict[str, Any], metadata: Dict[str, Any],
                       matched_on: Sequence[str]) -> str:
    """判定「新元数据」与「已有条目」的关系，防止把预印本当成已发表版本。"""
    if "doi" in matched_on:
        return VERSION_EXACT
    old_form = _item_form(item)
    new_form = _metadata_form(metadata)
    if old_form == "published" and new_form == "preprint":
        return VERSION_NEW_IS_PREPRINT
    if old_form == "preprint" and new_form == "published":
        return VERSION_NEW_IS_PUBLISHED
    if "arxiv" in matched_on and old_form == new_form:
        return VERSION_EXACT
    return VERSION_SAME_WORK


def _find_matches(items: Sequence[Dict[str, Any]], *, doi: Optional[str],
                  arxiv: Optional[str], title: Optional[str],
                  year: Optional[int]) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or not _is_bibliographic(item):
            continue
        reasons = _match_reasons(item, doi=doi, arxiv=arxiv, title=title, year=year)
        if not reasons:
            continue
        record = _record_view(item)
        record.update({
            "item_key": _item_key(item),
            "version": _item_version(item),
            "matched_on": reasons,
        })
        matches.append(record)
    matches.sort(key=lambda m: min(
        _REASON_PRIORITY.get(reason, 9) for reason in m.get("matched_on") or ["zzz"]))
    return matches


def find_by_identifiers(client: Any, *, doi: Optional[str] = None,
                        arxiv_id: Optional[str] = None, title: Optional[str] = None,
                        year: Any = None) -> List[Dict[str, Any]]:
    """按 DOI → arXiv ID → 归一化标题+年份 查找已有条目。

    返回 record 视图（含 `item_key` / `version` / `matched_on`）。
    文献库不可读时返回空列表；**不要**据此认为「没有重复」——
    `create_paper` 会单独检查可读性并在不可读时拒绝创建。
    """
    items = _load_items(client)
    if items is None:
        return []
    norm_doi = zc.normalize_doi(doi)
    norm_arxiv = normalize_arxiv_id(arxiv_id)
    norm_title = normalize_title(title)
    norm_year = _year_from(year)
    return _find_matches(items, doi=norm_doi, arxiv=norm_arxiv, title=norm_title,
                         year=norm_year)


# ---------------------------------------------------------------------------
# P1：创建
# ---------------------------------------------------------------------------

def create_paper(client: Any, metadata: Dict[str, Any], *, collections: Any = None,
                 tags: Any = None, dry_run: bool = False,
                 allow_related_version: bool = False) -> Dict[str, Any]:
    """创建论文条目（默认先按 DOI/arXiv/标题+年份去重）。

    Returns:
        `{created, item_key, version, record, duplicate_of, dry_run, version_relation,
        verified, ...}`。`created=False` 且 `duplicate_of` 非空表示命中已有记录。

    说明：`allow_related_version=True` 时，允许为「不同发表版本」新建条目
    （预印本 ↔ 已发表）；精确重复（同一 DOI）**永远**拒建。
    """
    if not isinstance(metadata, dict):
        return {"created": False, "item_key": None, "version": None, "record": None,
                "duplicate_of": None, "dry_run": bool(dry_run),
                "error": "metadata 必须是 dict"}
    try:
        payload, unmapped = _build_item_payload(metadata, collections=collections, tags=tags)
    except zw.ZoteroWriteError as exc:
        return {"created": False, "item_key": None, "version": None, "record": None,
                "duplicate_of": None, "dry_run": bool(dry_run), "error": str(exc)}

    norm_doi = zc.normalize_doi(metadata.get("DOI") or metadata.get("doi"))
    norm_arxiv = normalize_arxiv_id(metadata.get("arxiv_id"))
    norm_title = normalize_title(metadata.get("title"))
    norm_year = _year_from(metadata.get("year") or metadata.get("date"))

    items = _load_items(client)
    if items is None:
        return {"created": False, "item_key": None, "version": None, "record": None,
                "duplicate_of": None, "dry_run": bool(dry_run),
                "error": "无法读取 Zotero 文献库，去重不可靠，拒绝创建",
                "payload": payload}

    matches = _find_matches(items, doi=norm_doi, arxiv=norm_arxiv, title=norm_title,
                            year=norm_year)
    if matches:
        best = matches[0]
        relation = _classify_relation(
            _find_item_by_key(items, best.get("item_key")), metadata, best.get("matched_on") or [])
        blocked = relation == VERSION_EXACT or not allow_related_version
        if blocked:
            return {
                "created": False,
                "item_key": best.get("item_key"),
                "version": best.get("version"),
                "record": best,
                "duplicate_of": best.get("item_key"),
                "version_relation": relation,
                "matched_on": best.get("matched_on"),
                "needs_review": relation != VERSION_EXACT,
                "dry_run": bool(dry_run),
                "library_id": _library_id(client),
                "payload": payload,
                "unmapped_fields": unmapped,
                "message": ("精确重复，拒绝创建" if relation == VERSION_EXACT
                            else "命中同一工作的不同发表版本，按安全默认拒绝创建（可 allow_related_version=True 放行）"),
            }
        related_to = best.get("item_key")
    else:
        relation = VERSION_DISTINCT
        related_to = None

    if dry_run:
        return {
            "created": False,
            "item_key": None,
            "version": None,
            "record": _metadata_record(metadata),
            "duplicate_of": None,
            "version_relation": relation,
            "dry_run": True,
            "library_id": _library_id(client),
            "payload": payload,
            "unmapped_fields": unmapped,
            "related_to": related_to,
            "message": "dry-run：未写入",
        }

    before_keys = {m.get("item_key") for m in matches}
    # ★ POST **不重试**：Local API 无幂等键（WriteClient 不暴露 Zotero-Write-Token），
    #   盲目重试可能创建重复条目。失败后改为重新去重核对。
    try:
        results = client.post("item", [payload])
        attempts = 0
    except _NON_RETRYABLE as exc:
        return {"created": False, "item_key": None, "version": None, "record": None,
                "duplicate_of": None, "dry_run": False, "error": str(exc),
                "refused": True, "payload": payload}
    except zw.ZoteroWriteError as exc:
        # POST 不盲目重试（可能已落库）。超时后**重新去重核对**，避免制造重复条目。
        recovered = _recover_after_post_failure(
            client, before_keys=before_keys, doi=norm_doi, arxiv=norm_arxiv,
            title=norm_title, year=norm_year)
        base = {"created": False, "item_key": None, "version": None, "record": None,
                "duplicate_of": None, "dry_run": False,
                "error": f"创建失败（写请求未确认）：{exc}", "payload": payload}
        if recovered:
            base.update({
                "created": True,
                "item_key": recovered.get("item_key"),
                "version": recovered.get("version"),
                "record": recovered,
                "verified": True,
                "recovered_after_failure": True,
                "message": "写请求报错后发现条目已落库，按已创建报告",
            })
        else:
            base["message"] = "创建未确认；重试前请先按 DOI 去重"
        return base

    successful = results.get("successful") if isinstance(results, dict) else None
    failed = results.get("failed") if isinstance(results, dict) else None
    created_obj = None
    if isinstance(successful, dict) and successful:
        created_obj = successful.get("0") or next(iter(successful.values()))
    if not isinstance(created_obj, dict):
        return {"created": False, "item_key": None, "version": None, "record": None,
                "duplicate_of": None, "dry_run": False,
                "error": "创建响应缺少 successful 结果",
                "raw_result": results if isinstance(results, dict) else None,
                "failed": failed, "payload": payload}

    item_key = _clean(created_obj.get("key")) or _clean(
        (created_obj.get("data") or {}).get("key"))
    version = _item_version(created_obj)

    fresh = _read_item(client, item_key) if item_key else None
    verified = fresh is not None
    verification = _verify_created(created_obj, fresh)
    if fresh is not None:
        version = _item_version(fresh) or version
        record = _record_view(fresh)
    else:
        record = _record_view(created_obj)

    return {
        "created": True,
        "item_key": item_key,
        "version": version,
        "record": record,
        "duplicate_of": None,
        "version_relation": relation,
        "related_to": related_to,
        "dry_run": False,
        "library_id": _library_id(client),
        "verified": verified,
        "verification": verification,
        "attempts": attempts,
        "payload": payload,
        "unmapped_fields": unmapped,
    }


def _find_item_by_key(items: Sequence[Dict[str, Any]], key: Optional[str]) -> Dict[str, Any]:
    if not key:
        return {}
    for item in items:
        if _item_key(item) == key:
            return item
    return {}


def _recover_after_post_failure(client: Any, *, before_keys: set, doi: Optional[str],
                                arxiv: Optional[str], title: Optional[str],
                                year: Optional[int]) -> Optional[Dict[str, Any]]:
    items = _load_items(client)
    if items is None:
        return None
    for match in _find_matches(items, doi=doi, arxiv=arxiv, title=title, year=year):
        if match.get("item_key") not in before_keys:
            return match
    return None


def _verify_created(created_obj: Dict[str, Any], fresh: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """创建后核对：必须能重新 GET 到，且关键字段一致。"""
    if fresh is None:
        return {"ok": False, "reason": "创建后无法重新读取条目（可能未落库或库不可读）",
                "mismatches": []}
    new_data = _item_data(created_obj)
    fresh_data = _item_data(fresh)
    mismatches = []
    for field in ("itemType", "title", "DOI", "url", "date"):
        if new_data.get(field) != fresh_data.get(field):
            mismatches.append(field)
    return {"ok": not mismatches, "reason": None if not mismatches else "字段不一致",
            "mismatches": mismatches}


# ---------------------------------------------------------------------------
# P1：更新（PATCH 浅合并 / 版本安全）
# ---------------------------------------------------------------------------

def _merge_patch_fields(current_data: Dict[str, Any],
                        patch: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """构造 PATCH 字段：tags / collections 取并集，其余原样。"""
    fields: Dict[str, Any] = {}
    info: Dict[str, Any] = {"added_tags": [], "added_collections": []}
    for key, value in patch.items():
        if key == "tags":
            before = _tag_names(current_data.get("tags"))
            before_low = {name.casefold() for name in before}
            merged = _union_tags(current_data.get("tags"), value)
            fields["tags"] = merged
            info["added_tags"] = [t["tag"] for t in merged
                                  if t["tag"].casefold() not in before_low]
        elif key == "collections":
            before = _normalize_collections(current_data.get("collections"))
            merged = _union_collections(current_data.get("collections"), value)
            fields["collections"] = merged
            info["added_collections"] = [k for k in merged if k not in before]
        else:
            fields[key] = value
    return fields, info


def _changed_fields(current_data: Dict[str, Any], fields: Dict[str, Any]) -> List[str]:
    changed: List[str] = []
    for key, value in fields.items():
        if current_data.get(key) != value:
            changed.append(key)
    return changed


def update_paper(client: Any, item_key: str, patch: Dict[str, Any], *,
                 dry_run: bool = False) -> Dict[str, Any]:
    """更新论文元数据。**先读后写**，PATCH 携带新鲜版本号。

    - `tags` / `collections` 按**并集**提交完整数组（浅合并下数组整体替换）。
    - 只提交 `patch` 点名的字段，其余字段不动。
    - note 条目的正文**永不改写**（代理笔记只能新增，见 `create_note`）。
    - `412` 冲突：重新读取并报告，不盲目覆盖。
    """
    base = {"updated": False, "item_key": item_key, "version": None, "before": None,
            "after": None, "changed_fields": [], "dry_run": bool(dry_run)}
    if not isinstance(patch, dict) or not patch:
        base["error"] = "patch 必须是非空 dict"
        return base

    before_item = _read_item(client, item_key)
    if before_item is None:
        base["error"] = "条目不存在或文献库不可读"
        return base

    before_data = _item_data(before_item)
    base["before"] = _record_view(before_item)
    version = _item_version(before_item)

    if (_clean(before_data.get("itemType")) or "").lower() == "note" and "note" in patch:
        base.update({
            "refused": True,
            "reason": "user-note-protected",
            "error": "拒绝改写笔记正文：代理笔记只能通过 create_note 新增",
        })
        return base

    fields, merge_info = _merge_patch_fields(before_data, patch)
    changed = _changed_fields(before_data, fields)
    base["changed_fields"] = changed
    base["version"] = version

    merged_data = dict(before_data)
    merged_data.update(fields)
    after_item = {"key": item_key, "version": version, "data": merged_data}
    base["after"] = _record_view(after_item)

    if not changed:
        base["updated"] = False
        base["message"] = "所有目标字段已是期望值，未发生写入"
        base["no_op"] = True
        return base

    if dry_run:
        base["dry_run"] = True
        base["planned_fields"] = fields
        base["merge_info"] = merge_info
        base["message"] = "dry-run：未写入"
        return base

    try:
        (status, _payload), attempts = _with_retry(
            lambda: client.patch("item", item_key, fields, version=version))
    except zw.ZoteroConflict as exc:
        fresh = _read_item(client, item_key)
        base.update({
            "conflict": True,
            "error": f"并发冲突（412），未覆盖：{exc}",
            "current": _record_view(fresh) if fresh else None,
            "current_version": _item_version(fresh),
            "attempts": 1,
        })
        return base
    except _NON_RETRYABLE as exc:
        base.update({"error": str(exc), "refused": True})
        return base
    except zw.ZoteroWriteError as exc:
        base.update({"error": f"写请求失败：{exc}"})
        return base

    fresh = _read_item(client, item_key)
    base.update({
        "updated": True,
        "attempts": attempts,
        "status": status,
        "version": _item_version(fresh) if fresh is not None else version,
        "after": _record_view(fresh) if fresh is not None else base["after"],
        "after_data": _item_data(fresh) if fresh is not None else merged_data,
        "merge_info": merge_info,
        "verified": fresh is not None,
    })
    return base


# ---------------------------------------------------------------------------
# P1：标签 / 集合
# ---------------------------------------------------------------------------

def _tag_mutation(client: Any, item_key: str, tags: Any, *, mode: str) -> Dict[str, Any]:
    """tags 变更的公共实现。`mode` ∈ add / remove。"""
    base = {"updated": False, "item_key": item_key, "version": None, "tags": [],
            "changed": [], "mode": mode}
    incoming = _normalize_tags(tags)
    if not incoming:
        base["error"] = "未提供有效标签"
        return base
    item = _read_item(client, item_key)
    if item is None:
        base["error"] = "条目不存在或文献库不可读"
        return base
    data = _item_data(item)
    version = _item_version(item)
    current = _normalize_tags(data.get("tags"))
    if mode == "add":
        result = _union_tags(current, incoming)
        changed = [t["tag"] for t in result
                   if t["tag"].casefold() not in {c["tag"].casefold() for c in current}]
    else:
        drop = {t["tag"].casefold() for t in incoming}
        result = [t for t in current if t["tag"].casefold() not in drop]
        changed = [t["tag"] for t in current if t["tag"].casefold() in drop]
    base["tags"] = [t["tag"] for t in result]
    base["changed"] = changed
    base["version"] = version
    if not changed:
        base["no_op"] = True
        base["message"] = "无变化"
        return base
    try:
        (status, _payload), attempts = _with_retry(
            lambda: client.patch("item", item_key, {"tags": result}, version=version))
    except zw.ZoteroConflict as exc:
        base.update({"conflict": True, "error": f"并发冲突（412），未覆盖：{exc}"})
        return base
    except _NON_RETRYABLE as exc:
        base.update({"error": str(exc), "refused": True})
        return base
    except zw.ZoteroWriteError as exc:
        base.update({"error": f"写请求失败：{exc}"})
        return base
    base.update({
        "updated": True,
        "attempts": attempts,
        "status": status,
        # 只改关联，绝不动全局 tag 定义（本模块从不调用 /tags 的写端点）。
        "tag_definitions_untouched": True,
    })
    return base


def add_tags(client: Any, item_key: str, tags: Any) -> Dict[str, Any]:
    """给条目加标签（并集）。不创建/修改全局 tag 定义之外的任何东西。"""
    return _tag_mutation(client, item_key, tags, mode="add")


def remove_tags(client: Any, item_key: str, tags: Any) -> Dict[str, Any]:
    """移除条目上的标签关联。

    ★ **只删关联，不删全局 tag 定义。** 本函数只 PATCH 条目的 `tags` 数组，
    从不调用任何 tag 删除端点，因此 Zotero 的标签库条目保持原样。
    """
    result = _tag_mutation(client, item_key, tags, mode="remove")
    result["tag_definitions_untouched"] = True
    return result


def _collection_mutation(client: Any, item_key: str, collection_key: str,
                         *, mode: str) -> Dict[str, Any]:
    base = {"updated": False, "item_key": item_key, "collection_key": collection_key,
            "version": None, "collections": [], "mode": mode}
    key = _clean(collection_key)
    if not key:
        base["error"] = "collection_key 不能为空"
        return base
    item = _read_item(client, item_key)
    if item is None:
        base["error"] = "条目不存在或文献库不可读"
        return base
    data = _item_data(item)
    version = _item_version(item)
    current = _normalize_collections(data.get("collections"))
    if mode == "add":
        result = _union_collections(current, [key])
        changed = key not in current
    else:
        result = [c for c in current if c != key]
        changed = key in current
    base["collections"] = result
    base["version"] = version
    if not changed:
        base["no_op"] = True
        base["message"] = "无变化"
        return base
    try:
        (status, _payload), attempts = _with_retry(
            lambda: client.patch("item", item_key, {"collections": result}, version=version))
    except zw.ZoteroConflict as exc:
        base.update({"conflict": True, "error": f"并发冲突（412），未覆盖：{exc}"})
        return base
    except _NON_RETRYABLE as exc:
        base.update({"error": str(exc), "refused": True})
        return base
    except zw.ZoteroWriteError as exc:
        base.update({"error": f"写请求失败：{exc}"})
        return base
    base.update({"updated": True, "attempts": attempts, "status": status})
    return base


def add_to_collection(client: Any, item_key: str, collection_key: str) -> Dict[str, Any]:
    """把条目加入集合（并集完整提交）。"""
    return _collection_mutation(client, item_key, collection_key, mode="add")


def remove_from_collection(client: Any, item_key: str, collection_key: str) -> Dict[str, Any]:
    """把条目移出集合（并集完整提交，不删除集合本身）。"""
    return _collection_mutation(client, item_key, collection_key, mode="remove")


# ---------------------------------------------------------------------------
# P1：笔记（只新增，永不改写正文）
# ---------------------------------------------------------------------------

def _marked_note_body(note: str) -> str:
    text = note or ""
    if AGENT_NOTE_MARKER in text:
        return text
    return f"<p>{AGENT_NOTE_MARKER} {text}</p>"


def is_agent_note(item: Dict[str, Any]) -> bool:
    """识别代理笔记：专用 tag **或** 正文标记任一命中。"""
    data = _item_data(item)
    if (_clean(data.get("itemType")) or "").lower() != "note":
        return False
    if AGENT_NOTE_TAG in _tag_names(data.get("tags")):
        return True
    return AGENT_NOTE_MARKER in (data.get("note") or "")


def create_note(client: Any, parent_key: str, note: str, *,
                tags: Any = None) -> Dict[str, Any]:
    """给父条目**新增**一条代理笔记。

    ★ 永远 POST（新增），从不 PATCH 既有笔记 → 用户手写笔记不会被覆盖。
    正文带显式标记，并附带专用 tag，使代理产物可被单独筛出。
    """
    base = {"created": False, "note_key": None, "version": None, "parent_key": parent_key,
            "note": None, "tags": [], "marker": AGENT_NOTE_MARKER}
    if not _clean(parent_key):
        base["error"] = "parent_key 不能为空"
        return base
    if not _clean(note):
        base["error"] = "note 内容不能为空"
        return base
    body = _marked_note_body(note)
    payload = {
        "itemType": "note",
        "parentItem": parent_key,
        "note": body,
        "tags": _union_tags([{"tag": AGENT_NOTE_TAG}], _normalize_tags(tags)),
    }
    try:
        results = client.post("item", [payload])
        attempts = 0
    except _NON_RETRYABLE as exc:
        base.update({"error": str(exc), "refused": True})
        return base
    except zw.ZoteroWriteError as exc:
        base.update({"error": f"笔记创建失败（未确认）：{exc}"})
        return base
    successful = results.get("successful") if isinstance(results, dict) else None
    created_obj = None
    if isinstance(successful, dict) and successful:
        created_obj = successful.get("0") or next(iter(successful.values()))
    if not isinstance(created_obj, dict):
        base.update({"error": "创建响应缺少 successful 结果",
                     "raw_result": results if isinstance(results, dict) else None})
        return base
    note_key = _clean(created_obj.get("key")) or _clean(
        (created_obj.get("data") or {}).get("key"))
    fresh = _read_item(client, note_key) if note_key else None
    base.update({
        "created": True,
        "note_key": note_key,
        "version": _item_version(fresh) if fresh is not None else _item_version(created_obj),
        "note": _item_data(fresh or created_obj).get("note", body),
        "tags": _tag_names(_item_data(fresh or created_obj).get("tags")),
        "is_agent_note": True,
        "verified": fresh is not None,
        "attempts": attempts,
    })
    return base


def get_notes(client: Any, parent_key: str) -> List[Dict[str, Any]]:
    """列出父条目下的笔记（含是否代理笔记）。"""
    out: List[Dict[str, Any]] = []
    for child in _read_children(client, parent_key):
        data = _item_data(child)
        if (_clean(data.get("itemType")) or "").lower() != "note":
            continue
        out.append({
            "note_key": _item_key(child),
            "version": _item_version(child),
            "parent_key": parent_key,
            "note": data.get("note") or "",
            "tags": _tag_names(data.get("tags")),
            "is_agent_note": is_agent_note(child),
            "date_added": _clean(data.get("dateAdded")),
        })
    return out


# ---------------------------------------------------------------------------
# P2：安全删除
# ---------------------------------------------------------------------------

def _literature_match_reason(entry: Dict[str, Any], *, item_key: str, doi: Optional[str],
                             arxiv: Optional[str], title: Optional[str]) -> List[str]:
    reasons: List[str] = []
    for field in ("zotero_item_key", "zotero_key", "item_key", "key"):
        value = _clean(entry.get(field))
        if item_key and value and value == item_key:
            reasons.append(f"literature.{field}")
    if doi:
        entry_doi = zc.normalize_doi(entry.get("doi") or entry.get("DOI"))
        if entry_doi and entry_doi == doi:
            reasons.append("literature.doi")
    if arxiv:
        entry_arxiv = normalize_arxiv_id(entry.get("arxiv_id") or entry.get("arxivId"))
        if entry_arxiv and entry_arxiv == arxiv:
            reasons.append("literature.arxiv_id")
    ref = entry.get("ref")
    if isinstance(ref, str) and ref.strip():
        low = ref.casefold()
        if item_key and item_key.casefold() in low:
            reasons.append("literature.ref~item_key")
        if doi and doi in low:
            reasons.append("literature.ref~doi")
        if title:
            norm_title = normalize_title(title)
            if norm_title and len(norm_title) >= 12 and norm_title in normalize_title(ref):
                reasons.append("literature.ref~title")
    url = entry.get("url")
    if isinstance(url, str):
        if item_key and item_key in url:
            reasons.append("literature.url~item_key")
        if arxiv and arxiv in url.casefold():
            reasons.append("literature.url~arxiv")
    return reasons


def _collect_lit_tokens(value: Any) -> List[str]:
    tokens: List[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            tokens.extend(m.group(0) for m in _LIT_TOKEN_RE.finditer(node))
        elif isinstance(node, dict):
            for child in node.values():
                walk(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                walk(child)

    walk(value)
    return tokens


def _scan_state_references(state: Any, *, item_key: str, doi: Optional[str] = None,
                           arxiv_id: Optional[str] = None,
                           title: Optional[str] = None) -> Dict[str, Any]:
    """扫描已解析的 Research State，找指向目标条目的 `LIT<n>` 及其下游引用。

    **防御式**：任何非预期形状都只记录、不抛异常。返回结构：

    `{checked, scan_error, literature_matches, referenced_lit_ids,
      referencing_objects, total_references}`
    """
    result: Dict[str, Any] = {
        "checked": False,
        "scan_error": None,
        "literature_matches": [],
        "referenced_lit_ids": [],
        "referencing_objects": [],
        "total_references": 0,
    }
    if state is None:
        result["note"] = "未提供 Research State，跳过引用检查"
        return result
    if not isinstance(state, dict):
        result["scan_error"] = f"state 不是对象（{type(state).__name__}）"
        return result
    try:
        result["checked"] = True
        # 形状不可信 = 无法证明「没有引用」→ 记 scan_error，删除闸门据此**失败即拒绝**。
        shape_errors = [
            f"{field} 不是数组（{type(state.get(field)).__name__}）"
            for field in ("literature", "evidence", "claims", "assurance",
                          "hypotheses", "experiments")
            if state.get(field) is not None and not isinstance(state.get(field), list)
        ]
        literature = state.get("literature")
        matches: List[Dict[str, Any]] = []
        if isinstance(literature, list):
            for entry in literature:
                if not isinstance(entry, dict):
                    continue
                reasons = _literature_match_reason(
                    entry, item_key=item_key, doi=doi, arxiv=arxiv_id, title=title)
                if reasons:
                    matches.append({
                        "id": _clean(entry.get("id")),
                        "ref": _clean(entry.get("ref")),
                        "relation": _clean(entry.get("relation")),
                        "reasons": reasons,
                    })
        lit_ids = {m["id"] for m in matches if m["id"]}
        result["literature_matches"] = matches
        result["referenced_lit_ids"] = sorted(lit_ids)

        referencing: List[Dict[str, Any]] = []
        for kind in ("evidence", "claims", "assurance", "hypotheses", "experiments"):
            array = state.get(kind)
            if not isinstance(array, list):
                continue
            for entry in array:
                if not isinstance(entry, dict):
                    continue
                hits = sorted(set(_collect_lit_tokens(entry)) & lit_ids)
                if hits:
                    referencing.append({
                        "kind": kind,
                        "id": _clean(entry.get("id")),
                        "via": hits,
                    })
        result["referencing_objects"] = referencing
        result["total_references"] = len(matches) + len(referencing)
        if shape_errors:
            result["scan_error"] = "；".join(shape_errors)
    except Exception as exc:  # noqa: BLE001 —— 扫描失败必须成为拒绝删除的理由
        result["scan_error"] = f"{type(exc).__name__}: {exc}"
    return result


def _classify_children(children: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = {
        "attachments": [], "notes": [], "annotations": [], "other": [],
    }
    for child in children:
        data = _item_data(child)
        item_type = (_clean(data.get("itemType")) or "").lower()
        entry = {
            "item_key": _item_key(child),
            "version": _item_version(child),
            "item_type": item_type,
            "title": _clean(data.get("title")) or _clean(data.get("filename")),
            "content_type": _clean(data.get("contentType")),
            "link_mode": _clean(data.get("linkMode")),
            "is_agent_note": is_agent_note(child) if item_type == "note" else None,
        }
        if item_type == "attachment":
            groups["attachments"].append(entry)
        elif item_type == "note":
            groups["notes"].append(entry)
        elif item_type == "annotation":
            groups["annotations"].append(entry)
        else:
            groups["other"].append(entry)
    return groups


def delete_paper(client: Any, item_key: str, *, dry_run: bool = True, confirm: bool = False,
                 state: Any = None, force: bool = False) -> Dict[str, Any]:
    """安全删除（P2）。**默认 dry-run**，真实删除需三重凭据。

    闸门（全部满足才真正删除）：

    1. `dry_run=False` —— 显式要求真实删除。
    2. `confirm=True` —— 显式确认（不可逆：Local API 用 `eraseTx()` **永久抹除**）。
    3. 客户端**确实可写**（`capability().writable` 或 `has_key`）。
    4. 未被 Research State 的 `LIT<n>` 引用；若引用存在，默认拒绝，
       只有 `force=True` 才越过（并如实报告依赖）。

    另外：**永不批量删除**。本函数只对单个 key 发一次 `client.delete`。
    """
    result: Dict[str, Any] = {
        "deleted": False,
        "dry_run": bool(dry_run),
        "refused": False,
        "reason": None,
        "item_key": item_key,
        "version": None,
        "impact": None,
        "gates": {},
    }
    item = _read_item(client, item_key)
    if item is None:
        result["error"] = "条目不存在或文献库不可读"
        return result

    data = _item_data(item)
    version = _item_version(item)
    result["version"] = version
    children = _read_children(client, item_key)
    groups = _classify_children(children)
    doi = zc.normalize_doi(data.get("DOI"))
    arxiv = normalize_arxiv_id(zc.arxiv_id(data))
    state_scan = _scan_state_references(
        state, item_key=item_key, doi=doi, arxiv_id=arxiv, title=_clean(data.get("title")))

    impact = {
        "item_key": item_key,
        "version": version,
        "title": _clean(data.get("title")),
        "item_type": _clean(data.get("itemType")),
        "library_id": _library_id(client),
        "record": _record_view(item),
        "tags": _tag_names(data.get("tags")),
        "collections": _normalize_collections(data.get("collections")),
        "children": groups,
        "counts": {
            "attachments": len(groups["attachments"]),
            "notes": len(groups["notes"]),
            "annotations": len(groups["annotations"]),
            "other": len(groups["other"]),
            "total_children": len(children),
        },
        "research_state": state_scan,
        "warnings": [],
        "irreversible": True,
    }
    if groups["attachments"]:
        impact["warnings"].append(
            f"将一并永久删除 {len(groups['attachments'])} 个附件条目（含其文件关联）")
    if groups["notes"]:
        impact["warnings"].append(f"将一并永久删除 {len(groups['notes'])} 条笔记")
    if groups["annotations"]:
        impact["warnings"].append(f"将一并永久删除 {len(groups['annotations'])} 条标注")
    result["impact"] = impact

    writable, writable_reason = _writability(client)
    state_blocked = bool(state_scan.get("total_references")) or bool(
        state_scan.get("scan_error"))
    gates = {
        "dry_run": bool(dry_run),
        "confirmed": bool(confirm),
        "writable": writable,
        "writable_reason": writable_reason,
        "state_checked": bool(state_scan.get("checked")),
        "state_clear": not state_blocked,
        "force": bool(force),
    }
    result["gates"] = gates

    if dry_run:
        result["preview"] = impact
        result["message"] = "dry-run：未删除。真实删除需 dry_run=False + confirm=True"
        return result

    blockers: List[str] = []
    if not confirm:
        blockers.append("needs-confirm")
    if writable is not True:
        blockers.append("not-writable")
    if state_blocked and not force:
        blockers.append("research-state-reference")
    if blockers:
        result["refused"] = True
        result["reason"] = blockers[0]
        result["blockers"] = blockers
        result["message"] = {
            "needs-confirm": "真实删除被拒绝：需要 confirm=True 显式确认",
            "not-writable": f"真实删除被拒绝：客户端不可写（{writable_reason or '未授权'}）",
            "research-state-reference": "真实删除被拒绝：目标被 Research State 引用（force=True 可显式越过）",
        }[blockers[0]]
        return result

    try:
        (status, _payload), attempts = _with_retry(
            lambda: client.delete("item", item_key, version=version))
    except zw.ZoteroConflict as exc:
        fresh = _read_item(client, item_key)
        result.update({
            "conflict": True,
            "error": f"并发冲突（412），未删除：{exc}",
            "current_version": _item_version(fresh),
            "current": _record_view(fresh) if fresh else None,
        })
        return result
    except _NON_RETRYABLE as exc:
        result.update({"error": str(exc), "refused": True})
        return result
    except zw.ZoteroWriteError as exc:
        result.update({"error": f"删除失败（未确认）：{exc}"})
        return result

    after = _read_item(client, item_key)
    result.update({
        "deleted": True,
        "status": status,
        "attempts": attempts,
        "verified": after is None,
        "batch": False,
    })
    if after is not None:
        result["warning"] = "删除请求已接受，但条目仍可读；请人工确认"
    return result
