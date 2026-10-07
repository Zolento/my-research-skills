#!/usr/bin/env python3
"""release_check.py — 唯一的发布闸门。

**verdict 只看 exit code 与最后一行**（`PASS` / `FAIL`）。
前面逐项的 `[ok] / [FAIL]` 输出**只用于诊断** —— 不要拿它当判定。

为什么需要它
------------
一次真实事故：四个提交信息都写了「linter 硬违规 0」，但读的是 linter 输出的
**最后一行**（一句提示），不是计数行 —— 于是 5 处硬违规连续四批没被发现。

**人读闸门输出，本身就是一个未验证的步骤。** 因此把全部发布闸门收敛成一条命令：

    python3 scripts/release_check.py        # verdict = 最后一行 / exit code

它依次调用下面这些检查。**任一项不过，整体 FAIL。**

    1. 全套离线测试（`unittest discover scripts/test_*.py`）
       —— 它已经内含 golden path、Shape Gate、规则/表格/契约 parity、
          受控中文 linter、退役词扫描、链接与打包完整性
    2. `state_check.py --selftest`
    3. `state_check.py --check templates/research-state.template.json`
    4. 规则表逐字比对：policy §4.0 S1—S7 / §4.1 V1—V24 ↔ `state_check.py`
    5. 三方读写表逐格比对：SKILL §0 / policy §5 / 各 `phase-*.md`
    6. 文档里引用的每个 `scripts/*.py` 都真实存在
    7. `structural_equivalence_check.py --selftest` + audit 模板 + 七份 fixture
       —— Structural Equivalence 的 `EQ1`—`EQ13` + `NN1`—`NN14`（只查审计完整性，不宣判 novelty）

退出码
------
0  PASS
1  FAIL（任何一项不过）
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
from typing import List, Tuple

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _run(args: List[str]) -> Tuple[int, str]:
    """跑一个子进程，**把 stderr 并进 stdout**。

    不能写成 `proc.stdout + proc.stderr`：那是**拼接**而不是**交错**，
    于是「输出的最后一行」会取自 stderr，而它可能只是某个负例用例打印的环境消息。
    `--selftest` 就踩过这个坑 —— 它内部会跑「非法 JSON → 退出码 4」的用例。
    """
    proc = subprocess.run([sys.executable, *args], stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, cwd=str(ROOT))
    return proc.returncode, proc.stdout


# ---------------------------------------------------------------------------
# 各步骤
# ---------------------------------------------------------------------------

def step_tests() -> Tuple[bool, str]:
    code, out = _run(["-m", "unittest", "discover", "-s", "scripts", "-p", "test_*.py"])
    tail = [line for line in out.strip().splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
    return code == 0, " · ".join(tail) or out.strip()[-160:]


def step_selftest() -> Tuple[bool, str]:
    code, out = _run(["scripts/state_check.py", "--selftest"])
    lines = [line.strip() for line in out.strip().splitlines() if line.strip()]
    summary = next((line for line in reversed(lines) if "selftest" in line.lower()),
                   lines[-1] if lines else "no output")
    return code == 0, f"{summary}（exit={code}）"


def step_template() -> Tuple[bool, str]:
    code, out = _run(["scripts/state_check.py", "--check",
                      "templates/research-state.template.json"])
    return code == 0, f"exit={code}" + ("" if code == 0 else f" {out.strip()[-120:]}")


def step_rule_table_parity() -> Tuple[bool, str]:
    policy = (ROOT / "references" / "research-state-policy.md").read_text(encoding="utf-8")
    code, out = _run(["scripts/state_check.py", "--list-rules"])
    if code != 0:
        return False, f"--list-rules exit={code}"
    listed = {}
    for line in out.splitlines():
        match = re.match(r"^([SV]\d+)\s+.*?\s\s+(.*)$", line)
        if match:
            listed[match.group(1)] = match.group(2).strip()
    failures = []
    for tag, pattern in (("S", r"^\| (S\d+) \| (.+?) \| 形状 \|"),
                         ("V", r"^\| (V\d+) \| (.+?) \| 硬 \|")):
        documented = dict(re.findall(pattern, policy, re.M))
        for rule in sorted(set(documented) | {k for k in listed if k.startswith(tag)}):
            if documented.get(rule) != listed.get(rule):
                failures.append(f"{rule}")
    total = len(listed)
    if failures:
        return False, f"不一致：{failures}"
    return True, f"{total} 条（S+V）逐字一致"


def _parse_rw_table(text: str, anchor: str):
    lines = text[text.index(anchor):].split("\n")
    read_index = write_index = header_index = None
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


def step_readwrite_parity() -> Tuple[bool, str]:
    policy = _parse_rw_table((ROOT / "references" / "research-state-policy.md").read_text(encoding="utf-8"),
                             "| 阶段 | 读什么")
    skill = _parse_rw_table((ROOT / "SKILL.md").read_text(encoding="utf-8"), "| Phase | 名称 |")
    if not policy or not skill:
        return False, "读写表解析失败（表头或阶段行找不到）"
    checked = 0
    for stage in sorted(set(skill) & set(policy)):
        if skill[stage] != policy[stage]:
            return False, f"SKILL §0 的 {stage} 行与 policy §5 不一致"
        checked += 1
    for path in sorted((ROOT / "references").glob("phase-*.md")):
        text = path.read_text(encoding="utf-8")
        if "## 读 / 写 World Model" not in text:
            continue
        rows = _parse_rw_table(text, "## 读 / 写 World Model")
        for stage in sorted(set(rows) & set(policy)):
            if rows[stage] != policy[stage]:
                return False, f"{path.name} 的 {stage} 行与 policy §5 不一致"
            checked += 1
    if checked < 20:
        return False, f"只比对到 {checked} 行（解析器失效？）"
    return True, f"{checked} 行逐格一致"


def step_referenced_scripts_exist() -> Tuple[bool, str]:
    missing, seen = [], set()
    pattern = re.compile(r"scripts/([A-Za-z0-9_\-]+\.py)")
    for path in sorted(ROOT.rglob("*.md")):
        rel = str(path.relative_to(ROOT))
        if rel.startswith("docs/") or ".git" in rel:
            continue
        for name in pattern.findall(path.read_text(encoding="utf-8")):
            seen.add(name)
            if not (SCRIPTS / name).is_file():
                missing.append(f"{rel} → scripts/{name}")
    if missing:
        return False, "文档引用了不存在的脚本：" + "、".join(missing)
    return True, f"{len(seen)} 个脚本引用全部命中"


def step_structural_equivalence() -> Tuple[bool, str]:
    """Structural Equivalence 检查器：自带自检 + 模板 + 四份 fixture 必须全绿。

    这一项**必须**能被变异注入判红（见 `test_structural_equivalence.py` 的反例测试），
    否则它就是一个恒真的空转闸门。
    """
    code, out = _run(["scripts/structural_equivalence_check.py", "--selftest"])
    if code != 0:
        return False, f"--selftest exit={code} {out.strip()[-120:]}"
    targets = [ROOT / "templates" / "structural-equivalence-audit.template.json"]
    targets += sorted((ROOT / "examples" / "structural-equivalence").glob("*.json"))
    if len(targets) < 5:
        return False, f"待校验 artifact 少于 5 份（实际 {len(targets)}）"
    for path in targets:
        rel = path.relative_to(ROOT)
        code, out = _run(["scripts/structural_equivalence_check.py", "--artifact", str(rel)])
        if code != 0:
            return False, f"{rel} exit={code} {out.strip()[-120:]}"
    return True, f"自检 + {len(targets)} 份 artifact 全绿"


STEPS = (
    ("离线测试（含 golden path / parity / linter / deprecated / links）", step_tests),
    ("state_check --selftest", step_selftest),
    ("模板自身通过校验", step_template),
    ("规则表逐字比对（S1—S7 + V1—V24）", step_rule_table_parity),
    ("三方读写表逐格比对", step_readwrite_parity),
    ("文档引用的脚本存在", step_referenced_scripts_exist),
    ("Structural Equivalence（EQ1—EQ13 + NN1—NN14）自检 + 模板 + fixture", step_structural_equivalence),
)


def main() -> int:
    failures = 0
    for title, fn in STEPS:
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001 — 闸门不得因内部异常而静默通过
            ok, detail = False, f"步骤抛异常：{type(exc).__name__}: {exc}"
        if not ok:
            failures += 1
        print(f"[{'ok  ' if ok else 'FAIL'}] {title} —— {detail}")
    print()
    print("FAIL" if failures else "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
