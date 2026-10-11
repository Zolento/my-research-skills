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
* Nothing reaches `ACTIVE` without a leakage-checked, reproducible evaluation (`PE11`) and,
  for L3, an independently executed research-validation credential plus a human approval
  (`PE15`); synthetic replay evidence is capped at **L2** and comparison fairness is enforced
  (`PE16`). The evaluation rules must be unchanged since the candidate was generated (`PE12`).
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
import hashlib
import hmac
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
SCHEMA_RESEARCH_VALIDATION = "research-idea-pipeline/policy-research-validation@1"
SCHEMA_APPROVAL = "research-idea-pipeline/l3-approval@1"
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
    if rules is None:
        payload = copy.deepcopy(DEFAULT_EVALUATION_RULES)
    else:
        # A partial custom set is completed from the defaults, then validated: freezing a
        # malformed set must fail here, not with a KeyError deep in the promotion path.
        payload = copy.deepcopy(DEFAULT_EVALUATION_RULES)
        if isinstance(rules, dict):
            payload.update(copy.deepcopy(rules))
        else:
            payload = copy.deepcopy(rules)
    problems = _rule_schema_errors(payload)
    if problems:
        return {"status": "INVALID", "path": str(path), "digest": None, "rules": None,
                "errors": [f"评价规则结构非法：{problem}" for problem in problems]}
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
    diagnostics = [_diag("PE1", f"policy[{candidate.get('policy_id')}]", message)
                   for message in policy_id_errors(candidate.get("policy_id"))]
    diagnostics.extend(candidate_errors(candidate, records=records,
                                        trajectory_support=trajectory_support,
                                        rules_digest=rules_digest))
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

_REQUIRED_RULE_KEYS = ("dimensions", "min_cases", "min_runs", "delta_tolerance")


def _rule_schema_errors(rules: Any) -> List[str]:
    """Structural problems in a rule set.

    A frozen rule set missing `min_cases`/`min_runs`/`dimensions`/`delta_tolerance` used to
    reach the promotion path and raise an uncaught KeyError instead of a diagnosable refusal.
    """
    if not isinstance(rules, dict):
        return ["评价规则不是对象"]
    problems: List[str] = []
    for key in _REQUIRED_RULE_KEYS:
        if key not in rules:
            problems.append(f"冻结规则缺少必需字段 {key!r}")
    dimensions = rules.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions \
            or not all(isinstance(item, str) and item.strip() for item in dimensions):
        problems.append("dimensions 必须是非空字符串列表")
    for key in ("min_cases", "min_runs"):
        value = rules.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            problems.append(f"{key} 必须是 >=1 的整数")
    tolerance = rules.get("delta_tolerance")
    if not isinstance(tolerance, (int, float)) or isinstance(tolerance, bool) \
            or not tolerance >= 0:
        problems.append("delta_tolerance 必须是 >=0 的数")
    return problems


def frozen_rules(state_path: Path) -> Optional[Dict[str, Any]]:
    """The frozen rule *content*, or None when it is absent or inconsistent.

    The evaluation must actually run with these parameters: reading
    `DEFAULT_EVALUATION_RULES` while comparing three hashes let a custom frozen rule set
    pass every check while the evaluation used different thresholds.
    """
    path = rules_path(state_path)
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, OSError, json.JSONDecodeError):
        return None
    rules = document.get("rules") if isinstance(document, dict) else None
    if not isinstance(rules, dict) or document.get("digest") != cg.digest_of(rules):
        return None
    if _rule_schema_errors(rules):
        return None
    return rules


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
    schema_problems = _rule_schema_errors(document["rules"])
    if schema_problems:
        return [_diag("PE12", "policy.evaluation-rules",
                      "评价规则结构非法：" + "；".join(schema_problems))]
    return []


# ---------------------------------------------------------------------------
# Store lock: a transition is a multi-record operation
# ---------------------------------------------------------------------------

POLICY_LOCK_NAME = ".policy.lock"
EVALUATIONS_DIRNAME = "evaluations"
TRIALS_DIRNAME = "trials"
APPROVALS_DIRNAME = "approvals"

#: Axes the two arms must agree on (the intervention is declared in `contrast_axes`).
_REQUIRED_EQUIVALENCE_AXES = ("model", "harness", "tools", "visible_data", "budget", "task_ids")

#: Identities that must never appear as an "independent" executor.
_SELF_IDENTITIES = ("policy_evolution", "research-agent", "research_agent", "self",
                    "agent", "system", "skill")

#: Pre-registered dimensions. A promotion needs a *positive* improvement on a benefit
#: dimension; a reliability dimension may never regress. Both sets are frozen here so a
#: report cannot choose what counts as an improvement. Every scientific dimension is in the
#: non-compensable set: `mechanistic_understanding` was missing, so a policy could buy
#: search efficiency by weakening the mechanistic account and still be promoted.
BENEFIT_DIMENSIONS: Tuple[str, ...] = ("search_efficiency", "stagnation_recovery",
                                       "memory_accumulation")
RELIABILITY_DIMENSIONS: Tuple[str, ...] = ("mechanistic_understanding", "prediction_quality",
                                           "intervention_quality", "scientific_novelty")

#: Targets that may only be reached through a controlled entry point.
GATED_TARGETS: Tuple[str, ...] = ("REPLAY_EVALUATED", "BOUNDED_TRIAL", "VALIDATED", "ACTIVE")
LEVEL_RANK: Dict[str, int] = {"L1": 1, "L2": 2, "L3": 3}
TARGET_LEVEL: Dict[str, str] = {"SHADOW": "L1", "REPLAY_EVALUATED": "L2",
                                "BOUNDED_TRIAL": "L2", "VALIDATED": "L3", "ACTIVE": "L3"}

#: Which credential class a gated target accepts. Replay (synthetic/offline) evidence and
#: real-research validation evidence are different credentials: a replay artifact can never
#: be presented where an L3 research validation is required.
TARGET_ARTIFACT_SCHEMA: Dict[str, str] = {
    "REPLAY_EVALUATED": SCHEMA_EVALUATION,
    "BOUNDED_TRIAL": SCHEMA_TRIAL,
    "VALIDATED": SCHEMA_RESEARCH_VALIDATION,
    "ACTIVE": SCHEMA_RESEARCH_VALIDATION,
}

#: Directories that may never hold a "real task source" for an L3 credential.
_SYNTHETIC_SOURCE_HINTS = ("examples", "fixtures", "replay", "synthetic", ".dev")

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


#: A policy id becomes part of an artifact filename and of diagnostic paths.
_POLICY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def policy_id_errors(policy_id: Any) -> List[str]:
    """Reject ids that are not a single safe path segment.

    `"a/b"` reached `_store_artifact` and raised a raw FileNotFoundError; a NUL byte raised
    ValueError. No diagnostic path may escape the policy store.
    """
    if not isinstance(policy_id, str) or not policy_id:
        return ["policy_id 必须是非空字符串"]
    if not _POLICY_ID_RE.match(policy_id):
        return [f"policy_id {policy_id!r} 非法：只允许字母数字与 . _ -，且必须单段（≤64 字符）"]
    if policy_id in (".", "..") or ".." in policy_id:
        return [f"policy_id {policy_id!r} 非法：不得包含路径语义"]
    return []


def _discard_artifact(path: Optional[str]) -> None:
    """Best-effort removal of an artifact written for a transition that was refused."""
    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


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
    problems = policy_id_errors(payload.get("policy_id"))
    if problems:
        raise cg.CognitionError("拒绝写入评价产物：" + "；".join(problems))
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


