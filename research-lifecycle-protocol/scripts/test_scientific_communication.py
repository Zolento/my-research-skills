#!/usr/bin/env python3
"""test_scientific_communication.py — semantic checks for the reporting contract.

These tests do not merely look for headings. They check that the shipped policy and the
representative X88–X90 examples actually carry the required scientific content:

* the five-part order is present and the examples use it;
* a method report answers the six depth questions with substantive mechanism content;
* a terminated process is described as non-completion, not as a negative result;
* quantitative evidence keeps its uncertainty and its scope boundary;
* default reports do not leak PID / GPU UUID / long paths;
* the audit example expands those details without changing the science;
* the two policies are wired into the runtime contract documents.
"""

from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def between(text: str, start: str, end: str) -> str:
    left = text.index(start) + len(start)
    return text[left:text.index(end, left)]


class TestCommunicationPolicy(unittest.TestCase):

    def setUp(self):
        self.policy = read("references/scientific-communication-policy.md")

    def test_the_five_parts_are_ordered_and_dynamic(self):
        positions = [self.policy.index(name) for name in
                     ("Problem", "Insight", "Method", "Evidence", "Decision")]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("五段是**顺序**，不是等长模板", self.policy)
        self.assertIn("按研究阶段调整篇幅", self.policy)
        self.assertIn("不得为了凑满五段而生成空泛内容", self.policy)

    def test_method_depth_has_the_six_questions(self):
        section = between(self.policy, "## 2. Method-depth 检查", "## 3. 证据纪律")
        questions = re.findall(r"^\d+\. \*\*", section, re.MULTILINE)
        self.assertEqual(len(questions), 6, section)
        for phrase in ("数学对象", "最接近的已有方法", "假设使其可能有效",
                       "最可能的失败机制", "区分该机制与竞争解释"):
            self.assertIn(phrase, section)
        self.assertIn("无法回答时明确标注未知", section)
        self.assertIn("不得生成空泛解释", section)

    def test_evidence_discipline_forbids_causality_and_smoke(self):
        self.assertIn("不得把相关性写成因果性", self.policy)
        self.assertIn("不得把 engineering smoke 当作科学有效性证据", self.policy)
        self.assertIn("不得编造数学目标、机制或统计结论", self.policy)
        self.assertIn("必须保留负证据", self.policy)
        self.assertIn("不得把 UNKNOWN / INVALID 读成支持或否证", self.policy)

    def test_default_hides_operational_details_and_expands_on_request(self):
        section = between(self.policy, "## 4. 默认隐藏的操作细节", "## 6. 与 R12 的边界")
        for token in ("PID", "GPU UUID", "state_version", "长绝对路径"):
            self.assertIn(token, section)
        self.assertIn("用户显式要求「详细审计」", section)
        self.assertIn("仍然不得编造", section)
        self.assertIn("不是另一套结论", section)

    def test_r12_is_not_the_daily_report(self):
        self.assertIn("R12 是论文叙事机制，不是日常科研汇报", self.policy)
        self.assertIn("不调用 R12 的六槽位", self.policy)


class TestOperationalPolicy(unittest.TestCase):

    def setUp(self):
        self.policy = read("references/operational-autonomy-policy.md")

    def test_three_classes_are_explicit(self):
        for phrase in ("A. Routine Maintenance", "B. Evidence-Gated Scientific Updates",
                       "C. Privileged Research Actions"):
            self.assertIn(phrase, self.policy)
        self.assertIn("自动执行，不询问用户", self.policy)
        self.assertIn("全部通过才可自动提交，否则 `HOLD`", self.policy)
        self.assertIn("本次改造不新增任何权限", self.policy)

    def test_routine_work_cannot_write_canonical_state(self):
        self.assertIn("A 类不得写 `research-state.json`", self.policy)
        self.assertIn("投影刷新不得改变 canonical state", self.policy)
        self.assertIn("同一动作重复执行必须安全", self.policy)
        self.assertIn("不得把「刷新版本号」当成同步", self.policy)

    def test_termination_and_stale_telemetry_are_not_science(self):
        self.assertIn("进程终止不是科学完成", self.policy)
        self.assertIn("过期 telemetry 不是当前事实", self.policy)
        self.assertIn("未验证日志不是 outcome", self.policy)
        self.assertIn("真实阻塞必须保留", self.policy)

    def test_conflicts_hold_and_recovery_is_bounded(self):
        self.assertIn("冲突时 HOLD", self.policy)
        self.assertIn("有限恢复，不无限循环", self.policy)
        self.assertIn("最多按既有冷却/上限重试", self.policy)

    def test_analysis_does_not_trigger_experiments(self):
        self.assertIn("用户只请求分析时，不得擅自执行研究实验", self.policy)
        self.assertIn("用户请求继续科研时，不得因例行维护反复请求批准", self.policy)


