#!/usr/bin/env python3
"""test_report_lint.py — 报告结构 lint 的离线测试（stdlib unittest，不联网）

运行：
    python3 -m unittest discover -s scripts -p "test_*.py"
    python3 scripts/test_report_lint.py

为什么需要它
------------
`references/scientific-communication-policy.md` 的编号形态只写在散文里。实测后果是
「已同步 state，审计通过 12 条」当选结论，以及训练启动通知缺优化器而无人发现。
本测试钉住两侧：合规报告必须通过，每一类噪声必须有反例。

覆盖点
------
1. REP-01 编号与首节；2. REP-02 操作流水账与 gate 日志；3. REP-03 训练通知 11 项；
4. REP-04 数字可解释性与强断言只给 WARN；5. REP-05 阻塞不得静默；
6. REP-06 机器记录不得夹带；7. REP-07 未决事项与擅自选项；8. CLI 退出码与 --json。
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import report_lint as rl

GOOD = """# 结果报告

## 01. 本轮结论
X41 在 test 划分上 PSNR 31.60，基线 31.20，样本 1000 片。

## 02. 实验结果
| 方法 | test PSNR |
|---|---|
| base | 31.20 |
| ours | 31.60 |
"""

TRAINING = """# 训练启动报告

## 01. 本轮目的与方法
验证 A 臂在冻结采集协议下是否优于基线。

## 02. 数据和物理配置
| 数据划分 | 维度 | mask | CSM 模式与来源 | 样本配对键 |
|---|---|---|---|---|
| train/val/test | 320x320 | 列 mask | dataset_stored，数据集 csmslice | subject/volume/slice/acquisition |
输入 [B,C,H,W] k-space，输出 [B,H,W] complex image，FFT 轴向 norm=ortho，
归一化只用训练测量，learnable 参数为 0。

## 03. 训练与选模
| 优化器 | 学习率 | 预算 | 损失 | 选模 | checkpoint |
| AdamW | 3e-3 warmup 3000 | 18000 step | l1+ssim | full_val_gt PSNR | best_val |
代码 commit abc123，资源已授权。
"""


class LintCase(unittest.TestCase):
    def lint(self, text: str, report_type: str = "result"):
        return rl.lint(text, report_type)

    def rules(self, text: str, report_type: str = "result"):
        return {finding["rule"] for finding in self.lint(text, report_type)["findings"]}


class StructureTests(LintCase):
    def test_compliant_report_passes(self) -> None:
        result = self.lint(GOOD)
        self.assertEqual(result["blocks"], 0, result["findings"])

    def test_numbering_required(self) -> None:
        self.assertIn("REP-01", self.rules("## 本轮结论\n结果更好。\n"))

    def test_first_section_must_be_conclusion(self) -> None:
        self.assertIn("REP-01", self.rules("## 01. 操作记录\n跑了训练。\n"))

    def test_numbers_must_be_sequential(self) -> None:
        text = "## 01. 本轮结论\nok\n## 03. 结果\nok\n"
        self.assertIn("REP-01", self.rules(text))

    def test_progress_reports_need_no_numbering(self) -> None:
        self.assertEqual(self.lint("继续跑。", "progress")["blocks"], 0)


class OpenerTests(LintCase):
    def test_operation_opener_blocked(self) -> None:
        text = "## 01. 本轮结论\n已同步 state，审计通过 12 条。\n"
        self.assertIn("REP-02", self.rules(text))

    def test_gate_log_repetition_warned(self) -> None:
        text = "## 01. 结论\n正常。\n审计 12 条通过。\n检查 8 项通过。\n"
        self.assertIn("REP-02", self.rules(text))


class TrainingReportTests(LintCase):
    def test_complete_training_report_passes(self) -> None:
        result = self.lint(TRAINING, "training-report")
        self.assertEqual(result["blocks"], 0, result["findings"])

    def test_missing_fields_are_blocked(self) -> None:
        text = "## 01. 目的\n跑训练。\n## 02. 数据\n320x320。\n"
        result = self.lint(text, "training-report")
        self.assertIn("REP-03", {f["rule"] for f in result["findings"]})

    def test_na_is_warned_not_blocked(self) -> None:
        text = TRAINING + "\n缺项写 N/A。\n"
        result = self.lint(text, "training-report")
        self.assertIn("REP-03", {f["rule"] for f in result["findings"]})
        self.assertGreaterEqual(result["warns"], 1)


class EvidenceTests(LintCase):
    def test_numbers_without_metric_warned(self) -> None:
        text = "## 01. 结论\n提升 0.4，样本 1000 片，test 划分。\n"
        self.assertIn("REP-04", self.rules(text))

    def test_strong_claim_is_warn_only(self) -> None:
        text = "## 01. 结论\n该机制必然导致提升，PSNR 31.2，test 划分，1000 片。\n"
        result = self.lint(text)
        self.assertEqual(result["blocks"], 0)
        self.assertIn("REP-04", {f["rule"] for f in result["findings"]})


class SilenceTests(LintCase):
    def test_silent_block_is_blocked(self) -> None:
        self.assertIn("REP-05", self.rules("## 01. 结论\n训练失败。\n"))

    def test_block_with_disposition_passes(self) -> None:
        text = "## 01. 结论\n训练失败。\n## 02. 下一步\n影响 A 臂，待用户确认是否改预算。\n"
        self.assertNotIn("REP-05", self.rules(text))

    def test_machine_record_warned(self) -> None:
        text = '## 01. 结论\n正常。\n\n```json\n{"schema": "x"}\n```\n'
        self.assertIn("REP-06", self.rules(text))

    def test_self_chosen_default_blocked(self) -> None:
        self.assertIn("REP-07", self.rules("## 01. 结论\n有问题，我已自行选择方案继续。\n"))


class CliTests(LintCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = rl.main(list(argv))
        return code, out.getvalue()

    def test_exit_codes_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.md"
            good.write_text(GOOD, encoding="utf-8")
            code, text = self.run_cli(str(good))
            self.assertEqual(code, 0)
            code, text = self.run_cli(str(good), "--json")
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(text)["status"], "OK")

            bad = Path(tmp) / "bad.md"
            bad.write_text("## 01. 结论\n已同步 state，审计通过 12 条。\n", encoding="utf-8")
            self.assertEqual(self.run_cli(str(bad))[0], 3)

    def test_missing_file_is_environment_error(self) -> None:
        code, _ = self.run_cli("/nonexistent/report.md")
        self.assertEqual(code, 4)

    def test_selftest_and_list_rules(self) -> None:
        self.assertEqual(self.run_cli("--selftest")[0], 0)
        self.assertEqual(self.run_cli("--list-rules")[0], 0)


if __name__ == "__main__":
    unittest.main()
