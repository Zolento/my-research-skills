#!/usr/bin/env python3
"""report_lint.py — 用户报告的**结构**检查（不是科研门禁）。

为什么需要它
------------
`references/scientific-communication-policy.md` 规定了报告的默认形态，但形态只写在散文里。
实测后果有两类：把 `git status`、`已同步 state`、`XX 条审计通过` 当开场白；训练启动通知
缺优化器或选模协议，而用户当时无从发现缺项。

本脚本只做两件事：**结构**与**客观缺字段**。它不判断科学结论是否正确，不判断因果关系，
也不新增 R 阶段。疑似科学归因问题只给 `WARN`，交给既有证据资格审核。

用法

    python3 report_lint.py report.md
    python3 report_lint.py report.md --type training-report
    python3 report_lint.py report.md --json
    python3 report_lint.py --selftest
    python3 report_lint.py --list-rules

报告类型

    result          结果完成后的汇报（默认）
    training-report 训练启动前的完整配置报告
    progress        运行中的进度汇报（允许极简）

退出码：0 通过（可含 WARN）/ 3 有 BLOCK / 4 环境问题。

规则

    REP-01  非审计报告第一节必须是结论或研究决定，标题形如 `01.`
    REP-02  禁止以 git status / 已同步 state / N 条审计通过 开场；禁止重复 gate 日志
    REP-03  训练启动通知必须齐备 11 项配置；缺项阻断**通知合格判定**，不是删字段
    REP-04  结果数字须带指标名、样本单位/数量、数据集或划分、参考对照；
            未证实推断不得用「只能 / 必然 / 证明」——本项只提示风险，不给 WARN 以上
    REP-05  阻塞、失败、证据冲突、待用户决策绝不静默
    REP-06  详细 JSON / 日志不得进默认报告（只允许在 `--verbose` 或本地记录）
    REP-07  多项关键未决事项必须一次汇总，不得替用户选项后执行
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

BLOCK, WARN, OK = "BLOCK", "WARN", "OK"

NUMBERED = re.compile(r"^#{1,6}\s*(\d{2})\.\s*(.+)$")
ANY_HEADING = re.compile(r"^#{1,6}\s+(.+)$")

#: REP-02：操作流水账的开场白。
OPERATION_OPENERS = (
    "git status", "已同步", "已刷新", "审计通过", "条审计", "全部通过", "release_check",
    "目录检查", "索引已", "已更新 state", "已完成同步", "检查通过",
)
GATE_LOG = re.compile(r"(审计|检查|门禁)[^\n]{0,12}\d+\s*(条|项)[^\n]{0,6}(通过|ok|OK)")

#: REP-03：训练启动通知必须覆盖的 11 项（Contract v1.0 §10）。
TRAINING_FIELDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("数据与划分", ("划分", "train", "val", "test", "数据")),
    ("维度与尺寸", ("尺寸", "维度", "shape", "网格")),
    ("mask/ACS/方向", ("mask", "掩膜", "acs", "加速", "方向", "采样")),
    ("输入输出与线圈", ("输入", "输出", "线圈", "coil")),
    ("CSM 模式与来源", ("csm", "灵敏度", "csm 模式", "dataset_stored", "joint_estimation",
                        "not_applicable")),
    ("算子与归一化", ("算子", "fft", "伴随", "归一化", "norm")),
    ("优化器", ("优化器", "optimizer", "adam", "sgd")),
    ("学习率与调度", ("学习率", "lr", "调度", "schedule", "warmup")),
    ("预算", ("预算", "epoch", "step", "budget")),
    ("损失", ("损失", "loss")),
    ("选模协议与指标", ("选模", "选择", "selection", "psnr", "nmse", "指标")),
    ("checkpoint", ("checkpoint", "检查点", "best_val", "latest")),
)

#: REP-04：未证实推断的断言词。
STRONG_CLAIMS = ("只能", "必然", "证明了", "证明", "必然导致", "毫无疑问", "完全证明")
#: REP-04：数字必须带的对照信息。
METRIC_NAMES = ("psnr", "nmse", "ssim", "hfen", "snr", "lpips", "准确率", "f1", "auc")
NUMBER = re.compile(r"\d+\.\d+|\d+\s*(?:dB|%|个|片|例|张|次|step|epoch)", re.IGNORECASE)

#: REP-05：阻塞词。出现即要求报告里同时出现处置说明。
BLOCKING_WORDS = ("阻塞", "失败", "冲突", "HOLD", "未通过", "拒绝", "无法")
#: REP-06：不该出现在默认报告里的东西。
NOISE_PATTERNS = (
    (re.compile(r"\b(gpu|cuda)[-_ ]?uuid\b", re.I), "GPU UUID"),
    (re.compile(r"state_version\s*[:=]\s*\d+"), "state_version"),
    (re.compile(r'"(schema|digest|sha256)"\s*:'), "内联 JSON 字段"),
    (re.compile(r"^\{$|^\}\s*$", re.M), "整段 JSON"),
)
#: REP-07：多问题清单与擅自选项的判据。
OPTION_DECIDED = re.compile(r"(我已自行选择|默认按|按默认值|默认采用|先按.+继续)")


def numbered_headings(lines: List[str]) -> List[Tuple[int, str, str]]:
    found = []
    for index, line in enumerate(lines):
        match = NUMBERED.match(line.strip())
        if match:
            found.append((index, match.group(1), match.group(2).strip()))
    return found


def body_after(lines: List[str]) -> List[str]:
    """跳过 YAML frontmatter 与空行，返回正文行。"""
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return lines[index + 1:]
    return lines


def lint(text: str, report_type: str = "result") -> Dict[str, object]:
    lines = text.splitlines()
    body = body_after(lines)
    findings: List[Dict[str, str]] = []

    def add(rule: str, severity: str, message: str) -> None:
        findings.append({"rule": rule, "severity": severity, "message": message})

    non_empty = [line for line in body if line.strip()]
    headings = numbered_headings(body)

    # REP-01 — 编号与首节
    if report_type != "progress":
        if not headings:
            add("REP-01", BLOCK, "报告没有编号小节；用 `01. 本轮结论` 这种形式组织")
        else:
            first_title = headings[0][2]
            if not re.search(r"结论|决定|研究|目的|摘要|结果|变更", first_title):
                add("REP-01", BLOCK,
                    f"第一节标题是「{first_title}」：报告必须以结论或研究决定开头")
            numbers = [int(number) for _, number, _ in headings]
            if numbers != list(range(1, len(numbers) + 1)):
                add("REP-01", BLOCK, f"小节编号不连续或未从 01 起：{numbers}")

    # REP-02 — 开场白与 gate 日志
    opener = ""
    for line in non_empty:
        if line.lstrip().startswith("#") or line.strip() in ("---", ">"):
            continue
        opener = line.strip()
        break
    if opener and any(word in opener for word in OPERATION_OPENERS):
        add("REP-02", BLOCK, f"报告以操作流水账开场：「{opener[:40]}」；先给科学结论")
    gate_lines = [line for line in body if GATE_LOG.search(line)]
    if len(gate_lines) > 1:
        add("REP-02", WARN, f"正文重复出现 {len(gate_lines)} 行门禁通过日志；正常通过不逐条汇报")

    # REP-03 — 训练启动通知
    if report_type == "training-report":
        lowered = text.lower()
        missing = [label for label, keys in TRAINING_FIELDS
                   if not any(key.lower() in lowered for key in keys)]
        if missing:
            add("REP-03", BLOCK,
                "训练启动通知缺项：" + "、".join(missing)
                + "。补齐内容，不要删字段让检查通过")
        if re.search(r"\bN/?A\b", text):
            add("REP-03", WARN, "报告里出现 N/A；缺项要写清缺什么，不要用 N/A 掩盖")

    # REP-04 — 数字的可解释性（只提示风险）
    if report_type != "progress":
        numeric = [line for line in body if NUMBER.search(line)]
        if numeric:
            lowered = text.lower()
            if not any(name in lowered for name in METRIC_NAMES):
                add("REP-04", WARN, "报告有数字但没有任何指标名（PSNR/NMSE/SSIM 等）")
            if not re.search(r"(划分|test|val|train|验证|测试|样本|片|例)", text):
                add("REP-04", WARN, "报告有数字但没有说明数据集或划分与样本量")
        for word in STRONG_CLAIMS:
            if word in text:
                add("REP-04", WARN,
                    f"出现强断言「{word}」；未证实的推断请降级为观察或假设")
                break

    # REP-05 — 阻塞不得静默
    blocking = [word for word in BLOCKING_WORDS if word in text]
    if blocking and not re.search(r"(下一步|处置|解除|影响|待用户|需要你|请确认)", text):
        add("REP-05", BLOCK,
            f"报告提到 {blocking}，但没有写影响范围或处置方式；阻塞不得静默")

    # REP-06 — 默认报告不得夹带详细机器记录
    if report_type != "progress":
        for pattern, label in NOISE_PATTERNS:
            if pattern.search(text):
                add("REP-06", WARN,
                    f"默认报告出现 {label}；详细记录放本地结构化文件或 --verbose")
                break

    # REP-07 — 未决事项必须一次汇总
    if OPTION_DECIDED.search(text):
        add("REP-07", BLOCK,
            "报告替用户选了默认值；关键未决项必须一次性询问，不得自行决定后执行")
    if re.search(r"(问题清单|未决事项|需要确认)", text) and \
            len(re.findall(r"(^\s*[-*]\s*\d|\bQ\d\b|^\s*\d+\.)", text, re.M)) > 1:
        add("REP-07", WARN, "存在多项未决事项；确认它们已合并成一次询问而不是分多轮")

    blocks = [f for f in findings if f["severity"] == BLOCK]
    warns = [f for f in findings if f["severity"] == WARN]
    return {
        "report_type": report_type,
        "status": BLOCK if blocks else (WARN if warns else OK),
        "blocks": len(blocks),
        "warns": len(warns),
        "findings": findings,
    }


def render(result: Dict[str, object], verbose: bool = False) -> str:
    findings = result["findings"]  # type: ignore[index]
    if not findings and not verbose:
        return f"报告结构检查：{result['status']}"
    lines = [f"{f['severity']:<5} [{f['rule']}] {f['message']}" for f in findings]
    lines.append(f"report_lint: {result['status']}（BLOCK {result['blocks']} / WARN {result['warns']}）")
    return "\n".join(lines)


def selftest() -> int:
    failures = 0

    def expect(label: str, condition: bool) -> None:
        nonlocal failures
        if not condition:
            failures += 1
            print(f"FAIL  {label}")

    good = """# 报告

