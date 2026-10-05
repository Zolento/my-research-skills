# 示例：A005 — 叙事（claim-first 流程）

> 本例演示 Mode D 的完整产物。顺序固定：D0 证据台账 → D1 claim graph → D2 `(O, T, R)` →
> D3 anchor eligibility → D4 候选 claim hierarchy 与六槽位 → D5 攻击面审核 →
> D6 venue calibration → D7 硬门禁 → D8 六维排序 → D9 输出。
> **证据在 claim 之前，claim 在叙事之前。** 文档骨架见
> [project-layout.md](../references/project-layout.md) §2.4。
> 规则出处见 [claim-first-policy.md](../references/claim-first-policy.md)、
> [mode-d-narrative-generation.md](../references/mode-d-narrative-generation.md)、
> [narrative-patterns.md](../references/narrative-patterns.md)、
> [scoring-policy.md](../references/scoring-policy.md)。

---

## 0. 示例输入（D0 前置检查）

```
mode=D
idea 清单：
  I1: 用扩散过程的可逆性约束组合优化搜索空间
      预期贡献：把可逆性从采样技巧升级为硬可行性约束
      与现有工作差异：现有离散扩散只把可逆性当采样器，未用作约束
      关键假设：扩散过程的逆映射在置换空间上可定义且可微
方案（来自 Mode C）：proposal A003 + experiment-plan A004（含实验 E1—E6）
作者目标 anchor（A003 frontmatter 的 `core_goal`）：theory
目标会议：ICML
```

**检查结论：** 五项齐备，可跑 D0—D9。
若缺「关键假设」，`C0` 写不出来，必须先列待补充信息清单。**不得编造信息。**

**记法：** 下文的 `A` / `B` 是**领域占位符**。A = 组合优化，B = 扩散理论。
`Y` = 条件，`G` = 可验证的缺口，`K` = 本文建立的新知识。

---

## 摘要

| idea | (O, T, R) | 可辩护 anchor | 候选 preset | 最佳 preset | 门禁 G1—G5 | 六维（S/O/SM/ED/G/NC） |
|---|---|---|---|---|---|---|
| I1 | (Method, hidden-assumption, design-algorithm) | 性能（`eligible`） | N2 / N9 / N3 | **N2** | N2 全 `pass`。N9 全 `pass`。N3 `G1 fail` | 5/4/3/4/3/4 |

> **作者目标 anchor 是 `理论`，它与 `eligible` 集合冲突。** 已按
> [claim-first-policy.md](../references/claim-first-policy.md) §6 显式告知：
> 「你想定位成理论，但现有证据支持的是性能与现象。最强可辩护 anchor 是性能。」
>
> 本表按 idea 的**主导轴**登记一组 `(O, T, R)`。
> 候选层的 triple 可以不同（例如 N9 候选把贡献对象移到 `Phenomenon`）。
> 逐候选的 triple 与 anchor 见各候选小节的「preset 适配理由」。
>
> **`Soundness margin` 的记法：** 本表记**实验侧读数** 3。
> 理论侧读数是 2，单列在 §六维排序里，**两个读数不平均**。

---

## idea I1

### I1 / 证据台账与 claim graph

| E | 内容 | 来源 | `epistemic_status` | 可否进 `S5` |
|---|---|---|---|---|
| E1 | 在条件 Y（置换约束 + 硬可行性）下，三个离散扩散基线的可行解比例为 0/200。失败表现为支撑集不交，不是概率低 | A004/E1 | `Observed` | 可 |
| E2 | 置换群的复合结构与扩散逆过程的半群结构存在复合律对应 | 文献 [作者, 会议/年份] | `Supported` | 可 |
| E3 | pilot：把可逆性并入硬约束后，可行解比例 187/200（单数据集，5 种子） | A004/E2 | `Observed` | 可 |
| E4 | 消融：只保留后处理投影时 3/200。保留可逆性结构时 187/200 | A004/E5 | `Observed` | 可 |
| E5 | 同算力、同调参预算的公平比较已跑（5 种子，报告区间） | A004/E6 | `Observed` | 可 |
| E6 | 可行解比例是下游调度决策的依据 | 文献 [作者, 会议/年份] | `Supported` | 可 |
| E7 | 文献对「可逆性是否必要」结论相反。一方以采样质量衡量，另一方以可行解比例衡量 | 文献 [作者A, 会议/年份] [作者B, 会议/年份] | `Supported` | 可 |
| E8 | 用两种口径重算本组基线：采样质量口径下差异不显著，可行解比例口径下差异显著 | A004/E3 | `Observed` | 可 |
| E9 | L2 级不变量：约束投影算子保置换可行性（证明未完成） | 方案 §C3 | `Planned` | 不可，标 `[待补]` |
| E10 | 失效的根本原因是「可逆性仅作采样技巧」这一共享假设 | 方案 §C1 | `Hypothesized` | 不可，标 `[待验证]` |
| E11 | 跨数据集与跨规模的泛化验证（A004/E7 未跑） | A004/E7 | `Planned` | 不可，标 `[待补]` |
| E12 | 连续松弛求解器上是否同样失效（未做检索，也未做实验） | 无 | `Unknown` | 不可，标 `[待补]` |

