# Scientific Meta-Controller（跨阶段调度）

> **结论：`R0`—`R14` 是**能力**（capabilities），不是必须依次经过的 **workflow**。
> 下一步做什么，由调度策略 `π(S_t)` 依据当前 Research State 决定。**

**这不是第 16 个阶段。** 它是一层**横跨** `R0`—`R14` 的调度器，在任一 R 阶段
**开工前与收工后**各跑一次。（设计出处：Wave 5 规格 §4，属开发文档，不进安装副本。）

```text
S_t --π(S_t)--> a_t --> S_{t+1}
```

---

## 1. 落点：**出 state 的 telemetry 文件**

| 项 | 值 |
|---|---|
| 路径 | `.research-idea-pipeline/routes/<R>/scheduler.json` |
| 骨架 | [../templates/scheduler.template.json](../templates/scheduler.template.json) |

**它不进 `research-state.json`，也不是第九类一等对象。**

> **分区规则（Wave 5 spec §0.6）：** 机制若要**进 state**，必须是**已有八类对象上的字段**；
> 若它描述的是「系统自己怎么工作」，就**必须出 state**、落 telemetry 文件。
> 这条同时挡住「加第 9 类对象」和「把系统统计混进科研状态」两种漂移。

---

## 2. 为什么需要它

有 15 个阶段，但「**下一步最值得做什么**」此前没有正式定义 ——
执行者容易退化成「按 R 编号顺推」，于是把计算资源花在**不需要现在做**的事情上。

**对照 Co-Scientist 真正值得借的一点：** 它有六种 agent 不是关键；
关键是 **Supervisor 会依据当前 hypothesis population、review 状态与系统统计动态分配计算资源**，
且 **Meta-review 把反复出现的问题反馈给后续 generation/review**。

---

## 3. `next_action_policy.priority`（八级，**冻结**）

调度器按此顺序取第一个**可执行**的动作类别：

| 优先级 | 触发条件 | 对应动作 |
|---|---|---|
| 1 | `integrity_violation` | 立即停止并修复（`S-Integrity` fail） |
| 2 | `unresolved_critical_attack` | R10 处置（`repairs[]` 必须闭环） |
| 3 | `invalidated_dependency` | R11 失效传播 + 下游复核 |
| 4 | `high_information_gain_test` | R9 低成本高 EIG 实验 |
| 5 | `paradigm_escape_if_stagnant` | R3 `P1`—`P6` |
| 6 | `literature_collision` | R5 |
| 7 | `local_optimization` | R3 `local` / R6 |
| 8 | `narrative_or_venue_work` | R12 / R13 |

**语义：** 高优先级项**未清零**时，不得推进到低优先级项。
即 **「完整性 > 未决攻击 > 失效传播 > 信息增益 > 范式逃逸 > 文献碰撞 > 局部优化 > 叙事/投稿」**。

> **注意优先级 8 的位置。** 叙事与 venue 校准排在最后，与「Narrative 后置」「venue calibration 最后」
> 两条既有纪律一致 —— scheduler 把它们**从纪律升级成了可执行的排序**。

---

## 4. `next_actions[]` 条目结构

```json
{
  "action": "X14",
  "type": "discriminating_experiment",
  "target": "U7",
  "eig": "high",
  "cost": "low"
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `action` | 字符串 | 动作标识（可引用 `X<n>` / `H<n>` / `P<n>` / `R<n>`） |
| `type` | `discriminating_experiment` \| `remote_analogy` \| `literature_collision` \| `repair` \| `propagate_invalidation` \| `narrative` | 动作类别 |
| `target` | 字符串 | 作用对象（`U`/`C`/`H`/`AS` 的 id 或 `P<n>`） |
| `eig` | `high` \| `medium` \| `low` \| `unknown` | **LLM 估计**的期望信息增益；**必须按 §6.1 校准**。排序时把它连同 ①改哪条 `U` / ②预期方向 / ③成本口径一起写进 `predicted_information_gain`（**生产者在 R9，消费者在 R11**） |
| `cost` | `high` \| `medium` \| `low` | 成本档（口径见 `phase-r9-r11-experiment-loop.md` §R9） |

**排序只用 `EIG ÷ cost`**，**不得**按「最容易涨指标」或「最容易发论文」排序
（与 R9 的既有禁令一致）。

---

### 4.1 `operator_stats`（system-level Meta-Memory）

**它记录「系统自己哪种算子有效」，不是领域的科学知识。** 因此它**出 state**，落
`scheduler.json`；**不得**被 `evidence[].source_ref` 引用，也**不得**进叙事。

```json
{
  "operator_stats": {
    "by_operator": {
      "P5": {"generations": 3, "viable": 0, "killed": 3, "dormant": true}
    },
    "recurring_failure_patterns": ["theory_lens 只产出 theory relabeling"]
  }
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `by_operator[<算子>].generations` | 非负整数 | 该算子参与过的代数 |
| `by_operator[<算子>].viable` | 非负整数 | 产出且**未被淘汰**的候选数 |
| `by_operator[<算子>].killed` | 非负整数 | 产出后**被淘汰**的候选数 |
| `by_operator[<算子>].dormant` | `true` / `false` | **全灭**（`viable == 0` 且 `killed > 0`）时为 `true` |
| `recurring_failure_patterns` | 字符串数组 | 反复出现的失败模式，供 R6 / scheduler 复用 |

**硬规则：**

1. **island / operator 全灭写在这里，不写 `uncertainties[]`。**
   「某算子本轮表现不好」描述的是**系统行为**；`research-state.json` 只描述**世界**。
   **只有全灭暴露出一个独立的科学未知时**，才另立 `U<n>`。
2. **`dormant` 不等于淘汰。** 保留 exploration floor —— **不得**因成功率低就永久停用某算子。
   `dormant` 只表示「本轮没产出」；是否 reseed 由 `next_action_policy` 的
   `paradigm_escape_if_stagnant` 决定。
3. **项目级汇总：** `.research-idea-pipeline/meta/operator-stats.json` 是各路线
   `scheduler.json` 的 `operator_stats` 的**只读汇总**（跨路线看哪种算子整体有效）。
   它同样**不入 state**。

---

## 5. 运行时机

| 时点 | 做什么 |
|---|---|
| **任一 R 阶段开工前** | 读 `scheduler.json` + `research-state.json`，输出 `next_actions[]` 与推荐的下一阶段 |
| **任一 R 阶段收工后** | 用新 state 重算一次；若推荐的下一阶段与该阶段自己的收尾条件冲突，**以 state 为准** |

---

## 6. 边界（不得越权，三条硬规则）

1. **只排序，不改变标准。** scheduler **不得**改动角色库、评分维度、门禁规则（`G1—G5`、
   `V1`—`V24`）或派遣方式（§3.1）。
2. **不得直接写 `research-state.json`。** 它只能**建议**下一个 R 阶段；
   落盘一律由该阶段按自己的读写契约执行（`research-state-policy.md` §5）。
3. **telemetry 不得被当作科学证据。** `scheduler.json` 里的任何统计
   **不得**被 `evidence[]` 引用、**不得**进入叙事。

> **并且：`eig` 是估计值，不是事实。** 每个实验做完后必须把估计与
> **实际信息增益**对照（Wave 5 spec §5 的 P1-10），否则 `EIG` 只是另一个
> 「听起来很科学的主观评分」。

---

### 6.1 EIG 的生产者 / 消费者（**不得只存一个主观评分**）

**生产者与消费者必须分开，否则 `EIG ÷ cost` 会退化成「LLM 自己觉得这个实验挺有信息量」。**

```text
R9  scheduling        → scheduler.json : predicted_information_gain
实验完成
R11 state update      → scheduler.json : observed_delta + actual_information_gain
Meta-Controller later → 用对照校准未来的 EIG 估计
```

**`actual_information_gain` 不得由 LLM 重新拍脑袋。** 它必须由**结构化事实**推出：

```json
{
  "experiment": "X21",
  "predicted_information_gain": "high",
  "observed_delta": {
    "claim_status_changes": [{"id": "C17", "from": "ungrounded", "to": "partially-supported"}],
    "uncertainty_changes": [{"id": "U4", "level_from": "high", "level_to": "medium",
                             "status_from": "open", "status_to": "open"}],
    "hypothesis_status_changes": [],
    "new_uncertainties": ["U9"],
    "unexpected_observations": 1
  },
  "actual_information_gain": "medium"
}
```

**`actual_information_gain` 四值（冻结）：** `high` | `medium` | `low` | `zero`

| rating | 由什么 `observed_delta` 支撑（满足其一即可） |
|---|---|
| `high` | ① `claim_status_changes` 非空；② 某条 `U` 的 `status_to == "closed"`；③ 出现 claim 被 `contradicted` / `killed` 的判别证据 |
| `medium` | ① 某条 `U` 的 `level_to` 比 `level_from` **降一级**（`high → medium` 或 `medium → low`）；② `hypothesis_status_changes` 非空；③ `new_uncertainties` 非空 |
| `low` | ① 只有 `unexpected_observations ≥ 1`；② 只改了 `interpretation` / `scope`；③ 只做 `depends_on` 类账目修正 |
| `zero` | `observed_delta` 五项全空且未登记 `unexpected` —— **必须同时写 `failures[]`（`kind: inconclusive`）** |

**硬规则：**

1. **`rating` 必须由 `observed_delta` 支撑。** 出现 `"actual_information_gain": "high"` 而
   `observed_delta` 里没有任何支撑项 = **telemetry 自欺**，与「只存一个主观评分」等价。
2. **写入时机：** R11 的第 3 步之后、第 5 步之前（此时 `observed_delta` 才齐）。
3. **没做完的实验不写。** `experiments[].status != done` 的 `X` **不得**有 `actual_information_gain`。
4. **`observed_delta` 只记「变了什么」，不记「为什么变」。** 归因留给评审（R7 / R13），
   不要把因果解释塞进 telemetry。
5. **校准不等于自动改分：** Meta-Controller 只能**记录**估计与实际的偏差分布，
   **不得**自动改写历史 `predicted_information_gain`。
6. **`observed_delta` 与 state 的关系：** 它必须与同一轮 `research-state.json` 的实际改动
   **一致**。不一致时**以 state 为准**，并重算 `rating`。

> ⚠️ **已知限制（不得假装已闭环）：** `scheduler.json` **没有机械校验器** ——
> 上面这些是**契约**，不是闸门。`state_check.py` 只校验 `research-state.json`。
> 因此 EIG 对照目前靠 R11 的自检与评审保证；把它变成机械闸门需要一份 scheduler schema（未实现）。

---

## 7. 与既有机制的关系

| 既有 | scheduler 的作用 |
|---|---|
| §3.1 派遣方式（Team 优先询问） | **不变**；scheduler 不决定用不用 Team |
| R9 的 `EIG ÷ cost` 排序 | scheduler 在**跨阶段**层面复用同一口径，不新增第二套公式 |
| R10 修复门（critical flaw ⇒ state 必须改变） | scheduler 把「未闭环 critical attack」列为**优先级 2** |
| R11（归并 + 失效传播） | scheduler 把「失效依赖」列为**优先级 3**，即其未清零前不推进低优先级项 |
| R12 / R13（叙事、venue 校准） | 被固定为**优先级 8**（最后） |

---

## 8. 自检

- [ ] `scheduler.json` **不在** `research-state.json` 内，且未被任何 `evidence[].source_ref` 引用。
- [ ] 八级优先级**顺序未被重排**，且高优先级未清零时没有推进低优先级项。
- [ ] `next_actions[]` 的排序依据是 `EIG ÷ cost`，**没有**出现 venue fit 或指标提升。
- [ ] 每个 `done` 实验都有 **三件套**：`predicted_information_gain` + `observed_delta` +
      `actual_information_gain`，且 `rating` 由 `observed_delta` 支撑（§6.1）。
- [ ] `observed_delta` 与同一轮 `research-state.json` 的实际改动一致。
