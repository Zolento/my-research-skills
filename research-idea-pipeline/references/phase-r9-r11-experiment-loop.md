# R9 / R10 / R11 — 实验树 · 元认知修复 · 状态回写

**这三个阶段是「文档流水线」与「科研搜索系统」的分界。** R9 让实验成为**树**而不是清单，
R10 让发现的问题**必须改变状态**，R11 让结果**必然回流**成下一条待验证命题。

> **权威声明：** 本文档是 **R10 修复门**与 **R9 实验树**的唯一权威定义。
> [phase-r7-r10-r13-assurance-repair-review.md](phase-r7-r10-r13-assurance-repair-review.md) 只登记
> 「R7 发现的问题必须交给 R10」，**不得**在那里另立一套处置规则。

---

## R9 实验树

### R9.1 六段结构（固定，`stage` 取值逐字）

| stage | 目的 | 判据 | 不许做什么 |
|---|---|---|---|
| `X1` | **可行性 / 健全性** | 代码能跑通、数据能读、指标能算 | 不许顺带调参 |
| `X2` | **基线校准** | 基线复现到论文报告量级（容差写明） | **不得承担 claim 判别** |
| `X3` | **claim 判别实验** | 结果能区分 `C` 与 `nearest_alternative` | 不许只看「我们更好」 |
| `X4` | **机制 / 替代解释** | 能排除最简替代解释（见 R10 机制保真测试） | 不许把相关性当机制 |
| `X5` | **边界 / regime 位移** | 在声称范围**之外**仍成立或明确失效 | 不许只扩数据集 |
| `X6` | **复现 / 稳健性** | 多种子、多划分、超参扰动下结论不翻转 | 不许只换种子重跑一次 |

> **`X2` 不得承担 claim 判别**是故意的结构性措施：它是「主要靠找到更好的 hyperparameters」
> 这条退化路径的入口（见 `../SKILL.md` §7 设计依据）。把基线校准与 claim 判别**分开成两个
> stage**，那条路径就没法冒充科研进展。

### R9.2 每个 `X` 节点的 provenance（字段逐字，见 [research-state-policy.md](research-state-policy.md) §3.5）

```jsonc
{"id":"X7","parent":"X3","stage":"X3","claim_targeted":["C17"],
 "alternative_targeted":["ALT-1"],"code_commit":"…","data_split":"…","seed":0,
 "metric":"…","result":"…","interpretation":"…","unexpected":[],
 "known_flaws":["F4"],"next_branches":["X8","X9"],"status":"planned|running|done|failed"}
```

**硬规则：**

1. **`X` 是树**：`parent` 指向产生它的节点（`null` = 根）。`state_check.py` **V8** 机制强制
   父引用存在且**不成环**。
2. **`claim_targeted` 必须非空**：说不清这次实验判别哪条 claim 的实验，不许做。
3. **`unexpected` 是必填语义位。** 意外观察不是噪音 —— 它是 R3 paradigm escape 与
   `uncertainties[]` 的一等输入。
4. **`known_flaws` 与 `result` 同时落盘**，不允许「先写结论，回头补 caveat」。

### R9.3 实验选择：Expected Information Gain（取代「最可能成功」）

```
e* = argmax_e  E[ΔU | e] / cost(e)
```

- `U` **只取** `uncertainties[]` 中 `importance ∈ {critical, high}` **且** `uncertainty = high` 的项。
- **排序时必须写出三件事：** ① 这次实验改变哪条 `U`；② 预期改变方向；③ 成本口径
  （GPU 小时 / 数据 / 人力，写明单位）。
- **禁止**用「预期能提升多少指标」当排序依据 —— 那是 benchmark 驱动的入口。

**这是压掉 hyperparameter-tuning attractor 的主要机制：** 当选择标准是「最让我们知道
自己是不是错了」，调参就不再是低风险高回报的选择。

### R9.4 失败实验不得消失（强制）

