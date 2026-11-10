# Legacy Research Handoff — taking over a project that already ran

A project with a canonical `research-state.json` is **initialized**. Loading a newer skill
must not look like a fresh start: the state version, claim statuses, evidence, experiment
ids, anchor, diagnostic budget and historical decisions are all already there, and none of
them may be reset.

This document defines the takeover. The entry stays `continue-research`; **no fifth entry
is added**. See [invocation-prompts.md](invocation-prompts.md) §2.

## 0. Detection first

```sh
python3 scripts/legacy_handoff.py detect --state <route>/research-state.json
python3 scripts/legacy_handoff.py guard-bootstrap --state <route>/research-state.json
```

`detect` reports `initialized` and `bootstrap_forbidden`. `guard-bootstrap` exits 3 when a
canonical state exists, so a fresh `B0`—`B6` sequence cannot start by accident. Bootstrap is
for projects with **no** state; this is not one of them.

## 1. Read-only compatibility audit

`take` refuses to write anything until every check below passes or is a warning.

| Rule | Check | Severity |
|---|---|---|
| **LH1** | The canonical state passes S1—S7 and V1—V24 | blocking |
| **LH2** | Exactly one canonical state per route (DI-3) | blocking |
| **LH3** | `state_version` is not below any version recorded under `history/` | blocking |
| **LH4** | `scheduler.json`, when present, parses and its `state_version` matches the state | blocking |
| **LH5** | The research contract records a goal and a primary anchor | warning |
| **LH6** | Every terminal experiment records a result and a code revision | warning |
| **LH7** | No terminal experiment lacks a preregistration | blocking |
| **LH8** | `running` and `failed` experiments are reported and preserved | info |
| **LH9** | Failures carry `negative_knowledge` or `stop_rules` | warning |
| **LH10** | `ACCEPTED_LIMITATION` repairs are recovered as boundaries | info |
| **LH11** | An existing `.execution` ledger means budget is already spent | info |
| **LH12** | A pre-existing `cognition/index.json` still matches a fresh rebuild. *Drift* only: a `warning`-severity CM diagnostic describes the canonical state, is reported as a warning, and never refuses the takeover | blocking |
| **LH13** | No prediction was frozen after its result existed | blocking |
| **LH14** | The route keeps `README.md`, `STATUS.md` and `INDEX.md` | warning |
| **LH15** | Existing code or route configuration is discovered | info |
| **LH16** | The revision log, when present, is parseable | blocking |

**Severe errors block the write.** On any blocking finding `take` writes **nothing** — no
index, no brief, no report — prints the findings and exits 3. The answer is never "build a
new Research State and start again": that would discard the evidence, failure memory and
stop rules the project paid for. Fix the canonical artifact with the authority that owns it
(R10 for claim truth, R11 for the state transaction, the owning stage for provenance), then
take over again.

Three of these deserve a note.

* **LH7 — no retrospective preregistration.** A terminal experiment without a frozen
  preregistration is a blocking compatibility error, because the pipeline's V21 requires
  one. The handoff must **not** invent a frozen prediction to make the state valid. The
  result stays unexplained until a stage with the right authority records what happened.
* **LH12 — a corrupt derived layer is not overwritten.** If a stored index does not match a
  rebuild, silently replacing it could change a scientific conclusion. The handoff stops and
  reports the drift.
  **Drift is not the same thing as a warning.** A `warning`-severity CM diagnostic (say `CM10`:
  a legacy competition whose frozen outcomes have no criterion) describes the *canonical state*
  and is reported as a warning; the index still matches. Escalating it would be self-defeating:
  a takeover of a pre-`criterion` project **writes an index that carries that diagnostic**, so
  the next takeover would refuse the healthy project because of the previous takeover's own
  output — and `take` would stop being idempotent.
* **LH13 — prediction time leakage.** A preregistration frozen at or after the result is not
  a prediction. `frozen_at_state_version <= result_at_state_version` is legal for both
  `done` and `failed`; anything later is a leak, and the result may not be presented as a
  test of that prediction.

## 2. What is rebuilt, and how

The cognitive layer is reconstructed from canonical evidence — the same projection the rest
of the engine uses, with no revision log required:

