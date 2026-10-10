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
import fcntl
import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import cognition as cg
import decision_trajectory as dt

SCHEMA_CANDIDATE = "research-idea-pipeline/policy-candidate@1"
SCHEMA_TRANSITION = "research-idea-pipeline/policy-transition@1"
SCHEMA_ROLLBACK = "research-idea-pipeline/policy-rollback@1"
SCHEMA_RULES = "research-idea-pipeline/policy-evaluation-rules@1"
SCHEMA_EVALUATION = "research-idea-pipeline/policy-evaluation@1"
SCHEMA_TRIAL = "research-idea-pipeline/policy-trial@1"
SCHEMA_ABLATION_REPORT = "research-idea-pipeline/replay-ablation@1"
POLICY_SCHEMA_VERSION = "1"

EXIT_OK = cg.EXIT_OK
EXIT_ERROR = cg.EXIT_ERROR
EXIT_HARD = cg.EXIT_HARD
EXIT_ENV = cg.EXIT_ENV

POLICY_DIRNAME = "policy"
CANDIDATES_NAME = "candidates.jsonl"
RULES_NAME = "evaluation-rules.json"

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
    "applicability": {"required": ()},
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
    """`<route>/policy`, derived lexically like the other route control files.

    Resolving first made a symlinked state path read the policy store of the *real* route
    while the scheduler, trajectory, cognition and audit files stayed with the lexical route.
    """
    return Path(state_path).expanduser().parent / POLICY_DIRNAME


def candidates_path(state_path: Path) -> Path:
    return policy_dir(state_path) / CANDIDATES_NAME


def rules_path(state_path: Path) -> Path:
    return policy_dir(state_path) / RULES_NAME


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
        rules = existing.get("rules") if isinstance(existing, dict) else None
        stored = existing.get("digest") if isinstance(existing, dict) else None
        if not isinstance(rules, dict) or stored != cg.digest_of(rules):
            return {"status": "INVALID", "path": str(path), "digest": None, "rules": None,
                    "errors": ["评价规则内容与 digest 不一致：规则被改写，拒绝沿用"]}
        return {"status": "ALREADY_FROZEN", "path": str(path),
                "digest": stored, "rules": rules}
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
    """Digest of the frozen rule *content*, or None when absent or inconsistent.

    The stored `digest` field used to be returned verbatim, so editing `rules` while leaving
    the field alone produced a "frozen" rule set whose digest no longer described it. The
    digest is now recomputed; any mismatch means "untrusted" (None) and every promotion
    gate fails closed.
    """
    path = rules_path(state_path)
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, OSError, json.JSONDecodeError):
        return None
    rules = document.get("rules") if isinstance(document, dict) else None
    if not isinstance(rules, dict):
        return None
    recomputed = cg.digest_of(rules)
    return recomputed if document.get("digest") == recomputed else None


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


def _is_consumable_change(change: Any) -> bool:
    """Whether the Strategy Decision Adapter can act on this change.

    `applicability` only changes an ordering when it names an island the adapter can match
    against `hypotheses[].island`; a bare problem-structure string is context, not a consumer.
    """
    if not isinstance(change, dict):
        return False
    kind = change.get("kind")
    if kind not in CONSUMABLE_CHANGE_KINDS:
        return False
    if kind == "applicability":
        return bool(change.get("island"))
    return True


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
            if kind == "applicability":
                island = change.get("island")
                if island in (None, "") and change.get("problem_structure") in (None, ""):
                    diagnostics.append(_diag("PE1", cpath,
                                             "applicability 需要 island 或 problem_structure"))
                if island not in (None, ""):
                    try:
                        import state_check as sc
                        if island not in sc.ISLANDS:
                            diagnostics.append(_diag("PE2", cpath, f"未知 island {island!r}"))
                    except Exception:  # pragma: no cover
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
    # Second, independent scan for protected-target and executable-content attempts. The
    # guard used to be reachable only from its own tests, which is not an enforcement path.
    try:
        import source_freeze as sf
        for reason in sf.guard_errors(candidate):
            diagnostics.append(_diag("PE2", path, f"源码保护扫描拒绝：{reason}"))
    except Exception:  # pragma: no cover - source_freeze is always importable
        pass

    # A policy must be able to change a decision. Advisory-only changes (resource allocation)
    # may accompany a consumable one but may not be the whole policy, otherwise a promoted
    # policy could never have a real consumer.
    if isinstance(changes, list) and changes and \
            not any(_is_consumable_change(item) for item in changes):
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


