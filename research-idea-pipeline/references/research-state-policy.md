# Research State 政策（R1 权威：八类一等对象、写入时机、Shape Gate S1—S7 与引用完整性 V1—V24）

**本文件是 R1 Research World Model（简称 `state`）的唯一权威定义。** 八类一等对象的 ID 前缀、
逐字字段、每个 R 阶段的读写时机、Shape Gate S1—S7 与引用完整性 V1—V24 都写在这里。各 phase 文件只引用本文件，
**不得**各自再定义一遍枚举——各写一遍就是新的漂移源。

**权威顺序：** 仓库级 spec `docs/r-architecture-wave1-spec.md`
（唯一接口契约；**不随本 skill 安装**，故此处**刻意不作链接**——
指向包外的链接在安装态必然断）> 本文件（state 类）> [claim-first-policy.md](claim-first-policy.md)
（claim 类）> [evidence-policy.md](evidence-policy.md)（措辞类）>
[scoring-policy.md](scoring-policy.md)（评分类）> 各 phase 文件。
本文件与 spec 冲突时**以 spec 为准**，**不得**自行解释或放宽。

**机器强制：** [../scripts/state_check.py](../scripts/state_check.py) 逐条执行 §4.0 的 S1—S7 与 §4.1 的 V1—V24
**没有 validator，「一等对象」是宣言，不是机制**（spec §2.3）。

**骨架：** [../templates/research-state.template.json](../templates/research-state.template.json)
（模板自身**必须**通过 S1—S7 与 V1—V24）。

---

## 1. 双循环与 R1 的常驻性

**结论：`state` 是唯一的机器状态权威；双循环的每个阶段开工前先读它，收工前写回它。**

```
R0 Research Contract ─▶ R1 Research World Model ─▶ R2 Field Mapping
                                                          │
                    ┌─────────────────────────────────────┴──────────┐
                    ▼                                                ▼
            DISCOVERY LOOP                                   ASSURANCE LOOP
        R3 Dual Discovery                                R7 Adversarial Assurance
        R4 Isolated Populations                          R8 Evidence Contract
        R5 Co-evolving Retrieval                         R10 Metacognitive Repair
        R6 Evolution                                     R13 Artifact-aware Review
                    └─────────────────────┬──────────────────────────┘
                                          ▼
                        R9 Experiment Tree ─▶ R10 Repair ─▶ R11 Update World Model
                                          ▼
                        R12 Narrative ─▶ R13 Review ─▶ R14 Decision
                                          └──────────▶ 回 R3 / R9（continue | pivot | archive | submit）
```

**核心硬规则（逐字取自 spec §1 / §5）：**

> **`R1` 是常驻对象，不是一次调用。** 任何 R 阶段开工前先读 world model，收工前写回。

> **检测到 critical flaw ⇒ Research State 必须改变。**
> 不允许「reviewer 发现问题 → 写进 review → 流程结束」。

**硬规则：**

1. **R1 不是阶段，是对象。** §5 的写入时机表里**没有** R1 行：它不是一次调用，而是被 R0—R14
   反复读写的同一份 state。把 R1 当成「跑一次的阶段」= 违规。
2. **critical flaw ⇒ state 必须改变**（逐字）。review 里写了 flaw 而 `repairs[]` 没有对应记录、
   或 `state_delta` 没有真正改到任何字段 = **未闭环**（V10，spec §5）。
3. **失败实验不得消失。** 失败的实验**必须**同时留在 `experiments[]`（`status: failed`）与
   `failures[]` 里（spec §4）。从叙事里删掉失败、只在 state 里留成功分支 = 违规。
4. **叙事是视图。** R12 的叙事由 state 生成，**不得**在叙事里出现 state 没有的 claim / evidence；
   叙事暴露的新缺口**必须**回到 `uncertainties[]`。
5. **state 不得写成散文。** 每个对象**必须**落 §3 的字段与 ID 引用；自然语言只允许出现在
   `statement` / `scope` / `interpretation` / `why` 这类字符串字段里，**不得**用一段文字代替 ID 引用。
6. **收工条件含校验。** 任何写回 state 的阶段，收工前**必须**跑 `state_check.py`；硬违规未清零，
   该阶段**不得**宣告完成（退出码见 §4）。

**双循环各自对 state 的作用：**

| 循环 / 段 | 阶段 | 对 state 的主要作用 |
|---|---|---|
| DISCOVERY LOOP | R3 / R4 / R5 / R6 | 生成并演化 `hypotheses[]`、`assumptions[]`、`uncertainties[]`、`literature[]` |
| ASSURANCE LOOP | R7 / R8 / R10 / R13 | 攻击 `claims[]` / `evidence[]`，产出 `assurance[]`、`failures[]`、`repairs[]` |
| 汇合段 | R9 / R10 / R11 | 实验树写进 `experiments[]`；修复闭环；增量归并回 state |
| 出口段 | R12 / R13 / R14 | 只读生成叙事与审计；决策回写 `claims[].status`、`repairs[].closure`、`uncertainties[].status` |

---

## 2. 八类一等对象与 ID 前缀

**结论：`state` 只有八类一等对象，ID 前缀固定为 `C / E / AS / H / X / LIT / F / U`，逐字不得改。**

| # | 对象 | ID（逐字） | 顶层字段 | 回答什么问题 |
|---|---|---|---|---|
| 1 | Claim Graph | `C<n>` | `claims[]` | 本文主张什么？被哪些证据支持 / 反驳？ |
| 2 | Evidence Ledger | `E<n>` | `evidence[]` | 有哪些证据？认知状态是什么？ |
| 3 | Assumption Graph | `AS<n>` | `assumptions[]` | 结论依赖哪些显式 / 默认假设？被谁挑战？ |
| 4 | Hypothesis Portfolio | `H<n>` | `hypotheses[]` | 有哪些候选假设？结构距离与 niche 是什么？ |
| 5 | Experiment Graph | `X<n>` | `experiments[]` | 做了 / 要做什么实验？挂在树的哪个节点？ |
| 6 | Literature Graph | `LIT<n>` | `literature[]` | 文献与本文主张是什么关系？ |
| 7 | Failure Memory | `F<n>` | `failures[]` | 哪些路已经走过且失败 / 被搁置？ |
| 8 | Uncertainty Map | `U<n>` | `uncertainties[]` | 最大的未知是什么？最便宜的判别实验是哪个？ |

**ID 纪律：**

1. 前缀**必须**用上表原样；序号按**路线内独立递增**，**永不复用**（承接
   [claim-first-policy.md](claim-first-policy.md) §3 规则 4 的 `E` 编号纪律，本轮推广到全部八类）。
2. 跨对象引用**必须**用 ID（如 `C17`、`LIT9`），**不得**用文件路径、标题或「上文的实验」。
3. 删除对象后其 ID **不得**让给新对象；作废的对象**必须**落到 `failures[]`（`kind: deprioritized`）
   或改 `status`，**不得**直接消失。

### 2.1 为什么文献节点用 `LIT` 而不是 `L`

**结论：文献节点必须用 `LIT<n>`。`L` 前缀不能再用——`L1 / L2 / L3` 已经有两个互不相同的含义。**

| 已有含义 | 定义位置 | 例子 |
|---|---|---|
| **迁移举证等级** | [narrative-patterns.md](narrative-patterns.md) §4 | 「迁移等级 L2：formal invariance / sufficient conditions」 |
| **检索尽职调查等级** | [literature-policy.md](literature-policy.md) §3.2 | 「L3 穷尽级：≥8 检索式、饱和、负检索记录」 |

[narrative-patterns.md](narrative-patterns.md) §4 已明文消歧「两者同形不同义」，再引入第三个
`L<n>`（文献节点）会让 `L2` 在同一份 state 里指三件事。故：

1. `literature[]` 的 ID **必须**是 `LIT<n>`；**不得**简写成 `L<n>`、`Lit<n>`、`P<n>`。
2. 检索等级与迁移等级**不得**写进 `literature[]` 的 ID；它们属于项目文档字段与叙事正文。
3. 其它前缀同理防撞：假设用 `AS`（`A` 已被路线 / 文档 ID 前缀占用），`C` / `E` **沿用**
   claim-first 的编号（`C0—C5`、`E<n>`），**不得**改——改了上一轮冻结的 `Ci ← Ej` 语法与
   全部示例一起作废。

### 2.5 验证可信度层级用 `T0`—`T5`，**不能用 `V0`—`V5`**

**结论：证据与保证的「来源强度」字段 `verification_tier` 取 `T0`—`T5`。**

