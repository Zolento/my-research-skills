#!/usr/bin/env python3
"""test_structural_equivalence.py — Structural Equivalence 的离线测试。

两类内容：

1. **副本一致性**（AGENTS.md Rule 4）：policy §3 / §6 / §7 / §8 / §12 的枚举与规则表，
   必须与 `structural_equivalence_check.py` 里的常量**逐字一致**。
   改了 policy 却没改代码（或反过来）会在这里变红。

2. **metamorphic 套件 T1—T10**（[structural-equivalence-policy.md](../references/structural-equivalence-policy.md) §14.2）：
   验证 pipeline **不会**因为表面改写产生错误 verdict。每个变体都带一个**负例对照**：
   过度声称（把 `claimed_novelty_level` 拉到 `paradigm-candidate`）必须被 `EQ13` 拦下。
   这直接对应 `FalseParadigmRate` 这个优先指标。

全部离线，不访问网络。
"""

from __future__ import annotations

import contextlib
import copy
import importlib
import io
import json
import pathlib
import re
import shutil
import sys
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Tuple

SCRIPTS = pathlib.Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import structural_equivalence_check as seq  # noqa: E402 — 需要先插入 sys.path

ROOT = SCRIPTS.parent
POLICY = ROOT / "references" / "structural-equivalence-policy.md"
TEMPLATE = ROOT / "templates" / "structural-equivalence-audit.template.json"
FIXTURES = ROOT / "examples" / "structural-equivalence"

# fixture 名 → 期望 verdict（policy §14.2 的四个具名样例）
FIXTURE_VERDICTS = {
    "equivalent": "equivalent",
    "transfer-only": "transfer-only",
    "formulation-delta": "formulation-delta",
    "paradigm-candidate": "paradigm-candidate",
}


def _policy() -> str:
    return POLICY.read_text(encoding="utf-8")


def _section(start: str, end: str) -> str:
    text = _policy()
    head = text.index(start)
    return text[head:text.index(end, head)]


