#!/usr/bin/env python3
"""Zotero Local API 只读客户端（供文献检索与 refs 导出复用）。

设计约束：

1. **只读。** 只发 GET，不需要 API Key，绝不写入 Zotero。
2. **仅标准库。** 与 `literature_sources.py` 一致，用 `urllib`。
3. **离线优先。** Zotero 未运行时抛 `ZoteroUnavailable`，由调用方回落到 `docs/refs/`。

Local API 协议要点（Zotero 10.0.3 源码 `server_localAPI.js` 核实）：

- 读请求无需认证；响应头 `Zotero-Server-ID` 标识本机实例。
- 写请求才需要 `Zotero-Server-ID` 与 `/api/local/authorize` 颁发的 Key。本模块不涉及。
- 本地 API 默认不分页、无限流，一次 GET 即可取回全库。

CLI 自检：

    python3 scripts/zotero_client.py --probe
    python3 scripts/zotero_client.py --dump-records 3
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Tuple

#: Zotero 本地 API 默认地址（Zotero 桌面端默认监听该端口）。
DEFAULT_LOCAL_API = "http://127.0.0.1:23119/api"

#: 探测默认超时（秒）。保持短，避免拖慢无 Zotero 的机器。
PROBE_TIMEOUT = 2.0

#: 拉取全库默认超时（秒）。2744 条约 20 秒。
FETCH_TIMEOUT = 60.0

#: 单对象读取默认超时（秒）。
HTTP_TIMEOUT = 30.0

#: 用户库（个人库）。0 等价于当前登录用户。
DEFAULT_USER = "0"

STATUS_HEADER = "Zotero-Server-ID"
UA = "research-idea-pipeline/zotero (+https://github.com/Zolento/my-research-skills)"

_CHILD_TYPES = frozenset({"attachment", "note", "annotation"})

_DOI_RE = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
_ARXIV_NEW_RE = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")
_ARXIV_OLD_RE = re.compile(r"([a-z-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?")

#: 裸新式 ID 必须独立成词，否则 `10.1109/TMI.2018.2820120` 会被截成 `2018.28201`。
_BARE_ARXIV_NEW_RE = re.compile(r"(?<![\d.])(\d{4}\.\d{4,5})(?!\d)")

#: 旧式标识的 archive 部分（`cs.CV/0701001` 里的 `cs.CV`）。
#: 用于拒绝无锚点误匹配 —— 例如 URL 路径 `.../document/10656634/`。
_ARXIV_ARCHIVES = frozenset({
    "cs", "stat", "math", "physics", "eess", "q-bio", "q-fin",
    "astro-ph", "cond-mat", "gr-qc", "hep-ex", "hep-lat", "hep-ph",
    "hep-th", "math-ph", "nlin", "nucl-ex", "nucl-th", "quant-ph",
})


class ZoteroUnavailable(RuntimeError):
    """Zotero 本地 API 不可达（未运行 / 地址错误 / 超时）。

    调用方**必须**捕获它并回落到 `docs/refs/`，不得让整条检索失败。
    """


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def _clean(value: Any) -> Optional[str]:
    """去空白；空串与 None 都归一为 None。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_doi(value: Optional[str]) -> Optional[str]:
    """DOI 标准化：去 URL 前缀、去空白、转小写、去尾部标点。"""
    text = _clean(value)
    if not text:
        return None
    text = re.sub(r"^\s*(https?://(dx\.)?doi\.org/|doi:\s*)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", "", text)
    return text.rstrip(".,;)]}").lower() or None


def _year(value: Optional[str]) -> Optional[int]:
    match = re.search(r"(19|20)\d{2}", value or "")
    return int(match.group(0)) if match else None


def _old_arxiv_archive(value: str) -> bool:
    """旧式标识的 archive 是否为真实 arXiv archive。

    防止 `https://ieeexplore.ieee.org/document/10656634/` 这类路径被当成
    `document/1065663`（历史 bug）。
    """
    archive = value.split("/", 1)[0].lower()
    return archive.split(".", 1)[0] in _ARXIV_ARCHIVES


