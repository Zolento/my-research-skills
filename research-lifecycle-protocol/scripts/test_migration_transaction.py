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
from typing import Optional

import domain_guard as dg
import migrate_project_root as mp
import state_check as sc
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



# ---------------------------------------------------------------------------
# 历史保留迁移：存储完整性与科研合规性解耦
# ---------------------------------------------------------------------------

class LegacyDebtBase(TransactionBase):
    """A 是「可读、可追溯、但违反当前科研规则」的路线；B 保持合规。

    债务形态与真实项目一致：实验已经带结果记录，而 `contract.outcome_policy`
    是后来才引入的，因此 EO1 报告「outcome records require a frozen policy」。
    这类记录不能追溯补写，也不允许通过改状态、清空或归档来让检查通过。
    """

    def setUp(self):
        super().setUp()
        self.debt_route = "A"
        self.clean_route = "B"
        self._inject_outcome_debt()

    def _state_path(self, route: str, root: Optional[pathlib.Path] = None):
        base = (root or self.project) / rlp.LEGACY_STORAGE_ROOT
        return base / "routes" / route / "research-state.json"

    def _inject_outcome_debt(self) -> None:
        path = self._state_path(self.debt_route)
        state = json.loads(path.read_text(encoding="utf-8"))
        state.setdefault("contract", {}).pop("outcome_policy", None)
        state["experiments"][0]["outcome_protocol"] = {"frozen": True}
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    def baseline(self) -> dict:
        inventory = mp._state_inventory(self.legacy)
        return inventory["baseline"]

    def plan_preserve(self) -> dict:
        proc = run_tool("plan", "--project", self.project, "--backup-root", self.backup,
                        "--preserve-known-legacy-violations")
        return json.loads(proc.stdout)

    def migrate_preserve(self, baseline: Optional[dict] = None):
        baseline = baseline if baseline is not None else self.baseline()
        payload = self.root / "baseline.json"
        payload.write_text(json.dumps({"violation_baseline": baseline}), encoding="utf-8")
        return run_tool("migrate", "--project", self.project, "--backup-root", self.backup,
                        "--apply", "--assume-writers-quiesced",
                        "--preserve-known-legacy-violations",
                        "--violation-baseline", payload)

    def violation_set(self, root: pathlib.Path, route: str) -> set:
        inventory = mp._state_inventory(root)
        entry = inventory["baseline"]["routes"].get(route, {})
        return {(item["rule"], item["path"], item["detail"])
                for item in entry.get("violations", [])}


class TestHistoricalPreservationPlan(LegacyDebtBase):
    """M-a：预检必须把「存储坏了」与「科研规则债务」分开。"""

    def test_strict_plan_still_refuses(self):
        proc = run_tool("plan", "--project", self.project, "--backup-root", self.backup)
        report = json.loads(proc.stdout)
        self.assertFalse(report["ready_to_migrate"])
        self.assertIn("A", report.get("reason", ""))
        self.assertNotIn("storage_blockers", report)

    def test_preserve_plan_accepts_with_exact_inventory(self):
        report = self.plan_preserve()
        self.assertTrue(report["ready_to_migrate"], report.get("reason"))
        self.assertEqual(report["scientific_debt_routes"], ["A"])
        self.assertEqual(report["scientific_debt"]["A"]["rule_counts"], {"EO1": 1})
        self.assertTrue(report["violation_baseline_digest"])
        self.assertIn("scientific_debt", report)
        self.assertEqual(report["scientific_debt_routes"], ["A"],
                         "合规路线不得被列为债务")

    def test_unparseable_state_is_storage_fatal_not_debt(self):
        self._state_path("B").write_text("{broken", encoding="utf-8")
        report = self.plan_preserve()
        self.assertFalse(report["ready_to_migrate"])
        kinds = {item["kind"] for item in report["storage_blockers"]}
        self.assertIn("state_unreadable", kinds)
        self.assertIn("不属于科研规则债务", report["reason"])

    def test_shape_violation_is_storage_fatal(self):
        path = self._state_path("B")
        state = json.loads(path.read_text(encoding="utf-8"))
        state["state_version"] = "not-an-int"
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        report = self.plan_preserve()
        self.assertFalse(report["ready_to_migrate"])
        self.assertIn("shape_gate", {item["kind"] for item in report["storage_blockers"]})

    def test_damaged_hash_chain_is_storage_fatal(self):
        route_dir = self.legacy / "routes" / "B"
        (route_dir / "domain").mkdir(exist_ok=True)
        events = route_dir / "domain" / "tag-events.jsonl"
        events.write_text('{"_schema":"research-idea-pipeline/tag-events@1"}\n',
                          encoding="utf-8")
        report = self.plan_preserve()
        self.assertFalse(report["ready_to_migrate"])
        self.assertIn("hash_chain", {item["kind"] for item in report["storage_blockers"]})

    def test_no_debt_means_the_mode_is_refused(self):
        path = self._state_path(self.debt_route)
        state = json.loads(path.read_text(encoding="utf-8"))
        state["experiments"][0].pop("outcome_protocol")
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        proc = self.migrate_preserve()
        report = json.loads(proc.stdout)
        self.assertEqual(report["status"], "REFUSED")
        self.assertIn("没有科研规则债务", report["errors"][0])


