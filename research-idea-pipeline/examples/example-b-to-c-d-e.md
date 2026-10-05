# 示例：串联调用 B → C → D → E

演示主链路：从 idea 出发，到方案，到**多 preset 叙事选型**，最后到八子代理方案复核。

> 字母顺序即工作流顺序：**A 文献调研 → B idea 发现 → C 方案生成 → D 叙事生成 →
> E 方案复核**。本示例走 B→C→D→E，R2 / R5 按需在任一步被调用。

---

## 1. 调用 R3—R6（idea 发现）

```
调用 research-idea-pipeline，phase=R3-R6
输入：领域关键词="扩散模型 + 组合优化"，参考文献=[...]
```

**执行要点：**

1. **B1** 调用 R2 / R5（**必须走 R2 / R5 或等价的脚本调用，禁止内联自行实现检索**）：
   本地 + 多源并集检索（本地命中不终止），产出技术路线归纳表与创新性边界。
2. **B2** 逐路线做深度局限性分析 —— 每条"没做到"必须指向**具体未建立的结构性质**。
3. **R3** **同一轮并发**按 island 分轨生成候选（`P1`—`P6`，上下文隔离）；**子代理只做快筛与致命反驳**，不派会议审稿人（原「派 7 个头脑风暴子代理」指示已在 Wave 3 作废）。旧文如下，仅供追溯：
   ~~派遣 7 个头脑风暴子代理（R-CVPR / R-ICML / R-NeurIPS / R-MICCAI /
   A-Author / A-Experimenter / S-Devil），每人 ≥3 个 idea，**原始候选 ≥10、去重后 ≥6**。
4. **B4** 标注每个 idea 的推导策略。
5. **B5 idea 级审核（不可跳过）** —— 对每个候选派 四审稿人（创新性）+ S-Lit/S-Nov
   （重叠度）+ S-Feas（概念可行性）+ S-Theory（前提）+ S-Devil（致命反驳）。
   **不派 S-Repro。** **进入 population 的门槛 = 完成 L2**。只有要写进文档的
   「首次提出」类声称才要求 **L3**（并附负检索记录）。
6. **B6** 输出：**原始候选 ≥10、去重后 ≥6** 个 idea（每个带审核结论）+ **QD archive（每个 niche 一个 elite）** + 失败记忆。

**产物片段：**

| 编号 | 推导策略 | 核心思路 | 与现有工作差异 | 贡献类型 | 来源 | 创新性 | 可行性 | 重叠度 | 优先级 |
|---|---|---|---|---|---|---|---|---|---|
| I1 | 假设挑战 | 用扩散过程的可逆性约束组合优化搜索空间 | 现有方法把扩散当采样器，未利用可逆性作可行性约束 | Concept & Feasibility | `R-Novelty`（原 R-ICML） | 4 | 3 | 足够 | 高 |
| I7 | 组合创新 | 把 A 的注意力机制搬到 B 的图搜索 | 仅换模块，无新结构性质 | Use-Inspired | A-Author | 2 | 4 | 不足 | 建议放弃 |

**落盘：** `routeA/docs/A002-ideas.md` + 更新 `routeA/INDEX.md`

→ `next_phase_suggestion: "R8"`

---

## 2. 调用 R8（方案生成）

```
调用 research-idea-pipeline，phase=R8
输入：idea="I1: 用扩散模型的可逆性约束组合优化搜索空间"
```

**执行要点：**

1. **C1** 四审稿人视角独立评估创新性并**引用具体标准条目**。S-Lit 核实最接近
   先前工作并给出重叠度判定。I1 的 B5 结论是「重叠度 = 足够」→ 按 C1 的
   **增量复核**规则，**不重做 L3**，直接引用 B5 结论并标注其 `search_level`。
   若 B5 只到 L2，本步结论就按 L2 表述（「据本次检索未见」）。
2. **C2** S-Feas 给可行性评分 + 瓶颈。S-Theory 检查理论基础与隐含假设。
3. **C3** 六节提案展开，其中第 4 节动机必须回答"为什么之前没人这么做"。
4. **C4** 十四节（0—13）实验流程，含贡献—实验映射表与证伪条件。

**产物：** 论文提案（1500—2000 字）+ 实验流程计划书 + 创新性判定 + 可行性评分
+ 风险清单。

> 贡献编号用 **K1/K2**（不用 C1），避免与 R8 的章节号 C1—C7 混淆。

