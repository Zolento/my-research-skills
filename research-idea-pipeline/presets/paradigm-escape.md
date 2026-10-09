# Preset: `paradigm-escape` — 范式逃逸 / Paradigm Escape

> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`与选中的**这一个** Preset，不要一次注入全部 16 份。

| 字段 | 值 |
|---|---|
| preset id | `paradigm-escape` |
| 顶层入口 | `explore` |
| 执行授权 | `discover_only`（权限层 `discovery`）|
| registry trigger | `manual_or_stagnation` |
| 分组 / 优先级 | `user` / 100（越小越优先）|
| 协议来源 | 提供版 `presets/paradigm-escape.md` 正文 + 本仓库 9 节契约 |

## 1. 意图与入口

当前问题表示可能局部最优，需要改变建模对象和假设，而不是继续修改 loss、超参数或模块名称。

- 中文意图：执行 Representation Reset：在数学对象、变量、假设、目标与约束五个面上重建模，并给出可机械核验的结构性差异与判别实验；不是再生成一个算法变体
- English intent: structural representation reset across object/variable/assumption/objective/constraint
- 入口 `explore`；授权 `discover_only`；共同约束见 [shared-contract.md](../shared-contract.md)。

## 2. 触发条件

- 适用条件：
  - 当前表示被判定为局部最优或同构候选堆积
  - 用户明确要求换范式
- 自动触发（`recommend`，需先过防重入守卫）：信号 `stagnation`；前提：registry trigger=manual_or_stagnation；权限层 discovery（可在授权的 Autonomous Loop 内自动触发受控 Discovery）；冷却 0 轮；每指纹上限 1 次。
- registry 声明：`manual_or_stagnation`；自然语言示例：「跳出当前思路」、「换一个完全不同的数学建模角度」、「escape local paradigm」
- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。

## 3. 必需输入

- `research-state.json`
- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → `shared-contract.md` → **本 Preset** → 必要 references。

## 4. 允许与禁止

- 允许：
  - 提出新的数学对象/变量/假设/目标/约束
  - 用结构等价审计核验差异
- 禁止：
  - 把参数或模块替换当作范式改变
  - 跳过结构等价审计自证新颖
  - 未经授权启动 GPU 或执行实验
  - 修改研究主锚点
- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。

## 5. 复用的阶段、脚本与检查器

- 阶段：R3—R6（Discovery）+ R7（结构等价审计）
- 脚本 / 检查器：
  - `scripts/state_check.py`
  - `scripts/structural_equivalence_check.py`
  - `scripts/cognition.py`
  - `scripts/strategy_memory.py`
- 规则号：本仓库自身产生 `PR1`—`PR9`；科学判定仍由既有规则号给出。

## 6. 执行步骤

**提供版执行协议（逐字）：**

1. 确认停滞有实证迹象；保存当前研究锚点、经过核验的观察/反例和原路线，暂停同构优化，**不清空**历史与失败预算。
2. 构造与当前方法无关的 Problem Skeleton：可观测量、不可观测量、物理约束、目标变量、必要假设、已排除条件。标明哪些是数学必然，哪些只是当前实现选择。
3. 调用已有 R3—R6 的 P1—P6 探索协议；严格保持探索岛隔离，P3 只输出规范化 typed intermediate，P4 只读取允许的抽象骨架，不能提前混入其他岛候选。
4. 重点寻找新的变量/表示空间、信息结构、约束集合、目标、动力学、可识别性或优化层级；每个候选写明旧表述被改变的部分、理论后果、适用条件与最强反例。
5. 要求候选提出与旧模型不同的可检验预测或明确不可检验的原因。恢复完整历史后，使用 R4 结构指纹、R5 文献近邻和 R7 Assurance 检查伪创新。
6. 形成最多 3 个实质不同的优先候选；为每个提出低成本判别干预。不能达到 3 个有效候选就如实报告；不为达数量编造。

**在本仓库中实际执行的命令：**

| # | 步骤 | 命令 |
|---|---|---|
| 1 | 1 冻结现状表示 | `python3 scripts/cognition.py brief --state <state>` |
| 2 | 2 逐轴替换 | `编辑候选 H：object/variable/assumption/objective/constraint` |
| 3 | 3 结构差异核验 | `python3 scripts/structural_equivalence_check.py check --route <route>` |
| 4 | 4 判别实验 | `python3 scripts/prediction_compare.py freeze --state <state> --experiment <X>` |
| 5 | 5 计算下一动作 | `python3 scripts/strategy_memory.py recommend --state <state>` |

> 上表由 `preset_router.py run --preset paradigm-escape` 实际返回，文档与代码由 `test_preset_router` 断言一致。

## 7. 输出契约

**提供版产出（逐字）：**

旧表示的约束、新表示的数学对象、独立预测、最小判别、结构近邻与下一步候选；未证实不写为事实。

- 机器可读字段：
  - `representation_before`
  - `representation_after`
  - `axes_changed`
  - `discriminating_test`
  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / `reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / `next_action` / `canonical_untouched`。

## 8. 状态写回

- 允许写入：
  - research-state.json（hypotheses/claims 只经 R3—R6 权限）
- canonical `research-state.json`：只经 R3—R6 写 hypotheses[]/claims[] 候选。
- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 `scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。

## 9. 停止、失败与恢复

**提供版边界与退出（逐字）：**

这是 Discovery，不自动启动未授权实验；挑战主锚点可以存档，但改变锚点须用户授权。无法产生结构差异则停止再次发散并记录为什么失败。

- 机器可读停止条件：
  - 五个面均无法改变（记录边界并停手）
  - 新表示无法给出可判别预测
- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。
- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。
