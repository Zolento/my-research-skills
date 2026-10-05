# Mode D 重构规格：Narrative-first → Claim-first, evidence-constrained, narrative-last

> **本文件的地位：** 本轮开发的**唯一接口契约**。所有参与者的产物必须与本文件逐字一致
> （枚举值、字段名、章节号、公式）。发现冲突时**先改本文件并通知 Lead**，不得各自解释。
>
> **位置说明：** 本文件在**仓库根 `docs/`**，位于 skill 目录之外。
> `npx skills` 安装时**只拷贝 skill 子目录**，所以本文件**不会进入安装副本** —— 它是
> 仓库级开发文档，不是交付物。

**分支：** `research-idea-pipeline-dev`
**基 commit：** `d467b52`
**日期：** 2026-10-06

---

## 1. 目标与非目标

### 1.1 本轮要解决的问题

当前 Skill 的哲学是「**找到最有说服力的故事**」。它已经做到 scientific claim
engineering + reviewer-risk modeling，但**叙事层权力过大**：继续扩展会从「帮助发现最强
科学主张」滑向「帮助一个 idea 找最强包装」。

**新的哲学（必须逐字进入 SKILL.md §7 设计依据）：**

> **找到「在现有证据下最强但不过度」的科学主张，然后找到最短的故事使审稿人正确理解
> 该主张。**

**核心公式：**

```
Narrative quality = Claim strength × Evidence alignment × Reviewer comprehensibility
```

**明令取代的旧公式（禁止在任何文件中作为总纲出现）：**

```
Narrative quality = Novelty impression          ← 淘汰
```

### 1.2 顶层总纲的替换（全局，不是 Mode D 局部）

**旧总纲（降级为跨域场景专用）：**

> A 领域存在结构性缺口，B 恰好补上该缺口。

**新总纲（所有 Mode 的叙事层）：**

> 现有**理解 / 能力 / 评测**在条件 `Y` 下存在一个**可验证的缺口** `G`；
> 本文建立**新的知识** `K`，用于解释、界定或消除 `G`。
> **`B → K`（从来源领域引入）只是产生 `K` 的一种方式。**

判定：`N4`（现象）、`N8`（评测）、`N10`（负结果）**不需要也不得**硬塞一个 `B`。
凡要求「必须有 B」的规则一律作废，改为「必须能写出 `G` 与 `K`」。

### 1.3 非目标（本轮不做，见 §9 P1）

- 不改 Mode A/B/C/E 的**流程结构**（只做交叉引用与措辞同步）。
- 不把 Mode E 的八子代理换成攻击面审稿人。
- 不删除 `R-CVPR / R-ICML / R-NeurIPS / R-MICCAI`（B/C/E 仍在用）。
- 不动 `scripts/`（本轮无脚本改动）。
- 不改 `writing-policy.md` 三档机制。

### 1.4 分期

| 期 | 内容 | 本轮 |
|---|---|---|
| **P0** | 新建 claim-first 权威文件；重写 Mode D；两层评分；攻击面审稿人；venue 校准；venue-standards 2026 更新；SKILL.md 集成；templates/examples 同步 | ✅ 做 |
| **P1** | Mode E 迁移到攻击面 + 硬门禁；B/C 的 anchor eligibility 接入；会议枚举新增 ICLR 与顶刊 | ⏸ 登记待办 |

---

## 2. 冻结的枚举与字段名（逐字一致，不得改写）

### 2.1 证据台账的认知状态 `epistemic_status`

| 值 | 含义 | 可否进 Evidence Contract（S5） |
|---|---|---|
| `Observed` | 已观察到的实验 / 数据事实 | ✅ |
| `Supported` | 有文献或既有理论支持 | ✅ |
| `Hypothesized` | 假设，未验证 | ❌（标注 `[待验证]`） |
| `Planned` | 计划中、尚未产生的证据 | ❌（标注 `[待补]`） |
| `Unknown` | 未知 | ❌（标注 `[待补]`） |

