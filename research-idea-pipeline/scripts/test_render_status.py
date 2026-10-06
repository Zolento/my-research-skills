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


# ---------------------------------------------------------------------------
# 生成物 ↔ 模板 的节集合一致性（DI-4 的机械判据）
# ---------------------------------------------------------------------------

class TestStatusSectionParity(unittest.TestCase):
    """`render_status.py` 产出的节，必须与 `templates/STATUS.md` 声明的节**完全一致**。

    这是 DI-4 的另一半：幂等保证"同一份 state 两次生成一致"，
    本类保证"生成器的结构与人类模板不脱钩"。二者缺一，
    `STATUS.md` 就会慢慢漂成"生成器一份、文档一份"。
    """

    ROOT = pathlib.Path(__file__).resolve().parent.parent

    def _sections(self, text: str):
        return [line.strip() for line in text.splitlines() if line.startswith("## ")]

    def test_render_sections_equal_template_sections(self):
        template = (self.ROOT / "templates" / "STATUS.md").read_text(encoding="utf-8")
        state = json.loads(
            (self.ROOT / "templates" / "research-state.template.json").read_text(encoding="utf-8")
        )
        rendered = rs.render(state, "T")
        self.assertEqual(
            self._sections(rendered), self._sections(template),
            msg="生成物的节与 STATUS 模板声明的节不一致（顺序与名称都算）",
        )

    def _spec_sections(self):
        """从 `references/project-layout.md` §4.2 的「固定节」代码块里抽节名。"""
        text = (self.ROOT / "references" / "project-layout.md").read_text(encoding="utf-8")
        start = text.index("**固定节（顺序不得改）：**")
        block = text[start:]
        block = block[block.index("```") + 3:]
        block = block[: block.index("```")]
        return self._sections(block)

    def test_three_way_section_parity(self):
        """规格 / 模板 / 生成物**三方**的节集合必须逐项相等。

        project-layout §4.2 明文声称"三者一致"—— 本用例就是那句话的机械落点。
        缺了它，规格、模板、生成器会各自漂移，而没人发现。
        """
        spec = self._spec_sections()
        template = self._sections(
            (self.ROOT / "templates" / "STATUS.md").read_text(encoding="utf-8"))
        state = json.loads(
            (self.ROOT / "templates" / "research-state.template.json").read_text(encoding="utf-8"))
        rendered = self._sections(rs.render(state, "T"))
        self.assertEqual(spec, template, msg="规格 §4.2 与 templates/STATUS.md 节集合不一致")
        self.assertEqual(spec, rendered, msg="规格 §4.2 与 render_status.py 输出节集合不一致")

    def test_no_wall_clock_in_rendered_status(self):
        """幂等的硬边界：投影里不得出现墙钟时间（否则两次生成必然不同）。"""
        import datetime
        state = json.loads(
            (self.ROOT / "templates" / "research-state.template.json").read_text(encoding="utf-8")
        )
        rendered = rs.render(state, "T")
        today = datetime.date.today().isoformat()
        self.assertNotIn(today, rendered, "投影中不得含当天日期")
        self.assertNotIn("最后更新", rendered, "投影中不得含'最后更新'字段")
