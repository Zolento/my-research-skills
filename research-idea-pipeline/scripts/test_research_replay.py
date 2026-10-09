#!/usr/bin/env python3
"""test_research_replay.py — Phase 4: replay, metrics, ablation, adversarial suite.

Phase 4 is the part that has to prove the engine improved discovery rather than added
documents. That claim is easy to fake, so the tests attack the ways it could be faked:
a leak of the hidden answer, a metric that silently becomes an aggregate, a novelty score
that comes from the agent itself, a one-run "improvement", and an adversarial case that
passes because the runner was scripted to pass.
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
import research_replay as rr

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "research_replay.py"
CASES = ROOT / "examples" / "replay" / "adversarial"


def clone(value):
    return json.loads(json.dumps(value))


def quiet(callable_, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()) as sink:
        result = callable_(*args, **kwargs)
    return result, sink.getvalue()


# ---------------------------------------------------------------------------
# Case schema and the leak guard
# ---------------------------------------------------------------------------

class TestCaseSchema(unittest.TestCase):

    def test_the_generated_suite_is_complete(self):
        cases = rr.adversarial_cases()
        self.assertEqual(len(cases), 14)
        self.assertEqual([case["id"] for case in cases],
                         [f"ADV{n}" for n in range(1, 15)])

    def test_every_case_validates(self):
        for case in rr.adversarial_cases():
            self.assertEqual(rr.case_errors(case), [], msg=case["id"])

    def test_a_case_without_an_answer_is_rejected(self):
        case = clone(rr.adversarial_cases()[0])
        del case["hidden"]["answer"]
        self.assertIn("RP1", {d.rule for d in rr.case_errors(case)})

    def test_an_unknown_outcome_class_is_rejected(self):
        case = clone(rr.adversarial_cases()[0])
        case["hidden"]["answer"]["true_outcome_class"] = "PROBABLY_FINE"
        self.assertIn("RP1", {d.rule for d in rr.case_errors(case)})

    def test_an_unknown_forbidden_behaviour_is_rejected(self):
        case = clone(rr.adversarial_cases()[0])
        case["evaluation_only"]["forbidden_behaviours"] = ["be_lazy"]
        self.assertIn("RP2", {d.rule for d in rr.case_errors(case)})

    def test_a_self_rated_novelty_is_rejected(self):
        case = clone(rr.adversarial_cases()[0])
        case["hidden"]["answer"].pop("human_novelty_label", None)
        case["hidden"]["answer"].pop("novelty_neighbours", None)
        case["hidden"]["answer"]["novelty_rating"] = 0.9
        self.assertIn("RP5", {d.rule for d in rr.case_errors(case)})

    def test_the_shipped_cases_load_and_match_the_generator(self):
        shipped = rr.load_cases(CASES)
        self.assertEqual(len(shipped), 14)
        generated = rr.adversarial_cases()
        self.assertEqual([case["id"] for case in shipped],
                         [case["id"] for case in generated])


class TestLeakGuard(unittest.TestCase):

    def test_no_generated_case_leaks(self):
        for case in rr.adversarial_cases():
            visible = rr.visible_view(case)
            self.assertEqual(rr.leak_scan(case, visible), [], msg=case["id"])

    def test_the_hidden_section_is_absent_from_the_visible_view(self):
        for case in rr.adversarial_cases():
            blob = json.dumps(rr.visible_view(case), ensure_ascii=False)
            self.assertNotIn("later_results", blob)
            self.assertNotIn("true_outcome_class", blob)
            self.assertNotIn("reference_reasoning", blob)

    def test_an_injected_leak_is_caught(self):
        case = clone(rr.adversarial_cases()[0])
        case["visible"]["known_conditions"].append(case["hidden"]["later_results"][0])
        self.assertTrue(rr.leak_scan(case, rr.visible_view(case)))

    def test_a_leaking_case_refuses_to_run(self):
        case = clone(rr.adversarial_cases()[0])
        case["visible"]["known_conditions"].append(case["hidden"]["later_results"][0])
        with self.assertRaises(cg.CognitionError):
            rr.run_case(case)

    def test_short_strings_are_not_treated_as_leak_markers(self):
        case = clone(rr.adversarial_cases()[0])
        before = set(rr.forbidden_strings(case))
        case["hidden"]["answer"]["mechanism_terms"] = ["A", "ok"]
        after = set(rr.forbidden_strings(case))
        self.assertEqual(before, after)
        self.assertNotIn("A", after)
        self.assertNotIn("ok", after)

    def test_the_shipped_case_files_carry_hidden_answers(self):
        for path in sorted(CASES.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("hidden", payload, msg=path.name)
            self.assertTrue(payload["hidden"]["answer"], msg=path.name)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class TestMetrics(unittest.TestCase):

    def setUp(self):
        self.cases = rr.adversarial_cases()
        self.case = self.cases[0]
        self.result = rr.run_case(self.case, "full_cie")

    def test_all_seven_dimensions_are_reported(self):
        self.assertEqual(set(self.result["evaluation"]["metrics"]), set(rr.METRIC_DIMENSIONS))

    def test_no_dimension_is_an_aggregate(self):
        blob = json.dumps(self.result["evaluation"], ensure_ascii=False)
        for key in ("total", "overall", "score", "weighted"):
            self.assertNotIn(f'"{key}"', blob)

    def test_every_dimension_states_a_reason(self):
        for dimension, metric in self.result["evaluation"]["metrics"].items():
            self.assertTrue(metric["reason"], msg=dimension)
            self.assertIn("value", metric)
            self.assertIn("basis", metric)

    def test_an_unratable_dimension_is_null_not_zero(self):
        silent = rr.run_case(self.case, "baseline")
        self.assertIsNone(silent["evaluation"]["metrics"]["prediction_quality"]["value"])
        self.assertIn("没有产出预测判定",
                      silent["evaluation"]["metrics"]["prediction_quality"]["reason"])

    def test_novelty_requires_an_independent_label(self):
        by_id = {case["id"]: case for case in self.cases}
        labelled = rr.run_case(by_id["ADV1"], "full_cie")
        unknown = rr.run_case(by_id["ADV2"], "full_cie")
        self.assertEqual(labelled["evaluation"]["metrics"]["scientific_novelty"]["value"], 0.0)
        self.assertIsNone(unknown["evaluation"]["metrics"]["scientific_novelty"]["value"])
        self.assertIn("unknown",
                      unknown["evaluation"]["metrics"]["scientific_novelty"]["reason"])
        stripped = clone(by_id["ADV2"])
        stripped["hidden"]["answer"].pop("human_novelty_label", None)
        stripped["evaluation_only"]["forbidden_behaviours"] = []
        result = rr.run_case(stripped, "full_cie")
        self.assertIsNone(result["evaluation"]["metrics"]["scientific_novelty"]["value"])
        self.assertIn("不可评",
                      result["evaluation"]["metrics"]["scientific_novelty"]["reason"])

    def test_an_agent_novelty_rating_is_refused(self):
        decision = clone(self.result["decision"])
        decision["novelty_self_rating"] = 0.95
        self.assertIn("RP5", {d.rule for d in rr.decision_errors(decision)})

    def test_mechanistic_understanding_matches_the_reference_terms(self):
        metric = self.result["evaluation"]["metrics"]["mechanistic_understanding"]
        self.assertIsNotNone(metric["value"])
        self.assertGreater(metric["value"], 0.0)

    def test_search_efficiency_requires_a_baseline(self):
        alone = rr.evaluate(self.case, self.result["decision"], None)
        self.assertIsNone(alone["metrics"]["search_efficiency"]["value"])
        with_base = self.result["evaluation"]["metrics"]["search_efficiency"]
        self.assertIsNotNone(with_base["value"])

    def test_memory_accumulation_only_applies_to_a_second_session(self):
        by_id = {case["id"]: case for case in self.cases}
        second = rr.run_case(by_id["ADV8"], "full_cie")
        first = rr.run_case(by_id["ADV1"], "full_cie")
        self.assertIsNotNone(second["evaluation"]["metrics"]["memory_accumulation"]["value"])
        self.assertIsNone(first["evaluation"]["metrics"]["memory_accumulation"]["value"])

    def test_a_decision_that_forbids_stopping_is_flagged(self):
        case = clone(self.case)
        case["evaluation_only"]["forbidden_behaviours"] = [
            "continue_attribution_without_decision_value"]
        result = rr.run_case(case, "baseline")
        self.assertIn("decision_did_not_change", result["evaluation"]["violations"])

    def test_evaluation_never_reads_the_decision_for_the_answer(self):
        """The answer path is one-way: hidden → metrics, never hidden → runner."""
        mutated = clone(self.case)
        for field in ("mechanism_terms", "assumption_terms", "boundary_terms"):
            mutated["hidden"]["answer"][field] = ["完全不同的参考术语"]
        baseline = rr.run_case(self.case, "full_cie")
        altered = rr.run_case(mutated, "full_cie")
        self.assertEqual(baseline["decision"], altered["decision"],
                         "the hidden answer changed the runner's decision")
        self.assertNotEqual(
            baseline["evaluation"]["metrics"]["mechanistic_understanding"]["value"],
            altered["evaluation"]["metrics"]["mechanistic_understanding"]["value"])
        self.assertEqual(
            altered["evaluation"]["metrics"]["mechanistic_understanding"]["value"], 0.0)


# ---------------------------------------------------------------------------
# Ablation
# ---------------------------------------------------------------------------

class TestAblation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cases = rr.adversarial_cases()

    def test_the_four_arms_are_defined(self):
        self.assertEqual(rr.ABLATION_ARMS,
                         ("baseline", "memory_only", "memory_prediction", "full_cie"))

    def test_capabilities_are_cumulative(self):
        previous: set = set()
        for arm in rr.ABLATION_ARMS:
            current = set(rr.ARM_CAPABILITIES[arm])
            self.assertTrue(previous <= current, msg=arm)
            previous = current

    def test_the_baseline_can_use_nothing(self):
        self.assertEqual(rr.ARM_CAPABILITIES["baseline"], ())

    def test_each_arm_produces_observations(self):
        report = rr.run_suite(self.cases, runs=2)
        for arm, block in report["per_arm"].items():
            self.assertEqual(block["observations"], len(self.cases) * 2, msg=arm)
            self.assertEqual(block["cases"], len(self.cases))

    def test_the_capability_ladder_shows_up_in_the_metrics(self):
        report = rr.run_suite(self.cases, runs=1)
        baseline = report["per_arm"]["baseline"]["dimensions"]
        memory = report["per_arm"]["memory_only"]["dimensions"]
        predicted = report["per_arm"]["memory_prediction"]["dimensions"]
        self.assertIsNone(baseline["prediction_quality"]["mean"])
        self.assertIsNone(memory["prediction_quality"]["mean"])
        self.assertIsNotNone(predicted["prediction_quality"]["mean"])
        self.assertGreater(memory["memory_accumulation"]["mean"],
                           baseline["memory_accumulation"]["mean"])

    def test_the_baseline_fails_the_adversarial_suite(self):
        report = rr.run_suite(self.cases, runs=1)
        self.assertEqual(report["per_arm"]["baseline"]["pass_rate"], 0.0)
        self.assertIn("decision_did_not_change",
                      report["per_arm"]["baseline"]["violations"])

    def test_the_full_arm_passes_the_adversarial_suite(self):
        report = rr.run_suite(self.cases, runs=1)
        self.assertEqual(report["per_arm"]["full_cie"]["pass_rate"], 1.0)
        self.assertEqual(report["per_arm"]["full_cie"]["violations"], [])

    def test_an_undersized_sample_refuses_to_claim_an_improvement(self):
        report = rr.run_suite(self.cases[:1], runs=1)
        self.assertFalse(report["sufficient_sample"])
        self.assertIn("不得宣称提升", report["claim"])

    def test_indistinguishable_arms_are_reported(self):
        report = rr.run_suite(self.cases, runs=1)
        flat = {tuple(group) for group in report["undifferentiated_arms"]}
        self.assertIn(("memory_prediction", "full_cie"), flat)
        self.assertTrue(any("无法区分" in item for item in report["limitations"]))

    def test_the_report_states_its_limitations(self):
        report = rr.run_suite(self.cases, runs=1)
        self.assertTrue(report["limitations"])
        self.assertTrue(any("合成" in item for item in report["limitations"]))
        self.assertTrue(any("真实模型" in item for item in report["limitations"]))

    def test_a_custom_runner_is_pluggable(self):
        seen: list = []

        def runner(visible, arm):
            seen.append((visible["case_id"], arm))
            return {"_schema": rr.SCHEMA_DECISION, "case_id": visible["case_id"], "arm": arm,
                    "capabilities": [], "used_memory": [], "mechanism_terms": [],
                    "predicted_outcome_class": None, "chosen_intervention": None,
                    "decision_changed": False}

        report = rr.run_suite(self.cases[:2], runs=1, runner=runner)
        self.assertEqual(report["runner"], "external runner")
        self.assertTrue(seen)
        self.assertFalse(any("hidden" in str(item) for item in seen))

    def test_a_runner_that_returns_junk_is_rejected(self):
        report = rr.run_suite(self.cases[:1], runs=1, runner=lambda visible, arm: {"arm": arm})
        diagnostics = report["per_arm"]["baseline"]["results"][0]["diagnostics"]
        self.assertTrue(diagnostics)
        self.assertEqual(diagnostics[0]["rule"], "RP3")

    def test_a_runner_spec_is_validated(self):
        with self.assertRaises(cg.CognitionError):
            rr.load_runner("no_colon_here")
        with self.assertRaises(cg.CognitionError):
            rr.load_runner("json:not_a_function")

    def test_an_unknown_arm_is_rejected(self):
        with self.assertRaises(KeyError):
            rr.run_case(self.cases[0], "full_cie_plus")


# ---------------------------------------------------------------------------
# Adversarial coverage
# ---------------------------------------------------------------------------

class TestAdversarialCoverage(unittest.TestCase):

    def test_the_ten_required_situations_are_present(self):
        titles = " ".join(case["title"] for case in rr.adversarial_cases())
        for fragment in ("机制解释了历史", "等价", "实现错误", "再次提出", "EIG 很低",
                         "表面相似", "证据失效", "新会话", "事后修改", "连续几轮诊断",
                         "只提交其中一项", "执行有效性未知"):
            self.assertIn(fragment, titles, msg=fragment)

    def test_every_case_forbids_at_least_one_bad_behaviour_or_names_one(self):
        for case in rr.adversarial_cases():
            evaluation = case["evaluation_only"]
            self.assertTrue(evaluation.get("expected_behaviour"), msg=case["id"])

    def test_the_refuted_mechanism_case_blocks_the_repeat(self):
        case = next(case for case in rr.adversarial_cases() if case["id"] == "ADV4")
        result = rr.run_case(case, "full_cie")
        self.assertTrue(result["decision"]["repeat_blocked"])
        self.assertFalse(result["decision"]["repeated_prior_error"])

    def test_the_invalid_run_case_preserves_the_invalid_class(self):
        case = next(case for case in rr.adversarial_cases() if case["id"] == "ADV3")
        result = rr.run_case(case, "full_cie")
        self.assertEqual(result["decision"]["predicted_outcome_class"], "INVALID_EXECUTION")

    def test_the_stagnation_case_does_not_keep_diagnosing(self):
        case = next(case for case in rr.adversarial_cases() if case["id"] == "ADV10")
        result = rr.run_case(case, "full_cie")
        self.assertNotEqual(result["decision"]["switch_action"], "CONTINUE_ATTRIBUTION")

    def test_the_leak_case_forbids_post_hoc_editing(self):
        case = next(case for case in rr.adversarial_cases() if case["id"] == "ADV9")
        self.assertIn("treat_post_hoc_as_prediction",
                      case["evaluation_only"]["forbidden_behaviours"])
        self.assertEqual(rr.leak_scan(case, rr.visible_view(case)), [])

    def test_a_partial_submission_is_not_reported_as_held(self):
        """P0-1 end to end: the frozen set decides, not the submitted subset."""
        case = next(case for case in rr.adversarial_cases() if case["id"] == "ADV11")
        result = rr.run_case(case, "full_cie")
        self.assertEqual(result["decision"]["predicted_outcome_class"], "PARTIALLY_ASSESSED")
        self.assertNotEqual(result["decision"]["predicted_outcome_class"], "PREDICTION_HELD")
        self.assertFalse(result["decision"]["evidence_eligible"])
        self.assertTrue(result["evaluation"]["passed"])
        self.assertNotIn("report_unqualified_result_as_held",
                         result["evaluation"]["violations"])

    def test_an_unknown_execution_keeps_only_the_diagnostic_result(self):
        """P0-2 end to end: the comparison survives, the scientific claim does not."""
        case = next(case for case in rr.adversarial_cases() if case["id"] == "ADV12")
        result = rr.run_case(case, "full_cie")
        self.assertEqual(result["decision"]["diagnostic_outcome_class"], "PREDICTION_HELD")
        self.assertEqual(result["decision"]["predicted_outcome_class"], "UNTESTABLE")
        self.assertFalse(result["decision"]["evidence_eligible"])
        self.assertFalse(result["decision"]["transition_allowed"])
        self.assertTrue(result["evaluation"]["passed"])

    def test_an_unqualified_comparison_is_not_scored_as_evidence(self):
        case = next(case for case in rr.adversarial_cases() if case["id"] == "ADV12")
        result = rr.run_case(case, "full_cie")
        metric = result["evaluation"]["metrics"]["prediction_quality"]
        self.assertIsNone(metric["value"])
        self.assertIn("诊断性比较", metric["reason"])

    def test_reporting_an_unqualified_result_as_held_is_forbidden(self):
        case = next(case for case in rr.adversarial_cases() if case["id"] == "ADV11")
        result = rr.run_case(case, "full_cie")
        forged = clone(result["decision"])
        forged["predicted_outcome_class"] = "PREDICTION_HELD"
        self.assertTrue(rr._behaviour_present("report_unqualified_result_as_held", forged, case))
        forged["evidence_eligible"] = True
        self.assertFalse(rr._behaviour_present("report_unqualified_result_as_held", forged, case))

    def test_correct_stopping_counts_as_success(self):
        case = next(case for case in rr.adversarial_cases() if case["id"] == "ADV4")
        result = rr.run_case(case, "full_cie")
        self.assertEqual(result["evaluation"]["metrics"]["intervention_quality"]["value"], 1.0)
        self.assertTrue(result["evaluation"]["passed"])


# ---------------------------------------------------------------------------
# End-to-end smoke test
# ---------------------------------------------------------------------------

class TestSmoke(unittest.TestCase):

    def test_the_pipeline_runs_end_to_end(self):
        with tempfile.TemporaryDirectory() as temp:
            report = rr.smoke(pathlib.Path(temp))
            self.assertTrue(report["passed"],
                            [step for step in report["steps"] if not step["ok"]])
            steps = {step["step"] for step in report["steps"]}
            for required in ("initialize_state", "build_memory", "freeze_prediction",
                             "inject_synthetic_observation", "choose_next_action",
                             "restart_refuses_bootstrap", "restart_uses_previous_knowledge",
                             "next_round_reads_memory"):
                self.assertIn(required, steps)

    def test_the_smoke_test_leaves_the_state_alone(self):
        with tempfile.TemporaryDirectory() as temp:
            report = rr.smoke(pathlib.Path(temp))
            self.assertTrue(report["canonical_untouched"])

    def test_synthetic_values_are_marked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            rr.smoke(root)
            state = (root / ".research-idea-pipeline" / "routes" / "A"
                     / cg.STATE_NAME).read_text(encoding="utf-8")
            self.assertIn("SYNTHETIC FIXTURE", state)
            brief = (root / ".research-idea-pipeline" / "routes" / "A" / cg.COGNITION_DIRNAME
                     / cg.BRIEF_NAME).read_text(encoding="utf-8")
            self.assertIn("not evidence", brief)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCLI(unittest.TestCase):

    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True, cwd=str(ROOT))

    def test_selftest_passes(self):
        proc = self.run_cli("--selftest")
        self.assertEqual(proc.returncode, rr.EXIT_OK, proc.stdout + proc.stderr)
        self.assertIn("selftest: PASS", proc.stdout)

    def test_validate_show_and_run_a_shipped_case(self):
        case = str(CASES / "adv1.json")
        for command in ("validate", "show", "run"):
            proc = self.run_cli(command, "--case", case)
            self.assertEqual(proc.returncode, rr.EXIT_OK,
                             msg=f"{command}: {proc.stdout}{proc.stderr}")
            self.assertTrue(proc.stdout.strip())

    def test_show_does_not_expose_the_answer(self):
        proc = self.run_cli("show", "--case", str(CASES / "adv1.json"))
        payload = json.loads(proc.stdout)
        self.assertNotIn("hidden", payload)
        self.assertNotIn("answer", payload)

    def test_suite_and_ablate_over_the_shipped_directory(self):
        for command in ("suite", "ablate"):
            proc = self.run_cli(command, "--dir", str(CASES), "--runs", "1")
            self.assertEqual(proc.returncode, rr.EXIT_OK, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(report["cases"], len(rr.adversarial_cases()))

    def test_adversarial_writes_the_cases(self):
        with tempfile.TemporaryDirectory() as temp:
            proc = self.run_cli("adversarial", "--write", temp)
            self.assertEqual(proc.returncode, rr.EXIT_OK, proc.stdout + proc.stderr)
            self.assertEqual(len(list(pathlib.Path(temp).glob("*.json"))),
                             len(rr.adversarial_cases()))

    def test_smoke_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            proc = self.run_cli("smoke", "--work", temp)
            self.assertEqual(proc.returncode, rr.EXIT_OK, proc.stdout + proc.stderr)
            self.assertTrue(json.loads(proc.stdout)["passed"])

    def test_a_missing_case_is_an_environment_error(self):
        self.assertEqual(self.run_cli("validate", "--case", "/nope.json").returncode,
                         rr.EXIT_ENV)

    def test_missing_command_is_an_argument_error(self):
        self.assertEqual(self.run_cli().returncode, rr.EXIT_ERROR)

    def test_a_bad_runner_spec_is_an_environment_error(self):
        proc = self.run_cli("run", "--case", str(CASES / "adv1.json"), "--runner", "junk")
        self.assertEqual(proc.returncode, rr.EXIT_ENV)


if __name__ == "__main__":
    unittest.main()
