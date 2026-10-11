#!/usr/bin/env python3
"""test_insight_to_method.py — I2M 的对抗性验收（任务 §六 1—12 + 锚点补充要求）。

覆盖两类行为：

* **能力**：readiness → synthesis → design contract → minimal test → progress；
* **运行时**：`preset_router._loop_step` 在停滞且机制可用时**真的**改走方法步骤，
  非方法主锚点不被强行转成算法，且 I2M 永远不会越过硬门禁。
"""

from __future__ import annotations

import copy
import json
import pathlib
import sys
import tempfile
import unittest

import cognition as cg
import insight_to_method as i2m
import policy_evolution as pe
import preset_router as pr
import state_check
import test_state_check as fixture

METRIC = "recall@10"


def base_state(*, anchor="performance", stagnant=False, greed=False):
    """A legal state (all required fields) plus a scheduler that signals stagnation."""
    state = copy.deepcopy(fixture.valid_state())
    state["contract"] = {"goal": "提升长尾检索召回", "primary_anchor": anchor,
                         "target_metric": METRIC, "constraints": [], "resources": {},
                         "out_of_scope": [], "outcome_policy": {}}
    state["experiments"] = []
    for hypothesis in state.get("hypotheses", []):
        hypothesis.update({"intervention_axis": "loss_reweighting",
                           "nearest_prior": "focal loss",
                           "novelty_source": "样本层级重加权"})
    for uncertainty in state.get("uncertainties", []):
        uncertainty["cheapest_discriminating_test"] = "小规模长尾子集对照"
    if greed:
        for evidence in state.get("evidence", []):
            evidence["epistemic_status"] = "Conjecture"
    records = [{"experiment": f"X0{i}", "predicted_information_gain": "high",
                "observed_delta": {"claim_status_changes": [], "uncertainty_changes": [],
                                   "hypothesis_status_changes": [], "new_uncertainties": [],
                                   "unexpected_observations": 0},
                "actual_information_gain": "zero"} for i in (1, 2)] if stagnant else []
    scheduler = {"state_version": state.get("state_version"),
                 "next_actions": [{"action": "X1", "type": "discriminating_experiment",
                                   "target": "U3", "eig": "high", "cost": "low"}],
                 "eig_calibration": {"records": records}}
    return state, scheduler


def loop_step(state, scheduler):
    return pr._loop_step({"state_path": pathlib.Path("/tmp/i2m-state.json"), "state": state,
                          "scheduler": scheduler,
                          "index": {"state_version": state.get("state_version")},
                          "revisions": [], "route_dir": pathlib.Path("/tmp")})


def insight(**overrides):
    payload = {"problem_ref": "contract", "insight_refs": ["H42"],
               "mechanism": "头部样本主导梯度方向",
               "intervention_levers": ["loss_reweighting"],
               "predictions": [{"observation": "长尾 recall 上升"}],
               "falsifiers": ["长尾 recall 不升"],
               "comparators": ["no_intervention", "focal loss"],
               "minimal_experiment": {"plan": "小规模长尾子集对照"},
               "prior_art": [{"method": "focal loss"}],
               "novelty_boundary": "按样本层级而非类别重加权",
               "target_metric": METRIC}
    payload.update(overrides)
    return payload


def candidate(cid="M1", kind="objective", mechanism="alpha", formulation="L1", **overrides):
    payload = {"candidate_id": cid, "intervention": {"kind": kind},
               "how_it_addresses": "针对长尾", "mechanism_basis": "梯度主导",
               "structural_difference": "样本层级", "minimal_implementation_complexity": "low",
               "expected_benefit": "+2pt", "resource_cost": "low",
               "failure_boundary": ["不升则无效"], "falsifiable_predictions": ["recall 上升"],
               "distinctive_mechanism": mechanism, "mathematical_formulation": formulation,
               "method_hypothesis_ref": "H42", "algorithm_steps": ["统计频次", "重加权"]}
    payload.update(overrides)
    return payload


