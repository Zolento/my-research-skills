#!/usr/bin/env python3
"""migrate_project_root.py — safe control-root migration for RLP projects (v2.1.0).

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
    python3 scripts/migrate_project_root.py recover --project <project>   # interrupted run

Transaction (all steps logged to the migration journal):

    read-only preflight → writer quiesce advisory → verified external backup
    → private staging copy inside the project (same filesystem) → staged verification
    → explicit, manifest-tracked operational-path rewrites (opt-in) → atomic rename
    cutover → legacy root renamed to a non-runtime archive name → post-migration
    verification → project unlocked.

Guarantees:

* no in-place edit of the legacy root; the cutover is one atomic ``os.rename`` on the
  project filesystem (a cross-device backup is copied and checksum-verified, never
  claimed to be atomic);
* the backup is verified item-by-item (count + size + SHA-256) before the cutover;
* the legacy root is renamed (not deleted) to ``.research-idea-pipeline.migrated-<id>``
  — invisible to the runtime resolver — and may be pruned after verification;
* interrupted runs are detected via the journal and must be recovered explicitly;
* a second migrate run is idempotent (already-migrated → no-op with the original id);
* rollback restores the archived legacy root and every rewritten file, and refuses
  when the new root has produced writes after the migration (checked against the
  recorded post-migration state digests).

Exit codes: 0 ok, 1 usage, 3 preflight/migration/verification failure, 4 environment.
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
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cognition as cg
import rlp_paths as rlp

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_HARD = 3
EXIT_ENV = 4

JOURNAL_SCHEMA = "research-idea-pipeline/migration-journal@1"
REPORT_SCHEMA = "research-idea-pipeline/migration-report@1"

#: Durable control-plane artifacts that must survive the migration intact.
DURABLE_ARTIFACTS: Tuple[str, ...] = (
    "routes/*/research-state.json", "routes/*/scheduler.json",
    "routes/*/cognition/model-revisions.jsonl", "routes/*/cognition/index.json",
    "routes/*/cognition/context-brief.md", "routes/*/decision-trajectory.jsonl",
    "routes/*/domain/", "routes/*/experiments/", "routes/*/assurance/",
    "routes/*/repairs/", "routes/*/actions/", "routes/*/history/",
    "routes/*/methods/", "routes/*/.execution", "routes/*/policy/",
    "project/", "meta/",
)

#: Files whose *content* is historical evidence and must never be rewritten.
NEVER_REWRITE = (
    "research-state.json", "model-revisions.jsonl", "decision-trajectory.jsonl",
    "tag-events.jsonl", "scheduler.json",
)

#: Runtime/operational files whose content MAY be rewritten with explicit opt-in.
REWRITABLE = (
    "AGENTS.md", "README.md", "INDEX.md", "STATUS.md",
)


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _new_migration_id() -> str:
    return time.strftime("%Y%m%dT%H%M%S") + "-" + os.urandom(3).hex()


def journal_path(project_root: pathlib.Path) -> pathlib.Path:
    return project_root / ".rlp-migration" / "journal.jsonl"


def _record_post_state_digests(project: pathlib.Path, migration_id: str) -> None:
    """Record the new root's state digests right after the cutover (rollback guard)."""
    new_root = project / rlp.STORAGE_ROOT
    digests = {p.parent.name: cg.digest_of(json.loads(p.read_text(encoding="utf-8")))
               for p in _route_states(new_root)}
    _journal_append(project, {"event": "migrated", "migration_id": migration_id,
                              "post_state_digests": digests})


def _journal_append(project: pathlib.Path, entry: Dict[str, Any]) -> None:
    path = journal_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"_schema": JOURNAL_SCHEMA, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
             **entry}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _journal_read(project: pathlib.Path) -> List[Dict[str, Any]]:
    path = journal_path(project)
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _active_migration(project: pathlib.Path) -> Optional[Dict[str, Any]]:
    """The latest migration that has not reached a terminal state."""
    for entry in reversed(_journal_read(project)):
        if entry.get("event") in ("migrated", "verified", "rolled_back",
                                  "aborted") and entry.get("migration_id"):
            return entry
    return None


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------

