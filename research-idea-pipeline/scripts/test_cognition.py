#!/usr/bin/env python3
"""test_cognition.py — Cognitive Insight Engine Phase 1 (persistent cognitive memory).

What this file is guarding
--------------------------
Phase 1 turns "record research facts" into "accumulate scientific understanding".
The failure modes it must prevent are specific, so every one of them gets a test:

* a projection that silently becomes a **second authoritative state**;
* a revision that **certifies its own support level**;
* a cognitive entry that keeps being recalled after its **evidence died**;
* a context brief that **promotes speculation to fact**;
* an index that is **not reproducible** from canonical state + revision log;
* a build that **writes to `research-state.json`**.

The last one is checked byte-for-byte, not by inspection.
"""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import cognition as cg

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "cognition.py"
TEMPLATE = ROOT / "templates" / "research-state.template.json"
FIXTURES = ROOT / "examples" / "cognition"


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def validity(reason: str = "初始", version: int = 0, status: str = "valid"):
    return {"status": status, "reason": reason, "since_state_version": version}


def state(version: int = 4) -> dict:
    """A minimal state that satisfies S1—S7 / V1—V24 at version 4."""
    return {
        "state_version": version,
        "contract": {
            "goal": "判断机制 M 是否解释目标现象",
            "primary_anchor": "phenomenon",
            "constraints": ["单卡"],
            "resources": ["公开数据集"],
            "provisional_anchor_rationale": "先形式化再复核",
            "out_of_scope": [],
        },
        "claims": [{
            "id": "C1", "statement": "机制 M 解释目标现象", "parent": None, "subclaims": [],
            "status": "partially-supported", "supporting_evidence": ["E1"], "refuting_evidence": [],
            "nearest_alternative": "替代机制 N", "falsifier": "干预 I 后现象消失", "scope": "数据集 A",
            "known_flaws": ["F1"], "depends_on": [], "validity": validity("已按预注册写入"),
        }],
        "evidence": [{
            "id": "E1", "kind": "experiment", "supports": ["C1"], "contradicts": [],
            "strength": "strong", "scope": "数据集 A", "epistemic_status": "Observed",
            "source_ref": "X1（seed=0）", "verification_tier": "T2", "depends_on": ["X1"],
            "validity": validity("X1 已 done"),
        }],
        "assumptions": [{
            "id": "AS1", "statement": "测量无偏", "status": "explicit", "challenged_by": [],
            "if_false": "现象不可归因", "depends_on": [], "validity": validity("仍被接受"),
        }],
        "hypotheses": [{
            "id": "H1", "statement": "机制 M 是主因",
            "structural_signature": {"assumption_distance": 1, "formulation_distance": 1,
                                     "representation_distance": 0, "theory_lens_distance": 1,
                                     "mechanism_distance": 2},
            "novelty_source": "迁移", "theory_lens": "逆问题", "nearest_prior": "LIT1",
            "falsifier": "干预 I 无效", "expected_information_gain": 0.4, "status": "elite",
            "niche": "mechanism-shift", "island": "P2", "generation": 0,
            "operator": "assumption_breaker", "parents": [], "depends_on": ["AS1"],
            "validity": validity("AS1 未推翻"), "scientific_scope": None,
        }],
        "experiments": [{
            "id": "X1", "parent": None, "stage": "X3", "claim_targeted": ["C1"],
            "alternative_targeted": ["ALT-1"], "code_commit": "abc123", "data_split": "A/train",
            "seed": 0, "metric": "效应量", "result": "效应量 0.8", "interpretation": "初步",
            "unexpected": [], "known_flaws": ["F1"], "next_branches": [], "status": "done",
            "preregistration": {"frozen_at_state_version": 3, "outcomes": [
                {"id": "O1", "observation": "效应量 ≥ 0.5",
                 "update": [{"target": "C1", "op": "strengthen"}]}]},
            "result_at_state_version": 4, "depends_on": [], "validity": validity("按预注册写入"),
            "outcome_analysis": None, "execution_protocol": None,
        }, {
            "id": "X2", "parent": "X1", "stage": "X3", "claim_targeted": ["C1"],
            "alternative_targeted": ["ALT-1"], "code_commit": "TBD",
            "data_split": "A/fixed-centre", "seed": 0, "metric": "落差变化",
            "result": "", "interpretation": "尚未运行", "unexpected": [], "known_flaws": [],
            "next_branches": [], "status": "planned", "preregistration": None,
            "result_at_state_version": None, "depends_on": ["X1"],
            "validity": validity("尚未运行", 4, status="pending"),
            "outcome_analysis": None, "execution_protocol": None,
        }],
        "literature": [{
            "id": "LIT1", "ref": "[Author, Venue/Year]", "relation": "shares-structure",
            "depends_on": [], "validity": validity("未受波及"),
        }],
        "failures": [{
            "id": "F1", "kind": "falsified",
            "what": "协议 P 在该 regime 下已被判别实验否决", "why": "两次独立复现均为零效应",
            "referenced_by": ["C1", "X1"], "depends_on": [], "validity": validity("未受波及"),
            "source_review": None,
            "negative_knowledge": [{
                "target_id": "C1", "finding": "协议 P 无效",
                "ruled_out": "协议 P 在该 regime 下有效", "not_ruled_out": "其他 regime",
                "likely_failure_mode": "hypothesis_failure", "retry_allowed": False,
                "retry_conditions": "只有在 regime 改变且有新判别证据时",
                "revisit_conditions": "出现相反的 T2 以上独立证据", "confidence": "high",
            }],
            "stop_rules": [{
                "id": "STOP1", "target_ids": ["C1"], "scope": "数据集 A / 协议 P",
                "kind": "protocol", "rule": "禁止重复协议 P",
                "protocol_signature": "sig-p", "revisit_conditions": "regime 改变",
            }],
        }],
        "uncertainties": [{
            "id": "U1", "question": "机制 M 是否在数据集 B 上成立？", "importance": "high",
            "uncertainty": "high", "cheapest_discriminating_test": "TBD", "status": "open",
            "depends_on": [], "validity": validity("未受波及"),
        }],
        "assurance": [], "repairs": [],
    }


