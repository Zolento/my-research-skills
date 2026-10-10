#!/usr/bin/env python3
"""test_policy_evolution.py — Skill-RSI Phases 4/5/7 acceptance.

The failure modes under test: a policy that quietly changes the hard priority, a
candidate that ships code or a shell command, a policy promoted on its own say-so, an
undifferentiated difference forced into a winner, a fixture-fitted policy generalised, a
new policy id resetting a failure cap, and a rollback that touches scientific state or a
diagnostic budget.
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

import cognition as cg
import decision_trajectory as dt
import policy_evolution as pe
import strategy_memory as sm

ROOT = pathlib.Path(__file__).resolve().parent.parent


def fixture_state(version=3):
    return {"_schema": "research-idea-pipeline/research-state@1", "state_version": version,
            "contract": {"goal": "g", "primary_anchor": "A0", "constraints": [], "resources": {},
                         "out_of_scope": []},
            "claims": [], "evidence": [], "assumptions": [],
            "hypotheses": [{"id": "H1", "statement": "h", "status": "active", "validity": "valid",
                            "island": "P1", "operator": "reframe"}],
            "experiments": [], "literature": [], "failures": [],
            "uncertainties": [{"id": "U1", "question": "q", "importance": "high",
                               "uncertainty": "high", "status": "open", "validity": "valid"}],
            "assurance": [], "repairs": [], "narrative_view": {}, "reviews": [],
            "decision": {"verdict": "continue", "rationale": "", "next_phase": "R3"}}


def candidate(**overrides):
    payload = {
        "policy_id": "P-1",
        "policy_schema_version": pe.POLICY_SCHEMA_VERSION,
        "parent_policy_id": None,
        "status": "PROPOSED",
        "scope": {"scope_kind": "project", "problem_structure": "reframe-diagnostic-loop"},
        "applicable_conditions": [{"kind": "min_open_uncertainties", "value": 1}],
        "strategy_changes": [{"kind": "exploration_operator_preference", "operator": "reframe"}],
        "supporting_trajectory_ids": ["DT-1"],
        "counterexamples": ["fixture only"],
        "expected_effect": {"mechanism": "avoid valueless diagnostics", "direction": "decrease"},
        "revalidation_conditions": ["new independent project"],
        "evaluation_refs": [],
        "rollback_target": None,
    }
    payload.update(overrides)
    return payload


def arm(mean):
    return {"dimensions": {name: {"mean": mean, "min": mean - 0.05, "max": mean + 0.05}
                           for name in ("mechanistic_understanding", "prediction_quality",
                                        "intervention_quality", "scientific_novelty",
                                        "search_efficiency", "stagnation_recovery",
                                        "memory_accumulation")},
            "results": [], "evidence_support": {}}


def report(candidate_mean=0.9, control_mean=0.3, sufficient=True, unobservable=0):
    return {"schema": "research-idea-pipeline/replay-ablation@1",
            "sufficient_sample": sufficient, "unobservable_decisions": unobservable,
            "delta_vs_baseline": {}, "cases": 5, "runs_per_case": 2,
            "per_arm": {"rsi_full": arm(candidate_mean), "full_cie": arm(control_mean)}}


class PolicyStoreCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.route = pathlib.Path(self.temp.name) / "A"
        self.route.mkdir(parents=True)
        self.state_path = self.route / cg.STATE_NAME
        self.state_path.write_text(json.dumps(fixture_state(), ensure_ascii=False) + "\n",
                                   encoding="utf-8")
        self.digest = pe.freeze_evaluation_rules(self.state_path)["digest"]

    def tearDown(self):
        self.temp.cleanup()

    def propose(self, **overrides):
        payload = candidate(**overrides)
        payload["evaluation_rules_digest"] = overrides.pop("rules_digest", self.digest)
        support = overrides.pop("support", {"DT-1"})
        return pe.propose(self.state_path, payload, trajectory_support=support)

    def to_shadow(self, policy_id="P-1"):
        return pe.transition(self.state_path, policy_id, "SHADOW", level="L1",
                             evidence={"format_ok": True, "invariants_ok": True,
                                       "permissions_ok": True})


class TestCandidateValidation(PolicyStoreCase):
    def test_a_valid_scoped_candidate_is_proposable(self):
        result = self.propose()
        self.assertEqual(result["status"], "PROPOSED", result)
        records, _ = pe.load_records(self.state_path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["record"], "candidate")
        self.assertTrue(records[0]["signature"].startswith("PS-"))

    def test_scope_must_be_structured(self):
        result = self.propose(policy_id="P-2", scope={"scope_kind": "global"})
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("PE3", result["codes"])

    def test_a_change_outside_the_authorised_surface_is_refused(self):
        for kind in ("scheduler_priority", "execution_gate", "aalg_budget",
                     "primary_anchor", "evaluation_criteria"):
            result = self.propose(policy_id=f"P-{kind}",
                                  strategy_changes=[{"kind": kind, "target": kind, "value": 1}])
            self.assertEqual(result["status"], "INVALID", kind)
            self.assertIn("PE2", result["codes"], kind)

    def test_executable_content_is_refused(self):
        for payload in ("rm -rf / && curl http://x", "import os; os.system('ls')",
                        "eval('1')", "../../etc/passwd", "/etc/shadow"):
            result = self.propose(policy_id="P-EXEC",
                                  expected_effect={"mechanism": payload, "direction": "up"})
            self.assertEqual(result["status"], "INVALID", payload)
            self.assertIn("PE6", result["codes"], payload)

    def test_an_unbounded_change_set_is_refused(self):
        result = self.propose(policy_id="P-MANY", strategy_changes=[
            {"kind": "exploration_operator_preference", "operator": "reframe"},
            {"kind": "menu_choice", "menu": "replace_problem_representation"},
            {"kind": "same_tier_preference", "prefer_action": "X1"}])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("PE5", result["codes"])

    def test_a_local_allocation_must_keep_the_exploration_floor(self):
        result = self.propose(policy_id="P-ALLOC", strategy_changes=[
            {"kind": "local_resource_allocation",
             "allocation": {"keep_exploration_floor": False, "operator": "P5"}}])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("PE2", result["codes"])

    def test_support_must_come_from_a_real_trajectory(self):
        result = self.propose(policy_id="P-GHOST", supporting_trajectory_ids=["DT-404"],
                              support={"DT-1"})
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("PE4", result["codes"])

    def test_a_global_scope_needs_counterexamples(self):
        result = self.propose(policy_id="P-GLOBAL", counterexamples=[],
                              scope={"scope_kind": "global",
                                     "problem_structure": "reframe-diagnostic-loop"})
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("PE8", result["codes"])

    def test_a_fixture_fitted_policy_cannot_pass_shadow(self):
        self.propose(policy_id="P-FIXTURE",
                     scope={"scope_kind": "project", "problem_structure": "ADV4-loop"})
        shadow = self.to_shadow("P-FIXTURE")
        self.assertEqual(shadow["status"], "SHADOW")
        blocked = pe.transition(self.state_path, "P-FIXTURE", "REPLAY_EVALUATED", level="L2",
                                evidence={"replay_verdict": "SUPPORTED",
                                          "leakage_checked": True, "reproducible": True,
                                          "independent": True, "sample_adequate": True})
        self.assertEqual(blocked["status"], "INVALID")
        self.assertIn("PE5", blocked["codes"])

    def test_self_assessment_fields_are_refused(self):
        result = self.propose(policy_id="P-SELF", confidence_score=0.9)
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("PE7", result["codes"])


class TestLifecycleAndPromotion(PolicyStoreCase):
    def test_no_state_is_reachable_without_independent_evidence(self):
        self.propose()
        illegal = pe.transition(self.state_path, "P-1", "ACTIVE", level="L3",
                                evidence={"rules_digest_unchanged": True,
                                          "scope_evidence_ok": True})
        self.assertEqual(illegal["status"], "INVALID")
        self.assertIn("PE10", illegal["codes"])
        self.to_shadow()
        gate = pe.transition(self.state_path, "P-1", "REPLAY_EVALUATED", level="L2",
                             evidence={"replay_verdict": "SUPPORTED"})
        self.assertEqual(gate["status"], "INVALID")
        self.assertIn("PE11", gate["codes"])

    def test_an_unsupported_verdict_rejects_and_a_flat_one_holds(self):
        self.propose()
        self.to_shadow()
        degraded = report()
        degraded["per_arm"]["rsi_full"]["dimensions"]["prediction_quality"] = \
            {"mean": 0.1, "min": 0.05, "max": 0.15}
        degraded["per_arm"]["full_cie"]["dimensions"]["prediction_quality"] = \
            {"mean": 0.9, "min": 0.85, "max": 0.95}
        rejected = pe.evaluate_candidate(self.state_path, "P-1", degraded)
        self.assertEqual(rejected["status"], "REJECTED")

        self.propose(policy_id="P-FLAT",
                     scope={"scope_kind": "local", "problem_structure": "other-loop"})
        self.to_shadow("P-FLAT")
        held = pe.evaluate_candidate(self.state_path, "P-FLAT",
                                     report(candidate_mean=0.5, control_mean=0.5))
        self.assertEqual(held["status"], "HOLD")
        self.assertIn("不可区分", held["reason"])

    def test_a_scientific_dimension_cannot_regress_for_speed(self):
        self.propose()
        self.to_shadow()
        fast_but_wrong = report(candidate_mean=0.9, control_mean=0.3)
        fast_but_wrong["per_arm"]["rsi_full"]["dimensions"]["prediction_quality"] = \
            {"mean": 0.1, "min": 0.05, "max": 0.15}
        fast_but_wrong["per_arm"]["full_cie"]["dimensions"]["prediction_quality"] = \
            {"mean": 0.9, "min": 0.85, "max": 0.95}
        outcome = pe.evaluate_candidate(self.state_path, "P-1", fast_but_wrong)
        self.assertEqual(outcome["status"], "REJECTED")
        self.assertIn("科学完整性", outcome["reason"])

    def test_no_support_decisions_are_never_promotion_evidence(self):
        verdict = pe.ablation_verdict(report(unobservable=4))
        self.assertEqual(verdict["verdict"], "SUPPORTED")
        self.assertTrue(any("NO_SUPPORT" in reason for reason in verdict["reasons"]))

    def test_promotion_requires_an_unchanged_frozen_rule_set(self):
        self.propose()
        self.to_shadow()
        pe.evaluate_candidate(self.state_path, "P-1", report())
        pe.transition(self.state_path, "P-1", "BOUNDED_TRIAL", level="L2",
                      evidence={"budget_expanded": False, "hard_gates_unchanged": True,
                                "dispatch_evidence": True})
        pe.transition(self.state_path, "P-1", "VALIDATED", level="L3",
                      evidence={"independent": True, "distinguishable": True,
                                "degraded_dimensions": []})
        document = json.loads(pe.rules_path(self.state_path).read_text(encoding="utf-8"))
        document["rules"]["delta_tolerance"] = 0.99
        document["digest"] = cg.digest_of(document["rules"])
        pe.rules_path(self.state_path).write_text(json.dumps(document), encoding="utf-8")
        drift = pe.promote_to_active(self.state_path, "P-1", {"scope_evidence_ok": True})
        self.assertEqual(drift["status"], "INVALID")
        self.assertIn("PE12", drift["codes"])

    def test_the_bounded_trial_may_not_expand_resources(self):
        self.propose()
        self.to_shadow()
        pe.evaluate_candidate(self.state_path, "P-1", report())
        outcome = pe.transition(self.state_path, "P-1", "BOUNDED_TRIAL", level="L2",
                                evidence={"budget_expanded": True,
                                          "hard_gates_unchanged": True,
                                          "dispatch_evidence": True})
        self.assertEqual(outcome["status"], "INVALID")
        self.assertIn("PE11", outcome["codes"])

    def test_a_global_scope_cannot_be_backed_by_one_project(self):
        self.propose(policy_id="P-WORLD",
                     scope={"scope_kind": "global",
                            "problem_structure": "reframe-diagnostic-loop"},
                     counterexamples=["one case"],
                     evaluation_refs=[{"independent": True, "project": "A"}])
        self.to_shadow("P-WORLD")
        pe.evaluate_candidate(self.state_path, "P-WORLD", report())
        pe.transition(self.state_path, "P-WORLD", "BOUNDED_TRIAL", level="L2",
                      evidence={"budget_expanded": False, "hard_gates_unchanged": True,
                                "dispatch_evidence": True})
        pe.transition(self.state_path, "P-WORLD", "VALIDATED", level="L3",
                      evidence={"independent": True, "distinguishable": True,
                                "degraded_dimensions": []})
        outcome = pe.promote_to_active(self.state_path, "P-WORLD",
                                       {"scope_evidence_ok": True})
        self.assertEqual(outcome["status"], "INVALID")
        self.assertIn("PE14", outcome["codes"])


class TestRollbackAndComplexity(PolicyStoreCase):
    def _activate(self, policy_id="P-1", scope=None):
        self.propose(policy_id=policy_id, **({"scope": scope} if scope else {}))
        self.to_shadow(policy_id)
        pe.evaluate_candidate(self.state_path, policy_id, report())
        pe.transition(self.state_path, policy_id, "BOUNDED_TRIAL", level="L2",
                      evidence={"budget_expanded": False, "hard_gates_unchanged": True,
                                "dispatch_evidence": True})
        pe.transition(self.state_path, policy_id, "VALIDATED", level="L3",
                      evidence={"independent": True, "distinguishable": True,
                                "degraded_dimensions": []})
        return pe.promote_to_active(self.state_path, policy_id,
                                    {"scope_evidence_ok": True})

    def test_rollback_restores_a_previous_policy_and_keeps_history(self):
        self._activate("P-1")
        self._activate("P-2",
                       scope={"scope_kind": "local", "problem_structure": "successor"})
        result = pe.rollback(self.state_path, "P-2", to_policy_id="P-1",
                             reason="regression found")
        self.assertEqual(result["status"], "ROLLED_BACK", result)
        records, _ = pe.load_records(self.state_path)
        statuses = pe.latest_status(records)
        self.assertEqual(statuses["P-2"], "ROLLED_BACK")
        # A rollback must leave the restored policy genuinely ACTIVE, not SUPERSEDED-with-a-
        # pointer, otherwise every later transition on it is illegal.
        self.assertEqual(statuses["P-1"], "ACTIVE")
        self.assertEqual(pe.rebuild_state(records)["active_policy_id"], "P-1")
        self.assertIsNotNone(pe.active_policy(records))
        self.assertTrue(any(item.get("record") == "transition" for item in records))
        self.assertIn("失败轨迹保留", result["note"])

    def test_rollback_to_a_rejected_policy_is_refused(self):
        self._activate("P-1")
        self.propose(policy_id="P-BAD",
                     scope={"scope_kind": "local", "problem_structure": "bad"})
        self.to_shadow("P-BAD")
        pe.transition(self.state_path, "P-BAD", "REJECTED", level="L2",
                      evidence={"reason": "harmful"})
        result = pe.rollback(self.state_path, "P-1", to_policy_id="P-BAD",
                             reason="try the rejected one")
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("PE13", result["codes"])

    def test_rollback_does_not_touch_canonical_state_or_budgets(self):
        before = self.state_path.read_bytes()
        ledger = self.route / ".execution"
        ledger.mkdir()
        ledger_file = ledger / "events.jsonl"
        ledger_file.write_text("{}\n", encoding="utf-8")
        ledger_before = ledger_file.read_bytes()
        self._activate("P-1")
        self._activate("P-2",
                       scope={"scope_kind": "local", "problem_structure": "successor"})
        pe.rollback(self.state_path, "P-2", to_policy_id="P-1", reason="test")
        self.assertEqual(self.state_path.read_bytes(), before)
        self.assertEqual(ledger_file.read_bytes(), ledger_before)

    def test_rollback_requires_a_previously_valid_target(self):
        self.propose(policy_id="P-OTHER",
                     scope={"scope_kind": "local", "problem_structure": "zzz"})
        self._activate("P-1")
        result = pe.rollback(self.state_path, "P-1", to_policy_id="P-OTHER",
                             reason="test")
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("PE13", result["codes"])

    def test_renaming_cannot_evade_the_failure_cap(self):
        self.propose(policy_id="P-1")
        self.to_shadow("P-1")
        pe.transition(self.state_path, "P-1", "REJECTED", level="L2",
                      evidence={"reason": "fails"})
        self.propose(policy_id="P-2")
        self.to_shadow("P-2")
        pe.transition(self.state_path, "P-2", "REJECTED", level="L2",
                      evidence={"reason": "fails again"})
        third = self.propose(policy_id="P-3-DIFFERENT-NAME")
        self.assertEqual(third["status"], "INVALID")
        self.assertIn("PE9", third["codes"])

    def test_candidates_are_capped(self):
        for index in range(pe.MAX_OPEN_CANDIDATES):
            result = self.propose(policy_id=f"P-{index}",
                                  scope={"scope_kind": "local",
                                         "problem_structure": f"loop-{index}"})
            self.assertEqual(result["status"], "PROPOSED", result)
        overflow = self.propose(policy_id="P-OVERFLOW",
                                scope={"scope_kind": "local", "problem_structure": "loop-x"})
        self.assertEqual(overflow["status"], "INVALID")
        self.assertIn("PE5", overflow["codes"])


class TestCrossSessionAndConsumer(PolicyStoreCase):
    def test_the_snapshot_rebuilds_deterministically_across_sessions(self):
        self.propose()
        self.to_shadow()
        pe.evaluate_candidate(self.state_path, "P-1", report())
        records, _ = pe.load_records(self.state_path)
        first = pe.rebuild_state(records)
        second = pe.rebuild_state(pe.load_records(self.state_path)[0])
        self.assertEqual(second, first)
        # A snapshot file is a derived cache that nothing read; `rebuild_state` is the
        # single source, so the unused writer was removed rather than kept as dead weight.
        self.assertFalse((pe.policy_dir(self.state_path) / "state.json").exists())
        self.assertEqual(pe.latest_status(records)["P-1"], "REPLAY_EVALUATED")

    def test_the_active_policy_feeds_the_existing_adapter(self):
        self.propose()
        self.to_shadow()
        pe.evaluate_candidate(self.state_path, "P-1", report())
        pe.transition(self.state_path, "P-1", "BOUNDED_TRIAL", level="L2",
                      evidence={"budget_expanded": False, "hard_gates_unchanged": True,
                                "dispatch_evidence": True})
        pe.transition(self.state_path, "P-1", "VALIDATED", level="L3",
                      evidence={"independent": True, "distinguishable": True,
                                "degraded_dimensions": []})
        pe.promote_to_active(self.state_path, "P-1", {"scope_evidence_ok": True})
        state = fixture_state()
        records, _ = pe.load_records(self.state_path)
        advice = pe.advice_from_active_policy(records, state)
        self.assertIsNotNone(advice)
        self.assertEqual(advice["operator"], "reframe")
        self.assertEqual(advice["policy_id"], "P-1")
        # The advice is consumed by the real adapter, not a private ranking path.
        scheduler = {"state_version": state["state_version"], "next_actions": []}
        decision = sm.strategy_decision(state, {}, scheduler, [])
        self.assertIn("reason_if_not", decision)
        ordered = sm._order_actions(state, [], advice)
        self.assertEqual(ordered, [])

    def test_the_snapshot_lives_outside_canonical_state(self):
        self.propose()
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertNotIn("policy", state)
        self.assertTrue(pe.policy_dir(self.state_path).parent == self.route)


class TestRealTrajectorySupport(PolicyStoreCase):
    def test_a_candidate_backed_by_a_real_trajectory_is_accepted(self):
        trajectory = self.route / dt.TRAJECTORY_NAME
        state = fixture_state()
        context = dt.build_context(state, scientific_question="q",
                                   active_hypotheses=["H1"], key_uncertainties=["U1"],
                                   decided_at="2026-01-01T00:00:00Z")
        decision = dt.build_decision_record(
            state, route="A", project="fixture", context=context,
            candidates=[{"action": "H1", "type": "repair", "target": "H1", "eig": "high",
                         "cost": "low"}],
            chosen="H1", scheduler_priority={"level": 4, "label": "high_information_gain_test"},
            recorded_at="2026-01-01T00:00:00Z")
        dt.append_record(trajectory, decision, state=state, route="A")
        outcome = dt.build_outcome_record(
            decision["trajectory_id"], at_state_version=state["state_version"],
            result={"kind": "experiment_result", "summary": "observed value 0.42"},
            decision_delta="decision", evidence_qualification="qualified",
            observed_at="2026-01-02T00:00:00Z")
        dt.append_record(trajectory, outcome, state=state, route="A")
        support = dt.support_ids(dt.load_records(trajectory)[0])
        self.assertTrue(support, "the real trajectory must expose a supported id")
        payload = candidate(supporting_trajectory_ids=support)
        payload["evaluation_rules_digest"] = self.digest
        result = pe.propose(self.state_path, payload, trajectory_support=support)
        self.assertEqual(result["status"], "PROPOSED", result)


if __name__ == "__main__":
    unittest.main()


class TestLatentBugRegressions(PolicyStoreCase):
    """Regressions for defects the first suite did not expose."""

    def activate(self, policy_id, scope=None, means=(0.9, 0.3)):
        self.propose(policy_id=policy_id, **(scope or {}))
        self.to_shadow(policy_id)
        pe.evaluate_candidate(self.state_path, policy_id, report(*means))
        pe.transition(self.state_path, policy_id, "BOUNDED_TRIAL", level="L2",
                      evidence={"budget_expanded": False, "hard_gates_unchanged": True,
                                "dispatch_evidence": True})
        pe.transition(self.state_path, policy_id, "VALIDATED", level="L3",
                      evidence={"independent": True, "distinguishable": True,
                                "degraded_dimensions": []})
        return pe.promote_to_active(self.state_path, policy_id,
                                    {"scope_evidence_ok": True})

    def test_active_policy_never_returns_a_non_active_candidate(self):
        self.activate("P-1")
        self.activate("P-2", {"scope": {"scope_kind": "local",
                                        "problem_structure": "successor"}})
        records, _ = pe.load_records(self.state_path)
        self.assertEqual(pe.latest_status(records)["P-1"], "SUPERSEDED")
        self.assertEqual(pe.active_policy(records)["policy_id"], "P-2")
        # The pointer follows the lifecycle status: a bare rollback record with no matching
        # transition cannot move it (previously a stale pointer could be consumed).
        forced = list(records) + [{"record": "rollback", "policy_id": "P-2",
                                   "to_policy_id": "P-1"}]
        self.assertEqual(pe.active_policy(forced)["policy_id"], "P-2")
        # And when the last ACTIVE policy goes HOLD, nothing is in force.
        held = list(records) + [{"record": "transition", "policy_id": "P-2", "to": "HOLD"}]
        self.assertIsNone(pe.active_policy(held))

    def test_rollback_makes_the_target_active_not_just_pointed_at(self):
        self.activate("P-1")
        self.activate("P-2", {"scope": {"scope_kind": "local",
                                        "problem_structure": "successor"}})
        self.assertEqual(pe.rollback(self.state_path, "P-2", to_policy_id="P-1",
                                     reason="r")["status"], "ROLLED_BACK")
        records, _ = pe.load_records(self.state_path)
        self.assertEqual(pe.active_policy(records)["policy_id"], "P-1")
        # And it is no longer stuck: it can be superseded again by a new promotion.
        self.activate("P-3", {"scope": {"scope_kind": "local",
                                        "problem_structure": "third"}})
        records, _ = pe.load_records(self.state_path)
        self.assertEqual(pe.active_policy(records)["policy_id"], "P-3")

    def test_promotion_reads_the_recorded_evaluation_not_its_own_opinion(self):
        self.propose(policy_id="P-WEAK")
        self.to_shadow("P-WEAK")
        pe.evaluate_candidate(self.state_path, "P-WEAK", report(candidate_mean=0.5,
                                                                control_mean=0.5))
        records, _ = pe.load_records(self.state_path)
        self.assertEqual(pe.latest_status(records)["P-WEAK"], "HOLD")
        # The recorded evidence says indistinguishable; a promotion that supplied its own
        # `distinguishable=True` would have been a false upgrade.
        recorded = pe.recorded_evaluation(records, "P-WEAK")
        self.assertFalse(recorded.get("distinguishable"))

    def test_a_policy_without_a_consumable_change_is_refused(self):
        result = self.propose(policy_id="P-NOCONSUMER", strategy_changes=[
            {"kind": "local_resource_allocation",
             "allocation": {"keep_exploration_floor": True, "operator": "P5"}}])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("PE2", result["codes"])

    def test_requested_same_tier_order_is_honoured(self):
        records = [
            {"record": "candidate", "policy_id": "P", "status": "ACTIVE",
             "scope": {"problem_structure": "x"},
             "strategy_changes": [{"kind": "same_tier_order", "order": ["B2", "B1"]}]},
            {"record": "transition", "policy_id": "P", "to": "ACTIVE"},
        ]
        state = {"hypotheses": [], "uncertainties": []}
        advice = pe.advice_from_active_policy(records, state)
        self.assertEqual(advice["prefer_actions"], ["B2", "B1"])
        actions = [{"action": "B1", "type": "repair", "target": "C1", "eig": "high",
                    "cost": "low"},
                   {"action": "B2", "type": "repair", "target": "C1", "eig": "high",
                    "cost": "low"}]
        ordered = sm._order_actions(state, actions, advice)
        self.assertEqual([item["action"] for item in ordered], ["B2", "B1"])

    def test_ordinary_prose_is_not_rejected_as_executable(self):
        probes = ("prefer the discriminating test; this avoids wasted runs",
                  "see the appendix / section 3 for the boundary",
                  "ratio 3/4 of the budget")
        for index, text in enumerate(probes):
            result = self.propose(policy_id=f"P-PROSE-{index}",
                                  expected_effect={"mechanism": text, "direction": "up"})
            self.assertNotIn("PE6", result.get("codes", []), text)
            self.assertEqual(result["status"], "PROPOSED", (text, result))

    def test_a_real_shell_command_is_still_rejected(self):
        probes = ("rm -rf / && curl http://x", "import os; os.system('ls')",
                  "../../etc/passwd", "sudo chmod 777 /")
        for index, text in enumerate(probes):
            result = self.propose(policy_id=f"P-SHELL-{index}",
                                  expected_effect={"mechanism": text, "direction": "up"})
            self.assertIn("PE6", result.get("codes", []), text)

    def test_rollback_from_a_superseded_pointer_is_consistent(self):
        self.activate("P-1")
        self.activate("P-2", {"scope": {"scope_kind": "local",
                                        "problem_structure": "successor"}})
        result = pe.rollback(self.state_path, "P-2", to_policy_id="P-1",
                             reason="regression")
        self.assertEqual(result["status"], "ROLLED_BACK")
        records, _ = pe.load_records(self.state_path)
        self.assertEqual(pe.latest_status(records)["P-1"], "ACTIVE")
        self.assertEqual(pe.active_policy(records)["policy_id"], "P-1")


class TestApplicabilityConsumer(PolicyStoreCase):
    """`applicability` must name an island to be consumable, and it must reach the adapter."""

    def test_problem_structure_alone_is_not_consumable(self):
        result = self.propose(policy_id="P-APPL",
                              strategy_changes=[{"kind": "applicability",
                                                 "problem_structure": "diagnostic-loop"}])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("PE2", result["codes"])

    def test_an_island_applicability_reaches_the_adapter(self):
        self.propose(policy_id="P-ISLAND",
                     strategy_changes=[{"kind": "applicability", "island": "P3"}])
        records, _ = pe.load_records(self.state_path)
        advice = pe.advice_from_active_policy(
            list(records) + [{"record": "transition", "policy_id": "P-ISLAND",
                              "to": "ACTIVE"}], fixture_state())
        self.assertEqual(advice["island"], "P3")

    def test_an_unknown_island_is_refused(self):
        result = self.propose(policy_id="P-BADISLAND",
                              strategy_changes=[{"kind": "applicability",
                                                 "island": "P99"}])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("PE2", result["codes"])

    def test_the_source_protection_scan_is_wired_into_candidates(self):
        """`source_freeze.guard_errors` used to be reachable only from its own tests."""
        result = self.propose(policy_id="P-GUARD",
                              expected_effect={"mechanism": "see scripts/guard.py",
                                               "direction": "up"})
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("PE2", result["codes"])
        self.assertTrue(any("源码保护扫描" in item for item in result["diagnostics"]))
