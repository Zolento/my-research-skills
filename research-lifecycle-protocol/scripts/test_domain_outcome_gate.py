#!/usr/bin/env python3
"""test_domain_outcome_gate.py — DP12–DP15 inside the real Evidence Outcome transaction.

The integration seam under test: `evidence_outcome.apply(..., state_path=...)` resolves
the route's declared domain profile, runs the domain metric-contract checks after every
core gate, and can only add violations. A domain violation blocks the SUPPORTED
confirmation while the raw packet and experiment records stay untouched.

Fixture recipe (mirrors the real R8 sequence):
1. take the pre-apply fixture state (X1 running, preregistration frozen);
2. bind the frozen metric contract into the preregistration (bind_metric_contract);
3. re-derive the packet/analysis/audit digests from the bound state;
4. call the real `eo.apply(..., state_path=...)`.

Everything here is a synthetic fixture: it proves the gate wiring (L2), not research
effectiveness (L3 NOT YET VALIDATED).
"""

from __future__ import annotations

import copy
import json
import pathlib
import sys
import tempfile
import unittest

import domain_profile as dp
import evidence_outcome as eo
import rlp_paths as rlp
from test_domain_tag import profile_config
from test_evidence_outcome import TIMESTAMP, fixture

ROOT = pathlib.Path(__file__).resolve().parent.parent


def bound_project(temp: pathlib.Path, config: dict) -> pathlib.Path:
    """A legacy-root route whose state has the frozen metric contract bound at R8."""
    route = temp / rlp.STORAGE_ROOT / "routes" / "A"
    route.mkdir(parents=True, exist_ok=True)
    state0, packet, analysis, audit = fixture("positive")
    state0 = dp.bind_metric_contract(config, state0)
    experiment = [x for x in state0["experiments"] if x["id"] == "X1"][0]
    packet["experiment_digest"] = eo.digest(experiment)
    analysis["base_state_digest"] = eo.digest(state0)
    analysis["context_digest"] = eo.digest(eo.validation_context(state0))
    analysis["packet_digest"] = eo.digest(packet)
    audit["analysis_digest"] = eo.digest(analysis)
    audit["packet_digest"] = eo.digest(packet)
    audit["state_digest"] = analysis["base_state_digest"]
    (route / "research-state.json").write_text(json.dumps(state0, ensure_ascii=False),
                                               encoding="utf-8")
    domain_dir = route / "domain"
    domain_dir.mkdir(exist_ok=True)
    (domain_dir / "mri-reconstruction.json").write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return state0, packet, analysis, audit


def metric_source(source_id: str, name: str, value, baseline=None) -> dict:
    content = {"metric": name, "value": value}
    if baseline is not None:
        content["baseline"] = baseline
    return {"id": source_id, "kind": "metric", "location": f"{name}.json",
            "content": json.dumps(content, ensure_ascii=False),
            "digest": eo.digest(json.dumps(content, ensure_ascii=False))}


def with_metric_observations(packet: dict, sources: list) -> dict:
    """Append structured metric sources; the original bindings stay intact.

    The analysis's validity checks and claim updates cite the original observations,
    so those sources must survive; the metric results arrive as additional
    digest-verified ``kind=metric`` sources (the frozen packet schema carries no
    numeric fields of its own).
    """
    new_packet = copy.deepcopy(packet)
    existing_ids = {s["id"] for s in new_packet["sources"]}
    for source in sources:
        if source["id"] not in existing_ids:
            new_packet["sources"].append(source)
    metric_ids = [s["id"] for s in sources if s["kind"] == "metric"
                  and s["id"] in {x["id"] for x in new_packet["sources"]}]
    if metric_ids:
        new_packet["observations"].append(
            {"id": "OM", "statement": "Structured metric results recorded.",
             "scope": "Dataset A / fixed budget", "source_ids": metric_ids[:1]})
    return new_packet