def contract(state, **overrides):
    payload = {"problem_ref": "contract", "insight_refs": ["H42"],
               "method_hypothesis_ref": "H42",
               "intervention": {"kind": "objective", "change": "长尾感知重加权"},
               "mathematical_formulation": "L = Σ w_i l_i",
               "algorithm_steps": ["统计频次", "构造权重", "训练"],
               "nearest_prior": "focal loss", "distinctive_mechanism": "样本层级重加权",
               "predictions": [{"observation": "长尾 recall 上升"}], "falsifiers": ["不升"],
               "minimal_test": {"plan": "小规模"}, "comparators": ["no_intervention", "focal loss"],
               "success_criteria": ["recall@10 +2pt"], "stop_rules": ["无提升则停止"],
               "evidence_status": i2m.VERDICT_HYPOTHESIS, "rules_digest": "sha256:rules"}
    payload.update(overrides)
    return payload


MINIMAL_PLAN = {"implementation_change": "长尾重加权层", "expected_delta": "recall@10 上升",
                "comparators": ["no_intervention", "focal loss"],
                "primary_metrics": [METRIC], "decision_criteria": ["+2pt"],
                "stop_rules": ["无提升停止"],
                "fairness": {"capacity": True, "intervention_strength": True,
                             "optimization": True, "compute_budget": True},
                "preregistration_digest": "sha256:pre"}


# ---------------------------------------------------------------------------
# 1—4: readiness, unverified mechanisms, redirection, non-actionable insight
# ---------------------------------------------------------------------------

class TestReadiness(unittest.TestCase):
    def test_1_a_stagnant_loop_is_redirected_from_explanation_to_method(self):
        """Scenario 1: enough mechanism evidence, yet diagnostics keep being generated."""
        state, scheduler = base_state(stagnant=True)
        step = loop_step(state, scheduler)
        self.assertEqual(step["phase"], "I2M", step)
        self.assertEqual(step["step"], "Synthesize", step)
        self.assertNotEqual(step.get("dispatched_action"), "X1")
        self.assertIn("diagnosis_stagnant", step.get("trigger", ""))

    def test_1b_a_healthy_loop_is_not_hijacked(self):
        """The same state without stagnation still follows the Scheduler."""
        state, scheduler = base_state(stagnant=False)
        step = loop_step(state, scheduler)
        self.assertEqual(step["phase"], "R3—R6/R8", step)
        self.assertFalse(step.get("i2m"))

    def test_2_a_method_may_rest_on_an_unverified_mechanism(self):
        """Scenario 2: allowed, but never reported as verified."""
        state, _ = base_state(greed=True)          # evidence demoted to Conjecture
        readiness = i2m.insight_readiness(state, insight())
        self.assertEqual(readiness["mechanism_status"], i2m.VERDICT_HYPOTHESIS)
        self.assertEqual(readiness["verdict"], i2m.VERDICT_HYPOTHESIS)
        self.assertEqual(readiness["evidence_backing"], [])

    def test_2b_self_declared_verification_is_recorded_as_unsupported(self):
        state, _ = base_state(greed=True)
        readiness = i2m.insight_readiness(state, insight(mechanism_status="VERIFIED"))
        self.assertIn("I2M14", {item["rule"] for item in readiness["diagnostics"]})
        self.assertEqual(readiness["verdict"], i2m.VERDICT_HYPOTHESIS)

    def test_2c_readiness_is_not_proof(self):
        state, _ = base_state()
        readiness = i2m.insight_readiness(state, insight())
        self.assertIn("不是机制已被证实", readiness["notes"])

    def test_3_diagnosis_that_cannot_change_the_decision_redirects(self):
        """Scenario 3: zero streak with an unsatisfiable insight → design/stop, not another round."""
        state, scheduler = base_state(stagnant=True)
        step = loop_step(state, scheduler)
        self.assertEqual(step["stage"], "synthesis")
        decision = step["i2m"]["decision"]["decision"]
        self.assertIn(decision, (i2m.DECISION_RESYNTHESIZE, i2m.DECISION_STOP_OR_R14,
                                 i2m.DECISION_DISCRIMINATE))

    def test_4_a_non_actionable_insight_is_never_packaged_as_a_method(self):
        """Scenario 4: no lever → refuse synthesis instead of inventing a method."""
        state, _ = base_state()
        for hypothesis in state["hypotheses"]:
            hypothesis.pop("intervention_axis", None)
            hypothesis.pop("operator", None)
            hypothesis.pop("variable", None)
            hypothesis.pop("intervention", None)
        readiness = i2m.insight_readiness(state, insight(intervention_levers=[],
                                                         insight_refs=["H42"]))
        self.assertEqual(readiness["verdict"], i2m.VERDICT_NOT_ACTIONABLE)
        self.assertIn(i2m.CRITERION_INTERVENTION, readiness["missing"])
        outcome = i2m.synthesize_methods(state, readiness, [candidate(), candidate("M2")])
        self.assertEqual(outcome["status"], "INVALID")
        self.assertIn("I2M15", {item["rule"] for item in outcome["diagnostics"]})

    def test_4b_unresolvable_references_cannot_become_facts(self):
        state, _ = base_state()
        readiness = i2m.insight_readiness(state, insight(insight_refs=["H404"]))
        self.assertIn("I2M6", {item["rule"] for item in readiness["diagnostics"]})


