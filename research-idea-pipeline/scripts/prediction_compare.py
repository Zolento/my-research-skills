#!/usr/bin/env python3
"""prediction_compare.py — prediction, anomaly, mechanism competition, insight cards.

What this module fixes
----------------------
Phase 1 made mechanisms, anomalies and competitions recoverable. Phase 2 makes them
**checkable**:

* a prediction is frozen with a machine-decidable `criterion`, and a later silent rewrite
  of that criterion is detected (`PC4`);
* a frozen prediction is compared to an observation, and the comparison returns a class
  instead of a story: `PREDICTION_HELD`, `PREDICTION_DEVIATED`, `WITHIN_TOLERANCE`,
  `EXPLORATORY_ANOMALY`, `INVALID_EXECUTION`, `UNTESTABLE`;
* two mechanisms are distinguishable only if their frozen predictions differ and a real
  experiment can separate them (`PC6`);
* repeated uninformative diagnosis produces a behaviour switch rather than another
  explanation;
* an insight card may not certify its own novelty or evidence support (`PC7`).

**No parallel prediction schema.** The criterion lives inside the existing
`experiments[].preregistration.outcomes[]` slot, frozen by the existing V21 rule. Legacy
states without a criterion stay readable: they compare as `UNTESTABLE` and receive no
retrospective verdict.

Rule namespace `PC1`—`PC9`; `S`/`V` and `CM` keep their own identities.

Usage
-----
    python3 prediction_compare.py freeze   --state S --experiment X1
    python3 prediction_compare.py compare  --state S --packet observation.json
    python3 prediction_compare.py compete  --state S --competition CP1 [--cognition DIR]
    python3 prediction_compare.py switch   --state S [--scheduler S.json] [--cognition DIR]
    python3 prediction_compare.py insight  --state S --card card.json
    python3 prediction_compare.py --selftest

Exit codes: 0 pass, 1 argument error, 3 hard violation, 4 environment not satisfied.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cognition as cg
import execution_gate as eg

Diagnostic = cg.Diagnostic

SCHEMA_OBSERVATION = "research-idea-pipeline/prediction-observation@1"
SCHEMA_ASSESSMENT = "research-idea-pipeline/prediction-assessment@1"
SCHEMA_INSIGHT = "research-idea-pipeline/insight-card@1"

EXIT_OK = cg.EXIT_OK
EXIT_ERROR = cg.EXIT_ERROR
EXIT_HARD = cg.EXIT_HARD
EXIT_ENV = cg.EXIT_ENV

INSIGHT_CARDS_NAME = "insight-cards.jsonl"

# ---------------------------------------------------------------------------
# Frozen vocabularies
# ---------------------------------------------------------------------------

CRITERION_KINDS: Tuple[str, ...] = ("quantitative", "directional", "discrete")
DIRECTIONS: Tuple[str, ...] = ("increase", "decrease", "no_change")

#: Comparison outcomes. `EXPLORATORY_ANOMALY` is the only legal class for an observation
#: that was never a prediction; it may never be reported as a success or a failure.
#:
#: `PARTIALLY_ASSESSED` is the class for "some frozen predictions were decided and some
#: were not". It exists because the alternative — deciding on the submitted subset and
#: reporting `PREDICTION_HELD` — makes selective submission a way to manufacture support.
OUTCOME_CLASSES: Tuple[str, ...] = (
    "PREDICTION_HELD",
    "PREDICTION_DEVIATED",
    "WITHIN_TOLERANCE",
    "PARTIALLY_ASSESSED",
    "EXPLORATORY_ANOMALY",
    "INVALID_EXECUTION",
    "UNTESTABLE",
)

#: What the comparison result may be used for. A diagnostic comparison is legitimate and
#: useful; treating it as qualified scientific evidence is not. This is the boundary that
#: `UNKNOWN` execution validity used to cross silently.
EVIDENCE_CLASSES: Tuple[str, ...] = (
    "QUALIFIED_EVIDENCE",
    "DIAGNOSTIC_ONLY",
    "INSUFFICIENT_PROVENANCE",
)

#: Outcome classes that assert something about the world (support, refutation, or the
#: absence of contradiction). They may only occupy `outcome_class` on qualified evidence.
#: `PARTIALLY_ASSESSED` and `UNTESTABLE` describe the *adjudication*, not the world, so
#: they stay in the scientific slot even when the evidence is not qualified: "we could not
#: finish evaluating" is itself the correct scientific conclusion.
WORLD_CLAIMING_CLASSES: Tuple[str, ...] = (
    "PREDICTION_HELD", "PREDICTION_DEVIATED", "WITHIN_TOLERANCE",
)

#: `scientific_status` states what a consumer may do with an assessment, in one word.
SCIENTIFIC_STATUSES: Tuple[str, ...] = (
    "MAY_INFORM_TRANSITION",
    "DIAGNOSTIC_ONLY",
    "NO_INFERENCE",
)

#: Mechanism distinguishability. Four semantics, because "the digests differ" is not a
#: scientific claim:
#:
#: * `DISTINGUISHABLE` — comparable observable, conflicting predictions, a pre-declared
#:   discrimination rule, and enough resolution to apply it.
#: * `CONDITIONALLY_DISTINGUISHABLE` — the predictions do conflict, but the decision rule
#:   is not declared yet; declaring it is the missing step.
#: * `NOT_DISTINGUISHABLE` — on the declared design the two mechanisms cannot be separated.
#: * `INSUFFICIENT_INFORMATION` — the comparison is not even defined (different
#:   observables, no ownership, unusable intervention).
COMPETITION_VERDICTS: Tuple[str, ...] = (
    "DISTINGUISHABLE",
    "CONDITIONALLY_DISTINGUISHABLE",
    "NOT_DISTINGUISHABLE",
    "INSUFFICIENT_INFORMATION",
)

#: Machine-readable cause attached to every verdict. A verdict without a reason cannot
#: tell the researcher what single step would change it.
COMPETITION_REASONS: Tuple[str, ...] = (
    "insufficient_mechanisms",
    "no_prediction_gap",
    "insufficient_predictions",
    "no_ownership",
    "no_intervention",
    "intervention_not_actionable",
    "predictions_on_other_experiments",
    "different_observables",
    "different_measurement",
    "mixed_criterion_kinds",
    "identical_criteria",
    "overlapping_intervals",
    "non_conflicting_predictions",
    "within_uncertainty",
    "below_declared_min_separation",
    "no_discrimination_rule",
    "discrimination_rule_satisfied",
    "labels_mutually_exclusive",
    "invalid_criterion",
)

#: Reasons that a *design* step can resolve: a minimal intervention separates the pair.
DESIGN_FIXABLE_REASONS: Tuple[str, ...] = (
    "insufficient_mechanisms",
    "no_prediction_gap",
    "insufficient_predictions",
    "no_ownership",
    "no_intervention",
    "intervention_not_actionable",
    "predictions_on_other_experiments",
    "no_discrimination_rule",
)

#: Reasons that no additional run of the same design can resolve.
STRUCTURAL_REASONS: Tuple[str, ...] = (
    "different_observables",
    "different_measurement",
    "identical_criteria",
    "overlapping_intervals",
    "within_uncertainty",
    "below_declared_min_separation",
    "non_conflicting_predictions",
    "mixed_criterion_kinds",
    "invalid_criterion",
)

#: Behaviour-switch recommendations. These are **not** new R10/R14 enums; they map onto
#: existing dispositions and the existing STOP_DIAGNOSIS / T8 routing.
SWITCH_ACTIONS: Tuple[str, ...] = (
    "CONTINUE_ATTRIBUTION",
    "FIND_DISCRIMINATING_INTERVENTION",
    "REDESIGN_QUESTION",
    "RECORD_BOUNDARY_AND_STOP",
    "EXPLORE_METHOD_UNDER_UNCERTAINTY",
)

INSIGHT_CLASSES: Tuple[str, ...] = (
    "explanatory_hypothesis",
    "predictive_insight_candidate",
    "evidence_supported_insight",
)

DECISION_IMPACTS: Tuple[str, ...] = (
    "method_decision_differs", "same_method_decision", "unknown",
)

#: Consecutive uninformative diagnostics that trigger a behaviour switch. The AALG policy
#: already caps *equivalent* diagnostic attempts; this counter is about information, not
#: equivalence, so it is defined here rather than reusing the ledger counter.
DEFAULT_ZERO_STREAK = 2


# ---------------------------------------------------------------------------
# Prediction references and criteria
# ---------------------------------------------------------------------------

def parse_ref(ref: Any) -> Optional[Tuple[str, str]]:
    """`"X2:O1"` → `("X2", "O1")`. Anything else is not a prediction reference."""
    if not isinstance(ref, str) or ref.count(":") != 1:
        return None
    experiment, outcome = (part.strip() for part in ref.split(":"))
    if not experiment or not outcome:
        return None
    return experiment, outcome


def criterion_errors(criterion: Any, path: str) -> List[Diagnostic]:
    """Shape-check one frozen criterion. Absent criterion is legal but not decidable."""
    if not isinstance(criterion, dict):
        return [Diagnostic("PC1", path, "criterion 必须是对象")]
    failures: List[Diagnostic] = []
    kind = criterion.get("kind")
    if kind not in CRITERION_KINDS:
        return [Diagnostic("PC1", path, f"kind 必须是 {list(CRITERION_KINDS)} 之一，实际 {kind!r}")]
    if not isinstance(criterion.get("quantity"), str) or not criterion["quantity"].strip():
        failures.append(Diagnostic("PC1", path, "缺少非空 quantity（被测量的量，含单位口径）"))
    if kind == "quantitative":
        expected = criterion.get("expected_range")
        if (not isinstance(expected, list) or len(expected) != 2
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                           for v in expected)
                or expected[0] > expected[1]):
            failures.append(Diagnostic(
                "PC1", path, "quantitative 判据需要 expected_range = [下界, 上界]，且下界 ≤ 上界"))
        if not _is_non_negative_number(criterion.get("tolerance")):
            failures.append(Diagnostic("PC1", path, "quantitative 判据需要 tolerance ≥ 0"))
    elif kind == "directional":
        if criterion.get("direction") not in DIRECTIONS:
            failures.append(Diagnostic(
                "PC1", path, f"directional 判据需要 direction ∈ {list(DIRECTIONS)}"))
        if not _is_non_negative_number(criterion.get("tolerance")):
            failures.append(Diagnostic("PC1", path, "directional 判据需要 tolerance ≥ 0"))
    elif kind == "discrete":
        held = criterion.get("held_labels")
        failed = criterion.get("failed_labels")
        if not _non_empty_string_list(held):
            failures.append(Diagnostic("PC1", path, "discrete 判据需要非空 held_labels"))
        if not _non_empty_string_list(failed):
            failures.append(Diagnostic("PC1", path, "discrete 判据需要非空 failed_labels"))
        if _non_empty_string_list(held) and _non_empty_string_list(failed):
            overlap = sorted(set(held) & set(failed))
            if overlap:
                failures.append(Diagnostic(
                    "PC1", path, f"held_labels 与 failed_labels 不得重叠：{overlap}"))
    if "rule" in criterion and not isinstance(criterion["rule"], str):
        failures.append(Diagnostic("PC1", path, "rule 是给人读的说明，必须是字符串"))
    failures.extend(_statistical_criterion_errors(criterion, path))
    return failures


def _statistical_criterion_errors(criterion: Dict[str, Any], path: str) -> List[Diagnostic]:
    """Optional statistical declarations. They size the discrimination analysis only.

    `tolerance` decides "held" and is frozen into the comparison; `noise` / `sample_size`
    decide whether two mechanisms can be *separated* at all, which is a property of the
    design rather than of the observation.
    """
    failures: List[Diagnostic] = []
    if "noise" in criterion and not _is_non_negative_number(criterion["noise"]):
        failures.append(Diagnostic("PC1", path, "noise 必须是 ≥ 0 的数值（单位同 quantity）"))
    if "min_effect" in criterion and not _is_non_negative_number(criterion["min_effect"]):
        failures.append(Diagnostic("PC1", path, "min_effect 必须是 ≥ 0 的数值"))
    if "sample_size" in criterion:
        size = criterion["sample_size"]
        if not isinstance(size, int) or isinstance(size, bool) or size < 1:
            failures.append(Diagnostic("PC1", path, "sample_size 必须是 ≥ 1 的整数"))
    if "measurement" in criterion:
        measurement = criterion["measurement"]
        if not isinstance(measurement, str) or not measurement.strip():
            failures.append(Diagnostic(
                "PC1", path, "measurement 是测量口径说明（采集/聚合方式），必须是非空字符串"))
    return failures


def discrimination_rule_errors(rule: Any, path: str) -> List[Diagnostic]:
    """Shape-check a pre-declared discrimination rule.

    The rule answers "what outcome counts as separation, decided *before* the run". Without
    it a disjoint interval pair is only conditionally decisive, because nothing fixes the
    threshold at which one mechanism is declared the winner.
    """
    if rule is None:
        return []
    if not isinstance(rule, dict):
        return [Diagnostic("PC1", path, "discrimination_rule 必须是对象")]
    failures: List[Diagnostic] = []
    statistic = rule.get("statistic")
    if not isinstance(statistic, str) or not statistic.strip():
        failures.append(Diagnostic(
            "PC1", path, "discrimination_rule 需要非空 statistic（例如 difference_of_means）"))
    if not _is_non_negative_number(rule.get("min_separation")):
        failures.append(Diagnostic(
            "PC1", path, "discrimination_rule 需要 min_separation ≥ 0（该设计能分辨的最小间隔）"))
    if "alpha" in rule:
        alpha = rule["alpha"]
        if not isinstance(alpha, (int, float)) or isinstance(alpha, bool) or not 0 < alpha < 1:
            failures.append(Diagnostic("PC1", path, "alpha 必须在 (0, 1) 内"))
    if "requires" in rule and not isinstance(rule["requires"], str):
        failures.append(Diagnostic("PC1", path, "requires 是给人读的前置说明，必须是字符串"))
    return failures


def _is_non_negative_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def _non_empty_string_list(value: Any) -> bool:
    return (isinstance(value, list) and bool(value)
            and all(isinstance(item, str) and item.strip() for item in value))


def criterion_signature(criterion: Dict[str, Any]) -> str:
    """A comparable identity for 'what this prediction would count as held'.

    Two mechanisms whose predictions share a signature cannot be separated by the
    experiment that produced them, however differently the two are worded. The signature
    deliberately excludes `rule`, `measurement`, `noise` and `sample_size`: the first is
    prose, and the others size the *design*, not the prediction. They are compared
    separately by the comparability analysis.
    """
    kind = criterion.get("kind")
    payload: Dict[str, Any] = {"kind": kind, "quantity": criterion.get("quantity")}
    if kind == "quantitative":
        payload["expected_range"] = list(criterion.get("expected_range") or [])
        payload["tolerance"] = criterion.get("tolerance")
    elif kind == "directional":
        payload["direction"] = criterion.get("direction")
        payload["tolerance"] = criterion.get("tolerance")
    elif kind == "discrete":
        payload["held_labels"] = sorted(criterion.get("held_labels") or [])
        payload["failed_labels"] = sorted(criterion.get("failed_labels") or [])
    return cg.digest_of(payload)


# ---------------------------------------------------------------------------
# Comparability and separation arithmetic
#
# These are the operational definitions the competition verdict rests on. Everything is
# computed from frozen fields; no text similarity and no self-rating enters anywhere.
# ---------------------------------------------------------------------------

def normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).casefold()


def observable_of(criterion: Dict[str, Any]) -> str:
    """The observed variable *and* its unit, taken from `quantity`."""
    return normalize_text(criterion.get("quantity"))


def measurement_of(criterion: Dict[str, Any]) -> str:
    """Optional measurement basis (acquisition / aggregation). Empty means undeclared."""
    return normalize_text(criterion.get("measurement"))


def decision_margin(criterion: Dict[str, Any]) -> float:
    """Half-width added to a declared range before comparing two mechanisms.

    `margin = tolerance + noise / sqrt(sample_size)`.

    Rationale: `tolerance` is the frozen decision tolerance for a single result, and
    `noise / sqrt(n)` is the standard error of a mean over `n` planned measurements. Their
    sum is the range within which two declared predictions cannot be told apart by the
    planned design. Undeclared `noise` or `sample_size` contributes 0, which is the
    conservative direction for *declaring* a distinction: the analyst must state the design
    uncertainty for it to widen the band.
    """
    margin = float(criterion.get("tolerance") or 0.0)
    noise = criterion.get("noise")
    size = criterion.get("sample_size")
    if _is_non_negative_number(noise) and isinstance(size, int) and not isinstance(size, bool) \
            and size >= 1 and noise > 0:
        margin += float(noise) / (size ** 0.5)
    return margin


def declared_range(criterion: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    if criterion.get("kind") != "quantitative":
        return None
    expected = criterion.get("expected_range")
    if not isinstance(expected, list) or len(expected) != 2:
        return None
    return (float(expected[0]), float(expected[1]))


def effective_range(criterion: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """The declared range widened by the decision margin."""
    raw = declared_range(criterion)
    if raw is None:
        return None
    margin = decision_margin(criterion)
    return (raw[0] - margin, raw[1] + margin)


def intervals_intersect(left: Tuple[float, float], right: Tuple[float, float]) -> bool:
    return not (left[1] < right[0] or right[1] < left[0])


def interval_gap(left: Tuple[float, float], right: Tuple[float, float]) -> float:
    """Distance between two disjoint intervals; 0 when they intersect."""
    if intervals_intersect(left, right):
        return 0.0
    return round(right[0] - left[1], 12) if left[1] < right[0] else round(left[0] - right[1], 12)


def directional_conflict(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    """Two directional predictions conflict only when their directions are disjoint."""
    return left.get("direction") != right.get("direction")


def discrete_conflict(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    """Two label predictions conflict when no observation can satisfy both."""
    left_held = set(left.get("held_labels") or [])
    right_held = set(right.get("held_labels") or [])
    return bool(left_held) and bool(right_held) and not (left_held & right_held)


def pair_discrimination(
    first: Dict[str, Any],
    second: Dict[str, Any],
    rule: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, Dict[str, Any]]:
    """Decide whether one pair of frozen predictions can separate two mechanisms.

    Returns `(verdict, reason, detail)`. The order of checks is deliberate: comparability
    first (is a comparison even defined?), then conflict (can both be satisfied at once?),
    then resolution (can the design tell them apart?), then the declared rule (is the
    winner fixed in advance?).
    """
    detail: Dict[str, Any] = {"first_signature": criterion_signature(first),
                              "second_signature": criterion_signature(second),
                              "observable": observable_of(first)}
    if observable_of(first) != observable_of(second):
        return "INSUFFICIENT_INFORMATION", "different_observables", {
            **detail, "first_quantity": first.get("quantity"),
            "second_quantity": second.get("quantity"),
            "note": "两个机制预测不同的观测变量：该实验无法同时判定两者，先统一可观测口径"}
    first_measurement = measurement_of(first)
    second_measurement = measurement_of(second)
    if first_measurement and second_measurement and first_measurement != second_measurement:
        return "INSUFFICIENT_INFORMATION", "different_measurement", {
            **detail, "first_measurement": first.get("measurement"),
            "second_measurement": second.get("measurement"),
            "note": "同一观测变量但测量口径不同（采集/聚合方式不一致）"}
    first_kind, second_kind = first.get("kind"), second.get("kind")
    if first_kind != second_kind:
        return "CONDITIONALLY_DISTINGUISHABLE", "mixed_criterion_kinds", {
            **detail, "first_kind": first_kind, "second_kind": second_kind,
            "note": "两种判据类型不同（例如区间 vs 方向）：可以比较，但必须先声明判别规则"}

    if first_kind == "quantitative":
        raw_first, raw_second = declared_range(first), declared_range(second)
        if raw_first is None or raw_second is None:
            return "INSUFFICIENT_INFORMATION", "invalid_criterion", detail
        detail.update({"first_range": list(raw_first), "second_range": list(raw_second),
                       "first_margin": decision_margin(first),
                       "second_margin": decision_margin(second)})
        if intervals_intersect(raw_first, raw_second):
            reason = ("identical_criteria" if criterion_signature(first) == criterion_signature(second)
                      else "overlapping_intervals")
            return "NOT_DISTINGUISHABLE", reason, {
                **detail, "raw_gap": 0.0,
                "note": "冻结区间相交：同一个观测可以同时满足两个机制"}
        raw_gap = interval_gap(raw_first, raw_second)
        detail["raw_gap"] = raw_gap
        if intervals_intersect(effective_range(first), effective_range(second)):
            return "NOT_DISTINGUISHABLE", "within_uncertainty", {
                **detail,
                "note": "区间本身不相交，但被 tolerance + noise/√n 展宽后相交："
                        "该设计的分辨率不足以区分"}
        if rule is not None:
            min_separation = float(rule.get("min_separation") or 0.0)
            detail["min_separation"] = min_separation
            if raw_gap < min_separation:
                return "NOT_DISTINGUISHABLE", "below_declared_min_separation", {
                    **detail, "note": "间隔小于预先声明的最小可分辨效应"}
            return "DISTINGUISHABLE", "discrimination_rule_satisfied", detail
        return "CONDITIONALLY_DISTINGUISHABLE", "no_discrimination_rule", {
            **detail, "note": "预测冲突已成立，但尚未预先声明判别规则：先声明再执行"}

    if first_kind == "directional":
        if not directional_conflict(first, second):
            return "NOT_DISTINGUISHABLE", "non_conflicting_predictions", {
                **detail, "note": "两个机制预测同一方向：该实验不构成区分"}
        return "CONDITIONALLY_DISTINGUISHABLE", "no_discrimination_rule", {
            **detail, "note": "方向相反，但需要预先声明的判别规则（含最小可分辨效应）"}

    if first_kind == "discrete":
        if not discrete_conflict(first, second):
            return "NOT_DISTINGUISHABLE", "non_conflicting_predictions", {
                **detail, "note": "标签集合不互斥：同一个观测可以同时满足两个机制"}
        return "DISTINGUISHABLE", "labels_mutually_exclusive", {
            **detail, "note": "互斥标签由预注册直接读出，不需要统计阈值"}

    return "INSUFFICIENT_INFORMATION", "invalid_criterion", detail


def resolve_prediction(state: Dict[str, Any], ref: Any) -> Tuple[Optional[Dict[str, Any]], List[Diagnostic]]:
    """Resolve `<XID>:<OID>` against the canonical frozen preregistration."""
    parsed = parse_ref(ref)
    if parsed is None:
        return None, [Diagnostic(
            "PC3", "prediction_ref",
            f"预测引用必须是 `<XID>:<OID>` 形式，实际 {ref!r}")]
    experiment_id, outcome_id = parsed
    view = cg.CanonicalView(state)
    experiment = view.get("experiments", experiment_id)
    if experiment is None:
        return None, [Diagnostic("PC3", f"prediction_ref:{ref}",
                                 f"引用的实验不存在：{experiment_id}")]
    preregistration = experiment.get("preregistration")
    if not isinstance(preregistration, dict):
        return None, [Diagnostic(
            "PC3", f"prediction_ref:{ref}",
            f"{experiment_id} 没有冻结的 preregistration，因此没有可判定的预测")]
    outcomes = preregistration.get("outcomes")
    outcome = None
    if isinstance(outcomes, list):
        outcome = next((item for item in outcomes
                        if isinstance(item, dict) and item.get("id") == outcome_id), None)
    if outcome is None:
        return None, [Diagnostic(
            "PC3", f"prediction_ref:{ref}",
            f"{experiment_id} 的 preregistration 里没有结果 {outcome_id}")]
    return {
        "ref": ref,
        "experiment_id": experiment_id,
        "outcome_id": outcome_id,
        "experiment": experiment,
        "outcome": outcome,
        "criterion": outcome.get("criterion"),
        "frozen_at_state_version": preregistration.get("frozen_at_state_version"),
        "result_at_state_version": experiment.get("result_at_state_version"),
    }, []


# ---------------------------------------------------------------------------
# Freeze integrity
# ---------------------------------------------------------------------------

def freeze_digest(experiment: Dict[str, Any]) -> str:
    """Digest of exactly what was frozen: the outcomes and the freeze version."""
    preregistration = experiment.get("preregistration")
    if not isinstance(preregistration, dict):
        return ""
    payload = {
        "frozen_at_state_version": preregistration.get("frozen_at_state_version"),
        "outcomes": preregistration.get("outcomes"),
    }
    return cg.digest_of(payload)


def check_freezes(
    state: Dict[str, Any],
    revisions: Sequence[Dict[str, Any]],
) -> List[Diagnostic]:
    """Detect a silent rewrite of a frozen prediction, and late criteria.

    A recorded `preregistration.amended[]` entry makes an edit traceable, but only if it
    happened before the result existed. An amendment written at or after
    `result_at_state_version` is post-hoc and is reported as tampering.
    """
    diagnostics: List[Diagnostic] = []
    view = cg.CanonicalView(state)
    for record in revisions:
        if record.get("kind") != "prediction_freeze":
            continue
        path = f"{cg.REVISIONS_NAME}:{record.get('_line', '?')}"
        refs = cg.normalize_refs(record.get("refs"))
        for experiment_id in refs.get("experiments", []):
            experiment = view.get("experiments", experiment_id)
            if not isinstance(experiment, dict):
                diagnostics.append(Diagnostic(
                    "PC3", path, f"prediction_freeze 引用了不存在的实验：{experiment_id}"))
                continue
            after = record.get("after") if isinstance(record.get("after"), dict) else {}
            recorded = after.get("freeze_digest")
            current = freeze_digest(experiment)
            if not recorded:
                diagnostics.append(Diagnostic(
                    "PC5", path,
                    f"{experiment_id} 的 prediction_freeze 未登记 freeze_digest；"
                    "无法检测冻结后的改写"))
            elif recorded != current:
                diagnostics.extend(_tamper_diagnostics(state, experiment, experiment_id, path))
            if not _criterion_present(experiment):
                diagnostics.append(Diagnostic(
                    "PC1", f"experiments[{experiment_id}].preregistration.outcomes",
                    "冻结结果没有 criterion，比较器只能返回 UNTESTABLE；"
                    "请在结果产生前通过 preregistration.amended[] 补上可判定判据"))
            preregistration = experiment.get("preregistration") or {}
            frozen_at = preregistration.get("frozen_at_state_version")
            if isinstance(record.get("at_state_version"), int) and isinstance(frozen_at, int) \
                    and record["at_state_version"] != frozen_at:
                diagnostics.append(Diagnostic(
                    "PC5", path,
                    f"认知冻结登记发生在 state_version={record['at_state_version']}，"
                    f"canonical 冻结发生在 {frozen_at}；二者必须同轮"))
    return cg._dedupe(diagnostics)


def _tamper_diagnostics(
    state: Dict[str, Any],
    experiment: Dict[str, Any],
    experiment_id: str,
    path: str,
) -> List[Diagnostic]:
    preregistration = experiment.get("preregistration") or {}
    amended = preregistration.get("amended")
    result_version = experiment.get("result_at_state_version")
    if not isinstance(amended, list) or not amended:
        return [Diagnostic(
            "PC4", path,
            f"{experiment_id} 的冻结预测被改写，且没有 preregistration.amended[] 记录；"
            "静默改写违反 R13 Integrity Gate")]
    failures: List[Diagnostic] = []
    for entry in amended:
        if not isinstance(entry, dict):
            failures.append(Diagnostic("PC4", path, f"{experiment_id} 的 amended 条目必须是对象"))
            continue
        version = entry.get("at_state_version")
        if not isinstance(version, int) or isinstance(version, bool):
            failures.append(Diagnostic(
                "PC4", path, f"{experiment_id} 的 amended 条目缺少整数 at_state_version"))
            continue
        if not isinstance(entry.get("reason"), str) or not entry["reason"].strip():
            failures.append(Diagnostic(
                "PC4", path, f"{experiment_id} 的 amended 条目缺少非空 reason"))
        if isinstance(result_version, int) and version >= result_version:
            failures.append(Diagnostic(
                "PC4", path,
                f"{experiment_id} 在结果写入（state_version={result_version}）之后"
                f"修订冻结预测（state_version={version}）；事后修订无效"))
    return failures


def _criterion_present(experiment: Dict[str, Any]) -> bool:
    preregistration = experiment.get("preregistration")
    if not isinstance(preregistration, dict):
        return False
    outcomes = preregistration.get("outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        return False
    return all(isinstance(item, dict) and isinstance(item.get("criterion"), dict)
               for item in outcomes)


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare_outcome(
    criterion: Dict[str, Any],
    observation: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """Compare one frozen criterion against one observation.

    Returns `(class, detail)`. The detail records the numbers actually used, so a reader
    can re-derive the verdict instead of trusting the label.
    """
    kind = criterion.get("kind")
    detail: Dict[str, Any] = {"kind": kind, "quantity": criterion.get("quantity")}
    if kind == "quantitative":
        value = observation.get("value")
        if not _is_number(value):
            return "UNTESTABLE", {**detail, "reason": "观测没有提供数值 value"}
        low, high = criterion["expected_range"]
        tolerance = criterion["tolerance"]
        detail.update({"observed": value, "expected_range": [low, high], "tolerance": tolerance})
        if low <= value <= high:
            return "PREDICTION_HELD", detail
        distance = (low - value) if value < low else (value - high)
        detail["distance_outside_range"] = distance
        if distance <= tolerance:
            return "WITHIN_TOLERANCE", detail
        return "PREDICTION_DEVIATED", detail
    if kind == "directional":
        expected = criterion["direction"]
        tolerance = criterion["tolerance"]
        observed = observation.get("direction")
        detail.update({"expected_direction": expected, "tolerance": tolerance})
        if observed is not None:
            if observed not in DIRECTIONS:
                return "UNTESTABLE", {**detail, "reason": f"direction 非法：{observed!r}"}
            detail["observed_direction"] = observed
            return ("PREDICTION_HELD" if observed == expected
                    else "PREDICTION_DEVIATED"), detail
        value = observation.get("value")
        if not _is_number(value):
            return "UNTESTABLE", {**detail, "reason": "观测没有提供 direction 或数值 value"}
        detail["observed"] = value
        if expected == "no_change":
            return ("PREDICTION_HELD" if abs(value) <= tolerance
                    else "PREDICTION_DEVIATED"), detail
        if abs(value) <= tolerance:
            return "WITHIN_TOLERANCE", detail
        observed_direction = "increase" if value > 0 else "decrease"
        detail["observed_direction"] = observed_direction
        return ("PREDICTION_HELD" if observed_direction == expected
                else "PREDICTION_DEVIATED"), detail
    if kind == "discrete":
        label = observation.get("label")
        detail.update({"held_labels": criterion["held_labels"],
                       "failed_labels": criterion["failed_labels"]})
        if not isinstance(label, str) or not label.strip():
            return "UNTESTABLE", {**detail, "reason": "观测没有提供标签 label"}
        detail["observed_label"] = label
        if label in criterion["held_labels"]:
            return "PREDICTION_HELD", detail
        if label in criterion["failed_labels"]:
            return "PREDICTION_DEVIATED", detail
        return "UNTESTABLE", {**detail, "reason": f"标签 {label!r} 未在冻结判据中登记"}
    return "UNTESTABLE", {**detail, "reason": f"未知判据类型：{kind!r}"}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def observation_errors(packet: Any) -> List[Diagnostic]:
    if not isinstance(packet, dict):
        return [Diagnostic("PC2", "observation", "观测包必须是对象")]
    failures: List[Diagnostic] = []
    if packet.get("schema") != SCHEMA_OBSERVATION:
        failures.append(Diagnostic("PC2", "observation.schema",
                                   f"schema 必须是 {SCHEMA_OBSERVATION!r}"))
    if not isinstance(packet.get("experiment_id"), str) or not packet["experiment_id"].strip():
        failures.append(Diagnostic("PC2", "observation.experiment_id", "缺少 experiment_id"))
    execution = packet.get("execution")
    if not isinstance(execution, dict) or execution.get("validity") not in ("VALID", "INVALID", "UNKNOWN"):
        failures.append(Diagnostic(
            "PC2", "observation.execution",
            "execution.validity 必须是 VALID / INVALID / UNKNOWN"))
    if "observed_outcome" in packet:
        selected = packet["observed_outcome"]
        if not isinstance(selected, str) or not selected.strip():
            failures.append(Diagnostic(
                "PC2", "observation.observed_outcome",
                "observed_outcome 是分支选择，必须是非空字符串（指向冻结的 outcome id）"))
    outcomes = packet.get("outcomes")
    if not isinstance(outcomes, list):
        failures.append(Diagnostic("PC2", "observation.outcomes", "outcomes 必须是数组"))
        return failures
    for index, outcome in enumerate(outcomes):
        path = f"observation.outcomes[{index}]"
        if not isinstance(outcome, dict):
            failures.append(Diagnostic("PC2", path, "每个观测必须是对象"))
            continue
        if not isinstance(outcome.get("id"), str) or not outcome["id"].strip():
            failures.append(Diagnostic("PC2", path, "缺少 id"))
        if eg.source_observation({"diagnostic_observation": outcome.get("source")}) is None:
            failures.append(Diagnostic(
                "PC2", path + ".source",
                "source 必须绑定来源：恰好 {kind, location, content, digest}，"
                "kind ∈ {log, metric, result}，digest == digest(content)"))
    return failures


def _provenance_gaps(
    packet: Dict[str, Any],
    experiment: Dict[str, Any],
    preregistration: Dict[str, Any],
) -> List[str]:
    """The R8 / R9.O provenance a qualified comparison depends on.

    A comparison may still be *computed* without these, and it is useful to compute it.
    What it may not do is feed a scientific state transition, which is what this list
    separates. The authoritative transition gate stays `evidence_outcome.py` and
    `state_check.py`; this only reports whether the comparator's own inputs are complete.
    """
    gaps: List[str] = []
    execution = packet.get("execution") or {}
    if execution.get("status") not in ("completed", "failed"):
        gaps.append("execution.status 缺失或非法")
    experiment_id = experiment.get("id")
    if experiment.get("status") not in ("done", "failed"):
        gaps.append(f"experiments[{experiment_id}].status={experiment.get('status')!r} "
                    "未进入终态")
    result_version = experiment.get("result_at_state_version")
    if not isinstance(result_version, int) or isinstance(result_version, bool):
        gaps.append(f"experiments[{experiment_id}].result_at_state_version 缺失")
    frozen_version = preregistration.get("frozen_at_state_version")
    if not isinstance(frozen_version, int) or isinstance(frozen_version, bool):
        gaps.append("preregistration.frozen_at_state_version 缺失")
    elif isinstance(result_version, int) and not isinstance(result_version, bool) \
            and frozen_version > result_version:
        gaps.append(f"预测时间泄漏：frozen_at_state_version={frozen_version} > "
                    f"result_at_state_version={result_version}")
    return gaps


def assess_experiment(
    state: Dict[str, Any],
    packet: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Diagnostic]]:
    """Adjudicate every frozen prediction of one experiment against its observation packet.

    The **frozen preregistration is the complete decision set.** The packet is evidence
    *about* it, not the set of things to decide. Walking the packet instead of the freeze
    makes selective submission a way to manufacture a `PREDICTION_HELD`, which is the
    defect this function used to have.

    Two adjudication modes, selected by the optional `observed_outcome` field:

    * **completeness mode** (no `observed_outcome`) — every frozen outcome must be
      addressed by an observation. `PREDICTION_HELD` requires all of them decided and held;
      a missing one caps the experiment at `PARTIALLY_ASSESSED`.
    * **branch mode** (`observed_outcome` names a frozen branch) — the frozen outcomes are
      mutually exclusive branches of one decision, so only the selected branch is
      adjudicated. A non-selected branch is not a failed prediction, and a second branch
      that *also* holds means the freeze cannot decide: `UNTESTABLE`, reason
      `ambiguous_preregistration`.

    Whatever the mode, an outcome that was never frozen may not enter the verdict set, a
    duplicated outcome makes that branch undecidable, and an execution whose validity is
    `UNKNOWN` produces a diagnostic comparison that is explicitly not evidence.
    """
    diagnostics = observation_errors(packet)
    view = cg.CanonicalView(state)
    experiment_id = packet.get("experiment_id")
    experiment = view.get("experiments", experiment_id) if isinstance(experiment_id, str) else None
    assessment: Dict[str, Any] = {
        "schema": SCHEMA_ASSESSMENT,
        "experiment_id": experiment_id,
        "execution": packet.get("execution"),
        "outcome_class": "UNTESTABLE",
        "diagnostic_outcome_class": None,
        "mode": "completeness",
        "selected_outcome": packet.get("observed_outcome"),
        "predictions": [],
        "not_selected": [],
        "branch_conflicts": [],
        "unexpected_observations": [],
        "frozen_outcome_ids": [],
        "frozen_at_state_version": None,
        "freeze_digest": None,
        "evidence_class": "INSUFFICIENT_PROVENANCE",
        "evidence_eligible": False,
        "scientific_status": "NO_INFERENCE",
        "provenance_gaps": [],
    }
    if experiment is None:
        diagnostics.append(Diagnostic("PC3", "observation.experiment_id",
                                      f"实验不存在：{experiment_id!r}"))
        assessment["diagnostics"] = [d.as_dict() for d in cg._dedupe(diagnostics)]
        return assessment, cg._dedupe(diagnostics)

    validity = (packet.get("execution") or {}).get("validity")
    if validity == "INVALID":
        # An invalid execution is never a prediction failure. R9.O classifies it, and the
        # observation cannot become evidence by looking plausible.
        assessment["outcome_class"] = "INVALID_EXECUTION"
        assessment["diagnostic_outcome_class"] = None
        assessment["evidence_class"] = "INSUFFICIENT_PROVENANCE"
        assessment["evidence_eligible"] = False
        assessment["scientific_status"] = "NO_INFERENCE"
        diagnostics.append(Diagnostic(
            "PC6", f"experiments[{experiment_id}]",
            "执行/测量无效：不产生预测判定，也不是异常；走 R9.O 的 INVALID_EXPERIMENT 与 failures[]"))
        assessment["diagnostics"] = [d.as_dict() for d in cg._dedupe(diagnostics)]
        return assessment, cg._dedupe(diagnostics)

    preregistration = experiment.get("preregistration")
    if not isinstance(preregistration, dict):
        assessment["outcome_class"] = "EXPLORATORY_ANOMALY"
        assessment["diagnostic_outcome_class"] = None
        assessment["evidence_class"] = "INSUFFICIENT_PROVENANCE"
        assessment["scientific_status"] = "NO_INFERENCE"
        diagnostics.append(Diagnostic(
            "PC1", f"experiments[{experiment_id}]",
            "没有冻结预注册：该观察只能登记为探索性异常，不得写成预测成立或失败"))
        assessment["diagnostics"] = [d.as_dict() for d in cg._dedupe(diagnostics)]
        return assessment, cg._dedupe(diagnostics)

    assessment["frozen_at_state_version"] = preregistration.get("frozen_at_state_version")
    assessment["freeze_digest"] = freeze_digest(experiment)

    frozen_items = [item for item in preregistration.get("outcomes") or []
                    if isinstance(item, dict)]
    frozen_ids = [item.get("id") for item in frozen_items]
    assessment["frozen_outcome_ids"] = frozen_ids

    # --- index the packet, without letting it define the decision set -------------
    submitted: Dict[str, Dict[str, Any]] = {}
    duplicated: set = set()
    for index, observed in enumerate(packet.get("outcomes") or []):
        if not isinstance(observed, dict):
            continue
        outcome_id = observed.get("id")
        if outcome_id in submitted:
            duplicated.add(outcome_id)
            diagnostics.append(Diagnostic(
                "PC2", f"observation.outcomes[{index}]",
                f"结果 id 重复：{outcome_id!r}；重复提交使该分支不可判定，且不得取其中之一"))
            continue
        submitted[outcome_id] = observed
    for outcome_id in sorted(submitted):
        if outcome_id not in frozen_ids:
            assessment["unexpected_observations"].append(outcome_id)
            diagnostics.append(Diagnostic(
                "PC2", f"observation.outcomes[{outcome_id}]",
                f"{experiment_id} 的冻结预注册里没有结果 {outcome_id!r}；"
                "未冻结的结果不得进入判定集合"))

    selected = packet.get("observed_outcome")
    if isinstance(selected, str) and selected.strip():
        selected = selected.strip()
        assessment["mode"] = "branch"
        assessment["selected_outcome"] = selected
        if selected not in frozen_ids:
            diagnostics.append(Diagnostic(
                "PC3", "observation.observed_outcome",
                f"observed_outcome={selected!r} 不是 {experiment_id} 的冻结结果之一；"
                "分支选择必须指向预注册"))

    adjudicate = _branches_to_adjudicate(assessment, frozen_items, selected)
    adjudicated_ids = {item.get("id") for item in adjudicate}
    # In branch mode the non-selected branches are still *probed* when the packet reports
    # them: if one of them holds as well, the freeze is not a set of exclusive branches and
    # the observation cannot say which one happened. Probes never enter the verdict set.
    probe = [item for item in frozen_items if item.get("id") not in adjudicated_ids] \
        if assessment["mode"] == "branch" else []
    held_branches: List[str] = []
    ambiguous_branches: List[str] = []
    for frozen in adjudicate + probe:
        outcome_id = frozen.get("id")
        role = "adjudicated" if outcome_id in adjudicated_ids else "probe"
        ref = f"{experiment_id}:{outcome_id}"
        entry: Dict[str, Any] = {"ref": ref, "outcome_id": outcome_id, "role": role,
                                 "selected": outcome_id == assessment.get("selected_outcome")}
        observed = submitted.get(outcome_id)
        def record(payload: Dict[str, Any]) -> None:
            entry.update(payload)
            if role == "probe":
                assessment["branch_conflicts"].append(entry)
            else:
                assessment["predictions"].append(entry)
                if entry.get("verdict") == "PREDICTION_HELD":
                    held_branches.append(outcome_id)

        if outcome_id in duplicated:
            record({"verdict": "UNTESTABLE", "reason": "duplicate_observation"})
            continue
        if observed is None:
            record({"verdict": "UNTESTABLE", "reason": "missing_observation"})
            if role == "adjudicated":
                diagnostics.append(Diagnostic(
                    "PC8", f"experiments[{experiment_id}].preregistration.outcomes[{outcome_id}]",
                    "冻结结果是判定集合的成员，但观测包里没有任何对应观测："
                    "未完成评价不得宣称预测成立"))
            continue
        criterion = frozen.get("criterion")
        if not isinstance(criterion, dict):
            record({"verdict": "UNTESTABLE", "reason": "no_criterion"})
            if role == "adjudicated":
                diagnostics.append(Diagnostic(
                    "PC1", f"experiments[{experiment_id}].preregistration.outcomes[{outcome_id}]",
                    "冻结结果没有 criterion：不得宣告预测成立或失败"))
            continue
        shape = criterion_errors(
            criterion,
            f"experiments[{experiment_id}].preregistration.outcomes[{outcome_id}].criterion")
        diagnostics.extend(shape)
        if shape:
            record({"verdict": "UNTESTABLE", "reason": "invalid_criterion"})
            continue
        verdict, detail = compare_outcome(criterion, observed)
        record({"verdict": verdict, "detail": detail,
                "criterion_signature": criterion_signature(criterion),
                "observation_statement": frozen.get("observation")})
        if role == "probe" and verdict == "PREDICTION_HELD":
            ambiguous_branches.append(outcome_id)

    for frozen in _not_selected_branches(assessment, frozen_items):
        assessment["not_selected"].append(frozen.get("id"))

    # Ambiguity is a *branch* defect: one observation satisfies the selected branch and
    # another branch of the same freeze. In completeness mode each outcome is an
    # independent adjudication, so two held outcomes are simply two held predictions.
    ambiguous = bool(ambiguous_branches)
    if ambiguous:
        diagnostics.append(Diagnostic(
            "PC8", f"experiments[{experiment_id}]",
            f"冻结预注册不是互斥分支：选中的 {assessment.get('selected_outcome')} 与"
            f"{ambiguous_branches} 同时成立，一次观测无法判定哪一支发生；"
            "该预注册必须先修正"))

    diagnostic_class = _aggregate(
        assessment["predictions"], assessment["mode"], ambiguous)
    assessment["diagnostic_outcome_class"] = diagnostic_class

    gaps = _provenance_gaps(packet, experiment, preregistration)
    assessment["provenance_gaps"] = gaps
    if validity == "UNKNOWN":
        assessment["evidence_class"] = "DIAGNOSTIC_ONLY"
        assessment["scientific_status"] = "DIAGNOSTIC_ONLY"
        diagnostics.append(Diagnostic(
            "PC7", f"experiments[{experiment_id}]",
            "execution.validity=UNKNOWN：允许保留诊断性比较结果，但它不是合格科学证据，"
            "不得据此支持或否证机制、升级 Insight 或触发 R10/R11 状态迁移；"
            "先补齐执行收据与来源绑定"))
    elif gaps:
        assessment["evidence_class"] = "DIAGNOSTIC_ONLY"
        assessment["scientific_status"] = "DIAGNOSTIC_ONLY"
        diagnostics.append(Diagnostic(
            "PC7", f"experiments[{experiment_id}]",
            "关键 provenance 不完整（" + "；".join(gaps) + "）：只能作为诊断信息，"
            "不得支持或否证机制，也不得升级 Insight"))
    elif assessment["unexpected_observations"] or duplicated \
            or any(entry.get("reason") == "missing_observation"
                   for entry in assessment["predictions"]) or ambiguous:
        assessment["evidence_class"] = "DIAGNOSTIC_ONLY"
        assessment["scientific_status"] = "DIAGNOSTIC_ONLY"
        diagnostics.append(Diagnostic(
            "PC7", f"experiments[{experiment_id}]",
            "观测包与冻结预注册不一致（缺失/额外/重复/歧义）：该比较只能作为诊断信息，"
            "先修正冻结与观测的对应关系"))
    else:
        assessment["evidence_class"] = "QUALIFIED_EVIDENCE"
        assessment["evidence_eligible"] = True
        assessment["scientific_status"] = "MAY_INFORM_TRANSITION"

    # The scientific verdict slot never carries an unqualified support or refutation claim.
    # The comparison stays available as `diagnostic_outcome_class` for the researcher.
    if assessment["evidence_eligible"] or diagnostic_class not in WORLD_CLAIMING_CLASSES:
        assessment["outcome_class"] = diagnostic_class
    else:
        assessment["outcome_class"] = "UNTESTABLE"
        assessment["outcome_class_downgraded_from"] = diagnostic_class
        diagnostics.append(Diagnostic(
            "PC7", f"experiments[{experiment_id}]",
            f"比较结果是 {diagnostic_class}，但证据不合格：科学判定栏只能记 UNTESTABLE，"
            f"诊断结果保留在 diagnostic_outcome_class={diagnostic_class}"))

    diagnostics.extend(_aggregate_diagnostics(experiment_id, assessment))
    assessment["diagnostics"] = [d.as_dict() for d in cg._dedupe(diagnostics)]
    return assessment, cg._dedupe(diagnostics)


def _branches_to_adjudicate(
    assessment: Dict[str, Any],
    frozen_items: List[Dict[str, Any]],
    selected: Any,
) -> List[Dict[str, Any]]:
    """Branch mode adjudicates the selected branch; completeness mode adjudicates all."""
    if assessment["mode"] == "branch" and isinstance(selected, str):
        chosen = [item for item in frozen_items if item.get("id") == selected]
        if chosen:
            return chosen
    return frozen_items


def _not_selected_branches(
    assessment: Dict[str, Any],
    frozen_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if assessment["mode"] != "branch":
        return []
    selected = assessment.get("selected_outcome")
    return [item for item in frozen_items if item.get("id") != selected]


def _aggregate(
    predictions: List[Dict[str, Any]],
    mode: str = "completeness",
    ambiguous: bool = False,
) -> str:
    """Turn per-outcome verdicts into one class for the experiment.

    `PREDICTION_HELD` means *every adjudicated frozen prediction held*. Anything short of
    that is reported as such: `PARTIALLY_ASSESSED` when some outcomes were decided and
    others were not, `UNTESTABLE` when none were. A single deviation is not promoted to
    `PREDICTION_DEVIATED` while sibling outcomes remain undecided.
    """
    if not predictions:
        return "UNTESTABLE"
    if ambiguous:
        return "UNTESTABLE"
    verdicts = [entry.get("verdict") for entry in predictions]
    decided = [verdict for verdict in verdicts
               if verdict in ("PREDICTION_HELD", "PREDICTION_DEVIATED", "WITHIN_TOLERANCE")]
    undecided = len(verdicts) - len(decided)
    if undecided == 0:
        if all(verdict == "PREDICTION_HELD" for verdict in verdicts):
            return "PREDICTION_HELD"
        if any(verdict == "PREDICTION_DEVIATED" for verdict in verdicts):
            return "PREDICTION_DEVIATED"
        if any(verdict == "WITHIN_TOLERANCE" for verdict in verdicts):
            return "WITHIN_TOLERANCE"
        return "UNTESTABLE"
    if decided:
        return "PARTIALLY_ASSESSED"
    return "UNTESTABLE"


def _aggregate_diagnostics(experiment_id: str, assessment: Dict[str, Any]) -> List[Diagnostic]:
    outcomes: List[Diagnostic] = []
    if assessment.get("diagnostic_outcome_class") == "PREDICTION_DEVIATED":
        failed = [entry["ref"] for entry in assessment["predictions"]
                  if entry.get("verdict") == "PREDICTION_DEVIATED"]
        outcomes.append(Diagnostic(
            "PC6", f"experiments[{experiment_id}]",
            f"预测偏差：{failed}；异常记录必须引用冻结侧与观测侧，并说明是否复现"))
    if assessment.get("diagnostic_outcome_class") == "PARTIALLY_ASSESSED":
        undecided = [entry["ref"] for entry in assessment["predictions"]
                     if entry.get("verdict") not in
                     ("PREDICTION_HELD", "PREDICTION_DEVIATED", "WITHIN_TOLERANCE")]
        outcomes.append(Diagnostic(
            "PC8", f"experiments[{experiment_id}]",
            f"部分评价：{undecided} 尚未判定；不得据此宣称全部预测成立"))
    return outcomes


def evidence_transition_allowed(
    state: Dict[str, Any],
    assessment: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Whether a comparison may feed a scientific state transition.

    This is the comparator-side precondition only. The authority for a claim-status change
    remains R8's single-direction upgrade or R10, and the authoritative gates remain
    `scripts/evidence_outcome.py` plus `scripts/state_check.py`; a `True` here grants
    nothing on its own.
    """
    reasons: List[str] = []
    validity = (assessment.get("execution") or {}).get("validity")
    if validity not in ("VALID",):
        reasons.append(f"execution.validity={validity!r}：只有 VALID 的执行可以进入科学判定")
    if assessment.get("evidence_class") != "QUALIFIED_EVIDENCE":
        reasons.append(
            f"evidence_class={assessment.get('evidence_class')!r}："
            f"{'; '.join(assessment.get('provenance_gaps') or []) or '诊断性比较不是合格证据'}")
    if assessment.get("provenance_gaps"):
        reasons.extend(assessment["provenance_gaps"])
    if assessment.get("unexpected_observations"):
        reasons.append("观测包含未冻结结果："
                       + ", ".join(str(item) for item in assessment["unexpected_observations"]))
    if any(entry.get("reason") == "missing_observation"
           for entry in assessment.get("predictions") or []):
        reasons.append("存在未被观测的冻结预测：评价未完成")
    if assessment.get("outcome_class") == "INVALID_EXECUTION":
        reasons.append("执行无效：走 R9.O 的 INVALID_EXPERIMENT 与 failures[]")
    if assessment.get("outcome_class_downgraded_from"):
        reasons.append("科学判定栏已被降级为 UNTESTABLE（原比较结果："
                       f"{assessment['outcome_class_downgraded_from']}）")
    experiment_id = assessment.get("experiment_id")
    view = cg.CanonicalView(state)
    experiment = view.get("experiments", experiment_id) if isinstance(experiment_id, str) else None
    if not isinstance(experiment, dict):
        reasons.append(f"实验不存在：{experiment_id!r}")
    else:
        frozen = (experiment.get("preregistration") or {}).get("frozen_at_state_version")
        result = experiment.get("result_at_state_version")
        if isinstance(frozen, int) and isinstance(result, int) and frozen > result:
            reasons.append("预测冻结晚于结果：时间顺序约束被破坏")
    return (not reasons), reasons


