# R3—R6 — 双轨发现与种群进化（dual-discovery → isolated populations → evolution）

**R3—R6 的定位是「概念级」。** 它回答 **「这个方向 / 概念值不值得做」**：
文献上是否已被覆盖、概念上是否非平凡、方法路线上是否成立。
它**不**回答「这个方案做得对不对」——那是 R7 / R10 / R13 的职责（见 §R3—R6.0）。

---

## R3—R6.0 与 R7 / R10 / R13 的分工（必须先明确，避免重复劳动）

| 维度 | R3—R6（idea 级） | R7 / R10 / R13（方案级） |
|---|---|---|
| **对象** | 一句话级 idea / 技术方向 | 成型的 proposal + 实验计划 |
| **核心问题** | 这个概念值得做吗？ | 这个方案做得对吗、能不能做成？ |
| **创新性** | 方向是否已被覆盖、是否非平凡 | 方案是否**实质复现**已有工作（防复现） |
| **可行性** | 概念可行性：路线是否成立、资源是否现实 | 工程可行性：具体做法能否跑通、变量是否可控 |
| **正确性** | 前提是否自洽、有无明显逻辑缺口 | 方法正确性：推导 / 实现 / 指标 / 统计是否成立 |
| **理论** | 是否需要理论支撑、前提是否合理 | 证明是否成立、假设是否必要 |
| **复现性** | **不涉及**（无代码，不派 `S-Repro`） | **必查**（`S-Repro`） |
| **审查深度** | 快筛：双评分 + 一条致命反驳（见 §R3.7） | 深审：六个攻击面 + 交叉质询 + 逐维中位数 |
| **产出** | **未排序的** population + QD archive + 淘汰理由 | 审查结论卡片 + 修改建议 |

**一句话记法：R3—R6 管「值得做吗」，R7 / R10 / R13 管「做对了吗」。**

---

## R3—R6.1 输入

| 输入 | 必填 | 说明 |
|---|---|---|
| 研究领域关键词 | ✅ | 1—3 个核心方向词 |
| 已有参考文献 | ❌ | 用户提供的种子文献 |
| 资源约束 | ❌ | 算力 / 数据 / 时间 / 是否要求开源可控 |

**若关键词缺失或过泛**（如「深度学习」），先反问收敛，不要直接开跑。

> **锚定点（核心目标）必须先确认**（见 [../SKILL.md](../SKILL.md) §0.1）。
> 本阶段受锚点约束：**理论**锚点优先「假设挑战」类推导，**性能**锚点优先「问题重构 /
> 组合创新」；**population 只收服务主锚点的 idea**，与锚点无关的候选即使新颖也降级。
> 锚点与候选明显不匹配时，**在同一份输出里显式指出冲突**。
>
> **派遣方式：** 环境有 Team 能力时**必须先询问用户**是否使用 Team；用户显式要求但
> 环境不具备时须**显式回退**并告知（见 [../SKILL.md](../SKILL.md) §3.1）。

---

## R3—R6.2 基础文献调研与领域归纳（必须走 R2 / R5 或等价的脚本调用）

- **检索必须走 R2 / R5**（或等价的
  [literature_search.py](../scripts/literature_search.py) 调用），
  按 [literature-policy.md](literature-policy.md) 规范检索**本地 + 多源**
  （先本地、再 arxiv；**本地命中不是终点，仍须扩检**，429 指数退避）。
- **禁止内联自行实现一套检索。** 自行实现检索会**绕开 R2 / R5 的全部纪律**
  （T1—T7 触发、L3 饱和判据、每源状态、负检索记录）。走 R2 / R5 / 等价脚本时，必须
  保留其**检索式、每源状态与负检索记录**。
- **注意：本次调研支撑后续的创新性审核，属于 T4 / T5 触发场景**（**本节是概念级快筛，
  按 T4 的例外执行 L2**，见 [literature-policy.md](literature-policy.md) §2 的 T4 行），
  因此本地命中后仍必须执行**在线源**检索；检索等级门槛见 §R3.7。
