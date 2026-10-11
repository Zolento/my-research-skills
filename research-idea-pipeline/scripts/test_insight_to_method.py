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
    state["assurance"] = [{"id": "AS-OK", "status": "PASS", "experiment": "X900"}]
    for hypothesis in state.get("hypotheses", []):
        hypothesis.update({"intervention_axis": "loss_reweighting",
                           "nearest_prior": "focal loss",
                           "novelty_source": "样本层级重加权"})
    primary = next((str(h.get("id")) for h in state.get("hypotheses", [])), "")
    for uncertainty in state.get("uncertainties", []):
        uncertainty["cheapest_discriminating_test"] = "小规模长尾子集对照"
        uncertainty["depends_on"] = [primary]        # readiness requires a bound chain
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


def with_execution(state):
    """Progress tests need evidence that resolves to executed experiments (kept out of the
    shared loop fixture, where a terminal experiment would trigger R9.O instead)."""
    state = copy.deepcopy(state)
    state["experiments"] = [
        {"id": f"X{n}", "status": "executed", "metric": "recall@10",
         "claim_targeted": ["C1"], "result_at_state_version": state.get("state_version"),
         "preregistration": {"frozen_at_state_version": 1, "method_contract": {
             "method_digest": "d1", "version": 1, "method_hypothesis_ref": "H42"}}}
        for n in (900, 901, 910, 951, 952, 953)]
    return state


def progress_fixture(**kwargs):
    state, scheduler = base_state(**kwargs)
    return with_execution(state), scheduler


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
        self.assertIn(step.get("trigger", ""), ("readiness_actionable(MECHANISM_HYPOTHESIS)",
                                                "diagnosis_stagnant(zero_streak=2, switch=REDESIGN_QUESTION)"))
        self.assertIn(step["action_state"],
                      ("proposed", "admissible", "advisory", "authorized_in_queue"))

    def test_1b_a_ready_insight_enters_the_legal_candidate_set_without_stagnation(self):
        """Requirement 1: contribution development no longer waits for diagnosis to stall."""
        state, scheduler = base_state(stagnant=False)
        step = loop_step(state, scheduler)
        self.assertEqual(step["phase"], "I2M", step)
        self.assertIn("readiness_actionable", step["trigger"])
        self.assertIn(step["action_state"], ("proposed", "admissible", "advisory"))
        self.assertFalse(step["dispatched"])

    def test_1c_a_loop_without_a_ready_insight_is_still_not_hijacked(self):
        state, scheduler = base_state(stagnant=False)
        state["hypotheses"] = []                                    # nothing to build from
        step = loop_step(state, scheduler)
        self.assertIn(step["phase"], ("R3—R6", "R3—R6/R8"), step)
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
        state, _ = progress_fixture()
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
        state, _ = progress_fixture()
        broken = contract(state, intervention={"kind": "hyperparameter"})
        self.assertIn("I2M29", i2m._rules(i2m.design_contract_errors(state, broken)))

    def test_5c_an_unverifiable_novelty_claim_cannot_be_asserted(self):
        state, _ = progress_fixture(greed=True)
        broken = contract(state, evidence_status="supported")
        self.assertIn("I2M39", i2m._rules(i2m.design_contract_errors(state, broken)))

    def test_6_no_code_change_or_trustworthy_result_means_no_contribution(self):
        """Scenario 6: explanation rewrites and self-scores are not method progress."""
        state, _ = progress_fixture()
        before = dict(state["hypotheses"][0],
                      method={"intervention": "a", "definition_digest": "d1"})
        after = dict(state["hypotheses"][0],
                     method={"intervention": "b", "definition_digest": "d1"})
        progress = i2m.method_progress(state, before=before, after=after,
                                       previous_evidence=[e["id"] for e in state["evidence"]])
        self.assertFalse(progress["dimensions"]["design"])
        self.assertFalse(progress["dimensions"]["implementation"])
        self.assertFalse(progress["dimensions"]["validation"])
        self.assertIn("narrative_view", progress["excluded_signals"])
        grown = copy.deepcopy(state)
        grown["evidence"] = [*grown["evidence"],
                             {"id": "E900", "kind": "experiment_result",
                              "epistemic_status": "Observed", "validity": {"status": "valid"},
                              "supports": ["H42"], "source_ref": "exp:X900",
                              "verification_tier": "T2"}]
        self.assertTrue(i2m.method_progress(
            grown, before=before, after=after,
            previous_evidence=[e["id"] for e in state["evidence"]])["progress"])

    def test_6b_a_contract_alone_does_not_complete_a_method(self):
        state, _ = progress_fixture()
        decision = i2m.advance(state, readiness=i2m.insight_readiness(state, insight()),
                               contract=contract(state))
        self.assertEqual(decision["decision"], i2m.DECISION_CONTINUE)
        self.assertIn("设计→实现→有效性", decision["reason"])

    def test_7_no_execution_eligibility_means_no_gpu(self):
        """Scenario 7: the pre-execution gates keep their authority over I2M."""
        state, _ = progress_fixture()
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
        state, _ = progress_fixture()
        unfair = dict(MINIMAL_PLAN, fairness={"capacity": True})
        self.assertIn("I2M49", i2m._rules(i2m.minimal_test_errors(state, unfair)))

    def test_8_a_failed_method_cannot_hide_behind_a_rewrite(self):
        """Scenario 8: failure needs a taxonomy, and the frozen pre-registration stays frozen."""
        state, _ = progress_fixture()
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
        state, scheduler = progress_fixture(stagnant=True)
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
                state, _ = progress_fixture(anchor=anchor)
                path = i2m.anchor_path(state, readiness=i2m.insight_readiness(state, insight()))
                self.assertEqual(path["path"], "METHOD_SYNTHESIS")
        for anchor in i2m.NON_METHOD_ANCHORS:
            with self.subTest(anchor=anchor):
                state, _ = progress_fixture(anchor=anchor)
                path = i2m.anchor_path(state, readiness=i2m.insight_readiness(state, insight()))
                self.assertEqual(path["path"], "ANCHOR_NATIVE")
                self.assertTrue(path["contribution"])

    def test_9b_a_non_method_anchor_is_not_forced_into_an_algorithm(self):
        for anchor in ("theory", "phenomenon", "benchmark", "feasibility", "negative"):
            with self.subTest(anchor=anchor):
                state, scheduler = progress_fixture(anchor=anchor, stagnant=True)
                step = loop_step(state, scheduler)
                self.assertEqual(step["stage"], "anchor_native", step)
                self.assertIn("不把非方法锚点强行转成算法", step["action"])

    def test_9c_anchor_eligibility_is_evidence_decided(self):
        state, _ = progress_fixture()
        verdict = i2m.anchor_eligibility(state)
        self.assertIn(verdict["verdict"], i2m.ANCHOR_ELIGIBILITY)
        self.assertEqual(verdict["target_anchor"], "performance")
        empty = copy.deepcopy(state)
        empty["evidence"] = []
        self.assertEqual(i2m.anchor_eligibility(empty)["verdict"], i2m.NOT_ELIGIBLE)

    def test_9d_an_unsatisfied_anchor_does_not_block_method_work(self):
        state, scheduler = progress_fixture(stagnant=True)
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
        state, scheduler = progress_fixture(stagnant=True)
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
        state, scheduler = progress_fixture(stagnant=True)
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
        state, scheduler = progress_fixture(stagnant=True)
        state["experiments"] = [{"id": "X902", "status": "done", "preregistration": None,
                                 "result_at_state_version": state.get("state_version"),
                                 "outcome_analysis": None, "claim_targeted": [],
                                 "alternative_targeted": []}]
        step = loop_step(state, scheduler)
        self.assertNotEqual(step.get("stage"), "synthesis")
        self.assertFalse(step.get("i2m"))

    def test_12c_progress_requires_both_a_change_and_evidence(self):
        state, _ = progress_fixture()
        before = dict(state["hypotheses"][0],
                      method={"intervention": "objective-A", "definition_digest": "d1"})
        after = dict(state["hypotheses"][0],
                     method={"intervention": "objective-B", "definition_digest": "d1"})
        grown = copy.deepcopy(state)
        grown["evidence"] = [*grown["evidence"],
                             {"id": "E901", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "supports": ["H42"],
                              "source_ref": "exp:X901", "verification_tier": "T2"}]
        progress = i2m.method_progress(grown, before=before, after=after,
                                       previous_evidence=[e["id"] for e in state["evidence"]])
        self.assertTrue(progress["progress"])
        self.assertEqual(progress["related_evidence"], ["E901"])
        self.assertEqual(progress["unattributed_evidence"], [])
        self.assertTrue(progress["dimensions"]["validation"])
        self.assertEqual(progress["unrelated_evidence"], [])


