#!/usr/bin/env python3
"""test_policy_transfer.py — Skill-RSI Phase 7 三层记忆与策略迁移验收。

被测的失效模式正是让长期策略学习变得不科学的那几种：把策略当成已证科学事实、
把未观测的决策经验塞进科学记忆、按领域关键词而不是声明结构迁移策略、让一条被否证
的机制换个措辞重新出现、让只有单个项目经验的“全局策略”自动铺开、以及把证据压缩
掉之后仍然声称记忆完整。

每个用例都使用真实的 `research-state.json` 对象与真实的
`decision_trajectory.build_decision_record()` 输出；仅仅“能被 json.loads 解析”
不算通过。
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

import cognition as cg
import decision_trajectory as dt
import policy_evolution as pe
import policy_transfer as pt

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "policy_transfer.py"
TEMPLATE = ROOT / "templates" / "research-state.template.json"


def clone(value):
    return json.loads(json.dumps(value))


def fixture_state(*, operator="reframe", island="P1", anchor="phenomenon", version=3,
                  claim_status="killed"):
    """最小但真实的 canonical state（字段形状与模板一致）。"""
    return {
        "_schema": "research-idea-pipeline/research-state@1",
        "state_version": version,
        "contract": {
            "goal": "判断机制 M 是否解释目标现象", "primary_anchor": anchor,
            "constraints": [], "resources": [],
            "provisional_anchor_rationale": "先形式化", "out_of_scope": [],
            "validation": {"protocol": "preregistered", "min_tier": "T2"},
        },
        "claims": [{
            "id": "C1", "statement": "机制 M 解释目标现象", "status": claim_status,
            "nearest_alternative": "N", "falsifier": "干预 I 后消失", "scope": "数据集 A",
            "contract": {"minimal_discriminating_experiment": "X7"},
            "validity": {"status": "valid"},
        }],
        "evidence": [{
            "id": "E1", "kind": "experiment", "supports": ["C1"], "strength": "weak",
            "scope": "A", "epistemic_status": "Observed", "source_ref": "X1",
            "verification_tier": "T2", "validity": {"status": "valid"},
        }],
        "assumptions": [{"id": "AS1", "statement": "测量无偏", "status": "explicit",
                         "validity": {"status": "valid"}}],
        "hypotheses": [{
            "id": "H1", "statement": "机制 M 是主因", "status": "active",
            "operator": operator, "island": island,
            "structural_signature": {"assumption_distance": 1, "formulation_distance": 1,
                                     "representation_distance": 0,
                                     "theory_lens_distance": 1, "mechanism_distance": 2},
            "validity": {"status": "valid"},
        }],
        "experiments": [], "literature": [],
        "failures": [{
            "id": "F1", "kind": "falsified", "what": "协议 P 已被判别实验否决",
            "negative_knowledge": [{
                "target_id": "C2", "finding": "协议 P 在该 regime 下无效",
                "ruled_out": "协议 P 有效", "retry_allowed": False}],
            "validity": {"status": "valid"},
        }],
        "uncertainties": [{
            "id": "U1", "question": "机制 M 在数据集 B 成立？", "importance": "high",
            "uncertainty": "high", "cheapest_discriminating_test": "X8", "status": "open",
            "validity": {"status": "valid"},
        }],
        "assurance": [], "repairs": [], "narrative_view": {}, "reviews": [],
        "decision": {"verdict": "continue", "rationale": "", "next_phase": "R3"},
    }


def decision_record(state, *, project="A", version=None):
    snapshot = state if version is None else dict(state, state_version=version)
    context = dt.build_context(snapshot, scientific_question="机制 M 是否解释目标现象",
                               active_hypotheses=["H1"], key_uncertainties=["U1"],
                               visible_evidence=["E1"])
    return dt.build_decision_record(
        snapshot, route="A", project=project, context=context,
        candidates=[{"action": "H1", "type": "repair", "target": "H1", "eig": "high",
                     "cost": "low"}],
        chosen="H1", scheduler_priority={"level": 4, "label": "high_information_gain_test"})


def allow_policy(**overrides):
    policy = {
        "id": "POL-ALLOW",
        "scope": {"kind": "structure"},
        "applicable_conditions": [
            {"field": "contract.primary_anchor", "op": "eq", "value": "phenomenon"},
            {"field": "hypotheses[].operator", "op": "contains", "value": "reframe"},
        ],
        "required_tools": ["evaluation-harness"],
        "validation_protocol": {"protocol": "preregistered", "min_tier": "T2"},
        "evidence_level": "independent",
        "independent_evaluation_refs": ["SCHED-1"],
        "counterexamples": [],
    }
    policy.update(overrides)
    return policy


def attested_trajectories(*projects):
    """Minimal real trajectory records: one decision plus one qualified outcome each.

    PT9 accepts a project only when the trajectory carries BOTH, so these are what
    legitimate cross-project evidence looks like.
    """
    records = []
    for project in projects:
        ident = f"DT-{project.lower()}"
        records.append({"_schema": "research-idea-pipeline/decision-trajectory@1",
                        "record": "decision", "trajectory_id": ident, "project": project,
                        "route": project,
                        "context": {"state_version": 3, "state_digest": "sha256:x",
                                    "scientific_question": "q",
                                    "decided_at": "2026-01-01T00:00:00Z"},
                        "decision": {"chosen": "X1", "dispatch_status": "dispatched",
                                     "candidates": []},
                        "recorded_at": "2026-01-01T00:00:00Z"})
        records.append({"_schema": "research-idea-pipeline/decision-trajectory@1",
                        "record": "outcome", "trajectory_id": ident, "project": project,
                        "evidence_qualification": "qualified",
                        "result": {"kind": "experiment_result",
                                   "summary": "observed x=0.42"},
                        "observed_at": "2026-01-02T00:00:00Z", "at_state_version": 3,
                        "scientific_delta": "none", "decision_delta": "none",
                        "policy_delta": "none"})
    return records


def transfer(policy, target, source, **kwargs):
    options = {"source_state": source, "target_tools": ["evaluation-harness"],
               "source_project": "A", "target_project": "B"}
    options.update(kwargs)
    return pt.transfer_decision(policy, target, **options)


def error_codes(policy, target, source, **kwargs):
    options = {"source_state": source, "target_tools": ["evaluation-harness"],
               "source_project": "A", "target_project": "B"}
    options.update(kwargs)
    return {item.rule for item in pt.transfer_errors(policy, target, **options)}


# ---------------------------------------------------------------------------
# 1. 三层记忆严格分离
# ---------------------------------------------------------------------------

class TestMemoryLayerSeparation(unittest.TestCase):
    def test_three_layers_stay_separate_and_policy_never_enters_science(self):
        state = fixture_state()
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            record = decision_record(state)
            result = dt.append_record(path, record, state=state, route="A")
            self.assertEqual(result["status"], "APPENDED", result)
            outcome = dt.build_outcome_record(
                record["trajectory_id"], at_state_version=state["state_version"],
                result={"kind": "experiment_result", "summary": "observed value 0.42"},
                evidence_refs=[{"evidence": "E1"}], decision_delta="decision",
                evidence_qualification="qualified")
            outcome_result = dt.append_record(path, outcome, state=state, route="A")
            self.assertEqual(outcome_result["status"], "APPENDED", outcome_result)
            layers = pt.memory_layers(
                state, trajectory_path=path,
                policy_records=[{"id": "POL-1", "scope": {"kind": "structure"}}])

        self.assertEqual(set(pt.MEMORY_LAYERS), set(
            ("scientific_memory", "decision_experience", "policy_memory")))
        self.assertEqual(layers["scientific_memory"]["layer"], "scientific_memory")
        self.assertEqual(layers["scientific_memory"]["source"], "canonical_state")
        self.assertEqual(layers["decision_experience"]["layer"], "decision_experience")
        self.assertEqual(layers["policy_memory"]["layer"], "policy_memory")
        self.assertTrue(layers["separation_ok"])
        self.assertEqual(layers["diagnostics"], [])

        # 策略 id 与决策轨迹 id 都不得出现在科学层。
        science = json.dumps(layers["scientific_memory"], ensure_ascii=False)
        self.assertNotIn("POL-1", science)
        trajectory_ids = layers["decision_experience"]["trajectories"]
        self.assertEqual(trajectory_ids, [record["trajectory_id"]])
        self.assertNotIn(trajectory_ids[0], science)
        self.assertEqual(layers["decision_experience"]["supported"], trajectory_ids)
        self.assertEqual(layers["decision_experience"]["pending"], [])

    def test_a_policy_record_declaring_a_scientific_kind_is_PT1(self):
        layers = pt.memory_layers(
            fixture_state(),
            policy_records=[{"id": "POL-2", "kind": "scientific_fact"},
                            {"id": "POL-3", "kind": "evidence"}])
        codes = {item["rule"] for item in layers["diagnostics"]}
        self.assertIn("PT1", codes)
        self.assertFalse(layers["separation_ok"])
        science = json.dumps(layers["scientific_memory"], ensure_ascii=False)
        self.assertNotIn("POL-2", science)
        self.assertNotIn("POL-3", science)

    def test_a_policy_claiming_to_refute_a_scientific_claim_is_PT2(self):
        layers = pt.memory_layers(
            fixture_state(),
            policy_records=[{"id": "POL-4", "scope": {"kind": "structure"},
                             "refutes": ["C1"], "supports": ["H1"]}])
        codes = {item["rule"] for item in layers["diagnostics"]}
        self.assertIn("PT2", codes)
        self.assertFalse(layers["separation_ok"])

    def test_canonical_state_carrying_a_policy_section_is_PT1(self):
        state = fixture_state()
        state["policy_memory"] = [{"id": "POL-5"}]
        layers = pt.memory_layers(state)
        codes = {item["rule"] for item in layers["diagnostics"]}
        self.assertIn("PT1", codes)
        self.assertFalse(layers["separation_ok"])
        self.assertNotIn("POL-5", json.dumps(layers["scientific_memory"], ensure_ascii=False))

    def test_real_template_separates_cleanly(self):
        state = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        layers = pt.memory_layers(state)
        self.assertTrue(layers["separation_ok"], layers["diagnostics"])
        self.assertEqual(layers["scientific_memory"]["state_version"],
                         state["state_version"])
        self.assertTrue(layers["scientific_memory"]["claims"])


# ---------------------------------------------------------------------------
# 2. 结构相似性只看声明字段
# ---------------------------------------------------------------------------

class TestStructuralSimilarity(unittest.TestCase):
    def test_same_declared_structure_matches(self):
        result = pt.structure_similarity(fixture_state(), fixture_state())
        self.assertTrue(result["structural_match"])
        self.assertGreaterEqual(result["score"], result["threshold"])
        self.assertEqual(result["shared_operators"], ["reframe"])
        self.assertEqual(result["shared_islands"], ["P1"])

    def test_same_domain_keyword_but_different_structure_does_not_match(self):
        source = fixture_state()
        target = fixture_state(operator="remote_analogy", island="P4", anchor="benchmark")
        # 领域关键词/陈述文本完全相同，只有声明算子与岛不同。
        target["claims"][0]["statement"] = source["claims"][0]["statement"]
        target["hypotheses"][0]["statement"] = source["hypotheses"][0]["statement"]
        target["hypotheses"][0]["structural_signature"] = {
            "assumption_distance": 3, "formulation_distance": 4,
            "representation_distance": 2, "theory_lens_distance": 4,
            "mechanism_distance": 1}
        result = pt.structure_similarity(source, target)
        self.assertFalse(result["structural_match"])
        self.assertEqual(result["shared_operators"], [])
        self.assertEqual(result["shared_islands"], [])

    def test_empty_declared_structure_never_matches(self):
        result = pt.structure_similarity({}, {})
        self.assertFalse(result["structural_match"])
        self.assertEqual(result["score"], 0.0)

    def test_signature_uses_only_declared_fields(self):
        state = fixture_state()
        signature = pt.structural_signature(state)
        self.assertEqual(signature["source"], "declared_fields")
        for key in ("operators", "islands", "claim_structures", "assumption_count",
                    "uncertainty_axes", "digest", "source"):
            self.assertIn(key, signature)
        self.assertEqual(signature["assumption_count"], 1)
        self.assertEqual(signature["operators"], ["reframe"])
        self.assertEqual(signature["islands"], ["P1"])
        blob = json.dumps(signature, ensure_ascii=False)
        # 自由文本不得进入签名。
        self.assertNotIn("机制 M 解释目标现象", blob)
        self.assertNotIn("判断机制", blob)

    def test_signature_ignores_prose_rewording(self):
        source = fixture_state()
        target = clone(source)
        target["claims"][0]["statement"] = "完全不同的中文措辞"
        target["hypotheses"][0]["statement"] = "另一个说法"
        target["contract"]["goal"] = "换个目标描述"
        self.assertEqual(pt.structural_signature(source)["digest"],
                         pt.structural_signature(target)["digest"])


# ---------------------------------------------------------------------------
# 3/4. 迁移判定
# ---------------------------------------------------------------------------

class TestTransferDecision(unittest.TestCase):
    def setUp(self):
        self.source = fixture_state()
        self.target = fixture_state()

    def test_allowed_for_matching_scoped_policy_with_independent_evaluation(self):
        result = transfer(allow_policy(), self.target, self.source)
        self.assertEqual(result["status"], "ALLOW", result["reasons"])
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["schema"], pt.SCHEMA_TRANSFER)
        self.assertTrue(result["similarity"]["structural_match"])
        self.assertTrue(result["cross_project"])
        self.assertIn("scope:structure", result["boundaries"])

    def test_blocked_when_structure_differs_PT4(self):
        other = fixture_state(operator="remote_analogy", island="P4", anchor="benchmark")
        result = transfer(allow_policy(), other, self.source)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT4", result["codes"])

    def test_blocked_when_scope_missing_PT3(self):
        policy = allow_policy()
        policy.pop("scope")
        result = transfer(policy, self.target, self.source)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT3", result["codes"])

    def test_blocked_when_scope_is_not_structured_PT3(self):
        result = transfer(allow_policy(scope="我们大概可以到处用"),
                          self.target, self.source)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT3", result["codes"])

    def test_blocked_when_condition_is_unsatisfiable_PT5(self):
        policy = allow_policy(applicable_conditions=[
            {"field": "contract.primary_anchor", "op": "eq", "value": "theory"}])
        result = transfer(policy, self.target, self.source)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT5", result["codes"])

    def test_blocked_when_condition_field_is_unknown_PT5(self):
        policy = allow_policy(applicable_conditions=[
            {"field": "contract.does_not_exist", "op": "exists"}])
        result = transfer(policy, self.target, self.source)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT5", result["codes"])

    def test_blocked_when_tool_is_missing_PT6(self):
        policy = allow_policy(required_tools=["gpu-cluster"])
        result = transfer(policy, self.target, self.source)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT6", result["codes"])

    def test_blocked_when_validation_protocol_differs_PT7(self):
        policy = allow_policy(validation_protocol={"protocol": "exploratory",
                                                   "min_tier": "T0"})
        result = transfer(policy, self.target, self.source)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT7", result["codes"])

    def test_blocked_when_target_lacks_the_evidence_protocol_PT7(self):
        target = fixture_state()
        target["contract"].pop("validation")
        result = transfer(allow_policy(), target, self.source)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT7", result["codes"])

    def test_blocked_when_reproposing_a_refuted_mechanism_PT8(self):
        policy = allow_policy(mechanism={"id": "C1", "statement": ""})
        result = transfer(policy, self.target, self.source)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT8", result["codes"])

    def test_blocked_when_reproposing_a_refuted_mechanism_by_statement_PT8(self):
        policy = allow_policy(mechanism={
            "statement": "协议 P 在该 regime 下无效（换个措辞复述）"})
        result = transfer(policy, self.target, self.source)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT8", result["codes"])

    def test_blocked_when_global_scope_has_only_one_project_PT9(self):
        policy = allow_policy(scope={"kind": "global"})
        policy.pop("independent_evaluation_refs")
        result = transfer(policy, self.target, self.source)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT9", result["codes"])

    def test_blocked_when_global_scope_lacks_independent_evaluation_PT9(self):
        policy = allow_policy(scope={"kind": "global"},
                              evidence_projects=["A", "B"])
        policy.pop("independent_evaluation_refs")
        result = transfer(policy, self.target, self.source,
                          source_trajectories=[{"project": "A"}, {"project": "B"}])
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT9", result["codes"])

    def test_global_scope_with_two_attested_projects_is_allowed(self):
        """PT9 tightened: the projects must be backed by real trajectory evidence."""
        policy = allow_policy(scope={"kind": "global"}, evidence_projects=["A", "B"],
                              supporting_trajectory_ids=["DT-a", "DT-b"],
                              independent_evaluation_refs=["DT-a", "DT-b"])
        result = transfer(policy, self.target, self.source,
                          source_trajectories=attested_trajectories("A", "B"))
        self.assertEqual(result["status"], "ALLOW", result["reasons"])

    def test_a_self_declared_project_list_is_not_cross_project_evidence(self):
        """PT9: `evidence_projects: [A, B]` with zero records used to ALLOW."""
        policy = allow_policy(scope={"kind": "global"}, evidence_projects=["A", "B"])
        result = transfer(policy, self.target, self.source)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT9", result["codes"])

    def test_a_bare_outcome_line_is_not_evidence(self):
        """PT9: two forged outcome records with no decision behind them used to ALLOW."""
        forged = [{"record": "outcome", "trajectory_id": f"DT-{project}",
                   "project": project, "evidence_qualification": "qualified"}
                  for project in ("A", "B")]
        policy = allow_policy(scope={"kind": "global"}, evidence_projects=["A", "B"])
        result = transfer(policy, self.target, self.source, records=forged)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT9", result["codes"])

    def test_an_unbacked_declared_project_blocks(self):
        policy = allow_policy(scope={"kind": "global"}, evidence_projects=["A", "B", "Z"])
        result = transfer(policy, self.target, self.source,
                          source_trajectories=attested_trajectories("A", "B"))
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT9", result["codes"])

    def test_a_supporting_trajectory_that_is_not_attested_blocks(self):
        policy = allow_policy(scope={"kind": "global"}, evidence_projects=["A", "B"],
                              supporting_trajectory_ids=["DT-a", "DT-ghost"])
        result = transfer(policy, self.target, self.source,
                          source_trajectories=attested_trajectories("A", "B"))
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT9", result["codes"])

    def test_blocked_when_counterexamples_cover_the_target_PT10(self):
        policy = allow_policy(counterexamples=[
            {"id": "CE1", "operators": ["reframe"], "islands": ["P1"]}])
        result = transfer(policy, self.target, self.source)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT10", result["codes"])

    def test_blocked_when_counterexample_is_a_bare_structure_list_PT10(self):
        policy = allow_policy(counterexamples=[{"id": "CE1", "structure": ["reframe"]}])
        result = transfer(policy, self.target, self.source)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT10", result["codes"])

    def test_unrelated_declared_counterexample_does_not_block(self):
        policy = allow_policy(counterexamples=[
            {"id": "CE1", "operators": ["remote_analogy"], "islands": ["P4"]}])
        result = transfer(policy, self.target, self.source)
        self.assertEqual(result["status"], "ALLOW", result["reasons"])

    def test_counterexample_conditions_that_do_not_hold_do_not_block(self):
        policy = allow_policy(counterexamples=[{
            "id": "CE1", "operators": ["reframe"], "islands": ["P1"],
            "conditions": [{"field": "contract.primary_anchor", "op": "eq",
                            "value": "theory"}]}])
        result = transfer(policy, self.target, self.source)
        self.assertEqual(result["status"], "ALLOW", result["reasons"])

    def test_unstructured_counterexample_fails_closed_PT10(self):
        policy = allow_policy(counterexamples=["这个策略以前失败过"])
        result = transfer(policy, self.target, self.source)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT10", result["codes"])

    def test_transfer_never_mutates_its_inputs(self):
        policy = allow_policy()
        target = self.target
        source = self.source
        before = (clone(policy), clone(target), clone(source))
        pt.transfer_errors(policy, target, source_state=source,
                           target_tools=["evaluation-harness"],
                           source_project="A", target_project="B")
        pt.transfer_decision(policy, target, source_state=source,
                             target_tools=["evaluation-harness"],
                             source_project="A", target_project="B")
        self.assertEqual((policy, target, source), before)

    def test_layer_mixing_also_blocks_transfer_PT1(self):
        policy = allow_policy(kind="scientific_fact")
        result = transfer(policy, self.target, self.source)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT1", result["codes"])


# ---------------------------------------------------------------------------
# 5. 过期经验
# ---------------------------------------------------------------------------

class TestExpiredTrajectories(unittest.TestCase):
    def setUp(self):
        self.state = fixture_state(version=3)
        self.record = decision_record(self.state, version=3)
        self.ident = self.record["trajectory_id"]

    def test_old_state_version_is_flagged(self):
        expired = pt.expired_trajectories([self.record], fixture_state(version=200))
        self.assertEqual(expired, [self.ident])

    def test_boundary_gap_is_respected(self):
        # version 3 -> 53 正好 50，不超过 max_state_version_gap。
        self.assertEqual(pt.expired_trajectories([self.record],
                                                 fixture_state(version=53)), [])
        self.assertEqual(pt.expired_trajectories([self.record],
                                                 fixture_state(version=54)), [self.ident])

    def test_fresh_trajectory_is_not_flagged(self):
        self.assertEqual(pt.expired_trajectories([self.record],
                                                 fixture_state(version=10)), [])

    def test_invalidated_subject_is_flagged(self):
        expired = pt.expired_trajectories([self.record], fixture_state(version=10),
                                          invalidated_subjects=["H1"])
        self.assertEqual(expired, [self.ident])

    def test_result_is_sorted(self):
        second = decision_record(self.state, project="B", version=3)
        second["trajectory_id"] = "DT-aaa"
        first = clone(self.record)
        first["trajectory_id"] = "DT-zzz"
        expired = pt.expired_trajectories([second, first], fixture_state(version=200))
        self.assertEqual(expired, sorted(expired))


# ---------------------------------------------------------------------------
# 6. 有损压缩拒绝
# ---------------------------------------------------------------------------

class TestCompressionReport(unittest.TestCase):
    def test_refuses_when_evidence_would_be_dropped_and_drops_nothing(self):
        items = [("E1", "evidence"), ("E2", "evidence"), ("P1", "policy")]
        report = pt.compression_report(items, 1)
        self.assertEqual(report["status"], "REFUSED")
        self.assertEqual(report["dropped"], [])
        self.assertEqual(sorted(report["kept"]), ["E1", "E2", "P1"])
        self.assertTrue(report["reasons"])

    def test_refuses_when_stop_rule_or_scientific_fact_would_be_dropped(self):
        items = [("S1", "stop_rule"), ("F1", "scientific_fact"), ("P1", "policy")]
        self.assertEqual(pt.compression_report(items, 1)["status"], "REFUSED")
        self.assertEqual(pt.compression_report(items, 2)["status"], "OK")

    def test_refuses_when_protected_member_would_be_dropped(self):
        items = [("E1", "evidence"), ("D1", "decision_experience"), ("P1", "policy")]
        report = pt.compression_report(items, 1, protected=["D1"])
        self.assertEqual(report["status"], "REFUSED")
        self.assertEqual(report["dropped"], [])
        self.assertEqual(sorted(report["kept"]), ["D1", "E1", "P1"])

    def test_allows_dropping_policy_and_decision_experience_and_reports_it(self):
        items = [("E1", "evidence"), ("P1", "policy"), ("D1", "decision_experience")]
        report = pt.compression_report(items, 1)
        self.assertEqual(report["status"], "OK")
        self.assertEqual(report["kept"], ["E1"])
        self.assertEqual(sorted(report["dropped"]), ["D1", "P1"])
        reasons = " ".join(report["reasons"])
        self.assertIn("policy", reasons)
        self.assertIn("decision_experience", reasons)
        # 只丢 decision_experience 时同样要报告。
        only_experience = pt.compression_report(items, 2)
        self.assertEqual(only_experience["dropped"], ["D1"])
        self.assertIn("decision_experience", " ".join(only_experience["reasons"]))

    def test_budget_larger_than_items_drops_nothing(self):
        items = [("E1", "evidence"), ("P1", "policy")]
        report = pt.compression_report(items, 10)
        self.assertEqual(report["status"], "OK")
        self.assertEqual(report["dropped"], [])
        self.assertEqual(sorted(report["kept"]), ["E1", "P1"])

    def test_unknown_kind_fails_closed(self):
        items = [("X1", "mystery"), ("E1", "evidence")]
        report = pt.compression_report(items, 1)
        self.assertEqual(report["status"], "REFUSED")
        self.assertEqual(report["dropped"], [])

    def test_negative_budget_is_refused(self):
        self.assertEqual(pt.compression_report([("E1", "evidence")], -1)["status"],
                         "REFUSED")


# ---------------------------------------------------------------------------
# 7. CLI
# ---------------------------------------------------------------------------

class TestCli(unittest.TestCase):
    def test_selftest_flag_passes(self):
        out = subprocess.run([sys.executable, str(SCRIPT), "--selftest"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("selftest OK", out.stdout)
        self.assertIn("  ok  ", out.stdout)

    def test_selftest_command_passes(self):
        out = subprocess.run([sys.executable, str(SCRIPT), "selftest"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("selftest OK", out.stdout)

    def test_signature_and_compression_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = pathlib.Path(temp) / cg.STATE_NAME
            state_path.write_text(json.dumps(fixture_state(), ensure_ascii=False),
                                  encoding="utf-8")
            signature = subprocess.run(
                [sys.executable, str(SCRIPT), "signature", "--state", str(state_path)],
                capture_output=True, text=True)
            self.assertEqual(signature.returncode, 0, signature.stderr)
            self.assertEqual(json.loads(signature.stdout)["signature"]["operators"],
                             ["reframe"])
            compressed = subprocess.run(
                [sys.executable, str(SCRIPT), "compress",
                 "--items", json.dumps([["E1", "evidence"], ["P1", "policy"]]),
                 "--budget", "1"], capture_output=True, text=True)
            self.assertEqual(compressed.returncode, 0, compressed.stderr)
            self.assertEqual(json.loads(compressed.stdout)["status"], "OK")


# ---------------------------------------------------------------------------
# 8. 对抗审计回归（F1—F15）
# ---------------------------------------------------------------------------

class TestNegatedMechanismCoverage(unittest.TestCase):
    """F1：killed/refuted 的假设与索引机制也必须进入负向知识集合。"""

    def test_negated_mechanisms_includes_killed_and_archived_hypotheses(self):
        for status in ("killed", "archived"):
            state = fixture_state()
            state["hypotheses"][0]["status"] = status
            identifiers = {item["id"] for item in pt.negated_mechanisms(state)}
            self.assertIn("H1", identifiers, status)

    def test_reproposing_a_killed_hypothesis_blocks_PT8(self):
        state = fixture_state()
        state["hypotheses"][0]["status"] = "killed"
        result = transfer(allow_policy(mechanism={"id": "H1"}), state, state)
        self.assertEqual(result["status"], "BLOCK", result["reasons"])
        self.assertIn("PT8", result["codes"])

    def test_index_refuted_mechanism_is_negated_and_its_canonical_id_blocks_PT8(self):
        index = {"mechanisms": [{
            "id": "MECH-1", "status": "refuted", "statement": "机制 X 已被否证",
            "canonical_refs": {"claims": ["C9"], "hypotheses": ["H9"]}}]}
        identifiers = {item["id"] for item in pt.negated_mechanisms({}, index)}
        self.assertLessEqual({"MECH-1", "C9", "H9"}, identifiers)
        result = transfer(allow_policy(mechanism={"id": "H9"}), fixture_state(),
                          fixture_state(), target_index=index)
        self.assertEqual(result["status"], "BLOCK", result["reasons"])
        self.assertIn("PT8", result["codes"])


class TestNegativeKnowledgeProposition(unittest.TestCase):
    """F2：PT8 必须以 ruled_out（被排除的命题）为主匹配，finding 仅作上下文。"""

    def test_negative_knowledge_keeps_both_ruled_out_and_finding(self):
        entries = [item for item in pt.negated_mechanisms(fixture_state())
                   if item["kind"] == "failure"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["statement"], "协议 P 有效")
        self.assertEqual(entries[0]["finding"], "协议 P 在该 regime 下无效")

    def test_reproposing_the_ruled_out_proposition_blocks_PT8(self):
        state = fixture_state()
        result = transfer(allow_policy(mechanism={"id": "", "statement": "协议 P 有效"}),
                          state, state)
        self.assertEqual(result["status"], "BLOCK", result["reasons"])
        self.assertIn("PT8", result["codes"])

    def test_finding_is_still_a_secondary_match(self):
        result = transfer(allow_policy(
            mechanism={"id": "", "statement": "协议 P 在该 regime 下无效（换个说法）"}),
            fixture_state(), fixture_state())
        self.assertEqual(result["status"], "BLOCK", result["reasons"])
        self.assertIn("PT8", result["codes"])


class TestCounterexampleConditionFailClosed(unittest.TestCase):
    """F3：畸形/不可判定的反例条件不得中和 PT10 覆盖检查。"""

    def _counterexample(self, condition):
        return allow_policy(counterexamples=[{
            "id": "CE1", "operators": ["reframe"], "islands": ["P1"],
            "conditions": [condition]}])

    def test_unresolvable_condition_fails_closed_PT10(self):
        for condition in ({"field": "contract.does_not_exist", "op": "eq", "value": "x"},
                          {"field": "hypotheses[].operator", "op": "no_such_op"},
                          {"field": "contract.primary_anchor", "op": "eq"}):
            result = transfer(self._counterexample(condition), fixture_state(), fixture_state())
            self.assertEqual(result["status"], "BLOCK", condition)
            self.assertIn("PT10", result["codes"])
            self.assertNotIn("PT5", result["codes"])

    def test_regex_condition_in_a_counterexample_fails_closed_PT10(self):
        result = transfer(self._counterexample(
            {"field": "contract.primary_anchor", "op": "regex", "value": "(a+)+$"}),
            fixture_state(), fixture_state())
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT10", result["codes"])


class TestConditionAndToolShape(unittest.TestCase):
    """F4：present-but-not-list 的 applicable_conditions / required_tools 必须阻塞。"""

    def test_non_list_applicable_conditions_fails_closed_PT5(self):
        for shape in ("always applies", None, 42, True):
            policy = allow_policy(applicable_conditions=shape)
            result = transfer(policy, fixture_state(), fixture_state())
            self.assertEqual(result["status"], "BLOCK", shape)
            self.assertIn("PT5", result["codes"], shape)

    def test_empty_list_applicable_conditions_is_allowed(self):
        result = transfer(allow_policy(applicable_conditions=[]),
                          fixture_state(), fixture_state())
        self.assertEqual(result["status"], "ALLOW", result["reasons"])

    def test_non_list_required_tools_fails_closed_PT6(self):
        for shape in ("gpu-cluster", None, 42):
            policy = allow_policy(required_tools=shape)
            result = transfer(policy, fixture_state(), fixture_state())
            self.assertEqual(result["status"], "BLOCK", shape)
            self.assertIn("PT6", result["codes"], shape)


class TestCrossProjectGateProvenance(unittest.TestCase):
    """F5：未声明/不可验证的来源必须让 `cross_project_transfer_allowed` fail-closed。"""

    def test_missing_source_with_known_route_blocks(self):
        gate = pe.cross_project_transfer_allowed(
            {"id": "E", "scope": {"scope_kind": "project", "problem_structure": "x"}},
            fixture_state(), current_route="A")
        self.assertTrue(gate["required"])
        self.assertEqual(gate["status"], "BLOCK")
        self.assertTrue(gate["reasons"])

    def test_declared_source_with_empty_current_route_blocks(self):
        gate = pe.cross_project_transfer_allowed(
            {"id": "E", "scope": {"scope_kind": "project"}, "origin_stamped": True,
             "source_route": "B", "source_project": "B"},
            fixture_state(), current_route="")
        self.assertTrue(gate["required"])
        self.assertEqual(gate["status"], "BLOCK")

    def test_non_dict_candidate_blocks_instead_of_raising(self):
        gate = pe.cross_project_transfer_allowed([], fixture_state(), current_route="A")
        self.assertTrue(gate["required"])
        self.assertEqual(gate["status"], "BLOCK")

    def test_a_stamped_same_route_needs_no_gate(self):
        gate = pe.cross_project_transfer_allowed(
            {"id": "E", "scope": {"scope_kind": "project"}, "origin_stamped": True,
             "source_route": "A"},
            fixture_state(), current_route="A")
        self.assertFalse(gate["required"])
        self.assertEqual(gate["status"], "NOT_REQUIRED")

    def test_a_self_declared_route_is_not_provenance(self):
        """H-08: naming the target route as one's own origin used to skip the gate."""
        gate = pe.cross_project_transfer_allowed(
            {"id": "E", "scope": {"scope_kind": "project", "source_route": "A"}},
            fixture_state(), current_route="A")
        self.assertTrue(gate["required"])
        self.assertEqual(gate["status"], "BLOCK")

    def test_a_candidate_level_route_without_the_stamp_is_ignored(self):
        gate = pe.cross_project_transfer_allowed(
            {"id": "E", "scope": {"scope_kind": "project"}, "source_route": "A"},
            fixture_state(), current_route="A")
        self.assertTrue(gate["required"])
        self.assertEqual(gate["status"], "BLOCK")

    def test_require_transfer_forces_the_gate_without_a_source(self):
        gate = pe.cross_project_transfer_allowed(
            {"id": "E", "scope": {"scope_kind": "project", "problem_structure": "x"}},
            fixture_state(), current_route="A", require_transfer=True)
        self.assertTrue(gate["required"])
        self.assertEqual(gate["status"], "BLOCK")


