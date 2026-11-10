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

    def test_section_scoped_requirements_actually_load(self) -> None:
        """回归：`plan()` 能解析 `path#章节`，`execute()` 却把带 `#` 的字符串当文件名。

        这条链是新架构的核心能力。此前只有「章节规划的字符数更小」与「查询未命中被拒」
        两个断言，两者在 `#` 路径上会**因为同一个错误原因**同时通过，掩盖了真实缺陷。
        现在直接断言：执行成功、正文非空、确实是那一节、且严格小于整份文件。
        """
        payload = cplan.plan(entry="continue-research", preset_id="research-recovery",
                             authorization="execute")
        scoped = [item for item in payload["required"] if item.get("section_query")]
        self.assertTrue(scoped, "research-recovery 应当按章节加载认知记忆策略")

        executed = cplan.execute(payload)
        self.assertTrue(executed["can_proceed"],
                        f"章节级加载失败：{executed['blocked_missing']}")
        self.assertEqual(executed["blocked_missing"], [])

        loaded = {item["path"]: item for item in executed["loaded"]}
        for item in scoped:
            self.assertIn(item["path"], loaded, f"未进入 loaded：{item['path']}")
            entry = loaded[item["path"]]
            self.assertTrue(entry["text"].strip(), "加载到的章节正文为空")
            self.assertTrue(entry["sections"], "loaded 未记录命中的 section id")
            self.assertLess(entry["chars"], entry["full_chars"],
                            "章节加载必须真的比整份小")
            # 命中的章节正文必须能在原文件里定位到
            source = (ROOT / item["doc"]).read_text(encoding="utf-8")
            self.assertIn(entry["text"].split("\n", 1)[-1][:40], source)

    def test_every_preset_with_sections_can_be_executed(self) -> None:
        """任何声明了章节级必需项（或没有）的预设，都必须能 plan → execute → loaded。"""
        registry = cplan.load_registry()
        for preset in registry["presets"]:
            payload = cplan.plan(entry=preset["entry"],
                                 preset_id=preset["preset_id"],
                                 authorization="execute")
            executed = cplan.execute(payload)
            self.assertTrue(executed["can_proceed"],
                            f"{preset['preset_id']}: {executed['blocked_missing']}")
            self.assertTrue(executed["loaded_paths"])

    def test_execute_uses_doc_not_the_sectioned_path(self) -> None:
        """直接锁死错误形态：`path` 含 `#`，`doc` 不含；execute 必须读 `doc`。"""
        payload = cplan.plan(entry="continue-research", preset_id="context-drift-recovery")
        scoped = [item for item in payload["required"] if item.get("section_query")]
        self.assertTrue(scoped)
        for item in scoped:
            self.assertIn("#", item["path"])
            self.assertNotIn("#", item["doc"])
            self.assertTrue((ROOT / item["doc"]).is_file())
        self.assertTrue(cplan.execute(payload)["can_proceed"])

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
        # 真实布局：<project>/.research-lifecycle-protocol/routes/<R>/
        # 这样 `route_dir` 的推导与 `/domain/<profile>.json` 的定位都被真实覆盖。
        self.project = pathlib.Path(self.temp.name) / ".research-lifecycle-protocol"
        self.route = self.project / "routes" / "A"
        self.route.mkdir(parents=True)
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

    def test_domain_declaration_changes_invalidate_the_packet(self) -> None:
        """回归：`_domain_digest` 只算 Skill 内 PROFILE.md，漏掉项目/路线实际声明。

        项目把 `gt_free` 从 true 改成 false、或补上/撤掉 `<route>/domain/<p>.json`，
        canonical state 可能一点没变。Packet 必须因此失效，否则它会把旧边界当新事实。
        """
        domain_dir = self.route / "domain"
        domain_dir.mkdir()
        config = domain_dir / "mri-reconstruction.json"
        config.write_text(json.dumps({"profile": "mri-reconstruction", "gt_free": True}),
                          encoding="utf-8")

        packet = cp.build(self.state_path, domain="mri-reconstruction")
        self.assertEqual([item["scope"] for item in packet["binding"]["domain_declaration"]],
                         ["route"])
        self.assertFalse(cp.verify(packet, self.state_path)["stale"],
                         "配置未变时不应误判失效")

        config.write_text(json.dumps({"profile": "mri-reconstruction", "gt_free": False}),
                          encoding="utf-8")
        changed = cp.verify(packet, self.state_path)
        self.assertTrue(changed["stale"], "domain 声明变化必须让 Packet 失效")
        self.assertIn("Domain", " ".join(changed["stale_reasons"]))

        rebuilt = cp.build(self.state_path, domain="mri-reconstruction")
        config.unlink()
        removed = cp.verify(rebuilt, self.state_path)
        self.assertTrue(removed["stale"], "撤掉 domain 声明也必须失效")

    def test_domain_declaration_absent_is_still_a_stable_value(self) -> None:
        """没有声明时摘要必须是一个**确定值**，否则补上声明不会触发失效。"""
        first = cp.build(self.state_path, domain="mri-reconstruction")
        self.assertEqual(first["binding"]["domain_declaration"], [])
        domain_dir = self.route / "domain"
        domain_dir.mkdir()
        (domain_dir / "mri-reconstruction.json").write_text('{"profile":"mri-reconstruction"}',
                                                           encoding="utf-8")
        self.assertTrue(cp.verify(first, self.state_path)["stale"])

    def test_over_budget_is_not_reported_as_pass(self) -> None:
        """回归：超预算压缩后无条件 `status="PASS"`，超限被静默吞掉。"""
        packet = cp.build(self.state_path, budget=200)
        self.assertEqual(packet["status"], "OVER_BUDGET",
                         "超预算不得报 PASS")
        self.assertTrue(packet["budget"]["over_budget"])
        self.assertTrue(packet["budget"]["uncovered"], "必须列明被压缩的字段")
        self.assertIn("next_step", packet, "超预算必须给出下一步，而不是给结论")

    def test_over_budget_records_what_it_dropped(self) -> None:
        """省略必须可追：只留前三条时要写清省了哪些 id。"""
        packet = cp.build(self.state_path, budget=200)
        omitted = packet["budget"]["omitted"]
        self.assertTrue(omitted, "省略了内容却没有记录")
        for field, ids in omitted.items():
            self.assertIsInstance(ids, list)
            self.assertTrue(all(isinstance(item, str) for item in ids))

    def test_over_budget_never_shortens_protected_fields(self) -> None:
        packet = cp.build(self.state_path, budget=200)
        self.assertTrue(packet["budget"]["protected_intact"])
        for field in ("authorization", "constraints", "anchor", "banned_retries",
                      "required_domain_boundaries", "state_version", "canonical_digest"):
            self.assertIn(field, packet, f"预算压缩删掉了不可截断字段 {field}")

    def test_honest_status_is_exclusive(self) -> None:
        """PASS 与 OVER_BUDGET 互斥，且 PASS 一定意味着未超限。"""
        for budget in (cp.DEFAULT_RESEARCH_BUDGET, 600, 200):
            packet = cp.build(self.state_path, budget=budget)
            self.assertIn(packet["status"], ("PASS", "OVER_BUDGET"))
            if packet["status"] == "PASS":
                self.assertFalse(packet["budget"]["over_budget"])
                self.assertLessEqual(packet["chars"], budget)

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


