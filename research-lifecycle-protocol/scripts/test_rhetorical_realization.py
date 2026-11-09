#!/usr/bin/env python3
"""Offline R12 source freeze, realization and adversarial recovery tests."""
import copy
import json
from pathlib import Path
import unittest
import subprocess
import sys
import tempfile
from unittest.mock import patch

import rhetorical_realization as rr
import validate_rhetorical_variant as rv
import release_check

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

    def test_overstatement_disagreement_is_fragile_and_visible(self):
        args = evaluation_fixture()
        args[-1][0]["response"]["unsupported_or_overstated_claims"] = ["Unsupported novelty"]
        audit = rr.sensitivity(*args)
        self.assertEqual(audit["status"], "RHETORICALLY_FRAGILE")
        self.assertEqual(audit["variants"]["V1"]["unsupported_by_judge"]["J1"],
                         ["Unsupported novelty"])
        self.assertNotEqual(rr.select(*args)["selected_variant"], "V1")

    def test_constant_overstatement_is_stable_but_never_eligible(self):
        args = evaluation_fixture()
        for probe in args[-1]:
            probe["response"]["unsupported_or_overstated_claims"] = ["Unsupported novelty"]
        self.assertEqual(rr.sensitivity(*args)["status"], "STABLE")
        self.assertEqual(rr.select(*args)["status"], "NO_ELIGIBLE_VARIANT")

    def test_overstatement_list_order_does_not_create_fragility(self):
        args = evaluation_fixture()
        for i, probe in enumerate(args[-1]):
            claims = ["Unsupported novelty", "Unsupported scope"]
            probe["response"]["unsupported_or_overstated_claims"] = claims if i % 3 else claims[::-1]
        self.assertEqual(rr.sensitivity(*args)["status"], "STABLE")

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

    def test_no_claim_recovered_does_not_produce_a_recommendation(self):
        args = evaluation_fixture()
        for probe in args[-1]:
            probe["response"]["central_claim"] = []
        result = rr.select(*args)
        self.assertEqual(result["status"], "NO_ELIGIBLE_VARIANT")
        self.assertIsNone(result["selected_variant"])

    def test_changed_plan_models_profiles_or_source_make_panel_incomplete(self):
        for mutate in (lambda a: a[3]["judges"][0].update(model_id="replacement"),
                       lambda a: a[2].pop(),
                       lambda a: a[0]["uncertainties"][0].update(question="A new research question"),
                       lambda a: a[-1][0].update(model_id="not-the-registered-model")):
            args = evaluation_fixture()
            mutate(args)
            self.assertEqual(rr.sensitivity(*args)["status"], "INCOMPLETE")

    def test_selection_uses_preregistered_tie_order_not_caller_batch_order(self):
        state, snapshot, variants, plan, probes = evaluation_fixture()
        self.assertEqual(rr.select(state, snapshot, list(reversed(variants)), plan, probes)["selected_variant"], "V1")


