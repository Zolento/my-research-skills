# R3—R6 — 双轨发现与种群进化（dual-discovery → isolated populations → evolution）

基础文献调研 + 多子代理头脑风暴，产出 idea 候选，**并对每个候选做 idea 级的创新性
与可行性审核**，最后给出经过筛选的推荐清单。

> **R3—R6 的定位是"概念级"。** 它回答 **"这个方向/概念值不值得做"**：
> 文献上是否已被覆盖、概念上是否非平凡、方法路线上是否成立。
> 它**不**回答"这个方案做得对不对"——那是 R7 / R10 / R13 的职责（见 §B0）。


> ⚠️ **内部小节号 `§B0—§B8` 保留自旧命名**（本文档由旧 `mode-b` 迁移而来），语义已按本文件的「读 / 写」表重新映射；**全量重编号在 Wave 3 做**。
> **迁移不得丢节** —— 本注被删掉时，`§B0—§B8` 会失去唯一解释，读者会误当退役字母残留。


> ⚠️ **作用域裁决（Wave 2）：** 本文件同时含两代内容 ——
> **`B0`—`B8`** 是旧的 idea-discovery 流程，**`R3`—`R6`** 是 Wave 2 起生效的发现层正式规则。
> **冲突时一律以 `R3`—`R6` 为准**；`B2`（局限分析）、`B4`（发散策略）、`B5`（审核）
> 作为 **R3 的输入约束**保留，不再单独驱动「一轮 brainstorm → population（QD archive 的候选池）」那条路径。
> **被取代的节（点名）：** `B5.4`（按创新性/可行性/重叠度排名）、`B6`（推荐 shortlist 3—5 个）、
> `B8`（挑选 1—3 个进入 R8 + `state.json` 片段）—— 三者的**筛选动作已由 `R4.2`（QD archive）
> 与 `R6.3`（两阶段 fitness）取代**；`B8` 的 state 片段口径已作废，改用
> [research-state.template.json](../templates/research-state.template.json)。

## B0. 与 R7 / R10 / R13 的分工（必须先明确，避免重复劳动）

| 维度 | R3—R6（idea 级） | R7 / R10 / R13（方案级） |
|---|---|---|
| **对象** | 一句话级 idea / 技术方向 | 成型的 proposal + 实验计划 |
| **核心问题** | 这个概念值得做吗？ | 这个方案做得对吗、能不能做成？ |
| **创新性** | 方向是否已被覆盖、是否非平凡 | 方案是否**实质复现**已有工作（防复现） |
| **可行性** | 概念可行性：路线是否成立、资源是否现实 | 工程可行性：具体做法能否跑通、变量是否可控 |
| **正确性** | 前提是否自洽、有无明显逻辑缺口 | 方法正确性：推导/实现/指标/统计是否成立 |
| **理论** | 是否需要理论支撑、前提是否合理 | 证明是否成立、假设是否必要 |
| **复现性** | **不涉及**（无代码，不派 S-Repro） | **必查**（S-Repro） |
| **审查深度** | 快筛：双评分 + 致命反驳 | 深审：八子代理 + 交叉质询 + 中位数 |
| **产出** | 排序后的 population（QD archive 的候选池） + 淘汰理由 | 审查结论卡片 + 修改建议 |

**一句话记法：B 管"值得做吗"，E 管"做对了吗"。**

---

## 输入

| 输入 | 必填 | 说明 |
|---|---|---|
| 研究领域关键词 | ✅ | 1—3 个核心方向词 |
| 已有参考文献 | ❌ | 用户提供的种子文献 |
| 资源约束 | ❌ | 算力 / 数据 / 时间 / 是否要求开源可控 |

**若关键词缺失或过泛**（如"深度学习"），先反问收敛，不要直接开跑。

> **锚定点（核心目标）必须先确认**（见 [../SKILL.md](../SKILL.md) §0.1）。
> 本 Mode 受锚点约束：**理论**锚点优先"假设挑战"类推导，**性能**锚点优先"问题重构 /
> 组合创新"；**population（QD archive 的候选池） 只收服务主锚点的 idea**，与锚点无关的候选即使新颖也降级。
> 锚点与候选明显不匹配时，**在同一份输出里显式指出冲突**。
>
> **派遣方式：** 环境有 Team 能力时**必须先询问用户**是否使用 Team；用户显式要求但
> 环境不具备时须**显式回退**并告知（见 [../SKILL.md](../SKILL.md) §3.1）。

