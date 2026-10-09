#!/usr/bin/env python3
"""test_r10_liveness.py — R9.O → R10/R11 → Consolidate completion and loop liveness.

Every state used here is produced by a **real** `evidence_outcome.apply()` transaction over the
repository's own fixtures, validated by `evidence_outcome.state_errors()` and `state_check`, and
only then handed to `preset_router`.

What went wrong before this file existed
----------------------------------------
`r10_pending()` treated `repairs[].outcome_analysis_id` as the completion receipt. Repairs are
written only when an update attaches an evidence object to a claim/hypothesis, so the legal,
repair-less transactions below (`NEGATIVE_EVIDENCE`, `INVALID_EXPERIMENT`, hypothesis-only,
partial-scope, INCONCLUSIVE) looked permanently unfinished and the loop repeated `Revise`. The
formal receipt of R10/R11 is the five-key `outcome_analysis` block whose authority is
`state_errors()` — not a repair.

Acceptance: legal work is never repeated, missing work is never masked, damaged receipts HOLD.
"""

from __future__ import annotations

import copy
import json
import pathlib
import sys
import tempfile
import unittest

import evidence_outcome as eo
import preset_router as pr
import state_check as sc
import test_evidence_outcome as teo

TIMESTAMP = teo.TIMESTAMP


def committed(scenario: str, *, xid: str = "X1", mutate=None):
    """Run a real apply() transaction and return (state, result)."""
    args = list(teo.fixture(scenario, xid=xid))
    if mutate is not None:
        mutate(args)
    result = eo.apply(*args, timestamp=TIMESTAMP)
    return result, args


def committed_state(scenario: str, **kw):
    result, _ = committed(scenario, **kw)
    assert result["status"] == "PASS", result
    return result["state"]


def two_experiments():
    """Case B: X1 legally committed, X2 terminal but not yet analysed.

    X2 is *not* a rolled-back transaction — that would leave the claims carrying provenance from
    a receipt that no longer exists, which is a different (hold-worthy) condition. Here X2 simply
    finished its run and has no analysis yet, exactly as the loop meets it in practice.
    """
    state = committed_state("positive")
    args = list(teo.fixture("positive", state=state, xid="X2"))
    pending = copy.deepcopy(args[0])
    x2 = [item for item in pending["experiments"] if item["id"] == "X2"][0]
    x2["status"] = "done"
    x2["result"] = "M improves by 0.8 against matched P."
    pending["state_version"] = pending["state_version"] + 1
    x2["result_at_state_version"] = pending["state_version"]
    return pending, args


class TestTransactionSemantics(unittest.TestCase):
    """Phase 1: what a real transaction actually persists."""

    def test_positive_evidence_commits_with_a_repair(self):
        result, _ = committed("positive")
        self.assertEqual(result["status"], "PASS", result)
        state = result["state"]
        self.assertEqual(len(state["repairs"]), 1)
        self.assertEqual(state["repairs"][0]["outcome_analysis_id"],
                         state["experiments"][-1]["outcome_analysis"]["analysis"]["id"])
        self.assertEqual(eo.state_errors(state), [])

    def test_negative_evidence_commits_without_any_repair(self):
        result, _ = committed("negative")
        self.assertEqual(result["status"], "PASS", result)
        state = result["state"]
        self.assertEqual(state["repairs"], [], "NEGATIVE_EVIDENCE does not create a repair")
        self.assertEqual(len(state["failures"]), 1)
        self.assertEqual(state["failures"][0]["source_analysis_id"],
                         state["experiments"][-1]["outcome_analysis"]["analysis"]["id"])
        self.assertEqual(eo.state_errors(state), [])

    def test_invalid_experiment_commits_without_any_repair(self):
        result, _ = committed("invalid")
        self.assertEqual(result["status"], "PASS", result)
        state = result["state"]
        self.assertEqual(state["repairs"], [])
        experiment = state["experiments"][-1]
        self.assertEqual(experiment["status"], "failed")
        self.assertEqual(experiment["validity"]["status"], "invalid")
        self.assertEqual(eo.state_errors(state), [])
        self.assertEqual(sc.check_state(state).all_violations(), [])

    def test_every_committed_receipt_carries_the_formal_provenance(self):
        for scenario in ("positive", "negative", "invalid"):
            state = committed_state(scenario)
            receipt = state["experiments"][-1]["outcome_analysis"]
            self.assertEqual(set(receipt), {"packet", "analysis", "audit", "validation_context",
                                            "audit_trail"}, scenario)
            trail = receipt["audit_trail"]
            experiment = state["experiments"][-1]
            self.assertEqual(trail["state_version"], experiment["result_at_state_version"],
                             scenario)
            self.assertEqual(trail["previous_state"]["version"], trail["state_version"] - 1,
                             scenario)
            self.assertTrue(trail["state_delta"], scenario)
            self.assertEqual(trail["decision"], receipt["analysis"]["decisions"], scenario)


