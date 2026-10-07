# Language naturalization

Natural writing preserves authorial variation and removes unnecessary model
regularity. It is not produced by adding randomness. Never optimize AI detector
scores or claim that surface signals establish machine authorship.

## Principles

1. Make the minimum sufficient edit.
2. Keep correct, clear simple wording.
3. Avoid uniform sentence rhythm, but do not pursue random variation.
4. Avoid paragraph-template homogenization.
5. Add no unnecessary lexical sophistication.
6. Avoid adjective/adverb inflation.
7. Reduce empty meta discourse when it contributes no information.
8. Preserve established domain terminology.
9. Preserve clear and correct author idiosyncrasies.
10. Prefer concrete facts to abstract evaluations.
11. Do not optimize against AI detectors.
12. Use no fixed word blacklist as the main mechanism.
13. Distinguish local awkwardness from global voice.
14. Allow asymmetric scientific paragraphs.
15. Do not turn every observation into a grand implication.

## Contextual diagnosis

L1 Overpolishing includes needless fancy-word substitution, adjective/adverb growth,
complexifying every sentence, replacing concrete verbs with abstract nouns or
uniformizing author choices. A clear natural sentence belongs in Keep as is.

L2 Inspect repeated subordinate clauses, identical lengths/rhythm, three-part lists,
transitions, contrast formulas, “not only ... but also” and participial phrases.
Short direct observations can be appropriate. Do not make length variance a goal.

L3 Lexical signals concern contextual density of generic evaluative adjectives,
abstract contribution verbs, inflated verbs, intensifiers and formulaic transitions.
“Novel”, “significant” and “robust” can be legitimate technical statements. Verify
meaning and support rather than mechanically replacing words. A warning lexicon
may supply weak candidates only when a repeated pattern is present.

L4 Empty “It is important to note”, “It should be emphasized”, “Interestingly” and
“Notably” can often be removed. Keep a discourse marker when it serves an actual
contrast, expectation or necessary qualification. L5 checks repeated enumerations,
balanced “on the one hand” constructions and symmetry. A single useful list is fine.
L6 examines avoidable nominalization such as “the utilization of”, while preserving
technical names and nominalizations that label scientific quantities.

## Examples and quality check

“We measured error on Dataset A.” needs no sophistication edit. Replacing measured
with quantified merely for variety is not a suggestion. “The utilization of the
model facilitates a remarkable enhancement” needs a context check for its actual
operation and supported effect, not a new assertion invented while simplifying it.

`diagnose_patterns.py` reports weak repetition/length/density candidates, not naturalness
verdicts. A separate editorial quality audit judges usefulness, voice, genuine options,
non-quota editing and claim calibration. Correct/simple/uneven prose can be better
than uniform polish. Leave it alone when there is no concrete communication problem.
