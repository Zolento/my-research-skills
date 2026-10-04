---
name: research-idea-pipeline
description: >-
  面向 CVPR / ICML / NeurIPS 投稿的研究创意全流程流水线，覆盖文献调研、idea
  发现、方案生成、方案复核四个可独立调用、也可串联调用的子流程。文献检索先查
  本地文献库，未命中再通过 Python arxiv 包拉取，遇到 429 限流自动指数退避等待。
  End-to-end research-idea pipeline for top-conference submissions: literature
  survey, idea discovery, proposal generation, and proposal review. Use when the
  user wants to brainstorm research ideas, find a gap in the literature, turn an
  idea into a full paper proposal plus experiment plan, or rigorously review a
  proposal before submission. Prefers the local literature library and falls back
  to the arXiv Python package with exponential backoff on HTTP 429. Triggers:
  research idea, idea discovery, brainstorm ideas, find a gap, novel idea,
  literature survey, related work, proposal, research proposal, experiment plan,
  proposal review, mock review, reviewer critique, 找 idea, 头脑风暴, 研究创意,
  文献调研, 相关工作, 方案生成, 方案复核, 审阅方案, 投稿方案, 顶会投稿.
argument-hint: "mode=A|B|C|D [领域关键词 | idea | proposal | query]"
metadata:
  author: research-idea-pipeline
  version: "1.0.0"
  upstream-spec: "顶会研究创意流水线（Research Idea Pipeline）"
---

# Research Idea Pipeline（顶会研究创意流水线）

一套面向 CVPR / ICML / NeurIPS 投稿的研究创意全流程辅助流水线。覆盖从文献调研、
idea 发现、方案生成到方案复核的完整链路，并支持四个子流程的独立调用与串联调用。

**本 Skill 只做编排与串联。** 子代理的角色设定、评分维度、审查视角沿用统一角色库
（见 [references/roles.md](references/roles.md)），不在各 Mode 内重新定义。

---

## 0. 入口：解析 mode 参数

用户通过 `mode` 参数指定调用哪个子流程。`$ARGUMENTS` 的第一项即 `mode`。

| Mode | 名称 | 作用 | 可独立调用 | 可被谁调用 |
|---|---|---|---|---|
| **A** | `idea-discovery` | 基础文献调研 + 多子代理头脑风暴，产出 idea 候选 | 是 | — |
| **B** | `proposal-generation` | 基于 idea 做创新性与可行性研究，产出方案 | 是 | 接 A 之后 |
| **C** | `proposal-review` | 复核已有方案与审阅内容的正确性与创新性 | 是 | 接 B，或接上一次 C 继续复核 |
| **D** | `literature-survey` | 补充文献、扩大检索范围 | 是 | 被 A/B/C 调用，也可单独调用 |

**解析规则：**

1. 若 `$ARGUMENTS` 含 `mode=A|B|C|D`（大小写不敏感），按该 Mode 执行。
2. 若未给出 mode，**先反问用户**要调用哪个 Mode，不要猜测；只有意图极其明确时
   （如"帮我做文献调研"→ D、"帮我审一下这个方案"→ C）才可按意图推断，并在
   输出开头声明所推断的 Mode。
3. mode 之外的参数按该 Mode 的输入约定解析（见下）。
4. 若用户显式给了多个 Mode（如 `mode=A,B,C`），按 A → B → C 顺序串联执行，
   中间状态通过 `state.json` 片段传递（见 §5）。

**各 Mode 详细流程：**

- Mode A → [references/mode-a-idea-discovery.md](references/mode-a-idea-discovery.md)
- Mode B → [references/mode-b-proposal-generation.md](references/mode-b-proposal-generation.md)
- Mode C → [references/mode-c-proposal-review.md](references/mode-c-proposal-review.md)
- Mode D → [references/mode-d-literature-survey.md](references/mode-d-literature-survey.md)

---

## 1. 全局不变量（所有 Mode 强制遵守）

以下三条是硬约束，任何 Mode 都不得违反。执行前先确认，输出时自检。

### 1.1 文献检索：先本地，后 arxiv，429 必须等待

```
Step 1: 搜索本地文献库 ./local_literature/
        命中 → 直接返回，标注 source="local"，不再请求 arxiv
Step 2: 本地未命中 → 调用 Python arxiv 包
        命中 → 拉取元数据与摘要，缓存到本地库，标注 source="arxiv"
Step 3: 本地命中但信息不足 → 仅补充缺失字段，不重复拉取已有内容
```

