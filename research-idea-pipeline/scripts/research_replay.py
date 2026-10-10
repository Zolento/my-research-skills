#!/usr/bin/env python3
"""research_replay.py — historical replay, evaluation metrics, ablation, adversarial cases.

The question this module answers is not "does the code run". It is: **did the cognitive
layer actually improve scientific discovery?** That requires replaying a decision with only
the information available at the time, scoring it against an answer the system never saw,
and comparing configurations that differ only in which capabilities are enabled.

Three properties are non-negotiable:

* **No future information leaks.** Hidden results, reference answers and later conclusions
  are stripped before the runner sees anything, and the strip is verified by scanning the
  visible payload for forbidden strings — not by trusting the code path.
* **No invented gains.** With fewer than two runs per arm the report says
  `insufficient_sample` and reports the raw observations; it never claims an improvement.
* **No self-certified novelty.** Innovation is scored from an independent
  literature/human label carried by the case; an agent's own novelty rating is refused.

The runner is pluggable. The built-in runner is offline and deterministic: it drives the
shipped CIE machinery (`cognition` + `prediction_compare` + `strategy_memory`) so the suite
runs without a model, and the test file can assert exact behaviour.

Rule namespace `RP1`—`RP9`.

Usage
-----
    python3 research_replay.py validate    --case <case.json>
    python3 research_replay.py show        --case <case.json>          # agent-visible view
    python3 research_replay.py run         --case <case.json> [--arm full_cie]
    python3 research_replay.py suite       --dir <cases/> [--runner module:function]
    python3 research_replay.py ablate      --dir <cases/> [--runs N]
    python3 research_replay.py adversarial --write <dir>
    python3 research_replay.py smoke       --work <dir>
    python3 research_replay.py --selftest

Exit codes: 0 pass, 1 argument error, 3 hard violation, 4 environment not satisfied.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import cognition as cg
import prediction_compare as pc
import strategy_memory as sm

Diagnostic = cg.Diagnostic

SCHEMA_CASE = "research-idea-pipeline/replay-case@1"
SCHEMA_DECISION = "research-idea-pipeline/replay-decision@1"

EXIT_OK = cg.EXIT_OK
EXIT_ERROR = cg.EXIT_ERROR
EXIT_HARD = cg.EXIT_HARD
EXIT_ENV = cg.EXIT_ENV

#: Ablation arms, weakest first. Each arm adds exactly one capability.
#: These four are frozen: the shipped ablation report and its consumers read them.
ABLATION_ARMS: Tuple[str, ...] = ("baseline", "memory_only", "memory_prediction", "full_cie")

#: Skill-RSI arms. They extend the ladder instead of replacing it, so the original four
#: arms keep their exact meaning and the historical reports stay comparable.
RSI_ARMS: Tuple[str, ...] = (
    "rsi_full",
    "rsi_shadow",
    "rsi_without_trajectory",
    "rsi_without_replay",
    "rsi_without_scope",
    "rsi_without_promotion",
)

ARM_CAPABILITIES: Dict[str, Tuple[str, ...]] = {
    "baseline": (),
    "memory_only": ("cognitive_memory",),
    "memory_prediction": ("cognitive_memory", "prediction_comparator"),
    "full_cie": ("cognitive_memory", "prediction_comparator", "strategy_memory"),
    # Skill-RSI: a scoped, replay-evaluated policy candidate may change which already-legal
    # action is chosen. Every RSI arm keeps CIE + strategy memory; they differ only in
    # which guard is present, so a difference is attributable to that guard alone.
    "rsi_full": ("cognitive_memory", "prediction_comparator", "strategy_memory",
                 "scoped_policy", "trajectory_evidence", "replay_evaluation", "promotion_gate"),
    "rsi_shadow": ("cognitive_memory", "prediction_comparator", "strategy_memory",
                   "scoped_policy", "trajectory_evidence", "replay_evaluation",
                   "promotion_gate", "shadow_only"),
    "rsi_without_trajectory": ("cognitive_memory", "prediction_comparator", "strategy_memory",
                               "scoped_policy", "replay_evaluation", "promotion_gate"),
    "rsi_without_replay": ("cognitive_memory", "prediction_comparator", "strategy_memory",
                           "scoped_policy", "trajectory_evidence", "promotion_gate"),
    "rsi_without_scope": ("cognitive_memory", "prediction_comparator", "strategy_memory",
                          "trajectory_evidence", "replay_evaluation", "promotion_gate"),
    "rsi_without_promotion": ("cognitive_memory", "prediction_comparator", "strategy_memory",
                              "scoped_policy", "trajectory_evidence", "replay_evaluation"),
}

#: Counterfactual evidence classes (Skill-RSI §5.2). A historical branch that was never
#: executed cannot be scored, and it is never rounded up to an observed result.
EVIDENCE_SUPPORT_CLASSES: Tuple[str, ...] = ("OBSERVED", "REPLAY_SUPPORTED", "NO_SUPPORT")

#: Policy candidate statuses that are allowed to influence a decision during evaluation.
#: A merely PROPOSED candidate may not act; that is the promotion gate.
ACTIONABLE_POLICY_STATUSES: Tuple[str, ...] = ("ACTIVE",)

#: Any of these makes an arm a Skill-RSI arm, so the policy step runs and each *missing*
#: guard is reported as a bypass instead of the whole step being skipped.
RSI_POLICY_CAPABILITIES: Tuple[str, ...] = ("scoped_policy", "trajectory_evidence",
                                            "replay_evaluation", "promotion_gate",
                                            "shadow_only")


#: Evaluation dimensions. Each is scored independently; nothing is averaged into a total.
METRIC_DIMENSIONS: Tuple[str, ...] = (
    "mechanistic_understanding",
    "prediction_quality",
    "intervention_quality",
    "scientific_novelty",
    "search_efficiency",
    "stagnation_recovery",
    "memory_accumulation",
)

#: Keys that must never reach the runner.
HIDDEN_KEYS: Tuple[str, ...] = ("hidden", "evaluation_only", "reference", "answer",
                                "later_results", "future")

#: Regions that are genuine decision-time inputs: the agent is meant to see the canonical
#: state, the candidate actions, the scheduler, the case's own question, the observation
#: packet and any recalled projection. An identifier that appears here is legitimate history,
#: not a leak.
LEGITIMATE_VISIBLE_REGIONS: Tuple[str, ...] = ("state", "legal_actions", "scheduler",
                                              "revisions", "question", "observation_packet",
                                              "insight_cards", "cognition",
                                              "policy_candidates")

#: Only *identifier-shaped* short tokens are treated as answer markers: 2-11 ASCII chars,
#: starting with a letter and containing a digit (`X1`, `LIT1`, `P3`, `ADV4`). Natural
#: language fragments such as "mechanism A" are deliberately excluded — they legitimately
#: appear in the question, and a guard that fires on them is noise, not protection.
SHORT_TOKEN_PATTERN = re.compile(r"^(?=.{2,11}$)(?=.*[0-9])[A-Za-z][A-Za-z0-9_.\-]*$")

#: Behaviours an adversarial case may forbid.
FORBIDDEN_BEHAVIOURS: Tuple[str, ...] = (
    "propose_again_refuted_mechanism",
    "continue_attribution_without_decision_value",
    "treat_invalid_run_as_refutation",
    "treat_post_hoc_as_prediction",
    "self_certify_novelty",
    "claim_prediction_without_criterion",
    "inherit_unverified_inference",
    "repeat_stopped_protocol",
    "report_unqualified_result_as_held",
    "certify_insight_from_unqualified_evidence",
    # Skill-RSI additions: a policy change that skipped a guard.
    "apply_unpromoted_policy",
    "use_unobserved_branch",
    "apply_unscoped_policy",
    "apply_unsupported_policy",
    "apply_untracked_policy",
)

#: A novelty label must come from outside the agent.
NOVELTY_LABELS: Tuple[str, ...] = ("novel", "not_novel", "unknown")


# ---------------------------------------------------------------------------
# Cases: schema, validation, leak guard
# ---------------------------------------------------------------------------

def case_errors(case: Any) -> List[Diagnostic]:
    if not isinstance(case, dict):
        return [Diagnostic("RP1", "case", "replay case 必须是对象")]
    diagnostics: List[Diagnostic] = []
    if case.get("_schema") != SCHEMA_CASE:
        diagnostics.append(Diagnostic("RP1", "case._schema", f"必须是 {SCHEMA_CASE!r}"))
    if not isinstance(case.get("id"), str) or not case["id"].strip():
        diagnostics.append(Diagnostic("RP1", "case.id", "缺少非空 id"))
    if not isinstance(case.get("question"), str) or not case["question"].strip():
        diagnostics.append(Diagnostic("RP1", "case.question", "缺少研究问题"))
    visible = case.get("visible")
    if not isinstance(visible, dict):
        diagnostics.append(Diagnostic("RP1", "case.visible", "缺少 visible 段"))
        return diagnostics
    if not isinstance(visible.get("state"), dict):
        diagnostics.append(Diagnostic("RP1", "case.visible.state", "visible 必须包含 state"))
    for key in ("revisions", "available_literature", "known_conditions", "insight_cards"):
        if key in visible and not isinstance(visible[key], list):
            diagnostics.append(Diagnostic("RP1", f"case.visible.{key}", "必须是数组"))
    hidden = case.get("hidden")
    if not isinstance(hidden, dict) or not isinstance(hidden.get("answer"), dict):
        diagnostics.append(Diagnostic(
            "RP1", "case.hidden.answer",
            "hidden.answer 是评价基准，必须存在；没有它就无法判断回放是否成功"))
        return diagnostics
    answer = hidden["answer"]
    if answer.get("true_outcome_class") not in pc.OUTCOME_CLASSES:
        diagnostics.append(Diagnostic(
            "RP1", "case.hidden.answer.true_outcome_class",
            f"必须是 {list(pc.OUTCOME_CLASSES)} 之一"))
    if isinstance(answer.get("novelty_rating"), (int, float)) and \
            not answer.get("human_novelty_label") and not answer.get("novelty_neighbours"):
        diagnostics.append(Diagnostic(
            "RP5", "case.hidden.answer",
            "novelty 需要独立文献近邻或人工标签；不接受 agent 自评作为唯一依据"))
    evaluation = case.get("evaluation_only")
    if not isinstance(evaluation, dict):
        diagnostics.append(Diagnostic("RP1", "case.evaluation_only", "缺少评价段"))
    else:
        for marker in evaluation.get("must_not_appear") or []:
            if not isinstance(marker, str) or not marker.strip():
                diagnostics.append(Diagnostic(
                    "RP2", "case.evaluation_only.must_not_appear",
                    "额外的泄漏标记必须是非空字符串"))
        for behaviour in evaluation.get("forbidden_behaviours") or []:
            if behaviour not in FORBIDDEN_BEHAVIOURS:
                diagnostics.append(Diagnostic(
                    "RP2", "case.evaluation_only.forbidden_behaviours",
                    f"未知的禁止行为：{behaviour!r}"))
    return diagnostics


def load_case(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise cg.CognitionError(f"replay case not found: {path}")
    try:
        case = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise cg.CognitionError(f"replay case is not valid JSON: {path} ({exc})") from exc
    diagnostics = case_errors(case)
    if diagnostics:
        raise cg.CognitionError("; ".join(d.rule + " " + d.detail for d in diagnostics))
    return case


def visible_view(case: Dict[str, Any]) -> Dict[str, Any]:
    """Everything the runner may see. Hidden and evaluation sections are removed."""
    visible = case.get("visible") or {}
    return {
        "case_id": case.get("id"),
        "question": case.get("question"),
        "state": _strip_hidden_keys(visible.get("state") or {}),
        "revisions": [record for record in visible.get("revisions") or []
                      if isinstance(record, dict)
                      and not any(key in record for key in HIDDEN_KEYS)],
        "scheduler": visible.get("scheduler"),
        "observation_packet": visible.get("observation_packet"),
        "available_literature": list(visible.get("available_literature") or []),
        "known_conditions": list(visible.get("known_conditions") or []),
        "insight_cards": [card for card in visible.get("insight_cards") or []
                          if isinstance(card, dict)],
        # Skill-RSI visible surface: policy candidates and the counterfactual support map are
        # inputs to the decision, so they are visible by design. The hidden answer stays out.
        "policy_candidates": [dict(item) for item in visible.get("policy_candidates") or []
                              if isinstance(item, dict)],
        "evidence_support": dict(visible.get("evidence_support") or {}),
        "legal_actions": [dict(item) for item in visible.get("legal_actions") or []
                          if isinstance(item, dict)],
        "decision_time": visible.get("decision_time"),
        "cognition": visible.get("cognition"),
    }


def _strip_hidden_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_hidden_keys(item) for key, item in value.items()
                if key not in HIDDEN_KEYS}
    if isinstance(value, list):
        return [_strip_hidden_keys(item) for item in value]
    return value


def forbidden_strings(case: Dict[str, Any]) -> List[str]:
    """Every string that must not appear in the agent-visible payload."""
    hidden = case.get("hidden") or {}
    evaluation = case.get("evaluation_only") or {}
    strings: List[str] = []
    strings.extend(item for item in hidden.get("later_results") or [] if isinstance(item, str))
    answer = hidden.get("answer") or {}
    for field in ("mechanism_terms", "assumption_terms", "boundary_terms",
                  "required_controls", "reference_reasoning"):
        strings.extend(item for item in answer.get(field) or [] if isinstance(item, str))
    # Evaluation instructions are not research content, so their labels are not leak
    # markers. A case that needs extra markers lists them explicitly.
    value = evaluation.get("reference_mechanism")
    if isinstance(value, str):
        strings.append(value)
    strings.extend(item for item in evaluation.get("must_not_appear") or []
                   if isinstance(item, str))
    # Short tokens are too common to be meaningful leak markers.
    return sorted({text.strip() for text in strings if len(text.strip()) >= 12})


def leak_scan(case: Dict[str, Any], visible: Any) -> List[str]:
    """Hidden strings reachable from the visible payload.

    Tier 1 is the original substring guard over strings of 12+ characters. Tier 2 covers the
    shorter answer tokens the length filter used to drop entirely: an identifier such as an
    intervention id is legitimate inside the decision-time inputs (the agent must see the
    candidate set), so it is only a leak when it also appears *outside* those inputs, where
    nothing could have put it except a smuggled answer.
    """
    blob = json.dumps(visible, ensure_ascii=False)
    found = [text for text in forbidden_strings(case) if text in blob]
    found.extend(f"<short:{token}>" for token in short_token_leaks(case, visible))
    return sorted(set(found))


def short_answer_tokens(case: Dict[str, Any]) -> List[str]:
    """Hidden answer tokens too short for the substring guard but specific enough to matter."""
    hidden = case.get("hidden") or {}
    evaluation = case.get("evaluation_only") or {}

    def walk(value: Any) -> Iterable[str]:
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from walk(item)
        elif isinstance(value, list):
            for item in value:
                yield from walk(item)

    tokens: List[str] = []
    for value in list(walk(hidden)) + list(walk(evaluation)):
        text = value.strip()
        if SHORT_TOKEN_PATTERN.match(text):
            tokens.append(text)
    return sorted(set(tokens))


def _region_blob(visible: Dict[str, Any], *, inside: bool) -> str:
    return json.dumps({key: value for key, value in visible.items()
                       if (key in LEGITIMATE_VISIBLE_REGIONS) is inside},
                      ensure_ascii=False)


def short_token_leaks(case: Dict[str, Any], visible: Dict[str, Any]) -> List[str]:
    """Answer identifiers the agent could not have derived from its inputs.

    A short identifier is only a leak when it appears in the authored context **and** is
    absent from every decision-time input. An intervention id that the agent can already see
    in the candidate set or the observation packet reveals nothing; the same id appearing
    only in a hand-written `known_conditions` entry reveals the answer.
    """
    inside = _region_blob(visible, inside=True)
    outside = _region_blob(visible, inside=False)
    leaks: List[str] = []
    for token in short_answer_tokens(case):
        pattern = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(token) + r"(?![A-Za-z0-9_])")
        if pattern.search(outside) and not pattern.search(inside):
            leaks.append(token)
    return sorted(set(leaks))


# ---------------------------------------------------------------------------
# The offline runner
# ---------------------------------------------------------------------------

def cie_offline_runner(visible: Dict[str, Any], arm: str) -> Dict[str, Any]:
    """A deterministic, model-free runner built from the shipped CIE machinery.

    It is a real consumer of the layer, not a scripted answer: it builds the cognitive
    index, recalls context, compares the observation packet and asks for a behaviour
    switch. What it *cannot* do is see the hidden answer, and the ablation arms differ
    exactly in which of those capabilities they may call.
    """
    capabilities = ARM_CAPABILITIES[arm]
    state = visible.get("state") or {}
    revisions = visible.get("revisions") or []
    scheduler = visible.get("scheduler")
    decision: Dict[str, Any] = {
        "_schema": SCHEMA_DECISION,
        "case_id": visible.get("case_id"),
        "arm": arm,
        "capabilities": list(capabilities),
        "used_memory": [],
        "mechanism_terms": [],
        "predicted_outcome_class": None,
        "diagnostic_outcome_class": None,
        "anomaly_class": None,
        "evidence_class": None,
        "evidence_eligible": False,
        "scientific_status": "NO_INFERENCE",
        "provenance_gaps": [],
        "chosen_intervention": None,
        "identification_controls": [],
        "representation_changed": False,
        "repeated_prior_error": False,
        "novelty_self_rating": None,
        "decision_changed": False,
        "insight_classes": {},
    }

    if "cognitive_memory" not in capabilities:
        # Baseline: only the raw state. No recall, no support level, no constraints.
        decision["mechanism_terms"] = [claim.get("statement", "") for claim
                                       in state.get("claims", []) or []
                                       if isinstance(claim, dict)][:1]
        decision["chosen_intervention"] = ""
        decision["decision_changed"] = False
        return decision

    index, _ = cg.full_index(state, revisions, "replay",
                             None, scheduler if "strategy_memory" in capabilities else None)
    selection = cg.recall(index, state)
    decision["used_memory"] = [mechanism["id"] for mechanism in selection["hot"]["mechanisms"]]
    hot = selection["hot"]["mechanisms"]
    # What the system can actually articulate about the mechanism: every recalled
    # mechanism's statement, its necessity conditions and boundaries, plus the anomaly
    # text. An arm without the memory layer has none of this available.
    articulated: List[str] = []
    for mechanism in hot:
        articulated.append(str(mechanism.get("statement", "")))
        articulated.append(str(mechanism.get("scope", "")))
    for anomaly in selection["hot"].get("anomalies", []):
        articulated.append(str(anomaly.get("observation", "")))
    for competition in selection["hot"].get("competitions", []):
        articulated.append(str(competition.get("shared_explanation", "")))
    for mechanism in index.get("mechanisms", []):
        if mechanism.get("id") in decision["used_memory"]:
            structure = mechanism.get("structure") or {}
            articulated.extend(str(item) for item in structure.get("necessary_conditions") or [])
            articulated.extend(str(item) for item in structure.get("boundaries") or [])
            articulated.append(str(mechanism.get("support_level", "")))
    for boundary in index.get("boundaries", []):
        articulated.append(str(boundary.get("rule", "")))
    decision["mechanism_terms"] = [text for text in articulated if text.strip()]
    constraints = selection["failure_constraints"]
    stopped = [item for item in constraints if item.get("retry") == "blocked"]
    decision["repeat_blocked"] = bool(stopped)

    if "prediction_comparator" not in capabilities:
        decision["chosen_intervention"] = ""
        decision["decision_changed"] = bool(hot)
        return decision

    packet = visible.get("observation_packet")
    if isinstance(packet, dict):
        assessment, _ = pc.assess_experiment(state, packet)
        decision["predicted_outcome_class"] = assessment.get("outcome_class")
        decision["diagnostic_outcome_class"] = assessment.get("diagnostic_outcome_class")
        decision["anomaly_class"] = assessment.get("outcome_class")
        decision["evidence_class"] = assessment.get("evidence_class")
        decision["evidence_eligible"] = bool(assessment.get("evidence_eligible"))
        decision["scientific_status"] = assessment.get("scientific_status")
        decision["provenance_gaps"] = list(assessment.get("provenance_gaps") or [])
        decision["transition_allowed"] = pc.evidence_transition_allowed(state, assessment)[0]
    # The insight layer is the last link of the chain, so its class is observable here: a
    # regression that certifies an insight while the comparison was not qualified evidence
    # becomes a forbidden behaviour rather than a silent upgrade.
    projected = cg.project_insights(state, visible.get("insight_cards") or [])
    decision["insight_classes"] = {
        item.get("id"): item.get("derived_class") for item in projected["insights"]}
    switch = pc.diagnosis_switch(state, index.get("competitions", []),
                                 scheduler, index.get("mechanisms"))
    decision["switch_action"] = switch["action"]
    decision["chosen_intervention"] = _intervention_for(state, index, switch)
    decision["decision_changed"] = switch["action"] != "CONTINUE_ATTRIBUTION" or bool(hot)
    decision["independent_exploration_allowed"] = switch["independent_exploration_allowed"]

    if "strategy_memory" in capabilities:
        assessment = sm.value_assessment(state, index, _first_target(index), scheduler)
        decision["intervention_quality_signals"] = assessment["decision_value"][
            "changes_experiment_design"]["assessment"]
        decision["objections"] = assessment["objections"]

    if any(capability in capabilities for capability in RSI_POLICY_CAPABILITIES):
        _apply_policy_candidate(visible, capabilities, decision, state, scheduler)
    return decision


def _first_target(index: Dict[str, Any]) -> str:
    for mechanism in index.get("mechanisms", []):
        for key in ("claims", "hypotheses"):
            refs = (mechanism.get("canonical_refs") or {}).get(key) or []
            if refs:
                return refs[0]
    return ""


def _intervention_for(state: Dict[str, Any], index: Dict[str, Any],
                      switch: Dict[str, Any]) -> str:
    if switch["action"] == "RECORD_BOUNDARY_AND_STOP":
        return ""
    for competition in index.get("competitions", []):
        if competition.get("status") != "open":
            continue
        intervention = competition.get("discriminating_intervention")
        if isinstance(intervention, str) and intervention not in ("", "TBD"):
            return intervention
    for experiment in state.get("experiments", []) or []:
        if isinstance(experiment, dict) and experiment.get("status") == "planned":
            return str(experiment.get("id"))
    return ""


def load_runner(spec: Optional[str]) -> Callable[[Dict[str, Any], str], Dict[str, Any]]:
    """`module:function` or the built-in offline runner."""
    if not spec:
        return cie_offline_runner
    if ":" not in spec:
        raise cg.CognitionError("runner spec must be `module:function`")
    module_name, function_name = spec.split(":", 1)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    module = importlib.import_module(module_name)
    function = getattr(module, function_name, None)
    if not callable(function):
        raise cg.CognitionError(f"runner is not callable: {spec}")
    return function


def decision_errors(decision: Any) -> List[Diagnostic]:
    if not isinstance(decision, dict):
        return [Diagnostic("RP3", "decision", "runner 必须返回对象")]
    diagnostics: List[Diagnostic] = []
    if decision.get("_schema") != SCHEMA_DECISION:
        diagnostics.append(Diagnostic("RP3", "decision._schema",
                                      f"必须是 {SCHEMA_DECISION!r}"))
    for field in ("arm", "mechanism_terms", "used_memory"):
        if field not in decision:
            diagnostics.append(Diagnostic("RP3", f"decision.{field}", "缺少必填字段"))
    if decision.get("novelty_self_rating") is not None:
        diagnostics.append(Diagnostic(
            "RP5", "decision.novelty_self_rating",
            "agent 自评不是 novelty 证据；评分只读 case 携带的独立标签或文献近邻"))
    if decision.get("arm") not in ABLATION_ARMS + RSI_ARMS:
        diagnostics.append(Diagnostic("RP3", "decision.arm", "未知的 ablation arm"))
    return diagnostics


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _contains_all(haystack: str, needles: Sequence[str]) -> Tuple[int, int]:
    hits = sum(1 for needle in needles if needle and needle in haystack)
    return hits, len([needle for needle in needles if needle])


def _rate(hits: int, total: int) -> Optional[float]:
    return None if total == 0 else round(hits / total, 4)


def _metric(value: Optional[float], basis: List[str], reason: str) -> Dict[str, Any]:
    return {"value": value, "basis": basis, "reason": reason}


def evaluate(case: Dict[str, Any], decision: Dict[str, Any],
             baseline_decision: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Score one replayed decision against the case's answer. Never a single total."""
    answer = (case.get("hidden") or {}).get("answer") or {}
    evaluation = case.get("evaluation_only") or {}
    text = " ".join(str(item) for item in decision.get("mechanism_terms") or [])

    mechanism_hits, mechanism_total = _contains_all(text, answer.get("mechanism_terms") or [])
    assumption_hits, assumption_total = _contains_all(text, answer.get("assumption_terms") or [])
    boundary_hits, boundary_total = _contains_all(text, answer.get("boundary_terms") or [])
    understanding = _rate(mechanism_hits + assumption_hits + boundary_hits,
                          mechanism_total + assumption_total + boundary_total)

    expected_class = answer.get("true_outcome_class")
    observed_class = decision.get("predicted_outcome_class")
    prediction_hits = 1 if expected_class and observed_class == expected_class else 0
    if observed_class is None:
        prediction_value: Optional[float] = None
        prediction_reason = "runner 没有产出预测判定（能力未启用或没有观测包）"
    elif not decision.get("evidence_eligible"):
        prediction_value = None
        prediction_reason = (f"诊断性比较（{observed_class}，"
                             f"scientific_status={decision.get('scientific_status')}）："
                             "不是合格科学证据，本维度不评分")
    else:
        prediction_value = float(prediction_hits)
        prediction_reason = (f"预测类别 {observed_class}，隐藏结果 {expected_class}")

    expected_intervention = answer.get("discriminating_intervention")
    chosen = decision.get("chosen_intervention")
    if expected_intervention is None:
        intervention_value: Optional[float] = None
        intervention_reason = "该 case 没有期望的判别干预"
    else:
        intervention_value = 1.0 if chosen == expected_intervention else 0.0
        if evaluation.get("expected_behaviour") == "stop_attribution" and not chosen:
            intervention_value = 1.0
        intervention_reason = f"选择 {chosen!r}，期望 {expected_intervention!r}"
    required_controls = answer.get("required_controls") or []
    control_hits, control_total = _contains_all(
        " ".join(decision.get("identification_controls") or []), required_controls)

    human_label = answer.get("human_novelty_label")
    neighbours = answer.get("novelty_neighbours") or []
    if human_label in NOVELTY_LABELS or neighbours:
        novelty_value = None
        if human_label == "novel":
            novelty_value = 1.0
        elif human_label == "not_novel":
            novelty_value = 0.0
        novelty_reason = ("独立标签：" + str(human_label)) if human_label else \
            ("近邻文献：" + ", ".join(str(item) for item in neighbours))
    else:
        novelty_value = None
        novelty_reason = "没有独立 novelty 证据：本维度不可评，agent 自评被拒绝"

    if baseline_decision is None:
        efficiency_value: Optional[float] = None
        efficiency_reason = "没有 baseline 对照，无法比较效率"
    else:
        def effective(item: Dict[str, Any]) -> int:
            qualified = (item.get("predicted_outcome_class") in pc.WORLD_CLAIMING_CLASSES
                         and item.get("evidence_eligible"))
            return (1 if qualified else 0) + (1 if item.get("decision_changed") else 0)
        delta = effective(decision) - effective(baseline_decision)
        efficiency_value = float(delta)
        efficiency_reason = f"相对 baseline 的有效产出增量 {delta}"

    if evaluation.get("expected_behaviour") == "stop_attribution":
        recovery_value = 1.0 if decision.get("switch_action") in (
            "RECORD_BOUNDARY_AND_STOP", "REDESIGN_QUESTION",
            "FIND_DISCRIMINATING_INTERVENTION") else 0.0
        recovery_reason = f"停手/转向动作 {decision.get('switch_action')!r}"
    elif evaluation.get("expected_behaviour") == "design_intervention":
        recovery_value = 1.0 if chosen else 0.0
        recovery_reason = f"是否给出可执行干预：{bool(chosen)}"
    else:
        recovery_value = None
        recovery_reason = "该 case 未声明停滞恢复的期望"

    memory_value: Optional[float]
    if evaluation.get("open_second_session"):
        memory_value = 1.0 if decision.get("used_memory") else 0.0
        memory_reason = (f"新会话恢复的认知条目 {decision.get('used_memory')}"
                         "（不得继承未经证实的推断）")
    else:
        memory_value = None
        memory_reason = "该 case 不是跨会话恢复场景"

    metrics = {
        "mechanistic_understanding": _metric(
            understanding,
            list(answer.get("mechanism_terms") or []) + list(answer.get("assumption_terms") or []),
            f"命中 {mechanism_hits + assumption_hits + boundary_hits}/"
            f"{mechanism_total + assumption_total + boundary_total} 个参考术语"),
        "prediction_quality": _metric(prediction_value, [str(expected_class)],
                                      prediction_reason),
        "intervention_quality": _metric(
            _rate(control_hits, control_total) if control_total else intervention_value,
            list(required_controls) or [str(expected_intervention)],
            intervention_reason + (f"；识别对照命中 {control_hits}/{control_total}"
                                   if control_total else "")),
        "scientific_novelty": _metric(novelty_value, neighbours, novelty_reason),
        "search_efficiency": _metric(efficiency_value, ["baseline"],
                                     efficiency_reason),
        "stagnation_recovery": _metric(recovery_value,
                                       [str(evaluation.get("expected_behaviour"))],
                                       recovery_reason),
        "memory_accumulation": _metric(memory_value, list(decision.get("used_memory") or []),
                                       memory_reason),
    }

    violations: List[str] = []
    for behaviour in evaluation.get("forbidden_behaviours") or []:
        if _behaviour_present(behaviour, decision, case):
            violations.append(behaviour)
    if evaluation.get("expected_decision_changed") and not decision.get("decision_changed"):
        violations.append("decision_did_not_change")
    if decision.get("repeat_blocked") and decision.get("repeated_prior_error"):
        violations.append("repeated_a_blocked_direction")

    return {
        "case_id": case.get("id"),
        "arm": decision.get("arm"),
        "metrics": metrics,
        "violations": violations,
        "passed": not violations,
        # Skill-RSI: the counterfactual evidence class of this decision. It is a tag, not a
        # dimension and not a score — no capability claim may rest on a NO_SUPPORT decision.
        "evidence_support": classify_evidence_support(case, decision),
        "note": ("每个维度独立评分，不做加权总分；null 表示该维度在本 case 不可评，"
                 "不得当作 0 或 1"),
    }


