# Research Preset Library 与 Intent Router（`PR1`—`PR10`）

> **结论：用户说人话，Router 选协议；Loop 看机器可读信号选恢复协议；自进化必须改变下一轮真实动作选择。**

**为什么需要它：** 四个语义入口（`start-project` / `continue-research` / `explore` / `audit`）解决
"从哪进"，但没有解决"进去以后按哪套协议做"。预设是**入口内部已经排练过的协议**，不是新入口、
不是新阶段、不是第二套科研事实系统。本文件是 Router、触发条件与自进化的正式政策；
`scripts/preset_router.py` 是它的机器可读实现，`presets/*.md` 是每个协议的正文。

## 1. 不变量（不得被任何预设绕过）

1. **不新增顶层入口**：预设只映射到既有四入口，`phase=R<n>` 专家入口优先级不变。
2. **`research-state.json` 仍是唯一科学权威**；投影（`cognition/`）与遥测（`scheduler.json`、
   `cognition/recovery-log.jsonl`）都不是事实来源。
3. **不得绕过证据门禁**：R8/R9.O/R10/R11、`qualify_evidence`（`PQ1`—`PQ8`）、Insight 认证
   （`IC1`—`IC6`）与 PEIG/AALG 全部照旧；预设只能**调用**它们。
4. **不得刷新 AALG 诊断预算**，不得因失败无限重启同一实验。
5. **工程故障 ≠ 科学否证**：`ENGINEERING_FAILURE_KINDS` 只用于路由与修复，永不写假设状态。
6. **处理器失败即 HOLD**：Preset 处理器无法完成（`CognitionError` / `OSError`）时返回
   `HOLD` + `PR10` 诊断，**不重试、不放宽门禁、不把工程故障写成科学否证**；调用方看到状态
   而不是 traceback。编程错误与不可恢复错误（如 `ValueError` / `MemoryError`）仍然抛出。
7. **只读预设不写 canonical**：`run` 结束会逐字节比对 canonical 摘要（违反即 `PR9` + `BLOCKED`）。

## 2. 十六个预设（`preset-registry.json` 为元数据来源）

内容包与加载顺序：`SKILL.md` → 项目 `AGENTS.md` → [shared-contract.md](../shared-contract.md) →
**选中的那一个** `presets/<id>.md` → 必要 references。`shared-contract.md` 是所有预设的共同约束
（权威、权限、证据、记忆、回报格式），**不要一次注入 16 份协议**。

| preset | 名称 | 入口 | 执行授权 | 权限层 | registry trigger | 分组 |
|---|---|---|---|---|---|---|
| `research-loop` | 自主科研闭环 | `continue-research` | `execute` | execute | `manual` | user |
| `paradigm-escape` | 范式逃逸 | `explore` | `discover_only` | discovery | `manual_or_stagnation` | user |
| `research-recovery` | 科研状态恢复 | `continue-research` | `recover_no_experiment` | derived | `manual` | user |
| `scientific-replanning` | 科学重规划 | `continue-research` | `plan` | advisory | `manual_or_blocked` | user |
| `research-audit` | 对抗审查 | `audit` | `audit` | advisory | `manual` | user |
| `research-review` | 科学进展回顾 | `continue-research` | `read_only` | read_only | `manual` | user |
| `evidence-conflict-repair` | 证据冲突修复 | `audit` | `evidence_repair` | discovery | `event_or_manual` | recovery |
| `context-drift-recovery` | 上下文漂移恢复 | `continue-research` | `recover_no_experiment` | derived | `event` | recovery |
| `memory-consolidation` | 认知记忆整合 | `continue-research` | `derived_only` | derived | `event_or_manual` | recovery |
| `resource-recovery` | 资源与执行恢复 | `continue-research` | `runtime_recovery` | derived | `event_or_manual` | recovery |
| `experiment-failure-recovery` | 实验失败恢复 | `continue-research` | `engineering_recovery` | derived | `event_or_manual` | recovery |
| `loop-health-check` | Loop 健康检查 | `continue-research` | `inspect_only` | read_only | `event_or_manual` | recovery |
| `stagnation-breaker` | 停滞打破 | `continue-research` | `decision_only` | advisory | `event_or_manual` | recovery |
| `strategy-evolution` | 策略进化 | `continue-research` | `strategy_update` | strategy | `manual_or_scheduled` | evolution |
| `hypothesis-rebalance` | 假设组合再平衡 | `explore` | `portfolio` | strategy | `manual_or_scheduled` | evolution |
| `discovery-replay` | 发现能力回放评估 | `continue-research` | `evaluation_only` | read_only | `manual_or_scheduled` | evolution |

