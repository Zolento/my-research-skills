#!/usr/bin/env python3
"""context_planner.py — 决定**这一轮该读什么**的纯函数式上下文计划器。

它的职责边界
------------
它**不做科研决策**，也不路由意图（那是 `preset_router.py`）。它只回答一个问题：

> 给定入口、选中预设、当前阶段、授权等级与领域激活状态，**必须**加载哪些文档与章节，
> 哪些是条件加载，哪些是深层参考，哪些明确不加载，以及缺了什么就不许往下走。

为什么不是第二套路由
--------------------
入口解析、预设选择、否定守卫全部在 `preset_router.py` 里，本模块**只消费**它的决定
（`entry` / `preset_id` / `execution_scope`）。两者不重叠，也不互相回退。
`plan()` 是纯函数：同样的输入给同样的计划，同样的计划给同样的 `plan_digest`。

`loaded` 与 `referenced` 的区别（本模块存在的理由之一）
-------------------------------------------------------
此前的 `load_preset_context()` 把 `scripts/*.py` 的路径名放在 `loaded_references` 里。
**返回一个路径列表不等于相应规则已进入模型上下文。** 本模块把状态拆成七个值：

=============== ==========================================================
值               含义
=============== ==========================================================
`loaded`         已**实际读取并返回正文**（`execute()` 之后才非空）
`required`       当前任务必须读取；未读取则不得进入执行
`conditional`    满足某个 `when` 才需要；`active` 标明这次是否满足
`referenced`     只给引用路径，**没有**读取正文
`available`      可选深层材料，允许不读
`not_loaded`     本次明确没有读取
`blocked_missing` 必需的上下文缺失 ⇒ 不得继续
=============== ==========================================================

预算与截断
----------
四类预算分开管理（protocol / research / evidence / tool），**不合成一个长度**。
超出预算时**不静默截断**：安全约束、权限边界、冻结条件、会改变本轮决定的关键反例
永远不截断。超预算的结果是 `over_budget: true` 加上 `uncovered` 列表，
并让 `can_proceed` 变假（当未覆盖项属于硬要求时）。

Usage
-----
    python3 scripts/context_planner.py list
    python3 scripts/context_planner.py plan --entry continue-research --preset research-loop
    python3 scripts/context_planner.py plan --preset research-audit --domain mri-reconstruction --json
    python3 scripts/context_planner.py load --preset research-loop          # 真正读盘并填 loaded
    python3 scripts/context_planner.py check                                # 校验 registry 的依赖声明
    python3 scripts/context_planner.py --selftest

Exit codes: 0 pass, 1 argument error, 3 hard violation, 4 environment / blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import section_index as si

SCHEMA_PLAN = "research-idea-pipeline/context-plan@1"
SCHEMA_CONTEXT_DECL = "research-idea-pipeline/context-declarations@1"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_HARD = 3
EXIT_ENV = 4

SKILL_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_NAME = "preset-registry.json"
SHARED_CONTRACT_NAME = "shared-contract.md"
SKILL_DOC_NAME = "SKILL.md"

#: 七个加载状态。顺序即语义优先级。
LOAD_STATES: Tuple[str, ...] = (
    "loaded", "required", "conditional", "referenced",
    "available", "not_loaded", "blocked_missing",
)

#: 四类预算分开算。**不合成一个字符串长度预算** —— 那是把「证据不够」和「协议太长」
#: 混成同一个问题。
BUDGETS: Dict[str, int] = {
    "protocol_chars": 60_000,   # L0 + 契约 + 一个预设 + 必需协议
    "research_chars": 12_000,   # Research Context Packet
    "evidence_chars": 20_000,   # 本轮引用的证据切片
    "tool_chars": 8_000,        # 单次工具返回正文
}

#: 永远不截断的内容类别。超预算时宁可 `can_proceed=false`，也不静默切掉这些。
NEVER_TRUNCATE: Tuple[str, ...] = (
    "安全约束", "权限边界", "冻结条件", "会改变本轮决定的关键反例",
)

#: 阻断态：出现任一即不得进入执行。它们来自既有模块，本模块不重新判定。
BLOCKING_STATES: Tuple[str, ...] = (
    "MIGRATION_REQUIRED",
    "AMBIGUOUS_STORAGE_ROOT",
    "INVALID_STORAGE_ROOT",
    "MAINTENANCE_IN_PROGRESS",
    "HOLD",
)

#: 授权等级 → 允许的动作范围。只用于**报告**，不用于授予权限。
AUTHORIZATION_LEVELS: Tuple[str, ...] = ("read_only", "advisory", "execute")


# ---------------------------------------------------------------------------
# 注册表与领域
# ---------------------------------------------------------------------------

def load_registry(root: Optional[Path] = None) -> Dict[str, Any]:
    root = root or SKILL_ROOT
    return json.loads((root / REGISTRY_NAME).read_text(encoding="utf-8"))


def presets_by_id(registry: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {preset["preset_id"]: preset for preset in registry.get("presets") or []}


def domain_profile_dir(domain: str, root: Optional[Path] = None) -> Path:
    root = root or SKILL_ROOT
    return root / "domain-profiles" / domain


def domain_available(domain: str, root: Optional[Path] = None) -> bool:
    return (domain_profile_dir(domain, root) / "PROFILE.md").is_file()


def _resolve_domain_placeholder(path: str, domain: Optional[str]) -> str:
    """把 `domain-profiles/<profile>/PROFILE.md` 展开成真实路径。"""
    if "<profile>" in path:
        if not domain:
            return path
        return path.replace("<profile>", domain)
    return path


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 计划
# ---------------------------------------------------------------------------

SECTION_SEP = "#"


def split_requirement(rel: str) -> Tuple[str, Optional[str]]:
    """把 `"references/x.md#查询"` 拆成 (路径, 章节查询)。

    **章节级加载**是本轮的核心能力之一：`research-state-policy.md` 是 50K 字符，
    判断「引用完整性」只需要其中一节。整份加载等于让一个 20 行的判断拖进 700 行规范。
    """
    if SECTION_SEP in rel:
        path, _, query = rel.partition(SECTION_SEP)
        return path, (query.strip() or None)
    return rel, None


def section_text(text: str, query: str) -> Tuple[str, List[str]]:
    """按标题文本命中章节，返回 (正文字符串, section_id 列表)。"""
    sections = si.split_sections(text)
    picked = [section for section in sections
              if query.lower() in section["title"].lower()]
    if not picked:
        return "", []
    return "\n".join(section["text"] for section in picked), [s["id"] for s in picked]


def _entry(rel: str, *, layer: str, reason: str, root: Path,
           kind: str = "document") -> Dict[str, Any]:
    path_rel, query = split_requirement(rel)
    path = root / path_rel
    exists = path.is_file()
    full = path.read_text(encoding="utf-8") if exists else ""
    sections: List[str] = []
    text = full
    if exists and query:
        text, sections = section_text(full, query)
        if not sections:
            # 查询没命中任何章节：**不静默降级为整份加载**，而是标记为缺失，
            # 否则「按章节加载」会悄悄退化成「加载全文」。
            exists = False
    return {
        "path": rel,
        "doc": path_rel,
        "section_query": query,
        "sections": sections,
        "kind": kind,
        "layer": layer,
        "reason": reason,
        "exists": exists,
        "chars": len(text),
        "bytes": len(text.encode("utf-8")) if exists else 0,
        "digest": _digest(text) if exists else None,
        "full_chars": len(full),
    }


def plan(
    *,
    entry: str,
    preset_id: Optional[str],
    root: Optional[Path] = None,
    stage: Optional[str] = None,
    authorization: str = "read_only",
    domain: Optional[str] = None,
    state_version: Optional[int] = None,
    blockers: Sequence[str] = (),
    conditional_active: Sequence[str] = (),
    domain_slices: Sequence[str] = (),
    include_deep: bool = False,
) -> Dict[str, Any]:
    """产出这一轮的上下文计划。**纯函数**：不做 I/O 之外的任何副作用，不写盘。

    `include_deep=True` 才会把 `deep_references` 提为 `required`（用于专项审查 / 异常处理）。
    默认 `deep_references` 只进 `available`，因为它们的存在意义就是「允许不读」。
    """
    root = root or SKILL_ROOT
    registry = load_registry(root)
    presets = presets_by_id(registry)

    if authorization not in AUTHORIZATION_LEVELS:
        return {"status": "FAIL", "schema": SCHEMA_PLAN,
                "error": f"unknown authorization level: {authorization}"}

    problems: List[str] = []
    blocked: List[Dict[str, Any]] = []

    # 1) L0 恒在。它不是工具调用，而是 Harness 注入。
    required: List[Dict[str, Any]] = [
        _entry(SKILL_DOC_NAME, layer="L0", reason="L0 常驻核心，每次激活 RLP 都加载",
               root=root),
    ]

    # 2) 选中预设的声明；无预设的入口（start-project）走 entry_context
    context: Dict[str, Any] = {}
    if not preset_id:
        context = (registry.get("entry_context") or {}).get(entry) or {}
        if not context:
            # 该入口的上下文由**预设**决定；没有预设就是还没路由，不是「不需要读」。
            available = [item["preset_id"] for item in registry.get("presets") or []
                         if item.get("entry") == entry]
            problems.append(
                f"NEEDS_PRESET: entry {entry} 需要先选定一个预设"
                + (f"（可选：{', '.join(sorted(available))}）" if available else ""))
        for rel in context.get("required") or []:
            rel = _resolve_domain_placeholder(rel, domain)
            path = root / rel
            probe = _entry(rel, layer="L1", reason=f"{entry} 入口必需", root=root)
            if not probe["exists"]:
                blocked.append({"path": rel, "reason": f"{entry} 声明为必需但文件或章节不存在"})
                continue
            required.append(probe)
    if preset_id:
        preset = presets.get(preset_id)
        if preset is None:
            problems.append(f"unknown preset: {preset_id}")
        else:
            if preset.get("entry") != entry:
                problems.append(
                    f"preset {preset_id} belongs to entry {preset['entry']}, not {entry}")
            context = preset.get("context") or {}
            if not context:
                problems.append(f"preset {preset_id} declares no context block")
            protocol = f"presets/{preset_id}.md"
            if not (root / protocol).is_file():
                blocked.append({"path": protocol, "reason": "预设正文缺失"})
            else:
                required.append(_entry(protocol, layer="L1",
                                      reason="选中的唯一一个 Preset 正文", root=root))
            for rel in context.get("required") or []:
                rel = _resolve_domain_placeholder(rel, domain)
                if rel == protocol:
                    continue
                path = root / rel
                probe = _entry(rel, layer="L1",
                               reason=f"{preset_id} 声明为必需", root=root)
                if not probe["exists"]:
                    blocked.append({"path": rel, "reason": "预设声明为必需但文件或章节不存在"})
                    continue
                required.append(probe)

    # 3) 条件加载：只有 when 命中才进 required
    active_names = set(conditional_active)
    conditional: List[Dict[str, Any]] = []
    for cond in context.get("conditional") or []:
        when = cond.get("when")
        is_active = when in active_names
        items = []
        for rel in cond.get("load") or []:
            rel = _resolve_domain_placeholder(rel, domain)
            path = root / rel
            item = _entry(rel, layer="L1", reason=f"条件加载：{when}", root=root)
            item["active"] = is_active
            if is_active and not item["exists"]:
                blocked.append({"path": rel, "reason": f"条件 {when} 命中但文件或章节缺失"})
            if is_active and item["exists"]:
                required.append(dict(item))
            items.append(item)
        conditional.append({"when": when, "active": is_active, "items": items})

    # 4) 领域扩展：显式激活才加载，且只加载 PROFILE + 当前任务那一份
    domain_block: Dict[str, Any] = {"declared": bool(domain), "profile": domain}
    if domain:
        profile_dir = domain_profile_dir(domain, root)
        if not (profile_dir / "PROFILE.md").is_file():
            domain_block["available"] = False
            blocked.append({"path": f"domain-profiles/{domain}/PROFILE.md",
                            "reason": "声明了领域但 Profile 不存在"})
        else:
            domain_block["available"] = True
            domain_block["slices"] = sorted(
                str(path.relative_to(root)) for path in profile_dir.glob("*.md")
                if path.name != "PROFILE.md")
            required.append(_entry(f"domain-profiles/{domain}/PROFILE.md", layer="L1",
                                   reason=f"领域 {domain} 已激活", root=root))
            # 只加载当前任务用到的那一份子协议，不加载全部领域文档。
            for name in domain_slices:
                rel = f"domain-profiles/{domain}/{name}.md"
                probe = _entry(rel, layer="L1", reason=f"领域切片：{name}", root=root)
                if not probe["exists"]:
                    blocked.append({"path": rel,
                                    "reason": f"请求的领域切片不存在：{name}"})
                    continue
                required.append(probe)
                domain_block.setdefault("loaded_slices", []).append(name)

    # 5) 深层参考：默认只算 available
    deep: List[Dict[str, Any]] = []
    for rel in context.get("deep_references") or []:
        rel = _resolve_domain_placeholder(rel, domain)
        item = _entry(rel, layer="L2", reason="深层参考，允许不读", root=root)
        if include_deep and item["exists"]:
            item["layer"] = "L1"
            item["reason"] = "本轮显式要求深层参考"
            required.append(dict(item))
        deep.append(item)
    available = [item for item in deep if item["layer"] == "L2"]

    # 6) 明确不加载
    not_loaded: List[Dict[str, Any]] = []
    loaded_paths = {item["path"] for item in required}
    deep_paths = {item["path"] for item in deep}
    seen: set = set()
    for other in sorted(presets):
        if other == preset_id:
            continue
        rel = f"presets/{other}.md"
        if rel in seen:
            continue
        seen.add(rel)
        not_loaded.append({"path": rel, "reason": "未选中的预设"})
    for path in si.indexed_paths(root):
        if path in loaded_paths or path in deep_paths or path in seen:
            continue
        seen.add(path)
        not_loaded.append({"path": path, "reason": "本次任务不需要"})

    # 7) 阻断态
    hits = [state for state in blockers if state in BLOCKING_STATES]
    for state in hits:
        blocked.append({"path": "-", "reason": f"既有模块报告阻断态：{state}"})

    # 8) 预算：分开计，不静默截断
    protocol_chars = sum(item["chars"] for item in required if item["layer"] in ("L0", "L1"))
    over_protocol = protocol_chars > BUDGETS["protocol_chars"]
    uncovered: List[str] = []
    if over_protocol:
        # 超预算时**不**降级任何 required 项：列出未覆盖内容并要求进一步加载或审查。
        uncovered = [item["path"] for item in required]
    budget = {
        "limits": dict(BUDGETS),
        "used": {
            "protocol_chars": protocol_chars,
            "research_chars": 0,
            "evidence_chars": 0,
            "tool_chars": 0,
        },
        "over_budget": over_protocol,
        "uncovered": uncovered,
        "never_truncate": list(NEVER_TRUNCATE),
        "policy": ("超预算不静默截断。安全约束、权限边界、冻结条件与关键反例永不截断；"
                   "未覆盖项列入 uncovered，并由调用方选择继续加载或先做审查。"),
    }

    can_proceed = not blocked and not problems and not (over_protocol and uncovered)

    core = {
        "schema": SCHEMA_PLAN,
        "skill_version": _skill_version(root),
        "entry": entry,
        "preset_id": preset_id,
        "stage": stage,
        "authorization": authorization,
        "domain": domain,
        "domain_block": domain_block,
        "state_version": state_version,
        "blockers": list(blockers),
        "required": required,
        "conditional": conditional,
        "deep_references": deep,
        "available": available,
        "loaded": [],
        "referenced": [item["path"] for item in deep],
        "not_loaded": not_loaded,
        "blocked_missing": blocked,
        "budget": budget,
        "can_proceed": can_proceed,
        "problems": problems,
        "state_semantics": {
            "loaded": "已实际读取并返回正文（execute 之后才非空）",
            "required": "当前任务必须读取",
            "conditional": "满足 when 才需要",
            "referenced": "只给路径，未读正文",
            "available": "可选深层材料",
            "not_loaded": "本次明确未读",
            "blocked_missing": "必需上下文缺失，不得继续",
        },
        "gates_remaining": _gates_for(preset_id or entry, stage),
    }
    core["plan_digest"] = _digest(json.dumps(core, ensure_ascii=False, sort_keys=True))
    core["status"] = "PASS" if can_proceed else "BLOCKED"
    return core


def _skill_version(root: Path) -> Optional[str]:
    text = (root / SKILL_DOC_NAME).read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("version:"):
            return stripped.split(":", 1)[1].strip().strip('"').strip("'")
    return None


#: 预设 → 仍需执行器负责的门禁。**上下文精简不改变这些门禁。**
GATES: Dict[str, Tuple[str, ...]] = {
    "start-project": ("rlp_paths.py", "state_check.py"),
    "research-loop": ("state_check.py", "experiment_execute.py", "evidence_outcome.py"),
    "paradigm-escape": ("structure gate: state_check.py",),
    "research-audit": ("structural_equivalence_check.py", "state_check.py"),
    "evidence-conflict-repair": ("evidence_outcome.py", "state_check.py"),
    "experiment-failure-recovery": ("experiment_execute.py",),
    "stagnation-breaker": ("insight_to_method.py", "state_check.py"),
    "memory-consolidation": ("cognition.py",),
    "strategy-evolution": ("policy_evolution.py",),
    "discovery-replay": ("research_replay.py",),
    "research-recovery": ("rlp_paths.py", "state_check.py"),
    "context-drift-recovery": ("cognition.py",),
    "loop-health-check": ("operational_reconcile.py",),
    "research-review": ("state_check.py",),
    "scientific-replanning": ("state_check.py",),
    "resource-recovery": ("operational_reconcile.py",),
    "hypothesis-rebalance": ("state_check.py",),
}


def _gates_for(preset_id: Optional[str], stage: Optional[str]) -> List[str]:
    gates = list(GATES.get(preset_id or "", ()))
    if stage:
        gates.append(f"stage gate: {stage}")
    return gates


# ---------------------------------------------------------------------------
# 真正读盘：loaded 才有内容
# ---------------------------------------------------------------------------

def execute(plan_payload: Dict[str, Any], root: Optional[Path] = None,
            budget_key: str = "protocol_chars") -> Dict[str, Any]:
    """读 `required` 里的正文，填 `loaded`。

    这是 `loaded` 与 `referenced` 分开的地方：只有真的读过的文件才会出现在 `loaded` 里，
    并带上正文与 digest。缺任何一个 required 项都会把 `can_proceed` 置假。
    """
    root = root or SKILL_ROOT
    payload = json.loads(json.dumps(plan_payload))  # 深拷贝，纯函数式
    loaded: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []
    total = 0
    for item in payload.get("required") or []:
        path = root / item["path"]
        if not path.is_file():
            missing.append({"path": item["path"], "reason": "required 缺失"})
            continue
        full = path.read_text(encoding="utf-8")
        query = item.get("section_query")
        text = full
        if query:
            text, sections = section_text(full, query)
            if not sections:
                missing.append({"path": item["path"],
                                "reason": f"section query 未命中：{query}"})
                continue
        total += len(text)
        loaded.append({"path": item["path"], "layer": item["layer"],
                       "chars": len(text), "digest": _digest(text),
                       "sections": item.get("sections") or [], "text": text})
    payload["loaded"] = loaded
    payload["loaded_chars"] = total
    payload["loaded_paths"] = [item["path"] for item in loaded]
    payload["blocked_missing"] = (payload.get("blocked_missing") or []) + missing
    if missing:
        payload["can_proceed"] = False
        payload["status"] = "BLOCKED"
    used = dict(payload.get("budget", {}).get("used") or {})
    used[budget_key] = total
    payload.setdefault("budget", {})["used"] = used
    return payload


# ---------------------------------------------------------------------------
# 校验 registry 的依赖声明
# ---------------------------------------------------------------------------

def check(root: Optional[Path] = None) -> Tuple[bool, List[str]]:
    """校验 `preset-registry.json` 的 `context` 块。返回 (ok, problems)。"""
    root = root or SKILL_ROOT
    problems: List[str] = []
    registry = load_registry(root)
    if registry.get("context_schema") != SCHEMA_CONTEXT_DECL:
        problems.append(f"registry.context_schema 不是 {SCHEMA_CONTEXT_DECL}")
    presets = presets_by_id(registry)
    if not presets:
        problems.append("registry 没有任何预设")

    for preset_id, preset in sorted(presets.items()):
        context = preset.get("context")
        if not isinstance(context, dict):
            problems.append(f"{preset_id}: 缺少 context 块")
            continue
        required = context.get("required") or []
        if SHARED_CONTRACT_NAME not in required:
            problems.append(f"{preset_id}: required 未包含 {SHARED_CONTRACT_NAME}")
        if f"presets/{preset_id}.md" not in required:
            problems.append(f"{preset_id}: required 未包含自身协议正文")
        for other in presets:
            if other != preset_id and f"presets/{other}.md" in required:
                problems.append(f"{preset_id}: required 里出现了别的预设 {other}")
        for rel in required + list(context.get("deep_references") or []):
            # 领域占位符在 check 阶段不展开：展开需要真实的领域名，不是预设名。
            if "<profile>" in rel:
                continue
            probe = _entry(rel, layer="L1", reason="check", root=root)
            if not probe["exists"]:
                why = ("章节查询未命中" if probe.get("section_query")
                       else "文件不存在")
                problems.append(f"{preset_id}: 声明的路径{why} {rel}")
        for rel in required:
            if rel in (context.get("deep_references") or []):
                problems.append(f"{preset_id}: {rel} 同时是 required 与 deep_reference")
        for cond in context.get("conditional") or []:
            if not cond.get("when"):
                problems.append(f"{preset_id}: conditional 缺少 when")
            if not cond.get("load"):
                problems.append(f"{preset_id}: conditional 缺少 load")
            for rel in cond.get("load") or []:
                if "<profile>" in rel:
                    continue
                probe = _entry(rel, layer="L1", reason="check", root=root)
                if not probe["exists"]:
                    problems.append(f"{preset_id}: conditional {cond['when']} 的路径无效 {rel}")
        if not context.get("forbidden"):
            problems.append(f"{preset_id}: forbidden 为空（等于没声明边界）")
        for domain in context.get("domain_extensions") or []:
            if not domain_available(domain, root):
                problems.append(f"{preset_id}: 声明了不存在的领域扩展 {domain}")

    if not problems:
        # 每个预设都必须能规划成功
        for preset_id, preset in sorted(presets.items()):
            payload = plan(entry=preset.get("entry") or "", preset_id=preset_id, root=root,
                           authorization="read_only")
            if payload.get("status") != "PASS":
                problems.append(f"{preset_id}: plan 未通过 —— "
                                f"{payload.get('problems') or payload.get('blocked_missing')}")
    return (not problems), problems


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def render_markdown(payload: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# Context Plan · `{payload.get('preset_id')}`")
    lines.append("")
    lines.append(f"- schema: `{payload.get('schema')}`")
    lines.append(f"- entry: `{payload.get('entry')}` / authorization: "
                 f"`{payload.get('authorization')}` / domain: `{payload.get('domain') or '-'}`")
    lines.append(f"- skill_version: `{payload.get('skill_version')}` / "
                 f"plan_digest: `{payload.get('plan_digest')}`")
    lines.append(f"- can_proceed: **{payload.get('can_proceed')}** / status: "
                 f"`{payload.get('status')}`")
    lines.append("")
    lines.append("| 状态 | 路径 | 层 | 字符 | 原因 |")
    lines.append("|---|---|---|---|---|")
    for item in payload.get("required") or []:
        status = "loaded" if item["path"] in (payload.get("loaded_paths") or []) else "required"
        scope = ""
        if item.get("sections"):
            scope = f" §{','.join(item['sections'])}"
        lines.append(f"| {status} | `{item['path']}`{scope} | {item['layer']} "
                     f"| {item['chars']} | {item['reason']} |")
    for cond in payload.get("conditional") or []:
        for item in cond["items"]:
            mark = "conditional(active)" if cond["active"] else "conditional"
            lines.append(f"| {mark} | `{item['path']}` | L1 | {item['chars']} "
                         f"| {cond['when']} |")
    for item in payload.get("available") or []:
        lines.append(f"| available | `{item['path']}` | L2 | {item['chars']} | 允许不读 |")
    lines.append(f"| not_loaded | （{len(payload.get('not_loaded') or [])} 项） | — | — "
                 f"| 本次不需要 |")
    if payload.get("blocked_missing"):
        lines.append("")
        lines.append("## 阻断")
        for item in payload["blocked_missing"]:
            lines.append(f"- `{item['path']}` —— {item['reason']}")
    budget = payload.get("budget") or {}
    lines.append("")
    lines.append(f"预算：protocol {budget.get('used', {}).get('protocol_chars', 0)} / "
                 f"{budget.get('limits', {}).get('protocol_chars')} chars，"
                 f"over_budget={budget.get('over_budget')}")
    lines.append(f"仍需执行器负责的门禁：{payload.get('gates_remaining')}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def selftest(verbose: bool = False) -> Dict[str, Any]:
    checks: List[Tuple[str, bool, str]] = []

    def expect(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    root = SKILL_ROOT

    ok, problems = check(root)
    expect("check: registry 依赖声明合法", ok, "；".join(problems[:3]))

    base = plan(entry="continue-research", preset_id="research-loop", root=root,
                authorization="execute")
    expect("plan: 正常计划可继续", base["status"] == "PASS", str(base.get("problems")))
    expect("plan: L0 恒在", base["required"][0]["path"] == SKILL_DOC_NAME)
    expect("plan: 只含一个预设正文",
          sum(1 for item in base["required"] if item["path"].startswith("presets/")) == 1)
    expect("plan: not_loaded 覆盖其余 15 个预设",
          sum(1 for item in base["not_loaded"] if item["path"].startswith("presets/")) == 15)
    expect("plan: loaded 在 execute 之前为空", base["loaded"] == [])
    expect("plan: referenced 只给路径",
          all(isinstance(item, str) for item in base["referenced"]))

    # 纯函数：同输入同 digest
    again = plan(entry="continue-research", preset_id="research-loop", root=root,
                 authorization="execute")
    expect("plan: 同输入同 plan_digest", base["plan_digest"] == again["plan_digest"])

    # 条件加载：未命中不进 required
    cond_paths = [item["path"] for cond in base["conditional"] for item in cond["items"]]
    req_paths = [item["path"] for item in base["required"]]
    expect("plan: 条件项未命中时不进 required",
          all(path not in req_paths for path in cond_paths), str(cond_paths))

    # 条件命中后进 required
    active = plan(entry="continue-research", preset_id="research-loop", root=root,
                  authorization="execute", conditional_active=["method_synthesis"])
    active_req = [item["path"] for item in active["required"]]
    expect("plan: 条件命中后进 required",
          any("insight-to-method-policy" in path for path in active_req), str(active_req))
    expect("plan: 条件命中后 digest 变化",
          active["plan_digest"] != base["plan_digest"])

    # 领域：显式激活才加载
    dom = plan(entry="continue-research", preset_id="research-loop", root=root,
               authorization="execute", domain="mri-reconstruction",
               conditional_active=["method_synthesis"])
    dom_req = [item["path"] for item in dom["required"]]
    expect("plan: 领域激活后加载 PROFILE",
          "domain-profiles/mri-reconstruction/PROFILE.md" in dom_req, str(dom_req))
    no_dom = plan(entry="continue-research", preset_id="research-loop", root=root,
                  authorization="execute")
    expect("plan: 未声明领域则不加载领域文档",
          not any("domain-profiles" in item["path"] for item in no_dom["required"]))
    expect("plan: 领域只加载 PROFILE 与切片，不加载全部",
          sum(1 for path in dom_req if path.startswith("domain-profiles/")) == 1, str(dom_req))

    # 阻断态
    blocked = plan(entry="continue-research", preset_id="research-loop", root=root,
                   authorization="execute", blockers=["MIGRATION_REQUIRED"])
    expect("plan: 阻断态使 can_proceed 变假", blocked["can_proceed"] is False)
    unknown = plan(entry="continue-research", preset_id="research-loop", root=root,
                   authorization="execute", blockers=["SOMETHING_ELSE"])
    expect("plan: 未知阻断态不误判", unknown["can_proceed"] is True)

    # 授权等级
    expect("plan: 非法授权等级被拒",
          plan(entry="a", preset_id="research-loop", root=root,
               authorization="root")["status"] == "FAIL")

    # 预设与入口不匹配
    mismatch = plan(entry="audit", preset_id="research-loop", root=root)
    expect("plan: 预设与入口不匹配被报出", mismatch["problems"] != [],
          str(mismatch["problems"]))

    # loaded 只在 execute 之后出现，且缺文件即阻断
    loaded = execute(base, root=root)
    expect("execute: loaded 有正文", all(item.get("text") for item in loaded["loaded"]))
    expect("execute: loaded_paths 与 required 一致",
          set(loaded["loaded_paths"]) >= {
              item["path"] for item in base["required"] if item["exists"]})
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        broken = json.loads(json.dumps(base))
        broken["required"].append({"path": "references/does-not-exist.md", "layer": "L1",
                                   "kind": "document", "reason": "probe", "exists": False,
                                   "chars": 0, "bytes": 0, "digest": None})
        broken["loaded_paths"] = []
        after = execute(broken, root=root)
        expect("execute: required 缺失即阻断", after["can_proceed"] is False)
        expect("execute: 缺失项进 blocked_missing",
              any("does-not-exist" in item["path"] for item in after["blocked_missing"]))

    # 预算：超预算不静默截断，而是列 uncovered
    tight = plan(entry="continue-research", preset_id="research-loop", root=root,
                 authorization="execute")
    saved = BUDGETS["protocol_chars"]
    try:
        BUDGETS["protocol_chars"] = 10
        tight2 = plan(entry="continue-research", preset_id="research-loop", root=root,
                      authorization="execute")
        expect("plan: 超预算标记 over_budget", tight2["budget"]["over_budget"] is True)
        expect("plan: 超预算列出 uncovered 而非截断",
              len(tight2["budget"]["uncovered"]) > 0)
        expect("plan: 超预算时 required 一项不少",
              len(tight2["required"]) == len(tight["required"]))
        expect("plan: 永不截断类别已声明",
              "冻结条件" in tight2["budget"]["never_truncate"])
    finally:
        BUDGETS["protocol_chars"] = saved

    # 深层参考默认不读
    deep = plan(entry="audit", preset_id="research-audit", root=root, authorization="read_only")
    expect("plan: 深层参考默认只进 available",
          all(item["layer"] == "L2" for item in deep["available"]), str(len(deep["available"])))
    deep_on = plan(entry="audit", preset_id="research-audit", root=root,
                   authorization="read_only", include_deep=True)
    expect("plan: 显式要求时深层参考进 required",
          len(deep_on["required"]) > len(deep["required"]))

    # 门禁仍然存在（上下文精简不取消门禁）
    expect("plan: 门禁清单非空", len(base["gates_remaining"]) > 0, str(base["gates_remaining"]))

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
    parser = argparse.ArgumentParser(description="RLP 上下文计划器（决定这一轮读什么）")
    parser.add_argument("command", nargs="?", default=None,
                        choices=[None, "list", "plan", "load", "check"])
    parser.add_argument("--entry", default=None)
    parser.add_argument("--preset", default=None)
    parser.add_argument("--stage", default=None)
    parser.add_argument("--authorization", default="read_only")
    parser.add_argument("--domain", default=None)
    parser.add_argument("--state-version", type=int, default=None)
    parser.add_argument("--blocker", action="append", default=None)
    parser.add_argument("--conditional", action="append", default=None)
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", default=None)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        result = selftest(verbose=True)
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_OK if result["status"] == "PASS" else EXIT_HARD

    root = Path(args.root).resolve() if args.root else SKILL_ROOT

    if args.command == "list":
        registry = load_registry(root)
        for preset in registry["presets"]:
            ctx = preset.get("context") or {}
            print(f"{preset['preset_id']:<28} {preset['entry']:<18} "
                  f"required={len(ctx.get('required') or [])} "
                  f"conditional={len(ctx.get('conditional') or [])} "
                  f"deep={len(ctx.get('deep_references') or [])}")
        return EXIT_OK

    if args.command == "check":
        ok, problems = check(root)
        if ok:
            print("ok   registry context 声明合法，16 个预设全部可规划")
            return EXIT_OK
        for problem in problems:
            print("FAIL " + problem)
        return EXIT_HARD

    if args.command in ("plan", "load"):
        if not args.preset and not args.entry:
            parser.error("需要 --preset 或 --entry")
        registry = load_registry(root)
        preset = presets_by_id(registry).get(args.preset) if args.preset else None
        if args.preset and preset is None:
            print(f"unknown preset: {args.preset}", file=sys.stderr)
            return EXIT_ERROR
        entry = args.entry or (preset or {}).get("entry")
        payload = plan(entry=entry, preset_id=args.preset, root=root, stage=args.stage,
                       authorization=args.authorization, domain=args.domain,
                       state_version=args.state_version, blockers=args.blocker or (),
                       conditional_active=args.conditional or (), include_deep=args.deep)
        if payload.get("status") == "FAIL":
            print(payload.get("error"), file=sys.stderr)
            return EXIT_ERROR
        needs = [item for item in payload.get("problems") or []
                 if item.startswith("NEEDS_PRESET")]
        if needs:
            print(needs[0].split(": ", 1)[1], file=sys.stderr)
            return EXIT_ERROR
        if args.command == "load":
            payload = execute(payload, root=root)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(render_markdown(payload), end="")
        return EXIT_OK if payload.get("can_proceed") else EXIT_ENV

    parser.print_help()
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
