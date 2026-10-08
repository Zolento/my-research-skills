#!/usr/bin/env python3
"""strategy_memory.py — scientific value, taste memory and adaptive discovery.

The problem this module addresses is not "the agent cannot score ideas". It is that the
current ordering drifts toward short-term EIG, recordable state changes and cheap
diagnostics. Three things are therefore built here and nothing else:

1. **A value model that is per-dimension, with sources, and has no total.**
   Decision value and discovery potential are separate judgments; every indicator cites
   canonical evidence; there is deliberately no composite score to maximize
   ([scoring-policy.md](../references/scoring-policy.md) already refuses a third numeric
   system, and a single `insight_score` would be exactly that).
2. **A taste memory split into what the human owns and what evidence calibrated.**
   Human-specified preferences come from `contract` and are read-only. Evidence-calibrated
   preferences are inferred from outcomes and may change — but they may never overwrite the
   anchor, and a few failures may never condemn a whole mechanism class.
3. **An adaptive discovery strategy that reuses `P1`—`P6`, the QD archive and the existing
   scheduler ordering.** No new Exploration Agent, no new budget rule, and never a permanent
   ban on an operator.

Rule namespace `SV1`—`SV9`; `S`/`V`/`CM`/`PC`/`LH` keep their own identities.

Usage
-----
    python3 strategy_memory.py value      --state S --target H1
    python3 strategy_memory.py taste      --state S [--scheduler S.json] [--cognition DIR]
    python3 strategy_memory.py operators  --state S [--scheduler S.json] [--cognition DIR]
    python3 strategy_memory.py recommend  --state S [--scheduler S.json] [--cognition DIR]
    python3 strategy_memory.py apply      --state S [--scheduler S.json] [--cognition DIR]
    python3 strategy_memory.py validate   --state S [--cognition DIR]
    python3 strategy_memory.py --selftest

Exit codes: 0 pass, 1 argument error, 3 hard violation, 4 environment not satisfied.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cognition as cg
import state_check as sc

Diagnostic = cg.Diagnostic

EXIT_OK = cg.EXIT_OK
EXIT_ERROR = cg.EXIT_ERROR
EXIT_HARD = cg.EXIT_HARD
EXIT_ENV = cg.EXIT_ENV

# ---------------------------------------------------------------------------
# Frozen vocabularies
# ---------------------------------------------------------------------------

VALUE_DIMENSIONS: Tuple[str, ...] = (
    "changes_method_choice",
    "changes_experiment_design",
    "changes_resource_allocation",
    "changes_route",
    "changes_important_conclusion",
)

POTENTIAL_DIMENSIONS: Tuple[str, ...] = (
    "reveals_new_structure",
    "overturns_important_assumption",
    "builds_cross_domain_link",
    "raises_new_question",
)

#: Per-dimension assessment. There is no numeric rung and no aggregation.
ASSESSMENTS: Tuple[str, ...] = ("yes", "likely", "unclear", "no")

CONSIDERATIONS: Tuple[str, ...] = (
    "contract_relation", "extrapolation_range", "nearest_prior_delta",
    "falsification_difficulty", "identification_difficulty", "experiment_cost",
    "evidence_strength", "long_term_value",
)

OPERATOR_STATUSES: Tuple[str, ...] = ("encouraged", "neutral", "discouraged", "dormant")

#: Keys that would turn the per-dimension judgment back into a single number.
BANNED_AGGREGATE_KEYS: Tuple[str, ...] = (
    "score", "total", "overall", "composite", "weighted", "aggregate", "rating",
)

#: The eight discovery strategies, mapped onto operators that already exist. No new
#: operator and no new agent is introduced.
STRATEGY_MENUS: Tuple[Dict[str, str], ...] = (
    {"menu": "invert_hidden_assumption", "operator": "assumption_breaker", "island": "P2",
     "shift": "assumption-shift"},
    {"menu": "replace_problem_representation", "operator": "reframe", "island": "P1",
     "shift": "representation-shift"},
    {"menu": "change_research_scale", "operator": "theory_lens", "island": "P5",
     "shift": "theory-shift"},
    {"menu": "cross_domain_isomorphism", "operator": "remote_analogy", "island": "P4",
     "shift": "mechanism-shift"},
    {"menu": "construct_counterexample", "operator": "counterexample", "island": "P6",
     "shift": "boundary-shift"},
    {"menu": "redefine_from_objective_or_metric", "operator": "reframe", "island": "P1",
     "shift": "evaluation-shift"},
    {"menu": "probe_structure_by_minimal_intervention", "operator": "local", "island": "local",
     "shift": "mechanism-shift"},
    {"menu": "abandon_attribution_direction", "operator": "local", "island": "local",
     "shift": "boundary-shift"},
)

#: Menu table integrity: every menu must reuse a frozen operator and a frozen island.
#: Checked at import time so a typo cannot silently make every operator look neutral.
for _entry in STRATEGY_MENUS:
    assert _entry["operator"] in sc.OPERATORS, _entry
    assert _entry["island"] in sc.ISLANDS, _entry

MENU_BY_NAME = {entry["menu"]: entry for entry in STRATEGY_MENUS}

#: A discouraged operator needs at least this many independent failures in the same
#: problem structure before it is deprioritised. One failure is not a class result.
MIN_INDEPENDENT_FAILURES = 2

#: Consecutive strategy updates on the same menu that force a different one.
STAGNANT_MENU_RUN = 2


# ---------------------------------------------------------------------------
# Human-specified versus evidence-calibrated preferences
# ---------------------------------------------------------------------------

def human_preferences(state: Dict[str, Any]) -> Dict[str, Any]:
    """The part of taste memory the agent may not modify.

    It is read straight from `contract` and the route anchor. Strategy learning only ever
    *reads* it, and `SV3` rejects any attempt to write it back.
    """
    contract = state.get("contract") if isinstance(state.get("contract"), dict) else {}
    return {
        "goal": contract.get("goal"),
        "primary_anchor": contract.get("primary_anchor"),
        "constraints": list(contract.get("constraints") or []),
        "resources": list(contract.get("resources") or []),
        "out_of_scope": list(contract.get("out_of_scope") or []),
        "provisional_anchor_rationale": contract.get("provisional_anchor_rationale"),
        "authority": "user",
        "mutable_by_agent": False,
    }


def _records(scheduler: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(scheduler, dict):
        return []
    calibration = scheduler.get("eig_calibration")
    records = calibration.get("records") if isinstance(calibration, dict) else None
    return [record for record in records or [] if isinstance(record, dict)]


def _operator_stats(scheduler: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(scheduler, dict):
        return {}
    stats = scheduler.get("operator_stats")
    return stats if isinstance(stats, dict) else {}


def _hypothesis_table(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {entry.get("id"): entry for entry in state.get("hypotheses", []) or []
            if isinstance(entry, dict) and isinstance(entry.get("id"), str)}


# ---------------------------------------------------------------------------
# 3.1 Scientific value model
# ---------------------------------------------------------------------------

def _indicator(assessment: str, basis: List[str], uncertainty: str, note: str) -> Dict[str, Any]:
    return {"assessment": assessment, "basis": basis, "uncertainty": uncertainty, "note": note}


def target_refs(state: Dict[str, Any], index: Dict[str, Any], target: str) -> Dict[str, Any]:
    """Everything the value model is allowed to look at, already resolved."""
    view = cg.CanonicalView(state)
    hypothesis = view.get("hypotheses", target)
    claim = view.get("claims", target)
    return {
        "hypothesis": hypothesis,
        "claim": claim,
        "experiments": [experiment for experiment in state.get("experiments", []) or []
                        if isinstance(experiment, dict)
                        and target in (experiment.get("claim_targeted") or [])],
        "uncertainties": [uncertainty for uncertainty in state.get("uncertainties", []) or []
                          if isinstance(uncertainty, dict)
                          and uncertainty.get("importance") in ("critical", "high")
                          and uncertainty.get("status") == "open"],
        "competitions": [competition for competition in index.get("competitions", [])
                         if target in (competition.get("canonical_refs", {}).get("claims") or [])
                         or target in (competition.get("canonical_refs", {}).get("hypotheses") or [])],
        "repairs": [repair for repair in state.get("repairs", []) or []
                    if isinstance(repair, dict)
                    and target in (repair.get("targets") or [])],
        "assurance": [attack for attack in state.get("assurance", []) or []
                      if isinstance(attack, dict) and attack.get("target") == target],
    }


def value_assessment(state: Dict[str, Any], index: Dict[str, Any], target: str,
                     scheduler: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Per-dimension value for one research candidate. Never a single number."""
    view = cg.CanonicalView(state)
    if not view.contains("hypotheses", target) and not view.contains("claims", target):
        raise cg.CognitionError(f"target is neither a hypothesis nor a claim: {target}")
    refs = target_refs(state, index, target)
    contract = state.get("contract") if isinstance(state.get("contract"), dict) else {}
    basis_all: List[str] = [f"{'hypotheses' if refs['hypothesis'] else 'claims'}:{target}"]

    planned = [experiment.get("id") for experiment in refs["experiments"]
               if experiment.get("status") in ("planned", "running")]
    alternatives = sorted({alternative for experiment in refs["experiments"]
                           for alternative in experiment.get("alternative_targeted") or []})
    if planned:
        basis_all.extend(f"experiments:{ident}" for ident in planned)
    if refs["uncertainties"]:
        basis_all.extend(f"uncertainties:{item.get('id')}" for item in refs["uncertainties"])
    if refs["competitions"]:
        basis_all.extend(f"competitions:{item.get('id')}" for item in refs["competitions"])

    decision_value = {
        "changes_method_choice": _indicator(
            "yes" if refs["competitions"] and alternatives else "unclear",
            [f"competitions:{item.get('id')}" for item in refs["competitions"]] or basis_all[:1],
            "medium",
            "只有在竞争存在、且候选带有指名替代解释时才改变方法选择"),
        "changes_experiment_design": _indicator(
            "yes" if planned else "no",
            [f"experiments:{ident}" for ident in planned] or basis_all[:1],
            "low",
            "是否已经有 planned / running 实验围绕它设计"),
        "changes_resource_allocation": _indicator(
            "yes" if refs["uncertainties"] else "unclear",
            [f"uncertainties:{item.get('id')}" for item in refs["uncertainties"]] or basis_all[:1],
            "medium",
            "是否被 open 且 importance ∈ {critical, high} 的未知量引用"),
        "changes_route": _indicator(
            "yes" if any(repair.get("disposition") in ("NARROW_SCOPE", "KILL_BRANCH")
                         for repair in refs["repairs"]) else "no",
            [f"repairs:{repair.get('flaw', '')[:40]}" for repair in refs["repairs"]] or basis_all[:1],
            "medium",
            "是否已经被 R10 的收窄或封支处置覆盖"),
        "changes_important_conclusion": _indicator(
            "yes" if (refs["claim"] or {}).get("status") in ("supported", "contradicted") else "unclear",
            [f"claims:{refs['claim'].get('id')}"] if refs["claim"] else basis_all[:1],
            "medium",
            "claim 已经达到 supported / contradicted 时才直接影响重要结论"),
    }

    operator = (refs["hypothesis"] or {}).get("operator")
    niche = (refs["hypothesis"] or {}).get("niche")
    prior = (refs["hypothesis"] or {}).get("nearest_prior")
    structural = (refs["hypothesis"] or {}).get("structural_signature") or {}
    distances = [value for value in structural.values() if isinstance(value, int)]
    discovery_potential = {
        "reveals_new_structure": _indicator(
            "likely" if distances and max(distances) >= 2 else "unclear",
            [f"hypotheses:{target}"] if distances else basis_all[:1],
            "high",
            "结构签名里最大的维度距离 ≥ 2 才记为 likely；这是描述符，不是质量分"),
        "overturns_important_assumption": _indicator(
            "likely" if niche == "assumption-shift" else "unclear",
            [f"hypotheses:{target}"] if niche else basis_all[:1],
            "high",
            "只有 assumption-shift 轴上的候选才声称推翻隐含假设"),
        "builds_cross_domain_link": _indicator(
            "likely" if operator == "remote_analogy" else "no",
            (["hypotheses:%s" % target] if operator else basis_all[:1]),
            "high",
            "跨域类比只有在给出结构对应（P3 骨架 + 四维对应）后才有意义"),
        "raises_new_question": _indicator(
            "yes" if refs["uncertainties"] and (refs["hypothesis"] or {}).get("status") == "elite"
            else "unclear",
            [f"uncertainties:{item.get('id')}" for item in refs["uncertainties"]] or basis_all[:1],
            "high",
            "是否已经产生新的未决问题"),
    }

    evidence_ids = list((refs["claim"] or {}).get("supporting_evidence") or []) + \
        list((refs["claim"] or {}).get("refuting_evidence") or [])
    tiers = [view.get("evidence", ident).get("verification_tier") for ident in evidence_ids
             if isinstance(view.get("evidence", ident), dict)]
    best_tier = max((cg.TIER_ORDER.get(tier, 0) for tier in tiers), default=0)
    costs = [action.get("cost") for action in (scheduler or {}).get("next_actions", []) or []
             if isinstance(action, dict) and action.get("target") in (target, refs["claim"] or {}.get("id"))]
    considerations = {
        "contract_relation": _indicator(
            "yes" if contract.get("primary_anchor") else "unclear",
            ["contract:primary_anchor"], "low",
            f"锚点 {contract.get('primary_anchor')!r} 由用户指定；价值判断必须相对它给出"),
        "extrapolation_range": (refs["hypothesis"] or {}).get("scientific_scope")
        or (refs["claim"] or {}).get("scope") or "unknown",
        "nearest_prior_delta": prior or "unknown",
        "falsification_difficulty": "declared" if (refs["hypothesis"] or {}).get("falsifier")
        or (refs["claim"] or {}).get("falsifier") else "unknown",
        "identification_difficulty": "unresolved" if refs["competitions"] else "not_declared",
        "experiment_cost": costs[0] if costs else "unknown",
        "evidence_strength": f"T{best_tier}" if best_tier else "T0",
        "long_term_value": "unassessable_from_state"
                        if not distances else "structural_distance_recorded",
    }

    objections: List[str] = []
    if refs["claim"] and (refs["claim"].get("nearest_alternative") or "").strip():
        objections.append("最近替代解释：" + refs["claim"]["nearest_alternative"])
    for attack in refs["assurance"]:
        objections.append("R7 攻击面 " + str(attack.get("attack_type")) + "："
                          + str(attack.get("kill_condition", ""))[:80])
    if refs["competitions"]:
        objections.append("该候选参与 " + ", ".join(str(c.get("id")) for c in refs["competitions"])
                          + "；判别力见 prediction_compare.py compete")
    if not objections:
        objections.append("尚未登记反对意见：这本身是缺口，不是价值证据")

    return {
        "target": target,
        "kind": "hypothesis" if refs["hypothesis"] else "claim",
        "decision_value": decision_value,
        "discovery_potential": discovery_potential,
        "considerations": considerations,
        "objections": objections,
        "basis": sorted(set(basis_all)),
        "no_composite_reason": ("Decision value 与 Discovery potential 互相独立："
                                "高决策价值不等于高发现潜力，合成为一个数会重新引入"
                                "「自评分驱动排序」这一被禁止的机制"),
    }