| Recovered | Derived from |
|---|---|
| Mechanisms | one per `claims[]` entry with its evidence and critical assumptions; one per `hypotheses[]` entry |
| Competing mechanisms | `claims[].nearest_alternative`, but **only** when the claim also has an evidence contract naming a real discriminating experiment |
| Competitions | that contract plus the frozen outcome references of its experiment |
| Anomalies | `experiments[].unexpected` and `failed` experiments |
| Boundaries | `failures[]` stop rules, `negative_knowledge`, `REPEAT_BLOCKING` failure kinds, `NARROW_SCOPE` / `KILL_BRANCH` repairs, and objects whose `validity` is `invalid` or `stale` |

Every reconstructed entry carries:

```json
"provenance": {"origin": "legacy_derivation", "retrospective": true,
               "derived_from": ["claims:C1"], "missing": []}
```

and appears in the brief with a `[RETROSPECTIVE]` tag. `index.json` reports
`provenance_mode: legacy_derivation` (or `mixed` once revisions exist).

**Support levels are still computed, never declared.** A reconstructed mechanism anchored to
a strong `T2` experiment that supports a claim is `experiment_supported`; one anchored only
to a candidate is `hypothesis`; one whose claim is `contradicted`/`killed` is `refuted`.

One deliberate conservatism: `claims[].known_flaws` is a link required by V4, **not** a
recorded refutation. The reconstruction cites those failures for traceability but does not
derive `refuted` from them, because that would be over-reach. A revision event recorded by
an agent *may* assert that link, because then the assertion has an author and a trigger.

**Legacy derivation is suppressed as soon as a revision covers the same object**, so a route
migrates from `legacy_derivation` to `mixed` to `revision_log` without a migration step and
without `CM9` duplicate noise.

## 3. No fabricated history

| Situation | Legal handling |
|---|---|
| A frozen outcome has no machine-decidable criterion | reported as `retrospective`; `prediction_compare` returns `UNTESTABLE` and never a verdict |
| A terminal experiment has no preregistration | blocking (`LH7`); no prediction is created |
| An observation was never preregistered | `exploratory`; it may not be described as a prediction success or failure |
| Contract, failure conditions or route documents are missing | reported as `unknown`; the handoff does not write them |

## 4. Idempotence, traceability and rollback

* **Repeatable.** Given the same state the handoff writes byte-identical files; a second run
  reports `already_initialized: true` and changes nothing.
* **Traceable.** `handoff.json` records the state digest, the audit result, every recovered
  and unrecovered item, and the exact list of files written.
* **Rollback.** `rollback` removes exactly the files the handoff created and refuses if any
  unknown file is present, if the record belongs to another route, or if a path would escape
  the cognition directory. It never touches the canonical state.

```sh
python3 scripts/legacy_handoff.py rollback --state <route>/research-state.json
```

## 5. The takeover report

`cognition/handoff-report.md` contains: recovered information; information that could **not**
be recovered, marked `unknown` or `retrospective`; important mechanisms; unresolved
anomalies; directions forbidden to repeat; in-flight experiments with `must_not_rerun` and
`must_not_auto_close`; the next valuable research action; how to continue; and the full
audit finding list. `handoff.json` carries the same content in machine form.

## 6. Continuing afterwards

The route now behaves like any other: `continue-research` reads
`cognition/context-brief.md` from the default location, no manual memory path is needed, and
each round ends with

```sh
python3 scripts/cognition.py build --state <route>/research-state.json
python3 scripts/cognition.py check --state <route>/research-state.json   # exit 0
```

Rolling back the derived layer at any time loses no authoritative information, because the
layer is a projection of the state plus the revision log.

## 7. Self-check

- [ ] `guard-bootstrap` refuses on an initialized project and no `B0`—`B6` sequence ran.
- [ ] `research-state.json`, `scheduler.json` and the `.execution` ledger are byte-identical
      after the takeover.
- [ ] No state version, claim status, evidence id, experiment id, anchor or decision changed.
- [ ] Every reconstructed mechanism is marked `retrospective` and cites canonical ids.
- [ ] Unrecovered information is present in the report as `unknown` or `retrospective`.
- [ ] No prediction was invented for an experiment that never froze one.
- [ ] A second takeover is byte-identical; `rollback` restores the pre-takeover tree.
- [ ] A blocking finding produced no write at all, and no replacement state was created.