- 建议检索量：`max_results ≥ 20`；不足时按 R2 / R5 的 A3 策略扩大范围。
- **产出：**
  1. **技术路线归纳表** —— 把文献聚类为 3—6 条技术路线。
  2. **创新性边界** —— 分为三区：
     - 🔴 **红海**：竞争激烈、增量空间小
     - 🟡 **蓝海苗头**：有初步信号但未成熟
     - ⚪ **无人区**：检索未见覆盖（**必须标注检索式，且默认标「待核实」**）

**技术路线归纳表模板：**

| 路线 ID | 路线名 | 代表工作 | 核心机制 | 关键假设 | 理论工具 | 覆盖密度 |
|---|---|---|---|---|---|---|
| L1 | … | [作者, 会议/年份] | … | … | … | 红海 / 蓝海 / 无人区 |

---

## R3—R6.3 深度局限性分析

逐路线分析三件事：

| 路线 | 做到了什么 | 没做到什么 | 普遍局限性 |
|---|---|---|---|
| L1 | … | … | … |

**强制约束（硬性）：**

- **禁止模糊表述。** 不许写「效果不够好」「泛化性差」「缺乏理论」这类空话。
- 每条「没做到」**必须关联具体未建立的结构性质或未满足的理论条件**，例如：
  - ✅ 「未建立**置换等变性**，因此组合结构的顺序变化会导致解不稳定」
  - ✅ 「收敛性证明依赖**强凸性假设**，而目标函数在实际离散空间中非凸」
  - ❌ 「缺乏理论分析」

---

## R3. 双轨发现（**上下文隔离是硬规则**）

> **谁生成候选（Wave 4 裁决，取代 Wave 3 的「执行者分轨生成」）：**
> **R3 的候选由隔离 Exploration Agents 按 island 独立生成。** 中央执行者只负责构造各 island
> 的最小共享输入、实施上下文隔离、`typed intermediate` 路由、收集与结构化候选、分配 ID
> 和写入 Research State，**不得跨 island 补写或融合候选**。R3 生成阶段结束后，才允许调用
> 快筛 / 对抗代理做 concept-level collision check 与致命反驳。**生成代理不得自评 novelty
> 或投稿价值。** 「派遣 7 个具名子代理各出 ≥3 idea」**已作废**（那是 persona 多样性，
> 见 §R3.3；本阶段冻结的是 **operator 多样性**）。

```text
Exploration Agents generate divergence;
Assurance Agents   attack;
Executor           orchestrates and records.
```

| 主体 | R3 职责 | **禁止** |
|---|---|---|
| `P1`—`P6` Exploration Agents | 在**各自受限算子空间**内独立生成 raw hypotheses / reframings / analogies / theory lenses | 不给自己打 novelty 分；不声称「首次」；**不看其他 island 的候选** |
| `local` Exploration Agent | 在**已有范式内**生成稳健局部候选 | 不进入 paradigm islands |
| 中央执行者 | 构造共同 seed `S0`、实施上下文隔离、`typed intermediate` 路由、汇总、结构化、分配 ID、写 state | **不补写「更聪明的候选」**；不把 island A 的结果喂给 island B |
| 快筛 / `S-Devil` / `S-Lit` | **generation 完成后**做 concept-level collision check 与致命反驳 | **不参与第一轮生成** |

**两条边界（互为护栏）：**

1. **Exploration Agent 没有权力否决自己的 idea。**
2. **Assurance Agent 没有权力偷偷生成一个完全不同的新主方案**（它的攻击可以触发 R6 `mutation`）。

```text
                 ┌── Local Search ─────── 已有 gap / 机制改进
problem ─────────┤                        （基线：把现状做到更好）
                 └── Paradigm Escape ──── P1 Reframe            改问题 ontology
                                          P2 Assumption         摧毁 tacit assumption
                                          P3 Abstraction        先做 domain erasure，出 domain-free skeleton
                                          P4 Remote Analogy     吃 P3 骨架找结构同构（Wave B）
                                          P5 Theory Lens        换一套数学语言并导出后果（Wave B）
                                          P6 Counterexample     反例 / 不可能性 / 测量反转生成方向
```

