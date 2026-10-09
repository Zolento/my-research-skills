#!/usr/bin/env python3
"""policy_evolution.py — Scoped research policy evolution, evaluation and promotion.

Skill-RSI Phases 4, 5 and 7.

What this module is
-------------------
The existing Strategy Evolution can adjust *strategy memory* (operator priors, menu
re-ordering). What it cannot do is hold a **scoped, auditable policy candidate** with an
explicit applicability boundary, supporting and counter-evidence, a frozen evaluation
rule set, a lifecycle verified by an independent replay, and a rollback path.

This module adds that control record under `<route>/policy/`:

    policy/candidates.jsonl      append-only, hash-chained candidate + transition log
    policy/evaluation-rules.json frozen before the first candidate is generated

It does **not** replace the Strategy Decision Adapter. A promoted policy is consumed by
feeding its advice into the existing `strategy_memory.strategy_decision()` path
(`advice_from_active_policy`), so the hard scheduler priority, the `EIG ÷ cost` rule, the
hard gates, AALG budgets and the Research Contract remain exactly where they were.

Hard boundaries
---------------
* A policy may only touch the authorised strategy surface (exploration-operator
  preference, menu choice, same-tier ordering, applicability, probe order, local
  allocation that keeps the exploration floor). Everything else is refused (`PE2`).
* A candidate may not carry executable content (`PE6`) and free text is never treated as
  an instruction.
* Nothing reaches `ACTIVE` without an independent, leakage-checked, reproducible replay
  evaluation (`PE11`), and the evaluation rules must be unchanged since the candidate was
  generated (`PE12`).
* Rollback restores an earlier valid policy, keeps the failure history, and never resets
  AALG/PEIG counters or the canonical Research State.
* Generating a new policy id does not reset a failure count: the cap is keyed by the
  policy's structural signature (`PE9`), so renaming cannot evade it.

Levels: L1 implementation validity, L2 operational validity, L3 research improvement.
They are recorded separately and never conflated.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import cognition as cg
import decision_trajectory as dt

SCHEMA_CANDIDATE = "research-idea-pipeline/policy-candidate@1"
SCHEMA_TRANSITION = "research-idea-pipeline/policy-transition@1"
SCHEMA_ROLLBACK = "research-idea-pipeline/policy-rollback@1"
SCHEMA_RULES = "research-idea-pipeline/policy-evaluation-rules@1"
POLICY_SCHEMA_VERSION = "1"

EXIT_OK = cg.EXIT_OK
EXIT_ERROR = cg.EXIT_ERROR
EXIT_HARD = cg.EXIT_HARD
EXIT_ENV = cg.EXIT_ENV

POLICY_DIRNAME = "policy"
CANDIDATES_NAME = "candidates.jsonl"
RULES_NAME = "evaluation-rules.json"
STATE_NAME = "state.json"

#: The suggested policy lifecycle. It lives in this control record; it is **not** a new
#: scientific state enum and never appears in `research-state.json`.
LIFECYCLE: Tuple[str, ...] = ("PROPOSED", "SHADOW", "REPLAY_EVALUATED", "BOUNDED_TRIAL",
                              "VALIDATED", "ACTIVE", "SUPERSEDED", "REJECTED", "HOLD",
                              "ROLLED_BACK")
TERMINAL: Tuple[str, ...] = ("SUPERSEDED", "REJECTED", "ROLLED_BACK")

#: Forward path plus the failure exits. Anything else is refused by `PE10`.
ALLOWED_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "PROPOSED": ("SHADOW", "REJECTED", "HOLD"),
    "SHADOW": ("REPLAY_EVALUATED", "REJECTED", "HOLD"),
    "REPLAY_EVALUATED": ("BOUNDED_TRIAL", "VALIDATED", "REJECTED", "HOLD"),
    "BOUNDED_TRIAL": ("VALIDATED", "REJECTED", "HOLD"),
    "VALIDATED": ("ACTIVE", "REJECTED", "HOLD"),
    "ACTIVE": ("ROLLED_BACK", "SUPERSEDED"),
    # A superseded policy may come back only through an explicit restore, which is what
    # `rollback()` writes; that keeps `active_policy_id` and the lifecycle status consistent.
    "SUPERSEDED": ("ACTIVE", "ROLLED_BACK"),
    "HOLD": ("SHADOW", "REPLAY_EVALUATED", "REJECTED", "ROLLED_BACK"),
    "REJECTED": (),
    "ROLLED_BACK": (),
}

#: Evidence an independent evaluation must supply before a candidate may advance.
#: Each entry is (required keys, human description). A missing key blocks the transition.
TRANSITION_REQUIREMENTS: Dict[Tuple[str, str], Dict[str, Any]] = {
    ("PROPOSED", "SHADOW"): {"level": "L1",
                             "keys": ("format_ok", "invariants_ok", "permissions_ok")},
    ("SHADOW", "REPLAY_EVALUATED"): {"level": "L2",
                                     "keys": ("replay_verdict", "leakage_checked", "reproducible",
                                              "independent", "sample_adequate")},
    ("REPLAY_EVALUATED", "BOUNDED_TRIAL"): {"level": "L2",
                                            "keys": ("budget_expanded", "hard_gates_unchanged",
                                                     "dispatch_evidence")},
    ("REPLAY_EVALUATED", "VALIDATED"): {"level": "L3",
                                        "keys": ("independent", "distinguishable",
                                                 "degraded_dimensions")},
    ("BOUNDED_TRIAL", "VALIDATED"): {"level": "L3",
                                     "keys": ("independent", "distinguishable",
                                              "degraded_dimensions")},
    ("VALIDATED", "ACTIVE"): {"level": "L3",
                              "keys": ("rules_digest_unchanged", "scope_evidence_ok")},
    # A restore re-activates an already-promoted policy; it still requires a recorded reason.
    ("SUPERSEDED", "ACTIVE"): {"level": "L2", "keys": ("reason",)},
}

#: The authorised strategy surface. A change outside it is `PE2`.
CHANGE_KINDS: Dict[str, Dict[str, Any]] = {
    "exploration_operator_preference": {"required": ("operator",)},
    "menu_choice": {"required": ("menu",)},
    "same_tier_preference": {"required": ("prefer_action",)},
    "same_tier_order": {"required": ("order",)},
    "applicability": {"required": ("problem_structure",)},
    "probe_order": {"required": ("order",)},
    "local_resource_allocation": {"required": ("allocation",), "keep_exploration_floor": True},
}

#: Change kinds the Strategy Decision Adapter can actually consume. A policy made only of
#: advisory kinds (resource allocation) is accepted data but can never change a decision, so
#: it must not be promotable on its own — otherwise "the policy is ACTIVE" would be a lie.
CONSUMABLE_CHANGE_KINDS: Tuple[str, ...] = (
    "exploration_operator_preference", "menu_choice", "same_tier_preference",
    "same_tier_order", "probe_order", "applicability",
)

#: Targets a policy may never touch, whatever shape the attempt takes.
FORBIDDEN_TARGETS: Tuple[str, ...] = (
    "scheduler_priority", "next_action_policy", "priority", "eig_rule", "eig_cost",
    "cost_rule", "execution_gate", "evidence_qualification", "aalg", "peig",
    "diagnostic_budget", "research_contract", "primary_anchor", "anchor", "gpu_authorization",
    "gpu", "frozen_plan", "preregistration", "evaluation_criteria", "evaluation_rules",
    "scoring", "promotion_threshold", "skill_source", "SKILL.md", "shared-contract.md",
    "preset-registry.json", "presets/", "references/", "templates/", "schemas/", "scripts/",
)

#: A policy is structured data. These patterns mean someone is trying to ship code.
#: The traversal pattern is `\.\./` (a literal dot-dot), not `../`: the unescaped form was a
#: wildcard that matched any two characters followed by a slash, so ordinary prose such as
#: "ratio 3/4" or "see appendix / section 3" was rejected as a path-traversal attempt.
EXECUTABLE_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"`", "反引号（命令替换）"),
    (r"\$\(", "shell 命令替换"),
    (r"&&|\|\|", "shell 连接符"),
    (r";\s*(?:\w+\s+){0,3}(?:rm|curl|wget|chmod|chown|python|bash|sh|sudo)\b",
     "shell 语句分隔后接命令"),
    (r"\bimport\s+\w", "Python import"),
    (r"\b__import__\b", "Python 动态导入"),
    (r"\bexec\s*\(", "exec"),
    (r"\beval\s*\(", "eval"),
    (r"\bos\.system\b", "os.system"),
    (r"\bsubprocess\b", "subprocess"),
    (r"\bshutil\.rmtree\b", "shutil.rmtree"),
    (r"\.\./", "路径穿越"),
    (r"^\s*/", "绝对路径"),
    (r"\bcurl\b|\bwget\b", "网络下载"),
    (r"\bchmod\b|\bchown\b", "权限修改"),
)

#: Complexity regularisation (RRSI flavour): prefer one small mechanism at a time.
MAX_CHANGES_PER_CANDIDATE = 2
MAX_OPEN_CANDIDATES = 5
MAX_CANDIDATES_PER_SIGNATURE = 3
MAX_FAILURES_PER_SIGNATURE = 2

#: A candidate may never be over-fitted to a fixed fixture.
FIXTURE_PATTERN = re.compile(r"\b(adv\d+|fixture[_-]?\d*|synthetic[_-]?\d+)\b", re.IGNORECASE)

DEFAULT_NO_DEGRADATION: Tuple[str, ...] = ("scientific_evidence", "evidence_qualification")

SCALAR = (str, int, float, bool)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def policy_dir(state_path: Path) -> Path:
    return Path(state_path).resolve().parent / POLICY_DIRNAME


def candidates_path(state_path: Path) -> Path:
    return policy_dir(state_path) / CANDIDATES_NAME


def rules_path(state_path: Path) -> Path:
    return policy_dir(state_path) / RULES_NAME


def state_snapshot_path(state_path: Path) -> Path:
    return policy_dir(state_path) / STATE_NAME


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return dt._now()


def _diag(rule: str, path: str, message: str) -> cg.Diagnostic:
    return cg.Diagnostic(rule, path, message)


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def candidate_signature(candidate: Dict[str, Any]) -> str:
    """Structural identity used for duplicate-failure caps.

    Renaming a policy id must not reset the failure count, so the cap keys on the
    *mechanism* (scope plus normalised change set), not on the id.
    """
    scope = candidate.get("scope") if isinstance(candidate.get("scope"), dict) else {}
    changes = []
    for change in candidate.get("strategy_changes") or []:
        if not isinstance(change, dict):
            continue
        changes.append({key: change.get(key) for key in sorted(change)
                        if key not in ("rationale", "note")})
    payload = {"problem_structure": scope.get("problem_structure"),
               "scope_kind": scope.get("scope_kind"),
               "changes": sorted(json.dumps(item, sort_keys=True, ensure_ascii=False)
                                 for item in changes)}
    return "PS-" + cg.digest_of(payload)[:20]


# ---------------------------------------------------------------------------
# Evaluation rule freezing
# ---------------------------------------------------------------------------

DEFAULT_EVALUATION_RULES: Dict[str, Any] = {
    "dimensions": ["mechanistic_understanding", "prediction_quality", "intervention_quality",
                   "scientific_novelty", "search_efficiency", "stagnation_recovery",
                   "memory_accumulation"],
    "no_composite_total": True,
    "min_cases": 3,
    "min_runs": 2,
    "delta_tolerance": 0.05,
    "require_independent_arm": True,
    "require_no_support_excluded": True,
    "authority": "frozen_before_candidate_generation",
}


def freeze_evaluation_rules(state_path: Path,
                            rules: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Freeze the evaluation rule set once. A later candidate cannot rewrite it."""
    import os
    path = rules_path(state_path)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        return {"status": "ALREADY_FROZEN", "path": str(path),
                "digest": existing.get("digest"), "rules": existing.get("rules")}
    payload = copy.deepcopy(rules) if rules is not None else copy.deepcopy(DEFAULT_EVALUATION_RULES)
    document = {"_schema": SCHEMA_RULES, "frozen_at": _now(), "rules": payload,
                "digest": cg.digest_of(payload)}
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    pending.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    os.replace(pending, path)
    return {"status": "FROZEN", "path": str(path), "digest": document["digest"],
            "rules": payload}


