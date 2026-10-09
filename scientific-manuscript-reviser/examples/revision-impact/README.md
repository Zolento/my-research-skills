# Revision impact and bounded loop example

A small, real end-to-end pair. [before.md](before.md) and [after.md](after.md) differ
by exactly two declared edits:

- a language-layer edit that removes the words `that` from the abstract sentence, and
- a scientific-content edit that narrows the results sentence to the tested subset.

The facts artifacts [before-facts.json](before-facts.json) and
[after-facts.json](after-facts.json) use the existing `manuscript-invariants@1`
contract. The argument graph [graph.json](graph.json) is digest-bound to
before.md and carries one claim node in the abstract, one observation node in the
results and one limitation node in the limitations. The declared plan is
[plan.json](plan.json). The bounded loop is [loop.json](loop.json).

## Run the impact gate

```
python3 scripts/revision_impact.py examples/revision-impact/after.md \
  --before examples/revision-impact/before.md \
  --original-facts examples/revision-impact/before-facts.json \
  --revised-facts examples/revision-impact/after-facts.json \
  --plan examples/revision-impact/plan.json \
  --graph examples/revision-impact/graph.json
```

Exit 0, status PASS. The language-layer edit keeps `minimal_sufficient_check`. The
scientific-content edit requires `full_semantic_audit`. The abstract edit reports
`cross_section` impacts for the results and limitations sections, because both nodes
depend on the edited claim location in a different context.

## Run the loop gate

```
python3 scripts/revision_loop.py examples/revision-impact/loop.json
```

Exit 4, status NEEDS_REVIEW. One problem is resolved with a declared resolution. One
problem is blocked, its round declares a scientific disagreement and a matching
escalation is pending, so the loop stops with an unmet completion condition and lists
the human decisions. `loop_status` is `scientific_disagreement`. It never reaches
`ready_to_accept`.

## What this demonstrates

- A declared edit plan is located against the before text and re-checked against the
  revised text, using the existing fact contract rather than a new one.
- Language-layer and scientific-content edits are held to different verification
  depths.
- Cross-section dependencies are surfaced when an edit touches a location that other
  sections rely on.
- A loop with a resolved and a blocked problem stays NEEDS_REVIEW when the completion
  condition is unmet, and it reports what a human must decide.

## What this does not demonstrate

- It does not judge scientific truth. The impact layer bounds required verification
  and the loop reports progress. Neither one certifies a claim.
- It does not run the required semantic audit, a detector or any model. A PASS on the
  impact gate means the plan and its required audits are well formed.
- It does not show a lost limitation, a new assertion without an original fact or a
  raised verification state. Those blocking paths are exercised in
  `tests/test_impact.py`, and they keep status NEEDS_REVIEW rather than silently
  proceeding.