class OutcomeGateBase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = profile_config()
        self.config["metrics"] = {
            "primary": {"name": "nmse_global", "threshold": 0.02,
                        "direction": "lower_is_better", "baseline": 0.10,
                        "minimum_improvement": 0.01,
                        "preregistration_ref": "X1",
                        "frozen_before_results": True,
                        "frozen_at_state_version": 0},
            "structural": [{"name": "vessel_mip_connectivity", "threshold": 0.05,
                            "direction": "higher_is_better", "baseline": 0.30,
                            "minimum_improvement": 0.02,
                            "false_structure_max": 0.05,
                            "preregistration_ref": "X1",
                            "frozen_before_results": True,
                            "frozen_at_state_version": 0}],
            "measurement_domain": ["ssdu_loss"],
        }
        self.state0, self.packet, self.analysis, self.audit = bound_project(
            pathlib.Path(self.tmp.name), self.config)
        self.state_path = (pathlib.Path(self.tmp.name) /
                           rlp.STORAGE_ROOT / "routes" / "A" /
                           "research-state.json")

    def grounded_sources(self, nmse_value=0.05, nmse_baseline=0.10,
                         vessel_value=0.40, vessel_baseline=0.30):
        return self.sources(
            metric_source("SM1", "nmse_global", nmse_value, nmse_baseline),
            metric_source("SM2", "vessel_mip_connectivity", vessel_value,
                          vessel_baseline),
            metric_source("SM3", "false_structure_rate", 0.01),
            *[s for s in self.packet["sources"] if s["kind"] == "log"])

    def apply(self, state=None, packet=None, analysis=None, audit=None):
        state = state if state is not None else self.state0
        packet = packet if packet is not None else self.packet
        analysis = copy.deepcopy(self.analysis if analysis is None else analysis)
        audit = copy.deepcopy(self.audit if audit is None else audit)
        # the analysis/audit bind state/context/packet digests; re-derive them from the
        # arguments under test (exactly what an authoring agent must do after any edit)
        packet = copy.deepcopy(packet)
        packet["experiment_digest"] = eo.digest(
            [x for x in state["experiments"] if x["id"] == packet["experiment_id"]][0])
        analysis["base_state_digest"] = eo.digest(state)
        analysis["context_digest"] = eo.digest(eo.validation_context(state))
        analysis["packet_digest"] = eo.digest(packet)
        audit["analysis_digest"] = eo.digest(analysis)
        audit["packet_digest"] = eo.digest(packet)
        audit["state_digest"] = analysis["base_state_digest"]
        return eo.apply(state, packet, analysis, audit,
                        timestamp=TIMESTAMP, state_path=self.state_path)

    def sources(self, *entries):
        return with_metric_observations(self.packet, list(entries))


class TestMetricDirectionGate(OutcomeGateBase):

    def test_t12_improvement_follows_the_frozen_direction(self):
        """NMSE（越低越好）下降 + 结构指标（越高越好）上升 → 领域闸门放行。"""
        result = self.apply(packet=self.grounded_sources())
        self.assertEqual(result["status"], "PASS",
                         [e for e in result.get("errors", [])
                          if e.startswith("domain/")])
        self.assertEqual(result.get("domain_check"), "applied")
        self.assertNotIn("domain/", "".join(result.get("errors", [])))

    def test_t11_ssl_loss_improvement_alone_cannot_claim_image_success(self):
        """T11：ssdu_loss 改善而主指标未改善 → objective mismatch，SUPPORTED 被拒。"""
        sources = self.sources(
            metric_source("SM1", "ssdu_loss", 0.10, 0.20),      # improved
            metric_source("SM2", "nmse_global", 0.10, 0.10),    # unchanged
            metric_source("SM3", "false_structure_rate", 0.01),
            *[s for s in self.packet["sources"] if s["kind"] == "log"])
        result = self.apply(packet=sources)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any(e.startswith("domain/DPC3") or e.startswith("domain/DP12")
                            for e in result["errors"]),
                        result["errors"])

    def test_t12b_a_higher_is_better_metric_is_not_inverted(self):
        """PSNR/SSIM 类（越高越好）不得用 NMSE 的负号语义评判。"""
        sources = self.sources(
            metric_source("SM1", "nmse_global", 0.05, 0.10),    # lower → better
            metric_source("SM2", "vessel_mip_connectivity", 0.20, 0.30),  # worse
            metric_source("SM3", "false_structure_rate", 0.01),
            *[s for s in self.packet["sources"] if s["kind"] == "log"])
        result = self.apply(packet=sources)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("vessel_mip_connectivity" in e and "DP13" in e
                            for e in result["errors"]), result["errors"])
        # the direction conflict is about the structural metric only; NMSE's
        # lower-is-better improvement is not misread as a failure
        self.assertFalse(any("nmse_global 按冻结方向未达" in e
                             for e in result["errors"]), result["errors"])

    def test_missing_direction_blocks_instead_of_guessing(self):
        """契约缺方向 → 不足以支持结论（inconclusive），不得猜测。"""
        sources = self.sources(
            metric_source("SM1", "nmse_global", 0.05, 0.10),
            metric_source("SM2", "vessel_mip_connectivity", 0.40, 0.30),
            metric_source("SM3", "false_structure_rate", 0.01),
            *[s for s in self.packet["sources"] if s["kind"] == "log"])
        # the config keeps its direction; the *frozen contract* loses it (an authoring
        # mistake at freeze time is what this guard catches)
        state0 = copy.deepcopy(self.state0)
        for experiment in state0["experiments"]:
            contract = (experiment.get("preregistration") or {}).get(
                "domain_metric_contract")
            if isinstance(contract, dict):
                contract.pop("directions", None)
        result = self.apply(state=state0, packet=sources)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("DPC3" in e and "方向" in e for e in result["errors"]),
                        result["errors"])


