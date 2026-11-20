#!/usr/bin/env python3
"""test_mri_training.py — MRI Research Contract v1.0 的执行绑定测试（stdlib unittest，不联网）

运行：
    python3 -m unittest discover -s scripts -p "test_*.py"
    python3 scripts/test_mri_training.py

为什么需要它
------------
v2.3.1 的执行器把 `mri_training.selection == "full_val_gt"` 写死，并要求领域 profile 的
GT 可用且参与选模。于是用户批准的 `gt_free_frozen` **文档加了也跑不起来**。修这一条不能只改
文档：必须同时有两侧 fixture，否则下次又会退化成「只有一种合法模式」。

覆盖点
------
1. `sync-agents` 幂等：二次同步不改文件；项目原有非受管文字不丢；受管标记只出现一次。
2. `full_val_gt`：合法通过；`best_val_metric` 只收 PSNR / complex_NMSE；少字段拒绝。
3. `gt_free_frozen`：合法通过（含冻结字段与真实预注册文件）；
   缺任一冻结字段、缺源文件、声明 `best_val_metric`、profile 相反 —— 全部拒绝。
4. 交叉一致性：profile 的 `gt.available` / `uses_gt` / `metric` / `direction` 必须与配置相符。
5. 禁止项：`uses_loss_measurements: true` 即使其它字段齐全也拒绝。
6. `evaluation_only` 模式不需要选模字段，但仍要求受管段一致。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import domain_profile
import mri_training as mt
import rlp_paths as rlp

PROFILE = {
    "_schema": "research-idea-pipeline/domain-profile@1",
    "profile": "mri-reconstruction",
    "acquisition": {
        "forward_operators": ["coil_sensitivity", "fourier", "undersampling_mask"],
        "coils": 20,
        "undersampling": {"pattern": "variable_density", "acceleration": 10},
        "noise": {"model": "gaussian", "level_known": False},
    },
    "ssl": {
        "type": "ssdu",
        "split": {"input": "theta", "loss": "lambda", "held_out_validation": "val",
                  "measurement_identity": {"fields": "subject/volume/slice/acquisition",
                                           "mask_sharing_allowed": True}},
        "acs": {"usage": "frozen_protocol"},
    },
    "frozen": {"components": ["backbone"], "forbidden_changes": ["主干权重"]},
    "metrics": {
        "primary": {"name": "complex_nmse", "threshold": 0.02,
                    "frozen_before_results": True, "frozen_at_state_version": 1},
    },
    "resources": {"gpu_hours_budget": 12},
}


def gt_profile(**selection):
    profile = json.loads(json.dumps(PROFILE))
    profile["gt"] = {"available": True, "usage": "validation_only"}
    profile["model_selection"] = {"protocol": "full_val_gt", "uses_gt": True,
                                  "uses_loss_measurements": False}
    profile["model_selection"].update(selection)
    return profile


def gt_free_profile(**selection):
    profile = json.loads(json.dumps(PROFILE))
    profile["gt"] = {"available": False, "usage": "none"}
    profile["model_selection"] = {"protocol": "gt_free_frozen", "uses_gt": False,
                                  "uses_loss_measurements": False,
                                  "metric": "lambda_holdout_nmse", "direction": "minimize"}
    profile["model_selection"].update(selection)
    return profile


def gt_report(**overrides):
    report = {
        "budget": "18000 optimizer steps",
        "learning_rate": "3e-3, warmup 3000",
        "optimizer": "AdamW, weight_decay=0.01",
        "input": "[B,C,H,W] complex k-space, per-slice column mask",
        "output": "[B,H,W] complex image",
        "mask": "per-slice; 2D Cartesian column (W) sampling; ACS 4x4",
        "normalization": "measurement-only training; GT RMS paired evaluation",
        "csm": {"mode": "dataset_stored", "source": "csmslice field in dataset",
                "sample_identity": "subject/volume/slice/acquisition"},
        "checkpoint": "best_val + latest",
        "report_ref": "docs/dev/training-report-2026-11-20.md",
        "selection": "full_val_gt",
        "best_val_metric": "PSNR",
    }
    report.update(overrides)
    return report


def gt_free_report(**overrides):
    report = gt_report(selection="gt_free_frozen",
                       selection_metric="lambda_holdout_nmse",
                       metric_direction="minimize",
                       metric_source="mask-split holdout measurements",
                       selection_scope="full val (no GT)",
                       stop_rule="no improvement in 10 epochs",
                       selection_source_ref="prereg/holdout-selection.md")
    report.pop("best_val_metric", None)
    report.update(overrides)
    return report


class ProjectCase(unittest.TestCase):
    """一个临时项目：已同步受管段的 AGENTS.md + 一条 route + 领域 profile。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "proj"
        self.root.mkdir()
        (self.root / "AGENTS.md").write_text("# 项目自己的约定\n\n保留这段文字。\n",
                                             encoding="utf-8")
        self.state_path = (self.root / rlp.STORAGE_ROOT / "routes/A/research-state.json")
        self.state_path.parent.mkdir(parents=True)
        self.state_path.write_text(json.dumps({
            "_schema": "research-idea-pipeline/research-state@1", "state_version": 1,
            "contract": {}, "claims": [], "evidence": [], "assumptions": [],
            "hypotheses": [], "experiments": [], "literature": [], "failures": [],
            "uncertainties": [],
        }), encoding="utf-8")
        (self.root / "prereg").mkdir()
        (self.root / "prereg/holdout-selection.md").write_text(
            "# 冻结的无 GT 选模方案\n", encoding="utf-8")
        mt.sync_agents(self.root)
        self.profile_path = self.state_path.parent / "domain/mri-reconstruction.json"
        self.profile_path.parent.mkdir()
        self.set_profile(gt_profile())

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def set_profile(self, profile: dict) -> None:
        self.profile_path.write_text(json.dumps(profile), encoding="utf-8")

    def bind(self, report: dict):
        return mt.execution_binding(self.state_path, {}, [{"mri_training": report}])

    def rejects(self, report: dict, needle: str) -> None:
        with self.assertRaises(ValueError) as caught:
            self.bind(report)
        self.assertIn(needle, str(caught.exception))


