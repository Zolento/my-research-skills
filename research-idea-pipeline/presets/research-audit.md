# Preset: `research-audit` — 对抗审查 / Adversarial Research Audit

> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`与选中的**这一个** Preset，不要一次注入全部 16 份。

| 字段 | 值 |
|---|---|
| preset id | `research-audit` |
| 顶层入口 | `audit` |
| 执行授权 | `audit`（权限层 `read_only`）|
| registry trigger | `manual` |
| 分组 / 优先级 | `user` / 100（越小越优先）|
| 协议来源 | 提供版 `presets/research-audit.md` 正文 + 本仓库 9 节契约 |

## 1. 意图与入口

严格审查当前论点、方法、预测、创新性和实验完整性；不趁审计扩展 Discovery 候选。

- 中文意图：对科学正确性、创新性与实验公平性做对抗审查；只读，不推进 Discovery
- English intent: adversarial read-only audit of correctness, novelty and fairness
- 入口 `audit`；授权 `audit`；共同约束见 [shared-contract.md](../shared-contract.md)。

## 2. 触发条件

- 适用条件：
  - 用户要求审查
  - 关键决策前需要对抗复核
- 自动触发：**不适用**（用户显式意图优先）。
- registry 声明：`manual`；自然语言示例：「审查论文方案」、「找出当前实验的致命缺陷」、「audit my method」
- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。

## 3. 必需输入

- `research-state.json`
- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → `shared-contract.md` → **本 Preset** → 必要 references。

## 4. 允许与禁止

- 允许：
  - 报告 flaw、kill condition 与判别实验
  - 复用既有验证器给出规则号
  - 在显式请求（--apply）时产出 assurance[] 提案，交 R7 写回
- 禁止：
  - 执行 Discovery（R3—R6）
  - 改写证据或 claim 状态
  - 消耗实验预算
  - 因用户只说「审查」而隐式写 canonical
- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。

## 5. 复用的阶段、脚本与检查器

- 阶段：R7（Assurance）+ R8（证据契约）+ R13（Integrity Gate）
- 脚本 / 检查器：
  - `scripts/state_check.py`
  - `scripts/structural_equivalence_check.py`
  - `scripts/evidence_outcome.py`
  - `scripts/prediction_compare.py`
  - `scripts/execution_gate.py`
  - `scripts/rhetorical_realization.py`
- 规则号：本仓库自身产生 `PR1`—`PR10`；科学判定仍由既有规则号给出。

## 6. 执行步骤

**提供版执行协议（逐字）：**

1. 确认被审对象、其精确版本及全部证据来源；区分论文文字、代码行为与真实实验产物。
2. 按既有 R7/R10/R13 审核理论必要条件、结构近邻、替代解释、数据泄漏、容量/优化公平性、可识别性、统计有效性、Scope 和复现条件。
3. 每个实质攻击给出：目标 Claim、最强反例/替代机制、已有证据缺口、能改变判断的最小判别，以及 kill/repair/narrow 条件。
4. 如有 critical flaw，按合法 R10 修复合同处理，不直接修改 Claim Status 或自行制造闭环；需要未授权新实验时请求授权。

**在本仓库中实际执行的命令：**

| # | 步骤 | 命令 |
|---|---|---|
| 1 | 1 canonical 校验 | `python3 scripts/state_check.py <state>` |
| 2 | 2 结构等价审计 | `python3 scripts/structural_equivalence_check.py check --route <route>` |
| 3 | 3 判别力审查 | `python3 scripts/prediction_compare.py compete --state <state> --competition <CP>` |
| 4 | 4 执行门禁 | `python3 scripts/execution_gate.py peig --state <state> --experiment <X>` |

> 上表由 `preset_router.py run --preset research-audit` 实际返回，文档与代码由 `test_preset_router` 断言一致。

## 7. 输出契约

**提供版产出（逐字）：**

经证据排序的关键漏洞及其判别、状态影响和阻断条件。不生成新研究方向；不能仅靠主观评分。

- 机器可读字段：
  - `findings`
  - `severity`
  - `kill_conditions`
  - `discriminating_tests`
  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / `reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / `next_action` / `canonical_untouched`。

## 8. 状态写回

- 允许写入：
  - 审查报告
  - assurance[] 提案（写回由 R7 执行）
- canonical `research-state.json`：不写 canonical（assurance[] 只在显式 R7 写回时由 R7 落盘）。
- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 `scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。

## 9. 停止、失败与恢复

**提供版边界与退出（逐字）：**

（提供版未给出边界）

- 机器可读停止条件：
  - 审查完成即停（不自动转执行）
- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。
- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。
