# Skill-Level Recursive Self-Improvement（Skill-RSI）

> **渐进加载：** 只有需要「从真实科研经验改进科研策略」时才读本文件。它不替代
> [scheduler-policy.md](scheduler-policy.md)、[discovery-replay.md](discovery-replay.md)、
> [cognitive-memory-policy.md](cognitive-memory-policy.md) 或
> [scientific-value-adaptive-discovery.md](scientific-value-adaptive-discovery.md)，
> 而是在它们的既有边界内补上策略记忆、反事实回放、策略晋升与源码冻结四件事。
>
> 本文件**不是**第 16 个阶段，**不是**第九类 canonical 对象，**不是**第二个 CIE。

## 0. 一句话

科研事实仍由既有科学证据机制裁决；只有**科研策略**可以在受控、可审计、可回滚的范围内演化。

```text
Research Experience → Policy Hypothesis → Replay Evaluation → Controlled Adaptation
        → New Research Experience
```

## 1. 硬边界（优先于本文件其余全部内容）

1. **不改 Harness**：不动基础模型、推理协议、原生 Agent 调度、平台工具接口与权限模型。
2. **不改科学架构**：R0—R14、八类 canonical 对象、Discovery/Assurance 双循环、四个语义入口、
   16 个 Preset、Scheduler 八级硬优先级、PEIG/AALG、Evidence Qualification、预注册全部不变。
3. **不新增 canonical 对象或字段**：新增数据全部落 route 控制平面（telemetry / 派生存储）。
4. **运行期不得自主改 Skill 源码**：`SKILL.md`、`references/`、`presets/`、`scripts/`、
   `templates/`、`schemas/`、`preset-registry.json`、`shared-contract.md`、
   校验器、评分规则、隐藏评价数据、权限定义、发布元数据都是**只读**对象。
5. **不得伪造结果**：历史没有执行过的行动分支只有 `NO_SUPPORT`，不能用模型预测代替真实实验。
6. **不得把系统自评当能力提升**：日志数量、文档数量、状态变化、自评分数都不构成 Delta。

## 2. 三层记忆必须分开

| 层 | 载体 | 回答的问题 | 不能做什么 |
|---|---|---|---|
| Scientific Memory | canonical `research-state.json` + `cognition/` 投影 | 世界的科学事实是什么 | 不得被策略经验覆盖 |
| Decision Experience | `<route>/decision-trajectory.jsonl` | 当时可见什么、选了什么、实际发生了什么 | 不是科学证据，不得写入 `evidence[]` |
| Policy Memory | `<route>/policy/` | 哪类问题结构下哪种策略更好 | 不得否证或支持任何科学主张 |

「某探索算子在三个项目里失败」是策略经验；「某机制被实验否证」是科学事实。前者不能推出后者。

## 3. Decision Trajectory（`scripts/decision_trajectory.py`）

路径：`<route>/decision-trajectory.jsonl`，append-only、哈希链、`head` 摘要、`flock` + `fsync`。
只记录**对后续科研行为有实际影响**的重要决策。

一条轨迹由四类记录组成（同一 `trajectory_id`）：

| 记录 | 关键字段 |
|---|---|
| `decision` | `context`（state_version / contract 引用 / 科学问题 / 活跃假设 / 关键不确定性 / 可见证据 / 停止规则 / `decided_at` / `state_digest` / `scheduler_digest`）、`decision`（候选集 / 前置条件 / 优先级 / EIG÷cost / 选择 / 策略版本 / 是否改变排序 / `dispatch_status`）、`prediction`（可空，决策时冻结） |
| `outcome` | `observed_at` / `at_state_version` / `result` / `evidence_refs` / 三类 Delta / `policy_effect_observed` / 成本 / 未解决问题 / `evidence_qualification` |
| `learning` | `learning_value` / `bias_hypothesis` / `applicability` / `counterexamples` / `needs_validation` |

机械规则（`DT0`—`DT10`）：`DT0` 链完整性（含尾部）、`DT1` 结构、`DT2` 已记录决策不得被改写
（比较**决策语义**：被选动作与冻结上下文；调度器候选集变化属于重新观测，不是改写）、
`DT3` 来源引用必须存在、`DT4` 过期状态与时间倒挂、`DT5` 事后补写预测、
`DT6` 结果泄漏进冻结上下文、`DT7` 轨迹/策略存储不得作为科学证据来源、
`DT8` 同一 `state_version` 下同一行动不得改名重复派遣、`DT9` 未合格证据不得声称科学增量、
`DT10` route 绑定。