# ---------------------------------------------------------------------------
# End-to-end：Problem/Insight → 候选 → 冻结契约 → 最小实验计划 → 回写 → 下一决策
# ---------------------------------------------------------------------------

class TestEndToEnd(unittest.TestCase):
    def test_the_whole_transition_runs_end_to_end(self):
        state, scheduler = progress_fixture(stagnant=True)
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
        frozen["method_digest"] = "sha256:method-v1"
        frozen.update({"nearest_prior": "focal loss", "distinctive_mechanism": "样本层级",
                       "falsifiers": ["不升"], "minimal_test": {"plan": "小规模"},
                       "comparators": ["no_intervention", "focal loss"],
                       "success_criteria": ["+2pt"], "stop_rules": ["无提升停止"],
                       "problem_ref": "contract", "insight_refs": ["H42"]})
        problems = i2m.design_contract_errors(state, frozen)
        self.assertFalse(problems, [p.message for p in problems])
        plan = dict(MINIMAL_PLAN, preregistration_digest="sha256:pre")
        self.assertFalse(i2m.minimal_test_errors(state, plan))
        # 4. Result write-back and the next decision
        state_with_evidence = copy.deepcopy(state)
        state_with_evidence["evidence"] = [*state_with_evidence["evidence"],
                                           {"id": "E910", "epistemic_status": "Observed",
                                            "validity": {"status": "valid"},
                                            "supports": ["H42"], "source_ref": "exp:X910",
                                            "verification_tier": "T2"}]
        state_with_evidence["hypotheses"][0]["method"] = {
            "intervention": chosen["intervention"], "definition_digest": "d1"}
        progress = i2m.method_progress(
            state_with_evidence,
            before={"id": "H42", "method": {"intervention": {"kind": "none"},
                                            "definition_digest": "d1"}},
            after=state_with_evidence["hypotheses"][0],
            previous_evidence=[e["id"] for e in state["evidence"]],
            method_version="d1")
        self.assertTrue(progress["progress"])
        decision = i2m.advance(state_with_evidence, readiness=readiness, contract=frozen)
        self.assertEqual(decision["decision"], i2m.DECISION_CONTINUE)

    def test_the_runtime_step_matches_the_pure_transition(self):
        state, scheduler = progress_fixture(stagnant=True)
        runtime = loop_step(state, scheduler)
        pure = i2m.transition(state, scheduler=scheduler,
                              insight=i2m.insight_from_state(state))
        self.assertEqual(runtime["step"], pure["step"])
        self.assertEqual(runtime["i2m"]["readiness"]["verdict"],
                         pure["i2m"]["readiness"]["verdict"])


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# 第十三轮：决策完整性（P1×5 + P2）
# ---------------------------------------------------------------------------

