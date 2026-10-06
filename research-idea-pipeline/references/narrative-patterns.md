# 顶会论文叙事 preset 库（R12 锚定用）

> **名称说明：** 本文件在部分旧引用里被称为「叙事套路库」。现统一称 **narrative preset
> 库**：`N1—N10` 是 **preset**，不是套路等级，更不是创新等级。

> **记法警告（两条，先读）：**
> 1. **`N1—N10` = narrative presets / rhetorical realizations**，即「同一份科学内容可以
>    怎么讲」。它们**不是科学分类**、**互不排斥**、**不是创新等级**。
>    一个 idea 可以同时满足多个 preset；preset 编号高低不代表工作强弱。
>    真正的科学分类是 `(O, T, R)` 三轴（见 [claim-first-policy.md](claim-first-policy.md) §5）。
> 2. 下文与 [phase-r12-narrative.md](phase-r12-narrative.md) 中的 **「A 领域 / B 领域」是领域
>    占位符**（A = 要解决问题的目标领域，B = 提供理论工具的来源领域），**与 Mode 字母
>    A/B/C/D/E 无关**。

**本文件服务的总纲（claim-first）：**

> 现有**理解 / 能力 / 评测**在条件 `Y` 下存在一个**可验证的缺口** `G`；
> 本文建立**新的知识** `K`，用于解释、界定或消除 `G`。
> **`B → K`（从来源领域引入）只是产生 `K` 的一种方式。**

**推论（硬规则）：** `N4`（现象）、`N8`（评测）、`N10`（负结果）**不需要、也不得**硬塞一个
`B`。凡要求「必须有 B」的写法一律作废，改为「必须能写出 `G` 与 `K`」。
旧总纲「A 有结构性缺口、B 恰好补上」**降级为跨域场景专用**（见 §4）。

---


> **⚠️ 更正（HIGH-1）：`N1`—`N10` 只是叙事 preset，不是 QD archive 的 niche。**
> 早期版本让两者共用一套名字以避免第二套枚举，代价是把 Narrative ontology 泄漏进
> Discovery，而且映射本身**有损**（例如 preset「效率 / 可行性」在 QD 七轴里没有对应项）。
>
> **QD niche 现在是七个独立的科学结构轴**：`assumption-shift` / `formulation-shift` /
> `representation-shift` / `mechanism-shift` / `theory-shift` / `evaluation-shift` /
> `boundary-shift`（见 [phase-r3-r6-discovery.md](phase-r3-r6-discovery.md) §R4.2.1）。
>
> **`state_check.py` V6 只收那七轴** —— 把 preset 名写进 `hypotheses[].niche` 会被判违规。
> V15 只对 **live niche**（至少存在一个 `status ∈ {active, elite}` 的候选）要求 elite；
> 候选全部 `killed` / `archived` 的 niche **合法为空**。那是 **QD niche** 的规则，与 preset 无关。

## 1. 十套叙事 preset 表

### 1.1 N1—N10 的读法

- **它们是修辞实现，不是分类法。** 同一份 claim graph 可以用多套 preset 讲；
  同一套 preset 也能承载不同的 claim hierarchy。
- **不互斥。** 一套叙事常同时命中 2—3 个 preset（例如 N2 + N6，或 N4 + N9）。
  主叙事只选**一个**作为主线，其余作为辅助表述。
- **不是创新等级。** 选 N1 不代表比 N10 更创新；preset 不参与任何评分。
- **主叙事取决于 claim hierarchy 的强弱**，不取决于 preset 的「热度」。
  哪套 hierarchy 的 central proposition 更强、证据更闭合，哪套就是主叙事
  （判定见 [phase-r12-narrative.md](phase-r12-narrative.md) §D8）。
- 「适合会议」列是**候选提示**，不是判据。会议归口在
  [phase-r12-narrative.md](phase-r12-narrative.md) §D6 的 venue calibration 里按
  contribution type 校准；**禁止按会议直接选 preset**。

### 1.2 十套表

