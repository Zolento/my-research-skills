#!/usr/bin/env python3
"""test_prediction_compare.py — Phase 2: prediction, anomaly, competition, insight.

The behaviours under test are the ones that separate "explained it afterwards" from
"tested it": a prediction that cannot be decided, an execution that failed, a rewording
presented as a rival, a criterion edited after the result, and a card that certifies its
own novelty. Each has a test that fails if the gate is removed.
"""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import cognition as cg
import evidence_outcome as eo
import prediction_compare as pc

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "prediction_compare.py"
FIXTURES = ROOT / "examples" / "cognition"


def clone(value):
    return json.loads(json.dumps(value))


def bound_source(content: str, kind: str = "result") -> dict:
    return {"kind": kind, "location": "results/A/X1/summary.json",
            "content": content, "digest": eo.digest(content)}


def quiet(callable_, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()) as sink:
        result = callable_(*args, **kwargs)
    return result, sink.getvalue()


# ---------------------------------------------------------------------------
# Criteria
# ---------------------------------------------------------------------------

class TestCriterion(unittest.TestCase):

    def test_quantitative_criterion_accepts_a_valid_shape(self):
        self.assertEqual(pc.criterion_errors(
            {"kind": "quantitative", "quantity": "落差（dB）",
             "expected_range": [0.5, 3.0], "tolerance": 0.1}, "p"), [])

    def test_quantitative_requires_a_range(self):
        errors = pc.criterion_errors(
            {"kind": "quantitative", "quantity": "x", "tolerance": 0.1}, "p")
        self.assertTrue(errors)

    def test_inverted_range_is_rejected(self):
        errors = pc.criterion_errors(
            {"kind": "quantitative", "quantity": "x",
             "expected_range": [3.0, 0.5], "tolerance": 0.1}, "p")
        self.assertTrue(errors)

    def test_negative_tolerance_is_rejected(self):
        errors = pc.criterion_errors(
            {"kind": "quantitative", "quantity": "x",
             "expected_range": [0.0, 1.0], "tolerance": -1}, "p")
        self.assertTrue(errors)

    def test_directional_requires_a_direction(self):
        self.assertTrue(pc.criterion_errors(
            {"kind": "directional", "quantity": "x", "tolerance": 0.0}, "p"))
        self.assertEqual(pc.criterion_errors(
            {"kind": "directional", "quantity": "x", "direction": "decrease",
             "tolerance": 0.0}, "p"), [])

    def test_discrete_labels_must_be_non_empty_and_disjoint(self):
        self.assertTrue(pc.criterion_errors(
            {"kind": "discrete", "quantity": "x", "held_labels": [], "failed_labels": ["b"]}, "p"))
        self.assertTrue(pc.criterion_errors(
            {"kind": "discrete", "quantity": "x",
             "held_labels": ["a"], "failed_labels": ["a"]}, "p"))

    def test_unknown_kind_is_rejected(self):
        self.assertTrue(pc.criterion_errors({"kind": "fuzzy", "quantity": "x"}, "p"))

    def test_rule_text_does_not_change_the_signature(self):
        left = {"kind": "quantitative", "quantity": "q",
                "expected_range": [0.0, 1.0], "tolerance": 0.1, "rule": "wording A"}
        right = {"kind": "quantitative", "quantity": "q",
                 "expected_range": [0.0, 1.0], "tolerance": 0.1, "rule": "wording B"}
        self.assertEqual(pc.criterion_signature(left), pc.criterion_signature(right))

    def test_a_different_range_changes_the_signature(self):
        left = {"kind": "quantitative", "quantity": "q",
                "expected_range": [0.0, 1.0], "tolerance": 0.1}
        right = {"kind": "quantitative", "quantity": "q",
                 "expected_range": [0.0, 2.0], "tolerance": 0.1}
        self.assertNotEqual(pc.criterion_signature(left), pc.criterion_signature(right))


# ---------------------------------------------------------------------------
# References and comparison
# ---------------------------------------------------------------------------

