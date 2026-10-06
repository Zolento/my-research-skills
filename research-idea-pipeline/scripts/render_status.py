#!/usr/bin/env python3
"""render_status.py — 把 Research State 投影成人读的路线 STATUS.md（DI-4 的落地判据）

用法：
    python3 scripts/render_status.py --root <项目根> --route <路线字母>
    python3 scripts/render_status.py --root <项目根> --route <路线字母> --check
    python3 scripts/render_status.py <research-state.json> [--out <STATUS.md>]

为什么需要它
------------
目录规范 DI-4 要求「README / STATUS / INDEX 都是人类视图，不是第二份 machine state」。
若 STATUS.md 靠手写，它必然与 research-state.json 漂移 —— 那就退化成第二份人工真相。
本脚本把 STATUS.md 定义为**状态的纯函数**：

    STATUS.md = f(research-state.json)

因此它必须**幂等**：对同一份 state 重复渲染，输出逐字节一致。
`--check` 就是幂等闸门：重新渲染并与磁盘上的文件比对，不一致退出码 3。

**只读 state，只写 STATUS.md。** 不修改任何机器状态。

退出码
------
0  成功（`--check` 时表示磁盘文件与重新渲染结果一致）
3  不一致（`--check` 时磁盘 STATUS.md 已过期）／routes 路径缺失
4  环境不满足（state 文件缺失 / JSON 非法 / 结构不符）
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Dict, List

EXIT_OK = 0
EXIT_HARD = 3
EXIT_ENV = 4

STATE_REL = ".research-idea-pipeline/routes/{route}/research-state.json"
STATUS_REL = "routes/{route}/STATUS.md"


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _items(state: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    value = state.get(key)
    if not isinstance(value, list):
        return []
    return [x for x in value if isinstance(x, dict)]


def _label(obj: Dict[str, Any]) -> str:
    """一行摘要：`C7 — statement（status）`。绝不定长排序，保证幂等。"""
    oid = _text(obj.get("id"))
    statement = _text(obj.get("statement")) or _text(obj.get("question")) \
        or _text(obj.get("what")) or _text(obj.get("kill_condition")) \
        or _text(obj.get("ref"))
    status = _text(obj.get("status")) or _text(obj.get("kind")) \
        or _text(obj.get("closure")) or _text(obj.get("disposition"))
    head = f"`{oid}` — " if oid else ""
    tail = f"（{status}）" if status else ""
    body = statement.splitlines()[0][:160] if statement else ""
    return f"- {head}{body}{tail}".rstrip()


def _section(title: str, rows: List[str]) -> List[str]:
    out = [f"## {title}", ""]
    out.extend(rows if rows else ["_（无）_"])
    out.append("")
    return out


def render(state: Dict[str, Any], route: str) -> str:
    """纯函数：state → STATUS.md 文本。输出必须完全由 state 决定（无时间戳、无随机）。"""
    state_version = state.get("state_version")
    version = state_version if isinstance(state_version, int) and not isinstance(state_version, bool) else "?"

    claims = _items(state, "claims")
    hyps = _items(state, "hypotheses")
    uncs = _items(state, "uncertainties")
    exps = _items(state, "experiments")
    fails = _items(state, "failures")
    assurance = _items(state, "assurance")
    repairs = _items(state, "repairs")
    decision = state.get("decision") if isinstance(state.get("decision"), dict) else {}

    # central thesis：claim 树根（parent 为 null），退而取第一个 claim
    roots = [c for c in claims if c.get("parent") is None] or claims
    thesis = _text(roots[0].get("statement")) if roots else ""
    thesis_status = _text(roots[0].get("status")) if roots else ""

    supported = [_label(c) for c in claims if _text(c.get("status")) == "supported"]
    contradicted = [_label(c) for c in claims if _text(c.get("status")) == "contradicted"]
    active_h = [_label(h) for h in hyps if _text(h.get("status")) in ("active", "elite")]
    critical_u = [_label(u) for u in uncs
                  if _text(u.get("importance")) in ("critical", "high")
                  and _text(u.get("status")) == "open"]
    open_attacks = [_label(a) for a in assurance
                    if _text(a.get("closure")) != "RESOLVED"]
    active_x = [_label(x) for x in exps if _text(x.get("status")) in ("planned", "running")]
    negatives = [_label(f) for f in fails
                 if _text(f.get("kind")) in ("falsified", "unsupported", "inconclusive")] + contradicted
    next_actions: List[str] = [_label(r) for r in repairs if _text(r.get("closure")) != "RESOLVED"]
    for u in uncs:
        if _text(u.get("status")) != "open":
            continue
        t = _text(u.get("cheapest_discriminating_test"))
        if t and t != "TBD":
            next_actions.append(f"- 执行 `{t}` 判别 {_text(u.get('id')) or '该不确定项'}")
    verdict = _text(decision.get("verdict")).upper() or "CONTINUE"

    lines: List[str] = [
        f"# Route {route} — STATUS",
        "",
        "> **本文件是 `research-state.json` 的投影，不是第二份真相。**",
        "> **禁止手改** —— 手改会在下一次 render 时被覆盖。",
        "> 重新生成：`python3 scripts/render_status.py --root <项目根> --route "
        f"{route}`；校验是否过期：加 `--check`（不一致退出码 3）。",
        "",
        "## State version",
        "",
        f"- State version：S{version:04d}" if isinstance(version, int) else "- State version：?",
        "",
        "## Current thesis",
        "",
        thesis or "_（无）_",
        "",
        f"Status: {thesis_status}" if thesis_status else "Status: ?",
        "",
    ]
    lines += _section("Strongest supported findings", supported)
    lines += _section("Active hypotheses", active_h)
    lines += _section("Critical uncertainties", critical_u)
    lines += _section("Open critical attacks", open_attacks)
    lines += _section("Active experiments", active_x)
    lines += _section("Most important negative findings", negatives)
    lines += _section("Next recommended actions", next_actions)
    lines += _section("Current decision", [verdict])
    return "\n".join(lines).rstrip() + "\n"


def _fail(message: str, kind: str = "env") -> int:
    print(f"[{'env' if kind == 'env' else 'hard'}] {message}", file=sys.stderr)
    return EXIT_ENV if kind == "env" else EXIT_HARD


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="把 research-state.json 投影为路线 STATUS.md（幂等；--check 校验是否过期）")
    parser.add_argument("state", nargs="?",
                        help="research-state.json 路径（或改用 --root + --route）")
    parser.add_argument("--root", help="项目根目录")
    parser.add_argument("--route", help="路线字母（如 T）")
    parser.add_argument("--out", help="输出路径（默认 routes/<route>/STATUS.md）")
    parser.add_argument("--check", action="store_true",
                        help="只校验：重新渲染并与磁盘比对，不一致退出码 3")
    args = parser.parse_args(argv)

    if args.root and args.route:
        root = pathlib.Path(args.root).resolve()
        state_path = root / STATE_REL.format(route=args.route)
        out_path = pathlib.Path(args.out) if args.out else root / STATUS_REL.format(route=args.route)
    elif args.state:
        state_path = pathlib.Path(args.state).resolve()
        if args.out:
            out_path = pathlib.Path(args.out)
        elif args.route:
            out_path = state_path.parent.parent.parent.parent / STATUS_REL.format(route=args.route)
        else:
            return _fail("给了 state 路径但没给 --out 或 --route，无法确定输出位置")
    else:
        return _fail("必须给 --root + --route，或给 state 路径 + --out")

    if not state_path.exists():
        return _fail(f"state 文件不存在：{state_path}")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return _fail(f"state 不是合法 JSON：{exc}")
    if not isinstance(state, dict):
        return _fail("state 顶层必须是对象")

    route = args.route or state_path.parent.name
    rendered = render(state, route)

    if args.check:
        if not out_path.exists():
            return _fail(f"STATUS.md 不存在：{out_path}（先渲染一次）", kind="hard")
        on_disk = out_path.read_text(encoding="utf-8")
        if on_disk != rendered:
            print(f"[hard] STATUS.md 已过期：{out_path}", file=sys.stderr)
            print("       重新生成：去掉 --check 再跑一次", file=sys.stderr)
            return EXIT_HARD
        print(f"[ok] STATUS.md 与 state 一致：{out_path}")
        return EXIT_OK

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
    print(f"[ok] 已渲染 {out_path}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
