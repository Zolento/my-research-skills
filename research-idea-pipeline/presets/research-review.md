# Preset: `research-review` — 科学进展回顾 / Research Review

> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`与选中的**这一个** Preset，不要一次注入全部 16 份。

| 字段 | 值 |
|---|---|
| preset id | `research-review` |
| 顶层入口 | `continue-research` |
| 执行授权 | `read_only`（权限层 `read_only`）|
| registry trigger | `manual` |
| 分组 / 优先级 | `user` / 100（越小越优先）|
| 协议来源 | 提供版 `presets/research-review.md` 正文 + 本仓库 9 节契约 |

## 1. 意图与入口

用户想知道“目前究竟发现了什么、为什么停滞、下一步最好做什么”，不要求推进实验。

- 中文意图：只读总结：已确立的结论、仍未知的部分、未完成任务与下一决策选项
- English intent: read-only summary of established results, unknowns and next decisions
- 入口 `continue-research`；授权 `read_only`；共同约束见 [shared-contract.md](../shared-contract.md)。

## 2. 触发条件

- 适用条件：
  - 用户要求汇报/复盘
  - 行动前需要现状快照
- 自动触发：**不适用**（用户显式意图优先）。
- registry 声明：`manual`；自然语言示例：「现在研究进展怎么样」、「总结当前真实发现，不要执行」、「review research progress」
- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。

## 3. 必需输入

- `research-state.json`
- `cognition/`
- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → `shared-contract.md` → **本 Preset** → 必要 references。

## 4. 允许与禁止

- 允许：
  - 读 canonical 与认知投影
  - 给出下一决策选项与代价
- 禁止：
  - 写 canonical state
  - 执行实验
  - 改策略记忆
- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。

## 5. 复用的阶段、脚本与检查器

- 阶段：只读，不写任何阶段产物
- 脚本 / 检查器：
  - `scripts/cognition.py`
  - `scripts/strategy_memory.py`
  - `scripts/prediction_compare.py`
  - `scripts/evidence_outcome.py`
- 规则号：本仓库自身产生 `PR1`—`PR9`；科学判定仍由既有规则号给出。

## 6. 执行步骤

**提供版执行协议（逐字）：**

1. 以只读方式恢复路线、主锚点、State、Cognitive Memory、最近有效实验、预算和调度记录。
2. 将发现分成：有效证据支持、竞争假说、无效/失败执行、尚未解释异常、被否证范围。
3. 指出当前最薄弱的因果/数学链条和最高价值的不确定性；辨别是否因反复归因而停滞。
4. 比较不超过三种下一动作，说明各自的决策价值、证据条件和成本，不派遣任何动作。

**在本仓库中实际执行的命令：**

| # | 步骤 | 命令 |
|---|---|---|
| 1 | 1 只读状态快照 | `python3 scripts/state_check.py <state> --quiet` |
| 2 | 2 认知 brief | `python3 scripts/cognition.py brief --state <state>` |
| 3 | 3 价值判断 | `python3 scripts/strategy_memory.py value --state <state>` |

> 上表由 `preset_router.py run --preset research-review` 实际返回，文档与代码由 `test_preset_router` 断言一致。

## 7. 输出契约

**提供版产出（逐字）：**

一页研究现状，包含 Scientific Delta、未解机制、最关键风险与下一建议。明确标记 `read_only`，不得写回 State、启动 GPU 或暗中切换为执行模式。

- 机器可读字段：
  - `progress`
  - `unknowns`
  - `open_obligations`
  - `next_decisions`
  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / `reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / `next_action` / `canonical_untouched`。

## 8. 状态写回

- 允许写入：
  - cognition/context-brief.md（可选）
- canonical `research-state.json`：不写 canonical。
- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 `scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。

## 9. 停止、失败与恢复

**提供版边界与退出（逐字）：**

（提供版未给出边界）

- 机器可读停止条件：
  - 报告输出即停
- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。
- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。
