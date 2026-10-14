#!/usr/bin/env python3
"""research_summary.py — 只读的科研进展总结投影（`research-review` / `continue-research` 用）。

**只读**：读取 canonical Research State（可选 Scheduler / Cognition / 实验结果），输出一份
11 节人类可读报告。不修改任何 state、不派遣任务、不进入 research-loop、不新建实验。

与 `render_status.py` 的关系：STATUS 是"当前状态"的短投影；本脚本是"面向科研负责人的完整
进展总结"。两者都是 state 的**纯函数**，都不是第二份 machine state。

证据不足时输出 `[待补]`，**不补造**已完成工作、不把性能改善解释为机制成立、不把单次负结果
上升为普遍否证。`--check` 是幂等闸门（磁盘文件过期则退出码 3）。

用法：
    python3 scripts/research_summary.py --state <research-state.json> [--route-dir <dir>]
    python3 scripts/research_summary.py --state <state.json> --out <SUMMARY.md>
    python3 scripts/research_summary.py --state <state.json> --check --out <SUMMARY.md>
    python3 scripts/research_summary.py --selftest
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cognition as cg

SCHEMA_SUMMARY = "research-idea-pipeline/research-summary@1"
TBD = "[待补]"
ESTABLISHED = ("supported",)
PRELIMINARY = ("partially-supported",)
REFUTED = ("refuted", "killed")
EXIT_OK, EXIT_STALE, EXIT_MISSING = 0, 3, 4


def _items(state: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    value = (state or {}).get(key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) else default


def _or_tbd(value: Any) -> str:
    text = _text(value)
    return text or TBD


def _git_revision(root: Optional[pathlib.Path]) -> str:
    if root is None:
        return TBD
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or TBD
    except (OSError, subprocess.SubprocessError):
        return TBD


def _evidence_index(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(item.get("id")): item for item in _items(state, "evidence") if item.get("id")}


def _classify_claims(state: Dict[str, Any]) -> Dict[str, List[str]]:
    """Established / preliminary / refuted — from recorded status only, never inferred."""
    buckets: Dict[str, List[str]] = {"established": [], "preliminary": [], "refuted": [],
                                     "invalid_or_unverified": []}
    evidence = _evidence_index(state)
    for claim in _items(state, "claims"):
        ident = _text(claim.get("id"), "?")
        status = _text(claim.get("status")).lower()
        backing = [evidence[eid] for eid in claim.get("supporting_evidence") or []
                   if eid in evidence]
        qualified = [item for item in backing
                     if item.get("epistemic_status") in ("Observed", "Supported")
                     and _text((item.get("validity") or {}).get("status")) in ("", "valid")]
        if status in REFUTED:
            buckets["refuted"].append(ident)
        elif status in ESTABLISHED and qualified:
            buckets["established"].append(ident)
        elif status in ESTABLISHED or status in PRELIMINARY:
            buckets["preliminary"].append(ident)
        else:
            buckets["invalid_or_unverified"].append(ident)
    return buckets


def _next_actions(state: Dict[str, Any], blockers: Sequence[str]) -> List[Dict[str, str]]:
    """At most three, derived mechanically from unfinished obligations (suggestions only)."""
    actions: List[Dict[str, str]] = []
    for experiment in _items(state, "experiments"):
        identifier = _text(experiment.get("id"), "?")
        if _text(experiment.get("status")) in ("done", "failed") and not experiment.get("outcome_analysis"):
            actions.append({"question": f"{identifier} 的结果尚未做 Outcome Analysis",
                            "why": "缺少 R9.O/R10 分析时证据不能进入结论",
                            "depends_on": identifier,
                            "changes": "该实验对应 claim/uncertainty 的结论",
                            "minimal": "按既有 R9.O 流程提交分析",
                            "cost": "低", "stop_if": "分析判为工程故障则修复后重跑"})
    for uncertainty in _items(state, "uncertainties"):
        if _text(uncertainty.get("status")) not in ("open", "undecidable_recorded"):
            continue
        actions.append({"question": _or_tbd(uncertainty.get("question")),
                        "why": "仍未解且影响研究决定",
                        "depends_on": _text(uncertainty.get("id"), "?"),
                        "changes": "该不确定性的处置与后续方法选择",
                        "minimal": _or_tbd(uncertainty.get("cheapest_discriminating_test")),
                        "cost": "低—中", "stop_if": "判别结果不改变方法选择时停止继续归因"})
    for repair in _items(state, "repairs"):
        if _text(repair.get("closure")) not in ("RESOLVED", "CLOSED"):
            actions.append({"question": f"未闭环修复：{_or_tbd(repair.get('flaw'))}",
                            "why": "R10 要求 critical flaw 必须使 state 改变",
                            "depends_on": _text(repair.get("id"), "?"),
                            "changes": "受影响 claim 的有效性",
                            "minimal": _or_tbd(repair.get("disposition")),
                            "cost": "中", "stop_if": "修复无法闭环则按 R14 决策"})
    return actions[:3]


def _scientific_delta(state: Dict[str, Any], root: Optional[pathlib.Path]) -> str:
    """New scientific understanding since the last checkpoint, or `none`."""
    revisions: List[Any] = []
    if root is not None:
        path = pathlib.Path(root) / cg.COGNITION_DIRNAME / cg.REVISIONS_NAME
        if path.is_file():
            try:
                revisions = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                             if line.strip()]
            except (UnicodeDecodeError, OSError, json.JSONDecodeError):
                revisions = []
    if not revisions:
        return "none（无可核验的认知修订记录：不以文档或实验数量代替科学认识）"
    latest = revisions[-1] if isinstance(revisions[-1], dict) else {}
    kind = _text(latest.get("kind"), "unknown")
    return f"{kind}（来自 {cg.REVISIONS_NAME} 最后一条修订）"


def _decision_delta(state: Dict[str, Any], root: Optional[pathlib.Path]) -> str:
    decision = state.get("decision") if isinstance(state.get("decision"), dict) else {}
    verdict = _text(decision.get("verdict"))
    return f"decision.verdict={verdict}" if verdict else "none（未记录研究决策变化）"


def render_summary(state: Dict[str, Any], *, route: str = "", root: Optional[pathlib.Path] = None,
                   route_dir: Optional[pathlib.Path] = None,
                   skill_version: str = "", cutoff: str = "") -> str:
    """Render the eleven-section, read-only research summary."""
    contract = state.get("contract") if isinstance(state.get("contract"), dict) else {}
    claims = _classify_claims(state)
    experiments = _items(state, "experiments")
    blockers = [item for item in state.get("repairs") or []
                if isinstance(item, dict) and _text(item.get("closure")) not in ("RESOLVED", "CLOSED")]
    open_uncertainties = [item for item in _items(state, "uncertainties")
                          if _text(item.get("status")) in ("open", "undecidable_recorded")]
    actions = _next_actions(state, blockers)
    lines: List[str] = []
    add = lines.append

    add(f"# 科研进展总结（只读）— route {_or_tbd(route)}")
    add("")
    add(f"- Skill 版本：{_or_tbd(skill_version)} ｜ 执行范围：`read_only`"
        "（不改 state、不跑实验、不派遣）")
    add(f"- state_version：{state.get('state_version', TBD)} ｜ Git：{_git_revision(root)}"
        f" ｜ 信息截止：{_or_tbd(cutoff) or '本次读取时点'}")
    add(f"- 路线目录：{route_dir if route_dir else TBD}")
    add("")

    add("## 1. Executive Summary")
    add(f"- 目标：{_or_tbd(contract.get('goal'))}")
    add(f"- 主锚点：{_or_tbd(contract.get('primary_anchor'))}")
    add(f"- 规模：claims={len(_items(state, 'claims'))}, evidence={len(_items(state, 'evidence'))},"
        f" hypotheses={len(_items(state, 'hypotheses'))}, experiments={len(experiments)},"
        f" literature={len(_items(state, 'literature'))}")
    add(f"- 结论分布：已确立 {len(claims['established'])} ｜ 初步 {len(claims['preliminary'])}"
        f" ｜ 已否证 {len(claims['refuted'])} ｜ 未验证 {len(claims['invalid_or_unverified'])}")
    add("")

    add("## 2. Research Objective & Constraints")
    add(f"- 目标：{_or_tbd(contract.get('goal'))} ｜ 主锚点：{_or_tbd(contract.get('primary_anchor'))}"
        f" ｜ 次锚点：{_or_tbd(contract.get('core_goal_secondary'))}")
    add(f"- 成功判据：{_or_tbd(contract.get('success_criteria') or contract.get('frozen_success_criteria'))}")
    add(f"- 约束：{contract.get('constraints') or TBD} ｜ 范围外：{contract.get('out_of_scope') or TBD}"
        f" ｜ 资源：{contract.get('resources') or TBD}")
    add("")

    add("## 3. Current Methods & Implementation")
    methods = [item for item in _items(state, "hypotheses")
               if isinstance(item.get("method"), dict)]
    if methods:
        for item in methods:
            method = item["method"]
            add(f"- `{_text(item.get('id'))}` {_or_tbd(item.get('statement'))}"
                f" ｜ 版本 {_or_tbd(method.get('version'))}"
                f" ｜ 干预 {_or_tbd((method.get('intervention') or {}).get('kind') if isinstance(method.get('intervention'), dict) else method.get('intervention'))}")
    else:
        add(f"- {TBD}（state 中没有带 method 块的假设：方法尚未成型）")
    contracts = [item for item in experiments
                 if isinstance(item.get("preregistration"), dict)
                 and (item["preregistration"] or {}).get("method_contract")]
    add(f"- 已冻结设计契约：{len(contracts)} 个"
        + ("" if contracts else f"（{TBD}）"))
    add("")

    add("## 4. Research Timeline & Major Decisions")
    revisions = []
    if root is not None:
        path = pathlib.Path(root) / cg.COGNITION_DIRNAME / cg.REVISIONS_NAME
        if path.is_file():
            revisions = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    add(f"- 认知修订记录：{len(revisions)} 条"
        + ("（最近：" + revisions[-1][:160] + "）" if revisions else f"（{TBD}）"))
    add(f"- 当前研究决策：{state.get('decision') or TBD}")
    add("")

    add("## 5. Experimental Evidence")
    if experiments:
        for item in experiments:
            add(f"- `{_text(item.get('id'))}` 状态={_or_tbd(item.get('status'))}"
                f" ｜ 指标={_or_tbd(item.get('metric'))} ｜ 种子={_or_tbd(item.get('seed'))}"
                f" ｜ 数据切分={_or_tbd(item.get('data_split'))}"
                f" ｜ 结果版本={item.get('result_at_state_version', TBD)}"
                f" ｜ 分析={'有' if item.get('outcome_analysis') else '无'}")
    else:
        add(f"- {TBD}（尚无实验记录）")
    add("")

    add("## 6. Established / Unresolved / Refuted Findings")
    add(f"- **已确立**（supported 且合格证据支持）：{claims['established'] or TBD}")
    add(f"- **初步/未确立**：{claims['preliminary'] or TBD}")
    add(f"- **已否证/收窄**：{claims['refuted'] or TBD}")
    add(f"- **未验证/证据不合格**：{claims['invalid_or_unverified'] or TBD}")
    add(f"- **未解问题**：{[_text(item.get('id')) for item in open_uncertainties] or TBD}")
    add("")

    add("## 7. Scientific Insights & Failure Analysis")
    failures = _items(state, "failures")
    add(f"- 失败记忆：{len(failures)} 条"
        + (" ｜ " + "; ".join(f"`{_text(f.get('id'))}` {_or_tbd(f.get('kind'))}" for f in failures[:5])
           if failures else f"（{TBD}）"))
    add(f"- 未闭环修复：{[_text(r.get('id')) for r in blockers] or TBD}")
    add("- 注意：性能改善不等于机制成立；单次负结果不上升为普遍否证（本报告不推断）。")
    add("")

    add("## 8. Literature & Novelty Positioning")
    literature = _items(state, "literature")
    add(f"- 文献条目：{len(literature)}"
        + (" ｜ " + "; ".join(_or_tbd(item.get("ref")) for item in literature[:5]) if literature
           else f"（{TBD}）"))
    priors = sorted({_text(item.get("nearest_prior")) for item in _items(state, "hypotheses")
                     if _text(item.get("nearest_prior"))})
    add(f"- 最近邻工作：{priors or TBD}")
    add(f"- 创新边界：需由 R8 证据与 R7 审查支撑；本报告不代替证据资格判定。")
    add("")

    add("## 9. Current Blockers & Open Obligations")
    add(f"- 未闭环修复：{[_text(r.get('id')) for r in blockers] or '无'}"
        f" ｜ 未解问题：{len(open_uncertainties)}"
        f" ｜ 预算：{contract.get('resources') or TBD}")
    add(f"- 停止规则：{contract.get('stop_rules') or contract.get('outcome_policy') or TBD}")
    add("")

    add("## 10. Next Research Decisions")
    if actions:
        for index, action in enumerate(actions, 1):
            add(f"{index}. **{action['question']}**")
            add(f"   - 为何现在：{action['why']} ｜ 依赖：{action['depends_on']}")
            add(f"   - 会改变：{action['changes']} ｜ 最小验证：{action['minimal']}"
                f" ｜ 成本：{action['cost']}")
            add(f"   - 停止条件：{action['stop_if']}")
    else:
        add(f"- 无：没有未完成义务能改变研究决定（{TBD}：需人工判断是否进入 R14）")
    add("- 以上**仅为建议**，本次不派遣、不执行。")
    add("")

    add("## 11. Evidence & Artifact Index")
    add(f"- canonical state：`{route_dir / cg.STATE_NAME if route_dir else cg.STATE_NAME}`")
    add(f"- Scheduler：`{route_dir / cg.SCHEDULER_NAME if route_dir else cg.SCHEDULER_NAME}`")
    add(f"- 认知投影：`{cg.COGNITION_DIRNAME}/{cg.BRIEF_NAME}`、`{cg.COGNITION_DIRNAME}/{cg.REVISIONS_NAME}`")
    identifiers = ([_text(item.get("id")) for item in _items(state, "experiments")]
                   + [_text(item.get("id")) for item in _items(state, "evidence")])
    add(f"- 关键 ID：{identifiers[:20] or TBD}")
    add("")

    add("## 结论")
    top = ([f"已确立 `{item}`" for item in claims["established"][:5]]
           or [f"初步 `{item}`" for item in claims["preliminary"][:5]]
           or [f"{TBD}：尚无合格证据支持的科学结论"])
    for index, item in enumerate(top[:5], 1):
        add(f"**科学结论 {index}**：{item}")
    open_three = [_or_tbd(item.get("question")) for item in open_uncertainties[:3]] or [TBD]
    for index, item in enumerate(open_three, 1):
        add(f"**未解问题 {index}**：{item}")
    add(f"**最优先研究行动**：{actions[0]['question'] if actions else TBD}")
    add("")
    add("## 统一回报契约")
    add(f"- `action_taken`：read_only 总结（未修改 state、未执行实验、未派遣）")
    add(f"- `scientific_delta`：{_scientific_delta(state, root)}")
    add(f"- `decision_delta`：{_decision_delta(state, root)}")
    add(f"- `state_writeback`：none（只读；渲染产物为 `--out` 指定的报告文件）")
    add(f"- `next_action`：{actions[0]['question'] if actions else 'none'}")
    add(f"- `stop_reason`：summary_complete" + ("" if actions else "（无未完成义务）"))
    add("")
    return "\n".join(lines)


def selftest() -> int:
    """Deterministic checks; no network, no state writes."""
    failures: List[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            failures.append(name)

    state = {
        "state_version": 7,
        "contract": {"goal": "提升长尾检索召回", "primary_anchor": "performance",
                     "success_criteria": ["同算力下 recall@10 提升"]},
        "claims": [{"id": "C1", "status": "supported", "supporting_evidence": ["E1"]},
                   {"id": "C2", "status": "partially-supported"}],
        "evidence": [{"id": "E1", "epistemic_status": "Observed",
                      "validity": {"status": "valid"}, "source_ref": "exp:X1"}],
        "hypotheses": [{"id": "H1", "statement": "长尾被头部主导",
                        "method": {"version": "v1", "intervention": {"kind": "objective"}}}],
        "experiments": [{"id": "X1", "status": "done", "metric": "recall@10",
                         "result_at_state_version": 7}],
        "literature": [{"id": "LIT1", "ref": "focal loss"}],
        "failures": [{"id": "F1", "kind": "implementation"}],
        "uncertainties": [{"id": "U1", "status": "open", "question": "长尾是否被头部主导",
                           "cheapest_discriminating_test": "小规模子集对照"}],
        "repairs": [{"id": "R1", "flaw": "缺对照", "closure": "OPEN"}],
        "decision": {"verdict": "continue"}}
    report = render_summary(state, route="A", skill_version="1.0.0", cutoff="ts")
    for section in ("## 1. Executive Summary", "## 5. Experimental Evidence",
                    "## 10. Next Research Decisions", "## 11. Evidence & Artifact Index",
                    "## 统一回报契约"):
        check(f"含小节 {section}", section in report)
    check("标注 read_only", "read_only" in report)
    check("结论块含 5 条科学结论位", report.count("**科学结论") <= 5)
    check("最优先行动存在", "**最优先研究行动**：" in report and TBD not in report.split("最优先研究行动**：")[1][:20])
    check("未完成义务进入建议", "Outcome Analysis" in report)
    check("失败记忆被报告", "失败记忆：1 条" in report)
    check("机制结论不被推断", "性能改善不等于机制成立" in report)
    empty = render_summary({}, route="", skill_version="")
    check("空状态标 [待补] 而非编造", TBD in empty and "已确立 0" in empty)
    check("纯函数：两次渲染一致", render_summary(state, route="A") == render_summary(state, route="A"))
    check("schema 常量存在", SCHEMA_SUMMARY.endswith("@1"))
    for name in failures:
        print("  FAIL", name)
    if failures:
        print(f"selftest FAILED ({len(failures)} failures)")
        return 1
    print("selftest OK")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="read-only research progress summary")
    parser.add_argument("--state", help="canonical research-state.json")
    parser.add_argument("--root", help="project root (for cognition/git)")
    parser.add_argument("--route-dir", help="route directory")
    parser.add_argument("--route", help="route letter/name")
    parser.add_argument("--skill-version", default="")
    parser.add_argument("--cutoff", default="")
    parser.add_argument("--out", help="write the report here (default: stdout)")
    parser.add_argument("--check", action="store_true",
                        help="exit 3 when the file on disk differs from the projection")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.selftest:
        return selftest()
    if not args.state:
        parser.print_help()
        return 0
    state_path = pathlib.Path(args.state).expanduser()
    if not state_path.is_file():
        print(f"state 不存在：{state_path}", file=sys.stderr)
        return EXIT_MISSING
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, OSError, json.JSONDecodeError) as exc:
        print(f"state 不可读（{type(exc).__name__}）：不重建、不补造，请先修复", file=sys.stderr)
        return EXIT_MISSING
    route_dir = pathlib.Path(args.route_dir).expanduser() if args.route_dir else state_path.parent
    root = pathlib.Path(args.root).expanduser() if args.root else route_dir.parent.parent
    report = render_summary(state, route=args.route or route_dir.name, root=root,
                            route_dir=route_dir, skill_version=args.skill_version,
                            cutoff=args.cutoff)
    if args.out:
        out = pathlib.Path(args.out)
        if args.check:
            current = out.read_text(encoding="utf-8") if out.is_file() else ""
            if current != report:
                print(f"{out} 已过期（幂等闸门）", file=sys.stderr)
                return EXIT_STALE
            print(f"{out}: 一致")
            return EXIT_OK
        out.write_text(report, encoding="utf-8")
        print(f"wrote {out}")
        return EXIT_OK
    print(report)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