---

## B1. 基础文献调研（必须走 R2 / R5 或等价的脚本调用）

- **检索必须走 R2 / R5**（或等价的
  [literature_search.py](../scripts/literature_search.py) 调用），
  按 [literature-policy.md](literature-policy.md) 规范检索**本地 + 多源**
  （先本地、再 arxiv；**本地命中不是终点，仍须扩检**，429 指数退避）。
- **禁止内联自行实现一套检索。** 各 Mode 自行实现检索会**绕开 R2 / R5 的全部纪律**
  （T1—T7 触发、L3 饱和判据、每源状态、负检索记录）。走 R2 / R5 / 等价脚本时，必须
  保留其**检索式、每源状态与负检索记录**。
- **注意：本次调研支撑后续的创新性审核，属于 T4/T5 触发场景**（**B5 是概念级快筛，
  按 T4 的例外执行 L2**，见 [literature-policy.md](literature-policy.md) §2 的 T4 行），
  因此本地命中后仍必须执行**在线源**检索；检索等级门槛见 §B5.2。
- 建议检索量：`max_results ≥ 20`；不足时按 R2 / R5 的 A3 策略扩大范围。
- **产出：**
  1. **技术路线归纳表** —— 把文献聚类为 3—6 条技术路线。
  2. **创新性边界** —— 分为三区：
     - 🔴 **红海**：竞争激烈、增量空间小
     - 🟡 **蓝海苗头**：有初步信号但未成熟
     - ⚪ **无人区**：检索未见覆盖（**必须标注检索式，且默认标"待核实"**）

**技术路线归纳表模板：**

| 路线 ID | 路线名 | 代表工作 | 核心机制 | 关键假设 | 理论工具 | 覆盖密度 |
|---|---|---|---|---|---|---|
| L1 | … | [作者, 会议/年份] | … | … | … | 红海/蓝海/无人区 |

---

## B2. 深度局限性分析

逐路线分析三件事：

| 路线 | 做到了什么 | 没做到什么 | 普遍局限性 |
|---|---|---|---|
| L1 | … | … | … |

**强制约束（硬性）：**

- **禁止模糊表述。** 不许写"效果不够好""泛化性差""缺乏理论"这类空话。
- 每条"没做到"**必须关联具体未建立的结构性质或未满足的理论条件**，例如：
  - ✅ "未建立**置换等变性**，因此组合结构的顺序变化会导致解不稳定"
  - ✅ "收敛性证明依赖**强凸性假设**，而目标函数在实际离散空间中非凸"
  - ❌ "缺乏理论分析"

---

## B3. 多子代理头脑风暴

派遣以下子代理，**各自独立产出 idea 候选**（同一轮内并发派遣，互不可见对方的
结论，以保证发散度）。角色定义见 [roles.md](roles.md)。

| 子代理 | 头脑风暴视角 |
|---|---|
| R-CVPR | 从**方法落地与经验验证**角度提 idea |
| R-ICML | 从**理论原创性与假设移除**角度提 idea |
| R-NeurIPS | 从**贡献类型与洞察深度**角度提 idea |
| R-MICCAI | 从**临床转化与验证可行性**角度提 idea（无医学背景时按通用"验证严谨性"视角提） |
| A-Author | 从**投稿人论证**角度提 idea |
| A-Experimenter | 从**可验证性**角度提 idea |
| S-Devil | 从**"现有工作最致命的未解问题"**反向提 idea |

**要求：**

- 每个子代理**至少提 3 个 idea**（7 个视角，合计 ≥ 21 个原始候选）。
- 每个 idea 附：推导策略、核心思路、与现有工作的差异、贡献类型，
  以及**方法来源**（`原创` / `部分原创` / `迁移` —— 见
  [venue-standards.md](venue-standards.md) §5.1；**迁移本身不算增量**）。
- 汇总后**去重**（按"核心思路 + 差异"判定同质），保留来源子代理标注。
- 去重后候选 **≥ 6 个**（原始候选 ≥ 10 个）；不足则让覆盖不足的视角补提；
  **领域确实过窄时，可说明原因并减少**（须在输出与 INDEX Warnings 中写明理由）。

