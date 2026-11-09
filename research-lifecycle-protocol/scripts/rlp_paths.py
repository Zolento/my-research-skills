#!/usr/bin/env python3
"""rlp_paths.py — RLP identity, protocol namespace and runtime-storage compatibility.

Why this module exists
----------------------
The skill was renamed from ``research-idea-pipeline`` to
``research-lifecycle-protocol``. Three names must not be conflated:

1. **Skill identity** — the frontmatter ``name``, the install slug and the repository
   directory. This is the only name that changes with the rename.
2. **Protocol namespace** — schema ids such as ``research-idea-pipeline/research-state@1``.
   They are opaque machine identifiers stored inside existing projects. Renaming them
   would invalidate every historical state, ledger and fixture, so they stay frozen.
3. **Project storage namespace** — ``<project>/.research-idea-pipeline/`` historically
   held canonical state, cognition projections, ledgers and scheduler telemetry. New
   projects use ``<project>/.research-lifecycle-protocol/``; old projects keep their
   existing root and are never migrated automatically.

Rules enforced here
-------------------
* An existing legacy root stays canonical. Nothing is copied, renamed or re-bootstrapped.
* If both roots exist, resolution fails closed. Two roots would mean two competing
  canonical states, which the lifecycle protocol forbids.
* A project with neither root is a new project; the new root is the documented default.
* This module performs no writes. It only resolves and reports.

CLI
---
    python3 scripts/rlp_paths.py resolve --project <project-root>
    python3 scripts/rlp_paths.py resolve --state <research-state.json>
    python3 scripts/rlp_paths.py check --project <project-root>

Exit codes: 0 resolved, 3 ambiguous/invalid layout, 4 environment or usage error.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from dataclasses import dataclass
from typing import Optional

SKILL_NAME = "research-lifecycle-protocol"
SKILL_ABBREVIATION = "RLP"
LEGACY_SKILL_NAMES = ("research-idea-pipeline",)

# Frozen machine protocol namespace. Do not rename: existing canonical states, ledgers,
# replay fixtures and cognition projections carry these ids.
SCHEMA_NAMESPACE = "research-idea-pipeline"
SCHEMA_NAMESPACE_IS_FROZEN = True

STORAGE_ROOT = ".research-lifecycle-protocol"
LEGACY_STORAGE_ROOT = ".research-idea-pipeline"
STORAGE_ROOTS = (STORAGE_ROOT, LEGACY_STORAGE_ROOT)

EXIT_OK = 0
EXIT_LAYOUT = 3
EXIT_ENV = 4


class AmbiguousStorageRoot(ValueError):
    """Both the new and the legacy runtime roots exist for one project."""


class LayoutError(ValueError):
    """A path does not match the documented route layout."""


@dataclass(frozen=True)
class StorageRoot:
    project_root: pathlib.Path
    root: pathlib.Path
    kind: str            # "current" | "legacy" | "new"
    is_legacy: bool


def _root_kind(path: pathlib.Path) -> Optional[str]:
    if path.name == STORAGE_ROOT:
        return "current"
    if path.name == LEGACY_STORAGE_ROOT:
        return "legacy"
    return None


def resolve_storage_root(project_root: pathlib.Path) -> StorageRoot:
    """Resolve which runtime root a project owns.

    Resolution order:
    1. both present  -> AmbiguousStorageRoot (never pick one silently);
    2. new present   -> the new root;
    3. legacy present-> the legacy root, read/write compatible, never migrated;
    4. neither       -> the new root, as the default for a new project.

    No directory is created here.
    """
    project = pathlib.Path(project_root).resolve()
    current = project / STORAGE_ROOT
    legacy = project / LEGACY_STORAGE_ROOT
    current_exists = current.is_dir()
    legacy_exists = legacy.is_dir()
    if current_exists and legacy_exists:
        raise AmbiguousStorageRoot(
            f"both {STORAGE_ROOT}/ and {LEGACY_STORAGE_ROOT}/ exist under {project}; "
            f"two canonical storage roots are not allowed. Keep one and archive the other.")
    if current_exists:
        return StorageRoot(project, current, "current", False)
    if legacy_exists:
        return StorageRoot(project, legacy, "legacy", True)
    return StorageRoot(project, current, "new", False)


def project_root_from_state(state_path: pathlib.Path) -> pathlib.Path:
    """Return the project root that owns a canonical state file.

    Accepts both documented layouts and the plain ``<root>/<route>/research-state.json``
    layout used by installed fixtures:

        <project>/.research-lifecycle-protocol/routes/<R>/research-state.json
        <project>/.research-idea-pipeline/routes/<R>/research-state.json
    """
    path = pathlib.Path(state_path).resolve()
    route_dir = path.parent
    if path.name != "research-state.json":
        raise LayoutError(f"{path} is not a research-state.json file")
    routes_dir = route_dir.parent
    if routes_dir.name != "routes":
        return route_dir
    control = routes_dir.parent
    if _root_kind(control):
        project = control.parent
        resolve_storage_root(project)          # fail closed if both roots exist
        return project
    raise LayoutError(
        f"{path} sits under a routes/ directory whose parent is neither "
        f"{STORAGE_ROOT} nor {LEGACY_STORAGE_ROOT}")


def route_dir_from_state(state_path: pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(state_path).resolve()
    if path.name != "research-state.json":
        raise LayoutError(f"{path} is not a research-state.json file")
    return path.parent


def default_state_path(project_root: pathlib.Path, route: str) -> pathlib.Path:
    """Canonical state path for a route, honouring an existing legacy root."""
    resolved = resolve_storage_root(project_root)
    return resolved.root / "routes" / route / "research-state.json"


def inspect_project(project_root: pathlib.Path) -> dict:
    """Read-only description of the identity/layout boundary."""
    project = pathlib.Path(project_root).resolve()
    try:
        resolved = resolve_storage_root(project)
        ambiguous = None
        kind = resolved.kind
        root = str(resolved.root)
        legacy = resolved.is_legacy
    except AmbiguousStorageRoot as exc:
        ambiguous = str(exc)
        kind = "ambiguous"
        root = None
        legacy = None
    return {
        "skill_name": SKILL_NAME,
        "skill_abbreviation": SKILL_ABBREVIATION,
        "legacy_skill_names": list(LEGACY_SKILL_NAMES),
        "schema_namespace": SCHEMA_NAMESPACE,
        "schema_namespace_frozen": SCHEMA_NAMESPACE_IS_FROZEN,
        "project_root": str(project),
        "storage_root": root,
        "storage_kind": kind,
        "legacy_layout": legacy,
        "ambiguous_reason": ambiguous,
        "new_root_default": STORAGE_ROOT,
        "legacy_root": LEGACY_STORAGE_ROOT,
    }


def _cmd_resolve(args: argparse.Namespace) -> int:
    if args.state:
        state = pathlib.Path(args.state)
        if not state.is_file():
            print(f"[env] state file not found: {state}", file=sys.stderr)
            return EXIT_ENV
        try:
            project = project_root_from_state(state)
        except LayoutError as exc:
            print(f"[layout] {exc}", file=sys.stderr)
            return EXIT_LAYOUT
    else:
        project = pathlib.Path(args.project)
        if not project.is_dir():
            print(f"[env] project directory not found: {project}", file=sys.stderr)
            return EXIT_ENV
    try:
        report = inspect_project(project)
    except OSError as exc:                                   # pragma: no cover
        print(f"[env] {exc}", file=sys.stderr)
        return EXIT_ENV
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return EXIT_LAYOUT if report["storage_kind"] == "ambiguous" else EXIT_OK


def _cmd_check(args: argparse.Namespace) -> int:
    report = inspect_project(pathlib.Path(args.project))
    if report["storage_kind"] == "ambiguous":
        print(f"[FAIL] {report['ambiguous_reason']}", file=sys.stderr)
        return EXIT_LAYOUT
    print(f"[ok] {SKILL_NAME}: storage={report['storage_kind']} "
          f"root={report['storage_root']} schema_namespace={SCHEMA_NAMESPACE} (frozen)")
    return EXIT_OK


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    resolve = sub.add_parser("resolve", help="resolve skill identity and runtime root")
    target = resolve.add_mutually_exclusive_group(required=True)
    target.add_argument("--project")
    target.add_argument("--state")
    resolve.set_defaults(func=_cmd_resolve)
    check = sub.add_parser("check", help="fail closed on an ambiguous layout")
    check.add_argument("--project", required=True)
    check.set_defaults(func=_cmd_check)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