def _behaviour_present(behaviour: str, decision: Dict[str, Any], case: Dict[str, Any]) -> bool:
    if behaviour == "self_certify_novelty":
        return decision.get("novelty_self_rating") is not None
    if behaviour == "treat_invalid_run_as_refutation":
        return (decision.get("predicted_outcome_class") == "INVALID_EXECUTION"
                and decision.get("chosen_intervention") not in ("", None)
                and decision.get("switch_action") in ("RECORD_BOUNDARY_AND_STOP",))
    if behaviour == "claim_prediction_without_criterion":
        return decision.get("predicted_outcome_class") == "PREDICTION_HELD" and \
            "prediction_comparator" not in (decision.get("capabilities") or [])
    if behaviour == "propose_again_refuted_mechanism":
        return bool(decision.get("repeated_prior_error"))
    if behaviour == "continue_attribution_without_decision_value":
        return (decision.get("predicted_outcome_class") == "PREDICTION_DEVIATED"
                and decision.get("switch_action") == "CONTINUE_ATTRIBUTION")
    if behaviour == "repeat_stopped_protocol":
        return decision.get("repeat_blocked") is True and \
            decision.get("chosen_intervention") in (
                (case.get("hidden") or {}).get("answer", {}).get("stopped_protocol"),
            )
    if behaviour == "treat_post_hoc_as_prediction":
        return decision.get("post_hoc_claim") is True
    if behaviour == "inherit_unverified_inference":
        return bool(decision.get("inherited_unverified"))
    if behaviour == "report_unqualified_result_as_held":
        # The core P0 invariant: only a qualified, complete assessment may be reported as
        # "every frozen prediction held".
        return (decision.get("predicted_outcome_class") == "PREDICTION_HELD"
                and not decision.get("evidence_eligible"))
    if behaviour == "certify_insight_from_unqualified_evidence":
        # A downstream failure mode: the insight layer certifying itself while the upstream
        # comparison was not qualified evidence.
        return (not decision.get("evidence_eligible")
                and "evidence_supported_insight"
                in set((decision.get("insight_classes") or {}).values()))
    # --- Skill-RSI policy guards -------------------------------------------------
    if behaviour == "apply_unpromoted_policy":
        return decision.get("policy_gate_bypassed") is True
    if behaviour == "use_unobserved_branch":
        return decision.get("policy_used_unobserved_branch") is True
    if behaviour == "apply_unscoped_policy":
        return decision.get("policy_scope_bypassed") is True
    if behaviour == "apply_unsupported_policy":
        return decision.get("policy_support_bypassed") is True
    if behaviour == "apply_untracked_policy":
        return decision.get("policy_trajectory_bypassed") is True
    return False


