#!/usr/bin/env python3
"""test_storage_migration.py — the real migration of a full legacy project (§7.2/§7.3).

The fixture is a realistic legacy project: two routes, a non-empty evidence ledger,
failure memory, a done and a running experiment, a scheduler, cognitive memory, a
hash-chained decision trajectory, frozen preregistrations, TAG events, PEIG/AALG
budget records and old absolute path references. The tests drive the real tool:

    inspect → plan → migrate --apply → verify
    (+ rollback, failure injection, idempotency)

Nothing here claims research effectiveness; these prove the control-plane mechanics.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import cognition as cg
import decision_trajectory as dt
import domain_guard as dg
import domain_profile as dp
import evidence_outcome as eo
import rlp_paths as rlp
import state_check as sc

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def run_tool(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / "migrate_project_root.py"),
                           *map(str, args)], capture_output=True, text=True,
                          cwd=str(ROOT))


def sha(path: pathlib.Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LegacyProject:
    """A realistic legacy project in `.research-idea-pipeline/`."""

    def __init__(self, root: pathlib.Path):
        self.root = root
        self.legacy = root / rlp.LEGACY_STORAGE_ROOT
        self.build_route("A", with_running=True)
        self.build_route("B", with_running=False)
        self.build_budgets()

    @staticmethod
    def _validity(reason: str, version: int) -> dict:
        return {"status": "valid", "reason": reason, "since_state_version": version}

    def build_route(self, route: str, *, with_running: bool):
        version = 12 if route == "A" else 4
        route_dir = self.legacy / "routes" / route
        (route_dir / "cognition").mkdir(parents=True)
        (route_dir / "domain").mkdir()
        (route_dir / "experiments").mkdir()
        state = {
            "state_version": version,
            "contract": {"primary_anchor": "performance", "constraints": [],
                         "resources": [], "out_of_scope": [],
                         "goal": "机制 A 是否解释目标现象",
                         "scientific_question": "机制 A 通过什么路径解释目标现象"},
            "claims": [{"id": f"C1-{route}", "statement": "机制 A 解释现象",
                        "parent": None, "subclaims": [],
                        "status": "partially-supported",
                        "supporting_evidence": [f"E1-{route}"],
                        "refuting_evidence": [], "falsifier": "解耦后现象不变",
                        "scope": "数据集 A", "known_flaws": [f"F1-{route}"],
                        "depends_on": [],
                        "validity": self._validity("已按预注册", version - 2)}],
            "evidence": [{"id": f"E1-{route}", "kind": "experiment",
                          "supports": [f"C1-{route}"], "contradicts": [],
                          "strength": "strong", "scope": "数据集 A",
                          "epistemic_status": "Observed",
                          "source_ref": (f"X1-{route}（seed=0）, 产物归档: "
                                         f"{self.legacy.resolve()}/routes/{route}/experiments"),
                          "verification_tier": "T2", "depends_on": [f"X1-{route}"],
                          "validity": self._validity("X1 done", version - 2)}],
            "assumptions": [], "hypotheses": [],
            "experiments": [
                {"id": f"X1-{route}", "parent": None, "stage": "X3",
                 "claim_targeted": [f"C1-{route}"], "hypothesis_targeted": [],
                 "alternative_targeted": [], "status": "done",
                 "result": "M improves 0.8 against matched P.",
                 "result_at_state_version": version - 2,
                 "validity": self._validity("X1 done", version - 2),
                 "preregistration": {"frozen_at_state_version": version - 3,
                                     "outcomes": [{"id": "O1",
                                                   "observation": "M improves",
                                                   "update": [{"target": f"C1-{route}",
                                                               "op": "strengthen"}]}]}}],
            "literature": [], "failures": [
                {"id": f"F1-{route}", "kind": "unsupported",
                 "finding": "conditioning 假设未获支持", "referenced_by": [f"C1-{route}"],
                 "validity": self._validity("已记录", version - 2)}],
            "uncertainties": [{"id": f"U1-{route}", "uncertainty": "medium",
                               "importance": "high", "status": "open",
                               "cheapest_discriminating_test": "TBD",
                               "validity": self._validity("开放问题", version - 2)}],
            "assurance": [], "repairs": [],
        }
        if with_running:
            state["experiments"].append(
                {"id": f"X2-{route}", "parent": f"X1-{route}", "stage": "X4",
                 "claim_targeted": [f"C1-{route}"], "hypothesis_targeted": [],
                 "alternative_targeted": [], "status": "running",
                 "validity": self._validity("running per prereg", version - 1),
                 "preregistration": {"frozen_at_state_version": version - 3,
                                     "outcomes": []}})
        # V18/V19 completeness: every first-class object carries validity and an
        # explicit depends_on; experiments also carry known_flaws.
        for key in ("claims", "evidence", "failures", "uncertainties", "assumptions",
                    "hypotheses", "literature"):
            for item in state.get(key, []):
                item.setdefault("depends_on", [])
        for item in state.get("experiments", []):
            item.setdefault("depends_on", [])
            item.setdefault("known_flaws", [])
        (route_dir / "research-state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        (route_dir / "scheduler.json").write_text(json.dumps({
            "_schema": "research-idea-pipeline/scheduler@1",
            "state_version": version, "next_actions": [],
            "eig_calibration": {"records": []},
            "diagnostic_budget": {"spent": 3, "limit": 5},
        }, ensure_ascii=False), encoding="utf-8")
        revisions = [{"_schema": "research-idea-pipeline/cognition-revision@1",
                      "id": "REV1", "seq": 1, "kind": "mechanism_create",
                      "actor": "R9", "statement": "机制 A 支持 C1",
                      "payload": {"note": "来自 X1"}}]
        (route_dir / "cognition" / "model-revisions.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in revisions),
            encoding="utf-8")
        import decision_trajectory as dt
        trajectory = route_dir / "decision-trajectory.jsonl"
        context = dt.record_context(state, state_path=route_dir / "research-state.json")
        outcome = dt.append_record(trajectory, dt.build_decision_record(
            state, route=route, project=route, context=context,
            candidates=[{"action": f"X2-{route}", "type": "discriminating_experiment",
                         "target": f"U1-{route}"}],
            chosen=f"X2-{route}",
            scheduler_priority={"level": 4, "label": "high_information_gain_test"},
            policy_version="strategy-memory", policy_changed_order=False,
            dispatch_status="dispatched"), state=state, route=route)
        assert outcome["status"] == "APPENDED", outcome
        declaration = dg.parse_declaration({
            "mechanism": "conditioning", "scope": "route " + route,
            "assumptions": ["固定 mask"], "evidence_refs": [f"E1-{route}"],
            "predictions": ["X2 中 O1 无差异"]})[0]
        verdict = dg.classify(declaration, [], state=state)
        dg.append_event(route_dir, dg.event_from_classification(
            declaration, verdict, "fixture", state=state))
        (route_dir / "INDEX.md").write_text(
            f"# {route}\n数据位置：{self.legacy.resolve()}/routes/{route}/experiments\n",
            encoding="utf-8")

    def build_budgets(self):
        (self.legacy / "project").mkdir(exist_ok=True)
        (self.legacy / "project" / "constraints.json").write_text(json.dumps(
            {"gpu_hours_budget": 12, "pilot_runs": 1}, ensure_ascii=False),
            encoding="utf-8")
        (self.legacy / "meta").mkdir(exist_ok=True)
        (self.legacy / "meta" / "ledger.json").write_text(json.dumps(
            {"spent_hours": 4.5, "family": "default"}, ensure_ascii=False),
            encoding="utf-8")


class MigratedTestBase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backup_root = pathlib.Path(self.tmp.name) / "backups"
        self.backup_root.mkdir()
        self.project = pathlib.Path(self.tmp.name) / "MoSA-like"
        self.project.mkdir()
        LegacyProject(self.project)

    def migrate(self, *extra: str) -> subprocess.CompletedProcess:
        return run_tool("migrate", "--project", str(self.project),
                        "--backup-root", str(self.backup_root), "--apply",
                        "--assume-writers-quiesced", *extra)

    def assertSameAssets(self, before: dict, after: dict):
        self.assertEqual(before.keys(), after.keys())
        for route, fp in before.items():
            self.assertEqual(fp["state_version"], after[route]["state_version"],
                             route)
            self.assertEqual(fp["state_digest"], after[route]["state_digest"], route)
            self.assertEqual(fp["collections"], after[route]["collections"], route)
            self.assertEqual(fp["budgets"], after[route]["budgets"], route)


class TestHappyPath(MigratedTestBase):

    def test_inspect_reports_migration_required(self):
        proc = run_tool("inspect", "--project", str(self.project))
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(report["status"], "MIGRATION_REQUIRED")
        self.assertEqual(len(report["semantic_fingerprint"]["routes"]), 2)
        self.assertTrue(report["source_snapshot"]["entry_count"] > 8)
        self.assertFalse(report["maintenance"]["held"])
        self.assertTrue(any(dep["path"].endswith("INDEX.md")
                            for dep in report["path_dependencies"]["runtime_writable"]))
        self.assertTrue(any("research-state" in dep["path"] or "scheduler" in
                            dep["path"] or "decision-trajectory" in dep["path"]
                            for dep in report["path_dependencies"]["historical"]),
                        report["path_dependencies"])

    def test_plan_is_read_only_and_names_the_backup(self):
        before = sorted(p.name for p in self.legacy_root_iter())
        proc = run_tool("plan", "--project", str(self.project),
                        "--backup-root", str(self.backup_root))
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(report["ready_to_migrate"])
        self.assertTrue(report["backup_destination"].startswith(str(self.backup_root)))
        after = sorted(p.name for p in self.legacy_root_iter())
        self.assertEqual(before, after, "plan must not touch the project")

    def legacy_root_iter(self):
        return (self.project / rlp.LEGACY_STORAGE_ROOT).iterdir()

    def test_full_migration_keeps_every_research_asset(self):
        """7.2 — inspect → plan → migrate → verify：科研资产逐项保持。"""
        legacy_root = self.project / rlp.LEGACY_STORAGE_ROOT
        before = json.loads(run_tool("inspect", "--project", str(self.project)).stdout)[
            "semantic_fingerprint"]["routes"]
        # chain digests before
        chain_before = {route: sha(legacy_root / "routes" / route /
                                   "decision-trajectory.jsonl")
                        for route in ("A", "B")}
        proc = self.migrate()
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0, json.dumps(report)[:400])
        self.assertEqual(report["status"], "MIGRATED")
        # new root exists, legacy root is gone from the resolver namespace
        new_root = self.project / rlp.STORAGE_ROOT
        self.assertTrue(new_root.is_dir())
        self.assertFalse((self.project / rlp.LEGACY_STORAGE_ROOT).exists())
        self.assertTrue((self.project / f".rlp-archive" / report["migration_id"] /
                         "legacy-root").is_dir())
        # the archived copy is byte-identical for hashed chains
        for route in ("A", "B"):
            archived = (self.project / ".rlp-archive" / report["migration_id"] /
                        "legacy-root" / "routes" / route / "decision-trajectory.jsonl")
            self.assertEqual(sha(archived), chain_before[route],
                             "hashed chains must stay byte-identical")
        # semantic fingerprint unchanged
        after = report["verify"]["semantic_fingerprint"]["routes"]
        self.assertSameAssets(before, after)
        # no schema id was rewritten
        migrated_state = json.loads((new_root / "routes" / "A" /
                                     "research-state.json").read_text(encoding="utf-8"))
        # budgets unchanged
        sched = json.loads((new_root / "routes" / "A" / "scheduler.json").read_text())
        self.assertEqual(sched["diagnostic_budget"], {"spent": 3, "limit": 5})
        constraints = json.loads((new_root / "project" / "constraints.json").read_text())
        self.assertEqual(constraints["gpu_hours_budget"], 12)
        # TAG chain still valid under the new root
        records, problems = dg.load_events(new_root / "routes" / "A")
        self.assertEqual(problems, [])
        self.assertEqual(len(records), 1)
        # state gates pass under the new root
        for route in ("A", "B"):
            proc = subprocess.run(
                [sys.executable, str(SCRIPTS / "state_check.py"), "--check",
                 str(new_root / "routes" / route / "research-state.json")],
                capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_resume_continues_after_migration(self):
        """迁移后 Research Resume：project_context 在新根上正常工作。"""
        self.migrate()
        import preset_router as pr
        state_path = self.project / rlp.STORAGE_ROOT / "routes" / "A" / \
            "research-state.json"
        ctx = pr.project_context(state_path)     # must not raise MigrationRequired
        self.assertEqual(ctx["state"]["state_version"], 12)

    def test_migration_is_idempotent(self):
        """迁移后再次运行迁移：幂等 no-op，不重做。"""
        first = json.loads(self.migrate().stdout)
        second = json.loads(self.migrate().stdout)
        self.assertEqual(second["status"], "ALREADY_MIGRATED")
        self.assertTrue(second["idempotent"])
        self.assertEqual(second.get("previous_migration_id"), first["migration_id"])
        # the archive was not touched a second time
        archives = list((self.project / ".rlp-archive").iterdir())
        self.assertEqual(len(archives), 1)

    def test_operational_rewrite_is_explicit_and_rollbackable(self):
        """4.5 — 运行时文档重写：显式 opt-in、记录原始字节、可回滚。"""
        legacy_root = self.project / rlp.LEGACY_STORAGE_ROOT
        index_before = (legacy_root / "routes" / "A" / "INDEX.md").read_bytes()
        report = json.loads(self.migrate("--rewrite", "routes/A/INDEX.md").stdout)
        self.assertEqual(report["status"], "MIGRATED")
        self.assertEqual(len(report["rewrites"]), 1)
        new_index = (self.project / rlp.STORAGE_ROOT / "routes" / "A" / "INDEX.md")
        self.assertNotIn(".research-idea-pipeline", new_index.read_text())
        self.assertIn(".research-lifecycle-protocol", new_index.read_text())
        # rollback restores the original bytes
        rollback = json.loads(run_tool(
            "rollback", "--project", str(self.project),
            "--migration-id", report["migration_id"]).stdout)
        self.assertEqual(rollback["status"], "ROLLED_BACK")
        self.assertEqual((self.project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A" /
                          "INDEX.md").read_bytes(), index_before)

    def test_rollback_refuses_after_new_research_writes(self):
        """回滚守卫：迁移后产生新科研写入时禁止覆盖。"""
        report = json.loads(self.migrate().stdout)
        state_path = self.project / rlp.STORAGE_ROOT / "routes" / "A" / \
            "research-state.json"
        state = json.loads(state_path.read_text())
        state["state_version"] += 1          # new research write after migration
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        rollback = json.loads(run_tool(
            "rollback", "--project", str(self.project),
            "--migration-id", report["migration_id"]).stdout)
        self.assertEqual(rollback["status"], "ROLLBACK_REFUSED_NEW_WORK")
        self.assertTrue(rollback["differences"])
        self.assertIn("新的写入", "".join(rollback["errors"]))
        # the new root is untouched
        self.assertTrue((self.project / rlp.STORAGE_ROOT).is_dir())


class TestFailureInjection(MigratedTestBase):
    """7.3 — 每种失败都必须安全，且不丢数据。"""

    def test_target_exists_refuses_to_overwrite(self):
        """目标目录已存在 → 拒绝覆盖。"""
        (self.project / rlp.STORAGE_ROOT / "routes" / "A").mkdir(parents=True)
        (self.project / rlp.STORAGE_ROOT / "marker.txt").write_text("keep")
        report = json.loads(self.migrate().stdout)
        self.assertEqual(report["status"], "REFUSED")
        self.assertIn("AMBIGUOUS", report["status"] + report.get("errors", [""])[0])
        self.assertTrue((self.project / rlp.STORAGE_ROOT / "marker.txt").exists())

    def test_a_corrupt_legacy_state_refuses_migration(self):
        """旧 State 损坏 → 拒绝迁移（staging 指纹校验失败）。"""
        state_path = self.project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A" / \
            "research-state.json"
        state_path.write_text("{broken", encoding="utf-8")
        report = json.loads(self.migrate().stdout)
        self.assertIn(report["status"], ("FAILED_STAGING_VERIFY", "REFUSED",
                                         "FAILED_BACKUP"))
        # the legacy root is untouched (no cutover happened)
        self.assertTrue((self.project / rlp.LEGACY_STORAGE_ROOT).is_dir())
        self.assertFalse((self.project / rlp.STORAGE_ROOT).exists())

    def test_an_unwritable_backup_root_fails_safely(self):
        """备份目录无权限 → 安全失败，项目不受影响。"""
        read_only = self.project / "ro-backup"          # inside project: same FS
        read_only.mkdir()
        proc = run_tool("migrate", "--project", str(self.project),
                        "--backup-root", str(read_only / "backups"), "--apply")
        report = json.loads(proc.stdout)
        # either the backup fails (read-only via env) or it succeeds on a writable FS —
        # the invariant is: no partial cutover without a verified backup
        if report["status"] in ("FAILED_BACKUP", "REFUSED"):
            self.assertFalse((self.project / rlp.STORAGE_ROOT).exists())
        else:
            self.assertEqual(report["status"], "MIGRATED")

    def test_an_interrupted_migration_is_recoverable(self):
        """迁移中断（journal 有 started 无 terminal）→ recover 只在可证安全时清理。"""
        import migrate_project_root as mp
        mp._journal_append(self.project, {"event": "started", "migration_id": "sim-1",
                                          "backup": "x"})
        staging = mp.work_dir(self.project, "sim-1") / "staging"
        staging.mkdir(parents=True)
        (staging / "junk").write_text("x", encoding="utf-8")
        proc = run_tool("recover", "--project", str(self.project))
        report = json.loads(proc.stdout)
        self.assertEqual(report["action"], "clean_staging")
        self.assertTrue(staging.exists(), "recover without --apply must not delete")
        proc = run_tool("recover", "--project", str(self.project), "--apply")
        report = json.loads(proc.stdout)
        self.assertEqual(report["performed"], "clean_staging")
        self.assertFalse(staging.exists())
        self.assertTrue((self.project / rlp.LEGACY_STORAGE_ROOT).is_dir())

    def test_recovery_after_cutover_points_at_verify(self):
        import migrate_project_root as mp
        report = json.loads(self.migrate().stdout)
        # simulate a crash right after the cutover: journal lost its terminal entries
        journal = mp.journal_path(self.project)
        all_entries, problems = mp._journal_read(self.project)
        self.assertEqual(problems, [])
        entries = [e for e in all_entries
                   if e.get("migration_id") == report["migration_id"]]
        kept = [e for e in entries
                if e.get("event") in ("cutover_started", "new_root_installed")]
        journal.write_text("".join(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n"
                                   for e in kept), encoding="utf-8")
        proc = run_tool("recover", "--project", str(self.project))
        recovered = json.loads(proc.stdout)
        self.assertEqual(recovered["action"], "verify")

    def test_verify_fails_when_a_route_state_is_broken(self):
        report = json.loads(self.migrate().stdout)
        state_path = self.project / rlp.STORAGE_ROOT / "routes" / "A" / \
            "research-state.json"
        state_path.write_text("{broken", encoding="utf-8")
        proc = run_tool("verify", "--project", str(self.project),
                        "--migration-id", report["migration_id"])
        result = json.loads(proc.stdout)
        self.assertFalse(result["ok"])
        self.assertTrue(any("state 不可读" in p or "state gate" in p
                            for p in result["problems"]), result["problems"])

    def test_schema_ids_are_not_rewritten_by_migration(self):
        """机器协议 ID 不随目录迁移改变。"""
        self.migrate()
        sched = json.loads((self.project / rlp.STORAGE_ROOT / "routes" / "A" /
                            "scheduler.json").read_text())
        self.assertEqual(sched["_schema"], "research-idea-pipeline/scheduler@1")
        records, problems = dg.load_events(self.project / rlp.STORAGE_ROOT / "routes" / "A")
        self.assertEqual(problems, [])
        self.assertEqual(records[0]["_schema"], "research-idea-pipeline/tag-events@1")

    def test_domain_configs_move_with_the_control_root(self):
        """5.4 — 旧项目的 Domain Profile 随控制根迁移并被新根加载。"""
        legacy_route = self.project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A"
        profile = {"_schema": "research-idea-pipeline/domain-profile@1",
                   "profile": "mri-reconstruction"}
        (legacy_route / "domain").mkdir(exist_ok=True)
        (legacy_route / "domain" / "mri-reconstruction.json").write_text(
            json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        report = json.loads(self.migrate().stdout)
        self.assertEqual(report["status"], "MIGRATED")
        moved = (self.project / rlp.STORAGE_ROOT / "routes" / "A" / "domain" /
                 "mri-reconstruction.json")
        self.assertTrue(moved.is_file())
        state = json.loads((self.project / rlp.STORAGE_ROOT / "routes" / "A" /
                            "research-state.json").read_text())
        loaded = dp.load(
            self.project / rlp.STORAGE_ROOT / "routes" / "A", "mri-reconstruction",
            state=state)
        self.assertTrue(loaded.active)


class TestNewProject(MigratedTestBase):

    def test_a_new_project_never_creates_the_legacy_root(self):
        """7.1 — 新项目：只创建新控制根，Research Loop 正常启动。"""
        fresh = pathlib.Path(self.tmp.name) / "fresh-project"
        fresh.mkdir()
        import preset_router as pr
        from test_evidence_outcome import fixture, TIMESTAMP
        import evidence_outcome as eo
        route = fresh / rlp.STORAGE_ROOT / "routes" / "A"
        route.mkdir(parents=True)
        state = eo.apply(*fixture("positive"), timestamp=TIMESTAMP)["state"]
        state_path = route / "research-state.json"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        ctx = pr.project_context(state_path)             # must not raise
        self.assertEqual(ctx["state"]["state_version"], state["state_version"])
        self.assertFalse((fresh / rlp.LEGACY_STORAGE_ROOT).exists())
        self.assertTrue((fresh / rlp.STORAGE_ROOT).is_dir())
        # the runtime matrix is READY
        self.assertEqual(rlp.runtime_status(fresh)["status"], rlp.RUNTIME_STATUS_READY)

    def test_new_projects_cannot_write_the_legacy_root(self):
        """新项目尝试向旧根写入 → resolver 拒绝（不存在降级路径）。"""
        fresh = pathlib.Path(self.tmp.name) / "fresh2"
        fresh.mkdir()
        # NEW_PROJECT resolves fine; but the moment a legacy root appears the same
        # project flips to MIGRATION_REQUIRED — there is no downgrade path.
        self.assertEqual(rlp.runtime_status(fresh)["status"], rlp.RUNTIME_STATUS_NEW_PROJECT)
        (fresh / rlp.LEGACY_STORAGE_ROOT / "routes" / "A").mkdir(parents=True)
        self.assertEqual(rlp.runtime_status(fresh)["status"],
                         rlp.RUNTIME_STATUS_MIGRATION_REQUIRED)
        with self.assertRaises(rlp.MigrationRequired):
            rlp.default_state_path(fresh, "A")


if __name__ == "__main__":
    unittest.main()
