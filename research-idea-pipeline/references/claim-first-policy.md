# Claim-first 政策（claim 层规则的唯一权威定义）

**本文件是 claim 层规则的唯一权威定义。** 证据台账、claim graph、central proposition、
`(O, T, R)` 三轴与 anchor eligibility 的规则都写在这里。各 R 阶段 只引用本文件，不重复定义
——各自再写一遍枚举就是新的漂移源。

**适用范围：** 本轮（P0）由 **R12** 执行本文件全部规则。R3—R6 / R8 / R7 / R10 / R13 的接入登记为
**P1**，本轮不执行。

**权威顺序：** 仓库级 spec（`docs/claim-first-spec.md`，不进安装副本）
> 本文件（claim 类） > [scoring-policy.md](scoring-policy.md)（评分类） >
[venue-standards.md](venue-standards.md)（会议类） > 各 R 阶段 文件。
本文件与 spec 冲突时**以 spec 为准**，**不得**自行解释或放宽。

> **记法警告：** 本文件的 `A` / `B` 是**领域占位符**（A = 目标领域，B = 来源领域），
> **与已退役的 A/B/C/D/E 阶段字母无关**。`Y` = 条件，`G` = 可验证的缺口，`K` = 本文建立的新知识，
> `X` = 作者口头想定位的锚点。这套记法与 [narrative-patterns.md](narrative-patterns.md) 一致。

---

## 1. 总纲：先定 claim，再定故事

**结论：叙事质量由三个因子相乘决定，任一因子为零则叙事为零。**

**哲学（逐字）：**

> **找到「在现有证据下最强但不过度」的科学主张，然后找到最短的故事使审稿人正确理解
> 该主张。**

**核心公式（逐字）：**

```
Narrative quality = Claim strength × Evidence alignment × Reviewer comprehensibility
```

| 因子 | 含义 | 由谁保证 |
|---|---|---|
| `Claim strength` | 主张本身有多强 | §2 的证据台账 |
| `Evidence alignment` | 主张与证据的对应关系 | §3 的 `Ci ← Ej` 对照 |
| `Reviewer comprehensibility` | 审稿人读懂该主张的成本 | [narrative-patterns.md](narrative-patterns.md) 的 preset 与六槽位 |

**已淘汰的旧公式：** `Narrative quality = Novelty impression`。它**不得**再作为任何文件的
总纲出现。新颖性不再充当叙事的目标函数，改由 `G2` 门禁（[scoring-policy.md](scoring-policy.md)
§3）与攻击面审稿人 `R-Novelty`（[roles.md](roles.md) §1B）承担。

### 1.1 顶层总纲：写 `G` 与 `K`，不要求有 `B`

**结论：所有 R 阶段的叙事层必须能写出 `G` 与 `K`。要求「必须有 B」的旧规则一律作废。**

**新总纲（逐字）：**

> 现有**理解 / 能力 / 评测**在条件 `Y` 下存在一个**可验证的缺口** `G`；
> 本文建立**新的知识** `K`，用于解释、界定或消除 `G`。
> **`B → K`（从来源领域引入）只是产生 `K` 的一种方式。**

| 项 | 含义 | 必须回答的问题 |
|---|---|---|
| `Y` | 条件 | 在哪个条件下出现缺口？ |
| `G` | 可验证的缺口 | 缺口对应哪条证据 `E_i`？ |
| `K` | 新知识 | 本文新增了什么可被他人使用或检验的知识？ |

**硬规则：**

1. **`B → K` 只是产生 `K` 的一种方式。** 「A 领域存在结构性缺口，B 恰好补上该缺口」
   **降级**为**跨域场景专用**写法（见 [narrative-patterns.md](narrative-patterns.md) §4），
   **不得**再作为全局总纲。
2. `N4`（现象）、`N8`（评测）、`N10`（负结果）**不需要也不得**硬塞一个 `B`。
   凡要求「必须有 B」的规则一律作废，改为「必须能写出 `G` 与 `K`」。