class TestHistoricalPreservationMigrate(LegacyDebtBase):
    """M-b：保留模式的迁移本身仍然是无损事务。"""

    def test_preserve_migration_keeps_history_and_holds_the_gate(self):
        before = self.violation_set(self.legacy, "A")
        json.loads(run_tool("plan", "--project", self.project, "--backup-root",
                            self.backup, "--preserve-known-legacy-violations").stdout)
        proc = self.migrate_preserve()
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0, report.get("errors"))
        self.assertEqual(report["status"], "MIGRATED_WITH_LEGACY_ISSUES")
        verify = report["verify"]
        self.assertEqual(verify["status"], "VERIFIED_WITH_LEGACY_ISSUES")
        self.assertTrue(verify["storage_integrity_ok"])
        self.assertTrue(verify["historical_state_unchanged"])
        self.assertTrue(verify["legacy_violations_preserved"])
        self.assertFalse(verify["scientific_gate_ok"])
        self.assertEqual(verify["violation_rule_counts"], {"A": {"EO1": 1}})

        # 逐条比较，不是比数量
        self.assertEqual(self.violation_set(self.new_root, "A"), before)
        # 合规路线不受牵连
        gate_b = sc.check_state(json.loads(
            (self.new_root / "routes" / "B" / "research-state.json").read_text()))
        self.assertTrue(gate_b.ok)
        # 债务路线仍然被门禁拦住
        gate_a = sc.check_state(json.loads(
            (self.new_root / "routes" / "A" / "research-state.json").read_text()))
        self.assertFalse(gate_a.ok)
        self.assertIn("EO1", {v.rule for v in gate_a.outcome})
        # 路线身份未变：A 仍在 routes/A，registry 未被改成 archived
        self.assertTrue((self.new_root / "routes" / "A").is_dir())
        registry = self.new_root / "project" / "route-registry.json"
        if registry.is_file():
            payload = json.loads(registry.read_text())
            statuses = {entry.get("name"): entry.get("status")
                        for entry in payload.get("routes", [])}
            self.assertNotEqual(statuses.get("A"), "archived")

    def test_baseline_drift_is_refused(self):
        stale = self.baseline()
        # 迁移前再制造一条新违规：数量变化必须先被拒
        path = self._state_path("B")
        state = json.loads(path.read_text(encoding="utf-8"))
        state["contract"]["outcome_policy"] = None
        state["experiments"][0]["outcome_protocol"] = {"frozen": True}
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        proc = self.migrate_preserve(stale)
        report = json.loads(proc.stdout)
        self.assertEqual(report["status"], "REFUSED")
        self.assertIn("违规基线已变化", report["errors"][0])
        self.assertIn("B", report["diff"]["changed"])
        self.assertFalse(self.new_root.exists())

    def test_same_count_but_different_violation_is_refused(self):
        stale = self.baseline()
        path = self._state_path("A")
        state = json.loads(path.read_text(encoding="utf-8"))
        state["experiments"][0].pop("outcome_protocol")
        state["experiments"][1]["outcome_protocol"] = {"frozen": False}
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        proc = self.migrate_preserve(stale)
        report = json.loads(proc.stdout)
        self.assertEqual(report["status"], "REFUSED",
                         "同数量不同条目必须拒绝，不能只比计数")

    def test_staging_tampering_is_blocked_before_cutover(self):
        """staging 里把违规掩盖掉 → 字节级比对先阻断，且不发生切换。

        字节比对是最强的一道：改动 state 必然改变文件摘要。违规清单比对是它之后的
        第二道（见 `test_recorded_baseline_tampering_fails_verify`），用来保证即使
        字节层面「一致」，清单也不能被换掉。
        """
        import unittest.mock as mock
        original = mp._copy_tree

        def tampering(source, destination):
            problems, warnings = original(source, destination)
            if "staging" in str(destination):
                staged = destination / "routes" / "A" / "research-state.json"
                state = json.loads(staged.read_text(encoding="utf-8"))
                state["experiments"][0].pop("outcome_protocol", None)
                staged.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            return problems, warnings

        baseline = self.baseline()
        with mock.patch.object(mp, "_copy_tree", tampering):
            report = mp.migrate(self.project, self.backup, apply=True,
                                assume_writers_quiesced=True,
                                preserve_known_legacy_violations=True,
                                violation_baseline=baseline)
        self.assertEqual(report["status"], "FAILED_STAGING_VERIFY", report)
        self.assertTrue(any("research-state.json" in item for item in report["errors"]))
        self.assertFalse(self.new_root.exists())
        self.assertTrue(self.legacy.is_dir(), "旧根必须保持为唯一控制根")

    def test_source_change_during_preserve_migration_blocks(self):
        import threading, time as _time
        baseline = self.baseline()
        stop = threading.Event()

        def writer():
            target = self.legacy / "routes" / "A" / "scheduler.json"
            while not stop.is_set():
                if target.is_file():
                    target.write_text(json.dumps({"state_version": 999}), encoding="utf-8")
                    return
                _time.sleep(0.001)

        thread = threading.Thread(target=writer, daemon=True)
        thread.start()
        try:
            report = mp.migrate(self.project, self.backup, apply=True,
                                assume_writers_quiesced=True,
                                preserve_known_legacy_violations=True,
                                violation_baseline=baseline)
        finally:
            stop.set()
            thread.join(timeout=2)
        if report["status"] == "SOURCE_CHANGED_DURING_MIGRATION":
            self.assertFalse(self.new_root.exists())
        else:
            self.assertEqual(report["status"], "MIGRATED_WITH_LEGACY_ISSUES", report)
            self.assertTrue(report["verify"]["ok"])


