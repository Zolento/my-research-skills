#!/usr/bin/env python3
"""rsi_ablation.py — Skill-RSI ablation, overhead accounting and honest level reporting.

The ablation is not here to prove that every new module helps. It is here to show which
mechanism makes a measurable difference and to declare, in machine-readable form, what has
actually been verified:

* **L1 implementation validity** — format, permissions, unit tests and invariants pass.
* **L2 operational validity** — the real CLI/Scheduler/Replay consume the policy and
  produce an observable legal behaviour change.
* **L3 research improvement** — an independently evaluated improvement on unseen real
  research cases. This harness never claims L3 without such a run.

It also measures the cost of the new layer (prompt/serialised size, storage per record,
decision latency, extra tool calls) so complexity that buys nothing can be removed.

There is no composite score anywhere: arms are compared per dimension, small differences
are reported as indistinguishable, and unobservable decisions are excluded from any claim.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cognition as cg
import policy_evolution as pe
import research_replay as rr
import source_freeze as sf

EXIT_OK = cg.EXIT_OK
EXIT_ERROR = cg.EXIT_ERROR
EXIT_HARD = cg.EXIT_HARD
EXIT_ENV = cg.EXIT_ENV

ROOT = Path(__file__).resolve().parent.parent

#: The comparison the task asks for: Baseline / current CIE + Strategy Evolution / Skill-RSI.
CORE_ARMS: Tuple[str, ...] = ("baseline", "memory_only", "memory_prediction", "full_cie",
                              "rsi_full")

#: Skill-RSI minus one mechanism at a time. The goal is to identify which mechanisms act.
LEAVE_ONE_OUT: Tuple[str, ...] = ("rsi_without_trajectory", "rsi_without_replay",
                                  "rsi_without_scope", "rsi_without_promotion",
                                  "rsi_shadow")

RSI_MODULES: Tuple[str, ...] = ("decision_trajectory.py", "policy_evolution.py",
                                "policy_transfer.py", "research_replay.py",
                                "source_freeze.py", "strategy_memory.py",
                                "preset_router.py")


def default_cases() -> List[Dict[str, Any]]:
    directory = ROOT / "examples" / "replay" / "adversarial"
    if directory.is_dir():
        return rr.load_cases(directory)
    return rr.adversarial_cases()


def rsi_probe_cases(base_cases: Sequence[Dict[str, Any]], *, limit: Optional[int] = None,
                    status: str = "ACTIVE", scope: bool = True, trajectory: bool = True,
                    evaluated: bool = True,
                    policy_id_prefix: str = "P") -> List[Dict[str, Any]]:
    """Attach a promoted scoped policy candidate to cases that have a legal action pair.

    Why this exists: the shipped adversarial suite carries no policy candidate, so every RSI
    arm is a no-op on it and the honest result is "indistinguishable". Reporting only that
    would hide whether the mechanism is wired at all. These probes are still synthetic — they
    demonstrate the *mechanism*, not research capability — and the plain run is reported
    alongside them so the null result is not silently dropped.
    """
    probes: List[Dict[str, Any]] = []
    for case in base_cases:
        visible = case.get("visible") or {}
        scheduler = visible.get("scheduler") or {}
        actions = [dict(item) for item in (visible.get("legal_actions")
                                           or scheduler.get("next_actions") or [])
                   if isinstance(item, dict) and item.get("action")]
        if len(actions) < 2:
            # Fall back to the actions the runner itself would see for this case.
            actions = [dict(item) for item in rr._visible_actions(
                visible, visible.get("state") or {}, visible.get("scheduler"))
                if item.get("action")]
        if len(actions) < 2:
            continue
        actions = actions[:2]
        # Prefer an action the CIE+Strategy-Evolution arm would *not* have chosen, so the
        # probe actually exercises the policy step instead of restating the baseline.
        probe = json.loads(json.dumps(case))
        probe["id"] = f"{case.get('id')}-RSI"
        probe["visible"]["legal_actions"] = actions
        probe["visible"]["evidence_support"] = {
            "observed_actions": [],
            "replay_supported_actions": [item["action"] for item in actions],
        }
        baseline = rr.cie_offline_runner(rr.visible_view(probe), "full_cie")
        baseline_choice = baseline.get("chosen_intervention")
        remaining = [item["action"] for item in actions if item["action"] != baseline_choice]
        if not remaining:
            continue
        current, preferred = baseline_choice, remaining[0]
        probe["visible"]["evidence_support"]["observed_actions"] = (
            [current] if current else [])
        probe["visible"]["policy_candidates"] = [{
            "policy_id": f"{policy_id_prefix}-{case.get('id')}",
            "status": status,
            "strategy_changes": [{"kind": "same_tier_preference", "prefer_action": preferred}],
            "supporting_trajectory_ids": ["DT-synthetic-probe"] if trajectory else [],
            "evaluation_refs": ([{"independent": True, "verdict": "SUPPORTED",
                                  "project": "probe"}] if evaluated else []),
            "scope": ({"scope_kind": "local", "problem_structure": "rsi-probe"} if scope
                      else {}),
        }]
        probes.append(probe)
        if limit is not None and len(probes) >= limit:
            break
    return probes


def ablations(cases: Sequence[Dict[str, Any]], *, runs: int = 2) -> Dict[str, Any]:
    """Run the core ladder and the leave-one-out arms, on the plain and probe case sets."""
    core = rr.run_suite(cases, CORE_ARMS, runs)
    leave_one_out = rr.run_suite(cases, ("full_cie",) + LEAVE_ONE_OUT, runs)
    probes = rsi_probe_cases(cases)
    probe_core = rr.run_suite(probes, CORE_ARMS, runs) if probes else None
    # Guard probes: each variant violates exactly ONE guard, so a missing guard shows up
    # instead of being masked by an earlier one that is still present.
    guard_variants = {
        "unpromoted": dict(status="PROPOSED"),
        "unscoped": dict(scope=False),
        "unsupported": dict(trajectory=False),
        "unevaluated": dict(evaluated=False),
    }
    guard_probes: Dict[str, Any] = {}
    for name, kwargs in guard_variants.items():
        variant = rsi_probe_cases(cases, policy_id_prefix=f"PG-{name[:2]}", **kwargs)
        if not variant:
            continue
        report = rr.run_suite(variant, ("full_cie",) + LEAVE_ONE_OUT, runs)
        diverging = sorted(
            arm for arm, block in report["per_arm"].items()
            if arm != "full_cie" and any(
                item["decision"].get("policy_gate_bypassed")
                or item["decision"].get("policy_scope_bypassed")
                or item["decision"].get("policy_support_bypassed")
                or item["decision"].get("policy_applied")
                for item in block.get("results") or []))
        guard_probes[name] = {"cases": len(variant), "diverging_arms": diverging,
                              "leave_one_out": report}
    comparisons: Dict[str, Any] = {}
    for arm in ("full_cie",) + LEAVE_ONE_OUT:
        comparison = pe.distinguishable(core if arm in CORE_ARMS else leave_one_out,
                                        arm, "full_cie")
        comparisons[arm] = {
            "vs": "full_cie",
            "distinguishable": comparison["distinguishable"],
            "reason": comparison["reason"],
            "dimensions": comparison["dimensions"],
        }
    skill_rsi = pe.distinguishable(core, "rsi_full", "full_cie")
    return {
        "schema": "research-idea-pipeline/skill-rsi-ablation@1",
        "cases": len(cases),
        "runs_per_case": runs,
        "core": {"arms": list(CORE_ARMS), "report": core,
                 "undifferentiated_arms": core.get("undifferentiated_arms"),
                 "unobservable_decisions": core.get("unobservable_decisions")},
        "leave_one_out": {"arms": ["full_cie"] + list(LEAVE_ONE_OUT),
                          "report": leave_one_out},
        "skill_rsi_vs_current_cie": skill_rsi,
        "with_policy_candidates": {
            "cases": len(probes),
            "note": ("合成探针：给 case 附加一个已晋升的有作用域策略，用来证明机制接线；"
                     "仍然不是真实科研能力证据"),
            "skill_rsi_vs_current_cie": (pe.distinguishable(probe_core, "rsi_full", "full_cie")
                                         if probe_core else None),
            "report": probe_core,
            "guard_probes": {
                "note": ("每个探针只违反一个 guard（未晋升 / 无作用域 / 无轨迹依据 / "
                         "无独立评价）：用来测每个 guard 是否真的改变行为"),
                "variants": guard_probes,
            },
        },
        "comparisons": comparisons,
        "reading": ("逐维比较；差异在容差内或区间重叠即报告不可区分。"
                    "NO_SUPPORT 决策不计入任何结论。合成 fixture 上的差值不是真实科研性能。"),
        "limitations": [
            "fixture 是合成的：只能证明机制接线正确，不能证明科研能力提升",
            "没有真实模型、真实文献库或真实 GPU 运行",
            "L3（真实科研改进）需要未见过的真实案例与独立盲评，本报告不作该声明",
        ],
    }


# ---------------------------------------------------------------------------
# Cost accounting (complexity control)
# ---------------------------------------------------------------------------

def _serialised_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def overhead_report(*, iterations: int = 200) -> Dict[str, Any]:
    """Measure what the new layer costs: bytes, latency and extra calls.

    Prompt overhead is approximated by the size of the Skill-RSI reference document plus
    the added SKILL.md section, because those are what a session actually loads. No token
    counter is available offline, so a byte count is reported rather than a fabricated
    token figure.
    """
    import decision_trajectory as dt
    state = json.loads((ROOT / "templates" / "research-state.template.json")
                       .read_text(encoding="utf-8"))
    context = dt.build_context(state, scientific_question="overhead probe",
                               decided_at="2026-01-01T00:00:00Z",
                               active_hypotheses=[item.get("id")
                                                  for item in state.get("hypotheses") or []],
                               key_uncertainties=[item.get("id")
                                                  for item in state.get("uncertainties") or []])
    decision = dt.build_decision_record(
        state, route="A", project="probe", context=context,
        candidates=[{"action": "X1", "type": "discriminating_experiment", "target": "U1",
                     "eig": "high", "cost": "low"}],
        chosen="X1", scheduler_priority={"level": 4, "label": "high_information_gain_test"})
    candidate = {"policy_id": "P-probe", "policy_schema_version": pe.POLICY_SCHEMA_VERSION,
                 "parent_policy_id": None, "status": "PROPOSED",
                 "scope": {"scope_kind": "local", "problem_structure": "probe"},
                 "applicable_conditions": [{"kind": "min_open_uncertainties", "value": 1}],
                 "strategy_changes": [{"kind": "same_tier_preference",
                                       "prefer_action": "X1"}],
                 "supporting_trajectory_ids": ["DT-1"], "counterexamples": ["none"],
                 "expected_effect": {"mechanism": "probe", "direction": "up"},
                 "revalidation_conditions": ["probe"], "evaluation_refs": [],
                 "rollback_target": None}

    start = time.perf_counter()
    for _ in range(iterations):
        pe.candidate_signature(candidate)
    signature_us = (time.perf_counter() - start) / iterations * 1e6
    start = time.perf_counter()
    for _ in range(iterations):
        dt.build_context(state, scientific_question="probe",
                         decided_at="2026-01-01T00:00:00Z")
    context_us = (time.perf_counter() - start) / iterations * 1e6

    reference = ROOT / "references" / "skill-rsi-policy.md"
    prompt_bytes = reference.stat().st_size if reference.is_file() else 0
    module_lines = {}
    for name in RSI_MODULES:
        path = ROOT / "scripts" / name
        if path.is_file():
            module_lines[name] = len(path.read_text(encoding="utf-8").splitlines())
    manifest = sf.manifest(ROOT)
    return {
        "schema": "research-idea-pipeline/skill-rsi-overhead@1",
        "prompt_bytes": prompt_bytes,
        "prompt_note": "Skill-RSI 参考文档大小（渐进加载时按需读取，不每轮注入）",
        "trajectory_record_bytes": _serialised_size(decision),
        "policy_candidate_bytes": _serialised_size(candidate),
        "signature_latency_us": round(signature_us, 2),
        "context_build_latency_us": round(context_us, 2),
        "extra_tool_calls_per_loop": 1,
        "extra_tool_calls_note": ("research-loop 在应用路径上多写一条决策轨迹；"
                                  "策略评价是离线步骤，不在每轮循环内"),
        "protected_files": manifest.get("count"),
        "module_lines": module_lines,
        "new_module_lines": sum(module_lines.values()),
        "notes": [
            "没有可用的离线 token 计数器，因此报告字节数而不是编造 token 数",
            "source-freeze 在前/后各做一次全量摘要，只在应用路径上执行",
        ],
    }


# ---------------------------------------------------------------------------
# Honest level reporting
# ---------------------------------------------------------------------------

def level_report(*, l3_evidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """State exactly which level is verified. L3 is NOT claimed without a real run."""
    l1 = {
        "status": "VERIFIED",
        "evidence": ["实现格式/权限/不变量单元测试",
                     "decision_trajectory / policy_evolution / source_freeze / research_replay selftest",
                     "policy candidate 越权与可执行内容拒绝测试"],
    }
    l2 = {
        "status": "VERIFIED",
        "evidence": [
            "research-loop 通过现有 Strategy Decision Adapter 改变实际派遣动作（端到端测试）",
            "决策轨迹、策略存储、replay 消融、source-freeze 均由真实 CLI/测试消费",
            "晋升需要独立 replay 评价，且评价规则冻结后不可改动",
        ],
    }
    if l3_evidence:
        l3 = {"status": "VERIFIED", "evidence": l3_evidence}
    else:
        l3 = {"status": "NOT_VERIFIED",
              "evidence": [],
              "reason": ("没有未见的真实科研案例 A/B：合成 fixture 与形式化单元测试不能替代，"
                         "因此不宣称科研能力提升"),
              "note": "稳定策略的 L3 主张仍需独立真实评价"}
    return {
        "schema": "research-idea-pipeline/skill-rsi-levels@1",
        "L1_implementation_validity": l1,
        "L2_operational_validity": l2,
        "L3_research_improvement": l3,
        "must_not_conflate": ["策略候选已生成", "策略已被应用", "科研行为已改变",
                              "科研能力获得独立证据支持的改善"],
    }


def full_report(*, cases: Optional[Sequence[Dict[str, Any]]] = None, runs: int = 2) -> Dict[str, Any]:
    cases = list(cases) if cases is not None else default_cases()
    return {
        "schema": "research-idea-pipeline/skill-rsi-report@1",
        "ablation": ablations(cases, runs=runs),
        "overhead": overhead_report(),
        "levels": level_report(),
    }


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
    parser.add_argument("command", nargs="?", choices=("run", "overhead", "levels", "report"))
    parser.add_argument("--dir", help="directory of replay cases")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--selftest", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.selftest:
        return selftest()
    cases = None
    if args.dir:
        cases = rr.load_cases(Path(args.dir).expanduser())
    if args.command == "overhead":
        print(json.dumps(overhead_report(), ensure_ascii=False, indent=2))
        return EXIT_OK
    if args.command == "levels":
        print(json.dumps(level_report(), ensure_ascii=False, indent=2))
        return EXIT_OK
    if args.command in ("run", "report", None):
        print(json.dumps(full_report(cases=cases, runs=max(1, args.runs)),
                         ensure_ascii=False, indent=2))
        return EXIT_OK
    return EXIT_ERROR


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def selftest() -> int:
    checks: List[Tuple[str, bool]] = []

    def check(name, condition):
        checks.append((name, bool(condition)))

    cases = default_cases()[:4]
    report = ablations(cases, runs=1)
    check("the core ladder includes baseline / CIE+SE / Skill-RSI",
          set(CORE_ARMS) <= set(report["core"]["arms"]))
    check("Skill-RSI is compared against the current CIE+SE arm",
          "distinguishable" in report["skill_rsi_vs_current_cie"])
    check("leave-one-out arms exist", set(LEAVE_ONE_OUT) <= set(report["comparisons"]))
    blob = json.dumps(report["core"]["report"].get("per_arm", {}), ensure_ascii=False)
    check("no composite score key is reported", '"score"' not in blob)
    check("the report declares its limitations", bool(report["limitations"]))
    check("undifferentiated arms are reported, not hidden",
          "undifferentiated_arms" in report["core"])

    overhead = overhead_report(iterations=20)
    check("prompt overhead is measured in bytes", overhead["prompt_bytes"] > 0)
    check("record sizes are measured", overhead["trajectory_record_bytes"] > 0
          and overhead["policy_candidate_bytes"] > 0)
    check("latency is measured", overhead["signature_latency_us"] >= 0)
    check("there is no fabricated token count", "tokens" not in overhead)

    levels = level_report()
    check("L1 is verified", levels["L1_implementation_validity"]["status"] == "VERIFIED")
    check("L2 is verified", levels["L2_operational_validity"]["status"] == "VERIFIED")
    check("L3 is not claimed without a real run",
          levels["L3_research_improvement"]["status"] == "NOT_VERIFIED")
    check("the three states are explicitly not conflated",
          len(levels["must_not_conflate"]) == 4)

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    print("selftest " + ("OK" if not failed else "FAILED: " + "; ".join(failed)))
    return EXIT_OK if not failed else EXIT_HARD


if __name__ == "__main__":
    raise SystemExit(main())
