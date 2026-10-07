# Structural Equivalence & Novelty Audit 政策（跨阶段保证服务）

**本文件是 Structural Equivalence 的唯一权威定义。** R4 / R5 / R7 / R8 / R10 / R13 一律引用本文件，
**不得**各自重复定义（各自重写一遍就是新的漂移源，见 [evidence-policy.md](evidence-policy.md) 的同类教训）。

**它不是新的 R 阶段（仍 `R0`—`R14`）。** 它不新增一等对象，不新增 reviewer persona，
不新增 novelty 1—5 分、总分或第三套评分体系。它是**挂在既有阶段上的 cross-phase assurance service**。

> **核心原则（冻结）**
>
> **Novelty is not a new description of the structure. Novelty requires a load-bearing change in the structure.**
>
> 换一个理论名字、换一套叙事、换一个领域，**都不是**结构创新。只有承重结构发生改变，
> 并且这个改变导出一条可判定的新后果，才算。

---

## 1. 要解决的 failure mode

Paradigm Escape 强化之后出现了一类新的退化：

> Agent 提出一个听起来非常新颖的 theory lens / remote analogy / formulation，
> 但去掉领域名称、理论品牌和叙事包装后，其科学结构**与已有工作等价** ——
> 只是重新命名、重新解释，或跨领域搬运。

本服务必须能回答：

1. Candidate 与最近 prior work 在科学结构上**哪里相同、哪里不同**？
2. 所谓「创新」是否包含一个真正 **load-bearing 的 structural delta**？
3. 把这个 delta 换回 prior 的对应结构，candidate 是否**坍缩回**已有工作？
4. 这个 delta 是否产生新的 prediction / assumption / information boundary /
   mechanism / algorithmic consequence / discriminating experiment？

**LLM 不是 scientific novelty 的 truth oracle。** 本服务的产物是**可审计的结构对齐与反事实测试记录**，
不是「新 / 不新」的裁决。最终判断权属于检索覆盖、结构对齐证据与人类研究者。

---

## 2. 冻结边界（不扩张承诺）

以下边界**冻结**。任何实现若越过其中一条，视为设计回归。

| # | 冻结项 | 含义 |
|---|---|---|
| SE1 | 无新 R 阶段 | 仍 `R0`—`R14`。本服务是跨阶段能力，不是新阶段 |
| SE2 | 无第九类一等对象 | 完整审计 artifact 落 Control Plane；`research-state.json` 只留 summary / ID reference |
| SE3 | 无新 reviewer persona | 复用 `S-Lit` / `R-Novelty`，必要时 `R-Theory` |
| SE4 | 无新评分 | 不产 1—5 分、不产总分、不产第三套聚合。verdict 是 category，不是 score |
| SE5 | 无 venue 泄漏 | venue fit **不得**进入 Structural Equivalence 判断 |
| SE6 | 无 narrative 泄漏 | R12 的 preset `N1`—`N10` **不得**进入 Discovery / QD |
| SE7 | 不重新设计 pipeline | R3/R4/R6 = Diverge / Preserve Diversity / Recombine；R7 五元组；R8 证据契约；R10 修复；R13 artifact review；R14 decision 全部保持 |
| SE8 | 无文本相似度 / embedding | **禁止**用文本相似度、embedding similarity、普通 graph isomorphism 定义等价 |

**SE2 的判定口径：** 结构对齐的**大对象**（十四个 facet 的逐项对齐、逐边对应、反事实记录）
存在 Control Plane artifact 里；state 只保留 `audit_ref` 这样的路径引用与必要 summary。

---

## 3. Canonical Scientific Structure

### 3.1 十四个 scientific facets（冻结，逐字）

一个 candidate 或 prior 的 canonical structure **必须**表示以下十四个 facet。
facet 名一律用英文原样（`.json` 契约）。

| # | facet | 回答什么 |
|---|---|---|
| 1 | `problem` | 要解决的科学研究问题是什么 |
| 2 | `setting` | 在什么设定下做（实验/观测/理论条件） |
| 3 | `observables` | 能看到什么量 |
| 4 | `available_information` | 手上真正有什么信息 |
| 5 | `target_or_latent_quantity` | 想估计 / 恢复 / 推导的目标量 |
| 6 | `assumptions` | 承重假设 |
| 7 | `adaptation_or_intervention_object` | 被适配 / 被干预的对象是什么 |
| 8 | `objective` | 优化 / 证明的目标 |
| 9 | `mechanism` | 作用机制（因果 / 机制路径） |
| 10 | `information_flow` | 信息从哪来、经过什么、到哪去 |
| 11 | `theory_object` | 用的数学 / 理论对象 |
| 12 | `predictions_or_guarantees` | 可证伪 prediction 或 guarantee |
| 13 | `evaluation_target` | 用什么评、评什么 |
| 14 | `boundary_or_failure_regime` | 在什么条件下失效 / 不可能 |

**目标不是复杂 ontology。** 目标是获得一个足以回答「哪些 scientific element 与 relation 是承重的」
canonical representation。**不要**为完整性而扩张 facet 数。

### 3.2 typed relations（冻结，逐字）

facet 之间的关系**必须**是 typed relation。合法取值：

`observes` / `requires` / `assumes` / `estimates` / `transforms` / `optimizes` /
`constrains` / `implies` / `predicts` / `evaluated_by` / `fails_under`

**禁止**用无类型边（例如只写「A 相关 B」）。无类型边无法支撑 load-bearing 判定。

### 3.3 两条硬规则

1. **facet 值必须落到 concrete scientific content。** 只写「用了一个新理论」不是 facet 内容；
   必须写出该理论对象、它约束了什么、它导出了什么。
2. **关系必须可指向。** 每条 relation 的两端必须能在 alignment 里找到对应元素；
   悬空 relation 视为抽取失败，进 `blind_spots`。

---

## 4. 两套结构表示（必须同时产出）

每个 candidate / prior 都**必须**支持两套表示。两套缺一，audit 无效。

### 4.1 Domain-aware representation

**保留**：真实领域名、modality、task、data regime、architecture / method family、theory terminology。

例：`MRI` / `CT` / `source-free` / `Flow Matching` / `k-space`。

用途：判断**实际 setting 是否相同**。

### 4.2 Domain-stripped representation

**去掉**：domain names、method branding、theory branding、rhetorical terminology。
**替换成** structural roles。

例：`source population` / `target population` / `source unavailable` /
`indirect target observations` / `information-losing operator` / `frozen learned prior` /
`target-only adaptation`。

用途：判断**去掉包装以后，两项工作是不是同一个 scientific structure**。

### 4.3 硬规则：`domain-aware difference != paradigm novelty`

跨领域应用本身可以有价值，但**必须**区分五类 novelty：

| 类别 | 判据 |
|---|---|
| `transfer novelty` | domain-aware 不同，domain-stripped 结构基本相同 |
| `setting novelty` | 设定（data regime / 观测条件）不同，机制与 formulation 不变 |
| `mechanism novelty` | 作用路径 / information flow / adaptation mechanism 承重改变 |
| `formulation novelty` | observable / unknown / assumption / objective / information structure 改变 |
| `paradigm-level structural novelty` | 上述承重改变**同时**导出新的非平凡后果 |

**禁止**因为 domain 不同就判 paradigm-new。**禁止**因为理论名字不同就判 theory-new。

### 4.4 机器判据：`domain_terms`

Domain-stripped 表示**必须**真的去掉领域 / 品牌 / 理论名。
artifact **必须**登记 `domain_terms`：candidate 的领域名、方法品牌、理论品牌、修辞术语清单。

机械检查（`EQ6`）：`domain_stripped_alignment` 的**任一** facet 值**不得**包含 `domain_terms` 里的任一 token（大小写不敏感）。
这条检查不能证明「语义上真的去掉了」，但它能挡住「domain-stripped 其实原样复制」这类空转。

---

## 5. Load-Bearing Structural Delta

Structural Equivalence Audit 的核心**不是**「整体 similarity」。

> 它是：**candidate 相对 closest prior 的最小承重结构差异是什么？**

### 5.1 定义

一个 structural element 是 **load-bearing**，当且仅当改变它**会改变至少一种**：

1. `available information`
2. admissible hypothesis / solution space
3. critical assumption
4. causal / mechanistic path
5. optimization target
6. theoretical consequence
7. falsifiable prediction
8. algorithmic consequence
9. boundary / failure regime
10. discriminating experiment outcome

