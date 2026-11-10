#!/usr/bin/env python3
"""domain_replay.py — evaluation harness for real MRI research replays (RLP v2.0.1 §11).

Purpose
-------
Prepare the *interface* for the real-scientific A/B that v2.0.1 does not run: a
replay pack records a historical decision point with everything the agent was
allowed to see at that moment, hides everything that happened afterwards, and asks
the machinery (TAG / MMS / loop step) to act. The harness reports per-scenario
behaviour verdicts against the domain rules.

Honesty boundary
----------------
* Scenario packs shipped in ``examples/domain/mri-reconstruction/`` are **structural
  fixtures** distilled from the CT-FM and Wave-TOF task descriptions. They are not
  real project histories, and running them proves nothing about research
  effectiveness: **L3 NOT YET VALIDATED** until a blinded A/B on real project routes
  is executed with this harness.
* Leakage control: a pack declares the exact visible materials; anything else in the
  project (later results, later reports, full repository history) is out of scope for
  the runner by construction — the runner reads only the pack directory.

Pack schema (``research-idea-pipeline/replay-pack@1``)::

    {"_schema": ".../replay-pack@1", "task": "cross_domain_generative_prior",
     "decision_point": "adapter capacity expansion stalled",
     "visible": {"failures": [...], "declarations": [...]},
     "hidden_after": ["what really happened next (never shown to the runner)"],
     "probe": {"kind": "diagnosis|method_candidate",
               "declaration": {...TAG declaration...},
               "candidate": {...MMS candidate...}},
     "expected": {"no_fallbacks": ["noise_level", "forward_operator_mismatch"],
                  "allow": ["METHOD_TRANSITION_READY", ...]}}

CLI::

    python3 scripts/domain_replay.py run --pack examples/domain/mri-reconstruction
    python3 scripts/domain_replay.py validate --pack <dir>

Exit codes: 0 pass, 1 usage/selftest failure, 3 pack invalid or probe misbehaved,
4 environment.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cognition as cg
import domain_guard as dg
import domain_mms as mms
import domain_profile as dp

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_HARD = 3
EXIT_ENV = 4

PACK_SCHEMA = "research-idea-pipeline/replay-pack@1"
TASKS = ("cross_domain_generative_prior", "wave_3d_structure")


def load_pack(pack_path: pathlib.Path) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Read one pack file. Returns (pack|None, problems)."""
    try:
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, [f"{pack_path.name}: 不可读（{exc}）"]
    problems: List[str] = []
    if not isinstance(pack, dict):
        return None, [f"{pack_path.name}: 顶层必须是对象"]
    if pack.get("_schema") != PACK_SCHEMA:
        problems.append(f"{pack_path.name}: _schema 必须是 {PACK_SCHEMA}")
    if pack.get("task") not in TASKS:
        problems.append(f"{pack_path.name}: task 必须是 {TASKS} 之一")
    for field in ("decision_point", "probe", "expected"):
        if not isinstance(pack.get(field), (dict, str)):
            problems.append(f"{pack_path.name}: 缺少 {field}")
    visible = pack.get("visible")
    if not isinstance(visible, dict):
        problems.append(f"{pack_path.name}: visible 必须声明当时可见的材料")
    hidden = pack.get("hidden_after")
    if not isinstance(hidden, list) or not hidden:
        problems.append(f"{pack_path.name}: hidden_after 必须列出被隐藏的后续事实"
                        "（防泄漏审计的依据）")
    return (pack if not problems else None), problems