# ---------------------------------------------------------------------------
# Mechanism competition
# ---------------------------------------------------------------------------

#: Ordering of the verdicts by how much separating power they grant, weakest first.
_VERDICT_RANK: Dict[str, int] = {
    "INSUFFICIENT_INFORMATION": 0,
    "NOT_DISTINGUISHABLE": 1,
    "CONDITIONALLY_DISTINGUISHABLE": 2,
    "DISTINGUISHABLE": 3,
}

#: Experiment statuses for which an intervention can still be run.
ACTIONABLE_STATUSES: Tuple[str, ...] = ("planned", "running")


def distinguishability(
    state: Dict[str, Any],
    competition: Dict[str, Any],
    mechanisms: Optional[Sequence[Dict[str, Any]]] = None,
) -> Tuple[Dict[str, Any], List[Diagnostic]]:
    """Decide whether the declared intervention can actually separate the mechanisms.

    The verdict is built from four operational checks, none of which reads prose:

    1. **Comparability** — every pair must predict the *same observed variable* and, when
       both declare a measurement basis, the same basis. Different metrics are not a
       competition, they are two different experiments.
    2. **Conflict** — the declared ranges (or directions, or label sets) must not both be
       satisfiable by one observation. Overlapping intervals have no separating power.
    3. **Resolution** — the declared ranges, widened by `tolerance + noise / sqrt(n)`, must
       remain disjoint. If they do not, the design cannot resolve the difference, and the
       reason is recorded as `within_uncertainty`.
    4. **Pre-declared rule** — a `discrimination_rule` must fix the threshold *before* the
       run. Without it the pair is only `CONDITIONALLY_DISTINGUISHABLE`; with a
       `min_separation` larger than the actual gap it is `NOT_DISTINGUISHABLE`.

    With more than two mechanisms the experiment must separate **every** pair, so the
    overall verdict is the weakest pair verdict. No text similarity and no self-rating
    enters: the inputs are frozen numbers, label sets and declared design parameters.
    """
    diagnostics: List[Diagnostic] = []
    competition_id = competition.get("id")
    verdict: Dict[str, Any] = {
        "competition": competition_id,
        "verdict": "INSUFFICIENT_INFORMATION",
        "reason": "insufficient_mechanisms",
        "mechanisms": list(competition.get("mechanisms") or []),
        "intervention": competition.get("discriminating_intervention"),
        "intervention_actionable": False,
        "decision_impact": competition.get("decision_impact", "unknown"),
        "discrimination_rule": competition.get("discrimination_rule"),
        "per_mechanism": {},
        "pairs": [],
        "has_distinguishing_power": False,
    }

    def fail(code: str, detail: str, level: str = "PC6") -> Tuple[Dict[str, Any], List[Diagnostic]]:
        verdict["verdict"] = "INSUFFICIENT_INFORMATION"
        verdict["reason"] = code
        diagnostics.append(Diagnostic(level, f"competitions[{competition_id}]", detail))
        verdict["diagnostics"] = [d.as_dict() for d in cg._dedupe(diagnostics)]
        return verdict, cg._dedupe(diagnostics)

    names = competition.get("mechanisms")
    if not isinstance(names, list) or len(names) < 2:
        return fail("insufficient_mechanisms", "竞争至少需要两个机制")

    refs: List[Any] = list(competition.get("conflicting_predictions") or [])
    for entry in competition.get("predictions") or []:
        if isinstance(entry, dict) and entry.get("ref") not in refs:
            refs.append(entry.get("ref"))
    if not refs:
        return fail("no_prediction_gap",
                    "没有冲突预测的机制竞争不可判定：只并列多个可能原因不算竞争")

    intervention = competition.get("discriminating_intervention")
    view = cg.CanonicalView(state)
    intervention_experiment = (view.get("experiments", intervention)
                               if isinstance(intervention, str) else None)
    if not isinstance(intervention_experiment, dict) or intervention in ("", "TBD", None):
        return fail("no_intervention",
                    "没有可执行的判别干预：先设计最小干预，不要继续增加解释")
    if intervention_experiment.get("status") not in ACTIONABLE_STATUSES:
        return fail(
            "intervention_not_actionable",
            f"判别干预 {intervention} 的状态是 "
            f"{intervention_experiment.get('status')!r}；"
            "一个已经结束的实验不能用来区分机制，请登记可执行的判别实验")
    verdict["intervention_actionable"] = True

    resolved: Dict[str, Dict[str, Any]] = {}
    for ref in refs:
        entry, errors = resolve_prediction(state, ref)
        diagnostics.extend(errors)
        if entry is not None:
            resolved[ref] = entry
    if len(resolved) < 2:
        return fail("insufficient_predictions",
                    "冲突预测必须引用已冻结的 `<XID>:<OID>`；当前可解析的预测不足两条")

    on_intervention = {ref: entry for ref, entry in resolved.items()
                       if entry["experiment_id"] == intervention}
    if len(on_intervention) < 2:
        return fail("predictions_on_other_experiments",
                    f"判别干预 {intervention} 上可解析的冲突预测不足两条；"
                    "另一个机制的预测落在别的实验上，无法用该干预区分")
    resolved = on_intervention

    rule = competition.get("discrimination_rule")
    rule_shape = discrimination_rule_errors(rule, f"competitions[{competition_id}].discrimination_rule")
    diagnostics.extend(rule_shape)
    if rule_shape:
        return fail("invalid_criterion", "判别规则形状非法：" + rule_shape[0].detail)

    owned, ownership_errors = _owned_predictions(competition, names, mechanisms, resolved)
    diagnostics.extend(ownership_errors)
    verdict["per_mechanism"] = {
        name: {
            "predictions": owned.get(name, []),
            "observables": sorted({observable_of(resolved[ref]["criterion"])
                                   for ref in owned.get(name, []) if ref in resolved
                                   and isinstance(resolved[ref].get("criterion"), dict)}),
            "kinds": sorted({resolved[ref]["criterion"].get("kind")
                             for ref in owned.get(name, []) if ref in resolved
                             and isinstance(resolved[ref].get("criterion"), dict)}),
        } for name in names
    }
    if ownership_errors:
        verdict["reason"] = "no_ownership"
        verdict["diagnostics"] = [d.as_dict() for d in cg._dedupe(diagnostics)]
        return verdict, cg._dedupe(diagnostics)

    # --- pairwise analysis: an experiment must separate every pair ---------------
    pair_results: List[Dict[str, Any]] = []
    for left_index, left in enumerate(names):
        for right in names[left_index + 1:]:
            for left_ref in sorted(owned.get(left, [])):
                for right_ref in sorted(owned.get(right, [])):
                    left_criterion = resolved[left_ref].get("criterion")
                    right_criterion = resolved[right_ref].get("criterion")
                    if not isinstance(left_criterion, dict) or not isinstance(right_criterion, dict):
                        pair_results.append({
                            "left": left, "right": right, "left_ref": left_ref,
                            "right_ref": right_ref, "verdict": "INSUFFICIENT_INFORMATION",
                            "reason": "invalid_criterion",
                            "detail": {"note": "缺少可判定判据"}})
                        continue
                    if criterion_errors(left_criterion, "criterion") or \
                            criterion_errors(right_criterion, "criterion"):
                        pair_results.append({
                            "left": left, "right": right, "left_ref": left_ref,
                            "right_ref": right_ref, "verdict": "INSUFFICIENT_INFORMATION",
                            "reason": "invalid_criterion",
                            "detail": {"note": "判据形状非法"}})
                        continue
                    pair_verdict, reason, detail = pair_discrimination(
                        left_criterion, right_criterion, rule)
                    pair_results.append({
                        "left": left, "right": right, "left_ref": left_ref,
                        "right_ref": right_ref, "verdict": pair_verdict,
                        "reason": reason, "detail": detail})
    verdict["pairs"] = pair_results
    if not pair_results:
        return fail("insufficient_predictions", "没有任何可比较的预测对")

    weakest_rank = min(_VERDICT_RANK[pair["verdict"]] for pair in pair_results)
    weakest = [pair for pair in pair_results if _VERDICT_RANK[pair["verdict"]] == weakest_rank]
    weakest.sort(key=lambda pair: (pair["reason"], pair["left_ref"], pair["right_ref"]))
    overall = weakest[0]["verdict"]
    verdict["verdict"] = overall
    verdict["reason"] = weakest[0]["reason"]
    verdict["witness_pair"] = {"left": weakest[0]["left"], "right": weakest[0]["right"],
                               "left_ref": weakest[0]["left_ref"],
                               "right_ref": weakest[0]["right_ref"]}
    verdict["has_distinguishing_power"] = overall == "DISTINGUISHABLE"

    if overall == "DISTINGUISHABLE":
        verdict["fixed_by"] = ("labels_mutually_exclusive"
                               if all(pair["reason"] == "labels_mutually_exclusive" for pair in weakest)
                               else "discrimination_rule_satisfied")
    elif overall == "CONDITIONALLY_DISTINGUISHABLE":
        diagnostics.append(Diagnostic(
            "PC6", f"competitions[{competition_id}]",
            "预测冲突成立，但缺少预先声明的 discrimination_rule："
            "在执行前声明统计量与最小可分辨间隔，否则结果无法判定哪一方胜出"))
    elif overall == "NOT_DISTINGUISHABLE":
        diagnostics.append(Diagnostic(
            "PC6", f"competitions[{competition_id}]",
            f"该设计无法区分机制（{weakest[0]['reason']}）："
            f"{weakest[0]['detail'].get('note', '')}；再跑同一设计不会改变结论"))
    else:
        diagnostics.append(Diagnostic(
            "PC6", f"competitions[{competition_id}]",
            f"无法定义判别比较（{weakest[0]['reason']}）："
            f"{weakest[0]['detail'].get('note', '')}"))

    verdict["diagnostics"] = [d.as_dict() for d in cg._dedupe(diagnostics)]
    return verdict, cg._dedupe(diagnostics)


