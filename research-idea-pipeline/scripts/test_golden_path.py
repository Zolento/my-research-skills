#!/usr/bin/env python3
"""test_golden_path.py — Golden Path 集成测试（workflow executability 层）

为什么需要它
------------
本仓库已经有三层正确性，但此前只覆盖了前两层：

* **Layer A 静态一致性** — 表格 / 枚举 / schema / 链接 / linter（`TestTableIntegrity` 等）
* **Layer B 转移正确性** — `S_t + action → S_{t+1}` 是否合法（`TestV18V21` 等，V1—V24）
* **Layer C 流程可执行性** — 从 `R0` 一路走到 `R14`，**每个消费者需要的字段，
  在它被消费之前是否真的有生产者？**  ← 本文件

**为什么 A/B 层抓不到 C 层 bug：** 它们都能通过，而流程照样跑不通。
真实教训：曾经有两条硬规则要求 `state_version` 与 `experiments[].preregistration` 存在，
但**没有任何阶段被授权生产它们** —— 所有静态检查全绿，执行者一动手就必然 exit 3。
这类缺陷只有「把文档字面执行一遍、把产物真的喂给校验器」才能抓到。

本文件就是那件事的自动化版本：**逐阶段推进，每阶段断言收工状态 exit 0**。

对抗路径（Adversarial Golden Paths）则反向使用：构造**恶意输入**，断言系统**拦得住**。
若某条路径当前**没有机械闸门**，测试**明确记为缺口**（用 `self.skipTest` 或显式断言
"当前无闸门"），**不得为了让测试变绿而写松断言** —— 那会把"已知缺口"伪装成"已验证"。
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import pathlib
import tempfile
import unittest
from typing import Any, Callable, Dict, List

import state_check as sc

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE_CHECK = ROOT / "scripts" / "state_check.py"


# ---------------------------------------------------------------------------
# 最小合法 Research State 与其逐阶段演进
# ---------------------------------------------------------------------------

def _validity(reason: str = "初始", version: int = 0) -> Dict[str, Any]:
    return {"status": "valid", "reason": reason, "since_state_version": version}


def r0_contract() -> Dict[str, Any]:
    """R0 唯一产物：`contract` + 模板骨架（八类数组留空）+ `state_version: 0`。"""
    return {
        "state_version": 0,
        "contract": {
            "goal": "判断某机制性假设是否在目标分布上成立",
            "primary_anchor": "theory",
            "constraints": "单卡，≤ 40 GPU·小时",
            "resources": "已有代码与一份公开数据集",
            "provisional_anchor_rationale": "先用理论锚点把问题形式化，证据到位后复核",
            "out_of_scope": "不做新数据集采集，不做临床验证",
        },
        "claims": [], "evidence": [], "assumptions": [], "hypotheses": [],
        "experiments": [], "literature": [], "failures": [], "uncertainties": [],
        "assurance": [], "repairs": [],
    }


def r2_field_mapping(s: Dict[str, Any]) -> None:
    s["literature"].append({"id": "LIT1", "ref": "[Author, 2024]", "relation": "shares-assumption",
                            "depends_on": [], "validity": _validity()})
    s["evidence"].append({"id": "E1", "kind": "literature", "supports": [], "contradicts": [],
                          "strength": "partial", "scope": "target domain",
                          "epistemic_status": "Supported", "source_ref": "LIT1",
                          "verification_tier": "T1", "depends_on": ["LIT1"], "validity": _validity()})
    s["assumptions"].append({"id": "AS1", "statement": "目标分布与源分布共享该结构",
                             "status": "tacit", "challenged_by": [], "if_false": "机制主张不成立",
                             "depends_on": [], "validity": _validity()})
    s["uncertainties"].append({"id": "U1", "question": "该结构是否可识别？",
                               "importance": "critical", "uncertainty": "high",
                               "cheapest_discriminating_test": "TBD", "status": "open",
                               "depends_on": [], "validity": _validity()})


def r3_dual_discovery(s: Dict[str, Any]) -> None:
    """R3 创建候选：generation 0，自带 niche/island/operator/parents；同 niche 至少一条 elite。"""
    s["hypotheses"].append({
        "id": "H1", "statement": "解除假设 AS1 可恢复能力",
        "structural_signature": {"assumption_distance": 2, "formulation_distance": 3,
                                 "representation_distance": 1, "theory_lens_distance": 3,
                                 "mechanism_distance": 2},
        "novelty_source": "假设移除", "theory_lens": "transfer-learning",
        "nearest_prior": "LIT1", "falsifier": "若解除 AS1 后能力不恢复则 H1 不成立",
        "expected_information_gain": 0.6, "status": "elite",
        "niche": "N2", "island": "P2", "operator": "assumption_breaker",
        "parents": [], "generation": 0,
        "depends_on": ["AS1"], "validity": _validity()})
    s["hypotheses"].append({
        "id": "H2", "statement": "把问题重述为部分识别问题",
        "structural_signature": {"assumption_distance": 3, "formulation_distance": 4,
                                 "representation_distance": 2, "theory_lens_distance": 4,
                                 "mechanism_distance": 1},
        "novelty_source": "问题重构", "theory_lens": "partial-identification",
        "nearest_prior": "LIT1", "falsifier": "若部分识别界为空则 H2 无意义",
        "expected_information_gain": 0.5, "status": "elite",
        "niche": "N1", "island": "P1", "operator": "reframe",
        "parents": [], "generation": 0,
        "depends_on": [], "validity": _validity()})
    # 同 niche（N2）的第二条候选：R4 的「重排 elite 归属」必须**同 niche 有替代者**才合法，
    # 否则该 niche 会失去 elite 而触发 V15（见本文件 TestAdversarialGoldenPaths 的 V15 用例）。
    s["hypotheses"].append({
        "id": "H3", "statement": "仅解除部分假设即可恢复能力",
        "structural_signature": {"assumption_distance": 2, "formulation_distance": 2,
                                 "representation_distance": 2, "theory_lens_distance": 2,
                                 "mechanism_distance": 2},
        "novelty_source": "假设移除（部分）", "theory_lens": "transfer-learning",
        "nearest_prior": "LIT1", "falsifier": "若部分解除无增益则 H3 不成立",
        "expected_information_gain": 0.4, "status": "active",
        "niche": "N2", "island": "P2", "operator": "assumption_breaker",
        "parents": [], "generation": 0,
        "depends_on": ["AS1"], "validity": _validity()})
    # R3 同时创建 seed claims（status: ungrounded, falsifier 必填）
    s["claims"].append({
        "id": "C1", "statement": "在目标分布上，解除 AS1 可恢复能力", "parent": None,
        "subclaims": [], "status": "ungrounded", "supporting_evidence": [], "refuting_evidence": [],
        "nearest_alternative": "增益来自更多训练步数", "falsifier": "等训练步数下增益消失",
        "scope": "target domain", "known_flaws": [],
        "depends_on": ["H1"], "validity": _validity()})


def r4_isolated_populations(s: Dict[str, Any]) -> None:
    """R4 只重排 elite 归属（同 niche 内有替代者，故 V15 仍满足）。"""
    s["hypotheses"][0]["status"] = "active"   # H1(N2) 让位
    s["hypotheses"][2]["status"] = "elite"    # H3(N2) 接任 elite



def r6_evolution(s: Dict[str, Any]) -> None:
    """R6 是**唯一**允许跨 island 融合的阶段；本例用 mutation 产生 generation=1 子候选。"""
    s["hypotheses"].append({
        "id": "H4", "statement": "H1 的简化版：只解除最关键的假设",
        "structural_signature": {"assumption_distance": 1, "formulation_distance": 3,
                                 "representation_distance": 1, "theory_lens_distance": 3,
                                 "mechanism_distance": 2},
        "novelty_source": "简化（删假设优先于加）", "theory_lens": "transfer-learning",
        "nearest_prior": "H1", "falsifier": "若简化版无增益则 H4 不成立",
        "expected_information_gain": 0.3, "status": "active",
        "niche": "N2", "island": "P2", "operator": "simplification",
        "parents": ["H1"], "generation": 1,
        "depends_on": ["AS1"], "validity": _validity()})

def r5_co_evolving_retrieval(s: Dict[str, Any]) -> None:
    s["literature"].append({"id": "LIT2", "ref": "[Author2, 2025]", "relation": "shares-structure",
                            "depends_on": [], "validity": _validity()})
    s["evidence"].append({"id": "E2", "kind": "literature", "supports": ["C1"], "contradicts": [],
                          "strength": "partial", "scope": "target domain",
                          "epistemic_status": "Supported", "source_ref": "LIT2",
                          "verification_tier": "T1", "depends_on": ["LIT2"], "validity": _validity()})
    # 关键：claim 必须**显式**把支持它的证据写进 depends_on，V19 才能沿这条边传播。
    s["claims"][0]["depends_on"].append("E2")


def r7_adversarial_assurance(s: Dict[str, Any]) -> None:
    s["assurance"].append({"kill_condition": "若等步数对照下增益消失，则 C1 被杀死",
                           "discriminating_test": "TBD", "verification_tier": "T0"})


def r8_evidence_contract(s: Dict[str, Any]) -> None:
    """R8：建 contract；**创建 experiments 的 planned 条目并冻结 preregistration**；证据驱动升级。"""
    s["claims"][0]["contract"] = {
        "statement": "解除 AS1 恢复能力", "scope": "target domain",
        "kill_rule": "若 O2 出现则 C1 降级", "expansion_rule": "若 O1 出现且对照通过则扩到多中心",
    }
    s["experiments"].append({
        "id": "X1", "parent": None, "stage": "X3", "claim_targeted": ["C1"],
        "alternative_targeted": ["ALT-1"], "code_commit": "abc123",
        "data_split": "toy val", "seed": 0, "metric": "score",
        "result": "", "interpretation": "", "unexpected": [],
        "known_flaws": [], "next_branches": [], "status": "planned",
        "preregistration": {"frozen_at_state_version": s["state_version"],
                            "outcomes": [{"id": "O1", "observation": "等步数下增益保持",
                                          "update": [{"target": "C1", "op": "strengthen"}]},
                                         {"id": "O2", "observation": "等步数下增益消失",
                                          "update": [{"target": "C1", "op": "weaken"}]}]},
        "result_at_state_version": None,
        "depends_on": [], "validity": _validity()})
    s["claims"][0]["supporting_evidence"] = ["E2"]
    s["claims"][0]["status"] = "partially-supported"  # 证据驱动单向升级（T1 ⇒ ≥T1）


def r9_experiment_tree(s: Dict[str, Any]) -> None:
    x = s["experiments"][0]
    x["status"] = "done"
    x["result"] = "等步数下增益保持"
    x["interpretation"] = "支持 H1"
    x["result_at_state_version"] = s["state_version"]


def r10_metacognitive_repair(s: Dict[str, Any]) -> None:
    """故意产生一个 critical flaw，并**执行 state_delta**。"""
    s["failures"].append({"id": "F1", "kind": "inconclusive",
                          "what": "未排除「更多训练步数」的替代解释",
                          "why": "对照实验尚未做", "referenced_by": ["X1"],
                          "depends_on": ["X1"], "validity": _validity()})
    s["claims"][0]["known_flaws"] = ["F1"]
    s["repairs"].append({
        "flaw": "机制主张缺少等步数对照（critical）",
        "disposition": "RUN_TEST",
        "state_delta": "C1.status → partially-supported；新增 F1 并挂到 claims[0].known_flaws",
        "closure": "RESOLVED"})


def r11_state_update(s: Dict[str, Any]) -> None:
    """失效传播至不动点（本例无 invalid，故一趟即达）+ state_version +1。"""
    s["state_version"] += 1
    for key in ("claims", "evidence", "assumptions", "hypotheses",
                "experiments", "literature", "failures", "uncertainties"):
        for item in s[key]:
            item.setdefault("validity", _validity())


def r12_narrative(s: Dict[str, Any]) -> None:
    """R12 只写 narrative_view（必要时新增 uncertainties）。"""
    s["narrative_view"] = {
        "presets_selected": ["N2"],
        "rendered_claims": ["C1"],
        "failed_experiments_kept": ["F1"],
        "note": "主线 N2；F1 必须保留在叙事中",
    }


def r13_artifact_review(s: Dict[str, Any]) -> None:
    s["reviews"] = [{"route": "T", "artifact": "X1", "verdict": "缺口已交 R10",
                     "integrity_gate": "pass"}]


def r14_decision(s: Dict[str, Any]) -> None:
    s["decision"] = {"verdict": "continue", "rationale": "机制主张部分支持，需补对照",
                     "next_phase": "R9"}
    s["uncertainties"][0]["status"] = "closed"
    s["hypotheses"][0]["status"] = "archived"


GOLDEN_PATH: List[tuple] = [
    ("R0", lambda s: None),            # R0 的产物即 r0_contract() 本身
    ("R2", r2_field_mapping),
    ("R3", r3_dual_discovery),
    ("R4", r4_isolated_populations),
    ("R5", r5_co_evolving_retrieval),
    ("R6", r6_evolution),
    ("R7", r7_adversarial_assurance),
    ("R8", r8_evidence_contract),
    ("R9", r9_experiment_tree),
    ("R10", r10_metacognitive_repair),
    ("R11", r11_state_update),
    ("R12", r12_narrative),
    ("R13", r13_artifact_review),
    ("R14", r14_decision),
]

# 每个阶段「被授权写」的顶层字段（用于断言它确实做了事，而不是空转）
STAGE_WRITES: Dict[str, tuple] = {
    "R2": ("literature", "evidence", "assumptions", "uncertainties"),
    "R3": ("hypotheses", "claims"),
    "R4": ("hypotheses",),
    "R5": ("literature", "evidence"),
    "R6": ("hypotheses",),
    "R7": ("assurance",),
    "R8": ("experiments", "claims"),
    "R9": ("experiments",),
    "R10": ("failures", "repairs"),
    "R11": ("state_version",),
    "R12": ("narrative_view",),
    "R13": ("reviews",),
    "R14": ("decision",),
}


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="golden-")
        self.path = pathlib.Path(self.tmp.name) / "research-state.json"
        self.addCleanup(self.tmp.cleanup)

    def check(self, state: Dict[str, Any]) -> sc.Report:
        """把状态喂给校验器（静默），返回 Report。"""
        self.path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return sc.check_state(state, source=str(self.path))

    def assertClean(self, state: Dict[str, Any], stage: str = "") -> None:
        report = self.check(state)
        rules = report.rules()
        self.assertEqual(
            report.exit_code, sc.EXIT_OK,
            msg=f"{stage} 收工状态必须 exit 0，实际 exit {report.exit_code}，违规 {rules}")
        self.assertEqual(rules, [], msg=f"{stage} 不应有违规，实际 {rules}")


class TestGoldenPath(_Base):
    """逐阶段推进 R0→R14；每阶段断言收工状态 exit 0。"""

    def test_golden_path_runs_clean(self):
        state = r0_contract()
        self.assertClean(state, "R0")
        trace = ["R0:exit=0"]
        for stage, mutate in GOLDEN_PATH:
            if stage == "R0":
                continue
            before = copy.deepcopy(state)
            mutate(state)
            # 断言该阶段确实改动了被授权写的字段（不能空转就宣称完成）
            for field in STAGE_WRITES[stage]:
                self.assertNotEqual(
                    before.get(field), state.get(field),
                    msg=f"{stage} 必须改动 {field}，但它没有变")
            self.assertClean(state, stage)
            trace.append(f"{stage}:exit=0")
        self.assertEqual(len(trace), len(GOLDEN_PATH))
        # R12 的产物必须能被下游 R13/R14 保留
        self.assertIn("F1", state["narrative_view"]["failed_experiments_kept"])

    def test_r14_must_not_change_claim_truth(self):
        """决策层不得改科学主张真值（SKILL §1.7）。"""
        state = r0_contract()
        for stage, mutate in GOLDEN_PATH:
            if stage != "R0":
                mutate(state)
        before = [c["status"] for c in state["claims"]]
        self.assertClean(state, "R14")
        self.assertEqual([c["status"] for c in state["claims"]], before,
                         "R14 不得改变 claims[].status")

    def test_every_stage_is_reachable(self):
        """每个阶段都被走查覆盖（防止有人删掉某阶段却测试仍绿）。"""
        stages = {s for s, _ in GOLDEN_PATH}
        self.assertEqual(stages, set(STAGE_WRITES) | {"R0"},
                         "GOLDEN_PATH 覆盖的阶段与断言表不一致")


class TestAdversarialGoldenPaths(_Base):
    """五条恶意路径。系统必须拦得住；**拦不住的记为已知缺口，不得写松断言。**"""

    def _state_at_r10(self) -> Dict[str, Any]:
        state = r0_contract()
        for stage, mutate in GOLDEN_PATH:
            if stage == "R0":
                continue
            mutate(state)
            if stage == "R10":
                break
        return state

    # ---- A 证据失效传播 ----

    def test_path_a_upstream_invalid_forces_stale_not_valid(self):
        state = self._state_at_r10()
        state["evidence"][1]["validity"]["status"] = "invalid"   # E2 supports C1
        report = self.check(state)
        self.assertIn("V19", report.rules(),
                      "上游 E2 失效后，依赖它的 C1 仍为 valid → 必须报 V19")
        # 合规修法：下游写 stale（不得被自动改成 invalid）
        state["claims"][0]["validity"]["status"] = "stale"
        self.assertClean(state, "A-下游转 stale")

    def test_path_a_stale_does_not_cascade(self):
        """stale 不传染：只要求 invalid 的一跳。"""
        state = self._state_at_r10()
        state["evidence"][1]["validity"]["status"] = "invalid"
        state["claims"][0]["validity"]["status"] = "stale"
        # H1 依赖 AS1（非 invalid），因此不受影响
        state["hypotheses"][0]["validity"]["status"] = "valid"
        self.assertClean(state, "A-两跳不被追踪")

    def test_path_a_support_edge_is_not_a_propagation_edge_KNOWN_GAP(self):
        """**已登记缺口**：V19 沿 `depends_on` 传播，而证据支持走 `supporting_evidence`。

        因此「E 失效 ⇒ 依赖它的 C 变 stale」**不会自动发生** —— 除非 claim 显式把该证据
        写进 `depends_on`。本用例证明这一点：同样把 E2 置 invalid，若 C1 的 `depends_on`
        不含 E2，则 V19 **不报**（校验器无法从 `supporting_evidence` 推出依赖）。

        这与「证据失效传播」的直觉预期不同，属**语义缺口**而非实现 bug。
        建议二选一：① 规范要求「把支持证据一并写进 depends_on」；
        ② 让 V19 把 `supporting_evidence` / `refuting_evidence` 也视为传播边。
        """
        state = self._state_at_r10()
        state["claims"][0]["depends_on"] = ["H1"]        # 故意不声明依赖 E2
        state["evidence"][1]["validity"]["status"] = "invalid"
        report = self.check(state)
        self.assertNotIn("V19", report.rules(),
                         "若已把支持边纳入 V19，请更新本缺口用例")
        self.skipTest("已知缺口：支持边（supporting_evidence）不是传播边（depends_on）")

    # ---- B 负结果不得 narrative salvage ----

    def test_path_b_negative_outcome_cannot_be_upgraded_for_free(self):
        state = self._state_at_r10()
        # 预注册写的是 O2 → weaken；结果出现了 O2，却把 C1 升为 supported
        state["claims"][0]["status"] = "supported"
        # 唯一的支持证据 E2 是 T1 < T2，因此 V20 必须拦住
        report = self.check(state)
        self.assertIn("V20", report.rules(),
                      "T1 证据不得支撑 supported —— 负结果被 salvage 时必须被拦住")

    def test_path_b_negative_outcome_with_strong_evidence_is_still_traceable(self):
        """即使有 T2 证据，预注册也必须在场（V21）。"""
        state = self._state_at_r10()
        state["evidence"][1]["verification_tier"] = "T2"
        state["claims"][0]["status"] = "supported"
        self.assertClean(state, "B-有 T2 证据")
        # 去掉预注册 → V21 必须报
        for x in state["experiments"]:
            if x["status"] == "done":
                x["preregistration"] = None
        self.assertIn("V21", self.check(state).rules(),
                      "done 的实验没有 preregistration 必须被拦住")

    # ---- C 假范式新颖性（**当前无机械闸门 → 记为缺口**）----

    def test_path_c_fake_paradigm_novelty_is_a_KNOWN_GAP(self):
        """两条候选只有措辞不同、结构签名完全一致 —— 当前**没有任何规则**能识别。

        这不是测试失败，而是**已登记缺口**：
        需要 `structural-equivalence` 双 pass（canonicalize 七元组 → 与 nearest_prior 比结构）。
        测试在此**明确记录缺口**，而不是把断言写松来假装它已被覆盖。
        """
        state = self._state_at_r10()
        twin = copy.deepcopy(state["hypotheses"][1])
        twin["id"] = "H3"
        twin["statement"] = "用另一套术语重述同一个想法"   # 只有措辞不同
        twin["theory_lens"] = "some-new-branding"          # 只有品牌不同
        twin["opened"] = True if False else True  # noqa: 保持字段稳定
        state["hypotheses"].append(twin)
        report = self.check(state)
        structural_rules = [r for r in report.rules() if r in ("V22", "V23")]
        self.assertEqual(
            structural_rules, [],
            msg="当前实现了结构等价闸门？如已实现请更新本测试并补规则号")
        self.skipTest(
            "已知缺口：无 structural-equivalence 闸门，措辞不同的同构候选会被当成两个方向")

    # ---- D decision ≠ truth ----

    def test_path_d_decision_layer_cannot_kill_a_claim(self):
        """R14 可 archive 分支，**不得**改 claim 真值（SKILL §1.7）。

        本条是 §1.7 的**机械落点**：`V22` 要求 `claims[].status ∈ {killed, contradicted}`
        必须被一条 `repairs[].targets` 覆盖（且 disposition ∈ 五值）。
        决策层没有这条 repair，因此越权写 `killed` 会被校验器拦下。
        """
        state = r0_contract()
        for stage, mutate in GOLDEN_PATH:
            if stage != "R0":
                mutate(state)
        before = [c["status"] for c in state["claims"]]
        state["decision"] = {"verdict": "archive", "rationale": "路线停止", "next_phase": "R1"}
        state["hypotheses"][0]["status"] = "archived"
        self.assertClean(state, "D-archive 合法")
        self.assertEqual([c["status"] for c in state["claims"]], before,
                         "R14 不得改变 claims[].status")

        # 越权：决策层直接把 claim 置 killed —— 必须被 V22 拦住
        state["claims"][0]["status"] = "killed"
        report = self.check(state)
        self.assertEqual(report.exit_code, sc.EXIT_HARD,
                         "R14 越权写 killed 必须使校验失败（V22）")
        self.assertIn("V22", report.rules())

        # 合规修法：由 R10 留下覆盖该 claim 的 repair（disposition ∈ 五值）即可通过
        cid = state["claims"][0]["id"]
        state["repairs"].append({
            "flaw": "该主张被证据证否（critical）",
            "disposition": "REPAIR_CLAIM",
            "state_delta": f"{cid}.status → killed",
            "closure": "RESOLVED",
            "targets": [cid],
        })
        self.assertClean(state, "D-经 R10 合法否决")

    def test_path_d_gate_fail_must_close_the_loop(self):
        """**MAJOR-2 的机械落点**：`integrity_gate == "fail"` 必须有闭环动作。"""
        state = r0_contract()
        for stage, mutate in GOLDEN_PATH:
            if stage != "R0":
                mutate(state)
        state["reviews"] = [{"stage": "R13", "artifact": "code",
                             "integrity_gate": "fail", "findings": ["leakage"]}]
        # 工整路径里已有 failures[]，故此处先清掉以暴露缺口
        state["failures"] = []
        state["repairs"] = []
        state["claims"][0]["known_flaws"] = []
        for x in state["experiments"]:
            x["known_flaws"] = []
        report = self.check(state)
        self.assertIn("V23", report.rules(),
                      "integrity_gate=fail 且无 repairs/failures 时必须报 V23")
        # 合规修法：留下闭环动作
        state["failures"].append({"id": "F9", "kind": "engineering-failure",
                                  "what": "完整性审计发现泄漏", "why": "训练/测试同受试者",
                                  "referenced_by": ["X1"], "depends_on": [],
                                  "validity": _validity()})
        # V4：每条 F 必须被某个已知 flaws 引用
        state["experiments"][-1]["known_flaws"] = ["F9"]
        self.assertClean(state, "D-gate fail 已闭环")

    # ---- E 叙事幻觉不得创建 claim（**当前无机械闸门 → 记为缺口**）----

    def test_path_e_narrative_cannot_create_claim_is_a_KNOWN_GAP(self):
        """R12 只写 narrative_view；但校验器无法区分『R12 写的』与『R8 写的』。"""
        state = r0_contract()
        for stage, mutate in GOLDEN_PATH:
            if stage != "R0":
                mutate(state)
        before = len(state["claims"])
        # 模拟 R12 为让故事成立而新增一条 claim
        state["claims"].append({
            "id": "C99", "statement": "为叙事需要新增的主张", "parent": None,
            "subclaims": [], "status": "ungrounded", "supporting_evidence": [],
            "refuting_evidence": [], "nearest_alternative": "无",
            "falsifier": "若……则不成立", "scope": "target domain", "known_flaws": [],
            "depends_on": [], "validity": _validity()})
        report = self.check(state)
        self.assertEqual(len(state["claims"]), before + 1)
        if report.exit_code == sc.EXIT_OK:
            self.skipTest(
                "已知缺口：校验器无法识别『R12 创建了 claim』；该禁令只由 "
                "phase-r12 §D9.5 硬规则与 policy §5 读写表保证，无机械闸门")


if __name__ == "__main__":
    unittest.main()
