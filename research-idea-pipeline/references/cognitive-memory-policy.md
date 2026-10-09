# Cognitive Memory Policy — persistent scientific understanding across sessions

Research State records what we believe about the world. It does not record how our
**understanding of a mechanism changed**, which of two mechanisms is still viable,
or what a new session must recover before it can reason. This policy defines that
missing layer.

## 0. Placement and authority

This is an internal capability, not a sixteenth R stage and not a ninth first-class
object. It is a **cognitive projection** over data that already exists.

```
Canonical   .research-idea-pipeline/routes/<R>/research-state.json        ← sole authority
            + experiments[].preregistration + raw evidence
Event       .research-idea-pipeline/routes/<R>/cognition/model-revisions.jsonl
            structural assertions + canonical pointers                    ← append-only, no epistemics
Derived     .research-idea-pipeline/routes/<R>/cognition/index.json
            .research-idea-pipeline/routes/<R>/cognition/context-brief.md ← rebuildable, never authority
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
python3 scripts/cognition.py build    --state .research-idea-pipeline/routes/A/research-state.json
python3 scripts/cognition.py check    --state .research-idea-pipeline/routes/A/research-state.json
python3 scripts/cognition.py brief    --state .research-idea-pipeline/routes/A/research-state.json --budget 4000
python3 scripts/cognition.py recall   --state .research-idea-pipeline/routes/A/research-state.json
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
