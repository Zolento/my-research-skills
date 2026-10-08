---
name: research-idea-pipeline
description: >-
  以 Research State 为中心的科研搜索系统，面向 CVPR / ICML / NeurIPS / MICCAI 投稿：
  双循环（Discovery 扩大候选并保多样性 / Assurance 对抗审核与修复）共 15 个阶段 R0—R14，
  由 24 条硬规则机械强制。首次进入已有代码项目走 Bootstrap（只观察不推进）；
  日常用四个入口 start-project / continue-research / explore / audit。
  End-to-end research search system centered on a Research State: a dual loop
  (Discovery expands and preserves diversity; Assurance attacks and repairs)
  across 15 stages R0-R14, with 24 machine-enforced hard rules. Use when the
  user wants to survey literature, find a research gap, turn an idea into a
  submittable proposal plus experiment plan, generate and adversarially review
  paper narratives, or let evidence eliminate wrong explanations.
  Triggers: 找 idea, 头脑风暴, 研究创意, 文献调研, 相关工作, 研究缺口, 方案生成,
  实验计划, 论文叙事, 叙事套路, 讲故事, 卖点, 叙事评审, 方案复核, 审阅方案,
  投稿方案, 顶会投稿, 研究状态, 范式逃逸, 医学影像, 医学图像, 临床验证,
  research idea, idea discovery, brainstorm ideas, find a gap, novel idea,
  literature survey, related work, research proposal, experiment plan,
  paper narrative, storytelling, framing, positioning, narrative review,
  proposal review, mock review, reviewer critique, paradigm escape,
  research state, MICCAI, medical image analysis, clinical validation,
  proposal, narrative, review, 定位
argument-hint: "<start-project|continue-research|explore|audit> [phase=R0..R14] [writing=asd-ste100] [领域关键词 | idea | proposal | query]"
metadata:
  author: research-idea-pipeline
  version: "2.3.0"
  upstream-spec: "顶会研究创意流水线（Research Idea Pipeline）"
---

# Research Idea Pipeline（顶会研究创意流水线）

一套面向 CVPR / ICML / NeurIPS / MICCAI 投稿的**科研搜索系统**，不是文档流水线。
以 **Research State 为中心**，同时运行 **Discovery Loop**（扩大候选、保多样性）与
**Assurance Loop**（对抗审核、修复、可复现），共 15 个 R 阶段（R0—R14）。

**本 Skill 只做编排与串联。** 子代理的角色设定、评分维度、审查视角沿用统一角色库
（见 [references/roles.md](references/roles.md)），不在各 R 阶段内重新定义。

---

## 0. 入口：**语义入口优先**

`continue-research` 区分建议与执行授权，见 [invocation-prompts.md](references/invocation-prompts.md) §2。
持续执行时遵守 [scheduler-policy.md](references/scheduler-policy.md) §3.1，避免诊断长期替代方法探索。

**用户不需要知道 `R` 编号。** 常态入口是四个语义入口；`phase=` 是专家 / 调试用的**覆盖入口**。

**解析顺序（固定，命中即停 —— 这是唯一顺序，不得自行调整）：**

| 层 | 输入长什么样 | 处理 |
|---|---|---|
| **1. 语义入口**（常态） | `start-project` / `continue-research` / `explore` / `audit` | 按 [invocation-prompts.md](references/invocation-prompts.md) 的固定契约执行。用户只描述目标，不选阶段 |
| **2. 自然语言意图** | 「多给我一些新方向」「攻击一下我现在的路线」 | **映射到第 1 层的四个入口之一**，并在输出开头**声明映射结果**（对应表见 [invocation-prompts.md](references/invocation-prompts.md)） |
| **3. 显式 `phase=`**（**专家 / 调试覆盖**） | `phase=R8` / `phase=R3-R6` / `phase=R7,R10,R13` | 按该阶段的读写契约执行。**这是覆盖入口，不是常态入口** |
| **4. 兜底** | 以上都无法解析 | **才**反问用户要跑哪些阶段；不得猜测 |

**裁决规则（机器读者必须按这条走）：**

- **不要同时给出语义入口与 `phase=`。** 两者同时出现时**按语义入口执行**，并在输出开头
  **显式声明**这次裁决 —— 不得静默选一个。
- **`phase=` 不因为"更具体"就自动赢。** 它的定位是专家 / 调试覆盖：只在前两层都没命中时才生效。
- **旧 `mode=` 参数不再接受**（旧 A—E 阶段字母已退役）。收到时**必须报错**并给出映射
  （A→R2/R5、B→R3/R4/R6、C→R8、D→R12、E→R7/R10/R13），
  **不得**静默按旧模式执行，也不得猜测用户「其实想跑哪个」。

**架构 = 以 Research State 为中心的双循环**（权威定义见
[research-state-policy.md](references/research-state-policy.md)）：

```text
R0 研究契约 ─▶ R1 Research World Model ─▶ R2 领域测绘
                                              │
              ┌───────────────────────────────┴───────────────┐
              ▼                                               ▼
      DISCOVERY LOOP                                  ASSURANCE LOOP
  R3 双轨发现   R4 隔离种群                     R7 对抗保证   R8 证据契约
  R5 共演化检索 R6 进化                         R10 元认知修复 R13 artifact 审计
              └───────────────────┬───────────────────────────┘
                                  ▼
             R9 实验树 ─▶ R9.O Outcome Analysis ─▶ R10 修复 ─▶ R11 回写 World Model
                                  ▼
             R12 叙事 ─▶ R13 审查 ─▶ R14 决策（continue | pivot | archive | submit）
```

| Phase | 名称 | 作用 | 读 state | 写 state |
|---|---|---|---|---|
| **R0** | `research-contract` | 目标 / 约束 / 资源 / **provisional anchor** | — | `contract` + 模板骨架（含 `state_version: 0`） |
| **R1** | `research-state` | **常驻**：维护八类一等对象 | 全部 | 全部 |
| **R2** | `field-mapping` | field grammar + occupancy map + 检索纪律 | `literature` / `assumptions` / `uncertainties` | `literature` / `evidence`(kind=literature) / `assumptions` / `uncertainties` |
| **R3** | `dual-discovery` | 双轨发现：**隔离 Exploration Agents**（`P1`—`P6` 算子）+ `local`；执行者只编排（**上下文隔离**）。**`P3` 只产 typed intermediate，不产 candidate** | `literature` / `assumptions` / `failures` / `contract.constraints` | `hypotheses`（**含 `niche` / `island` / `operator` / `parents: []` / `generation: 0`**）/ `claims`（**seed**：每个 candidate 至少一条 `C`，`status: ungrounded`） |
| **R4** | `isolated-populations` | 隔离种群 → structural signature → QD archive | `hypotheses` | `hypotheses[].status`（**QD archive 精修：重排 elite 归属**） |
| **R5** | `co-evolving-retrieval` | idea → 新 query → 新文献（**常驻服务**） | `hypotheses` | `literature` / `evidence`(kind=literature) |
| **R6** | `evolution` | mutation / crossover / simplification / 新 niche（**首次占据一个当前为空的合法轴**；**唯一允许跨 island 融合**） | `hypotheses` / `uncertainties` / `failures` | `hypotheses[].generation` / `hypotheses[].status` / `hypotheses[].operator` / `hypotheses[].parents` / `failures` / `known_flaws`（把新 `F` 挂上） |
| **R7** | `adversarial-assurance` | 六攻击面审核 + 硬门禁 `G1—G5` | `claims` / `evidence` / `assumptions` / `hypotheses` | `assurance` / `failures` / `uncertainties` / `known_flaws`（把新 `F` 挂上） |
| **R8** | `evidence-contract` | 每个 central claim 一张证据契约 | `claims` / `evidence` / `assurance` | `claims[].contract` / `claims[].status`（**仅证据驱动的单向升级**：`ungrounded` → `partially-supported` / `supported`） / `evidence` / `claims[].supporting_evidence` / `refuting_evidence` / `uncertainties` / `experiments`（**创建 `planned` 条目 + 冻结 `preregistration`**） |
| **R9** | `experiment-tree` | 实验树 `X1—X6` + EIG 选择 + provenance | `uncertainties`(critical, high 且 high) / `claims` | `experiments`（**执行**）/ `experiments[].status` / `experiments[].result_at_state_version` / `assurance[].discriminating_test` / `failures` / `known_flaws`（把新 `F` 挂上） |
| **R10** | `metacognitive-repair` | **critical flaw ⇒ state 必须改变** | 全 state + artifact | `repairs` + **执行 `state_delta`** |
| **R11** | `state-update` | result → claim / uncertainty → next experiment | 全 state | 归并去重 + **失效传播至不动点** + `state_version` +1 + 跑 `state_check.py` |
| **R12** | `narrative` | **state 的视图**：六槽位 + presets + 六维 | `claims` / `evidence` / `failures` / `uncertainties` | `narrative_view`（+ 必要时新增 `uncertainties`） |
| **R13** | `artifact-review` | artifact-aware 审查（code / logs / failed runs） | 全 state + artifact | `reviews` / `failures` / `experiments[].unexpected` / `known_flaws`（把新 `F` 挂上）；缺口**必须**交 R10 |
| **R14** | `decision` | continue / pivot / archive / submit | 全 state + 未闭环 `repairs` | `decision` / `repairs[].closure` / `uncertainties[].status` / `hypotheses[].status`（**不含 `claims[].status`** —— `killed` 只能经 R10） |

> **R1 是常驻对象，不是一次调用。** 任何 R 阶段开工前先读 World Model，收工前写回。
> **R10 是闭环，不是报告：** 检测到 critical flaw ⇒ **state 必须改变**（见 §1.6）。

### 各阶段的分工（不重叠）

> **等价旧口号：** R3 决定"做不做"，R8 决定"做什么"，R12 决定"怎么讲"，
> R7 + R10 决定"做得对不对"。

| 维度 | Discovery Loop（R3—R6） | Assurance Loop（R7 / R10 / R13） |
|---|---|---|
| 对象 | `hypotheses[]` 候选群体 | `claims[]` / `evidence[]` / `experiments[]` |
| 可行性 | 概念可行性：结构是否成立 | 工程可行性：做法能否跑通、变量是否可控 |
| 正确性 | 不判 | 方法正确性：推导 / 实现 / 指标 / 统计是否成立 |
| 创新性 | 产出发散度（QD archive 的 niche 覆盖） | 是否**实质复现**已有工作（防复现） |
| 复现性 | 不涉及（不派 S-Repro） | 必查（S-Repro + 防复现检查） |
| 深度 | 广：population + 隔离 islands | 深：六攻击面 + 交叉质询 + 硬门禁 |

**Discovery 只管扩大与保多样性，Assurance 只管会不会被推翻。** 两者**都不允许直接改
`claims[].status`** —— 改 claim 状态**默认只能经 R10**（例外见 §1.6：R8 的证据驱动单向升级），这是防"自己给自己判分"的结构性措施。
**做得很扎实的复现仍是拒稿理由。**

**解析细则（配合上表四层）：**

1. 第 3 层的 `phase=` 写法：`R0|R1|…|R14`（大小写不敏感；逗号分隔或 `R3-R6` 区间均可），
   按上述顺序依次执行这些阶段。
2. 第 1 / 2 层命中时**不得**再要求用户选阶段 —— 入口自己决定跑什么
   （`start-project` 只跑 `B0`—`B6`；`explore` 跑 `R3`—`R6`；`audit` 跑 `R7`/`R10`/`R13`）。
3. 第 4 层才反问；反向推断（从意图猜阶段序号）**不是**允许的捷径。
4. 阶段之外的参数按该阶段的输入约定解析（见下）。
5. **写回义务：** 每个阶段收尾**必须**更新 World Model 的对应字段（读/写列见上表），
   并跑 `python3 scripts/state_check.py <state.json>`，**硬违规须为 0**。
6. **档位参数（可选）**：若 `$ARGUMENTS` 含 `writing=asd-ste100`，或用户在自然语言里
   显式要求「用 asd-ste100 档」，本次调用按 **asd-ste100** 执行（见 §1.3 与
   [writing-policy.md](references/writing-policy.md) §1）。未声明即走默认档；
   **Agent 不得自行升档**，声明也**不跨轮继承**。

**启动前置动作（每次调用都做）：**

> **若是已有代码 / 实验 / 文献 / 结论的存量项目，先做接管摸底** ——
> 按 [references/project-intake.md](references/project-intake.md) 的 9 个维度盘点，**不得从零开始**，
> **项目里已有的信息不得重复询问用户**；只有「缺失且会实质影响科研判断」的信息才集中提问（一次问完）。

0. **先确认锚定点（核心目标）** —— 见 §0.1。**项目主锚点未声明前不得开工。**
1. **读项目根目录的 `AGENTS.md`**（若存在）—— 其布局、命名、公用部分约定优先于本
   Skill 默认约定。**并校验它引用的文件是否都存在**：缺失项记入根 `INDEX.md` 的
   Warnings。**悬空引用会让后续所有"按 AGENTS.md 办"的动作失效**，所以发现即记。
2. **确定路线**（`routes/A` / `routes/B` / …）。用户未指定时反问；若只有一条路线则用它。
3. **读该路线的 `README.md` / `STATUS.md` / `INDEX.md`**：`README` 是路线身份证，
   `STATUS` 是当前状态（state 投影），`INDEX` 是材料目录。
4. 若路线或三件套不存在，按
   [references/project-layout.md](references/project-layout.md) §7 的检查清单手工建立
   （目录 + `README.md` / `STATUS.md` / `INDEX.md`）后再开工。

> **与 `AGENTS.md` 冲突时的裁决：** `AGENTS.md` 的**纪律性条款**（如"必须改进最终任务
> 性能""禁止在证明性工作上停留"）**优先于任何既有路线的锚定契约**。冲突时按 **§0.2
> 锚点变更单**处理：为该路线申请新方向，**或**按项目主锚点重定位（`anchor_role` +
> 可证伪的 `serves`）。**不得用路线自述的 `core_goal` 去抵消 `AGENTS.md` 的纪律。**

> 详细约定见 [references/project-layout.md](references/project-layout.md)。

### 0.1 锚定点（开工前必问，先于一切）

**开始任何 R 阶段之前，必须先与用户确认本工作的核心目标（锚定点）。未确认前不得开工。**

用户没说就**反问**——不要猜，更不要默认成"提高性能"。用户已经讲清楚了，就复述一遍
请其确认。

| 锚点 | 核心目标 | 成功判据 | 典型会议 | 贡献类型 |
|---|---|---|---|---|
| **理论** | 提出并验证理论：定理 / 界 / 不可能性 / 统一框架 | 命题成立、证明无缺口、假设必要且紧 | ICML / NeurIPS | Theory |
| **性能** | 提高某个任务 / 指标的绝对性能 | 公平比较下超过最强基线 | CVPR / NeurIPS | 方法 |
| **现象** | 发现并解释反直觉现象 | 解释唯一且具预测力 | NeurIPS / ICML | 实证 |
| **基准** | 揭示现有评测掩盖的失败 | 基准暴露真实失败模式 | CVPR / NeurIPS | 实证 / 问题定义 |
| **可行性** | 把不可行 / 过贵的方法变可行 | 保持理论保证同时显著降本 | CVPR / ICML | Concept & Feasibility |
| **负结果** | 证明某目标在一定条件下不可能 | 不可能性成立且给出可达松弛 | NeurIPS | Negative Results |

**三层锚点体系（先把层级分清，否则规则会互相打架）：**

| 层级 | 是什么 | 写在哪 | 谁定 |
|---|---|---|---|
| **项目主锚点** | 整个项目要成功，必须拿下什么 | **根 `INDEX.md` 的「项目主锚点」声明** | 用户（开工前确认一次） |
| **路线锚点** | 本条路线自己主攻什么（`core_goal`） | 路线 frontmatter + 路线 `INDEX.md` 概要 + `state.json` | 用户 / 执行者，须与项目主锚点对齐 |
| **次锚点** | 辅助方向 | **只写路线 `INDEX.md` 概要与 `state.json`** | 执行者 |

**规则：**

0. **项目主锚点必须先声明。** 只声明一次，写在根 `INDEX.md`。未声明前不得开工。
1. **允许组合，但必须指定主锚点。** 例如"主锚点 = 理论，次锚点 = 可行性"。
   **`core_goal` 字段只记主锚点**（单值，便于脚本解析）。**次锚点写进路线 `INDEX.md`
   概要与 `state.json` 的 `core_goal_secondary`**，**不得**塞进 `core_goal`
   （写成 `"theory+feasibility"` 之类会被下游脚本判为非法值）。