**执行授权 vs 权限层。** 授权标签来自提供版 registry（每个标签说明这个协议实际能做什么）；权限层是
本仓库冻结的安全分级，用于"歧义取最小授权""只读不升级"等硬规则：

| 权限层 | 授权标签 | 能做什么 |
|---|---|---|
| `read_only` | `read_only` / `inspect_only` / `evaluation_only` | 只读；只落报告/派生投影，不写 canonical |
| `derived` | `derived_only` / `recover_no_experiment` / `runtime_recovery` / `engineering_recovery` | 重建投影、修复运行；不写 canonical 科学事实 |
| `read_only` | `audit` | 普通审查**默认只读**；`assurance[]` 只在显式请求时由 R7 写回 |
| `advisory` | `plan` / `decision_only` | 产出计划与决策；不改 canonical 科学状态 |
| `discovery` | `discover_only` / `evidence_repair` | 候选经 R3—R6；证据修复只经 R10/R11 |
| `strategy` | `strategy_update` / `portfolio` | 只写既有授权的策略记忆与遥测 |
| `execute` | `execute` | 经既有 R 阶段与 PEIG/AALG 门禁执行实验 |

`SCOPE_CANONICAL` 逐标签写明对 canonical state 的写权限；`run` 结束会逐字节比对 canonical 摘要，
只读/派生层若发生写入即 `PR9` + `BLOCKED`。

## 3. Intent Router：优先级与安全

解析顺序（高→低），实现见 `preset_router.resolve()`：

1. **显式 preset id**（`trigger: explicit`）；2. **别名**；3. **意图词 + 用户点名入口**；
4. **意图词**；5. **Loop 自动建议**（仅当用户没有表达任何意图时）。

| 规则 | 行为 |
|---|---|
| 否定 | 匹配点前 6 个汉字 / 24 个字符内出现「不要/别/先不/don't/skip…」→ 该预设被拒；唯一命中被拒时 `HOLD` + `intent_negated` |
| 歧义 | **精确同分**才算歧义 → 取**最小授权**的预设 + `requires_confirmation`，并列出 `ambiguous_with` |
| 专家入口 | 只给 `phase=R<n>` 时 `HOLD` + `expert_phase_entry`，交回既有 R 阶段 |
| 只读安全 | 只读提问绝不升级为执行；`read_only` 结果的 `next_action` 永远是只读步骤 |
| 陈述 vs 请求 | 只陈述问题（"训练 OOM 了"）→ 先只读诊断 + `requires_confirmation`；明确请求（"帮我恢复…"）→ 可直接执行，但仍受硬门禁约束 |
| 不判定科学 | Router 只做路由；不得因"检测到失败"输出任何假设被否证的结论 |
| 无在线模型 | 意图映射由字面规则完成，不引入任何在线模型依赖 |

输出契约（可追踪）：`preset_id` / `entry` / `trigger` / `reason` / `execution_scope` /
`protocol` / `next_action` / `requires_confirmation` / `candidates` / `negated` / `hold_reason`。

## 4. 自动触发：信号 → 协议

信号全部由机器可读状态与既有验证器算出（`signal_snapshot`）：`context_drift`、`state_integrity`、
`evidence_conflict`、`memory_drift`、`engineering_failure`、`scientific_failure`、`resource_blocked`
（唯一带 `text_based: true` 的线索型信号，需机器可读佐证）、`stagnation`、`pseudo_progress`、
`portfolio_convergence`、`evolution_due`。

**优先级按安全，而不是按科研严重度**：证据冲突(10) → 上下文漂移(20) → 记忆漂移(30) →
资源(40) → 工程失败(50) → Loop 体检(60) → 停滞(70) → 策略进化(80) → 假设再平衡(85) →
回放(90)。canonical 硬违规时**一律 `HOLD`**：恢复协议不得在坏状态上执行。

## 5. 自动触发：接口是真的，守护进程不是

触发引擎读 11 个机器可读信号（`signal_snapshot`），按安全优先选协议，并把候选、守卫与原因输出成
`loop-trigger@1`。**但事件监听、派遣与后台常驻由调用方负责**——既有 Scheduler、运行时或平台 Hook
调用 `preset_router.py trigger` / `record`。本 skill **不安装守护进程，也不声称无人值守自动执行**；
环境不调用它时只有推荐（`shared-contract.md` §7：没有监听/派遣能力时必须输出
`recommendation_only` / `blocked`）。