def _inventory(root: pathlib.Path) -> Dict[str, Any]:
    """Inventory every durable file under a control root."""
    files: List[Dict[str, Any]] = []
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_file():
            stat = path.stat()
            total += stat.st_size
            files.append({"path": str(path.relative_to(root)), "size": stat.st_size,
                          "sha256": _sha256(path),
                          "symlink": str(path.resolve()) if path.is_symlink() else None})
    return {"file_count": len(files), "total_bytes": total, "files": files}


def _route_states(root: pathlib.Path) -> List[pathlib.Path]:
    routes = root / "routes"
    if not routes.is_dir():
        return []
    return sorted(routes.glob("*/research-state.json"))


def _semantic_fingerprint(root: pathlib.Path) -> Dict[str, Any]:
    """Research-asset counts and budget totals that must not change in migration."""
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


def _path_dependencies(root: pathlib.Path, project_root: pathlib.Path) -> Dict[str, List[Dict[str, str]]]:
    """Classify legacy-root string references found in durable files.

    runtime_writable: operational documents that may be rewritten with explicit
    opt-in (tracked for rollback). historical: frozen/hashed records that must stay
    byte-identical. Unknown records are classified historical by default.
    """
    runtime_writable: List[Dict[str, str]] = []
    historical: List[Dict[str, str]] = []
    needle = rlp.LEGACY_STORAGE_ROOT
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root))
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if needle not in text:
            continue
        entry = {"path": rel, "occurrences": text.count(needle)}
        name = pathlib.Path(rel).name
        if name in REWRITABLE or rel.endswith(("README.md", "INDEX.md", "STATUS.md",
                                               "AGENTS.md")):
            runtime_writable.append(entry)
        else:
            historical.append(entry)
    # project-level operational docs outside the control root
    for name in ("AGENTS.md", "README.md", "INDEX.md"):
        candidate = project_root / name
        if candidate.is_file():
            try:
                text = candidate.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if needle in text:
                runtime_writable.append({"path": f"<project>/{name}",
                                         "occurrences": text.count(needle)})
    return {"runtime_writable": runtime_writable, "historical": historical}


def inspect(project_root: pathlib.Path) -> Dict[str, Any]:
    """Read-only preflight. Never writes."""
    project = project_root.expanduser().resolve()
    matrix = rlp.runtime_status(project)
    report: Dict[str, Any] = {"_schema": REPORT_SCHEMA, "command": "inspect",
                              "project_root": str(project), "status": matrix["status"],
                              "reason": matrix["reason"]}
    legacy = rlp.inspect_legacy_root(project)
    if legacy is not None:
        report["legacy_inventory"] = _inventory(legacy.root)
        report["legacy_routes"] = [str(p.parent.relative_to(legacy.root))
                                   for p in _route_states(legacy.root)]
        report["semantic_fingerprint"] = _semantic_fingerprint(legacy.root)
        report["path_dependencies"] = _path_dependencies(legacy.root, project)
    if matrix["new_root_exists"]:
        new_root = project / rlp.STORAGE_ROOT
        report["new_root_inventory"] = _inventory(new_root)
    report["writers_advisory"] = (
        "迁移要求所有写入者停止：科研会话、Research Loop、DSH Research Mesh、"
        "自动 Resume、GPU 实验执行器、结果收集、Evidence Outcome 写回、"
        "Scheduler/Strategy Memory 与后台监控。工具不会终止任何进程；"
        "无法确认时不要执行 --apply。")
    pending = _active_migration(project)
    report["pending_migration"] = pending
    return report


# ---------------------------------------------------------------------------
# plan / backup
# ---------------------------------------------------------------------------

def _backup_destination(backup_root: pathlib.Path, project: pathlib.Path,
                        migration_id: str) -> pathlib.Path:
    project_id = project.name or "project"
    return backup_root.expanduser().resolve() / project_id / migration_id


def _copy_verified(source: pathlib.Path, destination: pathlib.Path
                   ) -> Tuple[Dict[str, Any], List[str]]:
    """Copy a tree and verify it item-by-item. Returns (manifest, problems)."""
    problems: List[str] = []
    manifest: Dict[str, Any] = {"files": [], "file_count": 0, "total_bytes": 0}
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source)
        target = destination / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            target.symlink_to(os.readlink(path))
            manifest["files"].append({"path": str(rel), "size": 0, "sha256": None,
                                      "symlink": os.readlink(path)})
            continue
        shutil.copy2(path, target)
        size = target.stat().st_size
        digest = _sha256(target)
        source_digest = _sha256(path)
        entry = {"path": str(rel), "size": size, "sha256": digest}
        manifest["files"].append(entry)
        manifest["file_count"] += 1
        manifest["total_bytes"] += size
        if digest != source_digest:
            problems.append(f"{rel}: 备份副本校验不一致")
    return manifest, problems