**硬规则：**

1. **各 island 在产生候选之前不得互相看到候选内容。** 理由：`early communication → idea convergence` ——
   若第一轮就共享答案，发散度会塌成一条。**隔离是机制，不是建议。**
   **隔离的对象是「候选内容」，不是「规范化中间表示」**（边界见 §R3.4）。
2. **`P3` 必须先做 domain erasure**：删掉 `MRI / CT / flow / reconstruction` 这类领域词，
   只留数学骨架（`domain-free skeleton`）；**`P3` 不产完整方法**。
3. **`P4` 的跨域联系必须逐维对应**：`object ↔ object`、`relation ↔ relation`、
   `constraint ↔ constraint`、`failure mode ↔ failure mode` **四维都要写出来**。
   只说「两边都有 distribution shift / optimization / uncertainty」**不算**结构同构。
4. **`P5` 每个 theory lens 必须产出下列五类后果中至少两个**：新 explanation / 新 boundary 或
   impossibility / 新 prediction / 新 algorithmic design / 新 discriminating experiment。
   做不到就是**理论包装**，退 `failures[]`（`kind: unsupported`）。
5. **`P6` 产出的方向必须写成可证伪命题**（否则它是抱怨，不是研究问题）。
6. 每轨的候选都写 `island`（`P1`—`P6` / `local`；**默认启用 `P1`—`P4`，`P5`/`P6` 按需**）、
   `operator`、`parents: []` 与 `generation: 0`（**V13 / V14 / V16 / V17 强制**）。

### R3.0 `claims[]` 的创建归属（总收官审计 M-1）

**每个候选必须产出至少一条 `C`** —— 它的 central proposition，`status: ungrounded`。
这是 claim graph 的**唯一起点**：

| 阶段 | 对 `claims[]` 做什么 |
|---|---|
| **R3** | **创建**（seed：`status: ungrounded`，`falsifier` 必填） |
| R7 | **读**（攻击它；输出 `assurance`，不改 `status`） |
| **R8** | 建 `claims[].contract`、更新 `supporting_evidence` / `refuting_evidence` / `scope`；挂证据时做**证据驱动的单向升级**（`ungrounded` → `partially-supported` / `supported`） |
| R10 | **降级与否决的唯一阶段**（`contradicted` / `killed`） |
| R12 | **只读**（渲染成 `narrative_view`，**不创建、不修改**） |

**为什么必须写在这里：** 双循环里 R7（对抗保证）与 R8（证据契约）都排在 R12 之前，
若 claim 由 R12 创建，则 R7 / R8 在读一个没人写的对象 —— `state_check.py` 的
V1 / V2 / V3 会**永不触发**，world model 变成没有 claim 的空壳。

### R3.1 生成预算（默认值，可缩放）

| 项 | 默认 |
|---|---|
| islands 数 | **默认 4**（`P1`—`P4`，各占独立预算）+ Local Search；`P5`（Theory Lens）与 `P6`（Counterexample & Measurement inversion）**按需启用**（枚举里合法，但不占默认预算；启用即上调，须说明理由） |
| 生成主体 | **每个 island 一个独立 Exploration Agent**（各自上下文，互不可见；见 §R3.3 / §R3.4） |
| 每 island 候选数 | **下限 3，上限 6**（超上限须显式说明为什么值得） |
| 进化轮数上限 | **2**（见 R6） |

**可缩放：** 领域过窄或资源受限时，可在 R0 `contract.constraints` 写明并降到 **2 islands × ≥2 候选**；
**上调上限需要用户同意**。

### R3.2 与 Local Search 的分工

