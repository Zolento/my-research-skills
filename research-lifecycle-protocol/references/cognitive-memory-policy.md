# Cognitive Memory Policy — persistent scientific understanding across sessions

Research State records what we believe about the world. It does not record how our
**understanding of a mechanism changed**, which of two mechanisms is still viable,
or what a new session must recover before it can reason. This policy defines that
missing layer.

## 0. Placement and authority

This is an internal capability, not a sixteenth R stage and not a ninth first-class
object. It is a **cognitive projection** over data that already exists.

```
Canonical   .research-lifecycle-protocol/routes/<R>/research-state.json        ← sole authority
            + experiments[].preregistration + raw evidence
Event       .research-lifecycle-protocol/routes/<R>/cognition/model-revisions.jsonl
            structural assertions + canonical pointers                    ← append-only, no epistemics
Derived     .research-lifecycle-protocol/routes/<R>/cognition/index.json
            .research-lifecycle-protocol/routes/<R>/cognition/context-brief.md ← rebuildable, never authority
```

The `cognition/` directory sits inside the route control plane, beside
`populations/` and `assurance/`. It follows the control-plane contract in
[project-layout.md](project-layout.md) §11.2: clear schema, stable ids, mutation safety,
validator friendliness, append-only provenance. It is not a human document and is not
placed under `routes/<R>/docs/`.

**No new state slot is introduced.** S1—S7 and V1—V24 are unchanged, the state template is
unchanged, and `scripts/state_check.py` is unchanged. The layer is enforced by
`scripts/cognition.py` under its own rule namespace `CM1`—`CM10`, which never collides with
`S`/`V` rule numbers or with the `C`/`E`/`AS`/`H`/`X`/`LIT`/`F`/`U` id prefixes.

## 1. Four cognitive memory classes

| Class | Answers | Derived from | Never duplicates |
|---|---|---|---|
| **Mechanistic** | Which mechanisms do we hold, with what conditions, boundaries, invariants, counterexamples and pending predictions? | `hypotheses[]`, `assumptions[]`, `claims[]`, `evidence[]`, `literature[]` | `claims[]` (a mechanism is not a claim and cannot set a claim status) |
| **Anomaly** | Where did a frozen prediction and the observation disagree, and is it reproduced? | `experiments[].unexpected`, `experiments[].preregistration.outcomes`, `evidence[].diagnostic_observation` | `uncertainties[]` (an anomaly is an observation gap, not a question) |
| **Mechanism competition** | Which mechanisms explain the same facts and what distinguishes them? | `claims[].nearest_alternative`, `claims[].contract.minimal_discriminating_experiment`, `assurance[]` | `assurance[]` (an attack is adversarial review; a competition is a live scientific rivalry) |
| **Scientific value** | What did a finding change, and what did we learn about our own search? | `contract`, `uncertainties[].importance`, `repairs[]`, `scheduler.json` | `scheduler.json` `operator_stats` (telemetry stays telemetry) |

**Hard boundary rules.**

1. Evidence authority stays with `evidence[]`. Cognitive memory never creates evidence and
   never assigns a `verification_tier`.
2. Failure authority stays with `failures[]`. Cognitive memory never invents a failure and
   never clears a stop rule.
3. Scheduler meta-memory stays in `scheduler.json`. Cognitive memory reads
   `operator_stats` and `eig_calibration`; it does not write them and never cites them as
   evidence ([scheduler-policy.md](scheduler-policy.md) §6).
4. A cognitive entry that restates a canonical object without adding structure, boundary or
   prediction is a duplicate, not progress (rule `CM9`).

## 2. Rule table `CM1`—`CM10`

| Rule | Check | Severity |
|---|---|---|
| **CM0** | A cognitive build/check must not modify `research-state.json` (byte comparison) | hard |
| **CM1** | Revision log shape: parseable JSONL, `_schema`, unique `id`, strictly increasing positive `seq`, non-empty `summary`, `kind` in the frozen enum, `actor` in the allowed list, known structural fields only | hard |
| **CM2** | Forbidden assertion: a revision may not declare `epistemic_status`, support level, claim status, `contract`, `anchor`, `research_goal`, `primary_anchor`, `out_of_scope` or `validity` | hard |
| **CM3** | Provenance: `trigger` present, `refs` non-empty, every reference exists, no reference to a future `state_version`, no reference to a `stale`/`invalid`/`pending` object; the derived index must match a fresh rebuild of canonical state plus the log | hard |
| **CM4** | `mechanism_create` must state the mechanism | hard |
| **CM5** | `anomaly_record` must state the observation | hard |
| **CM6** | A competition needs at least two registered mechanisms and, on closure, a conclusion | hard |
| **CM7** | A self-declared support level is recorded as a conflict and is never adopted | warning |
| **CM8** | An open competition without conflicting predictions plus a discriminating intervention is reported as lacking distinguishing power | warning |
| **CM9** | Two mechanisms with an identical canonical anchor set are reported as substantively equivalent explanations | warning |
| **CM10** | A competition cannot be decided because a frozen outcome has no machine-decidable `criterion`; a legacy state stays readable, compares as `UNTESTABLE` and receives no retrospective verdict | warning |

