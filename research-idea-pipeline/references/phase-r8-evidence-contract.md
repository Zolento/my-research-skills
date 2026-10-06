# R8 — 证据契约（evidence-contract）

**R8 定义「什么算成功」。** 它为每条 central claim 建一张证据契约，从契约派生 planned 实验，
并在**结果出现之前**冻结 `preregistration`。R9 产生证据，R13 逐条核对预测与实际 outcome。

---

## R8.0 定位与边界

| 项 | R8 做 | R8 不做 |
|---|---|---|
| 定义 | **定义 success**，冻结 `preregistration` | 不执行实验，不写 `result` |
| claim | 为**已存在**的 claim 建契约 | **不创建 claim**（claim 由 R3—R6 创建） |
| 新颖性 | 引用 R7 的 `S-Lit` 碰撞结论 | **不重做**新颖性检索；**不派 venue 角色** |
| 审计 | 审「**计划中的**证据契约」 | **不要求 artifact**（无 code / logs / failed runs） |
| status | 证据驱动的**单向升级** | 不得降级，不得写 `killed` / `contradicted` |

**三个阶段的分工（不得混为一谈）：**

```text
R8  defines success      冻结 preregistration
R9  produces evidence    执行，写 result_at_state_version
R13 audits the definition 逐条核对 prediction 与实际 outcome
```

**R8 不摘果子：** R8 期没有实验结果。写进契约的每个 outcome 都是**预测**。
不得把预测表述为已观察到的结论。

**事后修改契约必须留痕：** 在 `frozen_at_state_version` 之后改动 `outcomes`，
**必须**追加 `preregistration.amended[]`（含 `at_state_version` / `reason`）。
静默改写 = 违反 R13 的 Integrity Gate。

**锚点约束：** 贡献类型必须与主锚点一致（见 [../SKILL.md](../SKILL.md) §0.1、§2）。
**理论**锚点的契约必须含证明 / 反例 / 边界条件；**性能**锚点必须含同算力·同数据·同调参的
公平比较与显著性检验；**基准**锚点必须含新基准的构造与失败模式分析。
锚点与契约不一致时，**必须显式指出**。

---

## R8.1 输入

| 输入 | 必填 | 说明 |
|---|---|---|
| `claims[]` | ✅ | 来自 R3—R6 的 seed claim（`status: ungrounded`） |
| `evidence[]` | ✅ | 已有证据台账；契约的 `supporting_required` 引用它 |
| `assurance[]` | ✅ | 来自 R7 的六攻击面五元组；契约的必答项来源 |
| 一个或多个 idea | ✅ | 来自 R3—R6 的候选清单，或用户直接提供 |
| 资源约束 | ❌ | 算力 / 数据 / 人力 / 时间 / 开源要求 |

**信息完整性检查（开工前）：** 每条 central claim 是否有非空 `falsifier`（`V1`）？
写不出 `falsifier` 的 claim 不是科学主张，**先回 R3—R6 或 R7**，不得在 R8 补造。

---

## R8.2 流程

### R8.2.1 把 R7 的攻击结论转成契约的必答项

R7 的每个攻击面输出五元组 `(Attack, Target Claim, Alternative, Discriminating Test, Kill Condition)`。
R8 **逐条接收**，不重新发明攻击。映射关系如下：

| R7 五元组 | 落到契约的键 |
|---|---|
| `Target Claim` | 该契约所属的 `claims[].id` |
| `Alternative` | `nearest_alternative` |
| `Discriminating Test` | `minimal_discriminating_experiment` |
| `Kill Condition` | `kill_rule` |
| `Attack` | `refuting` 与 `critical_assumptions` |

**硬规则：**

- `assurance[].verification_tier` **上限是 `T0`** —— LLM reviewer 的产物不得据此升级任何
  claim 状态（`V20`）。契约可以引用它，**不得**把它当 `T1` 以上证据。
- R7 判为 `TBD` 的判别实验，R8 **必须**转成一个真实的 `planned` `X` 条目，或落一条
  `uncertainties[]`（`U` 的 `cheapest_discriminating_test` 可为 `TBD`，见 `V7`）。
  不得把 `TBD` 原样留在 `minimal_discriminating_experiment` 里进入 R9。