与 [evidence-policy.md](../research-idea-pipeline/references/evidence-policy.md) 的衔接：
`Hypothesized` / `Unknown` → 措辞等级**「待核实」**；`Planned` → **不得当作证据引用**；
只有 `Observed` / `Supported` 可支撑确定性表述。

### 2.2 Claim Graph 的节点 ID

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

### 2.3 Central Proposition（承重墙，取代「机制」）

**规则（逐字进入 Mode D 与 SKILL.md §1.5）：**

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

**取代关系（关键）：** 旧规则「第二段必须给机制性原因，写不出来叙事不成立」**降级**为
方法类 / 跨域类的**子规则**；全局承重墙改为 central proposition。理由：研究实际是
`Observation → Hypothesis → Experiment → Mechanism`，在 proposal 阶段强迫写「根本原因」
会把**待验证假设包装成已知原因**。

### 2.4 三轴科学分类 `(O, T, R)`

**O — Contribution Object：**
`Problem` | `Phenomenon` | `Theory` | `Method` | `Evaluation` | `Resource-System`

**T — Scientific Tension：**
`hidden-assumption` | `contradiction` | `shift-failure` | `infeasibility` |
`identifiability` | `evaluation-mismatch` | `unexplained-phenomenon`

**R — Resolution：**
`characterize` | `explain` | `prove` | `reformulate` | `design-algorithm` |
`build-benchmark` | `build-system`

**写法：** `(O=Method, T=hidden-assumption, R=design-algorithm)`。
**枚举值一律用上面的英文原样**（机器可读契约，不得意译，见 writing-policy §8 第 6 条）。

**单值约束（2026-10-06 追加）：** `O` / `T` / `R` **各为单值**。若多个轴同时成立，
取**主导**的那一个写进枚举字段，其余在叙事正文里说明；**不得**写 `Method+Evaluation`
这类拼接值（与 `core_goal` 的单值纪律一致，见 SKILL.md §0.1 规则 1）。

### 2.5 Anchor Eligibility 结论

| 值 | 含义 |
|---|---|
| `eligible` | 证据台账直接支持该 anchor |
| `conditional` | 需补指定证据后才支持（必须写明补什么） |
| `not-eligible` | 现有证据不支持；**不得**据此 anchor 组织叙事 |

**anchor 枚举沿用 SKILL.md §0.1：** 理论 / 性能 / 现象 / 基准 / 可行性 / 负结果。

**硬规则：**

> **作者的目标 anchor 是 prior（先验偏好），不是决定（decision）。**
> 流程为 `Evidence → Claim → Claim strength → Eligible anchors → Narrative`。
> 当作者的目标 anchor 与 `eligible` 集合冲突时，**必须显式告知**
> 「你想定位成 X，但现有证据支持的是 Y；最强可辩护 anchor 是 Y」，
> **不得**帮作者强化不被证据支持的故事。

### 2.6 六槽位（取代五段式）

| Slot | 问题 |
|---|---|
| `S1 Context` | 哪个能力 / 科学问题重要？ |
| `S2 Tension` | 当前知识 / 方法 / 评测具体哪里不够？ |
| `S3 Central Proposition` | 本文最关键、可证伪的新命题是什么？ |
| `S4 Resolution` | 如何证明、解释或利用该命题？ |
| `S5 Evidence Contract` | 哪些证据分别支撑哪些 claim？（`Ci ← Ej` 对照） |
| `S6 Consequence & Boundary` | 这改变了什么？在哪些条件下不成立？ |

**规则：** 六槽位**全部必填**；`S5` 至少覆盖 `C0`—`C4`；`S6` 必须写出**不成立的条件**。
**四类论文的填法差异写在 narrative-patterns.md，不新增硬编码模板。**

### 2.7 硬门禁 `G1—G5`（不打分，直接判定）

| Gate | Fail 条件 |
|---|---|
| `G1 Claim grounding` | central claim 找不到对应证据 |
| `G2 Prior-work distinction` | 与最近工作没有明确的 delta |
| `G3 Identification` | 实验 / 证明不能识别所声称的机制 |
| `G4 Factual integrity` | 定理 / 实验 / 结果被叙事夸大 |
| `G5 Venue scope` | 贡献对象与 venue 明显不匹配 |