命令：`open` / `outcome` / `learning` / `show` / `list` / `validate` / `--selftest`。

[AI-gen] `validate` 按写入顺序检查历史记录。每条记录只读取此前的账本前缀。
当前记录及后续记录不计入此前记录。`open` 仍严格拒绝过期状态。
提供 `--state` 时，同版本决策核对当前摘要；旧版本只核对现存来源引用。
旧版本不会与当前摘要混比，也不因此获得历史快照认证。
输出 `historical_state_bindings_unverified` 列明未认证的旧版本决策。
未提供 `--state` 时，`state_binding_scope` 为 `not_checked`，不认证状态绑定。

## 4. Counterfactual-Aware Replay（`scripts/research_replay.py`）

### 4.1 三类历史决策

| 证据等级 | 含义 | 允许的评价 |
|---|---|---|
| `OBSERVED` | 行动与其结果都被真实观测 | 可按实际结果评价 |
| `REPLAY_SUPPORTED` | 行动存在于历史已执行分支，在覆盖范围内 | 可在该范围内比较不同策略，决策时点信息必须一致 |
| `NO_SUPPORT` | 候选策略选择了历史未执行的行动 | **不得评价、不得晋升**；需要真实验证只能进入受控试验 |

### 4.2 防泄漏（在 `RP2` 之外）

- `RP6` 时间边界：可见文献不得晚于决策时间。
- `RP7` 文件系统：case 目录下可读文件、越界符号链接、项目认知投影都不得含隐藏答案。
- `RP8` 认知记忆：召回投影不得携带后续观测。
- 无法建立隔离时，`require_isolation` 直接拒绝该 case 的独立评价资格。

### 4.3 消融

原有四臂（`baseline` / `memory_only` / `memory_prediction` / `full_cie`）**语义冻结**；
Skill-RSI 追加 `rsi_full` / `rsi_shadow` / `rsi_without_trajectory` / `rsi_without_replay` /
`rsi_without_scope` / `rsi_without_promotion`，用于逐个隔离机制而不是堆叠能力。

命令：`ablate --rsi`、`support --trajectory`、`coverage --trajectory`、`validate --dir`。

## 5. Policy Candidate（`scripts/policy_evolution.py`）

### 5.1 允许调整的策略面

- 探索算子的相对偏好（`exploration_operator_preference`）
- 已定义探索菜单的选择（`menu_choice`）
- 同一合法优先级层内的动作排序（`same_tier_preference` / `same_tier_order`）
- 给定问题结构下的策略适用性（`applicability`）
- 候选探索顺序（`probe_order`）
- 保持探索下限的局部资源分配建议（`local_resource_allocation`，必须 `keep_exploration_floor: true`）

不得改变：Scheduler 八级硬优先级、`EIG ÷ cost` 固定判定、执行门禁、Evidence Qualification、
AALG 诊断预算、Research Contract、主研究锚点、GPU 授权、已冻结实验计划、核心评价标准。

### 5.2 候选结构

`policy_id` / `policy_schema_version` / `parent_policy_id` / `status` / `scope` /
`applicable_conditions` / `strategy_changes` / `supporting_trajectory_ids` / `counterexamples` /
`expected_effect` / `revalidation_conditions` / `evaluation_refs` / `rollback_target`。

机械规则：`PE1` 结构、`PE2` 越权目标、`PE3` 作用域必填且结构化、`PE4` 依据必须来自有真实
结果的轨迹、`PE5` 复杂度与 fixture 过拟合、`PE6` 可执行内容、`PE7` 自评字段、`PE8` 泛化需反例、
`PE9` 同一机制失败上限（换 `policy_id` 无效）、`PE10` 非法状态转移、`PE11` 晋升证据不足、
`PE12` 评价规则被改动、`PE13` 回滚目标非法、`PE14` 局部成功不得升级为全局策略、
`PE15` 缺少人工批准或信任边界不成立（批准绑定不可为空、账本不可篡改）、
`PE16` 两臂对照不公平（受控轴不一致、对照轴无差异、执行实例相同、配对任务不符）。

策略数据不得包含可执行代码、Shell 命令、动态导入路径。自由文本只用于解释，永远不作为指令执行。

### 5.3 生命周期

```text
PROPOSED → SHADOW → REPLAY_EVALUATED → BOUNDED_TRIAL → VALIDATED → ACTIVE
失败：REJECTED / HOLD / ROLLED_BACK        取代：SUPERSEDED
```

- 这些状态只存在于策略控制记录，**不是**科学状态枚举。
- 评价规则在候选生成前冻结（`policy/evaluation-rules.json`）：读取时**重算** digest 并与存储值
  比对，不一致即视为被改写（fail closed）；候选在生成时绑定该 digest，评价时再次核对。