class SyncTests(ProjectCase):
    def test_idempotent_and_preserves_project_text(self) -> None:
        agents = self.root / "AGENTS.md"
        first = agents.read_bytes()
        self.assertTrue(first.startswith("# 项目自己的约定".encode("utf-8")))
        self.assertIn("保留这段文字".encode("utf-8"), first)
        self.assertFalse(mt.sync_agents(self.root))
        self.assertEqual(agents.read_bytes(), first)
        text = first.decode("utf-8")
        self.assertEqual(text.count(mt.BEGIN), 1)
        self.assertEqual(text.count(mt.END), 1)

    def test_hand_edit_of_managed_block_is_detected(self) -> None:
        agents = self.root / "AGENTS.md"
        agents.write_bytes(agents.read_bytes().replace(b"gt_free_frozen", b"gt_free_custom"))
        self.rejects(gt_report(), "MRI_TRAINING_AGENTS")

    def test_missing_agents_file_blocks_training(self) -> None:
        (self.root / "AGENTS.md").unlink()
        self.rejects(gt_report(), "MRI_TRAINING_AGENTS")


class FullValGtTests(ProjectCase):
    def test_legal_gt_selection_passes(self) -> None:
        binding = self.bind(gt_report())
        self.assertEqual(binding["report_digests"].__len__(), 1)
        self.assertEqual(len(binding["policy_sha256"]), 64)

    def test_complex_nmse_is_legal(self) -> None:
        self.assertIsNotNone(self.bind(gt_report(best_val_metric="complex_NMSE")))

    def test_bare_nmse_is_rejected(self) -> None:
        self.rejects(gt_report(best_val_metric="NMSE"), "complex_NMSE")

    def test_each_required_field_is_enforced(self) -> None:
        for field in ("budget", "learning_rate", "optimizer", "input", "output",
                      "mask", "normalization", "checkpoint", "report_ref"):
            with self.subTest(field=field):
                report = gt_report()
                report.pop(field)
                self.rejects(report, "MRI_TRAINING_REPORT")

    def test_full_val_gt_requires_gt_available(self) -> None:
        self.set_profile(gt_free_profile())
        self.rejects(gt_report(), "MRI_TRAINING_GT")

    def test_loss_measurement_selection_is_forbidden(self) -> None:
        self.set_profile(gt_profile(uses_loss_measurements=True))
        self.rejects(gt_report(), "MRI_TRAINING_SELECTION")