class TestDecisionIntegrity(unittest.TestCase):
    # --- P1-1 调度冲突 -------------------------------------------------------
    def test_a_ready_insight_can_be_chosen_without_waiting_for_stagnation(self):
        state, scheduler = progress_fixture(stagnant=False)
        step = loop_step(state, scheduler)
        self.assertEqual(step["phase"], "I2M", step)
        self.assertIn("readiness_actionable", step["trigger"])
        self.assertIn(step["action_state"], ("proposed", "admissible", "advisory"))

    def test_an_unbound_method_action_of_the_same_type_does_not_authorize(self):
        """P1-A: the action *type* alone must never authorize this candidate."""
        state, scheduler = progress_fixture(stagnant=False)
        scheduler["next_actions"].append({"action": "M-OTHER", "type": "method_synthesis",
                                          "target": "other", "eig": "medium", "cost": "medium"})
        step = loop_step(state, scheduler)
        self.assertNotEqual(step["action_state"], "authorized_in_queue")
        candidate = i2m.candidate_method_action(state, scheduler)
        self.assertIn("I2M90", i2m._rules([type("D", (), {"rule": item["rule"]})()
                                           for item in candidate["authorization_errors"]])
                      or {item["rule"] for item in candidate["authorization_errors"]})

    def test_a_registered_candidate_is_authorized_through_its_own_entry(self):
        """There must be a legal first entry for a brand-new method."""
        state, scheduler = progress_fixture(stagnant=False)
        frozen = contract(state, method_digest="sha256:m1", version=2)
        registration = i2m.register_method_candidate(state, frozen)
        self.assertEqual(registration["status"], "ADMISSIBLE", registration["diagnostics"])
        self.assertEqual(registration["entry"]["method_candidate"], "H42")
        self.assertEqual(registration["entry"]["method_digest"], "sha256:m1")
        # write it into the queue the way the agent would, then it authorizes *this* candidate
        state["experiments"] = [{"id": "X1", "status": "planned",
                                 "preregistration": {"frozen_at_state_version": 1,
                                                     "method_contract": frozen}}]
        before = i2m.candidate_method_action(state, scheduler, contract=frozen)
        self.assertNotEqual(before["state"], "authorized_in_queue")
        scheduler["next_actions"].append(registration["entry"])
        after = i2m.candidate_method_action(state, scheduler, contract=frozen)
        self.assertEqual(after["state"], "authorized_in_queue")
        self.assertTrue(after["admitted"])
        other = copy.deepcopy(registration["entry"])
        other.update({"method_digest": "sha256:other", "action": "M2"})
        candidate = i2m.candidate_method_action(state, {"next_actions": [other]},
                                                contract=frozen)
        self.assertNotEqual(candidate["state"], "authorized_in_queue")

    def test_a_stale_state_version_does_not_reuse_the_authorization(self):
        state, scheduler = progress_fixture(stagnant=False)
        frozen = contract(state, method_digest="sha256:m1", version=2)
        entry = i2m.register_method_candidate(state, frozen)["entry"]
        entry["state_version"] = "999"
        state["experiments"] = [{"id": "X1", "status": "planned",
                                 "preregistration": {"frozen_at_state_version": 1,
                                                     "method_contract": frozen}}]
        candidate = i2m.candidate_method_action(state, {"next_actions": [entry]},
                                                contract=frozen)
        self.assertNotEqual(candidate["state"], "authorized_in_queue")
        self.assertIn("I2M92", {item["rule"] for item in candidate["authorization_errors"]})

    def test_i2m_cannot_bypass_the_execution_gate(self):
        """Requirement 13: PEIG/AALG/budget refusals are not overridable by I2M."""
        state, _ = progress_fixture()
        self.assertIn("I2M52", i2m._rules(i2m.minimal_test_errors(
            state, MINIMAL_PLAN, gate={"status": "HOLD", "errors": ["PEIG"]})))
        self.assertIn("I2M51", i2m._rules(i2m.minimal_test_errors(
            state, dict(MINIMAL_PLAN, gpu_required=True))))
        self.assertFalse(hasattr(i2m, "execute_experiment"))
        self.assertFalse(hasattr(i2m, "grant_gpu"))

    def test_a_valueless_planned_experiment_does_not_hold_the_queue(self):
        state, scheduler = progress_fixture(stagnant=True)
        claim_id = state["claims"][0]["id"]
        for claim in state["claims"]:
            claim["status"] = "refuted"
        state["experiments"] = [{"id": "X1", "status": "planned",
                                 "claim_targeted": [claim_id],
                                 "preregistration": {"frozen_at_state_version": 1}}]
        findings = i2m.planned_validity_errors(state, state["experiments"][0])
        self.assertIn("I2M80", i2m._rules(findings))
        step = loop_step(state, scheduler)
        self.assertEqual(step["phase"], "I2M", step)
        self.assertNotEqual(step.get("step"), "Intervene")

    def test_running_work_is_never_interrupted_to_switch_method(self):
        state, scheduler = progress_fixture(stagnant=True)
        state["experiments"] = [{"id": "X1", "status": "running",
                                 "claim_targeted": [], "preregistration": {}}]
        step = loop_step(state, scheduler)
        self.assertEqual(step["step"], "Intervene", step)

    def test_a_diagnosis_without_decision_value_cannot_preempt_method_work(self):
        state, scheduler = progress_fixture(stagnant=False)
        action = {"action": "X1", "type": "discriminating_experiment", "target": "U3",
                  "eig": "high", "cost": "low"}
        self.assertIn("I2M83", i2m._rules(i2m.diagnosis_decision_impact(state, action)))
        action["changes_decision"] = "whether to keep the reweighting route"
        self.assertFalse(i2m.diagnosis_decision_impact(state, action))

    # --- P1-2 虚假 Insight ---------------------------------------------------
    def test_splicing_fields_across_candidates_is_refused(self):
        state, _ = progress_fixture()
        state["hypotheses"].append({"id": "H99", "status": "active",
                                    "statement": "无关方向", "intervention_axis": "other",
                                    "falsifier": "f", "nearest_prior": "p",
                                    "novelty_source": "n"})
        spliced = {**insight(), "insight_refs": ["H42", "H99"]}
        readiness = i2m.insight_readiness(state, spliced)
        self.assertEqual(readiness["verdict"], i2m.VERDICT_NOT_ACTIONABLE)
        self.assertIn("I2M5", {item["rule"] for item in readiness["diagnostics"]})

    def test_an_unbound_prediction_is_refused(self):
        state, _ = progress_fixture()
        for uncertainty in state.get("uncertainties", []):
            uncertainty["depends_on"] = []
        derived = i2m.insight_from_state(state)          # predictions now come from nowhere
        self.assertTrue(derived["binding"]["related_uncertainties"] == [])
        readiness = i2m.insight_readiness(state, derived)
        self.assertEqual(readiness["verdict"], i2m.VERDICT_NOT_ACTIONABLE)
        self.assertIn(i2m.CRITERION_PREDICTIONS, readiness["missing"])

    def test_refuted_objects_cannot_pad_readiness(self):
        state, _ = progress_fixture()
        for hypothesis in state["hypotheses"]:
            hypothesis["status"] = "refuted"
        derived = i2m.insight_from_state(state)
        self.assertEqual(derived["insight_refs"], [])
        self.assertIn("未被否证", derived["binding_note"])

    def test_derivation_keeps_everything_on_one_candidate(self):
        state, _ = progress_fixture()
        state["hypotheses"].append({"id": "H98", "status": "active",
                                    "statement": "另一方向", "intervention_axis": "lever-98",
                                    "falsifier": "f", "nearest_prior": "p2",
                                    "novelty_source": "n2"})
        derived = i2m.insight_from_state(state)
        self.assertEqual(len(derived["insight_refs"]), 1)
        self.assertNotIn("lever-98", derived["intervention_levers"])
        self.assertEqual(derived["prior_art"][0]["hypothesis"], derived["insight_refs"][0])

    # --- P1-3 机制证据过度升级 -----------------------------------------------
    def test_dependency_is_not_support(self):
        state, _ = progress_fixture()
        state["evidence"] = [{"id": "E1", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "depends_on": ["H42"],
                              "source_ref": "exp:X1", "verification_tier": "T2"}]
        readiness = i2m.insight_readiness(state, insight())
        self.assertEqual(readiness["mechanism_status"], i2m.VERDICT_HYPOTHESIS)
        self.assertIn("I2M70", {item["rule"] for item in readiness["diagnostics"]})
        self.assertEqual(readiness["dependent_evidence"], ["E1"])
        self.assertEqual(readiness["evidence_backing"], [])

    def test_support_without_qualification_does_not_verify_the_mechanism(self):
        state, _ = progress_fixture()
        state["evidence"] = [{"id": "E1", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "supports": ["H42"]}]
        readiness = i2m.insight_readiness(state, insight())
        self.assertEqual(readiness["mechanism_status"], i2m.VERDICT_HYPOTHESIS)
        self.assertIn("I2M71", {item["rule"] for item in readiness["diagnostics"]})

    def test_only_explicit_mechanism_support_verifies_it(self):
        state, _ = progress_fixture()
        state["evidence"] = [{"id": "E1", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "supports": ["H42"],
                              "source_ref": "exp:X900", "verification_tier": "T3",
                              "mechanism_support": "mechanism", "assurance_ref": "AS-OK"}]
        readiness = i2m.insight_readiness(state, insight())
        self.assertEqual(readiness["mechanism_level"], i2m.SUPPORT_MECHANISM)
        self.assertEqual(readiness["mechanism_status"], i2m.VERDICT_VERIFIED)

    def test_observing_a_prediction_is_not_proving_the_mechanism(self):
        state, _ = progress_fixture()
        state["evidence"] = [{"id": "E1", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "supports": ["H42"],
                              "source_ref": "exp:X1", "verification_tier": "T2"}]
        readiness = i2m.insight_readiness(state, insight())
        self.assertEqual(readiness["mechanism_level"], i2m.SUPPORT_PREDICTION_OBSERVED)
        self.assertEqual(readiness["mechanism_status"], i2m.VERDICT_HYPOTHESIS)

    def test_refuting_evidence_is_recorded_as_refuting(self):
        state, _ = progress_fixture()
        state["evidence"] = [{"id": "E1", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "refutes": ["H42"],
                              "source_ref": "exp:X1", "verification_tier": "T2"}]
        readiness = i2m.insight_readiness(state, insight())
        self.assertEqual(readiness["refuting_evidence"], ["E1"])
        self.assertEqual(readiness["mechanism_status"], i2m.VERDICT_HYPOTHESIS)

    # --- P1-4 Anchor 虚假达标 -----------------------------------------------
    def test_an_unrelated_supported_claim_does_not_make_the_anchor_eligible(self):
        state, _ = progress_fixture()
        state["claims"] = [{"id": "C1", "status": "supported",
                            "statement": "与目标锚点无关的结论"}]
        verdict = i2m.anchor_eligibility(state)
        self.assertNotEqual(verdict["verdict"], i2m.ELIGIBLE)
        self.assertIn("C1", verdict["unbacked_claims"] + verdict["irrelevant_claims"])

    def test_an_anchor_bound_claim_is_eligible(self):
        state, _ = progress_fixture()
        state["claims"] = [{"id": "C1", "status": "supported", "anchor": "performance",
                            "target_metric": "recall@10", "supporting_evidence": ["E900"],
                            "statement": "同算力下召回提升"}]
        state["evidence"] = [*state["evidence"],
                             {"id": "E900", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "supports": ["C1"],
                              "source_ref": "exp:X900", "verification_tier": "T2"}]
        verdict = i2m.anchor_eligibility(state)
        self.assertEqual(verdict["verdict"], i2m.ELIGIBLE)
        self.assertEqual(verdict["anchor_satisfaction"], "undetermined")
        self.assertEqual(i2m.anchor_link(state, {"id": "CZ", "statement": "recall@10 顺带提到"},
                                         "performance"), "text_only")

    def test_a_supporting_route_cannot_satisfy_the_project_anchor(self):
        state, _ = progress_fixture()
        state["contract"]["anchor_role"] = "supporting"
        state["claims"] = [{"id": "C1", "status": "supported",
                            "statement": "recall@10 提升"}]
        verdict = i2m.anchor_eligibility(state)
        self.assertNotEqual(verdict["verdict"], i2m.ELIGIBLE)
        self.assertIn("辅助贡献", verdict["required_evidence"])

    def test_an_orthogonal_route_never_satisfies_the_anchor(self):
        state, _ = progress_fixture()
        state["contract"]["anchor_role"] = "orthogonal"
        self.assertEqual(i2m.anchor_eligibility(state)["verdict"], i2m.NOT_ELIGIBLE)

    def test_the_gap_lists_refuted_and_undecidable_conditions_with_references(self):
        state, _ = progress_fixture()
        gap = i2m.anchor_gap(state, {"satisfied": ["基线已建立"],
                                     "missing_evidence": ["同算力对比"],
                                     "refuted_requirements": ["旧损失假设"],
                                     "feasible_interventions": ["重加权"],
                                     "next_discriminating_test": "小规模对照",
                                     "exit_conditions": ["无提升则停止"]})
        self.assertEqual(gap["refuted_requirements"], ["旧损失假设"])
        self.assertTrue(gap["unsatisfied"])
        self.assertFalse(gap["blocks_method_work"])
        self.assertEqual(gap["eligibility"], i2m.anchor_eligibility(state)["verdict"])

    # --- P1-5 进展判定 -------------------------------------------------------
    def _progress(self, state, before, after, **kwargs):
        # the E95x records are this round's new evidence; everything else is the baseline
        previous = [e["id"] for e in state["evidence"]
                    if not str(e["id"]).startswith("E95")]
        return i2m.method_progress(state, before=before, after=after,
                                   previous_evidence=previous, **kwargs)

    def test_a_fingerprint_change_alone_is_not_validation(self):
        state, _ = progress_fixture()
        before = {"id": "H42", "method": {"intervention": {"kind": "A"},
                                          "definition_digest": "d1"}}
        after = {"id": "H42", "method": {"intervention": {"kind": "B"},
                                         "definition_digest": "d2"}}
        progress = self._progress(state, before, after)
        self.assertTrue(progress["dimensions"]["design"])       # a frozen new definition
        self.assertFalse(progress["dimensions"]["validation"])  # but not a verification
        self.assertEqual(progress["dimensions"]["anchor"], False)

    def test_unrelated_new_evidence_adds_no_progress(self):
        state, _ = progress_fixture()
        grown = copy.deepcopy(state)
        grown["evidence"] = [*grown["evidence"],
                             {"id": "E950", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "source_ref": "other"}]
        method = {"id": "H42", "method": {"intervention": {"kind": "A"},
                                          "definition_digest": "d1"}}
        progress = self._progress(grown, copy.deepcopy(method), copy.deepcopy(method))
        self.assertFalse(progress["progress"])
        self.assertFalse(any(progress["dimensions"].values()))
        self.assertEqual(progress["unattributed_evidence"], ["E950"])

    def test_same_version_independent_validation_counts(self):
        state, _ = progress_fixture()
        grown = copy.deepcopy(state)
        grown["evidence"] = [*grown["evidence"],
                             {"id": "E951", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "supports": ["H42"],
                              "source_ref": "exp:X951", "verification_tier": "T2"}]
        method = {"id": "H42", "method": {"intervention": {"kind": "A"},
                                          "definition_digest": "d1"}}
        progress = self._progress(grown, method, copy.deepcopy(method))
        self.assertFalse(progress["method_changed"])
        self.assertTrue(progress["dimensions"]["validation"])
        self.assertTrue(progress["progress"])

    def test_a_negative_result_is_real_epistemic_progress(self):
        state, _ = progress_fixture()
        grown = copy.deepcopy(state)
        grown["evidence"] = [*grown["evidence"],
                             {"id": "E952", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "refutes": ["H42"],
                              "source_ref": "exp:X952", "verification_tier": "T2"}]
        method = {"id": "H42", "method": {"intervention": {"kind": "A"},
                                          "definition_digest": "d1"}}
        progress = self._progress(grown, method, copy.deepcopy(method))
        self.assertTrue(progress["dimensions"]["epistemic"])
        self.assertTrue(progress["progress"])

    def test_implementation_progress_needs_a_passing_artifact_check(self):
        state, _ = progress_fixture()
        method = {"id": "H42", "method": {"intervention": {"kind": "A"},
                                          "definition_digest": "d1"}}
        ok = self._progress(state, method, copy.deepcopy(method),
                            implementation_check={"status": "PASS",
                                                  "artifact_digest": "sha256:a"})
        bad = self._progress(state, method, copy.deepcopy(method),
                             implementation_check={"status": "FAIL",
                                                   "artifact_digest": "sha256:a"})
        self.assertTrue(ok["dimensions"]["implementation"])
        self.assertFalse(bad["dimensions"]["implementation"])

    def test_anchor_progress_requires_anchor_relevant_evidence(self):
        state, _ = progress_fixture()
        grown = copy.deepcopy(state)
        grown["evidence"] = [*grown["evidence"],
                             {"id": "E953", "epistemic_status": "Observed",
                              "validity": {"status": "valid"},
                              "target_metric": "recall@10",
                              "statement": "在目标数据上提升",
                              "source_ref": "exp:X953", "verification_tier": "T2"}]
        method = {"id": "H42", "method": {"intervention": {"kind": "A"},
                                          "definition_digest": "d1"}}
        progress = self._progress(grown, method, copy.deepcopy(method))
        self.assertTrue(progress["dimensions"]["anchor"])

    # --- P2 契约选择与版本归属 ----------------------------------------------
    def _two_contracts(self):
        state, _ = progress_fixture()
        old = {"method_digest": "d0", "method_hypothesis_ref": "H42",
               "method_hypothesis_ref_note": "old"}
        new = {"method_digest": "d1", "method_hypothesis_ref": "H42"}
        state["experiments"] = [
            {"id": "X1", "status": "abandoned", "preregistration": {"method_contract": old}},
            {"id": "X2", "status": "planned", "preregistration": {"method_contract": new}}]
        return state, old, new

    def test_the_first_contract_encountered_is_not_selected(self):
        state, old, new = self._two_contracts()
        self.assertEqual(i2m._method_contract_in_state(state)["method_digest"], "d1")

    def test_an_abandoned_contract_is_reported_as_rejected(self):
        state, _, _ = self._two_contracts()
        selection = i2m.select_method_contract(state)
        self.assertEqual(selection["selected"]["experiment_id"], "X2")
        self.assertTrue(any(item["experiment_id"] == "X1" for item in selection["rejected"]))

    def test_explicit_experiment_selection_wins(self):
        state, old, _ = self._two_contracts()
        state["experiments"][0]["status"] = "done"
        selection = i2m.select_method_contract(state, experiment_id="X1")
        self.assertEqual(selection["contract"]["method_digest"], "d0")

    def test_a_contract_must_bind_a_method_version(self):
        state, _ = progress_fixture()
        broken = contract(state, method_digest="", rules_digest="")
        self.assertIn("I2M74", i2m._rules(i2m.contract_version_errors(state, broken)))
        self.assertIn("I2M74", i2m._rules(i2m.contract_version_errors(state, {})))

    def test_confirmatory_results_cannot_be_claimed_after_the_fact(self):
        state, _ = progress_fixture()
        late = contract(state, method_digest="d1", confirmatory=True,
                        registered_after_result=True)
        self.assertIn("I2M78", i2m._rules(i2m.contract_version_errors(state, late)))

    def test_string_references_are_not_split_into_characters(self):
        state, _ = progress_fixture()
        broken = contract(state, insight_refs="H42")
        self.assertIn("I2M72", i2m._rules(i2m.design_contract_errors(state, broken)))
        readiness = i2m.insight_readiness(state, {**insight(), "insight_refs": "H42"})
        self.assertIn("I2M60", {item["rule"] for item in readiness["diagnostics"]})
        self.assertEqual(readiness["verdict"], i2m.VERDICT_NOT_ACTIONABLE)

    def test_an_old_contract_without_a_version_is_readable_but_not_confirmatory(self):
        state, _ = progress_fixture()
        legacy = {"problem_ref": "contract", "insight_refs": ["H42"],
                  "method_hypothesis_ref": "H42", "intervention": {"kind": "objective"},
                  "mathematical_formulation": "L", "algorithm_steps": ["a"],
                  "nearest_prior": "focal loss", "distinctive_mechanism": "d",
                  "predictions": [{"observation": "o"}], "falsifiers": ["f"],
                  "minimal_test": {"plan": "p"}, "comparators": ["no_intervention", "focal loss"],
                  "success_criteria": ["+2pt"], "stop_rules": ["stop"],
                  "evidence_status": "supported", "rules_digest": "r"}
        problems = i2m.design_contract_errors(state, legacy)
        self.assertIn("I2M39", i2m._rules(problems))     # no version, no support claim


