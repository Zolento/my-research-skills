# Counterfactual Evaluation

This contract governs `counterfactual-evaluation@1`, `counterfactual-detection@1` and
`scripts/counterfactual_eval.py`. The normative summary is in
[evidence-grounding.md](evidence-grounding.md) §2. The reasoning standard that these
cases must exercise is [scientific-coherence.md](scientific-coherence.md). The harness
is a read-only gate: it validates artifacts and writes nothing else.

```
python3 scripts/counterfactual_eval.py evaluation.json --detection detection.json
```

`--detection` is optional. Exit 0 is PASS, 3 is FAIL and 4 is NEEDS_REVIEW or INVALID.

## Why paired cases

A single faulty sentence is not a test. A pair states the same scientific content twice,
once as a defensible variant and once with exactly one introduced defect, so a supplied
detector can be scored against a known location. The case set records the defect, not a
judgment that the surrounding prose is good.

Every case carries `id`, `class`, `domain`, `correct`, `faulty`, `faulty_defect`,
`faulty_span` and `paraphrase`. These define three variants, and every case keeps them
consistent:

| Variant | Meaning | Required verdict |
|---|---|---|
| `correct` | clean, unreworded | clean |
| `faulty` | a genuine defect, or the reworded clean text | defective only for a defect class |
| `paraphrase` | the same scientific content as `correct`, different wording | clean |

`paraphrase` exists so that a clean baseline is not tied to one phrasing.

## The seven defect classes

The classes mirror the forbidden entailment leaps and the experimental checks in the
coherence standard. Each one names a failure mode that can be introduced by a single
local change, which is what makes a paired case reviewable.

- `causal_overreach`: association is rewritten as mechanism or cause. Performance gain
  becomes proof of the mechanism.
- `conclusion_inflation`: a bounded result is generalized beyond its design, for example
  internal validation becomes generalization to new sites.
- `invalid_control`: the comparison is not controlled, for example a baseline trained on
  a different split or with a larger budget.
- `missing_theoretical_assumption`: a result that holds only under a stated condition is
  presented unconditionally. The defect is the omitted precondition.
- `unidentifiable_experiment`: several factors change together, yet the observed gain is
  attributed to one of them.
- `evidence_mismatch`: a number, cohort or table is described as measuring something
  other than what it measures.
- `cross_section_contradiction`: two sections disagree on strength, scope or validation,
  for example an internal-only abstract and a limitation that reports external sites.

These seven are negative classes. A negative case declares a genuine defect, so its
`faulty_defect` is a real substring of `faulty` and `faulty_span` is the exact nonzero
span that locates it.

## Two robustness classes, two different questions

`ROBUSTNESS_CLASSES` has two members and they are not interchangeable. They test
different abilities, so they are validated and scored differently.

`robustness_paraphrase` is a clean robustness class. It has **no defect at all**.
`faulty` is the reworded clean text, `faulty_defect` is the empty string and
`faulty_span` is `{start: 0, end: 0}`. Flagging either `correct` or `faulty` is a false
positive, because the scientific content is unchanged by construction. There is no defect
location to overlap, so this class measures clean rejection, not detection.

`robustness_defect_rewording` **does contain the genuine defect**, worded differently
from its unreworded clean counterpart, which is what `paraphrase` holds. Its
`faulty_defect` is a real substring of `faulty` and `faulty_span` locates it. This class
is in `evidence_core.DEFECT_CLASSES`, so it is a defect class: it is scored for detection
recall, not rejection. It answers whether a real defect survives rewording, whereas
`robustness_paraphrase` answers whether a clean sentence is falsely flagged when reworded.

`evidence_core.DEFECT_CLASSES` is `FAULTY_CLASSES` plus `robustness_defect_rewording`.
The harness derives every defect-versus-clean decision from that list. It does not
hardcode class names.

## Detection is a separate artifact

`counterfactual-detection@1` records what a detector actually did over the case set. The
harness never runs, simulates or fabricates a detector, and contains no keyword, regex or
model rule for classifying text. The supplied artifact is the entire empirical input:

- `detector` has `name`, `kind` and `description`. A detector may be a human reviewer, a
  rule set or a model; `kind` never changes how results are read.
- `evaluation_digest` is the canonical SHA256 of the exact evaluation artifact. A stale
  digest is an error, so results cannot be attached to a different case set.
- `results` has one entry per case, with `case_id`, `observed`, `detected_span` and
  optional `notes`.

`observed` is `correct`, `miss`, `false_positive` or `uncertain`. A `correct`
observation claims the genuine defect was flagged in `faulty`. A `miss` means it was not
flagged. A `false_positive` means a clean variant was flagged. Every case in the
evaluation must appear exactly once; a missing or duplicated case is an error, because
measured accuracy stops being meaningful when coverage is incomplete.

For a `correct` observation on a defect class, `detected_span` must overlap `faulty_span`.
A flag that lands somewhere else did not find the declared defect, so it is recorded as a
miss and surfaced as a location failure. This rule is enforced with
`evidence_core.spans_overlap`. A `robustness_paraphrase` case has no defect span, so a
flag on it is a false positive whether or not it carries a span.

## Reading the result

The result reports two independent trust boundaries.

Structural validation covers the case set and the detection artifact: schema, required
fields, enum membership, unique ids, the variant rules for each class, digest binding and
complete one-to-one coverage. It makes no claim about science.

Empirical reporting counts the supplied detection and reports **two separate abilities**:

- `detection_recall` over `DEFECT_CLASSES`: `detected` divided by all defect cases, where
  a location failure counts as a miss. This is the share of genuine defects found.
- `clean_rejection_accuracy` over `robustness_paraphrase`: clean rejections divided by all
  clean-rejection outcomes, where a false positive counts against it. This is the share of
  unchanged-content variants left alone.

Also reported, with raw counts, are `detected`, `missed`, `location_failures`,
`false_positives`, `uncertain`, `clean_rejections` and `location_overlap_accuracy` (the
share of positive defect claims that actually overlapped the declared defect; undefined
when the detector made no positive claim). Counts appear per class, per class group and
overall. Recall and clean rejection are never folded into one accuracy number, because a
detector can be good at one and bad at the other, and a merged score would hide which.

Decision order, with a valid case set:

- Without a detection artifact the status is NEEDS_REVIEW. The run validated structure
  only, and semantic detection ability remains unvalidated.
- A structurally invalid detection artifact is FAIL.
- Any verified false positive is FAIL.
- Any miss, location failure, uncertainty or non-empty `missing_context` is NEEDS_REVIEW.
- PASS requires a structurally valid detection that reports every case once, leaves every
  clean `robustness_paraphrase` variant unflagged, and locates every defect, including the
  reworded ones.

## Limits

A passing harness proves that the case set and its reporting are well formed. It does not
prove that this skill detects faulty reasoning, and the output says so. The counts measure
one supplied detector over one supplied case set. They are not a benchmark, do not
generalize, and are not evidence of semantic ability. Only independently produced results
over held-out cases can speak to detection, and even those describe the detector, not the
skill.

The case set is author-constructed and small. It tests whether a detector can be scored,
not whether a detector is good. The bundled example is deliberately imperfect so that no
reader mistakes it for a benchmark result.