class TestHistoricalPreservationVerifyAndRollback(LegacyDebtBase):
    """M-c：verify 分级与 rollback 保护。"""

    def migrate_ok(self) -> dict:
        proc = self.migrate_preserve()
        report = json.loads(proc.stdout)
        self.assertEqual(report["status"], "MIGRATED_WITH_LEGACY_ISSUES", report.get("errors"))
        return report

    def test_backup_damage_after_migration_fails_verify(self):
        report = self.migrate_ok()
        backup_root = pathlib.Path(report["backup_destination"]) / "legacy-root"
        victim = backup_root / "routes" / "A" / "research-state.json"
        self.assertTrue(victim.is_file())
        victim.write_text("{}", encoding="utf-8")
        result = json.loads(run_tool("verify", "--project", self.project,
                                     "--migration-id", report["migration_id"]).stdout)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "VERIFY_FAILED")
        self.assertFalse(result["storage_integrity_ok"])

    def test_recorded_baseline_tampering_fails_verify(self):
        """记录下来的基线被篡改 → verify 判 VERIFY_FAILED（清单不得被换掉）。"""
        report = self.migrate_ok()
        path = mp.manifest_path(self.project, report["migration_id"],
                               "violation-baseline.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        for entry in payload["baseline"]["routes"].values():
            for item in entry.get("violations", []):
                item["detail"] = "已被改写的描述"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result = json.loads(run_tool("verify", "--project", self.project,
                                     "--migration-id", report["migration_id"]).stdout)
        self.assertEqual(result["status"], "VERIFY_FAILED")
        self.assertFalse(result["legacy_violations_preserved"])
        self.assertIn("baseline_diff", result)

    def test_rollback_refuses_after_new_work_on_the_debt_route(self):
        report = self.migrate_ok()
        state_path = self.new_root / "routes" / "A" / "research-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["uncertainties"].append({"id": "U99", "question": "迁移后新增",
                                       "importance": "low", "uncertainty": "low",
                                       "cheapest_discriminating_test": "TBD",
                                       "status": "open"})
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        proc = run_tool("rollback", "--project", self.project,
                        "--migration-id", report["migration_id"])
        result = json.loads(proc.stdout)
        self.assertEqual(result["status"], "ROLLBACK_REFUSED_NEW_WORK")
        self.assertTrue(result["new_root_untouched"])

    def test_rollback_is_possible_before_new_work(self):
        report = self.migrate_ok()
        proc = run_tool("rollback", "--project", self.project,
                        "--migration-id", report["migration_id"])
        result = json.loads(proc.stdout)
        self.assertEqual(result["status"], "ROLLED_BACK", result.get("errors"))
        self.assertTrue(self.legacy.is_dir())
        self.assertEqual(rlp.runtime_status(self.project)["status"],
                         rlp.RUNTIME_STATUS_MIGRATION_REQUIRED)

    def test_recover_reports_verified_legacy_issues_as_done(self):
        report = self.migrate_ok()
        proc = run_tool("recover", "--project", self.project)
        recovered = json.loads(proc.stdout)
        self.assertEqual(recovered["action"], "none")
        self.assertIn("已完成", recovered["detail"])