class TestComparison(unittest.TestCase):

    def setUp(self):
        self.state, self.observation = pc._fixture()

    def test_reference_parsing(self):
        self.assertEqual(pc.parse_ref("X2:O1"), ("X2", "O1"))
        self.assertIsNone(pc.parse_ref("X2"))
        self.assertIsNone(pc.parse_ref("X2:O1:O2"))
        self.assertIsNone(pc.parse_ref(7))

    def test_reference_resolves_against_the_frozen_preregistration(self):
        resolved, errors = pc.resolve_prediction(self.state, "X1:O1")
        self.assertEqual(errors, [])
        self.assertEqual(resolved["outcome_id"], "O1")
        self.assertIsInstance(resolved["criterion"], dict)

    def test_unknown_experiment_and_outcome_are_reported(self):
        self.assertTrue(pc.resolve_prediction(self.state, "X9:O1")[1])
        self.assertTrue(pc.resolve_prediction(self.state, "X1:O9")[1])

    def test_an_experiment_without_a_preregistration_has_no_prediction(self):
        state = clone(self.state)
        state["experiments"][0]["preregistration"] = None
        resolved, errors = pc.resolve_prediction(state, "X1:O1")
        self.assertIsNone(resolved)
        self.assertIn("PC3", {d.rule for d in errors})

    def test_quantitative_bands(self):
        criterion = {"kind": "quantitative", "quantity": "q",
                     "expected_range": [0.5, 3.0], "tolerance": 0.1}
        self.assertEqual(pc.compare_outcome(criterion, {"value": 1.0})[0], "PREDICTION_HELD")
        self.assertEqual(pc.compare_outcome(criterion, {"value": 0.45})[0], "WITHIN_TOLERANCE")
        self.assertEqual(pc.compare_outcome(criterion, {"value": 0.2})[0], "PREDICTION_DEVIATED")
        self.assertEqual(pc.compare_outcome(criterion, {"value": 9.0})[0], "PREDICTION_DEVIATED")
        self.assertEqual(pc.compare_outcome(criterion, {})[0], "UNTESTABLE")

    def test_directional_bands(self):
        criterion = {"kind": "directional", "quantity": "q",
                     "direction": "decrease", "tolerance": 0.05}
        self.assertEqual(pc.compare_outcome(criterion, {"direction": "decrease"})[0],
                         "PREDICTION_HELD")
        self.assertEqual(pc.compare_outcome(criterion, {"direction": "increase"})[0],
                         "PREDICTION_DEVIATED")
        self.assertEqual(pc.compare_outcome(criterion, {"value": -0.5})[0], "PREDICTION_HELD")
        self.assertEqual(pc.compare_outcome(criterion, {"value": 0.01})[0], "WITHIN_TOLERANCE")
        self.assertEqual(pc.compare_outcome(criterion, {"direction": "sideways"})[0],
                         "UNTESTABLE")

    def test_no_change_direction_uses_the_tolerance(self):
        criterion = {"kind": "directional", "quantity": "q",
                     "direction": "no_change", "tolerance": 0.1}
        self.assertEqual(pc.compare_outcome(criterion, {"value": 0.05})[0], "PREDICTION_HELD")
        self.assertEqual(pc.compare_outcome(criterion, {"value": 0.5})[0], "PREDICTION_DEVIATED")

    def test_discrete_labels(self):
        criterion = {"kind": "discrete", "quantity": "q",
                     "held_labels": ["yes"], "failed_labels": ["no"]}
        self.assertEqual(pc.compare_outcome(criterion, {"label": "yes"})[0], "PREDICTION_HELD")
        self.assertEqual(pc.compare_outcome(criterion, {"label": "no"})[0], "PREDICTION_DEVIATED")
        self.assertEqual(pc.compare_outcome(criterion, {"label": "maybe"})[0], "UNTESTABLE")
        self.assertEqual(pc.compare_outcome(criterion, {})[0], "UNTESTABLE")


# ---------------------------------------------------------------------------
# Observation packets and assessment
# ---------------------------------------------------------------------------

