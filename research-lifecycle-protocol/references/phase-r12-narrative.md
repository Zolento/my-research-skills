# R12 — 叙事（narrative）：Research State 的视图

**本阶段的哲学：** **找到「在现有证据下最强但不过度」的科学主张，然后找到最短的故事
使审稿人正确理解该主张。**

**定位一句话：claim-first, evidence-constrained, narrative-last** —— 先立证据，
再立 claim，再算 claim 强度与可用锚点，**最后**才谈怎么讲。叙事是最后一层，
不是第一层。旧的「找到最有说服力的故事」不再作为本阶段的目标。

**核心公式：**

```
Narrative quality = Claim strength × Evidence alignment × Reviewer comprehensibility
```

> **已废弃的旧公式：** `Narrative quality = Novelty impression`。
> 任何以「新颖性印象」为总纲的写法都不得出现。

> ⚠️ **这仍是基于「预期贡献」的叙事预演，不是基于「实测结果」的包装。** 实验完成后
> 必须**回到 R12 复核叙事是否仍成立** —— 结论变了，叙事可能不再成立
> （此时必须按新结果重写 claim graph 与六槽位，不得沿用旧叙事）。

> **记法（两条）：** ① `N1—N10` = **scientific narrative presets**，
> 不是科学分类、不互斥、不是创新等级（见
> [narrative-patterns.md](narrative-patterns.md) §1）；
> ② 下文与 [narrative-patterns.md](narrative-patterns.md) 中的
> **「A 领域 / B 领域」是领域占位符**，与已退役的 A/B/C/D/E 阶段字母无关。

---


> **小节号 `§D0`—`§D9` 是 R12 自己的流程序号**（不是旧命名残留）。pre / post 归属见下。

## 定位与边界

**角色：** 你是横跨多领域的**资深论文作者**，熟悉 CVPR / ICML / NeurIPS / MICCAI 的
评审逻辑。本阶段由该角色主导 claim 与叙事生成，再由 §D5 的**攻击面审稿人**独立审查。

| 维度 | R3—R6（idea） | R8（方案） | **R12（叙事）** | R7 / R10 / R13（方案审查） |
|---|---|---|---|---|
| 对象 | 想法 | 想法 → 可执行方案 | **证据 → claim → 叙事** | 成型的方案 |
| 核心问题 | 值得做吗 | 怎么做、能不能做成 | **最强可辩护的 claim 是什么，最短的故事是什么** | 做得对不对 |
| 产出 | idea 清单 | 提案 + 实验计划 | **2—4 套真正不同的 claim hierarchy + 最佳叙事推荐 + 缺失证据清单** | 审查结论卡片 |
| 评审重心 | 方向与概念可行性 | 可行性与创新性 | **攻击面：新颖性 / 因果 / 实验 / 理论 / 泛化 / 效用** | 方法正确性 + 防复现 |

**一句话：B 决定「做不做」，C 决定「做什么」，D 决定「最强能声称什么、怎么讲」，E 决定「做得对不对」。**

**流程权威链：** `D0 Evidence Ledger → D1 Claim Graph → D2 Scientific Typing →
D3 Anchor Eligibility → D4a Claim-Hierarchy Realization → freeze →
D4b Rhetorical Realization → D4c Semantic-Equivalence Audit →
D4d Blind Claim-Recovery Probe → D5 Adversarial Review →
D6 Venue Calibration → D7 Hard Gates → D8 Ranking → D9 Output`。
**证据在 claim 之前，claim 在叙事之前** —— 任何一步不得跳序。
本阶段的 claim 层枚举与判据**以 [claim-first-policy.md](claim-first-policy.md) §1—§6 为
唯一权威**（本文件只复述执行所需的枚举值，不构成新定义；冲突时以该文件为准）；
评分与门禁机制以 [scoring-policy.md](scoring-policy.md) §3 / §4 为准。

**何时调用：**

- 接 **R8** 之后（**推荐**）：idea 与方案都已成型，证据台账最完整。
- 接 **R3—R6** 之后：只有 idea、暂无方案；可做 D0—D4，但台账里大量条目会是
  `Hypothesized` / `Planned`，必须标注 `[待补]`，且 `S5` 会出现缺口。
- **独立**调用：用户直接给出 idea（+ 方案 + 已有实验 / 定理）。

**输出给谁：** 最佳叙事回流到 **R8**（按该叙事重写提案）与/或 **R7 / R10 / R13**
（完整审查）。**所有候选叙事都被门禁判 `fail`** 时，建议**退回 R3—R6**。

---

## 输入

| 输入 | 必填 | 说明 |
|---|---|---|
| **idea 清单** | ✅ | 每个 idea 的：核心思路、预期贡献、与现有工作的差异、关键假设 |
| **方案（proposal）** | 推荐 | 来自 R8 的 `proposal`（含贡献清单 / 相关工作差异 / 动机 / 实验设计）或用户提供。缺失时叙事只能到「预期」层级并标注**待方案补充** |
| **已有实验 / 定理 / 文献** | 推荐 | 证据台账的原料；**没有原料就没有 claim graph** |
| 关键参考文献 | ❌ | 3—5 篇最相关论文 |
| 目标会议 | ❌ | CVPR / ICML / NeurIPS / MICCAI（**只影响 D6 校准，不影响 preset 选择**） |
| 资源约束 | ❌ | 算力、时间、数据、人力（进 D9 的最小必要实验评估） |

**前置检查（在 D0 内完成，不得跳过）：** 若某个 idea 缺少核心思路、预期贡献、
与现有工作的差异、关键假设中的任一项 → 先输出**待补充信息清单**，说明哪些步骤无法完成。
**不得编造信息。**

---

## 快速索引：D0—D9

| 步 | 名称 | 输入 | 产物 | 硬约束 |
|---|---|---|---|---|
| **D0** | Evidence Ledger | idea + 方案 + 已有实验 / 定理 / 文献 | 证据台账：每条 `E_i` + `epistemic_status` | 不得把 `Planned` 写成 `Observed`；无证据的条目留 `[待补]` |
| **D1** | Claim Graph | 证据台账 | `C0`—`C5` + `Ci ← Ej` 对照 | `C0` 必须一句话；每个 `C_i` 无证据则标 `[待补]` |
| **D2** | Scientific Typing | claim graph | `(O, T, R)` + 贡献类型 | 枚举逐字取自 [claim-first-policy.md](claim-first-policy.md) §5 |
| **D3** | Anchor Eligibility | claim graph + typing | 每个 anchor 的 `eligible/conditional/not-eligible` | 与作者目标 anchor 冲突时**必须显式告知** |
| **D4** | Narrative Realization | eligible anchors + claim graph | **2—4 套真正不同的 claim hierarchy** + 每套六槽位 | 必须是**不同的 claim 层级**，**不得**是同一 claim 的四种措辞 |
| **D4a** | Claim-Hierarchy Realization | D0–D3 | 原 D4 的 scientific narrative search + 每套冻结快照 | 只组织 State 已有 claims；冻结后不得改科学语义 |
| **D4b** | Rhetorical Realization | 单套 frozen snapshot | 四个固定 rhetorical profiles | 仅 evidence framing / contribution stance；一次批量生成 |
| **D4c** | Semantic-Equivalence Audit | 每个 variant + snapshot + State | RE1–RE5 PASS/FAIL | 不等价即 FAIL；不修补 State；不靠分数抵消 |
| **D4d** | Blind Claim-Recovery Probe | 已过 RE 的正文 | 四维恢复 + paired sensitivity diagnostic | 盲 judge 不读 truth；完整固定面板；不优化 overall score |
| **D5** | Adversarial Review | 每套叙事 | 6 攻击面审稿人独立意见 + S-Devil 弱点 + S-Lit 核验 | 六人全部派遣；S-Lit 恒派 |
| **D6** | Venue Calibration | 评审结果 | 会议适配判定（CVPR/ICML/NeurIPS/MICCAI） | 按 contribution type 校准，不按 venue 选 preset |
| **D7** | Hard Gates | 每套叙事 | `G1—G5` 逐项 `pass/fail` | 任一 `fail` ⇒ `not_submission_ready` |
| **D8** | Ranking | 通过门禁的叙事 | 六维 `1—5` + 逐维理由 | 门禁失败的**不参与排序** |
| **D9** | Output | 全部 | 最佳叙事 + runner-up + 胜出理由 + 致命风险 + **缺失证据清单** + **最小必要实验 / 定理** | 必须给出「还差什么证据」 |