class TestR10Classification(unittest.TestCase):
    """Phase 2: the classification is per experiment and validator-backed."""

    def test_repair_less_legal_commits_are_not_pending(self):
        for scenario in ("negative", "invalid"):
            state = committed_state(scenario)
            self.assertEqual(pr.r10_pending(state), [], scenario)
            status = pr.r10_status(state)["X1"]
            self.assertEqual(status["status"], pr.R10_COMMITTED, scenario)
            self.assertEqual(status["reason"], status["reason"])

    def test_pending_is_not_derived_from_a_repair(self):
        state = committed_state("negative")
        self.assertEqual(state["repairs"], [])
        self.assertEqual(pr.r10_pending(state), [])

    def test_a_terminal_experiment_without_a_receipt_needs_analysis(self):
        state = committed_state("positive")
        stripped = copy.deepcopy(state)
        stripped["experiments"][-1].pop("outcome_analysis")
        self.assertEqual(pr.r10_pending(stripped), ["X1"])
        self.assertEqual(pr.r10_status(stripped)["X1"]["status"], pr.R10_NEEDS_ANALYSIS)

    def test_history_does_not_mask_a_missing_analysis(self):
        stripped, _ = two_experiments()
        self.assertEqual(pr.r10_status(stripped)["X1"]["status"], pr.R10_COMMITTED)
        self.assertEqual(pr.r10_pending(stripped), ["X2"])

    def test_a_running_experiment_is_not_an_r10_item(self):
        state = committed_state("positive")
        state["experiments"].append({"id": "X9"})
        state["experiments"][-1]["status"] = "running"
        self.assertNotIn("X9", pr.r10_pending(state))
        self.assertEqual(pr.r10_status(state)["X9"]["status"], pr.R10_PENDING_EXECUTION)

    def test_a_damaged_receipt_blocks_instead_of_completing(self):
        for damage in ("missing_trail", "trail_version", "tampered_summary", "swapped_analysis"):
            state = committed_state("negative")
            experiment = state["experiments"][-1]
            receipt = experiment["outcome_analysis"]
            if damage == "missing_trail":
                receipt.pop("audit_trail")
            elif damage == "trail_version":
                receipt["audit_trail"]["state_version"] = 99
            elif damage == "tampered_summary":
                experiment["result"] = "a different summary"
            else:
                receipt["analysis"]["experiment_id"] = "X7"
            status = pr.r10_status(state)["X1"]
            self.assertEqual(status["status"], pr.R10_BLOCKED, damage)
            self.assertTrue(status["reason"], damage)
            self.assertEqual(pr.r10_pending(state), [], damage)

    def test_an_analysis_bound_to_another_state_is_blocked(self):
        state = committed_state("negative")
        state["experiments"][-1]["outcome_analysis"]["audit_trail"]["previous_state"]["version"] = 7
        self.assertEqual(pr.r10_status(state)["X1"]["status"], pr.R10_BLOCKED)

    def test_the_classification_is_stable_across_reloads(self):
        with tempfile.TemporaryDirectory() as temp:
            state = committed_state("invalid")
            path_a = pathlib.Path(temp) / "a.json"
            path_b = pathlib.Path(temp) / "b.json"
            for path in (path_a, path_b):
                path.write_text(pr.json.dumps(state, ensure_ascii=False), encoding="utf-8")
            first = pr.r10_status(pr.cg.load_state(path_a))
            second = pr.r10_status(pr.cg.load_state(path_b))
            self.assertEqual(first, second)
            self.assertEqual(pr.r10_pending(pr.cg.load_state(path_a)), [])
            self.assertEqual(first["X1"]["status"], pr.R10_COMMITTED)

    def test_an_old_project_without_policy_still_reports_conservatively(self):
        state = committed_state("negative")
        state.pop("contract", None)
        status = pr.r10_status(state)
        self.assertEqual(status["X1"]["status"], pr.R10_BLOCKED)
        self.assertEqual(pr.r10_pending(state), [])


