# Source-bound R12 example

[source-state.json](source-state.json) is illustrative data, not an actual experiment.
[manifest.json](manifest.json) selects an existing hierarchy and binds every frozen field.
The same State yields four profiles. A profile changes labels and order, not results or claims.
The example keeps the single-dataset limitation, lack of significance testing and observational status.

Run from the skill directory:

```bash
python3 scripts/rhetorical_realization.py generate \
  --state examples/narrative-realization/source-state.json \
  --manifest examples/narrative-realization/manifest.json > /tmp/r12-batch.json
```

Split the batch for inspection and subsequent commands:

```python
import json
from pathlib import Path
batch = json.loads(Path('/tmp/r12-batch.json').read_text())
Path('/tmp/r12-snapshot.json').write_text(json.dumps(batch['snapshot']))
for variant in batch['variants']:
    Path('/tmp/r12-' + variant['variant_id'] + '.json').write_text(json.dumps(variant))
    Path('/tmp/r12-' + variant['variant_id'] + '.md').write_text(variant['text'])
```

Check each variant before sending it to a judge:

```bash
python3 scripts/validate_rhetorical_variant.py \
  --state examples/narrative-realization/source-state.json \
  --snapshot /tmp/r12-snapshot.json --variant /tmp/r12-V1.json
python3 scripts/rhetorical_realization.py probe-task \
  --state examples/narrative-realization/source-state.json \
  --snapshot /tmp/r12-snapshot.json --variant /tmp/r12-V1.json
```

The validator exits 0 for PASS, 3 for gate FAIL, 4 for input/environment error.
probe-task emits only narrative, questions and instructions, after equivalence validation.
Send that payload to a fresh reviewer context. Do not send the State, snapshot or ground truth.
Repeat for all four variants and every registered judge.

Before obtaining responses, create a judges JSON array with actual judge_id/model_id pairs.
Use at least two different model IDs; two prompts for one model do not qualify.

```bash
python3 scripts/rhetorical_realization.py plan \
  --snapshot /tmp/r12-snapshot.json --judges /tmp/r12-judges.json > /tmp/r12-plan.json
```

Each blind response is a JSON object with six array-valued keys, defined in the
[equivalence policy](../../references/rhetoric-equivalence-policy.md) §3.
The judge copies source units from the visible narrative. The tool does not invoke a model,
invent responses, or automatically accept a free paraphrase as an equivalent answer.

Adjudication and response wrapping are separate from the blind reviewer:

```python
import sys
sys.path.insert(0, 'scripts')
from rhetorical_realization import probe_record
plan = json.loads(Path('/tmp/r12-plan.json').read_text())
variant = json.loads(Path('/tmp/r12-V1.json').read_text())
response = json.loads(Path('/tmp/r12-J1-V1-response.json').read_text())
record = probe_record(plan, variant, 'J1', response)
# Persist every registered variant/judge record in one array; do not filter it.
```

```bash
python3 scripts/rhetorical_realization.py score \
  --snapshot /tmp/r12-snapshot.json --response /tmp/r12-J1-V1-response.json
python3 scripts/rhetorical_realization.py audit \
  --state examples/narrative-realization/source-state.json \
  --batch /tmp/r12-batch.json --plan /tmp/r12-plan.json --probes /tmp/r12-probes.json
python3 scripts/rhetorical_realization.py select \
  --state examples/narrative-realization/source-state.json \
  --batch /tmp/r12-batch.json --plan /tmp/r12-plan.json --probes /tmp/r12-probes.json
```

Raw responses and claimed model identity are supplied by the coordinator. The code cannot prove
that an external judge used a fresh context or the claimed model. Preserve execution logs.
score reports protocol validity separately from metric PASS/PARTIAL/FAIL. select rechecks source,
prose, plan, text/task identity and complete panel before comparing recovery.
audit exits 3 for fragility or incomplete data. select can return a choice with a fragile diagnostic;
it always retains that diagnostic and sets submission_ready=false. D5/G1–G5 are still required.
No live reviewer result is included in this example. Tests use explicitly synthetic responses.

MVP limitations: source completeness needs scientific review; arbitrary prose is rejected;
exact copied units can penalize correct paraphrases; whole source records are intentionally verbose.
Future prose compilers or adjudication maps need independent semantic audits, not looser keyword checks.

Suggested experiment: fix the State, hierarchy, model panel and budgets; blind the variant identity;
compare score-driven selection with comprehension-driven selection on a held-out model panel.
Use claim/evidence/delta/boundary recovery and paired fragility as outcomes. Retain all limitations.
Record overall scores only in a separate offline comparison arm; never feed them into this selector.