---

### 前置：D0—D9 与 pre / post 的映射（总收官审计 M-1 配套）

| 段 | 属于 | 说明 |
|---|---|---|
| D0—D3（证据台账 / claim graph / 科学分类 / anchor eligibility） | **R12-pre** | **但 `claims[]` 的创建在 R3**（见 [phase-r3-r6-discovery.md](phase-r3-r6-discovery.md) §R3.0）；本段只**复核与展开**，**不创建** |
| D4—D9（叙事实现 / 攻击面审核 / venue 校准 / 门禁 / 排序 / 输出） | **R12-post** | 只读已核实的 claim / evidence / 边界 / 失败 |

> ⚠️ **`claims[]` 不由本文件创建。** 若执行者在这里新建 `C`，会与 R3 的创建归属冲突，
> 并让 R7/R8 在第一轮读不到 claim。

## D0. Evidence Ledger

**输入：** idea 清单 + 方案（proposal）+ 已有实验 / 定理 / 文献。

**动作：**

1. 做前置完整性检查，缺项写进**待补充信息清单**。
2. 把每一条可用证据登记为独立条目，ID 为 `E1`、`E2`、…（**路线内唯一，不复用**）。
   每条写清：一句话陈述 + 来源（哪个实验 / 哪篇文献 / 哪条定理）+ `epistemic_status`。
3. 标 `epistemic_status`，并据此判定它能否进 `S5 Evidence Contract`。

**`epistemic_status` 五值（逐字复述 [claim-first-policy.md](claim-first-policy.md) §2，
本处不构成新定义）：**

| `epistemic_status` | 含义 | 可否进 `S5` |
|---|---|---|
| `Observed` | 已观察到的实验 / 数据事实 | ✅ |
| `Supported` | 有文献或既有理论支持 | ✅ |
| `Hypothesized` | 假设，未验证 | ❌（标注 `[待验证]`） |
| `Planned` | 计划中、尚未产生的证据 | ❌（标注 `[待补]`） |
| `Unknown` | 未知 | ❌（标注 `[待补]`） |

**产物：** 证据台账对应 State 的 `evidence[]`；展开表保存在叙事文档。

**硬约束：**

- **不得把 `Planned` 写成 `Observed`。** `Planned` 不得当作证据引用。
- 无证据的条目留 `[待补]`，**不得**用「预计」「预期会」补空。
- 措辞等级按 [evidence-policy.md](evidence-policy.md) §3 的
  「认知状态 ↔ 措辞等级映射」执行：`Hypothesized` / `Unknown` → **待核实**。
  本阶段 **不另立**措辞表。

---

## D1. Claim Graph

**输入：** 证据台账。

**动作：** 按固定节点 ID 写出 claim graph。每个节点必须挂证据或标 `[待补]`。

**节点 ID 与问题（逐字复述 [claim-first-policy.md](claim-first-policy.md) §3）：**

| ID | 问题 |
|---|---|
| `C0` | **Central claim**：本文最关键的科学主张是什么 |
| `C1` | 为什么这个问题重要 |
| `C2` | 现有工作具体在哪里不够 |
| `C3` | 为什么不够 / 边界在哪 |
| `C4` | 建立了什么**新知识** `K` |
| `C5` | 由此推出什么后果 |

**证据引用语法（逐字，不得改写）：** `C2 ← E3, E4`；无对应证据写 `C2 ← [待补]`。

**产物：** claim graph 对应 State 的 `claims[]`；本阶段的展开视图保存在叙事文档。

**硬约束：**

- **`C0` 必须一句话。** 写不成一句话，说明 claim 还没成形 —— 回到 D0 补证据或收窄 claim。
- 每个 `C_i` 无证据则标 `[待补]`；**不留空、不默认成立**。
- **只有 `Observed` / `Supported` 的 `E_j` 可以被引用。** 引用 `Hypothesized` /
  `Planned` / `Unknown` 条目属于证据夸大，直接触发 `G4`
  （[claim-first-policy.md](claim-first-policy.md) §3 硬规则 3）。
- `E_j` 编号**路线内唯一且不复用**；删除证据时不得把编号让给新证据。
- `C0` 必须能对应到证据；找不到对应证据的 central claim **不得进入投稿叙事**
  （这条在 D7 会被 `G1` 再判一次）。

**范例（跨域类，示意）：**

```
C0 ← E1, E2     在 Y 下现有方法因共享假设 X 而结构性失效；据此解除 X 是恢复能力的路径
C1 ← E4         该能力影响下游决策
C2 ← E1         现有方法共享假设 X，在 Y 下结构性失效
C3 ← [待补]     为什么内部修补无法突破（机制待补，触发 G3）
C4 ← E2         新知识 K：两领域共享结构 S，且满足迁移条件 C
C5 ← [待补]     后果需要最小必要实验（见 D9）

[待验证]（台账 E3，Hypothesized：不得进 S5，不得被任何 C_i 引用）
                解除 X 可恢复能力 —— 由 D9 的最小必要实验检验
```

---

## D2. Scientific Typing

**输入：** claim graph。

**动作：** 给该 idea 标定三轴 `(O, T, R)`，并标注贡献类型。
**枚举值一律用英文原样**（机器可读契约，不得意译，见
[writing-policy.md](writing-policy.md) §8 第 6 条）。
三轴枚举逐字复述 [claim-first-policy.md](claim-first-policy.md) §5，本处不构成新定义：

**`O` — Contribution Object：**
`Problem` | `Phenomenon` | `Theory` | `Method` | `Evaluation` | `Resource-System`

**`T` — Scientific Tension：**
`hidden-assumption` | `contradiction` | `shift-failure` | `infeasibility` |
`identifiability` | `evaluation-mismatch` | `unexplained-phenomenon`

**`R` — Resolution：**
`characterize` | `explain` | `prove` | `reformulate` | `design-algorithm` |
`build-benchmark` | `build-system`

**写法：** `(O=Method, T=hidden-assumption, R=design-algorithm)`。

**贡献类型：** 沿用 [venue-standards.md](venue-standards.md) §5 的贡献类型标注规范
（`General` / `Theory` / `Use-Inspired` / `Concept & Feasibility` / `Negative Results`），
枚举值以该文件为准；枚举外的派生物写进 frontmatter 的 `subtype`
（见 [project-layout.md](project-layout.md) §3.2）。