判定值：`pass` / `fail`。**任一 `fail` ⇒ `not_submission_ready`**（不得推荐为最佳）。

### 2.8 排序维度 `1—5`（六维，取代 11 维向量）

`Significance` | `Originality` | `Soundness margin` | `Explanatory depth` |
`Generality` | `Narrative compression`

**全部同向（高 = 好）**，因此 **Mode D 不再需要极性归一化**。
`1—5` 标尺沿用 scoring-policy §1 的五级锚点。

**读数归属（2026-10-06 追加）：** 每个维度的读数由谁给、哪些维度是双读数，**由
`roles.md` §1B / §6 与 `mode-d` §D8 定义**；本 spec 只冻结**维度枚举与同向性**，
不重复规定归属，避免三处各写一份。

### 2.9 攻击面审稿人（Mode D 主审）

| 角色 | 专门攻击 |
|---|---|
| `R-Novelty` | 最近工作是否已做过？delta 是否非平凡？ |
| `R-Causal` | 所谓机制是否只是相关性 / 事后解释？ |
| `R-Experimental` | baseline、公平性、confounder、统计功效 |
| `R-Theory` | assumptions、proof、tightness、definition |
| `R-Generalization` | claim scope 是否超出证据 |
| `R-Utility` | 即使正确，谁会在意？改变了什么？ |

**证据核验员（不打分，只出事实 / 类别结论）：** `S-Lit`（**恒派**，L3 穷尽 + 负检索记录）、
`S-Nov`（按需）、`S-Repro`（按需）。
**对抗角色（不打分）：** `S-Devil` —— 出「致命弱点清单」+「最简解释反例」，
喂 `G3`/`G4` 与 `R-Causal`，**不产生 1—5 分，不进任何向量**。

> **为什么删掉 S-Devil 的反向分：** `新颖性稳健度 = 6 − 反驳分` 没有概率解释；
> 且六个 reviewer 不是独立样本（同一基础模型换 prompt，`corr ≫ 0`），
> 11 维中位数是**伪精确**。novelty 改由 `R-Novelty`（同向维度）+ `G2` 门禁承担。

### 2.10 迁移合法性等级（跨域，取代「必须有迁移合法性定理」）

| Level | 举证方式 | 适用 |
|---|---|---|
| `L1` | structural hypothesis + falsification experiments | CVPR / MICCAI 实证型 |
| `L2` | formal invariance / sufficient conditions / proposition | method-heavy ICML / NeurIPS |
| `L3` | theorem + proof + necessity / tightness analysis | theory-anchor ICML / NeurIPS / JMLR |

**硬约束（取代旧规则）：**

> **必须明确回答「为什么 B 在 A 中合法」，且证据强度必须与论文声称的贡献等级匹配。**
> **不再要求任何论文都必须有 theorem。**

### 2.11 落盘文件名（沿用现规范，不改）

`<routeX>/docs/<R>NNN-narrative.md`（一次调用一份）；审阅挂被审 ID：`<ID>-review-r01.md`。

---

## 3. 文件地图与写作用域（互不重叠）

| 文件 | 动作 | 所有者 | 依赖 |
|---|---|---|---|
| `docs/mode-d-claim-first-spec.md` | NEW（本文件） | **Lead** | — |
| `research-idea-pipeline/references/claim-first-policy.md` | **NEW** | `claim-core` | 本文件 §2.1—2.5 |
| `research-idea-pipeline/references/narrative-patterns.md` | REWRITE | `narrative-rewrite` | `claim-first-policy` 的枚举 |
| `research-idea-pipeline/references/mode-d-narrative-generation.md` | REWRITE | `narrative-rewrite` | 同上 |
| `research-idea-pipeline/references/scoring-policy.md` | REWRITE | `review-scoring` | 本文件 §2.7—2.9 |
| `research-idea-pipeline/references/roles.md` | UPDATE | `review-scoring` | 同上 |
| `research-idea-pipeline/references/evidence-policy.md` | UPDATE | `review-scoring` | 本文件 §2.1 |
| `research-idea-pipeline/references/venue-standards.md` | UPDATE | `venue-standards` | 本文件 §2.7—2.10 |
| `research-idea-pipeline/SKILL.md` | UPDATE | **Lead** | 全部 |
| `research-idea-pipeline/templates/*`、`examples/*` | UPDATE | `examples-templates`（P0 后段） | 全部 |
| `research-idea-pipeline/README.md` | UPDATE（同步速查 / 树 / Mode D 段） | **Lead** | 全部 |
| `research-idea-pipeline/references/writing-policy.md` | UPDATE（§6 分工表 1 行） | **Lead** | scoring-policy |
| `research-idea-pipeline/references/mode-b/c/e*.md`、`project-layout.md` | UPDATE（交叉引用） | **Lead**（核心落地后） | 全部 |

