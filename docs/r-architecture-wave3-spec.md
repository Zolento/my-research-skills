# R 架构 Wave 3 规格：角色层（Discovery / Assurance 算子 + venue 后移）

> **本文件是 Wave 3 的唯一接口契约。** 位置：仓库根 `docs/`，**不进安装副本**。
> 冲突时先改本文件并通知 Lead。

**分支：** `research-idea-pipeline-dev`
**基线：** `8ef4737`（Wave 2 收尾）
**日期：** 2026-10-06

---

## 1. 目标

前两波把**状态载体**与**发现机制**建好了，但角色库仍是按 venue 组织的
（`R-CVPR` / `R-ICML` / `R-NeurIPS` / `R-MICCAI` 占 52 处引用）。Wave 3 要：

1. **角色按「攻击面 / 算子」组织**，venue 差异**全部后移**为一层校准；
2. **assurance 输出可执行对象**，不再只给 1—5 分；
3. **R12 拆 pre / post**：叙事不得反过来决定研究方向；
4. **R13 artifact-aware 审计落地**，Integrity 从「附属检查」升为 Gate。

---

## 2. ⚠️ Lead 的设计取舍（**需用户确认**，已按此实现以不阻塞）

用户提案要求「**7 discovery + 8 assurance 算子**替换角色库」。若逐个新增，角色命名空间会撞车
（`A-*` 已被路线字母与作者角色占用；`AS-*` 是假设 ID；`R-*` 已给攻击面审稿人）。

**Lead 的方案：不新增 15 个角色，而是把现有角色重新定义为「算子 / 攻击面」，只补 1 个新角色。**

| 提案的 assurance 算子 | 落到现有角色 | 说明 |
|---|---|---|
| `A-Lit`（最近工作碰撞） | **`S-Lit`** + `R-Novelty` | 已有，L3 穷尽 + 负检索记录 |
| `A-Minimal`（更简单解释够不够） | **`R-Causal`** | 已有（S-Devil 的「最简解释反例」并入此列） |
| `A-Identification`（实验是否识别 claim） | **`R-Experimental`** | 已有 |
| `A-Theory`（assumption / theorem / boundary） | **`R-Theory`** | 已有 |
| `A-Stats`（统计 / confounder） | **`R-Experimental`** 的第二读数 | 已有 |
| `A-Repro`（实现 / 可复现） | **`S-Repro`** | 已有 |
| `A-Scope`（claim scope） | **`R-Generalization`** | 已有 |
| `A-Integrity`（leakage / cherry-pick / post-hoc） | **`S-Integrity`** ← **本波唯一新角色** | R13 起生效 |

**7 个 discovery 算子 → 已有 6 条 island（`P1`—`P6`）**，算子名与 island 对齐：
`P-Reframe`→`P1`、`P-Assumption`→`P2`、`P-Abstraction`/`P-Remote`→`P3`、
`P-TheoryLens`→`P4`、`P-Measurement`→`P5`、`P-Counterexample`→`P6`。

**理由：** 15 个角色 = 角色库膨胀到 20+，而 `roles.md` 已是全仓引用最多的文件（52 处）；
提案的**意图（按攻击面组织 + 输出可执行对象）完全保留**，只是不新增命名空间。

> **用户若要求逐字照搬 15 个角色名，本波返工范围：`roles.md` 全量 + 约 52 处引用 + 5 个 phase 文件。**

---

## 3. assurance 输出契约（**取代 1—5 分数**）

每个 assurance 算子**必须**输出五元组，而不是一个分数：

```
(Attack, Target Claim, Alternative, Discriminating Test, Kill Condition)
```

示例：

```
Attack:        MIND-specific mechanism may be unnecessary.
Target:        C17
Alternative:   Any edge-preserving relational loss gives same gain.
Test:          MIND vs gradient relation vs random matched-scale loss.
Kill Condition: If alternatives match MIND under equal compute,
                remove the MIND-specific mechanism claim.
```

**硬规则：**

1. `Kill Condition` **必须可判定**（写成「若观察 O 则 X」的形式），写不出即该 attack 无效。
2. `Discriminating Test` 必须指向存在的 `X`，或字面量 `TBD`（`state_check.py` **V9** 已最少覆盖）。
3. **assurance 不得直接改 `claims[].status`** —— 只能经 **R10**（Wave 1 §1.6 已冻结）。
4. 人读**摘要仍然必填**（仓库既有硬规则）：可执行对象为 primary，摘要是 secondary，二者并存。

---

## 4. R12 拆 pre / post