| 触发模式 | 谁可以进入 | 行为 |
|---|---|---|
| `recover`（分组 B/C） | 事件类 registry trigger | 通过守卫即 `RECOVER`，`requires_confirmation` 按权限层决定 |
| `recommend`（分组 A 中权限层 ≥ discovery 者，且**未授权**） | 仅推荐 | 候选带 `recommended_only: true`，**永不自动选中** |
| `recover` + `controlled`（已授权 Loop 内的受控 Discovery） | 需要 `scheduler.autonomous_loop` 授权 | 只在授权覆盖的权限层内触发；`discovery_only` **不覆盖** execute，故不会自动启动 GPU 或执行实验 |

**防死循环（三条硬规则）：**

| 机制 | 规则 |
|---|---|
| 同快照 | 相同 `(state_version, preset_id, signal_fingerprint)` 只允许一次 → `already_attempted_at_this_snapshot` |
| 冷却 | 距上次执行 < `cooldown_rounds` 且指纹未变 → `cooldown_active` |
| 上限 | 同一指纹累计达 `max_attempts` → `attempt_limit_reached`，`HOLD` 交人裁决 |

### 5.1 Loop 授权（`scheduler.autonomous_loop`）

用户决定：**Paradigm Escape 允许在已授权的 Autonomous Research Loop 中由真实停滞信号自动触发受控
Discovery；Scientific Replanning 允许自动生成/调整计划（只影响合法动作排序）。** 实现方式：

```sh
python3 scripts/preset_router.py authorize --state <S> --scope discovery_only   # 授权
python3 scripts/preset_router.py authorize --state <S> --revoke                 # 撤销
```

- 授权记录写在 **scheduler 遥测**（`autonomous_loop`），不在 canonical state；`discovery_only`
  只覆盖 `discovery` 权限层，`strategy` 覆盖 discovery+strategy，`full` 才覆盖 execute。
- 未授权时：`paradigm-escape` 只有 `recommended_only`；`scientific-replanning`（advisory）可直接自动生成计划。
- 无论是否授权：不得自动启动 GPU、不得改研究主锚点、不得绕过 R8/R9.O/R10/R11 与统一证据门禁；
  审查（`research-audit`）默认只读，写 `assurance[]` 必须显式经 R7 写回流程。

记录写在 `cognition/recovery-log.jsonl`（控制平面）。该文件与 `.execution/policy.json` 均不在恢复
路径的写入范围内（有测试逐字节校验，AALG 预算永不被刷新）。

## 5.2 R9.O → R10/R11 完成判定与 Loop 活性

**完成凭证是事务，不是 Repair。** `evidence_outcome.apply()` 合法提交后写入的正式凭证是五键
`outcome_analysis = {packet, analysis, audit, validation_context, audit_trail}`，其权威是
`evidence_outcome.state_errors()`：它校验 analysis 键集、packet/analysis/audit 摘要、audit 全部检查、
冻结策略、对 `validation_context` 的历史复验、"既有分析结果未被删除或改写"、
以及 `audit_trail`（`state_version == result_at_state_version`、`previous_state.version == state_version - 1`、
decision 一致、`state_delta` 非空、timestamp）与 `result`/`status` 一致性。

`repairs[]` **不是**完成条件：`NEGATIVE_EVIDENCE`、`INVALID_EXPERIMENT`、hypothesis-only 与
partial-scope 事务都合法提交却**不产生 Repair**（只有"把证据挂到 claim/hypothesis 上"的分支才写
Repair）。把 Repair 当收据会让这些实验永远像"待 Revise"。

| 状态 | 含义 | Loop 行为 |
|---|---|---|
| `NEEDS_ANALYSIS` | 终态实验尚无合法事务凭证 | 进入 R9.O（列出**具体**实验 ID） |
| `COMMITTED` | 正式事务凭证通过校验 | 不再重复 R10/R11；**不等于**科学结论成立，也不等于可以继续 GPU |
| `BLOCKED` | 凭证不完整、损坏、版本冲突或与状态矛盾 | `HOLD` 并报告实验 ID 与原因，不重试、不默认完成 |
| `PENDING_EXECUTION` | 尚未终态 | 不属于 R10/R11 待办 |