class TestAssessment(unittest.TestCase):

    def setUp(self):
        self.state, self.observation = pc._fixture()

    def test_every_observation_must_be_source_bound(self):
        packet = clone(self.observation)
        packet["outcomes"][0]["source"]["digest"] = "sha256:deadbeef"
        rules = {d.rule for d in pc.observation_errors(packet)}
        self.assertIn("PC2", rules)

    def test_a_packet_without_an_execution_verdict_is_rejected(self):
        packet = clone(self.observation)
        packet["execution"] = {"status": "completed"}
        self.assertIn("PC2", {d.rule for d in pc.observation_errors(packet)})

    def test_a_deviating_prediction_deviates_the_experiment(self):
        assessment, diagnostics = pc.assess_experiment(self.state, self.observation)
        self.assertEqual(assessment["outcome_class"], "PREDICTION_DEVIATED")
        self.assertIn("PC6", {d.rule for d in diagnostics})

    def test_all_predictions_held_holds_the_experiment(self):
        packet = clone(self.observation)
        packet["outcomes"] = [packet["outcomes"][0]]
        assessment, _ = pc.assess_experiment(self.state, packet)
        self.assertEqual(assessment["outcome_class"], "PREDICTION_HELD")

    def test_an_invalid_execution_is_never_a_prediction_verdict(self):
        packet = clone(self.observation)
        packet["execution"]["validity"] = "INVALID"
        assessment, diagnostics = pc.assess_experiment(self.state, packet)
        self.assertEqual(assessment["outcome_class"], "INVALID_EXECUTION")
        self.assertIn("PC6", {d.rule for d in diagnostics})
        self.assertEqual(assessment["predictions"], [])

    def test_an_unknown_execution_still_compares_but_is_marked(self):
        packet = clone(self.observation)
        packet["execution"]["validity"] = "UNKNOWN"
        assessment, _ = pc.assess_experiment(self.state, packet)
        self.assertNotEqual(assessment["outcome_class"], "INVALID_EXECUTION")

    def test_no_preregistration_means_exploratory_only(self):
        state = clone(self.state)
        state["experiments"][0]["preregistration"] = None
        state["experiments"][0]["status"] = "planned"
        state["experiments"][0]["result_at_state_version"] = None
        assessment, diagnostics = pc.assess_experiment(state, self.observation)
        self.assertEqual(assessment["outcome_class"], "EXPLORATORY_ANOMALY")
        self.assertTrue(any("探索性异常" in d.detail for d in diagnostics))

    def test_a_frozen_outcome_without_a_criterion_is_untestable(self):
        state = clone(self.state)
        del state["experiments"][0]["preregistration"]["outcomes"][0]["criterion"]
        assessment, diagnostics = pc.assess_experiment(state, self.observation)
        verdicts = {entry["verdict"] for entry in assessment["predictions"]}
        self.assertIn("UNTESTABLE", verdicts)
        self.assertIn("PC1", {d.rule for d in diagnostics})

    def test_an_observation_for_an_unfrozen_outcome_is_rejected(self):
        packet = clone(self.observation)
        packet["outcomes"][0]["id"] = "O9"
        assessment, diagnostics = pc.assess_experiment(self.state, packet)
        self.assertIn("PC3", {d.rule for d in diagnostics})

    def test_a_duplicate_observation_id_is_rejected(self):
        packet = clone(self.observation)
        packet["outcomes"] = [packet["outcomes"][0], clone(packet["outcomes"][0])]
        _, diagnostics = pc.assess_experiment(self.state, packet)
        self.assertIn("PC2", {d.rule for d in diagnostics})

    def test_unknown_experiment_is_reported(self):
        packet = clone(self.observation)
        packet["experiment_id"] = "X404"
        assessment, diagnostics = pc.assess_experiment(self.state, packet)
        self.assertIn("PC3", {d.rule for d in diagnostics})


# ---------------------------------------------------------------------------
# Freeze integrity
# ---------------------------------------------------------------------------