**central proposition 的形态（承重墙，取代「机制」）：**

> **任何叙事如果写不出一个明确、可证伪、且能对应到证据的 central proposition，
> 不得进入投稿叙事。**

| 论文类型 | central proposition 的形态 |
|---|---|
| 方法 | 某结构性限制导致现有方法在 `Y` 下失败，解除它可恢复能力 |
| 理论 | 在 assumptions `A` 下性质 `P` 成立 / 不成立 |
| 现象 | 控制变量后，现象 `P` 稳定存在 |
| Benchmark | 原评测 protocol 无法识别能力 `C` |
| 负结果 | 在条件 `Y` 下不存在同时满足 `P`、`Q` 的方法 |
| 跨域 | 两领域共享结构 `S`，且满足迁移条件 `C` |
| 临床 / Use-inspired | 实际 use case 的约束 `C` 会改变最优算法设计 |

**「机制」的降级（关键）：** 旧规则「第二段必须给机制性原因，写不出来叙事不成立」
**不再是全局承重墙**，降级为**方法类 / 跨域类**的子规则（体现在这两类的 `S4`）。
理由：研究实际走 `Observation → Hypothesis → Experiment → Mechanism`，
在 proposal 阶段强迫写「根本原因」，会把**待验证假设包装成已知原因**。
判定承重墙的是**命题可否被证伪**，不是机制是否已知。
（降级规则逐字见 [claim-first-policy.md](claim-first-policy.md) §4.2。）

> **两个「类型」不是一回事：** 上表的「论文类型」是 `C0` 的**命题形态**（含
> `跨域` 与 `临床 / Use-inspired`）；它们**不是** `O` 的枚举值
> （[claim-first-policy.md](claim-first-policy.md) §5 规则 4）。

**产物：** 叙事文档的 typing（含 `O` / `T` / `R` / `contribution_type` /
`central_proposition`）。

**硬约束：** 三轴枚举**逐字**取自 [claim-first-policy.md](claim-first-policy.md) §5；
`central_proposition` 字段不得留空。

---

## D3. Anchor Eligibility

**输入：** claim graph + typing。

**动作：** 对每个 anchor 给出资格结论。
**anchor 枚举沿用 [../SKILL.md](../SKILL.md) §0.1：** 理论 / 性能 / 现象 / 基准 / 可行性 / 负结果。
三值结论逐字复述 [claim-first-policy.md](claim-first-policy.md) §6，本处不构成新定义：

| 值 | 含义 |
|---|---|
| `eligible` | 证据台账直接支持该 anchor |
| `conditional` | 需补指定证据后才支持（**必须写明补什么**） |
| `not-eligible` | 现有证据不支持；**不得**据此 anchor 组织叙事 |

**硬规则（逐字，见 [claim-first-policy.md](claim-first-policy.md) §6）：**

> **作者的目标 anchor 是 prior（先验偏好），不是决定（decision）。**
> 流程为 `Evidence → Claim → Claim strength → Eligible anchors → Narrative`。

当作者的目标 anchor 与 `eligible` 集合冲突时，**必须显式告知**：

> 你想定位成 X，但现有证据支持的是 Y；最强可辩护 anchor 是 Y。

**不得**帮作者强化不被证据支持的故事。

**产物：** 叙事文档的 anchor eligibility（每个 anchor 一条：值 + 理由，
`conditional` 另附 `missing_evidence`）。

**硬约束：** `not-eligible` 的 anchor **不得**用于 D4 的 preset 选择与叙事组织；
冲突告知必须写进正式输出，不能只在心里判断。

---

## D4. Narrative Realization

本节原有动作和 D4.1–D4.5 属于 **D4a Scientific Narrative Search**。
2–4 套 hierarchy 的要求不变；每套另有 D4b 的四个表达变体，两种候选不能混计。
D4a 选择 central claim、claim hierarchy、scientific framing、preset、贡献顺序和
evidence mapping；它只组织 State 已有知识。D4.1 的 C0/K/scope 差异必须对应
不同的既有 claim，不得改同一 State 条目来制造候选。
独立的 **Rhetorical Realization Search** 见下方 D4b–D4d。

**输入：** `eligible` / `conditional` 的 anchor + claim graph + typing。

**动作：**

1. 按 [narrative-patterns.md](narrative-patterns.md) §2 用 `(O, T, R)` + eligible anchor
   选出候选 preset；锚点 → preset 映射表**只作参考**。
2. 生成 **2—4 套真正不同的 claim hierarchy**（不是同一 claim 的几种措辞）。
3. 每套按 [narrative-patterns.md](narrative-patterns.md) §3 写满六槽位 `S1—S6`。
4. 每套附「包装前后对照」（§D4.4）。

**产物：** 叙事文档的 presets 与 slots；State 只落 D9.5 的 view 描述符。

**硬约束：**

- **候选数 = 2—4 套。** 少于 2 套说明没做真正的对比；多于 4 套属于重复劳动。
- **必须是不同的 claim hierarchy：** 每套的 `C0` 不同，或支撑 `C0` 的 `C4`（新知识 `K`）
  不同，或 claim 的**范围**不同。**同一 claim 换四种措辞不算一套候选。**
- 每套必须写满六槽位，`S5` 必须给出 `Ci ← Ej` 对照 —— 否则该套不得进入 D5。
- **篇幅下限见 [roles.md](roles.md) §7**（D4 每套详写候选 ≥300 字）。本阶段不另立数字。
- **跨域类不强制写满四套**，但**必须做一次 anti-application stress test**
  （§D4.3）。
- **[../SKILL.md](../SKILL.md) §0.1 规则 3 不变：** `orthogonal` 路线仍不得进 R12。

### D4.1 什么算「真正不同的 claim hierarchy」

| 不同的方式 | 例 |
|---|---|
| `C0` 不同 | 一套讲「能力可在 `Y` 下恢复」，另一套讲「原评测无法识别该能力」 |
| `K` 的来源不同 | 一套的 `K` 来自理论刻画，另一套的 `K` 来自大规模实证边界 |
| claim 范围不同 | 一套声称「在 `Y` 下成立」，另一套只声称「在 `Y` 的某子条件成立但有普适推论」 |
| claim 强度不同 | 一套声称因果机制，另一套只声称稳定现象（**后者证据要求更低，可能更可辩护**） |

**选最强可辩护的那套，而不是听起来最大的那套。**

### D4.2 每套叙事的输出结构

```markdown
#### <idea_id> / <preset 编号 Nx> — <preset 名称>

**（1）claim hierarchy**
C0（central claim，一句话）：……
C1 / C2 / C3 / C4 / C5 与它的关系：……
本套与其余候选的**层级差异**在哪：……

**（2）六槽位**
S1 Context：……
S2 Tension：……（条件 Y 与缺口 G）
S3 Central Proposition：……（可证伪写法）
S4 Resolution：……
S5 Evidence Contract：C0 ← E1, E2；C1 ← E4；C2 ← E1；C3 ← [待补]；C4 ← E2；C5 ← [待补]
S6 Consequence & Boundary：改变了……；在……条件下不成立

**（3）preset 适配理由**
`(O, T, R)` = ……；使用的 anchor = ……（资格：eligible / conditional）。
该 preset 为何服务这套 hierarchy：……

**（4）贡献清单**（3—4 项，逐项标注**贡献类型**与**方法来源**）
- [方法] ……（方法来源：原创 / 部分原创 / 迁移）
- [理论] ……
- [实证] ……

**（5）为什么之前没人做**
至少一个具体理由：此前缺少技术条件 / 此前被某假设误导 / 此前问题未被定义 /
此前两领域缺乏交流。

**（6）该套的弱点**
诚实指出最容易被攻击的 1—2 个点。

**（7）包装前后对照**
改了哪个参照系 + 依据哪条 `Ci ← Ej`。
```

