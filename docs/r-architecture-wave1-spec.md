# R 架构 Wave 1 规格：Research World Model + 修复门 + 实验循环

> **本文件是本波唯一接口契约。** 枚举、字段名、文件名、退出码必须逐字一致。
> 冲突时先改本文件并通知 Lead，不得各自解释。
>
> **位置：** 仓库根 `docs/`，在 skill 目录之外，**不进安装副本**（`npx skills` 只拷 skill 子目录）。

**分支：** `research-idea-pipeline-dev`
**基线：** `f8cefdc`（claim-first 重构）
**日期：** 2026-10-06
**来源说明：** 本波的设计目标与所引自动科研系统（Co-Scientist / FlowPIE / FunSearch-AlphaEvolve /
AI Scientist-v2 / Kosmos / Virtual Lab / ResearchAgent-SciAgents / PaperBench-AutoResearchEval /
MLGym）由用户提供，**未经本仓库独立核实**，按用户指示直接落入设计，不逐条标注。

---

## 1. 架构切换：A→B→C→D→E 全部作废

**新架构 = 以 Research State 为中心的双循环。**

```
R0 Research Contract ─▶ R1 Research World Model ─▶ R2 Field Mapping
                                                          │
                    ┌─────────────────────────────────────┴──────────┐
                    ▼                                                ▼
            DISCOVERY LOOP                                   ASSURANCE LOOP
        R3 Dual Discovery                                R7 Adversarial Assurance
        R4 Isolated Populations                          R8 Evidence Contract
        R5 Co-evolving Retrieval                         R10 Metacognitive Repair
        R6 Evolution                                     R13 Artifact-aware Review
                    └─────────────────────┬──────────────────────────┘
                                          ▼
                        R9 Experiment Tree ─▶ R10 Repair ─▶ R11 Update World Model
                                          ▼
                        R12 Narrative ─▶ R13 Review ─▶ R14 Decision
                                          └──────────▶ 回 R3 / R9（continue | pivot | archive | submit）
```

**硬规则：**

1. **入口改为 `phase=R<n>`**（单个或逗号分隔，如 `phase=R3,R9`；也接受 `phase=R3-R6`）。
   旧的 `mode=A|B|C|D|E` **不再接受**，且必须报错并给出映射提示。
2. **字母 A—E 作为「阶段名」全部退役。** 不允许在现行规则里出现「Mode D」这类表述；
   追溯历史时写「旧的叙事阶段」。
3. **`R1` 是常驻对象，不是一次调用。** 任何 R 阶段开工前先读 world model，收工前写回。
4. **`R10` 是闭环，不是报告。** 见 §5。

**旧 → 新映射（迁移用，不对外暴露）：**

| 旧 | 新 |
|---|---|
| Mode A 文献调研 | **R2** Field Mapping + **R5** Co-evolving Retrieval（常驻服务） |
| Mode B idea 发现 | **R3** Dual Discovery + **R4** Isolated Populations + **R6** Evolution |
| Mode C 方案生成 | **R8** Evidence Contract |
| Mode D 叙事 | **R12** Narrative（**视图**，不是独立 artifact） |
| Mode E 方案复核 | **R7** Adversarial Assurance + **R10** Repair + **R13** Artifact-aware Review |
| （新） | **R0 / R1 / R9 / R11 / R14** |

---

## 2. 冻结对象：Research World Model（R1）

### 2.1 八类一等对象与 ID 前缀

| # | 对象 | ID | 文件字段 |
|---|---|---|---|
| 1 | Claim Graph | `C<n>` | `claims[]` |
| 2 | Evidence Ledger | `E<n>` | `evidence[]` |
| 3 | Assumption Graph | `AS<n>` | `assumptions[]` |
| 4 | Hypothesis Portfolio | `H<n>` | `hypotheses[]` |
| 5 | Experiment Graph | `X<n>` | `experiments[]` |
| 6 | Literature Graph | `LIT<n>` | `literature[]` |
| 7 | Failure Memory | `F<n>` | `failures[]` |
| 8 | Uncertainty Map | `U<n>` | `uncertainties[]` |

**ID 前缀为何这样定（防撞）：** `C` 沿用 claim-first 的 `C0—C5`；`E` 沿用证据台账的 `E<n>`
（**不改**，否则上一轮冻结的 `Ci ← Ej` 语法与全部示例作废）；假设用 `AS`（`A` 已被路线前缀占用）；
**文献节点用 `LIT` 而不是 `L`** —— `L1/L2/L3` 已经有**两个**含义（迁移举证等级、检索尽职调查等级），
不能引入第三个。

### 2.2 每类对象的必填字段（逐字）

