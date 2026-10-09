# Preset: `context-drift-recovery` — 上下文漂移恢复 / Context Drift Recovery

> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`与选中的**这一个** Preset，不要一次注入全部 16 份。

| 字段 | 值 |
|---|---|
| preset id | `context-drift-recovery` |
| 顶层入口 | `continue-research` |
| 执行授权 | `recover_no_experiment`（权限层 `derived`）|
| registry trigger | `event` |
| 分组 / 优先级 | `recovery` / 20（越小越优先）|
| 协议来源 | 提供版 `presets/context-drift-recovery.md` 正文 + 本仓库 9 节契约 |

## 1. 意图与入口

检测到 Skill/Context 版本不一致、关键规则不在活跃上下文、当前动作偏离锚点、压缩/会话重启等有记录的信号。没有程序性触发器时只作为人工调用协议。

- 中文意图：从磁盘重建 skill 契约、canonical state 与认知投影，检测并修复投影漂移
- English intent: rebuild the skill contract, state and projections from disk
- 入口 `continue-research`；授权 `recover_no_experiment`；共同约束见 [shared-contract.md](../shared-contract.md)。

## 2. 触发条件

- 适用条件：
  - 索引缺失或与 canonical 不一致
  - handoff 记录缺失
  - 会话上下文丢失
- 自动触发（`recover`，需先过防重入守卫）：信号 `context_drift`, `memory_drift`；前提：drift_detected；冷却 0 轮；每指纹上限 2 次。
- registry 声明：`event`；自然语言示例：「Skill 规则丢了，恢复上下文」、「上下文压缩以后重新确认规则」、「recover from context drift」
- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。

## 3. 必需输入

- `research-state.json`
- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → `shared-contract.md` → **本 Preset** → 必要 references。

## 4. 允许与禁止

- 允许：
  - 重建投影
  - 报告漂移原因与影响范围
- 禁止：
  - 依赖聊天历史作为事实来源
  - 改 canonical state
- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。

## 5. 复用的阶段、脚本与检查器

- 阶段：R11（状态同步）+ 认知投影重建
- 脚本 / 检查器：
  - `scripts/cognition.py`
  - `scripts/legacy_handoff.py`
  - `scripts/state_check.py`
- 规则号：本仓库自身产生 `PR1`—`PR9`；科学判定仍由既有规则号给出。

## 6. 执行步骤

**提供版执行协议（逐字）：**

1. 暂停派遣新副作用动作，保存当前动作和触发事件；避免重复记录同一状态版本的事件。
2. 重新从磁盘加载 Skill 核心规则、当前路线锚点、State、Scheduler、Cognitive Memory 与执行检查点；检查版本与权限。
3. 核验下一动作是否仍合法，是否重复完成或被失败证据禁止；记录漂移类型和已恢复的契约。
4. 可恢复则回到中断动作；不可恢复则 HOLD，报告唯一明确的阻断原因。不得在恢复流程内递归调用自身。

**在本仓库中实际执行的命令：**

| # | 步骤 | 命令 |
|---|---|---|
| 1 | 1 检测漂移 | `python3 scripts/preset_router.py trigger --state <state>` |
| 2 | 2 重建投影 | `python3 scripts/cognition.py build --state <state>` |
| 3 | 3 校验一致 | `python3 scripts/cognition.py check --state <state>` |

> 上表由 `preset_router.py run --preset context-drift-recovery` 实际返回，文档与代码由 `test_preset_router` 断言一致。

## 7. 输出契约

**提供版产出（逐字）：**

recovered/hold、前后版本与动作、恢复证据、仍存在的缺口。

- 机器可读字段：
  - `drift_reasons`
  - `rebuilt`
  - `canonical_untouched`
  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / `reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / `next_action` / `canonical_untouched`。

## 8. 状态写回

- 允许写入：
  - cognition/index.json
  - cognition/context-brief.md
- canonical `research-state.json`：不写 canonical。
- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 `scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。

## 9. 停止、失败与恢复

**提供版边界与退出（逐字）：**

（提供版未给出边界）

- 机器可读停止条件：
  - 重建后仍不一致（交人裁决）
- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。
- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。