**claim graph（`Ci ← Ej` 语法逐字）：**

```
C0 ← E1, E3, E4   在条件 Y 下现有离散扩散方法结构性失效，把可逆性改为硬约束可恢复置换可行性。
C1 ← E6           该能力影响下游调度决策。
C2 ← E1           现有方法共享假设 X（可逆性只用于采样），在 Y 下结构性失效。（机制归因是 `Hypothesized`，标 `[待验证]`，见缺失证据清单）
C3 ← E1, E2, E4   内部修补无法突破：后处理投影只回到 3/200，失效在结构层。
C4 ← E2           新知识 K：两领域共享复合结构 S，约束可并入逆过程。
C5 ← [待补]       跨数据集与更大规模的后果（E11 未跑）。
```

**两条硬约束（本例的实际处置）：**

- `E10` 是 `Hypothesized`，所以**没有任何 `C_i` 把 `E10` 当证据引用**。
  `C2` 的假设归因半支只写 `[待验证]`，并列进 D9 的缺失证据清单。
- `E9` / `E11` / `E12` 是 `Planned` / `Unknown`，同样不得进 `S5`。

#### D2 科学分类

主导轴登记为 `(O=Method, T=hidden-assumption, R=design-algorithm)`。
三轴**各取单值**，枚举值用英文原样，**不得**写成 `Method+Evaluation` 这类拼接值。
贡献类型 = `General`（沿用 [venue-standards.md](../references/venue-standards.md) §5）。

#### D3 Anchor Eligibility（逐 anchor）

| anchor | 结论 | 为什么 | 需补什么证据 |
|---|---|---|---|
| 理论 | `conditional` | E2 只给结构对应。迁移合法性未举证 | 补 E9：L2 级不变量或充分条件 |
| 性能 | `eligible` | E1 给失效。E3 / E4 给恢复与结构必要性。E5 给公平比较 | — |
| 现象 | `eligible` | E7 给结论矛盾。E8 给两种口径的重算结果 | — |
| 基准 | `not-eligible` | 本轮不交付评测 protocol。E8 只是口径重算 | 不得据此 anchor 组织叙事 |
| 可行性 | `conditional` | E3 是单数据集 pilot。真实规模未验证 | 补 E11：多数据集与 ≥10^4 节点验证 |
| 负结果 | `not-eligible` | 台账里没有不可能性结论 | 不得据此 anchor 组织叙事 |

> **作者目标 anchor 是 `理论`，与 `eligible` 集合冲突。** 必须显式告知：
> 「你想定位成理论，但现有证据支持的是性能与现象。最强可辩护 anchor 是性能。」
> 该条已落盘到本轮输出与 `routeA/INDEX.md` §7 Warnings。
> **不得**帮作者强化不被证据支持的故事。
> `not-eligible` 的 anchor **不得**用于 D4 的 preset 选择与叙事组织。
> 要真正更换主锚点，只能走 [SKILL.md](../SKILL.md) §0.2 的锚点变更单，
> 且**只有用户能授权**。

#### D4 候选层的层级差异

| 候选 | `C0` 的写法 | 新知识 `K` | 层级差异 |
|---|---|---|---|
| N2 | 在 Y 下结构性失效。解除该结构限制可恢复可行性 | 共享结构 S，假设 X 可移除 | 以「移除假设 → 恢复能力」为主轴 |
| N9 | 「可逆性是否必要」的矛盾来自口径差异 | 口径决定结论 | 以「定位矛盾来源」为主轴 |
| N3 | 两领域共享结构 S，且满足迁移条件 C | 迁移合法性（L2 待补） | 以「迁移合法性」为主轴 |