| # | 叙事 preset | 核心句式（`G → K` 写法） | 是否涉及来源领域 B | 适合会议 | 主要风险 |
|---|---|---|---|---|---|
| N1 | **新问题/新设定** | 现有理解在条件 `Y` 下缺少对问题 `P` 的定义；本文把它形式化，建立 `K` | 不涉及 | NeurIPS、CVPR、MICCAI（新任务 / 新临床设定） | 问题不够重要 |
| N2 | **瓶颈突破/移除假设** | 在 `Y` 下现有方法共享假设 `X` 而失效（`G`）；本文建立 `K`：解除 `X` 可恢复能力 | 可选 | ICML、NeurIPS、MICCAI（移除临床 / 成像假设） | 假设移除不彻底 |
| N3 | **跨域理论迁移** | A 缺少工具，`K` 由 B 迁移而来，并给出迁移合法性论证 | 典型 | ICML、MICCAI（成像物理 / 信号处理理论迁移） | 被视为简单应用 |
| N4 | **现象发现与解释** | 观察到反直觉现象 `P`，现有解释覆盖不了（`G`）；本文建立解释性 `K` | **不得硬塞** | NeurIPS、ICML、MICCAI（临床现象 / 失败模式） | 解释不唯一 |
| N5 | **统一框架** | 现有方法各自是特例，缺少统一刻画（`G`）；本文建立统一 `K` 并据此导出新算法 | 可选 | ICML、NeurIPS、MICCAI（统一重建 / 分割 / 配准框架） | 只有框架没有新算法 |
| N6 | **效率/可行性** | 现有做法在 `Y` 下不可行（`G`）；本文建立使其实用且保留保证的 `K` | 可选 | CVPR、ICML、MICCAI（低场 / 床旁 / 实时可行） | 被归为纯工程 |
| N7 | **鲁棒性/泛化** | 现有方法在分布偏移 / 非平稳下崩溃（`G`）；本文界定失效条件并建立 `K` | 可选 | NeurIPS、ICML、MICCAI（跨中心 / 跨设备泛化） | 设定不够新 |
| N8 | **Benchmark/评测** | 原评测 protocol 无法识别能力 `C`（`G`）；本文建立评测侧 `K` 并给出基线 | **不得硬塞** | CVPR、NeurIPS、MICCAI（多中心评测 / 挑战赛） | 贡献被归为数据集 |
| N9 | **矛盾解决** | 先前结果互相矛盾（`G`）；本文定位原因并给出统一解释 `K` | 可选 | ICML、NeurIPS、MICCAI（研究间结论冲突） | 原因不够关键 |
| N10 | **不可能性/负结果** | 在 `Y` 下不存在同时满足 `P`、`Q` 的方法（`G` 即负向知识）；本文给出可达松弛 `K` | **不得硬塞** | NeurIPS、MICCAI（外部验证失败 / 临床不可行） | 适用范围太窄 |

> **MICCAI 的出现不是装饰。** 凡贡献对象属于 `Method` / `Evaluation` / `Phenomenon` /
> `Resource-System`，且工作带医学影像、临床验证或数据合规属性时，MICCAI 都应进入候选会议。
> MICCAI 接受**方法学创新或应用创新**（见 [venue-standards.md](venue-standards.md)）；
> 但 `clinical significance ≠ methodological innovation`，两者**不得互相冒充**。

---

## 2. preset 选择：`(O, T, R)` + eligible anchor

**选择依据不再是「贡献类型 → 套路」的单轴映射。** 旧表已废弃，贡献类型改由 `(O, T, R)`
三轴表达（逐字枚举见 [claim-first-policy.md](claim-first-policy.md) §5）。
选 preset 的顺序固定为四步：

1. **先过锚点资格。** 做 Anchor Eligibility Test
   （[claim-first-policy.md](claim-first-policy.md) §6）：只有 `eligible` / `conditional`
   的锚点才可用于组织叙事；`not-eligible` 的锚点**不得**用来选 preset。
2. **按 `(O, T, R)` 求候选交集**（§2.1—§2.3）。
3. **用 eligible anchor 参考表排序**（§2.4，降级为参考，不是判据）。
4. **跨域类另做 anti-application stress test**（见 §4 与
   [phase-r12-narrative.md](phase-r12-narrative.md) §D4）。