class TestFreezeIntegrity(unittest.TestCase):

    def setUp(self):
        self.state, _ = pc._fixture()
        self.freeze = {
            "_schema": cg.SCHEMA_REVISION, "id": "REV1", "seq": 1,
            "kind": "prediction_freeze", "subject": "X1", "actor": "R8",
            "at_state_version": 5, "summary": "freeze",
            "trigger": {"kind": "preregistration_frozen", "ref": "X1"},
            "refs": {"experiments": ["X1"], "claims": ["C1"]},
            "after": {"freeze_digest": pc.freeze_digest(self.state["experiments"][0])},
        }

    def test_a_clean_freeze_has_no_findings(self):
        self.assertEqual(pc.check_freezes(self.state, [self.freeze]), [])

    def test_the_digest_covers_the_criteria(self):
        state = clone(self.state)
        state["experiments"][0]["preregistration"]["outcomes"][0]["criterion"][
            "expected_range"] = [0.9, 3.0]
        self.assertNotEqual(pc.freeze_digest(state["experiments"][0]),
                            self.freeze["after"]["freeze_digest"])

    def test_a_silent_rewrite_is_detected(self):
        state = clone(self.state)
        state["experiments"][0]["preregistration"]["outcomes"][0]["criterion"][
            "expected_range"] = [0.9, 3.0]
        self.assertIn("PC4", {d.rule for d in pc.check_freezes(state, [self.freeze])})

    def test_a_recorded_amendment_before_the_result_is_not_tampering(self):
        state = clone(self.state)
        state["experiments"][0]["preregistration"]["outcomes"][0]["criterion"][
            "expected_range"] = [0.9, 3.0]
        state["experiments"][0]["preregistration"]["amended"] = [
            {"at_state_version": 5, "reason": "口径写错，结果产生前修正"}]
        self.assertFalse([d for d in pc.check_freezes(state, [self.freeze])
                          if d.rule == "PC4"])

    def test_an_amendment_after_the_result_is_post_hoc(self):
        state = clone(self.state)
        state["experiments"][0]["preregistration"]["outcomes"][0]["criterion"][
            "expected_range"] = [0.9, 3.0]
        state["experiments"][0]["preregistration"]["amended"] = [
            {"at_state_version": 6, "reason": "看到结果后调整口径"}]
        details = [d.detail for d in pc.check_freezes(state, [self.freeze])
                   if d.rule == "PC4"]
        self.assertTrue(any("事后修订无效" in detail for detail in details))

    def test_an_amendment_without_a_reason_is_rejected(self):
        state = clone(self.state)
        state["experiments"][0]["preregistration"]["outcomes"][0]["criterion"][
            "expected_range"] = [0.9, 3.0]
        state["experiments"][0]["preregistration"]["amended"] = [{"at_state_version": 5}]
        self.assertIn("PC4", {d.rule for d in pc.check_freezes(state, [self.freeze])})

    def test_a_late_registration_is_reported(self):
        late = clone(self.freeze)
        late["at_state_version"] = 6
        self.assertIn("PC5", {d.rule for d in pc.check_freezes(self.state, [late])})

    def test_a_freeze_without_a_digest_is_reported(self):
        blind = clone(self.freeze)
        blind["after"] = {}
        self.assertIn("PC5", {d.rule for d in pc.check_freezes(self.state, [blind])})

    def test_a_freeze_over_an_outcome_without_a_criterion_is_reported(self):
        state = clone(self.state)
        del state["experiments"][0]["preregistration"]["outcomes"][0]["criterion"]
        freeze = clone(self.freeze)
        freeze["after"]["freeze_digest"] = pc.freeze_digest(state["experiments"][0])
        self.assertIn("PC1", {d.rule for d in pc.check_freezes(state, [freeze])})

    def test_a_freeze_over_a_missing_experiment_is_reported(self):
        blind = clone(self.freeze)
        blind["refs"] = {"experiments": ["X404"]}
        self.assertIn("PC3", {d.rule for d in pc.check_freezes(self.state, [blind])})


# ---------------------------------------------------------------------------
# Competition
# ---------------------------------------------------------------------------

