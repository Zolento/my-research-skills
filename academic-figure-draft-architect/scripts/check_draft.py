#!/usr/bin/env python3
"""Formal contract linter for academic figure drafts.

This script validates the **form** of a produced figure draft Markdown file
against ``references/output-contract.md``.  It never judges scientific
correctness.

Usage
-----
    python3 check_draft.py [--strict] [--json] [--forbid TERM]... \
        [--require TERM]... FILE [FILE...]

Exit codes
----------
    0   clean
    1   usage / file error (unreadable file, no files given)
    2   warnings only
    3   at least one contract error

Only the Python standard library is used and nothing touches the network.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter

# ---------------------------------------------------------------------------
# Enumerations (kept identical to references/evidence-policy.md §3 and
# references/visual-grammar.md §1).
# ---------------------------------------------------------------------------

# canonical grammar name -> aliases that must normalise to it
GRAMMARS = [
    ("Linear Pipeline", ["linearpipeline"]),
    ("Dual / Multi Branch", ["dualmultibranch", "dualbranch", "multibranch"]),
    ("Hierarchical System", ["hierarchicalsystem"]),
    ("Iterative Loop", ["iterativeloop"]),
    ("Train vs Inference", ["trainvsinference"]),
    ("Data / Model / Objective", ["datamodelobjective"]),
    ("Source / Target Domain", ["sourcetargetdomain"]),
    ("Temporal / Stage View", ["temporalstageview", "stageview"]),
]

TYPE_ENUM = {
    "data",
    "model",
    "operator",
    "state",
    "objective",
    "parameter",
    "supervision",
    "output",
}

STATUS_FIRST = {"observed", "abstraction"}
STATUS_QUALIFIERS = {
    "frozen",
    "trainable",
    "train-only",
    "inference-only",
    "optional",
    "semantic",
}

CONFIDENCE_ENUM = {"high", "medium", "low"}

EVIDENCE_HEADER_KEYWORDS = ["element", "evidence", "confidence"]
INVENTORY_HEADER_KEYWORDS = ["id", "type", "label", "group", "inputs", "outputs", "status"]

REQUIRED_SECTIONS = [
    ("figure understanding", "Figure Understanding"),
    ("evidence summary", "Evidence Summary"),
    ("recommended draft", "Recommended Draft"),
    ("alignment notes", "Alignment Notes"),
    ("uncertainties", "Uncertainties"),
    ("svg handoff notes", "SVG Handoff Notes"),
    ("figure element inventory", "Figure Element Inventory"),
]

H2_RE = re.compile(r"^##(?!#)\s*(.*?)\s*$")
FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
CLOSE_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})[ \t]*$")
DRAFT_RE = re.compile(r"draft\s+([A-E])\b", re.IGNORECASE)
RECOMMENDED_RE = re.compile(r"Recommended:\s*Draft\s*([A-E])", re.IGNORECASE)
ID_RE = re.compile(r"^N\d+$")
ID_TOKEN_RE = re.compile(r"\bN\d+\b")
SEP_CELL_RE = re.compile(r"^:?-+:?$")

NONE_MARKERS = {"", "\u2014", "-", "\u2013", "--"}  # — - – --

# ---------------------------------------------------------------------------
# Sketch primitives (references/sketch-primitives.md).
#
# These detect the *geometry* of the three new primitives only.  Whether a
# primitive is scientifically warranted is a human judgement and stays in the
# SKILL.md §8 checklist.
# ---------------------------------------------------------------------------

SKETCH_STYLE_ENUM = {
    "auto",
    "clean",
    "enhanced",
    "block_architecture",
    "stage_panel",
    "loop_centric",
}
SKETCH_STYLE_DEFAULT = "auto"
SKETCH_VARIANTS_ENUM = {"single", "both"}
SKETCH_VARIANTS_DEFAULT = "single"
MAX_PSEUDO3D_BLOCKS = 3
MAX_TENSOR_LAYERS = 5

# strong signatures: a pseudo-3D corner / edge
P3D_SLASH_RUN_RE = re.compile(r"/[\u2500\u2501_-]{2,}/")
P3D_PIPE_TO_SLASH_RE = re.compile(r"\|\s*/\s*$")
P3D_CORNER_SLASH_RE = re.compile(r"[\u2518\u2514]\s*/\s*$")
# weak signature: the top face of the tall variant; only counts when the block
# also shows a strong signature (avoids false positives on `______` dividers)
P3D_UNDERSCORE_RE = re.compile(r"_{6,}")

TENSOR_SEP_RE = re.compile(r"\u251c[\u2500-]{2,}\u2524")
TENSOR_OFFSET_RE = re.compile(r"^\s*\u250c")
IMAGE_FRAME_RE = re.compile(r"\[(?:image|slice)\]", re.IGNORECASE)

SKETCH_STYLE_RE = re.compile(
    r"^[ \t]*(?:\*\*)?SKETCH_STYLE(?:\*\*)?[ \t]*:[ \t]*([A-Za-z_]+)", re.MULTILINE
)
SKETCH_VARIANTS_RE = re.compile(
    r"^[ \t]*(?:\*\*)?SKETCH_VARIANTS(?:\*\*)?[ \t]*:[ \t]*([A-Za-z]+)", re.MULTILINE
)

# Box glyph families of the shape-encodes-semantics legend
# (references/sketch-primitives.md §1).  Each entry is
# (top-left, top-right, bottom-left, bottom-right, vertical, horizontal).
BOX_FAMILIES = (
    ("\u250c", "\u2510", "\u2514", "\u2518", "\u2502", "\u2500"),  # ┌┐└┘│─ data
    ("\u2554", "\u2557", "\u255a", "\u255d", "\u2551", "\u2550"),  # ╔╗╚╝║═ model
    ("\u256d", "\u256e", "\u2570", "\u256f", "\u2502", "\u2500"),  # ╭╮╰╯│─ objective
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def display_width(text: str) -> int:
    """Display columns of *text*; CJK wide/full-width chars count as 2."""
    width = 0
    for ch in text:
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def _strip_value(cell: str) -> str:
    """Strip surrounding whitespace and common Markdown emphasis markers."""
    return cell.strip().strip("`*_ ").strip()


def _norm_grammar(text: str) -> str:
    """Lowercase and remove spaces / slashes / hyphens for grammar matching."""
    return re.sub(r"[\s/\-_]+", "", text.lower())


def match_grammar(text: str):
    """Return the canonical grammar name found in *text*, or ``None``."""
    normalised = _norm_grammar(text)
    for name, aliases in GRAMMARS:
        for alias in aliases:
            if alias in normalised:
                return name
    return None


def read_param(text: str, pattern):
    """Return the lower-cased value of the parameter matched by *pattern*.

    The value is validated against the relevant enum by the caller so that an
    unknown value is reported rather than silently treated as the default.
    """
    m = pattern.search(text)
    return m.group(1).lower() if m else None


def _span_kind(line: str, has_strong: bool):
    """Classify one line as a pseudo-3D signature, or ``None``."""
    if P3D_SLASH_RUN_RE.search(line):
        return "strong"
    if line.count("/") >= 2 and "|" in line:
        return "strong"
    if P3D_PIPE_TO_SLASH_RE.search(line):
        return "strong"
    if P3D_CORNER_SLASH_RE.search(line):
        return "strong"
    if has_strong and P3D_UNDERSCORE_RE.search(line):
        return "weak"
    return None


def find_pseudo3d(content):
    """Return the content indices of lines that draw a pseudo-3D block."""
    strong = [
        idx
        for idx, (_, line) in enumerate(content)
        if any(
            probe.search(line)
            for probe in (
                P3D_SLASH_RUN_RE,
                P3D_PIPE_TO_SLASH_RE,
                P3D_CORNER_SLASH_RE,
            )
        )
        or (line.count("/") >= 2 and "|" in line)
    ]
    has_strong = bool(strong)
    return [
        idx
        for idx, (_, line) in enumerate(content)
        if _span_kind(line, has_strong) is not None
    ]


def _group_runs(indices, gap: int = 2):
    """Group ascending indices that are at most *gap* apart."""
    groups = []
    for idx in indices:
        if groups and idx - groups[-1][-1] <= gap:
            groups[-1].append(idx)
        else:
            groups.append([idx])
    return groups


def count_pseudo3d_blocks(indices):
    """Number of distinct pseudo-3D blocks among matching line *indices*."""
    return len(_group_runs(indices))


def find_tensor_stacks(content):
    """Return ``(content_index, visible_layers)`` for every tensor stack.

    Two geometries are recognised: stacked sheets separated by ``├──┤`` rows,
    and the offset / cascaded stack of three or more ``┌`` corners.
    """
    stacks = []

    seps = [
        idx
        for idx, (_, line) in enumerate(content)
        if TENSOR_SEP_RE.search(line)
    ]
    for group in _group_runs(seps, gap=4):
        stacks.append((group[0], len(group) + 1))

    run = 0
    for idx, (_, line) in enumerate(content):
        if TENSOR_OFFSET_RE.match(line):
            run += 1
        else:
            if run >= 3:
                stacks.append((idx - run, run))
            run = 0
    if run >= 3:
        stacks.append((len(content) - run, run))

    return stacks


def find_image_frames(content):
    """Return the content indices of ``[image]`` / ``[slice]`` placeholders."""
    return [
        idx
        for idx, (_, line) in enumerate(content)
        if IMAGE_FRAME_RE.search(line)
    ]


def find_double_line_boxes(content):
    """Return ``(lineno, text)`` for every ``╔ … ╚`` box in *content*."""
    boxes = []
    start = None
    buf = []
    for lineno, line in content:
        if start is None:
            if "\u2554" not in line:
                continue
            start = lineno
            buf = [line]
        else:
            buf.append(line)
        if "\u255a" in line:
            boxes.append((start, " ".join(buf)))
            start = None
            buf = []
    if start is not None:
        boxes.append((start, " ".join(buf)))
    return boxes


def _shape_key(text: str) -> str:
    """Normalise a label / box text for shape-vs-semantics matching."""
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text.lower())


def _finding(level: str, code: str, line, message: str) -> dict:
    return {"level": level, "code": code, "line": line, "message": message}


def err(code: str, line, message: str) -> dict:
    return _finding("ERROR", code, line, message)


def warn(code: str, line, message: str) -> dict:
    return _finding("WARNING", code, line, message)


def _fmt_finding(f: dict) -> str:
    bits = []
    if f.get("code"):
        bits.append(f["code"])
    if f.get("line") is not None:
        bits.append("line %s" % f["line"])
    prefix = " ".join(bits)
    return "%s: %s" % (prefix, f["message"]) if prefix else f["message"]


# ---------------------------------------------------------------------------
# Markdown structure parsing
# ---------------------------------------------------------------------------

def parse_sections(lines, skip_lines=None):
    """Split *lines* into H2 sections.

    *skip_lines* is an optional set of 1-based line numbers that must not be
    treated as headings (e.g. lines inside fenced code blocks).  Returns a list
    of dicts with title/line/start/end (0-based start, exclusive end) and the
    body lines (list of ``(1-based lineno, text)``).
    """
    skip_lines = skip_lines or set()
    heads = []
    for idx, line in enumerate(lines):
        if (idx + 1) in skip_lines:
            continue
        m = H2_RE.match(line)
        if m:
            heads.append((idx, m.group(1).strip()))

    sections = []
    for pos, (idx, title) in enumerate(heads):
        end = heads[pos + 1][0] if pos + 1 < len(heads) else len(lines)
        body = [(i + 1, lines[i]) for i in range(idx + 1, end)]
        sections.append(
            {
                "title": title,
                "line": idx + 1,
                "start": idx,
                "end": end,
                "body": body,
            }
        )
    return sections


def section_text(section) -> str:
    return "\n".join(text for _, text in section["body"])


def find_section(sections, keyword):
    keyword = keyword.lower()
    for section in sections:
        if keyword in section["title"].lower():
            return section
    return None


def extract_fences(lines):
    """Return every fenced code block as ``{line, info, content, end}``.

    ``line``/``end`` are 1-based document line numbers of the opening fence
    and the line after the block; ``content`` is a list of
    ``(1-based lineno, text)`` pairs.
    """
    blocks = []
    i = 0
    total = len(lines)
    while i < total:
        m = FENCE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        fence = m.group(1)
        info = m.group(2).strip()
        char = fence[0]
        length = len(fence)
        content = []
        j = i + 1
        while j < total:
            close = CLOSE_FENCE_RE.match(lines[j])
            if close and close.group(1)[0] == char and len(close.group(1)) >= length:
                break
            content.append((j + 1, lines[j]))
            j += 1
        blocks.append({"line": i + 1, "info": info, "content": content, "end": j + 1})
        i = j + 1
    return blocks


def block_in_section(block, section) -> bool:
    opener_index = block["line"] - 1
    return section["start"] < opener_index < section["end"]


def split_cells(line: str):
    """Split a Markdown table row into stripped cells, or ``None``."""
    stripped = line.strip()
    if "|" not in stripped:
        return None
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_sep_row(cells) -> bool:
    return bool(cells) and all(SEP_CELL_RE.match(cell) for cell in cells)


def parse_tables(lines_with_no):
    """Return Markdown tables as ``{header, data, line}``.

    ``data`` is a list of ``(lineno, cells)``.
    """
    tables = []
    i = 0
    total = len(lines_with_no)
    while i < total:
        cells = split_cells(lines_with_no[i][1])
        if cells and i + 1 < total:
            sep = split_cells(lines_with_no[i + 1][1])
            if sep and _is_sep_row(sep):
                data = []
                j = i + 2
                while j < total:
                    row = split_cells(lines_with_no[j][1])
                    if not row or _is_sep_row(row):
                        break
                    data.append((lines_with_no[j][0], row))
                    j += 1
                tables.append(
                    {"header": cells, "data": data, "line": lines_with_no[i][0]}
                )
                i = j
                continue
        i += 1
    return tables


def header_has(table, keywords) -> bool:
    header = [cell.lower() for cell in table["header"]]
    for keyword in keywords:
        if not any(keyword in cell for cell in header):
            return False
    return True


def col_index(table, keyword) -> int:
    for idx, cell in enumerate(table["header"]):
        if keyword in cell.lower():
            return idx
    return -1


def cell_at(row, index: int) -> str:
    if index < 0 or index >= len(row):
        return ""
    return row[index]


def body_before_first_fence(section, lines) -> str:
    out = []
    for i in range(section["start"] + 1, min(section["end"], len(lines))):
        if FENCE_RE.match(lines[i]):
            break
        out.append(lines[i])
    return "\n".join(out)


def extract_uncertain_labels(content):
    """Yield ``(label, lineno)`` for each ``[?`` marker in a diagram."""
    results = []
    for lineno, text in content:
        idx = 0
        while True:
            pos = text.find("[?", idx)
            if pos == -1:
                break
            rest = text[pos + 2:]
            close = rest.find("]")
            if close != -1:
                label = rest[:close].strip()
            else:
                tokens = rest.split()
                label = tokens[0].strip() if tokens else ""
            results.append((label, lineno))
            idx = pos + 2
    return results


# ---------------------------------------------------------------------------
# Box alignment (W4)
# ---------------------------------------------------------------------------

def _column_chars(text: str) -> dict:
    """Map display column -> character, honouring CJK double width."""
    columns = {}
    col = 0
    for ch in text:
        columns[col] = ch
        col += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return columns


def _check_box_family(content, warns, family, pseudo3d):
    """Alignment checks for one box glyph family.

    *pseudo3d* is the set of content indices belonging to pseudo-3D geometry.
    A pseudo-3D block is a *projection*, not a closed rectangle, so its flat
    top face and its slanted edges must not be judged by the rectangle rules.

    Every top-left corner on a line is checked, so side-by-side boxes sharing
    one top border and one bottom border are each validated independently.
    """
    tl, tr, bl, br, vertical, horizontal = family
    total = len(content)

    def check_corner(i, pos_open):
        text_i = content[i][1]
        lineno_i = content[i][0]
        # A branching glyph such as `┌─▶` is not a box corner.  A real top
        # border always carries at least two horizontal glyphs after the
        # corner (`┌───┐`), so require that before treating it as a box.
        rest = text_i[pos_open + 1 :]
        if not rest.startswith(horizontal * 2):
            return
        # `┌──▶` / `┌──◀` are fork glyphs (see ascii-design-language.md §1),
        # not box tops: an arrow terminates the horizontal run.
        if re.match(r"^%s{2,}[\u25b6\u25c0]" % re.escape(horizontal), rest):
            return
        c1 = display_width(text_i[:pos_open])

        # c2 = first top-right corner strictly to the right of this one.
        c2 = None
        for pos, ch in enumerate(text_i):
            if ch == tr and display_width(text_i[:pos]) > c1:
                c2 = display_width(text_i[:pos])
                break
        if c2 is None:
            warns.append(
                warn(
                    "W4",
                    lineno_i,
                    "box top border has no matching %s on the same line" % tr,
                )
            )
            return

        # First following line carrying a bottom-left corner at column c1.
        # A single line may close several side-by-side boxes, so every corner
        # on the line must be considered -- not just the leftmost one.
        j_found = None
        for j in range(i + 1, total):
            if j in pseudo3d:
                continue
            text_j = content[j][1]
            if bl not in text_j:
                continue
            if any(
                display_width(text_j[:pos]) == c1
                for pos, ch in enumerate(text_j)
                if ch == bl
            ):
                j_found = j
                break
        if j_found is None:
            warns.append(
                warn(
                    "W4",
                    lineno_i,
                    "box top border has no matching %s at column %d" % (bl, c1),
                )
            )
            return

        lineno_j, text_j = content[j_found]
        if _column_chars(text_j).get(c2) != br:
            warns.append(
                warn(
                    "W4",
                    lineno_j,
                    "box bottom border is not closed by %s at column %d" % (br, c2),
                )
            )

        for k in range(i + 1, j_found):
            lineno_k, text_k = content[k]
            columns = _column_chars(text_k)
            if columns.get(c1) == vertical and columns.get(c2) != vertical:
                warns.append(
                    warn(
                        "W4",
                        lineno_k,
                        "box right border misaligned (expected %s at column %d)"
                        % (vertical, c2),
                    )
                )

    for i in range(total):
        text_i = content[i][1]
        if tl not in text_i:
            continue
        # Skip the flat top face of a pseudo-3D block (its slanted bottom edge
        # sits at a different column by design).
        if any(abs(i - k) <= 2 for k in pseudo3d):
            continue
        for pos_open, ch in enumerate(text_i):
            if ch == tl:
                check_corner(i, pos_open)


def check_box_alignment(content, warns):
    """Warn when box borders do not line up on the display-column grid.

    Covers every box family of the shape legend (flat ``┌┐└┘│``, double
    ``╔╗╚╝║``, rounded ``╭╮╰╯│``); see references/sketch-primitives.md §1 and
    references/ascii-design-language.md §1/§5.

    Rules (see references/output-contract.md §9):
      * ``c1`` = column of the top-left corner; ``c2`` = column of the *first*
        top-right corner strictly to its right (so side-by-side boxes do not
        interfere).
      * the closing line is the first following line whose bottom-left corner
        sits at ``c1``; it must carry the matching bottom-right corner at ``c2``.
      * every interior line with ``│`` at ``c1`` must have ``│`` at ``c2``.

    Deliberately does *not* count corner glyphs: side-by-side boxes and
    in-box tree branches (``└ [n]``) make counts unbalanced for valid drafts.
    Pseudo-3D projections are exempt (see :func:`_check_box_family`).
    """
    pseudo3d = set(find_pseudo3d(content))
    for family in BOX_FAMILIES:
        _check_box_family(content, warns, family, pseudo3d)


# ---------------------------------------------------------------------------
# Core contract checks
# ---------------------------------------------------------------------------

def check_against_contract(text, forbid, require, strict):
    lines = text.splitlines()
    errors = []
    warnings = []

    all_blocks = extract_fences(lines)
    # Lines strictly inside a fence are code, not Markdown structure.
    fenced_content_lines = set()
    for block in all_blocks:
        for lineno, _ in block["content"]:
            fenced_content_lines.add(lineno)

    sections = parse_sections(lines, skip_lines=fenced_content_lines)
    section_lines = [
        (i + 1, lines[i]) for i in range(len(lines)) if (i + 1) not in fenced_content_lines
    ]
    all_tables = parse_tables(section_lines)

    text_blocks = [b for b in all_blocks if b["info"].strip().lower() == "text"]

    # -- drafts ------------------------------------------------------------
    drafts = []
    for section in sections:
        m = DRAFT_RE.search(section["title"])
        if m:
            drafts.append((section, m.group(1).upper()))

    # E1: required sections.
    for keyword, name in REQUIRED_SECTIONS:
        if find_section(sections, keyword) is None:
            errors.append(err("E1", None, "missing required section: %s" % name))
    if len(drafts) < 2:
        errors.append(
            err(
                "E1",
                None,
                "expected at least 2 draft sections (Draft A–E), found %d" % len(drafts),
            )
        )

    # E2: Recommended: Draft <X>.
    recommended = find_section(sections, "recommended draft")
    if recommended is not None:
        rec_text = section_text(recommended)
        m = RECOMMENDED_RE.search(rec_text)
        if not m:
            errors.append(
                err("E2", recommended["line"], "missing `Recommended: Draft <A–E>`")
            )
        else:
            letter = m.group(1).upper()
            if letter not in {letter_ for _, letter_ in drafts}:
                errors.append(
                    err(
                        "E2",
                        recommended["line"],
                        "Recommended Draft %s has no matching draft section" % letter,
                    )
                )

    # E3 / E5: grammar per draft.
    draft_grammars = {}
    for section, letter in drafts:
        search_text = section["title"] + "\n" + body_before_first_fence(section, lines)
        grammar = match_grammar(search_text)
        if grammar is None:
            errors.append(
                err(
                    "E3",
                    section["line"],
                    "draft heading/body matches no canonical grammar: \"%s\""
                    % section["title"],
                )
            )
        else:
            draft_grammars[letter] = grammar

    if drafts:
        counts = Counter(draft_grammars.values())
        for grammar, count in counts.items():
            if count > 1:
                errors.append(
                    err("E5", None, "grammar reused by multiple drafts: %s" % grammar)
                )
        if len(counts) < 2:
            errors.append(
                err(
                    "E5",
                    None,
                    "fewer than 2 distinct grammars among drafts (%d)" % len(counts),
                )
            )

    # E4: each draft has a `text` fenced block.
    for section, _ in drafts:
        has_text = any(block_in_section(b, section) for b in text_blocks)
        if not has_text:
            errors.append(
                err(
                    "E4",
                    section["line"],
                    "draft section has no `text` fenced diagram block",
                )
            )

    # W1: Best for / Strength / Weakness labels.
    for section, _ in drafts:
        body_lower = section_text(section).lower()
        missing = [
            label for label in ("best for", "strength", "weakness") if label not in body_lower
        ]
        if missing:
            warnings.append(
                warn(
                    "W1",
                    section["line"],
                    "draft section lacks label(s): %s" % ", ".join(missing),
                )
            )

    # E6 / E7 / W2: Evidence Summary table.
    evidence_table = None
    for table in all_tables:
        if header_has(table, EVIDENCE_HEADER_KEYWORDS):
            evidence_table = table
            break
    if evidence_table is None:
        errors.append(
            err(
                "E6",
                None,
                "no Markdown table with element/evidence/confidence header",
            )
        )
    else:
        if not evidence_table["data"]:
            warnings.append(
                warn("W2", evidence_table["line"], "evidence table has no data rows")
            )
        conf_idx = col_index(evidence_table, "confidence")
        for lineno, row in evidence_table["data"]:
            raw = cell_at(row, conf_idx)
            value = _strip_value(raw).lower()
            if value not in CONFIDENCE_ENUM:
                errors.append(
                    err("E7", lineno, "invalid Confidence value: \"%s\"" % raw.strip())
                )

    # E8-E15: Figure Element Inventory.
    inventory = None
    for table in all_tables:
        if header_has(table, INVENTORY_HEADER_KEYWORDS):
            inventory = table
            break

    if inventory is None:
        errors.append(
            err(
                "E8",
                None,
                "no Markdown table with ID/Type/Label/Group/Inputs/Outputs/Status header",
            )
        )
    else:
        id_idx = col_index(inventory, "id")
        type_idx = col_index(inventory, "type")
        inputs_idx = col_index(inventory, "inputs")
        outputs_idx = col_index(inventory, "outputs")
        status_idx = col_index(inventory, "status")

        known_ids = []

        # Pass 1: every ID, so forward references resolve regardless of order.
        for lineno, row in inventory["data"]:
            id_value = _strip_value(cell_at(row, id_idx))
            if not ID_RE.match(id_value):
                errors.append(err("E9", lineno, "illegal inventory ID: \"%s\"" % id_value))
            else:
                known_ids.append(id_value)
        known_set = set(known_ids)

        # Pass 2: field values and references.
        for lineno, row in inventory["data"]:
            type_value = _strip_value(cell_at(row, type_idx)).lower()
            if type_value not in TYPE_ENUM:
                errors.append(
                    err("E10", lineno, "illegal Type value: \"%s\"" % type_value)
                )

            status_raw = _strip_value(cell_at(row, status_idx))
            tokens = [t.strip().lower() for t in re.split(r"[·/]", status_raw) if t.strip()]
            if not tokens:
                errors.append(err("E11", lineno, "empty Status value"))
            else:
                if tokens[0] not in STATUS_FIRST:
                    errors.append(
                        err(
                            "E11",
                            lineno,
                            "illegal Status first token: \"%s\"" % tokens[0],
                        )
                    )
                for qualifier in tokens[1:]:
                    if qualifier not in STATUS_QUALIFIERS:
                        errors.append(
                            err(
                                "E11",
                                lineno,
                                "illegal Status qualifier: \"%s\"" % qualifier,
                            )
                        )
                if tokens[0] == "inferred":
                    errors.append(
                        err(
                            "E15",
                            lineno,
                            "Status \"inferred\" is not allowed: D-level content must not "
                            "enter a draft (use an Uncertainties entry, or "
                            "\"observed / abstraction · optional\" plus a `[? ...]` marker)",
                        )
                    )

            for ref_idx, field in ((inputs_idx, "Inputs"), (outputs_idx, "Outputs")):
                ref_raw = _strip_value(cell_at(row, ref_idx))
                if ref_raw in NONE_MARKERS:
                    continue
                for token in re.split(r"[,\s]+", ref_raw):
                    if not token:
                        continue
                    if not ID_RE.match(token) or token not in known_set:
                        errors.append(
                            err(
                                "E12",
                                lineno,
                                "%s references unknown ID: \"%s\"" % (field, token),
                            )
                        )

        duplicates = Counter(known_ids)
        for value, count in duplicates.items():
            if count > 1:
                errors.append(err("E9", None, "duplicate inventory ID: %s" % value))

        # E13 / E14: traceability through Alignment Notes.
        alignment = find_section(sections, "alignment notes")
        if alignment is not None:
            align_text = section_text(alignment)
            mentioned = set(ID_TOKEN_RE.findall(align_text))
            for value in known_ids:
                if value not in mentioned:
                    errors.append(
                        err(
                            "E13",
                            alignment["line"],
                            "inventory ID %s never mentioned in Alignment Notes" % value,
                        )
                    )
            for token in sorted(mentioned):
                if token not in known_set:
                    errors.append(
                        err(
                            "E14",
                            alignment["line"],
                            "Alignment Notes reference dangling ID: %s" % token,
                        )
                    )

        # E15 (see the Status handling above): `inferred` is rejected there.

    # W3: `[?` markers in draft diagrams must be listed in Uncertainties.
    uncertainties = find_section(sections, "uncertainties")
    uncertainties_text = section_text(uncertainties).lower() if uncertainties else ""
    for section, _ in drafts:
        for block in text_blocks:
            if not block_in_section(block, section):
                continue
            for label, lineno in extract_uncertain_labels(block["content"]):
                if not label:
                    warnings.append(
                        warn(
                            "W3",
                            lineno,
                            "`[?` marker has no label and needs an Uncertainties entry",
                        )
                    )
                elif label.lower() not in uncertainties_text:
                    warnings.append(
                        warn(
                            "W3",
                            lineno,
                            "uncertainty label \"%s\" not found in Uncertainties" % label,
                        )
                    )

    # W4: box alignment for every `text` diagram in the document.
    for block in text_blocks:
        check_box_alignment(block["content"], warnings)

    # -- sketch primitives (references/sketch-primitives.md) ---------------
    style_raw = read_param(text, SKETCH_STYLE_RE)
    variants_raw = read_param(text, SKETCH_VARIANTS_RE)

    sketch_style = SKETCH_STYLE_DEFAULT
    if style_raw is not None:
        if style_raw not in SKETCH_STYLE_ENUM:
            errors.append(
                err(
                    "E17",
                    None,
                    "SKETCH_STYLE value %r not in enum (%s)"
                    % (style_raw, " / ".join(sorted(SKETCH_STYLE_ENUM))),
                )
            )
        else:
            sketch_style = style_raw

    sketch_variants = SKETCH_VARIANTS_DEFAULT
    if variants_raw is not None:
        if variants_raw not in SKETCH_VARIANTS_ENUM:
            errors.append(
                err(
                    "E17",
                    None,
                    "SKETCH_VARIANTS value %r not in enum (%s)"
                    % (variants_raw, " / ".join(sorted(SKETCH_VARIANTS_ENUM))),
                )
            )
        else:
            sketch_variants = variants_raw

    for section, _letter in drafts:
        blocks = [b for b in text_blocks if block_in_section(b, section)]
        if sketch_variants == "both" and len(blocks) < 2:
            warnings.append(
                warn(
                    "W7",
                    section["line"],
                    "SKETCH_VARIANTS: both needs two `text` blocks "
                    "(clean then enhanced); found %d" % len(blocks),
                )
            )
        pseudo_blocks = 0
        for block in blocks:
            content = block["content"]
            p3d = find_pseudo3d(content)
            stacks = find_tensor_stacks(content)
            pseudo_blocks += count_pseudo3d_blocks(p3d)

            if sketch_style == "clean":
                for idx in p3d:
                    errors.append(
                        err(
                            "E16",
                            content[idx][0],
                            "SKETCH: clean forbids pseudo-3D geometry",
                        )
                    )
                for idx in find_image_frames(content):
                    errors.append(
                        err(
                            "E16",
                            content[idx][0],
                            "SKETCH: clean forbids image-frame placeholders",
                        )
                    )

            for idx, layers in stacks:
                if sketch_style == "clean":
                    errors.append(
                        err(
                            "E16",
                            content[idx][0],
                            "SKETCH: clean forbids tensor stacks",
                        )
                    )
                if layers > MAX_TENSOR_LAYERS:
                    warnings.append(
                        warn(
                            "W5",
                            content[idx][0],
                            "tensor stack shows %d visible layers (max %d)"
                            % (layers, MAX_TENSOR_LAYERS),
                        )
                    )

        if pseudo_blocks > MAX_PSEUDO3D_BLOCKS:
            warnings.append(
                warn(
                    "W6",
                    section["line"],
                    "%d pseudo-3D blocks in one draft (max %d)"
                    % (pseudo_blocks, MAX_PSEUDO3D_BLOCKS),
                )
            )

    # W8: shape encodes semantics — a double-line box means `model`, so every
    # `╔…╚` box *drawn inside a draft* must be traceable to an inventory row
    # whose Type is `model`.  Blocks outside the drafts (legend swatches in a
    # preamble, prose examples) are not figure nodes and are not judged.
    draft_blocks = [
        block
        for block in text_blocks
        if any(block_in_section(block, section) for section, _ in drafts)
    ]
    double_boxes = [
        box for block in draft_blocks for box in find_double_line_boxes(block["content"])
    ]
    if double_boxes:
        labelled_rows = []
        if inventory is not None:
            type_idx_ = col_index(inventory, "type")
            label_idx_ = col_index(inventory, "label")
            if type_idx_ is not None and label_idx_ is not None:
                for _, row in inventory["data"]:
                    label = _strip_value(cell_at(row, label_idx_))
                    kind = _strip_value(cell_at(row, type_idx_)).lower()
                    if label:
                        labelled_rows.append((label, kind))
        # Prefer the most specific (longest) label that appears in the box.
        labelled_rows.sort(key=lambda item: len(item[0]), reverse=True)

        for lineno, box_text in double_boxes:
            haystack = _shape_key(box_text)
            # Ignore the legend swatch itself (a box drawn only to show a shape).
            match = next(
                (
                    (label, kind)
                    for label, kind in labelled_rows
                    if _shape_key(label) and _shape_key(label) in haystack
                ),
                None,
            )
            if match is None:
                warnings.append(
                    warn(
                        "W8",
                        lineno,
                        "double-line box (the `model` shape) is not traceable to "
                        "any inventory row",
                    )
                )
            elif match[1] != "model":
                warnings.append(
                    warn(
                        "W8",
                        lineno,
                        "double-line box (the `model` shape) maps to inventory row "
                        "%r whose Type is %r, not `model`" % (match[0], match[1]),
                    )
                )

    # --forbid / --require.
    # `--forbid` scans only what ends up *in the figure* — diagram blocks plus
    # the Evidence Summary and Figure Element Inventory tables.  Prose is
    # excluded on purpose: a draft must be able to declare what it left out
    # (MUST_NOT_INCLUDE statements, Uncertainties naming excluded modules).
    # `--require` scans the whole document.
    figure_parts = [text for block in text_blocks for _, text in block["content"]]
    for table in (evidence_table, inventory):
        if not table:
            continue
        figure_parts.extend(table.get("header", []))
        figure_parts.extend(cell for _, row in table.get("data", []) for cell in row)
    figure_haystack = "\n".join(figure_parts).lower()

    haystack = text.lower()
    for term in forbid:
        if term.lower() in figure_haystack:
            errors.append(err("F1", None, "forbidden term present: \"%s\"" % term))
    for term in require:
        if term.lower() not in haystack:
            errors.append(err("R1", None, "required term absent: \"%s\"" % term))

    if strict:
        promoted = []
        for finding in warnings:
            promoted.append(
                _finding("ERROR", finding["code"], finding["line"], finding["message"])
            )
        errors.extend(promoted)
        warnings = []

    return errors, warnings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, "%s: error: %s\n" % (self.prog, message))


def build_parser():
    parser = _Parser(
        prog="check_draft.py",
        description="Lint academic figure draft Markdown against the output contract.",
    )
    parser.add_argument("--strict", action="store_true", help="promote warnings to errors")
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit JSON")
    parser.add_argument("--forbid", action="append", default=[], metavar="TERM")
    parser.add_argument("--require", action="append", default=[], metavar="TERM")
    parser.add_argument("files", nargs="*", metavar="FILE")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.files:
        parser.error("no input files")

    results = []
    for path in args.files:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
        except (OSError, UnicodeDecodeError) as exc:
            results.append(
                {
                    "path": path,
                    "errors": [err("FILE", None, "cannot read file: %s" % exc)],
                    "warnings": [],
                    "code": 1,
                    "readable": False,
                }
            )
            continue

        errors, warnings = check_against_contract(
            text, args.forbid, args.require, args.strict
        )
        code = 3 if errors else (2 if warnings else 0)
        results.append(
            {
                "path": path,
                "errors": errors,
                "warnings": warnings,
                "code": code,
                "readable": True,
            }
        )

    codes = {result["code"] for result in results}
    if 1 in codes:
        # A file we could not read means the check is incomplete: file errors
        # dominate the aggregate.
        exit_code = 1
    elif 3 in codes:
        exit_code = 3
    elif 2 in codes:
        exit_code = 2
    else:
        exit_code = 0

    if args.as_json:
        payload = {
            "files": [
                {
                    "path": result["path"],
                    "errors": [_fmt_finding(f) for f in result["errors"]],
                    "warnings": [_fmt_finding(f) for f in result["warnings"]],
                }
                for result in results
            ],
            "errors": sum(len(r["errors"]) for r in results),
            "warnings": sum(len(r["warnings"]) for r in results),
            "exit_code": exit_code,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return exit_code

    def _human(level, finding):
        location = (
            " line %s:" % finding["line"] if finding["line"] is not None else ""
        )
        return "%s: %s %s%s %s\n" % (
            result["path"],
            level,
            finding["code"],
            location,
            finding["message"],
        )

    total_errors = 0
    total_warnings = 0
    for result in results:
        if not result["readable"]:
            for finding in result["errors"]:
                sys.stderr.write(_human("ERROR", finding))
            sys.stderr.write(
                "%s: %d error(s), 0 warning(s)\n" % (result["path"], len(result["errors"]))
            )
            total_errors += len(result["errors"])
            continue

        for finding in result["errors"]:
            sys.stdout.write(_human("ERROR", finding))
        for finding in result["warnings"]:
            sys.stdout.write(_human("WARNING", finding))
        sys.stdout.write(
            "%s: %d error(s), %d warning(s)\n"
            % (result["path"], len(result["errors"]), len(result["warnings"]))
        )
        total_errors += len(result["errors"])
        total_warnings += len(result["warnings"])

    sys.stdout.write("overall: %d error(s), %d warning(s)\n" % (total_errors, total_warnings))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