class TestStructureRecoveryGate(OutcomeGateBase):

    def test_t13_global_improvement_without_structure_is_not_a_structure_claim(self):
        """T13：全局 NMSE 改善但结构指标恶化 → 不得宣称结构恢复。"""
        sources = self.sources(
            metric_source("SM1", "nmse_global", 0.05, 0.10),     # improved
            metric_source("SM2", "vessel_mip_connectivity", 0.20, 0.30),  # worse
            metric_source("SM3", "false_structure_rate", 0.01),
            *[s for s in self.packet["sources"] if s["kind"] == "log"])
        result = self.apply(packet=sources)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any(e.startswith("domain/DP13") and
                            "vessel_mip_connectivity" in e for e in result["errors"]),
                        result["errors"])

    def test_structural_recovery_requires_false_structure_evidence(self):
        """结构恢复结论必须带虚假结构率的实际来源，布尔声明不够。"""
        sources = self.sources(
            metric_source("SM1", "nmse_global", 0.05, 0.10),
            metric_source("SM2", "vessel_mip_connectivity", 0.40, 0.30),
            # deliberately no false_structure_rate source
            *[s for s in self.packet["sources"] if s["kind"] == "log"])
        result = self.apply(packet=sources)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("false_structure_rate" in e for e in result["errors"]),
                        result["errors"])

    def test_false_structures_over_the_frozen_cap_block_the_claim(self):
        sources = self.sources(
            metric_source("SM1", "nmse_global", 0.05, 0.10),
            metric_source("SM2", "vessel_mip_connectivity", 0.40, 0.30),
            metric_source("SM3", "false_structure_rate", 0.20),
            *[s for s in self.packet["sources"] if s["kind"] == "log"])
        result = self.apply(packet=sources)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("虚假结构率" in e for e in result.get("errors", [])),
                        result["errors"])


class TestGtProvenanceGate(OutcomeGateBase):

    def test_t14_machine_recorded_gt_selection_rejects_the_support(self):
        """T14：config 来源记录 uses_gt=true → 严格 GT-free 项目拒绝 SUPPORTED。"""
        gt_config_src = {
            "id": "SC1", "kind": "config", "location": "selection.json",
            "content": json.dumps({"model_selection": {"uses_gt": True}},
                                  ensure_ascii=False),
            "digest": eo.digest(json.dumps({"model_selection": {"uses_gt": True}},
                                           ensure_ascii=False))}
        sources = self.sources(
            metric_source("SM1", "nmse_global", 0.05, 0.10),
            metric_source("SM2", "vessel_mip_connectivity", 0.40, 0.30),
            metric_source("SM3", "false_structure_rate", 0.01),
            gt_config_src,
            *[s for s in self.packet["sources"] if s["kind"] == "log"])
        result = self.apply(packet=sources)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any(e.startswith("domain/DP14") for e in result["errors"]),
                        result["errors"])

    def test_t15_legal_omega_val_selection_is_not_a_gt_leak(self):
        """T15：合法 Ω_val 选择（无 GT）不被误判为泄漏。"""
        val_config_src = {
            "id": "SC1", "kind": "config", "location": "selection.json",
            "content": json.dumps({"model_selection": {
                "protocol": "omega_val_only", "uses_gt": False}},
                ensure_ascii=False),
            "digest": eo.digest(json.dumps({"model_selection": {
                "protocol": "omega_val_only", "uses_gt": False}}, ensure_ascii=False))}
        sources = self.sources(
            metric_source("SM1", "nmse_global", 0.05, 0.10),
            metric_source("SM2", "vessel_mip_connectivity", 0.40, 0.30),
            metric_source("SM3", "false_structure_rate", 0.01),
            val_config_src,
            *[s for s in self.packet["sources"] if s["kind"] == "log"])
        result = self.apply(packet=sources)
        self.assertNotIn("domain/DP14", "".join(result.get("errors", [])),
                         result.get("errors"))