| 子阶段 | 何时 | 只能做什么 |
|---|---|---|
| **R12-pre** | R8 之后、R9 之前 | 只写「**若 `H` 被验证，可能成立的 thesis 是…**」；**不得决定研究方向**；产出的预期叙事草稿**不落 `narrative_view`** |
| **R12-post** | R11 之后 | 只读**已核实**的 `claims[]` / `evidence[]` / `boundary` / **`failures[]`**；此时才用 `N1—N10` 选 preset |

**硬规则：** R12-post 的每句声称必须能落回 `Ci ← Ej`；**`failures[]` 不得在叙事中消失**（V4/V12 是前置）。

---

## 5. R13 artifact-aware 审计（落地）

审计对象（不是论文）：`paper` / `claim graph` / `experiment graph` / `code` /
`logs` / **`failed runs`** / `dataset selection history` / `metric selection history`。

**Integrity Gate（`S-Integrity`）**：benchmark cherry-picking / data leakage / metric misuse /
post-hoc selection bias —— **不通过即不得提交**（不是「记一条 warning」）。

**审计时机（Wave 1 已冻结，本波落地）：** R7 / R8 **无 artifact**，只能审计划中的证据契约；
真正的 artifact 审计绑 **R9 之后 / R13**。**禁止在无 artifact 的阶段要求 artifact 审计。**

---

## 6. venue 全量后移为校准

| 变化 | 内容 |
|---|---|
| `R-CVPR` / `R-ICML` / `R-NeurIPS` / `R-MICCAI` | **不再参与科学发现**；只在 **R12/R13 的 venue calibration** 中以**校准表**形式出现（不派子代理） |
| `venue-standards.md` §10 的 `contribution type → evidence contract → venue calibration` | 成为唯一入口；**禁止**「venue 直接选 preset」 |
| 消歧 | 会议审稿人可用于 **concept 级快筛**（`B5`），但**不得**用会议适配度**排序候选** |

---

## 7. 文件地图

| 文件 | 动作 | 所有者 |
|---|---|---|
| `docs/r-architecture-wave3-spec.md` | NEW（本文件） | **Lead** |
| `references/roles.md` | REWRITE：按「算子 / 攻击面」重组；venue 角色降为校准表；新增 `S-Integrity`；保留 `A-Author` / `A-Experimenter` | Wave 3 写者 |
| `references/phase-r7-r10-r13-assurance-repair-review.md` | UPDATE：五元组契约、Integrity Gate、venue 校准表 | Wave 3 写者 |
| `references/phase-r12-narrative.md` | UPDATE：拆 R12-pre / R12-post | Wave 3 写者 |
| `references/scoring-policy.md` | UPDATE：assurance 的分数改为**次要**（五元组为 primary）；`G1—G5` 不变 | Wave 3 写者 |
| `SKILL.md` | UPDATE：§2 角色库描述、§3 派遣表、§4 的 R7/R12/R13 段、§7 依据（+「为什么按攻击面而非 venue」） | **Lead** |
| `README.md` / `project-layout.md` / `examples/example-d-narrative.md` / `venv-standards.md` | UPDATE：引用同步 | **Lead** |

**纪律：** 只改自己 scope；不 commit；发现 spec 有错先报 Lead。

---

## 8. 验收标准

- [ ] `roles.md` 里 **venue 角色不再出现在任何 R 阶段的派遣表**（只在校准表）
- [ ] 每个 assurance 算子给出五元组；`Kill Condition` 可判定 —— **正例**：「若替代解释在等算力下追平，则移除机制专属 claim」；**反例**：「若结果不好看则重新考虑」（不可判定 → 该 attack 无效）
- [ ] **assurance 不得改 `claims[].status`** 写成硬规则，并与 §1.6 一致
- [ ] `S-Integrity` 是 Integrity Gate 的承担者，且**只在 R13 生效**
- [ ] R12-pre / R12-post 的**输入输出边界**写清（pre 不得决定方向；post 不得新增 `evidence`）
- [ ] venue 校准表与 `venue-standards.md` §10 一致
- [ ] 全量机械校验：链接 / `§` 引用 / JSON / 单测 / linter / deprecated-terms
- [ ] 三方口径 14 阶段仍逐字一致
- [ ] 独立 verifier 对抗验收通过

---

## 9. 变更记录

| 日期 | 变更 | 人 |
|---|---|---|
| 2026-10-06 | 初版；记录 Lead 关于「15 算子 → 映射到现有角色 + `S-Integrity`」的取舍，标注**需用户确认** | Lead |
