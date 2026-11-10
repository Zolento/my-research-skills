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
import contextlib
import fcntl
import json
import os
import pathlib
import sys
import time
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

    STATUS = "AMBIGUOUS_STORAGE_ROOT"


class MigrationRequired(ValueError):
    """Only the legacy root exists: the project must migrate before formal runs.

    This is an engineering control-plane state, not a research failure — it must not
    enter Failure Memory, trigger replanning or restart experiments.
    """

    STATUS = "MIGRATION_REQUIRED"


class InvalidStorageRoot(ValueError):
    """The new root exists but carries no recognizable control-plane content.

    The runtime never silently repairs or rebuilds a broken control root.
    """

    STATUS = "INVALID_STORAGE_ROOT"


class LayoutError(ValueError):
    """A path does not match the documented route layout."""

    STATUS = "INVALID_LAYOUT"


#: Project-level maintenance control directory and its stable lock file. The lock is
#: the cooperation point between a running migration and RLP's own write entries.
MAINTENANCE_DIR = ".rlp-migration"
MAINTENANCE_LOCK_NAME = "control.lock"


class MaintenanceInProgress(RuntimeError):
    """A migration (or rollback) holds the project maintenance lock.

    Raised by RLP write entries so a cooperating writer never writes the control
    plane while it is being migrated. External writers that do not use this lock are
    NOT covered — the migration tool reports that limitation explicitly.
    """

    STATUS = "MAINTENANCE_IN_PROGRESS"


def maintenance_lock_path(project_root: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(project_root).expanduser().resolve() / MAINTENANCE_DIR / \
        MAINTENANCE_LOCK_NAME


def _read_lock_owner(project_root: pathlib.Path) -> Optional[Dict[str, Any]]:
    path = maintenance_lock_path(project_root)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) and value else None


def maintenance_status(project_root: pathlib.Path) -> Dict[str, Any]:
    """Read-only view: is the maintenance lock currently held, and by whom?

    Detection opens the lock file and tries a non-blocking exclusive lock, then
    releases it immediately. This is a best-effort inspection for reports; writers
    must still go through :func:`maintenance_guard` to be actually excluded.
    """
    path = maintenance_lock_path(project_root)
    if not path.is_file():
        return {"held": False, "path": str(path), "owner": None}
    handle = None
    try:
        handle = os.open(str(path), os.O_RDONLY)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"held": True, "path": str(path),
                    "owner": _read_lock_owner(project_root)}
        finally:
            try:
                fcntl.flock(handle, fcntl.LOCK_UN)
            except OSError:
                pass
        return {"held": False, "path": str(path),
                "owner": _read_lock_owner(project_root)}
    except OSError:
        return {"held": None, "path": str(path),
                "owner": _read_lock_owner(project_root)}
    finally:
        if handle is not None:
            os.close(handle)