def _owned_predictions(
    competition: Dict[str, Any],
    names: List[str],
    mechanisms: Optional[Sequence[Dict[str, Any]]],
    resolved: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, List[str]], List[Diagnostic]]:
    """Attribute each frozen prediction to exactly one mechanism."""
    competition_id = competition.get("id")
    explicit: Dict[str, List[str]] = {}
    for entry in competition.get("predictions") or []:
        if isinstance(entry, dict) and isinstance(entry.get("mechanism"), str) \
                and isinstance(entry.get("ref"), str):
            explicit.setdefault(entry["mechanism"], []).append(entry["ref"])
    declared: Dict[str, List[str]] = {}
    for mechanism in mechanisms or []:
        if not isinstance(mechanism, dict):
            continue
        structure = mechanism.get("structure") or {}
        declared[mechanism.get("id")] = [ref for ref in structure.get("pending_predictions") or []
                                        if isinstance(ref, str)]

    owned: Dict[str, List[str]] = {name: [] for name in names}
    for ref in resolved:
        candidates = {name for name, refs in explicit.items() if ref in refs}
        if not candidates:
            candidates = {name for name, refs in declared.items()
                          if ref in refs and name in names}
        for name in candidates:
            owned.setdefault(name, []).append(ref)

    errors: List[Diagnostic] = []
    for name in names:
        unique = sorted({ref for ref in owned.get(name, []) if ref in resolved})
        owned[name] = unique
        if not unique:
            errors.append(Diagnostic(
                "PC6", f"competitions[{competition_id}]",
                f"无法把任何冲突预测归属到机制 {name}；请在竞争里写 `predictions[].mechanism`，"
                "或在机制结构里登记 pending_predictions"))
        elif not any(isinstance(resolved[ref].get("criterion"), dict) for ref in unique):
            errors.append(Diagnostic(
                "PC6", f"competitions[{competition_id}]",
                f"机制 {name} 的预测没有可判定判据，无法比较区分力"))
    return owned, errors