`CM7`—`CM10` are warnings: they do not block a build, and **they do not flip an exit code**.
They must appear in the context brief's provenance section, and `check`/`validate` print them
with an `[advisory]` marker and count them separately. `CM0`—`CM6` block:
`scripts/cognition.py check` exits 3.

The severity column is the contract. A consumer that treats *every* diagnostic as a violation
will refuse legitimate legacy projects: an index written by a takeover of a pre-`criterion`
project always carries `CM10`, so escalating it to a blocking finding makes the takeover refuse
its own output. `scripts/cognition.py` exposes the table as `WARNING_RULES`, and every consumer
(index validation, `LH12`, exit codes) reads it from there instead of re-deciding.

## 3. Derived support ladder (the anti self-certification core)

A mechanism's support level is a **function of canonical facts**, computed by
`cognition.derive_support`. A revision event may name structure and must cite canonical ids;
it may not name its own support. The ladder, weakest first:

| Level | Derived when |
|---|---|
| `speculative` | the mechanism carries no canonical reference at all |
| `hypothesis` | it is anchored to candidates (`hypotheses[]`) or explicit assumptions (`assumptions[]`) only — a proposed explanation |
| `literature_supported` | a referenced `evidence[]` of `kind: literature` reaches `T1`, or an `epistemic_status: Supported` evidence reaches `T1`, or a referenced `literature[]` relation is `supports` / `uses-same-theory` |
| `experiment_supported` | a referenced `evidence[]` is `kind: experiment`, `strength: strong`, `verification_tier >= T2`, `epistemic_status` in `Observed`/`Supported`, valid, and supports a claim whose status is `supported` or `partially-supported` |
| `refuted` | a referenced claim is `contradicted`/`killed`; or a referenced valid `evidence[]` with a non-empty `contradicts` reaches `T2`; or a referenced `failures[].kind` is `falsified` / `failed-to-reproduce`; or a `repairs[].disposition: KILL_BRANCH` covers a referenced candidate |

Refutation outranks every positive signal. An invalid or stale source contributes nothing
and marks the entry stale.

**The four epistemic distinctions the system must preserve** map onto this ladder exactly:
a model-proposed explanation is `hypothesis`, a literature-backed assumption is
`literature_supported`, an experiment-backed mechanism is `experiment_supported`, and a
mechanism killed by a discriminating experiment is `refuted`. No agent self-rating can move
an entry between these levels, and `CM7` reports any attempt to do so.

This ladder **does not replace** claim status or `verification_tier`
([evidence-policy.md](evidence-policy.md), [research-state-policy.md](research-state-policy.md) §3.2). It is a
summary of them, recomputed on every build.

## 4. Support level versus lifecycle status

Two axes, never merged:

* **Support level** is evidence-derived and can only move through canonical change.
* **Lifecycle status** — `active` / `weakened` / `refuted` / `dormant` / `merged` — records
  a *research decision* plus evidence. `refuted` is evidence-driven. `dormant` (deliberately
  set aside) and `merged` (folded into another mechanism) must be recorded explicitly in a
  revision event, because they are decisions, not measurements. `weakened` follows a lost
  competition, an explicit `mechanism_weaken` revision, or evidence-driven narrowing.

## 5. Memory lifecycle

```
Recall → Reason → Test → Revise → Consolidate → Recall
```

| Step | Where it happens | What it produces |
|---|---|---|
| Recall | session start, before any R stage | `cognition/context-brief.md` |
| Reason | R3—R6 | new mechanism structure, competitions, pending predictions |
| Test | R8—R9 | frozen preregistration; observation |
| Revise | R9.O / R10 / R11 | `mechanism_revise`, `mechanism_refute`, `mechanism_reactivate`, `anomaly_record` |
| Consolidate | after the state transaction | `scripts/cognition.py build` regenerates `index.json` and `context-brief.md` |

**Session start must recover, in this order:** the research contract and goal; still-valid key
mechanisms; important unexplained anomalies; refuted mechanisms with their boundaries;
unfinished mechanism competitions; the previous round's decisions and unfinished obligations.

