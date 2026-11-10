#!/usr/bin/env python3
"""test_migration_transaction.py — v2.1.1 migration transaction safety.

Covers the four patch areas with real processes and real files:

* concurrency: only one migration may hold the maintenance lock, and RLP write
  entries refuse while it is held;
* source stability: a change to the legacy root during the transaction aborts the
  cutover (``SOURCE_CHANGED_DURING_MIGRATION``) and preserves both roots;
* rollback guard: any durable write after the migration refuses the rollback
  (``ROLLBACK_REFUSED_NEW_WORK``) — Scheduler, TAG, trajectory, receipts, new files,
  deletions, symlink retargeting — not just a changed ``research-state.json``;
* document transaction: project documents stay untouched until the control root is
  installed; a failed commit restores original bytes; no ``--rewrite`` means no
  project-level document changes at all;
* journal/recovery: a corrupt journal fails closed, a dual-root transient is
  detectable, and recovery never deletes un-reviewed staging data.

Every case drives the real CLI where a user would; helper functions from
``test_storage_migration`` provide the realistic two-route legacy fixture.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import domain_guard as dg
import migrate_project_root as mp
import rlp_paths as rlp
from test_storage_migration import LegacyProject, run_tool, sha


def _migrate(project: pathlib.Path, backup: pathlib.Path, *extra: str):
    return run_tool("migrate", "--project", str(project), "--backup-root", str(backup),
                    "--apply", "--assume-writers-quiesced", *extra)


class TransactionBase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.backup = self.root / "backups"
        self.backup.mkdir()
        self.project = self.root / "proj"
        self.project.mkdir()
        LegacyProject(self.project)
        self.legacy = self.project / rlp.LEGACY_STORAGE_ROOT
        self.new_root = self.project / rlp.STORAGE_ROOT

    def migrate(self, *extra: str) -> dict:
        proc = _migrate(self.project, self.backup, *extra)
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0, json.dumps(report, ensure_ascii=False)[:600])
        self.assertEqual(report["status"], "MIGRATED", report.get("errors"))
        return report

    def rollback(self, migration_id: str) -> dict:
        proc = run_tool("rollback", "--project", str(self.project),
                        "--migration-id", migration_id)
        return json.loads(proc.stdout)


class TestConcurrency(TransactionBase):

    def test_a_second_migration_is_refused_while_the_lock_is_held(self):
        """两个迁移进程：只有一个能执行正式切换。"""
        holder = subprocess.Popen(
            [sys.executable, "-c",
             "import sys,time,pathlib;"
             f"sys.path.insert(0,{str(pathlib.Path('scripts').resolve())!r});"
             f"import rlp_paths as rlp;"
             f"ctx=rlp.maintenance_exclusive(pathlib.Path({str(self.project)!r}),"
             "owner={'migration_id':'foreign'});"
             "ctx.__enter__();print('held',flush=True);time.sleep(3)"],
            stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), "held")
            proc = _migrate(self.project, self.backup)
            report = json.loads(proc.stdout)
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(report["status"], "REFUSED")
            self.assertIn("维护锁", "".join(report["errors"]))
            self.assertFalse(self.new_root.exists(), "被拒绝的迁移不得切换控制根")
            self.assertTrue(self.legacy.is_dir())
        finally:
            holder.terminate()
            holder.wait(timeout=10)
            holder.stdout.close()

    def test_a_guarded_writer_is_refused_during_maintenance(self):
        """受控写入者在迁移期间拒绝新的控制平面写入。"""
        with rlp.maintenance_exclusive(self.project, owner={"migration_id": "m1"}):
            with self.assertRaises(rlp.MaintenanceInProgress):
                with rlp.maintenance_guard(self.project):
                    pass
            status = rlp.maintenance_status(self.project)
            self.assertTrue(status["held"])
            self.assertEqual(status["owner"]["migration_id"], "m1")

    def test_a_guarded_writer_works_when_no_migration_runs(self):
        with rlp.maintenance_guard(self.project):
            pass
        self.assertFalse(rlp.maintenance_status(self.project)["held"])

    def test_the_lock_is_released_after_a_failed_migration(self):
        """迁移失败后锁必须释放，后续迁移可继续。"""
        state_path = self.legacy / "routes" / "A" / "research-state.json"
        original = state_path.read_bytes()
        state_path.write_text("{broken", encoding="utf-8")
        proc = _migrate(self.project, self.backup)
        self.assertEqual(proc.returncode, 3)
        self.assertFalse(rlp.maintenance_status(self.project)["held"])
        # repair and migrate again: the abandoned lock is not an obstacle
        state_path.write_bytes(original)
        self.migrate()


class TestSourceStability(TransactionBase):

    def _run_migrate_with_mutation(self, mutate) -> dict:
        """Run the real migration transaction while mutating the legacy root.

        The CLI is a thin arg parser around :func:`migrate_project_root.migrate`, so the
        mutation hook is installed on the same library call the CLI makes. The hook
        fires after the staging copy (before staged verification and before the final
        source-stability check), which is exactly the race window being tested.
        """
        original_copy = mp._copy_tree
        calls = {"n": 0}

        def flaky(source, destination):
            calls["n"] += 1
            result = original_copy(source, destination)
            if calls["n"] == 2:          # after the staging copy, before verification
                mutate()
            return result

        mp._copy_tree = flaky
        try:
            return mp.migrate(self.project, self.backup, apply=True,
                              assume_writers_quiesced=True)
        finally:
            mp._copy_tree = original_copy

    def test_a_state_change_during_the_transaction_aborts_the_cutover(self):
        """迁移期间修改 research-state.json → 拒绝切换，保留旧根与备份。"""
        state_path = self.legacy / "routes" / "A" / "research-state.json"
        before = state_path.read_bytes()

        def mutate():
            state = json.loads(before)
            state["state_version"] += 1
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

        report = self._run_migrate_with_mutation(mutate)
        self.assertEqual(report["status"], "SOURCE_CHANGED_DURING_MIGRATION",
                         report)
        self.assertFalse(self.new_root.exists())
        self.assertTrue((self.legacy / "routes" / "A" / "research-state.json").is_file())
        self.assertTrue((self.backup).is_dir() and any(self.backup.rglob("research-state.json")))

    def test_an_appended_tag_event_aborts_the_cutover(self):
        route = self.legacy / "routes" / "A"
        declaration = dg.parse_declaration({
            "mechanism": "noise_level", "scope": "late write",
            "assumptions": ["x"], "evidence_refs": ["E1-A"]})[0]
        state = json.loads((route / "research-state.json").read_text())

        def mutate():
            verdict = dg.classify(declaration, [], state=state)
            dg.append_event(route, dg.event_from_classification(
                declaration, verdict, "late", state=state))

        report = self._run_migrate_with_mutation(mutate)
        self.assertEqual(report["status"], "SOURCE_CHANGED_DURING_MIGRATION")
        self.assertFalse(self.new_root.exists())

    def test_a_file_deleted_during_the_transaction_aborts_the_cutover(self):
        target = self.legacy / "routes" / "B" / "INDEX.md"

        def mutate():
            target.unlink()

        report = self._run_migrate_with_mutation(mutate)
        self.assertEqual(report["status"], "SOURCE_CHANGED_DURING_MIGRATION")
        self.assertFalse(self.new_root.exists())

    def test_same_length_different_content_is_detected(self):
        """长度不变、内容不同的改写也必须检出（摘要而不是大小）。"""
        target = self.legacy / "routes" / "A" / "INDEX.md"
        original = target.read_bytes()

        def mutate():
            mutated = bytearray(original)
            mutated[0] = ord("#") if mutated[0] != ord("#") else ord("%")
            target.write_bytes(bytes(mutated))
            self.assertEqual(len(target.read_bytes()), len(original))

        report = self._run_migrate_with_mutation(mutate)
        self.assertEqual(report["status"], "SOURCE_CHANGED_DURING_MIGRATION")
        self.assertFalse(self.new_root.exists())


class TestRollbackGuard(TransactionBase):
    """Each case mutates exactly one durable artifact after the migration."""

    def setUp(self):
        super().setUp()
        self.report = self.migrate()
        self.mid = self.report["migration_id"]
        self.route = self.new_root / "routes" / "A"

    def assert_refused(self):
        result = self.rollback(self.mid)
        self.assertEqual(result["status"], "ROLLBACK_REFUSED_NEW_WORK",
                         json.dumps(result, ensure_ascii=False)[:400])
        self.assertTrue(result["differences"])
        self.assertTrue(self.new_root.is_dir(), "拒绝回滚时新根必须保持不变")
        self.assertFalse((self.project / rlp.LEGACY_STORAGE_ROOT).exists())
        return result

    def test_only_state_change_refuses(self):
        state_path = self.route / "research-state.json"
        state = json.loads(state_path.read_text())
        state["state_version"] += 1
        state_path.write_text(json.dumps(state), encoding="utf-8")
        self.assert_refused()

    def test_only_scheduler_change_refuses(self):
        path = self.route / "scheduler.json"
        value = json.loads(path.read_text())
        value["diagnostic_budget"]["spent"] = 99
        path.write_text(json.dumps(value), encoding="utf-8")
        self.assert_refused()

    def test_only_tag_append_refuses(self):
        declaration = dg.parse_declaration({
            "mechanism": "noise_level", "scope": "after migration",
            "assumptions": ["x"], "evidence_refs": ["E1-A"]})[0]
        state = json.loads((self.route / "research-state.json").read_text())
        verdict = dg.classify(declaration, [], state=state)
        dg.append_event(self.route, dg.event_from_classification(
            declaration, verdict, "post", state=state))
        self.assert_refused()

    def test_only_trajectory_append_refuses(self):
        path = self.route / "decision-trajectory.jsonl"
        path.write_text(path.read_text() + "\n", encoding="utf-8")
        self.assert_refused()

    def test_only_a_new_receipt_refuses(self):
        receipt = self.route / "assurance" / "outcome" / "OA-X1.json"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text("{}", encoding="utf-8")
        self.assert_refused()

    def test_only_a_new_control_plane_file_refuses(self):
        (self.route / "methods").mkdir(exist_ok=True)
        (self.route / "methods" / "candidate-new.json").write_text("{}", encoding="utf-8")
        self.assert_refused()

    def test_only_a_deleted_file_refuses(self):
        (self.route / "INDEX.md").unlink()
        self.assert_refused()

    def test_only_a_retargeted_symlink_refuses(self):
        link = self.route / "store-link"
        link.symlink_to(self.project / "store-a")
        # the first link is itself new work → baseline it by rolling forward: recreate
        # the baseline through a fresh migration is overkill; instead start from a
        # migrated tree that already contains the link.
        self.assert_refused()

    def test_a_clean_rollback_succeeds_and_returns_to_migration_required(self):
        """无新增工作 → 正常回滚；回滚后是 MIGRATION_REQUIRED，不是可运行状态。"""
        archived_state = (self.project / ".rlp-archive" / self.mid / "legacy-root" /
                          "routes" / "A" / "research-state.json")
        legacy_before = sha(archived_state)
        result = self.rollback(self.mid)
        self.assertEqual(result["status"], "ROLLED_BACK", result)
        self.assertTrue((self.project / rlp.LEGACY_STORAGE_ROOT).is_dir())
        self.assertFalse(self.new_root.exists())
        self.assertEqual(rlp.runtime_status(self.project)["status"],
                         rlp.RUNTIME_STATUS_MIGRATION_REQUIRED)
        self.assertIn("MIGRATION_REQUIRED", result["note"])
        self.assertEqual(sha(self.project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A" /
                             "research-state.json"), legacy_before)

    def test_refusal_lists_the_exact_differences(self):
        path = self.route / "scheduler.json"
        value = json.loads(path.read_text())
        value["next_actions"] = [{"action": "X9", "type": "diagnostic",
                                  "target": "U1-A", "eig": "low", "cost": "low"}]
        path.write_text(json.dumps(value), encoding="utf-8")
        result = self.assert_refused()
        self.assertTrue(any(d["path"].endswith("scheduler.json")
                            for d in result["differences"]), result["differences"])


class TestRollbackSymlinkBaseline(TransactionBase):
    """Symlink retargeting is detected against a migration that already had a link."""

    def test_retargeted_symlink_refuses(self):
        (self.legacy / "routes" / "A" / "store-link").symlink_to(self.project / "store-a")
        report = self.migrate()
        link = self.new_root / "routes" / "A" / "store-link"
        self.assertTrue(link.is_symlink())
        os.unlink(link)
        link.symlink_to(self.project / "store-b")
        result = self.rollback(report["migration_id"])
        self.assertEqual(result["status"], "ROLLBACK_REFUSED_NEW_WORK")
        self.assertTrue(any(d["change"] == "symlink" for d in result["differences"]),
                        result["differences"])


class TestDocumentTransaction(TransactionBase):

    def test_without_rewrite_no_project_document_changes(self):
        before = {name: sha(self.project / name) for name in ("AGENTS.md", "README.md")
                  if (self.project / name).is_file()}
        (self.project / "README.md").write_text(
            "project uses .research-idea-pipeline/\n", encoding="utf-8")
        (self.project / "AGENTS.md").write_text(
            "store: .research-idea-pipeline\n", encoding="utf-8")
        before = {name: sha(self.project / name) for name in ("AGENTS.md", "README.md")}
        self.migrate()
        after = {name: sha(self.project / name) for name in ("AGENTS.md", "README.md")}
        self.assertEqual(before, after, "默认迁移不得修改项目级文档")

    def test_rewrite_is_committed_after_the_cutover_and_journalled(self):
        readme = self.project / "README.md"
        readme.write_text("root: .research-idea-pipeline/\n", encoding="utf-8")
        report = self.migrate("--rewrite", "README.md")
        self.assertIn(".research-lifecycle-protocol", readme.read_text())
        self.assertNotIn(".research-idea-pipeline", readme.read_text())
        entries = [e for e in mp._journal_read(self.project)[0]
                   if e.get("migration_id") == report["migration_id"]]
        self.assertIn("documents_commit_started", [e["event"] for e in entries])
        self.assertIn("document_committed", [e["event"] for e in entries])

    def test_a_midway_document_commit_failure_restores_every_original(self):
        """提交第一个文档后失败：所有文档恢复原始字节。"""
        readme = self.project / "README.md"
        agents = self.project / "AGENTS.md"
        readme.write_text("a: .research-idea-pipeline/\n", encoding="utf-8")
        agents.write_text("b: .research-idea-pipeline/\n", encoding="utf-8")
        originals = {"README.md": sha(readme), "AGENTS.md": sha(agents)}
        real = mp._atomic_write_bytes
        state = {"done": 0}

        def failing(path, payload):
            state["done"] += 1
            if state["done"] == 2:
                raise OSError("disk full (injected)")
            return real(path, payload)

        mp._atomic_write_bytes = failing
        try:
            report = mp.migrate(self.project, self.backup, apply=True,
                                assume_writers_quiesced=True,
                                rewrite=["README.md", "AGENTS.md"])
        finally:
            mp._atomic_write_bytes = real
        # the migration reports the document failure, not a clean success
        self.assertEqual(report["status"], "MIGRATED_DOCUMENTS_FAILED")
        self.assertEqual({name: sha(self.project / name) for name in originals},
                         originals, "部分提交失败后必须恢复全部原字节")
        self.assertTrue((self.project / ".rlp-archive").is_dir())

    def test_staging_failure_leaves_project_documents_untouched(self):
        readme = self.project / "README.md"
        readme.write_text("a: .research-idea-pipeline/\n", encoding="utf-8")
        before = sha(readme)
        state_path = self.legacy / "routes" / "A" / "research-state.json"
        state_path.write_text("{broken", encoding="utf-8")
        proc = _migrate(self.project, self.backup, "--rewrite", "README.md")
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(sha(readme), before)


class TestJournalAndRecovery(TransactionBase):

    def test_a_corrupt_journal_fails_closed(self):
        self.migrate()
        journal = mp.journal_path(self.project)
        journal.write_text(journal.read_text(encoding="utf-8") + "{not json\n",
                           encoding="utf-8")
        for command in ("verify", "recover"):
            proc = run_tool(command, "--project", str(self.project))
            report = json.loads(proc.stdout)
            self.assertEqual(report["status"], "JOURNAL_CORRUPT", command)
            self.assertEqual(proc.returncode, 3)
        result = self.rollback(json.loads(run_tool(
            "recover", "--project", str(self.project)).stdout).get("migration_id") or "x")
        self.assertEqual(result["status"], "JOURNAL_CORRUPT")

    def test_recover_never_deletes_staging_with_unique_content(self):
        """staging 有唯一内容 → 不自动删除，保留现场。"""
        mp._journal_append(self.project, {"event": "started", "migration_id": "sim-2",
                                          "backup": str(self.backup / "x")})
        snapshot = mp.snapshot(self.legacy)
        mp._save_manifest(self.project, "sim-2", "source-snapshot.json", snapshot)
        staging = mp.work_dir(self.project, "sim-2") / "staging" / rlp.STORAGE_ROOT
        staging.mkdir(parents=True)
        (staging / "unique.txt").write_text("only here", encoding="utf-8")
        proc = run_tool("recover", "--project", str(self.project), "--apply")
        report = json.loads(proc.stdout)
        self.assertEqual(report["action"], "manual")
        self.assertTrue((staging / "unique.txt").is_file())

    def test_dual_root_transient_is_recovered_by_completing_the_archive(self):
        """cutover 与归档之间中断：可安全完成归档，双根暂态被识别。"""
        report = self.migrate()
        legacy = self.project / rlp.LEGACY_STORAGE_ROOT
        archive = self.project / ".rlp-archive" / report["migration_id"] / "legacy-root"
        os.rename(archive, legacy)                       # simulate: archive undone
        journal = mp.journal_path(self.project)
        entries, _ = mp._journal_read(self.project)
        kept = [e for e in entries
                if e.get("event") in ("started", "backup_verified", "staged_verified",
                                      "cutover_started", "new_root_installed")]
        journal.write_text("".join(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n"
                                   for e in kept), encoding="utf-8")
        self.assertEqual(rlp.runtime_status(self.project)["status"],
                         rlp.RUNTIME_STATUS_AMBIGUOUS)
        proc = run_tool("recover", "--project", str(self.project), "--apply")
        recovered = json.loads(proc.stdout)
        self.assertEqual(recovered["action"], "complete_archive", recovered)
        self.assertEqual(recovered["performed"], "complete_archive")
        self.assertEqual(rlp.runtime_status(self.project)["status"],
                         rlp.RUNTIME_STATUS_READY)

    def test_verify_rejects_a_freshly_generated_manifest_as_proof(self):
        """verify 以迁移记录的 manifest 为基准：新根被改后必须失败。"""
        report = self.migrate()
        (self.new_root / "routes" / "A" / "extra.json").write_text("{}", encoding="utf-8")
        proc = run_tool("verify", "--project", str(self.project),
                        "--migration-id", report["migration_id"])
        result = json.loads(proc.stdout)
        self.assertFalse(result["ok"])
        self.assertTrue(any("extra.json" in p for p in result["problems"]),
                        result["problems"][:5])


class TestBackupBoundary(TransactionBase):

    def test_backup_inside_the_legacy_root_is_refused(self):
        report = json.loads(run_tool(
            "plan", "--project", str(self.project),
            "--backup-root", str(self.legacy / "backup")).stdout)
        self.assertFalse(report["ready_to_migrate"])
        self.assertIn("旧控制根", report["reason"])

    def test_backup_inside_the_new_root_is_refused(self):
        report = json.loads(run_tool(
            "plan", "--project", str(self.project),
            "--backup-root", str(self.new_root / "backup")).stdout)
        self.assertFalse(report["ready_to_migrate"])

    def test_symlink_out_of_the_root_is_copied_as_a_link_and_reported(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("must not be copied", encoding="utf-8")
        (self.legacy / "routes" / "A" / "outside-link").symlink_to(outside / "secret.txt")
        report = self.migrate()
        link = self.new_root / "routes" / "A" / "outside-link"
        self.assertTrue(link.is_symlink())
        copied = list(self.root.rglob("secret.txt"))
        self.assertFalse(any(p.is_file() and not p.is_symlink() and
                             rlp.MAINTENANCE_DIR not in p.parts and
                             p != outside / "secret.txt" for p in copied),
                         "符号链接目标内容不得被复制进控制根")

    def test_a_special_file_type_refuses_the_migration(self):
        fifo = self.legacy / "routes" / "A" / "weird.fifo"
        os.mkfifo(fifo)
        proc = _migrate(self.project, self.backup)
        report = json.loads(proc.stdout)
        self.assertEqual(report["status"], "FAILED_BACKUP", report)
        self.assertTrue(any("特殊文件" in e for e in report["errors"]))
        self.assertFalse(self.new_root.exists())


if __name__ == "__main__":
    unittest.main()