Local Search 不是「对照组」——它负责**把现状做到更好**，其候选同样进 population 与 QD archive。
**但两阶段 fitness 对它在 Search 期一视同仁**（见 R6.3）：不许因为它「更可行」就优先。

### R3.3 是「算子多样性」，**不是**「人格多样性」

| 模式 | 长什么样 | 裁决 |
|---|---|---|
| **persona diversity**（旧流程） | `R-CVPR` 想三个 idea、`R-ICML` 想三个 idea、`R-NeurIPS` 想三个 idea | ❌ **不恢复** |
| **operator diversity**（本阶段） | 六个**不同搜索算子**在各自**受限空间**里产生候选 | ✅ **冻结** |

**六个算子的受限空间（每个算子只允许改变括号里的东西）：**

| island | 算子（`operator` 值） | 只允许改变 |
|---|---|---|
| `P1` | `reframe` — 问题重构 | scientific object / target variable / formulation / success criterion |
| `P2` | `assumption_breaker` — 假设破坏 | 从 Assumption Graph 出发：`AS_i → ¬AS_i →` 新的 research world |
| `P3` | `abstraction` — 领域擦除 | 只产 `domain-free skeleton` / alternative abstractions；**不产完整方法** |
| `P4` | `remote_analogy` — 远域类比 | 目标 `semantic distance high` + `structural correspondence high`（四维逐维对应，见硬规则 3） |
| `P5` | `theory_lens` — 理论视角 | 强制换 mathematical object，并导出 ≥2 类后果 |
| `P6` | `counterexample` — 反例 / 测量 | 从 impossibility / counterexample / evaluation inversion / observability failure **反向**生成 |
| `local` | `local` | **已有范式内**的稳健局部改进 |

### R3.4 隔离边界：隔离**候选内容**，不隔离**规范化中间表示**

**结论：`isolation applies to candidate content, not to typed intermediate representations.`**

| | 内容 | 是否可跨 island 传递 |
|---|---|---|
| ❌ **禁止传递** | 其他 island 的候选、其候选领域名、「我们希望找到 causal inference」这类暗示、nearest literature 的 method details | 不得 |
| ✅ **允许传递** | 经规范化的 `typed intermediate representation`，例如 `P3` 输出的 `abstract_skeleton` | 允许，**且必须已去领域词** |

**为什么：** 若 `P4` 看到「`P1` 已经提出把它当 causal transport」，它只是**重新发现** causal transport ——
跨域类比的价值归零。但 `P4` 本来就需要 `P3` 的骨架：把「完全不许传信息」写死，
会退化成六个互不相干的孤岛。

**硬规则：** 允许传递的中间表示**必须**类型化、已去领域词（object / relation / constraint /
failure mode / core unknown 五类槽位），**不得**夹带候选领域名、方法名或结论。

### R3.5 两波生成（**不是一次六代理齐发**）

**结论：`P3 → P4` 存在天然的演绎依赖，所以 R3 分两波。**

| 波 | 并行算子 | 输入 |
|---|---|---|
| **Wave A — Representation generation** | `P1` / `P2` / `P3` / `P6` / `local` | **只有共同 seed `S0`** |
| **Wave B — Representation expansion** | `P4`（吃 `P3` 的 `abstract_skeleton`）/ `P5`（可选吃 `P1` 的 alternative formulations） | **只读规范化中间表示，不读完整 candidate pool** |
| merge | 执行者汇总、结构化、分配 ID、写 state | — |

### R3.6 生成后的 hygiene 快筛（**`R3 screening ≠ R7 assurance`**）

**结论：快筛只做最低限度卫生检查；不能让 critic 在 idea 出生五分钟后就把它杀死。**

**可以杀（仅此六条）：**

1. 自相矛盾
2. 明显违反已知事实
3. 实际只是同一个候选改名字（结构簇重复）
4. 明显不可定义
5. 已知 prior work 完全覆盖
6. 与研究契约根本无关

**不得因为下列理由杀：**

