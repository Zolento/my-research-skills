# R 架构 Wave 2 规格：发现层（Discovery Loop）

> **本文件是 Wave 2 的唯一接口契约。** 枚举、字段名、数字默认值、文件名必须逐字一致。
> 冲突时先改本文件并通知 Lead。位置：仓库根 `docs/`，**不进安装副本**。

**分支：** `research-idea-pipeline-dev`
**基线：** `f8dda53`（Wave 1 收口 + V11/V12 闸门）
**日期：** 2026-10-06

---

## 1. 目标：从「一轮选 Top-3」变成「保多样性的开放搜索」

Wave 1 把状态载体与修复门建好了，但 R3—R6 仍是旧的「文献归纳 → brainstorm → shortlist」
顺序 —— 这个顺序**本身就在制造 increment attractor**。Wave 2 要把它换成：

```
R3 双轨发现（上下文隔离）
      ├── Local Search ──── 已有 gap / 机制改进
      └── Paradigm Escape ─ P1 Reframe / P2 Assumption destruction /
                            P3 Remote structural analogy（先做 domain erasure）/
                            P4 Theory lens / P5 Measurement inversion /
                            P6 Counterexample & impossibility
R4 隔离种群 → structural signature → QD archive（每 niche 留 elite）
R5 共演化检索：I_t → Q_{t+1} → L_{t+1} → I_{t+1}
R6 进化：mutation / cross-domain crossover / simplification / theory-induced deduction / new niche
```

**两阶段 fitness（核心机制）：**

| 阶段 | 只看 | **不看** |
|---|---|---|
| **Search（R3—R6）** | `representation distance` + `structural novelty` + `cross-domain surprise` + `deductive yield` | **venue fit** |
| **Selection（进入 R7 之后）** | novelty / validity / importance / testability / EIG ÷ cost | — |

> **在搜索期优化 venue fit，正是杀死范式 idea 的机制。** 这条是本波最重要的纪律。

---

## 2. 冻结的默认值（用户 2026-10-06 拍板）

| 项 | 默认 | 说明 |
|---|---|---|
| **QD archive 的 niche** | **复用 `N1—N10` preset 名** | **不引入第二套枚举** —— 10 套 preset 已冻结且全仓一致，另设一套就是漂移源 |
| **islands 数** | **默认 4** | `P1` / `P2` / `P3` / `P4` **默认开启**；`P5`（Measurement inversion）与 `P6`（Counterexample & impossibility）是**按需启用**的第五、第六条轨 —— 枚举里合法，但不占默认预算（用户拍板的是「4 islands × 3—6」，启用 P5/P6 即上调，需说明理由） |
| **每 island 候选数** | **下限 3，上限 6** | 超出上限必须显式说明为什么值得 |
| **进化轮数上限** | **2** | 到上限仍未收敛 → 落 `uncertainties[]` 并交 R7，**不得无限进化** |
| **novelty 计算依据** | `structural_signature` **五维距离** | **不得用文本 embedding** —— 两个文字完全不同、本质同一个机制的候选必须被聚到同一 cluster |

**可缩放：** 领域过窄或资源受限时，可在 R0 `contract.constraints` 里写明并降到 2 islands × ≥2 候选；
**上调**上限需要用户同意。

---

## 3. 新增 / 变更的 state 字段

`hypotheses[]` 现有字段（Wave 1 已冻结）：`id / statement / structural_signature{5} / novelty_source /
theory_lens / nearest_prior / falsifier / expected_information_gain / status / niche`。

**Wave 2 新增两个字段（必须同轮改 5 处：本节 / `research-state-policy.md` §3.4 / 模板 /
`state_check.py` / 测试）：**

| 字段 | 取值 | 说明 |
|---|---|---|
| `island` | `P1`—`P6` / `local` | 该候选由哪条 escape 轨产生；`local` = Local Search。**`P1`—`P4` 默认开启，`P5`/`P6` 按需启用**（见 §2） |
| `generation` | 整数 ≥ 0 | `0` = 初始候选；每次 R6 进化 +1 |

**`structural_signature` 五维（逐字，Wave 1 已冻结，本波开始真正使用）：**
`assumption_distance` / `formulation_distance` / `representation_distance` /
`theory_lens_distance` / `mechanism_distance`。

---

## 4. 新增机械闸门（`state_check.py`）

| # | 规则 | 硬 |
|---|---|---|
| **V13** | `hypotheses[].island` ∈ `{P1..P6, local}` | 硬 |
| **V14** | `hypotheses[].generation` 是非负整数 | 硬 |
| **V15** | 若 `hypotheses[]` 非空，则**每个出现过的 `niche` 至少有一个 `status: elite`** | 硬 |