### 5.2 默认怀疑：relabeling

如果所谓新 theory / terminology 被替换后 —— **algorithm 不变、assumptions 不变、
predictions 不变、experiment 不变、failure boundary 不变** —— 则默认高度怀疑：

`theory relabeling / reframing-only`，而**不是** structural novelty。

### 5.3 机器判据（`EQ7` + `EQ8`）

`load_bearing_analysis` 的五个键**全部必填**，取非空字符串：

`changed_information` / `changed_assumptions` / `changed_mechanism` /
`changed_predictions` / `changed_boundary`

当 verdict 是 `mechanism-delta` / `formulation-delta` / `boundary-delta` / `paradigm-candidate` 时，
五个键里**至少一个**必须表示真实改变（**不得**全部是 `unchanged`）。
否则该 verdict 没有载体，判 `EQ7` 违规。

---

## 6. Counterfactual Collapse Test（必填）

对 candidate `H` 与 closest prior `P`：找到 candidate 声称的关键 delta `Δ`，做反事实：

```
H - Δ + Δ_prior
```

然后逐项检查：objective / information structure / assumptions / mechanism /
prediction / guarantee / discriminating experiment / failure regime **是否变化**。

判据：

- 替换后 scientific consequences **基本不变** ⇒ `Δ` **不是** load-bearing。
- 替换后**至少一个**关键 scientific consequence 消失或改变 ⇒ `Δ` **可能**是真正 structural delta。

### 6.1 artifact 必填项

`counterfactual_collapse` 是 audit artifact 的**必填项**。三个键：

| 键 | 取值 | 说明 |
|---|---|---|
| `replacement` | 非空字符串 | 具体替换了什么（`Δ` 换成 `Δ_prior` 的逐字描述）|
| `predicted_consequence` | 非空字符串 | 替换后预期哪个 consequence 会怎样 |
| `collapse_result` | `collapses` \| `partially-collapses` \| `does-not-collapse` | 反事实结论 |
| `verification_status` | `predicted` \| `derived` \| `executed` \| `unresolved` | 反事实被验证到什么程度（§6.3）|

### 6.2 机器判据（`EQ8` 的一致性）

`collapse_result` 与 `verdict` **必须**相容：

| `collapse_result` | 允许的 verdict |
|---|---|
| `collapses` | `equivalent` / `subsumed-by-prior` / `reframing-only` / `transfer-only` / `component-delta` |
| `partially-collapses` | 任意 verdict（但 `paradigm-candidate` 另需 ≥1 条 `differentiating_consequences`）|
| `does-not-collapse` | `mechanism-delta` / `formulation-delta` / `boundary-delta` / `paradigm-candidate` / `uncertain` |

**这条检查是本服务最关键的 anti-cheat：** 声称 strong novelty 却记录「替换后完全坍缩」，
或声称只是 relabeling 却记录「不坍缩」，都被机械拦下。

### 6.3 `verification_status`：「证据存在」不等于「反事实已验证」

`trust_basis` 回答「证据在哪」，`verification_status` 回答「反事实被推到了哪一步」。
**两者必须同时记录** —— `code exists` 不等于 `counterfactual was executed`；
`equation exists` 不等于 `equation proves the claimed non-collapse`。

| status | 含义 |
|---|---|
| `predicted` | LLM / 理论上预计会怎样 |
| `derived` | equation / proof / algorithm 能推出 |
| `executed` | 真正做过 executable-counterfactual / experiment |
| `unresolved` | 尚不可判 |

**硬规则（`NN14`）：** `collapse_result` 为 `does-not-collapse` 时，`verification_status`
**至少**为 `derived`。只有 `predicted` / `unresolved` 时，该反事实**只能**作为
**待验证 structural-delta hypothesis**，**不得**作为 strong structural evidence。
经验 / 算法类 claim 的目标档是 `executed`，但机械闸门只强制 `derived`（`executed` 由 R13 SENA-2 核）。

> **LLM proposes the counterfactual. Evidence executes and verifies it.**

---

## 7. Verdict：categorical，不是 numeric score

### 7.1 冻结枚举（十值，逐字）

| verdict | 含义 |
|---|---|
| `equivalent` | 科学结构没有实质差异 |
| `subsumed-by-prior` | candidate 的承重 scientific elements 已被某个 prior 覆盖 |
| `reframing-only` | 主要变化是 terminology / theory framing / narrative，结构不变 |
| `transfer-only` | domain-aware 明显不同，但 domain-stripped 结构基本等价 |
| `component-delta` | 组件变化，但 formulation / mechanism 基本不变 |
| `mechanism-delta` | 作用路径 / information flow / adaptation mechanism 出现承重差异 |
| `formulation-delta` | 改变 observable / unknown / assumption / objective / information structure |
| `boundary-delta` | 主要贡献是新的 impossibility / failure regime / identifiability boundary |
| `paradigm-candidate` | 存在明显 load-bearing structural change，并导出新的非平凡后果 |
| `uncertain` | 检索覆盖、结构抽取或对应关系不足，无法可靠判断 |

**必须叫 `paradigm-candidate`，不得叫 `paradigm-novel`。**
原因：open-world novelty **不能**被当前检索完全证明。`candidate` 一词保留了这个认识论边界。

**强 verdict 集合**（需要 minimal delta + collapse test + consequence）：
`mechanism-delta` / `formulation-delta` / `boundary-delta` / `paradigm-candidate`

**弱 verdict 集合**（**不得**支撑 paradigm novelty 声称）：
`equivalent` / `subsumed-by-prior` / `reframing-only` / `transfer-only` / `component-delta`

### 7.2 与 QD niche 七轴的对应（对应关系，**不是**新枚举）

QD niche 的七轴在 [research-state-policy.md](research-state-policy.md) §3.4 冻结。
本服务的 verdict 与它**不是**同一套枚举，**不得**互相替代。两者的对应关系仅供人类读者对齐：

| verdict | 对应 QD niche 轴 |
|---|---|
| `mechanism-delta` | `mechanism-shift` |
| `formulation-delta` | `formulation-shift` |
| `boundary-delta` | `boundary-shift` |
| `transfer-only` / `component-delta` | 不构成轴迁移（**不得**据此新开 niche）|

**禁止**把本表的右侧写成 `hypotheses[].niche` 的取值来源。`niche` 只能由 R3 按 QD 规则写。

---

## 8. Minimal Structural Delta Certificate（audit artifact 契约）

### 8.1 schema（逐字）

**`@2` = 本节的键 + §24 的 near-neighbor 必填键。** 两者缺一，artifact 无效。

```json
{
  "schema": "research-idea-pipeline/structural-equivalence-audit@2",
  "stage": "R7",
  "candidate": "H17",
  "closest_priors": ["LIT42", "LIT81"],
  "retrieval_status": "sufficient",
  "domain_terms": ["Flow Matching", "k-space"],
  "domain_aware_alignment": {
    "problem": "...",
    "setting": "...",
    "observables": "...",
    "available_information": "...",
    "target_or_latent_quantity": "...",
    "assumptions": "...",
    "adaptation_or_intervention_object": "...",
    "objective": "...",
    "mechanism": "...",
    "information_flow": "...",
    "theory_object": "...",
    "predictions_or_guarantees": "...",
    "evaluation_target": "...",
    "boundary_or_failure_regime": "..."
  },
  "domain_stripped_alignment": {
    "problem": "...",
    "setting": "...",
    "observables": "...",
    "available_information": "...",
    "target_or_latent_quantity": "...",
    "assumptions": "...",
    "adaptation_or_intervention_object": "...",
    "objective": "...",
    "mechanism": "...",
    "information_flow": "...",
    "theory_object": "...",
    "predictions_or_guarantees": "...",
    "evaluation_target": "...",
    "boundary_or_failure_regime": "..."
  },
  "matched_core": ["..."],
  "candidate_only_elements": ["..."],
  "prior_only_elements": ["..."],
  "minimal_structural_delta": ["..."],
  "load_bearing_analysis": {
    "changed_information": "...",
    "changed_assumptions": "...",
    "changed_mechanism": "...",
    "changed_predictions": "...",
    "changed_boundary": "..."
  },
  "counterfactual_collapse": {
    "replacement": "...",
    "predicted_consequence": "...",
    "collapse_result": "does-not-collapse",
    "verification_status": "derived"
  },
  "differentiating_consequences": ["..."],
  "discriminating_tests": ["..."],
  "claimed_novelty_level": "formulation-delta",
  "verdict": "formulation-delta",
  "novelty_boundary": "...",
  "blind_spots": ["..."],
  "evidence": ["LIT42", "LIT81"]
}
```