class TestExpiredVersionFailClosed(unittest.TestCase):
    """F6：缺失/非整数 state_version 与非法 gap 必须 fail-closed，而不是当 0。"""

    def setUp(self):
        self.state = fixture_state(version=3)
        self.record = decision_record(self.state, version=3)
        self.ident = self.record["trajectory_id"]

    def test_missing_state_version_expires_everything(self):
        without = {key: value for key, value in self.state.items() if key != "state_version"}
        self.assertEqual(pt.expired_trajectories([self.record], without), [self.ident])

    def test_string_state_version_expires_everything(self):
        self.assertEqual(pt.expired_trajectories([self.record], {"state_version": "200"}),
                         [self.ident])

    def test_non_dict_state_expires_everything(self):
        self.assertEqual(pt.expired_trajectories([self.record], None), [self.ident])

    def test_invalid_gap_diagnoses_instead_of_raising(self):
        for gap in (None, "50", 3.5, True):
            report = pt.expired_trajectories_report(
                [self.record], fixture_state(version=4), max_state_version_gap=gap)
            self.assertEqual(report["expired"], [self.ident], gap)
            self.assertTrue(report["diagnostics"], gap)

    def test_missing_version_is_reported_and_expired(self):
        report = pt.expired_trajectories_report([self.record], {"state_version": "3"})
        self.assertEqual(report["expired"], [self.ident])
        self.assertTrue(any("state_version" in item["path"]
                            for item in report["diagnostics"]))

    def test_valid_version_still_uses_the_gap(self):
        self.assertEqual(pt.expired_trajectories([self.record], fixture_state(version=10)), [])
        self.assertEqual(pt.expired_trajectories([self.record], fixture_state(version=200)),
                         [self.ident])