**Never inject the whole history.** Loading is tiered:

| Tier | Content | Selection |
|---|---|---|
| **Hot** | mechanisms anchored to the current focus, high-importance non-stale anomalies, open competitions, failure constraints, the last decision | refs intersect the focus set |
| **Warm** | refuted and weakened mechanisms, related history | not hot, but carries a support reason |
| **Cold** | everything else, plus all stale entries | ids and stale reasons only |

The **focus set** is derived from canonical state: open `critical`/`high` uncertainties and
their cheapest discriminating test, live supported claims, `planned`/`running` experiments,
live candidates, and `ACCEPTED_LIMITATION` repair targets.

Beyond tiering the recall applies: **relevance filtering**, **invalidation filtering** (a stale
or unresolved entry never enters hot memory), **deduplication** by canonical anchor set
(`CM9`), **source citation** on every line, **version checking** (index digests are compared
against the current state and log), and a **context budget** (`--budget`, default 6000
characters) with an explicit truncation marker.

## 6. Belief revision

**Allowed cognitive changes** — all of them recorded as revision events with a trigger and
canonical references: create a mechanism; revise a necessary condition; narrow a boundary;
add a counterexample; mark evidence-driven weakening; record refutation; reactivate after new
evidence; merge mechanisms; open, resolve or declare undecidable a competition.

**Forbidden** — rule `CM2`, without exception:

* raising a mechanism's support level;
* changing `claims[].status`;
* changing `contract`, the research anchor, or `out_of_scope`;
* editing `validity` of any canonical object;
* writing `evidence[]` or `failures[]`.

`claims[].status` moves only through R8's single-direction upgrade or R10
([research-state-policy.md](research-state-policy.md) §5.0). A cognitive revision that cites ≥ T2 refuting
evidence is a **hand-off to R10**, not a status change.

**Unrecoverable history is marked, not reconstructed.** If the referenced objects cannot
restore a judgement — a missing id, a stale source, a `since_state_version` ahead of the
current state — the entry is marked `stale` with reasons and dropped from hot memory.
The layer never fills the gap with plausible text.

## 7. Anomaly handling

An anomaly is recorded only from a source that names both sides of the disagreement.

| Situation | Legal recording |
|---|---|
| A frozen prediction exists and the observation differs | `anomaly_record` citing `experiments[]` (the freeze) and `evidence[]` (the observation) |
| The observation was not preregistered | the observation must first be registered as `evidence[]` with `diagnostic_observation`; the anomaly is then marked **exploratory** and may not be described as a prediction success or failure |
| The experiment implementation or measurement is invalid | **not an anomaly** — it is an R9.O `INVALID_EXPERIMENT` plus a `failures[]` entry |

Quantitative comparison and interval scoring are the prediction comparator's job; this
policy only fixes where the anomaly record lives and what may be claimed from it.

## 8. Read / write protocol per stage

| Stage | Reads cognition | Writes cognition |
|---|---|---|
| R0 | — | — (the anchor is human-owned) |
| R1 | brief | — |
| R2 / R5 | retrieval cues from the brief | — |
| R3—R6 | strategy priors, existing mechanisms, `CM9` duplicates | `mechanism_*`, `competition_*` |
| R7 | mechanisms and competitions under attack | — |
| R8 | pending predictions, competitions | `prediction_freeze`（`after` 记录 `freeze_digest`、`outcomes`、`outcome_mode`、`branch_rule`）|
| R9 | failure constraints, pending predictions | — |
| R9.O | frozen predictions | `anomaly_record`, `prediction_assessment` |
| R10 | refuted mechanisms | `mechanism_refute`, `mechanism_weaken`, `mechanism_reactivate` |
| R11 | — | `mechanism_merge`, `mechanism_revise`; then rebuild |
| R12 / R13 | read-only view | — (narrative and review are state views) |
| R14 | brief, strategy priors | — |

## 9. Commands

```sh
python3 scripts/cognition.py build    --state .research-lifecycle-protocol/routes/A/research-state.json
python3 scripts/cognition.py check    --state .research-lifecycle-protocol/routes/A/research-state.json
python3 scripts/cognition.py brief    --state .research-lifecycle-protocol/routes/A/research-state.json --budget 4000
python3 scripts/cognition.py recall   --state .research-lifecycle-protocol/routes/A/research-state.json
python3 scripts/cognition.py --selftest
```

Exit codes follow the repository convention: `0` pass, `1` argument error, `3` hard
violation, `4` environment not satisfied.

## 10. Self-check