class TestCompetition(unittest.TestCase):

    def setUp(self):
        self.state, _ = pc._fixture()
        self.mechanisms = [
            {"id": "M1", "structure": {"pending_predictions": ["X2:O1"]}},
            {"id": "M2", "structure": {"pending_predictions": ["X2:O3"]}},
        ]
        self.competition = {
            "id": "CP1", "status": "open", "mechanisms": ["M1", "M2"],
            "conflicting_predictions": ["X2:O1", "X2:O3"],
            "predictions": [{"mechanism": "M1", "ref": "X2:O1"},
                            {"mechanism": "M2", "ref": "X2:O3"}],
            "discriminating_intervention": "X2",
            "decision_impact": "method_decision_differs",
        }

    def test_a_real_gap_is_distinguishable(self):
        verdict, _ = pc.distinguishability(self.state, self.competition, self.mechanisms)
        self.assertEqual(verdict["verdict"], "DISTINGUISHABLE")
        self.assertEqual(len(set(verdict["signatures"].values())), 2)

    def test_a_rewording_is_not_a_competing_prediction(self):
        equivalent = clone(self.competition)
        equivalent["conflicting_predictions"] = ["X2:O1", "X2:O2"]
        equivalent["predictions"] = [{"mechanism": "M1", "ref": "X2:O1"},
                                     {"mechanism": "M2", "ref": "X2:O2"}]
        verdict, diagnostics = pc.distinguishability(self.state, equivalent, self.mechanisms)
        self.assertEqual(verdict["verdict"], "NOT_DISTINGUISHABLE_EQUIVALENT_PREDICTIONS")
        self.assertIn("PC6", {d.rule for d in diagnostics})

    def test_without_an_intervention_the_competition_is_not_decidable(self):
        blind = clone(self.competition)
        blind["discriminating_intervention"] = "TBD"
        verdict, _ = pc.distinguishability(self.state, blind, self.mechanisms)
        self.assertEqual(verdict["verdict"], "NOT_DISTINGUISHABLE_NO_INTERVENTION")

    def test_without_a_prediction_gap_there_is_no_competition(self):
        flat = clone(self.competition)
        flat["conflicting_predictions"] = []
        flat["predictions"] = []
        verdict, _ = pc.distinguishability(self.state, flat, self.mechanisms)
        self.assertEqual(verdict["verdict"], "NOT_DISTINGUISHABLE_NO_PREDICTION_GAP")

    def test_unattributed_predictions_are_insufficient_structure(self):
        unowned = clone(self.competition)
        unowned.pop("predictions")
        verdict, diagnostics = pc.distinguishability(self.state, unowned, None)
        self.assertEqual(verdict["verdict"], "INSUFFICIENT_STRUCTURE")
        self.assertTrue(any("归属" in d.detail for d in diagnostics))

    def test_a_single_mechanism_is_insufficient(self):
        solo = clone(self.competition)
        solo["mechanisms"] = ["M1"]
        verdict, _ = pc.distinguishability(self.state, solo, self.mechanisms)
        self.assertEqual(verdict["verdict"], "INSUFFICIENT_STRUCTURE")

    def test_a_prediction_on_another_experiment_cannot_be_separated(self):
        elsewhere = clone(self.competition)
        elsewhere["predictions"] = [{"mechanism": "M1", "ref": "X2:O1"},
                                    {"mechanism": "M2", "ref": "X1:O2"}]
        elsewhere["conflicting_predictions"] = ["X2:O1", "X1:O2"]
        verdict, _ = pc.distinguishability(self.state, elsewhere, self.mechanisms)
        self.assertEqual(verdict["verdict"], "INSUFFICIENT_STRUCTURE")

    def test_ownership_can_come_from_the_mechanism_structure(self):
        declared = dict(self.competition)
        declared.pop("predictions")
        verdict, _ = pc.distinguishability(self.state, declared, self.mechanisms)
        self.assertEqual(verdict["verdict"], "DISTINGUISHABLE")


# ---------------------------------------------------------------------------
# Behaviour switch
# ---------------------------------------------------------------------------

class TestDiagnosisSwitch(unittest.TestCase):

    def setUp(self):
        self.state, _ = pc._fixture()
        self.mechanisms = [
            {"id": "M1", "structure": {"pending_predictions": ["X2:O1"]}},
            {"id": "M2", "structure": {"pending_predictions": ["X2:O3"]}},
        ]
        self.idle = {"eig_calibration": {"records": [
            {"experiment": "X0", "predicted_information_gain": "low",
             "actual_information_gain": "zero",
             "observed_delta": {"claim_status_changes": [], "uncertainty_changes": [],
                                "hypothesis_status_changes": [], "new_uncertainties": [],
                                "unexpected_observations": 0}}] * 2}}

    def competition(self, **overrides):
        base = {
            "id": "CP1", "status": "open", "mechanisms": ["M1", "M2"],
            "conflicting_predictions": ["X2:O1", "X2:O3"],
            "predictions": [{"mechanism": "M1", "ref": "X2:O1"},
                            {"mechanism": "M2", "ref": "X2:O3"}],
            "discriminating_intervention": "X2",
            "decision_impact": "method_decision_differs",
        }
        base.update(overrides)
        return base

    def test_zero_streak_is_read_from_the_scheduler(self):
        self.assertEqual(pc.trailing_zero_streak(self.idle), 2)
        self.assertEqual(pc.trailing_zero_streak(None), 0)
        self.assertEqual(pc.trailing_zero_streak({"eig_calibration": {"records": [
            {"actual_information_gain": "high"}]}}), 0)

    def test_a_healthy_project_continues_attribution(self):
        switch = pc.diagnosis_switch(self.state, [self.competition()], None, self.mechanisms)
        self.assertEqual(switch["action"], "CONTINUE_ATTRIBUTION")

    def test_repeated_empty_diagnosis_asks_for_a_discriminating_intervention(self):
        blind = self.competition(discriminating_intervention="TBD")
        switch = pc.diagnosis_switch(self.state, [blind], self.idle, self.mechanisms)
        self.assertEqual(switch["action"], "FIND_DISCRIMINATING_INTERVENTION")
        self.assertIn("zero", switch["reason"])

    def test_an_undecidable_but_decision_irrelevant_rival_is_recorded_and_stopped(self):
        equivalent = self.competition(
            conflicting_predictions=["X2:O1", "X2:O2"],
            predictions=[{"mechanism": "M1", "ref": "X2:O1"},
                         {"mechanism": "M2", "ref": "X2:O2"}],
            decision_impact="same_method_decision")
        switch = pc.diagnosis_switch(self.state, [equivalent], self.idle, self.mechanisms)
        self.assertEqual(switch["action"], "RECORD_BOUNDARY_AND_STOP")

    def test_stagnation_without_an_undecidable_rival_redesigns_the_question(self):
        equivalent = self.competition(
            conflicting_predictions=["X2:O1", "X2:O2"],
            predictions=[{"mechanism": "M1", "ref": "X2:O1"},
                         {"mechanism": "M2", "ref": "X2:O2"}])
        switch = pc.diagnosis_switch(self.state, [equivalent], self.idle, self.mechanisms)
        self.assertEqual(switch["action"], "REDESIGN_QUESTION")

    def test_a_method_can_be_explored_under_uncertainty(self):
        no_gap = self.competition(conflicting_predictions=[], predictions=[])
        switch = pc.diagnosis_switch(self.state, [no_gap], None, self.mechanisms)
        self.assertEqual(switch["action"], "FIND_DISCRIMINATING_INTERVENTION")
        equivalent = self.competition(
            conflicting_predictions=["X2:O1", "X2:O2"],
            predictions=[{"mechanism": "M1", "ref": "X2:O1"},
                         {"mechanism": "M2", "ref": "X2:O2"}])
        switch = pc.diagnosis_switch(self.state, [equivalent], None, self.mechanisms)
        self.assertEqual(switch["action"], "EXPLORE_METHOD_UNDER_UNCERTAINTY")

    def test_independent_exploration_is_never_blocked(self):
        for scheduler in (None, self.idle):
            switch = pc.diagnosis_switch(self.state, [self.competition()], scheduler,
                                         self.mechanisms)
            self.assertTrue(switch["independent_exploration_allowed"])

    def test_the_switch_does_not_rewrite_history(self):
        scheduler = clone(self.idle)
        pc.diagnosis_switch(self.state, [self.competition()], scheduler, self.mechanisms)
        self.assertEqual(scheduler, self.idle)


