# Wave 5 规格：跨阶段系统机制（P0-3 … P0-6）

> **定位：** Wave 1—3 建的是「科研流程」，Wave 4 冻结了「谁来生成、谁来攻击」。
> Wave 5 补的是**横跨 R0—R14 的系统机制**：调度、状态失效传播、验证可信度、结果预注册。
> **它不是第 16 个阶段，也不是第 9 类对象。**

## 0. 不扩张承诺（硬约束，逐条可核）

| # | 承诺 | 核验方式 |
|---|---|---|
| 0.1 | **不新增 R 阶段**（仍 `R0`—`R14`） | `grep -oE 'R1[5-9]' SKILL.md` 为空 |
| 0.2 | **不新增 reviewer persona**（仍八攻击面；`S-Integrity` 之后不再加） | `roles.md` §1B 条目数 = 8 |
| 0.3 | **不新增评分维度**（仍六维 / 归一化五维） | `scoring-policy.md` 维度表不变 |
| 0.4 | **不新增叙事 preset**（仍 `N1`—`N10`） | `NICHES` 常量不变 |
| 0.5 | **不新增第九类 scientific object**（仍 `C/E/AS/H/X/LIT/F/U`） | `OBJECT_KEYS` 长度 = 8 |
| 0.6 | 元控制器统计 / 算子收益属 **systemic telemetry**，落**独立文件**，不进 `research-state.json` | `scheduler.json` / `operator-stats.json` 与 state 分离 |

**推论（本 Wave 最重要的一条设计纪律）：**

> **新的机制如果要"进 state"，就必须是**已有八类对象上的字段**；
> 如果它描述的是"系统自己怎么工作"，就**必须出 state**、落 telemetry 文件。**
> 这条同时挡住了「加第 9 类对象」和「把系统统计混进科研状态」两种漂移。

---

## 1. P0-3：Dependency Invalidation（状态失效传播）

### 1.1 要解决的问题

```text
E3 --supports--> C2 --supports--> C4 --premise--> H7 --generates--> X12 --used in--> N2
```

后来发现 `E3` 有数据泄漏。当前架构只会把 `E3` 标一下，**下游的 `C2 / C4 / H7 / X12 / N2` 仍然显示为有效** ——
narrative 还能引用一个已经被污染的前提。

**这不是"多一个字段"的问题，是 world model 会不会自己骗自己的问题。**

### 1.2 新增顶层字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `state_version` | 整数 ≥ 0 | 每次 R11 归并成功 **+1**；所有 `validity.since_state_version` 与它比较 |

### 1.3 八类一等对象各增两个子字段（**不新增对象**）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `depends_on` | id 数组，可为 `[]` | ✅ | 本对象**依赖**谁（引用方向：下游 → 上游） |
| `validity` | 对象，四键：`status` / `reason` / `since_state_version` | ✅ | 本对象当前是否可信 |

**`validity.status` 冻结四值（逐字）：**

| 值 | 含义 |
|---|---|
| `valid` | 未受任何失效影响 |
| `stale` | 上游失效或自身证据过期，**结论暂不可引用** |
| `invalid` | 已被证伪 / 已被撤回（如 `E3` 泄漏） |
| `pending` | 正在复核，尚未定论 |

**`validity.reason`**：字符串，非空（为什么是当前状态）。
**`validity.since_state_version`**：整数，状态变为当前值的那个 `state_version`。

> **为什么放在八类对象上而不是建一张边表：** 边表会变成第九类对象。
> 按 §0.5/§0.6，能挂在既有对象上的就不许自立门户。

### 1.4 新增规则

| 规则（逐字，进 `RULES` 与 policy §4） |
|---|
| `V18` `每个一等对象的 validity.status ∈ {valid, stale, invalid, pending}；validity.reason 非空；since_state_version 必须是 ≤ state_version 的非负整数` |
| `V19` `一跳传播：若 A.depends_on 含 B 且 B.validity.status == invalid，则 A.validity.status 不得为 valid` |

**V19 的语义边界（不得扩大解释）：**

1. V19 只检查**一跳**。多跳传播是 **R11 的责任**：R11 必须**迭代到不动点**（直到没有新的对象需要转
   `stale`/`invalid`），然后才跑校验器。**校验器不做不动点迭代** —— 否则规则会变成图算法，难以判错。
2. `stale` **不自动传染**（只有 `invalid` 触发 V19）。理由：`stale` 是"待复核"，若它传染，
   一次文献更新会把半个 state 标灰，系统立刻不可用。
