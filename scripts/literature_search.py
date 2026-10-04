#!/usr/bin/env python3
"""Research Idea Pipeline —— 文献检索执行器。

实现 references/literature-policy.md 的强制规范：

  1. 先本地，后 arxiv —— **但本地命中不是终点**：默认同时查 arxiv，结果取并集。
     仅在显式给出 --local-only 时才跳过 arxiv（该模式违反默认规则，会打印警告）。
  2. arxiv 429 限流 —— 指数退避 10s→20s→40s→80s→160s，最多 5 次；
     退避期间不发起任何新的 arxiv 请求。
  3. 结果必须缓存到 <local-dir>/cache/{query_hash}.json。
  4. 每条结果必须标注 source="local" 或 source="arxiv"。
  5. 5 次重试仍失败 —— 返回本地已有结果，并标注
     "arxiv 暂时不可用，以下结果仅来自本地库"（视为检索未达饱和）。
  6. --exhaustive 执行 A3 范围扩大直到饱和（§3.3），每轮结果按本轮参数单独缓存；
     --level L1|L2|L3 校验尽职调查等级（§3.1）；
     --also-query 追加同义词/上位词/否定式检索式。
  7. --limit 控制最终返回条数（--max 只控制每次 arxiv 查询的条数）。

用法：
    # 默认：本地 + arxiv 并集
    python literature_search.py --query "diffusion model combinatorial optimization" --max 20

    # 创新性声明：L3 穷尽级 + 自动扩检 + 追加检索式
    python literature_search.py --query "discrete diffusion combinatorial optimization" \
        --level L3 --exhaustive \
        --also-query "score-based generative model discrete optimization" \
        --also-query "limits of diffusion model combinatorial optimization"

    # 离线：显式只用本地（会打印规则违反提示，不得支撑创新性声明）
    python literature_search.py --query "..." --local-only

退出码：
    0  正常（本地 + arxiv 成功）
    1  硬错误（参数错误、本地库不可读、渲染失败等）
    2  arxiv 不可用，已回退到本地结果（检索未达饱和）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# 常量（与 literature-policy.md 保持一致）
# ---------------------------------------------------------------------------

MAX_RETRIES = 5
BASE_WAIT = 10  # 秒；退避序列 10 → 20 → 40 → 80 → 160
DEFAULT_LOCAL_DIR = os.environ.get("RESEARCH_LOCAL_LITERATURE", "./docs/refs")
DEFAULT_CACHE_DIR = os.environ.get("RESEARCH_LIT_CACHE")  # 为空则由 <local-dir>/cache 决定
RATE_LIMIT_NOTE = "arxiv 暂时不可用，以下结果仅来自本地库"
PARTIAL_ARXIV_NOTE = (
    "arxiv 在扩检索阶段中断，结果不完整（含中断前的 arxiv 结果）；检索未达饱和"
)

_LATIN_RE = re.compile(r"[a-z0-9][a-z0-9\-]+", re.IGNORECASE)
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
_STOPWORDS = {
    "the", "a", "an", "of", "for", "and", "or", "to", "in", "on", "with",
    "via", "using", "use", "from", "by", "is", "are", "be", "as", "at",
    "we", "our", "this", "that", "these", "those", "it", "its",
}

Log = Callable[[str], None]


def _log_stderr(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _noop_log(message: str) -> None:
    pass


def _cjk_tokens(text: str) -> List[str]:
    """中文没有空格分词：整段 + 二元组，使部分重合也能命中。"""
    out: List[str] = []
    for run in _CJK_RE.findall(text):
        out.append(run)
        if len(run) > 2:
            out.extend(run[i:i + 2] for i in range(len(run) - 1))
    return out


def tokenize(text: str) -> List[str]:
    """小写分词并去停用词；同时支持拉丁词与中文。

    ⚠️ 只匹配 ASCII 会让中文检索完全失效（本 Skill 的文档与多数查询是中文），
    因此中文走"整段 + 二元组"的分词策略。
    """
    if not text:
        return []
    low = text.lower()
    latin = [t for t in _LATIN_RE.findall(low) if t not in _STOPWORDS]
    return latin + _cjk_tokens(low)


def _coerce_year(value: Any) -> Optional[int]:
    """把 2019 / \"2019\" / \"2019-05\" 统一成 int；无法解析返回 None。"""
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

    ⚠️ 启用过滤时，年份未知的条目一律**排除**：否则 isinstance 守卫会让过滤被静默
    跳过，用户以为筛了年份其实没有。
    """
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
    """keywords 既可能是数组也可能是字符串；字符串不能被逐字符 join。"""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value if v)
    return ""


def query_hash(
    query: str,
    max_results: Optional[int] = None,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
) -> str:
    """稳定的查询哈希（含会影响结果的检索参数）。

    注意两点：
    1. Python 内建 hash() 受 PYTHONHASHSEED 影响，跨进程不稳定，不能用于缓存文件名
       （见 literature-policy.md §5.2）。此处使用 md5。
    2. 缓存键**必须包含 max_results 与年份过滤**：若只按 query 建键，用更大的
       --max 复跑会命中旧的、更小的结果集，直接损害 L3 / 扩检索的质量。
    """
    key = f"{query.strip().lower()}|{max_results}|{from_year}|{to_year}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Step 1：本地检索
# ---------------------------------------------------------------------------

def _read_paper_entries(papers_dir: Path) -> List[Dict[str, Any]]:
    """读取 papers/ 下的全部 JSON 元数据，并合并同名 .md 全文用于匹配。"""
    entries: List[Dict[str, Any]] = []
    if not papers_dir.is_dir():
        return entries

    for json_path in sorted(papers_dir.glob("*.json")):
        try:
            with json_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            _log_stderr(f"[warn] 跳过无法解析的文献文件：{json_path}")
            continue

        # 允许文件内是单条对象或对象数组
        records = data if isinstance(data, list) else [data]
        for record in records:
            if not isinstance(record, dict):
                continue
            record.setdefault("paper_id", json_path.stem)
            record["source"] = "local"

            md_path = json_path.with_suffix(".md")
            if md_path.is_file():
                try:
                    record["_fulltext"] = md_path.read_text(encoding="utf-8", errors="ignore")
                    record.setdefault("notes_path", str(md_path))
                except OSError:
                    pass
            entries.append(record)

    return entries


def search_local(
    query: str,
    local_dir: Path,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    entries: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """在本地文献库中按关键词匹配标题 / 摘要 / 关键词 / 全文。

    命中条目标注 source="local"。
    `entries` 可由调用方预先读入并复用，避免每个检索式都重读磁盘。
    """
    q_tokens = set(tokenize(query))
    if not q_tokens:
        return []

    if entries is None:
        entries = _read_paper_entries(local_dir / "papers")

    hit_records: List[Dict[str, Any]] = []
    for record in entries:
        year = _coerce_year(record.get("year"))
        if not _in_year_range(year, from_year, to_year):
            continue

        # 字段权重：标题 > 关键词 > 摘要 > 全文
        weighted_fields = [
            (record.get("title") or "", 3.0),
            (_keywords_text(record.get("keywords")), 2.5),
            (record.get("abstract") or "", 1.5),
            (record.get("_fulltext") or "", 1.0),
        ]

        score = 0.0
        matched: set = set()
        for text, weight in weighted_fields:
            field_tokens = set(tokenize(str(text)))
            overlap = q_tokens & field_tokens
            if overlap:
                matched |= overlap
                score += weight * len(overlap)

        # 短语整体命中额外加权（中文尤其依赖这一项）
        haystack = " ".join(
            str(record.get(k) or "") for k in ("title", "abstract", "_fulltext")
        ).lower()
        if query.strip().lower() in haystack:
            score += 5.0

        if score > 0:
            hit = {k: v for k, v in record.items() if not k.startswith("_")}
            hit["_score"] = round(score, 3)
            hit["matched_terms"] = sorted(matched)
            hit_records.append((score, hit))

    hit_records.sort(key=lambda pair: pair[0], reverse=True)
    return [hit for _, hit in hit_records]


# ---------------------------------------------------------------------------
# Step 2：arxiv 检索（含 429 指数退避）
# ---------------------------------------------------------------------------

def _status_of(exc: BaseException) -> Optional[int]:
    """从异常中尽力提取 HTTP 状态码。

    arxiv 包并不稳定导出 arxiv.HTTPError；实际多为 urllib.error.HTTPError
    （.code）或带 .response.status_code 的异常。详见 literature-policy.md §5.2。

    文本兜底只认"看起来像 HTTP 状态"的消息（要求 status/code/http 前缀），
    否则 "paper 2401.429 missing" 这类无关数字会触发 5 轮、共 310 秒的假退避。
    """
    for attr in ("status", "status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    if response is not None:
        value = getattr(response, "status_code", None)
        if isinstance(value, int):
            return value
    match = re.search(
        r"(?:status|code|http)[^0-9]{0,16}\b(4\d{2}|5\d{2})\b",
        str(exc),
        re.IGNORECASE,
    )
    if match:
        return int(match.group(1))
    return None


def extract_metadata(paper: Any) -> Dict[str, Any]:
    """把 arxiv 结果对象转成本地库约定格式。"""
    published = getattr(paper, "published", None)
    year = published.year if published is not None else None
    entry_id = getattr(paper, "entry_id", "") or ""
    return {
        "paper_id": entry_id.rsplit("/", 1)[-1] if entry_id else "",
        "title": (getattr(paper, "title", "") or "").strip(),
        "authors": [a.name for a in getattr(paper, "authors", []) or []],
        "abstract": (getattr(paper, "summary", "") or "").strip(),
        "published": str(published) if published is not None else "",
        "year": year,
        "venue": "",  # arxiv 元数据不含会议信息；会议过滤需人工/后续补充
        "url": entry_id,
        "categories": list(getattr(paper, "categories", []) or []),
        "source": "arxiv",
    }


def search_arxiv(
    query: str,
    max_results: int = 20,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    log: Log = _noop_log,
) -> List[Dict[str, Any]]:
    """调用 arxiv 包检索；429 时指数退避，最多 MAX_RETRIES 次。

    Raises:
        RuntimeError: 重试耗尽或 arxiv 包不可用。
        Exception: 非 429 的 HTTP 错误原样抛出（不重试）。
    """
    try:
        import arxiv  # type: ignore
    except ImportError as exc:  # pragma: no cover - 取决于环境
        raise RuntimeError("未安装 arxiv 包，请先 `pip install arxiv`") from exc

    last_error: Optional[BaseException] = None

    for attempt in range(MAX_RETRIES):
        try:
            client = arxiv.Client()
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance,
            )
            results: List[Dict[str, Any]] = []
            for paper in client.results(search):
                meta = extract_metadata(paper)
                if not _in_year_range(meta.get("year"), from_year, to_year):
                    continue
                results.append(meta)
            return results

        except Exception as exc:  # noqa: BLE001 - 需要按状态码分流
            last_error = exc
            status = _status_of(exc)
            if status == 429:
                wait = BASE_WAIT * (2 ** attempt)
                log(f"[429] 限流，等待 {wait}s 后重试（第 {attempt + 1} 次）")
                # 退避期间不发起任何新的 arxiv 请求
                time.sleep(wait)
                continue
            raise

    raise RuntimeError(f"arxiv 重试次数耗尽：{last_error}")


# ---------------------------------------------------------------------------
# Step 3：缓存
# ---------------------------------------------------------------------------

def cache_results(
    query: str,
    results: List[Dict[str, Any]],
    cache_dir: Path,
    max_results: Optional[int] = None,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
) -> Path:
    """把 arxiv 结果写入 <cache_dir>/{query_hash}.json（键含检索参数）。"""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{query_hash(query, max_results, from_year, to_year)}.json"
    payload = {
        "query": query,
        "params": {"max_results": max_results, "from_year": from_year, "to_year": to_year},
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "count": len(results),
        "results": results,
    }
    with cache_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return cache_path


def read_cache(
    query: str,
    cache_dir: Path,
    max_results: Optional[int] = None,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
) -> Optional[List[Dict[str, Any]]]:
    """读取查询缓存；缓存中的 arxiv 结果仍标注 source="arxiv"。

    缓存键含 max_results 与年份过滤，因此换了 --max / --from-year 不会命中旧结果。
    """
    cache_path = cache_dir / f"{query_hash(query, max_results, from_year, to_year)}.json"
    if not cache_path.is_file():
        return None
    try:
        with cache_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    results = payload.get("results")
    if not isinstance(results, list):
        return None
    for item in results:
        if isinstance(item, dict):
            item["source"] = "arxiv"
            item["cache_hit"] = True
    return results


# ---------------------------------------------------------------------------
# 编排：search_literature（对应 literature-policy.md 的伪代码）
# ---------------------------------------------------------------------------

# 尽职调查等级要求（见 literature-policy.md §3.1）
LEVEL_REQUIREMENTS: Dict[str, Dict[str, Any]] = {
    "L1": {"min_queries": 1, "min_results": 10, "require_arxiv": False},
    "L2": {"min_queries": 4, "min_results": 30, "require_arxiv": True},
    "L3": {"min_queries": 8, "min_results": 60, "require_arxiv": True},
}

LOCAL_ONLY_NOTE = (
    "仅使用本地库（--local-only）：违反默认检索规则——本地检索不得作为终点，"
    "本地结果不构成任何不存在性证据，**不得用于支撑创新性声明（T1）**。"
)


def _level_report(
    level: Optional[str],
    n_queries: int,
    n_results: int,
    arxiv_available: bool,
    saturated: bool,
    escalation_attempted: bool = False,
) -> Dict[str, Any]:
    """按 §3.1 校验尽职调查等级达成情况。

    ⚠️ 饱和（§3.3）**只对 L2/L3 是硬要求**：L1 不要求扩检索，若把 saturated 作为
    所有等级的硬检查，任何未开 --exhaustive 的普通检索都会报"L1 未达成"。
    """
    name = level or "L1"
    req = LEVEL_REQUIREMENTS.get(name, LEVEL_REQUIREMENTS["L1"])
    checks = {
        "queries": n_queries >= req["min_queries"],
        "results": n_results >= req["min_results"],
        "arxiv": arxiv_available or not req["require_arxiv"],
    }
    if name in ("L2", "L3"):
        checks["saturated"] = saturated
    return {
        "level": name,
        "requirements": req,
        "actual": {
            "queries": n_queries,
            "results": n_results,
            "arxiv_available": arxiv_available,
            "saturated": saturated,
            "escalation_attempted": escalation_attempted,
        },
        "checks": checks,
        "achieved": all(checks.values()),
        "gaps": [key for key, ok in checks.items() if not ok],
    }


def search_literature(
    query: str,
    max_results: int = 20,
    local_dir: Path = Path(DEFAULT_LOCAL_DIR),
    cache_dir: Optional[Path] = None,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    refresh: bool = False,
    use_cache: bool = True,
    local_only: bool = False,
    also_queries: Optional[List[str]] = None,
    exhaustive: bool = False,
    level: Optional[str] = None,
    limit: Optional[int] = None,
    log: Log = _noop_log,
) -> Dict[str, Any]:
    """本地 + arxiv 合并检索（含 429 退避、缓存、扩检与饱和判定）。

    ★ 默认不因本地命中而短路：只要未显式 `local_only`，都会查询 arxiv。
      这是 literature-policy.md §0 对原规范的强化。

    Args:
        max_results: 传给 arxiv 的单次查询条数上限（本地命中不受此限制）。
        limit: 可选，最终返回条数上限（None = 不截断）。截断时保留本地优先的顺序。

    Returns:
        {
          "query": str,
          "results": [...],              # 本地 + arxiv 并集（含 source 标注）
          "steps": [...],                # 检索过程记录
          "rate_limit_log": [...],       # 429 等待日志 / arxiv 失败记录
          "cache_updates": [...],
          "note": str | None,
          "arxiv_available": bool,
          "total_results_before_limit": int,
          "truncated": int,
          "negative_search_record": [...],  # 逐检索式的负检索记录（L2/L3 必需）
          "escalations": [...],          # A3 范围扩大记录
          "saturation": {...},
          "level_report": {...},
        }
    """
    cache_dir = cache_dir or (local_dir / "cache")
    steps: List[Dict[str, Any]] = []
    rate_limit_log: List[str] = []
    cache_updates: List[str] = []
    escalations: List[Dict[str, Any]] = []

    queries = [query] + [q for q in (also_queries or []) if q and q.strip()]
    local_by_query: Dict[str, List[Dict[str, Any]]] = {q: [] for q in queries}
    arxiv_by_query: Dict[str, List[Dict[str, Any]]] = {q: [] for q in queries}

    def capture(message: str) -> None:
        if message.startswith("[429]") or message.startswith("[arxiv-error]"):
            rate_limit_log.append(message)
        log(message)

    def try_cache(q: str, hits: List[Dict[str, Any]],
                  mx: Optional[int], fy: Optional[int], ty: Optional[int]) -> None:
        """缓存写入失败**不得**中断检索（缓存目录只读/被占用很常见）。"""
        try:
            path = cache_results(q, hits, cache_dir, mx, fy, ty)
        except OSError as exc:
            log(f"[warn] 缓存写入失败（不影响本次结果）：{exc}")
            return
        cache_updates.append(f"{path} ({len(hits)} 条)")
        steps.append({"step": "cache_write", "query": q, "hits": len(hits)})

    # --- Step 1: 本地检索（纳入结果，但不作为终点） ---    # 本地库只读一次，在所有检索式之间复用（避免 O(检索式 × 文件数) 的重复 IO）
    entries = _read_paper_entries(local_dir / "papers")
    for q in queries:
        hits = search_local(q, local_dir, from_year, to_year, entries=entries)
        steps.append({"step": "local", "query": q, "hits": len(hits)})
        local_by_query[q].extend(hits)

    local_hits = [hit for q in queries for hit in local_by_query[q]]
    per_query: Dict[str, List[Dict[str, Any]]] = dict(local_by_query)

    if local_only:
        merged = _merge_unique(local_hits)
        return _finish(
            query=query, merged=merged, steps=steps, rate_limit_log=rate_limit_log,
            cache_updates=[], note=LOCAL_ONLY_NOTE, arxiv_available=True,
            per_query=per_query, escalations=[],
            saturation={"saturated": False, "reason": "local-only 模式下不做饱和判定"},
            level=level, limit=limit, escalation_attempted=False,
        )

    # --- Step 2: arxiv 检索（每个检索式一次；命中缓存则跳过） ---
    arxiv_available = True
    for q in queries:
        if use_cache and not refresh:
            cached = read_cache(q, cache_dir, max_results, from_year, to_year)
            if cached is not None:
                steps.append({"step": "cache", "query": q, "hits": len(cached)})
                arxiv_by_query[q].extend(cached)
                continue

        try:
            hits = search_arxiv(
                q, max_results=max_results, from_year=from_year,
                to_year=to_year, log=capture,
            )
        except Exception as exc:  # noqa: BLE001 - arxiv 失败一律回退本地结果
            arxiv_available = False
            steps.append({"step": "arxiv", "query": q, "hits": 0, "error": str(exc)})
            if not rate_limit_log:
                rate_limit_log.append(f"[arxiv-error] 未发生 429；arxiv 调用失败：{exc}")
            break  # arxiv 不可用时不再发起新请求

        steps.append({"step": "arxiv", "query": q, "hits": len(hits)})
        arxiv_by_query[q].extend(hits)
        # 空结果同样缓存：否则冷门/罕见检索式每次都要重打 arxiv
        try_cache(q, hits, max_results, from_year, to_year)

    for q in queries:
        per_query[q] = _merge_unique(local_by_query[q], arxiv_by_query[q])

    arxiv_hits = [hit for q in queries for hit in arxiv_by_query[q]]
    merged = _merge_unique(local_hits, arxiv_hits)

    # --- Step 3: 范围扩大（A3）与饱和判定（§3.3） ---
    saturated = False
    saturation_reason = "未启动扩大检索"
    if exhaustive and arxiv_available:
        zero_streak = 0
        plan = [
            {"round": 2, "action": "放宽时间范围（A3 第 ② 级）", "from_year": None, "to_year": None, "max": max_results},
            {"round": 3, "action": "增加 max_results（A3 第 ④ 级）", "from_year": None, "to_year": None, "max": max_results * 2},
            {"round": 4, "action": "增加 max_results（A3 第 ④ 级）", "from_year": None, "to_year": None, "max": max_results * 4},
            {"round": 5, "action": "增加 max_results（A3 第 ④ 级）", "from_year": None, "to_year": None, "max": max_results * 8},
        ]
        for step_plan in plan:
            before = len(merged)
            round_hits: List[Dict[str, Any]] = []
            failed = False
            for q in queries:
                try:
                    q_hits = search_arxiv(
                        q, max_results=step_plan["max"],
                        from_year=step_plan["from_year"], to_year=step_plan["to_year"],
                        log=capture,
                    )
                except Exception as exc:  # noqa: BLE001
                    arxiv_available = False
                    steps.append({"step": "arxiv", "query": q, "hits": 0, "error": str(exc)})
                    failed = True
                    break
                round_hits.extend(q_hits)
                arxiv_by_query[q].extend(q_hits)
                # 扩检索结果按本轮参数单独缓存，否则下次 --exhaustive 会命中更小的集合
                try_cache(
                    q, q_hits, step_plan["max"],
                    step_plan["from_year"], step_plan["to_year"],
                )
            merged = _merge_unique(merged, round_hits)
            gained = len(merged) - before
            escalations.append({
                "round": step_plan["round"],
                "action": step_plan["action"],
                "max_results": step_plan["max"],
                "new_unique": gained,
            })
            steps.append({
                "step": f"escalation_{step_plan['round']}",
                "query": query,
                "hits": len(round_hits),
                "new_unique": gained,
            })
            for q in queries:
                per_query[q] = _merge_unique(local_by_query[q], arxiv_by_query[q])
            if failed:
                saturation_reason = "arxiv 调用失败，检索未达饱和"
                break
            zero_streak = zero_streak + 1 if gained == 0 else 0
            if zero_streak >= 2:
                saturated = True
                saturation_reason = "连续两轮扩大检索均无新增文献（§3.3 判据 1）"
                break
        if not saturated and arxiv_available:
            saturation_reason = "扩大检索轮次已用尽；新增仍非零，建议追加同义词检索式"
    elif arxiv_available:
        saturation_reason = "未启用 --exhaustive；本地+arxiv 单轮检索"

    # --- 回退说明：区分"完全没有 arxiv 结果"与"扩检索中途失败" ---
    if arxiv_available:
        note: Optional[str] = None
    elif any(hit.get("source") == "arxiv" for hit in merged):
        note = PARTIAL_ARXIV_NOTE
    else:
        note = RATE_LIMIT_NOTE

    return _finish(
        query=query, merged=merged, steps=steps, rate_limit_log=rate_limit_log,
        cache_updates=cache_updates, note=note, arxiv_available=arxiv_available,
        per_query=per_query, escalations=escalations,
        saturation={"saturated": saturated, "reason": saturation_reason},
        level=level, limit=limit, escalation_attempted=bool(escalations),
    )


def _finish(
    query: str,
    merged: List[Dict[str, Any]],
    steps: List[Dict[str, Any]],
    rate_limit_log: List[str],
    cache_updates: List[str],
    note: Optional[str],
    arxiv_available: bool,
    per_query: Dict[str, List[Dict[str, Any]]],
    escalations: List[Dict[str, Any]],
    saturation: Dict[str, Any],
    level: Optional[str],
    limit: Optional[int],
    escalation_attempted: bool,
) -> Dict[str, Any]:
    """组装返回值：套用 --limit、生成负检索记录与等级报告。"""
    total_before_limit = len(merged)
    truncated = 0
    if limit is not None and limit >= 0 and total_before_limit > limit:
        merged = merged[:limit]
        truncated = total_before_limit - limit

    gaps_level = _level_report(
        level, len(per_query), total_before_limit, arxiv_available,
        bool(saturation.get("saturated")), escalation_attempted,
    )
    return {
        "query": query,
        "results": merged,
        "steps": steps,
        "rate_limit_log": rate_limit_log or ["本轮无 429"],
        "cache_updates": cache_updates,
        "note": note,
        "arxiv_available": arxiv_available,
        "total_results_before_limit": total_before_limit,
        "truncated": truncated,
        "negative_search_record": _negative_record(list(per_query), per_query),
        "escalations": escalations,
        "saturation": saturation,
        "level_report": gaps_level,
    }


def _negative_record(
    queries: List[str],
    per_query: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """负检索记录：**每个检索式各自**命中了什么、来自哪里。

    用于支撑"据本次检索未见"这类措辞（literature-policy.md §2.1）：
    该措辞要求"检索式列表 + **每式命中数** + 为何不足以否定目标声明"。
    ⚠️ 早前实现把全局总数复制给每个检索式，导致该证据不成立。
    """
    record: List[Dict[str, Any]] = []
    for q in queries:
        hits = per_query.get(q, [])
        by_source: Dict[str, int] = {}
        for item in hits:
            src = str(item.get("source", "?"))
            by_source[src] = by_source.get(src, 0) + 1
        record.append({
            "query": q,
            "total_hits": len(hits),
            "by_source": by_source,
            # 脚本无法判定"为何不足以否定"，必须由执行者填写
            "why_not_conclusive": "",
        })
    return record


def _dedup_key(item: Dict[str, Any]) -> str:
    """去重键：归一化 arXiv URL/ID 后再比，避免 http/https、有无 vN 造成的重复。"""
    url = str(item.get("url") or "").strip().lower()
    if url:
        url = re.sub(r"^https?://", "", url)
        url = re.sub(r"v\d+$", "", url)            # .../2401.01234v2 → .../2401.01234
        url = url.rstrip("/")
        return url
    paper_id = str(item.get("paper_id") or "").strip().lower()
    if paper_id:
        return paper_id
    return re.sub(r"\W+", "", str(item.get("title") or "").lower())


def _merge_unique(*groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按归一化 URL/ID/标题去重合并，保留首次出现的来源标注。"""
    merged: List[Dict[str, Any]] = []
    seen: set = set()
    for group in groups:
        for item in group:
            key = _dedup_key(item)
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            merged.append(item)
    return merged


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _render_table(results: List[Dict[str, Any]], limit: int = 30) -> str:
    if not results:
        return "（无命中）"
    lines = []
    for i, r in enumerate(results[:limit], 1):
        # 本地库可能字段缺失或为 null，渲染不能因此崩溃
        authors = r.get("authors") or []
        if isinstance(authors, str):
            authors = [authors]
        first_author = authors[0] if authors else "?"
        year = r.get("year")
        if not year:
            published = str(r.get("published") or "")
            match = re.search(r"(?:19|20)\d{2}", published)
            year = match.group(0) if match else "?"
        venue = r.get("venue") or r.get("source") or "?"
        title = (r.get("title") or "").strip() or "(无标题)"
        lines.append(f"{i:>2}. [{first_author} et al., {venue} {year}] {title}")
        lines.append(f"    来源: {r.get('source', '?')}    {r.get('url', '')}")
    if len(results) > limit:
        lines.append(f"… 另有 {len(results) - limit} 条（用 --json 查看全部）")
    return "\n".join(lines)