`_usage` 键可选，用于放维护说明。以 `_` 开头的键不参与校验。

### 8.2 必填规则（机器强制）

| # | 规则 |
|---|---|
| 1 | `schema` 必须逐字等于 `research-idea-pipeline/structural-equivalence-audit@2` |
| 2 | `stage` ∈ `R7` \| `R13`（SENA-1 / SENA-2）|
| 3 | `candidate` 必须是 `H<n>` |
| 4 | `closest_priors` 不得为空，**除非** `retrieval_status == retrieval-insufficient` |
| 5 | `retrieval_status` ∈ `sufficient` \| `retrieval-insufficient` |
| 6 | `domain_terms` 非空数组 |
| 7 | `domain_aware_alignment` 与 `domain_stripped_alignment` 各自含**全部十四个 facet**，取非空字符串 |
| 8 | `domain_stripped_alignment` 的值不得包含任何 `domain_terms` token |
| 9 | `matched_core` 非空 |
| 10 | `minimal_structural_delta` 在强 verdict 下非空 |
| 11 | `load_bearing_analysis` 五键齐全；强 verdict 下至少一键表示真实改变 |
| 12 | `counterfactual_collapse` 四键齐全，且与 `verdict` 相容（§6.2）、与 `verification_status` 相容（§6.3）|
| 13 | `differentiating_consequences` 在强 verdict 下非空 |
| 14 | `discriminating_tests` 在强 verdict 下非空 |
| 15 | `claimed_novelty_level` ∈ `none` \| `transfer-only` \| `component-delta` \| `mechanism-delta` \| `formulation-delta` \| `boundary-delta` \| `paradigm-candidate` |
| 16 | `verdict` ∈ 十个冻结值 |
| 17 | `novelty_boundary` 非空 |
| 18 | `blind_spots` 非空 |
| 19 | `evidence` 每个元素是 `LIT<n>` |
| 20 | `claimed_novelty_level` **不得**强于 `verdict`（§11.3 的相容表）|

---

## 9. 归属：state 与 control plane 分工

### 9.1 artifact 路径

| artifact | 路径 |
|---|---|
| SENA-1（R7，pre-experiment） | `.research-idea-pipeline/routes/<R>/assurance/structural-equivalence/<H>.json` |
| SENA-2（R13，realized-artifact） | `.research-idea-pipeline/routes/<R>/assurance/structural-equivalence/<H>.sena2.json` |
| R4 cheap fingerprint | `.research-idea-pipeline/routes/<R>/populations/fingerprints/<H>.json` |

三处都在既有 Control Plane 目录下（`assurance/` 与 `populations/`），
**不新增目录族**，**不分配** `C` / `E` / `X` ID，**不得**被当作结论引用。

### 9.2 `research-state.json` 只留 summary / ID reference

`research-state.json` **不得**承载完整 alignment。允许的落点是既有对象上的字段与已登记的可选扩展：

**(a) 复用既有字段（优先）**

| 位置 | 承载什么 |
|---|---|
| `hypotheses[].nearest_prior` | 最接近的结构前作（引 `LIT<n>`）|
| `hypotheses[].novelty_source` | 新颖性来自哪一轴（与 verdict 一致的类别描述）|
| `claims[].contract.nearest_alternative` | 最近替代解释（= closest prior 的结构主张）|
| `claims[].contract.minimal_discriminating_experiment` | 判别实验 |
| `claims[].contract.kill_rule` | 坍缩杀死条件 |
| `claims[].contract.refuting` | 什么证据会反驳 |

**(b) `assurance[]` 的可选扩展字段（新增槽位，已登记）**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `target` | `H` id 或 `C` id | ❌ | 该 attack 攻击的对象（五元组的 `Target`）|
| `attack_type` | 字符串 | ❌ | attack 类别；SENA 记录用字面量 `structural-equivalence` |
| `literature` | `LIT` id 数组，可为 `[]` | ❌ | 该 attack 用作 alternative 的前作 |
| `audit_ref` | 字符串 | ❌ | 指向 Control Plane audit artifact 的路径 |

`assurance[]` 原有三键（`kill_condition` / `discriminating_test` / `verification_tier`）
**保持必填不变**，由 `V9` 强制。新增四键为**可选**。

**形状保护归属：** 新增四键的形状由 `scripts/structural_equivalence_check.py` 强制（见 §12），
`state_check.py` 按既有约定忽略未知键。这一点是**有意的分工**：
`state_check.py` 管八类对象与 `S1`—`S7` / `V1`—`V24`，本服务管自己的 artifact 契约。

**SENA-1 的 `discriminating_test` 写法：** `V9` 要求它是**存在的 `X` id 或字面量 `TBD`**。
反事实坍缩**不是**实验节点，**不得**写进 `discriminating_test`。它写在 artifact 的
`counterfactual_collapse` 里。需要判别实验时填该 `X` id，否则填 `TBD` 并落一条 `U`。

### 9.3 与「第 16 个阶段」的边界

`assurance[]` 由 R7 写、`reviews[]` 由 R13 写、`repairs[]` 由 R10 写 —— 这条归属不变。
本服务只是在既有阶段里多产出一个 artifact 和一个 summary 引用。

---

## 10. 跨阶段接入

### 10.1 R4 — cheap structural fingerprint

R4 只做**便宜**的结构指纹，**不做**完整 literature novelty audit。

R4 做：

1. 为每个 `H` 产出一份 fingerprint artifact：
   `.research-idea-pipeline/routes/<R>/populations/fingerprints/<H>.json`，
   内含 `domain_aware` 与 `domain_stripped` 两套 facet 表示；
2. 做 intra-population dedup；
3. 做 proximity / structural clustering；
4. 帮助 QD archive 保持**真正的结构多样性**；
5. 标记明显 structural duplicate。

R4 **不得**：

- 宣称 prior novelty；
- 搜完整 literature；
- 给 novelty 分；
- 把 descriptor 变成 archive 内的全局排序信号（见 [phase-r3-r6-discovery.md](phase-r3-r6-discovery.md) §R4）。

R4 的数值载体仍是既有的 `hypotheses[].structural_signature` 五维整数距离（S4 强制）——
fingerprint artifact 是它的**文本补充**，**不是**替代，**不得**新增数值维度。

### 10.2 R5 — 三路 retrieval

对需要 Structural Equivalence 检查的 `H`，R5 **必须**至少产生三类 retrieval query：

| query 类 | 用什么语言 |
|---|---|
| `surface` | 原领域语言 |
| `facet` | `problem` / supervision-data regime / `observables` / `objective` / `mechanism` 等 scientific facets |
| `structure-stripped` | 去掉 domain / method / theory branding，只保留 abstract scientific skeleton |

最终：`retrieved priors = surface ∪ facet ∪ stripped`。

**重点避免：** 「MRI 文献里没人做，所以 idea 新」。Structural prior 可以来自
statistics / econometrics / causal inference / system identification / control /
inverse problems / optimization / information theory / 其他 ML 领域 ——
只要 structural correspondence 成立。

R5 的写集不变（`literature[]` + `evidence[]`）。

### 10.3 Literature Graph 的 typed relation

`literature[].relation` 的权威枚举是 [research-state-policy.md](research-state-policy.md) §3.5 的**六值封冻**：
`supports` / `contradicts` / `shares-assumption` / `shares-structure` /
`solves-analogous-problem` / `uses-same-theory`。本分支**不新增**取值。

结构等价特有的细粒度关系**落在 audit artifact 里**，并按下表映射到六值之一写回 `literature[].relation`：

| 结构关系（artifact 内） | 六值落点 |
|---|---|
| `same-assumption` | `shares-assumption` |
| `same-information-structure` | `shares-structure` |
| `same-mechanism` | `shares-structure` |
| `uses-same-theory` | `uses-same-theory` |
| `same-problem` | `solves-analogous-problem` |
| `subsumes-formulation` | `solves-analogous-problem` |
| `analogous-failure-mode` | `solves-analogous-problem` |
| `different-setting` | `solves-analogous-problem` |
| `supports-delta` | `supports` |
| `contradicts-delta` | `contradicts` |