### 2.1 按 `O`（Contribution Object）取候选

| `O` | preset 候选 |
|---|---|
| `Problem` | N1、N9、N8 |
| `Phenomenon` | N4、N9、N1 |
| `Theory` | N10、N5、N3、N2 |
| `Method` | N2、N5、N6、N7 |
| `Evaluation` | N8、N1、N9 |
| `Resource-System` | N6、N1、N8 |

### 2.2 按 `T`（Scientific Tension）取候选

| `T` | preset 候选 |
|---|---|
| `hidden-assumption` | N2、N5 |
| `contradiction` | N9、N4 |
| `shift-failure` | N7、N6 |
| `infeasibility` | N10、N6 |
| `identifiability` | N4、N9、N10 |
| `evaluation-mismatch` | N8、N1 |
| `unexplained-phenomenon` | N4、N1 |

### 2.3 按 `R`（Resolution）取候选

| `R` | preset 候选 |
|---|---|
| `characterize` | N4、N1 |
| `explain` | N4、N9 |
| `prove` | N10、N3、N5 |
| `reformulate` | N1、N5 |
| `design-algorithm` | N2、N5、N6、N7 |
| `build-benchmark` | N8 |
| `build-system` | N6、N1 |

**取法：** 三张表的候选取**并集**后按命中次数排序。命中两次以上的优先。
三轴都给不出候选时，说明 claim 还没成形 —— 回到 `D1 Claim Graph` 重写 `C0`，
**不得**随便抓一个 preset 硬套。

### 2.4 锚点 → preset 参考表（降级为参考）

**只有 `eligible` / `conditional` 的锚点才允许出现在本节的使用中。**
本表**不再**是选 preset 的第一依据 —— 第一依据是 §2.1—§2.3 的 `(O, T, R)`。

| 主锚点 | 常配 preset | 默认不优先 |
|---|---|---|
| **理论** | N3、N5、N10、N2 | N6（易被归为纯工程）、N8 |
| **性能** | N2、N5、N6、N7 | N10（负结果与性能目标不符） |
| **现象** | N4、N8、N9、N1 | N6 |
| **基准** | N8、N1、N9 | N10 |
| **可行性** | N1、N6、N8 | N10 |
| **负结果** | N10、N9、N4 | N6、N7 |

> **「默认不优先」不是禁止。** 要选，必须说明它为什么仍然服务主锚点。
> **锚点与 preset 明显不匹配时（例如性能锚点去讲 N10 不可能性），必须在输出中显式
> 指出该冲突**，不得默默继续。
>
> **anchor 是 prior，不是 decision。** 作者想定位成 X、而证据支持的是 Y 时，
> 必须显式告知「最强可辩护的锚点是 Y」，**不得**帮作者强化不被证据支持的故事
> （[claim-first-policy.md](claim-first-policy.md) §6）。

---

## 3. 六槽位 S1—S6（取代旧的固定段落模板）

### 3.1 槽位定义

| Slot | 问题 |
|---|---|
| `S1 Context` | 哪个能力 / 科学问题重要？ |
| `S2 Tension` | 当前知识 / 方法 / 评测具体哪里不够？ |
| `S3 Central Proposition` | 本文最关键、可证伪的新命题是什么？ |
| `S4 Resolution` | 如何证明、解释或利用该命题？ |
| `S5 Evidence Contract` | 哪些证据分别支撑哪些 claim？（`Ci ← Ej` 对照） |
| `S6 Consequence & Boundary` | 这改变了什么？在哪些条件下不成立？ |

**规则（三条，全部强制）：**

1. **六个槽位全部必填。** 缺任一槽位，该套叙事不得标为「可用于投稿」，
   必须在输出里标出缺口位置。
2. **`S5` 至少覆盖 `C0`—`C4`。** 每条 claim 要么挂上证据（`Ci ← Ej`），
   要么显式写 `Ci ← [待补]`；**不得留空、不得默认成立**。
3. **`S6` 必须写出不成立的条件。** 只写「适用范围广」而不写边界，视为未完成。

**承重墙（先于槽位填写）：**

