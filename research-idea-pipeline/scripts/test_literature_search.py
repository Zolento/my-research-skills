#!/usr/bin/env python3
"""test_literature_search.py — 离线测试（stdlib unittest，**不联网**）

运行：
    python -m unittest discover -s scripts -p "test_*.py" -v
    python scripts/test_literature_search.py

设计原则
--------
**全部离线。** 网络测试必然 flaky，因此：

* 环境发现：注入候选列表与探测结果，不真的执行 conda / 子进程；
* 多源检索（后续步骤）：用 stub Source，不发任何 HTTP 请求。

覆盖点
------
1. 环境发现的选择规则（当前可用 / 唯一 / 多个 → ambiguous / 零个）
2. `_env_gate` 的四种分支与退出码
3. （后续）多源合并、饱和判据、退出码
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Sequence, Tuple

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import env_probe  # noqa: E402
import literature_search as ls  # noqa: E402
import literature_sources as src  # noqa: E402
import zotero_client  # noqa: E402


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

class _FakeProbe:
    """把 env_probe 的候选收集与依赖探测替换成注入数据。"""

    def __init__(self, candidates: Sequence[Tuple[str, str]],
                 versions: Dict[str, Dict[str, Any]]):
        self.candidates = [(origin, Path(path)) for origin, path in candidates]
        self.versions = versions
        self._orig_collect = None
        self._orig_probe = None

    def __enter__(self) -> "_FakeProbe":
        self._orig_collect = env_probe._collect_candidates
        self._orig_probe = env_probe.probe_modules
        env_probe._collect_candidates = lambda start: self.candidates  # type: ignore[assignment]
        env_probe.probe_modules = (  # type: ignore[assignment]
            lambda path, modules, timeout=30.0: dict(self.versions.get(str(path), {}))
        )
        return self

    def __exit__(self, *exc: Any) -> None:
        env_probe._collect_candidates = self._orig_collect  # type: ignore[assignment]
        env_probe.probe_modules = self._orig_probe  # type: ignore[assignment]


A = "/opt/envA/bin/python"
B = "/opt/envB/bin/python"
CUR = "/usr/bin/python3"

V_OK_A = {A: {"arxiv": "4.0.1"}}
V_OK_A_B = {A: {"arxiv": "4.0.1"}, B: {"arxiv": "3.0.0"}}
V_NONE: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# 1. 环境发现
# ---------------------------------------------------------------------------

class EnvDiscoverTests(unittest.TestCase):

    def test_current_interpreter_wins_when_it_qualifies(self):
        cands = [("conda-env", A), ("current", CUR)]
        versions = {A: {"arxiv": "4.0.1"}, CUR: {"arxiv": "4.0.1"}}
        with _FakeProbe(cands, versions):
            r = env_probe.discover(("arxiv",), Path("/tmp"), current=CUR)
        self.assertEqual(r["chosen"], CUR)
        self.assertFalse(r["ambiguous"])
        self.assertIn("无需切换", r["reason"])

    def test_unique_qualified_candidate_is_chosen(self):
        cands = [("conda-env", A), ("current", CUR)]
        with _FakeProbe(cands, V_OK_A):
            r = env_probe.discover(("arxiv",), Path("/tmp"), current=CUR)
        self.assertEqual(r["chosen"], A)
        self.assertFalse(r["ambiguous"])
        self.assertIn("唯一合格候选", r["reason"])

    def test_multiple_qualified_is_ambiguous_and_not_guessed(self):
        cands = [("conda-env", A), ("conda-env", B), ("current", CUR)]
        with _FakeProbe(cands, V_OK_A_B):
            r = env_probe.discover(("arxiv",), Path("/tmp"), current=CUR)
        self.assertIsNone(r["chosen"])
        self.assertTrue(r["ambiguous"])
        self.assertEqual(len(r["qualified"]), 2)

    def test_no_qualified_candidate(self):
        cands = [("conda-env", A), ("current", CUR)]
        with _FakeProbe(cands, V_NONE):
            r = env_probe.discover(("arxiv",), Path("/tmp"), current=CUR)
        self.assertIsNone(r["chosen"])
        self.assertFalse(r["ambiguous"])
        self.assertTrue(r["needs_python"])
        self.assertIn("未找到", r["reason"])

    def test_missing_modules_are_reported(self):
        cands = [("current", CUR)]
        versions = {CUR: {"arxiv": "4.0.1", "pypdf": None}}
        with _FakeProbe(cands, versions):
            r = env_probe.discover(("arxiv", "pypdf"), Path("/tmp"), current=CUR)
        self.assertEqual(r["candidates"][0]["missing"], ["pypdf"])
        self.assertFalse(r["candidates"][0]["ok"])

    def test_render_warns_that_missing_dep_is_not_source_failure(self):
        cands = [("current", CUR)]
        with _FakeProbe(cands, V_NONE):
            r = env_probe.discover(("arxiv",), Path("/tmp"), current=CUR)
        text = env_probe.render(r)
        self.assertIn("依赖缺失 ≠ 源不可用 ≠ 没人做过", text)
        self.assertIn(str(env_probe.EXIT_ENV), text)

    def test_render_shows_chosen(self):
        cands = [("conda-env", A), ("current", CUR)]
        with _FakeProbe(cands, V_OK_A):
            r = env_probe.discover(("arxiv",), Path("/tmp"), current=CUR)
        text = env_probe.render(r)
        self.assertIn("选定", text)
        self.assertIn(A, text)


# ---------------------------------------------------------------------------
# 2. 环境闸门
# ---------------------------------------------------------------------------

def _args(**kw: Any) -> SimpleNamespace:
    base = {"local_only": False, "offline": False, "check_env": False, "no_reexec": True}
    base.update(kw)
    return SimpleNamespace(**base)


_NOOP = lambda _msg: None  # noqa: E731


class EnvGateTests(unittest.TestCase):

    def _with_discover(self, report: Dict[str, Any]):
        original = env_probe.discover
        env_probe.discover = lambda *a, **k: report  # type: ignore[assignment]

        class _Ctx:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                env_probe.discover = original  # type: ignore[assignment]

        return _Ctx()

    def _report(self, chosen, candidates):
        return {
            "modules": ["arxiv"], "current": CUR, "candidates": candidates,
            "qualified": [c["path"] for c in candidates if c["ok"]],
            "chosen": chosen, "ambiguous": False, "needs_python": chosen is None,
            "reason": "test",
        }

    def test_gate_passes_when_current_qualifies(self):
        report = self._report(CUR, [{"path": CUR, "ok": True, "origin": "current",
                                     "modules": {"arxiv": "4"}, "python": "3.12", "missing": []}])
        with self._with_discover(report):
            gate = ls._env_gate(_args(), _NOOP, [])
        self.assertIsNone(gate)

    def test_gate_exit_4_when_unsatisfied_and_no_reexec(self):
        report = self._report(None, [{"path": CUR, "ok": False, "origin": "current",
                                      "modules": {"arxiv": None}, "python": "3.14", "missing": ["arxiv"]}])
        with self._with_discover(report):
            gate = ls._env_gate(_args(), _NOOP, [])
        self.assertEqual(gate, ls.EXIT_ENV)

    def test_check_env_returns_0_when_chosen(self):
        report = self._report(A, [{"path": A, "ok": True, "origin": "conda-env",
                                   "modules": {"arxiv": "4"}, "python": "3.12", "missing": []}])
        with self._with_discover(report), contextlib.redirect_stdout(io.StringIO()):
            gate = ls._env_gate(_args(check_env=True), _NOOP, [])
        self.assertEqual(gate, ls.EXIT_OK)

    def test_check_env_returns_4_when_unsatisfied(self):
        report = self._report(None, [])
        report["candidates"] = []
        with self._with_discover(report), contextlib.redirect_stdout(io.StringIO()):
            gate = ls._env_gate(_args(check_env=True), _NOOP, [])
        self.assertEqual(gate, ls.EXIT_ENV)

    def test_local_only_skips_the_gate_entirely(self):
        called = {"n": 0}
        original = env_probe.discover

        def _spy(*a, **k):
            called["n"] += 1
            return {}

        env_probe.discover = _spy  # type: ignore[assignment]
        try:
            gate = ls._env_gate(_args(local_only=True), _NOOP, [])
        finally:
            env_probe.discover = original  # type: ignore[assignment]
        self.assertIsNone(gate)
        self.assertEqual(called["n"], 0, "--local-only 不应触发环境探测")


# ---------------------------------------------------------------------------
# 3. 多源：身份键与合并
# ---------------------------------------------------------------------------

#: 同一篇论文，三个源各出一条（arXiv 无 venue / CrossRef 权威 / OpenAlex 带引文）
_SAME_PAPER = [
    {"title": "Diffusion Models in Vision: A Survey", "year": 2023,
     "arxiv_id": "2209.04747v2", "doi": None, "venue": None, "sources": ["arxiv"],
     "url": "http://arxiv.org/abs/2209.04747"},
    {"title": "Diffusion models in vision: a survey", "year": 2023,
     "doi": "10.1109/TPAMI.2023.3261988", "arxiv_id": "2209.04747",
     "venue": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
     "openalex_id": "W4360884927", "cited_by_count": 1862,
     "references": ["W1", "W2"], "sources": ["openalex"]},
    {"title": "Diffusion Models in Vision: A Survey", "year": 2023,
     "doi": "https://doi.org/10.1109/tpami.2023.3261988",
     "venue": "IEEE Trans. Pattern Anal. Mach. Intell.", "sources": ["crossref"],
     "authors": ["F. Croitoru", "D. Oneata"]},
]


class IdentityTests(unittest.TestCase):

    def test_doi_normalization_strips_url_and_case(self):
        self.assertEqual(
            src.normalize_doi("https://doi.org/10.1109/TPAMI.2023.3261988"),
            "10.1109/tpami.2023.3261988",
        )
        self.assertEqual(src.normalize_doi("doi:10.1/ABC"), "10.1/abc")

    def test_arxiv_id_normalization_strips_version_and_url(self):
        self.assertEqual(src.normalize_arxiv_id("2209.04747v2"), "2209.04747")
        self.assertEqual(src.normalize_arxiv_id("https://arxiv.org/abs/2209.04747"),
                         "2209.04747")
        self.assertEqual(src.normalize_arxiv_id("http://arxiv.org/pdf/2209.04747.pdf"),
                         "2209.04747")

    def test_openalex_id_extraction(self):
        self.assertEqual(src.normalize_openalex_id("https://openalex.org/W4360884927"),
                         "W4360884927")

    def test_identity_keys_cover_all_axes(self):
        keys = src.identity_keys(_SAME_PAPER[1])
        self.assertTrue(any(k.startswith("doi:") for k in keys))
        self.assertTrue(any(k.startswith("arxiv:") for k in keys))
        self.assertTrue(any(k.startswith("oa:") for k in keys))
        self.assertTrue(any(k.startswith("t:") for k in keys))


class MergeTests(unittest.TestCase):

    def test_same_paper_from_three_sources_merges_to_one(self):
        merged = src.merge_records(_SAME_PAPER)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["sources"], ["crossref", "openalex", "arxiv"])

    def test_venue_uses_authority_order(self):
        merged = src.merge_records(_SAME_PAPER)[0]
        self.assertEqual(merged["venue_from"], "crossref")
        self.assertIn("IEEE Trans", merged["venue"])

    def test_authors_pick_longest_list(self):
        merged = src.merge_records(_SAME_PAPER)[0]
        self.assertEqual(merged["authors"], ["F. Croitoru", "D. Oneata"])

    def test_derived_source_alias_is_first_of_sources(self):
        merged = src.merge_records(_SAME_PAPER)[0]
        self.assertEqual(merged["source"], merged["sources"][0])

    def test_merge_keeps_citation_data(self):
        merged = src.merge_records(_SAME_PAPER)[0]
        self.assertEqual(merged["cited_by_count"], 1862)
        self.assertEqual(merged["references"], ["W1", "W2"])

    def test_unrelated_paper_is_not_merged(self):
        records = _SAME_PAPER + [{"title": "A Completely Different Paper",
                                  "year": 2020, "sources": ["crossref"]}]
        self.assertEqual(len(src.merge_records(records)), 2)

    def test_records_without_title_are_dropped(self):
        self.assertEqual(src.merge_records([{"year": 2020}, {"title": None}]), [])

    def test_title_only_match_still_merges(self):
        """两个源都没有 DOI/arXiv ID 时，靠"标题+年份"合并。"""
        records = [
            {"title": "Some Unusual Paper Title", "year": 2021, "sources": ["arxiv"]},
            {"title": "Some   Unusual  Paper Title!", "year": 2021, "sources": ["crossref"]},
        ]
        merged = src.merge_records(records)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["sources"], ["crossref", "arxiv"])


class SourceRegistryTests(unittest.TestCase):

    def test_default_is_all_implemented_sources(self):
        names, unknown = src.resolve_source_names(None)
        self.assertEqual(names, list(src.DEFAULT_SOURCES))
        self.assertEqual(unknown, [])
        self.assertIn("all", ["all"])   # "all" 与 "*" 等价
        self.assertEqual(src.resolve_source_names("all")[0], list(src.DEFAULT_SOURCES))
        self.assertEqual(src.resolve_source_names("*")[0], list(src.DEFAULT_SOURCES))

    def test_subset_and_unknown(self):
        names, unknown = src.resolve_source_names("arxiv,crossref,bogus")
        self.assertEqual(names, ["arxiv", "crossref"])
        self.assertEqual(unknown, ["bogus"])

    def test_dedup_and_case(self):
        names, _ = src.resolve_source_names("Arxiv,arxiv")
        self.assertEqual(names, ["arxiv"])

    def test_all_hosts_unions(self):
        hosts = src.all_hosts(["arxiv", "openalex", "crossref"])
        self.assertIn("export.arxiv.org", hosts)
        self.assertIn("api.openalex.org", hosts)
        self.assertIn("api.crossref.org", hosts)
        self.assertEqual(len(hosts), len(set(hosts)))


class OpenAlexNormalizeTests(unittest.TestCase):

    def test_arxiv_repository_is_not_treated_as_venue(self):
        work = {
            "id": "https://openalex.org/W1",
            "display_name": "T", "publication_year": 2024,
            "primary_location": {"source": {"display_name": "arXiv (Cornell University)"},
                                 "landing_page_url": "http://arxiv.org/abs/2502.08696"},
        }
        record = src.REGISTRY["openalex"]._normalize(work)
        self.assertIsNone(record["venue"])
        self.assertEqual(record["arxiv_id"], "2502.08696")

    def test_real_venue_is_kept(self):
        work = {
            "id": "https://openalex.org/W2", "display_name": "T",
            "publication_year": 2023,
            "primary_location": {"source": {"display_name": "Neural Information Processing Systems"}},
        }
        self.assertEqual(src.REGISTRY["openalex"]._normalize(work)["venue"],
                         "Neural Information Processing Systems")


class YearRangeTests(unittest.TestCase):

    def test_year_range_inclusive(self):
        self.assertTrue(src._in_range(2024, 2020, 2025))
        self.assertTrue(src._in_range(2020, 2020, 2025))
        self.assertTrue(src._in_range(2025, 2020, 2025))
        self.assertFalse(src._in_range(2019, 2020, 2025))
        self.assertFalse(src._in_range(2026, 2020, 2025))

    def test_unknown_year_only_passes_without_filter(self):
        self.assertTrue(src._in_range(None, None, None))
        self.assertFalse(src._in_range(None, 2020, None))


# ---------------------------------------------------------------------------
# 4. 源状态与尽职调查等级
# ---------------------------------------------------------------------------

class BottleneckRetrievalTests(unittest.TestCase):
    """方法补检索复用 refresh/exhaustive，不能把旧缓存或失败源当作更新。"""

    def test_trigger_tables_have_the_same_ids_and_levels(self):
        root = SCRIPTS.parent
        paths = [root / "SKILL.md", root / "README.md", root / "references" / "literature-policy.md",
                 root / "references" / "phase-r2-r5-field-mapping-retrieval.md"]
        expected = {f"T{n}": "L3" if n in (1, 4, 6) else "L2"
                    for n in range(1, 9)}
        for path in paths:
            with self.subTest(path=path):
                rows = re.findall(r"^\| (?:\*\*)?(T\d+)(?:\*\*)? \| (.+)$",
                                  path.read_text(), re.M)
                levels = {key: re.search(r"L[123]", row.split("|")[-2]).group()
                          for key, row in rows}
                self.assertEqual(levels, expected)
        l2 = next(line for line in (root / "references" / "literature-policy.md").read_text().splitlines()
                  if line.startswith("| **L2** |"))
        self.assertIn("T8", l2)

    def test_web_search_precedes_local_and_multisource_in_instruction_copies(self):
        root = SCRIPTS.parent
        for path in (root / "SKILL.md", root / "references" / "literature-policy.md"):
            with self.subTest(path=path):
                text = path.read_text()
                self.assertLess(text.index("Step 0: 先尝试 web search"), text.index("Step 1:"))
                self.assertLess(text.index("Step 1:"), text.index("Step 2:"))
        phase = (root / "references" / "phase-r2-r5-field-mapping-retrieval.md").read_text()
        self.assertLess(phase.index("## A0. 先尝试 web search"), phase.index("## A1."))
        self.assertLess(phase.index("## A1."), phase.index("## A2."))
        for relative in ("README.md", "references/phase-r3-r6-discovery.md"):
            with self.subTest(path=relative):
                text = (root / relative).read_text()
                self.assertTrue(any(policy in text for policy in (
                    "先尝试 web search，再本地与多源",
                    "Attempt web search first, then query the local library and multiple sources.",
                )), "Web search must precede local and multisource retrieval in either language")

    def test_refresh_queries_all_sources_and_expansion_rounds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queries = ["mechanism bottleneck", "analogous constraint"]
            adapters = {name: mock.Mock(hosts=[], search=mock.Mock(return_value=[{
                "title": f"New method {name}", "doi": f"10.1234/{name}",
                "year": 2026, "sources": [name]}]))
                for name in ("arxiv", "openalex", "crossref")}
            for name in adapters:
                for query in queries:
                    ls.cache_results(query, [{"title": "Old result", "doi": "10.1234/old"}],
                                     root / "cache", 10, 2020, 2026, source=name)
            with mock.patch.dict(src.REGISTRY, adapters, clear=True), \
                    mock.patch.object(zotero_client, "probe", return_value=None), \
                    mock.patch.object(ls, "detect_proxy_environment",
                                      return_value={"notes": [], "unresolved": []}), \
                    mock.patch.object(ls, "read_cache", side_effect=AssertionError("stale cache used")):
                outcome = ls.search_literature(queries[0], local_dir=root, max_results=10,
                                    from_year=2020, to_year=2026, refresh=True,
                                    also_queries=queries[1:], exhaustive=True,
                                    sources=list(adapters))
            for adapter in adapters.values():
                self.assertEqual(adapter.search.call_count, 6)
            self.assertTrue(outcome["saturation"]["saturated"])
            self.assertEqual({record["doi"] for record in outcome["results"]},
                             {f"10.1234/{name}" for name in adapters})
            self.assertFalse(any(step["step"] == "cache" for step in outcome["steps"]))

    def test_failed_refresh_does_not_report_cached_results_as_online_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ls.cache_results("bottleneck", [{"title": "Old result"}], root / "cache", 10,
                             source="arxiv")
            adapter = mock.Mock(hosts=[], search=mock.Mock(side_effect=OSError("offline")))
            with mock.patch.dict(src.REGISTRY, {"arxiv": adapter}, clear=True), \
                    mock.patch.object(zotero_client, "probe", return_value=None), \
                    mock.patch.object(ls, "detect_proxy_environment",
                                      return_value={"notes": [], "unresolved": []}):
                outcome = ls.search_literature("bottleneck", local_dir=root, max_results=10,
                                    refresh=True, exhaustive=True, level="L2", sources=["arxiv"])
            self.assertEqual(outcome["sources_state"]["arxiv"]["state"], "unavailable")
            self.assertFalse(outcome["saturation"]["saturated"])
            self.assertFalse(outcome["level_report"]["achieved"])
            self.assertEqual(outcome["results"], [])

    def test_cli_source_degradation_is_independent_of_saturation(self):
        with tempfile.TemporaryDirectory() as directory:
            records = [{"title": f"Method {i}", "doi": f"10.1234/method{i}",
                        "year": 2026, "sources": ["arxiv"]} for i in range(30)]
            adapters = {
                "arxiv": mock.Mock(hosts=[], search=mock.Mock(return_value=records)),
                "openalex": mock.Mock(hosts=[], search=mock.Mock(side_effect=OSError("offline"))),
            }
            out = io.StringIO()
            with mock.patch.dict(src.REGISTRY, adapters, clear=True), \
                    mock.patch.object(zotero_client, "probe", return_value=None), \
                    mock.patch.object(ls, "_env_gate", return_value=None), \
                    mock.patch.object(ls, "detect_proxy_environment",
                                      return_value={"notes": [], "unresolved": []}), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = ls.main(["-q", "mechanism", "--local-dir", directory,
                                "--sources", "arxiv,openalex", "--max", "30",
                                "--refresh", "--exhaustive", "--level", "L2", "--json",
                                "--also-query", "constraint", "--also-query", "analogy",
                                "--also-query", "failure"])
            payload = json.loads(out.getvalue())
            self.assertEqual(code, ls.EXIT_SOURCE_DOWN)
            self.assertTrue(payload["degraded"])
            self.assertTrue(payload["saturation"]["saturated"])
            self.assertTrue(payload["level_report"]["achieved"])
            self.assertFalse(payload["level_report"]["source_coverage"]["complete"])

class SourceStateTests(unittest.TestCase):

    def test_is_degraded_true_for_partial_or_unavailable(self):
        self.assertFalse(ls.is_degraded({"a": {"state": "ok"}}))
        self.assertFalse(ls.is_degraded({"a": {"state": "skipped"}}))
        self.assertTrue(ls.is_degraded({"a": {"state": "unavailable"}}))
        self.assertTrue(ls.is_degraded({"a": {"state": "partial"}}))
        self.assertTrue(ls.is_degraded({"a": {"state": "ok"}, "b": {"state": "unavailable"}}))

    def test_degraded_any_source_means_exit_code_2(self):
        """用户决定：**任一**源降级就算降级（退出码 2），不是全部失败才算。"""
        state = {"arxiv": {"state": "ok"}, "crossref": {"state": "unavailable"}}
        self.assertTrue(ls.is_degraded(state))


class LevelReportTests(unittest.TestCase):

    ALL_OK = {"arxiv": {"state": "ok"}, "openalex": {"state": "ok"},
              "crossref": {"state": "ok"}}

    def test_l1_does_not_require_saturation(self):
        r = ls._level_report("L1", 1, 10, {"arxiv": {"state": "ok"}}, False)
        self.assertTrue(r["achieved"])

    def test_l2_requires_saturation(self):
        r = ls._level_report("L2", 4, 30, {"arxiv": {"state": "ok"}}, False)
        self.assertFalse(r["achieved"])
        self.assertIn("saturated", r["gaps"])

    def test_needs_at_least_one_online_source(self):
        dead = {"arxiv": {"state": "unavailable"}, "openalex": {"state": "unavailable"}}
        r = ls._level_report("L1", 1, 10, dead, False)
        self.assertFalse(r["achieved"])
        self.assertIn("online_sources", r["gaps"])

    def test_incomplete_coverage_does_not_block_l3(self):
        """★ 用户决定：三源全在**不**是硬性要求；覆盖不完整只是单独标记。"""
        state = {"arxiv": {"state": "ok"}, "openalex": {"state": "unavailable"},
                 "crossref": {"state": "ok"}}
        r = ls._level_report("L3", 8, 60, state, True)
        self.assertTrue(r["achieved"], "覆盖不完整不应阻止 L3 达成")
        self.assertFalse(r["source_coverage"]["complete"])
        self.assertEqual(r["source_coverage"]["failed"], ["openalex"])
        self.assertEqual(r["source_coverage"]["ok"], ["arxiv", "crossref"])

    def test_coverage_complete_when_all_ok(self):
        r = ls._level_report("L3", 8, 60, self.ALL_OK, True)
        self.assertTrue(r["source_coverage"]["complete"])
        self.assertTrue(r["achieved"])

    def test_unmet_queries_and_results_are_reported(self):
        r = ls._level_report("L3", 2, 5, {"arxiv": {"state": "ok"}}, True)
        self.assertIn("queries", r["gaps"])
        self.assertIn("results", r["gaps"])


# ---------------------------------------------------------------------------
# 5. 本地源：Zotero 优先，不可用回落 docs/refs/
# ---------------------------------------------------------------------------

#: Zotero Local API 原始条目：一条命中 + 一条无关 + 一条 PDF 子条目（应被过滤）
_ZOTERO_ITEMS: List[Dict[str, Any]] = [
    {"key": "ZOTKEY01", "version": 1, "data": {
        "itemType": "journalArticle",
        "title": "MRI Reconstruction with Diffusion Models",
        "creators": [{"firstName": "Ada", "lastName": "Lovelace"}],
        "abstractNote": "Diffusion priors for accelerated MRI reconstruction.",
        "date": "2023-05-01",
        "publicationTitle": "Medical Image Analysis",
        "url": "https://example.org/mri",
        "DOI": "10.1000/mri.2023",
        "tags": [{"tag": "MRI"}, {"tag": "diffusion"}],
    }},
    {"key": "ZOTKEY02", "version": 1, "data": {
        "itemType": "journalArticle",
        "title": "Unrelated Topic About Birds",
        "date": "1999",
    }},
    {"key": "ATTACH1", "version": 1, "data": {
        "itemType": "attachment", "contentType": "application/pdf",
        "parentItem": "ZOTKEY01",
    }},
]


def _write_refs_paper(papers: Path, name: str, record: Dict[str, Any]) -> None:
    papers.mkdir(parents=True, exist_ok=True)
    (papers / f"{name}.json").write_text(json.dumps(record), encoding="utf-8")


class ZoteroLocalBackendTests(unittest.TestCase):
    """不依赖真实 Zotero：probe / fetch_items 全部用 stub。"""

    def test_zotero_registered_but_not_a_default_online_source(self):
        self.assertIn("zotero", src.REGISTRY)
        self.assertNotIn("zotero", src.DEFAULT_SOURCES)
        adapter = src.REGISTRY["zotero"]
        self.assertEqual(adapter.hosts, ())
        self.assertEqual(adapter.requires, ())
        self.assertEqual(adapter.polite_delay, 0.0)
        self.assertEqual(adapter.name, "zotero")

    def test_zotero_url_resolution_order(self):
        self.assertEqual(ls._zotero_base_url("http://x:1/api"),
                         ("http://x:1/api", "--zotero-url"))
        with mock.patch.dict(os.environ, {ls.ZOTERO_ENV_VAR: "http://env:2/api"}):
            self.assertEqual(ls._zotero_base_url(None),
                             ("http://env:2/api", ls.ZOTERO_ENV_VAR))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(ls._zotero_base_url(None),
                             (zotero_client.DEFAULT_LOCAL_API, "默认地址"))

    def test_zotero_unreachable_falls_back_to_refs_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_refs_paper(root / "papers", "classic", {
                "title": "MRI Reconstruction Retrospective", "year": 2019,
                "abstract": "A classic MRI reconstruction approach.",
            })
            with mock.patch.object(zotero_client, "probe", return_value=None) as probe:
                outcome = ls.search_literature(
                    "MRI reconstruction", local_dir=root, local_only=True)
            self.assertEqual(probe.call_count, 1)
            self.assertEqual(outcome["local_backend"], "refs")
            self.assertIsNotNone(outcome["local_warning"])
            self.assertIn("Zotero", outcome["local_warning"])
            self.assertEqual([r["title"] for r in outcome["results"]],
                             ["MRI Reconstruction Retrospective"])
            self.assertEqual(outcome["results"][0]["source"], "local")

    def test_zotero_reachable_uses_zotero_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_refs_paper(root / "papers", "classic", {
                "title": "MRI Reconstruction Retrospective", "year": 2019,
            })
            with mock.patch.object(zotero_client, "probe", return_value="SID"), \
                    mock.patch.object(zotero_client, "fetch_items",
                                      return_value=_ZOTERO_ITEMS) as fetch:
                outcome = ls.search_literature(
                    "MRI reconstruction diffusion", local_dir=root, local_only=True)
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(outcome["local_backend"], "zotero")
            self.assertIsNone(outcome["local_warning"])
            titles = [r["title"] for r in outcome["results"]]
            self.assertIn("MRI Reconstruction with Diffusion Models", titles)
            self.assertNotIn("MRI Reconstruction Retrospective", titles)
            self.assertNotIn("Unrelated Topic About Birds", titles)
            self.assertEqual(outcome["results"][0]["sources"], ["local"])

    def test_local_format_refs_skips_zotero_even_when_reachable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_refs_paper(root / "papers", "classic", {
                "title": "MRI Reconstruction Retrospective", "year": 2019,
            })
            with mock.patch.object(zotero_client, "probe",
                                   side_effect=AssertionError("probe must not run")), \
                    mock.patch.object(zotero_client, "fetch_items",
                                      side_effect=AssertionError("fetch must not run")):
                outcome = ls.search_literature(
                    "MRI reconstruction", local_dir=root, local_only=True,
                    local_format="refs")
            self.assertEqual(outcome["local_backend"], "refs")
            self.assertEqual([r["title"] for r in outcome["results"]],
                             ["MRI Reconstruction Retrospective"])

    def test_local_format_zotero_when_down_is_a_clear_nonzero_error(self):
        with tempfile.TemporaryDirectory() as directory:
            err = io.StringIO()
            with mock.patch.object(zotero_client, "probe", return_value=None), \
                    mock.patch.object(ls, "_env_gate", return_value=None), \
                    contextlib.redirect_stderr(err), \
                    contextlib.redirect_stdout(io.StringIO()):
                code = ls.main(["-q", "MRI reconstruction", "--local-only",
                                "--local-dir", directory, "--local-format", "zotero"])
            self.assertEqual(code, ls.EXIT_ERROR)
            self.assertNotEqual(code, ls.EXIT_OK)
            self.assertIn("Zotero", err.getvalue())

    def test_zotero_source_search_filters_year_and_ranks_overlap(self):
        source = src.REGISTRY["zotero"]
        with mock.patch.object(zotero_client, "probe", return_value="SID"), \
                mock.patch.object(zotero_client, "fetch_items",
                                  return_value=_ZOTERO_ITEMS):
            hits = source.search("diffusion MRI", max_results=10, from_year=2020,
                                 to_year=2024, log=lambda _m: None)
        self.assertEqual([h["title"] for h in hits],
                         ["MRI Reconstruction with Diffusion Models"])
        self.assertEqual(hits[0]["sources"], ["local"])
        self.assertTrue(hits[0]["matched_terms"])

    def test_zotero_source_raises_unavailable_when_probe_fails(self):
        source = src.REGISTRY["zotero"]
        with mock.patch.object(zotero_client, "probe", return_value=None):
            with self.assertRaises(zotero_client.ZoteroUnavailable):
                source.search("mri", max_results=5, from_year=None, to_year=None,
                              log=lambda _m: None)


class FulltextLayerTests(unittest.TestCase):
    """第二层（Zotero 原生全文索引）接线。

    纪律：默认关闭；模块缺失 / Zotero 不可用一律降级，**不失败**；
    命中只能标 `indexed_fulltext`，不得据此产生页码。
    """

    def _client_stub(self, server_id="SID"):
        fake = mock.MagicMock()
        fake.server_id = server_id
        return fake

    def test_layer_disabled_returns_reason_or_disabled(self):
        """未启用时不产生 fulltext_layer（保持原有输出结构）。

        必须 hermetic：patch 掉本地源解析，避免依赖运行中的 Zotero。
        """
        with mock.patch.object(ls, "resolve_local_entries",
                               return_value=([], "refs", None)), \
                mock.patch.object(ls, "_fulltext_layer") as layer:
            result = ls.search_literature(
                "q", local_only=True, fulltext=False,
                local_dir=Path(tempfile.mkdtemp()), log=lambda _m: None)
        layer.assert_not_called()
        self.assertIsNone(result.get("fulltext_layer"))

    def test_layer_degrades_when_module_missing(self):
        with mock.patch.dict(sys.modules, {"zotero_fulltext": None}):
            out = ls._fulltext_layer(["q"], log=lambda _m: None)
        self.assertFalse(out["available"])
        self.assertIsNotNone(out["reason"])
        self.assertEqual(out["hits"], [])

    def test_layer_degrades_when_zotero_unreachable(self):
        fake_module = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"zotero_fulltext": fake_module}), \
                mock.patch("zotero_write.WriteClient") as wc:
            wc.return_value = self._client_stub(server_id=None)
            out = ls._fulltext_layer(["q"], log=lambda _m: None)
        self.assertFalse(out["available"])
        self.assertIn("不可达", out["reason"])

    def test_layer_collects_hits_per_query_and_marks_verification(self):
        hit = {"title": "T", "doi": "10.1/x", "zotero_key": "K",
               "verification": "indexed_fulltext", "page": None}
        fake_module = mock.MagicMock()
        fake_module.search_indexed.return_value = [hit]
        with mock.patch.dict(sys.modules, {"zotero_fulltext": fake_module}), \
                mock.patch("zotero_write.WriteClient") as wc:
            wc.return_value = self._client_stub()
            out = ls._fulltext_layer(["a", "b"], log=lambda _m: None)
        self.assertTrue(out["available"])
        self.assertEqual(len(out["hits"]), 2, "每个检索式各命中一次")
        self.assertIn("a", out["by_query"])
        # 索引命中绝不带页码
        self.assertIsNone(out["hits"][0]["page"])
        self.assertEqual(out["hits"][0]["verification"], "indexed_fulltext")

    def test_single_query_failure_does_not_abort_layer(self):
        fake_module = mock.MagicMock()
        fake_module.search_indexed.side_effect = [
            RuntimeError("boom"), [{"title": "T2", "verification": "indexed_fulltext"}]]
        with mock.patch.dict(sys.modules, {"zotero_fulltext": fake_module}), \
                mock.patch("zotero_write.WriteClient") as wc:
            wc.return_value = self._client_stub()
            out = ls._fulltext_layer(["bad", "good"], log=lambda _m: None)
        self.assertTrue(out["available"])
        self.assertEqual(len(out["hits"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)