3. 传播**不得自动改 `claims[].status`**。`validity` 与 `claims[].status` 是两个轴：
   `validity` 说"这个对象现在能不能引用"，`status` 说"这个主张在证据上站不站得住"。
   **claim 的状态迁移仍然只能经 R8（证据驱动）或 R10（处置）。**

### 1.5 R11 的职责改写

> **R11 不只是"归并去重"。R11 = State consistency + dependency propagation engine。**

R11 收工前必须依次完成：① 归并去重 ② **失效传播至不动点** ③ `state_version + 1`
④ 跑 `state_check.py`（含 V18/V19），退出码必须为 `0`。

---

## 2. P0-4：Verification Trust Hierarchy（验证可信度层级）

### 2.1 命名修正（**这是本规格唯一一处改动用户提案的地方**）

用户提案的层级名是 `V0`—`V5`。**必须改，理由与 `L` 前缀弃用（policy §2.1）同源：**

| 冲突 | 说明 |
|---|---|
| `V1`—`V21` | 已经是**引用完整性规则号**，出现在 `RULES`、policy §4、`--list-rules`、所有审计报告里 |
| `V0`—`V5` | 若同时作为**证据层级**，则 `V2` 在同一份文档里既指「规则 2」又指「统计证据级」 |

**冻结为 `T0`—`T5`（`T` = Tier）。** 与 policy §2.1 拒绝 `L<n>` 完全同一条纪律。

| 层级 | 含义 | 谁产出 |
|---|---|---|
| `T0` | speculative / model-only（**LLM 自评的上限**） | 任何 reviewer / 子代理 |
| `T1` | literature-grounded | `S-Lit` + `literature[]` |
| `T2` | computational / statistical evidence | 实验（含统计检验） |
| `T3` | deterministic / artifact-verifiable | 可执行 artifact、unit test、定理证明检查器 |
| `T4` | independent replication / external validation | 外部复现、跨中心验证 |
| `T5` | expert / human validated（按需） | 用户 / 领域专家 |

### 2.2 新增字段

| 字段 | 位置 | 取值 | 必填 |
|---|---|---|---|
| `verification_tier` | `evidence[]` | `T0`—`T5` | ✅ |
| `verification_tier` | `assurance[]` | `T0`—`T5` | ✅ |

### 2.3 升级权限表（**本节的真正内容**）

> **核心规则：什么等级的 verifier，有权让什么 claim 升级。**

| 目标迁移 | 最低需要 | 谁的授权 |
|---|---|---|
| `ungrounded` → `partially-supported` | ≥ `T1` | R8（证据驱动） |
| `partially-supported` → `supported` | ≥ `T2` | R8（证据驱动） |
| 任一 → `contradicted` | ≥ `T2` | R8（证据驱动） |
| 任一 → `killed` | ≥ `T2` 或 `T3` | **仅 R10** |
| `T0` 证据 | **不得触发任何状态迁移** | 只能记 `plausible`，留在 `assurance[]` |

**明令：LLM reviewer（八攻击面的任何一位）的 tier 上限是 `T0`。**

它的产物可以写进 `assurance[]`、可以触发 R10 的 `RUN_TEST` / `FIX_IMPLEMENTATION`，
但**无权**把任何 claim 从 `Hypothesized` 升到 `Supported`。
**这条直接切断「agent 自己审自己、然后自己宣布通过」的闭环污染。**

### 2.4 新增规则

| 规则（逐字） |
|---|
| `V20` `claims[].status ∈ {partially-supported, supported, contradicted} 时，其 supporting_evidence 或 refuting_evidence 中至少一条 evidence[].verification_tier ≥ T2（partially-supported 可放宽为 ≥ T1）` |

**与 V5 的关系（不得混为一谈）：**

| 轴 | 字段 | 回答 |
|---|---|---|
| 认知状态 | `evidence[].epistemic_status` | 这条证据**现在**是什么认知状态 |
| 来源强度 | `evidence[].verification_tier` | 这条证据**由什么级别的验证者**产出 |

**两者正交。** `T3` 的证据可以因为范围问题而 `Unknown`；`Observed` 的证据也可以是 `T0`（模型自述的观测）。

---

## 3. P0-5：Outcome → State Delta 预注册

### 3.1 要解决的问题

```text
跑出来 A → 「这其实也支持我们的理论。」
跑出来 B → 「B 同样说明我们的机制成立。」
```

**事后解释会让理论变成不可证伪。**