工程风险高 / 暂时没有 theorem / 暂时不知道怎么实现 / 不像当前领域主流 /
venue fit 不明确 / 当前证据不足。

> **否则 paradigm idea 会在出生五分钟后被「可行性审稿人」杀死。**
> 完整的对抗保证保留到 R7；`P5` 所需的 theorem 与 `P3` / `P4` 的实现路径**不属于 R3 的判据**。

### R3.7 概念级审核：派遣与输出（强制，不可跳过）

**这是 R3—R6 与 R7 / R10 / R13 的分界点：本节是概念级快筛，不是方案级深审。**

对去重后的**每一个**候选执行审核。**禁止只给 idea 不给审核。**
派遣名单与 [roles.md](roles.md) §4.2 派遣矩阵的 `R3—R6` 列**必须逐行一致**。

| 角色 | 派遣 | 在快筛的职责 |
|---|:--:|---|
| `S-Lit` | ○ | **最接近先前工作 + 重叠度判定**（足够 / 边缘 / 不足） |
| `R-Novelty` | ○ | 新颖性攻击：delta 是否非平凡 |
| `R-Causal` | ○ | 更简单替代解释 |
| `S-Feas` | ○ | **概念可行性**：路线是否成立、资源是否现实、有无已知不可行结论 |
| `S-Devil` | ● | **一条最致命反驳**（「若只能写一条否掉它的理由」） |
| `S-Nov` | ○ | **独立新颖性核验**：`S-Lit` 判「边缘」，或 idea 要打「首次」时**必派** |
| `S-Theory` | ○ | **前提自洽性**（仅当 idea 含理论声称时派遣） |
| `R-Theory` | ○ | 同上；理论锚点路线优先 |
| `A-Author` / `A-Experimenter` | ○ | 投稿人论证 / 可验证性 |
| `R-CVPR` / `R-ICML` / `R-NeurIPS` / `R-MICCAI` | — | **不派**（只在 R12 / R13 的 calibration 表里出现） |
| `R-Experimental` / `R-Generalization` / `R-Utility` / `S-Repro` / `S-Integrity` | — | **不派**（方案级与 artifact 级职责） |

> **不派遣 `S-Repro`。** idea 阶段没有代码可复现；可复现性审查只在 R7 / R10 / R13 进行。

#### R3.7.1 检索门禁

- **进入 population 的门槛 = 完成 L2**（强化级，见
  [literature-policy.md](literature-policy.md) §3.1）。概念级快筛的 L2 检索广度
  已足以支撑 population 决策。
- **只有要写进文档的「首次提出」类声称才要求 L3**（穷尽级），且必须附
  **负检索记录**；「首次提出」的三项门禁见
  [evidence-policy.md](evidence-policy.md)（措辞等级统一在该文件，本节不另立）。
- **不可控例外：** 在线源因 429 / 不可用而无法达到对应等级（不可控因素）时，该 idea
  仍可进入 population，但必须：① 标注「据本次检索未见 · 待核实」；② **不得**使用
  「首次提出」；③ 记入 `STATUS.md` 的 **Critical uncertainties**，并在源恢复后补做。
- 无论哪种情况，未完成对应等级时都**不得**把新颖性判定标为「已核实」。

#### R3.7.2 每个 idea 的审核输出

```markdown
#### I3 审核

- **推导策略：** 假设挑战
- **新颖性判定：** 非平凡 / 边缘 / 不足（`S-Lit` + `R-Novelty`）
- **最接近先前工作：** [作者, 会议/年份]（`S-Lit`）
- **重叠度：** 足够 / 边缘 / 不足
- **更简单替代解释：** ……（`R-Causal`）
- **概念可行性：** 成立 / 有缺口 / 不成立（`S-Feas`）
- **理论前提：** 自洽 / 有缺口 / 不适用（`S-Theory`，按需）
- **检索等级：** L2 已达成 / 未达成（population 门槛）；若含「首次提出」声称则须
  另标 L3 已达成 / 未达成；未达成对应等级时标「据本次检索未见 · 待核实」
- **致命反驳（`S-Devil`）：** ……
- **反驳是否可缓解：** 是（缓解路径：……）/ 否
```