# ---------------------------------------------------------------------------
# Insight cards
# ---------------------------------------------------------------------------

class TestInsightCards(unittest.TestCase):

    def setUp(self):
        self.state, _ = pc._fixture()
        self.card = {
            "_schema": pc.SCHEMA_INSIGHT, "id": "IC1", "at_state_version": 6, "actor": "R6",
            "observation": "中心 C 方向反转", "existing_mechanism": "M1",
            "challenged_assumption": "AS1", "proposed_mechanism": "M2",
            "explanatory_gain": "用域偏移解释反转", "competing_mechanism": "M1",
            "novel_prediction": {"ref": "X2:O1", "statement": "解耦后落差下降 ≥ 0.5 dB"},
            "discriminating_intervention": "X2", "scope_boundary": "数据集 A",
            "scientific_implication": "转向域覆盖",
            "refs": {"claims": ["C1"], "hypotheses": ["H1"]},
            "declared_class": "predictive_insight_candidate",
        }

    def test_a_complete_card_validates(self):
        self.assertEqual(pc.insight_card_errors(self.card, self.state), [])

    def test_every_required_element_is_required(self):
        for field in pc.CARD_REQUIRED_TEXT:
            broken = clone(self.card)
            broken[field] = ""
            self.assertTrue([d for d in pc.insight_card_errors(broken, self.state)
                             if d.rule == "PC8"], msg=field)

    def test_a_prediction_reference_is_required(self):
        broken = clone(self.card)
        broken["novel_prediction"] = {}
        self.assertIn("PC8", {d.rule for d in pc.insight_card_errors(broken, self.state)})

    def test_a_dangling_reference_is_rejected(self):
        broken = clone(self.card)
        broken["refs"] = {"claims": ["C404"]}
        self.assertIn("PC8", {d.rule for d in pc.insight_card_errors(broken, self.state)})

    def test_a_card_from_the_future_is_rejected(self):
        broken = clone(self.card)
        broken["at_state_version"] = 99
        self.assertIn("PC8", {d.rule for d in pc.insight_card_errors(broken, self.state)})

    def test_the_class_is_derived_not_declared(self):
        derived, _ = pc.classify_insight(self.card, self.state)
        self.assertEqual(derived, "predictive_insight_candidate")
        self.assertEqual([d.rule for d in pc.insight_card_errors(self.card, self.state)], [])

    def test_a_reworded_class_is_reported_and_the_derived_class_wins(self):
        softened = clone(self.card)
        softened["declared_class"] = "explanatory_hypothesis"
        self.assertIn("PC9", {d.rule for d in pc.insight_card_errors(softened, self.state)})

    def test_self_certified_evidence_support_is_a_hard_violation(self):
        supported = clone(self.card)
        supported["declared_class"] = "evidence_supported_insight"
        supported["novel_prediction"] = {"ref": "X1:O1", "statement": "落差 ≥ 0.5 dB"}
        supported["discriminating_intervention"] = "X1"
        supported["refs"] = {"claims": ["C1"], "evidence": ["E1"], "hypotheses": ["H1"]}
        self.assertIn("PC7", {d.rule for d in pc.insight_card_errors(supported, self.state)})

    def test_evidence_support_requires_an_independent_structural_audit(self):
        supported = clone(self.card)
        supported["declared_class"] = "evidence_supported_insight"
        supported["novel_prediction"] = {"ref": "X1:O1", "statement": "落差 ≥ 0.5 dB"}
        supported["discriminating_intervention"] = "X1"
        supported["refs"] = {"claims": ["C1"], "evidence": ["E1"], "hypotheses": ["H1"]}
        state = clone(self.state)
        state["assurance"] = [{"id": "A1", "target": "C1",
                               "attack_type": "structural-equivalence",
                               "verification_tier": "T1",
                               "kill_condition": "若与 LIT1 结构等价则杀死",
                               "discriminating_test": "X1"}]
        derived, reasons = pc.classify_insight(supported, state)
        self.assertEqual(derived, "evidence_supported_insight")
        self.assertTrue(reasons["structural_equivalence_audit"])
        self.assertFalse([d for d in pc.insight_card_errors(supported, state)
                          if d.rule == "PC7"])

    def test_evidence_outside_the_boundary_cannot_support_the_card(self):
        state = clone(self.state)
        state["evidence"][0]["scope"] = "数据集 Z"
        state["assurance"] = [{"id": "A1", "target": "C1",
                               "attack_type": "structural-equivalence",
                               "verification_tier": "T1",
                               "kill_condition": "x", "discriminating_test": "X1"}]
        derived, _ = pc.classify_insight(self.card, state)
        self.assertNotEqual(derived, "evidence_supported_insight")

    def test_evidence_must_be_bound_to_the_prediction_experiment(self):
        state = clone(self.state)
        state["evidence"][0]["depends_on"] = []
        state["assurance"] = [{"id": "A1", "target": "C1",
                               "attack_type": "structural-equivalence",
                               "verification_tier": "T1",
                               "kill_condition": "x", "discriminating_test": "X1"}]
        supported = clone(self.card)
        supported["refs"] = {"claims": ["C1"], "evidence": ["E1"]}
        supported["novel_prediction"] = {"ref": "X1:O1", "statement": "x"}
        derived, _ = pc.classify_insight(supported, state)
        self.assertNotEqual(derived, "evidence_supported_insight")

    def test_card_log_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / pc.INSIGHT_CARDS_NAME
            path.write_text(json.dumps(self.card, ensure_ascii=False) + "\nnot json\n",
                            encoding="utf-8")
            cards, diagnostics = pc.load_cards(path)
            self.assertEqual(len(cards), 1)
            self.assertIn("PC8", {d.rule for d in diagnostics})