**纪律：**

1. **只改自己作用域内的文件。** 需要别人改，发消息给 Lead，不要代改。
2. **不得 commit。** 提交由 Lead 统一做。
3. 冲突裁决顺序：`本 spec` > `claim-first-policy.md`（claim 类）> `scoring-policy.md`
   （评分类）> `venue-standards.md`（会议类）> 各 Mode 文件。
4. 发现 spec 有错：**改动 spec 必须经 Lead**；在任务里写 `BLOCKED: <原因>`。

---

## 4. 权威流程：D0—D9

**替换 `mode-d-narrative-generation.md` 现有的 D0—D8。** 每步必须写清输入、动作、产物。

| 步 | 名称 | 输入 | 产物 | 硬约束 |
|---|---|---|---|---|
| **D0** | Evidence Ledger | idea + 方案 + 已有实验 / 定理 / 文献 | 证据台账：每条 `E_i` + `epistemic_status` | 不得把 `Planned` 写成 `Observed`；无证据的条目留 `[待补]` |
| **D1** | Claim Graph | 证据台账 | `C0`—`C5` + `Ci ← Ej` 对照 | `C0` 必须一句话；每个 `C_i` 无证据则标 `[待补]` |
| **D2** | Scientific Typing | claim graph | `(O, T, R)` + 贡献类型 | 枚举逐字取自 §2.4 |
| **D3** | Anchor Eligibility | claim graph + typing | 每个 anchor 的 `eligible/conditional/not-eligible` | 与作者目标 anchor 冲突时**必须显式告知**（§2.5） |
| **D4** | Narrative Realization | eligible anchors + claim graph | **2—4 套真正不同的 claim hierarchy** + 每套六槽位 | 必须是**不同的 claim 层级**，**不得**是同一 claim 的四种措辞 |
| **D5** | Adversarial Review | 每套叙事 | 6 攻击面审稿人独立意见 + S-Devil 弱点 + S-Lit 核验 | 六人全部派遣；S-Lit 恒派 |
| **D6** | Venue Calibration | 评审结果 | 会议适配判定（CVPR/ICML/NeurIPS/MICCAI） | 按 contribution type 校准，不按 venue 选 preset |
| **D7** | Hard Gates | 每套叙事 | `G1—G5` 逐项 `pass/fail` | 任一 fail ⇒ `not_submission_ready` |
| **D8** | Ranking | 通过门禁的叙事 | 六维 1—5 + 逐维理由 | 门禁失败的**不参与排序** |
| **D9** | Output | 全部 | 最佳叙事 + runner-up + 胜出理由 + 致命风险 + **缺失证据清单** + **最小必要实验 / 定理** | 必须给出「还差什么证据」 |

**守则：**

- **D4 的候选数从「≥4 套」改为「2—4 套真正不同的 claim hierarchy」。**
  这直接消解「P3-10 × P3-11 每 idea 最低 24 份评审」的成本问题。
- **跨域类不再强制写满四套**，改为**必须做一次 anti-application stress test**：
  至少测试 `N2 / N3 / N5 / N9` 四个 preset，目的是**证明「把 B 用到 A」不是最准确的
  描述**，而不是四套都必须成稿。
- `orthogonal` 路线仍不得进 Mode D（SKILL.md §0.1 规则 3 不变）。

---

## 5. 与既有机制的接口

