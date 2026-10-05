#!/usr/bin/env python3
"""literature_sources.py — 多源文献检索适配器

三个源**互补，不是等价替换**：

    arxiv     管「新」  预印本，比索引快 6–12 个月
    openalex  管「关系」引文图（前向 `cites:` / 后向 `referenced_works`）+ venue 过滤
    crossref  管「出处」正式 venue 权威（会议/期刊全称、DOI、卷期）

被排除的源及其原因（实测，见 commit 说明）：
    DBLP               dblp.org 上线 Anubis JS 挑战，带浏览器 UA 也挡 → 程序化不可用
    Semantic Scholar   无 API key 时直接 429（共享池已满）→ 留待用户提供 key

统一记录格式（归一化后）
------------------------
    {
      "title": str, "authors": [str], "abstract": str|None, "year": int|None,
      "venue": str|None, "url": str|None, "doi": str|None, "arxiv_id": str|None,
      "openalex_id": str|None, "cited_by_count": int|None,
      "references": [str], "keywords": [str], "sources": [str]
    }

`source`（单值）保留为 `sources[0]` 的**派生别名**，只为兼容既有 sidecar 与渲染代码。

退出码不由此模块决定，由调用方按 `SourceOutcome.state` 汇总。
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

#: 源的权威序：venue 字段冲突时取靠前的
VENUE_AUTHORITY: Tuple[str, ...] = ("crossref", "openalex", "arxiv", "local")

#: 默认启用全部已实现的源（literature-policy.md §9.1：尽可能多）
DEFAULT_SOURCES: Tuple[str, ...] = ("arxiv", "openalex", "crossref")

HTTP_TIMEOUT = 30.0
RETRY_BASE = 3.0          # 秒
ARXIV_POLITE_DELAY = 3.0  # arXiv API 的礼貌间隔（秒）
ARXIV_MAX_RETRIES = 5     # 429 退避：10 → 20 → 40 → 80 → 160 秒
ARXIV_BASE_WAIT = 10.0

#: 只认"看起来像 HTTP 状态"的文本（要求 status/code/http 前缀），
#: 否则 "paper 2401.429 missing" 这类无关数字会触发 5 轮共 310 秒的假退避。
_STATUS_TEXT_RE = re.compile(r"(?:status|code|http)[^0-9]{0,12}(\d{3})", re.IGNORECASE)

_UA = "research-idea-pipeline/1.3 (+https://github.com/Zolento/myskills)"
_DOI_RE = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
_ARXIV_ID_RE = re.compile(r"\b(\d{4}\.\d{4,5})(v\d+)?\b")
_ARXIV_OLD_RE = re.compile(r"\b([a-z-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?\b")
_OA_ID_RE = re.compile(r"\b(W\d{6,})\b")
_TITLE_KEY_RE = re.compile(r"[^0-9a-z\u4e00-\u9fff]+")
#: OpenAlex 会把 arXiv 仓库本身当作 source，那不是"发表 venue"
_NOT_A_VENUE_RE = re.compile(r"^arxiv\b", re.IGNORECASE)

_last_request: Dict[str, float] = {}


# ---------------------------------------------------------------------------
# 小型工具
# ---------------------------------------------------------------------------

def normalize_doi(value: Optional[str]) -> Optional[str]:
    """归一化 DOI：去掉 `doi:` / URL 前缀与大小写差异。"""
    if not value:
        return None
    text = str(value).strip()
    text = re.sub(r"^(doi:|https?://(dx\.)?doi\.org/)", "", text, flags=re.IGNORECASE)
    text = text.strip()
    match = _DOI_RE.search(text)
    return match.group(0).rstrip(".").lower() if match else (text.lower() or None)


def normalize_arxiv_id(value: Optional[str]) -> Optional[str]:
    """归一化 arXiv ID：去掉版本号与 URL 前缀。"""
    if not value:
        return None
    text = str(value).strip()
    text = re.sub(r"^https?://arxiv\.org/(abs|pdf)/", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\.pdf$", "", text)
    match = _ARXIV_ID_RE.search(text) or _ARXIV_OLD_RE.search(text.lower())
    return match.group(1) if match else None


def normalize_openalex_id(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    match = _OA_ID_RE.search(str(value))
    return match.group(1) if match else None


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if value is None:
        return None
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _year(value: Any) -> Optional[int]:
    if isinstance(value, int):
        return value
    if not value:
        return None
    match = re.search(r"(19|20)\d{2}", str(value))
    return int(match.group(0)) if match else None


def _title_key(title: Optional[str], year: Optional[int]) -> Optional[str]:
    if not title:
        return None
    key = _TITLE_KEY_RE.sub("", str(title).lower())
    return f"t:{key}:{year or ''}" if len(key) >= 8 else None


def _http_status(exc: BaseException) -> Optional[int]:
    """从异常里尽力提取 HTTP 状态码（arxiv 包并不稳定导出 HTTPError）。"""
    for attr in ("status", "status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None) if response is not None else None
    if isinstance(status, int):
        return status
    match = _STATUS_TEXT_RE.search(str(exc))
    return int(match.group(1)) if match else None


def _polite_wait(source: str, delay: float) -> None:
    """同一源的两次请求之间至少间隔 delay 秒（arXiv 的礼貌要求）。"""
    if delay <= 0:
        return
    last = _last_request.get(source)
    now = time.monotonic()
    if last is not None:
        remaining = delay - (now - last)
        if remaining > 0:
            time.sleep(remaining)
    _last_request[source] = time.monotonic()


def http_get_json(
    url: str,
    *,
    source: str,
    log,
    retries: int = 3,
    base_wait: float = RETRY_BASE,
) -> Any:
    """GET + JSON 解析，带指数退避。

    Raises:
        RuntimeError: 重试耗尽。
    """
    last_error: Optional[BaseException] = None
    for attempt in range(retries):
        request = urllib.request.Request(url, headers={
            "User-Agent": _UA,
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in (429, 403, 503) and attempt < retries - 1:
                wait = base_wait * (2 ** attempt)
                log(f"[{source}] HTTP {exc.code}，等待 {wait:.0f}s 后重试"
                    f"（第 {attempt + 1} 次）")
                time.sleep(wait)
                continue
            raise RuntimeError(f"{source} HTTP {exc.code}: {exc.reason}") from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = exc
            if attempt < retries - 1:
                wait = base_wait * (2 ** attempt)
                log(f"[{source}] 请求失败（{exc}），等待 {wait:.0f}s 后重试")
                time.sleep(wait)
                continue
            raise RuntimeError(f"{source} 请求失败：{exc}") from exc
    raise RuntimeError(f"{source} 重试耗尽：{last_error}")


# ---------------------------------------------------------------------------
# 源协议
# ---------------------------------------------------------------------------

@dataclass
class SourceOutcome:
    """一次源调用的结果。state 决定退出码与饱和计数（见 literature_search.py）。"""

    name: str
    state: str = "skipped"          # ok | partial | unavailable | skipped
    hits: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.state in ("ok", "partial")


class Source:
    """文献源基类。子类至少实现 `search`。"""

    name: str = "base"
    label: str = ""
    hosts: Tuple[str, ...] = ()
    requires: Tuple[str, ...] = ()
    polite_delay: float = 0.0

    def search(
        self,
        query: str,
        *,
        max_results: int,
        from_year: Optional[int],
        to_year: Optional[int],
        log,
        mailto: Optional[str] = None,
        venue_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name, "label": self.label,
            "hosts": list(self.hosts), "requires": list(self.requires),
        }


# ---------------------------------------------------------------------------
# arXiv —— 管「新」
# ---------------------------------------------------------------------------

class ArxivSource(Source):
    name = "arxiv"
    label = "arXiv（预印本，最新工作）"
    hosts = ("arxiv.org", "export.arxiv.org")
    requires = ("arxiv",)
    polite_delay = ARXIV_POLITE_DELAY

    def search(self, query, *, max_results, from_year, to_year, log,
               mailto=None, venue_id=None):
        self._polite_wait(log)
        try:
            return self._via_package(query, max_results, from_year, to_year, log)
        except ImportError:
            log("[arxiv] 未安装 arxiv 包，改用 Atom HTTP 接口")
            return self._via_atom(query, max_results, from_year, to_year, log)

    def _polite_wait(self, log) -> None:
        if self.polite_delay:
            _polite_wait(self.name, self.polite_delay)

    def _via_package(self, query, max_results, from_year, to_year, log):
        """Python 包路径。★ 必须保留 429 指数退避（literature-policy.md §6）。"""
        import arxiv  # type: ignore  # 缺包时抛 ImportError，由 search() 兜底

        last_error: Optional[BaseException] = None
        for attempt in range(ARXIV_MAX_RETRIES):
            try:
                client = arxiv.Client()
                search = arxiv.Search(
                    query=query, max_results=max_results,
                    sort_by=arxiv.SortCriterion.Relevance,
                )
                records: List[Dict[str, Any]] = []
                for paper in client.results(search):
                    year = getattr(paper.published, "year", None)
                    if not _in_range(year, from_year, to_year):
                        continue
                    records.append({
                        "title": _clean(paper.title),
                        "authors": [str(a.name) for a in (paper.authors or [])],
                        "abstract": _clean(paper.summary),
                        "year": year,
                        "venue": None,   # ★ arxiv 元数据不含会议信息
                        "url": paper.entry_id,
                        "doi": normalize_doi(paper.doi),
                        "arxiv_id": normalize_arxiv_id(paper.get_short_id() or paper.entry_id),
                        "openalex_id": None,
                        "cited_by_count": None,
                        "references": [],
                        "keywords": list(paper.categories or []),
                        "sources": [self.name],
                    })
                return records
            except Exception as exc:  # noqa: BLE001 — 需要按状态码分流
                last_error = exc
                if _http_status(exc) == 429 and attempt < ARXIV_MAX_RETRIES - 1:
                    wait = ARXIV_BASE_WAIT * (2 ** attempt)
                    log(f"[429] 限流，等待 {wait:.0f}s 后重试（第 {attempt + 1} 次）")
                    # 退避期间不发起任何新的 arXiv 请求
                    time.sleep(wait)
                    continue
                raise
        raise RuntimeError(f"arxiv 重试次数耗尽：{last_error}")

    def _via_atom(self, query, max_results, from_year, to_year, log):
        """不依赖 Python 包的回退：arXiv 原生 Atom 接口。"""
        # ★ 必须先过礼貌间隔，否则连续查询会触发 arXiv 的限速
        params = urllib.parse.urlencode({
            "search_query": f'all:"{query}"',
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
        })
        url = f"https://export.arxiv.org/api/query?{params}"
        request = urllib.request.Request(url, headers={"User-Agent": _UA})
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
                raw = response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"arxiv Atom 接口失败：{exc}") from exc

        ns = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(raw)
        records: List[Dict[str, Any]] = []
        for entry in root.findall("a:entry", ns):
            published = entry.findtext("a:published", default="", namespaces=ns)
            year = _year(published)
            if not _in_range(year, from_year, to_year):
                continue
            entry_id = entry.findtext("a:id", default="", namespaces=ns)
            records.append({
                "title": _clean(entry.findtext("a:title", default="", namespaces=ns)),
                "authors": [a.text for a in entry.findall("a:author/a:name", ns) if a.text],
                "abstract": _clean(entry.findtext("a:summary", default="", namespaces=ns)),
                "year": year,
                "venue": None,
                "url": entry_id,
                "doi": None,
                "arxiv_id": normalize_arxiv_id(entry_id),
                "openalex_id": None,
                "cited_by_count": None,
                "references": [],
                "keywords": [c.get("term") for c in entry.findall("a:category", ns)
                             if c.get("term")],
                "sources": [self.name],
            })
        return records


def _in_range(year: Optional[int], from_year: Optional[int], to_year: Optional[int]) -> bool:
    if year is None:
        return from_year is None and to_year is None
    if from_year is not None and year < from_year:
        return False
    if to_year is not None and year > to_year:
        return False
    return True


# ---------------------------------------------------------------------------
# OpenAlex —— 管「关系」
# ---------------------------------------------------------------------------

class OpenAlexSource(Source):
    name = "openalex"
    label = "OpenAlex（引文图 + venue 过滤）"
    hosts = ("api.openalex.org", "openalex.org")
    requires = ()
    polite_delay = 0.0

    API = "https://api.openalex.org"
    SELECT = ("id,doi,title,display_name,publication_year,primary_location,"
              "authorships,cited_by_count,referenced_works")

    def search(self, query, *, max_results, from_year, to_year, log,
               mailto=None, venue_id=None):
        filters: List[str] = []
        if from_year:
            filters.append(f"from_publication_date:{from_year}-01-01")
        if to_year:
            filters.append(f"to_publication_date:{to_year}-12-31")
        if venue_id:
            filters.append(f"primary_location.source.id:{venue_id}")
        params: Dict[str, Any] = {"search": query, "per-page": min(max_results, 200),
                                  "select": self.SELECT}
        if filters:
            params["filter"] = ",".join(filters)
        if mailto:
            params["mailto"] = mailto
        url = f"{self.API}/works?{urllib.parse.urlencode(params)}"
        payload = http_get_json(url, source=self.name, log=log)
        return [self._normalize(w) for w in payload.get("results", []) or []]

    def resolve_venue_id(self, name: str, *, log, mailto: Optional[str] = None) -> Optional[str]:
        """把会议/期刊名解析成 OpenAlex source ID（venue 过滤必须先解析）。"""
        params = {"search": name, "per-page": 5}
        if mailto:
            params["mailto"] = mailto
        url = f"{self.API}/sources?{urllib.parse.urlencode(params)}"
        payload = http_get_json(url, source=self.name, log=log)
        results = payload.get("results") or []
        return results[0]["id"].rsplit("/", 1)[-1] if results else None

    def resolve_work_id(self, identifier: str, *, log,
                        mailto: Optional[str] = None) -> Optional[str]:
        """把 DOI / arXiv ID / OpenAlex ID 解析成 OpenAlex work ID（引文追溯的入口）。"""
        text = (identifier or "").strip()
        if not text:
            return None
        direct = normalize_openalex_id(text)
        if direct and re.fullmatch(r"W\d{6,}", text.strip()):
            return direct

        doi = normalize_doi(text)
        if doi:
            params = {"select": "id"}
            if mailto:
                params["mailto"] = mailto
            url = f"{self.API}/works/doi:{urllib.parse.quote(doi)}?{urllib.parse.urlencode(params)}"
            try:
                payload = http_get_json(url, source=self.name, log=log)
                found = normalize_openalex_id(payload.get("id"))
                if found:
                    return found
            except RuntimeError:
                pass

        arxiv_id = normalize_arxiv_id(text)
        if arxiv_id:
            params = {"filter": f"locations.landing_page_url:http://arxiv.org/abs/{arxiv_id}",
                      "per-page": 1, "select": "id"}
            if mailto:
                params["mailto"] = mailto
            url = f"{self.API}/works?{urllib.parse.urlencode(params)}"
            payload = http_get_json(url, source=self.name, log=log)
            results = payload.get("results") or []
            return normalize_openalex_id(results[0].get("id")) if results else None
        return direct

    def cited_by(self, work_id: str, *, max_results: int, log,
                 mailto: Optional[str] = None) -> List[Dict[str, Any]]:
        """前向引文：谁引用了它。"""
        return self._by_filter(f"cites:{normalize_openalex_id(work_id) or work_id}",
                               max_results=max_results, log=log, mailto=mailto)

    def references_of(self, work_id: str, *, max_results: int, log,
                      mailto: Optional[str] = None) -> List[Dict[str, Any]]:
        """后向引文：它引用了谁。"""
        clean = normalize_openalex_id(work_id) or work_id
        url = f"{self.API}/works/{clean}?select=referenced_works"
        if mailto:
            url += f"&mailto={urllib.parse.quote(mailto)}"
        payload = http_get_json(url, source=self.name, log=log)
        ids = (payload.get("referenced_works") or [])[:max_results]
        if not ids:
            return []
        joined = "|".join(i.rsplit("/", 1)[-1] for i in ids)
        return self._by_filter(f"openalex_id:{joined}", max_results=max_results,
                               log=log, mailto=mailto)

    def _by_filter(self, expr: str, *, max_results: int, log,
                   mailto: Optional[str]) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"filter": expr, "per-page": min(max_results, 200),
                                  "select": self.SELECT}
        if mailto:
            params["mailto"] = mailto
        url = f"{self.API}/works?{urllib.parse.urlencode(params)}"
        payload = http_get_json(url, source=self.name, log=log)
        return [self._normalize(w) for w in payload.get("results", []) or []]

    def _normalize(self, work: Dict[str, Any]) -> Dict[str, Any]:
        location = work.get("primary_location") or {}
        source = location.get("source") or {}
        venue = _clean(source.get("display_name"))
        if venue and _NOT_A_VENUE_RE.match(venue):
            venue = None   # "arXiv (Cornell University)" 是托管仓库，不是发表 venue
        authors = [
            _clean((a.get("author") or {}).get("display_name"))
            for a in (work.get("authorships") or [])
        ]
        return {
            "title": _clean(work.get("display_name") or work.get("title")),
            "authors": [a for a in authors if a],
            "abstract": None,   # OpenAlex 有 abstract_inverted_index，此处不还原
            "year": _year(work.get("publication_year")),
            "venue": venue,
            "url": location.get("landing_page_url") or work.get("id"),
            "doi": normalize_doi(work.get("doi")),
            "arxiv_id": self._arxiv_from(location) or self._arxiv_from(work),
            "openalex_id": normalize_openalex_id(work.get("id")),
            "cited_by_count": work.get("cited_by_count"),
            "references": [normalize_openalex_id(r) or r
                           for r in (work.get("referenced_works") or [])],
            "keywords": [],
            "sources": [self.name],
        }

    @staticmethod
    def _arxiv_from(container: Dict[str, Any]) -> Optional[str]:
        """OpenAlex 的 arXiv 连接点：locations / landing_page_url 里的 arxiv.org 链接。"""
        candidates: List[str] = []
        for key in ("landing_page_url", "pdf_url", "id"):
            value = container.get(key)
            if isinstance(value, str):
                candidates.append(value)
        for loc in container.get("locations") or []:
            if isinstance(loc, dict):
                candidates.extend(
                    str(loc.get(k)) for k in ("landing_page_url", "pdf_url", "id")
                    if loc.get(k)
                )
        for text in candidates:
            if "arxiv" in text.lower():
                found = normalize_arxiv_id(text)
                if found:
                    return found
        return None


# ---------------------------------------------------------------------------
# CrossRef —— 管「出处」
# ---------------------------------------------------------------------------

class CrossrefSource(Source):
    name = "crossref"
    label = "CrossRef（正式 venue 权威）"
    hosts = ("api.crossref.org", "crossref.org")
    requires = ()
    polite_delay = 0.0

    API = "https://api.crossref.org/works"
    SELECT = "DOI,title,author,issued,container-title,type,URL,subject,abstract"

    def search(self, query, *, max_results, from_year, to_year, log,
               mailto=None, venue_id=None):
        params: Dict[str, Any] = {
            "query.bibliographic": query,
            "rows": min(max_results, 100),
            "select": self.SELECT,
        }
        filters: List[str] = []
        if from_year:
            filters.append(f"from-pub-date:{from_year}-01-01")
        if to_year:
            filters.append(f"until-pub-date:{to_year}-12-31")
        if filters:
            params["filter"] = ",".join(filters)
        if mailto:
            params["mailto"] = mailto
        url = f"{self.API}?{urllib.parse.urlencode(params)}"
        payload = http_get_json(url, source=self.name, log=log)
        items = (payload.get("message") or {}).get("items") or []
        return [self._normalize(i) for i in items]

    def _normalize(self, item: Dict[str, Any]) -> Dict[str, Any]:
        authors: List[str] = []
        for a in item.get("author") or []:
            given = _clean(a.get("given"))
            family = _clean(a.get("family"))
            name = " ".join(p for p in (given, family) if p) or _clean(a.get("name"))
            if name:
                authors.append(name)
        issued = ((item.get("issued") or {}).get("date-parts") or [[]])[0]
        year = issued[0] if issued else None
        return {
            "title": _clean(item.get("title")),
            "authors": authors,
            "abstract": _clean(item.get("abstract")),
            "year": _year(year),
            "venue": _clean(item.get("container-title")),
            "url": item.get("URL"),
            "doi": normalize_doi(item.get("DOI")),
            "arxiv_id": None,
            "openalex_id": None,
            "cited_by_count": None,
            "references": [],
            "keywords": [k for k in (item.get("subject") or []) if k],
            "sources": [self.name],
        }


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

REGISTRY: Dict[str, Source] = {
    "arxiv": ArxivSource(),
    "openalex": OpenAlexSource(),
    "crossref": CrossrefSource(),
}


def resolve_source_names(requested: Optional[str]) -> Tuple[List[str], List[str]]:
    """解析 --sources。返回 (启用列表, 未知项列表)。"""
    if not requested or requested.strip().lower() in ("all", "*"):
        return [n for n in DEFAULT_SOURCES if n in REGISTRY], []
    names: List[str] = []
    unknown: List[str] = []
    for raw in requested.split(","):
        name = raw.strip().lower()
        if not name:
            continue
        if name in REGISTRY:
            if name not in names:
                names.append(name)
        else:
            unknown.append(raw.strip())
    return names, unknown


def all_hosts(names: Sequence[str]) -> List[str]:
    hosts: List[str] = []
    for name in names:
        for host in REGISTRY[name].hosts:
            if host not in hosts:
                hosts.append(host)
    return hosts


# ---------------------------------------------------------------------------
# 合并层
# ---------------------------------------------------------------------------

def identity_keys(record: Dict[str, Any]) -> List[str]:
    """一条记录的全部身份键（用于跨源合并）。"""
    keys: List[str] = []
    doi = normalize_doi(record.get("doi"))
    if doi:
        keys.append("doi:" + doi)
    arxiv_id = normalize_arxiv_id(record.get("arxiv_id"))
    if arxiv_id:
        keys.append("arxiv:" + arxiv_id)
    oa = normalize_openalex_id(record.get("openalex_id"))
    if oa:
        keys.append("oa:" + oa)
    title_key = _title_key(record.get("title"), _year(record.get("year")))
    if title_key:
        keys.append(title_key)
    return keys


def _pick_venue(group: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    """venue 取权威序最靠前的非空值。返回 (venue, venue_from)。"""
    for source in VENUE_AUTHORITY:
        for record in group:
            if source in (record.get("sources") or []) and record.get("venue"):
                return record["venue"], source
    for record in group:
        if record.get("venue"):
            return record["venue"], (record.get("sources") or [None])[0]
    return None, None


def _best(group: List[Dict[str, Any]], key: str) -> Any:
    for record in group:
        if record.get(key) not in (None, "", [], {}):
            return record[key]
    return None


def _best_authors(group: List[Dict[str, Any]]) -> List[str]:
    """作者取**最长**的非空列表（不同源裁剪程度不同，最长的最完整）。"""
    best: List[str] = []
    for record in group:
        value = record.get("authors")
        if isinstance(value, list) and len(value) > len(best):
            best = [str(a) for a in value if a]
    return best


def merge_records(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """跨源合并：同一篇论文只留一条，`sources` 取并集，`venue` 取权威序。

    身份判定用并查集，因为一条记录可能"按 DOI 匹配 A、按标题匹配 B"。
    """
    items = [dict(r) for r in records if isinstance(r, dict) and r.get("title")]
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    seen: Dict[str, int] = {}
    for index, record in enumerate(items):
        for key in identity_keys(record):
            if key in seen:
                union(index, seen[key])
            else:
                seen[key] = index

    groups: Dict[int, List[Dict[str, Any]]] = {}
    for index, record in enumerate(items):
        groups.setdefault(find(index), []).append(record)

    merged: List[Dict[str, Any]] = []
    for group in groups.values():
        sources: List[str] = []
        for record in group:
            for source in record.get("sources") or []:
                if source not in sources:
                    sources.append(source)
        sources.sort(key=lambda s: VENUE_AUTHORITY.index(s)
                     if s in VENUE_AUTHORITY else len(VENUE_AUTHORITY))
        venue, venue_from = _pick_venue(group)
        item = {
            "title": _best(group, "title"),
            "authors": _best_authors(group),
            "abstract": _best(group, "abstract"),
            "year": _best(group, "year"),
            "venue": venue,
            "venue_from": venue_from,
            "url": _best(group, "url"),
            "doi": normalize_doi(_best(group, "doi")),
            "arxiv_id": normalize_arxiv_id(_best(group, "arxiv_id")),
            "openalex_id": normalize_openalex_id(_best(group, "openalex_id")),
            "cited_by_count": _best(group, "cited_by_count"),
            "references": _best(group, "references") or [],
            "keywords": _best(group, "keywords") or [],
            "sources": sources,
            "source": sources[0] if sources else None,   # 派生别名，兼容旧消费方
        }
        merged.append(item)
    return merged


def dedup_key(record: Dict[str, Any]) -> str:
    """稳定的去重键（用于"新增了几条"的判定）。"""
    keys = identity_keys(record)
    return keys[0] if keys else (_clean(record.get("title")) or "").lower()