**为什么不是 `V0`—`V5`：** `V1`—`V24` 已经是**引用完整性规则号**。若层级也用 `V`，
则 `V2` 在同一份文档里既指「规则 2」又指「统计证据级」。这与 §2.1 拒绝 `L<n>` 是
**同一条纪律**：一个前缀不能有两个含义。

| 层级 | 含义 | 谁产出 |
|---|---|---|
| `T0` | speculative / model-only（**LLM 自评的上限**） | 任何 reviewer / 子代理 |
| `T1` | literature-grounded | `S-Lit` + `literature[]` |
| `T2` | computational / statistical evidence | 实验（含统计检验） |
| `T3` | deterministic / artifact-verifiable | 可执行 artifact / unit test / 定理检查器 |
| `T4` | independent replication / external validation | 外部复现 / 跨中心验证 |
| `T5` | expert / human validated（按需） | 用户 / 领域专家 |

**升级权限表（本节的真正内容：什么等级的 verifier，有权让什么 claim 升级）：**

| 目标迁移 | 最低需要 | 授权方 |
|---|---|---|
| `ungrounded` → `partially-supported` | ≥ `T1` | R8 |
| `partially-supported` → `supported` | ≥ `T2` | R8 |
| 任一 → `contradicted` | ≥ `T2` | R8 |
| 任一 → `killed` | ≥ `T2` 或 `T3` | **仅 R10** |
| `T0` 证据 | **不得触发任何状态迁移** | 只能记 `plausible`，留在 `assurance[]` |

**明令：八攻击面的任何一位（LLM reviewer）tier 上限是 `T0`。** 它的产物可以写进
`assurance[]`、可以触发 R10 的 `RUN_TEST` / `FIX_IMPLEMENTATION`，但**无权**把任何 claim
从 `Hypothesized` 升到 `Supported`。这直接切断「agent 自己审自己、然后自己宣布通过」的闭环污染。

**与 V5 的关系：** `epistemic_status` 是**认知状态**，`verification_tier` 是**来源强度**，
两者**正交**。`T3` 的证据可以因范围问题而 `Unknown`；`Observed` 的证据也可以是 `T0`。

---

## 3. 每类对象的必填字段（逐字）

**结论：§3.1—§3.9 的字段名与枚举值是机器可读契约，逐字取自 spec §2.2 / §2.3 / §5，不得意译。**

**通用规则：**

1. 字段名与枚举值一律**逐字**使用本节的英文原样；**不得**翻译、改大小写、改连字符
   （`.json` 契约，与 [writing-policy.md](writing-policy.md) §8 第 6 条一致）。
2. 表中「必填 = ✅」指**键必须存在**；若取值允许为空，说明列另行注明（如「可为 `[]`」「可为 `null`」）。
   字段缺失 = 该对象无效。
3. **未在本节出现的字段 = 未定义字段**，**不得**自行添加。确实需要新字段时，**必须**先报 Lead
   改 spec，**不得**在本轮自行扩大字段表。
4. 所有跨对象引用**必须**用 §2 的 ID；空引用**必须**写 `[]`，**不得**写 `null`、`""` 或省略键。

### 3.0 八类一等对象的公共字段（`depends_on` / `validity`）

**结论：`claims` / `evidence` / `assumptions` / `hypotheses` / `experiments` / `literature` /
`failures` / `uncertainties` 八类对象的**每一条**都**必须**带 `depends_on` 与 `validity`；
`assurance` / `repairs` 不在此列。**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `depends_on` | id 数组，可为 `[]` | ✅ | 本对象**依赖**谁（方向：下游 → 上游）；跨类引用直接用 §2 的 ID |
| `validity` | 对象，三键 | ✅ | 本对象现在**能不能被引用** |

**`validity` 三键（逐字）：**

| 键 | 取值 | 说明 |
|---|---|---|
| `status` | `valid` \| `stale` \| `invalid` \| `pending` | **V18** |
| `reason` | 非空字符串 | 为什么是当前状态 |
| `since_state_version` | 整数 ≥ 0 且 ≤ `state_version` | 状态变为当前值的那个版本；**V18** |

**顶层新增 `state_version`：** 整数 ≥ 0；每次 R11 归并成功 **+1**。
所有 `validity.since_state_version` 与它比较（V18）。

**失效传播（V19，只查一跳）：** 若 `A.depends_on` 含 `B` 且 `B.validity.status == invalid`，
则 `A.validity.status` **不得为 `valid`**（`stale` / `invalid` / `pending` 都可以）。

> **证据链也是依赖：** 对 `claims[]`，其 `supporting_evidence` / `refuting_evidence` 指向的
> `evidence[]` **同样构成依赖边**。即「E 失效 ⇒ 依赖它的 C 不得仍标 `valid`」是自动可检的，
> **不要求**执行者额外把证据再登记进 `depends_on`。

**为什么放在八类对象上而不建一张边表：** 边表会变成**第九类一等对象**，
违反 Wave 5 spec §0.5 的不扩张承诺。

**与 `claims[].status` 的区别（不得混为一谈）：**

| 轴 | 字段 | 回答 |
|---|---|---|
| **可引用性** | `validity.status` | 这个对象**现在能不能被引用** |
| **支持度** | `claims[].status` | 这个主张**在证据上站不站得住** |

**两条边界（不得扩大解释）：**

1. **V19 不得自动改 `claims[].status`。** claim 状态迁移仍只能经 R8（证据驱动）或 R10（`state_delta`），
   见 §5 硬规则 4。
2. **`stale` 不传染** —— 只有 `invalid` 触发 V19。否则一次文献更新会把半个 state 标灰，系统立刻不可用。
3. **多跳传播是 R11 的责任，不是校验器的。** R11 必须**迭代到不动点**后再跑校验器；
   `state_check.py` 只查一跳（图算法无法逐条判错）。

   **不动点的判定（必须可执行，不得只写口号）：**
   - 对**全体一类对象**做一趟扫描；若这一趟中**没有任何对象的 `validity.status` 发生变化**，
     即为不动点，停止。
   - **必须设上限**：扫描趟数上限 = 对象总数（下界 3）。**禁止无限迭代。**
   - 到达上限仍未收敛 → **不得静默继续**：须落 `uncertainties[]`（`importance: critical`），
     并在 `repairs[]` 记一条 `disposition: FIX_IMPLEMENTATION`，然后才可进入下一阶段。
   - 传播**只允许改 `validity`**；任何 `claims[].status` 的改动必须走 R8 或 R10（§5 硬规则 4）。
   - **传播产生的下游状态一律写 `stale`（不得写 `invalid`）。**
     理由：`invalid` 只表示「该对象自身已被证伪 / 撤回」，是**独立判定**的结果，不是传染出来的。
     加上这条后，不动点**唯一**且**一趟即达**（`stale` 不传染），执行者之间不会有分歧；
     若某对象确应 `invalid`，必须由它**自身的**证据或处置给出理由。

### 3.1 `claims[]` — Claim Graph（`C<n>`）

**结论：每个 claim 必须有可证伪的 `falsifier`，且 `supporting_evidence` / `refuting_evidence` 只能指向真实存在的 `E`。**

| 字段 | 取值 / 类型（逐字） | 必填 | 说明 |
|---|---|---|---|
| `id` | `C<n>` | ✅ | 子 claim 沿用 spec 例 `C17a` 形态 |
| `statement` | 字符串 | ✅ | 一句话主张 |
| `parent` | `null` 或存在的 `C` id | ✅ | claim 树 |
| `subclaims` | `C` id 数组，可为 `[]` | ✅ | |
| `status` | `ungrounded` \| `supported` \| `partially-supported` \| `contradicted` \| `killed` | ✅ | 取值受 V3 约束 |
| `supporting_evidence` | `E` id 数组，可为 `[]` | ✅ | 受 V2 / V5 约束 |
| `refuting_evidence` | `E` id 数组，可为 `[]` | ✅ | 受 V2 约束 |
| `nearest_alternative` | 字符串 | ✅ | 最近的替代解释 |
| `falsifier` | 字符串，非空 | ✅ | V1；写不出证伪条件 = 不是科学主张 |
| `scope` | 字符串 | ✅ | 结论成立的范围；`NARROW_SCOPE` / `ACCEPTED_LIMITATION` 的落点 |
| `known_flaws` | `F` id 数组，可为 `[]` | ✅ | V4 的引用点之一 |

### 3.2 `evidence[]` — Evidence Ledger（`E<n>`）

**结论：证据的 `epistemic_status` 决定它能不能被 claim 引用；五值之外不得新增。**