| 机制 | 接口要求 |
|---|---|
| `writing-policy.md` 三档 | **不改**。规范文本（`SKILL.md`、`references/*.md`）不跑 linter；`examples/`、`templates/` 跑默认档 `--disable synonym-rotation`，硬违规须为 0 |
| `evidence-policy.md` 五级 | 新增 §3「认知状态 ↔ 措辞等级映射」，**只做映射，不新立等级** |
| `project-layout.md` | 落盘路径与命名**不变**；仅当文件结构变化时同步 §2.4 叙事文档结构 |
| `state.template.json` | Mode D 段新增：`evidence_ledger` / `claim_graph` / `typing` / `anchor_eligibility` / `presets` / `slots` / `gates` / `ranking`；**`scores` 里按 venue 的键删除** |
| `scoring-policy.md` §2 极性归一化 | **保留**，但适用范围限定为「仍使用反向维度的 Mode（当前为 Mode E）」；Mode D 明确声明**无反向维度** |
| `roles.md` §7 字数表 | Mode D 的行按**攻击面审稿人**重写 |

---

## 6. 各文件验收标准

### 6.1 `claim-first-policy.md`（新）
- [ ] §1 总纲公式与「`B → K` 只是一种方式」逐字落地
- [ ] §2 证据台账：`epistemic_status` 五值 + 与 evidence-policy 的映射表
- [ ] §3 Claim Graph：`C0—C5` + `Ci ← Ej` 语法 + `[待补]` 规则
- [ ] §4 Central Proposition：七类论文的形态表 + 承重墙规则 + 对旧「机制」规则的降级说明
- [ ] §5 `(O, T, R)` 三轴 + 逐字枚举
- [ ] §6 Anchor Eligibility Test + 「prior 不是 decision」硬规则
- [ ] 每节标注它被哪些 Mode 引用；文末给「引用本文件的位置」清单

### 6.2 `narrative-patterns.md`（重写）
- [ ] 开篇明确：**N1—N10 = narrative presets / rhetorical realizations，不是科学分类，不互斥，不是创新等级**
- [ ] 十套表保留；**「适合会议」列必须补 `MICCAI`**（当前 10 行全无 MICCAI，属 §8 A2/B3 类漂移）
- [ ] 新增「preset ← (O,T,R) 与 anchor」的选择表，**取代**旧的「贡献类型 → 套路」单轴表
- [ ] 明写：一个 idea 可同时满足多个 N；主叙事取决于 claim hierarchy 强弱
- [ ] 六槽位 S1—S6 + 四类论文（理论 / benchmark / 跨域 / 负结果）的填法示例
- [ ] 跨域：五步升级保留，第 3 步改名 **Transfer Legitimacy Argument**，接 `L1/L2/L3`
- [ ] 禁用表述 §、包装纪律 § 保留并指向 claim-first-policy
- [ ] 自检清单更新（含「central proposition 可证伪」「`Ci ← Ej` 无缺口」）

### 6.3 `mode-d-narrative-generation.md`（重写）
- [ ] D0—D9 与 §4 表逐字一致
- [ ] 定位段改写：**claim-first, evidence-constrained, narrative-last**；保留「基于预期贡献的叙事预演，非基于实测结果的包装」
- [ ] 删除 11 维向量、极性归一化在 D 的使用、`新颖性稳健度` 公式
- [ ] 六攻击面审稿人 + S-Devil/S-Lit/S-Nov/S-Repro 的分工与「打分 / 不打分」边界
- [ ] D9 输出必须含「缺失证据清单」与「最小必要实验 / 定理」
- [ ] `state.json` 片段示例与新字段一致
- [ ] 交叉引用全部可解析（`§` 与相对路径）

### 6.4 `scoring-policy.md`（重写）
- [ ] 两层结构：**第一层硬门禁 `G1—G5`（不聚合、不平均）**；**第二层六维排序**
- [ ] §2 极性归一化保留但限定适用范围（当前 Mode E）
- [ ] 明写「六个 reviewer 不是独立样本，`corr ≫ 0`，故不得以『6 个都同意』声称
      reviewer consensus」
