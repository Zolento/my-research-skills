# Bounded revision loop

`bounded-revision-loop@1` tracks a problem-driven revision as a finite sequence of
rounds. Each round names what it intends to change and how that round is judged done.
The loop reports whether it made progress, which problems remain open and what a human
must decide. It never expands its own scope, invents evidence or converts an
unresolved disagreement into a confident conclusion. It is one of the four
evidence-grounding layers described in [evidence-grounding.md](evidence-grounding.md),
section 4.

```
python3 scripts/revision_loop.py loop.json [--iterations n]
```

Read-only. Exit 0 means PASS, 3 means FAIL and 4 means NEEDS_REVIEW or invalid input.

## Rounds are bounded by declaration

Each iteration has `id`, `problem_ids`, `target_change`, `completion_criteria`,
`scientific_disagreement` and `result`, and may declare `new_evidence` and
`resolves_problem_ids`. `result` is `progress`, `no_change` or `blocked`.

A round with an empty `target_change` or empty `completion_criteria` is not a bounded
revision round. That is a contract error: an unbounded round can drift, and a round
with no completion criterion cannot be reported as done.

Each problem has `id`, `statement`, `severity`, `state`, `iterations` and `resolution`.
`state` is `open`, `in_progress`, `resolved`, `blocked` or `withdrawn`. A problem in
state `resolved` needs a non-empty `resolution`. A problem in state `in_progress` must
appear in at least one processed round; otherwise the state and the rounds contradict
each other.

## Resolved problems stay resolved

A resolved problem may not be reopened or re-proposed without new evidence. The
resolving round is the one named in the problem's `iterations`, or an explicit
`resolves_problem_ids` declaration when present. Any later processed round that names
a resolved problem must declare `new_evidence` true. Re-proposing a resolved problem
without new evidence is an error, never a harmless re-run.

`new_evidence` is a boolean and must agree with the rounds. Claiming new evidence
while every processed result is `no_change` is an error. The top-level field states
whether the loop holds new evidence; the per-round field states whether a specific
round reopened a settled problem with it.

## Five stop reasons, one success

`stop_reason` is one of `completion_condition_met`, `no_substantive_progress`,
`scientific_disagreement`, `iteration_limit` or `user_stop`.

Only `completion_condition_met` is a successful stop. The three non-success stops are
`no_substantive_progress`, `scientific_disagreement` and `iteration_limit`. When the
completion condition is not met and the loop stops for any of those three, the gate
status is NEEDS_REVIEW, never PASS. `user_stop` with an unmet completion condition is
NEEDS_REVIEW for the same reason: an explicit stop ends the loop, it does not satisfy
the condition.

If `completion_met` is true, the loop must have stopped with
`completion_condition_met`. The converse also holds: a
`completion_condition_met` stop requires `completion_met` true. Any other combination
is an inconsistency and is an error.

## Disagreements become escalations

An iteration that declares `scientific_disagreement` yes must leave a pending
escalation, unless a matching escalation is already resolved. An escalation records
`problem_id` or `issue`, its `status` (`pending` or `resolved`) and, when resolved, a
`resolution`. A pending escalation forces NEEDS_REVIEW and appears in the list of
human decisions. The loop does not settle a scientific disagreement that the tooling
cannot settle.

## Caller cap

`--iterations n` is an optional cap supplied by the caller. When the loop declares
more rounds than the cap, only the first n are processed and the truncation is
reported explicitly in `unresolved`. A truncated review keeps NEEDS_REVIEW because
part of the declared work was not examined.

## Status and output

The artifact field `status` is the gate verdict. PASS requires a
`completion_condition_met` stop, `completion_met` true, no pending escalation and no
unresolved item. NEEDS_REVIEW covers non-success stops, pending escalations and
truncation. FAIL covers contract errors. The `loop_status` field carries the loop
vocabulary value: `ready_to_accept`, `no_substantive_progress`,
`scientific_disagreement`, `iteration_limit` or `in_progress`.

The output states whether the loop made progress, the remaining open problems and the
human decisions required. The loop only reaches `ready_to_accept`; it never declares
the revision accepted. A claim left at reported or unknown stays reported or unknown,
and no reviewer or confidence score is produced.
