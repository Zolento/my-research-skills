#!/usr/bin/env python3
"""insight_to_method.py — Insight-to-Method Transition (I2M).

The system could already *detect* that repeating a diagnosis is pointless
(`execution_gate.diagnostic_check` → T8/`STOP_DIAGNOSIS`,
`prediction_compare.diagnosis_switch` → advice strings), but nothing could turn a
mechanism finding into an actual algorithmic intervention: there was no readiness
test, no synthesis, no design contract, no minimal-intervention test plan, and no
method-progress signal.  The Loop therefore fell back to another scheduler action
(usually another diagnosis) until T8, then went to R5.1 retrieval and R3/R6
candidate regeneration — never to method synthesis.

This module adds exactly that missing capability, **without** a sixteenth R stage,
a ninth Research State object, or a parallel state machine:

* a **method candidate** is an ordinary `hypotheses[]` entry carrying a `method`
  block (R3/R6 already own that collection);
* a **design contract** is frozen inside the existing `experiments[].preregistration`
  that R8 already creates;
* **readiness / transition / progress** are derived, and recorded as ordinary
  `decision-trajectory` records;
* the **anchor system** (SKILL.md §0.1, `claim-first-policy.md` §6) keeps deciding
  what kind of contribution is legitimate: method work is the primary path only for
  method/performance anchors.  A theory, phenomenon, benchmark, feasibility or
  negative anchor keeps its own contribution type, and method exploration is never
  forced.

Design rules:

* `readiness` is **not** proof.  A method may be proposed from an unverified
  mechanism, but the read-out must say `MECHANISM_HYPOTHESIS`, never
  `MECHANISM_VERIFIED`, unless observed state evidence backs the mechanism.
* Method Readiness, Anchor Eligibility and Anchor Satisfaction are three different
  things.  An unsatisfied primary anchor does **not** block method exploration, and
  local progress never counts as anchor achievement.
* Progress requires a real artifact change *and* new evidence.  Rewritten
  explanations, new documents, candidate counts and self-rated scores are not
  progress, and must not reset the stagnation counters.

CLI: `python3 scripts/insight_to_method.py --selftest`
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cognition as cg

# ---------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------

SCHEMA_READINESS = "research-idea-pipeline/i2m-readiness@1"
SCHEMA_CANDIDATE = "research-idea-pipeline/method-candidate@1"
SCHEMA_CONTRACT = "research-idea-pipeline/method-design-contract@1"
SCHEMA_MINIMAL_TEST = "research-idea-pipeline/minimal-intervention-test@1"

#: `readiness` verdicts.  `MECHANISM_VERIFIED` is decided from state evidence,
#: never from what the insight says about itself.
VERDICT_VERIFIED = "MECHANISM_VERIFIED"
VERDICT_HYPOTHESIS = "MECHANISM_HYPOTHESIS"
VERDICT_NOT_ACTIONABLE = "NOT_ACTIONABLE"
READINESS_VERDICTS = (VERDICT_VERIFIED, VERDICT_HYPOTHESIS, VERDICT_NOT_ACTIONABLE)

#: Readiness criteria.  Deliberately six, each individually inspectable.
CRITERION_PROBLEM = "problem_and_metric"
CRITERION_MECHANISM = "actionable_mechanism"
CRITERION_INTERVENTION = "constructible_intervention"
CRITERION_PREDICTIONS = "predictions_and_falsifiers"
CRITERION_MINIMAL_EXPERIMENT = "comparators_and_minimal_experiment"
CRITERION_PRIOR_ART = "prior_art_and_novelty_boundary"
READINESS_CRITERIA = (CRITERION_PROBLEM, CRITERION_MECHANISM, CRITERION_INTERVENTION,
                      CRITERION_PREDICTIONS, CRITERION_MINIMAL_EXPERIMENT,
                      CRITERION_PRIOR_ART)

#: Interventions that change the method itself.  A pure hyper-parameter sweep is
#: not method synthesis, so it is refused as the *primary* intervention.
METHOD_INTERVENTION_KINDS = ("objective", "architecture", "algorithm", "training",
                             "inference", "solver", "representation", "regularizer",
                             "sampling", "search_operator")
NON_METHOD_INTERVENTION_KINDS = ("hyperparameter", "tuning", "seed", "schedule_scale")

#: Failure taxonomy for a minimal intervention test.  A failed test is never
#: silently attributed to the mechanism.
FAILURE_IMPLEMENTATION = "IMPLEMENTATION_ERROR"
FAILURE_INEFFECTIVE = "INTERVENTION_INEFFECTIVE"
FAILURE_MECHANISM_WEAKENED = "MECHANISM_WEAKENED"
FAILURE_INCONCLUSIVE = "EXPERIMENT_INCONCLUSIVE"
FAILURE_TAXONOMY = (FAILURE_IMPLEMENTATION, FAILURE_INEFFECTIVE,
                    FAILURE_MECHANISM_WEAKENED, FAILURE_INCONCLUSIVE)

#: Method-development decisions.
DECISION_CONTINUE = "CONTINUE_DEVELOPMENT"
DECISION_REDESIGN = "REDESIGN_METHOD"
DECISION_RESYNTHESIZE = "SYNTHESIZE_ALTERNATIVES"
DECISION_DISCRIMINATE = "RUN_DISCRIMINATING_EXPERIMENT"
DECISION_REPAIR_IMPLEMENTATION = "REPAIR_IMPLEMENTATION"
DECISION_STOP_OR_R14 = "STOP_OR_R14"
METHOD_DECISIONS = (DECISION_CONTINUE, DECISION_REDESIGN, DECISION_RESYNTHESIZE,
                    DECISION_DISCRIMINATE, DECISION_REPAIR_IMPLEMENTATION,
                    DECISION_STOP_OR_R14)

#: The 15 required contract fields (task §C), in reporting order.
CONTRACT_FIELDS = ("problem_ref", "insight_refs", "method_hypothesis_ref", "intervention",
                   "mathematical_formulation", "algorithm_steps", "nearest_prior",
                   "distinctive_mechanism", "predictions", "falsifiers", "minimal_test",
                   "comparators", "success_criteria", "stop_rules", "evidence_status")

#: Anchor kinds (SKILL.md §0.1 / claim-first-policy.md §6).  `performance` is the
#: method-driven anchor; `method` is accepted as an explicit alias.
METHOD_ANCHORS = ("performance", "method", "algorithm")
NON_METHOD_ANCHORS = ("theory", "phenomenon", "benchmark", "feasibility", "negative")
ANCHOR_KINDS = METHOD_ANCHORS + NON_METHOD_ANCHORS

#: What each non-method anchor legitimately contributes (task: do not force algorithms).
ANCHOR_CONTRIBUTION = {
    "performance": "可执行算法/干预 + 同算力公平对比",
    "method": "可执行算法/干预 + 同算力公平对比",
    "algorithm": "可执行算法/干预 + 同算力公平对比",
    "theory": "定义/定理/证明与可反驳形式化结论",
    "phenomenon": "可复现表征、边界条件与判别预测",
    "benchmark": "数据集/指标/协议及其效度证据",
    "feasibility": "可行性演示、资源边界与负向构造",
    "negative": "被排除的假设及其证据范围（不得包装成方法）",
}

#: Anchor eligibility is evidence-decided; the author's target anchor is only a prior.
ELIGIBLE = "eligible"
CONDITIONAL = "conditional"
NOT_ELIGIBLE = "not-eligible"
ANCHOR_ELIGIBILITY = (ELIGIBLE, CONDITIONAL, NOT_ELIGIBLE)

ANCHOR_ROLES = ("primary", "supporting", "orthogonal")

_ANCHOR_ALIAS = {"理论": "theory", "性能": "performance", "现象": "phenomenon",
                 "基准": "benchmark", "可行性": "feasibility", "负结果": "negative"}

_EVIDENCE_BACKED = ("Observed", "Supported")


class Diagnostic(object):
    """A refusal reason: rule code + path + human-readable message."""

    __slots__ = ("rule", "path", "message")

    def __init__(self, rule: str, path: str, message: str) -> None:
        self.rule, self.path, self.message = rule, path, message

    def render(self) -> str:
        return f"{self.rule}  {self.path}  {self.message}"

    def as_dict(self) -> Dict[str, str]:
        return {"rule": self.rule, "path": self.path, "message": self.message}


def _diag(rule: str, path: str, message: str) -> Diagnostic:
    return Diagnostic(rule, path, message)


def _rules(diagnostics: Any) -> set:
    """Rule codes from either Diagnostic objects or their dict form."""
    codes = set()
    for item in diagnostics or []:
        if isinstance(item, Diagnostic):
            codes.add(item.rule)
        elif isinstance(item, dict):
            codes.add(str(item.get("rule")))
    return codes


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _present(value: Any) -> bool:
    """A field counts as filled if it is a non-empty string/list/dict or a number."""
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return value is not None and not isinstance(value, bool)


def _items(state: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    value = (state or {}).get(key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _index(state: Dict[str, Any], key: str) -> Dict[str, Dict[str, Any]]:
    return {str(item.get("id")): item for item in _items(state, key) if item.get("id")}


def _resolve(state: Dict[str, Any], ref: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Resolve `C3`/`E2`/`H1`/`X4`/`U5`/`F6`/`LIT7` to (collection, object)."""
    prefix = "".join(ch for ch in ref if ch.isalpha()).upper()
    table = {"C": "claims", "E": "evidence", "H": "hypotheses", "X": "experiments",
             "U": "uncertainties", "F": "failures", "LIT": "literature", "AS": "assurance",
             "P": "hypotheses"}
    key = table.get(prefix)
    if key is None:
        return None
    found = _index(state, key).get(ref)
    return (key, found) if found is not None else None


