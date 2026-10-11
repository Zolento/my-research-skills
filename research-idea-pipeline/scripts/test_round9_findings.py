#!/usr/bin/env python3
"""test_round9_findings.py — 第九轮子代理对抗复核发现的回归测试。

覆盖 `research-idea-pipeline/.dev/audit/R8-A-approval-surface.md`、
`R8-B-permission-pipeline.md`、`R8-C-integration-contract.md` 中 Lead 已独立复现并修复的项：

- A-2 批准绑定必须可从凭证内容重算，且不得把「缺摘要」当作「匹配任意批准」
- A-3 被拒绝的凭证不得留下产物（否则孤儿产物会砖化一次性派遣记录）
- A-4 `policy_id` 必须是安全的单段标识
- A-5 批准账本尾部被删除必须报篡改
- A-6 批准有效期必须是有限且合理的秒数
- A-7 被拒绝的 `begin_bounded_trial` 不得留下孤儿试运行产物
- B-1 公平性检查必须比较**声明的**候选/对照臂，而不是映射里排在最前的两个
- B-2 批准账本里的非对象 JSON 行必须转为 PE15，而不是 TypeError
- B-4 受控轴不能只查「字段存在」，空值不算等价
- C-1 ACTIVE 策略的等级必须按记录上报，而不是硬编码 L2
- C-2/C-8 发布闸门必须能发现测试套件被删除、registry trigger 漂移
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

import cognition as cg
import policy_evolution as pe
import release_check as rc
import research_replay as rr
import rsi_test_support as support

BENEFIT = "search_efficiency"
ROOT = pathlib.Path(__file__).resolve().parent.parent


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


class Round9Case(unittest.TestCase):
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

    def _report(self):
        report = rr.run_suite(rr.adversarial_cases()[:4], arms=["rsi_full", "full_cie"], runs=2)
        for arm, shift in (("rsi_full", 0.5), ("full_cie", -0.05)):
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

    def ready(self, policy_id="P-1"):
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
        assert pe.evaluate_candidate(self.state_path, policy_id,
                                     self._report())["status"] == "REPLAY_EVALUATED"
        assert pe.begin_bounded_trial(self.state_path, policy_id,
                                      dispatch_evidence={"dispatched": "R2"})["status"] \
            == "BOUNDED_TRIAL"
        return policy_id

    def signature(self, policy_id="P-1"):
        return pe.policy_record(pe.load_records(self.state_path)[0], policy_id)["signature"]

    def credential(self, policy_id="P-1", **overrides):
        kwargs = {"signature": self.signature(policy_id),
                  "rules_digest": pe.evaluation_rules_digest(self.state_path)}
        kwargs.update(overrides)
        return support.research_validation(self.state_path, policy_id, self.workdir, **kwargs)

    def validated(self, policy_id="P-1", **overrides):
        credential = self.credential(policy_id, **overrides)
        support.approve(self.state_path, policy_id, credential)
        assert pe.record_research_validation(self.state_path, policy_id,
                                             credential)["status"] == "VALIDATED"
        return credential

    def _rewrite_transition_ref(self, forged_digest):
        """Point the stored VALIDATED transition at a tampered artifact (self-consistent)."""
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


# ---------------------------------------------------------------------------
# A-2 / A-3: the approval binding and the orphan artifact
# ---------------------------------------------------------------------------

class TestApprovalBinding(Round9Case):
    def test_a_missing_binding_summary_is_not_a_wildcard(self):
        self.ready()
        self.validated()
        self.assertTrue(pe.approval_errors(self.state_path, policy_id="P-1"),
                        "an approval check with no digest at all must fail closed")

    def test_an_empty_approval_block_cannot_promote(self):
        self.ready()
        self.validated()
        records, _ = pe.load_records(self.state_path)
        artifact = pe.latest_evaluation_artifact(self.state_path, "P-1", records)
        path = pathlib.Path(artifact["ref"]["path"])
        forged = json.loads(path.read_text(encoding="utf-8"))
        forged["approval"] = {}
        forged["digest"] = cg.digest_of({k: v for k, v in forged.items() if k != "digest"})
        path.write_text(json.dumps(forged, ensure_ascii=False, sort_keys=True) + "\n",
                        encoding="utf-8")
        self._rewrite_transition_ref(forged["digest"])
        result = pe.promote_to_active(self.state_path, "P-1", {"scope_evidence_ok": True})
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("PE15", result["codes"])

    def test_a_rewritten_provenance_cannot_reuse_an_approval(self):
        """The artifact's derived fields must be reproducible from the approved credential."""
        self.ready()
        self.validated()
        records, _ = pe.load_records(self.state_path)
        artifact = pe.latest_evaluation_artifact(self.state_path, "P-1", records)
        path = pathlib.Path(artifact["ref"]["path"])
        forged = json.loads(path.read_text(encoding="utf-8"))
        forged["task_provenance"]["task_id"] = "T-NEVER-REVIEWED"
        forged["digest"] = cg.digest_of({k: v for k, v in forged.items() if k != "digest"})
        path.write_text(json.dumps(forged, ensure_ascii=False, sort_keys=True) + "\n",
                        encoding="utf-8")
        self._rewrite_transition_ref(forged["digest"])
        result = pe.promote_to_active(self.state_path, "P-1", {"scope_evidence_ok": True})
        self.assertEqual(result["status"], "INVALID", result)

    def test_a_stale_credential_digest_in_the_artifact_is_refused(self):
        """The binding must be recomputed from the credential content, not read as written."""
        self.ready()
        self.validated()
        records, _ = pe.load_records(self.state_path)
        artifact = pe.latest_evaluation_artifact(self.state_path, "P-1", records)
        path = pathlib.Path(artifact["ref"]["path"])
        forged = json.loads(path.read_text(encoding="utf-8"))
        # change the credential AND the derived field, but leave the approval digest stale
        forged["credential"]["task_provenance"]["task_id"] = "T-NEW"
        forged["task_provenance"]["task_id"] = "T-NEW"
        forged["digest"] = cg.digest_of({k: v for k, v in forged.items() if k != "digest"})
        path.write_text(json.dumps(forged, ensure_ascii=False, sort_keys=True) + "\n",
                        encoding="utf-8")
        self._rewrite_transition_ref(forged["digest"])
        result = pe.promote_to_active(self.state_path, "P-1", {"scope_evidence_ok": True})
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("凭证内容摘要", " ".join(result["diagnostics"]))

    def test_a_tampered_report_inside_the_artifact_is_refused(self):
        """The report must be reproducible from the credential the human approved."""
        self.ready()
        self.validated()
        records, _ = pe.load_records(self.state_path)
        artifact = pe.latest_evaluation_artifact(self.state_path, "P-1", records)
        path = pathlib.Path(artifact["ref"]["path"])
        forged = json.loads(path.read_text(encoding="utf-8"))
        forged["report"]["per_arm"]["policy"]["dimensions"][BENEFIT]["mean"] = 9.9
        forged["digest"] = cg.digest_of({k: v for k, v in forged.items() if k != "digest"})
        path.write_text(json.dumps(forged, ensure_ascii=False, sort_keys=True) + "\n",
                        encoding="utf-8")
        self._rewrite_transition_ref(forged["digest"])
        result = pe.promote_to_active(self.state_path, "P-1", {"scope_evidence_ok": True})
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("报告", " ".join(result["diagnostics"]))

    def test_the_discard_safety_net_removes_an_artifact_when_the_gate_refuses(self):
        """White-box: if the transition is refused after storing, the artifact must go."""
        from unittest import mock
        self.ready()
        credential = self.credential()
        support.approve(self.state_path, "P-1", credential)   # pass the pre-checks
        before = sorted(path.name for path in pe.evaluations_dir(self.state_path).glob("*.json"))
        with mock.patch.object(pe, "_transition_locked",
                               return_value={"status": "INVALID", "written": False,
                                             "diagnostics": ["forced"], "codes": ["PE11"]}):
            result = pe.record_research_validation(self.state_path, "P-1", credential)
        self.assertEqual(result["status"], "INVALID", result)
        after = sorted(path.name for path in pe.evaluations_dir(self.state_path).glob("*.json"))
        self.assertEqual(before, after, "the refused artifact was not discarded")

    def test_a_refused_credential_leaves_no_artifact_and_can_be_retried(self):
        """A refused credential must not claim the single-use dispatch record."""
        self.ready()
        credential = self.credential()
        before = sorted(path.name for path in pe.evaluations_dir(self.state_path).glob("*.json"))
        refused = pe.record_research_validation(self.state_path, "P-1", credential)
        self.assertEqual(refused["status"], "INVALID", refused)
        after = sorted(path.name for path in pe.evaluations_dir(self.state_path).glob("*.json"))
        self.assertEqual(before, after, "a refused credential was still stored")
        support.approve(self.state_path, "P-1", credential)
        self.assertEqual(pe.record_research_validation(self.state_path, "P-1",
                                                       credential)["status"], "VALIDATED")

    def test_a_double_approval_still_selects_the_valid_one(self):
        self.ready()
        credential = self.credential()
        support.approve(self.state_path, "P-1", credential)
        # a duplicate with a non-positive lifetime is refused outright now
        duplicate = pe.approve_l3(self.state_path, policy_id="P-1", credential=credential,
                                  approver="human-2", confirm_human=True,
                                  expires_in_seconds=0)
        self.assertEqual(duplicate["status"], "INVALID", duplicate)
        self.assertEqual(pe.record_research_validation(self.state_path, "P-1",
                                                       credential)["status"], "VALIDATED")