> **这三套是真正不同的 claim hierarchy**（`C0` 不同、`K` 不同），
> **不是**同一主张的三种措辞。候选数 = 3，落在 2—4 套内。

#### 跨域 anti-application stress test（强制）

跨域类必须测试 `N2 / N3 / N5 / N9`，目的是证明「把 B 用到 A」不是最准确的描述。

| preset | 能否写出 `G` 与 `K` | 判定 |
|---|---|---|
| N2 | 能。`G` = 结构层失效（E1, E4）。`K` = 共享结构 S（E2） | **最准确**，保留 |
| N9 | 能。`G` = 结论矛盾（E7）。`K` = 口径决定结论（E8） | 保留为候选 |
| N3 | 能写，但迁移条件 C 的举证未完成（E9） | 保留，携 `G1` 风险 |
| N5 | 不能。现有证据只有一类方法，写不出「多类方法各自是特例」 | **排除**：只能退化成「把 B 用到 A」 |

---

### I1 / N2 瓶颈突破/移除假设

#### （1）claim hierarchy

- `C0`：在条件 Y 下现有离散扩散方法结构性失效，把可逆性改为硬约束可恢复置换可行性。
- `C1`—`C5` 与它的关系：`C1` 说明能力重要性（E6）。`C2` 钉住失效范围（E1）。
  `C3` 给出结构层原因（E1, E2, E4）。`C4` 是 `K`（E2）。`C2` 的归因半支待验证。`C5` 待补。
- 本套与其余候选的层级差异：主轴是**移除假设**，`K` 落在结构层。

#### （2）六槽位

**`S1 Context`**：置换约束下的组合优化决定调度与资源分配。
可行解比例是这条链路的上游能力。

**`S2 Tension`**：条件 `Y` = 置换约束 + 硬可行性。
缺口 `G` = 现有离散扩散方法在 `Y` 下失效（E1）。三套基线全部落在可行集之外。

**`S3 Central Proposition`**：`Y` 下的失效源于结构层。
把可逆性从采样技巧改为硬约束，即可恢复置换可行性。
**可证伪写法：** 若在同类结构约束下可行解比例仍是 0/200，该命题被推翻。

**`S4 Resolution`**：按 E2 的复合律把约束并入逆过程，得到约束投影算子。
用消融把「结构位置」与「投影次数」分开（E4）。
机制半支（E10）仍是假设，**不得**写成已知原因。

**`S5 Evidence Contract`**：

```
C0 ← E1, E3, E4    C1 ← E6    C2 ← E1    C3 ← E1, E2, E4    C4 ← E2    C5 ← [待补]
```

**`S6 Consequence & Boundary`**：

- 改变了什么：把「可逆性」从采样技巧重定位为硬可行性约束。下游调度可直接取用可行解。
- 在哪些条件下不成立：置换结构不成立时（连续松弛、无硬可行性要求）。
  约束投影不可微时，`S4` 的算法也不成立。`C5` 的跨规模后果未验证（E11）。

#### （3）preset 适配理由

`(O, T, R)` = `(Method, hidden-assumption, design-algorithm)`。
使用的 anchor = 性能，资格 `eligible`（E1 + E3 + E4 + E5 直接支持）。
N2 服务「移除假设 → 恢复能力」这套 hierarchy。

#### （4）贡献清单

- [方法] 约束投影算子：把置换约束并入扩散逆过程（方法来源：**部分原创**）
- [实证] 条件 `Y` 下的失效刻画与消融（方法来源：**原创**）
- [理论] 共享复合结构 `S` 的对应（方法来源：**迁移**）

> 第三条**如实标 `迁移`**。把它包装成「原创」属于夸大。

#### （5）为什么之前没人做

此前把可逆性当采样技巧，未检验它在硬约束下的作用。
置换可行性的判别口径也未统一（E7 的两套口径即为例证）。

#### （6）该套的弱点

- `E10` 的根本原因未验证，机制可能是事后解释。
- `E9` 的 L2 不变量未证，理论侧读数偏低。

