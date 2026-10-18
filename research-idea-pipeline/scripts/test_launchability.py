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
        self.assertIn("未找到", probe["error"])
        self.assertIn("PATH", probe["error"])

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
             "hours": 2, "dry_run": False, "seal": "S1"},
            {"kind": "launch_failed", "family": "F", "permission": "PILOT_ONLY",
             "receipt_id": "R1", "hours": 2, "consume_seal": "S1"},
            {"kind": "consume", "family": "F", "permission": "PILOT_ONLY", "receipt_id": "R2",
             "hours": 1, "dry_run": False}])
        spent = ex.effective_spend(ledger, "F", "PILOT_ONLY")
        self.assertEqual([event["receipt_id"] for event in spent], ["R2"])
        self.assertEqual(sum(event["hours"] for event in spent), 1)

    def test_b1_a_refund_not_bound_to_the_consumption_is_ignored(self):
        """伪造/错绑的退款不得减少预算（防跨 family、重复退款、伪造归属）。"""
        ledger = self._Ledger([
            {"kind": "consume", "family": "F", "permission": "PILOT_ONLY", "receipt_id": "R1",
             "hours": 2, "dry_run": False, "seal": "S1"},
            {"kind": "launch_failed", "family": "F", "permission": "PILOT_ONLY",
             "receipt_id": "R1", "hours": 2},                       # 无 consume_seal
            {"kind": "launch_failed", "family": "F", "permission": "PILOT_ONLY",
             "receipt_id": "R1", "hours": 2, "consume_seal": "OTHER"},
            {"kind": "launch_failed", "family": "G", "permission": "PILOT_ONLY",
             "receipt_id": "R1", "hours": 2, "consume_seal": "S1"}])  # 跨 family
        self.assertEqual(len(ex.effective_spend(ledger, "F", "PILOT_ONLY")), 1)

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


class LaunchFailureFlow(unittest.TestCase):
    """P0 集成：issue → preview → run（exec 被拒）→ 退款 → 重新签发 → 成功执行。

    **真实程度声明**：整条 issue / preview / run / 锁 / consume / refund / 预算核算 /
    重新签发都走生产代码；唯一被替换的是外部进程边界——`subprocess.run` 被替换为抛
    `PermissionError`，用来确定性地模拟"内核拒绝 exec"（真实 exec 的系统调用行为无法在
    不同 CI 内核上稳定复现）。真实的 argv 解析与可执行位判定由本文件前两组用例覆盖。
    """

    def _prepare(self):
        import tempfile
        from pathlib import Path
        import test_execution_gate as teg
        case = teg.fixture()
        state = case["state"]
        experiment = state["experiments"][-1]
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        manifest = teg.resources(state, root)
        ledger = ex.Ledger(root / "ledger")
        return teg, state, experiment, manifest, ledger

    def test_the_full_refund_flow_through_the_real_run_path(self):
        from unittest.mock import patch
        teg, state, experiment, manifest, ledger = self._prepare()
        issued = teg.issue(state, experiment["id"], manifest, ledger, now=100)
        self.assertEqual(issued["status"], "PASS", issued)
        preview = teg.managed_run(state, experiment["id"], manifest, issued["receipt"],
                                 ledger, now=101)
        self.assertTrue(preview.get("preview"), preview)
        self.assertFalse(preview.get("consumed"))
        self.assertTrue(preview["launch_probe"]["ok"], preview["launch_probe"])
        with patch.object(ex.subprocess, "run", side_effect=PermissionError(13, "denied")):
            failed = teg.managed_run(state, experiment["id"], manifest, issued["receipt"],
                                     ledger, execute=True, now=102)
        self.assertEqual(failed["status"], "FAIL", failed)
        self.assertIn("LAUNCH_FAILED", " ".join(failed["errors"]), failed)
        self.assertTrue(failed["budget_refunded"], failed)
        # 退款后预算回到可用状态，可合法重新签发
        reissued = teg.issue(state, experiment["id"], manifest, ledger, now=103)
        self.assertEqual(reissued["status"], "PASS", reissued)
        with patch.object(ex.subprocess, "run",
                          return_value=__import__("subprocess").CompletedProcess([], 0)):
            ran = teg.managed_run(state, experiment["id"], manifest, reissued["receipt"],
                                  ledger, execute=True, now=104)
        self.assertEqual(ran["status"], "PASS", ran)

    def test_a_refund_cannot_be_claimed_twice(self):
        from unittest.mock import patch
        teg, state, experiment, manifest, ledger = self._prepare()
        receipt = teg.issue(state, experiment["id"], manifest, ledger, now=100)["receipt"]
        with patch.object(ex.subprocess, "run", side_effect=PermissionError(13, "denied")):
            first = teg.managed_run(state, experiment["id"], manifest, receipt, ledger,
                                    execute=True, now=102)
        self.assertTrue(first["budget_refunded"], first)
        again = teg.managed_run(state, experiment["id"], manifest, receipt, ledger,
                                execute=True, now=103)
        self.assertEqual(again["errors"], ["UNKNOWN_OR_USED_RECEIPT"])
        with ex.Ledger(ledger.directory).locked() as loaded:
            refunds = [event for event in loaded.events if event.get("kind") == "launch_failed"]
        self.assertEqual(len(refunds), 1)

    def test_a_started_command_failure_is_not_refunded(self):
        """已真正启动并失败的任务不得伪装成 LAUNCH_FAILED 自动退款。"""
        from unittest.mock import patch
        import subprocess as sp
        teg, state, experiment, manifest, ledger = self._prepare()
        receipt = teg.issue(state, experiment["id"], manifest, ledger, now=100)["receipt"]
        with patch.object(ex.subprocess, "run",
                          return_value=sp.CompletedProcess([], 1)):
            failed = teg.managed_run(state, experiment["id"], manifest, receipt, ledger,
                                     execute=True, now=102)
        self.assertEqual(failed["status"], "FAIL", failed)
        self.assertEqual(failed["errors"], ["EXECUTION_FAILED"])
        self.assertNotIn("LAUNCH_FAILED", " ".join(failed["errors"]))
        with ex.Ledger(ledger.directory).locked() as loaded:
            self.assertFalse([e for e in loaded.events if e.get("kind") == "launch_failed"])