2. **锚点必须落盘，且路线必须声明它与项目主锚点的关系：**
   - **`core_goal`** —— 路线锚点（枚举见上表；英文枚举值见 §3 frontmatter）；
   - **`anchor_role`** —— `primary`（本路线就是主锚点的主战场）/ `supporting`（服务
     主锚点，但主攻方向不同）/ `orthogonal`（与主锚点成功判据无关）；
   - **`serves`** —— `supporting` **必填**：服务哪条主锚点、通过什么机制；
   - **`serves_evidence`** —— 该机制落到哪条贡献 / 实验，**须可核验**（如 `T003/K1`）。
   四者同时写进 frontmatter、路线 `INDEX.md` 概要与 `state.json`。
3. **`supporting` 必须可证伪，否则只能标 `orthogonal`。** 要说明**一个会因它而改变的
   下游决策**，以及该决策对主锚点成功判据的**可测影响**（自己实测，或写明由谁实测、
   指标与判据）。**只写"有理论价值 / 能提供洞见"不算。**
   - 答不出 ⇒ 只能标 `orthogonal`，并在根 `INDEX.md` 写明「不参与主锚点成功判据」；
   - **`orthogonal` 的路线不得进入 R12、不得作为投稿主线。**
4. **路线锚点不得覆盖项目主锚点。** 项目主锚点是**项目级**约束，任何路线都不能靠
   自称 `core_goal: theory` 来豁免它。**要改项目主锚点，只能走 §0.2 锚点变更单，
   且只有用户能授权** —— agent 只能提请，不能自行换方向（见 §0.2 约束 1）。
5. **锚点变更必须显式记录** —— 填 **§0.2 锚点变更单**。只有义务、没有载体的规则会空转。
6. **锚点与产出不一致时必须当场指出，并给出处置。** 例如项目主锚点是"性能"，但某条
   路线的 idea 是纯理论类、或实验设计里没有同算力公平比较 —— **指出冲突只是第一步**，
   必须**当轮落盘**下列之一：
   - ① **重新定位（agent 可自行执行）：** 给出**可证伪的** `serves` + `serves_evidence`，
     标 `anchor_role: supporting`。**答不出 ⇒ 只能标 `orthogonal`**，按规则 3 公开标注
     并接受后果（不得进 R12、不得作投稿主线）。
   - ② **换方向（只有用户能授权）：** 向用户**提请**并给出证据；**用户显式同意后**，
     才按 §0.2 开锚点变更单。**agent 不得自行换方向、换项目主锚点或开新路线。**
   **不得只提示冲突就继续。**

> **强制力的边界（避免误读）：** 本节的"必须服务主锚点"**不是**"不服务就作废"。
> 严格选法下，它的强制力是**「服务，或降级 + 公开正交」**。真正被禁止的是**沉默**：
> 既不服务、又不公开标注、还继续当作主线推进。

**锚点如何约束各 R 阶段：**

| R 阶段 | 锚点的作用 |
|---|---|
| **R2 / R5** | **检索边界：** 理论锚点必须查定理 / 反例 / 不可能性与负结果；性能锚点必须查 SOTA 与评测协议 |
| **R3—R6** | **推导与筛选：** 理论锚点优先「假设挑战」，性能锚点优先「问题重构 / 组合创新」；QD archive **收 `serving` 与 `challenging` 两类候选**（`orthogonal` 不进档案，见 §0.1 规则 3）。**不得**只收服务锚点的候选 —— 那会把 Paradigm Escape 的嘴堵住 |
| **R8** | **贡献类型与契约：** 理论锚点下证据契约必须含证明 / 反例 / 边界条件；性能锚点下必须含同算力·同数据·同调参的公平比较与显著性检验 |
| **R12** | **叙事资格（先于选 preset）：** 先做 **Anchor Eligibility Test**（[claim-first-policy.md](references/claim-first-policy.md) §6）——只有 `eligible` / `conditional` 的锚点才可用于组织叙事；与作者**目标锚点**冲突时**必须显式告知**。通过后再按 [narrative-patterns.md](references/narrative-patterns.md) §2 选 preset |
| **R7 / R10 / R13** | **评审权重：** 理论锚点首查证明正确性；性能锚点首查公平比较、指标口径与统计方案 |

**各 R 阶段 详细流程：**

- R0 → [references/phase-r0-contract.md](references/phase-r0-contract.md)
- R1 → [references/research-state-policy.md](references/research-state-policy.md)
- R2 / R5 → [references/phase-r2-r5-field-mapping-retrieval.md](references/phase-r2-r5-field-mapping-retrieval.md)
- R3—R6 → [references/phase-r3-r6-discovery.md](references/phase-r3-r6-discovery.md)
- R8 → [references/phase-r8-evidence-contract.md](references/phase-r8-evidence-contract.md)
- R12 → [references/phase-r12-narrative.md](references/phase-r12-narrative.md)
- R7 / R10 / R13 → [references/phase-r7-r10-r13-assurance-repair-review.md](references/phase-r7-r10-r13-assurance-repair-review.md)
- R9 / R10 / R11 → [references/phase-r9-r11-experiment-loop.md](references/phase-r9-r11-experiment-loop.md)

### 0.2 锚点变更单（Anchor Change Order）

**适用：** 任何对**项目主锚点**或**任一路线锚点**的变更。项目主锚点的变更单落盘到
**根 `INDEX.md`**，路线锚点的变更单落盘到**该路线 `INDEX.md`**，各自有「锚点变更单」小节。

| 字段 | 内容 |
|---|---|
| **日期** | |
| **旧方向 → 新方向** | 例：`performance → theory` |
| **类型** | **增补**（主锚点不变，只调整路线侧重）/ **替换**（主锚点或路线主攻方向改变） |
| **依据** | **`增补`**：证据或用户指令均可。**`替换`：必须是「用户显式指令原话」** —— 证据只能作为**提请**的支撑材料，**不能**作为变更依据 |
| **受影响产物** | **替换时必填**：列出需重审、或标 `superseded` 的文档 ID（idea / 方案 / 叙事 / 审阅结论） |

**约束：**

1. **谁有权改锚点：只有用户。** 锚点变更单的**执行**必须由**用户显式指令**触发。
   agent **不得**以"我发现主锚点不可达""觉得另一个方向更有意思"为由**自行换方向、
   换项目主锚点、或新开路线**。在用户答复前，agent 能做且只能做两件事：
   - **提请：** 把"不可达"的证据写进根 `INDEX.md` 的 Warnings，并向用户明确提问；
   - **降级：** 按 §0.1 规则 3 把自己标成 `orthogonal` 并**公开**标注。
   **提请与降级是 agent 可做的；换方向不是。**
2. **`类型: 替换` 而没有「受影响产物」清单 = 变更单无效。**
   **`替换` 的依据不是用户原话 = 变更单同样无效。** 两者缺一，都不得据此改变产出方向。
3. **「必须服务」的强制力是「服务，否则降级 + 公开正交」，不是「服务，否则作废」。**
   即：答不出可证伪的 `serves` ⇒ 标 `orthogonal`，并在根 `INDEX.md` **公开写明**
   「不参与主锚点成功判据」，且不得进入 R12、不得作为投稿主线。
   **路线本身不被销毁** —— 它仍可继续产出，只是不参与主锚点的成功判据。
4. **append-only：** 不修改历史条目，后续变更追加新行。
5. **受影响产物必须在同一轮内被重审**，结论先写回 `research-state.json`，
   再投影到各自路线的 `STATUS.md`（状态）与 `INDEX.md`（材料）。

---

### 0.3 首次运行：Bootstrap 编排（**只观察，不干预**）

**结论：第一次在本项目调用本 Skill 时，只允许执行下面这一个 Bootstrap 序列；不得自动跑 `R3`—`R14`。**

```text
B0 Repo Intake              ─▶ 按 project-intake.md 盘点（已有信息不得重复询问）
B1 Existing Asset Discovery ─▶ 从已有代码 / 实验 / 文献 / 笔记中提取**真实**状态
B2 Minimal R0 Contract      ─▶ 只写 contract（+ 模板骨架，含 state_version: 0）
B3 Bootstrap R1             ─▶ 建 World Model 骨架（**必须稀疏**）
B4 R2 Field Snapshot        ─▶ 领域地图快照（**不做穷尽检索**）
B5 Initial Uncertainty Map  ─▶ 只在**有依据**时写 uncertainties[]
B6 Recommend Next Action    ─▶ 给出下一步建议，**然后停下等用户确认**
```

> **`first invocation = observe before intervene`。**
> 首次运行的价值在于**看清现状**，不在于推进研究。
> **B6 之后必须停** —— 由用户决定下一步跑哪些阶段（见 §0 的 `phase` 参数）。

**B3 的稀疏纪律（本序最重要的一条）：**

> **`State completeness is not a goal; grounded completeness is.`**
> **稀疏的真实状态优于编造的完整状态。**

| 类别 | 首次运行的态度 |
|---|---|
| `contract` / `literature` / 已观测的 `evidence` / 已知 `experiments` / 已知 `failures` | **积极填**（这些在项目里真实存在） |
| `claims` / `assumptions` / `uncertainties` | **谨慎提取**（须有原文 / 代码 / 数据支撑） |
| `hypotheses` / 未来 `experiments` | **不要为了完整而生成** —— 除非项目里**已经有**这些内容 |

**判据：** 首次运行结束时，**每一条 state 条目都必须能指回一个真实来源**
（文件、代码、数据、实验记录或用户原话）。**指不回去的条目 = 编造**，
必须删除，或改记为 `uncertainties[]`（`importance: medium`，说明"尚需确认"）。

> **反面模式（必须避免）：** 为了"看起来完整"而一口气生成 `claims 12 / evidence 30 /
> assumptions 15 / hypotheses 10` —— 其中大半是猜的。**那会让整份 World Model 失去可信度。**

**四个用户入口**（用户不需要知道 `R` 编号）：见
[references/invocation-prompts.md](references/invocation-prompts.md)。

---

## 1. 全局不变量（所有 R 阶段强制遵守）

以下六条是硬约束，任何 R 阶段都不得违反。执行前先确认，输出时自检。

### 1.1 文献检索：先尝试 web search，再本地与多源

```
Step 0: 先尝试 web search，打开论文、作者实现与官方资料
        记录查询与发现 URL，核验原始页面，再用标题、标识符和机制术语驱动后续检索
        工具不可用或失败 → 记录状态并继续；明确离线请求 → 跳过
Step 1: 搜索本地文献库（默认由 Zotero 本地 API 提供）
        地址：--zotero-url → 环境变量 ZOTERO_LOCAL_API → 默认 http://127.0.0.1:23119/api
        前置：Zotero `Settings → Advanced` 勾选
          「Allow other applications on this computer to communicate with Zotero」
        探测可达 → 用 Zotero（默认）；探测失败 → 自动回落 ./docs/refs/papers/*.json
        并打印警告，不失败；--local-format auto（默认）/ zotero（强制，不可用报错）/ refs（强制跳过 Zotero）
        命中 → 纳入结果，标注 sources=["local"] —— 但流程继续，不得在此返回
        ★ Zotero 是本地库的后端，provenance 仍是 local；源枚举 local|arxiv|openalex|crossref
          不变，不得把 Zotero 计入在线源
        ★ 端点、授权、错误码、附件协议见 references/zotero-local-api.md（按需读，不必每次加载）
Step 2: 调用全部启用源（arxiv / openalex / crossref）
        ★ 即使 Step 1 已命中，只要触发下述任一条件，本步必须执行
        ★ 单源失败【不终止】检索：该源标记 unavailable，其余源照常
        命中 → 拉取元数据与摘要，缓存到 docs/refs/cache/<source>/，标注 sources=[<source>]
Step 3: 信息不足 → 仅补充缺失字段，不重复拉取已有内容
Step 4: 饱和判定 → 未达饱和则扩大范围继续检索
```

**web search 的执行与来源纪律见 [literature-policy.md](references/literature-policy.md) §1.1。**
网页发现不替代多源核验。脚本不调用 web search，由 agent 前置执行。

**Zotero 能力与读写边界（要点；细节按需读 [zotero-local-api.md](references/zotero-local-api.md)）：**

| 能力 | 入口 | 默认语义 |
|---|---|---|
| 原生全文检索（第二层） | `literature_search.py --zotero-fulltext` | 只读；命中只能标 `indexed_fulltext` |
| PDF 页码级抽取 | `zotero_fulltext.py` | 只读；`page_verified` 只来自真实 PDF 页面 |
| 定向深读与证据锚点 | `zotero_deepread.py` | 只读 |
| 文献 CRUD / 标签 / 分类 / 笔记 | `zotero_crud.py` | **写需用户明确请求** |
| 删除文献 | `zotero_crud.delete_paper` | 默认 dry-run；Local API 的 DELETE 是**永久抹除** |

四个语义入口（`start-project` / `continue-research` / `explore` / `audit`）**只读**。
不得因为发现了一篇有价值的论文就自动改动真实 Zotero 库。
未授权时写操作抛错，**不得**静默改到 refs 后端写入。

**⚠️ 强制扩检触发条件（命中任一即必须查**全部启用源**并扩大范围）：**

| # | 触发条件 | 最低等级 |
|---|---|---|
| T1 | **创新性声明**（"首次提出 / 没人做过 / 首个 / 该方向空白"） | **L3 穷尽** |
| T2 | **理论不清**（证不出来、假设无法验证、收敛性说不清） | L2 强化 |
| T3 | **可行性不确定**（能不能做、资源够不够、是否已有不可能性结果） | L2 强化 |
| T4 | 新颖性判定（**R7 / R12 的 `S-Lit`**、R7 / R10 / R13 的 `S-Nov`） | **L3 穷尽**（**例外：R3—R6 的 §R3.7 概念级快筛 = L2**，只有写进文档的「首次提出」声称才回到 L3，见 §4 R3—R6） |
| T5 | 本地命中不足（< 用户下限，或 < 5 条） | L2 强化 |
| T6 | 用户要求"尽可能多 / 彻底查" | **L3 穷尽** |
| T7 | 任何将写进文档的"现有工作尚未……"式论断 | L2 强化 |
| T8 | 方法瓶颈：已观察到性能平台、候选反复失败，或诊断不再改变方法决定且缺少新干预 | L2 强化 |

**遇到卡点时第一动作是检索，不是硬推：** 理论说不清、证不出来、不确定能不能做时，
必须先检索 ① 该问题本身是否已有定理/反例/不可能性结果 ② 所用工具在其他领域的处理
③ **负结果文献**。方法瓶颈按 [literature-policy.md](references/literature-policy.md) §2.3 与 R5.1 补检索并交接方法干预。检索后仍无解，写入 `INDEX.md` 的 Warnings 并标注待核实。

**禁止推断：** 本地未命中 ≠ 不存在；arxiv 本轮未命中 ≠ 无人研究过；429 中断 ≠ 检索完整。
未完成 L3 前，文档中只能写 **"据本次检索未见（检索式见附录）"**，
**不得**使用"首次提出"。**证据等级与措辞的权威定义见
[evidence-policy.md](references/evidence-policy.md)。**

**429 处理：** 捕获限流错误后按指数退避等待 `10s → 20s → 40s → 80s → 160s`，
最多重试 5 次；**重试期间不得发起任何新的 arxiv 请求**；5 次后仍失败则返回本地
已有结果，标注"arxiv 暂时不可用，以下结果仅来自本地库"，**并在 INDEX.md 的 Warnings
记录"检索未达饱和"**。

**代理环境识别：** 发起 arxiv 请求前，先解析 `arxiv.org` / `export.arxiv.org`。
**若解析到本地 IP**（回环 / 私有网段 / 链路本地 / `0.0.0.0`，例如 Clash 的
`198.18.x.x` fake-IP），说明**可能存在代理环境**——DNS 已被 hosts 文件或本地代理
（Clash / Surge / 镜像站）接管，你访问的不是 arxiv 官方。此时必须：

1. 在报告中**单列「代理环境提示」段**，写明解析到的**具体 IP 与判定类型**；
2. **不得**据此判定"在线源不可用"或"无人在研究"（代理缓存/镜像可能不完整）；
3. 代理链路上的 **429 未必是 arxiv 官方限流**，退避照常执行但结论中必须注明该不确定性；
4. 若本次检索用于支撑创新性声明，把"经代理环境检索"记入 INDEX.md 的 **Warnings**。

> **只告警，不阻断。** 代理环境下的结果仍可用，但**可信度需重新评估**——更应依赖
> 饱和判据（连续两轮零新增）与负检索记录来支撑结论。

完整规范（含 L1/L2/L3 尽职调查等级、饱和判据与代理环境识别）见
[references/literature-policy.md](references/literature-policy.md)（§6.1），实现见
[scripts/literature_search.py](scripts/literature_search.py)。

### 1.2 顶会标准锚定

所有创新性判定必须引用 CVPR / ICML / NeurIPS / MICCAI 的具体标准；所有贡献必须标注类型
（General / Theory / Use-Inspired / Concept & Feasibility / Negative Results 或
方法 / 理论 / 实证 / 问题定义）。
标准全文见 [references/venue-standards.md](references/venue-standards.md)。