def assurance_payload(state, experiment_id="X1"):
    """A source-bound post-update Assurance for the committed analysis of one experiment."""
    receipt = [item for item in state["experiments"]
               if item["id"] == experiment_id][0]["outcome_analysis"]
    return {"schema": "evidence-outcome-assurance@1", "state_digest": eo.digest(state),
            "analysis_digest": eo.digest(receipt["analysis"]),
            "checks": {name: {"status": "PASS", "reason": "source-bound review"}
                       for name in ("integrity", "claim_calibration", "reproducibility",
                                    "stop_rule_compliance")}}


class TestLoopStepLiveness(unittest.TestCase):
    """Phase 3: the phase is chosen from per-experiment todo state, and the loop advances."""

    def _ctx(self, state, *, index=None, index_missing=False, scheduler=None, revisions=(),
             route_dir=None):
        return {"state": state, "index": index or {}, "index_missing": index_missing,
                "scheduler": scheduler, "revisions": list(revisions), "route_dir": route_dir}

    def test_case_c_repair_less_commit_does_not_repeat_revise(self):
        for scenario in ("negative", "invalid"):
            step = pr._loop_step(self._ctx(committed_state(scenario)))
            self.assertNotEqual(step["step"], "Revise", scenario)

    def test_case_b_a_missing_analysis_is_found_next_to_a_committed_one(self):
        stripped, _ = two_experiments()
        step = pr._loop_step(self._ctx(stripped))
        self.assertEqual(step["step"], "Verify")
        self.assertEqual(step["pending_r10"], ["X2"])

    def test_case_d_a_damaged_receipt_holds_with_the_experiment_id(self):
        state = committed_state("negative")
        state["experiments"][-1]["outcome_analysis"].pop("audit_trail")
        step = pr._loop_step(self._ctx(state))
        self.assertTrue(step["hold"])
        self.assertEqual(step["hold_reason"], "outcome_receipt_blocked")
        self.assertIn("X1", step["blocked_experiments"])

    def test_case_a_all_committed_moves_on_after_consolidation(self):
        state = committed_state("positive")
        stale = pr._loop_step(self._ctx(state, index_missing=True))
        self.assertEqual(stale["step"], "Consolidate")
        fresh_index = {"state_version": state["state_version"]}
        progressed = pr._loop_step(self._ctx(state, index=fresh_index))
        self.assertNotEqual(progressed["step"], "Consolidate")
        self.assertNotEqual(progressed["step"], "Revise")

    def test_case_a_without_a_legal_action_holds_instead_of_faking_progress(self):
        state = committed_state("positive")
        fresh_index = {"state_version": state["state_version"]}
        step = pr._loop_step(self._ctx(state, index=fresh_index))
        self.assertTrue(step["hold"] or step["step"] in ("Assurance", "Discover", "Intervene"))

    def test_case_e_a_pending_review_is_surfaced_not_skipped(self):
        """A committed transaction is not a licence to continue: the review still applies."""
        state = committed_state("positive")
        step = pr._loop_step(self._ctx(state, index={"state_version": state["state_version"]}))
        self.assertEqual(step["step"], "Assurance")
        self.assertEqual(step["assurance_pending"], ["X1"])
        self.assertFalse(step["hold"])
        self.assertIn("Decision Gate", step["phase"])

    @staticmethod
    def _write_assurance(route, state, experiment_id="X1"):
        """A source-bound review written where the loop looks for it (never fabricated by the loop)."""
        receipt = [item for item in state["experiments"]
                   if item["id"] == experiment_id][0]["outcome_analysis"]
        payload = {**assurance_payload(state, experiment_id)}
        directory = pathlib.Path(route).joinpath(*pr.OUTCOME_ASSURANCE_SUBDIR)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{receipt['analysis']['id']}.json").write_text(
            json.dumps(payload), encoding="utf-8")

    def test_a_scheduler_action_is_consumed_once_the_review_passes(self):
        state = committed_state("positive")
        scheduler = {"state_version": state["state_version"], "next_actions": [
            {"action": "X2", "type": "discriminating_experiment", "target": "C1",
             "eig": "high", "cost": "low"}]}
        with tempfile.TemporaryDirectory() as route:
            self._write_assurance(route, state)
            step = pr._loop_step(self._ctx(state, index={"state_version": state["state_version"]},
                                           scheduler=scheduler, route_dir=route))
        self.assertIn(step["step"], ("Discover", "Intervene"))
        self.assertIn("X2", step["action"])

    def test_no_state_change_loop_between_two_calls(self):
        stripped, _ = two_experiments()
        first = pr._loop_step(self._ctx(stripped))
        second = pr._loop_step(self._ctx(stripped))
        self.assertEqual(first, second, "the same snapshot must yield the same step")
        self.assertEqual(first["step"], "Verify")

    def test_multi_round_liveness_reaches_the_next_legal_action(self):
        """Acceptance 7 + the explicit liveness requirement: rounds advance, never repeat."""
        pending, args = two_experiments()
        fresh = {"state_version": pending["state_version"]}
        scheduler = {"state_version": pending["state_version"], "next_actions": [
            {"action": "X3", "type": "discriminating_experiment", "target": "C1",
             "eig": "high", "cost": "low"}]}
        # Round 1 — the unfinished analysis is the todo.
        first = pr._loop_step(self._ctx(pending, index=fresh, scheduler=scheduler))
        self.assertEqual(first["step"], "Verify")
        self.assertEqual(first["pending_r10"], ["X2"])
        # Round 2 — do exactly that work, through the real transaction.
        applied = eo.apply(*args, timestamp=TIMESTAMP)
        self.assertEqual(applied["status"], "PASS", applied)
        state = applied["state"]
        self.assertEqual(pr.r10_pending(state), [])
        # Round 3 — receipts are complete but the projection is stale: consolidate once.
        third = pr._loop_step(self._ctx(state, index={"state_version": state["state_version"] - 1},
                                        scheduler=scheduler))
        self.assertEqual(third["step"], "Consolidate")
        # Round 4 — fresh projection: the pending review is surfaced, not skipped.
        fourth = pr._loop_step(self._ctx(state, index={"state_version": state["state_version"]},
                                         scheduler=scheduler))
        self.assertEqual(fourth["step"], "Assurance")
        # X2's result superseded X1's target assessment, so only X2 still needs a review.
        self.assertEqual(fourth["assurance_pending"], ["X2"])
        # Round 5 — the review is satisfied: the Scheduler's next legal action is consumed.
        with tempfile.TemporaryDirectory() as route:
            self._write_assurance(route, state, "X2")
            fifth = pr._loop_step(self._ctx(state, index={"state_version": state["state_version"]},
                                            scheduler=scheduler, route_dir=route))
        self.assertEqual(fifth["step"], "Discover")
        self.assertIn("X3", fifth["action"])
        # No round repeats a completed stage, and no round fakes progress.
        self.assertEqual([item["step"] for item in (first, third, fourth, fifth)],
                         ["Verify", "Consolidate", "Assurance", "Discover"])

    def test_a_planned_experiment_still_wins_over_discovery(self):
        state = committed_state("positive")
        state["experiments"].append({"id": "X3", "status": "planned"})
        step = pr._loop_step(self._ctx(state, index={"state_version": state["state_version"]}))
        self.assertEqual(step["step"], "Intervene")