def _arxiv_in_context(text: str) -> Optional[str]:
    """只从**明确的 arXiv 语境**取 ID：arXiv 链接，或 `arXiv:` 前缀。

    不对任意 URL 做无锚点匹配。
    """
    match = re.search(
        r"arxiv\.org/(?:abs|pdf)/((?:\d{4}\.\d{4,5})|(?:[a-z-]+(?:\.[A-Z]{2})?/\d{7}))",
        text, re.IGNORECASE)
    if match:
        value = match.group(1)
        if "/" not in value or _old_arxiv_archive(value):
            return value

    match = re.search(
        r"arxiv[.:\s/]\s*((?:\d{4}\.\d{4,5})|(?:[a-z-]+(?:\.[A-Z]{2})?/\d{7}))(?:v\d+)?",
        text, re.IGNORECASE)
    if match:
        value = match.group(1)
        if "/" not in value or _old_arxiv_archive(value):
            return value
    return None


def _bare_arxiv_in_metadata(text: str) -> Optional[str]:
    """无前缀裸 ID：只用于 `archiveID` / `extra` 这类纯元数据字段。

    旧式必须落在真实 archive 上；新式必须**独立成词**，避免把别处的
    DOI（如 `10.1109/TMI.2018.2820120` → `2018.28201`）当成 arXiv ID。
    """
    match = _BARE_ARXIV_NEW_RE.search(text)
    if match:
        return match.group(1)
    match = _ARXIV_OLD_RE.search(text)
    if match and _old_arxiv_archive(match.group(1)):
        return match.group(1)
    return None


def arxiv_id(item: Dict[str, Any]) -> Optional[str]:
    """从 DOI / url / extra / archiveID 提取 arXiv 标识。"""
    doi = _clean(item.get("DOI")) or ""
    match = re.search(r"arxiv[./:]?\s*(\d{4}\.\d{4,5})", doi, re.IGNORECASE)
    if match:
        return match.group(1)

    for field in ("url", "extra"):
        found = _arxiv_in_context(_clean(item.get(field)) or "")
        if found:
            return found

    for field in ("archiveID", "extra"):
        found = _bare_arxiv_in_metadata(_clean(item.get(field)) or "")
        if found:
            return found

    if (_clean(item.get("libraryCatalog")) or "").lower().startswith("arxiv"):
        for field in ("archiveID", "extra", "url"):
            text = _clean(item.get(field)) or ""
            found = _arxiv_in_context(text) or _bare_arxiv_in_metadata(text)
            if found:
                return found
    return None


def _authors(item: Dict[str, Any]) -> List[str]:
    """creators → ["Given Family", ...]；机构作者用 name 字段。"""
    names: List[str] = []
    for creator in item.get("creators") or []:
        if not isinstance(creator, dict):
            continue
        name = _clean(creator.get("name"))
        if not name:
            given = _clean(creator.get("firstName")) or ""
            family = _clean(creator.get("lastName")) or ""
            name = " ".join(part for part in (given, family) if part) or None
        if name:
            names.append(name)
    return names


#: venue 字段按条目类型优先级。
_VENUE_FIELDS = (
    "publicationTitle", "proceedingsTitle", "bookTitle", "encyclopediaTitle",
    "dictionaryTitle", "conferenceName", "university", "institution",
    "publisher", "websiteTitle", "blogTitle",
)


def _venue(item: Dict[str, Any]) -> Optional[str]:
    for field in _VENUE_FIELDS:
        value = _clean(item.get(field))
        if value:
            return value
    return None


def _keywords(item: Dict[str, Any]) -> List[str]:
    """标签转关键词。Zotero 标签多为 arXiv 分类，仍保留以支持本地匹配。"""
    out: List[str] = []
    for tag in item.get("tags") or []:
        name = _clean(tag.get("tag")) if isinstance(tag, dict) else _clean(tag)
        if name and name not in out:
            out.append(name)
    return out


# ---------------------------------------------------------------------------
# HTTP（只读）
# ---------------------------------------------------------------------------