> 任何叙事如果写不出一个明确、可证伪、且能对应到证据的 central proposition，
> 不得进入投稿叙事。

七类论文各自的命题形态见 [claim-first-policy.md](claim-first-policy.md) §4。
**机制性原因不再是全局承重墙** —— 它降级为**方法类 / 跨域类**的子规则
（即 `S4` 在这些类型下必须给出机制或迁移合法性，其他类型不强制）。

### 3.2 四类论文的填法示例

以下四例只示范「同样的槽位，不同论文类型填什么」，**不是硬编码模板**。
`[待补]` 表示该处必须由真实证据替换。

#### （a）理论类：`(O=Theory, T=hidden-assumption, R=prove)`

| Slot | 填法 |
|---|---|
| S1 | 某个被普遍依赖的性质 `P` 是否在更弱的假设下成立，决定了整类方法可用范围 |
| S2 | 现有结论都在假设 `A` 下证明；`A` 在 `Y` 下不成立，且无人给出替代条件 |
| S3 | **在 assumptions `A'` 下性质 `P` 成立 / 不成立**（可证伪：给出反例即推翻） |
| S4 | 证明主线 + 假设必要性分析 + 紧性分析 |
| S5 | `C0 ← E1`（定理）、`C3 ← E2`（反例）、`C4 ← E3`（紧性） |
| S6 | 改变了该性质的可依赖边界；在 `A'` 不满足时不成立 |

#### （b）Benchmark / 评测类：`(O=Evaluation, T=evaluation-mismatch, R=build-benchmark)`

| Slot | 填法 |
|---|---|
| S1 | 该能力 `C` 是下游决策的依据，但当前评测无法识别它 |
| S2 | 原 protocol 的指标 / 划分 / 口径使能力 `C` 的差异被掩盖（`G`） |
| S3 | **原评测 protocol 无法识别能力 `C`**（可证伪：给出被判为等价、实际不同的实例） |
| S4 | 构造评测集 + 划分协议 + 基线重测；证明原 protocol 的判别力缺口 |
| S5 | `C0 ← E1`（判别力实验）、`C2 ← E2`（原 protocol 的盲区实例）、`C4 ← [待补]` |
| S6 | 改变评测结论的可信度；在 `C` 不重要的任务上不成立 |
| 注意 | **不得**硬塞来源领域 `B`（N8 的 `K` 就是评测知识本身） |

#### （c）跨域类：`(O=Method, T=hidden-assumption, R=design-algorithm)`，`B → K`

| Slot | 填法 |
|---|---|
| S1 | A 领域任务的重要性 + 它对某结构性质 `S` 的依赖 |
| S2 | A 内部方法共享假设 `X`，在 `Y` 下结构性失效（`G`）；内部修补无法突破 |
| S3 | **两领域共享结构 `S`，且满足迁移条件 `C`**；由此得到的 `K` 解除 `X` |
| S4 | Transfer Legitimacy Argument（§4）+ 据此设计的新算法（不是照搬 B） |
| S5 | `C0 ← E1, E2`（结构对应 + 迁移合法性）、`C2 ← E3`（失效证据）、`C4 ← E4`（消融证明结构必要）、`C5 ← [待补]` |
| S6 | 改变 A 领域在 `Y` 下的可用能力；在迁移条件 `C` 不成立时不成立 |

**跨域类额外要求：** 必须做一次 **anti-application stress test**
—— 至少测试 `N2 / N3 / N5 / N9` 四个 preset，目的是**证明「把 B 用到 A」不是最准确的
描述**，而不是四套都必须成稿（见 [phase-r12-narrative.md](phase-r12-narrative.md) §D4）。

#### （d）负结果类：`(O=Theory, T=infeasibility, R=prove)`

> **各轴只取一个单值。** 若你的负结果更偏方法侧，改写 `(O=Method, R=characterize)`。
> **不得**在同一条里把两个轴值用「或」连起来 —— 枚举字段不接拼接值。