class TestExperienceChainDiagnostics(unittest.TestCase):
    """F7：容错读取断裂的决策链必须把诊断暴露出来并使 separation_ok=False。"""

    def test_broken_trajectory_chain_breaks_separation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "x.jsonl"
            path.write_text(
                json.dumps({"trajectory_id": "DT-evil", "record": "decision",
                            "decision": {"context": {"state_version": 3}}}) + "\nnot json\n",
                encoding="utf-8")
            layers = pt.memory_layers(fixture_state(), trajectory_path=path)
        self.assertFalse(layers["separation_ok"])
        self.assertFalse(layers["decision_experience"]["chain_ok"])
        self.assertTrue(layers["decision_experience"]["chain_diagnostics"])
        self.assertIn("DT0", {item["rule"] for item in layers["diagnostics"]})


class TestSelfAttestedStructure(unittest.TestCase):
    """F8：缺少 attested source_state 时，策略自证的结构签名不得产生结构匹配。"""

    def test_self_attested_signature_blocks_PT4(self):
        signature = fixture_state()["hypotheses"][0]["structural_signature"]
        policy = {
            "id": "EVIL", "scope": {"kind": "structure"},
            "structural_signature": {"operators": ["reframe"], "islands": ["P1"],
                                     "structural_signature": clone(signature)},
            "evidence_level": "independent", "independent_evaluation_refs": ["X"],
            "counterexamples": [],
        }
        result = pt.transfer_decision(policy, fixture_state())
        self.assertEqual(result["status"], "BLOCK", result["reasons"])
        self.assertIn("PT4", result["codes"])
        self.assertTrue(result["similarity"]["self_attested"])
        self.assertFalse(result["similarity"]["structural_match"])

    def test_explicit_source_state_is_attested_and_still_matches(self):
        source = fixture_state()
        policy = allow_policy()
        result = transfer(policy, source, source)
        self.assertEqual(result["status"], "ALLOW", result["reasons"])
        self.assertFalse(result["similarity"].get("self_attested", False))


