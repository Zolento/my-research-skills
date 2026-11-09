#!/usr/bin/env python3
"""domain_mms.py — Mechanism-to-Method Search (MMS) for the MRI reconstruction profile.

MMS is a *domain discovery policy* for R3–R6, not a new exploration engine. When a
performance bottleneck has stopped paying off in diagnosis, the agent should look for a
mechanism it can still change. MMS provides:

1. **Six exploration directions** (information use, prior/posterior adaptation,
   representation, optimization dynamics, measurement-prior coupling, target-structure
   recovery) as a *menu*, ordered by crowding and failure evidence — never by an
   aggregate score (the repository's no-score discipline applies here too).
2. **A concrete method-candidate contract** (``MM1``–``MM8``): a candidate must name the
   failed mechanism, the mathematical object or optimization rule it changes, a
   falsifiable expected effect under the frozen SSL boundary, an equal-capacity control,
   the nearest prior work with a stated delta, and the anchor it serves.

MMS never launches experiments, never relaxes a gate and never touches canonical state.
Its candidates enter the existing Insight-to-Method pipeline (sketch → candidate →
preference → contract → minimal test) and still need R8's evidence and identifiability
rules before anything is frozen.

CLI::

    python3 scripts/domain_mms.py menu --state <route>/research-state.json
    python3 scripts/domain_mms.py validate --candidate candidate.json --state <state>

Exit codes: 0 valid, 1 usage/selftest failure, 3 invalid candidate, 4 environment.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cognition as cg
import domain_guard as dg
import domain_profile as dp

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_HARD = 3
EXIT_ENV = 4

#: Frozen protocol namespace (references/identity-and-compatibility.md).
CANDIDATE_SCHEMA = "research-idea-pipeline/method-candidate-mms@1"

#: Six exploration directions. Not a task checklist: the current Research State, failure
#: memory and the project anchor decide which space is promising.
DIRECTIONS: Tuple[Tuple[str, str], ...] = (
    ("ssl_information_use", "自监督信息利用机制：监督信息效率、目标偏差、拆分结构对可学习结构的影响"),
    ("prior_posterior_adaptation", "先验与后验适配：来源域先验与目标域测量的失配、条件化修正、分布适配"),
    ("representation_inductive_bias", "表示能力与归纳偏置：CNN/UNet/INR/Fourier/HashGrid 的结构信息与容量"),
    ("optimization_dynamics", "优化动力学：训练优化与最终重建的失配、unrolled/FBS/HQS/ADMM 的可达更新空间"),
    ("measurement_prior_coupling", "测量与先验耦合：哪些观测方向真正约束先验修正、measurement-conditioned correction"),
    ("target_structure_recovery", "目标结构恢复：弱对比度/微小结构与全局指标的权衡、虚假结构控制"),
)

DIRECTION_IDS = tuple(item[0] for item in DIRECTIONS)
DIRECTION_DOCS = dict(DIRECTIONS)

#: Failure-mechanism token → directions that can address it. Failure memory feeds the menu,
#: the mapping is structural (shared tokens with domain_guard.MECHANISMS), not prose.
MECHANISM_TO_DIRECTIONS: Dict[str, Tuple[str, ...]] = {
    "forward_operator_mismatch": ("measurement_prior_coupling", "optimization_dynamics"),
    "coil_sensitivity_error": ("measurement_prior_coupling",),
    "noise_level": ("ssl_information_use", "target_structure_recovery"),
    "snr_limit": ("ssl_information_use", "representation_inductive_bias"),
    "undersampling_information": ("ssl_information_use", "measurement_prior_coupling",
                                  "target_structure_recovery"),
    "conditioning": ("optimization_dynamics", "representation_inductive_bias"),
    "ill_posedness": ("prior_posterior_adaptation", "representation_inductive_bias"),
    "oversmoothing": ("representation_inductive_bias", "target_structure_recovery"),
    "overstrong_prior": ("prior_posterior_adaptation", "measurement_prior_coupling"),
    "data_scarcity": ("ssl_information_use", "prior_posterior_adaptation"),
    "other_declared": DIRECTION_IDS,
}


def _items(state: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    value = state.get(key) if isinstance(state, dict) else None
    return [item for item in (value or []) if isinstance(item, dict)]


def failure_count_for_mechanism(state: Dict[str, Any], mechanism: str) -> int:
    """Independent failure records structurally linked to a mechanism token."""
    if mechanism not in dg.MECHANISMS:
        return 0
    count = 0
    for failure in _items(state, "failures"):
        text = str(failure.get("mechanism") or failure.get("finding") or
                   failure.get("statement") or "").strip().lower()
        if mechanism.replace("_", " ") in text or mechanism in text:
            count += 1
    return count


def physical_limit_for(records: Sequence[Dict[str, Any]], mechanism: str) -> Optional[Dict[str, Any]]:
    """The latest verified physical-limit verdict recorded for a mechanism."""
    latest = None
    for record in records:
        if record.get("mechanism") != mechanism:
            continue
        if record.get("tag_class") == "PHYSICAL_LIMIT_WITH_SCOPE":
            latest = record
    return latest


def methods_dir(route_dir: Any) -> pathlib.Path:
    return pathlib.Path(route_dir).expanduser() / "methods"


def _existing_candidates(route_dir: Any) -> List[Dict[str, Any]]:
    """Method candidates already authored under <route>/methods/ (I2M artifacts)."""
    out: List[Dict[str, Any]] = []
    directory = methods_dir(route_dir)
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("candidate-*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def recommend_directions(state: Dict[str, Any], route_dir: Any) -> Dict[str, Any]:
    """The MMS menu: directions with failure-evidence links and crowding counts.

    Structured counts only — deliberately **no aggregate score**. The order is
    deterministic: directions linked to recorded failures first, then uncrowded ones,
    each group alphabetically.
    """
    failures = _items(state, "failures")
    mechanisms: List[str] = []
    for failure in failures:
        text = str(failure.get("mechanism") or failure.get("finding") or
                   failure.get("statement") or "").strip().lower()
        for token in dg.MECHANISMS:
            if token.replace("_", " ") in text or token in text:
                mechanisms.append(token)
    linked: Dict[str, List[str]] = {item: [] for item in DIRECTION_IDS}
    for token in mechanisms:
        for direction in MECHANISM_TO_DIRECTIONS.get(token, ()):
            linked[direction].append(token)
    existing = _existing_candidates(route_dir)
    crowded: Dict[str, int] = {item: 0 for item in DIRECTION_IDS}
    for candidate in existing:
        direction = str(candidate.get("direction") or "")
        if direction in crowded:
            crowded[direction] += 1
    menu = []
    for direction, description in DIRECTIONS:
        menu.append({"direction": direction, "description": description,
                     "linked_failure_mechanisms": sorted(set(linked[direction])),
                     "existing_candidates": crowded[direction]})
    menu.sort(key=lambda item: (not item["linked_failure_mechanisms"],
                                item["existing_candidates"], item["direction"]))
    return {"menu": menu, "note": ("方向不是任务清单；按当前 Research State、失败记忆与主锚点"
                                   "选择有希望的空间，不允许机械地逐个执行"),
            "existing_candidates": len(existing)}


# ---------------------------------------------------------------------------
# Candidate contract (MM1–MM8)
# ---------------------------------------------------------------------------

def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def candidate_errors(candidate: Any, *, profile_config: Optional[Dict[str, Any]] = None,
                     state: Optional[Dict[str, Any]] = None,
                     tag_records: Sequence[Dict[str, Any]] = ()) -> List[str]:
    """Mechanical rules MM1–MM8 plus the repeat/limit guards (MM3a/MM3b/MM8a).

    ``tag_records`` are the route's TAG events (see ``domain_guard.load_events``); the
    CLI loads them from ``--state``'s route so the same check runs offline.
    """
    problems: List[str] = []
    if not isinstance(candidate, dict):
        return ["候选顶层必须是对象"]
    if candidate.get("_schema") != CANDIDATE_SCHEMA:
        problems.append("MM1: _schema 必须是 " + CANDIDATE_SCHEMA)

    direction = _text(candidate.get("direction"))
    if direction not in DIRECTION_IDS:
        problems.append(f"MM2: direction 必须是六个方向之一：{DIRECTION_IDS}")

    mechanism = _text(candidate.get("target_failure_mechanism"))
    if mechanism not in dg.MECHANISMS:
        problems.append("MM3: target_failure_mechanism 必须是受控机制枚举之一"
                        f"（{dg.MECHANISMS}）；新机制先登记 other_declared")
    if mechanism == "other_declared" and not _text(candidate.get("mechanism_evidence")):
        problems.append("MM3: other_declared 机制必须附 mechanism_evidence（R7/R10 确认依据）")
    # MM3a — repeated failures on one mechanism need a scope change, not a rename.
    if state is not None and mechanism:
        count = failure_count_for_mechanism(state, mechanism)
        if count >= 2 and not _text(candidate.get("scope_change_justification")):
            problems.append(
                f"MM3a: 机制 {mechanism} 已有 {count} 条独立失败记录；换名重试被拒绝——"
                "候选必须声明 scope_change_justification（新作用域/新机制假设）")
    # MM3b — a verified physical limit bounds what may be claimed, not what may be tried.
    limit = physical_limit_for(tag_records, mechanism) if mechanism else None
    if limit is not None and not _text(candidate.get("scope_justification")):
        problems.append(
            f"MM3b: 机制 {mechanism} 存在已验证的物理限制（适用范围："
            f"{limit.get('scope') or '未记录'}）；候选必须声明 scope_justification，"
            "证明目标在该范围之外，不得在已验证不可恢复范围内虚构改进")

    math_change = candidate.get("mathematical_change")
    if not isinstance(math_change, dict):
        problems.append("MM4: 缺少 mathematical_change（必须说明改变了哪个数学对象/优化规则）")
    else:
        if not _text(math_change.get("changes_object")):
            problems.append("MM4: mathematical_change.changes_object 缺失：改变了哪个对象？")
        if not _text(math_change.get("changed_rule")):
            problems.append("MM4: mathematical_change.changed_rule 缺失：改变了哪条规则？")

    effect = candidate.get("expected_effect")
    if not isinstance(effect, dict):
        problems.append("MM5: 缺少 expected_effect（可证伪预测）")
    else:
        if not _text(effect.get("prediction")):
            problems.append("MM5: expected_effect.prediction 缺失")
        if not _text(effect.get("criterion")):
            problems.append("MM5: expected_effect.criterion 缺失：判定预测成立/失败的冻结判据")
        if not _text(effect.get("falsification_test")):
            problems.append("MM5: expected_effect.falsification_test 缺失：什么实验会否定该机制？")

    controls = candidate.get("control_condition")
    if not isinstance(controls, dict):
        problems.append("MM6: 缺少 control_condition（等容量/等预算对照）")
    else:
        if controls.get("capacity_matched") is not True:
            problems.append("MM6: control_condition.capacity_matched 必须为 true"
                            "（只扩大容量的改进不得写成机制创新）")
        if not _text(controls.get("description")):
            problems.append("MM6: control_condition.description 缺失：对照怎么构造？")

    prior = candidate.get("nearest_prior_work")
    if not isinstance(prior, dict) or not _text(prior.get("reference")):
        problems.append("MM7: 缺少 nearest_prior_work.reference（最接近的已有工作）")
    elif not _text(prior.get("delta")):
        problems.append("MM7: nearest_prior_work.delta 缺失：与最接近工作的实质差异是什么？")

    boundary = candidate.get("ssl_boundary_compliance")
    gt_free = isinstance(profile_config, dict) and \
        isinstance(profile_config.get("gt"), dict) and \
        profile_config["gt"].get("available") is False
    if gt_free:
        if not isinstance(boundary, dict) or not _text(boundary.get("statement")):
            problems.append("MM8: 严格 GT-free 项目必须声明 ssl_boundary_compliance.statement"
                            "（预期改善如何落在冻结的自监督信息边界内）")
        if isinstance(boundary, dict) and boundary.get("uses_gt_for_selection") is True:
            problems.append("MM8: ssl_boundary_compliance.uses_gt_for_selection 不得为 true")

    anchor = _text(candidate.get("anchor_alignment"))
    contract = state.get("contract") if isinstance(state, dict) and         isinstance(state.get("contract"), dict) else {}
    anchor_name = _text(contract.get("primary_anchor"))
    if not anchor:
        problems.append("MM8: 缺少 anchor_alignment：候选服务于哪个主锚点/研究决定？")
    elif anchor_name and anchor_name.lower() not in anchor.lower():
        # A challenging candidate is allowed to argue the anchor itself — but only
        # explicitly, and the decision stays with the user (RLP §0.2).
        if candidate.get("anchor_change_requested") is True:
            if not _text(candidate.get("anchor_change_justification")):
                problems.append(
                    "MM8a: anchor_change_requested=true 必须附 "
                    "anchor_change_justification（证据 + 为什么现有锚点不再成立）；"
                    "改主锚点仍由用户授权（C 类），候选只是 challenging 证据")
        else:
            problems.append(f"MM8: anchor_alignment 未引用项目主锚点（{anchor_name!r}）；"
                            "若候选意在挑战锚点，请显式声明 anchor_change_requested=true")

    return problems


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _selftest() -> int:
    import tempfile
    failures: List[str] = []

    def expect(name: str, condition: bool, detail: str = "") -> None:
        print(f"  {'ok  ' if condition else 'FAIL'} {name}"
              + (f" —— {detail}" if detail and not condition else ""))
        if not condition:
            failures.append(name)

    config = {
        "_schema": dp.PROFILE_SCHEMA, "profile": "mri-reconstruction",
        "acquisition": {"forward_operators": ["fourier"], "coils": 2,
                        "undersampling": {"pattern": "vd"}, "noise": {"model": "gaussian"}},
        "gt": {"available": False, "usage": "none"},
        "ssl": {"type": "ssdu", "split": {"input": "theta", "loss": "lambda",
                                          "held_out_validation": "omega_val"},
                "acs": {"usage": "frozen"}},
        "model_selection": {"protocol": "omega_val", "uses_gt": False},
        "frozen": {"components": ["backbone"], "forbidden_changes": []},
        "metrics": {"primary": {"name": "nmse", "threshold": 0.02,
                                "frozen_before_results": True,
                                "frozen_at_state_version": 1}},
        "resources": {"gpu_hours_budget": 1},
    }
    expect("profile 配置合法（供 MM 用）", not dp.validate(config, state={"state_version": 2}))

    good = {
        "_schema": CANDIDATE_SCHEMA, "direction": "prior_posterior_adaptation",
        "target_failure_mechanism": "overstrong_prior",
        "mathematical_change": {"changes_object": "先验加权 w(y_Θ)",
                                "changed_rule": "FBS 中的近端步由固定先验改为测量条件化加权"},
        "expected_effect": {"prediction": "弱对比度结构恢复提升而全局 NMSE 不劣化",
                            "criterion": "vessel_mip_connectivity 改善 ≥0.05 且 NMSE Δ≤0.02",
                            "falsification_test": "X15 等容量对照上无差异则否定"},
        "control_condition": {"capacity_matched": True, "description": "同参数量 adapter"},
        "nearest_prior_work": {"reference": "CT-FM prior (2026)", "delta": "测量条件化加权"},
        "ssl_boundary_compliance": {"statement": "只用 Θ 输入与 Λ 损失",
                                    "uses_gt_for_selection": False},
        "anchor_alignment": "microvascular structure recovery (primary_anchor)",
        "mechanism_evidence": "",
    }
    state = {"state_version": 2, "contract": {"primary_anchor": "structure recovery"}}
    expect("完整候选通过", not candidate_errors(good, profile_config=config, state=state),
           str(candidate_errors(good, profile_config=config, state=state)))
    bad = json.loads(json.dumps(good))
    bad["direction"] = "融合注意力"
    bad["target_failure_mechanism"] = "自由文本机制"
    bad["control_condition"]["capacity_matched"] = False
    bad["nearest_prior_work"]["delta"] = ""
    bad["ssl_boundary_compliance"]["uses_gt_for_selection"] = True
    found = candidate_errors(bad, profile_config=config, state=state)
    rules = {item.split(":")[0] for item in found}
    expect("方向越权被拒", "MM2" in rules, str(found))
    expect("机制枚举外被拒", "MM3" in rules)
    expect("无等容量对照被拒", "MM6" in rules)
    expect("无实质差异被拒", "MM7" in rules)
    expect("GT-free 却用 GT 选择被拒", "MM8" in rules)
    noanchor = json.loads(json.dumps(good))
    noanchor["anchor_alignment"] = "与主锚点无关的表述"
    found2 = candidate_errors(noanchor, profile_config=config, state=state)
    expect("锚点不一致被拒", any(item.startswith("MM8") for item in found2), str(found2))
    gt_full_config = json.loads(json.dumps(config))
    gt_full_config["gt"] = {"available": True, "usage": "development"}
    no_boundary = json.loads(json.dumps(good))
    del no_boundary["ssl_boundary_compliance"]
    expect("GT 可用时边界声明可选",
           not any(item.startswith("MM8") and "ssl_boundary" in item
                   for item in candidate_errors(no_boundary, profile_config=gt_full_config)))

    with tempfile.TemporaryDirectory() as temp:
        route = pathlib.Path(temp)
        state2 = {"state_version": 3,
                  "failures": [{"id": "F1", "kind": "unsupported",
                                "finding": "conditioning 不佳导致弱结构被压制的假设不成立"},
                               {"id": "F2", "kind": "engineering-failure",
                                "finding": "OOM"}]}
        menu = recommend_directions(state2, route)
        top = menu["menu"][0]
        expect("失败机制链接到方向", "conditioning" in top["linked_failure_mechanisms"],
               json.dumps(menu["menu"][:2], ensure_ascii=False))
        expect("无聚合分字段", not any("score" in item for item in menu["menu"][0]))
        (route / "methods").mkdir()
        candidate = dict(good)
        candidate["direction"] = "prior_posterior_adaptation"
        (route / "methods" / "candidate-c1.json").write_text(
            json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
        menu2 = recommend_directions(state2, route)
        crowded = {item["direction"]: item["existing_candidates"] for item in menu2["menu"]}
        expect("已有候选计入拥挤度", crowded["prior_posterior_adaptation"] == 1, str(crowded))

    if failures:
        print(f"[FAIL] {len(failures)} selftest failures")
        return EXIT_ERROR
    print("[ok] domain_mms selftest")
    return EXIT_OK


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Mechanism-to-Method Search (MMS)")
    parser.add_argument("--selftest", action="store_true")
    sub = parser.add_subparsers(dest="command")
    menu_p = sub.add_parser("menu", help="recommend exploration directions (advisory)")
    menu_p.add_argument("--state", required=True)
    validate_p = sub.add_parser("validate", help="validate a method candidate (MM1–MM8)")
    validate_p.add_argument("--candidate", required=True)
    validate_p.add_argument("--state", required=True)
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    if args.command == "menu":
        state_path = pathlib.Path(args.state)
        if not state_path.is_file():
            print(f"[env] state 文件不存在：{state_path}", file=sys.stderr)
            return EXIT_ENV
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            print(f"[env] state 不可读：{exc}", file=sys.stderr)
            return EXIT_ENV
        if not isinstance(state, dict):
            print("[env] state 顶层必须是对象", file=sys.stderr)
            return EXIT_ENV
        print(json.dumps(recommend_directions(state, state_path.parent),
                         ensure_ascii=False, indent=2))
        return EXIT_OK
    if args.command == "validate":
        try:
            candidate = json.loads(pathlib.Path(args.candidate).read_text(encoding="utf-8"))
            state = json.loads(pathlib.Path(args.state).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"[env] 输入不可读：{exc}", file=sys.stderr)
            return EXIT_ENV
        _, profile = dp.active_profile(args.state)
        try:
            records, _ = dg.load_events(pathlib.Path(args.state).parent)
        except Exception:
            records = []
        problems = candidate_errors(candidate, profile_config=profile.config,
                                    state=state if isinstance(state, dict) else None,
                                    tag_records=records)
        if problems:
            for item in problems:
                print(f"[FAIL] {item}", file=sys.stderr)
            return EXIT_HARD
        print("[ok] 候选满足 MM1—MM8（进入 I2M 仍需既有证据与可识别性规则）")
        return EXIT_OK
    parser.error("需要子命令或 --selftest")
    return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
