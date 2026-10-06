# R7 / R10 / R13 — 对抗保证 · 元认知修复 · artifact 审计

**R7 / R10 / R13 审「已成型方案」的正确性与可行性，并守住新颖性底线。**
可接 R8，也可接上一次 R7 / R10 / R13 继续复核。

**R10 的权威定义在 [phase-r9-r11-experiment-loop.md](phase-r9-r11-experiment-loop.md)。**
本文件只登记「R7 / R13 发现的问题必须交给 R10」，**不另立一套处置规则**。

**首轮 R7 审什么：** R8 的证据契约在 R7 **之后**才建立，因此**首轮** R7 审的是
R3—R6 的候选与其**计划中的**证据契约（写在 `hypotheses[]` / `assurance[]` 里）；
从第二轮起才审 R8 正式建立的 `claims[].contract`。

---

## R7.0 定位与边界（先读）

> **R7 / R10 / R13 的对象是"已成型的方案"，核心问题是"这么做对不对、能不能做成"。
> 同时必须强调创新性——目的是避免在不知情的情况下**复现别人的方案**。**

| 维度 | R3—R6（idea 级，见 [phase-r3-r6-discovery.md](phase-r3-r6-discovery.md)） | **R7 / R10 / R13（方案级）** |
|---|---|---|
| **对象** | 一句话级 idea / 技术方向 | 成型的 proposal + 实验计划 |
| **核心问题** | 这个概念值得做吗？ | **这个方案做得对吗、能不能做成？** |
| **可行性** | 概念可行性：路线是否成立 | **工程可行性：具体做法能否跑通、变量是否可控、实验是否可证伪** |
| **正确性** | 前提是否自洽 | **方法正确性：推导、实现、指标选取、统计方案是否成立** |
| **创新性** | 方向是否已被覆盖、是否非平凡 | **方案是否实质复现已有工作（增量性质是否成立）** |
| **复现性** | 不涉及 | **必查（S-Repro）** |
| **深度** | 快筛：双评分 + 致命反驳 | **深审：六个攻击面 + 交叉质询 + 逐维中位数** |

**一句话记法：R3—R6 管「值得做吗」，R7 / R10 / R13 管「做对了吗」。**

**两条不可退让的原则：**

1. **正确性优先：** R7 的主战场是**方法本身的正确性**——推导是否成立、实现是否
   忠实于声称、指标是否测量了声称的东西、统计是否支持结论、实验是否真的能证伪假设。
2. **创新性必须显式表态：** 即使方案在技术上是正确的，若它实质上是已发表工作的
   **复现或微小实现变体**，R7 必须明确指出，并给出**复现风险等级**（见 §R7.3.2）。
   一个"做得很扎实的复现"在 CVPR/ICML/NeurIPS 是**拒稿**理由，不是优点。

**锚定点（核心目标）必须先确认**（见 [../SKILL.md](../SKILL.md) §0.1）。
本阶段受锚点约束——**评审侧重按锚点调整，但派遣名单不变**：

| 主锚点 | 首要核查项 |
|---|---|
| **理论** | 证明是否成立、假设是否必要、反例 / 紧性是否讨论（`R-Theory`、`S-Theory`） |
| **性能** | 公平比较（同算力·同数据·同调参）、指标口径、显著性检验（`R-Experimental`） |
| **现象 / 基准** | 解释是否唯一、基准是否暴露真实失败模式（`R-Generalization`） |
| **可行性 / 负结果** | 前提是否现实、结论是否被过度外推（`S-Feas`、`S-Theory`） |

> **会议审稿人（`R-CVPR` / `R-ICML` / `R-NeurIPS` / `R-MICCAI`）不参与科学发现。**
> 它们只在 **R12 / R13 的 venue calibration 表**里出现（见 §R7.10）。

**锚点与方案不一致时必须当场指出**（例如性能锚点却没做同算力比较），并计入结论卡片的
致命风险或修改建议。

> **派遣方式：** 环境有 Team 能力时**必须先询问用户**是否使用 Team；用户显式要求但
> 环境不具备时须**显式回退**并告知（见 [../SKILL.md](../SKILL.md) §3.1）。