失败的实验**必须双写**：

```jsonc
// experiments[]：{"id":"X9", …, "status":"failed"}
// failures[]：   {"id":"F4","kind":"inconclusive|falsified|failed-to-reproduce|engineering-failure|unsupported|deprioritized",
//                 "what":"…","why":"…","referenced_by":["X9","C17"]}
```

**`state_check.py` V4 机械强制：** 每条 `F` 必须被某个 `claims[].known_flaws` 或
`experiments[].known_flaws` 引用。**失败不得在叙事中消失**（R12 的视图也必须带上它们）。

---

## R10 元认知修复门

### R10.1 核心规则（逐字）

> **检测到 critical flaw ⇒ Research State 必须改变。**
> **不允许**「reviewer 发现问题 → 写进 review → 流程结束」。

一致性审计链（每轮强制）：

```
Claim ↔ Method ↔ Code ↔ Result ↔ Conclusion
```

**要防的具体失效模式：** agent 已经发现自己有问题（self-awareness 存在），
但**没有真正修改**，最后照样提交原结论 —— 只写一条 Warning 就收工属于此类。

### R10.2 处置枚举（只有这五个，逐字）

`REPAIR_CLAIM` | `RUN_TEST` | `FIX_IMPLEMENTATION` | `NARROW_SCOPE` | `KILL_BRANCH`

选择判据：

| 情形 | 处置 |
|---|---|
| 结论对，措辞 / 范围过了 | `REPAIR_CLAIM` |
| 缺一条判别证据 | `RUN_TEST` |
| 代码与所声称方法不一致 | `FIX_IMPLEMENTATION` |
| claim 只在更窄的条件下成立 | `NARROW_SCOPE` |
| 分支被证伪 / 不值得继续 | `KILL_BRANCH` |

### R10.3 关闭枚举（只有这两个，逐字）

`RESOLVED` | `ACCEPTED_LIMITATION`

- `RESOLVED`：状态已改，flaw 不再成立。
- `ACCEPTED_LIMITATION`：**必须同时写进 `C.scope` 或 `C.known_flaws`** ——
  否则那不是「接受」，只是「忽略」。

### R10.4 落盘三元组（`state_check.py` V10 机制强制）

```jsonc
{"flaw":"C17 not supported",
 "disposition":"RUN_TEST",
 "state_delta":"U3→X18 已排队；C17.status→partially-supported",
 "closure":"RESOLVED"}
```

**违规判定：**

- 只写 `flaw` 而无 `disposition` 或 `state_delta` = **未闭环**；
- `closure` 为空 = **该轮不得结束**；
- `disposition` / `closure` 出现枚举外的值 = 硬违规（V10 按 strip 精确比对）。

### R10.5 机制保真测试（regime shift，机制型 claim 强制）

对任何「方法有效**因为**机制 M」的 claim，构造两个条件：

| 条件 | 机制 M 的预期 |
|---|---|
| **`RS1`** | **应成立** |
| **`RS2`** | **应失效** |

若 `RS1 ≈ RS2`（结果近似），机制 claim **必须降级**为 `partially-supported`，
并按 §R10.2 选择处置。

> ⚠️ **命名：** 这里是 **`RS1` / `RS2`**（regime shift），**不是** `R1` / `R2` ——
> 那两个是阶段号（R1 研究状态、R2 领域测绘）。

**为什么必须做：** 一个结果可能在当前 regime 下看起来正确，但作者给出的机制解释与自己
的数据矛盾，换 regime 就崩。这类「答案对、机制错」的 claim 若被写进叙事，是把**未被识别的
错误**包装成洞察。

### R10.6 artifact 审计的适用时机（防空转规则）

| 阶段 | 有什么 artifact | 允许要求什么审计 |
|---|---|---|
| R7 / R8 | **没有** code / logs / failed runs | **只能审「计划中的证据契约」** |
| R9 之后 / R13 | 有完整 trace | artifact-aware 审计：code ↔ method、logs ↔ result、failed runs 是否被隐藏、metric / dataset 选择历史 |

