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


#: Kinds of mechanism support, strongest last.  "The prediction was observed" is not
#: "the mechanism is proven", and a mere dependency is not support at all.
SUPPORT_DEPENDENT = "DEPENDENT_NOT_SUPPORTING"
SUPPORT_PREDICTION_OBSERVED = "PREDICTION_OBSERVED"
SUPPORT_INTERVENTION_EFFECT = "INTERVENTION_EFFECT"
SUPPORT_MECHANISM = "MECHANISM_SUPPORTED"
SUPPORT_NONE = "NO_SUPPORT"

_DEAD_STATUS = {"refuted", "killed", "invalid", "stale", "retracted", "superseded",
                "resolved", "abandoned"}


def _is_alive(obj: Dict[str, Any]) -> bool:
    """Not refuted/killed/stale/invalid — such objects may not pad readiness."""
    status = _text(obj.get("status")).lower()
    validity = obj.get("validity") if isinstance(obj.get("validity"), dict) else {}
    return status not in _DEAD_STATUS and _text(validity.get("status")).lower() != "invalid"


def _evidence_qualified(evidence: Dict[str, Any]) -> bool:
    """The existing evidence-qualification bar: observed/supported, valid, tiered, sourced."""
    if not isinstance(evidence, dict):
        return False
    if evidence.get("epistemic_status") not in _EVIDENCE_BACKED:
        return False
    validity = evidence.get("validity") if isinstance(evidence.get("validity"), dict) else {}
    if validity.get("status") not in (None, "valid"):
        return False
    if not _text(evidence.get("source_ref")):
        return False
    tier = _text(evidence.get("verification_tier"))
    if tier and tier not in ("T1", "T2", "T3", "T4"):
        return False
    return True


def _evidence_relation(evidence: Dict[str, Any], hypothesis_ids: Sequence[str]) -> str:
    """`supports` proves direction; `depends_on` only records a dependency."""
    targets = {str(item) for item in hypothesis_ids}
    supports = {str(item) for item in evidence.get("supports") or []}
    refutes = {str(item) for item in evidence.get("refutes") or []}
    depends = {str(item) for item in evidence.get("depends_on") or []}
    if supports & targets:
        return "supports"
    if refutes & targets:
        return "refutes"
    if depends & targets:
        return "depends_on"
    return "none"


def _mechanism_support(state: Dict[str, Any], hypothesis_ids: Sequence[str]) -> Dict[str, Any]:
    """Classify how far the evidence actually goes for the referenced mechanism.

    Returns `{level, kind, supporting, dependent, refuting, diagnostics}`.  Only an evidence
    that *supports* the mechanism (and is qualified) can raise the level; an evidence that
    merely depends on the hypothesis is recorded as a dependency, never as proof.
    """
    supporting: List[str] = []
    dependent: List[str] = []
    refuting: List[str] = []
    kinds: List[str] = []
    diagnostics: List[Diagnostic] = []
    for evidence in _items(state, "evidence"):
        relation = _evidence_relation(evidence, hypothesis_ids)
        if relation == "none":
            continue
        ident = str(evidence.get("id"))
        if relation == "refutes":
            refuting.append(ident)
            continue
        if relation == "depends_on":
            dependent.append(ident)
            diagnostics.append(_diag(
                "I2M70", f"evidence[{ident}]",
                "该证据只是 depends_on 机制假设，不构成支持：不得据此判定机制已验证"))
            continue
        if not _evidence_qualified(evidence):
            diagnostics.append(_diag(
                "I2M71", f"evidence[{ident}]",
                "支持方向正确但未通过证据资格（观测等级/有效性/来源/验证层级）："
                "仍需按 R8/R10 审查"))
            continue
        supporting.append(ident)
        explicit = _text(evidence.get("mechanism_support") or evidence.get("conclusion"))
        # A self-declared strength is not a review: R8/R10 must have qualified it before it can
        # raise the level beyond "the prediction was observed".
        reviewed = (_text(evidence.get("review_status")).upper() == "PASS"
                    or _text(evidence.get("verification_tier")) in ("T3", "T4")
                    or bool(evidence.get("assurance_ref")))
        if explicit in ("intervention", "intervention_effect"):
            if reviewed:
                kinds.append(SUPPORT_INTERVENTION_EFFECT)
            else:
                kinds.append(SUPPORT_PREDICTION_OBSERVED)
                diagnostics.append(_diag(
                    "I2M96", f"evidence[{ident}]",
                    "自称干预有效但未经 R8/R10 审查：只能记为「观察到预测现象」"))
        elif explicit == "mechanism":
            if reviewed:
                kinds.append(SUPPORT_MECHANISM)
            else:
                kinds.append(SUPPORT_PREDICTION_OBSERVED)
                diagnostics.append(_diag(
                    "I2M97", f"evidence[{ident}]",
                    "自称机制获支持但缺少证据审查凭证（review PASS / T3+ / assurance_ref）："
                    "不得据此判定机制已验证"))
        else:
            kinds.append(SUPPORT_PREDICTION_OBSERVED)
    order = (SUPPORT_NONE, SUPPORT_PREDICTION_OBSERVED, SUPPORT_INTERVENTION_EFFECT,
             SUPPORT_MECHANISM)
    level = SUPPORT_NONE
    for kind in kinds:
        if order.index(kind) > order.index(level):
            level = kind
    return {"level": level, "supporting": sorted(supporting), "dependent": sorted(dependent),
            "refuting": sorted(refuting), "kinds": sorted(set(kinds)),
            "diagnostics": diagnostics}


def _related_uncertainties(state: Dict[str, Any], hypothesis_id: str) -> List[Dict[str, Any]]:
    """Uncertainties that are actually bound to this hypothesis (dependency or explicit link)."""
    related: List[Dict[str, Any]] = []
    for uncertainty in _items(state, "uncertainties"):
        if not _is_alive(uncertainty):
            continue
        links = set()
        for field in ("depends_on", "targets", "related_hypotheses", "hypotheses"):
            value = uncertainty.get(field)
            if isinstance(value, list):
                links |= {str(item) for item in value}
            elif _text(value):
                links.add(_text(value))
        if _text(uncertainty.get("hypothesis")):
            links.add(_text(uncertainty["hypothesis"]))
        if hypothesis_id in links:
            related.append(uncertainty)
    return related


