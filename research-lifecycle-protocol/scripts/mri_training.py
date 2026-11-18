#!/usr/bin/env python3
"""Install the MRI training policy in AGENTS.md and validate managed launches."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import domain_profile
import rlp_paths

POLICY = (Path(__file__).resolve().parents[1]
          / domain_profile.profile_doc("mri-reconstruction")).with_name("training-policy.md")
BEGIN = "<!-- BEGIN RLP MRI TRAINING -->"
END = "<!-- END RLP MRI TRAINING -->"
REPORT_FIELDS = ("budget", "learning_rate", "optimizer", "input", "output")


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
    training = False
    for report in reports:
        if not isinstance(report, dict):
            raise ValueError("MRI_TRAINING_REPORT: mri_training 必须是对象")
        mode = report.get("mode", "training")
        if mode == "evaluation_only":
            continue
        if mode != "training":
            raise ValueError("MRI_TRAINING_REPORT: mode 必须为 training 或 evaluation_only")
        training = True
        missing = [field for field in REPORT_FIELDS
                   if not isinstance(report.get(field), str) or not report[field].strip()]
        if missing:
            raise ValueError("MRI_TRAINING_REPORT: 缺少 " + ", ".join(missing))
        if report.get("selection") != "full_val_gt":
            raise ValueError("MRI_TRAINING_GT: selection 必须为 full_val_gt")
        if report.get("best_val_metric") not in ("PSNR", "NMSE"):
            raise ValueError("MRI_TRAINING_REPORT: best_val_metric 必须为 PSNR 或 NMSE")
    if training and profile.active:
        gt = profile.config.get("gt")
        selection = profile.config.get("model_selection")
        if (not isinstance(gt, dict) or gt.get("available") is not True
                or gt.get("usage") not in ("validation_only", "development", "full")
                or not isinstance(selection, dict) or selection.get("uses_gt") is not True
                or selection.get("protocol") == "omega_val_only"):
            raise ValueError("MRI_TRAINING_GT: 已声明的 MRI profile 与完整 val GT 选模规则冲突")
        if selection.get("uses_loss_measurements") is True:
            raise ValueError("MRI_TRAINING_SELECTION: 禁止使用自监督 mask split 损失或测量残差选模")
    return {
        "policy_sha256": hashlib.sha256(policy.encode("utf-8")).hexdigest(),
        "profile_sha256": hashlib.sha256(json.dumps(
            profile.config, sort_keys=True, ensure_ascii=False
        ).encode("utf-8")).hexdigest() if profile.active else None,
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
