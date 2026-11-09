#!/usr/bin/env python3
"""test_rsi_ablation.py — Skill-RSI Phase 9/11 acceptance.

Guards the honesty rules of the ablation report: no composite total, the four frozen arms
keep their identity, leave-one-out arms exist, cost is measured rather than invented, and
L3 is never claimed from synthetic fixtures.
"""

from __future__ import annotations

import json
import unittest

import research_replay as rr
import rsi_ablation as ra


class TestAblationReport(unittest.TestCase):
    def setUp(self):
        self.cases = ra.default_cases()[:5]

    def test_the_core_ladder_covers_baseline_current_cie_and_skill_rsi(self):
        report = ra.ablations(self.cases, runs=1)
        self.assertEqual(set(ra.CORE_ARMS),
                         {"baseline", "memory_only", "memory_prediction", "full_cie",
                          "rsi_full"})
        self.assertTrue(set(ra.CORE_ARMS) <= set(report["core"]["report"]["per_arm"]))

    def test_leave_one_out_arms_isolate_one_mechanism_each(self):
        report = ra.ablations(self.cases, runs=1)
        for arm in ra.LEAVE_ONE_OUT:
            self.assertIn(arm, report["comparisons"])
            self.assertEqual(report["comparisons"][arm]["vs"], "full_cie")
        self.assertEqual(len(ra.LEAVE_ONE_OUT), 5)

    def test_no_composite_total_is_reported(self):
        report = ra.ablations(self.cases, runs=1)
        blob = json.dumps(report, ensure_ascii=False)
        for key in ("total_score", '"overall"', '"weighted"'):
            self.assertNotIn(key, blob)

    def test_undifferentiated_arms_are_reported_not_hidden(self):
        report = ra.ablations(self.cases, runs=1)
        self.assertIn("undifferentiated_arms", report["core"])

    def test_the_report_states_the_limits_and_the_no_support_rule(self):
        report = ra.ablations(self.cases, runs=1)
        self.assertTrue(any("合成" in item for item in report["limitations"]))
        self.assertIn("NO_SUPPORT", report["reading"])

    def test_unobservable_decisions_are_surfaced(self):
        report = ra.ablations([rr.adversarial_cases()[0]], runs=1)
        self.assertIn("unobservable_decisions", report["core"])


class TestPolicyProbes(unittest.TestCase):
    """The shipped cases carry no policy, so the probe sets are how the mechanism is measured."""

    def setUp(self):
        self.cases = ra.default_cases()[:6]

    def test_probes_attach_a_promoted_scoped_policy(self):
        probes = ra.rsi_probe_cases(self.cases)
        self.assertTrue(probes)
        candidate = probes[0]["visible"]["policy_candidates"][0]
        self.assertEqual(candidate["status"], "ACTIVE")
        self.assertTrue(candidate["scope"])
        self.assertTrue(candidate["evaluation_refs"][0]["independent"])

    def test_the_probe_prefers_an_action_the_control_arm_did_not_choose(self):
        probes = ra.rsi_probe_cases(self.cases)
        for probe in probes:
            preferred = probe["visible"]["policy_candidates"][0]["strategy_changes"][0][
                "prefer_action"]
            baseline = rr.cie_offline_runner(rr.visible_view(probe), "full_cie")
            self.assertNotEqual(preferred, baseline.get("chosen_intervention"))

    def test_the_plain_report_is_kept_alongside_the_probe_report(self):
        report = ra.ablations(self.cases, runs=1)
        self.assertIsNotNone(report["core"])
        self.assertIn("with_policy_candidates", report)
        self.assertIsNotNone(report["with_policy_candidates"]["report"])

    def test_each_guard_variant_isolates_one_missing_guard(self):
        report = ra.ablations(self.cases, runs=1)
        variants = report["with_policy_candidates"]["guard_probes"]["variants"]
        self.assertEqual(set(variants),
                         {"unpromoted", "unscoped", "unsupported", "unevaluated"})
        self.assertIn("rsi_without_promotion", variants["unpromoted"]["diverging_arms"])
        self.assertIn("rsi_without_scope", variants["unscoped"]["diverging_arms"])
        self.assertIn("rsi_without_trajectory", variants["unsupported"]["diverging_arms"])
        self.assertIn("rsi_without_replay", variants["unevaluated"]["diverging_arms"])

    def test_the_shadow_arm_is_a_true_no_op(self):
        report = ra.ablations(self.cases, runs=1)
        probes = ra.rsi_probe_cases(self.cases)
        shadow = rr.run_suite(probes, ("full_cie", "rsi_shadow"), 1)
        self.assertEqual(shadow["per_arm"]["rsi_shadow"]["dimensions"],
                         shadow["per_arm"]["full_cie"]["dimensions"])

    def test_a_policy_that_degrades_science_is_not_reported_as_an_improvement(self):
        report = ra.ablations(self.cases, runs=1)
        comparison = report["with_policy_candidates"]["skill_rsi_vs_current_cie"]
        degraded = [name for name, block in comparison["dimensions"].items()
                    if block.get("status") == "DISTINGUISHABLE" and block.get("delta", 0) < 0]
        if degraded:
            self.assertFalse(comparison.get("improvement_claimed", False))


class TestOverhead(unittest.TestCase):
    def test_cost_is_measured_and_no_token_count_is_fabricated(self):
        report = ra.overhead_report(iterations=5)
        self.assertGreater(report["prompt_bytes"], 0)
        self.assertGreater(report["trajectory_record_bytes"], 0)
        self.assertGreater(report["policy_candidate_bytes"], 0)
        self.assertGreaterEqual(report["signature_latency_us"], 0)
        self.assertGreaterEqual(report["context_build_latency_us"], 0)
        self.assertNotIn("tokens", report)
        self.assertIn("没有可用的离线 token 计数器", " ".join(report["notes"]))

    def test_the_new_modules_are_counted(self):
        report = ra.overhead_report(iterations=5)
        self.assertGreater(report["new_module_lines"], 0)
        self.assertIn("policy_evolution.py", report["module_lines"])


class TestLevels(unittest.TestCase):
    def test_l1_and_l2_are_verified_and_l3_is_not_claimed(self):
        levels = ra.level_report()
        self.assertEqual(levels["L1_implementation_validity"]["status"], "VERIFIED")
        self.assertEqual(levels["L2_operational_validity"]["status"], "VERIFIED")
        self.assertEqual(levels["L3_research_improvement"]["status"], "NOT_VERIFIED")
        self.assertIn("真实科研案例", levels["L3_research_improvement"]["reason"])

    def test_the_four_states_are_explicitly_not_conflated(self):
        levels = ra.level_report()
        self.assertEqual(levels["must_not_conflate"],
                         ["策略候选已生成", "策略已被应用", "科研行为已改变",
                          "科研能力获得独立证据支持的改善"])

    def test_l3_can_only_be_claimed_with_supplied_evidence(self):
        levels = ra.level_report(l3_evidence=[{"project": "X", "verdict": "SUPPORTED"}])
        self.assertEqual(levels["L3_research_improvement"]["status"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()