---

## R7.1 输入

| 输入 | 必填 | 说明 |
|---|---|---|
| 待复核方案 | ✅ | 来自 R8 的 `proposal`，或用户提供 |
| 上一次审阅内容 | ❌ | **有 → 接续复核；无 → 首次复核** |
| 关键参考文献 | ❌ | 缺省时调用 R2 / R5 定向补充 |

---

## R7.2 判断复核类型

### R7.2.1 R7 的三个触发点（何时该调用 R7）

| # | 触发点 | 说明 |
|---|---|---|
| ① | **R8 产出后首次复核** | 方案与实验计划刚成型，做首次完整的六攻击面审查 |
| ② | **实验完成、有实测结果后** | 此时"预期"变"实测"，**防复现检查必须重做**（新颖性/复现判定的证据基础已变） |
| ③ | **投稿被拒 / 改投时** | 按新会议的审稿标准重审，并复核是否**出现了新的最接近工作**（判据是**有无新文献**，**不是**上次检索距今多久） |

> ⚠️ **R7 不是链条终点，而是反馈环。** R7 的结论可以**回流到 R8**（按审阅意见重写
> 方案 / 补实验）或**回流到 R3—R6**（叙事或方案的根本缺陷指向 idea 本身不成立）。
> 触发点 ② 之后**不得**直接沿用触发点 ① 的防复现结论。

### R7.2.2 复核类型

| 类型 | 触发条件 | 处理方式 |
|---|---|---|
| **首次复核** | 无上一次审阅内容 | 执行完整六攻击面审查（§R7.3 全量） |
| **接续复核** | 有上一次审阅内容 | 聚焦**上次未解决问题** + **新引入变更** |

判断依据是输入中是否存在上一次的 `review_output`（含六攻击面意见与评分）。
**开头必须声明本次属于哪一类。**

---

## R7.3 派遣：六个攻击面 + S-Lit + S-Devil

### R7.3.1 派遣名单

| 角色 | 派遣 | 审查焦点 |
|---|:--:|---|
| `S-Lit` | ● | **文献核实、新颖性是否真实、复现风险判定**（恒派，见 §R7.3.2） |
| `R-Novelty` | ● | 最近工作是否已做过、delta 是否非平凡 |
| `R-Causal` | ● | 是否只是相关性 / 事后解释、有无更简替代解释 |
| `R-Experimental` | ● | 基线公平性、confounder、统计功效、消融覆盖 |
| `R-Theory` | ● | 假设是否必要、证明是否有缺口、结论是否 tight |
| `R-Generalization` | ● | claim scope 是否超出证据、边界条件是否被写掉 |
| `R-Utility` | ● | 即使全部正确，谁会在意、改变了什么 |
| `S-Devil` | ● | 致命弱点清单 + 最简解释反例（**不打分**） |
| `S-Repro` | ○ | 可复现性与伦理风险 |
| `S-Nov` | ○ | `S-Lit` 判「边缘重叠」或方案涉及「首次提出」时追加，独立核验 |
| `S-Theory` | ○ | 理论严谨性 |
| `S-Feas` | ○ | 工程可行性、资源瓶颈 |
| `R-CVPR` / `R-ICML` / `R-NeurIPS` / `R-MICCAI` | — | **不派**：会议审稿人只在 R12 / R13 的 venue calibration 表里出现 |
| `A-Author` / `A-Experimenter` / `S-Integrity` | — | **不派**：`S-Integrity` 属 R13 |

**派遣名单的权威副本是 [roles.md](roles.md) §4.2 派遣矩阵的 `R7` 列。** 本表必须与它逐行一致。

**硬规则：**

- **六个攻击面审稿人全部派遣、不得裁减。** 每个角色**只攻击一个面**，不写平衡意见，不写总体评价。
- **`S-Devil` 不打分**：只出致命弱点清单与最简解释反例（1—5，**5 = 完全无新颖性，低 = 好，反向维度**）。
- **写不出可判定 `Kill Condition` 的评审不合格** —— 只有分数不构成评审（见 §R7.10）。
- **不得直接改 `claims[].status`** —— 只能经 R10（例外见 [../SKILL.md](../SKILL.md) §1.6）。
- **会议审稿人不参与科学发现。** 不得要求「理论角度 / 应用角度 / 会议特性判定」三段式评审。