**判定按实验逐一进行**，不使用"项目已有任意历史分析"作为其他实验的完成凭证。同一快照下重复调用
结果稳定；跨会话重载后判定不变。`r10_pending()` 仅返回 `NEEDS_ANALYSIS`（保持向后兼容），
`BLOCKED` 由 `r10_blocked()` 单独报告。

**Loop 步骤顺序**（`_loop_step`）：契约 → 候选 → 凭证受损（HOLD）→ 缺失分析（R9.O Verify）→
planned/running（R8/R9 Intervene）→ 投影过期（Consolidate 一次）→ 决策门禁未过（Assurance /
Decision Gate）→ Scheduler 的下一项合法动作（Discover）→ 无合法动作（HOLD，不伪造进展）。
`COMMITTED` 之后仍必须先过 Assurance/Decision Gate，**不得**把"分析完成"当作"可以无条件继续执行"。

**工程故障信号同理**：`engineering_failure` 只统计既无 R10 处置、也无 `COMMITTED` 凭证的失败实验，
避免已合法提交的 `INVALID_EXPERIMENT` 被反复重新触发。

## 5.3 Scheduler 整体判定、策略写者权限与 post-update Assurance（2.3.3 修复）

**Scheduler 必须整体 PASS 才可派遣。** `strategy_memory.scheduler_verdict()` 以
`execution_gate.scheduler_check()` 的**整体状态**为准（`STALE_SCHEDULER`、`STATE_INVALID`、schema
错误、`MISSING_EIG` 等任一 FAIL → 无可派遣动作），授权判断**不再解析英文错误文本**；错误归因只用于
报告。`hard_gates.scheduler_check` 只有在整体 PASS 时才是 `PASS`，且每个动作还要通过结构化复检
（`status == planned`、plan gate PASS、无 `execution_blocked_by`、PEIG 非 HOLD）。

**策略写者与校验者统一。** `cognition.STRATEGY_REVISION_ACTORS = (R3,R4,R5,R6,R11,CIE)` 是唯一权威：
Meta-Controller（`CIE`）负责写入，R14 只提出建议（`SV6`）。写入前**先整组校验**（`SV1`/`SV3`/`SV5`/
`SV6`/`SV8`），任何一条不合法则整组不落盘；`after` 载荷投影为 `CM1` 允许的键
（`note`/`priors`/`operator`/`action`/`evidence`/`observations`，结构化 `scope`/`reactivation_conditions`/
`telemetry` 保存在 `priors` 与 `note` 中）。同一 `(kind, subject, at_state_version, after)` 事件幂等，
重复提交不产生重复记录。

**post-update Assurance 生命周期。** 操作手册见 [loop-assurance-review.md](loop-assurance-review.md)
（R7 如何取上下文、四项检查各自审什么、如何用 `assurance-store` 提交、如何处理 STALE/SUPERSEDED/复审；
`UNKNOWN` 记录阻断与复审条件、不重复送审）。正式审核产物放在
`<route>/assurance/outcome/<analysis_id>.json`（派生产物，canonical 仍是唯一科学权威，R7 拥有审核）：

| 状态 | 判据 | Loop 行为 |
|---|---|---|
| `PENDING` | 无产物 / 产物非法 | R7 审查任务；依赖它的 planned 实验必须等 |
| `VERIFIED` | 真实 `decision_gate()` 返回 `PASS` | 消费并推进到下一项合法动作 |
| `FAILED` | 有检查项 FAIL | `HOLD`（`assurance_failed`），不得继续 |
| `STALE` | state/analysis 摘要与当前状态不再匹配 | 视为需重新审核（待办），**不得复用** |
| `UNKNOWN` | 产物存在但结论未决 | `HOLD`（`assurance_unknown`）：记录阻断原因与复审条件，**不重复送审**；只有摘要变化、相关证据/分析变化或显式 `--force` 才重新触发 |
| `SUPERSEDED` | `decision_gate` 判定已有更晚结果重评其目标 | 无需自身审核，不阻塞后续动作 |

阶段顺序：凭证受损 → 缺失分析(R9.O) → Assurance FAIL → **依赖未完成审核的 planned 实验（HOLD）** →
独立 planned 实验（可推进并附带 `assurance_pending`）→ Consolidate（投影过期时一次）→ 待办审核 →
Scheduler 合法动作 → HOLD。**Loop 永不自行生成 Assurance**；缺审核时只能是待办或 HOLD。

## 6. Strategy Decision Adapter：让建议进入真实动作选择