class TestCompressionDuplicateOrder(unittest.TestCase):
    """F9：同一 id 的冲突 kind 不得因输入顺序而丢弃不可丢成员。"""

    def test_protected_kind_wins_regardless_of_order(self):
        for items in ([("X1", "policy"), ("X1", "evidence")],
                      [("X1", "evidence"), ("X1", "policy")]):
            report = pt.compression_report(items, 0)
            self.assertEqual(report["status"], "REFUSED", items)
            self.assertEqual(report["dropped"], [], items)

    def test_unknown_kind_wins_regardless_of_order(self):
        for items in ([("X1", "policy"), ("X1", "mystery")],
                      [("X1", "mystery"), ("X1", "policy")]):
            report = pt.compression_report(items, 0)
            self.assertEqual(report["status"], "REFUSED", items)

    def test_protected_argument_and_kind_conflict_is_order_independent(self):
        first = pt.compression_report([("X1", "policy"), ("X1", "evidence")], 0)
        second = pt.compression_report([("X1", "evidence"), ("X1", "policy")], 0)
        self.assertEqual((first["status"], first["kept"], first["dropped"]),
                         (second["status"], second["kept"], second["dropped"]))


class TestRegexReDoSFailClosed(unittest.TestCase):
    """F10：用户提供的正则算子必须被拒绝，闸门不得被灾难性回溯拖住。"""

    def test_catastrophic_regex_is_refused_quickly(self):
        state = fixture_state()
        state["contract"]["goal"] = "a" * 40 + "b"
        policy = allow_policy(applicable_conditions=[
            {"field": "contract.goal", "op": "regex", "value": "(a+)+$"}])
        started = time.monotonic()
        result = transfer(policy, state, state)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 1.0, f"regex 求值耗时 {elapsed:.2f}s（ReDoS）")
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT5", result["codes"])

    def test_matches_operator_is_refused_too(self):
        policy = allow_policy(applicable_conditions=[
            {"field": "contract.primary_anchor", "op": "matches", "value": ".*"}])
        result = transfer(policy, fixture_state(), fixture_state())
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT5", result["codes"])