- 性能差异落在容差内或区间重叠时报告**不可区分**，不强行选胜者。
- 回滚恢复上一有效策略、保留完整失败轨迹、不改既有实验结果、不重置 AALG 或其他预算、
  不动 canonical Research State。
- **整个生命周期转换在策略存储锁内原子执行**：校验、追加、supersede 与快照是同一临界区，
  两个并发晋升不会产生两个 ACTIVE 或错误的 supersede。

### 5.3.1 晋升只能经受控入口，且必须有评价产物

`REPLAY_EVALUATED`、`BOUNDED_TRIAL`、`VALIDATED`、`ACTIVE` 是**受控目标**：

- `transition --to <受控目标>`（以及任何直接调用 `transition()`）一律拒绝，
  必须使用受控入口：`evaluate`（回放，L2 上限）/ `trial`（试运行）/ `validate-research`
  （L3 真实科研验证凭证）/ `approve-l3`（人工批准）/ `validate` / `promote`。
- 调用方自述的 JSON 布尔字段（`independent`、`distinguishable`、`sample_adequate` …）
  **不构成晋升证据**；这些门由入口从评价产物重新计算。
- 每个受控入口把评价产物写入 `<route>/policy/evaluations|trials/<policy>.<digest>.json`，
  并在转换记录里只留下对产物的**引用**。产物必须满足：

  | 要素 | 要求 |
  |---|---|
  | 明确来源 | 产物路径规范化后必须位于策略存储目录内（拒绝越界/符号链接逃逸） |
  | 完整性摘要 | `digest` 由产物内容重算并比对；引用声明的摘要也必须一致 |
  | 策略版本绑定 | `policy_id` + `policy_signature` + `policy_schema_version` 必须匹配当前候选 |
  | 冻结评价规则 | 产物记录的 `rules_digest` 必须等于当前重算规则 digest，且等于候选绑定的版本 |
  | 可信执行记录 | 报告必须带 `schema`、逐 case 的 `results`（含 `leak_checked`/`isolation_verified`）与具名 `runner`；否则不是评价证据 |
  | 证据等级 | 等级由产物的门与结论**重算**，不接受产物自报；各目标要求 L2 / L3 |

- **凭证类别决定等级上限**（合成证据不得冒充真实科研证据）：

  | 凭证 | 产出入口 | 等级上限 |
  |---|---|---|
  | 回放凭证 `policy-evaluation@1` | `evaluate`（Replay） | **L2** |
  | 试运行派遣记录 `policy-trial@1` | `trial` | L2 |
  | 真实科研验证凭证 `policy-research-validation@1` | `validate-research` | **L3** |

- 等级由产物的门与结论**重算**：回放凭证在 `SUPPORTED` 且可评维度 ≥2、`runs ≥ min_runs`、
  `cases ≥ min_cases`、有具名 `runner` 时为 L2，**永远不是 L3**；真实科研验证凭证还需
  `provenance_ok && independent_ok && dispatch_bound` 才是 L3。
- `VALIDATED` / `ACTIVE` 只接受**真实科研验证凭证**。回放凭证出现在这两个位置会被
  `PE11` 拒绝（凭证类别不可互换）。
- 真实科研验证凭证的要求：`task_provenance.synthetic` 必须显式为 `false`，任务来源文件必须
  存在、摘要匹配且不在示例/合成目录；`execution_evidence` 必须存在且摘要匹配；候选臂与对照臂
  必须有**不同**的 `executor`（且不得是策略自身/自身路由）；每个 case 必须显式
  `isolation_verified=true`；`dispatch_ref` 必须指向该策略**最近一次实际派遣**的试运行记录，
  且该记录**未被其他 L3 凭证使用**；受益结论用候选绑定的冻结规则重算。

### 5.3.1.1 信任边界：文件完整性 ≠ 证据真实性 ≠ 评价独立性

三件事必须分开申报，且**只有第一件是可机械验证的**：

| 维度 | 含义 | 本系统的能力 |
|---|---|---|
| 文件完整性 | 来源文件与摘要一致、凭证未被改写、批准账本未被篡改 | **可验证**（`PE11`/`PE12`）|
| 证据真实性 | 外部真的在真实任务上执行过 | **不可验证**：`synthetic=false`、`executor` 名称都是声明 |
| 评价独立性 | 评价者与策略作者彼此独立 | **不可验证**：只能检查「不是策略自身」 |

