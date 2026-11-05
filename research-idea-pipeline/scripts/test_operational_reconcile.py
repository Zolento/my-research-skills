#!/usr/bin/env python3
"""test_operational_reconcile.py — A/B/C maintenance, outcome readiness and freshness.

The tests use the real `evidence_outcome.apply()` transaction and the real projection builders.
They lock down the behaviour the communication policy promises:

* routine projections refresh idempotently and never bump `state_version`;
* a complete, audited bundle for a running result can commit; a terminal result without
  one stays `HOLD`;
* a terminated process is never turned into scientific completion;
* stale scheduler telemetry cannot supply the next action;
* a maintenance failure is reported, not papered over.
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import cognition as cg
import operational_reconcile as ops
import preset_router as pr
import state_check as sc
import test_evidence_outcome as teo

TIMESTAMP = teo.TIMESTAMP


def project(temp: pathlib.Path, state=None):
    root = temp / "A"
    root.mkdir(parents=True, exist_ok=True)
    state = state if state is not None else teo.fixture("positive")[0]
    state_path = root / "research-state.json"
    state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return state_path, state


def write_bundle(state_path: pathlib.Path, packet, analysis, audit, xid: str = "X1") -> pathlib.Path:
    root = state_path.parent / "results" / "A" / xid / "outcome"
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{xid}-packet.json").write_text(json.dumps(packet, ensure_ascii=False), encoding="utf-8")
    (root / f"{xid}-analysis.json").write_text(json.dumps(analysis, ensure_ascii=False), encoding="utf-8")
    (root / f"{xid}-audit.json").write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")
    return root


class TestClassification(unittest.TestCase):

    def test_the_three_classes_are_frozen(self):
        self.assertEqual(ops.classify("refresh_status_projection"), ops.CLASS_ROUTINE)
        self.assertEqual(ops.classify("submit_outcome_transaction"), ops.CLASS_EVIDENCE)
        self.assertEqual(ops.classify("change_primary_anchor"), ops.CLASS_PRIVILEGED)
        self.assertEqual(ops.classify("exceed_budget"), ops.CLASS_PRIVILEGED)

    def test_unknown_operations_are_refused(self):
        with self.assertRaises(KeyError):
            ops.classify("make_it_faster")


class TestOutcomeReadiness(unittest.TestCase):

    def test_a_complete_audited_bundle_commits_and_refreshes_projections(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path, state = project(pathlib.Path(temp))
            state, packet, analysis, audit = teo.fixture("positive")
            state_path, _ = project(pathlib.Path(temp), state)
            write_bundle(state_path, packet, analysis, audit)
            report = ops.reconcile(state_path, apply=True, timestamp=TIMESTAMP)
            self.assertEqual(report["status"], "OK", report)
            self.assertTrue(report["state_changed"])
            self.assertIn("research-state.json", report["writes"])
            self.assertIn("STATUS.md", report["writes"])
            self.assertTrue((state_path.parent / "cognition" / "index.json").is_file())
            after = json.loads(state_path.read_text(encoding="utf-8"))
            experiment = after["experiments"][0]
            self.assertEqual(experiment["status"], "done")
            self.assertEqual(after["state_version"], state["state_version"] + 1)
            self.assertEqual(set(experiment["outcome_analysis"]),
                             {"packet", "analysis", "audit", "validation_context", "audit_trail"})
            self.assertEqual([row["status"] for row in report["outcomes"]["experiments"]],
                             ["COMMITTED"])
            self.assertEqual(sc.check_file(state_path).exit_code, 0)

    def test_a_read_only_call_detects_a_ready_bundle_but_never_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            state, packet, analysis, audit = teo.fixture("positive")
            state_path, _ = project(pathlib.Path(temp), state)
            write_bundle(state_path, packet, analysis, audit)
            before_state = state_path.read_bytes()
            report = ops.reconcile(state_path, apply=False, timestamp=TIMESTAMP)
            self.assertIn("outcome_transaction_ready",
                          {item["code"] for item in report["holds"]})
            self.assertFalse(report["state_changed"])
            self.assertEqual(report["writes"], [])
            self.assertEqual(state_path.read_bytes(), before_state)
            self.assertFalse((state_path.parent / "cognition" / "index.json").exists())
            self.assertEqual([row["status"] for row in report["outcomes"]["experiments"]],
                             ["READY"])

    def test_a_terminal_result_without_a_bundle_is_held_not_invented(self):
        with tempfile.TemporaryDirectory() as temp:
            state, _, _, _ = teo.fixture("positive")
            experiment = state["experiments"][0]
            experiment.update(status="done", result="PSNR +0.8",
                              result_at_state_version=state["state_version"])
            state_path, _ = project(pathlib.Path(temp), state)
            before = state_path.read_bytes()
            report = ops.reconcile(state_path, apply=True, timestamp=TIMESTAMP)
            self.assertEqual(report["status"], "BLOCKED")
            self.assertIn("outcome_transaction_missing",
                          {item["code"] for item in report["holds"]})
            self.assertEqual(state_path.read_bytes(), before)
            after = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertIsNone(after["experiments"][0].get("outcome_analysis"))

    def test_an_incomplete_bundle_is_held_with_a_structured_reason(self):
        with tempfile.TemporaryDirectory() as temp:
            state, packet, analysis, audit = teo.fixture("positive")
            state["experiments"][0].update(status="done", result="PSNR +0.8",
                                           result_at_state_version=state["state_version"])
            state_path, _ = project(pathlib.Path(temp), state)
            root = state_path.parent / "results" / "A" / "X1" / "outcome"
            root.mkdir(parents=True, exist_ok=True)
            (root / "X1-packet.json").write_text(json.dumps(packet, ensure_ascii=False),
                                                 encoding="utf-8")
            report = ops.reconcile(state_path, apply=True, timestamp=TIMESTAMP)
            self.assertIn("outcome_transaction_invalid",
                          {item["code"] for item in report["holds"]})
            self.assertEqual(json.loads(state_path.read_text())["experiments"][0]["status"],
                             "done")

    def test_a_partial_commit_is_refused_while_the_backlog_remains(self):
        with tempfile.TemporaryDirectory() as temp:
            state, packet, analysis, audit = teo.fixture("positive")
            second = json.loads(json.dumps(state["experiments"][0]))
            second.update(id="X2", status="done", result="PSNR +0.1",
                          result_at_state_version=state["state_version"])
            state["experiments"].append(second)
            refreshed = [state, packet, analysis, audit]
            teo.refresh(refreshed)
            _, packet, analysis, audit = refreshed
            state_path, _ = project(pathlib.Path(temp), state)
            write_bundle(state_path, packet, analysis, audit)
            before = state_path.read_bytes()
            report = ops.reconcile(state_path, apply=True, timestamp=TIMESTAMP)
            self.assertIn("outcome_backlog_unresolved",
                          {item["code"] for item in report["holds"]})
            self.assertFalse(report["state_changed"])
            self.assertEqual(state_path.read_bytes(), before)


    def test_two_passes_are_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            state, packet, analysis, audit = teo.fixture("positive")
            state_path, _ = project(pathlib.Path(temp), state)
            write_bundle(state_path, packet, analysis, audit)
            first = ops.reconcile(state_path, apply=True, timestamp=TIMESTAMP)
            second = ops.reconcile(state_path, apply=True, timestamp=TIMESTAMP)
            self.assertTrue(first["state_changed"])
            self.assertFalse(second["state_changed"])
            self.assertEqual(second["writes"], [])
            self.assertEqual(json.loads(state_path.read_text())["state_version"],
                             first["state_version"])


class TestProjectLayoutProjections(unittest.TestCase):

    def test_status_is_written_to_the_human_route_not_the_canonical_one(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            route = project / ".research-idea-pipeline" / "routes" / "A"
            route.mkdir(parents=True)
            state = teo.fixture("positive")[0]
            state_path = route / "research-state.json"
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            report = ops.reconcile(state_path, apply=True, timestamp=TIMESTAMP)
            human = project / "routes" / "A" / "STATUS.md"
            self.assertTrue(human.is_file(), report)
            self.assertFalse((route / "STATUS.md").exists())
            self.assertIn("routes/A/STATUS.md", report["writes"])
            self.assertTrue((route / "cognition" / "index.json").is_file())

    def test_a_prepared_bundle_is_found_under_the_project_results_dir(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            route = project / ".research-idea-pipeline" / "routes" / "A"
            route.mkdir(parents=True)
            state, packet, analysis, audit = teo.fixture("positive")
            state_path = route / "research-state.json"
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            bundle = project / "results" / "A" / "X1" / "outcome"
            bundle.mkdir(parents=True)
            for name, payload in (("X1-packet.json", packet),
                                  ("X1-analysis.json", analysis),
                                  ("X1-audit.json", audit)):
                (bundle / name).write_text(json.dumps(payload, ensure_ascii=False),
                                           encoding="utf-8")
            report = ops.reconcile(state_path, apply=True, timestamp=TIMESTAMP)
            self.assertTrue(report["state_changed"], report)
            self.assertEqual(json.loads(state_path.read_text())["experiments"][0]["status"],
                             "done")


class TestTerminationAndTelemetry(unittest.TestCase):

    def test_sigterm_is_not_scientific_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            state, _, _, _ = teo.fixture("positive")
            state["experiments"][0]["execution_boundary"] = (
                "User stopped execution; SIGTERM; not scientifically complete")
            state_path, _ = project(pathlib.Path(temp), state)
            before = state_path.read_bytes()
            report = ops.reconcile(state_path, apply=True, timestamp=TIMESTAMP)
            self.assertEqual(report["status"], "HOLD")
            self.assertIn("execution_stopped_not_completion",
                          {item["code"] for item in report["holds"]})
            self.assertEqual(state_path.read_bytes(), before)
            self.assertEqual(json.loads(state_path.read_text())["experiments"][0]["status"],
                             "running")
            payload, _, code = pr.run_preset("research-loop", state_path)
            self.assertEqual(code, pr.EXIT_ENV)
            self.assertEqual(payload["hold_reason"], "execution_stopped_not_completion")
            self.assertNotIn("走 PEIG/AALG", payload["next_action"])

    def test_stale_scheduler_cannot_supply_the_next_action(self):
        with tempfile.TemporaryDirectory() as temp:
            state, _, _, _ = teo.fixture("positive")
            state["experiments"] = []
            state_path, _ = project(pathlib.Path(temp), state)
            cg.op_build(state_path, state_path.parent / cg.COGNITION_DIRNAME)
            scheduler = {
                "state_version": state["state_version"] - 1,
                "next_actions": [{"action": "X1", "type": "experiment", "target": "C1",
                                  "eig": "high", "cost": "low"}],
                "eig_calibration": {"records": []},
                "operator_stats": {"by_operator": {}, "recurring_failure_patterns": []},
            }
            (state_path.parent / cg.SCHEDULER_NAME).write_text(
                json.dumps(scheduler, ensure_ascii=False), encoding="utf-8")
            report = ops.reconcile(state_path, apply=False, timestamp=TIMESTAMP)
            self.assertIn("stale_scheduler", {item["code"] for item in report["holds"]})
            self.assertEqual(report["scheduler"]["status"], "STALE")
            payload, _, code = pr.run_preset("research-loop", state_path)
            self.assertEqual(code, pr.EXIT_ENV)
            self.assertEqual(payload["hold_reason"], "stale_scheduler")
            self.assertIsNone(payload["decision"]["dispatched_action"])

    def test_a_current_scheduler_with_a_conflicting_monitor_record_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as temp:
            state, _, _, _ = teo.fixture("positive")
            state["experiments"][0]["execution_boundary"] = (
                "User stopped execution; not scientifically complete")
            state_path, _ = project(pathlib.Path(temp), state)
            scheduler = {
                "state_version": state["state_version"],
                "next_actions": [],
                "eig_calibration": {"records": []},
                "operator_stats": {"by_operator": {}, "recurring_failure_patterns": []},
                "monitor": {"experiment": "X1", "status": "running", "pid": 4242},
            }
            (state_path.parent / cg.SCHEDULER_NAME).write_text(
                json.dumps(scheduler, ensure_ascii=False), encoding="utf-8")
            with patch("execution_gate.scheduler_check",
                       return_value={"status": "PASS", "errors": []}):
                view = ops._scheduler_view(state, state_path.parent, True)
            self.assertEqual(view["status"], "CONFLICT")
            self.assertEqual(view["monitor_conflicts"][0]["experiment"], "X1")

    def test_a_projection_failure_is_reported_not_claimed_as_synced(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path, _ = project(pathlib.Path(temp))
            # Remove the projection so the refresh path runs, then make the rebuild fail.
            with patch.object(cg, "op_build", return_value=3) as build:
                report = ops.reconcile(state_path, apply=True, timestamp=TIMESTAMP)
            build.assert_called_once()
            self.assertIn("projection_refresh_failed",
                          {item["code"] for item in report["holds"]})
            self.assertEqual(report["maintenance"][0]["status"], "FAILED")
            self.assertFalse((state_path.parent / "cognition" / "index.json").exists())


class TestLoopIntegration(unittest.TestCase):

    def test_the_loop_declares_reconciliation_before_recall(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path, _ = project(pathlib.Path(temp))
            payload, _, _ = pr.run_preset("research-loop", state_path)
            self.assertEqual(payload["steps"][0]["step"], "Reconcile")
            self.assertEqual(payload["observed"]["loop"][0], "Reconcile")
            self.assertIn("operations", payload["observed"])
            self.assertIn("operational_holds", payload["decision"])
            self.assertIn("hold_counts", payload["decision"]["operations"])
            self.assertIn("outcome_counts", payload["decision"]["operations"])

    def test_an_applying_loop_really_refreshes_the_projection(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path, _ = project(pathlib.Path(temp))
            payload, _, code = pr.run_preset("research-loop", state_path, apply=True)
            self.assertEqual(code, pr.EXIT_OK, payload.get("hold_reason"))
            self.assertTrue((state_path.parent / "cognition" / "index.json").is_file())
            self.assertTrue((state_path.parent / "STATUS.md").is_file())
            self.assertIn("cognition/index.json", payload["writes"])
            self.assertIn("STATUS.md", payload["writes"])


if __name__ == "__main__":
    unittest.main()