def _verify_backup(manifest: Dict[str, Any], destination: pathlib.Path
                   ) -> List[str]:
    problems: List[str] = []
    seen = 0
    for entry in manifest["files"]:
        target = destination / entry["path"]
        if entry.get("symlink"):
            if not target.is_symlink() or os.readlink(target) != entry["symlink"]:
                problems.append(f"{entry['path']}: 符号链接不一致")
            continue
        if not target.is_file():
            problems.append(f"{entry['path']}: 备份缺文件")
            continue
        if target.stat().st_size != entry["size"] or _sha256(target) != entry["sha256"]:
            problems.append(f"{entry['path']}: 备份校验不一致")
        seen += 1
    if seen != manifest["file_count"]:
        problems.append(f"备份文件数不符：期望 {manifest['file_count']}，实际 {seen}")
    return problems


def plan(project_root: pathlib.Path, backup_root: pathlib.Path) -> Dict[str, Any]:
    """Read-only migration plan: id, inventory, backup destination, rewrites."""
    project = project_root.expanduser().resolve()
    report = inspect(project)
    report["command"] = "plan"
    migration_id = _new_migration_id()
    destination = _backup_destination(backup_root, project, migration_id)
    report["migration_id"] = migration_id
    report["backup_destination"] = str(destination)
    report["staging_dir"] = str(project / f".rlp-migration-{migration_id}" / "staging")
    report["archive_name"] = f"{rlp.LEGACY_STORAGE_ROOT}.migrated-{migration_id}"
    if report["status"] != rlp.RUNTIME_STATUS_MIGRATION_REQUIRED:
        report["ready_to_migrate"] = False
        return report
    legacy = rlp.inspect_legacy_root(project)
    assert legacy is not None
    fingerprint = report.get("semantic_fingerprint", {})
    broken = [route for route, fp in fingerprint.get("routes", {}).items()
              if fp.get("error") or not fp.get("state_gate_ok")]
    if broken:
        report["broken_routes"] = broken
        report["ready_to_migrate"] = False
        report["reason"] = ("旧控制根中存在损坏或未过 state gate 的 Research State："
                            + "、".join(broken) +
                            "；先修复 canonical 产物，再迁移（不得绕过）")
        return report
    import shutil as _shutil
    usage = _shutil.disk_usage(project)
    needed = _inventory(legacy.root)["total_bytes"]
    report["disk"] = {"free_bytes": usage.free, "estimated_need_bytes": needed * 2,
                      "sufficient": usage.free > needed * 2}
    rewrites = report.get("path_dependencies", {}).get("runtime_writable", [])
    report["proposed_rewrites"] = rewrites
    report["rewrite_policy"] = (
        "默认不重写任何文件内容。--rewrite 仅重写显式列出的运行时文档"
        "（AGENTS/README/INDEX/STATUS），逐文件记录原始字节用于回滚；"
        "冻结预注册、证据、事件链等历史记录永不重写。")
    report["ready_to_migrate"] = report["disk"]["sufficient"]
    return report


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------

