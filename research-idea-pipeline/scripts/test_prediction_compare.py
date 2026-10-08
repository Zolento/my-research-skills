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
        packet["outcomes"] = [
            {"id": "O1", "value": 0.8, "source": bound_source("落差 0.8 dB")},
            {"id": "O2", "value": 0.05, "source": bound_source("落差 0.05 dB")},
        ]
        assessment, _ = pc.assess_experiment(self.state, packet)
        self.assertEqual(assessment["outcome_class"], "PREDICTION_HELD")

    def test_a_partial_submission_is_never_held(self):
        """P0-1: submitting only the favourable outcome is not 'all predictions held'."""
        packet = clone(self.observation)
        packet["outcomes"] = [packet["outcomes"][0]]
        assessment, diagnostics = pc.assess_experiment(self.state, packet)
        self.assertEqual(assessment["outcome_class"], "PARTIALLY_ASSESSED")
        missing = [entry for entry in assessment["predictions"]
                   if entry.get("reason") == "missing_observation"]
        self.assertEqual([entry["outcome_id"] for entry in missing], ["O2"])
        self.assertFalse(assessment["evidence_eligible"])
        self.assertIn("PC8", {d.rule for d in diagnostics})
        allowed, reasons = pc.evidence_transition_allowed(self.state, assessment)
        self.assertFalse(allowed)
        self.assertTrue(reasons)

    def test_a_duplicated_outcome_is_undecidable(self):
        packet = clone(self.observation)
        packet["outcomes"] = [packet["outcomes"][0], clone(packet["outcomes"][0]),
                              packet["outcomes"][1]]
        assessment, diagnostics = pc.assess_experiment(self.state, packet)
        entry = next(e for e in assessment["predictions"] if e["outcome_id"] == "O1")
        self.assertEqual(entry["reason"], "duplicate_observation")
        self.assertIn("PC2", {d.rule for d in diagnostics})
        self.assertNotIn(assessment["outcome_class"], ("PREDICTION_HELD",))

    def test_an_unfrozen_outcome_never_enters_the_verdict_set(self):
        packet = clone(self.observation)
        packet["outcomes"] = list(packet["outcomes"]) + [
            {"id": "O9", "value": 0.8, "source": bound_source("未冻结")}]
        assessment, _ = pc.assess_experiment(self.state, packet)
        self.assertEqual(assessment["unexpected_observations"], ["O9"])
        self.assertTrue(all(entry["outcome_id"] in ("O1", "O2")
                            for entry in assessment["predictions"]))
        self.assertFalse(assessment["evidence_eligible"])

    def test_the_frozen_set_is_the_decision_set(self):
        assessment, _ = pc.assess_experiment(self.state, self.observation)
        self.assertEqual(assessment["frozen_outcome_ids"], ["O1", "O2"])
        self.assertEqual([entry["outcome_id"] for entry in assessment["predictions"]],
                         ["O1", "O2"])

    def test_branch_mode_adjudicates_the_derived_branch(self):
        """P0-1: branch mode needs a frozen rule, and the rule — not the packet — selects."""
        state, packet = pc._branch_fixture()
        assessment, diagnostics = pc.assess_experiment(state, packet)
        self.assertEqual(assessment["mode"], "branch")
        self.assertEqual(assessment["outcome_class"], "PREDICTION_HELD")
        self.assertEqual(assessment["selected_outcome"], "O1")
        self.assertEqual(assessment["not_selected"], ["O2"])
        self.assertTrue(assessment["evidence_eligible"])
        self.assertEqual(diagnostics, [])

    def test_a_branch_declaration_without_a_frozen_rule_is_ignored(self):
        """The exploit: declare `observed_outcome` after seeing the numbers."""
        packet = clone(self.observation)
        packet["observed_outcome"] = "O1"
        packet["outcomes"] = [packet["outcomes"][0]]
        assessment, diagnostics = pc.assess_experiment(self.state, packet)
        self.assertEqual(assessment["mode"], "completeness")
        self.assertEqual(assessment["outcome_class"], "PARTIALLY_ASSESSED")
        self.assertFalse(assessment["evidence_eligible"])
        self.assertIn("PC10", {d.rule for d in diagnostics})

    def test_a_post_hoc_branch_rule_changes_the_freeze_digest(self):
        state, _ = pc._branch_fixture()
        experiment = state["experiments"][0]
        recorded = pc.freeze_digest(experiment)
        stripped = clone(state)
        del stripped["experiments"][0]["preregistration"]["branch_rule"]
        self.assertNotEqual(pc.freeze_digest(stripped["experiments"][0]), recorded)

    def test_an_old_freeze_without_a_branch_declaration_still_matches(self):
        """A project frozen before branch mode existed keeps reading clean."""
        state, _ = pc._fixture()
        experiment = state["experiments"][0]
        legacy = pc.freeze_digest(experiment, legacy=True)
        self.assertNotEqual(legacy, pc.freeze_digest(experiment))
        event = {
            "_schema": cg.SCHEMA_REVISION, "id": "REV1", "seq": 1, "kind": "prediction_freeze",
            "subject": "X1", "actor": "R8", "at_state_version": 5, "summary": "freeze X1",
            "trigger": {"kind": "preregistration_frozen", "ref": "X1"},
            "refs": {"experiments": ["X1"]}, "after": {"freeze_digest": legacy},
        }
        self.assertEqual(pc.check_freezes(state, [event]), [])
        branch_state, _ = pc._branch_fixture()
        self.assertTrue(pc.check_freezes(branch_state, [event]))

    def test_branch_criteria_must_be_mutually_exclusive(self):
        state, packet = pc._branch_fixture()
        state["experiments"][0]["preregistration"]["outcomes"][1]["criterion"][
            "expected_range"] = [0.0, 0.6]
        assessment, diagnostics = pc.assess_experiment(state, packet)
        self.assertEqual(assessment["mode"], "completeness")
        self.assertFalse(assessment["evidence_eligible"])
        self.assertTrue(any("互斥" in d.detail for d in diagnostics))
        exclusive, reason = pc.criteria_mutually_exclusive(
            {"kind": "quantitative", "quantity": "x", "expected_range": [0.0, 0.5], "tolerance": 0.0},
            {"kind": "quantitative", "quantity": "x", "expected_range": [0.5, 1.0], "tolerance": 0.0})
        self.assertFalse(exclusive, reason)

    def test_the_branch_set_must_partition_the_frozen_outcomes(self):
        state, packet = pc._branch_fixture()
        state["experiments"][0]["preregistration"]["branch_rule"]["branches"] = ["O1"]
        _, diagnostics = pc.assess_experiment(state, packet)
        self.assertTrue(any(d.rule == "PC10" and "完整划分" in d.detail for d in diagnostics))

    def test_a_branch_basis_outside_the_frozen_source_is_rejected(self):
        state, packet = pc._branch_fixture()
        packet["outcomes"][0]["source"]["location"] = "results/other.json"
        assessment, diagnostics = pc.assess_experiment(state, packet)
        self.assertEqual(assessment["outcome_class"], "UNTESTABLE")
        self.assertFalse(assessment["evidence_eligible"])
        self.assertTrue(any(d.rule == "PC10" for d in diagnostics))
        failed = {item["id"] for item in assessment["qualification"]["checks"]
                  if not item["passed"]}
        self.assertIn("PQ5", failed)

    def test_a_branch_declaration_that_conflicts_with_the_observation_is_rejected(self):
        state, packet = pc._branch_fixture()
        packet["observed_outcome"] = "O2"
        assessment, _ = pc.assess_experiment(state, packet)
        self.assertEqual(assessment["outcome_class"], "UNTESTABLE")
        self.assertEqual(assessment["branch_resolution"]["reason"], "branch_declaration_conflict")
        self.assertFalse(assessment["evidence_eligible"])

    def test_two_submitted_branches_cannot_both_be_observed(self):
        state, packet = pc._branch_fixture()
        packet["outcomes"] = [
            {"id": "O1", "value": 0.8, "source": bound_source("a")},
            {"id": "O2", "value": 0.05, "source": bound_source("b")},
        ]
        assessment, _ = pc.assess_experiment(state, packet)
        self.assertEqual(assessment["outcome_class"], "UNTESTABLE")
        self.assertEqual(assessment["branch_resolution"]["reason"], "branch_observation_count")
        self.assertFalse(assessment["evidence_eligible"])

    def test_an_observation_outside_every_branch_decides_nothing(self):
        state, packet = pc._branch_fixture()
        packet["outcomes"][0]["value"] = 0.35
        assessment, _ = pc.assess_experiment(state, packet)
        self.assertEqual(assessment["outcome_class"], "UNTESTABLE")
        self.assertEqual(assessment["branch_resolution"]["reason"], "no_branch_matched")

    def test_a_selected_branch_must_still_be_frozen(self):
        packet = clone(self.observation)
        packet["observed_outcome"] = "O9"
        assessment, diagnostics = pc.assess_experiment(self.state, packet)
        self.assertNotEqual(assessment["outcome_class"], "PREDICTION_HELD")
        self.assertIn("PC10", {d.rule for d in diagnostics})

    def test_an_invalid_execution_is_never_a_prediction_verdict(self):
        packet = clone(self.observation)
        packet["execution"]["validity"] = "INVALID"
        assessment, diagnostics = pc.assess_experiment(self.state, packet)
        self.assertEqual(assessment["outcome_class"], "INVALID_EXECUTION")
        self.assertIn("PC6", {d.rule for d in diagnostics})
        self.assertEqual(assessment["predictions"], [])

    def test_an_unknown_execution_still_compares_but_is_marked(self):
        """P0-2: the diagnostic comparison is kept, the scientific status is not."""
        packet = clone(self.observation)
        packet["execution"]["validity"] = "UNKNOWN"
        assessment, diagnostics = pc.assess_experiment(self.state, packet)
        self.assertNotEqual(assessment["outcome_class"], "INVALID_EXECUTION")
        self.assertEqual(assessment["evidence_class"], "DIAGNOSTIC_ONLY")
        self.assertFalse(assessment["evidence_eligible"])
        self.assertEqual(assessment["scientific_status"], "DIAGNOSTIC_ONLY")
        self.assertIn("PC7", {d.rule for d in diagnostics})
        allowed, reasons = pc.evidence_transition_allowed(self.state, assessment)
        self.assertFalse(allowed)
        self.assertTrue(any("UNKNOWN" in reason for reason in reasons), reasons)

    def test_incomplete_provenance_is_diagnostic_only(self):
        state = clone(self.state)
        state["experiments"][0]["status"] = "running"
        state["experiments"][0]["result_at_state_version"] = None
        assessment, diagnostics = pc.assess_experiment(state, self.observation)
        self.assertFalse(assessment["evidence_eligible"])
        self.assertTrue(assessment["provenance_gaps"])
        self.assertIn("PC7", {d.rule for d in diagnostics})

    def test_a_time_leak_blocks_the_transition(self):
        state = clone(self.state)
        state["experiments"][0]["preregistration"]["frozen_at_state_version"] = 99
        assessment, _ = pc.assess_experiment(state, self.observation)
        allowed, reasons = pc.evidence_transition_allowed(state, assessment)
        self.assertFalse(allowed)
        self.assertTrue(any("时间" in reason or "泄漏" in reason for reason in reasons))

    def test_only_a_qualified_assessment_may_inform_a_transition(self):
        complete, _ = pc.assess_experiment(self.state, self.observation)
        allowed, reasons = pc.evidence_transition_allowed(self.state, complete)
        self.assertTrue(allowed, reasons)
        self.assertEqual(reasons, [])
        partial_packet = clone(self.observation)
        partial_packet["outcomes"] = [partial_packet["outcomes"][0]]
        partial, _ = pc.assess_experiment(self.state, partial_packet)
        blocked, blockers = pc.evidence_transition_allowed(self.state, partial)
        self.assertFalse(blocked)
        self.assertTrue(blockers)
        invalid_packet = clone(self.observation)
        invalid_packet["execution"]["validity"] = "INVALID"
        invalid, _ = pc.assess_experiment(self.state, invalid_packet)
        self.assertFalse(pc.evidence_transition_allowed(self.state, invalid)[0])

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
        self.assertEqual(assessment["unexpected_observations"], ["O9"])
        self.assertIn("PC2", {d.rule for d in diagnostics})

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
# The Evidence Qualification Gate
# ---------------------------------------------------------------------------