> **V15 是 QD archive 的机制化**：只留「综合分最高的一个」会让某些 niche 空掉，那正是
> increment attractor。V15 强制「每个 niche 留一个 elite」。
> **配套**：`hypotheses[].niche` 取值必须是 `N1—N10` 之一（**V6 扩展**，不再只是「非空」）。

**登记要求（同轮 5 处）：** 本节 + `policy` §4 规则表 + `state_check.py`（RULES / `_v13`—`_v15` /
`_v6` 扩展 / CHECKS）+ 模板（必须通过）+ `test_state_check.py`（每条 ≥1 反例 + ≥1 合法反例）。
**测试里的规则数不得再硬编码** —— 期望值从 `RULES` / `RULE_ORDER` 派生。

---

## 5. 三方口径同步（沿用 Wave 1 的机械可判定口径）

新增/变更的读写字段必须同步三处，且**逐字相同**：
`research-state-policy.md` §5 表 ↔ `SKILL.md` §0 读/写列 ↔ 对应 `phase-*.md` 的读写表。

| 阶段 | 读 | 写 |
|---|---|---|
| **R3** | `literature` / `assumptions` / `failures` | `hypotheses` |
| **R4** | `hypotheses` | `hypotheses[].niche` / `hypotheses[].island` / `hypotheses[].status` |
| **R5** | `hypotheses` | `literature` / `evidence`(kind=literature) |
| **R6** | `hypotheses` / `uncertainties` / `failures` | `hypotheses[].generation` / `hypotheses[].status` / `failures` |

> ⚠️ **上表取代 Wave 1 的口径**；改完后跑 Wave 1 留下的三方一致性检查（14 阶段逐字比对）
> 必须仍为 0 不一致。

---

## 6. 文件地图

| 文件 | 动作 | 所有者 |
|---|---|---|
| `docs/r-architecture-wave2-spec.md` | NEW（本文件） | **Lead** |
| `references/phase-r3-r6-discovery.md` | UPDATE：替换 R3/R4/R6 骨架为正式规则（双轨隔离、六条 escape 轨、QD archive、五维聚类、进化算子、两阶段 fitness）；**B5 审核与文献纪律一字不动** | Wave 2 写者 |
| `references/phase-r2-r5-field-mapping-retrieval.md` | UPDATE：R5 共演化检索从骨架转正式规则（`I_t → Q_{t+1} → L_{t+1} → I_{t+1}`） | Wave 2 写者 |
| `references/research-state-policy.md` | UPDATE：§3.4 加 `island` / `generation`；§4 加 V13—V15、扩展 V6；§5 按 §5 表更新 | Wave 2 写者 |
| `scripts/state_check.py` + `test_state_check.py` | UPDATE：V13—V15 + V6 扩展 + 去硬编码 | Wave 2 写者（**与 policy 同轮**） |
| `templates/research-state.template.json` | UPDATE：`island` / `generation` 占位，且仍须通过全部规则 | Wave 2 写者 |
| `SKILL.md` | UPDATE：§0 读/写列、§4 的 R3—R6 段、§7 设计依据（+「为什么两阶段 fitness」） | **Lead** |
| `narrative-patterns.md` | UPDATE：§1 明写 preset 名同时是 QD archive 的 niche 取值 | **Lead** |

---

## 7. 验收标准

- [ ] V13—V15 各 ≥1 反例 + ≥1 合法反例；**测试不再硬编码规则数**（从 `RULES` 派生）
- [ ] `state_check.py --selftest` 覆盖 V1—V15；模板 `--check` exit 0
- [ ] 三方口径 14 阶段仍逐字一致（Wave 1 检查器复跑为 0 不一致）
- [ ] `hypotheses[].niche` 取值 ∈ `N1—N10`（V6 扩展）
- [ ] 双轨**上下文隔离**写成硬规则（「两轨在产生候选之前不得互相看到内容」）
- [ ] 两阶段 fitness 写明 **Search 期不看 venue fit**
- [ ] 预算默认值（4 islands × 3—6 候选，进化 ≤2 轮）写进 phase 文件，并标明可缩放条件
- [ ] 全量机械校验：链接 / `§` 引用 / JSON / 单测 / linter / deprecated-terms 全绿
- [ ] 独立 verifier 对抗验收通过

---

## 8. 非目标（Wave 3）

角色库替换（7 discovery + 8 assurance 算子）、venue 全量后移为校准、R12 拆 pre/post、
R13 artifact-aware 审计落地。

---

## 9. 变更记录

| 日期 | 变更 | 人 |
|---|---|---|
| 2026-10-06 | 初版；冻结 niche = N1—N10、预算 = 4 islands × 3—6 候选 / 进化 ≤2 轮（用户拍板） | Lead |
| 2026-10-06 | 依 `docs/verify-r-wave2.md` 修 M-1—M-6 与 MINOR/NIT；`island` 枚举澄清为 `P1`—`P6`/`local`（默认开启 P1—P4，P5/P6 按需） | Lead |
