# Preset: `scientific-replanning` — 科学重规划 / Scientific Replanning

> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`与选中的**这一个** Preset，不要一次注入全部 16 份。

| 字段 | 值 |
|---|---|
| preset id | `scientific-replanning` |
| 顶层入口 | `continue-research` |
| 执行授权 | `plan`（权限层 `advisory`）|
| registry trigger | `manual_or_blocked` |
| 分组 / 优先级 | `user` / 100（越小越优先）|
| 协议来源 | 提供版 `presets/scientific-replanning.md` 正文 + 本仓库 9 节契约 |

## 1. 意图与入口

当前路线的关键假设被否证、目标暂不可达或研究资源条件变化，需要调整行动计划而不擅自换主锚点。

- 中文意图：依据否证、停滞与资源约束调整研究策略：改的是下一步做什么，不是改写既有证据
- English intent: adjust strategy from refutations, stagnation and constraints
- 入口 `continue-research`；授权 `plan`；共同约束见 [shared-contract.md](../shared-contract.md)。

## 2. 触发条件

- 适用条件：
  - 出现否证/停滞/约束变化
  - 用户明确要求重规划
- 自动触发（`recommend`，需先过防重入守卫）：信号 `stagnation`；前提：registry trigger=manual_or_blocked；仅推荐，不自动执行；冷却 0 轮；每指纹上限 1 次。
- registry 声明：`manual_or_blocked`；自然语言示例：「重新规划当前路线」、「这条路线被否证了，重新制定计划」、「replan research」
- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。

## 3. 必需输入

- `research-state.json`
- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → `shared-contract.md` → **本 Preset** → 必要 references。

## 4. 允许与禁止

- 允许：
  - 重排实验/干预优先级
  - 登记新的不确定性
  - 通过 R10/R11 改 claim 状态
- 禁止：
  - 为了绕过门禁而重跑同一实验
  - 把无效执行当作否证
- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。

## 5. 复用的阶段、脚本与检查器

- 阶段：R10/R11（状态迁移）+ R14（策略）
- 脚本 / 检查器：
  - `scripts/cognition.py`
  - `scripts/strategy_memory.py`
  - `scripts/prediction_compare.py`
  - `scripts/evidence_outcome.py`
- 规则号：本仓库自身产生 `PR1`—`PR9`；科学判定仍由既有规则号给出。

## 6. 执行步骤

**提供版执行协议（逐字）：**

1. 恢复锚点、已完成与无效实验、失败边界、剩余资源、合法行动集合。
2. 将已验证事实与未证实解释分开；提出至少两条可执行的替代研究路径，给出各自的关键依赖、判别试验和失败条件。
3. 对路径比较科学重要性、执行依赖、证据质量、预期决策变化和成本；不得简单以 EIG 或模型自评分选优。
4. 标记 retain / defer / abandon / request_anchor_change。需要变更项目主锚点只能准备 Anchor Change Order 请求用户授权；不得自动执行。
5. 选一项合法下一动作，写入现有计划/调度通道并报告是否实际派遣。未经明确执行授权只生成建议。

**在本仓库中实际执行的命令：**

| # | 步骤 | 命令 |
|---|---|---|
| 1 | 1 汇总否证 | `python3 scripts/state_check.py <state> --quiet` |
| 2 | 2 停手约束 | `python3 scripts/evidence_outcome.py constraints --state <state>` |
| 3 | 3 重排下一步 | `python3 scripts/strategy_memory.py recommend --state <state>` |
| 4 | 4 必要时改状态 | `python3 scripts/evidence_outcome.py apply --state <state> ...` |

> 上表由 `preset_router.py run --preset scientific-replanning` 实际返回，文档与代码由 `test_preset_router` 断言一致。

## 7. 输出契约

**提供版产出（逐字）：**

路线重排、弃置理由、资源约束、下一决策及可证伪的成功/失败标准。

- 机器可读字段：
  - `plan_before`
  - `plan_after`
  - `refutations_used`
  - `next_action`
  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / `reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / `next_action` / `canonical_untouched`。

## 8. 状态写回

- 允许写入：
  - research-state.json（只经 R10/R11 权限）
  - 策略记忆
- canonical `research-state.json`：不写 canonical（只产出计划）。
- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 `scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。

## 9. 停止、失败与恢复

**提供版边界与退出（逐字）：**

（提供版未给出边界）

- 机器可读停止条件：
  - 无合法改法（HOLD 并交人裁决）
- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。
- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。