**审稿人评价的两角度 + 会议特性（强化）：** 四个会议审稿人
（R-CVPR / R-ICML / R-NeurIPS / R-MICCAI）**只用于 venue calibration 表**；
该校准表的**每一行**都必须同时给出：

> **作用域：** 本条**仅适用于 venue calibration 表**（R12 / R13）。**R12 已改用
> 攻击面审稿人**（见 §3 派遣表），会议审稿人只在 **R12 / R13 的 venue calibration** 中以校准表的
> 形式出现 —— 那里沿用「两角度 + 会议特性」的判据，但**不派子代理**。

1. **理论角度** —— 命题 / 假设 / 推导是否成立、形式化是否完整、理论贡献深度；
2. **应用角度** —— 能否落地、可验证性、影响面、与真实工作流的兼容性；
3. **会议特性判定** —— 按**本会议**首要标准给出一条显式判定，并引用
   [venue-standards.md](references/venue-standards.md) 的对应条目。

**三个都是必填；只写一个角度 = 评审不合格。** 两角度必须落到**具体命题 / 假设 /
实验 / 工作流环节**，不得用"理论没问题、应用有价值"充数。详见
[roles.md](references/roles.md) §1.0 与 [venue-standards.md](references/venue-standards.md) §0。

**创新性声明的额外约束（强化）：** 所有"首次提出"声称必须① 先完成 T1 的 **L3 穷尽
检索**，② 由 **S-Lit 核实**，必要时由 **S-Nov 独立复核**，③ 留存**负检索记录**
（检索式 + 命中数 + 为何不足以否定）。三项缺一，只能写"据本次检索未见"，
**不得**写"首次提出"。无法确认的标注 **"待核实"**。

### 1.3 输出规范

**形式（受控中文）：** 本节的每一条输出 —— 无论落到文档还是直接返回对话 —— 都遵守
[writing-policy.md](references/writing-policy.md)：**一句一动作、句长上限（默认档：指令 ≤25 字 /
说明 ≤40 字）、不用分号连接动作、一段一主题、≥3 项用列表**，并扫掉虚动词（「进行分析」→
「分析」）、套话（「需要注意的是」）、营销形容词（「无缝」「显著提升」）与同义轮换。
**默认档落盘前跑 `python scripts/ste_lint_zh.py --disable synonym-rotation <文件>`，
硬违规须为 0。**
**可选最强档 asd-ste100：** 用户显式声明时启用 —— 句长一律 ≤25 字、打开同义轮换、
建议类报告升为硬；命令改 `python scripts/ste_lint_zh.py --max-chars 25 <文件>`。
**Agent 不得自行升档**（见该政策 §1）。
**⚠️ 情态是内容：** 改写句子时**不得**把「可能 / 初步 / 倾向于」升成事实
（与 §1.1 的「禁止推断」同一条纪律）。

- 结构化报告，使用标题和表格。
- 所有引用给出具体出处，格式 `[作者, 会议/年份]`。
- 无法确认的信息标注 **"待核实"**，**不得臆造**。
  **证据等级 ↔ 允许/禁止表述的权威定义见
  [evidence-policy.md](references/evidence-policy.md)**（各 R 阶段 不再各自定义措辞）。
- 所有分析结论必须有文献依据或明确逻辑链。
- 每条"没做到 / 缺乏"必须关联**具体未建立的结构性质或未满足的理论条件**，
  禁止模糊表述。
- **返回对话时先给结论**，依据与推导放后面。

### 1.4 项目组织与文档落盘（所有 R 阶段强制）

**各路线产出的文档放该路线自己的 `routes/<R>/docs/`（扁平）；根目录 `docs/` 是跨路线共享区，
至少保证有 `refs/`。根目录有 `README.md` 与 `INDEX.md`；每条路线有 `README.md`、
`STATUS.md`、`INDEX.md` 三件套。**

```
<项目根目录>/
├── AGENTS.md              # 共享契约；存在则优先遵循
├── README.md              # ★ 根级：项目总览（研究问题、路线列表、怎么跑）
├── INDEX.md               # ★ 根级：路线总表投影（Route | Goal | Status | Thesis | Blocker）
├── docs/                  # ★ 跨路线共享区（不放路线文档）
│   ├── refs/              # ★ 必需：参考文献库 papers/ cache/<source>/ index.json
│   ├── decisions/         # ★ 项目级重大决策 DEC<NNN>-<slug>.md
│   ├── notes/             # 可选：跨路线共享笔记（按 AGENTS.md）
│   └── latex/             # 可选：跨路线共享 LaTeX（按 AGENTS.md）
├── routes/                # ★ 所有科研路线集中于此（DI-2）
│   └── A/
│       ├── README.md      # ★ 路线身份证：这条路线是什么（低频变更）
│       ├── STATUS.md      # ★ 当前状态人类摘要（research-state.json 的投影）
│       ├── INDEX.md       # ★ 资产目录 + 时间线（不再承载当前状态）
│       └── docs/          # ★ 本路线文档（扁平）
│           ├── A001-field-map.md
│           ├── A002-discovery.md
│           ├── A003-proposal.md
│           ├── A004-experiment-plan.md
│           ├── A005-narrative.md      # R12：一次调用一份，内含各 idea 小节
│           └── A003-review-r01.md     # 审阅挂被审 ID；零填充轮次
├── src/                   # ★ canonical implementation（唯一；route 不复制代码，DI-6）
├── configs/routes/A/      # route 之间的差异用 config 表达
├── experiments/A/<XID>/   # ★ 实验注册表：想做什么（pre-registration）
├── results/A/<XID>/       # ★ 观察到什么（observation）
├── shared/                # 极小：无法归入 src/docs/configs 的多路线资产
└── .research-idea-pipeline/routes/A/research-state.json   # 机器状态（不入 docs）
```

**八条硬性规则：**

1. **文档按路线分离、各自扁平：** 产出放 `routes/<R>/docs/`，**该目录内不再按类型分子目录**。
   **根 `docs/` 是跨路线共享区**——本 Skill **只保证 `refs/` 存在**，`notes/`、`latex/`
   等由项目与 `AGENTS.md` 决定。**唯一硬约束：路线文档不得放根 `docs/`。**
2. **路线级三文件职责分离（根级两文件）：** 根目录必须有 `README.md` 与 `INDEX.md`；
   每条路线必须有 `README.md` / `STATUS.md` / `INDEX.md`。三者回答不同问题、
   更新频率不同：

   | 文件 | 回答 | 更新频率 |
   |---|---|---|
   | `routes/<R>/README.md` | 这条路线**是什么**、为什么存在 | **很低** |
   | `routes/<R>/STATUS.md` | **现在做到哪、下一步是什么** | **很高** |
   | `routes/<R>/INDEX.md` | 这条路线**有哪些材料** | 中等 |

   **三者都是人类视图（DI-4），必须可从 `research-state.json` 投影。**
   **`STATUS.md` 由 `scripts/render_status.py` 生成，禁止手改。**
   **INDEX 不再承载 已证实 / 已证伪 / TODO / Bugs / Warnings；当前状态一律进 STATUS。**
   每次产出后更新所在路线的 `INDEX.md`（资产）；状态变化先写回 state，
   再重新生成 `STATUS.md`；跨路线层面的变化同步更新根 `INDEX.md`（路线总表投影）。
3. **文件名前缀 = 文档 ID**（不再是路径隔离）：前缀仍**必需** —— 审阅要挂靠、跨路线
   引用要唯一。序号按路线独立递增、**永不复用**。
   **文件名只能由 `<R><NNN>-<slug>.md` 决定，`slug` 只取
   [project-layout.md](references/project-layout.md) §2.1 表的封闭枚举。**
   实际路线必然产生枚举外的派生物（大纲、实验卡、数学合并、执行方案…）。它们
   **一律归到最接近的枚举 `slug`**，原始语义写 frontmatter 的**自由字段 `subtype:`**
   （**不参与文件名**），并在路线 `INDEX.md` 文档表加一列 `subtype`。
   **禁止自创 slug** —— 那会让"文件名可预测"这条保证失效，序号也会被派生物吃光。
4. **审阅挂被审 ID、轮次零填充：** `<被审ID>-review-r01.md`、`-r02.md`（**不占新序号**）。
   用 `-r<NN>` 是因为 `-review.md`/`-review-2.md` 在 `ls`/`sort` 下**轮次顺序是反的**。
   一轮覆盖多份文档时挂主文档 ID，其余写 frontmatter 的 `also_reviewed`。
5. **参考文献集中：** 论文元数据/笔记/缓存一律放 **`docs/refs/`**（脚本默认
   `--local-dir ./docs/refs`）；机器状态放 `.research-idea-pipeline/`，日志放 `logs/`
   ——**都不进 docs 正文**。
6. **PDF 必须入索引：** `docs/refs/` 下的每个 PDF 都要在 **`docs/refs/index.json`**
   里有一条记录（字段见 [literature-policy.md](references/literature-policy.md) §7.1）。
   **索引进版本库，PDF 不进**。新增/替换/删除 PDF 后**必须重建索引**
   （`python3 scripts/refs_index.py`，校验 `--check`）；**未入索引的 PDF 视为不存在**。
7. **落盘分三档，别把中间产物塞进 `docs/`：**

   | 档 | 落盘位置 | 例 |
   |---|---|---|
   | **交付物** | `routes/<R>/docs/`（扁平，不分子目录） | `anchor` / proposal / experiment-plan / narrative / review |
   | **中间产物** | `.research-idea-pipeline/routes/<R>/<被审ID>-r<NN>/` | 子代理**原始**评审件、草稿、检索原始结果 |
   | **机器状态** | `.research-idea-pipeline/routes/<R>/research-state.json` | **R1 常驻状态**（就地覆盖，不按阶段切分） |

   - 子代理的**原始评审件**属于**中间产物**：**不进 `docs/`**，也**不得**为了塞进去而在
     `routes/<R>/docs/` 下建子目录（该目录内不分子目录）。
   - **正式 review 必须自带摘要**（结论 + 评分 + 关键证据 + 交叉质询记录），放进 `docs/`。
   - **原始件不得被当作结论引用**——引用一律指向 review 正文（`<被审ID>-review-rNN.md`）。
   - 中间产物可随时删除；删掉不影响交付物的完整性（因为 review 自带摘要）。
8. **正文形式遵守受控中文：** 落盘**之前**跑
   `python scripts/ste_lint_zh.py --disable synonym-rotation <文件>`，**硬违规为 0**。
   档位按 [writing-policy.md](references/writing-policy.md) §1 判定
   （实验流程计划书的步骤与命令用 **Strict**，其余正文用**中文-顺**；
   **用户显式声明 asd-ste100 时改按该档执行** —— 命令换成
   `python scripts/ste_lint_zh.py --max-chars 25 <文件>`，且**不得自行升档**）。
   **⚠️ 不得为了过 linter 而删情态**（「可能 / 初步」是内容）。

> **slug 只能取：** `anchor` / `field-map` / `discovery` / `theory` / `evidence` /
> `proposal` / `experiment-plan` / `result-analysis` / `decision` / `narrative` / `review`。
> **R12 一次调用一份 `<R><NNN>-narrative.md`**（不再每个 idea 一份）。
> 完整规范见 [references/project-layout.md](references/project-layout.md)
> （含**八条 DI invariant**、三文件职责、`XID`、route fork 门槛、手工建骨架清单）。

---

### 1.5 推进纪律：理论建模是手段，不是终点（限制子代理行为）

> **禁止在「证明性工作」上停留与反复。** 数学理论的作用是**把问题建模清楚**，
> 据此找证据、提出方法、改进最终任务性能 —— **它不是交付物本身**。
> 这条规则同时约束**执行者**与**所有子代理**（尤其 S-Theory、R-ICML）。

**承重墙：可证伪的 central proposition（先于四步链）：**

> **任何 idea / 方案 / 投稿叙事，如果写不出一个明确、可证伪、且能对应到证据的
> central proposition，不得进入投稿叙事。**

七类论文各自的命题形态、`C0—C5` 的 claim graph、以及 `Ci ← Ej` 的证据对照写法，见
[claim-first-policy.md](references/claim-first-policy.md) §3 / §4。

> **旧规则的降级（重要）：** 「第二段必须给出机制性原因，写不出来叙事不成立」
> **不再是全局承重墙**，降级为**方法类 / 跨域类**的子规则。原因：研究实际走的是
> `Observation → Hypothesis → Experiment → Mechanism`，在方案阶段强迫写"根本原因"，
> 会把**待验证假设包装成已知原因**。判定承重墙的是**命题可否被证伪**，不是机制是否已知。

**四步链（每个 idea / 方案都必须走得通）：**

| 步 | 内容 | 产出 |
|---|---|---|
| 1 | **数学理论建模** | 形式化问题：变量、假设、目标、结构性质 |
| 2 | **寻找证据** | 文献证据 + 实验证据（不是"我觉得"） |
| 3 | **结合机器学习领域的方法提出方法**，并**明确标注方法来源** | 可执行的方法 / 算法 + `方法来源 = 原创 / 部分原创 / 迁移` |
| 4 | **改进最终任务性能** | 有可测指标与公平比较 |

**方法来源必须显式标注（原创 / 部分原创 / 迁移）：**

| 标注 | 含义 | 判据 |
|---|---|---|
| **原创** | 方法的核心机制由本工作提出，不来自既有工作 | 必须指出最接近先前工作，并说明**机制层面**的不同 |
| **部分原创** | 核心机制部分来自既有工作，但有关键改造 / 新组合 / 新性质 | 必须写明**改了哪一条**，以及改造带来的新性质 |
| **迁移** | 把其他领域 / 任务的既有方法搬过来，机制本身不变 | 必须写明**来源领域 + 迁移合法性依据**；**迁移本身不算增量** |

**标注的硬性要求：**

- 每个方法都必须标 —— R3—R6 的每个 idea、R8 的每条贡献、R12 的每套叙事。
  **不得留空，也不得模糊**（"受 X 启发"不是标注）。
- **迁移必须诚实标成迁移。** 把迁移包装成原创属于**夸大**，违反
  [phase-r12-narrative.md](references/phase-r12-narrative.md) §D4.4 的包装纪律
  （包装只允许改参照系，不允许改事实）。
- **迁移要成为贡献，必须证明迁移本身带来了新性质**（新的结构性质、理论条件或性能
  来源）。否则就只是"把 X 用到 Y 上" —— R3—R6 的反模式、R7 / R10 / R13 的**复现风险高**。
- 标注必须**可核验**：能指向具体的先前工作与具体的机制差异。

**明令禁止：**

- ❌ 反复打磨证明（"再证一遍"不是进度）
- ❌ 把"证不出来"当成阻塞 —— 应标注 **"待补证明"** 后**继续走第 2—4 步**
- ❌ 把贡献定位成"我们证明了 X"，却没有方法、没有可验证性能
- ❌ 在证明性工作上无限迭代而不产出可执行方法与实验

**证明预算（防止无限证明）：** 证明类工作必须设**显式预算**（时间或轮次上限）。
预算用尽仍未完成 → **标注"待补证明 · 待核实"，转入第 2—4 步**，并在 `INDEX.md`
的 TODO 里留下补证任务。**不得**因此阻塞整条链路。

**唯一例外（当且仅当《根 `INDEX.md`》声明的「项目主锚点」为「理论」或「负结果」时）：**
第 4 步改为「给出**可被实验检验的推论**或**可达到的松弛**」—— 此时"性能"指推论的
可检验性，不是 SOTA 指标。**但第 2、3 步仍然必须走通**：纯证明、无证据、无方法，
依然不成立。

> ⚠️ **例外的 key 是「项目主锚点」，不是路线自己的 `core_goal`。**
> **项目主锚点为「性能 / 基准 / 现象 / 可行性」时，本例外对任何路线都不生效**——
> **包括自称 `core_goal: theory` 的路线。** 这类路线可以不做实验，但必须给出
> **可检验的性能推论**，并指明**由谁执行、用什么指标、什么判据**。
> 路线想豁免，只能先走 §0.2 锚点变更单把**项目主锚点**改掉（只改路线 `core_goal`
> 不构成豁免）。

> ⚠️ **底线不变：** 本条约束的是**精力分配与停止条件**，不是诚实性。
> **不得**声称"已证明"却未完成证明；未完成的必须标 **"待补证明 · 待核实"**。

### 1.6 修复门：critical flaw ⇒ Research State 必须改变（所有 R 阶段强制）

> **检测到 critical flaw ⇒ Research State 必须改变。**
> **不允许**「reviewer 发现问题 → 写进 review → 流程结束」。

**一致性审计链（每轮强制）：** `Claim ↔ Method ↔ Code ↔ Result ↔ Conclusion`。

