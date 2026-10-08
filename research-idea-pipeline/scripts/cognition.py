#!/usr/bin/env python3
"""cognition.py — Cognitive Insight Engine: persistent scientific cognitive memory.

What this module is
-------------------
A **read-only cognitive projection** over the canonical Research State plus an
append-only revision log. It never writes `research-state.json`, never changes
`claims[].status`, never touches `contract`, and never creates a second
authoritative state.

Three layers, one direction of authority:

    Canonical    .research-idea-pipeline/routes/<R>/research-state.json
                 + frozen preregistration + raw evidence            ← sole authority
    Event        .research-idea-pipeline/routes/<R>/cognition/model-revisions.jsonl
                 structural assertions + canonical pointers        ← append-only, no epistemics
    Derived      .research-idea-pipeline/routes/<R>/cognition/index.json
                 .research-idea-pipeline/routes/<R>/cognition/context-brief.md
                 rebuildable from the two layers above             ← never authoritative

**Support levels are computed, never declared.** A revision event may name a
mechanism's structure (variables, conditions, boundaries, predictions, rivals)
and must cite canonical ids. Whether that mechanism is speculation, a
literature-supported hypothesis, an experiment-supported mechanism or a refuted
mechanism is *derived* from `verification_tier` / `strength` / `epistemic_status`
/ `validity` / claim `status`. A revision that asserts support for itself is a
hard violation (`C2`), not a shortcut.

Rule ids are a separate namespace from the state checker:
`state_check.py` owns S1—S7 / V1—V24. This module owns `CM1`—`CM9` and never
redefines a state rule. See `references/cognitive-memory-policy.md`.

Usage
-----
    python3 cognition.py build    --state <state.json> [--cognition <dir>]
    python3 cognition.py validate --state <state.json> [--cognition <dir>]
    python3 cognition.py brief    --state <state.json> [--cognition <dir>] [--budget N]
    python3 cognition.py check    --state <state.json> [--cognition <dir>]
    python3 cognition.py --selftest
    python3 cognition.py --list-kinds

Exit codes (same convention as the rest of the skill):
    0  pass
    1  argument error
    3  hard violation
    4  environment not satisfied (missing / unreadable / invalid JSON)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SCHEMA_INDEX = "research-idea-pipeline/cognitive-index@1"
SCHEMA_REVISION = "research-idea-pipeline/cognition-revision@1"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_HARD = 3
EXIT_ENV = 4

COGNITION_DIRNAME = "cognition"
INDEX_NAME = "index.json"
REVISIONS_NAME = "model-revisions.jsonl"
BRIEF_NAME = "context-brief.md"

STATE_NAME = "research-state.json"

# ---------------------------------------------------------------------------
# Frozen vocabularies
# ---------------------------------------------------------------------------

#: Cognitive memory classes (Phase 1 §1.1). Each canonical class maps to one
#: projection section; none of them is a new first-class Research State object.
MEMORY_CLASSES: Tuple[str, ...] = (
    "mechanistic", "anomaly", "competition", "scientific_value",
)

#: Revision event kinds. `mechanism_*` and `competition_*` and `anomaly_record`
#: are Phase 1. `prediction_*` are Phase 2. `strategy_update` is Phase 3.
REVISION_KINDS: Tuple[str, ...] = (
    "mechanism_create",
    "mechanism_revise",
    "mechanism_weaken",
    "mechanism_refute",
    "mechanism_reactivate",
    "mechanism_merge",
    "anomaly_record",
    "competition_open",
    "competition_resolve",
    "prediction_freeze",
    "prediction_assessment",
    "strategy_update",
)

MECHANISM_KINDS: Tuple[str, ...] = tuple(
    kind for kind in REVISION_KINDS if kind.startswith("mechanism_"))

#: Actors permitted to append a revision. R12/R13 are read-only views of the
#: state and must not create cognitive revisions from narrative work.
REVISION_ACTORS: Tuple[str, ...] = (
    "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R9.O", "R10", "R11", "R14", "CIE",
)

#: Derived support ladder, weakest first. This replaces the free-text notion of
#: "how much do we believe this mechanism" with a function of canonical evidence.
SUPPORT_LEVELS: Tuple[str, ...] = (
    "speculative", "hypothesis", "literature_supported",
    "experiment_supported", "refuted",
)

#: Mechanism lifecycle status. Only `refuted` and `weakened` are evidence-driven;
#: `dormant` and `merged` are explicit research decisions and must be recorded as
#: such, not inferred.
MECHANISM_STATUSES: Tuple[str, ...] = (
    "active", "weakened", "refuted", "dormant", "merged",
)

COMPETITION_STATUSES: Tuple[str, ...] = (
    "open", "resolved", "undecidable_recorded",
)

#: Keys a revision event may never use, in any position of `after` / `before`.
#: These are exactly the canonical mutations a cognitive projection is forbidden
#: to perform: support self-certification, claim lifecycle, and research anchors.
FORBIDDEN_REVISION_KEYS: Tuple[str, ...] = (
    "epistemic_status", "support_level", "support", "claim_status",
    "claims_status", "contract", "anchor", "research_goal", "primary_anchor",
    "out_of_scope", "validity",
)

#: Structural fields a mechanism revision may carry.
MECHANISM_FIELDS: Tuple[str, ...] = (
    "statement", "scope", "core_variables", "dependencies",
    "necessary_conditions", "boundaries", "invariants", "counterexamples",
    "pending_predictions", "competes_with", "merged_into", "dormant", "note",
)

REF_KEYS: Tuple[str, ...] = (
    "claims", "evidence", "assumptions", "hypotheses", "experiments",
    "literature", "failures", "uncertainties",
)

EMPTY_REFS: Dict[str, List[str]] = {key: [] for key in REF_KEYS}

#: Id prefixes per canonical array, taken from state_check.py S2.
ID_PREFIX: Dict[str, str] = {
    "claims": "C", "evidence": "E", "assumptions": "AS", "hypotheses": "H",
    "experiments": "X", "literature": "LIT", "failures": "F", "uncertainties": "U",
}

CONTEXT_TIERS = ("hot", "warm", "cold")

#: Default context budget: characters of the generated brief. The brief is a
#: recovery aid, not a state dump; the policy requires a bounded context.
DEFAULT_BUDGET = 6000

VALUE_LIMIT = 72


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

class Diagnostic:
    """One machine-readable finding: rule id + JSON pointer + detail."""

    __slots__ = ("rule", "path", "detail")

    def __init__(self, rule: str, path: str, detail: str) -> None:
        self.rule = rule
        self.path = path
        self.detail = detail

    def render(self) -> str:
        return f"{self.rule}  {self.path}  {self.detail}"

    def as_dict(self) -> Dict[str, str]:
        return {"rule": self.rule, "path": self.path, "detail": self.detail}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Diagnostic):
            return NotImplemented
        return (self.rule, self.path, self.detail) == (other.rule, other.path, other.detail)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Diagnostic({self.rule!r}, {self.path!r})"


class CognitionError(Exception):
    """Environment-level failure: missing file, unreadable input, invalid JSON."""


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def canonical_json(value: Any) -> str:
    """Stable serialisation used for digests and for reproducibility tests."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest_of(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def digest_of_lines(records: Sequence[Dict[str, Any]]) -> str:
    return digest_of(list(records))


