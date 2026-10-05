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
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Sequence, Tuple

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import env_probe  # noqa: E402
import literature_search as ls  # noqa: E402


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
    base = {"local_only": False, "check_env": False, "no_reexec": True}
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