```jsonc
// claims[]
{"id":"C17","statement":"…","parent":null,"subclaims":["C17a"],
 "status":"ungrounded|supported|partially-supported|contradicted|killed",
 "supporting_evidence":["E32"],"refuting_evidence":[],
 "nearest_alternative":"…","falsifier":"…","scope":"…","known_flaws":["F3"]}

// evidence[]
{"id":"E32","kind":"experiment|literature|theory|observation",
 "supports":["C17b"],"contradicts":[],"strength":"partial|strong|weak",
 "scope":"brain MRI / acceleration=4",
 "epistemic_status":"Observed|Supported|Hypothesized|Planned|Unknown",
 "source_ref":"…"}

// assumptions[]
{"id":"AS13","statement":"adaptation must modify prior parameters",
 "status":"explicit|tacit","challenged_by":["H42","H57"],"if_false":"…"}

// hypotheses[]
{"id":"H42","statement":"…","structural_signature":{"assumption_distance":2,
 "formulation_distance":3,"representation_distance":1,"theory_lens_distance":3,
 "mechanism_distance":2},"novelty_source":"…","theory_lens":"…",
 "nearest_prior":"…","falsifier":"…","expected_information_gain":0.0,
 "status":"active|elite|archived|killed","niche":"assumption-breaking"}

// experiments[]
{"id":"X7","parent":"X3","stage":"X1|X2|X3|X4|X5|X6","claim_targeted":["C17"],
 "alternative_targeted":["ALT-1"],"code_commit":"…","data_split":"…","seed":0,
 "metric":"…","result":"…","interpretation":"…","unexpected":[],
 "known_flaws":["F4"],"next_branches":["X8","X9"],"status":"planned|running|done|failed"}

// literature[]
{"id":"LIT9","ref":"[作者, 会议/年份]","relation":"supports|contradicts|shares-assumption|shares-structure|solves-analogous-problem|uses-same-theory"}

// failures[]
{"id":"F3","kind":"falsified|unsupported|inconclusive|failed-to-reproduce|engineering-failure|deprioritized",
 "what":"…","why":"…","referenced_by":["C17","X7"]}

// uncertainties[]
{"id":"U3","question":"…","importance":"critical|high|medium|low",
 "uncertainty":"high|medium|low","cheapest_discriminating_test":"X18|TBD","status":"open|closed"}
```

**实验树阶段（固定六段，`stage` 取值）：**
`X1` 可行性/健全性 → `X2` 基线校准 → `X3` **claim 判别实验** → `X4` 机制/替代解释 →
`X5` 边界/regime 位移 → `X6` 复现/稳健性。
**`X2` 只做基线校准，不允许承担 claim 判别** —— 这是防「调超参驱动」的结构性措施。

### 2.3 引用完整性（`state_check.py` 机械强制）

| # | 规则 | 违规 |
|---|---|---|
| V1 | 每个 `C` 的 `falsifier` 非空 | 硬 |
| V2 | `C.supporting_evidence` / `refuting_evidence` 的每个 id 必须存在于 `evidence[]` | 硬 |
| V3 | 无任何 `E` 引用的 `C` 必须 `status: ungrounded`；有 `E` 却标 `ungrounded` 也是违规 | 硬 |
| V4 | 每条 `F` 必须被至少一个 `claims[].known_flaws` 或 `experiments[].known_flaws` 引用 | 硬 |
| V5 | `epistemic_status` ∈ 五值；`Hypothesized` / `Unknown` 的条目**不得**出现在 `supporting_evidence` | 硬 |
| V6 | 每条 `H` 的 `niche` 非空（QD archive 的前提） | 硬 |
| V7 | `U.cheapest_discriminating_test` 必须指向存在的 `X`，或字面量 `TBD` | 硬 |
| V8 | `X.parent` 必须是存在的 `X` 或 `null`；树不得成环 | 硬 |
| V9 | `assurance[].kill_condition` 非空，且 `discriminating_test` 指向存在的 `X` 或 `TBD` | 硬 |
| V10 | 每条 `repairs[]` 记录必须齐备 `flaw / disposition / state_delta / closure` | 硬 |

**退出码（与仓库既有脚本一致）：** `0` 全部通过；`3` 存在硬违规；`4` 环境不满足（文件缺失等）。
**`--json` 输出机器可读结果；`--check` 只校验不写。**

> **为什么必须有这个脚本：** 「八类一等对象」如果只写在 policy 里，执行者会写成散文。
> 本仓库已有 4 次成功先例（`refs_index.py` / `ste_lint_zh.py` / 56 个离线测试 / `--check`）。
> **没有 validator，"一等对象"是宣言，不是机制。**

---

## 3. 文件地图（Wave 1）