### R7.3.2 防复现检查（Anti-Reproduction Check，强制）

**由 `S-Lit` 主责，`R-Novelty` 与 `S-Devil` 交叉验证。** 逐项作答：

| # | 检查项 | 判定 |
|---|---|---|
| 1 | 是否存在**可一对一对应**的已有方案（问题、机制、结论三层都对应）？ | 有 / 部分 / 无 |
| 2 | 本方案相对它的增量是**设计改变**，还是仅**实现优化/超参调整**？ | 设计改变 / 实现优化 / 无实质增量 |
| 3 | 增量是否触及**新的结构性质或理论条件**？（对应 §R3—R6.3 的"没做到"） | 是 / 否 |
| 4 | 若把已有方案原样重跑，本方案的核心声称是否仍成立？ | 是（→ 复现风险高）/ 否 |
| 5 | 是否只是把已有方法**换一个数据集/换一个 backbone**？ | 是（→ 复现风险高）/ 否 |
| 6 | 最接近工作的作者会认为这是**独立贡献**还是**自己的后续工作**？ | 独立 / 后续 / 复现 |

> ⚠️ **「换数据集 / 换 backbone」与「换问题定义 / 评估口径」必须分开判：**
> - 第 5 项的「换数据集 / 换 backbone」指**机制与结论不变、只替换数据或骨干网络**
>   → **复现风险高**；
> - 若改的是**问题定义 / 评估口径**（触及**新的问题形式化或新的评估协议**），
>   **不自动等于复现风险高** —— 必须**单独论证**该形式化 / 协议本身是否构成
>   **设计层面的贡献**（对照 [venue-standards.md](venue-standards.md) §6 的创新性判定范畴）。
>   论证不出来的，仍按原有风险等级处理。

**复现风险等级：**

| 等级 | 判据 | 后果 |
|---|---|---|
| **低** | 存在设计层面的增量，触及新的结构性质或理论条件 | 可继续 |
| **中** | 增量偏实现层，但问题设定或评估口径不同 | 必须补强贡献声称或改变定位 |
| **高** | 可一对一对应，且无实质设计增量 | **必须在结论卡片中列为致命风险** |

**S-Lit 的检索门禁：** 新颖性/复现判定属于 **T4 触发场景**，必须达到
**L3 穷尽检索**（见 [literature-policy.md](literature-policy.md) §3.1），并附
**负检索记录**。未达到时，结论只能写"据本次检索未见"，且**不得**给出"复现风险低"。
**措辞等级统一见 [evidence-policy.md](evidence-policy.md)**（本文件不另立措辞表）。

> **与方法来源的对应（见 [venue-standards.md](venue-standards.md) §5.1）：**
> `原创` → 通常复现风险低；`部分原创` → 看改造是否触及**新的结构性质或理论条件**；
> **`迁移` 且未证明迁移本身带来新性质 → 复现风险高**（本质仍是"把 X 用到 Y 上"）。
> 标注缺失或模糊（"受 X 启发"）**按最高风险处理**，并要求补齐标注。

**输出规格（强制）：**

- 每个攻击面**必须输出五元组**（`Attack` / `Target Claim` / `Alternative` /
  `Discriminating Test` / `Kill Condition`），见 §R7.10。**五元组是 primary。**
- **写不出可判定 `Kill Condition` 的评审不合格。** 只有分数不构成评审。
- 每个子代理同时输出 **1—5 分评分**（次要记录）+ **文字评审意见**。
- 字数下限：见 [roles.md](roles.md) §7 的**字数与规模下限总表**（R7 / R10 / R13 子代理意见
  ≥ 200 字，**S-Repro ≥ 150 字**）。
- 评分必须有理由，且**引用具体证据**（具体实验缺失、具体引用、具体逻辑缺口）。
- 使用 [roles.md](roles.md) §5 的统一输出骨架。

**评分锚点（1—5 分）：**