# ---------------------------------------------------------------------------
# 5—8: contract, contribution claims, GPU gate, failure taxonomy
# ---------------------------------------------------------------------------

class TestContractAndTestGates(unittest.TestCase):
    def test_5_a_contract_without_math_intervention_or_predictions_is_refused(self):
        state, _ = base_state()
        self.assertFalse(i2m.design_contract_errors(state, contract(state)))
        for field, rule in (("mathematical_formulation", "I2M30"),
                            ("algorithm_steps", "I2M31"),
                            ("falsifiers", "I2M34"),
                            ("comparators", "I2M35"),
                            ("stop_rules", "I2M37")):
            with self.subTest(field=field):
                broken = contract(state, **{field: "" if field != "comparators"
                                            and field != "stop_rules"
                                            and field != "algorithm_steps"
                                            and field != "falsifiers" else []})
                codes = i2m._rules(i2m.design_contract_errors(state, broken))
                self.assertTrue({rule, "I2M25"} & codes, codes)

    def test_5b_a_hyperparameter_only_intervention_is_refused(self):
        state, _ = base_state()
        broken = contract(state, intervention={"kind": "hyperparameter"})
        self.assertIn("I2M29", i2m._rules(i2m.design_contract_errors(state, broken)))

    def test_5c_an_unverifiable_novelty_claim_cannot_be_asserted(self):
        state, _ = base_state(greed=True)
        broken = contract(state, evidence_status="supported")
        self.assertIn("I2M39", i2m._rules(i2m.design_contract_errors(state, broken)))

    def test_6_no_code_change_or_trustworthy_result_means_no_contribution(self):
        """Scenario 6: explanation rewrites and self-scores are not method progress."""
        state, _ = base_state()
        before = dict(state["hypotheses"][0], method={"intervention": "a"})
        after = dict(state["hypotheses"][0], method={"intervention": "b"})
        progress = i2m.method_progress(state, before=before, after=after,
                                       previous_evidence=[e["id"] for e in state["evidence"]])
        self.assertFalse(progress["progress"], progress)
        self.assertIn("narrative_view", progress["excluded_signals"])
        grown = copy.deepcopy(state)
        grown["evidence"] = [*grown["evidence"],
                             {"id": "E900", "kind": "experiment_result",
                              "epistemic_status": "Observed", "validity": {"status": "valid"}}]
        self.assertTrue(i2m.method_progress(
            grown, before=before, after=after,
            previous_evidence=[e["id"] for e in state["evidence"]])["progress"])

    def test_6b_a_contract_alone_does_not_complete_a_method(self):
        state, _ = base_state()
        decision = i2m.advance(state, readiness=i2m.insight_readiness(state, insight()),
                               contract=contract(state))
        self.assertEqual(decision["decision"], i2m.DECISION_CONTINUE)
        self.assertIn("设计→实现→有效性", decision["reason"])

    def test_7_no_execution_eligibility_means_no_gpu(self):
        """Scenario 7: the pre-execution gates keep their authority over I2M."""
        state, _ = base_state()
        plan = dict(MINIMAL_PLAN, gpu_required=True)
        self.assertIn("I2M51", i2m._rules(i2m.minimal_test_errors(state, plan)),
                      "需要 GPU 但缺少执行资格信息时必须拒绝")
        self.assertIn("I2M51", i2m._rules(i2m.minimal_test_errors(
            state, plan, gate={"status": "HOLD", "errors": ["PEIG"]})))
        eligible = dict(plan, execution_eligibility={"peig": "PASS"},
                        preregistration_digest="sha256:pre")
        self.assertFalse(i2m.minimal_test_errors(
            state, eligible, gate={"status": "PASS"}))

    def test_7b_an_unfair_comparison_is_refused(self):
        state, _ = base_state()
        unfair = dict(MINIMAL_PLAN, fairness={"capacity": True})
        self.assertIn("I2M49", i2m._rules(i2m.minimal_test_errors(state, unfair)))

    def test_8_a_failed_method_cannot_hide_behind_a_rewrite(self):
        """Scenario 8: failure needs a taxonomy, and the frozen pre-registration stays frozen."""
        state, _ = base_state()
        self.assertIn("I2M54", i2m._rules(i2m.test_failure_errors(
            state, {"preregistration_digest": "sha256:pre"}, frozen_digest="sha256:pre")))
        self.assertIn("I2M55", i2m._rules(i2m.test_failure_errors(
            state, {"classification": i2m.FAILURE_INEFFECTIVE,
                    "preregistration_digest": "sha256:edited"}, frozen_digest="sha256:pre")))
        outcomes = {
            i2m.FAILURE_IMPLEMENTATION: i2m.DECISION_REPAIR_IMPLEMENTATION,
            i2m.FAILURE_INEFFECTIVE: i2m.DECISION_REDESIGN,
            i2m.FAILURE_MECHANISM_WEAKENED: i2m.DECISION_RESYNTHESIZE,
            i2m.FAILURE_INCONCLUSIVE: i2m.DECISION_DISCRIMINATE}
        for classification, expected in outcomes.items():
            decision = i2m.advance(state, outcome={"status": "failed",
                                                   "classification": classification})
            self.assertEqual(decision["decision"], expected, classification)

    def test_8b_rewriting_the_explanation_does_not_reset_the_diagnosis_budget(self):
        """The streak is read from executed eig records, not from prose."""
        state, scheduler = base_state(stagnant=True)
        import prediction_compare as pc
        before = pc.trailing_zero_streak(scheduler)
        rewritten = copy.deepcopy(state)
        rewritten["narrative_view"] = {"summary": "重写过的解释" * 20}
        after = pc.trailing_zero_streak(scheduler)
        self.assertEqual(before, after)
        self.assertGreaterEqual(after, 2)
        step = loop_step(rewritten, scheduler)
        self.assertEqual(step["step"], "Synthesize", step)


