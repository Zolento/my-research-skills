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
  6. --exhaustive 执行 D3 范围扩大直到饱和（§3.3）；
     --level L1|L2|L3 校验尽职调查等级（§3.1）；
     --also-query 追加同义词/上位词/否定式检索式。

用法：
    # 默认：本地 + arxiv 并集
    python literature_search.py --query "diffusion model combinatorial optimization" --max 20

    # 创新性声明：L3 穷尽级 + 自动扩检 + 追加检索式
    python literature_search.py --query "discrete diffusion combinatorial optimization" \
        --level L3 --exhaustive \
        --also-query "score-based generative model discrete optimization" \
        --also-query "limits of diffusion model combinatorial optimization"

    # 离线：显式只用本地（会打印规则违反提示）
    python literature_search.py --query "..." --local-only

退出码：
    0  正常（本地 + arxiv 成功）
    1  硬错误（参数错误、本地库不可读等）
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
DEFAULT_LOCAL_DIR = os.environ.get("RESEARCH_LOCAL_LITERATURE", "./local_literature")
RATE_LIMIT_NOTE = "arxiv 暂时不可用，以下结果仅来自本地库"

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-]+", re.IGNORECASE)
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


def tokenize(text: str) -> List[str]:
    """小写分词并去停用词，用于本地关键词匹配。"""
    if not text:
        return []
    return [t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _STOPWORDS]


def query_hash(query: str) -> str:
    """稳定的查询哈希。

    注意：Python 内建 hash() 受 PYTHONHASHSEED 影响，跨进程不稳定，不能用于
    缓存文件名（见 literature-policy.md §2.1）。此处使用 md5。
    """
    return hashlib.md5(query.strip().lower().encode("utf-8")).hexdigest()[:16]


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
) -> List[Dict[str, Any]]:
    """在本地文献库中按关键词匹配标题 / 摘要 / 关键词 / 全文。

    命中条目标注 source="local"。
    """
    q_tokens = set(tokenize(query))
    if not q_tokens:
        return []

    hits: List[Dict[str, Any]] = []
    for record in _read_paper_entries(local_dir / "papers"):
        year = record.get("year")
        if from_year is not None and isinstance(year, int) and year < from_year:
            continue
        if to_year is not None and isinstance(year, int) and year > to_year:
            continue

        # 字段权重：标题 > 关键词 > 摘要 > 全文
        weighted_fields = [
            (record.get("title", ""), 3.0),
            (" ".join(record.get("keywords", []) or []), 2.5),
            (record.get("abstract", ""), 1.5),
            (record.get("_fulltext", ""), 1.0),
        ]

        score = 0.0
        matched: set = set()
        for text, weight in weighted_fields:
            field_tokens = set(tokenize(str(text)))
            overlap = q_tokens & field_tokens
            if overlap:
                matched |= overlap
                score += weight * len(overlap)

        # 短语整体命中额外加权
        haystack = " ".join(
            str(record.get(k, "")) for k in ("title", "abstract", "_fulltext")
        ).lower()
        if query.strip().lower() in haystack:
            score += 5.0

        if score > 0:
            hit = {k: v for k, v in record.items() if not k.startswith("_")}
            hit["_score"] = round(score, 3)
            hit["matched_terms"] = sorted(matched)
            hits.append(hit)

    hits.sort(key=lambda r: r.get("_score", 0.0), reverse=True)
    return hits


# ---------------------------------------------------------------------------
# Step 2：arxiv 检索（含 429 指数退避）
# ---------------------------------------------------------------------------