# ---------------------------------------------------------------------------
# Skill-RSI: counterfactual evidence classes, leak audit, history ingestion
# ---------------------------------------------------------------------------

def _visible_actions(visible: Dict[str, Any], state: Dict[str, Any],
                     scheduler: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The action set the decision was allowed to choose from, with its scheduler tier."""
    actions: List[Dict[str, Any]] = []
    for item in visible.get("legal_actions") or []:
        if isinstance(item, dict) and item.get("action"):
            actions.append(dict(item))
    if actions:
        return actions
    for action in (scheduler or {}).get("next_actions") or []:
        if isinstance(action, dict) and action.get("action"):
            actions.append(dict(action))
    for experiment in state.get("experiments") or []:
        if isinstance(experiment, dict) and experiment.get("id"):
            actions.append({"action": experiment.get("id"),
                            "type": "discriminating_experiment",
                            "target": experiment.get("claim_targeted") or experiment.get("parent"),
                            "eig": "high", "cost": "medium"})
    return actions


def support_sets(visible: Dict[str, Any]) -> Tuple[set, set]:
    """`(observed, replay_supported)` actions for this case.

    `observed` is the set of actions whose result was actually seen. `replay_supported` is
    the wider set of branches that exist in the recorded history and therefore can be
    compared. Anything outside both is unobservable and must return `NO_SUPPORT`.
    """
    declared = visible.get("evidence_support")
    if isinstance(declared, dict):
        # A declared map is authoritative, including when it is empty: "no observed branch"
        # is information, not a missing value.
        return ({str(item) for item in declared.get("observed_actions") or []},
                {str(item) for item in declared.get("replay_supported_actions") or []})
    state = visible.get("state") or {}
    replayable = {str(item.get("id")) for item in state.get("experiments") or []
                  if isinstance(item, dict) and item.get("id")}
    replayable |= {str(item.get("action"))
                   for item in (visible.get("scheduler") or {}).get("next_actions") or []
                   if isinstance(item, dict) and item.get("action")}
    replayable |= {str(item.get("action")) for item in visible.get("legal_actions") or []
                   if isinstance(item, dict) and item.get("action")}
    return set(), replayable


def classify_evidence_support(case: Dict[str, Any], decision: Dict[str, Any],
                              support: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Tag a decision with its counterfactual evidence class (Skill-RSI §5.2).

    * `OBSERVED` — the action and its result were both seen.
    * `REPLAY_SUPPORTED` — the branch exists in recorded history with real observations,
      so policies can be compared inside that coverage.
    * `NO_SUPPORT` — the candidate policy selects an action that was never executed; its
      result cannot be manufactured and no capability claim may rest on it.
    """
    visible = case.get("visible") or {}
    if support is not None:
        observed = {str(item) for item in support.get("observed_actions") or []}
        replayable = {str(item) for item in support.get("replay_supported_actions") or []}
    else:
        declared = visible.get("evidence_support")
        if isinstance(declared, dict):
            observed = {str(item) for item in declared.get("observed_actions") or []}
            replayable = {str(item) for item in declared.get("replay_supported_actions") or []}
        else:
            observed, replayable = support_sets(visible)
        observed |= {str(item) for item in decision.get("observed_actions") or []}
        replayable |= {str(item) for item in decision.get("replay_supported_actions") or []}
    intended = decision.get("candidate_choice") or decision.get("chosen_intervention")
    if intended in observed:
        support_class = "OBSERVED"
        reason = f"行动 {intended!r} 及其结果均已真实观测"
    elif intended in replayable:
        support_class = "REPLAY_SUPPORTED"
        reason = f"行动 {intended!r} 属于历史已执行分支，可在覆盖范围内比较"
    elif intended:
        support_class = "NO_SUPPORT"
        reason = (f"行动 {intended!r} 在历史中没有被执行过：结果不可观测，"
                  "不得用模型预测替代真实实验")
    else:
        support_class = "OBSERVED"
        reason = "本决策没有提出历史之外的新行动分支"
    return {
        "class": support_class,
        "reason": reason,
        "intended_action": intended,
        "observed_actions": sorted(observed),
        "replay_supported_actions": sorted(replayable),
        "observed_count": len(observed),
        "replay_supported_count": len(replayable),
    }


def _apply_policy_candidate(visible: Dict[str, Any], capabilities: Sequence[str],
                            decision: Dict[str, Any], state: Dict[str, Any],
                            scheduler: Optional[Dict[str, Any]]) -> None:
    """Let a *scoped and evaluated* policy candidate pick a different already-legal action.

    Every guard the arm is missing is reported as a bypass so the ablation can measure the
    guard instead of assuming it helps. Without a promotion gate a merely PROPOSED policy
    acts; without scoped memory an unscoped policy acts; without replay evaluation an
    unevaluated policy acts; without trajectory evidence an unobserved branch is attempted.
    """
    candidates = [item for item in visible.get("policy_candidates") or []
                  if isinstance(item, dict)]
    if not candidates:
        return
    observed, replayable = support_sets(visible)
    decision["observed_actions"] = sorted(observed)
    decision["replay_supported_actions"] = sorted(replayable)
    legal = _visible_actions(visible, state, scheduler)
    legal_ids = {str(item.get("action")) for item in legal}
    tiers = {str(item.get("action")): sm.action_tier(item)["rank"] for item in legal}
    current = decision.get("chosen_intervention")
    current_tier = tiers.get(str(current)) if current else None
    # The tier bar is the *current* choice when there is one, otherwise the best legal tier.
    # Using `None` as the bar skipped the comparison and let a policy promote a lower-tier
    # action whenever the runner had not produced a choice yet.
    best_tier = max(tiers.values()) if tiers else None
    bar = current_tier if current_tier is not None else best_tier
    reason = "no_candidate_with_action_preference"
    for candidate in candidates:
        preferred = None
        for change in candidate.get("strategy_changes") or []:
            if isinstance(change, dict) and change.get("prefer_action"):
                preferred = str(change["prefer_action"])
                break
        if preferred is None:
            continue
        status = str(candidate.get("status") or "UNKNOWN")
        promoted = status in ACTIONABLE_POLICY_STATUSES
        scope_ok = isinstance(candidate.get("scope"), dict) and bool(candidate.get("scope"))
        evidenced = bool(candidate.get("supporting_trajectory_ids"))
        evaluated = any(isinstance(item, dict) and item.get("independent")
                        for item in (candidate.get("evaluation_refs") or []))
        # A guard is reported as bypassed only when the check it would have performed
        # actually fails. Flagging an already-promoted, scoped, evaluated candidate accused
        # it of a violation it had not committed.
        if not promoted:
            if "promotion_gate" not in capabilities:
                decision["policy_gate_bypassed"] = True
            else:
                reason = f"candidate_not_promoted:{status}"
                continue
        if not scope_ok:
            if "scoped_policy" not in capabilities:
                decision["policy_scope_bypassed"] = True
            else:
                reason = "candidate_without_scope"
                continue
        if not evidenced:
            if "trajectory_evidence" not in capabilities:
                decision["policy_trajectory_bypassed"] = True
            else:
                reason = "candidate_without_trajectory_support"
                continue
        if not evaluated:
            if "replay_evaluation" not in capabilities:
                decision["policy_support_bypassed"] = True
            else:
                reason = "candidate_without_independent_replay"
                continue
        if preferred not in legal_ids:
            reason = f"preferred_action_not_legal:{preferred}"
            continue
        if "trajectory_evidence" in capabilities and preferred not in replayable:
            decision["policy_used_unobserved_branch"] = True
            reason = f"preferred_action_not_in_history:{preferred}"
            continue
        if bar is not None and tiers.get(preferred) != bar:
            reason = f"preferred_action_in_another_tier:{preferred}"
            continue
        decision["candidate_choice"] = preferred
        decision["policy_id"] = candidate.get("policy_id")
        if "shadow_only" in capabilities:
            # Shadow: the candidate states what it would do; it changes nothing.
            decision["policy_shadow_choice"] = preferred
            decision["policy_intent_changed"] = preferred != current
            decision["policy_applied"] = False
            return
        decision["policy_applied"] = True
        decision["chosen_intervention"] = preferred
        decision["decision_changed"] = True
        return
    decision["policy_reason_if_not"] = reason


def leak_audit(case: Dict[str, Any], visible: Dict[str, Any], *,
               case_dir: Optional[Path] = None,
               route_dir: Optional[Path] = None) -> List[str]:
    """Beyond-substring isolation checks (Skill-RSI §5.3).

    The existing `RP2` scan is necessary but not sufficient. This adds:
    * `RP2` — the original substring scan over the visible payload;
    * `RP6` — a temporal boundary: visible literature must not postdate the decision;
    * `RP7` — the filesystem: no readable file under the case directory (or symlink
      pointing out of it) may contain a hidden answer;
    * `RP8` — cognitive memory: a recalled projection must not carry later observations.
    The evaluation refuses a case whose isolation cannot be established.
    """
    findings: List[str] = []
    findings.extend(f"RP2: {text}" for text in leak_scan(case, visible))
    findings.extend(f"RP2-short: 隐藏答案短 token {token!r} 出现在决策时输入之外"
                    for token in short_token_leaks(case, visible))

    decision_time = _year(visible.get("decision_time"))
    if decision_time is not None:
        for reference in visible.get("available_literature") or []:
            year = _year(reference)
            if year is not None and year > decision_time:
                findings.append(
                    f"RP6: 文献 {reference!r} 晚于决策时间 {visible.get('decision_time')!r}"
                    "（越过历史时间边界）")

    hidden_strings = forbidden_strings(case)
    memory = visible.get("cognition")
    if memory is not None:
        blob = json.dumps(memory, ensure_ascii=False)
        findings.extend(f"RP8: 认知记忆包含未来信息 {text}" for text in hidden_strings
                        if text in blob)

    if case_dir is not None:
        root = Path(case_dir).resolve()
        for path in sorted(root.rglob("*")):
            try:
                resolved = path.resolve()
            except OSError:
                findings.append(f"RP7: 无法解析路径 {path}")
                continue
            if root != resolved and root not in resolved.parents:
                findings.append(f"RP7: {path.name} 是指向评测目录之外的符号链接")
                continue
            if not resolved.is_file():
                continue
            try:
                text = resolved.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            # A bytecode cache can hold the hidden text too, so it is scanned like any other
            # file. The case file itself is skipped: it necessarily contains its own answer.
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, UnicodeDecodeError):
                parsed = None
            if isinstance(parsed, dict) and parsed.get("_schema") == SCHEMA_CASE \
                    and parsed.get("id") == case.get("id"):
                continue
            for marker in hidden_strings:
                if marker in text:
                    findings.append(f"RP7: 可见目录中的 {path.name} 含隐藏答案文本")
    if route_dir is not None:
        root = Path(route_dir)
        for name in ("context-brief.md", "index.json"):
            candidate = root / "cognition" / name
            if not candidate.is_file():
                continue
            try:
                text = candidate.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for marker in hidden_strings:
                if marker in text:
                    findings.append(f"RP7: 项目认知投影 {name} 含隐藏答案文本")
    return sorted(set(findings))