**方法来源**（`原创` / `部分原创` / `迁移`）必须标注且**可核验**；
把「迁移」包装成「原创」属于夸大（见 [../SKILL.md](../SKILL.md) §1.5）。

### D4.3 跨域类：anti-application stress test（强制）

**跨域类的目的不是「四套都成稿」，而是证明「把 B 用到 A」不是最准确的描述。**

- 至少测试 `N2 / N3 / N5 / N9` 四个 preset。
- 测试产物是一段**判定**：这四个 preset 中，哪个能把 `G` 与 `K` 写得比
  「B 恰好能解决 A 的问题」更准确；其余三个写出**被排除的理由**。
- 若四个 preset 都只能写成「把 B 用到 A」→ 该 idea 的 claim 层级还停在应用层，
  必须在 D9 里如实写出，且按 [narrative-patterns.md](narrative-patterns.md) §4
  的五步升级补 `Transfer Legitimacy Argument`（`L1 / L2 / L3` 一档）。

### D4.4 叙事包装：重新定位，不是夸大

**定义：** 叙事包装 = 在**不改变任何事实**的前提下，**改变读者理解该工作的参照系**。

**允许（重新定位）：**

下表是 **D4a 的科学 framing 候选**，不是同一句话可自由改写的等价关系。
新句涉及的失效条件、结构对应、统一关系或贡献类型必须已经由 State 支持。
冻结后不得用该表切换 contribution type、因果强度、范围或 central claim。

| 原始表述 | 重新定位后 | 改变了什么 |
|---|---|---|
| 我们提出了新模块 B | 现有方法依赖假设 X，我们**移除了 X** | 参照系：新增能力 → 解除限制 |
| 我们在数据集 A 上更好 | 现有方法在**条件 Y 下结构性失效** | 参照系：数值领先 → 失效条件 |
| 我们把 A 和 B 组合起来 | 我们建立了 A 与 B 的**结构对应**并给出 **Transfer Legitimacy Argument** | 参照系：工程拼装 → 理论联系 |
| 这是一个方法类工作 | 这是一个 **problem definition / theory** 类贡献 | 贡献类型归类 |
| 我们复现并改进了 X | 我们**统一了 X、Y、Z**，它们是本框架的特例 | 参照系：改进 → 统一 |

**严禁（这些是夸大，不是包装）：**

- ❌ 编造未做的实验、未证明的定理、未测的数字；
- ❌ 把「在 3 个数据集上有效」写成「普遍有效」；
- ❌ 把「部分重叠」写成「首次提出」；
- ❌ **把「迁移」写成「原创」**；
- ❌ 用「显著提升」「有效解决」替代具体数字与口径；
- ❌ 承诺**方案（R8 的 proposal）里没做**的事。

**判定标准（唯一、可机械执行）：**

> **包装后的每一句声称，都必须能在 claim graph 里找到对应的 `Ci ← Ej`。**
> 找不到对应证据的，就是夸大 —— 删除，或标注 `[待补]`。
> 详见 [narrative-patterns.md](narrative-patterns.md) §6 与
> [claim-first-policy.md](claim-first-policy.md) §3。

### D4.5 汇总格式

| idea | preset | claim hierarchy 一句话 | `(O,T,R)` | anchor（资格） | 层级差异 | 该套弱点 |
|---|---|---|---|---|---|---|
| I1 | N2 | …… | (Method, hidden-assumption, design-algorithm) | 性能（eligible） | …… | …… |
| I1 | N5 | …… | (Method, hidden-assumption, reformulate) | 性能（eligible） | …… | …… |

> preset 编号与名称**必须**取自 [narrative-patterns.md](narrative-patterns.md) §1
> 的十套表，不得自行改号或改名。**同时命中多个 preset 时，主叙事只写一个。**

### D4a. Claim-Hierarchy Realization 与冻结

完成上面的 2–4 套 hierarchy、六槽位和 stress test 后，逐套建立来源绑定的 manifest。
scientific audit 检查 14 项语义来源、closest prior delta、因果/统计解释及全部边界。
不因 rhetorical feedback 再挑更大的 claim 或改变 evidence interpretation。
manifest 的形状与例子见 [rhetoric-equivalence-policy.md](rhetoric-equivalence-policy.md) §1
和 [../examples/narrative-realization/manifest.json](../examples/narrative-realization/manifest.json)。

冻结 snapshot 同时锁定 State 除 narrative_view 外的全部内容、State version、hierarchy、
preset、anchor、contribution_order、evidence_mapping、S1–S6 和 14 项语义。
发现新 scientific gap 时先记 narrative_gap，退出此快照，交 R1/R8/R10 再重新冻结。
不得为让表达通过而向 State 增加 claim/evidence 或修改 uncertainty。

### D4b. Rhetorical Realization

先读 [rhetorical-operators.md](rhetorical-operators.md)，只使用登记的两个算子族：
evidence_framing、contribution_stance。每套 snapshot 固定一轮四 profile：neutral、
evidence-forward、contribution-forward、slightly-conservative。生成器是
[../scripts/rhetorical_realization.py](../scripts/rhetorical_realization.py) 的 generate 命令。

可前置已有比较/效果/interpretation、明确 actual contribution 与 prior delta；
不能改 metric、数值、aggregation、统计状态、conditions、certainty、causality、scope 或 novelty。
固定前部 boundary 面板，所有 profile 保留全部 assumptions/uncertainties/failures。
slightly-conservative 仅提醒原边界，不削弱或强化原 claim。
MVP 保留来源原句，通过标签和顺序搜索；不把自由 paraphrase 自动认定等价。

### D4c. Semantic-Equivalence Audit

**Rhetorical search 只能在 semantic equivalence class 内进行。**
每个 variant（含 neutral 和 perturbations）都运行
[../scripts/validate_rhetorical_variant.py](../scripts/validate_rhetorical_variant.py)：
RE1 来源冻结、RE2 语义冻结、RE3 白名单/预算、RE4 正文等价、RE5 boundary visibility。
任何 FAIL 都隔离该 variant；缺字段也 FAIL。正文比较是受限 renderer 的逐字审计，
不能仅检查 generator 自报 metadata。RE PASS 不替代原 G1–G5，也不证明 State 本身正确。

### D4d. Blind Claim-Recovery Probe 与 sensitivity

先持久化 evaluation_plan（至少两个不同 model ID，固定四 profile、一轮、阈值）。
独立 fresh judge context 只收到 probe-task 导出的正文和六问题；不给 snapshot、State、
profile、作者理由或其它 judge 的输出。该命令先执行 D4c，再导出盲 payload。
问题恢复 central_claim、main_contribution、closest_prior_work_delta、key_evidence、main_boundary、
unsupported_or_overstated_claims。adjudicator 再对冻结 truth 作 PASS/PARTIAL/FAIL 比较。