# ---------------------------------------------------------------------------
# Diagnosis-to-intervention behaviour switch
# ---------------------------------------------------------------------------

def _reason_summary(verdicts: Sequence[Dict[str, Any]], limit: int = 3) -> str:
    """Deterministic, compact reason list for the switch explanation."""
    reasons = sorted({str(item.get("reason")) for item in verdicts if item.get("reason")})
    shown = reasons[:limit]
    return ", ".join(shown) + ("…" if len(reasons) > limit else "")


def trailing_zero_streak(scheduler: Optional[Dict[str, Any]]) -> int:
    """Consecutive trailing diagnostics that produced no information.

    `actual_information_gain == "zero"` is defined by the scheduler policy as "the
    observed delta is empty". Counting that streak is mechanical; it does not re-rate
    anything and it never rewrites the historical prediction.
    """
    if not isinstance(scheduler, dict):
        return 0
    calibration = scheduler.get("eig_calibration")
    records = calibration.get("records") if isinstance(calibration, dict) else None
    if not isinstance(records, list):
        return 0
    streak = 0
    for record in reversed(records):
        if not isinstance(record, dict):
            break
        if record.get("actual_information_gain") == "zero":
            streak += 1
            continue
        break
    return streak


def diagnosis_switch(
    state: Dict[str, Any],
    competitions: Sequence[Dict[str, Any]],
    scheduler: Optional[Dict[str, Any]] = None,
    mechanisms: Optional[Sequence[Dict[str, Any]]] = None,
    threshold: int = DEFAULT_ZERO_STREAK,
) -> Dict[str, Any]:
    """Recommend a behaviour change instead of another round of attribution.

    The recommendation maps onto existing authority: `REDESIGN_QUESTION` routes through
    T8 and the existing `STOP_DIAGNOSIS` handling, `RECORD_BOUNDARY_AND_STOP` is an R10/R14
    decision, and `EXPLORE_METHOD_UNDER_UNCERTAINTY` is the existing permission to design a
    method intervention from an unverified mechanism.
    """
    verdicts = [distinguishability(state, competition, mechanisms)[0]
                for competition in competitions
                if competition.get("status") in ("open", "undecidable_recorded")]
    blocked = [v for v in verdicts if v["verdict"] != "DISTINGUISHABLE"]
    # `CONDITIONALLY_DISTINGUISHABLE` is a design step away from being usable: the
    # predictions conflict, only the pre-declared decision rule is missing. Grouping it
    # with the fixable reasons keeps the advice actionable instead of discouraging the run.
    design_fixable = [v for v in blocked
                      if v.get("reason") in DESIGN_FIXABLE_REASONS
                      or v["verdict"] == "CONDITIONALLY_DISTINGUISHABLE"]
    structural = [v for v in blocked if v.get("reason") in STRUCTURAL_REASONS]
    same_decision = [v for v in blocked if v.get("decision_impact") == "same_method_decision"]
    streak = trailing_zero_streak(scheduler)

    action = "CONTINUE_ATTRIBUTION"
    reason = "诊断仍在产生可执行的信息，或现有判别干预已经有效。"
    if streak >= threshold:
        if design_fixable:
            action = "FIND_DISCRIMINATING_INTERVENTION"
            reason = (f"连续 {streak} 次诊断的实际信息增益为 zero，且竞争尚不可判定"
                      f"（{_reason_summary(design_fixable)}）：先把判别条件补齐，"
                      "不要再增加解释。")
        elif structural and same_decision:
            action = "RECORD_BOUNDARY_AND_STOP"
            reason = (f"机制在该设计下不可区分（{_reason_summary(structural)}）"
                      "且不改变方法决策：记录未解边界并停止继续归因。")
        else:
            action = "REDESIGN_QUESTION"
            reason = (f"连续 {streak} 次诊断没有带来新的有效预测，也没有改变方法或资源决策"
                      f"（{_reason_summary(blocked)}）："
                      "按 T8 走 R5.1 定向补检索，再交 R3 reseed 或 R6 改造。")
    elif blocked:
        if design_fixable:
            action = "FIND_DISCRIMINATING_INTERVENTION"
            reason = ("竞争尚不可判定（" + _reason_summary(design_fixable) + "）："
                      "先补上可执行的判别条件——统一可观测口径、登记可运行的最小干预、"
                      "或声明判别规则。")
        elif same_decision:
            action = "RECORD_BOUNDARY_AND_STOP"
            reason = ("机制不可区分且不影响方法决策（" + _reason_summary(blocked) + "）："
                      "记录边界即可，不必继续归因。")
        else:
            action = "EXPLORE_METHOD_UNDER_UNCERTAINTY"
            reason = ("完整归因不是方法决策所必需（" + _reason_summary(blocked) + "）："
                      "把机制标为假设，用同一个干预同时检验机制与收益。")
    return {
        "action": action,
        "reason": reason,
        "zero_streak": streak,
        "threshold": threshold,
        "competition_verdicts": verdicts,
        "independent_exploration_allowed": True,
        "note": ("普通未知、尚未验证的机制与候选存在本身都不是全局阻塞；"
                 "本建议只改变归因方向的优先级，不新增预算规则，也不替代 R10/R14 的权限。"),
    }


