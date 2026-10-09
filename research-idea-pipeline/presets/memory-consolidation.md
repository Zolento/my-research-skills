# Preset: `memory-consolidation` — 认知记忆整合 / Cognitive Memory Consolidation

> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`与选中的**这一个** Preset，不要一次注入全部 16 份。

| 字段 | 值 |
|---|---|
| preset id | `memory-consolidation` |
| 顶层入口 | `continue-research` |
| 执行授权 | `derived_only`（权限层 `derived`）|
| registry trigger | `event_or_manual` |
| 分组 / 优先级 | `recovery` / 30（越小越优先）|
| 协议来源 | 提供版 `presets/memory-consolidation.md` 正文 + 本仓库 9 节契约 |

## 1. 意图与入口

合法 R11 更新、机制修订、新会话恢复或认知索引版本落后于 canonical State。

- 中文意图：在合法机制修订/状态变化后重建认知投影并报告记忆漂移；不修改 canonical 科学事实
- English intent: rebuild CIE projections after legal revisions; never touches canonical science
- 入口 `continue-research`；授权 `derived_only`；共同约束见 [shared-contract.md](../shared-contract.md)。

## 2. 触发条件

- 适用条件：
  - 机制修订或状态迁移后投影过期
  - CM 硬诊断出现
  - insight/策略投影漂移
- 自动触发（`recover`，需先过防重入守卫）：信号 `memory_drift`；前提：hard_cm_diagnostic；冷却 1 轮；每指纹上限 2 次。
- registry 声明：`event_or_manual`；自然语言示例：「整理认知记忆」、「State 更新后刷新 Cognitive Memory」、「consolidate research memory」
- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。

## 3. 必需输入

- `research-state.json`
- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → `shared-contract.md` → **本 Preset** → 必要 references。

## 4. 允许与禁止

- 允许：
  - 重建投影
  - 报告降级/失效传播结果
- 禁止：
  - 修改 canonical 科学事实
  - 用投影覆盖 state
  - 把自评写进支持等级
- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。

## 5. 复用的阶段、脚本与检查器

- 阶段：R11 后重建认知投影（`CM0`—`CM10`）
- 脚本 / 检查器：
  - `scripts/cognition.py`
  - `scripts/strategy_memory.py`
  - `scripts/state_check.py`
  - `scripts/policy_transfer.py`（Skill-RSI：三层记忆分离、过期经验、无损压缩检查）
- 规则号：本仓库自身产生 `PR1`—`PR9`；Skill-RSI 另产生 `PT1`—`PT10`；科学判定仍由既有规则号给出。

**三层记忆不得互相替代（Skill-RSI）：** Scientific Memory 由 canonical 科学对象及其派生投影提供；
Decision Experience 保存历史行动、选择条件、结果与执行成本（决策轨迹）；Policy Memory 保存经过
限定和验证的科研策略。压缩记忆时**不得丢失证据与停止规则**；跨项目迁移只看声明结构，不看领域关键词。

## 6. 执行步骤

**提供版执行协议（逐字）：**

1. 根据 canonical State、正式预注册、有效实验和 provenance 重新构建认知索引；复用已有 cognition build/check，勿重写权威事实。
2. 合并同义机制索引但保留不同适用范围、版本、失败条件和原始 ID；被否证机制保留为有范围的负面知识。
3. 对旧预测、异常和认知修订标记 valid / stale / unresolved；历史无法恢复的预测标记 retrospective/unknown，不得追认冻结。
4. 生成精简 Hot/Warm 上下文摘要；核对 State version、引用、过期传播和跨会话加载。
5. 若仅为派生投影更新，不能上调 Claim、Insight 或 Scheduler 成功指标。

**在本仓库中实际执行的命令：**

| # | 步骤 | 命令 |
|---|---|---|
| 1 | 1 重建 | `python3 scripts/cognition.py build --state <state>` |
| 2 | 2 校验 | `python3 scripts/cognition.py check --state <state>` |
| 3 | 3 失效传播 | `python3 scripts/state_check.py <state> --quiet` |

> 上表由 `preset_router.py run --preset memory-consolidation` 实际返回，文档与代码由 `test_preset_router` 断言一致。

## 7. 输出契约

**提供版产出（逐字）：**

更新的索引、实际变化/失效传播、版本核验和可恢复性检查结果。

- 机器可读字段：
  - `rebuilt`
  - `downgraded`
  - `stale`
  - `canonical_untouched`
  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / `reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / `next_action` / `canonical_untouched`。

## 8. 状态写回

- 允许写入：
  - cognition/index.json
  - cognition/context-brief.md
- canonical `research-state.json`：不写 canonical（只重建投影）。
- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 `scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。

## 9. 停止、失败与恢复

**提供版边界与退出（逐字）：**

（提供版未给出边界）

- 机器可读停止条件：
  - 重建后仍漂移（交人裁决）
- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。
- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。
