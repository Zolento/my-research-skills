# Revision impact analysis

`revision-impact-analysis@1` maps each declared edit to the located scientific
elements that depend on it and states what verification that edit forces. It is the
gate between a selected edit and any acceptance decision. It is read-only, it writes
no manuscript and it never rewrites prose. It is one of the four evidence-grounding
layers described in [evidence-grounding.md](evidence-grounding.md), section 3.

```
python3 scripts/revision_impact.py manuscript.md --before before.md \
  --original-facts before-facts.json --revised-facts after-facts.json \
  --plan plan.json [--graph graph.json]
```

`manuscript.md` is the revised text. `--before` is the text the plan is located in.
The two facts artifacts use the existing `manuscript-invariants@1` contract and are
validated against their own text. When `--graph` is supplied it must be digest-bound
to the before text, because that is where the edited offsets live. Exit 0 means PASS,
3 means FAIL and 4 means NEEDS_REVIEW or invalid input.

## The plan is declared

The plan is an explicit list of edits. Each edit declares `id`, `location`,
`original_span`, `replacement`, `depth` and `scientific_risk`, and may declare
`selected_repair_requires`, `new_reference_ids`, `loses_limitation`,
`raises_to_verified` and `auto_acceptable`.

Those declarations are the point. A deterministic tool can locate a dependent
element by overlapping spans, but it cannot decide that two differently worded spans
mean the same thing. `new_reference_ids`, `loses_limitation` and `raises_to_verified`
are therefore inputs, never inferences. An edit whose `original_span` is not an exact
span of the before text is a contract error, not a fuzzy match.

## Depth decides the required check

`depth` is `language_layer` or `scientific_content`. `scientific_risk` is `low`,
`medium` or `high`.

| Declared depth | Risk | Required audit |
|---|---|---|
| `language_layer` | `low` | `minimal_sufficient_check` |
| `language_layer` | `medium` or `high` | `full_semantic_audit` |
| `scientific_content` | any | `full_semantic_audit` |

Language-layer edits change wording. At low risk the only thing that can move is the
surface of the text, so a minimal sufficient check is enough to confirm that the
protected facts and the mechanical invariants survived. Above low risk the same
wording can carry a claim, a scope boundary or a causal statement, so the full
semantic audit is required. Scientific-content edits always require the full audit,
regardless of how small the replacement looks.

Two declarations override the declared depth. A selected repair whose `requires` is
`requires_reanalysis`, `requires_new_experiment` or `requires_new_theory` becomes
`scientific_content`, and its required audits gain `needs_reanalysis`,
`needs_new_experiment` or `needs_new_theory`. An edit that declares
`raises_to_verified` becomes `scientific_content` too. `requires_text_change_only`
does not override anything.

## What blocks auto-acceptance

Automatic acceptance is blocked, never negotiated, when any of the following holds:

- A `new_reference_ids` entry has no matching fact id in the original facts. The edit
  introduces a scientific assertion with no located original fact.
- `loses_limitation` is true. A lost or weakened limitation is not a text-only repair,
  even when no experiment would be needed to re-establish it. The escalation uses
  `LIMITATION_GUARD`.
- `raises_to_verified` is true. A reported or unknown claim may not move to verified
  through an edit; verification is a separate resolved act.
- `introduced_punctuation` is non-empty. Prose punctuation from the defused set
  appears more often in the replacement than in the original span. The tool reports
  the characters and does not fix them, because this skill never rewrites prose.
- The selected repair requires reanalysis, a new experiment or new theory.

A blocked edit gets `auto_acceptable` false, a `blocked` entry and a pending
escalation. If the plan nonetheless declares `auto_acceptable` true for that edit,
the whole gate is FAIL: a declared automatic acceptance of a blocked edit is an
inconsistency, not a preference.

## Impacts and cross-section divergence

Impacts are located by overlapping the edit location with graph node spans. Node
types map to element kinds: claim-bearing nodes to `claim`, propositions and theory
nodes to `theory`, design and measurement nodes to `experiment`, and located results
and prior knowledge to `evidence`.

`impact` values are literal span relations, not semantic verdicts. An element whose
text is replaced is `changed`. An element inside the replaced span whose literal
survives in the replacement is `unchanged`. An element whose literal is absent from
the replacement and from the revised text is `removed`. Whether a rewording preserves
meaning stays with the full semantic audit.

When two or more graph nodes in different `context` sections depend on the edited
location, the result also carries `cross_section` impacts, one per divergent node.
A change in one section can otherwise become silently inconsistent with another. The
impact layer shows the sections diverge; resolving the divergence is human work.

Without `--graph`, the tool reports the edit-level analysis only, locates no
dependent element, and keeps status NEEDS_REVIEW with an explicit reason. Locating
dependents is not optional for acceptance.

## Status and vocabulary

PASS requires every edit to be well formed, every required audit to be named, no
pending escalation and no unresolved item. NEEDS_REVIEW covers blocked edits, a
missing graph, unresolved items and pending escalations. FAIL covers contract errors
and a declared automatic acceptance of a blocked edit.

A claim left at reported or unknown stays reported or unknown. The output carries no
reviewer score and no confidence score. This layer bounds the required verification
and surfaces human decisions; it does not judge scientific truth.