**处置枚举（只有这五个，逐字）：**
`REPAIR_CLAIM` | `RUN_TEST` | `FIX_IMPLEMENTATION` | `NARROW_SCOPE` | `KILL_BRANCH`

**关闭枚举（只有这两个，逐字）：** `RESOLVED` | `ACCEPTED_LIMITATION`

**落盘三元组（`state_check.py` V10 强制）：**

```jsonc
{"flaw":"C17 not supported","disposition":"RUN_TEST",
 "state_delta":"U3→X18 已排队；C17.status→partially-supported","closure":"RESOLVED"}
```

**硬规则：**

- 只写 `flaw` 而无 `disposition` 或 `state_delta` = **未闭环**；`closure` 为空 = 该轮**不得结束**。
- **`ACCEPTED_LIMITATION` 必须同时写进 `C.scope` 或 `C.known_flaws`** —— 否则那不是"接受"，只是"忽略"。
- **改 `claims[].status` 默认只能经 R10。** **唯一例外**：R8 挂证据时可做**证据驱动的单向升级**（`ungrounded` → `partially-supported` / `supported`）；**降级与否决**（`contradicted` / `killed`）**仍只能经 R10**。
  Discovery 与 Assurance 都不得直接改（防自己给自己判分）。
- **机制型 claim 必须做 regime shift 测试**：构造机制应成立的 `RS1` 与应失效的 `RS2`
  （**注意：`RS<n>` 是 regime-shift 条件，不是阶段号**）；两者结果近似 ⇒ 该机制 claim
  **降级为 `partially-supported`**。
- **artifact 审计的时机：** **R7 首轮**（R8 之前）没有 artifact，也**没有** `claims[].contract`，
  只能审 R3—R6 落盘的 seed `claims[]` / `hypotheses[]` / `assumptions[]`；
  **R7 第二轮起**才逐条核契约；**R8** 只能审自己刚建的契约与刚冻结的 `preregistration`（都是预测）。
  真正的 artifact-aware 审计绑在 **R9 之后 / R13**。**禁止在无 artifact 的阶段要求 artifact 审计。**

> 权威定义与字段映射见
> [phase-r9-r11-experiment-loop.md](references/phase-r9-r11-experiment-loop.md) 与
> [research-state-policy.md](references/research-state-policy.md) §4。

---

### 1.7 认识论权限边界：**R14 能杀研究分支，不能杀真理主张**（硬 invariant）

> **R14 can kill a research branch, but cannot kill a truth claim.**

**`claims[].status` 只能由证据（R8）或元认知修复（R10）改变。**
决策层（R14）**没有**认识论权限（epistemic authority）—— 这是本 Skill **绝不让步**的一条。

| R14 可以 | R14 不可以 |
|---|---|
| `hypotheses[].status` → `archived` / `killed`（停一个**研究分支**） | `claims[].status` → `killed` / `contradicted` |
| `decision` → `archive` / `pivot`（停一条**路线**） | 因为「不研究了」而让 `C5` 变成「假的」 |
| 关闭 `repairs[].closure` | 用 `decision` 反推 claim 的真值 |

**理由：** 研究者可以**决定不再研究**某个 claim，但「不再研究」是**资源决策**，不是**真值判决**。
若 R14 能写 `claims[].status`，它就获得了认识论权限，整个「claim 状态只能证据驱动变化」
的结构性防错**当场失效**。

**正确写法：**

```text
H7.status  = archived      （分支停掉）
decision   = archive       （路线停掉）
C5.status  = Supported     ← 保持不动，不因"停研究"而降级
```

**机械体现：** R14 的写集合**不含** `claims[].status`（三方读写表逐字一致，
[research-state-policy.md](references/research-state-policy.md) §5 与 §5.0）；
`killed` 只能经 R10 的 `state_delta`。

> 本条与 §1.6（critical flaw ⇒ state 必须改变）配对：**§1.6 要求该变的必须变，
> §1.7 要求不该变的绝不许变。**

---

### 1.8 认知记忆：跨会话恢复科学理解（Cognitive Insight Engine）

> **记录事实 ≠ 积累理解。** Research State 回答「我们目前认为世界是什么样」；
> 认知记忆回答「我们持有哪些机制、它们如何被证据改写、下一位执行者必须先恢复什么」。

**定位：** 它是**已有系统的认知增强层**，不是第 16 个阶段，不是第九类一等对象，
也不是第二份事实来源。权威定义见
[cognitive-memory-policy.md](references/cognitive-memory-policy.md)。

**三层，一个方向：**

```text
Canonical  .research-idea-pipeline/routes/<R>/research-state.json   ← 唯一权威
Event      .research-idea-pipeline/routes/<R>/cognition/model-revisions.jsonl
           结构断言 + canonical 指针，append-only                  ← 不承载支持度
Derived    .research-idea-pipeline/routes/<R>/cognition/index.json
           .research-idea-pipeline/routes/<R>/cognition/context-brief.md
           可由前两层重建                                         ← 永不是权威
```

**四条硬边界（违反即与 §1.6 / §1.7 冲突）：**

1. **支持度是算出来的，不是声明的。** 机制的支持等级由 canonical 事实推出
   （`speculative` / `hypothesis` / `literature_supported` / `experiment_supported` /
   `refuted`）。修订事件**不得**声明 `epistemic_status`、支持等级或 Claim 状态（`CM2`）；
   自评只被记成冲突（`CM7`），不被采用。
2. **认知记忆不写 canonical。** 它不写 `claims[].status`、不写 `contract`、不写锚点、
   不写 `evidence[]` / `failures[]`。构建前后对 `research-state.json` 做字节比对（`CM0`）。
3. **失效即过期。** 引用的证据或对象 `validity` 变成 `stale` / `invalid` / `pending` 时，
   派生条目自动标记过期、退出 hot memory，并保留原因；不补写推测。
4. **记忆不等于事实。** 每条机制必须带支持等级、适用范围与来源引用。Context Brief
   不得把推测写成结论。

**记忆生命周期：** `Recall → Reason → Test → Revise → Consolidate → Recall`。
每次启动先恢复：研究契约与目标 / 仍有效的机制 / 未解释异常 / 被否证机制及其边界 /
未完成的机制竞争 / 上一轮决策与未完成操作。**三级加载，不得无差别注入全部历史：**

| 层 | 内容 | 选择依据 |
|---|---|---|
| **Hot** | 与当前焦点挂钩的机制、高重要度未复现异常、开放竞争、失败约束、上一轮决策 | 引用与焦点集相交 |
| **Warm** | 被否证 / 被削弱的机制与相关历史 | 非 hot，但有支持理由 |
| **Cold** | 其余一切，含全部过期条目 | 只给 id 与过期原因 |

焦点集取自 canonical：`open` 且 `importance ∈ {critical, high}` 的 `U` 及其判别测试、
存活的 `C`、`planned` / `running` 的 `X`、存活候选、`ACCEPTED_LIMITATION` 的 `repairs[].targets`。
另有去重（同一 canonical 锚点集合 = 实质等价解释，`CM9`）、来源引用、版本检查和
上下文预算（`--budget`，默认 6000 字符，截断必须显式标注）。

**读写协议（逐阶段）：** R3—R6 写 `mechanism_*` / `competition_*` 并读策略先验；
R8 写 `prediction_freeze`；R9.O 写 `anomaly_record` / `prediction_assessment`；
R10 写 `mechanism_refute` / `mechanism_weaken` / `mechanism_reactivate`；
R11 写 `mechanism_merge` / `mechanism_revise` 后重建；R12 / R13 **只读**（叙事与审阅是
state 的视图）；R14 只读 Context Brief。详见该政策 §8。

**机械闸门 `CM1`—`CM10`**（与 `S`/`V` 命名空间分离，`C` 不与 Claim 前缀冲突）：

```sh
python3 scripts/cognition.py build --state .research-idea-pipeline/routes/<R>/research-state.json
python3 scripts/cognition.py check --state .research-idea-pipeline/routes/<R>/research-state.json
python3 scripts/cognition.py brief --state .research-idea-pipeline/routes/<R>/research-state.json --budget 4000
```

退出码同仓库约定：`0` 通过 / `1` 参数错误 / `3` 硬违规 / `4` 环境不满足。
**不新增 state 槽位**：S1—S7 / V1—V24、state 模板与 `state_check.py` 一律不变。

**预测必须可判定（Phase 2）。** `preregistration.outcomes[].criterion` 把「什么算预测成立」
在冻结时写成机器可读判据（`quantitative` / `directional` / `discrete`）。
没有判据的结果只能返回 `UNTESTABLE`，**不得宣告预测成立或失败**；
执行无效只能返回 `INVALID_EXECUTION`，不是异常；没有预注册的观察只能是
`EXPLORATORY_ANOMALY`。

**冻结的 `outcomes[]` 是完整判定集合**：观测包是「关于它」的证据，不是「要判定哪些结果」的
清单。只提交一部分只能得到 `PARTIALLY_ASSESSED`，**永远不能读成「全部预测成立」**；
`execution.validity=UNKNOWN` 时比较结果保留在 `diagnostic_outcome_class`，
但**不占据科学判定栏**、不是合格证据，也不得触发 R10/R11 状态迁移
（`evidence_transition_allowed`）。

**互斥分支必须由预注册打开，不能由观测包声明。** 只有在冻结时写入
`outcome_mode: "branch"` + `branch_rule`（`selector` / `quantity` / `branches` 完整划分），
且分支判据**可证互斥**时，比较器才进入 branch mode；所选分支由冻结规则作用于**原始观测**
导出，packet 里的 `observed_outcome` 只是必须与之一致的声明。未声明 mode 的预注册一律按
completeness 判定（旧项目无需迁移）；分支规则缺失、冲突、不可验证或事后追加时，
**不得产生 `PREDICTION_HELD`**，未选分支也要以可核验的排除条件记录（`PC10`）。

**证据资格只有一个入口。** `qualify_evidence` 的 `PQ1`—`PQ8` 同时检查执行有效性、
预注册冻结与判据形状、判定集合完整性或合法 branch mode、观测来源绑定（
`{kind, location, content, digest}` 且 `digest == digest(content)`）、分支选择的可追溯性、
实验与预测绑定、终态收据、时间顺序与事后篡改。**任何一项不过就 fail closed**
（`evidence_eligible: false`）：不得标记 `QUALIFIED_EVIDENCE`、不得授权 Claim 状态升级、
不得用于机制否证或 Insight 认证；诊断性比较照常保留。Insight 只有绑定到**具体预测**、
具有合格判定、方向一致的证据与**已通过**的结构等价审计时才能成为
`evidence_supported_insight`（`PC11`）。

机制竞争必须逐对检验**可比性 → 冲突 → 分辨率 → 预先声明的判别规则**：
不同观测变量、不同测量口径、区间重叠、`noise/√n` 吃掉间隔、间隔小于 `min_separation`、
没有 `discrimination_rule`，**都不能算可区分**。判别干预必须可执行（`planned` / `running`）。
只有 `DISTINGUISHABLE` / `CONDITIONALLY_DISTINGUISHABLE` / `NOT_DISTINGUISHABLE` /
`INSUFFICIENT_INFORMATION` 四值，且**不接受文本相似度或 LLM 自评分**。行为切换与
Insight Card 规则见
[prediction-anomaly-competition.md](references/prediction-anomaly-competition.md)。

**科学价值不等于 EIG（Phase 3）。** 研究候选的**决策价值**与**发现潜力**分开判断，
每个维度都带 canonical 依据与不确定性，**没有总分**（`SV1` 拒绝任何聚合分数）。
科学品味分成**用户所有**（`contract`，agent 只读）与**证据校准**（从真实结果归纳，
可修订）两部分；自动学习**只影响探索建议**，不得改锚点（`SV3`）。
探索策略复用既有 `P1`—`P6` / `local` 与 QD archive：算子只能 `encouraged` /
`neutral` / `discouraged` / `dormant`，**没有永久封禁**，降级必须有范围与重启条件，
且至少两次独立失败（`SV5`）。规则见
[scientific-value-adaptive-discovery.md](references/scientific-value-adaptive-discovery.md)。

---

### 1.9 旧项目接管：Legacy Research Handoff

> **已有 canonical `research-state.json` ＝ 已初始化项目。** 载入新版 Skill **不是**新项目，
> **不得跑全新 Bootstrap（`B0`—`B6`）**。

入口**仍然是 `continue-research`**（只有四个入口，接管不新增第五个）。
首次接管执行**只读**兼容性审计并重建认知记忆：

```sh
python3 scripts/legacy_handoff.py detect --state .research-idea-pipeline/routes/<R>/research-state.json
python3 scripts/legacy_handoff.py take   --state .research-idea-pipeline/routes/<R>/research-state.json
```

**五条硬约束：**

1. **不重置** `state_version` / `claims[].status` / `evidence` / 实验 ID / 锚点 /
   诊断预算 / 历史决策；`research-state.json`、`scheduler.json` 与 `.execution` ledger
   在接管前后**逐字节相同**。
2. **不补造历史。** 历史上没有预注册的终态实验是**阻塞级兼容性错误**（`LH7`），
   不得事后补一份冻结预测；没有可判定判据的冻结结果标 `retrospective`，
   契约 / 失败条件 / 文档缺失标 `unknown`。
3. **可从 canonical 重建认知记忆**：机制 / 异常 / 竞争 / 失效边界全部由 `claims[]` /
   `hypotheses[]` / `experiments[]` / `failures[]` 投影得到，每条带
   `origin: legacy_derivation` + `retrospective: true`，并在 Context Brief 标
   `[RETROSPECTIVE]`。有修订记录覆盖同一对象时，重建条目自动让位。
4. **严重兼容性错误一律不写回**（退出码 3，什么都不写），
   **不得通过重建一份新 Research State 绕过问题**。`LH1`—`LH16` 见
   [legacy-handoff.md](references/legacy-handoff.md)。
5. **可重复、可追溯、可回滚。** 同样输入产出逐字节相同的文件；第二次接管只报
   `already_initialized`；`rollback` 只删本层创建的文件，遇到未知文件即拒绝。

接管产生 `cognition/handoff-report.md`（已恢复 / 未恢复 / 重要机制 / 未解异常 /
禁止重复方向 / 进行中实验 / 下一条有价值动作）。接管后进入正常 `continue-research`，
默认读取 `cognition/context-brief.md`，**不需要用户指定记忆文件**。

**发现能力必须可验证（Phase 4）。** 历史回放用**当时可见的信息**重放一次研究决策，
再拿系统从未见过的隐藏答案评分：七个维度**各自独立**，**不做加权总分**；
`null` 表示该 case 不可评，不得当作 0。消融四个 arm（baseline / memory_only /
memory_prediction / full_cie）只报实测值与不确定性，**样本不足时明确声明不得宣称提升**；
两个 arm 在所有维度上无法区分时也要写明。novelty **只认独立标签或文献近邻**，
agent 自评被拒绝。回放前必须证明隐藏信息不可达（`RP2`）。
规则见 [discovery-replay.md](references/discovery-replay.md)。

```sh
python3 scripts/research_replay.py suite --dir examples/replay/adversarial --runs 2
python3 scripts/research_replay.py smoke --work /tmp/cie-smoke
```

---

## 2. 共享资源索引