class TestAuditCliContract(unittest.TestCase):
    """F11/F15：REFUSED 的退出码与不可解析输入的 INVALID 负载。"""

    def test_compress_cli_exits_nonzero_on_refused(self):
        out = subprocess.run(
            [sys.executable, str(SCRIPT), "compress",
             "--items", json.dumps([["E1", "evidence"], ["P1", "policy"]]),
             "--budget", "0"],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, pt.EXIT_HARD, out.stderr)
        self.assertEqual(json.loads(out.stdout)["status"], "REFUSED")

    def test_transfer_cli_unparseable_policy_is_invalid(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = pathlib.Path(temp) / cg.STATE_NAME
            state_path.write_text(json.dumps(fixture_state(), ensure_ascii=False),
                                  encoding="utf-8")
            out = subprocess.run(
                [sys.executable, str(SCRIPT), "transfer",
                 "--policy", "not-a-json-file", "--target-state", str(state_path)],
                capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0)
        self.assertNotIn("Traceback", out.stderr)
        self.assertEqual(json.loads(out.stdout)["status"], "INVALID")

    def test_transfer_cli_non_dict_policy_is_invalid(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = pathlib.Path(temp) / cg.STATE_NAME
            state_path.write_text(json.dumps(fixture_state(), ensure_ascii=False),
                                  encoding="utf-8")
            out = subprocess.run(
                [sys.executable, str(SCRIPT), "transfer",
                 "--policy", "[]", "--target-state", str(state_path)],
                capture_output=True, text=True)
        self.assertEqual(out.returncode, pt.EXIT_ERROR)
        self.assertEqual(json.loads(out.stdout)["status"], "INVALID")

    def test_layers_cli_missing_state_is_invalid_not_a_traceback(self):
        out = subprocess.run(
            [sys.executable, str(SCRIPT), "layers", "--state", "/tmp/does-not-exist.json"],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, pt.EXIT_ERROR)
        self.assertNotIn("Traceback", out.stderr)
        self.assertEqual(json.loads(out.stdout)["status"], "INVALID")


if __name__ == "__main__":
    unittest.main()


class TestTransferDeltaRegressions(unittest.TestCase):
    """H-06..H-09: incomplete fixes of the policy-transfer findings."""

    def test_an_unsatisfied_condition_cannot_neutralise_pt10(self):
        """H-06: a well-formed but unsatisfied condition used to short-circuit coverage."""
        target = fixture_state()
        base = {"policy_id": "P", "scope": {"kind": "local", "problem_structure": "x"},
                "mechanism": {"id": "H1"}, "supporting_trajectory_ids": ["DT-1"]}
        bare = dict(base, counterexamples=[{"id": "CE"}])
        self.assertEqual(pt.transfer_decision(bare, target)["status"], "BLOCK")
        with_condition = dict(base, counterexamples=[{
            "id": "CE",
            "conditions": [{"field": "contract.primary_anchor", "op": "eq",
                            "value": "__nope__"}]}])
        self.assertEqual(pt.transfer_decision(with_condition, target)["status"], "BLOCK")

    def test_a_negative_state_version_does_not_disable_expiry(self):
        """H-07: a negative current version made the gap comparison unreachable."""
        records = [{"trajectory_id": "DT-x", "record": "decision",
                    "context": {"state_version": -1000000}}]
        self.assertEqual(pt.expired_trajectories(records, {"state_version": 10}), ["DT-x"])

    def test_a_non_string_ruled_out_blocks_instead_of_disabling_pt8(self):
        """H-09: a non-string proposition was filtered out of the match set."""
        state = fixture_state()
        state["failures"] = [{"id": "F1", "kind": "mechanism",
                              "negative_knowledge": [{"ruled_out": 42,
                                                      "finding": "explanation"}]}]
        policy = {"policy_id": "P", "scope": {"kind": "local", "problem_structure": "x"},
                  "mechanism": {"id": "H1"}, "supporting_trajectory_ids": ["DT-1"],
                  "counterexamples": ["structure: operator=reframe"]}
        decision = pt.transfer_decision(policy, state)
        self.assertEqual(decision["status"], "BLOCK")
        self.assertTrue(any("PT8" in str(reason) for reason in decision["reasons"]))


class TestAttestedCrossProjectEvidence(unittest.TestCase):
    """PT9 tightened: a self-declared project list is not cross-project evidence."""

    def _policy(self, **over):
        options = {"scope": {"kind": "global", "structures": ["reframe"]},
                   "evidence_projects": ["A", "B"]}
        options.update(over)
        return allow_policy(**options)

    def test_two_attested_projects_allow(self):
        policy = self._policy(supporting_trajectory_ids=["DT-a", "DT-b"],
                              independent_evaluation_refs=["DT-a", "DT-b"])
        result = transfer(policy, fixture_state(), fixture_state(),
                          source_trajectories=attested_trajectories("A", "B"))
        self.assertEqual(result["status"], "ALLOW", result["reasons"])

    def test_a_bare_outcome_line_without_a_decision_is_not_evidence(self):
        forged = [{"record": "outcome", "trajectory_id": f"DT-{p}", "project": p,
                   "evidence_qualification": "qualified"} for p in ("A", "B")]
        result = transfer(self._policy(), fixture_state(), fixture_state(), records=forged)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT9", result["codes"])

    def test_an_unbacked_declared_project_blocks(self):
        policy = self._policy(evidence_projects=["A", "B", "Z"])
        result = transfer(policy, fixture_state(), fixture_state(),
                          source_trajectories=attested_trajectories("A", "B"))
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PT9", result["codes"])