**落盘：** `routeA/docs/A003-proposal.md` + `routeA/docs/A004-experiment-plan.md` + 更新 INDEX

→ `next_phase_suggestion: "R12"`

---

## 3. 调用 R12（叙事生成与审稿）

```
调用 research-idea-pipeline，phase=R12
输入：idea=I1（含 B5 审核结论），proposal=上一步输出，目标会议=ICML
```

**执行要点（D0—D9，顺序不得跳）：**

1. **D0 证据台账**：把已有实验 / 定理 / 文献登记为 `E1`、`E2`、…（路线内唯一，不复用）。
   每条标 `epistemic_status`（`Observed` / `Supported` / `Hypothesized` / `Planned` / `Unknown`）。
   **不得把 `Planned` 写成 `Observed`。** 无证据的条目留 `[待补]`。
2. **D1 Claim Graph**：写 `C0`—`C5`，每条挂 `Ci ← Ej` 或标 `[待补]`。
   `C0` 必须一句话。**只有 `Observed` / `Supported` 的 `Ej` 可以被引用。**
3. **D2 科学分类**：本例登记 `(Method, hidden-assumption, design-algorithm)`。
   枚举值一律用英文原样，各轴取单值，**不得**拼接。
4. **D3 Anchor Eligibility**：逐 anchor 判 `eligible` / `conditional` / `not-eligible`。
   本例作者想定位成 `理论`，但证据支持的是 `性能` 与 `现象` → **必须显式告知**
   「你想定位成理论，但现有证据支持的是性能。最强可辩护 anchor 是性能」，
   并写进路线 INDEX 的 Warnings。**不得**帮作者强化不被证据支持的故事。
5. **D4 叙事实现**：本例是**跨域类**，所以**必须做一次 anti-application stress test**
   （至少测 `N2` / `N3` / `N5` / `N9`），再生成 **2—4 套真正不同的 claim hierarchy**。
   每套写满**六槽位** `S1`—`S6`：`S5` 给出 `Ci ← Ej` 对照，`S6` 写出**不成立的条件**。
   详写的候选 **≥300 字**，其余候选给摘要。**同一 claim 换四种措辞不算候选。**
6. **D5 攻击面审核**：六个攻击面审稿人**全部派遣** —— `R-Novelty` / `R-Causal` /
   `R-Experimental` / `R-Theory` / `R-Generalization` / `R-Utility`，每人只在**自己的
   主责维度**给一个 `1—5`。`S-Lit` **恒派**（本例判「部分重叠」）。`S-Devil` 必派但
   **不打分**：出致命弱点清单 + 最简解释反例，逐条处置（接受或反驳）。
   攻击面判定**不进任何向量**，只喂门禁与逐维理由。**不得**声称 reviewer consensus。
7. **D6 venue calibration**：顺序固定为 `contribution type → evidence contract →
   venue calibration`。**不得按 venue 选 preset**，也不派遣会议审稿人。
8. **D7 硬门禁**：逐项判 `G1 Claim grounding` / `G2 Prior-work distinction` /
   `G3 Identification` / `G4 Factual integrity` / `G5 Venue scope`，
   每项写出**依据位置**。任一 `fail` ⇒ `not_submission_ready`，**不参与排序**。
9. **D8 六维排序**：只排**通过门禁**的候选。六维是 `Significance` / `Originality` /
   `Soundness margin` / `Explanatory depth` / `Generality` / `Narrative compression`，
   **全部同向（高 = 好）**，因此 R12 **不做极性归一化**。
   `Soundness margin` 的实验侧与理论侧**两个读数并存，不得平均**。
   排序写出**胜负维**与**代价维**，不给综合总分。
10. **D9 输出**：最佳叙事 + runner-up + 逐维胜出理由 + 致命风险 + **缺失证据清单**
    + **最小必要实验 / 定理**。

**产物片段（候选对比）：**

| preset | `C0` 一句话 | `(O, T, R)` | anchor（资格） | 门禁 G1—G5 | 六维（S/O/SM/ED/G/NC） |
|---|---|---|---|---|---|
| N2 瓶颈突破/移除假设 | 在 `Y` 下结构性失效。改为硬约束可恢复可行性 | (Method, hidden-assumption, design-algorithm) | 性能（`eligible`） | 全 `pass` | 5/4/3/4/3/4 |
| N9 矛盾解决 | 「可逆性是否必要」的矛盾来自口径差异 | (Phenomenon, contradiction, explain) | 现象（`eligible`） | 全 `pass` | 3/3/5/4/2/5 |
| N3 跨域理论迁移 | 两领域共享结构 `S`，且满足迁移条件 `C` | (Method, hidden-assumption, prove) | 理论（`conditional`） | `G1 fail` | 不参与排序 |
| N5 统一框架 | — | — | — | — | stress test 排除 |