因此：**运行中的 Research Agent 不得仅凭自己生成的文件、标记、摘要和引用自主获得 L3。**
`VALIDATED` / `ACTIVE` 在 `PE15` 下**要求人工批准**：批准由 `approve-l3` 写入一条密封的
批准记录（复用 `experiment_execute.Ledger` 的 HMAC 封印与单次使用语义），绑定**该凭证的内容摘要**、
策略签名与冻结规则摘要，并带批准者身份与有效期。任何自动入口都不写批准记录；
晋升时会**重新**校验该记录仍然存在、未过期、未被篡改。

**必须如实声明的限制：** 这是**协议级人工门**，不是密码学证明。Skill 无法独立确认批准者
是人；拥有路由写权限者可以伪造批准记录。因此本系统**不声称具备自动可信晋升**，
在没有真实科研 A/B 时 **L3 一律标记为未验证**。

### 5.3.1.2 对照公平性（`PE16`）

每次 L3 评价必须留下可复核的对照记录 `equivalence`：

- **受控轴**（两臂必须相同）：`model`、`harness`、`tools`、`visible_data`、`budget`、`task_ids`；
- **对照轴**（必须显式声明且确实不同）：例如 `strategy`；
- **未声明的环境差异一律拒绝**（与 `execution_gate` 的 "undeclared changed variable" 一致）；
- **执行实例身份**（`instance`）两臂必须不同（证明是两次独立执行），
  **执行环境**在受控轴上必须一致（证明对照公平）；
- `paired_task_ids` 必须与逐 case 执行记录一致；预算与策略版本随凭证一并留存。

### 5.3.2 收益方向：DIFFERENT ≠ BETTER

- 评价按维度给出 `direction`（`BETTER` / `WORSE` / `NONE`）与 `confident`，
  容差取自**候选绑定的冻结规则**（不是编译期默认值）。
- 只有**预先定义的收益维度**（`search_efficiency` / `stagnation_recovery` /
  `memory_accumulation`）出现 `BETTER` **且 `confident`**（两臂区间不重叠），
  且**科学可靠性维度**（`mechanistic_understanding` / `prediction_quality` /
  `intervention_quality` / `scientific_novelty`）没有 `WORSE`，才可能得到 `SUPPORTED`。
- 区间重叠的“收益”只记录为不确定性（`uncertain_benefit`），**不计入晋升**：
  声明的 caveat 必须在晋升逻辑里真正生效。

### 5.3.3 报告必须能从执行记录重算

- 报告的 `per_arm[*].dimensions` 会与 `per_arm[*].results[*].evaluation.metrics`
  **重新计算**的结果逐项比对；声明的 mean/min/max 与记录不符即 `INVALID`。
- `cases`/`runs_per_case` 必须与实际记录数与 case 集合一致。
- 每个 case 必须显式给出 `leak_checked=true` 与 `isolation_verified=true`；
  **缺失不再默认为通过**。
- 报告若声明 `policy_id`/`policy_signature`/`rules_digest`，必须与候选及冻结规则一致；
  未声明的由受控入口绑定，并记录 `binding_source`。
- 晋升时会对产物内嵌的报告**再次重算结论**，与产物记录的结论不一致即拒绝。
- 样本不足 → `INSUFFICIENT_SAMPLE`；未观测（`NO_SUPPORT`）→ `INSUFFICIENT_COVERAGE`；
  没有任何收益维度正向改善 → `UNDIFFERENTIATED`；可靠性退化 → `REJECTED`。
- 非收益、非可靠性维度退化单独报告，不允许用某一维度的收益补偿科学可靠性或证据资格的退化。

### 5.4 真实消费者

晋升后的策略只通过**现有 Strategy Decision Adapter**生效：

```text
policy/ 中 ACTIVE 候选 → advice_from_active_policy() → strategy_memory.strategy_decision()
    → 同一 EIG÷cost 层内重排（只重排已通过硬门禁的动作）→ research-loop 的实际派遣
```

`research-loop` 优先采用该选择；选择无法实施时如实报告 `reason_if_not`，不制造差异。
策略是否被实际派遣记录在决策轨迹与 `scheduler.strategy_decisions[]` 中。

## 6. 三类 Delta

| Delta | 含义 | 不算 Delta 的东西 |
|---|---|---|
| `scientific_delta` | 新的合格科学证据、有效认识或明确科学边界 | 日志、文档、投影刷新 |
| `decision_delta` | 真正改变了候选、实验、方法、资源或终止决定 | 主观自评提高 |
| `policy_delta` | 有来源、有作用域、带评价等级的策略变化 | 仅「提出候选策略」 |