# ---------------------------------------------------------------------------
# A-4 / A-5 / A-6 / A-7
# ---------------------------------------------------------------------------

class TestStoreAndLedgerIntegrity(Round9Case):
    def test_an_unsafe_policy_id_is_refused(self):
        for policy_id in ("a/b", "evil\x00id", "..", "", "x" * 80, ".hidden"):
            payload = {"policy_id": policy_id, "policy_schema_version": "1",
                       "status": "PROPOSED",
                       "scope": {"scope_kind": "local", "problem_structure": "x"},
                       "applicable_conditions": [{"kind": "min_open_uncertainties", "value": 1}],
                       "strategy_changes": [{"kind": "same_tier_preference",
                                             "prefer_action": "R2"}],
                       "supporting_trajectory_ids": ["DT-1"], "counterexamples": ["c"],
                       "expected_effect": {"mechanism": "m", "direction": "up"},
                       "revalidation_conditions": ["r"], "evaluation_refs": [],
                       "rollback_target": None,
                       "evaluation_rules_digest": self.digest}
            result = pe.propose(self.state_path, payload, trajectory_support={"DT-1"})
            self.assertEqual(result["status"], "INVALID", (policy_id, result))
            self.assertIn("PE1", result["codes"])

    def test_a_deleted_ledger_tail_is_reported_as_tampering(self):
        self.ready()
        credential = self.credential()
        support.approve(self.state_path, "P-1", credential)
        ledger = pe.approvals_dir(self.state_path) / "events.jsonl"
        lines = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
        ledger.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
        diagnostics = pe.approval_errors(self.state_path, policy_id="P-1",
                                         credential_digest=cg.digest_of(credential))
        self.assertTrue(diagnostics, "a truncated approval ledger was accepted")
        self.assertIn("head", " ".join(item.render() for item in diagnostics))

    def test_an_absurd_approval_lifetime_is_refused(self):
        self.ready()
        outcome = pe.approve_l3(self.state_path, policy_id="P-1",
                                credential=self.credential(), approver="h",
                                confirm_human=True, expires_in_seconds=10 ** 400)
        self.assertEqual(outcome["status"], "INVALID", outcome)
        self.assertIn("PE15", outcome["codes"])

    def test_a_refused_trial_leaves_no_artifact(self):
        self.ready("P-2")          # P-2 is BOUNDED_TRIAL, not REPLAY_EVALUATED
        before = sorted(path.name for path in pe.trials_dir(self.state_path).glob("*.json"))
        refused = pe.begin_bounded_trial(self.state_path, "P-2",
                                         dispatch_evidence={"dispatched": "R2"})
        self.assertEqual(refused["status"], "INVALID", refused)
        after = sorted(path.name for path in pe.trials_dir(self.state_path).glob("*.json"))
        self.assertEqual(before, after, "a refused trial still wrote an artifact")


