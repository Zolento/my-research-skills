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
    4  环境不满足：当前解释器缺依赖，且找不到（或有多个）可用解释器
       —— 见 SKILL.md §0.2。**「依赖缺失」不等于「源不可用」。**
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import env_probe  # noqa: E402  （同目录模块，用于确认工作解释器）
import literature_sources  # noqa: E402  （同目录模块，多源适配器）

# ---------------------------------------------------------------------------
# 常量（与 literature-policy.md 保持一致）
# ---------------------------------------------------------------------------

MAX_RETRIES = 5
BASE_WAIT = 10  # 秒；退避序列 10 → 20 → 40 → 80 → 160

# 退出码（见模块 docstring）
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_SOURCE_DOWN = 2   # 在线源不可用，已回退本地结果（检索未达饱和）
EXIT_ENV = 4           # 环境不满足：依赖缺失 / 找不到可用解释器

# 防 re-exec 死循环：切换解释器后置位
ENV_REEXEC_FLAG = "RESEARCH_IDEA_PIPELINE_REEXEC"
DEFAULT_LOCAL_DIR = os.environ.get("RESEARCH_LOCAL_LITERATURE", "./docs/refs")
DEFAULT_CACHE_DIR = os.environ.get("RESEARCH_LIT_CACHE")  # 为空则由 <local-dir>/cache 决定
ALL_SOURCES_DOWN_NOTE = "所有在线源均不可用，以下结果仅来自本地库"
PARTIAL_SOURCE_NOTE = (
    "部分在线源不可用，结果不完整（含成功源的命中）；检索未达饱和"
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

# arxiv 域名解析到本地/私网地址 ⇒ 很可能处于代理或 hosts 劫持环境
# （Clash / Surge / 镜像站 / /etc/hosts）。详见 literature-policy.md §6.1。
ARXIV_HOSTS = ("arxiv.org", "export.arxiv.org")


def _address_scope(ip: str) -> str:
    """判定地址是否为非公网。公网可路由地址返回空串。"""
    try:
        addr = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return ""
    if addr.is_loopback:
        return "回环地址"
    if addr.is_unspecified:
        return "未指定地址 (0.0.0.0)"
    if addr.is_link_local:
        return "链路本地地址"
    if addr.is_private:
        return "私有网段地址"
    if not addr.is_global:
        return "非公网地址"
    return ""


def _resolve_host_ips(host: str) -> List[str]:
    """解析域名到 IP 列表；解析失败返回空列表（不抛异常）。"""
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return []
    return sorted({str(info[4][0]) for info in infos})


def detect_proxy_environment(hosts: Optional[List[str]] = None) -> Dict[str, Any]:
    """检查各在线源的域名是否解析到本地/私网地址。

    ★ 解析到本地 IP 是**代理环境**的强信号：DNS 被 hosts 文件或本地代理接管。
    此环境下 ① 结果可能来自代理缓存或镜像、与官方不同步；
    ② 429 与超时行为可能与直连不同，退避重试未必代表真实的限流；
    ③ 不得据此判定"源不可用 / 无人在研究"。

    Args:
        hosts: 要解析的域名列表；缺省为 arXiv 的两个域名（向后兼容）。

    Returns:
        {"detected": bool, "resolved": {host: [ip]}, "notes": [...], "unresolved": [...]}
    """
    targets = hosts or list(ARXIV_HOSTS)
    resolved: Dict[str, List[str]] = {}
    notes: List[str] = []
    for host in targets:
        ips = _resolve_host_ips(host)
        resolved[host] = ips
        flagged = [(ip, _address_scope(ip)) for ip in ips]
        flagged = [(ip, scope) for ip, scope in flagged if scope]
        if flagged:
            detail = "、".join(f"{ip}（{scope}）" for ip, scope in flagged)
            notes.append(
                f"{host} 解析到非公网地址：{detail} —— 可能存在代理 / hosts 劫持环境。"
                f"① 结果可能来自代理缓存或镜像，与官方不同步；"
                f"② 429 与超时行为可能与直连不同，退避重试未必代表真实限流；"
                f"③ 不得据此判定「源不可用」或「无人在研究」。"
            )
    return {
        "detected": bool(notes),
        "resolved": resolved,
        "notes": notes,
        "unresolved": [h for h, ips in resolved.items() if not ips],
    }


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


# ⚠️ 以下 `extract_metadata` / `search_arxiv` 已被 `literature_sources.ArxivSource`
#    取代（含 429 退避与 Atom HTTP 回退），本模块内部不再调用。保留仅为兼容
#    可能直接 import 它们的外部脚本；新代码请用 `literature_sources.REGISTRY["arxiv"]`。
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
    source: str = "arxiv",
) -> Path:
    """把某个源的结果写入 `<cache_dir>/<source>/{query_hash}.json`（键含检索参数）。

    ★ **按源分目录**：一个源失败/不可用时不会污染其他源的缓存。
    """
    directory = cache_dir / source
    directory.mkdir(parents=True, exist_ok=True)
    cache_path = directory / f"{query_hash(query, max_results, from_year, to_year)}.json"
    payload = {
        "query": query,
        "source": source,
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
    source: str = "arxiv",
) -> Optional[List[Dict[str, Any]]]:
    """读取某个源的查询缓存；结果标注 `sources=[source]` 且 `cache_hit: true`。

    缓存键含 max_results 与年份过滤，因此换了 --max / --from-year 不会命中旧结果。
    """
    cache_path = (cache_dir / source
                  / f"{query_hash(query, max_results, from_year, to_year)}.json")
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
            item["sources"] = [source]
            item["source"] = source
            item["cache_hit"] = True
    return results