- [ ] The build wrote nothing to `research-state.json` (`CM0`).
- [ ] The index rebuilds to identical bytes from canonical state plus the revision log.
- [ ] Every mechanism line in the brief carries a derived support level and a lifecycle status.
- [ ] No stale or unresolved entry appears in hot memory.
- [ ] No revision event declares its own support, a claim status or an anchor change.
- [ ] Failure memory with its stop rules and retry conditions is present in the brief.
- [ ] The brief is inside the context budget and its truncation is explicit.
- [ ] `scripts/state_check.py --check <state>` still exits 0 with the same violations as before.

## 认知记忆的 L0 表述

> 以下内容自 v2.2.0 起从 `SKILL.md` 的 L0 常驻核心迁出，本节为该规则的**权威落点**。
> L0 只保留可判定的短约束与本节指针。来源：`SKILL.md` §1.8。

> **记录事实 ≠ 积累理解。** Research State 回答「我们目前认为世界是什么样」；
> 认知记忆回答「我们持有哪些机制、它们如何被证据改写、下一位执行者必须先恢复什么」。
**定位：** 它是**已有系统的认知增强层**，不是第 16 个阶段，不是第九类一等对象，
也不是第二份事实来源。权威定义见
[cognitive-memory-policy.md](../references/cognitive-memory-policy.md)。
**三层，一个方向：**
```text
Canonical  .research-lifecycle-protocol/routes/<R>/research-state.json   ← 唯一权威
结构断言 + canonical 指针，append-only                  ← 不承载支持度
可由前两层重建                                         ← 永不是权威
```
**四条硬边界（违反即与 §1.6 / §1.7 冲突）：**
1. **支持度是算出来的，不是声明的。** 机制的支持等级由 canonical 事实推出
（`speculative` / `hypothesis` / `literature_supported` / `experiment_supported` /
`refuted`）。修订事件**不得**声明 `epistemic_status`、支持等级或 Claim 状态（`CM2`）；
自评只被记成冲突（`CM7`），不被采用。
2. **认知记忆不写 canonical。** 它不写 `claims[].status`、不写 `contract`、不写锚点、
不写 `evidence[]` / `failures[]`。构建前后对 `research-state.json` 做字节比对（`CM0`）。
3. **失效即过期。** 引用的证据或对象 `validity` 变成 `stale` / `invalid` / `pending` 时，
派生条目自动标记过期、退出 hot memory，并保留原因；不补写推测。
4. **记忆不等于事实。** 每条机制必须带支持等级、适用范围与来源引用。Context Brief
不得把推测写成结论。
**记忆生命周期：** `Recall → Reason → Test → Revise → Consolidate → Recall`。
每次启动先恢复：研究契约与目标 / 仍有效的机制 / 未解释异常 / 被否证机制及其边界 /
未完成的机制竞争 / 上一轮决策与未完成操作。**三级加载，不得无差别注入全部历史：**
| 层 | 内容 | 选择依据 |
|---|---|---|
| **Hot** | 与当前焦点挂钩的机制、高重要度未复现异常、开放竞争、失败约束、上一轮决策 | 引用与焦点集相交 |
| **Warm** | 被否证 / 被削弱的机制与相关历史 | 非 hot，但有支持理由 |
| **Cold** | 其余一切，含全部过期条目 | 只给 id 与过期原因 |
焦点集取自 canonical：`open` 且 `importance ∈ {critical, high}` 的 `U` 及其判别测试、
存活的 `C`、`planned` / `running` 的 `X`、存活候选、`ACCEPTED_LIMITATION` 的 `repairs[].targets`。
另有去重（同一 canonical 锚点集合 = 实质等价解释，`CM9`）、来源引用、版本检查和
上下文预算（`--budget`，默认 6000 字符，截断必须显式标注）。
**读写协议（逐阶段）：** R3—R6 写 `mechanism_*` / `competition_*` 并读策略先验；
R8 写 `prediction_freeze`；R9.O 写 `anomaly_record` / `prediction_assessment`；
R10 写 `mechanism_refute` / `mechanism_weaken` / `mechanism_reactivate`；
R11 写 `mechanism_merge` / `mechanism_revise` 后重建；R12 / R13 **只读**（叙事与审阅是
state 的视图）；R14 只读 Context Brief。详见该政策 §8。
**机械闸门 `CM1`—`CM10`**（与 `S`/`V` 命名空间分离，`C` 不与 Claim 前缀冲突）：
```sh
python3 scripts/cognition.py build --state .research-lifecycle-protocol/routes/<R>/research-state.json
python3 scripts/cognition.py check --state .research-lifecycle-protocol/routes/<R>/research-state.json
python3 scripts/cognition.py brief --state .research-lifecycle-protocol/routes/<R>/research-state.json --budget 4000
```
退出码同仓库约定：`0` 通过 / `1` 参数错误 / `3` 硬违规 / `4` 环境不满足。
**不新增 state 槽位**：S1—S7 / V1—V24、state 模板与 `state_check.py` 一律不变。
**预测必须可判定（Phase 2）。** `preregistration.outcomes[].criterion` 把「什么算预测成立」
在冻结时写成机器可读判据（`quantitative` / `directional` / `discrete`）。
没有判据的结果只能返回 `UNTESTABLE`，**不得宣告预测成立或失败**；
执行无效只能返回 `INVALID_EXECUTION`，不是异常；没有预注册的观察只能是
`EXPLORATORY_ANOMALY`。
**冻结的 `outcomes[]` 是完整判定集合**：观测包是「关于它」的证据，不是「要判定哪些结果」的
清单。只提交一部分只能得到 `PARTIALLY_ASSESSED`，**永远不能读成「全部预测成立」**；
`execution.validity=UNKNOWN` 时比较结果保留在 `diagnostic_outcome_class`，
但**不占据科学判定栏**、不是合格证据，也不得触发 R10/R11 状态迁移
（`evidence_transition_allowed`）。
**互斥分支必须由预注册打开，不能由观测包声明。** 只有在冻结时写入
`outcome_mode: "branch"` + `branch_rule`（`selector` / `quantity` / `branches` 完整划分），
且分支判据**可证互斥**时，比较器才进入 branch mode；所选分支由冻结规则作用于**原始观测**
导出，packet 里的 `observed_outcome` 只是必须与之一致的声明。未声明 mode 的预注册一律按
completeness 判定（旧项目无需迁移）；分支规则缺失、冲突、不可验证或事后追加时，
**不得产生 `PREDICTION_HELD`**，未选分支也要以可核验的排除条件记录（`PC10`）。
**证据资格只有一个入口。** `qualify_evidence` 的 `PQ1`—`PQ8` 同时检查执行有效性、
预注册冻结与判据形状、判定集合完整性或合法 branch mode、**观测包 schema 与结构校验
（`PQ4` 直接消费观测校验器的完整结论：schema 错误 / 缺字段 / 类型非法 / 来源缺失 /
摘要不符一律 fail closed）**、分支选择的可追溯性、实验与预测绑定、终态收据、时间顺序与
事后篡改（含不可核验的冻结 `PC5`）。**任何一项不过就 fail closed**
（`evidence_eligible: false`）：不得标记 `QUALIFIED_EVIDENCE`、不得授权 Claim 状态升级、
不得用于机制否证或 Insight 认证；诊断性比较照常保留。Insight 只有绑定到**具体预测**（evidence 必须带 `prediction_ref`，
或该实验只冻结了一个结果）、具有合格判定、方向一致的证据、**范围覆盖**（字符串 scope 规范化
精确相等；结构化 `scope_region` 按约束子集判定，禁止子串包含与外推）与**已通过**的结构等价
审计时才能成为 `evidence_supported_insight`（`PC11`）。
机制竞争必须逐对检验**可比性 → 冲突 → 分辨率 → 预先声明的判别规则**：
不同观测变量、不同测量口径、区间重叠、`noise/√n` 吃掉间隔、间隔小于 `min_separation`、
没有 `discrimination_rule`，**都不能算可区分**。判别干预必须可执行（`planned` / `running`）。
只有 `DISTINGUISHABLE` / `CONDITIONALLY_DISTINGUISHABLE` / `NOT_DISTINGUISHABLE` /
`INSUFFICIENT_INFORMATION` 四值，且**不接受文本相似度或 LLM 自评分**。行为切换与
Insight Card 规则见
[prediction-anomaly-competition.md](../references/prediction-anomaly-competition.md)。
**科学价值不等于 EIG（Phase 3）。** 研究候选的**决策价值**与**发现潜力**分开判断，
每个维度都带 canonical 依据与不确定性，**没有总分**（`SV1` 拒绝任何聚合分数）。
科学品味分成**用户所有**（`contract`，agent 只读）与**证据校准**（从真实结果归纳，
可修订）两部分；自动学习**只影响探索建议**，不得改锚点（`SV3`）。
探索策略复用既有 `P1`—`P6` / `local` 与 QD archive：算子只能 `encouraged` /
`neutral` / `discouraged` / `dormant`，**没有永久封禁**，降级必须有范围与重启条件，
且至少两次独立失败（`SV5`）。规则见
[scientific-value-adaptive-discovery.md](../references/scientific-value-adaptive-discovery.md)。
---
