#!/usr/bin/env python3
"""decision_trajectory.py — append-only Research Decision Trajectory (Skill-RSI Phase 2).

Why this module exists
----------------------
The scheduler already records strategy decisions, but only as a **bounded ring** of
telemetry (`scheduler.strategy_decisions[]`, `DECISION_LOG_LIMIT = 20`). That ring is
system statistics: it has no Context / Prediction / Outcome / Learning binding, no
source verification and no ordering guarantees. Long-horizon policy learning cannot
be built on it without corrupting its meaning.

This module adds a **second, append-only control-plane record** beside the existing
one instead of overwriting it:

    <route>/decision-trajectory.jsonl

Every line is one immutable record. A trajectory is identified by a deterministic id
so that re-submitting the same decision is idempotent, and a hash chain makes an
in-place rewrite of an earlier line detectable.

Hard boundaries
---------------
* Nothing here writes canonical `research-state.json`. A trajectory is *not* scientific
  evidence and must never be copied into `evidence[]` (checked by `DT7`).
* A prediction cannot be added after an outcome exists (`DT5`), and an outcome cannot
  be bound to a state older than its decision (`DT4`). Later results never rewrite an
  earlier decision: a differing payload for an existing trajectory id is rejected (`DT2`).
* Unobserved historical branches keep the status they had. This module stores what was
  actually chosen and actually observed; it does not manufacture outcomes.

Expected record keys are documented in `references/skill-rsi-policy.md`.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import cognition as cg

SCHEMA_TRAJECTORY = "research-idea-pipeline/decision-trajectory@1"

EXIT_OK = cg.EXIT_OK
EXIT_ERROR = cg.EXIT_ERROR
EXIT_HARD = cg.EXIT_HARD
EXIT_ENV = cg.EXIT_ENV

TRAJECTORY_NAME = "decision-trajectory.jsonl"
TRAJECTORY_LOCK = ".decision-trajectory.lock"
TRAJECTORY_HEAD_SUFFIX = ".head"

RECORD_KINDS: Tuple[str, ...] = ("decision", "prediction", "outcome", "learning")

#: A decision may only report these dispatch states. "not_dispatched" is a first-class
#: value: an action that was chosen but never dispatched is recorded as such instead of
#: being rounded up to "happened".
DISPATCH_STATUSES: Tuple[str, ...] = ("not_dispatched", "dispatched", "blocked")
EVIDENCE_QUALIFICATIONS: Tuple[str, ...] = ("qualified", "unqualified", "unknown")

#: Delta vocabulary shared with the preset output contract. "none" is required to be
#: expressible — logging, projection refresh and self-assessment are not deltas.
DELTA_VALUES: Tuple[str, ...] = ("none", "scientific", "decision", "policy")

#: Keys that must never appear in a decision's context section: they name *later*
#: information, and accepting them would silently admit a future observation.
LEAK_KEYS: Tuple[str, ...] = (
    "outcome", "outcomes", "later_results", "final_result", "post_hoc", "result_after",
)

_SCALAR = (str, int, float, bool)


# ---------------------------------------------------------------------------
# Diagnostics (same shape as cognition.Diagnostic so renderers stay uniform)
# ---------------------------------------------------------------------------

class TrajectoryError(Exception):
    """A trajectory operation that cannot proceed (tamper, conflict, missing file)."""


def _diag(rule: str, path: str, message: str) -> cg.Diagnostic:
    return cg.Diagnostic(rule, path, message)


def _dedupe(diagnostics: Iterable[cg.Diagnostic]) -> List[cg.Diagnostic]:
    return cg._dedupe(diagnostics)


# ---------------------------------------------------------------------------
# Paths and canonical digests
# ---------------------------------------------------------------------------

def trajectory_path(state_path: Path) -> Path:
    """`<route>/decision-trajectory.jsonl`, beside the canonical state."""
    return Path(state_path).resolve().parent / TRAJECTORY_NAME


def trajectory_path_for_dir(route_dir: Path) -> Path:
    return Path(route_dir).resolve() / TRAJECTORY_NAME


def head_path(path: Path) -> Path:
    """Sidecar holding the digest of the last line, so a rewritten tail is detectable.

    The hash chain alone protects every line *except* the most recent one; a head file
    mirrors `experiment_execute.Ledger` and closes that gap.
    """
    return Path(path).parent / (TRAJECTORY_NAME + TRAJECTORY_HEAD_SUFFIX)


def _digest(value: Any) -> str:
    return cg.digest_of(value)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


# ---------------------------------------------------------------------------
# Store I/O: append-only, hash-chained, locked
# ---------------------------------------------------------------------------

def load_records(path: Path, *, tolerant: bool = False) -> Tuple[List[Dict[str, Any]], List[cg.Diagnostic]]:
    """Read the trajectory, verifying the hash chain.

    A broken chain raises `TrajectoryError` unless `tolerant` is set, in which case the
    diagnostics are returned for reporting. A truncated tail (a partial JSON line) is
    always an error: silently dropping it would make an append-only log look shorter.
    """
    path = Path(path)
    diagnostics: List[cg.Diagnostic] = []
    if not path.exists():
        return [], diagnostics
    records: List[Dict[str, Any]] = []
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            diagnostics.append(_diag("DT0", f"{TRAJECTORY_NAME}:{index + 1}",
                                     f"轨迹行不是合法 JSON（拒绝截断/损坏的日志）：{exc.msg}"))
            if not tolerant:
                raise TrajectoryError(diagnostics[-1].render()) from exc
            continue
        if not isinstance(record, dict):
            diagnostics.append(_diag("DT0", f"{TRAJECTORY_NAME}:{index + 1}", "轨迹行必须是对象"))
            if not tolerant:
                raise TrajectoryError(diagnostics[-1].render())
            continue
        expected_previous = _digest(records[-1]) if records else None
        if record.get("previous") != expected_previous:
            diagnostics.append(_diag("DT0", f"{TRAJECTORY_NAME}:{index + 1}",
                                     "轨迹哈希链断裂：历史行被改写或被删除"))
            if not tolerant:
                raise TrajectoryError(diagnostics[-1].render())
        if record.get("seq") != index + 1:
            diagnostics.append(_diag("DT0", f"{TRAJECTORY_NAME}:{index + 1}",
                                     f"seq 不连续：期望 {index + 1}，实际 {record.get('seq')!r}"))
            if not tolerant:
                raise TrajectoryError(diagnostics[-1].render())
        records.append(record)
    if diagnostics and not tolerant:
        raise TrajectoryError(diagnostics[0].render())
    head = head_path(path)
    expected_head = _digest(records[-1]) if records else None
    if head.exists():
        actual_head = head.read_text(encoding="ascii").strip()
        if actual_head != expected_head:
            diagnostics.append(_diag("DT0", str(head),
                                     "轨迹尾部摘要与 head 不一致：最后一行被改写或历史被截断"))
            if not tolerant:
                raise TrajectoryError(diagnostics[-1].render())
    elif records:
        diagnostics.append(_diag("DT0", str(head), "轨迹有记录但缺少 head 摘要文件"))
        if not tolerant:
            raise TrajectoryError(diagnostics[-1].render())
    return records, diagnostics


def _append_line(path: Path, record: Dict[str, Any]) -> None:
    """Durably append one line while holding an exclusive lock on the store."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / TRAJECTORY_LOCK
    with lock_path.open("a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(record, ensure_ascii=False, sort_keys=True,
                                 allow_nan=False) + "\n")
            out.flush()
            os.fsync(out.fileno())
        pending = head_path(path).with_name(head_path(path).name + ".pending")
        with pending.open("w", encoding="ascii") as out:
            out.write(_digest(record))
            out.flush()
            os.fsync(out.fileno())
        os.replace(pending, head_path(path))