def validate_value(assessment: Any, path: str = "value") -> List[Diagnostic]:
    """Reject a single aggregate and require a source on every dimension."""
    if not isinstance(assessment, dict):
        return [Diagnostic("SV1", path, "价值判断必须是对象")]
    diagnostics: List[Diagnostic] = []
    for key in BANNED_AGGREGATE_KEYS:
        if key in assessment:
            diagnostics.append(Diagnostic(
                "SV1", f"{path}.{key}",
                "禁止把价值判断合成为单一分数；Decision Value 与 Discovery Potential 必须分开"))
    for group, dimensions in (("decision_value", VALUE_DIMENSIONS),
                              ("discovery_potential", POTENTIAL_DIMENSIONS)):
        block = assessment.get(group)
        if not isinstance(block, dict):
            diagnostics.append(Diagnostic("SV2", f"{path}.{group}", "缺少该组判断"))
            continue
        for dimension in dimensions:
            entry = block.get(dimension)
            if not isinstance(entry, dict):
                diagnostics.append(Diagnostic("SV2", f"{path}.{group}.{dimension}",
                                              "缺少该维度"))
                continue
            if entry.get("assessment") not in ASSESSMENTS:
                diagnostics.append(Diagnostic(
                    "SV2", f"{path}.{group}.{dimension}.assessment",
                    f"assessment 必须是 {list(ASSESSMENTS)} 之一"))
            basis = entry.get("basis")
            if not isinstance(basis, list) or not basis:
                diagnostics.append(Diagnostic(
                    "SV2", f"{path}.{group}.{dimension}.basis",
                    "每个维度必须给出 canonical 依据；没有依据的判断等于自评"))
            if not isinstance(entry.get("uncertainty"), str) or not entry["uncertainty"].strip():
                diagnostics.append(Diagnostic(
                    "SV2", f"{path}.{group}.{dimension}.uncertainty", "缺少不确定性"))
    for key in CONSIDERATIONS:
        if key not in (assessment.get("considerations") or {}):
            diagnostics.append(Diagnostic("SV2", f"{path}.considerations.{key}",
                                          "缺少该项考虑"))
    return diagnostics


