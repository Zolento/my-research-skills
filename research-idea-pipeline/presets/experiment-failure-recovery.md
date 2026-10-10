# Preset: `experiment-failure-recovery` — 实验失败恢复 / Experiment Failure Recovery

> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`与选中的**这一个** Preset，不要一次注入全部 16 份。

| 字段 | 值 |
|---|---|
| preset id | `experiment-failure-recovery` |
| 顶层入口 | `continue-research` |
| 执行授权 | `engineering_recovery`（权限层 `derived`）|
| registry trigger | `event_or_manual` |
| 分组 / 优先级 | `recovery` / 50（越小越优先）|
| 协议来源 | 提供版 `presets/experiment-failure-recovery.md` 正文 + 本仓库 9 节契约 |

## 1. 意图与入口

OOM、NaN、异常退出、数据解码失败、训练崩溃、作业失联或硬件故障。

- 中文意图：区分工程故障与科学否定：先修工程，再按既有授权重发执行收据；不得把工程故障写成假设否证
- English intent: separate engineering failure from scientific refutation and repair the run
- 入口 `continue-research`；授权 `engineering_recovery`；共同约束见 [shared-contract.md](../shared-contract.md)。

## 2. 触发条件

- 适用条件：
  - 存在工程类失败（implementation/optimization/data/protocol/measurement/evaluation/baseline/power/identifiability）
- 自动触发（`recover`，需先过防重入守卫）：信号 `engineering_failure`；前提：engineering_failure_present；冷却 1 轮；每指纹上限 2 次。
- registry 声明：`event_or_manual`；自然语言示例：「训练 OOM 了」、「实验 NaN 了，检查并恢复」、「recover failed experiment」
- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。

## 3. 必需输入

- `research-state.json`
- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → `shared-contract.md` → **本 Preset** → 必要 references。

## 4. 允许与禁止

- 允许：
  - 诊断故障类别
  - 修好后经 PEIG/AALG 重新授权执行
- 禁止：
  - 把 OOM/NaN 当作科学否证
  - 无限重启同一实验
  - 跳过执行授权
- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。

## 5. 复用的阶段、脚本与检查器

- 阶段：R9（执行）+ R9.O（结果分析，仅工程分类）
- 脚本 / 检查器：
  - `scripts/evidence_outcome.py`
  - `scripts/execution_gate.py`
  - `scripts/experiment_execute.py`
  - `scripts/state_check.py`
- 规则号：本仓库自身产生 `PR1`—`PR10`；科学判定仍由既有规则号给出。

## 6. 执行步骤

**提供版执行协议（逐字）：**

1. 锁定 run_id、实验 ID、提交版本、配置、数据、日志和进程事实；判断进程是否仍在运行，禁止盲目重试。
2. 分类为 environment / data / numerical / resource / code / scientific-invalid；按最小可复现实例验证失败原因，避免无意义归因。
3. 优先采用不改变科学干预定义的工程修复；若修改 batch size、精度、步数等会影响公平性或优化条件，必须重新进行可识别性与预注册核查。
4. 生成合法重试计划，保留原失败 attempt 与 provenance，增设 attempt ID；不得把执行失败写成科学负面证据。
5. 当修复无把握或预算不足时 HOLD，记录人工授权条件。

**在本仓库中实际执行的命令：**

| # | 步骤 | 命令 |
|---|---|---|

> 上表由 `preset_router.py run --preset experiment-failure-recovery` 实际返回，文档与代码由 `test_preset_router` 断言一致。

## 7. 输出契约

**提供版产出（逐字）：**

失败分类、根因证据、最小修复、重试幂等性检查、科学有效性是否受损与下一动作。

- 机器可读字段：
  - `failure_class`
  - `scientific_effect`
  - `repair_plan`
  - `rerun_authorized`
  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / `reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / `next_action` / `canonical_untouched`。

## 8. 状态写回

- 允许写入：
  - failures[]（只经 R9.O 权限）
  - 执行账本
- canonical `research-state.json`：不写 canonical。
- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 `scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。

## 9. 停止、失败与恢复

**提供版边界与退出（逐字）：**

（提供版未给出边界）

- 机器可读停止条件：
  - 同一指纹已达尝试上限（HOLD）
  - 资源或权限不足
- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。
- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。