# ---------------------------------------------------------------------------
# Record construction
# ---------------------------------------------------------------------------

def trajectory_id(project: str, route: str, state_version: Any, chosen: Any,
                  context_digest: str) -> str:
    """Deterministic id: the same decision submitted twice maps to the same trajectory."""
    return "DT-" + _digest({"project": project, "route": route, "state_version": state_version,
                            "chosen": chosen, "context": context_digest})[:20]


def context_digest(context: Dict[str, Any]) -> str:
    """Digest of the frozen context. `state_version` alone is not information visibility."""
    return _digest(context)


def build_context(state: Dict[str, Any], *, scientific_question: str,
                  active_hypotheses: Sequence[str] = (), key_uncertainties: Sequence[str] = (),
                  visible_evidence: Sequence[str] = (), stop_rules: Sequence[str] = (),
                  decided_at: Optional[str] = None,
                  scheduler: Optional[Dict[str, Any]] = None,
                  cognition_digest: Optional[str] = None) -> Dict[str, Any]:
    """Freeze everything that was visible when the decision was made."""
    contract = state.get("contract") if isinstance(state.get("contract"), dict) else {}
    return {
        "state_version": state.get("state_version"),
        "contract_ref": {"goal": contract.get("goal"),
                         "primary_anchor": contract.get("primary_anchor")},
        "scientific_question": scientific_question,
        "active_hypotheses": sorted(str(item) for item in active_hypotheses),
        "key_uncertainties": sorted(str(item) for item in key_uncertainties),
        "visible_evidence": sorted(str(item) for item in visible_evidence),
        "stop_rules": [str(item) for item in stop_rules],
        "decided_at": decided_at or _now(),
        "state_digest": _digest(state),
        "scheduler_digest": _digest(scheduler) if scheduler is not None else None,
        "cognition_digest": cognition_digest,
    }