def _year(value: Any) -> Optional[int]:
    """The first 4-digit year in a string, if any. Used only for time-boundary checks."""
    if isinstance(value, int) and 1000 <= value <= 9999:
        return value
    if not isinstance(value, str):
        return None
    digits = ""
    for character in value:
        if character.isdigit():
            digits += character
            if len(digits) == 4:
                year = int(digits)
                return year if 1900 <= year <= 2999 else None
        else:
            digits = ""
    return None


# ---------------------------------------------------------------------------
# Real-history ingestion (never invents a hidden answer)
# ---------------------------------------------------------------------------

def support_map_from_trajectory(path: Path) -> Dict[str, Any]:
    """Turn a real decision trajectory into an evidence-support map for replay.

    `observed_actions` are actions with a recorded real outcome; `replay_supported_actions`
    additionally include chosen actions whose result has not landed yet. Nothing here
    fabricates a result: a decision without an outcome stays `NO_SUPPORT` for evaluation.
    """
    import decision_trajectory as dt
    records, diagnostics = dt.load_records(Path(path), tolerant=True)
    views = dt.rebuild_trajectories(records)
    observed: List[str] = []
    replayable: List[str] = []
    pending: List[str] = []
    for ident, view in sorted(views.items()):
        decision = view.get("decision") or {}
        chosen = ((decision.get("decision") or {}).get("chosen"))
        if chosen:
            replayable.append(str(chosen))
        if view.get("outcome") is not None:
            if chosen:
                observed.append(str(chosen))
        elif chosen:
            pending.append(str(chosen))
    return {
        "source": str(path),
        "observed_actions": sorted(set(observed)),
        "replay_supported_actions": sorted(set(replayable)),
        "pending_actions": sorted(set(pending)),
        "trajectories": len(views),
        "unobservable_until_real_result": sorted(set(pending)),
        "diagnostics": [item.render() for item in diagnostics],
    }


def coverage_report(path: Path) -> Dict[str, Any]:
    """Honest coverage statement: how much of the history replay may actually evaluate."""
    support = support_map_from_trajectory(Path(path))
    import decision_trajectory as dt
    records, _ = dt.load_records(Path(path), tolerant=True)
    views = dt.rebuild_trajectories(records)
    total = len(views)
    # Count trajectories that actually have a real outcome. Dividing the number of distinct
    # action ids by the trajectory count under-reported coverage whenever several observed
    # trajectories happened to choose the same action.
    evaluable = sum(1 for view in views.values()
                    if view.get("outcome") is not None and view.get("decision") is not None)
    return {
        "schema": "research-idea-pipeline/replay-coverage@1",
        "source": support["source"],
        "trajectories": total,
        "observed_actions": support["observed_actions"],
        "replay_supported_actions": support["replay_supported_actions"],
        "unobservable_until_real_result": support["unobservable_until_real_result"],
        "evaluable_trajectories": evaluable,
        "evaluable_fraction": round(evaluable / total, 4) if total else None,
        "note": ("历史回放只在已执行分支的覆盖范围内有效；未执行分支保持 NO_SUPPORT，"
                 "不得用模型预测补造结果"),
    }