def propose(state_path: Path, candidate: Dict[str, Any], *,
            trajectory_support: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Append a candidate, refusing validation failures and duplicate-open limits.

    Runs under the store lock: the open-candidate cap and the duplicate-id check are read
    from a snapshot, so they must not race a concurrent proposal or transition.
    """
    with policy_lock(state_path):
        return _propose_locked(state_path, candidate, trajectory_support=trajectory_support)


def _propose_locked(state_path: Path, candidate: Dict[str, Any], *,
                    trajectory_support: Optional[Iterable[str]] = None) -> Dict[str, Any]:
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
    # unprovable. This OVERRIDES any value the candidate declared: `setdefault` let a
    # candidate claim the target route as its own and skip the transfer gate entirely.
    record["source_route"] = cg.route_of(Path(state_path))
    record["origin_stamped"] = True
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
    # The pointer and the lifecycle status must agree. Taking the last `-> ACTIVE` transition
    # unconditionally left a still-ACTIVE policy dropped as soon as a later policy went HOLD,
    # and a rollback pointer could name a policy that had since been rejected.
    order: List[str] = []
    for record in records:
        if record.get("record") == "transition" and record.get("to") == "ACTIVE":
            ident = record.get("policy_id")
            if ident in order:
                order.remove(ident)
            order.append(ident)
        elif record.get("record") == "rollback":
            target = record.get("to_policy_id")
            if isinstance(target, str) and target not in order:
                order.append(target)
    active = None
    for ident in reversed(order):
        if statuses.get(ident) == "ACTIVE":
            active = ident
            break
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


# ---------------------------------------------------------------------------
# Frozen evaluation rules: content and digest must agree
# ---------------------------------------------------------------------------

def evaluation_rules_errors(state_path: Path) -> List[cg.Diagnostic]:
    """PE12 diagnostics for the frozen rule set.

    The stored `digest` field is recomputed from `rules`; a document whose content and
    digest disagree is treated as tampered (fail closed) instead of returning the stale
    digest, which let an edited tolerance pass every downstream check.
    """
    path = rules_path(state_path)
    if not path.is_file():
        return [_diag("PE12", "policy.evaluation-rules", "冻结评价规则缺失")]
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, OSError, json.JSONDecodeError) as exc:
        return [_diag("PE12", "policy.evaluation-rules",
                      f"冻结评价规则不可读（{type(exc).__name__}）")]
    if not isinstance(document, dict) or not isinstance(document.get("rules"), dict):
        return [_diag("PE12", "policy.evaluation-rules", "冻结评价规则结构非法")]
    recomputed = cg.digest_of(document["rules"])
    if document.get("digest") != recomputed:
        return [_diag("PE12", "policy.evaluation-rules",
                      "评价规则内容与 digest 不一致：规则被改写，评价不可信")]
    return []


# ---------------------------------------------------------------------------
# Store lock: a transition is a multi-record operation
# ---------------------------------------------------------------------------

POLICY_LOCK_NAME = ".policy.lock"
EVALUATIONS_DIRNAME = "evaluations"
TRIALS_DIRNAME = "trials"

#: Pre-registered dimensions. A promotion needs a *positive* improvement on a benefit
#: dimension; a reliability dimension may never regress. Both sets are frozen here so a
#: report cannot choose what counts as an improvement.
BENEFIT_DIMENSIONS: Tuple[str, ...] = ("search_efficiency", "stagnation_recovery",
                                       "memory_accumulation")
RELIABILITY_DIMENSIONS: Tuple[str, ...] = ("prediction_quality", "intervention_quality",
                                           "scientific_novelty")

#: Targets that may only be reached through a controlled entry point.
GATED_TARGETS: Tuple[str, ...] = ("REPLAY_EVALUATED", "BOUNDED_TRIAL", "VALIDATED", "ACTIVE")
LEVEL_RANK: Dict[str, int] = {"L1": 1, "L2": 2, "L3": 3}
TARGET_LEVEL: Dict[str, str] = {"SHADOW": "L1", "REPLAY_EVALUATED": "L2",
                                "BOUNDED_TRIAL": "L2", "VALIDATED": "L3", "ACTIVE": "L3"}

#: Module-private authority token. Only the controlled promotion entries hold a reference;
#: `transition()` refuses a gated target without it, so hand-written evidence cannot climb.
_AUTHORITY = object()


@contextmanager
def policy_lock(state_path: Path) -> Iterator[None]:
    """Exclusive lock over the whole policy store.

    A transition appends several records (the transition, the supersede record, the
    snapshot). Validating against a snapshot read outside the lock let two concurrent
    promotions both observe VALIDATED and both append ACTIVE.
    """
    directory = policy_dir(state_path)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / POLICY_LOCK_NAME).open("a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _append(state_path: Path, record: Dict[str, Any]) -> Dict[str, Any]:
    """Append while the caller holds `policy_lock` (one lock for the whole store)."""
    return dt.append_chained(candidates_path(state_path), record, lock_held=True)


# ---------------------------------------------------------------------------
# Evaluation artifacts: source, digest, policy binding, frozen rules, execution record
# ---------------------------------------------------------------------------

def evaluations_dir(state_path: Path) -> Path:
    return policy_dir(state_path) / EVALUATIONS_DIRNAME


def trials_dir(state_path: Path) -> Path:
    return policy_dir(state_path) / TRIALS_DIRNAME


def _artifact_body(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "digest"}


def _store_artifact(state_path: Path, directory: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    document = dict(_artifact_body(payload), digest=cg.digest_of(_artifact_body(payload)))
    name = f"{payload.get('policy_id')}.{document['digest'].split(':')[-1][:16]}.json"
    target = directory / name
    pending = target.with_name(target.name + ".pending")
    pending.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.replace(pending, target)
    return {"path": str(target), "digest": document["digest"],
            "policy_id": payload.get("policy_id")}


def _read_artifact(directory: Path, ref: Any) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Load and integrity-check an artifact reference. Fail closed on every doubt."""
    if not isinstance(ref, dict):
        return None, ["评价产物引用必须是对象"]
    raw = ref.get("path")
    if not isinstance(raw, str) or not raw:
        return None, ["评价产物引用缺少 path"]
    try:
        resolved = Path(raw).resolve()
        base = Path(directory).resolve()
    except OSError as exc:
        return None, [f"评价产物路径无法解析（{type(exc).__name__}）"]
    if resolved != base and base not in resolved.parents:
        return None, ["评价产物不在策略存储目录内（拒绝越界路径）"]
    if not resolved.is_file():
        return None, ["评价产物文件不存在"]
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, OSError, json.JSONDecodeError) as exc:
        return None, [f"评价产物不可读（{type(exc).__name__}）"]
    if not isinstance(document, dict):
        return None, ["评价产物不是对象"]
    body = _artifact_body(document)
    if document.get("digest") != cg.digest_of(body):
        return None, ["评价产物完整性摘要不匹配：内容被替换"]
    if ref.get("digest") and ref["digest"] != document.get("digest"):
        return None, ["引用声明的摘要与产物不一致"]
    return document, []


