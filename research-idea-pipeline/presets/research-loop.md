# Preset: `research-loop` — 自主科研闭环 / Autonomous Research Loop

> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`与选中的**这一个** Preset，不要一次注入全部 16 份。

| 字段 | 值 |
|---|---|
| preset id | `research-loop` |
| 顶层入口 | `continue-research` |
| 执行授权 | `execute`（权限层 `execute`）|
| registry trigger | `manual` |
| 分组 / 优先级 | `user` / 100（越小越优先）|
| 协议来源 | 提供版 `presets/research-loop.md` 正文 + 本仓库 9 节契约 |

## 1. 意图与入口

用户要求“继续科研、自动运行、持续 Loop”。已初始化项目直接继续，绝不重新 Bootstrap。只在已经授权的范围内持续推进。

- 中文意图：在既有 R0—R14 与硬门禁内，按 Recall→Understand→Discover→Predict→Intervene→Verify→Revise→Consolidate→Loop 持续推进，直到停止条件出现
- English intent: run the CIE scientific loop inside the existing stages and gates
- 入口 `continue-research`；授权 `execute`；共同约束见 [shared-contract.md](../shared-contract.md)。

## 2. 触发条件

- 适用条件：
  - 用户明确要求自动/持续推进
  - 状态与证据完整，硬门禁可通过
- 自动触发：**不适用**（用户显式意图优先）。
- registry 声明：`manual`；自然语言示例：「继续自动科研」、「按现有授权持续跑 loop」、「continue autonomous research」
- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。

## 3. 必需输入

- `research-state.json`
- `contract`
- `scheduler`
- `cognition/index.json`
- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → `shared-contract.md` → **本 Preset** → 必要 references。

## 4. 允许与禁止

- 允许：
  - 调用既有阶段与脚本
  - 在 PEIG/AALG 授权内执行实验
- 禁止：
  - 绕过 R8/R9.O/R10 的证据门禁
  - 自行改写 contract/锚点
  - 刷新 AALG 诊断预算
- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。

## 5. 复用的阶段、脚本与检查器

- 阶段：R0 → R14（按 `_loop_step` 选择当前阶段）
- 脚本 / 检查器：
  - `scripts/cognition.py`
  - `scripts/prediction_compare.py`
  - `scripts/strategy_memory.py`
  - `scripts/state_check.py`
  - `scripts/execution_gate.py`
  - `scripts/experiment_execute.py`
  - `scripts/evidence_outcome.py`
  - `scripts/policy_evolution.py`（Skill-RSI：读取 ACTIVE 策略；只读，不在此处晋升）
  - `scripts/decision_trajectory.py`（Skill-RSI：应用路径记录实际派遣）
- 规则号：本仓库自身产生 `PR1`—`PR10`；Skill-RSI 另产生 `DT0`—`DT10`；科学判定仍由既有规则号给出。

**策略消费（Skill-RSI，只读）：** 若存在 ACTIVE 且有作用域的策略，Loop 通过现有
`strategy_memory.strategy_decision()` 在同一 `EIG ÷ cost` 层内重排已通过硬门禁的动作，
并采用其结果作为下一项**实际派遣**的动作；适用范围不满足或跨项目迁移未通过时忽略该策略并记录原因。
`apply` 路径把这次派遣写入决策轨迹与 `scheduler.strategy_decisions[]`；只读路径不写。
输出区分 `scientific_delta` / `decision_delta` / `policy_delta`，三者均可为 `none`。

## 6. 执行步骤

**提供版执行协议（逐字）：**

1. 恢复项目锚点、当前路线、State、Scheduler、Cognitive Memory、证据和在途实验；校验 Skill 版本及预算，确认未完成动作是否已被执行。
2. 调用现有 Meta-Controller 选择合法动作；优先能够改变科学认识、产生区分性预测或形成方法干预的动作，不以填满日志为目标。
3. 对机制假设构造适用条件、竞争解释、可观测预测和便宜的判别干预；允许清楚标注的探索性假设，不可事后伪造预注册。
4. 执行前经过 R8、容量/强度/优化条件/可识别性、公平比较及 GPU 授权检查；执行进程用已存在的运行 ID 与结果记录防重。
5. 经 Outcome Analysis、Evidence Qualification、R10/R11 修订状态和认知模型；更新失败边界与调度经验，证明本轮记忆是否改变后续研究动作。
6. 返回步骤 1，直到预算、用户指令、权限、安全、无合法动作或正式研究终止条件触发。每轮必要检查点落盘。

**在本仓库中实际执行的命令：**

| # | 步骤 | 命令 |
|---|---|---|
| 1 | Recall | `python3 scripts/cognition.py recall --state <state>` |
| 2 | Understand | `python3 scripts/state_check.py <state> --quiet` |
| 3 | Discover | `python3 scripts/strategy_memory.py recommend --state <state>` |
| 4 | Predict | `python3 scripts/prediction_compare.py freeze --state <state> --experiment <X>` |
| 5 | Intervene | `python3 scripts/execution_gate.py peig --state <state> --experiment <X>` |
| 6 | Verify | `python3 scripts/prediction_compare.py compare --state <state> --packet <packet> --for-transition` |
| 7 | Revise | `python3 scripts/evidence_outcome.py apply --state <state> --packet <packet> --analysis <analysis>` |
| 8 | Consolidate | `python3 scripts/cognition.py build --state <state>` |
| 9 | Loop | `python3 scripts/preset_router.py trigger --state <state>` |

> 上表由 `preset_router.py run --preset research-loop` 实际返回，文档与代码由 `test_preset_router` 断言一致。

## 7. 输出契约

**提供版产出（逐字）：**

每轮简要记录有效证据、新预测、模型修订、下一次决策、实际派遣、state_version、预算与停止原因；没有 Insight 就报告没有。

- 机器可读字段：
  - `loop_state`
  - `next_action`
  - `dispatched_action` / `strategy_changed_dispatch`
  - `evidence_delta`
  - `scientific_delta` / `decision_delta` / `policy_delta`（`policy_delta` 必须带评价等级）
  - `changed_decision`
  - `hold_reason`
  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / `reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / `next_action` / `canonical_untouched`。

## 8. 状态写回

- 允许写入：
  - research-state.json（只经既有 R 阶段与门禁）
  - cognition/ 投影
  - 执行账本
  - `decision-trajectory.jsonl`（**仅 apply 路径**：把本次实际派遣写入决策轨迹）
  - `scheduler.json`（**仅 apply 路径**：把策略决策追加到既有 `strategy_decisions[]` 遥测）
  - `source-integrity.jsonl`（运行前后的源码完整性审计事件）
- canonical `research-state.json`：只经既有 R 阶段与门禁写。
- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 `scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。

## 9. 停止、失败与恢复

**提供版边界与退出（逐字）：**

连续动作不带来新预测、结构变化或决策价值时，不继续同构诊断；交给 `stagnation-breaker`。上下文不一致交给 `context-drift-recovery`。工程故障交给 `experiment-failure-recovery`。每次转交只触发一次，不能互相递归。

- 机器可读停止条件：
  - 预算或配额耗尽
  - 证据冲突未解
  - 需要人类裁决
  - 连续无决策变化
- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。
- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。
