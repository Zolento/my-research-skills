# Real manuscript section walkthrough

Source is Seibold et al. (2021), *A computational reproducibility study of PLOS ONE
articles featuring longitudinal data analyses*, Materials and methods, Study questions,
first two paragraphs. [Published article](https://doi.org/10.1371/journal.pone.0251194).
The publisher identifies a Creative Commons Attribution license allowing reproduction
and adaptation with author/source credit. The text is attributed here and in this
directory; the adaptation is clearly separated from the original. The article has a
[2022 correction](https://doi.org/10.1371/journal.pone.0269047); this example uses the
publisher's displayed section, not a new assessment of its scientific results.

`input.txt` is the original excerpt. `proposed-revision.txt` only removes “Note that”
and capitalizes “Based”. It preserves the full selection boundary and both 11 values.
The revised sentence is an illustrative editorial proposal, not the authors' text.

## Short diagnosis and bank

Scientific purpose and the general-inference boundary are clear. The expectation
of helping authors stays an expectation, not an observed result. Scientific logic,
theory/proof, experimental design and conclusion validity remain limited by absent
full-paper context. No unsupported criticism is manufactured from the excerpt.
Narrative, paragraph roles, claims/evidence and references have no actionable local
issue that warrants an edit. Language has one minor opportunity. Defensiveness
contains necessary calibration, which must remain.

S2 exposes the missing local support for the expected benefit as a context-limited
structural candidate. Its alternatives are to inspect existing full-paper evidence
or evaluate the benefit if it is a central research goal. No full-paper defect or
completed new result is inferred from missing excerpt context.

S1 has two genuine options. A removes only the empty lead-in, giving a direct
boundary sentence. B keeps the original wording, retaining author voice and meta prose.
No extra alternatives or synonym changes are generated just for quantity.

Keep as is includes the direct statement about learning from encountered obstacles.
Well Supported includes the explicit no-general-inference boundary. Locations and
rationales are machine-readable in suggestions.json and graph.json.

## End-to-end artifacts and verdicts

`before-facts.json` and `after-facts.json` extract protected source spans.
`semantic-audit.json` records a source comparison of the minimal change. This is an
agent-performed audit example, not a claim of independent model-provider execution.
`graph.json`, `coherence-report.json` and `coherence-result.json` explicitly preserve
missing results/procedure/full-paper conclusions. The scientific verdict is NEEDS_REVIEW
for whole-paper coherence, including the untested expected-benefit hypothesis.

The suggestion bank's contract and quality audit PASS. Mechanical preservation,
post-edit semantic invariance and H1/H2 checks PASS for the illustrative minimal edit.
This does **not** mean the scientific paper has passed coherence review. Automatic
revision acceptance remains blocked by limited scientific context. The author may
review the proposal; a complete audit needs the rest of the manuscript.

```sh
python3 scripts/validate_style.py examples/real-section/proposed-revision.txt
python3 scripts/compare_invariants.py examples/real-section/input.txt \
  examples/real-section/proposed-revision.txt \
  --original-facts examples/real-section/before-facts.json \
  --revised-facts examples/real-section/after-facts.json \
  --audit examples/real-section/semantic-audit.json
python3 scripts/audit_coherence.py examples/real-section/input.txt \
  --graph examples/real-section/graph.json --report examples/real-section/coherence-report.json
```

The last command correctly returns review status (exit 4). A limited section should
not falsely pass a whole-paper audit merely because its prose is clear.