| 资源 | 位置 | 内容 |
|---|---|---|
| 子代理角色库 | [references/roles.md](references/roles.md) | 会议审稿人 R-CVPR / R-ICML / R-NeurIPS / **R-MICCAI**（**仅 venue calibration 用，不参与科学发现**）；**攻击面审稿人 R-Novelty / R-Causal / R-Experimental / R-Theory / R-Generalization / R-Utility**；A-Author / A-Experimenter；S-Lit / S-Nov / S-Theory / S-Feas / S-Devil / S-Repro / **S-Integrity** |
| 顶会创新性标准 | [references/venue-standards.md](references/venue-standards.md) | CVPR / ICML / NeurIPS / MICCAI 四视角锚定标准 + 防复现标准 |
| 叙事 preset 库 | [references/narrative-patterns.md](references/narrative-patterns.md) | **十套叙事 preset（N1—N10，非互斥、非创新等级）**、**(O,T,R) + anchor 选 preset**、**六槽位 S1—S6**、跨域 **Transfer Legitimacy Argument（L1/L2/L3）**、禁用表述、叙事自检 |
| Rhetorical Realization | [references/rhetorical-operators.md](references/rhetorical-operators.md)、[references/rhetoric-equivalence-policy.md](references/rhetoric-equivalence-policy.md) | D4a 科学 hierarchy 与 D4b 表达搜索分离；冻结 14 项、RE1–RE5、盲恢复与配对敏感性；不优化 reviewer overall score |
| Realization 工具与模板 | [scripts/rhetorical_realization.py](scripts/rhetorical_realization.py)、[scripts/validate_rhetorical_variant.py](scripts/validate_rhetorical_variant.py)、[templates/narrative-realization.md](templates/narrative-realization.md) | 有界生成、来源绑定、实际正文 gate、blind payload、恢复比较、多模型面板；独立 artifact，不迁移 State schema |
| **Claim-first 政策** | [references/claim-first-policy.md](references/claim-first-policy.md) | **R12 现行（P0）**：总纲公式（`Claim strength × Evidence alignment × Reviewer comprehensibility`）、**证据台账 `epistemic_status`**、**Claim Graph `C0—C5` + `Ci ← Ej`**、**可证伪 central proposition**、**`(O,T,R)` 三轴**、**Anchor Eligibility Test**。**R3—R6 / R8 / R7 / R10 / R13 的接入登记为 P1**（见 `docs/claim-first-spec.md` §9） |
| 文献检索规范 | [references/literature-policy.md](references/literature-policy.md) | 禁止只停留在本地、T1—T8 强制扩检、L1/L2/L3 尽职调查、饱和判据、429 退避、代理环境识别、缓存 |
| 项目组织规范 | [references/project-layout.md](references/project-layout.md) | **Wave 6 目录规范**：**八条 DI invariant**、`routes/` 聚合、**`README`/`STATUS`/`INDEX` 三文件职责分离**、**`STATUS.md = f(research-state.json)` 投影**、`XID` 贯穿、`experiments/` 与 `results/` 分离、`docs/decisions/DEC`、**三层锚点体系落盘**（`anchor_role`/`serves`）、`docs/` 命名与 `slug` 封闭枚举 + `subtype`、**落盘三档**（交付物/中间产物/状态）、锚点变更单、route fork 门槛、Git 边界、`AGENTS.md` 优先与可达性校验、并发写入 |
| 评分与聚合政策 | [references/scoring-policy.md](references/scoring-policy.md) | **两层**：**硬门禁 `G1—G5`（不聚合、不打分）** + **排序六维**（**R12 主用**）；1—5 标尺；极性归一化（**仅 R7 / R10 / R13 仍用**）；逐维度中位数、**一票否决 + 带条件的推荐出口** |
| 证据等级与措辞 | [references/evidence-policy.md](references/evidence-policy.md) | **五类共享政策**：已核实 / 部分核实 / 据本次检索未见 / 待核实 / 待补证明 ↔ 允许与禁止表述；**§3 认知状态 ↔ 措辞等级映射**（各 R 阶段 不再各自定义） |
| 受控中文写作 | [references/writing-policy.md](references/writing-policy.md) | **落盘文档 / 对话返回 / 子代理意见共用**：三档 **asd-ste100（可选最强档，须用户显式声明）/ Strict / 中文-顺**、结构规则（硬）、词汇规则（方向；asd-ste100 档下升为执行）、中文六种机器味、**情态是内容** |
| 受控中文 linter | [scripts/ste_lint_zh.py](scripts/ste_lint_zh.py) | 机械首查：分号 / 超长句 / 虚动词 / 营销词 / 套话 / 同义轮换 / 被动 / 复合体貌 / 含糊词 / 半角标点；`--baseline`、`--disable`、`--selftest`（MIT，vendored） |
| 检索实现脚本 | [scripts/literature_search.py](scripts/literature_search.py) | 可运行实现：**本地 + 多源**并集、每源状态、`--level`、`--exhaustive`、`--also-query`、`--venue`、`--cited-by`、退避、代理检测、`--check-env` |
| 多源适配器 | [scripts/literature_sources.py](scripts/literature_sources.py) | arxiv（新）/ openalex（关系）/ crossref（出处）+ 跨源合并层 |
| 环境自检脚本 | [scripts/env_probe.py](scripts/env_probe.py) | 发现工作解释器（已激活环境 → 项目 `.venv` → conda → PATH）；依赖缺失时退出码 4 |
| 离线测试 | [scripts/test_literature_search.py](scripts/test_literature_search.py) | stdlib unittest，全离线（环境发现 / 跨源合并 / 等级判定） |
| PDF 索引脚本 | [scripts/refs_index.py](scripts/refs_index.py) | 为 `docs/refs/` 下每个 PDF 建 `index.json` 条目；`--check` 校验（不一致退出码 3）、**`--migrate` 旧 schema 迁移（保留旧字段）** |
| 索引迁移测试 | [scripts/test_refs_index.py](scripts/test_refs_index.py) | 离线测试：三种旧索引形状的迁移、「保留旧字段」、`--check` 退出码与提示 |
| **Research World Model 政策** | [references/research-state-policy.md](references/research-state-policy.md) | **R1 权威**：八类一等对象（`C`/`E`/`AS`/`H`/`X`/`LIT`/`F`/`U`）+ `contract`、逐阶段读写时机、**Shape Gate S1—S7** 与 **V1—V24** |
| **World Model 模板** | [templates/research-state.template.json](templates/research-state.template.json) | R1 常驻骨架（顶层直接是各对象数组）；**模板自身必须通过 S1—S7 与 V1—V24** |
| **状态校验脚本** | [scripts/state_check.py](scripts/state_check.py) | **机械闸门**：**Shape Gate `S1—S7`**（在 V1—V24 之前跑）**+ 引用完整性 `V1—V24`**；`--check` / `--json` / `--selftest` / `--list-rules`；退出码 0 通过 / 3 硬违规（含形状）/ 4 环境 |
| 状态校验测试 | [scripts/test_state_check.py](scripts/test_state_check.py) | 离线测试：S1—S7 与 V1—V24 各有反例 + 退出码行为 + 表格/契约键一致性 |
| **存量项目接管** | [references/project-intake.md](references/project-intake.md) | 在**已有代码 / 实验 / 文献 / 结论**的项目里启动本 Skill 时的接管清单：9 个盘点维度、落盘映射、集中提问上限 |
| **调用契约（四个用户入口）** | [references/invocation-prompts.md](references/invocation-prompts.md) | `start-project` / `continue-research` / `explore` / `audit`：固定用户调用契约，**用户不需要知道 `R` 编号**；防止实际使用时绕过新哲学（一上手就发散、编造状态） |
| **跨阶段调度（Meta-Controller）** | [references/scheduler-policy.md](references/scheduler-policy.md) | `R0`—`R14` 是**能力**不是 workflow：八级 `next_action_policy` + `EIG ÷ cost`；telemetry 落 [scheduler.template.json](templates/scheduler.template.json)，**不进 state** |
| **Structural Equivalence 政策** | [references/structural-equivalence-policy.md](references/structural-equivalence-policy.md) | **跨阶段保证服务（不是第 16 个阶段）**：canonical scientific structure（十四个 facet + 十一个 typed relation）、domain-aware / domain-stripped 两套表示、load-bearing delta、Counterfactual Collapse Test、verdict 十值（含 `paradigm-candidate`）、audit artifact 契约、SENA-1（R7）/ SENA-2（R13）、无 score 纪律、`EQ1`—`EQ13` 机械闸门；**§15 起为 near-neighbor 判断层**：`near_neighbor_verdict` 八值、Preserved Core / Structural Delta、Local Neighborhood Test、Removal Test、Theory-Stripping（P5）、Structure-Preservation（P4）、provenance 四值 + 三值 relation、Null Hypothesis + Minimal Delta、claim-strength gate（不是 idea-kill）、population telemetry、对称不确定性闸门（未知证据既不膨胀也不塌缩）、禁 scalar 决定 novelty、`NN1`—`NN14` |
| **Structural Equivalence 模板** | [templates/structural-equivalence-audit.template.json](templates/structural-equivalence-audit.template.json) | Minimal Structural Delta Certificate 骨架（schema `@2` = §8 基础键 + §24 near-neighbor 必填键）；**模板自身必须通过 artifact 侧 `EQ4`—`EQ13` 与 `NN1`—`NN14`**（`--route` 侧的 `EQ1` / `EQ2` / `EQ3` / `EQ12` 需要真实 state，模板不跑） |
| **Structural Equivalence 检查器** | [scripts/structural_equivalence_check.py](scripts/structural_equivalence_check.py) | **机械闸门**：只查「审计做没做完整 / 引用是否存在 / schema 是否满足 / claim 强弱是否与 verdict 或 near_neighbor_verdict 相容」，**不宣判 novelty**，**不决定 H 与 P 是否结构等价**；两层规则 `EQ1`—`EQ13` + `NN1`—`NN14`；`--artifact` / `--route` / `--selftest` / `--list-rules`；退出码 0 / 1 / 3 / 4 |
| 路线级索引模板 | [templates/INDEX.md](templates/INDEX.md) | `routes/<R>/INDEX.md` 骨架（**资产目录 + 时间线**：Route Overview / Key Documents / Experiments / Decisions / Reviews / Milestones / Recent Research Changes / Archive；**不含已证实/已证伪/TODO/Bugs/Warnings**） |
| 路线级状态模板 | [templates/STATUS.md](templates/STATUS.md) | `routes/<R>/STATUS.md` 骨架（`research-state.json` 的投影；**由 `render_status.py` 生成**） |
| 根级索引模板 | [templates/INDEX.root.md](templates/INDEX.root.md) | 根 `INDEX.md` 骨架（**路线总表投影**：`Route | Goal | Status | Thesis | Blocker` + 项目主锚点声明 + 全局 Warnings） |
| 路线级说明模板 | [templates/README.route.md](templates/README.route.md) | `routes/<R>/README.md` 骨架（**路线身份证**：Research Question / Why / Relation / Thesis / Scope / Lineage / Resources / Entry points） |
| 串联示例 | [examples/](examples/) | 主链路串联（`R3—R6 → R8 → R12 → R7`）、接续复核、单独文献调研、多路线目录管理的示例；**受控中文两档对照（asd-ste100 改写样例）见 [example-writing-tier.md](examples/example-writing-tier.md)** |
| **认知记忆政策（CIE Phase 1）** | [references/cognitive-memory-policy.md](references/cognitive-memory-policy.md) | 四类认知记忆（机制 / 异常 / 竞争 / 科学价值）、三层权威边界、支持等级推导阶梯、`CM1`—`CM10` 规则（`CM7`—`CM10` 为 warning，不翻转退出码）、记忆生命周期与 hot/warm/cold 加载、写入禁止项 |
| **认知记忆脚本** | [scripts/cognition.py](scripts/cognition.py) | Memory Builder + Validator + Recall / Context Brief；`build` / `check` / `brief` / `recall` / `--selftest` / `--list-kinds`；**只读 canonical，从不写 `research-state.json`** |
| 认知记忆测试与示例 | [scripts/test_cognition.py](scripts/test_cognition.py)、[examples/cognition/](examples/cognition/README.md) | 离线测试（兼容性 / 可重建性 / 支持度推导 / 写入禁止 / 失效过滤 / CLI / fixture）+ 合成 fixture（**不是真实科研证据**） |
| **预测 / 异常 / 机制竞争（CIE Phase 2）** | [references/prediction-anomaly-competition.md](references/prediction-anomaly-competition.md) | 可判定判据 `criterion`、**冻结的 branch mode**（`outcome_mode`/`branch_rule`）、观测包来源绑定、七类结果、**统一证据资格门（`PQ1`—`PQ8`，fail closed）**、竞争区分力、诊断→干预行为切换、Insight Card 与**按预测逐个绑定**的认证；规则 `PC1`—`PC11`；**不得自我认证创新性** |
| **预测比较器脚本** | [scripts/prediction_compare.py](scripts/prediction_compare.py) | `freeze` / `compare` / `compete` / `switch` / `insight` / `--selftest`；判据形状、来源绑定、冻结完整性（`PC4`/`PC5`）、分支规则（`PC10`）、**唯一证据资格入口 `qualify_evidence`**、Insight 证据绑定（`PC11`）、区分力与行为切换 |
| **旧项目接管（Legacy Handoff）** | [references/legacy-handoff.md](references/legacy-handoff.md)、[scripts/legacy_handoff.py](scripts/legacy_handoff.py) | 已初始化项目**禁止重新 Bootstrap**；只读兼容性审计 `LH1`—`LH16`、`canonical` 无损、重建认知记忆、`unknown`/`retrospective` 标注、接管报告、幂等与回滚；**严重错误阻止写回** |
| 接管回归测试 | [scripts/test_legacy_handoff.py](scripts/test_legacy_handoff.py) | 无损接管 / 跨会话重启 / 重复接管 / 缺失历史 / 失效传播 / 预测时间泄漏 / 多路线隔离 / 下一轮复用旧知识 / 严重错误阻止写回 |
| **科学价值与自适应发现（CIE Phase 3）** | [references/scientific-value-adaptive-discovery.md](references/scientific-value-adaptive-discovery.md) | Decision Value / Discovery Potential 分维判断（**无总分**，`SV1`—`SV8`）、Taste Memory 双层权限、八种探索菜单到既有算子的映射、防锁死规则、`P4` 上下文隔离 |
| **策略记忆脚本** | [scripts/strategy_memory.py](scripts/strategy_memory.py) | `value` / `taste` / `operators` / `recommend` / `apply` / `validate`；字典序排序（无权重）、探索下限、算子重启条件；**scheduler.json 只读** |
| **历史回放与验证（CIE Phase 4）** | [references/discovery-replay.md](references/discovery-replay.md) | replay case schema、隐藏信息泄漏防护（`RP2`）、七维独立指标、四 arm 消融、十四个对抗 case、端到端 smoke；**未做真实 Agent A/B** |
| **回放脚本与 fixture** | [scripts/research_replay.py](scripts/research_replay.py)、[examples/replay/](examples/replay/README.md) | `validate` / `show` / `run` / `suite` / `ablate` / `adversarial` / `smoke`；可插拔 `--runner module:function`；fixture 为**合成**，不是真实科研证据 |

---

## 3. 子代理派遣总览

> **派遣前先定「派遣方式」（§3.1）：Team 还是默认子代理。** 方式未定不得开始派遣。

所有 R 阶段共享同一角色库。按阶段需派遣的子代理如下（角色定义不重复，见
[references/roles.md](references/roles.md)）：

| R 阶段 | 派遣子代理 |
|---|---|
| **R2 / R5** | 无（执行者直接完成检索与归纳） |
| **R3—R6** | **候选由隔离 Exploration Agents 按 island 生成**：`P1`—`P6` 各一个独立上下文（**互不可见**），另加 `local`；执行者只做编排、隔离、路由、汇总与写 state，**不得亲自补写候选**。generation 完成后才由 `S-Lit` + `R-Novelty` + `R-Causal` + `S-Feas` 做 concept 级 hygiene 快筛，`S-Devil` 出致命反驳。**不派 venue 角色**；**不派 S-Repro**。详见 [phase-r3-r6-discovery.md](references/phase-r3-r6-discovery.md) §R3.3—§R3.6 |
| **R8** | 证据契约与 `proposal.md` 由 `A-Author` / `A-Experimenter` 落盘；核实由 `R-Theory` / `S-Theory` / `S-Feas`（常规）+ **R7 的 `S-Lit` 结论（不重做 L3）**；`S-Nov` 按需。**venue 角色不派**，**不派 `S-Repro`**，**不派六个攻击面审稿人** |
| **R12** | **攻击面审核（六人全部派遣、不得裁减）**：R-Novelty、R-Causal、R-Experimental、R-Theory、R-Generalization、R-Utility；**S-Lit 恒派**（L3 穷尽 + 负检索记录）；**S-Devil 不打分**（只出致命弱点清单 + 最简解释反例，喂 `G3`/`G4`）；按需 **S-Nov / S-Feas / S-Repro**。会议审稿人**不派**，只在 **R12 / R13 的 venue calibration** 中以校准表出现 |
| **R7 / R10 / R13** | **R7 按八个攻击面派遣算子**：`S-Lit`（最近工作碰撞）+ `R-Novelty`、`R-Causal`（更简单解释）、`R-Experimental`（识别 + 统计两读数）、`R-Theory`、`R-Generalization`（scope）、`S-Repro`（实现与可复现）、**`S-Integrity`（完整性，R13 生效）**；`S-Feas` 按需。**venue 角色**（见 [roles.md](references/roles.md) §1）**不参与科学发现**，只在 R12/R13 的校准表里出现。 |

**职责边界：** 不派遣 S-Repro 到 R3—R6（idea 阶段无代码可复现）；**§R3.7 的审核是
概念级快筛**，不要与 R7 / R10 / R13 的方案级深审重复。详见
[phase-r3-r6-discovery.md](references/phase-r3-r6-discovery.md) §R3—R6.0 与
[phase-r7-r10-r13-assurance-repair-review.md](references/phase-r7-r10-r13-assurance-repair-review.md) §R7.0。

**派遣原则：** 子代理必须**独立产出**，不得互相抄袭结论；汇总时去重并保留来源标注。
**R12 与 R7 / R10 / R13 都要求交叉质询**：每个子代理对其余子代理的评分提出至少一条质疑或补充。