**为什么复用而不扩展枚举：** 扩展一个被 `G2` 门禁消费的冻结枚举会改变既有阶段的语义；
细粒度信息在 artifact 里**不丢失**，而图边保持粗粒度稳定。这是**最小改动**。

### 10.4 R7 — SENA-1（pre-experiment structural novelty audit）

第一次正式运行放在 R7。**不新增 persona**，复用 `S-Lit` / `R-Novelty`，必要时 `R-Theory`。

输出仍遵循既有 Assurance 五元组：
`(Attack, Target, Alternative, Discriminating Test, Kill Condition)`。

示例（措辞可逐字使用）：

```
Attack:          H17 may be structurally equivalent to LIT42.
Target:          H17 novelty claim.
Alternative:     The proposed theory is a relabeling of the same adaptation mechanism.
Test:            Counterfactual collapse against LIT42.
Kill Condition:  If replacing the claimed delta leaves assumptions, predictions
                 and discriminating tests unchanged, paradigm-level novelty fails.
```

完整结构对齐放 audit artifact。state 侧写 `assurance[]` 一条，并填可选键
`target` / `attack_type` / `literature` / `audit_ref`。

**时机边界：** R7 / R8 **不得**要求 artifact 审计（那时还没有 artifact）。
R7 的 SENA-1 审的是**方案**，不是实现。

### 10.5 R8 — novelty claim 必须绑定 structural delta

R8 **不重新判断** novelty。R8 只负责让 central novelty claim 明确绑定：
closest priors、minimal structural delta、differentiating consequence、
discriminating experiment、structural-equivalence audit。

绑定到既有 `claims[].contract` 键上：`nearest_alternative` /
`minimal_discriminating_experiment` / `kill_rule` / `refuting`。

| SENA verdict | R8 允许的 claim |
|---|---|
| `equivalent` / `subsumed-by-prior` / `reframing-only` | **不得**建立 paradigm novelty central claim |
| `transfer-only` | 必须缩窄：contribution 是 transfer / application / legitimacy，**不是**新 paradigm |
| `component-delta` | **不得**包装成 formulation / paradigm novelty |
| `mechanism-delta` / `formulation-delta` / `boundary-delta` / `paradigm-candidate` | 允许更强 claim，但**必须**在 Evidence Contract 写明其 load-bearing delta |
| `uncertain` | **不得**支撑强于 `uncertain` 的 claim；先补检索或补结构抽取 |

### 10.6 R10 — prior collision 的修复语义

发现 structural equivalence 时，**不要**自动把 scientific claim 改成 `contradicted`。

> **novelty claim 失败 != scientific proposition false.**

R10 的合理处置**必须**映射到既有冻结枚举（`disposition` 五值 + `closure` 两值），**不得**新增取值：

| 语义意图 | 落点 |
|---|---|
| `NARROW_CLAIM` | `disposition: NARROW_SCOPE` |
| `REFRAME` | `disposition: REPAIR_CLAIM` |
| `MERGE_WITH_PRIOR` | `disposition: REPAIR_CLAIM` + `state_delta` 指向 nearest prior |
| `RUN_MORE_RETRIEVAL` | `disposition: RUN_TEST`，并把检索写成该 claim 的 discriminating experiment |
| `DEPRIORITIZE_H` | `hypotheses[].status: archived` + `failures[].kind: deprioritized` |
| `ARCHIVE_BRANCH` | `disposition: KILL_BRANCH` |
| `ACCEPT_LIMITATION` | `closure: ACCEPTED_LIMITATION` |

Failure Memory 记录：`kind: prior-collision` **不是**合法枚举值。
用既有 `kind`（`unsupported` / `deprioritized` / `inconclusive`）并把碰撞写在 `what` / `why`。

只有 prior **真正提供反驳 scientific proposition 的证据**时，才走 `contradicted`，
且**必须**经 R10（V22 强制）。

### 10.7 R13 — SENA-2（realized-artifact audit）

**必须有第二次 structural-equivalence audit。** 原因：proposal 阶段声称「新 formulation / 新 mechanism」，
真正实现后可能退化成「baseline + mask + loss」。

R13 **必须**从**实际**代码 / equation / experiment / mechanism / result 提取 `G_realized`，
并与 `G_planned` 和 `G_prior` 比较，检测 **novelty drift**：

```
planned:  formulation-delta
   ↓
realized: component-delta
```

这种 downgrade **必须**进入 review / repair，**不得**继续按原 novelty claim 投稿。

落点：R13 写 `reviews[].findings` 与 `reviews[].integrity_gate`；
任何未闭合的 drift 缺口**必须**落 `repairs[]`（经 R10 语义，V23 强制）。
SENA-2 artifact 路径见 §9.1。

### 10.8 R14 — 可见性

R14 `decision.rationale` **必须**能体现：novelty drift、未解决的 structural collision。
R14 **不得**直接改 `claims[].status`（既有硬 invariant 不变）。

---

## 11. 认识论措辞边界

### 11.1 未发现结构等价前作时的唯一合法说法

对「未发现结构等价 prior」的结果**只能**写：

> **against the retrieved literature, no structural equivalent was identified**
> （据本次检索未见结构等价前作，检索式见附录 X）

**不得**写：

- `no prior work exists` / 「没有任何前作」
- `first` / 「首次」/ 「首次提出」
- `unprecedented` / 「前所未有」
- 「该方向空白」/「无人研究」

措辞等级一律查 [evidence-policy.md](evidence-policy.md) §1 与 [literature-policy.md](literature-policy.md)。
本服务**不新增**措辞等级。

### 11.2 机器判据（`EQ10`）

当 `retrieval_status == retrieval-insufficient` 或 `closest_priors` 为空时，
`novelty_boundary` **不得**包含禁用字面量（见上表），且**必须**包含 `retrieved literature` 或
`据本次检索未见` 之一。

---

## 12. 机械闸门：`structural_equivalence_check.py`

检查器：`scripts/structural_equivalence_check.py`。它**只验证**：

1. 审计做没做**完整**；
2. 引用**是否存在**；
3. schema 是否**满足**；
4. claim 强度是否有**对应审计**。

它**不得**自动宣判「idea 是新的」。**没有**任何规则形如「idea must be novel」。

### 12.1 规则表

**下表是 `scripts/structural_equivalence_check.py` 的 `RULES` 契约。**
「判据」列与代码常量**逐字相同**（`test_structural_equivalence.py` 逐条比对）；
改一处必须同轮改另一处。

| 规则 | 判据 |
|---|---|
| `EQ1` | 声称为强 novelty 的 candidate 必须有 SENA artifact，且有对应 assurance[].audit_ref |
| `EQ2` | candidate 指向的 H 必须在 state 中存在 |
| `EQ3` | closest_priors 与 evidence 的每个 LIT 必须在 state 中存在 |
| `EQ4` | closest_priors 非空，或 retrieval_status 为 retrieval-insufficient |
| `EQ5` | domain_aware_alignment 完整（十四个 facet + typed relations 可解析） |
| `EQ6` | domain_stripped_alignment 完整，且不含 domain_terms |
| `EQ7` | minimal_structural_delta 与 load_bearing_analysis 在强 verdict 下完整 |
| `EQ8` | counterfactual_collapse 完整，且与 verdict 相容 |
| `EQ9` | differentiating_consequences 与 discriminating_tests 在强 verdict 下完整 |
| `EQ10` | blind_spots 非空；未发现等价时 novelty_boundary 措辞合法 |
| `EQ11` | verdict 属于十个冻结值 |
| `EQ12` | audit_ref 指向合法 Control Plane artifact 路径，且与磁盘 artifact 双向一致 |
| `EQ13` | 更强的 claimed_novelty_level 不得与更弱的 verdict 冲突 |

退出码与仓库既有脚本一致：`0` 通过 / `1` 参数错误 / `3` 硬违规 / `4` 环境不满足。

### 12.2 兼容表（`EQ13`）

`claimed_novelty_level` 相对 `verdict` 只能**等强或更弱**：

| `verdict` | 允许的 `claimed_novelty_level` |
|---|---|
| `equivalent` / `subsumed-by-prior` / `reframing-only` | `none` |
| `transfer-only` | `none` / `transfer-only` |
| `component-delta` | `none` / `transfer-only` / `component-delta` |
| `mechanism-delta` | 上列 + `mechanism-delta` |
| `formulation-delta` | 上列 + `formulation-delta` |
| `boundary-delta` | 上列 + `boundary-delta` |
| `paradigm-candidate` | 全部（含 `paradigm-candidate`）|
| `uncertain` | `none` / `transfer-only` / `component-delta` |

