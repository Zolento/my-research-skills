#!/usr/bin/env python3
"""Offline stdlib tests for ``check_draft.py``.

Run with::

    python3 -m unittest discover -s scripts -p 'test_*.py' -v

The tests import ``check_draft`` directly (inserting this script's directory on
``sys.path``) and drive ``check_draft.main()`` so no subprocess is spawned.
Everything writes fixtures into a ``tempfile.TemporaryDirectory`` and no test
touches the network.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import check_draft  # noqa: E402  (import after sys.path manipulation)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def box(label: str, inner: int = 16) -> str:
    """Return a display-width-safe ASCII box (labels are ASCII here)."""
    inner = max(inner, len(label) + 2)
    top = "┌" + "─" * inner + "┐"
    middle = "│" + (" " + label).ljust(inner) + "│"
    bottom = "└" + "─" * inner + "┘"
    return "\n".join([top, middle, bottom])


DRAFT_A_DIAGRAM = box("Input x") + "\n       │\n       ▼\n" + box("DC Step")
DRAFT_B_DIAGRAM = box("Update x_k") + "\n        │\n        ▼\n     repeat K"

# A box whose Chinese label is *not* padded to double display width.
MISALIGNED_CJK_DIAGRAM = "┌" + "─" * 16 + "┐\n│ 编码          │\n└" + "─" * 16 + "┘"


def make_valid() -> str:
    return f"""# F001 — Figure Draft

**FIGURE_TYPE**: method-overview (推断)

---

## 1. Figure Understanding

Input is measurement y. Output is reconstruction x.
Core compute path is data consistency plus a prior update.
Training uses a supervised loss; inference uses no target.
Core contribution is the iterative solver.

---

## 2. Evidence Summary

| Figure element | Evidence | Confidence |
|---|---|---|
| Measurement y | `data.py::load()` | High |
| DC Step | `solver.py::dc()` | High |

---

## 3. Draft A — Linear Pipeline

> 设计意图：强调单程 inference 路径。

```text
{DRAFT_A_DIAGRAM}
```

**Best for:** method overview

**Strength:** simple

**Weakness:** hides the loop

---

## 4. Draft B — Iterative Loop

> 设计意图：强调 recurrence。

```text
{DRAFT_B_DIAGRAM}
```

**Best for:** optimization view

**Strength:** clear recurrence

**Weakness:** dense

---

## 5. Recommended Draft

**Recommended: Draft B**

Why:
1. clearest contribution

---

## 6. Alignment Notes

N1 Measurement y ↔ `data.py::load()`
N2 DC Step ↔ `solver.py::dc()`

---

## 7. Uncertainties

Uncertain:
- none（U1）

---

## 8. SVG Handoff Notes

Canvas: landscape
Primary flow: left → right

---

## 9. Figure Element Inventory