> **快筛不做总分排序。** 这里只输出「可杀 / 不可杀」与上述判定。
> 候选的取舍走 **`R4.2` 的 QD archive**（每个 live niche 留一个 `elite`）
> 与 **`R6.3` 的两阶段 fitness** —— **不得**据此把候选筛到 3—5 个。

### R3.8 发散策略约束

**每个候选必须通过以下至少一种策略推导，并在输出中标明是哪种：**

| 策略 | 含义 | 自检问句 |
|---|---|---|
| 问题重构 | 重新定义要解决的问题 | 我们是否在解一个错的问题？ |
| 假设挑战 | 质疑现有工作的前提假设 | 哪条假设其实不必成立？ |
| 跨域迁移 | 借其他领域的方法 / 视角 | 领域 X 怎么解这个结构？ |
| 反向思考 | 从失败 / 反面出发 | 如果目标反过来会怎样？ |
| 组合创新 | 创造性组合已有想法 | 把 A 的机制接到 B 的问题上会怎样？ |

> **反模式：** 仅写「把 X 用到 Y 上」而不说明**为什么这个组合会产生非平凡的新性质**，
> 不计入组合创新。

> **与算子的关系：** 本表是**推导正当性自检**；`R3.3` 的十二算子表是**生成空间约束**。
> 一个候选必须两者都满足。

---

## R4. 隔离种群 → structural signature → QD archive

### R4.1 聚类必须用结构性距离，**不得用文本 embedding**

两个文字完全不同、本质都是「feature consistency loss」的候选，必须被识别为同一 cluster。
因此用 `structural_signature` 的五维距离（V13/V14 之外，五键本身由 `state_check.py` 校验形状）：

| 维 | 问的是 |
|---|---|
| `assumption_distance` | 依赖的假设差多远 |
| `formulation_distance` | 问题表述差多远 |
| `representation_distance` | 数学表示差多远 |
| `theory_lens_distance` | 理论坐标系差多远 |
| `mechanism_distance` | 机制解释差多远 |

**同一 cluster 内保留 1 条**（避免同质候选占满 archive）；跨 cluster 一律保留。

### R4.2 Quality-Diversity archive（**不是 Top-K**）

**禁止** `21 ideas → 打分 → Top-3 → 丢掉其余`。改为每个 niche 留一个 elite：

```text
Niche N2（瓶颈突破/移除假设）        elite: H12
Niche N5（统一框架）                 elite: H31
Niche N3（跨域理论迁移）             elite: H44
Niche N10（不可能性/负结果）         elite: H59
Niche N8（Benchmark/评测）           elite: H62
```

- **niche 取值就是 `N1—N10` preset 名** —— 复用已冻结的 10 套，**不引入第二套枚举**（V6 强制）。
- **`state_check.py` V15 强制**：每个出现过的 niche 至少有一条 `status: elite`。
  没有 elite 的 niche 要嘛补一条 elite，要嘛就不要开这个 niche。
- **为什么**：只留综合分最高的一个，会让「可行性 5 的增量 idea」把「可行性 2 的范式 idea」
  提前杀掉 —— 那正是 increment attractor 的入口。

### R4.3 archive 的更新规则

| 事件 | 动作 |
|---|---|
| 新候选进 archive | 与该 niche 的 elite 比较；胜者 `elite`，败者 `active`（**两者都留在 population**，不删） |
| 某 niche 的 elite 被 R7 判 `已被覆盖`，或被 R14 `archive` | elite 转 `archived`，**必须同时**把同 niche 的另一条升为 `elite`。**若该 niche 只有这一条候选，则 R14 不得把它 `archive`** —— 用 `decision`（`pivot` / `archive`）表达"这条路停止"，**不要**靠改 `hypotheses[].status` 来表达；否则 V15 会在下一次校验时报出。**本仓库没有"关闭 niche"机制，不要发明它。** |
| 候选被 R6 判 `killed` | `status: killed` 并写 `failures[]`（`kind: deprioritized`） |