class _Parser(argparse.ArgumentParser):
    """让参数错误返回 1，与"arxiv 不可用"的退出码 2 区分开。"""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"错误：{message}", file=sys.stderr)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        description="Research Idea Pipeline 文献检索（先本地，后 arxiv；本地命中不是终点）",
    )
    parser.add_argument("--query", "-q", required=True, help="检索关键词或研究问题")
    parser.add_argument(
        "--max", "-n", type=int, default=20,
        help="每次 arxiv 查询的条数上限（默认 20）。本地命中不受此限制；"
             "最终返回条数请用 --limit 控制",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="最终返回条数上限（默认不截断；截断时保留本地优先顺序）",
    )
    parser.add_argument("--from-year", type=int, default=None, help="起始年份（含）")
    parser.add_argument("--to-year", type=int, default=None, help="结束年份（含）")
    parser.add_argument(
        "--local-dir", default=DEFAULT_LOCAL_DIR,
        help=f"本地文献库根目录（默认 {DEFAULT_LOCAL_DIR}，亦可用 RESEARCH_LOCAL_LITERATURE）",
    )
    parser.add_argument(
        "--cache-dir", default=DEFAULT_CACHE_DIR,
        help="缓存目录（默认 <local-dir>/cache，亦可用 RESEARCH_LIT_CACHE）",
    )
    parser.add_argument("--refresh", action="store_true", help="强制跳过缓存（仍查本地与 arxiv）")
    parser.add_argument("--no-cache", action="store_true", help="不使用缓存（仍会写入）")
    parser.add_argument(
        "--local-only", action="store_true",
        help="★ 显式只用本地库（离线场景）。违反默认检索规则，结果不得用于支撑创新性声明",
    )
    parser.add_argument(
        "--also-query", action="append", default=[], metavar="QUERY",
        help="追加检索式（同义词/上位词/否定式），可重复；用于 A3 第 ① 级扩大",
    )
    parser.add_argument(
        "--exhaustive", action="store_true",
        help="自动执行多轮扩大检索直到饱和（literature-policy §3.3）",
    )
    parser.add_argument(
        "--level", choices=["L1", "L2", "L3"], default=None,
        help="尽职调查等级：L1 快速 / L2 强化（理论·可行性卡点）/ L3 穷尽（创新性声明）",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 输出完整结果")
    parser.add_argument("--quiet", action="store_true", help="不输出过程日志")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    local_dir = Path(args.local_dir).expanduser().resolve()
    cache_dir = Path(args.cache_dir).expanduser().resolve() if args.cache_dir else None
    log: Log = _noop_log if args.quiet else _log_stderr

    if not local_dir.is_dir():
        log(f"[warn] 本地文献库不存在：{local_dir}")

    try:
        outcome = search_literature(
            query=args.query,
            max_results=args.max,
            local_dir=local_dir,
            cache_dir=cache_dir,
            from_year=args.from_year,
            to_year=args.to_year,
            refresh=args.refresh,
            use_cache=not args.no_cache,
            local_only=args.local_only,
            also_queries=args.also_query,
            exhaustive=args.exhaustive,
            level=args.level,
            limit=args.limit,
            log=log,
        )
    except Exception as exc:  # noqa: BLE001
        log(f"[error] 检索失败：{exc}")
        return 1

    payload = {
        "query": outcome["query"],
        "count": len(outcome["results"]),
        "total_results_before_limit": outcome["total_results_before_limit"],
        "truncated": outcome["truncated"],
        "results": outcome["results"],
        "retrieval_log": outcome["steps"],
        "rate_limit_log": outcome["rate_limit_log"] or ["本轮无 429"],
        "cache_updates": outcome["cache_updates"],
        "negative_search_record": outcome["negative_search_record"],
        "escalations": outcome["escalations"],
        "saturation": outcome["saturation"],
        "level_report": outcome["level_report"],
        "note": outcome["note"],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if outcome["arxiv_available"] else 2

    # 渲染阶段同样要防脏数据：本地库可能有 null 字段
    try:
        print(f"# 检索：{args.query}")
        print(f"# 命中：{payload['count']} 条"
              + (f"（截断自 {payload['total_results_before_limit']} 条）"
                 if payload["truncated"] else "") + "\n")
        print(_render_table(outcome["results"], limit=args.limit or 30))
        print("\n## 检索过程记录")
        for step in outcome["steps"]:
            extra = f"  错误: {step['error']}" if step.get("error") else ""
            print(f"- {step['step']}: {step['hits']} 条{extra}")
        print("\n## 429 等待日志 / arxiv 失败记录")
        for line in payload["rate_limit_log"]:
            print(f"- {line}")
        if payload["cache_updates"]:
            print("\n## 本地缓存更新记录")
            for line in payload["cache_updates"]:
                print(f"- {line}")
        if payload["escalations"]:
            print("\n## 范围扩大记录")
            for item in payload["escalations"]:
                print(f"- 第 {item['round']} 轮 [{item['action']}] max={item['max_results']}"
                      f" → 新增 {item['new_unique']} 条")
        print("\n## 负检索记录（每式命中数；why 需执行者填写）")
        for item in payload["negative_search_record"]:
            print(f"- 「{item['query']}」命中 {item['total_hits']} 条"
                  f"（来源 {item['by_source'] or '无'}）")
        sat, lvl = payload["saturation"], payload["level_report"]
        print("\n## 饱和与尽职调查")
        print(f"- 饱和：{'是' if sat['saturated'] else '否'}（{sat['reason']}）")
        actual = f"实际 检索式 {lvl['actual']['queries']} 个 / 结果 {lvl['actual']['results']} 条"
        if args.level:
            print(f"- 等级 {lvl['level']}：{'达成' if lvl['achieved'] else '未达成'}  {actual}")
            if lvl["gaps"]:
                print(f"- 未达标项：{', '.join(lvl['gaps'])}")
                if "saturated" in lvl["gaps"] and not args.exhaustive:
                    print("- 提示：L2/L3 要求达到饱和判据，请加上 --exhaustive 与更多 --also-query")
        else:
            # 未指定 --level 时不做等级判定，避免误报「L1 未达成」
            print(f"- 未指定 --level，未做等级判定；{actual}")
            print("- 提示：若本次检索要支撑创新性声明，请显式传 `--level L3 --exhaustive`")
        if payload["note"]:
            print(f"\n> ⚠️ {payload['note']}")
            print("> ⚠️ 检索未达饱和 —— 请记入 INDEX.md 的 Warnings。")
    except (AttributeError, TypeError, KeyError) as exc:
        log(f"[warn] 渲染失败（--json 仍可用）：{exc}")
        return 1

    return 0 if outcome["arxiv_available"] else 2


if __name__ == "__main__":
    sys.exit(main())
