#!/usr/bin/env python3
"""Zotero 按需深读（deep_read）+ 证据锚点 —— `zotero_deepread.py`。

设计目标（见 [zotero-local-api.md](../references/zotero-local-api.md) 与 references 的既有政策）：

1. **只按需加载。** 绝不整库深读。解析顺序固定为
   `目标 → 元数据 → 笔记 → 可用性 → 只取需要的 section / page → 定位证据 → 结构化 → 定级`。
2. **只用既有证据政策。** 证据等级与措辞一律查
   [../references/evidence-policy.md](../references/evidence-policy.md)；
   本模块不新立等级、不新立 novelty reviewer、不改 `LIT<n>` 语义。
3. **验证纪律（本模块的核心正确性属性）：**
   - Zotero 索引命中的等级**永远**是 `indexed_fulltext`，**不得**升级为 `page_verified`；
   - `page_verified` 只来自**真实 PDF 页面**抽取出的文本，且必须能指到具体页；
   - 有 PDF ≠ 深读过。只用摘要时结果**必须**是 `abstract_only` 并写明；
   - 不完整 / 扫描件**必须**报 `insufficient_evidence`，并写明覆盖范围，**绝不**编造。
4. **不扩张 Research State Schema。** 本模块产物只提供证据锚点，供既有 Evidence Contract 消费。

依赖说明：`zotero_fulltext.py` 由其它子代理并行实现，因此本模块**惰性导入**它；
缺失时依次回退到 `zotero_client.item_fulltext`（拿到 `indexed_fulltext`）
与本模块内建的最小 pypdf 页级抽取（拿 `page_verified`）。两条回退都不可用时，
如实报告「页级抽取不可用」，**不崩溃**。
"""
from __future__ import annotations

import hashlib
import html
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zotero_client as zc  # noqa: E402  （只读原语；本模块**不修改**它）

__all__ = [
    "VERIFICATION_LEVELS",
    "DEEPREAD_MODES",
    "SECTIONS",
    "COMPARE_ASPECTS",
    "DEFAULT_BUDGET",
    "make_evidence_anchor",
    "deep_read",
    "compare_papers",
]

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

#: 验证等级（逐字取自 architecture.md §3.4；**顺序即强度**，`insufficient_evidence` 正交）。
VERIFICATION_LEVELS: Tuple[str, ...] = (
    "metadata_only",
    "abstract_only",
    "indexed_fulltext",
    "pdf_text_verified",
    "page_verified",
    "insufficient_evidence",
)

#: 可排序的强度阶梯；`insufficient_evidence` 不参与排序（视为最低可信）。
_LEVEL_RANK: Dict[str, int] = {
    "metadata_only": 0,
    "abstract_only": 1,
    "indexed_fulltext": 2,
    "pdf_text_verified": 3,
    "page_verified": 4,
}

#: 深读模式：A 概览 / B 章节 / C 证据 / D 对比 / E 新颖性（复用既有词表，不做裁决）。
DEEPREAD_MODES: Tuple[str, ...] = ("overview", "section", "evidence", "compare", "novelty")

#: 可定位的章节（逐字）。
SECTIONS: Tuple[str, ...] = (
    "abstract",
    "introduction",
    "related",
    "method",
    "theory",
    "experiments",
    "limitations",
)

#: `compare_papers` 的对比维度。
COMPARE_ASPECTS: Tuple[str, ...] = (
    "method",
    "assumptions",
    "theory",
    "experimental_setup",
)

#: 默认文本预算（字符）：限制一次深读读入的正文量，避免整篇无界加载。
DEFAULT_BUDGET = 20000

#: aspect → 需要抽取的章节。
_ASPECT_SECTIONS: Dict[str, Tuple[str, ...]] = {
    "method": ("method",),
    "assumptions": ("method", "theory"),
    "theory": ("theory",),
    "experimental_setup": ("experiments",),
}

# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _strip_html(raw: str) -> str:
    """Zotero note 是 HTML；只取纯文本。"""
    if not raw:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", html.unescape(text)).strip()


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-]{1,}")

_STOPWORDS = frozenset({
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "with", "is", "are",
    "was", "were", "be", "been", "this", "that", "these", "those", "it", "its", "as",
    "by", "at", "from", "we", "our", "their", "they", "does", "do", "did", "what",
    "which", "how", "why", "when", "where", "used", "use", "using", "paper", "method",
    "approach", "proposed",
})


def _tokens(text: str) -> List[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")]


def _content_tokens(text: str) -> set:
    return {t for t in _tokens(text) if t not in _STOPWORDS and len(t) > 1}


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])|\n+")


def _sentences(text: str) -> List[str]:
    out: List[str] = []
    for raw in _SENTENCE_RE.split(text or ""):
        s = re.sub(r"\s+", " ", raw).strip()
        if len(s) >= 20:
            out.append(s)
    return out


def _sha256_file(path: str) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


# ---------------------------------------------------------------------------
# 章节切分（页级 / 扁平索引级）
# ---------------------------------------------------------------------------

#: 章节标题别名（小写、已去掉编号后做 fullmatch）。
_SECTION_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "abstract": (r"abstract", r"summary"),
    "introduction": (r"introduction",),
    "related": (r"related work", r"related works", r"background", r"literature review"),
    "method": (r"method", r"methods", r"methodology", r"approach", r"proposed method",
               r"our method", r"proposed approach", r"model"),
    "theory": (r"theory", r"theoretical analysis", r"theoretical background",
               r"preliminaries", r"analysis"),
    "experiments": (r"experiment", r"experiments", r"experimental setup",
                    r"experimental evaluation", r"evaluation", r"results",
                    r"experiments and results"),
    "limitations": (r"limitation", r"limitations", r"discussion", r"failure cases",
                    r"failure case", r"threats to validity"),
}

_NUMBER_PREFIX_RE = re.compile(r"^\s*(?:\d+(?:\.\d+)*|[IVXLC]+)[.)]?\s+", re.IGNORECASE)