def evaluation_rules_digest(state_path: Path) -> Optional[str]:
    path = rules_path(state_path)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("digest")


# ---------------------------------------------------------------------------
# Candidate validation
# ---------------------------------------------------------------------------

def _executable_errors(value: Any, path: str) -> List[cg.Diagnostic]:
    diagnostics: List[cg.Diagnostic] = []
    for text in _walk_strings(value):
        stripped = text.strip()
        if not stripped or len(stripped) > 400:
            continue
        for pattern, label in EXECUTABLE_PATTERNS:
            if re.search(pattern, stripped):
                diagnostics.append(_diag("PE6", path,
                                         f"策略数据不得包含可执行内容（{label}）：{stripped[:60]!r}"))
                break
    return diagnostics


def _forbidden_target_errors(candidate: Dict[str, Any], path: str) -> List[cg.Diagnostic]:
    diagnostics: List[cg.Diagnostic] = []
    for change in candidate.get("strategy_changes") or []:
        if not isinstance(change, dict):
            continue
        target = str(change.get("target") or change.get("kind") or "")
        for forbidden in FORBIDDEN_TARGETS:
            if forbidden.lower() in target.lower():
                diagnostics.append(_diag("PE2", path,
                                         f"策略不得修改 {forbidden}（越权目标 {target!r}）"))
    return diagnostics


def overfit_flags(candidate: Dict[str, Any]) -> List[str]:
    """A policy fitted to a fixed fixture may never be promoted past SHADOW."""
    flagged: List[str] = []
    for text in _walk_strings({"scope": candidate.get("scope"),
                               "applicable_conditions": candidate.get("applicable_conditions")}):
        if FIXTURE_PATTERN.search(text):
            flagged.append(f"scope/applicability 引用固定 fixture：{text[:60]!r}")
    return flagged