审计结论：`recommend_strategy()` 产出菜单/算子/结构轴，但**没有任何消费者**；
`next_actions[]` 按它自己的规则（`EIG ÷ cost`）排序；`strategy_memory apply` 只打印建议。
闭环由 `strategy_memory.strategy_decision()` 补上，规则如下：

1. **优先级不动**：最优层仍由 `EIG ÷ cost` 决定（复用 `EIG_WEIGHT`/`COST_WEIGHT`）。
2. **只在同层重排**：建议只能改变最优层内部的顺序，不得把低层动作提到高层。
3. **只重排合法动作**：`execution_gate.scheduler_check` 报错的动作、`execution_blocked_by`
   非空的动作一律排除。
4. **亲和度只看声明字段**：动作 `target` 指向的 `hypotheses[].operator`/`island` 与建议一致，
   或 `uncertainties[].cheapest_discriminating_test` 正是该动作；**不从散文推断**。
5. **with / without memory 对照**：同一 state、同一合法动作集下比较顺序与选择，
   差异只能归因于策略记忆。
6. **改变不了就说清楚**：`strategy_applied` / `decision_changed` / `reason_if_not`
   （`single_candidate_in_tier` / `no_aligned_candidate_in_tier` / `advice_agrees_with_existing_order`
   / `no_legal_action`），**不得制造差异**。
7. **记录在既有遥测**：`scheduler.strategy_decisions[]`（上限 20 条），
   含候选集、建议、最终动作、是否采纳、未采纳原因、状态版本与实际派遣结果；
   **只写这一个键**（`eig_calibration`/`operator_stats`/`next_actions` 保持逐字节不变）。
8. **下一轮消费**：`research-loop` 预设读取 `latest_strategy_decision()`，在 state_version 未变时
   优先采纳该派遣动作；R3—R6 用 `discovery_operator` 选探索算子。
9. **`apply` 命名歧义已消除**：`strategy_memory apply` 明确只输出建议（`writes: []` + 说明），
   要进入调度请用 `decide [--record]`。

**边界**：适配器不得修改固定优先级、Research Contract、证据资格、AALG 预算、研究锚点或执行权限；
保留 exploration floor、问题结构作用域与算子重启条件，**不永久封禁失败算子**。

## 7. 验证等级（必须分开报告）

| 等级 | 含义 | 本版状态 |
|---|---|---|
| **L1** | 静态审查 + 单元测试：注册表/协议一致、路由与安全规则、守卫、适配器不变量 | ✅ 达成 |
| **L2** | 合成端到端：真实 CLI 与真实 `scheduler.json` / `cognition/` 上的决策、派遣记录与跨会话消费 | ✅ 达成 |
| **L3** | 真实科研 A/B：真实项目上策略采纳是否带来更好的科研结果 | ❌ **未执行** |

**被采纳 ≠ 研究能力提升。** 自进化的真实收益只能由 Discovery Replay 与科学结果验证；
本文件与 `presets/self-evolution.md` 都不得宣称已验证科研能力。

## 8. 自检

- [ ] 16 个协议都在 `presets/` 下且各自独立；每次调用只加载共同契约 + 选中的一份。
- [ ] `preset_router.py check --fixtures` 通过：提供版 53 条（48 正例 + 5 约束）全部命中。
- [ ] 只读提问没有被升级为执行；否定表达没有触发（否定按分句作用）。
- [ ] 自动恢复过不了守卫时不执行，而是 `HOLD`；用户预设即使被事件触发也只推荐。
- [ ] 工程故障没有被写成科学否证。
- [ ] 策略建议进入选择时留下了候选集、采纳与否与原因；改不动时有 `reason_if_not`。
- [ ] 没有监听/派遣能力时输出 `recommendation_only`，不宣称自动执行。

## 9. 文件地图

| 文件 | 作用 |
|---|---|
| [shared-contract.md](../shared-contract.md) | 所有预设的共同执行/证据/记忆边界（提供版） |
| [preset-registry.json](../preset-registry.json) | 16 条元数据 + 48 条意图示例（提供版，注册表来源） |
| [presets/](../presets/) | 16 份独立协议正文（提供版逐字保留 + 本仓库机器可校验章节） |
| [router-fixtures.json](../router-fixtures.json) | 意图路由基准：48 正例 + 5 约束/否定反例 |
| [scripts/preset_router.py](../scripts/preset_router.py) | Router、触发引擎、守卫、16 个 handler、CLI |
| [scripts/strategy_memory.py](../scripts/strategy_memory.py) | Strategy Decision Adapter（`decide`）与策略记忆 |
