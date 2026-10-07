#!/usr/bin/env python3
"""Fail-closed R12 equivalence checks for source-bound, registered realizations.

This checks a restricted renderer, not arbitrary natural-language equivalence.
The independently reviewed D4a manifest is a trust boundary, not a signature.
Exit 0=PASS, 3=FAIL, 4=input/environment error. Never writes Research State.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

import state_check

ROOT = Path(__file__).resolve().parent.parent
FIELDS = (
    "central_claim", "supporting_claims", "evidence_ids", "numerical_values",
    "comparators", "uncertainty", "scope", "assumptions", "limitations",
    "failure_cases", "prior_work_delta", "causal_status",
    "scientific_interpretation", "main_contribution",
)
SLOTS = ("S1", "S2", "S3", "S4", "S5", "S6")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def state_digest(state):
    # This narrower substage may change ONLY the pre-existing view descriptor.
    return digest({k: v for k, v in state.items() if k != "narrative_view"})


def registry():
    text = (ROOT / "references" / "rhetorical-operators.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)\n```", text, re.S)
    if len(blocks) != 1:
        raise ValueError("operator registry must contain exactly one JSON block")
    result = json.loads(blocks[0])
    allowed = result["evidence_framing"]["allowed"] + result["contribution_stance"]["allowed"]
    if len(allowed) != len(set(allowed)) or any(
            not set(ops) <= set(allowed) for ops in result["profiles"].values()):
        raise ValueError("invalid operator registry")
    return result


def pointer(state, path):
    """Resolve a non-root JSON Pointer into a scientific State field."""
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("bindings require non-root JSON Pointers")
    parts = [p.replace("~1", "/").replace("~0", "~") for p in path[1:].split("/")]
    if parts[0] not in {"claims", "evidence", "assumptions", "hypotheses",
                        "experiments", "literature", "failures", "uncertainties", "contract"}:
        raise ValueError(f"not a scientific source: {path}")
    value = state
    for part in parts:
        if isinstance(value, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", part):
                raise ValueError(f"invalid array index: {path}")
            value = value[int(part)]
        else:
            value = value[part]
    return copy.deepcopy(value)


def atoms(values):
    """Stable, visible source units. Do not extract or recalculate numbers."""
    result = []
    for value in values:
        if isinstance(value, list):
            result.extend(atoms(value))
        elif isinstance(value, str):
            if value.strip():
                result.append(value)
        elif value is not None:
            result.append(canonical(value))
    return list(dict.fromkeys(result))


def source_domains(state, claim_ids, evidence_ids):
    """Permitted source roles, not a natural-language semantic classifier.

    D4a still reviews what a source means. Mechanical domains prevent unrelated,
    ungrounded or planned facts from entering a checked realization via a slot.
    """
    claims = {f"/claims/{i}/{key}"
              for i, c in enumerate(state["claims"]) if c["id"] in claim_ids
              for key in ("statement", "scope", "nearest_alternative", "falsifier",
                          "known_flaws", "supporting_evidence", "refuting_evidence")}
    claim_fields = lambda key: {p for p in claims if p.endswith("/" + key)}
    ev = {f"/evidence/{i}/{key}"
          for i, e in enumerate(state["evidence"]) if e["id"] in evidence_ids
          for key in ("id", "scope", "source_ref", "epistemic_status")}
    ev_records = {f"/evidence/{i}" for i, e in enumerate(state["evidence"])
                  if e["id"] in evidence_ids}
    dependencies = {dep for e in state["evidence"] if e["id"] in evidence_ids
                    for dep in e.get("depends_on", [])}
    exp_records = set()
    for i, exp in enumerate(state["experiments"]):
        referenced = exp["id"] in dependencies
        relevant = referenced or bool(set(exp.get("claim_targeted", [])) & set(claim_ids))
        verified = exp["status"] in ("done", "failed") and exp["validity"]["status"] == "valid"
        if referenced and not verified:
            raise ValueError("referenced experimental source must be completed and valid")
        if relevant and verified:
            exp_records.add(f"/experiments/{i}")
    exp_fields = lambda key: {p + "/" + key for p in exp_records}
    literature = {f"/literature/{i}/ref" for i, item in enumerate(state["literature"])
                  if item["validity"]["status"] == "valid"}
    assumptions = {"/assumptions"} | {
        f"/assumptions/{i}/{key}" for i in range(len(state["assumptions"]))
        for key in ("statement", "if_false")}
    uncertainty = {"/uncertainties"} | {
        f"/uncertainties/{i}/question" for i in range(len(state["uncertainties"]))}
    uncertainty |= {p for p in ev if p.endswith("/epistemic_status")}
    uncertainty |= exp_fields("result") | exp_fields("interpretation")
    scope = claim_fields("scope") | {p for p in ev if p.endswith("/scope")} | exp_fields("data_split")
    if "out_of_scope" in state.get("contract", {}):
        scope.add("/contract/out_of_scope")
    failures = {"/failures"} | {f"/failures/{i}" for i in range(len(state["failures"]))}
    failures |= {f"/failures/{i}/what" for i in range(len(state["failures"]))}
    limitations = failures | claim_fields("known_flaws") | scope
    failure_cases = failures | {f"/experiments/{i}" for i, x in enumerate(state["experiments"])
                                         if x["status"] == "failed"}
    source_refs = {p for p in ev if p.endswith("/source_ref")}
    interpretation = ev_records | exp_fields("interpretation") | claim_fields("nearest_alternative")
    causal = exp_fields("interpretation") | claim_fields("nearest_alternative") | claim_fields("statement")
    numbers = exp_records | exp_fields("result") | exp_fields("metric") | exp_fields("data_split") | source_refs
    comparators = literature | source_refs | exp_fields("result")
    delta = source_refs | claim_fields("statement") | claim_fields("nearest_alternative") | exp_fields("interpretation")
    domains = {
        "central_claim": claim_fields("statement"), "supporting_claims": claim_fields("statement"),
        "main_contribution": claim_fields("statement"), "evidence_ids": {p for p in ev if p.endswith("/id")},
        "numerical_values": numbers, "comparators": comparators, "uncertainty": uncertainty,
        "scope": scope, "assumptions": assumptions, "limitations": limitations,
        "failure_cases": failure_cases, "prior_work_delta": delta, "causal_status": causal,
        "scientific_interpretation": interpretation,
    }
    context = {"/contract/goal"} if "goal" in state.get("contract", {}) else set()
    slots = {"S1": context | claim_fields("statement") | assumptions,
             "S2": comparators | delta,
             "S3": claim_fields("statement") | claim_fields("falsifier") | claim_fields("scope"),
             "S4": causal | assumptions,
             "S5": numbers | ev | ev_records | exp_fields("interpretation")
                   | claim_fields("supporting_evidence") | claim_fields("refuting_evidence"),
             "S6": scope | assumptions | uncertainty | limitations | failure_cases
                   | claim_fields("falsifier") | exp_fields("unexpected")}
    return domains, slots


def freeze(state, manifest):
    """D4a source projection. Selection/framing has already been scientifically reviewed."""
    if state_check.check_state(state).exit_code != 0:
        raise ValueError("source State must pass existing S/V gates")
    required = {"central_claim_id", "supporting_claim_ids", "main_contribution_id",
                "preset", "anchor", "anchor_eligibility", "scientific_framing",
                "contribution_order", "evidence_mapping", "bindings", "slots", "empty_reasons"}
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("manifest fields must match the frozen contract")
    if manifest["anchor_eligibility"] not in ("eligible", "conditional"):
        raise ValueError("not-eligible anchor cannot be realized")
    if not re.fullmatch(r"N(?:[1-9]|10)", manifest["preset"]):
        raise ValueError("unknown narrative preset")
    for key in ("anchor", "scientific_framing"):
        if not isinstance(manifest[key], str) or not manifest[key].strip():
            raise ValueError(f"missing {key}")
    ids = [manifest["central_claim_id"], *manifest["supporting_claim_ids"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate claim in hierarchy")
    claims = {c["id"]: c for c in state["claims"]}
    indices = {c["id"]: i for i, c in enumerate(state["claims"])}
    if not set(ids) <= set(claims) or manifest["main_contribution_id"] not in ids:
        raise ValueError("hierarchy/contribution must select existing claims")
    order = manifest["contribution_order"]
    if not isinstance(order, list) or len(order) != len(ids) or set(order) != set(ids):
        raise ValueError("contribution_order must contain every selected claim once")
    selected = [claims[cid] for cid in ids]
    if any(c["status"] not in ("supported", "partially-supported") or
           c["validity"]["status"] != "valid" for c in selected):
        raise ValueError("R12-post requires valid, grounded selected claims")
    mapping = {c["id"]: {"supports": c["supporting_evidence"],
                         "refutes": c["refuting_evidence"]} for c in selected}
    if canonical(manifest["evidence_mapping"]) != canonical(mapping):
        raise ValueError("evidence mapping differs from State")
    eids = {eid for c in selected for eid in c["supporting_evidence"] + c["refuting_evidence"]}
    evidence = {e["id"]: e for e in state["evidence"]}
    if any(evidence[eid]["epistemic_status"] not in ("Observed", "Supported") or
           evidence[eid]["validity"]["status"] != "valid" for eid in eids):
        raise ValueError("unverified/stale evidence cannot enter realization")
    bindings = manifest["bindings"]
    if not isinstance(bindings, dict) or set(bindings) != set(FIELDS):
        raise ValueError("all 14 semantic fields must be explicitly bound")
    if any(not isinstance(paths, list) or any(not isinstance(p, str) for p in paths)
           or len(paths) != len(set(paths)) for paths in bindings.values()):
        raise ValueError("each binding must be a unique pointer list")
    domains, slot_domains = source_domains(state, ids, eids)
    for key, paths in bindings.items():
        if not set(paths) <= domains[key]:
            raise ValueError(f"source role mismatch for {key}")
    identities = {
        "central_claim": [f"/claims/{indices[ids[0]]}/statement"],
        "supporting_claims": [f"/claims/{indices[cid]}/statement" for cid in ids[1:]],
        "main_contribution": [f"/claims/{indices[manifest['main_contribution_id']]}/statement"],
    }
    if any(bindings[key] != paths for key, paths in identities.items()):
        raise ValueError("claim bindings must refer to the selected claim identities")
    semantics = {key: [pointer(state, p) for p in bindings[key]] for key in FIELDS}
    expected = {
        "central_claim": [claims[ids[0]]["statement"]],
        "supporting_claims": [claims[cid]["statement"] for cid in ids[1:]],
        "main_contribution": [claims[manifest["main_contribution_id"]]["statement"]],
    }
    for key, value in expected.items():
        if canonical(semantics[key]) != canonical(value):
            raise ValueError(f"wrong source binding for {key}")
    if set(atoms(semantics["evidence_ids"])) != eids:
        raise ValueError("evidence_ids must include support and refutation")
    # Mandatory whole-array bindings prevent selective weakness/uncertainty omission.
    complete = {"uncertainty": ["/uncertainties"], "assumptions": ["/assumptions"],
                "limitations": ["/failures"], "failure_cases": ["/failures"]}
    complete["scope"] = [f"/claims/{indices[cid]}/scope" for cid in ids]
    if "out_of_scope" in state.get("contract", {}):
        complete["scope"].append("/contract/out_of_scope")
    for i, exp in enumerate(state["experiments"]):
        if exp["status"] == "failed":
            complete["failure_cases"].append(f"/experiments/{i}")
    for key, paths in complete.items():
        if not set(paths) <= set(bindings[key]):
            raise ValueError(f"incomplete source coverage for {key}")
    # All referenced experiments keep original metric/result/condition/interpretation;
    # evidence objects also preserve epistemic status, source and scope verbatim.
    for i, ev in enumerate(state["evidence"]):
        if ev["id"] in eids and f"/evidence/{i}" not in bindings["scientific_interpretation"]:
            raise ValueError("original evidence metadata must remain visible")
    experiments = {x for eid in eids for x in evidence[eid].get("depends_on", [])}
    for i, exp in enumerate(state["experiments"]):
        if exp["id"] in experiments and f"/experiments/{i}" not in bindings["numerical_values"]:
            raise ValueError("original experimental record must remain visible")
    if not atoms(semantics["scope"]) or not eids:
        raise ValueError("scope and evidence must be nonempty")
    if not isinstance(manifest["empty_reasons"], dict):
        raise ValueError("empty_reasons must be an object")
    for key in FIELDS:
        if not atoms(semantics[key]):
            reason = manifest["empty_reasons"].get(key)
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError(f"empty {key} requires a D4a reason")
    if not isinstance(manifest["slots"], dict) or set(manifest["slots"]) != set(SLOTS):
        raise ValueError("all six slots must have source bindings")
    slots = {}
    for key, paths in manifest["slots"].items():
        if not isinstance(paths, list) or not paths or any(not isinstance(p, str) for p in paths):
            raise ValueError(f"slot {key} must be nonempty")
        if len(paths) != len(set(paths)) or not set(paths) <= slot_domains[key]:
            raise ValueError(f"source role mismatch for slot {key}")
        slots[key] = [pointer(state, path) for path in paths]
    snapshot = {"schema": "narrative-realization@1", "state_digest": state_digest(state),
                "state_version": state["state_version"], "manifest": copy.deepcopy(manifest),
                "semantics": semantics, "slots": slots}
    snapshot["snapshot_digest"] = digest(snapshot)
    return snapshot


def render(snapshot, profile):
    reg = registry()
    if profile not in reg["profiles"]:
        raise ValueError("unregistered profile")
    ops = reg["profiles"][profile]
    semantic = snapshot["semantics"]

    def field(key, label=None):
        units = atoms(semantic[key])
        if not units:
            units = ["Not established: " + snapshot["manifest"]["empty_reasons"][key]]
        return (label or key) + ":\n" + "\n".join("- " + x for x in units)

    def slot(key):
        return "\n".join("- " + x for x in atoms(snapshot["slots"][key]))

    # Pinned early boundary is identical across profiles; no salience laundering.
    front = "\n\n".join([
        "S3 Central Proposition\n" + field("central_claim") + "\n" + slot("S3"),
        "S6 Consequence & Boundary\n" + slot("S6"),
        *(field(k) for k in ("scope", "uncertainty", "assumptions", "limitations", "failure_cases")),
    ])
    labels = {}
    if "comparator_forward" in ops:
        labels["comparators"] = "Comparators under the frozen evaluation conditions"
    if "effect_forward" in ops:
        labels["numerical_values"] = "Reported comparison / effect (original metric, aggregation and conditions)"
    if "consistency_forward" in ops:
        labels["scientific_interpretation"] = "Original interpretation / consistency evidence (no added robustness claim)"
    if "explicit_prior_delta" in ops:
        labels["prior_work_delta"] = "Closest prior-work delta (only the established difference)"
    if "explicit_contribution" in ops:
        labels["main_contribution"] = "Actual contribution (frozen scientific knowledge or engineering contribution)"
    body = {
        "S1": "S1 Context\n" + slot("S1"),
        "S2": "S2 Tension\n" + slot("S2") + "\n\n" + field("prior_work_delta", labels.get("prior_work_delta")),
        "S4": "S4 Resolution\n" + slot("S4") + "\n\n" + field("main_contribution", labels.get("main_contribution"))
              + "\n\n" + field("supporting_claims") + "\n\n" + field("causal_status"),
        "S5": "S5 Evidence Contract\n" + slot("S5") + "\n\n" + "\n\n".join(
            field(k, labels.get(k)) for k in ("comparators", "evidence_ids", "numerical_values", "scientific_interpretation"))
              + "\n\n" + "\n".join(
                  f"{cid} ← {', '.join(v['supports']) or '[待补]'}; refutes: {', '.join(v['refutes']) or 'none'}"
                  for cid, v in snapshot["manifest"]["evidence_mapping"].items()),
    }
    order = ["S1", "S2", "S4", "S5"]
    if "evidence_reordering" in ops:
        order = ["S5", "S1", "S2", "S4"]
    elif "contribution_salience" in ops:
        order = ["S2", "S4", "S1", "S5"]
    prefix = "Frozen scope and uncertainty apply.\n\n" if profile == "slightly-conservative" else ""
    return front + "\n\n" + prefix + "\n\n".join(body[key] for key in order)


def validate(state, snapshot, variant):
    """Validate actual prose against a trusted snapshot and current source State."""
    errors = []
    try:
        if state_digest(state) != snapshot["state_digest"]:
            errors.append("RE1: scientific State changed; re-freeze outside rhetorical search")
        expected = freeze(state, snapshot["manifest"])
        if canonical(expected) != canonical(snapshot):
            errors.append("RE2: snapshot/provenance/semantics changed")
        required = {"variant_id", "snapshot_digest", "semantics", "profile", "operators", "round", "text"}
        if not isinstance(variant, dict) or set(variant) != required:
            errors.append("RE2: variant contract shape differs")
        else:
            if not isinstance(variant["variant_id"], str) or not variant["variant_id"].strip():
                errors.append("RE2: missing variant identity")
            if variant["snapshot_digest"] != snapshot["snapshot_digest"] or canonical(variant["semantics"]) != canonical(snapshot["semantics"]):
                errors.append("RE2: frozen semantic fields changed")
            reg = registry()
            profile = variant["profile"]
            if profile not in reg["profiles"] or variant["operators"] != reg["profiles"].get(profile) or type(variant["round"]) is not int or variant["round"] != 1:
                errors.append("RE3: unregistered operators/profile or recursive round")
            elif not isinstance(variant["text"], str) or variant["text"] != render(snapshot, profile):
                errors.append("RE4/RE5: actual prose or boundary visibility changed")
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        errors.append(f"RE2: incomplete/invalid contract: {exc}")
    return {"status": "FAIL" if errors else "PASS", "errors": errors}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--variant", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        state, snapshot, variant = [json.loads(p.read_text(encoding="utf-8"))
                                    for p in (args.state, args.snapshot, args.variant)]
        result = validate(state, snapshot, variant)
        code = 0 if result["status"] == "PASS" else 3
    except (OSError, ValueError) as exc:
        result, code = {"status": "FAIL", "errors": [f"input/environment: {exc}"]}, 4
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