| 字段 | 取值 / 类型（逐字） | 必填 | 说明 |
|---|---|---|---|
| `id` | `E<n>` | ✅ | 路线内唯一、不复用 |
| `kind` | `experiment` \| `literature` \| `theory` \| `observation` | ✅ | |
| `supports` | `C` id 数组，可为 `[]` | ✅ | 指向被支持的 claim / subclaim |
| `contradicts` | `C` id 数组，可为 `[]` | ✅ | |
| `strength` | `partial` \| `strong` \| `weak` | ✅ | |
| `scope` | 字符串（例 `brain MRI / acceleration=4`） | ✅ | 证据自身的适用范围，不得越界 |
| `epistemic_status` | `Observed` \| `Supported` \| `Hypothesized` \| `Planned` \| `Unknown` | ✅ | V5；↔ 措辞等级见 [evidence-policy.md](evidence-policy.md) §3 |
| `source_ref` | 字符串 | ✅ | 具体位置（实验 id / 文献 / 定理 / 数据路径） |
| `verification_tier` | `T0` \| `T1` \| `T2` \| `T3` \| `T4` \| `T5` | ✅ | 证据的**来源强度**（§2.5）；与 `epistemic_status` **正交**；**V20** |

### 3.3 `assumptions[]` — Assumption Graph（`AS<n>`）

**结论：默认假设必须显式化，否则它无法被攻击。**

| 字段 | 取值 / 类型（逐字） | 必填 | 说明 |
|---|---|---|---|
| `id` | `AS<n>` | ✅ | |
| `statement` | 字符串 | ✅ | 假设内容 |
| `status` | `explicit` \| `tacit` | ✅ | `tacit` = 尚未被写出来的默认假设 |
| `challenged_by` | `H` id 数组，可为 `[]` | ✅ | 哪个假设在挑战它 |
| `if_false` | 字符串 | ✅ | 假设为假时的后果与需要改的 claim |

### 3.4 `hypotheses[]` — Hypothesis Portfolio（`H<n>`）

**结论：每条假设必须有非空 `niche`、完整的五维 `structural_signature`，以及可追溯的 `operator` / `parents` 谱系，否则 QD archive 与 lineage 都无法成立。**

| 字段 | 取值 / 类型（逐字） | 必填 | 说明 |
|---|---|---|---|
| `id` | `H<n>` | ✅ | |
| `statement` | 字符串 | ✅ | |
| `structural_signature` | 对象，键固定五个：`assumption_distance` / `formulation_distance` / `representation_distance` / `theory_lens_distance` / `mechanism_distance` | ✅ | 五键**全部**必填，取整数距离 |
| `novelty_source` | 字符串 | ✅ | 新颖性来自哪里（问题重构 / 跨域迁移 / 表示变更……） |
| `theory_lens` | 字符串 | ✅ | 用什么理论视角看问题 |
| `nearest_prior` | 字符串 | ✅ | 最近的前作（可引 `LIT<n>`） |
| `falsifier` | 字符串 | ✅ | |
| `expected_information_gain` | 数值（如 `0.0`） | ✅ | EIG 排序用（spec §4） |
| `status` | `active` \| `elite` \| `archived` \| `killed` | ✅ | |
| `niche` | `N1`—`N10` 之一（**V6 强制**；复用 preset 名，不引入第二套枚举） | ✅ | V6；QD archive 的前提 |
| `island` | `P1`—`P6` / `local` | ✅ | 该候选由哪条 escape 轨产生（默认开启 `P1`—`P4`；`local` = Local Search）；**V13 强制**。**`P3` 不出现在这里** —— 它只产 typed intermediate（见 §5.0 规则 1） |
| `operator` | 十二算子之一（见下表） | ✅ | 产生该候选的搜索算子；`generation == 0` 时**必须与 `island` 一一对应**；**V16 强制** |
| `parents` | `H` id 数组，可为 `[]` | ✅ | 谱系：父候选；初始候选写 `[]`；**V17 强制**（必须存在、不得自指或成环、generation 严格大于每个 parent） |
| `generation` | 整数 ≥ 0 | ✅ | `0` = 初始候选，每次 R6 进化 +1；**V14 强制** |

**十二算子（冻结，逐字）：**

| 来源 | `operator` | 对应 `island` | 含义 |
|---|---|---|---|
| generation-0（island 算子） | `reframe` | `P1` | 问题重构：改 object / target variable / formulation / success criterion |
| generation-0 | `assumption_breaker` | `P2` | 假设破坏：`AS_i → ¬AS_i →` 新 research world |
| generation-0 | `abstraction` | `P3` | 领域擦除：出 `domain-free skeleton`，**不产完整方法**；**也不产出 `hypotheses[]` 条目**（该算子不会出现在任何 candidate 的 `operator` 上） |
| generation-0 | `remote_analogy` | `P4` | 远域类比：`semantic distance high` + `structural correspondence high` |
| generation-0 | `theory_lens` | `P5` | 理论视角：换 mathematical object 并导出 ≥2 类后果 |
| generation-0 | `counterexample` | `P6` | 反例 / 不可能性 / 测量反转 |
| generation-0 | `local` | `local` | 已有范式内的稳健局部改进 |
| R6 进化（五个） | `mutation` / `crossover` / `simplification` / `theory_induced` / `new_niche` | —（跨 island） | 见 [phase-r3-r6-discovery.md](phase-r3-r6-discovery.md) §R6.1 |

**谱系硬规则：** `generation == 0` 的候选 `parents` **必须为 `[]`**（没有任何 parent 的 generation 能严格小于 0）；
`generation ≥ 1` 的候选 `parents` **不得为空**（V17 要求每个 parent 的 generation 严格小于本候选，
成环必然违反这条，因此自指与环都被同一条规则拦下）。

### 3.5 `experiments[]` — Experiment Graph（`X<n>`）

**结论：每个实验节点必须携带完整 provenance；`stage` 只能是六段之一，`X2` 不得承担 claim 判别。**

| 字段 | 取值 / 类型（逐字） | 必填 | 说明 |
|---|---|---|---|
| `id` | `X<n>` | ✅ | |
| `parent` | `null` 或存在的 `X` id | ✅ | V8；树不得成环 |
| `stage` | `X1` \| `X2` \| `X3` \| `X4` \| `X5` \| `X6` | ✅ | 六段含义见下表 |
| `claim_targeted` | `C` id 数组，可为 `[]` | ✅ | |
| `alternative_targeted` | 字符串数组（例 `ALT-1`），可为 `[]` | ✅ | 该实验要排除的替代解释 |
| `code_commit` | 字符串 | ✅ | provenance：代码版本 |
| `data_split` | 字符串 | ✅ | provenance：数据划分 |
| `seed` | 整数 | ✅ | provenance：随机种子 |
| `metric` | 字符串 | ✅ | |
| `result` | 字符串 | ✅ | 未产生结果时留空，**不得**预填臆造结果 |
| `interpretation` | 字符串 | ✅ | |
| `unexpected` | 字符串数组，可为 `[]` | ✅ | 与预期不符之处，**必须**留痕 |
| `known_flaws` | `F` id 数组，可为 `[]` | ✅ | V4 的引用点之二 |
| `next_branches` | `X` id 数组，可为 `[]` | ✅ | |
| `status` | `planned` \| `running` \| `done` \| `failed` | ✅ | 失败实验**必须**保留（spec §4） |
| `preregistration` | 对象 或 `null` | 见 V21 | **结果冻结前**写下的「观察 → state delta」映射；R8 冻结、R9 执行、R13 逐条核 |
| `result_at_state_version` | 整数 ≥ 0 或 `null` | ✅ | 结果写入时的 `state_version`；未产生结果为 `null`；**V21** |

**实验树六段（固定，`stage` 取值，逐字）：**

| `stage` | 含义 |
|---|---|
| `X1` | 可行性 / 健全性 |
| `X2` | 基线校准 |
| `X3` | **claim 判别实验** |
| `X4` | 机制 / 替代解释 |
| `X5` | 边界 / regime 位移 |
| `X6` | 复现 / 稳健性 |

**硬规则：`X2` 只做基线校准，不允许承担 claim 判别**（防「调超参驱动」的结构性措施，spec §2.2）。
需要判别 claim 的实验**必须**登记为 `X3`。

### 3.6 `literature[]` — Literature Graph（`LIT<n>`）

**结论：文献节点只记「与本文的关系」，不重复记文献元数据。**

