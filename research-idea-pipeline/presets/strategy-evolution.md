# Preset: `strategy-evolution` — 策略进化 / Strategy Evolution

> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`与选中的**这一个** Preset，不要一次注入全部 16 份。

| 字段 | 值 |
|---|---|
| preset id | `strategy-evolution` |
| 顶层入口 | `continue-research` |
| 执行授权 | `strategy_update`（权限层 `strategy`）|
| registry trigger | `manual_or_scheduled` |
| 分组 / 优先级 | `evolution` / 80（越小越优先）|
| 协议来源 | 提供版 `presets/strategy-evolution.md` 正文 + 本仓库 9 节契约 |

## 1. 意图与入口

利用历史研究表现调整探索算子及下一动作选择，不改变科学证据与硬门禁。

- 中文意图：用预测/干预的历史成效更新既有授权的策略记忆与探索建议，并证明下一轮推荐发生可观察变化
- English intent: update authorised strategy memory from history and prove the next recommendation changes
- 入口 `continue-research`；授权 `strategy_update`；共同约束见 [shared-contract.md](../shared-contract.md)。

## 2. 触发条件

- 适用条件：
  - 同一算子/菜单累计失败
  - 预测-干预校准偏差
  - 策略修订间隔到达
- 自动触发（`recover`，需先过防重入守卫）：信号 `evolution_due`；前提：operator_history_present；冷却 1 轮；每指纹上限 2 次。
- registry 声明：`manual_or_scheduled`；自然语言示例：「根据历史结果改进探索策略」、「让策略记忆真正影响下一轮决策」、「evolve exploration strategy」
- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。

## 3. 必需输入

- `research-state.json`
- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → `shared-contract.md` → **本 Preset** → 必要 references。

## 4. 允许与禁止

- 允许：
  - 更新算子先验与菜单排序
  - 记录改变量
- 禁止：
  - 改 Research Contract/锚点
  - 改证据门禁或 skill 源码
  - 永久封禁算子
- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。

## 5. 复用的阶段、脚本与检查器

- 阶段：R14（策略记忆）+ `SV1`—`SV8`
- 脚本 / 检查器：
  - `scripts/strategy_memory.py`
  - `scripts/research_replay.py`
  - `scripts/cognition.py`
  - `scripts/decision_trajectory.py`（Skill-RSI：决策轨迹，策略经验的来源）
  - `scripts/policy_evolution.py`（Skill-RSI：有作用域的策略候选、评价、晋升、回滚）
  - `scripts/policy_transfer.py`（Skill-RSI：跨项目迁移门）
- 规则号：本仓库自身产生 `PR1`—`PR10`；Skill-RSI 另产生 `DT0`—`DT10` / `PE1`—`PE14` /
  `PT1`—`PT11`；科学判定仍由既有规则号给出。

**Skill-RSI 生命周期命令（按需，不在每轮循环内执行）：**

| # | 步骤 | 命令 |
|---|---|---|
| R1 | 冻结评价规则 | `python3 scripts/policy_evolution.py freeze-rules --state <state>` |
| R2 | 提出候选 | `python3 scripts/policy_evolution.py propose --state <state> --policy <candidate.json> --trajectory <trajectory.jsonl>` |
| R3 | Shadow 评价 | `python3 scripts/policy_evolution.py transition --state <state> --policy-id <P> --to SHADOW` |
| R4 | 独立回放评价 | `python3 scripts/research_replay.py ablate --dir examples/replay/adversarial --rsi --runs 2` |
| R5 | 记录评价结论 | `python3 scripts/policy_evolution.py evaluate --state <state> --policy-id <P> --report <report.json>` |
| R6 | 有限试运行与晋升 | `python3 scripts/policy_evolution.py transition --state <state> --policy-id <P> --to BOUNDED_TRIAL` |
| R7 | 回滚 | `python3 scripts/policy_evolution.py rollback --state <state> --policy-id <P> --to-policy-id <prev> --reason <why>` |
| R8 | 真实消费 | `python3 scripts/strategy_memory.py decide --state <state> --scheduler <scheduler> --record` |

> 上表是**策略演化**的操作面，不进 `preset_router.py` 的自动步骤；晋升后的策略由
> 现有 Strategy Decision Adapter 消费。详见 [references/skill-rsi-policy.md](../references/skill-rsi-policy.md)。

## 6. 执行步骤

**提供版执行协议（逐字）：**

1. 汇集可信的操作者表现：可区分预测、有效干预、无效诊断、结构重复、证据质量、成本。限制于相同或可比的问题结构，不以自评创新分替代反馈。
2. 复用现有 Strategy Memory 生成有 provenance 的候选策略更新，并保留 exploration floor、失效范围和重新激活条件。
3. 检查当前 Scheduler 是否有实际消费建议的 Strategy Decision Adapter：只能在同等合法、同等硬优先级的动作中调整顺序，不允许改 AALG、锚点、预算或证据规则。
4. 若有 adapter，比较**相同** state_version、合法动作集合、固定规则下 with-memory / without-memory 的行动排序或选择；记录 baseline、applied、decision_changed、dispatch_status 与不变原因。
5. 若没有 adapter，**必须明确输出 `recommendation_only`，不得声称 L2 实际策略进化**；提出消费接口的工程缺口，但不能伪造 `strategy_applied=true`。
6. 候选策略只有经独立 Replay/对照验证才可声称带来科研能力改进；实际策略应用不等于 Insight 增益。

**在本仓库中实际执行的命令：**

| # | 步骤 | 命令 |
|---|---|---|
| 1 | 1 历史校准 | `python3 scripts/strategy_memory.py operators --state <state>` |
| 2 | 2 生成修订 | `python3 scripts/strategy_memory.py apply --state <state>` |
| 3 | 3 决策适配（同层重排） | `python3 scripts/strategy_memory.py decide --state <state> --scheduler <scheduler>` |
| 4 | 4 写入调度遥测 | `python3 scripts/strategy_memory.py decide --state <state> --scheduler <scheduler> --record` |
| 5 | 5 回放验证 | `python3 scripts/preset_router.py run --preset discovery-replay --state <state>` |

> 上表由 `preset_router.py run --preset strategy-evolution` 实际返回，文档与代码由 `test_preset_router` 断言一致。

## 7. 输出契约

**提供版产出（逐字）：**

L1 建议、L2 实际调度影响证据、L3 独立效果证据，分别标记 verified/unverified；下一步合法探索动作。

- 机器可读字段（与 `_handle_strategy_evolution` 实际返回一致）：
  - `advice`（菜单/算子/island/shift/basis）
  - `candidates_before` / `candidates_after`
  - `chosen_without_memory` / `chosen`（同 `state_version`、同一合法动作集下的 with/without-memory 对照）
  - `strategy_applied` / `reason_if_not`
  - `dispatch`（实际派遣目标；未派遣时为 `null` 而不是伪装成已派遣）
  - `changed_decision`
  - Skill-RSI：`policy_delta` 只在实际改变了动作**且**该动作被派遣时才出现，否则为 `none`
  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / `reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / `next_action` / `canonical_untouched`。

## 8. 状态写回

- 允许写入：
  - 策略修订（`cognition/model-revisions.jsonl`，append-only）
  - `scheduler.json`（只追加 `strategy_decisions[]` 遥测，其余键逐字节不变）
  - Skill-RSI 策略候选与状态转移（`<route>/policy/`，append-only）
  - 运行期源码完整性审计事件（`<route>/source-integrity.jsonl`）
- **不写** `decision-trajectory.jsonl`：决策轨迹由 `research-loop` 在 apply 路径上记录
- canonical `research-state.json`：不写 canonical（只写策略记忆）。
- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 `scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。

## 9. 停止、失败与恢复

**提供版边界与退出（逐字）：**

（提供版未给出边界）

- 机器可读停止条件：
  - 无可信历史（NO_CHANGE）
  - 改变会越过证据标准（拒绝）
- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。
- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。