- [ ] 旧 §4/§5（中位数、一票否决）标注为「Mode E 仍适用；Mode D 改用门禁 + 六维」
- [ ] 冲突时以本文件为准的声明保留

### 6.5 `roles.md`（更新）
- [ ] 新增攻击面审稿人六个角色段（保留 `R-CVPR` 等四个会议审稿人给 B/C/E 用）
- [ ] §6「Mode D 叙事审核专用量表」重写为攻击面量表
- [ ] §7 字数表 Mode D 行同步
- [ ] 统一骨架 §5 适配「不打分角色」（S-Devil 输出弱点清单而非分数）

### 6.6 `evidence-policy.md`（更新）
- [ ] 新增 §3 认知状态 ↔ 措辞等级映射
- [ ] **修复现存缺陷：§2 有两条编号 `7.`**（第 31 行与第 38 行重复），后者应为 `8.`

### 6.7 `venue-standards.md`（更新）
- [ ] 2026 官方标准**逐条核实并附 URL**：ICML（soundness / presentation / significance /
      originality 拆分）、NeurIPS（按 contribution type 校准）、ICLR（问题 / 动机 /
      claim 支撑 / 新知识；SOTA 非必要条件）、CVPR、MICCAI（methodological **或**
      application innovation；高 clinical impact 可补偿方法创新）
- [ ] 新增顶刊一节：TMI（Significance—Innovation—Evaluation—Reproducibility）、
      JMLR（"学到了什么"）、Nature MI（是否改变领域思考方式）
- [ ] 明写 `clinical significance ≠ methodological innovation`，两者不得互相冒充
- [ ] 改写为 `contribution type → evidence contract → venue calibration` 的顺序，
      **不得**保留「venue 直接选 preset」
- [ ] 未能核实的条目必须标「待核实」，**不得**凭记忆写 2026 的规则

### 6.8 `SKILL.md`（Lead）
- [ ] §0.1 「锚点如何约束各 Mode」的 D 行改指 anchor eligibility
- [ ] §1.2 的「四会议审稿人两角度 + 会议特性」**限定作用域**（B/C/E + D6 校准），否则与 D5 冲突
- [ ] §1.5 承重墙改为 central proposition，机制降级为子规则
- [ ] §2 资源索引加入 `claim-first-policy.md`
- [ ] §3 派遣矩阵 Mode D 行改为六攻击面审稿人 + S-Lit 恒派
- [ ] §4 Mode D 速查重写；§5 衔接图不变
- [ ] §6 自检清单 Mode D 项重写（含门禁、六槽位、缺失证据清单）
- [ ] §7 设计依据新增「为什么 claim-first」「为什么删 11 维」「为什么 reviewer 按攻击面」
- [ ] §8 A/B 表登记本轮漂移类别（若出现新类别）

### 6.9 `templates/` 与 `examples/`
- [ ] `state.template.json` Mode D 段按 §5 更新，且 JSON 合法
- [ ] `examples/example-d-narrative.md` 重写为新流程示例（含 claim graph、六槽位、门禁表）
- [ ] `templates/` 与 `examples/` 全部通过默认档 linter（硬违规 0）

---

## 7. 机械校验（Lead 在合并前跑）

```bash
cd research-idea-pipeline

# 1) 相对链接可达 + §引用可解析（沿用仓库既有做法）
# 2) 废弃词扫描（必须 0 命中）
PAT=$(grep -vhE '^\s*(#|$)' references/deprecated-terms.txt | paste -sd'|')
grep -rnE "$PAT" --include=*.md .          # 期望 exit 1

# 3) 落盘路径必须带 routeX/ 前缀
grep -rnE '`docs/<' --include=*.md . | grep -vE 'templates/INDEX\.md|grep -rnE'

# 4) JSON 合法
python3 -c "import json;json.load(open('templates/state.template.json'))"
python3 -c "import json;json.load(open('docs/refs/index.json'))"
python3 scripts/refs_index.py --check

# 5) 离线测试
python3 -m unittest discover -s scripts -p "test_*.py"

