#!/usr/bin/env python3
"""preset_router.py — Research Preset Library, intent router and loop recovery triggers.

What this module fixes
----------------------
Three operational problems, none of which needs a new pipeline:

1. **A user should not have to memorise prompt shapes.** The four semantic entries
   (`start-project` / `continue-research` / `explore` / `audit`) are the authority; a preset is
   a *named, rehearsed* protocol inside one of them. Natural language, a preset id, an alias
   and the expert `phase=R<n>` form all resolve through one visible, testable precedence rule.
2. **A long autonomous loop must notice when it is stuck.** Context drift, repeated
   attribution, engineering failure, resource blockage and evidence conflict are all already
   visible in machine-readable state; this module turns them into *triggers* for the recovery
   protocols, with cooldowns, a per-snapshot ledger and an explicit `HOLD`.
3. **Strategy should improve from history.** The self-evolution presets read the existing
   strategy memory and replay harness and must produce an *observable* change in the next
   recommendation — writing a log entry without changing behaviour does not count.

**No second research pipeline.** Every preset names the existing stages, scripts and gates it
reuses; the router never invents state, never upgrades evidence and never grants execution
authority. `Research State` stays canonical, the CIE projections stay derived, and
`PEIG` / `AALG` / the R8 contract keep their authority.

Rule namespace `PR1`—`PR9`; `S`/`V`, `CM`, `PC`, `SV`, `RP`, `LH`, `EO`, `EX`, `RE`, `EQ`/`NN`
keep their own identities.

Usage
-----
    python3 preset_router.py list    [--json]
    python3 preset_router.py resolve --text "训练 OOM 了" [--state S]
    python3 preset_router.py inspect --preset research-loop
    python3 preset_router.py check   [--registry-only]
    python3 preset_router.py trigger --state S [--cognition DIR] [--scheduler S.json]
    python3 preset_router.py run     --preset loop-health-check --state S [--apply]
    python3 preset_router.py record  --state S --preset stagnation-breaker --signal SIG
    python3 preset_router.py --selftest

Exit codes: 0 pass, 1 argument error, 3 hard violation, 4 environment not satisfied / HOLD.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import cognition as cg
import evidence_outcome as eo
import prediction_compare as pc
import state_check as sc
import strategy_memory as sm

Diagnostic = cg.Diagnostic

SCHEMA_ROUTER = "research-idea-pipeline/preset-router@1"
SCHEMA_TRIGGER = "research-idea-pipeline/loop-trigger@1"
SCHEMA_RECOVERY_LOG = "research-idea-pipeline/recovery-log@1"

RECOVERY_LOG_NAME = "recovery-log.jsonl"
PRESETS_DIRNAME = "presets"

EXIT_OK = cg.EXIT_OK
EXIT_ERROR = cg.EXIT_ERROR
EXIT_HARD = cg.EXIT_HARD
EXIT_ENV = cg.EXIT_ENV

# ---------------------------------------------------------------------------
# Frozen vocabularies
# ---------------------------------------------------------------------------

#: Preset groups. `user` presets are only ever started by a human; `recovery` and `evolution`
#: may additionally be *suggested* by the loop trigger.
PRESET_GROUPS: Tuple[str, ...] = ("user", "recovery", "evolution")

#: The execution-scope vocabulary is the **provided registry's** (each label names what the
#: protocol may actually do). The repo keeps a frozen privilege tier per label so that safety
#: rules — ambiguity falls back to the least privileged protocol, read-only never escalates —
#: stay enforceable without flattening the provider's vocabulary.
EXECUTION_SCOPES: Tuple[str, ...] = (
    "read_only", "inspect_only", "evaluation_only", "derived_only", "recover_no_experiment",
    "runtime_recovery", "engineering_recovery", "audit", "plan", "decision_only",
    "discover_only", "evidence_repair", "strategy_update", "portfolio", "execute",
)

#: Privilege tier per scope, lowest first. `read_only` may write nothing but derived reports;
#: `derived` may rebuild projections; `advisory` produces plans/decisions/audits; `discovery`
#: may generate candidates through R3—R6; `strategy` may write strategy memory only; `execute`
#: may consume resources through the existing gates.
SCOPE_PRIVILEGE: Dict[str, str] = {
    "read_only": "read_only",
    "inspect_only": "read_only",
    "evaluation_only": "read_only",
    "derived_only": "derived",
    "recover_no_experiment": "derived",
    "runtime_recovery": "derived",
    "engineering_recovery": "derived",
    "audit": "read_only",
    "plan": "advisory",
    "decision_only": "advisory",
    "discover_only": "discovery",
    "evidence_repair": "discovery",
    "strategy_update": "strategy",
    "portfolio": "strategy",
    "execute": "execute",
}

#: Privilege order for ambiguity fallback: the smaller the rank, the safer the protocol.
PRIVILEGE_RANK: Dict[str, int] = {"read_only": 0, "derived": 1, "advisory": 2,
                                  "discovery": 3, "strategy": 4, "execute": 5}

#: What each scope may do to the canonical state. Only three scopes may ever write it, and each
#: one only through its own stage authority.
SCOPE_CANONICAL: Dict[str, str] = {
    "read_only": "不写 canonical", "inspect_only": "不写 canonical",
    "evaluation_only": "不写 canonical", "derived_only": "不写 canonical（只重建投影）",
    "recover_no_experiment": "不写 canonical",
    "runtime_recovery": "不写 canonical", "engineering_recovery": "不写 canonical",
    "audit": "不写 canonical（assurance[] 只在显式 R7 写回时由 R7 落盘）",
    "plan": "不写 canonical（只产出计划）", "decision_only": "不写 canonical（只产出决策）",
    "discover_only": "只经 R3—R6 写 hypotheses[]/claims[] 候选",
    "evidence_repair": "只经 R10/R11 写 claim/hypothesis 状态",
    "strategy_update": "不写 canonical（只写策略记忆）",
    "portfolio": "不写 canonical（只写策略记忆）",
    "execute": "只经既有 R 阶段与门禁写",
}

#: Named stage hints, used by the protocol generator and by `inspect`.
STAGES: Dict[str, str] = {
    "research-loop": "R0 → R14（按 `_loop_step` 选择当前阶段）",
    "paradigm-escape": "R3—R6（Discovery）+ R7（结构等价审计）",
    "research-recovery": "R0/R1 与 Legacy Handoff（`LH1`—`LH16`）",
    "scientific-replanning": "R10/R11（状态迁移）+ R14（策略）",
    "research-audit": "R7（Assurance）+ R8（证据契约）+ R13（Integrity Gate）",
    "research-review": "只读，不写任何阶段产物",
    "context-drift-recovery": "R11（状态同步）+ 认知投影重建",
    "stagnation-breaker": "R5.1/T8（行为切换）+ R6（重定义问题）",
    "experiment-failure-recovery": "R9（执行）+ R9.O（结果分析，仅工程分类）",
    "evidence-conflict-repair": "R10/R11（唯一有权改 claim 状态的两条路径）",
    "resource-recovery": "PEIG/AALG 执行授权 + `env_probe`",
    "memory-consolidation": "R11 后重建认知投影（`CM0`—`CM10`）",
    "loop-health-check": "R7/R14 只读体检",
    "strategy-evolution": "R14（策略记忆）+ `SV1`—`SV8`",
    "hypothesis-rebalance": "R3—R6（候选生成）+ `V13`/`V15`/`V16`",
    "discovery-replay": "`RP1`—`RP5`（回放与泄漏防护）",
}

#: The four semantic entries. A preset never introduces a fifth.
ENTRIES: Tuple[str, ...] = ("start-project", "continue-research", "explore", "audit")

#: Registry `trigger` vocabulary: who may start the protocol. `manual` never auto-triggers; an
#: `event*` form may be proposed by the trigger engine, and a *user* preset proposed that way is
#: marked `recommended_only` and is never started automatically.
PRESET_TRIGGERS: Tuple[str, ...] = (
    "manual", "event", "event_or_manual", "manual_or_stagnation", "manual_or_blocked",
    "manual_or_scheduled",
)

#: How a preset was selected. `auto` means the loop trigger proposed it.
TRIGGERS: Tuple[str, ...] = ("explicit", "alias", "intent", "entry", "auto", "expert")

#: Machine-readable signals the trigger engine reads. Every one of them is derived from
#: existing state or existing validators; none is a self-report.
SIGNAL_IDS: Tuple[str, ...] = (
    "context_drift",
    "state_integrity",
    "evidence_conflict",
    "memory_drift",
    "engineering_failure",
    "scientific_failure",
    "resource_blocked",
    "stagnation",
    "pseudo_progress",
    "portfolio_convergence",
    "evolution_due",
)

#: Reasons the router or the trigger returns without an action.
HOLD_REASONS: Tuple[str, ...] = (
    "no_intent_matched",
    "intent_negated",
    "ambiguous_intent",
    "expert_phase_entry",
    "descriptive_only",
    "state_integrity_blocked",
    "no_signal",
    "already_attempted_at_this_snapshot",
    "cooldown_active",
    "attempt_limit_reached",
    "not_actionable",
    "awaiting_human_decision",
)

#: Engineering failure kinds (`evidence_outcome.FAILURES`). A result that failed for one of
#: these reasons is **not** scientific evidence about the hypothesis.
ENGINEERING_FAILURE_KINDS: Tuple[str, ...] = (
    "implementation_failure", "optimization_failure", "data_failure", "protocol_failure",
    "measurement_failure", "evaluation_failure", "baseline_failure", "statistical_power_failure",
    "identifiability_failure",
)

#: Scientific failure kinds. They may *inform* R9.O/R10; they are never auto-adjudicated here.
SCIENTIFIC_FAILURE_KINDS: Tuple[str, ...] = (
    "hypothesis_failure", "theory_failure", "assumption_violation", "distribution_shift", "unknown",
)

#: Tokens that mark a *descriptive* report rather than a request to act. When the whole message
#: is descriptive the router returns the protocol with a read-only first step and requires
#: confirmation before anything consumes resources.
DESCRIPTIVE_MARKERS: Tuple[str, ...] = (
    "了", "出错了", "报错了", "崩了", "挂了", "失败了", "失败了。", "对不上", "不一致",
    "failed", "crashed", "oom", "nan", "error", "does not match", "mismatch",
)

#: Tokens that mark an explicit request to act.
IMPERATIVE_MARKERS: Tuple[str, ...] = (
    "帮我", "请", "开始", "跑一下", "执行", "恢复一下", "重启", "继续跑", "帮我看看怎么办",
    "please", "go ahead", "start", "run ", "execute", "fix", "recover", "resume and",
)

#: Negation scope: a negated preset is never selected, even when it is the only textual match.
NEGATION_PREFIXES: Tuple[str, ...] = (
    "不要", "不用", "不需要", "别", "先不", "暂时不", "停止", "拒绝", "勿", "不搞", "不做",
    "no need to", "don't", "do not", "dont", "without", "skip", "hold off", "not now",
    "stop the",
)

#: Text window (characters before a match) searched for a negation.
NEGATION_WINDOW_ZH = 6
NEGATION_WINDOW_EN = 24

#: Clause boundaries. Negation is decided **inside one clause**: in "不要审查，我只想知道下一步方案"
#: the refusal applies to the audit, not to what follows the comma. Chinese has no spaces, so a
#: window alone leaked the negation into the next clause and swallowed the whole request.
CLAUSE_SEPARATORS: Tuple[str, ...] = ("，", "。", "；", "、", "！", "？", ",", ";", ".", "!", "?",
                                      "\n", "\t", "  ")


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

def _preset(**kw: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "group": "user", "priority": 100, "cooldown_rounds": 0, "max_attempts": 1,
        "auto": None, "applies_when": (), "zh": (), "en": (), "reuses": (),
        "writes": (), "allowed": (), "forbidden": (), "outputs": (), "stops": (),
        "requires": ("research-state.json",),
    }
    base.update(kw)
    return base


#: The **enforcement** table: what the repository requires of each preset regardless of how the
#: registry words it (aliases, machine signals, priority, guard parameters, reuse, write scope,
#: permissions, output contract and stop conditions). The provided `preset-registry.json`
#: overlays ids, entries, titles, triggers, execution scopes, protocol paths and intent examples
#: on top of it; `PRESETS` below is the merged view everything else reads.
ENFORCEMENT: Tuple[Dict[str, Any], ...] = (
    # --- A. user-invoked ------------------------------------------------------
    _preset(
        id="research-loop", name_zh="自主科研闭环", name_en="Autonomous Research Loop",
        group="user", entry="continue-research", execution_scope="execute",
        protocol="presets/research-loop.md", priority=100, cooldown_rounds=0,
        aliases=("loop", "research-loop", "autonomous-research", "科研闭环", "自动科研"),
        zh=("继续自动科研", "一直跑科研闭环", "自动跑下去", "自己跑下去", "循环推进", "全自动科研",
            "接着自动跑", "继续跑别停", "继续科研", "持续跑 loop"),
        en=("run the loop", "keep researching", "autonomous research", "continue the loop",
            "run autonomously", "keep going until", "loop until"),
        intent_zh="在既有 R0—R14 与硬门禁内，按 Recall→Understand→Discover→Predict→Intervene→"
                  "Verify→Revise→Consolidate→Loop 持续推进，直到停止条件出现",
        intent_en="run the CIE scientific loop inside the existing stages and gates",
        applies_when=("用户明确要求自动/持续推进", "状态与证据完整，硬门禁可通过"),
        requires=("research-state.json", "contract", "scheduler", "cognition/index.json"),
        reuses=("cognition", "prediction_compare", "strategy_memory", "state_check",
                "execution_gate", "experiment_execute", "evidence_outcome"),
        writes=("research-state.json（只经既有 R 阶段与门禁）", "cognition/ 投影", "执行账本"),
        allowed=("调用既有阶段与脚本", "在 PEIG/AALG 授权内执行实验"),
        forbidden=("绕过 R8/R9.O/R10 的证据门禁", "自行改写 contract/锚点", "刷新 AALG 诊断预算"),
        outputs=("loop_state", "next_action", "evidence_delta", "changed_decision", "hold_reason"),
        stops=("预算或配额耗尽", "证据冲突未解", "需要人类裁决", "连续无决策变化"),
    ),
    _preset(
        id="paradigm-escape", name_zh="范式逃逸", name_en="Paradigm Escape",
        group="user", entry="explore", execution_scope="execute",
        protocol="presets/paradigm-escape.md", priority=100,
        aliases=("escape", "paradigm-escape", "representation-reset", "换范式", "表示重置"),
        zh=("跳出当前思路", "换一种数学建模方法", "换范式", "改变问题表示", "打破当前框架",
            "换个角度建模", "重新形式化"),
        en=("escape the current paradigm", "reframe the problem", "change the math",
            "representation reset", "different formulation", "reformulate"),
        intent_zh="执行 Representation Reset：在数学对象、变量、假设、目标与约束五个面上重建模，"
                  "并给出可机械核验的结构性差异与判别实验；不是再生成一个算法变体",
        intent_en="structural representation reset across object/variable/assumption/objective/constraint",
        applies_when=("当前表示被判定为局部最优或同构候选堆积", "用户明确要求换范式"),
        reuses=("state_check", "structural_equivalence_check", "cognition", "strategy_memory"),
        writes=("research-state.json（hypotheses/claims 只经 R3—R6 权限）",),
        allowed=("提出新的数学对象/变量/假设/目标/约束", "用结构等价审计核验差异"),
        forbidden=("把参数或模块替换当作范式改变", "跳过结构等价审计自证新颖",
                   "未经授权启动 GPU 或执行实验", "修改研究主锚点"),
        outputs=("representation_before", "representation_after", "axes_changed", "discriminating_test"),
        stops=("五个面均无法改变（记录边界并停手）", "新表示无法给出可判别预测"),
    ),
    _preset(
        id="research-recovery", name_zh="科研状态恢复", name_en="Research Recovery",
        group="user", entry="continue-research", execution_scope="read_only",
        protocol="presets/research-recovery.md", priority=100,
        aliases=("recovery", "resume", "research-recovery", "状态恢复", "恢复"),
        zh=("恢复之前的科研状态", "上下文丢了", "接着上次", "继续之前的工作", "记忆没了",
            "从头找回进度", "重新加载状态"),
        en=("resume", "recover the research state", "where were we", "pick up where we left off",
            "restore context", "reload the state"),
        intent_zh="从磁盘而不是聊天历史恢复：重读 skill 契约、canonical state、认知投影与未完成任务",
        intent_en="restore skill contract, research state, memory and in-flight tasks from disk",
        applies_when=("上下文被压缩或丢失", "新会话开始", "skill 未加载"),
        requires=("research-state.json", "cognition/"),
        reuses=("legacy_handoff", "cognition", "state_check", "prediction_compare"),
        writes=("cognition/index.json", "cognition/context-brief.md", "handoff 报告"),
        allowed=("重建认知投影", "报告未完成任务与阻塞", "调用 legacy_handoff detect/audit"),
        forbidden=("修改 canonical 科学事实", "重置 state_version/锚点/预算", "补造历史预测"),
        outputs=("recovered", "unrecovered", "in_flight", "blockers", "next_action"),
        stops=("严重兼容性错误（LH blocking）", "状态无法解析"),
    ),
    _preset(
        id="scientific-replanning", name_zh="科学重规划", name_en="Scientific Replanning",
        group="user", entry="continue-research", execution_scope="execute",
        protocol="presets/scientific-replanning.md", priority=100,
        aliases=("replan", "replanning", "scientific-replanning", "重规划", "重新规划"),
        zh=("重新规划研究路线", "调整研究策略", "方向不对", "换研究路线", "根据结果重新安排"),
        en=("replan", "re-plan the research", "change the strategy", "rethink the plan",
            "adjust the route"),
        intent_zh="依据否证、停滞与资源约束调整研究策略：改的是下一步做什么，不是改写既有证据",
        intent_en="adjust strategy from refutations, stagnation and constraints",
        applies_when=("出现否证/停滞/约束变化", "用户明确要求重规划"),
        reuses=("cognition", "strategy_memory", "prediction_compare", "evidence_outcome"),
        writes=("research-state.json（只经 R10/R11 权限）", "策略记忆"),
        allowed=("重排实验/干预优先级（优先只影响当前合法动作排序）", "登记新的不确定性",
                 "通过 R10/R11 改 claim 状态"),
        forbidden=("为了绕过门禁而重跑同一实验", "把无效执行当作否证",
                   "绕过 R10/R11 直接改科学状态", "变更主锚点（必须单独授权）"),
        outputs=("plan_before", "plan_after", "refutations_used", "next_action"),
        stops=("无合法改法（HOLD 并交人裁决）",),
    ),
    _preset(
        id="research-audit", name_zh="对抗审查", name_en="Adversarial Research Audit",
        group="user", entry="audit", execution_scope="read_only",
        protocol="presets/research-audit.md", priority=100,
        aliases=("audit", "adversarial-audit", "research-audit", "对抗审查", "审查", "审计"),
        zh=("审查目前的方法和实验", "对抗审查", "审一遍", "找问题", "检查科学正确性",
            "实验公平吗", "审计一下", "帮我审一下", "审计方法"),
        en=("audit", "review the method and experiments", "adversarial audit", "attack my claims",
            "check correctness", "is the experiment fair"),
        intent_zh="对科学正确性、创新性与实验公平性做对抗审查；只读，不推进 Discovery",
        intent_en="adversarial read-only audit of correctness, novelty and fairness",
        applies_when=("用户要求审查", "关键决策前需要对抗复核"),
        requires=("research-state.json",),
        reuses=("state_check", "structural_equivalence_check", "evidence_outcome",
                "prediction_compare", "execution_gate", "rhetorical_realization"),
        writes=("审查报告", "assurance[] 提案（写回由 R7 执行）"),
        allowed=("报告 flaw、kill condition 与判别实验", "复用既有验证器给出规则号",
                 "在显式请求（--apply）时产出 assurance[] 提案，交 R7 写回"),
        forbidden=("执行 Discovery（R3—R6）", "改写证据或 claim 状态", "消耗实验预算",
                   "因用户只说「审查」而隐式写 canonical"),
        outputs=("findings", "severity", "kill_conditions", "discriminating_tests"),
        stops=("审查完成即停（不自动转执行）",),
    ),
    _preset(
        id="research-review", name_zh="科学进展回顾", name_en="Research Review",
        group="user", entry="continue-research", execution_scope="read_only",
        protocol="presets/research-review.md", priority=100,
        aliases=("review", "summary", "research-review", "进展回顾", "总结"),
        zh=("现在到底取得了什么科学进展", "总结进展", "汇报一下", "汇报进展", "汇报",
            "复盘", "我们到哪一步了", "只汇报不要执行", "只要汇报", "进展如何",
            "下一步方案", "只想知道下一步"),
        en=("what progress", "summarize the progress", "review where we are", "status report",
            "just summarize"),
        intent_zh="只读总结：已确立的结论、仍未知的部分、未完成任务与下一决策选项",
        intent_en="read-only summary of established results, unknowns and next decisions",
        applies_when=("用户要求汇报/复盘", "行动前需要现状快照"),
        requires=("research-state.json", "cognition/"),
        reuses=("cognition", "strategy_memory", "prediction_compare", "evidence_outcome"),
        writes=("cognition/context-brief.md（可选）",),
        allowed=("读 canonical 与认知投影", "给出下一决策选项与代价"),
        forbidden=("写 canonical state", "执行实验", "改策略记忆"),
        outputs=("progress", "unknowns", "open_obligations", "next_decisions"),
        stops=("报告输出即停",),
    ),
    # --- B. loop-triggered recovery ------------------------------------------
    _preset(
        id="context-drift-recovery", name_zh="上下文漂移恢复", name_en="Context Drift Recovery",
        group="recovery", entry="continue-research", execution_scope="read_only",
        protocol="presets/runtime-recovery.md", priority=20, cooldown_rounds=0, max_attempts=2,
        aliases=("context-drift", "context-drift-recovery", "上下文漂移"),
        zh=("上下文压缩了", "skill 没加载", "执行目标漂移了", "状态索引不一致"),
        en=("context was compacted", "skill not loaded", "objective drifted", "index is stale"),
        intent_zh="从磁盘重建 skill 契约、canonical state 与认知投影，检测并修复投影漂移",
        intent_en="rebuild the skill contract, state and projections from disk",
        applies_when=("索引缺失或与 canonical 不一致", "handoff 记录缺失", "会话上下文丢失"),
        requires=("research-state.json",),
        reuses=("cognition", "legacy_handoff", "state_check"),
        writes=("cognition/index.json", "cognition/context-brief.md"),
        allowed=("重建投影", "报告漂移原因与影响范围"),
        forbidden=("依赖聊天历史作为事实来源", "改 canonical state"),
        outputs=("drift_reasons", "rebuilt", "canonical_untouched"),
        stops=("重建后仍不一致（交人裁决）",),
        auto={"signals": ("context_drift", "memory_drift"), "requires": "drift_detected"},
    ),
    _preset(
        id="stagnation-breaker", name_zh="停滞打破", name_en="Stagnation Breaker",
        group="recovery", entry="continue-research", execution_scope="execute",
        protocol="presets/runtime-recovery.md", priority=70, cooldown_rounds=2, max_attempts=2,
        aliases=("stagnation", "stagnation-breaker", "停滞"),
        zh=("一直在重复归因", "没有新东西", "原地打转", "同构候选太多", "没有新预测"),
        en=("repeating the same attribution", "nothing new", "going in circles", "stuck"),
        intent_zh="停滞诊断 + 动作选择器：选出一个能改变决策的最小干预，或明确停手",
        intent_en="diagnose stagnation and choose the smallest decision-changing intervention",
        applies_when=("连续零信息增益诊断", "同构候选/重复归因", "判别力缺失"),
        reuses=("prediction_compare", "cognition", "strategy_memory"),
        writes=("诊断记录", "scheduler 只读"),
        allowed=("选择判别干预或行为切换", "记录边界并停手"),
        forbidden=("仅凭一次负结果判定理论失败", "生成新解释来抢救旧机制", "刷新诊断预算"),
        outputs=("switch_action", "witness", "next_intervention", "stop_reason"),
        stops=("结构性不可区分且与决策无关（记录边界并停）",),
        auto={"signals": ("stagnation", "pseudo_progress"), "requires": "stagnation_detected"},
    ),
    _preset(
        id="experiment-failure-recovery", name_zh="实验失败恢复",
        name_en="Experiment Failure Recovery",
        group="recovery", entry="continue-research", execution_scope="execute",
        protocol="presets/runtime-recovery.md", priority=50, cooldown_rounds=1, max_attempts=2,
        aliases=("experiment-failure", "experiment-failure-recovery", "实验失败"),
        zh=("训练 oom 了", "实验出现 nan", "训练崩溃", "实验代码报错", "跑不起来",
            "显存不足", "训练失败", "实验失败", "恢复失败的实验", "实验结果报错",
            "oom", "nan"),
        en=("training oom", "nan in the run", "training crashed", "experiment code failed"),
        intent_zh="区分工程故障与科学否定：先修工程，再按既有授权重发执行收据；不得把工程故障"
                  "写成假设否证",
        intent_en="separate engineering failure from scientific refutation and repair the run",
        applies_when=("存在工程类失败（implementation/optimization/data/protocol/measurement/"
                      "evaluation/baseline/power/identifiability）",),
        reuses=("evidence_outcome", "execution_gate", "experiment_execute", "state_check"),
        writes=("failures[]（只经 R9.O 权限）", "执行账本"),
        allowed=("诊断故障类别", "修好后经 PEIG/AALG 重新授权执行"),
        forbidden=("把 OOM/NaN 当作科学否证", "无限重启同一实验", "跳过执行授权"),
        outputs=("failure_class", "scientific_effect", "repair_plan", "rerun_authorized"),
        stops=("同一指纹已达尝试上限（HOLD）", "资源或权限不足"),
        auto={"signals": ("engineering_failure",), "requires": "engineering_failure_present"},
    ),
    _preset(
        id="evidence-conflict-repair", name_zh="证据冲突修复",
        name_en="Evidence Conflict Repair",
        group="recovery", entry="continue-research", execution_scope="read_only",
        protocol="presets/evidence-memory-repair.md", priority=10, cooldown_rounds=1, max_attempts=2,
        aliases=("evidence-conflict", "evidence-conflict-repair", "证据冲突"),
        zh=("证据和研究状态对不上", "证据冲突", "状态不一致", "证据失效了但状态没变"),
        en=("evidence does not match the state", "evidence conflict", "stale evidence"),
        intent_zh="定位 Evidence/Claim/Prediction/Memory 的不一致，给出只能经 R10/R11 与统一证据"
                  "门禁执行的修复路径；本预设自身不改 canonical",
        intent_en="locate evidence/claim/prediction/memory conflicts and route the R10/R11 repair",
        applies_when=("state_check 引用/失效/可信度违规", "支持列表与状态矛盾", "证据已失效仍被引用"),
        reuses=("state_check", "evidence_outcome", "prediction_compare", "cognition"),
        writes=("诊断报告",),
        allowed=("列出冲突与最小修复步骤", "指出应走 R10 还是 R11"),
        forbidden=("自行改 claim 状态", "绕过统一证据资格门", "为了让状态变绿而删除证据"),
        outputs=("conflicts", "route", "blocked_transitions", "next_action"),
        stops=("无 R10/R11 授权（HOLD 并交人裁决）",),
        auto={"signals": ("evidence_conflict", "state_integrity"), "requires": "conflict_present"},
    ),
    _preset(
        id="resource-recovery", name_zh="资源与执行恢复",
        name_en="Resource & Execution Recovery",
        group="recovery", entry="continue-research", execution_scope="read_only",
        protocol="presets/runtime-recovery.md", priority=40, cooldown_rounds=2, max_attempts=2,
        aliases=("resource-recovery", "resource", "资源恢复"),
        zh=("gpu 不够了", "显存不够", "执行环境坏了", "依赖装不上", "预算不够", "磁盘满了"),
        en=("no gpu left", "out of memory", "environment is broken", "missing dependency",
            "budget exhausted"),
        intent_zh="诊断执行环境、依赖与预算，产出可执行的最小修复清单；本预设不启动任何作业",
        intent_en="diagnose environment, dependencies and budget; produce a repair checklist",
        applies_when=("资源或环境类失败", "预算/配额阻断", "依赖或环境探测失败"),
        reuses=("env_probe", "experiment_execute", "execution_gate", "state_check"),
        writes=("诊断报告",),
        allowed=("读环境探测与执行账本", "给出降配/排队/清理方案"),
        forbidden=("启动或重启 GPU 作业", "改预算策略文件", "把资源失败写成科学结论"),
        outputs=("blockers", "repair_checklist", "resume_conditions"),
        stops=("资源不可恢复（HOLD）",),
        auto={"signals": ("resource_blocked",), "requires": "resource_failure_present"},
    ),
    _preset(
        id="memory-consolidation", name_zh="认知记忆整合",
        name_en="Cognitive Memory Consolidation",
        group="recovery", entry="continue-research", execution_scope="read_only",
        protocol="presets/evidence-memory-repair.md", priority=30, cooldown_rounds=1, max_attempts=2,
        aliases=("memory-consolidation", "consolidate", "记忆整合"),
        zh=("合并和整理机制记忆", "整理记忆", "记忆漂移了", "重建认知索引"),
        en=("consolidate memory", "rebuild the cognitive index", "memory drifted"),
        intent_zh="在合法机制修订/状态变化后重建认知投影并报告记忆漂移；不修改 canonical 科学事实",
        intent_en="rebuild CIE projections after legal revisions; never touches canonical science",
        applies_when=("机制修订或状态迁移后投影过期", "CM 硬诊断出现", "insight/策略投影漂移"),
        reuses=("cognition", "strategy_memory", "state_check"),
        writes=("cognition/index.json", "cognition/context-brief.md"),
        allowed=("重建投影", "报告降级/失效传播结果"),
        forbidden=("修改 canonical 科学事实", "用投影覆盖 state", "把自评写进支持等级"),
        outputs=("rebuilt", "downgraded", "stale", "canonical_untouched"),
        stops=("重建后仍漂移（交人裁决）",),
        auto={"signals": ("memory_drift",), "requires": "hard_cm_diagnostic"},
    ),
    _preset(
        id="loop-health-check", name_zh="Loop 健康检查", name_en="Research Loop Health Check",
        group="recovery", entry="audit", execution_scope="read_only",
        protocol="presets/runtime-recovery.md", priority=60, cooldown_rounds=0, max_attempts=3,
        aliases=("loop-health", "loop-health-check", "健康检查"),
        zh=("检查 loop 是否正在原地打转", "loop 健康吗", "有没有伪进展", "检查自动科研是否有效"),
        en=("is the loop stuck", "loop health", "any pseudo progress", "is the loop effective"),
        intent_zh="只读体检：伪进展、重复行为、搜索停滞、预算与投影一致性，给出健康结论与建议",
        intent_en="read-only health report over pseudo-progress, repetition, stagnation and drift",
        applies_when=("定期体检", "怀疑伪进展", "恢复动作前后对照"),
        reuses=("cognition", "prediction_compare", "strategy_memory", "state_check"),
        writes=("体检报告",),
        allowed=("汇总机器可读信号", "给出恢复建议与优先级"),
        forbidden=("执行实验", "改 canonical state", "自行触发恢复动作"),
        outputs=("signals", "verdict", "recommended_preset", "hold_reason"),
        stops=("报告输出即停",),
        auto={"signals": ("pseudo_progress", "stagnation"), "requires": "always_available"},
    ),
    # --- C. self-evolution ----------------------------------------------------
    _preset(
        id="strategy-evolution", name_zh="策略进化", name_en="Strategy Evolution",
        group="evolution", entry="continue-research", execution_scope="mutate_strategy",
        protocol="presets/self-evolution.md", priority=80, cooldown_rounds=1, max_attempts=2,
        aliases=("strategy-evolution", "evolve-strategy", "策略进化"),
        zh=("根据历史结果改进探索策略", "进化探索策略", "让策略从历史里学", "调探索偏好"),
        en=("evolve the exploration strategy", "learn from history", "update the strategy priors"),
        intent_zh="用预测/干预的历史成效更新既有授权的策略记忆与探索建议，并证明下一轮推荐发生"
                  "可观察变化",
        intent_en="update authorised strategy memory from history and prove the next recommendation changes",
        applies_when=("同一算子/菜单累计失败", "预测-干预校准偏差", "策略修订间隔到达"),
        reuses=("strategy_memory", "research_replay", "cognition"),
        writes=("策略修订（append-only 修订日志）",),
        allowed=("更新算子先验与菜单排序", "记录改变量"),
        forbidden=("改 Research Contract/锚点", "改证据门禁或 skill 源码", "永久封禁算子"),
        outputs=("priors_before", "priors_after", "recommendation_before", "recommendation_after",
                 "changed_decision"),
        stops=("无可信历史（NO_CHANGE）", "改变会越过证据标准（拒绝）"),
        auto={"signals": ("evolution_due",), "requires": "operator_history_present"},
    ),
    _preset(
        id="hypothesis-rebalance", name_zh="假设组合再平衡",
        name_en="Hypothesis Portfolio Rebalance",
        group="evolution", entry="explore", execution_scope="mutate_strategy",
        protocol="presets/self-evolution.md", priority=85, cooldown_rounds=2, max_attempts=2,
        aliases=("hypothesis-rebalance", "rebalance", "假设再平衡"),
        zh=("所有 idea 都太相似了", "候选太同质", "换一批探索方向", "假设组合失衡"),
        en=("all ideas are too similar", "candidates converged", "rebalance the portfolio",
            "too homogeneous"),
        intent_zh="度量候选在同构轴上的集中度，并按既有算子/岛屿菜单再平衡；不新增候选家族分类",
        intent_en="measure portfolio concentration on existing structural axes and rebalance menus",
        applies_when=("单一岛屿/算子占比过高", "结构签名过于集中", "探索下限未被满足"),
        reuses=("strategy_memory", "cognition", "state_check"),
        writes=("策略修订（append-only 修订日志）",),
        allowed=("调整岛屿/算子探索权重", "要求至少一个新轴候选"),
        forbidden=("删除既有候选", "永久封禁岛屿/算子", "绕过 V13/V15/V16"),
        outputs=("concentration_before", "concentration_after", "menus_changed", "changed_decision"),
        stops=("已满足多样性下限（NO_CHANGE）",),
        auto={"signals": ("portfolio_convergence",), "requires": "concentration_above_threshold"},
    ),
    _preset(
        id="discovery-replay", name_zh="发现能力回放评估",
        name_en="Discovery Replay Evaluation",
        group="evolution", entry="audit", execution_scope="read_only",
        protocol="presets/self-evolution.md", priority=90, cooldown_rounds=1, max_attempts=2,
        aliases=("discovery-replay", "replay-eval", "回放评估"),
        zh=("用历史案例验证自进化是否有效", "回放评估", "用历史回放测新策略", "验证策略真的更好吗"),
        en=("evaluate the strategy with replay", "replay evaluation", "does the new strategy help"),
        intent_zh="用隔离隐藏结果的历史回放比较策略改动前后的表现，只报告分维度指标与样本量",
        intent_en="compare strategy variants on leak-checked replay cases, per dimension only",
        applies_when=("策略改动后需要回归验证", "怀疑自进化无效"),
        reuses=("research_replay", "strategy_memory", "cognition"),
        writes=("回放报告",),
        allowed=("运行回放与消融", "报告每维指标、样本量与不可评维度"),
        forbidden=("触碰隐藏答案", "把合成回放当作真实科研能力", "输出加权总分"),
        outputs=("per_dimension", "sample_size", "undifferentiated_arms", "limitations"),
        stops=("样本不足时明确拒绝下结论",),
        auto={"signals": ("evolution_due",), "requires": "strategy_revision_pending"},
    ),
)

# ---------------------------------------------------------------------------
# Registry integration (`preset-registry.json` is the provided source of truth)
# ---------------------------------------------------------------------------

REGISTRY_NAME = "preset-registry.json"
SHARED_CONTRACT_NAME = "shared-contract.md"
ROUTER_FIXTURES_NAME = "router-fixtures.json"
PROTOCOLS_DIRNAME = "presets"

#: Sections the shared contract must carry for the protocols to be loadable.
CONTRACT_SECTIONS: Tuple[str, ...] = ("## 权威与权限", "## 标准执行与回报")

#: Which machine signal makes a registry-level trigger observable. Group B/C presets have an
#: explicit signal in the enforcement table; this map covers the *recommend-only* forms the
#: registry attaches to user presets.
REGISTRY_TRIGGER_SIGNALS: Dict[str, str] = {
    "manual_or_stagnation": "stagnation",
    "manual_or_blocked": "evidence_conflict",
    "manual_or_scheduled": "evolution_due",
    "event": "context_drift",
}


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def registry_path(root: Optional[Path] = None) -> Path:
    return (root or skill_root()) / REGISTRY_NAME


def load_registry(root: Optional[Path] = None) -> Dict[str, Any]:
    """Read the provided registry. Missing or malformed is reported, not raised."""
    path = registry_path(root)
    if not path.is_file():
        return {"schema_version": None, "base_contract": SHARED_CONTRACT_NAME, "presets": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"schema_version": None, "base_contract": SHARED_CONTRACT_NAME, "presets": []}
    return payload if isinstance(payload, dict) else {"presets": []}


def _is_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


#: Privileges a user preset may auto-start on its own: work that cannot change science or
#: consume resources. Discovery/strategy/execution need an explicit loop authorization.
AUTO_SAFE_PRIVILEGES: Tuple[str, ...] = ("read_only", "derived", "advisory")


def may_auto_start(preset: Dict[str, Any]) -> bool:
    """Whether a registry-level event trigger may start this preset without further consent."""
    if preset.get("group") != "user":
        return True
    return scope_privilege(preset.get("execution_scope")) in AUTO_SAFE_PRIVILEGES


def scope_privilege(scope: Any) -> str:
    """The frozen privilege tier of a registry scope label."""
    return SCOPE_PRIVILEGE.get(str(scope), "read_only")


def scope_rank(preset: Dict[str, Any]) -> int:
    return PRIVILEGE_RANK[scope_privilege(preset.get("execution_scope"))]


def _merge_registry(enforcement: Tuple[Dict[str, Any], ...]) -> Tuple[Dict[str, Any], ...]:
    """Overlay the provided registry onto the enforcement table, per preset id."""
    registry = load_registry()
    by_id = {item.get("preset_id"): item for item in registry.get("presets") or []
             if isinstance(item, dict) and item.get("preset_id")}
    merged: List[Dict[str, Any]] = []
    for base in enforcement:
        entry = dict(base)
        record = by_id.get(base["id"]) or {}
        if record:
            entry["entry"] = record.get("entry", base["entry"])
            entry["execution_scope"] = record.get("execution_scope", base["execution_scope"])
            entry["name_en"] = record.get("title", base["name_en"])
            entry["protocol"] = record.get("path", base["protocol"])
            entry["registry_trigger"] = record.get("trigger", "manual")
            entry["intent_examples"] = tuple(
                item for item in record.get("intent_examples") or [] if isinstance(item, str))
        else:
            entry["registry_trigger"] = "manual"
            entry["intent_examples"] = ()
        # Intent examples from the provider are first-class routing patterns.
        zh = tuple(base.get("zh", ())) + tuple(
            item for item in entry["intent_examples"] if _is_cjk(item))
        en = tuple(base.get("en", ())) + tuple(
            item for item in entry["intent_examples"] if not _is_cjk(item))
        entry["zh"], entry["en"] = tuple(dict.fromkeys(zh)), tuple(dict.fromkeys(en))
        aliases = tuple(base.get("aliases", ())) + (entry["id"],)
        entry["aliases"] = tuple(dict.fromkeys(aliases))
        # Auto eligibility: group B/C recover automatically; a group-A preset the registry marks
        # as event-triggerable may only be *recommended*, never auto-started.
        auto = base.get("auto")
        if auto is None and entry["registry_trigger"] != "manual" and base["group"] == "user":
            signal = REGISTRY_TRIGGER_SIGNALS.get(entry["registry_trigger"], "stagnation")
            # A user preset may auto-start only when it cannot change science or resources:
            # read-only / derived / advisory work (plan, diagnose, repair the run) is safe to
            # trigger; discovery, strategy and execution need an explicit loop authorization.
            privilege = scope_privilege(entry["execution_scope"])
            auto = {
                "signals": (signal,),
                "requires": (f"registry trigger={entry['registry_trigger']}；权限层 {privilege}"
                             + ("（可在授权的 Autonomous Loop 内自动触发受控 Discovery）"
                                if privilege in ("discovery", "strategy", "execute")
                                else "（可直接自动触发；不改科学事实）")),
                "mode": "recover" if privilege in ("read_only", "derived", "advisory")
                else "recommend",
            }
        entry["auto"] = ({**auto, "mode": auto.get("mode", "recover")} if auto else None)
        merged.append(entry)
    return tuple(merged)


PRESETS: Tuple[Dict[str, Any], ...] = _merge_registry(ENFORCEMENT)

PRESET_IDS: Tuple[str, ...] = tuple(preset["id"] for preset in PRESETS)

#: Sections every protocol file must carry, so Markdown cannot drift from the registry.
PROTOCOL_SECTIONS: Tuple[str, ...] = (
    "## 1. 意图与入口", "## 2. 触发条件", "## 3. 必需输入", "## 4. 允许与禁止",
    "## 5. 复用的阶段、脚本与检查器", "## 6. 执行步骤", "## 7. 输出契约",
    "## 8. 状态写回", "## 9. 停止、失败与恢复",
)


def presets_by_id() -> Dict[str, Dict[str, Any]]:
    return {preset["id"]: preset for preset in PRESETS}


def scope_rank(preset: Dict[str, Any]) -> int:
    """Safety rank of a preset, used to resolve ambiguity toward the safer protocol."""
    return PRIVILEGE_RANK[scope_privilege(preset["execution_scope"])]


# ---------------------------------------------------------------------------
# Registry ↔ protocol parity
# ---------------------------------------------------------------------------

def registry_errors(root: Optional[Path] = None) -> List[Diagnostic]:
    """Every machine-checkable property of the preset library (`PR1`—`PR4`)."""
    root = root or Path(__file__).resolve().parent.parent
    failures: List[Diagnostic] = []
    seen_ids: set = set()
    seen_aliases: Dict[str, str] = {}
    for preset in PRESETS:
        preset_id = preset.get("id", "<missing>")
        path = f"presets[{preset_id}]"
        if not isinstance(preset_id, str) or not preset_id.strip():
            failures.append(Diagnostic("PR1", path, "preset 必须有非空 id"))
            continue
        if preset_id in seen_ids:
            failures.append(Diagnostic("PR1", path, f"preset id 重复：{preset_id}"))
        seen_ids.add(preset_id)
        if preset.get("group") not in PRESET_GROUPS:
            failures.append(Diagnostic("PR1", path, f"group 必须是 {list(PRESET_GROUPS)}"))
        if preset.get("entry") not in ENTRIES:
            failures.append(Diagnostic("PR1", path, f"entry 必须是 {list(ENTRIES)}"))
        if preset.get("execution_scope") not in EXECUTION_SCOPES:
            failures.append(Diagnostic(
                "PR1", path, f"execution_scope 必须是 {list(EXECUTION_SCOPES)}"))
        for field in ("name_zh", "name_en", "intent_zh", "intent_en"):
            if not isinstance(preset.get(field), str) or not preset[field].strip():
                failures.append(Diagnostic("PR1", path, f"缺少非空 {field}"))
        for field in ("zh", "en", "aliases"):
            values = preset.get(field)
            if not isinstance(values, tuple) or not values:
                failures.append(Diagnostic("PR1", path, f"{field} 必须是非空元组（匹配词）"))
                continue
            for value in values:
                if not isinstance(value, str) or not value.strip():
                    failures.append(Diagnostic("PR1", path, f"{field} 含空元素"))
                if field == "aliases":
                    key = value.strip().casefold()
                    if key in seen_aliases and seen_aliases[key] != preset_id:
                        failures.append(Diagnostic(
                            "PR1", path, f"别名 {value!r} 与 {seen_aliases[key]} 冲突"))
                    seen_aliases[key] = preset_id
        for field in ("reuses", "writes", "allowed", "forbidden", "outputs", "stops", "requires"):
            if not isinstance(preset.get(field), tuple) or not preset[field]:
                failures.append(Diagnostic("PR2", path, f"{field} 必须是非空元组"))
        for name in preset.get("reuses", ()):
            if not (root / "scripts" / f"{name}.py").is_file():
                failures.append(Diagnostic(
                    "PR2", path, f"reuses 指向不存在的脚本：scripts/{name}.py"))
        if not isinstance(preset.get("priority"), int) or isinstance(preset["priority"], bool):
            failures.append(Diagnostic("PR2", path, "priority 必须是整数"))
        else:
            if preset["priority"] < 0:
                failures.append(Diagnostic("PR2", path, "priority 必须 ≥ 0（越小越优先）"))
            primary = AUTO_SIGNAL_MAP.get(preset_id)
            if primary is not None and primary not in (preset["auto"].get("signals") or ()):
                failures.append(Diagnostic(
                    "PR2", path, f"AUTO_SIGNAL_MAP 的 {primary!r} 不在预设声明的信号里"))
            if preset.get("group") == "recovery" and preset.get("auto") is None:
                failures.append(Diagnostic("PR2", path, "recovery presets 必须声明 auto 触发条件"))
            if preset.get("auto") is not None and preset["auto"].get("mode") == "recover" \
                    and not may_auto_start(preset):
                failures.append(Diagnostic(
                    "PR2", path, "该预设的权限层不得自动执行（需 loop 授权）"))
        auto = preset.get("auto")
        if auto is not None:
            if not isinstance(auto, dict) or not isinstance(auto.get("signals"), tuple) \
                    or not auto["signals"]:
                failures.append(Diagnostic("PR2", path, "auto 必须声明非空 signals"))
            else:
                for signal in auto["signals"]:
                    if signal not in SIGNAL_IDS:
                        failures.append(Diagnostic(
                            "PR2", path, f"未知信号 {signal!r}；必须是 {list(SIGNAL_IDS)} 之一"))
                if not isinstance(auto.get("requires"), str) or not auto["requires"].strip():
                    failures.append(Diagnostic("PR2", path, "auto.requires 必须说明触发前提"))
                if auto.get("mode") not in ("recover", "recommend"):
                    failures.append(Diagnostic("PR2", path, "auto.mode 必须是 recover 或 recommend"))
                if auto.get("mode") == "recover" and not may_auto_start(preset):
                    failures.append(Diagnostic(
                        "PR2", path,
                        "该 user 预设的权限层不得自动执行（需 loop 授权，否则只能 recommend）"))
        cooldown = preset.get("cooldown_rounds")
        if not isinstance(cooldown, int) or isinstance(cooldown, bool) or cooldown < 0:
            failures.append(Diagnostic("PR2", path, "cooldown_rounds 必须是非负整数"))
        attempts = preset.get("max_attempts")
        if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
            failures.append(Diagnostic("PR2", path, "max_attempts 必须是 ≥1 的整数"))
        protocol = preset.get("protocol")
        if not isinstance(protocol, str) or not protocol.startswith(f"{PROTOCOLS_DIRNAME}/"):
            failures.append(Diagnostic("PR3", path, f"protocol 必须是 {PROTOCOLS_DIRNAME}/<name>.md"))
            continue
        protocol_path = root / protocol
        if not protocol_path.is_file():
            failures.append(Diagnostic("PR3", path, f"协议文件不存在：{protocol}"))
            continue
        text = protocol_path.read_text(encoding="utf-8")
        missing = [section for section in PROTOCOL_SECTIONS if section not in text]
        if missing:
            failures.append(Diagnostic(
                "PR3", protocol, f"协议文件缺少必需章节：{missing}"))
        if preset_id not in text:
            failures.append(Diagnostic("PR3", protocol, f"协议文件未出现 preset id {preset_id}"))
        for field, marker in (("entry", "入口"), ("execution_scope", "授权")):
            if preset[field] not in text:
                failures.append(Diagnostic(
                    "PR3", protocol, f"协议文件未声明 {marker}（{preset[field]}）"))
    for required in PRESET_IDS:
        if required not in seen_ids:
            failures.append(Diagnostic("PR1", "presets", f"注册表缺少 preset：{required}"))
    if len(PRESETS) != 16:
        failures.append(Diagnostic("PR1", "presets", f"必须恰好 16 个预设，实际 {len(PRESETS)}"))

    # --- the provided registry itself (`PR1`/`PR3`) ---------------------------
    registry_file = registry_path(root)
    if not registry_file.is_file():
        failures.append(Diagnostic("PR1", REGISTRY_NAME, "缺少提供版 preset-registry.json"))
    else:
        payload = load_registry(root)
        records = [item for item in payload.get("presets") or [] if isinstance(item, dict)]
        if len(records) != 16:
            failures.append(Diagnostic(
                "PR1", REGISTRY_NAME, f"注册表必须列出 16 个预设，实际 {len(records)}"))
        if [item.get("preset_id") for item in records] != list(PRESET_IDS):
            failures.append(Diagnostic("PR1", REGISTRY_NAME, "注册表 id 集合或顺序与实现不一致"))
        base = payload.get("base_contract")
        if base != SHARED_CONTRACT_NAME or not (root / SHARED_CONTRACT_NAME).is_file():
            failures.append(Diagnostic(
                "PR3", REGISTRY_NAME, f"base_contract 必须指向存在的 {SHARED_CONTRACT_NAME}"))
        for record in records:
            preset_id = record.get("preset_id")
            examples = record.get("intent_examples")
            if not isinstance(examples, list) or len(examples) < 3:
                failures.append(Diagnostic(
                    "PR3", REGISTRY_NAME, f"{preset_id} 至少需要 3 条 intent_examples"))
            if record.get("execution_scope") not in EXECUTION_SCOPES:
                failures.append(Diagnostic(
                    "PR3", REGISTRY_NAME,
                    f"{preset_id} 的 execution_scope={record.get('execution_scope')!r} 未登记"))
            if record.get("trigger") not in PRESET_TRIGGERS:
                failures.append(Diagnostic(
                    "PR3", REGISTRY_NAME,
                    f"{preset_id} 的 trigger={record.get('trigger')!r} 未登记"))
    if not (root / SHARED_CONTRACT_NAME).is_file():
        failures.append(Diagnostic("PR3", SHARED_CONTRACT_NAME, "缺少跨预设共同契约"))
    return cg._dedupe(failures)


# ---------------------------------------------------------------------------
# Intent matching
# ---------------------------------------------------------------------------

def normalize_intent_text(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    return " ".join(text.split()).casefold()


def _clause_start(text: str, index: int) -> int:
    """Where the clause containing `index` begins."""
    boundaries = [text.rfind(separator, 0, index) for separator in CLAUSE_SEPARATORS]
    return max(boundaries, default=-1) + 1


def _negated(text: str, start: int, token: str) -> bool:
    """Whether a match beginning at `start` is inside the scope of a negation.

    Scoped to the clause that contains the match: a refusal in one clause never cancels the
    request made in the next one.
    """
    window = NEGATION_WINDOW_EN if token.isascii() else NEGATION_WINDOW_ZH
    begin = max(_clause_start(text, start), start - window)
    prefix = text[begin:start]
    return any(negation in prefix for negation in NEGATION_PREFIXES)


def _intent_candidates(text: str) -> List[Dict[str, Any]]:
    """Score every preset against the message. No model, no embedding: literal rules only."""
    normalized = normalize_intent_text(text)
    found: List[Dict[str, Any]] = []
    if not normalized:
        return found
    for preset in PRESETS:
        best: Optional[Dict[str, Any]] = None
        exact_id = preset["id"].casefold()
        for alias in preset.get("aliases", ()):
            key = alias.casefold()
            index = normalized.find(key)
            if index < 0:
                continue
            if _negated(normalized, index, key):
                continue
            weight = 3 if key == exact_id else 2
            if best is None or weight > best["weight"] or len(key) > len(best["token"]):
                best = {"weight": weight, "token": alias, "kind": "alias"}
        for phrases, kind, weight in ((preset.get("zh", ()), "zh", 2),
                                      (preset.get("en", ()), "en", 2)):
            for phrase in phrases:
                key = phrase.casefold()
                index = normalized.find(key)
                if index < 0:
                    continue
                if _negated(normalized, index, key):
                    continue
                if best is None or weight > best["weight"] or len(key) > len(best["token"]):
                    best = {"weight": weight, "token": phrase, "kind": kind}
        if best is not None:
            found.append({**best, "preset_id": preset["id"],
                          "current_weight": best["weight"] + len(best["token"]) / 100.0})
    found.sort(key=lambda item: (-item["current_weight"], item["preset_id"]))
    return found


def _negated_presets(text: str) -> List[str]:
    """Presets that the message names but explicitly refuses."""
    normalized = normalize_intent_text(text)
    refused: List[str] = []
    for preset in PRESETS:
        for token in list(preset.get("aliases", ())) + list(preset.get("zh", ())) \
                + list(preset.get("en", ())):
            key = token.casefold()
            index = normalized.find(key)
            if index >= 0 and _negated(normalized, index, key):
                refused.append(preset["id"])
                break
    return sorted(set(refused))


def _has_phase_entry(text: str) -> bool:
    normalized = normalize_intent_text(text)
    return "phase=r" in normalized or "phase=r" in normalized.replace(" ", "")


def _is_descriptive(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if any(marker in normalized for marker in IMPERATIVE_MARKERS):
        return False
    return any(marker in normalized for marker in DESCRIPTIVE_MARKERS)


def _entry_from_text(text: str) -> Optional[str]:
    normalized = normalize_intent_text(text)
    for entry in ENTRIES:
        if entry in normalized:
            return entry
    return None


def resolve(
    text: Any,
    *,
    state: Optional[Dict[str, Any]] = None,
    index: Optional[Dict[str, Any]] = None,
    scheduler: Optional[Dict[str, Any]] = None,
    extra_triggers: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Resolve a natural-language request into one preset, or an explicit HOLD.

    Precedence, highest first:

    1. an explicit preset id in the message (`trigger: explicit`);
    2. an explicit alias (`alias`);
    3. an intent phrase plus the top-level entry named by the user (`entry`);
    4. an intent phrase alone (`intent`);
    5. a loop trigger, only when the user did not ask for anything (`auto`).

    Refusals are first class: a negated preset is never selected, an ambiguous match falls back
    to the **least privileged** candidate and asks for confirmation, a descriptive report gets a
    read-only first step, and a `phase=R<n>` expert request is passed through untouched unless a
    preset id is also given.
    """
    normalized = normalize_intent_text(text)
    refused = _negated_presets(text)
    candidates = [item for item in _intent_candidates(text) if item["preset_id"] not in refused]
    explicit = [item for item in candidates
                if item["kind"] == "alias" and item["token"].casefold() == item["preset_id"]]
    by_id = presets_by_id()
    phase = _has_phase_entry(text)
    entry_hint = _entry_from_text(text)
    payload: Dict[str, Any] = {
        "schema": SCHEMA_ROUTER,
        "query": text if isinstance(text, str) else "",
        "trigger": None,
        "preset_id": None,
        "entry": None,
        "execution_scope": None,
        "protocol": None,
        "reason": "",
        "confidence": 0.0,
        "negated": refused,
        "candidates": [{"preset_id": item["preset_id"], "matched": item["token"],
                        "kind": item["kind"]} for item in candidates],
        "next_action": None,
        "requires_confirmation": False,
        "expert_phase": phase,
        "action": "HOLD",
        "hold_reason": None,
    }

    def select(preset: Dict[str, Any], trigger: str, reason: str, confidence: float) -> Dict[str, Any]:
        payload.update({
            "trigger": trigger, "preset_id": preset["id"], "entry": preset["entry"],
            "execution_scope": preset["execution_scope"], "protocol": preset["protocol"],
            "reason": reason, "confidence": round(confidence, 3), "action": "ROUTE",
        })
        descriptive = _is_descriptive(text)
        payload["next_action"] = "diagnose" if (descriptive or trigger == "auto") else "execute"
        # Anything that can change more than a report needs confirmation when the user only
        # described a symptom; a read-only protocol never does.
        may_act = scope_privilege(preset["execution_scope"]) != "read_only"
        if payload["next_action"] == "diagnose" and may_act:
            payload["requires_confirmation"] = True
            payload["reason"] = reason + "；消息只是陈述问题，先只读诊断，执行前需确认"
        return payload

    if explicit:
        preset = by_id[explicit[0]["preset_id"]]
        return select(preset, "explicit", f"显式指定 preset id：{explicit[0]['token']}", 1.0)
    if candidates:
        top = candidates[0]
        # Ambiguity means an *exact* score tie: a longer, more specific phrase is not a tie,
        # it is the better match ("训练失败" beats the alias "恢复").
        tied = [item for item in candidates
                if item["current_weight"] == top["current_weight"]]
        if len(tied) > 1:
            privileged = min((by_id[item["preset_id"]] for item in tied), key=scope_rank)
            result = select(privileged, "intent",
                            "意图在多个预设间有歧义：" + "、".join(
                                sorted(item["preset_id"] for item in tied))
                            + f"；按最小授权选择 {privileged['execution_scope']}", 0.5)
            result["requires_confirmation"] = True
            result["ambiguous_with"] = sorted(item["preset_id"] for item in tied)
            return result
        preset = by_id[top["preset_id"]]
        entry_matches = entry_hint is not None and entry_hint == preset["entry"]
        trigger = "entry" if entry_matches else ("alias" if top["kind"] == "alias" else "intent")
        reason = f"自然语言命中 {top['kind']} 规则：{top['token']!r}"
        if entry_matches:
            reason += f"；与用户点名的顶层入口 {entry_hint} 一致"
        return select(preset, trigger, reason, 0.9 if entry_matches else 0.8)
    if refused:
        payload.update({"action": "HOLD", "hold_reason": "intent_negated",
                        "reason": "消息显式否定了唯一命中的预设：" + "、".join(refused)})
        return payload
    if phase:
        payload.update({"action": "HOLD", "hold_reason": "expert_phase_entry", "trigger": "expert",
                        "reason": "只给了 phase=R<n> 专家入口，没有预设意图；按既有 R 阶段执行"})
        return payload
    auto = extra_triggers or []
    if auto:
        best = sorted(auto, key=lambda item: (item.get("priority", 10 ** 6),
                                              item.get("preset_id", "")))[0]
        preset = by_id.get(best.get("preset_id"))
        if preset is not None:
            result = select(preset, "auto", "Loop 触发：" + str(best.get("reason", "")), 0.4)
            result["requires_confirmation"] = scope_privilege(
                preset["execution_scope"]) != "read_only"
            return result
    payload.update({"action": "HOLD", "hold_reason": "no_intent_matched",
                    "reason": "没有命中任何预设；请说明目标或直接给出 preset id"})
    return payload