### R8.2.2 每条 central claim 一张证据契约

契约写在 `claims[].contract`。键名**逐字**取自
[templates/research-state.template.json](../templates/research-state.template.json)，
本表与模板**必须逐字一致**。

| 键 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `statement` | 字符串 | ✅ | 该 claim 的一句话主张（与 `claims[].statement` 同源） |
| `scope` | 字符串 | ✅ | 结论成立的范围；`NARROW_SCOPE` / `ACCEPTED_LIMITATION` 的落点 |
| `critical_assumptions` | `AS` id 数组，可为 `[]` | ✅ | 该 claim 成立所依赖的假设 |
| `supporting_required` | `E` id 数组 | ✅ | 「什么样的证据才算支持」；R9 据此取实验 |
| `refuting` | 字符串 | ✅ | 什么样的观察构成**反驳** |
| `nearest_alternative` | 字符串 | ✅ | 最简替代解释；取自 R7 `R-Causal` 的五元组 |
| `minimal_discriminating_experiment` | 存在的 `X` id | ✅ | 能区分 claim 与 `nearest_alternative` 的最小实验 |
| `expected_outcomes` | 对象：`O<k>` → 文本 | ✅ | 预测的观察 → 它支持谁。键必须与派生实验的 `preregistration.outcomes[].id` **一一对应** |
| `kill_rule` | 字符串 | ✅ | **必须可判定** |
| `expansion_rule` | 字符串 | ✅ | 什么条件下可扩大 `scope` |

**范围：** 只为 **central claim** 建契约。子 claim 继承其父契约的 `scope` 与 `refuting`，
不单独建契约。

### R8.2.3 `kill_rule` 与 `expansion_rule` 必须可判定

两条规则都必须写成「**若观察 `O2` 则 `X`**」的形式。写出观察条件与后果。

**写不出可判定 `kill_rule` 的 claim，不得进入 R9。** `V1` 的 `falsifier` 是它的前置条件，
但 `falsifier` 不等于 `kill_rule` —— `falsifier` 说「什么算错」，
`kill_rule` 说「观察到什么就把它降级或杀掉」。

**不合格写法（不接受）：**

| 写法 | 为什么不合格 |
|---|---|
| 「如果实验失败就降级」 | `失败` 未定义，不可判定 |
| 「视结果而定」 | 无观察条件 |
| 「若 O1 不成立则降级」 | `O1` 是支持性预测，否定它仍是空话 |
| 「然后我们再评估」 | 后果不是状态变更 |

### R8.2.4 派生 planned 实验并冻结 `preregistration`

从契约派生 `experiments[]` 的 `planned` 条目。每条至少写：

```jsonc
{"id":"X7","parent":null,"stage":"X3","claim_targeted":["C0"],
 "alternative_targeted":["ALT-1"],"metric":"…","status":"planned"}
```

**`stage` 取值与 `claim_targeted` 的约束见 [phase-r9-r11-experiment-loop.md](phase-r9-r11-experiment-loop.md) §R9.1 / §R9.2。**
R8 **不执行**实验，只登记。

**同时冻结 `preregistration`：**

```jsonc
{"frozen_at_state_version": <当前 state_version>,
 "outcomes": [
   {"id":"O1","observation":"<观察到什么>",
    "update":[{"target":"C0","op":"strengthen"}]}
 ]}
```

**`op` 冻结七值（逐字）：**
`strengthen` / `weaken` / `falsify` / `kill` / `retain` / `retain-with-alternative` / `inconclusive`

**硬规则：**

- `preregistration.outcomes[].id` 与契约 `expected_outcomes` 的键**必须一一对应**。
  对不上就是「结果出来以后现编解释」的入口。
- `planned` 状态**不要求** `preregistration`（`V21` 只在 `running` / `done` / `failed` 时要求）。
  但 R8 建立契约时**应当**同时冻结，避免 R9 边跑边定义成功。
- `status` 进入 `running` / `done` / `failed` 后，`frozen_at_state_version` **必须**是
  ≤ `result_at_state_version` 的非负整数（`V21`）。

