#!/usr/bin/env python3
"""context_packet.py — 面向**一次科研决策**的最小 Research Context Packet。

它是什么，不是什么
------------------
Packet 是 **canonical Research State 的可重建派生视图**。它**不是**：

* 第九类一等状态对象（八类对象与 `contract` 不变）；
* 第二套 Research Memory（认知记忆仍由 `cognition.py` 维护）；
* 授权来源（它描述当前授权，不产生授权）；
* 证据（它引用 `evidence[]`，不新增、不抬高证据等级）。

每一条都能回到 canonical state 的某个对象或 `contract` 字段。指不回去的内容**不写进 Packet**。

为什么需要它
------------
「每轮注入全部历史」是上下文膨胀的主要来源。一次科研决策真正需要的是十三项内容：
项目与路线、状态版本与 digest、主锚点、授权与关键约束、活跃机制及其证据资格、
最重要的未解决问题、竞争解释、已失败且禁止等价重试的路线、正在运行或待处理的实验、
上一轮实际决策、当前合法动作、必须审查的证据引用、必要的领域边界。
其余历史留在 Research State 与原始资产里，按需检索。

失效与恢复
----------
Packet 绑定五项：`state_version`、canonical digest、相关 evidence digest、Skill 协议版本、
Domain Profile 配置摘要。State 更新后 `verify()` 会判定旧的 Packet 失效，此时**不得**：

* 把旧摘要当成新事实；
* 自动清空 Research State；
* 重新 Bootstrap。

正确动作是走既有 CIE 恢复，必要时精确读取原始证据。

Usage
-----
    python3 scripts/context_packet.py build --state <state.json>
    python3 scripts/context_packet.py build --state S --task method --domain mri-reconstruction
    python3 scripts/context_packet.py verify --packet P.json --state <state.json>
    python3 scripts/context_packet.py --selftest

Exit codes: 0 pass, 1 argument error, 3 hard violation, 4 environment / stale.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cognition as cg

SCHEMA_PACKET = "research-idea-pipeline/context-packet@1"

EXIT_OK = cg.EXIT_OK
EXIT_ERROR = cg.EXIT_ERROR
EXIT_HARD = cg.EXIT_HARD
EXIT_ENV = cg.EXIT_ENV

SKILL_ROOT = Path(__file__).resolve().parent.parent

#: 研究上下文预算（字符）。与协议预算分开，见 `context_planner.BUDGETS`。
DEFAULT_RESEARCH_BUDGET = 12_000

#: 任务类型 → 其中哪些字段优先。**只改变排序与篇幅，不改变事实。**
TASK_KINDS: Tuple[str, ...] = (
    "continue_method",   # 继续方法研究
    "review_paper",      # 论文审查
    "audit_evidence",    # 证据审计
    "discover",          # 扩大候选
    "inspect",           # 只读查看
)

#: 永远不因预算被截断的字段。截掉它们等于改变了这次决策的前提。
NEVER_TRUNCATE: Tuple[str, ...] = (
    "authorization", "constraints", "anchor", "frozen_protocol", "banned_retries",
    "required_domain_boundaries", "stale", "state_version", "canonical_digest",
)

#: 任务类型 → 优先保留的字段（其余字段允许被压缩成计数）。
TASK_PRIORITY: Dict[str, Tuple[str, ...]] = {
    "continue_method": ("active_mechanisms", "unresolved", "frozen_protocol",
                        "banned_retries", "legal_actions"),
    "review_paper": ("claims_under_review", "evidence_refs", "competing_explanations",
                     "unresolved"),
    "audit_evidence": ("evidence_refs", "claims_under_review", "unresolved",
                       "competing_explanations"),
    "discover": ("banned_retries", "unresolved", "competing_explanations", "legal_actions"),
    "inspect": (),
}


def _digest(value: Any) -> str:
    return cg.digest_of(value)


def _short(value: Any, limit: int = 160) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _skill_version(root: Path) -> Optional[str]:
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("version:"):
            return stripped.split(":", 1)[1].strip().strip('"').strip("'")
    return None


def _domain_digest(domain: Optional[str], root: Path) -> Optional[str]:
    """Domain Profile **配置摘要**：Profile + 本路线声明的子协议名，不算入全部文档正文。"""
    if not domain:
        return None
    profile_dir = root / "domain-profiles" / domain
    profile = profile_dir / "PROFILE.md"
    if not profile.is_file():
        return None
    payload = {
        "profile": domain,
        "profile_digest": hashlib.sha256(profile.read_bytes()).hexdigest()[:16],
        "slices": sorted(path.name for path in profile_dir.glob("*.md")
                         if path.name != "PROFILE.md"),
    }
    return _digest(payload)


def _anchor_of(contract: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "core_goal": contract.get("core_goal") or contract.get("primary_anchor"),
        "anchor_role": contract.get("anchor_role"),
        "serves": contract.get("serves"),
        "serves_evidence": contract.get("serves_evidence"),
        "provisional": contract.get("provisional_anchor_rationale") is not None,
        "goal": _short(contract.get("goal") or "", 200),
    }


def _active_mechanisms(state: Dict[str, Any], view: cg.CanonicalView) -> List[Dict[str, Any]]:
    """活跃机制及其**证据资格**。资格取自既有字段，不在这里重新判定。"""
    out: List[Dict[str, Any]] = []
    for hypothesis in state.get("hypotheses") or []:
        if not isinstance(hypothesis, dict):
            continue
        status = hypothesis.get("status")
        if status in ("refuted", "killed", "archived"):
            continue
        support = hypothesis.get("supporting_evidence") or []
        refuting = hypothesis.get("refuting_evidence") or []
        qualified = []
        for ref in list(support)[:4]:
            if not isinstance(ref, str):
                continue
            validity, reason = view.validity_of("evidence", ref)
            qualified.append({"evidence": ref, "validity": validity,
                              "reason": _short(reason, 80)})
        out.append({
            "id": hypothesis.get("id"),
            "status": status,
            "statement": _short(hypothesis.get("statement") or "", 180),
            "falsifier": _short(hypothesis.get("falsifier") or "", 120),
            "supporting_evidence": qualified,
            "refuting_evidence": [ref for ref in refuting if isinstance(ref, str)][:4],
            "novelty_source": _short(hypothesis.get("novelty_source") or "", 100),
        })
    return out


def _unresolved(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """最重要的未解决问题：按 importance 排序，保持 canonical 顺序内的稳定排序。"""
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    items = [item for item in state.get("uncertainties") or []
             if isinstance(item, dict) and item.get("status") not in ("resolved", "closed")]
    items.sort(key=lambda item: rank.get(str(item.get("importance")), 9))
    out = []
    for item in items:
        out.append({
            "id": item.get("id"),
            "importance": item.get("importance"),
            "statement": _short(item.get("statement") or item.get("question") or "", 160),
            "cheapest_discriminating_test": _short(
                item.get("cheapest_discriminating_test") or "", 120),
        })
    return out


def _competing(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for item in state.get("assurance") or []:
        if not isinstance(item, dict):
            continue
        alternative = item.get("alternative")
        if not alternative:
            continue
        out.append({
            "target_claim": item.get("target_claim"),
            "alternative": _short(alternative, 160),
            "discriminating_test": _short(item.get("discriminating_test") or "", 120),
            "kill_condition": _short(item.get("kill_condition") or "", 120),
        })
    return out


def _experiments(state: Dict[str, Any]) -> Dict[str, Any]:
    running, pending, frozen = [], [], []
    for experiment in state.get("experiments") or []:
        if not isinstance(experiment, dict):
            continue
        status = experiment.get("status")
        entry = {
            "id": experiment.get("id"),
            "status": status,
            "question": _short(experiment.get("question") or experiment.get("description") or "", 140),
        }
        if status in ("running", "issued"):
            running.append(entry)
        elif status == "planned":
            pending.append(entry)
        prereg = experiment.get("preregistration")
        if isinstance(prereg, dict) and prereg:
            frozen.append({
                "id": experiment.get("id"),
                "digest": _digest(prereg),
                "criterion": _short(prereg.get("criterion") or "", 120),
                "stop_rule": _short(prereg.get("stop_rule") or "", 100),
            })
    return {"running": running, "pending": pending, "frozen_protocol": frozen}


def _banned_retries(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for item in cg.failure_constraints(state):
        if not isinstance(item, dict):
            continue
        out.append({
            "failure": item.get("failure") or item.get("id"),
            "kind": item.get("kind"),
            "constraint": _short(item.get("constraint") or item.get("why") or "", 160),
        })
    return out


def _claims_under_review(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for claim in state.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        if claim.get("central") or claim.get("status") in (
                "supported", "partially-supported"):
            out.append({
                "id": claim.get("id"),
                "status": claim.get("status"),
                "statement": _short(claim.get("statement") or "", 180),
                "scope": _short(claim.get("scope") or "", 100),
                "supporting_evidence": [ref for ref in (claim.get("supporting_evidence") or [])
                                        if isinstance(ref, str)][:4],
                "refuting_evidence": [ref for ref in (claim.get("refuting_evidence") or [])
                                      if isinstance(ref, str)][:4],
            })
    return out


def _evidence_refs(state: Dict[str, Any], view: cg.CanonicalView) -> List[Dict[str, Any]]:
    """必须审查的证据引用：来源绑定缺失、已失效（stale）或 validity 未知的。"""
    out = []
    for evidence in state.get("evidence") or []:
        if not isinstance(evidence, dict):
            continue
        validity, reason = view.validity_of("evidence", evidence.get("id") or "")
        why = []
        if validity in ("stale", "invalid"):
            why.append(f"validity={validity}")
        if validity == "unknown":
            why.append("validity 无法确认")
        if not evidence.get("source") and not evidence.get("artifact"):
            why.append("无来源绑定")
        if not why:
            continue
        out.append({
            "id": evidence.get("id"),
            "kind": evidence.get("kind"),
            "why": "、".join(why),
            "summary": _short(evidence.get("summary") or evidence.get("statement") or "", 120),
        })
    return out


def _legal_actions(contract: Dict[str, Any], state: Dict[str, Any],
                   authorization: str) -> List[str]:
    """当前**合法**动作。这是 advisory 列表，不是授权。"""
    actions: List[str] = []
    if authorization == "read_only":
        return ["inspect_state", "summarise_findings", "request_authorisation"]
    actions.append("inspect_state")
    if state.get("uncertainties"):
        actions.append("design_discriminating_test")
    if authorization == "execute":
        if any(isinstance(item, dict) and item.get("status") == "planned"
               for item in state.get("experiments") or []):
            actions.append("run_frozen_experiment")
        actions.append("update_state_after_gates")
    if not actions:
        actions.append("inspect_state")
    return actions


def _domain_boundaries(domain: Optional[str], root: Path) -> List[str]:
    if not domain:
        return []
    profile = root / "domain-profiles" / domain / "PROFILE.md"
    if not profile.is_file():
        return []
    text = profile.read_text(encoding="utf-8")
    lines = [line.strip().lstrip("-").strip() for line in text.splitlines()
             if line.strip().startswith("- **")]
    return [_short(line, 120) for line in lines[:8]]


def build(
    state_path: Path,
    *,
    route: Optional[str] = None,
    task: str = "inspect",
    domain: Optional[str] = None,
    authorization: str = "read_only",
    root: Optional[Path] = None,
    budget: int = DEFAULT_RESEARCH_BUDGET,
) -> Dict[str, Any]:
    """从 canonical state 派生一个最小决策包。**只读**，不写任何文件。"""
    root = root or SKILL_ROOT
    if task not in TASK_KINDS:
        return {"status": "FAIL", "error": f"unknown task kind: {task}"}
    state_path = Path(state_path)
    if not state_path.is_file():
        return {"status": "FAIL", "error": f"state not found: {state_path}"}

    state = cg.load_state(state_path)
    view = cg.CanonicalView(state)
    contract = state.get("contract") if isinstance(state.get("contract"), dict) else {}
    decided = state.get("decision") if isinstance(state.get("decision"), dict) else {}

    experiments = _experiments(state)
    packet: Dict[str, Any] = {
        "schema": SCHEMA_PACKET,
        "is_canonical_state": False,
        "regenerable": True,
        "project": contract.get("project") or state.get("project"),
        "route": route or contract.get("route") or cg.route_of(state_path),
        "task": task,
        "authorization": authorization,
        "state_version": state.get("state_version"),
        "canonical_digest": _digest(state),
        "anchor": _anchor_of(contract),
        "constraints": [_short(item, 140) for item in
                        (contract.get("constraints") or [])][:10],
        "out_of_scope": [_short(item, 120) for item in
                         (contract.get("out_of_scope") or [])][:6],
        "active_mechanisms": _active_mechanisms(state, view),
        "unresolved": _unresolved(state),
        "competing_explanations": _competing(state),
        "banned_retries": _banned_retries(state),
        "failed_route_count": len([item for item in state.get("failures") or []
                                   if isinstance(item, dict)]),
        "experiments": experiments,
        "frozen_protocol": experiments["frozen_protocol"],
        "last_decision": {
            "verdict": decided.get("verdict") or decided.get("decision"),
            "rationale": _short(decided.get("rationale") or "", 200),
            "at_state_version": decided.get("at_state_version"),
        } if decided else None,
        "claims_under_review": _claims_under_review(state),
        "evidence_refs": _evidence_refs(state, view),
        "legal_actions": _legal_actions(contract, state, authorization),
        "required_domain_boundaries": _domain_boundaries(domain, root),
        "domain": domain,
    }

    # 绑定：State 一变，这些就必须重新核对
    evidence_digests = {}
    for item in packet["evidence_refs"][:12]:
        ident = item.get("id")
        if ident and view.contains("evidence", ident):
            evidence_digests[ident] = _digest(view.get("evidence", ident))
    packet["binding"] = {
        "state_version": packet["state_version"],
        "canonical_digest": packet["canonical_digest"],
        "evidence_digests": evidence_digests,
        "skill_version": _skill_version(root),
        "domain_digest": _domain_digest(domain, root),
    }
    packet["stale"] = False
    packet["stale_reasons"] = []

    # 预算：先算完整大小，再按任务优先级压缩**可压缩**字段
    full = len(json.dumps(packet, ensure_ascii=False))
    packet["budget"] = {
        "limit": budget,
        "full_chars": full,
        "never_truncate": list(NEVER_TRUNCATE),
        "compressed_fields": [],
        "note": ("超预算时只压缩可压缩字段（列表截断为计数），"
                 "授权、约束、锚点、冻结协议、禁重试路线、领域边界、失效标记永不截断。"),
    }
    if full > budget:
        priority = TASK_PRIORITY.get(task, ())
        compressible = [name for name in
                        ("active_mechanisms", "competing_explanations", "unresolved",
                         "claims_under_review", "evidence_refs", "experiments")
                        if name not in priority]
        for name in compressible:
            value = packet.get(name)
            if isinstance(value, list) and len(value) > 3:
                packet[name] = value[:3]
                packet["budget"]["compressed_fields"].append(name)
            elif isinstance(value, dict):
                trimmed = {}
                for key, item in value.items():
                    trimmed[key] = item[:2] if isinstance(item, list) and len(item) > 2 else item
                packet[name] = trimmed
                packet["budget"]["compressed_fields"].append(name)
            if len(json.dumps(packet, ensure_ascii=False)) <= budget:
                break
    packet["chars"] = len(json.dumps(packet, ensure_ascii=False))
    packet["status"] = "PASS"
    return packet


def verify(packet: Dict[str, Any], state_path: Path, *, root: Optional[Path] = None
           ) -> Dict[str, Any]:
    """核对 Packet 是否已失效。**不**改写 Packet，也**不**清空 state。"""
    root = root or SKILL_ROOT
    state_path = Path(state_path)
    if not state_path.is_file():
        return {"status": "FAIL", "error": f"state not found: {state_path}"}
    if packet.get("schema") != SCHEMA_PACKET:
        return {"status": "FAIL", "error": "not a context packet"}
    state = cg.load_state(state_path)
    binding = packet.get("binding") or {}
    reasons: List[str] = []

    current_version = state.get("state_version")
    if binding.get("state_version") != current_version:
        reasons.append(f"state_version 从 {binding.get('state_version')} 变为 {current_version}")
    if binding.get("canonical_digest") != _digest(state):
        reasons.append("canonical digest 变化")
    view = cg.CanonicalView(state)
    for ident, digest in (binding.get("evidence_digests") or {}).items():
        if not view.contains("evidence", ident):
            reasons.append(f"evidence {ident} 已不存在")
            continue
        if _digest(view.get("evidence", ident)) != digest:
            reasons.append(f"evidence {ident} 内容变化")
    if binding.get("skill_version") != _skill_version(root):
        reasons.append("Skill 协议版本变化")
    if binding.get("domain_digest") != _domain_digest(packet.get("domain"), root):
        reasons.append("Domain Profile 配置变化")

    return {
        "schema": SCHEMA_PACKET,
        "stale": bool(reasons),
        "stale_reasons": reasons,
        "action": ("失效：不得把旧摘要当成新事实，不得清空 Research State，不得重新 Bootstrap。"
                   "走既有 CIE 恢复；必要时精确读取原始证据后重新 build。")
        if reasons else "有效：可以继续使用",
        "status": "PASS",
    }


def render(packet: Dict[str, Any]) -> str:
    if packet.get("status") == "FAIL":
        return f"FAIL: {packet.get('error')}\n"
    lines = [f"# Research Context Packet · {packet.get('route')}", ""]
    lines.append(f"- task: `{packet.get('task')}` / authorization: "
                 f"`{packet.get('authorization')}` / domain: `{packet.get('domain') or '-'}`")
    lines.append(f"- state_version: {packet.get('state_version')} / digest: "
                 f"`{packet.get('canonical_digest')[:24]}…` / chars: {packet.get('chars')}")
    anchor = packet.get("anchor") or {}
    lines.append(f"- anchor: `{anchor.get('core_goal')}` ({anchor.get('anchor_role') or '-'})")
    lines.append("")
    if packet.get("constraints"):
        lines.append("## 约束")
        for item in packet["constraints"]:
            lines.append(f"- {item}")
    if packet.get("unresolved"):
        lines.append("## 最重要的未解决问题")
        for item in packet["unresolved"]:
            lines.append(f"- `{item['id']}` [{item['importance']}] {item['statement']}")
    if packet.get("active_mechanisms"):
        lines.append("## 活跃机制与证据资格")
        for item in packet["active_mechanisms"]:
            lines.append(f"- `{item['id']}` ({item['status']}) {item['statement']}")
            for evidence in item["supporting_evidence"]:
                lines.append(f"  - 支持：`{evidence['evidence']}` validity={evidence['validity']}")
    if packet.get("banned_retries"):
        lines.append("## 禁止等价重试")
        for item in packet["banned_retries"]:
            lines.append(f"- `{item['failure']}`：{item['constraint']}")
    if packet.get("legal_actions"):
        lines.append(f"## 当前合法动作（advisory）\n- " + "、".join(packet["legal_actions"]))
    if packet.get("budget", {}).get("compressed_fields"):
        lines.append(f"\n> 预算压缩字段：{packet['budget']['compressed_fields']}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def selftest(verbose: bool = False) -> Dict[str, Any]:
    checks: List[Tuple[str, bool, str]] = []

    def expect(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    import tempfile
    template = json.loads((SKILL_ROOT / "templates" / "research-state.template.json")
                          .read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "A"
        root.mkdir()
        state_path = root / "research-state.json"
        state_path.write_text(json.dumps(template, ensure_ascii=False, indent=2),
                              encoding="utf-8")

        packet = build(state_path, authorization="read_only", task="continue_method")
        expect("build: 成功生成", packet["status"] == "PASS", str(packet.get("error")))
        expect("build: 明确不是 canonical state", packet["is_canonical_state"] is False)
        expect("build: 可重建", packet["regenerable"] is True)
        expect("build: 绑定 state_version",
               packet["binding"]["state_version"] == template.get("state_version"))
        expect("build: 绑定 canonical digest", bool(packet["binding"]["canonical_digest"]))
        expect("build: 绑定 skill 版本", bool(packet["binding"]["skill_version"]))
        expect("build: 初始未失效", packet["stale"] is False)

        # 只读授权不得给出执行动作
        expect("build: 只读授权不给执行动作",
               "run_frozen_experiment" not in packet["legal_actions"],
               str(packet["legal_actions"]))
        exec_packet = build(state_path, authorization="execute", task="continue_method")
        expect("build: 执行授权才给执行动作",
               "update_state_after_gates" in exec_packet["legal_actions"],
               str(exec_packet["legal_actions"]))

        # 十三项字段齐备
        required_fields = ("project", "route", "state_version", "canonical_digest", "anchor",
                           "authorization", "constraints", "active_mechanisms", "unresolved",
                           "competing_explanations", "banned_retries", "experiments",
                           "last_decision", "legal_actions", "evidence_refs",
                           "required_domain_boundaries")
        missing = [name for name in required_fields if name not in packet]
        expect("build: 十三项必需字段齐备", not missing, str(missing))

        # 未新增第九类对象：state 未被改动
        before = state_path.read_bytes()
        build(state_path, authorization="execute")
        expect("build: 不修改 canonical state", state_path.read_bytes() == before)
        expect("build: 不写任何文件", sorted(p.name for p in root.iterdir())
               == ["research-state.json"], str([p.name for p in root.iterdir()]))

        # 失效检测
        ok = verify(packet, state_path)
        expect("verify: 未变化时有效", ok["stale"] is False, str(ok["stale_reasons"]))
        changed = json.loads(json.dumps(template))
        changed["state_version"] = int(changed.get("state_version") or 0) + 1
        state_path.write_text(json.dumps(changed, ensure_ascii=False, indent=2),
                              encoding="utf-8")
        stale = verify(packet, state_path)
        expect("verify: state_version 变化即失效", stale["stale"] is True,
               str(stale["stale_reasons"]))
        expect("verify: 失效时禁止清空与重新 Bootstrap",
               "不得重新 Bootstrap" in stale["action"], stale["action"])

        # 预算：可压缩字段被压缩，不可压缩字段保留
        tiny = build(state_path, authorization="execute", task="inspect", budget=200)
        expect("build: 预算紧张时不静默截断硬字段",
               all(name in tiny for name in NEVER_TRUNCATE if name != "frozen_protocol"),
               str(tiny.get("budget", {}).get("compressed_fields")))
        expect("build: 预算记录压缩字段",
               isinstance(tiny["budget"]["compressed_fields"], list))

        # 非法任务类型
        expect("build: 未知任务类型被拒",
               build(state_path, task="make_coffee")["status"] == "FAIL")
        expect("build: 缺失 state 被拒",
               build(Path(temp) / "nope.json")["status"] == "FAIL")

        # 领域边界只在声明时出现
        no_domain = build(state_path)
        expect("build: 未声明领域则无领域边界",
               no_domain["required_domain_boundaries"] == [])
        expect("build: 未声明领域则 domain_digest 为空",
               no_domain["binding"]["domain_digest"] is None)

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
    parser = argparse.ArgumentParser(description="Research Context Packet")
    parser.add_argument("command", nargs="?", default=None, choices=[None, "build", "verify"])
    parser.add_argument("--state", default=None)
    parser.add_argument("--route", default=None)
    parser.add_argument("--task", default="inspect", choices=list(TASK_KINDS))
    parser.add_argument("--domain", default=None)
    parser.add_argument("--authorization", default="read_only")
    parser.add_argument("--budget", type=int, default=DEFAULT_RESEARCH_BUDGET)
    parser.add_argument("--packet", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", default=None)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        result = selftest(verbose=True)
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_OK if result["status"] == "PASS" else EXIT_HARD

    root = Path(args.root).resolve() if args.root else SKILL_ROOT

    if args.command == "build":
        if not args.state:
            parser.error("需要 --state")
        packet = build(Path(args.state), route=args.route, task=args.task,
                       domain=args.domain, authorization=args.authorization,
                       root=root, budget=args.budget)
        if packet.get("status") == "FAIL":
            print(packet.get("error"), file=sys.stderr)
            return EXIT_ERROR
        if args.out:
            Path(args.out).write_text(json.dumps(packet, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
        if args.json:
            print(json.dumps(packet, ensure_ascii=False, indent=2))
        else:
            print(render(packet), end="")
        return EXIT_OK

    if args.command == "verify":
        if not args.packet or not args.state:
            parser.error("需要 --packet 与 --state")
        packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
        result = verify(packet, Path(args.state), root=root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return EXIT_ENV if result.get("stale") else EXIT_OK

    parser.print_help()
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
