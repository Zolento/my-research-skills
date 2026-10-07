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

# fixture 名 → (期望 near_neighbor_verdict, 期望 verdict)（policy §23.2 相容表）
FIXTURE_VERDICTS: Dict[str, Tuple[str, str]] = {
    "equivalent": ("duplicate-equivalent", "equivalent"),
    "reframing-neighbor": ("reframing-neighbor", "reframing-only"),
    "transfer-only": ("transfer-neighbor", "transfer-only"),
    "component-neighbor": ("component-neighbor", "component-delta"),
    "mechanism-neighbor": ("mechanism-neighbor", "mechanism-delta"),
    "formulation-delta": ("structural-delta", "formulation-delta"),
    "paradigm-candidate": ("structural-delta-strong", "paradigm-candidate"),
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
        self.assertEqual(rows, {k: v for k, v in seq.RULES.items() if k.startswith("EQ")},
                         "policy §12.1 的 EQ1—EQ13 判据与检查器 RULES 不一致")

    def test_nn_rule_table_matches_policy(self) -> None:
        rows = dict(re.findall(
            r"^\| `(NN\d+)` \| (.+?) \|$",
            _section("## 30. 机械闸门", "> **脚本不得决定"), re.M))
        self.assertEqual(len(rows), 14, f"policy §30 只解析出 {len(rows)} 条规则行")
        self.assertEqual(rows, {k: v for k, v in seq.RULES.items() if k.startswith("NN")},
                         "policy §30 的 NN1—NN14 判据与检查器 RULES 不一致")

    def test_documented_nn_ranges_match_checker(self) -> None:
        expected = [key for key in seq.RULES if key.startswith("NN")]
        paths = [ROOT / "SKILL.md", POLICY, TEMPLATE,
                 ROOT / "references" / "phase-r7-r10-r13-assurance-repair-review.md"]
        for path in paths:
            ranges = re.findall(r"`?(NN1)`?—`?(NN\d+)`?", path.read_text())
            self.assertTrue(ranges, str(path))
            for first, last in ranges:
                self.assertEqual((first, last), (expected[0], expected[-1]), str(path))

    def test_counterfactual_verification_enum_matches_policy(self) -> None:
        line = next(line for line in _policy().splitlines()
                    if line.startswith("| `verification_status` |"))
        rows = re.findall(r"`([a-z_-]+)`", line)[1:]
        self.assertEqual(tuple(rows), seq.COUNTERFACTUAL_VERIFICATION,
                         "policy §6.1 的 verification_status 四值与检查器不一致")
        self.assertEqual(seq.COUNTERFACTUAL_MIN_STRONG, ("derived", "executed"))
        self.assertTrue(set(seq.COUNTERFACTUAL_MIN_STRONG) <= set(seq.COUNTERFACTUAL_VERIFICATION))

    def test_near_neighbor_verdicts_match_policy(self) -> None:
        rows = re.findall(r"^\| `([a-z-]+)` \|",
                          _section("### 23.1 枚举", "### 23.2"), re.M)
        self.assertEqual(tuple(rows), seq.NEAR_NEIGHBOR_VERDICTS,
                         "policy §23.1 的八值与检查器 NEAR_NEIGHBOR_VERDICTS 不一致")

    def test_correspondence_relation_and_provenance_match_policy(self) -> None:
        relations = re.findall(r"^\| `([A-Z]+)` \|", _section("### 21.2 三值", "### 21.3"), re.M)
        self.assertEqual(tuple(relations), seq.CORRESPONDENCE_RELATIONS)
        provenance = re.findall(r"^\| `([A-Z]+)` \|", _section("### 21.1 每个 facet", "### 21.2"), re.M)
        self.assertEqual(tuple(provenance), seq.PROVENANCE)

    def test_local_modification_kinds_match_policy(self) -> None:
        rows = re.findall(r"^\| `([a-z-]+)` \|$", _section("### 16.3 Local", "## 17."), re.M)
        self.assertEqual(tuple(rows), seq.LOCAL_MODIFICATION_KINDS,
                         "policy §16.3 的十一类与检查器不一致")

    def test_theory_new_structure_kinds_match_policy(self) -> None:
        rows = re.findall(r"^\| `([a-z-]+)` \|$", _section("## 19. Theory-Stripping", "**除非**"), re.M)
        self.assertEqual(tuple(rows), seq.THEORY_NEW_STRUCTURE_KINDS,
                         "policy §19 的六类与检查器不一致")

    def test_trust_bases_match_policy(self) -> None:
        rows = re.findall(r"^\| `([a-z-]+)` \|$",
                          _section("### 21.3 可信度来源", "**落地键：**"), re.M)
        self.assertEqual(tuple(rows), seq.TRUST_BASES,
                         "policy §21.3 的八值与检查器 TRUST_BASES 不一致")

    def test_novel_consequence_kinds_match_policy(self) -> None:
        tail = _policy().split("`novel_consequence_kinds` 逐字为：", 1)[1][:120]
        rows = re.findall(r"`([a-z]+)`", tail)
        self.assertEqual(tuple(rows), seq.NOVEL_CONSEQUENCE_KINDS,
                         "policy §22.2 的五值与检查器不一致")

    def test_nn_compatibility_table_matches_policy(self) -> None:
        table = _section("### 23.2 与", "## 24. artifact")
        rows = {}
        ceilings = {}
        for line in table.splitlines():
            match = re.match(r"^\| `([a-z-]+)` \| (.+?) \| `([a-z-]+)` \|$", line)
            if match:
                rows[match.group(1)] = tuple(re.findall(r"`([a-z-]+)`", match.group(2)))
                ceilings[match.group(1)] = match.group(3)
        self.assertEqual(rows, seq.NN_ALLOWED_VERDICTS,
                         "policy §23.2 的 verdict 相容表与代码不一致")
        self.assertEqual(ceilings, seq.NN_CLAIM_CEILING,
                         "policy §23.2 的 claim 上限表与代码不一致")

    def test_rule_order_is_eq1_to_eq13_then_nn1_to_nn14(self) -> None:
        self.assertEqual(seq.RULE_ORDER,
                         [f"EQ{n}" for n in range(1, 14)] + [f"NN{n}" for n in range(1, 15)])

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
        for name, (near, verdict) in FIXTURE_VERDICTS.items():
            doc = _load(FIXTURES / f"{name}.json")
            self.assertEqual(doc["verdict"], verdict, f"{name}.json 的 verdict 被改动")
            self.assertEqual(doc["near_neighbor_verdict"], near,
                             f"{name}.json 的 near_neighbor_verdict 被改动")
            report = seq.check_artifact(doc, source=name)
            self.assertEqual(report.rules(), [],
                             f"{name}.json：{[v.render() for v in report.violations]}")

    def test_schema_typo_is_an_environment_error(self) -> None:
        doc = _load(TEMPLATE)
        doc["schema"] = "research-idea-pipeline/structural-equivalence-audit@3"
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


# round-1 verdict → near_neighbor_verdict（policy §23.2 相容表）
_NEAR_BY_VERDICT: Dict[str, str] = {
    "equivalent": "duplicate-equivalent",
    "subsumed-by-prior": "duplicate-equivalent",
    "reframing-only": "reframing-neighbor",
    "transfer-only": "transfer-neighbor",
    "component-delta": "component-neighbor",
    "mechanism-delta": "mechanism-neighbor",
    "formulation-delta": "structural-delta",
    "boundary-delta": "structural-delta",
    "paradigm-candidate": "structural-delta-strong",
    "uncertain": "uncertain",
}


def _variant(verdict: str, claimed: str) -> Dict[str, Any]:
    """按 verdict 的强弱，构造一份结构自洽的 artifact（含 near-neighbor 层）。"""
    near = _NEAR_BY_VERDICT[verdict]
    if verdict not in seq.STRONG_VERDICTS:
        extra: Dict[str, Any] = {}
        if verdict == "uncertain":
            extra["collapse"] = "partially-collapses"
        return nn_artifact(near, verdict, claimed, **extra)
    extra = dict(_DELTA)
    if near == "structural-delta-strong":
        extra.update({"different": ("boundary_or_failure_regime",),
                      "bearings": ("boundary_or_failure_regime",),
                      "consequence_kinds": ("boundary", "experiment")})
    return nn_artifact(near, verdict, claimed, **extra)


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
# 4b. Near-neighbor metamorphic 套件 NN-1—NN-12（policy §31）
# ---------------------------------------------------------------------------


_NA = {"applicable": False, "stripped_terms": [], "residual_structure": "not-applicable",
       "adds_new_structure": False, "new_structure_kinds": [], "conclusion": "not-applicable"}
_ANALOGY_NA = {"applicable": False, "object_mapping": "n/a", "relation_mapping": "n/a",
               "constraint_mapping": "n/a", "failure_mode_mapping": "n/a",
               "added_structure": False, "conclusion": "not-applicable"}


def nn_artifact(near, verdict, claimed, *, different=(), bearings=("information_flow", "mechanism"),
                local_kinds=(), confirmed=True, removal="component-local-delta", nullmap="full",
                unmapped=(), delta_set=(), consequence_kinds=(), consequences=(), tests=(),
                collapse="collapses", theory=None, analogy=None, trust=("source-span", "equation"),
                load=None):
    """构造一份结构自洽的 near-neighbor artifact（测试用）。"""
    if load is None:
        load = {key: "unchanged" for key in seq.LOAD_BEARING_KEYS}
        if verdict in seq.STRONG_VERDICTS:
            load["changed_information"] = "真实承重改变"
    return {
        "schema": seq.SCHEMA, "stage": "R7", "candidate": "H1",
        "closest_priors": ["LIT1"], "retrieval_status": "sufficient", "domain_terms": ["MRI"],
        "domain_aware_alignment": {f: f"domain {f}" for f in seq.FACETS},
        "domain_stripped_alignment": {f: f"role {f}" for f in seq.FACETS},
        "matched_core": ["core"], "candidate_only_elements": [], "prior_only_elements": [],
        "minimal_structural_delta": list(delta_set), "load_bearing_analysis": load,
        "counterfactual_collapse": {"replacement": "r", "predicted_consequence": "p",
                                    "collapse_result": collapse,
                                    "verification_status": ("derived" if collapse == "does-not-collapse"
                                                            else "predicted")},
        "differentiating_consequences": list(consequences), "discriminating_tests": list(tests),
        "claimed_novelty_level": claimed, "verdict": verdict,
        "novelty_boundary": "against the retrieved literature, no structural equivalent was identified",
        "blind_spots": ["blind"], "evidence": ["LIT1"],
        "near_neighbor_verdict": near,
        "correspondence": {f: {"relation": "DIFFERENT" if f in different else "MATCH",
                               "provenance": "DERIVED" if f in different else "EXPLICIT",
                               "evidence_span": "span", "note": "note"} for f in seq.FACETS},
        "load_bearing_facets": list(bearings),
        "local_neighborhood_test": {"near_prior": "LIT1",
                                    "local_modification_kinds": list(local_kinds),
                                    "neighbor_confirmed": confirmed, "rationale": "r"},
        "removal_test": {"removed_delta": "d",
                         "returns_to_prior": "LIT1" if removal == "component-local-delta" else "",
                         "unchanged_core": [], "conclusion": removal},
        "null_hypothesis": {"statement": seq.NULL_HYPOTHESIS_STATEMENT,
                            "strongest_subsumption_prior": "LIT1",
                            "mapping_completeness": nullmap,
                            "unmapped_load_bearing_elements": list(unmapped)},
        "minimal_delta_set": {"delta_set": list(delta_set),
                              "novel_consequence_kinds": list(consequence_kinds),
                              "sufficient_alone": bool(delta_set)},
        "theory_stripping": theory or dict(_NA),
        "remote_analogy_mapping": analogy or dict(_ANALOGY_NA),
        "trust_basis": list(trust),
    }


_THEORY_RELABEL = {"applicable": True, "stripped_terms": ["theory brand"],
                   "residual_structure": "stripping 后与 prior 逐项一致",
                   "adds_new_structure": False, "new_structure_kinds": [],
                   "conclusion": "theory-relabeling-risk"}
_ANALOGY_EXPLANATION = {"applicable": True, "object_mapping": "o", "relation_mapping": "r",
                        "constraint_mapping": "c", "failure_mode_mapping": "f",
                        "added_structure": False, "conclusion": "explanation-only"}
_DELTA = {"collapse": "does-not-collapse", "confirmed": False, "removal": "load-bearing-delta",
          "nullmap": "failed", "delta_set": ("d",), "consequence_kinds": ("prediction",),
          "consequences": ("c",), "tests": ("X1",)}
_MECH = {"different": ("mechanism", "information_flow"), "collapse": "partially-collapses",
         "delta_set": ("d",), "consequence_kinds": ("algorithm",), "consequences": ("c",),
         "tests": ("X1",), "nullmap": "partial", "unmapped": ("mechanism",)}

# (编号, 名称, near_neighbor_verdict, verdict, claimed, 额外参数, 允许的 near 集合)
NN_CASES: Tuple[Tuple[str, str, str, str, str, Dict[str, Any], Tuple[str, ...]], ...] = (
    ("NN-1", "Rename", "duplicate-equivalent", "equivalent", "none", {}, ("duplicate-equivalent",)),
    ("NN-2", "Narrative rewrite", "reframing-neighbor", "reframing-only", "none", {},
     ("reframing-neighbor",)),
    ("NN-3", "Theory relabel", "reframing-neighbor", "reframing-only", "none",
     {"theory": _THEORY_RELABEL}, ("reframing-neighbor",)),
    ("NN-4", "Cross-domain port", "transfer-neighbor", "transfer-only", "transfer-only",
     {"analogy": _ANALOGY_EXPLANATION}, ("transfer-neighbor",)),
    ("NN-5", "New regularizer", "component-neighbor", "component-delta", "component-delta",
     {"local_kinds": ("regularizer",)}, ("component-neighbor",)),
    ("NN-6", "New parameterization", "component-neighbor", "component-delta", "component-delta",
     {}, ("component-neighbor", "mechanism-neighbor")),
    ("NN-7", "Mechanism change", "mechanism-neighbor", "mechanism-delta", "mechanism-delta",
     _MECH, ("mechanism-neighbor", "structural-delta")),
    ("NN-8", "Assumption removal", "structural-delta", "formulation-delta", "formulation-delta",
     {**_DELTA, "different": ("assumptions",), "bearings": ("assumptions",)},
     ("structural-delta",)),
    ("NN-9", "Observable change", "structural-delta", "formulation-delta", "formulation-delta",
     {**_DELTA, "different": ("observables",), "bearings": ("observables",)},
     ("structural-delta",)),
    ("NN-10", "New impossibility boundary", "structural-delta-strong", "paradigm-candidate",
     "paradigm-candidate",
     {**_DELTA, "different": ("boundary_or_failure_regime",),
      "bearings": ("boundary_or_failure_regime",), "consequence_kinds": ("boundary", "experiment")},
     ("structural-delta-strong",)),
    ("NN-11", "Semantic far / structural same", "duplicate-equivalent", "equivalent", "none", {},
     ("duplicate-equivalent",)),
    ("NN-12", "Semantic close / structural different", "structural-delta", "formulation-delta",
     "formulation-delta",
     {**_DELTA, "different": ("assumptions", "observables", "predictions_or_guarantees"),
      "bearings": ("assumptions", "observables", "predictions_or_guarantees")},
     ("structural-delta",)),
)


class TestNearNeighborMetamorphic(unittest.TestCase):
    """NN-1—NN-12：语义距离 ≠ 科学距离（policy §31）。"""

    def test_policy_declares_exactly_these_twelve_variants(self) -> None:
        table = _section("## 31. Near-Neighbor metamorphic", "> **NN-11 与 NN-12")
        declared = re.findall(r"^\| (NN-\d+) \|", table, re.M)
        self.assertEqual(declared, [tag for tag, *_ in NN_CASES],
                         "policy §31 的 NN-1—NN-12 与测试表不一致")

    def test_each_variant_keeps_its_expected_verdict(self) -> None:
        for tag, name, near, verdict, claimed, extra, allowed in NN_CASES:
            doc = nn_artifact(near, verdict, claimed, **extra)
            report = seq.check_artifact(doc, source=f"{tag} {name}")
            self.assertEqual(report.rules(), [],
                             f"{tag} {name}：{[v.render() for v in report.violations]}")
            self.assertEqual(doc["near_neighbor_verdict"], near)
            self.assertIn(doc["near_neighbor_verdict"], allowed)

    def test_override_binary_same_or_different_is_rejected(self) -> None:
        for tag, name, near, verdict, claimed, extra, _allowed in NN_CASES:
            doc = nn_artifact(near, verdict, claimed, **extra)
            doc["correspondence"]["mechanism"]["relation"] = "SAME"
            self.assertIn("NN2", seq.check_artifact(doc, source=f"{tag} {name}").rules(),
                          f"{tag} {name}：强制二值 SAME 没被拦下")

    def test_essential_unresolved_never_becomes_a_strong_verdict(self) -> None:
        cases = (
            ("structural-delta", "formulation-delta", "formulation-delta", _DELTA),
            ("structural-delta-strong", "paradigm-candidate", "paradigm-candidate",
             {**_DELTA, "different": ("boundary_or_failure_regime",),
              "bearings": ("boundary_or_failure_regime",),
              "consequence_kinds": ("boundary", "experiment")}),
        )
        for near, verdict, claimed, extra in cases:
            doc = nn_artifact(near, verdict, claimed, **extra)
            for facet in doc["load_bearing_facets"]:
                doc["correspondence"][facet]["relation"] = "UNRESOLVED"
            rules = seq.check_artifact(doc, source=f"{near}+UNRESOLVED").rules()
            self.assertIn("NN3", rules,
                          f"{near}：load-bearing facet 全 UNRESOLVED 时仍给了强 verdict")

    def test_two_unresolved_forces_uncertain(self) -> None:
        doc = nn_artifact("component-neighbor", "component-delta", "component-delta",
                          bearings=("objective", "mechanism"))
        doc["correspondence"]["objective"]["relation"] = "UNRESOLVED"
        doc["correspondence"]["mechanism"]["relation"] = "UNRESOLVED"
        self.assertIn("NN3", seq.check_artifact(doc).rules())

    def test_single_unresolved_blocks_both_directions(self) -> None:
        """对称不确定性闸门：load-bearing UNRESOLVED 既禁止 delta，也禁止 neighbor 塌缩。"""
        for name in FIXTURE_VERDICTS:
            doc = _load(FIXTURES / f"{name}.json")
            facet = doc["load_bearing_facets"][0]
            doc["correspondence"][facet]["relation"] = "UNRESOLVED"
            doc["correspondence"][facet]["provenance"] = "UNKNOWN"
            rules = seq.check_artifact(doc, source=name).rules()
            self.assertIn("NN3", rules,
                          f"{name}：load-bearing facet 变 UNRESOLVED 后仍给出了非 uncertain 的 verdict")
            # 对称性：改成 uncertain 后 NN3 必须消失
            doc["near_neighbor_verdict"] = "uncertain"
            doc["verdict"] = "uncertain"
            doc["claimed_novelty_level"] = "component-delta"
            doc["counterfactual_collapse"] = {"replacement": "r", "predicted_consequence": "p",
                                              "collapse_result": "partially-collapses",
                                              "verification_status": "predicted"}
            doc["local_neighborhood_test"]["neighbor_confirmed"] = False
            doc["removal_test"]["conclusion"] = "unresolved"
            self.assertEqual(seq.check_artifact(doc, source=f"{name}/uncertain").rules(), [],
                             f"{name}：证据不足的完整 uncertain 审计必须通过")

    def test_uncertain_cannot_confirm_a_neighbor(self) -> None:
        doc = nn_artifact("uncertain", "uncertain", "component-delta",
                          collapse="partially-collapses")
        doc["local_neighborhood_test"]["neighbor_confirmed"] = True
        self.assertIn("NN6", seq.check_artifact(doc).rules())

    def test_uncertain_cannot_conclude_a_local_delta(self) -> None:
        doc = nn_artifact("uncertain", "uncertain", "component-delta",
                          collapse="partially-collapses")
        doc["removal_test"]["conclusion"] = "component-local-delta"
        self.assertIn("NN7", seq.check_artifact(doc).rules())

    def test_predicted_counterfactual_is_not_strong_evidence(self) -> None:
        doc = nn_artifact("structural-delta", "formulation-delta", "formulation-delta", **_DELTA)
        doc["counterfactual_collapse"]["verification_status"] = "predicted"
        self.assertIn("NN14", seq.check_artifact(doc).rules())
        doc["counterfactual_collapse"]["verification_status"] = "executed"
        self.assertNotIn("NN14", seq.check_artifact(doc).rules())

    def test_counterfactual_status_matrix_with_code_present(self) -> None:
        for status in seq.COUNTERFACTUAL_VERIFICATION:
            with self.subTest(status=status):
                doc = nn_artifact("structural-delta", "formulation-delta",
                                  "formulation-delta", trust=("code",), **_DELTA)
                doc["counterfactual_collapse"]["verification_status"] = status
                rules = seq.check_artifact(doc).rules()
                self.assertEqual(rules, [] if status in ("derived", "executed") else ["NN14"])

    def test_unresolved_counterfactual_can_remain_a_hypothesis(self) -> None:
        for status in ("predicted", "unresolved"):
            with self.subTest(status=status):
                doc = nn_artifact("uncertain", "uncertain", "none",
                                  confirmed=False, removal="unresolved",
                                  collapse="partially-collapses")
                doc["counterfactual_collapse"]["verification_status"] = status
                doc["correspondence"]["mechanism"]["relation"] = "UNRESOLVED"
                doc["correspondence"]["mechanism"]["provenance"] = "UNKNOWN"
                self.assertEqual(seq.check_artifact(doc).rules(), [])

    def test_population_telemetry_producer(self) -> None:
        self.skipTest("P1: population telemetry producer is not implemented, including UncertaintyAsymmetry")

    def test_nn11_and_nn12_are_the_semantic_distance_guard(self) -> None:
        """NN-11（语义远 / 结构同）与 NN-12（语义近 / 结构异）必须都稳定。"""
        far_same = nn_artifact("duplicate-equivalent", "equivalent", "none")
        near_diff = nn_artifact("structural-delta", "formulation-delta", "formulation-delta",
                                **_DELTA)
        self.assertEqual(seq.check_artifact(far_same).rules(), [])
        self.assertEqual(seq.check_artifact(near_diff).rules(), [])

    def test_overclaiming_a_neighbor_is_rejected(self) -> None:
        for tag, name, near, verdict, claimed, extra, _allowed in NN_CASES:
            if near == "structural-delta-strong":
                continue
            doc = nn_artifact(near, verdict, claimed, **extra)
            doc["claimed_novelty_level"] = "paradigm-candidate"
            self.assertIn("NN12", seq.check_artifact(doc, source=f"{tag} {name}").rules(),
                          f"{tag} {name}：把 neighbor 过度声称成 paradigm-candidate 没被拦下")


class TestHallucinationRegression(unittest.TestCase):
    """policy §32 的四条幻觉回归（只测可机械判定的部分）。"""

    def test_extraction_hallucination_cannot_be_explicit_without_a_span(self) -> None:
        doc = nn_artifact("duplicate-equivalent", "equivalent", "none")
        doc["correspondence"]["assumptions"]["evidence_span"] = ""
        self.assertIn("NN2", seq.check_artifact(doc).rules())

    def test_alignment_hallucination_cannot_force_binary(self) -> None:
        doc = nn_artifact("duplicate-equivalent", "equivalent", "none")
        doc["correspondence"]["mechanism"]["relation"] = "MATCH_ISH"
        self.assertIn("NN2", seq.check_artifact(doc).rules())

    def test_unresolved_is_preserved_not_rejected(self) -> None:
        doc = nn_artifact("component-neighbor", "component-delta", "component-delta")
        doc["correspondence"]["setting"]["relation"] = "UNRESOLVED"
        doc["correspondence"]["setting"]["provenance"] = "UNKNOWN"
        self.assertEqual(seq.check_artifact(doc).rules(), [])

    def test_missing_prior_cannot_claim_paradigm(self) -> None:
        doc = nn_artifact("uncertain", "uncertain", "component-delta",
                          collapse="partially-collapses")
        doc["retrieval_status"] = "retrieval-insufficient"
        doc["closest_priors"] = []
        doc["novelty_boundary"] = "检索未完成，无法判断"
        self.assertIn("EQ10", seq.check_artifact(doc).rules())
        doc["novelty_boundary"] = ("against the retrieved literature, "
                                   "no structural equivalent was identified")
        self.assertNotIn("EQ10", seq.check_artifact(doc).rules())
        doc["near_neighbor_verdict"] = "paradigm-candidate"
        self.assertIn("NN12", seq.check_artifact(doc).rules())

    def test_counterfactual_hallucination_requires_executable_trust(self) -> None:
        doc = nn_artifact("structural-delta", "formulation-delta", "formulation-delta", **_DELTA)
        doc["trust_basis"] = ["source-span", "literature"]
        self.assertIn("NN5", seq.check_artifact(doc).rules())
        doc["trust_basis"] = ["source-span", "equation"]
        self.assertNotIn("NN5", seq.check_artifact(doc).rules())

    def test_multiple_llm_passes_are_not_evidence(self) -> None:
        """pass 名字当 trust_basis 必须被拒；它们只是任务分解（policy §21.3）。"""
        doc = nn_artifact("structural-delta", "formulation-delta", "formulation-delta", **_DELTA)
        doc["trust_basis"] = ["extractor", "aligner", "adversarial-matcher", "delta-critic"]
        self.assertIn("NN5", seq.check_artifact(doc).rules())


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
        listed = dict(re.findall(r"^((?:EQ|NN)\d+)\s+硬\s{2}(.+)$", out, re.M))
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
        self.assertIn("populations/near-neighbor-telemetry.json", layout)
        self.assertIn("populations/near-neighbor-telemetry.json", self._policy())

    def test_divergence_protection_and_no_scalar_ban_are_frozen(self) -> None:
        text = self._policy()
        for token in ("Generate broadly", "generate first", "coverage before ranking",
                      "不得直接决定 novelty claim", "idea-kill gate",
                      "constrain claim strength", "不得用它们直接奖励模型"):
            self.assertIn(token, text, f"policy 缺少发散性保护 / 禁 scalar 的冻结表述：{token}")

    def test_r3_never_runs_the_formal_gate(self) -> None:
        """policy §25 与 phase-r3-r6 §R4.5 必须同时说「R3 不跑正式 gate」。"""
        text = self._policy()
        section = _section("## 25. 阶段分工", "## 26.")
        self.assertIn("不运行", section)
        self.assertIn("R3", section)
        discovery = (ROOT / "references" / "phase-r3-r6-discovery.md").read_text(encoding="utf-8")
        self.assertIn("**R3 只生成**", discovery)
        self.assertIn("不运行", discovery)

    def test_theory_and_remote_analogy_operators_are_wired(self) -> None:
        """P5 / P4 的 operator 触发条件必须写进 policy，并与代码常量同名。"""
        policy = self._policy()
        for token in (seq.THEORY_OPERATOR, seq.REMOTE_ANALOGY_OPERATOR,
                      "Theory-Stripping Test", "Structure-Preservation Test"):
            self.assertIn(token, policy, f"policy 缺少 P5 / P4 触发条件：{token}")


if __name__ == "__main__":
    unittest.main()