def _file_digest(path: Path) -> str:
    """SHA-256 over a file's raw bytes (content digests are not JSON values)."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _recompute_arm_dimensions(results: Sequence[Dict[str, Any]],
                              dimensions: Sequence[str]) -> Dict[str, Any]:
    """Recompute the per-arm dimension summary from the per-case measurements.

    The declared means used to be taken on faith. A report could state whatever numbers it
    liked as long as it also carried a syntactically valid `results` list.
    """
    summary: Dict[str, Any] = {}
    for name in dimensions:
        values: List[float] = []
        for row in results:
            metrics = (row.get("evaluation") or {}).get("metrics") if isinstance(row, dict) else None
            metric = metrics.get(name) if isinstance(metrics, dict) else None
            if isinstance(metric, dict) and metric.get("value") is not None:
                values.append(metric["value"])
        summary[name] = {"mean": round(sum(values) / len(values), 4) if values else None,
                         "min": min(values) if values else None,
                         "max": max(values) if values else None,
                         "observable_cases": len(values), "total_cases": len(results)}
    return summary


def _safe_int(value: Any, default: int = 0) -> int:
    """`int(value)` for values that may be NaN/inf/strings/None.

    A report could carry `unobservable_decisions: NaN`, and `int(NaN)` raised a raw
    ValueError out of the evaluation path instead of producing a diagnosable refusal.
    """
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number or number in (float("inf"), float("-inf")):
        return default
    return int(number)


def _numbers_differ(left: Any, right: Any) -> bool:
    if left is None and right is None:
        return False
    if left is None or right is None:
        return True
    try:
        left_number, right_number = float(left), float(right)
    except (TypeError, ValueError):
        return left != right
    # NaN/inf must not be treated as "matching": every NaN comparison is False, which made
    # the consistency check vacuous for a declared NaN.
    if left_number != left_number or right_number != right_number:
        return True
    if left_number in (float("inf"), float("-inf")) \
            or right_number in (float("inf"), float("-inf")):
        return left_number != right_number
    return abs(left_number - right_number) > 1e-9


def audit_report(report: Dict[str, Any], *, candidate: Optional[Dict[str, Any]] = None,
                 rules: Optional[Dict[str, Any]] = None,
                 current_rules_digest: Optional[str] = None) -> Dict[str, Any]:
    """Recompute a report's conclusions from its own execution records.

    Returns `{"errors": [...], "report": normalized, "verdict": {...}}`. A report is only
    usable when `errors` is empty: the per-case measurements must reproduce the declared
    means, the case/run counts must match, every record must carry an explicit isolation and
    leak verdict, and the binding the report declares (if any) must match the candidate.
    """
    rules = rules or DEFAULT_EVALUATION_RULES
    dimensions = list(rules.get("dimensions") or DEFAULT_EVALUATION_RULES["dimensions"])
    errors: List[str] = []
    if not isinstance(report, dict) or not isinstance(report.get("per_arm"), dict):
        return {"errors": ["不是 ablation 报告：缺少 per_arm"], "report": None, "verdict": None}
    if (report.get("schema") or report.get("_schema")) != SCHEMA_ABLATION_REPORT:
        errors.append(f"报告 schema 不是 {SCHEMA_ABLATION_REPORT!r}：不是可信的执行结果")
    per_arm = report["per_arm"]
    for arm in ("rsi_full", "full_cie"):
        if arm not in per_arm:
            errors.append(f"缺少必需的臂 {arm!r}")
    if not str(report.get("runner") or "").strip():
        errors.append("报告没有具名 runner：无法证明评价由谁执行")
    cases = report.get("cases")
    runs = report.get("runs_per_case")
    if not isinstance(cases, int) or cases < 1:
        errors.append(f"cases 非法：{cases!r}")
        cases = 0
    if not isinstance(runs, int) or runs < 1:
        errors.append(f"runs_per_case 非法：{runs!r}")
        runs = 1

    if candidate:
        declared_id = report.get("policy_id")
        if declared_id is not None and declared_id != candidate.get("policy_id"):
            errors.append(f"报告声明的 policy_id {declared_id!r} 与候选不一致")
        declared_sig = report.get("policy_signature")
        if declared_sig is not None and declared_sig != candidate.get("signature"):
            errors.append("报告声明的 policy_signature 与候选不一致")
        declared_rules = report.get("rules_digest")
        if declared_rules is not None and current_rules_digest is not None \
                and declared_rules != current_rules_digest:
            errors.append("报告声明的 rules_digest 与冻结评价规则不一致")

    normalized: Dict[str, Any] = {"schema": SCHEMA_ABLATION_REPORT, "cases": cases,
                                  "runs_per_case": runs, "runner": report.get("runner"),
                                  "policy_id": report.get("policy_id"),
                                  "policy_signature": report.get("policy_signature"),
                                  "rules_digest": report.get("rules_digest"),
                                  "unobservable_decisions": _safe_int(
                                      report.get("unobservable_decisions")),
                                  "delta_vs_baseline": {}, "per_arm": {}}
    case_sets: Dict[str, set] = {}
    for arm, block in per_arm.items():
        if not isinstance(block, dict):
            errors.append(f"{arm} 的块不是对象")
            continue
        results = block.get("results")
        if not isinstance(results, list) or not results:
            errors.append(f"{arm} 没有逐 case 执行记录：不是可信的执行结果")
            continue
        for row in results:
            if not isinstance(row, dict):
                errors.append(f"{arm} 存在非对象的执行记录")
                continue
            if row.get("leak_checked") is not True:
                errors.append(f"{arm} 的 case {row.get('case_id')!r} 缺少泄漏隔离证明"
                              "（必须显式为 true）")
            if row.get("isolation_verified") is not True:
                errors.append(f"{arm} 的 case {row.get('case_id')!r} 缺少隔离验证证明"
                              "（missing 不再默认为通过）")
        recomputed = _recompute_arm_dimensions(results, dimensions)
        declared = block.get("dimensions") if isinstance(block.get("dimensions"), dict) else {}
        for name in dimensions:
            stated = declared.get(name) if isinstance(declared.get(name), dict) else {}
            for key in ("mean", "min", "max"):
                if _numbers_differ(stated.get(key), recomputed[name][key]):
                    errors.append(
                        f"{arm}.{name}.{key} 与逐 case 执行记录重算结果不一致"
                        f"（声明 {stated.get(key)!r} / 重算 {recomputed[name][key]!r}）")
        ids = {str(row.get("case_id")) for row in results if isinstance(row, dict)}
        case_sets[arm] = ids
        if cases and len(ids) != cases:
            errors.append(f"{arm} 的 case 数 {len(ids)} 与声明的 {cases} 不一致")
        if cases and runs and len(results) != cases * runs:
            errors.append(f"{arm} 的执行记录数 {len(results)} 与 cases×runs "
                          f"({cases}×{runs}) 不一致")
        normalized["per_arm"][arm] = {"dimensions": recomputed, "results": results,
                                      "evidence_support": block.get("evidence_support") or {}}
    if len(case_sets) > 1 and len(set(map(frozenset, case_sets.values()))) > 1:
        errors.append("各臂执行的 case 集合不一致：无法配对比较")
    # The unobserved count is recomputed from the execution records; a report could otherwise
    # claim full coverage while every record said NO_SUPPORT.
    recomputed_unobservable = 0
    for block in normalized["per_arm"].values():
        for row in block["results"]:
            support = ((row.get("evaluation") or {}).get("evidence_support") or {}).get("class")
            if support == "NO_SUPPORT":
                recomputed_unobservable += 1
    declared_unobservable = _safe_int(report.get("unobservable_decisions"))
    if declared_unobservable != recomputed_unobservable:
        errors.append(
            f"unobservable_decisions 声明 {declared_unobservable}，但执行记录（NO_SUPPORT）"
            f"重算为 {recomputed_unobservable}")
    normalized["unobservable_decisions"] = recomputed_unobservable
    if errors:
        return {"errors": errors, "report": None, "verdict": None}
    verdict = ablation_verdict(normalized, rules=rules)
    return {"errors": [], "report": normalized, "verdict": verdict}


def _validation_errors(state_path: Path, payload: Dict[str, Any], *,
                       candidate: Dict[str, Any], rules: Dict[str, Any],
                       current_rules_digest: Optional[str],
                       artifact_path: Optional[str] = None) -> Dict[str, Any]:
    """Verify an L3 research-validation credential: provenance, independence, dispatch.

    Synthetic sources, self-executed results and missing isolation proofs are refused. The
    credential is bound to the actual dispatch record so it cannot be produced before the
    policy was actually trialled.
    """
    policy_id = candidate.get("policy_id")
    path = f"policy[{policy_id}]"
    diagnostics: List[cg.Diagnostic] = []
    if not isinstance(payload, dict):
        return {"errors": [_diag("PE11", path, "科研验证凭证不是对象")], "report": None,
                "verdict": None}

    def bad(message: str) -> None:
        diagnostics.append(_diag("PE11", path, message))

    def unfair(message: str) -> None:
        diagnostics.append(_diag("PE16", path, message))

    if payload.get("_schema") != SCHEMA_RESEARCH_VALIDATION:
        bad(f"凭证 schema 不是 {SCHEMA_RESEARCH_VALIDATION!r}")
    if payload.get("policy_id") != policy_id:
        bad("凭证绑定到另一个策略")
    if payload.get("policy_signature") != candidate.get("signature"):
        bad("凭证绑定的策略版本与当前候选不一致")
    if current_rules_digest is None:
        bad("冻结评价规则缺失或不可信")
    elif payload.get("rules_digest") != current_rules_digest:
        bad("凭证绑定的评价规则与当前冻结规则不一致")

    provenance = payload.get("task_provenance")
    if not isinstance(provenance, dict):
        bad("缺少 task_provenance：无法证明任务来源")
    else:
        if provenance.get("synthetic") is not False:
            bad("任务来源必须显式声明 synthetic=false（合成来源不得用于 L3）")
        if not str(provenance.get("task_id") or "").strip():
            bad("task_provenance 缺少 task_id")
        source = provenance.get("source")
        source_path = Path(str(source)).expanduser() if isinstance(source, str) else None
        if source_path is None or not source_path.is_file():
            bad("任务来源文件不存在或不可读")
        else:
            resolved = source_path.resolve()
            lowered = resolved.as_posix().lower()
            if any(f"/{hint}/" in lowered or lowered.endswith(f"/{hint}")
                   for hint in _SYNTHETIC_SOURCE_HINTS):
                bad(f"任务来源位于合成/示例目录（{resolved}），不得用于 L3 科研验证")
            if provenance.get("source_digest") != _file_digest(resolved):
                bad("任务来源摘要与文件内容不一致：来源被改写")

    evidence = payload.get("execution_evidence")
    if not isinstance(evidence, dict):
        bad("缺少 execution_evidence：无法复核执行过程")
    else:
        evidence_path = Path(str(evidence.get("path") or "")).expanduser()
        if not evidence_path.is_file():
            bad("执行证据文件不存在或不可读")
        elif evidence.get("digest") != _file_digest(evidence_path):
            bad("执行证据摘要与文件内容不一致")

    dispatch = payload.get("dispatch_ref")
    if not isinstance(dispatch, dict):
        bad("缺少 dispatch_ref：L3 凭证必须绑定到实际派遣记录（先完成有限试运行）")
    else:
        trial, trial_errors = _read_artifact(trials_dir(state_path), dispatch)
        if trial is None:
            bad("dispatch_ref 无法解析到试运行派遣记录：" + "；".join(trial_errors))
        elif trial.get("policy_id") != policy_id:
            bad("dispatch_ref 指向另一个策略的派遣记录")

    # Accept both the submitted credential (top-level per_arm) and the stored artifact,
    # whose records live under `report`.
    source = payload if isinstance(payload.get("per_arm"), dict) else (payload.get("report") or {})
    per_arm = source.get("per_arm")
    cases = source.get("cases", payload.get("cases"))
    runs = source.get("runs_per_case", payload.get("runs_per_case"))
    runner = source.get("runner") or payload.get("runner")
    if not isinstance(per_arm, dict) or len(per_arm) < 2:
        bad("科研验证至少需要两个臂（候选与对照）")
        return {"errors": diagnostics, "report": None, "verdict": None}
    # The candidate/control roles must be declared. Inferring them would let a regression be
    # read as an improvement by swapping the comparison direction.
    candidate_arm = payload.get("candidate_arm") or source.get("candidate_arm")
    control_arm = payload.get("control_arm") or source.get("control_arm")
    if not isinstance(candidate_arm, str) or candidate_arm not in per_arm:
        bad("必须显式声明 candidate_arm，且该臂必须在 per_arm 中")
    if not isinstance(control_arm, str) or control_arm not in per_arm:
        bad("必须显式声明 control_arm，且该臂必须在 per_arm 中")
    if isinstance(candidate_arm, str) and candidate_arm == control_arm:
        bad("candidate_arm 与 control_arm 不能是同一个臂")
    executors = [str(block.get("executor") or "").strip()
                 for block in per_arm.values() if isinstance(block, dict)]
    if any(not executor for executor in executors):
        bad("每个臂都必须记录 executor")
    elif len(set(executors)) < 2:
        bad("候选臂与对照臂必须由不同的 executor 独立执行（不得自评）")
    # A name is not an identity, but the policy's own route/agent must never be its evaluator.
    self_names = set(_SELF_IDENTITIES)
    self_names.add(Path(state_path).expanduser().parent.name.strip().lower())
    self_names.add(str(cg.route_of(Path(state_path))).strip().lower())
    declared_route = str(candidate.get("source_route") or "").strip().lower()
    if declared_route:
        self_names.add(declared_route)
    for arm, block in per_arm.items():
        executor = str((block or {}).get("executor") or "").strip().lower()
        if executor and executor in self_names:
            bad(f"{arm} 的 executor {executor!r} 就是策略自身：不构成独立评价")

    if not isinstance(cases, int) or cases < 1:
        bad(f"cases 非法：{cases!r}")
    if not isinstance(runs, int) or runs < 1:
        bad(f"runs_per_case 非法：{runs!r}")
    if not str(runner or "").strip():
        bad("缺少具名 runner")

    dimensions = list(rules.get("dimensions") or DEFAULT_EVALUATION_RULES["dimensions"])
    case_sets: Dict[str, set] = {}
    normalized: Dict[str, Any] = {"schema": SCHEMA_ABLATION_REPORT,
                                  "cases": cases if isinstance(cases, int) else 0,
                                  "runs_per_case": runs if isinstance(runs, int) else 1,
                                  "runner": runner,
                                  "candidate_arm": candidate_arm,
                                  "control_arm": control_arm,
                                  "policy_id": policy_id,
                                  "policy_signature": candidate.get("signature"),
                                  "rules_digest": current_rules_digest,
                                  "unobservable_decisions": 0, "delta_vs_baseline": {},
                                  "per_arm": {}}
    for arm, block in per_arm.items():
        results = block.get("results") if isinstance(block, dict) else None
        if not isinstance(results, list) or not results:
            bad(f"{arm} 没有逐 case 执行记录")
            continue
        for row in results:
            if not isinstance(row, dict) or row.get("isolation_verified") is not True:
                bad(f"{arm} 的 case 缺少隔离验证证明（必须显式为 true）")
        # Keep the executor with the arm: the stored credential must still prove that the
        # candidate arm and the control were run by different parties.
        normalized["per_arm"][arm] = {
            "dimensions": _recompute_arm_dimensions(results, dimensions),
            "results": results, "evidence_support": {},
            "executor": block.get("executor") if isinstance(block, dict) else None}
        if isinstance(cases, int) and cases >= 1:
            ids = {str(row.get("case_id")) for row in results if isinstance(row, dict)}
            if len(ids) != cases:
                bad(f"{arm} 的 case 数 {len(ids)} 与声明的 {cases} 不一致")
            if isinstance(runs, int) and runs >= 1 and len(results) != cases * runs:
                bad(f"{arm} 的执行记录数 {len(results)} 与 cases×runs "
                    f"({cases}×{runs}) 不一致")
            case_sets[arm] = ids
    if len(case_sets) > 1 and len(set(map(frozenset, case_sets.values()))) > 1:
        bad("各臂执行的 case 集合不一致：不存在可配对的对照")
    equivalence = payload.get("equivalence")
    if equivalence is None and isinstance(payload.get("report"), dict):
        equivalence = payload["report"].get("equivalence")
    for message in _equivalence_errors(equivalence, list(per_arm), case_sets,
                                       candidate_arm=candidate_arm,
                                       control_arm=control_arm):
        unfair(message)
    diagnostics.extend(_dispatch_reuse_errors(state_path, payload.get("dispatch_ref"),
                                              str(policy_id), exclude_path=artifact_path))
    if diagnostics:
        return {"errors": diagnostics, "report": None, "verdict": None}
    verdict = ablation_verdict(normalized, candidate_arm=candidate_arm,
                               control_arm=control_arm, rules=rules)
    if verdict.get("verdict") != "SUPPORTED":
        # Refuse before storing: a credential the very next gate rejects must not be written
        # to the store as if it were usable evidence.
        diagnostics.append(_diag(
            "PE11", path,
            f"科研验证结论是 {verdict.get('verdict')!r}，不是 SUPPORTED："
            + "；".join(verdict.get("reasons") or [])))
        return {"errors": diagnostics, "report": None, "verdict": None}
    return {"errors": [], "report": normalized, "verdict": verdict}


def _attested_projects(state_path: Path) -> set:
    """Projects with at least one trajectory carrying both a decision and a qualified outcome."""
    trail = Path(state_path).expanduser().parent / dt.TRAJECTORY_NAME
    if not trail.is_file():
        return set()
    records, _ = dt.load_records(trail, tolerant=True)
    decided = {str(item.get("trajectory_id")) for item in records
               if item.get("record") == "decision" and item.get("trajectory_id")}
    qualified = {str(item.get("trajectory_id")) for item in records
                 if item.get("record") == "outcome" and item.get("trajectory_id")
                 and item.get("evidence_qualification") == "qualified"}
    attested = set()
    for item in records:
        if item.get("record") != "outcome":
            continue
        ident = str(item.get("trajectory_id"))
        if ident in decided and ident in qualified:
            project = item.get("project") or item.get("route")
            if isinstance(project, str) and project.strip():
                attested.add(project.strip())
    return attested


def _recomputed_level(gates: Dict[str, Any], verdict: Dict[str, Any], *,
                      schema: Optional[str] = None,
                      rules: Optional[Dict[str, Any]] = None) -> str:
    """The level an artifact's own evidence supports — never the level it claims.

    The credential class caps the level: synthetic/offline replay evidence is L2 at most, and
    only a real-research validation credential can be L3.
    """
    rules = rules or DEFAULT_EVALUATION_RULES
    if schema == SCHEMA_TRIAL:
        # A bounded trial is a *dispatch* record, not an evaluation verdict: it earns L2 only
        # when it records the dispatch and keeps the budget and the hard gates unchanged.
        gates = gates or {}
        safe = (bool(gates.get("dispatch_record"))
                and not gates.get("budget_expanded")
                and bool(gates.get("hard_gates_unchanged")))
        return "L2" if safe else "L1"
    if schema == SCHEMA_RESEARCH_VALIDATION:
        gates = gates or {}
        if (verdict or {}).get("verdict") != "SUPPORTED" or not gates.get("provenance_ok"):
            return "L1"
        return "L3" if gates.get("independent_ok") and gates.get("dispatch_bound") else "L2"
    if schema == SCHEMA_EVALUATION:
        # Synthetic/offline replay can never be L3, however clean the numbers look.
        gates = gates or {}
        if (verdict or {}).get("verdict") != "SUPPORTED":
            return "L1"
        adequate = (_safe_int(gates.get("assessable_dimensions")) >= 2
                    and _safe_int(gates.get("runs")) >= rules["min_runs"]
                    and _safe_int(gates.get("cases")) >= rules["min_cases"]
                    and bool(gates.get("runner")))
        return "L2" if adequate else "L1"
    if (verdict or {}).get("verdict") != "SUPPORTED":
        return "L1"
    return "L1"


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
    """Verify the credential a gated transition depends on, and its achieved level.

    Each target accepts exactly one credential class (`TARGET_ARTIFACT_SCHEMA`), and the
    conclusion stored in the credential is recomputed from the credential's own execution
    records rather than trusted as written.
    """
    policy_id = candidate.get("policy_id")
    path = f"policy[{policy_id}]"
    schema = TARGET_ARTIFACT_SCHEMA.get(target, SCHEMA_EVALUATION)
    using_trial = schema == SCHEMA_TRIAL
    ref_key = "trial_ref" if using_trial else "evaluation_ref"
    directory = trials_dir(state_path) if using_trial else evaluations_dir(state_path)
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
        diagnostics.append(_diag(
            "PE11", path,
            f"{target} 需要 {schema!r} 凭证，实际是 {payload.get('_schema')!r}："
            "合成回放凭证与真实科研验证凭证不可互换"))
        return diagnostics
    if payload.get("policy_id") != policy_id:
        diagnostics.append(_diag("PE11", path, "评价产物绑定到另一个策略"))
    if payload.get("policy_signature") != candidate.get("signature"):
        diagnostics.append(_diag("PE11", path, "评价产物绑定的策略版本与当前候选不一致"))

    diagnostics.extend(evaluation_rules_errors(state_path))
    current = evaluation_rules_digest(state_path)
    rules = frozen_rules(state_path) or DEFAULT_EVALUATION_RULES
    if current is not None:
        if payload.get("rules_digest") != current:
            diagnostics.append(_diag("PE12", path, "评价规则已改变：该产物的评价结果失效"))
        if candidate.get("evaluation_rules_digest") != current:
            diagnostics.append(_diag("PE12", path, "候选绑定的是另一版评价规则"))

    verdict = payload.get("verdict") if isinstance(payload.get("verdict"), dict) else {}
    gates = payload.get("gates") if isinstance(payload.get("gates"), dict) else {}
    if schema == SCHEMA_EVALUATION:
        audit = audit_report(payload.get("report") or {}, candidate=candidate, rules=rules,
                             current_rules_digest=current)
        for message in audit["errors"]:
            diagnostics.append(_diag("PE11", path, "评价产物内的报告无法重算：" + message))
        recomputed_verdict = (audit.get("verdict") or {}).get("verdict")
        if recomputed_verdict is not None and recomputed_verdict != verdict.get("verdict"):
            diagnostics.append(_diag(
                "PE11", path,
                f"产物记录的结论 {verdict.get('verdict')!r} 与根据其执行记录重算的"
                f" {recomputed_verdict!r} 不一致"))
        verdict = audit.get("verdict") or verdict
    elif schema == SCHEMA_RESEARCH_VALIDATION:
        # The credential the human approved is the single source of truth. The artifact's
        # derived fields must all be reproducible from it; otherwise an attacker can rewrite
        # the provenance the checks read while leaving the approved copy untouched.
        recorded = payload.get("credential") if isinstance(payload.get("credential"), dict) else None
        if recorded is None:
            diagnostics.append(_diag("PE15", path,
                                     "凭证产物没有保留被批准的凭证内容：无法复核批准绑定"))
        source = recorded if recorded is not None else payload
        check = _validation_errors(state_path, source, candidate=candidate, rules=rules,
                                   current_rules_digest=current,
                                   artifact_path=ref.get("path"))
        diagnostics.extend(check["errors"])
        verdict = check.get("verdict") or verdict
        if recorded is not None:
            if payload.get("report") != check.get("report"):
                diagnostics.append(_diag("PE15", path,
                                         "产物中的评价报告与其保留的凭证内容不一致：派生字段被改写"))
            # `report` is compared above and carries cases/runs/runner; these are the other
            # derived fields the checks read.
            for field in ("dispatch_ref", "task_provenance", "execution_evidence",
                          "equivalence", "candidate_arm", "control_arm"):
                if payload.get(field) != recorded.get(field):
                    diagnostics.append(_diag(
                        "PE15", path, f"产物字段 {field!r} 与其保留的凭证内容不一致：凭证被改写"))
        approval = payload.get("approval") if isinstance(payload.get("approval"), dict) else {}
        if recorded is not None and approval.get("credential_digest") != cg.digest_of(recorded):
            diagnostics.append(_diag(
                "PE15", path,
                "批准绑定的凭证内容摘要与该产物内的凭证不一致：批准的是另一份凭证"))
        diagnostics.extend(approval_errors(
            state_path, policy_id=policy_id, approval_digest=approval.get("digest"),
            credential_digest=approval.get("credential_digest"),
            signature=candidate.get("signature"), rules_digest=current))

    recomputed = _recomputed_level(gates, verdict, schema=payload.get("_schema"), rules=rules)
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


def approvals_dir(state_path: Path) -> Path:
    """The sealed human-approval ledger for this route (never written by an automated entry)."""
    return policy_dir(state_path) / APPROVALS_DIRNAME


def _approval_seal(key: bytes, event: Dict[str, Any]) -> str:
    import evidence_outcome as eo
    return hmac.new(key, eo.digest(event).encode("ascii"), hashlib.sha256).hexdigest()


def _approval_event_digest(event: Dict[str, Any]) -> str:
    import evidence_outcome as eo
    return eo.digest({key: value for key, value in event.items() if key != "seal"})


def _read_approvals(state_path: Path) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Verify the sealed approval chain without creating anything.

    Uses the existing `experiment_execute.Ledger` seal construction; a broken chain, a bad
    seal or a rewritten event is reported as tampering rather than as an empty ledger.
    """
    import evidence_outcome as eo
    directory = approvals_dir(state_path)
    key_path, events_path = directory / "key", directory / "events.jsonl"
    if not key_path.is_file() or not events_path.is_file():
        return [], None
    try:
        key = key_path.read_bytes()
        head_path = directory / "head"
        head_expected = head_path.read_text(encoding="ascii").strip() if head_path.is_file() else None
        events: List[Dict[str, Any]] = []
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            seal = event.pop("seal", "")
            expected = _approval_seal(key, event)
            previous = eo.digest(events[-1]) if events else None
            if not isinstance(seal, str) or not hmac.compare_digest(seal, expected) \
                    or event.get("previous") != previous:
                return [], "批准账本被篡改：拒绝沿用"
            event["seal"] = seal
            events.append(event)
        # Mirror `experiment_execute.Ledger`: the head must commit to the last event, so
        # deleting trailing events is reported as tampering instead of silently dropping them.
        if head_expected is not None:
            actual = eo.digest(events[-1]) if events else None
            if actual != head_expected:
                return [], "批准账本 head 与最后一条事件不一致：尾部事件被删除或改写，拒绝沿用"
    except (UnicodeDecodeError, OSError, json.JSONDecodeError, ValueError,
            TypeError, AttributeError, KeyError) as exc:
        # A line that is valid JSON but not an object (e.g. a list) raised AttributeError, and
        # `Ledger.locked()` raises TypeError for the same input: both must become a PE15
        # "ledger unusable" rather than a traceback.
        return [], f"批准账本不可读或结构非法（{type(exc).__name__}）：拒绝沿用"
    return events, None