3. 写不出 `G` 或 `K` 的叙事**不得**进入投稿叙事（承接 §4 的承重墙）。

**引用本节的阶段：** R12（D4 定位与 §1 因子分解）。R3—R6 / R8 / R7 / R10 / R13 为 P1。

---

## 2. 证据台账：先定 `epistemic_status`，再引用

**结论：每条证据在进入 claim graph 之前，必须先定认知状态。状态决定它能不能被引用。**

证据台账是 D0 的产物，输入是 idea + 方案 + 已有实验 / 定理 / 文献。每条证据记一个
`E_i` 与一个 `epistemic_status`。台账条目的**最小字段**是 `E_i` 与 `epistemic_status`，
其余列只作说明，**不得**据此新造字段名。

| `epistemic_status` | 含义 | 可否进 Evidence Contract（`S5`） |
|---|---|---|
| `Observed` | 已观察到的实验 / 数据事实 | ✅ |
| `Supported` | 有文献或既有理论支持 | ✅ |
| `Hypothesized` | 假设，未验证 | ❌（标注 `[待验证]`） |
| `Planned` | 计划中、尚未产生的证据 | ❌（标注 `[待补]`） |
| `Unknown` | 未知 | ❌（标注 `[待补]`） |

**硬规则：**

1. **不得**把 `Planned` 写成 `Observed`。
2. **只有** `Observed` / `Supported` 可以进 `S5`，也**只有**它们可支撑确定性表述。
3. `Hypothesized` 条目**必须**标 `[待验证]`，`Planned` / `Unknown` 条目**必须**标 `[待补]`。
4. 没有证据的条目留 `[待补]`，**不得**用模糊表述顶替（例如「已有初步结果」）。
5. `epistemic_status` 取值只有上表五个，**不得**新增或改写（机器可读契约）。

### 2.1 认知状态 ↔ 措辞等级映射（只做映射，不新立等级）

**结论：五值认知状态映射到 [evidence-policy.md](evidence-policy.md) 的既有五级措辞等级。
本文件不新增等级。**

**衔接（逐字）：** 与 [evidence-policy.md](evidence-policy.md) 的衔接：
`Hypothesized` / `Unknown` → 措辞等级**「待核实」**；`Planned` → **不得当作证据引用**；
只有 `Observed` / `Supported` 可支撑确定性表述。

| `epistemic_status` | evidence-policy 措辞等级 | 允许的表述 |
|---|---|---|
| `Observed` | **已核实**（实验 / 数据确认） | 「已核实」「据本次实验」 |
| `Supported` | 默认**部分核实**。满足 [evidence-policy.md](evidence-policy.md) §1 的「已核实」条件（L3 + S-Lit 核实）后才可写**已核实**。声称「未见前作」且附负检索记录时可写**据本次检索未见**。未达 L2 时只能写**待核实** | 「据 X 证实」「部分核实（写明哪一维度未核实）」「据本次检索未见（检索式见附录）」 |
| `Hypothesized` | **待核实** | 「待核实」。**不得**任何确定性声称 |
| `Planned` | **待核实** + `[待补]` | 「待核实」。**不得当作证据引用**，**不得**进 `S5`。只允许出现在 D9 的缺失证据清单与最小必要实验 / 定理里 |
| `Unknown` | **待核实** + `[待补]` | 「待核实」。**不得**当作证据引用 |
| 任一条目（含 `Observed` / `Supported`）且为定理 / 命题类、证明预算已用尽 | **待补证明 · 待核实** | 「待补证明 · 待核实」 |

**硬规则：** `epistemic_status: Supported` **不等于**「已核实」。**不得**仅凭状态就把措辞
升为「已核实」，升级**必须**走 [evidence-policy.md](evidence-policy.md) §1 / §2 的条件。

**边界（不得扩大）：**