realization 选择的顺序：semantic PASS → 零 unsupported/错误解释 → 最差 Claim Recovery →
最差 Evidence Recovery → 最差 Novelty-Delta Recovery → 最差 Boundary Recovery →
低配对 fragility → 预登记 tie 顺序。不能通过隐藏 limitation 获益。
任一模型的任一恢复维度 FAIL 的 variant 不推荐；全部失败则 NO_ELIGIBLE_VARIANT。
不读 overall score；D8 的六维仍比较 scientific hierarchy，不被该排序替换。

sensitivity 在相同 snapshot/profile/judge 面板上计算 paired range、variance、disagreement。
恢复从 FAIL 到 PASS 的大幅变化、错误 novelty/central interpretation 或可选 scientific judgment
类别变化标 RHETORICALLY_FRAGILE。缺失/重复/错 snapshot 数据标 INCOMPLETE，不判稳定。
同一模型不同角色不能代替多模型；LLM 结果是 T0，不声称真人 reviewer consensus。
操作模板见 [../templates/narrative-realization.md](../templates/narrative-realization.md)。
真实模型不可用时保留已有科学 hierarchy，声明 probe INCOMPLETE，不推荐“最佳 rhetorical wording”。

**Anti-reward-hacking：** Strength visibility optimization, not weakness laundering.
禁止追 overall score、弱化 limitation、夸大 novelty/scope、堆积极形容词、单模型定向优化或
无界 recursive reviewer hill-climbing。盲评发现科学问题只作为 gap 交 Assurance，不自动改 State。

---

## D5. Adversarial Review

**输入：** D4 产出的每一套叙事（含 claim hierarchy 与六槽位）。D4b 的 realization
必须经过 D4c；D4d 的恢复结果和 fragility 单列，不能替代本阶段科学审核。

**动作：** 把每套叙事提交给**六个攻击面审稿人**独立审查 ——
**六人全部派遣，不得裁减**；**`S-Lit` 恒派**；**`S-Devil` 必派但不打分**（它只出弱点与反例）；
`S-Nov` / `S-Feas` / `S-Repro` 按需。
**会议审稿人（`R-CVPR` / `R-ICML` / `R-NeurIPS` / `R-MICCAI`）不作为 D5 的主审**
（见 §D6）。

**派遣方式：** 环境有 Team 能力时**必须先询问用户**是否使用 Team；
用户显式要求但环境不具备时须**显式回退**并告知
（见 [../SKILL.md](../SKILL.md) §3.1 与 [roles.md](roles.md) §4.1 派遣方式）。

| 角色 | 专门攻击 | 输出 |
|---|---|---|
| `R-Novelty` | 最近工作是否已做过？delta 是否非平凡？ | 该攻击面 `1—5` 判定 + 最接近先前工作 + 意见 |
| `R-Causal` | 所谓机制是否只是相关性 / 事后解释？ | 该攻击面 `1—5` 判定 + 竞争解释清单 + 意见 |
| `R-Experimental` | baseline、公平性、confounder、统计功效 | 该攻击面 `1—5` 判定 + 缺失对照清单 + 意见 |
| `R-Theory` | assumptions、proof、tightness、definition | 该攻击面 `1—5` 判定 + 假设 / 定义缺口 + 意见 |
| `R-Generalization` | claim scope 是否超出证据 | 该攻击面 `1—5` 判定 + 越界声称清单 + 意见 |
| `R-Utility` | 即使正确，谁会在意？改变了什么？ | 该攻击面 `1—5` 判定 + 受影响决策 + 意见 |
| `S-Lit` | 文献定位核验（**恒派**） | L3 穷尽结论 + 最接近先前工作（≥5 篇）+ 负检索记录，**不打分** |
| `S-Nov`（按需） | 独立新颖性核验（`S-Lit` 判「边缘」或涉「首次」时） | 核验结论，**不打分** |
| `S-Repro`（按需） | 可复现性核对 | 核对结论 + 风险清单，**不打分** |
| `S-Feas`（按需） | 概念可行性 / 资源与预算核对 | 核对结论，**不打分** |
| `S-Devil` | 敌对审查 | **致命弱点清单（≥3 条）+ 最简解释反例**，**不打分** |

### D5.1 打分 / 不打分的边界（强制）

1. **六个攻击面审稿人各给一个该攻击面的 `1—5` 判定**（同向：`5` = 该攻击面不构成阻塞，
   `1` = 该攻击面致命）。判定必须附**具体证据**（哪条实验缺失、哪篇引用、哪个逻辑缺口）。
2. **这些攻击面判定不进任何向量、不做中位数、不做加权平均。** 它们只用于两处：
   `D7` 门禁的证据，以及 `D8` 逐维理由的依据。排序的唯一标尺是 D8 的六维。
3. **不打分角色：** `S-Lit` / `S-Nov` / `S-Repro` / `S-Feas` / `S-Devil` 一律**不产生
   `1—5` 分，不进任何向量**。它们出**事实与类别结论**，或出**弱点清单与反例**。
4. **`S-Devil` 的弱点与反例必须被逐条处置：** 接受（转成缺失证据或门禁命中）
   或反驳（附证据）。**不得静默丢弃。**
5. **不得声称「reviewer consensus」。** 六个审稿人不是独立样本（同一基础模型换 prompt，
   `corr ≫ 0`），因此「六人都同意」不构成共识证据（见
   [scoring-policy.md](scoring-policy.md)）。

> **评分标尺**沿用 [scoring-policy.md](scoring-policy.md) §1 的五级锚点；
> 统一输出骨架见 [roles.md](roles.md) §5，各攻击面角色的定义见 [roles.md](roles.md) §1B，
> 派遣矩阵见 [roles.md](roles.md) §4.2，意见字数下限见 [roles.md](roles.md) §7
> （各子代理意见 ≥200 字，`S-Devil` ≥250 字）。

### D5.2 各攻击面的审核指令

**`R-Novelty`：**
- 该叙事的 `C2`（现有工作不够）是否**点名了最接近的工作**并说清 delta？
- 若声称原创，delta 是**机制层面**的，还是**组合 / 调参层面**的？
- `S-Lit` 的结论是「部分重叠」时，重叠的部分是否被诚实标注？

**`R-Causal`：**
- `C3`（为什么不够）给的是**已证原因**还是**待验证假设**？两者是否被混写？
- 若声称机制，是否存在**同样能解释数据的更简解释**？（`S-Devil` 的最简解释反例在此对接）
- 相关性证据是否被当成因果声称？

**`R-Experimental`：**
- 方案里的 baseline 是否覆盖**最强**对手？比较是否同算力 / 同数据 / 同调参？
- 是否存在 confounder（数据泄漏、评测集重叠、超参搜索预算不对等）？
- 声称的效果是否有**统计功效**支撑？不确定性是否报告？

**`R-Theory`：**
- central proposition 的 assumptions 是否写全？证明是否闭合？
- 定义是否自洽？界是否**紧**（tightness）？假设是否必要？
- 跨域类的 `Transfer Legitimacy Argument` 达到 `L1 / L2 / L3` 的哪一档，
  证据强度是否与声称的贡献等级匹配？

**`R-Generalization`：**
- `S6` 写出的边界是否与证据覆盖范围一致？有没有 `S6` 没提但正文声称的范围？
- 单数据集 / 单中心结论是否被写成普遍结论？
- 结论换到分布外 / 换设备 / 换人群时，哪些声称会失效？

**`R-Utility`：**
- 若该 claim 成立，**哪一个下游决策会改变**？答不出说明 `C1` 没写实。
- 影响面是方法层、评测层，还是临床 / 部署层？
- 与「把 B 用到 A」相比，该 claim 是否提供了任何 A 领域可复用的知识？