def revision(ident: str, seq: int, kind: str, subject: str, refs: dict,
             after: dict | None = None, actor: str = "R3", version: int = 4) -> dict:
    record = {
        "_schema": cg.SCHEMA_REVISION,
        "id": ident,
        "seq": seq,
        "kind": kind,
        "subject": subject,
        "actor": actor,
        "at_state_version": version,
        "summary": f"{kind} {subject}",
        "trigger": {"kind": "experiment_result", "ref": "X1"},
        "refs": refs,
    }
    if after is not None:
        record["after"] = after
    return record


def base_revisions() -> list:
    return [
        revision("REV1", 1, "mechanism_create", "M1",
                 {"hypotheses": ["H1"], "assumptions": ["AS1"]},
                 {"statement": "解耦带来跨中心增益", "core_variables": ["耦合强度"],
                  "necessary_conditions": ["测量无偏"], "boundaries": ["数据集 A"],
                  "pending_predictions": ["PR1"]}),
        revision("REV2", 2, "mechanism_create", "M2",
                 {"claims": ["C1"], "evidence": ["E1"], "experiments": ["X1"]},
                 {"statement": "耦合强度决定落差", "pending_predictions": ["PR2"]}),
        revision("REV3", 3, "competition_open", "CP1",
                 {"claims": ["C1"], "evidence": ["E1"]},
                 {"mechanisms": ["M1", "M2"],
                  "shared_explanation": "两者都能解释数据集 A 的落差",
                  "conflicting_predictions": ["PR1 预测数据集 B 有增益", "PR2 预测无增益"],
                  "discriminating_intervention": "X2",
                  "discrimination_rule": {"statistic": "difference_of_means",
                                          "min_separation": 0.2}}, actor="R6"),
        revision("REV4", 4, "anomaly_record", "AN1",
                 {"experiments": ["X1"], "evidence": ["E1"]},
                 {"observation": "数据集 B 上落差反转", "importance": "high",
                  "reproduced": False, "open_question": "反转是否来自实现错误？"}),
    ]


def write_fixture(root: pathlib.Path, doc: dict, revisions: list) -> tuple:
    state_path = root / cg.STATE_NAME
    state_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    cognition_dir = root / cg.COGNITION_DIRNAME
    cognition_dir.mkdir(parents=True, exist_ok=True)
    (cognition_dir / cg.REVISIONS_NAME).write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in revisions), encoding="utf-8")
    return state_path, cognition_dir