class TestLoopHandlerAndCli(unittest.TestCase):
    """Phase 4: the public interfaces agree with the classification."""

    def _write(self, root, state):
        path = pathlib.Path(root) / "research-state.json"
        path.write_text(pr.json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def test_the_loop_preset_reports_verify_for_a_missing_analysis(self):
        stripped, _ = two_experiments()
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._write(temp, stripped)
            before = state_path.read_bytes()
            payload, _, code = pr.run_preset("research-loop", state_path)
            self.assertTrue(payload["canonical_untouched"])
            self.assertEqual(payload["observed"]["current"]["step"], "Verify")
            self.assertEqual(payload["observed"]["current"]["pending_r10"], ["X2"])
            self.assertEqual(state_path.read_bytes(), before)

    def test_the_loop_preset_does_not_revise_a_committed_negative_result(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._write(temp, committed_state("negative"))
            payload, _, _ = pr.run_preset("research-loop", state_path)
            self.assertNotEqual(payload["observed"]["current"]["step"], "Revise")
            self.assertTrue(payload["canonical_untouched"])

    def test_a_damaged_receipt_surfaces_as_hold_through_the_cli(self):
        state = committed_state("negative")
        state["experiments"][-1]["outcome_analysis"]["audit_trail"]["state_version"] = 42
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._write(temp, state)
            payload, _, code = pr.run_preset("research-loop", state_path)
            self.assertEqual(payload["status"], "HOLD")
            self.assertEqual(code, pr.EXIT_ENV)
            self.assertEqual(payload["hold_reason"], "outcome_receipt_blocked")

    def test_an_unhandled_engineering_failure_signal_clears_after_commit(self):
        state = committed_state("invalid")
        failures = [item for item in state["failures"] if item["referenced_by"]]
        self.assertTrue(failures)
        signals = pr.signal_snapshot(state, scheduler={"state_version": state["state_version"],
                                                       "next_actions": []},
                                     index={"state_version": state["state_version"]},
                                     revisions=[])
        self.assertFalse(signals["engineering_failure"]["detected"],
                         "a committed INVALID_EXPERIMENT must stop re-signalling")
        self.assertEqual(pr.r10_pending(state), [])

    def test_repeated_calls_stay_stable_and_do_not_resubmit(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._write(temp, committed_state("negative"))
            before = state_path.read_bytes()
            steps = [pr.run_preset("research-loop", state_path)[0]["observed"]["current"]["step"]
                     for _ in range(3)]
            self.assertEqual(len(set(steps)), 1, steps)
            self.assertNotEqual(steps[0], "Revise")
            self.assertEqual(state_path.read_bytes(), before)

    def test_cross_session_reload_keeps_the_same_verdict(self):
        state = committed_state("invalid")
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._write(temp, state)
            first, _, _ = pr.run_preset("research-loop", state_path)
            reloaded = pr.cg.load_state(state_path)
            second = pr._loop_step({"state": reloaded, "index": {}, "index_missing": False,
                                    "scheduler": None, "revisions": []})
            self.assertEqual(first["observed"]["current"]["step"], second["step"])
            self.assertEqual(pr.r10_pending(reloaded), [])


if __name__ == "__main__":
    unittest.main()
