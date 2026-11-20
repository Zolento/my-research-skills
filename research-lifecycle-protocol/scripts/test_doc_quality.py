#!/usr/bin/env python3
"""test_doc_quality.py — 文档质量检查器的回归测试。

真实素材来自 route F 的 15 份文档（F000—F015）。这里不复制那 477 KB，而是按它们的
结构造最小片段：长理论文档、混进操作流水的限制节、冻结协议与 draft 状态、
并行会话抢同一个文档 ID、中英文数学混排、负结果与零差异、历史旧路径。

覆盖规范 §9 的 15 条场景，外加检查器自身的不变量：不改文件、结果可重复、
缺项目数据时明确报告无法核验。
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from typing import List

import doc_quality as dq
import layout_guard as lg
import rlp_paths as rlp

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def run_tool(*args: str, cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / "doc_quality.py"), *map(str, args)],
                          capture_output=True, text=True, cwd=str(cwd or ROOT))


def run_json(*args: str, cwd: pathlib.Path | None = None) -> tuple[int, dict]:
    proc = run_tool(*args, "--json", cwd=cwd)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise AssertionError(f"非 JSON 输出：{proc.stdout[-400:]} {proc.stderr[-400:]}")


def codes(report: dict) -> list[str]:
    return [item["code"] for entry in report["reports"] for item in entry["findings"]]


def findings(report: dict, code: str) -> list[dict]:
    return [item for entry in report["reports"] for item in entry["findings"]
            if item["code"] == code]


class Project:
    """最小项目骨架：控制根 + 一条路线 + INDEX。"""

    def __init__(self, base: pathlib.Path):
        self.root = base / "proj"
        self.control = self.root / rlp.STORAGE_ROOT
        self.docs = self.control / "routes" / "F" / "docs"
        self.docs.mkdir(parents=True)
        (self.root / "INDEX.md").write_text("# 根索引\n", encoding="utf-8")
        (self.control / "routes" / "F" / "INDEX.md").write_text("# F 索引\n", encoding="utf-8")

    def write(self, name: str, body: str, **front) -> pathlib.Path:
        fields = {"id": name.split("-")[0], "route": "F", "type": None,
                  "subtype": None, "status": "draft"}
        fields.update(front)
        header = "---\n" + "".join(
            f"{key}: {value}\n" for key, value in fields.items() if value is not None) + "---\n"
        path = self.docs / name
        path.write_text(header + "\n" + body, encoding="utf-8")
        return path

    def check(self, *paths: pathlib.Path) -> dict:
        args = ["check", "--root", str(self.root)]
        for path in paths:
            args += ["--path", str(path)]
        code, payload = run_json(*args)
        return payload

    def verify(self, path: pathlib.Path, *extra: str) -> dict:
        return dq.lint_doc(dq.read_doc(path), self.root, *extra and () or ())


class DocQualityBase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = pathlib.Path(self.tmp.name)
        self.project = Project(self.base)

    def tearDown(self):
        self.tmp.cleanup()


# ---------------------------------------------------------------------------
# 9.1 长理论文档：允许完整数学，缺导航才提示
# ---------------------------------------------------------------------------

class TestLongTheory(DocQualityBase):

    def long_theory(self, *, navigate: bool) -> pathlib.Path:
        parts: List[str] = ["# F010 深度研究轮", ""]
        if navigate:
            parts += ["## 0 执行摘要", "", "本轮的核心结论是切空间的秩上界。", ""]
        parts += ["## 3 定理", ""]
        for index in range(1, 41):
            parts.append(f"$$\\mathcal{{P}}_\\perp = I - U(U^{{H}}U)^{{-1}}U^{{H}},"
                         f" \\quad \\mathrm{{rank}}(U) = {index} \\tag{{{index}}}$$")
        parts.append("")
        for index in range(1, 26):
            parts.append(f"### 3.{index} 命题 {index}")
            parts.append("")
            parts.append("设 $A$ 为线性算子，则 $\\|Ax\\|_2 \\le \\|A\\|\\,\\|x\\|_2$。")
            parts.append("")
        return self.project.write("F010-theory.md", "\n".join(parts), type="theory")

    def test_math_heavy_theory_without_navigation_is_flagged(self):
        path = self.long_theory(navigate=False)
        report = self.project.check(path)
        self.assertIn("DQ-20", codes(report))
        self.assertEqual(findings(report, "DQ-20")[0]["severity"], "WARN")

    def test_the_same_doc_with_a_summary_is_not_flagged(self):
        path = self.long_theory(navigate=True)
        report = self.project.check(path)
        self.assertNotIn("DQ-20", codes(report))

    def test_formulas_never_produce_sentence_findings(self):
        path = self.long_theory(navigate=True)
        report = self.project.check(path)
        prose = [item for entry in report["reports"] for item in entry["findings"]
                 if item["code"].startswith("DQ-3-")]
        self.assertEqual(prose, [], "公式被掩码后不应产生任何句子规则命中")

    def test_math_survives_a_prose_only_revision(self):
        path = self.long_theory(navigate=True)
        original = path.read_text(encoding="utf-8")
        revised = original.replace("本轮的核心结论是切空间秩上界。",
                                   "本轮的核心结论为切空间的上界。")
        code, payload = run_json("compare", "--before", str(path), "--after",
                                 str(self._rewrite(revised)), "--intent", "prose-only")
        self.assertEqual(payload["status"], "PROSE_ONLY_OK", payload)
        self.assertEqual(code, 0)

    def _rewrite(self, text: str) -> pathlib.Path:
        path = self.base / "revised.md"
        path.write_text(text, encoding="utf-8")
        return path


# ---------------------------------------------------------------------------
# 9.2 操作流水混入研究正文
# ---------------------------------------------------------------------------

class TestOperationalLog(DocQualityBase):

    def discovery_with_log(self) -> pathlib.Path:
        body = """# F007 方法草图

