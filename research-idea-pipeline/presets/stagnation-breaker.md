# Preset: `stagnation-breaker` — 停滞打破 / Stagnation Breaker

> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`与选中的**这一个** Preset，不要一次注入全部 16 份。

| 字段 | 值 |
|---|---|
| preset id | `stagnation-breaker` |
| 顶层入口 | `continue-research` |
| 执行授权 | `decision_only`（权限层 `advisory`）|
| registry trigger | `event_or_manual` |
| 分组 / 优先级 | `recovery` / 70（越小越优先）|
| 协议来源 | 提供版 `presets/stagnation-breaker.md` 正文 + 本仓库 9 节契约 |

## 1. 意图与入口

连续有效闭环无独立预测/科学决策变化、候选结构指纹重复、AALG 诊断预算耗尽，或由运行轨迹观察到重复诊断。单次负结果不足以触发。

- 中文意图：停滞诊断 + 动作选择器：选出一个能改变决策的最小干预，或明确停手
- English intent: diagnose stagnation and choose the smallest decision-changing intervention
- 入口 `continue-research`；授权 `decision_only`；共同约束见 [shared-contract.md](../shared-contract.md)。

## 2. 触发条件

- 适用条件：
  - 连续零信息增益诊断
  - 同构候选/重复归因
  - 判别力缺失
- 自动触发（`recover`，需先过防重入守卫）：信号 `stagnation`, `pseudo_progress`；前提：stagnation_detected；冷却 2 轮；每指纹上限 2 次。
- registry 声明：`event_or_manual`；自然语言示例：「一直在重复归因」、「检查是不是陷入局部最优」、「detect scientific stagnation」
- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。

## 3. 必需输入

- `research-state.json`
- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → `shared-contract.md` → **本 Preset** → 必要 references。

## 4. 允许与禁止

- 允许：
  - 选择判别干预或行为切换
  - 记录边界并停手
- 禁止：
  - 仅凭一次负结果判定理论失败
  - 生成新解释来抢救旧机制
  - 刷新诊断预算
- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。

## 5. 复用的阶段、脚本与检查器

- 阶段：R5.1/T8（行为切换）+ R6（重定义问题）
- 脚本 / 检查器：
  - `scripts/prediction_compare.py`
  - `scripts/cognition.py`
  - `scripts/strategy_memory.py`
  - `scripts/decision_trajectory.py`（Skill-RSI：判断重复诊断是否真的改变过任何后续决定）
- 规则号：本仓库自身产生 `PR1`—`PR9`；Skill-RSI 另产生 `DT0`—`DT10`；科学判定仍由既有规则号给出。

**行为切换的证据必须是真实决定（Skill-RSI）：** 多次实验没有产生新的可区分预测、不断增加新解释却没有
新的识别实验、新假设与已失败机制结构等价、只缩小缺陷范围却不改方法设计、相同证据下重复审查、
已耗尽诊断预算、或新行动无法改变任何后续决定时，优先切换到停止某条诊断路径、重新设计方法、
有界竞争机制测试、R5.1 定向检索、R3/R6 结构性探索或 R14 决策。**不得**用「再跑一次 RSI」代替决策改变。

## 6. 执行步骤

**提供版执行协议（逐字）：**

1. 读取最近有效研究动作、结构签名、失败作用域、诊断预算及研究目标，区分工程卡死、优化卡住与建模范式卡住。
2. 计算可核验的停滞证据：相同机制前提、重复行动、预测/决策 delta 缺失；不以 Agent 主观感受作为触发依据。
3. 如果是工程故障，路由 `experiment-failure-recovery`；如果仍存在便宜且有区分力的判别干预，优先允许一次合法干预。
4. 仅当表征层停滞确立，输出 `paradigm-escape` 的单次触发建议/调度决策；保持原研究锚点和所有失败限制。
5. 同一状态快照和原因不可反复自触发；给出停止、冷却或等待新证据条件。

**在本仓库中实际执行的命令：**

| # | 步骤 | 命令 |
|---|---|---|
| 1 | 1 停滞检测 | `python3 scripts/prediction_compare.py switch --state <state>` |

> 上表由 `preset_router.py run --preset stagnation-breaker` 实际返回，文档与代码由 `test_preset_router` 断言一致。

## 7. 输出契约

**提供版产出（逐字）：**

停滞证据、分型、下一 preset 或实验、未触发理由及消除循环的检查点。

- 机器可读字段：
  - `switch_action`
  - `witness`
  - `next_intervention`
  - `stop_reason`
  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / `reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / `next_action` / `canonical_untouched`。

## 8. 状态写回

- 允许写入：
  - 诊断记录
  - scheduler 只读
- canonical `research-state.json`：不写 canonical（只产出决策）。
- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 `scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。

## 9. 停止、失败与恢复

**提供版边界与退出（逐字）：**

（提供版未给出边界）

- 机器可读停止条件：
  - 结构性不可区分且与决策无关（记录边界并停）
- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。
- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。
