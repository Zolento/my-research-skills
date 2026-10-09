# Evidence ledger walkthrough

This example shows one ledger gate run over a short results section and its
located argument graph. Every artifact is a real file inside this directory, so
every digest and every reference can be checked without a network or a model.

[manuscript.md](manuscript.md) holds the results text. [graph.json](graph.json)
locates the research question, experiment, observation, three claims and one
limitation. [ledger.json](ledger.json) records five artifacts and five evidence
records. The artifacts are a metrics file, a run log, a configuration file, a
reproduction script and reading notes on a prior study.

## What the example demonstrates

The three declared claims are handled differently, and the ledger says so.

- C1, the held-out precision and recall, is `verified`. Its headline record
  recomputes the numbers from
  [data/metrics.json](data/metrics.json) through
  [scripts/reproduce_metrics.py](scripts/reproduce_metrics.py). Provenance of
  the run is a separate non-headline record backed by
  [logs/run-2024-05-01.log](logs/run-2024-05-01.log).
- C2, that one configuration applied to every run, is `verified` by a
  `hash_match` against [config/run-config.json](config/run-config.json).
- C3, that a prior study reported comparable precision, stays `reported`. Its
  artifact is [notes/prior-study.md](notes/prior-study.md), a text artifact. The
  ledger marks it `presented_as_established: false`, so the run does not
  escalate it. Reading the note is not reproducing the prior result.
- The limitation sentence stays a located node in the graph, not a claim, so it
  is not used to justify anything.

The gate then returns PASS: every reference resolved, every digest matched, C1
and C2 have verified headlines, no claim is contradicted or unknown, coverage of
the graph central claims is complete, and `missing_context` is empty.

## What the example does not demonstrate

This is not scientific validation and not a claim that the numbers, the
detector or the prior study are correct. It does not show that the detector
generalises beyond the measured sensor families; the limitation node records
that it does not. It does not detect overclaiming, an unfair baseline or a
cross-section contradiction. Those remain the job of the coherence audit in
scientific-coherence.md.

A second limitation is deliberate: `notes/prior-study.md` is a local note, not
the prior publication. The record cannot be stronger than the artifact it points
at. A real ledger for that claim would point at the inspected source and still
stay `reported` until a separate act resolved it.

## Run the gate

```sh
python3 scripts/evidence_ledger.py examples/evidence-ledger/manuscript.md \
  --ledger examples/evidence-ledger/ledger.json \
  --graph examples/evidence-ledger/graph.json
```

The command is read-only and exits 0. Corrupt a digest or point an artifact at a
missing file and the gate exits 3. Leave a claim with no record and it exits 4
with distinct `NO_EVIDENCE` and `UNKNOWN` wording.
