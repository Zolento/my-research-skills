# Insight-to-Method Transition（I2M）：架构升级记录

> 分支 `research-idea-pipeline/skill-rsi-dev`；起始 HEAD `cf3c23437b398008678e85a0073757e1205f9805`。
> 无新 R 阶段、无第九类 Research State 对象、无平行状态机。

## 1. 问题：为什么旧机制无法推动方法实现

策略文档 `references/scheduler-policy.md` §3.1 **本来就写着「防止诊断替代方法探索」**，但运行时没有
任何东西能执行它。可复现失败路径（侦察核实）：

1. `scheduler.json` 队列里诊断动作处于最高层；`strategy_dispatch`（`preset_router.py:2122`）
   只能在**既有合法集合内**重排，`_loop_step`（`:1940`）回落到 `next_actions[0]`；
2. 诊断产生 `actual_information_gain == "zero"`；`trailing_zero_streak`
   （`prediction_compare.py:2066`）累计到 2 → `signal_snapshot`（`preset_router.py:1304`）报停滞；
3. `stagnation-breaker` 只**输出建议字符串**（`writes=[]`，`:2737`）；
   `diagnosis_switch` 的 `EXPLORE_METHOD_UNDER_UNCERTAINTY` 同样只是许可措辞；
4. 下一轮仍然回到 Scheduler 的诊断/修复动作；直到 `execution_gate.py:302` 触发 T8
   （`STOP_DIAGNOSIS`）→ `R5.1→R3/R6`，即**文献检索 + 候选再生**，仍不是方法合成。

**根因：动作词表里没有任何动作/算子表示「合成一个新方法/算法/目标/结构」，也没有 readiness、
设计契约、最小干预测试与方法进展信号。** 唯一存在的「方法」产物是实验臂 `role=method`
（`schemas/preflight-protocol.schema.json`），也就是说方法必须由人先建好。

## 2. 实现（`scripts/insight_to_method.py`，+ 运行时接线）

| 能力 | 函数 | 产物落点（复用既有对象） |
|---|---|---|
| A Insight Readiness | `insight_readiness` / `insight_from_state` | 由 `hypotheses[]`（`statement`/`operator`/`intervention_axis`/`falsifier`/`nearest_prior`/`novelty_source`）与 `uncertainties[].cheapest_discriminating_test` **派生**，不自建事实源 |
| B Method Synthesis | `synthesize_methods` / `synthesis_errors` | `hypotheses[].method`（R3/R6 已拥有该集合）|
| C Design Contract | `design_contract_errors` / `contract_from_candidate` | `experiments[].preregistration.method_contract`（R8 既有冻结机制）|
| D Minimal Intervention Test | `minimal_test_errors` / `test_failure_errors` | R8 登记 `planned` 实验；PEIG/AALG/预算/审批门禁不变 |
| E Development Loop + 进展 | `method_progress` / `advance` | 决策记录；进展 = 方法指纹变化 **且** 新执行证据 |
| 锚点兼容 | `anchor_kind`/`anchor_eligibility`/`anchor_role_errors`/`anchor_gap`/`anchor_change_errors`/`anchor_path` | 复用 SKILL §0.1 三层锚点、`claim-first-policy.md` §6 三值资格、§0.2 变更单 |
| Loop 步骤 | `transition` / `loop_step` / `signal_snapshot` | `preset_router._loop_step` 末尾、`stagnation-breaker`、`signal_snapshot` |

**readiness 的诚实性**：机制是否「已验证」由 **state 中的观测证据**决定，不由 insight 自述决定；
自称 `VERIFIED` 而无证据 → `I2M14`，且结论仍为 `MECHANISM_HYPOTHESIS`。
允许基于未证实的机制提出方法，但 readiness 明确写着「不是机制已被证实」。

**运行时接线（关键，行为可验证）：**
- `preset_router._loop_step`：I2M 步骤**只在该函数末尾**被咨询——所有硬门禁（完整性/未决攻击/
  失效传播/Assurance/planned 工作/预算）都已经有机会 `return`，因此 I2M 无法越过它们；
- `_handle_stagnation_breaker`：从「只写建议」改为在可执行时交出 I2M 步骤
  （`writes` 与 `next_action` 随 I2M 步骤，`next_intervention` 仍保留 switch 措辞）；