| 分 | 含义 |
|---|---|
| 5 | 无实质缺陷，可直接投稿 |
| 4 | 小修可解决 |
| 3 | 有明显缺陷，但可修复；需要大修 |
| 2 | 存在结构性缺陷，修复成本高 |
| 1 | 根本性错误 / 不可行 / 不成立 |

---

## R7.4 交叉质询与共识形成

### R7.4.1 第 0 步：极性归一化（强制，先于汇总）

**与 R12 一样，R7 / R10 / R13 的评分也必须先归一化再进中位数**（共用机制见
[scoring-policy.md](scoring-policy.md)）。R7 是**单个总分**而非维度向量，因此规则更简单：

- **S-Devil 的「新颖性反驳」是反向维度**：`1—5，5 = 完全无新颖性`，**低 = 好**；
  归一化为 **新颖性稳健度 = 6 − 反驳分**。
- **其余子代理的 1—5 分都是高 = 好**，取**原值**。
- **归一化后才能进中位数**；不得用原始的反驳分参与汇总。
- **中位数 ≤ 2 的归一化维度 → 不得判为「推荐优先级 = 高」**（一票否决；`≤ 2` 时
  允许「带条件的推荐」，须写明理由、缓解路径与验证点，见
  [scoring-policy.md](scoring-policy.md) §5 / §5.1）。
- **评分汇总表里必须同时给出原始分与归一化分，并标注方向。**

**规则：**

1. **每个子代理对其余子代理的评分提出至少一条质疑或补充。**
   （八条起：8 个子代理各至少一条；不得只写"同意"。）
2. **评分差异 ≥ 2 分的维度**，必须记录**分歧点**并尝试协商。
3. **无法达成共识的，明确标注"存在评审分歧"。**
4. **在归一化之后汇总取中位数评分**（不用平均数，避免被极端值拉偏）。
5. 分歧在记录时必须写清：谁给分多少、依据是什么、为何无法收敛。

**交叉质询记录模板：**

| 质询方 | 被质询方 | 原评分 | 质询内容 | 结果 |
|---|---|---|---|---|
| `S-Devil` | `R-Experimental` | 4 | 认为可复现性被高估：未披露随机种子 | 接受，`R-Experimental` 下调至 3 |

**评分汇总模板：**

| 子代理 | 原始分 | 方向 | 归一化分 | 中位数 | 分歧标记 |
|---|---|---|---|---|---|
| `R-Experimental` | 3 | 高 = 好 | 3 | | |
| `R-Theory` | 4 | 高 = 好 | 4 | **3.5** | ⚠️ `R-Theory` 与 `S-Devil` 差 3 分 |
| `S-Devil` | 2 | **低 = 好（反向）** | **4**（`6 − 2`） | | |
| … | … | … | … | | |

> **归一化分**才是进入中位数的值；S-Devil 的**原始分**与其归一化分方向相反，两列都必须给。

---

## R7.5 复核结论

**审查结论卡片（核心交付物）：**

```markdown
### 审查结论卡片

**总体判定（推荐优先级）：** 高 / 中 / 低 / 建议放弃
**最适合投稿的会议：** CVPR / ICML / NeurIPS / MICCAI（含理由）
**综合评分（中位数）：** <x>/5
**复现风险等级：** 低 / 中 / 高（来自 §R7.3.2 防复现检查）
**方法正确性判定：** 成立 / 有缺口 / 不成立（来自 §R7.3 的正确性维度）

**核心优势：**
- …（**引用具体子代理意见**，如「`R-Utility` 认为该洞察有复用价值」）

**致命风险：**
- …（每条标注**是否可缓解**；可缓解的写明缓解路径）
- 若复现风险 = 高，**必须在此列为致命风险**
- **若 S-Devil 的新颖性稳健度（`6 − 反驳分`）≤ 2，必须在此写入「致命风险」**，
  或在卡片中**显式说明**为何该低分不构成致命风险（带条件的推荐须附缓解路径与验证点）

**修改建议：**（针对具体缺陷，逐条可执行）
1. …
```

