#!/usr/bin/env python3
"""test_l3_trust_boundary.py — 第八轮：L3 信任边界、对照公平性与对抗路径。

三项要求：

一、L3 信任边界
  运行中的 Research Agent **不得**仅凭自己生成的文件、标记、摘要和引用自主获得可信 L3。
  文件完整性（digest 自洽）≠ 证据真实性（外部真的执行过）≠ 评价独立性（执行者彼此独立）。
  既然无法可靠区分独立验证者，生产路径**必须要求人工批准**；
  且不得把 `synthetic=false` / `executor` 名称 / `isolation_verified=true` 当作充分真实性证明。

二、实验对照公平性
  A/B 两臂在模型、Harness、工具、任务、可见数据、预算与评价规则上必须等价；
  必须区分**执行实例身份**（两臂必须不同）与**执行环境差异**（受控轴必须相同）；
  每次 L3 评价要留下可复核的配对任务、资源预算与策略版本。

三、对抗路径
  伪造任务来源、内部自洽的假执行凭证、重复使用派遣记录、伪造 executor 身份、
  篡改策略与凭证绑定 —— 每条都必须给出**明确的拒绝原因**。

这些测试针对旧版会通过的路径，修复前应当失败。
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

DIMENSIONS = rr.METRIC_DIMENSIONS
BENEFIT = "search_efficiency"
SCIENCE = "mechanistic_understanding"


def fixture_state(version=3):
    return {"_schema": "research-idea-pipeline/research-state@1", "state_version": version,
            "contract": {"goal": "g", "primary_anchor": "A0", "constraints": [],
                         "resources": {}, "out_of_scope": []},
            "claims": [], "evidence": [], "assumptions": [],
            "hypotheses": [{"id": "H1", "statement": "h", "status": "active",
                            "validity": "valid", "island": "P1", "operator": "reframe"}],
            "experiments": [], "literature": [], "failures": [],
            "uncertainties": [{"id": "U1", "question": "q", "importance": "high",
                               "uncertainty": "high", "status": "open", "validity": "valid"}],
            "assurance": [], "repairs": [], "narrative_view": {}, "reviews": [],
            "decision": {"verdict": "continue", "rationale": "", "next_phase": "R3"}}


class L3Case(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.route = pathlib.Path(self.temp.name) / "A"
        self.route.mkdir(parents=True)
        self.workdir = pathlib.Path(self.temp.name) / "work"
        self.state_path = self.route / cg.STATE_NAME
        self.state_path.write_text(json.dumps(fixture_state(), ensure_ascii=False) + "\n",
                                   encoding="utf-8")
        self.digest = pe.freeze_evaluation_rules(self.state_path)["digest"]

    def tearDown(self):
        self.temp.cleanup()

    def ready(self, policy_id="P-1"):
        payload = {"policy_id": policy_id, "policy_schema_version": "1",
                   "parent_policy_id": None, "status": "PROPOSED",
                   "scope": {"scope_kind": "local", "problem_structure": "reframe-loop"},
                   "applicable_conditions": [{"kind": "min_open_uncertainties", "value": 1}],
                   "strategy_changes": [{"kind": "same_tier_preference",
                                         "prefer_action": "R2"}],
                   "supporting_trajectory_ids": ["DT-1"], "counterexamples": ["c"],
                   "expected_effect": {"mechanism": "m", "direction": "up"},
                   "revalidation_conditions": ["r"], "evaluation_refs": [],
                   "rollback_target": None, "evaluation_rules_digest": self.digest}
        assert pe.propose(self.state_path, payload,
                          trajectory_support={"DT-1"})["status"] == "PROPOSED"
        assert pe.transition(self.state_path, policy_id, "SHADOW",
                             level="L1")["status"] == "SHADOW"
        report = self._report()
        assert pe.evaluate_candidate(self.state_path, policy_id,
                                     report)["status"] == "REPLAY_EVALUATED"
        assert support.begin_trial(self.state_path, policy_id)["status"] \
            == "BOUNDED_TRIAL"
        return policy_id

    def _report(self):
        """A record-consistent replay report whose benefit dimension improves."""
        report = rr.run_suite(rr.adversarial_cases()[:4],
                              arms=["rsi_full", "full_cie"], runs=2)
        for arm, shift in (("rsi_full", 0.5), ("full_cie", -0.05)):
            for row in report["per_arm"][arm]["results"]:
                row["evaluation"]["metrics"][BENEFIT] = {"value": round(0.5 + shift, 4)}
            block = report["per_arm"][arm]
            block["dimensions"] = {}
            for name in rr.METRIC_DIMENSIONS:
                values = [row["evaluation"]["metrics"][name]["value"]
                          for row in block["results"]
                          if row["evaluation"]["metrics"][name]["value"] is not None]
                block["dimensions"][name] = {
                    "mean": round(sum(values) / len(values), 4) if values else None,
                    "min": min(values) if values else None,
                    "max": max(values) if values else None}
        self.case_ids = sorted({row["case_id"] for row in
                                report["per_arm"]["rsi_full"]["results"]})
        # The L3 tasks are a separate, real execution; the replay fixtures are L2 evidence.""
        return report

    def signature(self, policy_id="P-1"):
        return pe.policy_record(pe.load_records(self.state_path)[0], policy_id)["signature"]

    def credential(self, policy_id="P-1", **overrides):
        kwargs = {"signature": self.signature(policy_id),
                  "rules_digest": pe.evaluation_rules_digest(self.state_path)}
        kwargs.update(overrides)
        return support.research_validation(self.state_path, policy_id, self.workdir, **kwargs)

    def approve(self, credential, policy_id="P-1", **kwargs):
        return support.approve(self.state_path, policy_id, credential, **kwargs)

    def record(self, credential, policy_id="P-1"):
        return pe.record_research_validation(self.state_path, policy_id, credential)


# ---------------------------------------------------------------------------
# 一、L3 信任边界：文件完整性 ≠ 真实性 ≠ 独立性
# ---------------------------------------------------------------------------

class TestNoSelfGrantedL3(L3Case):
    def test_a_self_consistent_credential_without_human_approval_is_refused(self):
        """Every field the agent controls (synthetic=false, two executor names, isolation
        flags, self-consistent digests) is still not an independent verifier."""
        self.ready()
        credential = self.credential()          # internally consistent, all flags set
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("PE15", result["codes"])
        self.assertIn("人工批准", " ".join(result["diagnostics"]))

    def test_flags_alone_are_never_accepted_as_authenticity(self):
        self.ready()
        credential = self.credential(synthetic=False, executor="external-reviewer-1",
                                     control_executor="external-reviewer-2")
        self.assertIs(credential["task_provenance"]["synthetic"], False)
        self.assertNotEqual(credential["per_arm"]["policy"]["executor"],
                            credential["per_arm"]["control"]["executor"])
        self.assertTrue(all(row["isolation_verified"] is True
                            for arm in credential["per_arm"].values()
                            for row in arm["results"]))
        self.assertEqual(self.record(credential)["status"], "INVALID")

    def test_the_automated_path_never_writes_an_approval(self):
        self.ready()
        self.assertFalse(len(pe.approval_events(self.state_path)),
                         "an automated entry wrote an approval")

    def test_an_approval_for_another_credential_does_not_authorize_this_one(self):
        self.ready()
        other = self.credential(benefit_policy=0.95)
        self.approve(other)
        result = self.record(self.credential())
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("人工批准", " ".join(result["diagnostics"]))

    def test_an_approval_with_a_non_positive_lifetime_is_refused(self):
        """An approval cannot be recorded already expired."""
        self.ready()
        outcome = self.approve(self.credential(), expires_in_seconds=-1)
        self.assertEqual(outcome["status"], "INVALID", outcome)
        self.assertIn("有效期", " ".join(outcome["diagnostics"]))

    def test_an_expired_approval_does_not_authorize(self):
        import time
        from unittest import mock
        self.ready()
        credential = self.credential()
        self.approve(credential, expires_in_seconds=60)
        with mock.patch("time.time", return_value=time.time() + 3600):
            result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("过期", " ".join(result["diagnostics"]))

    def test_approval_requires_an_explicit_human_confirmation(self):
        self.ready()
        credential = self.credential()
        outcome = self.approve(credential, confirm_human=False)
        self.assertEqual(outcome["status"], "INVALID", outcome)
        self.assertIn("确认", " ".join(outcome["diagnostics"]))
        self.assertEqual(self.record(credential)["status"], "INVALID")

    def test_an_approver_identity_is_required(self):
        self.ready()
        outcome = self.approve(self.credential(), approver="")
        self.assertEqual(outcome["status"], "INVALID", outcome)

    def test_an_approval_for_a_nonexistent_policy_is_refused(self):
        self.ready()
        outcome = pe.approve_l3(self.state_path, policy_id="P-GHOST",
                                credential={"policy_id": "P-GHOST"}, approver="someone",
                                confirm_human=True)
        self.assertEqual(outcome["status"], "INVALID", outcome)
        self.assertIn("PE1", outcome["codes"])
        self.assertFalse(pe.approval_events(self.state_path))

    def test_a_symlinked_approval_ledger_is_refused(self):
        """The approval must stay inside the route; a symlinked ledger escapes it."""
        import os
        self.ready()
        credential = self.credential()
        outside = pathlib.Path(self.temp.name) / "elsewhere"
        outside.mkdir()
        os.symlink(outside, pe.approvals_dir(self.state_path))
        outcome = self.approve(credential)
        self.assertEqual(outcome["status"], "INVALID", outcome)
        self.assertIn("PE15", outcome["codes"])

    def test_an_approved_credential_reaches_validated_and_active(self):
        self.ready()
        credential = self.credential()
        self.approve(credential)
        result = self.record(credential)
        self.assertEqual(result["status"], "VALIDATED", result)
        active = pe.promote_to_active(self.state_path, "P-1", {"scope_evidence_ok": True})
        self.assertEqual(active["status"], "ACTIVE", active)
        self.assertEqual(active["level"], "L3", active)

    def test_promotion_reverifies_the_approval(self):
        """VALIDATED is not a blank cheque: ACTIVE re-reads the approval ledger."""
        self.ready()
        credential = self.credential()
        self.approve(credential, expires_in_seconds=-1)
        self.assertEqual(self.record(credential)["status"], "INVALID")
        # approve properly, validate, then make the approval expire before promotion
        credential = self.credential()
        self.approve(credential)
        self.assertEqual(self.record(credential)["status"], "VALIDATED")
        ledger = pe.approvals_dir(self.state_path) / "events.jsonl"
        events = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        for event in events:
            event["expires_at"] = -1
        ledger.write_text("\n".join(json.dumps(event, ensure_ascii=False)
                                    for event in events) + "\n", encoding="utf-8")
        result = pe.promote_to_active(self.state_path, "P-1", {"scope_evidence_ok": True})
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("PE15", result["codes"])

    def test_a_rollback_restore_after_the_approval_expired_is_refused(self):
        """A time-bound approval must not be bypassed by restoring a superseded policy."""
        import time
        from unittest import mock
        for policy_id in ("P-1", "P-2"):
            self.ready(policy_id)
            credential = self.credential(policy_id)
            self.approve(credential, policy_id)
            self.assertEqual(self.record(credential, policy_id)["status"], "VALIDATED")
            self.assertEqual(pe.promote_to_active(self.state_path, policy_id,
                                                  {"scope_evidence_ok": True})["status"],
                             "ACTIVE")
        future = time.time() + 10 ** 7
        with mock.patch("time.time", return_value=future):
            result = pe.rollback(self.state_path, "P-2", to_policy_id="P-1",
                                 reason="recovery")
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("PE15", result["codes"])
        # and nothing was written: the rollback pre-validates the restore
        statuses = pe.latest_status(pe.load_records(self.state_path)[0])
        self.assertEqual(statuses["P-2"], "ACTIVE", statuses)
        self.assertEqual(statuses["P-1"], "SUPERSEDED", statuses)

    def test_a_rollback_restore_with_a_valid_approval_still_works(self):
        for policy_id in ("P-1", "P-2"):
            self.ready(policy_id)
            credential = self.credential(policy_id)
            self.approve(credential, policy_id)
            self.assertEqual(self.record(credential, policy_id)["status"], "VALIDATED")
            self.assertEqual(pe.promote_to_active(self.state_path, policy_id,
                                                  {"scope_evidence_ok": True})["status"],
                             "ACTIVE")
        result = pe.rollback(self.state_path, "P-2", to_policy_id="P-1", reason="recovery")
        self.assertEqual(result["status"], "ROLLED_BACK", result)
        statuses = pe.latest_status(pe.load_records(self.state_path)[0])
        self.assertEqual(statuses["P-1"], "ACTIVE", statuses)

    def test_a_tampered_approval_ledger_is_refused(self):
        self.ready()
        credential = self.credential()
        self.approve(credential)
        ledger = pe.approvals_dir(self.state_path) / "events.jsonl"
        event = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
        event["approver"] = "someone-else"
        ledger.write_text(json.dumps(event, ensure_ascii=False) + "\n", encoding="utf-8")
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("PE15", result["codes"])


# ---------------------------------------------------------------------------
# 二、对照公平性
# ---------------------------------------------------------------------------

class TestComparisonFairness(L3Case):
    def _recorded(self, **overrides):
        self.ready()
        credential = self.credential(**overrides)
        self.approve(credential)
        return self.record(credential)

    def test_a_controlled_axis_difference_is_refused(self):
        self.ready()
        credential = self.credential(
            equivalence_off=True,
            equivalence_record=support.equivalence(
                axis_overrides={"control": {"model": "model-b"}}))
        self.approve(credential)
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("model", " ".join(result["diagnostics"]))

    def test_an_undeclared_environment_difference_is_refused(self):
        self.ready()
        credential = self.credential(
            equivalence_off=True,
            equivalence_record=support.equivalence(
                axis_overrides={"control": {"tools": ["runner", "extra-tool"]}}))
        self.approve(credential)
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("tools", " ".join(result["diagnostics"]))

    def test_an_undeclared_extra_environment_axis_is_refused(self):
        """Every changed variable must be declared as a contrast, as execution_gate requires."""
        self.ready()
        record = support.equivalence()
        record["arms"]["control"]["environment"]["extra_axis"] = "different-model"
        credential = self.credential(equivalence_off=True, equivalence_record=record)
        self.approve(credential)
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("extra_axis", " ".join(result["diagnostics"]))

    def test_a_contrast_that_does_not_differ_is_refused(self):
        self.ready()
        record = support.equivalence()
        record["arms"]["control"]["environment"]["strategy"] = \
            record["arms"]["policy"]["environment"]["strategy"]
        credential = self.credential(equivalence_off=True, equivalence_record=record)
        self.approve(credential)
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("对照", " ".join(result["diagnostics"]))

    def test_the_same_execution_instance_for_both_arms_is_refused(self):
        """Execution instance identity must differ even when the environment is equal."""
        self.ready()
        credential = self.credential(
            equivalence_off=True,
            equivalence_record=support.equivalence(control_instance="run-policy-1"))
        self.approve(credential)
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("执行实例", " ".join(result["diagnostics"]))

    def test_a_missing_equivalence_record_is_refused(self):
        self.ready()
        credential = self.credential(equivalence_off=True)
        self.approve(credential)
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("equivalence", " ".join(result["diagnostics"]))

    def test_a_missing_required_axis_is_refused(self):
        self.ready()
        record = support.equivalence()
        del record["arms"]["policy"]["environment"]["budget"]
        del record["arms"]["control"]["environment"]["budget"]
        credential = self.credential(equivalence_off=True, equivalence_record=record)
        self.approve(credential)
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("budget", " ".join(result["diagnostics"]))

    def test_paired_task_ids_must_match_the_executed_cases(self):
        self.ready()
        record = support.equivalence(task_ids=["T0", "T1", "T2", "T9"])
        credential = self.credential(equivalence_off=True, equivalence_record=record)
        self.approve(credential)
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("配对任务", " ".join(result["diagnostics"]))

    def test_a_fair_credential_records_tasks_budget_and_policy_version(self):
        self.ready()
        credential = self.credential(
            equivalence_off=True,
            equivalence_record=support.equivalence(
                task_ids=["T0", "T1", "T2"], budget={"hours": 4, "runs": 2},
                policy_instance="run-policy-1", control_instance="run-control-2"))
        self.approve(credential)
        self.assertEqual(self.record(credential)["status"], "VALIDATED")
        records, _ = pe.load_records(self.state_path)
        artifact = pe.latest_evaluation_artifact(self.state_path, "P-1", records)
        self.assertEqual(artifact["_schema"], pe.SCHEMA_RESEARCH_VALIDATION)
        self.assertEqual(sorted(artifact["equivalence"]["paired_task_ids"]),
                         ["T0", "T1", "T2"])
        self.assertEqual(artifact["equivalence"]["arms"]["policy"]["environment"]["budget"],
                         {"hours": 4, "runs": 2})
        self.assertEqual(artifact["policy_signature"], self.signature("P-1"))
        self.assertEqual(artifact["rules_digest"], self.digest)
        self.assertNotEqual(artifact["equivalence"]["arms"]["policy"]["instance"],
                            artifact["equivalence"]["arms"]["control"]["instance"])


# ---------------------------------------------------------------------------
# 三、对抗路径
# ---------------------------------------------------------------------------

class TestAdversarialPaths(L3Case):
    def test_a_forged_task_source_is_refused(self):
        """The source file is replaced after its digest was taken."""
        self.ready()
        source = support.real_task(self.workdir)
        credential = self.credential(source=source)
        source.write_text(json.dumps({"task_id": "T1", "tampered": True}), encoding="utf-8")
        self.approve(credential)
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("摘要", " ".join(result["diagnostics"]))

    def test_an_internally_consistent_fake_credential_is_refused(self):
        """Digests all agree, flags all set - and none of it is an independent verifier."""
        self.ready()
        credential = self.credential()
        # the attacker recomputes every digest so nothing is internally inconsistent
        assert cg.digest_of(credential) == cg.digest_of(credential)
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("PE15", result["codes"])

    def test_an_old_dispatch_record_cannot_be_reused_after_a_new_trial(self):
        """A dispatch record from an earlier bounded trial is not this trial's evidence."""
        self.ready()
        stale = self.credential()["dispatch_ref"]
        assert pe.transition(self.state_path, "P-1", "HOLD", level="L2",
                             evidence={"reason": "retry with a new trial"})["status"] == "HOLD"
        assert pe.evaluate_candidate(self.state_path, "P-1",
                                     self._report())["status"] == "REPLAY_EVALUATED"
        assert support.begin_trial(self.state_path, "P-1")["status"] \
            == "BOUNDED_TRIAL"
        credential = self.credential()
        credential["dispatch_ref"] = stale          # resurrect the previous dispatch
        self.approve(credential)
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("派遣记录", " ".join(result["diagnostics"]))

    def test_a_dispatch_record_already_used_by_another_credential_is_reported(self):
        """White-box: the single-use guard fires when another stored credential shares it."""
        self.ready()
        credential = self.credential()
        self.approve(credential)
        self.assertEqual(self.record(credential)["status"], "VALIDATED")
        diagnostics = pe._dispatch_reuse_errors(self.state_path, credential["dispatch_ref"],
                                                "P-1")
        self.assertTrue(any("已被另一份" in item.render() for item in diagnostics),
                        [item.render() for item in diagnostics])

    def test_a_dispatch_record_from_another_policy_is_refused(self):
        self.ready()
        credential = self.credential()
        credential["dispatch_ref"] = {"path": "/nonexistent/trial.json", "digest": "sha256:x"}
        self.approve(credential)
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("派遣", " ".join(result["diagnostics"]))

    def test_a_self_named_executor_is_refused(self):
        """The policy's own route cannot be its own independent evaluator."""
        self.ready()
        route_name = self.route.name
        credential = self.credential(executor=route_name,
                                     control_executor=route_name + "-clone")
        self.approve(credential)
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("executor", " ".join(result["diagnostics"]))

    def test_a_tampered_policy_binding_is_refused(self):
        self.ready()
        credential = self.credential()
        credential["policy_signature"] = "sha256:not-the-real-signature"
        self.approve(credential)
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("策略版本", " ".join(result["diagnostics"]))

    def test_a_tampered_rules_binding_is_refused(self):
        self.ready()
        credential = self.credential()
        credential["rules_digest"] = "sha256:other-rules"
        self.approve(credential)
        result = self.record(credential)
        self.assertEqual(result["status"], "INVALID", result)

    def test_a_tampered_stored_credential_cannot_be_promoted(self):
        self.ready()
        credential = self.credential()
        self.approve(credential)
        self.assertEqual(self.record(credential)["status"], "VALIDATED")
        records, _ = pe.load_records(self.state_path)
        artifact = pe.latest_evaluation_artifact(self.state_path, "P-1", records)
        path = pathlib.Path(artifact["ref"]["path"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["verdict"]["verdict"] = "SUPPORTED"
        payload["gates"]["provenance_ok"] = False
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result = pe.promote_to_active(self.state_path, "P-1", {"scope_evidence_ok": True})
        self.assertEqual(result["status"], "INVALID", result)

    def test_the_cli_refuses_without_an_approval(self):
        import subprocess
        import sys
        self.ready()
        credential = self.credential()
        path = pathlib.Path(self.temp.name) / "credential.json"
        path.write_text(json.dumps(credential), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(pathlib.Path(__file__).resolve().parent /
                                 "policy_evolution.py"),
             "validate-research", "--state", str(self.state_path),
             "--policy-id", "P-1", "--validation", str(path)],
            capture_output=True, text=True)
        self.assertNotIn("Traceback", proc.stderr, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "INVALID", payload)
        self.assertIn("PE15", payload["codes"])


if __name__ == "__main__":
    unittest.main()