# 6) 受控中文（examples + templates，默认档）
python3 scripts/ste_lint_zh.py --selftest
for f in examples/*.md templates/*.md; do
  python3 scripts/ste_lint_zh.py --disable synonym-rotation "$f" || exit 1
done

# 7) 旧机制残留（Mode D 语境必须 0；Mode E 与 §7 设计依据属合法保留）
grep -rn '新颖性稳健度\|11 维\|11 个维度\|五段式' --include=*.md references/ SKILL.md \
  | grep -vE 'scoring-policy\.md|mode-e-proposal-review\.md'
#    ↑ 排除两类**合法保留**：① scoring-policy（§2/§5 明写「Mode E 仍适用」）
#      ② mode-e（Mode E 的现行规则）
#    然后**人工确认** SKILL.md 的命中只出现在 §7 设计依据 / §8 维护清单（历史说明，
#    本来就在论证「为什么改」）。**判据：命中必须处于 Mode E 或历史说明的上下文；
#    出现在 Mode D 的现行规则里 = 违规。**
#
# 8) 链接检查的**已知假阳性**（不要当回归修）
#    - `references/project-layout.md` §4.1 与 `examples/example-project-layout.md` 里的
#      `docs/A00x-*.md`：那是 routeA/INDEX.md 的**样例内容**，相对路径以**路线目录**为基准，
#      相对 skill 目录当然不存在。样例/模板路径按仓库既有约定不参与断链检查。

# 8) 标题增删检查（防整节吞掉，见 SKILL §8 D5）
git diff -U0 -- SKILL.md | grep -E '^[-+]## '
```

---

## 8. 已知缺陷登记（本轮顺带修）

| # | 缺陷 | 处理 |
|---|---|---|
| 1 | [`narrative-patterns.md`](../research-idea-pipeline/references/narrative-patterns.md) 十套表「适合会议」列**无 MICCAI** | 重写时补 |
| 2 | [`evidence-policy.md`](../research-idea-pipeline/references/evidence-policy.md) §2 编号 `7.` 重复 | 修 |
| 3 | [SKILL.md](../research-idea-pipeline/SKILL.md) §1.2「四会议审稿人必须三角度」与 D 的新攻击面审稿人冲突 | 限定作用域 |
| 4 | 「A 有缺口、B 补上」被当成全局总纲，导致 N4/N8/N10 硬塞 B | §1.2 替换 |

---

## 9. P1 待办（本轮登记，不做）

1. Mode E 迁移：`G1—G5` 门禁 + 六维排序 + 攻击面审稿人；届时 `scoring-policy.md` §2
   的极性归一化可整体退役。
2. Mode B / C 接入 `claim-first-policy.md` 的 evidence ledger 与 anchor eligibility。
3. 会议枚举新增 `ICLR` 与顶刊（TMI / JMLR / Nature MI）——涉及 SKILL §0/§3/§4、
   venue-standards、roles §1（约 13 处），单独一轮。
4. ~~`project-layout.md` §2.4 叙事文档内部结构按六槽位更新~~ —— **本轮已提前完成**
   （2026-10-06；§5 接口行优先，本条作废）。

---

## 10. 变更记录

| 日期 | 变更 | 人 |
|---|---|---|
| 2026-10-06 | 初版 | Lead |
| 2026-10-06 | §2.4 追加「单值约束」（`O`/`T`/`R` 各单值） | Lead |
| 2026-10-06 | §2.8 追加「读数归属」条（归属由 roles §1B/§6 与 mode-d §D8 定义） | Lead |
| 2026-10-06 | §3 文件地图补登记 `README.md` 与 `writing-policy.md`（所有者 Lead） | Lead |
| 2026-10-06 | §7 校验 7 扩排除名单（`scoring-policy` / `mode-e`），并登记链接检查的已知假阳性 | Lead |
| 2026-10-06 | §9 P1-4 标注「本轮已提前完成」（project-layout §2.4 已同步） | Lead |
| 2026-10-06 | 依 `docs/verify-mode-d-claim-first.md` 修 MAJOR 2 + MINOR 10 + NIT 7 | Lead |