# ---------------------------------------------------------------------------
# 3.2 Taste memory
# ---------------------------------------------------------------------------

def calibrated_preferences(
    state: Dict[str, Any],
    index: Dict[str, Any],
    scheduler: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """What the outcomes taught the system. Derived, revisable, never an anchor change."""
    hypotheses = _hypothesis_table(state)
    by_operator = (_operator_stats(scheduler).get("by_operator") or {})
    records = _records(scheduler)
    view = cg.CanonicalView(state)

    failed_mechanisms = [mechanism["id"] for mechanism in index.get("mechanisms", [])
                         if mechanism.get("status") in ("refuted", "weakened")]
    empty_diagnostics = [record.get("experiment") for record in records
                         if record.get("actual_information_gain") in ("zero", "low")]
    productive = [record.get("experiment") for record in records
                  if record.get("actual_information_gain") == "high"
                  and (record.get("observed_delta") or {}).get("claim_status_changes")]
    analogies_without_prediction = [
        ident for ident, hypothesis in sorted(hypotheses.items())
        if hypothesis.get("island") == "P4"
        and not any(mechanism.get("canonical_refs", {}).get("hypotheses") == [ident]
                    and mechanism.get("structure", {}).get("pending_predictions")
                    for mechanism in index.get("mechanisms", []))
    ]
    equivalent = sorted({mechanism["fingerprint"] for mechanism in index.get("mechanisms", [])}
                        - {None}) if False else []
    fingerprints: Dict[str, List[str]] = {}
    for mechanism in index.get("mechanisms", []):
        fingerprints.setdefault(mechanism.get("fingerprint", ""), []).append(mechanism["id"])
    structurally_equivalent = [ids for ids in fingerprints.values() if len(ids) > 1]

    preferences: List[Dict[str, Any]] = []

    def add(ident: str, statement: str, basis: List[str], confidence: str,
            scope: str, counterexamples: List[str], revisit: str) -> None:
        preferences.append({
            "id": ident, "statement": statement, "basis": sorted(set(basis)),
            "confidence": confidence, "scope": scope,
            "counterexamples": counterexamples, "revisit_conditions": revisit,
            "kind": "evidence_calibrated",
        })

    if empty_diagnostics:
        add("TP-DIAG", "无法改变候选、干预或资源决策的诊断反复出现，历史信息增益为零或低",
            [f"experiments:{ident}" for ident in empty_diagnostics if ident],
            "medium", "同一 claim line 与同一证据快照",
            [], "出现新的判别证据或 regime 改变")
    if productive:
        add("TP-INTERV", "直接改变 claim 状态或关闭未知量的干预才真正推进研究",
            [f"experiments:{ident}" for ident in productive if ident],
            "medium", "本项目已完成的实验", [], "出现反例时重估")
    if failed_mechanisms:
        add("TP-MECH", "被否证或被削弱的机制不得原样重提；只能在其边界之外重开",
            [f"mechanisms:{ident}" for ident in failed_mechanisms],
            "high", "这些机制已记录的适用范围之外",
            [], "出现 ≥ T2 的相反独立证据")
    if analogies_without_prediction:
        add("TP-ANALOGY", "跨域类比在没有给出结构对应与可检验预测前只是表面相似",
            [f"hypotheses:{ident}" for ident in analogies_without_prediction],
            "low", "P4 岛且未登记 pending_predictions 的候选",
            [], "该类比给出四维结构对应与判别预测时失效")
    if structurally_equivalent:
        add("TP-EQUIV", "canonical 锚点集合相同的候选是重述，不是新候选",
            [f"mechanisms:{ident}" for ids in structurally_equivalent for ident in ids],
            "high", "同一路线内", [], "新增独立预测或改变锚点集合时失效")
    dormant = sorted(name for name, stats in by_operator.items()
                     if isinstance(stats, dict) and stats.get("dormant"))
    if dormant:
        add("TP-DORMANT", "算子全灭只说明本轮无产出，不构成永久淘汰",
            [f"operator:{name}" for name in dormant],
            "high", "该算子在本轮问题结构下的表现",
            [], "问题结构改变或出现新 niche 时重试")

    return {
        "human_specified": human_preferences(state),
        "evidence_calibrated": sorted(preferences, key=lambda item: item["id"]),
        "carried_experience": {
            "failed_mechanisms": failed_mechanisms,
            "empty_diagnostics": [ident for ident in empty_diagnostics if ident],
            "productive_interventions": [ident for ident in productive if ident],
            "analogies_without_prediction": analogies_without_prediction,
            "structurally_equivalent_candidates": structurally_equivalent,
            "dormant_operators": dormant,
        },
        "anchor_untouched": True,
        "evidence_strength_hint": f"T{max((cg.TIER_ORDER.get((view.get('evidence', e) or {}).get('verification_tier', 'T0'), 0) for e in view.by_key.get('evidence', {})), default=0)}",
    }


# ---------------------------------------------------------------------------
# 3.3 Adaptive discovery strategy
# ---------------------------------------------------------------------------

def operator_priors(
    state: Dict[str, Any],
    index: Dict[str, Any],
    scheduler: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Per-operator history, scoped to the problem structure where it was measured.

    Nothing here may become a permanent ban. `dormant` and `discouraged` both carry
    reactivation conditions, and the exploration floor keeps at least one long-shot
    operator admissible.
    """
    statistics = _operator_stats(scheduler).get("by_operator") or {}
    hypotheses = _hypothesis_table(state)
    failures_by_operator: Dict[str, List[str]] = {}
    successes_by_operator: Dict[str, List[str]] = {}
    niches_by_operator: Dict[str, List[str]] = {}
    view = cg.CanonicalView(state)
    for ident, hypothesis in sorted(hypotheses.items()):
        operator = hypothesis.get("operator")
        if not isinstance(operator, str):
            continue
        niche = hypothesis.get("niche")
        if isinstance(niche, str):
            niches_by_operator.setdefault(operator, []).append(niche)
        status = hypothesis.get("status")
        if status in ("killed", "archived"):
            failures_by_operator.setdefault(operator, []).append(ident)
        elif status in ("active", "elite"):
            succeeded = any(
                mechanism.get("status") not in ("refuted",)
                and ident in (mechanism.get("canonical_refs", {}).get("hypotheses") or [])
                and mechanism.get("support_level") in ("experiment_supported", "literature_supported")
                for mechanism in index.get("mechanisms", []))
            if succeeded:
                successes_by_operator.setdefault(operator, []).append(ident)

    names = sorted(set(sc.OPERATORS) | set(statistics)
                   | set(failures_by_operator) | set(successes_by_operator))
    by_operator: Dict[str, Any] = {}
    for operator in names:
        stats = statistics.get(operator) if isinstance(statistics.get(operator), dict) else {}
        failures = sorted(failures_by_operator.get(operator, []))
        successes = sorted(successes_by_operator.get(operator, []))
        dormant = bool(stats.get("dormant"))
        if dormant:
            status = "dormant"
        elif len(failures) >= MIN_INDEPENDENT_FAILURES and not successes:
            status = "discouraged"
        elif successes and len(successes) >= len(failures):
            status = "encouraged"
        else:
            status = "neutral"
        by_operator[operator] = {
            "status": status,
            "failures": failures,
            "successes": successes,
            "generations": stats.get("generations"),
            "viable": stats.get("viable"),
            "killed": stats.get("killed"),
            "telemetry_dormant": dormant,
            "scope": sorted(set(niches_by_operator.get(operator, []))) or ["unscoped"],
            "reactivation_conditions": [
                "问题结构改变（出现新的 niche 或新的未知量）",
                "出现 ≥ T2 证据支持该算子在该结构下的产物",
                "上一次失败被归因为实现或测量问题而非算子无效",
            ] if status in ("discouraged", "dormant") else [],
            "source": "scheduler.json operator_stats + hypotheses[]",
        }

    discouraged = sorted(name for name, entry in by_operator.items()
                         if entry["status"] in ("discouraged", "dormant"))
    encouraged = sorted(name for name, entry in by_operator.items()
                        if entry["status"] == "encouraged")
    floor = [{"operator": name, "reason": "保留探索下限：历史失败不构成永久封禁"}
             for name in discouraged] or [
        {"operator": "P6", "reason": "保留探索下限：没有历史失败记录时也要留高潜力探索"}]
    return {
        "by_operator": by_operator,
        "encouraged": encouraged,
        "discouraged": discouraged,
        "exploration_floor": floor,
        "min_independent_failures": MIN_INDEPENDENT_FAILURES,
        "recurring_failure_patterns": list(
            _operator_stats(scheduler).get("recurring_failure_patterns") or []),
        "note": ("状态只在测到它的问题结构下有效；`dormant` / `discouraged` 均附带重启条件，"
                 "任何算子都不得被永久停用（scheduler-policy §4.1）"),
    }


def validate_priors(priors: Any, path: str = "operators") -> List[Diagnostic]:
    diagnostics: List[Diagnostic] = []
    if not isinstance(priors, dict):
        return [Diagnostic("SV5", path, "算子先验必须是对象")]
    by_operator = priors.get("by_operator")
    if not isinstance(by_operator, dict):
        return [Diagnostic("SV5", f"{path}.by_operator", "缺少 by_operator")]
    for name, entry in sorted(by_operator.items()):
        if not isinstance(entry, dict):
            diagnostics.append(Diagnostic("SV5", f"{path}.by_operator.{name}", "必须是对象"))
            continue
        status = entry.get("status")
        if status not in OPERATOR_STATUSES:
            diagnostics.append(Diagnostic(
                "SV5", f"{path}.by_operator.{name}.status",
                f"status 必须是 {list(OPERATOR_STATUSES)} 之一；不存在「永久禁用」"))
        if status in ("discouraged", "dormant") and not entry.get("reactivation_conditions"):
            diagnostics.append(Diagnostic(
                "SV5", f"{path}.by_operator.{name}",
                "被降级的算子必须给出重启条件，否则等于永久封禁"))
        if status == "discouraged" and len(entry.get("failures") or []) < MIN_INDEPENDENT_FAILURES:
            diagnostics.append(Diagnostic(
                "SV5", f"{path}.by_operator.{name}",
                f"少于 {MIN_INDEPENDENT_FAILURES} 次独立失败不得降级；"
                "不得由几次失败推断一整类机制无效"))
        if status in ("discouraged", "dormant") and not entry.get("scope"):
            diagnostics.append(Diagnostic(
                "SV5", f"{path}.by_operator.{name}",
                "降级必须限定在测到失败的问题结构内；没有范围的降级等于全类封禁"))
    if not priors.get("exploration_floor"):
        diagnostics.append(Diagnostic(
            "SV7", f"{path}.exploration_floor",
            "必须保留探索下限：不得因历史 EIG 低而永久排除高潜力探索"))
    return diagnostics


#: The typed intermediate slots `P3` produces. Only these may reach `P4`.
P3_SKELETON_SLOTS: Tuple[str, ...] = (
    "object", "relation", "constraint", "failure_mode", "core_unknown",
)

#: Keys that indicate candidate content leaking into a cross-domain analogy.
CANDIDATE_LEAK_KEYS: Tuple[str, ...] = (
    "statement", "candidate", "candidates", "hypothesis", "hypotheses",
    "domain_aware", "domain_terms", "method", "conclusion", "answer", "solution",
)


def p4_context(intermediates_dir: Path) -> Dict[str, Any]:
    """Build the only context `P4` is allowed to see: de-domained typed skeletons.

    The isolation rule is "candidate content, not typed intermediate representations".
    A skeleton may therefore cross islands; a candidate, a domain name or another
    island's answer may not, because that would manufacture a false independent
    discovery ([phase-r3-r6-discovery.md](phase-r3-r6-discovery.md)).
    """
    skeletons: List[Dict[str, Any]] = []
    diagnostics: List[Diagnostic] = []
    if not intermediates_dir.is_dir():
        return {"skeletons": [], "diagnostics": [
            Diagnostic("SV6", str(intermediates_dir),
                       "没有 P3 typed intermediate 目录：P4 不得在缺少骨架时启动")]}
    for path in sorted(intermediates_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            diagnostics.append(Diagnostic("SV6", path.name, f"骨架不可解析：{exc}"))
            continue
        if not isinstance(payload, dict):
            diagnostics.append(Diagnostic("SV6", path.name, "骨架必须是对象"))
            continue
        leaked = sorted(key for key in payload if key in CANDIDATE_LEAK_KEYS)
        if leaked:
            diagnostics.append(Diagnostic(
                "SV6", path.name,
                f"跨岛上下文不得携带候选内容：{leaked}；只允许 {list(P3_SKELETON_SLOTS)}"))
            continue
        missing = [slot for slot in P3_SKELETON_SLOTS if slot not in payload]
        if missing:
            diagnostics.append(Diagnostic(
                "SV6", path.name, f"骨架缺少槽位：{missing}"))
            continue
        skeletons.append({"source": path.name,
                          **{slot: payload[slot] for slot in P3_SKELETON_SLOTS}})
    return {"skeletons": skeletons, "diagnostics": diagnostics}


def validate_p4_context(payload: Any, path: str = "p4_context") -> List[Diagnostic]:
    diagnostics: List[Diagnostic] = []
    if not isinstance(payload, dict):
        return [Diagnostic("SV6", path, "P4 上下文必须是对象")]
    for skeleton in payload.get("skeletons") or []:
        if not isinstance(skeleton, dict):
            diagnostics.append(Diagnostic("SV6", path, "骨架必须是对象"))
            continue
        extra = [key for key in skeleton
                 if key not in P3_SKELETON_SLOTS and key != "source"]
        if extra:
            diagnostics.append(Diagnostic(
                "SV6", f"{path}.skeletons[{skeleton.get('source')}]",
                f"骨架只能携带 {list(P3_SKELETON_SLOTS)}，实际多出 {extra}"))
    return diagnostics


def recommend_strategy(
    state: Dict[str, Any],
    index: Dict[str, Any],
    scheduler: Optional[Dict[str, Any]] = None,
    revisions: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Pick one discovery menu by explicit lexicographic rules. No aggregate score."""
    import prediction_compare as pc

    priors = operator_priors(state, index, scheduler)
    taste = calibrated_preferences(state, index, scheduler)
    switch = pc.diagnosis_switch(state, index.get("competitions", []), scheduler,
                                 index.get("mechanisms"))
    stop_scopes = [item for item in index.get("boundaries", [])
                   if item.get("kind") in ("stop_rule", "failed_repeat", "retry_forbidden")]
    recent_menus = [record.get("after", {}).get("menu") for record in (revisions or [])
                    if record.get("kind") == "strategy_update"
                    and isinstance(record.get("after"), dict)]
    recent_menus = [menu for menu in recent_menus if isinstance(menu, str)][-STAGNANT_MENU_RUN:]

    trigger_map = {
        "CONTINUE_ATTRIBUTION": "probe_structure_by_minimal_intervention",
        "FIND_DISCRIMINATING_INTERVENTION": "probe_structure_by_minimal_intervention",
        "RECORD_BOUNDARY_AND_STOP": "abandon_attribution_direction",
        "REDESIGN_QUESTION": "replace_problem_representation",
        "EXPLORE_METHOD_UNDER_UNCERTAINTY": "invert_hidden_assumption",
    }
    preferred_menu = trigger_map.get(switch["action"], "invert_hidden_assumption")

    ranked: List[Dict[str, Any]] = []
    for entry in STRATEGY_MENUS:
        operator = entry["operator"]
        status = priors["by_operator"].get(operator, {}).get("status", "neutral")
        haystack = " ".join(str(item.get(field, "")) for item in stop_scopes
                            for field in ("scope", "rule", "target"))
        blocked = [item for item in stop_scopes
                   if entry["shift"] in haystack or operator in haystack]
        stagnant = len(recent_menus) >= STAGNANT_MENU_RUN and set(recent_menus) == {entry["menu"]}
        ranked.append({
            "menu": entry["menu"],
            "operator": operator,
            "island": entry["island"],
            "shift": entry["shift"],
            "operator_status": status,
            "blocked_by": [item.get("target") for item in blocked],
            "preferred_by_switch": entry["menu"] == preferred_menu,
            "repeated_recently": stagnant,
            "divergent": entry["menu"] not in recent_menus,
        })

    def rank_key(item: Dict[str, Any]) -> Tuple[int, int, int, int, str]:
        # Lexicographic, no weights: nothing is traded against anything else.
        return (
            0 if not item["blocked_by"] else 1,                        # stop rules first
            0 if item["preferred_by_switch"] else 1,                   # behaviour switch
            0 if item["operator_status"] in ("encouraged", "neutral") else 1,  # history, not a ban
            0 if item["divergent"] else 1,                             # escape repetition
            item["menu"],
        )

    ranked.sort(key=rank_key)
    chosen = ranked[0]
    return {
        "menu": chosen["menu"],
        "operator": chosen["operator"],
        "island": chosen["island"],
        "shift": chosen["shift"],
        "reason": (f"behaviour switch = {switch['action']}；"
                   f"算子 {chosen['operator']} 历史状态 {chosen['operator_status']}；"
                   f"是否被终止性规则阻塞：{'是' if chosen['blocked_by'] else '否'}"),
        "basis": [f"operator:{chosen['operator']}", f"switch:{switch['action']}"],
        "expected_decision": switch["reason"],
        "blocked_menus": [item["menu"] for item in ranked if item["blocked_by"]],
        "discouraged_but_admissible": priors["discouraged"],
        "exploration_floor": priors["exploration_floor"],
        "exploration_rounds_delta": 0,
        "independent_exploration_allowed": True,
        "taste_preferences": [item["id"] for item in taste["evidence_calibrated"]],
        "alternatives": [item["menu"] for item in ranked[1:4]],
        "ordered_menus": [item["menu"] for item in ranked],
    }


def validate_recommendation(recommendation: Any, path: str = "recommendation") -> List[Diagnostic]:
    diagnostics: List[Diagnostic] = []
    if not isinstance(recommendation, dict):
        return [Diagnostic("SV7", path, "策略建议必须是对象")]
    if recommendation.get("menu") not in MENU_BY_NAME:
        diagnostics.append(Diagnostic("SV7", f"{path}.menu", "未知的探索菜单"))
    if recommendation.get("exploration_rounds_delta") != 0:
        diagnostics.append(Diagnostic(
            "SV7", f"{path}.exploration_rounds_delta",
            "不得无条件增加探索轮数；轮数只能由它要解决的决策决定"))
    if not recommendation.get("exploration_floor"):
        diagnostics.append(Diagnostic("SV7", f"{path}.exploration_floor", "缺少探索下限"))
    if recommendation.get("independent_exploration_allowed") is not True:
        diagnostics.append(Diagnostic(
            "SV7", f"{path}.independent_exploration_allowed",
            "普通未知不得全局阻塞独立探索"))
    return diagnostics


# ---------------------------------------------------------------------------
# 3.4 Self-improvement from outcomes
# ---------------------------------------------------------------------------

def strategy_updates(
    state: Dict[str, Any],
    index: Dict[str, Any],
    scheduler: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """The recordable form of the learning loop.

    The loop is `prediction → experiment → outcome → model revision → strategy update`.
    Only the last step is produced here, and only when the derived evidence actually
    justifies it. A prior that is already reflected in the canonical state produces no
    update, so the loop converges instead of appending a note every round.
    """
    priors = operator_priors(state, index, scheduler)
    taste = calibrated_preferences(state, index, scheduler)
    recommendation = recommend_strategy(state, index, scheduler)
    updates: List[Dict[str, Any]] = []
    for operator in priors["discouraged"]:
        entry = priors["by_operator"][operator]
        updates.append({
            "kind": "strategy_update",
            "subject": operator,
            "summary": f"{operator} 在已测结构下连续失败，降低其优先级（不封禁）",
            "refs": _refs_for(entry["failures"] + entry["successes"], state),
            "after": {"operator": operator, "action": "discourage",
                      "scope": entry["scope"],
                      "reactivation_conditions": entry["reactivation_conditions"],
                      "telemetry": {"source": "hypotheses[].status + scheduler.operator_stats"}},
        })
    for operator in priors["encouraged"]:
        entry = priors["by_operator"][operator]
        updates.append({
            "kind": "strategy_update",
            "subject": operator,
            "summary": f"{operator} 产出了被证据支持的候选，提高其优先级",
            "refs": _refs_for(entry["successes"], state),
            "after": {"operator": operator, "action": "encourage",
                      "scope": entry["scope"], "telemetry": {"source": "index mechanisms"}},
        })
    return {
        "updates": updates,
        "recommendation": recommendation,
        "applied_taste": [item["id"] for item in taste["evidence_calibrated"]],
        "note": ("这些是**建议追加**的 strategy_update 事件；必须由 R3—R6 / Meta-Controller "
                 "以真实 trigger 追加，并保持 refs 指向 canonical 对象"),
    }


def _refs_for(identifiers: Sequence[str], state: Dict[str, Any]) -> Dict[str, List[str]]:
    view = cg.CanonicalView(state)
    refs = {key: [] for key in cg.REF_KEYS}
    for ident in identifiers:
        for key in cg.REF_KEYS:
            if view.contains(key, ident):
                refs[key].append(ident)
                break
    return refs


# ---------------------------------------------------------------------------
# Validation of recorded strategy updates
# ---------------------------------------------------------------------------

def validate_strategy_revisions(
    state: Dict[str, Any],
    revisions: Sequence[Dict[str, Any]],
) -> List[Diagnostic]:
    diagnostics: List[Diagnostic] = []
    view = cg.CanonicalView(state)
    for record in revisions:
        if record.get("kind") != "strategy_update":
            continue
        path = f"{cg.REVISIONS_NAME}:{record.get('_line', '?')}"
        after = record.get("after") if isinstance(record.get("after"), dict) else {}
        for key in BANNED_AGGREGATE_KEYS:
            if key in after:
                diagnostics.append(Diagnostic(
                    "SV1", path, f"策略更新不得携带聚合分数 {key}"))
        for forbidden in ("contract", "primary_anchor", "anchor", "out_of_scope", "research_goal"):
            if forbidden in after:
                diagnostics.append(Diagnostic(
                    "SV3", path,
                    f"策略学习不得修改研究锚点或契约（{forbidden}）；只有用户能改方向"))
        operator = after.get("operator")
        if operator is not None and operator not in sc.OPERATORS:
            diagnostics.append(Diagnostic(
                "SV5", path, f"未知算子 {operator!r}；不得自创探索算子"))
        if record.get("actor") not in ("R3", "R4", "R5", "R6", "R11", "CIE"):
            diagnostics.append(Diagnostic(
                "SV6", path, "strategy_update 只能由 Discovery 或 Meta-Controller 追加；"
                             "R12 / R13 / R14 不写认知层"))
        refs = cg.normalize_refs(record.get("refs"))
        if not any(refs.get(key) for key in cg.REF_KEYS):
            diagnostics.append(Diagnostic(
                "SV8", path, "策略更新必须引用 canonical 对象；没有依据的经验等于自评"))
        for key, ident in cg.iter_refs(refs):
            if not view.contains(key, ident):
                diagnostics.append(Diagnostic("SV8", path, f"悬空引用 {key}[{ident}]"))
    return cg._dedupe(diagnostics)


# ---------------------------------------------------------------------------
# CLI operations
# ---------------------------------------------------------------------------

def _load_scheduler(state_path: Path, override: Optional[Path]) -> Optional[Dict[str, Any]]:
    path = override or (state_path.parent / "scheduler.json")
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise cg.CognitionError(f"scheduler is not valid JSON: {path} ({exc.msg})") from exc


def _context(state_path: Path, cognition_dir: Path, scheduler_path: Optional[Path]):
    state = cg.load_state(state_path)
    revisions, _ = cg.load_revisions(cognition_dir / cg.REVISIONS_NAME)
    cards, _ = cg.load_insight_cards(cognition_dir / cg.INSIGHT_CARDS_NAME)
    index, _ = cg.full_index(state, revisions, state_path.parent.name, cards)
    return state, revisions, index, _load_scheduler(state_path, scheduler_path)


def _emit(payload: Any, diagnostics: Sequence[Diagnostic]) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    for diagnostic in diagnostics:
        print(diagnostic.render(), file=sys.stderr)
    return EXIT_OK if not diagnostics else EXIT_HARD


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _fixture() -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    def validity(reason: str, version: int = 4) -> Dict[str, Any]:
        return {"status": "valid", "reason": reason, "since_state_version": version}
    state = {
        "state_version": 4,
        "contract": {"goal": "判断机制 A 是否解释目标现象", "primary_anchor": "phenomenon",
                     "constraints": ["单卡"], "resources": ["公开数据集"],
                     "provisional_anchor_rationale": "先形式化", "out_of_scope": ["临床部署"]},
        "claims": [{
            "id": "C1", "statement": "机制 A 解释目标现象", "parent": None, "subclaims": [],
            "status": "partially-supported", "supporting_evidence": ["E1"], "refuting_evidence": [],
            "nearest_alternative": "机制 B", "falsifier": "干预后现象不变", "scope": "数据集 A",
            "known_flaws": [], "depends_on": [], "validity": validity("已按预注册写入"),
            "contract": {"statement": "机制 A", "scope": "数据集 A",
                         "critical_assumptions": [], "supporting_required": ["E1"],
                         "refuting": "干预后不变", "nearest_alternative": "机制 B",
                         "minimal_discriminating_experiment": "X2",
                         "expected_outcomes": {"O1": "下降", "O2": "不变"},
                         "kill_rule": "若 O2 出现则降级", "expansion_rule": "O1 且 X3 通过"},
        }],
        "evidence": [{
            "id": "E1", "kind": "experiment", "supports": ["C1"], "contradicts": [],
            "strength": "strong", "scope": "数据集 A", "epistemic_status": "Observed",
            "source_ref": "X1", "verification_tier": "T2", "depends_on": ["X1"],
            "validity": validity("X1 done"),
        }],
        "assumptions": [], "hypotheses": [
            {"id": "H1", "statement": "机制 A 是主因",
             "structural_signature": {"assumption_distance": 2, "formulation_distance": 1,
                                      "representation_distance": 0, "theory_lens_distance": 1,
                                      "mechanism_distance": 2},
             "novelty_source": "假设反转", "theory_lens": "逆问题", "nearest_prior": "LIT1",
             "falsifier": "干预无效", "expected_information_gain": 0.4, "status": "elite",
             "niche": "assumption-shift", "island": "P2", "generation": 0,
             "operator": "assumption_breaker", "parents": [], "depends_on": [],
             "validity": validity("未推翻"), "scientific_scope": "数据集 A"},
            {"id": "H2", "statement": "远域类比得到的候选（无预测）",
             "structural_signature": {"assumption_distance": 3, "formulation_distance": 2,
                                      "representation_distance": 2, "theory_lens_distance": 3,
                                      "mechanism_distance": 3},
             "novelty_source": "跨域类比", "theory_lens": "控制论", "nearest_prior": "LIT2",
             "falsifier": "结构对应不成立", "expected_information_gain": 0.2, "status": "active",
             "niche": "mechanism-shift", "island": "P4", "generation": 0,
             "operator": "remote_analogy", "parents": [], "depends_on": [],
             "validity": validity("未推翻"), "scientific_scope": None},
            {"id": "H3", "statement": "被淘汰的候选一",
             "structural_signature": {"assumption_distance": 1, "formulation_distance": 1,
                                      "representation_distance": 1, "theory_lens_distance": 1,
                                      "mechanism_distance": 1},
             "novelty_source": "理论视角", "theory_lens": "信息论", "nearest_prior": "LIT1",
             "falsifier": "推导不成立", "expected_information_gain": 0.1, "status": "killed",
             "niche": "theory-shift", "island": "P5", "generation": 0,
             "operator": "theory_lens", "parents": [], "depends_on": [],
             "validity": validity("已淘汰"), "scientific_scope": None},
            {"id": "H5", "statement": "理论视角候选（本轮没有产出）",
             "structural_signature": {"assumption_distance": 2, "formulation_distance": 2,
                                      "representation_distance": 1, "theory_lens_distance": 2,
                                      "mechanism_distance": 2},
             "novelty_source": "换一套数学语言", "theory_lens": "信息论", "nearest_prior": "LIT1",
             "falsifier": "推导不成立", "expected_information_gain": 0.15, "status": "elite",
             "niche": "theory-shift", "island": "P5", "generation": 0,
             "operator": "theory_lens", "parents": [], "depends_on": [],
             "validity": validity("未推翻"), "scientific_scope": None},
            {"id": "H4", "statement": "被淘汰的候选二",
             "structural_signature": {"assumption_distance": 1, "formulation_distance": 1,
                                      "representation_distance": 0, "theory_lens_distance": 1,
                                      "mechanism_distance": 1},
             "novelty_source": "理论视角", "theory_lens": "信息论", "nearest_prior": "LIT1",
             "falsifier": "推导不成立", "expected_information_gain": 0.1, "status": "killed",
             "niche": "theory-shift", "island": "P5", "generation": 1, "operator": "mutation",
             "parents": ["H3"], "depends_on": [], "validity": validity("已淘汰"),
             "scientific_scope": None},
        ],
        "experiments": [{
            "id": "X1", "parent": None, "stage": "X3", "claim_targeted": ["C1"],
            "alternative_targeted": ["ALT-1"], "code_commit": "abc", "data_split": "A/train",
            "seed": 0, "metric": "效应量", "result": "0.8", "interpretation": "初步",
            "unexpected": [], "known_flaws": [], "next_branches": [], "status": "done",
            "preregistration": {"frozen_at_state_version": 3, "outcomes": [
                {"id": "O1", "observation": "下降",
                 "criterion": {"kind": "quantitative", "quantity": "效应量",
                               "expected_range": [0.5, 3.0], "tolerance": 0.1, "rule": "x"},
                 "update": [{"target": "C1", "op": "strengthen"}]}]},
            "result_at_state_version": 4, "depends_on": [], "validity": validity("按预注册写入"),
            "outcome_analysis": None, "execution_protocol": None,
        }, {
            "id": "X2", "parent": "X1", "stage": "X3", "claim_targeted": ["C1"],
            "alternative_targeted": ["ALT-2"], "code_commit": "TBD", "data_split": "A/fixed",
            "seed": 0, "metric": "效应量变化", "result": "", "interpretation": "尚未运行",
            "unexpected": [], "known_flaws": [], "next_branches": [], "status": "planned",
            "preregistration": None, "result_at_state_version": None, "depends_on": ["X1"],
            "validity": {"status": "pending", "reason": "尚未运行", "since_state_version": 3},
            "outcome_analysis": None, "execution_protocol": None,
        }],
        "literature": [{"id": "LIT1", "ref": "[A, V/2024]", "relation": "shares-structure",
                        "depends_on": [], "validity": validity("未撤回")}],
        "failures": [], "uncertainties": [{
            "id": "U1", "question": "机制 A 在数据集 B 是否成立？", "importance": "critical",
            "uncertainty": "high", "cheapest_discriminating_test": "TBD", "status": "open",
            "depends_on": [], "validity": validity("未受波及"),
        }], "assurance": [], "repairs": [],
    }
    revisions = [
        {"_schema": cg.SCHEMA_REVISION, "id": "REV1", "seq": 1, "kind": "mechanism_create",
         "subject": "M1", "actor": "R3", "at_state_version": 3, "summary": "M1",
         "trigger": {"kind": "candidate_generation", "ref": "H1"},
         "refs": {"claims": ["C1"], "evidence": ["E1"], "hypotheses": ["H1"]},
         "after": {"statement": "机制 A 决定现象", "pending_predictions": ["X2:O1"]}},
        {"_schema": cg.SCHEMA_REVISION, "id": "REV2", "seq": 2, "kind": "mechanism_create",
         "subject": "M2", "actor": "R3", "at_state_version": 3, "summary": "M2",
         "trigger": {"kind": "candidate_generation", "ref": "H2"},
         "refs": {"hypotheses": ["H2"], "literature": ["LIT1"]},
         "after": {"statement": "远域类比得到的机制"}},
    ]
    scheduler = {
        "state_version": 4,
        "next_actions": [{"action": "X2", "type": "discriminating_experiment",
                          "target": "C1", "eig": "high", "cost": "low"}],
        "eig_calibration": {"records": [
            {"experiment": "X0", "predicted_information_gain": "low",
             "actual_information_gain": "zero",
             "observed_delta": {"claim_status_changes": [], "uncertainty_changes": [],
                                "hypothesis_status_changes": [], "new_uncertainties": [],
                                "unexpected_observations": 0}},
            {"experiment": "X1", "predicted_information_gain": "high",
             "actual_information_gain": "high",
             "observed_delta": {"claim_status_changes": [{"id": "C1", "from": "ungrounded",
                                                          "to": "partially-supported"}],
                                "uncertainty_changes": [], "hypothesis_status_changes": [],
                                "new_uncertainties": [], "unexpected_observations": 0}},
        ]},
        "operator_stats": {"by_operator": {"theory_lens": {"generations": 2, "viable": 0,
                                                           "killed": 2, "dormant": True}},
                           "recurring_failure_patterns": ["theory_lens 只产出 theory relabeling"]},
    }
    return state, revisions, scheduler


def selftest() -> int:
    failures = 0

    def check(name: str, condition: bool) -> None:
        nonlocal failures
        if not condition:
            failures += 1
            print(f"[FAIL] {name}")

    state, revisions, scheduler = _fixture()
    index, _ = cg.full_index(state, revisions, "A")

    check("every menu reuses a frozen operator and island",
          all(entry["operator"] in sc.OPERATORS and entry["island"] in sc.ISLANDS
              for entry in STRATEGY_MENUS))

    # -- value model -------------------------------------------------------
    assessment = value_assessment(state, index, "H1", scheduler)
    check("value assessment has both independent groups",
          set(assessment) >= {"decision_value", "discovery_potential"})
    check("value assessment validates", validate_value(assessment) == [])
    check("no aggregate key is produced",
          not any(key in assessment for key in BANNED_AGGREGATE_KEYS))
    check("every decision dimension cites a source",
          all(entry["basis"] for entry in assessment["decision_value"].values()))
    check("an aggregate is rejected",
          any(d.rule == "SV1" for d in validate_value(dict(assessment, score=0.9))))
    missing_basis = json.loads(json.dumps(assessment))
    missing_basis["decision_value"]["changes_route"]["basis"] = []
    check("a dimension without a source is rejected",
          any(d.rule == "SV2" for d in validate_value(missing_basis)))
    check("a hypothesis without an experiment scores no method change",
          assessment["decision_value"]["changes_method_choice"]["assessment"] in ASSESSMENTS)

    # -- taste memory ------------------------------------------------------
    taste = calibrated_preferences(state, index, scheduler)
    check("human preferences are read-only and attributed to the user",
          taste["human_specified"]["authority"] == "user"
          and taste["human_specified"]["mutable_by_agent"] is False)
    check("the anchor is not touched", taste["anchor_untouched"] is True)
    ids = {item["id"] for item in taste["evidence_calibrated"]}
    check("empty diagnostics become a calibrated preference", "TP-DIAG" in ids)
    check("productive interventions become a calibrated preference", "TP-INTERV" in ids)
    check("a dormant operator does not become a ban", "TP-DORMANT" in ids)
    check("every calibrated preference cites evidence",
          all(item["basis"] for item in taste["evidence_calibrated"]))
    check("every calibrated preference can be revisited",
          all(item["revisit_conditions"] for item in taste["evidence_calibrated"]))

    # -- operator priors ---------------------------------------------------
    priors = operator_priors(state, index, scheduler)
    check("priors validate", validate_priors(priors) == [])
    check("a dormant operator keeps reactivation conditions",
          priors["by_operator"]["theory_lens"]["reactivation_conditions"])
    check("dormant is not a permanent ban",
          priors["by_operator"]["theory_lens"]["status"] in OPERATOR_STATUSES)
    check("the exploration floor is never empty", bool(priors["exploration_floor"]))
    one_failure = json.loads(json.dumps(priors))
    one_failure["by_operator"]["remote_analogy"] = {
        "status": "discouraged", "failures": ["H2"], "successes": [],
        "scope": ["mechanism-shift"], "reactivation_conditions": ["x"]}
    check("a single failure cannot condemn an operator",
          any(d.rule == "SV5" for d in validate_priors(one_failure)))
    no_floor = json.loads(json.dumps(priors))
    no_floor["exploration_floor"] = []
    check("removing the exploration floor is rejected",
          any(d.rule == "SV7" for d in validate_priors(no_floor)))

    # -- P4 isolation ------------------------------------------------------
    import tempfile as _tempfile
    with _tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "good.json").write_text(json.dumps(
            {"object": "a", "relation": "b", "constraint": "c",
             "failure_mode": "d", "core_unknown": "e"}), encoding="utf-8")
        (root / "leaky.json").write_text(json.dumps(
            {"object": "a", "relation": "b", "constraint": "c", "failure_mode": "d",
             "core_unknown": "e", "statement": "另一个岛的候选答案"}), encoding="utf-8")
        context = p4_context(root)
        check("only the clean skeleton crosses to P4", len(context["skeletons"]) == 1)
        check("candidate content is refused",
              any("候选内容" in d.detail for d in context["diagnostics"]))
        check("the clean context validates", validate_p4_context(context) == [])
        polluted = {"skeletons": [{"object": "a", "relation": "b", "constraint": "c",
                                   "failure_mode": "d", "core_unknown": "e",
                                   "answer": "x"}]}
        check("a polluted context is rejected",
              any(d.rule == "SV6" for d in validate_p4_context(polluted)))

    # -- recommendation ----------------------------------------------------
    recommendation = recommend_strategy(state, index, scheduler, revisions)
    check("the recommendation validates", validate_recommendation(recommendation) == [])
    check("the recommendation names a real menu", recommendation["menu"] in MENU_BY_NAME)
    check("no exploration rounds are added", recommendation["exploration_rounds_delta"] == 0)
    check("independent exploration is allowed",
          recommendation["independent_exploration_allowed"] is True)
    check("the discouraged operator stays admissible",
          all(name in recommendation["discouraged_but_admissible"]
              for name in priors["discouraged"]))
    check("the ranking is lexicographic and total",
          len(recommendation["ordered_menus"]) == len(STRATEGY_MENUS))
    grown = json.loads(json.dumps(recommendation))
    grown["exploration_rounds_delta"] = 3
    check("unconditional extra rounds are rejected",
          any(d.rule == "SV7" for d in validate_recommendation(grown)))

    # a repeated menu forces divergence
    repeated = list(revisions) + [
        {"_schema": cg.SCHEMA_REVISION, "id": "REV3", "seq": 3, "kind": "strategy_update",
         "subject": "assumption_breaker", "actor": "R6", "at_state_version": 4,
         "summary": "repeat", "trigger": {"kind": "exploration_outcome", "ref": "H1"},
         "refs": {"hypotheses": ["H1"]},
         "after": {"menu": "invert_hidden_assumption", "operator": "assumption_breaker"}},
        {"_schema": cg.SCHEMA_REVISION, "id": "REV4", "seq": 4, "kind": "strategy_update",
         "subject": "assumption_breaker", "actor": "R6", "at_state_version": 4,
         "summary": "repeat", "trigger": {"kind": "exploration_outcome", "ref": "H1"},
         "refs": {"hypotheses": ["H1"]},
         "after": {"menu": "invert_hidden_assumption", "operator": "assumption_breaker"}},
    ]
    later = recommend_strategy(state, index, scheduler, repeated)
    check("a menu repeated twice stops being the top choice",
          later["menu"] != "invert_hidden_assumption"
          or later["ordered_menus"][0] != "invert_hidden_assumption")

    # -- self-improvement loop --------------------------------------------
    loop = strategy_updates(state, index, scheduler)
    check("the loop emits update suggestions", isinstance(loop["updates"], list))
    check("suggested updates cite canonical objects",
          all(any(refs.get(key) for key in cg.REF_KEYS)
              for refs in (update["refs"] for update in loop["updates"])))
    check("a strategy update referencing an anchor is rejected",
          any(d.rule == "SV3" for d in validate_strategy_revisions(state, [
              {"kind": "strategy_update", "actor": "R6", "refs": {"hypotheses": ["H1"]},
               "after": {"primary_anchor": "performance"}}])))
    check("a score-carrying strategy update is rejected",
          any(d.rule == "SV1" for d in validate_strategy_revisions(state, [
              {"kind": "strategy_update", "actor": "R6", "refs": {"hypotheses": ["H1"]},
               "after": {"score": 0.9}}])))
    check("a strategy update from the narrative layer is rejected",
          any(d.rule == "SV6" for d in validate_strategy_revisions(state, [
              {"kind": "strategy_update", "actor": "R12", "refs": {"hypotheses": ["H1"]},
               "after": {"operator": "P2"}}])))
    check("a baseless strategy update is rejected",
          any(d.rule == "SV8" for d in validate_strategy_revisions(state, [
              {"kind": "strategy_update", "actor": "R6", "refs": {}, "after": {}}])))

    # -- the loop closes: history changes the next action ------------------
    quiet_scheduler = {"state_version": 4, "next_actions": [],
                       "eig_calibration": {"records": []},
                       "operator_stats": {"by_operator": {}}}
    before = recommend_strategy(state, index, quiet_scheduler)
    after = recommend_strategy(state, index, scheduler)
    check("telemetry history changes the ordered menus",
          before["ordered_menus"] != after["ordered_menus"],
          )
    check("the operator that produced nothing is deprioritised",
          after["ordered_menus"].index("change_research_scale")
          > before["ordered_menus"].index("change_research_scale"))
    check("the deprioritised operator stays admissible",
          "theory_lens" in after["discouraged_but_admissible"]
          or after["operator"] != "P5")
    check("the deprioritised operator keeps its reactivation conditions",
          priors["by_operator"]["theory_lens"]["reactivation_conditions"]
          or priors["by_operator"]["theory_lens"]["status"] not in ("discouraged", "dormant"))

    print(f"selftest: {'PASS' if failures == 0 else 'FAIL'} ({failures} failures)")
    return EXIT_OK if failures == 0 else EXIT_ERROR


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # noqa: D401 - argparse hook
        self.print_usage(sys.stderr)
        print(f"argument error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(description="Scientific value, taste memory and adaptive discovery")
    parser.add_argument("command", nargs="?",
                        choices=["value", "taste", "operators", "recommend", "apply", "validate"])
    parser.add_argument("--state", help="path to research-state.json")
    parser.add_argument("--cognition", help="path to the cognition directory")
    parser.add_argument("--scheduler", help="path to scheduler.json")
    parser.add_argument("--target", help="hypothesis or claim id for value")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--list-menus", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.selftest:
        return selftest()
    if args.list_menus:
        for entry in STRATEGY_MENUS:
            print(f"{entry['menu']}\t{entry['operator']}\t{entry['shift']}")
        return EXIT_OK
    if not args.command:
        build_parser().print_usage(sys.stderr)
        print("argument error: a command is required", file=sys.stderr)
        return EXIT_ERROR
    if not args.state:
        print("argument error: --state is required", file=sys.stderr)
        return EXIT_ERROR
    state_path = Path(args.state).expanduser()
    cognition_dir = cg.cognition_dir_for(
        state_path, Path(args.cognition).expanduser() if args.cognition else None)
    scheduler_path = Path(args.scheduler).expanduser() if args.scheduler else None
    try:
        state, revisions, index, scheduler = _context(state_path, cognition_dir, scheduler_path)
        if args.command == "value":
            if not args.target:
                print("argument error: --target is required", file=sys.stderr)
                return EXIT_ERROR
            assessment = value_assessment(state, index, args.target, scheduler)
            return _emit(assessment, validate_value(assessment))
        if args.command == "taste":
            return _emit(calibrated_preferences(state, index, scheduler), [])
        if args.command == "operators":
            priors = operator_priors(state, index, scheduler)
            return _emit(priors, validate_priors(priors))
        if args.command == "recommend":
            recommendation = recommend_strategy(state, index, scheduler, revisions)
            return _emit(recommendation, validate_recommendation(recommendation))
        if args.command == "apply":
            return _emit(strategy_updates(state, index, scheduler), [])
        if args.command == "validate":
            diagnostics = validate_strategy_revisions(state, revisions)
            return _emit({"strategy_updates": sum(1 for record in revisions
                                                  if record.get("kind") == "strategy_update")},
                         diagnostics)
    except cg.CognitionError as exc:
        print(f"environment error: {exc}", file=sys.stderr)
        return EXIT_ENV
    print(f"argument error: unknown command {args.command!r}", file=sys.stderr)
    return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