# ---------------------------------------------------------------------------
# 编排：search_literature（对应 literature-policy.md 的伪代码）
# ---------------------------------------------------------------------------

# 尽职调查等级要求（见 literature-policy.md §3.1）
#
# ★ `min_online_sources` 只要求「至少一个在线源成功」——**不硬性要求三源全在**。
#   源覆盖是否完整由 `_level_report()["source_coverage"]["complete"]` **单独标记**，
#   它不作为等级门槛，但不完整时必须降级措辞并记入 Warnings（§9.2）。
LEVEL_REQUIREMENTS: Dict[str, Dict[str, Any]] = {
    "L1": {"min_queries": 1, "min_results": 10, "min_online_sources": 1},
    "L2": {"min_queries": 4, "min_results": 30, "min_online_sources": 1},
    "L3": {"min_queries": 8, "min_results": 60, "min_online_sources": 1},
}

LOCAL_ONLY_NOTE = (
    "仅使用本地库（--local-only）：违反默认检索规则——本地检索不得作为终点，"
    "本地结果不构成任何不存在性证据，**不得用于支撑创新性声明（T1）**。"
)


def source_is_ok(state: str) -> bool:
    """源是否可用于饱和计数与等级判定。"""
    return state in ("ok", "partial")


def is_degraded(sources_state: Dict[str, Dict[str, Any]]) -> bool:
    """是否有任一启用源降级（unavailable / partial）——决定退出码 2。"""
    return any(
        st.get("state") in ("unavailable", "partial")
        for st in sources_state.values()
    )