def build_decision_record(state: Dict[str, Any], *, route: str, project: str,
                          context: Dict[str, Any], candidates: Sequence[Dict[str, Any]],
                          chosen: Optional[str], scheduler_priority: Dict[str, Any],
                          policy_version: str = "none", policy_changed_order: bool = False,
                          dispatch_status: str = "not_dispatched",
                          dispatch_ref: Optional[str] = None,
                          prediction: Optional[Dict[str, Any]] = None,
                          recorded_at: Optional[str] = None) -> Dict[str, Any]:
    """Build an unsigned `decision` record (validation happens in `append_record`)."""
    ident = trajectory_id(project, route, context.get("state_version"), chosen,
                          context_digest(context))
    record: Dict[str, Any] = {
        "_schema": SCHEMA_TRAJECTORY,
        "record": "decision",
        "trajectory_id": ident,
        "recorded_at": recorded_at or _now(),
        "project": project,
        "route": route,
        "context": context,
        "decision": {
            "candidates": [copy.deepcopy(dict(item)) for item in candidates],
            "scheduler_priority": copy.deepcopy(dict(scheduler_priority)),
            "chosen": chosen,
            "policy_version": policy_version,
            "policy_changed_order": bool(policy_changed_order),
            "dispatch_status": dispatch_status,
            "dispatch_ref": dispatch_ref,
        },
        "prediction": copy.deepcopy(prediction) if prediction else None,
        "canonical_untouched": True,
    }
    return record


def build_outcome_record(trajectory: str, *, at_state_version: Any, result: Dict[str, Any],
                         evidence_refs: Sequence[Dict[str, str]] = (),
                         scientific_delta: str = "none", decision_delta: str = "none",
                         policy_delta: str = "none", policy_effect_observed: bool = False,
                         cost: Optional[Dict[str, Any]] = None,
                         open_questions: Sequence[str] = (),
                         evidence_qualification: str = "unknown",
                         observed_at: Optional[str] = None,
                         route: str = "", project: str = "") -> Dict[str, Any]:
    return {
        "_schema": SCHEMA_TRAJECTORY,
        "record": "outcome",
        "trajectory_id": trajectory,
        "recorded_at": observed_at or _now(),
        "observed_at": observed_at or _now(),
        "project": project,
        "route": route,
        "at_state_version": at_state_version,
        "result": copy.deepcopy(dict(result)),
        "evidence_refs": [copy.deepcopy(dict(item)) for item in evidence_refs],
        "scientific_delta": scientific_delta,
        "decision_delta": decision_delta,
        "policy_delta": policy_delta,
        "policy_effect_observed": bool(policy_effect_observed),
        "cost": copy.deepcopy(dict(cost)) if cost else {},
        "open_questions": [str(item) for item in open_questions],
        "evidence_qualification": evidence_qualification,
    }


