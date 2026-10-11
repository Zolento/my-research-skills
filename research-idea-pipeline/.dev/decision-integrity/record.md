# 第十三轮：Decision Integrity & Contribution Progress Hardening

> 起始 HEAD `1352d66a22d78547f80558f5724ccdb3b7adbf30`。无新 R 阶段 / 无第九类对象 / 无平行状态机。

## 1. 修复前复现（`1352d66`，脚本 `/tmp/r12_probe.py`）

| # | 偏移 | 复现结果（修复前） |
|---|---|---|
| R1 | 方法开发被诊断饿死 | readiness=`MECHANISM_HYPOTHESIS`（可行动），但 `_loop_step` 仍返回 Scheduler 的 `X1`，`i2m` 未触发 |
| R2 | 跨对象拼接虚假 Insight | `insight_from_state` 取 H77 的机制、另一个方向的 lever、与机制无关的 U 预测，readiness 仍判可行动 |
| R3 | 机制证据过度升级 | 某证据仅 `depends_on: [H42]`（`supports: []`）→ `mechanism_status = MECHANISM_VERIFIED` |
| R4 | Anchor 虚假达标 | 与性能锚点**无关**的 `supported` claim → `anchor_eligibility = eligible` |
| R5 | 进展判定双向出错 | 无关新证据 + 指纹变化 → `progress=True`；同一方法版本独立验证 → `progress=False` |
| R6 | 契约版本归属 | `_method_contract_in_state` 返回**第一个**遇到的契约（含已废弃实验的旧版本） |

## 2. 修复（`scripts/insight_to_method.py` + `preset_router.py`）

**P1-1 调度冲突**：`loop_step` 在 **readiness 成立时即可**输出贡献开发步骤（不必等停滞，也不再
劫持没有就绪 insight 的健康队列）；新增 **动作状态** `advisory / planned / authorized_in_queue /
dispatched / executed`，I2M 只给**候选动作**（`candidate_method_action`），未进入合法集合时为
`advisory`，绝不声称派遣或执行。新增 `planned_validity_errors`（**I2M80** 目标已全部解决/否证、
**I2M82** 与已结束实验同设计**且**同目标重复、I2M81 缺冻结预注册仅报告不丢弃）——
`_loop_step` 对**硬缺陷**（80/82）才移出队列，**running 永不被中断**。新增
`diagnosis_decision_impact`（**I2M83**）：无决策价值的诊断不得抢占方法开发（同层重排，
不动 1—8 级优先级）。

**P1-2 虚假 Insight**：`insight_from_state` 改为**单候选绑定**（`_primary_hypothesis` 选未被否证、
优先带 lever 者；机制/lever/falsifier/预测/对照/最近邻/新颖性**全部来自同一 H 及其绑定的 U**），
未绑定对象被丢弃并记入 `binding.dropped`；`_binding_errors`（**I2M60–64**）逐引用校验绑定链，
refuted/killed/stale 对象不得使用；关联不足 → **部分就绪 + 具体缺口**。

**P1-3 证据方向**：`_mechanism_support` 取代 `_mechanism_evidence`。`depends_on` **只算依赖**
（**I2M70**），`refutes` 记否证；只有 `supports` **且**通过证据资格（观测等级/有效性/来源/
验证层级，**I2M71**）才计入；分级 `PREDICTION_OBSERVED < INTERVENTION_EFFECT < MECHANISM_SUPPORTED`，
**只有显式机制支持**才得到 `MECHANISM_VERIFIED`。

**P1-4 Anchor 资格**：`_anchor_relevant` 要求 claim/evidence 追溯到目标锚点或其**目标指标**，
或被测量该指标的实验 targeting；无关 supported claim 记入 `irrelevant_claims` 且**不能**使锚点
eligible；`supporting` 路线只能辅助（`CONDITIONAL` + 明确理由），`orthogonal` 永不达标；
gap 增加 `undecidable`；不自动改锚点（§0.2/R14 用户授权不变）。

**P1-5 五维进展**：`method_progress` 拆为 **Epistemic / Design / Implementation /
Validation / Anchor**，各自要求可核验引用；**指纹变化本身不是验证**（Design 需冻结的
`definition_digest`）；**无关新证据不加任何维度**；**同方法版本独立验证算 Validation**（无须改算法）；
**可信负结果算 Epistemic**；Implementation 需 PASS + artifact 摘要（可按版本核对）。

**P2 契约版本归属**：`method_contracts` / `select_method_contract`（按显式 experiment_id →
绑定同一方法假设的**有效**实验 → 最新版本；废弃/被取代**永不选中**并列入 `rejected`）；
`contract_version_errors`（**I2M73–78**：必须绑定 `method_digest`、实验归属一致、结果早于预注册
只能探索性、事后包装为 confirmatory 被拒）；`design_contract_errors` 增加**类型硬化**
（**I2M72**：列表字段必须是列表，字符串引用不再被拆成字符）。

## 3. 验证

| 项 | 结果 |
|---|---|
| 全量单元测试 | **1957 OK（skipped=3）**（+34 项：13 轮新场景） |
| `test_insight_to_method.py` | **68/68 OK** |
| 模块 selftest | **7/7 OK**（`insight_to_method` 37 项检查） |
| `release_check.py` | **PASS** |
| 既有行为回归 | `test_loop_runtime_correctness` 的 planned/Assurance 顺序、`test_loop_step` 语义全部保持通过（过滤器只对**硬缺陷**生效） |

## 4. 提示词同步（运行时为先）

`SKILL.md` §0.4 增「决策完整性」7 条；`references/scheduler-policy.md` §3.1 增动作状态、
readiness 即可触发、planned 有效性、诊断决策价值；`references/claim-first-policy.md` §6 增
「必须与目标锚点绑定」；`references/invocation-prompts.md` 增默认行为；
`presets/research-loop.md` 增五维进展与「不必等停滞」。

## 5. 仍未验证

**L3 科研有效性仍未验证**：无真实 GPU/外部调度/科研 A/B。本轮证明的是**决策完整性与进展判定
的软件正确性**（不可被虚假 Insight、方向误读、虚假达标或无关证据绕过），**不等于**科研能力提升。
最小干预测试的真实执行仍依赖既有 PEIG/AALG 与真实算力，本仓库不伪造执行证据。