> `S-Devil` 的完整清单与逐条处置见 §攻击面评审。该 preset 的弱点不得静默丢弃。

#### （7）包装前后对照

| | 表述 | 依据 |
|---|---|---|
| 包装前 | 我们提出了一个可逆性约束模块 | — |
| 包装后 | 现有方法共享假设 X，在 `Y` 下结构性失效。我们移除该假设 | `C2 ← E1`、`C3 ← E4`、`C0 ← E3` |
| 判定 | 只改参照系，未改事实 | 每句都能落回 `Ci ← Ej` |

---

### I1 / N9 矛盾解决

#### （1）claim hierarchy

- `C0`：文献对「可逆性是否必要」结论相反，原因是评测口径不同。
- 层级差异：本套不主张「恢复能力」，只主张**定位矛盾来源**。证据面更窄，也更闭合。
- 候选层 typing 重定位：`(O=Phenomenon, T=contradiction, R=explain)`。

#### （2）六槽位

| Slot | 内容 |
|---|---|
| `S1 Context` | 可逆性的必要性决定离散扩散能否用于硬约束场景。这条判断影响方法选型 |
| `S2 Tension` | 缺口 `G` = 结论矛盾：一方以采样质量衡量，另一方以可行解比例衡量（E7） |
| `S3 Central Proposition` | 矛盾来自口径差异。换用可行解比例口径后，必要性差异显著（E8）。可证伪：统一口径重算后若差异消失，命题被推翻 |
| `S4 Resolution` | 用两种口径重算同一组基线（E8），给出统一口径与判定规则 |
| `S5 Evidence Contract` | `C0 ← E7, E8`　`C1 ← E6`　`C2 ← E7`　`C3 ← E8`　`C4 ← E8`　`C5 ← [待补]` |
| `S6 Consequence & Boundary` | 改变了：「可逆性是否必要」有了可判定的口径。不成立：任务不要求硬可行性时，或采样质量本身是唯一交付目标时 |

#### （3）preset 适配理由

`(O, T, R)` = `(Phenomenon, contradiction, explain)`。
使用的 anchor = 现象，资格 `eligible`（E7 + E8）。
N9 服务「定位矛盾来源」这套 hierarchy，与 N2 的层级不同。

#### （4）贡献清单

- [实证] 两口径重算与统一判定规则（方法来源：**原创**）
- [问题定义] 把矛盾定位到口径层，而不是方法层（方法来源：**原创**）

#### （5）为什么之前没人做

两个口径分属不同子社区，缺少共同重算。E7 的两篇工作各测各的口径。

#### （6）该套的弱点

影响面窄。若读者只承认采样质量口径，本套的价值下降。

> `S-Devil` 的弱点清单见 §攻击面评审（2 条），逐条处置后才可推荐。

#### （7）包装前后对照

| | 表述 | 依据 |
|---|---|---|
| 包装前 | 我们报告了一个更细的评测指标 | — |
| 包装后 | 矛盾结论的来源是口径差异。统一口径后即可判定可逆性的必要性 | `C0 ← E7, E8` |
| 判定 | 只改参照系，未改事实 | 未把口径重算写成新基准 |

---

### I1 / N3 跨域理论迁移（迁移合法性 = L2，待补）

#### （1）claim hierarchy

- `C0`：两领域共享复合结构 `S`，且满足迁移条件 `C` 时约束可并入逆过程。
- 层级差异：主轴是**迁移合法性**。理论 anchor 的举证尚未完成。

#### （2）六槽位

| Slot | 内容 |
|---|---|
| `S1 Context` | A 领域对结构性质 `S` 的依赖决定了可用方法范围 |
| `S2 Tension` | A 内部方法共享假设 X，在 `Y` 下结构性失效（`G`） |
| `S3 Central Proposition` | 两领域共享结构 `S`，且满足迁移条件 `C`（可证伪：找不到满足 `C` 的不变量即推翻） |
| `S4 Resolution` | Transfer Legitimacy Argument 按 `L2` 举证：不变量或充分条件（E9 待补） |
| `S5 Evidence Contract` | `C0 ← E2, [待补]`　`C1 ← E6`　`C2 ← E1`　`C3 ← E1`　`C4 ← E2`　`C5 ← [待补]` |
| `S6 Consequence & Boundary` | 改变了：迁移合法性成为可检验条件。不成立：迁移条件 `C` 不成立时 |