---

## R6. 进化与两阶段 fitness

### R6.0 R3 / R4 / R6 的边界（三句话冻结）

```text
R3: Diverge              让不同世界出现
R4: Preserve Diversity   不让这些世界被总分排序压扁
R6: Recombine            才允许不同世界互相借东西
```

**谱系（genealogy）强制：** 每次 R6 进化必须在子候选上写 `operator`（五个进化算子之一）
与 `parents`（父候选 `H` id 数组，**至少一个**），并让 `generation` 递增。**V16 / V17 强制。**

> 没有谱系就无法回答「**哪种算子最容易产生有效的范式创新**」—— 而那正是本 Wave 想度量的东西。

### R6.1 进化算子（五种，按序优先使用前三种）

| 算子 | 做什么 |
|---|---|
| `mutation` | 改一个 structural signature 维度 |
| `cross-domain crossover` | **跨 island** 组合两个候选的表示与机制（`P3` 抽象骨架 × `P4` 远域类比最常配对）。**这是唯一允许跨 island 融合的阶段** —— R3 严禁早熟收敛，见 R6.0 |
| `simplification` | 删掉不必要假设 —— **删比加优先** |
| `theory-induced deduction` | 从某个 theory lens 推出新命题 |
| `new niche creation` | 现有 niche 都不合适时开新 niche（须同时给出 elite，否则 V15 失败） |

**每次进化 `generation + 1`**；到 **2 轮**仍未收敛 → 落 `uncertainties[]` 并交 R7，**不得无限进化**。

### R6.2 保多样性：`island` 与 `niche` 都不许塌

- 进化不得让某个 island 的候选全被 `killed`（全灭说明该轨的提问方式有问题，应作为
  `uncertainties[]` 记下来，而不是静默消失）。
- 进化不得让某个 niche 失去 elite（V15 会在下一轮校验时报出来）。

### R6.3 两阶段 fitness（**Wave 2 最重要的纪律**）

| 阶段 | 只看 | **不看** |
|---|---|---|
| **Search（R3—R6）** | `representation_distance` + `structural_novelty` + `cross_domain_surprise` + `deductive_yield` | **venue fit** |
| **Selection（进 R7 之后）** | novelty / validity / importance / testability / `EIG ÷ cost` | — |

> **在搜索期优化 venue fit，正是杀死范式 idea 的机制。** R3—R6 的任何排序、
> 任何「优先做哪个」的表述里**都不许出现会议适配**（**消歧：** 会议审稿人角色在 R3—R6 仍可用于 concept 级快筛，但**不得**用「会议适配度」
排序候选；`venue-standards` 作为**排序依据**只在 R12/R13 生效）。

**`expected_information_gain` 在 Search 期只作为记录**，不作为排序依据 —— 它属于 Selection 阶段。

**`coverage before ranking`（Wave 4 加严）：`cross_domain_surprise` 与 `deductive_yield`
在 generation-0 只作 archive descriptors / search heuristics，不得用于硬排序。**
否则 `P4`（远域类比）与 `P5`（理论视角）会因为「跨域 / 理论」标签天然拿到更高 reward ——
系统只是把一个偏置换成另一个偏置。**第一代的唯一目标是覆盖度；质量压力从 R6 起才逐步引入。**

---

## R3—R6 交付物与落盘

**核心交付物：** population + QD archive（每个 live niche 至少一个 `elite`）
+ 技术路线归纳表 + 创新性边界界定 + 失败记忆。

> **不产出「shortlist」或「QD archive 的 elite 集合（3—5 个）」。** 该概念自 Wave 2 起作废。