def approval_events(state_path: Path) -> List[Dict[str, Any]]:
    """The verified approval events, or an empty list when there is no usable ledger."""
    events, problem = _read_approvals(state_path)
    return [] if problem else events


def approve_l3(state_path: Path, *, policy_id: str, credential: Dict[str, Any],
               approver: str, confirm_human: bool = False, scope_note: str = "",
               expires_in_seconds: int = 86400, now: Optional[float] = None) -> Dict[str, Any]:
    """Record a human authorisation for one exact L3 credential.

    This is the only way to produce the approval the VALIDATED/ACTIVE gates require. No
    automated entry calls it: the control plane cannot authorise itself. The approval binds
    the credential's content digest, the policy signature and the frozen rules digest, and it
    expires.
    """
    import experiment_execute as ex
    import time as _time
    diagnostics: List[cg.Diagnostic] = []
    path_label = f"policy[{policy_id}]"
    if confirm_human is not True:
        diagnostics.append(_diag("PE15", path_label,
                                 "人工批准必须由批准者显式确认（confirm_human）"))
    if not isinstance(approver, str) or not approver.strip():
        diagnostics.append(_diag("PE15", path_label, "必须记录批准者身份（approver）"))
    if not isinstance(credential, dict) or credential.get("policy_id") != policy_id:
        diagnostics.append(_diag("PE15", path_label, "批准对象必须是该策略的 L3 凭证"))
    problems = policy_id_errors(policy_id)
    diagnostics.extend(_diag("PE1", path_label, problem) for problem in problems)
    try:
        lifetime = float(expires_in_seconds)
    except (TypeError, ValueError, OverflowError):
        lifetime = -1.0
    if lifetime != lifetime or lifetime <= 0 or lifetime > 10 * 365 * 24 * 3600:
        diagnostics.append(_diag("PE15", path_label,
                                 f"批准有效期必须是 (0, 10 年] 内的有限秒数：{expires_in_seconds!r}"))
    if approvals_dir(state_path).is_symlink():
        diagnostics.append(_diag("PE15", path_label,
                                 "批准账本目录是符号链接：批准必须留在路由内，拒绝外移"))
    with policy_lock(state_path):
        existing = policy_record(load_records(state_path)[0], policy_id)
    if existing is None:
        diagnostics.append(_diag("PE1", path_label, "未知 policy_id：不能为一个不存在的策略记录批准"))
    if diagnostics:
        return {"status": "INVALID", "written": False,
                "diagnostics": [item.render() for item in diagnostics],
                "codes": sorted({item.rule for item in diagnostics})}
    now = _time.time() if now is None else now
    with policy_lock(state_path):
        records, _ = load_records(state_path)
        candidate = policy_record(records, policy_id) or {}
        event = {"_schema": SCHEMA_APPROVAL, "kind": "l3-approval", "policy_id": policy_id,
                 "policy_signature": candidate.get("signature"),
                 "rules_digest": evaluation_rules_digest(state_path),
                 "credential_digest": cg.digest_of(credential),
                 "approver": approver.strip(), "attested_by": "human", "confirm_human": True,
                 "scope_note": scope_note, "issued_at": now, "expires_at": now + lifetime,
                 "verification_limit": ("Skill 无法独立验证批准者身份；此记录是协议级人工门，"
                                        "不是密码学证明，也不是自动可信晋升")}
        try:
            with ex.Ledger(approvals_dir(state_path)).locked() as ledger:
                stored = ledger.append(event)
        except (ValueError, OSError, TypeError, AttributeError, KeyError) as exc:
            return {"status": "INVALID", "written": False,
                    "diagnostics": [f"批准账本不可用（{type(exc).__name__}）：拒绝沿用"],
                    "codes": ["PE15"]}
    return {"status": "APPROVED", "written": True, "policy_id": policy_id,
            "approval_digest": _approval_event_digest(stored), "approver": stored["approver"],
            "expires_at": stored["expires_at"],
            "note": "人工批准已记录；晋升时仍会重新校验该记录是否有效"}