def build_learning_record(trajectory: str, *, learning_value: bool, bias_hypothesis: str = "",
                          applicability: Optional[Dict[str, Any]] = None,
                          counterexamples: Sequence[str] = (),
                          needs_validation: bool = True,
                          recorded_at: Optional[str] = None,
                          route: str = "", project: str = "") -> Dict[str, Any]:
    return {
        "_schema": SCHEMA_TRAJECTORY,
        "record": "learning",
        "trajectory_id": trajectory,
        "recorded_at": recorded_at or _now(),
        "project": project,
        "route": route,
        "learning_value": bool(learning_value),
        "bias_hypothesis": bias_hypothesis,
        "applicability": copy.deepcopy(dict(applicability)) if applicability else {},
        "counterexamples": [str(item) for item in counterexamples],
        "needs_validation": bool(needs_validation),
        "is_hypothesis_not_fact": True,
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _prior(records: Sequence[Dict[str, Any]], ident: str, kind: str) -> List[Dict[str, Any]]:
    return [item for item in records
            if item.get("trajectory_id") == ident and item.get("record") == kind]


def _payload_digest(record: Dict[str, Any]) -> str:
    stripped = {key: value for key, value in record.items()
                if key not in ("seq", "previous")}
    return _digest(stripped)


def leak_strings(records: Sequence[Dict[str, Any]], ident: str) -> List[str]:
    """Outcome text that must never be visible inside the decision for `ident`.

    Reuses the replay guard's shape (>= 12 characters) so a distinctive later result
    cannot be smuggled into a decision's frozen context.
    """
    found: List[str] = []
    for record in records:
        if record.get("trajectory_id") != ident or record.get("record") != "outcome":
            continue
        result = record.get("result") if isinstance(record.get("result"), dict) else {}
        for key in ("summary", "detail", "value", "observed"):
            text = result.get(key)
            if isinstance(text, str) and len(text) >= 12:
                found.append(text)
        if isinstance(result.get("summary"), str) and len(result["summary"]) >= 12:
            found.append(result["summary"])
    return sorted(set(found))


def record_errors(record: Dict[str, Any], *, state: Optional[Dict[str, Any]] = None,
                  records: Sequence[Dict[str, Any]] = (),
                  route: Optional[str] = None) -> List[cg.Diagnostic]:
    """Structural, binding and ordering validation for a prospective record.

    `state` enables canonical source-reference checks (`DT3`) and stale-state rejection
    (`DT4`). `records` enables ordering and leakage checks (`DT2`/`DT4`/`DT5`/`DT6`).
    """
    diagnostics: List[cg.Diagnostic] = []
    kind = record.get("record")
    ident = record.get("trajectory_id")
    path = f"trajectory[{ident or '?'}]"

    if record.get("_schema") != SCHEMA_TRAJECTORY:
        diagnostics.append(_diag("DT1", path, f"_schema 必须是 {SCHEMA_TRAJECTORY!r}"))
    if kind not in RECORD_KINDS:
        diagnostics.append(_diag("DT1", path, f"未知记录类型 {kind!r}；允许 {RECORD_KINDS}"))
        return _dedupe(diagnostics)
    if not isinstance(ident, str) or not ident.startswith("DT-"):
        diagnostics.append(_diag("DT1", path, "trajectory_id 缺失或格式错误"))
        return _dedupe(diagnostics)
    if not isinstance(record.get("recorded_at"), str) or not record.get("recorded_at"):
        diagnostics.append(_diag("DT1", path, "recorded_at 缺失"))

    if kind == "decision":
        diagnostics += _decision_errors(record, state=state, records=records, route=route)
    elif kind == "prediction":
        diagnostics += _prediction_errors(record, records=records)
    elif kind == "outcome":
        diagnostics += _outcome_errors(record, state=state, records=records)
    elif kind == "learning":
        diagnostics += _learning_errors(record, records=records)
    return _dedupe(diagnostics)


def _decision_errors(record: Dict[str, Any], *, state: Optional[Dict[str, Any]],
                     records: Sequence[Dict[str, Any]],
                     route: Optional[str]) -> List[cg.Diagnostic]:
    diagnostics: List[cg.Diagnostic] = []
    ident = record["trajectory_id"]
    path = f"trajectory[{ident}]"
    context = record.get("context")
    decision = record.get("decision")
    if not isinstance(context, dict):
        return [_diag("DT1", path, "decision 记录缺少 context 对象")]
    if not isinstance(decision, dict):
        return [_diag("DT1", path, "decision 记录缺少 decision 对象")]

    for required in ("state_version", "scientific_question", "decided_at", "state_digest"):
        if context.get(required) in (None, ""):
            diagnostics.append(_diag("DT1", path, f"context.{required} 缺失"))
    if not isinstance(decision.get("candidates"), list) or not decision.get("candidates"):
        diagnostics.append(_diag("DT1", path, "decision.candidates 必须是非空数组（合法候选集）"))
    if decision.get("chosen") is not None and not isinstance(decision.get("chosen"), str):
        diagnostics.append(_diag("DT1", path, "decision.chosen 必须是字符串或 null"))
    if decision.get("dispatch_status") not in DISPATCH_STATUSES:
        diagnostics.append(_diag("DT1", path,
                                 f"dispatch_status 必须是 {DISPATCH_STATUSES} 之一"))
    if not isinstance(decision.get("scheduler_priority"), dict):
        diagnostics.append(_diag("DT1", path, "decision.scheduler_priority 缺失"))

    # The chosen action must come from the recorded legal candidate set.
    candidate_ids = {str(item.get("action")) for item in decision.get("candidates") or []
                     if isinstance(item, dict)}
    chosen = decision.get("chosen")
    if isinstance(chosen, str) and candidate_ids and chosen not in candidate_ids:
        diagnostics.append(_diag("DT1", path,
                                 f"chosen={chosen!r} 不在记录的候选集合 {sorted(candidate_ids)} 内"))

    for key in LEAK_KEYS:
        if key in context or key in decision:
            diagnostics.append(_diag("DT6", path, f"决策记录不得包含事后结果字段 {key!r}"))

    if isinstance(route, str) and route and record.get("route") and record["route"] != route:
        diagnostics.append(_diag("DT10", path,
                                 f"route 绑定不一致：记录 {record['route']!r} ≠ 当前 {route!r}"))

    if state is not None:
        if context.get("state_version") != state.get("state_version"):
            diagnostics.append(_diag(
                "DT4", path,
                f"过期状态：context.state_version={context.get('state_version')!r} "
                f"≠ 当前 {state.get('state_version')!r}"))
        if context.get("state_digest") not in (None, "") and \
                context.get("state_digest") != _digest(state):
            diagnostics.append(_diag("DT4", path, "context.state_digest 与当前 state 不一致（信息可见性不成立）"))
        diagnostics += _ref_errors(state, path,
                                  {"hypotheses": context.get("active_hypotheses") or [],
                                   "uncertainties": context.get("key_uncertainties") or [],
                                   "evidence": context.get("visible_evidence") or []})

    # Ordering: a decision for an already-observed trajectory may not be appended again
    # with different content, and may not be back-dated behind its own outcome.
    existing = _prior(records, ident, "decision")
    if existing:
        if _payload_digest(existing[-1]) != _payload_digest(record):
            diagnostics.append(_diag("DT2", path,
                                     "同一 trajectory_id 已存在且内容不同：旧决策不可被结果改写"))
        outcomes = _prior(records, ident, "outcome")
        if outcomes and context.get("decided_at") and \
                _text_le(context["decided_at"], outcomes[-1].get("observed_at")):
            diagnostics.append(_diag("DT4", path, "决策时间晚于其结果观测时间（时间顺序倒挂）"))
    return diagnostics


def _prediction_errors(record: Dict[str, Any],
                       *, records: Sequence[Dict[str, Any]]) -> List[cg.Diagnostic]:
    diagnostics: List[cg.Diagnostic] = []
    ident = record["trajectory_id"]
    path = f"trajectory[{ident}]"
    if not _prior(records, ident, "decision"):
        diagnostics.append(_diag("DT1", path, "prediction 记录必须先有 decision 记录"))
    if _prior(records, ident, "outcome"):
        diagnostics.append(_diag("DT5", path,
                                 "已有 outcome 之后不得补写预测：预注册预测不能事后补写"))
    for required in ("question", "distinguishable_predictions"):
        if record.get(required) in (None, "", []):
            diagnostics.append(_diag("DT1", path, f"prediction.{required} 缺失"))
    return diagnostics


def _outcome_errors(record: Dict[str, Any], *, state: Optional[Dict[str, Any]],
                    records: Sequence[Dict[str, Any]]) -> List[cg.Diagnostic]:
    diagnostics: List[cg.Diagnostic] = []
    ident = record["trajectory_id"]
    path = f"trajectory[{ident}]"
    decisions = _prior(records, ident, "decision")
    if not decisions:
        diagnostics.append(_diag("DT1", path, "outcome 记录必须先有 decision 记录"))
    else:
        decided = decisions[-1]
        decided_at = (decided.get("context") or {}).get("decided_at")
        if decided_at and record.get("observed_at") and _text_lt(record["observed_at"], decided_at):
            diagnostics.append(_diag("DT4", path, "outcome.observed_at 早于 decision.decided_at"))
        decision_version = (decided.get("context") or {}).get("state_version")
        if isinstance(decision_version, int) and isinstance(record.get("at_state_version"), int) \
                and record["at_state_version"] < decision_version:
            diagnostics.append(_diag(
                "DT4", path,
                f"过期状态：outcome.at_state_version={record['at_state_version']} "
                f"< decision.state_version={decision_version}"))
    if _prior(records, ident, "outcome"):
        diagnostics.append(_diag("DT1", path, "同一 trajectory 只允许一条 outcome（幂等追加）"))
    if not isinstance(record.get("result"), dict) or not record.get("result"):
        diagnostics.append(_diag("DT1", path, "outcome.result 必须是非空对象（不得只写状态名）"))
    for key in ("scientific_delta", "decision_delta", "policy_delta"):
        if record.get(key) not in DELTA_VALUES:
            diagnostics.append(_diag("DT1", path, f"{key} 必须是 {DELTA_VALUES} 之一"))
    if record.get("evidence_qualification") not in EVIDENCE_QUALIFICATIONS:
        diagnostics.append(_diag("DT1", path,
                                 f"evidence_qualification 必须是 {EVIDENCE_QUALIFICATIONS} 之一"))
    if record.get("scientific_delta") == "scientific" and \
            record.get("evidence_qualification") != "qualified":
        diagnostics.append(_diag("DT9", path,
                                 "未取得合格证据不得声称 scientific_delta（工程状态不算科学增量）"))
    if record.get("policy_delta") == "policy" and not record.get("policy_effect_observed") \
            and not record.get("decision_delta") == "decision":
        diagnostics.append(_diag("DT9", path,
                                 "policy_delta 必须伴随可观察的策略作用或决策变化"))
    refs = record.get("evidence_refs")
    if not isinstance(refs, list):
        diagnostics.append(_diag("DT1", path, "evidence_refs 必须是数组"))
    elif state is not None:
        diagnostics += _ref_errors(state, path, {"evidence": [item.get("evidence")
                                                              for item in refs
                                                              if isinstance(item, dict)]})

    # Leakage: an outcome summary must not already be present in the frozen decision.
    if decisions:
        frozen = json.dumps(decisions[-1].get("context") or {}, ensure_ascii=False)
        frozen += json.dumps(decisions[-1].get("decision") or {}, ensure_ascii=False)
        for text in leak_strings([record], ident):
            if text and text in frozen:
                diagnostics.append(_diag("DT6", path,
                                         "决策的冻结上下文已包含本次结果文本：结果泄漏"))
    return diagnostics


def _learning_errors(record: Dict[str, Any],
                     *, records: Sequence[Dict[str, Any]]) -> List[cg.Diagnostic]:
    diagnostics: List[cg.Diagnostic] = []
    ident = record["trajectory_id"]
    path = f"trajectory[{ident}]"
    if not _prior(records, ident, "outcome"):
        diagnostics.append(_diag("DT1", path,
                                 "learning 记录必须在真实 outcome 之后（不得先写学习信号）"))
    if not isinstance(record.get("learning_value"), bool):
        diagnostics.append(_diag("DT1", path, "learning_value 必须是布尔值"))
    if record.get("learning_value") and not _as_text(record.get("bias_hypothesis")):
        diagnostics.append(_diag("DT1", path,
                                 "有学习价值时必须写出待检验的偏差假设（不能只有一句“更科学”）"))
    if _prior(records, ident, "learning"):
        diagnostics.append(_diag("DT1", path, "同一 trajectory 只允许一条 learning 记录"))
    return diagnostics


def _ref_errors(state: Dict[str, Any], path: str,
                refs: Dict[str, Sequence[Any]]) -> List[cg.Diagnostic]:
    view = cg.CanonicalView(state)
    diagnostics: List[cg.Diagnostic] = []
    for key, identifiers in refs.items():
        for ident in identifiers:
            if ident in (None, ""):
                diagnostics.append(_diag("DT3", path, f"{key} 引用为空"))
                continue
            if not view.contains(key, str(ident)):
                diagnostics.append(_diag("DT3", path, f"悬空来源引用 {key}[{ident}]"))
    return diagnostics


# ---------------------------------------------------------------------------
# Public write API
# ---------------------------------------------------------------------------

def append_record(path: Path, record: Dict[str, Any], *, state: Optional[Dict[str, Any]] = None,
                  route: Optional[str] = None,
                  allow_replay: bool = False) -> Dict[str, Any]:
    """Validate then durably append one record.

    Returns `{"status": "APPENDED"|"DUPLICATE"|"INVALID"|"HOLD", ...}`. Re-submitting an
    identical record is a `DUPLICATE` and writes nothing; re-submitting a *different*
    record for the same trajectory is `INVALID` (DT2).
    """
    if not allow_replay:
        pass
    records, _ = load_records(path)
    if route is None and state is not None:
        route = cg.route_of(Path(path).parent / cg.STATE_NAME) \
            if (Path(path).parent / cg.STATE_NAME).exists() else Path(path).parent.name
    diagnostics = record_errors(record, state=state, records=records, route=route)
    if diagnostics:
        return {"status": "INVALID", "written": False, "path": str(path),
                "diagnostics": [item.render() for item in diagnostics],
                "codes": sorted({item.rule for item in diagnostics})}
    ident = record["trajectory_id"]
    same_kind = _prior(records, ident, record["record"])
    if same_kind and record["record"] in ("decision", "outcome", "learning", "prediction"):
        if _payload_digest(same_kind[-1]) == _payload_digest(record):
            return {"status": "DUPLICATE", "written": False, "path": str(path),
                    "trajectory_id": ident, "record": record["record"],
                    "diagnostics": []}
        return {"status": "INVALID", "written": False, "path": str(path),
                "diagnostics": [f"DT2 同一 {record['record']} 记录已存在且内容不同"],
                "codes": ["DT2"]}
    stored = copy.deepcopy(record)
    stored["seq"] = len(records) + 1
    stored["previous"] = _digest(records[-1]) if records else None
    _append_line(Path(path), stored)
    return {"status": "APPENDED", "written": True, "path": str(path),
            "trajectory_id": ident, "record": record["record"], "seq": stored["seq"],
            "digest": _digest(stored), "diagnostics": []}


def record_context(state: Dict[str, Any], *, state_path: Optional[Path] = None,
                   project: Optional[str] = None,
                   scheduler: Optional[Dict[str, Any]] = None,
                   cognition_digest: Optional[str] = None,
                   route: Optional[str] = None) -> Dict[str, Any]:
    """Convenience wrapper: a context frozen from a real state, with derived ids."""
    hypotheses = [item.get("id") for item in state.get("hypotheses") or []
                  if isinstance(item, dict) and item.get("status") not in ("killed", "refuted")]
    uncertainties = [item.get("id") for item in state.get("uncertainties") or []
                     if isinstance(item, dict) and item.get("status") == "open"]
    evidence = [item.get("id") for item in state.get("evidence") or []
                if isinstance(item, dict)]
    if route is None and state_path is not None:
        route = cg.route_of(state_path)
    return build_context(state, scientific_question=str(
        (state.get("contract") or {}).get("goal") or ""),
        active_hypotheses=hypotheses, key_uncertainties=uncertainties,
        visible_evidence=evidence, stop_rules=[], scheduler=scheduler,
        cognition_digest=cognition_digest)


# ---------------------------------------------------------------------------
# Derived views (rebuildable, never a second source of truth)
# ---------------------------------------------------------------------------

def rebuild_trajectories(records: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Fold the append-only log into per-trajectory views. Rebuild must be deterministic."""
    views: Dict[str, Dict[str, Any]] = {}
    for record in records:
        ident = record.get("trajectory_id")
        if not isinstance(ident, str):
            continue
        view = views.setdefault(ident, {"trajectory_id": ident, "decision": None,
                                        "prediction": None, "outcome": None,
                                        "learning": None, "records": 0})
        view["records"] += 1
        kind = record.get("record")
        if kind in ("decision", "prediction", "outcome", "learning"):
            view[kind] = record
        view["project"] = record.get("project")
        view["route"] = record.get("route")
    return views


def pending_outcomes(records: Sequence[Dict[str, Any]]) -> List[str]:
    """Trajectories with a decision but no real result yet — honest `not_dispatched` list."""
    views = rebuild_trajectories(records)
    return sorted(ident for ident, view in views.items()
                  if view["decision"] is not None and view["outcome"] is None)


def learning_records(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [item for item in records if item.get("record") == "learning"]


def support_ids(records: Sequence[Dict[str, Any]], *, require_outcome: bool = True) -> List[str]:
    """Trajectory ids usable as policy evidence: they must have a real observed outcome."""
    views = rebuild_trajectories(records)
    return sorted(ident for ident, view in views.items()
                  if view["decision"] is not None
                  and (view["outcome"] is not None or not require_outcome))


# ---------------------------------------------------------------------------
# Small time helpers (ISO-8601 Z strings compare lexicographically)
# ---------------------------------------------------------------------------

def _text_lt(left: Any, right: Any) -> bool:
    return isinstance(left, str) and isinstance(right, str) and left < right


def _text_le(left: Any, right: Any) -> bool:
    return isinstance(left, str) and isinstance(right, str) and left <= right


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    def error(self, message):  # pragma: no cover - argparse plumbing
        self.print_usage(sys.stderr)
        raise SystemExit(EXIT_ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(description=__doc__,
                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", choices=("open", "outcome", "learning", "show",
                                                       "list", "validate"))
    parser.add_argument("--state", help="path to research-state.json")
    parser.add_argument("--trajectory", help="path to decision-trajectory.jsonl")
    parser.add_argument("--scheduler", help="path to scheduler.json")
    parser.add_argument("--record", help="path to a JSON record file (or - for stdin)")
    parser.add_argument("--trajectory-id", help="trajectory id for outcome/learning/show")
    parser.add_argument("--selftest", action="store_true")
    return parser


def _store_path(args) -> Path:
    if args.trajectory:
        return Path(args.trajectory)
    if args.state:
        return trajectory_path(Path(args.state))
    raise SystemExit("需要 --state 或 --trajectory")


def _load_state(args) -> Optional[Dict[str, Any]]:
    if not args.state:
        return None
    return cg.load_state(Path(args.state))


def _emit(payload: Any, code: int = EXIT_OK) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return code


def _read_record(args) -> Dict[str, Any]:
    if not args.record:
        raise SystemExit("需要 --record")
    if args.record == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(args.record).read_text(encoding="utf-8"))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    try:
        path = _store_path(args)
    except SystemExit as exc:
        return _emit({"status": "INVALID", "errors": [str(exc)]}, EXIT_ERROR)
    state = _load_state(args)

    if args.command == "show":
        records, _ = load_records(path)
        views = rebuild_trajectories(records)
        if args.trajectory_id:
            view = views.get(args.trajectory_id)
            if view is None:
                return _emit({"status": "NOT_FOUND", "trajectory_id": args.trajectory_id},
                             EXIT_ERROR)
            return _emit({"status": "OK", "trajectory": view})
        return _emit({"status": "OK", "trajectories": sorted(views)})

    if args.command == "list":
        records, _ = load_records(path)
        views = rebuild_trajectories(records)
        return _emit({"status": "OK", "count": len(views),
                      "pending": pending_outcomes(records),
                      "supported": support_ids(records),
                      "learning": [item.get("trajectory_id") for item in learning_records(records)]})

    if args.command == "validate":
        records, diagnostics = load_records(path, tolerant=True)
        errors: List[str] = [item.render() for item in diagnostics]
        for record in records:
            errors += [item.render() for item in record_errors(record, state=state,
                                                               records=records)]
        verdict = "PASS" if not errors else "FAIL"
        return _emit({"status": verdict, "records": len(records), "errors": errors},
                     EXIT_OK if not errors else EXIT_HARD)

    # open / outcome / learning all append a caller-supplied record
    record = _read_record(args)
    if args.command == "open" and args.state:
        # Bind the record to the live state instead of trusting the caller's snapshot.
        route = cg.route_of(Path(args.state))
        result = append_record(path, record, state=state, route=route)
    else:
        result = append_record(path, record, state=state)
    return _emit(result, EXIT_OK if result["status"] in ("APPENDED", "DUPLICATE") else EXIT_HARD)


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _fixture_state(version: int = 3) -> Dict[str, Any]:
    state = {
        "_schema": "research-idea-pipeline/research-state@1",
        "state_version": version,
        "contract": {"goal": "fixture goal", "primary_anchor": "A0", "constraints": [],
                     "resources": {}, "out_of_scope": []},
        "claims": [{"id": "C1", "statement": "s", "status": "ungrounded"}],
        "evidence": [{"id": "E1", "kind": "experiment", "supports": ["C1"], "strength": "weak",
                      "scope": "s", "epistemic_status": "grounded", "source_ref": "fixture",
                      "verification_tier": "T0", "validity": "valid"}],
        "assumptions": [], "hypotheses": [{"id": "H1", "statement": "h", "status": "active",
                                           "validity": "valid", "island": "P1",
                                           "operator": "reframe"}],
        "experiments": [], "literature": [],
        "failures": [], "uncertainties": [{"id": "U1", "question": "q", "importance": "high",
                                           "uncertainty": "high", "status": "open",
                                           "validity": "valid"}],
        "assurance": [], "repairs": [],
        "narrative_view": {}, "reviews": [],
        "decision": {"verdict": "continue", "rationale": "", "next_phase": "R3"},
    }
    return state


def _synthetic_decision(state: Dict[str, Any], *, chosen: str = "H1",
                        recorded_at: str = "2026-01-01T00:00:00Z",
                        dispatch_status: str = "not_dispatched") -> Dict[str, Any]:
    context = build_context(state, scientific_question="fixture question",
                            active_hypotheses=["H1"], key_uncertainties=["U1"],
                            visible_evidence=["E1"], decided_at=recorded_at,
                            scheduler={"next_actions": [{"action": "H1"}]})
    return build_decision_record(
        state, route="A", project="fixture", context=context,
        candidates=[{"action": "H1", "type": "repair", "target": "H1", "eig": "high",
                     "cost": "low", "preconditions": []},
                    {"action": "H2", "type": "discriminating_experiment", "target": "U1",
                     "eig": "high", "cost": "low", "preconditions": []}],
        chosen=chosen, scheduler_priority={"level": 4, "label": "high_information_gain_test"},
        policy_version="none", policy_changed_order=False, dispatch_status=dispatch_status,
        recorded_at=recorded_at)


def selftest() -> int:
    import tempfile
    checks: List[Tuple[str, bool]] = []

    def check(name: str, condition: bool) -> None:
        checks.append((name, bool(condition)))

    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / TRAJECTORY_NAME
        state = _fixture_state()
        decision = _synthetic_decision(state)
        ident = decision["trajectory_id"]

        first = append_record(path, decision, state=state, route="A")
        check("open appends", first["status"] == "APPENDED")
        second = append_record(path, decision, state=state, route="A")
        check("identical resubmission is idempotent",
              second["status"] == "DUPLICATE" and second["written"] is False)
        check("one line on disk", len(path.read_text(encoding="utf-8").splitlines()) == 1)

        tampered = copy.deepcopy(decision)
        tampered["decision"]["chosen"] = "H2"
        third = append_record(path, tampered, state=state, route="A")
        check("rewriting a recorded decision is refused",
              third["status"] == "INVALID" and "DT2" in third["codes"])

        stale = _fixture_state(version=99)
        stale_result = append_record(path, _synthetic_decision(stale), state=state, route="A")
        check("stale state is refused", stale_result["status"] == "INVALID"
              and "DT4" in stale_result["codes"])

        leaked = copy.deepcopy(_synthetic_decision(state, chosen="H2",
                                                   recorded_at="2026-01-02T00:00:00Z"))
        leaked["context"]["visible_evidence"] = ["E1"]
        leaked["context"]["outcome"] = {"summary": "later observable result text"}
        leak_result = append_record(path, leaked, state=state, route="A")
        check("future-result field in a decision is refused",
              leak_result["status"] == "INVALID" and "DT6" in leak_result["codes"])

        # Back-dated decision relative to an existing outcome.
        outcome = build_outcome_record(ident, at_state_version=state["state_version"],
                                       result={"kind": "experiment_result", "summary":
                                               "a real observed value 0.42"},
                                       evidence_refs=[{"evidence": "E1"}],
                                       scientific_delta="none", decision_delta="decision",
                                       evidence_qualification="qualified",
                                       observed_at="2026-01-03T00:00:00Z")
        outcome_result = append_record(path, outcome, state=state, route="A")
        check("outcome after a real result appends", outcome_result["status"] == "APPENDED")

        post_hoc = {
            "_schema": SCHEMA_TRAJECTORY, "record": "prediction", "trajectory_id": ident,
            "recorded_at": "2026-01-04T00:00:00Z", "question": "q",
            "distinguishable_predictions": ["p"], "project": "fixture", "route": "A",
        }
        post_hoc_result = append_record(path, post_hoc, state=state, route="A")
        check("post-hoc prediction is refused",
              post_hoc_result["status"] == "INVALID" and "DT5" in post_hoc_result["codes"])

        learning = build_learning_record(ident, learning_value=True,
                                         bias_hypothesis="prefers cheap diagnostics",
                                         applicability={"problem_structure": "reframe"},
                                         counterexamples=["none"],
                                         recorded_at="2026-01-05T00:00:00Z")
        learning_result = append_record(path, learning, state=state, route="A")
        check("learning signal appends after outcome",
              learning_result["status"] == "APPENDED")

        bad_delta = build_outcome_record("DT-nonexistent", at_state_version=1,
                                         result={"kind": "x"},
                                         scientific_delta="scientific",
                                         evidence_qualification="unqualified",
                                         observed_at="2026-01-06T00:00:00Z")
        bad_delta_result = append_record(path, bad_delta, state=state)
        check("unqualified evidence cannot claim a scientific delta",
              bad_delta_result["status"] == "INVALID" and "DT9" in bad_delta_result["codes"])

        records, _ = load_records(path)
        views = rebuild_trajectories(records)
        check("rebuild reconstructs the trajectory",
              views[ident]["decision"] is not None and views[ident]["outcome"] is not None
              and views[ident]["learning"] is not None)
        check("rebuild is deterministic",
              rebuild_trajectories(records) == views)
        check("pending list excludes observed trajectories", ident not in pending_outcomes(records))
        check("supported ids require a real outcome", ident in support_ids(records))

        # Tamper detection: rewriting a historical line must break the chain.
        lines = path.read_text(encoding="utf-8").splitlines()
        first_line = json.loads(lines[0])
        first_line["decision"]["chosen"] = "H2"
        lines[0] = json.dumps(first_line, ensure_ascii=False, sort_keys=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            load_records(path)
            chain_detected = False
        except TrajectoryError:
            chain_detected = True
        check("hash chain detects a rewritten history line", chain_detected)

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    print("selftest " + ("OK" if not failed else "FAILED: " + "; ".join(failed)))
    return EXIT_OK if not failed else EXIT_HARD


if __name__ == "__main__":
    raise SystemExit(main())
