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

    # ---- content-shape parity（只核节名会漏掉「模板表格 / renderer bullet」这种分叉）----

    @staticmethod
    def _bodies(text: str):
        """返回 {节名: [节体行]}，跳过第一个 `##` 之前的内容。"""
        bodies, name, buf = {}, None, []
        for line in text.splitlines():
            if line.startswith("## "):
                if name is not None:
                    bodies[name] = buf
                name, buf = line[3:].strip(), []
            elif name is not None:
                buf.append(line)
        if name is not None:
            bodies[name] = buf
        return bodies

    @staticmethod
    def _shape(body):
        rows = [line for line in body if line.strip()]
        if not rows:
            return "empty"
        if rows == ["_（无）_"]:
            return "empty-marker"
        if all(line.lstrip().startswith("- ") for line in rows):
            return "bullets"
        if all(line.lstrip().startswith("|") for line in rows):
            return "table"
        return "prose"

    def _content_fixture(self):
        """每节都有内容的 state —— 否则形状不可分辨（空节只能是 empty-marker）。"""
        return {
            "state_version": 3,
            "claims": [{"id": "C1", "statement": "x", "parent": None, "status": "supported"}],
            "hypotheses": [{"id": "H1", "statement": "y", "status": "elite"}],
            "uncertainties": [{"id": "U1", "question": "q", "importance": "critical",
                               "uncertainty": "high", "status": "open",
                               "cheapest_discriminating_test": "X1"}],
            "experiments": [{"id": "X1", "status": "planned"}],
            "failures": [{"id": "F1", "kind": "inconclusive", "what": "w"}],
            "assurance": [{"kill_condition": "k", "discriminating_test": "X1",
                           "verification_tier": "T0"}],
            "repairs": [{"flaw": "f", "disposition": "RUN_TEST",
                         "state_delta": "d", "closure": "OPEN"}],
            "decision": {"verdict": "continue"},
        }

    def test_content_shape_parity(self):
        rendered = rs.render(self._content_fixture(), "A")
        template = (self.ROOT / "templates" / "STATUS.md").read_text(encoding="utf-8")
        rendered_bodies = self._bodies(rendered)
        template_bodies = self._bodies(template)
        self.assertEqual(list(template_bodies), list(rendered_bodies),
                         msg="模板与 renderer 的节名或顺序不一致")
        for name in rendered_bodies:
            self.assertEqual(
                self._shape(template_bodies[name]), self._shape(rendered_bodies[name]),
                msg=f"节「{name}」的块形态与 renderer 不一致 —— "
                    "模板必须与 renderer 同形（renderer 是 executable specification）")

    def test_fixture_makes_every_section_non_empty(self):
        # 守卫：fixture 退化成空 state 时，形状检查会静默变成「全是 empty-marker」
        shapes = {name: self._shape(body)
                  for name, body in self._bodies(rs.render(self._content_fixture(), "A")).items()}
        self.assertNotIn("empty-marker", shapes.values(), msg=f"fixture 有节为空：{shapes}")

    def test_template_uses_no_tables(self):
        template = (self.ROOT / "templates" / "STATUS.md").read_text(encoding="utf-8")
        tables = [name for name, body in self._bodies(template).items()
                  if self._shape(body) == "table"]
        self.assertEqual(tables, [], msg=f"模板里这些节仍是表格：{tables}")

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