| 字段 | 取值 / 类型（逐字） | 必填 | 说明 |
|---|---|---|---|
| `id` | `LIT<n>` | ✅ | §2.1；**不得**写成 `L<n>` |
| `ref` | 字符串（例 `[作者, 会议/年份]`） | ✅ | 元数据以 `docs/refs/index.json` 为准（[literature-policy.md](literature-policy.md) §7.1） |
| `relation` | `supports` \| `contradicts` \| `shares-assumption` \| `shares-structure` \| `solves-analogous-problem` \| `uses-same-theory` | ✅ | 六值封冻，不得新增 |

### 3.7 `failures[]` — Failure Memory（`F<n>`）

**结论：每条失败记录必须被至少一个 claim 或实验的 `known_flaws` 引用，否则它是死数据。**

| 字段 | 取值 / 类型（逐字） | 必填 | 说明 |
|---|---|---|---|
| `id` | `F<n>` | ✅ | |
| `kind` | `falsified` \| `unsupported` \| `inconclusive` \| `failed-to-reproduce` \| `engineering-failure` \| `deprioritized` | ✅ | 六值封冻 |
| `what` | 字符串 | ✅ | 什么失败了 |
| `why` | 字符串 | ✅ | 为什么失败 / 为什么搁置 |
| `referenced_by` | `C` / `X` id 数组 | ✅ | 与 V4 的 `known_flaws` 引用**并存**，两者都要有 |

### 3.8 `uncertainties[]` — Uncertainty Map（`U<n>`）

**结论：每条不确定项必须给出最便宜的判别实验，或显式写 `TBD`。**

| 字段 | 取值 / 类型（逐字） | 必填 | 说明 |
|---|---|---|---|
| `id` | `U<n>` | ✅ | |
| `question` | 字符串 | ✅ | 未知是什么 |
| `importance` | `critical` \| `high` \| `medium` \| `low` | ✅ | R9 只对 `critical` / `high` 且 `uncertainty: high` 的项排序（spec §4） |
| `uncertainty` | `high` \| `medium` \| `low` | ✅ | 当前不确定程度 |
| `cheapest_discriminating_test` | 存在的 `X` id 或字面量 `TBD` | ✅ | V7 |
| `status` | `open` \| `closed` | ✅ | 关闭**必须**有对应实验证据，不得口关 |

### 3.9 `assurance[]` 与 `repairs[]`（V9 / V10 强制）

**结论：这两类数组的字段名同样逐字取自 spec（§2.3 V9 / V10 与 §5），本文件不额外发明字段。**

| 顶层字段 | 条目字段 | 取值 / 类型（逐字） | 必填 | 说明 |
|---|---|---|---|---|
| `assurance[]` | `kill_condition` | 字符串，非空 | ✅ | V9；什么结果会杀死该 claim / 假设 |
| `assurance[]` | `discriminating_test` | 存在的 `X` id 或字面量 `TBD` | ✅ | V9 |
| `assurance[]` | `verification_tier` | `T0` \| `T1` \| `T2` \| `T3` \| `T4` \| `T5` | ✅ | §2.5；**LLM reviewer 产物的上限是 `T0`** —— 不得据此升级任何 claim 状态 |
| `repairs[]` | `flaw` | 字符串 | ✅ | V10；发现的缺陷（含 critical flaw） |
| `repairs[]` | `disposition` | `REPAIR_CLAIM` \| `RUN_TEST` \| `FIX_IMPLEMENTATION` \| `NARROW_SCOPE` \| `KILL_BRANCH` | ✅ | V10；五值封冻 |
| `repairs[]` | `state_delta` | 字符串 | ✅ | V10；**实际改动了哪些字段**，必须可核对 |
| `repairs[]` | `targets` | id 数组，可为 `[]` | ✅ | **V22**；该修复**直接作用**的对象 id —— 供「claim 被否决必须走 R10」做**精确**核对（不用易误判的子串匹配） |
| `repairs[]` | `closure` | `RESOLVED` \| `ACCEPTED_LIMITATION` | ✅ | V10；两值封冻 |
| `reviews[]` | `id` | 非空字符串（例 `REV7`） | **`integrity_gate == fail` 时必填** | **V23**；没有 id 就无法与 `repairs[]` / `failures[]` 建立关联 |
| `repairs[]` | `source_review` | `reviews[]` 的 id 或 `null` | ✅ | **V23**；该修复**因哪一次审查**而产生。**必须逐条对应** —— 全局存在性不算闭环 |
| `failures[]` | `source_review` | `reviews[]` 的 id 或 `null` | ✅ | **V23**；同上，供「记成失败」的闭环路径使用 |

**修复门的硬规则（spec §5）：**

1. 只写 `flaw` 而无 `disposition` 或 `state_delta` = **未闭环**；`closure` 为空 = **该轮不得结束**。
2. `ACCEPTED_LIMITATION` **必须**同时写入 `claims[].scope` 或 `claims[].known_flaws`，
   否则不算接受，只是忽略。
3. `RUN_TEST` 的 `state_delta` **必须**指向一个已登记的 `X`（`status: planned` 起），
   **不得**写「以后补实验」这类无 ID 的承诺。
4. `disposition` / `closure` 只有上表这些值；**不得**新增 `PARTIAL`、`DEFERRED` 之类的中间态。

---

## 4. 机械闸门：Shape Gate（S1—S7）+ 引用完整性（V1—V24）

**执行顺序（强制）：** 顶层结构（退出码 `4`）→ **Shape Gate S1—S7** → **V1—V24**。
形状失败时**不执行** V 规则 —— V 规则的措辞假设输入形状成立，
在形状错误上跑会给出误导性的级联判定。

### 4.0 Shape Gate S1—S7（在 V1—V24 之前跑）

**结论：S1—S7 全部是硬违规（退出码 `3`）；任何一条未清零，state 不得作为下一阶段的输入。**

**规则表（与 `state_check.py` 的 `SHAPES` 逐字一致）：**

| # | 规则（逐字） | 违规 | 典型反例 |
|---|---|---|---|
| S1 | 八类一等对象数组全部存在，且每个都是对象数组 | 形状 | 只写 `claims` 就交工；`"experiments": {}` |
| S2 | 每条一等对象条目有非空字符串 id，且 id 在本数组内唯一 | 形状 | `"id": ""`；两个 `C1`；claim 写成 `"id": "Q1"` |
| S3 | 冻结枚举字段必须存在且取值在枚举内（只查 V1—V24 未覆盖的枚举） | 形状 | `experiments[0].stage: "X9"`；`literature[0].relation: "sounds-good"`；`hypotheses[0]` 缺 `status` |
| S4 | 每条 hypothesis 的 structural_signature 是对象，五键齐全，值为非负整数 | 形状 | 只写 `{"assumption_distance": 2}`；`"structural_signature": "flat"` |
| S5 | claims[].contract 存在时是对象，十个契约键齐全，类型正确 | 形状 | 契约只写 4 键；`expected_outcomes` 写成数组 |
| S6 | reviews 存在时是对象数组，decision 存在时是对象；integrity_gate 取值在枚举内 | 形状 | `"reviews": {}`；`"decision": "continue"`；`integrity_gate: "maybe"` |
| S7 | state_version 是非负整数 | 形状 | `"state_version": "0"`；`-1` |

**S 与 V 的分工（不得互相重复）：**
S 只查**齐全 / 必填 / 类型 / 枚举 / 对象形状**；语义一致性由 V1—V24 负责。
**已被 V 规则覆盖的字段不在 S 里重复** —— 否则一次改动会同时报 S 与 V，掩盖真正的规则号。
分工清单：`falsifier` 属 V1；`kill_condition` 属 V9；`depends_on` 的类型与悬空属 V19；
`reviews[].id`（`gate == fail` 时必填）属 V23；`decision.verdict` 的枚举属 V24；
`epistemic_status` / `niche` / `island` / `operator` / `generation` / `validity.status` /
`verification_tier` / `disposition` / `closure` / `preregistration.outcomes[].op`
各自已有 V 规则。

**S3 覆盖的枚举（改动前曾被静默放过）：**