def _load(path: pathlib.Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run(*argv: str) -> Tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = seq.main(list(argv))
    return code, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# 1. 副本一致性（Rule 4：改规则必须同轮改所有副本，并加一条比对检查）
# ---------------------------------------------------------------------------


class TestPolicyCodeParity(unittest.TestCase):
    """policy 的枚举与规则表 ↔ 检查器常量，必须逐字一致。"""

    def test_facets_match_policy(self) -> None:
        rows = re.findall(r"^\| \d+ \| `([a-z_]+)` \|",
                          _section("### 3.1 十四个 scientific facets", "### 3.2"), re.M)
        self.assertEqual(tuple(rows), seq.FACETS,
                         "policy §3.1 的十四个 facet 与检查器 FACETS 不一致")

    def test_relations_match_policy(self) -> None:
        rows = re.findall(r"`([a-z_]+)`",
                          _section("### 3.2 typed relations", "### 3.3"))
        self.assertEqual(tuple(rows), seq.RELATIONS,
                         "policy §3.2 的 typed relation 与检查器 RELATIONS 不一致")

    def test_verdicts_match_policy(self) -> None:
        rows = re.findall(r"^\| `([a-z-]+)` \|",
                          _section("### 7.1 冻结枚举", "**强 verdict 集合**"), re.M)
        self.assertEqual(tuple(rows), seq.VERDICTS,
                         "policy §7.1 的十个 verdict 与检查器 VERDICTS 不一致")

    def test_claimed_levels_match_policy(self) -> None:
        line = next(line for line in _policy().splitlines()
                    if "`claimed_novelty_level` ∈" in line)
        rows = re.findall(r"`([a-z-]+)`", line.split("∈", 1)[1])
        self.assertEqual(tuple(rows), seq.CLAIMED_LEVELS,
                         "policy §8.2 第 15 条的 claimed_novelty_level 枚举与代码不一致")

    def test_collapse_results_match_policy(self) -> None:
        line = next(line for line in _policy().splitlines()
                    if line.startswith("| `collapse_result` |"))
        rows = re.findall(r"`([a-z_-]+)`", line)[1:]
        self.assertEqual(tuple(rows), seq.COLLAPSE_RESULTS,
                         "policy §6.1 的 collapse_result 枚举与代码不一致")

    def test_load_bearing_keys_match_policy(self) -> None:
        rows = re.findall(r"`(changed_[a-z_]+)`",
                          _section("### 5.3 机器判据", "## 6. Counterfactual"))
        self.assertEqual(tuple(rows), seq.LOAD_BEARING_KEYS,
                         "policy §5.3 的 load_bearing_analysis 五键与代码不一致")

    def test_eq_rule_table_matches_policy(self) -> None:
        rows = dict(re.findall(
            r"^\| `(EQ\d+)` \| (.+?) \|$",
            _section("### 12.1 规则表", "### 12.2"), re.M))
        self.assertEqual(len(rows), 13, f"policy §12.1 只解析出 {len(rows)} 条规则行")
        self.assertEqual(rows, seq.RULES,
                         "policy §12.1 的 EQ1—EQ13 判据与检查器 RULES 不一致")

    def test_rule_order_is_exactly_eq1_to_eq13(self) -> None:
        self.assertEqual(seq.RULE_ORDER, [f"EQ{n}" for n in range(1, 14)])

    def test_strong_and_weak_verdicts_partition_the_positive_side(self) -> None:
        self.assertEqual(set(seq.STRONG_VERDICTS) | set(seq.WEAK_VERDICTS) | {"uncertain"},
                         set(seq.VERDICTS))
        self.assertEqual(set(seq.STRONG_VERDICTS) & set(seq.WEAK_VERDICTS), set())


# ---------------------------------------------------------------------------
# 2. artifact 闸门：模板与 fixture
# ---------------------------------------------------------------------------


class TestArtifactGate(unittest.TestCase):
    def test_template_passes(self) -> None:
        report = seq.check_artifact(_load(TEMPLATE), source=str(TEMPLATE))
        self.assertEqual(report.rules(), [], [v.render() for v in report.violations])

    def test_fixtures_exist_and_are_not_empty(self) -> None:
        names = {p.stem for p in FIXTURES.glob("*.json")}
        self.assertEqual(names, set(FIXTURE_VERDICTS),
                         f"fixture 目录内容与 policy §14.2 的四个具名样例不符：{names}")

    def test_each_fixture_passes_and_keeps_its_expected_verdict(self) -> None:
        for name, verdict in FIXTURE_VERDICTS.items():
            doc = _load(FIXTURES / f"{name}.json")
            self.assertEqual(doc["verdict"], verdict, f"{name}.json 的 verdict 被改动")
            report = seq.check_artifact(doc, source=name)
            self.assertEqual(report.rules(), [],
                             f"{name}.json：{[v.render() for v in report.violations]}")

    def test_schema_typo_is_an_environment_error(self) -> None:
        doc = _load(TEMPLATE)
        doc["schema"] = "research-idea-pipeline/structural-equivalence-audit@2"
        self.assertEqual(seq.check_artifact(doc).exit_code(), seq.EXIT_ENV)

    def test_strong_verdict_with_all_unchanged_is_rejected(self) -> None:
        doc = _load(TEMPLATE)
        for key in seq.LOAD_BEARING_KEYS:
            doc["load_bearing_analysis"][key] = "unchanged"
        self.assertIn("EQ7", seq.check_artifact(doc).rules())

    def test_domain_stripped_leak_is_rejected(self) -> None:
        doc = _load(TEMPLATE)
        doc["domain_stripped_alignment"]["setting"] = "MRI 多中心采集"
        self.assertIn("EQ6", seq.check_artifact(doc).rules())

    def test_collapse_verdict_mismatch_is_rejected(self) -> None:
        doc = _load(TEMPLATE)
        doc["counterfactual_collapse"]["collapse_result"] = "collapses"
        self.assertIn("EQ8", seq.check_artifact(doc).rules())

    def test_forbidden_novelty_wording_is_rejected(self) -> None:
        for phrase in ("no prior work exists", "unprecedented", "没人做过", "无人研究"):
            doc = _load(TEMPLATE)
            doc["novelty_boundary"] = f"this is {phrase} 的前作"
            self.assertIn("EQ10", seq.check_artifact(doc, source=phrase).rules(),
                          f"`{phrase}` 未被拦下")

    def test_retrieval_insufficient_requires_the_sanctioned_wording(self) -> None:
        doc = _load(TEMPLATE)
        doc["retrieval_status"] = "retrieval-insufficient"
        doc["closest_priors"] = []
        doc["evidence"] = ["LIT42"]
        doc["novelty_boundary"] = "覆盖不足，无法判断。"
        self.assertIn("EQ10", seq.check_artifact(doc).rules())
        doc["novelty_boundary"] = ("against the retrieved literature, "
                                   "no structural equivalent was identified")
        self.assertNotIn("EQ10", seq.check_artifact(doc).rules())


# ---------------------------------------------------------------------------
# 3. route 模式：state ↔ artifact 交叉校验
# ---------------------------------------------------------------------------


class TestRouteMode(unittest.TestCase):
    REF = ".research-idea-pipeline/routes/T/assurance/structural-equivalence/H1.json"

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = pathlib.Path(self.tmp.name)
        self.route = self.project / ".research-idea-pipeline" / "routes" / "T"
        (self.route / "assurance" / "structural-equivalence").mkdir(parents=True)
        self.artifact = _load(TEMPLATE)
        self.artifact["candidate"] = "H1"
        self.artifact["closest_priors"] = ["LIT1"]
        self.artifact["evidence"] = ["LIT1"]
        self.state: Dict[str, Any] = {
            "state_version": 0,
            "hypotheses": [{"id": "H1"}],
            "literature": [{"id": "LIT1"}],
            "assurance": [{
                "kill_condition": "若替换 delta 后承重后果不变，则 novelty 主张失败",
                "discriminating_test": "TBD",
                "verification_tier": "T0",
                "target": "H1",
                "attack_type": "structural-equivalence",
                "literature": ["LIT1"],
                "audit_ref": self.REF,
            }],
        }
        self._write()

    def _write(self, artifact: Optional[Dict[str, Any]] = None) -> None:
        (self.route / "research-state.json").write_text(
            json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
        (self.route / "assurance" / "structural-equivalence" / "H1.json").write_text(
            json.dumps(artifact if artifact is not None else self.artifact,
                       ensure_ascii=False), encoding="utf-8")

    def test_valid_route_passes(self) -> None:
        report = seq.check_route(self.route)
        self.assertEqual(report.rules(), [], [v.render() for v in report.violations])

    def test_missing_artifact_hits_eq1(self) -> None:
        (self.route / "assurance" / "structural-equivalence" / "H1.json").unlink()
        self.assertIn("EQ1", seq.check_route(self.route).rules())

    def test_illegal_audit_ref_hits_eq12(self) -> None:
        self.state["assurance"][0]["audit_ref"] = "assurance/H1.json"
        self._write()
        self.assertIn("EQ12", seq.check_route(self.route).rules())

    def test_audit_ref_target_mismatch_hits_eq12(self) -> None:
        self.state["assurance"][0]["target"] = "H9"
        self._write()
        self.assertIn("EQ12", seq.check_route(self.route).rules())

    def test_unknown_target_hits_eq2(self) -> None:
        self.state["assurance"][0]["target"] = "H7"
        self.state["assurance"][0]["audit_ref"] = \
            ".research-idea-pipeline/routes/T/assurance/structural-equivalence/H7.json"
        (self.route / "assurance" / "structural-equivalence" / "H7.json").write_text(
            json.dumps({**self.artifact, "candidate": "H7"}, ensure_ascii=False),
            encoding="utf-8")
        self._write()
        self.assertIn("EQ2", seq.check_route(self.route).rules())

    def test_unknown_literature_hits_eq3(self) -> None:
        self.state["assurance"][0]["literature"] = ["LIT99"]
        self._write()
        self.assertIn("EQ3", seq.check_route(self.route).rules())

    def test_unreferenced_artifact_hits_eq12(self) -> None:
        self.state["assurance"] = []
        self._write()
        self.assertIn("EQ12", seq.check_route(self.route).rules())

    def test_route_without_artifacts_directory_is_legal(self) -> None:
        shutil.rmtree(self.route / "assurance")
        self.state["assurance"] = []
        (self.route / "research-state.json").write_text(
            json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
        report = seq.check_route(self.route)
        self.assertEqual(report.rules(), [], [v.render() for v in report.violations])

    def test_missing_state_is_an_environment_error(self) -> None:
        (self.route / "research-state.json").unlink()
        self.assertEqual(seq.check_route(self.route).exit_code(), seq.EXIT_ENV)


# ---------------------------------------------------------------------------
# 4. metamorphic 套件 T1—T10（policy §14.2）
# ---------------------------------------------------------------------------


def _variant(verdict: str, claimed: str) -> Dict[str, Any]:
    """按 verdict 的强弱，构造一份结构自洽的 artifact。"""
    doc = _load(TEMPLATE)
    doc["verdict"] = verdict
    doc["claimed_novelty_level"] = claimed
    strong = verdict in seq.STRONG_VERDICTS
    if strong:
        doc["minimal_structural_delta"] = ["承重结构发生改变：目标量与信息流同时变化"]
        doc["load_bearing_analysis"] = {
            "changed_information": "目标量的可观测量改变",
            "changed_assumptions": "新增一条承重假设",
            "changed_mechanism": "信息流路径改变",
            "changed_predictions": "新增可证伪预测",
            "changed_boundary": "新增失败边界",
        }
        doc["counterfactual_collapse"] = {
            "replacement": "把 delta 换回 prior 的对应结构",
            "predicted_consequence": "承重后果消失，说明 delta 承重",
            "collapse_result": "does-not-collapse",
        }
        doc["differentiating_consequences"] = ["一条可判定的新后果"]
        doc["discriminating_tests"] = ["X1"]
    else:
        doc["minimal_structural_delta"] = []
        doc["load_bearing_analysis"] = {key: "unchanged" for key in seq.LOAD_BEARING_KEYS}
        doc["counterfactual_collapse"] = {
            "replacement": "把 surface 术语换回 prior 的写法",
            "predicted_consequence": "目标、假设、预测、失败边界均不变",
            "collapse_result": "collapses",
        }
        doc["differentiating_consequences"] = []
        doc["discriminating_tests"] = []
    return doc


# (编号, 变体名, 期望 verdict, 合理的 claimed level)
METAMORPHIC_CASES: Tuple[Tuple[str, str, str, str], ...] = (
    ("T1", "Terminology Rename", "equivalent", "none"),
    ("T2", "Theory Relabel", "reframing-only", "none"),
    ("T3", "Cross-Domain Transfer", "transfer-only", "transfer-only"),
    ("T4", "Component Mutation", "component-delta", "component-delta"),
    ("T5", "Mechanism Mutation", "mechanism-delta", "mechanism-delta"),
    ("T6", "Assumption Removal", "formulation-delta", "formulation-delta"),
    ("T7", "New Boundary", "boundary-delta", "boundary-delta"),
    ("T8", "Narrative Rewrite", "equivalent", "none"),
    ("T9", "Hidden Prior Collision", "subsumed-by-prior", "none"),
    ("T10", "Genuine Paradigm Candidate", "paradigm-candidate", "paradigm-candidate"),
)


class TestMetamorphicStructure(unittest.TestCase):
    """T1—T10：正例必须通过；**过度声称必须被拦下**（`FalseParadigmRate` 的防线）。"""

    def test_policy_declares_exactly_these_ten_variants(self) -> None:
        table = _section("### 14.2 metamorphic 套件", "这些测试的重点")
        declared = re.findall(r"^\| (T\d+) \| (.+?) \|", table, re.M)
        self.assertEqual([tag for tag, _ in declared],
                         [tag for tag, *_ in METAMORPHIC_CASES],
                         "policy §14.2 的 T1—T10 与测试表不一致")

    def test_each_variant_is_structurally_complete(self) -> None:
        for tag, name, verdict, claimed in METAMORPHIC_CASES:
            report = seq.check_artifact(_variant(verdict, claimed), source=f"{tag} {name}")
            self.assertEqual(report.rules(), [],
                             f"{tag} {name}：{[v.render() for v in report.violations]}")

    def test_overclaiming_paradigm_is_always_rejected(self) -> None:
        for tag, name, verdict, _claimed in METAMORPHIC_CASES:
            if verdict in seq.STRONG_VERDICTS:
                continue
            doc = _variant(verdict, "paradigm-candidate")
            self.assertIn("EQ13", seq.check_artifact(doc, source=f"{tag} {name}").rules(),
                          f"{tag} {name}：把弱 verdict 过度声称成 paradigm-candidate 没被拦下")

    def test_strong_verdict_without_load_bearing_change_is_rejected(self) -> None:
        for tag, name, verdict, _claimed in METAMORPHIC_CASES:
            if verdict not in seq.STRONG_VERDICTS:
                continue
            doc = _variant(verdict, "paradigm-candidate")
            doc["load_bearing_analysis"] = {k: "unchanged" for k in seq.LOAD_BEARING_KEYS}
            self.assertIn("EQ7", seq.check_artifact(doc, source=f"{tag} {name}").rules(),
                          f"{tag} {name}：强 verdict 没有承重改变却没被拦下")

    def test_strong_verdict_that_collapses_is_rejected(self) -> None:
        for tag, name, verdict, _claimed in METAMORPHIC_CASES:
            if verdict not in seq.STRONG_VERDICTS:
                continue
            doc = _variant(verdict, "paradigm-candidate")
            doc["counterfactual_collapse"]["collapse_result"] = "collapses"
            self.assertIn("EQ8", seq.check_artifact(doc, source=f"{tag} {name}").rules(),
                          f"{tag} {name}：声称强 delta 却记录完全坍缩，没被拦下")

    def test_uncertain_cannot_carry_a_paradigm_claim(self) -> None:
        doc = _variant("uncertain", "paradigm-candidate")
        self.assertIn("EQ13", seq.check_artifact(doc).rules())


# ---------------------------------------------------------------------------
# 5. 发布闸门的那一步必须可被判红（Rule 5 / Rule 10）
# ---------------------------------------------------------------------------


class TestReleaseGateStep(unittest.TestCase):
    """`release_check.step_structural_equivalence` 必须能 FAIL，不是恒真。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls._originals = {path: path.read_text(encoding="utf-8")
                          for path in (TEMPLATE, FIXTURES / "paradigm-candidate.json")}

    @classmethod
    def tearDownClass(cls) -> None:
        for path, original in cls._originals.items():
            if path.read_text(encoding="utf-8") != original:
                path.write_text(original, encoding="utf-8")

    def setUp(self) -> None:
        import release_check
        self.rc = release_check

    def _mutate(self, path: pathlib.Path, old: str, new: str):
        original = path.read_text(encoding="utf-8")
        self.assertIn(old, original, msg=f"{path.name} 里找不到待改文本")
        path.write_text(original.replace(old, new, 1), encoding="utf-8")
        try:
            return self.rc.step_structural_equivalence()
        finally:
            path.write_text(original, encoding="utf-8")

    def test_step_passes_on_current_tree(self) -> None:
        ok, detail = self.rc.step_structural_equivalence()
        self.assertTrue(ok, detail)
        self.assertIn("全绿", detail)

    def test_step_detects_an_illegal_verdict_in_the_template(self) -> None:
        ok, _ = self._mutate(TEMPLATE, '"verdict": "formulation-delta"',
                             '"verdict": "super-novel"')
        self.assertFalse(ok, "模板里的非法 verdict 必须让该步骤 FAIL")

    def test_step_detects_a_broken_fixture(self) -> None:
        ok, _ = self._mutate(FIXTURES / "paradigm-candidate.json",
                             '"collapse_result": "does-not-collapse"',
                             '"collapse_result": "collapses"')
        self.assertFalse(ok, "fixture 与 verdict 不相容时该步骤必须 FAIL")

    def test_step_title_is_registered(self) -> None:
        titles = [title for title, _ in self.rc.STEPS]
        self.assertTrue(any("Structural Equivalence" in title for title in titles),
                        f"STEPS 未登记 Structural Equivalence 闸门：{titles}")


# ---------------------------------------------------------------------------
# 6. 打包完整性 / 登记完整性（Rule 5：每类新缺陷配一条检查）
# ---------------------------------------------------------------------------


class TestRegistrationAndPackaging(unittest.TestCase):
    def test_help_does_not_point_outside_the_package(self) -> None:
        text = seq.build_parser().format_help()
        self.assertNotIn("docs/", text, "--help 指向了不随包安装的文件")
        self.assertIn("references/structural-equivalence-policy.md", text,
                      "help 必须指向包内权威政策")

    def test_violation_messages_do_not_leak_dev_paths(self) -> None:
        doc = _load(TEMPLATE)
        doc["verdict"] = "super-novel"
        _, out, err = _run("--artifact", str(TEMPLATE), "--json")
        self.assertNotIn("docs/", out + err)

    def test_list_rules_matches_the_rule_table(self) -> None:
        code, out, _ = _run("--list-rules")
        self.assertEqual(code, seq.EXIT_OK)
        listed = dict(re.findall(r"^(EQ\d+)\s+硬\s{2}(.+)$", out, re.M))
        self.assertEqual(listed, seq.RULES)

    def test_new_assets_are_registered_in_skill(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for rel in ("references/structural-equivalence-policy.md",
                    "templates/structural-equivalence-audit.template.json",
                    "scripts/structural_equivalence_check.py"):
            self.assertIn(rel, skill, f"SKILL.md §2 资源索引未登记 {rel}")

    def test_every_fixture_is_registered_in_readme(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("structural-equivalence/", readme,
                      "README 未登记 structural-equivalence fixture 目录")
        for name in FIXTURE_VERDICTS:
            self.assertIn(f"{name}.json", readme,
                          f"README 未登记 fixture {name}.json")

    def test_new_gate_is_documented_in_skill_selfcheck(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("structural_equivalence_check.py", skill,
                      "SKILL §8 D 未登记新的机械闸门")

    def test_cli_requires_exactly_one_mode(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            _run("--artifact", str(TEMPLATE), "--route", ".")
        self.assertEqual(ctx.exception.code, seq.EXIT_ERROR)

    def test_cli_is_json_silent_about_human_lines(self) -> None:
        code, out, _ = _run("--artifact", str(TEMPLATE), "--json")
        self.assertEqual(code, seq.EXIT_OK)
        self.assertNotIn("PASS", out)
        self.assertEqual(json.loads(out)["exit_code"], seq.EXIT_OK)


class TestFrozenBoundaries(unittest.TestCase):
    """用户硬约束的机械守卫：不新增 R 阶段 / 第九类对象 / 评分 / persona / venue 泄漏。"""

    def _policy(self) -> str:
        return POLICY.read_text(encoding="utf-8")

    def test_no_new_r_stage_is_referenced(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"R1[5-9]", skill), [],
                         "SKILL.md 出现了 R15 及之后的阶段号")

    def test_no_ninth_state_object_is_declared(self) -> None:
        import state_check as sc
        self.assertEqual(len(sc.FIRST_CLASS_KEYS), 8, "八类一等对象的数量被改动")
        self.assertEqual(sc.EXTRA_KEYS, ("assurance", "repairs"),
                         "assurance / repairs 之外的载体被当成一级对象")
        template = _load(ROOT / "templates" / "research-state.template.json")
        leaked = [key for key in template
                  if "structural" in key.lower() and not key.startswith("_")]
        self.assertEqual(leaked, [], f"state 模板出现了新的顶层结构对象：{leaked}")

    def test_no_numeric_novelty_score_in_the_new_policy(self) -> None:
        """§1—§12 是定义区，不得出现任何数值 novelty 判据。

        §13「明令禁止的退化」**有意引用**这些反模式原文，因此排除在扫描之外；
        同时对 §13 做正向断言，保证「引用了反模式」这件事还在。
        """
        text = self._policy()
        body = text[:text.index("## 13. 明令禁止的退化")]
        negations = ("不产", "不得", "不是", "禁止", "不新增", "无")
        for pattern in (r"novelty[_ ]score\s*=", r"structural_similarity\s*=",
                        r"\d\s*—\s*5\s*分", r"<\s*0\.5\s*=>"):
            for line in body.splitlines():
                if re.search(pattern, line) and not any(neg in line for neg in negations):
                    self.fail(f"新政策定义区出现了数值 novelty 判据：{pattern} → {line.strip()[:80]}")
        self.assertIn("verdict 是 category，不是 score", text)
        self.assertIn("structural_similarity_score", text)
        self.assertIn("<0.5 => novel", text)

    def test_no_embedding_or_text_similarity_definition(self) -> None:
        self.assertIn("禁止**用文本相似度、embedding similarity、普通 graph isomorphism",
                      self._policy())

    def test_no_new_reviewer_persona(self) -> None:
        self.assertIn("不新增 persona", self._policy())
        roles = (ROOT / "references" / "roles.md").read_text(encoding="utf-8")
        self.assertNotIn("SENA", roles, "roles.md 里出现了 SENA 人格")

    def test_no_venue_fit_inside_the_equivalence_judgement(self) -> None:
        for line in self._policy().splitlines():
            if "venue" in line.lower() and "structural" in line.lower():
                self.assertTrue(any(ok in line for ok in ("不得", "不进入", "无 venue")),
                                f"venue fit 进入了结构等价判断：{line.strip()[:80]}")

    def test_assurance_extension_fields_have_carriers_and_a_documented_producer(self) -> None:
        """Producer → Carrier → Consumer：新增四个可选字段三侧齐全。"""
        template = _load(ROOT / "templates" / "research-state.template.json")
        sample = template["assurance"][0]
        policy = (ROOT / "references" / "research-state-policy.md").read_text("utf-8")
        missing: List[str] = []
        for field in ("target", "attack_type", "literature", "audit_ref"):
            if field not in sample:
                missing.append(f"模板 assurance[0] 缺载体 {field}")
            if f"`assurance[].{field}`" not in policy:
                missing.append(f"policy 未登记 `assurance[].{field}`")
        self.assertEqual(missing, [], "carrier/spec 缺口")
        consumers = seq.RULES["EQ2"] + seq.RULES["EQ3"] + seq.RULES["EQ12"] + self._policy()
        for field in ("target", "literature", "audit_ref"):
            self.assertIn(field, consumers, f"{field} 没有消费者")
        phase_r7 = (ROOT / "references" / "phase-r7-r10-r13-assurance-repair-review.md"
                    ).read_text(encoding="utf-8")
        self.assertIn("`audit_ref`", phase_r7, "R7 未登记 audit_ref 的生产动作")

    def test_artifact_paths_are_declared_consistently(self) -> None:
        text = self._policy()
        for path in (seq.AUDIT_DIR, seq.FINGERPRINT_DIR):
            self.assertIn(path, text, f"policy §9.1 未声明 artifact 路径 {path}")
        self.assertIn(seq.AUDIT_DIR, seq.AUDIT_REF_PATTERN.pattern)

    def test_control_plane_dirs_are_documented(self) -> None:
        layout = (ROOT / "references" / "project-layout.md").read_text(encoding="utf-8")
        self.assertIn("populations/{archive/,intermediates/,fingerprints/}", layout)
        self.assertIn("assurance/{structural-equivalence/}", layout)


if __name__ == "__main__":
    unittest.main()