## 01. 本轮结论
PSNR 提升 0.4 dB，但只在一个 test 划分上成立。

## 02. 实验结果
| 方法 | test PSNR |
|---|---|
| base | 31.20 |
| ours | 31.60 |
"""
    result = lint(good)
    expect("合规报告通过", result["status"] in (OK, WARN) and result["blocks"] == 0)

    bad_opener = "## 01. 本轮结论\n已同步 state，审计通过 12 条。\n"
    result = lint(bad_opener)
    expect("操作流水账开场被拦", result["status"] == BLOCK)

    no_numbers = "## 本轮结论\n结果更好。\n"
    expect("缺编号被判 BLOCK", lint(no_numbers)["blocks"] >= 1)

    bad_first = "## 01. 操作记录\n跑了训练。\n"
    expect("首节不是结论", lint(bad_first)["blocks"] >= 1)

    training = """## 01. 本轮目的与方法
验证 A 臂。

## 02. 数据与物理配置
| 数据划分 | 维度 | mask | CSM |
|---|---|---|---|
| train/val/test | 320x320 | 列 mask | 有 |
输入 [B,C,H,W] k-space，输出 [B,H,W]，FFT 轴向，归一化用测量。
## 03. 训练与选模
| 优化器 | 学习率 | 预算 | 损失 | 选模 | checkpoint |
| AdamW | 3e-3 | 18000 步 | l1 | full_val_gt PSNR | best_val |
代码 commit abc，资源已授权。
"""
    result = lint(training, "training-report")
    expect("完整训练通知通过", result["blocks"] == 0)

    incomplete = "## 01. 目的\n跑训练。\n## 02. 数据\n320x320。\n"
    result = lint(incomplete, "training-report")
    expect("缺项训练通知被拦", result["blocks"] >= 1)

    silent_block = "## 01. 本轮结论\n训练失败。\n"
    expect("阻塞静默被拦", lint(silent_block)["blocks"] >= 1)

    decided = "## 01. 本轮结论\n有问题，我已自行选择方案继续。\n"
    expect("擅自选项被拦", lint(decided)["blocks"] >= 1)

    strong = "## 01. 本轮结论\n该机制必然导致提升，PSNR 31.2，test 划分。\n"
    result = lint(strong)
    expect("强断言给 WARN 而非 BLOCK", result["blocks"] == 0 and result["warns"] >= 1)

    noise = '## 01. 本轮结论\n正常。\n\n```json\n{"schema": "x"}\n```\n'
    result = lint(noise)
    expect("内联 JSON 给 WARN", result["warns"] >= 1)

    expect("progress 类型不要求编号", lint("继续跑。", "progress")["blocks"] == 0)
    print(f"selftest: {failures} failure(s)")
    return 1 if failures else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--type", default="result",
                        choices=["result", "training-report", "progress"],
                        dest="report_type")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--list-rules", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.selftest:
        return selftest()
    if args.list_rules:
        for rule in ("REP-01", "REP-02", "REP-03", "REP-04", "REP-05", "REP-06", "REP-07"):
            print(rule)
        return 0
    if args.path is None:
        parser.error("需要报告文件路径（或 --selftest）")
    if not args.path.is_file():
        print(f"[env] 报告文件不存在：{args.path}", file=sys.stderr)
        return 4
    try:
        text = args.path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"[env] 无法读取：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 4
    result = lint(text, args.report_type)
    print(json.dumps(result, ensure_ascii=False, indent=1) if args.json
          else render(result, args.verbose))
    return 3 if result["status"] == BLOCK else 0


if __name__ == "__main__":
    sys.exit(main())