def candidate_errors(candidate: Any, *, records: Sequence[Dict[str, Any]] = (),
                     trajectory_support: Optional[Iterable[str]] = None,
                     rules_digest: Optional[str] = None) -> List[cg.Diagnostic]:
    """Validate a candidate and its operational boundary. Empty list means proposable."""
    diagnostics: List[cg.Diagnostic] = []
    if not isinstance(candidate, dict):
        return [_diag("PE1", "candidate", "策略候选必须是对象")]
    ident = str(candidate.get("policy_id") or "?")
    path = f"policy[{ident}]"

    for required in ("policy_id", "policy_schema_version", "status", "scope",
                     "applicable_conditions", "strategy_changes", "supporting_trajectory_ids",
                     "counterexamples", "expected_effect", "revalidation_conditions",
                     "rollback_target"):
        if required not in candidate:
            diagnostics.append(_diag("PE1", path, f"缺少必需字段 {required}"))
    if diagnostics:
        return cg._dedupe(diagnostics)
    if candidate.get("policy_schema_version") != POLICY_SCHEMA_VERSION:
        diagnostics.append(_diag("PE1", path,
                                 f"policy_schema_version 必须是 {POLICY_SCHEMA_VERSION!r}"))
    if candidate.get("status") not in LIFECYCLE:
        diagnostics.append(_diag("PE1", path, f"未知状态 {candidate.get('status')!r}"))

    # --- authorised change surface -------------------------------------------
    changes = candidate.get("strategy_changes")
    if not isinstance(changes, list) or not changes:
        diagnostics.append(_diag("PE1", path, "strategy_changes 必须是非空数组"))
    else:
        if len(changes) > MAX_CHANGES_PER_CANDIDATE:
            diagnostics.append(_diag(
                "PE5", path,
                f"一次最多修改 {MAX_CHANGES_PER_CANDIDATE} 个机制（RRSI 正则化）："
                f"收到 {len(changes)}"))
        for index, change in enumerate(changes):
            cpath = f"{path}.strategy_changes[{index}]"
            if not isinstance(change, dict):
                diagnostics.append(_diag("PE1", cpath, "变更项必须是对象"))
                continue
            kind = str(change.get("kind") or "")
            spec = CHANGE_KINDS.get(kind)
            if spec is None:
                diagnostics.append(_diag("PE2", cpath,
                                         f"未授权的策略面 {kind!r}；允许 {sorted(CHANGE_KINDS)}"))
                continue
            for key in spec["required"]:
                value = change.get(key)
                if value in (None, "", [], {}):
                    diagnostics.append(_diag("PE1", cpath, f"{kind} 需要 {key}"))
            if spec.get("keep_exploration_floor"):
                allocation = change.get("allocation")
                if not isinstance(allocation, dict) or \
                        allocation.get("keep_exploration_floor") is not True:
                    diagnostics.append(_diag(
                        "PE2", cpath,
                        "局部资源分配必须保留探索下限（keep_exploration_floor=true），"
                        "不得永久封禁失败算子"))
            if kind == "menu_choice":
                try:
                    import strategy_memory as sm
                    if change.get("menu") not in sm.MENU_BY_NAME:
                        diagnostics.append(_diag("PE2", cpath,
                                                 f"未知菜单 {change.get('menu')!r}"))
                except Exception:  # pragma: no cover - strategy memory always importable
                    pass
            if kind == "same_tier_order":
                order = change.get("order")
                if not isinstance(order, list) or not all(isinstance(item, str) and item
                                                          for item in order):
                    diagnostics.append(_diag("PE1", cpath,
                                             "same_tier_order.order 必须是非空字符串数组"))
            if kind == "probe_order":
                order = change.get("order")
                if not isinstance(order, list) or not all(isinstance(item, str) and item
                                                          for item in order):
                    diagnostics.append(_diag("PE1", cpath,
                                             "probe_order.order 必须是非空字符串数组"))
            if kind == "exploration_operator_preference":
                try:
                    import state_check as sc
                    if change.get("operator") not in sc.OPERATORS:
                        diagnostics.append(_diag("PE2", cpath,
                                                 f"未知算子 {change.get('operator')!r}"))
                except Exception:  # pragma: no cover
                    pass
    diagnostics += _forbidden_target_errors(candidate, path)

    # A policy must be able to change a decision. Advisory-only changes (resource allocation)
    # may accompany a consumable one but may not be the whole policy, otherwise a promoted
    # policy could never have a real consumer.
    if isinstance(changes, list) and changes and \
            not any(isinstance(item, dict) and item.get("kind") in CONSUMABLE_CHANGE_KINDS
                    for item in changes):
        diagnostics.append(_diag(
            "PE2", path,
            "策略至少需要一个可被 Strategy Decision Adapter 消费的变更类型"
            f"（{sorted(CONSUMABLE_CHANGE_KINDS)}）；只有建议性变更的策略没有消费者"))

    # --- operational boundary -------------------------------------------------
    scope = candidate.get("scope")
    if not isinstance(scope, dict) or not scope:
        diagnostics.append(_diag("PE3", path, "scope 必须是结构化对象（作用域不得为全局口号）"))
    else:
        if scope.get("scope_kind") not in ("local", "project", "global"):
            diagnostics.append(_diag("PE3", path,
                                     "scope.scope_kind 必须是 local/project/global"))
        if not scope.get("problem_structure"):
            diagnostics.append(_diag("PE3", path, "scope.problem_structure 缺失"))
    if not isinstance(candidate.get("applicable_conditions"), list) or \
            not candidate.get("applicable_conditions"):
        diagnostics.append(_diag("PE3", path, "applicable_conditions 必须是非空数组"))
    if not isinstance(candidate.get("revalidation_conditions"), list) or \
            not candidate.get("revalidation_conditions"):
        diagnostics.append(_diag("PE3", path, "revalidation_conditions 必须是非空数组"))

    counterexamples = candidate.get("counterexamples")
    if not isinstance(counterexamples, list):
        diagnostics.append(_diag("PE1", path, "counterexamples 必须是数组"))
    elif isinstance(scope, dict) and scope.get("scope_kind") in ("project", "global") and \
            not counterexamples:
        diagnostics.append(_diag("PE8", path,
                                 "project/global 作用域必须记录反例；没有反例的泛化不可信"))

    effect = candidate.get("expected_effect")
    if not isinstance(effect, dict) or not effect.get("mechanism") or not effect.get("direction"):
        diagnostics.append(_diag("PE3", path,
                                 "expected_effect 必须写明 mechanism 与 direction"
                                 "（不能只有一句“这个策略更科学”）"))

    support = candidate.get("supporting_trajectory_ids")
    if not isinstance(support, list) or not support:
        diagnostics.append(_diag("PE4", path, "supporting_trajectory_ids 必须是非空数组"))
    elif trajectory_support is not None:
        known = set(trajectory_support)
        for ident_ref in support:
            if str(ident_ref) not in known:
                diagnostics.append(_diag("PE4", path,
                                         f"轨迹 {ident_ref} 不存在或没有真实结果（不可作为依据）"))

    rollback = candidate.get("rollback_target")
    if rollback not in (None, ""):
        if not isinstance(rollback, str):
            diagnostics.append(_diag("PE1", path, "rollback_target 必须是字符串或 null"))
        elif records and rollback not in {str(item.get("policy_id")) for item in records}:
            diagnostics.append(_diag("PE13", path, f"rollback_target {rollback!r} 不存在"))
    parent = candidate.get("parent_policy_id")
    if parent not in (None, "") and records and \
            parent not in {str(item.get("policy_id")) for item in records}:
        diagnostics.append(_diag("PE1", path, f"parent_policy_id {parent!r} 不存在"))

    if rules_digest is not None:
        declared = candidate.get("evaluation_rules_digest")
        # A candidate that declares the rule set it was generated under must match it. A
        # candidate that declares nothing is stamped with the current rules at proposal time.
        if declared is not None and declared != rules_digest:
            diagnostics.append(_diag("PE12", path,
                                     "候选生成后评价规则被改动：评价结果不可信"))

    # --- complexity / anti-evasion -------------------------------------------
    signature = candidate_signature(candidate)
    failures = [item for item in records
                if item.get("record") == "transition" and item.get("to") in ("REJECTED",
                                                                             "ROLLED_BACK")
                and item.get("signature") == signature]
    if len(failures) >= MAX_FAILURES_PER_SIGNATURE:
        diagnostics.append(_diag(
            "PE9", path,
            f"同一策略机制（签名 {signature}）已失败 {len(failures)} 次："
            "不得靠新 policy_id 重复提出同一方案"))
    same_signature = [item for item in records
                      if item.get("record") == "candidate"
                      and item.get("signature") == signature]
    if len(same_signature) >= MAX_CANDIDATES_PER_SIGNATURE:
        diagnostics.append(_diag("PE5", path,
                                 f"同一签名候选已达上限 {MAX_CANDIDATES_PER_SIGNATURE}"))

    # --- no executable content / no self-assessment ---------------------------
    diagnostics += _executable_errors(candidate, path)
    for banned in ("novelty_self_rating", "self_assessment", "confidence_score", "effect_size"):
        if banned in candidate:
            diagnostics.append(_diag("PE7", path, f"策略候选不得携带自评字段 {banned!r}"))
    return cg._dedupe(diagnostics)


# ---------------------------------------------------------------------------
# Store operations
# ---------------------------------------------------------------------------

def load_records(state_path: Path, *, tolerant: bool = False
                 ) -> Tuple[List[Dict[str, Any]], List[cg.Diagnostic]]:
    return dt.load_chained(candidates_path(state_path), tolerant=tolerant)


def _append(state_path: Path, record: Dict[str, Any]) -> Dict[str, Any]:
    return dt.append_chained(candidates_path(state_path), record)


