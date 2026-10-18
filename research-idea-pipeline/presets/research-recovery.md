# Preset: `research-recovery` — 科研状态恢复 / Research Recovery

> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`与选中的**这一个** Preset，不要一次注入全部 16 份。

| 字段 | 值 |
|---|---|
| preset id | `research-recovery` |
| 顶层入口 | `continue-research` |
| 执行授权 | `recover_no_experiment`（权限层 `derived`）|
| registry trigger | `manual` |
| 分组 / 优先级 | `user` / 100（越小越优先）|
| 协议来源 | 提供版 `presets/research-recovery.md` 正文 + 本仓库 9 节契约 |

## 1. 意图与入口

用户换会话、换 Agent、上下文遗失或请求恢复当前科研工作；只做完整状态恢复，不擅自扩大到新实验。

- 中文意图：从磁盘而不是聊天历史恢复：重读 skill 契约、canonical state、认知投影与未完成任务
- English intent: restore skill contract, research state, memory and in-flight tasks from disk
- 入口 `continue-research`；授权 `recover_no_experiment`；共同约束见 [shared-contract.md](../shared-contract.md)。

## 2. 触发条件

- 适用条件：
  - 上下文被压缩或丢失
  - 新会话开始
  - skill 未加载
- 自动触发：**不适用**（用户显式意图优先）。
- registry 声明：`manual`；自然语言示例：「恢复之前的科研工作」、「上下文没了，恢复项目状态」、「resume research context」
- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。

## 3. 必需输入

- `research-state.json`
- `cognition/`
- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → `shared-contract.md` → **本 Preset** → 必要 references。

## 4. 允许与禁止

- 允许：
  - 重建认知投影
  - 报告未完成任务与阻塞
  - 调用 legacy_handoff detect/audit
- 禁止：
  - 修改 canonical 科学事实
  - 重置 state_version/锚点/预算
  - 补造历史预测
- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。

## 5. 复用的阶段、脚本与检查器

- 阶段：R0/R1 与 Legacy Handoff（`LH1`—`LH16`）
- 脚本 / 检查器：
  - `scripts/legacy_handoff.py`
  - `scripts/cognition.py`
  - `scripts/state_check.py`
  - `scripts/prediction_compare.py`
- 规则号：本仓库自身产生 `PR1`—`PR10`；科学判定仍由既有规则号给出。

## 6. 执行步骤

**提供版执行协议（逐字）：**

1. 从安装位置确认 Skill 版本，读取对应入口、项目规则和授权。读取路线 State / Scheduler / Cognitive Memory、进程状态、最新实验与 Git 工作区状态。
2. 检查 State/Memory 的来源版本、未完成 R10 修复、失败限制、预注册锁定状态、资源预算；必要时仅重建可派生记忆，不改历史结论。
3. 针对在途 GPU/外部任务检查实际进程和产物；未知状态不自动重试。检查配置/代码/数据版本与原任务匹配。
4. 恢复上一条已承诺且尚未完成的合法研究动作；区分真正阻断、可独立推进工作和已完成动作。
5. 形成一份有限的恢复检查点；如果用户只要求恢复，报告状态并停止。若同时明确授权继续研究，再转 `research-loop`，沿用原预算。

**在本仓库中实际执行的命令：**

| # | 步骤 | 命令 |
|---|---|---|
| 1 | 1 磁盘重载 | `python3 scripts/legacy_handoff.py detect --state <state>` |
| 2 | 2 只读兼容性审计 | `python3 scripts/legacy_handoff.py audit --state <state>` |
| 3 | 3 重建认知投影 | `python3 scripts/cognition.py build --state <state>` |
| 4 | 4 恢复理解 | `python3 scripts/cognition.py brief --state <state>` |
| 5 | 5 复用失败约束 | `python3 scripts/cognition.py recall --state <state>` |

> 上表由 `preset_router.py run --preset research-recovery` 实际返回，文档与代码由 `test_preset_router` 断言一致。

## 7. 输出契约

**提供版产出（逐字）：**

恢复的研究问题、可信机制、关键异常、被否证方向、运行中任务、下一个动作及无法恢复项。

- 机器可读字段：
  - `recovered`
  - `unrecovered`
  - `in_flight`
  - `blockers`
  - `next_action`
  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / `reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / `next_action` / `canonical_untouched`。

## 8. 状态写回

- 允许写入：
  - cognition/index.json
  - cognition/context-brief.md
  - handoff 报告
- canonical `research-state.json`：不写 canonical。
- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 `scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。

## 9. 停止、失败与恢复

**提供版边界与退出（逐字）：**

（提供版未给出边界）

- 机器可读停止条件：
  - 严重兼容性错误（LH blocking）
  - 状态无法解析
- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。
- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。
