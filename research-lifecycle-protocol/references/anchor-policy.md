# 锚点体系（anchor policy）

> **唯一权威。** 六类锚点、三层锚点体系、路线与主锚点的关系（`anchor_role` / `serves` /
> `serves_evidence`）、冲突处置与锚点变更单，全部定义在本文件。
> `SKILL.md` §0.1 / §0.2 只保留开工门槛与授权边界；`claim-first-policy.md` §6 只保留
> Anchor **Eligibility** 判定（证据是否支持某锚点），不重复定义锚点枚举。
>
> **加载条件：** 开工前必读 §0.1 对应的门槛部分；完整规则在以下情形加载 ——
> 用户要求换方向、路线不服务主锚点需要重新定位、`anchor_role` 判定有争议、
> 需要开锚点变更单、R12 的 Anchor Eligibility Test 需要锚点枚举。

本文件由 v2.2.0 的 L0 精简产生：内容来自 `SKILL.md` §0.1 与 §0.2，未改变任何规则含义。

## 1. 锚定点（开工前必问，先于一切）（开工前必问，先于一切）

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
| **R12** | **叙事资格（先于选 preset）：** 先做 **Anchor Eligibility Test**（[claim-first-policy.md](../references/claim-first-policy.md) §6）——只有 `eligible` / `conditional` 的锚点才可用于组织叙事；与作者**目标锚点**冲突时**必须显式告知**。通过后再按 [narrative-patterns.md](../references/narrative-patterns.md) §2 选 preset |
| **R7 / R10 / R13** | **评审权重：** 理论锚点首查证明正确性；性能锚点首查公平比较、指标口径与统计方案 |

**各 R 阶段 详细流程：**

- R0 → [references/phase-r0-contract.md](../references/phase-r0-contract.md)
- R1 → [references/research-state-policy.md](../references/research-state-policy.md)
- R2 / R5 → [references/phase-r2-r5-field-mapping-retrieval.md](../references/phase-r2-r5-field-mapping-retrieval.md)
- R3—R6 → [references/phase-r3-r6-discovery.md](../references/phase-r3-r6-discovery.md)
- R8 → [references/phase-r8-evidence-contract.md](../references/phase-r8-evidence-contract.md)
- R12 → [references/phase-r12-narrative.md](../references/phase-r12-narrative.md)
- R7 / R10 / R13 → [references/phase-r7-r10-r13-assurance-repair-review.md](../references/phase-r7-r10-r13-assurance-repair-review.md)
- R9 / R10 / R11 → [references/phase-r9-r11-experiment-loop.md](../references/phase-r9-r11-experiment-loop.md)


## 2. 锚点变更单（Anchor Change Order）（Anchor Change Order）

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

