#!/usr/bin/env python3
"""Offline R12 source freeze, realization and adversarial recovery tests."""
import copy
import json
from pathlib import Path
import unittest

import rhetorical_realization as rr
import validate_rhetorical_variant as rv

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "narrative-realization"


def fixture():
    state = json.loads((EXAMPLE / "source-state.json").read_text(encoding="utf-8"))
    manifest = json.loads((EXAMPLE / "manifest.json").read_text(encoding="utf-8"))
    snapshot = rv.freeze(state, manifest)
    return state, snapshot, rr.generate(state, snapshot)


class TestGeneration(unittest.TestCase):
    def test_bounded_profiles_all_pass_and_have_identical_semantics(self):
        state, snapshot, variants = fixture()
        self.assertEqual(len(variants), 4)
        for variant in variants:
            self.assertEqual(rv.validate(state, snapshot, variant)["status"], "PASS")
            self.assertEqual(variant["semantics"], snapshot["semantics"])
        self.assertEqual(len({v["text"] for v in variants}), 4)

    def test_read_only_generation_and_independent_objects(self):
        state, snapshot, _ = fixture()
        before = copy.deepcopy(state)
        frozen_before = copy.deepcopy(snapshot)
        variants = rr.generate(state, snapshot)
        self.assertEqual(state, before)
        self.assertEqual(snapshot, frozen_before)
        variants[0]["semantics"]["scope"].append("changed")
        self.assertEqual(snapshot, frozen_before)
        self.assertNotEqual(variants[0]["semantics"], variants[1]["semantics"])


def full_response(snapshot):
    response = rr.recovery_truth(snapshot)
    response["unsupported_or_overstated_claims"] = []
    return response


class TestRecovery(unittest.TestCase):
    def test_blind_payload_does_not_receive_snapshot_or_variant_metadata(self):
        _, snapshot, variants = fixture()
        payload = rr.blind_task(variants[0]["text"])
        self.assertEqual(set(payload), {"instruction", "questions", "narrative"})
        self.assertEqual(payload["narrative"], variants[0]["text"])
        self.assertNotIn(snapshot["snapshot_digest"], json.dumps(payload))
        self.assertNotIn("profile", payload)

    def test_full_recovery_pass_and_partial_boundary(self):
        _, snapshot, _ = fixture()
        response = full_response(snapshot)
        result = rr.score_recovery(snapshot, response)
        self.assertEqual(set(result["metrics"].values()), {"PASS"})
        response["main_boundary"].pop()
        result = rr.score_recovery(snapshot, response)
        self.assertEqual(result["metrics"]["Boundary Recovery"], "PARTIAL")

    def test_empty_and_invented_claim_fail(self):
        _, snapshot, _ = fixture()
        for recovered in ([], ["We are the first and universally effective."]):
            response = full_response(snapshot)
            response["central_claim"] = recovered
            result = rr.score_recovery(snapshot, response)
            self.assertEqual(result["metrics"]["Claim Recovery"], "FAIL")

    def test_unsupported_claim_and_overall_score_cannot_help(self):
        _, snapshot, _ = fixture()
        response = full_response(snapshot)
        response["unsupported_or_overstated_claims"] = ["Unsupported firstness"]
        self.assertFalse(rr.score_recovery(snapshot, response)["eligible"])
        response["overall_score"] = 10
        self.assertEqual(rr.score_recovery(snapshot, response)["status"], "INVALID")

    def test_complete_multimodel_panel_and_stale_text_rejection(self):
        state, snapshot, variants = fixture()
        plan = rr.evaluation_plan(snapshot, [{"judge_id": "J1", "model_id": "model-A"},
                                              {"judge_id": "J2", "model_id": "model-B"}])
        probes = [rr.probe_record(plan, v, j["judge_id"], full_response(snapshot))
                  for v in variants for j in plan["judges"]]
        self.assertEqual(rr.panel(state, snapshot, variants, plan, probes)[0], [])
        probes[0]["text_digest"] = "stale"
        self.assertTrue(rr.panel(state, snapshot, variants, plan, probes)[0])

    def test_same_model_roles_do_not_make_multimodel_panel(self):
        _, snapshot, _ = fixture()
        with self.assertRaises(ValueError):
            rr.evaluation_plan(snapshot, [{"judge_id": "J1", "model_id": "same"},
                                          {"judge_id": "J2", "model_id": "same"}])


