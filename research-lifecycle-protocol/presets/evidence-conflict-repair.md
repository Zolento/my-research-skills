# Preset: `evidence-conflict-repair` — 证据冲突修复 / Evidence Conflict Repair

> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`与选中的**这一个** Preset，不要一次注入全部 16 份。

| 字段 | 值 |
|---|---|
| preset id | `evidence-conflict-repair` |
| 顶层入口 | `audit` |
| 执行授权 | `evidence_repair`（权限层 `discovery`）|
| registry trigger | `event_or_manual` |
| 分组 / 优先级 | `recovery` / 10（越小越优先）|
| 协议来源 | 提供版 `presets/evidence-conflict-repair.md` 正文 + 本仓库 9 节契约 |

## 1. 意图与入口

预测、观测、Evidence、Claim、Insight、认知记忆间存在不同版本、缺失引用、失效来源或相互矛盾的合法性标记。

- 中文意图：定位 Evidence/Claim/Prediction/Memory 的不一致，给出只能经 R10/R11 与统一证据门禁执行的修复路径；本预设自身不改 canonical
- English intent: locate evidence/claim/prediction/memory conflicts and route the R10/R11 repair
- 入口 `audit`；授权 `evidence_repair`；共同约束见 [shared-contract.md](../shared-contract.md)。

## 2. 触发条件

- 适用条件：
  - state_check 引用/失效/可信度违规
  - 支持列表与状态矛盾
  - 证据已失效仍被引用
- 自动触发（`recover`，需先过防重入守卫）：信号 `evidence_conflict`, `state_integrity`；前提：conflict_present；冷却 1 轮；每指纹上限 2 次。
- registry 声明：`event_or_manual`；自然语言示例：「实验结果和 evidence 对不上」、「修复 claim 和 memory 冲突」、「repair evidence conflict」
- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。

## 3. 必需输入

- `research-state.json`
- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → `shared-contract.md` → **本 Preset** → 必要 references。

## 4. 允许与禁止

- 允许：
  - 列出冲突与最小修复步骤
  - 指出应走 R10 还是 R11
- 禁止：
  - 自行改 claim 状态
  - 绕过统一证据资格门
  - 为了让状态变绿而删除证据
- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。

## 5. 复用的阶段、脚本与检查器

- 阶段：R10/R11（唯一有权改 claim 状态的两条路径）
- 脚本 / 检查器：
  - `scripts/state_check.py`
  - `scripts/evidence_outcome.py`
  - `scripts/prediction_compare.py`
  - `scripts/cognition.py`
- 规则号：本仓库自身产生 `PR1`—`PR10`；科学判定仍由既有规则号给出。

## 6. 执行步骤

**提供版执行协议（逐字）：**

1. 将相关实验和预测升级链临时置于不得提升科学支持的状态；保存冲突清单和原始来源。
2. 逐级核对冻结预注册、结果结构/原始摘要、执行有效性、统一 Evidence Qualification、R9.O、R10/R11 及 Scope。
3. 区分观察错误、元数据错误、无效证据、真正冲突预测；不能用猜测补齐历史 prediction_ref 或事后改变冻结规则。
4. 按已有权限进行修复/失效传播；仅在合法状态迁移之后重建 Memory、Scheduler 投影。未解决的冲突保持 HOLD。
5. 验证没有通过其他入口间接认证 Insight，且同一冲突不反复重试。

**在本仓库中实际执行的命令：**

| # | 步骤 | 命令 |
|---|---|---|
| 1 | 1 定位冲突 | `python3 scripts/state_check.py <state>` |
| 2 | 2 判定迁移路径 | `python3 scripts/evidence_outcome.py check-plan --state <state> --experiment <X>` |
| 3 | 3 重放收缩 | `python3 scripts/evidence_outcome.py decision --state <state> --experiment <X>` |
| 4 | 4 应用迁移 | `python3 scripts/evidence_outcome.py apply --state <state> ...` |

> 上表由 `preset_router.py run --preset evidence-conflict-repair` 实际返回，文档与代码由 `test_preset_router` 断言一致。

## 7. 输出契约

**提供版产出（逐字）：**

冲突来源、资格判断、合法修复或 HOLD、受影响的 Claim / Insight / Memory 引用及复核结果。

- 机器可读字段：
  - `conflicts`
  - `route`
  - `blocked_transitions`
  - `next_action`
  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / `reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / `next_action` / `canonical_untouched`。

## 8. 状态写回

- 允许写入：
  - 诊断报告
- canonical `research-state.json`：只经 R10/R11 写 claim/hypothesis 状态。
- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 `scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。

## 9. 停止、失败与恢复

**提供版边界与退出（逐字）：**

（提供版未给出边界）

- 机器可读停止条件：
  - 无 R10/R11 授权（HOLD 并交人裁决）
- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。
- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。