**禁止在无 artifact 的阶段要求 artifact 审计。** 那会产出一条永远无法执行、只能填「待补」的规则。

### R10.7 Integrity Gate（R13 起生效）

以下必须作为 **Gate**（不通过即不得提交），不是「附属检查」：
benchmark cherry-picking / data leakage / metric misuse / post-hoc selection bias。
**只读最终论文比读完整 trace 更难发现这些问题**，所以审计对象是 trace。

---

## R11 状态回写（`result → claim → uncertainty → next experiment`）

每个 `X` 收工后**按序**执行四步，缺一不可：

| 步 | 动作 | 写哪个字段 |
|---|---|---|
| 1 | 把结果登记为证据 | `evidence[]` 新增 `E<n>`（`epistemic_status` 按实际：跑了 = `Observed`，只是推导 = `Supported`） |
| 2 | 把证据连到 claim | `claims[].supporting_evidence` / `refuting_evidence`；`status` 按 §R10 更新 |
| 3 | 更新不确定性 | `uncertainties[]`：`status` 转 `closed`，或**新增**由本次 `unexpected` 引出的 `U<n>` |
| 4 | 生成下一步 | `experiments[]` 新增 `planned` 节点，`parent` 指向本次；或在 `next_branches` 里登记 |

**硬规则：**

- **`status` 变更只能在这里（经 R10）** —— 例外：R8 的证据驱动**单向升级**（见 [../SKILL.md](../SKILL.md) §1.6）。 Discovery（R3—R6）与 Assurance（R7）**不得**直接改
  `claims[].status` —— 这是防「自己给自己判分」的结构性措施。
- 第 3 步**不允许只关不增**：一轮实验如果没有任何新不确定性，要么结论已足够强（走 R14），
  要么本次实验没有信息量（应记为 `failures[]` 的 `inconclusive`）。
- 收尾跑 `python3 scripts/state_check.py --check .research-idea-pipeline/routes/<R>/research-state.json`，
  **硬违规须为 0**。

---


## 自检（R9—R11）

- [ ] 实验树 `parent` 无环，根节点 `parent = null`
- [ ] `X1`/`X2` **没有**承担 claim 判别
- [ ] 实验排序写出了「改变哪条 `U` / 方向 / 成本口径」，且**未**用指标提升当依据
- [ ] 每个失败实验在 `experiments[]`（`status: failed`）与 `failures[]` **双写**，且被 `known_flaws` 引用
- [ ] 每条 `repairs[]` 四字段齐备，`disposition` / `closure` 取值在枚举内
- [ ] `ACCEPTED_LIMITATION` 已同时写进 `C.scope` 或 `C.known_flaws`
- [ ] 机制型 claim 做了 `RS1` / `RS2` 对比；结果近似时已降级
- [ ] 未在无 artifact 的阶段要求 artifact 审计
- [ ] R11 四步全做完，且新增了不确定性或已走 R14
- [ ] `state_check.py --check` 硬违规为 0

---

## 读 / 写 World Model（强制）

| 阶段 | 读 | 写 |
|---|---|---|
| **R9** |`uncertainties`(critical, high 且 high) / `claims` | `experiments`（**执行**）/ `experiments[].status` / `experiments[].result_at_state_version` / `failures` / `known_flaws`（把新 `F` 挂上） |
| **R10** | 全 state + artifact | `repairs` + **执行 `state_delta`** |
| **R11** | 全 state | 归并去重 + **失效传播至不动点** + `state_version` +1 + 跑 `state_check.py` |

> 权威定义见 [research-state-policy.md](research-state-policy.md) §5；本节与它**必须逐字一致**。
> 回写后跑 `python3 scripts/state_check.py --check .research-idea-pipeline/routes/<R>/research-state.json`，**硬违规须为 0**。
