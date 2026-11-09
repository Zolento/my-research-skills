# Preset: `hypothesis-rebalance` — 假设组合再平衡 / Hypothesis Portfolio Rebalance

> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`与选中的**这一个** Preset，不要一次注入全部 16 份。

| 字段 | 值 |
|---|---|
| preset id | `hypothesis-rebalance` |
| 顶层入口 | `explore` |
| 执行授权 | `portfolio`（权限层 `strategy`）|
| registry trigger | `manual_or_scheduled` |
| 分组 / 优先级 | `evolution` / 85（越小越优先）|
| 协议来源 | 提供版 `presets/hypothesis-rebalance.md` 正文 + 本仓库 9 节契约 |

## 1. 意图与入口

当当前 Hypothesis Portfolio 被单一假设、同构结构或同一个学习算子支配时，恢复多样性与风险分散。

- 中文意图：度量候选在同构轴上的集中度，并按既有算子/岛屿菜单再平衡；不新增候选家族分类
- English intent: measure portfolio concentration on existing structural axes and rebalance menus
- 入口 `explore`；授权 `portfolio`；共同约束见 [shared-contract.md](../shared-contract.md)。

## 2. 触发条件

- 适用条件：
  - 单一岛屿/算子占比过高
  - 结构签名过于集中
  - 探索下限未被满足
- 自动触发（`recover`，需先过防重入守卫）：信号 `portfolio_convergence`；前提：concentration_above_threshold；冷却 2 轮；每指纹上限 2 次。
- registry 声明：`manual_or_scheduled`；自然语言示例：「所有 idea 都一样」、「重新平衡假设组合」、「rebalance hypothesis portfolio」
- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。

## 3. 必需输入

- `research-state.json`
- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → `shared-contract.md` → **本 Preset** → 必要 references。

## 4. 允许与禁止

- 允许：
  - 调整岛屿/算子探索权重
  - 要求至少一个新轴候选
- 禁止：
  - 删除既有候选
  - 永久封禁岛屿/算子
  - 绕过 V13/V15/V16
- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。

## 5. 复用的阶段、脚本与检查器

- 阶段：R3—R6（候选生成）+ `V13`/`V15`/`V16`
- 脚本 / 检查器：
  - `scripts/strategy_memory.py`
  - `scripts/cognition.py`
  - `scripts/state_check.py`
- 规则号：本仓库自身产生 `PR1`—`PR10`；科学判定仍由既有规则号给出。

## 6. 执行步骤

**提供版执行协议（逐字）：**

1. 从当前 QD archive、结构签名、机制模型、否证约束中识别重复组合；比较不同 niche 的贡献和证据覆盖。
2. 明确哪些假设是同义变体、哪些在不同观察或干预下给出实质不同的预测；不凭词面多样性判定创新。
3. 调用现有 P1—P6 及 R4/R6 的隔离种群规则，允许反转占优假设并保留少量高风险高发现潜力方向。
4. 结合预算、证据等级与研究锚点提出 retain / pause / explore；淘汰不得跨越有效否证作用域，也不得自动改主锚点。
5. 与合法调度器衔接，输出具体候选和将改变的下一次动作；无派遣接口时只报告建议。

**在本仓库中实际执行的命令：**

| # | 步骤 | 命令 |
|---|---|---|
| 1 | 1 度量集中度 | `python3 scripts/cognition.py brief --state <state>` |
| 2 | 2 调整菜单 | `python3 scripts/strategy_memory.py recommend --state <state>` |
| 3 | 3 生成新轴候选 | `在 P5/P6/local 菜单下产出至少一个不同结构轴的候选` |
| 4 | 4 校验 | `python3 scripts/state_check.py <state> --quiet` |

> 上表由 `preset_router.py run --preset hypothesis-rebalance` 实际返回，文档与代码由 `test_preset_router` 断言一致。

## 7. 输出契约

**提供版产出（逐字）：**

组合集中度、结构差异、新假设独立预测、重新平衡建议与追踪引用。

- 机器可读字段：
  - `concentration_before`
  - `concentration_after`
  - `menus_changed`
  - `changed_decision`
  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / `reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / `next_action` / `canonical_untouched`。

## 8. 状态写回

- 允许写入：
  - 策略修订（append-only 修订日志）
- canonical `research-state.json`：不写 canonical（只写策略记忆）。
- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 `scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。

## 9. 停止、失败与恢复

**提供版边界与退出（逐字）：**

（提供版未给出边界）

- 机器可读停止条件：
  - 已满足多样性下限（NO_CHANGE）
- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。
- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。
