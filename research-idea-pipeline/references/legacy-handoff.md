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
| **LH12** | A pre-existing `cognition/index.json` still matches a fresh rebuild | blocking |
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