**聚合规则分两套**（权威定义见 [scoring-policy.md](references/scoring-policy.md)）：

- **R12：先过硬门禁 `G1—G5`**（任一 `fail` ⇒ `not_submission_ready`，**不参与排序**），
  再按**六个同向维度**排序，**不做极性归一化**（D 已无反向维度）。
- **R7 / R10 / R13：仍按极性归一化后的逐维度中位数聚合** —— 含 S-Devil 的**反向维度**，
  定义见 [scoring-policy.md](references/scoring-policy.md) §2 与 §5（本文件不复述公式，
  避免同一规则两份写法）。

> ⚠️ **不得用「6 个子代理都同意」声称 reviewer consensus** —— 六个 reviewer **不是独立
> 样本**（同一基础模型换 prompt，`corr ≫ 0`）。见 [scoring-policy.md](references/scoring-policy.md) §3。

### 3.1 派遣方式：Team 优先询问（强制）

**每次准备派发子代理前，先判断当前环境是否具备 Team 能力**（能创建持久、可被寻址的
teammate，例如 Agent Teams）。然后按三种情形处理：

| # | 情形 | 处理 |
|---|---|---|
| 1 | **环境具备 Team 能力** | **必须先询问用户是否使用 Team**，不得自行决定。用户要求用 → **用 Team**；用户不要或未表态 → 用默认子代理 |
| 2 | **环境不具备 Team 能力，用户也没提** | 用**默认子代理**，无需询问 |
| 3 | **用户显式要求用 Team，但环境不具备该能力** | **回退到默认子代理**，并**明确告知用户"当前环境无 Team 能力，已回退"** |

**硬约束：**

- **不得静默降级：** 回退必须显式说出来，不能让用户以为用了 Team。
- **不得假装用了 Team：** 没有该能力时，输出中不得出现"已派发 teammate"之类表述。
- **不得因为"Team 更高级"就默认启用：** Team 有持久化与并发写入成本，必须由用户选择。
- **方式不改变标准：** 无论用 Team 还是默认子代理，**角色库、派遣矩阵、评分维度、
  交叉质询与聚合规则完全一致**（R12 = 硬门禁 `G1—G5` + 六维排序；R7 / R10 / R13 = 归一化后
  逐维中位数 + 一票否决；见 [references/roles.md](references/roles.md)）。
  Team 只改变执行方式，**不改变审查标准**。
- **用 Team 时必须守写作用域：** 并行写者写**互不重叠**的文件；写冲突按
  "重新读取后再提交"处理（见 [project-layout.md](references/project-layout.md) §5）。

> 详见 [references/roles.md](references/roles.md) §4。

---

## 4. 各 R 阶段 输入 / 输出速查

### R2 / R5 — 领域测绘与共演化检索

- **输入：** 检索关键词或研究问题；检索范围（时间范围、会议范围、数量上限）；
  尽职调查等级（L1/L2/L3，默认按触发条件自动判定）。
- **流程：** A1 本地检索 → A2 **在线源强制补充检索**（不得因本地命中而跳过）→
  A3 范围扩大策略 → A4 饱和判定与输出。
- **交付物：** 文献列表（含来源标注）+ 检索过程记录（含 429 等待日志）+ 本地缓存
  更新记录 + 尽职调查等级达成情况。
- **落盘：** `routes/<R>/docs/<R>NNN-field-map.md`（含负检索记录），
  并更新该路线 `INDEX.md`；**检索未达饱和必须记入 Warnings**。

### R3—R6 — 双轨发现与种群进化

- **输入：** 研究领域关键词；已有参考文献（可选）；资源约束（可选）。
- **流程：** R3 双轨发现（`P1`—`P6` 由**隔离开的 Exploration Agents** 生成，`local` 另起一轨；
  **生成期互不可见**，见 [phase-r3-r6-discovery.md](references/phase-r3-r6-discovery.md) §R3.3—§R3.6）→
  R4 隔离种群 → `structural_signature` 五维聚类 → **QD archive**（**只保多样性，不做总分排序**）→
  **niche 是七个科学结构轴**（`assumption-` / `formulation-` / `representation-` / `mechanism-` /
  `theory-` / `evaluation-` / `boundary-shift`），**不是** R12 的叙事 preset `N1`—`N10`；
  **R4 elite = within-niche representative, not global winner** →
  R5 共演化检索（每轮至少一条 query 由最新候选生成）→
  R6 进化（mutation / cross-domain crossover / simplification / theory-induced deduction /
  **new niche = 首次占据一个当前为空的合法轴**（七轴冻结，见 §R4.2.1）；
  **跨 island 融合只允许在这里发生**，并写 `operator` + `parents` 谱系）。
- **边界三句话：** `R3: Diverge`（让不同世界出现）→ `R4: Preserve Diversity`（不让它们被总分压扁）
  → `R6: Recombine`（才允许互相借东西）。
- **发散策略约束（见 §R3.8）：** 每个候选至少通过一种算子推导 ——
  `P1` 问题重构 / `P2` 假设挑战 / `P3` 领域擦除 / `P4` 跨域结构类比 / `P5` 理论视角 / `P6` 反例与测量反转。
- **快筛（concept 级 hygiene，见 §R3.6 与 §R3.7）：** **只**能因「自相矛盾 / 违反已知事实 /
  同名重复 / 不可定义 / prior work 完全覆盖 / 与契约无关」六条杀掉；
  **不得**因工程风险高、暂无 theorem、不会实现、非主流、venue fit 不明、证据不足而杀。
  **进入 population 的门槛 = 完成 L2 检索**；要写进文档的「首次提出」类声称仍要求 L3 + 负检索记录。
  **不派遣 S-Repro。**`R3 screening ≠ R7 assurance`。
- **交付物：** **population + QD archive**（每个 **live niche** 至少一个 `elite`）+ 技术路线归纳表 +
  创新性边界界定 + **失败记忆**（被搁置的候选写 `failures[]`，不得删除）。
  **不再产出「QD archive 的 elite 集合（3—5 个）」——该概念在 Wave 2 起作废。**
- **预算：** 默认 4 islands（`P1`—`P4`；`P5`/`P6` 按需启用）× 每岛 3—6 候选；进化 ≤2 轮。
- **两阶段 fitness：** Search 期只看结构新颖度 / 跨域意外度 / 表示距离 / 演绎产出，
  **不看 venue fit** —— venue 适配在 R12 / R13 才生效。
  **`coverage before ranking`：** 上述四项在 `generation == 0` 只作 archive descriptors /
  search heuristics，**不得硬排序**；否则 `P4`/`P5` 会因「跨域 / 理论」标签天然拿高 reward。
  质量压力从 R6 起才逐步引入。
- **落盘：** `routes/<R>/docs/<R>NNN-discovery.md`，并更新该路线 `INDEX.md`
  （被放弃的候选 → **Most important negative findings**，**不是**「已证伪」——
  被放弃是**搜索决策**，不是对世界的判决；未核实的无人区声称记 Warnings）。

### R8 — 证据契约

- **输入：** `claims[]`（R3—R6 的 seed claim）+ `evidence[]` + `assurance[]`（R7 的攻击结论）；
  一个或多个 idea（来自 R3—R6 或用户直接提供）；资源约束（可选）。
- **流程：** ① 把 R7 的六攻击面**五元组**逐条转成契约的必答项（`Alternative` → `nearest_alternative`，
  `Discriminating Test` → `minimal_discriminating_experiment`，`Kill Condition` → `kill_rule`）
  → ② 每条 central claim 建一张证据契约（10 键，见
  [references/phase-r8-evidence-contract.md](references/phase-r8-evidence-contract.md) §R8.2.2）
  → ③ 从契约派生 `planned` 实验并**冻结 `preregistration`**
  → ④ **证据驱动的单向 `status` 升级** → ⑤ 写 `proposal.md`。
- **不做什么：** **不创建 claim**（claim 由 R3—R6 创建）；**不重做**新颖性检索（引用 R7 的
  `S-Lit` 结论）；**不要求 artifact**（R8 无 code / logs / failed runs）；**不降级、不写 `killed`**。
- **交付物：** 论文提案（1500—2000 字，含**证据契约摘要**节）+ `claims[].contract`
  + `planned` 实验（含冻结的 `preregistration`）；`evidence.md` / `theory.md` 按需。
- **落盘：** `routes/<R>/docs/<R>NNN-proposal.md`（`evidence.md` / `theory.md` 各占独立序号），
  并更新该路线 `INDEX.md`。
  **`experiment-plan.md` 不属于 R8** —— 实验规划文档由 **R9—R11** 落盘。

### R12 — 叙事（state 的视图）

- **输入：** **idea 清单**（来自 R3—R6 或用户提供）+ **方案**（来自 R8，推荐）；
  关键参考文献（可选）；目标会议（可选）；资源约束（可选）。
- **拆 pre / post（Wave 3）：** **R12-pre 覆盖 D0—D3**（证据台账 / claim graph 复核 / 科学分类 / anchor eligibility），
  只写「若 `H` 被验证，可能成立的 thesis 是…」，**不得决定研究方向**；
  **`claims[]` 的创建在 R3，不由本阶段创建**（见 [phase-r3-r6-discovery.md](references/phase-r3-r6-discovery.md) §R3.0）；**R12-post 覆盖 D4—D9**（叙事实现 / 攻击面审核 / venue 校准 / 门禁 / 排序 / 输出），
  只读**已核实**的 claim / evidence / 边界 / **失败**，
  此时才选 preset 并落 `narrative_view`，且**不得新增 `evidence`、不得提高 `epistemic_status`**。
- **定位：** **Claim-first, evidence-constrained, narrative-last** —— 先确定**在现有证据下
  最强但不过度**的科学主张，再找最短的故事让审稿人正确理解该主张。
  **这是基于「预期贡献」的叙事预演，不是基于「实测结果」的包装** —— 实验完成后应
  **回到 R12 复核叙事是否仍成立**。字母顺序上位于方案生成与方案复核之间。
- **流程（D0—D9 的 pre/post 归属见上）：** D0 证据台账 → D1 claim graph **复核**（**不创建**）→ D2 科学分类 `(O, T, R)` →
  D3 Anchor Eligibility → D4a Scientific Narrative Search（**2—4 套真正不同的 claim hierarchy**；六槽位
  `S1—S6`；含包装前后对照）→ 逐套 freeze → D4b Rhetorical Realization → D4c Semantic-Equivalence Audit →
  D4d Blind Claim-Recovery Probe（四维恢复 + paired sensitivity）→ D5 攻击面审核 → D6 venue calibration → （**R-Novelty / R-Causal / R-Experimental /
  R-Theory / R-Generalization / R-Utility 六人全部派遣 + S-Lit 恒派 + S-Devil 不打分**）→
  R12 / R13 的 venue calibration → D7 硬门禁 `G1—G5` → D8 六维排序 → D9 最佳叙事推荐。
- **冻结后的表达搜索：** 每套 hierarchy 只用 evidence framing / contribution stance，
  四个预登记 profile、一轮搜索。保持 claim/evidence/comparator/uncertainty/scope/prior delta/
  assumptions/limitations/failure/causal status/interpretation 不变；正文与 metadata 都检查。
  boundary 固定前置；不允许 weakness laundering 或用分数救回非等价表达。
  多模型盲恢复缺数据时标 INCOMPLETE；不改 State 补答案，不宣称科学判断已被改善。
- **交付物：** 证据台账 + claim graph + 每套候选的六槽位叙事 + 六攻击面审稿人意见 +
  S-Devil 致命弱点清单 + S-Lit 核验结论 + 门禁逐项判定 + 六维排序 + 最佳叙事推荐 +
  **缺失证据清单与最小必要实验 / 定理**。
- **落盘：** `routes/<R>/docs/<R>NNN-narrative.md`，并更新该路线 `INDEX.md`
  （被覆盖的叙事方向 → **Most important negative findings**；最佳叙事 →
  **Strongest supported findings** 的叙事表述；门禁 `fail`、或**六维中位 <3
  仅作 Warnings 标记**（**不是**综合评分、不进排序、不参与推荐）→ Warnings）。
  > ⚠️ **叙事被淘汰 ≠ 科学被证伪**，最优叙事被选 ≠ 科学被证实 —— R12 是 state 的
  > **视图**，不创造科学真理（见 §1.7）。`已证实` / `已证伪` **不得**用来描述修辞方案。

### R7 / R10 / R13 — 对抗保证 · 元认知修复 · artifact 审计

- **输入：** 待复核方案（来自 R8 或用户提供）；上一次审阅内容（可选，用于接续
  复核）；关键参考文献（可选）。
- **定位：** 对象是**已成型方案**；主战场是**方法正确性与工程可行性**；创新性维度
  以**防复现**为核心目的（见 §0 的「各阶段的分工」）。
  **E 不是链条终点，而是反馈环**——结论可回流到 **R8**（重写方案 / 补实验）或
  **R3—R6**（缺陷指向 idea 本身）。**三个触发点：** ① R8 产出后首次复核；
  ② **实验完成、有实测结果后**（"预期"变"实测"，**防复现检查必须重做**）；
  ③ 投稿被拒 / 改投时。
- **assurance 输出五元组（Wave 3 硬规则）：** `(Attack, Target Claim, Alternative, Discriminating Test, Kill Condition)`。
  **`Kill Condition` 必须可判定**；只有分数、没有可判定 Kill Condition 的评审**不合格**。
  1—5 分降为次要记录。**assurance 不得直接改 `claims[].status`** —— 只能经 R10（例外见 §1.6）。
- **Integrity Gate（`S-Integrity`，R13 生效）：** leakage / cherry-picking / metric misuse /
  post-hoc selection bias —— **不通过即不得提交**，不是「记一条 warning」。
- **流程：** R7.2 判断复核类型（首次 / 接续）→ **R7.3 派遣六个攻击面 + `S-Lit` + `S-Devil`**
  （含**防复现检查**）→ R7.4 交叉质询与共识形成（**先做极性归一化**，见
  [scoring-policy.md](references/scoring-policy.md)）→ R7.5 复核结论 → R7.6 接续复核规则。
- **交付物：** 六攻击面评审意见（含五元组）+ 交叉质询记录 + 审查结论卡片
  （含**复现风险等级**）+ 横向对比表 +（接续复核时）变更追踪表。
- **落盘：** `routes/<R>/docs/<被审ID>-review-r01.md`（接续复核用 `-r02.md`），
  并把审阅结论翻译成 `STATUS.md` 条目：成立 → **Strongest supported findings**；
  否定 → **Most important negative findings**；待补实验 / 文献 → **Next recommended actions**；
  未缓解的致命风险或**复现风险 = 高** → **Critical uncertainties**。
  写状态前先写回 `research-state.json`，再用 `scripts/render_status.py` 生成，
  **不得手工编辑 `STATUS.md`**。

---

### R0 / R1 — 研究契约与 World Model

- **R0 输入：** 研究问题原话 + 目标锚点（可选约束 / 资源）。**产物：** `contract`
  （`goal` / `primary_anchor` / `constraints` / `resources` / `provisional_anchor_rationale` / `out_of_scope`）。
- **R1 常驻：** 维护八类一等对象；**不是一次调用**，任何阶段开工前先读、收工前写回。
- **硬规则：** R0 **不得**产出 `claims[]`，**不写** `assurance[]`（后者由 R7 写）；
  契约期锚点是 **provisional**，由 R1 的 Anchor Eligibility Test 复核。
- **新项目：** 按 [outcome contract](references/evidence-outcome-contract.md) 冻结 `contract.outcome_policy`。
  旧项目显式回填历史 outcome，不将缺日志的实验伪造为已审计。原始八类对象与 lifecycle 枚举不变。

### R9 / R10 / R11 — 实验循环与修复门

- **R9：** 实验树 `X1—X6`（`X2` 只做基线校准，**不得承担 claim 判别**）；
  用 **EIG** 选下一个实验：`e* = argmax E[ΔU|e]/cost(e)`，必须写出「改变哪条 `U` / 方向 / 成本口径」，
  并把预测值写进 `scheduler.json` 的 `predicted_information_gain`。
- **R9.O：** 每次结果先做 [Evidence Outcome Analysis](references/evidence-outcome-analysis.md)，
  区分有效负证据、mixed outcome、未决推断与无效执行，逐 claim/hypothesis 给出 scoped update。
  独立审计通过后才经 R10/R11 回写。PIVOT/STOP 固化 stop rule，下一轮 Discovery/Planning 必须读取。
- **R10：** **critical flaw ⇒ state 必须改变**；处置五值 `REPAIR_CLAIM|RUN_TEST|FIX_IMPLEMENTATION|NARROW_SCOPE|KILL_BRANCH`；
  关闭两值 `RESOLVED|ACCEPTED_LIMITATION`；落盘三元组 `flaw/disposition/state_delta/closure`。
