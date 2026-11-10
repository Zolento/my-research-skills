#!/usr/bin/env python3
"""context_profile.py — 上下文基线与预算的**测量**工具（不是第二个 Agent 框架）。

What this module fixes
----------------------
RLP 被批评为「每次都要读一大堆科研规章」。这个批评可能是对的，但在修之前必须先**量**。
本模块把「上下文成本」拆成互相不可替代的六个测量层，并对每一层单独声明它到底测到了什么：

===========  ==================================================================  ============
层            测什么                                                              可复现
===========  ==================================================================  ============
`static`     磁盘上每个文件的确切字节数。                                             是
`loaded`     某个场景下**加载器实际读取并返回**的字符数（逐文件读后统计）。              是
`visible`    真正进入模型请求的文本。**本仓库无法观测**，只能由外部记录提供。           否（见下）
`duplicate`  同一批已加载文本之间的**逐行 shingle 重叠**（重复注入的确切占比）。        是
`estimate`   启发式 token 估算。**不是真实 token 数**，方法写在 `estimate_tokens`。      是（同一输入同一输出）
`calls`      按「一次读一个文件」保守估算的工具调用次数。                              是
===========  ==================================================================  ============

**`visible` 层的诚实边界。** 一个 Skill 的 SKILL.md 被 Harness 注入时是否被截断、是否被
服务商缓存、会话恢复时重新加载多少 —— 这些都不由本仓库决定，`context_profile.py` 看不到
DSH 的实际模型请求，因此**不产出** `visible` 数值。`--observation <json>` 可以折入外部*实测*
记录（例如一次真实会话里注入字节数与省略字节数），但报告会把它标成 `observed`，并明确
写「单次观测，不是统计量」。把估算和实测混在一张表里、不加标注，是这类工作最容易犯的错误。

**为什么不用固定系数换算 token。** 一个中文字符在不同 tokenizer 下可能是 1—2 个 token，
拉丁文本约 4 字符/token。用单一系数乘字节数得到的数字精度是假的。因此本模块给出
`chars`（精确）与 `est_tokens`（带方法名的启发式估算）两列，并在报告里说明差异来源。

Usage
-----
    python3 scripts/context_profile.py --list
    python3 scripts/context_profile.py --scenario research-loop
    python3 scripts/context_profile.py --all --markdown
    python3 scripts/context_profile.py --all --json --out profile.json
    python3 scripts/context_profile.py --observation obs.json --all
    python3 scripts/context_profile.py --selftest

Exit codes: 0 pass, 1 argument error, 3 hard violation, 4 environment not satisfied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SCHEMA_PROFILE = "research-idea-pipeline/context-profile@1"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_HARD = 3
EXIT_ENV = 4

SKILL_ROOT = Path(__file__).resolve().parent.parent

#: 使用本工具时**必须**随结果一起搬走的限制声明。任何报告里出现 token 数字而不带它，
#: 就是把估算当成了实测。
TOKEN_METHOD = "heuristic_v1: CJK 字符 1 token/char + 其余非空白 1 token/4 chars（向上取整）"
TOKEN_METHOD_NOTE = (
    "est_tokens 是启发式估算，不是真实 tokenizer 输出。仓库内没有可用 tokenizer；"
    "DSH Harness 的实际模型请求不可从本仓库观测。"
)

# ---------------------------------------------------------------------------
# 测量层枚举
# ---------------------------------------------------------------------------

LAYERS: Tuple[str, ...] = ("static", "loaded", "duplicate", "estimate", "calls")

#: 每一层的可信度声明。报告必须原样带上，不允许只贴数字。
LAYER_NOTES: Dict[str, str] = {
    "static": "磁盘字节数，精确",
    "loaded": "加载器实际读取的字符数，精确",
    "duplicate": "已加载文本之间的行级 shingle 重叠，精确（同一输入可复现）",
    "estimate": "启发式 token 估算，非真实 tokenizer 输出",
    "calls": "按一次读一个文件保守估算，非观测到的工具调用",
    "visible": "不可观测：本仓库读不到 DSH 的实际模型请求；只有 --observation 提供时才填",
}


# ---------------------------------------------------------------------------
# Token 估算（显式方法，可复现）
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """启发式 token 估算 —— **不是**真实 tokenizer 输出。

    方法（`heuristic_v1`，写死以便复现）：

    * CJK 字符与全角标点：1 token/char；
    * 其余非空白字符：1 token/4 chars，向上取整；
    * 空白字符不计。

    依据：主流 BPE tokenizer 对中文大致 1—1.5 token/char、对英文约 4 chars/token。
    取中文 1.0 是**下界偏中**的选择，因此估出来的数字不会被夸大。
    """
    cjk = 0
    other = 0
    for ch in text:
        if ch.isspace():
            continue
        if _is_cjk(ch):
            cjk += 1
        else:
            other += 1
    return cjk + (other + 3) // 4


# ---------------------------------------------------------------------------
# 章节切分 —— 复用 `section_index` 的**唯一实现**，不在这里再写一份
# ---------------------------------------------------------------------------

#: 章节寻址只有一份实现。本模块只是它的调用方 —— 两份实现就是两个漂移源，
#: 而这正是本轮要消除的问题。
from section_index import _is_cjk, slugify, split_sections  # noqa: E402


def section_sizes(text: str) -> List[Dict[str, Any]]:
    """每个章节的字数与字节数 + 内容 digest。"""
    out = []
    for section in split_sections(text):
        body = section["text"]
        out.append({
            "id": section["id"],
            "level": section["level"],
            "title": section["title"],
            "chars": len(body),
            "bytes": len(body.encode("utf-8")),
            "lines": body.count("\n") + (0 if body.endswith("\n") or not body else 1),
            "digest": hashlib.sha256(body.encode("utf-8")).hexdigest()[:16],
        })
    return out


# ---------------------------------------------------------------------------
# 重复内容测量（行级 shingle）
# ---------------------------------------------------------------------------

SHINGLE_LINES = 3
#: 太短的行（空行、`---`、`| 字段 | 值 |` 之类）参与 shingle 会制造大量假重叠。
_MIN_LINE_CHARS = 12


def _normalized_lines(text: str) -> List[str]:
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) < _MIN_LINE_CHARS:
            continue
        stripped = re.sub(r"\s+", " ", stripped)
        out.append(stripped)
    return out


def duplicate_report(documents: Dict[str, str]) -> Dict[str, Any]:
    """测量一批文档之间的重复注入。

    **为什么按行 shingle 而不是按句子：** 规范文档的重复几乎总是整段/整表被复制，
    行级 3-gram 能抓住它，又不会被「同一术语在两句里都出现」这种巧合骗到。
    统计口径是**字符级**：落在「至少出现在两个不同文档」的 shingle 里的字符所占比例。
    同一文档内部的重复不算（那是一次加载内的冗余，不是跨文件重复注入）。
    """
    per_doc_lines = {name: _normalized_lines(text) for name, text in documents.items()}
    owners: Dict[Tuple[str, ...], set] = {}
    for name, lines in per_doc_lines.items():
        for start in range(max(0, len(lines) - SHINGLE_LINES + 1)):
            key = tuple(lines[start:start + SHINGLE_LINES])
            owners.setdefault(key, set()).add(name)
    shared = {key for key, names in owners.items() if len(names) > 1}
    per_doc: Dict[str, Any] = {}
    total_chars = 0
    total_shared_chars = 0
    for name, lines in per_doc_lines.items():
        covered = 0
        seen_index: set = set()
        for start in range(max(0, len(lines) - SHINGLE_LINES + 1)):
            key = tuple(lines[start:start + SHINGLE_LINES])
            if key in shared:
                for delta in range(SHINGLE_LINES):
                    index = start + delta
                    if index not in seen_index:
                        seen_index.add(index)
                        covered += len(lines[index])
        doc_chars = sum(len(line) for line in lines)
        total_chars += doc_chars
        total_shared_chars += covered
        per_doc[name] = {
            "chars": doc_chars,
            "shared_chars": covered,
            "shared_ratio": round(covered / doc_chars, 4) if doc_chars else 0.0,
        }
    return {
        "shingle_lines": SHINGLE_LINES,
        "documents": per_doc,
        "total_chars": total_chars,
        "total_shared_chars": total_shared_chars,
        "shared_ratio": round(total_shared_chars / total_chars, 4) if total_chars else 0.0,
        "method": "行级 3-gram；只统计跨文档重复（同一文档内重复不计）",
    }


# ---------------------------------------------------------------------------
# 场景表
# ---------------------------------------------------------------------------

#: 场景的 `baseline_reads` 是**按当前 SKILL.md 的书面加载指令推导**出的读取集合，不是
#: 观测到的模型请求。推导依据写在每个场景的 `baseline_rationale` 里；`SKILL.md` 自身恒为
#: 已注入（Harness 注入，不计工具调用）。
SCENARIOS: Tuple[Dict[str, Any], ...] = (
    {
        "id": "bootstrap",
        "title": "新项目 Bootstrap",
        "entry": "start-project",
        "preset": None,
        "stage": "B0—B6",
        "domain": None,
        "baseline_reads": (
            "references/project-intake.md",
            "references/invocation-prompts.md",
            "references/phase-r0-contract.md",
        ),
        "baseline_rationale": (
            "SKILL.md §启动前置动作 明确要求「按 references/project-intake.md 的 9 个维度盘点」；"
            "§0 要求按 invocation-prompts.md 的固定契约执行；§0 的 R0 链接指向 phase-r0-contract.md。"
        ),
        "hard_constraints": (
            "不得重新 Bootstrap 已有项目", "项目主锚点未声明不得开工",
            "B3 稀疏纪律：每条 state 条目必须可指回真实来源", "B6 之后必须停",
        ),
        "unused_sections": ("7. 设计依据", "8. 规则变更自检清单", "6. 执行自检清单",
                            "3. 子代理派遣总览", "R12 — 叙事", "R8 — 证据契约"),
    },
    {
        "id": "resume",
        "title": "已有项目 Resume",
        "entry": "continue-research",
        "preset": "research-recovery",
        "stage": "R1",
        "domain": None,
        "baseline_reads": (
            "shared-contract.md",
            "presets/research-recovery.md",
            "references/scheduler-policy.md",
        ),
        "baseline_rationale": (
            "shared-contract.md 规定每次加载 Preset 前先读它与选中的单个 Preset；"
            "research-recovery 是 resume 的登记预设；scheduler-policy.md 是下一步动作的权威。"
            "SKILL.md §1.8 另要求读 cognitive-memory-policy 的相关规则。"
        ),
        "hard_constraints": (
            "已有 research-state.json 不得重新 Bootstrap", "从磁盘恢复 State 而不是聊天历史",
            "过期认知摘要不得当作当前事实", "进程终止不等于科学完成",
        ),
        "unused_sections": ("7. 设计依据", "8. 规则变更自检清单",
                            "R12 — 叙事", "1.2 顶会标准锚定", "1.11 Skill-RSI"),
    },
    {
        "id": "research-loop",
        "title": "Research Loop 单轮",
        "entry": "continue-research",
        "preset": "research-loop",
        "stage": "R1 + 闸门",
        "domain": None,
        "baseline_reads": (
            "shared-contract.md",
            "presets/research-loop.md",
            "references/operational-autonomy-policy.md",
            "references/scientific-communication-policy.md",
        ),
        "baseline_rationale": (
            "research-loop 协议正文直接引用 operational-autonomy-policy 与 "
            "scientific-communication-policy；shared-contract 是共同契约。"
        ),
        "hard_constraints": (
            "canonical state 是唯一科学事实源", "A/B/C 三类动作边界",
            "只读请求不得触发执行", "PEIG/AALG 先于 Preset",
            "每阶段收尾 state_check 硬违规为 0",
        ),
        "unused_sections": ("7. 设计依据", "8. 规则变更自检清单", "2. 共享资源索引",
                            "1.1 文献检索", "1.2 顶会标准锚定", "1.4 项目组织与文档落盘",
                            "R12 — 叙事", "R8 — 证据契约"),
    },
    {
        "id": "literature",
        "title": "Literature Discovery",
        "entry": "explore",
        "preset": "paradigm-escape",
        "stage": "R2 / R5",
        "domain": None,
        "baseline_reads": (
            "shared-contract.md",
            "presets/paradigm-escape.md",
            "references/literature-policy.md",
            "references/phase-r2-r5-field-mapping-retrieval.md",
        ),
        "baseline_rationale": (
            "SKILL.md §1.1 把检索执行与来源纪律委托给 literature-policy.md；"
            "§0 的 R2/R5 链接指向 phase-r2-r5；explore 的登记预设是 paradigm-escape。"
        ),
        "hard_constraints": (
            "先 web search 再本地与多源", "T1—T8 强制扩检", "未达 L3 不得写「首次提出」",
            "单源失败不终止检索", "代理环境不得判定为「无人在研究」",
        ),
        "unused_sections": ("7. 设计依据", "8. 规则变更自检清单", "R12 — 叙事",
                            "1.7 认识论权限边界", "1.11 Skill-RSI", "1.2 顶会标准锚定"),
    },
    {
        "id": "paradigm-escape",
        "title": "Paradigm Escape 多方向探索",
        "entry": "explore",
        "preset": "paradigm-escape",
        "stage": "R3—R6",
        "domain": None,
        "baseline_reads": (
            "shared-contract.md",
            "presets/paradigm-escape.md",
            "references/phase-r3-r6-discovery.md",
            "references/structural-equivalence-policy.md",
        ),
        "baseline_rationale": (
            "R3—R6 的权威是 phase-r3-r6-discovery.md；结构等价性判断在 §5.1 被列为"
            "跨阶段服务，探索阶段判定候选是否结构等价时需读 structural-equivalence-policy.md。"
        ),
        "hard_constraints": (
            "P3 只产 typed intermediate", "QD archive 每 live niche 留一个 elite",
            "R3—R6 不得用顶会口味判断候选", "Discovery 不得改 claims[].status",
        ),
        "unused_sections": ("7. 设计依据", "8. 规则变更自检清单", "R12 — 叙事",
                            "1.1 文献检索", "1.9 旧项目接管", "3. 子代理派遣总览"),
    },
    {
        "id": "audit",
        "title": "Research Audit 对抗审查",
        "entry": "audit",
        "preset": "research-audit",
        "stage": "R7 / R10 / R13",
        "domain": None,
        "baseline_reads": (
            "shared-contract.md",
            "presets/research-audit.md",
            "references/phase-r7-r10-r13-assurance-repair-review.md",
            "references/evidence-policy.md",
            "references/scoring-policy.md",
        ),
        "baseline_rationale": (
            "audit 的登记预设是 research-audit；权威流程在 phase-r7-r10-r13；"
            "§2 把证据等级与措辞、评分聚合分别委托给 evidence-policy 与 scoring-policy。"
        ),
        "hard_constraints": (
            "assurance 五元组 + 可判定 Kill Condition", "assurance 不得直接改 claims[].status",
            "Integrity Gate 不通过不得提交", "极性归一化先于聚合",
        ),
        "unused_sections": ("7. 设计依据", "8. 规则变更自检清单",
                            "1.1 文献检索", "1.9 旧项目接管", "1.4 项目组织与文档落盘",
                            "R12 — 叙事"),
    },
    {
        "id": "r8-prereg",
        "title": "R8 实验预注册（冻结契约）",
        "entry": "continue-research",
        "preset": "research-loop",
        "stage": "R8",
        "domain": None,
        "baseline_reads": (
            "shared-contract.md",
            "references/phase-r8-evidence-contract.md",
            "references/evidence-outcome-contract.md",
            "references/execution-identifiability.md",
        ),
        "baseline_rationale": (
            "§0 的 R8 链接指向 phase-r8-evidence-contract.md；§4 的 R0/R1 段要求"
            "按 evidence-outcome-contract 冻结 contract.outcome_policy；"
            "execution-identifiability 在 SKILL.md 的 execution gate 段被要求「先读」。"
        ),
        "hard_constraints": (
            "预注册必须事前冻结，事后不得改判据", "claim 状态只做证据驱动的单向升级",
            "PEIG 不通过不得跑正式 X3/X4", "冻结协议不得被模型修改",
        ),
        "unused_sections": ("7. 设计依据", "8. 规则变更自检清单", "R12 — 叙事",
                            "1.2 顶会标准锚定", "1.9 旧项目接管", "1.11 Skill-RSI"),
    },
    {
        "id": "r9o-outcome",
        "title": "R9.O 结果评价与证据资格",
        "entry": "continue-research",
        "preset": "research-loop",
        "stage": "R9 / R9.O / R10 / R11",
        "domain": None,
        "baseline_reads": (
            "shared-contract.md",
            "references/evidence-outcome-analysis.md",
            "references/evidence-outcome-contract.md",
            "references/evidence-policy.md",
            "references/phase-r9-r11-experiment-loop.md",
        ),
        "baseline_rationale": (
            "§0 的 R9/R10/R11 链接指向 phase-r9-r11；R9.O 的权威是 evidence-outcome-analysis；"
            "outcome 冻结在 evidence-outcome-contract；措辞等级在 evidence-policy。"
        ),
        "hard_constraints": (
            "运行失败不等于机制被否证", "未冻结的预测不得追认",
            "mixed outcome 不得写成支持", "B 类更新必须过 R9.O/R10/R11",
        ),
        "unused_sections": ("7. 设计依据", "8. 规则变更自检清单", "R12 — 叙事",
                            "1.1 文献检索", "1.2 顶会标准锚定", "1.4 项目组织与文档落盘"),
    },
    {
        "id": "mri-ssl",
        "title": "MRI 自监督研究（Domain Profile）",
        "entry": "continue-research",
        "preset": "research-loop",
        "stage": "R8 / R9",
        "domain": "mri-reconstruction",
        "baseline_reads": (
            "shared-contract.md",
            "domain-profiles/mri-reconstruction/PROFILE.md",
            "domain-profiles/mri-reconstruction/ssl-contract.md",
            "domain-profiles/mri-reconstruction/acquisition-contract.md",
            "domain-profiles/mri-reconstruction/evaluation-policy.md",
        ),
        "baseline_rationale": (
            "§2 的领域协议条目把 MRI 的四份子协议一起给出，当前没有「按任务只取一份」的机制，"
            "所以一个自监督任务会连带读到采集与评价协议全文。"
        ),
        "hard_constraints": (
            "GT-free 训练不得使用 GT", "SSL Loss 改善不等于重建质量提高",
            "阈值冻结（DP7）", "独立 Ω_val 可用于 GT-free 模型选择",
        ),
        "unused_sections": ("7. 设计依据", "8. 规则变更自检清单", "R12 — 叙事",
                            "1.1 文献检索", "1.4 项目组织与文档落盘"),
    },
    {
        "id": "mri-method",
        "title": "MRI 方法创新（TAG + MMS + I2M）",
        "entry": "continue-research",
        "preset": "stagnation-breaker",
        "stage": "R3 / R8",
        "domain": "mri-reconstruction",
        "baseline_reads": (
            "shared-contract.md",
            "presets/stagnation-breaker.md",
            "domain-profiles/mri-reconstruction/PROFILE.md",
            "domain-profiles/mri-reconstruction/attribution-guard.md",
            "domain-profiles/mri-reconstruction/mechanism-search.md",
            "references/skill-rsi-policy.md",
        ),
        "baseline_rationale": (
            "TAG 与 MMS 分别由 attribution-guard.md 与 mechanism-search.md 定义；"
            "I2M 的方法候选与进展判定由 skill-rsi-policy.md 与 insight_to_method 承担。"
        ),
        "hard_constraints": (
            "TAG 不得凭自我声明认定物理限制", "MMS 候选必须有具体数学改变",
            "已失败的相似方法不能改名获得新颖性", "新增解释不算方法进展（PE17）",
        ),
        "unused_sections": ("7. 设计依据", "8. 规则变更自检清单", "R12 — 叙事",
                            "1.2 顶会标准锚定", "1.9 旧项目接管"),
    },
    {
        "id": "context-drift",
        "title": "Context Drift Recovery",
        "entry": "continue-research",
        "preset": "context-drift-recovery",
        "stage": "R1",
        "domain": None,
        "baseline_reads": (
            "shared-contract.md",
            "presets/context-drift-recovery.md",
            "references/cognitive-memory-policy.md",
        ),
        "baseline_rationale": (
            "context-drift-recovery 是登记预设；§1.8 把 hot/warm/cold 加载与失效规则"
            "委托给 cognitive-memory-policy.md。"
        ),
        "hard_constraints": (
            "失效摘要不得当作新事实", "不得自动清空 Research State",
            "不得重新 Bootstrap", "恢复走既有 CIE 链",
        ),
        "unused_sections": ("7. 设计依据", "8. 规则变更自检清单",
                            "1.1 文献检索", "1.2 顶会标准锚定", "R12 — 叙事"),
    },
    {
        "id": "subagent",
        "title": "多 Agent 协作（子 Agent 上下文）",
        "entry": "continue-research",
        "preset": "research-loop",
        "stage": "派遣",
        "domain": None,
        "baseline_reads": (
            "shared-contract.md",
            "references/roles.md",
            "presets/research-loop.md",
        ),
        "baseline_rationale": (
            "§3 要求子代理沿用统一角色库 references/roles.md，并把 shared-contract 的"
            "共同约束一并交给子代理；当前没有按角色裁剪的机制。"
        ),
        "hard_constraints": (
            "子 Agent 不得绕过已有状态写入权限", "子 Agent 自评不得升级为科学证据",
            "Context Packet 不得成为第二个授权来源",
        ),
        "unused_sections": ("7. 设计依据", "8. 规则变更自检清单",
                            "1.1 文献检索", "1.4 项目组织与文档落盘", "R12 — 叙事"),
    },
)

#: 新架构（planned）下每个场景交给 `context_planner` 的参数。
#: `preset=None` 表示该入口无预设，走 registry 的 `entry_context`。
PLAN_PARAMS: Dict[str, Dict[str, Any]] = {
    "bootstrap": dict(entry="start-project", preset=None, conditional=[]),
    "resume": dict(entry="continue-research", preset="research-recovery",
                   conditional=["next_action_selection"]),
    "research-loop": dict(entry="continue-research", preset="research-loop",
                          conditional=["evidence_qualification"]),
    "literature": dict(entry="explore", preset="paradigm-escape",
                       conditional=["literature_search"]),
    "paradigm-escape": dict(entry="explore", preset="paradigm-escape", conditional=[]),
    "audit": dict(entry="audit", preset="research-audit", conditional=[]),
    "r8-prereg": dict(entry="continue-research", preset="research-loop",
                      conditional=["experiment_issue_or_run"]),
    "r9o-outcome": dict(entry="continue-research", preset="research-loop",
                        conditional=["evidence_qualification"]),
    "mri-ssl": dict(entry="continue-research", preset="research-loop",
                    conditional=[], domain="mri-reconstruction",
                    slices=["ssl-contract", "acquisition-contract"]),
    "mri-method": dict(entry="continue-research", preset="stagnation-breaker",
                       conditional=["mechanism_attribution", "method_candidate"],
                       domain="mri-reconstruction", slices=[]),
    "context-drift": dict(entry="continue-research", preset="context-drift-recovery",
                          conditional=["next_action_selection"]),
    # 子 Agent 不继承主 Agent 的协议上下文：它只拿角色任务契约，因此没有「读取文件」这一步。
    "subagent": dict(entry="continue-research", preset="research-loop",
                     conditional=[], subagent_role="literature"),
}

SCENARIO_IDS: Tuple[str, ...] = tuple(item["id"] for item in SCENARIOS)


def scenario_by_id(scenario_id: str) -> Optional[Dict[str, Any]]:
    for item in SCENARIOS:
        if item["id"] == scenario_id:
            return dict(item)
    return None


# ---------------------------------------------------------------------------
# 语料级重复：SKILL.md 有多少内容在 references 里已有逐字副本
# ---------------------------------------------------------------------------

def skill_vs_references(root: Optional[Path] = None) -> Dict[str, Any]:
    """量 SKILL.md 与 `references/` 之间的**逐字**重复。

    这是回答「SKILL.md 里有多少是复述」的唯一可复现方式。它的**已知盲区**必须一起报出：
    逐字重复低，不代表没有语义重复 —— 同一规则换个说法写两遍，shingle 看不出来。
    因此本函数的输出里带 `blind_spot`，而语义层面的权威归属由 `docs/rule-relocation-matrix.md`
    人工逐条裁定。
    """
    root = root or SKILL_ROOT
    skill_text = _read(root, "SKILL.md") or ""
    refs: Dict[str, str] = {}
    for path in sorted((root / "references").glob("*.md")):
        refs[f"references/{path.name}"] = path.read_text(encoding="utf-8")
    if not refs:
        return {"status": "FAIL", "error": "references/ is empty"}

    # 逐段检查：SKILL.md 的每个章节，是否在任一份 reference 里有 3 行以上的逐字重合。
    sections = split_sections(skill_text)
    ref_line_sets = {name: set(_normalized_lines(text)) for name, text in refs.items()}
    findings: List[Dict[str, Any]] = []
    duplicated_chars = 0
    for section in sections:
        own = _normalized_lines(section["text"])
        if not own:
            continue
        best_name = None
        best_hits = 0
        for name, lines in ref_line_sets.items():
            hits = sum(1 for line in own if line in lines)
            if hits > best_hits:
                best_hits, best_name = hits, name
        ratio = best_hits / len(own)
        if best_hits and ratio >= 0.5:
            size = len(section["text"])
            duplicated_chars += size
            findings.append({
                "section": section["title"],
                "section_id": section["id"],
                "chars": size,
                "verbatim_line_ratio": round(ratio, 3),
                "best_match": best_name,
            })

    total_chars = len(skill_text)
    return {
        "skill_chars": total_chars,
        "skill_bytes": len(skill_text.encode("utf-8")),
        "reference_files": len(refs),
        "reference_chars": sum(len(text) for text in refs.values()),
        "sections_with_verbatim_copy": findings,
        "duplicated_chars": duplicated_chars,
        "duplicated_ratio": round(duplicated_chars / total_chars, 4) if total_chars else 0.0,
        "method": ("按章节检查：该章节 ≥50% 的行在某一 reference 里逐字出现，"
                   "才记为「有逐字副本」；阈值 50% 避免个别术语命中造成假阳性"),
        "blind_spot": ("逐字副本占比低 ≠ 没有语义重复。SKILL.md 对多数 reference 是"
                       "**换个说法的复述**，这一层 shingle 测不出来，"
                       "由 docs/rule-relocation-matrix.md 逐条人工裁定。"),
    }


# ---------------------------------------------------------------------------
# 单场景测量
# ---------------------------------------------------------------------------

def _read(root: Path, rel: str) -> Optional[str]:
    path = root / rel
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _sections_matching(text: str, titles: Sequence[str]) -> List[Dict[str, Any]]:
    """按**标题文本**命中章节，并把命中的子树一并算入（父标题带出子章节）。

    用标题文本而不是行号：行号在文档被编辑后立即失效，而这里要回答的是
    「这次加载有多少字节是本场景用不到的」。
    """
    sections = section_sizes(text)
    hit: List[Dict[str, Any]] = []
    active_level: Optional[int] = None
    active_hit = False
    for section in sections:
        title = section["title"].strip()
        matched = any(token and token in title for token in titles)
        if active_hit and active_level is not None and section["level"] > active_level:
            hit.append(section)
            continue
        if matched:
            hit.append(section)
            active_level = section["level"]
            active_hit = True
        else:
            active_hit = False
            active_level = None
    return hit


def profile_scenario(
    scenario: Dict[str, Any],
    root: Optional[Path] = None,
    skill_doc: str = "SKILL.md",
    reads_key: str = "baseline_reads",
    architecture: str = "baseline",
    skill_doc_path: Optional[Path] = None,
    texts: Optional[Dict[str, str]] = None,
    tool_calls: Optional[int] = None,
) -> Dict[str, Any]:
    """测一个场景。

    `SKILL.md` 恒为**已注入**（Harness 注入 Skill 正文，不是工具调用），因此它计入
    `loaded_chars` 而**不**计入 `tool_calls`。其余文档按「一次读一个文件」计入工具调用。

    `reads_key` 允许调用方传入另一套读取集合（新架构用 Context Planner 的输出），
    这样前后两臂用同一把尺子量。
    """
    root = root or SKILL_ROOT
    no_skill_doc = bool(scenario.get("_no_skill_doc"))
    skill_text = (_read(root, skill_doc) if skill_doc_path is None
                  else Path(skill_doc_path).read_text(encoding="utf-8"))
    if skill_text is None and not no_skill_doc:
        return {"status": "FAIL", "error": f"skill document missing: {skill_doc}"}

    documents: Dict[str, str] = {}
    if skill_text is not None:
        documents[skill_doc] = skill_text
    # 子 Agent 的「上下文正文」是角色任务契约，不是任何协议文件。
    if no_skill_doc:
        contract = (scenario.get("_subagent_text") or "")
        if contract:
            documents[f"<subagent-contract:{scenario['id']}>"] = contract
    missing: List[str] = []
    calls = 0
    for rel in scenario.get(reads_key) or ():
        # 新架构臂用 `context_planner.execute()` 的真实输出：章节级依赖只计命中的章节，
        # 不再按整份文件计。否则基准会把「按章节加载」算成「读全文」。
        text = (texts or {}).get(rel) if texts is not None else _read(root, rel)
        if text is None:
            missing.append(rel)
            continue
        documents[rel] = text
        calls += 1

    loaded_chars = sum(len(text) for text in documents.values())
    loaded_bytes = sum(len(text.encode("utf-8")) for text in documents.values())
    section_count = sum(len(section_sizes(text)) for text in documents.values())

    dup = duplicate_report(documents)

    unused_hits: List[Dict[str, Any]] = []
    for rel, text in documents.items():
        for section in _sections_matching(text, scenario.get("unused_sections") or ()):
            unused_hits.append({"doc": rel, "section": section["title"],
                                "chars": section["chars"]})
    unused_chars = sum(item["chars"] for item in unused_hits)

    return {
        "schema": SCHEMA_PROFILE,
        "scenario": scenario["id"],
        "title": scenario.get("title"),
        "architecture": architecture,
        "entry": scenario.get("entry"),
        "preset": scenario.get("preset"),
        "stage": scenario.get("stage"),
        "domain": scenario.get("domain"),
        "status": "PASS" if not missing else "INCOMPLETE",
        "missing": missing,
        "files": (["SKILL.md"] if skill_text is not None else []) + list(scenario.get(reads_key) or ()),
        "file_count": len(documents),
        "loaded_sections": section_count,
        "loaded_chars": loaded_chars,
        "loaded_bytes": loaded_bytes,
        "est_tokens": sum(estimate_tokens(text) for text in documents.values()),
        "tool_calls": calls if tool_calls is None else tool_calls,
        "duplicate": dup,
        "unused_chars": unused_chars,
        "unused_ratio": round(unused_chars / loaded_chars, 4) if loaded_chars else 0.0,
        "unused_sections": unused_hits,
        "hard_constraints": list(scenario.get("hard_constraints") or ()),
        "measurement": {
            "static": "exact",
            "loaded": "exact",
            "duplicate": "exact",
            "estimate": TOKEN_METHOD,
            "visible": LAYER_NOTES["visible"],
        },
    }


def planned_reads(scenario_id: str, root: Optional[Path] = None,
                  skill_doc: str = "SKILL.md",
                  skill_doc_path: Optional[Path] = None
                  ) -> Tuple[List[str], Optional[Dict[str, Any]]]:
    """用 Context Planner 产出**新架构**下该场景的读取集合。

    子 Agent 场景特殊：子 Agent 不继承主 Agent 的协议上下文，只拿角色任务契约，
    所以它没有「读取协议文件」这一步。此时返回空读取集合，并附上契约规模报告。
    """
    import context_planner as cplan
    root = root or SKILL_ROOT
    params = PLAN_PARAMS.get(scenario_id)
    if not params:
        return [], None
    if params.get("subagent_role"):
        import subagent_context as sac
        contract = sac.build(params["subagent_role"], "probe task")
        return [], {"kind": "subagent_contract", "role": params["subagent_role"],
                    "chars": contract["chars"], "text": contract.get("text") or ""}
    payload = cplan.plan(entry=params["entry"], preset_id=params["preset"], root=root,
                         domain=params.get("domain"), authorization="execute",
                         conditional_active=params.get("conditional") or (),
                         domain_slices=params.get("slices") or ())
    executed = cplan.execute(payload, root=root)
    # 字符数按**要求项**计（章节级要求只计命中的章节），
    # 工具调用按**唯一文档**计（同一文件的两个章节要求只读一次盘）。
    reads: List[str] = []
    unique_docs: List[str] = []
    for item in executed.get("required") or ():
        if item["path"] == "SKILL.md":
            continue
        reads.append(item["path"])
        doc = item.get("doc") or item["path"]
        if doc not in unique_docs:
            unique_docs.append(doc)
    texts = {}
    for item in executed.get("loaded") or []:
        texts[item["path"]] = item["text"]
    if "SKILL.md" in texts:
        texts.pop("SKILL.md")           # SKILL.md 由 skill-doc 参数单独计
    return reads, {"kind": "plan", "plan_digest": executed.get("plan_digest"),
                   "tool_calls": len(unique_docs),
                   "can_proceed": executed.get("can_proceed"),
                   "loaded_chars": executed.get("loaded_chars"),
                   "blocked_missing": executed.get("blocked_missing"),
                   "budget": executed.get("budget"),
                   "texts": texts}


def profile_all(
    root: Optional[Path] = None,
    scenarios: Optional[Sequence[str]] = None,
    architecture: str = "baseline",
    reads_map: Optional[Dict[str, Sequence[str]]] = None,
    skill_doc: str = "SKILL.md",
    skill_doc_path: Optional[Path] = None,
) -> Dict[str, Any]:
    root = root or SKILL_ROOT
    wanted = list(scenarios or SCENARIO_IDS)
    results: List[Dict[str, Any]] = []
    for scenario_id in wanted:
        scenario = scenario_by_id(scenario_id)
        if scenario is None:
            return {"status": "FAIL", "error": f"unknown scenario: {scenario_id}"}
        extra: Dict[str, Any] = {}
        if reads_map and scenario_id in reads_map:
            scenario["baseline_reads"] = list(reads_map[scenario_id])
        elif architecture == "planned":
            reads, extra = planned_reads(scenario_id, root=root,
                                         skill_doc=skill_doc,
                                         skill_doc_path=skill_doc_path)
            scenario["baseline_reads"] = reads
            if extra and extra.get("kind") == "subagent_contract":
                # 子 Agent 不加载 SKILL.md：它的上下文就是角色任务契约本身。
                scenario["_no_skill_doc"] = True
                scenario["_subagent_text"] = extra.get("text") or ""
        item = profile_scenario(scenario, root=root, architecture=architecture,
                                skill_doc=skill_doc, skill_doc_path=skill_doc_path,
                                texts=(extra.get("texts") if extra else None),
                                tool_calls=(extra.get("tool_calls") if extra else None))
        if extra:
            item["plan"] = extra
        results.append(item)
    failed = [item for item in results if item["status"] != "PASS"]
    return {
        "schema": SCHEMA_PROFILE,
        "architecture": architecture,
        "skill_doc_bytes": len(((Path(skill_doc_path).read_text(encoding="utf-8"))
                               if skill_doc_path else (_read(root, "SKILL.md") or "")
                               ).encode("utf-8")),
        "scenarios": results,
        "status": "PASS" if not failed else "INCOMPLETE",
        "totals": {
            "scenarios": len(results),
            "mean_loaded_chars": round(
                sum(item["loaded_chars"] for item in results) / len(results)) if results else 0,
            "mean_est_tokens": round(
                sum(item["est_tokens"] for item in results) / len(results)) if results else 0,
            "mean_tool_calls": round(
                sum(item["tool_calls"] for item in results) / len(results), 2) if results else 0,
        },
        "measurement_note": TOKEN_METHOD_NOTE,
    }


# ---------------------------------------------------------------------------
# 外部观测（Harness 侧）
# ---------------------------------------------------------------------------

def apply_observation(profile: Dict[str, Any], observation: Dict[str, Any]) -> Dict[str, Any]:
    """把一次**实测**的 Harness 注入记录折进报告，并强制标注它是什么。

    观测记录字段：`skill`, `version`, `harness`, `observed_at`, `injected_bytes`,
    `visible_bytes`, `elided_bytes`, `note`。缺少任一字段即拒绝 —— 没有来源的「实测数字」
    比没有数字更糟。
    """
    required = ("skill", "version", "harness", "observed_at",
                "injected_bytes", "visible_bytes", "elided_bytes")
    missing = [key for key in required if key not in observation]
    if missing:
        raise ValueError(f"observation is missing fields: {missing}")
    injected = int(observation["injected_bytes"])
    visible = int(observation["visible_bytes"])
    elided = int(observation["elided_bytes"])
    if injected - visible != elided:
        raise ValueError("observation is internally inconsistent: "
                         f"{injected} - {visible} != {elided}")
    profile = dict(profile)
    profile["observation"] = {
        "source": observation,
        "layer": "visible",
        "label": "observed",
        "reproducible_by_this_script": False,
        "caveat": ("单次观测，不是统计量；由外部 Harness 记录提供，本脚本无法复现。"
                   "不得与 est_tokens 相加或互相校验。"),
        "visible_ratio": round(visible / injected, 4) if injected else 0.0,
        "elided_ratio": round(elided / injected, 4) if injected else 0.0,
    }
    return profile


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def render_markdown(profile: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Context Profile")
    lines.append("")
    lines.append(f"- schema: `{profile.get('schema')}`")
    lines.append(f"- architecture: `{profile.get('architecture')}`")
    if "skill_doc_bytes" in profile:
        lines.append(f"- SKILL.md: {profile['skill_doc_bytes']} bytes")
    lines.append(f"- token 口径：{TOKEN_METHOD}")
    lines.append(f"- 限制：{TOKEN_METHOD_NOTE}")
    lines.append("")
    if "scenarios" in profile:
        lines.append("| 场景 | 入口 | 文件 | 章节 | 字符 | est_tokens | 工具调用 "
                     "| 跨文件重复 | 未用但加载 |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for item in profile["scenarios"]:
            lines.append(
                f"| `{item['scenario']}` | {item.get('entry')} | {item['file_count']} "
                f"| {item['loaded_sections']} | {item['loaded_chars']} | {item['est_tokens']} "
                f"| {item['tool_calls']} | {item['duplicate']['shared_ratio']:.1%} "
                f"| {item['unused_ratio']:.1%} |")
        totals = profile.get("totals") or {}
        lines.append("")
        lines.append(f"平均：{totals.get('mean_loaded_chars')} 字符 / "
                     f"{totals.get('mean_est_tokens')} est_tokens / "
                     f"{totals.get('mean_tool_calls')} 次工具调用")
    else:
        lines.append(f"- scenario: `{profile.get('scenario')}`")
        lines.append(f"- files: {profile.get('files')}")
        lines.append(f"- loaded_chars: {profile.get('loaded_chars')}")
        lines.append(f"- est_tokens: {profile.get('est_tokens')}")
        lines.append(f"- tool_calls: {profile.get('tool_calls')}")
        dup = profile.get("duplicate") or {}
        lines.append(f"- 跨文件重复：{dup.get('shared_ratio')}")
        lines.append(f"- 未用但加载：{profile.get('unused_ratio')}")
    observation = profile.get("observation")
    if observation:
        source = observation["source"]
        lines.append("")
        lines.append("## 外部观测（visible 层）")
        lines.append("")
        lines.append(f"- 来源：{source['harness']} / {source['skill']} {source['version']} "
                     f"/ {source['observed_at']}")
        lines.append(f"- 注入 {source['injected_bytes']} bytes，模型可见 "
                     f"{source['visible_bytes']} bytes，省略 {source['elided_bytes']} bytes"
                     f"（可见率 {observation['visible_ratio']:.1%}）")
        lines.append(f"- 标注：**observed**，不可由本脚本复现。{observation['caveat']}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def selftest(verbose: bool = False) -> Dict[str, Any]:
    checks: List[Tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    # 1) token 估算：CJK 与拉丁分开计
    check("estimate_tokens: CJK 1/char", estimate_tokens("中文") == 2,
          str(estimate_tokens("中文")))
    check("estimate_tokens: latin 4chars/token", estimate_tokens("abcd") == 1,
          str(estimate_tokens("abcd")))
    check("estimate_tokens: whitespace disregarded", estimate_tokens("   ") == 0)
    check("estimate_tokens: mixed", estimate_tokens("研究 abcdefg") == 2 + 2,
          str(estimate_tokens("研究 abcdefg")))

    # 2) 围栏内的 `#` 不是标题（本仓库真实踩过的坑）
    fenced = "## real\n\ntext\n\n```bash\n# not a heading\n```\n\n## second\n"
    titles = [s["title"] for s in split_sections(fenced)]
    check("split_sections: 围栏内 # 不算标题", titles == ["real", "second"], str(titles))

    # 3) slug 稳定、不依赖行号
    doc_a = "# A\n\n## 读 / 写 World Model\n"
    doc_b = "# A\n\n前置段落\n\n\n## 读 / 写 World Model\n"
    ids_a = [s["id"] for s in split_sections(doc_a)]
    ids_b = [s["id"] for s in split_sections(doc_b)]
    check("split_sections: 插入段落不改变 section id",
          ids_a == ids_b, f"{ids_a} vs {ids_b}")

    # 4) 重名标题追加序号
    dup_doc = "## x\n\na\n\n## x\n\nb\n"
    ids = [s["id"] for s in split_sections(dup_doc)]
    check("split_sections: 重名标题唯一化", len(set(ids)) == 2, str(ids))

    # 5) 重复检测只算跨文档
    same = "line one is long enough\nline two is long enough\nline three is long enough\n"
    one_doc = duplicate_report({"a": same + same})
    check("duplicate_report: 同文档内重复不计", one_doc["shared_ratio"] == 0.0,
          str(one_doc["shared_ratio"]))
    two_docs = duplicate_report({"a": same, "b": same})
    check("duplicate_report: 跨文档重复被计入", two_docs["shared_ratio"] > 0.9,
          str(two_docs["shared_ratio"]))
    short = duplicate_report({"a": "# A\n-\n", "b": "# A\n-\n"})
    check("duplicate_report: 过短行不制造假重叠", short["shared_ratio"] == 0.0,
          str(short["shared_ratio"]))

    # 6) 观测记录必须自洽
    good = {"skill": "s", "version": "1", "harness": "h", "observed_at": "t",
            "injected_bytes": 100, "visible_bytes": 60, "elided_bytes": 40}
    try:
        merged = apply_observation({"schema": SCHEMA_PROFILE}, good)
        check("apply_observation: 自洽记录被接受",
              merged["observation"]["visible_ratio"] == 0.6)
    except ValueError as exc:  # pragma: no cover
        check("apply_observation: 自洽记录被接受", False, str(exc))
    try:
        apply_observation({}, dict(good, visible_bytes=99))
        check("apply_observation: 不自洽记录被拒绝", False, "accepted")
    except ValueError:
        check("apply_observation: 不自洽记录被拒绝", True)
    try:
        apply_observation({}, {"skill": "s"})
        check("apply_observation: 缺字段被拒绝", False, "accepted")
    except ValueError:
        check("apply_observation: 缺字段被拒绝", True)

    # 7) 每个场景的读取集合都必须真实存在（否则基线是编的）
    root = SKILL_ROOT
    missing: List[str] = []
    for item in SCENARIOS:
        for rel in item["baseline_reads"]:
            if not (root / rel).is_file():
                missing.append(f"{item['id']} → {rel}")
    check("scenarios: 基线读取集合全部真实存在", not missing, "、".join(missing))

    # 8) 场景 id 唯一
    check("scenarios: id 唯一", len(set(SCENARIO_IDS)) == len(SCENARIO_IDS))

    # 9) 语料级重复检测：合成一个「SKILL 章节被 reference 逐字复制」的最小仓库
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "references").mkdir()
        copied = "\n".join(f"这是一条足够长的规则行 编号 {i} 用于触发逐字重复检测"
                           for i in range(6))
        (root / "references" / "dup.md").write_text("## 权威\n\n" + copied + "\n",
                                                    encoding="utf-8")
        (root / "SKILL.md").write_text("# S\n\n## 复述\n\n" + copied + "\n\n"
                                       "## 独有\n\n这一段在参考文献里不存在。\n",
                                       encoding="utf-8")
        report = skill_vs_references(root=root)
        titles = [item["section"] for item in report["sections_with_verbatim_copy"]]
        check("skill_vs_references: 逐字副本被识别", "复述" in titles, str(titles))
        check("skill_vs_references: 独有段落不算重复", "独有" not in titles, str(titles))
        check("skill_vs_references: 报出盲区", bool(report.get("blind_spot")))

    # 10) 真实仓库上必须能跑通且给出比例
    real = skill_vs_references()
    check("skill_vs_references: 真实仓库可运行",
          real.get("skill_chars", 0) > 0 and "duplicated_ratio" in real)

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
    parser = argparse.ArgumentParser(description="RLP 上下文基线与预算测量")
    parser.add_argument("--list", action="store_true", help="列出场景")
    parser.add_argument("--scenario", action="append", default=None, help="只测这些场景")
    parser.add_argument("--all", action="store_true", help="测全部场景")
    parser.add_argument("--architecture", default="baseline",
                        help="标记本次测量对应哪套加载架构")
    parser.add_argument("--observation", default=None, help="外部 Harness 实测记录 JSON")
    parser.add_argument("--corpus", action="store_true",
                        help="量 SKILL.md 与 references/ 之间的逐字重复")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--markdown", action="store_true", help="输出 Markdown")
    parser.add_argument("--skills", action="store_true", help="同时输出技能合规摘要")
    parser.add_argument("--out", default=None, help="写入文件")
    parser.add_argument("--root", default=None, help="Skill 根目录")
    parser.add_argument("--skill-doc", default=None,
                        help="用另一份 SKILL.md 参与测量（基线对照用，路径）")
    parser.add_argument("--selftest", action="store_true", help="自检")
    args = parser.parse_args(argv)

    if args.selftest:
        result = selftest(verbose=True)
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_OK if result["status"] == "PASS" else EXIT_HARD

    root = Path(args.root).resolve() if args.root else SKILL_ROOT

    if args.list:
        for item in SCENARIOS:
            print(f"{item['id']:<18} {item['entry']:<18} "
                  f"{item.get('preset') or '-':<22} {item['title']}")
        return EXIT_OK

    if args.corpus:
        report = skill_vs_references(root=root)
        if args.out:
            Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"SKILL.md {report['skill_chars']} chars / {report['skill_bytes']} bytes")
            print(f"references: {report['reference_files']} 个文件 / "
                  f"{report['reference_chars']} chars")
            print(f"有逐字副本的章节：{len(report['sections_with_verbatim_copy'])} 个，"
                  f"{report['duplicated_chars']} chars "
                  f"({report['duplicated_ratio']:.1%})")
            for item in report["sections_with_verbatim_copy"]:
                print(f"  - {item['section'][:50]:<52} "
                      f"{item['chars']:>6} chars  {item['verbatim_line_ratio']:.0%} ← "
                      f"{item['best_match']}")
            print()
            print(f"盲区：{report['blind_spot']}")
        return EXIT_OK

    if not args.all and not args.scenario:
        parser.error("需要 --all 或 --scenario")

    skill_doc_path = Path(args.skill_doc) if args.skill_doc else None
    if args.all:
        profile = profile_all(root=root, architecture=args.architecture,
                              skill_doc_path=skill_doc_path)
    else:
        results = []
        for scenario_id in args.scenario:
            scenario = scenario_by_id(scenario_id)
            if scenario is None:
                print(f"unknown scenario: {scenario_id}", file=sys.stderr)
                return EXIT_ERROR
            results.append(profile_scenario(scenario, root=root,
                                            architecture=args.architecture,
                                            skill_doc_path=skill_doc_path))
        profile = {
            "schema": SCHEMA_PROFILE,
            "architecture": args.architecture,
            "skill_doc_bytes": len(((Path(skill_doc_path).read_text(encoding="utf-8"))
                               if skill_doc_path else (_read(root, "SKILL.md") or "")
                               ).encode("utf-8")),
            "scenarios": results,
            "status": "PASS" if all(r["status"] == "PASS" for r in results) else "INCOMPLETE",
            "totals": {
                "scenarios": len(results),
                "mean_loaded_chars": round(sum(r["loaded_chars"] for r in results) / len(results)),
                "mean_est_tokens": round(sum(r["est_tokens"] for r in results) / len(results)),
                "mean_tool_calls": round(
                    sum(r["tool_calls"] for r in results) / len(results), 2),
            },
            "measurement_note": TOKEN_METHOD_NOTE,
        }

    if args.observation:
        observation = json.loads(Path(args.observation).read_text(encoding="utf-8"))
        try:
            profile = apply_observation(profile, observation)
        except ValueError as exc:
            print(f"invalid observation: {exc}", file=sys.stderr)
            return EXIT_ERROR

    if args.out:
        Path(args.out).write_text(json.dumps(profile, ensure_ascii=False, indent=2),
                                  encoding="utf-8")

    if args.json:
        print(json.dumps(profile, ensure_ascii=False, indent=2))
    elif args.markdown:
        print(render_markdown(profile), end="")
    else:
        print(render_markdown(profile), end="")

    return EXIT_OK if profile.get("status") != "FAIL" else EXIT_HARD


if __name__ == "__main__":
    raise SystemExit(main())