**`S-Devil`（不打分）：**
- 若该叙事存在一个无法修复的根本缺陷，最可能是什么？
- 声称的「结构性缺口」是否只是对已有工作的**重新包装**？
- 最简解释反例：有没有一个**更简单**的假设能解释同一批证据？
- 是否可能被一个**简单 baseline**击败？
- 输出：**致命弱点清单（≥3 条）+ 最简解释反例**，逐条标注它威胁哪条 `Ci`。

### D5.3 `S-Lit` 的文献检索规则（强制）

`S-Lit` 遵守 [literature-policy.md](literature-policy.md) 的**全部**规则：

- **先本地、后多源；本地命中不是终点** —— 新颖性核实属 T1/T4 触发场景，
  **必须查全部启用源**，本地命中不得作为终止条件。
- 429 指数退避 `10s → 20s → 40s → 80s → 160s`，最多 5 次，退避期间不发新请求；
  失败则回退本地结果并**标注检索未达饱和**。
- 结果缓存到 `./docs/refs/cache/<source>/`；每条标注
  `sources=["local" | "arxiv" | "openalex" | "crossref"]`。
- 新颖性核实必须达到 **L3 穷尽检索**并附**负检索记录**；未达标时结论只能写
  **「据本次检索未见 · 待核实」**，且**不得**认定「确认新颖」。

### D5.4 交叉质询

每套叙事**至少经历一轮**交叉质询。

1. **每个攻击面审稿人必须对至少一个其他攻击面的意见提出质疑或补充。**
2. **攻击面判定相差 ≥2 分**时，记录分歧点并尝试**用证据**协商；无法收敛的标注
   **「存在评审分歧」**。
3. **分歧与结论并存**：分歧单列，不得被任何聚合掩盖。
4. **不做中位数、不做平均、不做一票否决** —— R12 的否决权在 D7 的门禁，
   排序在 D8 的六维。

### D5.5 汇总表

| idea | preset | R-Novelty | R-Causal | R-Experimental | R-Theory | R-Generalization | R-Utility | S-Devil 弱点条数 | S-Lit 结论 | 分歧项 |
|---|---|---|---|---|---|---|---|---|---|---|
| I1 | N2 | … | … | … | … | … | … | … | 部分重叠 | … |
| I1 | N5 | … | … | … | … | … | … | … | 据本次检索未见 · 待核实 | … |

> **`S-Lit` 恒派。** 若因**不可用**（如在线源不可用）而确实未派 `S-Lit`，
> 该列填 **「未核验」**，且该叙事的新颖性结论**不得**标为「确认新颖」，
> 只能写「据本次检索未见 · 待核实」。
>
> **各攻击面的读数归属（哪个攻击面喂哪个排序维度、联动哪道门禁）见 §D8 的表。**

---

## D6. Venue Calibration

**输入：** D5 的评审结果 + D2 的 typing。

**动作：** 对每套叙事判定**最适配会议**（CVPR / ICML / NeurIPS / MICCAI）。
判定顺序固定为 **`contribution type → evidence contract → venue calibration`**，
判据以 [venue-standards.md](venue-standards.md) §10（含 §1—§4 的会议标准条目）为准。
**顺序不得倒置**（[venue-standards.md](venue-standards.md) §10.0 硬规则）。

| 会议 | 校准时看什么（细节以 [venue-standards.md](venue-standards.md) 为准） |
|---|---|
| CVPR | 方法落地、技术正确性、可复现性；方法贡献是否实质 |
| ICML | soundness / presentation / significance / originality 的拆分；理论或广义原创性 |
| NeurIPS | 按 contribution type 校准（不同贡献类型各有门槛） |
| MICCAI | 方法学创新 **或** 应用创新；临床相关性与验证严谨性；数据许可与伦理合规 |

**硬约束：**

- **按 contribution type 校准，不按 venue 选 preset。** 会议只影响「这份 claim 是否
  落在该会议范围内」，**不影响** D4 已经确定的 claim hierarchy。
- **`clinical significance ≠ methodological innovation`**，两者**不得互相冒充**。
- **本阶段不派遣会议审稿人。** `R-CVPR` / `R-ICML` / `R-NeurIPS` / `R-MICCAI`
  四个角色留给 R3—R6 / R8 / R7 / R10 / R13（见 [roles.md](roles.md) §4.2）；
  D6 只在**校准**意义上使用会议标准。**派遣名单仍以 §D5 的六个攻击面审稿人为准。**
- 校准结论与 `G5 Venue scope` 联动：贡献对象与 venue 明显不匹配 → `G5` 记 `fail`。

**产物：** 每套叙事的会议适配判定 + 理由 + 不匹配时的处置建议
（换会议 / 收窄 claim scope / 补证据 / 退回 R3—R6）。

---

## D7. Hard Gates

**输入：** 每套叙事 + D5 的攻击面意见 + `S-Lit` / `S-Devil` 的结论。

**动作：** 逐项判定 `pass` / `fail`。**门禁不打分、不聚合、不平均。**
门禁定义与判定机制以 [scoring-policy.md](scoring-policy.md) §3 为唯一权威。

| Gate | Fail 条件 |
|---|---|
| `G1 Claim grounding` | central claim 找不到对应证据 |
| `G2 Prior-work distinction` | 与最近工作没有明确的 delta |
| `G3 Identification` | 实验 / 证明不能识别所声称的机制 |
| `G4 Factual integrity` | 定理 / 实验 / 结果被叙事夸大 |
| `G5 Venue scope` | 贡献对象与 venue 明显不匹配 |

**判定值与后果：**

- 判定值只有 `pass` / `fail`。
- **任一 `fail` ⇒ 该套叙事标 `not_submission_ready`**，**不得推荐为最佳**，
  且**不参与 D8 排序**。
- 门禁失败**不得**用高分抵消，**不得**走「带条件的推荐」出口
  （该出口只适用于 R7 / R10 / R13 的维度否决，见 [scoring-policy.md](scoring-policy.md) §5.1）。

**产物：** 叙事文档的 gates 表；不新增 State 顶层字段。

| idea | preset | G1 | G2 | G3 | G4 | G5 | 结论 |
|---|---|---|---|---|---|---|---|
| I1 | N5 | pass | pass | pass | pass | pass | 可排序（全 `pass`） |
| I1 | N2 | pass | pass | fail | pass | pass | `not_submission_ready` |

---

## D8. Ranking

**输入：** **通过门禁**的叙事（门禁失败者不参与排序）。

本节只比较 D4a 的科学 hierarchy。D4d 只在同一冻结 hierarchy 内选择表达，
不改变本节六维，也不让“好理解”替证据不足的主张通过 G1–G5。

**动作：** 对每套通过门禁的叙事，按**六维**给 `1—5`，并写**逐维理由**。
六维的定义与标尺以 [scoring-policy.md](scoring-policy.md) §4 为唯一权威；
`1—5` 标尺沿用该文件 §1 的五级锚点。