| 交付物 | 内容 |
|---|---|
| **population + QD archive** | 每个候选带 `island` / `operator` / `niche` / `generation` / `structural_signature` |
| **idea 候选清单** | 每个候选一行：推导策略 / 核心思路 / 与现有工作差异 / 贡献类型 / 方法来源 / 审核结论 |
| **技术路线归纳表** | 见 §R3—R6.2 |
| **深度局限性分析** | 见 §R3—R6.3 |
| **创新性边界界定** | 红海 / 蓝海苗头 / 无人区（见 §R3—R6.2） |
| **淘汰清单** | 被放弃的候选 + 理由。**不得删除**：写 `failures[]` |

**idea 候选清单模板：**

| 编号 | 推导策略 | 核心思路 | 与现有工作差异 | 贡献类型 | 来源 island | 新颖性 | 概念可行性 | 重叠度 |
|---|---|---|---|---|---|---|---|---|
| I1 | 假设挑战 | … | … | Concept & Feasibility | `P2` | 非平凡 | 成立 | 足够 |
| I2 | … | … | … | … | … | … | … | … |

**创新性边界界定模板：**

```markdown
### 创新性边界界定

**红海：** …（为什么拥挤：……）
**蓝海苗头：** …（初步信号：……）
**无人区：** …（检索式：……；**待核实** —— 需 `S-Lit` 复核）
```

**落盘步骤：**

1. **写文档：** `routes/<R>/docs/<R>NNN-discovery.md`（按
   [project-layout.md](project-layout.md) §2.6 扫描现有最大序号 +1）。
   内容 = 上表的全部交付物。
2. **frontmatter：** `phase: R3—R6` / `type: discovery` / `status` / `created`。
3. **更新该路线 `INDEX.md`：** `Key Documents` 新增本文件行，`Recent Research Changes` 同步更新。
4. **更新该路线 `STATUS.md`：** 先写回 `research-state.json`，再用
   `scripts/render_status.py` 重新生成。**不得手工编辑 `STATUS.md`。**
   - 被 `S-Lit` 判「重叠足够」的方向 → **Strongest supported findings**
   - 被判「重叠不足」或致命反驳不可缓解而**放弃**的候选 → **Most important negative findings**
   - 未完成 L2 的「无人区」声称、未完成 L3 的「首次」声称 → **Critical uncertainties**
   - 进入 R8 的 elite、待核实的无人区检索 → **Next recommended actions**

**进入 R8 的是 QD archive 的 `elite` 集合（每个 live niche 一个），不是「从 population 挑 1—3 个」。**

> **回写的是 Research World Model**，不是 `state.json` 片段。
> 写入 `hypotheses[]` / `claims[]` / `failures[]` / `literature[]` / `uncertainties[]`；
> 骨架见 [research-state.template.json](../templates/research-state.template.json)。
> 回写后**必须**跑 `python3 scripts/state_check.py --check .research-idea-pipeline/routes/<R>/research-state.json`，
> **硬违规须为 0**（exit 3 = 硬违规，exit 4 = 结构不符）。

---

## 读 / 写 World Model（强制）

| 阶段 | 读 | 写 |
|---|---|---|
| **R3** |`literature` / `assumptions` / `failures` / `contract.constraints` | `hypotheses`（**含 `niche` / `island` / `operator` / `parents: []` / `generation: 0`；同一 niche 至少一条 `elite`**）/ `claims`（**seed**：每个候选至少一条 `C`，`status: ungrounded`） |
| **R4** |`hypotheses` | `hypotheses[].status`（**QD archive 精修：重排 elite 归属**） |
| **R6** | `hypotheses` / `uncertainties` / `failures` | `hypotheses[].generation` / `hypotheses[].status` / `hypotheses[].operator` / `hypotheses[].parents` / `failures` / `known_flaws`（把新 `F` 挂上） |

> 权威定义见 [research-state-policy.md](research-state-policy.md) §5；本节与它**必须逐字一致**。
> 回写后跑 `python3 scripts/state_check.py --check .research-idea-pipeline/routes/<R>/research-state.json`，**硬违规须为 0**。