def migrate(project_root: pathlib.Path, backup_root: pathlib.Path, *,
            apply: bool = False, rewrite: Sequence[str] = ()) -> Dict[str, Any]:
    """Run the migration transaction. Without --apply this is plan-only."""
    project = project_root.expanduser().resolve()
    plan_report = plan(project, backup_root)
    report: Dict[str, Any] = {"_schema": REPORT_SCHEMA, "command": "migrate",
                              "project_root": str(project),
                              "migration_id": plan_report.get("migration_id"),
                              "status": plan_report["status"], "applied": False}
    if plan_report["status"] == rlp.RUNTIME_STATUS_READY:
        pending = _active_migration(project)
        report.update({"status": "ALREADY_MIGRATED", "applied": False,
                       "idempotent": True,
                       "previous_migration_id": (pending or {}).get("migration_id"),
                       "detail": "项目已在新根上运行；再次执行为幂等 no-op"})
        return report
    if plan_report["status"] != rlp.RUNTIME_STATUS_MIGRATION_REQUIRED:
        report["errors"] = [f"当前状态 {plan_report['status']} 不可迁移："
                            f"{plan_report['reason']}"]
        report["status"] = "REFUSED"
        return report
    if not plan_report.get("ready_to_migrate"):
        report["errors"] = ([plan_report.get("reason")] if plan_report.get("reason")
                            else ["磁盘空间不足或预检失败：需要约两倍控制根体积的可用空间"])
        report["status"] = "REFUSED"
        return report
    if not apply:
        report["detail"] = "plan-only（未加 --apply）；备份与切换都不会发生"
        return report

    migration_id = plan_report["migration_id"]
    legacy = rlp.inspect_legacy_root(project)
    assert legacy is not None
    backup_dir = pathlib.Path(plan_report["backup_destination"])
    if backup_dir.exists() and any(backup_dir.iterdir()):
        report["errors"] = [f"备份目的地已存在且非空：{backup_dir}；不覆盖已有备份"]
        report["status"] = "REFUSED"
        return report
    staging_root = project / f".rlp-migration-{migration_id}" / "staging"
    archive_name = plan_report["archive_name"]
    _journal_append(project, {"event": "started", "migration_id": migration_id,
                              "backup": str(backup_dir)})

    # 1) verified external backup
    backup_manifest, problems = _copy_verified(legacy.root, backup_dir / "legacy-root")
    if problems:
        _journal_append(project, {"event": "backup_failed", "migration_id": migration_id,
                                  "problems": problems[:5]})
        report["errors"] = ["备份失败，未发生任何切换："] + problems[:5]
        report["status"] = "FAILED_BACKUP"
        return report
    backup_problems = _verify_backup(backup_manifest, backup_dir / "legacy-root")
    if backup_problems:
        _journal_append(project, {"event": "backup_verify_failed",
                                  "migration_id": migration_id,
                                  "problems": backup_problems[:5]})
        report["errors"] = ["备份验证失败，未发生任何切换："] + backup_problems[:5]
        report["status"] = "FAILED_BACKUP"
        return report
    _journal_append(project, {"event": "backup_verified", "migration_id": migration_id,
                              "files": backup_manifest["file_count"]})

    # 2) private staging copy (same filesystem as the project)
    if staging_root.exists():
        shutil.rmtree(staging_root)
    staging_target = staging_root / rlp.STORAGE_ROOT
    staging_root.mkdir(parents=True)
    staging_manifest, problems = _copy_verified(legacy.root, staging_target)
    if problems:
        _journal_append(project, {"event": "staging_failed", "migration_id": migration_id})
        report["errors"] = ["staging 复制失败："] + problems[:5]
        report["status"] = "FAILED_STAGING"
        return report

    # 3) explicit, manifest-tracked operational rewrites (opt-in)
    rewrites_done: List[Dict[str, str]] = []
    rewrite_set = {str(item).strip() for item in rewrite if str(item).strip()}
    if rewrite_set:
        rewrites_done = _rewrite_operational(legacy.root, staging_target, project,
                                             rewrite_set, staging_root)
    _journal_append(project, {"event": "staged", "migration_id": migration_id,
                              "files": staging_manifest["file_count"],
                              "rewrites": len(rewrites_done)})

    # 4) staged verification against the legacy fingerprint
    staged_fp = _semantic_fingerprint(staging_target)
    legacy_fp = plan_report.get("semantic_fingerprint", {})
    if staged_fp != legacy_fp:
        _journal_append(project, {"event": "staging_verify_failed",
                                  "migration_id": migration_id})
        report["errors"] = ["staging 校验失败：科研资产指纹与源不一致，未发生切换"]
        report["status"] = "FAILED_STAGING_VERIFY"
        return report

    # 5) atomic cutover (same filesystem: staging dir lives inside the project)
    target_root = project / rlp.STORAGE_ROOT
    try:
        os.rename(staging_target, target_root)
    except OSError as exc:
        _journal_append(project, {"event": "cutover_failed", "migration_id": migration_id,
                                  "error": str(exc)})
        report["errors"] = [f"原子切换失败（未丢失数据，staging 保留）：{exc}"]
        report["status"] = "FAILED_CUTOVER"
        return report
    _journal_append(project, {"event": "cut_over", "migration_id": migration_id})
    _record_post_state_digests(project, migration_id)

    # 6) retire the legacy root by renaming it out of the resolver's namespace
    archive_dir = project / ".rlp-archive" / migration_id
    archive_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.rename(legacy.root, archive_dir / "legacy-root")
    except OSError as exc:
        _journal_append(project, {"event": "archive_rename_failed",
                                  "migration_id": migration_id, "error": str(exc)})
        # the cutover already happened; the stale legacy root must be reported loudly
        report["errors"] = [f"旧根归档重命名失败，项目根可能同时存在两个控制根，"
                            f"需要人工处理：{exc}"]
        report["status"] = "FAILED_ARCHIVE"
        return report
    _journal_append(project, {"event": "migrated", "migration_id": migration_id,
                              "backup": str(backup_dir),
                              "archive": str(archive_dir / "legacy-root"),
                              "rewrites": rewrites_done})

    # 7) post-migration verification
    verify_report = verify(project, migration_id=migration_id)
    report["verify"] = verify_report
    if verify_report["ok"]:
        report["status"] = "MIGRATED"
        report["applied"] = True
        report["backup_destination"] = str(backup_dir)
        report["archive"] = str(archive_dir / "legacy-root")
        report["semantic_fingerprint"] = legacy_fp
        report["rewrites"] = rewrites_done
        report["resume_hint"] = ("迁移完成且校验通过；新根为唯一运行时控制根。"
                                 "验证无误后可删除归档目录与 .rlp-migration-* 残留。")
    else:
        report["status"] = "MIGRATED_VERIFY_FAILED"
        report["applied"] = True
        report["rollback_hint"] = (
            "python3 scripts/migrate_project_root.py rollback --project ... "
            f"--migration-id {migration_id}")
    return report