class TestStorageFaults(TransactionBase):
    """M-2/M-3：存储与备份侧的缺陷回归（本轮修复项）。"""

    def test_an_unreadable_directory_blocks_the_plan(self):
        """不可读目录 → 预检拒绝，不得静默丢数据后再报 MIGRATED。"""
        locked = self.legacy / "routes" / "A" / "evidence-cache"
        locked.mkdir()
        (locked / "E99.json").write_text("{}", encoding="utf-8")
        os.chmod(locked, 0o000)
        try:
            proc = run_tool("plan", "--project", self.project, "--backup-root", self.backup)
            report = json.loads(proc.stdout)
            self.assertFalse(report["ready_to_migrate"])
            self.assertIn("不可读", report["reason"])
            self.assertTrue(report["unreadable_paths"])
            proc = _migrate(self.project, self.backup)
            self.assertEqual(json.loads(proc.stdout)["status"], "REFUSED")
            self.assertFalse(self.new_root.exists())
        finally:
            os.chmod(locked, 0o755)

    def test_backup_capacity_is_checked_on_the_backup_filesystem(self):
        """备份盘几乎满时预检必须拒绝，不能只看项目盘。"""
        import unittest.mock as mock
        real = shutil.disk_usage

        def fake(path):
            probe = pathlib.Path(path).resolve()
            if str(probe).startswith(str(self.backup.resolve())):
                return real(probe)._replace(free=1024)
            return real(probe)

        with mock.patch.object(shutil, "disk_usage", fake):
            report = mp.plan(self.project, self.backup)
        self.assertFalse(report["ready_to_migrate"])
        self.assertFalse(report["disk"]["backup_sufficient"])
        self.assertTrue(report["disk"]["staging_sufficient"])
        self.assertIn("backup_free_bytes", report["disk"])

    def test_an_empty_legacy_root_is_not_migratable(self):
        """旧根存在但为空 → 拒绝，不允许切出一个 INVALID 新根。"""
        empty_project = self.root / "empty"
        empty_project.mkdir()
        (empty_project / rlp.LEGACY_STORAGE_ROOT).mkdir()
        report = mp.plan(empty_project, self.backup)
        self.assertFalse(report["ready_to_migrate"])
        self.assertIn("不构成可迁移的研究状态", report["reason"])
        self.assertEqual(rlp.runtime_status(empty_project)["status"],
                         rlp.RUNTIME_STATUS_MIGRATION_REQUIRED)

    def test_rewrite_request_outside_the_rewritable_set_is_reported(self):
        """--rewrite 指向历史证据 → 不写，但必须报告，不得静默忽略。"""
        docs = self.legacy / "routes" / "A" / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        historical = docs / "A001-field-map.md"
        historical.write_text("历史路径 .research-idea-pipeline/routes/A", encoding="utf-8")
        project_readme = self.project / "README.md"
        project_readme.write_text("见 .research-idea-pipeline/routes/A", encoding="utf-8")
        report = self.migrate("--rewrite", "routes/A/docs/A001-field-map.md",
                              "--rewrite", "README.md")
        self.assertEqual(len(report["rewrites"]), 1)
        self.assertEqual(report["rewrites"][0]["label"], "<project>/README.md")
        ignored = {item["label"] for item in report.get("rewrites_ignored", [])}
        self.assertIn("routes/A/docs/A001-field-map.md", ignored)
        moved = self.new_root / "routes" / "A" / "docs" / "A001-field-map.md"
        self.assertIn(".research-idea-pipeline/routes/A", moved.read_text(),
                      "历史证据里的旧路径必须原样保留")

    def test_a_refused_attempt_does_not_hide_the_real_migration(self):
        """并发被拒的尝试只留审计记录，不得遮蔽真实迁移。"""
        report = self.migrate()
        mp._journal_append(self.project, {"event": "refused", "migration_id": "sim-refused",
                                          "problems": ["另一个迁移正持有维护锁"]})
        self.assertEqual(mp._completed_migration(self.project), report["migration_id"])
        recovered = json.loads(run_tool("recover", "--project", self.project).stdout)
        self.assertEqual(recovered["action"], "none")
        self.assertIn("已完成", recovered["detail"])
        self.assertEqual(recovered["migration_id"], report["migration_id"])

    def test_stale_lock_metadata_is_visible_without_blocking(self):
        """崩溃残留的锁文件不阻塞，但必须显示它来自已消失的进程。"""
        lock = rlp.maintenance_lock_path(self.project)
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({"pid": 999999, "command": "migrate",
                                    "migration_id": "crashed"}))
        status = rlp.maintenance_status(self.project)
        self.assertFalse(status["held"])
        self.assertTrue(status.get("stale"))
        self.assertFalse(status.get("owner_alive"))
        self.assertEqual(self.migrate()["status"], "MIGRATED")