def _get_json(url: str, *, timeout: float) -> Any:
    request = urllib.request.Request(url, headers={
        "Zotero-API-Version": "3",
        "Accept": "application/json",
        "User-Agent": UA,
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ZoteroUnavailable(f"HTTP {exc.code} from {url}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ZoteroUnavailable(f"{type(exc).__name__}: {exc}") from exc


def _get_text(url: str, *, timeout: float) -> str:
    """取纯文本响应。

    `GET /items/{key}/file/view/url` 返回 `Content-Type: text/plain` 的裸 URL，
    不是 JSON —— 用 `_get_json` 会失败。
    """
    request = urllib.request.Request(url, headers={
        "Zotero-API-Version": "3", "User-Agent": UA,
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace").strip()
    except urllib.error.HTTPError as exc:
        raise ZoteroUnavailable(f"HTTP {exc.code} from {url}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ZoteroUnavailable(f"{type(exc).__name__}: {exc}") from exc


def _base(base_url: Optional[str]) -> str:
    return (base_url or DEFAULT_LOCAL_API).rstrip("/")


def probe(base_url: Optional[str] = None, *, timeout: float = PROBE_TIMEOUT,
          user: str = DEFAULT_USER) -> Optional[str]:
    """探测 Zotero 本地 API。

    可达 → 返回 `Zotero-Server-ID`；不可达 → 返回 None（**不抛异常**）。
    这是"默认用 Zotero、不可用则回落 refs"这条规则的判定入口。
    """
    url = f"{_base(base_url)}/users/{user}/items?limit=1"
    request = urllib.request.Request(url, headers={
        "Zotero-API-Version": "3", "User-Agent": UA,
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.headers.get(STATUS_HEADER)
    except Exception:  # noqa: BLE001 —— 任何失败都只表示"不可用"
        return None


def fetch_items(base_url: Optional[str] = None, *, timeout: float = FETCH_TIMEOUT,
                user: str = DEFAULT_USER, top_only: bool = False) -> List[Dict[str, Any]]:
    """拉取条目（含子条目）。

    返回 Local API 的原始 item 列表，每项形如
    `{"key": ..., "version": ..., "data": {...}}`。

    Raises:
        ZoteroUnavailable: 地址不通或返回非 JSON。调用方必须回落 refs。
    """
    path = "items/top" if top_only else "items"
    url = f"{_base(base_url)}/users/{user}/{path}?format=json"
    payload = _get_json(url, timeout=timeout)
    if not isinstance(payload, list):
        raise ZoteroUnavailable("Local API did not return a JSON array of items")
    return [item for item in payload if isinstance(item, dict) and isinstance(item.get("data"), dict)]


# ---------------------------------------------------------------------------
# 单对象读取原语（P3/P4 依赖；均为只读）
# ---------------------------------------------------------------------------

def api_root(base_url: Optional[str] = None, *, timeout: float = PROBE_TIMEOUT,
             user: str = DEFAULT_USER) -> Optional[Dict[str, Any]]:
    """`GET /api/` —— 返回 `{"api_version", "schema_version", "server_id"}`；不可达返回 None。"""
    request = urllib.request.Request(
        f"{_base(base_url)}/", headers={"Zotero-API-Version": "3", "User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            headers = dict(response.headers)
            response.read()
    except Exception:  # noqa: BLE001
        return None
    return {
        "api_version": headers.get("Zotero-API-Version"),
        "schema_version": headers.get("Zotero-Schema-Version"),
        "server_id": headers.get(STATUS_HEADER),
    }


def get_item(key: str, *, base_url: Optional[str] = None, timeout: float = HTTP_TIMEOUT,
             user: str = DEFAULT_USER) -> Optional[Dict[str, Any]]:
    """按 key 读取单个条目；不存在返回 None。"""
    if not key:
        return None
    try:
        payload = _get_json(f"{_base(base_url)}/users/{user}/items/{key}", timeout=timeout)
    except ZoteroUnavailable:
        raise
    return payload if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else None


def get_children(key: str, *, base_url: Optional[str] = None, timeout: float = HTTP_TIMEOUT,
                 user: str = DEFAULT_USER) -> List[Dict[str, Any]]:
    """`GET /items/{key}/children` —— 子条目（附件 / 笔记 / 标注）。"""
    payload = _get_json(f"{_base(base_url)}/users/{user}/items/{key}/children?format=json",
                        timeout=timeout)
    if not isinstance(payload, list):
        return []
    return [i for i in payload if isinstance(i, dict) and isinstance(i.get("data"), dict)]


def search_items(query: str, *, base_url: Optional[str] = None, qmode: str = "everything",
                 limit: Optional[int] = None, timeout: float = FETCH_TIMEOUT,
                 user: str = DEFAULT_USER) -> List[Dict[str, Any]]:
    """`GET /items?q=...&qmode=everything` —— Zotero 索引检索。

    ★ 实测：同一命中会**同时**返回附件与其父条目。调用方必须按
    `data.parentItem` 归并回论文，否则会重复计数。
    """
    params = {"q": query, "qmode": qmode, "format": "json"}
    if limit:
        params["limit"] = str(limit)
    url = f"{_base(base_url)}/users/{user}/items?" + urllib.parse.urlencode(params)
    payload = _get_json(url, timeout=timeout)
    if not isinstance(payload, list):
        return []
    return [i for i in payload if isinstance(i, dict) and isinstance(i.get("data"), dict)]


def item_fulltext(attachment_key: str, *, base_url: Optional[str] = None,
                  timeout: float = HTTP_TIMEOUT,
                  user: str = DEFAULT_USER) -> Optional[Dict[str, Any]]:
    """`GET /items/{attachmentKey}/fulltext` → `{content, indexedPages, totalPages}`。

    ★ `content` 是**扁平文本，没有页码边界**。它只能作为检索资料，
    **不得**据此声称页码级证据（页码必须来自真实 PDF 解析）。
    附件未建索引时返回 None。
    """
    if not attachment_key:
        return None
    try:
        payload = _get_json(f"{_base(base_url)}/users/{user}/items/{attachment_key}/fulltext",
                            timeout=timeout)
    except ZoteroUnavailable:
        return None
    if not isinstance(payload, dict):
        return None
    return {
        "content": payload.get("content") or "",
        "indexedPages": payload.get("indexedPages"),
        "totalPages": payload.get("totalPages"),
    }


def fulltext_versions(base_url: Optional[str] = None, *, since: int = 0,
                      timeout: float = FETCH_TIMEOUT,
                      user: str = DEFAULT_USER) -> Dict[str, int]:
    """`GET /fulltext?since=N` → `{attachmentKey: <int>}`（索引版本快照）。

    用于增量判断哪些附件全文索引发生了变化。不可达时返回空 dict。
    """
    url = f"{_base(base_url)}/users/{user}/fulltext?" + urllib.parse.urlencode(
        {"since": str(since), "format": "json"})
    try:
        payload = _get_json(url, timeout=timeout)
    except ZoteroUnavailable:
        return {}
    return {str(k): int(v) for k, v in payload.items()} if isinstance(payload, dict) else {}


def file_view_url(attachment_key: str, *, base_url: Optional[str] = None,
                  timeout: float = HTTP_TIMEOUT,
                  user: str = DEFAULT_USER) -> Optional[str]:
    """`GET /items/{attachmentKey}/file/view/url` → 本地 `file://` URL（不可用返回 None）。

    只接受 `file://` 结果。**不跟随 http(s)**，避免附件地址触发非预期网络请求。
    """
    if not attachment_key:
        return None
    try:
        text = _get_text(f"{_base(base_url)}/users/{user}/items/{attachment_key}/file/view/url",
                         timeout=timeout)
    except ZoteroUnavailable:
        return None
    return text if text.startswith("file://") else None


def file_url_to_path(url: str) -> Optional[str]:
    """`file://` URL → 本地路径。拒绝非 file 协议。"""
    if not url or not url.startswith("file://"):
        return None
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "file":
        return None
    return urllib.request.url2pathname(parsed.path)


def local_attachment_path(attachment: Dict[str, Any], *, storage_dir: Optional[str] = None,
                          base_url: Optional[str] = None) -> Optional[str]:
    """解析附件的本地文件路径。

    顺序：Local API 的 `file/view/url`（**优先**，因为用户可能用第三方云盘，
    PDF 不一定在 `~/Zotero/storage/`）→ `storage/<key>/<filename>` 回退。
    返回 None 表示文件不可访问。**不移动、不重命名、不删除任何文件。**
    """
    data = attachment.get("data") or {}
    key = attachment.get("key") or data.get("key") or ""
    url = file_view_url(key, base_url=base_url)
    path = file_url_to_path(url) if url else None
    if path and os.path.isfile(path):
        return path

    filename = data.get("filename")
    if key and filename:
        root = storage_dir or os.path.join(os.path.expanduser("~"), "Zotero", "storage")
        candidate = os.path.join(root, key, filename)
        if os.path.isfile(candidate):
            return candidate
    return None


# ---------------------------------------------------------------------------
# 映射
# ---------------------------------------------------------------------------

def is_bibliographic(item: Dict[str, Any]) -> bool:
    """是否可引用条目（非附件 / 笔记 / 标注）。"""
    return (item.get("data") or {}).get("itemType") not in _CHILD_TYPES


def bibliographic_items(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """只保留顶层可引用条目（有 `parentItem` 的是子条目）。"""
    return [i for i in items
            if is_bibliographic(i) and not (i.get("data") or {}).get("parentItem")]


def pdf_children(items: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """父条目 key → 其 PDF 附件列表。"""
    out: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        data = item.get("data") or {}
        if data.get("itemType") != "attachment":
            continue
        if data.get("contentType") != "application/pdf":
            continue
        parent = data.get("parentItem")
        if parent:
            out.setdefault(parent, []).append(item)
    return out


def item_to_record(item: Dict[str, Any]) -> Dict[str, Any]:
    """映射到文献合并层要求的 record 形状。

    `sources` 固定为 `["local"]`：Zotero 属于本地文献库，
    `literature-policy` §1.1 Step 1 规定本地命中标注 `local`。
    """
    data = item.get("data") or {}
    return {
        "title": _clean(data.get("title")),
        "authors": _authors(data),
        "abstract": _clean(data.get("abstractNote")),
        "year": _year(data.get("date")),
        "venue": _venue(data),
        "url": _clean(data.get("url")),
        "doi": normalize_doi(data.get("DOI")),
        "arxiv_id": arxiv_id(data),
        "openalex_id": None,
        "cited_by_count": None,
        "references": [],
        "keywords": _keywords(data),
        "sources": ["local"],
        "zotero_key": item.get("key"),
    }


def item_to_sidecar(item: Dict[str, Any], *, file: Optional[str] = None,
                    sha256: Optional[str] = None,
                    size_bytes: Optional[int] = None,
                    notes_path: Optional[str] = None) -> Dict[str, Any]:
    """映射到 `docs/refs/` sidecar（§7.1 字段子集 + paper_id）。"""
    data = item.get("data") or {}
    title = _clean(data.get("title"))
    year = _year(data.get("date"))
    key = item.get("key")
    return {
        "paper_id": arxiv_id(data) or normalize_doi(data.get("DOI")) or key,
        "zotero_key": key,
        "title": title,
        "authors": _authors(data),
        "year": year,
        "venue": _venue(data),
        "arxiv_id": arxiv_id(data),
        "doi": normalize_doi(data.get("DOI")),
        "url": _clean(data.get("url")),
        "abstract": _clean(data.get("abstractNote")),
        "keywords": _keywords(data),
        "file": file,
        "size_bytes": size_bytes,
        "sha256": sha256,
        "added_at": (_clean(data.get("dateAdded")) or "")[:10] or None,
        "source": "zotero",
        "metadata_from": "zotero",
        "needs_verification": bool(not title or year is None),
        "notes_path": notes_path,
    }


# ---------------------------------------------------------------------------
# 自检 CLI
# ---------------------------------------------------------------------------

def _main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Zotero Local API 只读客户端自检")
    parser.add_argument("--base-url", default=None, help=f"默认 {DEFAULT_LOCAL_API}")
    parser.add_argument("--probe", action="store_true", help="只探测可达性")
    parser.add_argument("--dump-records", type=int, default=0,
                        metavar="N", help="打印 N 条映射后的 record")
    args = parser.parse_args(argv)

    base = _base(args.base_url)
    server_id = probe(base)
    if not server_id:
        print(f"Zotero 不可达：{base}", file=sys.stderr)
        return 4
    print(f"Zotero 可达：{base}（Server-ID {server_id}）")

    if args.probe:
        return 0

    try:
        items = fetch_items(base)
    except ZoteroUnavailable as exc:
        print(f"拉取失败：{exc}", file=sys.stderr)
        return 4

    bib = bibliographic_items(items)
    print(f"全部条目 {len(items)}，可引用 {len(bib)}")
    for item in bib[: max(args.dump_records, 0)]:
        print(json.dumps(item_to_record(item), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