def propose(state_path: Path, candidate: Dict[str, Any], *,
            trajectory_support: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Append a candidate, refusing validation failures and duplicate-open limits."""
    records, _ = load_records(state_path)
    rules_digest = evaluation_rules_digest(state_path)
    diagnostics = candidate_errors(candidate, records=records,
                                   trajectory_support=trajectory_support,
                                   rules_digest=rules_digest)
    open_ids = {item.get("policy_id") for item in records if item.get("record") == "candidate"}
    latest = latest_status(records)
    open_count = sum(1 for ident in open_ids if latest.get(ident) not in TERMINAL)
    if open_count >= MAX_OPEN_CANDIDATES:
        diagnostics.append(_diag("PE5", f"policy[{candidate.get('policy_id')}]",
                                 f"未结候选已达上限 {MAX_OPEN_CANDIDATES}：先评价或拒绝"))
    ident = candidate.get("policy_id")
    if ident in open_ids:
        diagnostics.append(_diag("PE1", f"policy[{ident}]", "policy_id 已存在（不可覆盖历史）"))
    if diagnostics:
        return {"status": "INVALID", "written": False,
                "diagnostics": [item.render() for item in diagnostics],
                "codes": sorted({item.rule for item in diagnostics})}
    record = copy.deepcopy(candidate)
    record.update({"_schema": SCHEMA_CANDIDATE, "record": "candidate",
                   "recorded_at": _now(), "signature": candidate_signature(candidate),
                   "evaluation_rules_digest": rules_digest,
                   "schema_version": POLICY_SCHEMA_VERSION})
    # Stamp the origin so a later cross-project application is verifiable instead of
    # unprovable; the transfer gate blocks a candidate whose provenance is missing.
    record.setdefault("source_route", cg.route_of(Path(state_path)))
    stored = _append(state_path, record)
    return {"status": "PROPOSED", "written": True, "policy_id": ident,
            "signature": stored["signature"], "seq": stored["seq"],
            "digest": dt._digest(stored), "diagnostics": []}


def latest_status(records: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    """Current status of every candidate, rebuilt from the append-only log."""
    status: Dict[str, str] = {}
    for record in records:
        ident = record.get("policy_id")
        if not isinstance(ident, str):
            continue
        if record.get("record") == "candidate":
            status[ident] = str(record.get("status") or "PROPOSED")
        elif record.get("record") == "transition":
            status[ident] = str(record.get("to"))
    return status


def rebuild_state(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Deterministically fold the log into a snapshot (never a second source of truth)."""
    statuses = latest_status(records)
    history: Dict[str, List[Dict[str, Any]]] = {}
    failed: Dict[str, int] = {}
    for record in records:
        ident = record.get("policy_id")
        if isinstance(ident, str) and record.get("record") == "transition":
            history.setdefault(ident, []).append({"from": record.get("from"),
                                                  "to": record.get("to"),
                                                  "at": record.get("at"),
                                                  "level": record.get("level"),
                                                  "reason": record.get("reason")})
            if record.get("to") in ("REJECTED", "ROLLED_BACK"):
                signature = str(record.get("signature") or "")
                failed[signature] = failed.get(signature, 0) + 1
    active = None
    for record in records:
        if record.get("record") == "transition" and record.get("to") == "ACTIVE":
            active = record.get("policy_id")
        elif record.get("record") == "rollback":
            active = record.get("to_policy_id")
    return {"schema": "research-idea-pipeline/policy-state@1",
            "count": len(statuses), "status": statuses, "history": history,
            "active_policy_id": active, "failures_by_signature": failed,
            "terminal": sorted(item for item, value in statuses.items() if value in TERMINAL)}


def active_policy(records: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The policy currently in force, or None.

    The pointer and the lifecycle status are both required to say `ACTIVE`: a pointer to a
    `SUPERSEDED`, `REJECTED` or `ROLLED_BACK` candidate must never be consumed as if it were
    in force.
    """
    snapshot = rebuild_state(records)
    ident = snapshot.get("active_policy_id")
    if not ident:
        return None
    if latest_status(records).get(ident) != "ACTIVE":
        return None
    for record in records:
        if record.get("record") == "candidate" and record.get("policy_id") == ident:
            return record
    return None


def policy_record(records: Sequence[Dict[str, Any]], policy_id: str) -> Optional[Dict[str, Any]]:
    found = None
    for record in records:
        if record.get("record") == "candidate" and record.get("policy_id") == policy_id:
            found = record
    return found


def write_snapshot(state_path: Path, records: Sequence[Dict[str, Any]]) -> Path:
    import os
    path = state_snapshot_path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    pending.write_text(json.dumps(rebuild_state(records), ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    os.replace(pending, path)
    return path


# ---------------------------------------------------------------------------
# Transitions, evaluation gates, rollback
# ---------------------------------------------------------------------------

def transition_errors(records: Sequence[Dict[str, Any]], policy_id: str, target: str,
                      evidence: Dict[str, Any]) -> List[cg.Diagnostic]:
    diagnostics: List[cg.Diagnostic] = []
    statuses = latest_status(records)
    current = statuses.get(policy_id)
    path = f"policy[{policy_id}]"
    if current is None:
        return [_diag("PE1", path, "未知 policy_id")]
    if target not in LIFECYCLE:
        return [_diag("PE1", path, f"未知目标状态 {target!r}")]
    if target not in ALLOWED_TRANSITIONS.get(current, ()):
        diagnostics.append(_diag("PE10", path, f"非法状态转移 {current} → {target}"))
        return diagnostics
    requirement = TRANSITION_REQUIREMENTS.get((current, target))
    if requirement:
        missing = [key for key in requirement["keys"] if key not in evidence]
        if missing:
            diagnostics.append(_diag("PE11", path,
                                     f"{current} → {target} 需要独立评价证据 {missing}"))
        else:
            if evidence.get("independent") is False and "independent" in requirement["keys"]:
                diagnostics.append(_diag("PE11", path, "晋升需要独立评价，不得自评"))
            if evidence.get("leakage_checked") is False:
                diagnostics.append(_diag("PE11", path, "未通过泄漏隔离检查，不得晋升"))
            if evidence.get("reproducible") is False:
                diagnostics.append(_diag("PE11", path, "评价结果不可重现，不得晋升"))
            if evidence.get("sample_adequate") is False:
                diagnostics.append(_diag("PE11", path, "样本不足，不得晋升"))
            if evidence.get("distinguishable") is False:
                diagnostics.append(_diag("PE11", path,
                                         "策略效应与对照无法区分：报告不可区分，不得选胜者"))
            degraded = evidence.get("degraded_dimensions") or []
            if degraded:
                diagnostics.append(_diag("PE11", path,
                                         f"科学完整性维度退化 {degraded}：不得晋升"))
            if current in ("REPLAY_EVALUATED", "BOUNDED_TRIAL") and \
                    target in ("BOUNDED_TRIAL", "VALIDATED") and evidence.get("budget_expanded"):
                diagnostics.append(_diag("PE11", path, "试运行不得扩大原有资源预算"))
            if evidence.get("hard_gates_unchanged") is False:
                diagnostics.append(_diag("PE11", path, "试运行不得改变硬门禁"))
            if current == "VALIDATED" and target == "ACTIVE":
                if evidence.get("rules_digest_unchanged") is False:
                    diagnostics.append(_diag("PE12", path, "评价规则已改变，晋升失效"))
                if evidence.get("scope_evidence_ok") is False:
                    diagnostics.append(_diag("PE14", path, "作用域超出证据支持范围"))
    candidate = policy_record(records, policy_id) or {}
    scope = candidate.get("scope") if isinstance(candidate.get("scope"), dict) else {}
    if target == "ACTIVE" and scope.get("scope_kind") == "global":
        refs = candidate.get("evaluation_refs") or []
        projects = {str(item.get("project")) for item in refs
                    if isinstance(item, dict) and item.get("project")}
        if len(projects) < 2:
            diagnostics.append(_diag("PE14", path,
                                     "global 作用域需要跨项目独立证据（≥2 个项目）："
                                     "局部成功不得自动升级为全局策略"))
    if target in ("REJECTED", "ROLLED_BACK", "HOLD") and not evidence.get("reason"):
        diagnostics.append(_diag("PE10", path, f"{target} 必须写明 reason"))
    if target in ("SHADOW", "REPLAY_EVALUATED", "BOUNDED_TRIAL", "VALIDATED", "ACTIVE"):
        overfit = overfit_flags(candidate)
        if overfit and target not in ("SHADOW",):
            diagnostics.append(_diag("PE5", path,
                                     "针对固定 fixture 的策略不得越过 SHADOW：" + "；".join(overfit)))
    return cg._dedupe(diagnostics)


def transition(state_path: Path, policy_id: str, target: str, *,
               level: str = "L1", evidence: Optional[Dict[str, Any]] = None,
               reason: str = "") -> Dict[str, Any]:
    records, _ = load_records(state_path)
    evidence = dict(evidence or {})
    if reason:
        evidence.setdefault("reason", reason)
    diagnostics = transition_errors(records, policy_id, target, evidence)
    if diagnostics:
        return {"status": "INVALID", "written": False,
                "diagnostics": [item.render() for item in diagnostics],
                "codes": sorted({item.rule for item in diagnostics})}
    candidate = policy_record(records, policy_id) or {}
    previous_active = rebuild_state(records).get("active_policy_id")
    record = {"_schema": SCHEMA_TRANSITION, "record": "transition", "policy_id": policy_id,
              "from": latest_status(records).get(policy_id), "to": target,
              "at": _now(), "level": level, "evidence": evidence, "reason": reason,
              "signature": candidate.get("signature")}
    stored = _append(state_path, record)
    if target == "ACTIVE" and previous_active and previous_active != policy_id:
        _append(state_path, {"_schema": SCHEMA_TRANSITION, "record": "transition",
                             "policy_id": previous_active, "from": "ACTIVE", "to": "SUPERSEDED",
                             "at": _now(), "level": "L2",
                             "evidence": {"reason": f"superseded by {policy_id}"},
                             "reason": f"superseded by {policy_id}",
                             "signature": (policy_record(records, previous_active) or {})
                             .get("signature")})
    if target == "ACTIVE":
        candidate = dict(candidate)
        candidate.setdefault("rollback_target", previous_active)
        _append(state_path, {"_schema": SCHEMA_CANDIDATE, "record": "candidate_snapshot",
                             "at": _now(), "policy_id": policy_id,
                             "rollback_target": previous_active})
    return {"status": target, "written": True, "policy_id": policy_id,
            "seq": stored["seq"], "reason": reason, "diagnostics": []}


def rollback(state_path: Path, policy_id: str, *, to_policy_id: str, reason: str) -> Dict[str, Any]:
    """Restore an earlier valid policy; keep the failure trail; touch nothing else.

    The target must currently be a *restorable* policy (`SUPERSEDED` or still `ACTIVE`).
    A `REJECTED` or already `ROLLED_BACK` policy is terminal and must not be restored —
    otherwise "防止同一失败策略重复晋升" would be violated by the rollback path itself.
    The restore is written as an explicit `→ ACTIVE` transition so the pointer and the
    lifecycle status can never disagree.
    """
    records, _ = load_records(state_path)
    statuses = latest_status(records)
    diagnostics: List[cg.Diagnostic] = []
    if statuses.get(policy_id) != "ACTIVE":
        diagnostics.append(_diag("PE13", f"policy[{policy_id}]", "只有 ACTIVE 策略可以回滚"))
    target_record = policy_record(records, to_policy_id)
    target_status = statuses.get(to_policy_id)
    if target_record is None:
        diagnostics.append(_diag("PE13", f"policy[{to_policy_id}]", "回滚目标不存在"))
    elif target_status not in ("SUPERSEDED", "ACTIVE"):
        diagnostics.append(_diag(
            "PE13", f"policy[{to_policy_id}]",
            f"回滚目标当前状态是 {target_status}：REJECTED / ROLLED_BACK 是终态，不得恢复"))
    if to_policy_id and to_policy_id == policy_id:
        diagnostics.append(_diag("PE13", f"policy[{policy_id}]",
                                 "回滚目标不能是策略自身"))
    if not reason:
        diagnostics.append(_diag("PE10", f"policy[{policy_id}]", "回滚必须写明原因"))
    if diagnostics:
        return {"status": "INVALID", "written": False,
                "diagnostics": [item.render() for item in diagnostics],
                "codes": sorted({item.rule for item in diagnostics})}
    record = {"_schema": SCHEMA_ROLLBACK, "record": "rollback", "policy_id": policy_id,
              "to_policy_id": to_policy_id, "at": _now(), "reason": reason,
              "signature": (policy_record(records, policy_id) or {}).get("signature")}
    stored = _append(state_path, record)
    _append(state_path, {"_schema": SCHEMA_TRANSITION, "record": "transition",
                         "policy_id": policy_id, "from": "ACTIVE", "to": "ROLLED_BACK",
                         "at": _now(), "level": "L2",
                         "evidence": {"reason": reason}, "reason": reason,
                         "signature": record["signature"]})
    if target_status == "SUPERSEDED":
        restore = transition(state_path, to_policy_id, "ACTIVE", level="L2",
                             evidence={"reason": f"restored by rollback from {policy_id}",
                                       "restored": True})
        if not restore.get("written"):
            return {"status": "INVALID", "written": False,
                    "diagnostics": restore.get("diagnostics") or [],
                    "codes": restore.get("codes") or ["PE13"]}
    return {"status": "ROLLED_BACK", "written": True, "policy_id": policy_id,
            "restored": to_policy_id, "seq": stored["seq"], "reason": reason,
            "note": ("回滚不修改既有实验结果、不重置 AALG/其他预算、"
                     "不改 canonical Research State；失败轨迹保留")}


# ---------------------------------------------------------------------------
# Independent evaluation
# ---------------------------------------------------------------------------

def distinguishable(report: Dict[str, Any], arm_a: str, arm_b: str,
                    dimension: Optional[str] = None) -> Dict[str, Any]:
    """Whether two arms differ beyond the frozen tolerance, per dimension.

    Small differences are reported as indistinguishable rather than forced into a winner.
    """
    tolerance = float(DEFAULT_EVALUATION_RULES["delta_tolerance"])
    per_arm = report.get("per_arm") or {}
    if arm_a not in per_arm or arm_b not in per_arm:
        return {"distinguishable": False, "reason": "缺少对照臂", "dimensions": {}}
    dims = [dimension] if dimension else list(
        (per_arm[arm_a].get("dimensions") or {}).keys())
    result: Dict[str, Any] = {}
    any_different = False
    for name in dims:
        a = (per_arm[arm_a]["dimensions"].get(name) or {})
        b = (per_arm[arm_b]["dimensions"].get(name) or {})
        if a.get("mean") is None or b.get("mean") is None:
            result[name] = {"status": "UNASSESSABLE"}
            continue
        delta = round(a["mean"] - b["mean"], 4)
        overlapping = bool(a.get("min") is not None and b.get("max") is not None
                           and not (a["min"] > b["max"] or b["min"] > a["max"]))
        # A *small* difference is reported as indistinguishable; the frozen tolerance, not the
        # spread, is the decision rule. Range overlap is kept as an explicit confidence caveat
        # so a wide but real shift is not silently rounded up to a confident win.
        different = abs(delta) > tolerance
        any_different = any_different or different
        block = {"delta": delta, "overlapping": overlapping,
                 "status": "DISTINGUISHABLE" if different else "UNDIFFERENTIATED"}
        if different and overlapping:
            block["caveat"] = ("均值差异超过容差，但两臂区间重叠：样本量偏小，"
                               "按不可区分处理为证据不足")
        result[name] = block
    return {"distinguishable": any_different, "dimensions": result,
            "reason": ("至少一个维度差异超过容差" if any_different
                       else "各维度差异在容差内：报告不可区分，不选胜者")}


def ablation_verdict(report: Dict[str, Any], *, candidate_arm: str = "rsi_full",
                     control_arm: str = "full_cie") -> Dict[str, Any]:
    """Turn a replay ablation report into promotion evidence. Never a composite score."""
    dimensions = report.get("delta_vs_baseline")
    if dimensions is None:
        return {"verdict": "INVALID", "reasons": ["不是 ablation 报告"]}
    comparison = distinguishable(report, candidate_arm, control_arm)
    degraded = [name for name, block in comparison["dimensions"].items()
                if block.get("status") == "DISTINGUISHABLE" and block.get("delta", 0) < 0]
    scientific_guard = {"scientific_novelty", "prediction_quality", "intervention_quality"}
    integrity_degraded = sorted(set(degraded) & scientific_guard)
    unobservable = int(report.get("unobservable_decisions") or 0)
    reasons: List[str] = []
    verdict = "SUPPORTED"
    if not report.get("sufficient_sample"):
        verdict = "INSUFFICIENT_SAMPLE"
        reasons.append("样本不足：不得宣称策略提升")
    if not comparison["distinguishable"]:
        verdict = "UNDIFFERENTIATED"
        reasons.append(comparison["reason"])
    if integrity_degraded:
        verdict = "REJECTED"
        reasons.append("科学完整性维度退化：" + ", ".join(integrity_degraded))
    if unobservable:
        reasons.append(f"{unobservable} 个决策为 NO_SUPPORT：不得计入晋升证据")
    if any(not result.get("isolation_verified", True)
           for block in (report.get("per_arm") or {}).values()
           for result in block.get("results") or []):
        verdict = "REJECTED"
        reasons.append("存在隔离未通过的 case：无独立评价资格")
    return {"verdict": verdict, "reasons": reasons, "comparison": comparison,
            "degraded_dimensions": degraded, "unobservable_decisions": unobservable,
            "note": "discovery replay 的维度各自独立，没有加权总分"}


def evaluate_candidate(state_path: Path, policy_id: str, report: Dict[str, Any], *,
                       independent: bool = True, leakage_checked: bool = True,
                       reproducible: bool = True, reason: str = "") -> Dict[str, Any]:
    """Run the independent replay evaluation and advance to REPLAY_EVALUATED or HOLD.

    The verdict is computed here from the report; the candidate never supplies it.
    """
    verdict = ablation_verdict(report)
    evidence = {
        "replay_verdict": verdict["verdict"],
        "leakage_checked": bool(leakage_checked),
        "reproducible": bool(reproducible),
        "independent": bool(independent),
        "sample_adequate": bool(report.get("sufficient_sample")),
        "distinguishable": bool(verdict["comparison"]["distinguishable"]),
        "degraded_dimensions": verdict["degraded_dimensions"],
        "unobservable_decisions": verdict["unobservable_decisions"],
        "reason": reason or "; ".join(verdict["reasons"]),
    }
    if verdict["verdict"] in ("SUPPORTED", "UNDIFFERENTIATED", "INSUFFICIENT_SAMPLE"):
        if verdict["verdict"] != "SUPPORTED":
            return transition(state_path, policy_id, "HOLD", level="L2", evidence=evidence,
                              reason=evidence["reason"])
        return transition(state_path, policy_id, "REPLAY_EVALUATED", level="L2",
                          evidence=evidence, reason=evidence["reason"])
    return transition(state_path, policy_id, "REJECTED", level="L2", evidence=evidence,
                      reason=evidence["reason"])


def recorded_evaluation(records: Sequence[Dict[str, Any]], policy_id: str) -> Dict[str, Any]:
    """The most recent evaluation evidence actually written for this policy.

    Promotion must read this, never restate it: a function that supplies its own
    `sample_adequate=True` would silently upgrade a policy whose recorded replay said the
    sample was too small or the arms were indistinguishable.
    """
    merged: Dict[str, Any] = {}
    for record in records:
        if record.get("record") != "transition" or record.get("policy_id") != policy_id:
            continue
        if record.get("to") not in ("REPLAY_EVALUATED", "BOUNDED_TRIAL", "VALIDATED"):
            continue
        # Later transitions override, but a key recorded earlier (e.g. `sample_adequate` from
        # the replay evaluation) is not lost just because a later step did not repeat it.
        merged.update({key: value for key, value in (record.get("evidence") or {}).items()})
    return merged


def promote_to_active(state_path: Path, policy_id: str,
                      evaluation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """ACTIVE promotion, using the *recorded* evaluation evidence plus the frozen-rule check."""
    evaluation = dict(evaluation or {})
    current_digest = evaluation_rules_digest(state_path)
    records, _ = load_records(state_path)
    candidate = policy_record(records, policy_id) or {}
    recorded = recorded_evaluation(records, policy_id)
    evidence = {
        "rules_digest_unchanged": bool(
            candidate.get("evaluation_rules_digest") == current_digest
            and evaluation.get("rules_digest_unchanged", True)),
        "scope_evidence_ok": bool(evaluation.get("scope_evidence_ok", True)),
        # Fail closed: absent recorded evidence is not evidence.
        "independent": bool(recorded.get("independent")),
        "leakage_checked": bool(recorded.get("leakage_checked", True)),
        "reproducible": bool(recorded.get("reproducible", True)),
        "sample_adequate": bool(recorded.get("sample_adequate")),
        "distinguishable": bool(recorded.get("distinguishable")),
        "degraded_dimensions": list(recorded.get("degraded_dimensions") or []),
        "reason": evaluation.get("reason") or recorded.get("reason")
        or "independent replay evaluation (recorded)",
    }
    return transition(state_path, policy_id, "ACTIVE", level="L3", evidence=evidence,
                      reason=evidence["reason"])


# ---------------------------------------------------------------------------
# Real consumer bridge: an ACTIVE policy feeds the existing adapter
# ---------------------------------------------------------------------------

def advice_from_active_policy(records: Sequence[Dict[str, Any]], state: Dict[str, Any],
                              index: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Project the ACTIVE policy into the `strategy_memory` advice shape.

    This is the only way a policy influences research behaviour: the existing Strategy
    Decision Adapter re-orders inside the top `EIG ÷ cost` tier, so the hard priority, the
    gates and the budgets are untouched.
    """
    candidate = active_policy(records)
    if not candidate:
        return None
    changes = candidate.get("strategy_changes") or []
    advice: Dict[str, Any] = {"menu": None, "operator": None, "island": None, "shift": None,
                              "basis": [f"policy:{candidate.get('policy_id')}"],
                              "reason": "active scoped policy",
                              "policy_id": candidate.get("policy_id"),
                              "scope": copy.deepcopy(candidate.get("scope"))}
    try:
        import strategy_memory as sm
        menus = sm.MENU_BY_NAME
    except Exception:  # pragma: no cover - strategy memory is always importable
        menus = {}
    for change in changes:
        kind = change.get("kind")
        if kind == "exploration_operator_preference":
            advice["operator"] = change.get("operator")
        elif kind == "menu_choice":
            # A menu only changes behaviour through the operator/island it declares, so map it;
            # recording the menu name alone made `menu_choice` a change with no consumer.
            advice["menu"] = change.get("menu")
            entry = menus.get(change.get("menu")) or {}
            advice["operator"] = advice.get("operator") or entry.get("operator")
            advice["island"] = advice.get("island") or entry.get("island")
            advice["shift"] = advice.get("shift") or entry.get("shift")
        elif kind == "same_tier_preference":
            advice.setdefault("prefer_actions", [])
            if change.get("prefer_action"):
                advice["prefer_actions"].append(change["prefer_action"])
        elif kind in ("same_tier_order", "probe_order"):
            # The requested order is preserved, not just the membership: the adapter uses the
            # position in this list as the re-ordering rank.
            advice.setdefault("prefer_actions", [])
            advice["prefer_actions"].extend(change.get("order") or [])
        elif kind == "applicability":
            advice["island"] = advice.get("island") or change.get("problem_structure")
    if not any(advice.get(key) for key in ("menu", "operator", "island", "prefer_actions")):
        return None
    return advice


def scope_conditions_hold(candidate: Dict[str, Any], state: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Whether the policy's applicability conditions are satisfied by the live state.

    Conditions are checked against declared canonical fields, never against prose.
    """
    index = None
    try:
        import cognition as cognition_module
        index, _ = cognition_module.full_index(state, [], "policy", None, None)
    except Exception:  # pragma: no cover - index is optional for the check
        index = None
    operators = {str(item.get("operator")) for item in state.get("hypotheses") or []
                 if isinstance(item, dict)}
    islands = {str(item.get("island")) for item in state.get("hypotheses") or []
               if isinstance(item, dict)}
    unmet: List[str] = []
    for condition in candidate.get("applicable_conditions") or []:
        if not isinstance(condition, dict):
            unmet.append(f"非结构化条件 {condition!r}")
            continue
        kind = str(condition.get("kind") or "")
        value = str(condition.get("value") or "")
        if kind == "operator_present":
            if value not in operators:
                unmet.append(f"缺少算子 {value}")
        elif kind == "island_present":
            if value not in islands:
                unmet.append(f"缺少 island {value}")
        elif kind == "min_state_version":
            try:
                if int(state.get("state_version") or 0) < int(value):
                    unmet.append(f"state_version < {value}")
            except ValueError:
                unmet.append(f"非法 min_state_version {value!r}")
        elif kind in ("min_open_uncertainties", "min_hypotheses"):
            field = ("uncertainties" if kind == "min_open_uncertainties" else "hypotheses")
            count = len([item for item in state.get(field) or [] if isinstance(item, dict)])
            try:
                if count < int(value):
                    unmet.append(f"{field} 少于 {value}")
            except ValueError:
                unmet.append(f"非法条件 {value!r}")
        else:
            unmet.append(f"未知条件类型 {kind!r}（不得凭自由文本判断适用性）")
    return (not unmet), unmet


def cross_project_transfer_allowed(candidate: Dict[str, Any], target_state: Dict[str, Any], *,
                                   current_route: Optional[str] = None,
                                   require_transfer: bool = False,
                                   **transfer_kwargs: Any) -> Dict[str, Any]:
    """Whether a policy that originated in another route may act on this one.

    Same-route policies are not gated. A policy that declares a different
    `scope.source_route` / `scope.source_project` must pass the structural transfer gate
    (`policy_transfer.PT*`); domain-keyword resemblance is never enough.

    Fail-closed provenance: `propose()` does not stamp `source_route`/`source_project`, so a
    candidate with no declared source is *unverifiable*, not "same route". When the caller
    supplies a `current_route` (or passes `require_transfer=True`), the gate must not silently
    return `NOT_REQUIRED`: an absent source, or an absent `current_route` when a source *is*
    declared, is a BLOCK. `require_transfer=True` forces the transfer gate even without a
    declared source, leaving the PT* rules to decide.
    """
    def blocked(reason: str) -> Dict[str, Any]:
        return {"required": True, "status": "BLOCK", "reasons": [reason], "similarity": None}

    if not isinstance(candidate, dict):
        return blocked("策略候选不是对象；无法判定跨项目迁移边界（fail-closed 阻塞）")
    raw_scope = candidate.get("scope")
    scope = raw_scope if isinstance(raw_scope, dict) else {}
    source = (scope.get("source_route") or scope.get("source_project")
              or candidate.get("source_route") or candidate.get("source_project"))
    source_declared = bool(source)
    if source_declared and current_route and str(source) == str(current_route):
        return {"required": False, "status": "NOT_REQUIRED", "reasons": [], "similarity": None}
    if not require_transfer:
        if not source_declared:
            if current_route:
                return blocked(
                    "策略未声明 scope.source_route/source_project；在已知当前路由 "
                    f"{current_route!r} 时无法证明同路由（fail-closed 阻塞）")
            return {"required": False, "status": "NOT_REQUIRED", "reasons": [],
                    "similarity": None}
        if not current_route:
            return blocked(
                f"当前路由未知（current_route 为空）；无法证明与来源 {source!r} 同路由"
                "（fail-closed 阻塞）")
    import policy_transfer as pt
    try:
        decision = pt.transfer_decision(candidate, target_state,
                                        target_project=current_route, **transfer_kwargs)
    except Exception as exc:  # fail closed: a broken transfer check must not allow the policy
        return {"required": True, "status": "BLOCK",
                "reasons": [f"transfer check failed: {type(exc).__name__}: {exc}"],
                "similarity": None}
    return {"required": True, "status": decision.get("status"),
            "reasons": decision.get("reasons"), "similarity": decision.get("similarity")}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    def error(self, message):  # pragma: no cover
        self.print_usage(sys.stderr)
        raise SystemExit(EXIT_ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(description=__doc__,
                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", choices=(
        "freeze-rules", "propose", "list", "show", "transition", "evaluate", "rollback",
        "state", "advice", "validate"))
    parser.add_argument("--state", help="path to research-state.json")
    parser.add_argument("--policy", help="path to a candidate JSON file (or - for stdin)")
    parser.add_argument("--policy-id")
    parser.add_argument("--to")
    parser.add_argument("--to-policy-id")
    parser.add_argument("--reason", default="")
    parser.add_argument("--level", default="L1")
    parser.add_argument("--report", help="path to a replay ablation report JSON")
    parser.add_argument("--trajectory", help="path to decision-trajectory.jsonl")
    parser.add_argument("--selftest", action="store_true")
    return parser


def _emit(payload: Any, code: int = EXIT_OK) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return code


def _state_path(args) -> Path:
    if not args.state:
        raise SystemExit("需要 --state")
    return Path(args.state)


def _read_json(value: Optional[str]) -> Any:
    if not value:
        raise SystemExit("缺少 JSON 输入")
    if value == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(value).read_text(encoding="utf-8"))


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.selftest:
        return selftest()
    try:
        state_path = _state_path(args)
    except SystemExit as exc:
        return _emit({"status": "INVALID", "errors": [str(exc)]}, EXIT_ERROR)

    if args.command == "freeze-rules":
        return _emit(freeze_evaluation_rules(state_path))
    if args.command == "list":
        records, diagnostics = load_records(state_path, tolerant=True)
        snapshot = rebuild_state(records)
        return _emit({"status": "OK" if not diagnostics else "INVALID",
                      "state": snapshot,
                      "errors": [item.render() for item in diagnostics]},
                     EXIT_OK if not diagnostics else EXIT_HARD)
    if args.command == "state":
        records, _ = load_records(state_path)
        return _emit(rebuild_state(records))
    if args.command == "show":
        records, _ = load_records(state_path)
        if not args.policy_id:
            return _emit({"status": "INVALID", "errors": ["需要 --policy-id"]}, EXIT_ERROR)
        candidate = policy_record(records, args.policy_id)
        if candidate is None:
            return _emit({"status": "NOT_FOUND", "policy_id": args.policy_id}, EXIT_ERROR)
        return _emit({"status": "OK", "candidate": candidate,
                      "status_now": latest_status(records).get(args.policy_id)})
    if args.command == "propose":
        candidate = _read_json(args.policy)
        support = None
        if args.trajectory:
            support = dt.support_ids(dt.load_records(Path(args.trajectory))[0])
        result = propose(state_path, candidate, trajectory_support=support)
        return _emit(result, EXIT_OK if result["status"] == "PROPOSED" else EXIT_HARD)
    if args.command == "transition":
        if not args.policy_id or not args.to:
            return _emit({"status": "INVALID", "errors": ["需要 --policy-id 与 --to"]},
                         EXIT_ERROR)
        evidence = json.loads(args.reason) if args.reason.startswith("{") else {}
        result = transition(state_path, args.policy_id, args.to, level=args.level,
                            evidence=evidence, reason="" if evidence else args.reason)
        return _emit(result, EXIT_OK if result["written"] else EXIT_HARD)
    if args.command == "evaluate":
        if not args.policy_id or not args.report:
            return _emit({"status": "INVALID",
                          "errors": ["需要 --policy-id 与 --report"]}, EXIT_ERROR)
        report = json.loads(Path(args.report).read_text(encoding="utf-8"))
        result = evaluate_candidate(state_path, args.policy_id, report)
        return _emit(result, EXIT_OK if result["written"] else EXIT_HARD)
    if args.command == "rollback":
        if not args.policy_id or not args.to_policy_id or not args.reason:
            return _emit({"status": "INVALID",
                          "errors": ["需要 --policy-id --to-policy-id --reason"]}, EXIT_ERROR)
        result = rollback(state_path, args.policy_id, to_policy_id=args.to_policy_id,
                          reason=args.reason)
        return _emit(result, EXIT_OK if result["written"] else EXIT_HARD)
    if args.command == "advice":
        import strategy_memory as sm  # noqa: F401 - imported for parity with the adapter
        state = cg.load_state(state_path)
        records, _ = load_records(state_path)
        advice = advice_from_active_policy(records, state)
        return _emit({"status": "OK" if advice else "NO_ACTIVE_POLICY", "advice": advice})
    return _emit({"status": "INVALID", "errors": ["未知命令"]}, EXIT_ERROR)


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _valid_candidate(**overrides) -> Dict[str, Any]:
    candidate = {
        "policy_id": "P-1",
        "policy_schema_version": POLICY_SCHEMA_VERSION,
        "parent_policy_id": None,
        "status": "PROPOSED",
        "scope": {"scope_kind": "project", "problem_structure": "reframe-diagnostic-loop"},
        "applicable_conditions": [{"kind": "min_open_uncertainties", "value": 1}],
        "strategy_changes": [{"kind": "exploration_operator_preference", "operator": "reframe"}],
        "supporting_trajectory_ids": ["DT-1"],
        "counterexamples": ["fixture only"],
        "expected_effect": {"mechanism": "avoid valueless diagnostics", "direction": "decrease"},
        "revalidation_conditions": ["new independent project"],
        "evaluation_refs": [],
        "rollback_target": None,
    }
    candidate.update(overrides)
    return candidate


def _arm_block(mean_high, mean_low=None):
    low = mean_high - 0.4 if mean_low is None else mean_low
    return {"dimensions": {
        "mechanistic_understanding": {"mean": 0.5, "min": 0.4, "max": 0.6},
        "prediction_quality": {"mean": low, "min": low - 0.1, "max": low + 0.1},
        "intervention_quality": {"mean": mean_high, "min": mean_high - 0.05,
                                 "max": mean_high + 0.05},
        "scientific_novelty": {"mean": 0.5, "min": 0.5, "max": 0.5},
        "search_efficiency": {"mean": 1.0, "min": 1.0, "max": 1.0},
        "stagnation_recovery": {"mean": 1.0, "min": 1.0, "max": 1.0},
        "memory_accumulation": {"mean": 1.0, "min": 1.0, "max": 1.0},
    }, "results": [], "evidence_support": {}}


def _report(sufficient=True, unobservable=0):
    return {"schema": "research-idea-pipeline/replay-ablation@1",
            "sufficient_sample": sufficient, "unobservable_decisions": unobservable,
            "delta_vs_baseline": {}, "per_arm": {"rsi_full": _arm_block(0.9),
                                                 "full_cie": _arm_block(0.3)},
            "cases": 5, "runs_per_case": 2}


def selftest() -> int:
    import tempfile
    checks: List[Tuple[str, bool]] = []

    def check(name, condition):
        checks.append((name, bool(condition)))

    with tempfile.TemporaryDirectory() as temp:
        route = Path(temp) / "A"
        route.mkdir(parents=True)
        state = {"state_version": 3, "contract": {"goal": "g", "primary_anchor": "A0"},
                 "hypotheses": [{"id": "H1", "operator": "reframe", "island": "P1"}],
                 "uncertainties": [{"id": "U1", "status": "open"}]}
        state_path = route / cg.STATE_NAME

        frozen = freeze_evaluation_rules(state_path)
        check("evaluation rules freeze once", frozen["status"] == "FROZEN")
        again = freeze_evaluation_rules(state_path)
        check("evaluation rules cannot be silently rewritten",
              again["status"] == "ALREADY_FROZEN" and again["digest"] == frozen["digest"])

        candidate = _valid_candidate()
        candidate["evaluation_rules_digest"] = frozen["digest"]
        result = propose(state_path, candidate, trajectory_support={"DT-1"})
        check("a valid scoped candidate is proposed", result["status"] == "PROPOSED", )

        bad = _valid_candidate(policy_id="P-BAD",
                               strategy_changes=[{"kind": "scheduler_priority",
                                                  "target": "scheduler_priority",
                                                  "value": [1]}])
        rejected = propose(state_path, bad)
        check("a candidate touching the hard priority is refused",
              rejected["status"] == "INVALID" and "PE2" in rejected["codes"])

        shell = _valid_candidate(policy_id="P-SHELL",
                                 expected_effect={"mechanism": "rm -rf / && curl x",
                                                  "direction": "up"})
        rejected = propose(state_path, shell)
        check("executable content is refused",
              rejected["status"] == "INVALID" and "PE6" in rejected["codes"])

        ghost = _valid_candidate(policy_id="P-GHOST", supporting_trajectory_ids=["DT-99"])
        rejected = propose(state_path, ghost, trajectory_support={"DT-1"})
        check("a candidate supported by a non-existent trajectory is refused",
              rejected["status"] == "INVALID" and "PE4" in rejected["codes"])

        changed_rules = _valid_candidate(policy_id="P-RULES")
        changed_rules["evaluation_rules_digest"] = "deadbeef"
        rejected = propose(state_path, changed_rules)
        check("a candidate generated under different evaluation rules is refused",
              rejected["status"] == "INVALID" and "PE12" in rejected["codes"])

        no_scope = _valid_candidate(policy_id="P-GLOBAL", scope={"scope_kind": "global"})
        rejected = propose(state_path, no_scope)
        check("a global slogan without structure is refused",
              rejected["status"] == "INVALID" and "PE3" in rejected["codes"])

        # --- lifecycle --------------------------------------------------------
        illegal = transition(state_path, "P-1", "ACTIVE", level="L3",
                             evidence={"rules_digest_unchanged": True, "scope_evidence_ok": True})
        check("PROPOSED cannot jump straight to ACTIVE",
              illegal["status"] == "INVALID" and "PE10" in illegal["codes"])

        to_shadow = transition(state_path, "P-1", "SHADOW", level="L1",
                               evidence={"format_ok": True, "invariants_ok": True,
                                         "permissions_ok": True})
        check("L1 moves to SHADOW", to_shadow["status"] == "SHADOW")

        gate = transition(state_path, "P-1", "REPLAY_EVALUATED", level="L2",
                          evidence={"replay_verdict": "SUPPORTED"})
        check("promotion without independent evidence is refused",
              gate["status"] == "INVALID" and "PE11" in gate["codes"])

        evaluated = evaluate_candidate(state_path, "P-1", _report())
        check("an independent support verdict reaches REPLAY_EVALUATED",
              evaluated["status"] == "REPLAY_EVALUATED", )

        # A second candidate isolates the "indistinguishable arms" rule.
        flat = _valid_candidate(policy_id="P-FLAT",
                                scope={"scope_kind": "local",
                                       "problem_structure": "unrelated-diagnostic-loop"})
        flat["evaluation_rules_digest"] = frozen["digest"]
        check("flat candidate proposes", propose(state_path, flat)["status"] == "PROPOSED")
        transition(state_path, "P-FLAT", "SHADOW", level="L1",
                   evidence={"format_ok": True, "invariants_ok": True, "permissions_ok": True})
        undifferentiated = evaluate_candidate(
            state_path, "P-FLAT",
            {"sufficient_sample": True, "unobservable_decisions": 0, "delta_vs_baseline": {},
             "per_arm": {"rsi_full": _arm_block(0.5, 0.5), "full_cie": _arm_block(0.5, 0.5)},
             "cases": 5, "runs_per_case": 2})
        check("indistinguishable arms are not promoted",
              undifferentiated["status"] == "HOLD")

        trial = transition(state_path, "P-1", "BOUNDED_TRIAL", level="L2",
                           evidence={"budget_expanded": False, "hard_gates_unchanged": True,
                                     "dispatch_evidence": True})
        check("bounded trial does not expand the budget", trial["status"] == "BOUNDED_TRIAL")
        expanded = transition(state_path, "P-1", "VALIDATED", level="L3",
                              evidence={"independent": True, "distinguishable": True,
                                        "degraded_dimensions": [], "budget_expanded": True})
        check("expanding the budget during a trial is refused",
              expanded["status"] == "INVALID")

        validated = transition(state_path, "P-1", "VALIDATED", level="L3",
                               evidence={"independent": True, "distinguishable": True,
                                         "degraded_dimensions": []})
        check("L3 validates", validated["status"] == "VALIDATED")

        # Frozen-rule drift after validation must invalidate promotion.
        import json as _json
        rules_file = rules_path(state_path)
        document = _json.loads(rules_file.read_text(encoding="utf-8"))
        original_rules = rules_file.read_bytes()
        document["rules"]["delta_tolerance"] = 0.99
        document["digest"] = cg.digest_of(document["rules"])
        rules_file.write_text(_json.dumps(document, ensure_ascii=False), encoding="utf-8")
        drift = promote_to_active(state_path, "P-1", {"scope_evidence_ok": True})
        check("a changed evaluation rule invalidates promotion",
              drift["status"] == "INVALID" and "PE12" in drift["codes"])
        rules_file.write_bytes(original_rules)

        active = promote_to_active(state_path, "P-1", {"scope_evidence_ok": True})
        check("a validated policy becomes ACTIVE", active["status"] == "ACTIVE")

        records, _ = load_records(state_path)
        advice = advice_from_active_policy(records, state)
        check("the ACTIVE policy yields adapter advice",
              advice and advice["operator"] == "reframe")
        hold, unmet = scope_conditions_hold(_valid_candidate(), state)
        check("applicability conditions are checked against declared fields", hold, )

        # --- rollback and anti-evasion ---------------------------------------
        # Promote a second policy so the first becomes SUPERSEDED, which is the only state a
        # rollback may restore (a REJECTED / ROLLED_BACK policy is terminal).
        successor = _valid_candidate(policy_id="P-2",
                                     scope={"scope_kind": "local",
                                            "problem_structure": "successor-loop"})
        successor["evaluation_rules_digest"] = evaluation_rules_digest(state_path)
        check("successor proposes", propose(state_path, successor,
                                            trajectory_support={"DT-1"})["status"] == "PROPOSED")
        transition(state_path, "P-2", "SHADOW", level="L1",
                   evidence={"format_ok": True, "invariants_ok": True, "permissions_ok": True})
        evaluate_candidate(state_path, "P-2", _report())
        transition(state_path, "P-2", "BOUNDED_TRIAL", level="L2",
                   evidence={"budget_expanded": False, "hard_gates_unchanged": True,
                             "dispatch_evidence": True})
        transition(state_path, "P-2", "VALIDATED", level="L3",
                   evidence={"independent": True, "distinguishable": True,
                             "degraded_dimensions": []})
        check("successor becomes ACTIVE",
              promote_to_active(state_path, "P-2", {"scope_evidence_ok": True})["status"]
              == "ACTIVE")
        rollback_result = rollback(state_path, "P-2", to_policy_id="P-1",
                                   reason="rehearsal rollback")
        check("rollback keeps the failure trail",
              rollback_result["status"] == "ROLLED_BACK", )
        snapshot = rebuild_state(load_records(state_path)[0])
        check("the snapshot records the rollback",
              snapshot["status"].get("P-2") == "ROLLED_BACK")
        check("a rollback restores the target to ACTIVE",
              snapshot["status"].get("P-1") == "ACTIVE"
              and snapshot["active_policy_id"] == "P-1")
        rejected = _valid_candidate(policy_id="P-REJECTED",
                                    scope={"scope_kind": "local",
                                           "problem_structure": "rejected-loop"})
        rejected["evaluation_rules_digest"] = evaluation_rules_digest(state_path)
        propose(state_path, rejected, trajectory_support={"DT-1"})
        transition(state_path, "P-REJECTED", "SHADOW", level="L1",
                   evidence={"format_ok": True, "invariants_ok": True, "permissions_ok": True})
        transition(state_path, "P-REJECTED", "REJECTED", level="L2",
                   evidence={"reason": "harmful"})
        check("rollback to a REJECTED policy is refused",
              rollback(state_path, "P-1", to_policy_id="P-REJECTED",
                       reason="try again")["status"] == "INVALID")

        for index in (0, 1):
            retry = _valid_candidate(policy_id=f"P-EVADE-{index}")
            retry["evaluation_rules_digest"] = evaluation_rules_digest(state_path)
            proposed = propose(state_path, retry)
            check(f"a same-signature retry #{index} is allowed under the cap",
                  proposed["status"] == "PROPOSED")
            transition(state_path, f"P-EVADE-{index}", "SHADOW", level="L1",
                       evidence={"format_ok": True, "invariants_ok": True,
                                 "permissions_ok": True})
            transition(state_path, f"P-EVADE-{index}", "REJECTED", level="L2",
                       evidence={"reason": "fails"})
        blocked = _valid_candidate(policy_id="P-EVADE-NEW-NAME")
        blocked["evaluation_rules_digest"] = evaluation_rules_digest(state_path)
        outcome = propose(state_path, blocked)
        check("renaming cannot evade the failure cap",
              outcome["status"] == "INVALID" and "PE9" in outcome["codes"])

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    print("selftest " + ("OK" if not failed else "FAILED: " + "; ".join(failed)))
    return EXIT_OK if not failed else EXIT_HARD


if __name__ == "__main__":
    raise SystemExit(main())