def anchor_kind(state: Dict[str, Any]) -> str:
    """The declared primary anchor, normalised to the English enum."""
    contract = (state or {}).get("contract") or {}
    raw = _text(contract.get("primary_anchor")) or _text(contract.get("core_goal"))
    raw = _ANCHOR_ALIAS.get(raw, raw).lower()
    return raw or "unknown"


def is_method_anchor(kind: str) -> bool:
    return kind in METHOD_ANCHORS


# ---------------------------------------------------------------------------
# A. Insight Readiness
# ---------------------------------------------------------------------------

def _target_metric(state: Dict[str, Any], insight: Dict[str, Any]) -> str:
    """A target metric may live in any existing place; we do not invent a new one."""
    contract = (state or {}).get("contract") or {}
    for source in (_text(insight.get("target_metric")), _text(contract.get("target_metric")),
                   _text(contract.get("metric")), _text(contract.get("success_metric"))):
        if source:
            return source
    for experiment in _items(state, "experiments"):
        metrics = (experiment.get("preregistration") or {}).get("metrics")
        if isinstance(metrics, list) and metrics:
            return str(metrics[0])
    for hypothesis in _items(state, "hypotheses"):
        criteria = hypothesis.get("success_criteria")
        if isinstance(criteria, str) and criteria.strip():
            return criteria.strip()
    return ""


def _mechanism_evidence(state: Dict[str, Any], hypothesis_ids: Sequence[str]) -> List[str]:
    """Evidence ids that actually back one of the referenced hypotheses."""
    backing: List[str] = []
    hypotheses = set(hypothesis_ids)
    for evidence in _items(state, "evidence"):
        if not hypotheses:
            break
        if evidence.get("epistemic_status") not in _EVIDENCE_BACKED:
            continue
        validity = evidence.get("validity")
        if isinstance(validity, dict) and validity.get("status") not in (None, "valid"):
            continue
        depends = {str(item) for item in evidence.get("depends_on") or []}
        supports = {str(item) for item in evidence.get("supports") or []}
        if depends & hypotheses or supports & hypotheses:
            backing.append(str(evidence.get("id")))
    return sorted(backing)


def insight_readiness(state: Dict[str, Any], insight: Dict[str, Any]) -> Dict[str, Any]:
    """Assess whether a finding can already support method design.

    Returns `{verdict, mechanism_status, criteria, missing, diagnostics, anchor_kind,
    method_anchor, notes}`.  The verdict is `MECHANISM_VERIFIED` only when state
    evidence backs the referenced mechanism; otherwise an unverified mechanism is
    still allowed to drive method work, reported as `MECHANISM_HYPOTHESIS`.
    """
    insight = insight if isinstance(insight, dict) else {}
    diagnostics: List[Diagnostic] = []
    criteria: Dict[str, bool] = {}

    # 1. problem and target metric
    goal = _text(((state.get("contract") or {}).get("goal")))
    metric = _target_metric(state, insight)
    problem_ref = _text(insight.get("problem_ref"))
    problem_ok = bool(goal) and bool(metric)
    criteria[CRITERION_PROBLEM] = problem_ok
    if not goal:
        diagnostics.append(_diag("I2M1", "contract.goal", "缺少研究目标：无法判断方法要改变什么"))
    if not metric:
        diagnostics.append(_diag("I2M2", "target_metric",
                                 "缺少目标指标：方法收益无法被测量"))
    if not problem_ref:
        diagnostics.append(_diag("I2M3", "problem_ref",
                                 "缺少 problem_ref：方法必须绑定一个具体问题"))

    # 2. actionable mechanism
    insight_refs = [str(item) for item in insight.get("insight_refs") or [] if _text(item)]
    hypothesis_ids = [ref for ref in insight_refs if ref.upper().startswith("H")]
    mechanism = _text(insight.get("mechanism"))
    resolved = [ref for ref in insight_refs if _resolve(state, ref) is not None]
    criteria[CRITERION_MECHANISM] = bool(mechanism) and bool(hypothesis_ids) \
        and len(resolved) == len(insight_refs)
    if not mechanism:
        diagnostics.append(_diag("I2M4", "mechanism", "缺少机制/工程局限陈述"))
    if not hypothesis_ids:
        diagnostics.append(_diag("I2M5", "insight_refs",
                                 "机制必须以 H 对象承载：不得把叙述当作事实源"))
    unresolved = [ref for ref in insight_refs if _resolve(state, ref) is None]
    if unresolved:
        diagnostics.append(_diag("I2M6", "insight_refs",
                                 f"以下引用无法在 state 中解析：{unresolved}"))

    # 3. constructible intervention (a lever exists)
    levers = [str(item) for item in insight.get("intervention_levers") or [] if _text(item)]
    if not levers:
        for hypothesis in _items(state, "hypotheses"):
            if str(hypothesis.get("id")) in hypothesis_ids:
                for field in ("intervention_axis", "variable", "operator"):
                    if _text(hypothesis.get(field)):
                        levers.append(str(hypothesis[field]))
                if _text(hypothesis.get("intervention")):
                    levers.append(_text(hypothesis["intervention"]))
    criteria[CRITERION_INTERVENTION] = bool(levers)
    if not levers:
        diagnostics.append(_diag("I2M7", "intervention_levers",
                                 "目前无法构造影响该局限的干预：不得强行包装成新方法"))

    # 4. predictions and falsifiers
    predictions = [item for item in insight.get("predictions") or [] if isinstance(item, dict)]
    falsifiers = [item for item in insight.get("falsifiers") or [] if _text(item)]
    criteria[CRITERION_PREDICTIONS] = bool(predictions) and bool(falsifiers) and \
        all(_text(item.get("observation")) for item in predictions)
    if not predictions:
        diagnostics.append(_diag("I2M8", "predictions",
                                 "缺少可检验预测：无法在方法开发前声明会观察到什么"))
    if not falsifiers:
        diagnostics.append(_diag("I2M9", "falsifiers", "缺少失败条件：方法不可被否证"))

    # 5. comparators and a feasible minimal experiment
    comparators = [str(item) for item in insight.get("comparators") or [] if _text(item)]
    minimal = insight.get("minimal_experiment")
    minimal_ok = isinstance(minimal, dict) and _text(minimal.get("plan"))
    criteria[CRITERION_MINIMAL_EXPERIMENT] = bool(comparators) and minimal_ok
    if not comparators:
        diagnostics.append(_diag("I2M10", "comparators",
                                 "缺少对照：至少需要无干预与最近邻方法"))
    if not minimal_ok:
        diagnostics.append(_diag("I2M11", "minimal_experiment",
                                 "缺少可行的最小实验（R8 计划）"))

    # 6. prior art and the novelty boundary
    prior = insight.get("prior_art")
    prior_items = [item for item in prior or [] if isinstance(item, dict)] \
        if isinstance(prior, list) else []
    novelty_checked = bool(prior_items) and bool(_text(insight.get("novelty_boundary")))
    criteria[CRITERION_PRIOR_ART] = novelty_checked
    if not prior_items:
        diagnostics.append(_diag("I2M12", "prior_art",
                                 "未核对直接相关的已有方法：不得把未核实的创新性写成事实"))
    if not _text(insight.get("novelty_boundary")):
        diagnostics.append(_diag("I2M13", "novelty_boundary",
                                 "缺少创新性边界说明"))

    # The mechanism status is decided by state evidence, not by the insight's claim.
    backing = _mechanism_evidence(state, hypothesis_ids)
    declared = _text(insight.get("mechanism_status")).upper()
    mechanism_status = VERDICT_VERIFIED if backing else VERDICT_HYPOTHESIS
    if declared == "VERIFIED" and not backing:
        diagnostics.append(_diag("I2M14", "mechanism_status",
                                 "insight 自称机制已验证，但 state 中没有观测证据支持："
                                 "readiness 不是科学证实"))
    blocking = [CRITERION_PROBLEM, CRITERION_MECHANISM, CRITERION_INTERVENTION,
                CRITERION_PREDICTIONS, CRITERION_MINIMAL_EXPERIMENT]
    if all(criteria.get(name) for name in blocking):
        verdict = mechanism_status
    else:
        verdict = VERDICT_NOT_ACTIONABLE
    return {"schema": SCHEMA_READINESS, "verdict": verdict,
            "mechanism_status": mechanism_status, "criteria": criteria,
            "missing": sorted(name for name, ok in criteria.items() if not ok),
            "evidence_backing": backing, "levers": sorted(set(levers)),
            "target_metric": metric, "diagnostics": [item.as_dict() for item in diagnostics],
            "anchor_kind": anchor_kind(state), "method_anchor": is_method_anchor(anchor_kind(state)),
            "notes": "readiness 表示「已足以支持方法设计」，不是机制已被证实。"}


# ---------------------------------------------------------------------------
# B. Method Synthesis
# ---------------------------------------------------------------------------

def synthesis_errors(state: Dict[str, Any], readiness: Dict[str, Any],
                     candidates: Sequence[Dict[str, Any]]) -> List[Diagnostic]:
    """Validation for a synthesis round: 2–3 distinct, falsifiable interventions."""
    problems: List[Diagnostic] = []
    if readiness.get("verdict") == VERDICT_NOT_ACTIONABLE:
        return [_diag("I2M15", "readiness",
                      "readiness 不足（" + ", ".join(readiness.get("missing") or [])
                      + "）：不得强行包装成新方法")]
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        return [_diag("I2M16", "candidates", "候选必须是列表")]
    if not 2 <= len(candidates) <= 3:
        problems.append(_diag("I2M17", "candidates",
                              f"需要 2—3 种不同干预方案，当前 {len(candidates)} 种"))
    seen: Dict[str, str] = {}
    for position, candidate in enumerate(candidates):
        path = f"candidates[{position}]"
        if not isinstance(candidate, dict):
            problems.append(_diag("I2M18", path, "候选必须是对象"))
            continue
        ident = _text(candidate.get("candidate_id")) or path
        intervention = candidate.get("intervention")
        kind = _text((intervention or {}).get("kind")) if isinstance(intervention, dict) else ""
        if not kind:
            problems.append(_diag("I2M19", f"{path}.intervention", "缺少干预类型"))
        elif kind in NON_METHOD_INTERVENTION_KINDS:
            problems.append(_diag("I2M20", f"{path}.intervention.kind",
                                  f"{kind} 不是方法层面的干预：优先探索建模/结构/目标/"
                                  "算法/训练/推理机制，而不是只调超参数"))
        for field in ("how_it_addresses", "mechanism_basis", "structural_difference",
                      "minimal_implementation_complexity", "expected_benefit",
                      "resource_cost", "failure_boundary"):
            if not _present(candidate.get(field)):
                problems.append(_diag("I2M21", f"{path}.{field}",
                                      "候选对比字段缺失"))
        predictions = [item for item in candidate.get("falsifiable_predictions") or []
                       if _text(item)]
        if not predictions:
            problems.append(_diag("I2M22", f"{path}.falsifiable_predictions",
                                  "缺少可证伪预测"))
        # Structural distinctness: same mechanism + same formulation is not a new method.
        fingerprint = cg.digest_of({
            "mechanism": _text(candidate.get("distinctive_mechanism")),
            "formulation": _text(candidate.get("mathematical_formulation")),
            "kind": kind})
        if fingerprint in seen:
            problems.append(_diag("I2M23", path,
                                  f"与 {seen[fingerprint]} 结构同构：不得为凑数量制造同构方法"))
        else:
            seen[fingerprint] = ident
    return problems