# ---------------------------------------------------------------------------
# Insight cards
# ---------------------------------------------------------------------------

CARD_REQUIRED_TEXT: Tuple[str, ...] = (
    "observation", "existing_mechanism", "challenged_assumption", "proposed_mechanism",
    "explanatory_gain", "competing_mechanism", "scope_boundary", "scientific_implication",
)


def insight_card_errors(card: Any, state: Dict[str, Any]) -> List[Diagnostic]:
    if not isinstance(card, dict):
        return [Diagnostic("PC8", "insight_card", "Insight Card 必须是对象")]
    failures: List[Diagnostic] = []
    if card.get("_schema") != SCHEMA_INSIGHT:
        failures.append(Diagnostic("PC8", "insight_card._schema",
                                   f"_schema 必须是 {SCHEMA_INSIGHT!r}"))
    if not isinstance(card.get("id"), str) or not card["id"].strip():
        failures.append(Diagnostic("PC8", "insight_card.id", "缺少非空 id"))
    version = card.get("at_state_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        failures.append(Diagnostic("PC8", "insight_card.at_state_version",
                                   "at_state_version 必须是非负整数"))
    elif version > (state.get("state_version") if isinstance(state.get("state_version"), int) else 0):
        failures.append(Diagnostic("PC8", "insight_card.at_state_version",
                                   "at_state_version 超过当前 state_version"))
    for field in CARD_REQUIRED_TEXT:
        if not isinstance(card.get(field), str) or not card[field].strip():
            failures.append(Diagnostic("PC8", f"insight_card.{field}",
                                       f"Insight Card 必须给出 {field}"))
    prediction = card.get("novel_prediction")
    if not isinstance(prediction, dict) or not prediction.get("ref"):
        failures.append(Diagnostic(
            "PC8", "insight_card.novel_prediction",
            "必须给出 novel_prediction.ref（`<XID>:<OID>`）；没有独立预测的只能登记为解释性假设"))
    else:
        _, errors = resolve_prediction(state, prediction.get("ref"))
        failures.extend(errors)
        if not isinstance(prediction.get("statement"), str) or not prediction["statement"].strip():
            failures.append(Diagnostic("PC8", "insight_card.novel_prediction.statement",
                                       "novel_prediction 必须给出 statement"))
    intervention = card.get("discriminating_intervention")
    if not isinstance(intervention, str) or not intervention.strip():
        failures.append(Diagnostic("PC8", "insight_card.discriminating_intervention",
                                   "必须给出判别干预"))
    refs = cg.normalize_refs(card.get("refs"))
    if not any(refs.get(key) for key in cg.REF_KEYS):
        failures.append(Diagnostic("PC8", "insight_card.refs",
                                   "Insight Card 必须引用 canonical 对象"))
    for key, ident in cg.iter_refs(refs):
        if not cg.CanonicalView(state).contains(key, ident):
            failures.append(Diagnostic("PC8", "insight_card.refs",
                                       f"悬空引用 {key}[{ident}]"))
    declared = card.get("declared_class")
    if declared not in INSIGHT_CLASSES:
        failures.append(Diagnostic("PC8", "insight_card.declared_class",
                                   f"declared_class 必须是 {list(INSIGHT_CLASSES)} 之一"))
    derived, reasons = classify_insight(card, state)
    if declared == "evidence_supported_insight" and derived != "evidence_supported_insight":
        failures.append(Diagnostic(
            "PC7", "insight_card.declared_class",
            f"自我认证：卡片声称 evidence_supported_insight，canonical 事实只能推出 {derived}；"
            f"缺少 {reasons.get('missing') or ['独立证据']}"))
    elif declared != derived:
        failures.append(Diagnostic(
            "PC9", "insight_card.declared_class",
            f"声明类别 {declared} 与推导类别 {derived} 不一致；以推导类别为准"))
    return cg._dedupe(failures)