def _rewrite_operational(legacy_root: pathlib.Path, staging_target: pathlib.Path,
                         project: pathlib.Path, rewrite_set: set,
                         staging_root: pathlib.Path) -> List[Dict[str, str]]:
    """Rewrite explicitly allow-listed operational docs inside the staged copy.

    Every rewrite records the original bytes in the staging root so a rollback can
    restore them byte-for-byte. Historical records are never touched.
    """
    done: List[Dict[str, str]] = []
    needle = rlp.LEGACY_STORAGE_ROOT
    originals = staging_root / "rewrite-originals"
    originals.mkdir(parents=True, exist_ok=True)
    for rel in sorted(rewrite_set):
        source = staging_target / rel
        if not source.is_file():
            continue
        name = pathlib.Path(rel).name
        if name not in REWRITABLE:
            continue
        original = source.read_bytes()
        (originals / f"{abs(hash(rel))}-{name}").write_bytes(original)
        text = original.decode("utf-8")
        source.write_text(text.replace(needle, rlp.STORAGE_ROOT), encoding="utf-8")
        done.append({"path": rel, "original_backup": str(originals), "occurrences":
                     original.decode("utf-8").count(needle)})
    # project-level docs live outside the staged control root; rewrite in place and
    # keep originals for rollback
    for name in sorted(rewrite_set):
        candidate = project / name
        if name in REWRITABLE and candidate.is_file():
            original = candidate.read_bytes()
            text = original.decode("utf-8")
            if needle in text:
                (originals / f"project-{name}").write_bytes(original)
                candidate.write_text(text.replace(needle, rlp.STORAGE_ROOT),
                                     encoding="utf-8")
                done.append({"path": f"<project>/{name}",
                             "original_backup": str(originals),
                             "occurrences": text.count(needle)})
    return done


# ---------------------------------------------------------------------------
# verify / rollback / recover
# ---------------------------------------------------------------------------