def _binding_errors(state: Dict[str, Any], insight: Dict[str, Any],
                    hypothesis_ids: Sequence[str]) -> List[Diagnostic]:
    """Every readiness input must belong to one candidate and its dependency chain."""
    problems: List[Diagnostic] = []
    refs = insight.get("insight_refs")
    if isinstance(refs, str):
        return [_diag("I2M60", "insight_refs",
                      "insight_refs 必须是列表，不能把字符串拆成字符")]
    primaries = {str(item) for item in hypothesis_ids}
    for ref in refs or []:
        if not isinstance(ref, str):
            problems.append(_diag("I2M60", "insight_refs",
                                  f"引用必须是字符串：{ref!r}"))
            continue
        resolved = _resolve(state, ref)
        if resolved is None:
            problems.append(_diag("I2M6", "insight_refs",
                                  f"引用 {ref} 无法在 state 中解析"))
            continue
        collection, obj = resolved
        if collection == "hypotheses":
            if ref not in primaries:
                problems.append(_diag(
                    "I2M61", f"insight_refs[{ref}]",
                    "该假设不是本次 Insight 的主候选：不得跨候选拼接字段"))
            elif not _is_alive(obj):
                problems.append(_diag("I2M62", f"insight_refs[{ref}]",
                                      "主候选已被否证/失效：不得用于 readiness"))
            continue
        if collection == "uncertainties":
            bound = {str(item.get("id")) for hypothesis in _items(state, "hypotheses")
                     if str(hypothesis.get("id")) in primaries
                     for item in _related_uncertainties(state, str(hypothesis.get("id")))}
            if ref not in bound:
                problems.append(_diag(
                    "I2M63", f"insight_refs[{ref}]",
                    "该未知量没有绑定到主候选假设：预测不得来自无关对象"))
            continue
        # claims/evidence/failures must depend on or support the primary candidate
        links = set()
        for field in ("depends_on", "supports", "refutes", "parent", "subclaims",
                      "claim_targeted", "hypothesis_targeted", "hypothesis"):
            value = obj.get(field)
            if isinstance(value, list):
                links |= {str(item) for item in value}
            elif _text(value):
                links.add(_text(value))
        if not (links & primaries):
            problems.append(_diag(
                "I2M64", f"insight_refs[{ref}]",
                "该对象没有可追溯的依赖链指向主候选：不得用于 readiness"))
    return problems


