#!/usr/bin/env python3
"""structural_equivalence_check.py — Structural Equivalence / near-neighbor audit 的机械闸门。

**它只验证「审计做没做完整」，不验证「idea 到底新不新」。**

四项职责（与 `references/structural-equivalence-policy.md` §12 与 §30 逐字对应）：

    1. 审计是否完整；
    2. 引用是否存在；
    3. schema 是否满足；
    4. claim 强度是否有对应审计。

两层规则：

    `EQ1`—`EQ13`   结构等价契约（policy §12.1）
    `NN1`—`NN13`   near-neighbor 判断层（policy §30）

**没有任何规则形如「idea must be novel」。** LLM 不是 scientific novelty 的 truth oracle，
机械闸门也**不得**代替它宣判。本脚本只把「没有审计就主张强 novelty」这类**可判定的**缺口拦下。

**`NN` 规则只验证审计纪律**：对应矩阵是否完整、枚举是否合法、`evidence_span` 是否存在、
`UNRESOLVED` 是否被保留、stripping / mapping 是否按 operator 触发、claim 强度是否超过上限。
它**不**决定「`H` 与 `P` 是否真的结构等价」。

用法
----

    python3 scripts/structural_equivalence_check.py --artifact <audit.json>
    python3 scripts/structural_equivalence_check.py --route <routes/R>
    python3 scripts/structural_equivalence_check.py --selftest
    python3 scripts/structural_equivalence_check.py --list-rules

`--artifact` 只校验单份 artifact（EQ4—EQ11、EQ13）。
`--route` 额外做 state 交叉校验：artifact ↔ `assurance[]` ↔ `LIT` 引用（EQ1—EQ3、EQ12）。

退出码（与仓库既有脚本一致）
---------------------------

    0  全部通过
    1  参数错误
    3  存在硬违规
    4  环境不满足（文件缺失 / JSON 非法 / 顶层结构不符）

verdict 只看**退出码与最后一行**（`PASS` / `FAIL`）；前面的逐条输出只用于诊断。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA = "research-idea-pipeline/structural-equivalence-audit@2"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_HARD = 3
EXIT_ENV = 4

HARD = "hard"
SEVERITY_LABEL: Dict[str, str] = {HARD: "硬违规"}

# ---------------------------------------------------------------------------
# 冻结枚举（权威定义见 references/structural-equivalence-policy.md §3 / §6 / §7 / §8）
# 改动这里必须同轮改 policy、模板、fixture 与引用该 policy 的 phase-*.md。
# ---------------------------------------------------------------------------

FACETS: Tuple[str, ...] = (
    "problem",
    "setting",
    "observables",
    "available_information",
    "target_or_latent_quantity",
    "assumptions",
    "adaptation_or_intervention_object",
    "objective",
    "mechanism",
    "information_flow",
    "theory_object",
    "predictions_or_guarantees",
    "evaluation_target",
    "boundary_or_failure_regime",
)

RELATIONS: Tuple[str, ...] = (
    "observes",
    "requires",
    "assumes",
    "estimates",
    "transforms",
    "optimizes",
    "constrains",
    "implies",
    "predicts",
    "evaluated_by",
    "fails_under",
)

VERDICTS: Tuple[str, ...] = (
    "equivalent",
    "subsumed-by-prior",
    "reframing-only",
    "transfer-only",
    "component-delta",
    "mechanism-delta",
    "formulation-delta",
    "boundary-delta",
    "paradigm-candidate",
    "uncertain",
)

# 强 verdict：需要 minimal delta + collapse test + differentiating consequence。
STRONG_VERDICTS: Tuple[str, ...] = (
    "mechanism-delta", "formulation-delta", "boundary-delta", "paradigm-candidate",
)
# 弱 verdict：不得支撑 paradigm novelty 声称。
WEAK_VERDICTS: Tuple[str, ...] = (
    "equivalent", "subsumed-by-prior", "reframing-only", "transfer-only", "component-delta",
)

CLAIMED_LEVELS: Tuple[str, ...] = (
    "none", "transfer-only", "component-delta", "mechanism-delta",
    "formulation-delta", "boundary-delta", "paradigm-candidate",
)

COLLAPSE_RESULTS: Tuple[str, ...] = ("collapses", "partially-collapses", "does-not-collapse")
RETRIEVAL_STATUSES: Tuple[str, ...] = ("sufficient", "retrieval-insufficient")
STAGES: Tuple[str, ...] = ("R7", "R13")

LOAD_BEARING_KEYS: Tuple[str, ...] = (
    "changed_information", "changed_assumptions", "changed_mechanism",
    "changed_predictions", "changed_boundary",
)

# §6.2 相容表：collapse_result → 允许的 verdict。
COLLAPSE_ALLOWED: Dict[str, Tuple[str, ...]] = {
    "collapses": WEAK_VERDICTS,
    "partially-collapses": VERDICTS,
    "does-not-collapse": (
        "mechanism-delta", "formulation-delta", "boundary-delta",
        "paradigm-candidate", "uncertain",
    ),
}

# §12.2 兼容表：verdict → 允许的 claimed_novelty_level（只能等强或更弱）。
_CLAIM_LADDER: Tuple[str, ...] = (
    "none", "transfer-only", "component-delta",
    "mechanism-delta", "formulation-delta", "boundary-delta", "paradigm-candidate",
)
_UP_TO: Dict[str, str] = {
    "equivalent": "none",
    "subsumed-by-prior": "none",
    "reframing-only": "none",
    "transfer-only": "transfer-only",
    "component-delta": "component-delta",
    "mechanism-delta": "mechanism-delta",
    "formulation-delta": "formulation-delta",
    "boundary-delta": "boundary-delta",
    "paradigm-candidate": "paradigm-candidate",
    "uncertain": "component-delta",
}


def allowed_claims(verdict: str) -> Tuple[str, ...]:
    """给定 verdict，返回允许的 claimed_novelty_level（只能等强或更弱）。"""
    ceiling = _UP_TO.get(verdict)
    if ceiling is None:
        return ()
    return _CLAIM_LADDER[: _CLAIM_LADDER.index(ceiling) + 1]


# ---------------------------------------------------------------------------
# Near-neighbor 判断层（权威定义见 policy §15—§24 与 §30 的 NN 表）
# ---------------------------------------------------------------------------

NEAR_NEIGHBOR_VERDICTS: Tuple[str, ...] = (
    "duplicate-equivalent", "reframing-neighbor", "transfer-neighbor",
    "component-neighbor", "mechanism-neighbor",
    "structural-delta", "structural-delta-strong", "uncertain",
)
NEIGHBOR_FAMILY: Tuple[str, ...] = (
    "duplicate-equivalent", "reframing-neighbor", "transfer-neighbor",
    "component-neighbor", "mechanism-neighbor",
)
DELTA_FAMILY: Tuple[str, ...] = ("structural-delta", "structural-delta-strong")

CORRESPONDENCE_RELATIONS: Tuple[str, ...] = ("MATCH", "DIFFERENT", "UNRESOLVED")
PROVENANCE: Tuple[str, ...] = ("EXPLICIT", "DERIVED", "INFERRED", "UNKNOWN")
STRONG_PROVENANCE: Tuple[str, ...] = ("EXPLICIT", "DERIVED")

LOCAL_MODIFICATION_KINDS: Tuple[str, ...] = (
    "loss-replacement", "module-replacement", "regularizer", "weighting", "optimizer",
    "masking", "adapter", "schedule", "architectural-block", "hyperparameter",
    "implementation-detail",
)
NOVEL_CONSEQUENCE_KINDS: Tuple[str, ...] = (
    "prediction", "theorem", "boundary", "algorithm", "experiment",
)
THEORY_NEW_STRUCTURE_KINDS: Tuple[str, ...] = (
    "new-assumption", "new-identifiable-object", "new-prediction", "new-impossibility",
    "new-algorithmic-consequence", "new-discriminating-experiment",
)
THEORY_STRIPPING_CONCLUSIONS: Tuple[str, ...] = (
    "theory-relabeling-risk", "reframing-only", "theory-substantive", "not-applicable",
)
REMOTE_ANALOGY_CONCLUSIONS: Tuple[str, ...] = (
    "structural-novelty", "explanation-only", "transfer", "interpretation", "not-applicable",
)
REMOVAL_CONCLUSIONS: Tuple[str, ...] = ("component-local-delta", "load-bearing-delta", "unresolved")
MAPPING_COMPLETENESS: Tuple[str, ...] = ("full", "partial", "failed")
TRUST_BASES: Tuple[str, ...] = (
    "source-span", "equation", "algorithm", "code", "literature",
    "executable-counterfactual", "discriminating-experiment", "expert-validation",
)
# §22「反事实幻觉」：声称不坍缩必须有可执行证据，而不是 LLM 断言。
EXECUTABLE_TRUST: Tuple[str, ...] = (
    "equation", "algorithm", "code", "executable-counterfactual", "discriminating-experiment",
)
NULL_HYPOTHESIS_STATEMENT = "candidate is structurally subsumed by an existing prior"

# §23.2 相容表：near_neighbor_verdict → 允许的 verdict。
NN_ALLOWED_VERDICTS: Dict[str, Tuple[str, ...]] = {
    "duplicate-equivalent": ("equivalent", "subsumed-by-prior"),
    "reframing-neighbor": ("reframing-only",),
    "transfer-neighbor": ("transfer-only",),
    "component-neighbor": ("component-delta",),
    "mechanism-neighbor": ("mechanism-delta",),
    "structural-delta": ("formulation-delta", "boundary-delta"),
    "structural-delta-strong": ("paradigm-candidate",),
    "uncertain": ("uncertain",),
}
# §23.2 相容表：near_neighbor_verdict → claimed_novelty_level 上限。
NN_CLAIM_CEILING: Dict[str, str] = {
    "duplicate-equivalent": "none",
    "reframing-neighbor": "none",
    "transfer-neighbor": "transfer-only",
    "component-neighbor": "component-delta",
    "mechanism-neighbor": "mechanism-delta",
    "structural-delta": "boundary-delta",
    "structural-delta-strong": "paradigm-candidate",
    "uncertain": "component-delta",
}
# §21.1 关键 facet：这三项出现大量 INFERRED / UNKNOWN 时不得给强 novelty verdict。
KEY_FACETS_FOR_TRUST: Tuple[str, ...] = ("mechanism", "assumptions", "predictions_or_guarantees")
# §29 禁止用 scalar 直接决定 novelty。
SCALAR_DECISION_KEYS: Tuple[str, ...] = (
    "structural_distance", "similarity", "cosine", "novelty_score", "scalar_distance",
)
RETRIEVAL_HEURISTIC_USE = "retrieval-clustering-only"
# operator → 必做的 stripping / mapping（V16 的十二算子之一）
THEORY_OPERATOR = "theory_lens"
REMOTE_ANALOGY_OPERATOR = "remote_analogy"


def nn_allowed_claims(near_verdict: str) -> Tuple[str, ...]:
    """给定 near_neighbor_verdict，返回允许的 claimed_novelty_level。"""
    ceiling = NN_CLAIM_CEILING.get(near_verdict)
    if ceiling is None:
        return ()
    return _CLAIM_LADDER[: _CLAIM_LADDER.index(ceiling) + 1]


# "changed_*" 被视为「没有真实改变」的字面量。
UNCHANGED_LITERALS: Tuple[str, ...] = ("unchanged", "none", "n/a", "无", "不变", "未变")

# §11.1 未发现结构等价前作时**不得**出现的字面量。
FORBIDDEN_NOVELTY_PHRASES: Tuple[str, ...] = (
    "no prior work exists", "unprecedented",
    "没人做过", "首次", "前所未有", "无人研究", "该方向空白", "该方向是空白",
)
_ASCII_WORD_PHRASES: Tuple[str, ...] = ("first",)
# §11.1 唯一合法说法的标志。
HEDGE_MARKERS: Tuple[str, ...] = ("retrieved literature", "据本次检索未见")

AUDIT_DIR = "assurance/structural-equivalence"
FINGERPRINT_DIR = "populations/fingerprints"
AUDIT_REF_PATTERN = re.compile(
    r"^\.research-idea-pipeline/routes/[^/]+/assurance/structural-equivalence/H\d+"
    r"(?:\.sena2)?\.json$"
)
_ID_H = re.compile(r"^H\d+$")
_ID_LIT = re.compile(r"^LIT\d+$")
_ID_TARGET = re.compile(r"^(?:H|C)\d+$")

# ---------------------------------------------------------------------------
# 规则表（与 policy §12.1 逐字对应；测试会做两处逐字比对）
# ---------------------------------------------------------------------------

RULES: Dict[str, str] = {
    "EQ1": "声称为强 novelty 的 candidate 必须有 SENA artifact，且有对应 assurance[].audit_ref",
    "EQ2": "candidate 指向的 H 必须在 state 中存在",
    "EQ3": "closest_priors 与 evidence 的每个 LIT 必须在 state 中存在",
    "EQ4": "closest_priors 非空，或 retrieval_status 为 retrieval-insufficient",
    "EQ5": "domain_aware_alignment 完整（十四个 facet + typed relations 可解析）",
    "EQ6": "domain_stripped_alignment 完整，且不含 domain_terms",
    "EQ7": "minimal_structural_delta 与 load_bearing_analysis 在强 verdict 下完整",
    "EQ8": "counterfactual_collapse 完整，且与 verdict 相容",
    "EQ9": "differentiating_consequences 与 discriminating_tests 在强 verdict 下完整",
    "EQ10": "blind_spots 非空；未发现等价时 novelty_boundary 措辞合法",
    "EQ11": "verdict 属于十个冻结值",
    "EQ12": "audit_ref 指向合法 Control Plane artifact 路径，且与磁盘 artifact 双向一致",
    "EQ13": "更强的 claimed_novelty_level 不得与更弱的 verdict 冲突",
    "NN1": "correspondence 必须完整：十四个 facet 全在，且不含额外键",
    "NN2": "correspondence 每项的 relation / provenance 必须在冻结枚举内，且 evidence_span 非空",
    "NN3": "UNRESOLVED 必须被保留；load-bearing facet 出现 UNRESOLVED 时禁止 structural-delta 与 structural-delta-strong，出现 2 个及以上时必须为 uncertain",
    "NN4": "load_bearing_facets 必须非空且是十四个 facet 的子集",
    "NN5": "关键结论不得主要依赖 INFERRED；load-bearing facet 中 EXPLICIT / DERIVED 少于一半时禁止 structural-delta，且 trust_basis 必须非空、collapse_result 为 does-not-collapse 时另需 equation / algorithm / code / executable-counterfactual / discriminating-experiment 之一",
    "NN6": "local_neighborhood_test 必须完整；neighbor_confirmed 为 true 时 near_neighbor_verdict 必须是 neighbor 家族",
    "NN7": "removal_test 必须完整；结论为 component-local-delta 时 near_neighbor_verdict 必须是 neighbor 家族",
    "NN8": "null_hypothesis 必须完整且 statement 逐字；mapping_completeness 为 full 时禁止 structural-delta",
    "NN9": "minimal_delta_set 在 delta 家族下必须非空且 sufficient_alone 为 true；structural-delta-strong 另需至少两种不同的 novel_consequence_kinds 且含 experiment 或 boundary",
    "NN10": "theory_stripping 必须按 operator 触发；结论为 theory-relabeling-risk 时 near_neighbor_verdict 只允许 reframing-neighbor / duplicate-equivalent / uncertain",
    "NN11": "remote_analogy_mapping 必须按 operator 触发；added_structure 为 false 时结论不得是 structural-novelty",
    "NN12": "near_neighbor_verdict 必须与 verdict 相容，且 claimed_novelty_level 不得超过其上限",
    "NN13": "禁止任何 scalar 决定 novelty；retrieval_heuristic 的 use 必须逐字为 retrieval-clustering-only",
}
RULE_ORDER: List[str] = list(RULES)

# artifact 模式跑的规则；其余四条需要 research-state.json，只在 route 模式跑。
ROUTE_ONLY_RULES: Tuple[str, ...] = ("EQ1", "EQ2", "EQ3", "EQ12")


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    rule: str
    path: str
    detail: str
    value: Any = None
    subject: str = ""
    severity: str = HARD

    def render(self) -> str:
        shown = "" if self.value is None else f" · 现值 {_shorten(self.value)}"
        return f"{self.rule} {SEVERITY_LABEL[self.severity]} · {self.path} {self.detail}{shown}"


@dataclass
class Report:
    source: str
    violations: List[Violation] = field(default_factory=list)
    env_error: Optional[str] = None
    checked: int = 0

    def add(self, rule: str, path: str, detail: str, value: Any = None, subject: str = "") -> None:
        self.violations.append(Violation(rule, path, detail, value, subject))

    def rules(self) -> List[str]:
        seen: List[str] = []
        for violation in self.violations:
            if violation.rule not in seen:
                seen.append(violation.rule)
        return sorted(seen, key=RULE_ORDER.index)

    def rule_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for violation in self.violations:
            counts[violation.rule] = counts.get(violation.rule, 0) + 1
        return counts

    def summary(self) -> str:
        if self.env_error:
            return f"{self.source} 环境不满足：{self.env_error}（exit={EXIT_ENV}）"
        if not self.violations:
            return f"{self.source} 通过：{self.checked} 项检查，0 硬违规（exit={EXIT_OK}）"
        counts = "、".join(f"{rule}×{n}" for rule, n in sorted(self.rule_counts().items(),
                                                              key=lambda kv: RULE_ORDER.index(kv[0])))
        return f"{self.source} 存在硬违规：{len(self.violations)} 处（{counts}）"

    def exit_code(self) -> int:
        if self.env_error:
            return EXIT_ENV
        return EXIT_HARD if self.violations else EXIT_OK

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema": "research-idea-pipeline/structural-equivalence-check@1",
            "source": self.source,
            "exit_code": self.exit_code(),
            "checked": self.checked,
            "env_error": self.env_error,
            "rule_counts": self.rule_counts(),
            "violations": [
                {"rule": v.rule, "path": v.path, "detail": v.detail,
                 "value": v.value, "subject": v.subject}
                for v in self.violations
            ],
        }


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------


def _shorten(value: Any, limit: int = 60) -> str:
    text = _display(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _display(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(value)


def _text_ok(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_blank(value: Any) -> bool:
    return not _text_ok(value)


def _string_list(value: Any) -> Optional[List[str]]:
    """返回非空字符串列表；不是列表、或含非字符串、或含空串时返回 None。"""
    if not isinstance(value, list):
        return None
    out: List[str] = []
    for item in value:
        if not _text_ok(item):
            return None
        out.append(item)
    return out


def _forbidden_novelty_hit(text: str) -> Optional[str]:
    lowered = text.lower()
    for phrase in FORBIDDEN_NOVELTY_PHRASES:
        if phrase in text or phrase.lower() in lowered:
            return phrase
    for phrase in _ASCII_WORD_PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", lowered):
            return phrase
    return None


# ---------------------------------------------------------------------------
# 顶层结构
# ---------------------------------------------------------------------------


def structure_error(doc: Any) -> Optional[str]:
    if not isinstance(doc, dict):
        return "顶层不是 JSON 对象"
    if doc.get("schema") != SCHEMA:
        return f"schema 必须逐字等于 {SCHEMA}"
    return None


# ---------------------------------------------------------------------------
# artifact 级规则（EQ4—EQ11、EQ13）
# ---------------------------------------------------------------------------


def _check_alignment(report: Report, rule: str, key: str, doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    value = doc.get(key)
    if not isinstance(value, dict):
        report.add(rule, key, "缺失或不是对象（必须是十四个 facet 的逐项对齐）", value)
        return None
    missing = [facet for facet in FACETS if facet not in value]
    if missing:
        report.add(rule, key, f"缺少 facet：{'、'.join(missing)}", None)
    extra = [facet for facet in value if facet not in FACETS]
    if extra:
        report.add(rule, key, f"含十四个 facet 之外的键：{'、'.join(sorted(extra))}",
                   "、".join(sorted(extra)))
    blank = [facet for facet in FACETS if facet in value and _is_blank(value.get(facet))]
    if blank:
        report.add(rule, key, f"facet 取值为空：{'、'.join(blank)}", None)
    report.checked += 1
    return value


def check_artifact(doc: Any, source: str = "<memory>") -> Report:
    """单份 artifact 的机械校验：EQ4—EQ11 + EQ13。"""
    report = Report(source=source)
    env = structure_error(doc)
    if env is not None:
        report.env_error = env
        return report
    assert isinstance(doc, dict)

    # --- stage / candidate 形状（归 EQ2 / EQ11 的输入前提）---
    if doc.get("stage") not in STAGES:
        report.add("EQ11", "stage", f"必须是 {' | '.join(STAGES)} 之一", doc.get("stage"))
    candidate = doc.get("candidate")
    if not _text_ok(candidate) or not _ID_H.match(str(candidate)):
        report.add("EQ2", "candidate", "必须是 `H<n>` 形式的 id", candidate)
    report.checked += 1

    # --- EQ4 closest_priors + retrieval_status ---
    status = doc.get("retrieval_status")
    if status not in RETRIEVAL_STATUSES:
        report.add("EQ4", "retrieval_status",
                   f"必须是 {' | '.join(RETRIEVAL_STATUSES)} 之一", status)
    priors = _string_list(doc.get("closest_priors"))
    if priors is None:
        report.add("EQ4", "closest_priors", "必须是非空字符串数组", doc.get("closest_priors"))
    else:
        bad = [item for item in priors if not _ID_LIT.match(item)]
        if bad:
            report.add("EQ4", "closest_priors", f"元素必须是 `LIT<n>`：{'、'.join(bad)}",
                       "、".join(bad))
        if not priors and status != "retrieval-insufficient":
            report.add("EQ4", "closest_priors",
                       "不得为空，除非 retrieval_status 为 retrieval-insufficient",
                       "、".join(priors))
    report.checked += 1

    # --- EQ5 domain-aware alignment ---
    aware = _check_alignment(report, "EQ5", "domain_aware_alignment", doc)

    # --- EQ6 domain-stripped alignment + domain_terms ---
    stripped = _check_alignment(report, "EQ6", "domain_stripped_alignment", doc)
    terms = _string_list(doc.get("domain_terms"))
    if terms is None or not terms:
        report.add("EQ6", "domain_terms",
                   "必须是非空字符串数组（用于验证 domain-stripped 真的去掉了领域 / 品牌名）",
                   doc.get("domain_terms"))
    elif isinstance(stripped, dict):
        leaks: List[str] = []
        for facet in FACETS:
            text = stripped.get(facet)
            if not _text_ok(text):
                continue
            lowered = text.lower()
            for term in terms:
                if term.lower() in lowered:
                    leaks.append(f"{facet}⊃{term}")
        if leaks:
            report.add("EQ6", "domain_stripped_alignment",
                       f"仍含 domain_terms：{'、'.join(sorted(set(leaks)))}",
                       "、".join(sorted(set(leaks))))
    report.checked += 1

    # --- EQ11 verdict ---
    verdict = doc.get("verdict")
    if verdict not in VERDICTS:
        report.add("EQ11", "verdict", f"必须是十个冻结值之一（{' | '.join(VERDICTS)}）", verdict)
    report.checked += 1

    strong = verdict in STRONG_VERDICTS

    # --- EQ7 minimal_structural_delta + load_bearing_analysis ---
    delta = _string_list(doc.get("minimal_structural_delta"))
    if delta is None:
        report.add("EQ7", "minimal_structural_delta", "必须是非空字符串数组",
                   doc.get("minimal_structural_delta"))
    elif strong and not delta:
        report.add("EQ7", "minimal_structural_delta", "强 verdict 下不得为空", "[]")
    load = doc.get("load_bearing_analysis")
    if not isinstance(load, dict):
        report.add("EQ7", "load_bearing_analysis", "缺失或不是对象（五键必填）", load)
    else:
        missing = [key for key in LOAD_BEARING_KEYS if key not in load]
        if missing:
            report.add("EQ7", "load_bearing_analysis", f"缺少键：{'、'.join(missing)}", None)
        blank = [key for key in LOAD_BEARING_KEYS
                 if key in load and _is_blank(load.get(key))]
        if blank:
            report.add("EQ7", "load_bearing_analysis", f"取值为空：{'、'.join(blank)}", None)
        if strong and not blank and not missing:
            changed = [key for key in LOAD_BEARING_KEYS
                       if not any(lit in str(load.get(key)).strip().lower()
                                  for lit in UNCHANGED_LITERALS)]
            if not changed:
                report.add("EQ7", "load_bearing_analysis",
                           "强 verdict 下至少一个 changed_* 必须表示真实改变（不得全部 unchanged）",
                           "、".join(LOAD_BEARING_KEYS))
    report.checked += 1

    # --- EQ8 counterfactual_collapse ---
    collapse = doc.get("counterfactual_collapse")
    if not isinstance(collapse, dict):
        report.add("EQ8", "counterfactual_collapse", "必填，且必须是对象", collapse)
    else:
        for key in ("replacement", "predicted_consequence", "collapse_result"):
            if _is_blank(collapse.get(key)):
                report.add("EQ8", f"counterfactual_collapse.{key}", "缺失或为空", collapse.get(key))
        result = collapse.get("collapse_result")
        if _text_ok(result) and result not in COLLAPSE_RESULTS:
            report.add("EQ8", "counterfactual_collapse.collapse_result",
                       f"必须是 {' | '.join(COLLAPSE_RESULTS)} 之一", result)
        elif _text_ok(result) and verdict in VERDICTS:
            if verdict not in COLLAPSE_ALLOWED[result]:
                report.add("EQ8", "counterfactual_collapse.collapse_result",
                           f"与 verdict `{verdict}` 不相容；该 collapse_result 只允许 "
                           f"{' | '.join(COLLAPSE_ALLOWED[result])}",
                           result)
    report.checked += 1

    # --- EQ9 differentiating_consequences + discriminating_tests ---
    for key in ("differentiating_consequences", "discriminating_tests"):
        items = _string_list(doc.get(key))
        if items is None:
            report.add("EQ9", key, "必须是非空字符串数组", doc.get(key))
        elif strong and not items:
            report.add("EQ9", key, "强 verdict 下不得为空", "[]")
    report.checked += 1

    # --- EQ10 blind_spots + novelty_boundary 措辞 ---
    spots = _string_list(doc.get("blind_spots"))
    if spots is None or not spots:
        report.add("EQ10", "blind_spots", "必填，且必须是非空字符串数组", doc.get("blind_spots"))
    boundary = doc.get("novelty_boundary")
    if _is_blank(boundary):
        report.add("EQ10", "novelty_boundary", "必填，且不能为空", boundary)
    else:
        hit = _forbidden_novelty_hit(str(boundary))
        if hit:
            report.add("EQ10", "novelty_boundary",
                       f"含禁用字面量 `{hit}`；未发现等价前作时只能写 "
                       "「against the retrieved literature, no structural equivalent was identified」",
                       hit)
        if (not priors) or status == "retrieval-insufficient":
            if not any(marker in str(boundary) for marker in HEDGE_MARKERS):
                report.add("EQ10", "novelty_boundary",
                           "检索不足或 closest_priors 为空时，必须含 "
                           "`retrieved literature` 或 `据本次检索未见`",
                           str(boundary)[:60])
    report.checked += 1

    # --- EQ13 claimed_novelty_level 不得强于 verdict ---
    claimed = doc.get("claimed_novelty_level")
    if claimed not in CLAIMED_LEVELS:
        report.add("EQ13", "claimed_novelty_level",
                   f"必须是七个冻结值之一（{' | '.join(CLAIMED_LEVELS)}）", claimed)
    elif verdict in VERDICTS:
        permitted = allowed_claims(verdict)
        if claimed not in permitted:
            report.add("EQ13", "claimed_novelty_level",
                       f"`{claimed}` 强于 verdict `{verdict}`；只允许 {' | '.join(permitted)}",
                       claimed)
    report.checked += 1

    # --- evidence 形状（EQ3 的 artifact 侧）---
    evidence = _string_list(doc.get("evidence"))
    if evidence is None:
        report.add("EQ3", "evidence", "必须是非空字符串数组", doc.get("evidence"))
    else:
        bad = [item for item in evidence if not _ID_LIT.match(item)]
        if bad:
            report.add("EQ3", "evidence", f"元素必须是 `LIT<n>`：{'、'.join(bad)}", "、".join(bad))
        if priors:
            missing_prior = [p for p in priors if p not in evidence]
            if missing_prior:
                report.add("EQ3", "evidence",
                           f"closest_priors 必须同时登记进 evidence：{'、'.join(missing_prior)}",
                           "、".join(missing_prior))
    report.checked += 1

    _check_near_neighbor(report, doc)
    return report


# ---------------------------------------------------------------------------
# Near-neighbor 规则（NN1—NN13；policy §30）
#
# 这些规则只验证**审计纪律**：矩阵完整、枚举合法、span 存在、unresolved 被保留、
# stripping / mapping 按 operator 触发、claim 强度不超过上限。
# 它们**不**决定「H 与 P 是否真的结构等价」。
# ---------------------------------------------------------------------------


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _enum_ok(value: Any, allowed: Tuple[str, ...]) -> bool:
    return _text_ok(value) and value in allowed


def _nn_correspondence(report: Report, doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """NN1 / NN2：矩阵完整 + 枚举合法 + evidence_span 非空。"""
    value = doc.get("correspondence")
    if not isinstance(value, dict):
        report.add("NN1", "correspondence", "缺失或不是对象（必须是十四个 facet 的对应矩阵）", value)
        return None
    missing = [facet for facet in FACETS if facet not in value]
    if missing:
        report.add("NN1", "correspondence", f"缺少 facet：{'、'.join(missing)}", None)
    extra = sorted(facet for facet in value if facet not in FACETS)
    if extra:
        report.add("NN1", "correspondence", f"含十四个 facet 之外的键：{'、'.join(extra)}",
                   "、".join(extra))
    for facet in FACETS:
        entry = value.get(facet)
        base = f"correspondence.{facet}"
        if not isinstance(entry, dict):
            report.add("NN2", base, "缺失或不是对象（relation / provenance / evidence_span / note）",
                       entry)
            continue
        if not _enum_ok(entry.get("relation"), CORRESPONDENCE_RELATIONS):
            report.add("NN2", f"{base}.relation",
                       f"必须是 {' | '.join(CORRESPONDENCE_RELATIONS)} 之一（禁止二值强制）",
                       entry.get("relation"))
        if not _enum_ok(entry.get("provenance"), PROVENANCE):
            report.add("NN2", f"{base}.provenance",
                       f"必须是 {' | '.join(PROVENANCE)} 之一", entry.get("provenance"))
        if _is_blank(entry.get("evidence_span")):
            report.add("NN2", f"{base}.evidence_span",
                       "必填（原文 span / equation / code 位置）；没有 span 的对应关系不是证据",
                       entry.get("evidence_span"))
        if _is_blank(entry.get("note")):
            report.add("NN2", f"{base}.note", "必填（判断依据）", entry.get("note"))
    return value


def _nn_load_bearing(report: Report, doc: Dict[str, Any]) -> List[str]:
    """NN4：load_bearing_facets 非空且 ⊆ FACETS。"""
    value = doc.get("load_bearing_facets")
    if not isinstance(value, list) or not value:
        report.add("NN4", "load_bearing_facets", "必须是非空数组（承重 facet 清单）", value)
        return []
    bad = [item for item in value if not _text_ok(item) or item not in FACETS]
    if bad:
        report.add("NN4", "load_bearing_facets",
                   f"元素必须是十四个 facet 之一：{'、'.join(map(str, bad))}",
                   "、".join(map(str, bad)))
        return [item for item in value if item in FACETS]
    return list(value)


def _nn_validate_object(report: Report, rule: str, key: str, doc: Dict[str, Any],
                        spec: Tuple[Tuple[str, str, Tuple[str, ...]], ...],
                        optional_when: Optional[Any] = None) -> Optional[Dict[str, Any]]:
    """校验一个必填对象。

    `spec` 每项 = (键名, 类型, 枚举)。类型 ∈ str / bool / list / enum / lit / lit_or_empty。
    `optional_when(value)` 为真时只校验 `applicable` 与 `conclusion`（policy §24 的宽松分支）。
    """
    value = doc.get(key)
    if not isinstance(value, dict):
        report.add(rule, key, "缺失或不是对象", value)
        return None
    fields = spec
    if optional_when is not None and optional_when(value):
        fields = tuple(item for item in spec if item[0] in ("applicable", "conclusion"))
    problems: List[str] = []
    for field, kind, allowed in fields:
        if field not in value:
            problems.append(f"缺少键 {field}")
            continue
        item = value.get(field)
        if kind == "str":
            if _is_blank(item):
                problems.append(f"{field} 必须是非空字符串")
        elif kind == "bool":
            if not _is_bool(item):
                problems.append(f"{field} 必须是布尔")
        elif kind == "list":
            if not isinstance(item, list) or not all(_text_ok(part) for part in item):
                problems.append(f"{field} 必须是字符串数组（可为 []）")
        elif kind == "enum":
            if not _enum_ok(item, allowed):
                problems.append(f"{field} 必须是 {' | '.join(allowed)} 之一")
        elif kind == "lit":
            if not _text_ok(item) or not _ID_LIT.match(str(item)):
                problems.append(f"{field} 必须是 `LIT<n>`")
        elif kind == "lit_or_empty":
            if item != "" and (not _text_ok(item) or not _ID_LIT.match(str(item))):
                problems.append(f"{field} 必须是 `LIT<n>` 或空字符串")
    for problem in problems:
        report.add(rule, key, problem, None)
    return value


def _check_near_neighbor(report: Report, doc: Dict[str, Any],
                         operator: Optional[str] = None) -> None:
    """NN1—NN13：只验证审计纪律，不判断结构是否真的等价。

    `operator` 只在 route 模式传入（来自 `hypotheses[].operator`），用于 `NN10` / `NN11` 的触发检查。
    """
    near = doc.get("near_neighbor_verdict")
    if not _enum_ok(near, NEAR_NEIGHBOR_VERDICTS):
        report.add("NN12", "near_neighbor_verdict",
                   f"必须是八个冻结值之一（{' | '.join(NEAR_NEIGHBOR_VERDICTS)}）", near)
        near = None
    report.checked += 1

    matrix = _nn_correspondence(report, doc)
    bearings = _nn_load_bearing(report, doc)
    report.checked += 1

    # --- NN3 / NN5：UNRESOLVED 与 provenance 纪律 ---
    if isinstance(matrix, dict) and bearings:
        unresolved = [facet for facet in bearings
                      if isinstance(matrix.get(facet), dict)
                      and matrix[facet].get("relation") == "UNRESOLVED"]
        if unresolved and near in DELTA_FAMILY:
            report.add("NN3", "correspondence",
                       f"load-bearing facet 上保留了 UNRESOLVED：{'、'.join(unresolved)}；"
                       "此时禁止 structural-delta 与 structural-delta-strong",
                       "、".join(unresolved))
        if len(unresolved) >= 2 and near not in (None, "uncertain"):
            report.add("NN3", "near_neighbor_verdict",
                       f"{len(unresolved)} 个 load-bearing facet 为 UNRESOLVED，必须判 uncertain", near)
        strong = [facet for facet in bearings
                  if isinstance(matrix.get(facet), dict)
                  and matrix[facet].get("provenance") in STRONG_PROVENANCE]
        if len(strong) * 2 < len(bearings) and near in DELTA_FAMILY:
            report.add("NN5", "load_bearing_facets",
                       f"load-bearing facet 中 EXPLICIT / DERIVED 只有 {len(strong)}/{len(bearings)}；"
                       "关键结论不得主要依赖 INFERRED",
                       f"{len(strong)}/{len(bearings)}")
        weak_key = [facet for facet in bearings if facet in KEY_FACETS_FOR_TRUST
                    and isinstance(matrix.get(facet), dict)
                    and matrix[facet].get("provenance") in ("INFERRED", "UNKNOWN")]
        if weak_key and near in DELTA_FAMILY:
            report.add("NN5", "correspondence",
                       f"关键 facet 的对应关系依赖 INFERRED / UNKNOWN：{'、'.join(weak_key)}；"
                       "不得据此给强 novelty verdict",
                       "、".join(weak_key))

    trust = doc.get("trust_basis")
    if not isinstance(trust, list) or not trust:
        report.add("NN5", "trust_basis", "必须是非空数组（§21.3 八值）", trust)
    else:
        bad_trust = [item for item in trust if not _enum_ok(item, TRUST_BASES)]
        if bad_trust:
            report.add("NN5", "trust_basis",
                       f"元素必须是 {' | '.join(TRUST_BASES)} 之一：{'、'.join(map(str, bad_trust))}",
                       "、".join(map(str, bad_trust)))
    collapse = doc.get("counterfactual_collapse")
    if isinstance(trust, list) and trust and isinstance(collapse, dict) \
            and collapse.get("collapse_result") == "does-not-collapse" \
            and not (set(trust) & set(EXECUTABLE_TRUST)):
        report.add("NN5", "trust_basis",
                   "collapse_result 为 does-not-collapse 时，trust_basis 必须含可执行证据之一："
                   + " / ".join(EXECUTABLE_TRUST),
                   "、".join(map(str, trust)))
    report.checked += 1

    # --- NN6 local_neighborhood_test ---
    local = _nn_validate_object(report, "NN6", "local_neighborhood_test", doc, (
        ("near_prior", "lit", ()),
        ("local_modification_kinds", "list", ()),
        ("neighbor_confirmed", "bool", ()),
        ("rationale", "str", ()),
    ))
    if isinstance(local, dict):
        kinds = local.get("local_modification_kinds")
        if isinstance(kinds, list):
            bad_kinds = [item for item in kinds if item not in LOCAL_MODIFICATION_KINDS]
            if bad_kinds:
                report.add("NN6", "local_neighborhood_test.local_modification_kinds",
                           f"必须是 §16.3 十一类之一：{'、'.join(map(str, bad_kinds))}",
                           "、".join(map(str, bad_kinds)))
        if local.get("neighbor_confirmed") is True and near in DELTA_FAMILY:
            report.add("NN6", "local_neighborhood_test.neighbor_confirmed",
                       "为 true 时 near_neighbor_verdict 必须是 neighbor 家族", near)
    report.checked += 1

    # --- NN7 removal_test ---
    removal = _nn_validate_object(report, "NN7", "removal_test", doc, (
        ("removed_delta", "str", ()),
        ("returns_to_prior", "lit_or_empty", ()),
        ("unchanged_core", "list", ()),
        ("conclusion", "enum", REMOVAL_CONCLUSIONS),
    ))
    if isinstance(removal, dict) and removal.get("conclusion") == "component-local-delta" \
            and near in DELTA_FAMILY:
        report.add("NN7", "removal_test.conclusion",
                   "结论为 component-local-delta 时 near_neighbor_verdict 必须是 neighbor 家族", near)
    report.checked += 1

    # --- NN8 null_hypothesis ---
    null = _nn_validate_object(report, "NN8", "null_hypothesis", doc, (
        ("statement", "str", ()),
        ("strongest_subsumption_prior", "lit", ()),
        ("mapping_completeness", "enum", MAPPING_COMPLETENESS),
        ("unmapped_load_bearing_elements", "list", ()),
    ))
    if isinstance(null, dict):
        if _text_ok(null.get("statement")) and null.get("statement") != NULL_HYPOTHESIS_STATEMENT:
            report.add("NN8", "null_hypothesis.statement",
                       f"必须逐字为 `{NULL_HYPOTHESIS_STATEMENT}`", null.get("statement"))
        if null.get("mapping_completeness") == "full" and near in DELTA_FAMILY:
            report.add("NN8", "null_hypothesis.mapping_completeness",
                       "为 full（最强 subsumption 映射成立）时禁止 delta 家族 verdict", near)
    report.checked += 1

    # --- NN9 minimal_delta_set ---
    delta = _nn_validate_object(report, "NN9", "minimal_delta_set", doc, (
        ("delta_set", "list", ()),
        ("novel_consequence_kinds", "list", ()),
        ("sufficient_alone", "bool", ()),
    ))
    if isinstance(delta, dict):
        raw_kinds = delta.get("novel_consequence_kinds")
        if isinstance(raw_kinds, list):
            bad_consequences = [item for item in raw_kinds if item not in NOVEL_CONSEQUENCE_KINDS]
            if bad_consequences:
                report.add("NN9", "minimal_delta_set.novel_consequence_kinds",
                           f"必须是 {' | '.join(NOVEL_CONSEQUENCE_KINDS)} 之一："
                           f"{'、'.join(map(str, bad_consequences))}",
                           "、".join(map(str, bad_consequences)))
        if near in DELTA_FAMILY:
            if not delta.get("delta_set"):
                report.add("NN9", "minimal_delta_set.delta_set", "delta 家族下不得为空", "[]")
            if delta.get("sufficient_alone") is not True:
                report.add("NN9", "minimal_delta_set.sufficient_alone",
                           "delta 家族下必须为 true（仅凭 Δ* 就能推出新后果）",
                           delta.get("sufficient_alone"))
        if near == "structural-delta-strong" and isinstance(raw_kinds, list):
            kinds = list(dict.fromkeys(raw_kinds))
            if len(kinds) < 2:
                report.add("NN9", "minimal_delta_set.novel_consequence_kinds",
                           "structural-delta-strong 需要至少两种不同的后果类别", "、".join(kinds))
            if not ({"experiment", "boundary"} & set(kinds)):
                report.add("NN9", "minimal_delta_set.novel_consequence_kinds",
                           "structural-delta-strong 的后果必须包含 experiment 或 boundary",
                           "、".join(kinds))
    report.checked += 1

    # --- NN10 theory_stripping ---
    theory = _nn_validate_object(
        report, "NN10", "theory_stripping", doc, (
            ("applicable", "bool", ()),
            ("stripped_terms", "list", ()),
            ("residual_structure", "str", ()),
            ("adds_new_structure", "bool", ()),
            ("new_structure_kinds", "list", ()),
            ("conclusion", "enum", THEORY_STRIPPING_CONCLUSIONS),
        ), optional_when=lambda value: value.get("applicable") is False)
    if isinstance(theory, dict):
        raw_theory = theory.get("new_structure_kinds")
        if isinstance(raw_theory, list):
            bad_structure = [item for item in raw_theory
                             if item not in THEORY_NEW_STRUCTURE_KINDS]
            if bad_structure:
                report.add("NN10", "theory_stripping.new_structure_kinds",
                           f"必须是 §19 六类之一：{'、'.join(map(str, bad_structure))}",
                           "、".join(map(str, bad_structure)))
        if theory.get("applicable") is False and theory.get("conclusion") != "not-applicable":
            report.add("NN10", "theory_stripping.conclusion",
                       "applicable 为 false 时 conclusion 必须是 not-applicable",
                       theory.get("conclusion"))
        if theory.get("adds_new_structure") is True and not raw_theory:
            report.add("NN10", "theory_stripping.new_structure_kinds",
                       "adds_new_structure 为 true 时必须登记新结构类别", "[]")
        if theory.get("conclusion") == "theory-relabeling-risk" and near not in (
                "reframing-neighbor", "duplicate-equivalent", "uncertain", None):
            report.add("NN10", "theory_stripping.conclusion",
                       "theory-relabeling-risk 只允许 reframing-neighbor / duplicate-equivalent / uncertain",
                       near)
        if operator == THEORY_OPERATOR and theory.get("applicable") is not True:
            report.add("NN10", "theory_stripping.applicable",
                       f"operator 为 {THEORY_OPERATOR} 的候选必须做 theory stripping",
                       theory.get("applicable"))
    report.checked += 1

    # --- NN11 remote_analogy_mapping ---
    analogy = _nn_validate_object(
        report, "NN11", "remote_analogy_mapping", doc, (
            ("applicable", "bool", ()),
            ("object_mapping", "str", ()),
            ("relation_mapping", "str", ()),
            ("constraint_mapping", "str", ()),
            ("failure_mode_mapping", "str", ()),
            ("added_structure", "bool", ()),
            ("conclusion", "enum", REMOTE_ANALOGY_CONCLUSIONS),
        ), optional_when=lambda value: value.get("applicable") is False)
    if isinstance(analogy, dict):
        if analogy.get("applicable") is False and analogy.get("conclusion") != "not-applicable":
            report.add("NN11", "remote_analogy_mapping.conclusion",
                       "applicable 为 false 时 conclusion 必须是 not-applicable",
                       analogy.get("conclusion"))
        if analogy.get("added_structure") is False \
                and analogy.get("conclusion") == "structural-novelty":
            report.add("NN11", "remote_analogy_mapping.conclusion",
                       "added_structure 为 false 时结论不得是 structural-novelty",
                       analogy.get("conclusion"))
        if operator == REMOTE_ANALOGY_OPERATOR and analogy.get("applicable") is not True:
            report.add("NN11", "remote_analogy_mapping.applicable",
                       f"operator 为 {REMOTE_ANALOGY_OPERATOR} 的候选必须做四类映射",
                       analogy.get("applicable"))
    report.checked += 1

    # --- NN12 near_neighbor_verdict ↔ verdict ↔ claimed 上限 ---
    verdict = doc.get("verdict")
    if near in NEAR_NEIGHBOR_VERDICTS and verdict in VERDICTS:
        allowed_verdicts = NN_ALLOWED_VERDICTS[near]
        if verdict not in allowed_verdicts:
            report.add("NN12", "near_neighbor_verdict",
                       f"与 verdict `{verdict}` 不相容；`{near}` 只允许 "
                       f"{' | '.join(allowed_verdicts)}", near)
    claimed = doc.get("claimed_novelty_level")
    if near in NEAR_NEIGHBOR_VERDICTS and claimed in CLAIMED_LEVELS:
        permitted = nn_allowed_claims(near)
        if claimed not in permitted:
            report.add("NN12", "claimed_novelty_level",
                       f"`{claimed}` 超过 `{near}` 的上限；只允许 {' | '.join(permitted)}", claimed)
    report.checked += 1

    # --- NN13 禁止 scalar 决定 novelty ---
    offenders = [key for key in SCALAR_DECISION_KEYS if key in doc]
    if offenders:
        report.add("NN13", "根节点",
                   f"禁止 scalar 决定 novelty；标量只能放 retrieval_heuristic：{'、'.join(offenders)}",
                   "、".join(offenders))
    heuristic = doc.get("retrieval_heuristic")
    if heuristic is not None:
        if not isinstance(heuristic, dict):
            report.add("NN13", "retrieval_heuristic", "存在时必须是对象", heuristic)
        else:
            extra = sorted(key for key in heuristic if key not in ("scalar_distance", "use"))
            if extra:
                report.add("NN13", "retrieval_heuristic",
                           f"只允许 scalar_distance 与 use：{'、'.join(extra)}", "、".join(extra))
            distance = heuristic.get("scalar_distance")
            if _is_bool(distance) or not isinstance(distance, (int, float)):
                report.add("NN13", "retrieval_heuristic.scalar_distance", "必须是数值", distance)
            if heuristic.get("use") != RETRIEVAL_HEURISTIC_USE:
                report.add("NN13", "retrieval_heuristic.use",
                           f"必须逐字为 {RETRIEVAL_HEURISTIC_USE}", heuristic.get("use"))
    report.checked += 1


# ---------------------------------------------------------------------------
# route 级规则（EQ1—EQ3、EQ12）+ 全部 artifact 规则
# ---------------------------------------------------------------------------


def _load_state(route: pathlib.Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    path = route / "research-state.json"
    if not path.is_file():
        return None, f"找不到 research-state.json（{path}）"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"research-state.json 不是合法 JSON：{exc}"
    if not isinstance(doc, dict):
        return None, "research-state.json 顶层不是对象"
    return doc, None


def _artifact_paths(route: pathlib.Path) -> List[pathlib.Path]:
    directory = route / AUDIT_DIR
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.json"))


def check_route(route_dir: pathlib.Path) -> Report:
    """state ↔ artifact 交叉校验。缺 artifacts 目录视为无 SENA 记录，合法。"""
    report = Report(source=str(route_dir))
    state, env = _load_state(route_dir)
    if env is not None:
        report.env_error = env
        return report
    assert isinstance(state, dict)

    existing_ids = set()
    for key in ("claims", "evidence", "assumptions", "hypotheses", "experiments",
                "literature", "failures", "uncertainties"):
        for entry in state.get(key) or []:
            if isinstance(entry, dict) and _text_ok(entry.get("id")):
                existing_ids.add(entry["id"])

    hypothesis_by_id = {entry.get("id"): entry
                        for entry in state.get("hypotheses") or []
                        if isinstance(entry, dict)}

    assurance = [entry for entry in state.get("assurance") or [] if isinstance(entry, dict)]
    sena_records = [entry for entry in assurance
                    if entry.get("attack_type") == "structural-equivalence"]

    referenced: Dict[str, Dict[str, Any]] = {}

    # --- EQ1 / EQ12：SENA 记录必须指向一份真实存在的合法 artifact；EQ2 / EQ3：引用存在 ---
    for index, record in enumerate(sena_records):
        base = f"assurance[{index}]"
        target = record.get("target")
        audit_ref = record.get("audit_ref")
        if _is_blank(audit_ref):
            report.add("EQ1", f"{base}.audit_ref",
                       "attack_type 为 structural-equivalence 时必须指向 SENA artifact", audit_ref)
            continue
        text = str(audit_ref)
        if not AUDIT_REF_PATTERN.match(text):
            report.add("EQ12", f"{base}.audit_ref",
                       "必须形如 .research-idea-pipeline/routes/<R>/"
                       f"{AUDIT_DIR}/H<n>.json（或 .sena2.json）", text)
            continue
        route_name = text.split("/")[2]
        if route_name != route_dir.name:
            report.add("EQ12", f"{base}.audit_ref",
                       f"路径里的路线 `{route_name}` 与本路线 `{route_dir.name}` 不一致", text)
            continue
        recorded = re.search(r"/H(\d+)(?:\.sena2)?\.json$", text)
        if _text_ok(target) and recorded and str(target) != f"H{recorded.group(1)}":
            report.add("EQ12", f"{base}.audit_ref",
                       f"路径里的 H{recorded.group(1)} 与 target `{target}` 不一致", text)
            continue
        resolved = route_dir / AUDIT_DIR / text.rsplit("/", 1)[-1]
        if not resolved.is_file():
            report.add("EQ1", f"{base}.audit_ref", f"artifact 不存在：{text}", text)
            continue
        referenced[text] = record
        if not _text_ok(target) or not _ID_TARGET.match(str(target)):
            report.add("EQ2", f"{base}.target", "必须是 `H<n>` 或 `C<n>`", target)
        elif target not in existing_ids:
            report.add("EQ2", f"{base}.target", f"state 中不存在 id `{target}`", target)
        for lit in record.get("literature") or []:
            if lit not in existing_ids:
                report.add("EQ3", f"{base}.literature", f"state 中不存在 `{lit}`", lit)

    # --- EQ12 反向：磁盘 artifact 必须被 state 引用；并对每份被引用的 artifact 跑 artifact 规则 ---
    for path in _artifact_paths(route_dir):
        rel = f".research-idea-pipeline/routes/{route_dir.name}/{AUDIT_DIR}/{path.name}"
        if rel not in referenced:
            report.add("EQ12", rel,
                       "artifact 存在但没有任何 assurance[].audit_ref 指向它（producer/carrier 缺口）",
                       rel)
            continue
        sub = check_artifact_file(path)
        if sub.env_error is not None:
            report.env_error = sub.env_error
            return report
        report.violations.extend(sub.violations)
        report.checked += sub.checked

        # NN10 / NN11 的 operator 触发检查只有 route 模式能做（需要 state 里的 operator）。
        doc, err = _load_json(path)
        if err is None and isinstance(doc, dict):
            operator = (hypothesis_by_id.get(doc.get("candidate")) or {}).get("operator")
            if operator in (THEORY_OPERATOR, REMOTE_ANALOGY_OPERATOR):
                operator_report = Report(source=str(path))
                _check_near_neighbor(operator_report, doc, operator=operator)
                report.violations.extend(operator_report.violations)

    report.checked += len(sena_records)
    return report


def _load_json(path: pathlib.Path) -> Tuple[Any, Optional[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, str(exc)


def check_artifact_file(path: pathlib.Path) -> Report:
    if not path.is_file():
        report = Report(source=str(path))
        report.env_error = f"文件不存在（{path}）"
        return report
    doc, err = _load_json(path)
    if err is not None:
        report = Report(source=str(path))
        report.env_error = f"不是合法 JSON：{err}"
        return report
    return check_artifact(doc, source=str(path))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover — argparse 固定路径
        self.print_usage(sys.stderr)
        self.exit(EXIT_ERROR, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="structural_equivalence_check.py",
        description="Structural Equivalence / near-neighbor audit 的机械闸门"
                    "（只查审计完整性，不宣判 novelty）。"
                    "规则定义见 references/structural-equivalence-policy.md §12 与 §30。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--artifact", metavar="FILE", help="校验单份 audit artifact")
    parser.add_argument("--route", metavar="DIR", help="校验一条路线：state ↔ artifact 交叉检查")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON（stdout 只有 JSON）")
    parser.add_argument("--quiet", action="store_true", help="只打印汇总行")
    parser.add_argument("--selftest", action="store_true",
                        help="跑内置自检（EQ1—EQ13 与 NN1—NN13 全覆盖）")
    parser.add_argument("--list-rules", action="store_true", help="列出 EQ1—EQ13 与 NN1—NN13 及判据")
    return parser


def emit(report: Report, as_json: bool, quiet: bool) -> None:
    if as_json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        return
    if not quiet:
        for violation in report.violations:
            print(violation.render())
    print(report.summary())


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_rules:
        for rule in RULE_ORDER:
            print(f"{rule:5} 硬  {RULES[rule]}")
        return EXIT_OK

    if args.selftest:
        return selftest()

    targets = [bool(args.artifact), bool(args.route)]
    if sum(targets) != 1:
        parser.error("必须且只能给 --artifact / --route / --selftest / --list-rules 之一")

    if args.artifact:
        report = check_artifact_file(pathlib.Path(args.artifact))
    else:
        report = check_route(pathlib.Path(args.route))

    emit(report, args.json, args.quiet)
    code = report.exit_code()
    if not args.json and not args.quiet:
        print("PASS" if code == EXIT_OK else "FAIL")
    return code


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------


def _selftest_artifact(**overrides: Any) -> Dict[str, Any]:
    """一份合法 artifact（`structural-delta`）；`overrides` 用点号路径覆盖单个字段。"""
    aware = {facet: f"aware {facet}" for facet in FACETS}
    stripped = {facet: f"stripped {facet}" for facet in FACETS}
    changed = ("target_or_latent_quantity", "information_flow")
    correspondence = {
        facet: {
            "relation": "DIFFERENT" if facet in changed else "MATCH",
            "provenance": "DERIVED" if facet in changed else "EXPLICIT",
            "evidence_span": f"span://{facet}",
            "note": f"依据 {facet} 的原文与 equation",
        }
        for facet in FACETS
    }
    doc: Dict[str, Any] = {
        "schema": SCHEMA,
        "stage": "R7",
        "candidate": "H1",
        "closest_priors": ["LIT1"],
        "retrieval_status": "sufficient",
        "domain_terms": ["MRI"],
        "domain_aware_alignment": aware,
        "domain_stripped_alignment": stripped,
        "matched_core": ["core"],
        "candidate_only_elements": ["a"],
        "prior_only_elements": ["b"],
        "minimal_structural_delta": ["delta"],
        "load_bearing_analysis": {
            "changed_information": "yes",
            "changed_assumptions": "unchanged",
            "changed_mechanism": "unchanged",
            "changed_predictions": "unchanged",
            "changed_boundary": "unchanged",
        },
        "counterfactual_collapse": {
            "replacement": "replace",
            "predicted_consequence": "consequence",
            "collapse_result": "does-not-collapse",
        },
        "differentiating_consequences": ["consequence"],
        "discriminating_tests": ["X1"],
        "claimed_novelty_level": "formulation-delta",
        "verdict": "formulation-delta",
        "novelty_boundary": "against the retrieved literature, no structural equivalent was identified",
        "blind_spots": ["blind"],
        "evidence": ["LIT1"],
        "near_neighbor_verdict": "structural-delta",
        "correspondence": correspondence,
        "load_bearing_facets": list(changed),
        "local_neighborhood_test": {
            "near_prior": "LIT1",
            "local_modification_kinds": [],
            "neighbor_confirmed": False,
            "rationale": "local modification 无法解释目标量的改变",
        },
        "removal_test": {
            "removed_delta": "移除目标量重定义",
            "returns_to_prior": "LIT1",
            "unchanged_core": ["problem", "observables"],
            "conclusion": "load-bearing-delta",
        },
        "null_hypothesis": {
            "statement": NULL_HYPOTHESIS_STATEMENT,
            "strongest_subsumption_prior": "LIT1",
            "mapping_completeness": "partial",
            "unmapped_load_bearing_elements": ["target_or_latent_quantity"],
        },
        "minimal_delta_set": {
            "delta_set": ["目标量改为算子参数后验"],
            "novel_consequence_kinds": ["prediction"],
            "sufficient_alone": True,
        },
        "theory_stripping": {
            "applicable": False,
            "stripped_terms": [],
            "residual_structure": "not-applicable",
            "adds_new_structure": False,
            "new_structure_kinds": [],
            "conclusion": "not-applicable",
        },
        "remote_analogy_mapping": {
            "applicable": False,
            "object_mapping": "not-applicable",
            "relation_mapping": "not-applicable",
            "constraint_mapping": "not-applicable",
            "failure_mode_mapping": "not-applicable",
            "added_structure": False,
            "conclusion": "not-applicable",
        },
        "trust_basis": ["source-span", "equation"],
    }
    for path, value in overrides.items():
        node: Any = doc
        parts = path.split(".")
        for part in parts[:-1]:
            node = node[part]
        node[parts[-1]] = value
    return doc


def selftest() -> int:
    failures: List[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"  ok   {name}")
        else:
            failures.append(f"{name}: {detail}")
            print(f"  FAIL {name}: {detail}")

    base = _selftest_artifact()
    report = check_artifact(base, source="<selftest>")
    check("合法 artifact 通过", report.exit_code() == EXIT_OK, report.summary())

    cases = [
        ("EQ4", {"closest_priors": []}),
        ("EQ4", {"retrieval_status": "unknown"}),
        ("EQ5", {"domain_aware_alignment": {"problem": "x"}}),
        ("EQ6", {"domain_stripped_alignment": {**{f: "s" for f in FACETS}, "problem": "MRI scan"}}),
        ("EQ6", {"domain_terms": []}),
        ("EQ7", {"minimal_structural_delta": []}),
        ("EQ7", {"load_bearing_analysis": {"changed_information": "unchanged",
                                           "changed_assumptions": "unchanged",
                                           "changed_mechanism": "unchanged",
                                           "changed_predictions": "unchanged",
                                           "changed_boundary": "unchanged"}}),
        ("EQ8", {"counterfactual_collapse": {"replacement": "r", "predicted_consequence": "p",
                                             "collapse_result": "collapses"}}),
        ("EQ9", {"differentiating_consequences": []}),
        ("EQ10", {"blind_spots": []}),
        ("EQ10", {"novelty_boundary": "no prior work exists"}),
        ("EQ11", {"verdict": "super-novel"}),
        ("EQ13", {"claimed_novelty_level": "paradigm-candidate", "verdict": "reframing-only",
                  "counterfactual_collapse": {"replacement": "r", "predicted_consequence": "p",
                                              "collapse_result": "collapses"}}),
        # --- near-neighbor 层（NN1—NN13）---
        ("NN1", {"correspondence": {f: {"relation": "MATCH", "provenance": "EXPLICIT",
                                        "evidence_span": "s", "note": "n"}
                                    for f in FACETS if f != "problem"}}),
        ("NN2", {"correspondence.mechanism.relation": "MAYBE"}),
        ("NN2", {"correspondence.mechanism.evidence_span": ""}),
        ("NN2", {"correspondence.mechanism.note": ""}),
        ("NN3", {"correspondence.target_or_latent_quantity.relation": "UNRESOLVED"}),
        ("NN3", {"correspondence.target_or_latent_quantity.relation": "UNRESOLVED",
                 "correspondence.information_flow.relation": "UNRESOLVED",
                 "near_neighbor_verdict": "component-neighbor", "verdict": "component-delta",
                 "claimed_novelty_level": "component-delta",
                 "counterfactual_collapse": {"replacement": "r", "predicted_consequence": "p",
                                             "collapse_result": "collapses"},
                 "minimal_structural_delta": [],
                 "load_bearing_analysis": {k: "unchanged" for k in LOAD_BEARING_KEYS},
                 "differentiating_consequences": [], "discriminating_tests": []}),
        ("NN4", {"load_bearing_facets": []}),
        ("NN4", {"load_bearing_facets": ["not_a_facet"]}),
        ("NN5", {"trust_basis": []}),
        ("NN5", {"trust_basis": ["vibes"]}),
        ("NN5", {"trust_basis": ["literature"]}),
        ("NN5", {"correspondence.target_or_latent_quantity.provenance": "INFERRED",
                 "correspondence.information_flow.provenance": "INFERRED"}),
        ("NN5", {"load_bearing_facets": ["target_or_latent_quantity", "mechanism"],
                 "correspondence.mechanism.provenance": "INFERRED"}),
        ("NN6", {"local_neighborhood_test.neighbor_confirmed": True}),
        ("NN6", {"local_neighborhood_test.local_modification_kinds": ["banana"]}),
        ("NN6", {"local_neighborhood_test.rationale": ""}),
        ("NN7", {"removal_test.conclusion": "component-local-delta"}),
        ("NN7", {"removal_test": {"returns_to_prior": "", "unchanged_core": [],
                                  "conclusion": "unresolved"}}),
        ("NN8", {"null_hypothesis.statement": "candidate is novel"}),
        ("NN8", {"null_hypothesis.mapping_completeness": "full"}),
        ("NN9", {"minimal_delta_set": {"delta_set": [], "novel_consequence_kinds": ["prediction"],
                                       "sufficient_alone": True}}),
        ("NN9", {"minimal_delta_set": {"delta_set": ["d"], "novel_consequence_kinds": ["prediction"],
                                       "sufficient_alone": False}}),
        ("NN9", {"minimal_delta_set": {"delta_set": ["d"], "novel_consequence_kinds": ["vibes"],
                                       "sufficient_alone": True}}),
        ("NN9", {"near_neighbor_verdict": "structural-delta-strong",
                 "verdict": "paradigm-candidate", "claimed_novelty_level": "paradigm-candidate",
                 "minimal_delta_set": {"delta_set": ["d"], "novel_consequence_kinds": ["prediction"],
                                       "sufficient_alone": True}}),
        ("NN10", {"theory_stripping.conclusion": "theory-relabeling-risk"}),
        ("NN10", {"theory_stripping.conclusion": "theory-substantive"}),
        ("NN10", {"theory_stripping.applicable": True, "theory_stripping.adds_new_structure": True}),
        ("NN10", {"theory_stripping.new_structure_kinds": ["vibes"]}),
        ("NN11", {"remote_analogy_mapping.conclusion": "transfer"}),
        ("NN11", {"remote_analogy_mapping.applicable": True,
                  "remote_analogy_mapping.added_structure": False,
                  "remote_analogy_mapping.conclusion": "structural-novelty"}),
        ("NN12", {"verdict": "reframing-only", "claimed_novelty_level": "none",
                  "counterfactual_collapse": {"replacement": "r", "predicted_consequence": "p",
                                              "collapse_result": "collapses"}}),
        ("NN12", {"near_neighbor_verdict": "transfer-neighbor", "verdict": "transfer-only",
                  "claimed_novelty_level": "paradigm-candidate",
                  "counterfactual_collapse": {"replacement": "r", "predicted_consequence": "p",
                                              "collapse_result": "collapses"}}),
        ("NN13", {"structural_distance": 0.73}),
        ("NN13", {"retrieval_heuristic": {"scalar_distance": 0.73, "use": "novelty-gate"}}),
        ("NN13", {"retrieval_heuristic": {"scalar_distance": 0.73,
                                          "use": RETRIEVAL_HEURISTIC_USE, "extra": 1}}),
    ]
    for expected, overrides in cases:
        probe = _selftest_artifact(**overrides)
        got = check_artifact(probe, source="<selftest>").rules()
        check(f"反例命中 {expected}", expected in got, f"实际命中 {got}")

    # EQ3 artifact 侧：evidence 元素形状
    probe = _selftest_artifact(evidence=["nope"])
    check("反例命中 EQ3", "EQ3" in check_artifact(probe, source="<selftest>").rules(),
          str(check_artifact(probe, source="<selftest>").rules()))

    # 结构错误 → 环境不满足
    bad = check_artifact({"schema": "wrong"}, source="<selftest>")
    check("schema 不符 → exit 4", bad.exit_code() == EXIT_ENV, bad.summary())

    # allowed_claims 单调性
    check("allowed_claims 单调", allowed_claims("reframing-only") == ("none",),
          str(allowed_claims("reframing-only")))
    check("allowed_claims 上限", allowed_claims("paradigm-candidate") == _CLAIM_LADDER,
          str(allowed_claims("paradigm-candidate")))

    # near-neighbor 正向：合法 retrieval_heuristic 不报 NN13
    probe = _selftest_artifact(retrieval_heuristic={"scalar_distance": 0.4,
                                                    "use": RETRIEVAL_HEURISTIC_USE})
    check("合法 retrieval_heuristic 通过", check_artifact(probe).exit_code() == EXIT_OK,
          str(check_artifact(probe).rules()))

    # operator 触发：theory_lens 必须做 stripping；remote_analogy 必须做四类映射
    operator_report = Report(source="<selftest>")
    _check_near_neighbor(operator_report, _selftest_artifact(), operator=THEORY_OPERATOR)
    check("operator=theory_lens 触发 NN10", "NN10" in operator_report.rules(),
          str(operator_report.rules()))
    operator_report = Report(source="<selftest>")
    _check_near_neighbor(operator_report, _selftest_artifact(), operator=REMOTE_ANALOGY_OPERATOR)
    check("operator=remote_analogy 触发 NN11", "NN11" in operator_report.rules(),
          str(operator_report.rules()))

    # nn_allowed_claims 上限
    check("nn_allowed_claims 上限", nn_allowed_claims("duplicate-equivalent") == ("none",),
          str(nn_allowed_claims("duplicate-equivalent")))
    check("nn_allowed_claims delta 上限",
          nn_allowed_claims("structural-delta")
          == _CLAIM_LADDER[: _CLAIM_LADDER.index("boundary-delta") + 1],
          str(nn_allowed_claims("structural-delta")))

    print(f"selftest {'OK' if not failures else 'FAILED'}"
          + ("" if not failures else f"（{len(failures)} 项）"))
    return EXIT_OK if not failures else EXIT_HARD


if __name__ == "__main__":
    raise SystemExit(main())
