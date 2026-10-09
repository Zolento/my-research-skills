# Venue intelligence

One sentence governs this layer.

**Scientific validity is venue-independent. Contribution positioning and submission
requirements are venue-dependent.**

Everything below follows from that separation. Changing the target venue may change what to
emphasise, how to order a paper and which stated requirements apply. It may never change a
support status, a scientific finding, a mechanism claim or a critical gap. This layer does
not predict acceptance, score reviewer preference, imitate a reviewer or optimise a score.
`venue_intelligence_core.py` is the vocabulary authority, and `venue_dependent_change_ok`
mechanically rejects a venue-driven change to a support status or a vanished scientific defect.

## Fixed order

1. The venue-independent Scientific Coherence Audit runs first and its verdict stands.
2. The venue layer runs against a policy profile.

The order is structural, not stylistic. A scientific defect is never re-labelled as a venue
risk, and a venue fit judgement never softens a scientific verdict. Every critical and major
scientific finding must appear in the venue report; dropping one is an error, not a summary
choice.

A venue profile is optional. With no profile the skill runs a **venue-neutral science audit**,
applies no mandatory rule, and reports venue fit as unknown. If the user does not name a
venue, year and track, never infer one from topics, formatting or writing style.

## Venue Policy Registry

Profiles live in `venue-policies/profiles/` and their verbatim source excerpts in
`venue-policies/sources/`. The registry is offline-first: validation, lookup and reporting
need no network. Fetching a source is an optional maintenance step.

Each profile is bound to exactly one **venue, year and track**. Rules are typed:

| Kind | Meaning |
|---|---|
| `MANDATORY_POLICY` | The official text requires it. Must be `EXPLICIT`, from a `VERIFIED` source, with a verbatim quote. |
| `REVIEW_CRITERION` | What reviewers are instructed to judge. |
| `RECOMMENDED_PRACTICE` | Non-binding official advice. |
| `EMPIRICAL_CONVENTION` | Community practice not stated in official text. |
| `UNKNOWN` | Could not be established. |

Reviewer policy and author policy are recorded separately through each source's `phase`
(`reviewer`, `author` or `both`). The same rule is only in force for the year, venue and
track it was published for. A profile that cites another year's document is rejected, because
inheriting a superseded rule is how an unreviewed requirement becomes a false mandate. When a
venue has not published rules for a year, the correct entry is `UNKNOWN` or a
`changes_from_prior_year` entry with status `PENDING` — never last year's text presented as
current.

### Every claim is source-bound

A source file carries a `url`, a `retrieved` date, a `source_type`, a `status` and an
`excerpt` copied verbatim from the official page. Every profile claim carries a `quote` that
must occur verbatim in the cited excerpt, and `venue_registry.py` enforces that containment;
whitespace is normalised, wording is not. A summary therefore cannot masquerade as a published
rule. Quotes and digests make profiles re-checkable offline, and the original retrieved text
is kept in the branch-local development area for re-verification without shipping whole pages.

### Choosing, verifying and updating a profile

1. Identify the venue, year and track from the user. Do not guess.
2. Prefer official material: call for papers, author guidelines, reviewer guidelines, review
   forms, ethics and reproducibility policies, submission requirements.
3. Verify the document governs the requested edition, then record it as a source with
   `status: VERIFIED`. Use `PARTIAL` when it is incomplete or ambiguous and `UNREACHABLE`
   when it could not be retrieved.
4. Record only what the document states. Anything else becomes an `unknown_policies` entry or
   a `PENDING` change, with the reason.
5. Run `python3 scripts/venue_registry.py venue-policies`.

Incremental updates add or revise one profile. Because scope is exact, a new year never edits
an old profile: add a new one, fill `changes_from_prior_year`, and leave the historical
profile intact for comparison. Sources whose host serves one page for several year URLs must
be recorded against the edition the page actually governs, not the year in the link.

## Internal contribution classes and the official taxonomy

`venue_intelligence_core.INTERNAL_CONTRIBUTION_TYPES` holds the skill's own classes:
algorithmic/methodological, theoretical/foundational, problem formulation/conceptual,
empirical discovery/analysis, dataset/benchmark/evaluation, applied/systems/translational,
negative results/critical findings, and concept and feasibility.

These are internal analysis classes. They are **not** official submission categories and must
never be presented as the venue's labels. Positioning declares an `official_category` that
must exist in the cited profile's `contribution_types`; otherwise the mapping verdict is
`NOT_PUBLISHED` when the profile publishes none and the mapping is unverifiable without a
profile. A mixed contribution and an unresolved classification are both acceptable outcomes.

## Contribution positioning

`contribution_positioning.py` validates a **declared** positioning against evidence and
policy. It cannot discover what a paper contributes — that is scientific judgement — so it
enforces the rules that keep the declaration honest:

- Support status comes only from ledger evidence. No evidence is `UNKNOWN`, never
  `SUPPORTED`; reported-only evidence is never established.
- A novelty or priority assertion requires an inspected, source-bound prior-work record.
  Without one the status becomes `UNVERIFIED`. "First", "no prior work" and "unprecedented"
  are treated as claims to substantiate, not as rhetoric.
- A claimed structural equivalence must name the twin and the distinguishing property,
  otherwise it may be prior work reworded.
- Internal classes and official categories stay distinct.

Novelty, significance, soundness and presentation are reported separately. Expressive
strength never substitutes for a knowledge increment.

## Venue-aware audit

`venue_audit.py` evaluates eight criteria — scope fit, contribution type fit, soundness and
evidence adequacy, originality and prior-work delta, significance, experimental or theoretical
adequacy, reproducibility and transparency, and submission compliance — citing the official
criterion each traces to. Every issue is classified by what it actually is:

| Issue type | Origin | Meaning |
|---|---|---|
| `SCIENTIFIC_DEFECT` | scientific core | Invalidates or weakens a claim. Must cite the coherence finding it came from. |
| `CONTRIBUTION_GAP` | science or venue | The contribution is not yet supported or not established. |
| `VENUE_FIT_RISK` | venue layer | A real misfit with the venue's scope or criteria. Never a restatement of a defect. |
| `PRESENTATION_ISSUE` | either | Clarity or organisation, not validity. |
| `COMPLIANCE_ISSUE` | compliance layer | A stated submission requirement. |

A critical or major scientific defect cannot be closed by `TEXT_ONLY` or
`CLAIM_CALIBRATION` alone. A venue or presentation issue may not cite a scientific finding as
its source, which is how a defect would otherwise be quietly re-typed as a fit problem.

## Venue strategy

`venue_strategy.py` sits on the existing blueprint and changes framing, ordering and emphasis
only.

- A framing must rest on a genuinely different scientific anchor. Two framings that describe
  the same story are rejected, and a framing marked rhetorical-only is rejected outright.
- A proposed experiment must resolve a **named logic gap already recorded in the blueprint**,
  and must declare its hypothesis, the alternative explanations it rules out, the comparison
  and control, budget and data parity, observable, identifiability, completion condition, and
  which results would support or refute the claim. A venue preference is not a justification.
  "Run a bigger experiment" is not a repair.
- Every scientific gap in the blueprint must remain visible in the strategy.
- A contribution is never foregrounded beyond its evidence-derived support status.
- Strategy prose may not introduce a numeric value absent from the research material.

## Revision

The existing diagnose-first, suggestion-bank, scientific-invariance and post-edit audit rules
are unchanged. Venue strategy affects contribution presentation, section proportion,
information organisation and expression only. `venue_revision_impact.py` blocks a revision
that:

- raises a support status without new evidence,
- introduces a novelty claim without inspected prior work,
- removes or weakens an evidence boundary while labelled a text-only change.

A removed limitation is a scientific change wearing a presentation label. Real claim changes
still follow the original high-risk authorisation and new-baseline rules, and missing
experiments are never written as completed.

## Submission compliance

`submission_compliance.py` verifies only clearly checkable requirements: document structure,
required declarations, template clues, citation and anonymisation candidates. Hard policy is
reported separately from scientific quality.

- **Page limits are judged on the compiled document.** With no compiled file the page count is
  `UNKNOWN`. A LaTeX source length is never a page count, and the gate never claims a
  compliance it did not measure. When a PDF is supplied, the page count comes from its page
  tree.
- **AI-use disclosure** is checked only against records the author actually supplied. The gate
  never infers, reconstructs or guesses a usage history. No records plus an unknown disclosure
  state yields `NEEDS_REVIEW`.
- Anything a machine cannot establish stays `NEEDS_REVIEW`. The safe failure of a compliance
  gate is "unknown", never a false pass.

## Venue readiness

`venue_readiness.py` is the single reporting authority and aggregates the upstream verdicts
without recomputing them, so an issue cannot be softened by being summarised twice. Its
overall verdict is the worst of its inputs, with reasons listed.

It reports supported strengths, scientific defects, contribution gaps, venue fit risks,
mandatory requirements, unresolved items and a prioritised repair plan routed to `TEXT_ONLY`,
`EXISTING_DATA_REANALYSIS`, `NEW_EXPERIMENT`, `NEW_THEORY`, `CLAIM_CALIBRATION` or
`HUMAN_DECISION`. A blocker missing from the priority plan is an error, and a demoted blocker
is an error.

It deliberately produces **no acceptance probability, no weighted overall score and no
reviewer simulation**. Priority comes from the nature of the problem: a defect needing new
data or theory is a blocker; a wording issue is not.

## Interpreting status

`PASS` means the checks that ran found no problem **within their scope** — schema, provenance,
scope, coverage, evidence-derived support. It does not mean the paper is correct, novel or
acceptable. `NEEDS_REVIEW` means something genuine is unresolved: an `UNKNOWN` policy, missing
context, an unverified claim or a partial manuscript. `FAIL` means a rule was violated or a
finding is serious. Unresolved items are never silently dropped to reach `PASS`; a partial
manuscript cannot earn a whole-paper PASS.

## CLI

```
python3 scripts/venue_registry.py venue-policies
python3 scripts/venue_registry.py venue-policies --venue CVPR --year 2027 --track main
python3 scripts/contribution_positioning.py --positioning p.json --graph graph.json \
  --coherence report.json --ledger ledger.json --registry venue-policies
python3 scripts/venue_audit.py --audit audit.json --positioning p.json --coherence report.json \
  --venue CVPR --year 2027 --track main --registry venue-policies
python3 scripts/venue_strategy.py --strategy s.json --blueprint b.json --positioning p.json \
  --material-numbers numbers.json --venue CVPR --year 2027 --track main --registry venue-policies
python3 scripts/venue_revision_impact.py --impact i.json --before p.json --after q.json
python3 scripts/submission_compliance.py --manifest m.json --venue CVPR --year 2027 \
  --track main --registry venue-policies
python3 scripts/venue_readiness.py --report r.json --coherence report.json \
  --positioning p.json --venue-audit audit.json --compliance compliance.json
python3 scripts/venue_intelligence_core.py --self-check
```

Exit 0 means the applicable gate passed, 3 means failed, 4 means review, unknown or invalid
input. Every gate is read-only and writes no manuscript.