| 维度 | 问题 | 读数归属（攻击面 → 维度） | 联动门禁 |
|---|---|---|---|
| `Significance` | 若成立，改变了什么？谁会在意？ | `R-Utility` | `G5` |
| `Originality` | 相对最近工作的 delta 是否非平凡？ | `R-Novelty`（辅以 `S-Lit` 的核验结论） | `G2` |
| `Soundness margin` | 证据到 claim 的余量（识别、baseline、统计、假设） | `R-Experimental`（实验侧读数）与 `R-Theory`（理论侧读数），**两个读数并存，不得平均** | `G3` / `G4` |
| `Explanatory depth` | 是解释，还是事后叙述？ | `R-Causal` | `G3` |
| `Generality` | claim scope 与证据覆盖是否匹配 | `R-Generalization` | `G1` / `G5` |
| `Narrative compression` | 是否用最短的叙事让审稿人正确理解 claim | **无专属攻击手** —— 由汇总者依六槽位与六份攻击报告给出 | — |

**硬约束：**

- **六维全部同向（高 = 好）。R12 没有反向维度，因此不使用极性归一化。**
  极性归一化仅适用于仍含反向维度的阶段（当前为 R7 / R10 / R13），
  见 [scoring-policy.md](scoring-policy.md) §2 的适用范围限定。
- **不做跨审稿人逐维中位数，不折算单一综合评分。** 六个审稿人不是独立样本
  （`corr ≫ 0`），聚合出的中位数或总分是伪精确。
- **`Soundness margin` 的两个读数并存，不得平均。** 实验侧与理论侧各自成立或各自缺失。
- **排序 = 逐维比较 + 显式写出胜负维与代价维**（哪一维赢、哪一维付出代价），
  而不是给一个总分排名。
- **逐维理由必须引用具体依据**（哪条 `Ci ← Ej`、哪条攻击面判定、哪条 `S-Devil` 弱点），
  不得只写「创新性最高」。
- **不得只看 `Originality`。** 六维必须全部给出；缺失维度视为排序无效。
- **门禁失败（`not_submission_ready`）的候选不进排序**（§D7）。

**产物：** 叙事文档的 ranking；不新增 State 顶层字段。

**反模式（出现即视为违规）：**

- ❌ 把门禁失败的叙事放进排序表；
- ❌ 只按 `Originality` 排序；
- ❌ 忽略 `S-Lit` 的「已被覆盖」结论或 `S-Devil` 的致命弱点；
- ❌ 用平均值掩盖极端低分；
- ❌ 对攻击面判定做中位数后当作排序分。

---

## D9. Output

**输入：** D4—D8 的全部产物。

**动作与产物：** 按以下五节输出。

### D9.1 交付内容（六项，缺一不可）

1. **最佳叙事** —— preset + 完整六槽位 + claim hierarchy。
2. **runner-up** —— 次优叙事及其落败维度（**也必须通过门禁**；门禁失败的候选不参与排序，
   只能进「致命风险」与缺失证据清单）。
3. **胜出理由** —— **逐维**说明为什么它胜出（引用依据），不得只写一句话。
4. **致命风险** —— 最可能被攻击的点 + 缓解策略；`S-Devil` 未处置的弱点一律列出。
5. **缺失证据清单** —— 所有 `Ci ← [待补]` 条目，逐条写明缺什么证据、
   它威胁哪条 claim、当前措辞等级。
6. **最小必要实验 / 定理** —— 把缺失证据转成可执行的最小补齐方案：
   做哪个实验 / 证哪个命题、用什么数据与基线、判定成功的标准是什么。
   **必须给出「还差什么证据」，不得只给结论。**

以上六项不变。每套 scientific hierarchy 另附 realization snapshot ID、RE 结果、
四维恢复、固定 judge 面板、sensitivity、失败变体与 rejected reasons。
RHETORICALLY_FRAGILE 和 INCOMPLETE 必须随推荐保留，不用高 overall score 覆盖。

### D9.2 推荐汇总表与最终建议

| idea | 最佳 preset | 六维（S/O/SM/ED/G/NC） | 胜负维 | 代价维 | 最适合会议 | 最大优势 | 最大风险 | runner-up | 门禁 |
|---|---|---|---|---|---|---|---|---|---|
| I1 | N5 | 4/4/3/4/3/4 | Explanatory depth | Soundness margin | ICML | … | … | 无（N2 门禁 `fail`，不参与排序） | N5 全 `pass` |

最终建议必须明确回答三件事：

1. **哪个 idea 的 claim hierarchy 最成熟，最值得优先投入？**
2. **哪个 idea 的叙事存在无法修复的根本缺陷？**
3. **哪个 idea 如果换一种 claim hierarchy，可能获得更高价值？**

**退回规则：** 某 idea 的所有候选叙事均 `not_submission_ready`，或六维普遍 ≤ 2
→ 建议**退回 R3—R6** 重新生成 idea（并在 `STATUS.md` 的 Next recommended actions 里留任务）。

**合并规则：** 两个 idea 的**最佳叙事高度相似** → 考虑**合并或差异化定位**。

### D9.3 写作约束（强制）

- 所有引用给出具体出处，格式 `[作者, 会议/年份]`。
- 所有「首次提出」声称**必须先标注「待核实」**；保留的前提是三件事齐备：
  ① 已完成 **L3 穷尽检索**（§D5.3 / [literature-policy.md](literature-policy.md) §3.1）、
  ② 经 `S-Lit` 核实、③ 附**负检索记录**。缺一只能写「据本次检索未见」。
  **措辞等级统一见 [evidence-policy.md](evidence-policy.md)**（本阶段不另立措辞表）。
- 叙事必须回答**「为什么之前没人做」**。
- **禁止**「显著提升」「有效解决」「泛化性不足」等无信息量表述
  （见 [narrative-patterns.md](narrative-patterns.md) §5）。
- **包装只允许改变参照系，不允许改变事实**（§D4.4）；每句声称都要落回 `Ci ← Ej`，
  否则删除或标 `[待补]`。
- 信息不足处明确标注 **`[待补]`**，**不得编造**。
- **仅输出 claim、叙事分析与审核报告**，不添加前言、说明或评论。

### D9.4 文档落盘与状态更新（强制）

1. **写文档：** `routes/<R>/docs/<R>NNN-narrative.md`（一次调用一份）。
   ID 按 [project-layout.md](project-layout.md) §2.6 扫描现有最大序号 +1；
   落盘路径与命名规范见 [project-layout.md](project-layout.md) §2.1。
   内容 = 证据台账 + claim graph + typing + anchor eligibility + 2—4 套叙事
   （每套 claim hierarchy + 六槽位）+ 攻击面评审意见 + 交叉质询记录 + 门禁表
   + 六维排序 + 最佳叙事推荐 + 缺失证据清单 + 最小必要实验 / 定理 + 最终建议。
2. **frontmatter：** `id / route / phase: R12 / type: narrative / status / created`。
3. **更新该路线 `INDEX.md`（资产目录）**（章节规范见
   [project-layout.md](project-layout.md) §4.1）：`Key Documents` 与 `Reviews` 新增本文件行。
4. **更新该路线 `STATUS.md`（当前状态）：** 先写回 `research-state.json`，再重新生成。
   - `S-Lit` 确认新颖、且通过全部门禁的叙事方向 → **Strongest supported findings**；
   - 被 `S-Lit` 判「已被覆盖」、或因结构性缺陷无法成立的候选 → **Most important negative findings**；
   - **门禁 `fail` 的候选**、**存在评审分歧**的项、**未完成 L3 的「首次提出」声称**、
     **未核验的新颖性结论** → **Critical uncertainties**；
   - **退回 R3—R6 / 换 claim hierarchy 重试 / 按最佳叙事重写提案 /
     补齐缺失证据清单** → **Next recommended actions**。

### D9.5 输出后：写回 Research State