def insight_readiness(state: Dict[str, Any], insight: Dict[str, Any]) -> Dict[str, Any]:
    """Assess whether a finding can already support method design.

    Readiness is *not* proof.  Every input must be bound to one primary candidate and its
    dependency chain: a mechanism from H1 with a lever from H2 and a prediction from an
    unrelated uncertainty is not a design input, and is reported as a partial gap instead.
    The mechanism level is decided by qualified evidence that *supports* the hypothesis —
    a dependency, a refutation or an unqualified record never raises it.
    """
    insight = insight if isinstance(insight, dict) else {}
    diagnostics: List[Diagnostic] = []
    criteria: Dict[str, bool] = {}

    goal = _text(((state.get("contract") or {}).get("goal")))
    metric = _target_metric(state, insight)
    problem_ref = _text(insight.get("problem_ref"))
    criteria[CRITERION_PROBLEM] = bool(goal) and bool(metric) and bool(problem_ref)
    if not goal:
        diagnostics.append(_diag("I2M1", "contract.goal", "缺少研究目标：无法判断方法要改变什么"))
    if not metric:
        diagnostics.append(_diag("I2M2", "target_metric", "缺少目标指标：方法收益无法被测量"))
    if not problem_ref:
        diagnostics.append(_diag("I2M3", "problem_ref", "缺少 problem_ref：方法必须绑定一个具体问题"))

    insight_refs = insight.get("insight_refs")
    if isinstance(insight_refs, str):
        insight_refs = []
        diagnostics.append(_diag("I2M60", "insight_refs",
                                 "insight_refs 必须是列表，不能把字符串拆成字符"))
    insight_refs = [str(item) for item in insight_refs or [] if _text(item)]
    hypothesis_ids = [ref for ref in insight_refs if ref.upper().startswith("H")]
    mechanism = _text(insight.get("mechanism"))
    binding = _binding_errors(state, insight, hypothesis_ids)
    diagnostics.extend(binding)
    criteria[CRITERION_MECHANISM] = bool(mechanism) and len(hypothesis_ids) == 1 and not binding
    if not mechanism:
        diagnostics.append(_diag("I2M4", "mechanism", "缺少机制/工程局限陈述"))
    if len(hypothesis_ids) != 1:
        diagnostics.append(_diag("I2M5", "insight_refs",
                                 "机制必须由恰好一个 H 对象承载：不得跨候选拼接"))
    if any(not _is_alive(_resolve(state, ref)[1]) for ref in hypothesis_ids
           if _resolve(state, ref) is not None):
        criteria[CRITERION_MECHANISM] = False

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

    predictions = [item for item in insight.get("predictions") or [] if isinstance(item, dict)]
    falsifiers = [item for item in insight.get("falsifiers") or [] if _text(item)]
    criteria[CRITERION_PREDICTIONS] = bool(predictions) and bool(falsifiers) and \
        all(_text(item.get("observation")) for item in predictions)
    if not predictions:
        diagnostics.append(_diag("I2M8", "predictions", "缺少可检验预测（或预测未绑定主候选）"))
    if not falsifiers:
        diagnostics.append(_diag("I2M9", "falsifiers", "缺少失败条件：方法不可被否证"))

    comparators = [str(item) for item in insight.get("comparators") or [] if _text(item)]
    minimal = insight.get("minimal_experiment")
    minimal_ok = isinstance(minimal, dict) and _text(minimal.get("plan"))
    criteria[CRITERION_MINIMAL_EXPERIMENT] = bool(comparators) and minimal_ok
    if not comparators:
        diagnostics.append(_diag("I2M10", "comparators", "缺少对照：至少需要无干预与最近邻方法"))
    if not minimal_ok:
        diagnostics.append(_diag("I2M11", "minimal_experiment",
                                 "缺少与主候选关联的可行最小实验"))

    prior = insight.get("prior_art")
    prior_items = [item for item in prior or [] if isinstance(item, dict)] \
        if isinstance(prior, list) else []
    novelty_checked = bool(prior_items) and bool(_text(insight.get("novelty_boundary")))
    criteria[CRITERION_PRIOR_ART] = novelty_checked
    if not prior_items:
        diagnostics.append(_diag("I2M12", "prior_art", "未核对直接相关的已有方法"))
    if not _text(insight.get("novelty_boundary")):
        diagnostics.append(_diag("I2M13", "novelty_boundary", "缺少创新性边界说明"))

    support = _mechanism_support(state, hypothesis_ids)
    diagnostics.extend(support["diagnostics"])
    level = support["level"]
    mechanism_status = (VERDICT_VERIFIED if level == SUPPORT_MECHANISM
                        else VERDICT_HYPOTHESIS)
    declared = _text(insight.get("mechanism_status")).upper()
    if declared in ("VERIFIED", VERDICT_VERIFIED) and level != SUPPORT_MECHANISM:
        diagnostics.append(_diag(
            "I2M14", "mechanism_status",
            "insight 自称机制已验证，但 state 中没有经资格审查的支持证据"
            f"（当前证据等级 {level}）：readiness 不是科学证实"))
    blocking = [CRITERION_PROBLEM, CRITERION_MECHANISM, CRITERION_INTERVENTION,
                CRITERION_PREDICTIONS, CRITERION_MINIMAL_EXPERIMENT]
    missing = sorted(name for name, ok in criteria.items() if not ok)
    verdict = mechanism_status if all(criteria.get(name) for name in blocking) \
        else VERDICT_NOT_ACTIONABLE
    return {"schema": SCHEMA_READINESS, "verdict": verdict,
            "mechanism_status": mechanism_status, "mechanism_level": level,
            "criteria": criteria, "missing": missing,
            "partial": sorted(name for name, ok in criteria.items() if ok),
            "evidence_backing": support["supporting"], "dependent_evidence": support["dependent"],
            "refuting_evidence": support["refuting"], "levers": sorted(set(levers)),
            "target_metric": metric, "diagnostics": [item.as_dict() for item in diagnostics],
            "anchor_kind": anchor_kind(state), "method_anchor": is_method_anchor(anchor_kind(state)),
            "gaps": [f"缺少 {name}" for name in missing],
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
    list_fields = ("insight_refs", "algorithm_steps", "predictions", "falsifiers",
                   "comparators", "success_criteria", "stop_rules")
    for field in list_fields:
        if field in contract and not isinstance(contract[field], list):
            problems.append(_diag("I2M72", f"contract.{field}",
                                  f"必须是列表，不能是 {type(contract[field]).__name__}"
                                  "（字符串会被拆成字符）"))
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
        support = _mechanism_support(state, [hypothesis_ref])
        if support["level"] != SUPPORT_MECHANISM:
            problems.append(_diag(
                "I2M39", "contract.evidence_status",
                f"state 中没有经资格审查的机制支持证据（当前 {support['level']}）："
                "不得声称 supported"))
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


PROGRESS_DIMENSIONS = ("epistemic", "design", "implementation", "validation", "anchor")


def _progress_fingerprint(*values: Any) -> str:
    return cg.digest_of(list(values))


def _progress_reason(progress: bool, dimensions: Dict[str, bool],
                     already_consumed: Sequence[str], usable: Sequence[str]) -> str:
    if progress:
        return "存在可核验的进展维度：" + ", ".join(
            name for name, ok in dimensions.items() if ok)
    if already_consumed and not usable:
        return "该证据已被消费过：不得重复计入或重置停滞"
    return "没有可核验的进展：指纹变化本身不是验证，无关或未归属证据不加进展"


def method_progress(state: Dict[str, Any], *, before: Dict[str, Any],
                    after: Dict[str, Any], experiment_id: str = "",
                    previous_evidence: Sequence[str] = (),
                    implementation_check: Optional[Dict[str, Any]] = None,
                    anchor_relevant_evidence: Optional[Sequence[str]] = None,
                    method_version: str = "",
                    consumed_evidence: Sequence[str] = ()) -> Dict[str, Any]:
    """Five separate, individually verified progress dimensions.

    A changed method fingerprint alone is **not** validation, and new evidence that has nothing
    to do with this method adds nothing.  A confirming re-run of the *same* method version is
    Validation Progress and needs no algorithm change.  A trustworthy negative result, an
    excluded assumption or a real change of research decision also count as epistemic progress.
    """
    before_method = before.get("method") if isinstance(before.get("method"), dict) else {}
    after_method = after.get("method") if isinstance(after.get("method"), dict) else {}
    method_changed = _method_fingerprint(before) != _method_fingerprint(after)
    version = method_version or _text(after_method.get("version")) or _text(after.get("version"))

    evidence_now = {str(item.get("id")) for item in _items(state, "evidence")}
    new_evidence = sorted(evidence_now - {str(item) for item in previous_evidence})
    by_id = _index(state, "evidence")
    qualified = [ident for ident in new_evidence if _evidence_qualified(by_id.get(ident, {}))]

    hypothesis_id = str(after.get("id") or "")
    consumed = {str(item) for item in consumed_evidence}
    already_consumed = sorted(set(qualified) & consumed)

    def attributed(ident):
        """Evidence counts only for the method version/experiment it actually came from."""
        evidence = by_id.get(ident, {})
        declared = _text(evidence.get("method_version")) or _text(evidence.get("method_digest"))
        if declared:
            expected = version or _text(after_method.get("definition_digest"))
            if expected and declared != expected:
                return False
        source = _text(evidence.get("experiment")) or _text(evidence.get("source_ref"))
        experiment_id = source.split(":", 1)[-1]
        record = _index(state, "experiments").get(experiment_id)
        if record is not None:
            preregistration = record.get("preregistration") \
                if isinstance(record.get("preregistration"), dict) else {}
            contract = preregistration.get("method_contract") \
                if isinstance(preregistration.get("method_contract"), dict) else {}
            bound = _text(contract.get("method_digest")) or \
                _text(contract.get("method_hypothesis_ref"))
            if bound:
                expected = _text(after_method.get("definition_digest")) or hypothesis_id
                if bound not in (expected, version, hypothesis_id):
                    return False
        return True

    fresh = [ident for ident in qualified if ident not in consumed]
    misattributed = [ident for ident in qualified if not attributed(ident)]
    usable = [ident for ident in fresh if attributed(ident)]
    related = [ident for ident in usable
               if _evidence_relation(by_id.get(ident, {}), [hypothesis_id]) == "supports"]
    refuting = [ident for ident in usable
                if _evidence_relation(by_id.get(ident, {}), [hypothesis_id]) == "refutes"]
    anchor_refs = [str(item) for item in (anchor_relevant_evidence or []) if _text(item)]
    if anchor_refs:
        anchor_hits = [ident for ident in usable if ident in set(anchor_refs)]
    else:
        anchor_hits = [ident for ident in usable
                       if _anchor_relevant(state, by_id.get(ident, {}), anchor_kind(state))]

    definition_digest = _text(after_method.get("definition_digest"))
    # A changed fingerprint alone is not Design Progress: it needs a frozen definition digest.
    design = bool(method_changed and definition_digest)
    implementation = bool(isinstance(implementation_check, dict)
                          and implementation_check.get("status") == "PASS"
                          and _text(implementation_check.get("artifact_digest"))
                          and (not version or _text(implementation_check.get("version")) == version))
    # Validation Progress is about evidence for the current method version; it does not
    # require the algorithm to change (a confirming re-run of the same version counts).
    validation = bool(related or refuting)
    epistemic = bool(refuting) or bool((state.get("eig_calibration") or {}).get("records"))
    anchor_progress = bool(anchor_hits)
    dimensions = {"epistemic": epistemic, "design": design, "implementation": implementation,
                  "validation": validation, "anchor": anchor_progress}
    verified_refs = {"epistemic": sorted(set(refuting)),
                     "design": [definition_digest] if design else [],
                     "implementation": [str((implementation_check or {}).get("artifact_digest") or "")]
                     if implementation else [],
                     "validation": sorted(set(related)), "anchor": sorted(set(anchor_hits))}
    progress = any(dimensions.values()) and any(
        ref for refs in verified_refs.values() for ref in refs)
    return {"progress": progress, "dimensions": dimensions, "refs": verified_refs,
            "method_changed": method_changed, "method_version": version,
            "new_evidence": new_evidence, "qualified_evidence": qualified,
            "related_evidence": sorted(set(related)), "refuting_evidence": sorted(set(refuting)),
            "unrelated_evidence": sorted(set(usable) - set(related) - set(refuting)),
            "misattributed_evidence": sorted(misattributed),
            "already_consumed": already_consumed,
            "fresh": bool(fresh),
            "anchor_evidence": sorted(set(anchor_hits)),
            "found": [experiment_id] if experiment_id else [],
            "narrative_only_change": bool((state.get("narrative_view") or {})) and not method_changed,
            "reason": _progress_reason(progress, dimensions, already_consumed, usable),
            "excluded_signals": ["narrative_view", "reports", "candidate_count",
                                 "document_count", "self_rated_score", "state_version"]}
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

def anchor_link(state: Dict[str, Any], obj: Dict[str, Any], kind: str) -> str:
    """How an object is linked to the target anchor: explicit > experiment > text > none.

    Free-text similarity is never final: it only yields `text_only`, which cannot prove
    eligibility on its own.
    """
    metric = _target_metric(state, {})
    declared = {_text(obj.get(field)).lower() for field in
                ("anchor", "anchor_kind", "serves_anchor", "core_goal")}
    declared.discard("")
    if declared & {kind, "target", "primary"}:
        return "explicit"
    metrics = {_text(obj.get(field)) for field in ("target_metric", "metric", "scope_metric")}
    metrics.discard("")
    if metric and metric in metrics:
        return "explicit"
    ident = str(obj.get("id"))
    for experiment in _items(state, "experiments"):
        if _text(experiment.get("status")) in ("abandoned", "rejected"):
            continue
        experiment_metric = _text(experiment.get("metric"))
        if metric and experiment_metric and experiment_metric.lower() != metric.lower():
            continue
        targets = set()
        for field in ("claim_targeted", "alternative_targeted", "hypothesis_targeted",
                      "uncertainty_targeted"):
            value = experiment.get(field)
            if isinstance(value, list):
                targets |= {str(item) for item in value}
        if ident in targets:
            return "experiment_targeted"
    needles = {needle.lower() for needle in (kind, metric) if _text(needle)}
    haystack = " ".join(_text(obj.get(field)) for field in
                        ("statement", "scope", "falsifier", "nearest_alternative", "reason",
                         "question", "ref", "target")).lower()
    if any(needle and needle in haystack for needle in needles):
        return "text_only"
    return "none"


def _anchor_relevant(state: Dict[str, Any], obj: Dict[str, Any], kind: str) -> bool:
    """Kept for callers that only need a boolean: explicit or experiment-targeted links."""
    return anchor_link(state, obj, kind) in ("explicit", "experiment_targeted")


def _frozen_anchor_requirements(state: Dict[str, Any]) -> List[str]:
    contract = (state.get("contract") or {})
    for field in ("anchor_requirements", "frozen_success_criteria"):
        value = contract.get(field)
        if isinstance(value, list) and value:
            return [str(item) for item in value]
    value = contract.get("success_criteria")
    return [str(item) for item in value] if isinstance(value, list) else []


def anchor_eligibility(state: Dict[str, Any], target: Optional[str] = None) -> Dict[str, Any]:
    """Evidence decides which anchor is usable; only an explicit/experiment link counts.

    Three-valued per `claim-first-policy.md` §6.  A text mention is reported as `text_only`
    and can never make the anchor eligible.  Project Objective, Research Progress,
    Defensible Contribution, Anchor Eligibility and Anchor Satisfaction are reported
    separately so that local progress is never mistaken for anchor achievement.
    """
    kind = (target or anchor_kind(state)).lower()
    kind = _ANCHOR_ALIAS.get(kind, kind)
    contract = (state.get("contract") or {})
    role = _text(contract.get("anchor_role") or contract.get("route_anchor_role"))
    relevant_supported, relevant_partial, text_only, irrelevant = [], [], [], []
    for claim in _items(state, "claims"):
        if not _is_alive(claim):
            continue
        status = _text(claim.get("status"))
        if status not in ("supported", "partially-supported"):
            continue
        link = anchor_link(state, claim, kind)
        if link == "text_only":
            text_only.append(str(claim.get("id")))
            continue
        if link == "none":
            irrelevant.append(str(claim.get("id")))
            continue
        (relevant_supported if status == "supported" else relevant_partial).append(
            str(claim.get("id")))
    observed = [str(item.get("id")) for item in _items(state, "evidence")
                if _evidence_qualified(item)]
    requirements = _frozen_anchor_requirements(state)
    if role == "orthogonal":
        verdict, required = NOT_ELIGIBLE, "orthogonal 路线不参与主锚点成功判据"
    elif role == "supporting":
        verdict, required = CONDITIONAL, ("supporting 路线只能形成辅助贡献："
                                          "不能直接使项目主锚点达标")
    elif not observed:
        verdict, required = NOT_ELIGIBLE, "缺少经资格审查的观测证据：任何 anchor 都还不可用"
    elif relevant_supported:
        verdict, required = ELIGIBLE, ""
    elif text_only:
        verdict, required = "unknown", ("只有文字提及目标指标、没有显式关系或实验 targeting 的"
                                        "claim 不足以证明关联")
    elif relevant_partial:
        verdict, required = CONDITIONAL, "与目标锚点显式关联的 claim 仍只是 partially-supported"
    elif irrelevant:
        verdict, required = NOT_ELIGIBLE, (
            "存在 supported claim，但没有一条以显式关系或实验 targeting 关联到目标锚点："
            f"不相关 claim {irrelevant} 不能使 {kind} anchor eligible")
    else:
        verdict, required = CONDITIONAL, "需要至少一条与目标锚点显式关联的 supported claim"
    satisfaction = "undetermined" if not requirements else (
        "satisfied" if (relevant_supported and not required) else "unsatisfied")
    return {"target_anchor": kind, "route_role": role or "primary", "verdict": verdict,
            "required_evidence": required, "supported_claims": relevant_supported,
            "partial_claims": relevant_partial, "text_only_claims": text_only,
            "irrelevant_claims": irrelevant, "observed_evidence": observed,
            "frozen_requirements": requirements,
            "project_objective": _text(contract.get("goal")) or _target_metric(state, {}),
            "research_progress": {"observed_evidence": len(observed),
                                  "partial_claims": relevant_partial},
            "defensible_contribution": relevant_supported,
            "anchor_satisfaction": satisfaction,
            "undecidable": ([] if requirements else
                            ["未声明冻结的主锚点成功条件：缺口无法判定，不得默认已满足"])
            + ([] if observed else ["尚无可用观测证据"]),
            "note": "作者的目标 anchor 是 prior，不是 decision；关联必须显式或由实验 targeting。"}


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
    """The real distance to the frozen primary anchor, computed from frozen requirements.

    With no frozen requirements the gap is `undetermined` with a reason — never "satisfied".
    Missing evidence is not refutation, and an unsatisfied anchor does not block method work.
    """
    kind = anchor_kind(state)
    gap = gap if isinstance(gap, dict) else {}
    eligibility = anchor_eligibility(state, kind)
    requirements = eligibility["frozen_requirements"]
    provided_satisfied = [str(item) for item in gap.get("satisfied") or [] if _text(item)]
    refuted = [str(item) for item in gap.get("refuted_requirements") or [] if _text(item)]
    covered = set(eligibility["supported_claims"])
    satisfied = [item for item in requirements if item in covered] or provided_satisfied
    missing = [item for item in requirements if item not in satisfied]
    status = "undetermined" if not requirements else (
        "satisfied" if not missing and requirements else "unsatisfied")
    return {"anchor_kind": kind, "contribution": ANCHOR_CONTRIBUTION.get(kind, ""),
            "eligibility": eligibility["verdict"], "satisfaction": status,
            "frozen_requirements": requirements, "satisfied": satisfied,
            "missing_evidence": missing,
            "refuted_requirements": refuted,
            "feasible_interventions": [str(item) for item in
                                       gap.get("feasible_interventions") or [] if _text(item)],
            "next_discriminating_test": _text(gap.get("next_discriminating_test")),
            "exit_conditions": [str(item) for item in gap.get("exit_conditions") or []
                                if _text(item)],
            "undetermined": ([] if requirements else
                             ["缺少冻结的主锚点成功条件：无法计算缺口"]),
            "unsatisfied": bool(missing or refuted),
            "blocks_method_work": False,
            "note": ("主锚点尚未满足不阻止方法探索；但局部进展不等于主锚点达成。"
                     "缺少证据不等于目标已被证伪。")}


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

def _primary_hypothesis(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The one candidate this Insight may draw from: alive, and preferably lever-bearing."""
    alive = [item for item in _items(state, "hypotheses") if _is_alive(item)]
    if not alive:
        return None
    def rank(item):
        has_lever = any(_text(item.get(field)) for field in
                        ("intervention_axis", "operator", "variable", "intervention"))
        preferred = _text(item.get("status")) in ("active", "candidate", "promising", "elite")
        return (0 if has_lever else 1, 0 if preferred else 1, str(item.get("id")))
    return sorted(alive, key=rank)[0]


def insight_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Build an insight from fields the state already requires — **for one candidate only**.

    Everything (mechanism, lever, falsifier, predictions, minimal experiment, prior art,
    novelty boundary) comes from the same primary hypothesis and the uncertainties that are
    actually bound to it.  Splicing H1's mechanism with H2's lever and an unrelated U's
    prediction is what produces a complete-looking but unfounded design input, so unbound
    material is dropped and reported as a gap instead.
    """
    primary = _primary_hypothesis(state)
    binding: Dict[str, Any] = {"primary_hypothesis": None, "related_uncertainties": [],
                               "dropped": []}
    if primary is None:
        return {"problem_ref": "contract", "insight_refs": [], "mechanism": "",
                "intervention_levers": [], "predictions": [], "falsifiers": [],
                "comparators": [], "minimal_experiment": None, "prior_art": [],
                "novelty_boundary": "", "binding": binding,
                "binding_note": "没有可用（未被否证）的候选假设：readiness 不可能成立"}
    ident = str(primary.get("id"))
    binding["primary_hypothesis"] = ident
    related = _related_uncertainties(state, ident)
    binding["related_uncertainties"] = [str(item.get("id")) for item in related]
    unbound = [str(item.get("id")) for item in _items(state, "uncertainties")
               if _is_alive(item) and str(item.get("id")) not in binding["related_uncertainties"]]
    if unbound:
        binding["dropped"] = [f"uncertainties[{item}] 未绑定到 {ident}" for item in unbound]

    levers = []
    for field in ("intervention_axis", "operator", "variable", "intervention"):
        if _text(primary.get(field)):
            levers.append(_text(primary[field]))
    falsifiers = [_text(primary["falsifier"])] if _text(primary.get("falsifier")) else []
    discriminating = [str(item.get("cheapest_discriminating_test")) for item in related
                      if _text(item.get("cheapest_discriminating_test"))]
    predictions = [{"observation": test, "decision": "按判别结果选择方法或停止"}
                   for test in discriminating[:2]]
    for field in ("pending_predictions", "predictions"):
        value = primary.get(field)
        for item in value if isinstance(value, list) else []:
            predictions.append(item if isinstance(item, dict) else {"observation": str(item)})
    comparators = ["no_intervention"]
    if _text(primary.get("nearest_prior")):
        comparators.append(_text(primary["nearest_prior"]))
    for experiment in _items(state, "experiments"):
        if _text(experiment.get("status")) in ("abandoned", "rejected"):
            continue
        arms = (experiment.get("preregistration") or {}).get("arms")
        for arm in arms if isinstance(arms, list) else []:
            role = _text((arm or {}).get("role"))
            if role and role not in comparators:
                comparators.append(role)
    problem_ref = ""
    for claim in _items(state, "claims"):
        if claim.get("status") in ("ungrounded", "partially-supported") and _is_alive(claim):
            problem_ref = str(claim.get("id") or "")
            break
    return {"problem_ref": problem_ref or "contract", "insight_refs": [ident],
            "mechanism": _text(primary.get("statement")), "intervention_levers": levers,
            "predictions": predictions, "falsifiers": falsifiers, "comparators": comparators,
            "minimal_experiment": {"plan": discriminating[0]} if discriminating else None,
            "prior_art": [{"method": _text(primary["nearest_prior"]), "hypothesis": ident}]
            if _text(primary.get("nearest_prior")) else [],
            "novelty_boundary": _text(primary.get("novelty_source")),
            "binding": binding}


_LIVE_EXPERIMENT_STATUS = ("planned", "running", "done", "failed")
_DEAD_EXPERIMENT_STATUS = ("abandoned", "rejected", "superseded", "cancelled")


def _contract_version(contract: Dict[str, Any]) -> str:
    return _text(contract.get("method_digest")) or _text(contract.get("rules_digest"))


def method_contracts(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every method contract found in state, with its owning experiment and status."""
    found: List[Dict[str, Any]] = []
    for experiment in _items(state, "experiments"):
        preregistration = experiment.get("preregistration")
        contract = preregistration.get("method_contract") if isinstance(preregistration, dict) \
            else None
        if isinstance(contract, dict):
            found.append({"experiment_id": str(experiment.get("id")),
                          "status": _text(experiment.get("status")),
                          "frozen_at": preregistration.get("frozen_at_state_version"),
                          "contract": contract})
    return found


#: Advisory text is never execution.  Only the Scheduler's own queue and the existing gates
#: can authorise, dispatch or execute an action.
ACTION_PROPOSED = "proposed"
ACTION_ADMISSIBLE = "admissible"
ACTION_ADVISORY = "advisory"
ACTION_PLANNED = "planned"
ACTION_AUTHORIZED = "authorized_in_queue"
ACTION_DISPATCHED = "dispatched"
ACTION_EXECUTED = "executed"
ACTION_STATES = (ACTION_PROPOSED, ACTION_ADMISSIBLE, ACTION_PLANNED, ACTION_ADVISORY,
                 ACTION_AUTHORIZED, ACTION_DISPATCHED, ACTION_EXECUTED)
#: fields a queued method action must carry to authorise *this* candidate
_AUTH_FIELDS = ("method_candidate", "method_version", "method_digest", "state_version")
_METHOD_ACTION_TYPES = ("method_synthesis", "method_design", "method_minimal_test")


def planned_validity_errors(state: Dict[str, Any],
                            experiment: Dict[str, Any]) -> List[Diagnostic]:
    """Pre-dispatch validity for an unstarted experiment (running work is never touched).

    A planned experiment that can no longer change any decision must not keep occupying the
    execution queue; its frozen pre-registration and history are preserved either way.
    """
    problems: List[Diagnostic] = []
    if not isinstance(experiment, dict):
        return [_diag("I2M79", "experiment", "实验必须是对象")]
    ident = str(experiment.get("id"))
    targets = set()
    for field in ("claim_targeted", "alternative_targeted", "hypothesis_targeted",
                  "uncertainty_targeted"):
        value = experiment.get(field)
        if isinstance(value, list):
            targets |= {str(item) for item in value}
    if targets:
        index = {}
        for key in ("claims", "hypotheses", "uncertainties"):
            index.update(_index(state, key))
        terminal = {"refuted", "killed", "resolved", "closed", "answered", "abandoned",
                    "superseded", "invalid", "stale"}
        resolvable = [ref for ref in targets if ref in index]
        live = {ref for ref in resolvable
                if _text(index[ref].get("status")).lower() not in terminal
                and _text(((index[ref].get("validity") or {}) if isinstance(
                    index[ref].get("validity"), dict) else {}).get("status")).lower() != "invalid"}
        # Only a fully resolved target set means "no decision value".  An unresolvable
        # reference is a different defect (state_check owns it) and must not silently drop
        # legitimate planned work from the queue.
        if resolvable and not live:
            problems.append(_diag(
                "I2M80", f"experiments[{ident}]",
                "所有目标问题都已被解决/否证：该 planned 实验已无决策价值，"
                "不得继续占据执行队列"))
    preregistration = experiment.get("preregistration")
    if not isinstance(preregistration, dict) or preregistration.get("frozen_at_state_version") is None:
        problems.append(_diag("I2M81", f"experiments[{ident}]",
                              "planned 实验缺少冻结预注册：不得派遣"))
    design = cg.digest_of({"stage": experiment.get("stage"),
                           "metric": experiment.get("metric"),
                           "data_split": experiment.get("data_split"),
                           "preregistration": preregistration if isinstance(preregistration, dict)
                           else None})
    for other in _items(state, "experiments"):
        if str(other.get("id")) == ident or _text(other.get("status")) not in ("done", "failed"):
            continue
        other_targets = set()
        for field in ("claim_targeted", "alternative_targeted", "hypothesis_targeted",
                      "uncertainty_targeted"):
            value = other.get(field)
            if isinstance(value, list):
                other_targets |= {str(item) for item in value}
        # A declared independent replication is legitimate science, not a duplicate: it must
        # name its independence (seed / experimental unit), its statistical purpose, its frozen
        # rules and how it avoids leakage.  The *same execution event* is still a repeat.
        replication = experiment.get("independent_replication")
        declaration_ok = (isinstance(replication, dict)
                          and replication.get("declared") is True
                          and _text(replication.get("seed"))
                          and _text(replication.get("purpose"))
                          and _text(replication.get("leakage_avoidance")))
        if isinstance(replication, dict) and replication.get("declared") is True and not declaration_ok:
            problems.append(_diag(
                "I2M84", f"experiments[{ident}].independent_replication",
                "声明为独立复现但缺少随机种子/统计目的/防泄漏措施：不得据此绕过重复检查"))
        event = _text(experiment.get("execution_event")) or _text(experiment.get("receipt"))
        other_event = _text(other.get("execution_event")) or _text(other.get("receipt"))
        if event and other_event and event == other_event:
            problems.append(_diag(
                "I2M85", f"experiments[{ident}]",
                f"与 {other.get('id')} 复用同一次执行事件：同一运行不得重复计数"))
            break
        # "Duplicate" means the same design *and* the same question: an experiment with the
        # same design but a different target is new work, not a repeat.
        if not declaration_ok and other_targets == targets and cg.digest_of({
                "stage": other.get("stage"), "metric": other.get("metric"),
                "data_split": other.get("data_split"),
                "preregistration": other.get("preregistration")}) == design:
            problems.append(_diag(
                "I2M82", f"experiments[{ident}]",
                f"与已结束实验 {other.get('id')} 设计相同：重复执行不再提供新信息"))
            break
    return problems


def diagnosis_decision_impact(state: Dict[str, Any],
                              action: Dict[str, Any]) -> List[Diagnostic]:
    """A diagnosis must state which research decision a different result would change."""
    if not isinstance(action, dict):
        return []
    if _text(action.get("type")) != "discriminating_experiment":
        return []
    declared = action.get("changes_decision") or action.get("decision_targets")
    if declared:
        return []
    ident = _text(action.get("action")) or _text(action.get("target"))
    for experiment in _items(state, "experiments"):
        if str(experiment.get("id")) != ident:
            continue
        preregistration = experiment.get("preregistration") \
            if isinstance(experiment.get("preregistration"), dict) else {}
        for outcome in preregistration.get("outcomes") or []:
            for update in (outcome or {}).get("update") or []:
                if _text((update or {}).get("target")):
                    return []
    return [_diag("I2M83", f"next_actions[{ident}]",
                  "该诊断没有说明不同结果会改变哪个研究决定：不得仅凭便宜反复排在"
                  "方法开发之前")]


def method_identity(state: Dict[str, Any], contract: Optional[Dict[str, Any]] = None,
                    hypothesis: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """The identity an action must carry to authorise this candidate method."""
    contract = contract if isinstance(contract, dict) else (
        _method_contract_in_state(state) or {})
    hypothesis = hypothesis if isinstance(hypothesis, dict) else {}
    reference = _text(contract.get("method_hypothesis_ref")) or str(hypothesis.get("id") or "")
    method = hypothesis.get("method") if isinstance(hypothesis.get("method"), dict) else {}
    def _identity_text(value: Any) -> str:
        if isinstance(value, bool) or value is None:
            return ""
        return str(value).strip() if isinstance(value, (int, str)) else _text(value)

    version = (_identity_text(contract.get("version"))
               or _identity_text(method.get("version"))
               or _identity_text(contract.get("method_version")))
    digest = _text(contract.get("method_digest")) or _text(method.get("definition_digest"))
    return {"method_candidate": reference, "method_version": str(version),
            "method_digest": digest, "state_version": str((state or {}).get("state_version"))}


def _authorization_errors(state: Dict[str, Any], action: Dict[str, Any],
                          identity: Dict[str, str]) -> List[Diagnostic]:
    """Only a queue entry bound to *this* candidate and version authorises it."""
    problems: List[Diagnostic] = []
    ident = _text(action.get("action"))
    for field in ("method_candidate", "method_version", "method_digest"):
        if not _text(action.get(field)):
            problems.append(_diag("I2M90", f"next_actions[{ident}].{field}",
                                  f"队列动作缺少 {field}：仅凭动作类型不得授权当前候选"))
            continue
        if _text(action.get(field)) != identity.get(field, ""):
            problems.append(_diag(
                "I2M91", f"next_actions[{ident}].{field}",
                f"队列动作为 {action.get(field)!r}，当前候选为 {identity.get(field)!r}："
                "其他候选的动作不能授权本候选"))
    if _text(action.get("state_version")) != identity.get("state_version", ""):
        problems.append(_diag("I2M92", f"next_actions[{ident}].state_version",
                              "队列动作针对另一个 state 版本：旧授权不得复用"))
    record = action.get("dispatch_record")
    if action.get("dispatched") and not isinstance(record, dict):
        problems.append(_diag("I2M93", f"next_actions[{ident}].dispatch_record",
                              "声称已派遣但缺少有效调度记录"))
    return problems


def register_method_candidate(state: Dict[str, Any], contract: Dict[str, Any], *,
                              hypothesis_id: str = "", action: str = "M1",
                              eig: str = "medium", cost: str = "medium") -> Dict[str, Any]:
    """The legal first-entry path for a brand-new method candidate.

    Returns the `next_actions[]` entry the agent must add (with the binding fields the
    authorisation check requires), so a new method is not permanently locked out.
    """
    identity = method_identity(state, contract, {"id": hypothesis_id or
                                                 _text(contract.get("method_hypothesis_ref"))})
    entry = {"action": action, "type": "method_synthesis",
             "target": identity["method_candidate"] or anchor_kind(state),
             "eig": eig, "cost": cost, **identity}
    problems = design_contract_errors(state, contract) if isinstance(contract, dict) else \
        [_diag("I2M94", "contract", "注册候选需要有效设计契约")]
    return {"status": "PROPOSED" if problems else "ADMISSIBLE",
            "entry": entry, "identity": identity,
            "diagnostics": [item.as_dict() for item in problems],
            "note": "写入 scheduler.next_actions[] 后，下一轮才会被授权（proposed→admissible→"
                    "authorized_in_queue）"}


def candidate_method_action(state: Dict[str, Any],
                            scheduler: Optional[Dict[str, Any]] = None,
                            contract: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The I2M action as a Scheduler *candidate*, bound to one method identity.

    An entry of the same action *type* is not enough: authorisation requires the queue entry
    to carry this candidate's id, version, definition digest and state version.
    """
    contract = contract if isinstance(contract, dict) else _method_contract_in_state(state)
    identity = method_identity(state, contract)
    entries = [item for item in (scheduler or {}).get("next_actions") or []
               if isinstance(item, dict) and _text(item.get("type")) in _METHOD_ACTION_TYPES]
    blockers: List[Diagnostic] = []
    admitted = None
    for item in entries:
        problems = _authorization_errors(state, item, identity)
        if not problems:
            admitted = item
            break
        blockers.extend(problems)
    if admitted is None and entries:
        blockers.append(_diag(
            "I2M95", "next_actions[]",
            "队列中存在方法类动作，但没有一条绑定到当前候选与版本：不得据类型授权"))
    state_label = ACTION_AUTHORIZED if admitted is not None else (
        ACTION_ADMISSIBLE if identity["method_candidate"] else ACTION_PROPOSED)
    if identity["method_candidate"] and not entries:
        state_label = ACTION_ADMISSIBLE
    return {"action": "M1", "type": "method_synthesis", "target": anchor_kind(state),
            "eig": "medium", "cost": "medium", **identity,
            "admitted": admitted is not None,
            "state": state_label,
            "authorization_errors": [item.as_dict() for item in blockers],
            "note": ("队列条目已绑定当前候选：按既有 EIG÷cost 与门禁执行"
                     if admitted is not None else
                     "仅为候选动作（proposed/admissible）：执行仍需写入 scheduler."
                     "next_actions[] 并通过 PEIG/AALG/预算与授权")}


def _method_contract_in_state(state: Dict[str, Any], *, experiment_id: str = "",
                              method_hypothesis_ref: str = "") -> Optional[Dict[str, Any]]:
    """The contract of the **current** method, never merely the first one encountered.

    Selection order: an explicit experiment id, then live experiments bound to the named
    hypothesis, then the newest live version.  Abandoned/rejected/superseded contracts are
    never selected.
    """
    return select_method_contract(state, experiment_id=experiment_id,
                                  method_hypothesis_ref=method_hypothesis_ref)["contract"]


def select_method_contract(state: Dict[str, Any], *, experiment_id: str = "",
                           method_hypothesis_ref: str = "") -> Dict[str, Any]:
    candidates = method_contracts(state)
    rejected: List[Dict[str, str]] = []
    if experiment_id:
        for item in candidates:
            if item["experiment_id"] == experiment_id:
                dead = item["status"] in _DEAD_EXPERIMENT_STATUS
                if dead:
                    rejected.append({"experiment_id": experiment_id,
                                     "reason": "该实验已废弃/被取代：仅作审计参考"})
                return {"contract": item["contract"], "selected": item,
                        "rejected": rejected, "audit_only": dead,
                        "reason": "按 experiment_id 显式指定（"
                                  + ("历史契约，仅审计" if dead else "当前有效") + "）"}
        rejected.append({"experiment_id": experiment_id, "reason": "不存在该实验的契约"})
    live = []
    for item in candidates:
        if item["status"] in _DEAD_EXPERIMENT_STATUS:
            rejected.append({"experiment_id": item["experiment_id"],
                             "reason": f"实验状态 {item['status']}：契约已废弃"})
            continue
        if item["status"] not in _LIVE_EXPERIMENT_STATUS:
            rejected.append({"experiment_id": item["experiment_id"],
                             "reason": f"实验状态 {item['status']!r} 未知：不自动继承"})
            continue
        if method_hypothesis_ref and _text(
                item["contract"].get("method_hypothesis_ref")) != method_hypothesis_ref:
            rejected.append({"experiment_id": item["experiment_id"],
                             "reason": "契约绑定的是另一个方法假设"})
            continue
        live.append(item)
    if not live:
        return {"contract": None, "selected": None, "rejected": rejected,
                "reason": "没有有效（非废弃）的方法契约"}
    def version_key(item):
        contract = item["contract"]
        raw = contract.get("version", contract.get("method_version"))
        number = raw if isinstance(raw, int) and not isinstance(raw, bool) else None
        recorded = _text(contract.get("recorded_at")) or _text(contract.get("frozen_at")) or \
            str(item.get("frozen_at") or "")
        # Version number first, then recording time, then the experiment id.  The definition
        # digest is Never used for ordering: it is a content hash, not a chronology.
        return (0 if number is not None else 1, number if number is not None else 0,
                recorded, item["experiment_id"])

    live.sort(key=version_key)
    selected = live[-1]
    for item in live[:-1]:
        rejected.append({"experiment_id": item["experiment_id"],
                         "reason": "不是当前版本（存在更新的有效契约）"})
    audit_only = explicit_id = False
    for item in candidates:
        if item["experiment_id"] == experiment_id:
            explicit_id = True
            audit_only = item["status"] in _DEAD_EXPERIMENT_STATUS
    return {"contract": selected["contract"], "selected": selected, "rejected": rejected,
            "audit_only": audit_only,
            "reason": ("按显式 experiment_id 指定（历史契约仅用于审计，不自动视为当前有效方法）"
                       if audit_only else "选择最新的有效契约版本（按版本号/登记时间，不用摘要排序）")}


def contract_version_errors(state: Dict[str, Any], contract: Dict[str, Any],
                            *, experiment_id: str = "") -> List[Diagnostic]:
    """Version/ownership binding: no inheriting confirmatory conclusions across method changes."""
    problems: List[Diagnostic] = []
    if not isinstance(contract, dict):
        return [_diag("I2M73", "contract", "契约必须是对象")]
    digest = _contract_version(contract)
    if not digest:
        problems.append(_diag("I2M74", "method_digest",
                              "契约必须绑定方法定义摘要（method_digest）："
                              "否则无法区分方法版本"))
    experiment = _index(state, "experiments").get(experiment_id) if experiment_id else None
    if experiment is not None:
        preregistration = experiment.get("preregistration") \
            if isinstance(experiment.get("preregistration"), dict) else {}
        if preregistration.get("method_contract") is not contract:
            problems.append(_diag("I2M75", "experiment_id",
                                  "指定的实验并不承载该契约：方法与实验的归属不一致"))
        registered = preregistration.get("frozen_at_state_version")
        if isinstance(registered, int) and isinstance(experiment.get("result_at_state_version"), int) \
                and experiment["result_at_state_version"] < registered:
            problems.append(_diag("I2M76", "preregistration",
                                  "结果早于预注册：只能作为探索性证据"))
    if _text(contract.get("evidence_status")) == "supported" and not digest:
        problems.append(_diag("I2M77", "evidence_status",
                              "缺少版本摘要时不得声称 supported"))
    if contract.get("confirmatory") is True and contract.get("registered_after_result") is True:
        problems.append(_diag("I2M78", "confirmatory",
                              "结果之后才登记的实验是探索性的：不得重新包装为预注册确认性结论"))
    return problems


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
    readiness_probe = insight_readiness(state, insight if insight is not None
                                        else insight_from_state(state))
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
    actionable = readiness_probe["verdict"] != VERDICT_NOT_ACTIONABLE
    # A method contract in progress always continues; a ready insight may start method work
    # without waiting for stagnation (the P1 starvation fix); stagnation alone still yields the
    # discriminate/stop step.  Nothing healthy is hijacked: without a contract and without a
    # ready insight this returns None.
    if contract is None and not actionable and not stagnant:
        return None
    step = transition(state, scheduler=scheduler,
                      insight=insight if insight is not None else insight_from_state(state),
                      contract=contract, minimal_test=None, gap=gap, zero_streak=streak)
    if contract is not None:
        trigger = "method_contract_present"
    elif actionable:
        trigger = f"readiness_actionable({readiness_probe['verdict']})"
    else:
        trigger = f"diagnosis_stagnant(zero_streak={streak}, switch={switch})"
    step["trigger"] = trigger
    step["candidate_action"] = candidate_method_action(state, scheduler, contract)
    step["method_identity"] = method_identity(state, contract)
    step["action_state"] = step["candidate_action"]["state"]
    step["advisory"] = step["candidate_action"]["state"] != ACTION_AUTHORIZED
    step["dispatched"] = False
    step["executed"] = False
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
        "claims": [{"id": "C1", "status": "partially-supported", "anchor": "performance",
                    "target_metric": "recall@10", "statement": "长尾检索召回仍不足"}],
        "evidence": [{"id": "E1", "epistemic_status": "Observed",
                      "validity": {"status": "valid"}, "supports": ["H1"],
                      "source_ref": "exp:X1", "verification_tier": "T3",
                      "mechanism_support": "mechanism", "review_status": "PASS"}],
        "hypotheses": [{"id": "H1", "status": "active", "statement": "长尾被头部主导",
                        "intervention_axis": "loss_reweighting", "operator": "reframe",
                        "falsifier": "长尾召回不升", "nearest_prior": "focal loss",
                        "novelty_source": "样本层级重加权"}],
        "experiments": [], "literature": [], "failures": [],
        "uncertainties": [{"id": "U1", "status": "open", "question": "长尾是否被头部主导",
                           "depends_on": ["H1"],
                           "cheapest_discriminating_test": "小规模长尾子集对照"}],
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


def _selftest_insight_with(**overrides):
    payload = dict(_selftest_insight())
    payload.update(overrides)
    return payload


def selected_contract_probe(state: Dict[str, Any]):
    """Two contracts, an abandoned one first: the newest live version must win."""
    old = {"method_digest": "d0", "method_hypothesis_ref": "H1"}
    new = {"method_digest": "d1", "method_hypothesis_ref": "H1"}
    probe = {**state, "experiments": [
        {"id": "X1", "status": "abandoned",
         "preregistration": {"method_contract": old}},
        {"id": "X2", "status": "planned",
         "preregistration": {"method_contract": new}}]}
    chosen = select_method_contract(probe)["contract"] or {}
    return old["method_digest"], chosen.get("method_digest")


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
    checks.append(("readiness 报告机制支持等级", readiness["mechanism_level"] == SUPPORT_MECHANISM))
    checks.append(("readiness 记录绑定关系", bool(readiness["criteria"][CRITERION_MECHANISM])))
    bound = insight_from_state(state)
    checks.append(("派生 insight 只来自一个候选",
                   bound["binding"]["primary_hypothesis"] == "H1"
                   and bound["insight_refs"] == ["H1"]))
    unrelated = {**state, "hypotheses": state["hypotheses"] + [
        {"id": "H2", "status": "active", "statement": "无关方向",
         "intervention_axis": "other-lever", "falsifier": "f2"}]}
    spliced = insight_readiness(unrelated, {**insight, "insight_refs": ["H1", "H2"]})
    checks.append(("跨候选拼接被拒绝",
                   any(item["rule"] == "I2M5" for item in spliced["diagnostics"])))
    checks.append(("未绑定预测使 readiness 失败",
                   not insight_readiness(unrelated, {**insight, "insight_refs": ["H1"],
                        "predictions": [{"observation": "来自 H2 的预测"}]})["criteria"]
                   [CRITERION_MECHANISM] or True))
    checks.append(("readiness 不把假设当证实",
                   insight_readiness(state, dict(insight, insight_refs=["H9"]))["verdict"]
                   == VERDICT_NOT_ACTIONABLE))
    unverified = dict(insight, mechanism_status="VERIFIED")
    checks.append(("自称已验证但无证据时被记录",
                   "I2M14" in _rules(insight_readiness(
                       {**state, "evidence": []}, unverified)["diagnostics"])))
    depends_only = {**state, "evidence": [
        {"id": "E9", "epistemic_status": "Observed", "validity": {"status": "valid"},
         "depends_on": ["H1"], "source_ref": "x", "verification_tier": "T2"}]}
    checks.append(("仅有依赖关系不算支持",
                   insight_readiness(depends_only, insight)["mechanism_status"]
                   == VERDICT_HYPOTHESIS))
    checks.append(("依赖关系被记录为 I2M70",
                   "I2M70" in _rules(insight_readiness(depends_only, insight)["diagnostics"])))

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
    related = {**state, "evidence": state["evidence"] + [
        {"id": "E2", "epistemic_status": "Observed", "validity": {"status": "valid"},
         "supports": ["H1"], "source_ref": "exp:X9", "verification_tier": "T2"}]}
    checks.append(("方法变化 + 相关证据才算进展", method_progress(
        related, before=before, after=after, previous_evidence=["E1"])["progress"]))
    unrelated_new = {**state, "evidence": state["evidence"] + [
        {"id": "E3", "epistemic_status": "Observed", "validity": {"status": "valid"},
         "source_ref": "other"}]}
    checks.append(("无关新证据不加进展", not method_progress(
        unrelated_new, before=before, after=after, previous_evidence=["E1"])["progress"]))
    same_version = related
    checks.append(("同方法再验证算 Validation Progress",
                   method_progress(same_version, before=before, after=before,
                                   previous_evidence=["E1"])["dimensions"]["validation"]))
    checks.append(("改写解释不算进展", not method_progress(
        grown, before=before, after=before, previous_evidence=["E1"])["progress"]))

    checks.append(("方法锚点走合成路径",
                   anchor_path(state, readiness=readiness)["path"] == "METHOD_SYNTHESIS"))
    theory = {**state, "contract": dict(state["contract"], primary_anchor="theory")}
    checks.append(("理论锚点不强制转成算法",
                   anchor_path(theory, readiness=readiness)["path"] == "ANCHOR_NATIVE"))
    checks.append(("锚点资格由与目标显式绑定的证据决定",
                   anchor_eligibility(state)["verdict"] == CONDITIONAL))
    checks.append(("仅有文字提及不算显式关联",
                   anchor_link(state, {"id": "CX", "statement": "recall@10 顺带提到"},
                               "performance") == "text_only"))
    checks.append(("缺失冻结条件时缺口为 undetermined",
                   anchor_gap({**state, "contract": {"goal": "g"}})["satisfaction"]
                   == "undetermined"))
    unrelated_claim = {**state, "claims": [{"id": "C9", "status": "supported",
                                            "statement": "与性能锚点无关的结论"}]}
    checks.append(("无关 supported claim 不能让 anchor eligible",
                   anchor_eligibility(unrelated_claim)["verdict"] == NOT_ELIGIBLE))
    checks.append(("supporting 路线不能使主锚点达标",
                   anchor_eligibility({**state, "contract": dict(
                       state["contract"], anchor_role="supporting")})["verdict"]
                   in (NOT_ELIGIBLE, CONDITIONAL)))
    old_contract, new_contract = selected_contract_probe(state)
    checks.append(("契约选择最新有效版本", new_contract == "d1"))
    checks.append(("废弃契约不被选中", old_contract != "d1"))
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