# ---------------------------------------------------------------------------
# 9—12: anchors, recovery, historical compatibility, scheduler change
# ---------------------------------------------------------------------------

class TestAnchorsAndRuntime(unittest.TestCase):
    def test_9_different_anchors_select_different_paths(self):
        """Scenario 9: method anchors synthesize; others keep their own contribution."""
        for anchor in i2m.METHOD_ANCHORS:
            with self.subTest(anchor=anchor):
                state, _ = base_state(anchor=anchor)
                path = i2m.anchor_path(state, readiness=i2m.insight_readiness(state, insight()))
                self.assertEqual(path["path"], "METHOD_SYNTHESIS")
        for anchor in i2m.NON_METHOD_ANCHORS:
            with self.subTest(anchor=anchor):
                state, _ = base_state(anchor=anchor)
                path = i2m.anchor_path(state, readiness=i2m.insight_readiness(state, insight()))
                self.assertEqual(path["path"], "ANCHOR_NATIVE")
                self.assertTrue(path["contribution"])

    def test_9b_a_non_method_anchor_is_not_forced_into_an_algorithm(self):
        for anchor in ("theory", "phenomenon", "benchmark", "feasibility", "negative"):
            with self.subTest(anchor=anchor):
                state, scheduler = base_state(anchor=anchor, stagnant=True)
                step = loop_step(state, scheduler)
                self.assertEqual(step["stage"], "anchor_native", step)
                self.assertIn("不把非方法锚点强行转成算法", step["action"])

    def test_9c_anchor_eligibility_is_evidence_decided(self):
        state, _ = base_state()
        verdict = i2m.anchor_eligibility(state)
        self.assertIn(verdict["verdict"], i2m.ANCHOR_ELIGIBILITY)
        self.assertEqual(verdict["target_anchor"], "performance")
        empty = copy.deepcopy(state)
        empty["evidence"] = []
        self.assertEqual(i2m.anchor_eligibility(empty)["verdict"], i2m.NOT_ELIGIBLE)

    def test_9d_an_unsatisfied_anchor_does_not_block_method_work(self):
        state, scheduler = base_state(stagnant=True)
        gap = {"satisfied": ["基线已建立"], "missing_evidence": ["同算力对比"],
               "refuted_requirements": ["旧假设被否"], "feasible_interventions": ["重加权"],
               "next_discriminating_test": "小规模对照",
               "exit_conditions": ["同算力下无提升则停止"]}
        view = i2m.anchor_gap(state, gap)
        self.assertTrue(view["unsatisfied"])
        self.assertFalse(view["blocks_method_work"])
        self.assertIn("不阻止方法探索", view["note"])
        step = i2m.loop_step(state, scheduler, gap=gap)
        self.assertEqual(step["step"], "Synthesize", step)

    def test_9e_supporting_contribution_must_be_falsifiable(self):
        self.assertIn("I2M57", i2m._rules(i2m.anchor_role_errors({"anchor_role": "supporting"})))
        self.assertIn("I2M59", i2m._rules(i2m.anchor_role_errors(
            {"anchor_role": "supporting", "serves": "性能锚点",
             "serves_evidence": "T003/K1"})))
        self.assertFalse(i2m.anchor_role_errors(
            {"anchor_role": "supporting", "serves": "性能锚点", "serves_evidence": "T003/K1",
             "downstream_decision": "是否继续重加权路线", "measurable_impact": "recall@10"}))

    def test_9f_orthogonal_contribution_keeps_its_own_value(self):
        self.assertFalse(i2m.anchor_role_errors({"anchor_role": "orthogonal"}))
        self.assertIn("orthogonal", " ".join(i2m.ANCHOR_ROLES))

    def test_9g_an_unauthorised_anchor_change_is_refused(self):
        """Only the user may change the primary anchor (SKILL.md §0.2)."""
        self.assertIn("I2M61", i2m._rules(i2m.anchor_change_errors(
            {"new_anchor": "theory", "reason": "证据不足", "evidence": "E1"})))
        self.assertIn("I2M62", i2m._rules(i2m.anchor_change_errors(
            {"new_anchor": "theory", "user_authorized": True})))
        self.assertFalse(i2m.anchor_change_errors(
            {"new_anchor": "theory", "user_authorized": True,
             "reason": "机制不可达", "evidence": "E1,E2"}))

    def test_10_loop_restart_and_recovery_are_stable(self):
        """Scenario 10: the same state yields the same step; a fresh process too."""
        state, scheduler = base_state(stagnant=True)
        first = loop_step(copy.deepcopy(state), copy.deepcopy(scheduler))
        second = loop_step(copy.deepcopy(state), copy.deepcopy(scheduler))
        self.assertEqual(first["step"], second["step"])
        self.assertEqual(first["trigger"], second["trigger"])
        self.assertEqual(json.dumps(first["i2m"], sort_keys=True),
                         json.dumps(second["i2m"], sort_keys=True))

    def test_10b_rsi_promotion_gates_are_untouched_by_i2m(self):
        """Scenario 10: I2M cannot promote a policy or grant a level."""
        self.assertFalse(hasattr(i2m, "promote"))
        for name in ("promote_to_active", "record_research_validation", "approve_l3"):
            self.assertTrue(callable(getattr(pe, name)))

    def test_10c_synthesis_and_narrative_are_not_l3_evidence(self):
        """R8/RSI boundary: generating candidates is never research-improvement evidence."""
        source = pathlib.Path(__file__).with_name("policy_evolution.py").read_text(
            encoding="utf-8")
        self.assertIn("PE17", source)
        self.assertIn("candidate_generation", source)

    def test_11_legal_old_states_and_artifacts_stay_readable(self):
        """Scenario 11: no new required field, no new state object."""
        state = copy.deepcopy(fixture.valid_state())
        report = state_check.check_state(state, "<old>")
        self.assertFalse(list(getattr(report, "errors", [])),
                         list(getattr(report, "errors", []))[:3])
        snapshot = i2m.signal_snapshot(state, {"state_version": state.get("state_version"),
                                               "next_actions": [], "eig_calibration":
                                               {"records": []}})
        self.assertIn(snapshot["readiness"], i2m.READINESS_VERDICTS)
        self.assertNotIn("contract", state.get("_extra", {}))

    def test_11b_a_state_with_the_method_block_still_validates(self):
        """The method block lives on existing objects, so the shape gate must accept it."""
        state = copy.deepcopy(fixture.valid_state())
        state["hypotheses"][0]["method"] = {"intervention": {"kind": "objective"},
                                            "mathematical_formulation": "L"}
        state["experiments"].append({
            "id": "X900", "status": "planned",
            "preregistration": {"frozen_at_state_version": state.get("state_version", 1),
                                "outcomes": [],
                                "method_contract": contract(state)}})
        report = state_check.check_state(state, "<with-method>")
        self.assertFalse(list(getattr(report, "errors", [])),
                         list(getattr(report, "errors", []))[:3])
        self.assertEqual(i2m._method_contract_in_state(state)["nearest_prior"], "focal loss")

    def test_12_new_method_evidence_changes_the_next_action(self):
        """Scenario 12: with a frozen contract the Loop continues method development."""
        state, scheduler = base_state(stagnant=True)
        state["experiments"].append({
            "id": "X901", "status": "planned",
            "preregistration": {"frozen_at_state_version": state.get("state_version", 1),
                                "outcomes": [], "method_contract": contract(state)}})
        # the registered minimal test is actionable work, so the Loop routes it through the
        # existing PEIG/AALG execution branch - method progress, not another diagnosis
        step = loop_step(state, scheduler)
        self.assertEqual(step["phase"], "R8/R9", step)
        self.assertIn("PEIG/AALG", step["action"])
        pure = i2m.loop_step(state, scheduler)
        self.assertEqual(pure["trigger"], "method_contract_present")

    def test_12b_the_i2m_step_never_skips_a_hard_gate(self):
        """An Assurance failure must still outrank method synthesis."""
        state, scheduler = base_state(stagnant=True)
        state["experiments"] = [{"id": "X902", "status": "done", "preregistration": None,
                                 "result_at_state_version": state.get("state_version"),
                                 "outcome_analysis": None, "claim_targeted": [],
                                 "alternative_targeted": []}]
        step = loop_step(state, scheduler)
        self.assertNotEqual(step.get("stage"), "synthesis")
        self.assertFalse(step.get("i2m"))

    def test_12c_progress_requires_both_a_change_and_evidence(self):
        state, _ = base_state()
        before = dict(state["hypotheses"][0], method={"intervention": "objective-A"})
        after = dict(state["hypotheses"][0], method={"intervention": "objective-B"})
        grown = copy.deepcopy(state)
        grown["evidence"] = [*grown["evidence"],
                             {"id": "E901", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}}]
        progress = i2m.method_progress(grown, before=before, after=after,
                                       previous_evidence=[e["id"] for e in state["evidence"]])
        self.assertTrue(progress["progress"])
        self.assertEqual(progress["executed_evidence"], ["E901"])


