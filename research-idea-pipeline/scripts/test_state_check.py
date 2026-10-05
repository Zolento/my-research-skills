#!/usr/bin/env python3
"""test_state_check.py — state_check.py 的离线测试（stdlib unittest，**不联网**）

运行：
    python3 -m unittest discover -s scripts -p "test_*.py" -v
    python3 scripts/test_state_check.py

为什么需要它
------------
`docs/r-architecture-wave1-spec.md` §2.3 的 V1—V10 如果只靠实现者自述「已实现」，
就还是散文。每条规则必须有一个**违规 fixture**钉住：
造违规 → 退出码 3 → 规则号正确 → 违规行带 JSON 路径与现值。
环境侧同理：缺文件 / JSON 非法必须是 4，不能与硬违规 3 混为一谈。

覆盖点
------
1. 合法 state → 0；`--json` 的 `ok=true` 且可解析
2. V1—V10 每条至少一个反例（V2 另测 refuting；V5 两个子判定；V8 悬空 + 成环；
   V10 四字段齐备 + 处置/关闭两个枚举）
3. 环境：缺文件 / 非法 JSON / 空文件 / 根非对象 / 缺八类数组 / 数组类型错 / 条目非对象 → 4
4. `--json` 在 0 / 3 / 4 三种情况下都可解析；`--check` 与默认行为等价
5. `--selftest` / `--list-rules` / 缺位置参数（退出码 1）
6. 模板联动：`templates/research-state.template.json` 就绪后自动启用断言（未就绪时 skip）
"""

from __future__ import annotations

import contextlib
import io
import copy
import pathlib
import re
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Tuple

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import state_check as sc  # noqa: E402

TEMPLATE = SCRIPTS.parent / "templates" / "research-state.template.json"


# ---------------------------------------------------------------------------
# fixture：一份覆盖 spec §2.2 全部八类对象 + assurance/repairs 的合法 state
# ---------------------------------------------------------------------------

def valid_state() -> Dict[str, Any]:
    """合法骨架。任何一条 V 规则的反例都在它上面做单点变异。"""
    return {
        "_schema": "research-idea-pipeline/research-state@1",
        "claims": [
            {
                "id": "C17",
                "statement": "adaptation 必须改写先验参数才带来增量",
                "parent": None,
                "subclaims": ["C17a"],
                "status": "supported",
                "supporting_evidence": ["E32"],
                "refuting_evidence": [],
                "nearest_alternative": "通用微调也能达到同等增量",
                "falsifier": "若 R2（机制应失效）与 R1 结果近似，则 C17 不成立",
                "scope": "brain MRI / acceleration=4",
                "known_flaws": ["F3"],
            },
            {
                "id": "C18",
                "statement": "该机制可外推到 multi-coil 采集",
                "parent": "C17",
                "subclaims": [],
                "status": "ungrounded",
                "supporting_evidence": [],
                "refuting_evidence": [],
                "nearest_alternative": "外推不成立，增益来自 coil 冗余",
                "falsifier": "若 multi-coil 上增量消失则 C18 不成立",
                "scope": "multi-coil / acceleration=4",
                "known_flaws": [],
            },
        ],
        "evidence": [
            {
                "id": "E32", "kind": "experiment", "supports": ["C17"], "contradicts": [],
                "strength": "strong", "scope": "brain MRI / acceleration=4",
                "epistemic_status": "Observed", "source_ref": "X7",
            },
            {
                "id": "E33", "kind": "experiment", "supports": [], "contradicts": [],
                "strength": "weak", "scope": "brain MRI / acceleration=4",
                "epistemic_status": "Planned", "source_ref": "X8",
            },
        ],
        "assumptions": [
            {
                "id": "AS13", "statement": "adaptation must modify prior parameters",
                "status": "explicit", "challenged_by": ["H42"], "if_false": "C17 改写为通用微调",
            },
        ],
        "hypotheses": [
            {
                "id": "H42", "statement": "先验参数改写带来机制性增量",
                "structural_signature": {
                    "assumption_distance": 2, "formulation_distance": 3,
                    "representation_distance": 1, "theory_lens_distance": 3,
                    "mechanism_distance": 2,
                },
                "novelty_source": "assumption-breaking", "theory_lens": "transfer-learning",
                "nearest_prior": "LoRA", "falsifier": "R2 不降级",
                "expected_information_gain": 0.4, "status": "active",
                "niche": "N2", "island": "P2", "generation": 0, "status": "elite",
            },
        ],
        "experiments": [
            {
                "id": "X7", "parent": None, "stage": "X3", "claim_targeted": ["C17"],
                "alternative_targeted": ["ALT-1"], "code_commit": "abc123",
                "data_split": "fastMRI val", "seed": 0, "metric": "PSNR",
                "result": "0.8dB", "interpretation": "机制成立",
                "unexpected": [], "known_flaws": ["F3"], "next_branches": ["X8"],
                "status": "done",
            },
            {
                "id": "X8", "parent": "X7", "stage": "X4", "claim_targeted": ["C17"],
                "alternative_targeted": [], "code_commit": "abc123",
                "data_split": "fastMRI test", "seed": 0, "metric": "PSNR",
                "result": "", "interpretation": "", "unexpected": [],
                "known_flaws": [], "next_branches": [], "status": "planned",
            },
        ],
        "literature": [
            {"id": "LIT9", "ref": "[Author, 2024]", "relation": "shares-assumption"},
        ],
        "failures": [
            {
                "id": "F3", "kind": "inconclusive", "what": "R2 未分离出机制",
                "why": "样本量不足", "referenced_by": ["C17", "X7"],
            },
        ],
        "uncertainties": [
            {
                "id": "U3", "question": "机制在 R2 是否失效", "importance": "critical",
                "uncertainty": "high", "cheapest_discriminating_test": "X8", "status": "open",
            },
            {
                "id": "U4", "question": "multi-coil 外推是否成立", "importance": "high",
                "uncertainty": "medium", "cheapest_discriminating_test": "TBD", "status": "open",
            },
        ],
        "assurance": [
            {
                "kill_condition": "若 X8 上 R2 与 R1 结果近似则 kill 该机制分支",
                "discriminating_test": "X8",
            },
        ],
        "repairs": [
            {
                "flaw": "C17 not supported",
                "disposition": "RUN_TEST",
                "state_delta": "U3→X8 已排队；C17.status→partially-supported",
                "closure": "RESOLVED",
            },
        ],
    }