| 数组 | 字段 | 冻结取值 |
|---|---|---|
| `claims[]` | `status` | `ungrounded` \| `supported` \| `partially-supported` \| `contradicted` \| `killed` |
| `evidence[]` | `kind` | `experiment` \| `literature` \| `theory` \| `observation` |
| `evidence[]` | `strength` | `partial` \| `strong` \| `weak` |
| `assumptions[]` | `status` | `explicit` \| `tacit` |
| `hypotheses[]` | `status` | `active` \| `elite` \| `archived` \| `killed` |
| `experiments[]` | `stage` | `X1` \| `X2` \| `X3` \| `X4` \| `X5` \| `X6` |
| `experiments[]` | `status` | `planned` \| `running` \| `done` \| `failed` |
| `literature[]` | `relation` | `supports` \| `contradicts` \| `shares-assumption` \| `shares-structure` \| `solves-analogous-problem` \| `uses-same-theory` |
| `uncertainties[]` | `importance` | `critical` \| `high` \| `medium` \| `low` |
| `uncertainties[]` | `uncertainty` | `high` \| `medium` \| `low` |
| `uncertainties[]` | `status` | `open` \| `closed` |

### 4.1 引用完整性 V1—V24

**结论：V1—V24 全部是硬违规；任何一条未清零，state 不得作为下一阶段的输入。**

**规则表（规则文本逐字取自 spec §2.3；`state_check.py` 与该表一一对应）：**

| # | 规则（逐字） | 违规 | 典型反例 |
|---|---|---|---|
| V1 | 每个 C 的 falsifier 非空 | 硬 | `"falsifier": ""`，或写了「无法证伪」 |
| V2 | C.supporting_evidence / refuting_evidence 的每个 id 必须存在于 evidence[] | 硬 | `"supporting_evidence": ["E9"]`，但 `evidence[]` 里没有 `E9`；或写成 `"E9 (文献)"` |
| V3 | 无任何 E 引用的 C 必须 status: ungrounded；有 E 却标 ungrounded 也是违规 | 硬 | 无证据的 `C3` 标 `supported`；有 `E1` 的 `C0` 标 `ungrounded` |
| V4 | 每条 F 必须被至少一个 claims[].known_flaws 或 experiments[].known_flaws 引用 | 硬 | `F3` 只出现在 `failures[].referenced_by` 里，没有任何 `known_flaws` 指向它 |
| V5 | epistemic_status ∈ 五值；Hypothesized / Unknown 的条目不得出现在 supporting_evidence | 硬 | `C0.supporting_evidence: ["E4"]`，而 `E4.epistemic_status: Hypothesized`；或写了 `"observed"`（大小写） |
| V6 | 每条 H 的 `niche` 非空**且 ∈ `N1`—`N10`**（复用 preset 名，不引入第二套枚举） | 硬 | `"niche": ""` / `"niche": "N11"`（越界）；**旧描述性 niche 名同样违规**（见 `deprecated-terms.txt`） |
| V7 | U.cheapest_discriminating_test 必须指向存在的 X，或字面量 TBD | 硬 | 指向 `X18`，但 `experiments[]` 里没有 `X18`；或写「暂无」 |
| V8 | X.parent 必须是存在的 X 或 null；树不得成环 | 硬 | `X7.parent: "X8"`、`X8.parent: "X7"`（互指成环）；或 `parent: "X99"` |
| V9 | assurance[].kill_condition 非空，且 discriminating_test 指向存在的 X 或 TBD | 硬 | `"kill_condition": ""`；`discriminating_test` 指向未登记的实验 |
| V10 | 每条 repairs[] 记录必须齐备 flaw / disposition / state_delta / closure | 硬 | 只写 `flaw` 与 `disposition`——未闭环；`closure` 写 `后续再看` |
| V11 | stage == X2（基线校准）时 claim_targeted 必须为空数组，不得承担 claim 判别 | 硬 | `{"stage":"X2","claim_targeted":["C0"]}` |
| V12 | status == failed 的 X 必须被某条 failures[].referenced_by 引用（失败不得消失） | 硬 | failed 实验没有对应 `F` |
| V13 | hypotheses[].island ∈ {P1..P6, local}（默认开启 P1—P4，P5/P6 按需），但 **`P3` 不得出现**（P3 只产 typed intermediate，不产 candidate） | 硬 | `"island": "PX"`；`"island": "P3"` |
| V14 | hypotheses[].generation 是非负整数 | 硬 | `"generation": "1"` / `-1` |
| V15 | 每个 live niche（含 status ∈ {active, elite} 的候选）至少有一条 status: elite；全部 killed/archived 的 niche 不要求 elite | 硬 | `N5` 下全是 `active` |
| V16 | hypotheses[].operator ∈ 十二算子之一；generation == 0 时必须与 island 一一对应 | 硬 | `{"island": "P2", "generation": 0, "operator": "reframe"}`；或 `"operator": "Reframe"`（大小写）；或空串 |
| V17 | hypotheses[].parents 必须是数组，每个 id 存在且 generation 严格大于每个 parent（不得自指或成环） | 硬 | `"parents": ["H9"]` 但无 `H9`；`"parents": []` 而 `generation: 1`；`H3.parents: ["H4"]` 且 `H4.parents: ["H3"]` |
| V18 | 每个一等对象的 validity.status ∈ {valid, stale, invalid, pending}；validity.reason 非空；since_state_version 是 ≤ state_version 的非负整数 | 硬 | 缺 `validity`；`"status": "ok"`；`"reason": ""`；`since_state_version: 7` 而 `state_version: 3` |
| V19 | 一跳传播：若 A 依赖 B（A.depends_on 含 B，或 A 是 claim 且其 supporting_evidence / refuting_evidence 含 B）且 B.validity.status == invalid，则 A.validity.status 不得为 valid | 硬 | `E3.validity.status: "invalid"`，而 `C2.depends_on: ["E3"]` 且 `C2.validity.status: "valid"` |
| V20 | claims[].status ∈ {partially-supported, supported, contradicted} 时，需有 evidence[].verification_tier 达阈值（partially-supported ≥ T1，其余 ≥ T2） | 硬 | `C0.status: "supported"`，而其支持证据全是 `T0`（LLM 自评）；或证据缺 `verification_tier` |
| V21 | status ∈ {running, done, failed} 的 experiments[] 必须存在 preregistration；done/failed 时 frozen_at_state_version ≤ result_at_state_version | 硬 | `X12` 已 `done` 却无 `preregistration`；或 `frozen_at_state_version: 5 > result_at_state_version: 4`；或 `op: "improve"` 越界 |
| V22 | claims[].status ∈ {killed, contradicted} 时必须被至少一条 repairs[] 覆盖（该条 repairs[].targets 含此 claim 的 id，且 disposition ∈ 五值） | 硬 | `C5.status: "killed"` 而没有任何 `repairs[].targets` 含 `C5`——**决策层无权改 claim 真值**（SKILL §1.7） |
| V23 | reviews[].integrity_gate == "fail" 时必须存在以 source_review 关联该 review id 的 repairs[]（disposition ∈ 五值）或 failures[]（kind ∈ 六值） | 硬 | `integrity_gate: "fail"`，而 `repairs[]` 与 `failures[]` 都没有对应记录——**Gate 不是 warning** |
| V24 | decision.verdict 存在时必须是 continue / pivot / archive / submit 之一 | 硬 | `"verdict": "banana"`，或空串 |

**执行契约（spec §2.3）：**

| 项 | 约定 |
|---|---|
| 退出码 | `0` 全部通过；`3` 存在硬违规；`4` 环境不满足（文件缺失、非法 JSON、结构不符等） |
| `--json` | 输出机器可读结果 |
| `--check` | 只校验不写（默认行为即只校验） |
| `--list-rules` | 列出 Shape Gate S1—S7 与 V1—V24 及判据（本文件 §4.0 / §4.1 两表与它逐字一致） |
| `--selftest` | 内置自检，S1—S7 与 V1—V24 全覆盖 |
| 收工门槛 | 退出码**必须**为 `0`；`3` / `4` 都**不得**当作通过 |

**与 `state_check.py` 实现的对应（一一对齐，不得各自解释）：**

1. **V10 加严到枚举**：`state_check.py` 除检查四字段齐备（非空字符串）外，还硬校验
   `disposition` ∈ 五值、`closure` ∈ 两值，`strip` 后**精确比对**（`"run_test"` 判违规）。
   这是 spec §7「R10 的处置 / 关闭枚举逐字一致」的机械落点——只查「非空」拦不住
   `"disposition": "FIX"`。
2. **V5 只收单个合法值**：`epistemic_status` **必须**是五值之一；**不得**把
   `"Observed | Supported | ..."` 这类枚举提示串填进字段（那是给人看的表，不是值）。
3. **顶层结构**：state 顶层**直接**是八类数组；八类数组**全部**缺失 → 退出码 `4`（不算 world model）。
   **任一数组缺失 → S1（退出码 `3`）** —— 模板 `_usage` 明写「不使用 null 或省略键」。
   `assurance` / `repairs` 键**缺失按空数组处理**（不算违规），键存在但不是数组 → 退出码 `4`。