### 12.3 发布闸门接入

检查器**必须**挂进唯一发布闸门 `scripts/release_check.py`（AGENTS.md Rule 10：
「Add a new gate to that command. Do not add a manual step.」）。
闸门步骤至少跑：自带自检 `--selftest`、audit 模板校验、以及七份 fixture 校验。
该步骤必须**可被变异注入判红**（有反例证明它不是恒真）。

---

## 13. 明令禁止的退化

看到下面任何一条，立即视为**设计回归**。

| # | 禁止 | 为什么 |
|---|---|---|
| 1 | `structural_similarity_score = 0.83`，然后 `<0.5 => novel` | 这是第三套评分，且把连续量当判据 |
| 2 | 只问一个 LLM「Is this idea structurally novel?」 | LLM 不是 truth oracle |
| 3 | 把 embedding distance 当 paradigm novelty | 文本相似度不是结构 |
| 4 | 因为 domain 不同就判 paradigm-new | 跨领域搬运不是范式创新 |
| 5 | 理论名字不同就判 theory-new | branding 不是结构 |
| 6 | prior collision 后直接 `claims[].status = contradicted` | novelty 失败与科学证伪必须区分 |
| 7 | 为实现 SENA 新增 `structural_equivalence[]` 第九类 state object | 越 SE2 |
| 8 | 为 SENA 再新增一个 reviewer persona | 越 SE3 |

---

## 14. 评估：内部指标与 metamorphic 套件

### 14.1 内部指标（定义，不产分数给 candidate）

| 指标 | 定义 | 优先 |
|---|---|---|
| `FalseParadigmRate` | structurally equivalent / reframing-only 的 idea 被误判成 `paradigm-candidate` 的比例 | **最高优先降低** |
| `StructuralCollisionRecall` | 真实 prior collision 被检出的比例 | 高 |
| `DeltaLocalizationAccuracy` | 最小承重 delta 定位与人类判断一致的比例 | 中 |
| `TransferVsParadigmConfusion` | `transfer-only` 与 `paradigm-candidate` 的混淆率 | 中 |
| `TheoryRelabelDetectionRate` | theory relabeling 检出率 | 高 |

这些是**系统级评测指标**，**不是**候选的 score，**不得**写进 state。

### 14.2 metamorphic 套件（T1—T10）

套件**必须**覆盖下表。期望值是 verdict，不是分数。

| # | 变体 | 期望 verdict |
|---|---|---|
| T1 | Terminology Rename（同一方法只改术语）| `equivalent` |
| T2 | Theory Relabel（算法 / assumption / prediction 不变，只换 theory framing）| `reframing-only` |
| T3 | Cross-Domain Transfer（domain 变，domain-stripped 结构不变）| `transfer-only` |
| T4 | Component Mutation（只换 regularizer / block / attention / optimizer）| `component-delta` |
| T5 | Mechanism Mutation（真正改变 information flow / adaptation mechanism）| `mechanism-delta` |
| T6 | Assumption Removal（移除承重 assumption，并改变 prediction / solution space）| `formulation-delta` |
| T7 | New Boundary（方法类似，但发现新的 impossibility / identifiability / failure regime）| `boundary-delta` |
| T8 | Narrative Rewrite（论文故事完全重写）| `equivalent` |
| T9 | Hidden Prior Collision（表面关键词差异大，stripped structure 一致）| `equivalent` 或 `subsumed-by-prior` |
| T10 | Genuine Paradigm Candidate（problem representation / assumption / prediction / discriminating test 均承重变化）| `paradigm-candidate` |

这些测试的重点不是评估 LLM 的科学真理能力，而是验证 pipeline **不会**因为表面改写产生错误 verdict。

### 14.3 外部 benchmarking

如条件允许，后续可用已有 research novelty benchmark 做**辅助**评估。
**不得**把它当作 Structural Equivalence 的完全 gold standard。

---

> **§1—§14 是结构等价契约；§15 起是 near-neighbor 判断层。两层同属一个服务。**
> near-neighbor 判断层只把「局部邻域」判得更准，**不改变** §1—§14 的任何硬约束。

---

## 15. Near-neighbor 定义（冻结）

### 15.1 禁用的判据

以下判据**不得**用于判断 near-neighbor：

- embedding cosine similarity
- keyword overlap
- method name similarity
- theory name similarity
- domain similarity

### 15.2 scientific structure

candidate `H` 与 prior `P` 的 scientific structure 记为 `G(H)` 与 `G(P)`。
至少包含 §3.1 的**十四个 node**与 §3.2 的**十一个 relation**。

### 15.3 定义

> **candidate 与 prior 在绝大多数 load-bearing node + relation 上保持一致，
> 仅剩局部 component / terminology / implementation 差异，则该 prior 是 candidate 的
> structural near-neighbor。**

**语义距离远不等于结构距离远。** 一个 candidate 的 language、domain、theory framing、
implementation 全都可以看起来不同，而 load-bearing structure 仍然被保留。

---

## 16. Preserved Core / Structural Delta / Local Neighborhood Test

### 16.1 Preserved Core（复用 `matched_core`）

**Preserved Core 就是 artifact 的 `matched_core`**（§8.1 已有键，不新增）。
逐项列出 candidate 与 prior 之间**保持不变**的结构：

information regime / assumptions / scientific target / objective / intervention object /
mechanism path / prediction structure / evaluation target。

### 16.2 Structural Delta（复用 `minimal_structural_delta`）

**Structural Delta 就是 artifact 的 `minimal_structural_delta`**（§8.1 已有键，不新增）。

只有 delta 改变以下**至少一项**时，才**可能**离开近邻：

available information / admissible solution space / critical assumption /
adaptation object / causal-mechanistic path / theoretical consequence /
falsifiable prediction / boundary-failure regime / discriminating experiment。

### 16.3 Local Neighborhood Test

对 `H` 取若干 closest structural prior `P1 … Pk`，逐一检验：

```text
H = P + local modification
```

`local modification` **只允许**属于下表（冻结，逐字）：

| local modification 类别 |
|---|
| `loss-replacement` |
| `module-replacement` |
| `regularizer` |
| `weighting` |
| `optimizer` |
| `masking` |
| `adapter` |
| `schedule` |
| `architectural-block` |
| `hyperparameter` |
| `implementation-detail` |

若同时满足：`problem` 不变、`observables` 不变、`assumptions` 基本不变、`target` 不变、
`mechanism` 主路径不变、`prediction` 不变、`boundary` 不变 —— 则**默认**判定 `near-neighbor`。

**即使论文语言、理论解释、领域名称非常不同，也一样判 `near-neighbor`。**

**落地键：** `local_neighborhood_test`（§24）。

---

## 17. Removal Test 与 Replacement-Collapse Test

### 17.1 Removal Test

对 candidate 声称的新元素 `Δ` 执行 `H - Δ`，问：去掉 `Δ` 后 candidate 是否基本退回某个 prior？

若 **performance 可能变化**，但 scientific question / information structure / assumptions /
mechanism 主路径 / prediction / failure regime **全都保持不变**，
则 `Δ` 是 `component/local delta`，**不是** paradigm delta。

**落地键：** `removal_test`（§24）。

### 17.2 Replacement-Collapse Test（扩展 §6）

执行 `H - Δ_candidate + Δ_prior`，检查 objective / algorithm / assumptions / mechanism /
predictions / regime-shift behavior / discriminating experiment **是否仍无法区分**。

若全部或绝大多数保持 —— **candidate collapses to prior neighborhood**。
判 `structural near-neighbor`，或判 §23 的 neighbor 家族，**不得**声称 paradigm novelty。

`counterfactual_collapse`（§8.1 已有键）就是本测试的落地键，**不新增键**。

---

## 18. 两套表示与 transfer 优先判据

两套表示的定义见 §4（`domain_aware_alignment` / `domain_stripped_alignment`）。
本层**不新增**表示，只加一条判据：

> 若 `domain-aware distance = high` 且 `domain-stripped structural distance = low`，
> **优先**判 `transfer-neighbor`（`transfer-only`），**不得**判 paradigm novelty。

**domain-stripped 的机械判据仍是 `EQ6`**（值不得含 `domain_terms`）。
`transfer-neighbor` 因此**必须**先有非空 `domain_terms` —— 这就是「做过 domain-stripped 比较」的机械落点。

---