def classify_insight(card: Dict[str, Any], state: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Derive the insight class from canonical facts, never from the card's own label."""
    view = cg.CanonicalView(state)
    reasons: Dict[str, Any] = {"missing": []}
    prediction = card.get("novel_prediction")
    ref = prediction.get("ref") if isinstance(prediction, dict) else None
    resolved, errors = resolve_prediction(state, ref) if ref else (None, [])
    if resolved is None:
        reasons["missing"].append("可解析的冻结预测")
        return "explanatory_hypothesis", reasons
    criterion = resolved.get("criterion")
    if not isinstance(criterion, dict) or criterion_errors(criterion, "criterion"):
        reasons["missing"].append("可判定判据")
        return "explanatory_hypothesis", reasons
    intervention = card.get("discriminating_intervention")
    has_intervention = (isinstance(intervention, str) and intervention.strip()
                        and view.contains("experiments", intervention))
    # Evidence support needs a valid, strong enough, in-scope observation of the new
    # prediction, plus an independent structural-equivalence audit of the claim.
    refs = cg.normalize_refs(card.get("refs"))
    boundary = card.get("scope_boundary") or ""
    supported: List[str] = []
    for evidence_id in refs.get("evidence", []):
        evidence = view.get("evidence", evidence_id)
        if not isinstance(evidence, dict):
            continue
        status, _ = view.validity_of("evidence", evidence_id)
        if status != "valid" or not cg.tier_at_least(evidence.get("verification_tier"), 2):
            continue
        if evidence.get("epistemic_status") not in ("Observed", "Supported"):
            continue
        scope = evidence.get("scope")
        if not isinstance(scope, str) or not scope.strip():
            continue
        if not _scope_within(scope, boundary):
            continue
        if resolved["experiment_id"] not in [str(dep) for dep in evidence.get("depends_on") or []]:
            reasons["missing"].append(f"证据 {evidence_id} 未绑定到该实验")
            continue
        supported.append(evidence_id)
    audited = any(
        isinstance(entry, dict)
        and entry.get("attack_type") == "structural-equivalence"
        and cg.tier_at_least(entry.get("verification_tier"), 1)
        and entry.get("target") in (refs.get("claims") or []) + (refs.get("hypotheses") or [])
        for entry in view.assurance
    )
    reasons["supporting_evidence"] = supported
    reasons["structural_equivalence_audit"] = audited
    if supported and audited:
        return "evidence_supported_insight", reasons
    if not supported:
        reasons["missing"].append("valid 且 ≥ T2 的独立证据")
    if not audited:
        reasons["missing"].append("针对该主张的结构等价审计（防自我认证创新性）")
    if has_intervention:
        return "predictive_insight_candidate", reasons
    reasons["missing"].append("可执行的判别干预")
    return "explanatory_hypothesis", reasons


def _scope_within(evidence_scope: str, boundary: str) -> bool:
    """Conservative scope containment: one scope must textually contain the other."""
    if not boundary.strip():
        return False
    left, right = evidence_scope.strip(), boundary.strip()
    return left in right or right in left


# ---------------------------------------------------------------------------
# Card I/O
# ---------------------------------------------------------------------------

def load_cards(path: Path) -> Tuple[List[Dict[str, Any]], List[Diagnostic]]:
    """Read insight cards. Malformed lines are reported, not raised."""
    diagnostics: List[Diagnostic] = []
    cards: List[Dict[str, Any]] = []
    if not path.exists():
        return cards, diagnostics
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            card = json.loads(stripped)
        except json.JSONDecodeError as exc:
            diagnostics.append(Diagnostic("PC8", f"{INSIGHT_CARDS_NAME}:{lineno}",
                                          f"无法解析为 JSON（{exc.msg}）"))
            continue
        if not isinstance(card, dict):
            diagnostics.append(Diagnostic("PC8", f"{INSIGHT_CARDS_NAME}:{lineno}",
                                          "每条 Insight Card 必须是对象"))
            continue
        card["_line"] = lineno
        cards.append(card)
    return cards, diagnostics


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def op_freeze(state_path: Path, experiment_id: str) -> int:
    state = cg.load_state(state_path)
    view = cg.CanonicalView(state)
    experiment = view.get("experiments", experiment_id)
    if experiment is None:
        print(f"environment error: experiment not found: {experiment_id}", file=sys.stderr)
        return EXIT_ENV
    preregistration = experiment.get("preregistration")
    if not isinstance(preregistration, dict):
        print(f"environment error: {experiment_id} has no frozen preregistration",
              file=sys.stderr)
        return EXIT_ENV
    diagnostics = criterion_errors(preregistration.get("outcomes"), f"{experiment_id}.outcomes") \
        if not isinstance(preregistration.get("outcomes"), list) else []
    print(json.dumps({
        "kind": "prediction_freeze",
        "subject": experiment_id,
        "at_state_version": preregistration.get("frozen_at_state_version"),
        "freeze_digest": freeze_digest(experiment),
        "outcomes": [item.get("id") for item in preregistration.get("outcomes", [])
                     if isinstance(item, dict)],
        "criteria_present": _criterion_present(experiment),
        "diagnostics": [d.as_dict() for d in diagnostics],
    }, ensure_ascii=False, indent=2))
    return EXIT_OK if not diagnostics else EXIT_HARD


def op_compare(state_path: Path, packet_path: Optional[Path],
               for_transition: bool = False) -> int:
    state = cg.load_state(state_path)
    if packet_path is None:
        print("argument error: --packet is required", file=sys.stderr)
        return EXIT_ERROR
    if not packet_path.is_file():
        print(f"environment error: observation packet not found: {packet_path}", file=sys.stderr)
        return EXIT_ENV
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"environment error: packet is not valid JSON: {exc.msg}", file=sys.stderr)
        return EXIT_ENV
    assessment, diagnostics = assess_experiment(state, packet)
    if for_transition:
        allowed, reasons = evidence_transition_allowed(state, assessment)
        assessment["transition_allowed"] = allowed
        assessment["transition_blockers"] = reasons
        print(json.dumps(assessment, ensure_ascii=False, indent=2))
        if not allowed:
            for reason in reasons:
                print(f"PC7  {reason}", file=sys.stderr)
            return EXIT_HARD
        return EXIT_OK
    print(json.dumps(assessment, ensure_ascii=False, indent=2))
    return EXIT_OK if not diagnostics else EXIT_HARD


def op_compete(state_path: Path, cognition_dir: Path, competition_id: str) -> int:
    state = cg.load_state(state_path)
    revisions, parse_diagnostics = cg.load_revisions(cognition_dir / cg.REVISIONS_NAME)
    index, _ = cg.full_index(state, revisions, state_path.parent.name)
    competition = next((item for item in index.get("competitions", [])
                        if item.get("id") == competition_id), None)
    if competition is None:
        print(f"environment error: competition not found: {competition_id}", file=sys.stderr)
        return EXIT_ENV
    verdict, diagnostics = distinguishability(state, competition, index.get("mechanisms"))
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    for diagnostic in cg._dedupe(list(parse_diagnostics) + diagnostics):
        print(diagnostic.render(), file=sys.stderr)
    return EXIT_OK if verdict["verdict"] == "DISTINGUISHABLE" else EXIT_HARD


def op_switch(state_path: Path, cognition_dir: Path, scheduler_path: Optional[Path]) -> int:
    state = cg.load_state(state_path)
    revisions, _ = cg.load_revisions(cognition_dir / cg.REVISIONS_NAME)
    index, _ = cg.full_index(state, revisions, state_path.parent.name)
    scheduler = None
    if scheduler_path is not None:
        if not scheduler_path.is_file():
            print(f"environment error: scheduler not found: {scheduler_path}", file=sys.stderr)
            return EXIT_ENV
        scheduler = json.loads(scheduler_path.read_text(encoding="utf-8"))
    else:
        default = state_path.parent / "scheduler.json"
        if default.is_file():
            scheduler = json.loads(default.read_text(encoding="utf-8"))
    result = diagnosis_switch(state, index.get("competitions", []), scheduler,
                              index.get("mechanisms"))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return EXIT_OK


def op_insight(state_path: Path, cognition_dir: Path, card_path: Optional[Path]) -> int:
    state = cg.load_state(state_path)
    if card_path is None:
        card_path = cognition_dir / INSIGHT_CARDS_NAME
    cards, parse_diagnostics = load_cards(card_path)
    diagnostics: List[Diagnostic] = list(parse_diagnostics)
    payload = []
    for card in cards:
        diagnostics.extend(insight_card_errors(card, state))
        derived, reasons = classify_insight(card, state)
        payload.append({"id": card.get("id"), "derived_class": derived,
                        "declared_class": card.get("declared_class"), "reasons": reasons})
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    diagnostics = cg._dedupe(diagnostics)
    for diagnostic in diagnostics:
        print(diagnostic.render(), file=sys.stderr)
    hard = [d for d in diagnostics if d.rule in ("PC7", "PC8")]
    return EXIT_OK if not hard else EXIT_HARD


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _fixture() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    state = {
        "state_version": 6,
        "contract": {"goal": "判断两个机制中哪一个解释目标现象", "primary_anchor": "phenomenon",
                     "constraints": [], "resources": [],
                     "provisional_anchor_rationale": "先形式化", "out_of_scope": []},
        "claims": [{
            "id": "C1", "statement": "机制 A 解释目标现象", "parent": None, "subclaims": [],
            "status": "partially-supported", "supporting_evidence": ["E1"], "refuting_evidence": [],
            "nearest_alternative": "机制 B", "falsifier": "干预后现象消失", "scope": "数据集 A",
            "known_flaws": [], "depends_on": [],
            "validity": {"status": "valid", "reason": "已按预注册写入",
                         "since_state_version": 5},
        }],
        "evidence": [
            {"id": "E1", "kind": "experiment", "supports": ["C1"], "contradicts": [],
             "strength": "strong", "scope": "数据集 A", "epistemic_status": "Observed",
             "source_ref": "X1", "verification_tier": "T2", "depends_on": ["X1"],
             "validity": {"status": "valid", "reason": "X1 done", "since_state_version": 5}},
            {"id": "E2", "kind": "observation", "supports": [], "contradicts": [],
             "strength": "weak", "scope": "数据集 A / 中心 C", "epistemic_status": "Observed",
             "source_ref": "X1 的意外观察", "verification_tier": "T2", "depends_on": ["X1"],
             "validity": {"status": "valid", "reason": "已绑定来源", "since_state_version": 5}},
        ],
        "assumptions": [{"id": "AS1", "statement": "测量无偏", "status": "explicit",
                         "challenged_by": [], "if_false": "不可归因", "depends_on": [],
                         "validity": {"status": "valid", "reason": "仍被接受",
                                      "since_state_version": 4}}],
        "hypotheses": [{
            "id": "H1", "statement": "机制 A",
            "structural_signature": {"assumption_distance": 1, "formulation_distance": 1,
                                     "representation_distance": 0, "theory_lens_distance": 1,
                                     "mechanism_distance": 2},
            "novelty_source": "迁移", "theory_lens": "逆问题", "nearest_prior": "LIT1",
            "falsifier": "干预无效", "expected_information_gain": 0.4, "status": "elite",
            "niche": "mechanism-shift", "island": "P2", "generation": 0,
            "operator": "assumption_breaker", "parents": [], "depends_on": [],
            "validity": {"status": "valid", "reason": "未推翻", "since_state_version": 4},
            "scientific_scope": None,
        }],
        "experiments": [{
            "id": "X1", "parent": None, "stage": "X3", "claim_targeted": ["C1"],
            "alternative_targeted": ["ALT-1"], "code_commit": "abc", "data_split": "A/train",
            "seed": 0, "metric": "落差", "result": "落差 0.8", "interpretation": "初步",
            "unexpected": [], "known_flaws": [], "next_branches": [], "status": "done",
            "preregistration": {"frozen_at_state_version": 5, "outcomes": [
                {"id": "O1", "observation": "落差 ≥ 0.5",
                 "criterion": {"kind": "quantitative", "quantity": "落差（dB）",
                               "expected_range": [0.5, 3.0], "tolerance": 0.1,
                               "rule": "落差存在"},
                 "update": [{"target": "C1", "op": "strengthen"}]},
                {"id": "O2", "observation": "落差 < 0.1",
                 "criterion": {"kind": "quantitative", "quantity": "落差（dB）",
                               "expected_range": [0.0, 0.1], "tolerance": 0.1,
                               "rule": "无差异"},
                 "update": [{"target": "C1", "op": "retain-with-alternative"}]}]},
            "result_at_state_version": 6, "depends_on": [],
            "validity": {"status": "valid", "reason": "按预注册写入", "since_state_version": 6},
            "outcome_analysis": None, "execution_protocol": None,
        }, {
            "id": "X2", "parent": "X1", "stage": "X3", "claim_targeted": ["C1"],
            "alternative_targeted": ["ALT-1"], "code_commit": "TBD",
            "data_split": "A/fixed-centre ablation", "seed": 0, "metric": "落差变化（dB）",
            "result": "", "interpretation": "尚未运行", "unexpected": [], "known_flaws": [],
            "next_branches": [], "status": "planned",
            "preregistration": {"frozen_at_state_version": 5, "outcomes": [
                {"id": "O1", "observation": "解耦后落差下降 ≥ 0.5 dB",
                 "criterion": {"kind": "quantitative", "quantity": "落差变化（dB）",
                               "expected_range": [-3.0, -0.5], "tolerance": 0.1,
                               "rule": "M1 预测下降"},
                 "update": [{"target": "C1", "op": "strengthen"}]},
                {"id": "O2", "observation": "解耦后落差下降（M2 的另一种说法）",
                 "criterion": {"kind": "quantitative", "quantity": "落差变化（dB）",
                               "expected_range": [-3.0, -0.5], "tolerance": 0.1,
                               "rule": "M2 用另一种措辞预测下降，判据与 O1 完全相同"},
                 "update": [{"target": "C1", "op": "retain"}]},
                {"id": "O3", "observation": "解耦前后落差变化 < 0.1 dB",
                 "criterion": {"kind": "quantitative", "quantity": "落差变化（dB）",
                               "expected_range": [-0.1, 0.1], "tolerance": 0.1,
                               "rule": "M2 预测无变化"},
                 "update": [{"target": "C1", "op": "retain-with-alternative"}]}]},
            "result_at_state_version": None, "depends_on": ["X1"],
            "validity": {"status": "valid", "reason": "预注册已冻结，尚未运行",
                         "since_state_version": 5},
            "outcome_analysis": None, "execution_protocol": None,
        }],
        "literature": [{"id": "LIT1", "ref": "[A, V/2024]", "relation": "shares-structure",
                        "depends_on": [], "validity": {"status": "valid", "reason": "未撤回",
                                                       "since_state_version": 0}}],
        "failures": [], "uncertainties": [], "assurance": [], "repairs": [],
    }
    observation = {
        "schema": SCHEMA_OBSERVATION,
        "experiment_id": "X1",
        "execution": {"status": "completed", "validity": "VALID"},
        "outcomes": [
            {"id": "O1", "value": 0.8, "source": _source("落差 0.8 dB")},
            {"id": "O2", "value": 0.8, "source": _source("落差 0.8 dB")},
        ],
    }
    return state, observation


