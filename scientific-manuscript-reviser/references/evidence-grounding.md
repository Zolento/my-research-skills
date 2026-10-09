# Evidence grounding contracts

v0.2.0 adds four contracts. They are additive: no v0.1.0 artifact, enum or gate changes,
and Audit, Architect and Revise keep every existing invariant. `scripts/evidence_core.py`
is the single vocabulary authority. All offsets are zero-based Unicode characters with an
exclusive end. All digests use `compare_invariants.digest`.

Four trust boundaries stay separate and must never be summarized as one another:

| Layer | Established by | Never established by |
|---|---|---|
| Structural | `evidence_core` enums, schema, coverage, provenance | any claim about science |
| Mechanical | literal/format preservation in `compare_invariants` and `validate_style` | semantic equivalence |
| Declared judgment | supplied audits and ledger states | automatic extraction from prose |
| Empirical | a separate detection artifact over held-out cases | the harness code itself |

## 1. Evidence Ledger

`claim-evidence-ledger@1` is optional and independent of the manuscript text. It records
where each claim's evidence actually lives. Fields are `schema`, `claims`, `artifacts`,
`evidence`, `missing_context`.

Artifacts have `id`, `type`, `reference`, `digest`, `origin`, `locator`. `reference` is a
repository-relative path that must exist; `digest` is the SHA256 of that file and must
match. A record whose file or digest cannot be resolved is an error, not unknown.

Evidence has `id`, `claim_id`, `artifact_id`, `locator`, `statement`, `state`,
`verification_method`, `headline`, `scope`, optionally `conditions` and `note`.

- `type` is one of `evidence_core.ARTIFACT_TYPES`.
- `state` is `verified`, `reported`, `contradicted` or `unknown`.
- `verification_method` is one of `evidence_core.VERIFICATION_METHODS`.
- `headline` is true when this evidence speaks directly to its claim. A claim may have
  several supporting records and more than one headline is an error.
- `scope` states what the evidence actually measures, which is often narrower than the claim.

Recorded states are genuinely different things. `reported` means the manuscript or a source
states it. `verified` means an independent act established it. `contradicted` means evidence
against it was located. `unknown` means it was not resolved. A `literature` artifact reached
by reading stays `reported` or becomes `contradicted`: source inspection of a paper can
report something or show content that refutes a claim, but it is not verification of a
claim. Text evidence therefore keeps `verification_method` `unverified` in every state and
can never be `verified`. `evidence_core.evidence_state_rule` is the single authority for
which type, state and method combinations are honest, and both the ledger gate and the
release gate call it rather than restating the rule.

A verified assertion always needs at least one `verified` headline record. A claim with only
reported, unknown or absent evidence can never be presented as established, however fluent
its wording. `unknown` differs from `no_evidence`: missing evidence is not unresolved science
and must not read as one. Contradiction outranks verification in aggregation.

The ledger does not replace the coherence audit. A well-sourced claim can still be an
overclaim, an unidentifiable experiment or a cross-section contradiction. Resolving a
high-risk item is human work, and every unresolved item keeps `UNKNOWN` or `NEEDS_REVIEW`.

## 2. Counterfactual Evaluation

`counterfactual-evaluation@1` is a paired case set: `schema`, `cases`, `missing_context`.
Each case has `id`, `class`, `domain`, `correct`, `faulty`, `faulty_defect`, `faulty_span`,
`paraphrase`. `correct` and `faulty` are the two variants. `faulty_defect` names the exact
introduced defect and must be a real substring of `faulty`; `faulty_span` locates it.
`paraphrase` is a wording-only variant whose scientific content is unchanged. Together these
fields define **three** variants, and every case must keep them consistent:

| Variant | Meaning | Required verdict |
|---|---|---|
| `correct` | clean, unreworded | clean |
| `faulty` | a genuine defect present, or the reworded clean text | defective only when the class is a defect class |
| `paraphrase` | the same scientific content as `correct`, different wording | clean |

`class` is a negative class from `evidence_core.FAULTY_CLASSES` or a robustness class from
`ROBUSTNESS_CLASSES`. The negative classes cover causal overreach, conclusion inflation,
invalid controls, missing theoretical assumptions, unidentifiable experiments, evidence
mismatch and cross-section contradiction. A negative case declares a genuine defect, so its
`faulty_defect` is a real substring of `faulty` and `faulty_span` locates it.

The two robustness classes answer two different questions and must not be merged:

- `robustness_paraphrase` has **no defect**. `faulty` is the reworded clean text, so
  `faulty_defect` is empty and `faulty_span` is `{0,0}`. Flagging either `correct` or
  `faulty` is a false positive, which is exactly what this class detects.
- `robustness_defect_rewording` **does contain the genuine defect**, worded differently from
  its negative counterpart, and `paraphrase` is the unreworded clean text. The defect must
  still be located after rewording, so this class is a defect class: it is in
  `evidence_core.DEFECT_CLASSES`, and it is scored with detection recall, not rejection.