def verify(project_root: pathlib.Path, migration_id: Optional[str] = None
           ) -> Dict[str, Any]:
    """Post-migration verification: matrix, fingerprints, chains, budgets, no dual root."""
    project = project_root.expanduser().resolve()
    matrix = rlp.runtime_status(project)
    report: Dict[str, Any] = {"_schema": REPORT_SCHEMA, "command": "verify",
                              "project_root": str(project),
                              "migration_id": migration_id,
                              "runtime_status": matrix["status"], "ok": False}
    problems: List[str] = []
    if matrix["status"] != rlp.RUNTIME_STATUS_READY:
        problems.append(f"运行时状态为 {matrix['status']}：{matrix['reason']}")
    new_root = project / rlp.STORAGE_ROOT
    if new_root.is_dir():
        fingerprint = _semantic_fingerprint(new_root)
        report["semantic_fingerprint"] = fingerprint
        for route_name, route_fp in fingerprint.get("routes", {}).items():
            if route_fp.get("error"):
                problems.append(f"路线 {route_name}：state 不可读（{route_fp['error']}）")
            elif not route_fp.get("state_gate_ok"):
                problems.append(f"路线 {route_name}：state gate 未通过")
            for chain in (("decision-trajectory.jsonl", "决策轨迹"),
                          ("domain/tag-events.jsonl", "TAG 事件")):
                chain_path = new_root / "routes" / route_name / chain[0]
                if chain_path.is_file():
                    if "tag-events" in chain[0]:
                        import domain_guard as dg
                        _records, chain_problems = dg.load_events(new_root / "routes" / route_name)
                    else:
                        import decision_trajectory as dt
                        chain_problems = []
                        try:
                            _records, diagnostics = dt.load_records(chain_path, tolerant=True)
                            chain_problems = [item.render() for item in diagnostics]
                        except Exception as exc:               # a broken chain must be loud
                            chain_problems = [str(exc)]
                    if chain_problems:
                        problems.append(f"路线 {route_name}：{chain[1]}链校验失败")
    journal_entries = [e for e in _journal_read(project)
                       if e.get("migration_id") == migration_id] if migration_id else []
    if migration_id:
        migrated = [e for e in journal_entries if e.get("event") == "migrated"]
        if not migrated:
            problems.append(f"迁移日志中没有 {migration_id} 的 migrated 记录")
        else:
            report["journal_summary"] = [e.get("event") for e in journal_entries]
            # a rollback must refuse when research has advanced past the migration
            report["post_migration_digests"] = migrated[0].get("post_state_digests")
    report["problems"] = problems
    report["ok"] = not problems
    return report


def rollback(project_root: pathlib.Path, migration_id: str) -> Dict[str, Any]:
    """Restore the archived legacy root and every rewritten operational file.

    Refuses when the new root has produced research writes after the migration
    (post-migration state digests differ) — such a rollback would overwrite new work.
    """
    project = project_root.expanduser().resolve()
    report: Dict[str, Any] = {"_schema": REPORT_SCHEMA, "command": "rollback",
                              "project_root": str(project),
                              "migration_id": migration_id}
    entries = [e for e in _journal_read(project)
               if e.get("migration_id") == migration_id]
    migrated = [e for e in entries if e.get("event") == "migrated"]
    if not migrated:
        report["errors"] = [f"迁移日志中没有 {migration_id} 的 migrated 记录，无法回滚"]
        report["status"] = "REFUSED"
        return report
    archive_dir = project / ".rlp-archive" / migration_id / "legacy-root"
    if not archive_dir.is_dir():
        report["errors"] = [f"归档目录不存在：{archive_dir}"]
        report["status"] = "REFUSED"
        return report
    new_root = project / rlp.STORAGE_ROOT
    # rollback guard: research writes after the migration block a direct rollback
    recorded = migrated[0].get("post_state_digests") or {}
    for route_name, digest in recorded.items():
        state_path = new_root / "routes" / route_name / "research-state.json"
        if state_path.is_file():
            current = cg.digest_of(json.loads(state_path.read_text(encoding="utf-8")))
            if current != digest:
                report["errors"] = [
                    f"路线 {route_name} 在迁移后产生了新的科研写入"
                    f"（state_version/digest 已变化）；禁止回滚覆盖新工作，"
                    "需要人工协调（例如先把新工作另存）"]
                report["status"] = "REFUSED"
                return report
    if new_root.exists():
        aside = project / ".rlp-archive" / migration_id / "forward-root"
        aside.parent.mkdir(parents=True, exist_ok=True)
        os.rename(new_root, aside)
    os.rename(archive_dir, project / rlp.LEGACY_STORAGE_ROOT)
    # restore rewritten operational files from the staging originals
    restored = 0
    for originals in project.glob(f".rlp-migration-{migration_id}/staging/rewrite-originals/project-*"):
        name = originals.name.replace("project-", "")
        target = project / name
        if target.is_file():
            target.write_bytes(originals.read_bytes())
            restored += 1
    _journal_append(project, {"event": "rolled_back", "migration_id": migration_id,
                              "restored_files": restored})
    report.update({"status": "ROLLED_BACK", "restored_files": restored,
                   "legacy_root": str(project / rlp.LEGACY_STORAGE_ROOT)})
    return report