class TestFrozenThresholdGate(OutcomeGateBase):

    def test_t16_a_post_hoc_threshold_edit_is_detected(self):
        """T16：结果后修改阈值 → DP15 摘要不一致被检出。"""
        tampered = copy.deepcopy(self.config)
        tampered["metrics"]["primary"]["threshold"] = 0.5      # relax after results
        (self.state_path.parent / "domain" / "mri-reconstruction.json").write_text(
            json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
        result = self.apply(packet=self.grounded_sources())
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("DP15" in e for e in result["errors"]), result["errors"])
        self.assertTrue(any("结果后修改" in e for e in result["errors"]),
                        result["errors"])

    def test_an_unbound_threshold_blocks_supported_claims(self):
        """未绑定预注册的阈值 → DPC1 拒绝 SUPPORTED（只能 inconclusive）。"""
        unbound = copy.deepcopy(self.config)
        unbound["metrics"]["primary"].pop("preregistration_ref")
        (self.state_path.parent / "domain" / "mri-reconstruction.json").write_text(
            json.dumps(unbound, ensure_ascii=False), encoding="utf-8")
        result = self.apply(packet=self.grounded_sources())
        self.assertEqual(result["status"], "FAIL")
        # an unbound threshold fails closed at either layer: the config check (DP15)
        # or the transaction gate (DPC1)
        self.assertTrue(any(e.startswith("domain/") and
                            ("DPC1" in e or "DP15" in e)
                            for e in result.get("errors", [])), result.get("errors"))


class TestGateDiscipline(OutcomeGateBase):

    def test_a_domain_violation_does_not_delete_the_experiment_record(self):
        """领域违规阻止 SUPPORTED 确认，但原始实验记录不被删除。"""
        sources = self.sources(
            metric_source("SM1", "ssdu_loss", 0.10, 0.20),
            metric_source("SM2", "nmse_global", 0.10, 0.10),
            metric_source("SM3", "false_structure_rate", 0.01),
            *[s for s in self.packet["sources"] if s["kind"] == "log"])
        result = self.apply(packet=sources)
        self.assertEqual(result["status"], "FAIL")
        # a failed apply mutates nothing: the experiment stays running, unanalysed
        experiment = [x for x in self.state0["experiments"] if x["id"] == "X1"][0]
        self.assertEqual(experiment["status"], "running")
        self.assertIsNone(experiment.get("outcome_analysis"))

    def test_no_profile_declared_keeps_core_behaviour(self):
        """T22 seed：未声明领域 Profile → 事务行为与 2.0.0 一致。"""
        (self.state_path.parent / "domain" / "mri-reconstruction.json").unlink()
        result = self.apply()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result.get("domain_check"), "inactive")

    def test_without_a_state_path_the_check_is_reported_as_skipped(self):
        result = eo.apply(self.state0, self.packet, self.analysis, self.audit,
                          timestamp=TIMESTAMP)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result.get("domain_check"), "skipped:no_state_path")

    def test_core_evidence_qualification_still_decides(self):
        """领域规则不能覆盖既有裁决：INVALID 实验仍无法支撑 claim。"""
        sources = self.sources(
            metric_source("SM1", "nmse_global", 0.05, 0.10),
            metric_source("SM2", "vessel_mip_connectivity", 0.40, 0.30),
            metric_source("SM3", "false_structure_rate", 0.01),
            *[s for s in self.packet["sources"] if s["kind"] == "log"])
        invalid_packet = copy.deepcopy(sources)
        invalid_packet["execution_status"] = "failed"
        result = self.apply(packet=invalid_packet)
        self.assertNotEqual(result["status"], "PASS")
        combined = "".join(result.get("errors", []))
        self.assertTrue(any(k in combined for k in
                            ("negative evidence", "INVALID", "validity", "invalid")),
                        result["errors"])


if __name__ == "__main__":
    unittest.main()
