#!/usr/bin/env python3
"""test_context_architecture.py — 上下文架构的行为回归（v2.2.0）。

What this file is guarding
--------------------------
本轮把「Agent 每次读一大堆科研规章」换成「L0 常驻 + 按任务精确加载 + 机器门禁」。这个
替换只有在下面四件事同时成立时才算成功，而每一件都是**行为**而不是文档：

* **计划器**：给定入口/预设/阶段/授权/领域，产出一个可复现、可解释、可解释「为什么没加载
  其他」的计划；条件未命中不进 required；缺必需项就不许往下走；
  `loaded` 与 `referenced` 不混用；
* **预算**：超预算**不静默截断**安全约束、权限边界、冻结条件与关键反例，而是列出未覆盖项；
* **章节级加载**：大型 policy 可以只取一节，章节查询未命中时**不得**悄悄退化为整文件；
* **不丢规则**：L0 精简后仍保留全部硬约束标记，且没有重新长出被移除的重复表；
* **权限不扩张**：子 Agent 的上下文裁剪不产生任何额外写入权。

`SKILL.md` 的本轮上限是回归闸门，不是审美要求：超过上限意味着细节被重新塞回 L0。

Verification levels: L1（单元）与 L2（真实接口的合成端到端）。L3（真实科研 A/B）**没有**做，
不得声称。
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

import context_packet as cp
import context_planner as cplan
import context_profile as cprof
import section_index as sindex
import subagent_context as sacon

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: v2.2.0 的 L0 回归上限。改动这个数字必须同时改 docs/context-benchmark.md。
L0_BUDGET_BYTES = 40_000

#: L0 必须常驻的硬约束（与 release_check 同一份口径）。
L0_MARKERS = (
    "唯一科学事实源",
    "禁止重新 Bootstrap",
    "用户授权不可由 Agent 自行升级",
    "GT-free",
    "执行门禁",
    "不得把「路线终止」等同于「科学真理被否定」",
    "相关性不得写成因果性",
    "子 Agent 不得绕过已有状态写入权限",
    "冻结",
    "没读规则",
    "只有用户能授权",
)


class TestL0Contract(unittest.TestCase):
    """L0 精简不得丢规则，也不得重新长出被移除的重复内容。"""

    def setUp(self) -> None:
        self.skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")

    def test_l0_is_within_the_regression_budget(self) -> None:
        size = len(self.skill.encode("utf-8"))
        self.assertLessEqual(size, L0_BUDGET_BYTES,
                             f"SKILL.md 为 {size} bytes，超过 L0 上限；细节应下沉到 references")

    def test_l0_shrank_by_at_least_three_quarters(self) -> None:
        """v2.1.1 的 SKILL.md 是 156565 bytes。精简必须是真的。"""
        size = len(self.skill.encode("utf-8"))
        self.assertLess(size, 156565 * 0.25,
                        "L0 精简幅度不足 75%，本轮目标没有达成")

    def test_every_hard_constraint_is_still_loaded(self) -> None:
        missing = [marker for marker in L0_MARKERS if marker not in self.skill]
        self.assertEqual(missing, [], "L0 丢失了硬约束（精简不等于删规则）")

    def test_frontmatter_still_allows_skill_discovery(self) -> None:
        self.assertTrue(self.skill.startswith("---\n"))
        head = self.skill[:self.skill.index("\n---", 3)]
        self.assertIn("name: research-lifecycle-protocol", head)
        self.assertIn("description:", head)
        self.assertIn("version:", head)
        # kebab-case：provider 只接受这个形状，否则整个 skill 被静默丢弃
        self.assertRegex(head.split("name:", 1)[1].split("\n", 1)[0].strip(),
                         r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    def test_anchors_cited_elsewhere_still_exist(self) -> None:
        """`AGENTS.md` §23.1 与多个 reference 引用了固定小节号，不得静默消失。"""
        for anchor in ("### 0.1", "### 0.2", "### 1.6", "### 1.7", "#### 3.1.0"):
            self.assertIn(anchor, self.skill, f"L0 丢失被外部引用的锚点 {anchor}")

    def test_l0_does_not_regrow_the_copied_read_write_table(self) -> None:
        """读写契约只有 policy §5 一个权威；回到 L0 就又是两个漂移源。"""
        self.assertNotIn("| 读什么（state 字段） |", self.skill)
        self.assertNotIn("| 写什么（state 字段） |", self.skill)

    def test_l0_links_all_resolve(self) -> None:
        import re
        broken = []
        for target in re.findall(r"\]\((references/[^)#]+|domain-profiles/[^)#]+|presets/[^)#]+)\)",
                                 self.skill):
            if not (ROOT / target).is_file():
                broken.append(target)
        self.assertEqual(broken, [], f"L0 里有悬空链接：{broken}")


class TestContextPlanner(unittest.TestCase):
    def test_registry_declarations_are_valid(self) -> None:
        ok, problems = cplan.check()
        self.assertTrue(ok, f"依赖声明不合法：{problems[:3]}")

    def test_every_preset_is_plannable(self) -> None:
        registry = cplan.load_registry()
        for preset in registry["presets"]:
            payload = cplan.plan(entry=preset["entry"], preset_id=preset["preset_id"],
                                 authorization="read_only")
            self.assertEqual(payload["status"], "PASS",
                             f"{preset['preset_id']}: {payload.get('problems')}")

    def test_plan_loads_exactly_one_protocol(self) -> None:
        payload = cplan.plan(entry="continue-research", preset_id="research-loop")
        protocols = [item for item in payload["required"]
                     if item["path"].startswith("presets/")]
        self.assertEqual(len(protocols), 1, "一次调用不得加载多个 Preset")

    def test_plan_is_a_pure_function(self) -> None:
        a = cplan.plan(entry="audit", preset_id="research-audit")
        b = cplan.plan(entry="audit", preset_id="research-audit")
        self.assertEqual(a["plan_digest"], b["plan_digest"])

    def test_conditional_items_do_not_enter_required_until_triggered(self) -> None:
        cold = cplan.plan(entry="continue-research", preset_id="research-loop")
        warm = cplan.plan(entry="continue-research", preset_id="research-loop",
                          conditional_active=["method_synthesis"])
        cold_paths = {item["path"] for item in cold["required"]}
        warm_paths = {item["path"] for item in warm["required"]}
        self.assertTrue(cold_paths < warm_paths, "条件命中后 required 应当变大")
        for step in cold["conditional"]:
            if not step["active"]:
                for item in step["items"]:
                    self.assertNotIn(item["path"], cold_paths)

    def test_domain_profile_loads_only_when_declared(self) -> None:
        off = cplan.plan(entry="continue-research", preset_id="research-loop")
        on = cplan.plan(entry="continue-research", preset_id="research-loop",
                        domain="mri-reconstruction")
        self.assertFalse([i for i in off["required"] if "domain-profiles" in i["path"]])
        domain_items = [i for i in on["required"] if "domain-profiles" in i["path"]]
        self.assertEqual([i["path"] for i in domain_items],
                         ["domain-profiles/mri-reconstruction/PROFILE.md"],
                         "领域激活时只加载 PROFILE，子协议按任务切片")

    def test_domain_slice_is_loaded_on_request(self) -> None:
        payload = cplan.plan(entry="continue-research", preset_id="research-loop",
                             domain="mri-reconstruction",
                             domain_slices=["ssl-contract"])
        paths = {item["path"] for item in payload["required"]}
        self.assertIn("domain-profiles/mri-reconstruction/ssl-contract.md", paths)
        # 只要被请求的那一份，不要整包
        self.assertNotIn("domain-profiles/mri-reconstruction/mechanism-search.md", paths)

    def test_missing_domain_slice_blocks_the_plan(self) -> None:
        payload = cplan.plan(entry="continue-research", preset_id="research-loop",
                             domain="mri-reconstruction",
                             domain_slices=["no-such-slice"])
        self.assertFalse(payload["can_proceed"])
        self.assertTrue(any("no-such-slice" in item["path"]
                            for item in payload["blocked_missing"]))

    def test_blocking_state_stops_execution(self) -> None:
        payload = cplan.plan(entry="continue-research", preset_id="research-loop",
                             blockers=["MIGRATION_REQUIRED"])
        self.assertFalse(payload["can_proceed"])
        self.assertEqual(payload["status"], "BLOCKED")

    def test_read_only_and_execute_differ_only_in_authorisation(self) -> None:
        ro = cplan.plan(entry="continue-research", preset_id="research-loop",
                        authorization="read_only")
        ex = cplan.plan(entry="continue-research", preset_id="research-loop",
                        authorization="execute")
        self.assertEqual({i["path"] for i in ro["required"]},
                         {i["path"] for i in ex["required"]},
                         "授权等级只改允许的动作，不改要读的规则")
        self.assertNotEqual(ro["authorization"], ex["authorization"])

    def test_loaded_and_referenced_are_different_things(self) -> None:
        payload = cplan.plan(entry="audit", preset_id="research-audit")
        self.assertEqual(payload["loaded"], [], "plan 阶段不得声称已加载")
        executed = cplan.execute(payload)
        self.assertTrue(executed["loaded"], "execute 之后 loaded 必须有正文")
        self.assertTrue(all(isinstance(item, str) for item in executed["referenced"]))
        self.assertTrue(set(executed["loaded_paths"])
                        <= {item["path"] for item in executed["required"]},
                        "loaded 不得包含未在 required 声明的内容")

    def test_missing_required_context_blocks_execution(self) -> None:
        payload = cplan.plan(entry="continue-research", preset_id="research-loop")
        payload["required"].append({"path": "references/not-here.md", "doc": "x",
                                   "layer": "L1", "kind": "document", "reason": "probe",
                                   "exists": False, "chars": 0, "bytes": 0, "digest": None,
                                   "full_chars": 0})
        executed = cplan.execute(payload)
        self.assertFalse(executed["can_proceed"], "缺必需上下文不得继续")
        self.assertTrue(executed["blocked_missing"])

    def test_over_budget_reports_instead_of_truncating(self) -> None:
        saved = cplan.BUDGETS["protocol_chars"]
        try:
            cplan.BUDGETS["protocol_chars"] = 10
            payload = cplan.plan(entry="continue-research", preset_id="research-loop")
        finally:
            cplan.BUDGETS["protocol_chars"] = saved
        self.assertTrue(payload["budget"]["over_budget"])
        self.assertTrue(payload["budget"]["uncovered"], "超预算必须列出未覆盖项")
        self.assertIn("冻结条件", payload["budget"]["never_truncate"])
        self.assertFalse(payload["can_proceed"], "硬要求未覆盖时不得宣称可以继续")

    def test_gate_ownership_is_explicit_even_when_rules_are_not_loaded(self) -> None:
        """上下文精简与工具侧门禁分离：没读规则也照样列出门禁。"""
        payload = cplan.plan(entry="continue-research", preset_id="research-loop")
        self.assertIn("state_check.py", payload["gates_remaining"])
        self.assertIn("experiment_execute.py", payload["gates_remaining"])

    def test_section_scoped_requirement_loads_only_that_section(self) -> None:
        payload = cplan.plan(entry="continue-research", preset_id="research-recovery")
        scoped = [item for item in payload["required"] if item.get("section_query")]
        self.assertTrue(scoped, "research-recovery 应当按章节加载认知记忆策略")
        for item in scoped:
            self.assertLess(item["chars"], item["full_chars"],
                            "章节加载必须真的比整份小")

    def test_section_query_miss_does_not_fall_back_to_the_whole_file(self) -> None:
        payload = cplan.plan(entry="continue-research", preset_id="research-loop")
        payload["required"][0] = dict(payload["required"][0],
                                      section_query="不存在的章节标题")
        executed = cplan.execute(payload)
        self.assertFalse(executed["can_proceed"],
                         "章节查询未命中时不得悄悄加载整份文件")
        self.assertTrue(any("section query" in item["reason"]
                            for item in executed["blocked_missing"]))


class TestSubagentContext(unittest.TestCase):
    def test_contracts_are_within_bounds(self) -> None:
        ok, problems = sacon.check()
        self.assertTrue(ok, f"子 Agent 契约越界：{problems[:3]}")

    def test_no_role_can_write_canonical_state_by_default(self) -> None:
        for role in sacon.ROLE_IDS:
            payload = sacon.build(role, "probe")
            self.assertFalse(payload["permits"]["write_canonical"],
                             f"{role} 默认不得写 canonical state")

    def test_no_role_can_modify_the_anchor(self) -> None:
        for role in sacon.ROLE_IDS:
            self.assertFalse(sacon.build(role, "probe")["permits"]["modify_anchor"])

    def test_context_is_much_smaller_than_the_global_rule_book(self) -> None:
        roles = (ROOT / "references" / "roles.md").read_text(encoding="utf-8")
        payload = sacon.build("literature", "核验近邻")
        self.assertLess(payload["chars"] * 4, len(roles),
                        "子 Agent 上下文应当远小于整份角色库")

    def test_execution_roles_require_manifest_and_approval(self) -> None:
        payload = sacon.build("experiment", "跑已冻结的 X3")
        self.assertTrue(payload["permits"]["execute_experiment"])
        self.assertTrue(payload["manifest_required"], "执行角色必须要求 manifest")
        self.assertTrue(payload["approval_required"], "执行角色必须要求批准")

    def test_context_never_includes_the_full_state(self) -> None:
        for role in sacon.ROLE_IDS:
            payload = sacon.build(role, "probe")
            self.assertFalse(payload["includes_full_state"])
            self.assertNotIn("research-state.json", payload["text"].split("## 你")[0])

    def test_slice_without_provenance_is_rejected(self) -> None:
        self.assertEqual(sacon.build("assurance", "t",
                                     evidence_slices=[{"note": "无来源"}])["status"],
                         "FAIL")
        self.assertEqual(sacon.build("assurance", "t",
                                     evidence_slices=[{"ref": "E1"}])["status"], "PASS")

    def test_permission_escalation_is_refused(self) -> None:
        original = dict(sacon.ROLES["literature"]["permits"])
        try:
            sacon.ROLES["literature"]["permits"]["write_canonical"] = True
            self.assertEqual(sacon.build("literature", "t")["status"], "FAIL")
            ok, _ = sacon.check()
            self.assertFalse(ok)
        finally:
            sacon.ROLES["literature"]["permits"] = original


class TestContextPacket(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.route = pathlib.Path(self.temp.name) / "A"
        self.route.mkdir()
        self.state_path = self.route / "research-state.json"
        template = (ROOT / "templates" / "research-state.template.json")
        self.state_path.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_packet_is_derived_and_not_a_ninth_object(self) -> None:
        packet = cp.build(self.state_path, authorization="execute")
        self.assertFalse(packet["is_canonical_state"])
        self.assertTrue(packet["regenerable"])
        before = self.state_path.read_bytes()
        cp.build(self.state_path, authorization="execute")
        self.assertEqual(self.state_path.read_bytes(), before,
                         "Packet 不得写 canonical state")

    def test_packet_carries_the_thirteen_items(self) -> None:
        packet = cp.build(self.state_path, task="continue_method")
        for field in ("route", "state_version", "canonical_digest", "anchor",
                      "authorization", "constraints", "active_mechanisms", "unresolved",
                      "competing_explanations", "banned_retries", "experiments",
                      "last_decision", "legal_actions", "evidence_refs",
                      "required_domain_boundaries"):
            self.assertIn(field, packet)

    def test_packet_binds_to_the_state_and_detects_staleness(self) -> None:
        packet = cp.build(self.state_path)
        self.assertFalse(cp.verify(packet, self.state_path)["stale"])
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        state["state_version"] = int(state.get("state_version") or 0) + 1
        self.state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        result = cp.verify(packet, self.state_path)
        self.assertTrue(result["stale"])
        self.assertIn("不得清空 Research State", result["action"])
        self.assertIn("不得重新 Bootstrap", result["action"])

    def test_packet_never_truncates_safety_fields(self) -> None:
        packet = cp.build(self.state_path, budget=200)
        for field in ("authorization", "constraints", "anchor", "banned_retries",
                      "required_domain_boundaries", "state_version", "canonical_digest"):
            self.assertIn(field, packet, f"预算压缩不得删掉 {field}")
        self.assertTrue(packet["budget"]["never_truncate"])

    def test_read_only_packet_offers_no_execution(self) -> None:
        packet = cp.build(self.state_path, authorization="read_only")
        self.assertNotIn("run_frozen_experiment", packet["legal_actions"])
        self.assertNotIn("update_state_after_gates", packet["legal_actions"])


class TestSectionIndex(unittest.TestCase):
    def test_checked_in_index_matches_the_documents(self) -> None:
        ok, detail = sindex.check_index()
        self.assertTrue(ok, f"章节索引与正文不一致：{detail}")

    def test_section_ids_are_position_independent(self) -> None:
        a = sindex.split_sections("# T\n\n## 读 / 写 World Model\n")
        b = sindex.split_sections("# T\n\n新增一段\n\n\n## 读 / 写 World Model\n")
        self.assertEqual([s["id"] for s in a], [s["id"] for s in b])

    def test_fenced_headings_are_not_sections(self) -> None:
        text = "## real\n\n```bash\n# not a heading\n```\n\n## second\n"
        self.assertEqual([s["title"] for s in sindex.split_sections(text)],
                         ["real", "second"])

    def test_find_returns_a_usable_pointer(self) -> None:
        index = sindex.build_index()
        hits = sindex.find_sections(index, "research-state-policy", "引用完整性")
        self.assertTrue(hits, "应当能按章节标题定位")
        self.assertTrue(all("V1" in hit["rule_ids"] or "V24" in hit["rule_ids"]
                            for hit in hits))


class TestContextProfile(unittest.TestCase):
    def test_estimate_is_labelled_and_deterministic(self) -> None:
        self.assertEqual(cprof.estimate_tokens("abcd"), 1)
        self.assertEqual(cprof.estimate_tokens("中文"), 2)
        self.assertIn("heuristic", cprof.TOKEN_METHOD)

    def test_every_scenario_reads_only_real_files(self) -> None:
        for scenario in cprof.SCENARIOS:
            for rel in scenario["baseline_reads"]:
                self.assertTrue((ROOT / rel).is_file(), f"{scenario['id']} → {rel}")

    def test_profiler_never_claims_a_real_token_count(self) -> None:
        report = cprof.profile_all(scenarios=["research-loop"])
        self.assertIn("measurement", report["scenarios"][0])
        self.assertIn("visible", report["scenarios"][0]["measurement"])
        self.assertIn("估算", report["measurement_note"])
        self.assertIn("不可观测", report["scenarios"][0]["measurement"]["visible"])

    def test_observation_must_be_self_consistent(self) -> None:
        good = {"skill": "s", "version": "1", "harness": "h", "observed_at": "t",
                "injected_bytes": 100, "visible_bytes": 60, "elided_bytes": 40}
        merged = cprof.apply_observation({"schema": "x"}, good)
        self.assertEqual(merged["observation"]["label"], "observed")
        self.assertFalse(merged["observation"]["reproducible_by_this_script"])
        with self.assertRaises(ValueError):
            cprof.apply_observation({}, dict(good, elided_bytes=1))

    def test_planned_arm_loads_less_than_the_old_architecture(self) -> None:
        """回归：新架构的协议上下文必须显著小于 v2.1.1 的 L0。"""
        plans = cprof.profile_all(architecture="planned")
        for item in plans["scenarios"]:
            # 每次调用至少要比「只注入旧 SKILL.md」小得多
            self.assertLess(item["loaded_chars"], 156565,
                            f"{item['scenario']} 没有比旧 L0 更小")


if __name__ == "__main__":
    unittest.main(verbosity=2)
