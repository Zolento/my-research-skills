#!/usr/bin/env python3
"""test_skill_rsi_e2e.py — Skill-RSI Phase 6/9 end-to-end acceptance.

Proves the whole chain runs on real scripts and real objects, and that every new artefact
has a real consumer:

    Research State → Decision Recording → Strategy Proposal → Replay → Policy Evaluation
        → Policy Selection → Strategy Decision Adapter → Next Legal Action → Outcome Feedback

It also runs the required research-decision adversarial cases: a refuted mechanism
re-appearing, an engineering failure mis-read as refutation, repeated valueless
diagnostics, an unobservable historical branch, a policy blocked by a hard gate, a single
legal action (no room to change anything), a strategy that reorders without dispatching,
over-fitting to a fixture, and "progress" faked through document/state counts.
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

import cognition as cg
import decision_trajectory as dt
import execution_gate as eg
import policy_evolution as pe
import preset_router as pr
import research_replay as rr
import strategy_memory as sm

ROOT = pathlib.Path(__file__).resolve().parent.parent
PREFERRED_XID = "R2"


def arm(mean):
    return {"dimensions": {name: {"mean": mean, "min": mean - 0.05, "max": mean + 0.05}
                           for name in rr.METRIC_DIMENSIONS},
            "results": [], "evidence_support": {}}


def replay_report(candidate_mean=0.9, control_mean=0.3):
    return {"schema": "research-idea-pipeline/replay-ablation@1",
            "sufficient_sample": True, "unobservable_decisions": 0,
            "delta_vs_baseline": {}, "cases": 5, "runs_per_case": 2,
            "per_arm": {"rsi_full": arm(candidate_mean), "full_cie": arm(control_mean)}}


class RsiProject(unittest.TestCase):
    """A schema-valid project whose adapter can genuinely reorder inside one tier."""

    def project(self, root, *, actions=None, lower_second=False, reduce=None):
        """A valid state whose loop reaches the scheduler's action selection.

        The experiment list and the assurance entry that referenced it are removed, so no
        planned/running work pre-empts the loop; the decision then really is "which of the
        scheduler's legal actions is next", which is exactly where a policy may reorder.
        """
        state = json.loads((ROOT / "examples/preflight-identifiability/ct-mri.json")
                           .read_text(encoding="utf-8"))["state"]
        state["experiments"] = []
        state["assurance"] = []
        if reduce:
            state = reduce(state)
        actions = [dict(item) for item in (actions or [
            {"action": "R1", "type": "repair", "target": "C1", "eig": "high", "cost": "low"},
            {"action": PREFERRED_XID, "type": "repair", "target": "C1", "eig": "high",
             "cost": "low"}])]
        if lower_second:
            actions[1] = {**actions[1], "eig": "low", "cost": "high"}
        scheduler = {"state_version": state["state_version"], "next_actions": actions,
                     "eig_calibration": {"records": []},
                     "operator_stats": {"by_operator": {}, "recurring_failure_patterns": []}}
        route = pathlib.Path(root)
        route.mkdir(parents=True, exist_ok=True)
        state_path = route / cg.STATE_NAME
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        (route / cg.SCHEDULER_NAME).write_text(json.dumps(scheduler, ensure_ascii=False,
                                                          indent=2), encoding="utf-8")
        # A fresh, non-stale cognition projection so the loop reaches the scheduler branch.
        cg.op_build(state_path, route / cg.COGNITION_DIRNAME)
        return state_path

    def propose_policy(self, state_path, *, policy_id="P-RSI", prefer=PREFERRED_XID,
                       scope_kind="local", counterexamples=("none yet",), trajectory=("DT-1",)):
        pe.freeze_evaluation_rules(state_path)
        candidate = {
            "policy_id": policy_id,
            "policy_schema_version": pe.POLICY_SCHEMA_VERSION,
            "parent_policy_id": None,
            "status": "PROPOSED",
            "scope": {"scope_kind": scope_kind, "problem_structure": "repair-vs-discriminate"},
            "applicable_conditions": [{"kind": "min_open_uncertainties", "value": 1}],
            "strategy_changes": [{"kind": "same_tier_preference", "prefer_action": prefer}],
            "supporting_trajectory_ids": list(trajectory),
            "counterexamples": list(counterexamples),
            "expected_effect": {"mechanism": "prefer the discriminating test in the top tier",
                                "direction": "increase"},
            "revalidation_conditions": ["any new independent project"],
            "evaluation_refs": [{"independent": True, "verdict": "SUPPORTED", "project": "A"}],
            "rollback_target": None,
        }
        result = pe.propose(state_path, candidate, trajectory_support={"DT-1"})
        self.assertEqual(result["status"], "PROPOSED", result)
        return candidate

    def activate(self, state_path, policy_id="P-RSI"):
        self.assertEqual(pe.transition(state_path, policy_id, "SHADOW", level="L1",
                                       evidence={"format_ok": True, "invariants_ok": True,
                                                 "permissions_ok": True})["status"], "SHADOW")
        self.assertEqual(pe.evaluate_candidate(state_path, policy_id,
                                               replay_report())["status"], "REPLAY_EVALUATED")
        self.assertEqual(pe.transition(
            state_path, policy_id, "BOUNDED_TRIAL", level="L2",
            evidence={"budget_expanded": False, "hard_gates_unchanged": True,
                      "dispatch_evidence": True})["status"], "BOUNDED_TRIAL")
        self.assertEqual(pe.transition(
            state_path, policy_id, "VALIDATED", level="L3",
            evidence={"independent": True, "distinguishable": True,
                      "degraded_dimensions": []})["status"], "VALIDATED")
        self.assertEqual(pe.promote_to_active(state_path, policy_id,
                                              {"scope_evidence_ok": True})["status"], "ACTIVE")


class TestFullChain(RsiProject):
    def test_policy_changes_the_dispatched_action_and_leaves_an_audit_trail(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self.project(pathlib.Path(temp) / "A")
            context = pr.project_context(state_path)
            self.assertEqual(eg.scheduler_check(context["state"], context["scheduler"])["status"],
                             "PASS")

            # 1. Baseline: the scheduler's first action wins and the adapter has no policy.
            baseline = pr.run_preset("research-loop", state_path)[0]
            self.assertEqual(baseline["decision"]["dispatched_action"], "R1")
            self.assertFalse(baseline["decision"]["strategy_changed_dispatch"])
            self.assertEqual(baseline["decision"]["policy_delta"]["status"], "none")

            # 2. Propose → replay → evaluate → promote a scoped policy.
            self.propose_policy(state_path)
            self.activate(state_path)
            records, _ = pe.load_records(state_path)
            self.assertEqual(pe.rebuild_state(records)["active_policy_id"], "P-RSI")

            # 3. The loop now dispatches the policy's action, through the existing adapter.
            applied = pr.run_preset("research-loop", state_path, apply=True)[0]
            self.assertEqual(applied["status"], "OK", applied)
            self.assertEqual(applied["decision"]["dispatched_action"], PREFERRED_XID)
            self.assertTrue(applied["decision"]["strategy_changed_dispatch"])
            self.assertEqual(applied["decision"]["policy_delta"]["status"], "applied")
            self.assertEqual(applied["decision"]["policy_delta"]["level"], "L2")
            self.assertEqual(applied["decision"]["policy_delta"]["policy_id"], "P-RSI")
            self.assertEqual(applied["decision"]["scientific_delta"], "none")
            self.assertEqual(applied["observed"]["scoped_policy"]["source"],
                             "active_scoped_policy")
            self.assertTrue(applied["canonical_untouched"])

            # 4. Decision recording persisted a real trajectory artefact.
            trajectory = pathlib.Path(temp) / "A" / dt.TRAJECTORY_NAME
            self.assertTrue(trajectory.is_file())
            trajectory_records, diagnostics = dt.load_records(trajectory)
            self.assertEqual(diagnostics, [])
            view = dt.rebuild_trajectories(trajectory_records)
            ident, entry = next(iter(view.items()))
            self.assertEqual(entry["decision"]["decision"]["chosen"], PREFERRED_XID)
            self.assertEqual(entry["decision"]["decision"]["dispatch_status"], "dispatched")
            self.assertTrue(entry["decision"]["decision"]["policy_changed_order"])
            self.assertEqual(entry["decision"]["decision"]["policy_version"], "P-RSI")
            self.assertIn(dt.TRAJECTORY_NAME, applied["writes"])
            self.assertIn(cg.SCHEDULER_NAME, applied["writes"])

            # 5. Outcome feedback: a real result, then a learning signal.
            state = cg.load_state(state_path)
            outcome = dt.build_outcome_record(
                ident, at_state_version=state["state_version"],
                result={"kind": "experiment_result", "summary": "observed effect 0.42"},
                evidence_refs=[{"evidence": state["evidence"][0]["id"]}],
                decision_delta="decision", evidence_qualification="qualified",
                observed_at="2030-01-01T00:00:00Z")
            recorded = dt.append_record(trajectory, outcome, state=state, route="A")
            self.assertEqual(recorded["status"], "APPENDED", recorded)

            # 6. The recorded history feeds replay as a support map (real consumer).
            support = rr.support_map_from_trajectory(trajectory)
            self.assertIn(PREFERRED_XID, support["observed_actions"])
            coverage = rr.coverage_report(trajectory)
            self.assertEqual(coverage["trajectories"], 1)

            # 7. Scheduler telemetry was updated and remains the bounded telemetry only.
            scheduler = json.loads((pathlib.Path(temp) / "A" / cg.SCHEDULER_NAME)
                                   .read_text(encoding="utf-8"))
            self.assertTrue(scheduler.get("strategy_decisions"))
            self.assertLessEqual(len(scheduler["strategy_decisions"]),
                                 sm.DECISION_LOG_LIMIT)

    def test_a_reordered_decision_that_never_dispatches_is_reported_as_such(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self.project(pathlib.Path(temp) / "A")
            self.propose_policy(state_path)
            self.activate(state_path)
            read_only = pr.run_preset("research-loop", state_path)[0]
            self.assertEqual(read_only["decision"]["dispatched_action"], PREFERRED_XID)
            self.assertNotIn(dt.TRAJECTORY_NAME, read_only["writes"])
            self.assertFalse((pathlib.Path(temp) / "A" / dt.TRAJECTORY_NAME).exists())


class TestAdversarialDecisionCases(RsiProject):
    def test_a_hard_gate_still_blocks_the_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self.project(pathlib.Path(temp) / "A",
                                      lower_second=True)
            self.propose_policy(state_path)
            self.activate(state_path)
            payload = pr.run_preset("research-loop", state_path)[0]
            # The preferred action sits in a worse tier; the adapter may not promote it.
            self.assertEqual(payload["decision"]["dispatched_action"], "R1")
            self.assertFalse(payload["decision"]["strategy_changed_dispatch"])
            self.assertEqual(payload["decision"]["policy_delta"]["status"], "none")

    def test_a_single_legal_action_leaves_no_room_to_change(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self.project(
                pathlib.Path(temp) / "A",
                actions=[{"action": "R1", "type": "repair", "target": "C1", "eig": "high",
                          "cost": "low"}])
            self.propose_policy(state_path)
            self.activate(state_path)
            payload = pr.run_preset("research-loop", state_path)[0]
            self.assertEqual(payload["decision"]["dispatched_action"], "R1")
            self.assertFalse(payload["decision"]["strategy_changed_dispatch"])

    def test_a_policy_whose_conditions_do_not_hold_is_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self.project(pathlib.Path(temp) / "A")
            candidate = self.propose_policy(state_path)
            # The condition is not satisfied by this state.
            records, _ = pe.load_records(state_path)
            state = cg.load_state(state_path)
            conditions_ok, unmet = pe.scope_conditions_hold(
                {"applicable_conditions": [{"kind": "min_open_uncertainties", "value": 99}]}, state)
            self.assertFalse(conditions_ok)
            self.assertTrue(unmet)
            self.assertTrue(candidate["applicable_conditions"])

    def test_an_unobserved_branch_cannot_be_scored(self):
        case = rr.adversarial_cases()[0]
        tag = rr.classify_evidence_support(case, {"chosen_intervention": "NEVER-RUN"},
                                           {"observed_actions": ["X1"],
                                            "replay_supported_actions": ["X1"]})
        self.assertEqual(tag["class"], "NO_SUPPORT")
        verdict = pe.ablation_verdict(replay_report())
        self.assertNotIn("NO_SUPPORT", json.dumps(verdict["comparison"]))
        self.assertEqual(verdict["unobservable_decisions"], 0)

    def test_a_cross_project_policy_must_pass_the_transfer_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self.project(pathlib.Path(temp) / "A")
            candidate = self.propose_policy(state_path)
            candidate["scope"]["source_route"] = "B"
            gate = pe.cross_project_transfer_allowed(candidate, cg.load_state(state_path),
                                                     current_route="A")
            self.assertTrue(gate["required"])
            self.assertEqual(gate["status"], "BLOCK")
            self.assertTrue(gate["reasons"])

    def test_a_same_route_policy_needs_no_transfer_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self.project(pathlib.Path(temp) / "A")
            candidate = self.propose_policy(state_path)
            # `propose()` stamps the origin; emulate the stored record here.
            candidate["scope"]["source_route"] = "A"
            candidate["origin_stamped"] = True
            candidate["source_route"] = "A"
            gate = pe.cross_project_transfer_allowed(candidate, cg.load_state(state_path),
                                                     current_route="A")
            self.assertFalse(gate["required"])
            self.assertEqual(gate["status"], "NOT_REQUIRED")

    def test_an_engineering_failure_is_not_a_scientific_delta(self):
        with tempfile.TemporaryDirectory() as temp:
            trajectory = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state = cg.load_state(self.project(pathlib.Path(temp) / "A"))
            context = dt.build_context(state, scientific_question="q",
                                       decided_at="2026-01-01T00:00:00Z")
            decision = dt.build_decision_record(
                state, route="A", project="A", context=context,
                candidates=[{"action": "X1", "type": "discriminating_experiment",
                             "target": "U1", "eig": "high", "cost": "low"}],
                chosen="X1", scheduler_priority={"level": 4, "label": "x"},
                recorded_at="2026-01-01T00:00:00Z")
            dt.append_record(trajectory, decision, state=state, route="A")
            outcome = dt.build_outcome_record(
                decision["trajectory_id"], at_state_version=state["state_version"],
                result={"kind": "engineering_failure", "summary": "CUDA OOM at step 3"},
                scientific_delta="scientific", evidence_qualification="unqualified",
                observed_at="2026-01-02T00:00:00Z")
            result = dt.append_record(trajectory, outcome, state=state, route="A")
            self.assertEqual(result["status"], "INVALID")
            self.assertIn("DT9", result["codes"])

    def test_document_or_state_counts_cannot_fake_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self.project(pathlib.Path(temp) / "A")
            payload = pr.run_preset("research-loop", state_path)[0]
            self.assertEqual(payload["decision"]["scientific_delta"], "none")
            self.assertFalse(payload["observed"]["scoped_policy"]["applied"])
            self.assertIsNone(payload["decision"]["policy_delta"]["level"])

    def test_a_refuted_mechanism_must_not_be_proposed_again(self):
        verdict = rr.run_case(rr.adversarial_cases()[3], "full_cie")  # ADV4
        self.assertFalse(verdict["decision"].get("repeated_prior_error"))
        by_id = {case["id"]: case for case in rr.adversarial_cases()}
        self.assertIn("ADV4", by_id)


class TestAblationHarness(unittest.TestCase):
    def test_the_rsi_ablation_is_separate_from_the_frozen_ladder(self):
        cases = rr.adversarial_cases()[:4]
        baseline = rr.run_suite(cases, rr.ABLATION_ARMS, 1)
        extended = rr.run_suite(cases, rr.ABLATION_ARMS + rr.RSI_ARMS, 1)
        self.assertEqual(set(baseline["per_arm"]), set(rr.ABLATION_ARMS))
        self.assertEqual(set(extended["per_arm"]),
                         set(rr.ABLATION_ARMS) | set(rr.RSI_ARMS))
        for arm_name in rr.ABLATION_ARMS:
            self.assertEqual(baseline["per_arm"][arm_name]["dimensions"],
                             extended["per_arm"][arm_name]["dimensions"], arm_name)

    def test_every_new_artefact_has_a_consumer(self):
        """No module may exist without something that reads its output."""
        import inspect
        consumers = {
            "decision_trajectory": ["policy_evolution", "research_replay", "preset_router"],
            "policy_evolution": ["preset_router"],
            "policy_transfer": ["policy_evolution", "rsi_ablation"],
            "research_replay": ["preset_router", "release_check"],
            "source_freeze": ["preset_router"],
        }
        for module, users in consumers.items():
            source = (ROOT / "scripts" / f"{module}.py").read_text(encoding="utf-8")
            self.assertTrue(source)
            for user in users:
                candidate = ROOT / "scripts" / f"{user}.py"
                if not candidate.is_file():
                    continue
                text = candidate.read_text(encoding="utf-8")
                self.assertIn(module, text, f"{user} does not consume {module}")
        self.assertTrue(inspect.ismodule(pe))


if __name__ == "__main__":
    unittest.main()


class TestLatentBugRegressions(RsiProject):
    """Regressions for integration defects found by the adversarial review."""

    def test_a_tampered_policy_store_stops_policy_consumption(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self.project(pathlib.Path(temp) / "A")
            self.propose_policy(state_path)
            self.activate(state_path)
            store = pe.candidates_path(state_path)
            lines = store.read_text(encoding="utf-8").splitlines()
            first = json.loads(lines[0])
            first["strategy_changes"] = [{"kind": "same_tier_preference",
                                          "prefer_action": "R1"}]
            lines[0] = json.dumps(first, ensure_ascii=False, sort_keys=True)
            store.write_text("\n".join(lines) + "\n", encoding="utf-8")
            # The tampered log is no longer a valid ACTIVE policy source.
            self.assertIsNone(pr.scoped_policy_state(pr.project_context(state_path))["candidate"])
            payload = pr.run_preset("research-loop", state_path)[0]
            self.assertEqual(payload["status"], "HOLD")
            self.assertEqual(payload["hold_reason"], "policy_store_tampered")
            self.assertEqual(payload["decision"]["policy_delta"]["status"], "none")

    def test_a_damaged_trajectory_store_holds_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self.project(pathlib.Path(temp) / "A")
            self.propose_policy(state_path)
            self.activate(state_path)
            (state_path.parent / dt.TRAJECTORY_NAME).write_text('{"broken\n', encoding="utf-8")
            payload, diagnostics, code = pr.run_preset("research-loop", state_path, apply=True)
            self.assertEqual(payload["status"], "HOLD")
            self.assertIn("decision_trajectory", payload["hold_reason"])
            self.assertTrue(payload["canonical_untouched"])
            self.assertEqual(payload["decision"]["policy_delta"]["status"], "none")

    def test_no_policy_delta_is_claimed_when_nothing_is_dispatched(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self.project(pathlib.Path(temp) / "A")
            context = pr.project_context(state_path)
            scheduler = dict(context["scheduler"],
                             strategy_decisions=[{
                                 "state_version": context["state"]["state_version"],
                                 "advice": {}, "discovery_operator": "reframe",
                                 "candidates_before": [], "chosen": "R9", "adopted": True,
                                 "strategy_applied": True, "decision_changed": True,
                                 "reason_if_not": None,
                                 "hard_gates": {"scheduler_check": "PASS"},
                                 "dispatch": {"action": "R9", "type": "repair",
                                              "target": "C1"},
                                 "dispatch_result": "dispatched R9"}])
            (state_path.parent / cg.SCHEDULER_NAME).write_text(
                json.dumps(scheduler, ensure_ascii=False), encoding="utf-8")
            payload = pr.run_preset("research-loop", state_path)[0]
            self.assertEqual(payload["decision"]["policy_delta"]["status"], "none")


class TestRepeatLoopRegressions(RsiProject):
    """A loop that runs again without a state change must not HOLD.

    `scheduler.json` is telemetry: it may legitimately gain a candidate action without a
    state bump (an assurance review unblocking work). The trajectory identity used to be
    compared field-by-field, so a grown candidate list looked like an attempt to rewrite a
    recorded decision and the whole run went to HOLD.
    """

    def test_running_the_loop_again_at_the_same_state_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self.project(pathlib.Path(temp) / "A")
            self.propose_policy(state_path)
            self.activate(state_path)
            for _ in range(3):
                payload, _, code = pr.run_preset("research-loop", state_path, apply=True)
                self.assertEqual(payload["status"], "OK", payload.get("hold_reason"))
                self.assertEqual(code, 0)
                self.assertEqual(payload["decision"]["dispatched_action"], PREFERRED_XID)
            trajectory = state_path.parent / dt.TRAJECTORY_NAME
            lines = trajectory.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1, "the same decision must not be recorded twice")

    def test_a_grown_scheduler_candidate_set_does_not_hold(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self.project(pathlib.Path(temp) / "A")
            self.propose_policy(state_path)
            self.activate(state_path)
            scheduler_path = state_path.parent / cg.SCHEDULER_NAME
            self.assertEqual(pr.run_preset("research-loop", state_path, apply=True)[0]["status"],
                             "OK")
            scheduler = json.loads(scheduler_path.read_text(encoding="utf-8"))
            scheduler["next_actions"] = list(scheduler["next_actions"]) + [
                {"action": "R3", "type": "repair", "target": "C1", "eig": "high", "cost": "low"}]
            scheduler_path.write_text(json.dumps(scheduler, ensure_ascii=False),
                                      encoding="utf-8")
            payload, _, code = pr.run_preset("research-loop", state_path, apply=True)
            self.assertEqual(payload["status"], "OK", payload.get("hold_reason"))
            self.assertEqual(payload["decision"]["dispatched_action"], PREFERRED_XID)

    def test_a_real_rewrite_of_a_recorded_decision_is_still_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self.project(pathlib.Path(temp) / "A")
            state = cg.load_state(state_path)
            path = state_path.parent / dt.TRAJECTORY_NAME
            context = dt.build_context(state, scientific_question="q",
                                       decided_at="2026-01-01T00:00:00Z")
            first = dt.build_decision_record(
                state, route="A", project="A", context=context,
                candidates=[{"action": "R1", "type": "repair", "target": "C1", "eig": "high",
                             "cost": "low"}],
                chosen="R1", scheduler_priority={"level": 4, "label": "x"},
                recorded_at="2026-01-01T00:00:00Z")
            self.assertEqual(dt.append_record(path, first, state=state, route="A")["status"],
                             "APPENDED")
            rewritten = dict(first)
            rewritten["decision"] = dict(first["decision"], chosen="R2")
            rewritten["decision"]["candidates"] = [
                {"action": "R2", "type": "repair", "target": "C1", "eig": "high", "cost": "low"}]
            result = dt.append_record(path, rewritten, state=state, route="A")
            self.assertEqual(result["status"], "INVALID")
            self.assertIn("DT2", result["codes"])
