#!/usr/bin/env python3
"""rsi_test_support.py — shared fixtures for the Skill-RSI test suites.

Not a test module (the discovery pattern is `test_*.py`); imported by the suites that need a
well-formed L3 research-validation credential, whose provenance requirements are deliberately
awkward to satisfy by accident.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any, Dict, Optional

import policy_evolution as pe


def trial_ref(state_path: pathlib.Path, policy_id: str) -> Dict[str, Any]:
    """The stored bounded-trial dispatch record, as a credential reference."""
    for path in pe.trials_dir(state_path).glob(f"{policy_id}.*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("policy_id") == policy_id:
            return {"path": str(path), "digest": payload["digest"]}
    raise AssertionError(f"no trial artifact for {policy_id}")


def real_task(directory: pathlib.Path, *, name: str = "task.json",
              task_id: str = "T1") -> pathlib.Path:
    directory.mkdir(parents=True, exist_ok=True)
    task = directory / name
    task.write_text(json.dumps({"task_id": task_id, "dataset": "real",
                                "synthetic": False}), encoding="utf-8")
    return task


def real_log(directory: pathlib.Path, *, name: str = "run.log") -> pathlib.Path:
    directory.mkdir(parents=True, exist_ok=True)
    log = directory / name
    log.write_text("external harness executed\n", encoding="utf-8")
    return log


def _rows(case_id_prefix, cases, runs, metrics, *, isolation, leak, executor):
    rows = []
    for _ in range(runs):
        for index in range(cases):
            rows.append({"case_id": f"{case_id_prefix}{index}",
                         "evaluation": {"metrics": {name: {"value": value}
                                                    for name, value in metrics.items()}},
                         "isolation_verified": isolation, "leak_checked": leak,
                         "executor": executor})
    return rows


def equivalence(*, policy_arm: str = "policy", control_arm: str = "control",
                task_ids=None, model: str = "model-a", harness: str = "harness-1",
                tools=("runner",), visible_data: str = "sha256:data",
                budget=None, policy_instance: str = "run-policy-1",
                control_instance: str = "run-control-1",
                contrast_axes=("strategy",), axis_overrides=None,
                policy_environment=None, control_environment=None):
    """A reviewable paired-task / budget / environment record for the two arms."""
    task_ids = list(task_ids or [f"T{i}" for i in range(3)])
    budget = budget or {"hours": 4, "runs": 2}
    base = {"model": model, "harness": harness, "tools": list(tools),
            "visible_data": visible_data, "budget": dict(budget),
            "task_ids": list(task_ids)}
    policy_env = dict(base, **(policy_environment or {}))
    control_env = dict(base, **(control_environment or {}))
    if axis_overrides:
        for arm, values in axis_overrides.items():
            target = policy_env if arm == policy_arm else control_env
            target.update(values)
    # the declared contrast must actually differ between the arms
    if "strategy" in contrast_axes:
        policy_env["strategy"] = "policy-intervention"
        control_env["strategy"] = "control-condition"
    return {"controlled_axes": ["model", "harness", "tools", "visible_data", "budget"],
            "contrast_axes": list(contrast_axes),
            "paired_task_ids": list(task_ids),
            "arms": {policy_arm: {"instance": policy_instance, "environment": policy_env},
                     control_arm: {"instance": control_instance, "environment": control_env}}}


def approve(state_path: pathlib.Path, policy_id: str, credential, *,
            approver: str = "external-human-reviewer", confirm_human: bool = True,
            expires_in_seconds: int = 86400, scope_note: str = "round 8 test") -> dict:
    """Append a human approval for this exact credential (the production gate)."""
    import policy_evolution as pe
    return pe.approve_l3(state_path, policy_id=policy_id, credential=credential,
                         approver=approver, confirm_human=confirm_human,
                         scope_note=scope_note, expires_in_seconds=expires_in_seconds)


def research_validation(state_path: pathlib.Path, policy_id: str, workdir: pathlib.Path, *,
                        signature: Optional[str] = None,
                        rules_digest: Optional[str] = None,
                        dimensions=("search_efficiency", "mechanistic_understanding"),
                        benefit_policy: float = 0.9, benefit_control: float = 0.3,
                        science_policy: float = 0.5, science_control: float = 0.5,
                        cases: int = 3, runs: int = 2,
                        executor: str = "external-reviewer-1",
                        control_executor: str = "external-reviewer-2",
                        synthetic: bool = False, isolation: bool = True, leak: bool = True,
                        source: Optional[pathlib.Path] = None,
                        dispatch_ref: Optional[Dict[str, Any]] = None,
                        candidate_arm: str = "policy", control_arm: str = "control",
                        equivalence_record: Optional[Dict[str, Any]] = None,
                        equivalence_off: bool = False) -> Dict[str, Any]:
    """A valid L3 research-validation credential (unless overridden into an invalid one)."""
    benefit, science = dimensions[0], dimensions[-1]
    task = source if source is not None else real_task(workdir)
    log = real_log(workdir)
    source_digest = pe._file_digest(task) if pathlib.Path(task).is_file() else "sha256:missing"
    return {
        "_schema": pe.SCHEMA_RESEARCH_VALIDATION,
        "policy_id": policy_id,
        "policy_signature": signature,
        "rules_digest": rules_digest,
        "candidate_arm": candidate_arm,
        "control_arm": control_arm,
        "task_provenance": {"task_id": "T1", "source": str(task),
                            "source_digest": source_digest, "synthetic": synthetic},
        "execution_evidence": {"path": str(log), "digest": pe._file_digest(log)},
        "dispatch_ref": dispatch_ref if dispatch_ref is not None
        else trial_ref(state_path, policy_id),
        "cases": cases, "runs_per_case": runs,
        "runner": "external research validation harness",
        "equivalence": (equivalence_record if equivalence_record is not None
                        else (None if equivalence_off else equivalence(
                            policy_arm=candidate_arm, control_arm=control_arm,
                            task_ids=[f"T{i}" for i in range(cases)]))),
        "per_arm": {
            candidate_arm: {"executor": executor, "results": _rows(
                "T", cases, runs, {benefit: benefit_policy, science: science_policy},
                isolation=isolation, leak=leak, executor=executor)},
            control_arm: {"executor": control_executor, "results": _rows(
                "T", cases, runs, {benefit: benefit_control, science: science_control},
                isolation=isolation, leak=leak, executor=control_executor)},
        },
    }