> **N3 的 `G1 fail` 来自 `C0` 的迁移条件半支没有证据**（L2 不变量待补）。
> 门禁 `fail` 的候选**不得**推荐为最佳，也**不进排序表**。
> **N5 被 stress test 排除**：现有证据只有一类方法，写不出「多类方法各自是特例」，
> 只能退化成「把 B 用到 A」。
> `S-Lit` 判「部分重叠」：机制层重叠、结论层不重叠 → 相关工作需显式划界。

**包装前后对照（N2）：**

| | 表述 | 依据 |
|---|---|---|
| 包装前 | 我们提出了一个可逆性约束模块 | — |
| 包装后 | 现有离散扩散方法共享**「可逆性仅作采样技巧」**这一假设，导致在置换约束下**结构性失效**。我们移除该假设 | `C2 ← E1`、`C3 ← E4`、`C0 ← E3` |
| 判定 | 只改参照系，未改事实 | 每句都能落回 `Ci ← Ej` |

**落盘：** `routeA/docs/A005-narrative.md` + 更新 INDEX（门禁 `fail` 的候选 → §4 已证伪。
缺失证据与 anchor 冲突 → §5 TODO 与 §7 Warnings）

→ `next_phase_suggestion: "R8 | R7 / R10 / R13"`

---

## 4. 调用 R7 / R10 / R13（方案复核）

```
调用 research-idea-pipeline，phase=R7,R10,R13
输入：proposal=上一步输出，best_narrative=上一步的最佳叙事
```

**执行要点：**

1. **E1** 判定为**首次复核**（触发点 ①：R8 刚产出后，无上一次审阅内容）。
2. **E2** 派遣八子代理：每人 **1—5 分** + ≥200 字意见（S-Repro ≥150 字）。
   四个会议审稿人的意见必须分 **理论角度 / 应用角度 / 会议特性判定** 三段。
   焦点是**方法正确性与工程可行性**，不重复 B 的概念评估。
3. **E2.2 防复现检查** —— S-Lit 主责，逐项回答六项：

   | 检查项 | 判定 |
   |---|---|
   | 1 是否存在可一对一对应的已有方案？ | 部分 |
   | 2 增量是设计改变还是实现优化？ | 设计改变 |
   | 3 是否触及新的结构性质？ | 是（可逆性作为硬约束） |
   | 4 原样重跑已有方案，本方案声称是否仍成立？ | 否 |
   | 5 是否只是换数据集/backbone？ | 否 |
   | 6 最接近工作的作者会认为是独立贡献还是后续工作？ | 独立贡献 |

   → **复现风险等级：低**（第 5 项若改的是"问题定义 / 评估口径"而非"换数据/换 backbone"，
   需**单独论证**是否构成设计贡献，不自动等于风险高）

4. **E3** 交叉质询：每人至少一条质疑。评分差 ≥2 分记录分歧。**先做极性归一化**
   （S-Devil 反驳分 → `新颖性稳健度 = 6 − 反驳分`）后再汇总取**中位数**。
5. **E4** 结论卡片（含**复现风险等级**与**方法正确性判定**）。

**落盘：** `routeA/docs/A003-review-r01.md` + 更新 INDEX（结论翻译成进度条目）

---

## 5. 全链路落盘结果

```
routeA/
├── INDEX.md                              # 文档索引 + 已证实/已证伪/TODO/Bugs/Warnings
├── code/
└── experiments/

docs/
├── A001-literature-survey.md             # R2 / R5（按需）
├── A002-ideas.md                         # R3—R6（含 I1..In 与 B5 审核）
├── A003-proposal.md                      # R8
├── A004-experiment-plan.md               # R8
├── A005-narrative.md                     # R12（一次调用：I1 的 2—4 套 claim hierarchy + 六槽位 + 门禁 + 最佳推荐）
└── A003-review-r01.md                        # R7 / R10 / R13（含复现风险等级）
```

`.research-idea-pipeline/` 下另有 `state-B-*.json`、`state-C-*.json`、`state-D-*.json`、
`state-E-*.json` —— 机器状态，**不进 docs**。