---

## B4. 发散策略约束

**每个 idea 必须通过以下至少一种策略推导，并在输出中标明是哪种：**

| 策略 | 含义 | 自检问句 |
|---|---|---|
| 问题重构 | 重新定义要解决的问题 | 我们是否在解一个错的问题？ |
| 假设挑战 | 质疑现有工作的前提假设 | 哪条假设其实不必成立？ |
| 跨域迁移 | 借其他领域的方法/视角 | 领域 X 怎么解这个结构？ |
| 反向思考 | 从失败/反面出发 | 如果目标反过来会怎样？ |
| 组合创新 | 创造性组合已有想法 | 把 A 的机制接到 B 的问题上会怎样？ |

> **反模式：** 仅写"把 X 用到 Y 上"而不说明**为什么这个组合会产生非平凡的新性质**，
> 不计入组合创新。

---

## B5. Idea 创新性与可行性审核（强制，不可跳过）

> ⚠️ **本节已被 R4.2 / R6.3 取代**（仅在 R3 的 concept 级快筛里作为检查项保留）：
> **不得**据此把候选筛到 3—5 个 —— 筛选动作走 QD archive（每个 niche 留一个 elite）。


**这是 R3—R6 与 R7 / R10 / R13 的分界点：B5 是概念级快筛，不是方案级深审。**

对去重后的**每一个**候选 idea 执行审核。**禁止只给 idea 不给审核。**

### B5.1 派遣

| 子代理 | 在 B5 的职责 |
|---|---|
| R-CVPR | **创新性**：从方法落地角度看是否非平凡（警惕"新颖性谬误"） |
| R-ICML | **创新性**：是否属于"创造性组合 / 应用新领域 / 移除限制性假设" |
| R-NeurIPS | **创新性**：贡献类型判定 + 洞察深度（Concept & Feasibility 门槛更高） |
| R-MICCAI | **创新性**：临床相关性是否成立 + 验证方案是否可行（无临床属性时按通用视角评） |
| **S-Lit** | **最接近先前工作 + 重叠度判定**（足够 / 边缘 / 不足） |
| **S-Nov** | **独立新颖性核验**（S-Lit 判"边缘"，或 idea 要打"首次"时**必派**） |
| **S-Feas** | **概念可行性**：路线是否成立、资源是否现实、是否存在已知不可行结论 |
| **S-Theory** | **前提自洽性**（仅当 idea 含理论声称时派遣） |
| **S-Devil** | **一条最致命反驳**（"若只能写一条否掉它的理由"） |

> **四个会议审稿人必须按「两角度 + 会议特性」评审**（见
> [roles.md](roles.md) §1.0 与 [venue-standards.md](venue-standards.md) §0）：
> 先给**理论角度**与**应用角度**各自的实质判断，再给一条**本会议特性判定**
> （引用该会议标准条目）。只写一个角度 = 评审不合格。B5 是快筛，但不等于可以只写一句话。
>
> **不派遣 S-Repro。** idea 阶段没有代码可复现；可复现性审查只在 R7 / R10 / R13 进行。

### B5.2 检索门禁

- **进入 population（QD archive 的候选池） 的门槛 = 完成 L2**（强化级，见
  [literature-policy.md](literature-policy.md) §3.1）。B5 是**概念级快筛**，
  L2 的检索广度已足以支撑 population（QD archive 的候选池） 决策。
- **只有要写进文档的「首次提出」类声称才要求 L3**（穷尽级），且必须附
  **负检索记录**；「首次提出」的三项门禁见
  [evidence-policy.md](evidence-policy.md)（措辞等级统一在该文件，本节不另立）。
- **不可控例外：** 在线源因 429/不可用而无法达到对应等级（不可控因素）时，该 idea
  仍可进入 population（QD archive 的候选池），但必须：① 标注"据本次检索未见 · 待核实"；② **不得**使用
  "首次提出"；③ 记入 `INDEX.md` 的 **Warnings**，并在源恢复后补做。
- 无论哪种情况，未完成对应等级时都**不得**把新颖性判定标为"已核实"。