**创新性表态要求：** 结论卡片**必须**给出复现风险等级，且必须回答一句
"本方案相对最接近工作，是**设计层面的贡献**还是**实现层面的改进**"。
复现风险 = 高时，总体判定不得为"高"。**S-Devil 归一化后的新颖性稳健度 ≤ 2 时，
总体判定同样不得为"高"**（除非走 [scoring-policy.md](scoring-policy.md) §5.1 的
「带条件的推荐」并写明理由、缓解路径与验证点）。

**每条路线的总体判定**（若输入含多个 idea/方案）需分别给出优先级。

**横向对比表**（多方案时必需）：

| 方案 | 创新性 | 可行性 | 可复现性 | 推荐优先级 | 最适合会议 |
|---|---|---|---|---|---|
| S1 | 高 | 中 | 中 | 高 | ICML |
| S2 | 中 | 高 | 高 | 中 | CVPR |

---

## R7.6 接续复核规则

**如果输入包含上一次审阅内容**（`review_output` + `open_questions`）：

1. **对比上次评分**，标注变化维度（↑ / ↓ / =，以及变化幅度）。
   ⚠️ **对比前必须先做极性归一化**：S-Devil 的分数是**反向**的（`5 = 完全无新颖性`，
   低 = 好）。**"↑" 一律指归一化后的方向**（即"变好"），因此 S-Devil 的
   **原始分上升 = 变差**，必须写成 **↓**。见 [scoring-policy.md](scoring-policy.md) §2。
2. 上次被标记为 **"致命风险"** 的项，本次**必须专项复核**——不得跳过。
3. 上次存在 **"评审分歧"** 的，本次**必须尝试用新证据解决**；若仍无法解决，
   明确说明新增了哪些证据、为何仍不收敛。
4. 输出 **"变更追踪表"**。

**变更追踪表模板：**

| 上次问题 | 类型 | 上次状态 | 本次是否解决 | 证据 |
|---|---|---|---|---|
| 未披露随机种子 | 可复现性 | 致命风险 | ✅ 已解决 | 新增 §10 明确 5 个种子与误差棒 |
| 收敛性证明依赖强凸性 | 理论 | 评审分歧 | ❌ 未解决 | 未给出非凸情形证明；新增证据不足 |

**评分变化表模板：**

| 子代理 | 上次评分 | 本次评分 | 变化 | 原因 |
|---|---|---|---|---|
| `R-Experimental` | 2 | 4 | ↑2 | 补全了消融矩阵与复现细节 |
| S-Devil | 2 | 3 | **↓1** | 归一化后稳健度 **4 → 3**（`6−反驳分`）；**原始分上升 = 新颖性风险上升**，不是改善 |

> ⚠️ 上表 S-Devil 一行是**方向陷阱的示范**：若照抄原始分就会写成「↑1 改善」，那是错的。
> **变化列的 ↑ / ↓ 一律按归一化后的方向**；S-Devil 行须同时给出原始分与归一化后的
> 稳健度（见 [scoring-policy.md](scoring-policy.md) §2）。

---

## R7.7 文档落盘与状态更新（强制）

1. **写审阅记录：** `routes/<R>/docs/<被审ID>-review-r01.md`；
   接续复核写 `-r02.md`、`-r03.md`（轮次零填充两位）（frontmatter 记 `review_round`）。
   **审阅记录不占用新序号**，永远挂在被审文档 ID 上。
2. **frontmatter：** `phase: R7 / R10 / R13 / type: review / review_of: <被审ID> / review_round / also_reviewed / status`。**跨文档复核**（如同时审方案 + 实验计划）挂在主文档 ID 上，其余写进 `also_reviewed`。
3. **更新该路线 `INDEX.md`（资产目录）：** `Reviews` 新增本文件行。
4. **把审阅结论翻译成 `STATUS.md` 状态**（这是本 R 阶段最容易漏的一步）：

   | 审阅结论 | 写入 STATUS |
   |---|---|
   | 某机制成立 / 已被数据支持 | **Strongest supported findings** |
   | 某假设被否定 / 不可行 | **Most important negative findings**（保留，不删） |
   | 需要补实验 X / 补文献 Y | **Next recommended actions** |
   | 致命风险未缓解 | **Critical uncertainties** |
   | **复现风险 = 高** | **Critical uncertainties** + 结论卡片致命风险 |
   | 复现步骤本身有错 | **Next recommended actions**（工程项，不新增正式文档） |
   | 评分与上轮的变化 | `STATUS.md` 的 State version 变化与 `INDEX.md` 的 Recent Research Changes |

   > 写状态前先写回 `research-state.json`，再重新生成 `STATUS.md`；**不得手改**。