## 6 预测

若去掉碰撞缓解，重建设置不变时读数应有可测量的变化。这条预测是事前的。

## 11 限制与未决

1. 体素间距未登记，因此 §8 的坐标声明当前不可核验，属阻塞性前置条件。
2. 本文不主张任何性能收益，§6 的三条预测是事前预测，不是结论。
3. 并发写披露：`routes/F/INDEX.md` 开工前 sha256 `00e2edbe…` → 写后 `8ad5f081…`
   （mtime 22:13），非本文所为；`models/f_prior_gamma.py` 早期 sha256 `d87b2376…`
   → `1d4f57d3…`（mtime 21:56），本文引用只保证对修订前版本成立。
4. 写作期间另一个 Agent 创建了 F005，本文的编号因此顺延，修订过程见 appendix。
"""
        return self.project.write("F007-discovery.md", body, type="discovery")

    def test_mixed_section_is_reported(self):
        report = self.project.check(self.discovery_with_log())
        self.assertIn("DQ-21", codes(report))
        message = findings(report, "DQ-21")[0]["message"]
        self.assertIn("运行记录", message)

    def test_the_hint_forbids_silent_deletion(self):
        report = self.project.check(self.discovery_with_log())
        hint = findings(report, "DQ-21")[0]["hint"]
        self.assertIn("不要删除", hint)

    def test_an_audit_report_may_contain_logs(self):
        body = """# F014 审计

## 1 故障记录

sha256 `deadbeefdeadbeef` 不匹配，mtime 为 22:13，另一个 Agent 写入过。
sha256 `cafebabecafebabe` 同样不匹配，mtime 为 22:20，并发写入被检出。
sha256 `0123456789abcdef` 第三次不匹配，修订过程记在日志里。

## 2 结论

零修正没有改变科学判断。
"""
        path = self.project.write("F014-zero-correction-selection-audit.md", body,
                                  type="review")
        report = self.project.check(path)
        self.assertNotIn("DQ-21", codes(report))

    def test_a_dedicated_appendix_is_not_punished(self):
        body = """# F010 理论

## 0 执行摘要

结论是秩上界。

## 附录 A 复现记录