class TestAdversarialEquivalence(unittest.TestCase):
    def setUp(self):
        self.state, self.snapshot, self.variants = fixture()

    def check(self, variant):
        return rv.validate(self.state, self.snapshot, variant)["status"]

    def mutate_text(self, old, new):
        variant = copy.deepcopy(self.variants[0])
        self.assertIn(old, variant["text"])
        variant["text"] = variant["text"].replace(old, new)
        # The generator's semantic declaration is unchanged: audit must read prose.
        self.assertEqual(variant["semantics"], self.snapshot["semantics"])
        return variant

    def test_case_1_valid_evidence_framing(self):
        neutral, evidence = self.variants[:2]
        self.assertEqual(self.check(evidence), "PASS")
        self.assertEqual(neutral["semantics"]["numerical_values"], evidence["semantics"]["numerical_values"])
        self.assertIn("Reported comparison / effect", evidence["text"])
        self.assertLess(evidence["text"].index("S5 Evidence Contract"), evidence["text"].index("S1 Context"))

    def test_case_2_novelty_inflation(self):
        self.assertEqual(self.check(self.mutate_text("We study changing X", "We are the first to change X")), "FAIL")

    def test_case_3_scope_inflation(self):
        self.assertEqual(self.check(self.mutate_text("On Dataset-A under protocol Y", "Universally across all datasets")), "FAIL")

    def test_case_4_limitation_laundering(self):
        for text in ("", "Minor practical detail, broadly robust"):
            self.assertEqual(self.check(self.mutate_text(
                "Single dataset; statistical significance and cross-setting robustness are untested.", text)), "FAIL")

    def test_case_5_statistical_inflation(self):
        for phrase in ("a statistically significant PSNR improvement", "a robust PSNR improvement"):
            self.assertEqual(self.check(self.mutate_text("a mean PSNR improvement", phrase)), "FAIL")

    def test_case_6_valid_prior_work_delta(self):
        contribution = self.variants[2]
        self.assertEqual(self.check(contribution), "PASS")
        self.assertIn("Closest prior-work delta", contribution["text"])
        self.assertIn(self.state["evidence"][1]["source_ref"], contribution["text"])
        self.assertEqual(contribution["semantics"]["prior_work_delta"], self.snapshot["semantics"]["prior_work_delta"])

    def test_case_7_causal_inflation(self):
        self.assertEqual(self.check(self.mutate_text("is associated with", "causes")), "FAIL")

    def test_case_8_same_claims_different_ordering(self):
        self.assertEqual(self.check(self.variants[2]), "PASS")
        self.assertEqual(self.variants[0]["semantics"], self.variants[2]["semantics"])
        self.assertLess(self.variants[2]["text"].index("S2 Tension"), self.variants[2]["text"].index("S1 Context"))

    def test_all_frozen_fields_are_checked(self):
        for field in rv.FIELDS:
            with self.subTest(field=field):
                v = copy.deepcopy(self.variants[0])
                v["semantics"][field].append("unsupported change")
                self.assertEqual(self.check(v), "FAIL")

    def test_source_changes_cannot_be_repaired_by_narrative(self):
        for key in ("claims", "evidence", "uncertainties", "failures", "assumptions", "literature"):
            with self.subTest(key=key):
                state = copy.deepcopy(self.state)
                state[key][0]["validity"]["reason"] = "Changed for storytelling"
                self.assertEqual(rv.validate(state, self.snapshot, self.variants[0])["status"], "FAIL")
        state = copy.deepcopy(self.state)
        state["claims"].append(copy.deepcopy(state["claims"][0]))
        state["claims"][-1]["id"] = "C99"
        self.assertEqual(rv.validate(state, self.snapshot, self.variants[0])["status"], "FAIL")

    def test_existing_view_descriptor_is_the_only_permitted_state_change(self):
        state = copy.deepcopy(self.state)
        state["narrative_view"]["note"] = "Selected audited variant V1"
        self.assertEqual(rv.validate(state, self.snapshot, self.variants[0])["status"], "PASS")

    def test_unknown_operator_extra_prose_and_unbounded_round_fail(self):
        mutations = [lambda v: v["operators"].append("inflate_novelty"),
                     lambda v: v.update(profile="optimize-reviewer-score"),
                     lambda v: v.update(round=2), lambda v: v.update(round=True),
                     lambda v: v.update(text=v["text"] + "\nWe propose a novel unprecedented framework."),
                     lambda v: v.update(overall_score=5)]
        for mutate in mutations:
            v = copy.deepcopy(self.variants[0])
            mutate(v)
            self.assertEqual(self.check(v), "FAIL")

    def test_snapshot_and_mapping_tampering_fail(self):
        for mutate in (lambda s: s["manifest"]["evidence_mapping"]["C0"].update(supports=["E2"]),
                       lambda s: s["manifest"].update(preset="N10"),
                       lambda s: s["slots"]["S6"].clear()):
            snapshot = copy.deepcopy(self.snapshot)
            mutate(snapshot)
            self.assertEqual(rv.validate(self.state, snapshot, self.variants[0])["status"], "FAIL")

    def test_omitted_failure_uncertainty_and_comparator_are_not_trusted(self):
        for field in ("limitations", "failure_cases", "uncertainty", "scope"):
            manifest = copy.deepcopy(self.snapshot["manifest"])
            manifest["bindings"][field] = []
            manifest["empty_reasons"][field] = "Hide it"
            with self.subTest(field=field), self.assertRaises(ValueError):
                rv.freeze(self.state, manifest)

    def test_source_roles_cannot_be_substituted(self):
        for kind, field, paths in (
                ("bindings", "comparators", ["/claims/0/statement"]),
                ("bindings", "numerical_values", ["/uncertainties/0/question"]),
                ("slots", "S5", ["/uncertainties/0/question"]),
                ("slots", "S3", ["/literature/0/ref"])):
            manifest = copy.deepcopy(self.snapshot["manifest"])
            manifest[kind][field] = paths
            with self.subTest(kind=kind, field=field), self.assertRaisesRegex(ValueError, "source role"):
                rv.freeze(self.state, manifest)

    def test_unselected_ungrounded_claim_cannot_enter_slots(self):
        state = copy.deepcopy(self.state)
        claim = copy.deepcopy(state["claims"][0])
        claim.update(id="C99", status="ungrounded", supporting_evidence=[], refuting_evidence=[],
                     parent=None, subclaims=[], known_flaws=[])
        state["claims"].append(claim)
        self.assertEqual(rv.state_check.check_state(state).exit_code, 0)
        manifest = copy.deepcopy(self.snapshot["manifest"])
        manifest["slots"]["S3"].append("/claims/2/statement")
        with self.assertRaisesRegex(ValueError, "source role"):
            rv.freeze(state, manifest)

    def test_same_text_from_wrong_claim_identity_is_rejected(self):
        state = copy.deepcopy(self.state)
        state["claims"][1]["statement"] = state["claims"][0]["statement"]
        self.assertEqual(rv.state_check.check_state(state).exit_code, 0)
        manifest = copy.deepcopy(self.snapshot["manifest"])
        manifest["bindings"]["central_claim"] = ["/claims/1/statement"]
        with self.assertRaisesRegex(ValueError, "claim identities"):
            rv.freeze(state, manifest)

    def test_referenced_planned_experiment_is_not_observed_result(self):
        state = copy.deepcopy(self.state)
        state["experiments"][0].update(status="planned", prereg=None, result_at=None)
        self.assertEqual(rv.state_check.check_state(state).exit_code, 0)
        with self.assertRaisesRegex(ValueError, "completed and valid"):
            rv.freeze(state, self.snapshot["manifest"])

    def test_boundary_source_leaves_remain_supported(self):
        manifest = copy.deepcopy(self.snapshot["manifest"])
        manifest["slots"]["S6"].extend(["/uncertainties/0/question", "/assumptions/0/if_false"])
        snapshot = rv.freeze(self.state, manifest)
        self.assertTrue(all(rv.validate(self.state, snapshot, v)["status"] == "PASS"
                            for v in rr.generate(self.state, snapshot)))

    def test_non_string_and_duplicate_source_pointers_are_rejected(self):
        for kind, field, paths in (("bindings", "comparators", [None]),
                                   ("slots", "S5", [None]),
                                   ("bindings", "comparators", ["/literature/0/ref"] * 2),
                                   ("slots", "S5", ["/experiments/0/result"] * 2)):
            manifest = copy.deepcopy(self.snapshot["manifest"])
            manifest[kind][field] = paths
            with self.subTest(kind=kind, paths=paths), self.assertRaises(ValueError):
                rv.freeze(self.state, manifest)

    def test_boundary_position_identical_for_every_profile(self):
        for v in self.variants:
            text = v["text"]
            self.assertLess(text.index("limitations:"), text.index("S1 Context"))
            self.assertLess(text.index("failure_cases:"), text.index("S5 Evidence Contract"))
        prefix = self.variants[0]["text"].split("\n\nS1 Context")[0]
        self.assertTrue(all(v["text"].startswith(prefix) for v in self.variants))

    def test_bad_prose_is_blocked_before_probe(self):
        v = self.mutate_text("We study changing X", "We are the first to change X")
        with self.assertRaises(ValueError):
            rr.prepare_probe(self.state, self.snapshot, v)

    def test_malformed_inputs_fail_closed(self):
        for value in (None, [], {}, "bad"):
            self.assertEqual(rv.validate(self.state, self.snapshot, value)["status"], "FAIL")
            self.assertEqual(rv.validate(self.state, value, self.variants[0])["status"], "FAIL")