def _level_report(
    level: Optional[str],
    n_queries: int,
    n_results: int,
    sources_state: Dict[str, Dict[str, Any]],
    saturated: bool,
    escalation_attempted: bool = False,
) -> Dict[str, Any]:
    """按 §3.1 校验尽职调查等级达成情况。

    ⚠️ 饱和（§3.3）**只对 L2/L3 是硬要求**：L1 不要求扩检索。
    ⚠️ **源覆盖完整性不是门槛**：`min_online_sources` 只要求 ≥1 个在线源成功。
       覆盖不完整由 `source_coverage.complete = False` 标记，调用方据此降级措辞。
    """
    name = level or "L1"
    req = LEVEL_REQUIREMENTS.get(name, LEVEL_REQUIREMENTS["L1"])
    enabled = list(sources_state)
    ok = [s for s in enabled if source_is_ok(sources_state[s].get("state", "skipped"))]
    failed = [s for s in enabled if sources_state[s].get("state") == "unavailable"]

    checks = {
        "queries": n_queries >= req["min_queries"],
        "results": n_results >= req["min_results"],
        "online_sources": len(ok) >= req["min_online_sources"],
    }
    if name in ("L2", "L3"):
        checks["saturated"] = saturated

    return {
        "level": name,
        "requirements": req,
        "actual": {
            "queries": n_queries,
            "results": n_results,
            "online_sources_ok": len(ok),
            "online_sources_enabled": len(enabled),
            "saturated": saturated,
            "escalation_attempted": escalation_attempted,
        },
        "source_coverage": {
            "enabled": enabled,
            "ok": ok,
            "failed": failed,
            "complete": bool(enabled) and not failed and len(ok) == len(enabled),
        },
        "checks": checks,
        "achieved": all(checks.values()),
        "gaps": [key for key, passed in checks.items() if not passed],
    }