def _source(content: str) -> Dict[str, str]:
    import evidence_outcome as eo
    return {"kind": "result", "location": "results/A/X1/summary.json",
            "content": content, "digest": eo.digest(content)}


def selftest() -> int:
    failures = 0

    def check(name: str, condition: bool) -> None:
        nonlocal failures
        if not condition:
            failures += 1
            print(f"[FAIL] {name}")

    state, observation = _fixture()

    # -- criteria ----------------------------------------------------------
    check("valid quantitative criterion passes",
          criterion_errors({"kind": "quantitative", "quantity": "落差（dB）",
                            "expected_range": [0.5, 3.0], "tolerance": 0.1}, "p") == [])
    check("quantitative criterion needs a range",
          bool(criterion_errors({"kind": "quantitative", "quantity": "x",
                                 "tolerance": 0.1}, "p")))
    check("discrete labels must not overlap",
          bool(criterion_errors({"kind": "discrete", "quantity": "x",
                                 "held_labels": ["a"], "failed_labels": ["a"]}, "p")))
    check("unknown criterion kind is rejected",
          bool(criterion_errors({"kind": "fuzzy", "quantity": "x"}, "p")))

    # -- resolution --------------------------------------------------------
    resolved, errors = resolve_prediction(state, "X1:O1")
    check("prediction reference resolves", resolved is not None and not errors)
    check("missing outcome is reported",
          resolve_prediction(state, "X1:O9")[0] is None)
    check("malformed reference is reported",
          resolve_prediction(state, "X1")[0] is None)

    # -- comparison --------------------------------------------------------
    verdict, detail = compare_outcome(resolved["criterion"], {"value": 0.8})
    check("value inside range holds", verdict == "PREDICTION_HELD")
    verdict, _ = compare_outcome(resolved["criterion"], {"value": 0.45})
    check("value just outside range is within tolerance", verdict == "WITHIN_TOLERANCE")
    verdict, _ = compare_outcome(resolved["criterion"], {"value": 0.1})
    check("value far outside range deviates", verdict == "PREDICTION_DEVIATED")
    verdict, _ = compare_outcome(resolved["criterion"], {})
    check("missing measurement is untestable", verdict == "UNTESTABLE")
    verdict, _ = compare_outcome(
        {"kind": "directional", "quantity": "x", "direction": "decrease", "tolerance": 0.0},
        {"direction": "increase"})
    check("direction mismatch deviates", verdict == "PREDICTION_DEVIATED")
    verdict, _ = compare_outcome(
        {"kind": "discrete", "quantity": "x", "held_labels": ["yes"], "failed_labels": ["no"]},
        {"label": "maybe"})
    check("unregistered label is untestable", verdict == "UNTESTABLE")

    # -- experiment assessment --------------------------------------------
    assessment, diagnostics = assess_experiment(state, observation)
    check("divergent outcome deviates the experiment",
          assessment["outcome_class"] == "PREDICTION_DEVIATED")
    check("deviation raises a diagnostic", any(d.rule == "PC6" for d in diagnostics))
    check("the frozen set defines the decision set",
          assessment["frozen_outcome_ids"] == ["O1", "O2"])

    # P0-1: submitting only the favourable outcome must not read as "all held".
    partial_packet = json.loads(json.dumps(observation))
    partial_packet["outcomes"] = [{"id": "O1", "value": 0.8, "source": _source("落差 0.8 dB")}]
    partial, partial_diagnostics = assess_experiment(state, partial_packet)
    check("a partial submission is PARTIALLY_ASSESSED, not HELD",
          partial["outcome_class"] == "PARTIALLY_ASSESSED")
    missing = next(entry for entry in partial["predictions"] if entry["outcome_id"] == "O2")
    check("the missing frozen outcome is named",
          missing["verdict"] == "UNTESTABLE" and missing["reason"] == "missing_observation")
    check("the incomplete assessment cannot inform a transition",
          partial["evidence_eligible"] is False
          and not evidence_transition_allowed(state, partial)[0])
    check("selective submission is reported",
          any(d.rule == "PC8" for d in partial_diagnostics))

    full_held = json.loads(json.dumps(observation))
    full_held["outcomes"] = [
        {"id": "O1", "value": 0.8, "source": _source("落差 0.8 dB")},
        {"id": "O2", "value": 0.05, "source": _source("落差 0.05 dB")},
    ]
    held, _ = assess_experiment(state, full_held)
    check("only a complete held submission reads as HELD",
          held["outcome_class"] == "PREDICTION_HELD")
    check("a complete and consistent submission is qualified evidence",
          held["evidence_eligible"] is True
          and held["scientific_status"] == "MAY_INFORM_TRANSITION")

    # duplicate and extra outcomes cannot enter the decision set
    duplicated = json.loads(json.dumps(observation))
    duplicated["outcomes"] = [observation["outcomes"][0], observation["outcomes"][0],
                              observation["outcomes"][1]]
    dup, dup_diagnostics = assess_experiment(state, duplicated)
    check("a duplicated outcome is undecidable",
          next(e for e in dup["predictions"] if e["outcome_id"] == "O1")["reason"]
          == "duplicate_observation")
    check("a duplicate is reported", any(d.rule == "PC2" for d in dup_diagnostics))
    extra = json.loads(json.dumps(observation))
    extra["outcomes"] = observation["outcomes"] + [
        {"id": "O9", "value": 1.0, "source": _source("未冻结")}]
    with_extra, extra_diagnostics = assess_experiment(state, extra)
    check("an unfrozen outcome is excluded from the verdict set",
          with_extra["unexpected_observations"] == ["O9"]
          and all(e["outcome_id"] != "O9" for e in with_extra["predictions"]))
    check("an unexpected observation blocks qualification",
          with_extra["evidence_eligible"] is False
          and any(d.rule == "PC2" for d in extra_diagnostics))

    # branch mode: mutually exclusive branches of one decision
    branch = json.loads(json.dumps(observation))
    branch["observed_outcome"] = "O1"
    branch["outcomes"] = [branch["outcomes"][0]]
    branch_assessment, _ = assess_experiment(state, branch)
    check("branch mode adjudicates only the selected branch",
          branch_assessment["outcome_class"] == "PREDICTION_HELD"
          and branch_assessment["mode"] == "branch"
          and branch_assessment["not_selected"] == ["O2"])
    ambiguous = json.loads(json.dumps(observation))
    ambiguous["observed_outcome"] = "O1"
    ambiguous["outcomes"] = [
        {"id": "O1", "value": 0.8, "source": _source("a")},
        {"id": "O2", "value": 0.05, "source": _source("b")},
    ]
    ambiguous_assessment, ambiguous_diagnostics = assess_experiment(state, ambiguous)
    check("two satisfied branches make the freeze undecidable",
          ambiguous_assessment["outcome_class"] == "UNTESTABLE"
          and any(d.rule == "PC8" for d in ambiguous_diagnostics))

    bad_packet = json.loads(json.dumps(observation))
    bad_packet["execution"]["validity"] = "INVALID"
    invalid, invalid_diagnostics = assess_experiment(state, bad_packet)
    check("invalid execution never becomes a prediction verdict",
          invalid["outcome_class"] == "INVALID_EXECUTION")
    check("invalid execution is reported for R9.O",
          any(d.rule == "PC6" for d in invalid_diagnostics))
    check("invalid execution may not inform a transition",
          invalid["evidence_eligible"] is False
          and not evidence_transition_allowed(state, invalid)[0])

    unknown_packet = json.loads(json.dumps(observation))
    unknown_packet["execution"]["validity"] = "UNKNOWN"
    unknown, unknown_diagnostics = assess_experiment(state, unknown_packet)
    check("UNKNOWN keeps the diagnostic comparison",
          unknown["diagnostic_outcome_class"] == "PREDICTION_DEVIATED")
    check("UNKNOWN cannot occupy the scientific verdict slot with a world claim",
          unknown["outcome_class"] == "UNTESTABLE"
          and unknown["outcome_class_downgraded_from"] == "PREDICTION_DEVIATED")
    check("UNKNOWN is not qualified evidence",
          unknown["evidence_eligible"] is False
          and unknown["evidence_class"] == "DIAGNOSTIC_ONLY"
          and unknown["scientific_status"] == "DIAGNOSTIC_ONLY")
    check("UNKNOWN is reported as an evidence-eligibility violation",
          any(d.rule == "PC7" for d in unknown_diagnostics))
    allowed, blockers = evidence_transition_allowed(state, unknown)
    check("UNKNOWN cannot support, refute or upgrade", allowed is False and blockers)

    # an unfinished experiment produces a diagnostic comparison only
    unfinished = json.loads(json.dumps(state))
    unfinished["experiments"][0]["status"] = "running"
    unfinished["experiments"][0]["result_at_state_version"] = None
    unfinished_assessment, unfinished_diagnostics = assess_experiment(unfinished, observation)
    check("incomplete provenance is diagnostic only",
          unfinished_assessment["evidence_eligible"] is False
          and unfinished_assessment["provenance_gaps"])
    check("incomplete provenance is reported",
          any(d.rule == "PC7" for d in unfinished_diagnostics))

    exploratory = json.loads(json.dumps(observation))
    exploratory_state = json.loads(json.dumps(state))
    exploratory_state["experiments"][0]["preregistration"] = None
    exploratory_state["experiments"][0]["status"] = "planned"
    exploratory_state["experiments"][0]["result_at_state_version"] = None
    discovered, exploratory_diagnostics = assess_experiment(exploratory_state, exploratory)
    check("no preregistration means exploratory only",
          discovered["outcome_class"] == "EXPLORATORY_ANOMALY")
    check("exploratory observation cannot claim success or failure",
          any("探索性异常" in d.detail for d in exploratory_diagnostics))

    legacy = json.loads(json.dumps(state))
    del legacy["experiments"][0]["preregistration"]["outcomes"][0]["criterion"]
    legacy_assessment, legacy_diagnostics = assess_experiment(legacy, observation)
    check("legacy outcome without a criterion is untestable",
          legacy_assessment["predictions"][0]["verdict"] == "UNTESTABLE")
    check("legacy outcome raises PC1",
          any(d.rule == "PC1" for d in legacy_diagnostics))

    # -- source binding ----------------------------------------------------
    unbound = json.loads(json.dumps(observation))
    unbound["outcomes"][0]["source"]["digest"] = "sha256:deadbeef"
    _, unbound_diagnostics = assess_experiment(state, unbound)
    check("unbound source is rejected", any(d.rule == "PC2" for d in unbound_diagnostics))

    # -- freeze integrity --------------------------------------------------
    freeze_event = {
        "_schema": cg.SCHEMA_REVISION, "id": "REV1", "seq": 1, "kind": "prediction_freeze",
        "subject": "X1", "actor": "R8", "at_state_version": 5, "summary": "freeze X1",
        "trigger": {"kind": "preregistration_frozen", "ref": "X1"},
        "refs": {"experiments": ["X1"], "claims": ["C1"]},
        "after": {"freeze_digest": freeze_digest(state["experiments"][0])},
    }
    check("clean freeze passes", check_freezes(state, [freeze_event]) == [])

    tampered = json.loads(json.dumps(state))
    tampered["experiments"][0]["preregistration"]["outcomes"][0]["criterion"]["expected_range"] = [0.9, 3.0]
    tamper_diagnostics = check_freezes(tampered, [freeze_event])
    check("silent rewrite of a frozen criterion is detected",
          any(d.rule == "PC4" for d in tamper_diagnostics))

    amended = json.loads(json.dumps(tampered))
    amended["experiments"][0]["preregistration"]["amended"] = [
        {"at_state_version": 5, "reason": "判据口径写错，结果产生前修正"}]
    amended_diagnostics = check_freezes(amended, [freeze_event])
    check("recorded amendment before the result is not tampering",
          not any(d.rule == "PC4" for d in amended_diagnostics))

    post_hoc = json.loads(json.dumps(tampered))
    post_hoc["experiments"][0]["preregistration"]["amended"] = [
        {"at_state_version": 6, "reason": "看到结果后调整口径"}]
    post_hoc_diagnostics = check_freezes(post_hoc, [freeze_event])
    check("amendment after the result is post-hoc tampering",
          any(d.rule == "PC4" and "事后修订无效" in d.detail for d in post_hoc_diagnostics))

    late = json.loads(json.dumps(freeze_event))
    late["at_state_version"] = 6
    check("late freeze registration is reported",
          any(d.rule == "PC5" for d in check_freezes(state, [late])))

    # -- competition -------------------------------------------------------
    mechanisms = [
        {"id": "M1", "structure": {"pending_predictions": ["X2:O1"]}},
        {"id": "M2", "structure": {"pending_predictions": ["X2:O3"]}},
    ]
    rule = {"statistic": "difference_of_means", "min_separation": 0.2}
    competition = {
        "id": "CP1", "status": "open", "mechanisms": ["M1", "M2"],
        "conflicting_predictions": ["X2:O1", "X2:O3"],
        "predictions": [{"mechanism": "M1", "ref": "X2:O1"},
                        {"mechanism": "M2", "ref": "X2:O3"}],
        "discriminating_intervention": "X2", "decision_impact": "method_decision_differs",
        "discrimination_rule": rule,
    }
    verdict, _ = distinguishability(state, competition, mechanisms)
    check("a conflicting pair with a declared rule and an actionable design is distinguishable",
          verdict["verdict"] == "DISTINGUISHABLE", )
    check("the separating pair is reported as a witness",
          verdict.get("witness_pair", {}).get("left_ref") == "X2:O1")

    without_rule = dict(competition, discrimination_rule=None)
    verdict, _ = distinguishability(state, without_rule, mechanisms)
    check("conflict without a pre-declared rule is only conditional",
          verdict["verdict"] == "CONDITIONALLY_DISTINGUISHABLE"
          and verdict["reason"] == "no_discrimination_rule")

    no_gap = dict(competition, conflicting_predictions=[], predictions=[])
    verdict, _ = distinguishability(state, no_gap, mechanisms)
    check("no prediction gap is insufficient information",
          verdict["verdict"] == "INSUFFICIENT_INFORMATION"
          and verdict["reason"] == "no_prediction_gap")

    no_intervention = dict(competition, discriminating_intervention="TBD")
    verdict, _ = distinguishability(state, no_intervention, mechanisms)
    check("a missing intervention is insufficient information",
          verdict["verdict"] == "INSUFFICIENT_INFORMATION"
          and verdict["reason"] == "no_intervention")

    # O2 is the same criterion as O1 with different wording: a rewording is not a
    # competing prediction, and no amount of extra samples makes it one.
    equivalent = dict(competition,
                      conflicting_predictions=["X2:O1", "X2:O2"],
                      predictions=[{"mechanism": "M1", "ref": "X2:O1"},
                                   {"mechanism": "M2", "ref": "X2:O2"}])
    verdict, _ = distinguishability(state, equivalent, mechanisms)
    check("a reworded identical criterion has no distinguishing power",
          verdict["verdict"] == "NOT_DISTINGUISHABLE"
          and verdict["reason"] == "identical_criteria")

    unowned = {"id": "CP8", "status": "open", "mechanisms": ["M1", "M2"],
               "conflicting_predictions": ["X2:O1", "X2:O3"],
               "discriminating_intervention": "X2"}
    verdict, unowned_diagnostics = distinguishability(state, unowned, None)
    check("predictions that cannot be attributed to a mechanism are insufficient",
          verdict["verdict"] == "INSUFFICIENT_INFORMATION"
          and verdict["reason"] == "no_ownership")
    check("unattributed predictions are reported",
          any("归属" in d.detail for d in unowned_diagnostics))

    structure_only = {"id": "CP9", "status": "open", "mechanisms": ["M1"],
                      "conflicting_predictions": ["X2:O1", "X2:O3"],
                      "discriminating_intervention": "X2"}
    verdict, _ = distinguishability(state, structure_only, mechanisms)
    check("a single mechanism is insufficient",
          verdict["verdict"] == "INSUFFICIENT_INFORMATION"
          and verdict["reason"] == "insufficient_mechanisms")

    # --- P0-3: different metrics are not a competition ---------------------
    different_metric_state = json.loads(json.dumps(state))
    different_metric_state["experiments"][1]["preregistration"]["outcomes"][2]["criterion"][
        "quantity"] = "完全不同的指标（ms）"
    verdict, _ = distinguishability(different_metric_state, competition, mechanisms)
    check("two mechanisms measuring different observables are not distinguishable",
          verdict["verdict"] == "INSUFFICIENT_INFORMATION"
          and verdict["reason"] == "different_observables")

    # --- P0-3: partially overlapping intervals ----------------------------
    overlap_state = json.loads(json.dumps(state))
    overlap_state["experiments"][1]["preregistration"]["outcomes"][2]["criterion"][
        "expected_range"] = [-0.6, 0.4]
    verdict, _ = distinguishability(overlap_state, competition, mechanisms)
    check("partially overlapping intervals cannot separate the mechanisms",
          verdict["verdict"] == "NOT_DISTINGUISHABLE"
          and verdict["reason"] == "overlapping_intervals")

    # --- P0-3: statistical uncertainty swallows the gap -------------------
    noisy_state = json.loads(json.dumps(state))
    noisy_state["experiments"][1]["preregistration"]["outcomes"][0]["criterion"].update(
        {"noise": 4.0, "sample_size": 4})
    verdict, _ = distinguishability(noisy_state, competition, mechanisms)
    check("an underpowered design cannot separate the mechanisms",
          verdict["verdict"] == "NOT_DISTINGUISHABLE"
          and verdict["reason"] == "within_uncertainty")

    # --- P0-3: the declared resolution must be met ------------------------
    strict_rule = {"statistic": "difference_of_means", "min_separation": 0.9}
    verdict, _ = distinguishability(
        state, dict(competition, discrimination_rule=strict_rule), mechanisms)
    check("a gap below the declared resolution is not distinguishable",
          verdict["verdict"] == "NOT_DISTINGUISHABLE"
          and verdict["reason"] == "below_declared_min_separation")

    # --- P0-3: measurement basis mismatch ---------------------------------
    basis_state = json.loads(json.dumps(state))
    basis_state["experiments"][1]["preregistration"]["outcomes"][0]["criterion"][
        "measurement"] = "single centre"
    basis_state["experiments"][1]["preregistration"]["outcomes"][2]["criterion"][
        "measurement"] = "mean over centres"
    verdict, _ = distinguishability(basis_state, competition, mechanisms)
    check("different measurement bases are not comparable",
          verdict["verdict"] == "INSUFFICIENT_INFORMATION"
          and verdict["reason"] == "different_measurement")

    # --- P0-3: a finished experiment is not an actionable intervention ----
    stale_intervention = json.loads(json.dumps(state))
    stale_intervention["experiments"][1]["status"] = "done"
    verdict, _ = distinguishability(stale_intervention, competition, mechanisms)
    check("an experiment that already ran is not an actionable intervention",
          verdict["verdict"] == "INSUFFICIENT_INFORMATION"
          and verdict["reason"] == "intervention_not_actionable")

    # --- P0-3: prose and self-rating must not change the verdict ----------
    verbose = dict(competition,
                   note="两个机制在语义上高度相似",
                   similarity=0.91, confidence=0.99,
                   predictions=[{"mechanism": "M1", "ref": "X2:O1", "note": "看起来一样"},
                                {"mechanism": "M2", "ref": "X2:O3", "note": "完全不同"}])
    verdict, _ = distinguishability(state, verbose, mechanisms)
    check("free text and self-ratings do not decide distinguishability",
          verdict["verdict"] == "DISTINGUISHABLE")

    # --- P0-3: with three mechanisms every pair must separate -------------
    three = {"id": "CP3", "status": "open", "mechanisms": ["M1", "M2", "M3"],
             "conflicting_predictions": ["X2:O1", "X2:O3", "X2:O2"],
             "predictions": [{"mechanism": "M1", "ref": "X2:O1"},
                             {"mechanism": "M2", "ref": "X2:O3"},
                             {"mechanism": "M3", "ref": "X2:O2"}],
             "discriminating_intervention": "X2",
             "decision_impact": "method_decision_differs",
             "discrimination_rule": rule}
    verdict, _ = distinguishability(state, three, [
        {"id": "M1", "structure": {"pending_predictions": ["X2:O1"]}},
        {"id": "M2", "structure": {"pending_predictions": ["X2:O3"]}},
        {"id": "M3", "structure": {"pending_predictions": ["X2:O2"]}}])
    check("three mechanisms need every pair separated",
          verdict["verdict"] == "NOT_DISTINGUISHABLE"
          and verdict["reason"] == "identical_criteria"
          and verdict["witness_pair"]["left"] in ("M1", "M2"))

    # -- switch ------------------------------------------------------------
    idle = {"eig_calibration": {"records": [
        {"experiment": "X0", "actual_information_gain": "zero", "predicted_information_gain": "low",
         "observed_delta": {"claim_status_changes": [], "uncertainty_changes": [],
                            "hypothesis_status_changes": [], "new_uncertainties": [],
                            "unexpected_observations": 0}},
        {"experiment": "X1", "actual_information_gain": "zero", "predicted_information_gain": "low",
         "observed_delta": {"claim_status_changes": [], "uncertainty_changes": [],
                            "hypothesis_status_changes": [], "new_uncertainties": [],
                            "unexpected_observations": 0}}]}}
    switch = diagnosis_switch(state, [no_intervention], idle, mechanisms)
    check("repeated empty diagnosis asks for a discriminating intervention",
          switch["action"] == "FIND_DISCRIMINATING_INTERVENTION")
    check("independent exploration is never blocked globally",
          switch["independent_exploration_allowed"] is True)

    switch = diagnosis_switch(state, [equivalent], idle, mechanisms)
    check("indistinguishable mechanisms stop costing experiments",
          switch["action"] in ("RECORD_BOUNDARY_AND_STOP", "REDESIGN_QUESTION"))
    same = dict(equivalent, decision_impact="same_method_decision")
    switch = diagnosis_switch(state, [same], idle, mechanisms)
    check("indistinguishable and decision-irrelevant is recorded and stopped",
          switch["action"] == "RECORD_BOUNDARY_AND_STOP")

    switch = diagnosis_switch(state, [no_gap], None, mechanisms)
    check("no gap asks for a minimal intervention",
          switch["action"] == "FIND_DISCRIMINATING_INTERVENTION")
    switch = diagnosis_switch(state, [], None, mechanisms)
    check("a healthy project continues attribution",
          switch["action"] == "CONTINUE_ATTRIBUTION")

    # -- insight cards -----------------------------------------------------
    card = {
        "_schema": SCHEMA_INSIGHT, "id": "IC1", "at_state_version": 6, "actor": "R6",
        "observation": "中心 C 上方向反转", "existing_mechanism": "M1",
        "challenged_assumption": "AS1", "proposed_mechanism": "M2",
        "explanatory_gain": "解释反向观察", "competing_mechanism": "M1",
        "novel_prediction": {"ref": "X2:O1", "statement": "解耦后落差下降 ≥ 0.5 dB"},
        "discriminating_intervention": "X2", "scope_boundary": "数据集 A",
        "scientific_implication": "需要分中心建模",
        "refs": {"claims": ["C1"], "hypotheses": ["H1"]},
        "declared_class": "predictive_insight_candidate",
    }
    check("a well-formed predictive card validates", insight_card_errors(card, state) == [])
    derived, _ = classify_insight(card, state)
    check("predictive card derives the predictive class",
          derived == "predictive_insight_candidate")

    explanatory = dict(card, novel_prediction={}, declared_class="explanatory_hypothesis")
    errors = insight_card_errors(explanatory, state)
    check("a card without a prediction cannot be a predictive candidate",
          any(d.rule == "PC8" for d in errors))

    supported = dict(card, id="IC2",
                     novel_prediction={"ref": "X1:O1", "statement": "落差 ≥ 0.5 dB"},
                     discriminating_intervention="X1",
                     refs={"claims": ["C1"], "evidence": ["E1"], "hypotheses": ["H1"]},
                     declared_class="evidence_supported_insight")
    errors = insight_card_errors(supported, state)
    check("self-certified evidence support is a hard violation",
          any(d.rule == "PC7" for d in errors))

    audited_state = json.loads(json.dumps(state))
    audited_state["assurance"] = [{"id": "A1", "target": "C1",
                                   "attack_type": "structural-equivalence",
                                   "verification_tier": "T1",
                                   "kill_condition": "若与 LIT1 结构等价则杀死",
                                   "discriminating_test": "X1"}]
    derived, reasons = classify_insight(supported, audited_state)
    check("evidence plus an independent audit derives evidence support",
          derived == "evidence_supported_insight", )
    errors = insight_card_errors(supported, audited_state)
    check("a supported card after the audit validates",
          [d for d in errors if d.rule in ("PC7",)] == [])

    unscoped = json.loads(json.dumps(audited_state))
    unscoped["evidence"][0]["scope"] = "数据集 Z"
    derived, _ = classify_insight(supported, unscoped)
    check("evidence outside the claimed boundary cannot support the card",
          derived == "predictive_insight_candidate")

    unbound = json.loads(json.dumps(audited_state))
    unbound["evidence"][0]["depends_on"] = []
    derived, _ = classify_insight(supported, unbound)
    check("evidence not bound to the prediction's experiment cannot support the card",
          derived != "evidence_supported_insight")

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
    parser = _Parser(description="Prediction, anomaly, competition and insight checks")
    parser.add_argument("command", nargs="?",
                        choices=["freeze", "compare", "compete", "switch", "insight"])
    parser.add_argument("--state", help="path to research-state.json")
    parser.add_argument("--cognition", help="path to the cognition directory")
    parser.add_argument("--experiment", help="experiment id for freeze")
    parser.add_argument("--packet", help="observation packet for compare")
    parser.add_argument("--competition", help="competition id for compete")
    parser.add_argument("--scheduler", help="path to scheduler.json")
    parser.add_argument("--card", help="path to an insight card or card log")
    parser.add_argument("--for-transition", action="store_true",
                        help="compare: fail unless the result may inform a state transition")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--list-classes", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.selftest:
        return selftest()
    if args.list_classes:
        for name in OUTCOME_CLASSES:
            print(name)
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
    try:
        if args.command == "freeze":
            if not args.experiment:
                print("argument error: --experiment is required", file=sys.stderr)
                return EXIT_ERROR
            return op_freeze(state_path, args.experiment)
        if args.command == "compare":
            return op_compare(state_path,
                              Path(args.packet).expanduser() if args.packet else None,
                              args.for_transition)
        if args.command == "compete":
            if not args.competition:
                print("argument error: --competition is required", file=sys.stderr)
                return EXIT_ERROR
            return op_compete(state_path, cognition_dir, args.competition)
        if args.command == "switch":
            return op_switch(state_path, cognition_dir,
                             Path(args.scheduler).expanduser() if args.scheduler else None)
        if args.command == "insight":
            return op_insight(state_path, cognition_dir,
                              Path(args.card).expanduser() if args.card else None)
    except cg.CognitionError as exc:
        print(f"environment error: {exc}", file=sys.stderr)
        return EXIT_ENV
    print(f"argument error: unknown command {args.command!r}", file=sys.stderr)
    return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