sha256 `deadbeefdeadbeef` 记录在案，mtime 22:13，并发写入已披露。
sha256 `cafebabecafebabe` 记录在案，mtime 22:20。
sha256 `0123456789abcdef` 记录在案。
"""
        path = self.project.write("F010-theory.md", body, type="theory")
        report = self.project.check(path)
        self.assertNotIn("DQ-21", codes(report))


# ---------------------------------------------------------------------------
# 9.3 冻结协议与 Markdown 状态
# ---------------------------------------------------------------------------

class TestFrozenProtocol(DocQualityBase):

    def plan_doc(self, *, authority: bool, digest: str | None = None) -> pathlib.Path:
        prereg = self.project.control / "routes" / "F" / "experiments" / "X301" / "preregistration.json"
        prereg.parent.mkdir(parents=True, exist_ok=True)
        prereg.write_text('{"_schema": "prereg@1", "frozen": true}', encoding="utf-8")
        import hashlib
        real = hashlib.sha256(prereg.read_bytes()).hexdigest()
        body = "# F005 冻结预注册\n\n本文件产出冻结协议常量，冻结先于观察。\n"
        if digest:
            body += f"\n预注册正文见 `{prereg.relative_to(self.project.root)}`（sha256 `{digest}`）。\n"
        if authority:
            body += "\n**权威来源**是上面的 `preregistration.json`；本文只解释它，不覆盖它。\n"
        return self.project.write("F005-experiment-plan.md", body, type="experiment-plan")

    def test_draft_status_with_frozen_body_needs_review(self):
        report = self.project.check(self.plan_doc(authority=False))
        self.assertIn("DQ-42", codes(report))
        self.assertEqual(findings(report, "DQ-42")[0]["severity"], "REVIEW_REQUIRED")

    def test_declaring_the_authority_clears_the_review(self):
        report = self.project.check(self.plan_doc(authority=True))
        self.assertNotIn("DQ-42", codes(report))

    def test_matching_digest_is_accepted(self):
        import hashlib
        path = self.plan_doc(authority=True)
        prereg = (self.project.control / "routes" / "F" / "experiments" / "X301" /
                  "preregistration.json")
        digest = hashlib.sha256(prereg.read_bytes()).hexdigest()
        text = path.read_text(encoding="utf-8") + (
            f"\n预注册正文见 `{prereg.relative_to(self.project.root)}`（sha256 `{digest}`）。\n")
        path.write_text(text, encoding="utf-8")
        report = self.project.check(path)
        self.assertNotIn("DQ-10", codes(report))
        self.assertNotIn("DQ-43", codes(report))

    def test_a_stale_digest_is_a_block(self):
        report = self.project.check(self.plan_doc(authority=True, digest="0" * 64))
        self.assertIn("DQ-10", codes(report))
        self.assertEqual(findings(report, "DQ-10")[0]["severity"], "BLOCK")

    def test_an_unreachable_prereg_is_a_review_not_a_guess(self):
        body = ("# F006 计划\n\n预注册见 `.research-idea-pipeline/routes/F/experiments/X999/"
                "preregistration.json`（sha256 `" + "a" * 64 + "`）。\n")
        path = self.project.write("F006-experiment-plan.md", body, type="experiment-plan")
        report = self.project.check(path)
        self.assertIn("DQ-43", codes(report))
        self.assertNotIn("DQ-10", codes(report))


# ---------------------------------------------------------------------------
# 9.4 并行会话的文档 ID 冲突
# ---------------------------------------------------------------------------

class TestDocumentIds(DocQualityBase):

    def test_a_second_file_with_the_same_id_is_blocked(self):
        self.project.write("F009-mist-inr-candidate.md", "# F009\n\n候选方向。\n",
                           type="proposal")
        second = self.project.write("F009-another-session.md", "# F009\n\n另一个会话。\n",
                                    type="proposal")
        report = self.project.check(second)
        self.assertIn("DQ-05", codes(report))
        self.assertEqual(findings(report, "DQ-05")[0]["severity"], "BLOCK")

    def test_allocation_returns_the_next_free_id(self):
        self.project.write("F009-mist-inr-candidate.md", "# F009\n", type="proposal")
        control = lg.control_root(self.project.root)
        self.assertEqual(lg.next_doc_id(self.project.root, control, "F"), "F010")

    def test_allocation_never_overwrites_an_existing_file(self):
        existing = self.project.write("F009-mist-inr-candidate.md", "# F009 原始\n",
                                      type="proposal")
        before = existing.read_text(encoding="utf-8")
        result = lg.allocate_doc(self.project.root, "F", "second-session")
        self.assertTrue(result["created"])
        self.assertNotEqual(pathlib.Path(result["path"]).name, existing.name)
        self.assertEqual(existing.read_text(encoding="utf-8"), before,
                         "分配新 ID 不得改动任何既有文档")

    def test_a_unique_id_produces_no_finding(self):
        path = self.project.write("F003-discovery.md", "# F003\n\n方法差异。\n",
                                  type="discovery")
        report = self.project.check(path)
        self.assertNotIn("DQ-05", codes(report))


# ---------------------------------------------------------------------------
# 9.5 中英文与数学混排
# ---------------------------------------------------------------------------

class TestMixedLanguageMath(DocQualityBase):

    def mixed_doc(self) -> pathlib.Path:
        body = r"""# F015 NPSF 阶段一