`policy_delta` 必须携带 `level`（L1/L2/L3）；三者均可为 `none`。

## 7. 等级不得混淆

- **L1 实现有效性**：格式、权限、代码测试与不变量通过。
- **L2 运行有效性**：真实 CLI / Scheduler / Replay 能消费并产生可观测的合法行为变化。
- **L3 科研改进**：在独立、未见过的真实科研案例上取得可重复且实际有价值的改善。

L2 不能推出 L3。稳定策略的 L3 主张必须经过独立真实评价；没有该条件时明确标记 L3 未验证。

**当前状态：** 本分支**没有**真实科研 A/B 评价，因此 Skill-RSI 的 L3 **标记为未验证**。
系统能够做到的是：合成回放证据**上限为 L2**；真实 L3 凭证要求人工批准、对照公平记录与
派遣记录绑定，且这些要求都可在拒绝理由中复核。系统**不能**证明批准者是人、也不能证明
外部真的执行过 —— 这两点在任何 L3 申报中都必须如实写出。

## 8. 迁移条件（`scripts/policy_transfer.py`）

迁移判断只看**声明结构**：问题结构相似性、适用假设、可用工具与资源、科学验证协议、
已知反例、历史成功的证据等级。领域关键词相似不足以判定适用。
过期经验（绑定过旧 state_version 或引用已被失效的对象）失效；被否证的机制不得再次提出。
记忆压缩不得丢失证据与停止规则。

机械规则（`PT1`—`PT11`）：`PT1` 三层记忆不得混用、`PT2` 策略不得声称科学效果、
`PT3` scope 必须结构化、`PT4` 结构不匹配不得迁移（自证签名不算证据）、
`PT5` 适用条件不满足或**不可解析**即拒绝、`PT6` 必需工具缺失、
`PT7` 验证协议不兼容、`PT8` 不得重提已被否证的机制
（含 `hypotheses[].status = killed`；匹配的是被排除的 `ruled_out` 命题）、
`PT9` 证据等级低于 scope 主张、`PT10` 已知反例覆盖目标结构
（**畸形条件 fail-closed**，不得用来抵消覆盖判定）、`PT11` 经验状态版本缺失或非法即视为过期。

**跨项目来源是必需项：** `propose()` 会为候选打上来源路由；缺少来源而当前路由已知时迁移门直接
BLOCK。用户自带正则（`op: regex`/`matches`）一律拒绝，避免 ReDoS。

## 9. Source Freeze 与写入白名单（`scripts/source_freeze.py`）

- **每次执行 Preset 都核验**（含只读诊断）：开始记录受保护文件的规范化路径与内容摘要，
  结束再核验一次；结果写入输出的 `source_integrity`。
- **审计事件只在允许写入的执行上记录**（`apply` 且该次执行确实声明了写入，或发生了违规）。
  只读请求本身不写任何文件；审计写入会在 `writes` 里声明，不做未声明的写入。
- 检测覆盖符号链接、路径别名与安装副本；越界符号链接一律拒绝。
- 只读对象：Skill 源码、Preset 协议正文、系统 Prompt、科学验证器、评分规则、测试 fixture、
  隐藏评价数据、权限定义、发布元数据。
- 可写对象：已授权的策略记忆、策略候选状态、研究项目执行账本、决策轨迹、必要运行遥测、
  以及**经既有科学阶段**合法更新的 Research State。
- 写入许可按规范化后的真实路径判定，不按文件名；`../` 与符号链接逃逸一律拒绝。
- 检测到源码被修改：立即 `HOLD`、写审计事件、停止继续应用策略；**不自动修订源码**。

> **残余风险（必须如实说明）：** 本机制是**可检查的检测与策略边界**，不是操作系统级隔离。
> 具有任意文件写权限的执行者仍可绕过它。需要真正强制时，应使用只读安装目录、
> 只读挂载、独立运行用户与安装副本摘要核验。**Prompt 层面的禁令不构成安全边界。**

## 10. 自检

- [ ] 没有新增第九类 canonical 对象或字段。
- [ ] 策略只通过 `strategy_decision()` 生效，未替换硬优先级与 `EIG ÷ cost`。
- [ ] 未执行分支返回 `NO_SUPPORT`，没有被计入任何晋升证据。
- [ ] `policy_delta` 带评价等级，未把「提出候选」写成「策略已提升」。
- [ ] 运行期没有修改 Skill 源码；生产写入全部落在白名单路径内。
- [ ] 回滚不重置预算、不改实验结果、不动 canonical state。
- [ ] 合成 fixture 与单元测试未被当作 L3 证据。