# ---------------------------------------------------------------------------
# Machine-readable signals (the trigger engine's only inputs)
# ---------------------------------------------------------------------------

RESOURCE_TOKENS: Tuple[str, ...] = (
    "oom", "out of memory", "cuda", "gpu", "cudnn", "nccl", "disk", "quota", "no space",
    "dependency", "dependencies", "import error", "modulenotfound", "environment",
    "显存", "内存不足", "磁盘", "配额", "依赖", "环境", "驱动",
)

#: Concentration above which the hypothesis portfolio counts as converged.
PORTFOLIO_CONCENTRATION = 0.7

#: Minimum live candidates before convergence is meaningful.
PORTFOLIO_MIN_CANDIDATES = 3


def _text_of(value: Any) -> str:
    if isinstance(value, str):
        return value.casefold()
    if isinstance(value, (list, tuple)):
        return " ".join(_text_of(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_text_of(item) for item in value.values())
    return ""


def failure_classification(state: Dict[str, Any]) -> Dict[str, Any]:
    """Split recorded failures into engineering vs scientific **by their declared kind**.

    This is a routing classification, never a scientific verdict: an engineering failure says
    something about the implementation, and the R9.O contract already decides what may become
    evidence. Nothing here may mark a hypothesis refuted.
    """
    engineering: Dict[str, int] = {}
    scientific: Dict[str, int] = {}
    unclassified: List[str] = []
    for failure in state.get("failures") or []:
        if not isinstance(failure, dict):
            continue
        kind = failure.get("kind")
        if kind in ENGINEERING_FAILURE_KINDS:
            engineering[str(kind)] = engineering.get(str(kind), 0) + 1
        elif kind in SCIENTIFIC_FAILURE_KINDS:
            scientific[str(kind)] = scientific.get(str(kind), 0) + 1
        else:
            unclassified.append(str(failure.get("id")))
    return {"engineering": engineering, "scientific": scientific,
            "unclassified": sorted(unclassified)}


def terminal_failed_experiments(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [item for item in state.get("experiments") or []
            if isinstance(item, dict) and item.get("status") == "failed"]


def _resource_hits(state: Dict[str, Any]) -> List[str]:
    hits: List[str] = []
    for failure in state.get("failures") or []:
        if not isinstance(failure, dict):
            continue
        blob = _text_of([failure.get("what"), failure.get("why"), failure.get("kind")])
        hits.extend(token for token in RESOURCE_TOKENS if token in blob)
    for experiment in state.get("experiments") or []:
        if not isinstance(experiment, dict) or experiment.get("status") != "failed":
            continue
        blob = _text_of([experiment.get("unexpected"), experiment.get("interpretation")])
        hits.extend(token for token in RESOURCE_TOKENS if token in blob)
    return sorted(set(hits))


def _repair_covers(state: Dict[str, Any], experiment_id: str) -> bool:
    for repair in state.get("repairs") or []:
        if not isinstance(repair, dict):
            continue
        if experiment_id in [str(item) for item in repair.get("targets") or []]:
            return True
    return False


def _portfolio_concentration(state: Dict[str, Any]) -> Dict[str, Any]:
    live = [item for item in state.get("hypotheses") or []
            if isinstance(item, dict) and item.get("status") in ("active", "elite")]
    if not live:
        return {"live": 0, "share": 0.0, "top": None, "converged": False}
    counts: Dict[str, int] = {}
    for item in live:
        key = str(item.get("island") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    top = max(counts, key=lambda key: (counts[key], key))
    share = round(counts[top] / len(live), 4)
    return {"live": len(live), "share": share, "top": top, "counts": counts,
            "converged": len(live) >= PORTFOLIO_MIN_CANDIDATES and share > PORTFOLIO_CONCENTRATION}


#: Where the runtime records that the user authorized an autonomous loop. It lives in the
#: scheduler telemetry (control plane), never in the canonical state.
LOOP_AUTHORIZATION_KEY = "autonomous_loop"


def loop_authorization(scheduler: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The recorded loop authorization, if any. `scope` bounds which privileges it covers."""
    record = (scheduler or {}).get(LOOP_AUTHORIZATION_KEY)
    if not isinstance(record, dict) or record.get("authorized") is not True:
        return {"authorized": False, "scope": None, "covers": []}
    scope = record.get("scope")
    covers = ["read_only", "derived", "advisory"]
    if scope in ("discovery_only", "discovery"):
        covers += ["discovery"]
    if scope in ("strategy", "full"):
        covers += ["discovery", "strategy"]
    if scope == "full":
        covers += ["execute"]
    return {"authorized": True, "scope": scope, "covers": covers,
            "since_state_version": record.get("since_state_version"),
            "note": record.get("note")}


def signal_snapshot(
    state: Dict[str, Any],
    *,
    scheduler: Optional[Dict[str, Any]] = None,
    index: Optional[Dict[str, Any]] = None,
    revisions: Optional[Sequence[Dict[str, Any]]] = None,
    index_missing: bool = False,
    projection: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute every signal from machine-readable state only.

    No signal is a self-report and none of them is a scientific judgement. Text is used in
    exactly one place — the resource token scan — and the result is flagged `text_based` so a
    caller knows it needs a machine-readable corroboration before acting.
    """
    # `index` is what is on disk (drift is a property of the *stored* projection);
    # `projection` is the in-memory rebuild the content signals are computed from. Using the
    # rebuild for both made "the index is missing" undetectable.
    content = projection if projection is not None else index
    signals: Dict[str, Any] = {}
    state_version = state.get("state_version")

    report = sc.check_state(state)
    violations = [item for item in report.all_violations()] if not report.ok else []
    signals["state_integrity"] = {
        "ok": bool(report.ok),
        "count": len(violations),
        "rules": sorted({item.rule for item in violations}),
        "paths": [item.path for item in violations[:8]],
    }

    # Outcome-transaction errors, computed once: the same validator verdict backs both the
    # R10/R11 classification and the engineering-failure signal.
    outcome_errors = eo.state_errors(state)
    r10_report = r10_status(state, state_errors=outcome_errors)

    drift: List[str] = []
    if index is None or index_missing:
        drift.append("cognition 索引缺失（磁盘上没有可用的认知投影）")
    else:
        if index.get("state_version") != state_version:
            drift.append(f"索引 state_version={index.get('state_version')} 与 canonical "
                         f"{state_version} 不一致")
        digest = (index.get("digest") or {}).get("state")
        if isinstance(digest, str) and digest and digest != cg.digest_of(state):
            drift.append("索引 state 摘要与 canonical 不一致")
    signals["context_drift"] = {"detected": bool(drift), "reasons": drift}

    hard_cm = [item for item in (content or {}).get("diagnostics") or []
               if isinstance(item, dict) and not cg.is_warning(str(item.get("rule")))]
    memory_reasons = [f"{item.get('rule')} {item.get('path')}" for item in hard_cm]
    if content is not None and not (content.get("insights") is not None):
        memory_reasons.append("索引缺少 insights 投影")
    signals["memory_drift"] = {"detected": bool(memory_reasons), "reasons": memory_reasons}

    conflict_rules = {"V2", "V3", "V5", "V19", "V20", "EO1"}
    conflicts = [item.render() for item in violations if item.rule in conflict_rules]
    for claim in state.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        if claim.get("refuting_evidence") and claim.get("status") == "supported":
            conflicts.append(f"claims[{claim.get('id')}].status=supported 但存在 refuting_evidence")
    signals["evidence_conflict"] = {"detected": bool(conflicts), "conflicts": conflicts[:8]}

    classification = failure_classification(state)
    failed_experiments = terminal_failed_experiments(state)
    # A failed experiment is "unhandled" only while it has neither an R10 disposition nor a
    # committed outcome receipt. Deriving this from repairs alone re-signalled every legally
    # committed INVALID_EXPERIMENT forever.
    unhandled = [item.get("id") for item in failed_experiments
                 if not _repair_covers(state, str(item.get("id")))
                 and (r10_report.get(str(item.get("id"))) or {}).get("status")
                 != R10_COMMITTED]
    signals["engineering_failure"] = {
        "detected": bool(classification["engineering"]) or bool(unhandled),
        "kinds": classification["engineering"],
        "failed_experiments": [item.get("id") for item in failed_experiments],
        "unhandled_experiments": unhandled,
    }
    signals["scientific_failure"] = {
        "detected": bool(classification["scientific"]),
        "kinds": classification["scientific"],
        "note": "科学类失败只供 R9.O/R10 使用；本路由器不据此判定假设被否证",
    }
    resource_hits = _resource_hits(state)
    signals["resource_blocked"] = {
        "detected": bool(resource_hits),
        "tokens": resource_hits,
        "text_based": True,
        "budget": (state.get("contract") or {}).get("resources"),
    }

    zero_streak = pc.trailing_zero_streak(scheduler)
    competitions = (content or {}).get("competitions") or []
    switch = pc.diagnosis_switch(state, competitions, scheduler,
                                 (content or {}).get("mechanisms"))
    warning_rules = {str(item.get("rule")) for item in (content or {}).get("diagnostics") or []}
    stagnation_reasons: List[str] = []
    if zero_streak >= 2:
        stagnation_reasons.append(f"连续 {zero_streak} 次零信息增益诊断")
    if switch.get("action") != "CONTINUE_ATTRIBUTION":
        stagnation_reasons.append(f"行为切换建议：{switch.get('action')}")
    for rule in sorted({"CM8", "CM9", "CM10"} & warning_rules):
        stagnation_reasons.append(f"认知层提示：{rule}")
    signals["stagnation"] = {"detected": bool(stagnation_reasons),
                             "reasons": stagnation_reasons,
                             "switch_action": switch.get("action"),
                             "zero_streak": zero_streak,
                             "switch": switch}

    records = ((scheduler or {}).get("eig_calibration") or {}).get("records") or []
    pseudo = [item for item in records if isinstance(item, dict)
              and item.get("actual_information_gain") == "zero"
              and item.get("predicted_information_gain") in ("high", "medium")]
    deltas: Dict[str, int] = {}
    for item in records:
        if isinstance(item, dict):
            key = json.dumps(item.get("observed_delta"), sort_keys=True, ensure_ascii=False)
            deltas[key] = deltas.get(key, 0) + 1
    repeated = [count for count in deltas.values() if count >= 2]
    signals["pseudo_progress"] = {
        "detected": bool(pseudo) or bool(repeated),
        "predicted_high_actual_zero": len(pseudo),
        "repeated_deltas": len(repeated),
        "records": len(records),
    }

    concentration = _portfolio_concentration(state)
    signals["portfolio_convergence"] = concentration

    updates = _strategy_updates(state, content, scheduler, revisions)
    signals["evolution_due"] = {
        "detected": bool(updates),
        "pending_updates": len(updates),
        "operators": sorted({str(item.get("subject")) for item in updates}),
    }
    signals["loop_authorization"] = loop_authorization(scheduler)
    signals["_snapshot"] = {
        "state_version": state_version,
        "scheduler_version": (scheduler or {}).get("state_version"),
        "index_version": (index or {}).get("state_version"),
        "index_present": not (index is None or index_missing),
        "at": (scheduler or {}).get("updated_at"),
    }
    return signals


def _strategy_updates(
    state: Dict[str, Any],
    index: Optional[Dict[str, Any]],
    scheduler: Optional[Dict[str, Any]],
    revisions: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Pending, already-authorised strategy updates (reused, never re-derived here)."""
    if index is None:
        return []
    try:
        payload = sm.strategy_updates(state, index, scheduler)
    except Exception:  # noqa: BLE001 — a strategy computation must not break the router
        return []
    updates = payload.get("updates") if isinstance(payload, dict) else None
    return [item for item in updates or [] if isinstance(item, dict)]


def signal_fingerprint(signals: Dict[str, Any], preset_id: str) -> str:
    """A stable identity for "this recovery, on this situation"."""
    relevant = {key: value for key, value in signals.items() if not key.startswith("_")}
    return cg.digest_of({"preset": preset_id, "signals": relevant,
                         "state_version": (signals.get("_snapshot") or {}).get("state_version")})


# ---------------------------------------------------------------------------
# Recovery ledger and anti-recursion guard
# ---------------------------------------------------------------------------

def ledger_path(cognition_dir: Path) -> Path:
    return cognition_dir / RECOVERY_LOG_NAME


def load_ledger(path: Path) -> Tuple[List[Dict[str, Any]], List[Diagnostic]]:
    records: List[Dict[str, Any]] = []
    diagnostics: List[Diagnostic] = []
    if not path.exists():
        return records, diagnostics
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            diagnostics.append(Diagnostic("PR7", f"{RECOVERY_LOG_NAME}:{lineno}",
                                          f"无法解析为 JSON（{exc.msg}）"))
            continue
        if isinstance(record, dict):
            record["_line"] = lineno
            records.append(record)
    return records, diagnostics


def recovery_guard(
    records: Sequence[Dict[str, Any]],
    preset: Dict[str, Any],
    fingerprint: str,
    state_version: Optional[int],
) -> Dict[str, Any]:
    """Refuse a repeat of the same recovery on the same situation (`PR8`).

    Three rules, in order: the identical fingerprint at the identical snapshot is refused
    outright; a `cooldown_rounds` window stops immediately repeated attempts; and
    `max_attempts` per fingerprint puts a hard cap on retries. Together they make the recovery
    layer unable to loop, without touching the AALG diagnostic budget.
    """
    same_preset = [item for item in records if item.get("preset_id") == preset["id"]]
    identical = [item for item in same_preset
                 if item.get("signal_fingerprint") == fingerprint
                 and item.get("at_state_version") == state_version]
    if identical:
        return {"allowed": False, "reason": "already_attempted_at_this_snapshot",
                "detail": f"同一状态快照（state_version={state_version}）已执行过 "
                          f"{preset['id']}；先改变状态或换协议",
                "attempts": len(identical)}
    attempts = len([item for item in same_preset
                    if item.get("signal_fingerprint") == fingerprint])
    if attempts >= preset["max_attempts"]:
        return {"allowed": False, "reason": "attempt_limit_reached",
                "detail": f"{preset['id']} 在同一指纹上已尝试 {attempts} 次"
                          f"（上限 {preset['max_attempts']}）；HOLD 并交人裁决",
                "attempts": attempts}
    cooldown = preset.get("cooldown_rounds") or 0
    if cooldown and same_preset and isinstance(state_version, int):
        last = max((item.get("at_state_version") for item in same_preset
                    if isinstance(item.get("at_state_version"), int)), default=None)
        if isinstance(last, int) and state_version - last < cooldown:
            return {"allowed": False, "reason": "cooldown_active",
                    "detail": f"{preset['id']} 冷却中：距上次执行 {state_version - last} 轮"
                              f"（要求 {cooldown}）", "attempts": attempts}
    return {"allowed": True, "reason": None, "attempts": attempts}


def append_ledger(path: Path, entry: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _guard_candidate(
    signals: Dict[str, Any],
    preset: Dict[str, Any],
    records: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    fingerprint = signal_fingerprint(signals, preset["id"])
    guard = recovery_guard(records, preset, fingerprint,
                           (signals.get("_snapshot") or {}).get("state_version"))
    return {**guard, "fingerprint": fingerprint}


# ---------------------------------------------------------------------------
# The trigger engine
# ---------------------------------------------------------------------------

#: The primary signal each auto preset consumes, used for the reason text and as a parity anchor
#: (`registry_errors` checks it is one of the signals the preset declares). Firing is driven by
#: the *declared* signal list, so a registry-provided trigger cannot be silently ignored.
AUTO_SIGNAL_MAP: Dict[str, str] = {
    "evidence-conflict-repair": "evidence_conflict",
    "context-drift-recovery": "context_drift",
    "memory-consolidation": "memory_drift",
    "resource-recovery": "resource_blocked",
    "experiment-failure-recovery": "engineering_failure",
    "loop-health-check": "pseudo_progress",
    "stagnation-breaker": "stagnation",
    "strategy-evolution": "evolution_due",
    "hypothesis-rebalance": "portfolio_convergence",
    "discovery-replay": "evolution_due",
}

#: Signals that must never be routed to a *scientific* recovery: fixing the run first.
SAFETY_FIRST = ("evidence_conflict", "state_integrity", "context_drift", "memory_drift")


def _signal_fired(signals: Dict[str, Any], signal_id: str) -> bool:
    value = signals.get(signal_id)
    if not isinstance(value, dict):
        return False
    if signal_id == "state_integrity":
        return not value.get("ok", True)
    if signal_id == "memory_drift":
        return bool(value.get("detected"))
    return bool(value.get("detected"))


def trigger(
    state: Dict[str, Any],
    *,
    index: Optional[Dict[str, Any]] = None,
    scheduler: Optional[Dict[str, Any]] = None,
    revisions: Optional[Sequence[Dict[str, Any]]] = None,
    records: Optional[Sequence[Dict[str, Any]]] = None,
    index_missing: bool = False,
    projection: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pick at most one recovery preset for the current situation, or HOLD.

    Ordering is by safety, not by severity of the science: an unsound evidence base, a wrong
    context or a drifted memory is fixed before any question about stagnation is asked. Every
    candidate passes the anti-recursion guard, and one blocked candidate does not hide the next.
    """
    signals = signal_snapshot(state, scheduler=scheduler, index=index, revisions=revisions,
                              index_missing=index_missing, projection=projection)
    records = list(records or [])
    payload: Dict[str, Any] = {
        "schema": SCHEMA_TRIGGER,
        "snapshot": signals.get("_snapshot"),
        "signals": {key: value for key, value in signals.items() if not key.startswith("_")},
        "candidates": [],
        "selected": None,
        "action": "HOLD",
        "hold_reason": None,
        "reason": "",
    }
    if not signals["state_integrity"]["ok"]:
        payload.update({
            "hold_reason": "state_integrity_blocked",
            "reason": "canonical state 存在硬违规（"
                      + "、".join(signals["state_integrity"]["rules"])
                      + "）：先按 R11/R13 修状态，恢复协议不得在坏状态上执行",
        })
        return payload
    for preset in sorted(PRESETS, key=lambda item: (item["priority"], item["id"])):
        if preset.get("auto") is None:
            continue
        declared = list(preset["auto"].get("signals") or [])
        signal_id = next((item for item in declared if _signal_fired(signals, item)), None)
        if signal_id is None:
            continue
        guard = _guard_candidate(signals, preset, records)
        recommended_only = preset["auto"].get("mode") == "recommend"
        authorization = signals.get("loop_authorization") or {}
        controlled = False
        if recommended_only and authorization.get("authorized") \
                and scope_privilege(preset["execution_scope"]) in authorization.get("covers", []):
            # An authorized Autonomous Loop may start controlled Discovery — but never an
            # experiment: the promotion is bounded by the preset's own scope.
            recommended_only = False
            controlled = True
        candidate = {
            "preset_id": preset["id"], "signal": signal_id,
            "priority": preset["priority"], "execution_scope": preset["execution_scope"],
            "requires_confirmation": preset["execution_scope"] == "execute"
            or scope_privilege(preset["execution_scope"]) != "read_only",
            "recommended_only": recommended_only,
            "controlled": controlled,
            "authorization": {"scope": authorization.get("scope")} if controlled else None,
            "reason": _signal_reason(signals, signal_id),
            "allowed": guard["allowed"] and not recommended_only,
            "blocked_by": ("recommended_only" if recommended_only else guard["reason"]),
            "detail": guard.get("detail"), "fingerprint": guard["fingerprint"],
            "attempts": guard["attempts"],
        }
        if signal_id == "evolution_due" and preset["id"] == "discovery-replay":
            candidate["note"] = "先做策略进化，回放用于验证其效果"
        payload["candidates"].append(candidate)
        # Select on the *candidate's* verdict: a `recommended_only` proposal has an allowed
        # guard but must never be started by the trigger.
        if payload["selected"] is None and candidate["allowed"]:
            payload["selected"] = candidate
    if payload["selected"] is None:
        blocked = [item for item in payload["candidates"] if not item["allowed"]]
        if blocked:
            first = blocked[0]
            payload.update({"hold_reason": first["blocked_by"],
                            "reason": f"{first['preset_id']} 被防重入守卫拒绝：{first['detail']}"})
        else:
            payload.update({"hold_reason": "no_signal",
                            "reason": "没有触发任何恢复信号：当前状态下没有可执行的恢复动作"})
        return payload
    payload.update({"action": "RECOVER", "reason": payload["selected"]["reason"]})
    return payload


def _signal_reason(signals: Dict[str, Any], signal_id: str) -> str:
    value = signals.get(signal_id) or {}
    if signal_id == "context_drift":
        return "上下文/投影漂移：" + "；".join(value.get("reasons") or [])
    if signal_id == "memory_drift":
        return "记忆漂移：" + "；".join(value.get("reasons") or [])
    if signal_id == "evidence_conflict":
        return "证据冲突：" + "；".join(value.get("conflicts") or [])
    if signal_id == "engineering_failure":
        return ("工程故障：" + json.dumps(value.get("kinds") or {}, ensure_ascii=False)
                + f"；失败实验 {value.get('failed_experiments')}")
    if signal_id == "resource_blocked":
        return "资源/环境阻断（文本线索，需机器可读佐证）：" + "、".join(value.get("tokens") or [])
    if signal_id == "stagnation":
        return "科研停滞：" + "；".join(value.get("reasons") or [])
    if signal_id == "pseudo_progress":
        return (f"疑似伪进展：预测高而实际零增益 {value.get('predicted_high_actual_zero')} 次，"
                f"重复增量 {value.get('repeated_deltas')} 组")
    if signal_id == "portfolio_convergence":
        return (f"候选集中：{value.get('top')} 占 {value.get('share')}"
                f"（{value.get('live')} 个 live 候选）")
    if signal_id == "evolution_due":
        return "策略修订待应用：" + "、".join(value.get("operators") or [])
    return signal_id


# ---------------------------------------------------------------------------
# Project context and the sixteen protocols
# ---------------------------------------------------------------------------

def project_context(state_path: Path, cognition_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Everything a preset needs, read once through the existing loaders."""
    state = cg.load_state(state_path)
    cognition_dir = cognition_dir or cg.cognition_dir_for(state_path)
    revisions, revision_diagnostics = cg.load_revisions(cognition_dir / cg.REVISIONS_NAME)
    cards, scheduler, audits = cg.projection_inputs(state, state_path.parent)
    index, index_diagnostics = cg.full_index(state, revisions, cg.route_of(state_path),
                                             cards, scheduler, audits)
    ledger, ledger_diagnostics = load_ledger(ledger_path(cognition_dir))
    index_path = cognition_dir / cg.INDEX_NAME
    index_on_disk: Optional[Dict[str, Any]] = None
    if index_path.is_file():
        try:
            parsed = json.loads(index_path.read_text(encoding="utf-8"))
            index_on_disk = parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            index_on_disk = None
    return {
        "state_path": state_path, "route_dir": state_path.parent, "cognition_dir": cognition_dir,
        "state": state, "revisions": revisions, "cards": cards, "scheduler": scheduler,
        "audits": audits, "index": index, "index_on_disk": index_on_disk,
        "index_missing": index_on_disk is None,
        "diagnostics": list(revision_diagnostics) + list(index_diagnostics)
        + list(ledger_diagnostics),
        "records": ledger,
        "canonical_digest": cg.digest_of(state),
    }


def _result(preset: Dict[str, Any], status: str, **kw: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "preset_id": preset["id"], "status": status, "protocol": preset["protocol"],
        "entry": preset["entry"], "execution_scope": preset["execution_scope"],
        "reused": list(preset["reuses"]), "observed": {}, "decision": {},
        "steps": [], "writes": [], "changed_decision": None, "next_action": None,
    }
    payload.update(kw)
    payload["_schema"] = SCHEMA_ROUTER
    return payload


def _rec_key(recommendation: Dict[str, Any]) -> Dict[str, Any]:
    return {"menu": recommendation.get("menu"), "operator": recommendation.get("operator"),
            "island": recommendation.get("island"), "shift": recommendation.get("shift")}


def _recommend(ctx: Dict[str, Any], revisions: Optional[Sequence[Dict[str, Any]]] = None
               ) -> Dict[str, Any]:
    return sm.recommend_strategy(ctx["state"], ctx["index"], ctx["scheduler"],
                                 list(revisions if revisions is not None else ctx["revisions"]))


#: R9.O → R10/R11 completion states, per experiment.
#:
#: * `COMMITTED` — a formal outcome transaction is on record and passes its own validator.
#: * `NEEDS_ANALYSIS` — the experiment is terminal but has no legal outcome analysis yet.
#: * `BLOCKED` — a receipt exists but is incomplete, damaged, or contradicts the state.
#: * `PENDING_EXECUTION` — not terminal, so R10/R11 does not apply yet.
R10_COMMITTED = "COMMITTED"
R10_NEEDS_ANALYSIS = "NEEDS_ANALYSIS"
R10_BLOCKED = "BLOCKED"
R10_PENDING_EXECUTION = "PENDING_EXECUTION"

#: The exact receipt keys `evidence_outcome._apply` writes; a partial block is not a receipt.
R10_RECEIPT_KEYS = ("packet", "analysis", "audit", "validation_context", "audit_trail")


def r10_status(state: Dict[str, Any], *,
               state_errors: Optional[Sequence[str]] = None) -> Dict[str, Dict[str, Any]]:
    """Per-experiment R10/R11 completion, derived from the transaction receipt.

    The authority is `evidence_outcome.state_errors()` — it re-validates the analysis key set, the
    packet/analysis/audit digests, every audit check, the frozen policy, the historical
    re-validation against `validation_context`, the "previously analysed result was not removed or
    rewritten" invariant, the `audit_trail` (`state_version == result_at_state_version`,
    `previous_state.version == state_version - 1`, decision match, non-empty `state_delta`,
    timestamp) and the `result`/`status` consistency.

    A repair is **not** part of this judgement: `NEGATIVE_EVIDENCE`, `INVALID_EXPERIMENT`,
    hypothesis-only and partial-scope transactions commit legally without ever writing one, and
    requiring a repair made them look permanently unfinished.

    Reporting `COMMITTED` means "the transaction was legally committed", never "the scientific
    claim is supported" and never "the next GPU run is authorized".
    """
    if state_errors is None:
        state_errors = eo.state_errors(state)
    errors = [str(item) for item in state_errors]
    experiments = [item for item in state.get("experiments") or [] if isinstance(item, dict)]
    known_ids = {str(item.get("id")) for item in experiments}
    global_errors = [item for item in errors
                     if not any(item.startswith(f"{xid}: ") for xid in known_ids)]
    report: Dict[str, Dict[str, Any]] = {}
    for experiment in experiments:
        xid = str(experiment.get("id"))
        if experiment.get("status") not in ("done", "failed"):
            report[xid] = {"status": R10_PENDING_EXECUTION,
                           "reason": f"实验状态为 {experiment.get('status')!r}，尚未进入 R10/R11"}
            continue
        receipt = experiment.get("outcome_analysis")
        if not isinstance(receipt, dict):
            report[xid] = {"status": R10_NEEDS_ANALYSIS,
                           "reason": "终态实验尚无 outcome_analysis 事务"}
            continue
        missing = [key for key in R10_RECEIPT_KEYS if key not in receipt]
        if missing:
            report[xid] = {"status": R10_BLOCKED,
                           "reason": "凭证不完整，缺少：" + ", ".join(missing)}
            continue
        trail = receipt.get("audit_trail") if isinstance(receipt.get("audit_trail"), dict) else {}
        version = experiment.get("result_at_state_version")
        if not isinstance(version, int) or trail.get("state_version") != version:
            report[xid] = {"status": R10_BLOCKED,
                           "reason": ("audit_trail.state_version 与 result_at_state_version 不一致"
                                      f"（{trail.get('state_version')!r} vs {version!r}）")}
            continue
        if version > state.get("state_version", version):
            report[xid] = {"status": R10_BLOCKED,
                           "reason": "凭证版本晚于当前 state_version（版本冲突）"}
            continue
        own = [item for item in errors if item.startswith(f"{xid}: ")]
        if own:
            report[xid] = {"status": R10_BLOCKED, "reason": "; ".join(own[:2])}
            continue
        if global_errors:
            report[xid] = {"status": R10_BLOCKED, "reason": "; ".join(global_errors[:2])}
            continue
        analysis = receipt.get("analysis") if isinstance(receipt.get("analysis"), dict) else {}
        report[xid] = {"status": R10_COMMITTED,
                       "reason": "正式事务凭证通过校验（analysis/audit/audit_trail 一致）",
                       "analysis_id": analysis.get("id"),
                       "committed_at_state_version": version}
    return report


def r10_pending(state: Dict[str, Any], *,
                state_errors: Optional[Sequence[str]] = None) -> List[str]:
    """Terminal experiments that still need their R9.O analysis (compatibility wrapper).

    `BLOCKED` receipts are deliberately *not* listed here: they are a hold condition to be
    reported, not work to be repeated.
    """
    return sorted(xid for xid, item in r10_status(state, state_errors=state_errors).items()
                  if item["status"] == R10_NEEDS_ANALYSIS)


def r10_blocked(state: Dict[str, Any], *,
                state_errors: Optional[Sequence[str]] = None) -> Dict[str, str]:
    """Terminal experiments whose receipt is incomplete, damaged or in conflict."""
    return {xid: item["reason"] for xid, item in
            sorted(r10_status(state, state_errors=state_errors).items())
            if item["status"] == R10_BLOCKED}


def _r10_covered(state: Dict[str, Any], experiment_id: str,
                 state_errors: Optional[Sequence[str]] = None) -> bool:
    """Whether the experiment's outcome transaction is on record (used by the signals)."""
    item = r10_status(state, state_errors=state_errors).get(str(experiment_id))
    return bool(item) and item["status"] == R10_COMMITTED


#: Where a post-update Assurance artifact lives, next to the route's state. It is a *derived*
#: control-plane artifact: the canonical state stays the only scientific authority, and R7 owns
#: the review. `evidence_outcome.decision --assurance <file>` accepts exactly this document.
OUTCOME_ASSURANCE_SUBDIR: Tuple[str, ...] = ("assurance", "outcome")
SCHEMA_OUTCOME_ASSURANCE = "evidence-outcome-assurance@1"

#: Assurance lifecycle states. `PENDING`/`STALE` keep the gate at `NEEDS_REVIEW`; `FAILED`
#: blocks; `CONSUMED` means the real `decision_gate` accepted it.
ASSURANCE_PENDING = "PENDING"
ASSURANCE_VERIFIED = "VERIFIED"
ASSURANCE_FAILED = "FAILED"
ASSURANCE_STALE = "STALE"

#: A superseded analysis (a later result already reassessed its targets) needs no review of its
#: own: `decision_gate` says so itself, and treating it as pending would block the loop forever.
ASSURANCE_SUPERSEDED = "SUPERSEDED"

#: A review exists but a check came back UNKNOWN (or otherwise still NEEDS_REVIEW). The reviewer
#: has been asked and answered "not yet": the loop waits with the recorded blocker and the stated
#: re-review conditions instead of sending the same question back every round.
ASSURANCE_UNKNOWN = "UNKNOWN"


def outcome_assurance_path(route_dir: Optional[Path], analysis_id: Any) -> Optional[Path]:
    """The conventional location of the Assurance for one committed analysis."""
    if route_dir is None or not analysis_id:
        return None
    return Path(route_dir).joinpath(*OUTCOME_ASSURANCE_SUBDIR, f"{analysis_id}.json")


def load_outcome_assurance(route_dir: Optional[Path],
                           analysis_id: Any) -> Dict[str, Any]:
    """Read the Assurance artifact for an analysis, if one is on disk.

    Only the document shape is checked here; the authoritative verification (state/analysis
    digests and every check verdict) stays inside `evidence_outcome.decision_gate`, so this can
    never upgrade a review into a pass.
    """
    path = outcome_assurance_path(route_dir, analysis_id)
    if path is None or not path.is_file():
        return {"found": False, "path": None, "assurance": None}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return {"found": True, "path": str(path), "assurance": None,
                "problem": "unreadable assurance artifact"}
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_OUTCOME_ASSURANCE:
        return {"found": True, "path": str(path), "assurance": None,
                "problem": "unexpected assurance schema"}
    return {"found": True, "path": str(path), "assurance": payload}


def assurance_status(state: Dict[str, Any],
                     route_dir: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    """Per-experiment post-update Assurance state, checked with the real `decision_gate`.

    A missing artifact stays `PENDING` (NEEDS_REVIEW), a failing check is `FAILED`, and an
    artifact whose binding digests no longer match the state is `STALE`: it must be re-reviewed,
    not reused and not treated as a failure of the science.
    """
    status: Dict[str, Dict[str, Any]] = {}
    for experiment in state.get("experiments") or []:
        if not isinstance(experiment, dict):
            continue
        receipt = experiment.get("outcome_analysis")
        if not isinstance(receipt, dict):
            continue
        analysis = receipt.get("analysis") if isinstance(receipt.get("analysis"), dict) else {}
        # Ask the real gate even without an artifact: it reports whether a *later* result already
        # reassessed this analysis's targets. Such an analysis needs no review of its own and must
        # not keep the loop parked on a review nobody owes.
        baseline = eo.decision_gate(state, str(experiment.get("id")))
        baseline_reason = "; ".join(str(item.get("reason", item))
                                   for item in baseline.get("decisions") or [])
        if baseline.get("status") != "PASS" and "superseded" in baseline_reason.lower():
            status[str(experiment.get("id"))] = {
                "status": ASSURANCE_SUPERSEDED, "gate": baseline.get("status"),
                "source": "superseded", "analysis_id": analysis.get("id"), "path": None,
                "reason": baseline_reason}
            continue
        loaded = load_outcome_assurance(route_dir, analysis.get("id"))
        if not loaded["found"]:
            status[str(experiment.get("id"))] = {
                "status": ASSURANCE_PENDING, "gate": "NEEDS_REVIEW", "source": "missing",
                "analysis_id": analysis.get("id"), "path": None,
                "reason": "no post-update Assurance artifact found"}
            continue
        if loaded["assurance"] is None:
            status[str(experiment.get("id"))] = {
                "status": ASSURANCE_PENDING, "gate": "NEEDS_REVIEW", "source": "invalid",
                "analysis_id": analysis.get("id"), "path": loaded["path"],
                "reason": loaded.get("problem", "invalid assurance artifact")}
            continue
        gate = eo.decision_gate(state, str(experiment.get("id")), loaded["assurance"])
        verdict = gate.get("status")
        if verdict == "PASS":
            lifecycle, reason = ASSURANCE_VERIFIED, None
        elif verdict == "FAIL":
            failures = "; ".join(str(item) for item in gate.get("errors") or [])
            if "stale" in failures.lower() or "invalid" in failures.lower():
                lifecycle, reason = ASSURANCE_STALE, failures
            else:
                lifecycle, reason = ASSURANCE_FAILED, failures
        else:
            reasons = "; ".join(str(item.get("reason", item))
                                for item in gate.get("decisions") or []) or str(verdict)
            if "superseded" in reasons.lower():
                lifecycle, reason = ASSURANCE_SUPERSEDED, reasons
            else:
                # The artifact exists and was actually reviewed: this is a recorded blocker,
                # not an outstanding task.
                lifecycle, reason = ASSURANCE_UNKNOWN, reasons
        conditions = loaded["assurance"].get("re_review_conditions")
        status[str(experiment.get("id"))] = {
            "status": lifecycle, "gate": verdict, "source": "artifact",
            "analysis_id": analysis.get("id"), "path": loaded["path"], "reason": reason,
            "reviewer": loaded["assurance"].get("reviewer"),
            "verification_tier": loaded["assurance"].get("verification_tier"),
            "re_review_conditions": list(conditions) if isinstance(conditions, list) else [],
            "checks": {name: item.get("status") for name, item in
                       (loaded["assurance"].get("checks") or {}).items()
                       if isinstance(item, dict)}}
    return status


def _assurance_dependencies(state: Dict[str, Any], pending: Sequence[str]) -> List[str]:
    """Planned experiments whose targets overlap an experiment still awaiting Assurance.

    An independent new action is not blocked by an unrelated review; an action that depends on a
    target whose outcome is not yet assured must wait.
    """
    pending_set = set(pending)
    touched: Dict[str, set] = {}
    for experiment in state.get("experiments") or []:
        if not isinstance(experiment, dict) or str(experiment.get("id")) not in pending_set:
            continue
        receipt = experiment.get("outcome_analysis") or {}
        analysis = receipt.get("analysis") if isinstance(receipt.get("analysis"), dict) else {}
        targets = {str(item.get("id")) for item in
                   (analysis.get("claim_updates") or []) + (analysis.get("hypothesis_updates") or [])
                   if isinstance(item, dict)}
        touched[str(experiment.get("id"))] = targets
    dependent: List[str] = []
    for experiment in state.get("experiments") or []:
        if not isinstance(experiment, dict) or experiment.get("status") not in ("planned", "running"):
            continue
        xid = str(experiment.get("id"))
        own = {str(item) for item in
               (experiment.get("claim_targeted") or []) + (experiment.get("hypothesis_targeted") or [])}
        dep_chain = {str(item) for item in experiment.get("depends_on") or []}
        if any(own & targets or xid in {str(i) for i in targets} for targets in touched.values()) \
                or (dep_chain & pending_set):
            dependent.append(xid)
    return sorted(dependent)


def _loop_step(ctx: Dict[str, Any], *,
               strategy_choice: Optional[str] = None) -> Dict[str, Any]:
    """Choose the next loop step from **per-experiment** todo and Assurance state.

    Ordering: contract → candidates → damaged receipts (hold) → missing analyses (R9.O) →
    failed Assurance (hold) → dependent planned work (hold) → independent planned work →
    consolidate a stale projection → pending Assurance → the Scheduler's next legal action.
    A completed outcome transaction never authorizes new dependent work by itself, and a review
    that is merely missing is a todo, not a failure.

    `strategy_choice` is the action the Strategy Decision Adapter selected inside the same
    `EIG ÷ cost` tier and the same hard-gated legal set (`Skill-RSI` §4.2). It only replaces
    `next_actions[0]` when it is one of the scheduler's own next actions, so it can never
    promote a lower tier, unblock a stop rule or invent an action.
    """
    state = ctx["state"]
    contract = state.get("contract") or {}
    experiments = [item for item in state.get("experiments") or [] if isinstance(item, dict)]
    if not contract:
        return {"phase": "R0", "step": "Understand", "action": "先建立 research contract",
                "blocked": True, "hold": False}
    if not (state.get("hypotheses") or []):
        return {"phase": "R3—R6", "step": "Discover", "action": "生成并筛选候选",
                "blocked": False, "hold": False}
    status = r10_status(state)
    blocked = {xid: item["reason"] for xid, item in sorted(status.items())
               if item["status"] == R10_BLOCKED}
    if blocked:
        return {"phase": "R10/R11", "step": "HOLD",
                "action": "凭证损坏或冲突，需人工处理：" + "；".join(
                    f"{xid}（{reason}）" for xid, reason in blocked.items()),
                "blocked": True, "hold": True, "hold_reason": "outcome_receipt_blocked",
                "blocked_experiments": blocked}
    needs = sorted(xid for xid, item in status.items()
                   if item["status"] == R10_NEEDS_ANALYSIS)
    if needs:
        return {"phase": "R9.O", "step": "Verify",
                "action": f"为 {needs} 提交 Outcome Analysis（R9.O，工程故障不得当作否证）",
                "blocked": False, "hold": False, "pending_r10": needs}
    # Post-update Assurance: discovered from the route's artifacts, verified by the real gate.
    assurance = assurance_status(state, ctx.get("route_dir"))
    failed = {xid: item for xid, item in sorted(assurance.items())
              if item["status"] == ASSURANCE_FAILED}
    if failed:
        return {"phase": "Assurance", "step": "HOLD",
                "action": "post-update Assurance 未通过，不得继续：" + "；".join(
                    f"{xid}（{item['reason']}）" for xid, item in failed.items()),
                "blocked": True, "hold": True, "hold_reason": "assurance_failed",
                "assurance_failed": {xid: item["reason"] for xid, item in failed.items()}}
    pending = sorted(xid for xid, item in assurance.items()
                     if item["status"] in (ASSURANCE_PENDING, ASSURANCE_STALE))
    unknown = sorted(xid for xid, item in assurance.items()
                     if item["status"] == ASSURANCE_UNKNOWN)
    guarantee = {xid: {"lifecycle": item["status"], "gate": item["gate"],
                       "path": item["path"], "reason": item["reason"],
                       "reviewer": item.get("reviewer"),
                       "re_review_conditions": item.get("re_review_conditions")}
                 for xid, item in sorted(assurance.items())}
    planned = [item for item in experiments if item.get("status") in ("planned", "running")]
    dependent = _assurance_dependencies(state, pending)
    if dependent:
        return {"phase": "Assurance", "step": "HOLD",
                "action": ("以下实验依赖尚未完成 post-update Assurance 的结果，必须先审核："
                           + "、".join(dependent) + f"（待审核：{', '.join(pending)}）"),
                "blocked": False, "hold": True, "hold_reason": "assurance_pending_dependency",
                "assurance_pending": pending, "assurance_dependent": dependent,
                "assurance": guarantee, "pending_r10": []}
    if planned:
        return {"phase": "R8/R9", "step": "Intervene",
                "action": f"为 {len(planned)} 个 planned/running 实验走 PEIG/AALG 后执行",
                "blocked": False, "hold": False, "pending_r10": [],
                "assurance_pending": pending, "assurance": guarantee}
    if ctx.get("index_missing") or (ctx.get("index") or {}).get("state_version") != \
            state.get("state_version"):
        return {"phase": "R11+", "step": "Consolidate",
                "action": "所有结果凭证有效：重建认知投影后进入下一轮",
                "blocked": False, "hold": False, "pending_r10": [],
                "assurance_pending": pending, "assurance": guarantee}
    if pending:
        paths = [item["path"] for xid, item in sorted(assurance.items()) if item["path"]]
        states = {xid: assurance[xid]["status"] for xid in pending}
        return {"phase": "R7 / Assurance", "step": "Assurance",
                "action": ("R7 审查任务：为 " + "、".join(
                    f"{xid}（{states[xid]}，analysis {assurance[xid]['analysis_id']}）"
                    for xid in pending)
                    + " 完成四项检查并提交："
                    + "python3 scripts/evidence_outcome.py assurance-store --state <state> "
                      "--experiment <" + pending[0] + "> --reviewer R7 --check "
                      "integrity=PASS:理由 --check claim_calibration=PASS:理由 --check "
                      "reproducibility=PASS:理由 --check stop_rule_compliance=PASS:理由；"
                      "步骤见 references/loop-assurance-review.md；产物路径 "
                    + str(outcome_assurance_path(ctx.get("route_dir"), "<analysis_id>"))),
                "blocked": False, "hold": False, "pending_r10": [],
                "assurance_pending": pending, "assurance_task": True,
                "assurance_states": states, "assurance_paths": paths,
                "assurance": guarantee}
    if unknown:
        details = {xid: {"reason": assurance[xid]["reason"],
                         "re_review_conditions": assurance[xid].get("re_review_conditions") or []}
                   for xid in unknown}
        return {"phase": "R7 / Assurance", "step": "HOLD",
                "action": ("R7 已审查但结论为 UNKNOWN/未决，等待新信息，不重复送审："
                           + "、".join(f"{xid}（{assurance[xid]['reason']}）" for xid in unknown)
                           + "；重新审查条件：" + "；".join(
                               f"{xid}: {' / '.join(details[xid]['re_review_conditions'])}"
                               for xid in unknown)),
                "blocked": False, "hold": True, "hold_reason": "assurance_unknown",
                "assurance_unknown": details, "assurance": guarantee, "pending_r10": []}
    actions = [item for item in (ctx.get("scheduler") or {}).get("next_actions") or []
               if isinstance(item, dict) and item.get("action")]
    if actions:
        scheduler_first = actions[0].get("action")
        dispatched = scheduler_first
        overrode = False
        if strategy_choice and any(item.get("action") == strategy_choice for item in actions):
            dispatched = strategy_choice
            overrode = dispatched != scheduler_first
        return {"phase": "R3—R6/R8", "step": "Discover",
                "action": f"按 Scheduler 选择下一项合法动作：{dispatched}",
                "blocked": False, "hold": False, "pending_r10": [],
                "assurance": guarantee, "assurance_pending": pending,
                "dispatched_action": dispatched,
                "scheduler_first_action": scheduler_first,
                "strategy_overrode_scheduler": overrode,
                "next_actions": [item.get("action") for item in actions[:5]]}
    return {"phase": "HOLD", "step": "HOLD",
            "action": "无新状态、无待分析结果、无合法下一动作：停下交人裁决",
            "blocked": False, "hold": True, "hold_reason": "no_legal_action",
            "assurance": guarantee, "pending_r10": []}

def scoped_policy_state(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """The ACTIVE Skill-RSI scoped policy (if any) and the adapter advice it produces.

    Read-only: it never proposes, promotes or writes a policy. The policy log lives in the
    route control plane, so its absence simply means "no scoped policy".

    A broken hash chain is NOT tolerate-and-continue: a tampered policy log is exactly the
    threat the chain exists for, so the state is reported as tampered and no policy is
    loaded from it.
    """
    import policy_evolution as pe
    path = pe.candidates_path(ctx["state_path"])
    if not path.is_file():
        return {"candidate": None, "advice": None, "records": [], "tampered": False,
                "diagnostics": []}
    records, diagnostics = pe.load_records(ctx["state_path"], tolerant=True)
    if diagnostics:
        return {"candidate": None, "advice": None, "records": records, "tampered": True,
                "diagnostics": [item.render() for item in diagnostics]}
    candidate = pe.active_policy(records)
    advice = pe.advice_from_active_policy(records, ctx["state"], ctx["index"]) \
        if candidate else None
    return {"candidate": candidate, "advice": advice, "records": records, "tampered": False,
            "diagnostics": []}


def strategy_dispatch(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the action the loop should dispatch, through the existing adapter.

    Precedence: an ACTIVE scoped policy evaluated right now on this state → the recorded
    scheduler decision while it is still fresh → the scheduler's own first action. A scoped
    policy whose applicability conditions do not hold is reported as such and ignored. A
    tampered policy store stops policy consumption entirely.
    """
    import policy_evolution as pe
    policy = scoped_policy_state(ctx)
    candidate = policy["candidate"]
    applied = False
    decision = None
    conditions_ok = None
    unmet: List[str] = []
    reason = None
    if policy["tampered"]:
        return {"policy_id": None, "advice": None, "decision": None, "conditions_ok": False,
                "unmet": [], "applied": False, "action": None, "level": None,
                "source": "policy_store_tampered", "reason": "policy_store_tampered",
                "recorded": None, "tampered": True,
                "diagnostics": policy["diagnostics"]}
    if candidate and policy["advice"]:
        conditions_ok, unmet = pe.scope_conditions_hold(candidate, ctx["state"])
        transfer = pe.cross_project_transfer_allowed(
            candidate, ctx["state"], current_route=cg.route_of(ctx["state_path"]))
        if conditions_ok and transfer["status"] != "BLOCK":
            decision = sm.strategy_decision(ctx["state"], ctx["index"], ctx["scheduler"],
                                            ctx["revisions"], advice=policy["advice"])
            applied = bool(decision.get("strategy_applied"))
            reason = decision.get("reason_if_not")
        elif transfer["status"] == "BLOCK":
            conditions_ok = False
            unmet = list(unmet) + [f"cross_project_transfer: {item}"
                                   for item in (transfer.get("reasons") or [])]
            reason = "cross_project_transfer_blocked"
        else:
            reason = "scope_conditions_unmet"
    if not applied:
        recorded = sm.latest_strategy_decision(ctx["scheduler"])
        if isinstance(recorded, dict):
            fresh = recorded.get("state_version") == ctx["state"].get("state_version")
            dispatch = recorded.get("dispatch") or {}
            if fresh and recorded.get("adopted") and dispatch.get("action"):
                decision = None
                reason = "consumed_recorded_decision"
                return {"policy_id": None, "advice": policy.get("advice"),
                        "decision": None, "conditions_ok": conditions_ok, "unmet": unmet,
                        "applied": True, "action": dispatch.get("action"), "level": "L2",
                        "source": "recorded_strategy_decision", "reason": reason,
                        "recorded": recorded}
    return {"policy_id": (candidate or {}).get("policy_id"), "advice": policy.get("advice"),
            "decision": decision, "conditions_ok": conditions_ok, "unmet": unmet,
            "applied": applied, "tampered": False, "diagnostics": [],
            "action": (decision or {}).get("chosen") if applied else None,
            "level": "L2" if applied else None,
            "source": "active_scoped_policy" if applied else "scheduler",
            "reason": reason, "recorded": None}


def _handle_research_loop(ctx: Dict[str, Any], apply: bool) -> Dict[str, Any]:
    preset = presets_by_id()["research-loop"]
    dispatch = strategy_dispatch(ctx)
    step = _loop_step(ctx, strategy_choice=dispatch.get("action") if dispatch["applied"] else None)
    # The next round consumes what the previous round decided: the adapter records its choice
    # in the scheduler telemetry, and the loop prefers that action while it is still legal.
    recorded = sm.latest_strategy_decision(ctx["scheduler"])
    guidance = None
    if isinstance(recorded, dict):
        dispatch_previous = recorded.get("dispatch") or {}
        guidance = {
            "dispatch": dispatch_previous,
            "discovery_operator": recorded.get("discovery_operator"),
            "adopted": recorded.get("adopted"),
            "decision_changed": recorded.get("decision_changed"),
            "reason_if_not": recorded.get("reason_if_not"),
            "state_version": recorded.get("state_version"),
            "stale": recorded.get("state_version") != ctx["state"].get("state_version"),
        }
    switch = pc.diagnosis_switch(ctx["state"], (ctx["index"].get("competitions") or []),
                                 ctx["scheduler"], ctx["index"].get("mechanisms"))
    loop = ["Recall", "Understand", "Discover", "Predict", "Intervene", "Verify", "Revise",
            "Consolidate", "Loop"]
    steps = [
        {"step": "Recall", "command": "python3 scripts/cognition.py recall --state <state>"},
        {"step": "Understand", "command": "python3 scripts/state_check.py <state> --quiet"},
        {"step": "Discover", "command": "python3 scripts/strategy_memory.py recommend --state <state>"},
        {"step": "Predict", "command": "python3 scripts/prediction_compare.py freeze --state <state> --experiment <X>"},
        {"step": "Intervene", "command": "python3 scripts/execution_gate.py peig --state <state> --experiment <X>"},
        {"step": "Verify", "command": "python3 scripts/prediction_compare.py compare --state <state> --packet <packet> --for-transition"},
        {"step": "Revise", "command": "python3 scripts/evidence_outcome.py apply --state <state> --packet <packet> --analysis <analysis>"},
        {"step": "Consolidate", "command": "python3 scripts/cognition.py build --state <state>"},
        {"step": "Loop", "command": "python3 scripts/preset_router.py trigger --state <state>"},
    ]
    if step.get("hold"):
        status = "HOLD"
    elif step.get("blocked"):
        status = "BLOCKED"
    else:
        status = "OK"
    write_failure = None
    if dispatch.get("tampered"):
        # A tampered policy store stops policy consumption; it is not a "no policy" state.
        status = "HOLD"
        write_failure = "policy_store_tampered"
    next_action = step["action"]
    if guidance and not guidance["stale"] and guidance["dispatch"].get("action"):
        next_action = (f"{step['action']}；上一轮策略决策："
                       f"{guidance['dispatch'].get('action')}"
                       f"（算子 {guidance.get('discovery_operator')}）")

    writes = ["cognition/ 投影（经 cognition build）"]
    strategy_changed_dispatch = bool(step.get("strategy_overrode_scheduler"))
    # A policy delta exists only when a policy actually changed the dispatched action. Reporting
    # "an L2 policy was consumed" while nothing was dispatched (or while the decision came from
    # strategy memory rather than a scoped policy) is a false Delta.
    policy_delta: Dict[str, Any] = {"status": "none", "level": None, "policy_id": None,
                                    "scope": None}
    if dispatch["applied"] and strategy_changed_dispatch and step.get("dispatched_action"):
        policy_delta = {"status": "applied", "level": dispatch.get("level") or "L2",
                        "policy_id": dispatch.get("policy_id"),
                        "scope": (dispatch.get("advice") or {}).get("scope")}
    if apply and dispatch["applied"] and step.get("dispatched_action"):
        import decision_trajectory as dt
        state = ctx["state"]
        trajectory = ctx["route_dir"] / dt.TRAJECTORY_NAME
        try:
            context = dt.record_context(state, state_path=ctx["state_path"],
                                        scheduler=ctx["scheduler"])
            record = dt.build_decision_record(
                state, route=cg.route_of(ctx["state_path"]), project=ctx["route_dir"].name,
                context=context,
                candidates=[{"action": item.get("action"), "type": item.get("type"),
                             "target": item.get("target"), "eig": item.get("eig"),
                             "cost": item.get("cost")}
                            for item in (ctx["scheduler"] or {}).get("next_actions") or []
                            if isinstance(item, dict)],
                chosen=step["dispatched_action"],
                scheduler_priority={"level": 4, "label": "high_information_gain_test"},
                policy_version=dispatch.get("policy_id") or "strategy-memory",
                policy_changed_order=strategy_changed_dispatch,
                dispatch_status="dispatched")
            outcome = dt.append_record(trajectory, record, state=state,
                                       route=cg.route_of(ctx["state_path"]))
            if outcome["status"] in ("APPENDED", "DUPLICATE"):
                writes.append(dt.TRAJECTORY_NAME)
            else:
                # An INVALID trajectory write is a real failure, not a silent no-op.
                write_failure = "decision_trajectory_rejected"
        except (dt.TrajectoryError, OSError) as exc:
            # A damaged trajectory store must produce a diagnosable HOLD, not a traceback.
            write_failure = f"decision_trajectory_unreadable: {type(exc).__name__}"
        if write_failure is None and ctx["scheduler"] and dispatch.get("decision"):
            try:
                updated = sm.record_strategy_decision(
                    ctx["scheduler"], dispatch["decision"],
                    dispatch_result=f"dispatched {step['dispatched_action']}")
                (ctx["route_dir"] / cg.SCHEDULER_NAME).write_text(
                    json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                writes.append(cg.SCHEDULER_NAME)
            except OSError as exc:
                write_failure = f"scheduler_telemetry_unwritable: {type(exc).__name__}"
    if write_failure:
        status = "HOLD"
        policy_delta = {"status": "none", "level": None, "policy_id": None, "scope": None}

    return _result(preset, status, observed={"loop": loop, "current": step,
                                             "switch_action": switch.get("action"),
                                             "strategy_guidance": guidance,
                                             "scoped_policy": {
                                                 "policy_id": dispatch.get("policy_id"),
                                                 "applied": dispatch.get("applied"),
                                                 "conditions_ok": dispatch.get("conditions_ok"),
                                                 "unmet_conditions": dispatch.get("unmet"),
                                                 "source": dispatch.get("source"),
                                                 "tampered": dispatch.get("tampered"),
                                                 "diagnostics": dispatch.get("diagnostics"),
                                                 "write_failure": write_failure,
                                                 "dispatched_action": step.get("dispatched_action"),
                                                 "strategy_overrode_scheduler":
                                                     strategy_changed_dispatch},
                                             "assurance": step.get("assurance"),
                                             "assurance_pending": step.get("assurance_pending")},
                   decision={"next_action": next_action,
                             "consumes_previous_decision": bool(guidance and not guidance["stale"]),
                             "step": step["step"],
                             "dispatched_action": step.get("dispatched_action"),
                             "strategy_changed_dispatch": strategy_changed_dispatch,
                             "scientific_delta": "none",
                             "decision_delta": ("decision" if strategy_changed_dispatch
                                                or switch.get("action") != "CONTINUE_ATTRIBUTION"
                                                else "none"),
                             "policy_delta": policy_delta,
                             "pending_r10": step.get("pending_r10"),
                             "blocked_experiments": step.get("blocked_experiments"),
                             "decision_gate": step.get("decision_gate"),
                             "assurance_pending": step.get("assurance_pending"),
                             "assurance_dependent": step.get("assurance_dependent"),
                             "assurance_paths": step.get("assurance_paths"),
                             "stop_reason": write_failure or step.get("hold_reason")
                             or (None if not step["blocked"] else "contract missing")},
                   steps=steps, writes=writes,
                   changed_decision=switch.get("action") != "CONTINUE_ATTRIBUTION"
                   or strategy_changed_dispatch,
                   next_action=next_action,
                   hold_reason=write_failure or step.get("hold_reason"))


REPRESENTATION_AXES: Tuple[str, ...] = ("object", "variable", "assumption", "objective",
                                        "constraint")


def _current_representation(ctx: Dict[str, Any]) -> Dict[str, Any]:
    state = ctx["state"]
    claim = next((item for item in state.get("claims") or [] if isinstance(item, dict)), {})
    contract = claim.get("contract") if isinstance(claim.get("contract"), dict) else {}
    mechanism = next((item for item in ctx["index"].get("mechanisms") or []
                      if isinstance(item, dict)), {})
    structure = mechanism.get("structure") or {}
    return {
        "object": contract.get("statement") or claim.get("statement") or "",
        "variable": "; ".join(str(item) for item in structure.get("core_variables") or []) or
                    str(contract.get("scope") or ""),
        "assumption": "; ".join(str(item) for item in structure.get("necessary_conditions") or []) or
                      "; ".join(str(item) for item in contract.get("critical_assumptions") or []),
        "objective": str(contract.get("statement") or ""),
        "constraint": str(claim.get("scope") or ""),
        "signature": cg.digest_of({"statement": contract.get("statement") or claim.get("statement"),
                                   "scope": claim.get("scope"),
                                   "hypotheses": [item.get("id") for item in
                                                  state.get("hypotheses") or []
                                                  if isinstance(item, dict)]}),
    }


def _handle_paradigm_escape(ctx: Dict[str, Any], apply: bool) -> Dict[str, Any]:
    """Representation Reset: five axes, grounded in this project's canonical material.

    The handler does not invent a new theory and it does not pretend to: it freezes the current
    representation, derives a *candidate* reset per axis from the project's own objects
    (competing framing, unmodelled unknowns, tacit assumptions, the recommended structural
    axis, the frozen constraints), and states the two conditions under which the reset counts —
    a mechanically checkable structural difference and a discriminating prediction. Whether the
    new formulation is real novelty is decided by the structural-equivalence audit, never here.
    """
    preset = presets_by_id()["paradigm-escape"]
    before = _current_representation(ctx)
    state = ctx["state"]
    claim = next((item for item in state.get("claims") or [] if isinstance(item, dict)), {})
    contract = claim.get("contract") if isinstance(claim.get("contract"), dict) else {}
    mechanism = next((item for item in ctx["index"].get("mechanisms") or []
                      if isinstance(item, dict)), {})
    structure = mechanism.get("structure") or {}
    recommendation = _recommend(ctx)
    unknowns = [item for item in state.get("uncertainties") or []
                if isinstance(item, dict) and item.get("status") == "open"]
    assumptions = [ident for ident in contract.get("critical_assumptions") or []]
    resources = (state.get("contract") or {}).get("constraints") or []

    variable_source = ("；".join(str(item) for item in structure.get("core_variables") or [])
                       or str(claim.get("scope") or "当前指标"))
    unknown_question = (unknowns[0].get("question") if unknowns else None)
    after = {
        "object": (f"把「{contract.get('statement') or claim.get('statement')}」的竞争框架 "
                   f"`{claim.get('nearest_alternative')}` 提升为一等对象，"
                   "两个框架下的观测量分别声明"
                   if claim.get("nearest_alternative") else
                   "把「现象」改为「在给定观测算子下的条件可识别性对象」"),
        "variable": (f"把 {variable_source} 换成未建模的不确定量"
                     + (f"（`{unknown_question}`）" if unknown_question else "")
                     + "：从结果变量改为可识别性变量（零空间投影 / 条件数）"),
        "assumption": (f"撤销 tacit 假设 {assumptions or '（未登记）'}，"
                       "改为显式可检验条件并登记 falsifier"
                       if assumptions else
                       "先登记当前建模所依赖的 tacit 假设（`assumptions[]`），再逐条改为可检验条件"),
        "objective": (f"按推荐的结构轴 `{recommendation.get('shift')}` 重构目标："
                      f"从「{contract.get('statement') or '解释现象'}」"
                      "改为在该轴上的可判别目标"),
        "constraint": (f"在 {resources or ['现有资源']} 与冻结范围 "
                       f"`{claim.get('scope')}` 不变的前提下比较新旧表示"),
    }
    axes_changed = [axis for axis in REPRESENTATION_AXES if before.get(axis) != after.get(axis)]
    structurally_new = cg.digest_of(after) != cg.digest_of(
        {axis: before.get(axis) for axis in REPRESENTATION_AXES})
    islands = sorted({str(item.get("island")) for item in state.get("hypotheses") or []
                      if isinstance(item, dict)})
    steps = [
        {"step": "1 冻结现状表示", "command": "python3 scripts/cognition.py brief --state <state>"},
        {"step": "2 逐轴替换", "command": "编辑候选 H：object/variable/assumption/objective/constraint"},
        {"step": "3 结构差异核验",
         "command": "python3 scripts/structural_equivalence_check.py check --route <route>"},
        {"step": "4 判别实验",
         "command": "python3 scripts/prediction_compare.py freeze --state <state> --experiment <X>"},
        {"step": "5 计算下一动作",
         "command": "python3 scripts/strategy_memory.py recommend --state <state>"},
    ]
    status = "OK" if len(axes_changed) >= 2 and structurally_new else "HOLD"
    return _result(preset, status,
                   observed={"representation_before": before,
                             "representation_after": after,
                             "axes_changed": axes_changed,
                             "current_islands": islands,
                             "grounded_in": {"claim": claim.get("id"), "mechanism": mechanism.get("id"),
                                             "unknowns": [item.get("id") for item in unknowns],
                                             "assumptions": assumptions}},
                   decision={"requires_structural_audit": True,
                             "discriminating_test": "TBD（必须在 R8 冻结前给出）",
                             "candidate_is_a_scaffold": True,
                             "note": "语料来自本项目 canonical 对象；新表示是否构成真实 novelty "
                                     "只能由 SENA 结构等价审计判定，参数/模块替换不算范式改变"},
                   steps=steps, writes=["hypotheses[]（只经 R3—R6）"],
                   changed_decision=bool(axes_changed),
                   next_action="按 5 个面重建模并提交结构等价审计",
                   hold_reason=None if status == "OK" else "not_actionable")


def _handle_research_recovery(ctx: Dict[str, Any], apply: bool) -> Dict[str, Any]:
    preset = presets_by_id()["research-recovery"]
    import legacy_handoff as lh
    detect = lh.detect(ctx["state_path"])
    audit = lh.compatibility_audit(ctx["state_path"], None)
    constraints = cg.failure_constraints(ctx["state"])
    obligations = cg.open_obligations(ctx["state"])
    in_flight = [{"id": item.get("id"), "status": item.get("status"),
                  "stage": item.get("stage")}
                 for item in ctx["state"].get("experiments") or []
                 if isinstance(item, dict) and item.get("status") in ("planned", "running")]
    blockers = [{"rule": finding.rule, "path": finding.path, "severity": finding.severity}
                for finding in audit["findings"] if finding.severity == lh.BLOCKING]
    writes: List[str] = []
    rebuilt = False
    if apply and not blockers:
        before = ctx["canonical_digest"]
        cg.op_build(ctx["state_path"], ctx["cognition_dir"])
        rebuilt = cg.digest_of(cg.load_state(ctx["state_path"])) == before
        writes.append("cognition/index.json")
        writes.append("cognition/context-brief.md")
    steps = [
        {"step": "1 磁盘重载", "command": f"python3 scripts/legacy_handoff.py detect --state {ctx['state_path']}"},
        {"step": "2 只读兼容性审计", "command": f"python3 scripts/legacy_handoff.py audit --state {ctx['state_path']}"},
        {"step": "3 重建认知投影", "command": f"python3 scripts/cognition.py build --state {ctx['state_path']}"},
        {"step": "4 恢复理解", "command": f"python3 scripts/cognition.py brief --state {ctx['state_path']}"},
        {"step": "5 复用失败约束", "command": f"python3 scripts/cognition.py recall --state {ctx['state_path']}"},
    ]
    status = "BLOCKED" if blockers else "OK"
    return _result(preset, status,
                   observed={"bootstrap_forbidden": detect.get("bootstrap_forbidden"),
                             "recovered": {"mechanisms": ctx["index"].get("counts", {}).get("mechanisms"),
                                           "competitions": ctx["index"].get("counts", {}).get("competitions"),
                                           "anomalies": ctx["index"].get("counts", {}).get("anomalies")},
                             "forbidden_repeats": constraints,
                             "open_obligations": obligations,
                             "in_flight": in_flight, "blockers": blockers,
                             "rebuilt": rebuilt,
                             "canonical_untouched": rebuilt or not apply},
                   decision={"next_action": _loop_step(ctx)["action"]},
                   steps=steps, writes=writes,
                   changed_decision=None, next_action=_loop_step(ctx)["action"],
                   hold_reason="awaiting_human_decision" if blockers else None)


def _handle_scientific_replanning(ctx: Dict[str, Any], apply: bool) -> Dict[str, Any]:
    preset = presets_by_id()["scientific-replanning"]
    decision = sm.strategy_decision(ctx["state"], ctx["index"], ctx["scheduler"],
                                    ctx["revisions"])
    before = _recommend(ctx)
    refuted = [item.get("id") for item in ctx["state"].get("claims") or []
               if isinstance(item, dict) and item.get("status") in ("contradicted", "killed")]
    sci = failure_classification(ctx["state"])["scientific"]
    updates = _strategy_updates(ctx["state"], ctx["index"], ctx["scheduler"], ctx["revisions"])
    after = _recommend(ctx, list(ctx["revisions"]) + updates) if updates else before
    changed = _rec_key(before) != _rec_key(after)
    writes: List[str] = []
    if apply and updates:
        appended = _append_strategy_revisions(ctx, updates)
        if appended["written"]:
            writes.append("cognition/model-revisions.jsonl")
    status = "OK" if (refuted or sci or changed) else "HOLD"
    steps = [
        {"step": "1 汇总否证", "command": "python3 scripts/state_check.py <state> --quiet"},
        {"step": "2 停手约束", "command": "python3 scripts/evidence_outcome.py constraints --state <state>"},
        {"step": "3 重排下一步", "command": "python3 scripts/strategy_memory.py recommend --state <state>"},
        {"step": "4 必要时改状态", "command": "python3 scripts/evidence_outcome.py apply --state <state> ..."},
    ]
    return _result(preset, status,
                   observed={"refuted_targets": refuted, "scientific_failures": sci,
                             "plan_before": decision.get("chosen_without_memory"),
                             "plan_after": decision.get("chosen"),
                             "reason_if_not": decision.get("reason_if_not")},
                   decision={"next_action": decision.get("chosen") or after.get("menu"),
                             "replan_basis": "否证 + 停滞 + 约束（不重写既有证据）"},
                   steps=steps, writes=writes, changed_decision=changed,
                   next_action=after.get("menu"),
                   hold_reason=None if status == "OK" else "no_intent_matched")


def _revision_identity(record: Dict[str, Any]) -> str:
    """Event identity of a strategy revision: kind + subject + state version + payload digest."""
    return cg.digest_of({"kind": record.get("kind"), "subject": record.get("subject"),
                         "at_state_version": record.get("at_state_version"),
                         "after": record.get("after")})


def _strategy_revision_records(ctx: Dict[str, Any],
                               updates: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The exact records that would be appended (no I/O, so they can be validated first)."""
    existing = list(ctx["revisions"])
    next_seq = max([item.get("seq", 0) for item in existing] + [0]) + 1
    records: List[Dict[str, Any]] = []
    for offset, update in enumerate(updates):
        records.append({
            "_schema": cg.SCHEMA_REVISION, "id": f"REV{next_seq + offset}",
            "seq": next_seq + offset, "kind": update.get("kind", "strategy_update"),
            "subject": update.get("subject"),
            # `SV6`: the Meta-Controller commits; R14 only proposes. Recording "R14" here made
            # every written strategy update fail its own validator.
            "actor": cg.STRATEGY_UPDATE_ACTOR,
            "at_state_version": ctx["state"].get("state_version"),
            "summary": update.get("summary"),
            "trigger": {"kind": "strategy_update", "ref": update.get("subject")},
            # `CM1` only accepts the canonical payload keys; the projection keeps the structured
            # scope/reactivation/telemetry under `priors` instead of writing unknown fields.
            "refs": update.get("refs") or cg.EMPTY_REFS,
            "after": sm.revision_payload(update),
        })
    return records


def _append_strategy_revisions(ctx: Dict[str, Any],
                               updates: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate the whole set, then append it atomically. Nothing is written when any record is
    invalid, so a rejected revision can never pollute the append-only strategy memory."""
    if not updates:
        return {"written": 0, "diagnostics": [], "records": []}
    records = _strategy_revision_records(ctx, updates)
    diagnostics = sm.validate_strategy_revisions(ctx["state"], records)
    if diagnostics:
        return {"written": 0, "diagnostics": [item.render() for item in diagnostics],
                "records": [], "skipped": 0}
    # Idempotency by event identity: re-running the same preset on the same state version must not
    # append a duplicate record for an event the log already holds.
    seen = {_revision_identity(record) for record in ctx["revisions"]}
    fresh = [record for record in records if _revision_identity(record) not in seen]
    skipped = len(records) - len(fresh)
    if not fresh:
        return {"written": 0, "diagnostics": [], "records": [], "skipped": skipped}
    path = ctx["cognition_dir"] / cg.REVISIONS_NAME
    payload = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in fresh)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload)
    return {"written": len(fresh), "diagnostics": [], "records": fresh, "skipped": skipped}


def _handle_research_audit(ctx: Dict[str, Any], apply: bool) -> Dict[str, Any]:
    preset = presets_by_id()["research-audit"]
    report = sc.check_state(ctx["state"], source=str(ctx["state_path"]))
    findings = [{"rule": item.rule, "path": item.path, "detail": item.detail}
                for item in (report.all_violations() if not report.ok else [])]
    competitions = ctx["index"].get("competitions") or []
    for competition in competitions:
        verdict, _ = pc.distinguishability(ctx["state"], competition,
                                           ctx["index"].get("mechanisms"))
        if not verdict.get("has_distinguishing_power"):
            findings.append({"rule": "PR5", "path": f"competitions[{competition.get('id')}]",
                             "detail": f"竞争缺乏区分力：{verdict.get('reason')}"})
    for card in ctx["cards"]:
        for diagnostic in pc.insight_card_errors(card, ctx["state"], ctx["audits"]):
            findings.append({"rule": diagnostic.rule, "path": diagnostic.path,
                             "detail": diagnostic.detail})
    import execution_gate as eg
    for experiment in ctx["state"].get("experiments") or []:
        if isinstance(experiment, dict) and experiment.get("status") in ("planned", "running"):
            gate = eg.peig(ctx["state"], experiment.get("id"))
            if gate.get("status") != "PASS":
                findings.append({"rule": "PR6", "path": f"experiments[{experiment.get('id')}]",
                                 "detail": f"执行前识别性门禁未通过：{gate.get('errors') or gate.get('status')}"})
    severity = "high" if any(item["rule"] in ("V1", "V2", "V3", "V19", "V20") for item in findings) \
        else ("medium" if findings else "none")
    # Decision: a plain "audit" never touches the canonical state. Persisting an attack into
    # `assurance[]` is an explicit, separate step through R7; `--apply` only *proposes* it here
    # (the write itself belongs to R7, so this preset stays read-only).
    proposal = [{"target": item["path"], "kill_condition": item["detail"],
                 "discriminating_test": "TBD", "verification_tier": "T0"}
                for item in findings[:5]] if apply else []
    writes: List[str] = []
    steps = [
        {"step": "1 canonical 校验", "command": f"python3 scripts/state_check.py {ctx['state_path']}"},
        {"step": "2 结构等价审计", "command": "python3 scripts/structural_equivalence_check.py check --route <route>"},
        {"step": "3 判别力审查", "command": "python3 scripts/prediction_compare.py compete --state <state> --competition <CP>"},
        {"step": "4 执行门禁", "command": "python3 scripts/execution_gate.py peig --state <state> --experiment <X>"},
    ]
    return _result(preset, "OK",
                   observed={"findings": findings, "counts": {"total": len(findings)},
                             "severity": severity},
                   decision={"read_only": not apply,
                             "discovery_started": False,
                             "kill_conditions": [item["detail"] for item in findings[:3]],
                             "assurance_proposal": proposal,
                             "writeback_flow": "R7（仅显式请求时）" if apply else None,
                             "note": "普通审查默认只读；写 assurance[] 必须显式经 R7 写回流程，"
                                     "不得因用户只说「审查」而隐式改 canonical"},
                   steps=steps, writes=writes, changed_decision=None,
                   next_action=("把 assurance_proposal 交给 R7 写回" if proposal
                                else "把 findings 交给 R7 落 assurance[]（本预设不执行 Discovery）"))


def _handle_research_review(ctx: Dict[str, Any], apply: bool) -> Dict[str, Any]:
    preset = presets_by_id()["research-review"]
    state = ctx["state"]
    counts = ctx["index"].get("counts") or {}
    supported = [{"id": item.get("id"), "statement": item.get("statement"),
                  "evidence": item.get("supporting_evidence")}
                 for item in state.get("claims") or []
                 if isinstance(item, dict) and item.get("status") in ("supported",
                                                                     "partially-supported")]
    unknowns = [{"id": item.get("id"), "question": item.get("question"),
                 "importance": item.get("importance")}
                for item in state.get("uncertainties") or []
                if isinstance(item, dict) and item.get("status") == "open"]
    recommendation = _recommend(ctx)
    return _result(preset, "OK",
                   observed={"established": supported, "unknowns": unknowns,
                             "counts": counts,
                             "open_obligations": cg.open_obligations(state),
                             "forbidden_repeats": cg.failure_constraints(state)},
                   decision={"next_decisions": [
                       {"option": recommendation.get("menu"),
                        "operator": recommendation.get("operator"),
                        "reason": recommendation.get("reason")}],
                       "read_only": True},
                   steps=[{"step": "1 只读状态快照", "command":
                           f"python3 scripts/state_check.py {ctx['state_path']} --quiet"},
                          {"step": "2 认知 brief", "command":
                           f"python3 scripts/cognition.py brief --state {ctx['state_path']}"},
                          {"step": "3 价值判断", "command":
                           "python3 scripts/strategy_memory.py value --state <state>"}],
                   writes=[], changed_decision=None,
                   next_action="由用户选择下一决策；本预设不执行")


def _handle_context_drift_recovery(ctx: Dict[str, Any], apply: bool) -> Dict[str, Any]:
    preset = presets_by_id()["context-drift-recovery"]
    signals = signal_snapshot(ctx["state"], scheduler=ctx["scheduler"], index=ctx["index"],
                              revisions=ctx["revisions"])
    reasons = signals["context_drift"]["reasons"] + signals["memory_drift"]["reasons"]
    writes: List[str] = []
    fixed = False
    if apply and reasons:
        before = ctx["canonical_digest"]
        cg.op_build(ctx["state_path"], ctx["cognition_dir"])
        fixed = cg.digest_of(cg.load_state(ctx["state_path"])) == before
        writes.extend(["cognition/index.json", "cognition/context-brief.md"])
    status = "OK" if reasons else "NO_CHANGE"
    if reasons and not apply:
        status = "OK"
    return _result(preset, status,
                   observed={"drift_reasons": reasons, "rebuilt": fixed,
                             "canonical_untouched": fixed or not apply,
                             "source": "disk（不使用聊天历史作为事实来源）"},
                   decision={"next_action": "重建投影后从 context-brief 继续"},
                   steps=[{"step": "1 检测漂移", "command":
                           "python3 scripts/preset_router.py trigger --state <state>"},
                          {"step": "2 重建投影", "command":
                           f"python3 scripts/cognition.py build --state {ctx['state_path']}"},
                          {"step": "3 校验一致", "command":
                           f"python3 scripts/cognition.py check --state {ctx['state_path']}"}],
                   writes=writes, changed_decision=None,
                   next_action="从磁盘恢复的上下文继续" if reasons else "无需恢复",
                   hold_reason=None)


def _handle_stagnation_breaker(ctx: Dict[str, Any], apply: bool) -> Dict[str, Any]:
    preset = presets_by_id()["stagnation-breaker"]
    signals = signal_snapshot(ctx["state"], scheduler=ctx["scheduler"], index=ctx["index"],
                              revisions=ctx["revisions"])
    stagnation = signals["stagnation"]
    if not stagnation["detected"]:
        return _result(preset, "NO_CHANGE",
                       observed={"stagnation": stagnation,
                                 "scientific_failures": signals["scientific_failure"]},
                       decision={"next_action": "继续归因（尚未构成停滞）"},
                       next_action="继续归因", changed_decision=False,
                       steps=[{"step": "1 停滞检测", "command":
                               "python3 scripts/prediction_compare.py switch --state <state>"}])
    switch = stagnation["switch"]
    action = switch.get("action")
    return _result(preset, "OK",
                   observed={"zero_streak": stagnation["zero_streak"],
                             "reasons": stagnation["reasons"],
                             "witness": switch.get("competition_verdicts") or switch.get("basis")},
                   decision={"switch_action": action,
                             "next_intervention": switch.get("note"),
                             "single_negative_is_not_stagnation": True},
                   steps=[{"step": "1 行为切换", "command":
                           "python3 scripts/prediction_compare.py switch --state <state>"},
                          {"step": "2 设计判别干预", "command":
                           "python3 scripts/prediction_compare.py compete --state <state> --competition <CP>"},
                          {"step": "3 停手或重定义", "command":
                           "python3 scripts/prediction_compare.py switch --state <state> --scheduler <scheduler>"}],
                   writes=[], changed_decision=action != "CONTINUE_ATTRIBUTION",
                   next_action=action)


def _handle_experiment_failure_recovery(ctx: Dict[str, Any], apply: bool) -> Dict[str, Any]:
    preset = presets_by_id()["experiment-failure-recovery"]
    classification = failure_classification(ctx["state"])
    failed = terminal_failed_experiments(ctx["state"])
    if not classification["engineering"] and not failed:
        return _result(preset, "NO_CHANGE",
                       observed={"failure_class": "none",
                                 "scientific_failures": classification["scientific"]},
                       decision={"next_action": "无工程故障"},
                       next_action="无需恢复", changed_decision=False)
    kinds = classification["engineering"]
    repair_plan: List[Dict[str, Any]] = []
    for experiment in failed:
        repair_plan.append({
            "experiment": experiment.get("id"),
            "fix": f"修复工程原因（{kinds or 'implementation_failure'}）后重新走 PEIG/AALG",
            "new_receipt_required": True,
            "reuse_same_experiment_id": False,
            "reason": "失败执行没有科学含义；同一实验不得无限重启",
        })
    return _result(preset, "OK",
                   observed={"failure_class": "engineering",
                             "kinds": kinds,
                             "failed_experiments": [item.get("id") for item in failed],
                             "scientific_effect": "none"},
                   decision={"repair_plan": repair_plan,
                             "rerun_authorized": False,
                             "note": "本预设分类并给出修复路径，不授权执行；重跑必须经 PEIG/AALG"},
                   steps=[{"step": "1 分类失败", "command":
                           "python3 scripts/evidence_outcome.py constraints --state <state>"},
                          {"step": "2 诊断执行", "command":
                           "python3 scripts/experiment_execute.py diagnose --state <state> --experiment <X>"},
                          {"step": "3 修复后重发收据", "command":
                           "python3 scripts/execution_gate.py peig --state <state> --experiment <X>"},
                          {"step": "4 执行", "command":
                           "python3 scripts/experiment_execute.py run --config <config> --state <state>"}],
                   writes=[], changed_decision=None,
                   next_action="先修工程原因，再按门禁重新授权执行")


def _handle_evidence_conflict_repair(ctx: Dict[str, Any], apply: bool) -> Dict[str, Any]:
    preset = presets_by_id()["evidence-conflict-repair"]
    signals = signal_snapshot(ctx["state"], scheduler=ctx["scheduler"], index=ctx["index"],
                              revisions=ctx["revisions"])
    conflicts = signals["evidence_conflict"]["conflicts"]
    routes = []
    for claim in ctx["state"].get("claims") or []:
        if not isinstance(claim, dict):
            continue
        if claim.get("refuting_evidence") and claim.get("status") == "supported":
            routes.append({"target": claim.get("id"), "route": "R10",
                           "reason": "存在反驳证据但状态仍为 supported"})
    status = "OK" if conflicts else "NO_CHANGE"
    return _result(preset, status,
                   observed={"conflicts": conflicts, "counts": len(conflicts),
                             "state_integrity": signals["state_integrity"]},
                   decision={"route": routes or [{"route": "R10/R11", "reason": "见 conflicts"}],
                             "canonical_untouched": True,
                             "gate": "所有状态迁移必须经统一证据资格门（qualify_evidence）"},
                   steps=[{"step": "1 定位冲突", "command":
                           f"python3 scripts/state_check.py {ctx['state_path']}"},
                          {"step": "2 判定迁移路径", "command":
                           "python3 scripts/evidence_outcome.py check-plan --state <state> --experiment <X>"},
                          {"step": "3 重放收缩", "command":
                           "python3 scripts/evidence_outcome.py decision --state <state> --experiment <X>"},
                          {"step": "4 应用迁移", "command":
                           "python3 scripts/evidence_outcome.py apply --state <state> ..."}],
                   writes=[], changed_decision=None,
                   next_action="按 R10/R11 修复（需要授权时 HOLD 交人裁决）",
                   hold_reason=None if conflicts else "no_signal")


def _handle_resource_recovery(ctx: Dict[str, Any], apply: bool) -> Dict[str, Any]:
    preset = presets_by_id()["resource-recovery"]
    import shutil as _shutil
    signals = signal_snapshot(ctx["state"], scheduler=ctx["scheduler"], index=ctx["index"],
                              revisions=ctx["revisions"])
    resource = signals["resource_blocked"]
    policy_path = ctx["route_dir"] / ".execution" / "policy.json"
    budget = None
    if policy_path.is_file():
        try:
            budget = json.loads(policy_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            budget = {"unreadable": True}
    environment = {
        "nvidia_smi": _shutil.which("nvidia-smi") is not None,
        "python": sys.version.split()[0],
        "execution_ledger": policy_path.is_file(),
    }
    checklist = []
    if resource["detected"]:
        checklist.append({"issue": "资源/环境类失败线索：" + "、".join(resource["tokens"]),
                          "action": "核对机器与依赖后再重发执行收据（不得直接重启）"})
    if not environment["nvidia_smi"]:
        checklist.append({"issue": "未检测到 GPU 工具", "action": "确认目标机器或改用 CPU 小规模验证"})
    status = "OK" if checklist else "NO_CHANGE"
    return _result(preset, status,
                   observed={"tokens": resource["tokens"], "text_based": True,
                             "contract_resources": resource.get("budget"),
                             "execution_policy": budget, "environment": environment},
                   decision={"repair_checklist": checklist, "starts_jobs": False,
                             "note": "资源失败不构成科学结论；预算策略文件只读"},
                   steps=[{"step": "1 环境探测", "command": "python3 scripts/env_probe.py"},
                          {"step": "2 执行账本", "command":
                           "python3 scripts/experiment_execute.py scheduler-check --state <state>"},
                          {"step": "3 修复后恢复", "command":
                           "python3 scripts/execution_gate.py peig --state <state> --experiment <X>"}],
                   writes=[], changed_decision=None,
                   next_action="按清单修复环境；本预设不启动作业",
                   hold_reason=None if status == "OK" else "no_signal")


def _handle_memory_consolidation(ctx: Dict[str, Any], apply: bool) -> Dict[str, Any]:
    preset = presets_by_id()["memory-consolidation"]
    signals = signal_snapshot(ctx["state"], scheduler=ctx["scheduler"], index=ctx["index"],
                              revisions=ctx["revisions"])
    reasons = signals["memory_drift"]["reasons"]
    writes: List[str] = []
    rebuilt = False
    if apply:
        before = ctx["canonical_digest"]
        cg.op_build(ctx["state_path"], ctx["cognition_dir"])
        rebuilt = cg.digest_of(cg.load_state(ctx["state_path"])) == before
        writes.extend(["cognition/index.json", "cognition/context-brief.md"])
    stale = [item.get("id") for item in ctx["index"].get("mechanisms") or []
             if isinstance(item, dict) and item.get("stale")]
    refuted = [item.get("id") for item in ctx["index"].get("mechanisms") or []
               if isinstance(item, dict) and item.get("status") == "refuted"]
    return _result(preset, "OK" if (reasons or apply) else "NO_CHANGE",
                   observed={"drift_reasons": reasons, "rebuilt": rebuilt,
                             "stale_mechanisms": stale, "refuted_mechanisms": refuted},
                   decision={"canonical_untouched": rebuilt or not apply,
                             "note": "投影只由 canonical 事实重建；不得用投影覆盖 state"},
                   steps=[{"step": "1 重建", "command":
                           f"python3 scripts/cognition.py build --state {ctx['state_path']}"},
                          {"step": "2 校验", "command":
                           f"python3 scripts/cognition.py check --state {ctx['state_path']}"},
                          {"step": "3 失效传播", "command":
                           "python3 scripts/state_check.py <state> --quiet"}],
                   writes=writes, changed_decision=None,
                   next_action="重建后继续（投影不是科学事实）")


def _handle_loop_health_check(ctx: Dict[str, Any], apply: bool) -> Dict[str, Any]:
    preset = presets_by_id()["loop-health-check"]
    signals = signal_snapshot(ctx["state"], scheduler=ctx["scheduler"], index=ctx["index"],
                              revisions=ctx["revisions"])
    decision = trigger(ctx["state"], index=ctx["index"], scheduler=ctx["scheduler"],
                       revisions=ctx["revisions"], records=ctx["records"])
    unhealthy = [key for key, value in signals.items()
                 if not key.startswith("_") and isinstance(value, dict)
                 and (value.get("detected") or (key == "state_integrity" and not value.get("ok")))]
    verdict = "AT_RISK" if unhealthy else "HEALTHY"
    return _result(preset, "OK",
                   observed={"signals": {key: value for key, value in signals.items()
                                         if not key.startswith("_")},
                             "unhealthy": unhealthy},
                   decision={"verdict": verdict,
                             "recommended_preset": (decision.get("selected") or {}).get("preset_id"),
                             "trigger_action": decision.get("action"),
                             "hold_reason": decision.get("hold_reason"),
                             "read_only": True},
                   steps=[{"step": "1 采集信号", "command":
                           "python3 scripts/preset_router.py trigger --state <state>"},
                          {"step": "2 回放对照", "command":
                           "python3 scripts/research_replay.py suite --dir examples/replay/adversarial --runs 1"}],
                   writes=[], changed_decision=None,
                   next_action="按 recommended_preset 处理（需用户或 Loop 授权）",
                   hold_reason=decision.get("hold_reason"))


def _handle_strategy_evolution(ctx: Dict[str, Any], apply: bool) -> Dict[str, Any]:
    """Advice → decision → dispatch, using the Strategy Decision Adapter.

    `changed_decision` is the adapter's own verdict about the *action selection*, not a claim
    about research capability: the adapter may only reorder inside the best `EIG ÷ cost` tier
    and only among actions that already pass the hard gates. When it cannot change anything it
    says why, and the preset reports `NO_CHANGE`.
    """
    preset = presets_by_id()["strategy-evolution"]
    decision = sm.strategy_decision(ctx["state"], ctx["index"], ctx["scheduler"],
                                    ctx["revisions"])
    changes = sm.strategy_updates(ctx["state"], ctx["index"], ctx["scheduler"])
    updates = changes.get("updates") if isinstance(changes, dict) else []
    updates = [item for item in updates or [] if isinstance(item, dict)]
    writes: List[str] = []
    applied_revisions = 0
    revision_diagnostics: List[str] = []
    revisions_skipped = 0
    if apply:
        if updates:
            appended = _append_strategy_revisions(ctx, updates)
            applied_revisions = appended["written"]
            revision_diagnostics = appended["diagnostics"]
            revisions_skipped = appended.get("skipped", 0)
            writes.append("cognition/model-revisions.jsonl")
        if ctx["scheduler"]:
            recorded = decision
            if applied_revisions:
                ctx["revisions"] = list(ctx["revisions"]) + updates
                recorded = sm.strategy_decision(ctx["state"], ctx["index"], ctx["scheduler"],
                                                ctx["revisions"])
            updated = sm.record_strategy_decision(ctx["scheduler"], recorded)
            path = ctx["route_dir"] / cg.SCHEDULER_NAME
            path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
            writes.append(cg.SCHEDULER_NAME)
            decision = recorded
    changed = bool(decision.get("decision_changed"))
    status = "OK" if changed else "NO_CHANGE"
    steps = [
        {"step": "1 历史校准", "command": "python3 scripts/strategy_memory.py operators --state <state>"},
        {"step": "2 生成修订", "command": "python3 scripts/strategy_memory.py apply --state <state>"},
        {"step": "3 决策适配（同层重排）", "command":
         "python3 scripts/strategy_memory.py decide --state <state> --scheduler <scheduler>"},
        {"step": "4 写入调度遥测", "command":
         "python3 scripts/strategy_memory.py decide --state <state> --scheduler <scheduler> --record"},
        {"step": "5 回放验证", "command":
         "python3 scripts/preset_router.py run --preset discovery-replay --state <state>"},
    ]
    return _result(preset, status,
                   observed={"pending_updates": len(updates),
                             "applied_revisions": applied_revisions,
                             "revision_diagnostics": revision_diagnostics,
                             "revisions_skipped": revisions_skipped,
                             "advice": decision.get("advice"),
                             "candidates_before": decision.get("candidates_before"),
                             "candidates_after": decision.get("candidates_after"),
                             "chosen_without_memory": decision.get("chosen_without_memory"),
                             "chosen": decision.get("chosen"),
                             "hard_gates": decision.get("hard_gates")},
                   decision={"changed_decision": changed,
                             "strategy_applied": decision.get("strategy_applied"),
                             "reason_if_not": decision.get("reason_if_not"),
                             "dispatch": decision.get("dispatch"),
                             "log_without_behaviour_change_counts": False,
                             "adoption_is_not_capability": True,
                             "note": "被采纳 ≠ 研究能力提升；真实收益由 Discovery Replay "
                                     "与科学结果验证"},
                   steps=steps, writes=writes, changed_decision=changed,
                   next_action=(decision.get("dispatch") or {}).get("action")
                   or "无合法动作可重排（HOLD）",
                   hold_reason=None if changed else "not_actionable")


def _handle_hypothesis_rebalance(ctx: Dict[str, Any], apply: bool) -> Dict[str, Any]:
    preset = presets_by_id()["hypothesis-rebalance"]
    before = _portfolio_concentration(ctx["state"])
    decision = sm.strategy_decision(ctx["state"], ctx["index"], ctx["scheduler"],
                                    ctx["revisions"])
    updates = _strategy_updates(ctx["state"], ctx["index"], ctx["scheduler"], ctx["revisions"])
    menus_before = [c.get("action") for c in decision.get("candidates_before") or []]
    menus_after = [c.get("action") for c in decision.get("candidates_after") or []]
    changed = bool(decision.get("decision_changed"))
    writes: List[str] = []
    if apply and updates and changed:
        appended = _append_strategy_revisions(ctx, updates)
        if appended["written"]:
            writes.append("cognition/model-revisions.jsonl")
    status = "OK" if (before["converged"] or changed) else "NO_CHANGE"
    return _result(preset, status,
                   observed={"concentration_before": before,
                             "order_before": menus_before, "order_after": menus_after,
                             "pending_updates": len(updates),
                             "discovery_operator": decision.get("discovery_operator"),
                             "reason_if_not": decision.get("reason_if_not")},
                   decision={"requires_new_axis": bool(before["converged"]),
                             "permanent_ban": False,
                             "note": "只调整既有岛屿/算子权重；不删除候选、不永久封禁"},
                   steps=[{"step": "1 度量集中度", "command":
                           "python3 scripts/cognition.py brief --state <state>"},
                          {"step": "2 调整菜单", "command":
                           "python3 scripts/strategy_memory.py recommend --state <state>"},
                          {"step": "3 生成新轴候选", "command":
                           "在 P5/P6/local 菜单下产出至少一个不同结构轴的候选"},
                          {"step": "4 校验", "command":
                           f"python3 scripts/state_check.py {ctx['state_path']} --quiet"}],
                   writes=writes, changed_decision=changed or before["converged"],
                   next_action="在新轴上生成候选" if before["converged"] else "维持当前组合",
                   hold_reason=None if status == "OK" else "no_signal")


def _handle_discovery_replay(ctx: Dict[str, Any], apply: bool) -> Dict[str, Any]:
    preset = presets_by_id()["discovery-replay"]
    import research_replay as rr
    cases_dir = Path(__file__).resolve().parent.parent / "examples" / "replay" / "adversarial"
    cases = rr.load_cases(cases_dir) if cases_dir.is_dir() else rr.adversarial_cases()
    report = rr.run_suite(cases, runs=1)
    arms = report.get("per_arm", {}) or {}
    dimensions = {name: {"mean": block.get("mean"),
                         "observable_cases": block.get("observable_cases"),
                         "total_cases": block.get("total_cases")}
                  for name, block in (arms.get("full_cie", {}).get("dimensions", {}) or {}).items()}
    results = [result for arm in arms.values() for result in arm.get("results") or []]
    support = {}
    for arm in arms.values():
        for name, count in (arm.get("evidence_support") or {}).items():
            support[name] = support.get(name, 0) + count
    return _result(preset, "OK",
                   observed={"sample_size": report.get("sample_size"),
                             "per_dimension": dimensions,
                             "undifferentiated_arms": report.get("undifferentiated_arms"),
                             "evidence_support": support,
                             "unobservable_decisions": report.get("unobservable_decisions"),
                             "leak_checked": bool(results) and all(
                                 result.get("leak_checked") for result in results),
                             "isolation_verified": bool(results) and all(
                                 result.get("isolation_verified", True) for result in results)},
                   decision={"limitations": report.get("limitations"),
                             "composite_score": None,
                             "note": "合成回放不是真实科研能力证据；NO_SUPPORT 分支不得用于晋升"},
                   steps=[{"step": "1 加载 case", "command":
                           "python3 scripts/research_replay.py validate --dir examples/replay/adversarial"},
                          {"step": "2 回放", "command":
                           "python3 scripts/research_replay.py suite --dir examples/replay/adversarial --runs 2"},
                          {"step": "3 消融", "command":
                           "python3 scripts/research_replay.py ablate --dir examples/replay/adversarial --runs 2"},
                          {"step": "4 RSI 消融", "command":
                           "python3 scripts/research_replay.py ablate --dir examples/replay/adversarial --rsi --runs 2"}],
                   writes=[], changed_decision=None,
                   next_action="把指标交给 strategy-evolution，不作为科学结论")


HANDLERS: Dict[str, Callable[[Dict[str, Any], bool], Dict[str, Any]]] = {
    "research-loop": _handle_research_loop,
    "paradigm-escape": _handle_paradigm_escape,
    "research-recovery": _handle_research_recovery,
    "scientific-replanning": _handle_scientific_replanning,
    "research-audit": _handle_research_audit,
    "research-review": _handle_research_review,
    "context-drift-recovery": _handle_context_drift_recovery,
    "stagnation-breaker": _handle_stagnation_breaker,
    "experiment-failure-recovery": _handle_experiment_failure_recovery,
    "evidence-conflict-repair": _handle_evidence_conflict_repair,
    "resource-recovery": _handle_resource_recovery,
    "memory-consolidation": _handle_memory_consolidation,
    "loop-health-check": _handle_loop_health_check,
    "strategy-evolution": _handle_strategy_evolution,
    "hypothesis-rebalance": _handle_hypothesis_rebalance,
    "discovery-replay": _handle_discovery_replay,
}


def inspect(preset_id: str, root: Optional[Path] = None) -> Dict[str, Any]:
    """The full machine-readable contract of one preset."""
    preset = presets_by_id().get(preset_id)
    if preset is None:
        return {"error": f"unknown preset: {preset_id}", "known": list(PRESET_IDS)}
    root = root or Path(__file__).resolve().parent.parent
    protocol_path = root / preset["protocol"]
    sections: List[str] = []
    if protocol_path.is_file():
        text = protocol_path.read_text(encoding="utf-8")
        sections = [section for section in PROTOCOL_SECTIONS if section in text]
    return {"_schema": SCHEMA_ROUTER, **preset, "protocol_path": str(protocol_path),
            "manual_path": "manual", "sections_present": sections,
            "sections_required": list(PROTOCOL_SECTIONS)}


def run_preset(
    preset_id: str,
    state_path: Path,
    cognition_dir: Optional[Path] = None,
    *,
    apply: bool = False,
) -> Tuple[Dict[str, Any], List[Diagnostic], int]:
    """Execute one preset's protocol against a real project. Returns `(payload, diagnostics, code)`."""
    preset = presets_by_id().get(preset_id)
    if preset is None:
        return ({"error": f"unknown preset: {preset_id}", "known": list(PRESET_IDS)}, [], EXIT_ERROR)
    handler = HANDLERS[preset_id]
    context = project_context(state_path, cognition_dir)
    # Skill-RSI source freeze: only a run that may write can violate the boundary, so the
    # before/after digest check runs on the applying path and is reported either way.
    integrity: Dict[str, Any] = {"status": "SKIPPED", "reason": "read-only run"}
    if apply:
        import source_freeze as sf
        freeze = sf.SourceFreeze(route_dir=context["route_dir"], context=f"preset:{preset_id}")
        freeze.__enter__()
        try:
            payload = handler(context, apply)
        finally:
            freeze.__exit__(None, None, None)
        integrity = dict(freeze.result or {})
        payload["source_integrity"] = integrity
        if integrity.get("status") != "PASS":
            payload["status"] = "HOLD"
            payload["hold_reason"] = "skill_source_modified"
    else:
        payload = handler(context, apply)
    payload["canonical_digest_before"] = context["canonical_digest"]
    payload["canonical_digest_after"] = cg.digest_of(cg.load_state(state_path))
    payload["canonical_untouched"] = (payload["canonical_digest_before"]
                                      == payload["canonical_digest_after"])
    payload["apply"] = apply
    hard = [item for item in context["diagnostics"] if not cg.is_warning(item.rule)]
    if integrity.get("status") not in (None, "PASS", "SKIPPED"):
        hard.append(Diagnostic("SRC1", "skill-source",
                               "运行期间 Skill 源码被修改：立即 HOLD，记录审计事件，"
                               "停止继续应用策略；不自动修订源码"))
    payload["diagnostics"] = [item.as_dict() for item in hard]
    if scope_privilege(payload.get("execution_scope")) == "read_only" \
            and not payload["canonical_untouched"]:
        payload["status"] = "BLOCKED"
        hard.append(Diagnostic("PR9", "canonical", "只读预设改动了 canonical state"))
    if payload["status"] == "BLOCKED":
        code = EXIT_HARD
    elif payload["status"] == "HOLD":
        code = EXIT_ENV
    else:
        code = EXIT_OK
    return payload, hard, code


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # noqa: D401 - argparse hook
        self.print_usage(sys.stderr)
        print(f"argument error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(description="Research preset library, intent router and loop recovery")
    parser.add_argument("command", nargs="?",
                        choices=["list", "resolve", "inspect", "check", "trigger", "run",
                                 "record", "load", "authorize"])
    parser.add_argument("--state", help="path to research-state.json")
    parser.add_argument("--cognition", help="path to the cognition directory")
    parser.add_argument("--scheduler", help="path to scheduler.json")
    parser.add_argument("--text", help="natural-language request to resolve")
    parser.add_argument("--preset", help="preset id")
    parser.add_argument("--signal", help="signal fingerprint for `record`")
    parser.add_argument("--outcome", help="observed outcome for `record`")
    parser.add_argument("--scope", help="authorize: discovery_only | strategy | full")
    parser.add_argument("--revoke", action="store_true", help="authorize: revoke the loop")
    parser.add_argument("--changed-decision", action="store_true",
                        help="record that the recovery changed the next decision")
    parser.add_argument("--apply", action="store_true",
                        help="allow the protocol's write step (projections / strategy memory)")
    parser.add_argument("--fixtures", action="store_true",
                        help="check: also run the provided router-fixtures.json")
    parser.add_argument("--registry-only", action="store_true",
                        help="check the registry without touching the protocol files")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    return parser


def _context_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    if not args.state:
        raise SystemExit("argument error: --state is required")
    state_path = Path(args.state).expanduser()
    cognition = Path(args.cognition).expanduser() if args.cognition else None
    context = project_context(state_path, cognition)
    if args.scheduler:
        scheduler_path = Path(args.scheduler).expanduser()
        if not scheduler_path.is_file():
            print(f"environment error: scheduler not found: {scheduler_path}", file=sys.stderr)
            raise SystemExit(EXIT_ENV)
        context["scheduler"] = json.loads(scheduler_path.read_text(encoding="utf-8"))
    return context


def op_list(as_json: bool) -> int:
    if as_json:
        print(json.dumps({"presets": [{key: preset[key] for key in
                                       ("id", "name_zh", "name_en", "group", "entry",
                                        "execution_scope", "protocol", "priority", "auto")}
                                      for preset in PRESETS]}, ensure_ascii=False, indent=2))
        return EXIT_OK
    print(f"{'id':30s} {'group':10s} {'entry':18s} {'scope':16s} auto")
    for preset in PRESETS:
        auto = ",".join(preset["auto"]["signals"]) if preset.get("auto") else "-"
        print(f"{preset['id']:30s} {preset['group']:10s} {preset['entry']:18s} "
              f"{preset['execution_scope']:16s} {auto}")
    print(f"\n{len(PRESETS)} presets ({len(PRESET_IDS)} ids)")
    return EXIT_OK


def op_resolve(args: argparse.Namespace) -> int:
    context = _context_from_args(args) if args.state else None
    extra: List[Dict[str, Any]] = []
    if context is not None:
        decision = trigger(context["state"], index=context["index_on_disk"],
                           scheduler=context["scheduler"], revisions=context["revisions"],
                           records=context["records"], index_missing=context["index_missing"],
                           projection=context["index"])
        extra = [item for item in decision["candidates"] if item["allowed"]]
    payload = resolve(args.text, state=(context or {}).get("state"),
                      index=(context or {}).get("index"),
                      scheduler=(context or {}).get("scheduler"), extra_triggers=extra)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return EXIT_OK if payload["action"] == "ROUTE" else EXIT_ENV


def op_inspect(args: argparse.Namespace) -> int:
    if not args.preset:
        print("argument error: --preset is required", file=sys.stderr)
        return EXIT_ERROR
    payload = inspect(args.preset)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return EXIT_OK if "error" not in payload else EXIT_ENV


def load_preset_context(preset_id: str, root: Optional[Path] = None
                        ) -> Tuple[Dict[str, Any], int]:
    """Load exactly what one call needs: the shared contract reference + **one** protocol.

    This is the context-budget rule of the integration (load the selected preset and only the
    references it needs; never inject all sixteen). It returns the paths and the text, plus a
    count of the presets deliberately *not* loaded, so a caller can prove the boundary.
    """
    root = root or skill_root()
    preset = presets_by_id().get(preset_id)
    if preset is None:
        return ({"error": f"unknown preset: {preset_id}", "known": list(PRESET_IDS)}, EXIT_ENV)
    contract_path = root / SHARED_CONTRACT_NAME
    protocol_path = root / preset["protocol"]
    if not contract_path.is_file():
        return ({"error": f"shared contract not found: {SHARED_CONTRACT_NAME}",
                 "preset_id": preset_id}, EXIT_ENV)
    if not protocol_path.is_file():
        return ({"error": f"protocol not found: {preset['protocol']}", "preset_id": preset_id},
                EXIT_ENV)
    # The contract is *loaded*, not merely named: it is read here, checked for the sections the
    # protocols rely on, and returned with the one selected protocol. Nothing else is read.
    contract_text = contract_path.read_text(encoding="utf-8")
    protocol_text = protocol_path.read_text(encoding="utf-8")
    problems: List[str] = []
    if not contract_text.strip():
        problems.append("shared contract is empty")
    missing = [section for section in CONTRACT_SECTIONS if section not in contract_text]
    if missing:
        problems.append(f"shared contract is missing sections: {missing}")
    if SHARED_CONTRACT_NAME not in protocol_text:
        problems.append("the protocol does not reference the shared contract")
    return ({
        "schema": SCHEMA_ROUTER,
        "preset_id": preset_id,
        "entry": preset["entry"],
        "execution_scope": preset["execution_scope"],
        "privilege": scope_privilege(preset["execution_scope"]),
        "registry_trigger": preset.get("registry_trigger"),
        "loaded": [SHARED_CONTRACT_NAME, preset["protocol"]],
        "contract_chars": len(contract_text),
        "contract_sections": [section for section in CONTRACT_SECTIONS
                              if section in contract_text],
        "contract_text": contract_text,
        "loaded_references": [f"scripts/{name}.py" for name in preset["reuses"]],
        "not_loaded": [item for item in PRESET_IDS if item != preset_id],
        "protocol_chars": len(protocol_text),
        "protocol_text": protocol_text,
        "problems": problems,
        "status": "PASS" if not problems else "FAIL",
    }, EXIT_OK if not problems else EXIT_HARD)


def run_router_fixtures(path: Optional[Path] = None, root: Optional[Path] = None
                        ) -> Dict[str, Any]:
    """Run the provided `router-fixtures.json` through the router (the intent base test)."""
    root = root or skill_root()
    fixture_path = path or (root / ROUTER_FIXTURES_NAME)
    if not fixture_path.is_file():
        return {"status": "FAIL", "error": f"fixtures not found: {fixture_path}", "cases": []}
    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {"status": "FAIL", "error": f"fixtures are not valid JSON: {exc}", "cases": []}
    cases = [item for item in payload.get("fixtures") or [] if isinstance(item, dict)]
    results: List[Dict[str, Any]] = []
    for case in cases:
        text = case.get("input")
        expected = case.get("expected_preset_id")
        resolved = resolve(text)
        results.append({
            "input": text, "expected": expected, "actual": resolved["preset_id"],
            "guard": case.get("guard"), "ok": resolved["preset_id"] == expected,
            "hold_reason": resolved["hold_reason"],
        })
    failed = [item for item in results if not item["ok"]]
    return {"status": "PASS" if not failed else "FAIL", "total": len(results),
            "passed": len(results) - len(failed), "failed": failed, "cases": results}


def op_authorize(args: argparse.Namespace) -> int:
    """Record (or revoke) the user's authorization for an autonomous loop.

    Written to the scheduler telemetry — never to the canonical state — and read by the trigger
    to decide whether a user preset may auto-start controlled Discovery. Without it, such a
    preset is only ever recommended.
    """
    if not args.state:
        print("argument error: --state is required", file=sys.stderr)
        return EXIT_ERROR
    state_path = Path(args.state).expanduser()
    scheduler_path = (Path(args.scheduler).expanduser() if args.scheduler
                      else state_path.parent / cg.SCHEDULER_NAME)
    scheduler: Dict[str, Any] = {}
    if scheduler_path.is_file():
        try:
            parsed = json.loads(scheduler_path.read_text(encoding="utf-8"))
            scheduler = parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            scheduler = {}
    state = cg.load_state(state_path)
    if args.revoke:
        scheduler.pop(LOOP_AUTHORIZATION_KEY, None)
        action = "revoked"
    else:
        scope = args.scope or "discovery_only"
        if scope not in ("discovery_only", "strategy", "full"):
            print("argument error: --scope must be discovery_only | strategy | full",
                  file=sys.stderr)
            return EXIT_ERROR
        scheduler[LOOP_AUTHORIZATION_KEY] = {
            "authorized": True, "scope": scope,
            "since_state_version": state.get("state_version"),
            "note": "用户授权：可在该范围内自动触发受控 Discovery；不启动 GPU、不改锚点",
        }
        action = "authorized"
    scheduler_path.write_text(json.dumps(scheduler, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    print(json.dumps({"schema": SCHEMA_ROUTER, "action": action,
                      "scheduler": str(scheduler_path),
                      "authorization": loop_authorization(scheduler)},
                     ensure_ascii=False, indent=2))
    return EXIT_OK


def op_load(args: argparse.Namespace) -> int:
    if not args.preset:
        print("argument error: --preset is required", file=sys.stderr)
        return EXIT_ERROR
    payload, code = load_preset_context(args.preset)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


def op_check(args: argparse.Namespace) -> int:
    failures = registry_errors()
    if args.registry_only:
        failures = [item for item in failures if item.rule != "PR3"]
    report = None
    if args.fixtures:
        report = run_router_fixtures()
    for diagnostic in failures:
        print(diagnostic.render())
    ids = sorted(presets_by_id())
    print(f"check: {len(failures)} 处问题；presets={len(PRESETS)}；"
          f"groups={ {group: sum(1 for p in PRESETS if p['group'] == group) for group in PRESET_GROUPS} }")
    print("ids: " + ", ".join(ids))
    if report is not None:
        print(f"router fixtures: {report.get('passed')}/{report.get('total')} "
              f"({report.get('status')})")
        for item in report.get("failed") or []:
            print(f"  ✗ {item['input']!r} → {item['actual']}（期望 {item['expected']}）")
        if report.get("status") != "PASS":
            return EXIT_HARD
    return EXIT_OK if not failures else EXIT_HARD


def op_trigger(args: argparse.Namespace) -> int:
    context = _context_from_args(args)
    payload = trigger(context["state"], index=context["index_on_disk"],
                      scheduler=context["scheduler"], revisions=context["revisions"],
                      records=context["records"], index_missing=context["index_missing"],
                      projection=context["index"])
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return EXIT_OK if payload["action"] == "RECOVER" else EXIT_ENV


def op_run(args: argparse.Namespace) -> int:
    if not args.preset:
        print("argument error: --preset is required", file=sys.stderr)
        return EXIT_ERROR
    if not args.state:
        print("argument error: --state is required", file=sys.stderr)
        return EXIT_ERROR
    state_path = Path(args.state).expanduser()
    cognition = Path(args.cognition).expanduser() if args.cognition else None
    payload, diagnostics, code = run_preset(args.preset, state_path, cognition, apply=args.apply)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    for diagnostic in diagnostics:
        print(diagnostic.render(), file=sys.stderr)
    return code


def op_record(args: argparse.Namespace) -> int:
    if not args.preset:
        print("argument error: --preset is required", file=sys.stderr)
        return EXIT_ERROR
    preset = presets_by_id().get(args.preset)
    if preset is None:
        print(f"environment error: unknown preset: {args.preset}", file=sys.stderr)
        return EXIT_ENV
    context = _context_from_args(args)
    signals = signal_snapshot(context["state"], scheduler=context["scheduler"],
                              index=context["index"], revisions=context["revisions"])
    fingerprint = args.signal or signal_fingerprint(signals, preset["id"])
    guard = recovery_guard(context["records"], preset, fingerprint,
                           (signals.get("_snapshot") or {}).get("state_version"))
    entry = {
        "_schema": SCHEMA_RECOVERY_LOG, "preset_id": preset["id"],
        "at_state_version": (signals.get("_snapshot") or {}).get("state_version"),
        "signal_fingerprint": fingerprint, "outcome": args.outcome or "",
        "changed_decision": bool(args.changed_decision),
        "guard_allowed": guard["allowed"], "guard_reason": guard["reason"],
    }
    print(json.dumps({"schema": SCHEMA_ROUTER, "record": entry, "guard": guard},
                     ensure_ascii=False, indent=2))
    if not guard["allowed"]:
        return EXIT_ENV
    append_ledger(ledger_path(context["cognition_dir"]), entry)
    return EXIT_OK


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.command:
        build_parser().print_usage(sys.stderr)
        print("argument error: a command is required", file=sys.stderr)
        return EXIT_ERROR
    if args.command == "list":
        return op_list(args.json)
    if args.command == "resolve":
        return op_resolve(args)
    if args.command == "inspect":
        return op_inspect(args)
    if args.command == "check":
        return op_check(args)
    if args.command == "trigger":
        return op_trigger(args)
    if args.command == "run":
        return op_run(args)
    if args.command == "record":
        return op_record(args)
    if args.command == "load":
        return op_load(args)
    if args.command == "authorize":
        return op_authorize(args)
    print(f"argument error: unknown command {args.command!r}", file=sys.stderr)
    return EXIT_ERROR




# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _fixture(tmp: Path) -> Path:
    """A minimal, valid project: one claim, one experiment, one candidate."""
    state = {
        "state_version": 4,
        "contract": {"goal": "判断机制 A 是否解释目标现象", "primary_anchor": "phenomenon",
                     "constraints": ["单卡"], "resources": ["公开数据集"],
                     "provisional_anchor_rationale": "先形式化", "out_of_scope": []},
        "claims": [{"id": "C1", "statement": "机制 A 解释目标现象", "parent": None, "subclaims": [],
                    "status": "ungrounded", "supporting_evidence": [], "refuting_evidence": [],
                    "nearest_alternative": "机制 B", "falsifier": "干预 I 后现象不变",
                    "scope": "数据集 A", "known_flaws": [], "depends_on": [],
                    "validity": {"status": "valid", "reason": "初始", "since_state_version": 0}}],
        "evidence": [], "assumptions": [],
        "hypotheses": [{"id": "H1", "statement": "机制 A 是主因",
                        "structural_signature": {"assumption_distance": 2, "formulation_distance": 1,
                                                 "representation_distance": 0,
                                                 "theory_lens_distance": 1, "mechanism_distance": 2},
                        "novelty_source": "假设反转", "theory_lens": "逆问题",
                        "nearest_prior": "LIT1", "falsifier": "干预无效",
                        "expected_information_gain": 0.4, "status": "elite",
                        "niche": "assumption-shift", "island": "P2", "generation": 0,
                        "operator": "assumption_breaker", "parents": [], "depends_on": [],
                        "validity": {"status": "valid", "reason": "未推翻", "since_state_version": 0},
                        "scientific_scope": "数据集 A"}],
        "experiments": [{"id": "X1", "parent": None, "stage": "X3", "claim_targeted": ["C1"],
                         "alternative_targeted": ["ALT-1"], "code_commit": "abc",
                         "data_split": "A/train", "seed": 0, "metric": "效应量", "result": "0.8",
                         "interpretation": "初步", "unexpected": [], "known_flaws": [],
                         "next_branches": [], "status": "planned",
                         "preregistration": {"frozen_at_state_version": 3, "outcomes": [
                             {"id": "O1", "observation": "效应量 ≥ 0.5",
                              "update": [{"target": "C1", "op": "strengthen"}]}]},
                         "result_at_state_version": None, "depends_on": [],
                         "validity": {"status": "pending", "reason": "尚未运行",
                                      "since_state_version": 3},
                         "outcome_analysis": None, "execution_protocol": None}],
        "literature": [{"id": "LIT1", "ref": "[Synthetic, Fixture/2024]",
                        "relation": "shares-structure", "depends_on": [],
                        "validity": {"status": "valid", "reason": "未撤回",
                                     "since_state_version": 0}}],
        "failures": [], "uncertainties": [], "assurance": [], "repairs": [],
    }
    tmp.mkdir(parents=True, exist_ok=True)
    path = tmp / cg.STATE_NAME
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def selftest() -> int:
    import tempfile
    failures = 0

    def check(name: str, condition: bool) -> None:
        nonlocal failures
        if not condition:
            failures += 1
            print(f"[FAIL] {name}")

    check("sixteen presets are registered", len(PRESETS) == 16)
    check("preset ids are unique", len(set(PRESET_IDS)) == 16)
    groups = {group: sum(1 for preset in PRESETS if preset["group"] == group)
              for group in PRESET_GROUPS}
    check("group counts are 6/7/3", groups == {"user": 6, "recovery": 7, "evolution": 3})
    check("every preset reuses an existing script",
          all((Path(__file__).resolve().parent / f"{name}.py").is_file()
              for preset in PRESETS for name in preset["reuses"]))
    check("one handler per preset", set(HANDLERS) == set(PRESET_IDS))
    check("every auto preset maps to a signal", set(AUTO_SIGNAL_MAP) <= set(PRESET_IDS))
    check("user presets auto-start only when the privilege rule allows it",
          all(preset["auto"] is None or preset["auto"].get("mode") == "recommend"
              or may_auto_start(preset)
              for preset in PRESETS if preset["group"] == "user"))
    check("recovery presets recover, not merely recommend",
          all(preset["auto"] and preset["auto"].get("mode") == "recover"
              for preset in PRESETS if preset["group"] in ("recovery", "evolution")))
    fixtures = run_router_fixtures()
    check("the provided router fixtures all pass",
          fixtures.get("status") == "PASS" and fixtures.get("passed") == fixtures.get("total"))
    loaded, load_code = load_preset_context("research-review")
    check("a call loads exactly one protocol",
          load_code == EXIT_OK and len(loaded.get("not_loaded") or []) == 15
          and loaded.get("loaded") == [SHARED_CONTRACT_NAME, "presets/research-review.md"]
          and loaded.get("contract_text"))

    # --- intent routing -------------------------------------------------------
    for preset in PRESETS:
        result = resolve(preset["id"])
        check(f"explicit id routes {preset['id']}",
              result["preset_id"] == preset["id"] and result["trigger"] == "explicit")
        check(f"entry is preserved for {preset['id']}", result["entry"] == preset["entry"])
        check(f"scope is reported for {preset['id']}",
              result["execution_scope"] == preset["execution_scope"])
        check(f"protocol file named for {preset['id']}",
              isinstance(result["protocol"], str) and result["protocol"].startswith("presets/"))
        zh = resolve(preset["zh"][0])
        check(f"zh intent routes {preset['id']}", zh["preset_id"] == preset["id"])
        en = resolve(preset["en"][0])
        check(f"en intent routes {preset['id']}", en["preset_id"] == preset["id"])
    check("unknown text holds", resolve("今天天气不错")["action"] == "HOLD")
    check("negated preset holds",
          resolve("不要审计")["hold_reason"] == "intent_negated")
    mixed = resolve("先不要跑自动科研，只汇报进展")
    check("negation does not swallow the rest of the sentence",
          mixed["preset_id"] in ("research-review", "loop-health-check"))
    check("expert phase entry is not hijacked",
          resolve("phase=R7 继续")["hold_reason"] == "expert_phase_entry")
    ambiguous = resolve("汇报并恢复")
    check("an exact tie falls back to the least privileged preset",
          ambiguous.get("requires_confirmation") is True
          and len(ambiguous.get("ambiguous_with") or []) >= 2
          and ambiguous["execution_scope"] == "read_only")
    check("read-only request stays read-only",
          resolve("现在到底取得了什么科学进展")["execution_scope"] == "read_only")
    descriptive = resolve("训练 OOM 了")
    check("a descriptive report routes to the engineering recovery",
          descriptive["preset_id"] == "experiment-failure-recovery")
    check("a descriptive report starts read-only",
          descriptive["next_action"] == "diagnose" and descriptive["requires_confirmation"])
    imperative = resolve("帮我恢复训练失败的实验")
    check("an explicit request may execute",
          imperative["preset_id"] == "experiment-failure-recovery"
          and imperative["next_action"] == "execute")
    check("routing output is traceable",
          all(key in descriptive for key in ("preset_id", "entry", "trigger", "reason",
                                             "execution_scope", "protocol")))

    # --- signals, triggers and the guard -------------------------------------
    with tempfile.TemporaryDirectory() as temp:
        state_path = _fixture(Path(temp) / "routeA")
        context = project_context(state_path)
        signals = signal_snapshot(context["state"], scheduler=context["scheduler"],
                                  index=context["index"], revisions=context["revisions"])
        check("every signal is computed", set(SIGNAL_IDS) <= set(signals))
        check("a missing on-disk index is drift, not nothing",
              trigger(context["state"], index=None, index_missing=True,
                      projection=context["index"],
                      scheduler=context["scheduler"])["selected"]["preset_id"]
              == "context-drift-recovery")
        cg.op_build(state_path, context["cognition_dir"])
        built = project_context(state_path)
        check("a built, matching index clears the drift signal",
              not built["index_missing"]
              and signal_snapshot(built["state"], scheduler=built["scheduler"],
                                  index=built["index_on_disk"],
                                  projection=built["index"])["context_drift"]["detected"] is False)
        check("a healthy project has no recovery", trigger(
            built["state"], index=built["index_on_disk"], scheduler=built["scheduler"],
            revisions=built["revisions"],
            projection=built["index"])["hold_reason"] == "no_signal")
        preset = presets_by_id()["stagnation-breaker"]
        fingerprint = signal_fingerprint(signals, preset["id"])
        first = recovery_guard([], preset, fingerprint, 4)
        check("first attempt is allowed", first["allowed"])
        used = [{"preset_id": preset["id"], "signal_fingerprint": fingerprint,
                 "at_state_version": 4}]
        second = recovery_guard(used, preset, fingerprint, 4)
        check("the same snapshot is refused",
              not second["allowed"] and second["reason"] == "already_attempted_at_this_snapshot")
        moved = recovery_guard(used, preset, fingerprint, 7)
        check("a moved state may retry", moved["allowed"])
        cooldown = recovery_guard([{"preset_id": preset["id"],
                                    "signal_fingerprint": "other", "at_state_version": 4}],
                                  preset, "brand-new", 5)
        check("cooldown blocks an immediate retry",
              not cooldown["allowed"] and cooldown["reason"] == "cooldown_active")
        # evidence safety outranks stagnation
        broken = json.loads(json.dumps(context["state"]))
        broken["claims"][0]["supporting_evidence"] = ["E9"]
        broken_signals = signal_snapshot(broken, index=None)
        check("a broken state blocks every recovery",
              trigger(broken, index=None)["hold_reason"] == "state_integrity_blocked")
        check("evidence conflict is detected",
              broken_signals["evidence_conflict"]["detected"])

        # --- presets run against the real interfaces -------------------------
        for preset_id in ("research-review", "loop-health-check", "research-audit",
                          "memory-consolidation", "context-drift-recovery",
                          "discovery-replay", "strategy-evolution",
                          "hypothesis-rebalance", "research-recovery",
                          "scientific-replanning", "paradigm-escape",
                          "stagnation-breaker", "experiment-failure-recovery",
                          "evidence-conflict-repair", "resource-recovery",
                          "research-loop"):
            payload, _, code = run_preset(preset_id, state_path)
            check(f"{preset_id} returns a contract", payload.get("preset_id") == preset_id
                  and payload.get("status") in ("OK", "NO_CHANGE", "BLOCKED", "HOLD")
                  and code in (EXIT_OK, EXIT_HARD, EXIT_ENV))
            check(f"{preset_id} reports canonical safety",
                  payload.get("canonical_untouched") is not None)
        read_only = run_preset("research-review", state_path)[0]
        check("read-only preset writes nothing", read_only["writes"] == [])
        escape = run_preset("paradigm-escape", state_path)[0]
        check("paradigm escape changes at least two axes",
              len(escape["observed"]["axes_changed"]) >= 2)
        check("paradigm escape demands a structural audit",
              escape["decision"]["requires_structural_audit"] is True)
        engineering = run_preset("experiment-failure-recovery", state_path)[0]
        check("no engineering failure means no action",
              engineering["status"] == "NO_CHANGE")

    print(f"selftest: {'PASS' if failures == 0 else 'FAIL'} ({failures} failures)")
    return EXIT_OK if failures == 0 else EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
