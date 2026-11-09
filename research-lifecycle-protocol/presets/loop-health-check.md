# Preset: `loop-health-check` — Loop 健康检查 / Research Loop Health Check

> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`与选中的**这一个** Preset，不要一次注入全部 16 份。

| 字段 | 值 |
|---|---|
| preset id | `loop-health-check` |
| 顶层入口 | `continue-research` |
| 执行授权 | `inspect_only`（权限层 `read_only`）|
| registry trigger | `event_or_manual` |
| 分组 / 优先级 | `recovery` / 60（越小越优先）|
| 协议来源 | 提供版 `presets/loop-health-check.md` 正文 + 本仓库 9 节契约 |

## 1. 意图与入口

每个有意义的科研闭环后或用户要求健康检查；长循环中可按现有调度频率进行，但不能占满研究计算预算。

- 中文意图：只读体检：伪进展、重复行为、搜索停滞、预算与投影一致性，给出健康结论与建议
- English intent: read-only health report over pseudo-progress, repetition, stagnation and drift
- 入口 `continue-research`；授权 `inspect_only`；共同约束见 [shared-contract.md](../shared-contract.md)。

## 2. 触发条件

- 适用条件：
  - 定期体检
  - 怀疑伪进展
  - 恢复动作前后对照
- 自动触发（`recover`，需先过防重入守卫）：信号 `pseudo_progress`, `stagnation`；前提：always_available；冷却 0 轮；每指纹上限 3 次。
- registry 声明：`event_or_manual`；自然语言示例：「检查科研 loop 健康度」、「有在真正推进科研吗」、「check research loop health」
- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。

## 3. 必需输入

- `research-state.json`
- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → `shared-contract.md` → **本 Preset** → 必要 references。

## 4. 允许与禁止

- 允许：
  - 汇总机器可读信号
  - 给出恢复建议与优先级
- 禁止：
  - 执行实验
  - 改 canonical state
  - 自行触发恢复动作
- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。

## 5. 复用的阶段、脚本与检查器

- 阶段：R7/R14 只读体检
- 脚本 / 检查器：
  - `scripts/cognition.py`
  - `scripts/prediction_compare.py`
  - `scripts/strategy_memory.py`
  - `scripts/state_check.py`
- 规则号：本仓库自身产生 `PR1`—`PR10`；科学判定仍由既有规则号给出。

## 6. 执行步骤

**提供版执行协议（逐字）：**

1. 从真实 action/evidence 日志检视重复动作、失败恢复次数、科学有效结果、机制预测、state delta、决策 delta 与实际资源消耗。
2. 区分科学无突破但实验有效、执行故障、伪进展（新增文档但无新证据）和正常探索。
3. 对触发阈值的类别只推荐相应 preset：context drift、stagnation、experiment failure、evidence conflict、resource；不自行跨权限执行。
4. 记录当前快照上已建议/已派遣的恢复动作，防止检查器和修复器循环触发。

**在本仓库中实际执行的命令：**

| # | 步骤 | 命令 |
|---|---|---|
| 1 | 1 采集信号 | `python3 scripts/preset_router.py trigger --state <state>` |
| 2 | 2 回放对照 | `python3 scripts/research_replay.py suite --dir examples/replay/adversarial --runs 1` |

> 上表由 `preset_router.py run --preset loop-health-check` 实际返回，文档与代码由 `test_preset_router` 断言一致。

## 7. 输出契约

**提供版产出（逐字）：**

简短健康状态、触发证据、被推荐动作与是否已派遣、暂停/继续条件；不把代理自评作为核心度量。

- 机器可读字段：
  - `signals`
  - `verdict`
  - `recommended_preset`
  - `hold_reason`
  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / `reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / `next_action` / `canonical_untouched`。

## 8. 状态写回

- 允许写入：
  - 体检报告
- canonical `research-state.json`：不写 canonical。
- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 `scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。

## 9. 停止、失败与恢复

**提供版边界与退出（逐字）：**

（提供版未给出边界）

- 机器可读停止条件：
  - 报告输出即停
- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。
- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。