class GtFreeTests(ProjectCase):
    def setUp(self) -> None:
        super().setUp()
        self.set_profile(gt_free_profile())

    def test_legal_gt_free_selection_passes(self) -> None:
        """这一条是本次修复的核心：合法 GT-free 必须能通过，而不是靠关掉检查。"""
        binding = self.bind(gt_free_report())
        self.assertEqual(len(binding["report_digests"]), 1)

    def test_each_frozen_field_is_enforced(self) -> None:
        for field in mt.GT_FREE_FIELDS:
            with self.subTest(field=field):
                report = gt_free_report()
                report.pop(field)
                self.rejects(report, "MRI_TRAINING_SELECTION")

    def test_missing_preregistration_file_is_rejected(self) -> None:
        self.rejects(gt_free_report(selection_source_ref="prereg/does-not-exist.md"),
                     "selection_source_ref")

    def test_gt_metric_in_gt_free_report_is_rejected(self) -> None:
        self.rejects(gt_free_report(best_val_metric="PSNR"), "best_val_metric")

    def test_bad_direction_is_rejected(self) -> None:
        self.rejects(gt_free_report(metric_direction="lower"), "metric_direction")

    def test_profile_metric_must_match(self) -> None:
        self.rejects(gt_free_report(selection_metric="other_metric"), "MRI_TRAINING_GT")

    def test_profile_direction_must_match(self) -> None:
        self.set_profile(gt_free_profile(direction="maximize"))
        self.rejects(gt_free_report(metric_direction="minimize"), "MRI_TRAINING_GT")

    def test_profile_claiming_gt_is_rejected(self) -> None:
        self.set_profile(gt_profile())
        self.rejects(gt_free_report(), "MRI_TRAINING_GT")

    def test_unknown_selection_mode_is_rejected(self) -> None:
        self.rejects(gt_free_report(selection="val_subset"), "MRI_TRAINING_SELECTION")


class CsmSourceTests(ProjectCase):
    """MRI-10：默认强制数据集存储 CSM；联合估计是唯一方法类别例外。"""

    def setUp(self) -> None:
        super().setUp()
        (self.root / "docs/dev").mkdir(parents=True, exist_ok=True)
        (self.root / "docs/dev/joint-sense-protocol.md").write_text(
            "# 启动前冻结的联合估计灵敏度方法协议\n", encoding="utf-8")

    def joint(self, **csm_overrides):
        csm = {"mode": "joint_estimation",
               "protocol_ref": "docs/dev/joint-sense-protocol.md",
               "eval_reference": "stored"}
        csm.update(csm_overrides)
        return gt_report(csm=csm)

    def test_dataset_stored_passes(self) -> None:
        self.assertIsNotNone(self.bind(gt_report()))

    def test_dataset_stored_requires_source_and_identity(self) -> None:
        for field in ("source", "sample_identity"):
            with self.subTest(field=field):
                csm = dict(gt_report()["csm"])
                csm.pop(field)
                self.rejects(gt_report(csm=csm), f"csm.{field}")

    def test_string_form_is_rejected(self) -> None:
        """旧的自撰字符串形态不再合法：必须是对象，防止两种形状并存。"""
        self.rejects(gt_report(csm="stored"), "csm 必须是对象")

    def test_unknown_mode_is_rejected(self) -> None:
        self.rejects(gt_report(csm={"mode": "estimated"}), "csm.mode")

    def test_single_coil_not_applicable_is_legal(self) -> None:
        self.assertIsNotNone(self.bind(gt_report(csm={"mode": "not_applicable"})))

    def test_joint_estimation_with_frozen_protocol_passes(self) -> None:
        self.assertIsNotNone(self.bind(self.joint()))

    def test_joint_estimation_requires_protocol_ref(self) -> None:
        csm = {"mode": "joint_estimation", "eval_reference": "stored"}
        self.rejects(gt_report(csm=csm), "csm.protocol_ref")

    def test_joint_estimation_protocol_must_exist(self) -> None:
        self.rejects(self.joint(protocol_ref="docs/dev/missing.md"), "csm.protocol_ref")

    def test_joint_estimation_requires_eval_reference(self) -> None:
        csm = {"mode": "joint_estimation",
               "protocol_ref": "docs/dev/joint-sense-protocol.md"}
        self.rejects(gt_report(csm=csm), "csm.eval_reference")

    def test_non_frozen_eval_reference_needs_ref(self) -> None:
        self.rejects(self.joint(eval_reference="method_estimate"), "csm.eval_reference_ref")
        self.assertIsNotNone(self.bind(self.joint(
            eval_reference="method_estimate",
            eval_reference_ref="docs/dev/joint-sense-protocol.md")))

    def test_profile_declaration_must_agree(self) -> None:
        profile = gt_profile()
        profile["acquisition"]["coil_sensitivity"] = {"mode": "dataset_stored"}
        self.set_profile(profile)
        self.rejects(self.joint(), "相反")

    def test_profile_not_applicable_agrees_for_single_coil(self) -> None:
        profile = gt_profile()
        profile["acquisition"]["coil_sensitivity"] = {"mode": "not_applicable"}
        self.set_profile(profile)
        self.assertIsNotNone(self.bind(gt_report(csm={"mode": "not_applicable"})))