A clean-rejection metric and a detection metric therefore have to be reported separately.
Combining them hides which of the two abilities a detector actually has.

`counterfactual-detection@1` is a **separate** artifact recording what a detector actually
did: `schema`, `detector`, `evaluation_digest`, `results`. A detector is named by
`name`, `kind` and `description`; it may be a human reviewer, a rule set or a model, and
its kind never changes how results are read. Each result has `case_id`, `observed`,
`detected_span`, optionally `notes`.

`observed` is `correct`, `miss`, `false_positive` or `uncertain`. Each case in the
evaluation is reported exactly once, so measured accuracy stays meaningful. A `correct`
observation means the genuine defect was flagged in the faulty variant; a `false_positive`
means the clean variant was flagged as faulty; a miss means the defect was not flagged.
A `correct` observation with `detected_span` must actually overlap `faulty_span`, otherwise
the flag did not find the declared defect and is recorded as a miss.

The harness validates structure and reports detection, miss, false-positive and
location-overlap counts **separately**. It never runs a detector, never simulates one and
never fabricates a detection artifact. A clean harness run means the case set and its
reporting are well formed. It is **not** evidence that this skill detects faulty reasoning.
Semantic detection ability remains unvalidated until real, independently produced results
over held-out cases are supplied, and the report says so explicitly.

## 3. Revision Impact Analysis

`revision-impact-analysis@1` maps each edited location to the scientific elements that
depend on it: `schema`, `manuscript_digest`, `edits`, `escalations`, `auto_acceptable`,
`blocked`. Each edit has `id`, `location`, `original_span`, `replacement`, `depth`,
`impacts`, `new_reference_ids`, `loses_limitation`, `introduced_punctuation`,
`required_audits`, `scientific_risk`, `auto_acceptable`, `decision`.

`depth` is `language_layer` or `scientific_content`. `scientific_risk` is `low`, `medium`
or `high`. Each impact has `element_id`, `kind`, `impact`, `rationale`; `kind` is one of
`evidence_core.ELEMENT_KINDS` and `impact` is one of `IMPACTS`.

Language-layer edits take `minimal_sufficient_check` at low risk and `full_semantic_audit`
above it. Scientific-content edits always take `full_semantic_audit`. An edit selecting a
repair whose `requires` is reanalysis, a new experiment or new theory becomes
`scientific_content` even when it looks like wording, and an edit that escalates a reported
or unknown claim to verified becomes `scientific_content` too.

Automatic acceptance is blocked, never negotiated, when the change introduces a scientific
assertion that has no original fact, loses or weakens a limitation, or raises an
unverified inference. `new_reference_ids` and `loses_limitation` therefore have to be
declared rather than inferred: a deterministic tool can locate a dependent element but
cannot decide that two differently worded spans mean the same thing.

The impact analysis does not vote on scientific correctness. It bounds what kind of
verification a change requires and surfaces what a human must resolve.

## 4. Bounded Revision Loop

`bounded-revision-loop@1` is `schema`, `goal`, `problems`, `iterations`, `stop_reason`,
`completion_condition`, `completion_met`, `new_evidence`, `status`, `escalations`.

Each problem has `id`, `statement`, `severity`, `state`, `iterations`, `resolution`.
`state` is `open`, `in_progress`, `resolved`, `blocked` or `withdrawn`. Each iteration has
`id`, `problem_ids`, `target_change`, `completion_criteria`, `scientific_disagreement`,
`result`. `result` is `progress`, `no_change` or `blocked`. `target_change` names the
change this round intends, and `completion_criteria` states how that round is judged done.
A round without both is not a bounded revision round.

A problem stays `resolved` only with a `resolution`; it may not be reopened without new
evidence. The loop does not re-propose a resolved problem or one with no new evidence.

The loop stops on a met completion condition, no substantive progress, a scientific
disagreement the tooling cannot settle, an iteration limit, or an explicit user stop.
`evidence_core.SUCCESSFUL_STOPS` contains the only stop that counts as success. A stop for
no progress, disagreement or a limit with an unmet completion condition ends
`NEEDS_REVIEW`, never PASS. Escalations record an issue the loop could not settle, with
`status` `pending` or `resolved`; a pending escalation keeps human review explicit.

The loop reports whether it made progress. It does not expand its own scope, invent
evidence to satisfy a criterion, or convert an unresolved disagreement into a confident
conclusion to reach a stopping point.

## CLI gates

```
python3 scripts/evidence_ledger.py manuscript.md --ledger ledger.json --graph graph.json
python3 scripts/counterfactual_eval.py evaluation.json --detection detection.json
python3 scripts/revision_impact.py manuscript.md --before before.md \
  --original-facts before-facts.json --revised-facts after-facts.json \
  --plan plan.json [--graph graph.json]
python3 scripts/revision_loop.py loop.json [--iterations n]
python3 scripts/evidence_core.py --self-check
```

Exit 0 means the applicable gate passed, 3 means failed, 4 means review, ambiguity or
invalid input. Every gate is read-only and writes no manuscript.
