# Counterfactual evaluation example

This folder is a reviewable paired case set for `counterfactual-evaluation@1`.

- [evaluation.json](evaluation.json): eleven cases. Seven cover the seven
  `FAULTY_CLASSES`, two are `robustness_paraphrase` clean variants, and two are
  `robustness_defect_rewording` cases that keep a genuine defect under reworded context.
- [detection.json](detection.json): an illustrative, non-authoritative placeholder
  detection artifact. It is not a detector product and not a benchmark result.
- [optimistic-detection.json](optimistic-detection.json): a deliberately fabricated
  counter-example that claims every case is correct while pointing every span away from
  the declared defect. It exists to show that the harness does not accept unlocated
  claims at face value.

Run the gate with and without the placeholder:

```
python3 scripts/counterfactual_eval.py examples/counterfactual/evaluation.json
python3 scripts/counterfactual_eval.py examples/counterfactual/evaluation.json \
  --detection examples/counterfactual/detection.json
```

Without `--detection` the status is NEEDS_REVIEW: structure validated, semantic detection
unvalidated. With the placeholder the status is NEEDS_REVIEW and the raw counts are
`detected=7`, `missed=2`, `location_failures=1`, `false_positives=0`, `uncertain=0`,
`clean_rejections=2`. The two abilities are reported separately: `detection_recall` is
`0.7778` over nine defect cases and `clean_rejection_accuracy` is `1.0` over the two
`robustness_paraphrase` cases. They are not combined.

## Provenance

All eleven cases are **synthetic and author-constructed** for this contract. None is
taken from a real manuscript, a real review, a real detector output or a published
dataset. The domains are medical imaging segmentation, general machine learning and
statistics, and the wording is kept precise enough to be checkable, but the cases are
fixtures, not data.

The detection artifact is likewise fabricated for illustration. It was written by hand to
exercise the reporting path, not produced by running any tool. The optimistic artifact is
explicitly fabricated to test rejection.

## What each case demonstrates

| id | class | variant rule |
|---|---|---|
| co-augmentation-01 | causal_overreach | a genuine defect: association becomes "improves segmentation quality" |
| co-external-02 | conclusion_inflation | a genuine defect: internal validation becomes generalization "across clinical sites" |
| ic-baseline-03 | invalid_control | a genuine defect: baseline trained on a different split with a larger budget |
| mt-conditioning-04 | missing_theoretical_assumption | a genuine defect: the well-conditioned design assumption is dropped |
| ue-confounded-05 | unidentifiable_experiment | a genuine defect: a joint change is attributed to the augmentation alone |
| em-cohort-06 | evidence_mismatch | a genuine defect: a table is said to report the same screening-cohort result |
| xc-external-07 | cross_section_contradiction | a genuine defect: the limitation section reports external validation |
| rp-ci-08 | robustness_paraphrase | no defect; `faulty` rewords the clean text, defect is empty and span is `{0,0}` |
| rp-seed-09 | robustness_paraphrase | no defect; `faulty` rewords the clean text, defect is empty and span is `{0,0}` |
| rdr-mechanism-10 | robustness_defect_rewording | genuine causal overreach under reworded context; `paraphrase` is the clean text |
| rdr-generalization-11 | robustness_defect_rewording | genuine conclusion inflation under reworded context; `paraphrase` is the clean text |

For the seven negative classes and the two `robustness_defect_rewording` cases, every
`faulty_defect` is a real substring of `faulty` and `faulty_span` is the exact nonzero
span that locates it. For the two `robustness_paraphrase` cases, `faulty_defect` is the
empty string and `faulty_span` is `{start: 0, end: 0}`, because there is no defect.

## What this example demonstrates

- The structure contract can be validated mechanically, including defect location and the
  class-dependent rule for an empty defect.
- All seven defect classes, the clean robustness class and the reworded-defect robustness
  class are represented.
- Detection recall and clean-rejection accuracy are reported as separate numbers with
  raw counts, not one opaque score.
- A flag that does not overlap the declared defect is counted as a miss.
- A flag on a wording-only clean variant is a false positive.
- A reworded genuine defect is still scored for detection, not for rejection.
- A fabricated all-correct artifact with wrong spans does not produce a clean PASS.

## What this example does NOT demonstrate

- It does not show that this skill, or any detector, recognizes faulty reasoning. The
  placeholder detection is hand-authored and the case set is small.
- It is not a benchmark, has no held-out split and supports no accuracy claim.
- It does not prove that the classes cover real manuscript defects, only that they can be
  expressed and located as reviewable pairs.
- It does not certify the scientific content of the `correct` variants. They are
  plausible fixtures, not reviewed publications.

See [../../references/counterfactual-evaluation.md](../../references/counterfactual-evaluation.md)
for the full contract.