- **「据本次检索未见」不是认知状态**，而是**负检索记录**的措辞等级。它只用于「现有工作
  不够 / 未见前作」类声称，且**必须**附检索式、命中数与不足以否定的理由。
  不附负检索记录的条目**必须**降为「待核实」。
- **「待补证明」不是新等级**，它就是 [evidence-policy.md](evidence-policy.md) §1 的第五级。
  本条只说明它对应哪种 `epistemic_status`。
- 措辞等级的判定与措辞选择**一律**以 [evidence-policy.md](evidence-policy.md) 为准。
  本文件只规定「哪种状态能升到哪一级」。

**引用本节的阶段：** R12（D0、D9）。[evidence-policy.md](evidence-policy.md) §3 做反向映射。
R3—R6 / R8 为 P1。

---

## 3. Claim Graph：`C0—C5` 与 `Ci ← Ej`

**结论：每个 claim 必须能指向证据。指不到证据就写 `[待补]`，不得留空。**

| ID | 问题 |
|---|---|
| `C0` | **Central claim**：本文最关键的科学主张是什么 |
| `C1` | 为什么这个问题重要 |
| `C2` | 现有工作具体在哪里不够 |
| `C3` | 为什么不够 / 边界在哪 |
| `C4` | 建立了什么**新知识** `K` |
| `C5` | 由此推出什么后果 |

**证据引用语法（逐字）：** `C2 ← E3, E4`；无对应证据写 `C2 ← [待补]`。

**Evidence ID：** `E1`、`E2`、…（路线内唯一，不复用）。

**硬规则：**

1. `C0` **必须**一句话。它是 §4 的 central proposition 的载体。
2. 每个 `C_i` **必须**写 `Ci ← Ej`。写不出就写 `Ci ← [待补]`。**不得**留空，
   也**不得**用一段文字描述代替该语法。
3. 引用的 `E_j` **必须**是 §2 中 `Observed` / `Supported` 的条目。引用 `Hypothesized` /
   `Planned` / `Unknown` 条目属于证据夸大，违反 §2 并直接触发 `G4`。
4. `E_j` 编号在**路线内唯一且不复用**。删除一条证据时**不得**把编号让给新证据。
5. `[待补]` 不是失败标记，是**必须交付的内容**：所有 `[待补]` 行**必须**汇总进 D9 的
   缺失证据清单，并给出最小必要实验 / 定理。
6. 槽位接口：`S5` 至少覆盖 `C0`—`C4`，`S6` 必须写出不成立的条件
   （见 [narrative-patterns.md](narrative-patterns.md) §3）。claim graph 与槽位的对照
   **必须**一一落地，**不得**只在 claim graph 里写 `Ci ← Ej` 而槽位里没有对应证据句。

**引用本节的阶段：** R12（D1、D4 的 `S5`、D9）。
[scoring-policy.md](scoring-policy.md) §3 的 `G1` / `G4`。R3—R6 / R8 为 P1。

---

## 4. Central Proposition：全局承重墙

**结论：写不出可证伪的 central proposition，就没有投稿叙事。**

**承重墙规则（逐字）：**

> **任何叙事如果写不出一个明确、可证伪、且能对应到证据的 central proposition，
> 不得进入投稿叙事。**

### 4.1 七类论文的命题形态（逐字）

| 论文类型 | central proposition 的形态 |
|---|---|
| 方法 | 某结构性限制导致现有方法在 `Y` 下失败，解除它可恢复能力 |
| 理论 | 在 assumptions `A` 下性质 `P` 成立 / 不成立 |
| 现象 | 控制变量后，现象 `P` 稳定存在 |
| Benchmark | 原评测 protocol 无法识别能力 `C` |
| 负结果 | 在条件 `Y` 下不存在同时满足 `P`、`Q` 的方法 |
| 跨域 | 两领域共享结构 `S`，且满足迁移条件 `C` |
| 临床 / Use-inspired | 实际 use case 的约束 `C` 会改变最优算法设计 |

