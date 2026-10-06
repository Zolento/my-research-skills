#!/usr/bin/env python3
"""test_render_status.py — render_status.py 的离线测试（stdlib unittest，**不联网**）

为什么需要它
------------
目录规范 DI-4 把 STATUS.md 定义为 `f(research-state.json)`，并要求它**不是第二份真相**。
这条 invariant 的机械判据只有一条：**幂等**。
所以本测试的核心不是"输出好看"，而是：

    同一份 state 渲染两次 → 逐字节一致；
    磁盘文件被手改后 `--check` 必须报 3。

若这条测试不存在，"STATUS = f(state)" 就只是散文。
"""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import shutil
import tempfile
import unittest

import render_status as rs

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "research-state.template.json"


class TestRenderStatus(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="render-status-"))
        self.route = "T"
        state_dir = self.tmp / ".research-idea-pipeline" / "routes" / self.route
        state_dir.mkdir(parents=True)
        self.state_path = state_dir / "research-state.json"
        shutil.copyfile(TEMPLATE, self.state_path)
        self.status_path = self.tmp / "routes" / self.route / "STATUS.md"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _render(self, check: bool = False) -> int:
        """跑 main()，吞掉它的 stdout/stderr —— 离线测试必须静默。"""
        argv = ["--root", str(self.tmp), "--route", self.route]
        if check:
            argv.append("--check")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return rs.main(argv)

    # ---- 幂等：DI-4 的机械判据 ----

    def test_render_is_idempotent(self):
        self.assertEqual(self._render(), rs.EXIT_OK)
        first = self.status_path.read_bytes()
        self.assertEqual(self._render(), rs.EXIT_OK)
        self.assertEqual(first, self.status_path.read_bytes(), "两次渲染必须逐字节一致")

    def test_render_is_pure_function_of_state(self):
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(rs.render(state, self.route), rs.render(state, self.route))

    def test_state_version_change_moves_output(self):
        before = rs.render(json.loads(self.state_path.read_text(encoding="utf-8")), self.route)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        state["state_version"] = 47
        after = rs.render(state, self.route)
        self.assertNotEqual(before, after)
        self.assertIn("S0047", after)

    # ---- --check 闸门 ----

    def test_check_passes_when_fresh(self):
        self._render()
        self.assertEqual(self._render(check=True), rs.EXIT_OK)

    def test_check_fails_when_status_is_stale(self):
        self._render()
        self.status_path.write_text("被手改过\n", encoding="utf-8")
        self.assertEqual(self._render(check=True), rs.EXIT_HARD)

    def test_check_fails_when_status_missing(self):
        self.assertEqual(self._render(check=True), rs.EXIT_HARD)

    # ---- 环境侧：必须是 4，不能与硬违规 3 混为一谈 ----

    def test_missing_state_is_env_error(self):
        self.state_path.unlink()
        self.assertEqual(self._render(), rs.EXIT_ENV)

    def test_bad_json_is_env_error(self):
        self.state_path.write_text("{not json", encoding="utf-8")
        self.assertEqual(self._render(), rs.EXIT_ENV)

    # ---- 投影内容：人类入口必须真的反映状态 ----

    def test_status_projects_core_sections(self):
        self._render()
        text = self.status_path.read_text(encoding="utf-8")
        for title in ("Current thesis", "Strongest supported findings", "Active hypotheses",
                      "Critical uncertainties", "Open critical attacks", "Active experiments",
                      "Most important negative findings", "Next recommended actions",
                      "Current decision"):
            self.assertIn(f"## {title}", text, f"缺少人类入口节：{title}")

    def test_status_declares_itself_a_projection(self):
        self._render()
        text = self.status_path.read_text(encoding="utf-8")
        self.assertIn("不是第二份真相", text)
        self.assertIn("禁止手改", text)

    def test_thesis_comes_from_claim_root(self):
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        root_claim = next(c for c in state["claims"] if c.get("parent") is None)
        self.assertIn(root_claim["statement"][:20], rs.render(state, self.route))


if __name__ == "__main__":
    unittest.main()
