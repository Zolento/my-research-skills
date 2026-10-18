#!/usr/bin/env python3
"""test_launchability.py — 启动期可执行性（BUG: launch-vs-budget 的 A 类回归）。

修复前失败的最小复现：`argv[0]` 是项目内 **0644** 脚本时，
`manifest_binding` 只做 `is_file()` + `read_bytes()`（两谓词对 0644 均为真），
于是"不可启动的命令"通过全部执行闸门，并在 `subprocess.run` 抛 PermissionError 前
就已原子消费 pilot 预算。本文件固定四项行为：
A1 `manifest_binding` 拒绝无 +x 的 argv[0]；A2 `launch_probe` 同样拒绝；
A4 启动期失败报 `LAUNCH_FAILED` 而非 `EXECUTION_FAILED`；
B1 该失败**退还**预算（收据仍为已消费，防双发）。
"""

from __future__ import annotations

import os
import pathlib
import unittest

import experiment_execute as ex


class LaunchabilityCase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.cwd = pathlib.Path(self.temp.name)
        self.script = self.cwd / "train.sh"
        self.script.write_text("#!/bin/sh\ntrue\n", encoding="utf-8")
        self.manifest = {"argv": [str(self.script)], "cwd": str(self.cwd), "files": [],
                         "gpu_devices": ["0"], "env": {}}

    def tearDown(self):
        self.temp.cleanup()

    def test_a2_probe_rejects_a_non_executable_argv0(self):
        os.chmod(self.script, 0o644)
        probe = ex.launch_probe(self.manifest)
        self.assertFalse(probe["ok"], probe)
        self.assertIn("UNLAUNCHABLE_ARGV", probe["error"])
        self.assertIn("可执行位", probe["error"])

    def test_a2_probe_accepts_an_executable_argv0(self):
        os.chmod(self.script, 0o755)
        probe = ex.launch_probe(self.manifest)
        self.assertTrue(probe["ok"], probe)
        self.assertEqual(probe["resolved"], str(self.script))

    def test_a2_probe_resolves_a_bare_interpreter_through_path(self):
        manifest = dict(self.manifest, argv=["sh"])
        probe = ex.launch_probe(manifest)
        self.assertTrue(probe["ok"], probe)
        self.assertTrue(probe["via_path"])

    def test_a2_probe_reports_an_unresolvable_argv0(self):
        manifest = dict(self.manifest, argv=["definitely-not-a-command-xyz"])
        probe = ex.launch_probe(manifest)
        self.assertFalse(probe["ok"])
        self.assertIn("无法解析", probe["error"])

    def test_a1_the_launch_predicate_refuses_a_non_executable_project_argv0(self):
        """修复前只有 is_file()/read_bytes()（对 0644 均为真）→ 闸门全通过。"""
        bound = {str(self.script.resolve())}
        os.chmod(self.script, 0o644)
        error = ex.argv_launch_error(self.cwd, [str(self.script)], bound, self.manifest)
        self.assertIsNotNone(error)
        self.assertIn("UNLAUNCHABLE_ARGV", error)
        os.chmod(self.script, 0o755)
        self.assertIsNone(ex.argv_launch_error(self.cwd, [str(self.script)], bound,
                                               self.manifest))

    def test_a1_an_unbound_executable_is_still_refused(self):
        os.chmod(self.script, 0o755)
        error = ex.argv_launch_error(self.cwd, [str(self.script)], set(), self.manifest)
        self.assertEqual(error, "UNBOUND_EXECUTABLE")

    def test_a1_the_gate_calls_the_launch_predicate(self):
        import inspect
        self.assertIn("argv_launch_error", inspect.getsource(ex.manifest_binding))

    def test_a5_ensure_executable_sets_the_bit(self):
        os.chmod(self.script, 0o644)
        self.assertTrue(ex.ensure_executable(self.script))
        self.assertTrue(os.access(str(self.script), os.X_OK))
        self.assertFalse(ex.ensure_executable(self.cwd / "missing.sh"))


class MalformedInputCase(unittest.TestCase):
    """畸形输入不得以未捕获异常终止（闸门应给出可诊断结论）。"""

    def test_an_empty_argv_is_reported_not_raised(self):
        probe = ex.launch_probe({"argv": [], "cwd": ".", "files": []})
        self.assertFalse(probe["ok"])
        self.assertIn("argv", probe["error"])

    def test_a_non_list_argv_is_reported_not_raised(self):
        self.assertFalse(ex.launch_probe({"argv": "sh", "cwd": ".", "files": []})["ok"])

    def test_a_corrupt_ledger_line_is_skipped(self):
        ledger = type("L", (), {"events": ["bad", None, {"kind": "consume",
                                                         "family": "F",
                                                         "permission": "PILOT_ONLY",
                                                         "receipt_id": "R1",
                                                         "hours": 1, "dry_run": False}]})()
        self.assertEqual(len(ex.effective_spend(ledger, "F", "PILOT_ONLY")), 1)

    def test_ensure_executable_tolerates_none(self):
        self.assertFalse(ex.ensure_executable(None))


class BudgetAccountingCase(unittest.TestCase):
    class _Ledger:
        def __init__(self, events):
            self.events = events

    def test_b1_a_refunded_launch_does_not_count_toward_the_budget(self):
        ledger = self._Ledger([
            {"kind": "consume", "family": "F", "permission": "PILOT_ONLY", "receipt_id": "R1",
             "hours": 2, "dry_run": False},
            {"kind": "launch_failed", "family": "F", "permission": "PILOT_ONLY",
             "receipt_id": "R1", "hours": 2},
            {"kind": "consume", "family": "F", "permission": "PILOT_ONLY", "receipt_id": "R2",
             "hours": 1, "dry_run": False}])
        spent = ex.effective_spend(ledger, "F", "PILOT_ONLY")
        self.assertEqual([event["receipt_id"] for event in spent], ["R2"])
        self.assertEqual(sum(event["hours"] for event in spent), 1)

    def test_b1_an_unrefunded_launch_still_counts(self):
        ledger = self._Ledger([
            {"kind": "consume", "family": "F", "permission": "PILOT_ONLY", "receipt_id": "R1",
             "hours": 2, "dry_run": False}])
        self.assertEqual(len(ex.effective_spend(ledger, "F", "PILOT_ONLY")), 1)

    def test_a4_the_run_path_classifies_launch_failure_separately(self):
        import inspect
        source = inspect.getsource(ex.run)
        self.assertIn("LAUNCH_FAILED", source)
        self.assertIn("PermissionError", source)
        self.assertIn("launch_failed", source)


if __name__ == "__main__":
    unittest.main()
