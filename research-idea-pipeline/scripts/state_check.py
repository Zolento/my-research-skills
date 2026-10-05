#!/usr/bin/env python3
"""state_check.py — Research World Model（R1）机械闸门：V1—V12 引用完整性审计

契约来源
--------
`docs/r-architecture-wave1-spec.md` §2.2（八类一等对象的必填字段）
与 §2.3（引用完整性规则 V1—V10）、§5（R10 处置 / 关闭枚举）。

**为什么必须有这个脚本：**「八类一等对象」只写在 policy 里，执行者会写成散文。
没有 validator，"一等对象"是宣言，不是机制。本脚本把 §2.3 的十条规则变成可执行判定，
每条违规都带 **规则号 + JSON 路径 + 现值**，可直接贴回执行者。

用法：
    python3 state_check.py <state.json>            # 校验（默认行为，本脚本从不写入）
    python3 state_check.py <state.json> --check    # 显式化「只校验不写」
    python3 state_check.py <state.json> --json     # 机器可读结果（stdout 只有 JSON）
    python3 state_check.py <state.json> --quiet    # 只打印汇总行
    python3 state_check.py --selftest              # 内置自检（V1—V12 全覆盖）
    python3 state_check.py --list-rules            # 列出规则号与判据

规则（逐字取自 spec §2.3，全部为硬违规）：

    V1  每个 C 的 `falsifier` 非空
    V2  `C.supporting_evidence` / `refuting_evidence` 的每个 id 必须存在于 `evidence[]`
    V3  无任何 E 引用的 C 必须 `status: ungrounded`；有 E 却标 `ungrounded` 也是违规
    V4  每条 F 必须被至少一个 `claims[].known_flaws` 或 `experiments[].known_flaws` 引用
    V5  `epistemic_status` ∈ 五值；`Hypothesized` / `Unknown` 的条目不得出现在 `supporting_evidence`
    V6  每条 H 的 `niche` 非空（QD archive 的前提）
    V7  `U.cheapest_discriminating_test` 必须指向存在的 X，或字面量 `TBD`
    V8  `X.parent` 必须是存在的 X 或 `null`；树不得成环
    V9  `assurance[].kill_condition` 非空，且 `discriminating_test` 指向存在的 X 或 `TBD`
    V10 每条 `repairs[]` 记录必须齐备 `flaw / disposition / state_delta / closure`

判据补充（口径固定，避免各自解释）：
    * 「非空」= 字符串 strip 后非空；非字符串（数字 / 数组 / null）一律算违规。
    * V3 的「E 引用」按 `supporting_evidence` + `refuting_evidence` 里**写出来的 id 条目**计数，
      不查它是否悬空（悬空由 V2 单独判）。
    * V4 只认 `claims[].known_flaws` 与 `experiments[].known_flaws`；`failures[].referenced_by`
      **不构成**引用凭证（spec §2.3 逐字如此）。
    * V7 / V9 的 `TBD` 为精确字面量（strip 后比对，不接受 `tbd` / `TBD 待定`）。
    * V10 除四字段齐备外，另按 spec §5 强制两个枚举：
      `disposition ∈ REPAIR_CLAIM|RUN_TEST|FIX_IMPLEMENTATION|NARROW_SCOPE|KILL_BRANCH`；
      `closure ∈ RESOLVED|ACCEPTED_LIMITATION`。（§7 验收要求枚举逐字一致。）
    * `X.parent` 键缺失或为 `null` = 根节点；缺失 `assurance` / `repairs` 顶层键 = 空数组。
    * 顶层允许把 world model 包在 `world_model` / `research_state` / `state` 单键下（自动解包）。
    * V1—V15 之外**不新增**硬规则（spec §2.3 是唯一契约）。

退出码（与仓库既有脚本一致）：
    0  全部通过
    1  参数错误（与 refs_index.py 的硬错误口径一致）
    3  存在硬违规
    4  环境不满足（文件缺失 / JSON 非法 / 顶层结构不符，无法作为 world model 校验）
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

SCHEMA = "research-idea-pipeline/state-check@1"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_HARD = 3
EXIT_ENV = 4

HARD = "hard"
# 人类可读行的severity 标签（JSON 里仍是机器可读的 "hard"）
SEVERITY_LABEL: Dict[str, str] = {HARD: "硬违规"}

# 八类一等对象（spec §2.1）：字段名 → ID 前缀
OBJECT_KEYS: Tuple[Tuple[str, str], ...] = (
    ("claims", "C"),
    ("evidence", "E"),
    ("assumptions", "AS"),
    ("hypotheses", "H"),
    ("experiments", "X"),
    ("literature", "LIT"),
    ("failures", "F"),
    ("uncertainties", "U"),
)
# V9 / V10 的载体（spec §2.3 要求，但 §2.1 未列入八类）
EXTRA_KEYS: Tuple[str, ...] = ("assurance", "repairs")
CHECKED_KEYS: Tuple[str, ...] = tuple(key for key, _ in OBJECT_KEYS) + EXTRA_KEYS

# 顶层包装键：允许 world model 被包一层（容错，不改变判定）
WRAPPER_KEYS: Tuple[str, ...] = ("world_model", "research_state", "state")

EPISTEMIC_STATUSES: Tuple[str, ...] = (
    "Observed", "Supported", "Hypothesized", "Planned", "Unknown",
)
# spec §2.3 V5：这两类不得出现在 supporting_evidence
UNSUPPORTABLE_STATUSES: Tuple[str, ...] = ("Hypothesized", "Unknown")

# spec §5：处置 / 关闭枚举（只有这些）
DISPOSITIONS: Tuple[str, ...] = (
    "REPAIR_CLAIM", "RUN_TEST", "FIX_IMPLEMENTATION", "NARROW_SCOPE", "KILL_BRANCH",
)
CLOSURES: Tuple[str, ...] = ("RESOLVED", "ACCEPTED_LIMITATION")
# Wave 2：QD archive 的 niche 复用 N1—N10 preset 名（不引入第二套枚举）
NICHES: Tuple[str, ...] = tuple(f"N{n}" for n in range(1, 11))
ISLANDS: Tuple[str, ...] = ("P1", "P2", "P3", "P4", "P5", "P6", "local")

UNGROUNDED = "ungrounded"
TBD = "TBD"

VALUE_LIMIT = 60  # 违规行里「现值」的显示上限

RULES: Dict[str, str] = {
    "V1": "每个 C 的 falsifier 非空",
    "V2": "C.supporting_evidence / refuting_evidence 的每个 id 必须存在于 evidence[]",
    "V3": "无任何 E 引用的 C 必须 status: ungrounded；有 E 却标 ungrounded 也是违规",
    "V4": "每条 F 必须被至少一个 claims[].known_flaws 或 experiments[].known_flaws 引用",
    "V5": "epistemic_status ∈ 五值；Hypothesized / Unknown 的条目不得出现在 supporting_evidence",
    "V6": "每条 H 的 niche 非空",
    "V7": "U.cheapest_discriminating_test 必须指向存在的 X，或字面量 TBD",
    "V8": "X.parent 必须是存在的 X 或 null；树不得成环",
    "V9": "assurance[].kill_condition 非空，且 discriminating_test 指向存在的 X 或 TBD",
    "V10": "每条 repairs[] 记录必须齐备 flaw / disposition / state_delta / closure",
    "V11": "stage == X2（基线校准）时 claim_targeted 必须为空数组，不得承担 claim 判别",
    "V12": "status == failed 的 X 必须被某条 failures[].referenced_by 引用（失败不得消失）",
    "V13": "hypotheses[].island ∈ {P1..P6, local}（默认开启 P1—P4，P5/P6 按需）",
    "V14": "hypotheses[].generation 是非负整数",
    "V15": "每个出现过的 niche 至少有一条 status: elite（QD archive 保多样性）",
}
RULE_ORDER: List[str] = list(RULES)


# ---------------------------------------------------------------------------
# 小工具：非空判定 / 显示 / 取值
# ---------------------------------------------------------------------------

def _text_ok(value: Any) -> bool:
    """文本字段的「非空」口径：必须是 strip 后非空的字符串。"""
    return isinstance(value, str) and bool(value.strip())


def _is_blank(value: Any) -> bool:
    """None / 空串 / 空白串 / 空容器 = 空（用于违规措辞：为空 vs 类型错）。"""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    return False


def _shorten(text: str, limit: int = VALUE_LIMIT) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _display(value: Any) -> str:
    """违规行里的「现值」显示；空值返回空串（由调用方回退到对象 id）。"""
    if _is_blank(value):
        return ""
    if isinstance(value, str):
        return _shorten(value)
    if isinstance(value, (dict, list)):
        try:
            return _shorten(json.dumps(value, ensure_ascii=False))
        except (TypeError, ValueError):  # pragma: no cover - 不可序列化的兜底
            return _shorten(repr(value))
    return _shorten(repr(value))


def _id_of(entry: Dict[str, Any]) -> str:
    value = entry.get("id")
    return value.strip() if isinstance(value, str) else ""


def _subject_of(entry: Dict[str, Any], *fallback_keys: str) -> str:
    """违规行的对象定位符：优先 id；assurance / repairs 这类无 id 的记录用特征字段。"""
    identifier = _id_of(entry)
    if identifier:
        return identifier
    for key in fallback_keys:
        value = entry.get(key)
        if _text_ok(value):
            return _shorten(value)
    return ""


def _string_refs(entry: Dict[str, Any], key: str) -> List[str]:
    """取 xx[].key 里的非空字符串条目（非数组 / 非字符串条目一律忽略）。"""
    values = entry.get(key)
    if not isinstance(values, list):
        return []
    return [item.strip() for item in values if isinstance(item, str) and item.strip()]


# ---------------------------------------------------------------------------
# 违规记录
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    """一条硬违规：规则号 + JSON 路径 + 现值（+ 对象 id，便于回贴执行者）。"""

    rule: str
    path: str
    detail: str
    value: Any = None
    subject: str = ""
    severity: str = HARD

    def render(self) -> str:
        shown = _display(self.value) or self.subject or "-"
        label = SEVERITY_LABEL.get(self.severity, self.severity)
        return f"{self.rule} {label} · {self.path} {self.detail} · {shown}"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "path": self.path,
            "detail": self.detail,
            "value": self.value,
            "subject": self.subject,
            "line": self.render(),
        }


@dataclass
class Report:
    """一次校验的结果（JSON 输出与人类输出的共同来源）。"""

    ok: bool
    exit_code: int
    source: str = ""
    violations: List[Violation] = field(default_factory=list)
    checked: Dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None
    error_kind: Optional[str] = None
    unwrapped_from: Optional[str] = None

    def rules(self) -> List[str]:
        present = {violation.rule for violation in self.violations}
        return [rule for rule in RULE_ORDER if rule in present]

    def rule_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for rule in self.rules():
            counts[rule] = sum(1 for v in self.violations if v.rule == rule)
        return counts

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "source": self.source,
            "ok": self.ok,
            "exit_code": self.exit_code,
            "checked": dict(self.checked),
            "counts": self.rule_counts(),
            "violations": [violation.as_dict() for violation in self.violations],
        }
        if self.error is not None:
            payload["error"] = self.error
            payload["error_kind"] = self.error_kind
        if self.unwrapped_from is not None:
            payload["unwrapped_from"] = self.unwrapped_from
        return payload

    def summary(self) -> str:
        if self.error is not None:
            return f"[env] 环境不满足（退出码 {EXIT_ENV}）：{self.error}"
        counts = "、".join(f"{key}={self.checked.get(key, 0)}" for key in CHECKED_KEYS)
        if not self.violations:
            return f"[ok] 0 处硬违规：V1—V{RULE_ORDER[-1][1:]} 全部通过；{counts}"
        breakdown = "、".join(f"{rule}×{count}" for rule, count in self.rule_counts().items())
        return (f"[hard] 共 {len(self.violations)} 处硬违规（{breakdown}）；state 不合规；{counts}")


# ---------------------------------------------------------------------------
# 结构校验（决定退出码 4）
# ---------------------------------------------------------------------------

def _unwrap(doc: Any) -> Tuple[Any, Optional[str]]:
    """顶层若是单键包装（world_model / research_state / state），解一层。"""
    if not isinstance(doc, dict):
        return doc, None
    if any(key in doc for key, _ in OBJECT_KEYS):
        return doc, None
    for key in WRAPPER_KEYS:
        inner = doc.get(key)
        if isinstance(inner, dict) and any(name in inner for name, _ in OBJECT_KEYS):
            return inner, key
    return doc, None


def structure_error(doc: Any) -> Tuple[Optional[str], Any, Optional[str]]:
    """返回 (错误信息, 有效 doc, 解包来源键)。错误信息非空 = 退出码 4。"""
    if not isinstance(doc, dict):
        kind = type(doc).__name__
        return f"根节点必须是 JSON 对象（实际是 {kind}）", doc, None

    effective, unwrapped_from = _unwrap(doc)

    present = [key for key, _ in OBJECT_KEYS if key in effective]
    if not present:
        return (
            "未找到 Research World Model 的八类一等对象数组"
            "（claims / evidence / assumptions / hypotheses / experiments / "
            "literature / failures / uncertainties）；这不是 R1 world model",
            effective,
            unwrapped_from,
        )

    for key in CHECKED_KEYS:
        if key not in effective:
            continue
        values = effective[key]
        if not isinstance(values, list):
            return (
                f"`{key}` 必须是数组（实际是 {type(values).__name__}），无法校验",
                effective,
                unwrapped_from,
            )
        for index, entry in enumerate(values):
            if not isinstance(entry, dict):
                return (
                    f"`{key}[{index}]` 必须是对象（实际是 {type(entry).__name__}），无法校验",
                    effective,
                    unwrapped_from,
                )

    return None, effective, unwrapped_from


# ---------------------------------------------------------------------------
# 上下文
# ---------------------------------------------------------------------------

def _entries(doc: Dict[str, Any], key: str) -> List[Tuple[int, Dict[str, Any]]]:
    values = doc.get(key)
    if not isinstance(values, list):
        return []
    return [(index, entry) for index, entry in enumerate(values) if isinstance(entry, dict)]


def _index_by_id(entries: Sequence[Tuple[int, Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    mapping: Dict[str, Dict[str, Any]] = {}
    for _index, entry in entries:
        identifier = _id_of(entry)
        if identifier and identifier not in mapping:
            mapping[identifier] = entry
    return mapping


@dataclass
class _Context:
    claims: List[Tuple[int, Dict[str, Any]]]
    evidence: List[Tuple[int, Dict[str, Any]]]
    assumptions: List[Tuple[int, Dict[str, Any]]]
    hypotheses: List[Tuple[int, Dict[str, Any]]]
    experiments: List[Tuple[int, Dict[str, Any]]]
    literature: List[Tuple[int, Dict[str, Any]]]
    failures: List[Tuple[int, Dict[str, Any]]]
    uncertainties: List[Tuple[int, Dict[str, Any]]]
    assurance: List[Tuple[int, Dict[str, Any]]]
    repairs: List[Tuple[int, Dict[str, Any]]]
    evidence_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    experiment_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    experiment_index: Dict[str, int] = field(default_factory=dict)

    @classmethod
    def build(cls, doc: Dict[str, Any]) -> "_Context":
        context = cls(
            claims=_entries(doc, "claims"),
            evidence=_entries(doc, "evidence"),
            assumptions=_entries(doc, "assumptions"),
            hypotheses=_entries(doc, "hypotheses"),
            experiments=_entries(doc, "experiments"),
            literature=_entries(doc, "literature"),
            failures=_entries(doc, "failures"),
            uncertainties=_entries(doc, "uncertainties"),
            assurance=_entries(doc, "assurance"),
            repairs=_entries(doc, "repairs"),
        )
        context.evidence_by_id = _index_by_id(context.evidence)
        context.experiment_by_id = _index_by_id(context.experiments)
        for index, experiment in context.experiments:
            identifier = _id_of(experiment)
            if identifier and identifier not in context.experiment_index:
                context.experiment_index[identifier] = index
        return context


# ---------------------------------------------------------------------------
# V1—V10
# ---------------------------------------------------------------------------

def _v1(ctx: _Context) -> List[Violation]:
    """V1：每个 C 的 falsifier 非空。"""
    out: List[Violation] = []
    for index, claim in ctx.claims:
        value = claim.get("falsifier")
        if _text_ok(value):
            continue
        detail = "为空" if _is_blank(value) else "必须是非空字符串"
        out.append(Violation("V1", f"claims[{index}].falsifier", detail, value, _subject_of(claim)))
    return out


def _v2(ctx: _Context) -> List[Violation]:
    """V2：C 的 evidence 引用必须存在于 evidence[]。"""
    out: List[Violation] = []
    for index, claim in ctx.claims:
        for key in ("supporting_evidence", "refuting_evidence"):
            refs = claim.get(key)
            if refs is None:
                continue
            if not isinstance(refs, list):
                out.append(Violation(
                    "V2", f"claims[{index}].{key}", "必须是数组", refs, _subject_of(claim),
                ))
                continue
            for position, ref in enumerate(refs):
                path = f"claims[{index}].{key}[{position}]"
                if not _text_ok(ref):
                    out.append(Violation("V2", path, "不是非空 evidence id", ref, _subject_of(claim)))
                elif ref.strip() not in ctx.evidence_by_id:
                    out.append(Violation(
                        "V2", path, "指向不存在的 evidence id", ref, _subject_of(claim),
                    ))
    return out


def _v3(ctx: _Context) -> List[Violation]:
    """V3：无 E 引用 ⇒ ungrounded；有 E ⇒ 不得 ungrounded。"""
    out: List[Violation] = []
    for index, claim in ctx.claims:
        malformed = any(
            claim.get(key) is not None and not isinstance(claim.get(key), list)
            for key in ("supporting_evidence", "refuting_evidence")
        )
        if malformed:
            continue  # 字段形状错误已由 V2 报出，这里不重复计
        refs = _string_refs(claim, "supporting_evidence") + _string_refs(claim, "refuting_evidence")
        status = claim.get("status")
        path = f"claims[{index}].status"
        if not refs:
            if status != UNGROUNDED:
                out.append(Violation(
                    "V3", path, f"无 E 引用时必须为 {UNGROUNDED}", status, _subject_of(claim),
                ))
        elif status == UNGROUNDED:
            out.append(Violation("V3", path, f"有 E 引用却标 {UNGROUNDED}", status, _subject_of(claim)))
    return out


def _v4(ctx: _Context) -> List[Violation]:
    """V4：每条 F 必须被 claim / experiment 的 known_flaws 引用。"""
    referenced: set = set()
    for _index, claim in ctx.claims:
        referenced.update(_string_refs(claim, "known_flaws"))
    for _index, experiment in ctx.experiments:
        referenced.update(_string_refs(experiment, "known_flaws"))

    out: List[Violation] = []
    for index, failure in ctx.failures:
        identifier = _id_of(failure)
        if identifier and identifier in referenced:
            continue
        out.append(Violation(
            "V4",
            f"failures[{index}]",
            "未被任何 claims[].known_flaws 或 experiments[].known_flaws 引用",
            identifier or None,
            _subject_of(failure),
        ))
    return out


def _v5(ctx: _Context) -> List[Violation]:
    """V5：epistemic_status 五值；Hypothesized / Unknown 不得作支持证据。"""
    out: List[Violation] = []
    allowed = "|".join(EPISTEMIC_STATUSES)
    for index, entry in ctx.evidence:
        status = entry.get("epistemic_status")
        if isinstance(status, str) and status.strip() in EPISTEMIC_STATUSES:
            continue
        out.append(Violation(
            "V5",
            f"evidence[{index}].epistemic_status",
            f"必须是 {allowed} 之一",
            status,
            _subject_of(entry),
        ))

    for index, claim in ctx.claims:
        refs = claim.get("supporting_evidence")
        if not isinstance(refs, list):
            continue
        for position, ref in enumerate(refs):
            if not _text_ok(ref):
                continue
            entry = ctx.evidence_by_id.get(ref.strip())
            if entry is None:
                continue
            status = entry.get("epistemic_status")
            status_text = status.strip() if isinstance(status, str) else ""
            if status_text in UNSUPPORTABLE_STATUSES:
                out.append(Violation(
                    "V5",
                    f"claims[{index}].supporting_evidence[{position}]",
                    f"指向 epistemic_status={status_text} 的证据，不得作为支持证据",
                    ref,
                    _subject_of(claim),
                ))
    return out


def _v6(ctx: _Context) -> List[Violation]:
    """V6：每条 H 的 niche 非空，且取值必须是 N1—N10 之一（QD archive 的前提）。"""
    out: List[Violation] = []
    for index, hypothesis in ctx.hypotheses:
        value = hypothesis.get("niche")
        if not _text_ok(value):
            detail = "为空（QD archive 的前提）" if _is_blank(value) else "必须是非空字符串"
            out.append(Violation(
                "V6", f"hypotheses[{index}].niche", detail, value, _subject_of(hypothesis),
            ))
            continue
        if value.strip() not in NICHES:
            out.append(Violation(
                "V6",
                f"hypotheses[{index}].niche",
                f"不是 N1—N10 之一（QD archive 的 niche 复用 preset 名，不引入第二套枚举）",
                value,
                _subject_of(hypothesis),
            ))
    return out


def _v13(ctx: _Context) -> List[Violation]:
    """V13：island ∈ {P1, P2, P3, P4, local}。"""
    out: List[Violation] = []
    for index, hypothesis in ctx.hypotheses:
        value = hypothesis.get("island")
        if _text_ok(value) and value.strip() in ISLANDS:
            continue
        detail = ("为空（必须标明由哪条轨产生）" if _is_blank(value)
                  else f"不是 {'|'.join(ISLANDS)} 之一")
        out.append(Violation("V13", f"hypotheses[{index}].island", detail, value, _subject_of(hypothesis)))
    return out


def _v14(ctx: _Context) -> List[Violation]:
    """V14：generation 是非负整数。"""
    out: List[Violation] = []
    for index, hypothesis in ctx.hypotheses:
        value = hypothesis.get("generation")
        ok = isinstance(value, int) and not isinstance(value, bool) and value >= 0
        if ok:
            continue
        out.append(Violation(
            "V14", f"hypotheses[{index}].generation",
            "必须是非负整数（0 = 初始候选，每次 R6 进化 +1；不接受 \"1\" 这类字符串）",
            value, _subject_of(hypothesis),
        ))
    return out


def _v15(ctx: _Context) -> List[Violation]:
    """V15：每个出现过的 niche 至少有一条 elite（QD archive 不塌成单点）。"""
    if not ctx.hypotheses:
        return []
    niches = {}
    for index, hypothesis in ctx.hypotheses:
        niche = hypothesis.get("niche")
        if not (_text_ok(niche) and niche.strip() in NICHES):
            continue
        entry = niches.setdefault(niche.strip(), {"elite": None, "first": index})
        if _text_ok(hypothesis.get("status")) and hypothesis["status"].strip() == "elite":
            if entry["elite"] is None:
                entry["elite"] = index
    out: List[Violation] = []
    for niche, entry in sorted(niches.items()):
        if entry["elite"] is None:
            out.append(Violation(
                "V15", f"hypotheses[{entry['first']}].niche",
                f"niche {niche} 没有任何 status: elite 的候选（QD archive 要求每 niche 留一个 elite）",
                niche, niche,
            ))
    return out


def _test_reference(
    rule: str, path: str, value: Any, ctx: _Context, subject: str,
) -> Optional[Violation]:
    """X 引用判定：存在的 X id 或字面量 TBD（V7 / V9 共用）。"""
    if not _text_ok(value):
        return Violation(rule, path, f"必须指向存在的 X 或字面量{TBD}", value, subject)
    target = value.strip()
    if target == TBD or target in ctx.experiment_by_id:
        return None
    return Violation(rule, path, f"指向不存在的 X（或写{TBD}）", value, subject)


def _v7(ctx: _Context) -> List[Violation]:
    """V7：U.cheapest_discriminating_test 指向存在的 X 或 TBD。"""
    out: List[Violation] = []
    for index, uncertainty in ctx.uncertainties:
        violation = _test_reference(
            "V7",
            f"uncertainties[{index}].cheapest_discriminating_test",
            uncertainty.get("cheapest_discriminating_test"),
            ctx,
            _subject_of(uncertainty, "question"),
        )
        if violation is not None:
            out.append(violation)
    return out


def _cycle_starts(parent_of: Dict[str, str]) -> List[str]:
    """返回每组环里**下标最小**的闭环节点（每个环只报一次）。"""
    state: Dict[str, int] = {node: 0 for node in parent_of}
    starts: List[str] = []
    for start in parent_of:
        if state[start] != 0:
            continue
        chain: List[str] = []
        node: Optional[str] = start
        while node is not None and state.get(node, 2) == 0:
            state[node] = 1
            chain.append(node)
            node = parent_of.get(node)
        if node is not None and state.get(node) == 1 and node in chain:
            starts.append(node)
        for visited in chain:
            state[visited] = 2
    return starts


def _v8(ctx: _Context) -> List[Violation]:
    """V8：X.parent 是存在的 X 或 null；树不得成环。"""
    out: List[Violation] = []
    parent_of: Dict[str, str] = {}

    for index, experiment in ctx.experiments:
        path = f"experiments[{index}].parent"
        subject = _subject_of(experiment)
        if "parent" not in experiment or experiment.get("parent") is None:
            continue  # 缺失 / null = 根节点
        parent = experiment.get("parent")
        if not _text_ok(parent):
            out.append(Violation("V8", path, "必须是存在的 X id 或 null", parent, subject))
            continue
        target = parent.strip()
        if target not in ctx.experiment_by_id:
            out.append(Violation("V8", path, "指向不存在的 X", parent, subject))
            continue
        if subject:
            parent_of[subject] = target

    for start in _cycle_starts(parent_of):
        index = ctx.experiment_index.get(start, 0)
        out.append(Violation(
            "V8",
            f"experiments[{index}].parent",
            "实验树成环（沿 parent 链回到自身）",
            parent_of.get(start),
            start,
        ))
    return out


def _v9(ctx: _Context) -> List[Violation]:
    """V9：assurance[].kill_condition 非空；discriminating_test 指向 X 或 TBD。"""
    out: List[Violation] = []
    for index, entry in ctx.assurance:
        subject = _subject_of(entry, "discriminating_test")
        kill_condition = entry.get("kill_condition")
        if not _text_ok(kill_condition):
            detail = "为空" if _is_blank(kill_condition) else "必须是非空字符串"
            out.append(Violation(
                "V9", f"assurance[{index}].kill_condition", detail, kill_condition, subject,
            ))
        violation = _test_reference(
            "V9",
            f"assurance[{index}].discriminating_test",
            entry.get("discriminating_test"),
            ctx,
            subject,
        )
        if violation is not None:
            out.append(violation)
    return out


def _v10(ctx: _Context) -> List[Violation]:
    """V10：repairs[] 每条齐备 flaw / disposition / state_delta / closure（+ §5 枚举）。"""
    out: List[Violation] = []
    for index, record in ctx.repairs:
        base = f"repairs[{index}]"
        subject = _subject_of(record, "flaw")
        for key in ("flaw", "disposition", "state_delta", "closure"):
            value = record.get(key)
            if _text_ok(value):
                continue
            detail = "为空（该轮未闭环）" if _is_blank(value) else "必须是非空字符串"
            out.append(Violation("V10", f"{base}.{key}", detail, value, subject))

        disposition = record.get("disposition")
        if _text_ok(disposition) and disposition.strip() not in DISPOSITIONS:
            out.append(Violation(
                "V10",
                f"{base}.disposition",
                f"不是处置枚举之一（{'|'.join(DISPOSITIONS)}）",
                disposition,
                subject,
            ))
        closure = record.get("closure")
        if _text_ok(closure) and closure.strip() not in CLOSURES:
            out.append(Violation(
                "V10",
                f"{base}.closure",
                f"不是关闭枚举之一（{'|'.join(CLOSURES)}）",
                closure,
                subject,
            ))
    return out



def _v11(ctx: _Context) -> List[Violation]:
    """V11：stage == "X2" ⇒ claim_targeted 必须为空数组（X2 只做基线校准）。"""
    out: List[Violation] = []
    for index, record in ctx.experiments:
        stage = record.get("stage")
        if not (_text_ok(stage) and stage.strip() == "X2"):
            continue
        targets = record.get("claim_targeted")
        if not isinstance(targets, list):
            targets = []
        nonblank = [t for t in targets if _text_ok(t)]
        if nonblank:
            out.append(Violation(
                "V11",
                f"experiments[{index}].claim_targeted",
                f"stage=X2（基线校准）不得承担 claim 判别，却给了 {len(nonblank)} 条 claim_targeted",
                targets,
                _subject_of(record, "id"),
            ))
    return out


def _v12(ctx: _Context) -> List[Violation]:
    """V12：status == "failed" ⇒ 必须有某条 F.referenced_by 含该 X 的非空 id。"""
    referenced = set()
    for _, record in ctx.failures:
        ids = record.get("referenced_by")
        if isinstance(ids, list):
            for item in ids:
                if _text_ok(item):
                    referenced.add(str(item).strip())
    out: List[Violation] = []
    for index, record in ctx.experiments:
        status = record.get("status")
        if not (_text_ok(status) and status.strip() == "failed"):
            continue
        xid = record.get("id")
        if not (_text_ok(xid) and str(xid).strip() in referenced):
            out.append(Violation(
                "V12",
                f"experiments[{index}].status",
                "status=failed 的节点必须有一条 failures[].referenced_by 引用它（失败不得消失）",
                record.get("status"),
                _subject_of(record, "id"),
            ))
    return out


CHECKS: Dict[str, Callable[[_Context], List[Violation]]] = {
    "V1": _v1, "V2": _v2, "V3": _v3, "V4": _v4, "V5": _v5,
    "V6": _v6, "V7": _v7, "V8": _v8, "V9": _v9, "V10": _v10,
    "V11": _v11, "V12": _v12,
    "V13": _v13, "V14": _v14, "V15": _v15,
}


# ---------------------------------------------------------------------------
# 校验入口
# ---------------------------------------------------------------------------

def _environment_report(source: str, message: str, kind: str) -> Report:
    return Report(
        ok=False,
        exit_code=EXIT_ENV,
        source=source,
        violations=[],
        checked={},
        error=message,
        error_kind=kind,
    )


def check_state(doc: Any, source: str = "<memory>") -> Report:
    """校验一份已解析的 state（dict）。返回 Report（不抛异常、不写文件）。"""
    error, effective, unwrapped_from = structure_error(doc)
    if error is not None:
        return _environment_report(source, error, "structure")

    ctx = _Context.build(effective)
    violations: List[Violation] = []
    for rule in RULE_ORDER:
        violations.extend(CHECKS[rule](ctx))

    checked = {
        "claims": len(ctx.claims),
        "evidence": len(ctx.evidence),
        "assumptions": len(ctx.assumptions),
        "hypotheses": len(ctx.hypotheses),
        "experiments": len(ctx.experiments),
        "literature": len(ctx.literature),
        "failures": len(ctx.failures),
        "uncertainties": len(ctx.uncertainties),
        "assurance": len(ctx.assurance),
        "repairs": len(ctx.repairs),
    }
    return Report(
        ok=not violations,
        exit_code=EXIT_OK if not violations else EXIT_HARD,
        source=source,
        violations=violations,
        checked=checked,
        unwrapped_from=unwrapped_from,
    )


def check_file(path: Path) -> Report:
    """读文件 → 解析 → 校验。文件层问题一律退出码 4。"""
    source = str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _environment_report(source, f"state 文件不存在：{path}", "missing-file")
    except IsADirectoryError:
        return _environment_report(source, f"路径是目录，不是 state 文件：{path}", "not-a-file")
    except UnicodeDecodeError as exc:
        return _environment_report(source, f"state 文件不是 UTF-8 文本：{exc}", "bad-encoding")
    except OSError as exc:
        return _environment_report(source, f"state 文件读不到：{exc}", "unreadable")

    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return _environment_report(
            source, f"state 文件不是合法 JSON：{exc.msg}（行 {exc.lineno} 列 {exc.colno}）", "invalid-json",
        )
    return check_state(doc, source=source)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    """参数错误退出码必须是 1，不能与「硬违规(3)」「环境不满足(4)」混淆。"""

    def error(self, message: str):  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="state_check.py",
        description="Research World Model（R1）机械闸门：V1—V12 引用完整性审计"
                    "（docs/r-architecture-wave1-spec.md §2.3）",
    )
    parser.add_argument("state", nargs="?", default=None,
                        help="state JSON 路径（如 templates/research-state.template.json）")
    parser.add_argument("--check", action="store_true",
                        help="只校验不写入（默认行为即如此；显式化以便与 refs_index.py 口径一致）")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON（stdout 只有 JSON）")
    parser.add_argument("--quiet", action="store_true", help="只打印汇总行，不逐条打印违规")
    parser.add_argument("--selftest", action="store_true", help="跑内置自检（V1—V12 全覆盖）")
    parser.add_argument("--list-rules", action="store_true", help="列出 V1—V10 与判据")
    return parser


def emit(report: Report, as_json: bool, quiet: bool) -> None:
    """输出口径：--json 时 stdout 只有 JSON；环境问题走 stderr；违规逐条走 stdout。"""
    if as_json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        return
    if report.error is not None:
        print(report.summary(), file=sys.stderr)
        return
    if not quiet:
        for violation in report.violations:
            print(violation.render())
    print(report.summary())
    if report.violations and not quiet:
        print("[hint] 每条违规形如「规则号 硬违规 · JSON 路径 判据 · 现值」；"
              "规则定义见 docs/r-architecture-wave1-spec.md §2.3")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)

    if args.selftest:
        return selftest()
    if args.list_rules:
        for rule in RULE_ORDER:
            print(f"{rule:4} 硬  {RULES[rule]}")
        return EXIT_OK
    if not args.state:
        build_parser().error("缺少 <state.json> 路径（或用 --selftest / --list-rules）")

    report = check_file(Path(args.state).expanduser())
    emit(report, args.json, args.quiet)
    return report.exit_code


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

def _selftest_state() -> Dict[str, Any]:
    """自检用的最小合法 world model（覆盖 V1—V10 的通过侧）。"""
    return {
        "_schema": "research-idea-pipeline/research-state@1",
        "claims": [{
            "id": "C0", "statement": "adaptation modifies prior parameters",
            "parent": None, "subclaims": [], "status": "supported",
            "supporting_evidence": ["E1"], "refuting_evidence": [],
            "nearest_alternative": "generic fine-tuning",
            "falsifier": "若 R2 与 R1 结果近似则 C0 不成立",
            "scope": "brain MRI / acceleration=4", "known_flaws": ["F1"],
        }],
        "evidence": [{
            "id": "E1", "kind": "experiment", "supports": ["C0"], "contradicts": [],
            "strength": "strong", "scope": "brain MRI / acceleration=4",
            "epistemic_status": "Observed", "source_ref": "X1",
        }],
        "assumptions": [{
            "id": "AS1", "statement": "adaptation must modify prior parameters",
            "status": "explicit", "challenged_by": [], "if_false": "C0 需改写",
        }],
        "hypotheses": [{
            "id": "H1", "statement": "prior-parameter adaptation beats fine-tuning",
            "structural_signature": {"assumption_distance": 2},
            "novelty_source": "assumption-breaking", "theory_lens": "transfer",
            "nearest_prior": "LoRA", "falsifier": "R2 不降级",
            "expected_information_gain": 0.4, "status": "elite", "niche": "N2", "island": "P2", "generation": 0,
        }],
        "experiments": [{
            "id": "X1", "parent": None, "stage": "X1", "claim_targeted": ["C0"],
            "alternative_targeted": [], "code_commit": "abc123", "data_split": "fastMRI val",
            "seed": 0, "metric": "PSNR", "result": "…", "interpretation": "…",
            "unexpected": [], "known_flaws": ["F1"], "next_branches": [], "status": "done",
        }],
        "literature": [{
            "id": "LIT1", "ref": "[Author, 2024]", "relation": "shares-assumption",
        }],
        "failures": [{
            "id": "F1", "kind": "inconclusive", "what": "R2 未分离", "why": "样本不足",
            "referenced_by": ["C0", "X1"],
        }],
        "uncertainties": [{
            "id": "U1", "question": "机制在 R2 是否失效", "importance": "critical",
            "uncertainty": "high", "cheapest_discriminating_test": "X1", "status": "open",
        }],
        "assurance": [{
            "kill_condition": "若 X1 在 R2 上不降级则 kill 该机制分支",
            "discriminating_test": "X1",
        }],
        "repairs": [{
            "flaw": "C0 not supported", "disposition": "RUN_TEST",
            "state_delta": "U1→X1 已排队；C0.status→partially-supported", "closure": "RESOLVED",
        }],
    }


def selftest() -> int:
    failures: List[str] = []
    detected: set = set()

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"  ok   {name}")
        else:
            failures.append(f"{name} {detail}")
            print(f"  FAIL {name} {detail}")

    base = _selftest_state()

    def report_with(mutate: Callable[[Dict[str, Any]], None]) -> Report:
        doc = copy.deepcopy(base)
        mutate(doc)
        report = check_state(doc, source="<selftest>")
        detected.update(report.rules())
        return report

    print(f"state_check.py 自检（V1—V{RULE_ORDER[-1][1:]}）：")
    clean = check_state(base, source="<selftest>")
    check("合法 state 退出码 0", clean.exit_code == EXIT_OK and clean.ok)
    check("合法 state 无违规", clean.violations == [])
    check("对象计数齐全", clean.checked.get("claims") == 1 and clean.checked.get("repairs") == 1)

    v1 = report_with(lambda d: d["claims"][0].update(falsifier=""))
    check("V1 falsifier 为空 → 3", v1.exit_code == EXIT_HARD and v1.rules() == ["V1"])
    check("V1 违规行含路径与现值",
          v1.violations[0].path == "claims[0].falsifier" and "claims[0].falsifier" in v1.violations[0].render())

    v2 = report_with(lambda d: d["claims"][0].update(supporting_evidence=["E9"]))
    check("V2 悬空 E 引用 → 3", v2.exit_code == EXIT_HARD and v2.rules() == ["V2"])
    check("V2 违规行含现值 E9", "E9" in v2.violations[0].render())

    v3a = report_with(lambda d: d["claims"][0].update(supporting_evidence=[]))
    check("V3 无 E 引用却 supported → 3", v3a.exit_code == EXIT_HARD and v3a.rules() == ["V3"])
    v3b = report_with(lambda d: d["claims"][0].update(status="ungrounded"))
    check("V3 有 E 却标 ungrounded → 3", v3b.exit_code == EXIT_HARD and v3b.rules() == ["V3"])

    v4 = report_with(lambda d: (d["claims"][0].update(known_flaws=[]),
                                d["experiments"][0].update(known_flaws=[])))
    check("V4 F 无人引用 → 3", v4.exit_code == EXIT_HARD and v4.rules() == ["V4"])

    v5a = report_with(lambda d: d["evidence"][0].update(epistemic_status="Verified"))
    check("V5 非法 epistemic_status → 3", v5a.exit_code == EXIT_HARD and v5a.rules() == ["V5"])
    v5b = report_with(lambda d: d["evidence"][0].update(epistemic_status="Hypothesized"))
    check("V5 Hypothesized 作支持证据 → 3", v5b.exit_code == EXIT_HARD and v5b.rules() == ["V5"])

    v6 = report_with(lambda d: d["hypotheses"][0].update(niche=""))
    check("V6 niche 为空 → 3", v6.exit_code == EXIT_HARD and v6.rules() == ["V6"])

    v7 = report_with(lambda d: d["uncertainties"][0].update(cheapest_discriminating_test="X99"))
    check("V7 指向不存在的 X → 3", v7.exit_code == EXIT_HARD and v7.rules() == ["V7"])
    check("V7 TBD 合法",
          report_with(lambda d: d["uncertainties"][0].update(cheapest_discriminating_test="TBD")).exit_code == EXIT_OK)

    v8a = report_with(lambda d: d["experiments"][0].update(parent="X99"))
    check("V8 parent 不存在 → 3", v8a.exit_code == EXIT_HARD and v8a.rules() == ["V8"])

    def _cycle(doc: Dict[str, Any]) -> None:
        second = copy.deepcopy(doc["experiments"][0])
        second.update(id="X2", parent="X1")
        doc["experiments"].append(second)
        doc["experiments"][0].update(parent="X2")

    v8b = report_with(_cycle)
    check("V8 树成环 → 3（每环一条）",
          v8b.exit_code == EXIT_HARD and v8b.rules() == ["V8"] and len(v8b.violations) == 1)

    v9a = report_with(lambda d: d["assurance"][0].update(kill_condition=""))
    check("V9 kill_condition 为空 → 3", v9a.exit_code == EXIT_HARD and v9a.rules() == ["V9"])
    v9b = report_with(lambda d: d["assurance"][0].update(discriminating_test="X99"))
    check("V9 discriminating_test 不存在 → 3", v9b.exit_code == EXIT_HARD and v9b.rules() == ["V9"])

    v10a = report_with(lambda d: d["repairs"].__setitem__(0, {"flaw": "C0 not supported"}))
    check("V10 只写 flaw → 3（spec §7 指定场景）",
          v10a.exit_code == EXIT_HARD and v10a.rules() == ["V10"]
          and any("disposition" in v.path for v in v10a.violations))
    v10b = report_with(lambda d: d["repairs"][0].update(disposition="FIX"))
    check("V10 处置枚举不合法 → 3", v10b.exit_code == EXIT_HARD and v10b.rules() == ["V10"])
    v10c = report_with(lambda d: d["repairs"][0].update(closure="DONE"))
    check("V10 关闭枚举不合法 → 3", v10c.exit_code == EXIT_HARD and v10c.rules() == ["V10"])

    v11 = report_with(lambda d: d["experiments"][0].update(stage="X2"))
    check("V11 X2 承担 claim 判别 → 3",
          v11.exit_code == EXIT_HARD and v11.rules() == ["V11"]
          and v11.violations[0].path == "experiments[0].claim_targeted")
    v11ok = report_with(lambda d: d["experiments"][0].update(stage="X2", claim_targeted=[]))
    check("V11 合法反例：X2 + 空 claim_targeted → 0",
          v11ok.exit_code == EXIT_OK and v11ok.violations == [])

    def _unrecorded_failure(d):
        d["experiments"].append({
            "id": "X99", "parent": None, "stage": "X3", "claim_targeted": ["C0"],
            "alternative_targeted": [], "code_commit": "c", "data_split": "s", "seed": 0,
            "metric": "m", "result": "r", "interpretation": "i", "unexpected": [],
            "known_flaws": [], "next_branches": [], "status": "failed",
        })

    v12 = report_with(_unrecorded_failure)
    check("V12 failed 未被 failures[] 记录 → 3",
          v12.exit_code == EXIT_HARD and v12.rules() == ["V12"]
          and v12.violations[0].path == "experiments[1].status")
    v12ok = report_with(lambda d: d["experiments"][0].update(status="failed"))
    check("V12 合法反例：failed 且已被 F 引用 → 0",
          v12ok.exit_code == EXIT_OK and v12ok.violations == [])

    v13 = report_with(lambda d: d["hypotheses"][0].update(island="PX"))
    check("V13 island 非法 → 3", v13.exit_code == EXIT_HARD and v13.rules() == ["V13"])
    v13ok = report_with(lambda d: d["hypotheses"][0].update(island="local"))
    check("V13 合法反例：island=local → 0", v13ok.exit_code == EXIT_OK and v13ok.violations == [])

    v14 = report_with(lambda d: d["hypotheses"][0].update(generation="1"))
    check("V14 generation 是字符串 → 3", v14.exit_code == EXIT_HARD and v14.rules() == ["V14"])
    v14b = report_with(lambda d: d["hypotheses"][0].update(generation=-1))
    check("V14 generation 为负 → 3", v14b.exit_code == EXIT_HARD and v14b.rules() == ["V14"])

    v6b = report_with(lambda d: d["hypotheses"][0].update(niche="assumption-breaking"))
    check("V6 niche 不在 N1—N10 → 3", v6b.exit_code == EXIT_HARD and v6b.rules() == ["V6"])

    def _no_elite(d):
        d["hypotheses"].append(dict(d["hypotheses"][0], id="H2", niche="N5", status="active", generation=0))
    v15 = report_with(_no_elite)
    check("V15 niche N5 无 elite → 3", v15.exit_code == EXIT_HARD and v15.rules() == ["V15"])

    check(f"自检覆盖 V1—V{max(RULE_ORDER, key=lambda r: int(r[1:]))[1:]}", set(RULE_ORDER) - detected == set(),
          f"未覆盖 {sorted(set(RULE_ORDER) - detected)}")

    check("缺八类数组 → 4", check_state({"foo": 1}).exit_code == EXIT_ENV)
    check("根节点非对象 → 4", check_state([1, 2, 3]).exit_code == EXIT_ENV)
    check("数组字段类型错 → 4", check_state({"claims": "nope"}).exit_code == EXIT_ENV)
    check("缺 assurance/repairs = 空数组（0）",
          check_state({"claims": []}).exit_code == EXIT_OK)
    check("包装键自动解包（0）", check_state({"world_model": base}).exit_code == EXIT_OK and
          check_state({"world_model": base}).unwrapped_from == "world_model")

    # 文件层：缺文件 / 非法 JSON 都必须退出码 4（用临时文件，不联网）
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        missing = tmp_dir / f"__selftest_missing_{uuid.uuid4().hex}.json"
        check("缺文件 → 4", main([str(missing), "--quiet"]) == EXIT_ENV)

        broken = tmp_dir / "broken.json"
        broken.write_text("{ not json", encoding="utf-8")
        check("非法 JSON → 4", main([str(broken), "--quiet"]) == EXIT_ENV)

        good = tmp_dir / "state.json"
        good.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
        check("文件路径端到端 → 0", main([str(good), "--quiet"]) == EXIT_OK)

    if failures:
        print(f"selftest FAILED（{len(failures)} 项）")
        return EXIT_ERROR
    print("selftest OK")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