class TestCLIAndRelease(unittest.TestCase):
    def test_end_to_end_cli_generation_validator_and_blind_task_are_read_only(self):
        state, snapshot, variants = fixture()
        script = rv.ROOT / "scripts" / "rhetorical_realization.py"
        checker = rv.ROOT / "scripts" / "validate_rhetorical_variant.py"
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            files = {"state": state, "snapshot": snapshot, "variant": variants[0]}
            for name, value in files.items():
                (folder / (name + ".json")).write_text(json.dumps(value), encoding="utf-8")
            args = [arg for name in files for arg in ("--" + name, str(folder / (name + ".json")))]
            before = (folder / "state.json").read_bytes()
            proc = subprocess.run([sys.executable, str(checker), *args], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            proc = subprocess.run([sys.executable, str(script), "probe-task", *args], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertEqual(set(json.loads(proc.stdout)), {"instruction", "questions", "narrative"})
            variant_path = folder / "variant.json"
            v = variants[0]
            v["text"] += " Unsupported claim"
            variant_path.write_text(json.dumps(v), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(checker), *args], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(json.loads(proc.stdout)["status"], "FAIL")
            variant_path.write_text("bad JSON", encoding="utf-8")
            proc = subprocess.run([sys.executable, str(checker), *args], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 4)
            self.assertEqual((folder / "state.json").read_bytes(), before)
        proc = subprocess.run([sys.executable, str(script), "generate", "--state", str(EXAMPLE / "source-state.json"),
                               "--manifest", str(EXAMPLE / "manifest.json")], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(len(json.loads(proc.stdout)["variants"]), 4)

    def test_release_step_detects_mutated_actual_prose(self):
        _, snapshot, variants = fixture()
        variants[0]["text"] += " We are the first."
        output = json.dumps({"snapshot": snapshot, "variants": variants})
        with patch.object(release_check, "_run", return_value=(0, output)):
            self.assertFalse(release_check.step_rhetorical_realization()[0])


if __name__ == "__main__":
    unittest.main()