5. **新颖性结论的门禁：** S-Lit/S-Nov 判定"新颖"前必须完成 T4 的 **L3 穷尽检索**；
   未完成则结论只能写"据本次检索未见"，且**不得**给出"复现风险低"，并记入
   **Critical uncertainties**。

## R7.8 输出

| 交付物 | 说明 |
|---|---|
| **六攻击面评审意见** | 每条含评分 + 意见；字数下限见 [roles.md](roles.md) §7（R7 / R10 / R13 子代理 ≥200 字，S-Repro ≥150 字） |
| **五元组记录** | 每个攻击面一条 `(Attack, Target, Alternative, Test, Kill Condition)` |
| **交叉质询记录** | 每人至少一条质询 |
| **审查结论卡片** | §R7.5 模板 |
| **横向对比表** | 多方案时必需 |
| **变更追踪表** | **仅接续复核时**输出 |

## R7.9 回写 Research World Model

**R7 写 state 的对象只有 `assurance[]` / `failures[]` / `uncertainties[]` / `known_flaws`。**
审查记录本身（评审意见、评分汇总、交叉质询、变更追踪）落**文档**（见 §R7.7），**不落 state**。

```jsonc
{
  "assurance": [
    {"kill_condition": "若 O2 出现则 C17 降级",
     "discriminating_test": "X8",
     "verification_tier": "T0"}
  ],
  "failures": [
    {"id": "F1", "kind": "unsupported", "what": "…", "why": "…",
     "referenced_by": ["C17"], "source_review": "REV1"}
  ],
  "uncertainties": [
    {"id": "U3", "question": "…", "importance": "high", "uncertainty": "high",
     "cheapest_discriminating_test": "TBD", "status": "open"}
  ]
}
```

**硬规则：**

- **R7 不写 `reviews`。** `reviews` 由 **R13** 写（[research-state-policy.md](research-state-policy.md) §3.11）。
- **`assurance[].verification_tier` 的上限是 `T0`** —— LLM reviewer 的产物
  **不得**据此升级任何 claim 状态（`V20`）。
- **R7 不得改 `claims[].status`** —— 只能经 R10（例外见 [../SKILL.md](../SKILL.md) §1.6）。
- **每条疑点必须落成 `assurance[]` 条目**，不得只写进 review 文档。
- **`kill_condition` 非空且 `discriminating_test` 指向存在的 `X` 或 `TBD`**（`V9` 强制）。
- **验收记录的结构以 `reviews[].id` 为关联键**：`repairs[].source_review` 与
  `failures[].source_review` 用它建立逐条对应（`V23`）。**全局存在性不算闭环。**
- 回写后跑 `python3 scripts/state_check.py --check .research-idea-pipeline/routes/<R>/research-state.json`，
  **硬违规须为 0**。

---

## R7.10 assurance：输出**可执行对象**，不是分数

**八个攻击面**（取代「按 venue 组织」）：

| 攻击面 | 承担角色 | 专攻 |
|---|---|---|
| 最近工作碰撞 | **`S-Lit`** + `R-Novelty` | 是否已有人做过、delta 是否非平凡 |
| 更简单解释够不够 | **`R-Causal`** | 是否只是相关性 / 事后解释 |
| 实验是否识别 claim | **`R-Experimental`**（读数 ①） | baseline、confounder、统计功效 |
| 统计与不确定性 | **`R-Experimental`**（读数 ②） | p 值、置信区间、多重比较 |
| assumption / theorem / boundary | **`R-Theory`** | 假设是否必要、证明是否有缺口 |
| claim scope | **`R-Generalization`** | 声称范围是否超出证据 |
| 实现与可复现 | **`S-Repro`** | 复现风险、实现与声称是否一致 |
| **完整性** | **`S-Integrity`**（Wave 3 新增；**R13 起生效**，R7/R8 不得要求） | leakage / cherry-pick / metric misuse / post-hoc |