### 3.2 新增字段（挂在 `experiments[]` 上，不新增对象）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `preregistration` | 对象 或 `null` | 见 V21 | 结果**冻结前**写下的「观察 → state delta」映射 |
| `result_at_state_version` | 整数 或 `null` | ✅ | 结果写入时的 `state_version`；未产生结果为 `null` |

**`preregistration` 结构：**

```text
{
  "frozen_at_state_version": <int>,
  "outcomes": [
    { "id": "O1",
      "observation": "<观察到什么>",
      "update": [ { "target": "<id>", "op": "<op>" }, ... ] }
  ]
}
```

**`op` 冻结七值（逐字）：**
`strengthen` / `weaken` / `falsify` / `kill` / `retain` / `retain-with-alternative` / `inconclusive`

### 3.3 新增规则

| 规则（逐字） |
|---|
| `V21` `experiments[].status ∈ {running, done, failed} 时必须存在 preregistration，且 frozen_at_state_version 必须是 ≤ result_at_state_version 的非负整数` |

### 3.4 阶段归属（**闭环的关键**）

```text
R8  defines success  （冻结 preregistration）
R9  produces evidence（执行，写 result_at_state_version）
R13 audits the same definition（逐条核对 prediction vs 实际 outcome）
```

**事后修改必须留痕：** 任何在 `frozen_at_state_version` 之后对 `outcomes` 的改动，
**必须**追加 `preregistration.amended[]`（含 `at_state_version` / `reason`）。
**静默改写 = 违反 R13 的 integrity gate（`S-Integrity`）。**

---

## 4. P0-6：Scientific Meta-Controller（调度，不是新阶段）

### 4.1 落点：**出 state 的 telemetry 文件**

```text
.research-idea-pipeline/<route>/scheduler.json
```

**不进 `research-state.json`，不新增第九类对象**（依 §0.5/§0.6）。

### 4.2 形式化

```text
S_t --π(S_t)--> a_t --> S_{t+1}
```

**`R0`—`R14` 是能力（capabilities），不是必须依次经过的 workflow。**

### 4.3 `next_action_policy.priority`（八级，冻结）

| 优先级 | 触发条件 | 对应动作 |
|---|---|---|
| 1 | `integrity_violation` | 立即停并修（`S-Integrity` fail） |
| 2 | `unresolved_critical_attack` | R10 处置 |
| 3 | `invalidated_dependency` | R11 失效传播 + 下游复核 |
| 4 | `high_information_gain_test` | R9 低成本高 EIG 实验 |
| 5 | `paradigm_escape_if_stagnant` | R3 `P1`—`P6` |
| 6 | `literature_collision` | R5 |
| 7 | `local_optimization` | R3 `local` / R6 |
| 8 | `narrative_or_venue_work` | R12 / R13 |

**`next_actions[]` 条目结构：** `{ action, type, target, eig, cost }`
（`type` 取 `discriminating_experiment` / `remote_analogy` / …；`eig` 取 `high`/`medium`/`low`/`unknown`）。

### 4.4 运行时机

**在任一 R 阶段开工前与收工后各跑一次**（读 `scheduler.json` + `research-state.json`，
输出 `next_actions[]` 与推荐的下一个阶段）。**它是横跨层，不是第 16 个阶段。**

### 4.5 边界（不得越权）

1. scheduler **只排序**，**不得**改变角色库、评分维度、门禁规则。
2. scheduler **不得**直接写 `research-state.json`；它只能**建议**下一个 R 阶段，由该阶段按自己的读写契约落盘。
3. scheduler 的 telemetry **不得**被叙事引用（它不是科学证据）。

---

## 5. P1 登记（本 Wave 不实现，只冻结设计意图）

| # | 项 | 落点 | 备注 |
|---|---|---|---|
| P1-7 | island lifecycle / `dormant` / reseeding | `hypotheses[].status` **增 `dormant`**（枚举变更 → V 规则 + 模板 + 测试三处同步） | §0.5 允许（是字段枚举，非新对象） |
| P1-8 | Literature Graph 的 typed structural edges + 2-hop/3-hop 路径检索 | `literature[].relation` 现值六值，**增结构类边**（如同构 / 同失败模式） | 服务 `P4` Remote Analogy：不搜"最像"，搜**结构路径** |
| P1-9 | system Meta-Memory / operator yield | `.research-idea-pipeline/<route>/operator-stats.json`（telemetry） | 记录 `generated` / `survived_R7` / `became_elite` / `recurring_failure_patterns`；**保留 exploration floor，不得直接淘汰低成功率 operator** |
| P1-10 | EIG 预测校准 | `experiments[]` 增 `predicted_information_gain` / `actual_information_gain` | 长期算 EIG calibration error |
| P1-11 | structural-equivalence novelty test | R7 `R-Novelty` **双 pass**（surface / structural）；canonicalize 七元组后与 `nearest_prior` 比结构 | `Δterminology ≫ 0` 且 `Δstructure ≈ 0` ⇒ 标 `reframing-only`，**不得**称 paradigm novelty |
| P1-12 | R8 Evidence Contract → R13 Review Rubric 共用 | R13 逐条核 `claims[].contract` | 避免 proposal 与 reviewer 各一套标准 |