class TestEvidenceQualificationGate(unittest.TestCase):
    """P0-2: one entry point decides what a comparison is worth, and it fails closed.

    Each test mutates the packet or the state and then reads the *public* result:
    `assess_experiment` and `evidence_transition_allowed`. None of them asserts on a private
    helper, and none of them accepts "a diagnostic was reported" as a substitute for
    "the evidence is not qualified".
    """

    def setUp(self):
        self.state, self.observation = pc._fixture()
        self.complete = clone(self.observation)
        self.complete["outcomes"] = [
            {"id": "O1", "value": 0.8, "source": bound_source("落差 0.8 dB")},
            {"id": "O2", "value": 0.05, "source": bound_source("落差 0.05 dB")},
        ]

    def _evaluate(self, packet=None, state=None):
        state = state or self.state
        assessment, _ = pc.assess_experiment(state, packet or self.complete)
        allowed, reasons = pc.evidence_transition_allowed(state, assessment)
        return assessment, allowed, reasons

    def test_a_clean_comparison_is_qualified(self):
        assessment, allowed, reasons = self._evaluate()
        self.assertTrue(assessment["evidence_eligible"])
        self.assertTrue(allowed, reasons)
        self.assertEqual(assessment["evidence_class"], "QUALIFIED_EVIDENCE")
        self.assertEqual(assessment["scientific_status"], "MAY_INFORM_TRANSITION")
        self.assertEqual(assessment["provenance_gaps"], [])
        self.assertEqual([item["id"] for item in assessment["qualification"]["checks"]],
                         list(pc.QUALIFICATION_CHECK_IDS))

    def test_every_check_is_recorded_with_its_verdict(self):
        assessment, _, _ = self._evaluate()
        checks = assessment["qualification"]["checks"]
        self.assertTrue(all(item["passed"] for item in checks))
        self.assertEqual(assessment["qualification"]["schema"], pc.SCHEMA_QUALIFICATION)
        self.assertEqual(assessment["qualification"]["packet_digest"],
                         assessment["packet_digest"])

    def test_a_missing_source_cannot_qualify_evidence(self):
        packet = clone(self.complete)
        del packet["outcomes"][0]["source"]
        assessment, allowed, reasons = self._evaluate(packet)
        self.assertFalse(assessment["evidence_eligible"])
        self.assertFalse(allowed)
        self.assertTrue(reasons)
        failed = {item["id"] for item in assessment["qualification"]["checks"]
                  if not item["passed"]}
        self.assertIn("PQ4", failed)
        self.assertEqual(assessment["outcome_class"], "UNTESTABLE")
        self.assertEqual(assessment["diagnostic_outcome_class"], "PREDICTION_HELD")

    def test_a_digest_mismatch_cannot_qualify_evidence(self):
        packet = clone(self.complete)
        packet["outcomes"][0]["source"]["digest"] = "0" * 64
        assessment, allowed, _ = self._evaluate(packet)
        self.assertFalse(assessment["evidence_eligible"])
        self.assertFalse(allowed)
        self.assertIn("PQ4", {item["id"] for item in assessment["qualification"]["checks"]
                              if not item["passed"]})

    def test_source_content_edited_after_the_fact_is_detected(self):
        packet = clone(self.complete)
        packet["outcomes"][0]["source"]["content"] = "落差 0.8 dB（改过）"
        assessment, allowed, _ = self._evaluate(packet)
        self.assertFalse(assessment["evidence_eligible"])
        self.assertFalse(allowed)

    def test_an_incomplete_source_cannot_qualify_evidence(self):
        for field in ("kind", "location", "content", "digest"):
            packet = clone(self.complete)
            packet["outcomes"][0]["source"][field] = ""
            assessment, allowed, _ = self._evaluate(packet)
            self.assertFalse(assessment["evidence_eligible"], field)
            self.assertFalse(allowed, field)

    def test_a_malformed_packet_fails_closed_without_crashing(self):
        """Found in review: a non-object packet produced `outcome_class: null`."""
        for garbage in ([], "not a packet", 42, None, {}, {"experiment_id": "X1"}):
            assessment, _ = pc.assess_experiment(self.state, garbage)
            self.assertIn(assessment["outcome_class"], pc.OUTCOME_CLASSES, repr(garbage))
            self.assertFalse(assessment["evidence_eligible"], repr(garbage))
            self.assertIn(assessment["evidence_class"], pc.EVIDENCE_CLASSES, repr(garbage))
            allowed, reasons = pc.evidence_transition_allowed(self.state, assessment)
            self.assertFalse(allowed, repr(garbage))
            self.assertTrue(reasons, repr(garbage))
            block = pc.qualify_evidence(self.state, garbage)
            self.assertFalse(block["eligible"], repr(garbage))

    def test_unknown_validity_keeps_the_comparison_but_not_the_evidence(self):
        packet = clone(self.complete)
        packet["execution"]["validity"] = "UNKNOWN"
        assessment, allowed, reasons = self._evaluate(packet)
        self.assertFalse(allowed)
        self.assertEqual(assessment["evidence_class"], "DIAGNOSTIC_ONLY")
        self.assertEqual(assessment["scientific_status"], "DIAGNOSTIC_ONLY")
        self.assertEqual(assessment["diagnostic_outcome_class"], "PREDICTION_HELD")
        self.assertNotIn(assessment["outcome_class"], pc.WORLD_CLAIMING_CLASSES)
        self.assertTrue(any("UNKNOWN" in reason for reason in reasons), reasons)
        self.assertIn("PQ1", {item["id"] for item in assessment["qualification"]["checks"]
                              if not item["passed"]})

    def test_invalid_execution_is_never_qualified(self):
        packet = clone(self.complete)
        packet["execution"]["validity"] = "INVALID"
        assessment, allowed, _ = self._evaluate(packet)
        self.assertFalse(allowed)
        self.assertEqual(assessment["outcome_class"], "INVALID_EXECUTION")
        self.assertEqual(assessment["evidence_class"], "INSUFFICIENT_PROVENANCE")
        self.assertEqual(assessment["scientific_status"], "NO_INFERENCE")
        self.assertEqual(assessment["predictions"], [])

    def test_an_unfinished_experiment_is_diagnostic_only(self):
        state = clone(self.state)
        state["experiments"][0]["status"] = "running"
        state["experiments"][0]["result_at_state_version"] = None
        assessment, allowed, _ = self._evaluate(state=state)
        self.assertFalse(allowed)
        self.assertEqual(assessment["evidence_class"], "DIAGNOSTIC_ONLY")
        self.assertIn("PQ7", {item["id"] for item in assessment["qualification"]["checks"]
                              if not item["passed"]})

    def test_a_time_leak_is_blocked_and_named(self):
        state = clone(self.state)
        state["experiments"][0]["preregistration"]["frozen_at_state_version"] = 99
        assessment, allowed, reasons = self._evaluate(state=state)
        self.assertFalse(allowed)
        self.assertTrue(any("时间" in reason or "泄漏" in reason for reason in reasons), reasons)
        self.assertFalse(assessment["evidence_eligible"])

    def test_a_tamper_and_a_time_leak_are_both_reported(self):
        state = clone(self.state)
        state["experiments"][0]["preregistration"]["frozen_at_state_version"] = 99
        state["experiments"][0]["preregistration"]["amended"] = [
            {"at_state_version": 6, "reason": "看到结果之后调整判据"}]
        assessment, allowed, _ = self._evaluate(state=state)
        self.assertFalse(allowed)
        check = next(item for item in assessment["qualification"]["checks"]
                     if item["id"] == "PQ8")
        self.assertEqual(check["severity"], pc.BLOCKING)
        self.assertTrue(any("泄漏" in item for item in check["failures"]), check["failures"])
        self.assertTrue(any("事后" in item or "后修订" in item for item in check["failures"]),
                        check["failures"])

    def test_a_post_hoc_amendment_blocks_the_gate(self):
        state = clone(self.state)
        state["experiments"][0]["preregistration"]["amended"] = [
            {"at_state_version": 6, "reason": "看到结果之后调整判据"}]
        assessment, allowed, _ = self._evaluate(state=state)
        self.assertFalse(allowed)
        self.assertFalse(assessment["evidence_eligible"])

    def test_the_revision_log_participates_in_the_gate(self):
        """A frozen criterion rewritten after the result is not evidence, log or no log."""
        state, _ = pc._fixture()
        freeze = {
            "_schema": cg.SCHEMA_REVISION, "id": "REV1", "seq": 1, "kind": "prediction_freeze",
            "subject": "X1", "actor": "R8", "at_state_version": 5, "summary": "freeze X1",
            "trigger": {"kind": "preregistration_frozen", "ref": "X1"},
            "refs": {"experiments": ["X1"]},
            "after": {"freeze_digest": pc.freeze_digest(state["experiments"][0])},
        }
        clean, _ = pc.assess_experiment(state, self.complete, [freeze])
        self.assertTrue(clean["evidence_eligible"])
        rewritten = clone(state)
        rewritten["experiments"][0]["preregistration"]["outcomes"][0]["criterion"][
            "expected_range"] = [0.79, 3.0]
        tampered, _ = pc.assess_experiment(rewritten, self.complete, [freeze])
        self.assertFalse(tampered["evidence_eligible"])
        self.assertIn("PQ8", {item["id"] for item in tampered["qualification"]["checks"]
                              if not item["passed"]})

    def test_re_freezing_after_the_result_cannot_escape_the_gate(self):
        """A version bump plus a retro-fitted branch rule is still a post-hoc rewrite."""
        state, _ = pc._fixture()
        freeze = {
            "_schema": cg.SCHEMA_REVISION, "id": "REV1", "seq": 1, "kind": "prediction_freeze",
            "subject": "X1", "actor": "R8", "at_state_version": 5, "summary": "freeze X1",
            "trigger": {"kind": "preregistration_frozen", "ref": "X1"},
            "refs": {"experiments": ["X1"]},
            "after": {"freeze_digest": pc.freeze_digest(state["experiments"][0])},
        }
        refrozen = clone(state)
        preregistration = refrozen["experiments"][0]["preregistration"]
        preregistration["frozen_at_state_version"] = 6
        preregistration["outcome_mode"] = "branch"
        preregistration["branch_rule"] = {
            "selector": {"kind": "result", "location": "results/A/X1/summary.json"},
            "quantity": "落差（dB）", "branches": ["O1", "O2"]}
        packet = clone(self.complete)
        packet["observed_outcome"] = "O1"
        packet["outcomes"] = [packet["outcomes"][0]]
        assessment, diagnostics = pc.assess_experiment(refrozen, packet, [freeze])
        self.assertFalse(assessment["evidence_eligible"])
        self.assertFalse(pc.evidence_transition_allowed(refrozen, assessment)[0])
        self.assertNotEqual(assessment["outcome_class"], "PREDICTION_HELD")
        failed = {item["id"] for item in assessment["qualification"]["checks"]
                  if not item["passed"]}
        self.assertTrue({"PQ8"} & failed, sorted(failed))
        self.assertTrue(any(d.rule in ("PC4", "PC5") for d in pc.check_freezes(refrozen, [freeze])))

    def test_a_hand_written_assessment_grants_nothing(self):
        """No caller may re-derive eligibility from a subset of the fields."""
        assessment, _, _ = self._evaluate()
        forged = {k: v for k, v in assessment.items() if k != "qualification"}
        forged["evidence_eligible"] = True
        forged["evidence_class"] = "QUALIFIED_EVIDENCE"
        forged["scientific_status"] = "MAY_INFORM_TRANSITION"
        allowed, reasons = pc.evidence_transition_allowed(self.state, forged)
        self.assertFalse(allowed)
        self.assertTrue(reasons)

    def test_a_block_from_another_packet_is_refused(self):
        assessment, _, _ = self._evaluate()
        other = clone(self.complete)
        other["outcomes"][0]["value"] = 0.1
        mismatched = dict(assessment, packet_digest=cg.digest_of(other))
        allowed, _ = pc.evidence_transition_allowed(self.state, mismatched)
        self.assertFalse(allowed)

    def test_a_state_that_changed_after_the_block_blocks_the_transition(self):
        assessment, allowed, _ = self._evaluate()
        self.assertTrue(allowed)
        state = clone(self.state)
        state["experiments"][0]["status"] = "running"
        allowed_after, reasons = pc.evidence_transition_allowed(state, assessment)
        self.assertFalse(allowed_after)
        self.assertTrue(reasons)

    def test_the_gate_is_the_only_authority_for_the_assessment_fields(self):
        """Every mutation must move `qualification`, `evidence_class` and the gate together."""
        mutations = []
        packet = clone(self.complete)
        del packet["outcomes"][0]["source"]
        mutations.append(("missing source", packet, None))
        packet = clone(self.complete)
        packet["execution"]["validity"] = "UNKNOWN"
        mutations.append(("unknown validity", packet, None))
        packet = clone(self.complete)
        packet["outcomes"] = [packet["outcomes"][0]]
        mutations.append(("partial submission", packet, None))
        packet = clone(self.complete)
        packet["outcomes"] = list(packet["outcomes"]) + [
            {"id": "O9", "value": 0.8, "source": bound_source("未冻结")}]
        mutations.append(("unfrozen outcome", packet, None))
        for label, mutated, _ in mutations:
            state = self.state
            assessment, _ = pc.assess_experiment(state, mutated)
            direct = pc.qualify_evidence(state, mutated, assessment)
            self.assertEqual(assessment["qualification"], direct, label)
            self.assertEqual(assessment["evidence_class"], direct["evidence_class"], label)
            self.assertEqual(assessment["evidence_eligible"], direct["eligible"], label)
            self.assertEqual(assessment["scientific_status"], direct["scientific_status"], label)
            self.assertFalse(direct["eligible"], label)
            self.assertFalse(pc.evidence_transition_allowed(state, assessment)[0], label)

    def test_the_standalone_gate_is_as_strict_as_the_integrated_one(self):
        packet = clone(self.complete)
        packet["outcomes"] = [packet["outcomes"][0]]
        standalone = pc.qualify_evidence(self.state, packet)
        integrated, _ = pc.assess_experiment(self.state, packet)
        self.assertFalse(standalone["eligible"])
        self.assertEqual([item["id"] for item in standalone["failures"]],
                         [item["id"] for item in integrated["qualification"]["failures"]])
        self.assertEqual(standalone, integrated["qualification"])
        clean = pc.qualify_evidence(self.state, self.complete)
        self.assertTrue(clean["eligible"])

    def test_every_reported_evidence_class_is_in_the_frozen_vocabulary(self):
        """`evidence_class` is a frozen three-value vocabulary, not a free-text verdict."""
        packets = []
        packet = clone(self.complete)
        del packet["outcomes"][0]["source"]
        packets.append(packet)
        packet = clone(self.complete)
        packet["execution"]["validity"] = "UNKNOWN"
        packets.append(packet)
        packet = clone(self.complete)
        packet["execution"]["validity"] = "INVALID"
        packets.append(packet)
        packet = clone(self.complete)
        packet["outcomes"] = [packet["outcomes"][0]]
        packets.append(packet)
        packets.append([])
        unfinished = clone(self.state)
        unfinished["experiments"][0]["status"] = "running"
        for index, mutated in enumerate(packets):
            assessment, _ = pc.assess_experiment(
                unfinished if index == len(packets) - 1 else self.state, mutated)
            self.assertIn(assessment["evidence_class"], pc.EVIDENCE_CLASSES)
            self.assertIn(assessment["scientific_status"], pc.SCIENTIFIC_STATUSES)
            self.assertIn(assessment["outcome_class"], pc.OUTCOME_CLASSES)
        self.assertIn(pc.qualify_evidence(self.state, self.complete)["evidence_class"],
                      pc.EVIDENCE_CLASSES)

    def test_a_partial_submission_is_reported_as_an_incomplete_decision_set(self):
        packet = clone(self.complete)
        packet["outcomes"] = [packet["outcomes"][0]]
        assessment, allowed, _ = self._evaluate(packet)
        self.assertFalse(allowed)
        self.assertIn("PQ3", {item["id"] for item in assessment["qualification"]["checks"]
                              if not item["passed"]})
        self.assertEqual(assessment["outcome_class"], "PARTIALLY_ASSESSED")


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
            "discrimination_rule": {"statistic": "difference_of_means",
                                    "min_separation": 0.2},
        }

    def test_a_real_gap_is_distinguishable(self):
        verdict, _ = pc.distinguishability(self.state, self.competition, self.mechanisms)
        self.assertEqual(verdict["verdict"], "DISTINGUISHABLE")
        self.assertEqual(verdict["reason"], "discrimination_rule_satisfied")
        self.assertTrue(verdict["has_distinguishing_power"])
        self.assertEqual(verdict["witness_pair"]["left_ref"], "X2:O1")

    def test_without_a_pre_declared_rule_the_pair_is_only_conditional(self):
        """P0-3: conflicting ranges alone do not fix which mechanism won."""
        blind = clone(self.competition)
        blind.pop("discrimination_rule")
        verdict, diagnostics = pc.distinguishability(self.state, blind, self.mechanisms)
        self.assertEqual(verdict["verdict"], "CONDITIONALLY_DISTINGUISHABLE")
        self.assertEqual(verdict["reason"], "no_discrimination_rule")
        self.assertFalse(verdict["has_distinguishing_power"])
        self.assertIn("PC6", {d.rule for d in diagnostics})

    def test_different_observables_are_not_a_competition(self):
        state = clone(self.state)
        state["experiments"][1]["preregistration"]["outcomes"][2]["criterion"][
            "quantity"] = "另一个指标（ms）"
        verdict, _ = pc.distinguishability(state, self.competition, self.mechanisms)
        self.assertEqual(verdict["verdict"], "INSUFFICIENT_INFORMATION")
        self.assertEqual(verdict["reason"], "different_observables")

    def test_different_measurement_bases_are_not_comparable(self):
        state = clone(self.state)
        state["experiments"][1]["preregistration"]["outcomes"][0]["criterion"][
            "measurement"] = "single centre"
        state["experiments"][1]["preregistration"]["outcomes"][2]["criterion"][
            "measurement"] = "mean over centres"
        verdict, _ = pc.distinguishability(state, self.competition, self.mechanisms)
        self.assertEqual(verdict["reason"], "different_measurement")

    def test_overlapping_intervals_have_no_separating_power(self):
        state = clone(self.state)
        state["experiments"][1]["preregistration"]["outcomes"][2]["criterion"][
            "expected_range"] = [-0.6, 0.4]
        verdict, _ = pc.distinguishability(state, self.competition, self.mechanisms)
        self.assertEqual(verdict["verdict"], "NOT_DISTINGUISHABLE")
        self.assertEqual(verdict["reason"], "overlapping_intervals")

    def test_statistical_uncertainty_can_swallow_the_gap(self):
        state = clone(self.state)
        state["experiments"][1]["preregistration"]["outcomes"][0]["criterion"].update(
            {"noise": 4.0, "sample_size": 4})
        verdict, diagnostics = pc.distinguishability(state, self.competition, self.mechanisms)
        self.assertEqual(verdict["verdict"], "NOT_DISTINGUISHABLE")
        self.assertEqual(verdict["reason"], "within_uncertainty")
        self.assertIn("PC6", {d.rule for d in diagnostics})

    def test_a_gap_below_the_declared_resolution_is_not_distinguishable(self):
        strict = dict(self.competition,
                      discrimination_rule={"statistic": "difference_of_means",
                                           "min_separation": 0.9})
        verdict, _ = pc.distinguishability(self.state, strict, self.mechanisms)
        self.assertEqual(verdict["verdict"], "NOT_DISTINGUISHABLE")
        self.assertEqual(verdict["reason"], "below_declared_min_separation")

    def test_a_finished_experiment_is_not_an_actionable_intervention(self):
        state = clone(self.state)
        state["experiments"][1]["status"] = "done"
        verdict, _ = pc.distinguishability(state, self.competition, self.mechanisms)
        self.assertEqual(verdict["verdict"], "INSUFFICIENT_INFORMATION")
        self.assertEqual(verdict["reason"], "intervention_not_actionable")

    def test_prose_and_self_ratings_do_not_decide_distinguishability(self):
        verbose = dict(self.competition, note="两个机制语义上高度相似",
                       similarity=0.91, confidence=0.99)
        verdict, _ = pc.distinguishability(self.state, verbose, self.mechanisms)
        self.assertEqual(verdict["verdict"], "DISTINGUISHABLE")

    def test_every_pair_must_separate_when_there_are_three_mechanisms(self):
        three = {"id": "CP3", "status": "open", "mechanisms": ["M1", "M2", "M3"],
                 "conflicting_predictions": ["X2:O1", "X2:O3", "X2:O2"],
                 "predictions": [{"mechanism": "M1", "ref": "X2:O1"},
                                 {"mechanism": "M2", "ref": "X2:O3"},
                                 {"mechanism": "M3", "ref": "X2:O2"}],
                 "discriminating_intervention": "X2",
                 "decision_impact": "method_decision_differs",
                 "discrimination_rule": {"statistic": "difference_of_means",
                                         "min_separation": 0.2}}
        mechanisms = [{"id": "M1", "structure": {"pending_predictions": ["X2:O1"]}},
                      {"id": "M2", "structure": {"pending_predictions": ["X2:O3"]}},
                      {"id": "M3", "structure": {"pending_predictions": ["X2:O2"]}}]
        verdict, _ = pc.distinguishability(self.state, three, mechanisms)
        self.assertEqual(verdict["verdict"], "NOT_DISTINGUISHABLE")
        self.assertEqual(verdict["reason"], "identical_criteria")
        self.assertEqual(len(verdict["pairs"]), 3)

    def test_a_rewording_is_not_a_competing_prediction(self):
        equivalent = clone(self.competition)
        equivalent["conflicting_predictions"] = ["X2:O1", "X2:O2"]
        equivalent["predictions"] = [{"mechanism": "M1", "ref": "X2:O1"},
                                     {"mechanism": "M2", "ref": "X2:O2"}]
        verdict, diagnostics = pc.distinguishability(self.state, equivalent, self.mechanisms)
        self.assertEqual(verdict["verdict"], "NOT_DISTINGUISHABLE")
        self.assertEqual(verdict["reason"], "identical_criteria")
        self.assertIn("PC6", {d.rule for d in diagnostics})

    def test_without_an_intervention_the_competition_is_not_decidable(self):
        blind = clone(self.competition)
        blind["discriminating_intervention"] = "TBD"
        verdict, _ = pc.distinguishability(self.state, blind, self.mechanisms)
        self.assertEqual(verdict["verdict"], "INSUFFICIENT_INFORMATION")
        self.assertEqual(verdict["reason"], "no_intervention")

    def test_without_a_prediction_gap_there_is_no_competition(self):
        flat = clone(self.competition)
        flat["conflicting_predictions"] = []
        flat["predictions"] = []
        verdict, _ = pc.distinguishability(self.state, flat, self.mechanisms)
        self.assertEqual(verdict["verdict"], "INSUFFICIENT_INFORMATION")
        self.assertEqual(verdict["reason"], "no_prediction_gap")

    def test_unattributed_predictions_are_insufficient_structure(self):
        unowned = clone(self.competition)
        unowned.pop("predictions")
        verdict, diagnostics = pc.distinguishability(self.state, unowned, None)
        self.assertEqual(verdict["verdict"], "INSUFFICIENT_INFORMATION")
        self.assertEqual(verdict["reason"], "no_ownership")
        self.assertTrue(any("归属" in d.detail for d in diagnostics))

    def test_a_single_mechanism_is_insufficient(self):
        solo = clone(self.competition)
        solo["mechanisms"] = ["M1"]
        verdict, _ = pc.distinguishability(self.state, solo, self.mechanisms)
        self.assertEqual(verdict["verdict"], "INSUFFICIENT_INFORMATION")
        self.assertEqual(verdict["reason"], "insufficient_mechanisms")

    def test_a_prediction_on_another_experiment_cannot_be_separated(self):
        elsewhere = clone(self.competition)
        elsewhere["predictions"] = [{"mechanism": "M1", "ref": "X2:O1"},
                                    {"mechanism": "M2", "ref": "X1:O2"}]
        elsewhere["conflicting_predictions"] = ["X2:O1", "X1:O2"]
        verdict, _ = pc.distinguishability(self.state, elsewhere, self.mechanisms)
        self.assertEqual(verdict["verdict"], "INSUFFICIENT_INFORMATION")
        self.assertEqual(verdict["reason"], "predictions_on_other_experiments")

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
            "discrimination_rule": {"statistic": "difference_of_means",
                                    "min_separation": 0.2},
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

    def _certified(self, **overrides):
        """A card whose every certification ingredient is canonical and verifiable.

        The synthesis is deliberate: the point of the P1 gate is that this is what it takes.
        The observation packet is a real `prediction-observation@1` packet for `X1`, the
        R9.O receipt is a real `evidence-result@1` + analysis pair in the supporting
        direction, and the audit is validated by its owning module.
        """
        packet = clone(self.state["experiments"][0]["preregistration"]["outcomes"])
        observation_packet = {
            "schema": pc.SCHEMA_OBSERVATION, "experiment_id": "X1",
            "execution": {"status": "completed", "validity": "VALID"},
            "outcomes": [
                {"id": "O1", "value": 0.8, "source": bound_source("落差 0.8 dB")},
                {"id": "O2", "value": 0.05, "source": bound_source("落差 0.05 dB")},
            ],
        }
        self.assertEqual(len(packet), 2)
        state = clone(self.state)
        state["evidence"][0]["supports"] = ["C1"]
        state["assurance"] = [{
            "id": "A1", "target": "H1", "attack_type": "structural-equivalence",
            "verification_tier": "T1", "kill_condition": "若与 LIT1 结构等价则杀死",
            "discriminating_test": "X2",
            "audit_ref": ".research-idea-pipeline/routes/A/assurance/structural-equivalence/"
                         "H1.json"}]
        content = "落差 0.8 dB"
        state["experiments"][0]["outcome_analysis"] = {
            "packet": {
                "schema": "evidence-result@1", "experiment_id": "X1",
                "experiment_digest": "sha256:x", "execution_status": "completed",
                "result_summary": content,
                "sources": [{"id": "S1", "kind": "result",
                             "location": "results/A/X1/summary.json",
                             "content": content, "digest": eo.digest(content)}],
                "observations": [{"id": "OBS1", "statement": content, "scope": "数据集 A",
                                  "source_ids": ["S1"]}],
            },
            "analysis": {
                "schema": "evidence-outcome-analysis@1", "id": "AN1", "experiment_id": "X1",
                "verification_tier": "T2", "outcome": "POSITIVE_EVIDENCE",
                "claim_updates": [{"id": "C1", "direction": "positive", "identification": "PASS",
                                   "new_status": "SUPPORTED", "evidence": ["OBS1"],
                                   "scope": "数据集 A"}],
            },
            "audit": None,
        }
        card = clone(self.card)
        card["declared_class"] = "evidence_supported_insight"
        card["discriminating_intervention"] = "X1"
        card["refs"] = {"claims": ["C1"], "hypotheses": ["H1"], "evidence": ["E1"],
                        "experiments": ["X1"]}
        card["novel_prediction"] = {
            "ref": "X1:O1", "statement": "落差 ≥ 0.5 dB", "experiment_ref": "X1",
            "observation": observation_packet,
            "observation_digest": cg.digest_of(observation_packet)}
        import structural_equivalence_check as sec
        artifact = sec._selftest_artifact()
        audits = {"A1": {"artifact": artifact, "verdict": artifact.get("verdict"),
                         "candidate": artifact.get("candidate"), "source": "<synthetic>",
                         "violations": []}}
        for key, value in overrides.items():
            target = {"state": state, "card": card, "audits": audits}[key]
            target.update(value)
        return card, state, audits

    def test_a_fully_bound_card_is_certified(self):
        card, state, audits = self._certified()
        derived, reasons = pc.classify_insight(card, state, audits)
        self.assertEqual(derived, "evidence_supported_insight")
        self.assertEqual(pc.insight_card_errors(card, state, audits), [])
        self.assertTrue(reasons["structural_equivalence_audit"])

    def test_the_audit_result_must_be_known(self):
        """P1: 'an audit exists' is not 'the audit found a structural delta'."""
        card, state, _ = self._certified()
        derived, _ = pc.classify_insight(card, state)
        self.assertNotEqual(derived, "evidence_supported_insight")

    def test_the_audit_result_must_support_the_claim(self):
        card, state, audits = self._certified()
        audits["A1"]["artifact"] = {**audits["A1"]["artifact"], "verdict": "reframing-only"}
        derived, _ = pc.classify_insight(card, state, audits)
        self.assertNotEqual(derived, "evidence_supported_insight")

    def test_the_audit_must_apply_to_the_referenced_candidate(self):
        card, state, audits = self._certified()
        audits["A1"]["artifact"] = {**audits["A1"]["artifact"], "candidate": "H9"}
        derived, _ = pc.classify_insight(card, state, audits)
        self.assertNotEqual(derived, "evidence_supported_insight")

    def test_the_prediction_must_have_a_qualified_adjudication(self):
        card, state, audits = self._certified()
        del card["novel_prediction"]["observation_digest"]
        derived, _ = pc.classify_insight(card, state, audits)
        self.assertNotEqual(derived, "evidence_supported_insight")

    def test_an_unobserved_prediction_cannot_be_certified(self):
        card, state, audits = self._certified()
        card["novel_prediction"]["observation"]["outcomes"] = [
            card["novel_prediction"]["observation"]["outcomes"][0]]
        card["novel_prediction"]["observation_digest"] = cg.digest_of(
            card["novel_prediction"]["observation"])
        derived, _ = pc.classify_insight(card, state, audits)
        self.assertNotEqual(derived, "evidence_supported_insight")

    def test_a_failing_prediction_cannot_support_the_insight(self):
        card, state, audits = self._certified()
        card["novel_prediction"]["observation"]["outcomes"][0]["value"] = 9.0
        card["novel_prediction"]["observation"]["outcomes"][0]["source"] = bound_source("落差 9 dB")
        card["novel_prediction"]["observation_digest"] = cg.digest_of(
            card["novel_prediction"]["observation"])
        derived, _ = pc.classify_insight(card, state, audits)
        self.assertNotEqual(derived, "evidence_supported_insight")

    def test_an_observation_packet_for_another_experiment_is_rejected(self):
        card, state, audits = self._certified()
        card["novel_prediction"]["observation"]["experiment_id"] = "X2"
        card["novel_prediction"]["observation_digest"] = cg.digest_of(
            card["novel_prediction"]["observation"])
        derived, reasons = pc.classify_insight(card, state, audits)
        self.assertNotEqual(derived, "evidence_supported_insight")
        self.assertTrue(any("experiment_id" in item
                            for item in reasons["certification"]["failures"]))

    def test_certification_requires_an_r9o_receipt(self):
        card, state, audits = self._certified()
        state["experiments"][0]["outcome_analysis"] = None
        derived, _ = pc.classify_insight(card, state, audits)
        self.assertNotEqual(derived, "evidence_supported_insight")

    def test_an_r9o_receipt_in_the_opposite_direction_is_rejected(self):
        card, state, audits = self._certified()
        state["experiments"][0]["outcome_analysis"]["analysis"]["outcome"] = "NEGATIVE_EVIDENCE"
        derived, _ = pc.classify_insight(card, state, audits)
        self.assertNotEqual(derived, "evidence_supported_insight")

    def test_an_r9o_receipt_below_t2_cannot_upgrade_the_insight(self):
        card, state, audits = self._certified()
        state["experiments"][0]["outcome_analysis"]["analysis"]["verification_tier"] = "T1"
        derived, _ = pc.classify_insight(card, state, audits)
        self.assertNotEqual(derived, "evidence_supported_insight")

    def test_t2_evidence_from_the_same_experiment_but_another_prediction(self):
        """Cross-prediction borrowing: same experiment is not the same prediction."""
        card, state, audits = self._certified()
        state["evidence"][0]["prediction_ref"] = "X1:O2"
        derived, reasons = pc.classify_insight(card, state, audits)
        self.assertNotEqual(derived, "evidence_supported_insight")
        self.assertTrue(any("不能互相借用" in item
                            for item in reasons["certification"]["failures"]))

    def test_two_cards_on_one_experiment_are_checked_separately(self):
        """Two cards sharing an experiment: each must bind its *own* held prediction."""
        first, state, audits = self._certified()
        second = clone(first)
        second["id"] = "IC2"
        second["novel_prediction"] = {**clone(first["novel_prediction"]), "ref": "X1:O2",
                                      "statement": "落差 < 0.1 dB"}
        outcomes = second["novel_prediction"]["observation"]["outcomes"]
        outcomes[1] = {"id": "O2", "value": 0.5, "source": bound_source("落差 0.5 dB")}
        second["novel_prediction"]["observation_digest"] = cg.digest_of(
            second["novel_prediction"]["observation"])
        derived_first, _ = pc.classify_insight(first, state, audits)
        derived_second, second_reasons = pc.classify_insight(second, state, audits)
        self.assertEqual(derived_first, "evidence_supported_insight")
        self.assertNotEqual(derived_second, "evidence_supported_insight")
        self.assertTrue(any("IC3" in item
                            for item in second_reasons["certification"]["failures"]))

    def test_a_contradicted_claim_cannot_back_a_certified_insight(self):
        card, state, audits = self._certified()
        state["claims"][0]["status"] = "contradicted"
        derived, _ = pc.classify_insight(card, state, audits)
        self.assertNotEqual(derived, "evidence_supported_insight")

    def test_invalidated_evidence_downgrades_a_certified_card(self):
        """Evidence retracted after certification must push the card back down."""
        card, state, audits = self._certified()
        self.assertEqual(pc.classify_insight(card, state, audits)[0],
                         "evidence_supported_insight")
        state["evidence"][0]["validity"]["status"] = "invalid"
        state["evidence"][0]["validity"]["reason"] = "上游实验被撤销"
        derived, _ = pc.classify_insight(card, state, audits)
        self.assertNotEqual(derived, "evidence_supported_insight")

    def test_legacy_cards_without_fine_grained_refs_keep_the_lower_class(self):
        """No guessing: missing provenance is reported, never reconstructed."""
        card, state, audits = self._certified()
        card["declared_class"] = "predictive_insight_candidate"
        card["refs"] = {"claims": ["C1"], "hypotheses": ["H1"]}
        card["novel_prediction"] = {"ref": "X2:O1", "statement": "解耦后落差下降 ≥ 0.5 dB"}
        card["discriminating_intervention"] = "X2"
        derived, reasons = pc.classify_insight(card, state, audits)
        self.assertEqual(derived, "predictive_insight_candidate")
        self.assertFalse(reasons["certification"]["attempted"])
        self.assertEqual([d.rule for d in pc.insight_card_errors(card, state, audits)], [])

    def test_evidence_outside_the_boundary_cannot_support_the_card(self):
        card, state, audits = self._certified()
        state["evidence"][0]["scope"] = "数据集 Z"
        derived, _ = pc.classify_insight(card, state, audits)
        self.assertNotEqual(derived, "evidence_supported_insight")

    def test_evidence_must_be_bound_to_the_prediction_experiment(self):
        card, state, audits = self._certified()
        state["evidence"][0]["depends_on"] = []
        derived, _ = pc.classify_insight(card, state, audits)
        self.assertNotEqual(derived, "evidence_supported_insight")

    def test_evidence_that_contradicts_the_claim_is_not_support(self):
        card, state, audits = self._certified()
        state["evidence"][0]["supports"] = []
        state["evidence"][0]["contradicts"] = ["C1"]
        derived, reasons = pc.classify_insight(card, state, audits)
        self.assertNotEqual(derived, "evidence_supported_insight")
        self.assertTrue(any("方向" in item or "supports" in item
                            for item in reasons["certification"]["failures"]))

    def test_the_audit_artifact_is_loaded_from_the_assurance_reference(self):
        import structural_equivalence_check as sec
        card, state, _ = self._certified()
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            directory = root / sec.AUDIT_DIR
            directory.mkdir(parents=True)
            (directory / "H1.json").write_text(
                json.dumps(sec._selftest_artifact(), ensure_ascii=False), encoding="utf-8")
            audits, problems = pc.load_audits(state, root)
            self.assertEqual(problems, [])
            self.assertEqual(sorted(audits), ["A1"])
            self.assertTrue(audits["A1"]["artifact"])
            unsupported = clone(state)
            unsupported["assurance"] = []
            self.assertEqual(pc.load_audits(unsupported, root)[0], {})

    def test_every_certification_failure_names_a_declared_check(self):
        """Each failure must name the single missing step, not a generic refusal."""
        scenarios = []
        card, state, audits = self._certified()
        card["novel_prediction"]["observation"]["experiment_id"] = "X2"
        scenarios.append((card, state, audits))
        card, state, audits = self._certified()
        state["evidence"][0]["supports"] = []
        scenarios.append((card, state, audits))
        card, state, audits = self._certified()
        audits["A1"]["artifact"] = {**audits["A1"]["artifact"], "verdict": "equivalent"}
        scenarios.append((card, state, audits))
        card, state, audits = self._certified()
        state["evidence"][0]["prediction_ref"] = "X1:O2"
        scenarios.append((card, state, audits))
        card, state, audits = self._certified()
        state["experiments"][0]["outcome_analysis"] = None
        scenarios.append((card, state, audits))
        for index, (candidate, scenario_state, scenario_audits) in enumerate(scenarios):
            derived, reasons = pc.classify_insight(candidate, scenario_state, scenario_audits)
            certification = reasons["certification"]
            self.assertNotEqual(derived, "evidence_supported_insight", index)
            # Every attempt must name what is missing, and every *violation* must name the
            # check it failed; a generic refusal would not tell the researcher what to fix.
            self.assertTrue(certification["missing"] or certification["failures"], index)
            self.assertTrue(reasons["missing"], index)
            for failure in certification["failures"]:
                self.assertTrue(
                    any(failure.startswith(check_id)
                        for check_id in pc.CERTIFICATION_CHECKS), failure)

    def test_a_certification_attempt_without_provenance_is_reported(self):
        card, state, _ = self._certified()
        card["novel_prediction"]["observation"] = {}
        card["novel_prediction"]["observation_digest"] = "sha256:x"
        errors = pc.insight_card_errors(card, state)
        self.assertIn("PC11", {d.rule for d in errors})
        self.assertIn("PC7", {d.rule for d in errors})

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
            self.assertEqual(payload["cards"][0]["derived_class"],
                             "predictive_insight_candidate")
            self.assertEqual(payload["audit_problems"],
                             ["A1 没有 audit_ref：审计只被声明，没有被审核过的结果"])

    def test_a_missing_competition_is_an_environment_error(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path, cognition_dir = self.project(pathlib.Path(temp))
            proc = self.run_cli("compete", "--state", str(state_path),
                                "--cognition", str(cognition_dir), "--competition", "CP9")
            self.assertEqual(proc.returncode, pc.EXIT_ENV)


if __name__ == "__main__":
    unittest.main()