- **R11：** `result → claim update → uncertainty update → EIG 回填 → next experiment` **五步**，缺一不可。
  第 3 步的判据是「**有没有有意义的 state delta**」，不是「有没有关掉一条 `U`」：
  `uncertainty` 可 `high → medium → low` 而 `status` 保持 `open`（两个维度独立，**不得**判不闭环）。
- **落盘：** `.research-idea-pipeline/routes/<R>/research-state.json`（就地覆盖，不按阶段切分）；
  EIG 对照写同目录的 `scheduler.json`（telemetry，由 execution gate 检查来源和状态）。

### R13 / R14 — artifact 审计与决策

- **R13：** 审 artifact 而非论文（code / logs / **failed runs** / dataset 与 metric 选择历史）；
  Integrity 检查（cherry-picking / leakage / metric misuse / post-hoc bias）是 **Gate**。
  **R7 首轮无 artifact 也无契约，只能审 seed claim / hypothesis / assumption** ——
  不得在无 artifact 阶段要求 artifact 审计。
- **R14：** `continue | pivot | archive | submit`，并回写 `decision`。

## 5. R 阶段衔接与状态回写

**衔接图见 §0 的双循环图。** 三条回写规则：

1. **R1 是唯一状态载体**：`.research-idea-pipeline/routes/<R>/research-state.json`，**就地覆盖**，
   不按阶段切分快照（旧的 `state-<mode>-<ts>.json` 口径已作废）。
2. **改 `claims[].status` 默认只能经 R10。** **唯一例外**：R8 挂证据时可做**证据驱动的单向升级**（`ungrounded` → `partially-supported` / `supported`）；**降级与否决**（`contradicted` / `killed`）**仍只能经 R10**。
   Discovery（R3—R6）与 Assurance（R7）都不得直接改 ——
   防「自己给自己判分」。
3. **每阶段收尾跑** `python3 scripts/state_check.py --check <state.json>`，**硬违规须为 0**；exit 3 = 硬违规，exit 4 = 文件缺失 / JSON 非法。

**反馈环：** R14 的 `pivot` 回 **R3**；`continue` 回 **R9**；R10 的 `KILL_BRANCH` 归档该分支。

## 6. 执行自检清单（每次输出前）

- [ ] phase 已明确，且与该阶段的输入约定一致。
- [ ] **锚定点（核心目标）已与用户确认**，并已写入 frontmatter 的 `core_goal`、
      路线 `INDEX.md` 的路线概要、以及 `state.json`；**未确认就开工属于违规**。
- [ ] **锚点体系完整（新增）**：根 `INDEX.md` 已声明**项目主锚点**；
      本路线的 `anchor_role` 已给出；`supporting` 时 `serves` / `serves_evidence`
      已填**且可证伪**；答不出已降级为 `orthogonal` 并在根 `INDEX.md` 公开写明
      "不参与主锚点成功判据"（`orthogonal` 不得进 R12、不得作投稿主线）。
      **`core_goal` 只记主锚点**；次锚点写的是 `core_goal_secondary`，不是
      `"theory+feasibility"` 这种拼接值。
- [ ] **锚点与产出不一致时已落盘处置，而不是只提示（新增）**：要么重新定位
      （可证伪的 `serves` 或 `orthogonal`），要么向用户提请换方向。
      **没有自行换方向、换项目主锚点或开新路线**（只有用户能授权，走 §0.2 变更单）。
- [ ] **派遣方式已定**：环境有 Team 能力时**已询问用户**；用户显式要求 Team 而环境
      不具备时，已**显式告知回退**（未静默降级、未假装使用 Team）。
- [ ] **已读项目 `AGENTS.md` 与目标路线的 `INDEX.md`**，并遵循其约定；
      **`AGENTS.md` 引用的文件已逐个校验存在性**，缺失项已记入根 `INDEX.md` 的 Warnings。
- [ ] 文献检索：**先尝试 web search，再本地与多源**；网页发现有来源记录。
      不可用或失败已记录；明确离线时跳过。网页与本地命中均没有替代多源核验。
- [ ] 已判定触发条件（T1—T8）并达到对应尽职调查等级（L1/L2/L3）与饱和判据。
- [ ] 每条文献结果标注了 `source`；结果集是本地 + 多源 的并集。
- [ ] 若发生 429，输出了等待日志，且退避符合 `10→20→40→80→160s`、上限 5 次。
- [ ] **每个启用源都有状态**（`ok` / `partial` / `unavailable` / `skipped`）；任一源降级已在输出中显式说明，且**退出码为 2**。
- [ ] **饱和计数只在「当期可用源集合未变」时累加**；集合一变已重置计数。
- [ ] 若少用了源（`--sources`），报告中已写明理由；源覆盖不完整时结论措辞已降级。
- [ ] **已解析 `arxiv.org` / `export.arxiv.org`；若解析到本地 IP，输出了「代理环境提示」段**
      （写明具体 IP 与判定类型），且**没有**据此判定"在线源不可用 / 无人在研究"。
- [ ] arxiv 结果已写入缓存。
- [ ] **创新性 / 新颖性判定**依据 prior-work collision + structural novelty +
      scientific non-triviality（**不是** venue 口味）；贡献标注了类型。
- [ ] **只有 R12 / R13 的 venue calibration 与投稿评估**引用具体顶会标准；
      **R3—R6 不得用顶会口味判断候选**（见 §4 R3—R6 的两阶段 fitness）。
- [ ] **每个方法都标了「方法来源」**（`原创` / `部分原创` / `迁移`）且**可核验**；
      没有把「迁移」包装成「原创」；标为「迁移」的**已证明迁移本身带来新性质**，
      否则其复现风险按"高"处理。
- [ ] **四步链完整**（数学建模 → 证据 → 结合 ML 方法 → 任务性能）；**没有在证明性
      工作上停留或反复**；未完成的证明已标 **"待补证明 · 待核实"** 并转入后续步骤，
      而不是阻塞链路；**也没有声称"已证明"却未完成证明**。
- [ ] **四个会议审稿人的评价都含「理论角度 + 应用角度 + 会议特性判定」三段**
      （**仅 venue calibration 表**）
      （见 [roles.md](references/roles.md) §1.0）；R-MICCAI 不适用时已标 **"不适用"**
      而非硬凑临床相关性。
- [ ] **R3—R6：每个 candidate 都完成 §R3.7 概念级审核**（新颖性判定 / 概念可行性 /
      重叠度 / 致命反驳），没有「只给 idea 不给审核」；且未误派 S-Repro；
      **进入 QD archive 的 elite 已达 L2**，含「首次提出」声称的已达 L3 并附负检索记录。
- [ ] **assurance 五元组齐备**：每个攻击面都给了 `(Attack, Target Claim, Alternative, Discriminating Test, Kill Condition)`；**`Kill Condition` 可判定**；只有分数没有 Kill Condition 的评审**不合格**。
- [ ] **Integrity Gate（R13）**：leakage / cherry-picking / metric misuse / post-hoc bias 已逐项过闸；**R7/R8 未要求 artifact 审计**。
- [ ] **R12：先有证据台账与 claim graph，再有叙事**：`C0—C5` 完整，每个 `Ci` 都有
      `Ci ← Ej` 或标 `[待补]`；每套候选都能写出一句话的**可证伪 central proposition**；
      候选是 **2—4 套真正不同的 claim hierarchy**（**不是**同一主张的四种措辞）；
      每套用**六槽位 `S1—S6`**（`S5` 覆盖 `C0`—`C4`，`S6` 写出**不成立的条件**）；
      跨域类已做 **anti-application stress test** 与 **Transfer Legitimacy（L1/L2/L3）**；
      **六个攻击面审稿人全部派遣、S-Lit 恒派、S-Devil 不打分**；已做**叙事包装
      （重新定位，非夸大）**；**D9 给出了缺失证据清单与最小必要实验 / 定理**；无禁用表述。
- [ ] **R7 / R10 / R13：结论卡片给出了复现风险等级**，并回答了"设计层面贡献 vs 实现层面改进"；
      复现风险 = 高时总体判定不为"高"；**S-Devil 归一化后的新颖性稳健度 ≤ 2 时总体判定
      同样不为"高"**（除非走「带条件的推荐」并写明理由、缓解路径与验证点）。
- [ ] **R12：硬门禁 `G1—G5` 已逐项判定**（任一 `fail` ⇒ `not_submission_ready`，
      且**不参与六维排序**）；排序用的是**六个同向维度**，**未做也不需要极性归一化**。
- [ ] **R7 / R10 / R13：聚合前已做极性归一化**（S-Devil 反驳分 → 新颖性稳健度 = `6 − 反驳分`），
      汇总表同时给出原始分与归一化分（见
      [scoring-policy.md](references/scoring-policy.md)）。**不得用「6 个都同意」声称
      reviewer consensus** —— 六个 reviewer 不是独立样本。
- [ ] 所有"首次提出"声称**已完成 L3 穷尽检索**、经 S-Lit 核实、附负检索记录，
      否则已降级为"据本次检索未见"或标注"待核实"；
      **全部措辞符合 [evidence-policy.md](references/evidence-policy.md) 的证据等级表**。
- [ ] **`STATUS.md` 的 Critical uncertainties 已统计「待核实」条数**；若超过 5，已在本轮内收敛
      （补检索 / 补实验 / 明确降级措辞）；**`needs_verification` 的条数也已计入根
      `INDEX.md` 的全局 Warnings**，超过 5 已开补元数据 TODO。
- [ ] **正文形式已达受控中文**：落盘文件已跑
      `python scripts/ste_lint_zh.py --disable synonym-rotation <文件>` 且**硬违规为 0**
      （无分号串联动作、无超长句、无虚动词「进行分析」、无营销形容词、无套话）；
      对话返回**第一段就是结论**；一份文档内同一概念只用一种写法。
      **若用户显式声明了 asd-ste100 档**，命令改为
      `python scripts/ste_lint_zh.py --max-chars 25 <文件>`，且**建议类报告已逐条人工处置**
      （脚本不会因此失败，见 [writing-policy.md](references/writing-policy.md) §7）。
      **⚠️ 情态未被删改**（「可能 / 初步」原样保留，见
      [writing-policy.md](references/writing-policy.md) §5）。
- [ ] 理论/可行性卡点已先检索（含负结果文献），未直接假设成立。
- [ ] 无臆造引用；无法确认处标注"待核实"。
- [ ] **方案/审阅记录已落盘到所在路线的 `routes/<R>/docs/`**，命名符合
      `<R><NNN>-<slug>.md` / `<ID>-review-r01.md`；且**文档前缀 = 路线字母**（不随阶段变化）。
      **`slug` 未越界**（只用 [project-layout.md](references/project-layout.md) §2.1 封闭枚举）；枚举外的派生物写的是 frontmatter 的
      `subtype`，且路线 `INDEX.md` 文档表**有 `subtype` 列**。
- [ ] **落盘分档正确**：交付物在 `routes/<R>/docs/`（**扁平，无子目录**）；
      子代理**原始评审件**在 `.research-idea-pipeline/routes/<R>/<被审ID>-r<NN>/`，
      **没有**塞进 `docs/`；**正式 review 自带摘要**，且没有引用指向原始件。
- [ ] **`docs/refs/` 下每个 PDF 都在 `docs/refs/index.json` 里有条目**
      （`python3 scripts/refs_index.py --check` 通过）；索引中无绝对路径；
      `needs_verification = true` 的条目**未**用于支撑创新性声明；
      遇到旧 schema 已用 `--migrate`（**不是**直接重建，避免丢旧字段）。
- [ ] **已更新路线 `INDEX.md`**（资产目录：文档索引、Experiments、Decisions、Reviews、
      Milestones、Recent Research Changes）**与 `STATUS.md`**（当前状态，由 state 生成）。
- [ ] 未达饱和的检索、未缓解的风险已记入 `STATUS.md` 的 Critical uncertainties；
      跨路线层面已同步到根 `INDEX.md` 的全局 Warnings。
- [ ] 已附 `state.json` 片段与 **`next_action_recommendation`**（**不是** `next_phase_suggestion`
      —— `R0`—`R14` 是**能力**不是固定流水线；下一步由
      [scheduler-policy.md](references/scheduler-policy.md) 的 `next_action_policy` 决定）。

---

## 7. 设计依据（为什么这样编排）

1. **为什么用 R 阶段而非单一流程？** 科研搜索需要 Discovery 与 Assurance 两条循环
   **并行且互相牵制**，不是一条流水线。R0—R14 让每步有清晰输入输出、并把结果**写回同一个
   Research State**；读到 `R<n>` 就知道它在双循环的哪一侧。**旧 A—E 顺序流水线已作废**。
2. **为什么先尝试 web search，再本地与多源？** 网页搜索可以发现新术语、原论文和实现资料。
   本地库用于复用已有资料，多源用于核验和扩检。网页无命中与本地无命中都不能证明工作不存在。
   凡是支撑创新性声明、理论判断、可行性判断的检索，必须扩到 arxiv 并达到饱和。
   把工具的局限当成世界的性质，是本流水线要防的最主要错误。
3. **为什么 429 要指数退避？** 429 通常意味着短时限流；指数退避比固定等待更高效，
   也比立即重试更礼貌；5 次上限避免无限阻塞。失败时必须降级标注"检索未达饱和"，
   不能让不完整的检索伪装成完整结论。
4. **为什么 R7 / R10 / R13 支持接续复核？** 接续复核聚焦上次未解决问题与新增变更，避免
   重复完整审查，同时用"变更追踪表"保证审查连续性。
5. **为什么单设 R12 做叙事？** 同一 State 的科学内容可能因表达次序与隐含比较被误读。
   D4a 先由 State 决定科学 hierarchy、preset 和证据映射，再逐套冻结；D4b 仅搜索同一
   科学故事的等价表达。D4c 拒绝任何语义或边界改变，D4d 以盲恢复检验理解，并检查轻微
   修辞扰动的敏感性。目标是准确恢复 claim/evidence/实际 delta/boundary，不是更高
   reviewer overall score。G1–G5 和 D8 六维继续约束科学候选，二者不能被修辞恢复替代。
6. **为什么角色不变？** 本 Skill 只做编排，角色定义、评分维度、审查视角全部沿用
   统一角色库，保证审查标准的一致性。
7. **为什么文档也按路线分目录，而不是集中到根 `docs/`？** 早期设计把文档集中到根
   `docs/`，靠文件名前缀隔离路线。实际用起来有两个问题：① 每条路线都会持续产出
   （方案、叙事、多轮审阅），**文件数线性增长，"集中"很快变成"平摊"**；② 前缀成了
   唯一的隔离手段，一旦写错就无法补救。
   改为**文档随路线走**（`routes/<R>/docs/`，目录内仍保持扁平），根 `docs/` 退为**跨路线
   共享区**（只保证有 `refs/`）。**前缀仍然保留，但身份变了**：它不再是隔离手段，
   而是**文档 ID** —— 审阅要挂靠（`A003-review-r01`）、跨路线引用要唯一（`A002/I3`）。
   根 `README.md` / `INDEX.md` 管住"项目级"，避免根索引膨胀成流水账。
   **Wave 6 进一步把全部路线集中到 `routes/`**，并把路线级人类视图拆成三件：
   `README.md`（是什么）、`STATUS.md`（现在怎样）、`INDEX.md`（有哪些材料）。
8. **为什么负结果要固化成资产？** 负结果常被丢弃，导致后人重复踩坑。
   把证伪结论与 TODO/Bugs/Warnings 一起固化，是最省算力的做法。
   **Wave 6 后它们归 `STATUS.md`**（即 `research-state.json` 的投影），
   `INDEX.md` 只留资产目录 —— 状态与材料分开，才不会互相污染。
9. **为什么把评分与证据措辞抽成共享文件？** 这两类机制被多个 R 阶段 复用，**复制一份
   就是多一个漂移源**：改了一处、漏了另一处，就会出现"同一条规则两个版本"。
   因此 [scoring-policy.md](references/scoring-policy.md) 与
   [evidence-policy.md](references/evidence-policy.md) 各自做**唯一权威定义**，
   各 R 阶段 只保留自己特有的部分（如 R12 的维度向量规模、R7 的攻击面分工）并引用它们。
10. **为什么 R7 / R10 / R13 也必须做极性归一化？** R7 / R10 / R13 **仍在用** S-Devil 的
   **反向**「新颖性反驳」分（`5 = 完全无新颖性`）。不归一化就直接取中位数，会把
   **最没新颖性的方案算成高分**。归一化（`稳健度 = 6 − 反驳分`）是聚合的前置条件。
   **R12 已不使用该反向分**（`S-Devil` 不打分、六维全部同向），因此 §2 的归一化
   **对 R12 不适用** —— 与第 13 条一致。