**每个攻击面必须输出五元组（硬规则）：**

```
(Attack, Target Claim, Alternative, Discriminating Test, Kill Condition)
```

示例：

```
Attack:         MIND-specific mechanism may be unnecessary.
Target:         C17
Alternative:    Any edge-preserving relational loss gives same gain.
Test:           MIND vs gradient relation vs random matched-scale loss.
Kill Condition: If alternatives match MIND under equal compute,
                remove the MIND-specific mechanism claim.
```

1. **`Kill Condition` 必须可判定** —— 写成「若观察 `O` 则 `X`」的形式；写不出即该 attack 无效
   （`state_check.py` V9 已强制 `kill_condition` 非空、`discriminating_test` 指向存在的 `X` 或 `TBD`）。
2. **`Discriminating Test` 必须指向存在的 `X`** —— 没有就写 `TBD` 并落一条 `U`。
3. **assurance 不得直接改 `claims[].status`** —— 只能经 **R10**（例外见 [../SKILL.md](../SKILL.md) §1.6：R8 证据驱动的单向升级）。
4. **分数只是次要记录。** 可执行对象是 primary；`scoring-policy` 的 `G1—G5` 仍生效，但
   1—5 分**不再**是 assurance 的主要输出。
5. **人读摘要仍然必填**（仓库既有硬规则）：五元组为 primary，摘要是 secondary，**二者并存**。

**venue 校准（不进 R7）**：`R-CVPR` / `R-ICML` / `R-NeurIPS` / `R-MICCAI`
**不参与科学发现**，只在 **R12/R13 的 venue calibration 表**里出现（不派子代理）。
`contribution type → evidence contract → venue calibration` 是唯一入口
（见 [venue-standards.md](venue-standards.md) §10）；**禁止**「venue 直接选 preset」。

## R13. artifact-aware 审计

**审计对象不是论文**，而是：`paper` / `claim graph` / `experiment graph` / `code` /
`logs` / **`failed runs`** / `dataset selection history` / `metric selection history`。

**Integrity Gate（承担者 `S-Integrity`）：** benchmark cherry-picking / data leakage /
metric misuse / post-hoc selection bias —— **不通过即不得提交**，
**不是**「记一条 warning」（对比 R10 的 `RESOLVED` / `ACCEPTED_LIMITATION` 闭合规则）。

**审计时机（Wave 1 已冻结）：**

| 阶段 | 有什么 artifact | 允许要求什么审计 |
|---|---|---|
| R7 / R8 | **没有** code / logs / failed runs | **只能审「计划中的证据契约」** |
| R9 之后 / R13 | 完整 trace | artifact-aware 审计（含 Integrity Gate） |

**禁止在无 artifact 的阶段要求 artifact 审计** —— 那会产出一条永远无法执行、只能填「待补」的规则。

**失败的实验不得在审计里消失**：`state_check.py` V4 + V12 是机械前置。

## 读 / 写 World Model（强制）

| 阶段 | 读 | 写 |
|---|---|---|
| **R7** | `claims` / `evidence` / `hypotheses` | `assurance` / `failures` / `uncertainties` / `known_flaws`（把新 `F` 挂上） |
| **R13** | 全 state + artifact | `reviews` / `failures` / `experiments[].unexpected` / `known_flaws`（把新 `F` 挂上）；缺口**必须**交 R10 |
| **R14** | 全 state + 未闭环 `repairs` | `decision` / `repairs[].closure` / `uncertainties[].status` / `hypotheses[].status`（**不含 `claims[].status`** —— `killed` 只能经 R10） |

> 权威定义见 [research-state-policy.md](research-state-policy.md) §5；本节与它**必须逐字一致**。
> 回写后跑 `python3 scripts/state_check.py --check .research-idea-pipeline/routes/<R>/research-state.json`，**硬违规须为 0**。