## 1 定义

设 $x \in \mathbb{C}^{N}$，重建算子记为 $\mathcal{A}$，其共轭转置为 $\mathcal{A}^{H}$。
傅里叶变换定义为 $\hat{x}[k] = \sum_{n=0}^{N-1} x[n] e^{-2\pi i k n / N}$。

$$
\mathcal{L}(\theta) = \mathbb{E}_{y \sim p_{\text{data}}}\left[\| \mathcal{A} f_\theta(y) - y \|_2^2\right]
$$

| 变量 | 含义 | 单位 |
|---|---|---|
| $N$ | 采样点数 | — |
| $\sigma$ | 噪声标准差 | a.u. |

在 `configs/routes/F/npsf.yaml` 里把 `lambda_tv` 设为 0.0 时，等价于不做 TV 正则。
"""
        return self.project.write("F015-npsf-stage01.md", body, type="evidence")

    def test_no_sentence_finding_lands_inside_math(self):
        report = self.project.check(self.mixed_doc())
        prose = [item for entry in report["reports"] for item in entry["findings"]
                 if item["code"].startswith("DQ-3-")]
        self.assertEqual(prose, [])

    def test_rewriting_chinese_does_not_touch_math(self):
        path = self.mixed_doc()
        text = path.read_text(encoding="utf-8")
        revised = text.replace("设 $x", "令 $x").replace("等价于不做 TV 正则",
                                                        "等价于省略 TV 正则")
        target = self.base / "revised.md"
        target.write_text(revised, encoding="utf-8")
        _code, payload = run_json("compare", "--before", str(path), "--after",
                                  str(target), "--intent", "prose-only")
        self.assertEqual(payload["status"], "PROSE_ONLY_OK", payload["protected_changes"])

    def test_changing_a_symbol_is_caught(self):
        path = self.mixed_doc()
        text = path.read_text(encoding="utf-8")
        target = self.base / "changed.md"
        target.write_text(text.replace("\\mathcal{A}^{H}", "\\mathcal{A}^{T}"),
                          encoding="utf-8")
        _code, payload = run_json("compare", "--before", str(path), "--after",
                                  str(target), "--intent", "prose-only")
        self.assertEqual(payload["status"], "BLOCK")
        self.assertEqual(payload["protected_changes"][0]["category"], "公式")


# ---------------------------------------------------------------------------
# 9.6 负结果与零差异得到保护
# ---------------------------------------------------------------------------

class TestNegativeResults(DocQualityBase):

    def results_doc(self) -> pathlib.Path:
        body = """# F012 有界合成试点结果

## 1 完成范围

本轮跑完两个 seed 的合成数据试点。

## 2 结果

