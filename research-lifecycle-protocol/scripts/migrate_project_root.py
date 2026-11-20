#!/usr/bin/env python3
"""migrate_project_root.py — safe control-root migration for RLP projects (v2.1.1).

Migrates a project's machine control plane from the legacy
``.research-idea-pipeline/`` root to the only runtime root
``.research-lifecycle-protocol/``. This is control-plane maintenance, not research:
it must never change scientific facts, evidence qualification, experiment history,
failure knowledge, budgets or decision history, and it never re-bootstraps.

Command matrix (default behaviour is read-only):

    python3 scripts/migrate_project_root.py inspect --project <project>
    python3 scripts/migrate_project_root.py plan    --project <project> --backup-root <dir>
    python3 scripts/migrate_project_root.py migrate --project <project> --backup-root <dir> [--apply]
    python3 scripts/migrate_project_root.py verify  --project <project> [--migration-id <id>]
    python3 scripts/migrate_project_root.py rollback --project <project> --migration-id <id>
    python3 scripts/migrate_project_root.py recover --project <project> [--apply]

Transaction and recovery states (journal):

    started → backup_verified → staged_verified → cutover_started
    → new_root_installed → legacy_archived → documents_committed → verified

Every state has a defined set of on-disk facts it implies (which roots exist) and a
defined recovery action; see ``_recovery_action``.

Guarantees (v2.1.1):

* **Cooperative maintenance lock** (``.rlp-migration/control.lock``, ``flock``) is held
  exclusively for the whole transaction; RLP write entries hold it shared and refuse
  writes while a migration runs. External writers that do not take this lock are NOT
  excluded — a migration cannot prove their quiescence and says so.
* **Source stability**: the legacy root is snapshotted (type / size / SHA-256 / symlink
  target) before the backup, after the backup, after staging and immediately before the
  cutover. Any change aborts with ``SOURCE_CHANGED_DURING_MIGRATION`` and preserves
  both roots and the backup.
* **Full durable manifest**: the post-cutover control root is recorded file-by-file.
  ``rollback`` compares that manifest, so a changed Scheduler, an appended TAG event, a
  new receipt or a deleted file refuses the rollback (``ROLLBACK_REFUSED_NEW_WORK``) —
  not just a changed ``research-state.json``.
* **Document rewrite transaction**: project-level documents are never modified before
  the cutover; rewritten bytes are staged, then committed one by one with atomic
  replace after the control root is installed, journalled per file and restorable.
* **Backup boundary**: the backup root may not sit inside the source or target control
  roots; symlinks are copied as links and never followed out of the root.
* **Fail closed**: a corrupt journal is ``JOURNAL_CORRUPT``; an unclassifiable state is
  ``manual``; nothing is auto-deleted without a proven-safe condition.

Only one control root may be a runtime root. A legacy root is a migration source and a
disaster-recovery archive, never a normal execution root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sys
import time
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import cognition as cg
import rlp_paths as rlp

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_HARD = 3
EXIT_ENV = 4

JOURNAL_SCHEMA = "research-idea-pipeline/migration-journal@2"
REPORT_SCHEMA = "research-idea-pipeline/migration-report@2"
MANIFEST_SCHEMA = "research-idea-pipeline/migration-manifest@1"

#: Journal lifecycle. Each name is also the event name written to the journal.
STATE_STARTED = "started"
STATE_BACKUP_VERIFIED = "backup_verified"
STATE_STAGED_VERIFIED = "staged_verified"
STATE_CUTOVER_STARTED = "cutover_started"
STATE_NEW_ROOT_INSTALLED = "new_root_installed"
STATE_LEGACY_ARCHIVED = "legacy_archived"
STATE_DOCUMENTS_COMMITTED = "documents_committed"
STATE_VERIFIED = "verified"
STATE_SEQUENCE = (
    STATE_STARTED, STATE_BACKUP_VERIFIED, STATE_STAGED_VERIFIED,
    STATE_CUTOVER_STARTED, STATE_NEW_ROOT_INSTALLED, STATE_LEGACY_ARCHIVED,
    STATE_DOCUMENTS_COMMITTED, STATE_VERIFIED,
)
#: Terminal states that end a migration attempt (success or deliberate abort).
TERMINAL_STATES = frozenset({STATE_VERIFIED, "rolled_back", "aborted"})
#: Failure events. ``after_cutover`` failures leave the new root installed.
FAILURE_EVENTS = frozenset({
    "refused", "backup_failed", "backup_verify_failed", "staging_failed",
    "staging_verify_failed", "cutover_failed", "archive_rename_failed",
    "documents_commit_failed", "source_changed", "verify_failed",
})

#: Files whose *content* is historical evidence and must never be rewritten.
NEVER_REWRITE = (
    "research-state.json", "model-revisions.jsonl", "decision-trajectory.jsonl",
    "tag-events.jsonl", "scheduler.json",
)

#: 历史保留迁移模式：把「存储可搬运」与「科研规则合规」分开。
LEGACY_VIOLATION_MODE = "preserve_known_legacy_violations"

#: Project-level operational documents that MAY be rewritten with explicit opt-in.
REWRITABLE = ("AGENTS.md", "README.md", "INDEX.md", "STATUS.md")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _new_migration_id() -> str:
    return time.strftime("%Y%m%dT%H%M%S") + "-" + os.urandom(3).hex()


def _write_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def _atomic_write_bytes(path: pathlib.Path, payload: bytes) -> None:
    """Write one file through a same-directory temp file plus ``os.replace``."""
    tmp = path.with_name(f".{path.name}.rlp-tmp-{os.getpid()}")
    with tmp.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------

def migration_dir(project_root: pathlib.Path) -> pathlib.Path:
    return project_root / rlp.MAINTENANCE_DIR


def journal_path(project_root: pathlib.Path) -> pathlib.Path:
    return migration_dir(project_root) / "journal.jsonl"


def work_dir(project_root: pathlib.Path, migration_id: str) -> pathlib.Path:
    return migration_dir(project_root) / migration_id


def manifest_path(project_root: pathlib.Path, migration_id: str,
                  name: str = "durable-manifest.json") -> pathlib.Path:
    return work_dir(project_root, migration_id) / name


def _journal_append(project: pathlib.Path, entry: Dict[str, Any]) -> None:
    path = journal_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"_schema": JOURNAL_SCHEMA, "ts": _now(), **entry}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _journal_read(project: pathlib.Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Read the journal. A malformed line is a hard problem, never silently skipped."""
    path = journal_path(project)
    if not path.is_file():
        return [], []
    entries: List[Dict[str, Any]] = []
    problems: List[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return [], [f"journal 不可读：{exc}"]
    for index, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"第 {index} 行不是合法 JSON：{exc}")
            continue
        if not isinstance(record, dict) or not record.get("migration_id"):
            problems.append(f"第 {index} 行缺少 migration_id")
            continue
        entries.append(record)
    return entries, problems


def attempts(project: pathlib.Path) -> List[Dict[str, Any]]:
    """Every migration attempt in journal order, grouped by migration id.

    ``refused`` entries are recorded without any lifecycle step. They are kept (an audit
    trail of who tried what) but must never become "the latest attempt": doing so would
    hide a real interrupted migration from ``recover`` and make
    ``_completed_migration`` forget an already verified one.
    """
    entries, _problems = _journal_read(project)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for entry in entries:
        origin = entry["migration_id"]
        if origin not in grouped:
            grouped[origin] = []
            order.append(origin)
        grouped[origin].append(entry)
    result: List[Dict[str, Any]] = []
    for origin in order:
        events = _events(grouped[origin])
        result.append({
            "migration_id": origin,
            "events": events,
            "last_event": events[-1] if events else None,
            "lifecycle": [e for e in events if e in STATE_SEQUENCE],
            "entries": grouped[origin],
            "refused_only": not any(e in STATE_SEQUENCE for e in events),
        })
    return result


def journal_state(project: pathlib.Path) -> Dict[str, Any]:
    """The latest *lifecycle* migration attempt and its last recorded event."""
    entries, problems = _journal_read(project)
    if problems:
        return {"status": "JOURNAL_CORRUPT", "problems": problems,
                "migration_id": None, "last_event": None, "entries": [],
                "attempts": [], "refused_attempts": []}
    if not entries:
        return {"status": "EMPTY", "problems": [], "migration_id": None,
                "last_event": None, "entries": [], "attempts": [],
                "refused_attempts": []}
    all_attempts = attempts(project)
    refused = [a["migration_id"] for a in all_attempts if a["refused_only"]]
    live = [a for a in all_attempts if not a["refused_only"]]
    if not live:
        return {"status": "EMPTY", "problems": [], "migration_id": None,
                "last_event": None, "entries": [], "attempts": all_attempts,
                "refused_attempts": refused}
    latest = live[-1]
    return {"status": "OK", "problems": [], "migration_id": latest["migration_id"],
            "last_event": latest["last_event"], "entries": latest["entries"],
            "attempts": all_attempts, "refused_attempts": refused}


def _events(entries: Sequence[Dict[str, Any]]) -> List[str]:
    return [str(e.get("event")) for e in entries]


def _state_rank(event: Optional[str]) -> int:
    if event in STATE_SEQUENCE:
        return STATE_SEQUENCE.index(event)
    return -1


def _last_known_state(entries: Sequence[Dict[str, Any]]) -> Optional[str]:
    """The furthest lifecycle state reached by this migration attempt."""
    best: Optional[str] = None
    for event in _events(entries):
        if event in STATE_SEQUENCE:
            if best is None or _state_rank(event) > _state_rank(best):
                best = event
    return best


def _completed_migration(project: pathlib.Path) -> Optional[str]:
    """The migration id of the last successfully verified migration, if any."""
    entries, problems = _journal_read(project)
    if problems:
        return None
    for entry in reversed(entries):
        if entry.get("event") == STATE_VERIFIED:
            return entry["migration_id"]
    return None


# ---------------------------------------------------------------------------
# Snapshots / durable manifests
# ---------------------------------------------------------------------------

def _walk(root: pathlib.Path, unreadable: Optional[List[Dict[str, str]]] = None
          ) -> Iterator[Tuple[pathlib.Path, str]]:
    """Walk a tree without following symlinks. Yields (path, kind).

    A directory that cannot be listed is **recorded** in ``unreadable`` instead of being
    skipped silently: an incomplete snapshot that reports itself complete would let a
    migration cut over with data missing from the active root and still verify ``ok``.
    """
    if not root.is_dir():
        return
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(os.scandir(current), key=lambda e: e.name)
        except OSError as exc:
            if unreadable is not None:
                try:
                    rel = str(current.relative_to(root))
                except ValueError:
                    rel = str(current)
                unreadable.append({"path": rel or ".", "error": f"{type(exc).__name__}: {exc}"})
            continue
        for entry in entries:
            path = pathlib.Path(entry.path)
            if entry.is_symlink():
                yield path, "symlink"
            elif entry.is_dir(follow_symlinks=False):
                yield path, "dir"
                stack.append(path)
            elif entry.is_file(follow_symlinks=False):
                yield path, "file"
            else:
                yield path, "other"


