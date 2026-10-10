# Preset: `discovery-replay` — 发现能力回放评估 / Discovery Replay Evaluation

> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`与选中的**这一个** Preset，不要一次注入全部 16 份。

| 字段 | 值 |
|---|---|
| preset id | `discovery-replay` |
| 顶层入口 | `continue-research` |
| 执行授权 | `evaluation_only`（权限层 `read_only`）|
| registry trigger | `manual_or_scheduled` |
| 分组 / 优先级 | `evolution` / 90（越小越优先）|
| 协议来源 | 提供版 `presets/discovery-replay.md` 正文 + 本仓库 9 节契约 |

## 1. 意图与入口

评价 CIE / Strategy Evolution 是否真的改善科学发现和下一动作质量，而不是证明 Prompt 看起来更好。

- 中文意图：用隔离隐藏结果的历史回放比较策略改动前后的表现，只报告分维度指标与样本量
- English intent: compare strategy variants on leak-checked replay cases, per dimension only
- 入口 `continue-research`；授权 `evaluation_only`；共同约束见 [shared-contract.md](../shared-contract.md)。

## 2. 触发条件

- 适用条件：
  - 策略改动后需要回归验证
  - 怀疑自进化无效
- 自动触发（`recover`，需先过防重入守卫）：信号 `evolution_due`；前提：strategy_revision_pending；冷却 1 轮；每指纹上限 2 次。
- registry 声明：`manual_or_scheduled`；自然语言示例：「做一次历史研究回放」、「检验自进化策略是否真的更好」、「evaluate discovery replay」
- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。

## 3. 必需输入

- `research-state.json`
- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → `shared-contract.md` → **本 Preset** → 必要 references。

## 4. 允许与禁止

- 允许：
  - 运行回放与消融
  - 报告每维指标、样本量与不可评维度
- 禁止：
  - 触碰隐藏答案
  - 把合成回放当作真实科研能力
  - 输出加权总分
- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。

## 5. 复用的阶段、脚本与检查器

- 阶段：`RP1`—`RP5`（回放与泄漏防护）
- 脚本 / 检查器：
  - `scripts/research_replay.py`
  - `scripts/strategy_memory.py`
  - `scripts/cognition.py`
- 规则号：本仓库自身产生 `PR1`—`PR10`；科学判定仍由既有规则号给出。

## 6. 执行步骤

**提供版执行协议（逐字）：**

1. 使用现有 research_replay / fixture 机制，选择含历史冻结点、隐藏后续结果和独立答案来源的案例。隔离隐藏信息，防止被检索索引、Memory 或候选生成提前看到。
2. 用相同初始 State、模型、预算、合法工具、停止标准比较 baseline 与新策略；尽可能多次重复运行并控制随机波动。
3. 评估：有效预测准确/校准、判别干预质量、结构创新、无价值诊断次数、下一决策变化、科学证据有效性与资源消耗。
4. 不把候选生成 Agent 的自评当作主要评判；已知历史结论或独立验证与盲评优先。
5. 清楚区分单元测试、合成端到端、真实 Agent A/B 和真实科学新发现的证据等级。策略未优于 baseline 应保留旧策略或标记试验性，不自动晋升。

**在本仓库中实际执行的命令：**

| # | 步骤 | 命令 |
|---|---|---|
| 1 | 1 加载 case | `python3 scripts/research_replay.py validate --dir examples/replay/adversarial` |
| 2 | 2 回放 | `python3 scripts/research_replay.py suite --dir examples/replay/adversarial --runs 2` |
| 3 | 3 消融 | `python3 scripts/research_replay.py ablate --dir examples/replay/adversarial --runs 2` |
| 4 | 4 RSI 消融 | `python3 scripts/research_replay.py ablate --dir examples/replay/adversarial --rsi --runs 2` |

> 上表由 `preset_router.py run --preset discovery-replay` 实际返回，文档与代码由 `test_preset_router` 断言一致。

## 7. 输出契约

**提供版产出（逐字）：**

复现实验条件、隔离校验、对照结果与不确定性、是否建议 promotion 和尚未验证的推断。

- 机器可读字段：
  - `per_dimension`
  - `sample_size`
  - `undifferentiated_arms`
  - `limitations`
  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / `reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / `next_action` / `canonical_untouched`。

## 8. 状态写回

- 允许写入：
  - 回放报告
- canonical `research-state.json`：不写 canonical。
- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 `scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。

## 9. 停止、失败与恢复

**提供版边界与退出（逐字）：**

（提供版未给出边界）

- 机器可读停止条件：
  - 样本不足时明确拒绝下结论
- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。
- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。