def _with_sources(record: Dict[str, Any], name: str) -> Dict[str, Any]:
    """保证记录带 `sources` 列表（本地记录没有；合并层依赖它）。"""
    item = dict(record)
    sources = item.get("sources")
    if not isinstance(sources, list) or not sources:
        item["sources"] = [item.get("source") or name]
    item.setdefault("source", item["sources"][0])
    return item


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
    sources: Optional[List[str]] = None,
    mailto: Optional[str] = None,
    venue: Optional[str] = None,
    cited_by: Optional[str] = None,
    references: Optional[str] = None,
) -> Dict[str, Any]:
    """本地 + 多源在线检索（每源状态、退避、缓存、引文追溯、扩检与饱和判定）。

    ★ 默认不因本地命中而短路：只要未显式 `local_only`，都会查询**全部启用源**。
    ★ 源覆盖「尽可能多」但**不硬性要求三源全在**（literature-policy.md §9.1）；
      任一源降级 → `degraded = True` → 退出码 2（用户决定）。

    Args:
        max_results: 传给每个在线源的单次查询条数上限（本地命中不受此限制）。
        sources: 启用的源名列表；None = 全部已实现源。
        venue: 会议/期刊名，经 OpenAlex 解析后过滤（A3 第 ③ 级自动化）。
        cited_by: 前向引文种子（谁引用了它）——DOI / arXiv ID / OpenAlex ID。
        references: 后向引文种子（它引用了谁）。

    Returns:
        {
          "query": str, "results": [...], "steps": [...],
          "rate_limit_log": [...], "cache_updates": [...], "note": str | None,
          "sources_state": {name: {state, hits, error}},
          "degraded": bool, "total_results_before_limit": int, "truncated": int,
          "negative_search_record": [...], "escalations": [...],
          "saturation": {...}, "level_report": {...}, "proxy_env": {...},
        }
    """
    cache_dir = cache_dir or (local_dir / "cache")
    steps: List[Dict[str, Any]] = []
    rate_limit_log: List[str] = []
    cache_updates: List[str] = []
    escalations: List[Dict[str, Any]] = []

    names = [n for n in (sources or literature_sources.DEFAULT_SOURCES)
             if n in literature_sources.REGISTRY]
    adapters = {n: literature_sources.REGISTRY[n] for n in names}
    tally: Dict[str, Dict[str, Any]] = {
        n: {"ok": 0, "fail": 0, "hits": 0, "error": None} for n in adapters
    }

    queries = [query] + [q for q in (also_queries or []) if q and q.strip()]
    local_by_query: Dict[str, List[Dict[str, Any]]] = {q: [] for q in queries}
    online_by_query: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        name: {q: [] for q in queries} for name in adapters
    }

    def capture(message: str) -> None:
        if message.startswith("["):
            rate_limit_log.append(message)
        log(message)

    def sources_state() -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for name, rec in tally.items():
            if rec["fail"] and not rec["ok"]:
                state = "unavailable"
            elif rec["fail"]:
                state = "partial"
            elif rec["ok"]:
                state = "ok"
            else:
                state = "skipped"
            out[name] = {"state": state, "hits": rec["hits"], "error": rec["error"]}
        return out

    def online_records() -> List[Dict[str, Any]]:
        return [h for name in adapters for hits in online_by_query[name].values() for h in hits]

    def for_query(q: str) -> List[Dict[str, Any]]:
        return [h for name in adapters for h in online_by_query[name].get(q, [])]

    def rebuild():
        return (
            literature_sources.merge_records(local_hits + online_records()),
            {q: literature_sources.merge_records(local_by_query[q] + for_query(q))
             for q in queries},
        )

    def try_cache(q: str, hits: List[Dict[str, Any]], mx: Optional[int],
                  fy: Optional[int], ty: Optional[int], source: str) -> None:
        """缓存写入失败**不得**中断检索（缓存目录只读/被占用很常见）。"""
        try:
            path = cache_results(q, hits, cache_dir, mx, fy, ty, source=source)
        except OSError as exc:
            log(f"[warn] 缓存写入失败（不影响本次结果）：{exc}")
            return
        cache_updates.append(f"{path} ({len(hits)} 条)")
        steps.append({"step": "cache_write", "source": source, "query": q, "hits": len(hits)})

    def query_source(name: str, q: str, mx: Optional[int], fy: Optional[int],
                     ty: Optional[int], venue_id: Optional[str]) -> Optional[List[Dict[str, Any]]]:
        """查询一个源（先查缓存）。失败返回 None 并累计 fail 计数——**不终止整体检索**。"""
        if use_cache and not refresh:
            cached = read_cache(q, cache_dir, mx, fy, ty, source=name)
            if cached is not None:
                tally[name]["ok"] += 1
                online_by_query[name][q].extend(cached)
                steps.append({"step": "cache", "source": name, "query": q, "hits": len(cached)})
                return cached
        try:
            hits = adapters[name].search(
                q, max_results=mx, from_year=fy, to_year=ty,
                log=capture, mailto=mailto, venue_id=venue_id,
            )
        except Exception as exc:  # noqa: BLE001 — 单源失败不得终止检索
            tally[name]["fail"] += 1
            tally[name]["error"] = str(exc)
            steps.append({"step": name, "query": q, "hits": 0, "error": str(exc)})
            rate_limit_log.append(f"[{name}-error] {exc}")
            return None
        tally[name]["ok"] += 1
        tally[name]["hits"] += len(hits)
        online_by_query[name][q].extend(hits)
        steps.append({"step": name, "query": q, "hits": len(hits)})
        try_cache(q, hits, mx, fy, ty, name)
        return hits

    # --- Step 1: 本地检索（纳入结果，但不作为终点） ---
    # 本地库只读一次，在所有检索式之间复用（避免 O(检索式 × 文件数) 的重复 IO）
    entries = _read_paper_entries(local_dir / "papers")
    for q in queries:
        hits = [_with_sources(h, "local")
                for h in search_local(q, local_dir, from_year, to_year, entries=entries)]
        steps.append({"step": "local", "query": q, "hits": len(hits)})
        local_by_query[q].extend(hits)

    local_hits = [hit for q in queries for hit in local_by_query[q]]

    if local_only:
        return _finish(
            query=query, merged=literature_sources.merge_records(local_hits),
            steps=steps, rate_limit_log=rate_limit_log, cache_updates=[],
            note=LOCAL_ONLY_NOTE, sources_state=sources_state(),
            per_query={q: literature_sources.merge_records(local_by_query[q]) for q in queries},
            escalations=[],
            saturation={"saturated": False, "reason": "local-only 模式下不做饱和判定"},
            level=level, limit=limit, escalation_attempted=False,
        )

    # --- 代理环境检查（覆盖所有启用源的域名）---
    proxy_env = detect_proxy_environment(literature_sources.all_hosts(list(adapters)))
    for note in proxy_env["notes"]:
        log(f"[proxy?] {note}")
    for host in proxy_env["unresolved"]:
        log(f"[warn] {host} 无法解析；若处于受限网络，请检查代理与 DNS 配置")

    # --- venue 解析（A3 第 ③ 级自动化：会议维度不再只能靠人工 --also-query）---
    venue_id: Optional[str] = None
    if venue:
        if "openalex" in adapters:
            try:
                venue_id = adapters["openalex"].resolve_venue_id(venue, log=capture, mailto=mailto)
            except Exception as exc:  # noqa: BLE001
                log(f"[venue] 解析失败：{exc}")
            if venue_id:
                escalations.append({
                    "round": 1,
                    "action": f"venue 过滤（A3 第 ③ 级）：{venue} → {venue_id}",
                    "max_results": max_results, "new_unique": 0,
                })
                # ★ 诚实说明：只有 OpenAlex 支持服务端 venue 过滤。
                #   arXiv 根本没有会议字段；CrossRef 本次未按 container-title 过滤。
                log("[venue] 注意：venue 过滤**只在 OpenAlex 上生效**（服务端过滤）；"
                    "arxiv 与 crossref 的命中未按会议过滤，仍会出现在合并结果里。"
                    "判断某条是否属于该会议请以结果里的 venue 字段为准，"
                    "不要因为用了 --venue 就假定结果已全部筛过。")
            else:
                log(f"[venue] 未能解析 venue「{venue}」；本次不做会议过滤")
        else:
            log("[venue] 未启用 openalex，无法做 venue 解析（A3 第 ③ 级需要 OpenAlex）")

    def run_round(mx: int, fy: Optional[int], ty: Optional[int],
                  vid: Optional[str]) -> set:
        """跑一轮：所有检索式 × 所有源。返回**本轮成功的源集合**。"""
        ok: set = set()
        for q in queries:
            for name in adapters:
                if query_source(name, q, mx, fy, ty, vid) is not None:
                    ok.add(name)
        return ok

    # --- Step 2: 第一轮（每个检索式 × 每个源）---
    first_round_ok = run_round(max_results, from_year, to_year, venue_id)
    merged, per_query = rebuild()

    # --- 引文追溯（阶段一：OpenAlex 前向 + 后向）---
    for label, ident, method in (
        ("cited_by", cited_by, "cited_by"),
        ("references", references, "references_of"),
    ):
        if not ident:
            continue
        if "openalex" not in adapters:
            log(f"[citation] 未启用 openalex，无法做引文追溯（{label}）")
            continue
        openalex = adapters["openalex"]
        try:
            work_id = openalex.resolve_work_id(ident, log=capture, mailto=mailto)
            if not work_id:
                log(f"[citation] 无法把「{ident}」解析成 OpenAlex work ID")
                continue
            hits = getattr(openalex, method)(work_id, max_results=max_results,
                                             log=capture, mailto=mailto)
            tally["openalex"]["ok"] += 1
            tally["openalex"]["hits"] += len(hits)
            online_by_query["openalex"].setdefault(f"citation:{label}:{ident}", []).extend(hits)
            steps.append({"step": f"citation_{label}", "query": ident, "hits": len(hits)})
            escalations.append({
                "round": 0,
                "action": f"引文追溯（A3 第 ⑤ 级）：{label} {ident} → {work_id}",
                "max_results": max_results, "new_unique": 0,
            })
            merged, per_query = rebuild()
        except Exception as exc:  # noqa: BLE001
            tally["openalex"]["fail"] += 1
            tally["openalex"]["error"] = str(exc)
            rate_limit_log.append(f"[openalex-error] 引文追溯失败（{label}）：{exc}")
            log(f"[citation] {label} 失败：{exc}")

    # --- Step 3: 范围扩大（A3）与饱和判定（§3.3）---
    saturated = False
    saturation_reason = "未启用 --exhaustive；单轮多源检索"
    if exhaustive:
        zero_streak = 0
        prev_ok = first_round_ok
        saturation_reason = "扩大检索轮次已用尽；新增仍非零，建议追加同义词检索式"
        plan = [
            {"round": 2, "action": "放宽时间范围（A3 第 ② 级）", "fy": None, "ty": None,
             "max": max_results},
            {"round": 3, "action": "增加 max_results（A3 第 ④ 级）", "fy": None, "ty": None,
             "max": max_results * 2},
            {"round": 4, "action": "增加 max_results（A3 第 ④ 级）", "fy": None, "ty": None,
             "max": max_results * 4},
            {"round": 5, "action": "增加 max_results（A3 第 ④ 级）", "fy": None, "ty": None,
             "max": max_results * 8},
        ]
        for step_plan in plan:
            before = len(merged)
            round_ok = run_round(step_plan["max"], step_plan["fy"], step_plan["ty"], venue_id)
            merged, per_query = rebuild()
            gained = len(merged) - before
            escalations.append({
                "round": step_plan["round"], "action": step_plan["action"],
                "max_results": step_plan["max"], "new_unique": gained,
            })
            steps.append({
                "step": f"escalation_{step_plan['round']}", "query": query,
                "hits": gained, "new_unique": gained,
            })
            if not round_ok:
                saturation_reason = "本轮没有任何在线源成功；检索未达饱和"
                break
            if round_ok != prev_ok:
                # ★ 可用源集合变了 → 之前的"零新增"证据作废，必须重新计数，
                #   否则"某源挂了三轮后恢复、恰好前两轮零新增"会被误判成饱和。
                zero_streak = 0
                prev_ok = round_ok
                saturation_reason = "可用源集合发生变化，饱和计数已重置"
                continue
            zero_streak = zero_streak + 1 if gained == 0 else 0
            if zero_streak >= 2:
                saturated = True
                saturation_reason = "连续两轮扩大检索均无新增，且可用源集合未变（§3.3 判据 1）"
                break

    # --- 回退说明：区分「部分源降级」与「所有在线源都不可用」---
    src_state = sources_state()
    degraded = is_degraded(src_state)
    if not degraded:
        note: Optional[str] = None
    elif any(s != "local" for h in merged for s in (h.get("sources") or [])):
        note = PARTIAL_SOURCE_NOTE
    else:
        note = ALL_SOURCES_DOWN_NOTE

    return _finish(
        query=query, merged=merged, steps=steps, rate_limit_log=rate_limit_log,
        cache_updates=cache_updates, note=note, sources_state=src_state,
        per_query=per_query, escalations=escalations,
        saturation={"saturated": saturated, "reason": saturation_reason},
        level=level, limit=limit, escalation_attempted=bool(escalations),
        proxy_env=proxy_env,
    )