def quiet(callable_, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return callable_(*args, **kwargs)


# ---------------------------------------------------------------------------
# Backward compatibility: an existing project must keep working
# ---------------------------------------------------------------------------

class TestBackwardCompatibility(unittest.TestCase):
    ROOT = ROOT

    def test_shipped_template_state_builds_with_zero_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state_path = root / cg.STATE_NAME
            shutil.copy(TEMPLATE, state_path)
            cognition_dir = root / cg.COGNITION_DIRNAME
            self.assertEqual(quiet(cg.op_build, state_path, cognition_dir), cg.EXIT_OK)
            self.assertEqual(quiet(cg.op_check, state_path, cognition_dir), cg.EXIT_OK)
            index = json.loads((cognition_dir / cg.INDEX_NAME).read_text(encoding="utf-8"))
            self.assertEqual(index["diagnostics"], [])
            # A project with no revision log still projects its canonical claims and
            # candidates. Everything reconstructed this way must be marked retrospective.
            self.assertTrue(index["mechanisms"], "a legacy state projects no mechanism at all")
            for mechanism in index["mechanisms"]:
                self.assertEqual(mechanism["provenance"]["origin"], cg.LEGACY_ORIGIN)
                self.assertTrue(mechanism["provenance"]["retrospective"])
                self.assertEqual(mechanism["revision_ids"], [])
            self.assertEqual(index["provenance_mode"], "legacy_derivation")

    def test_state_without_a_cognition_directory_is_readable(self):
        doc = cg.load_state(TEMPLATE)
        index, diagnostics = cg.build_index(doc, [], "A")
        self.assertEqual(diagnostics, [])
        self.assertEqual(index["counts"]["legacy_mechanisms"],
                         index["counts"]["mechanisms"])
        self.assertEqual(index["counts"]["mechanisms"],
                         len([claim for claim in doc["claims"]])
                         + len([hypothesis for hypothesis in doc["hypotheses"]])
                         + len([claim for claim in doc["claims"]
                                if isinstance(claim.get("contract"), dict)
                                and claim["contract"].get("minimal_discriminating_experiment")
                                in {x["id"] for x in doc["experiments"]}]))

    def test_old_state_shape_is_not_modified_by_validation(self):
        doc = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        before = cg.canonical_json(doc)
        cg.build_index(doc, base_revisions(), "A")
        cg.validate_revisions(doc, base_revisions())
        self.assertEqual(cg.canonical_json(doc), before)

    def test_index_schema_is_stable(self):
        index, _ = cg.build_index(state(), base_revisions(), "A")
        self.assertEqual(index["_schema"], "research-idea-pipeline/cognitive-index@1")


# ---------------------------------------------------------------------------
# Determinism and rebuildability
# ---------------------------------------------------------------------------

class TestRebuildability(unittest.TestCase):

    def test_build_is_reproducible(self):
        doc = state()
        revisions = base_revisions()
        first, _ = cg.full_index(doc, revisions, "A")
        for _ in range(3):
            again, _ = cg.full_index(doc, revisions, "A")
            self.assertEqual(cg.canonical_json(again), cg.canonical_json(first))

    def test_build_twice_writes_identical_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state_path, cognition_dir = write_fixture(root, state(), base_revisions())
            quiet(cg.op_build, state_path, cognition_dir)
            first_index = (cognition_dir / cg.INDEX_NAME).read_bytes()
            first_brief = (cognition_dir / cg.BRIEF_NAME).read_bytes()
            quiet(cg.op_build, state_path, cognition_dir)
            self.assertEqual((cognition_dir / cg.INDEX_NAME).read_bytes(), first_index)
            self.assertEqual((cognition_dir / cg.BRIEF_NAME).read_bytes(), first_brief)

    def test_index_is_rebuildable_from_canonical_state_alone(self):
        """Deleting the derived layer must lose nothing authoritative."""
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state_path, cognition_dir = write_fixture(root, state(), base_revisions())
            quiet(cg.op_build, state_path, cognition_dir)
            before = (cognition_dir / cg.INDEX_NAME).read_bytes()
            shutil.rmtree(cognition_dir)
            cognition_dir.mkdir()
            (cognition_dir / cg.REVISIONS_NAME).write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in base_revisions()),
                encoding="utf-8")
            quiet(cg.op_build, state_path, cognition_dir)
            self.assertEqual((cognition_dir / cg.INDEX_NAME).read_bytes(), before)

    def test_index_drift_is_detected(self):
        doc = state()
        revisions = base_revisions()
        index, _ = cg.full_index(doc, revisions, "A")
        index["mechanisms"][0]["support_level"] = "experiment_supported"
        rules = {d.rule for d in cg.validate_index(doc, revisions, index)}
        self.assertIn("CM3", rules)

    def test_stale_index_is_detected_after_a_state_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state_path, cognition_dir = write_fixture(root, state(), base_revisions())
            quiet(cg.op_build, state_path, cognition_dir)
            bumped = state(version=5)
            state_path.write_text(json.dumps(bumped, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(quiet(cg.op_check, state_path, cognition_dir), cg.EXIT_HARD)


# ---------------------------------------------------------------------------
# Derived support: the anti self-certification core
# ---------------------------------------------------------------------------

class TestDerivedSupport(unittest.TestCase):

    def support_of(self, refs: dict, doc: dict | None = None) -> str:
        view = cg.CanonicalView(doc or state())
        level, _, _ = cg.derive_support(view, cg.normalize_refs(refs))
        return level

    def test_no_reference_is_speculation(self):
        self.assertEqual(self.support_of({}), "speculative")

    def test_hypothesis_reference_stays_a_hypothesis(self):
        self.assertEqual(self.support_of({"hypotheses": ["H1"]}), "hypothesis")

    def test_strong_experiment_evidence_reaches_experiment_supported(self):
        self.assertEqual(
            self.support_of({"claims": ["C1"], "evidence": ["E1"], "experiments": ["X1"]}),
            "experiment_supported")

    def test_literature_evidence_only_reaches_literature_supported(self):
        doc = state()
        doc["evidence"].append({
            "id": "E2", "kind": "literature", "supports": [], "contradicts": [],
            "strength": "partial", "scope": "综述覆盖范围", "epistemic_status": "Supported",
            "source_ref": "[Author, Venue/Year]", "verification_tier": "T1", "depends_on": [],
            "validity": validity("文献未撤回"),
        })
        self.assertEqual(self.support_of({"evidence": ["E2"]}, doc), "literature_supported")

    def test_weak_experiment_evidence_does_not_reach_experiment_supported(self):
        doc = state()
        doc["evidence"][0]["strength"] = "partial"
        self.assertNotEqual(self.support_of({"claims": ["C1"], "evidence": ["E1"]}, doc),
                            "experiment_supported")

    def test_t0_experiment_evidence_cannot_support_a_mechanism(self):
        doc = state()
        doc["evidence"][0]["verification_tier"] = "T0"
        self.assertNotEqual(self.support_of({"claims": ["C1"], "evidence": ["E1"]}, doc),
                            "experiment_supported")

    def test_contradicted_claim_refutes_the_mechanism(self):
        doc = state()
        doc["claims"][0]["status"] = "contradicted"
        doc["claims"][0]["supporting_evidence"] = []
        doc["claims"][0]["refuting_evidence"] = ["E1"]
        doc["evidence"][0]["supports"] = []
        doc["evidence"][0]["contradicts"] = ["C1"]
        self.assertEqual(self.support_of({"claims": ["C1"], "evidence": ["E1"]}, doc), "refuted")

    def test_falsified_failure_memory_refutes_the_mechanism(self):
        doc = state()
        doc["failures"][0]["kind"] = "falsified"
        self.assertEqual(self.support_of({"hypotheses": ["H1"], "failures": ["F1"]}, doc), "refuted")

    def test_refutation_outranks_positive_evidence(self):
        doc = state()
        doc["claims"][0]["status"] = "contradicted"
        doc["claims"][0]["refuting_evidence"] = ["E1"]
        doc["evidence"][0]["kind"] = "experiment"
        doc["evidence"][0]["strength"] = "strong"
        doc["evidence"][0]["verification_tier"] = "T3"
        self.assertEqual(self.support_of({"claims": ["C1"], "evidence": ["E1"]}, doc), "refuted")

    def test_invalidated_evidence_removes_support(self):
        doc = state()
        doc["evidence"][0]["validity"] = validity("源实验作废", version=1, status="invalid")
        self.assertNotEqual(self.support_of({"claims": ["C1"], "evidence": ["E1"]}, doc),
                            "experiment_supported")

    def test_support_levels_are_exactly_the_frozen_ladder(self):
        self.assertEqual(cg.SUPPORT_LEVELS,
                         ("speculative", "hypothesis", "literature_supported",
                          "experiment_supported", "refuted"))


# ---------------------------------------------------------------------------
# Revision authority: memory may not certify itself
# ---------------------------------------------------------------------------

class TestRevisionAuthority(unittest.TestCase):

    def rules(self, revisions: list, doc: dict | None = None) -> set:
        return {d.rule for d in cg.validate_revisions(doc or state(), revisions)}

    def build_rules(self, revisions: list, doc: dict | None = None) -> set:
        """Rules raised while folding the log into mechanisms/competitions."""
        _, diagnostics = cg.build_index(doc or state(), revisions, "A")
        return {d.rule for d in diagnostics}

    def test_clean_log_validates(self):
        self.assertEqual(self.rules(base_revisions()), set())

    def test_declaring_epistemic_status_is_a_hard_violation(self):
        bad = base_revisions() + [revision(
            "REV5", 5, "mechanism_revise", "M1", {"hypotheses": ["H1"]},
            {"epistemic_status": "experiment_supported"})]
        self.assertIn("CM2", self.rules(bad))

    def test_declaring_a_claim_status_is_a_hard_violation(self):
        bad = base_revisions() + [revision(
            "REV5", 5, "mechanism_revise", "M1", {"claims": ["C1"]},
            {"claim_status": "supported"})]
        self.assertIn("CM2", self.rules(bad))

    def test_touching_the_research_anchor_is_a_hard_violation(self):
        for key in ("contract", "anchor", "primary_anchor", "research_goal"):
            bad = base_revisions() + [revision(
                "REV5", 5, "mechanism_revise", "M1", {"hypotheses": ["H1"]}, {key: "performance"})]
            self.assertIn("CM2", self.rules(bad), msg=key)

    def test_self_declared_support_is_recorded_but_never_adopted(self):
        bad = base_revisions() + [revision(
            "REV5", 5, "mechanism_revise", "M1", {"hypotheses": ["H1"]},
            {"declared_support": "experiment_supported"})]
        index, _ = cg.build_index(state(), bad, "A")
        m1 = next(m for m in index["mechanisms"] if m["id"] == "M1")
        self.assertEqual(m1["support_level"], "hypothesis")
        self.assertTrue(any(d["rule"] == "CM7" for d in index["diagnostics"]))
        self.assertIn("CM7", self.rules(bad))

    def test_dangling_reference_is_detected(self):
        bad = base_revisions() + [revision(
            "REV5", 5, "mechanism_create", "M3", {"claims": ["C404"]},
            {"statement": "无来源的机制"})]
        details = [d.detail for d in cg.validate_revisions(state(), bad) if d.rule == "CM3"]
        self.assertTrue(any("C404" in detail for detail in details))

    def test_revision_cannot_point_at_a_future_state_version(self):
        bad = base_revisions() + [revision(
            "REV5", 5, "mechanism_revise", "M1", {"hypotheses": ["H1"]},
            {"note": "future"}, version=99)]
        self.assertIn("CM3", self.rules(bad))

    def test_revision_without_canonical_reference_is_rejected(self):
        bad = base_revisions() + [revision("REV5", 5, "mechanism_create", "M3", {},
                                           {"statement": "凭空机制"})]
        self.assertIn("CM3", self.rules(bad))

    def test_revision_without_trigger_is_rejected(self):
        record = revision("REV5", 5, "mechanism_revise", "M1", {"hypotheses": ["H1"]},
                          {"note": "no trigger"})
        record.pop("trigger")
        self.assertIn("CM3", self.rules(base_revisions() + [record]))

    def test_sequence_must_strictly_increase(self):
        bad = base_revisions() + [revision("REV5", 4, "mechanism_revise", "M1",
                                           {"hypotheses": ["H1"]}, {"note": "backwards"})]
        self.assertIn("CM1", self.rules(bad))

    def test_duplicate_ids_are_rejected(self):
        bad = base_revisions() + [revision("REV1", 5, "mechanism_revise", "M1",
                                           {"hypotheses": ["H1"]}, {"note": "duplicate"})]
        self.assertIn("CM1", self.rules(bad))

    def test_unknown_kind_is_rejected(self):
        bad = base_revisions() + [revision("REV5", 5, "mechanism_invent", "M1",
                                           {"hypotheses": ["H1"]}, {"note": "x"})]
        self.assertIn("CM1", self.rules(bad))

    def test_read_only_view_stages_cannot_write_cognition(self):
        for actor in ("R12", "R13"):
            bad = base_revisions() + [revision("REV5", 5, "mechanism_revise", "M1",
                                               {"hypotheses": ["H1"]}, {"note": "x"}, actor=actor)]
            self.assertIn("CM1", self.rules(bad), msg=actor)

    def test_competition_needs_two_mechanisms_and_a_discriminating_intervention(self):
        bad = base_revisions() + [revision(
            "REV5", 5, "competition_open", "CP2", {"claims": ["C1"]},
            {"mechanisms": ["M1"], "shared_explanation": "只有一个机制"}, actor="R6")]
        self.assertIn("CM6", self.build_rules(bad))

    def test_competition_without_prediction_gap_raises_a_diagnostic(self):
        bad = base_revisions() + [revision(
            "REV5", 5, "competition_open", "CP2", {"claims": ["C1"]},
            {"mechanisms": ["M1", "M2"], "shared_explanation": "都能解释",
             "conflicting_predictions": [], "discriminating_intervention": "TBD"}, actor="R6")]
        self.assertIn("CM8", self.build_rules(bad))

    def test_duplicate_anchor_sets_are_flagged_as_equivalent_explanations(self):
        duplicated = base_revisions() + [revision(
            "REV5", 5, "mechanism_create", "M3", {"claims": ["C1"], "evidence": ["E1"],
                                                  "experiments": ["X1"]},
            {"statement": "与 M2 实质等价的重述"})]
        index, _ = cg.build_index(state(), duplicated, "A")
        self.assertTrue(any(d["rule"] == "CM9" for d in index["diagnostics"]))

    def test_broken_jsonl_line_is_reported_not_fatal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state_path, cognition_dir = write_fixture(root, state(), base_revisions())
            with (cognition_dir / cg.REVISIONS_NAME).open("a", encoding="utf-8") as handle:
                handle.write('{"_schema": "x", "id": "REV9", "seq": 9,\n')
            doc, revisions, diagnostics = cg._load_inputs(state_path, cognition_dir)[:3]
            self.assertEqual(len(revisions), 4)
            self.assertTrue(any(d.rule == "CM1" for d in diagnostics))


# ---------------------------------------------------------------------------
# Memory lifecycle: invalidation, staleness, recall
# ---------------------------------------------------------------------------

class TestMemoryLifecycle(unittest.TestCase):

    def test_invalidated_source_marks_derived_memory_stale(self):
        doc = state()
        doc["evidence"][0]["validity"] = validity("源实验作废", version=1, status="invalid")
        index, diagnostics = cg.build_index(doc, base_revisions(), "A")
        m2 = next(m for m in index["mechanisms"] if m["id"] == "M2")
        self.assertTrue(m2["stale"])
        self.assertTrue(m2["stale_reasons"])
        self.assertTrue(any(d.rule == "CM3" for d in diagnostics))

    def test_stale_memory_leaves_hot_memory(self):
        doc = state()
        doc["evidence"][0]["validity"] = validity("源实验作废", version=1, status="invalid")
        index, _ = cg.build_index(doc, base_revisions(), "A")
        selection = cg.recall(index, doc)
        hot_ids = {m["id"] for m in selection["hot"]["mechanisms"]}
        self.assertNotIn("M2", hot_ids)
        cold_ids = {m["id"] for m in selection["cold"]["mechanisms"]}
        self.assertIn("M2", cold_ids)

    def test_invalidation_reaches_anomalies_and_competitions(self):
        """Phase 1 end-to-end: one dead source must expire every derived view of it."""
        doc = state()
        doc["evidence"][0]["validity"] = validity("源实验作废", version=1, status="invalid")
        index, _ = cg.build_index(doc, base_revisions(), "A")
        mechanism = next(m for m in index["mechanisms"] if m["id"] == "M2")
        anomaly = next(a for a in index["anomalies"] if a["id"] == "AN1")
        competition = next(c for c in index["competitions"] if c["id"] == "CP1")
        for entry in (mechanism, anomaly, competition):
            self.assertTrue(entry["stale"], msg=entry["id"])
            self.assertTrue(entry["stale_reasons"], msg=entry["id"])
        selection = cg.recall(index, doc)
        hot_ids = {item["id"] for item in selection["hot"]["mechanisms"]}
        hot_ids |= {item["id"] for item in selection["hot"]["anomalies"]}
        hot_ids |= {item["id"] for item in selection["hot"]["competitions"]}
        self.assertNotIn("M2", hot_ids)
        self.assertNotIn("AN1", hot_ids)
        self.assertNotIn("CP1", hot_ids)
        self.assertTrue(any(item["kind"] == "invalidated_object"
                            for item in index["boundaries"]))

    def test_missing_reference_marks_the_entry_unresolved(self):
        doc = state()
        doc["claims"] = []
        index, _ = cg.build_index(doc, base_revisions(), "A")
        m2 = next(m for m in index["mechanisms"] if m["id"] == "M2")
        self.assertTrue(m2["stale"])
        self.assertTrue(m2["missing_refs"])

    def test_failure_memory_with_stop_rules_is_recovered(self):
        constraints = cg.failure_constraints(state())
        self.assertEqual(len(constraints), 1)
        self.assertEqual(constraints[0]["retry"], "blocked")
        self.assertEqual(constraints[0]["stop_rules"][0]["id"], "STOP1")
        self.assertIn("regime", constraints[0]["stop_rules"][0]["revisit_conditions"])

    def test_accepted_limitation_is_recovered_as_an_obligation(self):
        doc = state()
        doc["repairs"] = [{
            "flaw": "C1 只在数据集 A 上成立", "disposition": "NARROW_SCOPE",
            "state_delta": "C1.scope→'数据集 A'", "closure": "ACCEPTED_LIMITATION",
            "targets": ["C1"], "source_review": None,
        }]
        obligations = cg.open_obligations(doc)
        self.assertEqual(len(obligations), 1)
        self.assertEqual(obligations[0]["disposition"], "NARROW_SCOPE")

    def test_recall_is_bounded_by_the_budget(self):
        index, _ = cg.build_index(state(), base_revisions(), "A")
        brief = cg.render_brief(index, state(), budget=600)
        self.assertLessEqual(len(brief), 900)
        self.assertIn("context budget", brief)

    def test_hot_before_cold_ordering_is_deterministic(self):
        index, _ = cg.build_index(state(), base_revisions(), "A")
        first = cg.canonical_json(cg.recall(index, state()))
        for _ in range(3):
            self.assertEqual(cg.canonical_json(cg.recall(index, state())), first)


# ---------------------------------------------------------------------------
# Context brief: speculation must stay labelled
# ---------------------------------------------------------------------------

class TestContextBrief(unittest.TestCase):

    def brief(self, doc: dict | None = None) -> str:
        doc = doc or state()
        index, _ = cg.full_index(doc, base_revisions(), "A")
        return cg.render_brief(index, doc)

    def test_brief_declares_it_is_not_evidence(self):
        text = self.brief()
        self.assertIn("It is not evidence and not a state.", text)

    def test_every_mechanism_line_carries_a_support_level(self):
        text = self.brief()
        mechanism_lines = [line for line in text.splitlines()
                           if line.startswith("- `M")]
        self.assertTrue(mechanism_lines, "brief lists no mechanism at all")
        for line in mechanism_lines:
            self.assertRegex(line, r"^\- `M\d+` \[[a-z_]+/[a-z_]+\]",
                             msg=f"support level or lifecycle status missing: {line}")

    def test_proposed_mechanism_is_labelled_as_a_hypothesis(self):
        text = self.brief()
        line = next(line for line in text.splitlines() if line.startswith("- `M1`"))
        self.assertIn("[hypothesis/", line)

    def test_brief_recovers_pending_predictions_and_boundaries(self):
        index, _ = cg.full_index(state(), base_revisions(), "A")
        m1 = next(m for m in index["mechanisms"] if m["id"] == "M1")
        self.assertEqual(m1["structure"]["pending_predictions"], ["PR1"])
        self.assertEqual(m1["structure"]["boundaries"], ["数据集 A"])
        self.assertEqual(m1["structure"]["necessary_conditions"], ["测量无偏"])

    def test_brief_recovers_refuted_memory_and_its_boundary(self):
        doc = state()
        doc["claims"][0]["status"] = "contradicted"
        doc["claims"][0]["refuting_evidence"] = ["E1"]
        doc["evidence"][0]["contradicts"] = ["C1"]
        doc["evidence"][0]["supports"] = []
        text = self.brief(doc)
        self.assertIn("refuted", text)

    def test_brief_recovers_open_competition_with_its_intervention(self):
        text = self.brief()
        self.assertIn("competition `CP1`", text)
        self.assertIn("X2", text)

    def test_brief_recovers_failure_constraints_and_stop_rules(self):
        text = self.brief()
        self.assertIn("what must not be repeated", text)
        self.assertIn("stop rule `STOP1`", text)
        self.assertIn("retry=blocked", text)

    def test_brief_prefers_the_discriminating_intervention_over_more_explanations(self):
        doc = state()
        index, _ = cg.full_index(doc, base_revisions(), "A")
        hint = cg.next_action_hint(cg.CanonicalView(doc), index)
        # CP1 already carries a distinguishing intervention, and there is an open
        # high-importance uncertainty, so the hint must point at that uncertainty.
        self.assertIn("数据集 B", hint)

    def test_a_competition_without_distinguishing_power_dominates_the_hint(self):
        revisions = base_revisions() + [revision(
            "REV5", 5, "competition_open", "CP2", {"claims": ["C1"]},
            {"mechanisms": ["M1", "M2"], "shared_explanation": "都能解释",
             "conflicting_predictions": [], "discriminating_intervention": "TBD"}, actor="R6")]
        index, _ = cg.full_index(state(), revisions, "A")
        hint = cg.next_action_hint(cg.CanonicalView(state()), index)
        self.assertIn("CP2", hint)

    def test_brief_is_generated_in_english_machine_form_not_a_document(self):
        """The brief is a control-plane artifact, not a route document."""
        text = self.brief()
        self.assertTrue(text.startswith("# Cognitive Context Brief"))
        self.assertNotIn(".research-idea-pipeline/routes/", text.splitlines()[0])


# ---------------------------------------------------------------------------
# Cross-session: a refuted mechanism must not be re-proposed
# ---------------------------------------------------------------------------

class TestCrossSessionAvoidsRefutedMechanism(unittest.TestCase):
    """Recovering understanding includes recovering what is already dead.

    A restart that brings back the mechanism model but loses the refutation will re-propose
    the same explanation, which is the duplication the engine exists to prevent. The test
    therefore drives a full restart from disk and checks the recovered *behaviour*, not just
    the presence of a field.
    """

    def refuted_revisions(self):
        revisions = base_revisions()
        revisions.append(revision(
            "REV9", 9, "mechanism_create", "M9",
            {"hypotheses": ["H1"], "failures": ["F1"]},
            {"statement": "已被判别实验否证的机制（不得重提）"}))
        return revisions

    def test_the_refuted_mechanism_is_recovered_as_refuted(self):
        index, diagnostics = cg.full_index(state(), self.refuted_revisions(), "A")
        mechanism = next(m for m in index["mechanisms"] if m["id"] == "M9")
        self.assertEqual(mechanism["support_level"], "refuted")
        self.assertEqual(mechanism["status"], "refuted")
        self.assertTrue(any("failures[F1]" in reason
                            for reason in mechanism["support_reasons"]))
        self.assertFalse([d for d in diagnostics if d.rule in ("CM7", "CM9")])

    def test_a_restart_keeps_it_out_of_hot_memory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state_path, cognition_dir = write_fixture(root, state(), self.refuted_revisions())
            self.assertEqual(quiet(cg.op_build, state_path, cognition_dir), cg.EXIT_OK)
            # New session: everything is re-read from disk, nothing is carried in memory.
            reloaded = cg.load_state(state_path)
            revisions, _ = cg.load_revisions(cognition_dir / cg.REVISIONS_NAME)
            index, _ = cg.full_index(reloaded, revisions, "A")
            selection = cg.recall(index, reloaded)
            hot_ids = {m["id"] for m in selection["hot"]["mechanisms"]}
            warm_ids = {m["id"] for m in selection["warm"]["mechanisms"]}
            self.assertNotIn("M9", hot_ids)
            self.assertIn("M9", warm_ids)
            self.assertEqual(quiet(cg.op_check, state_path, cognition_dir), cg.EXIT_OK)

    def test_the_restart_recovers_the_repeat_prohibition(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state_path, cognition_dir = write_fixture(root, state(), self.refuted_revisions())
            quiet(cg.op_build, state_path, cognition_dir)
            reloaded = cg.load_state(state_path)
            constraints = cg.failure_constraints(reloaded)
            self.assertEqual(constraints[0]["retry"], "blocked")
            index, _ = cg.full_index(reloaded, base_revisions(), "A")
            self.assertTrue(any(item["kind"] == "failed_repeat" for item in index["boundaries"]))
            brief = (cognition_dir / cg.BRIEF_NAME).read_text(encoding="utf-8")
            self.assertIn("refuted", brief)
            self.assertIn("retry=blocked", brief)

    def test_re_proposing_the_same_explanation_is_flagged(self):
        """The refuted anchors are remembered, so a restatement is not new progress."""
        revisions = self.refuted_revisions() + [revision(
            "REV10", 10, "mechanism_create", "M10",
            {"hypotheses": ["H1"], "failures": ["F1"]},
            {"statement": "同一机制换一种措辞重新提出"})]
        index, _ = cg.full_index(state(), revisions, "A")
        duplicates = [d for d in index["diagnostics"] if d["rule"] == "CM9"]
        self.assertTrue(duplicates, "a restatement of a refuted mechanism was not flagged")

    def test_the_next_action_does_not_revive_the_refuted_direction(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state_path, cognition_dir = write_fixture(root, state(), self.refuted_revisions())
            quiet(cg.op_build, state_path, cognition_dir)
            index, _ = cg.full_index(cg.load_state(state_path),
                                     self.refuted_revisions(), "A")
            hint = cg.next_action_hint(cg.CanonicalView(cg.load_state(state_path)), index)
            self.assertNotIn("M9", hint)
            self.assertTrue(hint.strip())


# ---------------------------------------------------------------------------
# No canonical mutation
# ---------------------------------------------------------------------------

class TestNoCanonicalMutation(unittest.TestCase):

    def test_build_validate_and_check_never_write_the_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state_path, cognition_dir = write_fixture(root, state(), base_revisions())
            before = state_path.read_bytes()
            self.assertEqual(quiet(cg.op_build, state_path, cognition_dir), cg.EXIT_OK)
            self.assertEqual(state_path.read_bytes(), before)
            self.assertEqual(quiet(cg.op_validate, state_path, cognition_dir), cg.EXIT_OK)
            self.assertEqual(state_path.read_bytes(), before)
            self.assertEqual(quiet(cg.op_check, state_path, cognition_dir), cg.EXIT_OK)
            self.assertEqual(state_path.read_bytes(), before)
            brief_out = root / "brief.md"
            self.assertEqual(quiet(cg.op_brief, state_path, cognition_dir, brief_out, 4000),
                             cg.EXIT_OK)
            self.assertEqual(state_path.read_bytes(), before)

    def test_cognition_writes_nothing_outside_its_own_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state_path, cognition_dir = write_fixture(root, state(), base_revisions())
            before = {path.name for path in root.iterdir()}
            quiet(cg.op_build, state_path, cognition_dir)
            after = {path.name for path in root.iterdir()}
            self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# CLI contract
# ---------------------------------------------------------------------------

class TestCLI(unittest.TestCase):

    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True, cwd=str(ROOT))

    def test_selftest_passes(self):
        proc = self.run_cli("--selftest")
        self.assertEqual(proc.returncode, cg.EXIT_OK, proc.stdout + proc.stderr)
        self.assertIn("selftest: PASS", proc.stdout)

    def test_list_kinds_exposes_the_frozen_vocabulary(self):
        proc = self.run_cli("--list-kinds")
        self.assertEqual(proc.returncode, cg.EXIT_OK)
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual(lines, list(cg.REVISION_KINDS))

    def test_missing_state_is_an_environment_error(self):
        proc = self.run_cli("check", "--state", "/nonexistent/state.json")
        self.assertEqual(proc.returncode, cg.EXIT_ENV)

    def test_invalid_json_is_an_environment_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / cg.STATE_NAME
            path.write_text("{not json", encoding="utf-8")
            proc = self.run_cli("check", "--state", str(path))
            self.assertEqual(proc.returncode, cg.EXIT_ENV)

    def test_missing_command_is_an_argument_error(self):
        proc = self.run_cli()
        self.assertEqual(proc.returncode, cg.EXIT_ERROR)

    def test_build_then_check_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state_path, cognition_dir = write_fixture(root, state(), base_revisions())
            build = self.run_cli("build", "--state", str(state_path),
                                 "--cognition", str(cognition_dir))
            self.assertEqual(build.returncode, cg.EXIT_OK, build.stdout + build.stderr)
            check = self.run_cli("check", "--state", str(state_path),
                                 "--cognition", str(cognition_dir))
            self.assertEqual(check.returncode, cg.EXIT_OK, check.stdout + check.stderr)

    def test_check_fails_when_the_index_is_absent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state_path, cognition_dir = write_fixture(root, state(), base_revisions())
            proc = self.run_cli("check", "--state", str(state_path),
                                "--cognition", str(cognition_dir))
            self.assertEqual(proc.returncode, cg.EXIT_HARD)

    def test_recall_emits_json(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state_path, cognition_dir = write_fixture(root, state(), base_revisions())
            quiet(cg.op_build, state_path, cognition_dir)
            proc = self.run_cli("recall", "--state", str(state_path),
                                "--cognition", str(cognition_dir))
            self.assertEqual(proc.returncode, cg.EXIT_OK)
            payload = json.loads(proc.stdout)
            self.assertIn("hot", payload)
            self.assertIn("failure_constraints", payload)


# ---------------------------------------------------------------------------
# Shipped fixture
# ---------------------------------------------------------------------------

class TestShippedFixture(unittest.TestCase):

    def test_fixture_exists_and_round_trips(self):
        state_path = FIXTURES / "state.json"
        self.assertTrue(state_path.is_file(), "examples/cognition/state.json is missing")
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            copied_state = root / cg.STATE_NAME
            shutil.copy(state_path, copied_state)
            cognition_dir = root / cg.COGNITION_DIRNAME
            cognition_dir.mkdir()
            shutil.copy(FIXTURES / cg.REVISIONS_NAME, cognition_dir / cg.REVISIONS_NAME)
            self.assertEqual(quiet(cg.op_build, copied_state, cognition_dir), cg.EXIT_OK)
            self.assertEqual(quiet(cg.op_check, copied_state, cognition_dir), cg.EXIT_OK)
            index = json.loads((cognition_dir / cg.INDEX_NAME).read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(index["mechanisms"]), 2)
            self.assertGreaterEqual(len(index["competitions"]), 1)
            self.assertGreaterEqual(len(index["anomalies"]), 1)

    def test_fixture_state_passes_the_canonical_gate(self):
        import state_check as sc
        doc = json.loads((FIXTURES / "state.json").read_text(encoding="utf-8"))
        report = sc.check_state(doc, source=str(FIXTURES / "state.json"))
        self.assertTrue(report.ok, [v.render() for v in report.all_violations()])

    def test_fixture_is_marked_synthetic(self):
        doc = json.loads((FIXTURES / "state.json").read_text(encoding="utf-8"))
        blob = json.dumps(doc, ensure_ascii=False).lower()
        self.assertIn("synthetic", blob)


if __name__ == "__main__":
    unittest.main()