def _recomputed_level(gates: Dict[str, Any], verdict: Dict[str, Any]) -> str:
    """The level an artifact's own evidence supports — never the level it claims."""
    if (verdict or {}).get("verdict") != "SUPPORTED":
        return "L1"
    rules = DEFAULT_EVALUATION_RULES
    coverage = int((gates or {}).get("assessable_dimensions") or 0)
    if coverage >= 2 and int((gates or {}).get("runs") or 0) >= rules["min_runs"] \
            and int((gates or {}).get("cases") or 0) >= rules["min_cases"] \
            and (gates or {}).get("runner"):
        return "L3"
    return "L2"


def latest_evaluation_artifact(state_path: Path, policy_id: str,
                               records: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The most recent stored evaluation artifact bound to this policy, if any."""
    for record in reversed(list(records)):
        if record.get("record") != "transition" or record.get("policy_id") != policy_id:
            continue
        ref = (record.get("evidence") or {}).get("evaluation_ref")
        if not isinstance(ref, dict):
            continue
        payload, errors = _read_artifact(evaluations_dir(state_path), ref)
        if payload is not None and not errors:
            return dict(payload, ref=ref)
    return None


def _artifact_gate_errors(state_path: Path, records: Sequence[Dict[str, Any]],
                          candidate: Dict[str, Any], target: str,
                          evidence: Dict[str, Any]) -> List[cg.Diagnostic]:
    """Verify the artifact a gated transition depends on, and its achieved level."""
    policy_id = candidate.get("policy_id")
    path = f"policy[{policy_id}]"
    using_trial = target == "BOUNDED_TRIAL"
    ref_key = "trial_ref" if using_trial else "evaluation_ref"
    directory = trials_dir(state_path) if using_trial else evaluations_dir(state_path)
    schema = SCHEMA_TRIAL if using_trial else SCHEMA_EVALUATION
    ref = evidence.get(ref_key)
    if not isinstance(ref, dict):
        return [_diag("PE11", path,
                      f"{target} 必须由受控晋升入口完成，并携带它写出的 {ref_key}；"
                      "调用方自述字段不能用于晋升")]
    payload, errors = _read_artifact(directory, ref)
    if payload is None:
        return [_diag("PE11", path, err) for err in errors]
    diagnostics: List[cg.Diagnostic] = []
    if payload.get("_schema") != schema:
        diagnostics.append(_diag("PE11", path, f"评价产物 schema 不是 {schema!r}"))
    if payload.get("policy_id") != policy_id:
        diagnostics.append(_diag("PE11", path, "评价产物绑定到另一个策略"))
    if payload.get("policy_signature") != candidate.get("signature"):
        diagnostics.append(_diag("PE11", path, "评价产物绑定的策略版本与当前候选不一致"))

    rules = evaluation_rules_errors(state_path)
    diagnostics.extend(rules)
    current = evaluation_rules_digest(state_path)
    if current is not None:
        if payload.get("rules_digest") != current:
            diagnostics.append(_diag("PE12", path, "评价规则已改变：该产物的评价结果失效"))
        if candidate.get("evaluation_rules_digest") != current:
            diagnostics.append(_diag("PE12", path, "候选绑定的是另一版评价规则"))

    verdict = payload.get("verdict") if isinstance(payload.get("verdict"), dict) else {}
    gates = payload.get("gates") if isinstance(payload.get("gates"), dict) else {}
    recomputed = _recomputed_level(gates, verdict)
    if payload.get("level") != recomputed:
        diagnostics.append(_diag("PE11", path,
                                 f"产物自报等级 {payload.get('level')!r} 与其证据不符"
                                 f"（应为 {recomputed!r}）"))
    required = TARGET_LEVEL.get(target, "L1")
    if LEVEL_RANK.get(recomputed, 0) < LEVEL_RANK.get(required, 1):
        diagnostics.append(_diag("PE11", path,
                                 f"{target} 需要 {required} 级证据，产物只达到 {recomputed}"))
    if not using_trial and verdict.get("verdict") != "SUPPORTED":
        diagnostics.append(_diag("PE11", path,
                                 f"评价产物结论是 {verdict.get('verdict')!r}，不是 SUPPORTED"))
    return diagnostics


# ---------------------------------------------------------------------------
# Transitions, evaluation gates, rollback
# ---------------------------------------------------------------------------

def transition_errors(state_path: Path, records: Sequence[Dict[str, Any]], policy_id: str,
                      target: str, evidence: Dict[str, Any], *,
                      authority_ok: bool = False) -> List[cg.Diagnostic]:
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

    candidate = policy_record(records, policy_id) or {}
    scope = candidate.get("scope") if isinstance(candidate.get("scope"), dict) else {}
    # Only the restore of an already-promoted policy may re-enter ACTIVE without a new
    # artifact; every other gated target needs the controlled entry point.
    restoring = current == "SUPERSEDED" and target == "ACTIVE"

    if target in ("SHADOW", "REPLAY_EVALUATED", "BOUNDED_TRIAL", "VALIDATED", "ACTIVE"):
        overfit = overfit_flags(candidate)
        if overfit and target != "SHADOW":
            diagnostics.append(_diag("PE5", path,
                                     "针对固定 fixture 的策略不得越过 SHADOW：" + "；".join(overfit)))
    if target in GATED_TARGETS and not restoring:
        if not authority_ok:
            diagnostics.append(_diag(
                "PE11", path,
                f"{target} 只能由受控晋升入口完成（evaluate / trial / validate / promote）；"
                "调用方自述的布尔字段不能用于晋升"))
            return diagnostics
        diagnostics.extend(_artifact_gate_errors(state_path, records, candidate, target,
                                                 evidence))

    if target == "SHADOW":
        # L1 is re-derived from the stored candidate, not read from the caller's booleans.
        if evaluation_rules_digest(state_path) is None:
            diagnostics.append(_diag("PE12", path, "冻结评价规则缺失或不可信，无法进入 SHADOW"))
        diagnostics.extend(candidate_errors(candidate, records=records))

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
    return cg._dedupe(diagnostics)


def _achieved_level(state_path: Path, records: Sequence[Dict[str, Any]],
                    candidate: Dict[str, Any], target: str,
                    evidence: Dict[str, Any]) -> str:
    """The level actually achieved, derived from the verified artifact."""
    if target == "SHADOW":
        return "L1"
    using_trial = target == "BOUNDED_TRIAL"
    ref = evidence.get("trial_ref" if using_trial else "evaluation_ref")
    directory = trials_dir(state_path) if using_trial else evaluations_dir(state_path)
    payload, errors = _read_artifact(directory, ref)
    if payload is None or errors:
        return "L1"
    return _recomputed_level(payload.get("gates") or {}, payload.get("verdict") or {})


def _transition_locked(state_path: Path, records: Sequence[Dict[str, Any]], policy_id: str,
                       target: str, *, evidence: Dict[str, Any], reason: str,
                       authority: Any) -> Dict[str, Any]:
    """The whole read-validate-append sequence; the caller holds `policy_lock`."""
    diagnostics = transition_errors(state_path, records, policy_id, target, evidence,
                                    authority_ok=(authority is _AUTHORITY))
    if diagnostics:
        return {"status": "INVALID", "written": False,
                "diagnostics": [item.render() for item in diagnostics],
                "codes": sorted({item.rule for item in diagnostics})}
    candidate = policy_record(records, policy_id) or {}
    previous_active = rebuild_state(records).get("active_policy_id")
    level = _achieved_level(state_path, records, candidate, target, evidence)
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
        _append(state_path, {"_schema": SCHEMA_CANDIDATE, "record": "candidate_snapshot",
                             "at": _now(), "policy_id": policy_id,
                             "rollback_target": previous_active})
    return {"status": target, "written": True, "policy_id": policy_id,
            "seq": stored["seq"], "reason": reason, "level": level, "diagnostics": []}


def transition(state_path: Path, policy_id: str, target: str, *,
               level: str = "L1", evidence: Optional[Dict[str, Any]] = None,
               reason: str = "", _authority: Any = None) -> Dict[str, Any]:
    """Public transition entry. Gated targets require the controlled promotion entries."""
    with policy_lock(state_path):
        records, _ = load_records(state_path)
        payload = dict(evidence or {})
        if reason:
            payload.setdefault("reason", reason)
        return _transition_locked(state_path, records, policy_id, target, evidence=payload,
                                  reason=reason, authority=_authority)


def rollback(state_path: Path, policy_id: str, *, to_policy_id: str, reason: str) -> Dict[str, Any]:
    """Restore an earlier valid policy; keep the failure trail; touch nothing else."""
    with policy_lock(state_path):
        records, _ = load_records(state_path)
        statuses = latest_status(records)
        diagnostics: List[cg.Diagnostic] = []
        if statuses.get(policy_id) != "ACTIVE":
            diagnostics.append(_diag("PE13", f"policy[{policy_id}]", "只有 ACTIVE 策略可以回滚"))
        target_status = statuses.get(to_policy_id)
        if policy_record(records, to_policy_id) is None:
            diagnostics.append(_diag("PE13", f"policy[{to_policy_id}]", "回滚目标不存在"))
        elif target_status not in ("SUPERSEDED", "ACTIVE"):
            diagnostics.append(_diag(
                "PE13", f"policy[{to_policy_id}]",
                f"回滚目标当前状态是 {target_status}：REJECTED / ROLLED_BACK 是终态，不得恢复"))
        if to_policy_id and to_policy_id == policy_id:
            diagnostics.append(_diag("PE13", f"policy[{policy_id}]", "回滚目标不能是策略自身"))
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
            after, _ = load_records(state_path)
            restore = _transition_locked(
                state_path, after, to_policy_id, "ACTIVE",
                evidence={"reason": f"restored by rollback from {policy_id}",
                          "restored": True},
                reason=f"restored by rollback from {policy_id}", authority=_AUTHORITY)
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
    """Whether two arms differ beyond the frozen tolerance, and in which direction."""
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
        # DIFFERENT is not BETTER. A negative delta beyond the frozen tolerance is a
        # regression and must never be read as an improvement.
        better = delta > tolerance
        worse = delta < -tolerance
        different = better or worse
        any_different = any_different or different
        block = {"delta": delta, "overlapping": overlapping,
                 "direction": "BETTER" if better else ("WORSE" if worse else "NONE"),
                 "better": better, "worse": worse,
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
    empty: Dict[str, Any] = {"verdict": "INVALID", "reasons": [], "comparison": {},
                             "benefit_dimensions": [], "reliability_degraded": [],
                             "other_degraded": [], "unobservable_decisions": 0,
                             "sample_adequate": False, "coverage": {},
                             "isolation_ok": False, "execution_record": False,
                             "note": "discovery replay 的维度各自独立，没有加权总分"}
    if not isinstance(report, dict) or not isinstance(report.get("per_arm"), dict) \
            or candidate_arm not in report["per_arm"] or control_arm not in report["per_arm"]:
        empty["reasons"] = ["不是可用的 ablation 报告：缺少 per_arm 或对照臂"]
        return empty
    declared_schema = report.get("schema") or report.get("_schema")
    if declared_schema != SCHEMA_ABLATION_REPORT:
        empty["reasons"] = [f"报告 schema 不是 {SCHEMA_ABLATION_REPORT!r}："
                            "不是可信的执行结果"]
        return empty
    comparison = distinguishable(report, candidate_arm, control_arm)
    if not comparison.get("dimensions"):
        empty["reasons"] = ["报告没有可比对的评价维度"]
        return empty

    reasons: List[str] = []
    dimensions = comparison["dimensions"]
    benefit_better = sorted(name for name, block in dimensions.items()
                            if block.get("direction") == "BETTER" and name in BENEFIT_DIMENSIONS)
    reliability_worse = sorted(name for name, block in dimensions.items()
                               if block.get("direction") == "WORSE"
                               and name in RELIABILITY_DIMENSIONS)
    other_worse = sorted(name for name, block in dimensions.items()
                         if block.get("direction") == "WORSE"
                         and name not in RELIABILITY_DIMENSIONS and name not in BENEFIT_DIMENSIONS)
    assessable = sorted(name for name, block in dimensions.items()
                        if block.get("status") not in (None, "UNASSESSABLE"))
    benefit_assessable = [name for name in BENEFIT_DIMENSIONS if name in assessable]

    rules = DEFAULT_EVALUATION_RULES
    cases = int(report.get("cases") or 0)
    runs = int(report.get("runs_per_case") or 0)
    sample_adequate = (cases >= rules["min_cases"] and runs >= rules["min_runs"]
                       and bool(assessable) and bool(benefit_assessable))
    execution_record = any(block.get("results") for block in report["per_arm"].values())
    isolation_ok = bool(execution_record) and all(
        result.get("leak_checked") and result.get("isolation_verified", True)
        for block in report["per_arm"].values() for result in block.get("results") or [])
    unobservable = int(report.get("unobservable_decisions") or 0)

    verdict = "SUPPORTED"
    if not execution_record:
        verdict = "INVALID"
        reasons.append("报告没有逐 case 执行记录：不是可信的执行结果")
    if not isolation_ok and execution_record:
        verdict = "REJECTED"
        reasons.append("存在隔离未通过的 case：无独立评价资格")
    if reliability_worse:
        verdict = "REJECTED"
        reasons.append("科学可靠性维度退化：" + ", ".join(reliability_worse)
                       + "（不得用效率收益补偿）")
    if other_worse:
        reasons.append("其他维度退化：" + ", ".join(other_worse))
    if not sample_adequate:
        if verdict == "SUPPORTED":
            verdict = "INSUFFICIENT_SAMPLE"
        reasons.append(f"样本不足（cases={cases}, runs={runs}, 可评维度 {len(assessable)}）："
                       "不得宣称策略提升")
    if verdict == "SUPPORTED" and unobservable:
        # Unobserved branches cannot be counted; the report's coverage is partial.
        verdict = "INSUFFICIENT_COVERAGE"
        reasons.append(f"{unobservable} 个决策为 NO_SUPPORT：覆盖率不足，不得计入晋升证据")
    if verdict == "SUPPORTED" and not benefit_better:
        verdict = "UNDIFFERENTIATED"
        reasons.append("没有任何预先定义的收益维度取得正向改善：差异不可区分或不是收益（DIFFERENT ≠ BETTER）")
    if verdict == "SUPPORTED":
        reasons.append("至少一个收益维度正向改善，且科学可靠性未退化")

    return {"verdict": verdict, "reasons": reasons, "comparison": comparison,
            "benefit_dimensions": benefit_better,
            "reliability_degraded": reliability_worse,
            "other_degraded": other_worse,
            "unobservable_decisions": unobservable,
            "sample_adequate": sample_adequate,
            "coverage": {"assessable": assessable, "benefit_assessable": benefit_assessable},
            "isolation_ok": isolation_ok, "execution_record": execution_record,
            "note": "discovery replay 的维度各自独立，没有加权总分"}


def evaluate_candidate(state_path: Path, policy_id: str, report: Dict[str, Any], *,
                       report_source: Optional[str] = None, reason: str = "",
                       independent: Any = None, leakage_checked: Any = None,
                       reproducible: Any = None) -> Dict[str, Any]:
    """Run the independent replay evaluation, store an artifact, then advance.

    The verdict, the gates and the achieved level are all computed from the report; the
    keyword arguments kept for call compatibility are ignored on purpose.
    """
    with policy_lock(state_path):
        records, _ = load_records(state_path)
        candidate = policy_record(records, policy_id)
        if candidate is None:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": ["未知 policy_id"], "codes": ["PE1"]}
        current_status = latest_status(records).get(policy_id)
        if current_status not in ("SHADOW", "HOLD"):
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": [f"只有 SHADOW/HOLD 可以评价，当前是 {current_status}"],
                    "codes": ["PE10"]}
        rules = evaluation_rules_errors(state_path)
        if rules:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": [item.render() for item in rules],
                    "codes": sorted({item.rule for item in rules})}
        current_rules = evaluation_rules_digest(state_path)
        if candidate.get("evaluation_rules_digest") != current_rules:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": ["候选绑定的是另一版评价规则：评价结果不可信"],
                    "codes": ["PE12"]}

        verdict = ablation_verdict(report)
        gates = {
            "independent": bool(verdict.get("execution_record") and verdict.get("isolation_ok")),
            "leakage_checked": bool(verdict.get("isolation_ok")),
            "reproducible": int(report.get("runs_per_case") or 0)
            >= DEFAULT_EVALUATION_RULES["min_runs"],
            "sample_adequate": bool(verdict.get("sample_adequate")),
            "distinguishable": bool(verdict.get("benefit_dimensions")),
            "degraded_dimensions": list(verdict.get("reliability_degraded") or []),
            "unobservable_decisions": int(verdict.get("unobservable_decisions") or 0),
            "assessable_dimensions": len(verdict.get("coverage", {}).get("assessable") or []),
            "cases": int(report.get("cases") or 0),
            "runs": int(report.get("runs_per_case") or 0),
            "runner": report.get("runner"),
        }
        payload = {
            "_schema": SCHEMA_EVALUATION,
            "policy_id": policy_id,
            "policy_signature": candidate.get("signature"),
            "policy_schema_version": candidate.get("policy_schema_version"),
            "rules_digest": current_rules,
            "report": copy.deepcopy(report),
            "report_digest": cg.digest_of(report),
            "report_source": report_source or "inline",
            "runner": report.get("runner"),
            "produced_by": "policy_evolution.evaluate_candidate",
            "evaluated_at": _now(),
            "verdict": verdict,
            "gates": gates,
            "level": _recomputed_level(gates, verdict),
        }
        ref = _store_artifact(state_path, evaluations_dir(state_path), payload)
        evidence = {"evaluation_ref": ref, "reason": reason or "; ".join(verdict["reasons"])}
        if verdict["verdict"] == "SUPPORTED":
            return _transition_locked(state_path, records, policy_id, "REPLAY_EVALUATED",
                                      evidence=evidence, reason=evidence["reason"],
                                      authority=_AUTHORITY)
        if verdict["verdict"] in ("INVALID", "REJECTED"):
            return _transition_locked(state_path, records, policy_id, "REJECTED",
                                      evidence=evidence, reason=evidence["reason"],
                                      authority=_AUTHORITY)
        return _transition_locked(state_path, records, policy_id, "HOLD",
                                  evidence=evidence, reason=evidence["reason"],
                                  authority=_AUTHORITY)


def recorded_evaluation(records: Sequence[Dict[str, Any]], policy_id: str) -> Dict[str, Any]:
    """The merged gate evidence actually recorded for this policy's transitions."""
    merged: Dict[str, Any] = {}
    for record in records:
        if record.get("record") != "transition" or record.get("policy_id") != policy_id:
            continue
        if record.get("to") not in ("REPLAY_EVALUATED", "BOUNDED_TRIAL", "VALIDATED"):
            continue
        merged.update({key: value for key, value in (record.get("evidence") or {}).items()})
        merged.setdefault("level", record.get("level"))
    return merged


def begin_bounded_trial(state_path: Path, policy_id: str, *,
                        dispatch_evidence: Dict[str, Any],
                        budget_expanded: bool = False,
                        hard_gates_unchanged: bool = True) -> Dict[str, Any]:
    """Enter BOUNDED_TRIAL with a stored trial artifact (the trusted dispatch record)."""
    diagnostics: List[str] = []
    codes: List[str] = []
    if not isinstance(dispatch_evidence, dict) or not dispatch_evidence:
        diagnostics.append("试运行需要非空的 dispatch_evidence")
        codes.append("PE11")
    if budget_expanded:
        diagnostics.append("试运行不得扩大原有资源预算")
        codes.append("PE11")
    if not hard_gates_unchanged:
        diagnostics.append("试运行不得改变硬门禁")
        codes.append("PE11")
    if diagnostics:
        return {"status": "INVALID", "written": False, "policy_id": policy_id,
                "diagnostics": diagnostics, "codes": sorted(set(codes))}
    with policy_lock(state_path):
        records, _ = load_records(state_path)
        candidate = policy_record(records, policy_id)
        if candidate is None:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": ["未知 policy_id"], "codes": ["PE1"]}
        current_rules = evaluation_rules_digest(state_path)
        payload = {
            "_schema": SCHEMA_TRIAL,
            "policy_id": policy_id,
            "policy_signature": candidate.get("signature"),
            "rules_digest": current_rules,
            "dispatch_evidence": copy.deepcopy(dispatch_evidence),
            "budget_expanded": bool(budget_expanded),
            "hard_gates_unchanged": bool(hard_gates_unchanged),
            "produced_by": "policy_evolution.begin_bounded_trial",
            "recorded_at": _now(),
            "verdict": {"verdict": "SUPPORTED"},
            "gates": {"assessable_dimensions": 2, "cases": 1, "runs": 1,
                      "runner": "bounded-trial"},
        }
        payload["level"] = _recomputed_level(payload["gates"], payload["verdict"])
        ref = _store_artifact(state_path, trials_dir(state_path), payload)
        return _transition_locked(state_path, records, policy_id, "BOUNDED_TRIAL",
                                  evidence={"trial_ref": ref, "reason": "bounded trial"},
                                  reason="bounded trial", authority=_AUTHORITY)


def validate_candidate(state_path: Path, policy_id: str, *,
                       evaluation_ref: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """VALIDATED requires an L3 evaluation artifact bound to this policy."""
    with policy_lock(state_path):
        records, _ = load_records(state_path)
        if policy_record(records, policy_id) is None:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": ["未知 policy_id"], "codes": ["PE1"]}
        ref = evaluation_ref
        if not isinstance(ref, dict):
            artifact = latest_evaluation_artifact(state_path, policy_id, records)
            if artifact is None:
                return {"status": "INVALID", "written": False, "policy_id": policy_id,
                        "diagnostics": ["没有可用的 L3 评价产物：不能验证"],
                        "codes": ["PE11"]}
            ref = artifact["ref"]
        return _transition_locked(state_path, records, policy_id, "VALIDATED",
                                  evidence={"evaluation_ref": ref, "reason": "L3 evaluation"},
                                  reason="L3 evaluation", authority=_AUTHORITY)


def promote_to_active(state_path: Path, policy_id: str,
                      evaluation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """ACTIVE promotion: L3 artifact + frozen-rule integrity + scope evidence."""
    evaluation = dict(evaluation or {})
    with policy_lock(state_path):
        records, _ = load_records(state_path)
        candidate = policy_record(records, policy_id)
        if candidate is None:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": ["未知 policy_id"], "codes": ["PE1"]}
        artifact = latest_evaluation_artifact(state_path, policy_id, records)
        if artifact is None:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": ["没有 L3 评价产物：不得晋升 ACTIVE"], "codes": ["PE11"]}
        return _transition_locked(
            state_path, records, policy_id, "ACTIVE",
            evidence={"evaluation_ref": artifact["ref"],
                      "scope_evidence_ok": bool(evaluation.get("scope_evidence_ok", True)),
                      "reason": evaluation.get("reason") or "independent L3 evaluation"},
            reason=evaluation.get("reason") or "independent L3 evaluation",
            authority=_AUTHORITY)


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
            advice["island"] = (advice.get("island") or change.get("island")
                                or change.get("problem_structure"))
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

    Fail-closed provenance: only a source **stamped by `propose()`** (`origin_stamped`) counts.
    A candidate-declared `source_route`/`source_project` is self-attested and ignored, so a
    candidate cannot name the target route as its own origin to skip the gate. When the caller
    supplies a `current_route` (or passes `require_transfer=True`), the gate must not silently
    return `NOT_REQUIRED`: an absent/unstamped source, or an absent `current_route` when a
    stamped source exists, is a BLOCK. `require_transfer=True` forces the PT* rules to decide.
    """
    def blocked(reason: str) -> Dict[str, Any]:
        return {"required": True, "status": "BLOCK", "reasons": [reason], "similarity": None}

    if not isinstance(candidate, dict):
        return blocked("策略候选不是对象；无法判定跨项目迁移边界（fail-closed 阻塞）")
    raw_scope = candidate.get("scope")
    scope = raw_scope if isinstance(raw_scope, dict) else {}
    # Provenance must be STAMPED by `propose()`. A candidate-declared source is not
    # provenance: letting it win meant a policy could name the target route as its own origin
    # and skip the structural transfer gate entirely.
    stamped = candidate.get("origin_stamped") is True
    source = (candidate.get("source_route") or candidate.get("source_project")) if stamped else None
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
        "freeze-rules", "propose", "list", "show", "transition", "evaluate", "trial",
        "validate", "promote", "rollback", "state", "advice"))
    parser.add_argument("--state", help="path to research-state.json")
    parser.add_argument("--policy", help="path to a candidate JSON file (or - for stdin)")
    parser.add_argument("--policy-id")
    parser.add_argument("--to")
    parser.add_argument("--to-policy-id")
    parser.add_argument("--reason", default="")
    parser.add_argument("--level", default="L1")
    parser.add_argument("--report", help="path to a replay ablation report JSON")
    parser.add_argument("--dispatch", help="trial: dispatch evidence as JSON")
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
        if args.to in GATED_TARGETS:
            # The CLI must not be a way around the promotion gates.
            return _emit({"status": "INVALID", "policy_id": args.policy_id,
                          "diagnostics": [f"{args.to} 只能由受控晋升入口完成："
                                          "evaluate / trial / validate / promote"],
                          "codes": ["PE11"]}, EXIT_HARD)
        evidence = json.loads(args.reason) if args.reason.startswith("{") else {}
        result = transition(state_path, args.policy_id, args.to, level=args.level,
                            evidence=evidence, reason="" if evidence else args.reason)
        return _emit(result, EXIT_OK if result["written"] else EXIT_HARD)
    if args.command in ("trial", "validate", "promote"):
        if not args.policy_id:
            return _emit({"status": "INVALID", "errors": ["需要 --policy-id"]}, EXIT_ERROR)
        options = json.loads(args.reason) if args.reason.startswith("{") else {}
        if args.command == "trial":
            dispatch = json.loads(args.dispatch) if args.dispatch else {"dispatched": True}
            result = begin_bounded_trial(state_path, args.policy_id,
                                         dispatch_evidence=dispatch,
                                         budget_expanded=bool(options.get("budget_expanded")),
                                         hard_gates_unchanged=bool(
                                             options.get("hard_gates_unchanged", True)))
        elif args.command == "validate":
            result = validate_candidate(state_path, args.policy_id)
        else:
            result = promote_to_active(state_path, args.policy_id, options)
        return _emit(result, EXIT_OK if result.get("written") else EXIT_HARD)
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


def _arm_block(mean_high, mean_low=None, benefit=None):
    """An arm with a per-case execution record; `benefit` controls the benefit dimensions."""
    low = mean_high - 0.4 if mean_low is None else mean_low
    gain = mean_high if benefit is None else benefit
    return {"dimensions": {
        "mechanistic_understanding": {"mean": 0.5, "min": 0.4, "max": 0.6},
        "prediction_quality": {"mean": low, "min": low - 0.1, "max": low + 0.1},
        "intervention_quality": {"mean": mean_high, "min": mean_high - 0.05,
                                 "max": mean_high + 0.05},
        "scientific_novelty": {"mean": 0.5, "min": 0.5, "max": 0.5},
        "search_efficiency": {"mean": gain, "min": gain - 0.05, "max": gain + 0.05},
        "stagnation_recovery": {"mean": gain, "min": gain - 0.05, "max": gain + 0.05},
        "memory_accumulation": {"mean": gain, "min": gain - 0.05, "max": gain + 0.05},
    },
        "results": [{"case_id": f"C{i}", "leak_checked": True, "isolation_verified": True,
                     "evaluation": {"evidence_support": {"class": "OBSERVED"}}}
                    for i in range(5)],
        "evidence_support": {"OBSERVED": 5}}


def _report(sufficient=True, unobservable=0, flat=False):
    """A supported report: a real benefit gain, reliability intact, an execution record."""
    candidate = _arm_block(0.5 if flat else 0.9, benefit=0.5 if flat else 0.9)
    control = _arm_block(0.5 if flat else 0.3, benefit=0.5 if flat else 0.3)
    return {"schema": "research-idea-pipeline/replay-ablation@1",
            "sufficient_sample": sufficient, "unobservable_decisions": unobservable,
            "delta_vs_baseline": {}, "per_arm": {"rsi_full": candidate, "full_cie": control},
            "runner": "offline CIE runner (no model calls)",
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
        undifferentiated = evaluate_candidate(state_path, "P-FLAT", _report(flat=True))
        check("indistinguishable arms are not promoted",
              undifferentiated["status"] == "HOLD")

        expanded = begin_bounded_trial(state_path, "P-1",
                                       dispatch_evidence={"dispatched": "R2"},
                                       budget_expanded=True)
        check("expanding the budget during a trial is refused",
              expanded["status"] == "INVALID" and "PE11" in expanded["codes"])
        trial = begin_bounded_trial(state_path, "P-1",
                                    dispatch_evidence={"dispatched": "R2"})
        check("bounded trial does not expand the budget", trial["status"] == "BOUNDED_TRIAL")
        bypass = transition(state_path, "P-1", "VALIDATED", level="L3",
                            evidence={"independent": True, "distinguishable": True,
                                      "degraded_dimensions": []})
        check("raw transition cannot validate (controlled entry required)",
              bypass["status"] == "INVALID" and "PE11" in bypass["codes"])

        validated = validate_candidate(state_path, "P-1")
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
        begin_bounded_trial(state_path, "P-2",
                                     dispatch_evidence={"dispatched": "R2"})
        validate_candidate(state_path, "P-2")
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
