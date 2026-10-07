# Bounded Architect walkthrough

This is a **synthetic protocol example**, not actual experimental evidence or a
proof benchmark. It supplies a matched comparison of X and P under Y and a mean
M improvement of 0.8. It establishes no significance, mechanism, cross-domain
robustness or prior-work novelty. Those strengths must not be invented.

Material map preserves source positions and epistemic types. Claim C is the bounded
mean comparison supported by the observation. Q motivates H, the comparison tests H,
and O supports C. Novelty is not established, so there is only one scientific thesis.
Two architecture choices put performance or protocol constraint first. They do not
pretend to be two different discoveries.

Full blueprint has five paragraphs with different roles

| Section | Paragraph role | Purpose |
|---|---|---|
| Introduction | problem | State the actual comparison question |
| Method | method_definition | Describe matched evaluation |
| Results | result | Report the bounded mean observation |
| Discussion | discussion | Separate observation from mechanism |
| Conclusion | takeaway | Restate the supported scope |

No decorative theory or invented Related Work is inserted. Literature grounding
for novelty remains missing. The experimental portfolio contains only the central
comparison. New controls or studies would be proposals with explicit logic gaps.

The local scientific report and outline review are protocol fixtures, not API model
responses. Their conditional PASS exercises artifact/status handling, not automatic
scientific truth assessment. All paragraph sketches obey H1/H2 and have a purpose,
claim/evidence map, short instruction, predecessor/successor and overinterpretation guard.

```sh
python3 scripts/architect.py check \
  --material examples/architect-bounded/materials.json \
  --graph examples/architect-bounded/graph.json \
  --report examples/architect-bounded/coherence-report.json \
  --blueprint examples/architect-bounded/blueprint.json \
  --audit examples/architect-bounded/outline-audit.json
```

To sketch the corresponding incomplete-research route, change a result's material
type to planned_experiment and rebuild the hierarchy as PLANNED with explicit gaps.
Leaving the supported result/contribution intact must FAIL. Changing prose alone
cannot upgrade planned evidence. Unresolved major findings remain visible as
SCIENTIFIC GAP TO RESOLVE, and the plan is not ready for completed-section drafting.
