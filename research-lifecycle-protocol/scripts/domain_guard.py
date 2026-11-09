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
    physical_limit: Optional[Dict[str, Any]] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def trivial_mechanism(self) -> bool:
        return self.mechanism in TRIVIAL_MECHANISMS


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


def append_event(route_dir: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Append one event under an exclusive lock, extending the hash chain."""
    path = events_path(route_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
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
        fcntl.flock(handle, fcntl.LOCK_EX)
        os.write(handle, (line + "\n").encode("utf-8"))
        os.fsync(handle)
    finally:
        os.close(handle)
    return record


class ChainDamaged(RuntimeError):
    """The event chain failed validation; refuse to append to a tampered log."""


def history_for(records: Sequence[Dict[str, Any]], fp: str) -> Dict[str, Any]:
    """Aggregated history for one fingerprint: seen refs, counts, latest verdict."""
    refs: set = set()
    repeat_count = 0
    latest: Optional[Dict[str, Any]] = None
    for record in records:
        if record.get("fingerprint") != fp:
            continue
        refs.update(record.get("evidence_refs") or [])
        if record.get("tag_class") == "REPEATED_ATTRIBUTION":
            repeat_count += 1
        latest = record
    return {"evidence_refs": refs, "repeat_count": repeat_count, "latest": latest}


# ---------------------------------------------------------------------------
# Classification (TG1–TG7)
# ---------------------------------------------------------------------------

def classify(declaration: Declaration, records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Classify one attribution declaration. Pure: reads history, writes nothing."""
    fp = fingerprint(declaration)
    history = history_for(records, fp)
    seen_refs = history["evidence_refs"]
    new_refs = [ref for ref in declaration.evidence_refs if ref not in seen_refs]
    review_required = False
    notes: List[str] = []

    if declaration.mechanism not in MECHANISMS:
        # Not keyword fuzzing: an unknown token is structurally a new declaration that
        # still has to carry evidence; equivalence for it cannot be proven mechanically.
        review_required = True
        notes.append("机制不在受控枚举内：等价性无法机械证明，登记待审")

    if declaration.validity_findings:
        # TG2 — a real validity defect wins over everything, including repetition.
        tag_class = "VALIDITY_BLOCKER"
        reason = "存在未解决的算子/流程验证失败或数据不一致证据：必须优先修复"
    elif isinstance(declaration.physical_limit, dict) and \
            declaration.physical_limit.get("verified") is True:
        # TG3 — verified physical limit, scope required.
        scope = str(declaration.physical_limit.get("scope") or "").strip()
        if scope:
            tag_class = "PHYSICAL_LIMIT_WITH_SCOPE"
            reason = f"已验证的物理限制，适用范围：{scope}"
        else:
            review_required = True
            tag_class = "INSUFFICIENT_EVIDENCE"
            reason = "物理限制声明缺少适用范围：无法机械确认，登记待审"
    elif not new_refs and history["latest"] is not None:
        # TG4 — same structural fingerprint, no evidence that history has not seen.
        tag_class = "REPEATED_ATTRIBUTION"
        reason = (f"等价归因（指纹 {fp[:16]}…）此前已记录 {history['repeat_count']} 次；"
                  f"本次证据引用 {declaration.evidence_refs} 均在历史集合内，无新增信息")
    elif new_refs:
        # TG5 — genuinely new evidence for this mechanism fingerprint.
        tag_class = "NOVEL_DECISION_RELEVANT_DIAGNOSIS"
        reason = f"存在该机制历史上未见过的新证据引用：{new_refs}"
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
            "review_required": review_required, "notes": notes,
            "decision_consequence": declaration.decision_consequence,
            "mechanism": declaration.mechanism, "scope": declaration.scope}


def event_from_classification(declaration: Declaration, verdict: Dict[str, Any],
                              source: str) -> Dict[str, Any]:
    return {"fingerprint": verdict["fingerprint"], "mechanism": declaration.mechanism,
            "scope": declaration.scope, "assumptions": declaration.assumptions,
            "evidence_refs": declaration.evidence_refs,
            "decision_consequence": verdict["decision_consequence"],
            "tag_class": verdict["tag_class"], "review_required": verdict["review_required"],
            "source": source}


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
    invalid = parse_declaration({**decl.raw, "validity_findings": ["adjoint test failed"]})[0]
    blocker = classify(invalid, [])
    expect("验证失败 → VALIDITY_BLOCKER 优先",
           blocker["tag_class"] == "VALIDITY_BLOCKER")
    limit = parse_declaration({**decl.raw, "physical_limit": {"verified": True,
                                                             "scope": ">=20x"}})[0]
    phys = classify(limit, [])
    expect("已验证物理限制 → PHYSICAL_LIMIT_WITH_SCOPE",
           phys["tag_class"] == "PHYSICAL_LIMIT_WITH_SCOPE")
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
        verdict = classify(declaration, records)
        print(json.dumps(verdict, ensure_ascii=False, indent=2))
        if args.record:
            event = append_event(route_dir, event_from_classification(declaration, verdict,
                                                                      "cli"))
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
    parser.error("需要子命令或 --selftest")
    return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