| 文件 | 动作 | 所有者 |
|---|---|---|
| `docs/r-architecture-wave1-spec.md` | NEW（本文件） | **Lead** |
| `references/research-state-policy.md` | **NEW** — R1 权威：八类对象、写入时机、双循环与 state 的关系 | `state-model` ✅ |
| `templates/research-state.template.json` | **NEW** — 完整骨架，JSON 合法 | `state-model` ✅ |
| `scripts/state_check.py` | **NEW** — V1—V10 | `state-validator` |
| `scripts/test_state_check.py` | **NEW** — 离线测试（stdlib unittest，≥14 用例） | `state-validator` |
| `references/phase-r0-contract.md` | **NEW**（手写） — R0 研究契约 | `phase-migration` |
| `references/phase-r2-r5-field-mapping-retrieval.md` | **`git mv`** ← `mode-a-literature-survey.md`，再改 `Mode X`→`R<n>`、补 field grammar / occupancy map / 共演化检索骨架 | `phase-migration` |
| `references/phase-r3-r6-discovery.md` | **`git mv`** ← `mode-b-idea-discovery.md`，再改名 + 补 local/paradigm 双轨与 population 骨架 | `phase-migration` |
| `references/phase-r8-evidence-contract.md` | **`git mv`** ← `mode-c-proposal-generation.md`，再改名 + 补 Claim Contract 骨架 | `phase-migration` |
| `references/phase-r7-r10-r13-assurance-repair-review.md` | **`git mv`** ← `mode-e-proposal-review.md`，再改名 + 补修复门/artifact 审计骨架 | `phase-migration` |
| `references/phase-r12-narrative.md` | **`git mv`** ← `mode-d-narrative-generation.md`，再改名（claim-first 内容全部保留） | `phase-migration` |
| `references/phase-r9-r11-experiment-loop.md` | **NEW**（手写） — R9 实验树 + R10 修复门 + R11 回写 | `experiment-repair` |
| **删除** `templates/state.template.json` | DELETE（被 `research-state.template.json` 取代） | **Lead** |
| `SKILL.md` | UPDATE（入口、§0 表、§1 不变量、§2 资源、§3 派遣、§4 速查、§5 衔接、§6 自检、§7 依据、§8） | **Lead** |
| `README.md` / `references/roles.md` / `references/scoring-policy.md` / `references/venue-standards.md` / `references/project-layout.md` / `references/claim-first-policy.md` / `references/evidence-policy.md` / `references/writing-policy.md` / `examples/*` / `templates/INDEX*.md` | UPDATE（`Mode X` → `R<n>`、旧 `mode-*.md` 链接 → 新 `phase-*.md`、`state.template.json` → `research-state.template.json`） | **Lead**（全员核心落地后统一扫尾） |

> **迁移用 `git mv` + 定向改名，不重写。** 这样「内容不丢」由构造保证（git 记录重命名），
> 风险只落在**改名是否彻底**和**新增骨架是否写清**上。**不要**手工重打一遍旧内容。

**写作用域纪律：** 只改自己那几行；不 commit；发现 spec 有错先报 Lead。

---

## 4. R9 实验树（`phase-r9-r11-experiment-loop.md`）

**每个实验节点必须携带完整 provenance（§2.2 的 `experiments[]` 字段即契约）。**

**实验选择规则（EIG，取代「最可能成功」）：**

```
e* = argmax_e  E[ΔU | e] / cost(e)
```

`U` 取 `uncertainties[]` 中 `importance ∈ {critical, high}` 且 `uncertainty = high` 的项。
**排序时必须写出：这次实验改变哪条 `U`、预期改变方向、成本口径。**

**失败的实验必须留在 `experiments[]`（`status: failed`）与 `failures[]` 里**，不得从叙事中消失。

---

## 5. R10 元认知修复门（`phase-r9-r11-experiment-loop.md`）

**核心硬规则（逐字）：**

> **检测到 critical flaw ⇒ Research State 必须改变。**
> 不允许「reviewer 发现问题 → 写进 review → 流程结束」。

**一致性审计链（每轮强制）：** `Claim ↔ Method ↔ Code ↔ Result ↔ Conclusion`。

**处置枚举（只有这五个）：**

`REPAIR_CLAIM` | `RUN_TEST` | `FIX_IMPLEMENTATION` | `NARROW_SCOPE` | `KILL_BRANCH`

**裁决（2026-10-06）：`assurance[]` 由 R7 写，不由 R0 写。**
理由：kill condition 是对**具体 attack** 的回应；R0 期还没有 claim，更没有 attack，
在那里写 `kill_condition` 只能写出空话 —— 空转规则正是本轮要清掉的东西。
R0 只写 `contract`；R7 写 `assurance[]`（`discriminating_test` 无 `X` 时可填 `TBD`）。

**关闭枚举（只有这两个）：** `RESOLVED` | `ACCEPTED_LIMITATION`