### R8.2.5 证据驱动的单向 `status` 升级

R8 是唯一除 R10 之外能改 `claims[].status` 的阶段（见 [../SKILL.md](../SKILL.md) §1.6）。

| 迁移 | 门槛 | 归属 |
|---|---|---|
| `ungrounded` → `partially-supported` | 支持证据达 `≥ T1` | **R8** |
| `partially-supported` → `supported` | 支持证据达 `≥ T2` | **R8** |
| 任一 → `contradicted` | 反驳证据达 `≥ T2` | **R8** |
| `*` → `killed` | — | **只能经 R10** |
| 任何**降级** | — | **只能经 R10** |

**硬规则：**

- 无证据仍为 `ungrounded`；挂上证据却仍写 `ungrounded` 同样违规（`V3`）。
- 状态升级必须由**证据**驱动，不得由 `scope` 收窄或措辞改写驱动。
- 达不到门槛时**保持原状态**，并把缺口落进 `uncertainties[]`。

### R8.2.6 写 `proposal.md`

提案是**契约的人读视图**，不是独立的论证流程。按以下 6 节输出，逐节作答：

| # | 章节 | 要求 |
|---|---|---|
| 1 | **背景** | 问题是什么、为什么重要、当前状态 |
| 2 | **核心贡献** | 每条标 `K<n>` + **贡献类型** + **方法来源**（`原创` / `部分原创` / `迁移`，判据见 [venue-standards.md](venue-standards.md) §5.1） |
| 3 | **相关工作** | 含**精确差异**；引用 R7 的 `S-Lit` 结论，**不得自造** |
| 4 | **动机** | **必须回答「为什么之前没人这么做」** |
| 5 | **证据契约摘要** | 每条 central claim 一行：`C<n>` + `nearest_alternative` + `minimal_discriminating_experiment` + `kill_rule` |
| 6 | **预期结论与替代解释** | 预期结论 + `expected_outcomes` 里支持替代解释的分支 |

**第 5 节不得省略。** 提案与 R13 的评审标准共用同一份契约 —— 两者不同标准就是
「proposal 与 reviewer 各一套标准」，见 [research-state-policy.md](research-state-policy.md) §5。

**第 4 节的特别要求：** 给出**至少一条**具体原因，并说明该原因为什么现在不成立了。

- 技术原因（此前缺少某工具 / 表示 / 硬件）
- 数据原因（此前无某数据集 / 标注）
- 理论原因（此前缺少某性质刻画）
- 社区原因（此前该问题被归入另一领域）

> ❌ 「因为没人想到」 —— 不接受。
> ❌ 「因为我们首次提出」 —— 循环论证，不接受。

---

## R8.3 派遣

**权威副本：[roles.md](roles.md) §4.2 派遣矩阵的 `R8（证据契约）` 列。**
本表必须与它逐行一致。

| 角色 | 派遣 | 职责 |
|---|:--:|---|
| `A-Author` | ● | 按 §R8.2.6 落盘 `proposal.md`；标注贡献类型与方法来源 |
| `A-Experimenter` | ● | 按 §R8.2.4 登记 `planned` 实验并冻结 `preregistration` |
| `S-Lit` | ● | **引用 R7 的结论**，不重做 L3；「首次提出」声称按原检索等级表述 |
| `S-Nov` | ○ | S-Lit 判「边缘」或存在「首次提出」声称时；独立复核覆盖判定 |
| `S-Theory` | ● | 理论型 claim 的前提、边界条件、反例 |
| `S-Feas` | ● | 工程可行性与资源估算，产出落 `uncertainties[]` |
| `R-Theory` | ● | 理论锚点路线的证明正确性首要审查项 |
| `S-Devil` / `S-Repro` / `R-Novelty` / `R-Causal` / `R-Experimental` / `R-Generalization` / `R-Utility` | — | 不派 |

**硬规则：**

- **venue 角色不派。** `R-CVPR` / `R-ICML` / `R-NeurIPS` / `R-MICCAI` 只在 R12 / R13 的
  calibration 表里出现，不参与 R8。
