# Preset: `resource-recovery` — 资源与执行恢复 / Resource & Execution Recovery

> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`与选中的**这一个** Preset，不要一次注入全部 16 份。

| 字段 | 值 |
|---|---|
| preset id | `resource-recovery` |
| 顶层入口 | `continue-research` |
| 执行授权 | `runtime_recovery`（权限层 `derived`）|
| registry trigger | `event_or_manual` |
| 分组 / 优先级 | `recovery` / 40（越小越优先）|
| 协议来源 | 提供版 `presets/resource-recovery.md` 正文 + 本仓库 9 节契约 |

## 1. 意图与入口

GPU/CPU/存储不足、依赖变化、环境失联、队列阻断、时间或计算预算不足。

- 中文意图：诊断执行环境、依赖与预算，产出可执行的最小修复清单；本预设不启动任何作业
- English intent: diagnose environment, dependencies and budget; produce a repair checklist
- 入口 `continue-research`；授权 `runtime_recovery`；共同约束见 [shared-contract.md](../shared-contract.md)。

## 2. 触发条件

- 适用条件：
  - 资源或环境类失败
  - 预算/配额阻断
  - 依赖或环境探测失败
- 自动触发（`recover`，需先过防重入守卫）：信号 `resource_blocked`；前提：resource_failure_present；冷却 2 轮；每指纹上限 2 次。
- registry 声明：`event_or_manual`；自然语言示例：「GPU 不够了」、「环境崩溃，恢复执行」、「recover resource block」
- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。

## 3. 必需输入

- `research-state.json`
- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → `shared-contract.md` → **本 Preset** → 必要 references。

## 4. 允许与禁止

- 允许：
  - 读环境探测与执行账本
  - 给出降配/排队/清理方案
- 禁止：
  - 启动或重启 GPU 作业
  - 改预算策略文件
  - 把资源失败写成科学结论
- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。

## 5. 复用的阶段、脚本与检查器

- 阶段：PEIG/AALG 执行授权 + `env_probe`
- 脚本 / 检查器：
  - `scripts/env_probe.py`
  - `scripts/experiment_execute.py`
  - `scripts/execution_gate.py`
  - `scripts/state_check.py`
- 规则号：本仓库自身产生 `PR1`—`PR10`；科学判定仍由既有规则号给出。

## 6. 执行步骤

**提供版执行协议（逐字）：**

1. 查询真实资源使用和在途作业，不根据聊天记录假定进程已停止；识别可重入和不能重复的外部副作用。
2. 记录当前执行意图、任务 ID、尝试次数、检查点及预算余额；不得重置配额或重复派遣已完成实验。
3. 寻找符合原科学协议的资源替代、可在 CPU 上完成的验证、理论推导或必要文献工作；改变科学条件需要重新预注册/比较设计。
4. 可安全恢复则重启/继续，不能恢复则 HOLD；禁止通过减少必要对照伪造可执行性。

**在本仓库中实际执行的命令：**

| # | 步骤 | 命令 |
|---|---|---|
| 1 | 1 环境探测 | `python3 scripts/env_probe.py` |
| 2 | 2 执行账本 | `python3 scripts/experiment_execute.py scheduler-check --state <state>` |
| 3 | 3 修复后恢复 | `python3 scripts/execution_gate.py peig --state <state> --experiment <X>` |

> 上表由 `preset_router.py run --preset resource-recovery` 实际返回，文档与代码由 `test_preset_router` 断言一致。

## 7. 输出契约

**提供版产出（逐字）：**

资源事实、可执行替代、预算变化、实际派遣状态、恢复条件。

- 机器可读字段：
  - `blockers`
  - `repair_checklist`
  - `resume_conditions`
  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / `reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / `next_action` / `canonical_untouched`。

## 8. 状态写回

- 允许写入：
  - 诊断报告
- canonical `research-state.json`：不写 canonical。
- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 `scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。

## 9. 停止、失败与恢复

**提供版边界与退出（逐字）：**

（提供版未给出边界）

- 机器可读停止条件：
  - 资源不可恢复（HOLD）
- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。
- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。