### B5.3 每个 idea 的审核输出

```markdown
#### I3 审核

- **推导策略：** 假设挑战
- **创新性评分：** 4/5（R-CVPR / R-ICML / R-NeurIPS / R-MICCAI 合并判定）
- **理论角度：** ……（四位审稿人的理论侧判断摘要）
- **应用角度：** ……（四位审稿人的应用侧判断摘要）
- **会议特性判定：** R-CVPR ……；R-ICML ……；R-NeurIPS ……；R-MICCAI ……（各引一条标准条目）
- **可行性评分：** 3/5（S-Feas）
- **理论前提：** 自洽 / 有缺口 / 不适用（S-Theory）
- **最接近先前工作：** [作者, 会议/年份]（S-Lit）
- **重叠度：** 足够 / 边缘 / 不足
- **检索等级：** L2 已达成 / 未达成（population（QD archive 的候选池） 门槛）；若含「首次提出」声称则须
  另标 L3 已达成 / 未达成；未达成对应等级时标"据本次检索未见 · 待核实"
- **致命反驳（S-Devil）：** ……
- **反驳是否可缓解：** 是（缓解路径：……）/ 否
- **推荐优先级：** 高 / 中 / 低 / 建议放弃
```

### B5.4 优先级判定规则

> ⚠️ **本节已被 R4.2 取代**：这张排名表**不得**用来筛到 3—5 个候选；
> 筛选动作走 **QD archive**（每个 niche 留一个 elite）。它只作为 **R3 的 concept 级快筛**输入。


| 优先级 | 条件 |
|---|---|
| **高** | 创新性 ≥4 且 可行性 ≥3 且 重叠度 = 足够 |
| **中** | 创新性 =3 或 可行性 =3，或 重叠度 = 边缘 |
| **低** | 创新性 ≤2 或 可行性 ≤2 |
| **建议放弃** | 重叠度 = 不足（实质已被覆盖），或 S-Devil 致命反驳**不可缓解** |

> 被淘汰的 idea **不删除**：保留其评分与淘汰理由，写入文档与 INDEX。

---

## B6. 输出

> ⚠️ **本节已被 R4.2 取代**：输出的是 **population + QD archive**，
> **不是**「shortlist（3—5 个）」。shortlist 这个概念在 Wave 2 起作废。


**idea 候选清单（核心交付物：原始候选 ≥ 10，去重后 ≥ 6，每个都带审核结论；领域过窄时可说明原因并减少）：**

| 编号 | 推导策略 | 核心思路 | 与现有工作差异 | 贡献类型 | 来源子代理 | 创新性 | 可行性 | 重叠度 | 优先级 |
|---|---|---|---|---|---|---|---|---|---|
| I1 | 假设挑战 | … | … | Concept & Feasibility | R-ICML | 4 | 3 | 足够 | 高 |
| I2 | … | … | … | … | … | … | … | … | … |

**推荐 population（QD archive 的候选池）（3—5 个）** —— 从"高/中"中挑选，每个附：
① 解决的具体局限（回指 B2 哪一条）；② 为什么现在能做；③ 最可能被攻击的一点。

**淘汰清单** —— 被放弃的 idea + 淘汰理由（重叠不足 / 可行性过低 / 致命反驳不可缓解）。

**其他交付物：**

- 技术路线归纳表（B1）
- 创新性边界界定：红海 / 蓝海苗头 / 无人区（B1）

**创新性边界界定模板：**

```markdown
### 创新性边界界定

**红海：** …（为什么拥挤：……）
**蓝海苗头：** …（初步信号：……）
**无人区：** …（检索式：……；**待核实** —— 需 S-Lit 复核）
```

---

## B7. 文档落盘与 INDEX 更新（强制）

1. **写文档：** `<routeX>/docs/<R>NNN-ideas.md`（ID 按
   [project-layout.md](project-layout.md) §2.6 扫描现有最大序号 +1）。
   内容 = B1 技术路线归纳表 + B2 局限性分析 + B6 idea 清单（**含 B5 审核评分**）
   + 推荐 population（QD archive 的候选池） + 淘汰清单 + 创新性边界界定。