## 19. Theory-Stripping Test（P5 必须做）

对 P5 / theory-driven candidate，**必须**先写出原始描述，再做 theory stripping。

**删除：** theory 名、theorem 名、专业术语、analogy language。

**只保留：** assumptions、variables、observables、transformations、mechanism、predictions、boundary。

| stripping 后的结果 | 结论 |
|---|---|
| `candidate ≈ prior` | `theory-relabeling-risk` 或 `reframing-only` |
| 产生了下表任一新结构 | `theory-substantive` |

**「新结构」的冻结类别**（逐字）：

| 类别 |
|---|
| `new-assumption` |
| `new-identifiable-object` |
| `new-prediction` |
| `new-impossibility` |
| `new-algorithmic-consequence` |
| `new-discriminating-experiment` |

**除非** theory lens 真正产生上表至少一项，否则**不得**据此判强 novelty。

**机械触发：** 当 `hypotheses[].operator` 为 `theory_lens`（`P5`）时，`applicable` **必须**为 true（`NN10`）。

**落地键：** `theory_stripping`（§24）。

---

## 20. Structure-Preservation Test（P4 remote analogy 必须做）

P4 **不得**因为「这个 idea 来自一个很远的领域」就获得高 novelty。

对 remote analogy，**必须**显式列出四类映射：

object mapping / relation mapping / constraint mapping / failure-mode mapping

然后问：**这个 analogy 给当前问题增加了什么 prior 本来没有的 scientific structure？**

若只发现「两个领域用不同术语描述同一个关系结构」，则：

> **remote analogy != structural novelty**

它**可以**作为 explanation / transfer / interpretation，**不得**自动升级成 paradigm novelty。

**机械触发：** 当 `hypotheses[].operator` 为 `remote_analogy`（`P4`）时，`applicable` **必须**为 true（`NN11`）。

**落地键：** `remote_analogy_mapping`（§24）。

---

## 21. Provenance、三值关系与可信度来源

### 21.1 每个 facet 的 provenance（冻结四值）

| 值 | 含义 |
|---|---|
| `EXPLICIT` | 原文明确陈述 |
| `DERIVED` | 可由 equation / algorithm / code 明确推出 |
| `INFERRED` | LLM 的解释性推断 |
| `UNKNOWN` | 证据不足 |

**near-neighbor 判断的关键结论不得主要依赖 `INFERRED`。**
若关键 `mechanism` / `assumptions` / `predictions_or_guarantees` 的对应关系存在大量
`INFERRED` / `UNKNOWN`，则 verdict **必须允许** `uncertain`。

**另外硬要求：** 每个 facet 的 correspondence 必须带非空 `evidence_span`（原文 span / equation / code 位置）。
没有 span 的对应关系不是证据，是猜测。

### 21.2 三值 relation（禁止二值强制）

| 值 | 含义 |
|---|---|
| `MATCH` | 有证据表明结构一致 |
| `DIFFERENT` | 有证据表明结构不同 |
| `UNRESOLVED` | 证据不足 |

**禁止**模型在证据不足时强制选择 `MATCH` / `DIFFERENT`。`UNRESOLVED` **必须**被保留。

**对称不确定性闸门（`NN3`，冻结）：**

> **Unknown evidence should block both novelty inflation and premature neighbor collapse.**

`load_bearing_facets` 中**任一** facet 为 `UNRESOLVED` 时，`near_neighbor_verdict` **必须**为 `uncertain`：

- **不得**判 delta 家族（`structural-delta` / `structural-delta-strong`）—— 防止「证据没搞清就宣布结构创新」；
- **不得**判 neighbor 家族（`duplicate-equivalent` / `reframing-neighbor` / `transfer-neighbor` /
  `component-neighbor` / `mechanism-neighbor`）—— 防止「不知道 mechanism 是否不同」被默认成「它是近邻」。

**为什么必须对称：** SENA 是 **claim-strength gate，不是 idea-kill gate**。
误判 `uncertain` 的成本只是「暂时不能声称强 novelty」；
误判 `component-neighbor` 的成本是**一个真正远端的 idea 被系统错误降级**。后者更危险。

**由此产生的相容要求**（由既有规则分别强制，不需要新增规则）：

| 情形 | 必须 |
|---|---|
| `near_neighbor_verdict == uncertain` | `local_neighborhood_test.neighbor_confirmed` 必须为 `false`（否则 `NN6`）|
| `near_neighbor_verdict == uncertain` | `removal_test.conclusion` 不得为 `component-local-delta`（否则 `NN7`）|

即：**证据不足时，「已确认是近邻」与「已确认是局部 delta」都不能成立。**

### 21.3 可信度来源（禁止「多 LLM 同意 = 结构事实」）

可以使用多个 pass —— `Extractor` / `Aligner` / `Adversarial Matcher` / `Delta Critic`。
它们**只是任务分解**，**不是**独立证据。

**禁止**声称：「4 个 Agent 都认为不是近邻，所以结论可靠。」
同一个基础模型换 prompt 仍然高度相关。

真正提升可信度的来源**必须**是下表之一（冻结，逐字）：

| 可信度来源 |
|---|
| `source-span` |
| `equation` |
| `algorithm` |
| `code` |
| `literature` |
| `executable-counterfactual` |
| `discriminating-experiment` |
| `expert-validation` |

**落地键：** `trust_basis`（§24），必须非空。

**`does-not-collapse` 必须有可执行证据：** 若 `collapse_result` 为 `does-not-collapse`，
`trust_basis` **必须**至少含 `equation` / `algorithm` / `code` / `executable-counterfactual` /
`discriminating-experiment` 之一。只有 LLM 断言、没有 equation / code / experiment 支持的「不坍缩」
**不算**证据（见 §32 的反事实幻觉）。

---

## 22. Null Hypothesis 与 Minimal Delta Principle

### 22.1 Null Hypothesis（默认先证明它是近邻）

Structural Audit 的 adversarial pass **必须**从下式出发：

```text
H0: candidate is structurally subsumed by an existing prior
```

**不得**一上来就问「candidate 有什么创新」。

系统**必须主动构造** `candidate → closest prior` 的**最大覆盖映射**。
只有当该映射在某个 load-bearing structural element 上**无法成立**，才产生 structural delta candidate。

```text
Novelty = residual after the strongest prior subsumption attempt
```

**不是** `Novelty = LLM 能想到的差异列表`。

**落地键：** `null_hypothesis`（§24）。`statement` 逐字为上式英文原文。

### 22.2 Minimal Delta Principle

**不接受**「candidate 和 prior 有 12 个不同点」。

**必须**找出能解释 candidate scientific novelty 的**最小** delta set `Δ*`（例：`{observable-subspace restriction}`）。

然后检查：**仅凭 `Δ*` 是否就能推出**下列至少一项？

new prediction / new theorem / new boundary / new algorithm / new experiment

若不能，则当前所谓 structural delta **不是 load-bearing**。

**落地键：** `minimal_delta_set`（§24）。冻结的 `novel_consequence_kinds` 逐字为：
`prediction` / `theorem` / `boundary` / `algorithm` / `experiment`。

---

## 23. `near_neighbor_verdict`（冻结八值）

### 23.1 枚举（逐字）

| verdict | 含义 |
|---|---|
| `duplicate-equivalent` | 几乎完全结构等价 |
| `reframing-neighbor` | 主要变化是 narrative / theory / terminology |
| `transfer-neighbor` | 领域变了，domain-stripped structure 基本不变 |
| `component-neighbor` | 只发生局部组件改变 |
| `mechanism-neighbor` | mechanism 有变化，但 problem / formulation / information structure 仍处于同一局部邻域 |
| `structural-delta` | 至少一个 load-bearing structure 明显变化 |
| `structural-delta-strong` | load-bearing delta 同时产生新的 prediction / boundary / discriminating experiment 等 |
| `uncertain` | 检索覆盖、结构抽取或对应关系不足 |

**neighbor 家族**（不得支撑强 novelty 声称）：
`duplicate-equivalent` / `reframing-neighbor` / `transfer-neighbor` / `component-neighbor` / `mechanism-neighbor`

**delta 家族**：`structural-delta` / `structural-delta-strong`

> **`structural-delta-strong` 仍然不等于 `globally novel`。**
> 它只代表：**against current retrieved priors，存在强结构差异。**
>
> **它的门槛是 heuristic 代理判据，不是真值。** 冻结的门槛是「至少两种不同的
> `novel_consequence_kinds`，且含 `boundary` 或 `experiment`」（`NN9`）。
> 这是把 §14 的「同时产生」措辞落成可机械检查的形状，**不得**被读成对科学价值的判定。