class TestRepresentativeReports(unittest.TestCase):

    def setUp(self):
        text = read("examples/scientific-reporting.md")
        self.before_x88 = between(text, "### 1.1 X88", "### 1.2 X87")
        self.before_x87 = between(text, "### 1.2 X87", "### 1.3 X90")
        self.before_x90 = between(text, "### 1.3 X90", "## 2. 修改后")
        self.after_x88 = between(text, "### 2.1 X88", "### 2.2 X87")
        self.after_x87 = between(text, "### 2.2 X87", "### 2.3 X90")
        self.after_x90 = between(text, "### 2.3 X90", "## 3. 用户要求详细审计时")
        self.audit = between(text, "## 3. 用户要求详细审计时", "## 4. 负结果示例")
        self.negative = text[text.index("## 4. 负结果示例"):]

    def assert_order(self, report: str):
        positions = [report.index(name) for name in
                     ("### Problem", "### Insight", "### Method", "### Evidence", "### Decision")]
        self.assertEqual(positions, sorted(positions))

    def test_before_reports_are_operations_first_and_ask_permission(self):
        for report in (self.before_x88, self.before_x90):
            self.assertIn("PID", report)
            self.assertIn("确认", report)
        self.assertIn("标记为 done", self.before_x87)
        self.assertNotIn("### Problem", self.before_x88)

    def test_x88_keeps_quantitative_evidence_and_scope(self):
        report = self.after_x88
        self.assert_order(report)
        for token in ("37.225", "35.988", "1.237", "1.200", "1.273"):
            self.assertIn(token, report)
        self.assertIn("不是 test", report)
        self.assertIn("不证明适配机制成立", report)
        self.assertIn("不在 val 上调参", report)
        self.assertIn("判别标准", report)

    def test_x87_is_not_completion_and_not_negative_evidence(self):
        report = self.after_x87
        self.assert_order(report)
        self.assertIn("SIGTERM", report)
        self.assertIn("不是负证据", report)
        self.assertIn("没有支持或否定", report)
        self.assertIn("不把 X87 标为 done", report)
        self.assertIn("不自动重启", report)
        self.assertNotIn("标记为 done，因为", report)

    def test_x90_explains_method_depth_not_run_details(self):
        report = self.after_x90
        self.assert_order(report)
        for phrase in ("改变的是先验对象", "关键假设", "最可能的失败机制",
                       "能区分这些机制的实验", "判别标准", "417/512"):
            self.assertIn(phrase, report)
        self.assertIn("GMRES", report)
        self.assertIn("不证明方法有效", report)
        for hidden in ("PID", "GPU UUID", "/home/", "state_version"):
            self.assertNotIn(hidden, report)

    def test_a_negative_result_is_not_hidden_for_brevity(self):
        report = self.negative
        self.assert_order(report)
        for token in ("ΔPSNR", "[-0.03, 0.06]", "scoped negative evidence",
                      "不是对方法的全局否证", "仍是", "功效"):
            self.assertIn(token, report)
        self.assertIn("不把结果写成“方法被证明无效”", report)
        self.assertIn("保留 negative knowledge", report)

    def test_audit_mode_expands_paths_without_changing_the_science(self):
        for token in ("PID 1713654", "GPU-c0599104", "/home/zhanglt/",
                      "state_version=160", "canonical=163"):
            self.assertIn(token, self.audit)
        self.assertIn("科学结论与默认模式一致", self.audit)


class TestPolicyWiring(unittest.TestCase):
    """The policies must be reachable from the runtime contract, not only from a new file."""

    def test_skill_and_runtime_documents_link_the_policies(self):
        skill = read("SKILL.md")
        self.assertIn("references/scientific-communication-policy.md", skill)
        self.assertIn("references/operational-autonomy-policy.md", skill)
        self.assertIn("scripts/operational_reconcile.py", skill)
        for path in ("shared-contract.md", "references/invocation-prompts.md",
                     "presets/research-loop.md"):
            text = read(path)
            self.assertIn("scientific-communication-policy.md", text, path)
            self.assertIn("operational-autonomy-policy.md", text, path)

    def test_the_loop_payload_declares_operations(self):
        text = read("scripts/preset_router.py")
        self.assertIn("ops.reconcile(", text)
        self.assertIn('"operations": operational', text)
        self.assertIn('"operational_holds"', text)
        preset = read("presets/research-loop.md")
        self.assertIn("`operations`", preset)
        self.assertIn("`operational_holds`", preset)

    def test_the_new_tests_are_part_of_the_release_gate(self):
        text = read("scripts/release_check.py")
        self.assertIn("test_operational_reconcile.py", text)
        self.assertIn("test_scientific_communication.py", text)


if __name__ == "__main__":
    unittest.main()
