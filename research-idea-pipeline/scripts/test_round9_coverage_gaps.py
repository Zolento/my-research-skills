#!/usr/bin/env python3
"""test_round9_coverage_gaps.py — 关闭子代理 D（R8-D-test-quality）报告的存活变异。

`research-idea-pipeline/.dev/audit/R8-D-test-quality.md` 在 `dda4fe3` 上重放 43 个变异，
**12 个仍存活**：即这些保护一旦被削弱，测试套件不会报警。本文件为每个存活变异补一条
能杀死它的测试（并顺带修正被点名的空转测试）。

对应关系：
  D-1  L3 凭证缺少 `isolation_verified` 键（而不仅是显式 False）
  D-2  晋升时重审必须使用**冻结**规则，而不是编译期默认规则
  D-3  区间重叠的"收益"不得计为确证收益（原测试是空转的）
  D-4  `audit_report` 的跨臂 case 集合检查（经 `evaluate_candidate`）
  D-5  `audit_report` 的 `cases × runs` 记录数检查（经 `evaluate_candidate`）
  D-6  非 SUPPORTED 的 L3 凭证在**已有批准**时也不得落盘
  D-7  试运行等级必须考虑 `budget_expanded` / `hard_gates_unchanged`
  D-8  批准的策略签名/规则绑定不得被忽略
  D-9  global 作用域在 `evaluation_refs` 为空时也必须要求 ≥2 个背书项目
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

import cognition as cg
import policy_evolution as pe
import research_replay as rr
import rsi_test_support as support

BENEFIT = "search_efficiency"
SCIENCE = "mechanistic_understanding"


class CoverageCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.route = pathlib.Path(self.temp.name) / "A"
        self.route.mkdir(parents=True)
        self.workdir = pathlib.Path(self.temp.name) / "work"
        self.state_path = self.route / cg.STATE_NAME
        self.state_path.write_text(json.dumps({
            "_schema": "research-idea-pipeline/research-state@1", "state_version": 3,
            "contract": {"goal": "g", "primary_anchor": "A0", "constraints": [],
                         "resources": {}, "out_of_scope": []},
            "claims": [], "evidence": [], "assumptions": [],
            "hypotheses": [{"id": "H1", "statement": "h", "status": "active",
                            "validity": "valid", "island": "P1", "operator": "reframe"}],
            "experiments": [], "literature": [], "failures": [],
            "uncertainties": [{"id": "U1", "question": "q", "importance": "high",
                               "uncertainty": "high", "status": "open", "validity": "valid"}],
            "assurance": [], "repairs": [], "narrative_view": {}, "reviews": [],
            "decision": {"verdict": "continue", "rationale": "", "next_phase": "R3"}},
            ensure_ascii=False) + "\n", encoding="utf-8")
        self.digest = pe.freeze_evaluation_rules(self.state_path)["digest"]

    def tearDown(self):
        self.temp.cleanup()

    def _report(self, *, candidate_shift=0.5, control_shift=-0.05, cases=4, runs=2):
        report = rr.run_suite(rr.adversarial_cases()[:cases], arms=["rsi_full", "full_cie"],
                              runs=runs)
        for arm, shift in (("rsi_full", candidate_shift), ("full_cie", control_shift)):
            for row in report["per_arm"][arm]["results"]:
                row["evaluation"]["metrics"][BENEFIT] = {"value": round(0.5 + shift, 4)}
            block = report["per_arm"][arm]
            block["dimensions"] = {}
            for name in rr.METRIC_DIMENSIONS:
                values = [row["evaluation"]["metrics"][name]["value"] for row in block["results"]
                          if row["evaluation"]["metrics"][name]["value"] is not None]
                block["dimensions"][name] = {
                    "mean": round(sum(values) / len(values), 4) if values else None,
                    "min": min(values) if values else None,
                    "max": max(values) if values else None}
        return report

    def ready(self, policy_id="P-1", **overrides):
        payload = {"policy_id": policy_id, "policy_schema_version": "1",
                   "parent_policy_id": None, "status": "PROPOSED",
                   "scope": {"scope_kind": "local", "problem_structure": "reframe-loop"},
                   "applicable_conditions": [{"kind": "min_open_uncertainties", "value": 1}],
                   "strategy_changes": [{"kind": "same_tier_preference", "prefer_action": "R2"}],
                   "supporting_trajectory_ids": ["DT-1"], "counterexamples": ["c"],
                   "expected_effect": {"mechanism": "m", "direction": "up"},
                   "revalidation_conditions": ["r"], "evaluation_refs": [],
                   "rollback_target": None, "evaluation_rules_digest": self.digest}
        payload.update(overrides)
        assert pe.propose(self.state_path, payload,
                          trajectory_support={"DT-1"})["status"] == "PROPOSED"
        assert pe.transition(self.state_path, policy_id, "SHADOW",
                             level="L1")["status"] == "SHADOW"
        assert pe.evaluate_candidate(self.state_path, policy_id,
                                     self._report())["status"] == "REPLAY_EVALUATED"
        assert support.begin_trial(self.state_path, policy_id)["status"] \
            == "BOUNDED_TRIAL"
        return policy_id

    def shadow(self, policy_id="P-1"):
        """A policy that is only at SHADOW, so evaluate_candidate can be driven directly."""
        payload = {"policy_id": policy_id, "policy_schema_version": "1",
                   "parent_policy_id": None, "status": "PROPOSED",
                   "scope": {"scope_kind": "local", "problem_structure": "reframe-loop"},
                   "applicable_conditions": [{"kind": "min_open_uncertainties", "value": 1}],
                   "strategy_changes": [{"kind": "same_tier_preference", "prefer_action": "R2"}],
                   "supporting_trajectory_ids": ["DT-1"], "counterexamples": ["c"],
                   "expected_effect": {"mechanism": "m", "direction": "up"},
                   "revalidation_conditions": ["r"], "evaluation_refs": [],
                   "rollback_target": None, "evaluation_rules_digest": self.digest}
        assert pe.propose(self.state_path, payload,
                          trajectory_support={"DT-1"})["status"] == "PROPOSED"
        assert pe.transition(self.state_path, policy_id, "SHADOW",
                             level="L1")["status"] == "SHADOW"
        return policy_id

    def signature(self, policy_id="P-1"):
        return pe.policy_record(pe.load_records(self.state_path)[0], policy_id)["signature"]

    def credential(self, policy_id="P-1", **overrides):
        kwargs = {"signature": self.signature(policy_id),
                  "rules_digest": pe.evaluation_rules_digest(self.state_path)}
        kwargs.update(overrides)
        return support.research_validation(self.state_path, policy_id, self.workdir, **kwargs)

    def stored_artifact(self, policy_id="P-1"):
        records, _ = pe.load_records(self.state_path)
        return pe.latest_evaluation_artifact(self.state_path, policy_id, records)

    def _rewrite_transition_ref(self, forged_digest):
        import decision_trajectory as dt
        path = pe.candidates_path(self.state_path)
        out, previous = [], None
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("record") == "transition" and record.get("to") == "VALIDATED":
                record["evidence"]["evaluation_ref"]["digest"] = forged_digest
            record = dict(record)
            record["seq"] = len(out) + 1
            record["previous"] = previous
            out.append(record)
            previous = dt._digest(record)
        path.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
                                for item in out), encoding="utf-8")
        dt.head_path(path).write_text(dt._digest(out[-1]), encoding="ascii")

    def _reseal(self, document):
        document["digest"] = cg.digest_of({k: v for k, v in document.items()
                                           if k != "digest"})
        return document


# ---------------------------------------------------------------------------
# D-1 / D-6: the credential must carry explicit proofs
# ---------------------------------------------------------------------------

class TestExplicitProofs(CoverageCase):
    def test_a_missing_isolation_key_is_refused_even_with_an_approval(self):
        """D-1: only explicit `isolation_verified: true` counts; a missing key does not."""
        self.ready()
        credential = self.credential()
        for arm in credential["per_arm"].values():
            for row in arm["results"]:
                row.pop("isolation_verified")
        support.approve(self.state_path, "P-1", credential)
        result = pe.record_research_validation(self.state_path, "P-1", credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("隔离", " ".join(result["diagnostics"]))

    def test_a_rejected_credential_with_an_approval_leaves_no_artifact(self):
        """D-6: the non-SUPPORTED refusal must fire before the artifact is stored."""
        self.ready()
        credential = self.credential()
        for row in credential["per_arm"]["policy"]["results"]:
            row["evaluation"]["metrics"][SCIENCE] = {"value": 0.1}   # reliability regression
        support.approve(self.state_path, "P-1", credential)
        before = sorted(path.name for path in pe.evaluations_dir(self.state_path).glob("*.json"))
        result = pe.record_research_validation(self.state_path, "P-1", credential)
        after = sorted(path.name for path in pe.evaluations_dir(self.state_path).glob("*.json"))
        self.assertEqual(result["status"], "INVALID", result)
        self.assertEqual(before, after, "a rejected credential was stored")
        # the refusal must come from the credential check itself, not from the later gate
        # (the discard safety net would hide a regression here)
        self.assertIn("科研验证结论是", " ".join(result["diagnostics"]))


# ---------------------------------------------------------------------------
# D-2: the promotion re-audit uses the frozen rules
# ---------------------------------------------------------------------------

class TestFrozenRulesAtPromotion(CoverageCase):
    def test_the_promotion_re_audit_uses_the_frozen_tolerance(self):
        """D-2: a 0.3 gap is not a benefit under a frozen tolerance of 0.5."""
        pe.rules_path(self.state_path).unlink()
        rules = dict(pe.DEFAULT_EVALUATION_RULES)
        rules["delta_tolerance"] = 0.5
        self.digest = pe.freeze_evaluation_rules(self.state_path, rules)["digest"]
        self.ready()
        credential = self.credential()
        support.approve(self.state_path, "P-1", credential)
        self.assertEqual(pe.record_research_validation(self.state_path, "P-1",
                                                       credential)["status"], "VALIDATED")
        artifact = self.stored_artifact()
        path = pathlib.Path(artifact["ref"]["path"])
        document = json.loads(path.read_text(encoding="utf-8"))

        def rewrite(per_arm):
            for arm, mean in (("policy", 0.35), ("control", 0.05)):
                block = per_arm[arm]
                for row in block["results"]:
                    row["evaluation"]["metrics"][BENEFIT] = {"value": mean}
                if "dimensions" in block:      # only the normalized report carries a summary
                    block["dimensions"][BENEFIT] = {"mean": mean, "min": mean, "max": mean}

        rewrite(document["credential"]["per_arm"])
        rewrite(document["report"]["per_arm"])
        self._reseal(document)
        path.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n",
                        encoding="utf-8")
        self._rewrite_transition_ref(document["digest"])
        support.approve(self.state_path, "P-1", document["credential"])
        result = pe.promote_to_active(self.state_path, "P-1", {"scope_evidence_ok": True})
        self.assertEqual(result["status"], "INVALID", result)
        # Only a frozen tolerance of 0.5 makes a 0.3 gap non-beneficial; the default (0.05)
        # would call it a benefit, so this message proves the frozen rules were used.
        self.assertIn("UNDIFFERENTIATED", " ".join(result["diagnostics"]))


# ---------------------------------------------------------------------------
# D-3: overlapping ranges are not a confirmed benefit
# ---------------------------------------------------------------------------

class TestOverlapIsUncertain(CoverageCase):
    def _arm(self, mean, low, high):
        return {"dimensions": {name: {"mean": mean, "min": low, "max": high}
                               for name in rr.METRIC_DIMENSIONS},
                "results": [], "evidence_support": {}}

    def test_an_overlapping_gap_is_reported_as_uncertain_not_as_a_benefit(self):
        """D-3: the declared caveat must actually stop the dimension counting as a benefit."""
        report = {"schema": "research-idea-pipeline/replay-ablation@1", "cases": 3,
                  "runs_per_case": 2, "runner": "test harness", "sufficient_sample": True,
                  "unobservable_decisions": 0, "delta_vs_baseline": {},
                  "per_arm": {"rsi_full": self._arm(0.9, 0.10, 1.00),
                              "full_cie": self._arm(0.3, 0.00, 0.90)}}
        for arm in report["per_arm"].values():
            arm["results"] = [{"case_id": f"C{i}", "leak_checked": True,
                               "isolation_verified": True,
                               "evaluation": {"metrics": {name: {"value": 0.5}
                                                          for name in rr.METRIC_DIMENSIONS},
                                              "evidence_support": {"class": "OBSERVED"}}}
                              for i in range(3)] * 2
        outcome = pe.ablation_verdict(report, rules=pe.DEFAULT_EVALUATION_RULES)
        block = outcome["comparison"]["dimensions"][BENEFIT]
        self.assertTrue(block["overlapping"], block)
        self.assertFalse(block["confident"], block)
        self.assertIn(BENEFIT, outcome["uncertain_benefit"], outcome)
        self.assertNotIn(BENEFIT, outcome["benefit_dimensions"], outcome)
        self.assertNotEqual(outcome["verdict"], "SUPPORTED", outcome)


# ---------------------------------------------------------------------------
# D-4 / D-5: audit_report consistency checks through evaluate_candidate
# ---------------------------------------------------------------------------

class TestAuditReportChecks(CoverageCase):
    def test_arms_with_different_case_sets_are_refused(self):
        """D-4: the cross-arm case-set check in audit_report."""
        self.shadow()
        report = self._report()
        for index, row in enumerate(report["per_arm"]["full_cie"]["results"]):
            row["case_id"] = f"W{index % 4}"
        result = pe.evaluate_candidate(self.state_path, "P-1", report)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("case 集合", " ".join(result["diagnostics"]))

    def test_a_record_count_mismatch_is_refused(self):
        """D-5: distinct case ids stay correct while len(results) != cases x runs."""
        self.shadow()
        report = self._report()
        report["runs_per_case"] = 3          # 4 cases x 3 = 12 expected, only 8 present
        result = pe.evaluate_candidate(self.state_path, "P-1", report)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("执行记录数", " ".join(result["diagnostics"]))


# ---------------------------------------------------------------------------
# D-7 / D-8 / D-9
# ---------------------------------------------------------------------------

class TestLevelAndBinding(CoverageCase):
    def test_the_trial_level_honours_budget_and_hard_gate_flags(self):
        """D-7: a trial that expanded the budget is not L2 evidence."""
        bad = pe._recomputed_level({"dispatch_record": True, "budget_expanded": True,
                                    "hard_gates_unchanged": True},
                                   {"verdict": "DISPATCHED"}, schema=pe.SCHEMA_TRIAL)
        self.assertEqual(bad, "L1", bad)
        bad_gates = pe._recomputed_level({"dispatch_record": True, "budget_expanded": False,
                                          "hard_gates_unchanged": False},
                                         {"verdict": "DISPATCHED"}, schema=pe.SCHEMA_TRIAL)
        self.assertEqual(bad_gates, "L1", bad_gates)
        good = pe._recomputed_level({"dispatch_record": True, "budget_expanded": False,
                                     "hard_gates_unchanged": True},
                                    {"verdict": "DISPATCHED"}, schema=pe.SCHEMA_TRIAL)
        self.assertEqual(good, "L2", good)

    def test_the_approval_signature_and_rules_binding_are_enforced(self):
        """D-8: an approval for another signature or another rule set does not authorise."""
        self.ready()
        credential = self.credential()
        support.approve(self.state_path, "P-1", credential)
        digest = cg.digest_of(credential)
        self.assertEqual(pe.approval_errors(self.state_path, policy_id="P-1",
                                            credential_digest=digest,
                                            signature=self.signature("P-1"),
                                            rules_digest=self.digest), [])
        other_signature = pe.approval_errors(self.state_path, policy_id="P-1",
                                             credential_digest=digest,
                                             signature="sha256:another-policy",
                                             rules_digest=self.digest)
        self.assertTrue(any("策略版本" in item.render() for item in other_signature),
                        [item.render() for item in other_signature])
        other_rules = pe.approval_errors(self.state_path, policy_id="P-1",
                                         credential_digest=digest,
                                         signature=self.signature("P-1"),
                                         rules_digest="sha256:another-rules")
        self.assertTrue(any("评价规则" in item.render() for item in other_rules),
                        [item.render() for item in other_rules])

    def test_a_global_scope_with_no_declared_projects_still_needs_attestation(self):
        """D-9: an empty evaluation_refs list must not skip the attested-project gate."""
        self.ready("P-GLOBAL", scope={"scope_kind": "global",
                                      "problem_structure": "reframe-loop"},
                   evaluation_refs=[])
        credential = self.credential("P-GLOBAL")
        support.approve(self.state_path, "P-GLOBAL", credential)
        self.assertEqual(pe.record_research_validation(self.state_path, "P-GLOBAL",
                                                       credential)["status"], "VALIDATED")
        result = pe.promote_to_active(self.state_path, "P-GLOBAL",
                                      {"scope_evidence_ok": True})
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("PE14", result["codes"])


if __name__ == "__main__":
    unittest.main()