### 23.2 与 `verdict` 的相容表（`NN12`）

`near_neighbor_verdict` 是**claim 强度的决定项**；`verdict` 仍是 delta 类型记录。两者**必须**相容：

| `near_neighbor_verdict` | 允许的 `verdict` | `claimed_novelty_level` 上限 |
|---|---|---|
| `duplicate-equivalent` | `equivalent` \| `subsumed-by-prior` | `none` |
| `reframing-neighbor` | `reframing-only` | `none` |
| `transfer-neighbor` | `transfer-only` | `transfer-only` |
| `component-neighbor` | `component-delta` | `component-delta` |
| `mechanism-neighbor` | `mechanism-delta` | `mechanism-delta` |
| `structural-delta` | `formulation-delta` \| `boundary-delta` | `boundary-delta` |
| `structural-delta-strong` | `paradigm-candidate` | `paradigm-candidate` |
| `uncertain` | `uncertain` | `component-delta` |

---

## 24. artifact 契约（`@2`）：near-neighbor 必填键

**schema 版本升为 `research-idea-pipeline/structural-equivalence-audit@2`。**
`@2` = §8.1 的全部键 + 本节全部键。随后者为**必填**。

| 键 | 取值 / 类型（逐字） | 说明 |
|---|---|---|
| `near_neighbor_verdict` | §23.1 八值之一 | **必填** |
| `correspondence` | 对象，键恰为十四个 facet | 每项见下 |
| `correspondence.<facet>.relation` | `MATCH` \| `DIFFERENT` \| `UNRESOLVED` | 三值，不得二值强制 |
| `correspondence.<facet>.provenance` | `EXPLICIT` \| `DERIVED` \| `INFERRED` \| `UNKNOWN` | 四值 |
| `correspondence.<facet>.evidence_span` | 非空字符串 | 原文 span / equation / code 位置 |
| `correspondence.<facet>.note` | 非空字符串 | 判断依据 |
| `load_bearing_facets` | facet 名数组，非空 | 承重 facet 清单 |
| `local_neighborhood_test` | 对象 | 四键：`near_prior`（`LIT<n>`）/ `local_modification_kinds`（§16.3 枚举，可为 `[]`）/ `neighbor_confirmed`（bool）/ `rationale`（非空） |
| `removal_test` | 对象 | 四键：`removed_delta` / `returns_to_prior`（`LIT<n>` 或 `""`）/ `unchanged_core`（数组）/ `conclusion` ∈ `component-local-delta` \| `load-bearing-delta` \| `unresolved` |
| `null_hypothesis` | 对象 | 四键：`statement`（逐字英文原文）/ `strongest_subsumption_prior`（`LIT<n>`）/ `mapping_completeness` ∈ `full` \| `partial` \| `failed` / `unmapped_load_bearing_elements`（数组） |
| `minimal_delta_set` | 对象 | 三键：`delta_set`（数组）/ `novel_consequence_kinds`（§22.2 枚举）/ `sufficient_alone`（bool） |
| `theory_stripping` | 对象 | 六键：`applicable`（bool）/ `stripped_terms`（数组）/ `residual_structure`（字符串）/ `adds_new_structure`（bool）/ `new_structure_kinds`（§19 枚举）/ `conclusion` ∈ `theory-relabeling-risk` \| `reframing-only` \| `theory-substantive` \| `not-applicable` |
| `remote_analogy_mapping` | 对象 | 七键：`applicable`（bool）/ `object_mapping` / `relation_mapping` / `constraint_mapping` / `failure_mode_mapping`（非空字符串）/ `added_structure`（bool）/ `conclusion` ∈ `structural-novelty` \| `explanation-only` \| `transfer` \| `interpretation` \| `not-applicable` |
| `trust_basis` | §21.3 枚举数组，非空 | 可信度来源 |
| `retrieval_heuristic` | 对象，**可选** | 仅两键：`scalar_distance`（数值）/ `use`（逐字 `retrieval-clustering-only`） |

**`applicable == false` 时**：`theory_stripping` / `remote_analogy_mapping` 的其余内容键可省，
但 `conclusion` **必须**是 `not-applicable`。

---

## 25. 阶段分工：R3 / R4 / R5 / R7

**必须保护发散性。**

| 阶段 | 做什么 | 不做什么 |
|---|---|---|
| **R3** | **只生成**，`generate first` | **不运行**正式 near-neighbor gate |
| **R4** | intra-population structural dedup / cheap fingerprint / clustering / detect obvious duplicate candidates | **不得**做 literature-level novelty kill |
| **R5** | 找 surface priors + facet priors + structure-stripped priors，构造 **closest structural prior set** | 不下最终 verdict |
| **R7** | 正式 near-neighbor audit：strongest prior subsumption / theory stripping / domain stripping / collapse test / minimal delta / unresolved mapping，然后决定**当前最大 defensible novelty claim** | 不改 `claims[].status`（走 R10） |

---

## 26. Claim-strength gate（不是 idea-kill gate）—— 硬 invariant

> **Near-neighbor verdict 约束的是「能声称什么」，不是「值不值得做」。**

- `component-neighbor` **不表示** idea 不值得做 —— 它可能 performance 很强、utility 很高、efficiency 很好。
  它只表示**不能声称 paradigm novelty**。
- `transfer-neighbor` **可以**形成很好的 cross-domain paper。

系统的动作是 **`constrain claim strength`**，**不是** `automatically kill candidate`。
**任何实现若把 near-neighbor verdict 变成淘汰开关，视为设计回归。**

---

## 27. 发散性保护（不得破坏 anti-incremental 架构）

本 feature **不得**破坏下列既有机制：

Local Search ‖ Paradigm Escape；`P1`—`P6` isolated operators；`P3` domain erasure；
`P4` remote analogy；`P5` theory lens；`P6` counterexample；coverage before ranking；
QD archive；serving + challenging candidates；delayed R6 crossover；stagnation / reseeding。

> Structural audit 是「检查生成的**远**是不是真的远」，**不是**「阻止系统生成远 idea」。

---

## 28. Population-level near-neighbor telemetry

除 candidate-prior 判断外，还要检测**整个 generation 是否又掉回 local basin**。

**落盘（telemetry，不进 Research State）：**

```text
.research-idea-pipeline/routes/<R>/populations/near-neighbor-telemetry.json
```

| 指标 | 含义 |
|---|---|
| `StructuralCoverage` | 七个 QD axis 有多少被覆盖 |
| `PairwiseStructuralDistance` | population 内候选结构距离 |
| `CrossIslandRedundancy` | `P1` / `P2` / `P4` / `P5` 是否最终都落在同一结构簇 |
| `LocalCollapseRate` | 多少候选最终被判 `component` / `reframing` neighbor |
| `RemoteConversionRate` | `P4` / `P5` 的候选有多少形成真正的 formulation / theory / boundary delta |
| `UncertaintyAsymmetry` | 面对不完整证据时，系统判 `neighbor` 与判 `delta` 的比例是否对称；理想是两者都收敛到 `uncertain` |

`UncertaintyAsymmetry` 使用同一轮、同一检索快照下的首次审计提案。
在机械闸门修正前记录提案，包含被拒绝的提案。每个 candidate-prior pair 只计一次。
分母 `n` 是至少一个 load-bearing facet 为 `UNRESOLVED` 的提案数。
分别记录 `neighbor_count / n`、`delta_count / n` 和 `uncertain_count / n`。
neighbor / delta 家族采用 §23 的枚举。非法 verdict 单独计数，不移出分母。
`n = 0` 时比例记录为 `null`。同时保留样本数与审计引用，支持复核。
两种误判率都应为零，不能只看两者之差。相等的高误判率也不是成功。
这些比例只用于诊断，不作为 reward、novelty gate 或候选淘汰条件。

**两条硬规则：**

1. **这些指标不得进 `research-state.json`。**
2. **不得用它们直接奖励模型** —— 否则会诱导「为了距离而胡思乱想」。

---

## 29. 禁止 scalar structural_distance 决定 novelty

**禁止**下列写法：

```text
distance = 0.73
if distance > 0.6:
    novel = True
```

科学结构是**异质、多轴**的。正确形状是逐 facet 的 `MATCH` / `DIFFERENT` / `UNRESOLVED`，
再结合 load-bearing 规则判断。