def evaluation_fixture():
    state, snapshot, variants = fixture()
    plan = rr.evaluation_plan(snapshot, [{"judge_id": "J1", "model_id": "model-A"},
                                          {"judge_id": "J2", "model_id": "model-B"}])
    probes = [rr.probe_record(plan, v, j["judge_id"], full_response(snapshot))
              for v in variants for j in plan["judges"]]
    return state, snapshot, variants, plan, probes


class TestSensitivity(unittest.TestCase):
    def test_stable_complete_panel_and_neutral_tie(self):
        args = evaluation_fixture()
        audit = rr.sensitivity(*args)
        self.assertEqual(audit["status"], "STABLE")
        self.assertEqual(audit["paired_by_judge"]["J1"]["Claim Recovery"]["variance"], 0)
        selected = rr.select(*args)
        self.assertEqual(selected["selected_variant"], "V1")
        self.assertFalse(selected["submission_ready"])

    def test_paired_disagreement_not_hidden_by_same_pooled_mean(self):
        state, snapshot, variants, plan, probes = evaluation_fixture()
        for probe in probes:
            # Both profiles have one PASS and one FAIL: pooled means are identical.
            if (probe["variant_id"], probe["judge_id"]) in (("V1", "J1"), ("V2", "J2")):
                probe["response"]["central_claim"] = []
        audit = rr.sensitivity(state, snapshot, variants, plan, probes)
        self.assertEqual(audit["status"], "RHETORICALLY_FRAGILE")
        self.assertEqual(audit["paired_by_judge"]["J1"]["Claim Recovery"]["range"], 2)
        self.assertGreater(audit["between_judges"]["V1"]["Claim Recovery"]["disagreement"], 0)

    def test_wrong_novelty_interpretation_is_fragile(self):
        args = evaluation_fixture()
        args[-1][0]["response"]["closest_prior_work_delta"].append("We are the first")
        self.assertEqual(rr.sensitivity(*args)["status"], "RHETORICALLY_FRAGILE")
        self.assertNotEqual(rr.select(*args)["selected_variant"], "V1")

    def test_scientific_judgment_change_is_diagnostic_only(self):
        args = evaluation_fixture()
        for probe in args[-1]:
            probe["response"]["scientific_judgment"] = "supported"
        args[-1][0]["response"]["scientific_judgment"] = "unsupported"
        self.assertEqual(rr.sensitivity(*args)["status"], "RHETORICALLY_FRAGILE")
        # Equal recoverability: judgment is never an optimization score.
        self.assertEqual(rr.select(*args)["selected_variant"], "V1")

    def test_missing_duplicate_or_unpaired_data_is_incomplete(self):
        for mutate in (lambda p: p.pop(), lambda p: p.append(copy.deepcopy(p[0])),
                       lambda p: p[0]["response"].update(scientific_judgment="supported")):
            args = evaluation_fixture()
            mutate(args[-1])
            self.assertEqual(rr.sensitivity(*args)["status"], "INCOMPLETE")
            self.assertIsNone(rr.select(*args)["selected_variant"])

    def test_boundary_recovery_wins_tie_and_overstatement_disqualifies(self):
        args = evaluation_fixture()
        for probe in args[-1]:
            if probe["variant_id"] == "V1":
                probe["response"]["main_boundary"].pop()
            if probe["variant_id"] == "V2":
                probe["response"]["unsupported_or_overstated_claims"] = ["Unsupported novelty"]
        self.assertEqual(rr.select(*args)["selected_variant"], "V3")


if __name__ == "__main__":
    unittest.main()