| Slot | 填法 |
|---|---|
| S1 | 该目标被普遍认为可达成，方向上有持续投入 |
| S2 | 现有尝试各自绕过障碍，但无人证明障碍是否可绕（`G`：缺负向知识） |
| S3 | **在条件 `Y` 下不存在同时满足 `P`、`Q` 的方法**（可证伪：给出一个满足者即推翻） |
| S4 | 不可能性证明 / 归约；给出可达松弛与代价界 |
| S5 | `C0 ← E1`（不可能性）、`C3 ← E2`（松弛的代价界）、`C4 ← E3`（边界实例） |
| S6 | 改变了资源投入方向；在 `P` 或 `Q` 被放宽时不成立 |
| 注意 | **不得**硬塞来源领域 `B`；负结果的 `K` 就是负向知识本身 |

---

## 4. 跨域 Transfer Legitimacy Argument

跨域叙事**不得**停留在「A 有问题，B 能解决」。必须完成以下五步。
**第 1、2、4、5 步与旧版一致；第 3 步改名为 Transfer Legitimacy Argument**
（旧名「迁移合法性定理」作废），并按 `L1 / L2 / L3` 三级给出举证。

| 步 | 内容 | 对应攻击面 |
|---|---|---|
| 1 | **结构性缺口 `G`**：A 领域现有方法**共享假设 X**，在条件 Y 下**结构性失效**。失败原因必须具体到机制或可检验的结构性质，不能是「效果不好」。 | `R-Novelty`（delta 是否非平凡）、`R-Utility`（谁会在意） |
| 2 | **结构对应 `S`**：A 中的结构性质与 B 中的定理 / 机制具有**同构或可映射关系**，不是表面相似。必须指明对应的是什么结构。 | `R-Theory`（定义是否成立）、`R-Generalization`（映射是否越界） |
| 3 | **Transfer Legitimacy Argument**：回答「为什么 B 在 A 中合法」。按下表选 `L1 / L2 / L3` 中的**一档**举证，**证据强度必须与论文声称的贡献等级匹配**。 | `R-Theory`（假设与紧性）、`R-Causal`（是否只是相关性） |
| 4 | **新知识 `K` 与新方法**：基于第 3 步建立 `K`，并据此**设计**新算法，而不是直接套用 B。 | `R-Novelty`、`R-Utility` |
| 5 | **实证与必要性**：实验证明新算法优于 A 领域**最强基线**，且**消融证明 B 带来的结构是必要的**。 | `R-Experimental`（公平性 / 统计功效）、`R-Generalization`（scope 是否超出证据） |

**`L1 / L2 / L3` 举证等级（逐字，不得改写）：**

> ⚠️ **消歧：** 本节的 `L1` / `L2` / `L3` 是**迁移举证等级**，与
> [literature-policy.md](literature-policy.md) 的**检索尽职调查等级** L1 / L2 / L3
> **无关** —— 两者同形不同义，引用时必须带限定词（「迁移等级 L2」/「L2 检索」）。

| Level | 举证方式 | 适用 |
|---|---|---|
| `L1` | structural hypothesis + falsification experiments | CVPR / MICCAI 实证型 |
| `L2` | formal invariance / sufficient conditions / proposition | method-heavy ICML / NeurIPS |
| `L3` | theorem + proof + necessity / tightness analysis | theory-anchor ICML / NeurIPS / JMLR |

**硬约束（取代旧规则）：**

> **必须明确回答「为什么 B 在 A 中合法」，且证据强度必须与论文声称的贡献等级匹配。**
> **不再要求任何论文都必须有 theorem。** `L1` 的证伪实验、`L2` 的不变量或充分条件，
> 都可以独立构成合法的迁移论证。

**未完成五步的后果：** 缺任一步，该套叙事**不得**标为「可用于投稿」；
应在输出中标注缺口位置，并把它记入 `D9` 的缺失证据清单。

**跨域类还必须做 anti-application stress test**（见 [phase-r12-narrative.md](phase-r12-narrative.md) §D4）：
至少测试 `N2 / N3 / N5 / N9` 四个 preset，目的是证明「把 B 用到 A」不是最准确的描述。

---

## 5. 禁用表述（无信息量）

叙事与贡献清单中**禁止**出现：