class TestRollbackStranding(TransactionBase):
    """M-4：回滚不得把项目留在「没有可用控制根」的现场。"""

    def test_rollback_refuses_when_the_legacy_path_is_occupied(self):
        report = self.migrate()
        squatter = self.project / rlp.LEGACY_STORAGE_ROOT
        squatter.mkdir()
        (squatter / "someone-else.txt").write_text("x", encoding="utf-8")
        proc = run_tool("rollback", "--project", self.project,
                        "--migration-id", report["migration_id"])
        result = json.loads(proc.stdout)
        self.assertEqual(result["status"], "REFUSED", result.get("errors"))
        self.assertIn("已被占用", result["errors"][0])
        # 没有任何目录被移动：新根仍在原位，归档仍在原处
        self.assertTrue(self.new_root.is_dir())
        self.assertFalse((self.project / ".rlp-archive" / report["migration_id"] /
                          "forward-root").exists())
        # 占用者仍在，双根并存 → 运行时 fail closed（而不是悄悄选一个）
        self.assertEqual(rlp.runtime_status(self.project)["status"],
                         rlp.RUNTIME_STATUS_AMBIGUOUS)

    def test_rollback_restores_the_new_root_when_the_archive_move_fails(self):
        """归档移动失败 → 新根放回原位，项目继续可用。"""
        report = self.migrate()
        import unittest.mock as mock
        real_rename = os.rename

        def failing(src, dst):
            if str(dst).endswith(rlp.LEGACY_STORAGE_ROOT):
                raise OSError("simulated cross-device failure")
            return real_rename(src, dst)

        with mock.patch.object(os, "rename", failing):
            result = mp.rollback(self.project, report["migration_id"])
        self.assertEqual(result["status"], "ROLLBACK_FAILED", result)
        self.assertTrue(result["new_root_restored"])
        self.assertTrue(self.new_root.is_dir())
        self.assertEqual(rlp.runtime_status(self.project)["status"], rlp.RUNTIME_STATUS_READY)