def load_state(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise CognitionError(f"state file not found: {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CognitionError(f"state file is not valid JSON: {path} ({exc})") from exc
    if not isinstance(doc, dict):
        raise CognitionError(f"state root must be an object: {path}")
    return doc


def load_revisions(path: Path) -> Tuple[List[Dict[str, Any]], List[Diagnostic]]:
    """Read the JSONL revision log. Malformed lines are reported, not raised.

    A torn last line (crash during append) must not make the whole cognitive
    memory unreadable; it becomes a diagnostic so the operator can repair it.
    """
    diagnostics: List[Diagnostic] = []
    records: List[Dict[str, Any]] = []
    if not path.exists():
        return records, diagnostics
    if not path.is_file():
        raise CognitionError(f"revision log is not a file: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise CognitionError(f"revision log is not valid UTF-8: {path}") from exc
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            diagnostics.append(Diagnostic(
                "CM1", f"{REVISIONS_NAME}:{lineno}",
                f"无法解析为 JSON（{exc.msg}）；请修复或删除该行"))
            continue
        if not isinstance(record, dict):
            diagnostics.append(Diagnostic(
                "CM1", f"{REVISIONS_NAME}:{lineno}", "修订事件必须是 JSON 对象"))
            continue
        record["_line"] = lineno
        records.append(record)
    return records, diagnostics


def cognition_dir_for(state_path: Path, override: Optional[Path] = None) -> Path:
    if override is not None:
        return override
    return state_path.parent / COGNITION_DIRNAME


def route_of(state_path: Path) -> str:
    """Route letter is the directory that owns the canonical state file."""
    return state_path.parent.name


# ---------------------------------------------------------------------------
# Canonical index: fast id lookup + validity
# ---------------------------------------------------------------------------

class CanonicalView:
    """Read-only view of the canonical state. The only source of scientific fact."""

    def __init__(self, state: Dict[str, Any]) -> None:
        self.state = state
        self.state_version = state.get("state_version") if isinstance(
            state.get("state_version"), int) else 0
        self.by_key: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for key in REF_KEYS:
            entries = state.get(key)
            table: Dict[str, Dict[str, Any]] = {}
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                        table.setdefault(entry["id"], entry)
            self.by_key[key] = table
        # assurance / repairs are carriers without uniform ids; expose them for
        # competition and refutation checks through their own lookups.
        self.assurance = state.get("assurance") if isinstance(state.get("assurance"), list) else []
        self.repairs = state.get("repairs") if isinstance(state.get("repairs"), list) else []

    def get(self, key: str, ident: str) -> Optional[Dict[str, Any]]:
        return self.by_key.get(key, {}).get(ident)

    def contains(self, key: str, ident: str) -> bool:
        return ident in self.by_key.get(key, {})

    def validity_of(self, key: str, ident: str) -> Tuple[str, str]:
        entry = self.get(key, ident)
        if entry is None:
            return "missing", "引用不存在"
        validity = entry.get("validity")
        if not isinstance(validity, dict):
            return "unknown", "缺少 validity"
        status = validity.get("status")
        reason = validity.get("reason")
        return (status if isinstance(status, str) else "unknown",
                reason if isinstance(reason, str) else "")


def normalize_refs(raw: Any) -> Dict[str, List[str]]:
    """Coerce a revision's `refs` block into the eight canonical arrays."""
    refs: Dict[str, List[str]] = {key: [] for key in REF_KEYS}
    if not isinstance(raw, dict):
        return refs
    for key in REF_KEYS:
        values = raw.get(key)
        if isinstance(values, list):
            refs[key] = [value for value in values if isinstance(value, str) and value.strip()]
    return refs


def iter_refs(refs: Dict[str, List[str]]) -> Iterable[Tuple[str, str]]:
    for key in REF_KEYS:
        for ident in refs.get(key, []):
            yield key, ident


def merge_refs(target: Dict[str, List[str]], extra: Dict[str, List[str]]) -> Dict[str, List[str]]:
    merged = {key: list(target.get(key, [])) for key in REF_KEYS}
    for key in REF_KEYS:
        for ident in extra.get(key, []):
            if ident not in merged[key]:
                merged[key].append(ident)
    return merged


# ---------------------------------------------------------------------------
# Derived support — the anti self-certification core
# ---------------------------------------------------------------------------

TIER_ORDER: Dict[str, int] = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "T4": 4, "T5": 5}

#: Refutation through a failure memory entry requires one of these kinds.
REFUTING_FAILURE_KINDS: Tuple[str, ...] = ("falsified", "failed-to-reproduce")


def tier_at_least(tier: Any, floor: int) -> bool:
    if not isinstance(tier, str) or tier not in TIER_ORDER:
        return False
    return TIER_ORDER[tier] >= floor


def derive_support(
    view: CanonicalView,
    refs: Dict[str, List[str]],
    declared: Optional[str] = None,
) -> Tuple[str, List[str], List[str]]:
    """Derive a mechanism's support level from canonical facts only.

    Returns `(level, reasons, conflicts)`. `reasons` records which canonical
    objects produced the level; `conflicts` records a disagreement between what
    a revision claimed about itself and what the canonical evidence supports.
    The derivation never reads a revision-declared level.
    """
    reasons: List[str] = []
    has_any_ref = any(refs.get(key) for key in REF_KEYS)

    # --- refutation takes precedence over every positive signal -------------
    for claim_id in refs.get("claims", []):
        claim = view.get("claims", claim_id)
        if isinstance(claim, dict) and claim.get("status") in ("contradicted", "killed"):
            reasons.append(f"claims[{claim_id}].status={claim['status']}")
    for evidence_id in refs.get("evidence", []):
        evidence = view.get("evidence", evidence_id)
        if not isinstance(evidence, dict):
            continue
        contradicts = evidence.get("contradicts")
        status, _ = view.validity_of("evidence", evidence_id)
        if (isinstance(contradicts, list) and contradicts
                and tier_at_least(evidence.get("verification_tier"), 2)
                and status == "valid"):
            reasons.append(f"evidence[{evidence_id}] 反驳且达 T2")
    for failure_id in refs.get("failures", []):
        failure = view.get("failures", failure_id)
        if isinstance(failure, dict) and failure.get("kind") in REFUTING_FAILURE_KINDS:
            reasons.append(f"failures[{failure_id}].kind={failure['kind']}")
    for repair in view.repairs:
        if not isinstance(repair, dict) or repair.get("disposition") != "KILL_BRANCH":
            continue
        targets = repair.get("targets")
        if not isinstance(targets, list):
            continue
        touched = set(refs.get("claims", [])) | set(refs.get("hypotheses", []))
        if touched & {t for t in targets if isinstance(t, str)}:
            reasons.append("repairs[KILL_BRANCH] 覆盖本机制引用的候选")
    if reasons:
        return "refuted", reasons, _conflict("refuted", declared)

    # --- experiment support -------------------------------------------------
    for evidence_id in refs.get("evidence", []):
        evidence = view.get("evidence", evidence_id)
        if not isinstance(evidence, dict):
            continue
        status, _ = view.validity_of("evidence", evidence_id)
        if status != "valid" or not tier_at_least(evidence.get("verification_tier"), 2):
            continue
        if evidence.get("kind") != "experiment" or evidence.get("strength") != "strong":
            continue
        if evidence.get("epistemic_status") not in ("Observed", "Supported"):
            continue
        supports = evidence.get("supports")
        backed = False
        if isinstance(supports, list):
            for claim_id in supports:
                claim = view.get("claims", claim_id)
                if isinstance(claim, dict) and claim.get("status") in ("supported", "partially-supported"):
                    backed = True
                    reasons.append(f"evidence[{evidence_id}] 支持 claims[{claim_id}]（{claim['status']}）")
        if backed:
            return "experiment_supported", reasons, _conflict("experiment_supported", declared)

    # --- literature support -------------------------------------------------
    for evidence_id in refs.get("evidence", []):
        evidence = view.get("evidence", evidence_id)
        if not isinstance(evidence, dict):
            continue
        status, _ = view.validity_of("evidence", evidence_id)
        if status != "valid" or not tier_at_least(evidence.get("verification_tier"), 1):
            continue
        if evidence.get("kind") == "literature":
            reasons.append(f"evidence[{evidence_id}] 为文献证据且达 T1")
        elif evidence.get("epistemic_status") == "Supported":
            reasons.append(f"evidence[{evidence_id}] epistemic_status=Supported")
    if reasons:
        return "literature_supported", reasons, _conflict("literature_supported", declared)
    for literature_id in refs.get("literature", []):
        literature = view.get("literature", literature_id)
        if isinstance(literature, dict) and literature.get("relation") in ("supports", "uses-same-theory"):
            reasons.append(f"literature[{literature_id}].relation={literature['relation']}")
    if reasons:
        return "literature_supported", reasons, _conflict("literature_supported", declared)

    if not has_any_ref:
        return "speculative", ["无 canonical 引用"], _conflict("speculative", declared)
    for hypothesis_id in refs.get("hypotheses", []):
        if view.contains("hypotheses", hypothesis_id):
            reasons.append(f"hypotheses[{hypothesis_id}] 为候选解释")
    for assumption_id in refs.get("assumptions", []):
        if view.contains("assumptions", assumption_id):
            reasons.append(f"assumptions[{assumption_id}] 为显式假设")
    return "hypothesis", (reasons or ["仅有人工登记的机制结构"]), _conflict("hypothesis", declared)


def _conflict(derived: str, declared: Optional[str]) -> List[str]:
    if declared is None:
        return []
    if declared == derived:
        return []
    return [f"修订声明的支持等级为 {declared}，canonical 事实推出 {derived}；以 canonical 为准"]


def stagnation_fingerprint(view: CanonicalView, refs: Dict[str, List[str]]) -> str:
    """A stable identity for 'the same explanation proposed again'.

    Two mechanisms with the same canonical anchor set explain the same facts
    from the same starting point; treating them as independent progress is the
    duplication this engine exists to prevent.
    """
    anchors: List[str] = []
    for key, ident in iter_refs(refs):
        anchors.append(f"{key}:{ident}")
    return digest_of(sorted(anchors))


# ---------------------------------------------------------------------------
# Index construction (pure function of state + revisions)
# ---------------------------------------------------------------------------

def _empty_structure() -> Dict[str, Any]:
    return {
        "core_variables": [], "dependencies": [], "necessary_conditions": [],
        "boundaries": [], "invariants": [], "counterexamples": [],
        "pending_predictions": [], "competes_with": [],
    }


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


class _Builder:
    """Folds the revision log into projected cognitive structures."""

    def __init__(self, view: CanonicalView, revisions: Sequence[Dict[str, Any]]) -> None:
        self.view = view
        self.revisions = sorted(
            (record for record in revisions if isinstance(record, dict)),
            key=lambda record: (record.get("seq") if isinstance(record.get("seq"), int) else 0,
                                record.get("_line", 0)),
        )
        self.diagnostics: List[Diagnostic] = []
        self.mechanisms: Dict[str, Dict[str, Any]] = {}
        self.anomalies: Dict[str, Dict[str, Any]] = {}
        self.competitions: Dict[str, Dict[str, Any]] = {}

    # -- helpers ------------------------------------------------------------
    def _resolve(self, refs: Dict[str, List[str]], path: str) -> Tuple[List[str], List[str]]:
        """Return `(stale_reasons, missing_refs)` for a reference set."""
        stale: List[str] = []
        missing: List[str] = []
        for key, ident in iter_refs(refs):
            if not self.view.contains(key, ident):
                missing.append(f"{key}:{ident}")
                self.diagnostics.append(Diagnostic(
                    "CM3", path, f"引用的 canonical 对象不存在：{key}[{ident}]"))
                continue
            status, reason = self.view.validity_of(key, ident)
            if status in ("invalid", "stale", "pending"):
                stale.append(f"{key}[{ident}].validity={status}" + (f"（{reason}）" if reason else ""))
                self.diagnostics.append(Diagnostic(
                    "CM3", path,
                    f"引用的对象已失效：{key}[{ident}]（{status}）；该认知条目自动标记过期并退出 hot memory"))
            elif status == "unknown":
                stale.append(f"{key}[{ident}] 缺少 validity.status")
        return stale, missing

    def _mechanism(self, subject: str, path: str) -> Dict[str, Any]:
        entry = self.mechanisms.get(subject)
        if entry is None:
            entry = {
                "id": subject,
                "statement": "",
                "scope": "",
                "structure": _empty_structure(),
                "declared_intents": [],
                "refs": {key: [] for key in REF_KEYS},
                "revision_ids": [],
                "first_seq": None,
                "last_seq": None,
                "merged_into": None,
                "dormant": False,
                "lost_competitions": [],
                "won_competitions": [],
            }
            self.mechanisms[subject] = entry
        return entry

    # -- revision folding ---------------------------------------------------
    def fold(self) -> None:
        seen_ids: Dict[str, int] = {}
        for record in self.revisions:
            path = f"{REVISIONS_NAME}:{record.get('_line', '?')}"
            ident = record.get("id")
            if isinstance(ident, str):
                if ident in seen_ids:
                    self.diagnostics.append(Diagnostic(
                        "CM1", path, f"修订事件 id 重复：{ident}"))
                seen_ids[ident] = record.get("_line", 0)
            kind = record.get("kind")
            if kind not in REVISION_KINDS:
                self.diagnostics.append(Diagnostic(
                    "CM1", path, f"未知的修订事件类型：{kind!r}"))
                continue
            refs = normalize_refs(record.get("refs"))
            subject = record.get("subject")
            if not isinstance(subject, str) or not subject.strip():
                self.diagnostics.append(Diagnostic("CM1", path, "修订事件缺少 subject"))
                continue
            if kind in MECHANISM_KINDS:
                self._fold_mechanism(record, refs, subject, kind, path)
            elif kind == "anomaly_record":
                self._fold_anomaly(record, refs, subject, path)
            elif kind in ("competition_open", "competition_resolve"):
                self._fold_competition(record, refs, subject, kind, path)
            # prediction_* and strategy_update are folded by their own phases;
            # they are accepted here so the log stays a single append-only file.

    def _apply_structure(self, entry: Dict[str, Any], payload: Any, path: str) -> None:
        if payload is None:
            return
        if not isinstance(payload, dict):
            self.diagnostics.append(Diagnostic("CM1", path, "after/before 必须是对象"))
            return
        for key in payload:
            if key in FORBIDDEN_REVISION_KEYS:
                self.diagnostics.append(Diagnostic(
                    "CM2", path,
                    f"修订事件不得声明 {key}；支持等级与 Claim 状态只能由 canonical 证据推出"))
                continue
            if key == "declared_support":
                # Accepted only so it can be recorded as a conflict (CM7); it is
                # never adopted as the mechanism's support level.
                continue
            if key not in MECHANISM_FIELDS:
                self.diagnostics.append(Diagnostic(
                    "CM1", path, f"未知的机制字段：{key}"))
                continue
        for field in ("statement", "scope", "note"):
            if isinstance(payload.get(field), str) and payload[field].strip():
                entry[field] = payload[field]
        structure = entry["structure"]
        for field in ("core_variables", "dependencies", "necessary_conditions",
                      "boundaries", "invariants", "counterexamples", "pending_predictions"):
            if field in payload:
                structure[field] = _as_list(payload.get(field))
        if "competes_with" in payload:
            rivals = [r for r in _as_list(payload.get("competes_with")) if isinstance(r, str)]
            for rival in rivals:
                if rival not in structure["competes_with"]:
                    structure["competes_with"].append(rival)
        if isinstance(payload.get("merged_into"), str):
            entry["merged_into"] = payload["merged_into"]
        if payload.get("dormant") is True:
            entry["dormant"] = True

    def _fold_mechanism(self, record: Dict[str, Any], refs: Dict[str, List[str]],
                        subject: str, kind: str, path: str) -> None:
        entry = self._mechanism(subject, path)
        seq = record.get("seq")
        if not isinstance(seq, int):
            self.diagnostics.append(Diagnostic("CM1", path, "修订事件缺少整数 seq"))
            return
        if entry["first_seq"] is None:
            entry["first_seq"] = seq
        entry["last_seq"] = seq
        entry["revision_ids"].append(record.get("id"))
        entry["refs"] = merge_refs(entry["refs"], refs)
        entry["declared_intents"].append(kind)
        self._apply_structure(entry, record.get("after"), path)
        if kind == "mechanism_create" and not entry["statement"]:
            self.diagnostics.append(Diagnostic(
                "CM4", path, f"新建机制 {subject} 必须给出 statement"))

    def _fold_anomaly(self, record: Dict[str, Any], refs: Dict[str, List[str]],
                      subject: str, path: str) -> None:
        entry = self.anomalies.get(subject)
        if entry is None:
            entry = {
                "id": subject,
                "observation": "",
                "frozen_prediction": None,
                "reproduced": None,
                "importance": "medium",
                "open_question": "",
                "related_mechanisms": [],
                "refs": {key: [] for key in REF_KEYS},
                "revision_ids": [],
                "last_seq": None,
            }
            self.anomalies[subject] = entry
        entry["revision_ids"].append(record.get("id"))
        entry["refs"] = merge_refs(entry["refs"], refs)
        entry["last_seq"] = record.get("seq")
        after = record.get("after")
        if isinstance(after, dict):
            for field in ("observation", "importance", "open_question", "frozen_prediction"):
                if field in after and not isinstance(after.get(field), (dict, list)):
                    entry[field] = after.get(field)
            if isinstance(after.get("reproduced"), bool):
                entry["reproduced"] = after["reproduced"]
            if isinstance(after.get("related_mechanisms"), list):
                entry["related_mechanisms"] = [m for m in after["related_mechanisms"]
                                               if isinstance(m, str)]
        if not entry["observation"]:
            self.diagnostics.append(Diagnostic(
                "CM5", path, f"异常 {subject} 必须给出 observation"))

    def _fold_competition(self, record: Dict[str, Any], refs: Dict[str, List[str]],
                          subject: str, kind: str, path: str) -> None:
        entry = self.competitions.get(subject)
        if entry is None:
            entry = {
                "id": subject,
                "mechanisms": [],
                "shared_explanation": "",
                "conflicting_predictions": [],
                "discriminating_intervention": "TBD",
                "status": "open",
                "conclusion": "",
                "decidable": None,
                "refs": {key: [] for key in REF_KEYS},
                "revision_ids": [],
                "last_seq": None,
            }
            self.competitions[subject] = entry
        entry["revision_ids"].append(record.get("id"))
        entry["refs"] = merge_refs(entry["refs"], refs)
        entry["last_seq"] = record.get("seq")
        after = record.get("after")
        if isinstance(after, dict):
            if isinstance(after.get("mechanisms"), list):
                entry["mechanisms"] = [m for m in after["mechanisms"] if isinstance(m, str)]
            for field in ("shared_explanation", "discriminating_intervention", "conclusion"):
                if isinstance(after.get(field), str):
                    entry[field] = after[field]
            if isinstance(after.get("conflicting_predictions"), list):
                entry["conflicting_predictions"] = list(after["conflicting_predictions"])
            if isinstance(after.get("decidable"), bool):
                entry["decidable"] = after["decidable"]
        if kind == "competition_open":
            if len(entry["mechanisms"]) < 2:
                self.diagnostics.append(Diagnostic(
                    "CM6", path, f"竞争 {subject} 必须给出至少两个机制"))
        else:
            entry["status"] = "resolved"
            winner = after.get("winner") if isinstance(after, dict) else None
            if isinstance(winner, str):
                entry["winner"] = winner
                for rival in entry["mechanisms"]:
                    mechanism = self.mechanisms.get(rival)
                    if mechanism is None:
                        continue
                    if rival == winner:
                        mechanism["won_competitions"].append(subject)
                    else:
                        mechanism["lost_competitions"].append(subject)
            if isinstance(after, dict) and after.get("decidable") is False and not winner:
                entry["status"] = "undecidable_recorded"
            if not entry["conclusion"]:
                self.diagnostics.append(Diagnostic(
                    "CM6", path, f"竞争 {subject} 收口必须给出 conclusion"))

    # -- projection ---------------------------------------------------------
    def project(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        mechanisms = [self._project_mechanism(mid) for mid in _id_order(self.mechanisms)]
        anomalies = [self._project_anomaly(aid) for aid in _id_order(self.anomalies)]
        competitions = [self._project_competition(cid) for cid in _id_order(self.competitions)]
        return mechanisms, anomalies, competitions

    def _project_mechanism(self, mid: str) -> Dict[str, Any]:
        entry = self.mechanisms[mid]
        path = f"mechanisms[{mid}]"
        stale, missing = self._resolve(entry["refs"], path)
        declared = None
        for record in self.revisions:
            if record.get("subject") == mid and record.get("kind") in MECHANISM_KINDS:
                after = record.get("after")
                if isinstance(after, dict):
                    candidate = after.get("declared_support")
                    if isinstance(candidate, str):
                        declared = candidate
        level, reasons, conflicts = derive_support(self.view, entry["refs"], declared)
        for conflict in conflicts:
            self.diagnostics.append(Diagnostic("CM7", path, conflict))
        status = _mechanism_status(entry, level)
        unresolved = bool(missing)
        return {
            "id": mid,
            "statement": entry["statement"],
            "scope": entry["scope"],
            "structure": entry["structure"],
            "support_level": level,
            "support_reasons": reasons,
            "status": status,
            "stale": bool(stale) or unresolved,
            "stale_reasons": stale,
            "missing_refs": missing,
            "canonical_refs": {key: list(entry["refs"].get(key, [])) for key in REF_KEYS},
            "revision_ids": [r for r in entry["revision_ids"] if isinstance(r, str)],
            "fingerprint": stagnation_fingerprint(self.view, entry["refs"]),
            "lost_competitions": entry["lost_competitions"],
            "won_competitions": entry["won_competitions"],
            "declared_intents": entry["declared_intents"],
        }

    def _project_anomaly(self, aid: str) -> Dict[str, Any]:
        entry = self.anomalies[aid]
        path = f"anomalies[{aid}]"
        stale, missing = self._resolve(entry["refs"], path)
        return {
            "id": aid,
            "observation": entry["observation"],
            "frozen_prediction": entry["frozen_prediction"],
            "reproduced": entry["reproduced"],
            "importance": entry["importance"],
            "open_question": entry["open_question"],
            "related_mechanisms": entry["related_mechanisms"],
            "canonical_refs": {key: list(entry["refs"].get(key, [])) for key in REF_KEYS},
            "revision_ids": [r for r in entry["revision_ids"] if isinstance(r, str)],
            "stale": bool(stale) or bool(missing),
            "stale_reasons": stale,
            "missing_refs": missing,
        }

    def _project_competition(self, cid: str) -> Dict[str, Any]:
        entry = self.competitions[cid]
        path = f"competitions[{cid}]"
        stale, missing = self._resolve(entry["refs"], path)
        known = [m for m in entry["mechanisms"] if m in self.mechanisms]
        unknown = [m for m in entry["mechanisms"] if m not in self.mechanisms]
        for rival in unknown:
            self.diagnostics.append(Diagnostic(
                "CM6", path, f"竞争引用了未登记的机制：{rival}（该机制在本日志中没有任何修订事件）"))
        payload = {
            "id": cid,
            "mechanisms": entry["mechanisms"],
            "shared_explanation": entry["shared_explanation"],
            "conflicting_predictions": entry["conflicting_predictions"],
            "discriminating_intervention": entry["discriminating_intervention"],
            "status": entry["status"],
            "conclusion": entry["conclusion"],
            "decidable": entry["decidable"],
            "canonical_refs": {key: list(entry["refs"].get(key, [])) for key in REF_KEYS},
            "revision_ids": [r for r in entry["revision_ids"] if isinstance(r, str)],
            "stale": bool(stale) or bool(missing),
            "stale_reasons": stale,
            "missing_refs": missing,
            "has_distinguishing_power": bool(
                entry["conflicting_predictions"]
                and entry["discriminating_intervention"] not in ("", "TBD", None)),
        }
        if entry.get("winner"):
            payload["winner"] = entry["winner"]
        if not payload["has_distinguishing_power"] and entry["status"] == "open":
            self.diagnostics.append(Diagnostic(
                "CM8", path,
                "开放竞争尚未给出「冲突预测 + 判别干预」；仅并列多个可能原因不算机制竞争"))
        return payload


def _id_order(table: Dict[str, Any]) -> List[str]:
    """Deterministic order: numeric id suffix, then registration sequence."""
    def key(ident: str) -> Tuple[int, int, str]:
        digits = "".join(ch for ch in ident if ch.isdigit())
        try:
            number = int(digits) if digits else 0
        except ValueError:  # pragma: no cover - digits-only guard
            number = 0
        entry = table[ident]
        seq = entry.get("first_seq") if isinstance(entry, dict) else None
        return (number, seq if isinstance(seq, int) else 0, ident)
    return sorted(table, key=key)


def _mechanism_status(entry: Dict[str, Any], level: str) -> str:
    if level == "refuted":
        return "refuted"
    if entry.get("merged_into"):
        return "merged"
    if entry.get("dormant"):
        return "dormant"
    if entry.get("lost_competitions"):
        return "weakened"
    intents = entry.get("declared_intents") or []
    if "mechanism_weaken" in intents and "mechanism_reactivate" not in intents:
        return "weakened"
    return "active"


def build_index(
    state: Dict[str, Any],
    revisions: Sequence[Dict[str, Any]],
    route: str = "",
) -> Tuple[Dict[str, Any], List[Diagnostic]]:
    """Build the cognitive index. Pure: no I/O, no mutation of `state`."""
    view = CanonicalView(state)
    builder = _Builder(view, revisions)
    builder.fold()
    mechanisms, anomalies, competitions = builder.project()
    diagnostics = builder.diagnostics

    duplicates: Dict[str, List[str]] = {}
    for mechanism in mechanisms:
        duplicates.setdefault(mechanism["fingerprint"], []).append(mechanism["id"])
    for fingerprint, ids in sorted(duplicates.items()):
        if len(ids) > 1:
            diagnostics.append(Diagnostic(
                "CM9", "mechanisms[]",
                f"机制 {ids} 的 canonical 锚点集合完全相同（fingerprint {fingerprint[:19]}…）；"
                "实质等价的解释不得当作独立进展"))

    index = {
        "_schema": SCHEMA_INDEX,
        "route": route,
        "state_version": view.state_version,
        "digest": {
            "state": digest_of(state),
            "revisions": digest_of_lines([_strip_internal(r) for r in revisions]),
        },
        "mechanisms": mechanisms,
        "anomalies": anomalies,
        "competitions": competitions,
        "counts": {
            "mechanisms": len(mechanisms),
            "anomalies": len(anomalies),
            "competitions": len(competitions),
            "stale_mechanisms": sum(1 for m in mechanisms if m["stale"]),
            "refuted_mechanisms": sum(1 for m in mechanisms if m["status"] == "refuted"),
        },
        "diagnostics": [d.as_dict() for d in sorted(
            diagnostics, key=lambda d: (d.rule, d.path, d.detail))],
    }
    return index, diagnostics


def _strip_internal(record: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in record.items() if not key.startswith("_")}


def full_index(
    state: Dict[str, Any],
    revisions: Sequence[Dict[str, Any]],
    route: str = "",
) -> Tuple[Dict[str, Any], List[Diagnostic]]:
    """The index as written to disk: projection plus the complete diagnostic set.

    A single entry point, so `build`, `validate`, `check`, `brief` and `recall`
    can never disagree about what the index should contain.
    """
    index, build_diagnostics = build_index(state, revisions, route)
    diagnostics = _dedupe(list(build_diagnostics) + validate_revisions(state, revisions))
    index["diagnostics"] = [d.as_dict() for d in sorted(
        diagnostics, key=lambda d: (d.rule, d.path, d.detail))]
    return index, diagnostics


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_revisions(
    state: Dict[str, Any],
    revisions: Sequence[Dict[str, Any]],
) -> List[Diagnostic]:
    """Validate the append-only revision log against canonical state."""
    view = CanonicalView(state)
    diagnostics: List[Diagnostic] = []
    seen_ids: Dict[str, int] = {}
    last_seq = 0
    for record in revisions:
        path = f"{REVISIONS_NAME}:{record.get('_line', '?')}"
        if record.get("_schema") != SCHEMA_REVISION:
            diagnostics.append(Diagnostic(
                "CM1", path, f"_schema 必须是 {SCHEMA_REVISION!r}"))
        ident = record.get("id")
        if not isinstance(ident, str) or not ident.strip():
            diagnostics.append(Diagnostic("CM1", path, "缺少非空 id"))
        elif ident in seen_ids:
            diagnostics.append(Diagnostic("CM1", path, f"id 重复：{ident}"))
        else:
            seen_ids[ident] = record.get("_line", 0)
        seq = record.get("seq")
        if not isinstance(seq, int) or isinstance(seq, bool) or seq < 1:
            diagnostics.append(Diagnostic("CM1", path, "seq 必须是正整数"))
        else:
            if seq <= last_seq:
                diagnostics.append(Diagnostic(
                    "CM1", path, f"seq 必须严格递增（当前 {seq}，前一条 {last_seq}）"))
            last_seq = seq
        kind = record.get("kind")
        if kind not in REVISION_KINDS:
            diagnostics.append(Diagnostic("CM1", path, f"未知的事件类型：{kind!r}"))
        if not isinstance(record.get("summary"), str) or not record.get("summary", "").strip():
            diagnostics.append(Diagnostic("CM1", path, "缺少非空 summary"))
        actor = record.get("actor")
        if actor not in REVISION_ACTORS:
            diagnostics.append(Diagnostic(
                "CM1", path, f"actor 必须是 {list(REVISION_ACTORS)} 之一，实际 {actor!r}"))
        version = record.get("at_state_version")
        if not isinstance(version, int) or isinstance(version, bool) or version < 0:
            diagnostics.append(Diagnostic("CM1", path, "at_state_version 必须是非负整数"))
        elif version > view.state_version:
            diagnostics.append(Diagnostic(
                "CM3", path,
                f"at_state_version={version} 超过当前 state_version={view.state_version}；"
                "修订不得指向未来状态"))
        trigger = record.get("trigger")
        if not isinstance(trigger, dict) or not str(trigger.get("kind", "")).strip():
            diagnostics.append(Diagnostic(
                "CM3", path, "缺少 trigger（认知修订必须指明触发它的 canonical 事件或证据）"))
        refs = normalize_refs(record.get("refs"))
        if not any(refs.get(key) for key in REF_KEYS):
            diagnostics.append(Diagnostic(
                "CM3", path, "refs 为空：认知修订必须指向 canonical 状态、实验结果或有效修订记录"))
        for key, ref_ident in iter_refs(refs):
            if not view.contains(key, ref_ident):
                diagnostics.append(Diagnostic(
                    "CM3", path, f"悬空引用 {key}[{ref_ident}]"))
                continue
            status, reason = view.validity_of(key, ref_ident)
            if status in ("invalid", "stale", "pending"):
                diagnostics.append(Diagnostic(
                    "CM3", path,
                    f"引用了失效对象 {key}[{ref_ident}]（{status}）；该修订必须重审或标记不可恢复"))
        for field in ("before", "after"):
            payload = record.get(field)
            if payload is None:
                continue
            if not isinstance(payload, dict):
                diagnostics.append(Diagnostic("CM1", path, f"{field} 必须是对象"))
                continue
            for key, value in payload.items():
                if key in FORBIDDEN_REVISION_KEYS:
                    diagnostics.append(Diagnostic(
                        "CM2", path,
                        f"{field}.{key} 被禁止：认知修订不得声明支持等级、Claim 状态或研究锚点"))
                elif key not in MECHANISM_FIELDS and key not in (
                        "observation", "importance", "reproduced", "open_question",
                        "frozen_prediction", "related_mechanisms", "mechanisms",
                        "shared_explanation", "conflicting_predictions",
                        "discriminating_intervention", "decidable", "winner",
                        "conclusion", "assessment", "outcome_class",
                        "prediction_id", "observed", "tolerance", "declared_support"):
                    diagnostics.append(Diagnostic("CM1", path, f"{field} 含未知字段：{key}"))
                elif key == "declared_support":
                    diagnostics.append(Diagnostic(
                        "CM7", path,
                        "declared_support 只是自评；支持等级一律由 canonical 事实推出，"
                        "该字段会被记录为冲突而不被采用"))
    return diagnostics


def validate_index(
    state: Dict[str, Any],
    revisions: Sequence[Dict[str, Any]],
    index: Dict[str, Any],
) -> List[Diagnostic]:
    """Recompute the index and compare. Any drift is a hard violation."""
    diagnostics: List[Diagnostic] = []
    if index.get("_schema") != SCHEMA_INDEX:
        diagnostics.append(Diagnostic(
            "CM3", INDEX_NAME, f"_schema 必须是 {SCHEMA_INDEX!r}"))
    if index.get("state_version") != state.get("state_version"):
        diagnostics.append(Diagnostic(
            "CM3", INDEX_NAME,
            f"索引 state_version={index.get('state_version')} 与 "
            f"canonical state_version={state.get('state_version')} 不一致"))
    digest = index.get("digest") if isinstance(index.get("digest"), dict) else {}
    if digest.get("state") != digest_of(state):
        diagnostics.append(Diagnostic(
            "CM3", INDEX_NAME, "索引的 state 摘要与当前 research-state.json 不一致；必须重建"))
    if digest.get("revisions") != digest_of_lines(
            [_strip_internal(r) for r in revisions]):
        diagnostics.append(Diagnostic(
            "CM3", INDEX_NAME, "索引的 revisions 摘要与当前 model-revisions.jsonl 不一致；必须重建"))
    expected, build_diagnostics = full_index(
        state, revisions, str(index.get("route", "")))
    # Diagnostics are advisory output, not projected science: compare the
    # projection itself, so a torn log line cannot masquerade as index drift.
    left = {k: v for k, v in expected.items() if k != "diagnostics"}
    right = {k: v for k, v in index.items() if k != "diagnostics"}
    if canonical_json(left) != canonical_json(right):
        diagnostics.append(Diagnostic(
            "CM3", INDEX_NAME, "索引内容与由 canonical state + revisions 重建的结果不一致"))
    for entry in index.get("mechanisms", []) if isinstance(index.get("mechanisms"), list) else []:
        if not isinstance(entry, dict):
            continue
        level = entry.get("support_level")
        if level not in SUPPORT_LEVELS:
            diagnostics.append(Diagnostic(
                "CM3", f"{INDEX_NAME}:mechanisms[{entry.get('id')}]",
                f"support_level 非法：{level!r}"))
        status = entry.get("status")
        if status not in MECHANISM_STATUSES:
            diagnostics.append(Diagnostic(
                "CM3", f"{INDEX_NAME}:mechanisms[{entry.get('id')}]",
                f"status 非法：{status!r}"))
    for entry in index.get("competitions", []) if isinstance(index.get("competitions"), list) else []:
        if isinstance(entry, dict) and entry.get("status") not in COMPETITION_STATUSES:
            diagnostics.append(Diagnostic(
                "CM3", f"{INDEX_NAME}:competitions[{entry.get('id')}]",
                f"status 非法：{entry.get('status')!r}"))
    diagnostics.extend(build_diagnostics)
    return _dedupe(diagnostics)


def _dedupe(diagnostics: Iterable[Diagnostic]) -> List[Diagnostic]:
    seen: Dict[Tuple[str, str, str], Diagnostic] = {}
    for diagnostic in diagnostics:
        seen.setdefault((diagnostic.rule, diagnostic.path, diagnostic.detail), diagnostic)
    return [seen[key] for key in sorted(seen)]


# ---------------------------------------------------------------------------
# Context recovery: hot / warm / cold
# ---------------------------------------------------------------------------

def focus_ids(view: CanonicalView) -> List[str]:
    """Ids the current research question directly needs (hot-memory seed)."""
    focus: List[str] = []
    for uncertainty in view.state.get("uncertainties", []) or []:
        if not isinstance(uncertainty, dict):
            continue
        if uncertainty.get("status") != "open":
            continue
        if uncertainty.get("importance") in ("critical", "high"):
            _push(focus, uncertainty.get("id"))
            test = uncertainty.get("cheapest_discriminating_test")
            if isinstance(test, str) and test != "TBD":
                _push(focus, test)
    for claim in view.state.get("claims", []) or []:
        if isinstance(claim, dict) and claim.get("status") in ("partially-supported", "supported"):
            _push(focus, claim.get("id"))
    for experiment in view.state.get("experiments", []) or []:
        if isinstance(experiment, dict) and experiment.get("status") in ("planned", "running"):
            _push(focus, experiment.get("id"))
    for repair in view.repairs:
        if isinstance(repair, dict) and repair.get("closure") == "ACCEPTED_LIMITATION":
            for target in _as_list(repair.get("targets")):
                if isinstance(target, str):
                    _push(focus, target)
    for hypothesis in view.state.get("hypotheses", []) or []:
        if isinstance(hypothesis, dict) and hypothesis.get("status") in ("active", "elite"):
            _push(focus, hypothesis.get("id"))
    return focus


def _push(target: List[str], value: Any) -> None:
    if isinstance(value, str) and value and value not in target:
        target.append(value)


def recall(
    index: Dict[str, Any],
    state: Dict[str, Any],
    budget: int = DEFAULT_BUDGET,
) -> Dict[str, Any]:
    """Select a bounded, relevant, provenance-carrying context slice."""
    view = CanonicalView(state)
    focus = set(focus_ids(view))
    hot: List[Dict[str, Any]] = []
    warm: List[Dict[str, Any]] = []
    cold: List[Dict[str, Any]] = []

    candidates: List[Tuple[int, int, str, Dict[str, Any]]] = []
    for mechanism in index.get("mechanisms", []) or []:
        refs = set()
        for values in (mechanism.get("canonical_refs") or {}).values():
            if isinstance(values, list):
                refs.update(v for v in values if isinstance(v, str))
        overlap = len(refs & focus)
        candidates.append((-overlap, refs and 0 or 1, str(mechanism.get("id")), mechanism))
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))

    for _, _, _, mechanism in candidates:
        entry = {
            "id": mechanism.get("id"),
            "statement": mechanism.get("statement", ""),
            "support_level": mechanism.get("support_level"),
            "status": mechanism.get("status"),
            "scope": mechanism.get("scope", ""),
            "refs": mechanism.get("canonical_refs", {}),
            "stale": mechanism.get("stale", False),
        }
        if mechanism.get("stale"):
            entry["stale_reasons"] = mechanism.get("stale_reasons", [])
            cold.append(entry)
            continue
        if mechanism.get("status") in ("active", "weakened") and reuse_overlap(mechanism, focus):
            hot.append(entry)
        elif mechanism.get("status") in ("refuted", "weakened"):
            warm.append(entry)
        else:
            cold.append(entry)

    anomalies_hot = [a for a in index.get("anomalies", []) or []
                     if not a.get("stale") and a.get("importance") in ("critical", "high")]
    competitions_open = [c for c in index.get("competitions", []) or []
                         if c.get("status") in ("open", "undecidable_recorded") and not c.get("stale")]

    return {
        "focus": sorted(focus),
        "hot": {"mechanisms": hot, "anomalies": anomalies_hot, "competitions": competitions_open},
        "warm": {"mechanisms": warm},
        "cold": {"mechanisms": cold},
        "failure_constraints": failure_constraints(state),
        "open_obligations": open_obligations(state),
        "budget": budget,
    }


def reuse_overlap(mechanism: Dict[str, Any], focus: set) -> bool:
    for values in (mechanism.get("canonical_refs") or {}).values():
        if isinstance(values, list) and focus & {v for v in values if isinstance(v, str)}:
            return True
    return False


#: Failure kinds that forbid a plain repeat of the same protocol.
REPEAT_BLOCKING_KINDS: Tuple[str, ...] = ("falsified", "failed-to-reproduce", "unsupported")


def failure_constraints(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Recover failure memory together with its repeat-prohibition conditions.

    Phase 1 requires a new session to recover "历史失败及其禁止重复条件".
    Failure memory is canonical (`failures[]`); this function only selects and
    summarises it, and never invents a condition that the state does not carry.
    """
    constraints: List[Dict[str, Any]] = []
    failures = state.get("failures")
    if not isinstance(failures, list):
        return constraints
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        kind = failure.get("kind")
        stop_rules = [r for r in _as_list(failure.get("stop_rules")) if isinstance(r, dict)]
        negative = [n for n in _as_list(failure.get("negative_knowledge")) if isinstance(n, dict)]
        if not stop_rules and not negative and kind not in REPEAT_BLOCKING_KINDS:
            continue
        retry_flags = [n.get("retry_allowed") for n in negative
                       if isinstance(n.get("retry_allowed"), bool)]
        if any(flag is False for flag in retry_flags):
            retry = "blocked"
        elif any(flag is True for flag in retry_flags):
            retry = "conditional"
        elif kind in REPEAT_BLOCKING_KINDS:
            retry = "blocked"
        else:
            retry = "unknown"
        constraints.append({
            "id": failure.get("id"),
            "kind": kind,
            "what": failure.get("what", ""),
            "retry": retry,
            "stop_rules": [
                {"id": rule.get("id"), "scope": rule.get("scope", ""),
                 "rule": rule.get("rule", ""),
                 "revisit_conditions": rule.get("revisit_conditions", "")}
                for rule in stop_rules
            ],
            "retry_conditions": [n.get("retry_conditions", "") for n in negative
                                 if n.get("retry_conditions")],
            "revisit_conditions": [n.get("revisit_conditions", "") for n in negative
                                   if n.get("revisit_conditions")],
        })
    constraints.sort(key=lambda item: (str(item.get("id")), str(item.get("kind"))))
    return constraints


def open_obligations(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Recover the previous round's decisions and unfinished obligations."""
    obligations: List[Dict[str, Any]] = []
    for repair in (state.get("repairs") if isinstance(state.get("repairs"), list) else []):
        if not isinstance(repair, dict):
            continue
        if repair.get("closure") == "ACCEPTED_LIMITATION":
            obligations.append({
                "kind": "accepted_limitation",
                "flaw": repair.get("flaw", ""),
                "disposition": repair.get("disposition"),
                "state_delta": repair.get("state_delta", ""),
            })
    return obligations


def render_brief(
    index: Dict[str, Any],
    state: Dict[str, Any],
    budget: int = DEFAULT_BUDGET,
) -> str:
    """Render the context-recovery brief. Speculation is always labelled."""
    view = CanonicalView(state)
    selection = recall(index, state, budget)
    lines: List[str] = []
    lines.append("# Cognitive Context Brief")
    lines.append("")
    lines.append("Generated from `research-state.json` + `cognition/model-revisions.jsonl`.")
    lines.append("This file is a rebuildable projection. It is not evidence and not a state.")
    lines.append("Every mechanism line carries its derived support level; a mechanism without")
    lines.append("canonical support appears as `speculative`, never as an established fact.")
    lines.append("")
    lines.append(f"- route: `{index.get('route', '')}`")
    lines.append(f"- state_version: {index.get('state_version')}")
    lines.append(f"- mechanisms: {index.get('counts', {}).get('mechanisms', 0)}"
                 f"（stale {index.get('counts', {}).get('stale_mechanisms', 0)}）")
    lines.append(f"- competition: {index.get('counts', {}).get('competitions', 0)}")
    lines.append("")

    lines.append("## Research contract (read-only, human-owned)")
    contract = state.get("contract") if isinstance(state.get("contract"), dict) else {}
    lines.append(f"- goal: {_clip(contract.get('goal', 'TBD'))}")
    lines.append(f"- primary_anchor: {_clip(contract.get('primary_anchor', 'TBD'))}")
    lines.append("")

    lines.append("## Hot memory — what the current question needs now")
    hot = selection["hot"]
    if not hot["mechanisms"]:
        lines.append("- (no mechanism is anchored to the current focus)")
    for entry in hot["mechanisms"]:
        lines.append(
            f"- `{entry['id']}` [{entry['support_level']}/{entry['status']}] "
            f"{_clip(entry['statement'])} ← {_refs(entry['refs'])}")
    for anomaly in hot["anomalies"]:
        lines.append(f"- anomaly `{anomaly['id']}` [{anomaly.get('importance')}] "
                     f"{_clip(anomaly.get('observation', ''))} ← {_refs(anomaly.get('canonical_refs', {}))}")
    for competition in hot["competitions"]:
        lines.append(
            f"- competition `{competition['id']}` [{competition.get('status')}] "
            f"{' vs '.join(competition.get('mechanisms', []))} | "
            f"intervention: {_clip(competition.get('discriminating_intervention', 'TBD'))}")
    lines.append("")

    lines.append("## Warm memory — related history")
    if not selection["warm"]["mechanisms"]:
        lines.append("- (none)")
    for entry in selection["warm"]["mechanisms"]:
        lines.append(f"- `{entry['id']}` [{entry['support_level']}/{entry['status']}] "
                     f"{_clip(entry['statement'])} ← {_refs(entry['refs'])}")
    lines.append("")

    lines.append("## Cold memory — index only")
    cold = selection["cold"]["mechanisms"]
    if not cold:
        lines.append("- (none)")
    for entry in cold:
        reason = "; ".join(entry.get("stale_reasons", []) or []) or entry.get("status", "")
        lines.append(f"- `{entry['id']}` [{entry['support_level']}] {_clip(reason)}")
    lines.append("")

    lines.append("## Failure memory — what must not be repeated")
    constraints = selection["failure_constraints"]
    if not constraints:
        lines.append("- (no recorded failure constrains the next round)")
    for item in constraints:
        lines.append(f"- `{item['id']}` [{item['kind']}] retry={item['retry']} "
                     f"{_clip(item.get('what', ''))}")
        for rule in item.get("stop_rules", []):
            lines.append(f"  - stop rule `{rule.get('id')}` (scope {_clip(rule.get('scope'), 40)}): "
                         f"{_clip(rule.get('rule', ''))}")
            if rule.get("revisit_conditions"):
                lines.append(f"    revisit only if: {_clip(rule['revisit_conditions'])}")
        for condition in item.get("retry_conditions", []):
            lines.append(f"  - retry only if: {_clip(condition)}")
    lines.append("")

    lines.append("## Previous decision and open obligations")
    decision = state.get("decision") if isinstance(state.get("decision"), dict) else {}
    if decision:
        lines.append(f"- verdict: {_clip(decision.get('verdict', 'TBD'))}"
                     f" | next_phase: {_clip(decision.get('next_phase', 'TBD'))}")
        lines.append(f"- rationale: {_clip(decision.get('rationale', ''))}")
    else:
        lines.append("- (no decision recorded yet)")
    for obligation in selection["open_obligations"]:
        lines.append(f"- accepted limitation [{obligation.get('disposition')}]: "
                     f"{_clip(obligation.get('flaw', ''))}")
    lines.append("")

    diagnostics = index.get("diagnostics", []) or []
    lines.append("## Provenance warnings")
    if not diagnostics:
        lines.append("- (none)")
    for diagnostic in diagnostics[:20]:
        lines.append(f"- {diagnostic.get('rule')} {diagnostic.get('path')} "
                     f"{_clip(diagnostic.get('detail', ''))}")
    if len(diagnostics) > 20:
        lines.append(f"- …还有 {len(diagnostics) - 20} 条，见 `index.json` 的 diagnostics")
    lines.append("")

    lines.append("## Next action")
    lines.append(f"- {_clip(next_action_hint(view, index))}")
    lines.append("")

    text = "\n".join(lines)
    return _enforce_budget(text, budget)


def next_action_hint(view: CanonicalView, index: Dict[str, Any]) -> str:
    undecided = [c for c in index.get("competitions", []) or []
                 if c.get("status") == "open" and not c.get("has_distinguishing_power")]
    if undecided:
        ids = ", ".join(str(c.get("id")) for c in undecided)
        return (f"开放竞争 {ids} 尚无判别干预；先设计能分开两者预测的最小干预，"
                "不要继续增加解释。")
    open_uncertainties = [u for u in view.state.get("uncertainties", []) or []
                          if isinstance(u, dict) and u.get("status") == "open"
                          and u.get("importance") in ("critical", "high")]
    if open_uncertainties:
        first = open_uncertainties[0]
        return (f"最高价值的未决问题：{_clip(first.get('question', ''))}"
                f"（判别测试 {first.get('cheapest_discriminating_test', 'TBD')}）。")
    return "无未决高价值问题；按 scheduler 的 next_action_policy 选择下一动作。"


def _refs(refs: Any) -> str:
    if not isinstance(refs, dict):
        return "—"
    parts: List[str] = []
    for key in REF_KEYS:
        values = refs.get(key)
        if isinstance(values, list) and values:
            parts.append(f"{key}:{','.join(str(v) for v in values)}")
    return " ".join(parts) if parts else "—"


def _clip(value: Any, limit: int = VALUE_LIMIT) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _enforce_budget(text: str, budget: int) -> str:
    if budget <= 0 or len(text) <= budget:
        return text
    lines = text.splitlines()
    kept: List[str] = []
    used = 0
    omitted = 0
    for line in lines:
        if used + len(line) + 1 > budget - 80:
            omitted += 1
            continue
        kept.append(line)
        used += len(line) + 1
    kept.append("")
    kept.append(f"_[context budget {budget} 已截断 {omitted} 行；完整内容见 `index.json`]_")
    return "\n".join(kept) + "\n"


# ---------------------------------------------------------------------------
# Snapshot guard: building cognition must not touch canonical state
# ---------------------------------------------------------------------------

def state_fingerprint(path: Path) -> str:
    if not path.is_file():
        raise CognitionError(f"state file not found: {path}")
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def _load_inputs(state_path: Path, cognition_dir: Path):
    state = load_state(state_path)
    revisions, parse_diagnostics = load_revisions(cognition_dir / REVISIONS_NAME)
    return state, revisions, parse_diagnostics


def op_build(state_path: Path, cognition_dir: Path) -> int:
    before = state_fingerprint(state_path)
    state, revisions, parse_diagnostics = _load_inputs(state_path, cognition_dir)
    index, index_diagnostics = full_index(state, revisions, route_of(state_path))
    diagnostics = _dedupe(list(parse_diagnostics) + list(index_diagnostics))
    index["diagnostics"] = [d.as_dict() for d in sorted(
        diagnostics, key=lambda d: (d.rule, d.path, d.detail))]
    cognition_dir.mkdir(parents=True, exist_ok=True)
    (cognition_dir / INDEX_NAME).write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    (cognition_dir / BRIEF_NAME).write_text(
        render_brief(index, state), encoding="utf-8")
    after = state_fingerprint(state_path)
    if before != after:
        print("CM0  canonical state was modified during a cognitive build; aborting",
              file=sys.stderr)
        return EXIT_HARD
    hard = [d for d in diagnostics]
    print(f"built {cognition_dir / INDEX_NAME} "
          f"(mechanisms={len(index['mechanisms'])}, diagnostics={len(hard)})")
    for diagnostic in hard:
        print("  " + diagnostic.render())
    return EXIT_OK


def op_validate(state_path: Path, cognition_dir: Path) -> int:
    state, revisions, parse_diagnostics = _load_inputs(state_path, cognition_dir)
    diagnostics = list(parse_diagnostics) + validate_revisions(state, revisions)
    index_path = cognition_dir / INDEX_NAME
    if not index_path.is_file():
        diagnostics.append(Diagnostic("CM3", INDEX_NAME, "索引不存在；先运行 build"))
    else:
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            diagnostics.append(Diagnostic("CM3", INDEX_NAME, f"索引不是合法 JSON：{exc.msg}"))
            index = None
        if isinstance(index, dict):
            diagnostics.extend(validate_index(state, revisions, index))
    diagnostics = _dedupe(diagnostics)
    for diagnostic in diagnostics:
        print(diagnostic.render())
    print(f"validate: {len(diagnostics)} 处问题（规则 CM1—CM9）")
    return EXIT_OK if not diagnostics else EXIT_HARD


def op_brief(state_path: Path, cognition_dir: Path, out: Optional[Path], budget: int) -> int:
    state, revisions, _ = _load_inputs(state_path, cognition_dir)
    index, _ = full_index(state, revisions, route_of(state_path))
    text = render_brief(index, state, budget)
    target = out or (cognition_dir / BRIEF_NAME)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(f"brief written to {target} ({len(text)} chars, budget {budget})")
    return EXIT_OK


def op_recall(state_path: Path, cognition_dir: Path, budget: int) -> int:
    state, revisions, _ = _load_inputs(state_path, cognition_dir)
    index, _ = full_index(state, revisions, route_of(state_path))
    print(json.dumps(recall(index, state, budget), ensure_ascii=False, indent=2))
    return EXIT_OK


def op_check(state_path: Path, cognition_dir: Path) -> int:
    before = state_fingerprint(state_path)
    state, revisions, parse_diagnostics = _load_inputs(state_path, cognition_dir)
    index, index_diagnostics = full_index(state, revisions, route_of(state_path))
    diagnostics = list(parse_diagnostics) + list(index_diagnostics)
    index_path = cognition_dir / INDEX_NAME
    if index_path.is_file():
        try:
            stored = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                diagnostics.extend(validate_index(state, revisions, stored))
        except json.JSONDecodeError as exc:
            diagnostics.append(Diagnostic("CM3", INDEX_NAME, f"索引不是合法 JSON：{exc.msg}"))
    else:
        diagnostics.append(Diagnostic("CM3", INDEX_NAME, "索引不存在；先运行 build"))
    brief_path = cognition_dir / BRIEF_NAME
    if index_path.is_file() and brief_path.is_file():
        expected = render_brief(index, state)
        actual = brief_path.read_text(encoding="utf-8")
        if expected != actual:
            diagnostics.append(Diagnostic(
                "CM3", BRIEF_NAME, "context brief 不是由当前 state 与 revisions 生成；先运行 build"))
    elif brief_path.exists():
        diagnostics.append(Diagnostic("CM3", BRIEF_NAME, "brief 存在但索引缺失"))
    diagnostics = _dedupe(diagnostics)
    if state_fingerprint(state_path) != before:
        diagnostics.append(Diagnostic("CM0", STATE_NAME, "认知检查过程修改了 canonical state"))
    for diagnostic in diagnostics:
        print(diagnostic.render())
    print(f"check: {len(diagnostics)} 处问题（规则 CM1—CM9）")
    return EXIT_OK if not diagnostics else EXIT_HARD


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest_state() -> Dict[str, Any]:
    version = 4
    validity = lambda reason: {"status": "valid", "reason": reason, "since_state_version": version}
    return {
        "state_version": version,
        "contract": {"goal": "判断机制 M 是否解释目标现象", "primary_anchor": "phenomenon",
                     "constraints": [], "resources": [],
                     "provisional_anchor_rationale": "先形式化", "out_of_scope": []},
        "claims": [{
            "id": "C1", "statement": "机制 M 解释目标现象", "parent": None, "subclaims": [],
            "status": "partially-supported", "supporting_evidence": ["E1"], "refuting_evidence": [],
            "nearest_alternative": "替代机制 N", "falsifier": "干预 I 后现象消失", "scope": "数据集 A",
            "known_flaws": [], "depends_on": [], "validity": validity("已按预注册写入"),
        }],
        "evidence": [{
            "id": "E1", "kind": "experiment", "supports": ["C1"], "contradicts": [],
            "strength": "strong", "scope": "数据集 A", "epistemic_status": "Observed",
            "source_ref": "X1（seed=0）", "verification_tier": "T2", "depends_on": ["X1"],
            "validity": validity("X1 已 done"),
        }],
        "assumptions": [{"id": "AS1", "statement": "测量无偏", "status": "explicit",
                         "challenged_by": [], "if_false": "现象不可归因",
                         "depends_on": [], "validity": validity("仍被接受")}],
        "hypotheses": [{
            "id": "H1", "statement": "机制 M 是主因",
            "structural_signature": {"assumption_distance": 1, "formulation_distance": 1,
                                     "representation_distance": 0, "theory_lens_distance": 1,
                                     "mechanism_distance": 2},
            "novelty_source": "迁移", "theory_lens": "逆问题", "nearest_prior": "LIT1",
            "falsifier": "干预 I 无效", "expected_information_gain": 0.4, "status": "elite",
            "niche": "mechanism-shift", "island": "P2", "generation": 0,
            "operator": "assumption_breaker", "parents": [], "depends_on": ["AS1"],
            "validity": validity("AS1 未推翻"), "scientific_scope": None,
        }],
        "experiments": [{
            "id": "X1", "parent": None, "stage": "X3", "claim_targeted": ["C1"],
            "alternative_targeted": ["ALT-1"], "code_commit": "abc123", "data_split": "A/train",
            "seed": 0, "metric": "效应量", "result": "效应量 0.8", "interpretation": "初步",
            "unexpected": [], "known_flaws": [], "next_branches": [], "status": "done",
            "preregistration": {"frozen_at_state_version": 3, "outcomes": [
                {"id": "O1", "observation": "效应量 ≥ 0.5",
                 "update": [{"target": "C1", "op": "strengthen"}]}]},
            "result_at_state_version": 4, "depends_on": [], "validity": validity("按预注册写入"),
            "outcome_analysis": None, "execution_protocol": None,
        }],
        "literature": [{"id": "LIT1", "ref": "[Author, Venue/Year]", "relation": "shares-structure",
                        "depends_on": [], "validity": validity("未受波及")}],
        "failures": [], "uncertainties": [{
            "id": "U1", "question": "机制 M 是否在数据集 B 上成立？", "importance": "high",
            "uncertainty": "high", "cheapest_discriminating_test": "TBD", "status": "open",
            "depends_on": [], "validity": validity("未受波及"),
        }],
        "assurance": [], "repairs": [],
    }


def _selftest_revisions() -> List[Dict[str, Any]]:
    def record(ident, seq, kind, subject, refs, after, actor="R3", version=4):
        return {"_schema": SCHEMA_REVISION, "id": ident, "seq": seq, "kind": kind,
                "subject": subject, "actor": actor, "at_state_version": version,
                "summary": f"{kind} for {subject}",
                "trigger": {"kind": "experiment_result", "ref": "X1"},
                "refs": refs, "after": after}
    return [
        record("REV1", 1, "mechanism_create", "M1",
               {"hypotheses": ["H1"], "assumptions": ["AS1"]},
               {"statement": "解耦带来增益", "core_variables": ["耦合强度"],
                "necessary_conditions": ["测量无偏"], "pending_predictions": ["PR1"]}),
        record("REV2", 2, "mechanism_create", "M2",
               {"claims": ["C1"], "evidence": ["E1"]},
               {"statement": "耦合强度决定落差", "pending_predictions": ["PR2"]}),
        record("REV3", 3, "competition_open", "CP1",
               {"claims": ["C1"], "evidence": ["E1"]},
               {"mechanisms": ["M1", "M2"], "shared_explanation": "两者都能解释数据集 A 的落差",
                "conflicting_predictions": ["PR1 在数据集 B 预测增益", "PR2 在数据集 B 预测无增益"],
                "discriminating_intervention": "X2"}, actor="R6"),
        record("REV4", 4, "anomaly_record", "AN1",
               {"experiments": ["X1"], "evidence": ["E1"]},
               {"observation": "数据集 B 上落差反转", "importance": "high",
                "reproduced": False, "open_question": "反转是否来自实现错误？"}),
    ]


def selftest() -> int:
    failures = 0

    def check(name: str, condition: bool) -> None:
        nonlocal failures
        if not condition:
            failures += 1
            print(f"[FAIL] {name}")

    state = _selftest_state()
    revisions = _selftest_revisions()
    index, diagnostics = build_index(state, revisions, "A")
    check("clean fixture builds without diagnostics",
          [d for d in diagnostics if d.rule != "CM8"] == [])
    check("two mechanisms survive competition", len(index["mechanisms"]) == 2)
    check("competition recorded", len(index["competitions"]) == 1)
    check("M2 is experiment-supported",
          next(m for m in index["mechanisms"] if m["id"] == "M2")["support_level"]
          == "experiment_supported")
    check("M1 stays at hypothesis level: a proposed explanation is not evidence",
          next(m for m in index["mechanisms"] if m["id"] == "M1")["support_level"] == "hypothesis")
    check("build is deterministic", canonical_json(build_index(state, revisions, "A")[0])
          == canonical_json(index))
    check("revision validation clean", validate_revisions(state, revisions) == [])

    # self-certification must be rejected, not honoured
    forged = list(revisions) + [{
        "_schema": SCHEMA_REVISION, "id": "REV5", "seq": 5, "kind": "mechanism_revise",
        "subject": "M1", "actor": "R3", "at_state_version": 4, "summary": "claim support",
        "trigger": {"kind": "experiment_result", "ref": "X1"},
        "refs": {"hypotheses": ["H1"]}, "after": {"epistemic_status": "experiment_supported"},
    }]
    forged_diagnostics = validate_revisions(state, forged)
    check("declared epistemic_status is a hard violation",
          any(d.rule == "CM2" for d in forged_diagnostics))

    # declared_support is recorded as a conflict and never adopted
    conflict = list(revisions) + [{
        "_schema": SCHEMA_REVISION, "id": "REV6", "seq": 5, "kind": "mechanism_revise",
        "subject": "M1", "actor": "R3", "at_state_version": 4, "summary": "self rating",
        "trigger": {"kind": "experiment_result", "ref": "X1"},
        "refs": {"hypotheses": ["H1"]}, "after": {"declared_support": "experiment_supported"},
    }]
    conflict_index, _ = build_index(state, conflict, "A")
    m1 = next(m for m in conflict_index["mechanisms"] if m["id"] == "M1")
    check("self-declared support is not adopted", m1["support_level"] == "hypothesis")
    check("self-declared support raises a conflict diagnostic",
          any(d["rule"] == "CM7" for d in conflict_index["diagnostics"]))

    # an invalidated evidence source marks derived memory stale
    stale_state = json.loads(json.dumps(state))
    stale_state["evidence"][0]["validity"]["status"] = "invalid"
    stale_state["evidence"][0]["validity"]["reason"] = "源实验作废"
    stale_index, stale_diagnostics = build_index(stale_state, revisions, "A")
    m2 = next(m for m in stale_index["mechanisms"] if m["id"] == "M2")
    check("invalidated evidence makes derived memory stale", m2["stale"] is True)
    check("invalidated evidence is reported", any(d.rule == "CM3" for d in stale_diagnostics))

    # missing reference detection
    broken = list(revisions) + [{
        "_schema": SCHEMA_REVISION, "id": "REV7", "seq": 5, "kind": "mechanism_create",
        "subject": "M3", "actor": "R3", "at_state_version": 4, "summary": "dangling",
        "trigger": {"kind": "experiment_result", "ref": "X9"}, "refs": {"claims": ["C404"]},
        "after": {"statement": "无来源的机制"},
    }]
    check("dangling reference is detected",
          any(d.rule == "CM3" and "C404" in d.detail for d in validate_revisions(state, broken)))

    # index drift detection
    drifted = json.loads(json.dumps(index))
    drifted["mechanisms"][0]["support_level"] = "experiment_supported"
    check("index drift is detected", any(d.rule == "CM3" for d in validate_index(state, revisions, drifted)))

    # context recovery
    brief = render_brief(index, state)
    check("brief labels support levels",
          "hypothesis" in brief and "experiment_supported" in brief)
    check("brief states it is not evidence", "not evidence and not a state" in brief)
    selection = recall(index, state)
    check("stale mechanisms never enter hot memory",
          all(not m["stale"] for m in selection["hot"]["mechanisms"]))
    bounded = render_brief(index, state, budget=400)
    check("brief honours the context budget", len(bounded) <= 600)

    # state immutability
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        state_path = root / STATE_NAME
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        cognition_dir = root / COGNITION_DIRNAME
        cognition_dir.mkdir()
        (cognition_dir / REVISIONS_NAME).write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in revisions) + "\n",
            encoding="utf-8")
        before = state_fingerprint(state_path)
        check("build exits 0", op_build(state_path, cognition_dir) == EXIT_OK)
        check("build never modifies canonical state", state_fingerprint(state_path) == before)
        check("validate exits 0 after build", op_validate(state_path, cognition_dir) == EXIT_OK)
        check("check exits 0 after build", op_check(state_path, cognition_dir) == EXIT_OK)
        state_path.write_text(json.dumps(_selftest_state() | {"state_version": 5},
                                         ensure_ascii=False), encoding="utf-8")
        check("stale index is detected after a state change",
              op_check(state_path, cognition_dir) == EXIT_HARD)

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
    parser = _Parser(description="Cognitive Insight Engine — persistent cognitive memory")
    parser.add_argument("command", nargs="?",
                        choices=["build", "validate", "brief", "check", "recall"])
    parser.add_argument("--state", help="path to research-state.json")
    parser.add_argument("--cognition", help="path to the cognition directory")
    parser.add_argument("--out", help="output path for the brief")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                        help="context brief character budget")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--list-kinds", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.selftest:
        return selftest()
    if args.list_kinds:
        for kind in REVISION_KINDS:
            print(kind)
        return EXIT_OK
    if not args.command:
        build_parser().print_usage(sys.stderr)
        print("argument error: a command is required", file=sys.stderr)
        return EXIT_ERROR
    if not args.state:
        print("argument error: --state is required", file=sys.stderr)
        return EXIT_ERROR
    state_path = Path(args.state).expanduser()
    cognition_dir = cognition_dir_for(
        state_path, Path(args.cognition).expanduser() if args.cognition else None)
    try:
        if args.command == "build":
            return op_build(state_path, cognition_dir)
        if args.command == "validate":
            return op_validate(state_path, cognition_dir)
        if args.command == "brief":
            return op_brief(state_path, cognition_dir,
                            Path(args.out).expanduser() if args.out else None, args.budget)
        if args.command == "check":
            return op_check(state_path, cognition_dir)
        if args.command == "recall":
            return op_recall(state_path, cognition_dir, args.budget)
    except CognitionError as exc:
        print(f"environment error: {exc}", file=sys.stderr)
        return EXIT_ENV
    print(f"argument error: unknown command {args.command!r}", file=sys.stderr)
    return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