class TestProvenanceConsistency(unittest.TestCase):
    """第十四轮：归属与一致性（P1×3 + P2×2 + 机制审查）。"""

    # --- P1-B anchor: explicit relations, not text --------------------------
    def test_a_text_mention_is_not_an_anchor_relation(self):
        state, _ = progress_fixture()
        mention = {"id": "C-MENTION", "status": "supported",
                   "supporting_evidence": ["E-MENTION"],
                   "statement": "recall@10 顺带被提到"}
        state["evidence"] = [*state["evidence"],
                             {"id": "E-MENTION", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "supports": ["C-MENTION"],
                              "source_ref": "exp:X902", "verification_tier": "T2"}]
        self.assertEqual(i2m.anchor_link(state, mention, "performance"), "text_only")
        state["claims"] = [mention]
        verdict = i2m.anchor_eligibility(state)
        self.assertNotEqual(verdict["verdict"], i2m.ELIGIBLE)
        self.assertEqual(verdict["text_only_claims"], ["C-MENTION"])

    def test_an_experiment_targeting_the_metric_is_an_explicit_link(self):
        state, _ = progress_fixture()
        state["claims"] = [{"id": "C1", "status": "supported", "statement": "更好",
                            "supporting_evidence": ["E901"]}]
        state["evidence"] = [*state["evidence"],
                             {"id": "E901", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "supports": ["C1"],
                              "source_ref": "exp:X901", "verification_tier": "T2"}]
        state["experiments"] = [*state["experiments"],
                                {"id": "X901b", "status": "done", "metric": "recall@10",
                                 "claim_targeted": ["C1"]}]
        self.assertEqual(i2m.anchor_link(state, state["claims"][0], "performance"),
                         "experiment_targeted")
        self.assertEqual(i2m.anchor_eligibility(state)["verdict"], i2m.ELIGIBLE)

    def test_the_five_notions_are_reported_separately(self):
        state, _ = progress_fixture()
        state["contract"]["anchor_requirements"] = ["同算力下 recall@10 提升"]
        verdict = i2m.anchor_eligibility(state)
        for key in ("project_objective", "research_progress", "defensible_contribution",
                    "anchor_satisfaction"):
            self.assertIn(key, verdict)
        self.assertEqual(verdict["anchor_satisfaction"], "unsatisfied")

    def test_a_missing_frozen_requirement_leaves_the_gap_undetermined(self):
        state, _ = progress_fixture()
        gap = i2m.anchor_gap(state)
        self.assertEqual(gap["satisfaction"], "undetermined")
        self.assertTrue(gap["undetermined"])
        self.assertTrue(gap["unsatisfied"] is False or gap["missing_evidence"] == [])

    def test_missing_evidence_is_not_refutation(self):
        state, _ = progress_fixture()
        state["contract"]["anchor_requirements"] = ["同算力对比"]
        gap = i2m.anchor_gap(state)
        self.assertEqual(gap["satisfaction"], "unsatisfied")
        self.assertEqual(gap["refuted_requirements"], [])
        self.assertFalse(gap["blocks_method_work"])
        self.assertIn("不等于目标已被证伪", gap["note"])

    def test_a_supporting_route_cannot_satisfy_the_frozen_anchor(self):
        state, _ = progress_fixture()
        state["contract"]["anchor_requirements"] = ["同算力对比"]
        state["claims"] = [{"id": "C1", "status": "supported", "anchor": "performance"}]
        state["contract"]["anchor_role"] = "supporting"
        self.assertNotEqual(i2m.anchor_eligibility(state)["verdict"], i2m.ELIGIBLE)

    # --- P1-C progress attribution -----------------------------------------
    def _method(self, version="v1"):
        return {"id": "H42", "method": {"version": version, "definition_digest": "d1"}}

    def test_evidence_from_another_method_version_is_not_attributed(self):
        state, _ = progress_fixture()
        state["evidence"] = [*state["evidence"],
                             {"id": "E1", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "supports": ["H42"],
                              "source_ref": "exp:X1", "verification_tier": "T2",
                              "method_version": "d2"}]
        progress = i2m.method_progress(state, before=self._method("v1"),
                                       after=self._method("v1"), previous_evidence=[])
        self.assertFalse(progress["dimensions"]["validation"])
        self.assertFalse(progress["progress"])
        self.assertIn("E1", progress["misattributed_evidence"])
        self.assertNotIn("E1", progress["related_evidence"])

    def test_evidence_for_the_current_version_is_attributed(self):
        state, _ = progress_fixture()
        state["evidence"] = [*state["evidence"],
                             {"id": "E1", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "supports": ["H42"],
                              "source_ref": "exp:X900", "verification_tier": "T2",
                              "method_version": "d1"}]
        progress = i2m.method_progress(state, before=self._method("v1"),
                                       after=self._method("v1"), previous_evidence=[])
        self.assertTrue(progress["dimensions"]["validation"])
        self.assertTrue(progress["progress"])

    def test_the_same_evidence_cannot_be_consumed_twice(self):
        state, _ = progress_fixture()
        state["evidence"] = [*state["evidence"],
                             {"id": "E1", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "supports": ["H42"],
                              "source_ref": "exp:X1", "verification_tier": "T2",
                              "method_version": "d1"}]
        again = i2m.method_progress(state, before=self._method("v1"), after=self._method("v1"),
                                    previous_evidence=[], consumed_evidence=["E1"])
        self.assertFalse(again["progress"])
        self.assertEqual(again["already_consumed"], ["E1"])
        self.assertNotIn("E1", again["related_evidence"])      # it cannot count again
        # and with nothing else usable left, the reason names the repeated consumption
        only = copy.deepcopy(state)
        only["evidence"] = [e for e in only["evidence"] if e["id"] == "E1"]
        exhausted = i2m.method_progress(only, before=self._method("v1"),
                                        after=self._method("v1"), previous_evidence=[],
                                        consumed_evidence=["E1"])
        self.assertIn("已被消费", exhausted["reason"])

    # --- P2-A contract ordering ---------------------------------------------
    def test_version_number_decides_not_the_digest_order(self):
        state, _ = progress_fixture()
        state["experiments"] = [
            {"id": "X1", "status": "planned", "preregistration": {"method_contract":
                {"method_digest": "zzz", "version": 1, "method_hypothesis_ref": "H42"}}},
            {"id": "X2", "status": "planned", "preregistration": {"method_contract":
                {"method_digest": "aaa", "version": 2, "method_hypothesis_ref": "H42"}}}]
        selection = i2m.select_method_contract(state)
        self.assertEqual(selection["contract"]["version"], 2)
        self.assertEqual(selection["selected"]["experiment_id"], "X2")

    def test_an_explicit_historical_contract_is_audit_only(self):
        state, _ = progress_fixture()
        state["experiments"] = [
            {"id": "X1", "status": "superseded", "preregistration": {"method_contract":
                {"method_digest": "old", "version": 1, "method_hypothesis_ref": "H42"}}},
            {"id": "X2", "status": "planned", "preregistration": {"method_contract":
                {"method_digest": "new", "version": 2, "method_hypothesis_ref": "H42"}}}]
        selection = i2m.select_method_contract(state, experiment_id="X1")
        self.assertTrue(selection["audit_only"])
        self.assertEqual(i2m.select_method_contract(state)["contract"]["version"], 2)

    def test_a_stale_contract_never_dominates_the_loop(self):
        state, _ = progress_fixture()
        state["experiments"] = [
            {"id": "X1", "status": "archived", "preregistration": {"method_contract":
                {"method_digest": "very-new-looking", "version": 9,
                 "method_hypothesis_ref": "H42"}}}]
        self.assertIsNone(i2m.select_method_contract(state)["contract"])

    # --- P2-B replication vs duplicate --------------------------------------
    def _planned(self, state, **overrides):
        experiment = {"id": "X2", "status": "planned", "claim_targeted": ["C1"],
                      "stage": "S1", "metric": "recall@10", "data_split": "d1",
                      "preregistration": {"frozen_at_state_version": 1}}
        experiment.update(overrides)
        return experiment

    def test_a_declared_independent_replication_is_accepted(self):
        state, _ = progress_fixture()
        state["experiments"] = [
            {"id": "X1", "status": "done", "claim_targeted": ["C1"], "stage": "S1",
             "metric": "recall@10", "data_split": "d1",
             "preregistration": {"frozen_at_state_version": 1}},
            self._planned(state, independent_replication={
                "declared": True, "seed": "s2", "purpose": "confirmatory replication",
                "leakage_avoidance": "disjoint units",
                "statistical_purpose": "increase confidence"})]
        self.assertNotIn("I2M82", i2m._rules(i2m.planned_validity_errors(
            state, state["experiments"][1])))

    def test_an_undeclared_repeat_of_the_same_question_is_refused(self):
        state, _ = progress_fixture()
        state["experiments"] = [
            {"id": "X1", "status": "done", "claim_targeted": ["C1"], "stage": "S1",
             "metric": "recall@10", "data_split": "d1",
             "preregistration": {"frozen_at_state_version": 1}},
            self._planned(state)]
        self.assertIn("I2M82", i2m._rules(i2m.planned_validity_errors(
            state, state["experiments"][1])))

    def test_renaming_does_not_bypass_the_duplicate_check(self):
        state, _ = progress_fixture()
        state["experiments"] = [
            {"id": "X1", "status": "done", "claim_targeted": ["C1"], "stage": "S1",
             "metric": "recall@10", "data_split": "d1",
             "preregistration": {"frozen_at_state_version": 1}},
            self._planned(state, id="X-RENAMED")]
        self.assertIn("I2M82", i2m._rules(i2m.planned_validity_errors(
            state, state["experiments"][1])))

    def test_reusing_the_same_execution_event_is_refused(self):
        state, _ = progress_fixture()
        state["experiments"] = [
            {"id": "X1", "status": "done", "claim_targeted": ["C1"], "stage": "S1",
             "metric": "recall@10", "data_split": "d1", "execution_event": "run-777",
             "preregistration": {"frozen_at_state_version": 1}},
            self._planned(state, execution_event="run-777",
                          independent_replication={"declared": True, "seed": "s",
                                                   "purpose": "p",
                                                   "leakage_avoidance": "l"})]
        self.assertIn("I2M85", i2m._rules(i2m.planned_validity_errors(
            state, state["experiments"][1])))

    def test_a_replication_must_declare_independence(self):
        state, _ = progress_fixture()
        state["experiments"] = [
            {"id": "X1", "status": "done", "claim_targeted": ["C1"], "stage": "S1",
             "metric": "recall@10", "data_split": "d1",
             "preregistration": {"frozen_at_state_version": 1}},
            self._planned(state, independent_replication={"declared": True, "seed": "s"})]
        self.assertIn("I2M84", i2m._rules(i2m.planned_validity_errors(
            state, state["experiments"][1])))

    # --- mechanism self-report ----------------------------------------------
    def test_a_self_declared_mechanism_without_review_is_capped(self):
        state, _ = progress_fixture()
        state["evidence"] = [{"id": "E1", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "supports": ["H42"],
                              "source_ref": "exp:X1", "verification_tier": "T2",
                              "mechanism_support": "mechanism"}]
        readiness = i2m.insight_readiness(state, insight())
        self.assertEqual(readiness["mechanism_level"], i2m.SUPPORT_PREDICTION_OBSERVED)
        self.assertEqual(readiness["mechanism_status"], i2m.VERDICT_HYPOTHESIS)
        self.assertIn("I2M97", {item["rule"] for item in readiness["diagnostics"]})

    def test_a_reviewed_mechanism_claim_is_accepted(self):
        state, _ = progress_fixture()
        state["evidence"] = [{"id": "E1", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "supports": ["H42"],
                              "source_ref": "exp:X1", "verification_tier": "T2",
                              "mechanism_support": "mechanism", "assurance_ref": "AS-OK"}]
        readiness = i2m.insight_readiness(state, insight())
        self.assertEqual(readiness["mechanism_level"], i2m.SUPPORT_MECHANISM)
        self.assertEqual(readiness["mechanism_status"], i2m.VERDICT_VERIFIED)

    def test_an_intervention_effect_without_review_is_only_an_observation(self):
        state, _ = progress_fixture()
        state["evidence"] = [{"id": "E1", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "supports": ["H42"],
                              "source_ref": "exp:X1", "verification_tier": "T2",
                              "mechanism_support": "intervention"}]
        readiness = i2m.insight_readiness(state, insight())
        self.assertEqual(readiness["mechanism_level"], i2m.SUPPORT_PREDICTION_OBSERVED)
        self.assertIn("I2M96", {item["rule"] for item in readiness["diagnostics"]})