零修正与完整修正的 PSNR 差为 0.00 dB，统计上不可区分，不构成增益。
负结果记录：目标错位风险在 120 例样本上复现，未观察到改善。

## 3 研究决定

维持现有主张，不把有限候选的结论推广到整个方法类。
"""
        return self.project.write("F012-h8-p1-results.md", body, type="evidence")

    def test_zero_difference_survives_a_language_edit(self):
        path = self.results_doc()
        text = path.read_text(encoding="utf-8")
        target = self.base / "polished.md"
        target.write_text(text.replace("本轮跑完两个 seed", "本轮完成两个 seed"),
                          encoding="utf-8")
        _code, payload = run_json("compare", "--before", str(path), "--after",
                                  str(target), "--intent", "prose-only")
        self.assertEqual(payload["status"], "PROSE_ONLY_OK", payload["protected_changes"])

    def test_dropping_a_negative_result_is_blocked(self):
        path = self.results_doc()
        text = path.read_text(encoding="utf-8")
        stripped = text.replace("负结果记录：目标错位风险在 120 例样本上复现，未观察到改善。\n", "")
        target = self.base / "slim.md"
        target.write_text(stripped, encoding="utf-8")
        code, payload = run_json("compare", "--before", str(path), "--after",
                                 str(target), "--intent", "prose-only")
        self.assertEqual(code, 3)
        self.assertEqual(payload["status"], "BLOCK")

    def test_changing_modality_is_blocked(self):
        path = self.results_doc()
        text = path.read_text(encoding="utf-8")
        target = self.base / "hedged.md"
        target.write_text(text.replace("不构成增益", "可能构成增益"), encoding="utf-8")
        _code, payload = run_json("compare", "--before", str(path), "--after",
                                  str(target), "--intent", "prose-only")
        self.assertEqual(payload["status"], "BLOCK")
        self.assertEqual(payload["protected_changes"][0]["category"], "情态与限定")


# ---------------------------------------------------------------------------
# 9.7 合法的科学修订不被一概拒绝
# ---------------------------------------------------------------------------

class TestScientificRevision(DocQualityBase):

    def test_an_authorised_scientific_change_is_allowed(self):
        before = self.base / "a.md"
        after = self.base / "b.md"
        before.write_text("主实验达到 PSNR 31.2 dB（n=120）。", encoding="utf-8")
        after.write_text("主实验达到 PSNR 33.8 dB（n=240）。", encoding="utf-8")
        _code, payload = run_json("compare", "--before", str(before), "--after",
                                  str(after), "--intent", "scientific-change")
        self.assertEqual(payload["status"], "REVIEW_ONLY")
        self.assertEqual(payload["protected_changes"], [])

    def test_the_same_change_under_prose_intent_blocks_until_authorised(self):
        before = self.base / "a.md"
        after = self.base / "b.md"
        before.write_text("主实验达到 PSNR 31.2 dB。", encoding="utf-8")
        after.write_text("主实验达到 PSNR 33.8 dB。", encoding="utf-8")
        code, payload = run_json("compare", "--before", str(before), "--after",
                                 str(after), "--intent", "prose-only")
        self.assertEqual(code, 3)
        code, payload = run_json("compare", "--before", str(before), "--after",
                                 str(after), "--intent", "prose-only",
                                 "--allow-scientific-change")
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "SCIENTIFIC_CHANGE_ALLOWED")


# ---------------------------------------------------------------------------
# 9.8 历史旧路径不被全局替换
# ---------------------------------------------------------------------------

class TestHistoricalPaths(DocQualityBase):

    def test_an_old_control_root_reference_is_not_rewritten(self):
        body = ("# F000 锚点\n\n历史证据来自 `.research-idea-pipeline/routes/A/docs/A001.md`，"
                "该路径在迁移后仍是合法历史引用。\n")
        path = self.project.write("F000-anchor.md", body, type="anchor")
        before = path.read_text(encoding="utf-8")
        report = self.project.check(path)
        self.assertNotIn("DQ-06", codes(report), "旧控制根不是错误链接")
        self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_prose_compare_does_not_touch_paths(self):
        before = self.base / "a.md"
        after = self.base / "b.md"
        text = "读数见 `.research-idea-pipeline/routes/A/E35.json`。"
        before.write_text(text, encoding="utf-8")
        after.write_text(text.replace("读数见", "读数记录见"), encoding="utf-8")
        _code, payload = run_json("compare", "--before", str(before), "--after",
                                  str(after), "--intent", "prose-only")
        self.assertEqual(payload["status"], "PROSE_ONLY_OK")


# ---------------------------------------------------------------------------
# 9.9 相似结论不被自动合并
# ---------------------------------------------------------------------------

class TestRedundancy(DocQualityBase):

    def test_near_duplicate_paragraphs_are_flagged_but_kept(self):
        paragraph = ("零修正与完整修正的读数在统计上不可区分，这一结论在两个 seed 上都一致，"
                     "既没有观察到性能增益，也不能把这条有限候选的结论推广到其他重建方法类，"
                     "更不能据此推断该机制在其他采样率下同样成立。")
        body = f"# F013\n\n## 1 合成数据\n\n{paragraph}\n\n## 2 真实数据\n\n{paragraph}\n"
        path = self.project.write("F013-h8-real-mri-pilot-results.md", body, type="evidence")
        before = path.read_bytes()
        report = self.project.check(path)
        self.assertIn("DQ-22", codes(report))
        self.assertEqual(path.read_bytes(), before, "检查器不得合并或删除任何段落")
        self.assertEqual(path.read_text(encoding="utf-8").count(paragraph), 2,
                         "两处相似段落都必须留在原文里")


# ---------------------------------------------------------------------------
# 9.10 Git 增量：只报新增问题，staged 读索引
# ---------------------------------------------------------------------------

class TestIncremental(DocQualityBase):

    def setUp(self):
        super().setUp()
        subprocess.run(["git", "init", "-q"], cwd=str(self.project.root), check=True)
        for key, value in (("user.email", "t@example.com"), ("user.name", "t")):
            subprocess.run(["git", "config", key, value], cwd=str(self.project.root),
                           check=True)
        self.legacy = self.project.write(
            "F001-evidence.md", "# F001\n\n这是一段旧正文；它本来就有一个分号。\n",
            type="evidence")
        subprocess.run(["git", "add", "-A"], cwd=str(self.project.root), check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=str(self.project.root),
                       check=True)

    def test_an_untouched_problem_is_not_reported_again(self):
        code, payload = run_json("check", "--changed", "--root", str(self.project.root))
        self.assertEqual(payload["reports"], [])
        self.assertEqual(code, 0)

    def test_only_the_new_problem_is_reported(self):
        self.legacy.write_text(
            self.legacy.read_text(encoding="utf-8").replace(
                "这是一段旧正文；它本来就有一个分号。",
                "这是一段旧正文；它本来就有一个分号；新加的内容也带了分号。"),
            encoding="utf-8")
        code, payload = run_json("check", "--changed", "--root", str(self.project.root))
        self.assertEqual(code, 0, "分号是 WARN，不应阻断")
        reported = findings(payload, "DQ-3-semicolon")
        self.assertTrue(reported, payload)

    def test_a_new_block_is_reported_on_changed(self):
        self.legacy.write_text(
            "---\nid: F001\nroute: F\ntype: evidence\nstatus: draft\n---\n\n见 [丢失的附件](missing-file.md)。\n", encoding="utf-8")
        code, payload = run_json("check", "--changed", "--root", str(self.project.root))
        self.assertEqual(code, 3)
        self.assertIn("DQ-06", codes(payload))

    def test_staged_check_reads_the_index_not_the_worktree(self):
        good = "---\nid: F001\nroute: F\ntype: evidence\nstatus: draft\n---\n\n这一版没有结构问题。\n"
        self.legacy.write_text(good, encoding="utf-8")
        subprocess.run(["git", "add", str(self.legacy)], cwd=str(self.project.root),
                       check=True)
        self.legacy.write_text("---\nid: F001\nroute: F\ntype: evidence\nstatus: draft\n---\n\n见 [丢失](gone.md)。\n", encoding="utf-8")
        code, payload = run_json("check", "--staged", "--root", str(self.project.root))
        self.assertEqual(code, 0, "工作区的坏版本不应影响暂存区检查")
        self.assertNotIn("DQ-06", codes(payload))

    def test_staged_check_sees_the_staged_block(self):
        self.legacy.write_text("---\nid: F001\nroute: F\ntype: evidence\nstatus: draft\n---\n\n见 [丢失](gone.md)。\n", encoding="utf-8")
        subprocess.run(["git", "add", str(self.legacy)], cwd=str(self.project.root),
                       check=True)
        self.legacy.write_text("---\nid: F001\nroute: F\ntype: evidence\nstatus: draft\n---\n\n修好的版本。\n", encoding="utf-8")
        code, payload = run_json("check", "--staged", "--root", str(self.project.root))
        self.assertEqual(code, 3, "暂存区里仍是坏版本")
        self.assertIn("DQ-06", codes(payload))


# ---------------------------------------------------------------------------
# 9.11 检查器自身的不变量
# ---------------------------------------------------------------------------

class TestCheckerInvariants(DocQualityBase):

    def sample(self) -> pathlib.Path:
        body = "# F004 理论\n\n## 1 记号\n\n设 $A$ 为线性算子；这里有一个分号。\n"
        return self.project.write("F004-theory.md", body, type="theory")

    def test_a_check_never_modifies_the_file(self):
        path = self.sample()
        before = path.read_bytes()
        self.project.check(path)
        self.assertEqual(path.read_bytes(), before)

    def test_repeated_runs_produce_the_same_report(self):
        path = self.sample()
        first = self.project.check(path)
        second = self.project.check(path)
        self.assertEqual(json.dumps(first, sort_keys=True),
                         json.dumps(second, sort_keys=True))

    def test_missing_project_data_is_reported_not_invented(self):
        path = self.sample()
        payload = dq.report_for(path, None)
        self.assertNotIn("DQ-05", [item["code"] for item in payload["findings"]],
                         "没有项目根时不得假装做过 ID 冲突检查")

    def test_a_missing_file_is_an_environment_error(self):
        proc = run_tool("check", "--path", str(self.base / "nope.md"))
        self.assertEqual(proc.returncode, 4)

    def test_frontmatter_id_mismatch_is_blocked(self):
        path = self.project.write("F002-field-map.md", "# F002\n", id="F003")
        report = self.project.check(path)
        self.assertIn("DQ-02", codes(report))
        self.assertEqual(findings(report, "DQ-02")[0]["severity"], "BLOCK")

    def test_unclosed_fence_is_blocked(self):
        path = self.project.write("F003-discovery.md", "# F003\n\n```python\nprint(1)\n",
                                  type="discovery")
        report = self.project.check(path)
        self.assertIn("DQ-08", codes(report))

    def test_broken_anchor_is_blocked(self):
        path = self.project.write("F003-discovery.md",
                                  "# F003\n\n见 [第二节](#不存在的小节)。\n", type="discovery")
        report = self.project.check(path)
        self.assertIn("DQ-07", codes(report))

    def test_per_rule_cap_keeps_reports_readable(self):
        body = "# F003\n\n" + "\n".join(f"第{i}句；后半句。" for i in range(30))
        path = self.project.write("F003-discovery.md", body, type="discovery")
        report = self.project.check(path)
        semicolons = findings(report, "DQ-3-semicolon")
        self.assertLessEqual(len(semicolons), dq.MAX_PER_RULE + 1)
        self.assertTrue(any("未逐条列出" in item["message"] for item in semicolons))

    def test_json_payload_has_a_schema_and_counts(self):
        path = self.sample()
        _code, payload = run_json("check", "--path", str(path), "--root",
                                  str(self.project.root))
        self.assertEqual(payload["_schema"], dq.SCHEMA)
        self.assertIn("counts", payload)

    def test_selftest_passes(self):
        proc = subprocess.run([sys.executable, str(SCRIPTS / "doc_quality.py"), "selftest"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