def synthesize_methods(state: Dict[str, Any], readiness: Dict[str, Any],
                       candidates: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate a synthesis round and mark what may and may not be claimed."""
    problems = synthesis_errors(state, readiness, candidates)
    accepted = [dict(item) for item in candidates if isinstance(item, dict)] \
        if not problems else []
    for item in accepted:
        item.setdefault("schema", SCHEMA_CANDIDATE)
        item["evidence_status"] = readiness.get("mechanism_status", VERDICT_HYPOTHESIS)
        item["novelty_verified"] = False          # never asserted, only recorded as unchecked
    return {"status": "SYNTHESIZED" if accepted else "INVALID",
            "candidates": accepted,
            "diagnostics": [item.as_dict() for item in problems],
            "readiness_verdict": readiness.get("verdict"),
            "anchor_contribution": ANCHOR_CONTRIBUTION.get(readiness.get("anchor_kind", ""), "")}


# ---------------------------------------------------------------------------
# C. Method Design Contract
# ---------------------------------------------------------------------------

def _non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def design_contract_errors(state: Dict[str, Any], contract: Dict[str, Any]) -> List[Diagnostic]:
    """Validate the 15 required fields and their binding to real state objects."""
    problems: List[Diagnostic] = []
    if not isinstance(contract, dict):
        return [_diag("I2M24", "contract", "设计契约必须是对象")]
    for field in CONTRACT_FIELDS:
        value = contract.get(field)
        ok = bool(value) if not isinstance(value, (list, dict)) else bool(value)
        if isinstance(value, str):
            ok = bool(value.strip())
        if not ok:
            problems.append(_diag("I2M25", f"contract.{field}", "必填字段缺失"))

    if _resolve(state, _text(contract.get("problem_ref"))) is None \
            and _text(contract.get("problem_ref")) not in ("contract", "goal"):
        problems.append(_diag("I2M26", "contract.problem_ref",
                              "problem_ref 必须在 state 中可解析（或为 contract）"))
    for ref in contract.get("insight_refs") or []:
        if _resolve(state, str(ref)) is None:
            problems.append(_diag("I2M27", "contract.insight_refs",
                                  f"引用 {ref} 无法解析：引用必须可核验"))
    hypothesis_ref = _text(contract.get("method_hypothesis_ref"))
    hypothesis = _resolve(state, hypothesis_ref)
    if hypothesis is None or hypothesis[0] != "hypotheses":
        problems.append(_diag("I2M28", "contract.method_hypothesis_ref",
                              "方法假设必须引用既有 H 对象"))

    intervention = contract.get("intervention")
    kind = _text(intervention.get("kind")) if isinstance(intervention, dict) else ""
    if kind in NON_METHOD_INTERVENTION_KINDS or not kind:
        problems.append(_diag("I2M29", "contract.intervention",
                              "干预必须改变方法本身（目标/结构/算法/训练/推理/求解），"
                              "不能只是超参数调整"))
    if not _present(contract.get("mathematical_formulation")):
        problems.append(_diag("I2M30", "contract.mathematical_formulation",
                              "缺少数学定义"))
    if not _non_empty_list(contract.get("algorithm_steps")):
        problems.append(_diag("I2M31", "contract.algorithm_steps", "缺少算法步骤"))
    if not _present(contract.get("nearest_prior")) \
            or not _present(contract.get("distinctive_mechanism")):
        problems.append(_diag("I2M32", "contract.nearest_prior",
                              "缺少最近邻方法与结构差异：无法判断方法是否真的新"))
    predictions = [item for item in contract.get("predictions") or [] if isinstance(item, dict)]
    if not predictions or any(not _text(item.get("observation")) for item in predictions):
        problems.append(_diag("I2M33", "contract.predictions",
                              "预测必须给出可观测结果"))
    if not _non_empty_list(contract.get("falsifiers")):
        problems.append(_diag("I2M34", "contract.falsifiers", "缺少可证伪条件"))
    if not _non_empty_list(contract.get("comparators")) or len(contract["comparators"]) < 2:
        problems.append(_diag("I2M35", "contract.comparators",
                              "至少需要无干预与最近邻方法两个对照"))
    if not _non_empty_list(contract.get("success_criteria")):
        problems.append(_diag("I2M36", "contract.success_criteria", "缺少成功判据"))
    if not _non_empty_list(contract.get("stop_rules")):
        problems.append(_diag("I2M37", "contract.stop_rules", "缺少停止条件"))

    status = _text(contract.get("evidence_status"))
    if status not in (VERDICT_HYPOTHESIS, "partially_supported", "supported"):
        problems.append(_diag("I2M38", "contract.evidence_status",
                              "evidence_status 取值非法"))
    elif status == "supported":
        backing = _mechanism_evidence(state, [hypothesis_ref])
        if not backing:
            problems.append(_diag("I2M39", "contract.evidence_status",
                                  "state 中没有观测证据支持该机制：不得声称 supported"))
    if not _text(contract.get("rules_digest")):
        problems.append(_diag("I2M40", "contract.rules_digest",
                              "设计契约必须绑定冻结规则指纹"))
    return problems


def contract_from_candidate(candidate: Dict[str, Any], *, insight: Dict[str, Any],
                            rules_digest: str) -> Dict[str, Any]:
    """Build a contract skeleton from a candidate; the caller fills the specifics."""
    return {"schema": SCHEMA_CONTRACT,
            "problem_ref": _text(insight.get("problem_ref")),
            "insight_refs": list(insight.get("insight_refs") or []),
            "method_hypothesis_ref": _text(candidate.get("method_hypothesis_ref")),
            "intervention": candidate.get("intervention"),
            "mathematical_formulation": _text(candidate.get("mathematical_formulation")),
            "algorithm_steps": list(candidate.get("algorithm_steps") or []),
            "nearest_prior": _text(candidate.get("nearest_prior")),
            "distinctive_mechanism": _text(candidate.get("distinctive_mechanism")),
            # a bare prediction string is a measurable observation; the contract validator
            # still requires the dict form, so normalise it here rather than loosening the gate
            "predictions": [item if isinstance(item, dict) else {"observation": str(item)}
                            for item in candidate.get("falsifiable_predictions") or []],
            "falsifiers": list(candidate.get("failure_boundary") or []),
            "minimal_test": candidate.get("minimal_test"),
            "comparators": list(candidate.get("comparators") or []),
            "success_criteria": list(candidate.get("success_criteria") or []),
            "stop_rules": list(candidate.get("stop_rules") or []),
            "evidence_status": candidate.get("evidence_status", VERDICT_HYPOTHESIS),
            "rules_digest": rules_digest}


# ---------------------------------------------------------------------------
# D. Minimal Intervention Test
# ---------------------------------------------------------------------------

def minimal_test_errors(state: Dict[str, Any], plan: Dict[str, Any], *,
                        gate: Optional[Dict[str, Any]] = None) -> List[Diagnostic]:
    """Pre-registered minimal intervention test, before any large run."""
    problems: List[Diagnostic] = []
    if not isinstance(plan, dict):
        return [_diag("I2M41", "minimal_test", "最小干预测试必须是对象")]
    if not _text(plan.get("implementation_change")):
        problems.append(_diag("I2M42", "implementation_change",
                              "必须实际改动算法或方法实现，而不是只写计划"))
    if not _text(plan.get("expected_delta")):
        problems.append(_diag("I2M43", "expected_delta",
                              "必须预先声明干预后应观察到什么可测变化"))
    comparators = [str(item) for item in plan.get("comparators") or [] if _text(item)]
    if len(comparators) < 2:
        problems.append(_diag("I2M44", "comparators",
                              "至少需要无干预对照与最近邻方法对照"))
    metrics = [str(item) for item in plan.get("primary_metrics") or [] if _text(item)]
    if not metrics:
        problems.append(_diag("I2M45", "primary_metrics",
                              "主要指标必须提前冻结"))
    if not _non_empty_list(plan.get("decision_criteria")):
        problems.append(_diag("I2M46", "decision_criteria", "判别标准必须提前冻结"))
    if not _non_empty_list(plan.get("stop_rules")):
        problems.append(_diag("I2M47", "stop_rules", "停止条件必须提前冻结"))
    fairness = plan.get("fairness")
    if not isinstance(fairness, dict):
        problems.append(_diag("I2M48", "fairness", "缺少公平性核验"))
    else:
        for axis in ("capacity", "intervention_strength", "optimization", "compute_budget"):
            if fairness.get(axis) is not True:
                problems.append(_diag("I2M49", f"fairness.{axis}",
                                      f"公平性轴 {axis} 未核验：不得以不公平对比宣称收益"))
    if not _text(plan.get("preregistration_digest")):
        problems.append(_diag("I2M50", "preregistration_digest",
                              "最小实验必须针对冻结的 preregistration 摘要"))
    if plan.get("gpu_required") and not plan.get("execution_eligibility"):
        problems.append(_diag("I2M51", "execution_eligibility",
                              "需要 GPU 的最小实验必须先具备执行资格信息"))
    if isinstance(gate, dict) and gate.get("status") not in (None, "PASS", "PILOT_ONLY"):
        problems.append(_diag("I2M52", "gate",
                              "执行前门禁未通过（" + ", ".join(gate.get("errors") or []) + "）："
                              "不得使用 GPU 或预算"))
    return problems


def test_failure_errors(state: Dict[str, Any], outcome: Dict[str, Any], *,
                        frozen_digest: str) -> List[Diagnostic]:
    """A failed minimal test must be classified, and the frozen criteria stay frozen."""
    problems: List[Diagnostic] = []
    if not isinstance(outcome, dict):
        return [_diag("I2M53", "outcome", "结果必须是对象")]
    classification = _text(outcome.get("classification")).upper()
    if classification not in FAILURE_TAXONOMY:
        problems.append(_diag("I2M54", "classification",
                              "最小实验失败必须区分实现错误 / 干预无效 / 机制被削弱 / "
                              "实验不可判别，不得自动归因"))
    if _text(outcome.get("preregistration_digest")) != _text(frozen_digest):
        problems.append(_diag("I2M55", "preregistration_digest",
                              "预注册的指标或判据被事后修改：结果不可用于任何结论"))
    return problems


# ---------------------------------------------------------------------------
# E. Method Development Loop + progress signal
# ---------------------------------------------------------------------------

def _method_fingerprint(hypothesis: Dict[str, Any]) -> str:
    method = hypothesis.get("method") if isinstance(hypothesis.get("method"), dict) else {}
    return cg.digest_of({"intervention": method.get("intervention"),
                         "formulation": method.get("mathematical_formulation"),
                         "steps": method.get("algorithm_steps")})


def method_progress(state: Dict[str, Any], *, before: Dict[str, Any],
                    after: Dict[str, Any], experiment_id: str = "",
                    previous_evidence: Sequence[str] = ()) -> Dict[str, Any]:
    """Did the *method* actually change, backed by new evidence?

    Rewriting an explanation, adding a document, adding candidate records or a
    self-rated score is not progress.  Only a changed method fingerprint **and** at
    least one new executed-evidence id count, which is what may reset stagnation.
    """
    method_changed = _method_fingerprint(before) != _method_fingerprint(after)
    evidence_now = {str(item.get("id")) for item in _items(state, "evidence")}
    new_evidence = sorted(evidence_now - {str(item) for item in previous_evidence})
    executed = []
    for ident in new_evidence:
        evidence = _index(state, "evidence").get(ident) or {}
        if evidence.get("epistemic_status") in _EVIDENCE_BACKED:
            executed.append(ident)
    experiments = _index(state, "experiments")
    executed_records = [xid for xid in ([experiment_id] if experiment_id else [])
                        if (experiments.get(xid) or {}).get("status") in ("done", "failed")]
    narrative_only = bool((state.get("narrative_view") or {})) and not method_changed
    return {"progress": bool(method_changed and executed),
            "method_changed": method_changed,
            "new_evidence": new_evidence, "executed_evidence": executed,
            "found": executed_records,
            "narrative_only_change": narrative_only,
            "reason": ("方法指纹与证据都发生了变化：可以推进停滞计数重置"
                       if method_changed and executed else
                       "没有同时出现方法变化与新增执行证据：不得重置停滞计数"),
            "excluded_signals": ["narrative_view", "reports", "candidate_count",
                                 "document_count", "self_rated_score"]}


def advance(state: Dict[str, Any], *, readiness: Optional[Dict[str, Any]] = None,
            contract: Optional[Dict[str, Any]] = None, minimal_test: Optional[Dict[str, Any]] = None,
            outcome: Optional[Dict[str, Any]] = None,
            zero_streak: int = 0) -> Dict[str, Any]:
    """The next method-development decision: continue / redesign / resynthesize / stop."""
    readiness = readiness or {}
    if outcome and _text(outcome.get("status")) == "failed":
        classification = _text(outcome.get("classification")).upper()
        if classification == FAILURE_IMPLEMENTATION:
            return {"decision": DECISION_REPAIR_IMPLEMENTATION, "reason": "先修实现，再判断干预是否有效"}
        if classification == FAILURE_INEFFECTIVE:
            return {"decision": DECISION_REDESIGN, "reason": "干预无效：修改方法而非解释"}
        if classification == FAILURE_MECHANISM_WEAKENED:
            return {"decision": DECISION_RESYNTHESIZE,
                    "reason": "该机制被削弱：换机制或重新合成，不扩大否证范围"}
        return {"decision": DECISION_DISCRIMINATE,
                "reason": "实验不可判别：补做必要判别实验后再下结论"}
    if minimal_test and not outcome:
        return {"decision": DECISION_CONTINUE, "reason": "最小干预测试已登记，等待执行结果"}
    if readiness.get("verdict") == VERDICT_NOT_ACTIONABLE:
        if zero_streak >= 2:
            return {"decision": DECISION_STOP_OR_R14,
                    "reason": "重复诊断不再改变方法决定且 readiness 不足：按 R14 决策或停止"}
        return {"decision": DECISION_DISCRIMINATE,
                "reason": "先做能改变方法决定的判别实验（" + ", ".join(readiness.get("missing") or []) + "）"}
    if contract is None:
        return {"decision": DECISION_RESYNTHESIZE, "reason": "readiness 已足够：先合成并冻结设计契约"}
    return {"decision": DECISION_CONTINUE, "reason": "继续方法开发：设计→实现→有效性→消融→公平对比"}


# ---------------------------------------------------------------------------
# Anchor compatibility (SKILL.md §0.1/§0.2, claim-first-policy.md §6)
# ---------------------------------------------------------------------------

def anchor_eligibility(state: Dict[str, Any], target: Optional[str] = None) -> Dict[str, Any]:
    """Evidence decides which anchor is usable; the declared target is only a prior.

    Three-valued per `claim-first-policy.md` §6: eligible / conditional / not-eligible.
    """
    kind = (target or anchor_kind(state)).lower()
    kind = _ANCHOR_ALIAS.get(kind, kind)
    supported = [str(item.get("id")) for item in _items(state, "claims")
                 if item.get("status") == "supported"]
    partial = [str(item.get("id")) for item in _items(state, "claims")
               if item.get("status") == "partially-supported"]
    observed = [str(item.get("id")) for item in _items(state, "evidence")
                if item.get("epistemic_status") in _EVIDENCE_BACKED]
    if not observed:
        verdict, required = NOT_ELIGIBLE, "缺少观测证据：任何 anchor 都还不可用"
    elif supported:
        verdict, required = ELIGIBLE, ""
    else:
        verdict, required = CONDITIONAL, "需要至少一条 supported claim 才能据此 anchor 组织叙事"
    return {"target_anchor": kind, "verdict": verdict, "required_evidence": required,
            "supported_claims": supported, "partial_claims": partial,
            "observed_evidence": observed,
            "note": "作者的目标 anchor 是 prior，不是 decision；证据先行。"}


def anchor_role_errors(declaration: Dict[str, Any]) -> List[Diagnostic]:
    """`supporting` must be falsifiable; otherwise only `orthogonal` is allowed."""
    problems: List[Diagnostic] = []
    declaration = declaration if isinstance(declaration, dict) else {}
    role = _text(declaration.get("anchor_role"))
    if role not in ANCHOR_ROLES:
        return [_diag("I2M56", "anchor_role",
                      f"anchor_role 必须是 {ANCHOR_ROLES} 之一")]
    if role == "supporting":
        if not _text(declaration.get("serves")):
            problems.append(_diag("I2M57", "serves",
                                  "supporting 必须写明服务哪条主锚点与通过什么机制"))
        if not _text(declaration.get("serves_evidence")):
            problems.append(_diag("I2M58", "serves_evidence",
                                  "supporting 的机制必须落到可核验的贡献/实验"))
        if not _text(declaration.get("downstream_decision")) \
                or not _text(declaration.get("measurable_impact")):
            problems.append(_diag("I2M59", "downstream_decision",
                                  "supporting 必须可证伪：说明会改变哪个下游决策及其可测影响；"
                                  "答不出只能标 orthogonal"))
    return problems


def anchor_gap(state: Dict[str, Any], gap: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Maintain the gap to an unsatisfied primary anchor (never a new fact source)."""
    kind = anchor_kind(state)
    gap = gap if isinstance(gap, dict) else {}
    eligibility = anchor_eligibility(state, kind)
    satisfied = [str(item) for item in gap.get("satisfied") or [] if _text(item)]
    missing = [str(item) for item in gap.get("missing_evidence") or [] if _text(item)]
    refuted = [str(item) for item in gap.get("refuted_requirements") or [] if _text(item)]
    interventions = [str(item) for item in gap.get("feasible_interventions") or [] if _text(item)]
    next_test = _text(gap.get("next_discriminating_test"))
    exits = [str(item) for item in gap.get("exit_conditions") or [] if _text(item)]
    return {"anchor_kind": kind, "contribution": ANCHOR_CONTRIBUTION.get(kind, ""),
            "eligibility": eligibility["verdict"], "satisfied": satisfied,
            "missing_evidence": missing, "refuted_requirements": refuted,
            "feasible_interventions": interventions, "next_discriminating_test": next_test,
            "exit_conditions": exits,
            "unsatisfied": bool(missing or refuted),
            "blocks_method_work": False,
            "note": "主锚点尚未满足不阻止方法探索；但局部进展不等于主锚点达成。"}


def anchor_change_errors(change: Dict[str, Any]) -> List[Diagnostic]:
    """An anchor change is legitimate only with explicit user authorisation (§0.2)."""
    problems: List[Diagnostic] = []
    change = change if isinstance(change, dict) else {}
    if not _text(change.get("new_anchor")):
        problems.append(_diag("I2M60", "new_anchor", "锚点变更单必须写明新锚点"))
    if change.get("user_authorized") is not True:
        problems.append(_diag("I2M61", "user_authorized",
                              "只有用户能授权改主锚点：agent 只能提请，不得自行替换"))
    if not _text(change.get("evidence")) or not _text(change.get("reason")):
        problems.append(_diag("I2M62", "evidence",
                              "提请调整锚点必须给出证据与理由；不得放宽冻结成功标准或"
                              "通过修改叙事制造达标"))
    return problems


def anchor_path(state: Dict[str, Any], *, readiness: Optional[Dict[str, Any]] = None,
                gap: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Choose the Insight-to-Contribution path from the primary anchor."""
    kind = anchor_kind(state)
    readiness = readiness or {}
    gap = gap or anchor_gap(state)
    if is_method_anchor(kind):
        if readiness.get("verdict") == VERDICT_NOT_ACTIONABLE:
            return {"path": "METHOD_DISCRIMINATE", "contribution": ANCHOR_CONTRIBUTION[kind],
                    "reason": "方法锚点但 readiness 不足：先做判别实验，不强行合成方法"}
        return {"path": "METHOD_SYNTHESIS", "contribution": ANCHOR_CONTRIBUTION[kind],
                "reason": "方法/性能主锚点：优先形成可执行算法与干预"}
    return {"path": "ANCHOR_NATIVE", "contribution": ANCHOR_CONTRIBUTION.get(kind, ""),
            "reason": f"{kind} 主锚点有独立科研贡献，不强制转成算法",
            "gap": gap}


# ---------------------------------------------------------------------------
# Loop-facing transition
# ---------------------------------------------------------------------------

def transition(state: Dict[str, Any], *, scheduler: Optional[Dict[str, Any]] = None,
               insight: Optional[Dict[str, Any]] = None,
               contract: Optional[Dict[str, Any]] = None,
               minimal_test: Optional[Dict[str, Any]] = None,
               candidates: Optional[Sequence[Dict[str, Any]]] = None,
               gap: Optional[Dict[str, Any]] = None,
               zero_streak: int = 0) -> Dict[str, Any]:
    """One inspectable I2M step for the Loop: readiness → synthesis → contract → test.

    Returns a step dict shaped like `preset_router._loop_step` so the Loop can use it
    without a parallel state machine.  `blocked` is only about I2M's own preconditions;
    the caller's hard gates (integrity/critical attack/invalidation/assurance/budget)
    are decided before this step is consulted.
    """
    readiness = insight_readiness(state, insight or {})
    path = anchor_path(state, readiness=readiness, gap=gap)
    stage = "readiness"
    decision = advance(state, readiness=readiness, contract=contract,
                       minimal_test=minimal_test, zero_streak=zero_streak)
    if path["path"] == "ANCHOR_NATIVE":
        return {"phase": "I2M", "stage": "anchor_native", "step": "Contribution",
                "action": f"按 {path['contribution']} 形成主锚点贡献；"
                          "不把非方法锚点强行转成算法",
                "blocked": False, "hold": False, "i2m": {"readiness": readiness,
                                                         "path": path, "decision": decision}}
    if readiness["verdict"] == VERDICT_NOT_ACTIONABLE:
        stage = "discriminate"
        return {"phase": "I2M", "stage": stage, "step": "Discriminate",
                "action": "先做能改变方法决定的判别实验：" + "、".join(readiness["missing"]),
                "blocked": False, "hold": False,
                "i2m": {"readiness": readiness, "path": path, "decision": decision}}
    if contract is None:
        stage = "synthesis"
        outcome = synthesize_methods(state, readiness, candidates or [])
        action = ("合成 2—3 种有实质差异的方法候选并冻结设计契约"
                  if outcome["status"] != "SYNTHESIZED"
                  else "冻结选定方法的设计契约（R8 preregistration）")
        if candidates and outcome["status"] == "SYNTHESIZED":
            stage = "contract"
        return {"phase": "I2M", "stage": stage, "step": "Synthesize", "action": action,
                "blocked": False, "hold": False,
                "i2m": {"readiness": readiness, "path": path, "synthesis": outcome,
                        "decision": decision}}
    problems = design_contract_errors(state, contract)
    if problems:
        return {"phase": "I2M", "stage": "contract", "step": "HOLD",
                "action": "设计契约未通过校验：" + "；".join(item.message for item in problems[:3]),
                "blocked": True, "hold": True, "hold_reason": "method_contract_invalid",
                "i2m": {"readiness": readiness, "path": path,
                        "diagnostics": [item.as_dict() for item in problems],
                        "decision": decision}}
    if minimal_test is None:
        return {"phase": "I2M", "stage": "minimal_test", "step": "Plan",
                "action": "登记最小干预测试（预注册指标/判据/停止条件 + 公平性核验）",
                "blocked": False, "hold": False,
                "i2m": {"readiness": readiness, "path": path, "decision": decision}}
    return {"phase": "I2M", "stage": "minimal_test", "step": "Intervene",
            "action": "执行最小干预测试（PEIG/AALG/预算门禁不变）",
            "blocked": False, "hold": False,
            "i2m": {"readiness": readiness, "path": path, "decision": decision}}


# ---------------------------------------------------------------------------
# Deriving the I2M inputs from existing state (no new fact source)
# ---------------------------------------------------------------------------

def insight_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Build a provisional insight from fields the state already requires.

    Nothing new is authored: the mechanism comes from `hypotheses[].statement`, the lever
    from `operator`/`intervention_axis`, the falsifier from the required `falsifier`, the
    discriminating test from `uncertainties[].cheapest_discriminating_test`, and the novelty
    boundary from `nearest_prior`/`novelty_source`.  A richer, explicitly authored insight may
    be passed to `insight_readiness` instead.
    """
    hypotheses = [item for item in _items(state, "hypotheses")
                  if item.get("status") in ("active", "candidate", "promising")]
    hypotheses = hypotheses or _items(state, "hypotheses")
    mechanism, mechanism_id, levers, falsifiers, prior = "", "", [], [], []
    for hypothesis in hypotheses:
        if not mechanism_id:
            mechanism = _text(hypothesis.get("statement"))
            mechanism_id = str(hypothesis.get("id") or "")
        for field in ("intervention_axis", "operator", "variable"):
            if _text(hypothesis.get(field)):
                levers.append(_text(hypothesis[field]))
        if _text(hypothesis.get("falsifier")):
            falsifiers.append(_text(hypothesis["falsifier"]))
        if _text(hypothesis.get("nearest_prior")):
            prior.append({"method": _text(hypothesis["nearest_prior"]),
                          "hypothesis": str(hypothesis.get("id") or "")})
    uncertainties = [item for item in _items(state, "uncertainties")
                     if item.get("status") in ("open", "undecidable_recorded")]
    discriminating = [str(item.get("cheapest_discriminating_test")) for item in uncertainties
                      if _text(item.get("cheapest_discriminating_test"))]
    predictions = [{"observation": test, "decision": "按判别结果选择方法或停止"}
                   for test in discriminating[:2]]
    # "necessary comparators exist" means they can be constructed, not that an experiment is
    # already registered: the no-intervention control plus the nearest prior method.
    comparators = ["no_intervention"]
    for item in prior:
        if item["method"] not in comparators:
            comparators.append(item["method"])
    for experiment in _items(state, "experiments"):
        arms = (experiment.get("preregistration") or {}).get("arms")
        for arm in arms if isinstance(arms, list) else []:
            role = _text((arm or {}).get("role"))
            if role and role not in comparators:
                comparators.append(role)
    problem_ref = ""
    for claim in _items(state, "claims"):
        if claim.get("status") in ("ungrounded", "partially-supported"):
            problem_ref = str(claim.get("id") or "")
            break
    novelty = _text(next((item.get("novelty_source") for item in hypotheses
                          if _text(item.get("novelty_source"))), ""))
    return {"problem_ref": problem_ref or "contract",
            "insight_refs": [mechanism_id] if mechanism_id else [],
            "mechanism": mechanism, "intervention_levers": sorted(set(levers)),
            "predictions": predictions, "falsifiers": falsifiers,
            "comparators": comparators,
            "minimal_experiment": {"plan": discriminating[0]} if discriminating else None,
            "prior_art": prior, "novelty_boundary": novelty}


def _method_contract_in_state(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for experiment in _items(state, "experiments"):
        preregistration = experiment.get("preregistration")
        if isinstance(preregistration, dict) and isinstance(
                preregistration.get("method_contract"), dict):
            return preregistration["method_contract"]
    return None


def signal_snapshot(state: Dict[str, Any], scheduler: Optional[Dict[str, Any]] = None,
                   insight: Optional[Dict[str, Any]] = None,
                   gap: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Loop-visible I2M state: readiness, contribution path, gap and the next decision."""
    readiness = insight_readiness(state, insight if insight is not None
                                  else insight_from_state(state))
    path = anchor_path(state, readiness=readiness, gap=gap)
    step = loop_step(state, scheduler, insight=insight, gap=gap)
    return {"readiness": readiness["verdict"], "mechanism_status": readiness["mechanism_status"],
            "missing": readiness["missing"], "path": path["path"],
            "contribution": path["contribution"], "anchor_kind": anchor_kind(state),
            "gap": anchor_gap(state, gap),
            "next_step": (step or {}).get("step"), "next_action": (step or {}).get("action"),
            "trigger": (step or {}).get("trigger"),
            "note": "I2M 只在硬门禁之后生效；它不改变完整性/攻击/失效/预算的优先权。"}


def loop_step(state: Dict[str, Any], scheduler: Optional[Dict[str, Any]] = None,
              insight: Optional[Dict[str, Any]] = None,
              gap: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """The I2M step the Loop should take, or `None` when method work is not indicated.

    Called by `preset_router._loop_step` *after* every hard gate (integrity, critical attack,
    invalidation propagation, Assurance, budget) has already had its say, so I2M can never
    outrank them.  Method work is indicated when diagnosis has stopped paying off, or when a
    frozen method contract already exists and development should continue.
    """
    scheduler = scheduler if isinstance(scheduler, dict) else {}
    contract = _method_contract_in_state(state)
    # The Switch is the existing authority for "diagnosis stopped paying off"; only a missing
    # module is tolerated here, never a real error from it.
    try:
        import prediction_compare as pc
    except ImportError:                              # pragma: no cover - module is shipped
        pc = None
    if pc is None:
        streak, switch = 0, None
    else:
        streak = pc.trailing_zero_streak(scheduler)
        switch = pc.diagnosis_switch(state, [], scheduler).get("action")
    stagnant = streak >= 2 or (switch is not None and switch != "CONTINUE_ATTRIBUTION")
    if contract is None and not stagnant:
        return None                                  # healthy diagnosis: do not hijack the queue
    step = transition(state, scheduler=scheduler,
                      insight=insight if insight is not None else insight_from_state(state),
                      contract=contract, minimal_test=None, gap=gap, zero_streak=streak)
    step["trigger"] = ("method_contract_present" if contract is not None
                       else f"diagnosis_stagnant(zero_streak={streak}, switch={switch})")
    return step


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest_state() -> Dict[str, Any]:
    return {
        "_schema": "research-idea-pipeline/research-state@1", "state_version": 7,
        "contract": {"goal": "提升长尾检索的召回", "primary_anchor": "performance",
                     "constraints": [], "resources": {}, "out_of_scope": [],
                     "target_metric": "recall@10"},
        "claims": [{"id": "C1", "status": "partially-supported", "statement": "s"}],
        "evidence": [{"id": "E1", "epistemic_status": "Observed", "validity": {"status": "valid"},
                      "supports": ["H1"]}],
        "hypotheses": [{"id": "H1", "status": "active", "statement": "长尾被头部主导",
                        "intervention_axis": "loss_reweighting", "operator": "reframe"}],
        "experiments": [], "literature": [], "failures": [], "uncertainties": [],
        "assurance": [], "repairs": [], "narrative_view": {}, "reviews": [],
    }


def _selftest_insight() -> Dict[str, Any]:
    return {"problem_ref": "C1",
            "insight_refs": ["H1"],
            "mechanism": "头部样本主导梯度方向",
            "intervention_levers": ["loss_reweighting"],
            "predictions": [{"observation": "长尾 recall 上升", "decision": "继续"}],
            "falsifiers": ["长尾 recall 不升"],
            "comparators": ["no_intervention", "nearest_prior"],
            "minimal_experiment": {"plan": "单数据集小规模干预"},
            "prior_art": [{"method": "focal loss"}],
            "novelty_boundary": "与 focal loss 的差异在样本层级重加权",
            "target_metric": "recall@10"}


def _selftest_contract(state: Dict[str, Any]) -> Dict[str, Any]:
    return {"schema": SCHEMA_CONTRACT, "problem_ref": "C1", "insight_refs": ["H1"],
            "method_hypothesis_ref": "H1",
            "intervention": {"kind": "objective", "change": "长尾感知重加权目标"},
            "mathematical_formulation": "L = Σ w_i l_i, w_i = f(freq_i)",
            "algorithm_steps": ["统计频次", "构造权重", "训练"],
            "nearest_prior": "focal loss", "distinctive_mechanism": "按样本层级而非类别重加权",
            "predictions": [{"observation": "长尾 recall 上升"}], "falsifiers": ["不升"],
            "minimal_test": {"plan": "小规模"}, "comparators": ["no_intervention", "focal_loss"],
            "success_criteria": ["recall@10 +2pt"], "stop_rules": ["无提升则停止"],
            "evidence_status": VERDICT_HYPOTHESIS, "rules_digest": "sha256:rules"}


def selftest() -> int:
    checks: List[Tuple[str, bool]] = []
    state = _selftest_state()
    insight = _selftest_insight()

    readiness = insight_readiness(state, insight)
    checks.append(("readiness 可用于方法设计", readiness["verdict"] == VERDICT_VERIFIED))
    checks.append(("readiness 不把假设当证实",
                   insight_readiness(state, dict(insight, insight_refs=["H9"]))["verdict"]
                   == VERDICT_NOT_ACTIONABLE))
    unverified = dict(insight, mechanism_status="VERIFIED")
    checks.append(("自称已验证但无证据时被记录",
                   "I2M14" in _rules(insight_readiness(
                       {**state, "evidence": []}, unverified)["diagnostics"])))

    candidates = [
        {"candidate_id": "M1", "intervention": {"kind": "objective"},
         "how_it_addresses": "a", "mechanism_basis": "b", "structural_difference": "c",
         "minimal_implementation_complexity": "low", "expected_benefit": "d",
         "resource_cost": "low", "failure_boundary": ["f"],
         "falsifiable_predictions": ["p"], "distinctive_mechanism": "alpha",
         "mathematical_formulation": "L1"},
        {"candidate_id": "M2", "intervention": {"kind": "architecture"},
         "how_it_addresses": "a", "mechanism_basis": "b", "structural_difference": "c",
         "minimal_implementation_complexity": "low", "expected_benefit": "d",
         "resource_cost": "low", "failure_boundary": ["f"],
         "falsifiable_predictions": ["p"], "distinctive_mechanism": "beta",
         "mathematical_formulation": "L2"},
    ]
    synthesis = synthesize_methods(state, readiness, candidates)
    checks.append(("两种实质不同的方法可合成", synthesis["status"] == "SYNTHESIZED"))
    duplicate = [dict(candidates[0], candidate_id="M3"), candidates[0]]
    checks.append(("同构方法被拒绝",
                   "I2M23" in _rules(
                       synthesize_methods(state, readiness, duplicate)["diagnostics"])))
    hyper = [dict(candidates[0], intervention={"kind": "hyperparameter"}), candidates[1]]
    checks.append(("纯超参干预被拒绝",
                   "I2M20" in _rules(
                       synthesize_methods(state, readiness, hyper)["diagnostics"])))

    contract = _selftest_contract(state)
    checks.append(("合法设计契约通过", not design_contract_errors(state, contract)))
    checks.append(("缺数学定义被拒绝",
                   "I2M30" in _rules(design_contract_errors(
                       state, dict(contract, mathematical_formulation="")))))
    checks.append(("无证据却声称 supported 被拒绝",
                   "I2M39" in _rules(design_contract_errors(
                       {**state, "evidence": []},
                       dict(contract, evidence_status="supported")))))
    checks.append(("引用不可解析被拒绝",
                   "I2M27" in _rules(design_contract_errors(
                       state, dict(contract, insight_refs=["H404"])))))

    plan = {"implementation_change": "长尾重加权层", "expected_delta": "recall@10 上升",
            "comparators": ["no_intervention", "focal_loss"], "primary_metrics": ["recall@10"],
            "decision_criteria": ["+2pt"], "stop_rules": ["无提升停止"],
            "fairness": {"capacity": True, "intervention_strength": True,
                         "optimization": True, "compute_budget": True},
            "preregistration_digest": "sha256:pre"}
    checks.append(("最小干预测试计划通过", not minimal_test_errors(state, plan)))
    checks.append(("未核验公平性被拒绝",
                   "I2M49" in _rules(minimal_test_errors(
                       state, dict(plan, fairness={"capacity": True})))))
    checks.append(("门禁未通过时不得用 GPU",
                   "I2M52" in _rules(minimal_test_errors(
                       state, plan, gate={"status": "HOLD", "errors": ["BUDGET"]}))))
    checks.append(("事后改预注册被拒绝",
                   "I2M55" in _rules(test_failure_errors(
                       state, {"classification": FAILURE_INEFFECTIVE,
                               "preregistration_digest": "sha256:edited"},
                       frozen_digest="sha256:pre"))))

    before = dict(state["hypotheses"][0], method={"intervention": "a"})
    after = dict(state["hypotheses"][0], method={"intervention": "b"})
    checks.append(("无新证据不算进展", not method_progress(
        state, before=before, after=after, previous_evidence=["E1"])["progress"]))
    grown = {**state, "evidence": state["evidence"] + [
        {"id": "E2", "epistemic_status": "Observed", "validity": {"status": "valid"}}]}
    checks.append(("方法变化 + 新证据才算进展", method_progress(
        grown, before=before, after=after, previous_evidence=["E1"])["progress"]))
    checks.append(("改写解释不算进展", not method_progress(
        grown, before=before, after=before, previous_evidence=["E1"])["progress"]))

    checks.append(("方法锚点走合成路径",
                   anchor_path(state, readiness=readiness)["path"] == "METHOD_SYNTHESIS"))
    theory = {**state, "contract": dict(state["contract"], primary_anchor="theory")}
    checks.append(("理论锚点不强制转成算法",
                   anchor_path(theory, readiness=readiness)["path"] == "ANCHOR_NATIVE"))
    checks.append(("锚点资格由证据决定",
                   anchor_eligibility(state)["verdict"] == CONDITIONAL))
    checks.append(("supporting 不可证伪则拒绝",
                   "I2M59" in _rules(anchor_role_errors(
                       {"anchor_role": "supporting", "serves": "s",
                        "serves_evidence": "T003/K1"}))))
    checks.append(("无用户授权不得改锚点",
                   "I2M61" in _rules(anchor_change_errors(
                       {"new_anchor": "theory", "reason": "r", "evidence": "e"}))))

    step = transition(state, insight=insight, candidates=candidates)
    checks.append(("transition 在可合成时给出综合步骤", step["step"] == "Synthesize"))
    step2 = transition({**state, "contract": dict(state["contract"], primary_anchor="negative")},
                       insight=insight)
    checks.append(("非方法锚点给出 anchor-native 步骤", step2["stage"] == "anchor_native"))

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(("  ok   " if ok else "  FAIL ") + name)
    if failed:
        print("selftest FAILED: " + "; ".join(failed))
        return 1
    print(f"selftest OK ({len(checks)} checks)")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Insight-to-Method Transition (I2M)")
    parser.add_argument("--selftest", action="store_true", help="run the module self-test")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.selftest:
        return selftest()
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