#### （3）preset 适配理由

`(O, T, R)` = `(Method, hidden-assumption, prove)`。
使用的 anchor = 理论，资格 `conditional`（需补 E9）。
`C0` 的迁移条件半支**没有证据**，这是 `G1` 的直接命中点。

#### （4）贡献清单

- [理论] 迁移合法性论证（方法来源：**迁移**）

#### （5）为什么之前没人做

两领域此前缺乏交流。扩散理论的复合律未被映射到置换结构上。

#### （6）该套的弱点

`C0` 的迁移条件半支缺证据。`E9` 未完成前，本套不可提交。

> `S-Devil` 的弱点清单见 §攻击面评审（3 条）。其中一条直接命中 `G1`。

#### （7）包装前后对照

| | 表述 | 依据 |
|---|---|---|
| 包装前 | 我们把扩散方法用到了组合优化 | — |
| 包装后 | 两领域共享结构 `S`，迁移需满足条件 `C` | `C0 ← E2, [待补]` |
| 判定 | 参照系改了，但**关键半支无证据** → 不得作为最佳叙事 | `G1 fail` |

---

## 攻击面评审（跨 idea）

**派遣：** 六个攻击面审稿人全部派遣。`S-Lit` 恒派。`S-Devil` 必派但不打分。
`S-Nov` / `S-Repro` / `S-Feas` 按需。

| preset | R-Novelty | R-Causal | R-Experimental | R-Theory | R-Generalization | R-Utility | S-Devil 弱点条数 | S-Lit 结论 |
|---|---|---|---|---|---|---|---|---|
| N2 | 4 | 4 | 3 | 2 | 3 | 5 | 3 | 部分重叠 |
| N9 | 3 | 4 | 5 | 5 | 2 | 3 | 2 | 部分重叠 |
| N3 | 3 | 2 | 3 | 1 | 2 | 3 | 3 | 部分重叠 |

> **打分边界：** 每个攻击面审稿人只在自己的主责维度上给一个 `1—5`。
> `5` = 该攻击面不构成阻塞，`1` = 该攻击面致命。
> `S-Lit` / `S-Devil` 不打分，只出事实与类别结论。
> **这些判定不进任何向量，也不做中位数。** 它们只喂 `D7` 门禁与 `D8` 逐维理由。
> 六个审稿人不是独立样本（`corr ≫ 0`），**不得以「六个都同意」声称 reviewer consensus**。

**六个攻击面的意见摘要（N2）：**

- `R-Novelty` 4：最接近工作 [作者, 会议/年份] 也改采样器，但未把结构并入约束。delta 在结构层。
- `R-Causal` 4：`C3` 的结构原因有 E4 消融支撑。替代解释「投影次数」已被固定次数的对照排除。
- `R-Experimental` 3：E5 已对齐算力与调参预算。缺功效分析与跨数据集对照（E11）。
- `R-Theory` 2：`S3` 的命题没有不变量支撑。E9 完成前，理论侧缺可依赖的支撑。
- `R-Generalization` 3：`S6` 写出了边界。但「结构层」结论目前只在单数据集上成立。
- `R-Utility` 5：改变下游调度的选型口径。受影响决策具体（见 `C1 ← E6`）。

**`S-Lit`（恒派，不打分）：** 给出 5 篇最接近工作，结论「部分重叠」。
已完成 L3 穷尽检索并附负检索记录。重叠在机制层，结论层不重叠。

**`S-Devil` 的致命弱点清单（N2，逐条处置）：**

| # | 弱点 | 威胁 | 处置 |
|---|---|---|---|
| 1 | `E10` 的根本原因未验证，机制可能是事后解释 | `C2` 的假设归因 | **接受**，转缺失证据 |
| 2 | pilot 只在单数据集上跑。跨规模失败会让「结构层」结论失效 | `C3` / `C5` | **接受**，转最小必要实验（E11） |
| 3 | 「可逆性结构」与「任意硬投影」未完全分离 | `G3` | **反驳**：E4 固定投影次数，只改结构位置（3/200 对 187/200） |

**最简解释反例（`S-Devil`）：** pilot 的提升可能来自投影次数增加，而不是可逆性结构。
处置：由弱点 3 的反驳证据排除。该反例同时喂 `R-Causal` 与 `G3`。