**必要时可以把 scalar 用作 retrieval / clustering heuristic。**
但 **scalar distance 不得直接决定 novelty claim**。
落地方式：只在 `retrieval_heuristic` 里出现，且 `use` 逐字为 `retrieval-clustering-only`（`NN13`）。

---

## 30. 机械闸门：`NN1`—`NN14`

检查器仍是 `scripts/structural_equivalence_check.py`。**它只验证审计纪律，不决定
`H` 与 `P` 是否真的结构等价。**

**下表是 `RULES` 的契约；「判据」列与代码常量逐字相同。**

| 规则 | 判据 |
|---|---|
| `NN1` | correspondence 必须完整：十四个 facet 全在，且不含额外键 |
| `NN2` | correspondence 每项的 relation / provenance 必须在冻结枚举内，且 evidence_span 非空 |
| `NN3` | UNRESOLVED 必须被保留；load_bearing_facets 中任一 facet 为 UNRESOLVED 时 near_neighbor_verdict 必须为 uncertain（不得据此判 neighbor 家族，也不得判 delta 家族） |
| `NN4` | load_bearing_facets 必须非空且是十四个 facet 的子集 |
| `NN5` | 关键结论不得主要依赖 INFERRED；load-bearing facet 中 EXPLICIT / DERIVED 少于一半时禁止 structural-delta，且 trust_basis 必须非空、collapse_result 为 does-not-collapse 时另需 equation / algorithm / code / executable-counterfactual / discriminating-experiment 之一 |
| `NN6` | local_neighborhood_test 必须完整；neighbor_confirmed 为 true 时 near_neighbor_verdict 必须是 neighbor 家族 |
| `NN7` | removal_test 必须完整；结论为 component-local-delta 时 near_neighbor_verdict 必须是 neighbor 家族 |
| `NN8` | null_hypothesis 必须完整且 statement 逐字；mapping_completeness 为 full 时禁止 structural-delta |
| `NN9` | minimal_delta_set 在 delta 家族下必须非空且 sufficient_alone 为 true；structural-delta-strong 另需至少两种不同的 novel_consequence_kinds 且含 experiment 或 boundary |
| `NN10` | theory_stripping 必须按 operator 触发；结论为 theory-relabeling-risk 时 near_neighbor_verdict 只允许 reframing-neighbor / duplicate-equivalent / uncertain |
| `NN11` | remote_analogy_mapping 必须按 operator 触发；added_structure 为 false 时结论不得是 structural-novelty |
| `NN12` | near_neighbor_verdict 必须与 verdict 相容，且 claimed_novelty_level 不得超过其上限 |
| `NN13` | 禁止任何 scalar 决定 novelty；retrieval_heuristic 的 use 必须逐字为 retrieval-clustering-only |
| `NN14` | counterfactual_collapse.verification_status 必须存在且属于四值；collapse_result 为 does-not-collapse 时至少为 derived |

> **脚本不得决定「`H` 与 `P` 是否真的结构等价」。** LLM proposes correspondences；
> evidence and constrained tests 决定这些对应关系可以被信任到什么程度。

---

## 31. Near-Neighbor metamorphic 套件（NN-1—NN-12）

构造**人工已知关系**的 pair。期望值是 verdict，不是分数。

| # | 变体 | 期望 `near_neighbor_verdict` |
|---|---|---|
| NN-1 | Rename（完全同方法，只改名称） | `duplicate-equivalent` |
| NN-2 | Narrative rewrite（同结构重新讲故事） | `reframing-neighbor` |
| NN-3 | Theory relabel（同算法、同 prediction，换 theory） | `reframing-neighbor` |
| NN-4 | Cross-domain port（结构不变，应用领域不同） | `transfer-neighbor` |
| NN-5 | New regularizer（同 formulation / mechanism，只加 regularizer） | `component-neighbor` |
| NN-6 | New parameterization（表示不同，target / mechanism 不变） | 局部 neighbor，除非 consequence 改变 |
| NN-7 | Mechanism change（information flow 真改变） | `mechanism-neighbor` 或 structural delta，取决于 consequences |
| NN-8 | Assumption removal（删承重假设并改变 solution space） | `structural-delta` |
| NN-9 | Observable change（可用信息变化） | `structural-delta` |
| NN-10 | New impossibility boundary（发现旧 formulation 未知的 failure regime） | `structural-delta-strong` |
| NN-11 | Semantic far / structural same（名词与领域完全不同，抽象结构相同） | near-neighbor |
| NN-12 | Semantic close / structural different（术语很像，assumption / observable / prediction 真变化） | `structural-delta` |

> **NN-11 与 NN-12 是最重要的两条。** 它们直接测「语义距离 ≠ 科学距离」。

---

## 32. 幻觉回归测试

四条必测，全部落测试代码（AGENTS.md Rule 8）。

| 构造 | 期望 |
|---|---|
| Extraction hallucination（prior 原文没有该 assumption） | 不能标 `EXPLICIT` |
| Alignment hallucination（两个 object 名称类似但 relations 不同） | 不得 `MATCH` |
| Missing prior（检索为空） | `uncertain` / `retrieval-insufficient`，**不是** `paradigm-candidate` |
| Counterfactual hallucination（声称 replacement 会改 prediction，但无 equation / code / experiment 支持） | collapse test = `unresolved` |

---

## 33. 完成判据（12 问）

系统面对一个 candidate，**必须**能回答：

1. 它最近的 structural priors 是谁？
2. candidate 与 prior 哪些承重结构保持不变？
3. 哪些差异只是 wording / theory / domain？
4. minimal structural delta 是什么？
5. delta 是否 load-bearing？
6. delta 删除后是否回到 prior？
7. delta 替换成 prior 后是否 collapse？
8. 哪个 prediction / boundary / experiment 因 delta 改变？
9. 关键 mapping 的证据来源是什么？
10. 哪些 mapping 仍然 unresolved？
11. 当前最多 defensible 的 novelty claim 是什么？
12. candidate 是 local neighbor / transfer neighbor / reframing neighbor / structural delta / uncertain？

---

## 34. 最高层原则（四句冻结）

> **Semantic distance is not scientific distance.**

> **A candidate is near-neighbor when its load-bearing scientific structure is preserved,
> even if its language, domain, theory framing or implementation looks different.**

> **A candidate escapes the local neighborhood only when a load-bearing structural change
> produces a different scientific consequence.**

> **The system must preserve divergence during generation, and audit whether that divergence
> is real only after generation.**

最终目标**不是**「把所有近邻 idea 杀掉」，而是：

```text
Generate broadly → Preserve diversity → Find strongest prior mapping
→ Measure residual structural delta → Constrain novelty claim
```

---

## 35. 维护规则

1. **本文件的枚举是权威。** `verdict` 十值、`near_neighbor_verdict` 八值、
   `claimed_novelty_level` 七值、十四个 facet、十一个 relation、`collapse_result` 三值、
   `relation` 三值、`provenance` 四值、`local modification` 十一类、
   `novel_consequence_kinds` 五值、`new_structure_kinds` 六值、`trust_basis` 八值、
   `counterfactual_collapse.verification_status` 四值
   一旦改动，**必须**同轮扫四处：
   `scripts/structural_equivalence_check.py`（规则实现）、
   `templates/structural-equivalence-audit.template.json`（骨架）、
   `examples/structural-equivalence/`（fixture）、
   以及引用本文件的 `phase-*.md`（读写时机）。
2. **`EQ1`—`EQ13` 与 `NN1`—`NN14` 的判据文本**同时存在于本文件 §12.1 / §30 与检查器常量中。
   两处**逐字相同**，由 `test_structural_equivalence.py` 机械比对；改一处必须同轮改另一处。
3. **新增 `assurance[]` 可选字段**时，**必须**同轮改：
   §9.2 表 + `templates/research-state.template.json` + 检查器。
4. **引用本文件时**必须写 `structural-equivalence-policy.md §N`，**不得**只写「见等价政策」。
5. **不得**为了通过闸门而放宽本文件的判据或删除 fixture。
6. **不得**把 near-neighbor verdict 实现成淘汰开关（§26）。
7. **不得**给 `state_check.py` 加 near-neighbor 语义规则 —— 归属仍是本服务自己的检查器。
8. 已知缺口一律记为测试里的 `skipTest` 并写明理由，**不得**只在散文里承认
   （AGENTS.md Rule 8）。