- `signal_snapshot`：新增 `signals["i2m"]`（readiness/path/contribution/gap/next_step/trigger）；
- RSI：新增 **PE17**——证据类型为 `method_synthesis`/`narrative`/`self_assessment`/
  `candidate_generation` 时不得作为 L3 能力提升证据。

## 3. 实测行为变化（对抗性验收，`test_insight_to_method.py` 34 项）

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 停滞 + 机制可用（方法锚点）| 回到 Scheduler 诊断动作 | **`phase=I2M, step=Synthesize`**，`trigger=diagnosis_stagnant(zero_streak=2, switch=REDESIGN_QUESTION)` |
| 非停滞 | Scheduler 动作 | **不变**（`R3—R6/R8`，`i2m=False`）——不劫持健康队列 |
| 理论 / 现象 / 基准 / 可行性 / 负结果主锚点 | 无区分 | **`stage=anchor_native`**，产出该锚点贡献类型，不转算法 |
| 已冻结方法契约 | 无从识别 | `trigger=method_contract_present`；已登记最小实验走既有 `R8/R9` PEIG/AALG 分支 |
| 改写解释 | 可能被当作新进展 | `trailing_zero_streak` 只读执行记录；重写 `narrative_view` 后 `zero_streak` 不变 |

## 4. 覆盖的对抗场景（任务 §六 1—12 + 锚点补充）

1 停滞仍生成解释 → 必须转向方法；2 机制假设可驱动方法但不得标为已证实（含自称验证被记录）；
3 诊断不改变决定 → 转向合成/判别/停止；4 不可操作 Insight 不得包装成方法；
5 缺数学定义/干预/可证伪预测/对照/停止条件 → 契约拒绝（含纯超参与无证据声称 supported）；
6 无代码变更或可信结果 → 不得宣称方法完成；7 缺执行资格/门禁未过 → 不得用 GPU；不公平对比拒绝；
8 失败未分类或事后改预注册 → 拒绝，失败四分类映射到四种决策；
9 不同主锚点选择不同路径（方法类 vs 非方法类）；10 重启/恢复确定性 + RSI 晋升门禁未受影响；
11 合法旧 state 与旧产物仍可读（无新增必填字段）；12 新证据/冻结契约改变下一动作；
13（补充）主锚点部分满足、方法局部有效未达标、supporting 可证伪、orthogonal 保留价值、
主锚点不可达、非方法主锚点、**无用户授权的锚点变更被拒绝**。
另含端到端：Problem/Insight → 2 候选 → 冻结契约 → 最小实验计划 → 结果回写 → 下一决策。

## 5. 验证

| 项 | 结果 |
|---|---|
| 全量单元测试 | **1923 OK（skipped=3）**（新增 34 项；修复前 1889）|
| 模块 selftest | **7/7 OK**（新增 `insight_to_method` 24 项检查）|
| `release_check.py` | **PASS**（新套件纳入 `EXPECTED_TEST_SUITES`，新 selftest 纳入 `SELFTEST_MODULES`）|
| 行为变化证据 | §3 的实测输出（非提示词自证）|

## 6. 兼容性

- **Research State**：无新增必填字段、无新增集合；`method` 挂在既有 `hypotheses[]`，
  `method_contract` 挂在既有 `experiments[].preregistration`（两者都是宽松校验位置；
  `structural_signature` 与 `claims[].contract` 是严格校验，**未触碰**）。旧 state 通过 `state_check`。
- **Scheduler**：八级优先级不变；`method_*` 动作类型只是同层内可选项，不提升优先级、不解阻
  stop rule；I2M 只在门禁之后咨询。
- **Loop**：`_loop_step` 的既有顺序（todo → 损坏凭证 → 缺失分析 → Assurance → planned →
  重建投影 → 待审 → 未知）全部优先于 I2M。
- **Policy Evolution**：晋升/等级/审批链路未改；只新增 PE17 禁令。
- **主锚点**：三层锚点体系与 §0.2 授权边界不变；I2M 不得替换主锚点或放宽冻结标准。

## 7. 仍未验证

- **L3 科研有效性仍未验证**：没有真实 GPU / 外部调度 / 科研 A/B；本轮证明的是
  「方法从 Insight 到最小干预的**流程与门禁**可执行且不可被叙事绕过」，**不是**科研能力提升。
- 最小干预测试的**实际执行**仍依赖既有 PEIG/AALG 与真实算力；本仓库不伪造执行证据。
- `pairing`/`method_progress` 的指纹来自回放与状态字段，不是硬件执行证明。