**说明：** 这张表定的是 `C0` 的**形态**，不是新的枚举。`(O, T, R)` 是另一层分类（见 §5），
两者**不得**互相替代。

### 4.2 旧「机制」规则的降级（关键）

**结论：机制性原因不再是全局承重墙，降级为方法类 / 跨域类的子规则。**

**取代关系（关键，逐字）：** 旧规则「第二段必须给机制性原因，写不出来叙事不成立」
**降级**为方法类 / 跨域类的**子规则**；全局承重墙改为 central proposition。理由：研究实际是
`Observation → Hypothesis → Experiment → Mechanism`，在 proposal 阶段强迫写「根本原因」会把
**待验证假设包装成已知原因**。

新规则：

| 论文类型 | 机制性原因的效力 |
|---|---|
| 方法类 | **必须**给出机制性原因（旧规则作为**子规则**保留） |
| 跨域类 | **必须**给出迁移合法性论证（见 [narrative-patterns.md](narrative-patterns.md) §4） |
| 其余类型 | 机制性原因**不是**承重墙条件。可以写，但**不得**因写不出机制就判叙事不成立 |

**降级后的判定（逐字保留）：** 判定承重墙的是**命题可否被证伪**，不是机制是否已知。

**机制未知时的写法（不得含糊）：**

1. 该机制**必须**写成 `C_i ← [待补]`。
2. 对应的台账条目**必须**标 `epistemic_status: Hypothesized` 与 `[待验证]`。
3. 该条**必须**进 D9 的缺失证据清单。**不得**把假设写成已知原因。

**引用本节的阶段：** R12（D1 的 `C0`、D4 的 `S3`）。
[../SKILL.md](../SKILL.md) §1.5。[narrative-patterns.md](narrative-patterns.md) §2 / §4 / §7。

---

## 5. 三轴科学分类 `(O, T, R)`

**结论：用三个轴描述一套 claim，每轴取一个单值，枚举值一律用英文原样。**

**`O` — Contribution Object：**

`Problem` | `Phenomenon` | `Theory` | `Method` | `Evaluation` | `Resource-System`

**`T` — Scientific Tension：**

`hidden-assumption` | `contradiction` | `shift-failure` | `infeasibility` |
`identifiability` | `evaluation-mismatch` | `unexplained-phenomenon`

**`R` — Resolution：**

`characterize` | `explain` | `prove` | `reformulate` | `design-algorithm` |
`build-benchmark` | `build-system`

**写法（逐字）：** `(O=Method, T=hidden-assumption, R=design-algorithm)`。

**硬规则：**

1. **枚举值一律用上面的英文原样**（机器可读契约，不得意译，见 writing-policy §8 第 6 条）。
   因此**不得**换成中文名，也**不得**改大小写或连字符。完整规则见
   [writing-policy.md](writing-policy.md) §8 第 6 条。
2. **不得**新增、合并、拆分任何枚举值。需要新值**必须**先提请 Lead 改 spec，
   **不得**在本轮自行扩大枚举。
3. 每个 claim graph **必须**登记一组 `(O, T, R)`（三个轴各取一个单值），它是 D2 的产物。
4. `O` 的枚举值与 §4.1 的论文类型**不是一一对应**。`跨域` 与 `临床 / Use-inspired` 是
   §4.1 的**论文形态**，**不是** `O` 的枚举值。
5. 三轴的用途：D2 登记贡献类型、D6 做 venue calibration（`G5`）、
   [narrative-patterns.md](narrative-patterns.md) §2 选 preset。

**单值约束（2026-10-06 追加）：** `O` / `T` / `R` **各为单值**。若多个轴同时成立，
取**主导**的那一个写进枚举字段，其余在叙事正文里说明；**不得**写 `Method+Evaluation`
这类拼接值（与 `core_goal` 的单值纪律一致，见 SKILL.md §0.1 规则 1）。

