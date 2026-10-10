#!/usr/bin/env python3
"""policy_transfer.py — 三层记忆分离与策略迁移闸门（Skill-RSI Phase 7，只读）。

为什么需要本模块
----------------
Skill-RSI 有三类记忆，它们的权威来源、失效方式和可信度**互不相同**：

```
scientific_memory    canonical research-state.json + cognition/index.json（科学事实）
decision_experience  <route>/decision-trajectory.jsonl（决策经验，可过期）
policy_memory        <route>/policy/ 候选（探索性策略，可迁移、可回滚）
```

把它们混在一起会立刻产生三类伪科学：一条策略被当成“已证事实”、一次未观测的
历史决策被当成“经验证据”、一个被否证的机制被换个措辞重新提出。本模块是**只读**
的机械闸门：它只做分离、迁移判定、过期检测、负向知识保护和有损压缩拒绝。

三层分离
--------
`memory_layers()` 以 canonical 字段构造 `scientific_memory`，以
`decision_trajectory.rebuild_trajectories()` 构造 `decision_experience`，以调用方传入
的候选字典构造 `policy_memory`。科学事实永远不出现在策略层，策略/决策记录永远不
写入科学层。规则 `PT1`（层次混装）与 `PT2`（策略声称否证/支持科学主张）是硬规则。

策略候选字典形状（供 `policy_evolution.py` 等消费者使用；本模块只读）
------------------------------------------------------------------
```
{
  "id": "POL-...",
  "scope": {"kind": "global"|"cross_project"|"project"|"route"|"task"|"structure",
            "projects": [...], "structures": [...]},
  "applicable_conditions": [ {"field": "contract.primary_anchor", "op": "eq", "value": "..."} ],
  "required_tools": ["..."],
  "validation_protocol": {"protocol": "...", "min_tier": "T2"},
  "evidence_level": "independent"|"multi_project"|"single_project"|"none",
  "independent_evaluation_refs": ["..."],
  "counterexamples": [ {"id": "...", "operators": ["reframe"], "islands": ["P1"]} ],
  "mechanism": {"id": "H1", "statement": "..."},
  "menu": "replace_problem_representation",
}
```
未声明的键按 fail-closed 处理：无法证明条件成立即阻塞。

设计规则：fail-closed、无 LLM、无网络、除打印外不写任何东西。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import cognition as cg
import decision_trajectory as dt
import strategy_memory as sm

SCHEMA_TRANSFER = "research-idea-pipeline/policy-transfer@1"
MEMORY_LAYERS: Tuple[str, ...] = ("scientific_memory", "decision_experience", "policy_memory")

EXIT_OK = cg.EXIT_OK
EXIT_ERROR = cg.EXIT_ERROR
EXIT_HARD = cg.EXIT_HARD
EXIT_ENV = cg.EXIT_ENV

#: 结构相似度阈值。只有 score >= threshold 且至少共享一个“声明结构 token”才算匹配。
SIMILARITY_THRESHOLD = 0.5

#: 合法 scope 种类。缺少 kind 的 scope 一律 PT3。
SCOPE_KINDS: Tuple[str, ...] = (
    "global", "cross_project", "project", "route", "task", "structure",
)

#: 需要跨项目历史证据的 scope（PT9）。
BROAD_SCOPES: Tuple[str, ...] = ("global", "cross_project")

#: 历史成功证据等级；低于 scope 主张即 PT9。
EVIDENCE_RANKS: Dict[str, int] = {
    "none": 0, "anecdotal": 0, "speculative": 0, "hypothesis": 0,
    "single_project": 1, "project": 1, "local": 1,
    "multi_project": 2, "cross_project": 2, "structure": 2,
    "independent": 3, "replicated": 3, "global": 3,
}
WEAK_EVIDENCE_LEVELS: Tuple[str, ...] = (
    "none", "anecdotal", "speculative", "hypothesis", "single_project", "one_project",
)

#: 压缩报告里绝对不可丢弃的记忆种类。
NON_DROPPABLE_KINDS: Tuple[str, ...] = ("evidence", "stop_rule", "scientific_fact")
#: 压缩报告允许丢弃的记忆种类（但必须报告丢弃了哪些）。
DROPPABLE_KINDS: Tuple[str, ...] = ("decision_experience", "policy")
ALL_KINDS: Tuple[str, ...] = NON_DROPPABLE_KINDS + DROPPABLE_KINDS

#: 科学层对应的 canonical 数组（cognition REF_KEYS 的子集语义）。
SCIENTIFIC_SECTIONS: Tuple[str, ...] = cg.REF_KEYS

#: 只读检测：canonical state 中出现这些“策略/经验层”段即为 PT1。
POLICY_SECTIONS: Tuple[str, ...] = (
    "policy_memory", "policy_candidates", "policies", "policy",
    "decision_experience", "decision_trajectory", "decision_trajectories",
    "trajectories", "policy_layer",
)

#: 一条策略记录若声明自己是下列 kind，则它承载的是科学事实而非策略（PT1）。
SCIENTIFIC_KINDS: Tuple[str, ...] = (
    "evidence", "stop_rule", "scientific_fact", "claim", "scientific_claim", "fact",
)

#: 策略声称对科学主张产生“否证/支持”效果的键（PT2）。
SCIENTIFIC_EFFECT_KEYS: Tuple[str, ...] = (
    "refutes", "supports", "contradicts", "proves", "disproves", "overturns",
    "establishes", "scientific_claim", "claim_status", "scientific_effect",
)

#: 结构签名五键（state_check.STRUCTURAL_SIGNATURE_KEYS）。
STRUCTURAL_SIGNATURE_KEYS: Tuple[str, ...] = (
    "assumption_distance", "formulation_distance", "representation_distance",
    "theory_lens_distance", "mechanism_distance",
)

#: 证据契约中可比对的 validation/verification 键。
PROTOCOL_KEYS: Tuple[str, ...] = (
    "kind", "protocol", "protocol_id", "validation", "verification",
    "evidence_protocol", "standard", "tier", "min_tier", "level",
    "require_independent_replication",
)

#: 声明“独立评价”的键名。
INDEPENDENT_EVIDENCE_KEYS: Tuple[str, ...] = (
    "independent_evaluation_refs", "independent_evaluations", "independent_evaluation",
    "independent_refs", "evaluation_refs",
)

#: 声明历史证据所属项目的键名（不含 scope.projects —— 那是适用范围，不是证据）。
EVIDENCE_PROJECT_KEYS: Tuple[str, ...] = (
    "evidence_projects", "source_projects", "basis_projects", "projects",
)

_MISSING = object()


# ---------------------------------------------------------------------------
# 诊断
# ---------------------------------------------------------------------------

def _diag(rule: str, path: str, message: str) -> cg.Diagnostic:
    return cg.Diagnostic(rule, path, message)


def _dedupe(diagnostics: Iterable[cg.Diagnostic]) -> List[cg.Diagnostic]:
    return cg._dedupe(diagnostics)


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _as_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _scalar_token(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return value
    return cg.canonical_json(value)


def _norm_statement(value: Any) -> str:
    text = _as_text(value).lower()
    return re.sub(r"\s+", " ", text)


# ---------------------------------------------------------------------------
# 三层记忆分离
# ---------------------------------------------------------------------------

def _scientific_layer(state: Dict[str, Any]) -> Dict[str, Any]:
    """只从 canonical 字段读取。策略、决策经验永远不进入这一层。"""

    def pick(key: str, fields: Sequence[str]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for entry in _as_list(state.get(key)):
            if not isinstance(entry, dict):
                continue
            item: Dict[str, Any] = {}
            for field in fields:
                if field in entry:
                    item[field] = entry.get(field)
            out.append(item)
        out.sort(key=lambda item: str(item.get("id", "")))
        return out

    projection = {
        "claims": pick("claims", ("id", "status")),
        "evidence": pick("evidence", ("id", "verification_tier", "epistemic_status")),
        "assumptions": pick("assumptions", ("id", "status")),
        "hypotheses": pick("hypotheses", ("id", "status", "operator", "island")),
        "experiments": pick("experiments", ("id", "status")),
        "literature": pick("literature", ("id", "relation")),
        "failures": pick("failures", ("id", "kind")),
        "uncertainties": pick("uncertainties", ("id", "status")),
    }
    return {
        "layer": "scientific_memory",
        "source": "canonical_state",
        "state_version": state.get("state_version"),
        "digest": cg.digest_of(projection),
        **projection,
    }


def _experience_layer(trajectory_path: Optional[Path]
                      ) -> Tuple[Dict[str, Any], List[cg.Diagnostic]]:
    if trajectory_path is None:
        return {"layer": "decision_experience", "source": "decision_trajectory",
                "trajectory_path": None, "count": 0, "trajectories": [],
                "supported": [], "pending": [], "chain_ok": True,
                "chain_diagnostics": []}, []
    path = Path(trajectory_path)
    try:
        links, chain_diagnostics = dt.load_records(path, tolerant=True)
    except dt.TrajectoryError as exc:  # tolerant=True 正常不抛；保险地 fail-closed
        links, chain_diagnostics = [], [_diag("DT0", str(path), str(exc))]
    views = dt.rebuild_trajectories(links)
    return {
        "layer": "decision_experience",
        "source": "decision_trajectory",
        "trajectory_path": str(path),
        "count": len(views),
        "trajectories": sorted(views),
        "supported": dt.support_ids(links),
        "pending": dt.pending_outcomes(links),
        # 容错读取会把断裂的哈希链/seq 降级为诊断；这里必须把它暴露出来，
        # 否则任意 JSONL 都会被当成“已验证的决策经验”（provenance fail-open）。
        "chain_ok": not chain_diagnostics,
        "chain_diagnostics": [item.as_dict() for item in chain_diagnostics],
    }, chain_diagnostics


def _policy_layer(policy_records: Sequence[Any]) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []
    for record in policy_records:
        if not isinstance(record, dict):
            continue
        scope = record.get("scope")
        kind = scope.get("kind") if isinstance(scope, dict) else scope
        candidates.append({
            "id": record.get("id"),
            "scope_kind": kind if isinstance(kind, str) else None,
            "status": record.get("status"),
            "layer": "policy_memory",
        })
    candidates.sort(key=lambda item: str(item.get("id", "")))
    return {
        "layer": "policy_memory",
        "source": "policy_candidates",
        "count": len(candidates),
        "candidates": candidates,
    }


def _policy_mixing_diagnostics(policy: Any, path: str) -> List[cg.Diagnostic]:
    """PT1/PT2：一条策略候选不得承载科学记忆，也不得对科学主张下断言。"""
    diagnostics: List[cg.Diagnostic] = []
    if not isinstance(policy, dict):
        return [_diag("PT1", path, "策略候选必须是对象；非对象无法证明其属于策略层")]
    layer = policy.get("layer") or policy.get("_layer") or policy.get("memory_layer")
    if isinstance(layer, str) and layer and layer != "policy_memory":
        diagnostics.append(_diag("PT1", path,
                                 f"策略候选声明 layer={layer!r}，不属于 policy_memory 层"))
    kind = policy.get("kind")
    if isinstance(kind, str) and kind in SCIENTIFIC_KINDS:
        diagnostics.append(_diag("PT1", path,
                                 f"策略候选 kind={kind!r} 是科学记忆种类，不得作为策略上报"))
    for key in ("scientific_facts", "scientific_memory", "canonical_facts", "facts",
                "evidence_layer"):
        if policy.get(key) not in (None, [], {}, ""):
            diagnostics.append(_diag("PT1", f"{path}.{key}",
                                     "策略候选不得内嵌科学记忆（科学事实唯一来源是 canonical state）"))

    for key in SCIENTIFIC_EFFECT_KEYS:
        if policy.get(key) in (None, [], {}, "", False):
            continue
        if key in ("scientific_effect",) and isinstance(policy.get(key), dict):
            nested = [k for k in SCIENTIFIC_EFFECT_KEYS
                      if policy[key].get(k) not in (None, [], {}, "", False)]
            if nested:
                diagnostics.append(_diag("PT2", f"{path}.{key}",
                                         f"策略不得声称对科学主张产生效果：{sorted(nested)}"))
            continue
        diagnostics.append(_diag("PT2", f"{path}.{key}",
                                 "策略不得否证/支持科学主张；科学主张状态只能由 canonical 证据变更"))
    for parent in ("claim", "scientific", "effect"):
        nested = policy.get(parent)
        if isinstance(nested, dict):
            diagnostics.extend(_policy_mixing_diagnostics(nested, f"{path}.{parent}"))
    return diagnostics


def memory_layers(state: Dict[str, Any], *, trajectory_path: Optional[Path] = None,
                  policy_records: Sequence[Any] = ()) -> Dict[str, Any]:
    """三层记忆的严格分离视图。只读，不写盘。"""
    state = state if isinstance(state, dict) else {}
    diagnostics: List[cg.Diagnostic] = []

    for key in POLICY_SECTIONS:
        if state.get(key) not in (None, [], {}, ""):
            diagnostics.append(_diag(
                "PT1", f"state.{key}",
                "canonical state 中出现策略/决策经验层内容：科学与策略记忆必须分离"))

    for index, record in enumerate(policy_records or ()):
        diagnostics.extend(_policy_mixing_diagnostics(record, f"policy[{index}]"))

    scientific = _scientific_layer(state)
    experience, chain_diagnostics = _experience_layer(trajectory_path)
    policies = _policy_layer(policy_records or ())

    # 决策经验链断裂时，经验层不可信：把链诊断升格为 separation 诊断。
    diagnostics.extend(chain_diagnostics)
    if chain_diagnostics:
        diagnostics.append(_diag(
            "PT1", "decision_experience",
            f"决策经验哈希链/序列校验失败（{len(chain_diagnostics)} 条诊断）；"
            "该 JSONL 不能作为已验证的决策经验来源"))

    diagnostics = _dedupe(diagnostics)
    return {
        "scientific_memory": scientific,
        "decision_experience": experience,
        "policy_memory": policies,
        "separation_ok": not diagnostics,
        "diagnostics": [item.as_dict() for item in diagnostics],
    }


# ---------------------------------------------------------------------------
# 声明结构签名
# ---------------------------------------------------------------------------

def _contract_tokens(contract: Any) -> List[str]:
    tokens: Set[str] = set()
    if not isinstance(contract, dict):
        return []
    anchor = contract.get("primary_anchor")
    if isinstance(anchor, str) and anchor.strip():
        tokens.add(f"anchor:{anchor.strip()}")
    for key in ("constraints", "out_of_scope"):
        values = contract.get(key)
        if isinstance(values, list) and values:
            tokens.add(f"contract:{key}={len(values)}")
    for name in _as_list(contract.get("resources")):
        text = _tool_name(name)
        if text:
            tokens.add(f"contract:resource:{text}")
    for key in ("validation", "verification", "evidence_protocol", "validation_protocol"):
        if contract.get(key) not in (None, [], {}, ""):
            tokens.add(f"contract:protocol:{key}")
    return sorted(tokens)


def _claim_tokens(claim: Dict[str, Any]) -> Set[str]:
    tokens: Set[str] = set()
    status = claim.get("status")
    if isinstance(status, str) and status:
        tokens.add(f"claim:status={status}")
    for key in ("nearest_alternative", "falsifier", "scope", "parent", "subclaims",
                "known_flaws", "depends_on"):
        if claim.get(key) not in (None, [], {}, ""):
            tokens.add(f"claim:{key}")
    contract = claim.get("contract")
    if isinstance(contract, dict):
        for key, value in contract.items():
            if value not in (None, [], {}, ""):
                tokens.add(f"claim:contract:{key}")
    return tokens


def _uncertainty_tokens(uncertainty: Dict[str, Any]) -> Set[str]:
    tokens: Set[str] = set()
    for key, tag in (("status", "status"), ("importance", "importance"),
                     ("uncertainty", "level")):
        value = uncertainty.get(key)
        if isinstance(value, str) and value:
            tokens.add(f"unc:{tag}={value}")
    if uncertainty.get("cheapest_discriminating_test") not in (None, "", "TBD"):
        tokens.add("unc:test=declared")
    return tokens


def _signature_from_parts(*, operators: Iterable[Any], islands: Iterable[Any],
                          signature: Any, claim_structures: Iterable[Any] = (),
                          uncertainty_axes: Iterable[Any] = (),
                          contract_structures: Iterable[Any] = (),
                          assumption_count: int = 0) -> Dict[str, Any]:
    ops = sorted({_as_text(item) for item in operators if _as_text(item)})
    isls = sorted({_as_text(item) for item in islands if _as_text(item)})
    sig_tokens: Set[str] = set()
    if isinstance(signature, dict):
        for key, value in signature.items():
            if key in STRUCTURAL_SIGNATURE_KEYS and value is not None:
                sig_tokens.add(f"sig:{key}={_scalar_token(value)}")
    claims = sorted({str(item) for item in claim_structures if str(item)})
    unc = sorted({str(item) for item in uncertainty_axes if str(item)})
    contract_tokens = sorted({str(item) for item in contract_structures if str(item)})
    body = {
        "operators": ops,
        "islands": isls,
        "claim_structures": claims,
        "assumption_count": int(assumption_count),
        "uncertainty_axes": unc,
        "structural_signature": sorted(sig_tokens),
        "contract_structures": contract_tokens,
    }
    return {**body, "digest": cg.digest_of(body), "source": "declared_fields"}


def structural_signature(state: Dict[str, Any], index: Optional[Dict[str, Any]] = None
                         ) -> Dict[str, Any]:
    """只从**声明字段**推导结构签名；绝不读取自由文本或领域关键词。"""
    state = state if isinstance(state, dict) else {}
    operators: Set[str] = set()
    islands: Set[str] = set()
    signature: Dict[str, Any] = {}
    claim_structures: Set[str] = set()
    uncertainty_axes: Set[str] = set()

    # hypothesis.niche 是声明字段，映射到已有八菜单的 operator/island（复用 strategy_memory）。
    niche_operator = {entry["shift"]: entry["operator"] for entry in sm.STRATEGY_MENUS}
    niche_island = {entry["shift"]: entry["island"] for entry in sm.STRATEGY_MENUS}

    for hypothesis in _as_list(state.get("hypotheses")):
        if not isinstance(hypothesis, dict):
            continue
        op = _as_text(hypothesis.get("operator"))
        if op:
            operators.add(op)
        island = _as_text(hypothesis.get("island"))
        if island:
            islands.add(island)
        sig = hypothesis.get("structural_signature")
        if isinstance(sig, dict):
            signature.update(sig)
        niche = _as_text(hypothesis.get("niche"))
        if niche in niche_operator:
            operators.add(niche_operator[niche])
            islands.add(niche_island[niche])

    for claim in _as_list(state.get("claims")):
        if isinstance(claim, dict):
            claim_structures.update(_claim_tokens(claim))

    for uncertainty in _as_list(state.get("uncertainties")):
        if isinstance(uncertainty, dict):
            uncertainty_axes.update(_uncertainty_tokens(uncertainty))

    # index 只提供已经声明过的结构字段，不引入新语义。
    if isinstance(index, dict):
        for mechanism in _as_list(index.get("mechanisms")):
            if not isinstance(mechanism, dict):
                continue
            op = _as_text(mechanism.get("operator"))
            if op:
                operators.add(op)
            island = _as_text(mechanism.get("island"))
            if island:
                islands.add(island)
            sig = mechanism.get("structural_signature")
            if isinstance(sig, dict):
                signature.update(sig)

    assumptions = _as_list(state.get("assumptions"))
    return _signature_from_parts(
        operators=operators, islands=islands, signature=signature,
        claim_structures=claim_structures, uncertainty_axes=uncertainty_axes,
        contract_structures=_contract_tokens(state.get("contract")),
        assumption_count=len(assumptions))


def _signature_from_declared(declared: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(declared, dict):
        return None
    signature = declared.get("structural_signature")
    if not isinstance(signature, dict):
        signature = {key: declared[key] for key in STRUCTURAL_SIGNATURE_KEYS
                     if key in declared}
    operators = set(_as_list(declared.get("operators")))
    islands = set(_as_list(declared.get("islands")))
    op = _as_text(declared.get("operator"))
    if op:
        operators.add(op)
    island = _as_text(declared.get("island"))
    if island:
        islands.add(island)
    menu = _as_text(declared.get("menu"))
    entry = sm.MENU_BY_NAME.get(menu)
    if entry:
        operators.add(entry["operator"])
        islands.add(entry["island"])
    if not operators and not islands and not signature:
        return None
    return _signature_from_parts(operators=operators, islands=islands, signature=signature)


def _structure_tokens(signature: Dict[str, Any]) -> Set[str]:
    tokens: Set[str] = set()
    for op in signature.get("operators") or []:
        tokens.add(f"op:{op}")
    for island in signature.get("islands") or []:
        tokens.add(f"island:{island}")
    tokens.update(str(item) for item in signature.get("structural_signature") or [])
    return tokens


def _similarity_from_signatures(source: Dict[str, Any], target: Dict[str, Any],
                                threshold: float = SIMILARITY_THRESHOLD) -> Dict[str, Any]:
    source_tokens = _structure_tokens(source)
    target_tokens = _structure_tokens(target)
    union = source_tokens | target_tokens
    shared = source_tokens & target_tokens
    score = round(len(shared) / len(union), 6) if union else 0.0

    source_axes = {token for token in source_tokens
                   if token.startswith("op:") or token.startswith("island:")}
    target_axes = {token for token in target_tokens
                   if token.startswith("op:") or token.startswith("island:")}
    shared_axes = source_axes & target_axes
    if source_axes and target_axes:
        # 两侧都声明了算子/岛时，必须共享至少一个：不同的算子/岛就是不同的结构，
        # 即使五个距离签名恰好相同也不构成结构匹配。
        structural_match = bool(score >= threshold and shared_axes)
    else:
        structural_match = bool(score >= threshold and shared)

    shared_operators = sorted(set(source.get("operators") or []) &
                              set(target.get("operators") or []))
    shared_islands = sorted(set(source.get("islands") or []) &
                            set(target.get("islands") or []))
    shared_sig = sorted(set(source.get("structural_signature") or []) &
                        set(target.get("structural_signature") or []))
    basis = [
        f"operators: {len(shared_operators)}/{max(len(set(source.get('operators') or []) | set(target.get('operators') or [])), 1)}",
        f"islands: {len(shared_islands)}/{max(len(set(source.get('islands') or []) | set(target.get('islands') or [])), 1)}",
        f"structural_signature: {len(shared_sig)}/{max(len(set(source.get('structural_signature') or []) | set(target.get('structural_signature') or [])), 1)}",
        f"声明结构 token Jaccard={score}，阈值={threshold}",
    ]
    if not structural_match:
        basis.append("仅领域关键词/措辞相似不构成结构匹配（本判定不读取自由文本）")
    return {
        "score": score,
        "basis": basis,
        "shared_operators": shared_operators,
        "shared_islands": shared_islands,
        "structural_match": structural_match,
        "threshold": threshold,
    }


def structure_similarity(source_state: Dict[str, Any], target_state: Dict[str, Any],
                         source_index: Optional[Dict[str, Any]] = None,
                         target_index: Optional[Dict[str, Any]] = None,
                         *, threshold: float = SIMILARITY_THRESHOLD) -> Dict[str, Any]:
    """声明算子/岛/结构签名 token 上的 Jaccard；关键词重叠不构成结构匹配。"""
    source = structural_signature(source_state, source_index)
    target = structural_signature(target_state, target_index)
    return _similarity_from_signatures(source, target, threshold)


# ---------------------------------------------------------------------------
# 负向知识
# ---------------------------------------------------------------------------

NEGATED_CLAIM_STATUSES: Tuple[str, ...] = ("killed", "contradicted", "refuted")

#: 假设生命周期中代表“已停止追求/已被否证”的合法状态（state_check.HYPOTHESIS_STATUSES
#: 是 ("active","elite","archived","killed")；refuted/contradicted 用于兼容显式声明的投影）。
NEGATED_HYPOTHESIS_STATUSES: Tuple[str, ...] = (
    "killed", "archived", "refuted", "contradicted",
)

#: 索引（cognition/index.json）里机制生命周期中代表已否证的状态（cognition.MECHANISM_STATUSES）。
NEGATED_MECHANISM_STATUSES: Tuple[str, ...] = ("refuted",)


def negated_mechanisms(state: Dict[str, Any],
                       index: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """已被否证的机制：killed/contradicted/refuted 的主张、killed/archived 的假设、
    negative_knowledge，以及（当提供索引时）status == "refuted" 的索引机制。

    对 negative_knowledge 条目同时保留 `finding`（解释）与 `statement`（= ruled_out，
    即真正被排除的命题）；PT8 以 ruled_out 为主匹配、finding 为次级上下文。
    """
    state = state if isinstance(state, dict) else {}
    out: List[Dict[str, Any]] = []
    for claim in _as_list(state.get("claims")):
        if not isinstance(claim, dict):
            continue
        status = claim.get("status")
        if status not in NEGATED_CLAIM_STATUSES:
            continue
        out.append({
            "id": claim.get("id"),
            "statement": claim.get("statement", ""),
            "finding": "",
            "kind": "claim",
            "status": status,
        })
    for hypothesis in _as_list(state.get("hypotheses")):
        if not isinstance(hypothesis, dict):
            continue
        status = hypothesis.get("status")
        if status not in NEGATED_HYPOTHESIS_STATUSES:
            continue
        out.append({
            "id": hypothesis.get("id"),
            "statement": hypothesis.get("statement", ""),
            "finding": "",
            "kind": "hypothesis",
            "status": status,
        })
    for failure in _as_list(state.get("failures")):
        if not isinstance(failure, dict):
            continue
        failure_id = failure.get("id")
        for index_in_failure, memory in enumerate(_as_list(failure.get("negative_knowledge"))):
            if not isinstance(memory, dict):
                continue
            target = memory.get("target_id")
            ident = (target if isinstance(target, str) and target
                     else f"{failure_id}#nk{index_in_failure + 1}")
            finding = memory.get("finding")
            ruled_out = memory.get("ruled_out")
            # ruled_out 是被排除的命题；finding 只是解释。没有 ruled_out 时退回 finding /
            # failure.what，保证旧数据仍被覆盖。
            # Only strings can be compared. A non-string `ruled_out` used to be coerced by
            # truthiness into a non-string statement and then filtered out of the match set,
            # which silently disabled PT8 for that entry.
            ambiguous = ruled_out is not None and not isinstance(ruled_out, str)
            if isinstance(ruled_out, str) and ruled_out.strip():
                statement = ruled_out
            elif isinstance(finding, str) and finding.strip():
                statement = finding
            elif isinstance(failure.get("what"), str):
                statement = failure["what"]
            else:
                statement = ""
            out.append({
                "id": ident,
                "statement": statement,
                "finding": finding if isinstance(finding, str) else "",
                "kind": "failure",
                "status": failure.get("kind") or "negated",
                "ruled_out_ambiguous": ambiguous,
            })
    if isinstance(index, dict):
        for mechanism in _as_list(index.get("mechanisms")):
            if not isinstance(mechanism, dict):
                continue
            status = mechanism.get("status")
            if status not in NEGATED_MECHANISM_STATUSES:
                continue
            statement = mechanism.get("statement", "")
            identifiers: List[Any] = [mechanism.get("id")]
            refs = mechanism.get("canonical_refs")
            if isinstance(refs, dict):
                for key in ("claims", "hypotheses"):
                    identifiers.extend(_as_list(refs.get(key)))
            for ident in identifiers:
                if not isinstance(ident, str) or not ident:
                    continue
                out.append({
                    "id": ident,
                    "statement": statement,
                    "finding": "",
                    "kind": "mechanism",
                    "status": status,
                })
    out.sort(key=lambda item: (str(item.get("kind")), str(item.get("id"))))
    return out


# ---------------------------------------------------------------------------
# 条件求值（对目标 state 的声明字段）
# ---------------------------------------------------------------------------

def _resolve_path(path: str, state: Any) -> Tuple[bool, Any]:
    parts = [part for part in str(path).split(".") if part]
    if not parts:
        return False, None

    def walk(node: Any, remaining: List[str]) -> Tuple[bool, Any]:
        if not remaining:
            return True, node
        segment = remaining[0]
        if segment.endswith("[]"):
            key = segment[:-2]
            if not isinstance(node, dict) or key not in node:
                return False, None
            sequence = node[key]
            if not isinstance(sequence, list):
                return False, None
            collected = []
            for item in sequence:
                ok, value = walk(item, remaining[1:])
                if ok:
                    collected.append(value)
            return True, collected
        if isinstance(node, dict):
            if segment not in node:
                return False, None
            return walk(node[segment], remaining[1:])
        return False, None

    return walk(state, parts)


def _normalize_condition(condition: Any, index: int) -> Optional[Dict[str, Any]]:
    if not isinstance(condition, dict):
        return None
    cond = dict(condition)
    if not cond.get("field") and not cond.get("path"):
        if "hypothesis_operator" in cond:
            cond["field"] = "hypotheses[].operator"
            cond["value"] = cond["hypothesis_operator"]
            cond["op"] = cond.get("op") or "contains"
        elif "operator" in cond:
            cond["field"] = "hypotheses[].operator"
            cond["value"] = cond["operator"]
            cond["op"] = cond.get("op") or "contains"
        elif "island" in cond:
            cond["field"] = "hypotheses[].island"
            cond["value"] = cond["island"]
            cond["op"] = cond.get("op") or "contains"
        elif "anchor" in cond:
            cond["field"] = "contract.primary_anchor"
            cond["value"] = cond["anchor"]
            cond["op"] = cond.get("op") or "eq"
    return cond


def _collect_conditions(policy: Dict[str, Any], scope: Optional[Dict[str, Any]]
                        ) -> Tuple[List[Any], List[cg.Diagnostic]]:
    """收集条件；对“存在但不是 list/dict”的声明fail-closed 诊断（PT5）。

    只处理**显式存在**的键：键缺失表示未声明，是合法的默认；显式 null/字符串/数字则
    无法机械求值，必须阻塞而不是被静默忽略。
    """
    conditions: List[Any] = []
    diagnostics: List[cg.Diagnostic] = []

    def absorb(source: Any, path: str) -> None:
        if isinstance(source, list):
            conditions.extend(source)
            return
        if isinstance(source, dict):
            for key, value in source.items():
                if isinstance(value, dict):
                    item = dict(value)
                    item.setdefault("field", key)
                    conditions.append(item)
                else:
                    conditions.append({"field": key, "op": "eq", "value": value})
            return
        diagnostics.append(_diag(
            "PT5", path,
            f"applicable_conditions 声明为 {type(source).__name__}（{source!r}），"
            "既不是列表也不是对象；无法证明其条件成立（fail-closed 阻塞）"))

    containers: List[Tuple[Dict[str, Any], str]] = [(policy, "policy")]
    if isinstance(scope, dict):
        containers.append((scope, "policy.scope"))
    for container, prefix in containers:
        for key in ("applicable_conditions", "conditions"):
            if key in container:
                absorb(container[key], f"{prefix}.{key}")
    return conditions, diagnostics


def _condition_eval(condition: Any, target_state: Dict[str, Any]) -> Tuple[bool, bool, str]:
    """求值一个条件，返回 (是否满足, 是否可机械判定, 说明)。

    `可机械判定=False` 表示条件畸形/不可解析（缺 field、未知算子、缺 value、正则被拒），
    调用方必须 fail-closed。`可机械判定=True` 但 `满足=False` 才是“确实不适用”。
    """
    if not isinstance(condition, dict):
        return False, False, "条件不是对象；无法机械求值（fail-closed 阻塞）"
    cond = _normalize_condition(condition, 0)
    assert cond is not None
    field = cond.get("field") or cond.get("path")
    if not isinstance(field, str) or not field.strip():
        return False, False, "条件缺少 field，无法对声明字段求值（fail-closed 阻塞）"
    field = field.strip()
    op = cond.get("op") or cond.get("compare") or cond.get("relation")
    value = cond.get("value", _MISSING)
    if op is None:
        if "values" in cond:
            op, value = "in", cond.get("values")
        elif "present" in cond:
            op = "present" if cond.get("present") else "absent"
        elif value is not _MISSING:
            op = "eq"
        else:
            op = "exists"
    op = str(op)

    resolved, actual = _resolve_path(field, target_state)
    if not resolved:
        return False, False, f"条件字段 {field!r} 不存在于目标声明字段（fail-closed 阻塞）"

    if op in ("exists", "present"):
        present = actual is not None and actual != "" and actual != []
        return present, True, ("" if present else f"条件字段 {field!r} 为空")
    if op in ("absent", "missing"):
        missing = actual is None or actual == "" or actual == []
        return missing, True, ("" if missing else f"条件字段 {field!r} 存在")
    if value is _MISSING:
        return False, False, f"条件 {field!r} 的算子 {op!r} 缺少 value（fail-closed 阻塞）"

    if op in ("eq", "=="):
        ok = actual == value
    elif op in ("ne", "!="):
        ok = actual != value
    elif op == "in":
        ok = isinstance(value, (list, tuple, set)) and actual in list(value)
    elif op == "contains":
        ok = isinstance(actual, (list, tuple, set)) and value in list(actual)
        if not ok and isinstance(actual, str) and isinstance(value, str):
            ok = actual == value
    elif op == "subset":
        try:
            ok = set(actual) <= set(value)
        except TypeError:
            ok = False
    elif op == "superset":
        try:
            ok = set(actual) >= set(value)
        except TypeError:
            ok = False
    elif op in ("gt", "gte", "lt", "lte"):
        try:
            left, right = float(actual), float(value)
        except (TypeError, ValueError):
            return False, False, f"条件 {field!r} 的算子 {op!r} 需要数值"
        ok = {"gt": left > right, "gte": left >= right,
              "lt": left < right, "lte": left <= right}[op]
    elif op in ("matches", "regex"):
        # 安全决策：策略/反例条件完全由调用方（可能不可信）提供。`re` 没有超时，攻击者可用
        # `(a+)+$` 这类模式让闸门灾难性回溯（ReDoS），因此这里直接拒绝用户提供的正则算子
        # （fail-closed 不可判定），而不是执行无界匹配。规则只允许结构化比较算子。
        return False, False, (
            f"条件 {field!r} 使用被拒绝的正则算子 {op!r}；"
            "为避免无界回溯（ReDoS），闸门不接受用户提供的正则（fail-closed 阻塞）")
    else:
        return False, False, f"未知条件算子 {op!r}（fail-closed 阻塞）"
    detail = "" if ok else f"条件不满足：{field} {op} {value!r}（实际 {actual!r}）"
    return bool(ok), True, detail


def _condition_satisfied(condition: Any, target_state: Dict[str, Any]) -> Tuple[bool, str]:
    ok, _resolved, detail = _condition_eval(condition, target_state)
    return ok, detail


# ---------------------------------------------------------------------------
# 工具/资源、验证协议
# ---------------------------------------------------------------------------

def _tool_name(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("name", "id", "tool", "resource", "tool_id", "resource_id"):
            text = _as_text(item.get(key))
            if text:
                return text
    return ""


def _absorb_tool_names(value: Any, path: str, names: List[str],
                       diagnostics: List[cg.Diagnostic]) -> None:
    """收集工具名；存在但不是 list/tuple 时给出 PT6 诊断（fail-closed）。"""
    if isinstance(value, (list, tuple)):
        names.extend(_tool_name(item) for item in value)
        return
    diagnostics.append(_diag(
        "PT6", path,
        f"required_tools/resources 声明为 {type(value).__name__}（{value!r}），"
        "不是列表；无法证明目标具备这些工具/资源（fail-closed 阻塞）"))


def _required_tools(policy: Dict[str, Any], scope: Optional[Dict[str, Any]]
                    ) -> Tuple[List[str], List[cg.Diagnostic]]:
    names: List[str] = []
    diagnostics: List[cg.Diagnostic] = []
    for key in ("required_tools", "required_resources", "tools", "resources"):
        if key in policy:
            _absorb_tool_names(policy[key], f"policy.{key}", names, diagnostics)
    requires = policy.get("requires")
    if isinstance(requires, dict):
        for key in ("tools", "resources", "required_tools", "required_resources"):
            if key in requires:
                _absorb_tool_names(requires[key], f"policy.requires.{key}", names, diagnostics)
    if isinstance(scope, dict):
        for key in ("required_tools", "required_resources", "tools", "resources"):
            if key in scope:
                _absorb_tool_names(scope[key], f"policy.scope.{key}", names, diagnostics)
    return sorted({name for name in names if name}), diagnostics


def _declared_resources(state: Dict[str, Any]) -> Set[str]:
    contract = state.get("contract") if isinstance(state.get("contract"), dict) else {}
    names: Set[str] = set()
    for key in ("resources", "tools"):
        for item in _as_list(contract.get(key)):
            name = _tool_name(item)
            if name:
                names.add(name)
    return names


def _flatten_protocol(value: Any, prefix: str = "") -> Set[str]:
    if value is None or value == "":
        return set()
    if isinstance(value, (str, int, float, bool)):
        return {f"{prefix}={value}"} if prefix else {str(value)}
    if isinstance(value, list):
        tokens: Set[str] = set()
        for item in value:
            tokens |= _flatten_protocol(item, prefix)
        return tokens
    if isinstance(value, dict):
        keys = [key for key in value if key in PROTOCOL_KEYS]
        selected = keys if keys else list(value)
        tokens = set()
        for key in selected:
            child = f"{prefix}.{key}" if prefix else str(key)
            tokens |= _flatten_protocol(value[key], child)
        return tokens
    return set()


def _protocol_tokens(state: Dict[str, Any]) -> Set[str]:
    state = state if isinstance(state, dict) else {}
    contract = state.get("contract") if isinstance(state.get("contract"), dict) else {}
    tokens: Set[str] = set()
    for key in ("validation", "verification", "evidence_protocol", "validation_protocol"):
        tokens |= _flatten_protocol(contract.get(key))
    tokens |= _flatten_protocol(state.get("validation_protocol"))
    return tokens


def _policy_protocol_tokens(policy: Dict[str, Any]) -> Set[str]:
    tokens: Set[str] = set()
    for key in ("validation_protocol", "validation", "evidence_protocol", "protocol"):
        tokens |= _flatten_protocol(policy.get(key))
    return tokens


# ---------------------------------------------------------------------------
# 策略提出的机制、反例
# ---------------------------------------------------------------------------

def _proposed_mechanisms(policy: Dict[str, Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []

    def absorb(value: Any) -> None:
        if isinstance(value, str):
            text = value.strip()
            if text:
                out.append({"id": text, "statement": ""})
        elif isinstance(value, dict):
            ident = value.get("id") or value.get("mechanism_id") or value.get("target")
            statement = value.get("statement") or value.get("mechanism") or value.get("description")
            out.append({"id": _as_text(ident), "statement": _as_text(statement)})
        elif isinstance(value, list):
            for item in value:
                absorb(item)

    for key in ("mechanism", "proposed_mechanism", "proposes_mechanism", "proposal",
                "mechanism_id", "mechanism_ids", "mechanism_refs", "target_mechanism",
                "target", "subject", "reproposes"):
        if key in policy:
            absorb(policy.get(key))
    return [item for item in out if item.get("id") or item.get("statement")]


def _counterexample_list(policy: Dict[str, Any]) -> List[Any]:
    for key in ("counterexamples", "known_counterexamples", "exceptions"):
        value = policy.get(key)
        if isinstance(value, list):
            return value
    return []


def _counterexample_tokens(counterexample: Any) -> Tuple[Set[str], bool, List[Any]]:
    """返回 (声明结构 token, 是否结构化, 条件列表)。"""
    if not isinstance(counterexample, dict):
        return set(), False, []
    tokens: Set[str] = set()
    structured = False
    for key in ("operators", "islands"):
        values = _as_list(counterexample.get(key))
        if values:
            structured = True
            prefix = "op:" if key == "operators" else "island:"
            tokens |= {f"{prefix}{_as_text(item)}" for item in values if _as_text(item)}
    for key in ("structural_signature", "signature"):
        value = counterexample.get(key)
        if isinstance(value, dict):
            structured = True
            for name, number in value.items():
                tokens.add(f"sig:{name}={_scalar_token(number)}")
    structure = counterexample.get("structure") or counterexample.get("applies_to")
    if isinstance(structure, dict):
        structured = True
        tokens |= {f"op:{_as_text(item)}" for item in _as_list(structure.get("operators"))
                   if _as_text(item)}
        tokens |= {f"island:{_as_text(item)}" for item in _as_list(structure.get("islands"))
                   if _as_text(item)}
        signature = structure.get("structural_signature")
        if isinstance(signature, dict):
            for name, number in signature.items():
                tokens.add(f"sig:{name}={_scalar_token(number)}")
    elif isinstance(structure, list):
        structured = True
        tokens |= {str(item) for item in structure if isinstance(item, str)}
    if counterexample.get("operator") or counterexample.get("island"):
        structured = True
        if _as_text(counterexample.get("operator")):
            tokens.add(f"op:{_as_text(counterexample.get('operator'))}")
        if _as_text(counterexample.get("island")):
            tokens.add(f"island:{_as_text(counterexample.get('island'))}")
    conditions: List[Any] = []
    for key in ("conditions", "applicable_conditions", "when"):
        conditions.extend(_as_list(counterexample.get(key)))
    if conditions:
        structured = True
    return tokens, structured, conditions


def _counterexample_errors(policy: Dict[str, Any], target_state: Dict[str, Any],
                           threshold: float) -> List[cg.Diagnostic]:
    diagnostics: List[cg.Diagnostic] = []
    target_tokens = _structure_tokens(structural_signature(target_state))
    target_ops = set(structural_signature(target_state).get("operators") or [])
    target_islands = set(structural_signature(target_state).get("islands") or [])
    for index, counterexample in enumerate(_counterexample_list(policy)):
        path = f"policy.counterexamples[{index}]"
        if isinstance(counterexample, str):
            text = counterexample.strip()
            if text in target_ops or text in target_islands or text in target_tokens:
                diagnostics.append(_diag("PT10", path,
                                         f"已知反例 {text!r} 覆盖目标结构；不得迁移"))
            elif re.fullmatch(r"[A-Za-z]+[0-9][A-Za-z0-9\-]*", text):
                continue  # 指向具体 canonical 对象的反例引用，不构成结构覆盖
            else:
                diagnostics.append(_diag(
                    "PT10", path,
                    "反例未声明适用结构，无法排除其覆盖目标（fail-closed 阻塞）"))
            continue
        tokens, structured, conditions = _counterexample_tokens(counterexample)
        for token in list(tokens):
            if token.startswith(("op:", "island:", "sig:")):
                continue
            prefixed = []
            if token in target_ops:
                prefixed.append(f"op:{token}")
            if token in target_islands:
                prefixed.append(f"island:{token}")
            if prefixed:
                tokens.discard(token)
                tokens.update(prefixed)
        declared_structure = bool(tokens) or counterexample.get("structure") is not None \
            or counterexample.get("signature") is not None
        if conditions:
            evaluations = [_condition_eval(condition, target_state) for condition in conditions]
            unresolved = [detail for _ok, resolved, detail in evaluations if not resolved]
            if unresolved:
                # 无法机械判定条件是否适用时不得当作“不适用”：否则加一个畸形条件即可
                # 中和反例覆盖检查（fail-open）。这里 fail-closed。
                diagnostics.append(_diag(
                    "PT10", path,
                    "反例条件无法机械求值，无法排除其覆盖目标（fail-closed 阻塞）："
                    + "；".join(unresolved)))
                continue
            if not any(ok for ok, _resolved, _detail in evaluations):
                if declared_structure:
                    continue  # 有作用域的反例：条件可判定且不成立，确实不适用
                # 只写了不成立的条件、却没有任何适用结构：这不是“可判定不适用”，
                # 而是缺少结构声明，必须 fail-closed（否则加一条条件即可中和 PT10）。
                diagnostics.append(_diag(
                    "PT10", path,
                    "反例只声明了不成立的条件、没有任何适用结构：无法排除其覆盖目标"
                    "（fail-closed 阻塞）"))
                continue
        if tokens:
            union = tokens | target_tokens
            shared = tokens & target_tokens
            score = len(shared) / len(union) if union else 0.0
            if tokens <= target_tokens or (shared and score >= threshold):
                diagnostics.append(_diag(
                    "PT10", path,
                    f"已知反例覆盖目标结构（共享 {sorted(shared)}）；不得迁移"))
                continue
        if not structured:
            diagnostics.append(_diag(
                "PT10", path,
                "反例未声明适用结构，无法排除其覆盖目标（fail-closed 阻塞）"))
    return diagnostics


# ---------------------------------------------------------------------------
# 迁移判定
# ---------------------------------------------------------------------------

def _normalize_scope(policy: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]],
                                                      List[cg.Diagnostic]]:
    raw: Any = policy.get("scope")
    if raw is None:
        raw = policy.get("scopes")
    if raw is None:
        raw = policy.get("applicability")
    if raw is None:
        return None, [_diag("PT3", "policy.scope", "策略缺少 scope：无法界定迁移边界")]
    if isinstance(raw, str):
        kind = raw.strip()
        if kind in SCOPE_KINDS:
            return {"kind": kind}, []
        return None, [_diag("PT3", "policy.scope",
                            f"scope 字符串 {raw!r} 不是结构化作用域；必须是 {SCOPE_KINDS} 之一")]
    if isinstance(raw, dict):
        kind = raw.get("kind") or raw.get("type") or raw.get("level")
        if not isinstance(kind, str) or kind not in SCOPE_KINDS:
            return None, [_diag(
                "PT3", "policy.scope",
                f"scope.kind={kind!r} 缺失或未知；允许 {SCOPE_KINDS}")]
        return dict(raw), []
    return None, [_diag("PT3", "policy.scope", "scope 必须是结构化对象")]


def _policy_declared_signature(policy: Dict[str, Any],
                               scope: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    candidates: List[Any] = [policy.get("structural_signature"), policy.get("source_signature"),
                             policy.get("signature"), policy.get("structure")]
    if isinstance(scope, dict):
        candidates += [scope.get("structural_signature"), scope.get("signature"),
                       scope.get("structure")]
    for candidate in candidates:
        signature = _signature_from_declared(candidate)
        if signature is not None:
            return signature
    return None


def _transfer_similarity(policy: Dict[str, Any], target_state: Dict[str, Any],
                         scope: Optional[Dict[str, Any]],
                         source_state: Optional[Dict[str, Any]],
                         source_index: Optional[Dict[str, Any]],
                         target_index: Optional[Dict[str, Any]],
                         threshold: float, *, attested: bool = False
                         ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if not isinstance(target_state, dict):
        return None, None
    target = structural_signature(target_state, target_index)
    if isinstance(source_state, dict):
        source = structural_signature(source_state, source_index)
        self_attested = False
    else:
        source = _policy_declared_signature(policy, scope)
        self_attested = True
    if source is None:
        return None, target
    similarity = _similarity_from_signatures(source, target, threshold)
    if self_attested:
        # 自证结构：策略自己声明源签名并给自己打分。没有 attested source_state
        # （或调用方显式提供 source_trajectories 作为来源）时不得据此判定结构匹配，
        # 否则任何策略只要自带一个 signatur 就能得到 1.0 并迁移（fail-open）。
        similarity["self_attested"] = True
        if not attested:
            similarity["basis"] = list(similarity["basis"]) + [
                "缺少 attested source_state/source_trajectories：策略自证的结构签名"
                "不足以判定可迁移（fail-closed 阻塞）"]
        similarity["structural_match"] = bool(similarity["structural_match"] and attested)
    return similarity, target


def _tool_errors(policy: Dict[str, Any], target_state: Dict[str, Any],
                 scope: Optional[Dict[str, Any]], target_tools: Sequence[Any]
                 ) -> List[cg.Diagnostic]:
    required, diagnostics = _required_tools(policy, scope)
    if not required:
        return diagnostics
    available = {_tool_name(item) for item in target_tools}
    available.discard("")
    if isinstance(target_state, dict):
        available |= _declared_resources(target_state)
    for tool in required:
        if tool not in available:
            diagnostics.append(_diag(
                "PT6", "policy.required_tools",
                f"目标缺少必备工具/资源 {tool!r}；可用集合 {sorted(available)}"))
    return diagnostics


def _protocol_errors(policy: Dict[str, Any], target_state: Dict[str, Any],
                     source_state: Optional[Dict[str, Any]]) -> List[cg.Diagnostic]:
    diagnostics: List[cg.Diagnostic] = []
    policy_tokens = _policy_protocol_tokens(policy)
    target_tokens = _protocol_tokens(target_state) if isinstance(target_state, dict) else set()
    source_tokens = _protocol_tokens(source_state) if isinstance(source_state, dict) else set()

    required = policy_tokens or source_tokens
    if not required:
        return []
    if not target_tokens:
        diagnostics.append(_diag(
            "PT7", "policy.validation_protocol",
            "目标状态未声明 source 的证据/验证协议；不能默认协议兼容"))
        return diagnostics
    missing = sorted(required - target_tokens)
    if missing:
        diagnostics.append(_diag(
            "PT7", "policy.validation_protocol",
            f"验证协议不兼容：目标缺少 {missing}"))
    if source_tokens and target_tokens and not (source_tokens <= target_tokens):
        diagnostics.append(_diag(
            "PT7", "policy.validation_protocol",
            "源与目标的 contract.validation/verification 声明不同；不可直接迁移"))
    return diagnostics


def _negated_errors(policy: Dict[str, Any], target_state: Dict[str, Any],
                    source_state: Optional[Dict[str, Any]],
                    target_index: Optional[Dict[str, Any]] = None,
                    source_index: Optional[Dict[str, Any]] = None) -> List[cg.Diagnostic]:
    negated: List[Dict[str, Any]] = []
    if isinstance(target_state, dict):
        negated += negated_mechanisms(target_state, target_index)
    if isinstance(source_state, dict):
        negated += negated_mechanisms(source_state, source_index)
    if not negated:
        return []
    diagnostics: List[cg.Diagnostic] = []
    ambiguous = sorted(str(item.get("id")) for item in negated
                       if item.get("ruled_out_ambiguous"))
    if ambiguous:
        # Cannot prove the policy does not re-propose these, so the transfer is blocked.
        diagnostics.append(_diag(
            "PT8", "negative_knowledge.ruled_out",
            "以下已否证条目的 ruled_out 不是字符串，无法机械比较："
            + ", ".join(ambiguous[:5])))
        return diagnostics
    for proposed in _proposed_mechanisms(policy):
        for item in negated:
            ident = str(item.get("id") or "")
            # 主匹配对象是被排除的命题 ruled_out（statement），finding 仅作次级上下文。
            negated_statements = [_norm_statement(item.get("statement")),
                                  _norm_statement(item.get("finding"))]
            negated_statements = [text for text in negated_statements if text]
            if proposed.get("id") and proposed["id"] == ident:
                diagnostics.append(_diag(
                    "PT8", "policy.mechanism",
                    f"策略重新提出已被否证的机制 {ident!r}（{item.get('kind')}）"))
                continue
            statement = _norm_statement(proposed.get("statement"))
            if not statement or not negated_statements:
                continue
            context = ""
            finding = _norm_statement(item.get("finding"))
            if finding and finding != negated_statements[0]:
                context = f"；否证理由：{item.get('finding')!r}"
            if statement in negated_statements:
                diagnostics.append(_diag(
                    "PT8", "policy.mechanism",
                    f"策略重新提出已被否证的机制陈述（{ident!r}）{context}"))
            elif any(len(text) >= 12 and (text in statement or statement in text)
                     for text in negated_statements):
                diagnostics.append(_diag(
                    "PT8", "policy.mechanism",
                    f"策略机制陈述与已否证机制 {ident!r} 实质相同{context}"))
    return diagnostics


def _evidence_level(policy: Dict[str, Any]) -> str:
    for key in ("evidence_level", "success_level", "support_level", "historical_evidence_level"):
        value = policy.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    evidence = policy.get("evidence")
    if isinstance(evidence, dict):
        for key in ("level", "success_level", "support_level"):
            value = evidence.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _independent_refs(policy: Dict[str, Any]) -> List[str]:
    refs: List[str] = []
    for key in INDEPENDENT_EVIDENCE_KEYS:
        value = policy.get(key)
        if isinstance(value, str) and value.strip():
            refs.append(value.strip())
        elif isinstance(value, (list, tuple)):
            refs.extend(str(item) for item in value if str(item).strip())
    evidence = policy.get("evidence")
    if isinstance(evidence, dict):
        for key in INDEPENDENT_EVIDENCE_KEYS:
            value = evidence.get(key)
            if isinstance(value, str) and value.strip():
                refs.append(value.strip())
            elif isinstance(value, (list, tuple)):
                refs.extend(str(item) for item in value if str(item).strip())
    return sorted({ref for ref in refs if ref})


def _evidence_projects(policy: Dict[str, Any]) -> Set[str]:
    projects: Set[str] = set()
    for key in EVIDENCE_PROJECT_KEYS:
        value = policy.get(key)
        if isinstance(value, str) and value.strip():
            projects.add(value.strip())
        elif isinstance(value, (list, tuple)):
            projects.update(str(item) for item in value if str(item).strip())
    evidence = policy.get("evidence")
    if isinstance(evidence, dict):
        for key in EVIDENCE_PROJECT_KEYS:
            value = evidence.get(key)
            if isinstance(value, str) and value.strip():
                projects.add(value.strip())
            elif isinstance(value, (list, tuple)):
                projects.update(str(item) for item in value if str(item).strip())
    return projects


def _evidence_level_errors(policy: Dict[str, Any], scope: Optional[Dict[str, Any]],
                           source_trajectories: Sequence[Any],
                           records: Sequence[Any], source_project: Optional[str]
                           ) -> List[cg.Diagnostic]:
    diagnostics: List[cg.Diagnostic] = []
    kind = (scope or {}).get("kind")
    level = _evidence_level(policy)

    declared_projects = _evidence_projects(policy)
    projects = set(declared_projects)
    if isinstance(source_project, str) and source_project.strip():
        projects.add(source_project.strip())

    # Attested evidence is a *trajectory* that carries BOTH a decision and a qualified
    # outcome. A self-declared project list, and a bare outcome line with no decision behind
    # it, are not evidence: both used to satisfy the cross-project requirement on their own.
    views: Dict[str, Any] = {}
    try:
        import decision_trajectory as dt
        views = dt.rebuild_trajectories(list(records or ()) + list(source_trajectories or ()))
    except Exception:  # pragma: no cover - a malformed store means "no attested evidence"
        views = {}
    attested: Dict[str, Set[str]] = {}
    for ident, view in views.items():
        decision = view.get("decision")
        outcome = view.get("outcome")
        if not isinstance(decision, dict) or not isinstance(outcome, dict):
            continue
        if outcome.get("evidence_qualification") != "qualified":
            continue
        project = (outcome.get("project") or decision.get("project") or view.get("project"))
        if isinstance(project, str) and project.strip():
            attested.setdefault(project.strip(), set()).add(ident)
    attested_projects: Set[str] = set(attested)
    attested_trajectories = {ident for idents in attested.values() for ident in idents}
    unbacked = sorted(item for item in declared_projects if item not in attested_projects)

    independent = _independent_refs(policy)
    def _ref_key(ref: Any) -> str:
        if isinstance(ref, str):
            return ref.strip()
        if isinstance(ref, dict):
            for key in ("project", "trajectory_id", "trajectory", "id", "ref"):
                value = ref.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    independent_backed = any(
        _ref_key(ref) in attested_projects or _ref_key(ref) in attested_trajectories
        for ref in independent)
    diagnostic_path = "policy.scope"

    if level in WEAK_EVIDENCE_LEVELS:
        diagnostics.append(_diag(
            "PT9", diagnostic_path,
            f"历史成功证据等级 {level!r} 不足以支撑迁移（无成功历史证据）"))
    elif level and level not in EVIDENCE_RANKS:
        diagnostics.append(_diag(
            "PT9", diagnostic_path,
            f"历史成功证据等级 {level!r} 未知，无法证明达到 scope 主张（fail-closed 阻塞）"))
    elif level and kind in BROAD_SCOPES and \
            EVIDENCE_RANKS.get(level, 0) < EVIDENCE_RANKS.get(kind, 0):
        diagnostics.append(_diag(
            "PT9", diagnostic_path,
            f"scope 声称 {kind!r}，但历史成功证据等级只有 {level!r}"))

    if kind in BROAD_SCOPES:
        if len(attested_projects) < 2:
            diagnostics.append(_diag(
                "PT9", diagnostic_path,
                f"{kind!r} scope 需要 ≥2 个有真实轨迹（决策 + 合格 outcome）的项目；"
                f"当前只有 {len(attested_projects)} 个：{sorted(attested_projects)}。"
                f"自述项目列表与没有决策的 outcome 行都不算证据"))
        if unbacked:
            diagnostics.append(_diag(
                "PT9", diagnostic_path,
                "以下项目是策略自述、没有轨迹证据支撑：" + ", ".join(unbacked[:5])
                + "（自述证据不构成跨项目依据）"))
        supporting = [str(item) for item in (policy.get("supporting_trajectory_ids") or [])
                      if str(item)]
        missing = sorted(item for item in supporting if item not in attested_trajectories)
        if missing:
            diagnostics.append(_diag(
                "PT9", diagnostic_path,
                "supporting_trajectory_ids 未指向有「决策 + 合格 outcome」的轨迹："
                + ", ".join(missing[:5])
                + "（依赖的轨迹必须自己站得住）"))
        if independent and not independent_backed:
            diagnostics.append(_diag(
                "PT9", diagnostic_path,
                "independent_evaluation_refs 的项目没有一个能得到轨迹证据背书："
                "自述的独立评价不算独立评价"))
        if not independent and len(attested_projects) < 2:
            diagnostics.append(_diag(
                "PT9", diagnostic_path,
                "缺少独立评价引用，且没有 ≥2 个项目的合格 outcome 轨迹"))
    return diagnostics


def transfer_errors(policy: Dict[str, Any], target_state: Dict[str, Any], *,
                    source_state: Optional[Dict[str, Any]] = None,
                    source_index: Optional[Dict[str, Any]] = None,
                    target_index: Optional[Dict[str, Any]] = None,
                    source_trajectories: Sequence[Any] = (),
                    source_project: Optional[str] = None,
                    target_project: Optional[str] = None,
                    target_tools: Sequence[Any] = (),
                    records: Sequence[Any] = (),
                    threshold: float = SIMILARITY_THRESHOLD) -> List[cg.Diagnostic]:
    """PT1—PT10 迁移诊断。空列表 = 允许迁移；任何一条 = fail-closed 阻塞。只读，不改输入。"""
    policy_dict = policy if isinstance(policy, dict) else {}
    target = target_state if isinstance(target_state, dict) else {}
    diagnostics: List[cg.Diagnostic] = []
    diagnostics.extend(_policy_mixing_diagnostics(policy, "policy"))

    scope, scope_errors = _normalize_scope(policy_dict)
    diagnostics.extend(scope_errors)

    if not isinstance(target_state, dict):
        diagnostics.append(_diag("PT4", "policy", "目标 state 不是对象，无法建立结构签名"))

    similarity, _target_sig = _transfer_similarity(
        policy_dict, target, scope, source_state, source_index, target_index, threshold,
        attested=bool(isinstance(source_state, dict) or source_trajectories))
    if similarity is None:
        diagnostics.append(_diag(
            "PT4", "policy.structure",
            "无法建立源结构签名；领域关键词相似不足以判定可迁移"))
    elif not similarity["structural_match"]:
        if similarity.get("self_attested"):
            diagnostics.append(_diag(
                "PT4", "policy.structure",
                "策略自证结构签名，但没有 attested source_state/source_trajectories；"
                "自证来源不能判定可迁移（fail-closed 阻塞）"))
        else:
            diagnostics.append(_diag(
                "PT4", "policy.structure",
                f"结构不匹配（score={similarity['score']} < {similarity['threshold']} "
                "或未共享声明结构 token）；领域关键词相似不足以判定可迁移"))

    conditions, condition_shape_errors = _collect_conditions(policy_dict, scope)
    diagnostics.extend(condition_shape_errors)
    for index, condition in enumerate(conditions):
        ok, detail = _condition_satisfied(condition, target)
        if not ok:
            diagnostics.append(_diag("PT5", f"policy.applicable_conditions[{index}]", detail))

    diagnostics.extend(_tool_errors(policy_dict, target, scope, target_tools))
    diagnostics.extend(_protocol_errors(policy_dict, target, source_state))
    diagnostics.extend(_negated_errors(policy_dict, target, source_state,
                                       target_index, source_index))
    diagnostics.extend(_evidence_level_errors(
        policy_dict, scope, source_trajectories, records, source_project))
    diagnostics.extend(_counterexample_errors(policy_dict, target, threshold))
    return _dedupe(diagnostics)


def transfer_decision(policy: Dict[str, Any], target_state: Dict[str, Any],
                      **kwargs: Any) -> Dict[str, Any]:
    """迁移判定：任何一条诊断都返回 BLOCK（fail-closed 默认）。"""
    threshold = kwargs.pop("threshold", SIMILARITY_THRESHOLD)
    diagnostics = transfer_errors(policy, target_state, threshold=threshold, **kwargs)
    scope, _ = _normalize_scope(policy if isinstance(policy, dict) else {})
    similarity, _ = _transfer_similarity(
        policy if isinstance(policy, dict) else {}, target_state, scope,
        kwargs.get("source_state"), kwargs.get("source_index"),
        kwargs.get("target_index"), threshold,
        attested=bool(isinstance(kwargs.get("source_state"), dict)
                      or kwargs.get("source_trajectories")))
    if similarity is None:
        similarity = {"score": 0.0, "basis": ["无源结构签名，无法匹配"],
                      "shared_operators": [], "shared_islands": [],
                      "structural_match": False, "threshold": threshold}

    source_project = kwargs.get("source_project")
    target_project = kwargs.get("target_project")
    if isinstance(source_project, str) and isinstance(target_project, str):
        cross_project = source_project != target_project
    else:
        cross_project = bool(scope and scope.get("kind") in BROAD_SCOPES)

    boundaries: List[str] = []
    if scope:
        boundaries.append(f"scope:{scope.get('kind')}")
    if isinstance(source_project, str) and isinstance(target_project, str):
        boundaries.append(f"project:{source_project}->{target_project}")
    for item in negated_mechanisms(
            target_state if isinstance(target_state, dict) else {},
            kwargs.get("target_index")):
        boundaries.append(f"negated:{item.get('kind')}:{item.get('id')}")
    for index, counterexample in enumerate(_counterexample_list(
            policy if isinstance(policy, dict) else {})):
        ident = counterexample.get("id") if isinstance(counterexample, dict) else counterexample
        boundaries.append(f"counterexample:{ident if ident is not None else index}")
    if isinstance(policy, dict) and isinstance(policy.get("action"), dict):
        tier = sm.action_tier(policy["action"])
        boundaries.append(f"action_tier:{tier.get('label')}")
    boundaries = sorted({str(item) for item in boundaries})

    return {
        "status": "BLOCK" if diagnostics else "ALLOW",
        "reasons": [item.render() for item in diagnostics],
        "codes": sorted({item.rule for item in diagnostics}),
        "similarity": similarity,
        "boundaries": boundaries,
        "schema": SCHEMA_TRANSFER,
        "cross_project": cross_project,
    }


# ---------------------------------------------------------------------------
# 过期经验
# ---------------------------------------------------------------------------

def expired_trajectories_report(records: Sequence[Any], state: Dict[str, Any], *,
                                max_state_version_gap: int = 50,
                                invalidated_subjects: Sequence[Any] = ()
                                ) -> Dict[str, Any]:
    """过期轨迹 + 诊断（`expired_trajectories` 的 fail-closed 报告版）。

    - 缺失/非整数的 `state_version`：无法证明轨迹新鲜 → 全部视为过期，并给出诊断。
    - 缺失/非整数/负数的 `max_state_version_gap`：不抛 TypeError，按 0 处理（任何正差都
      过期）并给出诊断。
    - 引用已失效主体的轨迹始终过期。
    """
    diagnostics: List[cg.Diagnostic] = []
    current: Optional[int] = None
    if isinstance(state, dict):
        raw_version = state.get("state_version")
        if isinstance(raw_version, int) and not isinstance(raw_version, bool) \
                and raw_version >= 0:
            current = raw_version
        else:
            diagnostics.append(_diag(
                "PT11", "state.state_version",
                f"state_version={raw_version!r} 缺失或非整数；无法证明轨迹未过期，"
                "按 fail-closed 全部视为过期"))
    else:
        diagnostics.append(_diag(
            "PT11", "state", "state 不是对象；无法读取 state_version，按 fail-closed 全部视为过期"))

    if isinstance(max_state_version_gap, int) and not isinstance(max_state_version_gap, bool):
        gap = max_state_version_gap
        if gap < 0:
            diagnostics.append(_diag(
                "PT11", "max_state_version_gap",
                f"max_state_version_gap={gap!r} 为负数；按 0 处理（fail-closed）"))
            gap = 0
    else:
        diagnostics.append(_diag(
            "PT11", "max_state_version_gap",
            f"max_state_version_gap={max_state_version_gap!r} 非整数；"
            "按 0 处理（任何正版本差都视为过期，fail-closed）"))
        gap = 0

    invalid = {str(item) for item in invalidated_subjects}
    views = dt.rebuild_trajectories(records)
    expired: Set[str] = set()
    for ident, view in views.items():
        decision = view.get("decision") if isinstance(view.get("decision"), dict) else {}
        context = decision.get("context") if isinstance(decision.get("context"), dict) else {}
        outcome = view.get("outcome") if isinstance(view.get("outcome"), dict) else {}

        referenced: List[Any] = []
        for key in ("active_hypotheses", "key_uncertainties", "visible_evidence"):
            referenced.extend(_as_list(context.get(key)))
        for ref in _as_list(outcome.get("evidence_refs")):
            if isinstance(ref, dict):
                referenced.extend(value for value in ref.values() if value is not None)
        if invalid and any(str(item) in invalid for item in referenced):
            expired.add(ident)
            continue

        # 状态版本不可用时，轨迹的新鲜度不可证明：fail-closed。
        if current is None:
            expired.add(ident)
            continue

        versions: List[int] = []
        bound = context.get("state_version")
        if isinstance(bound, int) and not isinstance(bound, bool):
            versions.append(bound)
        at_version = outcome.get("at_state_version")
        if isinstance(at_version, int) and not isinstance(at_version, bool):
            versions.append(at_version)
        if not versions:
            expired.add(ident)
            continue
        if current - min(versions) > gap:
            expired.add(ident)
    return {
        "expired": sorted(expired),
        "diagnostics": [item.as_dict() for item in _dedupe(diagnostics)],
    }


def expired_trajectories(records: Sequence[Any], state: Dict[str, Any], *,
                         max_state_version_gap: int = 50,
                         invalidated_subjects: Sequence[Any] = ()) -> List[str]:
    """过期轨迹：绑定 state_version 落后过多，或引用了已失效主体。

    接口保持 `List[str]`；需要诊断时使用 `expired_trajectories_report`。
    """
    return expired_trajectories_report(
        records, state, max_state_version_gap=max_state_version_gap,
        invalidated_subjects=invalidated_subjects)["expired"]


# ---------------------------------------------------------------------------
# 有损压缩拒绝
# ---------------------------------------------------------------------------

def _compression_item(entry: Any) -> Tuple[str, str]:
    if isinstance(entry, dict):
        return str(entry.get("id")), str(entry.get("kind"))
    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
        return str(entry[0]), str(entry[1])
    return str(entry), "unknown"


def compression_report(identifier_kinds: Iterable[Any], budget: int, *,
                       protected: Sequence[Any] = ()) -> Dict[str, Any]:
    """模拟把记忆压缩到 budget 条；证据/终止规则/科学事实与 protected 永不可丢。"""
    # 先按 id 归并**所有**声明，再做保护判定：同一个 id 以不同 kind 重复出现时，
    # 只要任一声明是不可丢弃/未知种类/protected，该 id 就被强制保留。
    order: List[str] = []
    kinds_by_id: Dict[str, List[str]] = {}
    for entry in identifier_kinds:
        ident, kind = _compression_item(entry)
        if ident not in kinds_by_id:
            order.append(ident)
            kinds_by_id[ident] = []
        if kind not in kinds_by_id[ident]:
            kinds_by_id[ident].append(kind)
    protected_set = {str(item) for item in protected}

    def effective_kind(ident: str) -> str:
        kinds = kinds_by_id[ident]
        for kind in kinds:
            if kind in NON_DROPPABLE_KINDS:
                return kind
        for kind in kinds:
            if kind not in ALL_KINDS:
                return kind
        return kinds[0]

    items: List[Tuple[str, str]] = [(ident, effective_kind(ident)) for ident in order]

    if not isinstance(budget, int) or isinstance(budget, bool) or budget < 0:
        return {"status": "REFUSED", "kept": [ident for ident, _ in items], "dropped": [],
                "reasons": [f"非法预算 {budget!r}；压缩拒绝执行"]}

    reasons: List[str] = []
    forced: List[Tuple[str, str]] = []
    droppable: List[Tuple[str, str]] = []
    for ident, kind in items:
        unknown = kind not in ALL_KINDS
        if kind in NON_DROPPABLE_KINDS or ident in protected_set or unknown:
            forced.append((ident, kind))
            if unknown:
                reasons.append(f"未知记忆种类 {kind!r} 按不可丢弃处理：{ident}")
        else:
            droppable.append((ident, kind))

    if budget >= len(items):
        return {"status": "OK", "kept": [ident for ident, _ in items], "dropped": [],
                "reasons": reasons}

    if budget < len(forced):
        reasons.insert(0, (
            f"预算 {budget} < 必须保留的 {len(forced)} 条（evidence/stop_rule/"
            f"scientific_fact/protected）；拒绝任何有损压缩"))
        return {"status": "REFUSED", "kept": [ident for ident, _ in items], "dropped": [],
                "reasons": reasons}

    room = budget - len(forced)
    kept_droppable = droppable[:room]
    dropped = droppable[room:]
    kept = forced + kept_droppable
    # 保持输入顺序。
    order = {ident: index for index, (ident, _) in enumerate(items)}
    kept.sort(key=lambda item: order[item[0]])
    dropped.sort(key=lambda item: order[item[0]])
    kept_ids = [ident for ident, _ in kept]
    dropped_ids = [ident for ident, _ in dropped]
    for kind in DROPPABLE_KINDS:
        dropped_kind = [ident for ident, item_kind in dropped if item_kind == kind]
        if dropped_kind:
            reasons.append(f"丢弃 {kind}: {sorted(dropped_kind)}")
    return {"status": "OK", "kept": kept_ids, "dropped": dropped_ids, "reasons": reasons}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    def error(self, message):  # pragma: no cover - argparse plumbing
        self.print_usage(sys.stderr)
        raise SystemExit(EXIT_ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(description=__doc__,
                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", choices=(
        "layers", "signature", "transfer", "expired", "compress", "selftest"))
    parser.add_argument("--state", help="path to research-state.json")
    parser.add_argument("--trajectory", help="path to decision-trajectory.jsonl")
    parser.add_argument("--policy", help="path to a policy JSON file (or inline JSON)")
    parser.add_argument("--target-state", dest="target_state",
                        help="path to the target research-state.json")
    parser.add_argument("--source-state", dest="source_state",
                        help="path to the source research-state.json")
    parser.add_argument("--source-trajectory", dest="source_trajectory",
                        help="path to the source decision-trajectory.jsonl")
    parser.add_argument("--source-project", dest="source_project")
    parser.add_argument("--target-project", dest="target_project")
    parser.add_argument("--items", help="JSON file or inline JSON for compression items")
    parser.add_argument("--budget", type=int, help="compression budget")
    parser.add_argument("--selftest", action="store_true")
    return parser


def _emit(payload: Any, code: int = EXIT_OK) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return code


def _read_json(value: str) -> Any:
    path = Path(value)
    try:
        text = path.read_text(encoding="utf-8") if path.is_file() else value
    except OSError as exc:
        raise cg.CognitionError(f"无法读取 {value!r}：{exc}") from exc
    try:
        return json.loads(text)
    except (TypeError, ValueError) as exc:
        raise cg.CognitionError(f"无法把 {value!r} 解析为 JSON：{exc}") from exc


def _load_trajectory_records(path_value: Optional[str]) -> Tuple[List[Dict[str, Any]], Optional[Path]]:
    if not path_value:
        return [], None
    path = Path(path_value)
    try:
        records, _ = dt.load_records(path, tolerant=True)
    except (OSError, dt.TrajectoryError) as exc:
        raise cg.CognitionError(f"无法读取轨迹 {path_value!r}：{exc}") from exc
    return records, path


def _invalid(errors: Sequence[str]) -> int:
    return _emit({"status": "INVALID", "errors": [str(item) for item in errors]}, EXIT_ERROR)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.selftest or args.command == "selftest":
        return selftest()

    if args.command == "layers":
        if not args.state:
            return _invalid(["需要 --state"])
        try:
            state = cg.load_state(Path(args.state))
        except Exception as exc:
            return _invalid([f"无法加载 state {args.state!r}：{type(exc).__name__}: {exc}"])
        payload = memory_layers(state, trajectory_path=Path(args.trajectory)
                                if args.trajectory else None)
        return _emit({"status": "OK" if payload["separation_ok"] else "FAIL", **payload},
                     EXIT_OK if payload["separation_ok"] else EXIT_HARD)

    if args.command == "signature":
        if not args.state:
            return _invalid(["需要 --state"])
        try:
            state = cg.load_state(Path(args.state))
        except Exception as exc:
            return _invalid([f"无法加载 state {args.state!r}：{type(exc).__name__}: {exc}"])
        return _emit({"status": "OK", "signature": structural_signature(state)})

    if args.command == "transfer":
        if not args.policy or not args.target_state:
            return _invalid(["需要 --policy 与 --target-state"])
        try:
            policy = _read_json(args.policy)
            target_state = cg.load_state(Path(args.target_state))
            source_state = cg.load_state(Path(args.source_state)) if args.source_state else None
            records, _ = _load_trajectory_records(args.source_trajectory)
        except Exception as exc:
            return _invalid([f"无法读取输入：{type(exc).__name__}: {exc}"])
        if not isinstance(policy, dict):
            return _invalid(["策略候选必须是 JSON 对象（非对象无法证明其属于策略层）"])
        if not isinstance(target_state, dict):
            return _invalid(["target-state 必须是 JSON 对象"])
        result = transfer_decision(
            policy, target_state, source_state=source_state, records=records,
            source_project=args.source_project, target_project=args.target_project)
        return _emit(result, EXIT_OK if result["status"] == "ALLOW" else EXIT_HARD)

    if args.command == "expired":
        if not args.state or not args.trajectory:
            return _invalid(["需要 --state 与 --trajectory"])
        try:
            state = cg.load_state(Path(args.state))
            records, _ = _load_trajectory_records(args.trajectory)
        except Exception as exc:
            return _invalid([f"无法读取输入：{type(exc).__name__}: {exc}"])
        report = expired_trajectories_report(records, state)
        return _emit({"status": "OK" if not report["diagnostics"] else "DEGRADED",
                      "expired": report["expired"], "diagnostics": report["diagnostics"]},
                     EXIT_OK if not report["diagnostics"] else EXIT_HARD)

    if args.command == "compress":
        if args.items is None or args.budget is None:
            return _invalid(["需要 --items 与 --budget"])
        try:
            items = _read_json(args.items)
        except Exception as exc:
            return _invalid([f"无法读取 --items：{type(exc).__name__}: {exc}"])
        report = compression_report(items, args.budget)
        # REFUSED 正是本命令要检测的失败；必须以非零退出码暴露给 CI/自动化。
        return _emit(report, EXIT_OK if report.get("status") == "OK" else EXIT_HARD)

    parser.print_help()
    return EXIT_ERROR


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest_state(*, operator: str = "reframe", island: str = "P1",
                    anchor: str = "phenomenon", version: int = 3) -> Dict[str, Any]:
    return {
        "_schema": "research-idea-pipeline/research-state@1",
        "state_version": version,
        "contract": {"goal": "判断机制 M 是否解释目标现象", "primary_anchor": anchor,
                     "constraints": [], "resources": [],
                     "provenance_rationale": "", "out_of_scope": [],
                     "validation": {"protocol": "preregistered", "min_tier": "T2"}},
        "claims": [{"id": "C1", "statement": "机制 M 解释目标现象", "status": "killed",
                    "nearest_alternative": "N", "falsifier": "干预 I 后消失",
                    "scope": "数据集 A", "contract": {}, "validity": {"status": "valid"}}],
        "evidence": [{"id": "E1", "kind": "experiment", "supports": ["C1"], "strength": "weak",
                      "scope": "A", "epistemic_status": "Observed", "source_ref": "X1",
                      "verification_tier": "T2", "validity": {"status": "valid"}}],
        "assumptions": [{"id": "AS1", "statement": "测量无偏", "status": "explicit",
                         "validity": {"status": "valid"}}],
        "hypotheses": [{"id": "H1", "statement": "机制 M 是主因", "status": "active",
                        "operator": operator, "island": island,
                        "structural_signature": {"assumption_distance": 1,
                                                 "formulation_distance": 1,
                                                 "representation_distance": 0,
                                                 "theory_lens_distance": 1,
                                                 "mechanism_distance": 2},
                        "validity": {"status": "valid"}}],
        "experiments": [], "literature": [],
        "failures": [{"id": "F1", "kind": "falsified", "what": "协议 P 已被否决",
                      "negative_knowledge": [{"target_id": "C2",
                                              "finding": "协议 P 在该 regime 下无效",
                                              "ruled_out": "协议 P 有效",
                                              "retry_allowed": False}],
                      "validity": {"status": "valid"}}],
        "uncertainties": [{"id": "U1", "question": "机制 M 在数据集 B 成立？",
                           "importance": "high", "uncertainty": "high",
                           "cheapest_discriminating_test": "X8", "status": "open",
                           "validity": {"status": "valid"}}],
        "assurance": [], "repairs": [], "narrative_view": {}, "reviews": [],
        "decision": {"verdict": "continue", "rationale": "", "next_phase": "R3"},
    }


def _selftest_diagnostics(policy: Dict[str, Any], target: Dict[str, Any],
                          source: Dict[str, Any]) -> List[cg.Diagnostic]:
    return transfer_errors(policy, target, source_state=source,
                           target_tools=["evaluation-harness"],
                           source_project="A", target_project="B")


def selftest() -> int:
    checks: List[Tuple[str, bool]] = []

    def check(name: str, condition: bool) -> None:
        checks.append((name, bool(condition)))

    source = _selftest_state()
    target = _selftest_state()

    # 三层分离
    layers = memory_layers(source, policy_records=[{"id": "POL-1", "scope": {"kind": "structure"}}])
    check("scientific_memory 不含策略候选",
          "POL-1" not in json.dumps(layers["scientific_memory"]))
    check("policy_memory 与 decision_experience 分离",
          layers["policy_memory"]["count"] == 1
          and layers["decision_experience"]["layer"] == "decision_experience")
    check("合法候选 separation_ok", layers["separation_ok"] is True)
    mixed = memory_layers(source, policy_records=[
        {"id": "POL-2", "kind": "scientific_fact", "refutes": ["C1"]}])
    codes = {item["rule"] for item in mixed["diagnostics"]}
    check("PT1/PT2 捕获层次混装", "PT1" in codes and "PT2" in codes
          and mixed["separation_ok"] is False)

    # 结构相似 / 不相似
    same = structure_similarity(source, target)
    check("相同声明结构匹配", same["structural_match"] is True and same["score"] >= 0.5)
    different = _selftest_state(operator="remote_analogy", island="P4")
    different["contract"]["primary_anchor"] = "benchmark"
    different["claims"][0]["statement"] = "机制 M 解释目标现象"  # 领域关键词故意相同
    different["hypotheses"][0]["structural_signature"] = {
        "assumption_distance": 3, "formulation_distance": 4,
        "representation_distance": 2, "theory_lens_distance": 4,
        "mechanism_distance": 1}
    diff = structure_similarity(source, different)
    check("同领域关键词但结构不同不匹配",
          diff["structural_match"] is False and diff["score"] < 0.5)
    empty = structure_similarity({}, {})
    check("空声明结构不匹配", empty["structural_match"] is False and empty["score"] == 0.0)

    # 负向知识
    negated = negated_mechanisms(target)
    check("否证机制被收集", any(item["id"] == "C1" for item in negated)
          and any(item["kind"] == "failure" for item in negated))

    # 迁移：ALLOW
    allow_policy = {
        "id": "POL-ALLOW",
        "scope": {"kind": "structure"},
        "applicable_conditions": [
            {"field": "contract.primary_anchor", "op": "eq", "value": "phenomenon"}],
        "required_tools": ["evaluation-harness"],
        "validation_protocol": {"protocol": "preregistered", "min_tier": "T2"},
        "evidence_level": "independent",
        "independent_evaluation_refs": ["SCHED-1"],
        "counterexamples": [],
    }
    allowed = transfer_decision(allow_policy, target, source_state=source,
                                target_tools=["evaluation-harness"],
                                source_project="A", target_project="B")
    check("结构匹配的策略被允许", allowed["status"] == "ALLOW", )
    check("cross_project 被标记", allowed["cross_project"] is True
          and allowed["schema"] == SCHEMA_TRANSFER)

    # PT3
    no_scope = dict(allow_policy)
    no_scope.pop("scope")
    check("PT3 缺少 scope", "PT3" in {d.rule for d in _selftest_diagnostics(no_scope, target, source)})

    # PT4
    check("PT4 结构不同",
          "PT4" in {d.rule for d in _selftest_diagnostics(allow_policy, different, source)})

    # PT5
    bad_condition = dict(allow_policy)
    bad_condition["applicable_conditions"] = [
        {"field": "contract.primary_anchor", "op": "eq", "value": "theory"}]
    check("PT5 条件不满足",
          "PT5" in {d.rule for d in _selftest_diagnostics(bad_condition, target, source)})

    # PT6
    missing_tool = dict(allow_policy)
    missing_tool["required_tools"] = ["gpu-cluster"]
    check("PT6 工具缺失",
          "PT6" in {d.rule for d in _selftest_diagnostics(missing_tool, target, source)})

    # PT8
    repropose = dict(allow_policy)
    repropose["mechanism"] = {"id": "C1", "statement": ""}
    check("PT8 重新提出被否证机制",
          "PT8" in {d.rule for d in _selftest_diagnostics(repropose, target, source)})

    # PT9
    global_policy = dict(allow_policy)
    global_policy["scope"] = {"kind": "global"}
    global_policy.pop("independent_evaluation_refs")
    check("PT9 单一项目的 global scope",
          "PT9" in {d.rule for d in _selftest_diagnostics(global_policy, target, source)})

    # PT10
    counter = dict(allow_policy)
    counter["counterexamples"] = [{"id": "CE1", "operators": ["reframe"], "islands": ["P1"]}]
    check("PT10 反例覆盖目标结构",
          "PT10" in {d.rule for d in _selftest_diagnostics(counter, target, source)})

    # 过期轨迹
    context = dt.build_context(source, scientific_question="q", active_hypotheses=["H1"],
                               key_uncertainties=["U1"], visible_evidence=["E1"])
    record = dt.build_decision_record(
        source, route="A", project="A", context=context,
        candidates=[{"action": "H1"}], chosen="H1",
        scheduler_priority={"level": 1, "label": "x"})
    fresh_state = dict(source, state_version=context["state_version"] + 10)
    old_state = dict(source, state_version=context["state_version"] + 500)
    check("过期轨迹被标记",
          dt.rebuild_trajectories([record]) and
          expired_trajectories([record], old_state) == [record["trajectory_id"]])
    check("新鲜轨迹不过期", expired_trajectories([record], fresh_state) == [])
    check("失效主体标记轨迹",
          expired_trajectories([record], fresh_state, invalidated_subjects=["H1"])
          == [record["trajectory_id"]])

    # 压缩
    items = [("E1", "evidence"), ("E2", "stop_rule"), ("P1", "policy"),
             ("P2", "policy"), ("D1", "decision_experience")]
    refused = compression_report(items, 1)
    check("有损压缩拒绝丢弃证据", refused["status"] == "REFUSED"
          and refused["dropped"] == [] and len(refused["kept"]) == 5)
    allowed_compression = compression_report(items, 3)
    check("允许丢弃策略并报告", allowed_compression["status"] == "OK"
          and "P2" in allowed_compression["dropped"]
          and any("policy" in reason for reason in allowed_compression["reasons"]))
    protected = compression_report(items, 2, protected=["D1"])
    check("protected 成员不可丢",
          protected["status"] == "REFUSED" and protected["dropped"] == [])

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    print("selftest " + ("OK" if not failed else "FAILED: " + "; ".join(failed)))
    return EXIT_OK if not failed else EXIT_HARD


if __name__ == "__main__":
    raise SystemExit(main())