4. **ID 存在性**：V7 / V9 指向的 `X` 与 V2 引用的 `E` **必须**是真实存在的 id；
   **不得**写 `"X?"`、`"待补"`、`"E9 (文献)"` 这类带修饰的串。

**边界（不得扩大解释）：**

1. **S1—S7 覆盖形状**（齐全 / 必填 / 类型 / 枚举 / 对象形状），**V1—V24 覆盖引用完整性**。
   两层都是硬违规。**S 查不到的**（措辞等级、判据口径）见 §3 与各 policy 文件——
   **不得**因为「机械闸门没查」就省略字段或放松措辞。
2. V5 只否决 `Hypothesized` / `Unknown` 进 `supporting_evidence`；`Planned` 条目的引用纪律
   见 [claim-first-policy.md](claim-first-policy.md) §2 与 [evidence-policy.md](evidence-policy.md) §3
   ——**不得**当作证据引用（R8 的 Evidence Contract 只收 `Observed` / `Supported`）。
3. V3 的判定是**双向**的：漏标 `ungrounded` 与错标 `ungrounded` 都是硬违规。
4. 校验器报的是**字段与 ID**，不是措辞。措辞等级一律查 [evidence-policy.md](evidence-policy.md) §1 / §3，
   **不得**用 state 里的 `epistemic_status` 直接充当「已核实」。

---

### 5.0 三条归属规则（总收官审计 M-1 / M-2）

1. **`claims[]` 的创建归属 = R3。** 每个 **candidate** 必须产出至少一条 `C`（其 central
   proposition，`status: ungrounded`）。**R7 攻击它、R8 建契约并更新 status、R12 只做视图（不创建）**。
   —— 否则 R7/R8 在读一个没人写的对象，V1/V2/V3 永不触发。
   **candidate 的定义见 [phase-r3-r6-discovery.md](phase-r3-r6-discovery.md) §R3.0.1：
   `P3` 只产 typed intermediate，**不是** candidate，不产 `H` 也不产 `C`（`V13` 强制）。**
2. **每个写 `failures[]` 的阶段（R6 / R7 / R9 / R13）同时负 `known_flaws` 义务**：
   把新 `F` 的 id 挂到对应 `claims[].known_flaws` 或 `experiments[].known_flaws`。
   —— 否则 V4 会在**这些阶段自己的收工检查**上报错，而写表又不授权它改 `known_flaws`。
   （挂 `known_flaws` **不是**改 `claims[].status`，不与 §1.6 冲突。）

3. **`claims[].status` 的变更分两类：** **升级**（`ungrounded` → `partially-supported` / `supported`）
   由 **R8** 按证据驱动执行；**降级与否决**（`contradicted` / `killed`）**只能经 R10**。
   这条与 SKILL §1.6 的「默认只能经 R10」互为例外关系 —— 八处提及该禁令的地方都已回指本条。

> **终端产物（无显式读者，不是僵尸字段）：** `narrative_view`（R12 写、R13/R14 通过「全 state」隐含读）
> 与 `decision`（R14 写、供人读与下一轮 R3/R9 的 `pivot`/`continue` 依据）。
> 机械比对会把它们当成「写了没人读」，**这是设计内**。

## 5. 写入时机：每个 R 阶段读什么、写什么

**结论：每个阶段都必须「先读 state，再写 state」；下面是逐阶段的读写契约，phase 文件不得超出该表。**

**说明：** R1 **不占行**——它是被反复读写的常驻对象（§1 硬规则 1）。R4 / R5 属 Wave 2
（spec §8），本轮不单独列行；其产出经 R6 落入 `hypotheses[]` / `uncertainties[]`。
下表「对应文件」列的文件名取自 spec §3 的文件地图（由各 phase 所有者创建）。

| 阶段 | 读什么（state 字段） | 写什么（state 字段） | 对应文件 |
|---|---|---|---|
| **R0** Research Contract | — | `contract` + 模板骨架（含 `state_version: 0`） | `phase-r0-contract.md` |
| **R2** Field Mapping | `literature` / `assumptions` / `uncertainties` | `literature` / `evidence`(kind=literature) / `assumptions` / `uncertainties` | `phase-r2-r5-field-mapping-retrieval.md` |
| **R3** |`literature` / `assumptions` / `failures` / `contract.constraints` | `hypotheses`（**含 `niche` / `island` / `operator` / `parents: []` / `generation: 0`**）/ `claims`（**seed**：每个 candidate 至少一条 `C`，`status: ungrounded`） | `phase-r3-r6-discovery.md` |
| **R4** Isolated Populations | `hypotheses` | `hypotheses[].status`（**QD archive 精修：重排 elite 归属**） | `phase-r3-r6-discovery.md` |
| **R5** Co-evolving Retrieval | `hypotheses` | `literature` / `evidence`(kind=literature) | `phase-r2-r5-field-mapping-retrieval.md` |
| **R6** | `hypotheses` / `uncertainties` / `failures` | `hypotheses[].generation` / `hypotheses[].status` / `hypotheses[].operator` / `hypotheses[].parents` / `failures` / `known_flaws`（把新 `F` 挂上） | `phase-r3-r6-discovery.md` |
| **R7** | `claims` / `evidence` / `assumptions` / `hypotheses` | `assurance` / `failures` / `uncertainties` / `known_flaws`（把新 `F` 挂上） | `phase-r7-r10-r13-assurance-repair-review.md` |
| **R8** Evidence Contract | `claims` / `evidence` / `assurance` | `claims[].contract` / `claims[].status`（**仅证据驱动的单向升级**：`ungrounded` → `partially-supported` / `supported`） / `evidence` / `claims[].supporting_evidence` / `refuting_evidence` / `uncertainties` / `experiments`（**创建 `planned` 条目 + 冻结 `preregistration`**） | `phase-r8-evidence-contract.md` |
| **R9** | `uncertainties`(critical, high 且 high) / `claims` | `experiments`（**执行**）/ `experiments[].status` / `experiments[].result_at_state_version` / `assurance[].discriminating_test` / `failures` / `known_flaws`（把新 `F` 挂上） | `phase-r9-r11-experiment-loop.md` |
| **R10** Metacognitive Repair | 全 state + artifact | `repairs` + **执行 `state_delta`** | `phase-r9-r11-experiment-loop.md` |
| **R11** Update World Model | 全 state | 归并去重 + **失效传播至不动点** + `state_version` +1 + 跑 `state_check.py` | `phase-r9-r11-experiment-loop.md` |
| **R12** Narrative | `claims` / `evidence` / `failures` / `uncertainties` | `narrative_view`（+ 必要时新增 `uncertainties`） | `phase-r12-narrative.md` |
| **R13** | 全 state + artifact | `reviews` / `failures` / `experiments[].unexpected` / `known_flaws`（把新 `F` 挂上）；缺口**必须**交 R10 | `phase-r7-r10-r13-assurance-repair-review.md` |
| **R14** Decision | 全 state + 未闭环 `repairs` | `decision` / `repairs[].closure` / `uncertainties[].status` / `hypotheses[].status`（**不含 `claims[].status`** —— `killed` 只能经 R10） | `../SKILL.md` §4「R13 / R14」 |