class EvaluationOnlyTests(ProjectCase):
    def test_evaluation_only_needs_no_selection(self) -> None:
        binding = mt.execution_binding(
            self.state_path, {}, [{"mri_training": {"mode": "evaluation_only"}}])
        self.assertIsNotNone(binding)
        self.assertEqual(binding["report_digests"], [])

    def test_unknown_mode_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as caught:
            mt.execution_binding(self.state_path, {},
                                 [{"mri_training": {"mode": "dry"}}])
        self.assertIn("mode", str(caught.exception))


class ProfileRuleTests(ProjectCase):
    def test_gt_free_profile_needs_metric_and_direction(self) -> None:
        findings = domain_profile.validate(
            gt_free_profile(metric="", direction=None), profile="mri-reconstruction")
        rules = {finding.rule for finding in findings}
        self.assertIn("DP6", rules)

    def test_gt_free_profile_may_not_claim_gt(self) -> None:
        findings = domain_profile.validate(
            gt_free_profile(uses_gt=True), profile="mri-reconstruction")
        self.assertTrue(any(f.rule == "DP6" for f in findings))

    def test_no_profile_means_no_binding(self) -> None:
        self.profile_path.unlink()
        (self.root / "AGENTS.md").write_text("# 纯项目\n", encoding="utf-8")
        self.assertIsNone(mt.execution_binding(self.state_path, {}, [{"mri_training": gt_report()}]))


class ProfileCsmRuleTests(ProjectCase):
    """DP3a：profile 声明线圈灵敏度来源时的形状与一致性问题。"""

    def rules(self, profile: dict) -> set:
        return {finding.rule for finding in domain_profile.validate(
            profile, profile="mri-reconstruction")}

    def test_declared_dataset_stored_passes(self) -> None:
        profile = gt_profile()
        profile["acquisition"]["coil_sensitivity"] = {
            "mode": "dataset_stored", "source": "csmslice in dataset"}
        self.assertFalse([f for f in domain_profile.validate(
            profile, profile="mri-reconstruction")
            if f.path.startswith("acquisition.coil_sensitivity")])

    def test_dataset_stored_needs_source(self) -> None:
        profile = gt_profile()
        profile["acquisition"]["coil_sensitivity"] = {"mode": "dataset_stored"}
        self.assertTrue(any(f.path == "acquisition.coil_sensitivity.source"
                            for f in domain_profile.validate(
                                profile, profile="mri-reconstruction")))

    def test_joint_estimation_needs_protocol(self) -> None:
        profile = gt_profile()
        profile["acquisition"]["coil_sensitivity"] = {"mode": "joint_estimation"}
        self.assertTrue(any(f.path == "acquisition.coil_sensitivity.protocol_ref"
                            for f in domain_profile.validate(
                                profile, profile="mri-reconstruction")))

    def test_unknown_mode_is_rejected(self) -> None:
        profile = gt_profile()
        profile["acquisition"]["coil_sensitivity"] = {"mode": "estimated"}
        self.assertTrue(any(f.path == "acquisition.coil_sensitivity.mode"
                            for f in domain_profile.validate(
                                profile, profile="mri-reconstruction")))

    def test_absent_declaration_changes_nothing(self) -> None:
        """未声明 coil_sensitivity 的既有 profile 不因此多出任何发现。"""
        findings = domain_profile.validate(gt_profile(), profile="mri-reconstruction")
        self.assertFalse([f for f in findings
                          if f.path.startswith("acquisition.coil_sensitivity")])


if __name__ == "__main__":
    unittest.main()