def _detect_heading(line: str) -> Optional[str]:
    """把一行判定为章节标题；不是标题返回 None。"""
    stripped = (line or "").strip()
    if not stripped or len(stripped) > 90:
        return None
    core = stripped.rstrip(":：.").strip()
    core = _NUMBER_PREFIX_RE.sub("", core).strip()
    core = re.sub(r"\s+", " ", core).lower()
    if not core or len(core) > 60:
        return None
    for name, patterns in _SECTION_PATTERNS.items():
        for pattern in patterns:
            if re.fullmatch(pattern, core):
                return name
    return None


def _segment_pages(pages: Sequence[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """把页文本切成 `sections` 与有序 `spans`。

    `spans` 形如 `{"section": name|None, "page": int|None, "text": str}`；
    证据搜索走 `spans`，因此能同时给出 section 与 page。
    """
    sections: Dict[str, Any] = {}
    spans: List[Dict[str, Any]] = []
    current: Optional[str] = None
    buffer: List[str] = []

    def flush(page_no: Optional[int]) -> None:
        nonlocal buffer
        text = "\n".join(buffer).strip()
        buffer = []
        if text:
            spans.append({"section": current, "page": page_no, "text": text})

    for page in pages:
        page_no = page.get("page")
        for line in (page.get("text") or "").splitlines():
            heading = _detect_heading(line)
            if heading:
                flush(page_no)
                current = heading
                record = sections.setdefault(heading, {
                    "found": True, "source": "pdf_page", "page": page_no,
                    "pages": [], "lines": [],
                })
                if record["page"] is None:
                    record["page"] = page_no
                if page_no not in record["pages"]:
                    record["pages"].append(page_no)
                continue
            if line.strip():
                if current:
                    record = sections[current]
                    if page_no not in record["pages"]:
                        record["pages"].append(page_no)
                    record["lines"].append(line)
                buffer.append(line)
        flush(page_no)

    for record in sections.values():
        record["text"] = "\n".join(record.pop("lines", [])).strip()
    return sections, spans


def _segment_flat(content: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """索引全文是扁平文本、**没有页码边界** → section 有、page 恒为 None。"""
    sections: Dict[str, Any] = {}
    spans: List[Dict[str, Any]] = []
    current: Optional[str] = None
    buffer: List[str] = []

    def flush() -> None:
        nonlocal buffer
        text = "\n".join(buffer).strip()
        buffer = []
        if text:
            spans.append({"section": current, "page": None, "text": text})

    for line in (content or "").splitlines():
        heading = _detect_heading(line)
        if heading:
            flush()
            current = heading
            record = sections.setdefault(heading, {
                "found": True, "source": "indexed_fulltext", "page": None,
                "pages": [], "lines": [],
            })
            continue
        if line.strip():
            if current:
                sections[current]["lines"].append(line)
            buffer.append(line)
    flush()

    for record in sections.values():
        record["text"] = "\n".join(record.pop("lines", [])).strip()
    return sections, spans


# ---------------------------------------------------------------------------
# 只读桥接：兼容 WriteClient / 自定义 client / 裸 base_url
# ---------------------------------------------------------------------------


def _zotero_fulltext():
    """惰性导入并行开发的 `zotero_fulltext`；不可用返回 None。"""
    try:
        import zotero_fulltext  # type: ignore
    except Exception:  # noqa: BLE001 —— 缺失不是错误，是降级条件
        return None
    return zotero_fulltext


def _extract_pages_pypdf(pdf_path: str) -> Optional[Dict[str, Any]]:
    """内建最小 PDF 页级抽取（`zotero_fulltext` 缺失时的回退）。

    只依赖既有 `pypdf`。失败返回 None —— 调用方必须按「页级抽取不可用」处理。
    """
    if not pdf_path or not os.path.isfile(pdf_path):
        return None
    try:
        from pypdf import PdfReader
    except Exception:  # noqa: BLE001
        return None
    try:
        reader = PdfReader(pdf_path)
        total = len(reader.pages)
    except Exception:  # noqa: BLE001
        return None

    pages: List[Dict[str, Any]] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:  # noqa: BLE001
            text = ""
        pages.append({
            "page": index,
            "printed_page": index,
            "text": text,
            "quality": "good" if text else "empty",
        })
    return {
        "sha256": _sha256_file(pdf_path),
        "num_pages": total,
        "total_pages": total,
        "pages": pages,
    }


class _Bridge:
    """把「client 对象 / 裸 base_url」统一成只读调用面。

    优先级：**client 自身的方法**（便于测试注入）→ `zotero_fulltext` → `zotero_client`。
    """

    def __init__(self, client: Any):
        if isinstance(client, str):
            self._client: Any = None
            self.base_url: Optional[str] = client or None
        else:
            self._client = client
            base = getattr(client, "base_url", None) or getattr(client, "base", None)
            self.base_url = _clean(base)

    # -- 元数据 ----------------------------------------------------------

    def get_item(self, key: str) -> Optional[Dict[str, Any]]:
        fn = getattr(self._client, "get_item", None)
        if callable(fn):
            return fn(key)
        return zc.get_item(key, base_url=self.base_url)

    def get_children(self, key: str) -> List[Dict[str, Any]]:
        fn = getattr(self._client, "get_children", None)
        if callable(fn):
            return fn(key)
        return zc.get_children(key, base_url=self.base_url)

    # -- 附件与全文 ------------------------------------------------------

    def resolve_attachment_path(self, attachment: Dict[str, Any]) -> Optional[str]:
        fn = getattr(self._client, "resolve_attachment_path", None)
        if callable(fn):
            # client 自带解析：它是权威，不回落网络。
            try:
                return fn(attachment)
            except Exception:  # noqa: BLE001
                return None
        module = _zotero_fulltext()
        if module is not None and hasattr(module, "resolve_attachment_path"):
            try:
                path = module.resolve_attachment_path(self._client, attachment)
            except Exception:  # noqa: BLE001
                path = None
            if path:
                return path
        try:
            return zc.local_attachment_path(attachment, base_url=self.base_url)
        except Exception:  # noqa: BLE001
            return None

    def attachment_fulltext(self, attachment_key: str) -> Optional[Dict[str, Any]]:
        fn = getattr(self._client, "item_fulltext", None)
        if callable(fn):
            # client 自带只读全文读取：它是权威，不回落网络。
            try:
                return fn(attachment_key)
            except Exception:  # noqa: BLE001
                return None
        module = _zotero_fulltext()
        if module is not None and hasattr(module, "attachment_fulltext"):
            try:
                payload = module.attachment_fulltext(self._client, attachment_key)
            except Exception:  # noqa: BLE001
                payload = None
            if payload:
                return payload
        try:
            return zc.item_fulltext(attachment_key, base_url=self.base_url)
        except Exception:  # noqa: BLE001
            return None

    def extract_pages(self, attachment_key: Optional[str],
                      pdf_path: Optional[str]) -> Optional[Dict[str, Any]]:
        """页级抽取。返回 None 表示「页级抽取不可用」，调用方必须如实降级。"""
        fn = getattr(self._client, "page_texts_for", None)
        if callable(fn):
            try:
                payload = fn(attachment_key, pdf_path)
            except TypeError:
                payload = fn(attachment_key)
            except Exception:  # noqa: BLE001
                payload = None
            if payload:
                return payload

        fn = getattr(self._client, "extract_pages", None)
        if callable(fn):
            try:
                payload = fn(pdf_path)
            except Exception:  # noqa: BLE001
                payload = None
            if payload:
                return payload

        module = _zotero_fulltext()
        if module is not None and hasattr(module, "extract_pages"):
            try:
                payload = module.extract_pages(pdf_path)
            except Exception:  # noqa: BLE001
                payload = None
            if payload:
                return payload

        return _extract_pages_pypdf(pdf_path or "")


def _library_backend(client: Any) -> str:
    """活动文献后端标识：Zotero Local API 优先，否则 refs / unknown。"""
    if client is None:
        return "unknown"
    for attr in ("library_backend", "backend"):
        value = getattr(client, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    status = getattr(client, "status", None)
    if isinstance(status, str) and status.strip():
        return "zotero" if status.strip().upper().startswith("ZOTERO") else "refs"
    return "zotero"


# ---------------------------------------------------------------------------
# 证据锚点
# ---------------------------------------------------------------------------


def make_evidence_anchor(
    *,
    library_backend: Optional[str] = None,
    zotero_item_key: Optional[str] = None,
    attachment_key: Optional[str] = None,
    doi: Optional[str] = None,
    pdf_sha256: Optional[str] = None,
    page: Optional[int] = None,
    section: Optional[str] = None,
    quote: Optional[str] = None,
    claim: Optional[str] = None,
    assessment: Optional[str] = None,
    verification: str = "insufficient_evidence",
    fingerprint_expected: Optional[str] = None,
) -> Dict[str, Any]:
    """构造证据锚点（任务书 §5.3 的 11 个字段 + stale 标记）。

    纪律（硬）：

    - `page` **只在** `verification == "page_verified"` 时允许非 None；否则抛 `ValueError`；
    - `page_verified` **必须**同时有 `page` 与非空 `quote`；
    - 指纹不匹配（`fingerprint_expected` 已给且 ≠ `pdf_sha256`）→ `stale = True`，
      `assessment` 标记 `needs-review`，消费方**不得**再把它当有效证据。
    """
    if verification not in VERIFICATION_LEVELS:
        raise ValueError(
            f"verification 必须是 {VERIFICATION_LEVELS} 之一，得到 {verification!r}")
    if verification != "page_verified" and page is not None:
        raise ValueError("page 只在 verification == 'page_verified' 时允许非 None")
    if verification == "page_verified" and (page is None or not _clean(quote)):
        raise ValueError("page_verified 必须有 page 与非空 quote")

    stale = bool(fingerprint_expected) and fingerprint_expected != pdf_sha256
    note = _clean(assessment)
    if stale:
        note = f"needs-review（PDF 指纹不匹配）{('；' + note) if note else ''}"
    elif not note:
        note = "not-assessed"

    return {
        "library_backend": library_backend or "unknown",
        "zotero_item_key": zotero_item_key,
        "attachment_key": attachment_key,
        "doi": doi,
        "pdf_sha256": pdf_sha256,
        "page": page,
        "section": section,
        "quote": _clean(quote),
        "claim": _clean(claim),
        "assessment": note,
        "verification": verification,
        # 扩展（非 Research State 字段）：证据锚点自身的 freshness。
        "stale": stale,
        "fingerprint_expected": fingerprint_expected,
    }


def _anchor_is_stale(anchor: Dict[str, Any], current_sha256: Optional[str]) -> bool:
    return bool(anchor.get("pdf_sha256")) and bool(current_sha256) \
        and anchor.get("pdf_sha256") != current_sha256


# ---------------------------------------------------------------------------
# 上下文：按需解析目标 / 元数据 / 笔记 / 可用性 / 页文本 / 索引全文
# ---------------------------------------------------------------------------


class _Context:
    def __init__(self, bridge: _Bridge, client: Any, item_key: str,
                 budget: int, warnings: List[str]):
        self.bridge = bridge
        self.client = client
        self.library_backend = _library_backend(client)
        self.requested_key = item_key
        self.budget = max(int(budget), 500)
        self.budget_used = 0
        self.warnings = warnings

        self.item: Optional[Dict[str, Any]] = None
        self.metadata: Dict[str, Any] = {}
        self.children: List[Dict[str, Any]] = []
        self.notes: List[str] = []
        self.attachments: List[Dict[str, Any]] = []
        self.attachment: Optional[Dict[str, Any]] = None
        self.attachment_key: Optional[str] = None
        self.pdf_path: Optional[str] = None
        self.doi: Optional[str] = None

        self._pages_payload: Optional[Dict[str, Any]] = None
        self._pages_loaded = False
        self._index_payload: Optional[Dict[str, Any]] = None
        self._index_loaded = False
        self.page_extraction_available: Optional[bool] = None
        self.pdf_complete: Optional[bool] = None
        self.page_coverage: Optional[str] = None
        self.page_numbers: List[int] = []

    # -- 解析 ------------------------------------------------------------

    def load(self) -> bool:
        item = self.bridge.get_item(self.requested_key)
        if not item:
            self.warnings.append(f"条目不存在或不可读：{self.requested_key}")
            return False
        data = item.get("data") or {}
        # 允许直接传附件 key：向上找父条目。
        if data.get("itemType") in {"attachment", "note", "annotation"}:
            parent = data.get("parentItem")
            if parent:
                parent_item = self.bridge.get_item(parent)
                if parent_item:
                    item = parent_item
        self.item = item
        key = item.get("key") or self.requested_key
        record = zc.item_to_record(item)
        self.metadata = {
            "title": record.get("title"),
            "authors": record.get("authors") or [],
            "year": record.get("year"),
            "venue": record.get("venue"),
            "doi": record.get("doi"),
            "arxiv_id": record.get("arxiv_id"),
            "abstract": record.get("abstract"),
            "zotero_item_key": key,
        }
        self.doi = record.get("doi")
        self.children = self.bridge.get_children(key) or []
        self.notes = [t for t in (_strip_html((c.get("data") or {}).get("note") or "")
                                  for c in self.children) if t]
        self.attachments = [
            c for c in self.children
            if (c.get("data") or {}).get("itemType") == "attachment"
            and (c.get("data") or {}).get("contentType") == "application/pdf"
        ]
        if self.attachments:
            self.attachment = self.attachments[0]
            self.attachment_key = (self.attachment.get("key")
                                   or (self.attachment.get("data") or {}).get("key"))
            self.pdf_path = self.bridge.resolve_attachment_path(self.attachment)
        return True

    # -- 懒加载 ----------------------------------------------------------

    def pages_payload(self) -> Optional[Dict[str, Any]]:
        """只在真正需要页级判断时抽取 PDF。"""
        if self._pages_loaded:
            return self._pages_payload
        self._pages_loaded = True
        if not self.pdf_path:
            self._pages_payload = None
            return None
        payload = self.bridge.extract_pages(self.attachment_key, self.pdf_path)
        if not payload or not payload.get("pages"):
            self.page_extraction_available = False
            self.warnings.append(
                "PDF 页级抽取不可用（zotero_fulltext 缺失且内建回退不可用/解析失败）；"
                "已降级，不声称 page_verified。")
            self._pages_payload = None
            return None
        self.page_extraction_available = True
        self._pages_payload = payload
        self.page_numbers = [int(p.get("page") or i + 1)
                             for i, p in enumerate(payload.get("pages") or [])]
        self.pdf_complete, self.page_coverage = _coverage(payload)
        if not self.pdf_complete:
            self.warnings.append(
                f"PDF 不完整或文本质量不足，覆盖范围 {self.page_coverage}；"
                "结果按 insufficient_evidence 处理，未覆盖部分不编造。")
        return payload

    def pages(self, page_filter: Optional[Iterable[int]] = None) -> List[Dict[str, Any]]:
        payload = self.pages_payload()
        if not payload:
            return []
        keep = {int(p) for p in page_filter} if page_filter else None
        out = []
        for page in payload.get("pages") or []:
            if keep is not None and int(page.get("page") or -1) not in keep:
                continue
            out.append(page)
        return out

    def index_payload(self) -> Optional[Dict[str, Any]]:
        if self._index_loaded:
            return self._index_payload
        self._index_loaded = True
        if not self.attachment_key:
            return None
        self._index_payload = self.bridge.attachment_fulltext(self.attachment_key)
        return self._index_payload

    def index_content(self) -> Optional[str]:
        payload = self.index_payload()
        content = _clean((payload or {}).get("content"))
        return content

    # -- 预算 ------------------------------------------------------------

    def consume(self, text: Optional[str]) -> Tuple[Optional[str], bool]:
        """按剩余预算截断文本；返回 `(text, truncated)`。"""
        if not text:
            return text, False
        remaining = self.budget - self.budget_used
        if remaining <= 0:
            return None, True
        if len(text) <= remaining:
            self.budget_used += len(text)
            return text, False
        clipped = text[:remaining]
        self.budget_used += remaining
        return clipped, True


def _coverage(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """返回 `(是否完整, 覆盖范围描述)`。

    不完整 = 有页缺文本 / 页数不足 / 质量标记异常。范围描述必须如实给出。
    """
    pages = payload.get("pages") or []
    total = payload.get("total_pages") or payload.get("num_pages") or len(pages)
    try:
        total = int(total)
    except (TypeError, ValueError):
        total = len(pages)
    nonempty = [int(p.get("page") or i + 1) for i, p in enumerate(pages)
                if (p.get("text") or "").strip()]
    low_quality = [int(p.get("page") or i + 1) for i, p in enumerate(pages)
                   if str(p.get("quality") or "").lower()
                   in {"empty", "scanned", "low", "low_text", "poor", "two_column_order"}]
    if total <= 0:
        return False, "无可抽取页"
    if not nonempty:
        return False, "0 页（疑为扫描件或无文本层）"
    span = f"{min(nonempty)}-{max(nonempty)} / {total}"
    complete = len(nonempty) >= total and not low_quality
    return complete, span


# ---------------------------------------------------------------------------
# 定级
# ---------------------------------------------------------------------------


def _grade(*, used_pdf_pages: bool, used_index: bool, used_abstract: bool,
           used_metadata: bool, page_located: bool, incomplete: bool) -> Tuple[str, str]:
    """唯一的等级判定入口（证据政策只认这里产出的等级）。"""
    if incomplete and used_pdf_pages:
        return ("insufficient_evidence",
                "PDF 不完整或有页面无文本：已抽取部分可用，覆盖范围见 availability，"
                "不得据此声称完整全文级判断。")
    if used_pdf_pages:
        if page_located:
            return ("page_verified", "引文取自真实 PDF 页文本，可指到具体页码。")
        return ("pdf_text_verified", "文本取自真实 PDF，但未定位到单一页码。")
    if used_index:
        # ★ 索引命中一律 indexed_fulltext，绝不升级为 page_verified。
        return ("indexed_fulltext",
                "命中来自 Zotero 全文索引；索引是扁平文本、无页码边界，"
                "不得作为页码级证据。")
    if used_abstract:
        return ("abstract_only", "仅有摘要可用；原文明确声明未做全文级判断。")
    if used_metadata:
        return ("metadata_only", "仅有元数据；未读取任何正文。")
    return ("insufficient_evidence", "没有可用作证据的文本。")


def _weaker(a: str, b: str) -> str:
    """取两个等级中更弱的一个（`insufficient_evidence` 最弱）。"""
    if a == "insufficient_evidence" or b == "insufficient_evidence":
        return "insufficient_evidence"
    return a if _LEVEL_RANK.get(a, -1) <= _LEVEL_RANK.get(b, -1) else b


# ---------------------------------------------------------------------------
# 证据定位
# ---------------------------------------------------------------------------


def _search_spans(spans: Sequence[Dict[str, Any]], query: str, *,
                  min_score: float = 0.25, top_k: int = 5) -> Tuple[List[Dict], List[Dict]]:
    """在章节 span 上定位支持句；返回 `(supporting, irrelevant)`。

    支持句 = 与 query 的内容词重合度 ≥ `min_score`；
    无关句 = 有弱重合但低于阈值 —— 显式分开，避免「搜到就当成支持」。
    """
    query_tokens = _content_tokens(query)
    if not query_tokens:
        return [], []

    scored: List[Dict[str, Any]] = []
    for span in spans:
        for sentence in _sentences(span.get("text") or ""):
            sentence_tokens = _content_tokens(sentence)
            if not sentence_tokens:
                continue
            overlap = query_tokens & sentence_tokens
            if not overlap:
                continue
            score = len(overlap) / len(query_tokens)
            scored.append({
                "quote": sentence,
                "page": span.get("page"),
                "section": span.get("section"),
                "score": round(score, 4),
                "matched_terms": sorted(overlap),
            })

    scored.sort(key=lambda item: (-item["score"], item["page"] or 0))
    supporting = [item for item in scored if item["score"] >= min_score][:top_k]
    irrelevant = [item for item in scored if item["score"] < min_score][:top_k]
    return supporting, irrelevant


def _section_page_map(sections: Dict[str, Any]) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for name in SECTIONS:
        record = sections.get(name)
        if not record:
            continue
        for page in record.get("pages") or []:
            out.setdefault(int(page), name)
    return out


# ---------------------------------------------------------------------------
# 模式实现
# ---------------------------------------------------------------------------


def _base_result(ctx: _Context, mode: str, result_level: str, reason: str) -> Dict[str, Any]:
    return {
        "item_key": (ctx.item or {}).get("key") or ctx.requested_key,
        "library_backend": ctx.library_backend,
        "mode": mode,
        "verification": result_level,
        "verification_reason": reason,
        "verification_levels": VERIFICATION_LEVELS,
        "metadata": ctx.metadata,
        "notes": ctx.notes,
        "availability": {
            "has_metadata": bool(ctx.metadata.get("title") or ctx.metadata.get("doi")),
            "has_abstract": bool(_clean(ctx.metadata.get("abstract"))),
            "has_notes": bool(ctx.notes),
            "has_pdf": bool(ctx.pdf_path),
            "pdf_path": ctx.pdf_path,
            "pdf_sha256": (ctx._pages_payload or {}).get("sha256") if ctx._pages_payload else None,
            "page_extraction_available": ctx.page_extraction_available,
            "pdf_complete": ctx.pdf_complete,
            "page_coverage": ctx.page_coverage,
            "pages_available": list(ctx.page_numbers),
            "index_checked": ctx._index_loaded,
            "has_indexed_fulltext": bool(ctx._index_payload),
        },
        "evidence": [],
        "anchors": [],
        "sections": {},
        "warnings": list(ctx.warnings),
        "budget": {"limit": ctx.budget, "used": ctx.budget_used},
    }


def _fill_availability_index(ctx: _Context, result: Dict[str, Any]) -> None:
    result["availability"].update({
        "index_checked": ctx._index_loaded,
        "has_indexed_fulltext": bool(ctx._index_payload),
    })


def _overview(ctx: _Context) -> Dict[str, Any]:
    """A 概览：只元数据 + 摘要 + 笔记 + 可用性；**不**做全文级判断。"""
    abstract = _clean(ctx.metadata.get("abstract"))
    detail = {
        "title": ctx.metadata.get("title"),
        "authors": ctx.metadata.get("authors"),
        "year": ctx.metadata.get("year"),
        "venue": ctx.metadata.get("venue"),
        "doi": ctx.metadata.get("doi"),
        "abstract": abstract,
        "abstract_char_count": len(abstract or ""),
        "notes": ctx.notes,
        "scope": "metadata_and_abstract_only",
    }
    if abstract:
        used_abstract, used_metadata = True, True
    else:
        used_abstract, used_metadata = False, bool(ctx.metadata.get("title"))
    level, reason = _grade(
        used_pdf_pages=False, used_index=False, used_abstract=used_abstract,
        used_metadata=used_metadata, page_located=False, incomplete=False)
    result = _base_result(ctx, "overview", level, reason)
    result["detail"] = detail
    if ctx.pdf_path:
        result["warnings"].append(
            "存在 PDF 附件，但 overview 只读元数据与摘要；"
            "有 PDF ≠ 深读过，故不提升验证等级。")
    result["availability"]["pdf_complete"] = None
    return result


def _section(ctx: _Context, sections: Sequence[str], page_filter: Optional[Iterable[int]],
             budget: int) -> Dict[str, Any]:
    """B 章节：只抽需要的章节；页级优先，索引次之，摘要兜底。"""
    requested = [s for s in (sections or SECTIONS) if s in SECTIONS]
    unknown = [s for s in (sections or []) if s not in SECTIONS]
    page_texts = ctx.pages(page_filter)
    used_pdf = bool(page_texts)
    used_index = False

    if used_pdf:
        found, _spans = _segment_pages(page_texts)
    else:
        content = ctx.index_content()
        if content:
            used_index = True
            found, _spans = _segment_flat(content)
        else:
            found, _spans = {}, []

    extracted: Dict[str, Any] = {}
    truncated_any = False
    for name in requested:
        record = found.get(name)
        if record and _clean(record.get("text")):
            text, truncated = ctx.consume(record.get("text"))
            truncated_any = truncated_any or truncated
            extracted[name] = {
                "found": True,
                "source": record.get("source"),
                "page": record.get("page"),
                "pages": list(record.get("pages") or []),
                "text": text,
            }
        elif name == "abstract" and _clean(ctx.metadata.get("abstract")):
            text, truncated = ctx.consume(ctx.metadata.get("abstract"))
            truncated_any = truncated_any or truncated
            extracted[name] = {
                "found": True, "source": "abstract", "page": None, "pages": [],
                "text": text,
            }
        else:
            extracted[name] = {
                "found": False, "source": None, "page": None, "pages": [], "text": None,
            }

    any_found = any(item["found"] for item in extracted.values())
    used_abstract = any(item["source"] == "abstract" for item in extracted.values())
    page_located = used_pdf and any(
        item["page"] is not None for item in extracted.values())
    level, reason = _grade(
        used_pdf_pages=used_pdf, used_index=used_index, used_abstract=used_abstract,
        used_metadata=bool(ctx.metadata.get("title")), page_located=page_located,
        incomplete=bool(used_pdf and ctx.pdf_complete is False))

    result = _base_result(ctx, "section", level, reason)
    result["sections"] = extracted
    result["detail"] = {
        "requested_sections": requested,
        "unknown_sections": unknown,
        "all_requested_found": all(item["found"] for item in extracted.values()),
    }
    section_pages = _section_page_map(found)
    anchors = []
    for name, item in extracted.items():
        if not item["found"] or not item["text"]:
            continue
        if level == "page_verified" and item["page"] is not None:
            page: Optional[int] = int(item["page"])
            anchor_verification = "page_verified"
        else:
            page = None
            anchor_verification = level
        anchors.append(make_evidence_anchor(
            library_backend=ctx.library_backend,
            zotero_item_key=result["item_key"],
            attachment_key=ctx.attachment_key,
            doi=ctx.doi,
            pdf_sha256=result["availability"]["pdf_sha256"],
            page=page,
            section=name,
            quote=item["text"][:280],
            claim=None,
            assessment=f"section '{name}' 抽取自 {item['source']}",
            verification=anchor_verification,
        ))
    result["anchors"] = anchors
    result["section_pages"] = section_pages
    if unknown:
        result["warnings"].append(f"忽略未知章节：{unknown}")
    if truncated_any:
        result["warnings"].append("预算用尽，部分章节文本被截断。")
    if used_pdf and ctx.pdf_complete is False:
        result["warnings"].append(
            f"PDF 覆盖不完整（{ctx.page_coverage}），结果等级 insufficient_evidence。")
    if any_found and level != "page_verified":
        result["warnings"].append(
            f"当前等级 {level}，不得据此写全文级或页码级结论。")
    _fill_availability_index(ctx, result)
    result["budget"]["used"] = ctx.budget_used
    return result


def _evidence(ctx: _Context, question: Optional[str], claim: Optional[str],
              page_filter: Optional[Iterable[int]]) -> Dict[str, Any]:
    """C 证据：在源文本中定位对特定 question / claim 的支持，并显式拒绝不支持者。"""
    query = _clean(question) or _clean(claim)
    page_texts = ctx.pages(page_filter)
    used_pdf = bool(page_texts)
    used_index = False

    if used_pdf:
        _sections, spans = _segment_pages(page_texts)
        used_index = False
    else:
        content = ctx.index_content()
        if content:
            used_index = True
            _sections, spans = _segment_flat(content)
        else:
            spans = []

    used_abstract = False
    if not spans and _clean(ctx.metadata.get("abstract")):
        used_abstract = True
        spans = [{"section": "abstract", "page": None,
                  "text": ctx.metadata.get("abstract")}]

    supporting, irrelevant = _search_spans(spans, query or "") if query else ([], [])
    matched = bool(supporting)
    page_located = used_pdf and any(item.get("page") is not None for item in supporting)
    level, reason = _grade(
        used_pdf_pages=used_pdf, used_index=used_index, used_abstract=used_abstract,
        used_metadata=bool(ctx.metadata.get("title")), page_located=page_located,
        incomplete=bool(used_pdf and ctx.pdf_complete is False))

    if not matched:
        assessment = "not_in_text"
        conclusion = "claim_not_supported_by_source"
    elif level == "insufficient_evidence":
        assessment = "partial_text_only"
        conclusion = "insufficient_evidence"
    else:
        assessment = "supported_by_source_text"
        conclusion = "supported_in_source_text"

    result = _base_result(ctx, "evidence", level, reason)
    result["detail"] = {
        "question": _clean(question),
        "claim": _clean(claim),
        "matched": matched,
        "assessment": assessment,
        "conclusion": conclusion,
        "page_filter": list(page_filter) if page_filter else None,
    }

    anchors = []
    for item in supporting:
        page = int(item["page"]) if (level == "page_verified" and item.get("page") is not None) else None
        anchors.append(make_evidence_anchor(
            library_backend=ctx.library_backend,
            zotero_item_key=result["item_key"],
            attachment_key=ctx.attachment_key,
            doi=ctx.doi,
            pdf_sha256=result["availability"]["pdf_sha256"],
            page=page,
            section=item.get("section"),
            quote=item.get("quote"),
            claim=_clean(claim) or _clean(question),
            assessment=assessment,
            verification=level,
        ))
    result["anchors"] = anchors
    result["evidence"] = [
        {
            "quote": item.get("quote"),
            "page": item.get("page") if level == "page_verified" else None,
            "section": item.get("section"),
            "score": item.get("score"),
            "matched_terms": item.get("matched_terms"),
            "verification": level,
        }
        for item in supporting
    ]
    result["irrelevant"] = [
        {
            "quote": item.get("quote"),
            "page": item.get("page") if level == "page_verified" else None,
            "section": item.get("section"),
            "score": item.get("score"),
            "matched_terms": item.get("matched_terms"),
        }
        for item in irrelevant
    ]
    if not matched:
        result["warnings"].append(
            "源文本中未找到支持该问题的语句：**拒绝**据此断言，assessment=not_in_text。")
    if used_pdf and ctx.pdf_complete is False:
        result["warnings"].append(
            f"PDF 覆盖不完整（{ctx.page_coverage}）；未覆盖部分不得推断。")
    if level == "indexed_fulltext":
        result["warnings"].append(
            "命中来自 Zotero 索引（扁平、无页码），等级固定为 indexed_fulltext，"
            "不得升级为 page_verified。")
    _fill_availability_index(ctx, result)
    return result


def _novelty_vocabulary() -> Dict[str, Any]:
    """复用既有词表：claim-first（`epistemic_status`）+ structural-equivalence（verdict）。

    本模块**不**新增 novelty reviewer，也**不**自行裁决；只暴露既有枚举。
    """
    vocab: Dict[str, Any] = {
        "epistemic_status_values": ("Observed", "Supported", "Hypothesized",
                                    "Planned", "Unknown"),
        "provenance_values": ("EXPLICIT", "DERIVED", "INFERRED", "UNKNOWN"),
        "verdict_values": (),
        "near_neighbor_verdict_values": (),
        "claimed_novelty_levels": (),
        "sources": [
            "claim-first-policy.md §2",
            "structural-equivalence-policy.md §7.1 / §23.1 / §8.2",
            "evidence-policy.md §1 / §3",
        ],
        "loaded_from_module": False,
    }
    try:
        import structural_equivalence_check as sec  # type: ignore
        vocab.update({
            "verdict_values": tuple(sec.VERDICTS),
            "near_neighbor_verdict_values": tuple(sec.NEAR_NEIGHBOR_VERDICTS),
            "claimed_novelty_levels": tuple(sec.CLAIMED_LEVELS),
            "loaded_from_module": True,
        })
    except Exception:  # noqa: BLE001
        vocab.update({
            "verdict_values": (
                "equivalent", "subsumed-by-prior", "reframing-only", "transfer-only",
                "component-delta", "mechanism-delta", "formulation-delta",
                "boundary-delta", "paradigm-candidate", "uncertain"),
            "near_neighbor_verdict_values": (
                "duplicate-equivalent", "reframing-neighbor", "transfer-neighbor",
                "component-neighbor", "mechanism-neighbor", "structural-delta",
                "structural-delta-strong", "uncertain"),
            "claimed_novelty_levels": (
                "none", "transfer-only", "component-delta", "mechanism-delta",
                "formulation-delta", "boundary-delta", "paradigm-candidate"),
        })
    return vocab


#: E 模式抽取的承重 facet（逐字取自 structural-equivalence-policy.md §3.1 的子集）。
_NOVELTY_FACETS: Tuple[str, ...] = (
    "problem",
    "assumptions",
    "mechanism",
    "predictions_or_guarantees",
    "boundary_or_failure_regime",
)


def _novelty(ctx: _Context) -> Dict[str, Any]:
    """E 新颖性：只做结构 facet 抽取 + 暴露既有词表；**不**裁决 novelty。"""
    sections_result = _section(ctx, ("method", "theory", "experiments", "limitations"),
                               None, ctx.budget)
    facets: Dict[str, Any] = {}
    for facet in _NOVELTY_FACETS:
        source_name = "method" if facet in {"problem", "assumptions", "mechanism"} else None
        record = sections_result["sections"].get(source_name) if source_name else None
        if not record or not record.get("found"):
            facets[facet] = {
                "value": None, "quote": None, "page": None,
                "provenance": "UNKNOWN", "epistemic_status": "Unknown",
            }
            continue
        quote = _first_sentence(record.get("text"))
        facets[facet] = {
            "value": quote,
            "quote": quote,
            "page": record.get("page") if sections_result["verification"] == "page_verified" else None,
            "provenance": "EXPLICIT",
            "epistemic_status": "Observed",
        }

    result = _base_result(ctx, "novelty", "insufficient_evidence",
                          "novelty 判断需要 structural-equivalence audit artifact；"
                          "本模式只抽取结构 facet，不作裁决。")
    result["detail"] = {
        "judgement_performed": False,
        "why": "LLM 不是 scientific novelty 的 truth oracle；novelty 只能由检索覆盖 + "
               "结构对齐证据 + 人类研究者判定（structural-equivalence-policy.md §1）。",
        "vocabulary": _novelty_vocabulary(),
        "scientific_typing": {"O": None, "T": None, "R": None},
        "facets": facets,
        "structural_evidence": sections_result.get("anchors") or [],
        "verdict": "uncertain",
        "near_neighbor_verdict": "uncertain",
        "claimed_novelty_level": "none",
        "note": "复用 claim-first-policy 与 structural-equivalence-policy 的既有枚举；"
                "不得据此声称 paradigm novelty。",
    }
    result["sections"] = sections_result["sections"]
    result["anchors"] = sections_result.get("anchors") or []
    result["warnings"].extend(sections_result.get("warnings") or [])
    result["availability"] = sections_result["availability"]
    _fill_availability_index(ctx, result)
    return result


def _first_sentence(text: Optional[str]) -> Optional[str]:
    sentences = _sentences(text or "")
    return sentences[0] if sentences else _clean(text)


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------


def deep_read(client: Any, item_key: str, *, mode: str = "overview",
              sections: Optional[Sequence[str]] = None,
              question: Optional[str] = None,
              pages: Optional[Sequence[int]] = None,
              budget: int = DEFAULT_BUDGET,
              claim: Optional[str] = None) -> Dict[str, Any]:
    """按需深读单篇论文，返回结构化结果 + 证据锚点。

    Args:
        client: `WriteClient` / 只读 client / 裸 base_url / None；只需暴露
            `base_url`，或 `get_item` / `get_children` / `item_fulltext` 等方法。
        item_key: 论文（或附件）key。
        mode: `overview` | `section` | `evidence` | `compare` | `novelty`。
        sections: `section` 模式要抽的章节；None = 全部。
        question: `evidence` 模式要定位的问题 / 主张。
        pages: 只在给定页码内搜索（页码级验证的边界）。
        budget: 正文读取字符预算。
        claim: 可选的显式主张（与 `question` 二选一或同给）。

    Returns:
        dict。`verification` 只取 `VERIFICATION_LEVELS`；`page` 仅在
        `page_verified` 时非 None。
    """
    warnings: List[str] = []
    if mode not in DEEPREAD_MODES:
        raise ValueError(f"mode 必须是 {DEEPREAD_MODES} 之一，得到 {mode!r}")
    bridge = _Bridge(client)
    ctx = _Context(bridge, client, item_key, budget, warnings)

    if not ctx.load():
        result = _base_result(ctx, mode, "insufficient_evidence",
                              f"目标不可读：{item_key}")
        result["warnings"] = warnings
        return result

    if mode == "overview":
        result = _overview(ctx)
    elif mode == "section":
        result = _section(ctx, sections or SECTIONS, pages, budget)
    elif mode == "evidence":
        result = _evidence(ctx, question, claim, pages)
    elif mode == "novelty":
        result = _novelty(ctx)
    else:  # compare：单篇时退化为 section 视图并提示使用 compare_papers
        result = _section(ctx, sections or SECTIONS, pages, budget)
        result["mode"] = "compare"
        result["warnings"].append(
            "compare 模式需要多篇论文；单篇调用请用 compare_papers()。")

    # 统一收尾：预算、指纹、锚点纪律。
    result["budget"] = {"limit": ctx.budget, "used": ctx.budget_used}
    result["warnings"] = list(dict.fromkeys(result.get("warnings") or warnings))
    _enforce_anchor_discipline(result)
    return result


def _enforce_anchor_discipline(result: Dict[str, Any]) -> None:
    """硬纪律落点：非 page_verified 的锚点 page 必须为 None。"""
    for anchor in result.get("anchors") or []:
        if anchor.get("verification") != "page_verified" and anchor.get("page") is not None:
            anchor["page"] = None
            anchor["assessment"] = (
                f"{anchor.get('assessment') or ''}；page 已清除（非 page_verified）").strip("；")


def compare_papers(client: Any, item_keys: Sequence[str], *,
                   aspect: str = "method",
                   budget: int = DEFAULT_BUDGET) -> Dict[str, Any]:
    """D 跨论文对比：只抽与 `aspect` 相关的章节，逐篇给锚点，不编造差异结论。

    `aspect` ∈ `method` | `assumptions` | `theory` | `experimental_setup`。
    """
    if aspect not in COMPARE_ASPECTS:
        raise ValueError(f"aspect 必须是 {COMPARE_ASPECTS} 之一，得到 {aspect!r}")

    sections = _ASPECT_SECTIONS[aspect]
    per_paper: List[Dict[str, Any]] = []
    weakest = "page_verified"
    warnings: List[str] = []
    for key in item_keys:
        read = deep_read(client, key, mode="section", sections=sections, budget=budget)
        weakest = _weaker(weakest, read.get("verification") or "insufficient_evidence")
        warnings.extend(read.get("warnings") or [])
        first_found = None
        for name in sections:
            record = (read.get("sections") or {}).get(name)
            if record and record.get("found"):
                first_found = {"section": name, **record}
                break
        per_paper.append({
            "item_key": read.get("item_key"),
            "doi": (read.get("metadata") or {}).get("doi"),
            "title": (read.get("metadata") or {}).get("title"),
            "verification": read.get("verification"),
            "found": bool(first_found),
            "section": first_found["section"] if first_found else None,
            "page": first_found.get("page") if first_found else None,
            "quote": _first_sentence(first_found.get("text")) if first_found else None,
            "text": first_found.get("text") if first_found else None,
            "anchors": read.get("anchors") or [],
            "availability": read.get("availability"),
        })

    comparison: Dict[str, Any] = {}
    for entry in per_paper:
        comparison[entry["item_key"]] = {
            "aspect": aspect,
            "section": entry["section"],
            "page": entry["page"] if entry["verification"] == "page_verified" else None,
            "quote": entry["quote"],
            "verification": entry["verification"],
            "present": entry["found"],
        }

    return {
        "mode": "compare",
        "aspect": aspect,
        "aspects": COMPARE_ASPECTS,
        "item_keys": list(item_keys),
        "verification": weakest,
        "verification_levels": VERIFICATION_LEVELS,
        "papers": per_paper,
        "comparison": comparison,
        "differences": [],
        "warnings": list(dict.fromkeys(warnings)),
        "note": "本结果只做逐篇取证与并列；差异结论必须由研究者/下游阶段基于锚点写出，"
                "不得由本模块编造。",
    }
