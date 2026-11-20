#!/usr/bin/env python3
"""Install the MRI training policy in AGENTS.md and validate managed launches.

两种合法的选模协议（MRI Research Contract v1.0 §2）：

    full_val_gt      有完整 val GT，按 PSNR（越大越好）或 complex_NMSE（越小越好）选 best_val
    gt_free_frozen   真正 GT-free，事前冻结无 GT 的选择指标、方向、来源、范围、停止准则

本模块只做两件事：把受管段同步进项目根 `AGENTS.md`，以及在执行门禁里核对绑定配置。
它**不**判断科学有效性，也不启动训练。任何缺项都 fail closed，不静默兜底。
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import domain_profile
import rlp_paths

POLICY = (Path(__file__).resolve().parents[1]
          / domain_profile.profile_doc("mri-reconstruction")).with_name("training-policy.md")
BEGIN = "<!-- BEGIN RLP MRI TRAINING -->"
END = "<!-- END RLP MRI TRAINING -->"

#: 训练前报告必须覆盖的字段（Contract v1.0 §10）。
REPORT_FIELDS = ("budget", "learning_rate", "optimizer", "input", "output",
                 "mask", "normalization", "checkpoint")
#: 有 GT 时的合法主指标。`NMSE` 不再默认等同 `complex_NMSE`（Contract §6.1）。
GT_METRICS = ("PSNR", "complex_NMSE")
#: GT-free 选模必须事前冻结的字段（Contract §2.3）。
GT_FREE_FIELDS = ("selection_metric", "metric_direction", "metric_source",
                  "selection_scope", "stop_rule", "selection_source_ref")
DIRECTIONS = ("maximize", "minimize")
#: MRI-10：灵敏度来源。默认 dataset_stored；joint_estimation 是唯一方法类别例外。
CSM_MODES = ("dataset_stored", "joint_estimation", "not_applicable")
#: 评价参考若沿用项目冻结口径，不需要额外的授权文件。
FROZEN_EVAL_REFERENCES = ("stored", "frozen_protocol")


def project_section(text: str) -> str:
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(BEGIN) >= text.index(END):
        raise ValueError("MRI_TRAINING_AGENTS: 管理章节标记缺失或重复")
    return text[text.index(BEGIN):text.index(END) + len(END)]


def sync_agents(project: Path) -> bool:
    agents = project / "AGENTS.md"
    original = agents.read_bytes() if agents.exists() else b""
    text = original.decode("utf-8")
    newline = "\r\n" if b"\r\n" in original else "\n"
    section = project_section(POLICY.read_text(encoding="utf-8")).replace("\n", newline)
    if BEGIN in text or END in text:
        updated = text.replace(project_section(text), section, 1)
    else:
        separator = "" if not text or text.endswith(newline * 2) else (
            newline if text.endswith(newline) else newline * 2
        )
        updated = text + separator + section + newline
    if text == updated:
        return False
    agents.write_bytes(updated.encode("utf-8"))
    return True


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _resolve_source(project: Path, reference: str) -> Optional[Path]:
    """`selection_source_ref` 必须指向真实存在的文件（预注册 / 冻结协议）。"""
    candidate = Path(reference)
    path = candidate if candidate.is_absolute() else project / candidate
    return path if path.is_file() else None



def validate_csm(report: Dict[str, Any], project: Path, profile: Any = None) -> Dict[str, Any]:
    """MRI-10：校验灵敏度来源。

    默认强制使用数据集存储的 CSM。`joint_estimation` 是唯一方法类别例外，它必须能指回一份
    启动前冻结的方法协议，并写明评价时的线圈合并口径 —— 例外**不**延长到跨方法比较的参考，
    否则每个方法的参考随方法漂移，表内数字不再可比。
    """
    csm = report.get("csm")
    if not isinstance(csm, dict):
        raise ValueError(
            "MRI_TRAINING_CSM: csm 必须是对象，含 mode 字段"
            "（dataset_stored / joint_estimation / not_applicable）")
    mode = csm.get("mode")
    if mode not in CSM_MODES:
        raise ValueError(
            "MRI_TRAINING_CSM: csm.mode 必须为 dataset_stored、joint_estimation 或 "
            "not_applicable")
    summary: Dict[str, Any] = {"mode": mode}

    if mode == "not_applicable":
        # 单线圈例外必须核对线圈数：`not_applicable` 不能用作多线圈项目的逃生门。
        coils = coil_count(profile, csm)
        if coils is None:
            raise ValueError(
                "MRI_TRAINING_CSM: not_applicable 需要可核对的线圈数："
                "在领域 profile 声明 acquisition.coils，或在本配置写 csm.coil_count")
        if coils != 1:
            raise ValueError(
                f"MRI_TRAINING_CSM: not_applicable 只适用于单线圈；"
                f"本项目线圈数为 {coils}，必须使用 dataset_stored 或 joint_estimation")
        summary.update({"declared": "not_applicable", "coil_count": coils})
    elif mode == "dataset_stored":
        for field in ("source", "sample_identity"):
            if not _text(csm.get(field)):
                raise ValueError(
                    f"MRI_TRAINING_CSM: dataset_stored 必须声明 csm.{field}"
                    "（真实存储来源与样本配对键）")
        summary.update({"source": csm["source"], "sample_identity": csm["sample_identity"]})
    else:  # joint_estimation
        protocol = csm.get("protocol_ref")
        if not _text(protocol):
            raise ValueError(
                "MRI_TRAINING_CSM: joint_estimation 必须给出 csm.protocol_ref"
                "（实验启动前冻结的方法协议）")
        if _resolve_source(project, protocol) is None:
            raise ValueError(
                "MRI_TRAINING_CSM: csm.protocol_ref 必须指向已存在的冻结方法协议")
        evaluation = csm.get("eval_reference")
        if not _text(evaluation):
            raise ValueError(
                "MRI_TRAINING_CSM: joint_estimation 必须声明 csm.eval_reference"
                "（评价时的线圈合并口径；例外不覆盖评估参考）")
        if evaluation.strip() not in FROZEN_EVAL_REFERENCES:
            reference = csm.get("eval_reference_ref")
            if not _text(reference) or _resolve_source(project, reference) is None:
                raise ValueError(
                    "MRI_TRAINING_CSM: csm.eval_reference 不是项目冻结口径时，"
                    "必须给出指向冻结协议的 csm.eval_reference_ref")
            summary["eval_reference_ref"] = reference
        summary.update({"protocol_ref": protocol, "eval_reference": evaluation})

    if profile is not None and getattr(profile, "active", False):
        declared = csm_declared_in_profile(profile.config)
        if declared is not None and declared != mode:
            raise ValueError(
                "MRI_TRAINING_CSM: 领域 profile 的 acquisition.coil_sensitivity.mode "
                f"是 {declared}，与训练配置的 {mode} 相反")
    return summary


def coil_count(profile: Any, csm: Dict[str, Any]) -> Optional[int]:
    """线圈数来源：领域 profile 的 acquisition.coils，其次训练配置的 csm.coil_count。

    两处都没有时返回 None —— 调用方必须把「无法确认线圈数」当作拒绝条件，
    不得默认成单线圈。
    """
    candidates = []
    if profile is not None and getattr(profile, "active", False):
        acquisition = (profile.config or {}).get("acquisition")
        if isinstance(acquisition, dict):
            candidates.append(acquisition.get("coils"))
    candidates.append(csm.get("coil_count"))
    for value in candidates:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
            return value
    return None


def csm_declared_in_profile(config: Any) -> Optional[str]:
    """领域 profile 若声明了 `acquisition.coil_sensitivity.mode`，返回它。"""
    if not isinstance(config, dict):
        return None
    acquisition = config.get("acquisition")
    if not isinstance(acquisition, dict):
        return None
    csm = acquisition.get("coil_sensitivity")
    if not isinstance(csm, dict):
        return None
    mode = csm.get("mode")
    return mode if isinstance(mode, str) else None


def report_lint_status(text: str) -> Dict[str, Any]:
    """把报告交给已有的结构 lint 检查一次，结果进入绑定摘要。

    这是**调用既有 lint**，不新增科研门禁：它只报告结构与字段完整性（`REP-01`—`REP-07`），
    不判断科学结论。`status` 随报告内容变化，因此报告被改写会让 receipt 的绑定摘要变化。
    """
    try:
        import report_lint
    except ImportError:  # 安装副本缺该模块时如实降级，不假装检查过
        return {"status": "UNAVAILABLE", "blocks": 0, "warns": 0, "rules": []}
    result = report_lint.lint(text, "training-report")
    return {"status": result["status"], "blocks": result["blocks"],
            "warns": result["warns"],
            "rules": sorted({f["rule"] for f in result["findings"]})}


def validate_report_ref(report: Dict[str, Any], project: Path,
                        selection: str, csm_mode: str) -> Dict[str, Any]:
    """训练前报告必须真实存在、内容与配置一致，摘要进入绑定。

    `report_ref` 只检查非空等于没有检查：报告可以不存在，或写着另一套配置。
    这里要求文件存在、可读，并且同时提到本次的 `selection` 与 `csm.mode`；
    它的 SHA-256 进入执行绑定，报告被改动会让 receipt 失效（RECEIPT_CONTENT_MISMATCH）。
    """
    reference = report["report_ref"]
    path = _resolve_source(project, reference)
    if path is None:
        raise ValueError(
            "MRI_TRAINING_REPORT_REF: report_ref 必须指向已存在的训练前报告文件")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(
            f"MRI_TRAINING_REPORT_REF: 报告文件不可读（{type(exc).__name__}）") from None
    missing = [token for token in (selection, csm_mode) if token not in text]
    if missing:
        raise ValueError(
            "MRI_TRAINING_REPORT_REF: 报告内容与配置不一致，缺少 "
            + "、".join(missing) + "；报告须与绑定配置描述同一套设置")
    return {"path": reference, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "bytes": len(text.encode("utf-8")),
            "lint": report_lint_status(text)}


def validate_report(report: Dict[str, Any], project: Path,
                    profile: Any) -> Tuple[str, Dict[str, Any]]:
    """校验一份绑定配置的 `mri_training` 报告，返回 (selection, 归一化摘要)。

    失败时抛 ValueError，错误码前缀即规则来源，便于直接贴回执行者。
    """
    if not isinstance(report, dict):
        raise ValueError("MRI_TRAINING_REPORT: mri_training 必须是对象")
    missing = [field for field in REPORT_FIELDS if not _text(report.get(field))]
    if not _text(report.get("report_ref")):
        missing.append("report_ref")
    if missing:
        raise ValueError("MRI_TRAINING_REPORT: 缺少 " + ", ".join(missing))
    csm = validate_csm(report, project, profile)
    selection = report.get("selection")
    if selection not in ("full_val_gt", "gt_free_frozen"):
        raise ValueError(
            "MRI_TRAINING_SELECTION: selection 必须为 full_val_gt 或 gt_free_frozen")
    summary: Dict[str, Any] = {"selection": selection, "csm": csm,
                               "report_ref": validate_report_ref(
                                   report, project, selection, csm["mode"])}

    if selection == "full_val_gt":
        metric = report.get("best_val_metric")
        if metric not in GT_METRICS:
            raise ValueError(
                "MRI_TRAINING_REPORT: best_val_metric 必须为 PSNR 或 complex_NMSE"
                "（幅度 NMSE 须单列 magnitude_NMSE，不得用 NMSE 含糊代替）")
        summary["best_val_metric"] = metric
        if profile.active:
            gt = profile.config.get("gt")
            model = profile.config.get("model_selection")
            if (not isinstance(gt, dict) or gt.get("available") is not True
                    or gt.get("usage") not in ("validation_only", "development", "full")):
                raise ValueError(
                    "MRI_TRAINING_GT: full_val_gt 要求领域 profile 声明 gt.available: true"
                    " 且 gt.usage 为 validation_only / development / full")
            if (not isinstance(model, dict) or model.get("uses_gt") is not True):
                raise ValueError(
                    "MRI_TRAINING_GT: full_val_gt 要求 model_selection.uses_gt: true")
            if model.get("protocol") != "full_val_gt":
                raise ValueError(
                    "MRI_TRAINING_SELECTION: 训练配置是 full_val_gt，但领域 profile 的"
                    f" model_selection.protocol 是 {model.get('protocol')!r}；两者必须一致")
        return selection, summary

    # gt_free_frozen —— 事前冻结的无 GT 选择方案
    missing = [field for field in GT_FREE_FIELDS if not _text(report.get(field))]
    if missing:
        raise ValueError(
            "MRI_TRAINING_SELECTION: GT-free 选模缺少冻结字段 " + ", ".join(missing))
    if report.get("metric_direction") not in DIRECTIONS:
        raise ValueError("MRI_TRAINING_SELECTION: metric_direction 必须为 maximize 或 minimize")
    source = _resolve_source(project, report["selection_source_ref"])
    if source is None:
        raise ValueError(
            "MRI_TRAINING_SELECTION: selection_source_ref 必须指向已存在的预注册文件")
    if _text(report.get("best_val_metric")):
        raise ValueError(
            "MRI_TRAINING_SELECTION: GT-free 训练不得声明 best_val_metric"
            "（GT 指标不参与无 GT 选模）")
    if profile.active:
        gt = profile.config.get("gt")
        model = profile.config.get("model_selection")
        if not isinstance(gt, dict) or gt.get("available") is not False:
            raise ValueError(
                "MRI_TRAINING_GT: gt_free_frozen 要求领域 profile 声明 gt.available: false")
        if not isinstance(model, dict) or model.get("uses_gt") is not False:
            raise ValueError(
                "MRI_TRAINING_GT: gt_free_frozen 要求 model_selection.uses_gt: false")
        if model.get("metric") != report["selection_metric"]:
            raise ValueError(
                "MRI_TRAINING_GT: 领域 profile 的 model_selection.metric 必须与"
                " selection_metric 一致")
        if model.get("direction") not in (None, report["metric_direction"]):
            raise ValueError(
                "MRI_TRAINING_GT: 领域 profile 的 model_selection.direction 与"
                " metric_direction 不一致")
        if model.get("protocol") != "gt_free_frozen":
            raise ValueError(
                "MRI_TRAINING_SELECTION: 训练配置是 gt_free_frozen，但领域 profile 的"
                f" model_selection.protocol 是 {model.get('protocol')!r}；两者必须一致")
    summary.update({field: report[field] for field in GT_FREE_FIELDS})
    return selection, summary


def execution_binding(state_path: Path, state: dict, configs: list[dict]) -> dict | None:
    profile = domain_profile.load(state_path.parent, "mri-reconstruction", state=state)
    try:
        project = rlp_paths.project_root_from_state(state_path)
    except rlp_paths.LayoutError:
        if not profile.active:
            return None
        raise ValueError("MRI_TRAINING_AGENTS: 无法解析 MRI 项目根") from None
    agents = project / "AGENTS.md"
    text = agents.read_text(encoding="utf-8") if agents.is_file() else ""
    if not profile.active and BEGIN not in text and END not in text:
        return None
    policy = project_section(POLICY.read_text(encoding="utf-8"))
    if project_section(text) != policy:
        raise ValueError("MRI_TRAINING_AGENTS: 先同步项目根 AGENTS.md 的 MRI 训练规则")
    reports = [config["mri_training"] for config in configs if "mri_training" in config]
    if not reports:
        raise ValueError("MRI_TRAINING_REPORT: 绑定训练配置必须包含 mri_training")
    model = profile.config.get("model_selection")
    if isinstance(model, dict) and model.get("uses_loss_measurements") is True:
        raise ValueError(
            "MRI_TRAINING_SELECTION: 禁止使用自监督 mask split 损失或测量残差选模")
    summaries: List[Dict[str, Any]] = []
    for report in reports:
        if not isinstance(report, dict):
            raise ValueError("MRI_TRAINING_REPORT: mri_training 必须是对象")
        mode = report.get("mode", "training")
        if mode == "evaluation_only":
            continue
        if mode != "training":
            raise ValueError("MRI_TRAINING_REPORT: mode 必须为 training 或 evaluation_only")
        _, summary = validate_report(report, project, profile)
        summaries.append(summary)
    return {
        "policy_sha256": hashlib.sha256(policy.encode("utf-8")).hexdigest(),
        "profile_sha256": hashlib.sha256(json.dumps(
            profile.config, sort_keys=True, ensure_ascii=False
        ).encode("utf-8")).hexdigest() if profile.active else None,
        "report_digests": [hashlib.sha256(json.dumps(
            summary, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
            for summary in summaries],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["sync-agents"])
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    try:
        updated = sync_agents(args.project)
    except (OSError, ValueError) as exc:
        parser.exit(3, f"{exc}\n")
    print("已同步 MRI 训练规则" if updated else "MRI 训练规则已是最新")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