- ❌ 「显著提升」「有效解决」「性能优异」（除非紧跟具体数字与口径）
- ❌ 「泛化性不足」「缺乏理论分析」「效果不够好」（必须指向具体结构性质或理论条件）
- ❌ 「我们首次提出」（未标注「待核实」前）

**替换要求：** 每一处评价必须给出**具体机制、具体条件、具体数字**三者之一。

措辞等级以 [evidence-policy.md](evidence-policy.md) 为唯一权威
（认知状态 ↔ 措辞等级映射见该文件 §3）。**本文件不另立措辞表。**
**替代表述必须落回证据台账条目**（[claim-first-policy.md](claim-first-policy.md) §2）：
找不到对应 `E_j` 的表述一律删除，不得用更有力的形容词补位。

---

## 6. 叙事包装：重新定位，不是夸大

**叙事包装 = 在不改变任何事实的前提下，改变读者理解该工作的参照系。**

| 允许（重新定位） | 禁止（夸大） |
|---|---|
| 把「提出新模块」定位为「移除假设 X」 | 编造未做的实验 / 未证明的定理 / 未测的数字 |
| 把「数据集上更好」定位为「现有方法在条件 Y 下结构性失效」 | 把「3 个数据集有效」写成「普遍有效」 |
| 把「组合 A 与 B」定位为「建立结构对应 + Transfer Legitimacy Argument」 | 把「部分重叠」写成「首次提出」 |
| 改变贡献类型的归类（method → theory / problem definition） | 用「显著提升」替代具体数字与口径 |
| 把「改进 X」定位为「统一 X/Y/Z」 | 承诺方案里没做的事 |
| 把「迁移」如实标成`迁移` | 把「迁移」包装成「原创」 |

**唯一判定标准（指向 claim graph）：**

> **包装后的每一句声称，都必须能在 claim graph 里找到对应的 `Ci ← Ej`。**
> 找不到对应证据的，就是夸大 —— 删除，或标注 `[待补]`。
> 判定细节见 [claim-first-policy.md](claim-first-policy.md) §3。

**包装必须写在文档里：** 每套叙事附一小节「包装前后对照」，写明改了哪个参照系、
依据哪条证据（`Ci ← Ej`）。

---

## 7. 叙事自检清单

每套叙事产出后逐条核对：

- [ ] `N1—N10` 只当 **preset / 修辞实现**用，没有当成科学分类、创新等级或互斥选项。
- [ ] 能写出**条件 `Y`、缺口 `G`、新知识 `K`** 三者；`N4` / `N8` / `N10` 没有被硬塞 `B`。
- [ ] central proposition **明确、可证伪、能对应到证据**（形态符合其论文类型）。
- [ ] 六个槽位 `S1—S6` 全部填写，且 `S6` 写出了**不成立的条件**。
- [ ] `S5` 的 `Ci ← Ej` 对照**无缺口**：每条 claim 要么挂证据，要么标 `[待补]`。
- [ ] 使用的锚点均为 `eligible` / `conditional`；与作者目标锚点冲突时已**显式告知**。
- [ ] 跨域类已完成**五步升级**，第 3 步给出了 `L1 / L2 / L3` 中的一档举证；
      没有默认要求 theorem。
- [ ] 跨域类已完成 **anti-application stress test**（`N2 / N3 / N5 / N9`）。
- [ ] 贡献清单 3—4 项，每项**标注贡献类型**与**方法来源**（`原创` / `部分原创` / `迁移`）。
- [ ] 回答了「为什么之前没人做」（至少一个具体理由）。
- [ ] 诚实写出该套叙事的**弱点**（1—2 条）。
- [ ] 无 §5 的禁用表述；所有引用为 `[作者, 会议/年份]`。
- [ ] 「首次提出」已标「待核实」；要保留则三件事齐备：L3 穷尽检索 + S-Lit 核实 +
      负检索记录（见 [phase-r12-narrative.md](phase-r12-narrative.md) §D5.3）。
- [ ] 已附「包装前后对照」，且每句声称都能落回 `Ci ← Ej`。
- [ ] 落盘路径带 `routes/<R>/` 前缀（`routes/<R>/docs/<R>NNN-narrative.md`）。