**结论：R12 只写 `narrative_view`（+ 必要时新增 `uncertainties[]`）。叙事正文是**文档**，不是 state。**

**载体划分（不得混淆）：**

| 产物 | 落点 | 类型 |
|---|---|---|
| 叙事正文（六槽位、preset 选择理由、`G1—G5` 判定、六维读数与排序） | `routes/<R>/docs/<R><NNN>-narrative.md` | **文档**（人的读物） |
| 叙事**视图描述符**（选了哪些 preset、渲染了哪些 claim、保留了哪些失败实验） | state 的 `narrative_view` | **state** |
| 攻击面审稿人的五元组 | `assurance[]`（R7 写）／`reviews[]`（R13 写） | **state** |
| 叙事暴露的新缺口 | `uncertainties[]`（`status: open`） | **state** |
| 冻结快照、manifest、variants、plan、blind responses、recovery、sensitivity | `routes/<R>/narrative-realization/<doc-id>/` | 叙事文档的配套 **artifact**；不新增 State 顶层字段 |

**`narrative_view` 四键（逐字，取自模板）：**

| 键 | 类型 | 说明 |
|---|---|---|
| `presets_selected` | 字符串数组 | 本次叙事选用的 preset（`N1`—`N10`） |
| `rendered_claims` | `C` id 数组 | 被渲染进叙事的 claim |
| `failed_experiments_kept` | `F` id 数组 | **失败实验必须保留**（不得从叙事消失） |
| `note` | 字符串 | 视图说明 |

**R12 收工要写的那部分（字段形状合法）：**

> 已实测：把下列内容**并入一份完整 state** 后，`state_check.py --check` 退出码 **0**。
> **片段本身不是完整 state**（缺八类数组），不能单独喂校验器。

```json
{
  "state_version": 3,
  "narrative_view": {
    "presets_selected": ["N5", "N2"],
    "rendered_claims": ["C1", "C2", "C4"],
    "failed_experiments_kept": ["F1"],
    "note": "主线 N5（统一框架），N2 作辅助表述；G3 未过的候选不参与排序"
  },
  "uncertainties": [
    {
      "id": "U9",
      "question": "迁移合法性只有 L1 级举证，是否充分？",
      "importance": "high",
      "uncertainty": "medium",
      "cheapest_discriminating_test": "TBD",
      "status": "open",
      "depends_on": ["C4"],
      "validity": {"status": "valid", "reason": "叙事阶段暴露的新缺口", "since_state_version": 3}
    }
  ]
}
```

**硬规则：**

1. **R12 不得新建 `claims[]` / `evidence[]` / `hypotheses[]`。** 叙事写作最容易发生「为了故事成立补一条未经验证的 claim」——
   若叙事确需新 claim，**只能**产出 `uncertainties[]`（新缺口）或标 `narrative_gap`，**回 R1 / R8** 处理。
2. **R12 不得提高任何既有条目的 `epistemic_status` 或 `claims[].status`。**
3. **`narrative_view` 是唯一的 state 写入**（除新增 `uncertainties[]` 外）。
4. **禁止**在 state 里出现下列槽位 —— 它们**在 schemas 中没有载体**，
   写了即违反 [research-state-policy.md](research-state-policy.md) §3「未在本节出现的字段 = 未定义字段」：

   `phase` / `route` / `timestamp` / `doc_id` / `target_venue` / `core_goal` /
   `evidence_ledger` / `claim_graph` / `typing` / `anchor_eligibility` /
   `presets` / `slots` / `attack_surfaces` / `gates` / `ranking`

   **这些含义仍然存在**，但各有载体：

   | 含义 | 真正的载体 |
   |---|---|
   | `phase` / `route` | route 目录与 `routes/<R>/README.md` |
   | `doc_id` | 叙事文档的 frontmatter |
   | `target_venue` / `gates` / `ranking` / `slots` / preset 选择理由 | **叙事文档正文** |
   | `attack_surfaces` | `assurance[]`（R7）/ `reviews[]`（R13） |
   | `core_goal` | `contract.primary_anchor` |
   | `evidence_ledger` | `evidence[]` |
   | `claim_graph` | `claims[]`（**数组**，不是按 `C0..C5` 做的字典） |

5. **判据（Carrier Completeness）：** 任何规则要求「产出 / 记录 / 持久化 X」，
   就必须同时存在 **`Producer(X)` + `Carrier(X)` + `Consumer(X)`**；三者缺一即为缺陷。

6. **冻结后的 D4b–D4d 只允许更新既有 narrative_view 描述符。**
   旧 R12 的新增 uncertainty 权限只适用于退出快照后的 gap 处理；冻结期间不行使。
   描述符仍四键，note 可引用 `<doc-id>/snapshot/variant`，原始正文与评测不塞进 State。

## 定位补充：Narrative 是 Research State 的视图

**叙事不创造事实，只呈现 state。** 硬规则：

- 叙事里的每句声称必须能落回 `Ci ← Ej`；找不到的删除或标 `[待补]`。
- **`failures[]` 里的失败不得在叙事中消失**（`state_check.py` V4 是它的机械前置）。
- Wave 3 将拆成 **R12-pre**（只能写「若 H 被验证，可能成立的 thesis 是…」，**不得决定研究方向**）
  与 **R12-post**（只读已核实的 claim graph / evidence ledger / boundary / negative findings）。

---

## R12-pre / R12-post（Wave 3 拆分）

**叙事不得反过来决定研究方向。** 因此拆成两个子阶段，输入输出边界是硬约束：

| 子阶段 | 何时 | 能做什么 | **不能做什么** |
|---|---|---|---|
| **R12-pre** | R8 之后、R9 之前 | 只写「**若 `H` 被验证，可能成立的 thesis 是…**」；产出一份**预期叙事草稿**（不落 `narrative_view`） | **不得决定研究方向**；不得据此筛候选、排实验优先级；不得写进 `narrative_view` |
| **R12-post** | R11 之后 | 只读**已核实**的 `claims[]` / `evidence[]` / `S6` 的边界 / **`failures[]`**；此时才用 `N1`—`N10` 选 preset 并落 `narrative_view` | **不得新增 `evidence[]`**；**不得提高既有条目的 `epistemic_status`**；`failures[]` 不得在叙事中消失 |

**R12-post 的三条硬规则：**

1. 每句声称必须能落回 `Ci ← Ej`；找不到的删除或标 `[待补]`。
2. **包含 `failures[]`** —— 失败实验是叙事的一部分（V4/V12 是机械前置）。
3. 综合评分 < 3 或门禁 `fail` 的候选**不得**被包装成推荐叙事（Wave 1 已冻结）。

**判断 pre/post 是否越界的机械问法：** 「这条产物里的信息，能让某一轮 `R3`/`R9` 改变选择吗？」
**能** ⇒ 它属于 pre 的**输入侧**（即不得由 pre 自己决定）；**不能** ⇒ 它是纯视图。

## 读 / 写 World Model（强制）

| 阶段 | 读 | 写 |
|---|---|---|
| **R12** | `claims` / `evidence` / `failures` / `uncertainties` | `narrative_view`（+ 必要时新增 `uncertainties`） |

> 权威定义见 [research-state-policy.md](research-state-policy.md) §5；本节与它**必须逐字一致**。
> 回写后跑 `python3 scripts/state_check.py --check .research-idea-pipeline/routes/<R>/research-state.json`，**硬违规须为 0**。
