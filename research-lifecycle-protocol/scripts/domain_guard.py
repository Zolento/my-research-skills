#!/usr/bin/env python3
"""domain_guard.py — Trivial Attribution Guard (TAG) for domain profiles.

Problem: in self-supervised MRI reconstruction research, agents keep falling back to
the same cheap attributions — "the forward operator", "the noise", "the conditioning",
"the undersampling" — without new evidence and without any research decision changing.
The method search stalls while diagnosis repeats itself.

TAG is a *guard*, not a gate:

* it classifies an attribution declaration into one of six classes;
* it flags the equivalent-repeat case so the research loop stops re-dispatching the
  same diagnosis and moves to a legal method transition instead;
* it never overrides a verified physical defect (``VALIDITY_BLOCKER`` always wins);
* it never bypasses PEIG/AALG, never starts GPU work, never refreshes a diagnostic
  budget and never writes canonical state.

Equivalence is structural — the same controlled mechanism token, the same assumption
set and the same scope — never free-text similarity. An equivalence the module cannot
prove mechanically becomes ``review_required`` judgement, never an automatic block.

Event log: ``<route>/domain/tag-events.jsonl`` (append-only hash chain). It is a route
control-plane file: deleting it must not affect canonical state validation.

CLI::

    python3 scripts/domain_guard.py classify --state <route>/research-state.json \
        --declaration declaration.json [--record]
    python3 scripts/domain_guard.py events  --route <route-dir>
    python3 scripts/domain_guard.py check   --route <route-dir>

Exit codes: 0 ok, 1 usage/selftest failure, 3 damaged chain, 4 environment.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import pathlib
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cognition as cg

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_HARD = 3
EXIT_ENV = 4

#: Frozen protocol namespace (references/identity-and-compatibility.md).
EVENTS_SCHEMA = "research-idea-pipeline/tag-events@1"
EVENTS_DIRNAME = "domain"
EVENTS_NAME = "tag-events.jsonl"

TAG_CLASSES: Tuple[str, ...] = (
    "VALIDITY_BLOCKER",
    "NOVEL_DECISION_RELEVANT_DIAGNOSIS",
    "REPEATED_ATTRIBUTION",
    "PHYSICAL_LIMIT_WITH_SCOPE",
    "METHOD_TRANSITION_READY",
    "INSUFFICIENT_EVIDENCE",
)

#: Controlled mechanism tokens. Equivalence is matched on these tokens plus structured
#: assumptions/scope — never on prose.
MECHANISMS: Tuple[str, ...] = (
    "forward_operator_mismatch", "coil_sensitivity_error", "noise_level", "snr_limit",
    "undersampling_information", "conditioning", "ill_posedness", "oversmoothing",
    "overstrong_prior", "data_scarcity", "other_declared",
)

#: The classic fallback attributions this guard exists for. `other_declared` is a new
#: mechanism awaiting R7/R10 confirmation and is not trivial by default.
TRIVIAL_MECHANISMS = frozenset(MECHANISMS) - {"other_declared"}


@dataclass
class Declaration:
    mechanism: str
    scope: str
    assumptions: List[str] = field(default_factory=list)
    predictions: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    decision_consequence: str = ""
    validity_findings: List[str] = field(default_factory=list)
    validity_evidence_refs: List[str] = field(default_factory=list)
    physical_limit: Optional[Dict[str, Any]] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def trivial_mechanism(self) -> bool:
        return self.mechanism in TRIVIAL_MECHANISMS


#: What a ``physical_limit`` claim may be *backed by*, weakest to strongest. The class
#: a limitation earns is bounded by this type — an agent saying "verified": true does
#: not choose the bound; the resolved canonical evidence does (TG3).
LIMIT_TYPES: Tuple[str, ...] = (
    "mathematical_impossibility",   # proven: no estimator can recover the target
    "detection_power_limit",        # a specific statistical test lacks power
    "empirical_upper_bound",        # measured ceiling in one experimental configuration
    "physical_interpretation",      # an unverified physical explanation
)


def parse_declaration(value: Any) -> Tuple[Optional[Declaration], List[str]]:
    """Read a structured declaration. Returns (declaration | None, problems)."""
    problems: List[str] = []
    if not isinstance(value, dict):
        return None, ["declaration 顶层必须是对象"]
    mechanism = str(value.get("mechanism") or "").strip()
    scope = str(value.get("scope") or "").strip()
    assumptions = [str(item).strip() for item in
                   (value.get("assumptions") or []) if str(item).strip()]
    refs = [str(item).strip() for item in
            (value.get("evidence_refs") or []) if str(item).strip()]
    if not mechanism:
        problems.append("缺少 mechanism（受控枚举之一；新机制先登记 other_declared）")
    if not scope:
        problems.append("缺少 scope（归因必须声明适用范围）")
    if not refs:
        problems.append("缺少 evidence_refs（没有证据引用的归因按 INSUFFICIENT_EVIDENCE 处理）")
    if problems:
        return None, problems
    limit = value.get("physical_limit")
    if limit is not None and not isinstance(limit, dict):
        problems.append("physical_limit 必须是对象")
        limit = None
    declaration = Declaration(
        mechanism=mechanism, scope=scope.lower(), assumptions=sorted(assumptions),
        predictions=[str(item) for item in (value.get("predictions") or [])],
        evidence_refs=refs,
        decision_consequence=str(value.get("decision_consequence") or "").strip(),
        validity_findings=[str(item) for item in (value.get("validity_findings") or [])],
        validity_evidence_refs=[str(item).strip() for item in
                                (value.get("validity_evidence_refs") or [])
                                if str(item).strip()],
        physical_limit=limit, raw=value)
    return declaration, problems


def fingerprint(declaration: Declaration) -> str:
    """Structural fingerprint: mechanism + assumptions + scope.

    Predictions and evidence refs are deliberately excluded: they are the *new
    information* a repeated attribution fails to bring.
    """
    return cg.digest_of({"mechanism": declaration.mechanism,
                         "assumptions": declaration.assumptions,
                         "scope": declaration.scope})


# ---------------------------------------------------------------------------
# Event store: append-only hash chain under <route>/domain/
# ---------------------------------------------------------------------------

def events_path(route_dir: Any) -> pathlib.Path:
    return pathlib.Path(route_dir).expanduser() / EVENTS_DIRNAME / EVENTS_NAME


def load_events(route_dir: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Read the chain. Returns (records, problems). A damaged chain is a real error."""
    path = events_path(route_dir)
    if not path.is_file():
        return [], []
    records: List[Dict[str, Any]] = []
    problems: List[str] = []
    prev = ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [], [f"事件链不可读：{exc}"]
    for index, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"第 {index} 行不是合法 JSON：{exc}")
            continue
        if record.get("prev_hash") != prev:
            problems.append(f"第 {index} 行哈希链断裂（prev_hash 不匹配）")
        expected = cg.digest_of({k: v for k, v in record.items() if k != "hash"})
        if record.get("hash") != expected:
            problems.append(f"第 {index} 行 hash 与内容不符")
        prev = record.get("hash", prev)
        records.append(record)
    return records, problems


def lock_path(route_dir: Any) -> pathlib.Path:
    """A dedicated, stable lock file next to the event log.

    Locking the log file itself would break whenever the log is rotated or recovered
    (the lock would guard the wrong inode), so the lock lives in its own file.
    """
    return pathlib.Path(route_dir).expanduser() / EVENTS_DIRNAME / (EVENTS_NAME + ".lock")


def event_id_from(payload: Dict[str, Any]) -> str:
    """A stable idempotency id for one logical enforcement.

    Binds the identity fields the caller supplies (route / state / action /
    fingerprint / verdict / kind). The same logical operation retried after a lost
    response maps to the same id and must not append twice; genuinely new evidence or
    a new decision changes at least one field and gets a new id.
    """
    identity = {k: payload.get(k) for k in
                ("route", "state_version", "state_digest", "action", "fingerprint",
                 "tag_class", "event_kind") if payload.get(k) is not None}
    return cg.digest_of(identity)


def _append_locked(route_dir: pathlib.Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    """The append transaction. Caller must hold the lock."""
    path = events_path(route_dir)
    records, problems = load_events(route_dir)
    if problems:
        raise ChainDamaged("; ".join(problems[:3]))
    seq = (records[-1]["seq"] + 1) if records else 1
    prev = records[-1]["hash"] if records else ""
    record = {"_schema": EVENTS_SCHEMA, "seq": seq, "prev_hash": prev, **payload}
    record["hash"] = cg.digest_of({k: v for k, v in record.items()})
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    handle = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(handle, (line + "\n").encode("utf-8"))
        os.fsync(handle)
    finally:
        os.close(handle)
    return record


def append_event_once(route_dir: Any, payload: Dict[str, Any],
                      idempotency_key: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """Idempotent append. Returns (record, status) with status APPENDED or DUPLICATE."""
    route = pathlib.Path(route_dir).expanduser()
    path = events_path(route)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body["event_id"] = event_id_from(idempotency_key)
    lock_handle = os.open(str(lock_path(route)), os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        records, problems = load_events(route)
        if problems:
            raise ChainDamaged("; ".join(problems[:3]))
        for existing in records:
            if existing.get("event_id") == body["event_id"]:
                return existing, "DUPLICATE"
        return _append_locked(route, body), "APPENDED"
    finally:
        fcntl.flock(lock_handle, fcntl.LOCK_UN)
        os.close(lock_handle)


def append_event(route_dir: Any, payload: Dict[str, Any],
                 idempotency_key: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Append one event, extending the hash chain.

    The whole transaction — read, validate, sequence, construct, append, fsync — runs
    inside one exclusive critical section on the dedicated lock file, so concurrent
    writers can never fork the chain. With ``idempotency_key`` the event id is derived
    from the given identity fields; when an event with that id already exists the
    existing record is returned unchanged and nothing is appended.

    Raises ChainDamaged on a corrupt log. Recovery is explicit
    (``main recover --route ... --archive``), never automatic.
    """
    route = pathlib.Path(route_dir).expanduser()
    path = events_path(route)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    if idempotency_key:
        body["event_id"] = event_id_from(idempotency_key)
    lock = lock_path(route)
    lock_handle = os.open(str(lock), os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        if "event_id" in body:
            records, problems = load_events(route)
            if problems:
                raise ChainDamaged("; ".join(problems[:3]))
            for existing in records:
                if existing.get("event_id") == body["event_id"]:
                    return existing
        return _append_locked(route, body)
    finally:
        fcntl.flock(lock_handle, fcntl.LOCK_UN)
        os.close(lock_handle)


def recover_log(route_dir: Any) -> Dict[str, Any]:
    """Archive a damaged log and start a fresh chain. Explicit, auditable, never silent."""
    route = pathlib.Path(route_dir).expanduser()
    path = events_path(route)
    _records, problems = load_events(route)
    if not problems:
        return {"status": "OK", "archived": None, "problems": []}
    stamp = pathlib.Path(time.strftime("%Y%m%dT%H%M%S")).name if False else None
    import time as _time
    archive = path.with_name(path.name + f".corrupt-{_time.strftime('%Y%m%dT%H%M%S')}")
    if path.is_file():
        os.replace(path, archive)
    lock = lock_path(route)
    if lock.exists():
        lock.unlink()
    return {"status": "ARCHIVED", "archived": str(archive), "problems": problems[:5]}


class ChainDamaged(RuntimeError):
    """The event chain failed validation; refuse to append to a tampered log."""


def history_for(records: Sequence[Dict[str, Any]], fp: str) -> Dict[str, Any]:
    """Aggregated history for one fingerprint: seen refs, content digests, counts."""
    refs: set = set()
    digests: set = set()
    predictions: set = set()
    repeat_count = 0
    latest: Optional[Dict[str, Any]] = None
    for record in records:
        if record.get("fingerprint") != fp:
            continue
        refs.update(record.get("evidence_refs") or [])
        digests.update(record.get("evidence_digests") or [])
        predictions.update(record.get("predictions") or [])
        if record.get("tag_class") == "REPEATED_ATTRIBUTION":
            repeat_count += 1
        latest = record
    return {"evidence_refs": refs, "evidence_digests": digests,
            "predictions": predictions, "repeat_count": repeat_count, "latest": latest}


# ---------------------------------------------------------------------------
# Evidence resolution against the canonical Research State (TG2/TG3/TG5)
# ---------------------------------------------------------------------------
# TAG never keeps its own evidence database. Every claim about "verified",
# "invalid", "revoked" is resolved against the canonical state the caller passes in,
# so an attribution inherits exactly the epistemics the Research State already has.

#: object-id prefixes → canonical collections (first match wins).
REF_COLLECTIONS: Tuple[Tuple[str, str], ...] = (
    ("E", "evidence"), ("X", "experiments"), ("C", "claims"), ("H", "hypotheses"),
    ("F", "failures"), ("U", "uncertainties"), ("LIT", "literature"),
)

#: failure kinds that count as *recorded* engineering validity defects.
VALIDITY_FAILURE_KINDS = ("engineering-failure", "failed-to-reproduce")


def _items(state: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    value = state.get(key) if isinstance(state, dict) else None
    return [item for item in (value or []) if isinstance(item, dict)]


def resolve_ref(state: Optional[Dict[str, Any]], ref: str) -> Optional[Dict[str, Any]]:
    """Resolve one object id (``E7``, ``X11``, ``F3``, ...) in the canonical state."""
    if not isinstance(state, dict) or not ref:
        return None
    prefix = next((p for p, _ in REF_COLLECTIONS if ref.startswith(p)), None)
    if prefix is None:
        return None
    collection = next(c for p, c in REF_COLLECTIONS if p == prefix)
    for item in _items(state, collection):
        if str(item.get("id")) == ref:
            return item
    return None


def _dependency_invalid(state: Dict[str, Any], item: Dict[str, Any],
                        seen: Optional[set] = None) -> bool:
    """One-hop dependency validity (V19 semantics, read-only re-derivation)."""
    seen = seen if seen is not None else set()
    refs = list(item.get("depends_on") or [])
    if str(item.get("id", "")).startswith("C"):
        refs += list(item.get("supporting_evidence") or [])
        refs += list(item.get("refuting_evidence") or [])
    for ref in refs:
        if ref in seen:
            continue
        seen.add(ref)
        other = resolve_ref(state, str(ref))
        if other is None:
            continue
        status = str((other.get("validity") or {}).get("status") or "")
        if status == "invalid":
            return True
    return False


def evidence_usable(state: Optional[Dict[str, Any]],
                    ref: str) -> Tuple[bool, str]:
    """Is ``ref`` currently usable as scientific support?

    Returns (usable, reason). Revoked (``validity.status`` invalid/stale), dependent-
    invalidated and unresolvable refs are not usable — a TAG verdict may cite them as
    history, never as current support.
    """
    item = resolve_ref(state, ref)
    if item is None:
        return False, f"{ref} 不存在于 canonical state"
    status = str((item.get("validity") or {}).get("status") or "")
    if status in ("invalid", "stale"):
        return False, f"{ref} validity={status}（已失效/撤销）"
    if state is not None and _dependency_invalid(state, item):
        return False, f"{ref} 依赖已失效对象（一跳传播）"
    return True, ""


def evidence_content_digest(state: Optional[Dict[str, Any]], ref: str) -> Optional[str]:
    """A structural digest of *what the evidence is* — not its id.

    Two refs with the same digest carry the same evidential content; re-labelling an
    old measurement with a fresh id must not manufacture novelty (TG5).
    """
    item = resolve_ref(state, ref)
    if item is None:
        return None
    semantic = {k: item.get(k) for k in
                ("kind", "scope", "strength", "epistemic_status", "verification_tier",
                 "source_ref", "statement", "finding", "contradicts", "supports")
                if item.get(k) is not None}
    prereg = item.get("preregistration") if isinstance(item.get("preregistration"), dict) else {}
    if prereg.get("outcomes"):
        semantic["outcomes"] = prereg["outcomes"]
    return cg.digest_of(semantic)


def validity_refs_confirmed(state: Optional[Dict[str, Any]],
                            refs: Sequence[str]) -> Tuple[List[str], List[str]]:
    """Which validity-finding refs are *recorded* defects in the canonical state?

    A ref counts as confirmed when it resolves to a failed experiment, a recorded
    engineering failure, or observed evidence. Prose findings without any resolvable
    source stay unconfirmed. Returns (confirmed_ids, rejection_reasons).
    """
    if state is None:
        return [], ["无 canonical state，无法核证有效性发现"]
    if not refs:
        return [], ["validity_findings 未引用任何可解析来源"]
    confirmed, missing = [], []
    for ref in refs:
        item = resolve_ref(state, ref)
        if item is None:
            missing.append(f"{ref} 不存在")
            continue
        kind = str(item.get("kind") or "")
        status = str(item.get("status") or "")
        if status == "failed" or kind in VALIDITY_FAILURE_KINDS:
            confirmed.append(ref)
            continue
        if str(item.get("id", "")).startswith("E") and \
                str(item.get("epistemic_status") or "") in ("Observed", "Verified"):
            confirmed.append(ref)
            continue
        missing.append(f"{ref} 既非 failed 实验，也非已记录工程失败或已观测证据")
    return confirmed, missing


def physical_limit_verdict(state: Optional[Dict[str, Any]],
                           limit: Dict[str, Any]) -> Tuple[str, str, bool]:
    """Map a physical-limit claim to (tag_class, reason, review_required).

    The agent's ``verified`` flag is a *proposal*. The bound the limitation earns
    depends on ``limit_type`` and on evidence that actually resolves in the canonical
    state right now; a detection-power result must never masquerade as a global
    impossibility, and an unverified interpretation never self-upgrades.
    """
    limit_type = str(limit.get("limit_type") or "").strip()
    if limit_type not in LIMIT_TYPES:
        return ("INSUFFICIENT_EVIDENCE",
                "物理限制缺少 limit_type（" + " / ".join(LIMIT_TYPES) + "）："
                "结论强度无法确定，登记待审", True)
    source_refs = [str(r).strip() for r in (limit.get("source_refs") or [])
                   if str(r).strip()]
    if state is None:
        return ("INSUFFICIENT_EVIDENCE",
                "无 canonical state：物理限制声明无法核证，不得自我升级为 verified", True)
    if not source_refs:
        return ("INSUFFICIENT_EVIDENCE",
                "物理限制未引用任何来源（source_refs 为空）：仅凭声明不构成验证", True)
    usable, reasons = [], []
    for ref in source_refs:
        ok, why = evidence_usable(state, ref)
        (usable if ok else reasons).append(ref if ok else why)
    if not usable:
        return ("INSUFFICIENT_EVIDENCE",
                "物理限制来源当前不可用：" + "；".join(reasons[:3]) +
                "；已撤销/失效的证据不得继续支撑限制结论", True)
    scope = str(limit.get("scope") or "").strip()
    if not scope:
        return ("INSUFFICIENT_EVIDENCE",
                "物理限制缺少适用范围：无法机械确认", True)
    if limit_type == "mathematical_impossibility":
        reason = (f"已证明的数学不可能性（来源 {usable}），适用范围：{scope}")
        return "PHYSICAL_LIMIT_WITH_SCOPE", reason, False
    if limit_type == "detection_power_limit":
        return ("PHYSICAL_LIMIT_WITH_SCOPE",
                f"检测功效限制（来源 {usable}），适用范围：{scope}"
                "；这是特定统计检验下的条件性结论，不得表述为全局不可恢复", False)
    if limit_type == "empirical_upper_bound":
        return ("PHYSICAL_LIMIT_WITH_SCOPE",
                f"经验上限（来源 {usable}），适用范围：{scope}"
                "；仅限该实验配置，不得推广到所有先验/数据分布/任务", False)
    # physical_interpretation — an explanation is not a verified limitation; only the
    # existing Evidence Qualification / Assurance can promote it.
    return ("INSUFFICIENT_EVIDENCE",
            "物理解释未经现有证据体系核证（来源存在但类型为解释）："
            "不得自我升级为已验证限制；登记待审", True)


# ---------------------------------------------------------------------------
# Classification (TG1–TG7)
# ---------------------------------------------------------------------------

def classify(declaration: Declaration, records: Sequence[Dict[str, Any]],
             state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Classify one attribution declaration. Pure: reads history and state, writes nothing.

    ``state`` is the current canonical Research State. Without it the guard can still
    detect structural repetition, but it can never confirm a physical limitation or a
    validity defect — those degrade to INSUFFICIENT_EVIDENCE + review instead of
    trusting the agent's own "verified" label (TG2/TG3).
    """
    fp = fingerprint(declaration)
    history = history_for(records, fp)
    seen_refs = history["evidence_refs"]
    review_required = False
    notes: List[str] = []
    safety = None

    if declaration.mechanism not in MECHANISMS:
        # Not keyword fuzzing: an unknown token is structurally a new declaration that
        # still has to carry evidence; equivalence for it cannot be proven mechanically.
        review_required = True
        notes.append("机制不在受控枚举内：等价性无法机械证明，登记待审")

    # TG5 evidence accounting happens once, before the class decision: a cited ref is
    # *novel support* only when it (a) has not been cited for this fingerprint before,
    # (b) does not duplicate already-seen evidential content under a fresh id, and
    # (c) is currently usable in the canonical state (not revoked/invalidated).
    fresh: List[str] = []
    duplicate_content: List[str] = []
    unusable: List[str] = []
    new_digests: List[str] = []
    for ref in declaration.evidence_refs:
        if ref in seen_refs:
            continue
        digest_ = evidence_content_digest(state, ref) if state is not None else None
        if digest_ is not None and digest_ in history["evidence_digests"]:
            duplicate_content.append(ref)
            continue
        ok, _why = (evidence_usable(state, ref) if state is not None else (True, ""))
        if not ok:
            unusable.append(ref)
            continue
        fresh.append(ref)
        if digest_ is not None:
            new_digests.append(digest_)
    new_refs = fresh
    if duplicate_content:
        notes.append("仅更换证据 ID、内容与既有证据等价（" +
                     ", ".join(duplicate_content) + "）：不构成科研增量")
    if unusable:
        notes.append("引用的证据当前不可用（" + ", ".join(unusable) +
                     "）：已撤销/失效证据不支撑新结论")

    if declaration.validity_findings:
        # TG2 — a *confirmed* validity defect wins over everything, including
        # repetition. Findings backed by prose alone stay unconfirmed: they earn a
        # bounded safety review, never a permanent "verified defect" registration.
        confirmed, missing = validity_refs_confirmed(
            state, declaration.validity_evidence_refs)
        if confirmed:
            tag_class = "VALIDITY_BLOCKER"
            reason = ("存在已记录的有效性缺陷（来源 " + ", ".join(confirmed) +
                      "）：必须优先修复；未修复前不得在同一缺陷上堆叠方法实验")
        else:
            review_required = True
            safety = "hold_pending_verification"
            tag_class = "INSUFFICIENT_EVIDENCE"
            reason = ("有效性发现未经证据核证（" + "；".join(missing[:2]) +
                      "）：按安全审查处理（有限 HOLD/升级审查），"
                      "不得登记为已验证故障，也不得据此声称机制被否证")
    elif isinstance(declaration.physical_limit, dict):
        # TG3 — the limitation class is bounded by evidence resolution, not by the
        # agent's own "verified" label.
        tag_class, reason, review_required = physical_limit_verdict(
            state, declaration.physical_limit)
    elif not new_refs and history["latest"] is not None:
        # TG4 — same structural fingerprint, no usable evidence history has not seen.
        tag_class = "REPEATED_ATTRIBUTION"
        reason = (f"等价归因（指纹 {fp[:16]}…）此前已记录 {history['repeat_count']} 次；"
                  f"本次证据引用 {declaration.evidence_refs} 均在历史集合内，无新增信息")
    elif new_refs:
        # TG5 — genuinely new, currently-usable evidence for this fingerprint.
        predictions_changed = (not history["predictions"] or
                               set(declaration.predictions) != history["predictions"])
        tag_class = "NOVEL_DECISION_RELEVANT_DIAGNOSIS"
        reason = f"存在该机制历史上未见过且当前可用的证据引用：{new_refs}"
        if not predictions_changed:
            notes.append("预测与历史相同：新证据需说明判别预测的差别，"
                         "否则不足以改变机制竞争的可信度")
        if not declaration.decision_consequence:
            notes.append("未声明 decision_consequence：诊断必须说明不同结果会改变哪个研究决定"
                         "（与 I2M83 一致）")
    else:
        tag_class = "INSUFFICIENT_EVIDENCE"
        reason = "没有可判定的证据：不得写成结论"

    if declaration.trivial_mechanism and tag_class == "REPEATED_ATTRIBUTION":
        notes.append("平凡机制重复归因：不得继续生成同类诊断任务；转方法转化或重规划")
    if tag_class == "PHYSICAL_LIMIT_WITH_SCOPE":
        notes.append("范围内不得虚构可行改进；范围外不得以该限制阻止方法探索")

    return {"tag_class": tag_class, "reason": reason, "fingerprint": fp,
            "new_evidence_refs": new_refs, "repeat_count": history["repeat_count"],
            "review_required": review_required, "notes": notes, "safety": safety,
            "decision_consequence": declaration.decision_consequence,
            "mechanism": declaration.mechanism, "scope": declaration.scope}


def event_from_classification(declaration: Declaration, verdict: Dict[str, Any],
                              source: str, *, state: Optional[Dict[str, Any]] = None
                              ) -> Dict[str, Any]:
    limit = declaration.physical_limit if isinstance(declaration.physical_limit, dict) else None
    event = {"fingerprint": verdict["fingerprint"], "mechanism": declaration.mechanism,
             "scope": declaration.scope, "assumptions": declaration.assumptions,
             "evidence_refs": declaration.evidence_refs,
             "evidence_digests": [d for d in
                                  (evidence_content_digest(state, r)
                                   for r in declaration.evidence_refs)
                                  if d],
             "predictions": list(declaration.predictions),
             "decision_consequence": verdict["decision_consequence"],
             "tag_class": verdict["tag_class"],
             "review_required": verdict["review_required"],
             "source": source}
    if limit is not None:
        event["physical_limit"] = {"limit_type": limit.get("limit_type"),
                                   "scope": limit.get("scope")}
    if state is not None:
        event["state_version"] = state.get("state_version")
        event["state_digest"] = cg.digest_of(state)
    return event


# ---------------------------------------------------------------------------
# Loop integration (TG6/TG8): the research loop consumes this
# ---------------------------------------------------------------------------

def action_fingerprint(action: Any) -> Optional[str]:
    """The declared fingerprint of a queued diagnosis action, if the agent declared one.

    Fail open: an action without a declared attribution is invisible to TAG. The guard
    must never block what it cannot see — an undeclared action keeps normal priority.
    """
    if not isinstance(action, dict):
        return None
    mechanism = str(action.get("attribution_mechanism") or "").strip()
    if not mechanism:
        return None
    assumptions = sorted(str(item).strip() for item in
                         (action.get("attribution_assumptions") or [])
                         if str(item).strip())
    scope = str(action.get("attribution_scope") or "").strip().lower()
    if not scope:
        return None
    return cg.digest_of({"mechanism": mechanism, "assumptions": assumptions,
                         "scope": scope})


def loop_guard(state: Dict[str, Any], action: Any, route_dir: Any) -> Optional[Dict[str, Any]]:
    """Called by `preset_router._loop_step` for the scheduler's first queued action.

    Returns None when TAG has nothing to say (no declaration, no recorded repeat, or a
    validity blocker that must run). Returns a directive dict when the action is a
    recorded equivalent repeat: the loop then stops dispatching it and moves to the
    existing method-transition path.
    """
    if not isinstance(state, dict) or not route_dir:
        return None
    fp = action_fingerprint(action)
    if not fp:
        return None
    records, problems = load_events(route_dir)
    if problems:
        # A damaged chain must not silently disable the guard, and must not invent a
        # verdict either: hold with a diagnosable reason instead.
        return {"tag_class": "HOLD", "reason": "TAG 事件链损坏：" + "; ".join(problems[:2]),
                "fingerprint": fp, "review_required": True, "notes": [], "hold": True,
                "hold_reason": "tag_chain_damaged"}
    history = history_for(records, fp)
    latest = history.get("latest") or {}
    if latest.get("tag_class") != "REPEATED_ATTRIBUTION":
        return None
    ident = str(action.get("action") or action.get("target") or "")
    return {"tag_class": "REPEATED_ATTRIBUTION",
            "reason": (f"动作 {ident} 对应的归因已被判定为重复（{history['repeat_count']} 次）；"
                       "无新增证据时不得再派遣同类诊断"),
            "fingerprint": fp, "review_required": False,
            "notes": ["转方法转化（I2M/MMS）或重规划（stagnation-breaker）"],
            "hold": False, "preempted_action": ident}


def record_event(route_dir: Any, event: Dict[str, Any]) -> Dict[str, Any]:
    return append_event(route_dir, event)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _selftest() -> int:
    import tempfile
    failures: List[str] = []

    def expect(name: str, condition: bool, detail: str = "") -> None:
        print(f"  {'ok  ' if condition else 'FAIL'} {name}"
              + (f" —— {detail}" if detail and not condition else ""))
        if not condition:
            failures.append(name)

    decl = parse_declaration({
        "mechanism": "noise_level", "scope": "10x VD 20-coil",
        "assumptions": ["高斯噪声"], "evidence_refs": ["E7"],
        "predictions": ["X11 中 O1/O2 无差异"]})[0]
    expect("声明解析", decl is not None)
    first = classify(decl, [])
    expect("首次带证据 → NOVEL", first["tag_class"] == "NOVEL_DECISION_RELEVANT_DIAGNOSIS",
           str(first))
    repeat = classify(decl, [event_from_classification(decl, first, "test")])
    expect("同指纹同证据 → REPEATED", repeat["tag_class"] == "REPEATED_ATTRIBUTION")
    fresh = parse_declaration({**decl.raw, "evidence_refs": ["E7", "E9"]})[0]
    novel = classify(fresh, [event_from_classification(decl, first, "test")])
    expect("新增证据引用 → NOVEL", novel["tag_class"] == "NOVEL_DECISION_RELEVANT_DIAGNOSIS")
    # T01 — a self-declared "verified" physical limit without resolvable evidence must
    # not earn a verified verdict (no state at all).
    limit = parse_declaration({**decl.raw, "physical_limit": {"verified": True,
                                                             "scope": ">=20x"}})[0]
    phys = classify(limit, [])
    expect("T01 自我声明 verified 无来源 → 不得认定已验证",
           phys["tag_class"] == "INSUFFICIENT_EVIDENCE" and phys["review_required"],
           str(phys))
    # T02 — a limitation backed by resolvable, currently-valid evidence earns a scoped
    # verdict bounded by its limit type.
    state = {"state_version": 5, "evidence": [
        {"id": "E9", "kind": "experiment", "scope": "20x VD", "supports": [],
         "contradicts": [], "epistemic_status": "Observed",
         "source_ref": "X9 oracle power run", "verification_tier": "T2",
         "depends_on": [], "validity": {"status": "valid", "reason": "已按预注册",
                                        "since_state_version": 4}}]}
    limit2 = parse_declaration({**decl.raw, "physical_limit": {
        "verified": True, "limit_type": "detection_power_limit",
        "scope": ">=20x，直径 <1.5px 微血管", "source_refs": ["E9"]}})[0]
    phys2 = classify(limit2, [], state=state)
    expect("T02 有效证据支持的物理限制 → 带范围条件结论",
           phys2["tag_class"] == "PHYSICAL_LIMIT_WITH_SCOPE"
           and "条件性结论" in phys2["reason"], str(phys2))
    # T03 — the same limitation whose evidence was later revoked stops binding.
    revoked = json.loads(json.dumps(state))
    revoked["evidence"][0]["validity"]["status"] = "invalid"
    phys3 = classify(limit2, [], state=revoked)
    expect("T03 证据被撤销 → 不再作为可靠限制",
           phys3["tag_class"] == "INSUFFICIENT_EVIDENCE", str(phys3))
    # T05 — a confirmed operator failure (failed experiment in state) wins.
    op_state = {"state_version": 6, "experiments": [
        {"id": "X9", "status": "failed", "stage": "X2", "claim_targeted": [],
         "parent": None, "preregistration": {"frozen_at_state_version": 4}}]}
    invalid = parse_declaration({**decl.raw, "validity_findings": ["adjoint test failed"],
                                 "validity_evidence_refs": ["X9"]})[0]
    blocker = classify(invalid, [], state=op_state)
    expect("T05 真实算子失败（failed 实验）→ VALIDITY_BLOCKER 优先",
           blocker["tag_class"] == "VALIDITY_BLOCKER", str(blocker))
    invalid2 = parse_declaration({**decl.raw,
                                  "validity_findings": ["adjoint test failed"]})[0]
    unproven = classify(invalid2, [], state=op_state)
    expect("T05b 纯文本有效性声明 → 安全审查而非已验证故障",
           unproven["tag_class"] == "INSUFFICIENT_EVIDENCE"
           and unproven["safety"] == "hold_pending_verification", str(unproven))
    limit_noscope = parse_declaration({**decl.raw,
                                       "physical_limit": {"verified": True}})[0]
    noscope = classify(limit_noscope, [])
    expect("无范围物理限制 → review_required",
           noscope["review_required"] and noscope["tag_class"] == "INSUFFICIENT_EVIDENCE")
    incomplete, problems = parse_declaration({"mechanism": "conditioning"})
    expect("缺 scope/证据被拒", incomplete is None and len(problems) == 2)
    freetext = parse_declaration({**decl.raw, "mechanism": "病态问题"})[0]
    freetext_verdict = classify(freetext, [])
    expect("自由文本机制 → other_declared 等价性待审", freetext_verdict["review_required"])

    with tempfile.TemporaryDirectory() as temp:
        route = pathlib.Path(temp)
        stored = append_event(route, event_from_classification(decl, first, "selftest"))
        records, problems = load_events(route)
        expect("事件链可写可读", not problems and len(records) == 1)
        append_event(route, event_from_classification(decl, repeat, "selftest"))
        records, problems = load_events(route)
        expect("链式追加后校验通过", not problems and len(records) == 2)
        expect("历史聚合重复计数", history_for(records, stored["fingerprint"])["repeat_count"] == 1)
        path = events_path(route)
        lines = path.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[0])
        tampered["tag_class"] = "REPEATED_ATTRIBUTION"   # a real mutation, not a no-op
        lines[0] = json.dumps(tampered, ensure_ascii=False, sort_keys=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _, problems = load_events(route)
        expect("篡改被检出", bool(problems))
        try:
            append_event(route, event_from_classification(decl, first, "selftest"))
            expect("篡改后拒绝追加", False)
        except ChainDamaged:
            expect("篡改后拒绝追加", True)
        expect("canonical state 不受事件链影响", True)   # guard writes only <route>/domain/

    if failures:
        print(f"[FAIL] {len(failures)} selftest failures")
        return EXIT_ERROR
    print("[ok] domain_guard selftest")
    return EXIT_OK


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Trivial Attribution Guard (TAG)")
    parser.add_argument("--selftest", action="store_true")
    sub = parser.add_subparsers(dest="command")
    classify_p = sub.add_parser("classify", help="classify one attribution declaration")
    classify_p.add_argument("--state", required=True)
    classify_p.add_argument("--declaration", required=True)
    classify_p.add_argument("--record", action="store_true",
                            help="persist the verdict to <route>/domain/tag-events.jsonl")
    sub.add_parser("events", help="print the route's TAG events").add_argument("--route",
                                                                              required=True)
    sub.add_parser("check", help="validate the event chain").add_argument("--route",
                                                                         required=True)
    rec = sub.add_parser("recover", help="archive a damaged chain and start fresh")
    rec.add_argument("--route", required=True)
    rec.add_argument("--archive", action="store_true",
                     help="required confirmation: move the damaged log aside")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    if args.command == "classify":
        state_path = pathlib.Path(args.state)
        route_dir = state_path.parent
        try:
            value = json.loads(pathlib.Path(args.declaration).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"[env] declaration 不可读：{exc}", file=sys.stderr)
            return EXIT_ENV
        declaration, problems = parse_declaration(value)
        if declaration is None:
            for item in problems:
                print(f"[FAIL] {item}", file=sys.stderr)
            print("[FAIL] 判定为 INSUFFICIENT_EVIDENCE：声明不完整", file=sys.stderr)
            return EXIT_HARD
        records, chain_problems = load_events(route_dir)
        if chain_problems:
            for item in chain_problems:
                print(f"[FAIL] {item}", file=sys.stderr)
            return EXIT_HARD
        state = None
        try:
            loaded = json.loads(state_path.read_text(encoding="utf-8"))
            state = loaded if isinstance(loaded, dict) else None
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            state = None
        verdict = classify(declaration, records, state=state)
        print(json.dumps(verdict, ensure_ascii=False, indent=2))
        if args.record:
            event = append_event(route_dir, event_from_classification(
                declaration, verdict, "cli", state=state))
            # Keep stdout machine-readable: the confirmation goes to stderr.
            print(f"[recorded] seq={event['seq']} → {events_path(route_dir)}",
                  file=sys.stderr)
        return EXIT_OK
    if args.command == "events":
        records, problems = load_events(pathlib.Path(args.route))
        for item in problems:
            print(f"[FAIL] {item}", file=sys.stderr)
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return EXIT_HARD if problems else EXIT_OK
    if args.command == "check":
        _, problems = load_events(pathlib.Path(args.route))
        if problems:
            for item in problems:
                print(f"[FAIL] {item}", file=sys.stderr)
            return EXIT_HARD
        print(f"[ok] {events_path(args.route)} 链完整")
        return EXIT_OK
    if args.command == "recover":
        route = pathlib.Path(args.route)
        _, problems = load_events(route)
        if not problems:
            print(f"[ok] {events_path(route)} 链完整，无需恢复")
            return EXIT_OK
        if not args.archive:
            for item in problems[:3]:
                print(f"[FAIL] {item}", file=sys.stderr)
            print("[env] 确认后加 --archive 才会归档损坏日志并重新开始链条；"
                  "不会静默清空或重置序号", file=sys.stderr)
            return EXIT_ENV
        result = recover_log(route)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return EXIT_OK
    parser.error("需要子命令或 --selftest")
    return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