**交叉质询（每套至少一轮）：**

| preset | 质疑方 → 被质疑方 | 分歧点 | 结论 |
|---|---|---|---|
| N2 | R-Theory → R-Causal | R-Causal 给 `Explanatory depth` 4，但机制半支待验证 | **未收敛 → 存在评审分歧** |
| N2 | R-Experimental → R-Utility | `Significance` 5 建立在单数据集 pilot 上 | 收敛：`Significance` 记 5，`Soundness margin` 记 3 |
| N9 | R-Generalization → R-Novelty | 口径结论是否够「新」 | 收敛：delta 在口径层，非机制层 |

> 分歧单列，**不得**被任何聚合掩盖。**不做中位数、不做平均、不做一票否决。**

---

## 门禁判定 G1—G5（跨 idea）

| preset | G1 | G2 | G3 | G4 | G5 | 结论 |
|---|---|---|---|---|---|---|
| N2 | pass | pass | pass | pass | pass | 可排序 |
| N9 | pass | pass | pass | pass | pass | 可排序 |
| N3 | **fail** | pass | pass | pass | pass | **`not_submission_ready`** |

**依据位置（逐门禁）：**

- N2 / `G1 Claim grounding`：`C0 ← E1, E3, E4`，三条都是 `Observed`。
- N2 / `G2 Prior-work distinction`：`S-Lit` 给出 5 篇最接近工作，delta 在结构层。
- N2 / `G3 Identification`：E4 在固定投影次数下隔离了结构位置。
- N2 / `G4 Factual integrity`：叙事句与 E1/E3/E4 的原始范围一致。E10 未被写成已知原因。
- N2 / `G5 Venue scope`：贡献对象 `Method` 与 ICML 的接收范围一致。
- N9 / `G1`：`C0 ← E7, E8`。N9 / `G3`：E8 用两种口径直接重算。
- N9 / `G2`：`S-Lit` 的「部分重叠」限于机制层，口径层未被覆盖。
- N3 / `G1 Claim grounding`：`C0 ← E2, [待补]`。**迁移条件半支没有证据**（E9 未完成）。

**判定规则：** 判定值只有 `pass` / `fail`。任一 `fail` ⇒ `not_submission_ready`。
门禁**不打分、不聚合、不平均**，也**不得**用高分抵消 `fail`。

---

## 六维排序与最佳叙事推荐（跨 idea）

**门禁失败的候选不进排序。** 所以下表只有 N2 与 N9。

| preset | Significance | Originality | Soundness margin（实验侧 / 理论侧） | Explanatory depth | Generality | Narrative compression | 胜负维 | 代价维 |
|---|---|---|---|---|---|---|---|---|
| **N2** | 5 | 4 | 3 / 2 | 4 | 3 | 4 | Significance、Originality、Generality | Soundness margin、Narrative compression |
| N9 | 3 | 3 | 5 / 不适用 | 4 | 2 | 5 | Soundness margin、Narrative compression | Significance、Originality、Generality |

**逐维理由（必须引用依据）：**

- N2 `Significance` 5：`C1 ← E6` 指出可行解比例决定下游调度决策。`R-Utility` 判 5。
- N2 `Originality` 4：`S-Lit` 判「部分重叠」（机制层重叠、结论层不重叠）。`R-Novelty` 判 4。
- N2 `Soundness margin` 3：`R-Experimental` 判 3。公平比较已跑（E5），缺功效与跨数据集（E11）。
  理论侧 `R-Theory` 判 2：L2 不变量未证（E9）。
- N2 `Explanatory depth` 4：`R-Causal` 判 4。E4 隔离了结构。`E10` 仍待验证。
- N2 `Generality` 3：`R-Generalization` 判 3。单数据集，`S6` 已写出边界。
- N2 `Narrative compression` 4：汇总者判 4。六槽位闭合，`C5 ← [待补]` 需一句交代。
- N9 `Soundness margin` 5（实验侧）：`R-Experimental` 判 5。E8 直接重算两种口径。
  理论侧记「不适用」：本套不主张理论命题。**两个读数不平均。**
- N9 `Generality` 2：`R-Generalization` 判 2。结论只覆盖 `Y` 下的评测设置。

**排序方式 = 逐维比较 + 显式写出胜负维与代价维，不给综合总分。**