> **补充说明（不参与逐字比对）：** 上表读/写列与 `SKILL.md` §0、各 `phase-*.md` 的
> 「读 / 写 World Model」表**必须逐字相同**；下面保留各阶段的细节语义，供执行时理解，
> **不得**把它当成第二套口径。
>
> **`P3` 的骨架不进 state** —— 它写 `.research-idea-pipeline/routes/<R>/populations/intermediates/`
> （search artifact；见 [phase-r3-r6-discovery.md](phase-r3-r6-discovery.md) §R3.0.1）。
>
- **R0**：读 用户输入、路线 `README.md` / `STATUS.md` / `INDEX.md`、续跑时的既有 state；写 **只有 `contract`**：`goal` / `primary_anchor` / `constraints` / `resources` / `provisional_anchor_rationale` / `out_of_scope`。**R0 不产出 `claims[]`，也不写 `assurance[]`**（`assurance[]` 由 **R7** 写：kill condition 是对具体 attack 的回应，R0 期还没有 claim/attack，写了只能是空话）
- **R2**：读 `literature[]`、`assumptions[]`、`uncertainties[]`、`claims[]`（只读，用于定位缺口）；写 `literature[]`、`evidence[]`(kind=literature)、`assumptions[]`、`uncertainties[]`（缺口类主张先落 `U`，由 R3 转成 `C`）
- **R3**：读 `literature[]`、`assumptions[]`、`failures[]`、`contract.constraints`；写 `hypotheses[]`、**`claims[]`（创建 seed）**。**只给 candidate 建 `H` / `C`**；`P3` 的 typed intermediate 写 `.research-idea-pipeline/routes/<R>/populations/intermediates/`，**不进 state**（与上表逐字一致）
- **R4**：读 `hypotheses[]`；写 `hypotheses[].status`（**QD archive 精修：只能重排 elite 归属**）。**`niche` / `operator` / `parents` / `generation: 0` 由 R3 创建时写入，R4 不得新建 niche**（与上表逐字一致）
- **R5**：读 `hypotheses[]`；写 `literature[]` / `evidence[]`(kind=literature) —— **由当前候选反向决定下一轮 query**
- **R6**：读 `hypotheses[]`、`uncertainties[]`、`failures[]`；写 `hypotheses[].status`（`active` / `elite` / `archived` / `killed`）、`expected_information_gain` 更新、`failures[]`（被搁置的假设记 `kind: deprioritized`）、`uncertainties[]`（收敛或新增）
- **R7**：读 `claims[]`、`evidence[]`、`assumptions[]`、`hypotheses[]`；写 `assurance[]`（`kill_condition`、`discriminating_test`）、`failures[]`（攻击暴露的缺口）、`uncertainties[]`。**首轮（R8 之前）审的是 R3—R6 落盘的 seed `claims[]` / `hypotheses[]` / `assumptions[]`** —— 此时还没有 `claims[].contract`；**第二轮起**才审契约。两个时点都**不得**要求 artifact 审计（spec §5）
- **R8**：读 `claims[]`、`evidence[]`、`literature[]`、`assurance[]`；写 `evidence[]`（`epistemic_status` 定档、`kind`、`strength`、`scope`、`source_ref`、`supports` / `contradicts`）、`claims[].supporting_evidence` / `refuting_evidence` / `scope`、`uncertainties[]`（缺失证据 → `U` 条目，`cheapest_discriminating_test: TBD` 起步）
- **R9**：读 `uncertainties[]`（`importance ∈ {critical, high}` 且 `uncertainty: high`）、`claims[]`、`evidence[]`；写 `experiments[]`（全字段；`parent` 建树、`stage` 六段、失败实验 `status: failed` **仍留在** `experiments[]`）、`failures[]`、`assurance[].discriminating_test` 指向新 `X`。排序**必须**写出：改哪条 `U`、预期改变方向、成本口径（EIG，spec §4）
- **R10**：读 全 state + artifact（code / logs / failed runs）；写 `repairs[]`（`flaw` / `disposition` / `state_delta` / `closure` 齐备），并**立即执行 `state_delta`**：改 `claims[].status` / `scope` / `known_flaws`、`experiments[].status`、`uncertainties[].status`、`hypotheses[].status`。一致性审计链 `Claim ↔ Method ↔ Code ↔ Result ↔ Conclusion`
- **R11**：读 全 state；写 把 R2—R10 的增量**归并**成一份一致 state：去重、ID 永不复用、`TBD` 要么消掉要么保留并挂 `U`；跑 `state_check.py`，退出码非 `0` **不得**进入 R12
- **R12**：读 `claims[]`、`evidence[]`、`literature[]`、`assurance[]`、`uncertainties[]`；写 默认**零写入**（叙事是视图，不是 artifact）；仅当叙事暴露新缺口时新增 `uncertainties[]`（`status: open`）。**不得**新增 `evidence[]`，**不得**提高既有条目的 `epistemic_status`
- **R13**：读 全 state + artifact（code / logs / failed runs）；写 `reviews[]`、`failures[]`（`failed-to-reproduce` / `engineering-failure` / `inconclusive`）、`experiments[].unexpected` / `interpretation`；`assurance[]` **不归 R13**（归 R7）；缺口**必须**交 R10 落成 `repairs[]`，**不得**只写进 review
- **R14**：读 全 state + `repairs[]` 未闭环项；写 `repairs[].closure`（`RESOLVED` / `ACCEPTED_LIMITATION`）、`uncertainties[].status`（`closed`）、`hypotheses[].status`；**不写 `claims[].status` —— `killed` 只能经 R10**；`ACCEPTED_LIMITATION` **必须**同时写进 `C.scope` 或 `C.known_flaws`。决策 `continue` / `pivot` / `archive` / `submit` 回 R3 / R9（与上表逐字一致）


**公共字段的写授权（补 MINOR-2）：** `depends_on` / `validity` 是八类对象的**公共必填字段**，
`verification_tier` 是 `evidence` / `assurance` 的必填字段。**创建或更新某对象时，
该对象的这些必填字段随对象一并授权写入** —— 不必在写表里逐格列出（写表列的是**对象与语义字段**，
不是每一条子字段）。**未创建该对象的阶段仍然不得单独修改它们。**

**读写的四条硬规则：**

1. **写回是收工条件。** 任何阶段**不得**在未写回 state 的情况下宣告完成；「结果只在对话里」
   等于没有结果（与 [claim-first-policy.md](claim-first-policy.md) §6 规则 5 的落盘纪律一致）。
2. **只写本阶段的行。** 表中未列出的字段**不得**顺手改（例如 R9 **不得**直接改 `claims[].status`
   ——那是 R10 / R14 的处置权限）。跨阶段修改**必须**走 `repairs[].state_delta`。
3. **状态迁移只能取枚举值。** 任何「部分支持但还没定」的中间态**必须**落到枚举里最接近的一个
   （如 `partially-supported`），**不得**自造 `mostly-supported` 这类值。
4. **认识论权限边界（硬 invariant）。** **R14 能杀研究分支，不能杀真理主张** ——
   `claims[].status` **只能**经 R8（证据驱动）或 R10（`state_delta`）改变；
   **R14 的写集合永不含 `claims[].status`**。停一个 hypothesis / 停一条路线是**资源决策**，
   不是**真值判决**。完整定义见 [../SKILL.md](../SKILL.md) §1.7。

---

## 6. 与既有权威文件的接口

**结论：本文件只管 state；claim 语义、措辞等级、落盘路径、评分与门禁各自由既有权威文件定义，本文件只定义接口。**

| 既有权威文件 | 管什么 | 与 state 的接口（**不得**越界重复定义） |
|---|---|---|
| [claim-first-policy.md](claim-first-policy.md) §2 / §3 | claim / evidence 语义、`epistemic_status`、`Ci ← Ej` | `claims[]` / `evidence[]` 承接其语义：`C0—C5` 的槽位含义、`E<n>` 路线内唯一不复用。`Ci ← [待补]` 在 state 里的落地 = `supporting_evidence: []` + `status: ungrounded` + 一条对应的 `uncertainties[]` |
| [evidence-policy.md](evidence-policy.md) §1 / §3 | 五级措辞等级与 ↔ `epistemic_status` 映射 | `evidence[].epistemic_status` 五值 ↔ 措辞等级**一律**查该文件 §3；state **不得**新增措辞等级，**不得**让 `Supported` 直接等于「已核实」 |
| [narrative-patterns.md](narrative-patterns.md) §4 | 迁移举证等级 `L1 / L2 / L3` | 与 `literature[].id` **无关**；该等级**不得**占用 `LIT` 之外的 `L` 前缀（§2.1） |
| [literature-policy.md](literature-policy.md) §3.2 | 检索尽职调查等级 `L1 / L2 / L3` | 同上：检索等级写进项目文档与检索记录，**不写进** `literature[]` 的 ID |
| [scoring-policy.md](scoring-policy.md) §3 / §4 | `G1—G5` 门禁、六维排序 | 门禁与排序**读** state：`claims[].supporting_evidence`（`G1`）、`literature[].relation` 与最近前作（`G2`）、`evidence[].epistemic_status`（`G4`）、`hypotheses[].niche` / `experiments[].stage`（实验设计质量）。**state 只存事实与状态，不存评分**；门禁 `fail` 的后果**必须**回写成 `repairs[]` / `claims[].status` / `failures[]`，**不得**只停留在评分表里 |
| [project-layout.md](project-layout.md) §6（落盘三档）/ §3.1（正文禁令） | 落盘路径与「什么不得贴进正文」 | 机器状态 → `.research-idea-pipeline/routes/<R>/research-state.json`（**常驻、就地覆盖**：每轮只保留一份当前 state；过程快照若需要，放 `.research-idea-pipeline/routes/<R>/` 下的中间产物档）。交付物仍在 `routes/<R>/docs/`；**不得**把 state / 原始 JSON 贴进正文（该文件 §3.1 的既有禁令） |
| [../SKILL.md](../SKILL.md) §1.6（本轮新增） | 「critical flaw ⇒ state change」不变量 | 本文件 §1 硬规则 2 与 §3.9 是它的执行细则；两处措辞**必须**一致 |
| [../scripts/state_check.py](../scripts/state_check.py) | S1—S7 与 V1—V24 的机械强制 | §4.0 / §4.1 的规则表是该脚本的契约；命令、`--json`、退出码以脚本 `--help` 为准 |
| [../templates/research-state.template.json](../templates/research-state.template.json) | state 骨架与示例条目 | 模板**必须**通过 S1—S7 与 V1—V24（spec §7 验收）；模板里的占位值**不得**被当作真实实验结论引用 |