def active_policy_standing(state_path: Path,
                           records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """What the ACTIVE policy actually recorded: its evidence level and approval status.

    Reporting a flat "L2" for every applied policy discarded the recorded level (an L3
    promotion) and hid whether a human approval backs it.
    """
    candidate = active_policy(records)
    if candidate is None:
        return {"level": None, "approved": None, "policy_id": None}
    policy_id = candidate.get("policy_id")
    level = None
    for record in records:
        if record.get("record") != "transition" or record.get("policy_id") != policy_id:
            continue
        recorded = record.get("level")
        if recorded in LEVEL_RANK and (level is None
                                       or LEVEL_RANK[recorded] > LEVEL_RANK[level]):
            level = recorded
    approval = latest_valid_approval(state_path, policy_id=str(policy_id),
                                     signature=candidate.get("signature"))
    return {"level": level, "approved": bool(approval), "policy_id": policy_id,
            "approver": (approval or {}).get("approver")}


def latest_valid_approval(state_path: Path, *, policy_id: str,
                          credential_digest: Optional[str] = None,
                          approval_digest: Optional[str] = None,
                          signature: Optional[str] = None,
                          rules_digest: Optional[str] = None,
                          now: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """The event `approval_errors` would accept (latest valid match), or None.

    Selecting "the last matching event" instead let an expired duplicate shadow the valid
    approval, so the artifact was written claiming an already-expired authorisation.
    """
    import time as _time
    now = _time.time() if now is None else now
    events, problem = _read_approvals(state_path)
    if problem:
        return None
    best: Optional[Dict[str, Any]] = None
    for event in events:
        if event.get("kind") != "l3-approval" or event.get("policy_id") != policy_id:
            continue
        if credential_digest is not None and event.get("credential_digest") != credential_digest:
            continue
        if approval_digest is not None and _approval_event_digest(event) != approval_digest:
            continue
        if event.get("attested_by") != "human" or event.get("confirm_human") is not True:
            continue
        if signature is not None and event.get("policy_signature") != signature:
            continue
        if rules_digest is not None and event.get("rules_digest") != rules_digest:
            continue
        if float(event.get("expires_at") or 0) <= now:
            continue
        best = event
    return best


def approval_errors(state_path: Path, *, policy_id: str,
                    credential_digest: Optional[str] = None,
                    approval_digest: Optional[str] = None,
                    signature: Optional[str] = None,
                    rules_digest: Optional[str] = None,
                    now: Optional[float] = None) -> List[cg.Diagnostic]:
    """PE15 diagnostics for the human approval a VALIDATED/ACTIVE transition requires."""
    import time as _time
    path_label = f"policy[{policy_id}]"
    now = _time.time() if now is None else now
    if credential_digest is None and approval_digest is None:
        # Treating a missing binding as "match anything" let an artifact with an empty
        # approval block promote on the strength of any approval for the policy.
        return [_diag("PE15", path_label,
                      "没有可核验的凭证摘要或批准摘要：批准绑定不可为空，拒绝沿用")]
    events, problem = _read_approvals(state_path)
    if problem:
        return [_diag("PE15", path_label, problem)]
    if not events:
        return [_diag("PE15", path_label,
                      "没有人工批准记录：L3 晋升必须先由人类批准者批准该凭证"
                      "（approve-l3）。Skill 无法独立区分验证者，因此不提供自动可信晋升")]
    matches = [event for event in events
               if event.get("kind") == "l3-approval"
               and event.get("policy_id") == policy_id
               and (credential_digest is None
                    or event.get("credential_digest") == credential_digest)
               and (approval_digest is None
                    or _approval_event_digest(event) == approval_digest)]
    if not matches:
        return [_diag("PE15", path_label,
                      "没有匹配该凭证的人工批准记录（批准绑定的是凭证内容摘要）")]
    reasons: List[str] = []
    for event in matches:
        problems: List[str] = []
        if event.get("attested_by") != "human" or event.get("confirm_human") is not True:
            problems.append("批准记录没有人类确认")
        if signature is not None and event.get("policy_signature") != signature:
            problems.append("批准针对另一个策略版本")
        if rules_digest is not None and event.get("rules_digest") != rules_digest:
            problems.append("批准针对另一版评价规则")
        if float(event.get("expires_at") or 0) <= now:
            problems.append("人工批准已过期")
        if not problems:
            return []
        # The reasons used to be recorded and then discarded by an unconditional `return []`,
        # so a signature or rule binding mismatch was silently accepted.
        reasons.extend(problems)
    return [_diag("PE15", path_label, "；".join(sorted(set(reasons))))]


def _equivalence_errors(record: Any, arm_names: Sequence[str],
                        case_sets: Dict[str, set], *,
                        candidate_arm: Optional[str] = None,
                        control_arm: Optional[str] = None) -> List[str]:
    """The A/B fairness check: equal controlled axes, a real contrast, distinct instances.

    Mirrors the existing `execution_gate` comparison semantics: a controlled variable that
    differs, a contrast that does not differ, or an undeclared changed variable is a defect.
    """
    if not isinstance(record, dict):
        return ["缺少 equivalence 记录：无法证明两臂在模型/Harness/工具/任务/可见数据/预算上等价"]
    arms = record.get("arms")
    if not isinstance(arms, dict):
        return ["equivalence.arms 缺失"]
    problems: List[str] = []
    for arm in arm_names:
        if arm not in arms:
            problems.append(f"equivalence 缺少臂 {arm!r}")
    if problems:
        return problems
    # Compare the arms the verdict actually compares. Using the first two keys of the mapping
    # let a decoy pair (sorted first) satisfy the fairness check while the real comparison was
    # unfair; artifacts are stored with sort_keys=True, so the order was attacker-chosen.
    compared = [arm for arm in (candidate_arm, control_arm) if isinstance(arm, str)]
    if len(compared) == 2 and compared[0] != compared[1]:
        missing = [arm for arm in compared if arm not in arms]
        if missing:
            problems.append(f"equivalence 缺少被比较的臂 {missing}")
            return problems
        if set(arms) != set(compared):
            problems.append(f"equivalence.arms 与声明的候选/对照臂不一致："
                            f"{sorted(arms)} vs {sorted(compared)}")
            return problems
        arm_names = compared
    instances = {}
    for arm in arm_names:
        block = arms.get(arm)
        if not isinstance(block, dict):
            problems.append(f"equivalence.arms[{arm}] 不是对象")
            continue
        instance = block.get("instance")
        if not isinstance(instance, str) or not instance.strip():
            problems.append(f"equivalence.arms[{arm}] 缺少执行实例 identity（instance）")
        else:
            instances[arm] = instance.strip()
        if not isinstance(block.get("environment"), dict):
            problems.append(f"equivalence.arms[{arm}] 缺少执行环境（environment）")
    if len(set(instances.values())) != len(instances):
        problems.append("两臂的执行实例 identity 相同：无法区分是两次独立执行")
    contrast = record.get("contrast_axes")
    if not isinstance(contrast, list) or not contrast:
        problems.append("equivalence.contrast_axes 必须显式声明干预轴")
        contrast = []
    envs = {arm: (arms.get(arm) or {}).get("environment") or {} for arm in arm_names}
    left, right = envs[arm_names[0]], envs[arm_names[1]]
    for axis in _REQUIRED_EQUIVALENCE_AXES:
        missing = [arm for arm in arm_names if axis not in envs[arm]]
        if missing:
            problems.append(f"equivalence 缺少受控轴 {axis!r}（臂 {missing}）")
            continue
        # Presence is not equality: a null/empty value on both sides used to pass.
        empty = [arm for arm in arm_names if envs[arm][axis] in (None, "", [], {})]
        if empty:
            problems.append(f"equivalence 的受控轴 {axis!r} 在臂 {empty} 中为空")
    for axis in contrast:
        if axis not in left or axis not in right:
            problems.append(f"对照轴 {axis!r} 未在两个臂中声明")
        elif left[axis] == right[axis]:
            problems.append(f"对照轴 {axis!r} 在两臂间没有差异：不构成对照")
    # Mirror the existing execution_gate rule: every changed variable must be declared as a
    # contrast. Comparing only the required axes left an undeclared extra difference (a
    # different model under a made-up key) undetected.
    for axis in sorted(set(left) | set(right)):
        if axis in contrast:
            continue
        if left.get(axis) != right.get(axis):
            problems.append(f"环境轴 {axis!r} 在两臂间不一致（未声明为对照轴）")
    paired = record.get("paired_task_ids")
    if not isinstance(paired, list) or not paired:
        problems.append("equivalence.paired_task_ids 缺失：无法复核配对任务")
    elif len(case_sets) > 1:
        executed = sorted(set().union(*case_sets.values()))
        if sorted({str(item) for item in paired}) != executed:
            problems.append(f"配对任务与执行记录不一致（声明 {sorted(map(str, paired))[:4]}，"
                            f"执行 {executed[:4]}）")
    return problems


def _dispatch_reuse_errors(state_path: Path, dispatch_ref: Any, policy_id: str,
                           *, exclude_path: Optional[str] = None) -> List[cg.Diagnostic]:
    """A bounded-trial dispatch record is single-use and must be the latest one."""
    path_label = f"policy[{policy_id}]"
    diagnostics: List[cg.Diagnostic] = []
    digest = (dispatch_ref or {}).get("digest") if isinstance(dispatch_ref, dict) else None
    records, _ = load_records(state_path)
    latest = None
    for record in records:
        if record.get("record") != "transition" or record.get("policy_id") != policy_id:
            continue
        ref = (record.get("evidence") or {}).get("trial_ref")
        if isinstance(ref, dict):
            latest = ref
    if latest is not None and latest.get("digest") != digest:
        diagnostics.append(_diag("PE11", path_label,
                                 "派遣记录不是该策略最近一次有限试运行：不得用旧派遣记录充当"
                                 "本次 L3 的绑定"))
    directory = evaluations_dir(state_path)
    excluded = None
    if exclude_path:
        try:
            excluded = Path(exclude_path).resolve()
        except OSError:
            excluded = None
    for candidate_path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        if excluded is not None and candidate_path.resolve() == excluded:
            continue          # the artifact under verification is not "another credential"
        try:
            payload = json.loads(candidate_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError, json.JSONDecodeError):
            continue
        if payload.get("_schema") != SCHEMA_RESEARCH_VALIDATION:
            continue
        if (payload.get("dispatch_ref") or {}).get("digest") == digest:
            diagnostics.append(_diag("PE11", path_label,
                                     "该派遣记录已被另一份 L3 凭证使用：派遣记录不可重复使用"))
            break
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
    # A rollback restore may reuse the policy's existing credential, but it still has to
    # present one. Skipping the gate let a restore put a policy back into ACTIVE with no
    # human action at all, bypassing the approval's expiry.

    if target in ("SHADOW", "REPLAY_EVALUATED", "BOUNDED_TRIAL", "VALIDATED", "ACTIVE"):
        overfit = overfit_flags(candidate)
        if overfit and target != "SHADOW":
            diagnostics.append(_diag("PE5", path,
                                     "针对固定 fixture 的策略不得越过 SHADOW：" + "；".join(overfit)))
    if target in GATED_TARGETS:
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
        named = {str(item.get("project")) for item in refs
                 if isinstance(item, dict) and item.get("project")}
        attested = _attested_projects(state_path)
        if len(attested) < 2:
            diagnostics.append(_diag(
                "PE14", path,
                "global 作用域需要 ≥2 个有「决策 + 合格 outcome」轨迹的背书项目；"
                f"当前背书项目 {sorted(attested)}：项目名不能替代独立来源"))
        else:
            unbacked = sorted(named - attested)
            if unbacked:
                diagnostics.append(_diag(
                    "PE14", path, f"以下项目没有合格轨迹证据支持：{unbacked}"))
    if target in ("REJECTED", "ROLLED_BACK", "HOLD") and not evidence.get("reason"):
        diagnostics.append(_diag("PE10", path, f"{target} 必须写明 reason"))
    return cg._dedupe(diagnostics)


def _achieved_level(state_path: Path, records: Sequence[Dict[str, Any]],
                    candidate: Dict[str, Any], target: str,
                    evidence: Dict[str, Any]) -> str:
    """The level actually achieved, derived from the verified artifact.

    When there is no new artifact (the rollback restore of an already-promoted policy), the
    highest level that policy previously recorded is kept. Defaulting to L1 misreported an
    L3-backed policy as L1 the moment it was superseded and restored.
    """
    if target == "SHADOW":
        return "L1"
    using_trial = target == "BOUNDED_TRIAL"
    ref = evidence.get("trial_ref" if using_trial else "evaluation_ref")
    directory = trials_dir(state_path) if using_trial else evaluations_dir(state_path)
    payload, errors = _read_artifact(directory, ref)
    if payload is not None and not errors:
        return _recomputed_level(payload.get("gates") or {}, payload.get("verdict") or {},
                                 schema=payload.get("_schema"))
    prior = [record.get("level") for record in records
             if record.get("record") == "transition"
             and record.get("policy_id") == candidate.get("policy_id")
             and record.get("level") in LEVEL_RANK]
    return max(prior, key=lambda item: LEVEL_RANK[item]) if prior else "L1"


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
        # Validate the restore BEFORE writing anything. Writing first left a failed restore as
        # a half-state (the old policy rolled back, the target still superseded, no ACTIVE
        # policy and no way to retry, since ROLLED_BACK is terminal).
        restore_evidence: Optional[Dict[str, Any]] = None
        if not diagnostics and target_status == "SUPERSEDED":
            artifact = latest_evaluation_artifact(state_path, to_policy_id, records)
            restore_evidence = {"reason": f"restored by rollback from {policy_id}",
                                "restored": True}
            if artifact is not None:
                restore_evidence["evaluation_ref"] = artifact["ref"]
            diagnostics.extend(transition_errors(state_path, records, to_policy_id, "ACTIVE",
                                                 restore_evidence, authority_ok=True))
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
                state_path, after, to_policy_id, "ACTIVE", evidence=restore_evidence,
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
                    dimension: Optional[str] = None, *,
                    rules: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Whether two arms differ beyond the frozen tolerance, and in which direction."""
    tolerance = float((rules or DEFAULT_EVALUATION_RULES)["delta_tolerance"])
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
        # Overlapping ranges mean the sample cannot support a confident direction. The caveat
        # used to be recorded while the dimension was still counted as a promotion benefit.
        confident = different and not overlapping
        block = {"delta": delta, "overlapping": overlapping,
                 "direction": "BETTER" if better else ("WORSE" if worse else "NONE"),
                 "better": better, "worse": worse, "confident": confident,
                 "status": "DISTINGUISHABLE" if different else "UNDIFFERENTIATED"}
        if different and overlapping:
            block["caveat"] = ("均值差异超过容差，但两臂区间重叠：样本量偏小，"
                               "按不可区分处理为证据不足")
        result[name] = block
    return {"distinguishable": any_different, "dimensions": result,
            "reason": ("至少一个维度差异超过容差" if any_different
                       else "各维度差异在容差内：报告不可区分，不选胜者")}


def ablation_verdict(report: Dict[str, Any], *, candidate_arm: str = "rsi_full",
                     control_arm: str = "full_cie",
                     rules: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Turn a replay ablation report into promotion evidence. Never a composite score.

    `rules` must be the frozen rule set the candidate is bound to; the default is only a
    fallback for direct calls.
    """
    rules = rules or DEFAULT_EVALUATION_RULES
    empty: Dict[str, Any] = {"verdict": "INVALID", "reasons": [], "comparison": {},
                             "benefit_dimensions": [], "uncertain_benefit": [],
                             "reliability_degraded": [],
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
    comparison = distinguishable(report, candidate_arm, control_arm, rules=rules)
    if not comparison.get("dimensions"):
        empty["reasons"] = ["报告没有可比对的评价维度"]
        return empty

    reasons: List[str] = []
    dimensions = comparison["dimensions"]
    benefit_better = sorted(name for name, block in dimensions.items()
                            if block.get("direction") == "BETTER"
                            and block.get("confident") and name in BENEFIT_DIMENSIONS)
    uncertain_benefit = sorted(name for name, block in dimensions.items()
                               if block.get("direction") == "BETTER"
                               and not block.get("confident")
                               and name in BENEFIT_DIMENSIONS)
    reliability_worse = sorted(name for name, block in dimensions.items()
                               if block.get("direction") == "WORSE"
                               and name in RELIABILITY_DIMENSIONS)
    other_worse = sorted(name for name, block in dimensions.items()
                         if block.get("direction") == "WORSE"
                         and name not in RELIABILITY_DIMENSIONS and name not in BENEFIT_DIMENSIONS)
    assessable = sorted(name for name, block in dimensions.items()
                        if block.get("status") not in (None, "UNASSESSABLE"))
    benefit_assessable = [name for name in BENEFIT_DIMENSIONS if name in assessable]

    cases = _safe_int(report.get("cases"))
    runs = _safe_int(report.get("runs_per_case"))
    sample_adequate = (cases >= rules["min_cases"] and runs >= rules["min_runs"]
                       and bool(assessable) and bool(benefit_assessable))
    execution_record = any(block.get("results") for block in report["per_arm"].values())
    isolation_ok = bool(execution_record) and all(
        result.get("leak_checked") and result.get("isolation_verified", True)
        for block in report["per_arm"].values() for result in block.get("results") or [])
    unobservable = _safe_int(report.get("unobservable_decisions"))

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
    if uncertain_benefit:
        reasons.append("收益方向区间重叠、证据不足（不计入晋升）：" + ", ".join(uncertain_benefit))
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
            "uncertain_benefit": uncertain_benefit,
            "isolation_ok": isolation_ok, "execution_record": execution_record,
            "note": "discovery replay 的维度各自独立，没有加权总分"}


def evaluate_candidate(state_path: Path, policy_id: str, report: Dict[str, Any], *,
                       report_source: Optional[str] = None, reason: str = "",
                       independent: Any = None, leakage_checked: Any = None,
                       reproducible: Any = None) -> Dict[str, Any]:
    """Audit a replay report, store an L2 credential, then advance.

    The report is recomputed from its own per-case execution records and the conclusion is
    derived with the candidate's frozen rules. The resulting credential is capped at L2: it is
    synthetic/offline evidence, so it can never stand in for an L3 research validation.
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
        rules_errors = evaluation_rules_errors(state_path)
        if rules_errors:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": [item.render() for item in rules_errors],
                    "codes": sorted({item.rule for item in rules_errors})}
        current_rules = evaluation_rules_digest(state_path)
        rules = frozen_rules(state_path)
        if rules is None:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": ["冻结评价规则缺失或内容与 digest 不一致"],
                    "codes": ["PE12"]}
        if candidate.get("evaluation_rules_digest") != current_rules:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": ["候选绑定的是另一版评价规则：评价结果不可信"],
                    "codes": ["PE12"]}

        audit = audit_report(report, candidate=candidate, rules=rules,
                             current_rules_digest=current_rules)
        if audit["errors"]:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": audit["errors"], "codes": ["PE11"]}
        normalized = audit["report"]
        verdict = audit["verdict"]
        gates = {
            "independent": bool(verdict.get("execution_record") and verdict.get("isolation_ok")),
            "leakage_checked": bool(verdict.get("isolation_ok")),
            "reproducible": int(normalized.get("runs_per_case") or 0) >= rules["min_runs"],
            "sample_adequate": bool(verdict.get("sample_adequate")),
            "distinguishable": bool(verdict.get("benefit_dimensions")),
            "degraded_dimensions": list(verdict.get("reliability_degraded") or []),
            "unobservable_decisions": int(verdict.get("unobservable_decisions") or 0),
            "assessable_dimensions": len(verdict.get("coverage", {}).get("assessable") or []),
            "cases": int(normalized.get("cases") or 0),
            "runs": int(normalized.get("runs_per_case") or 0),
            "runner": normalized.get("runner"),
        }
        payload = {
            "_schema": SCHEMA_EVALUATION,
            "policy_id": policy_id,
            "policy_signature": candidate.get("signature"),
            "policy_schema_version": candidate.get("policy_schema_version"),
            "rules_digest": current_rules,
            "report": normalized,
            "report_digest": cg.digest_of(normalized),
            "report_source": report_source or "inline",
            "binding_source": ("report" if normalized.get("policy_signature") else "entry"),
            "runner": normalized.get("runner"),
            "credential_class": "replay",
            "produced_by": "policy_evolution.evaluate_candidate",
            "evaluated_at": _now(),
            "verdict": verdict,
            "gates": gates,
            "level": _recomputed_level(gates, verdict, schema=SCHEMA_EVALUATION, rules=rules),
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
        # A trial attempt identity keeps two attempts distinct. Content addressing alone
        # collapsed same-second retries into one artifact, so an old dispatch record could
        # silently count as the newest one.
        attempt = 1 + sum(1 for record in records
                          if record.get("record") == "transition"
                          and record.get("policy_id") == policy_id
                          and record.get("to") == "BOUNDED_TRIAL")
        payload = {
            "_schema": SCHEMA_TRIAL,
            "policy_id": policy_id,
            "attempt": attempt,
            "policy_signature": candidate.get("signature"),
            "rules_digest": current_rules,
            "dispatch_evidence": copy.deepcopy(dispatch_evidence),
            "budget_expanded": bool(budget_expanded),
            "hard_gates_unchanged": bool(hard_gates_unchanged),
            "produced_by": "policy_evolution.begin_bounded_trial",
            "recorded_at": _now(),
            "verdict": {"verdict": "DISPATCHED",
                        "note": "试运行派遣记录，不是评价结论"},
            "gates": {"dispatch_record": True,
                      "budget_expanded": bool(budget_expanded),
                      "hard_gates_unchanged": bool(hard_gates_unchanged),
                      "runner": "bounded-trial"},
        }
        payload["level"] = _recomputed_level(payload["gates"], payload["verdict"],
                                             schema=SCHEMA_TRIAL)
        ref = _store_artifact(state_path, trials_dir(state_path), payload)
        result = _transition_locked(state_path, records, policy_id, "BOUNDED_TRIAL",
                                    evidence={"trial_ref": ref, "reason": "bounded trial"},
                                    reason="bounded trial", authority=_AUTHORITY)
        if not result.get("written"):
            _discard_artifact(ref.get("path"))
        return result


def record_research_validation(state_path: Path, policy_id: str,
                               validation: Dict[str, Any]) -> Dict[str, Any]:
    """Store an L3 research-validation credential and advance to VALIDATED.

    This is the only way to reach L3. The credential must name a real (non-synthetic) task
    source, a reviewable execution log, independently executed arms, explicit isolation
    proofs, and the actual dispatch record it validates; its benefit conclusion is recomputed
    with the candidate's frozen rules.
    """
    with policy_lock(state_path):
        records, _ = load_records(state_path)
        candidate = policy_record(records, policy_id)
        if candidate is None:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": ["未知 policy_id"], "codes": ["PE1"]}
        current_status = latest_status(records).get(policy_id)
        if current_status not in ("REPLAY_EVALUATED", "BOUNDED_TRIAL"):
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": [f"只有 REPLAY_EVALUATED/BOUNDED_TRIAL 可以记录科研验证，"
                                    f"当前是 {current_status}"],
                    "codes": ["PE10"]}
        rules_errors = evaluation_rules_errors(state_path)
        if rules_errors:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": [item.render() for item in rules_errors],
                    "codes": sorted({item.rule for item in rules_errors})}
        current_rules = evaluation_rules_digest(state_path)
        rules = frozen_rules(state_path) or DEFAULT_EVALUATION_RULES
        check = _validation_errors(state_path, validation, candidate=candidate, rules=rules,
                                   current_rules_digest=current_rules)
        if check["errors"]:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": [item.render() for item in check["errors"]],
                    "codes": sorted({item.rule for item in check["errors"]})}
        # The human gate: the Skill cannot distinguish an independent verifier, so the
        # production path requires an approval bound to this exact credential.
        approval_diagnostics = approval_errors(
            state_path, policy_id=policy_id, credential_digest=cg.digest_of(validation),
            signature=candidate.get("signature"), rules_digest=current_rules)
        if approval_diagnostics:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": [item.render() for item in approval_diagnostics],
                    "codes": sorted({item.rule for item in approval_diagnostics})}
        approval = latest_valid_approval(
            state_path, policy_id=policy_id, credential_digest=cg.digest_of(validation),
            signature=candidate.get("signature"), rules_digest=current_rules)
        if approval is None:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": ["没有仍然有效的人工批准记录（可能已过期或被后续记录遮蔽）"],
                    "codes": ["PE15"]}
        verdict = check["verdict"]
        gates = {"provenance_ok": True,
                 "independent_ok": True,
                 "dispatch_bound": True,
                 "isolation_ok": bool(verdict.get("isolation_ok")),
                 "sample_adequate": bool(verdict.get("sample_adequate")),
                 "cases": int(check["report"].get("cases") or 0),
                 "runs": int(check["report"].get("runs_per_case") or 0),
                 "runner": check["report"].get("runner")}
        payload = {
            "_schema": SCHEMA_RESEARCH_VALIDATION,
            "policy_id": policy_id,
            "policy_signature": candidate.get("signature"),
            "rules_digest": current_rules,
            "report": check["report"],
            "report_digest": cg.digest_of(check["report"]),
            "task_provenance": validation.get("task_provenance"),
            "execution_evidence": validation.get("execution_evidence"),
            "dispatch_ref": validation.get("dispatch_ref"),
            "equivalence": validation.get("equivalence"),
            # The submitted credential is kept verbatim so the binding can be recomputed from
            # its content at promotion time instead of being read from this artifact's own field.
            "credential": copy.deepcopy(validation),
            "approval": {"digest": _approval_event_digest(approval),
                         "credential_digest": cg.digest_of(validation),
                         "approver": approval.get("approver"),
                         "issued_at": approval.get("issued_at"),
                         "expires_at": approval.get("expires_at"),
                         "attested_by": approval.get("attested_by")},
            "runner": check["report"].get("runner"),
            "credential_class": "research_validation",
            "produced_by": "policy_evolution.record_research_validation",
            "evaluated_at": _now(),
            "candidate_arm": validation.get("candidate_arm"),
            "control_arm": validation.get("control_arm"),
            "verdict": verdict,
            "gates": gates,
            "level": _recomputed_level(gates, verdict,
                                       schema=SCHEMA_RESEARCH_VALIDATION, rules=rules),
        }
        ref = _store_artifact(state_path, evaluations_dir(state_path), payload)
        evidence = {"evaluation_ref": ref,
                    "reason": "L3 科研验证：" + "; ".join(verdict.get("reasons") or [])}
        result = _transition_locked(state_path, records, policy_id, "VALIDATED",
                                    evidence=evidence, reason=evidence["reason"],
                                    authority=_AUTHORITY)
        if not result.get("written"):
            # A refused credential must not persist: an orphan artifact would also claim the
            # single-use dispatch record and brick every retry.
            _discard_artifact(ref.get("path"))
        return result


def validate_candidate(state_path: Path, policy_id: str, *,
                       evaluation_ref: Optional[Dict[str, Any]] = None,
                       validation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """VALIDATED requires an L3 research-validation credential.

    A replay credential is not accepted here: synthetic/offline evidence and real-research
    evidence are different credential classes.
    """
    if isinstance(validation, dict):
        return record_research_validation(state_path, policy_id, validation)
    with policy_lock(state_path):
        records, _ = load_records(state_path)
        if policy_record(records, policy_id) is None:
            return {"status": "INVALID", "written": False, "policy_id": policy_id,
                    "diagnostics": ["未知 policy_id"], "codes": ["PE1"]}
        ref = evaluation_ref
        if isinstance(ref, dict):
            payload, errors = _read_artifact(evaluations_dir(state_path), ref)
            if payload is None:
                return {"status": "INVALID", "written": False, "policy_id": policy_id,
                        "diagnostics": errors, "codes": ["PE11"]}
            if payload.get("_schema") != SCHEMA_RESEARCH_VALIDATION:
                return {"status": "INVALID", "written": False, "policy_id": policy_id,
                        "diagnostics": [f"VALIDATED 需要 L3 真实科研验证凭证"
                                        f"（{SCHEMA_RESEARCH_VALIDATION}），"
                                        f"实际是 {payload.get('_schema')!r}："
                                        "合成回放评价不能当作 L3"],
                        "codes": ["PE11"]}
        else:
            artifact = latest_evaluation_artifact(state_path, policy_id, records)
            if artifact is None or artifact.get("_schema") != SCHEMA_RESEARCH_VALIDATION:
                return {"status": "INVALID", "written": False, "policy_id": policy_id,
                        "diagnostics": ["没有 L3 真实科研验证凭证：合成回放评价不得升级为 "
                                        "L3。请用 record_research_validation 提交真实任务来源、"
                                        "独立执行结果与派遣记录"],
                        "codes": ["PE11"]}
            ref = artifact["ref"]
        return _transition_locked(state_path, records, policy_id, "VALIDATED",
                                  evidence={"evaluation_ref": ref,
                                            "reason": "L3 research validation"},
                                  reason="L3 research validation", authority=_AUTHORITY)


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
        "validate", "validate-research", "approve-l3", "promote", "rollback", "state",
        "advice"))
    parser.add_argument("--state", help="path to research-state.json")
    parser.add_argument("--policy", help="path to a candidate JSON file (or - for stdin)")
    parser.add_argument("--policy-id")
    parser.add_argument("--to")
    parser.add_argument("--to-policy-id")
    parser.add_argument("--reason", default="")
    parser.add_argument("--level", default="L1")
    parser.add_argument("--report", help="path to a replay ablation report JSON")
    parser.add_argument("--dispatch", help="trial: dispatch evidence as JSON")
    parser.add_argument("--validation", help="validate-research: L3 validation credential JSON")
    parser.add_argument("--approver", help="approve-l3: the approving human's identity")
    parser.add_argument("--scope-note", default="", help="approve-l3: what is being approved")
    parser.add_argument("--confirm-human", action="store_true",
                        help="approve-l3: confirm that a human is authorising this")
    parser.add_argument("--expires-in", type=float, default=86400,
                        help="approve-l3: approval lifetime in seconds")
    parser.add_argument("--trajectory", help="path to decision-trajectory.jsonl")
    parser.add_argument("--selftest", action="store_true")
    return parser


def _read_json_input(path: str, label: str) -> Tuple[Any, Optional[str]]:
    """Read a JSON input file, turning any failure into a diagnosable message."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"{label} 文件不存在：{path}"
    except (UnicodeDecodeError, OSError) as exc:
        return None, f"{label} 文件不可读（{type(exc).__name__}）：{path}"
    except json.JSONDecodeError as exc:
        return None, f"{label} 不是合法 JSON：{exc}"


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
    if args.command == "approve-l3":
        if not args.policy_id or not args.validation or not args.approver:
            return _emit({"status": "INVALID",
                          "errors": ["需要 --policy-id --validation <file> --approver <name>"]},
                         EXIT_ERROR)
        credential, failure = _read_json_input(args.validation, "validation")
        if failure:
            return _emit({"status": "INVALID", "policy_id": args.policy_id,
                          "diagnostics": [failure], "codes": ["PE15"]}, EXIT_HARD)
        result = approve_l3(state_path, policy_id=args.policy_id, credential=credential,
                            approver=args.approver, confirm_human=args.confirm_human,
                            scope_note=args.scope_note,
                            expires_in_seconds=args.expires_in)
        return _emit(result, EXIT_OK if result.get("written") else EXIT_HARD)
    if args.command == "validate-research":
        if not args.policy_id or not args.validation:
            return _emit({"status": "INVALID",
                          "errors": ["需要 --policy-id 与 --validation <file>"]}, EXIT_ERROR)
        credential, failure = _read_json_input(args.validation, "validation")
        if failure:
            return _emit({"status": "INVALID", "policy_id": args.policy_id,
                          "diagnostics": [failure], "codes": ["PE11"]}, EXIT_HARD)
        result = record_research_validation(state_path, args.policy_id, credential)
        return _emit(result, EXIT_OK if result.get("written") else EXIT_HARD)
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
        report, failure = _read_json_input(args.report, "report")
        if failure:
            return _emit({"status": "INVALID", "policy_id": args.policy_id,
                          "diagnostics": [failure], "codes": ["PE11"]}, EXIT_HARD)
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


_SELFTEST_DIMS = ("mechanistic_understanding", "prediction_quality", "intervention_quality",
                  "scientific_novelty", "search_efficiency", "stagnation_recovery",
                  "memory_accumulation")


def _arm_block(values):
    """An arm whose declared summary is derived from its own per-case execution record."""
    series = {name: [round(values[name] - 0.02 + 0.04 * index / 4, 4) for index in range(5)]
              for name in _SELFTEST_DIMS}
    results = []
    for _run in range(2):
        for index in range(5):
            results.append({"case_id": f"C{index}", "leak_checked": True,
                            "isolation_verified": True,
                            "evaluation": {"metrics": {name: {"value": series[name][index]}
                                                       for name in _SELFTEST_DIMS},
                                           "evidence_support": {"class": "OBSERVED"}}})
    dimensions = {name: {"mean": round(sum(series[name]) / len(series[name]), 4),
                         "min": min(series[name]), "max": max(series[name])}
                  for name in _SELFTEST_DIMS}
    return {"dimensions": dimensions, "results": results,
            "evidence_support": {"OBSERVED": len(results)}}


def _selftest_arm(*, science=0.5, intervention=0.5, benefit=0.5):
    return _arm_block({"mechanistic_understanding": science, "prediction_quality": science,
                       "intervention_quality": intervention, "scientific_novelty": 0.5,
                       "search_efficiency": benefit, "stagnation_recovery": benefit,
                       "memory_accumulation": benefit})


def _report(sufficient=True, unobservable=0, flat=False):
    """A supported report: a real benefit gain, reliability intact, an execution record."""
    gain = 0.5 if flat else 0.9
    low = 0.5 if flat else 0.3
    return {"schema": "research-idea-pipeline/replay-ablation@1",
            "sufficient_sample": sufficient, "unobservable_decisions": unobservable,
            "delta_vs_baseline": {},
            "per_arm": {"rsi_full": _selftest_arm(science=0.5, intervention=0.5, benefit=gain),
                        "full_cie": _selftest_arm(science=0.5, intervention=0.5, benefit=low)},
            "runner": "offline CIE runner (no model calls)",
            "cases": 5, "runs_per_case": 2}


def _selftest_validation(state_path: Path, policy_id: str, workdir: Path,
                         *, science=(0.5, 0.5), benefit=(0.9, 0.3)) -> Dict[str, Any]:
    """A minimal valid L3 research-validation credential for the selftest."""
    workdir.mkdir(parents=True, exist_ok=True)
    task = workdir / "task.json"
    task.write_text(json.dumps({"task_id": "T1", "synthetic": False}), encoding="utf-8")
    log = workdir / "run.log"
    log.write_text("external harness executed\n", encoding="utf-8")
    trial = None
    for path in trials_dir(state_path).glob(f"{policy_id}.*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("policy_id") == policy_id:
            trial = {"path": str(path), "digest": payload["digest"]}
    def rows(executor, sci, ben):
        return [{"case_id": f"T{index}", "isolation_verified": True, "leak_checked": True,
                 "executor": executor,
                 "evaluation": {"metrics": {"mechanistic_understanding": {"value": sci},
                                            "search_efficiency": {"value": ben}}}}
                for _ in range(2) for index in range(3)]
    def env(instance, strategy):
        return {"instance": instance, "environment": {
            "model": "selftest-model", "harness": "selftest-harness",
            "tools": ["runner"], "visible_data": "sha256:selftest",
            "budget": {"hours": 1}, "task_ids": ["T0", "T1", "T2"],
            "strategy": strategy}}
    return {"_schema": SCHEMA_RESEARCH_VALIDATION, "policy_id": policy_id,
            "policy_signature": (policy_record(load_records(state_path)[0], policy_id)
                                 or {}).get("signature"),
            "equivalence": {"controlled_axes": list(_REQUIRED_EQUIVALENCE_AXES),
                            "contrast_axes": ["strategy"],
                            "paired_task_ids": ["T0", "T1", "T2"],
                            "arms": {"policy": env("selftest-policy-run", "policy"),
                                     "control": env("selftest-control-run", "control")}},
            "rules_digest": evaluation_rules_digest(state_path),
            "candidate_arm": "policy", "control_arm": "control",
            "task_provenance": {"task_id": "T1", "source": str(task),
                                "source_digest": _file_digest(task), "synthetic": False},
            "execution_evidence": {"path": str(log), "digest": _file_digest(log)},
            "dispatch_ref": trial,
            "cases": 3, "runs_per_case": 2,
            "runner": "external research validation harness",
            "per_arm": {"policy": {"executor": "external-1",
                                   "results": rows("external-1", science[0], benefit[0])},
                        "control": {"executor": "external-2",
                                    "results": rows("external-2", science[1], benefit[1])}}}


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
        replay = validate_candidate(state_path, "P-1")
        check("a replay credential cannot be L3 validation",
              replay["status"] == "INVALID" and "PE11" in replay["codes"])

        pending = _selftest_validation(state_path, "P-1", Path(temp) / "l3")
        unapproved = record_research_validation(state_path, "P-1", pending)
        check("L3 without human approval is refused",
              unapproved["status"] == "INVALID" and "PE15" in unapproved["codes"])
        approved = approve_l3(state_path, policy_id="P-1", credential=pending,
                              approver="selftest-human", confirm_human=True,
                              scope_note="selftest")
        check("human approval records", approved["status"] == "APPROVED")
        validated = record_research_validation(state_path, "P-1", pending)
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
        pending_2 = _selftest_validation(state_path, "P-2", Path(temp) / "l3b")
        approve_l3(state_path, policy_id="P-2", credential=pending_2,
                   approver="selftest-human", confirm_human=True, scope_note="selftest")
        record_research_validation(state_path, "P-2", pending_2)
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