**最佳叙事：N2（瓶颈突破/移除假设）**

**runner-up：N9（矛盾解决）。** 它也通过了全部门禁。

**胜出理由（逐维）：** N2 在 `Significance`（5 对 3）、`Originality`（4 对 3）、
`Generality`（3 对 2）三维胜出。它付出的代价是 `Soundness margin`（3/2 对 5）
与 `Narrative compression`（4 对 5）。`Explanatory depth` 两套持平（4 对 4）。
N2 的 claim 更强，且已过门禁。按 claim-first 总纲，它是最强可辩护的一套。

**致命风险：** `E9` 与 `E11` 未补时，`Soundness margin` 抬不起来。
若更大规模上替代解释成立，`G3` 会回退为 `fail`。
缓解策略：投稿前补 E9 与 E11。若两者都补不上，**改用 runner-up N9**。

**最适合会议：** ICML。判定顺序是 contribution type → evidence contract → venue calibration。
会议只影响范围判定，**不影响** D4 已定的 claim hierarchy。**不按 venue 选 preset。**

---

## 缺失证据清单与最小必要实验 / 定理（跨 idea）

| claim | 缺什么证据 | 威胁哪条 claim / 哪道门禁 | 当前措辞等级 |
|---|---|---|---|
| `C5` | 跨数据集与跨规模验证（E11） | `C5`（不威胁门禁） | 待核实 |
| `C2` 的假设归因（E10） | 根本原因的识别实验 | `C2` / `G3`（现为 pass，可能回退） | 待核实 |
| N3 的 `C0` | L2 级不变量或充分条件（E9） | N3 的 `C0` / `G1 fail` | 待补证明 · 待核实 |
| E12 | 连续松弛求解器上是否同样失效 | `S6` 的边界句 | 待核实 |

| target_claim | action | data | baselines | success_criterion |
|---|---|---|---|---|
| N3 的 `C0` | 证 L2 不变量：投影算子保置换可行性 | 不适用（理论） | — | 给出不变量陈述与证明，或给出反例并降为 L1 |
| `C2` 的假设归因 | 做识别实验：固定投影次数，只改结构位置 | A004 数据集 + 1 个新数据集 | 三套基线 + 后处理投影 | 结构组与后处理组的区间不重叠 |
| `C5` | 跨数据集与 ≥10^4 节点规模的泛化验证 | 3 个数据集 | 同上 | 可行解比例下界高于基线区间上界 |
| E12 | 在连续松弛求解器上重跑 E1 | 1 个连续松弛基线 | — | 明确给出「同样失效 / 不失效」 |

**最终建议（回答三问）：**

1. **哪个 idea 的 claim hierarchy 最成熟？** I1 的 N2 层级。它全门禁 `pass`，六维最高。
2. **哪个 idea 有无法修复的根本缺陷？** 本例只有一个 idea，无不可修复缺陷。
   N3 的 `G1 fail` 可以修复（补 E9）。N5 方向已被 stress test 排除。
3. **哪个 idea 换一种 claim hierarchy 可能更高价值？** 若 E8 的口径重算扩到 3 个以上数据集，
   N9 可升级为「原评测 protocol 无法识别能力」的层级，此时 anchor 转为基准。

**退回规则：** 若某 idea 的全部候选都 `not_submission_ready`，或六维普遍 ≤ 2，
就退回 Mode B 重做 idea。

---

## 落盘与 INDEX 更新

- 文档：`routeA/docs/A005-narrative.md`（一次调用一份，内含全部 idea 的小节）。
- `routeA/INDEX.md` §2 文档索引：新增 A005 行。
- §3 已证实：E1 与 E4 支撑的「在 `Y` 下结构性失效」与「结构必要性」。
- §4 已证伪：N3 的迁移合法性方向（`G1 fail`）。N5 方向被 stress test 排除。
- §5 TODO：补 E9、E11、E12，并检验 E10 的假设归因。按最佳叙事重写提案（回 Mode C）。
- §7 Warnings：作者目标 anchor `理论` 与 `eligible` 集合冲突（需锚点变更单 + 用户授权）。
  `S-Lit` 判「部分重叠」（delta 需在相关工作显式划界）。`N2` 的 `Soundness margin` 偏低。
- `next_mode_suggestion: "C | E"`：按最佳叙事重写提案，或直接送审。
