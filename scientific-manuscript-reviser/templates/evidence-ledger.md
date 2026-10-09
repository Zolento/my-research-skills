# Claim evidence ledger template

Fill one record per claim and one record per evidence location. Delete every
placeholder. A placeholder left in the file is a claim with no evidence.

## Declared context

- Manuscript section and scope:
- Graph file and central claim ids:
- What this ledger does not cover:

## JSON skeleton

`schema` is fixed. `reference` paths are relative to the skill directory.
Compute each digest with `evidence_core.source_digest(path)`. Offsets count
Unicode characters with an exclusive end.

```json
{
  "schema": "claim-evidence-ledger@1",
  "claims": [
    {
      "id": "C1",
      "statement": "normalized claim text",
      "location": {"start": 0, "end": 0},
      "source_span": "exact manuscript wording",
      "presented_as_established": true
    }
  ],
  "artifacts": [
    {
      "id": "A1",
      "type": "experiment_data",
      "reference": "examples/evidence-ledger/data/metrics.json",
      "digest": "sha256 of the file bytes",
      "origin": "how this file was produced",
      "locator": "field or line that carries the evidence"
    }
  ],
  "evidence": [
    {
      "id": "E1",
      "claim_id": "C1",
      "artifact_id": "A1",
      "locator": "field precision",
      "statement": "what the located material says",
      "state": "verified",
      "verification_method": "recomputed",
      "headline": true,
      "scope": "what the evidence actually measures",
      "conditions": ["circumstance the evidence depends on"],
      "note": "anything a reader must know"
    }
  ],
  "missing_context": []
}
```

## Fill-in checklist

1. Declare every graph central claim in `claims`. Declare
   `presented_as_established` explicitly for each.
2. Use an artifact type from `evidence_core.ARTIFACT_TYPES`. Point it at the
   file that carries the evidence, not at a summary of the file.
3. Refresh every digest after any source edit. A stale digest is an error.
4. Give `scope` the narrow statement. Do not widen it to match the claim.
5. Use `verified` only with a real method. A text citation stays `reported` with
   method `unverified`.
6. Put at most one `headline` per claim. Add further records with
   `headline: false`.
7. Record a claim with no located support as `no_evidence`, not as `unknown`.
   Record an unresolved question with records as `unknown`.
8. List every unresolved item in `missing_context` as an explicit string.
9. Run the gate. Anything unresolved stays UNKNOWN or NEEDS_REVIEW.

## Verdict

- Status:
- Errors:
- Claims left at NO_EVIDENCE:
- Claims left at UNKNOWN:
- Escalations:
- Human decisions required:
