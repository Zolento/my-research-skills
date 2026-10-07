# Experimental design and result entailment

## Level 1 Scientific identification

For each experiment identify question, hypothesis, comparison/manipulation,
observations, supported claims and plausible alternatives. Classify it as performance,
ablation, mechanism, robustness, generalization, sensitivity or failure analysis.
An unconnected experiment is an orphan candidate. An untested central hypothesis
is UNTESTED_HYPOTHESIS. An experiment unable to distinguish the target explanation
from an alternative is NON_IDENTIFYING_EXPERIMENT, not proof the explanation is false.

Check necessary controls, negative controls and sanity checks. Removing a component
may change capacity, optimization or budget simultaneously. This does not isolate
its claimed mechanism. Performance and associative ablation gains do not alone
establish causal mechanisms. State the strongest conclusion the design permits.

## Level 2 Validity checklist

- Data: train/test/preprocessing/subject leakage, duplicates, distribution mismatch,
  split appropriateness and sampling description. Verified central-result leakage
  is Critical. Missing detail is not proof of leakage.
- Baselines: relevant strong comparator, compute/training/tuning budgets, pretrained
  information, data access and identical evaluation protocol. Missing baseline
  knowledge needs external verification unless the paper itself supplies it.
- Metrics: claim-relevant estimand, direction, cherry-picking, aggregation/subgroups,
  uncertainty and appropriate statistical test. Non-significance is not equivalence.
- Ablation: exact scientific question, isolated factor, preserved training budget,
  and causal versus associative interpretation.
- Robustness: distinguish seeds, datasets, distributions, hyperparameters, corruptions
  and domains. One axis does not establish all-axis robustness. Mean gain is not
  robust gain. Limited benchmarks do not establish universal generality.
- Reproducibility: dataset, preprocessing, split, implementation, optimization,
  hyperparameters, seeds, compute and evaluation procedure for central results.

Do not turn absence of reported detail into a confident accusation. Record what is
missing and how to verify it. Correct controls, bounded robustness and fair
comparisons belong in Well Supported. New analysis/experiment repair paths describe
proposed work, never fabricated completed results.