**429 处理：** 捕获限流错误后按指数退避等待 `10s → 20s → 40s → 80s → 160s`，
最多重试 5 次；**重试期间不得发起任何新的 arxiv 请求**；5 次后仍失败则返回本地
已有结果，并标注"arxiv 暂时不可用，以下结果仅来自本地库"。

完整规范、目录格式约定与可直接运行的实现见
[references/literature-policy.md](references/literature-policy.md) 与
[scripts/literature_search.py](scripts/literature_search.py)。

### 1.2 顶会标准锚定

所有创新性判定必须引用 CVPR / ICML / NeurIPS 的具体标准；所有贡献必须标注类型
（General / Theory / Use-Inspired / Concept & Feasibility / Negative Results 或
方法 / 理论 / 实证 / 问题定义）；所有"首次提出"声称必须经 S-Lit 核实。
标准全文见 [references/venue-standards.md](references/venue-standards.md)。

### 1.3 输出规范

- 结构化报告，使用标题和表格。
- 所有引用给出具体出处，格式 `[作者, 会议/年份]`。
- 无法确认的信息标注 **"待核实"**，**不得臆造**。
- 所有分析结论必须有文献依据或明确逻辑链。
- 每条"没做到 / 缺乏"必须关联**具体未建立的结构性质或未满足的理论条件**，
  禁止模糊表述。

---

## 2. 共享资源索引

| 资源 | 位置 | 内容 |
|---|---|---|
| 子代理角色库 | [references/roles.md](references/roles.md) | R-CVPR / R-ICML / R-NeurIPS / A-Author / A-Experimenter / S-Lit / S-Nov / S-Theory / S-Feas / S-Devil / S-Repro |
| 顶会创新性标准 | [references/venue-standards.md](references/venue-standards.md) | CVPR / ICML / NeurIPS 三视角锚定标准 |
| 文献检索规范 | [references/literature-policy.md](references/literature-policy.md) | 本地优先、arxiv 调用、429 退避、缓存、目录格式 |
| 检索实现脚本 | [scripts/literature_search.py](scripts/literature_search.py) | 可直接运行的 local-first + 429 backoff 实现 |
| 状态传递模板 | [templates/state.template.json](templates/state.template.json) | `state.json` 片段结构 |
| 串联示例 | [examples/](examples/) | A→B→C、接续 C、单独 D 的示例调用与产物形状 |

---

## 3. 子代理派遣总览

所有 Mode 共享同一角色库。按 Mode 需派遣的子代理如下（角色定义不重复，见
[references/roles.md](references/roles.md)）：

| Mode | 派遣子代理 |
|---|---|
| A | R-CVPR、R-ICML、R-NeurIPS、A-Author、A-Experimenter、S-Devil（每个至少 3 个 idea） |
| B | R-CVPR、R-ICML、R-NeurIPS（创新性）；S-Lit（先前工作核实）；S-Feas（可行性）；S-Theory（理论基础）；投稿人视角展开提案；实验设计者视角展开实验 |
| C | R-CVPR、R-ICML、R-NeurIPS、S-Devil、S-Feas、S-Lit、S-Repro（七子代理严格审查 + 交叉质询） |
| D | 无（执行者直接完成检索与归纳） |

**派遣原则：** 子代理必须**独立产出**，不得互相抄袭结论；汇总时去重并保留来源标注。
交叉质询（Mode C）要求每个子代理对其余子代理的评分提出至少一条质疑或补充。

---

## 4. 各 Mode 输入 / 输出速查

### Mode A — idea-discovery

- **输入：** 研究领域关键词；已有参考文献（可选）；资源约束（可选）。
- **流程：** A1 基础文献调研（调用 Mode D 或内联执行）→ A2 深度局限性分析 →
  A3 多子代理头脑风暴 → A4 发散策略约束 → A5 输出编号 idea 清单。
- **发散策略约束：** 每个 idea 必须通过以下**至少一种**策略推导：
  *问题重构 / 假设挑战 / 跨域迁移 / 反向思考 / 组合创新*。
- **交付物：** idea 候选清单（**不少于 10 个**）+ 技术路线归纳表 + 创新性边界界定
  （红海 / 蓝海苗头 / 无人区）。

### Mode B — proposal-generation

- **输入：** 一个或多个 idea（来自 Mode A 或用户直接提供）；关键参考文献（可选）；
  资源约束（可选）。