# ---------------------------------------------------------------------------
# Integration with the cognitive index and the shipped fixture
# ---------------------------------------------------------------------------

class TestFixtureIntegration(unittest.TestCase):

    def test_the_cognitive_index_projects_the_fixture_cards(self):
        state = json.loads((FIXTURES / "state.json").read_text(encoding="utf-8"))
        revisions, _ = cg.load_revisions(FIXTURES / "model-revisions.jsonl")
        cards, _ = cg.load_insight_cards(FIXTURES / pc.INSIGHT_CARDS_NAME)
        index, diagnostics = cg.full_index(state, revisions, "A", cards)
        self.assertEqual([d.render() for d in diagnostics if d.rule in ("PC7", "PC8")], [])
        self.assertEqual(len(index["insights"]), 1)
        self.assertEqual(index["insights"][0]["derived_class"], "predictive_insight_candidate")

    def test_the_fixture_observation_compares(self):
        state = json.loads((FIXTURES / "state.json").read_text(encoding="utf-8"))
        packet = json.loads((FIXTURES / "prediction-observation.json").read_text("utf-8"))
        assessment, diagnostics = pc.assess_experiment(state, packet)
        self.assertEqual(assessment["outcome_class"], "PREDICTION_HELD")
        self.assertEqual(diagnostics, [])

    def test_the_fixture_competition_is_distinguishable(self):
        state = json.loads((FIXTURES / "state.json").read_text(encoding="utf-8"))
        revisions, _ = cg.load_revisions(FIXTURES / "model-revisions.jsonl")
        index, _ = cg.full_index(state, revisions, "A")
        competition = next(c for c in index["competitions"] if c["id"] == "CP1")
        verdict, _ = pc.distinguishability(state, competition, index["mechanisms"])
        self.assertEqual(verdict["verdict"], "DISTINGUISHABLE")

    def test_the_fixture_freeze_digests_still_match(self):
        state = json.loads((FIXTURES / "state.json").read_text(encoding="utf-8"))
        revisions, _ = cg.load_revisions(FIXTURES / "model-revisions.jsonl")
        self.assertEqual(pc.check_freezes(state, revisions), [])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCLI(unittest.TestCase):

    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True, cwd=str(ROOT))

    def project(self, root: pathlib.Path):
        state_path = root / cg.STATE_NAME
        state_path.write_text((FIXTURES / "state.json").read_text(encoding="utf-8"),
                              encoding="utf-8")
        cognition_dir = root / cg.COGNITION_DIRNAME
        cognition_dir.mkdir()
        for name in (cg.REVISIONS_NAME, pc.INSIGHT_CARDS_NAME):
            (cognition_dir / name).write_text((FIXTURES / name).read_text(encoding="utf-8"),
                                              encoding="utf-8")
        return state_path, cognition_dir

    def test_selftest_passes(self):
        proc = self.run_cli("--selftest")
        self.assertEqual(proc.returncode, pc.EXIT_OK, proc.stdout + proc.stderr)
        self.assertIn("selftest: PASS", proc.stdout)

    def test_list_classes(self):
        proc = self.run_cli("--list-classes")
        self.assertEqual(proc.returncode, pc.EXIT_OK)
        self.assertEqual([line.strip() for line in proc.stdout.splitlines() if line.strip()],
                         list(pc.OUTCOME_CLASSES))

    def test_missing_command_is_an_argument_error(self):
        self.assertEqual(self.run_cli().returncode, pc.EXIT_ERROR)

    def test_missing_state_is_an_environment_error(self):
        self.assertEqual(self.run_cli("compare", "--state", "/nope.json").returncode,
                         pc.EXIT_ENV)

    def test_freeze_reports_the_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path, _ = self.project(pathlib.Path(temp))
            proc = self.run_cli("freeze", "--state", str(state_path), "--experiment", "X1")
            self.assertEqual(proc.returncode, pc.EXIT_OK, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["kind"], "prediction_freeze")
            self.assertTrue(payload["criteria_present"])

    def test_compare_reports_the_class(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path, _ = self.project(pathlib.Path(temp))
            proc = self.run_cli("compare", "--state", str(state_path),
                                "--packet", str(FIXTURES / "prediction-observation.json"))
            self.assertEqual(proc.returncode, pc.EXIT_OK, proc.stdout + proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["outcome_class"], "PREDICTION_HELD")

    def test_compete_and_switch_run(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path, cognition_dir = self.project(pathlib.Path(temp))
            compete = self.run_cli("compete", "--state", str(state_path),
                                   "--cognition", str(cognition_dir), "--competition", "CP1")
            self.assertEqual(compete.returncode, pc.EXIT_OK, compete.stdout + compete.stderr)
            switch = self.run_cli("switch", "--state", str(state_path),
                                  "--cognition", str(cognition_dir))
            self.assertEqual(switch.returncode, pc.EXIT_OK, switch.stdout + switch.stderr)
            self.assertIn(json.loads(switch.stdout)["action"], pc.SWITCH_ACTIONS)

    def test_insight_reports_the_derived_class(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path, cognition_dir = self.project(pathlib.Path(temp))
            proc = self.run_cli("insight", "--state", str(state_path),
                                "--cognition", str(cognition_dir))
            self.assertEqual(proc.returncode, pc.EXIT_OK, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload[0]["derived_class"], "predictive_insight_candidate")

    def test_a_missing_competition_is_an_environment_error(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path, cognition_dir = self.project(pathlib.Path(temp))
            proc = self.run_cli("compete", "--state", str(state_path),
                                "--cognition", str(cognition_dir), "--competition", "CP9")
            self.assertEqual(proc.returncode, pc.EXIT_ENV)


if __name__ == "__main__":
    unittest.main()