2. **frontmatter：** `id / route / phase: R3—R6 / type: idea-discovery / status / created`。
3. **更新该路线 `INDEX.md`：**
   - §2 文档索引：新增本文件行；
   - §3 已证实：被 S-Lit 证实"重叠足够"的 idea 方向；
   - §4 已证伪：被判"重叠不足"或致命反驳不可缓解而**放弃**的 idea；
   - §5 TODO：进入 population（QD archive 的候选池） 的 idea → 转成"进入 R8"的任务；"待核实"的无人区
     条目 → 检索任务；
   - §7 Warnings：**未完成 L2 的"无人区"声称、未完成 L3 的"首次"声称必须记为 Warning**；
   - §9 变更日志。

## B8. 输出后

> ⚠️ **本节已被 R11 取代**：写回的**必须是 Research World Model**（八类一等对象 + `island` / `generation`）；
> 旧的 `state.json` 片段（`idea_candidates` / `population（QD archive 的候选池）` / `rejected`）**已删除**，照抄会被 `state_check.py` 判 exit 4。


1. **写回 Research World Model**（不是附 state.json 片段），`next_phase_suggestion: "R8"`。
2. 进入 R8 的是 **QD archive 的 elite 集合**（每个 niche 一个），**不是**「从 population（QD archive 的候选池） 挑 1—3 个」；
   并把 B2 的局限分析与 B5 的快筛结论一并传入。

**state 片段示例：**

```json
{
  "phase": "R3—R6",
  "claims": [{"id": "C1", "statement": "…", "falsifier": "…", "status": "ungrounded",
              "supporting_evidence": [], "refuting_evidence": [], "known_flaws": ["F1"]}],
  "hypotheses": [{"id": "H1", "statement": "…", "niche": "N2", "island": "P2", "generation": 0,
                  "status": "elite", "falsifier": "…",
                  "structural_signature": {"assumption_distance": 2, "formulation_distance": 3,
                                           "representation_distance": 1, "theory_lens_distance": 3,
                                           "mechanism_distance": 2}}],
  "experiments": [{"id": "X1", "parent": null, "stage": "X1", "claim_targeted": ["C1"],
                   "status": "planned", "known_flaws": ["F1"]}],
  "failures": [{"id": "F1", "kind": "deprioritized", "what": "…", "why": "…",
                "referenced_by": ["C1", "X1"]}],
  "literature": [{"id": "LIT1", "ref": "[作者, 会议/年份]", "relation": "shares-assumption"}],
  "uncertainties": [{"id": "U1", "question": "…", "importance": "high", "uncertainty": "high",
                     "cheapest_discriminating_test": "X1", "status": "open"}]
}
```

> 完整骨架见 [research-state.template.json](../templates/research-state.template.json)；
> 写回后**必须**跑 `python3 scripts/state_check.py --check .research-idea-pipeline/<route>/research-state.json`，
> **硬违规须为 0**（exit 3 = 硬违规，exit 4 = 结构不符）。


---


## R3. 双轨发现（**上下文隔离是硬规则**）

> **谁生成候选（Wave 3 澄清）：** 候选由**执行者按 island 分轨生成**（`P1`—`P6`，各轨上下文隔离）。
> **子代理不负责生成候选**，只用于：concept 级快筛（`S-Lit` / `R-Novelty` / `R-Causal` / `S-Feas`）
> 与致命反驳（`S-Devil`）。因此 `B3` 里「派遣 7 个具名子代理各出 ≥3 idea」的**旧指示作废**。

```text
                 ┌── Local Search ─────── 已有 gap / 机制改进
problem ─────────┤                        （基线：把现状做到更好）
                 └── Paradigm Escape ──── P1 Reframe            改问题 ontology
                                          P2 Assumption         摧毁 tacit assumption
                                          P3 Remote Analogy     先做 domain erasure，再找结构同构
                                          P4 Theory Lens        换一套数学语言重述
                                          P5 Measurement        怀疑 metric / observable
                                          P6 Counterexample     从反例与不可能性生成方向
```

**硬规则：**

1. **两轨在产生候选之前不得互相看到内容。** 理由：`early communication → idea convergence` ——
   四轨若第一轮就共享答案，发散度会塌成一条。**隔离是机制，不是建议。**