def _status_of(exc: BaseException) -> Optional[int]:
    """从异常中尽力提取 HTTP 状态码。

    arxiv 包并不稳定导出 arxiv.HTTPError；实际多为 urllib.error.HTTPError
    （.code）或带 .response.status_code 的异常。详见 literature-policy.md §2.1。
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
    match = re.search(r"\b(429|4\d{2}|5\d{2})\b", str(exc))
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
                year = meta.get("year")
                if from_year is not None and isinstance(year, int) and year < from_year:
                    continue
                if to_year is not None and isinstance(year, int) and year > to_year:
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

def cache_results(query: str, results: List[Dict[str, Any]], cache_dir: Path) -> Path:
    """把 arxiv 结果写入 <cache_dir>/{query_hash}.json。"""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{query_hash(query)}.json"
    payload = {
        "query": query,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "count": len(results),
        "results": results,
    }
    with cache_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return cache_path


def read_cache(query: str, cache_dir: Path) -> Optional[List[Dict[str, Any]]]:
    """读取查询缓存；缓存中的 arxiv 结果仍标注 source="arxiv"。"""
    cache_path = cache_dir / f"{query_hash(query)}.json"
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
    "本地结果不构成任何不存在性证据。"
)


def _level_report(
    level: Optional[str],
    n_queries: int,
    n_results: int,
    arxiv_available: bool,
    saturated: bool,
) -> Dict[str, Any]:
    """按 §3.1 校验尽职调查等级达成情况。"""
    name = level or "L1"
    req = LEVEL_REQUIREMENTS.get(name, LEVEL_REQUIREMENTS["L1"])
    checks = {
        "queries": n_queries >= req["min_queries"],
        "results": n_results >= req["min_results"],
        "arxiv": arxiv_available or not req["require_arxiv"],
        "saturated": saturated,
    }
    return {
        "level": name,
        "requirements": req,
        "actual": {
            "queries": n_queries,
            "results": n_results,
            "arxiv_available": arxiv_available,
            "saturated": saturated,
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
    log: Log = _noop_log,
) -> Dict[str, Any]:
    """本地 + arxiv 合并检索（含 429 退避、缓存、扩检与饱和判定）。

    ★ 默认不因本地命中而短路：只要未显式 `local_only`，都会查询 arxiv。
      这是 literature-policy.md §0 对原规范的强化。

    Returns:
        {
          "query": str,
          "results": [...],              # 本地 + arxiv 并集（含 source 标注）
          "steps": [...],                # 检索过程记录
          "rate_limit_log": [...],       # 429 等待日志 / arxiv 失败记录
          "cache_updates": [...],
          "note": str | None,
          "arxiv_available": bool,
          "negative_search_record": [...],  # 负检索记录（L2/L3 必需）
          "escalations": [...],          # D3 范围扩大记录
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

    def capture(message: str) -> None:
        if message.startswith("[429]") or message.startswith("[arxiv-error]"):
            rate_limit_log.append(message)
        log(message)

    # --- Step 1: 本地检索（纳入结果，但不作为终点） ---
    local_hits: List[Dict[str, Any]] = []
    for q in queries:
        hits = search_local(q, local_dir, from_year, to_year)
        steps.append({"step": "local", "query": q, "hits": len(hits)})
        local_hits.extend(hits)

    if local_only:
        merged = _merge_unique(local_hits)
        return {
            "query": query,
            "results": merged,
            "steps": steps,
            "rate_limit_log": rate_limit_log or ["本轮无 429"],
            "cache_updates": [],
            "note": LOCAL_ONLY_NOTE,
            "arxiv_available": True,
            "negative_search_record": _negative_record(queries, merged),
            "escalations": [],
            "saturation": {"saturated": False, "reason": "local-only 模式下不做饱和判定"},
            "level_report": _level_report(level, len(queries), len(merged), False, False),
        }

    # --- Step 2: arxiv 检索（每个检索式一次；命中缓存则跳过） ---
    arxiv_hits: List[Dict[str, Any]] = []
    arxiv_available = True
    for q in queries:
        if use_cache and not refresh:
            cached = read_cache(q, cache_dir)
            if cached is not None:
                steps.append({"step": "cache", "query": q, "hits": len(cached)})
                arxiv_hits.extend(cached)
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
        arxiv_hits.extend(hits)
        if hits:
            cache_path = cache_results(q, hits, cache_dir)
            cache_updates.append(f"{cache_path} ({len(hits)} 条)")
            steps.append({"step": "cache_write", "query": q, "hits": len(hits)})

    merged = _merge_unique(local_hits, arxiv_hits)

    # --- Step 3: 范围扩大（D3）与饱和判定（§3.3） ---
    saturated = False
    saturation_reason = "未启动扩大检索"
    if exhaustive and arxiv_available and not refresh:
        zero_streak = 0
        plan = [
            {"round": 2, "action": "放宽时间范围", "from_year": None, "to_year": None, "max": max_results},
            {"round": 3, "action": "增加 max_results", "from_year": None, "to_year": None, "max": max_results * 2},
            {"round": 4, "action": "再次增加 max_results", "from_year": None, "to_year": None, "max": max_results * 4},
            {"round": 5, "action": "再次增加 max_results", "from_year": None, "to_year": None, "max": max_results * 8},
        ]
        for step_plan in plan:
            before = len(merged)
            round_hits: List[Dict[str, Any]] = []
            failed = False
            for q in queries:
                try:
                    round_hits.extend(
                        search_arxiv(
                            q, max_results=step_plan["max"],
                            from_year=step_plan["from_year"], to_year=step_plan["to_year"],
                            log=capture,
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    arxiv_available = False
                    steps.append({"step": "arxiv", "query": q, "hits": 0, "error": str(exc)})
                    failed = True
                    break
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
    elif exhaustive and refresh:
        saturation_reason = "--refresh 已开启，扩大检索跳过"
    elif arxiv_available:
        saturation_reason = "未启用 --exhaustive；本地+arxiv 单轮检索"

    if not arxiv_available:
        note: Optional[str] = RATE_LIMIT_NOTE
    else:
        note = None

    return {
        "query": query,
        "results": merged,
        "steps": steps,
        "rate_limit_log": rate_limit_log or ["本轮无 429"],
        "cache_updates": cache_updates,
        "note": note,
        "arxiv_available": arxiv_available,
        "negative_search_record": _negative_record(queries, merged),
        "escalations": escalations,
        "saturation": {"saturated": saturated, "reason": saturation_reason},
        "level_report": _level_report(
            level, len(queries), len(merged), arxiv_available, saturated,
        ),
    }


def _negative_record(
    queries: List[str], results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """负检索记录：每个检索式命中了什么、来自哪里。

    用于支撑"据本次检索未见"这类措辞（literature-policy.md §2.1）。
    """
    by_source: Dict[str, int] = {}
    for item in results:
        src = str(item.get("source", "?"))
        by_source[src] = by_source.get(src, 0) + 1
    return [
        {"query": q, "total_hits": len(results), "by_source": by_source}
        for q in queries
    ]


def _merge_unique(*groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按标题/URL 去重合并，保留首次出现的来源标注。"""
    merged: List[Dict[str, Any]] = []
    seen: set = set()
    for group in groups:
        for item in group:
            key = (
                str(item.get("url") or "").strip().lower()
                or re.sub(r"\W+", "", str(item.get("title", "")).lower())
            )
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
        authors = r.get("authors") or []
        first_author = authors[0] if authors else "?"
        year = r.get("year") or (str(r.get("published", ""))[:4] or "?")
        venue = r.get("venue") or "arXiv"
        title = r.get("title", "").strip() or "(无标题)"
        lines.append(f"{i:>2}. [{first_author} et al., {venue} {year}] {title}")
        lines.append(f"    来源: {r.get('source', '?')}    {r.get('url', '')}")
    if len(results) > limit:
        lines.append(f"… 另有 {len(results) - limit} 条（用 --json 查看全部）")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Research Idea Pipeline 文献检索（先本地，后 arxiv，429 指数退避）",
    )
    parser.add_argument("--query", "-q", required=True, help="检索关键词或研究问题")
    parser.add_argument("--max", "-n", type=int, default=20, help="最多返回条数（默认 20）")
    parser.add_argument("--from-year", type=int, default=None, help="起始年份（含）")
    parser.add_argument("--to-year", type=int, default=None, help="结束年份（含）")
    parser.add_argument(
        "--local-dir", default=DEFAULT_LOCAL_DIR,
        help=f"本地文献库根目录（默认 {DEFAULT_LOCAL_DIR}，亦可用 RESEARCH_LOCAL_LITERATURE）",
    )
    parser.add_argument("--cache-dir", default=None, help="缓存目录（默认 <local-dir>/cache）")
    parser.add_argument("--refresh", action="store_true", help="强制跳过缓存（仍查本地与 arxiv）")
    parser.add_argument("--no-cache", action="store_true", help="不使用缓存（仍会写入）")
    parser.add_argument(
        "--local-only", action="store_true",
        help="★ 显式只用本地库（离线场景）。违反默认检索规则，结果不构成不存在性证据",
    )
    parser.add_argument(
        "--also-query", action="append", default=[], metavar="QUERY",
        help="追加检索式（同义词/上位词/否定式），可重复；用于 D3 第 ① 级扩大",
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
            log=log,
        )
    except Exception as exc:  # noqa: BLE001
        log(f"[error] 检索失败：{exc}")
        return 1

    payload = {
        "query": outcome["query"],
        "count": len(outcome["results"]),
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
    else:
        print(f"# 检索：{args.query}")
        print(f"# 命中：{payload['count']} 条\n")
        print(_render_table(outcome["results"]))
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
        sat, lvl = payload["saturation"], payload["level_report"]
        print("\n## 饱和与尽职调查")
        print(f"- 饱和：{'是' if sat['saturated'] else '否'}（{sat['reason']}）")
        print(f"- 等级 {lvl['level']}：{'达成' if lvl['achieved'] else '未达成'}"
              f"  实际 检索式 {lvl['actual']['queries']} 个 / 结果 {lvl['actual']['results']} 条")
        if lvl["gaps"]:
            print(f"- 未达标项：{', '.join(lvl['gaps'])}")
        if payload["note"]:
            print(f"\n> ⚠️ {payload['note']}")
            print("> ⚠️ 检索未达饱和 —— 请记入 INDEX.md 的 Warnings。")

    return 0 if outcome["arxiv_available"] else 2


if __name__ == "__main__":
    sys.exit(main())