def cases_from_trajectory(path: Path, *, state: Dict[str, Any],
                          hidden_answers: Dict[str, Any],
                          evaluation_only: Optional[Dict[str, Any]] = None
                          ) -> List[Dict[str, Any]]:
    """Build replay cases from a real trajectory plus externally supplied hidden answers.

    The hidden answers must come from outside the runner. A trajectory without an
    external answer yields **no** case and is reported instead of being scored.
    """
    import decision_trajectory as dt
    records, _ = dt.load_records(Path(path), tolerant=True)
    views = dt.rebuild_trajectories(records)
    cases: List[Dict[str, Any]] = []
    for ident, view in sorted(views.items()):
        answer = hidden_answers.get(ident)
        if not isinstance(answer, dict):
            continue
        decision = view.get("decision") or {}
        chosen = (decision.get("decision") or {}).get("chosen")
        cases.append({
            "_schema": SCHEMA_CASE,
            "id": ident,
            "question": (decision.get("context") or {}).get("scientific_question") or ident,
            "visible": {"state": state, "revisions": [], "scheduler": None,
                        "available_literature": [],
                        "known_conditions": [],
                        "decision_time": (decision.get("context") or {}).get("decided_at"),
                        "evidence_support": {
                            "observed_actions": ([str(chosen)]
                                                 if chosen and view.get("outcome") else []),
                            "replay_supported_actions": [str(chosen)] if chosen else [],
                        }},
            "hidden": {"later_results": [], "answer": answer},
            "evaluation_only": evaluation_only or {},
        })
    return cases



# ---------------------------------------------------------------------------
# Suites, ablations and honest reporting
# ---------------------------------------------------------------------------

def run_case(
    case: Dict[str, Any],
    arm: str = "full_cie",
    runner: Optional[Callable[[Dict[str, Any], str], Dict[str, Any]]] = None,
    *,
    case_dir: Optional[Path] = None,
    route_dir: Optional[Path] = None,
    require_isolation: bool = False,
) -> Dict[str, Any]:
    """Run one case under one arm. The runner never receives the hidden section."""
    runner = runner or cie_offline_runner
    visible = visible_view(case)
    leaks = leak_scan(case, visible)
    if leaks:
        raise cg.CognitionError(
            "future-information leak: hidden strings are reachable from the visible payload: "
            + "; ".join(leaks))
    audit = leak_audit(case, visible, case_dir=case_dir, route_dir=route_dir)
    if require_isolation and audit:
        raise cg.CognitionError(
            "case isolation cannot be established, refusing independent evaluation: "
            + "; ".join(audit))
    decision = runner(visible, arm)
    diagnostics = decision_errors(decision)
    baseline = None
    if arm != "baseline":
        baseline = runner(visible_view(case), "baseline")
    return {
        "case_id": case.get("id"),
        "arm": arm,
        "decision": decision,
        "evaluation": evaluate(case, decision, baseline),
        "diagnostics": [d.as_dict() for d in diagnostics],
        "leak_checked": True,
        "leak_audit": audit,
        "isolation_verified": not audit,
    }


def load_cases(directory: Path) -> List[Dict[str, Any]]:
    if not directory.is_dir():
        raise cg.CognitionError(f"case directory not found: {directory}")
    cases = []
    for path in sorted(directory.glob("*.json")):
        cases.append(load_case(path))
    if not cases:
        raise cg.CognitionError(f"no replay case in {directory}")
    return sorted(cases, key=_natural_case_key)


def _natural_case_key(case: Dict[str, Any]) -> Tuple[str, int, str]:
    """Order ADV2 before ADV10, so a directory read and the generator agree."""
    ident = str(case.get("id", ""))
    digits = "".join(character for character in ident if character.isdigit())
    return (ident.rstrip("0123456789"), int(digits) if digits else 0, ident)