2. **P3 必须先做 domain erasure**：删掉 `MRI / CT / flow / reconstruction` 这类领域词，
   只留数学骨架，再找 `high semantic distance + high structural similarity` 的对象。
   直接说「领域 A 和 B 都在做类似的事」**不算**结构同构。
3. **P4 每个 theory lens 必须产出 `explanation + prediction + algorithmic consequence`
   三者中至少两个**，否则是理论包装，退 `failures[]`（`kind: unsupported`）。
4. **P6 产出的方向必须写成可证伪命题**（否则它是抱怨，不是研究问题）。
5. 每轨的候选都写 `island`（`P1`—`P6` / `local`；**默认启用 `P1`—`P4`，`P5`/`P6` 按需**）与 `generation: 0`（V13/V14 强制）。

### R3.0 `claims[]` 的创建归属（总收官审计 M-1）

**每个候选必须产出至少一条 `C`** —— 它的 central proposition，`status: ungrounded`。
这是 claim graph 的**唯一起点**：

| 阶段 | 对 `claims[]` 做什么 |
|---|---|
| **R3** | **创建**（seed：`status: ungrounded`，`falsifier` 必填） |
| R7 | **读**（攻击它；输出 `assurance`，不改 `status`） |
| R8 | 建 `claims[].contract`、更新 `supporting_evidence` / `refuting_evidence` / `scope` |
| R10 | 唯一能改 `claims[].status` 的阶段 |
| R12 | **只读**（渲染成 `narrative_view`，**不创建、不修改**） |

**为什么必须写在这里：** 双循环里 R7（对抗保证）与 R8（证据契约）都排在 R12 之前，
若 claim 由 R12 创建，则 R7/R8 在读一个没人写的对象 —— `state_check.py` 的
V1 / V2 / V3 会**永不触发**，world model 变成没有 claim 的空壳。

### R3.1 生成预算（默认值，可缩放）

| 项 | 默认 |
|---|---|
| islands 数 | **默认 4**（`P1`—`P4`，各占独立预算）+ Local Search；`P5`（Measurement inversion）与 `P6`（Counterexample & impossibility）**按需启用**（枚举里合法，但不占默认预算；启用即上调，须说明理由） |
| 每 island 候选数 | **下限 3，上限 6**（超上限须显式说明为什么值得） |
| 进化轮数上限 | **2**（见 R6） |

**可缩放：** 领域过窄或资源受限时，可在 R0 `contract.constraints` 写明并降到 **2 islands × ≥2 候选**；
**上调上限需要用户同意**。

### R3.2 与 Local Search 的分工

Local Search 不是「对照组」——它负责**把现状做到更好**，其候选同样进 population 与 QD archive。
**但两阶段 fitness 对它在 Search 期一视同仁**（见 R6.3）：不许因为它"更可行"就优先。

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
| 某 niche 的 elite 被 R7 判 `已被覆盖` | elite 转 `archived`，按 R4.2 补新 elite，或关闭该 niche |
| 候选被 R6 判 `killed` | `status: killed` 并写 `failures[]`（`kind: deprioritized`） |

---

## R6. 进化与两阶段 fitness

### R6.1 进化算子（五种，按序优先使用前三种）

| 算子 | 做什么 |
|---|---|
| `mutation` | 改一个 structural signature 维度 |
| `cross-domain crossover` | **跨 island** 组合两个候选的表示与机制（P3 的产物最适合） |
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

---

## 读 / 写 World Model（强制）

| 阶段 | 读 | 写 |
|---|---|---|
| **R3** | `literature` / `assumptions` / `failures` / `contract.constraints` | `hypotheses` / `claims`（**seed**：每个候选至少一条 `C` = central proposition，`status: ungrounded`） |
| **R4** | `hypotheses` | `hypotheses[].niche` / `hypotheses[].island` / `hypotheses[].status` |
| **R6** | `hypotheses` / `uncertainties` / `failures` | `hypotheses[].generation` / `hypotheses[].status` / `failures` / `known_flaws`（把新 `F` 挂上） |

> 权威定义见 [research-state-policy.md](research-state-policy.md) §5；本节与它**必须逐字一致**。
> 回写后跑 `python3 scripts/state_check.py --check .research-idea-pipeline/<route>/research-state.json`，**硬违规须为 0**。