---

## 何时**不**需要接管（Research Resume）

已有 canonical `research-state.json` 时，日常续研（含 DSH `/loop` 每轮唤醒、`continue-research`、
会话恢复、上下文压缩后重载）**直接** Research Resume：读 state + 认知投影 + Scheduler + 已有方法
产物，继续未完成行动。**不要**为续研运行 `compatibility_audit`、生成接管报告或重建投影。

分类逻辑的唯一实现是 `scripts/legacy_handoff.py:resume_decision`（只读、可解释、四条出口：
Bootstrap / Cold Handoff / Research Resume / Recover-or-HOLD）；本文档不重复定义。
**一次接管完成后**，下一轮即进入 Research Resume，且不得重复生成接管报告。

## 旧项目接管的 L0 表述

> 以下内容自 v2.2.0 起从 `SKILL.md` 的 L0 常驻核心迁出，本节为该规则的**权威落点**。
> L0 只保留可判定的短约束与本节指针。来源：`SKILL.md` §1.9。

> **已有 canonical `research-state.json` ＝ 已初始化项目。** 载入新版 Skill **不是**新项目，
> **不得跑全新 Bootstrap（`B0`—`B6`）**。
入口**仍然是 `continue-research`**（只有四个入口，接管不新增第五个）。
首次接管执行**只读**兼容性审计并重建认知记忆：
```sh
python3 scripts/legacy_handoff.py detect --state .research-idea-pipeline/routes/<R>/research-state.json
python3 scripts/legacy_handoff.py take   --state .research-idea-pipeline/routes/<R>/research-state.json
```
**五条硬约束：**
1. **不重置** `state_version` / `claims[].status` / `evidence` / 实验 ID / 锚点 /
诊断预算 / 历史决策；`research-state.json`、`scheduler.json` 与 `.execution` ledger
在接管前后**逐字节相同**。
2. **不补造历史。** 历史上没有预注册的终态实验是**阻塞级兼容性错误**（`LH7`），
不得事后补一份冻结预测；没有可判定判据的冻结结果标 `retrospective`，
契约 / 失败条件 / 文档缺失标 `unknown`。
3. **可从 canonical 重建认知记忆**：机制 / 异常 / 竞争 / 失效边界全部由 `claims[]` /
`hypotheses[]` / `experiments[]` / `failures[]` 投影得到，每条带
`origin: legacy_derivation` + `retrospective: true`，并在 Context Brief 标
`[RETROSPECTIVE]`。有修订记录覆盖同一对象时，重建条目自动让位。
4. **严重兼容性错误一律不写回**（退出码 3，什么都不写），
**不得通过重建一份新 Research State 绕过问题**。`LH1`—`LH16` 见
[legacy-handoff.md](../references/legacy-handoff.md)。
5. **可重复、可追溯、可回滚。** 同样输入产出逐字节相同的文件；第二次接管只报
`already_initialized`；`rollback` 只删本层创建的文件，遇到未知文件即拒绝。
接管产生 `cognition/handoff-report.md`（已恢复 / 未恢复 / 重要机制 / 未解异常 /
禁止重复方向 / 进行中实验 / 下一条有价值动作）。接管后进入正常 `continue-research`，
默认读取 `cognition/context-brief.md`，**不需要用户指定记忆文件**。
**发现能力必须可验证（Phase 4）。** 历史回放用**当时可见的信息**重放一次研究决策，
再拿系统从未见过的隐藏答案评分：七个维度**各自独立**，**不做加权总分**；
`null` 表示该 case 不可评，不得当作 0。消融四个 arm（baseline / memory_only /
memory_prediction / full_cie）只报实测值与不确定性，**样本不足时明确声明不得宣称提升**；
两个 arm 在所有维度上无法区分时也要写明。novelty **只认独立标签或文献近邻**，
agent 自评被拒绝。回放前必须证明隐藏信息不可达（`RP2`）。
规则见 [discovery-replay.md](../references/discovery-replay.md)。
```sh
python3 scripts/research_replay.py suite --dir examples/replay/adversarial --runs 2
python3 scripts/research_replay.py smoke --work /tmp/cie-smoke
```
---