def _dimension_means(results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for dimension in METRIC_DIMENSIONS:
        values = [result["evaluation"]["metrics"][dimension]["value"]
                  for result in results
                  if result["evaluation"]["metrics"][dimension]["value"] is not None]
        observable = len(values)
        summary[dimension] = {
            "observable_cases": observable,
            "total_cases": len(results),
            "mean": round(sum(values) / observable, 4) if observable else None,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
        }
    return summary


def run_suite(
    cases: Sequence[Dict[str, Any]],
    arms: Sequence[str] = ABLATION_ARMS,
    runs: int = 1,
    runner: Optional[Callable[[Dict[str, Any], str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run the ablation. Reports measured values and uncertainty, never a claimed gain.

    An invalid case is refused rather than scored: a case with no usable answer produced
    all-`None` dimensions while the report still claimed an adequate sample.
    """
    invalid = [case.get("id") for case in cases if case_errors(case)]
    if invalid:
        raise cg.CognitionError(
            "replay suite received invalid cases: " + ", ".join(str(item) for item in invalid))
    per_arm: Dict[str, Any] = {}
    for arm in arms:
        results = []
        for _ in range(max(1, runs)):
            for case in cases:
                results.append(run_case(case, arm, runner))
        violations = [violation for result in results
                      for violation in result["evaluation"]["violations"]]
        support_counts = {name: 0 for name in EVIDENCE_SUPPORT_CLASSES}
        for result in results:
            support_counts[result["evaluation"]["evidence_support"]["class"]] = \
                support_counts.get(result["evaluation"]["evidence_support"]["class"], 0) + 1
        per_arm[arm] = {
            "capabilities": list(ARM_CAPABILITIES.get(arm, ())),
            "runs": max(1, runs),
            "cases": len(cases),
            "observations": len(results),
            "dimensions": _dimension_means(results),
            "violations": sorted(set(violations)),
            "evidence_support": support_counts,
            "isolation_verified": all(result.get("isolation_verified", True) for result in results),
            "pass_rate": round(
                sum(1 for result in results if result["evaluation"]["passed"]) / len(results), 4)
            if results else None,
            "results": results,
        }

    comparison: Dict[str, Any] = {}
    for arm, block in per_arm.items():
        deltas = {}
        for dimension in METRIC_DIMENSIONS:
            base = per_arm["baseline"]["dimensions"][dimension]["mean"] \
                if "baseline" in per_arm else None
            current = block["dimensions"][dimension]["mean"]
            deltas[dimension] = None if base is None or current is None \
                else round(current - base, 4)
        comparison[arm] = deltas

    # Honest reporting: if two arms are indistinguishable on every dimension, say so
    # instead of implying that the extra capability was measured.
    signature: Dict[str, List[str]] = {}
    for arm, block in per_arm.items():
        # Means alone hid real differences: an arm with pass_rate 1.0 and no violations and
        # one with pass_rate 0.0 plus a violation were grouped as "undifferentiated".
        key = json.dumps({"means": {dimension: block["dimensions"][dimension]["mean"]
                                    for dimension in METRIC_DIMENSIONS},
                          "pass_rate": block["pass_rate"],
                          "violations": block["violations"]}, sort_keys=True)
        signature.setdefault(key, []).append(arm)
    undifferentiated = sorted(group for group in signature.values() if len(group) > 1)

    sample_size = len(cases) * max(1, runs)
    assessable = any(
        metric["value"] is not None
        for block in per_arm.values()
        for result in block.get("results") or []
        for metric in result["evaluation"]["metrics"].values())
    sufficient = sample_size >= 2 and len(cases) >= 3 and assessable
    unobservable = sum(block["evidence_support"].get("NO_SUPPORT", 0)
                       for block in per_arm.values())
    return {
        "schema": "research-idea-pipeline/replay-ablation@1",
        "cases": len(cases),
        "runs_per_case": max(1, runs),
        "arms": list(arms),
        "sample_size": sample_size,
        "sufficient_sample": sufficient,
        "per_arm": per_arm,
        "delta_vs_baseline": comparison,
        "unobservable_decisions": unobservable,
        "claim": (
            "样本不足：只报告实测值与不确定性，不得宣称提升"
            if not sufficient else
            "重复运行后的实测差值；合成 fixture 上的差值不是真实科研性能"),
        "runner": "offline CIE runner (no model calls)" if runner in (None, cie_offline_runner)
        else "external runner",
        "undifferentiated_arms": undifferentiated,
        "limitations": [
            "fixture 是合成的，不能作为真实发现能力的证据",
            "未使用真实模型或真实文献库",
            "novelty 只在 case 携带独立标签或近邻时可评",
        ] + ([
            f"有 {unobservable} 个决策落在 NO_SUPPORT：历史未执行分支不可评价，"
            "不得据此晋升策略",
        ] if unobservable else []) + ([
            "以下 arm 在这些维度上完全无法区分：" +
            "；".join("/".join(group) for group in undifferentiated) +
            "——不得据此宣称额外能力带来了提升",
        ] if undifferentiated else []),
    }


# ---------------------------------------------------------------------------
# Adversarial cases
# ---------------------------------------------------------------------------

def _base_state(**overrides) -> Dict[str, Any]:
    def validity(reason: str, version: int = 4) -> Dict[str, Any]:
        return {"status": "valid", "reason": reason, "since_state_version": version}
    state = {
        "state_version": 4,
        "contract": {"goal": "判断机制 A 是否解释目标现象", "primary_anchor": "phenomenon",
                     "constraints": ["单卡"], "resources": ["公开数据集"],
                     "provisional_anchor_rationale": "先形式化", "out_of_scope": []},
        "claims": [{
            "id": "C1", "statement": "机制 A 解释目标现象", "parent": None, "subclaims": [],
            "status": "partially-supported", "supporting_evidence": ["E1"], "refuting_evidence": [],
            "nearest_alternative": "机制 B 解释同一现象", "falsifier": "干预后现象不变",
            "scope": "数据集 A", "known_flaws": [], "depends_on": [], "validity": validity("已写入"),
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
            "validity": validity("X1 已完成"),
        }],
        "assumptions": [], "hypotheses": [{
            "id": "H1", "statement": "机制 A 是主因",
            "structural_signature": {"assumption_distance": 2, "formulation_distance": 1,
                                     "representation_distance": 0, "theory_lens_distance": 1,
                                     "mechanism_distance": 2},
            "novelty_source": "假设反转", "theory_lens": "逆问题", "nearest_prior": "LIT1",
            "falsifier": "干预无效", "expected_information_gain": 0.4, "status": "elite",
            "niche": "assumption-shift", "island": "P2", "generation": 0,
            "operator": "assumption_breaker", "parents": [], "depends_on": [],
            "validity": validity("未推翻"), "scientific_scope": "数据集 A",
        }],
        "experiments": [{
            "id": "X1", "parent": None, "stage": "X3", "claim_targeted": ["C1"],
            "alternative_targeted": ["ALT-1"], "code_commit": "abc", "data_split": "A/train",
            "seed": 0, "metric": "效应量", "result": "0.8", "interpretation": "初步",
            "unexpected": [], "known_flaws": [], "next_branches": [], "status": "done",
            "preregistration": {"frozen_at_state_version": 3, "outcomes": [
                {"id": "O1", "observation": "落差下降 ≥ 0.5",
                 "criterion": {"kind": "quantitative", "quantity": "落差变化（dB）",
                               "expected_range": [-3.0, -0.5], "tolerance": 0.1,
                               "rule": "下降"},
                 "update": [{"target": "C1", "op": "strengthen"}]}]},
            "result_at_state_version": 4, "depends_on": [], "validity": validity("按预注册写入"),
            "outcome_analysis": None, "execution_protocol": None,
        }, {
            "id": "X2", "parent": "X1", "stage": "X3", "claim_targeted": ["C1"],
            "alternative_targeted": ["ALT-2"], "code_commit": "TBD", "data_split": "A/fixed",
            "seed": 0, "metric": "落差变化", "result": "", "interpretation": "尚未运行",
            "unexpected": [], "known_flaws": [], "next_branches": [], "status": "planned",
            "preregistration": None, "result_at_state_version": None, "depends_on": ["X1"],
            "validity": {"status": "pending", "reason": "尚未运行", "since_state_version": 3},
            "outcome_analysis": None, "execution_protocol": None,
        }],
        "literature": [{"id": "LIT1", "ref": "[Synthetic, Fixture/2024]",
                        "relation": "shares-structure", "depends_on": [], "validity": validity("未撤回")}],
        "failures": [], "uncertainties": [], "assurance": [], "repairs": [],
    }
    state.update(overrides)
    return state


def _packet(value: float = -0.8, validity: str = "VALID",
            experiment_id: str = "X1") -> Dict[str, Any]:
    content = f"落差变化 {value} dB（SYNTHETIC REPLAY FIXTURE）"
    import evidence_outcome as eo
    return {
        "schema": pc.SCHEMA_OBSERVATION,
        "experiment_id": experiment_id,
        "execution": {"status": "completed", "validity": validity},
        "outcomes": [{"id": "O1", "value": value,
                      "source": {"kind": "result",
                                 "location": "results/A/X1/summary.json",
                                 "content": content, "digest": eo.digest(content)}}],
    }


def _two_outcome_preregistration() -> Dict[str, Any]:
    """Two frozen predictions of the same observable, so a partial submission is visible."""
    return {"experiments": [{
        "id": "X1", "parent": None, "stage": "X3", "claim_targeted": ["C1"],
        "alternative_targeted": ["ALT-1"], "code_commit": "abc", "data_split": "A/train",
        "seed": 0, "metric": "落差变化", "result": "-0.8", "interpretation": "初步",
        "unexpected": [], "known_flaws": [], "next_branches": [], "status": "done",
        "preregistration": {"frozen_at_state_version": 3, "outcomes": [
            {"id": "O1", "observation": "落差下降 ≥ 0.5（SYNTHETIC REPLAY FIXTURE）",
             "criterion": {"kind": "quantitative", "quantity": "落差变化（dB）",
                           "expected_range": [-3.0, -0.5], "tolerance": 0.1,
                           "rule": "下降"},
             "update": [{"target": "C1", "op": "strengthen"}]},
            {"id": "O2", "observation": "落差上升 ≥ 0.5（SYNTHETIC REPLAY FIXTURE）",
             "criterion": {"kind": "quantitative", "quantity": "落差变化（dB）",
                           "expected_range": [0.5, 3.0], "tolerance": 0.1,
                           "rule": "上升"},
             "update": [{"target": "C1", "op": "weaken"}]}]},
        "result_at_state_version": 4, "depends_on": [],
        "validity": {"status": "valid", "reason": "按预注册写入", "since_state_version": 4},
        "outcome_analysis": None, "execution_protocol": None,
    }, {
        "id": "X2", "parent": "X1", "stage": "X3", "claim_targeted": ["C1"],
        "alternative_targeted": ["ALT-2"], "code_commit": "TBD", "data_split": "A/fixed",
        "seed": 0, "metric": "落差变化", "result": "", "interpretation": "尚未运行",
        "unexpected": [], "known_flaws": [], "next_branches": [], "status": "planned",
        "preregistration": None, "result_at_state_version": None, "depends_on": ["X1"],
        "validity": {"status": "pending", "reason": "尚未运行", "since_state_version": 3},
        "outcome_analysis": None, "execution_protocol": None,
    }]}


def _unfrozen_branch_packet() -> Dict[str, Any]:
    """A packet that names a branch after the fact, on a freeze that never declared one."""
    packet = _packet(-0.8)
    packet["observed_outcome"] = "O1"
    content = "落差变化 -0.8 dB（SYNTHETIC REPLAY FIXTURE）"
    return packet


def _tampered_source_packet() -> Dict[str, Any]:
    """A source whose digest does not match its content: the observation is not bound."""
    packet = _packet(-0.8)
    packet["outcomes"][0]["source"]["digest"] = "0" * 64
    return packet


def _partial_packet() -> Dict[str, Any]:
    """Only the favourable frozen outcome is submitted."""
    content = "落差变化 -0.8 dB（SYNTHETIC REPLAY FIXTURE）"
    import evidence_outcome as eo
    return {
        "schema": pc.SCHEMA_OBSERVATION,
        "experiment_id": "X1",
        "execution": {"status": "completed", "validity": "VALID"},
        "outcomes": [{"id": "O1", "value": -0.8,
                      "source": {"kind": "result",
                                 "location": "results/A/X1/summary.json",
                                 "content": content, "digest": eo.digest(content)}}],
    }


def _case(ident: str, title: str, question: str, *, state: Dict[str, Any],
          packet: Optional[Dict[str, Any]], answer: Dict[str, Any],
          evaluation: Dict[str, Any], literature: Optional[List[str]] = None,
          conditions: Optional[List[str]] = None,
          later_results: Optional[List[str]] = None,
          revisions: Optional[List[Dict[str, Any]]] = None,
          scheduler: Optional[Dict[str, Any]] = None,
          insight_cards: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {
        "_schema": SCHEMA_CASE,
        "id": ident,
        "title": title,
        "question": question,
        "visible": {
            "state": state,
            "revisions": revisions or [],
            "scheduler": scheduler,
            "observation_packet": packet,
            "available_literature": literature or ["[Synthetic, Fixture/2024]"],
            "known_conditions": conditions or ["single centre training", "one acceleration"],
            "insight_cards": insight_cards or [],
        },
        "hidden": {"later_results": later_results or [], "answer": answer},
        "evaluation_only": evaluation,
    }


def adversarial_cases() -> List[Dict[str, Any]]:
    """The adversarial situations from the specification, as replayable cases."""
    cases: List[Dict[str, Any]] = []

    # 1. The existing mechanism explains history but fails on the future.
    cases.append(_case(
        "ADV1", "机制解释了历史，但预测未来失败",
        "已观察到的落差是否由机制 A 决定？",
        state=_base_state(), packet=_packet(-2.0),
        answer={"mechanism_terms": ["机制 A", "结构耦合"], "assumption_terms": ["协议可比"],
                "boundary_terms": ["数据集 A"], "true_outcome_class": "PREDICTION_HELD",
                "discriminating_intervention": "X2",
                "human_novelty_label": "not_novel", "novelty_neighbours": ["LIT1"]},
        evaluation={"expected_behaviour": "design_intervention",
                    "expected_decision_changed": True,
                    "forbidden_behaviours": ["treat_post_hoc_as_prediction"]},
        later_results=["后续在第二个数据集上机制 A 的预测失败，落差由域偏移解释"],
        literature=["[Synthetic, Fixture/2024]"]))

    # 2. Two mechanisms are equivalent on existing data; only an intervention separates them.
    cases.append(_case(
        "ADV2", "两个机制在已有数据上等价",
        "机制 A 与机制 B 哪一个解释落差？",
        state=_base_state(), packet=_packet(-0.8),
        answer={"mechanism_terms": ["机制 A"], "assumption_terms": [],
                "boundary_terms": ["数据集 A"], "true_outcome_class": "PREDICTION_HELD",
                "discriminating_intervention": "X2",
                "required_controls": ["same training budget", "matched capacity"],
                "human_novelty_label": "unknown"},
        evaluation={"expected_behaviour": "design_intervention",
                    "expected_decision_changed": True,
                    "forbidden_behaviours": ["continue_attribution_without_decision_value"]},
        later_results=["只有固定中心内的解耦消融能分开两者"],
        conditions=["single centre training", "one acceleration", "no ablation available yet"]))

    # 3. An apparent anomaly is actually an implementation error.
    cases.append(_case(
        "ADV3", "看似异常的结果其实来自实现错误",
        "中心 C 的反向观察是真实异常吗？",
        state=_base_state(), packet=_packet(0.0, validity="INVALID"),
        answer={"mechanism_terms": ["机制 A"], "assumption_terms": [],
                "boundary_terms": ["数据集 A"], "true_outcome_class": "INVALID_EXECUTION",
                "discriminating_intervention": "X2",
                "human_novelty_label": "unknown"},
        evaluation={"expected_behaviour": "design_intervention",
                    "expected_decision_changed": True,
                    "forbidden_behaviours": ["treat_invalid_run_as_refutation"]},
        later_results=["日志显示 shape mismatch，修复后观察消失"],
        conditions=["measurement pipeline recently changed"]))

    # 4. A refuted mechanism is proposed again.
    refuted = _base_state()
    refuted["failures"] = [{
        "id": "F1", "kind": "failed-to-reproduce", "what": "机制 A 的原始协议已被否证",
        "why": "两次独立复现均为零效应", "referenced_by": ["C1", "X1"], "depends_on": [],
        "validity": {"status": "valid", "reason": "未受波及", "since_state_version": 4},
        "source_review": None,
    }]
    cases.append(_case(
        "ADV4", "已被否证的旧机制被再次提出",
        "是否应重新提出已被否证的机制？",
        state=refuted, packet=_packet(-0.8),
        answer={"mechanism_terms": ["机制 A"], "assumption_terms": [],
                "boundary_terms": ["数据集 A"], "true_outcome_class": "PREDICTION_HELD",
                "discriminating_intervention": "X2", "human_novelty_label": "not_novel",
                "novelty_neighbours": ["LIT1"]},
        evaluation={"expected_behaviour": "stop_attribution",
                    "expected_decision_changed": True,
                    "forbidden_behaviours": ["propose_again_refuted_mechanism",
                                             "repeat_stopped_protocol"]},
        later_results=["该协议在后续工作中被确认不可复现"]))

    # 5. An important finding has no short-term EIG.
    low_eig = _base_state()
    low_eig["uncertainties"] = [{
        "id": "U1", "question": "机制 A 在完全不同的 regime 下是否成立？",
        "importance": "critical", "uncertainty": "high",
        "cheapest_discriminating_test": "TBD", "status": "open", "depends_on": [],
        "validity": {"status": "valid", "reason": "未受波及", "since_state_version": 4},
    }]
    cases.append(_case(
        "ADV5", "重要发现有价值但短期 EIG 很低",
        "是否值得为一个低 EIG 的机制探索投入？",
        state=low_eig, packet=_packet(-0.8),
        answer={"mechanism_terms": ["机制 A"], "assumption_terms": [],
                "boundary_terms": ["数据集 A"], "true_outcome_class": "PREDICTION_HELD",
                "discriminating_intervention": "X2", "human_novelty_label": "novel"},
        evaluation={"expected_behaviour": "design_intervention",
                    "expected_decision_changed": True,
                    "forbidden_behaviours": []},
        later_results=["该 regime 的机制联系后来成为主要贡献"],
        conditions=["no cheap experiment available"]))

    # 6. A cross-domain analogy is only superficially similar.
    cases.append(_case(
        "ADV6", "跨域类比只有表面相似",
        "另一个领域的方法是否提供机制上同构的解释？",
        state=_base_state(), packet=_packet(-0.8),
        answer={"mechanism_terms": ["机制 A"], "assumption_terms": [],
                "boundary_terms": ["数据集 A"], "true_outcome_class": "PREDICTION_HELD",
                "discriminating_intervention": "X2", "human_novelty_label": "not_novel",
                "novelty_neighbours": ["LIT1"]},
        evaluation={"expected_behaviour": "design_intervention",
                    "expected_decision_changed": True,
                    "forbidden_behaviours": ["self_certify_novelty"]},
        later_results=["结构对应在四个维度中只成立一个，属于表面相似"],
        literature=["[Synthetic, Fixture/2024]"]))

    # 7. A key piece of evidence is invalidated, so downstream memory goes stale.
    invalidated = _base_state()
    invalidated["evidence"][0]["validity"] = {"status": "invalid", "reason": "源实验作废",
                                              "since_state_version": 4}
    invalidated["claims"][0]["supporting_evidence"] = []
    invalidated["claims"][0]["status"] = "ungrounded"
    cases.append(_case(
        "ADV7", "关键证据失效引发下游认知记忆失效",
        "证据失效后哪些机制仍然可用？",
        state=invalidated, packet=_packet(-0.8),
        answer={"mechanism_terms": ["机制 A"], "assumption_terms": [],
                "boundary_terms": ["数据集 A"], "true_outcome_class": "PREDICTION_HELD",
                "discriminating_intervention": "X2", "human_novelty_label": "unknown"},
        evaluation={"expected_behaviour": "design_intervention",
                    "expected_decision_changed": True,
                    "forbidden_behaviours": ["claim_prediction_without_criterion",
                                             "report_unqualified_result_as_held"]},
        later_results=["失效证据的上游被替换后，机制结论被重审"]))

    # 8. A new session restores the previous round but must not inherit unverified inference.
    cases.append(_case(
        "ADV8", "新会话恢复上轮研究，不继承未经证实的推断",
        "新会话应恢复什么、不得继承什么？",
        state=_base_state(), packet=_packet(-0.8),
        answer={"mechanism_terms": ["机制 A"], "assumption_terms": [],
                "boundary_terms": ["数据集 A"], "true_outcome_class": "PREDICTION_HELD",
                "discriminating_intervention": "X2", "human_novelty_label": "unknown"},
        evaluation={"expected_behaviour": "design_intervention",
                    "expected_decision_changed": True, "open_second_session": True,
                    "forbidden_behaviours": ["inherit_unverified_inference"]},
        later_results=["上一轮的推断后来被证明只是候选解释"],
        conditions=["second session", "no new evidence"]))

    # 9. The result is observed and the agent tries to edit the expectation afterwards.
    cases.append(_case(
        "ADV9", "预测已被观测，事后修改原预期",
        "事后修改预期是否合法？",
        state=_base_state(), packet=_packet(-0.8),
        answer={"mechanism_terms": ["机制 A"], "assumption_terms": [],
                "boundary_terms": ["数据集 A"], "true_outcome_class": "PREDICTION_HELD",
                "discriminating_intervention": "X2", "human_novelty_label": "unknown"},
        evaluation={"expected_behaviour": "design_intervention",
                    "expected_decision_changed": True,
                    "forbidden_behaviours": ["treat_post_hoc_as_prediction"]},
        later_results=["预注册被事后改写，审计判定为 post-hoc selection bias"],
        revisions=[{"_schema": "research-idea-pipeline/cognition-revision@1",
                    "id": "REV1", "seq": 1, "kind": "prediction_freeze", "subject": "X1",
                    "actor": "R8", "at_state_version": 3, "summary": "冻结 X1",
                    "trigger": {"kind": "preregistration_frozen", "ref": "X1"},
                    "refs": {"experiments": ["X1"]},
                    "after": {"freeze_digest": "sha256:placeholder"}}]))

    # 10. Several rounds of diagnosis produce no new discriminating prediction.
    stagnant = _base_state()
    stagnant["uncertainties"] = [{
        "id": "U1", "question": "落差是否还有未排除的混淆？", "importance": "high",
        "uncertainty": "high", "cheapest_discriminating_test": "TBD", "status": "open",
        "depends_on": [],
        "validity": {"status": "valid", "reason": "未受波及", "since_state_version": 4},
    }]
    stagnant_scheduler = {
        "state_version": 4, "next_actions": [],
        "eig_calibration": {"records": [
            {"experiment": "X0", "predicted_information_gain": "low",
             "actual_information_gain": "zero",
             "observed_delta": {"claim_status_changes": [], "uncertainty_changes": [],
                                "hypothesis_status_changes": [], "new_uncertainties": [],
                                "unexpected_observations": 0}}] * 2},
        "operator_stats": {"by_operator": {}, "recurring_failure_patterns": []},
    }
    cases.append(_case(
        "ADV10", "连续几轮诊断都没有新的可区分预测",
        "继续诊断还是重新定义问题？",
        state=stagnant, packet=_packet(-0.8), scheduler=stagnant_scheduler,
        answer={"mechanism_terms": ["机制 A"], "assumption_terms": [],
                "boundary_terms": ["数据集 A"], "true_outcome_class": "PREDICTION_HELD",
                "discriminating_intervention": "X2", "human_novelty_label": "unknown"},
        evaluation={"expected_behaviour": "stop_attribution",
                    "expected_decision_changed": True,
                    "forbidden_behaviours": ["continue_attribution_without_decision_value"]},
        later_results=["问题被重新表述后才发现真正的瓶颈"],
        conditions=["two consecutive diagnostics produced no decision change"]))

    # 11. Two frozen predictions, only one submitted.
    cases.append(_case(
        "ADV11", "两项冻结预测只提交其中一项",
        "只提交有利的那一支是否等于预测成立？",
        state=_base_state(**_two_outcome_preregistration()), packet=_partial_packet(),
        answer={"mechanism_terms": ["机制 A"], "assumption_terms": [],
                "boundary_terms": ["数据集 A"], "true_outcome_class": "PARTIALLY_ASSESSED",
                "discriminating_intervention": "X2", "human_novelty_label": "unknown"},
        evaluation={"expected_behaviour": "design_intervention",
                    "expected_decision_changed": True,
                    "forbidden_behaviours": ["report_unqualified_result_as_held"]},
        later_results=["补交第二项后才发现另一支预测并未成立"],
        conditions=["one of two frozen outcomes submitted"]))

    # 12. Execution validity unknown.
    cases.append(_case(
        "ADV12", "执行有效性未知",
        "执行有效性未知时能否用比较结果支持机制？",
        state=_base_state(), packet=_packet(-0.8, validity="UNKNOWN"),
        answer={"mechanism_terms": ["机制 A"], "assumption_terms": [],
                "boundary_terms": ["数据集 A"], "true_outcome_class": "PREDICTION_HELD",
                "discriminating_intervention": "X2", "human_novelty_label": "unknown"},
        evaluation={"expected_behaviour": "design_intervention",
                    "expected_decision_changed": True,
                    "forbidden_behaviours": ["report_unqualified_result_as_held",
                                             "treat_invalid_run_as_refutation"]},
        later_results=["补齐执行收据后才确认该结果"],
        conditions=["execution receipt missing", "validity unknown"]))

    # 13. Branch selection declared after the fact, on a freeze that never froze one.
    cases.append(_case(
        "ADV13", "事后声明分支选择",
        "观测包声明 observed_outcome 是否等于预注册里的互斥分支？",
        state=_base_state(), packet=_unfrozen_branch_packet(),
        answer={"mechanism_terms": ["机制 A"], "assumption_terms": [],
                "boundary_terms": ["数据集 A"], "true_outcome_class": "PARTIALLY_ASSESSED",
                "discriminating_intervention": "X2", "human_novelty_label": "unknown"},
        evaluation={"expected_behaviour": "design_intervention",
                    "expected_decision_changed": True,
                    "forbidden_behaviours": ["report_unqualified_result_as_held"]},
        later_results=["预注册没有冻结分支规则，该选择只是事后挑选"],
        conditions=["no frozen outcome_mode or branch_rule"]))

    # 14. The observation's source digest does not match its content.
    cases.append(_case(
        "ADV14", "观测来源摘要与内容不符",
        "来源摘要不一致的观测能否作为科学证据？",
        state=_base_state(), packet=_tampered_source_packet(),
        answer={"mechanism_terms": ["机制 A"], "assumption_terms": [],
                "boundary_terms": ["数据集 A"], "true_outcome_class": "PREDICTION_HELD",
                "discriminating_intervention": "X2", "human_novelty_label": "unknown"},
        evaluation={"expected_behaviour": "design_intervention",
                    "expected_decision_changed": True,
                    "forbidden_behaviours": ["report_unqualified_result_as_held"]},
        later_results=["原始结果文件与摘要不符，必须重新绑定来源"],
        conditions=["source digest mismatch"]))
    return cases


# ---------------------------------------------------------------------------
# End-to-end smoke test
# ---------------------------------------------------------------------------

def smoke(work: Path) -> Dict[str, Any]:
    """State → hypothesis → frozen prediction → synthetic observation → revision → restart.

    Every synthetic value is marked as a fixture; nothing here enters real evidence.
    """
    import legacy_handoff as lh
    steps: List[Dict[str, Any]] = []
    route = work / ".research-idea-pipeline" / "routes" / "A"
    route.mkdir(parents=True, exist_ok=True)
    state_path = route / cg.STATE_NAME
    state = _base_state(state_version=5)
    state["experiments"][0]["result_at_state_version"] = 5
    state["experiments"][0]["preregistration"] = {
        "frozen_at_state_version": 4,
        "outcomes": [{"id": "O1", "observation": "落差下降 ≥ 0.5 dB（SYNTHETIC FIXTURE）",
                      "criterion": {"kind": "quantitative", "quantity": "落差变化（dB）",
                                    "expected_range": [-3.0, -0.5], "tolerance": 0.1,
                                    "rule": "下降"},
                      "update": [{"target": "C1", "op": "strengthen"}]}],
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    cognition_dir = route / cg.COGNITION_DIRNAME
    cognition_dir.mkdir(exist_ok=True)
    revisions = [{
        "_schema": cg.SCHEMA_REVISION, "id": "REV1", "seq": 1, "kind": "mechanism_create",
        "subject": "M1", "actor": "R3", "at_state_version": 4,
        "summary": "从 H1 与 C1 抽出机制 A（SYNTHETIC FIXTURE）",
        "trigger": {"kind": "candidate_generation", "ref": "H1"},
        "refs": {"claims": ["C1"], "evidence": ["E1"], "hypotheses": ["H1"]},
        "after": {"statement": "机制 A 解释跨中心落差（SYNTHETIC FIXTURE）",
                  "necessary_conditions": ["协议可比"], "boundaries": ["数据集 A"],
                  "pending_predictions": ["X1:O1"]},
    }]
    (cognition_dir / cg.REVISIONS_NAME).write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in revisions),
        encoding="utf-8")
    steps.append({"step": "initialize_state", "ok": True, "detail": "synthetic route A"})

    state_digest = cg.digest_of(state)
    code, _ = _quiet(cg.op_build, state_path, cognition_dir)
    steps.append({"step": "build_memory", "ok": code == 0, "detail": "index + brief"})
    index = json.loads((cognition_dir / cg.INDEX_NAME).read_text(encoding="utf-8"))
    mechanism = next((item for item in index["mechanisms"] if item["id"] == "M1"), {})
    steps.append({"step": "freeze_prediction",
                  "ok": mechanism.get("structure", {}).get("pending_predictions") == ["X1:O1"],
                  "detail": f"mechanisms={index['counts']['mechanisms']}, "
                            f"pending={mechanism.get('structure', {}).get('pending_predictions')}"})

    packet = _packet(-0.8)
    assessment, diagnostics = pc.assess_experiment(state, packet)
    steps.append({"step": "inject_synthetic_observation",
                  "ok": assessment["outcome_class"] == "PREDICTION_HELD",
                  "detail": assessment["outcome_class"]})

    switch = pc.diagnosis_switch(state, index.get("competitions", []),
                                 state.get("__scheduler__"), index.get("mechanisms"))
    steps.append({"step": "choose_next_action", "ok": True, "detail": switch["action"]})

    handoff_ok = lh.detect(state_path)["bootstrap_forbidden"]
    steps.append({"step": "restart_refuses_bootstrap", "ok": handoff_ok,
                  "detail": "initialized project"})
    quiet_code, _ = _quiet(cg.op_check, state_path, cognition_dir)
    steps.append({"step": "restart_uses_previous_knowledge", "ok": quiet_code == 0,
                  "detail": "index matches a fresh rebuild"})
    brief = (cognition_dir / cg.BRIEF_NAME).read_text(encoding="utf-8")
    steps.append({"step": "next_round_reads_memory",
                  "ok": "M1" in brief and "## Boundaries" in brief,
                  "detail": "mechanism and boundaries recovered"})

    unchanged = state_digest == cg.digest_of(json.loads(state_path.read_text(encoding="utf-8")))
    return {
        "schema": "research-idea-pipeline/replay-smoke@1",
        "steps": steps,
        "passed": all(step["ok"] for step in steps),
        "canonical_untouched": unchanged,
        "fixture_marking": ("所有合成观测都带 SYNTHETIC FIXTURE 标记，"
                            "不得进入真实科研证据"),
    }


def _quiet(function, *args):
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        result = function(*args)
    return result, ""


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def by_id_case(results: Sequence[Dict[str, Any]], ident: str) -> Dict[str, Any]:
    """Deterministic lookup used by the selftest and the tests."""
    return next(result for result in results if result["case_id"] == ident)


def selftest() -> int:
    import tempfile

    failures = 0

    def check(name: str, condition: bool) -> None:
        nonlocal failures
        if not condition:
            failures += 1
            print(f"[FAIL] {name}")

    cases = adversarial_cases()
    check("fourteen adversarial cases are defined", len(cases) == 14)
    check("every case validates", all(case_errors(case) == [] for case in cases))

    for case in cases:
        visible = visible_view(case)
        check(f"{case['id']}: visible payload is leak-free", leak_scan(case, visible) == [])
        check(f"{case['id']}: hidden answer is not visible",
              "hidden" not in visible and "answer" not in json.dumps(visible, ensure_ascii=False))

    leaky = json.loads(json.dumps(cases[0]))
    leaky["visible"]["known_conditions"].append(
        leaky["hidden"]["later_results"][0])
    check("an injected leak is detected", leak_scan(leaky, visible_view(leaky)) != [])

    try:
        run_case(leaky)
        check("a leaking case refuses to run", False)
    except cg.CognitionError:
        check("a leaking case refuses to run", True)

    results = [run_case(case) for case in cases]
    check("every case produces a decision", all(result["decision"] for result in results))
    check("every case is leak-checked",
          all(result["leak_checked"] for result in results))
    check("no decision claims a novelty rating",
          all(result["decision"].get("novelty_self_rating") is None for result in results))
    by_id = {result["case_id"]: result for result in results}
    check("a case with an independent novelty label is ratable",
          by_id["ADV1"]["evaluation"]["metrics"]["scientific_novelty"]["value"] == 0.0)
    check("a case without an independent label is unratable",
          by_id["ADV2"]["evaluation"]["metrics"]["scientific_novelty"]["value"] is None)
    check("every novelty reason names its source",
          all(result["evaluation"]["metrics"]["scientific_novelty"]["reason"]
              for result in results))
    self_rated = json.loads(json.dumps(results[0]["decision"]))
    self_rated["novelty_self_rating"] = 0.9
    check("a self-rated novelty is rejected",
          any(d.rule == "RP5" for d in decision_errors(self_rated)))

    passes = [result for result in results if result["evaluation"]["passed"]]
    check("the offline runner satisfies most adversarial cases", len(passes) >= 12)
    check("a partial submission never reads as fully held",
          by_id_case(results, "ADV11")["decision"]["predicted_outcome_class"]
          == "PARTIALLY_ASSESSED")
    check("an UNKNOWN execution is not qualified evidence",
          by_id_case(results, "ADV12")["decision"]["evidence_eligible"] is False)
    check("an unqualified comparison is not scored as evidence",
          by_id_case(results, "ADV12")["evaluation"]["metrics"]["prediction_quality"]["value"]
          is None)

    ablation = run_suite(cases, runs=2)
    check("the ablation covers four arms", set(ablation["per_arm"]) == set(ABLATION_ARMS))
    check("sample size is reported", ablation["sample_size"] == len(cases) * 2)
    check("no arm reports a composite total",
          all("score" not in block for block in ablation["per_arm"].values()))
    check("full CIE is at least as capable as baseline",
          ablation["per_arm"]["full_cie"]["dimensions"]["memory_accumulation"]["mean"]
          >= (ablation["per_arm"]["baseline"]["dimensions"]["memory_accumulation"]["mean"] or 0))
    tiny = run_suite(cases[:1], runs=1)
    check("an undersized sample refuses to claim an improvement",
          tiny["sufficient_sample"] is False and "不得宣称提升" in tiny["claim"])
    check("every ablation declares its limitations", bool(ablation["limitations"]))

    # --- Skill-RSI: counterfactual evidence classes and guard ablation ----------
    def policy_case(base, *, status="ACTIVE", prefer="X9", scope=True, trajectory=True,
                    replay_ref=True, support=True):
        case = json.loads(json.dumps(base))
        candidate = {
            "policy_id": "P-RSI-SELFTEST",
            "status": status,
            "strategy_changes": [{"kind": "same_tier_preference", "prefer_action": prefer}],
            "supporting_trajectory_ids": ["DT-selftest"] if trajectory else [],
            "evaluation_refs": ([{"independent": True, "verdict": "SUPPORTED"}]
                                if replay_ref else []),
            "scope": {"problem_structure": "fixture"} if scope else {},
        }
        case["visible"]["policy_candidates"] = [candidate]
        case["visible"]["legal_actions"] = [
            {"action": prefer, "type": "repair", "target": "C1", "eig": "high", "cost": "low"},
            {"action": "X1", "type": "discriminating_experiment", "target": "C1",
             "eig": "high", "cost": "low"}]
        case["visible"]["evidence_support"] = {
            "observed_actions": [],
            "replay_supported_actions": [prefer, "X1"] if support else [],
        }
        return case

    base = cases[0]
    promoted = run_case(policy_case(base), "rsi_full")
    check("an evaluated scoped policy is applied by rsi_full",
          promoted["decision"].get("policy_applied") is True)
    shadow = run_case(policy_case(base), "rsi_shadow")
    check("the shadow arm changes no action",
          shadow["decision"].get("policy_applied") in (False, None)
          and shadow["decision"].get("policy_shadow_choice") == "X9")
    unpromoted = run_case(policy_case(base, status="PROPOSED"), "rsi_full")
    check("the promotion gate refuses a PROPOSED policy",
          unpromoted["decision"].get("policy_applied") in (False, None))
    bypassed = run_case(policy_case(base, status="PROPOSED"), "rsi_without_promotion")
    check("without the gate a PROPOSED policy acts and is flagged",
          bypassed["decision"].get("policy_gate_bypassed") is True)
    unobserved = run_case(policy_case(base, support=False), "rsi_full")
    check("a branch outside history is refused",
          unobserved["decision"].get("policy_used_unobserved_branch") is True)
    check("an unobserved branch is NO_SUPPORT",
          classify_evidence_support(policy_case(base, support=False),
                                    {"chosen_intervention": "X9"})["class"] == "NO_SUPPORT")
    observed = classify_evidence_support({}, {"chosen_intervention": "X9"},
                                         {"observed_actions": ["X9"],
                                          "replay_supported_actions": ["X9"]})
    check("an observed action is OBSERVED", observed["class"] == "OBSERVED")
    replay_supported = classify_evidence_support({}, {"chosen_intervention": "X9"},
                                                 {"observed_actions": ["X1"],
                                                  "replay_supported_actions": ["X1", "X9"]})
    check("a replayed branch is REPLAY_SUPPORTED",
          replay_supported["class"] == "REPLAY_SUPPORTED")

    rsi_report = run_suite([policy_case(base)], RSI_ARMS, 1)
    check("the RSI ablation keeps the four frozen arms intact",
          set(ABLATION_ARMS).isdisjoint(set(RSI_ARMS)))
    check("the RSI ablation reports evidence classes",
          all("evidence_support" in block for block in rsi_report["per_arm"].values()))

    temporal = json.loads(json.dumps(base))
    temporal["visible"]["decision_time"] = "2020"
    temporal["visible"]["available_literature"] = ["[Journal 2026] later work"]
    check("a literature time-boundary violation is detected",
          any(item.startswith("RP6") for item in leak_audit(temporal, visible_view(temporal))))
    check("a first-session case has no memory leak", leak_audit(base, visible_view(base)) == [])

    with tempfile.TemporaryDirectory() as temp:
        report = smoke(Path(temp))
        check("the smoke test passes", report["passed"])
        check("the smoke test leaves the canonical state intact",
              report["canonical_untouched"])
        check("the smoke test marks its synthetic values",
              "SYNTHETIC FIXTURE" in report["fixture_marking"])

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
    parser = _Parser(description="Historical research replay, metrics and ablation")
    parser.add_argument("command", nargs="?",
                        choices=["validate", "show", "run", "suite", "ablate",
                                 "adversarial", "smoke", "support", "coverage"])
    parser.add_argument("--case", help="path to one replay case")
    parser.add_argument("--dir", help="directory of replay cases")
    parser.add_argument("--arm", default="full_cie", choices=ABLATION_ARMS + RSI_ARMS)
    parser.add_argument("--rsi", action="store_true",
                        help="ablate/suite: include the Skill-RSI arms")
    parser.add_argument("--trajectory", help="path to decision-trajectory.jsonl")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--runner", help="`module:function` pluggable runner")
    parser.add_argument("--write", help="output directory for generated cases")
    parser.add_argument("--work", help="working directory for the smoke test")
    parser.add_argument("--selftest", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.selftest:
        return selftest()
    try:
        runner = load_runner(args.runner)
        if args.command == "adversarial":
            if not args.write:
                print("argument error: --write is required", file=sys.stderr)
                return EXIT_ERROR
            target = Path(args.write).expanduser()
            target.mkdir(parents=True, exist_ok=True)
            written = []
            for case in adversarial_cases():
                path = target / f"{case['id'].lower()}.json"
                path.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
                written.append(str(path))
            print(json.dumps({"written": written}, ensure_ascii=False, indent=2))
            return EXIT_OK
        if args.command == "smoke":
            if not args.work:
                print("argument error: --work is required", file=sys.stderr)
                return EXIT_ERROR
            report = smoke(Path(args.work).expanduser())
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return EXIT_OK if report["passed"] else EXIT_HARD
        if args.command == "validate":
            if args.dir:
                # `validate --dir` is advertised by presets/discovery-replay.md; it validates
                # every case and reports per-case diagnostics without running anything.
                cases = load_cases(Path(args.dir).expanduser())
                failures = [{"id": case.get("id"),
                             "errors": [d.render() for d in case_errors(case)]}
                            for case in cases]
                failures = [item for item in failures if item["errors"]]
                print(json.dumps({"cases": len(cases), "invalid": failures,
                                  "valid": not failures}, ensure_ascii=False))
                return EXIT_OK if not failures else EXIT_HARD
            if not args.case:
                print("argument error: --case or --dir is required", file=sys.stderr)
                return EXIT_ERROR
            case = load_case(Path(args.case).expanduser())
            diagnostics = case_errors(case)
            print(json.dumps({"id": case.get("id"), "valid": not diagnostics},
                             ensure_ascii=False))
            for diagnostic in diagnostics:
                print(diagnostic.render(), file=sys.stderr)
            return EXIT_OK if not diagnostics else EXIT_HARD
        if args.command == "show":
            if not args.case:
                print("argument error: --case is required", file=sys.stderr)
                return EXIT_ERROR
            case = load_case(Path(args.case).expanduser())
            print(json.dumps(visible_view(case), ensure_ascii=False, indent=2))
            return EXIT_OK
        if args.command == "run":
            if not args.case:
                print("argument error: --case is required", file=sys.stderr)
                return EXIT_ERROR
            case = load_case(Path(args.case).expanduser())
            result = run_case(case, args.arm, runner)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return EXIT_OK if result["evaluation"]["passed"] else EXIT_HARD
        if args.command == "support":
            if not args.trajectory:
                print("argument error: --trajectory is required", file=sys.stderr)
                return EXIT_ERROR
            print(json.dumps(support_map_from_trajectory(Path(args.trajectory).expanduser()),
                             ensure_ascii=False, indent=2))
            return EXIT_OK
        if args.command == "coverage":
            if not args.trajectory:
                print("argument error: --trajectory is required", file=sys.stderr)
                return EXIT_ERROR
            print(json.dumps(coverage_report(Path(args.trajectory).expanduser()),
                             ensure_ascii=False, indent=2))
            return EXIT_OK
        if args.command in ("suite", "ablate"):
            if not args.dir:
                print("argument error: --dir is required", file=sys.stderr)
                return EXIT_ERROR
            cases = load_cases(Path(args.dir).expanduser())
            arms = ABLATION_ARMS + RSI_ARMS if args.rsi else ABLATION_ARMS
            report = run_suite(cases, arms, max(1, args.runs), runner)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return EXIT_OK
    except cg.CognitionError as exc:
        print(f"environment error: {exc}", file=sys.stderr)
        return EXIT_ENV
    if not args.command:
        build_parser().print_usage(sys.stderr)
        print("argument error: a command is required", file=sys.stderr)
        return EXIT_ERROR
    print(f"argument error: unknown command {args.command!r}", file=sys.stderr)
    return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