# ---------------------------------------------------------------------------
# B-1 / B-2 / B-4
# ---------------------------------------------------------------------------

class TestFairnessArms(Round9Case):
    def test_decoy_arms_cannot_satisfy_the_fairness_check(self):
        """The comparison must use the declared arms, not the first two keys."""
        self.ready()
        record = support.equivalence()
        record["arms"] = {"aaa": record["arms"]["control"],
                          "zzz": record["arms"]["policy"]}
        record["arms"]["aaa"]["environment"] = dict(record["arms"]["aaa"]["environment"])
        credential = self.credential(equivalence_off=True, equivalence_record=record)
        support.approve(self.state_path, "P-1", credential)
        result = pe.record_research_validation(self.state_path, "P-1", credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("PE16", result["codes"])

    def test_decoy_arms_that_sort_first_cannot_mask_the_declared_comparison(self):
        """The fairness check must compare the arms the verdict compares."""
        self.ready()
        record = support.equivalence()
        policy_env = dict(record["arms"]["policy"]["environment"])
        control_env = dict(record["arms"]["control"]["environment"])
        policy_env["model"] = "model-fair"          # declared contrast on a controlled axis
        decoy = dict(control_env)                   # decoys agree with each other
        record["arms"] = {"aaa": {"instance": "run-aaa", "environment": decoy},
                          "control": {"instance": control_env and "run-control",
                                      "environment": control_env},
                          "policy": {"instance": "run-policy", "environment": policy_env}}
        record["contrast_axes"] = ["strategy"]
        credential = self.credential(equivalence_off=True, equivalence_record=record)
        support.approve(self.state_path, "P-1", credential)
        result = pe.record_research_validation(self.state_path, "P-1", credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("PE16", result["codes"])

    def test_a_null_controlled_axis_is_not_equivalence(self):
        self.ready()
        record = support.equivalence()
        record["arms"]["policy"]["environment"]["model"] = None
        record["arms"]["control"]["environment"]["model"] = None
        credential = self.credential(equivalence_off=True, equivalence_record=record)
        support.approve(self.state_path, "P-1", credential)
        result = pe.record_research_validation(self.state_path, "P-1", credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("model", " ".join(result["diagnostics"]))

    def test_a_ledger_line_that_is_not_an_object_is_a_pe15(self):
        self.ready()
        credential = self.credential()
        support.approve(self.state_path, "P-1", credential)
        ledger = pe.approvals_dir(self.state_path) / "events.jsonl"
        with ledger.open("a", encoding="utf-8") as handle:
            handle.write('["not", "an", "object"]\n')
        diagnostics = pe.approval_errors(self.state_path, policy_id="P-1",
                                         credential_digest=cg.digest_of(credential))
        self.assertTrue(diagnostics)
        self.assertIn("PE15", [item.rule for item in diagnostics])
        result = pe.record_research_validation(self.state_path, "P-1", credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("PE15", result["codes"])


# ---------------------------------------------------------------------------
# C-1 / C-2 / C-8
# ---------------------------------------------------------------------------

class TestReportingAndGate(Round9Case):
    def test_the_active_policy_standing_reports_the_recorded_level(self):
        self.ready()
        self.validated()
        self.assertEqual(pe.promote_to_active(self.state_path, "P-1",
                                              {"scope_evidence_ok": True})["status"], "ACTIVE")
        standing = pe.active_policy_standing(self.state_path,
                                             pe.load_records(self.state_path)[0])
        self.assertEqual(standing["level"], "L3", standing)
        self.assertTrue(standing["approved"], standing)

    def test_the_gate_manifest_catches_a_deleted_suite(self):
        with tempfile.TemporaryDirectory() as temp:
            scripts = pathlib.Path(temp)
            for name in rc.EXPECTED_TEST_SUITES:
                (scripts / name).write_text("", encoding="utf-8")
            missing = rc.EXPECTED_TEST_SUITES[0]
            (scripts / missing).unlink()
            original = rc.SCRIPTS
            try:
                rc.SCRIPTS = scripts
                ok, detail = rc.step_tests()
            finally:
                rc.SCRIPTS = original
            self.assertFalse(ok, detail)
            self.assertIn(missing, detail)

    def test_the_preset_parity_catches_a_trigger_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / "presets").mkdir()
            registry = json.loads((ROOT / "preset-registry.json").read_text(encoding="utf-8"))
            # pick a preset whose trigger is NOT "manual", so the mutation really drifts
            preset = next(item for item in registry["presets"] if item["trigger"] != "manual")
            (root / "preset-registry.json").write_text(json.dumps(registry), encoding="utf-8")
            for source in (ROOT / "presets").glob("*.md"):
                (root / "presets" / source.name).write_text(
                    source.read_text(encoding="utf-8"), encoding="utf-8")
            text = (ROOT / preset["path"]).read_text(encoding="utf-8")
            changed = text.replace(f"`{preset['trigger']}`", "`manual`", 1)
            self.assertNotEqual(changed, text, "the fixture mutation was a no-op")
            (root / preset["path"]).write_text(changed, encoding="utf-8")
            original_root = rc.ROOT
            try:
                rc.ROOT = root
                ok, detail = rc.step_preset_library()
            finally:
                rc.ROOT = original_root
            self.assertFalse(ok, detail)
            self.assertIn(preset["preset_id"], detail)


if __name__ == "__main__":
    unittest.main()