class TestRouterConsumesThePlan(unittest.TestCase):
    """回归：Planner 与 Router 只靠文档「关联」，正常调用路径并不执行计划。

    AGENTS.md §22 要求能力的五环完整（Producer → Runtime Entry → Consumer →
    Decision Effect → Persistence）。只有 `plan()` 可被调用，证明的是第一环。
    这组测试走**真实入口** `preset_router.run_preset`，要求计划被执行、被随结果返回，
    并且在不能继续时**真的**挡住处理器。
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        project = pathlib.Path(self.temp.name) / ".research-lifecycle-protocol"
        self.route = project / "routes" / "A"
        self.route.mkdir(parents=True)
        self.state_path = self.route / "research-state.json"
        self.state_path.write_text(
            (ROOT / "templates" / "research-state.template.json").read_text(encoding="utf-8"),
            encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_real_entry_carries_an_executed_plan(self) -> None:
        import preset_router as pr
        payload, _, code = pr.run_preset("research-recovery", self.state_path)
        self.assertEqual(code, pr.EXIT_OK)
        plan = payload.get("context_plan")
        self.assertIsNotNone(plan, "run_preset 没有消费上下文计划")
        self.assertEqual(plan["status"], "PASS")
        self.assertTrue(plan["plan_digest"])
        self.assertTrue(plan["loaded"], "计划没有被执行（loaded 为空）")
        self.assertIn("SKILL.md", plan["loaded"])
        self.assertGreater(plan["not_loaded_count"], 0, "未列出「为什么没加载其他」")
        self.assertTrue(plan["gates_remaining"], "计划没有声明剩余门禁")

    def test_the_plan_path_is_the_one_that_loads(self) -> None:
        """走真实入口时也必须经过章节级加载，而不是退化成整份读取。"""
        import preset_router as pr
        payload, _, _ = pr.run_preset("research-recovery", self.state_path)
        loaded = payload["context_plan"]["loaded"]
        sectioned = [path for path in loaded if "#" in path]
        self.assertTrue(sectioned, "真实入口没有走章节级加载")
        self.assertLessEqual(len(sectioned), 4)

    def test_incomplete_context_blocks_the_handler(self) -> None:
        """Decision Effect：计划说不能继续时，处理器不得运行。"""
        import preset_router as pr
        import context_planner as cplan
        ran: list = []
        original_handler = pr.HANDLERS["research-recovery"]
        original_execute = cplan.execute

        def fake_execute(plan, **kwargs):
            out = original_execute(plan, **kwargs)
            out["can_proceed"] = False
            out["status"] = "BLOCKED"
            out["blocked_missing"] = [{"path": "references/missing.md",
                                       "reason": "probe: 必需上下文缺失"}]
            return out

        def spy(context, apply):
            ran.append(True)
            return original_handler(context, apply)

        pr.HANDLERS["research-recovery"] = spy
        cplan.execute = fake_execute
        try:
            payload, _, code = pr.run_preset("research-recovery", self.state_path)
        finally:
            pr.HANDLERS["research-recovery"] = original_handler
            cplan.execute = original_execute

        self.assertEqual(ran, [], "上下文不完整时处理器仍然执行了")
        self.assertEqual(payload["status"], "HOLD")
        self.assertEqual(payload["hold_reason"], "context_incomplete")
        self.assertEqual(code, pr.EXIT_ENV)
        self.assertTrue(any(item["rule"] == "PR12" for item in payload["diagnostics"]))

    def test_authorisation_is_never_upgraded(self) -> None:
        import preset_router as pr
        self.assertEqual(pr._authorisation_for("execute"), "execute")
        for scope in ("read_only", "inspect_only", "audit", "evaluation_only"):
            self.assertEqual(pr._authorisation_for(scope), "read_only", scope)
        for scope in ("discover_only", "strategy_update", "plan", "decision_only",
                      "evidence_repair", "portfolio"):
            self.assertEqual(pr._authorisation_for(scope), "advisory", scope)
        self.assertNotIn(pr._authorisation_for("read_only"), ("execute",))
        self.assertNotIn(pr._authorisation_for("discover_only"), ("execute",))

    def test_declared_domain_is_detected_but_never_guessed(self) -> None:
        import preset_router as pr
        self.assertIsNone(pr._declared_domain(self.route))
        domain_dir = self.route / "domain"
        domain_dir.mkdir()
        (domain_dir / "mri-reconstruction.json").write_text("{}", encoding="utf-8")
        self.assertEqual(pr._declared_domain(self.route), "mri-reconstruction")
        # 两个声明 → 不猜
        (domain_dir / "other-profile.json").write_text("{}", encoding="utf-8")
        self.assertIsNone(pr._declared_domain(self.route))


if __name__ == "__main__":
    unittest.main(verbosity=2)
