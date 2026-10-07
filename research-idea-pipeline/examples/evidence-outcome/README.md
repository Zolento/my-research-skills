# Executable Evidence Outcome examples

These are synthetic protocol fixtures. They demonstrate source-bound transitions,
not results from a real study or scientific detection accuracy. Each JSON contains
source state, collected packet, analysis proposal, semantic-audit verdict, timestamp,
post-update Assurance and expected decisions. No model API or experiment is invoked.
The audit verdicts are illustrative inputs. In a real run, inspect the actual logs,
configuration and measurements independently before assigning PASS.

| Input | Observation and validity | Scientific effect | Next decision |
|---|---|---|---|
| [positive.json](positive.json) | Valid fixed-budget comparison, M gains 0.8 | Tested performance claim and H1 SUPPORTED within Dataset A | CONTINUE |
| [valid-negative.json](valid-negative.json) | Valid completed comparison, improvement absent | H1 and corresponding claim WEAKENED, not globally falsified | HOLD for discriminating replication |
| [invalid-experiment.json](invalid-experiment.json) | Training crashes with an inspected shape mismatch | Invalid attempt, prior scientific support unchanged | RETRY after the shape fix is evidenced |
| [pivot.json](pivot.json) | Two eligible negative runs with different seeds meet frozen criteria | Scoped prediction FALSIFIED, original claim contradicted, negative knowledge retained | PIVOT with persistent protocol stop rule |
| [mixed.json](mixed.json) | Performance gains 0.8, mechanism proxy does not change, stress metric falls in one run | Performance SUPPORTED, mechanism WEAKENED, broad robustness UNRESOLVED | CONTINUE method, PIVOT mechanism, REDESIGN robustness |

In the mixed case H2 is a plausible capacity explanation, not an established cause.
A registered capacity-matched followup identifies the decision it would resolve.
The negative and pivot examples preserve surviving explanations. They do not
interpret absence of significance as equivalence or invent implementation faults.

From the skill directory, exercise all five source/state/Assurance paths through the
same release gate as the ordinary pipeline

```bash
python3 scripts/release_check.py
```

To inspect one example using the public API

```python
import json
import sys
sys.path.insert(0, "scripts")
import evidence_outcome as eo

with open("examples/evidence-outcome/valid-negative.json", encoding="utf-8") as source:
    case = json.load(source)
result = eo.apply(case["state"], case["packet"], case["analysis"], case["audit"], timestamp=case["timestamp"])
assert result["status"] == "PASS", result
print(eo.constraints(result["state"]))
print(eo.decision_gate(result["state"], case["packet"]["experiment_id"], case["assurance"]))
```

For command-line use, export the envelope's state, packet, analysis and audit into
separate JSON files, then use the [contract commands](../../references/evidence-outcome-contract.md).
Write a new state copy. State acceptance never itself authorizes another run.
For STOP, the same repeated-evidence criteria plus an explicit stop rule apply.
The regression suite also tests REDESIGN, STOP, local outcomes, stale decisions,
planning holds, cleared conditions, migration and unsupported attributions.

Each real report covers observations, validity, individual claims/hypotheses,
classification, alternatives, exact state delta, Assurance-gated decision,
stop/retry conditions and the next scientific action. Use the
[report template](../../templates/evidence-outcome-analysis.md).