# ---------------------------------------------------------------------------
# End-to-end：Problem/Insight → 候选 → 冻结契约 → 最小实验计划 → 回写 → 下一决策
# ---------------------------------------------------------------------------

class TestEndToEnd(unittest.TestCase):
    def test_the_whole_transition_runs_end_to_end(self):
        state, scheduler = base_state(stagnant=True)
        # 1. Problem + Insight
        readiness = i2m.insight_readiness(state, insight())
        self.assertEqual(readiness["verdict"], i2m.VERDICT_HYPOTHESIS)
        self.assertTrue(readiness["criteria"][i2m.CRITERION_PROBLEM])
        # 2. Method synthesis: two distinct candidates
        synthesis = i2m.synthesize_methods(
            state, readiness, [candidate("M1", "objective", "alpha", "L1"),
                               candidate("M2", "architecture", "beta", "L2")])
        self.assertEqual(synthesis["status"], "SYNTHESIZED", synthesis["diagnostics"])
        self.assertEqual(len(synthesis["candidates"]), 2)
        # 3. Frozen design contract bound to the existing rule digest
        chosen = synthesis["candidates"][0]
        frozen = i2m.contract_from_candidate(chosen, insight=insight(),
                                             rules_digest="sha256:rules")
        frozen.update({"nearest_prior": "focal loss", "distinctive_mechanism": "样本层级",
                       "falsifiers": ["不升"], "minimal_test": {"plan": "小规模"},
                       "comparators": ["no_intervention", "focal loss"],
                       "success_criteria": ["+2pt"], "stop_rules": ["无提升停止"],
                       "problem_ref": "contract", "insight_refs": ["H42"]})
        self.assertFalse(i2m.design_contract_errors(state, frozen),
                         i2m.design_contract_errors(state, frozen))
        plan = dict(MINIMAL_PLAN, preregistration_digest="sha256:pre")
        self.assertFalse(i2m.minimal_test_errors(state, plan))
        # 4. Result write-back and the next decision
        state_with_evidence = copy.deepcopy(state)
        state_with_evidence["evidence"] = [*state_with_evidence["evidence"],
                                           {"id": "E910", "epistemic_status": "Observed",
                                            "validity": {"status": "valid"}}]
        state_with_evidence["hypotheses"][0]["method"] = chosen["intervention"]
        progress = i2m.method_progress(state_with_evidence,
                                       before={"method": {"intervention": {"kind": "none"}}},
                                       after=state_with_evidence["hypotheses"][0],
                                       previous_evidence=[e["id"] for e in state["evidence"]])
        self.assertTrue(progress["progress"])
        decision = i2m.advance(state_with_evidence, readiness=readiness, contract=frozen)
        self.assertEqual(decision["decision"], i2m.DECISION_CONTINUE)

    def test_the_runtime_step_matches_the_pure_transition(self):
        state, scheduler = base_state(stagnant=True)
        runtime = loop_step(state, scheduler)
        pure = i2m.transition(state, scheduler=scheduler,
                              insight=i2m.insight_from_state(state))
        self.assertEqual(runtime["step"], pure["step"])
        self.assertEqual(runtime["i2m"]["readiness"]["verdict"],
                         pure["i2m"]["readiness"]["verdict"])


if __name__ == "__main__":
    unittest.main()
