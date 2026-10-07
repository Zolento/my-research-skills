#!/usr/bin/env python3
"""Offline R12 source freeze, realization and adversarial recovery tests."""
import copy
import json
from pathlib import Path
import unittest

import rhetorical_realization as rr
import validate_rhetorical_variant as rv

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "narrative-realization"


def fixture():
    state = json.loads((EXAMPLE / "source-state.json").read_text(encoding="utf-8"))
    manifest = json.loads((EXAMPLE / "manifest.json").read_text(encoding="utf-8"))
    snapshot = rv.freeze(state, manifest)
    return state, snapshot, rr.generate(state, snapshot)


class TestGeneration(unittest.TestCase):
    def test_bounded_profiles_all_pass_and_have_identical_semantics(self):
        state, snapshot, variants = fixture()
        self.assertEqual(len(variants), 4)
        for variant in variants:
            self.assertEqual(rv.validate(state, snapshot, variant)["status"], "PASS")
            self.assertEqual(variant["semantics"], snapshot["semantics"])
        self.assertEqual(len({v["text"] for v in variants}), 4)

    def test_read_only_generation_and_independent_objects(self):
        state, snapshot, _ = fixture()
        before = copy.deepcopy(state)
        frozen_before = copy.deepcopy(snapshot)
        variants = rr.generate(state, snapshot)
        self.assertEqual(state, before)
        self.assertEqual(snapshot, frozen_before)
        variants[0]["semantics"]["scope"].append("changed")
        self.assertEqual(snapshot, frozen_before)
        self.assertNotEqual(variants[0]["semantics"], variants[1]["semantics"])


if __name__ == "__main__":
    unittest.main()
