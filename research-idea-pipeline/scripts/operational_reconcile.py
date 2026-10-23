#!/usr/bin/env python3
"""operational_reconcile.py — thin coordination between maintenance and science.

This module does **not** create a second canonical state, a new evidence gate or a daemon.
It reads the existing canonical state, scheduler telemetry, cognitive projection and
source-bound outcome bundles, then:

1. performs idempotent **A-class** maintenance (cognitive projection and `STATUS.md`),
2. reports scheduler / monitor freshness and refuses to use stale telemetry,
3. detects terminal experiments that still lack a legal R9.O/R10 outcome transaction,
4. applies a prepared packet/analysis/audit bundle **only** when the existing
   `evidence_outcome.validate()` / `apply()` path accepts it,
5. returns structured `HOLD` reasons for everything it cannot legally finish.

All scientific writes still go through `evidence_outcome.apply()`. All projections remain
derived views. A read-only call (`apply=False`) never writes.

Usage:
    python3 scripts/operational_reconcile.py --state <research-state.json>
    python3 scripts/operational_reconcile.py --state <research-state.json> --apply
    python3 scripts/operational_reconcile.py --state <research-state.json> \
        --outcome-root results/A/X88/outcome --apply

Exit codes:
    0  OK
    3  BLOCKED (invalid transaction, conflicting evidence, invalid canonical state)
    4  HOLD (missing evidence, stale telemetry, maintenance failure)
    1  bad arguments / unreadable input
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import pathlib
import sys
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import cognition as cg
import evidence_outcome as eo
import render_status
import state_check as sc

SCHEMA = "research-idea-pipeline/operational-reconciliation@1"
EXIT_OK = 0
EXIT_BLOCKED = 3
EXIT_HOLD = 4
EXIT_ERROR = 1

CLASS_ROUTINE = "routine"
CLASS_EVIDENCE = "evidence_gated"
CLASS_PRIVILEGED = "privileged"

#: Frozen classification. The table exists so callers cannot silently turn a scientific
#: update into "maintenance". Only entries marked routine may run without a user decision.
OPERATIONS: Dict[str, str] = {
    "refresh_cognition_projection": CLASS_ROUTINE,
    "refresh_status_projection": CLASS_ROUTINE,
    "check_scheduler_freshness": CLASS_ROUTINE,
    "inspect_result_artifacts": CLASS_ROUTINE,
    "detect_outcome_submission": CLASS_EVIDENCE,
    "submit_outcome_transaction": CLASS_EVIDENCE,
    "change_claim_or_hypothesis": CLASS_EVIDENCE,
    "write_assurance": CLASS_EVIDENCE,
    "change_research_decision": CLASS_EVIDENCE,
    "change_primary_anchor": CLASS_PRIVILEGED,
    "exceed_budget": CLASS_PRIVILEGED,
    "modify_frozen_protocol": CLASS_PRIVILEGED,
    "run_unauthorized_large_training": CLASS_PRIVILEGED,
    "bypass_evidence_gate": CLASS_PRIVILEGED,
}

STOP_TOKENS = (
    "stopped", "terminated", "sigterm", "sigint", "sigkill", "aborted", "abort",
    "暂停", "中止", "终止", "已停止", "用户停止", "not scientifically complete",
    "not a scientific completion", "不要恢复", "do not resume", "paused",
)
MONITOR_STATUSES = ("planned", "running", "done", "failed")


# ---------------------------------------------------------------------------
# Small deterministic helpers
# ---------------------------------------------------------------------------

def classify(operation: str) -> str:
    """Return the frozen class for an operation, or raise for an unknown name."""
    if operation not in OPERATIONS:
        raise KeyError(f"unknown operation: {operation}")
    return OPERATIONS[operation]


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _atomic_write_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: pathlib.Path, root: pathlib.Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except (ValueError, OSError):
        return str(path)


def _capture(call, *args, **kwargs) -> Tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = call(*args, **kwargs)
    return int(code), buffer.getvalue().strip()


# ---------------------------------------------------------------------------
# Canonical state, scheduler and monitor freshness
# ---------------------------------------------------------------------------

def _violation_rows(violations: Iterable[Any]) -> List[Dict[str, Any]]:
    rows = []
    for violation in violations:
        if hasattr(violation, "as_dict"):
            rows.append(violation.as_dict())
        else:
            rows.append({"detail": str(violation)})
    return rows


def _outcome_errors(state: Dict[str, Any]) -> List[str]:
    try:
        return [str(item) for item in eo.state_errors(state)]
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as exc:
        return [f"invalid outcome state: {exc}"]


def stopped_execution(experiment: Dict[str, Any]) -> Optional[str]:
    """Return the stopped/terminated evidence text, if the record says so explicitly.

    This is deliberately limited to **structured canonical fields**. Logs or scheduler
    monitor entries are not allowed to manufacture a scientific outcome here.
    """
    fields = (
        experiment.get("execution_boundary"),
        experiment.get("status_note"),
        (experiment.get("external_execution_record") or {}).get("status")
        if isinstance(experiment.get("external_execution_record"), dict) else None,
        (experiment.get("execution_record") or {}).get("status")
        if isinstance(experiment.get("execution_record"), dict) else None,
    )
    for value in fields:
        text = _text(value)
        lowered = text.lower()
        if text and any(token in lowered for token in STOP_TOKENS):
            return text
    return None


def _iter_monitor_records(value: Any, depth: int = 0) -> Iterable[Dict[str, Any]]:
    """Yield dicts that look like scheduler experiment monitor records."""
    if depth > 5:
        return
    if isinstance(value, dict):
        if isinstance(value.get("experiment"), str) and (
                value.get("status") in MONITOR_STATUSES
                or "progress" in value or "pid" in value or "next" in value):
            yield value
        for item in value.values():
            yield from _iter_monitor_records(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_monitor_records(item, depth + 1)


def _scheduler_view(state: Dict[str, Any], route_dir: pathlib.Path,
                    canonical_ok: bool) -> Dict[str, Any]:
    path = route_dir / cg.SCHEDULER_NAME
    view: Dict[str, Any] = {
        "path": _rel(path, route_dir), "status": "MISSING", "state_version": None,
        "reason": "no scheduler telemetry", "next_actions": [], "monitor_conflicts": [],
        "errors": [],
    }
    if not path.is_file():
        return view
    try:
        scheduler = _load_json(path)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        view.update(status="UNREADABLE", reason=f"{type(exc).__name__}: {exc}")
        return view
    if not isinstance(scheduler, dict):
        view.update(status="UNREADABLE", reason="scheduler is not a JSON object")
        return view
    version = scheduler.get("state_version")
    view["state_version"] = version
    if version != state.get("state_version"):
        view.update(
            status="STALE",
            reason=(f"scheduler state_version={version!r} != canonical "
                    f"{state.get('state_version')!r}; next_actions and monitors are history"),
        )
        return view
    view.update(status="CURRENT", reason="scheduler is bound to the current state_version")
    actions = [item.get("action") for item in scheduler.get("next_actions") or []
               if isinstance(item, dict) and item.get("action")]
    view["next_actions"] = actions
    # A current version is not enough: the real gate also checks EIG provenance,
    # blocked experiments and terminal references. Do not invent a second gate.
    if canonical_ok:
        import execution_gate as eg
        try:
            verdict = eg.scheduler_check(state, scheduler)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            verdict = {"status": "FAIL", "errors": [f"invalid scheduler: {exc}"]}
        view["errors"] = [str(item) for item in verdict.get("errors") or []]
        view["status"] = "PASS" if verdict.get("status") == "PASS" else "FAIL"
        if view["status"] == "FAIL":
            view["reason"] = "scheduler gate failed; actions are not usable as current decisions"
            return view
    experiments = {str(item.get("id")): item for item in state.get("experiments") or []
                   if isinstance(item, dict)}
    conflicts: List[Dict[str, Any]] = []
    for record in _iter_monitor_records(scheduler):
        xid = str(record.get("experiment"))
        experiment = experiments.get(xid)
        if experiment is None:
            continue
        recorded = record.get("status")
        actual = experiment.get("status")
        stopped = stopped_execution(experiment)
        if recorded in ("running", "planned") and stopped:
            conflicts.append({"experiment": xid, "monitor_status": recorded,
                              "canonical_status": actual,
                              "reason": "monitor says active but execution_boundary says stopped",
                              "boundary": stopped})
        elif recorded == "done" and actual != "done":
            conflicts.append({"experiment": xid, "monitor_status": recorded,
                              "canonical_status": actual,
                              "reason": "monitor says done but canonical state is not done"})
        elif recorded == "failed" and actual != "failed":
            conflicts.append({"experiment": xid, "monitor_status": recorded,
                              "canonical_status": actual,
                              "reason": "monitor says failed but canonical state is not failed"})
    view["monitor_conflicts"] = conflicts
    if conflicts:
        view["status"] = "CONFLICT"
        view["reason"] = "scheduler monitor records disagree with canonical state"
    return view


def _project_root(route_dir: pathlib.Path) -> pathlib.Path:
    """The project root that owns `results/` and the human `routes/` view."""
    pipeline = route_dir.parent.parent
    if pipeline.name == ".research-idea-pipeline":
        return pipeline.parent
    return route_dir


def _human_status_path(route_dir: pathlib.Path, route: str) -> Tuple[pathlib.Path, pathlib.Path]:
    """Return the human STATUS.md path and the root used for relative write reporting.

    Canonical state lives in `<project>/.research-idea-pipeline/routes/<R>/`; the human view
    lives in `<project>/routes/<R>/STATUS.md`.  Tests and installed fixtures may use a plain
    `<root>/<R>/research-state.json`, in which case STATUS.md sits next to the state.
    """
    project = _project_root(route_dir)
    if project != route_dir:
        return project / "routes" / route / "STATUS.md", project
    return route_dir / "STATUS.md", route_dir


# ---------------------------------------------------------------------------
# Result artifacts and prepared outcome bundles
# ---------------------------------------------------------------------------

def _result_locators(route_dir: pathlib.Path, route: str, xid: str,
                     experiment: Optional[Dict[str, Any]] = None) -> List[str]:
    base = _project_root(route_dir) / "results" / route / xid
    candidates = [base / "summary.md", base / "summary.json", base / "metrics.json"]
    locators = [_rel(path, route_dir) for path in candidates if path.is_file()]
    for key in ("completed_result_ref", "result_ref", "completion_audit_ref",
                "review_ref", "launch_ref", "protocol_ref"):
        value = _text((experiment or {}).get(key))
        if value and value not in locators:
            locators.append(value)
    prereg = (experiment or {}).get("preregistration")
    if isinstance(prereg, dict):
        value = _text(prereg.get("protocol_ref"))
        if value and value not in locators:
            locators.append(value)
    return locators


def _bundle_prefix(name: str) -> Optional[str]:
    for suffix in ("-packet.json", "_packet.json"):
        if name.endswith(suffix):
            return name[:-len(suffix)]
    if name == "packet.json":
        return ""
    return None


def _find_outcome_bundles(root: pathlib.Path) -> List[pathlib.Path]:
    if not root.is_dir():
        return []
    packets: List[pathlib.Path] = []
    for path in root.rglob("*.json"):
        if _bundle_prefix(path.name) is not None:
            packets.append(path)
    return sorted(set(packets), key=lambda item: str(item))


def _load_bundle(packet_path: pathlib.Path) -> Dict[str, Any]:
    prefix = _bundle_prefix(packet_path.name) or ""
    if prefix:
        analysis_path = packet_path.with_name(prefix + "-analysis.json")
        audit_path = packet_path.with_name(prefix + "-audit.json")
    else:
        analysis_path = packet_path.with_name("analysis.json")
        audit_path = packet_path.with_name("audit.json")
    payloads: Dict[str, Any] = {}
    problems: List[str] = []
    for key, path in (("packet", packet_path), ("analysis", analysis_path), ("audit", audit_path)):
        if not path.is_file():
            problems.append(f"missing {key}: {path.name}")
            continue
        try:
            payloads[key] = _load_json(path)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            problems.append(f"unreadable {key}: {type(exc).__name__}: {exc}")
    return {"packet_path": packet_path, "analysis_path": analysis_path,
            "audit_path": audit_path, "payloads": payloads, "problems": problems}


def _bundle_status(state: Dict[str, Any], xid: str,
                   bundle: Dict[str, Any]) -> Dict[str, Any]:
    problems = list(bundle["problems"])
    payloads = bundle["payloads"]
    if problems:
        return {"status": "INVALID", "errors": problems}
    packet = payloads.get("packet") or {}
    analysis = payloads.get("analysis") or {}
    audit = payloads.get("audit") or {}
    if not isinstance(packet, dict) or packet.get("experiment_id") != xid:
        return {"status": "INVALID", "errors": ["packet does not belong to " + xid]}
    if not isinstance(analysis, dict) or analysis.get("experiment_id") != xid:
        return {"status": "INVALID", "errors": ["analysis does not belong to " + xid]}
    verdict = eo.validate(state, packet, analysis, audit)
    if verdict.get("status") == "PASS":
        return {"status": "READY", "errors": [], "payloads": payloads,
                "packet_path": bundle["packet_path"],
                "analysis_path": bundle["analysis_path"], "audit_path": bundle["audit_path"]}
    if verdict.get("status") == "NEEDS_REVIEW":
        return {"status": "NEEDS_REVIEW",
                "errors": list(verdict.get("unresolved") or []),
                "payloads": payloads}
    return {"status": "INVALID", "errors": list(verdict.get("errors") or [])}


def _outcome_view(state: Dict[str, Any], route_dir: pathlib.Path, route: str,
                  outcome_root: Optional[pathlib.Path]) -> Dict[str, Any]:
    errors = _outcome_errors(state)
    experiments = [item for item in state.get("experiments") or [] if isinstance(item, dict)]
    known = {str(item.get("id")) for item in experiments}
    global_errors = [error for error in errors
                     if not any(error.startswith(xid + ": ") for xid in known)]
    roots: List[pathlib.Path] = []
    if outcome_root is not None:
        roots = [outcome_root]
    else:
        roots = list(dict.fromkeys([
            _project_root(route_dir) / "results" / route,
            route_dir / "results" / route,
            _project_root(route_dir) / "outcome",
            route_dir / "outcome",
        ]))
    bundles: Dict[str, List[Dict[str, Any]]] = {}
    for root in roots:
        for packet_path in _find_outcome_bundles(root):
            bundle = _load_bundle(packet_path)
            packet = bundle["payloads"].get("packet")
            if not isinstance(packet, dict):
                continue
            xid = str(packet.get("experiment_id") or "")
            if xid in known:
                bundles.setdefault(xid, []).append(bundle)
    rows: List[Dict[str, Any]] = []
    for experiment in experiments:
        xid = str(experiment.get("id"))
        status = str(experiment.get("status"))
        row: Dict[str, Any] = {
            "experiment": xid, "status": status,
            "result_locators": _result_locators(route_dir, route, xid, experiment),
        }
        stopped = stopped_execution(experiment)
        if stopped and status in ("planned", "running"):
            row.update(status="STOPPED_NOT_COMPLETION",
                       reason="execution stopped or terminated; this is not scientific completion",
                       boundary=stopped)
            rows.append(row)
            continue
        if status not in ("done", "failed"):
            candidates = bundles.get(xid) or []
            if status == "running" and candidates:
                selected = _bundle_status(state, xid, candidates[0])
                row.update(status=selected["status"],
                           reason="running experiment has a prepared outcome bundle",
                           errors=selected.get("errors", [])[:5])
                if selected["status"] == "READY":
                    row["bundle"] = {
                        "packet": _rel(selected["packet_path"], route_dir),
                        "analysis": _rel(selected["analysis_path"], route_dir),
                        "audit": _rel(selected["audit_path"], route_dir),
                    }
                    row["_payloads"] = selected["payloads"]
                rows.append(row)
                continue
            row.update(status="ACTIVE" if status == "running" else "NOT_TERMINAL",
                       reason="not a terminal experiment; no outcome transaction is due yet")
            rows.append(row)
            continue
        receipt = experiment.get("outcome_analysis")
        if isinstance(receipt, dict):
            own = [error for error in errors if error.startswith(xid + ": ")]
            if own:
                row.update(status="BLOCKED", reason="outcome receipt is invalid or stale",
                           errors=own[:5])
            elif global_errors:
                row.update(status="BLOCKED", reason="outcome receipt is valid but the state has a global gate error",
                           errors=global_errors[:3])
            else:
                row.update(status="COMMITTED", reason="formal outcome transaction is on record")
            rows.append(row)
            continue
        candidates = bundles.get(xid) or []
        if not candidates:
            row.update(status="MISSING",
                       reason="terminal experiment has no outcome transaction and no prepared bundle",
                       errors=[error for error in errors if error.startswith(xid + ": ")][:3])
            rows.append(row)
            continue
        selected = _bundle_status(state, xid, candidates[0])
        row.update(status=selected["status"], reason="prepared outcome bundle inspected",
                   errors=selected.get("errors", [])[:5])
        if selected["status"] == "READY":
            row["bundle"] = {
                "packet": _rel(selected["packet_path"], route_dir),
                "analysis": _rel(selected["analysis_path"], route_dir),
                "audit": _rel(selected["audit_path"], route_dir),
            }
            row["_payloads"] = selected["payloads"]
        rows.append(row)
    return {"experiments": rows, "global_errors": global_errors[:5]}


# ---------------------------------------------------------------------------
# Projection refresh
# ---------------------------------------------------------------------------

def _projection_view(state: Dict[str, Any], state_path: pathlib.Path, route_dir: pathlib.Path,
                     route: str, apply: bool, canonical_ok: bool) -> Dict[str, Any]:
    cognition_dir = cg.cognition_dir_for(state_path)
    result: Dict[str, Any] = {
        "cognition": {"status": "SKIPPED", "reason": "canonical state is invalid"},
        "status": {"status": "SKIPPED", "reason": "canonical state is invalid"},
        "writes": [], "errors": [],
    }
    if not canonical_ok:
        return result
    try:
        check_code, check_output = _capture(cg.op_check, state_path, cognition_dir)
    except (cg.CognitionError, OSError) as exc:
        check_code, check_output = sc.EXIT_HARD, f"{type(exc).__name__}: {exc}"
    cognition = {"status": "CURRENT", "reason": "index and brief match canonical state"}
    if check_code != sc.EXIT_OK:
        cognition = {"status": "STALE", "reason": check_output or "projection is stale"}
        if apply:
            try:
                build_code, build_output = _capture(cg.op_build, state_path, cognition_dir)
            except (cg.CognitionError, OSError) as exc:
                build_code, build_output = sc.EXIT_HARD, f"{type(exc).__name__}: {exc}"
            if build_code != sc.EXIT_OK:
                cognition = {"status": "FAILED", "reason": build_output or "cognition build failed"}
                result["errors"].append("refresh_cognition_projection: " + cognition["reason"])
            else:
                cognition = {"status": "REFRESHED", "reason": "rebuilt from canonical state"}
                result["writes"].extend([
                    _rel(cognition_dir / cg.INDEX_NAME, route_dir),
                    _rel(cognition_dir / cg.BRIEF_NAME, route_dir),
                ])
        else:
            cognition = {"status": "WOULD_REFRESH", "reason": "read-only call: stale projection not written"}
    result["cognition"] = cognition

    status_path, project_root = _human_status_path(route_dir, route)
    rendered = render_status.render(state, route)
    on_disk = None
    if status_path.is_file():
        try:
            on_disk = status_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            on_disk = None
            result["errors"].append(f"read STATUS.md: {type(exc).__name__}: {exc}")
    if on_disk == rendered:
        status = {"status": "CURRENT", "reason": "STATUS.md already matches canonical state"}
    elif apply:
        try:
            _atomic_write_text(status_path, rendered)
            status = {"status": "REFRESHED", "reason": "STATUS.md re-rendered from canonical state"}
            result["writes"].append(_rel(status_path, project_root))
        except OSError as exc:
            status = {"status": "FAILED", "reason": f"{type(exc).__name__}: {exc}"}
            result["errors"].append("refresh_status_projection: " + status["reason"])
    else:
        status = {"status": "WOULD_REFRESH", "reason": "read-only call: stale STATUS.md not written"}
    result["status"] = status
    result["status_path"] = _rel(status_path, project_root)
    return result


# ---------------------------------------------------------------------------
# Main reconciliation
# ---------------------------------------------------------------------------

def reconcile(state_path: pathlib.Path, *, apply: bool = False,
              outcome_root: Optional[pathlib.Path] = None,
              timestamp: Optional[str] = None) -> Dict[str, Any]:
    """Run the reconciliation and return a JSON-serializable report.

    `apply=True` is the caller's existing write authorization. It never grants a new
    scientific permission: a prepared outcome bundle is still validated by the real
    `evidence_outcome.apply()` transaction, and projections are only rebuilt.
    """
    state_path = pathlib.Path(state_path).expanduser().resolve()
    route_dir = state_path.parent
    route = route_dir.name
    report = sc.check_file(state_path)
    if report.error is not None:
        return {
            "_schema": SCHEMA, "status": "BLOCKED", "reason": "state unreadable",
            "error": report.error, "writes": [], "holds": [
                {"code": "state_unreadable", "class": CLASS_EVIDENCE,
                 "detail": report.error}]}
    state = cg.load_state(state_path)
    canonical_ok = report.ok
    canonical = {
        "status": "PASS" if canonical_ok else "FAIL",
        "state_version": state.get("state_version"),
        "summary": report.summary(),
        "violations": _violation_rows(report.shape + report.violations),
        "outcome_violations": _violation_rows(report.outcome),
    }
    scheduler = _scheduler_view(state, route_dir, canonical_ok)
    outcomes = _outcome_view(state, route_dir, route, outcome_root)
    holds: List[Dict[str, Any]] = []
    writes: List[str] = []
    state_changed = False
    maintenance: List[Dict[str, Any]] = []

    if not canonical_ok:
        holds.append({"code": "canonical_state_invalid", "class": CLASS_EVIDENCE,
                      "detail": report.summary()})
    if scheduler["status"] == "STALE":
        holds.append({"code": "stale_scheduler", "class": CLASS_ROUTINE,
                      "detail": scheduler["reason"]})
    elif scheduler["status"] == "FAIL":
        holds.append({"code": "scheduler_gate_failed", "class": CLASS_EVIDENCE,
                      "detail": "; ".join(scheduler.get("errors") or [])[:500]})
    elif scheduler["status"] == "CONFLICT":
        holds.append({"code": "monitor_record_conflict", "class": CLASS_EVIDENCE,
                      "detail": scheduler["reason"]})
    elif scheduler["status"] in ("UNREADABLE", "MISSING"):
        if scheduler["status"] == "UNREADABLE":
            holds.append({"code": "scheduler_unreadable", "class": CLASS_ROUTINE,
                          "detail": scheduler["reason"]})

    ready = [row for row in outcomes["experiments"] if row["status"] == "READY"]
    if apply and ready:
        # One transaction per pass. Applying several would invalidate the base-state digest
        # of the others; a second pass can continue after projections are refreshed.
        target = ready[0]
        payloads = target.pop("_payloads", {})
        result = eo.apply(state, payloads["packet"], payloads["analysis"], payloads["audit"],
                          timestamp=timestamp)
        if result.get("status") == "PASS":
            _atomic_write_json(state_path, result["state"])
            writes.append(_rel(state_path, route_dir))
            state_changed = True
            target.update(status="COMMITTED", reason="prepared transaction applied through R10/R11")
            state = result["state"]
            report = sc.check_state(state)
            canonical_ok = report.ok
            canonical = {
                "status": "PASS" if canonical_ok else "FAIL",
                "state_version": state.get("state_version"),
                "summary": report.summary(),
                "violations": _violation_rows(report.shape + report.violations),
                "outcome_violations": _violation_rows(report.outcome),
            }
            scheduler = _scheduler_view(state, route_dir, canonical_ok)
            outcomes = _outcome_view(state, route_dir, route, outcome_root)
            # Keep the committed row visible in the new outcome view by replacing it.
            for row in outcomes["experiments"]:
                if row["experiment"] == target["experiment"]:
                    row.update(target)
                    break
        elif result.get("status") == "NEEDS_REVIEW":
            target.update(status="BLOCKED", reason="outcome backlog remains unresolved",
                          errors=list(result.get("unresolved") or [])[:5])
            holds.append({"code": "outcome_backlog_unresolved", "class": CLASS_EVIDENCE,
                          "detail": "prepared transaction could not be accepted while other "
                                    "terminal experiments still lack source-grounded analyses"})
        else:
            target.update(status="BLOCKED", reason="prepared transaction failed its gates",
                          errors=list(result.get("errors") or [])[:5])
            holds.append({"code": "outcome_transaction_invalid", "class": CLASS_EVIDENCE,
                          "detail": "; ".join(str(item) for item in
                                              (result.get("errors") or [])[:3])})
    elif ready:
        for row in ready:
            row.update(status="READY", reason="prepared transaction is valid; read-only call did not apply")
        if not apply:
            holds.append({"code": "outcome_transaction_ready", "class": CLASS_EVIDENCE,
                          "detail": "a valid prepared bundle exists; run with --apply only under "
                                    "existing execute authorization"})

    for row in outcomes["experiments"]:
        if row["status"] == "STOPPED_NOT_COMPLETION":
            holds.append({"code": "execution_stopped_not_completion", "class": CLASS_EVIDENCE,
                          "detail": f"{row['experiment']}: {row.get('boundary', '')}",
                          "experiment": row["experiment"]})
        elif row["status"] == "MISSING":
            holds.append({"code": "outcome_transaction_missing", "class": CLASS_EVIDENCE,
                          "detail": f"{row['experiment']}: terminal result has no outcome transaction",
                          "experiment": row["experiment"]})
        elif row["status"] == "BLOCKED":
            holds.append({"code": "outcome_receipt_blocked", "class": CLASS_EVIDENCE,
                          "detail": f"{row['experiment']}: {row.get('reason', '')}",
                          "experiment": row["experiment"]})
        elif row["status"] == "INVALID":
            holds.append({"code": "outcome_transaction_invalid", "class": CLASS_EVIDENCE,
                          "detail": f"{row['experiment']}: prepared bundle failed validation",
                          "experiment": row["experiment"]})
        elif row["status"] == "NEEDS_REVIEW":
            holds.append({"code": "outcome_audit_unknown", "class": CLASS_EVIDENCE,
                          "detail": f"{row['experiment']}: audit or validity is unresolved",
                          "experiment": row["experiment"]})

    projections = _projection_view(state, state_path, route_dir, route, apply, canonical_ok)
    writes.extend(projections["writes"])
    if projections["cognition"]["status"] == "FAILED":
        holds.append({"code": "projection_refresh_failed", "class": CLASS_ROUTINE,
                      "detail": projections["cognition"]["reason"]})
    if projections["status"]["status"] == "FAILED":
        holds.append({"code": "status_render_failed", "class": CLASS_ROUTINE,
                      "detail": projections["status"]["reason"]})

    maintenance.extend([
        {"operation": "refresh_cognition_projection", "class": CLASS_ROUTINE,
         "status": projections["cognition"]["status"], "reason": projections["cognition"]["reason"]},
        {"operation": "refresh_status_projection", "class": CLASS_ROUTINE,
         "status": projections["status"]["status"], "reason": projections["status"]["reason"]},
        {"operation": "check_scheduler_freshness", "class": CLASS_ROUTINE,
         "status": scheduler["status"], "reason": scheduler["reason"]},
        {"operation": "detect_outcome_submission", "class": CLASS_EVIDENCE,
         "status": "CHECKED", "reason": f"{len(outcomes['experiments'])} experiments inspected"},
    ])

    blocking = any(item["code"] in (
        "canonical_state_invalid", "outcome_transaction_invalid", "outcome_receipt_blocked",
        "outcome_backlog_unresolved", "scheduler_gate_failed", "monitor_record_conflict",
    ) for item in holds)
    for row in outcomes["experiments"]:
        row.pop("_payloads", None)
    hold_counts: Dict[str, int] = {}
    for hold in holds:
        code = str(hold.get("code"))
        hold_counts[code] = hold_counts.get(code, 0) + 1
    outcome_counts: Dict[str, int] = {}
    for row in outcomes["experiments"]:
        key = str(row.get("status"))
        outcome_counts[key] = outcome_counts.get(key, 0) + 1
    status = "BLOCKED" if blocking else "HOLD" if holds else "OK"
    return {
        "_schema": SCHEMA,
        "status": status,
        "route": route,
        "state_version": state.get("state_version"),
        "canonical": canonical,
        "scheduler": scheduler,
        "outcomes": outcomes,
        "maintenance": maintenance,
        "holds": holds,
        "hold_counts": hold_counts,
        "outcome_counts": outcome_counts,
        "writes": sorted(set(writes)),
        "state_changed": state_changed,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operational reconciliation for a Research State")
    parser.add_argument("--state", required=True, help="path to research-state.json")
    parser.add_argument("--apply", action="store_true",
                        help="perform routine maintenance and commit validated outcome bundles")
    parser.add_argument("--outcome-root", help="directory to scan for prepared outcome bundles")
    parser.add_argument("--timestamp", help="fixed timestamp for an applied transaction (tests)")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    state_path = pathlib.Path(args.state)
    if not state_path.is_file():
        print(f"[env] state file missing: {state_path}", file=sys.stderr)
        return EXIT_ERROR
    outcome_root = pathlib.Path(args.outcome_root) if args.outcome_root else None
    try:
        payload = reconcile(state_path, apply=args.apply, outcome_root=outcome_root,
                            timestamp=args.timestamp)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"[env] cannot read input: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload["status"] == "BLOCKED":
        return EXIT_BLOCKED
    if payload["status"] == "HOLD":
        return EXIT_HOLD
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