| ID | Type | Label | Group | Inputs | Outputs | Status |
|---|---|---|---|---|---|---|
| N1 | data | Measurement y | Inference | — | N2 | observed |
| N2 | operator | DC Step | Solver | N1 | — | observed |
"""


class CheckDraftTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name: str, text: str) -> str:
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def run_check(self, argv):
        buffer = io.StringIO()
        err_buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(err_buffer):
            code = check_draft.main(argv)
        return code, buffer.getvalue() + err_buffer.getvalue()

    # -- 1. valid draft ----------------------------------------------------
    def test_valid_draft_exits_zero(self):
        path = self.write("valid.md", make_valid())
        code, out = self.run_check([path])
        self.assertEqual(code, 0, out)
        self.assertIn("0 error(s), 0 warning(s)", out)

    def test_valid_draft_strict_exits_zero(self):
        path = self.write("valid.md", make_valid())
        code, out = self.run_check(["--strict", path])
        self.assertEqual(code, 0, out)

    # -- 2. missing Uncertainties section ---------------------------------
    def test_missing_uncertainties_section(self):
        text = make_valid().replace("## 7. Uncertainties", "### 7. Uncertainties")
        path = self.write("no_uncertainties.md", text)
        code, out = self.run_check([path])
        self.assertEqual(code, 3, out)
        self.assertIn("Uncertainties", out)

    # -- 3. duplicate grammar ---------------------------------------------
    def test_duplicate_grammar(self):
        text = make_valid().replace(
            "## 4. Draft B — Iterative Loop", "## 4. Draft B — Linear Pipeline"
        )
        path = self.write("duplicate.md", text)
        code, out = self.run_check([path])
        self.assertEqual(code, 3, out)
        self.assertIn("E5", out)

    # -- 4. no character diagrams at all ----------------------------------
    def test_both_drafts_missing_text_blocks(self):
        text = make_valid().replace("```text", "```mermaid")
        path = self.write("mermaid_only.md", text)
        code, out = self.run_check([path])
        self.assertEqual(code, 3, out)
        self.assertIn("E4", out)

    # -- 5. bad confidence value ------------------------------------------
    def test_bad_confidence_value(self):
        text = make_valid().replace("| High |", "| Maybe |")
        path = self.write("confidence.md", text)
        code, out = self.run_check([path])
        self.assertEqual(code, 3, out)
        self.assertIn("E7", out)

    # -- 6. dangling inventory ID in Inputs -------------------------------
    def test_dangling_input_id(self):
        text = make_valid().replace(
            "| N1 | data | Measurement y | Inference | — | N2 | observed |",
            "| N1 | data | Measurement y | Inference | N9 | N2 | observed |",
        )
        path = self.write("dangling.md", text)
        code, out = self.run_check([path])
        self.assertEqual(code, 3, out)
        self.assertIn("E12", out)

    # -- 7. inventory ID never mentioned in Alignment Notes ---------------
    def test_id_missing_from_alignment_notes(self):
        text = make_valid().replace(
            "N2 DC Step ↔ `solver.py::dc()`", "DC Step ↔ `solver.py::dc()`"
        )
        path = self.write("untraced.md", text)
        code, out = self.run_check([path])
        self.assertEqual(code, 3, out)
        self.assertIn("E13", out)

    # -- 8. inferred label present in a diagram ---------------------------
    def test_inferred_status_rejected(self):
        # D-level content must not enter a draft: `inferred` has no Status slot.
        text = make_valid().replace(
            "| N2 | operator | DC Step | Solver | N1 | — | observed |",
            "| N2 | operator | DC Step | Solver | N1 | — | observed |\n"
            "| N3 | model | Feature Extractor | Prior | N1 | N2 | inferred |",
        )
        text = text.replace(
            "N2 DC Step ↔ `solver.py::dc()`",
            "N2 DC Step ↔ `solver.py::dc()`\n"
            "N3 Feature Extractor ↔ `prior.py::Feature Extractor`",
        )
        path = self.write("inferred.md", text)
        code, out = self.run_check([path])
        self.assertEqual(code, 3, out)
        self.assertIn("E15", out)
        self.assertIn("inferred", out)

    # -- 9. illegal Status first token ------------------------------------
    def test_illegal_status_token(self):
        text = make_valid().replace("| observed |", "| maybe |", 1)
        path = self.write("status.md", text)
        code, out = self.run_check([path])
        self.assertEqual(code, 3, out)
        self.assertIn("E11", out)

    # -- 10. CJK-misaligned box -------------------------------------------
    def test_cjk_misaligned_box_warns_then_strict_errors(self):
        text = make_valid().replace(DRAFT_A_DIAGRAM, MISALIGNED_CJK_DIAGRAM)
        path = self.write("cjk.md", text)

        code, out = self.run_check([path])
        self.assertEqual(code, 2, out)
        self.assertIn("W4", out)

        code_strict, out_strict = self.run_check(["--strict", path])
        self.assertEqual(code_strict, 3, out_strict)

    # -- 11. forbid / require ---------------------------------------------
    def test_forbid_present(self):
        path = self.write("valid.md", make_valid())
        code, out = self.run_check(["--forbid", "DC Step", path])
        self.assertEqual(code, 3, out)

    def test_forbid_absent_is_clean(self):
        path = self.write("valid.md", make_valid())
        code, out = self.run_check(["--forbid", "Cross Attention", path])
        self.assertEqual(code, 0, out)

    def test_forbid_scans_figure_content_only(self):
        # Naming an excluded module in prose is required (the draft must declare
        # what it left out) and must not trip --forbid ...
        prose = make_valid().replace(
            "N2 DC Step ↔ `solver.py::dc()`",
            "N2 DC Step ↔ `solver.py::dc()`\n"
            "**未画出：** Cross Attention（无依据，见 Uncertainties）",
        )
        path = self.write("prose_only.md", prose)
        code, out = self.run_check(["--forbid", "Cross Attention", path])
        self.assertEqual(code, 0, out)

        # ... but the same term inside a diagram is a real violation.
        figure = make_valid().replace(box("DC Step"), box("Cross Attention"))
        path2 = self.write("in_figure.md", figure)
        code2, out2 = self.run_check(["--forbid", "Cross Attention", path2])
        self.assertEqual(code2, 3, out2)
        self.assertIn("F1", out2)

    def test_require_absent(self):
        path = self.write("valid.md", make_valid())
        code, out = self.run_check(["--require", "Nonexistent Term", path])
        self.assertEqual(code, 3, out)

    def test_require_present_is_clean(self):
        path = self.write("valid.md", make_valid())
        code, out = self.run_check(["--require", "Flow Prior", path])
        self.assertEqual(code, 3, out)  # absent in the valid fixture
        code2, out2 = self.run_check(["--require", "DC Step", path])
        self.assertEqual(code2, 0, out2)

    # -- 12. JSON output ---------------------------------------------------
    def test_json_output_shape(self):
        path = self.write("valid.md", make_valid())
        code, out = self.run_check(["--json", path])
        self.assertEqual(code, 0, out)
        payload = json.loads(out)
        self.assertEqual(
            set(payload.keys()), {"files", "errors", "warnings", "exit_code"}
        )
        self.assertEqual(payload["exit_code"], 0)
        self.assertEqual(payload["errors"], 0)
        self.assertEqual(payload["warnings"], 0)
        self.assertIsInstance(payload["files"], list)
        self.assertEqual(payload["files"][0]["path"], path)
        self.assertIn("errors", payload["files"][0])
        self.assertIn("warnings", payload["files"][0])

    # -- 13. missing file --------------------------------------------------
    def test_missing_file_exits_one(self):
        path = os.path.join(self.dir, "does-not-exist.md")
        code, _ = self.run_check([path])
        self.assertEqual(code, 1)

    def test_no_files_exits_one(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_check([])
        self.assertEqual(ctx.exception.code, 1)

    # -- extra coverage: grammar aliases / normalisation -------------------
    def test_grammar_alias_normalisation(self):
        cases = {
            "Dual Branch": "Dual / Multi Branch",
            "Multi-Branch": "Dual / Multi Branch",
            "multibranch": "Dual / Multi Branch",
            "Data Model Objective": "Data / Model / Objective",
            "Stage View": "Temporal / Stage View",
        }
        for heading, expected in cases.items():
            with self.subTest(heading=heading):
                self.assertEqual(check_draft.match_grammar(heading), expected)

    def test_e14_dangling_alignment_id(self):
        text = make_valid().replace(
            "N2 DC Step ↔ `solver.py::dc()`",
            "N2 DC Step ↔ `solver.py::dc()`\nN99 stray reference",
        )
        path = self.write("dangling_align.md", text)
        code, out = self.run_check([path])
        self.assertEqual(code, 3, out)
        self.assertIn("E14", out)

    def test_w3_uncertain_label_resolved_in_uncertainties(self):
        text = make_valid().replace(
            DRAFT_A_DIAGRAM,
            box("Input x") + "\n       │\n       ▼\n" + box("[? Prior Step]"),
        )
        # The label is not listed in Uncertainties -> warning.
        path = self.write("uncertain_warn.md", text)
        code, out = self.run_check([path])
        self.assertEqual(code, 2, out)
        self.assertIn("W3", out)

        resolved = text.replace(
            "Uncertain:\n- none（U1）", "Uncertain:\n- prior step unclear（U1）"
        )
        path2 = self.write("uncertain_ok.md", resolved)
        code2, out2 = self.run_check([path2])
        self.assertEqual(code2, 0, out2)

    def test_w4_side_by_side_boxes_and_tree_branch_are_clean(self):
        # Two boxes side by side, each with its own border, plus an in-box tree
        # branch (└ leaf) that must not be mistaken for a closing corner.
        diagram = (
            "┌────────┐   ┌──────────┐\n"
            "│ A      │   │ B        │\n"
            "│  ├ sub │   │  └ leaf  │\n"
            "└────────┘   └──────────┘"
        )
        text = make_valid().replace(DRAFT_A_DIAGRAM, diagram)
        path = self.write("side_by_side.md", text)
        code, out = self.run_check(["--strict", path])
        self.assertEqual(code, 0, out)

    def test_w4_missing_right_border_warns(self):
        diagram = "┌────────┐\n│ Box\n└────────┘"
        text = make_valid().replace(DRAFT_A_DIAGRAM, diagram)
        path = self.write("missing_border.md", text)
        code, out = self.run_check([path])
        self.assertEqual(code, 2, out)
        self.assertIn("W4", out)
        self.assertIn("right border", out)

        code_strict, out_strict = self.run_check(["--strict", path])
        self.assertEqual(code_strict, 3, out_strict)

    def test_valid_status_qualifiers(self):
        text = make_valid().replace(
            "| N2 | operator | DC Step | Solver | N1 | — | observed |",
            "| N2 | operator | DC Step | Solver | N1 | — | observed · frozen |",
        )
        path = self.write("qualifiers.md", text)
        code, out = self.run_check([path])
        self.assertEqual(code, 0, out)

    def test_illegal_status_qualifier(self):
        text = make_valid().replace(
            "| N2 | operator | DC Step | Solver | N1 | — | observed |",
            "| N2 | operator | DC Step | Solver | N1 | — | observed · maybe |",
        )
        path = self.write("bad_qualifier.md", text)
        code, out = self.run_check([path])
        self.assertEqual(code, 3, out)
        self.assertIn("E11", out)

    def test_forbid_require_are_case_insensitive(self):
        path = self.write("valid.md", make_valid())
        code, out = self.run_check(["--forbid", "dc step", path])
        self.assertEqual(code, 3, out)
        code2, out2 = self.run_check(["--require", "dc step", path])
        self.assertEqual(code2, 0, out2)

    def test_pipe_inside_diagram_is_not_a_table(self):
        # A Markdown-looking table inside a fenced character diagram is code,
        # not a table: it must not be mistaken for the element inventory.
        in_fence_table = (
            "| ID | Type | Label | Group | Inputs | Outputs | Status |\n"
            "|---|---|---|---|---|---|---|\n"
            "| BAD | data | Foo | G | — | — | observed |\n"
        )
        diagram = box("Input x") + "\n" + in_fence_table + box("DC Step")
        text = make_valid().replace(DRAFT_A_DIAGRAM, diagram)
        path = self.write("pipe_diagram.md", text)
        code, out = self.run_check([path])
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