def load_packs(pack_dir: pathlib.Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    packs, problems = [], []
    for path in sorted(pack_dir.glob("*.json")):
        pack, pack_problems = load_pack(path)
        problems.extend(pack_problems)
        if pack is not None:
            pack["_source"] = path.name
            packs.append(pack)
    if not packs and not problems:
        problems.append(f"{pack_dir}: 未找到任何 replay pack")
    return packs, problems


def _scenario_state(pack: Dict[str, Any]) -> Dict[str, Any]:
    """A minimal canonical state assembled from the pack's visible materials only."""
    failures = [dict(item, id=item.get("id") or f"F{index}")
                for index, item in enumerate(pack.get("visible", {}).get("failures") or [])
                if isinstance(item, dict)]
    return {"state_version": pack.get("state_version", 1),
            "contract": {"primary_anchor": pack.get("primary_anchor", "performance"),
                         "constraints": [], "resources": [], "out_of_scope": []},
            "claims": [], "evidence": [], "assumptions": [], "hypotheses": [],
            "experiments": [], "literature": [], "failures": failures,
            "uncertainties": [], "assurance": [], "repairs": []}


def run_pack(pack: Dict[str, Any]) -> Dict[str, Any]:
    """Run one pack through the domain machinery and classify the behaviour."""
    probe = pack.get("probe") or {}
    state = _scenario_state(pack)
    expected = pack.get("expected") or {}
    forbidden = set(expected.get("no_fallbacks") or [])
    allowed = set(expected.get("allow") or [])
    verdict: Dict[str, Any] = {"decision_point": pack.get("decision_point"),
                               "task": pack.get("task"), "behaviour": None,
                               "used_forbidden_fallbacks": [], "ok": True,
                               "detail": ""}
    if probe.get("kind") == "diagnosis":
        declaration, problems = dg.parse_declaration(probe.get("declaration"))
        if declaration is None:
            verdict.update(ok=False,
                           detail="probe declaration 不完整：" + "；".join(problems))
            return verdict
        # Seed the chain from the pack's visible history: what was already attributed
        # at the decision point (NOVEL first, then its repeat) — never the hidden data.
        records: List[Dict[str, Any]] = []
        for prior in pack.get("visible", {}).get("prior_declarations") or []:
            prior_decl, prior_problems = dg.parse_declaration(prior)
            if prior_decl is None:
                continue
            first = dg.classify(prior_decl, records, state=state)
            records.append(dg.event_from_classification(prior_decl, first, "pack",
                                                        state=state))
            records.append(dg.event_from_classification(
                prior_decl, dict(first, tag_class="REPEATED_ATTRIBUTION"), "pack",
                state=state))
        fp = dg.fingerprint(declaration)
        history = dg.history_for(records, fp)
        if (history["latest"] or {}).get("tag_class") == "REPEATED_ATTRIBUTION":
            behaviour = "REPEATED_ATTRIBUTION"
        else:
            result = dg.classify(declaration, records, state=state)
            behaviour = result["tag_class"]
            if declaration.mechanism in forbidden and \
                    behaviour == "NOVEL_DECISION_RELEVANT_DIAGNOSIS" and \
                    not declaration.evidence_refs:
                verdict["used_forbidden_fallbacks"].append(declaration.mechanism)
        verdict["behaviour"] = behaviour
        if behaviour == "REPEATED_ATTRIBUTION" and (
                "METHOD_TRANSITION_READY" in allowed or
                "stagnation-breaker" in allowed or not allowed):
            verdict["ok"] = True
            verdict["detail"] = "重复归因被识别；研究转向合法方法转化"
        elif verdict["used_forbidden_fallbacks"]:
            verdict["ok"] = False
            verdict["detail"] = "probe 复现了平凡归因回退"
        elif behaviour in allowed or not allowed:
            verdict["ok"] = True
            verdict["detail"] = f"分类 {behaviour} 在预期集合内"
        else:
            verdict["ok"] = False
            verdict["detail"] = f"分类 {behaviour} 不在预期集合 {sorted(allowed)} 内"
    elif probe.get("kind") == "method_candidate":
        problems = mms.candidate_errors(probe.get("candidate"), state=state)
        duplicate = mms.duplicate_candidate_errors(probe.get("candidate") or {},
                                                   pathlib.Path(pack.get(
                                                       "route_dir", ".")))
        verdict["behaviour"] = "METHOD_CANDIDATE"
        verdict["ok"] = not problems and not duplicate
        verdict["detail"] = ("候选通过 MMS 契约" if verdict["ok"]
                             else "；".join((problems + duplicate)[:3]))
        if problems and forbidden:
            verdict["used_forbidden_fallbacks"] = [
                token for token in forbidden
                if token in json.dumps(probe.get("candidate") or {}, default=str)]
    return verdict


def run(pack_dir: pathlib.Path) -> Tuple[List[Dict[str, Any]], bool]:
    packs, problems = load_packs(pack_dir)
    reports = [{"pack": "load", "ok": False, "detail": problem} for problem in problems]
    ok = not problems
    for pack in packs:
        verdict = run_pack(pack)
        verdict["pack"] = pack.get("_source") or pack.get("task")
        reports.append(verdict)
        ok = ok and verdict.get("ok", False)
    return reports, ok


def _selftest() -> int:
    failures = []

    def expect(name, condition, detail=""):
        print(f"  {'ok  ' if condition else 'FAIL'} {name}"
              + (f" —— {detail}" if detail and not condition else ""))
        if not condition:
            failures.append(name)

    pack = {"_schema": PACK_SCHEMA, "task": "wave_3d_structure",
            "decision_point": "NMSE 改善但微血管指标未改善",
            "visible": {"failures": [{"id": "F1", "kind": "unsupported",
                                      "finding": "conditioning 假设未获支持"}],
                        "prior_declarations": [{
                            "mechanism": "noise_level", "scope": "wave 3d",
                            "assumptions": ["高斯噪声"], "evidence_refs": ["F1"]}]},
            "hidden_after": ["后续 Wave guidance 实验结果"],
            "probe": {"kind": "diagnosis", "declaration": {
                "mechanism": "noise_level", "scope": "wave 3d",
                "assumptions": ["高斯噪声"], "evidence_refs": ["F1"]}},
            "expected": {"no_fallbacks": ["noise_level"],
                         "allow": ["REPEATED_ATTRIBUTION"]}}
    report = run_pack(pack)
    expect("重复噪声归因被识别", report["ok"], str(report))

    pack2 = {"_schema": PACK_SCHEMA, "task": "cross_domain_generative_prior",
             "decision_point": "adapter 容量扩展失败",
             "visible": {"failures": []},
             "hidden_after": ["后续自蒸馏结果"],
             "probe": {"kind": "method_candidate", "candidate": {
                 "_schema": "research-idea-pipeline/method-candidate@1",
                 "candidate_id": "C1",
                 "direction": "prior_posterior_adaptation",
                 "target_failure_mechanism": "overstrong_prior",
                 "mathematical_change": {"changes_object": "w(y_Θ)",
                                         "changed_rule": "测量条件化加权"},
                 "expected_effect": {"prediction": "p", "criterion": "c",
                                     "falsification_test": "X1"},
                 "control_condition": {"capacity_matched": True,
                                       "description": "同参"},
                 "nearest_prior_work": {"reference": "CT-FM", "delta": "加权"},
                 "ssl_boundary_compliance": {"statement": "Θ/Λ",
                                             "uses_gt_for_selection": False},
                 "anchor_alignment": "performance"}},
             "expected": {"no_fallbacks": []}}
    report2 = run_pack(pack2)
    expect("完整候选通过 MMS 契约", report2["ok"], str(report2))

    bad = dict(pack2, _schema="research-lifecycle-protocol/replay-pack@1")
    _, problems = load_pack.__wrapped__ if False else (None, [])  # noqa: F841
    _p, problems = (lambda: (None, ["x"]))()  # placeholder keeps structure stable
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        dirp = pathlib.Path(temp)
        (dirp / "bad.json").write_text(json.dumps(bad, ensure_ascii=False),
                                       encoding="utf-8")
        packs, problems = load_packs(dirp)
        expect("非法 schema 被拒", not packs and any("schema" in p for p in problems))
        (dirp / "bad.json").unlink()
        packs, problems = load_packs(dirp)
        expect("空目录被报告", not packs and problems)

    if failures:
        print(f"[FAIL] {len(failures)} selftest failures")
        return EXIT_ERROR
    print("[ok] domain_replay selftest")
    return EXIT_OK


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MRI domain replay harness")
    parser.add_argument("--selftest", action="store_true")
    sub = parser.add_subparsers(dest="command")
    run_p = sub.add_parser("run", help="run every pack in a directory")
    run_p.add_argument("--pack", required=True)
    validate_p = sub.add_parser("validate", help="validate pack schema only")
    validate_p.add_argument("--pack", required=True)
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    pack_dir = pathlib.Path(args.pack)
    if not pack_dir.is_dir():
        print(f"[env] pack 目录不存在：{pack_dir}", file=sys.stderr)
        return EXIT_ENV
    if args.command == "validate":
        _packs, problems = load_packs(pack_dir)
        for problem in problems:
            print(f"[FAIL] {problem}", file=sys.stderr)
        print(f"[{'ok' if not problems else 'FAIL'}] {pack_dir}")
        return EXIT_OK if not problems else EXIT_HARD
    reports, ok = run(pack_dir)
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    print("L3 status: NOT YET VALIDATED — 合成/结构 fixture 只证明机制接线，"
          "科研有效性需要真实项目盲化 A/B")
    print("PASS" if ok else "FAIL")
    return EXIT_OK if ok else EXIT_HARD


if __name__ == "__main__":
    sys.exit(main())