@contextlib.contextmanager
def maintenance_guard(project_root: pathlib.Path):
    """Hold a SHARED maintenance lock for one control-plane write.

    Cooperating RLP writers take this guard; a migration holds the EXCLUSIVE lock for
    its whole transaction, so a guarded write fails with MaintenanceInProgress instead
    of racing the migration. Non-cooperating writers (external Mesh workers, training
    scripts, third-party plugins) do not take this lock and are not excluded — the
    migration report lists them explicitly.
    """
    path = maintenance_lock_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            owner = _read_lock_owner(project_root)
            raise MaintenanceInProgress(
                "项目正在维护（迁移或回滚进行中）：暂停控制平面写入"
                + (f"；持有者：{owner}" if owner else "")) from exc
        try:
            yield
        finally:
            try:
                fcntl.flock(handle, fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        os.close(handle)


@contextlib.contextmanager
def maintenance_exclusive(project_root: pathlib.Path, *, owner: Dict[str, Any]):
    """Hold the EXCLUSIVE maintenance lock for a whole migration transaction.

    Writes owner metadata (migration id, pid, command, start time) into the lock file
    so an interrupted run and cooperating writers can see who holds it.
    """
    path = maintenance_lock_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            current = _read_lock_owner(project_root)
            raise MaintenanceInProgress(
                "另一个迁移/回滚正在持有维护锁"
                + (f"：{current}" if current else "")) from exc
        payload = {"pid": os.getpid(), "started_at":
                   time.strftime("%Y-%m-%dT%H:%M:%S"), **owner}
        os.ftruncate(handle, 0)
        os.lseek(handle, 0, os.SEEK_SET)
        os.write(handle, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        os.fsync(handle)
        try:
            yield payload
        finally:
            try:
                os.ftruncate(handle, 0)
                os.fsync(handle)
            except OSError:
                pass
            try:
                fcntl.flock(handle, fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        os.close(handle)


#: Stable status tokens for the storage matrix (§2.1 of the storage spec).
RUNTIME_STATUS_READY = "READY"
RUNTIME_STATUS_NEW_PROJECT = "NEW_PROJECT"
RUNTIME_STATUS_MIGRATION_REQUIRED = "MIGRATION_REQUIRED"
RUNTIME_STATUS_AMBIGUOUS = "AMBIGUOUS_STORAGE_ROOT"
RUNTIME_STATUS_INVALID = "INVALID_STORAGE_ROOT"

#: Content that makes an existing new root recognizable. An empty directory is
#: INVALID_STORAGE_ROOT — the runtime never silently repairs a control root.
_ROOT_MARKERS = ("routes", "project", "meta", "runtime", "cache")


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


def _is_recognizable_root(path: pathlib.Path) -> bool:
    """Does an existing root directory carry recognizable control-plane content?"""
    try:
        entries = {entry.name for entry in path.iterdir()}
    except OSError:
        return False
    return bool(entries & set(_ROOT_MARKERS)) or \
        any(name.endswith(".json") for name in entries)


def runtime_status(project_root: pathlib.Path) -> Dict[str, Any]:
    """The machine-readable storage matrix (stable status tokens).

    | 现场 | 状态 | 运行行为 |
    |---|---|---|
    | 两根都不存在 | NEW_PROJECT | 初始化使用新根 |
    | 只有新根（有可识别内容） | READY | 正常加载与执行 |
    | 只有新根（空/不可识别） | INVALID_STORAGE_ROOT | 禁止静默修复或重建 |
    | 只有旧根 | MIGRATION_REQUIRED | 暂停正式运行，先迁移 |
    | 两根同时存在 | AMBIGUOUS_STORAGE_ROOT | fail closed |
    """
    project = pathlib.Path(project_root).resolve()
    current = project / STORAGE_ROOT
    legacy = project / LEGACY_STORAGE_ROOT
    current_exists = current.is_dir()
    legacy_exists = legacy.is_dir()
    base = {"project_root": str(project), "new_root": str(current),
            "legacy_root": str(legacy), "new_root_exists": current_exists,
            "legacy_root_exists": legacy_exists}
    if current_exists and legacy_exists:
        return {**base, "status": RUNTIME_STATUS_AMBIGUOUS,
                "reason": f"both {STORAGE_ROOT}/ and {LEGACY_STORAGE_ROOT}/ exist; "
                          "two canonical storage roots are not allowed"}
    if current_exists:
        if not _is_recognizable_root(current):
            return {**base, "status": RUNTIME_STATUS_INVALID,
                    "reason": f"{RUNTIME_STATUS_INVALID}: {STORAGE_ROOT}/ exists but "
                              "carries no recognizable control-plane content; the "
                              "runtime never silently repairs or rebuilds it"}
        return {**base, "status": RUNTIME_STATUS_READY, "reason": None}
    if legacy_exists:
        return {**base, "status": RUNTIME_STATUS_MIGRATION_REQUIRED,
                "reason": f"{RUNTIME_STATUS_MIGRATION_REQUIRED}: only "
                          f"{LEGACY_STORAGE_ROOT}/ exists; formal research runs are "
                          "paused until the project migrates "
                          "(scripts/migrate_project_root.py)"}
    return {**base, "status": RUNTIME_STATUS_NEW_PROJECT, "reason": None}


def resolve_runtime_root(project_root: pathlib.Path) -> StorageRoot:
    """The ONLY runtime resolver: returns the new root or raises.

    Raises AmbiguousStorageRoot (both roots), MigrationRequired (legacy only) or
    InvalidStorageRoot (new root without recognizable content). Normal research
    execution must call this — never read or write the legacy root as runtime state.
    No directory is created here.
    """
    report = runtime_status(project_root)
    if report["status"] == RUNTIME_STATUS_AMBIGUOUS:
        raise AmbiguousStorageRoot(report["reason"])
    if report["status"] == RUNTIME_STATUS_MIGRATION_REQUIRED:
        raise MigrationRequired(report["reason"])
    if report["status"] == RUNTIME_STATUS_INVALID:
        raise InvalidStorageRoot(report["reason"])
    return StorageRoot(pathlib.Path(project_root).resolve(),
                       pathlib.Path(project_root).resolve() / STORAGE_ROOT,
                       "current" if report["status"] == RUNTIME_STATUS_READY else "new",
                       False)


def inspect_legacy_root(project_root: pathlib.Path) -> Optional[StorageRoot]:
    """Migration/audit/compat-inspection API: describe the legacy root if present.

    Read-only. Does not raise for the storage matrix; returns None when no legacy
    root exists. Never used as a runtime write base.
    """
    project = pathlib.Path(project_root).resolve()
    legacy = project / LEGACY_STORAGE_ROOT
    if not legacy.is_dir():
        return None
    return StorageRoot(project, legacy, "legacy", True)


def resolve_storage_root(project_root: pathlib.Path) -> StorageRoot:
    """Legacy-aware inspection resolver (migration / compat tools only).

    Runtime code must use :func:`resolve_runtime_root`. This function keeps the
    v2.0.x dual-root behaviour for read-only compatibility inspection and raises on
    the ambiguous layout.
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
        report = runtime_status(project)
        if report["status"] == RUNTIME_STATUS_AMBIGUOUS:
            raise AmbiguousStorageRoot(report["reason"])
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
    """Canonical state path for a route under the ONLY runtime root.

    Raises MigrationRequired / AmbiguousStorageRoot / InvalidStorageRoot — normal
    runtime never reads or writes the legacy root.
    """
    resolved = resolve_runtime_root(project_root)
    return resolved.root / "routes" / route / "research-state.json"


def ensure_runtime_root(project_root: pathlib.Path) -> StorageRoot:
    """Gate for write entries (loop / reconcile / execution / projections).

    Raises the storage-matrix errors instead of letting a legacy project continue
    formal research. Read-only tools and the migration tool must NOT call this.
    """
    return resolve_runtime_root(project_root)


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
    matrix = runtime_status(project)
    legacy_root = inspect_legacy_root(project)
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
        "runtime_status": matrix["status"],
        "runtime_reason": matrix["reason"],
        "legacy_root_present": legacy_root is not None,
        "legacy_root_path": str(legacy_root.root) if legacy_root else None,
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
    status = report["runtime_status"]
    if status in (RUNTIME_STATUS_AMBIGUOUS, RUNTIME_STATUS_INVALID,
                  RUNTIME_STATUS_MIGRATION_REQUIRED):
        return EXIT_LAYOUT
    return EXIT_OK


def _cmd_check(args: argparse.Namespace) -> int:
    report = inspect_project(pathlib.Path(args.project))
    status = report["runtime_status"]
    if status in (RUNTIME_STATUS_AMBIGUOUS, RUNTIME_STATUS_INVALID,
                  RUNTIME_STATUS_MIGRATION_REQUIRED):
        print(f"[FAIL] {status}: {report['runtime_reason']}", file=sys.stderr)
        if status == RUNTIME_STATUS_MIGRATION_REQUIRED:
            print("[hint] python3 scripts/migrate_project_root.py inspect "
                  "--project <project>", file=sys.stderr)
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