11. **为什么要给"形式"单独立一条政策（受控中文）？** 本流水线一次产出几千字：一份提案、
   多套叙事、六到八份评审意见。**没有人会逐句重读**，读不清就等于没写。
   而中文技术文本有一套和英文不同的机器味：**虚动词**（「进行分析」）、**套话**
   （「需要注意的是」）、**同义轮换**（同一件事换三个名字）、**分号串联**。
   这些不是审美问题，是**消歧成本**：读者要把一句话读两遍，就等于这条产出打了个对折。
   所以按 [writing-policy.md](references/writing-policy.md) 立硬规则，并配一个**能读中文的**
   linter。**为什么不用英文的 ASD-STE100 原版规则？** 它是英文标准；实测把它套在中文段落上
   会返回「0 违规」的**假绿灯**，等于装了一道不存在的闸。中文没有官方受控词表，
   因此词汇规则**只作方向**，不声称合规。
   **为什么 asd-ste100 只作可选最强档、不做默认？** 实测：8 个受管文件在默认档下硬违规
   全为 0；换成 asd-ste100 口径（25 字上限 + 同义轮换）会新增 2—20 处，其中多为
   **说明性长句**。默认档服务常规产出（一次几千字），asd-ste100 服务**必须逐字精确**的产出
   （对外交付、冻结契约、给外部 agent 的指令）。按期放开是**产能与严格度的取舍**，
   所以开关交给用户；**Agent 不得自行升档**，否则严格档会被当默认档用，产出速度静默变慢。
   **为什么情态单列一条？** 受控写作最常见的翻车方式是：为了压句长，把「实验**可能**受批次
   效应影响」改成「实验受批次效应影响」——那不是简化，是**换了个结论**。句长上限最容易
   引诱人删掉的正是这些词，所以必须在政策里显式禁止。

12. **为什么把叙事层从 Narrative-first 改成 Claim-first？** 旧哲学是「找到最有说服力的
    故事」，它已经做到了 claim engineering，但**叙事层权力过大**：继续扩展会从"帮助发现
    最强科学主张"滑向"帮助一个 idea 找最强包装"。新哲学是**「找到在现有证据下最强但
    不过度的科学主张，然后找到最短的故事让审稿人正确理解它」**，即
    `Narrative quality = Claim strength × Evidence alignment × Reviewer comprehensibility`。
    **其中 Evidence alignment 最难伪造**：它要求每个 major claim 都有专门的 identifying
    evidence（`Ci ← Ej`），而不是"所有实验都支持这篇论文"就够了。
    这也是把总纲从「A 有结构性缺口、B 恰好补上」换成「条件 `Y` 下存在可验证缺口 `G`，
    本文建立新知识 `K`」的原因 —— **`B → K` 只是产生 `K` 的一种方式**，否则 N4（现象）、
    N8（评测）、N10（负结果）会被迫硬塞一个 `B`。
13. **为什么删掉 11 维中位数与「新颖性稳健度 = 6 − 反驳分」？** 它们看起来 rigorous，
    实际是**伪精确**：六个 reviewer **不是独立样本**（同一基础模型换 prompt，`corr ≫ 0`），
    所以"6 个都认为新颖"不等于真人 reviewer consensus；而 `6 − 反驳分` 没有概率解释。
    改为**两层**：**硬门禁 `G1—G5` 不打分、不聚合**（claim grounding / prior-work
    distinction / identification / factual integrity / venue scope），**排序只用六个同向
    维度**。门禁失败**不参与排序**，避免"高创新性 + 低可验证性"被中位数救回来。
14. **为什么 reviewer 按「攻击面」分，而不是按会议分？** 真实的 paper failure mode 是
    *novelty / causality / experimental design / theory / scope / utility* 六类，而
    `R-CVPR`、`R-ICML`、`R-NeurIPS` 的意见**高度重合** —— 真实的 CVPR 审稿人可能是理论
    审稿人，真实的 ICML 审稿人也可能主攻实验设计。所以 R12 改派六个攻击面审稿人，
    会议差异改由 **R12 / R13 的 venue calibration** 单独一层承担：**按 contribution type 校准，
    不是 venue 直接选 preset**。
    **为什么同时删掉「必须有迁移合法性定理」？** 那是一条过拟合 ICML theory 的规则，
    会让一个很好的 empirical insight 因为没有 theorem 被判"不可投稿"。改为
    **Transfer Legitimacy Argument** 三级（`L1` 结构假设 + 证伪实验 / `L2` 形式化不变性 +
    充分条件 / `L3` 定理 + 证明 + 紧性），硬约束变成**证据强度必须与声称的贡献等级匹配**。

15. **为什么两阶段 fitness？** 在**搜索期**优化 venue fit，正是杀死范式 idea 的机制 ——
    系统会稳定收敛到「安全、合理、容易做的小改动」。所以 R3—R6 只看
    `representation_distance` / `structural_novelty` / `cross_domain_surprise` / `deductive_yield`，
    `EIG` 也只作记录不作排序依据；venue 适配推迟到 **R12 / R13**。
    配套机制是 **QD archive**（每个 **live niche** 留一个 elite，**V15 机械强制**）——
    **只留综合分最高的一个，会让「可行性 5 的增量 idea」把「可行性 2 的范式 idea」提前杀掉。**


16. **为什么角色按「攻击面」而非「venue」组织？** 真实的 paper failure mode 是
    *novelty / causality / experimental design / theory / scope / integrity* 这几类，
    而 `R-CVPR`、`R-ICML`、`R-NeurIPS` 的意见**高度重合** —— 真实的 CVPR 审稿人可能是理论审稿人，
    真实的 ICML 审稿人也可能主攻实验设计。所以 venue 差异**后移为一层校准**
    （`contribution type → evidence contract → venue calibration`，见 venue-standards §10），
    不参与科学发现。
    **为什么 assurance 输出五元组而不是分数？** 分数只能排序，**不能指导下一步**。
    `(Attack, Target Claim, Alternative, Discriminating Test, Kill Condition)` 里每一格
    都直接对应一个可执行动作或一次实验 —— 这正是从「评审意见」走向「科研搜索」的一步。


---

## 8. 规则变更自检清单（维护本 Skill 时用）

> **与 §6 的区别：** §6 是**执行时**的输出自检；本节是**改本 Skill 自身**时的自检。
> 触发条件：改动任何**规则、命名、枚举、计数、路径**。

**为什么需要它：** 本仓库的实际漂移记录显示，改了规则后**漏掉的从来不是规则本身**，
而是下面 A 组这五类"看起来不像规则"的位置。

### A. 五类高危位置（历史上反复漏）

| # | 位置 | 为什么危险 | 必做动作 |
|---|---|---|---|
| A1 | **设计依据 / 理由段**（§7、各文件开头的"为什么"） | 它在**论证旧设计**，读起来像权威依据。改规则后最容易整条漏掉，且在有人质疑设计时被当成正确论点引用 | **逐条读一遍 §7 与各"为什么"，问："这条还在支持当前规则吗？"** |
| A2 | **速查 / 汇总表**（§4 各 R 阶段 速查、`project-layout` §6 落盘职责表、`roles` §4.2 派遣矩阵、`phase-r12` §D5.5 汇总表） | 汇总表是规则的**复制品**。改规则不改它 = 仓库里有两份互相矛盾的规则 | **所有"表格式汇总"逐个核对** |
| A3 | **示例与模板**（`examples/*`、`templates/*`） | 示例会**示范旧写法**，且比正文更容易被照抄 | **示例里的文件名、路径、计数、命令逐个核对** |
| A4 | **语义字段与规则的一致性**（§0.1/§0.2 锚点体系、`project-layout` §2.1 类型枚举、§3 frontmatter schema、`research-state.template.json`、§4 INDEX 章节） | 规则写"**必须**有 X"，但 schema / 枚举里**没有 X 的槽位**，或强制项与枚举表脱节。这种漂移**不在计数上、在语义上**，比 A2 更难发现：执行者只能自创值或让 frontmatter 失真 | **规则 → 字段 → 枚举 → 模板 → 示例，五处同步。** 每条新规则都问两句：①「它要求落盘的东西，**字段表里有槽位吗**？」②「它要求存在的文档类型，**枚举里有值吗**？」 |
| A5 | **跨层漂移：claim 层 / 叙事层 / 评审层三层的耦合**（`claim-first-policy` 的枚举与门禁 ↔ `narrative-patterns` 的槽位与 preset ↔ `scoring-policy` 的门禁表与排序维度 ↔ `roles` 的攻击面角色 ↔ `research-state.template.json` 的 `claims` / `assurance` 段 ↔ `examples/example-d-narrative.md`） | 三层是**同一套规则的三种呈现**。改一层而不改另两层，就会出现"claim 要求 `Ci ← Ej`，但叙事槽位里没有 `S5`"或"门禁叫 `G1—G5`，但评分政策还在算 11 维中位数"这类**跨文件互斥指令** | **改 claim 层或评审层的任何枚举 / 门禁 / 维度，必须同时扫这三层。** 机械做法：`grep -rn '<被改的枚举名>' --include=*.md .` 逐个确认；并在 `docs/claim-first-spec.md` §10 记一行 |

> **A4 的现实教训（计数与枚举类 B1—B5 那一批）：** 规则要求"锚点必须落盘"，但 frontmatter 没有
> `anchor_role` / `serves` 的槽位；强制"锚点文档"，但类型枚举里没有 `anchor`；
> 允许"主+次锚点"，但 `core_goal` 只有一个槽；实际路线必然产出枚举外的派生物，
> 但除自创 slug 外无处安放。**全都是"规则有、载体无"** —— 只查计数与链接是查不出来的。

### B. 计数与枚举（每轮都漏）

| # | 对象 | 历史改动 | 分布位置 |
|---|---|---|---|
| B1 | **子代理数** | 会议审稿人 `3→4`；R12 `5→6`；**R7 / R10 / R13 由「八子代理」改为「六个攻击面 + `S-Lit` + `S-Devil`」** | 标题、正文、汇总表、速查节、`roles` 矩阵 |
| B2 | **规则条数** | §1 `四→五`；§1.4 布局规则 `四→五→六` | **标题里的"N 条"必须与该节实际条目数一致** |
| B3 | **会议枚举** | `CVPR/ICML/NeurIPS` → `+MICCAI` | 约 13 处 |
| B4 | **源枚举** | `local\|arxiv` → `+openalex\|crossref` | 约 15 处（注意 `index.json` 的 `source` 是**另一种含义**，不要改） |
| B5 | **slug 枚举** | 叙事从「每个 idea 一个后缀式 slug」改为单一 slug | 类型表、规则表、示例、模板 |
| B6 | **退出码** | `0/1/2` → `0/1/2/4` | CLI 表、退出码表、各 R 阶段 输出说明 |

### C. 路径与命名

| # | 对象 | 历史改动 |
|---|---|---|
| C1 | **落盘路径** | `docs/` → `routes/<R>/docs/`（**含 §4 速查节** —— 曾漏 5 处） |
| C2 | **审阅命名** | `<ID>-review.md` → `<ID>-review-r01.md` |
| C3 | **标题里的旧词** | 曾漏 `phase-r2-r5` 的 A2 标题（正文早已改为多源，标题仍写旧源名） |

### D. 机械校验（先跑，再人工）

```bash
# 1) 相对链接可达（排除代码围栏内的示例路径与模板占位路径）
# 2) §X<n> 与 §<数字> 引用可解析
# 3) JSON 文件与 md 内 ```json 围栏块合法
python3 scripts/refs_index.py --check
python3 -m unittest discover -s scripts -p "test_*.py"

# 4) 陈旧措辞扫描 —— 必须为 0
# 废弃词清单在 references/deprecated-terms.txt（.txt 天然被 --include=*.md 排除，
# 因此扫描结果才能真的为 0）；以后新增废弃表述就追加到那个文件。
PAT=$(grep -vhE '^\s*(#|$)' references/deprecated-terms.txt | paste -sd'|')
grep -rnE "$PAT" --include=*.md .          # 期望：0 命中（exit 1）

# 5) 落盘路径必须带 routes/<R>/ 前缀 —— 正确的写法以 `routes/<R>/docs/ 开头，
#    所以「反引号紧跟 docs/」就是缺前缀（§1.4 规则 1）
grep -rnE '`docs/<' --include=*.md . | grep -vE 'templates/INDEX\.md|grep -rnE'
#    ↑ 排除 templates/INDEX.md：路线 INDEX 本身就在 routes/<R>/ 内，
#      它的 `docs/` 相对链接是正确写法，不算缺前缀

# 6) 受控中文 linter —— 自检 + 受管文件必须全绿
python3 scripts/ste_lint_zh.py --selftest
for f in examples/*.md templates/*.md; do
  python3 scripts/ste_lint_zh.py --disable synonym-rotation "$f" || exit 1
done
#    注意：**不要**拿它扫本 Skill 自己的规范文本（SKILL.md / references/*.md）——
#    范围只包含「落盘文档 / 对话返回 / 子代理意见」+ examples/ + templates/，
#    见 writing-policy.md §0
#    这里固定跑**默认档**：examples/ 与 templates/ 是存量样例，不按 asd-ste100 追溯改写。
#    asd-ste100 是**当次调用**的可选档（--max-chars 25），不是仓库级闸门。

# 7) Structural Equivalence 检查器 —— 自检 + 模板 + 四份 fixture 必须全绿
python3 scripts/structural_equivalence_check.py --selftest
python3 scripts/structural_equivalence_check.py --artifact templates/structural-equivalence-audit.template.json
for f in examples/structural-equivalence/*.json; do
  python3 scripts/structural_equivalence_check.py --artifact "$f" || exit 1
done
#    真实项目里还要跑路线级交叉校验：
#    python3 scripts/structural_equivalence_check.py --route .research-idea-pipeline/routes/<R>

# 8) Rhetorical Realization —— 受限算子与 adversarial counterexamples
python3 -m unittest discover -s scripts -p 'test_rhetorical_realization.py'
```

> **唯一的发布判据是 `scripts/release_check.py` 的最后一行**（`PASS` / `FAIL`）。
> 上面的逐条命令只用于**诊断**；其中 1—8 项已全部收进那一个闸门。
> 手动逐条跑不能替代 `release_check.py`（AGENTS.md Rule 10）。

> **D4 的"已废弃措辞"清单要持续维护**：每次改规则时，把**被替换掉的旧表述**
> 追加进来。这份 grep 清单是防漂移最省力的一道闸。
>
> **新规则若带机械闸门，也要挂进本节。** 例：受控中文政策（
> [writing-policy.md](references/writing-policy.md)）带来的 `ste_lint_zh.py`
> 已挂为第 6 项；它的默认口径（`--disable synonym-rotation`）与其理由写在政策 §7，
> 不要在这里重复。

### D5. **内容丢失检查（本次真实教训）**

用「按区间替换」改动大段文本时，很容易**把夹在区间内的其它章节整节吞掉**。
本次真实发生过：重写 §1.4 时替换区间取到 `## 2.`，**把夹在中间的 §1.5 整节删除**
（一个用户明确要求的规则）——而当时的链接/引用检查**完全测不出来**，
因为引用处写的是 `§1.5` 这个**字符串**，字符串还在。

**必做：** 任何按区间替换的编辑，都要检查被替换区间内是否含其它标题：

```bash
git diff -U0 -- SKILL.md | grep -E '^[-+]## '     # 标题增删一眼可见
git log --oneline -S"<被删章节的关键词>" -- SKILL.md
```

### E. 清单自身

**改完后问一句：这次漏掉的位置，属于 A/B/C 里的哪一类？**
如果是**新的一类**，把它加进上表 —— 否则下一轮还会漏在同一处。

### Execution gate within R8/R9 and bounded R10 diagnosis

Read [execution-identifiability.md](references/execution-identifiability.md) before
managed experiments or diagnostic repairs. Use `scripts/experiment_execute.py`
issue/run with a current scheduler and content-bound manifest. Formal X3/X4
requires PEIG PASS; prospectively bounded exploration/X1/X2/pilots use PILOT_ONLY.
HOLD affects the named claim validation. Record R7 attacks and real arm/control
values; a control ID or reviewer score is not mechanical evidence of validity.

Use diagnose for R10 decision-bearing repairs. The finite shared route ledger
prevents rewording, repeated R10, new IDs/seeds, scope edits, extra U or documents
from manufacturing progress. After the configured limit, stop diagnosis and use
existing REDESIGN/T8/R14 authority. Do not iterate experiment cards to make PEIG
pass indefinitely. Post-hoc explanations are exploratory; confirm them with an
independent identifying protocol. Scientific uncertainty remains uncertainty.

The runner covers only its managed entrypoint, not arbitrary external GPU paths.
It never grants global GPU control. Legacy states remain compatible, with no
retrospective execution PASS. R9.O retains and verifies managed execution_record;
R11 uses scheduler-check to source-check actual EIG. Full tests use mock/dry-run.