def _finish(
    query: str,
    merged: List[Dict[str, Any]],
    steps: List[Dict[str, Any]],
    rate_limit_log: List[str],
    cache_updates: List[str],
    note: Optional[str],
    sources_state: Dict[str, Dict[str, Any]],
    per_query: Dict[str, List[Dict[str, Any]]],
    escalations: List[Dict[str, Any]],
    saturation: Dict[str, Any],
    level: Optional[str],
    limit: Optional[int],
    escalation_attempted: bool,
    proxy_env: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """组装返回值：套用 --limit、生成负检索记录与等级报告。"""
    total_before_limit = len(merged)
    truncated = 0
    if limit is not None and limit >= 0 and total_before_limit > limit:
        merged = merged[:limit]
        truncated = total_before_limit - limit

    gaps_level = _level_report(
        level, len(per_query), total_before_limit, sources_state,
        bool(saturation.get("saturated")), escalation_attempted,
    )
    return {
        "query": query,
        "results": merged,
        "steps": steps,
        "rate_limit_log": rate_limit_log or ["本轮无源级错误"],
        "cache_updates": cache_updates,
        "note": note,
        "sources_state": sources_state,
        "degraded": is_degraded(sources_state),
        "total_results_before_limit": total_before_limit,
        "truncated": truncated,
        "negative_search_record": _negative_record(list(per_query), per_query),
        "escalations": escalations,
        "saturation": saturation,
        "level_report": gaps_level,
        "proxy_env": proxy_env,
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
            for src in (item.get("sources") or [item.get("source") or "?"]):
                by_source[str(src)] = by_source.get(str(src), 0) + 1
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
    parser.add_argument("--query", "-q", default=None,
                        help="检索关键词或研究问题（--check-env 时可省略）")
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
    parser.add_argument(
        "--sources", default=None, metavar="LIST",
        help="启用的检索源，逗号分隔（arxiv,openalex,crossref）或 all。"
             "默认全部启用——源覆盖要求「尽可能多」；少指定时请在报告中给出理由",
    )
    parser.add_argument(
        "--venue", default=None, metavar="NAME",
        help="会议/期刊名（如 CVPR、NeurIPS）。经 OpenAlex 解析后过滤 —— "
             "这是 A3 第 ③ 级「扩大会议范围」的自动化，不再需要人工拼 --also-query",
    )
    parser.add_argument(
        "--cited-by", default=None, metavar="ID",
        help="前向引文追溯（谁引用了它）。ID 可为 DOI / arXiv ID / OpenAlex ID",
    )
    parser.add_argument(
        "--references", default=None, metavar="ID",
        help="后向引文追溯（它引用了谁）。ID 同上",
    )
    parser.add_argument(
        "--mailto", default=os.environ.get("RESEARCH_MAILTO"), metavar="EMAIL",
        help="OpenAlex / CrossRef 的 polite pool 联系方式（亦可用 RESEARCH_MAILTO）",
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="--local-only 的别名：不查询任何在线源",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 输出完整结果")
    parser.add_argument("--quiet", action="store_true", help="不输出过程日志")
    parser.add_argument(
        "--check-env", action="store_true",
        help="只做工作解释器 / 依赖自检并退出（无需 --query）；"
             "不满足时退出码 4。依赖缺失不等于源不可用，见 SKILL.md §0.2",
    )
    parser.add_argument(
        "--no-reexec", action="store_true",
        help="禁止自动切换到合格解释器（默认会切换并打印 [env] 行）",
    )
    return parser


def _env_gate(args: Any, log: Log, argv: List[str]) -> Optional[int]:
    """确认工作解释器（SKILL.md §0.2）。

    返回 None 表示"继续执行"；返回 int 表示"直接以该退出码结束"。

    当**当前解释器缺依赖**而**恰好有一个**合格候选时，切换到该解释器并重新执行本脚本
    （会打印 `[env]` 行，非静默）。多个候选取"不猜"，直接交回用户。

    ⚠️ **依赖缺失 ≠ 源不可用 ≠ 没人做过。** 这里失败绝不能写成"检索未达饱和"。
    """
    required = ("arxiv",)

    # --local-only / --offline 不调用任何在线源，因此不要求 arxiv
    if (args.local_only or args.offline) and not args.check_env:
        return None

    report = env_probe.discover(required)

    if args.check_env:
        print(env_probe.render(report))
        return EXIT_OK if report["chosen"] else EXIT_ENV

    current = report["current"]
    if any(env_probe._same(c["path"], current) and c["ok"] for c in report["candidates"]):
        return None

    chosen = report["chosen"]
    if chosen and not args.no_reexec and os.environ.get(ENV_REEXEC_FLAG) != "1":
        log(f"[env] 当前解释器缺少 {', '.join(required)}：{current}")
        log(f"[env] 已切换到 {chosen} 并重新执行（加 --no-reexec 可禁止该行为）")
        env = dict(os.environ)
        env[ENV_REEXEC_FLAG] = "1"
        try:
            os.execve(chosen, [chosen, str(Path(__file__).resolve()), *argv], env)
        except OSError as exc:  # 切换失败则按环境不满足处理
            log(f"[env] 切换解释器失败：{exc}")
        return EXIT_ENV

    log(env_probe.render(report))
    log(f"[env] 退出码 {EXIT_ENV}：环境不满足，**未发起任何检索**")
    if report["ambiguous"]:
        log("[env] 合格解释器不止一个，不自动选择 —— 请指定其一后重跑")
    else:
        log(f"[env] 请先安装依赖或指定解释器，例如："
            f"conda run -n <env> python {Path(__file__).name} ...")
    return EXIT_ENV


def main(argv: Optional[List[str]] = None) -> int:
    effective_argv = list(argv) if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.check_env and not args.query:
        parser.error("--query 是必填项（仅 --check-env 可省略）")
    log: Log = _noop_log if args.quiet else _log_stderr

    # --- 环境闸门：先确认工作解释器，再谈检索 ---
    gate = _env_gate(args, log, effective_argv)
    if gate is not None:
        return gate

    local_dir = Path(args.local_dir).expanduser().resolve()
    cache_dir = Path(args.cache_dir).expanduser().resolve() if args.cache_dir else None

    if not local_dir.is_dir():
        log(f"[warn] 本地文献库不存在：{local_dir}")

    local_only = args.local_only or args.offline
    source_names, unknown_sources = literature_sources.resolve_source_names(args.sources)
    if unknown_sources:
        log(f"[warn] 未知的源已忽略：{', '.join(unknown_sources)}"
            f"（可用：{', '.join(sorted(literature_sources.REGISTRY))}）")
    if not local_only and not source_names:
        log("[warn] 没有可用的在线源；本次等价于 --local-only")
        local_only = True
    if not local_only and args.sources and len(source_names) < len(literature_sources.DEFAULT_SOURCES):
        log(f"[warn] 只启用了 {len(source_names)}/"
            f"{len(literature_sources.DEFAULT_SOURCES)} 个源 —— 源覆盖要求「尽可能多」，"
            f"请在报告中写明少用源的理由")

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
            local_only=local_only,
            also_queries=args.also_query,
            exhaustive=args.exhaustive,
            level=args.level,
            limit=args.limit,
            log=log,
            sources=source_names,
            mailto=args.mailto,
            venue=args.venue,
            cited_by=args.cited_by,
            references=args.references,
        )
    except Exception as exc:  # noqa: BLE001
        log(f"[error] 检索失败：{exc}")
        return EXIT_ERROR

    payload = {
        "query": outcome["query"],
        "count": len(outcome["results"]),
        "total_results_before_limit": outcome["total_results_before_limit"],
        "truncated": outcome["truncated"],
        "results": outcome["results"],
        "retrieval_log": outcome["steps"],
        "sources": outcome["sources_state"],
        "degraded": outcome["degraded"],
        "rate_limit_log": outcome["rate_limit_log"],
        "cache_updates": outcome["cache_updates"],
        "negative_search_record": outcome["negative_search_record"],
        "escalations": outcome["escalations"],
        "saturation": outcome["saturation"],
        "level_report": outcome["level_report"],
        "note": outcome["note"],
        "proxy_env": outcome.get("proxy_env"),
    }
    exit_code = EXIT_SOURCE_DOWN if outcome["degraded"] else EXIT_OK

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return exit_code

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
        print("\n## 源状态")
        for name, st in payload["sources"].items():
            mark = {"ok": "✅", "partial": "⚠️", "unavailable": "❌", "skipped": "—"}.get(
                st["state"], "?")
            extra = f"  错误: {st['error']}" if st.get("error") else ""
            print(f"- {mark} {name}: {st['state']}（{st['hits']} 条）{extra}")
        lvl_cov = payload["level_report"].get("source_coverage", {})
        if lvl_cov and not lvl_cov.get("complete", True):
            print(f"- ⚠️ 源覆盖不完整：成功 {lvl_cov.get('ok')} / 启用 {lvl_cov.get('enabled')}"
                  f" → 结论措辞须降级，并记入 INDEX.md 的 Warnings")

        print("\n## 源日志（429 / 失败 / 代理）")
        for line in payload["rate_limit_log"]:
            print(f"- {line}")
        proxy = payload.get("proxy_env") or {}
        if proxy.get("detected"):
            print("\n## 代理环境提示（arxiv 域名解析到本地 IP）")
            for line in proxy["notes"]:
                print(f"- ⚠️ {line}")
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
        actual = (f"实际 检索式 {lvl['actual']['queries']} 个 / 结果 {lvl['actual']['results']} 条"
                  f" / 在线源 {lvl['actual']['online_sources_ok']}"
                  f"⁄{lvl['actual']['online_sources_enabled']}")
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
        return EXIT_ERROR

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