class _TmpState:
    """临时目录 + 写 state 文件（测试不碰仓库里的任何文件）。"""

    def __init__(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)

    def write(self, payload: Any, name: str = "state.json") -> Path:
        path = self.root / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def write_raw(self, text: str, name: str = "state.json") -> Path:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def cleanup(self) -> None:
        self._dir.cleanup()


def _run(*argv: str) -> Tuple[int, str, str]:
    """跑 main()，返回 (退出码, stdout, stderr)。"""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = sc.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def _run_json(*argv: str) -> Tuple[int, Dict[str, Any]]:
    code, out, _err = _run(*argv)
    return code, json.loads(out)


# ---------------------------------------------------------------------------
# 合法 state
# ---------------------------------------------------------------------------

class TestValidState(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = _TmpState()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_valid_state_exits_zero(self) -> None:
        path = self.tmp.write(valid_state())
        code, out, err = _run(str(path))
        self.assertEqual(code, sc.EXIT_OK, msg=out + err)
        self.assertIn(f"V1—V{sc.RULE_ORDER[-1][1:]} 全部通过", out)

    def test_valid_state_report_is_clean(self) -> None:
        report = sc.check_state(valid_state())
        self.assertTrue(report.ok)
        self.assertEqual(report.violations, [])
        self.assertEqual(report.exit_code, sc.EXIT_OK)

    def test_object_counts_are_reported(self) -> None:
        report = sc.check_state(valid_state())
        self.assertEqual(report.checked["claims"], 2)
        self.assertEqual(report.checked["experiments"], 2)
        self.assertEqual(report.checked["repairs"], 1)

    def test_tbd_literals_are_accepted(self) -> None:
        doc = valid_state()
        doc["uncertainties"][0]["cheapest_discriminating_test"] = "TBD"
        doc["assurance"][0]["discriminating_test"] = "TBD"
        self.assertEqual(sc.check_state(doc).exit_code, sc.EXIT_OK)

    def test_absent_assurance_and_repairs_are_vacuously_ok(self) -> None:
        doc = valid_state()
        del doc["assurance"], doc["repairs"]
        self.assertEqual(sc.check_state(doc).exit_code, sc.EXIT_OK)

    def test_wrapped_world_model_is_unwrapped(self) -> None:
        report = sc.check_state({"world_model": valid_state()})
        self.assertEqual(report.exit_code, sc.EXIT_OK)
        self.assertEqual(report.unwrapped_from, "world_model")

    def test_quiet_prints_only_summary(self) -> None:
        path = self.tmp.write(valid_state())
        code, out, _err = _run(str(path), "--quiet")
        self.assertEqual(code, sc.EXIT_OK)
        self.assertEqual(len(out.strip().splitlines()), 1)


# ---------------------------------------------------------------------------
# V1—V10：每条至少一个反例
# ---------------------------------------------------------------------------

class TestHardRules(unittest.TestCase):
    """每个反例：单点变异 → 退出码 3 → 只有该规则号 → 违规行含路径与现值。"""

    def _hard(self, doc: Dict[str, Any], rule: str, path_fragment: str) -> sc.Report:
        path = self.tmp.write(doc)
        code, out, err = _run(str(path))
        self.assertEqual(code, sc.EXIT_HARD, msg=out + err)
        report = sc.check_state(doc)
        self.assertEqual(report.rules(), [rule], msg=f"命中规则 {report.rules()}")
        self.assertTrue(
            any(path_fragment in violation.path for violation in report.violations),
            msg=f"违规路径缺 {path_fragment}：{[v.path for v in report.violations]}",
        )
        for violation in report.violations:
            line = violation.render()
            self.assertIn(violation.rule, line)
            self.assertIn(violation.path, line)
            expected_tail = "· " + (sc._display(violation.value) or violation.subject or "-")
            self.assertTrue(line.endswith(expected_tail), msg=line)
        return report

    def setUp(self) -> None:
        self.tmp = _TmpState()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_v1_falsifier_empty(self) -> None:
        doc = valid_state()
        doc["claims"][0]["falsifier"] = ""
        report = self._hard(doc, "V1", "claims[0].falsifier")
        # spec §2.3 的样例形态：规则号 + JSON 路径 + 现值（现值为空时显示对象 id）
        self.assertEqual(report.violations[0].render(), "V1 硬违规 · claims[0].falsifier 为空 · C17")

    def test_v1_falsifier_missing_key(self) -> None:
        doc = valid_state()
        del doc["claims"][1]["falsifier"]
        self._hard(doc, "V1", "claims[1].falsifier")

    def test_v2_supporting_evidence_dangling(self) -> None:
        doc = valid_state()
        doc["claims"][0]["supporting_evidence"] = ["E99"]
        report = self._hard(doc, "V2", "claims[0].supporting_evidence[0]")
        self.assertIn("E99", report.violations[0].render())

    def test_v2_refuting_evidence_dangling(self) -> None:
        doc = valid_state()
        doc["claims"][0]["refuting_evidence"] = ["E404"]
        self._hard(doc, "V2", "claims[0].refuting_evidence[0]")

    def test_v3_no_evidence_must_be_ungrounded(self) -> None:
        doc = valid_state()
        doc["claims"][0]["supporting_evidence"] = []
        doc["claims"][0]["status"] = "supported"
        self._hard(doc, "V3", "claims[0].status")

    def test_v3_grounded_claim_must_not_be_ungrounded(self) -> None:
        doc = valid_state()
        doc["claims"][0]["status"] = "ungrounded"
        self._hard(doc, "V3", "claims[0].status")

    def test_v4_failure_without_reference(self) -> None:
        doc = valid_state()
        doc["claims"][0]["known_flaws"] = []
        doc["experiments"][0]["known_flaws"] = []
        report = self._hard(doc, "V4", "failures[0]")
        self.assertIn("F3", report.violations[0].render())

    def test_v4_referenced_by_alone_is_not_enough(self) -> None:
        """spec §2.3 只认 claims/experiments 的 known_flaws；referenced_by 不算凭证。"""
        doc = valid_state()
        doc["claims"][0]["known_flaws"] = []
        doc["experiments"][0]["known_flaws"] = []
        doc["failures"][0]["referenced_by"] = ["C17", "X7"]  # 仍然违规
        self._hard(doc, "V4", "failures[0]")

    def test_v5_invalid_epistemic_status(self) -> None:
        doc = valid_state()
        doc["evidence"][0]["epistemic_status"] = "Verified"
        self._hard(doc, "V5", "evidence[0].epistemic_status")

    def test_v5_hypothesized_cannot_support(self) -> None:
        doc = valid_state()
        doc["evidence"][0]["epistemic_status"] = "Hypothesized"
        report = self._hard(doc, "V5", "claims[0].supporting_evidence[0]")
        self.assertIn("E32", report.violations[0].render())

    def test_v5_unknown_cannot_support(self) -> None:
        doc = valid_state()
        doc["evidence"][0]["epistemic_status"] = "Unknown"
        self._hard(doc, "V5", "claims[0].supporting_evidence[0]")

    def test_v6_hypothesis_niche_empty(self) -> None:
        doc = valid_state()
        doc["hypotheses"][0]["niche"] = ""
        self._hard(doc, "V6", "hypotheses[0].niche")

    def test_v7_test_points_to_missing_experiment(self) -> None:
        doc = valid_state()
        doc["uncertainties"][0]["cheapest_discriminating_test"] = "X99"
        report = self._hard(doc, "V7", "uncertainties[0].cheapest_discriminating_test")
        self.assertIn("X99", report.violations[0].render())

    def test_v8_parent_missing_experiment(self) -> None:
        doc = valid_state()
        doc["experiments"][1]["parent"] = "X99"
        self._hard(doc, "V8", "experiments[1].parent")

    def test_v8_tree_cycle(self) -> None:
        doc = valid_state()
        doc["experiments"][0]["parent"] = "X8"  # X8.parent 已是 X7
        report = self._hard(doc, "V8", "experiments[0].parent")
        self.assertEqual(len(report.violations), 1, msg="每个环只报一次")
        self.assertIn("成环", report.violations[0].render())

    def test_v9_kill_condition_empty(self) -> None:
        doc = valid_state()
        doc["assurance"][0]["kill_condition"] = ""
        self._hard(doc, "V9", "assurance[0].kill_condition")

    def test_v9_discriminating_test_dangling(self) -> None:
        doc = valid_state()
        doc["assurance"][0]["discriminating_test"] = "X99"
        self._hard(doc, "V9", "assurance[0].discriminating_test")

    def test_v10_flaw_only_is_not_closed(self) -> None:
        """spec §7 指定的场景：只写 flaw 不写 disposition 必须被拦住。"""
        doc = valid_state()
        doc["repairs"][0] = {"flaw": "C17 not supported"}
        report = self._hard(doc, "V10", "repairs[0].disposition")
        self.assertEqual(
            sorted({v.path.split(".")[-1] for v in report.violations}),
            ["closure", "disposition", "state_delta"],
        )

    def test_v10_disposition_enum(self) -> None:
        doc = valid_state()
        doc["repairs"][0]["disposition"] = "FIX"
        self._hard(doc, "V10", "repairs[0].disposition")

    def test_v10_closure_enum(self) -> None:
        doc = valid_state()
        doc["repairs"][0]["closure"] = "DONE"
        self._hard(doc, "V10", "repairs[0].closure")

    def test_v10_two_records_both_reported(self) -> None:
        doc = valid_state()
        doc["repairs"].append({"flaw": "X8 未复现"})
        report = sc.check_state(doc)
        self.assertEqual(report.rules(), ["V10"])
        self.assertEqual(len(report.violations), 3)  # 第二条缺三个字段
        self.assertEqual(report.rule_counts()["V10"], 3)


# ---------------------------------------------------------------------------
# 环境不满足：退出码 4
# ---------------------------------------------------------------------------

class TestV11V12(unittest.TestCase):
    """V11（X2 不得承担 claim 判别）与 V12（failed 必须进 failures[]）—— Wave 2 首批闸门。"""

    def test_v11_x2_with_claim_targeted_is_hard(self) -> None:
        doc = valid_state()
        doc["experiments"][0]["stage"] = "X2"
        report = sc.check_state(doc)
        self.assertEqual(report.exit_code, sc.EXIT_HARD)
        self.assertEqual(report.rules(), ["V11"])
        self.assertEqual(report.violations[0].path, "experiments[0].claim_targeted")

    def test_v11_x2_with_empty_claim_targeted_is_clean(self) -> None:
        doc = valid_state()
        doc["experiments"][0]["stage"] = "X2"
        doc["experiments"][0]["claim_targeted"] = []
        self.assertEqual(sc.check_state(doc).exit_code, sc.EXIT_OK)

    def test_v12_failed_without_failure_record_is_hard(self) -> None:
        doc = valid_state()
        node = copy.deepcopy(doc["experiments"][0])
        node.update(id="X99", stage="X3", status="failed", claim_targeted=["C0"])
        doc["experiments"].append(node)
        report = sc.check_state(doc)
        self.assertEqual(report.exit_code, sc.EXIT_HARD)
        self.assertEqual(report.rules(), ["V12"])
        self.assertEqual(report.violations[0].subject, "X99")
        self.assertTrue(report.violations[0].path.endswith(".status"), msg=report.violations[0].path)

    def test_v12_failed_already_referenced_is_clean(self) -> None:
        doc = valid_state()
        doc["experiments"][0]["status"] = "failed"   # X1 已被 failures[] 引用
        self.assertEqual(sc.check_state(doc).exit_code, sc.EXIT_OK)


class TestV13V15(unittest.TestCase):
    """V13（island 枚举）/ V14（generation 非负整数）/ V15（每 niche 留 elite）—— Wave 2 发现层。"""

    def test_v13_illegal_island_is_hard(self) -> None:
        doc = valid_state(); doc["hypotheses"][0]["island"] = "PX"
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V13"])

    def test_v13_local_track_is_legal(self) -> None:
        doc = valid_state(); doc["hypotheses"][0]["island"] = "local"
        self.assertEqual(sc.check_state(doc).exit_code, sc.EXIT_OK)

    def test_v14_string_generation_is_hard(self) -> None:
        doc = valid_state(); doc["hypotheses"][0]["generation"] = "1"
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V14"])

    def test_v14_negative_generation_is_hard(self) -> None:
        doc = valid_state(); doc["hypotheses"][0]["generation"] = -1
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V14"])

    def test_v15_niche_without_elite_is_hard(self) -> None:
        doc = valid_state()
        doc["hypotheses"].append(dict(doc["hypotheses"][0], id="H2", niche="N5", status="active"))
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V15"])

    def test_v15_two_niches_each_with_elite_is_clean(self) -> None:
        doc = valid_state()
        doc["hypotheses"].append(dict(doc["hypotheses"][0], id="H2", niche="N5", status="elite"))
        self.assertEqual(sc.check_state(doc).exit_code, sc.EXIT_OK)

    def test_v15_elite_counts_even_with_active_sibling(self) -> None:
        doc = valid_state()
        doc["hypotheses"].append(dict(doc["hypotheses"][0], id="H2", niche="N2", status="active"))
        self.assertEqual(sc.check_state(doc).exit_code, sc.EXIT_OK)

    def test_v6_niche_must_be_preset_name(self) -> None:
        doc = valid_state(); doc["hypotheses"][0]["niche"] = "assumption-breaking"
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V6"])


class TestEnvironment(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = _TmpState()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_missing_file(self) -> None:
        code, _out, err = _run(str(self.tmp.root / "nope.json"))
        self.assertEqual(code, sc.EXIT_ENV)
        self.assertIn("不存在", err)

    def test_invalid_json(self) -> None:
        path = self.tmp.write_raw("{ not json")
        code, _out, err = _run(str(path))
        self.assertEqual(code, sc.EXIT_ENV)
        self.assertIn("不是合法 JSON", err)

    def test_empty_file(self) -> None:
        path = self.tmp.write_raw("")
        self.assertEqual(_run(str(path))[0], sc.EXIT_ENV)

    def test_directory_is_not_a_state_file(self) -> None:
        code, _out, err = _run(str(self.tmp.root))
        self.assertEqual(code, sc.EXIT_ENV)
        self.assertTrue("目录" in err or "读不到" in err, msg=err)

    def test_root_not_an_object(self) -> None:
        path = self.tmp.write([1, 2, 3])
        self.assertEqual(_run(str(path))[0], sc.EXIT_ENV)

    def test_no_world_model_arrays(self) -> None:
        path = self.tmp.write({"foo": 1})
        code, _out, err = _run(str(path))
        self.assertEqual(code, sc.EXIT_ENV)
        self.assertIn("八类一等对象", err)

    def test_object_array_wrong_type(self) -> None:
        path = self.tmp.write({"claims": "nope"})
        self.assertEqual(_run(str(path))[0], sc.EXIT_ENV)

    def test_entry_not_an_object(self) -> None:
        path = self.tmp.write({"claims": ["C1"]})
        self.assertEqual(_run(str(path))[0], sc.EXIT_ENV)

    def test_check_flag_matches_default(self) -> None:
        good = self.tmp.write(valid_state(), "good.json")
        self.assertEqual(_run(str(good), "--check")[0], sc.EXIT_OK)

        doc = valid_state()
        doc["claims"][0]["falsifier"] = ""
        bad = self.tmp.write(doc, "bad.json")
        self.assertEqual(_run(str(bad), "--check")[0], sc.EXIT_HARD)


# ---------------------------------------------------------------------------
# --json：0 / 3 / 4 三种情况都可解析
# ---------------------------------------------------------------------------

class TestJsonOutput(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = _TmpState()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_json_for_valid_state(self) -> None:
        path = self.tmp.write(valid_state())
        code, payload = _run_json(str(path), "--json")
        self.assertEqual(code, sc.EXIT_OK)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["exit_code"], sc.EXIT_OK)
        self.assertEqual(payload["violations"], [])
        self.assertEqual(payload["schema"], sc.SCHEMA)

    def test_json_for_violation_is_machine_readable(self) -> None:
        doc = valid_state()
        doc["claims"][0]["falsifier"] = ""
        path = self.tmp.write(doc)
        code, payload = _run_json(str(path), "--json")
        self.assertEqual(code, sc.EXIT_HARD)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["counts"], {"V1": 1})
        violation = payload["violations"][0]
        for key in ("rule", "severity", "path", "detail", "value", "subject", "line"):
            self.assertIn(key, violation)
        self.assertEqual(violation["rule"], "V1")
        self.assertEqual(violation["path"], "claims[0].falsifier")
        self.assertEqual(violation["subject"], "C17")
        self.assertIn("V1 硬违规", violation["line"])

    def test_json_for_missing_file(self) -> None:
        code, payload = _run_json(str(self.tmp.root / "nope.json"), "--json")
        self.assertEqual(code, sc.EXIT_ENV)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error_kind"], "missing-file")
        self.assertEqual(payload["violations"], [])

    def test_json_for_invalid_json(self) -> None:
        path = self.tmp.write_raw("{ oops")
        code, payload = _run_json(str(path), "--json")
        self.assertEqual(code, sc.EXIT_ENV)
        self.assertEqual(payload["error_kind"], "invalid-json")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCli(unittest.TestCase):
    def test_list_rules_covers_all_rules(self) -> None:
        code, out, _err = _run("--list-rules")
        self.assertEqual(code, sc.EXIT_OK)
        for rule in sc.RULE_ORDER:
            self.assertIn(rule, out)
        self.assertEqual(sc.RULE_ORDER, list(sc.RULES))

    def test_selftest_passes(self) -> None:
        code, out, _err = _run("--selftest")
        self.assertEqual(code, sc.EXIT_OK, msg=out)
        self.assertIn("selftest OK", out)

    def test_missing_positional_is_usage_error(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            with contextlib.redirect_stderr(io.StringIO()):
                sc.main([])
        self.assertEqual(caught.exception.code, sc.EXIT_ERROR)

    def test_every_rule_has_judgement_text(self) -> None:
        self.assertTrue(len(sc.RULES) >= len(sc.CHECKS))
        self.assertEqual(set(sc.RULES), set(sc.CHECKS))
        for rule, text in sc.RULES.items():
            self.assertTrue(text.strip(), msg=rule)


# ---------------------------------------------------------------------------
# 模板联动（state-model 并发生成；未就绪时 skip，就绪后自动生效）
# ---------------------------------------------------------------------------

class TestTemplateInterop(unittest.TestCase):
    @unittest.skipUnless(TEMPLATE.is_file(), "templates/research-state.template.json 尚未就绪")
    def test_template_passes_validator(self) -> None:
        code, out, err = _run(str(TEMPLATE))
        self.assertEqual(code, sc.EXIT_OK, msg=f"{out}\n{err}")

    @unittest.skipUnless(TEMPLATE.is_file(), "templates/research-state.template.json 尚未就绪")
    def test_template_json_is_clean(self) -> None:
        code, payload = _run_json(str(TEMPLATE), "--json")
        self.assertEqual(code, sc.EXIT_OK, msg=json.dumps(payload.get("violations"), ensure_ascii=False))

    @unittest.skipUnless(TEMPLATE.is_file(), "templates/research-state.template.json 尚未就绪")
    def test_template_declares_all_eight_objects(self) -> None:
        doc = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        for key, _prefix in sc.OBJECT_KEYS:
            self.assertIn(key, doc, msg=f"模板缺少 {key}")


if __name__ == "__main__":
    unittest.main(verbosity=2)

class TestTableIntegrity(unittest.TestCase):
    """三张读写表的结构完整性 —— 三方「读/写格」比对看不见列覆盖/错位。

    起因：一次「按单元格索引重写」把 SKILL §0 的「作用」列与 policy §5 的
    「对应文件」列覆盖掉，而三方读/写格比对仍然全绿。本组用例覆盖该盲区。
    """

    ROOT = pathlib.Path(__file__).resolve().parent.parent

    def _rows(self, rel, start, stop, key_col=1):
        text = (self.ROOT / rel).read_text(encoding="utf-8")
        begin = text.index(start)
        end = text.index(stop, begin) if stop else len(text)
        rows = []
        for line in text[begin:end].split("\n"):
            cells = line.split("|")
            if len(cells) < 3:
                continue
            m = re.match(r"^\s*\*\*(R\d+)\*\*", cells[key_col])
            if m:
                rows.append((m.group(1), cells))
        return rows

    def test_policy_readwrite_table_columns(self) -> None:
        rows = self._rows("references/research-state-policy.md", "| 阶段 | 读什么", "\n\n>")
        self.assertTrue(rows, "policy §5 读不到阶段行")
        for stage, cells in rows:
            # 4 列表格：| 阶段 | 读 | 写 | 文件 | → split("|") 得 6 段
            self.assertEqual(len(cells), 6, f"policy {stage} 列数 {len(cells)}")

    def test_skill_stage_table_has_effect_column(self) -> None:
        rows = self._rows("SKILL.md", "| Phase | 名称 |", "\n\n")
        self.assertTrue(rows, "SKILL §0 读不到阶段行")
        for stage, cells in rows:
            self.assertEqual(len(cells), 7, f"SKILL {stage} 列数 {len(cells)}")
            effect, read = cells[2].strip(), cells[4].strip()
            self.assertTrue(effect, f"SKILL {stage} 作用列空")
            self.assertNotEqual(effect, read, f"SKILL {stage} 作用列被读列覆盖")

    def test_policy_file_column_points_to_real_file(self) -> None:
        rows = self._rows("references/research-state-policy.md", "| 阶段 | 读什么", "\n\n>")
        for stage, cells in rows:
            target = cells[4].strip().strip("`")
            self.assertTrue(target, f"policy {stage} 对应文件列空")
            if target.startswith("phase-"):
                self.assertTrue((self.ROOT / "references" / target).exists(),
                                f"policy {stage} 指向不存在的 {target}")

    def test_phase_tables_three_columns(self) -> None:
        for path in sorted((self.ROOT / "references").glob("phase-*.md")):
            text = path.read_text(encoding="utf-8")
            if "## 读 / 写 World Model" not in text:
                continue
            block = text[text.rindex("## 读 / 写 World Model"):]
            for line in block.split("\n"):
                cells = line.split("|")
                if len(cells) < 3:
                    continue
                m = re.match(r"^\s*\*\*(R\d+)\*\*", cells[1])
                if m:
                    self.assertEqual(len(cells), 5, f"{path.name} {m.group(1)} 列数 {len(cells)}")