该条与 [../SKILL.md](../SKILL.md) §0.1 规则 1 的 `core_goal` 单值纪律一致。

**引用本节的阶段：** R12（D2、D6）。[narrative-patterns.md](narrative-patterns.md) §2。
[venue-standards.md](venue-standards.md) §10。

---

## 6. Anchor Eligibility Test：目标 anchor 是 prior，不是 decision

**结论：证据先决定哪些 anchor 可用。作者的目标 anchor 只能作为偏好，不能作为决定。**

**结论枚举（逐字）：**

| 值 | 含义 |
|---|---|
| `eligible` | 证据台账直接支持该 anchor |
| `conditional` | 需补指定证据后才支持（必须写明补什么） |
| `not-eligible` | 现有证据不支持；**不得**据此 anchor 组织叙事 |

**anchor 枚举沿用 SKILL.md §0.1：** 理论 / 性能 / 现象 / 基准 / 可行性 / 负结果。
（锚点表与三层锚点体系见 [../SKILL.md](../SKILL.md) §0.1。）

写到 frontmatter 的 `core_goal` **必须**用英文枚举原样：`theory` / `performance` /
`phenomenon` / `benchmark` / `feasibility` / `negative`（见 [writing-policy.md](writing-policy.md)
§8 第 6 条）。

**硬规则（逐字）：**

> **作者的目标 anchor 是 prior（先验偏好），不是决定（decision）。**
> 流程为 `Evidence → Claim → Claim strength → Eligible anchors → Narrative`。

1. 顺序**不得**颠倒。先有证据台账（§2）与 claim graph（§3），再算 anchor eligibility，
   最后才选叙事 preset。
2. 当作者的目标 anchor 与 `eligible` 集合冲突时，**必须显式告知**
   「你想定位成 X，但现有证据支持的是 Y；最强可辩护 anchor 是 Y」，
   **不得**帮作者强化不被证据支持的故事。
3. `conditional` **必须**写明补什么证据、以及补上后该 anchor 才成立。
   补什么写不清 = 降为 `not-eligible`。
4. `not-eligible` 的 anchor **不得**用于组织叙事，也**不得**出现在贡献清单的定位句里。
5. 「显式告知」**必须**落盘（当轮输出 + 路线 `STATUS.md` 的 Critical uncertainties）。
   只写进对话不算，**不得**提示冲突后继续（[../SKILL.md](../SKILL.md) §0.1 规则 6）。
6. 冲突的处置权限：agent 只能**提请**或**降级**。要真正更换主锚点，只能走
   [../SKILL.md](../SKILL.md) §0.2 锚点变更单，且**只有用户能授权**。
7. `anchor_role: orthogonal` 的路线**不得**进入 R12（[../SKILL.md](../SKILL.md) §0.1 规则 3）。

**引用本节的阶段：** R12（D3）。[../SKILL.md](../SKILL.md) §0.1 的 D 行。

---

## 7. 引用位置清单（哪些文件哪一节引用本文件）

**结论：本节是本文件的引用契约。改本文件的任何节号，必须同轮改本节与全部引用点。**

### 7.1 [../SKILL.md](../SKILL.md)

| 节 | 引用的内容 | 被引节 |
|---|---|---|
| §0.1「锚点如何约束各 R 阶段」D 行 | Anchor Eligibility Test、与目标锚点冲突时必须显式告知 | §6 |
| §1.5 | 承重墙、`C0—C5`、`Ci ← Ej`、机制规则降级 | §3、§4 |
| §2 资源索引 | 本文件全部规则 | §1—§6 |
| §3 派遣矩阵 R12 行、§4 R12 速查、§6 执行自检清单 | claim-first 流程与自检项 | §1—§6 |
| §7 设计依据 | 「为什么 claim-first」 | §1、§4 |
| §8 A5 跨层漂移 | claim 层枚举与叙事层 / 评审层的耦合 | §2—§6 |

### 7.2 [phase-r12-narrative.md](phase-r12-narrative.md)