- **流程：** B1 创新性研究（三审稿人视角 + S-Lit 核实）→ B2 可行性研究
  （S-Feas + S-Theory）→ B3 论文格式展开 → B4 实验流程设计 → B5 输出。
- **交付物：** 论文提案（1500—2000 字）+ 实验流程计划书 + 创新性判定 + 可行性评分
  + 风险清单。

### Mode C — proposal-review

- **输入：** 待复核方案（来自 Mode B 或用户提供）；上一次审阅内容（可选，用于接续
  复核）；关键参考文献（可选）。
- **流程：** C1 判断复核类型（首次 / 接续）→ C2 七子代理严格审查 → C3 交叉质询与
  共识形成 → C4 复核结论 → C5 接续复核规则。
- **交付物：** 七子代理评审意见 + 交叉质询记录 + 审查结论卡片 + 横向对比表 +
  （接续复核时）变更追踪表。

### Mode D — literature-survey

- **输入：** 检索关键词或研究问题；检索范围（时间范围、会议范围、数量上限）；
  是否强制刷新本地缓存（默认**否**）。
- **流程：** D1 本地检索 → D2 arxiv 补充检索 → D3 范围扩大策略 → D4 输出。
- **交付物：** 文献列表（含来源标注）+ 检索过程记录（含 429 等待日志）+ 本地缓存
  更新记录。

---

## 5. 模式衔接与状态传递

```
[用户输入]
    │
    ├─ Mode D（可独立）──────┐
    │                        │
    ├─ Mode A ──→ Mode B ──→ Mode C ──→ Mode C（接续）
    │      ↑         ↑          ↑
    │      └─ D ─────┴──── D ───┘
    │
    └─ 任意 Mode 可单独调用
```

每个 Mode 输出时，附加一个 `state.json` 片段（模板见
[templates/state.template.json](templates/state.template.json)）：

```json
{
  "mode": "A",
  "timestamp": "...",
  "idea_candidates": [],
  "literature_used": [],
  "open_questions": [],
  "next_mode_suggestion": "B"
}
```

**接续规则：**

- Mode B 读取 Mode A 的 `idea_candidates`。
- Mode C 读取 Mode B 的 `proposal` 与 `experiment_plan`。
- Mode C 接续复核时，读取上一次 Mode C 的 `review_output` 与 `open_questions`。
- 任意 Mode 调用 Mode D 时，传递 `query` 与 `scope`。

**落地约定：** 状态写入工作目录下的 `.research-idea-pipeline/state-<mode>-<timestamp>.json`；
串联调用时后一个 Mode 读取前一个 Mode 的片段。若用户未要求持久化，则在回复末尾
以 JSON 代码块给出该片段即可。

---

## 6. 执行自检清单（每次输出前）

- [ ] mode 已明确，且与该 Mode 的输入约定一致。
- [ ] 文献检索走了"先本地后 arxiv"，每条结果标注了 `source`。
- [ ] 若发生 429，输出了等待日志，且退避符合 `10→20→40→80→160s`、上限 5 次。
- [ ] arxiv 结果已写入 `./local_literature/cache/`。
- [ ] 创新性判定引用了具体顶会标准；贡献标注了类型。
- [ ] 所有"首次提出"声称已由 S-Lit 核实，或标注"待核实"。
- [ ] 无臆造引用；无法确认处标注"待核实"。
- [ ] 已附 `state.json` 片段与 `next_mode_suggestion`。

---

## 7. 设计依据（为什么这样编排）

1. **为什么用 Mode 而非单一流程？** 四个能力需可独立、可串联；Mode 化让每个子流程
   有清晰输入输出，并通过 `state.json` 传递状态，避免重复劳动。
2. **为什么文献检索必须"先本地后 arxiv"？** 本地检索零成本、零延迟、无 429 风险；
   arxiv 是补充手段而非首选，缓存进一步减少重复请求。
3. **为什么 429 要指数退避？** 429 通常意味着短时限流；指数退避比固定等待更高效，
   也比立即重试更礼貌；5 次上限避免无限阻塞。
4. **为什么 Mode C 支持接续复核？** 接续复核聚焦上次未解决问题与新增变更，避免
   重复完整审查，同时用"变更追踪表"保证审查连续性。
5. **为什么角色不变？** 本 Skill 只做编排，角色定义、评分维度、审查视角全部沿用
   统一角色库，保证审查标准的一致性。
