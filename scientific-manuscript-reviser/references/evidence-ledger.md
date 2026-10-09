# Claim evidence ledger

The ledger records where each claim's evidence actually lives. It is an optional
artifact separate from the manuscript and separate from the argument graph. It
does not add, remove or reword any claim. `scripts/evidence_ledger.py` validates
provenance and declared states only. It performs no science and certifies no
claim as true.

The four trust boundaries in evidence-grounding.md §1 apply unchanged. The
ledger belongs to the declared-judgment boundary. A PASS says every reference
resolved, every digest matched and every declared state is internally
consistent. It never says the claim is correct.

## Artifact

`claim-evidence-ledger@1` has exactly `schema`, `claims`, `artifacts`,
`evidence` and `missing_context`.

```
python3 scripts/evidence_ledger.py manuscript.md --ledger ledger.json --graph graph.json
```

Each artifact has `id`, `type`, `reference`, `digest`, `origin` and `locator`.

- `type` is one of `evidence_core.ARTIFACT_TYPES`: `experiment_data`, `run_log`,
  `config`, `code`, `figure`, `table`, `proof`, `literature`, `dataset_card`,
  `notebook`, `other`.
- `reference` is a path relative to the skill directory. The resolved path must
  stay inside that directory and must be a real file. A missing file is an
  error, never an unknown state.
- `digest` is `evidence_core.source_digest(path)`, the SHA256 of the file bytes.
  Any mismatch is an error. The ledger binds to exact file content, so an edited
  source invalidates the gate until the digest is refreshed.
- `origin` states how the artifact came to exist, for example a command, a
  capture or a reading note. `locator` states where inside the artifact the
  relevant material sits, for example `lines 12-18`, `field precision`,
  `sheet Results` or `paragraph 2`.

Point at the artifact that carries the actual evidence:

| Claim depends on | Typical artifact | Typical locator |
|---|---|---|
| Measured numbers, tables of results | `experiment_data` | field, row, sheet |
| That a run happened and with what outcome | `run_log` | capture lines, timestamp |
| Hyperparameters, seeds, splits | `config` | key, section |
| A procedure or an implementation | `code` | function, commit, lines |
| A displayed result | `figure` or `table` | panel, column |
| A derivation | `proof` | step, lemma |
| What another publication states | `literature` | paragraph, page, equation |

## Evidence

Each evidence record has `id`, `claim_id`, `artifact_id`, `locator`,
`statement`, `state`, `verification_method`, `headline`, `scope`, and optionally
`conditions` and `note`.

- `claim_id` must name a claim-bearing node in graph.json. The accepted types are
  `audit_coherence.CLAIM_TYPES`. An unknown node is an error.
- `statement` names what the located material says. `scope` names what it
  actually measures, which is often narrower than the claim. A narrow scope is
  the point of the field, not a defect.
- `conditions` lists the circumstances the evidence depends on. `note` records
  anything a reader must know to interpret the record.
- `headline` is true when this record speaks directly to the claim. A claim may
  have many supporting records and at most one headline. A second headline is an
  error.

## States

`state` is one of `verified`, `reported`, `contradicted`, `unknown`.

- `verified`: an independent act established the relation. It needs a real
  `verification_method`, one of `recomputed`, `hash_match`, `test_suite`,
  `independent_replication`, `provenance_audit`, `source_inspection` or
  `unverified`.
- `reported`: the manuscript or a source states it. Reading a paper, a README or
  a note is inspection of a report.
- `contradicted`: located evidence goes against the claim.
- `unknown`: the question was not resolved.

A record with state `verified` and method `unverified` is an error. Method
`unverified` exists so that unresolved material can be recorded honestly instead
of being upgraded.

## Why a text citation is not verification

A `literature` artifact, and every text artifact, can never be `verified`.
`evidence_core.evidence_state_rule` is the single authority for this. Text artifacts
must keep `verification_method` as `unverified`, and their `state` is `reported`,
`contradicted` or `unknown`, never `verified`.

Reading a paper establishes what the paper says. It does not establish the
claim. A citation therefore produces a `reported` record, and a paper that refutes
the claim produces a `contradicted` record without becoming a verification act. A
claim whose only support is `reported` cannot be presented as established. Neither
a citation nor its contradiction may be recorded as a verification act. Verification of a
literature claim requires a separate resolved act: a reproduction, a
recomputation from released data, or an explicitly independent check recorded
with its own artifact.

## Aggregation

`evidence_core.claim_state` aggregates one claim from its records. Missing
records yield `no_evidence`. Contradiction outranks verification: a claim with
any `contradicted` record aggregates to `contradicted` even when a `verified`
headline exists. That situation raises an explicit
`CONTRADICTION_OVERRIDES_VERIFICATION` escalation and cannot pass silently.

A claim that aggregates to `verified` needs at least one headline record whose
state is `verified`. A claim supported only by `reported`, `unknown` or absent
evidence cannot be presented as established, however fluent its wording.

`no_evidence` and `unknown` are different conditions and are reported
separately. `no_evidence` means no record was supplied: this is missing
evidence. `unknown` means records exist but the question stayed unresolved: this
is unresolved science. Both keep the run at NEEDS_REVIEW and both use distinct
output wording. Neither is a failure of the manuscript; both are work that only a
human can close.

`missing_context` is a list of explicit strings naming what the ledger could not
resolve. A non-empty list always keeps the run at NEEDS_REVIEW.

## Claims

Each claim has `id`, `statement`, `location`, `source_span` and
`presented_as_established`.

- `id` must be a claim-bearing node in graph.json.
- `location` and `source_span` locate the manuscript wording that carries the
  claim. They must match the supplied manuscript exactly.
- `presented_as_established` is a declaration, not an inference. A reported
  claim that the manuscript presents as established keeps the run at
  NEEDS_REVIEW. Parsing prose to decide this would cross into automatic
  extraction, which the contract forbids.

Every graph `central_claim_ids` entry should be declared. An undeclared central
claim is an incomplete-coverage item and keeps the run at NEEDS_REVIEW.

## Status

The gate returns one of three statuses.

- `FAIL` (exit 3): any error, including a missing file, a digest mismatch, an
  unknown node, a text artifact carrying verification, a verified claim without a
  verified headline, or more than one headline.
- `NEEDS_REVIEW` (exit 4): no error, but unresolved, unknown, contradicted or
  no-evidence items, a reported claim presented as established, incomplete
  coverage, or non-empty `missing_context`.
- `PASS` (exit 0): no error and no review item.

Unreadable or non-JSON input is reported as `INVALID` and exits 4.

Do not read a PASS as scientific validation. A well-sourced claim can still be an
overclaim, an unidentifiable experiment or a cross-section contradiction. The
ledger does not replace the coherence audit in scientific-coherence.md. Resolving
a high-risk item is human work, and every unresolved item keeps `UNKNOWN` or
`NEEDS_REVIEW`.