- **不派遣** `S-Repro`（R8 无代码可复现）与六个攻击面审稿人（那是 R7 的职责）。
- **不重做新颖性检索。** R7 已派 `S-Lit`。R8 只按 [roles.md](roles.md) §3 的继承规则引用结论：
  R3—R6 的 §R3.7 快筛若只达 L2，结论**只能按 L2 表述**，不得升级为「已核实」。
- **`S-Lit` 产物的上限是 `T0`。** 不得据此升级任何 claim 状态。

---

## R8.4 交付物与落盘

| 交付物 | 规格 | 落盘 |
|---|---|---|
| **论文提案** | 覆盖 §R8.2.6 的 6 节 | `routes/<R>/docs/<R>NNN-proposal.md` |
| **证据契约** | 每条 central claim 一张 | `claims[].contract`（机器状态，不单独落文档） |
| **planned 实验** | 含冻结的 `preregistration` | `experiments[]`（机器状态） |
| **证据综合** | 按需；跨文献的证据合成 | `routes/<R>/docs/<R>NNN-evidence.md` |
| **理论分析** | 按需；理论锚点路线 | `routes/<R>/docs/<R>NNN-theory.md` |

**落盘步骤：**

1. 按 [project-layout.md](project-layout.md) §2.6 扫描现有最大序号 +1，**序号永不复用**。
2. **frontmatter：** `phase: R8` / `type: proposal | evidence | theory` / `status` / `created`。
3. **更新该路线 `INDEX.md`：** `Key Documents` 加行，`Recent Research Changes` 加一行。
4. **更新该路线 `STATUS.md`：** 先写回 `research-state.json`，再用
   `scripts/render_status.py` 重新生成。**不得手工编辑 `STATUS.md`。**
   - 已升级的 claim → **Strongest supported findings**
   - `kill_rule` 未定的 claim → **Critical uncertainties**
   - 未缓解的风险与未登记的判别实验 → **Next recommended actions**

**边界：`experiment-plan.md` 不属于 R8。**
实验规划文档由 **R9—R11** 落盘（[project-layout.md](project-layout.md) §2.2 / §6.2）。
R8 只创建 `planned` 实验**条目**并冻结 `preregistration`。

**门禁：** 若某条 central claim 要用「首次提出」措辞，必须已完成 `T1` 的 **L3 穷尽检索**
并附负检索记录；否则降级为「据本次检索未见」，或落进 **Critical uncertainties**。

---

## 读 / 写 World Model（强制）

| 阶段 | 读 | 写 |
|---|---|---|
| **R8** | `claims` / `evidence` / `assurance` | `claims[].contract` / `claims[].status`（**仅证据驱动的单向升级**：`ungrounded` → `partially-supported` / `supported`） / `evidence` / `claims[].supporting_evidence` / `refuting_evidence` / `uncertainties` / `experiments`（**创建 `planned` 条目 + 冻结 `preregistration`**） |

> 权威定义见 [research-state-policy.md](research-state-policy.md) §5；本节与它**必须逐字一致**。
> 回写后跑 `python3 scripts/state_check.py --check .research-idea-pipeline/routes/<R>/research-state.json`，**硬违规须为 0**。

---

## 自检（R8）

- [ ] 每条 central claim 都有 `contract`，且 10 个键齐全、无多余键
- [ ] 每条 `kill_rule` 都写成「若观察 `O` 则 `X`」，且后果是状态变更
- [ ] `expected_outcomes` 的键与派生实验的 `preregistration.outcomes[].id` 一一对应
- [ ] 没有把 `TBD` 留在 `minimal_discriminating_experiment` 里进入 R9
- [ ] `preregistration` 已冻结，或已登记「为什么留到 R9 才冻结」的 `U`
- [ ] 没有创建 claim，没有执行实验，没有写 `result`
- [ ] 状态升级有 `≥ T1` / `≥ T2` 证据支撑；无降级、无 `killed`
- [ ] 未派 venue 角色，未重做新颖性检索
- [ ] `proposal.md` 第 5 节「证据契约摘要」未省略
- [ ] `STATUS.md` 由 `render_status.py` 生成，非手工编辑
- [ ] `state_check.py --check` 硬违规为 0