def snapshot(root: pathlib.Path) -> Dict[str, Any]:
    """A complete, symlink-safe snapshot of one control root.

    Entries record type, size, SHA-256 (files only), symlink target, permission mode
    and whether a symlink escapes the root. The aggregate digest covers every entry,
    so a changed byte, a new file, a deletion, a type change or a retargeted link all
    change the digest.
    """
    root = root.expanduser().resolve()
    entries: List[Dict[str, Any]] = []
    unreadable: List[Dict[str, str]] = []
    for path, kind in _walk(root, unreadable):
        rel = str(path.relative_to(root))
        record: Dict[str, Any] = {"path": rel, "type": kind}
        try:
            stat = path.lstat()
            record["mode"] = oct(stat.st_mode & 0o777)
        except OSError as exc:
            record["error"] = f"lstat: {exc}"
            entries.append(record)
            continue
        if kind == "symlink":
            target = os.readlink(path)
            record["symlink"] = target
            try:
                record["symlink_escapes_root"] = not pathlib.Path(
                    os.path.realpath(path)).is_relative_to(root)
            except (OSError, ValueError):
                record["symlink_escapes_root"] = True
        elif kind == "file":
            try:
                record["size"] = stat.st_size
                record["sha256"] = _sha256(path)
            except OSError as exc:
                record["error"] = f"read: {exc}"
        elif kind == "other":
            record["size"] = stat.st_size
        entries.append(record)
    entries.sort(key=lambda item: item["path"])
    digest = _sha256_bytes(json.dumps({"entries": entries, "unreadable": unreadable},
                                      ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return {"root": str(root), "digest": digest, "entry_count": len(entries),
            "entries": entries, "unreadable": unreadable,
            "complete": not unreadable}


def _snapshot_index(value: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {entry["path"]: entry for entry in value.get("entries", [])}


def compare_snapshots(before: Dict[str, Any], after: Dict[str, Any]
                      ) -> List[Dict[str, str]]:
    """Differences between two snapshots: added / removed / changed / type / link."""
    left, right = _snapshot_index(before), _snapshot_index(after)
    differences: List[Dict[str, str]] = []
    for path in sorted(set(left) | set(right)):
        one, two = left.get(path), right.get(path)
        if one is None:
            differences.append({"path": path, "change": "added",
                                "detail": "快照后有新文件"})
            continue
        if two is None:
            differences.append({"path": path, "change": "removed",
                                "detail": "快照后文件被删除"})
            continue
        if one.get("type") != two.get("type"):
            differences.append({"path": path, "change": "type",
                                "detail": f"{one.get('type')} → {two.get('type')}"})
            continue
        if one.get("type") == "symlink" and one.get("symlink") != two.get("symlink"):
            differences.append({"path": path, "change": "symlink",
                                "detail": f"{one.get('symlink')} → {two.get('symlink')}"})
            continue
        if one.get("type") == "file" and (one.get("size") != two.get("size")
                                          or one.get("sha256") != two.get("sha256")):
            differences.append({"path": path, "change": "modified",
                                "detail": f"{one.get('sha256', '')[:12]} → "
                                          f"{two.get('sha256', '')[:12]}"})
            continue
        if one.get("type") == "other" and one.get("size") != two.get("size"):
            differences.append({"path": path, "change": "modified",
                                "detail": "特殊文件大小变化"})
    return differences


def _save_manifest(project: pathlib.Path, migration_id: str, name: str,
                   value: Dict[str, Any]) -> Dict[str, str]:
    path = manifest_path(project, migration_id, name)
    _write_json(path, value)
    return {"path": str(path), "digest": _sha256(path),
            "entry_count": value.get("entry_count")}


def _load_manifest(path: pathlib.Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _evidence(path: pathlib.Path) -> Tuple[str, Optional[Dict[str, Any]]]:
    """迁移证明材料的三种状态：``ok`` / ``missing`` / ``corrupt``。

    ``verify`` 不能用「读不到就跳过这项比对」的方式通过：那样删掉一份证明材料
    就能让一份不完整的验证看起来完整。
    """
    if not path.is_file():
        return "missing", None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return "corrupt", None
    if not isinstance(value, dict):
        return "corrupt", None
    return "ok", value


# ---------------------------------------------------------------------------
# Semantic fingerprint (research assets that must not change)
# ---------------------------------------------------------------------------

def _chain_problems(root: pathlib.Path, route: str) -> List[str]:
    """Hash-chain integrity for one route (TAG events, decision trajectory)."""
    problems: List[str] = []
    route_dir = root / "routes" / route
    tag = route_dir / "domain" / "tag-events.jsonl"
    if tag.is_file():
        import domain_guard as dg
        _records, tag_problems = dg.load_events(route_dir)
        problems.extend(f"TAG：{item}" for item in tag_problems)
    trajectory = route_dir / "decision-trajectory.jsonl"
    if trajectory.is_file():
        import decision_trajectory as dt
        try:
            _records, diagnostics = dt.load_records(trajectory, tolerant=True)
            problems.extend(f"轨迹：{item.render()}" for item in diagnostics)
        except Exception as exc:  # noqa: BLE001 — 链损坏必须报出，不得静默
            problems.append(f"轨迹：{exc}")
    return problems


def _state_inventory(root: pathlib.Path) -> Dict[str, Any]:
    """把「存储坏了」与「科研规则违规」分开的逐路线清单。

    - ``fatal``：无法安全搬运的存储/结构问题（不可读、结构错误、形状门禁失败、哈希链损坏）。
    - ``scientific``：可读、可追溯，但违反当前科研规则（V1—V24 / EO1 / EX1）。
    - ``baseline``：每条路线的 state digest 与**逐条**违规记录，供迁移前后逐项比对。
    """
    import state_check as sc
    inventory: Dict[str, Any] = {"routes": {}, "fatal": [], "scientific": [],
                                 "baseline": {"routes": {}}}
    for state_path in _route_states(root):
        route = state_path.parent.name
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            inventory["fatal"].append({
                "route": route, "kind": "state_unreadable",
                "detail": f"{type(exc).__name__}: {exc}"})
            continue
        report = sc.check_state(state, source=str(state_path))
        if report.error is not None:
            inventory["fatal"].append({
                "route": route, "kind": "state_structure", "detail": str(report.error)})
            continue
        if report.shape:
            inventory["fatal"].append({
                "route": route, "kind": "shape_gate",
                "detail": "；".join(v.render() for v in report.shape[:5])})
            continue
        chain = _chain_problems(root, route)
        if chain:
            inventory["fatal"].append({
                "route": route, "kind": "hash_chain",
                "detail": "；".join(chain[:3])})
            continue
        violations = sorted(
            ({"rule": v.rule, "path": v.path, "detail": v.detail}
             for v in list(report.violations) + list(report.outcome)),
            key=lambda item: (item["rule"], item["path"], item["detail"]))
        inventory["routes"][route] = {
            "state_digest": cg.digest_of(state),
            "state_version": state.get("state_version"),
            "gate_ok": report.ok,
            "violation_count": len(violations),
            "rule_counts": _count_rules(violations),
            "violations": violations,
        }
        inventory["baseline"]["routes"][route] = {
            "state_digest": cg.digest_of(state),
            "state_version": state.get("state_version"),
            "violations": violations,
        }
        if violations:
            inventory["scientific"].append(route)
    return inventory


def _count_rules(violations: Sequence[Dict[str, str]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in violations:
        counts[item["rule"]] = counts.get(item["rule"], 0) + 1
    return dict(sorted(counts.items()))


def _route_states(root: pathlib.Path) -> List[pathlib.Path]:
    routes = root / "routes"
    if not routes.is_dir():
        return []
    return sorted(routes.glob("*/research-state.json"))


def _semantic_fingerprint(root: pathlib.Path) -> Dict[str, Any]:
    """Research-asset counts, state digests and budget records per route."""
    import state_check as sc
    fingerprint: Dict[str, Any] = {"routes": {}}
    for state_path in _route_states(root):
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            fingerprint["routes"][state_path.parent.name] = {"error": str(exc)}
            continue
        report = sc.check_state(state)
        collections = {key: len(state.get(key) or []) for key in
                       ("claims", "evidence", "assumptions", "hypotheses",
                        "experiments", "literature", "failures", "uncertainties",
                        "assurance", "repairs")}
        budgets = {}
        for experiment in state.get("experiments") or []:
            ledger = (experiment.get("execution_protocol") or {}).get("budget")
            if isinstance(ledger, dict):
                budgets[str(experiment.get("id"))] = ledger
        fingerprint["routes"][state_path.parent.name] = {
            "state_version": state.get("state_version"),
            "state_digest": cg.digest_of(state),
            "state_gate_ok": report.ok,
            "collections": collections,
            "budgets": budgets,
        }
    return fingerprint


def _path_dependencies(root: pathlib.Path, project_root: pathlib.Path
                       ) -> Dict[str, List[Dict[str, str]]]:
    """Classify legacy-root references: rewritable operational docs vs historical."""
    runtime_writable: List[Dict[str, str]] = []
    historical: List[Dict[str, str]] = []
    needle = rlp.LEGACY_STORAGE_ROOT
    for path, kind in _walk(root):
        if kind != "file":
            continue
        rel = str(path.relative_to(root))
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if needle not in text:
            continue
        entry = {"path": rel, "occurrences": str(text.count(needle))}
        name = pathlib.Path(rel).name
        if name in REWRITABLE:
            runtime_writable.append(entry)
        else:
            historical.append(entry)
    for name in REWRITABLE:
        candidate = project_root / name
        if candidate.is_file():
            try:
                text = candidate.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if needle in text:
                runtime_writable.append({"path": f"<project>/{name}",
                                         "occurrences": str(text.count(needle))})
    return {"runtime_writable": runtime_writable, "historical": historical}


# ---------------------------------------------------------------------------
# inspect / plan
# ---------------------------------------------------------------------------

def inspect(project_root: pathlib.Path) -> Dict[str, Any]:
    """Read-only preflight. Never writes and never acquires the lock."""
    project = pathlib.Path(project_root).expanduser().resolve()
    matrix = rlp.runtime_status(project)
    report: Dict[str, Any] = {"_schema": REPORT_SCHEMA, "command": "inspect",
                              "project_root": str(project), "status": matrix["status"],
                              "reason": matrix["reason"]}
    lock = rlp.maintenance_status(project)
    report["maintenance"] = {"held": lock["held"], "owner": lock["owner"],
                             "lock_path": lock["path"]}
    legacy = rlp.inspect_legacy_root(project)
    if legacy is not None:
        snap = snapshot(legacy.root)
        report["source_snapshot"] = {"digest": snap["digest"],
                                     "entry_count": snap["entry_count"],
                                     "symlink_escapes": [e["path"] for e in
                                                         snap["entries"]
                                                         if e.get("symlink_escapes_root")]}
        report["semantic_fingerprint"] = _semantic_fingerprint(legacy.root)
        report["path_dependencies"] = _path_dependencies(legacy.root, project)
    journal = journal_state(project)
    report["journal"] = {"status": journal["status"],
                         "migration_id": journal["migration_id"],
                         "last_event": journal["last_event"],
                         "problems": journal["problems"][:5]}
    report["writers_advisory"] = (
        "迁移要求所有写入者停止：科研会话、Research Loop、DSH Research Mesh、"
        "自动 Resume、GPU 实验执行器、结果收集、Evidence Outcome 写回、"
        "Scheduler/Strategy Memory 与后台监控。RLP 自身的写入入口受维护锁保护；"
        "外部写入者（Mesh worker、训练脚本、第三方插件）不获取该锁，工具无法证明它们静止。"
        "工具不会终止任何进程；无法确认静止时不要执行 --apply。")
    report["external_writers_unprotected"] = [
        "DSH Research Mesh worker（外部插件，不获取 RLP 维护锁）",
        "后台训练 / 结果收集进程（shell、SSH、notebook）",
        "第三方脚本对控制根的直接读写",
    ]
    return report


def _normalize_baseline(baseline: Any) -> Dict[str, Any]:
    """只保留判定所需的字段：state digest、state_version、逐条违规。"""
    routes: Dict[str, Any] = {}
    if isinstance(baseline, dict):
        for route, entry in (baseline.get("routes") or {}).items():
            if not isinstance(entry, dict):
                continue
            routes[str(route)] = {
                "state_digest": entry.get("state_digest"),
                "state_version": entry.get("state_version"),
                "violations": sorted(
                    ({"rule": str(v.get("rule")), "path": str(v.get("path")),
                      "detail": str(v.get("detail"))}
                     for v in entry.get("violations", []) if isinstance(v, dict)),
                    key=lambda item: (item["rule"], item["path"], item["detail"])),
            }
    return {"routes": routes}


def _baseline_diff(submitted: Any, current: Any) -> Dict[str, Any]:
    left, right = _normalize_baseline(submitted)["routes"],         _normalize_baseline(current)["routes"]
    diff: Dict[str, Any] = {"routes_added": [], "routes_removed": [], "changed": {}}
    for route in sorted(set(left) - set(right)):
        diff["routes_removed"].append(route)
    for route in sorted(set(right) - set(left)):
        diff["routes_added"].append(route)
    for route in sorted(set(left) & set(right)):
        if left[route] != right[route]:
            before = {(v["rule"], v["path"], v["detail"])
                      for v in left[route]["violations"]}
            after = {(v["rule"], v["path"], v["detail"])
                     for v in right[route]["violations"]}
            diff["changed"][route] = {
                "appeared": sorted(after - before)[:10],
                "disappeared": sorted(before - after)[:10],
                "state_digest_changed": left[route]["state_digest"]
                != right[route]["state_digest"]}
    return diff


def _baseline_digest(baseline: Dict[str, Any]) -> str:
    return _sha256_bytes(json.dumps(baseline, ensure_ascii=False,
                                    sort_keys=True).encode("utf-8"))


def _recognizable_legacy(snapshot_value: Dict[str, Any], legacy_root: pathlib.Path) -> bool:
    """旧根是否含有可识别的控制平面内容（至少一条路线 state，或 project/ 目录）。"""
    if (legacy_root / "project").is_dir():
        return True
    for entry in snapshot_value.get("entries", []):
        path = entry.get("path", "")
        if path.startswith("routes/") and path.endswith("/research-state.json"):
            return True
    return False


def _backup_destination(backup_root: pathlib.Path, project: pathlib.Path,
                        migration_id: str) -> pathlib.Path:
    return backup_root.expanduser().resolve() / (project.name or "project") / migration_id


def _boundary_errors(project: pathlib.Path, backup_root: pathlib.Path
                     ) -> List[str]:
    """The backup root must not be inside the control roots or the staging area."""
    problems: List[str] = []
    resolved = backup_root.expanduser().resolve()
    guarded = {
        "旧控制根": project / rlp.LEGACY_STORAGE_ROOT,
        "新控制根": project / rlp.STORAGE_ROOT,
        "迁移工作目录": migration_dir(project),
        "归档目录": project / ".rlp-archive",
    }
    for label, root in guarded.items():
        try:
            if resolved == root or resolved.is_relative_to(root):
                problems.append(f"备份根 {resolved} 位于{label} {root} 内部："
                                "会递归复制或破坏源数据")
        except ValueError:
            continue
    return problems


def plan(project_root: pathlib.Path, backup_root: pathlib.Path, *,
         preserve_known_legacy_violations: bool = False) -> Dict[str, Any]:
    """Read-only migration plan: id, snapshots, backup destination, rewrites.

    Storage integrity and scientific compliance are classified separately. A route whose
    state is readable and traceable but violates current research rules (for example an
    Outcome Policy frozen after the experiment) is a **scientific debt**, not a storage
    defect: it may be copied losslessly in the explicit
    ``preserve_known_legacy_violations`` mode, with its exact violation inventory bound
    to the plan. Structural or chain damage stays fatal in every mode.
    """
    project = pathlib.Path(project_root).expanduser().resolve()
    report = inspect(project)
    report["command"] = "plan"
    migration_id = _new_migration_id()
    destination = _backup_destination(backup_root, project, migration_id)
    report["migration_id"] = migration_id
    report["backup_destination"] = str(destination)
    report["staging_dir"] = str(work_dir(project, migration_id) / "staging")
    report["archive_name"] = f"{rlp.LEGACY_STORAGE_ROOT}.migrated-{migration_id}"
    if report["status"] != rlp.RUNTIME_STATUS_MIGRATION_REQUIRED:
        report["ready_to_migrate"] = False
        return report
    legacy = rlp.inspect_legacy_root(project)
    assert legacy is not None
    boundary = _boundary_errors(project, backup_root)
    if boundary:
        report["boundary_errors"] = boundary
        report["ready_to_migrate"] = False
        report["reason"] = "；".join(boundary)
        return report
    snapshot_value = snapshot(legacy.root)
    if not snapshot_value.get("complete", True):
        report["unreadable_paths"] = snapshot_value.get("unreadable", [])[:10]
        report["ready_to_migrate"] = False
        report["reason"] = ("旧控制根存在不可读目录，快照不完整：迁移会静默丢数据。"
                            "先修复权限或移出不可读内容，再重试")
        return report
    if not _recognizable_legacy(snapshot_value, legacy.root):
        report["ready_to_migrate"] = False
        report["reason"] = ("旧控制根为空或不含可识别的控制平面内容（无 routes/*/research-state.json，"
                            "也没有 project/）：这不构成可迁移的研究状态，拒绝迁移。"
                            "若这是新项目，请勿创建旧根")
        return report
    inventory = _state_inventory(legacy.root)
    report["route_inventory"] = {
        route: {key: value for key, value in entry.items() if key != "violations"}
        for route, entry in inventory["routes"].items()}
    if inventory["fatal"]:
        report["storage_blockers"] = inventory["fatal"]
        report["ready_to_migrate"] = False
        report["reason"] = ("旧控制根存在无法安全搬运的存储/结构问题："
                            + "；".join(f"{item['route']}({item['kind']})"
                                        for item in inventory["fatal"])
                            + "；这类问题不属于科研规则债务，必须先修复")
        return report
    if inventory["scientific"]:
        report["scientific_debt_routes"] = inventory["scientific"]
        report["scientific_debt"] = {
            route: {"violation_count": inventory["routes"][route]["violation_count"],
                    "rule_counts": inventory["routes"][route]["rule_counts"]}
            for route in inventory["scientific"]}
        if not preserve_known_legacy_violations:
            report["ready_to_migrate"] = False
            report["reason"] = ("旧控制根中存在未通过 state gate 的 Research State："
                                + "、".join(inventory["scientific"])
                                + "；严格模式拒绝迁移。若这些是历史科研规则债务、"
                                  "且要求逐条保留，请使用 "
                                  "--preserve-known-legacy-violations 并把本计划作为"
                                  " --violation-baseline 提交")
            return report
        report["preserve_known_legacy_violations"] = True
        report["violation_baseline"] = inventory["baseline"]
        report["violation_baseline_digest"] = _baseline_digest(inventory["baseline"])
        report["constraints"] = [
            "不合规的历史状态被原样保留，不补写预注册、不改 status、不改字段",
            "科研写入门禁不变：这些路线仍按原有规则 HOLD",
            "route-registry 不被自动改为 archived",
            "迁移只保证存储无损，不赋予任何历史记录新的证据资格",
        ]
    fingerprint = report.get("semantic_fingerprint", {})
    broken = []
    snapshot_value = snapshot(legacy.root)
    escaped = [e["path"] for e in snapshot_value["entries"]
               if e.get("symlink_escapes_root")]
    if escaped:
        report["symlink_escapes"] = escaped
    # 磁盘：staging 在项目文件系统，备份在 backup_root 的文件系统；两者可能不同盘，
    # 只查项目盘会让「备份盘已满」通过预检，然后在事务中途失败。
    needed = sum(e.get("size", 0) for e in snapshot_value["entries"]
                 if e.get("type") == "file")
    staging_free = shutil.disk_usage(project).free
    backup_parent = _backup_destination(backup_root, project, migration_id).parent
    probe = backup_parent
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    if not probe.exists():
        probe = project
    try:
        backup_free = shutil.disk_usage(probe).free
    except OSError:
        backup_free = 0
    report["disk"] = {
        "estimated_need_bytes": needed,
        "project_free_bytes": staging_free,
        "backup_free_bytes": backup_free,
        "staging_sufficient": staging_free > needed,
        "backup_sufficient": backup_free > needed,
        "sufficient": staging_free > needed and backup_free > needed,
        "note": "staging 与备份分别占用项目盘与备份盘；两处都要有余量",
    }
    report["proposed_rewrites"] = report.get("path_dependencies", {}).get(
        "runtime_writable", [])
    report["rewrite_policy"] = (
        "默认不重写任何文件内容。--rewrite 仅重写显式列出的项目级/路线级运行时文档"
        "（AGENTS/README/INDEX/STATUS）；改写发生在控制根切换成功之后，"
        "逐文件原子替换并写入 journal，失败可按 manifest 恢复原字节。"
        "冻结预注册、证据、事件链等历史记录永不重写。")
    report["ready_to_migrate"] = bool(report["disk"]["sufficient"])
    return report


# ---------------------------------------------------------------------------
# Backup / staging copies
# ---------------------------------------------------------------------------

def _copy_tree(source: pathlib.Path, destination: pathlib.Path
               ) -> Tuple[List[str], List[str]]:
    """Copy a tree with type fidelity; never follow symlinks out of the root.

    Returns (problems, warnings). ``problems`` are hard failures that must abort;
    ``warnings`` are risks worth reporting (e.g. a symlink leaving the root).
    """
    problems: List[str] = []
    warnings: List[str] = []
    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return [f"无法创建目标目录：{exc}"], warnings
    unreadable: List[Dict[str, str]] = []
    for path, kind in _walk(source, unreadable):
        rel = path.relative_to(source)
        target = destination / rel
        try:
            if kind == "dir":
                target.mkdir(parents=True, exist_ok=True)
                continue
            if kind == "symlink":
                link = os.readlink(path)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(link, target)
                try:
                    escapes = not pathlib.Path(os.path.realpath(path)).is_relative_to(
                        source.resolve())
                except (OSError, ValueError):
                    escapes = True
                if escapes:
                    warnings.append(f"{rel}: 符号链接指向控制根之外（{link}），"
                                    "已按链接复制，未读取目标内容")
                continue
            if kind == "other":
                problems.append(f"{rel}: 不支持的特殊文件类型（fifo/socket/device），"
                                "无法校验，拒绝迁移")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        except OSError as exc:
            problems.append(f"{rel}: 复制失败（{type(exc).__name__}: {exc}）")
    for item in unreadable:
        problems.append(f"{item['path']}: 目录不可读，无法复制或校验（{item['error']}）")
    # item-by-item verification of the copy
    source_snap = snapshot(source)
    for item in source_snap.get("unreadable", []):
        problems.append(f"{item['path']}: 快照时目录不可读（{item['error']}）")
    target_snap = snapshot(destination)
    for difference in compare_snapshots(source_snap, target_snap):
        problems.append(f"{difference['path']}: 副本校验不一致（{difference['change']}）")
    return problems, warnings


def _backup_report(manifest_value: Dict[str, Any], destination: pathlib.Path
                   ) -> List[str]:
    problems: List[str] = []
    index = _snapshot_index(manifest_value)
    actual = snapshot(destination)
    for difference in compare_snapshots(manifest_value, actual):
        problems.append(f"备份 {difference['path']}: {difference['change']} "
                        f"({difference['detail']})")
    if not index and actual["entry_count"]:
        problems.append("备份清单为空但目标目录有内容")
    return problems


# ---------------------------------------------------------------------------
# Document rewrite staging (committed only after the cutover)
# ---------------------------------------------------------------------------

def _stage_document_rewrites(project: pathlib.Path, legacy: pathlib.Path,
                             staging_target: pathlib.Path,
                             rewrite_set: Sequence[str],
                             migration_id: str) -> Dict[str, Any]:
    """Prepare rewritten bytes + original bytes; write nothing into the project."""
    prepared: List[Dict[str, Any]] = []
    ignored: List[Dict[str, str]] = []
    originals_dir = work_dir(project, migration_id) / "rewrite-originals"
    staged_dir = work_dir(project, migration_id) / "project-docs"
    needle = rlp.LEGACY_STORAGE_ROOT.encode("utf-8")
    for raw in rewrite_set:
        rel = str(raw).strip()
        if not rel:
            continue
        name = pathlib.Path(rel).name
        if name not in REWRITABLE:
            ignored.append({"label": rel,
                            "reason": "不是可重写的运行时文档；历史证据不得改写"})
            continue
        if rel.startswith("<project>/"):
            candidate = project / name
            label = f"<project>/{name}"
            inside_root = False
        else:
            candidate = legacy / rel
            label = rel
            inside_root = True
            if not candidate.is_file():
                # a project-level document (README/AGENTS/...) passed by bare name
                project_candidate = project / name
                if project_candidate.is_file():
                    candidate = project_candidate
                    label = f"<project>/{name}"
                    inside_root = False
        if not candidate.is_file():
            ignored.append({"label": rel, "reason": "文件不存在"})
            continue
        original = candidate.read_bytes()
        occurrences = original.count(needle)
        if occurrences == 0:
            ignored.append({"label": rel, "reason": "文件里没有旧控制根引用"})
            continue
        rewritten = original.replace(needle, rlp.STORAGE_ROOT.encode("utf-8"))
        originals_dir.mkdir(parents=True, exist_ok=True)
        safe = label.replace("/", "__")
        (originals_dir / f"{safe}.orig").write_bytes(original)
        if inside_root:
            # the staging tree is a private copy: rewriting it there is safe and keeps
            # the project root untouched until after the cutover
            staged_target_file = staging_target / rel
            staged_target_file.parent.mkdir(parents=True, exist_ok=True)
            staged_target_file.write_bytes(rewritten)
        else:
            staged_dir.mkdir(parents=True, exist_ok=True)
            (staged_dir / name).write_bytes(rewritten)
        prepared.append({
            "label": label, "name": name, "inside_root": inside_root,
            "original_sha256": _sha256_bytes(original),
            "rewritten_sha256": _sha256_bytes(rewritten),
            "occurrences": occurrences,
            "original_path": str(originals_dir / f"{safe}.orig"),
            "staged_path": (str(staged_dir / name) if not inside_root else None),
        })
    manifest = {"schema": MANIFEST_SCHEMA, "migration_id": migration_id,
                "files": prepared, "ignored": ignored}
    _write_json(work_dir(project, migration_id) / "rewrite-manifest.json", manifest)
    return manifest


def _rewrite_manifest(project: pathlib.Path, migration_id: str
                      ) -> Optional[Dict[str, Any]]:
    return _load_manifest(work_dir(project, migration_id) / "rewrite-manifest.json")


def _commit_documents(project: pathlib.Path, migration_id: str
                      ) -> Tuple[List[str], List[str]]:
    """Commit project-level rewrites one file at a time, journalling each.

    Returns (committed_labels, problems). On a mid-way failure the already committed
    files are restored from their recorded originals, so a partial commit never leaves
    a mixed project.
    """
    manifest = _rewrite_manifest(project, migration_id) or {}
    files = [f for f in manifest.get("files", []) if not f.get("inside_root")]
    if not files:
        return [], []
    _journal_append(project, {"event": "documents_commit_started",
                              "migration_id": migration_id, "files": len(files)})
    committed: List[str] = []
    problems: List[str] = []
    try:
        for item in files:
            target = project / item["name"]
            payload = pathlib.Path(item["staged_path"]).read_bytes()
            if _sha256_bytes(payload) != item["rewritten_sha256"]:
                problems.append(f"{item['label']}: 暂存文档摘要不一致")
                raise OSError("staged document digest mismatch")
            _atomic_write_bytes(target, payload)
            committed.append(item["label"])
            _journal_append(project, {"event": "document_committed",
                                      "migration_id": migration_id,
                                      "file": item["label"],
                                      "sha256": item["rewritten_sha256"]})
    except (OSError, KeyError) as exc:
        problems.append(f"文档提交失败（{type(exc).__name__}: {exc}）")
        restored = _restore_documents(project, migration_id)
        _journal_append(project, {"event": "documents_commit_failed",
                                  "migration_id": migration_id,
                                  "problems": problems[:3],
                                  "restored": restored})
        return committed, problems
    return committed, problems


def _restore_documents(project: pathlib.Path, migration_id: str
                       ) -> List[str]:
    """Restore project-level documents from their recorded original bytes."""
    manifest = _rewrite_manifest(project, migration_id) or {}
    restored: List[str] = []
    for item in manifest.get("files", []):
        if item.get("inside_root"):
            continue
        original = pathlib.Path(item["original_path"])
        if not original.is_file():
            continue
        payload = original.read_bytes()
        if _sha256_bytes(payload) != item["original_sha256"]:
            continue
        _atomic_write_bytes(project / item["name"], payload)
        restored.append(item["label"])
    return restored


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------

def migrate(project_root: pathlib.Path, backup_root: pathlib.Path, *,
            apply: bool = False, rewrite: Sequence[str] = (),
            assume_writers_quiesced: bool = False,
            preserve_known_legacy_violations: bool = False,
            violation_baseline: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run the migration transaction. Without ``apply`` this is plan-only.

    ``assume_writers_quiesced`` is the operator's explicit confirmation that external
    writers (Mesh workers, training jobs, third-party scripts) are stopped. Without it
    ``--apply`` refuses, because the maintenance lock only covers RLP's own entries.

    ``preserve_known_legacy_violations`` moves history that is readable but violates
    current research rules. It is not a ``--force``: the caller must supply the
    ``violation_baseline`` reviewed in the plan, the baseline must still match exactly,
    and the result is reported as ``VERIFIED_WITH_LEGACY_ISSUES`` — never as a clean
    scientific verification.
    """
    project = pathlib.Path(project_root).expanduser().resolve()
    plan_report = plan(project, backup_root,
                       preserve_known_legacy_violations=preserve_known_legacy_violations)
    report: Dict[str, Any] = {"_schema": REPORT_SCHEMA, "command": "migrate",
                              "project_root": str(project),
                              "migration_id": plan_report.get("migration_id"),
                              "status": plan_report["status"], "applied": False}
    if plan_report["status"] == rlp.RUNTIME_STATUS_READY:
        report.update({"status": "ALREADY_MIGRATED", "applied": False,
                       "idempotent": True,
                       "previous_migration_id": _completed_migration(project),
                       "detail": "项目已在新根上运行；再次执行为幂等 no-op"})
        return report
    if plan_report["status"] != rlp.RUNTIME_STATUS_MIGRATION_REQUIRED:
        report["errors"] = [f"当前状态 {plan_report['status']} 不可迁移："
                            f"{plan_report['reason']}"]
        report["status"] = "REFUSED"
        return report
    if preserve_known_legacy_violations:
        expected = plan_report.get("violation_baseline")
        if expected is None:
            report["errors"] = ["旧控制根没有科研规则债务；不要在有债务时才需要的模式下迁移"]
            report["status"] = "REFUSED"
            return report
        if violation_baseline is None:
            report["errors"] = [
                "preserve_known_legacy_violations 必须绑定迁移前的违规清单："
                "把 plan 输出中的 violation_baseline 原样提交为 --violation-baseline 文件。"
                "不接受通用 --force，也不接受只给数量"]
            report["status"] = "REFUSED"
            return report
        if _normalize_baseline(violation_baseline) != _normalize_baseline(expected):
            report["errors"] = [
                "违规基线已变化：提交的清单与当前旧控制根不一致。"
                "重新运行 plan、重新审阅，再迁移（不得沿用旧基线）",
                "submitted_digest=" + _baseline_digest(violation_baseline),
                "current_digest=" + _baseline_digest(expected)]
            report["diff"] = _baseline_diff(violation_baseline, expected)
            report["status"] = "REFUSED"
            return report
    if not plan_report.get("ready_to_migrate"):
        report["errors"] = ([plan_report.get("reason")] if plan_report.get("reason")
                            else ["磁盘空间不足或预检失败：需要约两倍控制根体积的可用空间"])
        report["status"] = "REFUSED"
        return report
    if not apply:
        report["detail"] = ("plan-only（未加 --apply）；备份与切换都不会发生。"
                            "执行前须停止所有写入者，并在 --apply 时加 "
                            "--assume-writers-quiesced 确认。")
        return report
    if not assume_writers_quiesced:
        report["errors"] = [
            "拒绝无人值守迁移：维护锁只覆盖 RLP 自身写入入口，无法证明外部写入者"
            "（Mesh worker/训练脚本/第三方插件）已停止。确认后加 "
            "--assume-writers-quiesced 重新执行。"]
        report["status"] = "REFUSED"
        return report

    migration_id = plan_report["migration_id"]
    legacy = rlp.inspect_legacy_root(project)
    assert legacy is not None
    backup_dir = pathlib.Path(plan_report["backup_destination"])
    if backup_dir.exists() and any(backup_dir.iterdir()):
        report["errors"] = [f"备份目的地已存在且非空：{backup_dir}；不覆盖已有备份"]
        report["status"] = "REFUSED"
        return report

    try:
        with rlp.maintenance_exclusive(project, owner={"migration_id": migration_id,
                                                       "command": "migrate"}):
            return _migrate_transaction(project, legacy, backup_dir, migration_id,
                                        plan_report, rewrite, report,
                                        preserve_known_legacy_violations=(
                                            preserve_known_legacy_violations))
    except rlp.MaintenanceInProgress as exc:
        report["errors"] = [str(exc)]
        report["status"] = "REFUSED"
        _journal_append(project, {"event": "refused", "migration_id": migration_id,
                                  "problems": [str(exc)]})
        return report


def _migrate_transaction(project: pathlib.Path, legacy: rlp.StorageRoot,
                         backup_dir: pathlib.Path, migration_id: str,
                         plan_report: Dict[str, Any], rewrite: Sequence[str],
                         report: Dict[str, Any], *,
                         preserve_known_legacy_violations: bool = False) -> Dict[str, Any]:
    work = work_dir(project, migration_id)
    work.mkdir(parents=True, exist_ok=True)
    source_before = snapshot(legacy.root)
    baseline = plan_report.get("violation_baseline") if preserve_known_legacy_violations \
        else None
    _journal_append(project, {"event": STATE_STARTED, "migration_id": migration_id,
                              "backup": str(backup_dir),
                              "source_digest": source_before["digest"],
                              "source_entry_count": source_before["entry_count"],
                              "mode": (LEGACY_VIOLATION_MODE
                                       if preserve_known_legacy_violations else "strict"),
                              "violation_baseline_digest": (
                                  _baseline_digest(baseline) if baseline else None)})
    if baseline is not None:
        _write_json(manifest_path(project, migration_id, "violation-baseline.json"),
                    {"baseline": baseline,
                     "digest": _baseline_digest(baseline),
                     "mode": LEGACY_VIOLATION_MODE})
        _journal_append(project, {"event": "legacy_violations_accepted",
                                  "migration_id": migration_id,
                                  "digest": _baseline_digest(baseline),
                                  "routes": sorted((baseline.get("routes") or {}).keys()),
                                  "violation_count": sum(
                                      len(entry.get("violations", []))
                                      for entry in (baseline.get("routes") or {}).values())})
    _save_manifest(project, migration_id, "source-snapshot.json", source_before)
    _write_json(manifest_path(project, migration_id, "source-fingerprint.json"),
                plan_report.get("semantic_fingerprint", {}))

    # 1) verified external backup
    backup_target = backup_dir / "legacy-root"
    problems, warnings = _copy_tree(legacy.root, backup_target)
    if problems:
        return _fail(project, report, migration_id, "FAILED_BACKUP", "backup_failed",
                     ["备份失败，未发生任何切换："] + problems[:5])
    backup_snapshot = snapshot(backup_target)
    backup_problems = compare_snapshots(source_before, backup_snapshot)
    if backup_problems:
        return _fail(project, report, migration_id, "FAILED_BACKUP",
                     "backup_verify_failed",
                     ["备份验证失败，未发生任何切换："])
    # source stability after the backup
    source_after_backup = snapshot(legacy.root)
    changed = compare_snapshots(source_before, source_after_backup)
    if changed:
        return _fail(project, report, migration_id, "SOURCE_CHANGED_DURING_MIGRATION",
                     "source_changed",
                     ["备份期间旧控制根发生变化："] +
                     [f"{d['path']}({d['change']})" for d in changed[:5]])
    _save_manifest(project, migration_id, "backup-manifest.json", backup_snapshot)
    _journal_append(project, {"event": STATE_BACKUP_VERIFIED,
                              "migration_id": migration_id,
                              "entries": backup_snapshot["entry_count"],
                              "digest": backup_snapshot["digest"],
                              "warnings": warnings[:5]})

    # 2) private staging copy inside the project (same filesystem)
    staging_root = work / "staging"
    if staging_root.exists():
        shutil.rmtree(staging_root)
    staging_root.mkdir(parents=True)
    staging_target = staging_root / rlp.STORAGE_ROOT
    problems, staging_warnings = _copy_tree(legacy.root, staging_target)
    if problems:
        return _fail(project, report, migration_id, "FAILED_STAGING", "staging_failed",
                     ["staging 复制失败："] + problems[:5])
    source_after_staging = snapshot(legacy.root)
    changed = compare_snapshots(source_before, source_after_staging)
    if changed:
        return _fail(project, report, migration_id, "SOURCE_CHANGED_DURING_MIGRATION",
                     "source_changed",
                     ["staging 期间旧控制根发生变化："] +
                     [f"{d['path']}({d['change']})" for d in changed[:5]])

    # 3) document rewrites: staged, never applied before the cutover
    if rewrite:
        rewrite_manifest = _stage_document_rewrites(project, legacy.root, staging_target,
                                                    rewrite, migration_id)
    else:
        rewrite_manifest = {"schema": MANIFEST_SCHEMA, "migration_id": migration_id,
                            "files": [], "ignored": []}
        _write_json(work_dir(project, migration_id) / "rewrite-manifest.json",
                    rewrite_manifest)
    _journal_append(project, {"event": STATE_STAGED_VERIFIED,
                              "migration_id": migration_id,
                              "entries": snapshot(staging_target)["entry_count"],
                              "rewrites": len(rewrite_manifest["files"])})

    # 4) staged verification against the recorded source snapshot (modulo rewrites)
    staged_snapshot = snapshot(staging_target)
    expected = source_before
    differences = compare_snapshots(expected, staged_snapshot)
    allowed = {f["label"] for f in rewrite_manifest["files"] if f["inside_root"]}
    unexpected = [d for d in differences
                  if not any(a and (d["path"] == a or d["path"].endswith("/" + a))
                             for a in allowed)]
    if unexpected:
        return _fail(project, report, migration_id, "FAILED_STAGING_VERIFY",
                     "staging_verify_failed",
                     ["staging 校验失败：与源快照不一致，未发生切换"] +
                     [f"{d['path']}({d['change']})" for d in unexpected[:5]])
    staged_fp = _semantic_fingerprint(staging_target)
    legacy_fp = plan_report.get("semantic_fingerprint", {})
    if staged_fp != legacy_fp:
        return _fail(project, report, migration_id, "FAILED_STAGING_VERIFY",
                     "staging_verify_failed",
                     ["staging 校验失败：科研资产指纹与源不一致，未发生切换"])
    if baseline is not None:
        staged_baseline = _state_inventory(staging_target)["baseline"]
        if _normalize_baseline(staged_baseline) != _normalize_baseline(baseline):
            return _fail(project, report, migration_id, "FAILED_STAGING_VERIFY",
                         "staging_verify_failed",
                         ["staging 校验失败：违规清单与迁移前基线不一致（被删除、掩盖或新增），"
                          "未发生切换"],
                         extra={"baseline_diff": _baseline_diff(baseline, staged_baseline)})

    # 5) final source-stability check immediately before the cutover
    source_at_cutover = snapshot(legacy.root)
    changed = compare_snapshots(source_before, source_at_cutover)
    if changed:
        return _fail(project, report, migration_id, "SOURCE_CHANGED_DURING_MIGRATION",
                     "source_changed",
                     ["切换前旧控制根发生变化（可能仍有写入者）："] +
                     [f"{d['path']}({d['change']})" for d in changed[:5]])
    _journal_append(project, {"event": STATE_CUTOVER_STARTED,
                              "migration_id": migration_id,
                              "source_digest": source_at_cutover["digest"]})

    # 6) install the new root (one atomic rename), then retire the legacy root
    target_root = project / rlp.STORAGE_ROOT
    try:
        os.rename(staging_target, target_root)
    except OSError as exc:
        return _fail(project, report, migration_id, "FAILED_CUTOVER", "cutover_failed",
                     [f"切换失败（未丢失数据，staging 保留）：{exc}"])
    installed = snapshot(target_root)
    _save_manifest(project, migration_id, "installed-manifest.json", installed)
    _journal_append(project, {"event": STATE_NEW_ROOT_INSTALLED,
                              "migration_id": migration_id,
                              "entries": installed["entry_count"],
                              "digest": installed["digest"]})

    archive_dir = project / ".rlp-archive" / migration_id
    archive_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.rename(legacy.root, archive_dir / "legacy-root")
    except OSError as exc:
        _journal_append(project, {"event": "archive_rename_failed",
                                  "migration_id": migration_id,
                                  "error": str(exc)})
        report["errors"] = [
            f"旧根归档失败：新根已安装，两个控制根暂同时存在（维护窗口中，"
            f"运行时 fail closed），需要 recover 完成或 rollback：{exc}"]
        report["status"] = "DUAL_ROOT_TRANSIENT"
        report["applied"] = True
        report["migration_id"] = migration_id
        report["recover_hint"] = (f"python3 scripts/migrate_project_root.py recover "
                                  f"--project {project} --apply")
        return report
    _journal_append(project, {"event": STATE_LEGACY_ARCHIVED,
                              "migration_id": migration_id,
                              "archive": str(archive_dir / "legacy-root")})

    # 7) commit project-level documents (after the control root is installed)
    committed, doc_problems = _commit_documents(project, migration_id)
    if doc_problems:
        report["errors"] = doc_problems
        report["status"] = "MIGRATED_DOCUMENTS_FAILED"
        report["applied"] = True
        report["migration_id"] = migration_id
        report["restored_documents"] = _restore_documents(project, migration_id)
        report["rollback_hint"] = (f"python3 scripts/migrate_project_root.py rollback "
                                   f"--project {project} --migration-id {migration_id}")
        return report
    _journal_append(project, {"event": STATE_DOCUMENTS_COMMITTED,
                              "migration_id": migration_id,
                              "committed": committed})

    # 8) post-migration verification against the recorded manifests
    verify_report = verify(project, migration_id=migration_id)
    report["verify"] = verify_report
    report["rewrites"] = rewrite_manifest["files"]
    if rewrite_manifest.get("ignored"):
        report["rewrites_ignored"] = rewrite_manifest["ignored"]
        report.setdefault("warnings", [])
        report["warnings"] = list(report["warnings"]) + [
            f"未重写 {item['label']}：{item['reason']}"
            for item in rewrite_manifest["ignored"][:5]]
    report["backup_destination"] = str(backup_dir)
    report["archive"] = str(archive_dir / "legacy-root")
    report["warnings"] = warnings[:10] + staging_warnings[:10]
    if verify_report["ok"]:
        legacy_issues = verify_report["status"] == "VERIFIED_WITH_LEGACY_ISSUES"
        _journal_append(project, {"event": STATE_VERIFIED,
                                  "migration_id": migration_id,
                                  "manifest_digest": verify_report.get(
                                      "recorded_manifest_digest"),
                                  "mode": report.get("mode", "strict"),
                                  "result": verify_report["status"],
                                  "legacy_violations_preserved":
                                      verify_report.get("legacy_violations_preserved"),
                                  "scientific_gate_ok":
                                      verify_report.get("scientific_gate_ok")})
        report.update({
            "status": ("MIGRATED_WITH_LEGACY_ISSUES" if legacy_issues else "MIGRATED"),
            "applied": True,
            "semantic_fingerprint": legacy_fp,
            "storage_migrated": True,
            "scientific_gate_ok": verify_report.get("scientific_gate_ok"),
            "legacy_violations_preserved": verify_report.get("legacy_violations_preserved"),
            "resume_hint": (
                ("存储迁移完成；历史科研规则债务逐条保留，相关路线继续按原有门禁 HOLD。"
                 "这不是科研合规证明。" if legacy_issues else
                 "迁移完成且校验通过；新根为唯一运行时控制根。")
                + "请保留 .rlp-archive/<id>（回滚所需的原始控制根）与 .rlp-migration/<id>"
                  "（本次校验的证明材料）；verify 依赖这些材料，缺失即判失败。"
                  "只有在明确决定不再回滚、并已另行备份之后，才由人手动删除。")})
        return report
    _journal_append(project, {"event": "verify_failed", "migration_id": migration_id,
                              "problems": verify_report["problems"][:5]})
    report.update({"status": "MIGRATED_VERIFY_FAILED", "applied": True,
                   "rollback_hint": (
                       f"python3 scripts/migrate_project_root.py rollback "
                       f"--project {project} --migration-id {migration_id}")})
    return report


def _fail(project: pathlib.Path, report: Dict[str, Any], migration_id: str,
          status: str, event: str, errors: List[str],
          extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _journal_append(project, {"event": event, "migration_id": migration_id,
                              "problems": errors[:5]})
    if extra:
        report.update(extra)
    report["errors"] = errors
    report["status"] = status
    report["applied"] = False
    report["preserved"] = "旧控制根与备份保持不变；未发生切换"
    return report


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

def verify(project_root: pathlib.Path, migration_id: Optional[str] = None
           ) -> Dict[str, Any]:
    """Compare the on-disk result with the manifests recorded by the migration."""
    project = pathlib.Path(project_root).expanduser().resolve()
    report: Dict[str, Any] = {"_schema": REPORT_SCHEMA, "command": "verify",
                              "project_root": str(project),
                              "migration_id": migration_id, "ok": False,
                              "problems": []}
    problems: List[str] = report["problems"]
    journal = journal_state(project)
    if journal["status"] == "JOURNAL_CORRUPT":
        report.update({"status": "JOURNAL_CORRUPT", "problems": journal["problems"]})
        return report
    if journal["status"] == "EMPTY":
        report["status"] = "NO_MIGRATION"
        problems.append("没有任何迁移记录")
        return report
    migration_id = migration_id or journal["migration_id"]
    entries = [e for e in journal["entries"]
               if e.get("migration_id") == migration_id]
    if journal["migration_id"] != migration_id:
        entries = [e for e in _journal_read(project)[0]
                   if e.get("migration_id") == migration_id]
    report["migration_id"] = migration_id
    report["journal_summary"] = _events(entries)
    started = next((e for e in entries if e.get("event") == STATE_STARTED), {})
    legacy_mode = started.get("mode") == LEGACY_VIOLATION_MODE
    report["mode"] = LEGACY_VIOLATION_MODE if legacy_mode else "strict"
    scientific_issues: List[str] = []
    if journal["migration_id"] == migration_id and journal["last_event"] in FAILURE_EVENTS:
        report["status"] = "FAILED_ATTEMPT"
        problems.append(f"迁移未完成：最后一个事件是 {journal['last_event']}")
        return report
    if journal["migration_id"] == migration_id and journal["last_event"] not in (
            STATE_VERIFIED, STATE_DOCUMENTS_COMMITTED, STATE_LEGACY_ARCHIVED,
            STATE_NEW_ROOT_INSTALLED, STATE_CUTOVER_STARTED):
        report["status"] = "INCOMPLETE"
        problems.append(f"迁移未到可验证状态：{journal['last_event']}")
        return report

    matrix = rlp.runtime_status(project)
    report["runtime_status"] = matrix["status"]
    if matrix["status"] != rlp.RUNTIME_STATUS_READY:
        problems.append(f"运行时状态为 {matrix['status']}：{matrix['reason']}")
    if rlp.inspect_legacy_root(project) is not None:
        problems.append("旧控制根仍以运行时目录存在：必须归档后才算完成")

    # new root must equal the installed manifest exactly
    new_root = project / rlp.STORAGE_ROOT
    installed_manifest = _load_manifest(
        manifest_path(project, migration_id, "installed-manifest.json"))
    if new_root.is_dir() and installed_manifest is None:
        problems.append("缺少安装时记录的 durable manifest：无法证明结果等于预期")
    elif new_root.is_dir():
        actual = snapshot(new_root)
        differences = compare_snapshots(installed_manifest, actual)
        if differences:
            problems.extend(f"新根 {d['path']}: {d['change']}（{d['detail']}）"
                            for d in differences[:10])
        report["recorded_manifest_digest"] = installed_manifest.get("digest")
        report["actual_manifest_digest"] = actual["digest"]
        report["manifest_matches"] = not differences

    # backup must still match its recorded manifest
    backup_manifest = _load_manifest(
        manifest_path(project, migration_id, "backup-manifest.json"))
    if backup_manifest is None:
        problems.append("缺少备份 manifest：无法证明备份完整")
    else:
        journal_started = next((e for e in entries if e.get("event") == STATE_STARTED),
                               {})
        candidate = journal_started.get("backup")
        if candidate:
            backup_root_dir = pathlib.Path(candidate) / "legacy-root"
            if not backup_root_dir.is_dir():
                problems.append(f"备份目录不存在：{backup_root_dir}")
            else:
                for difference in compare_snapshots(backup_manifest,
                                                    snapshot(backup_root_dir))[:5]:
                    problems.append(f"备份 {difference['path']}: {difference['change']}")

    # ---- 迁移证明材料：缺失或损坏一律失败，不允许「跳过即通过」 ----
    evidence = {
        "source-snapshot.json": _evidence(manifest_path(project, migration_id,
                                                        "source-snapshot.json")),
        "source-fingerprint.json": _evidence(manifest_path(project, migration_id,
                                                           "source-fingerprint.json")),
    }
    staged_event = next((e for e in entries if e.get("event") == STATE_STAGED_VERIFIED), {})
    declared_rewrites = int(staged_event.get("rewrites") or 0)
    rewrite_evidence = _evidence(work_dir(project, migration_id) / "rewrite-manifest.json")
    if declared_rewrites or rewrite_evidence[0] == "ok":
        evidence["rewrite-manifest.json"] = rewrite_evidence
    else:
        # 早期迁移在没有任何重写请求时不写这份清单；这不算缺证据
        evidence["rewrite-manifest.json"] = ("not_required", None)
    if legacy_mode:
        evidence["violation-baseline.json"] = _evidence(
            manifest_path(project, migration_id, "violation-baseline.json"))
    for name, (state, _value) in evidence.items():
        if state in ("ok", "not_required"):
            continue
        problems.append(
            f"缺少迁移证明 {name}（{state}）：无法证明迁移前的状态，这项比对不允许跳过。"
            "若工作目录被清理过，需要人工核对，或重新迁移以生成完整证据")
    report["evidence"] = {name: state for name, (state, _v) in evidence.items()}
    report["evidence_ok"] = all(state in ("ok", "not_required")
                                for state, _v in evidence.values())

    # rewritten documents must match their staged digests
    rewrite_manifest = evidence["rewrite-manifest.json"][1] or {"files": []}
    committed = {e.get("file") for e in entries if e.get("event") == "document_committed"}
    for item in rewrite_manifest.get("files", []):
        if item.get("inside_root"):
            continue
        target = project / item["name"]
        if not target.is_file():
            problems.append(f"文档 {item['label']}: 缺失")
            continue
        if _sha256(target) != item["rewritten_sha256"]:
            problems.append(f"文档 {item['label']}: 内容与提交记录不一致")
        if item["label"] not in committed and journal["last_event"] == STATE_VERIFIED:
            problems.append(f"文档 {item['label']}: 未记录在 journal 中")

    # research assets: fingerprint and hash chains
    source_snapshot = _load_manifest(
        manifest_path(project, migration_id, "source-snapshot.json"))
    if new_root.is_dir():
        fingerprint = _semantic_fingerprint(new_root)
        report["semantic_fingerprint"] = fingerprint
        for route_name, route_fp in fingerprint.get("routes", {}).items():
            if route_fp.get("error"):
                problems.append(f"路线 {route_name}：state 不可读（{route_fp['error']}）")
            elif not route_fp.get("state_gate_ok"):
                message = f"路线 {route_name}：state gate 未通过"
                # 历史保留模式下，既有的科研规则债务不算存储失败；它必须与基线逐条相等，
                # 由下面的 legacy_violations_preserved 判定，并反映在最终状态里。
                (scientific_issues if legacy_mode else problems).append(message)
            problems.extend(f"路线 {route_name}：{p}"
                            for p in _chain_problems(new_root, route_name)[:3])
        recorded_fp = evidence["source-fingerprint.json"][1]
        if source_snapshot is not None and recorded_fp is not None and \
                recorded_fp != fingerprint:
            problems.append("科研资产指纹与迁移前记录不一致（预算/计数/状态被改变）")

    # 四路信号分开计算：存储完整、历史不变、科研门禁、违规清单保持
    inventory = _state_inventory(new_root) if new_root.is_dir() else {"routes": {},
                                                                    "fatal": [],
                                                                    "baseline": {"routes": {}}}
    actual_baseline = inventory["baseline"]
    expected_baseline: Optional[Dict[str, Any]] = None
    baseline_diff: Dict[str, Any] = {}
    violations_preserved = True
    if legacy_mode:
        # 保留模式的全部正当性来自「清单与迁移前逐条相等」。基线读不到时，
        # 这条比对无法执行，结论只能是失败，不能默认成立。
        violations_preserved = False
        baseline_state, baseline_entry = evidence.get("violation-baseline.json",
                                                      ("missing", None))
        if baseline_state != "ok" or baseline_entry is None:
            problems.append("历史保留模式缺少违规基线（violation-baseline.json）："
                            "无法证明历史违规清单被原样保留")
        else:
            expected_baseline = baseline_entry.get("baseline")
            stored_digest = baseline_entry.get("digest")
            if not isinstance(expected_baseline, dict):
                problems.append("历史保留模式的基线文件没有 baseline 内容")
            elif stored_digest != _baseline_digest(expected_baseline):
                problems.append("历史保留模式的基线文件自相矛盾：记录的摘要与内容不符")
            else:
                baseline_diff = _baseline_diff(expected_baseline, actual_baseline)
                violations_preserved = (
                    _normalize_baseline(expected_baseline)
                    == _normalize_baseline(actual_baseline))
                if not violations_preserved:
                    problems.append("历史违规清单与迁移前基线不一致（被删除、掩盖或新增）")
    registry_digest_unchanged = True
    registry = new_root / "project" / "route-registry.json"
    source_registry = None
    if source_snapshot is not None:
        source_registry = next((e for e in source_snapshot.get("entries", [])
                                if e.get("path") == "project/route-registry.json"), None)
    if source_registry is not None and registry.is_file():
        registry_digest_unchanged = _sha256(registry) == source_registry.get("sha256")
        if not registry_digest_unchanged:
            problems.append("route-registry.json 在迁移中被改动（路线不应被自动归档或改状态）")
    elif source_registry is None and registry.is_file() and source_snapshot is not None:
        registry_digest_unchanged = False
        problems.append("route-registry.json 在迁移后出现，但源快照中没有它"
                        "（迁移不得创建或改写路线登记）")

    report["storage_integrity_ok"] = not problems
    report["historical_state_unchanged"] = (
        not problems and report["evidence_ok"] and registry_digest_unchanged
        and violations_preserved)
    report["scientific_gate_ok"] = bool(inventory["routes"]) and all(
        entry.get("gate_ok") for entry in inventory["routes"].values())
    report["legacy_violations_preserved"] = violations_preserved
    report["scientific_issues"] = scientific_issues
    if expected_baseline is not None and not violations_preserved:
        report["baseline_diff"] = baseline_diff
    report["violation_baseline_digest"] = (
        (evidence.get("violation-baseline.json", ("", None))[1] or {}).get("digest")
        if expected_baseline is not None else None)
    report["violation_rule_counts"] = {
        route: entry.get("rule_counts")
        for route, entry in inventory["routes"].items() if entry.get("violation_count")}
    if not report["storage_integrity_ok"] or not report["historical_state_unchanged"]:
        report["ok"] = False
        report["status"] = "VERIFY_FAILED"
        return report
    if legacy_mode and not report["scientific_gate_ok"]:
        report["ok"] = True
        report["status"] = "VERIFIED_WITH_LEGACY_ISSUES"
        report["meaning"] = (
            "存储迁移成功，历史科研状态逐条保留；这不表示这些路线已通过科研门禁，"
            "它们继续按原有规则 HOLD")
        return report
    report["ok"] = True
    report["status"] = "VERIFIED"
    return report


def plan_fingerprint(project: pathlib.Path, migration_id: str
                     ) -> Optional[Dict[str, Any]]:
    """The semantic fingerprint recorded at migration start (from source snapshot)."""
    value = _load_manifest(manifest_path(project, migration_id,
                                         "source-fingerprint.json"))
    return value if isinstance(value, dict) else None


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------

def rollback(project_root: pathlib.Path, migration_id: str) -> Dict[str, Any]:
    """Restore the archived legacy root, refusing if the new root has new work.

    The guard compares the **whole durable control plane** with the manifest recorded
    at cutover, not just ``research-state.json``: an updated Scheduler, an appended TAG
    event, a new receipt or a deleted file all refuse the rollback.
    """
    project = pathlib.Path(project_root).expanduser().resolve()
    report: Dict[str, Any] = {"_schema": REPORT_SCHEMA, "command": "rollback",
                              "project_root": str(project),
                              "migration_id": migration_id}
    journal = journal_state(project)
    if journal["status"] == "JOURNAL_CORRUPT":
        report.update({"status": "JOURNAL_CORRUPT", "errors": journal["problems"]})
        return report
    entries = [e for e in _journal_read(project)[0]
               if e.get("migration_id") == migration_id]
    if not entries:
        report.update({"status": "REFUSED",
                       "errors": [f"迁移日志中没有 {migration_id} 的记录"]})
        return report
    migrated = any(e.get("event") in (STATE_NEW_ROOT_INSTALLED,
                                      STATE_LEGACY_ARCHIVED, STATE_VERIFIED)
                   for e in entries)
    if not migrated:
        report.update({"status": "REFUSED",
                       "errors": ["该迁移尚未完成切换，无需回滚（旧根仍是唯一控制根）"]})
        return report
    archive_dir = project / ".rlp-archive" / migration_id / "legacy-root"
    if not archive_dir.is_dir():
        report.update({"status": "REFUSED",
                       "errors": [f"归档目录不存在：{archive_dir}"]})
        return report
    installed_manifest = _load_manifest(
        manifest_path(project, migration_id, "installed-manifest.json"))
    if installed_manifest is None:
        report.update({"status": "REFUSED",
                       "errors": ["缺少安装时 durable manifest：无法判定新根是否只有迁移内容"]})
        return report

    try:
        with rlp.maintenance_exclusive(project, owner={"migration_id": migration_id,
                                                       "command": "rollback"}):
            return _rollback_transaction(project, migration_id, entries,
                                         archive_dir, installed_manifest, report)
    except rlp.MaintenanceInProgress as exc:
        report.update({"status": "REFUSED", "errors": [str(exc)]})
        return report


def _rollback_transaction(project: pathlib.Path, migration_id: str,
                          entries: Sequence[Dict[str, Any]],
                          archive_dir: pathlib.Path,
                          installed_manifest: Dict[str, Any],
                          report: Dict[str, Any]) -> Dict[str, Any]:
    new_root = project / rlp.STORAGE_ROOT
    refused: List[Dict[str, str]] = []
    if new_root.is_dir():
        refused = compare_snapshots(installed_manifest, snapshot(new_root))
    # project-level documents are also durable state
    rewrite_manifest = _rewrite_manifest(project, migration_id) or {"files": []}
    for item in rewrite_manifest.get("files", []):
        if item.get("inside_root"):
            continue
        target = project / item["name"]
        if not target.is_file():
            refused.append({"path": item["label"], "change": "removed",
                            "detail": "迁移后文档被删除"})
        elif _sha256(target) != item["rewritten_sha256"]:
            refused.append({"path": item["label"], "change": "modified",
                            "detail": "迁移后文档被改写"})
    if refused:
        report.update({
            "status": "ROLLBACK_REFUSED_NEW_WORK",
            "errors": ["迁移后控制平面产生了新的写入；回滚会覆盖这些工作，"
                       "请人工导出并协调后再回滚"],
            "differences": refused[:50],
            "difference_count": len(refused),
            "new_root_untouched": True})
        return report

    aside = project / ".rlp-archive" / migration_id / "forward-root"
    legacy_target = project / rlp.LEGACY_STORAGE_ROOT
    # 先把所有前置条件核完，再动任何目录：回滚是两步 rename，中途失败会让项目
    # 既没有新根也没有旧根，只能靠人工从 forward-root 里捞回研究数据。
    if legacy_target.exists():
        report.update({
            "status": "REFUSED",
            "errors": [f"旧控制根路径已被占用：{legacy_target}；回滚会覆盖它。"
                       "先把占用内容移走（或确认它是谁创建的），再回滚"],
            "new_root_untouched": True,
            "occupied_path": str(legacy_target)})
        return report
    if new_root.is_dir() and aside.exists():
        report.update({"status": "REFUSED",
                       "errors": [f"回滚暂存位置已存在：{aside}"]})
        return report
    aside.parent.mkdir(parents=True, exist_ok=True)
    moved_aside = False
    if new_root.is_dir():
        os.rename(new_root, aside)
        moved_aside = True
    try:
        os.rename(archive_dir, legacy_target)
    except OSError as exc:
        # 撤销第一步：新根回到原位，绝不留下「无控制根」的现场
        restored_root = False
        if moved_aside:
            try:
                os.rename(aside, new_root)
                restored_root = True
            except OSError:
                restored_root = False
        report.update({
            "status": "ROLLBACK_FAILED",
            "errors": [f"恢复旧根失败（{type(exc).__name__}: {exc}）"],
            "new_root_restored": restored_root,
            "new_root_present": new_root.is_dir(),
            "archive": str(archive_dir),
            "detail": ("新根已放回原位，项目仍在新根上运行；归档仍在原处"
                       if restored_root else
                       "新根未能放回原位，研究数据在 forward-root，需要人工恢复"),
            "forward_root": str(aside) if moved_aside and not restored_root else None})
        _journal_append(project, {"event": "rollback_failed",
                                  "migration_id": migration_id,
                                  "restored_new_root": restored_root,
                                  "error": str(exc)})
        return report
    restored = _restore_documents(project, migration_id)
    _journal_append(project, {"event": "rolled_back", "migration_id": migration_id,
                              "restored_documents": restored})
    matrix = rlp.runtime_status(project)
    report.update({
        "status": "ROLLED_BACK", "restored_documents": restored,
        "legacy_root": str(project / rlp.LEGACY_STORAGE_ROOT),
        "runtime_status": matrix["status"],
        "note": ("回滚是灾难恢复操作，不是恢复正常科研执行的许可：旧根重新成为迁移来源，"
                 "正式运行仍需重新完成安全迁移（MIGRATION_REQUIRED）。")})
    return report


# ---------------------------------------------------------------------------
# recover
# ---------------------------------------------------------------------------

def _recovery_action(project: pathlib.Path, state: Optional[str],
                     journal: Dict[str, Any]) -> Dict[str, Any]:
    """Classify an interrupted migration from journal + on-disk facts."""
    legacy = rlp.inspect_legacy_root(project)
    new_root = project / rlp.STORAGE_ROOT
    migration_id = journal.get("migration_id")
    archive = (project / ".rlp-archive" / migration_id / "legacy-root") \
        if migration_id else None
    facts = {"legacy_root_present": legacy is not None,
             "new_root_present": new_root.is_dir(),
             "archive_present": bool(archive and archive.is_dir())}
    if state is None:
        return {"action": "none", "detail": "没有迁移记录", "facts": facts}
    rank = _state_rank(state)
    if state == STATE_VERIFIED:
        return {"action": "none", "detail": "迁移已完成并验证", "facts": facts}
    if state in FAILURE_EVENTS:
        return {"action": "manual",
                "detail": f"上次迁移以 {state} 结束；检查报告中的 errors 后再决定重试或回滚",
                "facts": facts}
    if rank < _state_rank(STATE_CUTOVER_STARTED):
        # nothing was switched: cleaning staging is safe only if it holds no new data
        staging = work_dir(project, migration_id) / "staging" / rlp.STORAGE_ROOT
        source_snapshot = _load_manifest(
            manifest_path(project, migration_id, "source-snapshot.json"))
        if staging.is_dir() and source_snapshot is not None:
            differences = compare_snapshots(source_snapshot, snapshot(staging))
            rewrites = _rewrite_manifest(project, migration_id) or {"files": []}
            allowed = {f["label"] for f in rewrites.get("files", []) if f["inside_root"]}
            unique = [d for d in differences
                      if not any(a and (d["path"] == a or d["path"].endswith("/" + a))
                                 for a in allowed)]
            if unique:
                return {"action": "manual",
                        "detail": f"staging 含源控制根之外的内容（{unique[0]['path']}）："
                                  "不自动删除，请人工核对",
                        "facts": facts, "unique_paths": [d["path"] for d in unique[:10]]}
        return {"action": "clean_staging",
                "detail": "切换未开始，staging 与源一致；可安全清理工作目录",
                "facts": facts}
    if facts["legacy_root_present"] and facts["new_root_present"] and \
            not facts["archive_present"]:
        installed = _load_manifest(
            manifest_path(project, migration_id, "installed-manifest.json"))
        source = _load_manifest(
            manifest_path(project, migration_id, "source-snapshot.json"))
        if installed is not None and source is not None and \
                not compare_snapshots(installed, snapshot(new_root)) and \
                not compare_snapshots(source, snapshot(legacy.root)):
            return {"action": "complete_archive",
                    "detail": "新根已安装、旧根未归档且两边都与记录的 manifest 一致："
                              "可安全完成归档（双根暂态）",
                    "facts": facts}
        return {"action": "manual",
                "detail": "新根已安装但旧根未归档，且内容与记录不一致：请人工核对",
                "facts": facts}
    if facts["archive_present"] or (not facts["legacy_root_present"] and
                                    facts["new_root_present"]):
        return {"action": "verify",
                "detail": "切换已完成但未验证：运行 verify 确认新根；必要时 rollback",
                "facts": facts}
    return {"action": "manual", "detail": "无法从 journal 与磁盘事实判断安全动作",
            "facts": facts}


def recover(project_root: pathlib.Path, *, apply: bool = False) -> Dict[str, Any]:
    """Inspect an interrupted migration; only perform provably safe actions."""
    project = pathlib.Path(project_root).expanduser().resolve()
    report: Dict[str, Any] = {"_schema": REPORT_SCHEMA, "command": "recover",
                              "project_root": str(project), "apply": apply}
    journal = journal_state(project)
    if journal["status"] == "JOURNAL_CORRUPT":
        report.update({"status": "JOURNAL_CORRUPT",
                       "problems": journal["problems"],
                       "detail": "journal 损坏：保留原文件供审计，不做任何推断或自动动作"})
        return report
    entries = journal["entries"]
    state = _last_known_state(entries)
    report.update({"status": journal["status"],
                   "migration_id": journal["migration_id"],
                   "last_event": journal["last_event"],
                   "reached_state": state,
                   "maintenance": rlp.maintenance_status(project),
                   "runtime_status": rlp.runtime_status(project)["status"]})
    action = _recovery_action(project, state, journal)
    report.update({"action": action["action"], "detail": action["detail"],
                   "facts": action.get("facts", {})})
    if action.get("unique_paths"):
        report["unique_paths"] = action["unique_paths"]
    leftovers = sorted(project.glob(f"{rlp.MAINTENANCE_DIR}/*/staging"))
    report["staging_leftovers"] = [str(p) for p in leftovers]
    if not apply:
        report["note"] = "只读诊断；安全动作需加 --apply 执行"
        return report
    if action["action"] == "clean_staging":
        try:
            with rlp.maintenance_exclusive(project,
                                           owner={"migration_id": journal["migration_id"],
                                                  "command": "recover"}):
                for leftover in leftovers:
                    shutil.rmtree(leftover, ignore_errors=True)
                _journal_append(project, {"event": "aborted",
                                          "migration_id": journal["migration_id"],
                                          "reason": "staging cleaned after interruption"})
            report["performed"] = "clean_staging"
        except rlp.MaintenanceInProgress as exc:
            report["performed"] = None
            report["errors"] = [str(exc)]
    elif action["action"] == "complete_archive":
        try:
            with rlp.maintenance_exclusive(project,
                                           owner={"migration_id": journal["migration_id"],
                                                  "command": "recover"}):
                legacy = rlp.inspect_legacy_root(project)
                archive = project / ".rlp-archive" / journal["migration_id"] / \
                    "legacy-root"
                archive.parent.mkdir(parents=True, exist_ok=True)
                os.rename(legacy.root, archive)
                _journal_append(project, {"event": STATE_LEGACY_ARCHIVED,
                                          "migration_id": journal["migration_id"],
                                          "archive": str(archive),
                                          "recovered": True})
            report["performed"] = "complete_archive"
            report["next"] = "运行 verify 确认新根"
        except rlp.MaintenanceInProgress as exc:
            report["performed"] = None
            report["errors"] = [str(exc)]
    else:
        report["performed"] = None
        report["note"] = "该状态不能自动处理；保留现场，按 detail 人工处理"
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="RLP project control-root migration")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "plan", "migrate", "verify", "rollback", "recover"):
        p = sub.add_parser(name)
        p.add_argument("--project", required=True)
        if name in ("plan", "migrate"):
            p.add_argument("--backup-root", required=(name == "migrate"))
        if name == "plan":
            p.add_argument("--preserve-known-legacy-violations", action="store_true",
                           help="plan the historical-preservation mode")
            p.add_argument("--baseline-out",
                           help="write the violation baseline to this JSON file")
        if name == "migrate":
            p.add_argument("--apply", action="store_true",
                           help="execute the migration (default: plan only)")
            p.add_argument("--rewrite", action="append", nargs="*", default=[],
                           help="operational docs to rewrite (explicit opt-in); "
                                "repeatable")
            p.add_argument("--assume-writers-quiesced", action="store_true",
                           help="confirm that external writers are stopped "
                                "(required with --apply)")
            p.add_argument("--preserve-known-legacy-violations", action="store_true",
                           help="move readable history that violates current research "
                                "rules; requires --violation-baseline from a reviewed plan")
            p.add_argument("--violation-baseline",
                           help="the plan's violation_baseline as a JSON file")
        if name in ("verify", "rollback"):
            p.add_argument("--migration-id")
        if name == "recover":
            p.add_argument("--apply", action="store_true",
                           help="perform a provably safe recovery action")
    args = parser.parse_args(argv)
    project = pathlib.Path(args.project)
    if not project.is_dir():
        print(f"[env] 项目目录不存在：{project}", file=sys.stderr)
        return EXIT_ENV
    try:
        if args.command == "inspect":
            report = inspect(project)
            code = EXIT_OK if report["status"] in (
                rlp.RUNTIME_STATUS_READY, rlp.RUNTIME_STATUS_MIGRATION_REQUIRED,
                rlp.RUNTIME_STATUS_NEW_PROJECT) else EXIT_HARD
        elif args.command == "plan":
            report = plan(project, pathlib.Path(args.backup_root),
                          preserve_known_legacy_violations=(
                              args.preserve_known_legacy_violations))
            if getattr(args, "baseline_out", None) and "violation_baseline" in report:
                baseline_file = pathlib.Path(args.baseline_out)
                _write_json(baseline_file, {"violation_baseline":
                                            report["violation_baseline"]})
                report["baseline_file"] = str(baseline_file)
            code = EXIT_OK if report.get("ready_to_migrate") else EXIT_HARD
        elif args.command == "migrate":
            baseline = None
            if getattr(args, "violation_baseline", None):
                try:
                    baseline_value = json.loads(
                        pathlib.Path(args.violation_baseline).read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                    print(f"[env] 违规基线不可读：{args.violation_baseline}（{exc}）",
                          file=sys.stderr)
                    return EXIT_ENV
                baseline = baseline_value.get("violation_baseline", baseline_value)
            report = migrate(project, pathlib.Path(args.backup_root),
                             apply=args.apply,
                             rewrite=[item for group in (args.rewrite or [])
                                      for item in (group if isinstance(group, list)
                                                   else [group])],
                             assume_writers_quiesced=args.assume_writers_quiesced,
                             preserve_known_legacy_violations=(
                                 args.preserve_known_legacy_violations),
                             violation_baseline=baseline)
            ok = report["status"] in ("MIGRATED", "ALREADY_MIGRATED",
                                      "MIGRATED_WITH_LEGACY_ISSUES")
            code = EXIT_OK if ok else EXIT_HARD
        elif args.command == "verify":
            report = verify(project, migration_id=args.migration_id)
            code = EXIT_OK if report["ok"] else EXIT_HARD
        elif args.command == "rollback":
            report = rollback(project, migration_id=args.migration_id)
            code = EXIT_OK if report["status"] == "ROLLED_BACK" else EXIT_HARD
        else:
            report = recover(project, apply=args.apply)
            code = EXIT_OK if report.get("status") != "JOURNAL_CORRUPT" else EXIT_HARD
    except rlp.MaintenanceInProgress as exc:
        report = {"_schema": REPORT_SCHEMA, "command": args.command,
                  "status": exc.STATUS, "errors": [str(exc)]}
        code = EXIT_HARD
    except (rlp.AmbiguousStorageRoot, rlp.MigrationRequired,
            rlp.InvalidStorageRoot, rlp.LayoutError) as exc:
        report = {"_schema": REPORT_SCHEMA, "command": args.command,
                  "status": getattr(exc, "STATUS", "INVALID_LAYOUT"),
                  "errors": [str(exc)]}
        code = EXIT_HARD
    except OSError as exc:
        report = {"_schema": REPORT_SCHEMA, "command": args.command,
                  "status": "ENVIRONMENT", "errors": [f"{type(exc).__name__}: {exc}"]}
        code = EXIT_ENV
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