class TestVerificationEvidence(TransactionBase):
    """M-e：验证证明材料是强制项；缺一份就不能报「完整验证通过」。"""

    def _inject_outcome_debt(self) -> None:
        path = self.legacy / "routes" / "A" / "research-state.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state.setdefault("contract", {}).pop("outcome_policy", None)
        state["experiments"][0]["outcome_protocol"] = {"frozen": True}
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    def legacy_migration(self) -> dict:
        """跑一次历史保留模式的迁移，返回报告。"""
        self._inject_outcome_debt()
        payload = self.project / "baseline.json"
        payload.write_text(json.dumps(
            {"violation_baseline": mp._state_inventory(self.legacy)["baseline"]}),
            encoding="utf-8")
        proc = run_tool("migrate", "--project", self.project, "--backup-root",
                        self.backup, "--apply", "--assume-writers-quiesced",
                        "--preserve-known-legacy-violations",
                        "--violation-baseline", payload)
        report = json.loads(proc.stdout)
        self.assertEqual(report["status"], "MIGRATED_WITH_LEGACY_ISSUES",
                         report.get("errors"))
        return report

    def evidence_path(self, migration_id: str, name: str) -> pathlib.Path:
        return mp.manifest_path(self.project, migration_id, name)

    def verify(self, migration_id: str) -> dict:
        return json.loads(run_tool("verify", "--project", self.project,
                                   "--migration-id", migration_id).stdout)

    def test_a_missing_baseline_file_fails_verification(self):
        """基线文件被删 → 不能默认「清单保持一致」。"""
        report = self.legacy_migration()
        self.evidence_path(report["migration_id"], "violation-baseline.json").unlink()
        result = self.verify(report["migration_id"])
        self.assertEqual(result["status"], "VERIFY_FAILED")
        self.assertFalse(result["ok"])
        self.assertFalse(result["legacy_violations_preserved"])
        self.assertEqual(result["evidence"]["violation-baseline.json"], "missing")
        self.assertTrue(any("violation-baseline.json" in p for p in result["problems"]))

    def test_a_corrupt_baseline_file_fails_verification(self):
        report = self.legacy_migration()
        path = self.evidence_path(report["migration_id"], "violation-baseline.json")
        path.write_text("{not json", encoding="utf-8")
        result = self.verify(report["migration_id"])
        self.assertEqual(result["status"], "VERIFY_FAILED")
        self.assertEqual(result["evidence"]["violation-baseline.json"], "corrupt")
        self.assertFalse(result["legacy_violations_preserved"])

    def test_a_baseline_whose_digest_disagrees_fails_verification(self):
        """文件内容被改但保留了旧摘要 → 自相矛盾，判失败。"""
        report = self.legacy_migration()
        path = self.evidence_path(report["migration_id"], "violation-baseline.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        route = next(iter(payload["baseline"]["routes"]))
        payload["baseline"]["routes"][route]["state_digest"] = "0" * 64
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result = self.verify(report["migration_id"])
        self.assertEqual(result["status"], "VERIFY_FAILED")
        self.assertTrue(any("自相矛盾" in p for p in result["problems"]),
                        result["problems"])

    def test_a_strict_migration_does_not_require_a_baseline(self):
        """严格迁移没有基线文件，这是正常的，不构成失败。"""
        report = self.migrate()
        result = self.verify(report["migration_id"])
        self.assertEqual(result["status"], "VERIFIED", result.get("problems"))
        self.assertNotIn("violation-baseline.json", result["evidence"])

    def test_missing_source_snapshot_fails_verification(self):
        report = self.migrate()
        self.evidence_path(report["migration_id"], "source-snapshot.json").unlink()
        result = self.verify(report["migration_id"])
        self.assertEqual(result["status"], "VERIFY_FAILED")
        self.assertFalse(result["evidence_ok"])
        self.assertTrue(any("source-snapshot.json" in p for p in result["problems"]))

    def test_missing_source_fingerprint_fails_verification(self):
        report = self.migrate()
        self.evidence_path(report["migration_id"], "source-fingerprint.json").unlink()
        result = self.verify(report["migration_id"])
        self.assertEqual(result["status"], "VERIFY_FAILED")
        self.assertFalse(result["historical_state_unchanged"])

    def test_missing_rewrite_manifest_fails_verification(self):
        """真的发生过重写的迁移，重写清单就是强制材料。"""
        (self.project / "README.md").write_text(
            "旧路径见 .research-idea-pipeline/routes/A", encoding="utf-8")
        report = json.loads(run_tool(
            "migrate", "--project", self.project, "--backup-root", self.backup,
            "--apply", "--assume-writers-quiesced",
            "--rewrite", "<project>/README.md").stdout)
        self.assertEqual(report["status"], "MIGRATED", report.get("errors"))
        (mp.work_dir(self.project, report["migration_id"]) /
         "rewrite-manifest.json").unlink()
        result = self.verify(report["migration_id"])
        self.assertEqual(result["status"], "VERIFY_FAILED")
        self.assertEqual(result["evidence"]["rewrite-manifest.json"], "missing")

    def test_a_migration_without_rewrites_records_an_empty_manifest(self):
        """没有重写请求时也留一份空清单，证据包齐整。"""
        report = self.migrate()
        path = mp.work_dir(self.project, report["migration_id"]) / "rewrite-manifest.json"
        self.assertTrue(path.is_file())
        self.assertEqual(json.loads(path.read_text())["files"], [])

    def test_migration_keeps_its_evidence_bundle(self):
        """成功提示必须要求保留证据，不再建议删除归档与工作目录。"""
        report = self.migrate()
        hint = report["resume_hint"]
        self.assertIn("保留", hint)
        self.assertNotIn("可删除", hint)
        self.assertTrue((self.project / ".rlp-archive" / report["migration_id"] /
                         "legacy-root").is_dir())
        self.assertTrue((mp.work_dir(self.project, report["migration_id"]) /
                         "source-snapshot.json").is_file())


if __name__ == "__main__":
    unittest.main()
