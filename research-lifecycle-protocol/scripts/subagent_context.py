#!/usr/bin/env python3
"""subagent_context.py — 按角色生成子 Agent 的**最小任务上下文**与权限上限。

它解决的问题
------------
此前的做法是把 `shared-contract.md` 与整份 `references/roles.md` 交给每个子 Agent。
子 Agent 因此拿到全量全局规则与全量历史，注意力被稀释，还容易产生「我也有权写」
的权限幻觉。

本模块把「该角色需要什么」写成机器可读的契约，并**机械校验权限不因裁剪而扩张**。

权限模型
--------
权限是**能力集合**，不是文字描述。父级（主 Agent）有上限 `PARENT_PERMITS`，
子角色拿到的 `permits` 必须是它的子集。四个关键能力：

=================== ==========================================================
能力                 含义
=================== ==========================================================
`write_canonical`    写 `research-state.json`
`modify_anchor`      改项目主锚点 / 路线锚点
`execute_experiment` 执行实验
`write_artifacts`    写 `experiments/` 与 `results/` 下的产物
=================== ==========================================================

**五条不可越过的边界**（`check()` 逐条机械判定）：

1. 每个角色的 `permits` 必须是父级权限的子集；
2. `write_canonical` 只允许主 Agent，或被用户显式授权的角色；
3. 任何角色都不得获得 `modify_anchor`（只有用户能改锚点）；
4. `execute_experiment` 为真时必须同时要求 manifest 与批准字段；
5. `never` 列表必须非空 —— 「什么都给它」等于没有裁剪。

Usage
-----
    python3 scripts/subagent_context.py roles
    python3 scripts/subagent_context.py build --role literature --task "核验近邻"
    python3 scripts/subagent_context.py check
    python3 scripts/subagent_context.py --selftest

Exit codes: 0 pass, 1 argument error, 3 hard violation, 4 environment.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA_CONTRACT = "research-idea-pipeline/subagent-contract@1"
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_HARD = 3
EXIT_ENV = 4

SKILL_ROOT = Path(__file__).resolve().parent.parent

#: 能力枚举。
CAPABILITIES: Tuple[str, ...] = (
    "write_canonical", "modify_anchor", "execute_experiment", "write_artifacts",
)

#: 父级（主 Agent）权限上限。子角色的 `permits` 必须是它的子集。
#: `modify_anchor` **不在**任何主体的能力集里 —— 它只属于用户。
PARENT_PERMITS: Dict[str, bool] = {
    "write_canonical": True,
    "modify_anchor": False,
    "execute_experiment": True,
    "write_artifacts": True,
}

#: 用户显式授权后可以拿到 `write_canonical` 的角色。默认空。
USER_GRANTABLE: Tuple[str, ...] = ()

ROLES: Dict[str, Dict[str, Any]] = {
    "literature": {
        "title": "Literature Agent（S-Lit / 检索）",
        "purpose": "检索、核验近邻工作、判定结构差异与新颖性边界",
        "receives": (
            "研究问题原话",
            "本次任务的一句话指令",
            "检索范围：源、时间窗、语言",
            "要比对的论文清单",
            "评价规则：检索等级与措辞等级",
            "来源与引用要求",
            "输出 Schema",
            "当前权限：只读",
        ),
        "never": (
            "完整 research-state.json",
            "主 Agent 的结论与偏好",
            "其他角色的评审意见",
            "未完成实验的结果",
        ),
        "output": "每条结果带 source、DOI/arXiv id、检索式与命中位置；未核实的标「待核实」",
        "evidence_slice": "literature", 
        "permits": {"write_canonical": False, "modify_anchor": False,
                    "execute_experiment": False, "write_artifacts": False},
        "may_write": ("<route>/docs/refs/cache/", "<subagent-raw>/"),
        "manifest_required": False,
        "approval_required": False,
        "approval_note": "写真实 Zotero 库需要用户明确请求",
    },
    "theory": {
        "title": "Theory Agent（S-Theory）",
        "purpose": "判定机制假设是否成立，找反例与不可能性，给出边界条件",
        "receives": (
            "机制假设 statement + assumptions",
            "涉及的数学对象与符号约定",
            "前提与冻结条件",
            "与本假设相关的 evidence 切片",
            "待证明或待否证命题",
            "输出契约",
        ),
        "never": (
            "完整补充实验日志",
            "其他候选的完整档案",
            "主 Agent 的方向偏好",
        ),
        "output": "命题形式化、证明或反例、失败在哪一步、需要的额外假设；未完成标「待补证明 · 待核实」",
        "evidence_slice": "theory",
        "permits": {"write_canonical": False, "modify_anchor": False,
                    "execute_experiment": False, "write_artifacts": False},
        "may_write": ("<subagent-raw>/",),
        "manifest_required": False,
        "approval_required": False,
    },
    "experiment": {
        "title": "Experiment Agent（A-Experimenter）",
        "purpose": "执行已冻结的实验并如实回报",
        "receives": (
            "冻结的实验 manifest（内容绑定）",
            "具体实验动作",
            "资源限制：GPU、时长、存储",
            "不允许修改的配置清单",
            "验收指标与停止条件",
            "输出路径与证据要求",
        ),
        "never": (
            "未冻结的候选方案",
            "主 Agent 对结果的期望",
            "其他实验 arm 的结果（避免选择性调参）",
        ),
        "output": "execution_record：manifest digest、实际命令、arm/control 真实取值、退出状态；失败须区分实现错误与无效执行",
        "evidence_slice": "experiment",
        "permits": {"write_canonical": False, "modify_anchor": False,
                    "execute_experiment": True, "write_artifacts": True},
        "may_write": ("<route>/experiments/", "<route>/results/"),
        "manifest_required": True,
        "approval_required": True,
        "approval_note": "改预算、延长冻结期、动新 GPU 需要用户批准",
    },
    "assurance": {
        "title": "Assurance Agent（六攻击面 / S-Devil / S-Repro / S-Integrity）",
        "purpose": "攻击一个已成型方案，给出可判定的 Kill Condition",
        "receives": (
            "被审对象：claim / 方案 / artifact 路径",
            "该攻击面的定义（只给自己的那一面）",
            "相关 evidence 与 assumptions 切片",
            "已存在的反例与 failure memory",
            "五元组输出契约",
        ),
        "never": (
            "其他攻击面的评审意见（独立判定必须先于交叉质询）",
            "主 Agent 的倾向",
            "S-Devil 的分数（它不打分）",
        ),
        "output": "(Attack, Target Claim, Alternative, Discriminating Test, Kill Condition)；Kill Condition 必须可判定",
        "evidence_slice": "review",
        "permits": {"write_canonical": False, "modify_anchor": False,
                    "execute_experiment": False, "write_artifacts": False},
        "may_write": ("<subagent-raw>/",),
        "manifest_required": False,
        "approval_required": False,
    },
    "discovery": {
        "title": "Discovery Agent（R3 的 P1—P6 隔离算子）",
        "purpose": "在隔离上下文里产生候选，保持多样性",
        "receives": (
            "研究锚点与约束",
            "分配给它的那一个算子",
            "可用的文献与 failure memory 切片",
            "输出 Schema：niche / operator / parents / generation",
        ),
        "never": (
            "其他算子产出的候选（隔离的意义就在这里）",
            "QD archive 全文",
            "主 Agent 的排序",
        ),
        "output": "结构化候选 + 一句话 falsifier + nearest_prior",
        "evidence_slice": "discovery",
        "permits": {"write_canonical": False, "modify_anchor": False,
                    "execute_experiment": False, "write_artifacts": False},
        "may_write": (),
        "manifest_required": False,
        "approval_required": False,
    },
}

ROLE_IDS: Tuple[str, ...] = tuple(ROLES)


def role_contract(role: str) -> Dict[str, Any]:
    if role not in ROLES:
        raise KeyError(f"unknown role: {role}")
    contract = dict(ROLES[role])
    contract["role"] = role
    contract["schema"] = SCHEMA_CONTRACT
    return contract


def capabilities_subset(child: Dict[str, bool], parent: Dict[str, bool]) -> List[str]:
    """返回 child 超出 parent 的能力名。空列表 = 是子集。"""
    excess: List[str] = []
    for capability in CAPABILITIES:
        if child.get(capability) and not parent.get(capability):
            excess.append(capability)
    return excess


def build(
    role: str,
    task: str,
    *,
    evidence_slices: Optional[Sequence[Dict[str, Any]]] = None,
    authorization: str = "read_only",
    parent_permits: Optional[Dict[str, bool]] = None,
    user_granted: bool = False,
    stage: Optional[str] = None,
) -> Dict[str, Any]:
    """生成一个子 Agent 的最小任务上下文。

    **不读取 Research State 全文**：证据以切片引用形式传入（`evidence_slices`），
    每片必须带原始 id，由调用方负责切片。本函数不猜切片内容。
    """
    if role not in ROLES:
        return {"status": "FAIL", "error": f"unknown role: {role}"}
    if authorization not in ("read_only", "advisory", "execute"):
        return {"status": "FAIL", "error": f"unknown authorization: {authorization}"}

    parent = dict(parent_permits or PARENT_PERMITS)
    contract = role_contract(role)
    permits = dict(contract["permits"])

    # 唯一可以放宽的路径：用户显式授权且角色在 USER_GRANTABLE 内
    if user_granted and role in USER_GRANTABLE:
        permits["write_canonical"] = True

    excess = capabilities_subset(permits, parent)
    if excess:
        return {"status": "FAIL",
                "error": f"role {role} exceeds parent permissions: {excess}"}
    if permits.get("modify_anchor"):
        return {"status": "FAIL", "error": "no role may modify the anchor"}
    # 边界 2：write_canonical 只属于主 Agent，或被用户显式授权的角色。
    if permits.get("write_canonical") and not (user_granted and role in USER_GRANTABLE):
        return {"status": "FAIL",
                "error": (f"role {role} may not write canonical state without "
                          f"explicit user authorisation")}

    slices = list(evidence_slices or ())
    slice_problems: List[str] = []
    for item in slices:
        if not isinstance(item, dict):
            slice_problems.append("slice is not an object")
            continue
        if not item.get("ref"):
            slice_problems.append("slice has no source ref (evidence_id / experiment_id / paper_id)")

    lines: List[str] = []
    lines.append(f"# 任务上下文 · {contract['title']}")
    lines.append("")
    lines.append(f"**任务：** {task}")
    if stage:
        lines.append(f"**阶段：** {stage}")
    lines.append("")
    lines.append("## 你能收到什么")
    for item in contract["receives"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 你不会收到什么（并且不需要）")
    for item in contract["never"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 权限（上限，不可自行扩大）")
    for capability in CAPABILITIES:
        lines.append(f"- `{capability}`: **{permits.get(capability)}**")
    if contract.get("may_write"):
        lines.append(f"- 可写位置：{'、'.join(contract['may_write'])}")
    else:
        lines.append("- 可写位置：无（只读角色）")
    if contract.get("approval_required"):
        lines.append(f"- 需要上级批准：是（{contract.get('approval_note', '')}）")
    else:
        lines.append(f"- 需要上级批准：否"
                     + (f"（{contract['approval_note']}）" if contract.get("approval_note") else ""))
    lines.append("")
    lines.append("## 输出契约")
    lines.append(f"- {contract['output']}")
    lines.append("")
    lines.append("## 硬边界")
    lines.append("- 你的输出是**输入**，不是科学证据。主 Agent 汇总，但汇总不是认证。")
    lines.append("- 不得写 canonical Research State，不得改锚点，不得扩大自己的权限。")
    lines.append("- 证据切片是引用，不得重写；任何结论都要能回溯到切片的原始 id。")
    if slices:
        lines.append("")
        lines.append("## 证据切片")
        for item in slices:
            ref = item.get("ref") or "MISSING-REF"
            note = item.get("note") or ""
            lines.append(f"- `{ref}`{(' —— ' + note) if note else ''}")

    payload = {
        "schema": SCHEMA_CONTRACT,
        "role": role,
        "title": contract["title"],
        "purpose": contract["purpose"],
        "task": task,
        "stage": stage,
        "authorization": authorization,
        "permits": permits,
        "parent_permits": parent,
        "evidence_slice_kind": contract["evidence_slice"],
        "manifest_required": contract.get("manifest_required", False),
        "approval_required": contract.get("approval_required", False),
        "may_write": list(contract.get("may_write") or ()),
        "evidence_slices": slices,
        "text": "\n".join(lines) + "\n",
        "chars": len("\n".join(lines)) + 1,
        "includes_full_state": False,
        "includes_global_rules": False,
        "slice_problems": slice_problems,
        "can_proceed": not slice_problems,
        "status": "PASS" if not slice_problems else "FAIL",
    }
    return payload


# ---------------------------------------------------------------------------
# 五条边界的机械校验
# ---------------------------------------------------------------------------

def check() -> Tuple[bool, List[str]]:
    problems: List[str] = []
    for role, contract in sorted(ROLES.items()):
        permits = contract.get("permits") or {}
        missing = [name for name in CAPABILITIES if name not in permits]
        if missing:
            problems.append(f"{role}: permits 缺少能力 {missing}")
            continue
        excess = capabilities_subset(permits, PARENT_PERMITS)
        if excess:
            problems.append(f"{role}: 超出父级权限 {excess}")
        if permits.get("modify_anchor"):
            problems.append(f"{role}: 不得拥有 modify_anchor")
        if permits.get("write_canonical") and role not in USER_GRANTABLE:
            problems.append(f"{role}: write_canonical 需要用户显式授权")
        if permits.get("execute_experiment"):
            if not contract.get("manifest_required"):
                problems.append(f"{role}: execute_experiment 必须要求 manifest")
            if not contract.get("approval_required"):
                problems.append(f"{role}: execute_experiment 必须要求批准")
        if not contract.get("never"):
            problems.append(f"{role}: never 为空，等于没有裁剪")
        if not contract.get("receives"):
            problems.append(f"{role}: receives 为空")
        if not contract.get("output"):
            problems.append(f"{role}: 缺少输出契约")
    if not ROLES:
        problems.append("没有任何角色契约")
    return (not problems), problems


def render_roles() -> str:
    lines = ["| 角色 | 目的 | 写 canonical | 执行实验 | 需要批准 |", "|---|---|---|---|---|"]
    for role, contract in ROLES.items():
        permits = contract["permits"]
        lines.append(f"| `{role}` | {contract['purpose']} | "
                     f"{permits['write_canonical']} | {permits['execute_experiment']} | "
                     f"{contract.get('approval_required')} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def selftest(verbose: bool = False) -> Dict[str, Any]:
    checks: List[Tuple[str, bool, str]] = []

    def expect(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    ok, problems = check()
    expect("check: 五条边界全部成立", ok, "；".join(problems[:3]))

    base = build("literature", "核验 12 篇近邻的结构差异")
    expect("build: 正常任务上下文可生成", base["status"] == "PASS", str(base.get("error")))
    expect("build: 不含完整 state", base["includes_full_state"] is False)
    expect("build: 不含全局规则全文", base["includes_global_rules"] is False)
    expect("build: 默认不写 canonical", base["permits"]["write_canonical"] is False)
    expect("build: 默认不改锚点", base["permits"]["modify_anchor"] is False)
    expect("build: 角色只有只读权", base["permits"]["execute_experiment"] is False)

    # 上下文规模远小于整份全局规则
    roles_md = SKILL_ROOT / "references" / "roles.md"
    if roles_md.is_file():
        full = len(roles_md.read_text(encoding="utf-8"))
        expect("build: 小于整份 roles.md 的 1/4", base["chars"] * 4 < full,
               f"{base['chars']} vs {full}")

    # 权限扩张必须被拒
    escalated = build("literature", "t",
                      parent_permits=dict(PARENT_PERMITS, write_canonical=False))
    expect("build: 父级无写权时子角色无写权", escalated["permits"]["write_canonical"] is False)
    widen = dict(ROLES["literature"]["permits"])
    widen["write_canonical"] = True
    original = dict(ROLES["literature"]["permits"])
    try:
        ROLES["literature"]["permits"] = widen
        bad = build("literature", "t")
        expect("build: 无用户授权的扩权被拒", bad["status"] == "FAIL", str(bad))
        ok2, problems2 = check()
        expect("check: 无用户授权的扩权被判红", not ok2, "；".join(problems2[:2]))
    finally:
        ROLES["literature"]["permits"] = original

    # 锚点永不可改
    anchor = dict(ROLES["theory"]["permits"])
    anchor["modify_anchor"] = True
    original2 = dict(ROLES["theory"]["permits"])
    try:
        ROLES["theory"]["permits"] = anchor
        expect("build: 改锚点能力被拒", build("theory", "t")["status"] == "FAIL")
        ok3, _ = check()
        expect("check: 改锚点能力被判红", not ok3)
    finally:
        ROLES["theory"]["permits"] = original2

    # 执行角色必须带 manifest + 批准
    exec_role = build("experiment", "跑已冻结的 X3")
    expect("build: experiment 允许执行", exec_role["permits"]["execute_experiment"] is True)
    expect("build: experiment 必须要求批准", exec_role["approval_required"] is True or
           ROLES["experiment"]["approval_required"] is True)
    expect("build: experiment 可写产物但不写 state",
           exec_role["permits"]["write_artifacts"] is True and
           exec_role["permits"]["write_canonical"] is False)

    # 证据切片必须带来源
    with_ref = build("assurance", "攻击 claim C1",
                     evidence_slices=[{"ref": "E3", "note": "NMSE 改善"}])
    expect("build: 带来源的切片被接受", with_ref["status"] == "PASS")
    without_ref = build("assurance", "攻击 claim C1",
                        evidence_slices=[{"note": "没有来源"}])
    expect("build: 无来源的切片被拒", without_ref["status"] == "FAIL")

    # 未知角色 / 非法授权
    expect("build: 未知角色被拒", build("intern", "t")["status"] == "FAIL")
    expect("build: 非法授权被拒",
           build("literature", "t", authorization="root")["status"] == "FAIL")

    # 每个角色都能生成，且都不写 canonical
    for role in ROLE_IDS:
        payload = build(role, "probe")
        expect(f"build: {role} 可生成且不写 canonical",
               payload["status"] == "PASS" and
               payload["permits"]["write_canonical"] is False, str(payload.get("error")))

    passed = sum(1 for _, ok, _ in checks if ok)
    for name, ok, detail in checks:
        if verbose or not ok:
            print(f"[{'ok  ' if ok else 'FAIL'}] {name}" + (f" —— {detail}" if detail else ""))
    return {"status": "PASS" if passed == len(checks) else "FAIL",
            "passed": passed, "total": len(checks),
            "failures": [name for name, ok, _ in checks if not ok]}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="子 Agent 最小任务上下文")
    parser.add_argument("command", nargs="?", default=None,
                        choices=[None, "roles", "build", "check"])
    parser.add_argument("--role", default=None)
    parser.add_argument("--task", default="")
    parser.add_argument("--authorization", default="read_only")
    parser.add_argument("--slice", action="append", default=None,
                        help="证据切片，格式 <ref>[=<note>]")
    parser.add_argument("--stage", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        result = selftest(verbose=True)
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_OK if result["status"] == "PASS" else EXIT_HARD

    if args.command == "roles":
        print(render_roles(), end="")
        return EXIT_OK

    if args.command == "check":
        ok, problems = check()
        if ok:
            print(f"ok   {len(ROLES)} 个角色契约全部满足五条边界")
            return EXIT_OK
        for problem in problems:
            print("FAIL " + problem)
        return EXIT_HARD

    if args.command == "build":
        if not args.role:
            parser.error("需要 --role")
        slices = []
        for raw in args.slice or ():
            ref, _, note = raw.partition("=")
            slices.append({"ref": ref, "note": note})
        payload = build(args.role, args.task, evidence_slices=slices,
                        authorization=args.authorization, stage=args.stage)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(payload.get("text") or payload.get("error", ""), end="")
        return EXIT_OK if payload["status"] == "PASS" else EXIT_HARD

    parser.print_help()
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