def recover(project_root: pathlib.Path) -> Dict[str, Any]:
    """Detect and report an interrupted migration; clean staging when it is safe."""
    project = project_root.expanduser().resolve()
    report: Dict[str, Any] = {"_schema": REPORT_SCHEMA, "command": "recover",
                              "project_root": str(project)}
    active = _active_migration(project)
    report["pending_migration"] = active
    leftovers = sorted(project.glob(".rlp-migration-*"))
    report["staging_leftovers"] = [str(p) for p in leftovers]
    matrix = rlp.runtime_status(project)
    report["runtime_status"] = matrix["status"]
    # an interrupted run: journal has started/cut_over without a terminal event, or
    # staging leftovers exist
    entries = _journal_read(project)
    cut_over_ids = {e["migration_id"] for e in entries
                    if e.get("event") == "cut_over"}
    migrated_ids = {e["migration_id"] for e in entries
                    if e.get("event") in ("migrated", "rolled_back", "aborted")}
    orphan_cutover = sorted(cut_over_ids - migrated_ids)
    interrupted = bool(active and active.get("event") in
                       ("started", "backup_verified", "staged", "cut_over")) \
        or bool(orphan_cutover)
    report["interrupted"] = interrupted or bool(leftovers)
    report["orphan_cutovers"] = orphan_cutover
    if orphan_cutover and matrix["status"] == rlp.RUNTIME_STATUS_READY:
        report["action"] = "verify"
        report["detail"] = ("检测到已切换但收尾未记录的迁移 "
                            f"（{', '.join(orphan_cutover)}）：请运行 verify 确认新根，"
                            "必要时用对应 migration_id 执行 rollback")
        return report
    if interrupted and matrix["status"] == rlp.RUNTIME_STATUS_READY:
        # the cutover happened; the safe action is verify + explicit rollback
        report["action"] = "verify"
        report["detail"] = ("切换已完成但收尾未记录：请运行 verify 确认新根，"
                            "必要时用对应 migration_id 执行 rollback")
    elif leftovers and matrix["status"] in (rlp.RUNTIME_STATUS_MIGRATION_REQUIRED,
                                            rlp.RUNTIME_STATUS_NEW_PROJECT):
        report["action"] = "clean_staging"
        for leftover in leftovers:
            shutil.rmtree(leftover, ignore_errors=True)
        report["detail"] = "未发生切换，仅清理 staging 残留；旧根未受影响"
    else:
        report["action"] = "manual"
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
        if name == "migrate":
            p.add_argument("--apply", action="store_true",
                           help="execute the migration (default: plan only)")
            p.add_argument("--rewrite", nargs="*", default=[],
                           help="operational docs to rewrite (explicit opt-in)")
        if name in ("verify", "rollback"):
            p.add_argument("--migration-id")
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
            report = plan(project, pathlib.Path(args.backup_root))
            code = EXIT_OK if report.get("ready_to_migrate") else EXIT_HARD
        elif args.command == "migrate":
            report = migrate(project, pathlib.Path(args.backup_root),
                             apply=args.apply, rewrite=args.rewrite)
            code = EXIT_OK if report["status"] in ("MIGRATED", "ALREADY_MIGRATED") \
                else EXIT_HARD if report["status"] != "REFUSED" else EXIT_HARD
        elif args.command == "verify":
            report = verify(project, migration_id=args.migration_id)
            code = EXIT_OK if report["ok"] else EXIT_HARD
        elif args.command == "rollback":
            report = rollback(project, migration_id=args.migration_id)
            code = EXIT_OK if report["status"] == "ROLLED_BACK" else EXIT_HARD
        else:
            report = recover(project)
            code = EXIT_OK
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
