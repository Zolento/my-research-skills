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
2. V1—V24 每条至少一个反例（V2 另测 refuting；V5 两个子判定；V8 悬空 + 成环；
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
        "state_version": 0,
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
                "depends_on": ["E32"],
                "validity": {"status": "valid", "reason": "X7 的统计证据仍成立", "since_state_version": 0},
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
                "depends_on": [],
                "validity": {"status": "valid", "reason": "尚无证据也未受失效影响", "since_state_version": 0},
            },
        ],
        "evidence": [
            {
                "id": "E32", "kind": "experiment", "supports": ["C17"], "contradicts": [],
                "strength": "strong", "scope": "brain MRI / acceleration=4",
                "epistemic_status": "Observed", "source_ref": "X7",
                "verification_tier": "T2",
                "depends_on": ["X7"],
                "validity": {"status": "valid", "reason": "X7 已 done 且结果已写入", "since_state_version": 0},
            },
            {
                "id": "E33", "kind": "experiment", "supports": [], "contradicts": [],
                "strength": "weak", "scope": "brain MRI / acceleration=4",
                "epistemic_status": "Planned", "source_ref": "X8",
                "verification_tier": "T0",
                "depends_on": ["X8"],
                "validity": {"status": "pending", "reason": "X8 尚未产生结果", "since_state_version": 0},
            },
        ],
        "assumptions": [
            {
                "id": "AS13", "statement": "adaptation must modify prior parameters",
                "status": "explicit", "challenged_by": ["H42"], "if_false": "C17 改写为通用微调",
                "depends_on": [],
                "validity": {"status": "valid", "reason": "仍被显式接受", "since_state_version": 0},
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
                "operator": "assumption_breaker", "parents": [],
                "depends_on": ["AS13"],
                "validity": {"status": "valid", "reason": "上游假设未被推翻", "since_state_version": 0},
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
                "preregistration": {
                    "frozen_at_state_version": 0,
                    "outcomes": [{
                        "id": "O1", "observation": "R2 上 PSNR 下降",
                        "update": [{"target": "C17", "op": "strengthen"}],
                    }],
                },
                "result_at_state_version": 0,
                "depends_on": [],
                "validity": {"status": "valid", "reason": "结果已按预注册写入", "since_state_version": 0},
            },
            {
                "id": "X8", "parent": "X7", "stage": "X4", "claim_targeted": ["C17"],
                "alternative_targeted": [], "code_commit": "abc123",
                "data_split": "fastMRI test", "seed": 0, "metric": "PSNR",
                "result": "", "interpretation": "", "unexpected": [],
                "known_flaws": [], "next_branches": [], "status": "planned",
                "preregistration": None,
                "result_at_state_version": None,
                "depends_on": ["X7"],
                "validity": {"status": "pending", "reason": "尚未运行", "since_state_version": 0},
            },
        ],
        "literature": [
            {"id": "LIT9", "ref": "[Author, 2024]", "relation": "shares-assumption",
             "depends_on": [], "validity": {"status": "valid", "reason": "与当前 scope 一致", "since_state_version": 0}},
        ],
        "failures": [
            {
                "id": "F3", "kind": "inconclusive", "what": "R2 未分离出机制",
                "why": "样本量不足", "referenced_by": ["C17", "X7"],
                "depends_on": ["X7"],
                "validity": {"status": "valid", "reason": "失败记录仍成立", "since_state_version": 0},
            },
        ],
        "uncertainties": [
            {
                "id": "U3", "question": "机制在 R2 是否失效", "importance": "critical",
                "uncertainty": "high", "cheapest_discriminating_test": "X8", "status": "open",
                "depends_on": ["C17"],
                "validity": {"status": "valid", "reason": "仍待判别实验", "since_state_version": 0},
            },
            {
                "id": "U4", "question": "multi-coil 外推是否成立", "importance": "high",
                "uncertainty": "medium", "cheapest_discriminating_test": "TBD", "status": "open",
                "depends_on": [],
                "validity": {"status": "valid", "reason": "尚无判别实验", "since_state_version": 0},
            },
        ],
        "assurance": [
            {
                "kill_condition": "若 X8 上 R2 与 R1 结果近似则 kill 该机制分支",
                "discriminating_test": "X8",
                "verification_tier": "T0",
            },
        ],
        "repairs": [
            {
                "flaw": "C17 not supported",
                "disposition": "RUN_TEST",
                "state_delta": "U3→X8 已排队；C17.status→partially-supported",
                "closure": "RESOLVED", "targets": [],
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

    def test_v13_island_p3_is_hard(self) -> None:
        """`P3` 只产 typed intermediate，不是 candidate（HIGH-2）。"""
        doc = valid_state()
        doc["hypotheses"][0].update(island="P3", operator="abstraction")
        report = sc.check_state(doc, source="<test>")
        self.assertEqual(report.rules(), ["V13"])
        self.assertIn("typed intermediate", report.violations[0].detail)

    def test_candidate_islands_exclude_p3(self) -> None:
        self.assertEqual(sc.CANDIDATE_ISLANDS,
                         ("P1", "P2", "P4", "P5", "P6", "local"))

    def test_v13_local_track_is_legal(self) -> None:
        doc = valid_state(); doc["hypotheses"][0]["island"] = "local"
        doc["hypotheses"][0]["operator"] = "local"  # V16：generation-0 必须与 island 对应
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


class TestV16V17(unittest.TestCase):
    """V16（operator 十二算子 + generation-0 与 island 对应）/ V17（parents 谱系）—— R6 候选谱系。"""

    def _with_child(self, doc, **overrides):
        """在 base 上补一个 generation-1 的子候选（默认由 H42 繁衍）。"""
        child = copy.deepcopy(doc["hypotheses"][0])
        child.update(id="H2", generation=1, operator="mutation", parents=["H42"], status="active")
        child.update(overrides)
        doc["hypotheses"].append(child)
        return doc

    # --- V16 ---

    def test_v16_empty_operator_is_hard(self) -> None:
        doc = valid_state(); doc["hypotheses"][0]["operator"] = ""
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V16"])
        self.assertEqual(r.violations[0].path, "hypotheses[0].operator")

    def test_v16_missing_operator_is_hard(self) -> None:
        doc = valid_state(); del doc["hypotheses"][0]["operator"]
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V16"])

    def test_v16_unknown_operator_is_hard(self) -> None:
        doc = valid_state(); doc["hypotheses"][0]["operator"] = "teleport"
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V16"])

    def test_v16_non_string_operator_is_hard(self) -> None:
        doc = valid_state(); doc["hypotheses"][0]["operator"] = 7
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V16"])

    def test_v16_generation0_island_mismatch_is_hard(self) -> None:
        doc = valid_state(); doc["hypotheses"][0]["operator"] = "reframe"  # island 是 P2
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V16"])
        self.assertIn("assumption_breaker", r.violations[0].render())

    def test_v16_every_generation0_island_operator_pair_is_clean(self) -> None:
        # 只覆盖 candidate island：`P3` 不产 candidate（V13 拒绝），
        # 其合法性由 TestV13V15.test_v13_island_p3_is_hard 单独锁住。
        for island, operator in sc.ISLAND_OPERATOR.items():
            if island not in sc.CANDIDATE_ISLANDS:
                continue
            doc = valid_state()
            doc["hypotheses"][0]["island"] = island
            doc["hypotheses"][0]["operator"] = operator
            self.assertEqual(sc.check_state(doc).exit_code, sc.EXIT_OK, msg=f"{island}/{operator}")

    def test_v16_all_twelve_operators_legal_at_generation1(self) -> None:
        for operator in sc.OPERATORS:
            doc = self._with_child(valid_state(), operator=operator)
            self.assertEqual(sc.check_state(doc).exit_code, sc.EXIT_OK, msg=operator)

    def test_v16_illegal_island_is_left_to_v13(self) -> None:
        doc = valid_state()
        doc["hypotheses"][0]["island"] = "PX"
        doc["hypotheses"][0]["operator"] = "reframe"  # V16 不得重复报 island 本身非法
        r = sc.check_state(doc)
        self.assertEqual(r.rules(), ["V13"])

    def test_v16_invalid_generation_does_not_trigger_mapping(self) -> None:
        doc = valid_state()
        doc["hypotheses"][0]["operator"] = "reframe"  # 与 P2 不匹配，但 generation 非法 → 交给 V14
        doc["hypotheses"][0]["generation"] = "0"
        r = sc.check_state(doc)
        self.assertEqual(r.rules(), ["V14"])

    # --- V17 ---

    def test_v17_missing_parents_is_hard(self) -> None:
        doc = valid_state(); del doc["hypotheses"][0]["parents"]
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V17"])
        self.assertEqual(r.violations[0].path, "hypotheses[0].parents")

    def test_v17_parents_not_array_is_hard(self) -> None:
        doc = valid_state(); doc["hypotheses"][0]["parents"] = "H42"
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V17"])

    def test_v17_non_string_parent_id_is_hard(self) -> None:
        doc = valid_state(); doc["hypotheses"][0]["parents"] = [7]
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V17"])

    def test_v17_dangling_parent_is_hard(self) -> None:
        doc = valid_state(); doc["hypotheses"][0]["parents"] = ["H404"]
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V17"])
        self.assertEqual(r.violations[0].path, "hypotheses[0].parents[0]")

    def test_v17_self_parent_is_hard(self) -> None:
        doc = valid_state(); doc["hypotheses"][0]["parents"] = ["H42"]
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V17"])
        self.assertIn("自指", r.violations[0].render())

    def test_v17_cycle_is_hard(self) -> None:
        doc = self._with_child(valid_state())
        doc["hypotheses"][0]["parents"] = ["H2"]  # H42 → H2 → H42
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V17"])
        self.assertTrue(any("成环" in v.render() for v in r.violations))

    def test_v17_generation_not_strictly_decreasing_is_hard(self) -> None:
        doc = self._with_child(valid_state())
        doc["hypotheses"][0]["generation"] = 1  # H2(gen 1) 的 parent H42 也是 gen 1
        r = sc.check_state(doc)
        self.assertEqual(r.exit_code, sc.EXIT_HARD); self.assertEqual(r.rules(), ["V17"])

    def test_v17_gen1_child_of_gen0_is_clean(self) -> None:
        doc = self._with_child(valid_state())
        self.assertEqual(sc.check_state(doc).exit_code, sc.EXIT_OK)

    def test_v17_initial_candidate_with_empty_parents_is_clean(self) -> None:
        self.assertEqual(sc.check_state(valid_state()).exit_code, sc.EXIT_OK)

    def test_v17_invalid_parent_generation_is_left_to_v14(self) -> None:
        doc = self._with_child(valid_state())
        doc["hypotheses"][0]["generation"] = "0"  # 父 generation 非法 → 跳过该边
        r = sc.check_state(doc)
        self.assertEqual(r.rules(), ["V14"])


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
            # markdown 表格在空行处结束。**必须**在这里停：一条误插进表体中间的
            # blockquote 会把表切成两半，而原来的 "\n\n>" 停止标记会被同一条 note 带偏，
            # 于是列检查只覆盖前半张表却仍然全绿（Batch 8 就是这么漏的）。
            if not line.strip():
                break
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
        # 行数守卫：表体若被一行 blockquote 切开，列检查只会覆盖前半张表却仍然全绿
        self.assertEqual(len(rows), 14, "policy §5 应恰好 14 个阶段行（表被切开了？）")
        for stage, cells in rows:
            # 4 列表格：| 阶段 | 读 | 写 | 文件 | → split("|") 得 6 段
            self.assertEqual(len(cells), 6, f"policy {stage} 列数 {len(cells)}")

    def test_skill_stage_table_has_effect_column(self) -> None:
        rows = self._rows("SKILL.md", "| Phase | 名称 |", "\n\n")
        self.assertTrue(rows, "SKILL §0 读不到阶段行")
        self.assertEqual(len(rows), 15, "SKILL §0 应恰好 15 个阶段行（表被切开了？）")
        for stage, cells in rows:
            self.assertEqual(len(cells), 7, f"SKILL {stage} 列数 {len(cells)}")
            name, effect, read = cells[2].strip(), cells[3].strip(), cells[4].strip()
            self.assertTrue(effect, f"SKILL {stage} 作用列空")
            self.assertNotEqual(effect, read, f"SKILL {stage} 作用列被读列覆盖")

    def test_policy_file_column_points_to_real_file(self) -> None:
        rows = self._rows("references/research-state-policy.md", "| 阶段 | 读什么", "\n\n>")
        for stage, cells in rows:
            target = cells[4].strip().strip("`")
            self.assertTrue(target, f"policy {stage} 对应文件列空")
            # 真实损坏是「文件列被读/写值覆盖」→ 必须先把格式断言放在存在性之前
            self.assertRegex(target, r"^(phase-[\w-]+\.md|\.\./SKILL\.md.*)$",
                             f"policy {stage} 对应文件列不是 phase-*.md：{target[:40]}")
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


# ---------------------------------------------------------------------------
# 规则副本比对 / R8 契约三方一致 / phase 文档不得残留旧字母流程
# ---------------------------------------------------------------------------

class TestRuleTableParity(unittest.TestCase):
    """一条规则有多个副本 → 必须有检查比对副本。

    规则正文的权威副本是 policy §4 的规则表；`state_check.py` 的 `RULES` 是执行副本。
    两者逐字不一致时，文档与代码各自「正确」，合起来是错的。
    """

    ROOT = pathlib.Path(__file__).resolve().parent.parent

    def _policy_rows(self):
        text = (self.ROOT / "references" / "research-state-policy.md").read_text(encoding="utf-8")
        return dict(re.findall(r"^\| (V\d+) \| (.+?) \| 硬 \|", text, re.M))

    def test_policy_rule_table_is_parseable(self) -> None:
        # 正则静默失配时，下面的比对会「全绿」——先锁住解析结果本身。
        rows = self._policy_rows()
        self.assertEqual(len(rows), len(sc.RULES), "policy §4 解析到的规则数不等于 RULES")
        self.assertIn("V1", rows)
        self.assertIn("V24", rows)

    def test_policy_rule_text_matches_validator(self) -> None:
        rows = self._policy_rows()
        self.assertEqual(set(rows), set(sc.RULES), "policy §4 的规则号集合与 RULES 不一致")
        for rule, expected in sc.RULES.items():
            self.assertEqual(rows[rule].strip(), expected.strip(), f"{rule} 文档与代码不一致")

    def _policy_shape_rows(self):
        text = (self.ROOT / "references" / "research-state-policy.md").read_text(encoding="utf-8")
        return dict(re.findall(r"^\| (S\d+) \| (.+?) \| 形状 \|", text, re.M))

    def test_policy_shape_table_is_parseable(self) -> None:
        rows = self._policy_shape_rows()
        self.assertEqual(len(rows), len(sc.SHAPES), "policy §4.0 解析到的形状规则数不等于 SHAPES")
        self.assertIn("S1", rows)

    def test_policy_shape_text_matches_validator(self) -> None:
        rows = self._policy_shape_rows()
        self.assertEqual(set(rows), set(sc.SHAPES), "policy §4.0 的编号集合与 SHAPES 不一致")
        for rule, expected in sc.SHAPES.items():
            self.assertEqual(rows[rule].strip(), expected.strip(), f"{rule} 文档与代码不一致")


class TestShapeGate(unittest.TestCase):
    """S1—S7：形状门。位置在 V1—V24 **之前**，且形状失败时不执行 V 规则。

    起因（总收官审计 MAJOR-4）：`state_check.py` 只做「引用完整性」，
    八类枚举、`structural_signature` 五键、`contract` 形状**零校验** ——
    非法值可以静默通过，`--check` 仍是 exit 0。
    """

    def _shape(self, doc):
        return sc.check_state(doc, source="<test>").shape_rules()

    def test_valid_state_passes_shape_gate(self) -> None:
        report = sc.check_state(valid_state(), source="<test>")
        self.assertEqual(report.shape, [])
        self.assertEqual(report.exit_code, sc.EXIT_OK)

    # ---- S1 ----
    def test_s1_missing_first_class_array(self) -> None:
        doc = valid_state(); doc.pop("literature")
        self.assertEqual(self._shape(doc), ["S1"])

    def test_s1_all_eight_empty_is_clean(self) -> None:
        doc = {key: [] for key in sc.FIRST_CLASS_KEYS}
        self.assertEqual(self._shape(doc), [])

    # ---- S2 ----
    def test_s2_empty_id(self) -> None:
        doc = valid_state(); doc["claims"][0]["id"] = ""
        self.assertEqual(self._shape(doc), ["S2"])

    def test_s2_duplicate_id(self) -> None:
        doc = valid_state()
        doc["claims"].append(dict(doc["claims"][0]))
        self.assertEqual(self._shape(doc), ["S2"])

    def test_s2_wrong_prefix(self) -> None:
        doc = valid_state(); doc["claims"][0]["id"] = "Q17"
        self.assertEqual(self._shape(doc), ["S2"])

    def test_s2_literature_must_use_lit_prefix(self) -> None:
        # policy §3.6：`LIT<n>`；**不得**写成 `L<n>`
        doc = valid_state(); doc["literature"][0]["id"] = "L1"
        self.assertEqual(self._shape(doc), ["S2"])

    # ---- S3 ----
    def test_s3_stage_out_of_enum(self) -> None:
        doc = valid_state(); doc["experiments"][0]["stage"] = "X9"
        self.assertEqual(self._shape(doc), ["S3"])

    def test_s3_missing_required_enum(self) -> None:
        doc = valid_state(); doc["hypotheses"][0].pop("status")
        self.assertEqual(self._shape(doc), ["S3"])

    def test_s3_literature_relation_out_of_enum(self) -> None:
        doc = valid_state(); doc["literature"][0]["relation"] = "sounds-good"
        self.assertEqual(self._shape(doc), ["S3"])

    def test_s3_claim_status_out_of_enum(self) -> None:
        doc = valid_state(); doc["claims"][0]["status"] = "maybe-true"
        self.assertEqual(self._shape(doc), ["S3"])

    def test_s3_every_listed_enum_is_enforced(self) -> None:
        # 防止有人往 ENUM_FIELDS 加字段却忘了它真的被查
        for key, field, allowed in sc.ENUM_FIELDS:
            doc = valid_state()
            if not doc.get(key):
                continue
            doc[key][0][field] = "definitely-not-in-enum"
            self.assertEqual(self._shape(doc), ["S3"], f"{key}[].{field} 未被 S3 强制")
            self.assertNotIn("definitely-not-in-enum", allowed)

    # ---- S4 ----
    def test_s4_missing_one_of_five_keys(self) -> None:
        doc = valid_state()
        doc["hypotheses"][0]["structural_signature"].pop("mechanism_distance")
        self.assertEqual(self._shape(doc), ["S4"])

    def test_s4_signature_not_object(self) -> None:
        doc = valid_state(); doc["hypotheses"][0]["structural_signature"] = "flat"
        self.assertEqual(self._shape(doc), ["S4"])

    def test_s4_distance_not_nonneg_int(self) -> None:
        doc = valid_state()
        doc["hypotheses"][0]["structural_signature"]["mechanism_distance"] = -1
        self.assertEqual(self._shape(doc), ["S4"])

    def test_s4_extra_key_rejected(self) -> None:
        doc = valid_state()
        doc["hypotheses"][0]["structural_signature"]["vibes_distance"] = 1
        self.assertEqual(self._shape(doc), ["S4"])

    # ---- S5 ----
    def test_s5_contract_missing_keys(self) -> None:
        doc = valid_state()
        doc["claims"][0]["contract"] = {"statement": "x", "scope": "y"}
        self.assertEqual(self._shape(doc), ["S5"])

    def test_s5_contract_full_ten_keys_is_clean(self) -> None:
        doc = valid_state()
        doc["claims"][0]["contract"] = {
            "statement": "x", "scope": "y", "critical_assumptions": ["AS13"],
            "supporting_required": ["E32"], "refuting": "z",
            "nearest_alternative": "alt", "minimal_discriminating_experiment": "X7",
            "expected_outcomes": {"O1": "supports C17"},
            "kill_rule": "若 O1 不成立则降级", "expansion_rule": "若 O1 成立则扩范围",
        }
        self.assertEqual(self._shape(doc), [])

    def test_s5_expected_outcomes_must_be_object(self) -> None:
        doc = valid_state()
        doc["claims"][0]["contract"] = {
            "statement": "x", "scope": "y", "critical_assumptions": [],
            "supporting_required": [], "refuting": "z",
            "nearest_alternative": "alt", "minimal_discriminating_experiment": "X7",
            "expected_outcomes": ["O1"], "kill_rule": "k", "expansion_rule": "e",
        }
        self.assertEqual(self._shape(doc), ["S5"])

    def test_s5_absent_contract_is_legal(self) -> None:
        # R1 骨架里未建契约的 claim 合法（模板 C0a / C1 就是这类）
        doc = valid_state()
        doc["claims"][1].pop("contract", None)
        self.assertNotIn("S5", self._shape(doc))

    # ---- S6 ----
    def test_s6_integrity_gate_out_of_enum(self) -> None:
        doc = valid_state(); doc["reviews"] = [{"id": "REV1", "integrity_gate": "maybe"}]
        self.assertEqual(self._shape(doc), ["S6"])

    def test_s6_reviews_not_array(self) -> None:
        doc = valid_state(); doc["reviews"] = {"id": "REV1"}
        self.assertEqual(self._shape(doc), ["S6"])

    def test_s6_decision_not_object(self) -> None:
        doc = valid_state(); doc["decision"] = "continue"
        self.assertEqual(self._shape(doc), ["S6"])

    def test_s6_reviews_id_absence_is_left_to_v23(self) -> None:
        # gate=fail 却无 id 是 V23 的判据；S6 不得抢报，否则规则号被掩盖
        doc = valid_state()
        doc["reviews"] = [{"integrity_gate": "fail"}]
        report = sc.check_state(doc, source="<test>")
        self.assertEqual(report.shape, [])
        self.assertEqual(report.rules(), ["V23"])

    def test_s6_decision_verdict_enum_is_left_to_v24(self) -> None:
        doc = valid_state()
        doc["decision"] = {"verdict": "banana"}
        report = sc.check_state(doc, source="<test>")
        self.assertEqual(report.shape, [])
        self.assertEqual(report.rules(), ["V24"])

    # ---- S7 ----
    def test_s7_state_version_must_be_nonneg_int(self) -> None:
        doc = valid_state(); doc["state_version"] = "0"
        self.assertEqual(self._shape(doc), ["S7"])

    def test_s7_negative_state_version(self) -> None:
        doc = valid_state(); doc["state_version"] = -1
        self.assertEqual(self._shape(doc), ["S7"])

    # ---- 顺序与互斥 ----
    def test_shape_runs_before_rules(self) -> None:
        doc = valid_state()
        doc["claims"][0]["id"] = ""          # S2
        doc["claims"][0]["falsifier"] = ""   # V1
        report = sc.check_state(doc, source="<test>")
        self.assertEqual(report.shape_rules(), ["S2"])
        self.assertEqual(report.rules(), [], "形状失败时不得执行 V 规则")
        self.assertEqual(report.violations, [])
        self.assertEqual(report.exit_code, sc.EXIT_HARD)

    def test_v19_depends_on_type_is_not_duplicated_in_shape(self) -> None:
        # 去重契约：depends_on 的类型属 V19，S 不得重复报
        doc = valid_state(); doc["claims"][0]["depends_on"] = "E32"
        report = sc.check_state(doc, source="<test>")
        self.assertEqual(report.shape, [])
        self.assertEqual(report.rules(), ["V19"])

    def test_shape_rules_are_reported_in_order(self) -> None:
        doc = valid_state()
        doc["claims"][0]["id"] = ""
        doc["state_version"] = "0"
        report = sc.check_state(doc, source="<test>")
        self.assertEqual(report.shape_rules(), ["S2", "S7"])

    def test_shape_violations_are_machine_readable(self) -> None:
        doc = valid_state(); doc["state_version"] = "0"
        payload = sc.check_state(doc, source="<test>").as_dict()
        self.assertEqual(payload["shape_counts"], {"S7": 1})
        self.assertEqual(payload["violations"], [])
        self.assertTrue(payload["shape"][0]["line"].startswith("S7"))

    def test_summary_names_shape_gate(self) -> None:
        doc = valid_state(); doc["state_version"] = "0"
        self.assertIn("[shape]", sc.check_state(doc, source="<test>").summary())

    def test_list_rules_includes_shape_gate(self) -> None:
        code, out, _err = _run("--list-rules")
        self.assertEqual(code, sc.EXIT_OK)
        for rule in sc.SHAPE_ORDER:
            self.assertIn(rule, out)
            self.assertIn(sc.SHAPES[rule], out)


class TestReadWriteTableParity(unittest.TestCase):
    """三处「读 / 写」表的**单元格内容**必须逐字一致。

    三处 = SKILL §0、policy §5、各 `phase-*.md` 的「读 / 写 World Model」。
    `TestTableIntegrity` 只查列数与列错位，**看不见内容漂移**。

    起因：Batch 8 改了 R3 的写集，SKILL 与 policy 都改了，却漏了
    `phase-r3-r6-discovery.md` 自己的那张表 —— 三方不一致，而所有表格检查全绿。
    """

    ROOT = pathlib.Path(__file__).resolve().parent.parent

    @staticmethod
    def _parse(text: str, anchor: str):
        """返回 {R 阶段: (读格, 写格)}。

        **必须给锚点**：文件里更早的表格也可能同时含「读」「写」两个字，
        扫全文会解析到错的表 —— 那样这个检查会静默变成空集。
        """
        lines = text[text.index(anchor):].split("\n")
        header_index = None
        read_index = write_index = 0
        for index, line in enumerate(lines):
            if "读" in line and "写" in line and line.strip().startswith("|"):
                cells = [cell.strip() for cell in line.split("|")]
                read_index = next(j for j, cell in enumerate(cells) if "读" in cell)
                write_index = next(j for j, cell in enumerate(cells) if "写" in cell)
                header_index = index
                break
        if header_index is None:
            return {}
        rows = {}
        for line in lines[header_index + 2:]:
            cells = line.split("|")
            if len(cells) <= max(read_index, write_index):
                if line.strip().startswith("|"):
                    continue
                break
            match = re.match(r"^\s*\*\*(R\d+(?:\s*/\s*R\d+)?)", cells[1].replace(" ", ""))
            if match:
                rows[match.group(1)] = (cells[read_index].strip(), cells[write_index].strip())
        return rows

    POLICY_ANCHOR = "| 阶段 | 读什么"
    SKILL_ANCHOR = "| Phase | 名称 |"
    PHASE_ANCHOR = "## 读 / 写 World Model"

    def _policy(self):
        text = (self.ROOT / "references" / "research-state-policy.md").read_text(encoding="utf-8")
        return self._parse(text, self.POLICY_ANCHOR)

    def test_skill_matches_policy(self) -> None:
        skill = self._parse((self.ROOT / "SKILL.md").read_text(encoding="utf-8"),
                            self.SKILL_ANCHOR)
        policy = self._policy()
        self.assertTrue(skill and policy, "读/写表解析失败（表头或阶段行找不到）")
        for stage in sorted(set(skill) & set(policy)):
            self.assertEqual(skill[stage], policy[stage], f"SKILL §0 的 {stage} 行与 policy §5 不一致")

    def test_every_phase_table_matches_policy(self) -> None:
        policy = self._policy()
        checked = 0
        for path in sorted((self.ROOT / "references").glob("phase-*.md")):
            text = path.read_text(encoding="utf-8")
            if "## 读 / 写 World Model" not in text:
                continue
            rows = self._parse(text, self.PHASE_ANCHOR)
            for stage in sorted(set(rows) & set(policy)):
                self.assertEqual(rows[stage], policy[stage],
                                 f"{path.name} 的 {stage} 行与 policy §5 不一致")
                checked += 1
        self.assertGreaterEqual(checked, 6, "解析到的 phase 读/写行太少（解析器失效？）")
        # 三道守卫：解析器一旦失效，检查必须变红，而不是静默通过
        self.assertEqual(len(policy), 14, "policy §5 应解析到 14 个阶段")


class TestContractKeyParity(unittest.TestCase):
    """`claims[].contract` 的十个键：validator ↔ 模板 ↔ R8 文档，三处必须一致。

    起因：迁移后契约键只在模板里；golden path 只写了 4 键却仍然 exit 0。
    """

    ROOT = pathlib.Path(__file__).resolve().parent.parent

    def test_validator_keys_match_template(self) -> None:
        tmpl = json.loads((self.ROOT / "templates" / "research-state.template.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual(list(sc.CONTRACT_KEYS), list(tmpl["claims"][0]["contract"]))

    def test_validator_keys_match_r8_doc_table(self) -> None:
        text = (self.ROOT / "references" / "phase-r8-evidence-contract.md").read_text(encoding="utf-8")
        begin = text.index("### R8.2.2")
        end = text.index("### R8.2.3", begin)
        self.assertEqual(list(sc.CONTRACT_KEYS),
                         re.findall(r"^\| `([a-z_]+)` \|", text[begin:end], re.M))

    def test_signature_keys_match_policy(self) -> None:
        text = (self.ROOT / "references" / "research-state-policy.md").read_text(encoding="utf-8")
        row = next(line for line in text.splitlines()
                   if line.startswith("| `structural_signature` |"))
        for key in sc.STRUCTURAL_SIGNATURE_KEYS:
            self.assertIn(f"`{key}`", row, f"policy §3.4 未登记结构签名键 {key}")


class TestR8ContractParity(unittest.TestCase):
    """R8 的头号产物 `claims[].contract` —— spec、模板两处必须一致。

    起因：R8 迁移后 `contract` 只在模板里存在，spec 侧没有字段表，
    `state_check.py` 零校验。本组同时锁住键集合与键顺序。
    """

    ROOT = pathlib.Path(__file__).resolve().parent.parent
    SPEC = "references/phase-r8-evidence-contract.md"

    def _spec_keys(self):
        text = (self.ROOT / self.SPEC).read_text(encoding="utf-8")
        begin = text.index("### R8.2.2")
        end = text.index("### R8.2.3", begin)
        return re.findall(r"^\| `([a-z_]+)` \|", text[begin:end], re.M)

    def test_spec_contract_table_has_ten_keys(self) -> None:
        keys = self._spec_keys()
        self.assertEqual(len(keys), 10, f"§R8.2.2 契约键数不是 10：{keys}")

    def test_spec_keys_match_template_contract(self) -> None:
        tmpl = json.loads((self.ROOT / "templates" / "research-state.template.json")
                          .read_text(encoding="utf-8"))
        contract = tmpl["claims"][0]["contract"]
        self.assertEqual(self._spec_keys(), list(contract),
                         "§R8.2.2 的契约键与模板 claims[].contract 不一致（含顺序）")

    def test_preregistration_op_seven_values_documented(self) -> None:
        text = (self.ROOT / self.SPEC).read_text(encoding="utf-8")
        for op in sc.PREREG_OPS:
            self.assertIn(op, text, f"R8 文档未登记 preregistration op：{op}")


class TestR7FirstPassAuditTarget(unittest.TestCase):
    """R7 首轮不得要求审一个尚不存在的 `claims[].contract`。

    起因（总收官审计 MAJOR-7）：多份文档写「R7 / R8 只能审**计划中的证据契约**」，
    但 `claims[].contract` 由 **R8** 建立，而 R8 排在 R7 **之后** ——
    首轮 R7 没有契约可审，`hypotheses[]` 也没有 contract 字段承载。
    该规则只能产出「待补」。首轮的攻击对象必须是 R3—R6 已落盘的三类对象。
    """

    ROOT = pathlib.Path(__file__).resolve().parent.parent
    DOCS = (
        "references/phase-r7-r10-r13-assurance-repair-review.md",
        "references/phase-r9-r11-experiment-loop.md",
        "SKILL.md",
        "references/research-state-policy.md",
    )

    def test_no_unbacked_planned_contract_phrase(self) -> None:
        for rel in self.DOCS:
            text = (self.ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("计划中的证据契约", text,
                             f"{rel} 仍要求审「计划中的证据契约」（无承载）")

    def test_r7_doc_names_the_first_pass_targets(self) -> None:
        text = (self.ROOT / "references" / "phase-r7-r10-r13-assurance-repair-review.md"
                ).read_text(encoding="utf-8")
        self.assertIn("首轮 R7 没有契约可审", text)
        for target in ("`claims[]`", "`hypotheses[]`", "`assumptions[]`"):
            self.assertIn(target, text, f"R7 文档未点名首轮攻击对象 {target}")

    def test_r7_read_set_includes_assumptions(self) -> None:
        # 攻击面 R-Theory 打的就是 tacit 假设；读集少了 assumptions 就自相矛盾。
        for rel in self.DOCS:
            text = (self.ROOT / rel).read_text(encoding="utf-8")
            row = next((line for line in text.splitlines()
                        if line.startswith("| **R7**") and "`claims`" in line), None)
            if row is None:
                continue
            self.assertIn("`assumptions`", row, f"{rel} 的 R7 读集缺 assumptions")


class TestExamplesFreeOfRetiredPipeline(unittest.TestCase):
    """`examples/` 是用户照抄的对象 —— 示例示范旧写法比正文陈旧更危险。

    起因：正文改完后，`examples/` 仍在走 B→C→D→E 并派遣「八子代理」，
    而且两个文件名本身编码了退役流水线（`example-b-to-c-d-e` / `example-a-standalone`）。
    正文扫描当时把 `examples/` 排除了，所以这一层一直没被检查。
    """

    ROOT = pathlib.Path(__file__).resolve().parent.parent
    RETIRED_WORDS = (
        "B→C", "C→D", "D→E", "八子代理", "七个子代理",
        "创新性研究", "可行性研究", "论文格式展开", "实验流程设计",
    )
    RETIRED_FILE_NAMES = ("example-b-to-c-d-e.md", "example-a-standalone.md")

    def test_examples_have_no_retired_pipeline_wording(self) -> None:
        offenders = []
        for path in sorted((self.ROOT / "examples").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            for word in self.RETIRED_WORDS:
                if word in text:
                    offenders.append(f"{path.name}: {word}")
        self.assertEqual(offenders, [], f"示例仍在示范退役流程：{offenders}")

    def test_no_example_file_name_encodes_retired_pipeline(self) -> None:
        names = {path.name for path in (self.ROOT / "examples").glob("*.md")}
        for bad in self.RETIRED_FILE_NAMES:
            self.assertNotIn(bad, names, f"示例文件名仍在编码退役流水线：{bad}")

    def test_every_example_is_registered_in_readme(self) -> None:
        readme = (self.ROOT / "README.md").read_text(encoding="utf-8")
        for path in sorted((self.ROOT / "examples").glob("*.md")):
            self.assertIn(path.name, readme, f"README 的示例清单未登记 {path.name}")


class TestCandidateBoundary(unittest.TestCase):
    """`P3` 只产 typed intermediate，不进 Research State（HIGH-2）。

    起因：`policy §5.0` 写「每个候选必须产出至少一条 `C`」，而「候选」没有定义 ——
    `P3` 的 `domain-free skeleton` 被默认当成候选，执行者于是被迫
    「把骨架包成 `H` + 造一条 `C`」，把表示探索提前变成可证伪假设。
    """

    ROOT = pathlib.Path(__file__).resolve().parent.parent

    def test_r3_doc_defines_candidate_and_excludes_p3(self) -> None:
        text = (self.ROOT / "references" / "phase-r3-r6-discovery.md").read_text(encoding="utf-8")
        self.assertIn("R3.0.1 什么才算 candidate", text)
        self.assertIn("不进 `hypotheses[]`、不产 `C`", text)
        self.assertIn("populations/intermediates/", text)
        self.assertIn("derived_from_intermediate", text)

    def test_policy_rule1_references_the_definition(self) -> None:
        text = (self.ROOT / "references" / "research-state-policy.md").read_text(encoding="utf-8")
        self.assertIn("每个 **candidate** 必须产出至少一条 `C`", text)
        self.assertIn("§R3.0.1", text)

    def test_no_doc_keeps_the_undefined_wording(self) -> None:
        for rel in ("SKILL.md", "references/research-state-policy.md",
                    "references/phase-r3-r6-discovery.md"):
            text = (self.ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("每个候选必须产出至少一条", text,
                             f"{rel} 仍在用未定义的「候选」")

    def test_project_layout_registers_the_intermediates_dir(self) -> None:
        text = (self.ROOT / "references" / "project-layout.md").read_text(encoding="utf-8")
        self.assertIn("populations/intermediates/", text)

    def test_skill_entry_states_the_p3_boundary(self) -> None:
        text = (self.ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`P3` 只产 typed intermediate，不产 candidate", text)

    def test_genealogy_stays_within_hypotheses(self) -> None:
        # `parents` 只引用 `H`：P3 的来源关系不得进 state 谱系
        self.assertNotIn("intermediates", sc.FIRST_CLASS_KEYS)
        self.assertNotIn("P3", sc.CANDIDATE_ISLANDS)


class TestPhaseDocNoLegacyFlow(unittest.TestCase):
    """迁移后的 phase 文档不得再含旧字母流程的**活跃**小节。

    起因：迁移只加 precedence note，旧 `B/C/E` 小节仍原地可执行 ——
    注释不是隔离。对 LLM 读者，留着就等于两套流程并存。

    已退役的内部小节号字母：`B`（旧 discovery 流程）、`C`（旧方案生成流程）、
    `E`（旧方案复核流程）。`A`（R2 / R5）与 `D`（R12）是**当前**命名，不在禁止之列。
    """

    ROOT = pathlib.Path(__file__).resolve().parent.parent
    R8 = "references/phase-r8-evidence-contract.md"
    LEGACY_FLOW_WORDS = ("创新性研究", "可行性研究", "论文格式展开", "实验流程设计")
    RETIRED_LETTERS = ("B", "C", "E")
    VENUE_ROLES = ("R-CVPR", "R-ICML", "R-NeurIPS", "R-MICCAI")

    def _phase_files(self):
        return sorted((self.ROOT / "references").glob("phase-*.md"))

    def test_r8_has_no_legacy_letter_headings(self) -> None:
        text = (self.ROOT / self.R8).read_text(encoding="utf-8")
        offenders = re.findall(r"^#{1,3}\s+C\d+[.．]", text, re.M)
        self.assertEqual(offenders, [], f"R8 文档仍含旧 C 级小节标题：{offenders}")

    def test_r8_has_no_legacy_flow_words(self) -> None:
        text = (self.ROOT / self.R8).read_text(encoding="utf-8")
        for word in self.LEGACY_FLOW_WORDS:
            self.assertNotIn(word, text, f"R8 文档仍含旧流程词：{word}")

    def test_no_retired_letter_headings_in_any_phase_doc(self) -> None:
        offenders = []
        for path in self._phase_files():
            for line in path.read_text(encoding="utf-8").splitlines():
                m = re.match(r"^#{1,3}\s+([A-Z])\d+[.．]", line)
                if m and m.group(1) in self.RETIRED_LETTERS:
                    offenders.append(f"{path.name}: {line.strip()}")
        self.assertEqual(offenders, [], f"phase 文档仍含退役字母小节标题：{offenders}")

    def test_no_retired_section_refs_in_skill(self) -> None:
        text = (self.ROOT / "SKILL.md").read_text(encoding="utf-8")
        for ref in ("§B0", "§B1", "§B5", "§C1", "§C4", "§E0", "§E2", "§E8"):
            self.assertNotIn(ref, text, f"SKILL.md 仍引用退役小节号 {ref}")

    def test_no_venue_role_is_dispatched_in_phase_docs(self) -> None:
        # 会议审稿人只在 R12 / R13 的 calibration 表里出现，不得成为任何阶段的派遣项。
        offenders = []
        for path in self._phase_files():
            for line in path.read_text(encoding="utf-8").splitlines():
                if any(role in line for role in self.VENUE_ROLES) and "●" in line:
                    offenders.append(f"{path.name}: {line.strip()[:70]}")
        self.assertEqual(offenders, [], f"phase 文档把会议审稿人列为派遣角色：{offenders}")

    def test_r8_deliverables_exclude_experiment_plan(self) -> None:
        # project-layout.md §2.2 把 experiment-plan.md 归 R9—R11。
        text = (self.ROOT / self.R8).read_text(encoding="utf-8")
        begin = text.index("## R8.4 交付物与落盘")
        end = text.index("## 读 / 写 World Model", begin)
        for line in text[begin:end].splitlines():
            if line.startswith("| **"):
                self.assertNotIn("NNN-experiment-plan.md", line,
                                 "experiment-plan.md 属于 R9—R11，不得出现在 R8 交付物表")

    def test_r8_states_contract_ownership_boundary(self) -> None:
        text = (self.ROOT / self.R8).read_text(encoding="utf-8")
        for phrase in ("不创建 claim", "不重做", "不要求 artifact"):
            self.assertIn(phrase, text, f"R8 文档缺少边界声明：{phrase}")


# ---------------------------------------------------------------------------
# V18—V21：状态失效传播 / 验证可信度层级 / 结果预注册
# ---------------------------------------------------------------------------

class _Wave5RuleTest(unittest.TestCase):
    """Wave 5 四条规则的共同夹具：单点变异 → 退出码 3 → 只报该规则。"""

    OBJ8 = ("claims", "evidence", "assumptions", "hypotheses",
            "experiments", "literature", "failures", "uncertainties")

    def _rules(self, doc: Dict[str, Any]):
        return sc.check_state(doc, source="<test>").rules()

    def _status(self, doc: Dict[str, Any]) -> int:
        return sc.check_state(doc, source="<test>").exit_code


class TestV18V19(_Wave5RuleTest):
    """V18（validity 三键）/ V19（一跳失效传播）—— Wave 5 状态失效传播。"""

    # ---- V18：validity 四键 ----

    def test_v18_validity_missing(self):
        doc = valid_state()
        del doc["claims"][0]["validity"]
        self.assertEqual(self._rules(doc), ["V18"])
        self.assertEqual(self._status(doc), sc.EXIT_HARD)

    def test_v18_status_out_of_enum(self):
        doc = valid_state()
        doc["claims"][0]["validity"]["status"] = "ok"
        self.assertEqual(self._rules(doc), ["V18"])

    def test_v18_reason_blank(self):
        doc = valid_state()
        doc["claims"][0]["validity"]["reason"] = "   "
        self.assertEqual(self._rules(doc), ["V18"])

    def test_v18_since_version_negative(self):
        doc = valid_state()
        doc["claims"][0]["validity"]["since_state_version"] = -1
        self.assertEqual(self._rules(doc), ["V18"])

    def test_v18_since_version_ahead_of_state_version(self):
        doc = valid_state()
        doc["claims"][0]["validity"]["since_state_version"] = 5
        self.assertEqual(self._rules(doc), ["V18"])

    def test_v18_assurance_is_exempt(self):
        """V18 只管八类一等对象：assurance / repairs 没有 validity 不算违规。"""
        doc = valid_state()
        for item in doc.get("assurance", []):
            item.pop("validity", None)
        for item in doc.get("repairs", []):
            item.pop("validity", None)
        self.assertNotIn("V18", self._rules(doc))

    # ---- V19：一跳传播 ----

    def test_v19_invalid_upstream_but_downstream_valid(self):
        doc = valid_state()
        doc["evidence"][0]["validity"]["status"] = "invalid"  # E32
        self.assertIn("V19", self._rules(doc))  # C17.depends_on 含 E32 且自身 valid

    def test_v19_downstream_stale_is_legal(self):
        doc = valid_state()
        doc["evidence"][0]["validity"]["status"] = "invalid"
        doc["claims"][0]["validity"]["status"] = "stale"
        self.assertNotIn("V19", self._rules(doc))

    def test_v19_dangling_depends_on(self):
        doc = valid_state()
        doc["claims"][1]["depends_on"] = ["E999"]
        self.assertIn("V19", self._rules(doc))

    def test_v19_empty_depends_on_is_legal(self):
        doc = valid_state()
        for key in self.OBJ8:
            for item in doc.get(key, []):
                item["depends_on"] = []
        self.assertNotIn("V19", self._rules(doc))

    def test_v19_does_not_iterate(self):
        """V19 只查一跳：X7(invalid) → E32 必须转 stale；但 C17 依赖的是 E32（stale），
        不得再被追着传染 —— 多跳是 R11 的责任，不是校验器的。"""
        doc = valid_state()
        for exp in doc["experiments"]:
            if exp["id"] == "X7":
                exp["validity"]["status"] = "invalid"
        # X7 的两个**直接**依赖者满足一跳；C17 依赖的是 E32（两跳），必须不被追着传染。
        doc["evidence"][0]["validity"]["status"] = "stale"   # E32 满足一跳
        doc["failures"][0]["validity"]["status"] = "stale"   # F3 满足一跳
        doc["claims"][0]["validity"]["status"] = "valid"     # C17 是两跳，合法
        self.assertNotIn("V19", self._rules(doc))

    def test_v19_one_hop_actually_fires(self):
        """同一构造，但 E32 仍写 valid —— 一跳必须报。"""
        doc = valid_state()
        for exp in doc["experiments"]:
            if exp["id"] == "X7":
                exp["validity"]["status"] = "invalid"
        doc["claims"][0]["validity"]["status"] = "valid"
        self.assertIn("V19", self._rules(doc))


class TestV20V21(_Wave5RuleTest):
    """V20（验证可信度阈值）/ V21（结果预注册）—— Wave 5 升级权限与防事后解释。"""

    # ---- V20：升级权限 ----

    def test_v20_supported_needs_t2(self):
        doc = valid_state()  # C17 = supported, E32 = T2
        doc["evidence"][0]["verification_tier"] = "T1"
        self.assertIn("V20", self._rules(doc))

    def test_v20_supported_with_t2_is_legal(self):
        self.assertNotIn("V20", self._rules(valid_state()))

    def test_v20_partially_supported_with_t1_is_legal(self):
        doc = valid_state()
        doc["claims"][0]["status"] = "partially-supported"
        doc["evidence"][0]["verification_tier"] = "T1"
        self.assertNotIn("V20", self._rules(doc))

    def test_v20_partially_supported_with_t0_is_violation(self):
        doc = valid_state()
        doc["claims"][0]["status"] = "partially-supported"
        doc["evidence"][0]["verification_tier"] = "T0"
        self.assertIn("V20", self._rules(doc))

    def test_v20_missing_tier_is_violation(self):
        doc = valid_state()
        del doc["evidence"][0]["verification_tier"]
        self.assertIn("V20", self._rules(doc))

    def test_v20_ungrounded_is_not_checked(self):
        doc = valid_state()
        doc["claims"][0].update(status="ungrounded", supporting_evidence=[])
        self.assertNotIn("V20", self._rules(doc))

    def test_v20_llm_tier_t0_cannot_upgrade(self):
        """T0 = LLM 自评上限：即便证据 tier 齐全，T0 也不得支撑 supported。"""
        doc = valid_state()
        doc["evidence"][0]["verification_tier"] = "T0"
        self.assertIn("V20", self._rules(doc))

    # ---- V21：结果预注册 ----

    def test_v21_done_without_preregistration(self):
        doc = valid_state()
        for exp in doc["experiments"]:
            if exp["status"] == "done":
                exp["preregistration"] = None
        self.assertIn("V21", self._rules(doc))

    def test_v21_done_frozen_after_result(self):
        doc = valid_state()
        for exp in doc["experiments"]:
            if exp["status"] == "done":
                exp["result_at_state_version"] = 0
                exp["preregistration"]["frozen_at_state_version"] = 3
        self.assertIn("V21", self._rules(doc))

    def test_v21_running_needs_preregistration_only(self):
        doc = valid_state()
        for exp in doc["experiments"]:
            if exp["status"] == "done":
                exp["status"] = "running"
                exp["result_at_state_version"] = None
        self.assertNotIn("V21", self._rules(doc))

    def test_v21_planned_is_not_checked(self):
        self.assertNotIn("V21", self._rules(valid_state()))  # X8 = planned

    def test_v21_bad_op_is_violation(self):
        doc = valid_state()
        for exp in doc["experiments"]:
            if exp.get("preregistration"):
                exp["preregistration"]["outcomes"][0]["update"][0]["op"] = "improve"
        self.assertIn("V21", self._rules(doc))

    def test_v21_done_with_frozen_equal_result_is_legal(self):
        doc = valid_state()
        for exp in doc["experiments"]:
            if exp["status"] == "done":
                exp["preregistration"]["frozen_at_state_version"] = 0
                exp["result_at_state_version"] = 0
        self.assertNotIn("V21", self._rules(doc))


# ---------------------------------------------------------------------------
# Carrier Completeness：读写表授权写入的字段，必须在 schema/模板里真的有位置
# ---------------------------------------------------------------------------

class TestCarrierCompleteness(unittest.TestCase):
    """Producer → Carrier → Consumer。

    静态一致性检查只能保证"文档之间不打架"，抓不到**「文档授权写一个不存在的位置」**
    —— 那会让执行者被迫违反 policy §3「未在本节出现的字段 = 未定义字段」。
    本类把这条判据机械化：**读/写表里出现的每个 `X[].field`，模板必须有对应的键。**
    """

    ROOT = pathlib.Path(__file__).resolve().parent.parent

    OBJ = ("claims", "evidence", "assumptions", "hypotheses", "experiments",
           "literature", "failures", "uncertainties", "assurance", "repairs")
    PATTERN = re.compile(
        r"`(" + "|".join(OBJ) + r")\[\]\."
        r"([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)`"
    )

    def _template(self) -> Dict[str, Any]:
        path = self.ROOT / "templates" / "research-state.template.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_table_fields(self) -> Dict[str, set]:
        files = [self.ROOT / "references" / "research-state-policy.md"]
        files += sorted((self.ROOT / "references").glob("phase-*.md"))
        found: Dict[str, set] = {}
        for path in files:
            for match in self.PATTERN.finditer(path.read_text(encoding="utf-8")):
                found.setdefault(match.group(1), set()).add(match.group(2))
        return found

    def test_every_write_table_field_has_a_carrier(self):
        template = self._template()
        missing: List[str] = []
        for obj, fields in sorted(self._write_table_fields().items()):
            entries = template.get(obj)
            if not isinstance(entries, list) or not entries:
                missing.append(f"{obj}[]：模板没有样例条目，无法承载任何字段")
                continue
            sample = entries[0]
            for field in sorted(fields):
                head = field.split(".")[0]
                if head not in sample:
                    missing.append(f"{obj}[].{field}：写表要求它，模板条目却没有这个键")
        self.assertEqual(
            missing, [],
            msg="Carrier 缺口（写表授权了一个不存在的位置）：\n  " + "\n  ".join(missing),
        )

    def test_check_is_not_vacuous(self):
        """防空转：确认确实抽到了字段（否则上面的断言恒真）。"""
        self.assertGreaterEqual(
            sum(len(v) for v in self._write_table_fields().values()), 20,
            "应从读写表抽出 ≥20 个字段引用；数量骤降说明正则或文档结构变了",
        )

    def test_template_top_level_keys_are_all_documented(self):
        """模板的每个顶层键都要在 policy §3 里有定义（反向 carrier 检查）。"""
        template = self._template()
        policy = (self.ROOT / "references" / "research-state-policy.md").read_text(encoding="utf-8")
        undocumented = [
            key for key in template
            if not key.startswith("_") and f"`{key}`" not in policy and f"`{key}[]`" not in policy
        ]
        self.assertEqual(undocumented, [], msg=f"模板有但 policy §3 未定义的顶层键：{undocumented}")


# ---------------------------------------------------------------------------
# 打包完整性：相对链接不得指向 skill 包之外
# ---------------------------------------------------------------------------

class TestPackagedLinks(unittest.TestCase):
    """本 skill 会被整包拷到 `~/.agents/skills/` 等安装点使用。

    因此**任何指向包外的相对链接，在安装态必然断** —— 而在开发树里它可能恰好可达
    （`research-idea-pipeline-dev/docs/` 就在旁边），于是开发期的链接检查**是绿的**。
    这类缺陷只在「装出去」那一刻暴露，必须机械化拦住。

    规则：每个 `*.md` 里的相对链接，解析后必须 ① 存在，② 仍在 skill 根目录内。
    """

    ROOT = pathlib.Path(__file__).resolve().parent.parent
    FENCE = re.compile(r"```.*?```", re.S)
    LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")

    def _links(self):
        for path in sorted(self.ROOT.rglob("*.md")):
            text = self.FENCE.sub("", path.read_text(encoding="utf-8"))
            for match in self.LINK.finditer(text):
                target = match.group(1).split("#")[0]
                if not target or target.startswith(("http", "mailto:", "<", "{")):
                    continue
                yield path, target

    def test_relative_links_stay_inside_the_package(self):
        root = self.ROOT.resolve()
        outside, missing = [], []
        for path, target in self._links():
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                missing.append(f"{path.relative_to(root)} -> {target}")
            elif root not in resolved.parents and resolved != root:
                outside.append(f"{path.relative_to(root)} -> {target}")
        self.assertEqual(missing, [], msg="断链（相对链接目标不存在）：\n  " + "\n  ".join(missing))
        self.assertEqual(
            outside, [],
            msg="链接指向 skill 包之外 —— 安装后必然断裂，请改为代码体或包内路径：\n  "
                + "\n  ".join(outside),
        )

    def test_link_scan_is_not_vacuous(self):
        self.assertGreaterEqual(len(list(self._links())), 200, "链接扫描数量骤降，正则或目录结构可能变了")


# ---------------------------------------------------------------------------
# frontmatter 完整性：发现能力不得被静默削弱
# ---------------------------------------------------------------------------

class TestSkillFrontmatter(unittest.TestCase):
    """`SKILL.md` 的 frontmatter 是 `npx skills` 的**发现入口**。

    曾经发生过一次回归：架构迁移把 `argument-hint`、`metadata.version` 与
    整串触发关键词一起弄丢了——**skill 仍然能跑，但被"找到"的概率大幅下降**，
    而这在功能测试里完全看不出来。本类把该契约机械化。
    """

    ROOT = pathlib.Path(__file__).resolve().parent.parent

    def _frontmatter(self) -> str:
        text = (self.ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"), "SKILL.md 必须以 frontmatter 开头")
        end = text.index("\n---\n", 3)
        return text[3:end]

    def test_required_keys_present(self):
        fm = self._frontmatter()
        for key in ("name:", "description:", "argument-hint:", "metadata:", "version:"):
            self.assertIn(key, fm, msg=f"frontmatter 缺少 {key}")

    def test_name_matches_directory(self):
        fm = self._frontmatter()
        self.assertIn(f"name: {self.ROOT.name}", fm, "name 必须与 skill 目录名一致")

    def test_version_is_semver_quoted(self):
        fm = self._frontmatter()
        match = re.search(r'version:\s*"([0-9]+\.[0-9]+\.[0-9]+)"', fm)
        self.assertIsNotNone(match, "metadata.version 必须是被引号包住的 X.Y.Z")

    def test_argument_hint_points_at_phase_not_mode(self):
        fm = self._frontmatter()
        self.assertIn("phase=", fm, "argument-hint 必须用 phase= 入口")
        self.assertNotIn("mode=", fm, "不得再出现已退役的 mode= 入口")

    def test_trigger_keywords_are_retained(self):
        """触发词是发现能力的实质；数量骤降说明有人把描述改瘦了。"""
        fm = self._frontmatter()
        match = re.search(r"Triggers:(.*?)\nargument-hint:", fm, re.S)
        self.assertIsNotNone(match, "description 必须含 Triggers: 段落")
        raw = match.group(1)
        keywords = [x.strip() for x in re.split(r"[,\n]", raw) if x.strip()]
        self.assertGreaterEqual(len(keywords), 40, f"触发词只有 {len(keywords)} 个，疑似被削减")