## 6. P2 登记：Research Skill Eval Suite

**"139 tests OK" 只证明 schema / link / state / linter / 规则没坏，不证明这个 Skill 更会做研究。**
需建 blind replay 评测（拿历史项目做 A/B）：

| # | Eval | 判据 |
|---|---|---|
| E1 | Paradigm Escape | 不给它后来的真实创新，看能否进入正确的远域理论邻域 |
| E2 | False Novelty | 给一个其实已有工作的 idea，看 R5/R7 能不能发现 |
| E3 | Mechanism Trap | `performance improves` 但真因只是 extra training，看是否错写成机制成功 |
| E4 | Negative Result | 给 null result，看是否落 `unsupported` 而非 `falsified` |
| E5 | State Invalidation | 让 `E3` 后验被证伪，检查 `E→C→H→X→N` 是否正确传播 |
| E6 | Incremental Attractor | 给成熟 baseline，看是否产出 20 个 loss/adapter，还是跳出 representation |

**指标（比"平均 novelty 4.2"有意义）：**

| 指标 | 定义 |
|---|---|
| `LSCR`（Local-Search Collapse Rate） | Level-1 组件级候选 ÷ 全部保留下来的候选 |
| `PSR`（Paradigm Survival Rate） | 通过 R7 的 Level-3 候选 ÷ Level-3 生成数 |
| `FPR`（False Paradigm Rate） | 号称 paradigm、经结构等价检查后实为改写的比例 |

---

## 7. 验收清单（实现完成后必须全部机械可核）

| # | 项 | 命令 / 判据 |
|---|---|---|
| 1 | V18—V21 进 `RULES` 且与 policy §4 **逐字一致** | `--list-rules` ↔ policy §4 比较器，不一致 = 0 |
| 2 | 模板通过（含 `state_version` / `validity` / `depends_on` / `verification_tier` / `preregistration`） | `--check templates/research-state.template.json` → exit 0 |
| 3 | 每条新规则有违规 fixture + selftest | `--selftest` 全覆盖 `V1—V21` |
| 4 | 三方读/写表仍逐字一致 | 三方比较器，不一致 = 0 |
| 5 | 新增字段已在 policy §3 + 模板 + `state_check.py` **三处同步** | §3.11 硬要求 |
| 6 | §0 的六条不扩张承诺全部可核 | 见 §0 核验方式列 |

**依赖顺序（实现时不得颠倒）：** ① V18/V19（失效传播）→ ② `T0`—`T5` + V20
（可信度层级，因为它是升级权限的前提）→ ③ V21（预注册，因为 preregistration 的
`update.op` 要引用 ② 定下的升级权限）→ ④ scheduler（纯 telemetry，最后做，不阻塞前三项）。

---

## 8. 本规格与既有架构的关系

| 既有 | 本 Wave 的改变 |
|---|---|
| R1 常驻维护八类对象 | 八类对象各增 `depends_on` / `validity` |
| R11 = 归并去重 | **R11 = 归并 + 失效传播至不动点 + `state_version + 1`** |
| R8 = 证据契约 | **R8 兼结果预注册**（冻结 `preregistration`） |
| R13 = artifact 审计 | **R13 逐条核 `preregistration` vs 实际 outcome**，静默改写交 `S-Integrity` |
| R0—R14 顺序推进 | **改为 state-driven：`π(S_t)` 决定下一个动作**，R0—R14 是能力不是 workflow |
| `claims[].status` 只经 R8/R10 | **不变，且被 V20 加严**（升级需要 ≥T2 证据） |

---

## 9. 一句话总结

```text
Search      → Evidence        → State Update          （Wave 1—4 已有）
State Update → Dependency Invalidation → Next Action  （Wave 5 P0-3 / P0-6）
Research History → Meta-Learning → Better Future Search（Wave 5 P1-9 / P2）
```

**前两层决定它是不是一个可靠科研系统；第三层决定它会不会越来越会做研究。**