| 节 | 引用的内容 | 被引节 |
|---|---|---|
| D0 Evidence Ledger | 台账、`E_i`、`epistemic_status`、`[待补]` | §2 |
| D1 Claim Graph | `C0—C5`、`Ci ← Ej` 语法、`C0` 一句话 | §3 |
| D2 Scientific Typing | `(O, T, R)` 逐字枚举与写法 | §5 |
| D3 Anchor Eligibility | 三值结论、`prior` 不是 `decision`、冲突告知 | §6 |
| D4a Claim-Hierarchy Realization | central proposition（`S3`）与可证伪性；D4b–D4d 冻结后仅表达 | §4 |
| D7 Hard Gates | `G1` / `G4` 的判定依据 | §2、§3 |
| D9 Output | 缺失证据清单、最小必要实验 / 定理 | §3 |

### 7.3 [narrative-patterns.md](narrative-patterns.md)

| 节 | 引用的内容 | 被引节 |
|---|---|---|
| §2 preset 选择 | `(O, T, R)` + eligible anchor | §5、§6 |
| §3 六槽位 `S1—S6` | `S3` 的 central proposition、`S5` 的 `Ci ← Ej` | §3、§4 |
| §4 Transfer Legitimacy Argument | 跨域类子规则与 `L1` / `L2` / `L3` | §4（**定义在 [narrative-patterns.md](narrative-patterns.md) §4；本节只登记跨域子规则**） |
| §5 禁用表述 | 无信息量表述的替代表述须带证据 | §2（`narrative-patterns` §5 末句已指向本节 §2） |
| §6 叙事包装 | 包装判定标准指向 `Ci ← Ej` | §3 |
| §7 自检清单 | central proposition 可证伪、`Ci ← Ej` 无缺口 | §3、§4 |

### 7.4 其它引用方

| 文件 | 节 | 引用的内容 | 被引节 |
|---|---|---|---|
| [scoring-policy.md](scoring-policy.md) | §3 硬门禁 `G1`—`G5` | `G1` 引 `Ci ← Ej`，`G2` 引 delta，`G4` 引证据台账 | §2、§3 |
| [scoring-policy.md](scoring-policy.md) | §4 排序维度六维 | `Claim strength` 与 `Narrative compression` | §1 |
| [evidence-policy.md](evidence-policy.md) | §3 认知状态 ↔ 措辞等级映射 | `epistemic_status` 五值 | §2 |
| [roles.md](roles.md) | §1B 攻击面审稿人（R12 主审） | `R-Novelty` / `R-Causal` 攻击 `Ci ← Ej` 的缺口 | §3、§4 |
| [venue-standards.md](venue-standards.md) | §10 contribution type → evidence contract → calibration | `(O, T, R)` 与证据契约 | §5 |
| [../templates/research-state.template.json](../templates/research-state.template.json) | R12 段 | `claims[]` / `evidence[]` 与 `narrative_view`；typing / eligibility 保存在叙事文档 | §2、§3、§5、§6 |
| [../examples/example-d-narrative.md](../examples/example-d-narrative.md) | 全篇示例 | 台账、claim graph、`(O, T, R)`、anchor eligibility、`[待补]` | §2—§6 |

**维护规则：**

1. 节号 `§1—§7` **冻结**。新增或移动节属于破坏性变更，**必须**同轮更新本节与全部引用点，
   并在仓库级 spec §10 记一行。
2. 引用本文件时**必须**写 `claim-first-policy.md §N`，**不得**只写「见 claim-first 政策」。
3. 本文件的枚举或门禁一旦改动，**必须**按 [../SKILL.md](../SKILL.md) §8 A5 扫完 claim 层、
   叙事层、评审层三层再收工。
4. P1 登记（本轮不做）：R3—R6 / R8 接入证据台账与 anchor eligibility，R7 / R10 / R13 迁移到
   `G1`—`G5` 门禁与六维排序。