**维护规则：**

1. 节号 `§1—§6` **冻结**。新增或移动节属于破坏性变更，**必须**同轮更新本节与全部引用点，
   并在 spec 的变更记录里记一行。
2. 引用本文件时**必须**写 `research-state-policy.md §N`，**不得**只写「见 state 政策」。
3. §2 的 ID 前缀、§3 的字段与枚举、§4.0 的 S1—S7、§4.1 的 V1—V24 一旦改动，**必须**同轮扫三处：
   `state_check.py`（规则实现）、`research-state.template.json`（骨架）、全部 `phase-*.md`
   （读写时机），**不得**只改一处。

### 3.10 `contract`（R0 写入，之后只读）

**`contract` 不是「第八类之外的可选字段」，它是 R0 的唯一产物。** 字段逐字：

| 字段 | 必填 | 说明 |
|---|---|---|
| `goal` | ✅ | 用户研究目标**原话**，不得替其改写 |
| `primary_anchor` | ✅ | 锚点枚举（英文原样），见 `../SKILL.md` §0.1 |
| `constraints` | ❌ | 时间 / 算力 / 数据 / 伦理合规 |
| `resources` | ❌ | 已有代码、数据、模型、合作者 |
| `provisional_anchor_rationale` | ✅ | 为什么现在先按这个锚点走（给 R1 的 Anchor Eligibility 复核用） |
| `out_of_scope` | ✅ | **写不出「不做什么」= 边界没想清** |

**硬规则：** `contract` 期的主锚点是 **provisional（暂定）**，不是决定。
证据到位后由 R1 的 Anchor Eligibility Test（[claim-first-policy.md](claim-first-policy.md) §6）复核；
若证据不支持用户偏好的锚点，**必须显式告知**。改主锚点只能由用户授权（走锚点变更单）。
**R0 不得产出 `claims[]` 条目**；`assurance[]` 由 R7 写。

### 3.11 附加槽位（与八类对象同级或挂在对象下，全部已在模板中占位）

**⚠️ 更正：本节列出的槽位是 R 阶段的落盘目标，模板与 `state_check.py` 都**不拒绝**它们**
**（`state_check.py` 忽略未知键；S1—S7 只校验本表已登记槽位的形状 —— 新增槽位必须同轮登记，否则形状不受保护）。

旧表述「不得自加字段」的**准确含义是**：**新加字段必须同时改本表、模板与 `state_check.py`**，
而不是「只准用八类对象」。

| 槽位 | 位置 | 谁写 | 用途 |
|---|---|---|---|
| `contract` | 顶层对象 | R0 | 研究契约（见 §3.10） |
| `claims[].contract` | 挂在 claim 下 | R8 | 该 claim 的证据契约（Statement/Scope/Kill rule/…） |
| `narrative_view` | 顶层 | R12 | 叙事视图；**不是独立 artifact**，失败实验必须在其中保留 |
| `reviews` | 顶层 | **R13**（R7 只产出 `assurance`，不写 reviews） | artifact-aware 审查记录（含 integrity gate 判定） |
| `decision` | 顶层 | R14 | `continue` / `pivot` / `archive` / `submit` |
| `assurance` | 顶层 | **R7** | attack 与 kill condition（**R0 不写**） |
| `repairs` | 顶层 | R10 | 修复三元组（V10 强制） |

### 3.12 人读措辞 → 冻结枚举（映射表，**不是第二套枚举**）

**结论：日常科研措辞（verified / falsified / REFORMULATE / 「移除假设」这类说法…）不得直接写进 state 字段；
必须按本节的映射落到 §3 的冻结枚举上。本节只做**翻译**，不新增任何合法取值。**

**为什么需要它：** 这类措辞**不是一个枚举**——它们混用了「证据的认知状态」「claim 的状态」
「失败记忆的类型」「修复处置」四个不同对象的字段。塞进同一个字段会**同时**违反 V3 与 V5。

#### 3.12.1 证据 / claim 状态措辞

| 日常措辞 | 落到哪个对象的哪个字段 | 合法取值 |
|---|---|---|
| verified（直接观测到） | `evidence[].epistemic_status` | `Observed` |
| verified（有支持但非直接观测） | `evidence[].epistemic_status` | `Supported` |
| partially supported | **`claims[].status`** | `partially-supported` |
| supported | **`claims[].status`** | `supported` |
| unsupported | **`claims[].status`** | `ungrounded` |
| falsified | **`claims[].status`** + `failures[]` | `contradicted` + `kind: falsified` |
| inconclusive | `evidence[].epistemic_status` / `failures[].kind` | `Unknown` / `inconclusive` |
| needs verification | `evidence[].epistemic_status` | `Hypothesized` 或 `Planned` |

> ⚠️ `evidence[].epistemic_status` 与 `claims[].status` 是**两个不同字段的两套枚举**。
> 把 `partially-supported` 写进 `epistemic_status` 违反 V5；把 `Supported` 写进 `claims[].status` 违反 V3。

#### 3.12.2 claim 分层措辞（**不是枚举**，是 claim 树的形状）

| 日常措辞 | state 落点 |
|---|---|
| central claim | claim 树根：`parent: null`；`C0—C5` 图式见 [claim-first-policy.md](claim-first-policy.md) §3 |
| supporting claims | 根的 `subclaims[]` 指向的子 claim |
| mechanism claim | 子 claim，`statement` 描述机制；**必须过 Minimal Explanation Test**（R7 的 `A-Minimal`） |
| empirical claim | 子 claim，其支持证据 `kind: experiment` / `observation` |
| theoretical claim | 子 claim，其支持证据 `kind: theory` |

#### 3.12.3 R10 处置措辞

| 日常措辞 | 冻结落点 |
|---|---|
| `run_test` / `fix_implementation` / `repair_claim` | 同名 `disposition`：`RUN_TEST` / `FIX_IMPLEMENTATION` / `REPAIR_CLAIM` |
| `narrow_claim` | `disposition: NARROW_SCOPE` |
| `kill_hypothesis` | `disposition: KILL_BRANCH` |
| `reformulate` | **无同名值** → `disposition: REPAIR_CLAIM`，并在 `state_delta` 改写 claim 的 `statement` / `scope`；若属路线级改向，另开 `uncertainties[]` 交 R6 `mutation` |
| `pivot_proposal` | **无同名值** → 这是 **R14 的 `decision: pivot`**，不是 R10 处置；R10 用 `KILL_BRANCH` + `state_delta` 收掉旧分支 |
| `accept_limitation` | **它是 `closure`，不是 `disposition`** → `closure: ACCEPTED_LIMITATION`，并同步写 `C.scope` 或 `C.known_flaws` |

#### 3.12.4 niche 描述性概念 → `N1`—`N10`

| 描述性 niche 概念 | `hypotheses[].niche` |
|---|---|
| 新问题 / 新设定 | `N1` |
| 移除假设 / 瓶颈突破 | `N2` |
| 跨域理论迁移 | `N3` |
| 现象发现与解释 | `N4` |
| 统一框架 | `N5` |
| 效率 / 可行性 | `N6` |
| 鲁棒性 / 泛化 | `N7` |
| 评测反转 / 基准改造 | `N8` |
| 矛盾解决 | `N9` |
| 不可能性 / 负结果 | `N10` |

> ⚠️ **任何英文描述性 niche 名（含旧名与新造名）都不得写进 `hypotheses[].niche`** ——
> V6 只收 `N1`—`N10`，旧描述性名已登记在 [deprecated-terms.txt](deprecated-terms.txt)。
> 本表左列刻意只用**中文概念**，就是为了不把废弃原文再写进正文。
> 高风险范式类候选按**实际改写的对象**取 `N1`（改写 formulation）或 `N10`（改写 boundary）。
