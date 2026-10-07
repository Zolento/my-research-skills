#!/usr/bin/env python3
"""Bounded R12 realization generation and offline probe protocol. No model API calls."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys

from validate_rhetorical_variant import freeze, registry, render, validate


def generate(state, snapshot):
    """Generate the entire pre-registered batch once; audit EVERY variant."""
    reg = registry()
    if len(reg["profiles"]) > reg["budget"]["max_variants"]:
        raise ValueError("profile batch exceeds pre-registered budget")
    variants = []
    for i, (profile, ops) in enumerate(reg["profiles"].items(), 1):
        variant = {"variant_id": f"V{i}", "snapshot_digest": snapshot["snapshot_digest"],
                   "semantics": copy.deepcopy(snapshot["semantics"]), "profile": profile,
                   "operators": copy.deepcopy(ops), "round": 1, "text": render(snapshot, profile)}
        gate = validate(state, snapshot, variant)
        if gate["status"] != "PASS":
            raise ValueError("generation failed equivalence gate: " + str(gate["errors"]))
        variants.append(variant)
    return variants


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("generate", help="read source State + D4a manifest; emit audited batch")
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        state = json.loads(args.state.read_text(encoding="utf-8"))
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        snapshot = freeze(state, manifest)
        result = {"snapshot": snapshot, "variants": generate(state, snapshot)}
    except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        print(json.dumps({"status": "FAIL", "errors": [str(exc)]}, ensure_ascii=False))
        return 4
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