**落盘三元组（V10 强制）：**

```jsonc
{"flaw":"C17 not supported","disposition":"RUN_TEST","state_delta":"U3→X18 已排队；C17.status→partially-supported","closure":"RESOLVED"}
```

**违规判定：** 只写 `flaw` 而无 `disposition` 或 `state_delta` = 未闭环；`closure` 为空 = 该轮不得结束。
**`ACCEPTED_LIMITATION` 必须同时写入 `C.scope` 或 `C.known_flaws`**，否则不算接受，只是忽略。

**机制保真测试（regime shift，机制型 claim 强制）：** 构造 `RS1`（机制应成立）与
`RS2`（机制应失效）；若两者结果近似，机制 claim **必须降级**为 `partially-supported`。

> ⚠️ **命名：** regime-shift 条件用 **`RS1` / `RS2`**，**不要**写成 `R1` / `R2` ——
> 那两个是阶段号（R1 研究状态、R2 领域测绘）。

**完整性审计的适用时机（防止空转规则）：** artifact-aware 审计需要 code / logs / failed runs。
**R7/R8 阶段无 artifact，只能审「计划中的证据契约」**；真正的 artifact 审计绑在
**R9 之后 / R13**。禁止在无 artifact 的阶段要求 artifact 审计。

---

## 6. SKILL.md 接线（Lead）

1. `argument-hint` → `"phase=R0..R14 [writing=asd-ste100] [领域关键词 | idea | proposal | query]"`。
2. §0 入口：`mode` 解析 → `phase` 解析；加「旧 `mode=` 不再接受，报错并给映射」；新增「双循环」总览图。
3. §1 不变量：新增 **1.6「critical flaw ⇒ state change」**；`§1.5` 的承重墙保持 central proposition。
4. §2 资源索引：加 `research-state-policy.md` / `research-state.template.json` / `state_check.py` / 6 个 `phase-*.md`；删 `state.template.json` 行。
5. §3 派遣总览：按 R 阶段重列（Wave 1 沿用现有角色，Wave 3 换算子）。
6. §4 各 Mode 速查 → §4 各 R 阶段速查（R0—R14）。
7. §5 衔接图：改为双循环图。
8. §6 自检：加 V1—V10 与修复门闭环项。
9. §7 设计依据：新增「为什么以 state 为中心」「为什么 W 型双循环」「为什么修复必须改变状态」「为什么实验用 EIG 而非成功率」「为什么必须留失败实验」。
10. §8：登记本波漂移类别（模式字母全线改名 = B3 类放大的案例）。

---

## 7. 验收标准

- [ ] `state_check.py --selftest` 通过；`test_state_check.py` **≥14 用例全过**；V1—V10 每条至少一个反例用例
- [ ] `research-state.template.json` 通过 `state_check.py`（模板自身必须合规）
- [ ] 全仓 `grep -rn 'Mode [ABCDE]\|mode=[ABCDE]\|mode-[abcde]-'` → **0 命中**（历史说明改写）
- [ ] 全仓不再引用已删文件（`mode-a…e`、`state.template.json`）
- [ ] `deprecated-terms.txt` 追加：`mode=A|B|C|D|E` 类写法、`state.template.json`
- [ ] 相对链接 0 断链；`§` 引用可解析；JSON 合法；`python3 -m unittest discover -s scripts -p "test_*.py"` 全过
- [ ] `examples/` + `templates/` 默认档 linter 硬违规 0
- [ ] 每个 phase 文件都写明：输入 / 动作 / 产物 / **写回 world model 的哪些字段**
- [ ] R10 的处置/关闭枚举逐字一致，且 `state_check.py` V10 能拦住「只写 flaw 不写 disposition」
- [ ] 独立 verifier 对抗验收通过

---

## 8. 波次边界（不混）

| 波 | 内容 | 状态 |
|---|---|---|
| **Wave 1** | 世界模型 + validator + Repair Gate + R9 实验树 + A–E→R 全线改名与迁移 | **本文件** |
| Wave 2 | R3 拆 local/paradigm + R4 islands 上下文隔离 + QD archive + 两阶段 fitness + R5 共演化检索 | 待规格 |
| Wave 3 | 7 discovery + 8 assurance 算子替换角色库 + venue 全量后移 + R12 拆 pre/post + R13 artifact 审计 | 待规格 |

---

## 9. 变更记录

| 日期 | 变更 | 人 |
|---|---|---|
| 2026-10-06 | 初版 | Lead |
| 2026-10-06 | 依 `docs/verify-r-wave1.md` §9 修 M-3/M-4/M-6/M-7/M-8 与 MINOR；R14 决策枚举统一为 `continue\|pivot\|archive\|submit`（本节 §1 的图同步） | Lead |
