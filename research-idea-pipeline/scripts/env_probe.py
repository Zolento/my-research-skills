#!/usr/bin/env python3
"""env_probe.py — 确认「工作解释器」并做依赖自检

为什么需要它
------------
本 Skill 的脚本依赖第三方包（`literature_search.py` 要 `arxiv`，`refs_index.py` 要
`pypdf`）。这些包通常只装在**某个 conda 环境**或**项目内的 .venv** 里。若直接用系统
`python3` 运行，import 会失败，脚本会"优雅降级"成只用本地库 —— 于是：

    依赖缺失  →  被误读成"源不可用"  →  被误读成"没人在研究"

这三件事必须严格区分。本模块负责前两段的判定。

发现顺序（可配置）
------------------
    1. 当前已激活环境（$CONDA_PREFIX / $VIRTUAL_ENV）
    2. 项目内 .venv / venv / env（自 cwd 向上最多 3 层）
    3. conda 环境（`conda env list`）
    4. PATH 上的 python3 / python
    5. 当前解释器 sys.executable
    6. 都不可用 → **退出码 4，交回用户确认**

选择规则
--------
    * 当前解释器已满足依赖 → 用它（无需切换）
    * 否则 `<唯一>` 合格候选 → 用它
    * 否则 `<多个>` 合格候选 → **不猜**，标记 ambiguous 并全部列出
    * 一个都没有 → chosen = None

用法
----
    python env_probe.py --check                # 人类可读报告
    python env_probe.py --check --json         # 机器可读
    python env_probe.py --which arxiv          # 只打印合格解释器路径（无则空）
    python env_probe.py --ensure arxiv         # 退出码 0 / 4

退出码
------
    0  找到合格解释器
    1  硬错误（参数错误等）
    4  环境不满足（依赖缺失 / 找不到可用解释器）—— 见 SKILL.md §0.2
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_ENV = 4

# 本 Skill 脚本需要的第三方包
DEFAULT_MODULES: Tuple[str, ...] = ("arxiv", "pypdf")

# 在子进程里探测依赖；不用 importlib 是为了能探测「别的解释器」
_PROBE_CODE = r"""
import json, sys, warnings
warnings.filterwarnings("ignore")
out = {}
for name in sys.argv[1:]:
    try:
        mod = __import__(name)
        out[name] = getattr(mod, "__version__", "ok")
    except Exception:
        out[name] = None
out["_python"] = sys.version.split()[0]
out["_executable"] = sys.executable
print(json.dumps(out))
"""

_PYTHON_RELATIVE = ("bin/python", "bin/python3", "Scripts/python.exe")


class _Parser(argparse.ArgumentParser):
    """参数错误必须退出码 1，不能与「环境不满足 4」混淆。"""

    def error(self, message: str):  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)


# ---------------------------------------------------------------------------
# 探测
# ---------------------------------------------------------------------------

def probe_modules(python: Path, modules: Sequence[str], timeout: float = 30.0) -> Dict[str, Any]:
    """在指定解释器里探测依赖。返回 {module: version|None, "_python": ..., "_executable": ...}。

    任何失败（不存在、超时、输出非 JSON）都返回 {}，不抛异常。
    """
    try:
        proc = subprocess.run(
            [str(python), "-W", "ignore", "-c", _PROBE_CODE, *modules],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if proc.returncode != 0:
        return {}
    for line in reversed((proc.stdout or "").strip().splitlines()):
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data
    return {}


def _python_in(prefix: Optional[str]) -> Optional[Path]:
    """给定环境根目录，找出其中的 python 可执行文件。"""
    if not prefix:
        return None
    root = Path(prefix).expanduser()
    for rel in _PYTHON_RELATIVE:
        candidate = root / rel
        if candidate.is_file():
            return candidate
    return None


def _project_venvs(start: Path, levels: int = 3) -> List[Path]:
    """自 start 向上最多 levels 层，找 .venv / venv / env。"""
    found: List[Path] = []
    current = start.resolve()
    for _ in range(levels + 1):
        for name in (".venv", "venv", "env"):
            python = _python_in(str(current / name))
            if python:
                found.append(python)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return found


def _conda_pythons(timeout: float = 30.0) -> List[Path]:
    """列出 conda 各环境的 python。找不到 conda 或解析失败时返回 []。"""
    conda = shutil.which("conda")
    if not conda:
        for candidate in (
            Path.home() / "miniconda3" / "condabin" / "conda",
            Path.home() / "anaconda3" / "condabin" / "conda",
            Path.home() / "miniforge3" / "condabin" / "conda",
            Path("/opt/conda/condabin/conda"),
        ):
            if candidate.is_file():
                conda = str(candidate)
                break
    if not conda:
        return []
    try:
        proc = subprocess.run(
            [conda, "env", "list", "--json"],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        envs = json.loads(proc.stdout or "{}").get("envs", [])
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
        return []
    result: List[Path] = []
    for env in envs:
        python = _python_in(str(env))
        if python:
            result.append(python)
    return result


def _collect_candidates(start: Path) -> List[Tuple[str, Path]]:
    """按发现顺序收集 (来源, 解释器路径)，去重保序。"""
    raw: List[Tuple[str, Path]] = []

    def add(origin: str, path: Optional[Path]) -> None:
        if path is not None:
            raw.append((origin, Path(path)))

    add("active-conda", _python_in(os.environ.get("CONDA_PREFIX")))
    add("active-venv", _python_in(os.environ.get("VIRTUAL_ENV")))
    for python in _project_venvs(start):
        add("project-venv", python)
    for python in _conda_pythons():
        add("conda-env", python)
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            add("path", Path(found))
    add("current", Path(sys.executable))

    seen: set = set()
    ordered: List[Tuple[str, Path]] = []
    for origin, path in raw:
        try:
            key = path.resolve()
        except OSError:
            key = path
        if key in seen:
            continue
        seen.add(key)
        ordered.append((origin, path))
    return ordered


def discover(
    modules: Sequence[str] = DEFAULT_MODULES,
    start: Optional[Path] = None,
    current: Optional[str] = None,
) -> Dict[str, Any]:
    """发现并选择一个满足依赖的工作解释器。

    Args:
        current: 覆盖"当前解释器"（默认 sys.executable）。仅为可测试性而暴露。

    Returns:
        {
          "modules": [...], "candidates": [{origin,path,modules,ok,missing}],
          "chosen": str | None, "ambiguous": bool, "needs_python": [...],
          "reason": str, "current": str
        }
    """
    start = start or Path.cwd()
    current = current or str(Path(sys.executable))
    candidates: List[Dict[str, Any]] = []
    for origin, path in _collect_candidates(start):
        versions = probe_modules(path, modules)
        missing = [m for m in modules if not versions.get(m)]
        candidates.append({
            "origin": origin,
            "path": str(path),
            "modules": {m: versions.get(m) for m in modules},
            "python": versions.get("_python"),
            "ok": not missing,
            "missing": missing,
        })

    qualified = [c for c in candidates if c["ok"]]
    chosen: Optional[str] = None
    ambiguous = False
    reason = ""

    current_ok = next((c for c in qualified if _same(c["path"], current)), None)
    if current_ok is not None:
        chosen = current_ok["path"]
        reason = "当前解释器已满足依赖，无需切换"
    elif len(qualified) == 1:
        chosen = qualified[0]["path"]
        reason = f"唯一合格候选（来源：{qualified[0]['origin']}）"
    elif len(qualified) > 1:
        ambiguous = True
        reason = (f"发现 {len(qualified)} 个合格候选，不自动选择 —— "
                  f"请用户指定，或用 --python 显式传入")
    else:
        reason = ("未找到同时具备 " + ", ".join(modules) + " 的解释器 —— "
                  "请用户指定 conda 环境名或项目 .venv 路径")

    return {
        "modules": list(modules),
        "current": current,
        "candidates": candidates,
        "qualified": [c["path"] for c in qualified],
        "chosen": chosen,
        "ambiguous": ambiguous,
        "needs_python": not qualified,
        "reason": reason,
    }


def _same(a: str, b: str) -> bool:
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return a == b


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def render(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# 工作解释器自检（需要：{', '.join(report['modules'])}）")
    lines.append("")
    lines.append(f"- 当前解释器：{report['current']}")
    lines.append("")
    lines.append("| 来源 | 解释器 | Python | " +
                 " | ".join(report["modules"]) + " | 判定 |")
    lines.append("|---|---|---|" + "---|" * len(report["modules"]) + "---|")
    for c in report["candidates"]:
        versions = " | ".join(str(c["modules"].get(m) or "—") for m in report["modules"])
        verdict = "✅ 可用" if c["ok"] else "❌ 缺 " + ", ".join(c["missing"])
        lines.append(f"| {c['origin']} | `{c['path']}` | {c['python'] or '—'} | "
                     f"{versions} | {verdict} |")
    lines.append("")
    if report["chosen"]:
        lines.append(f"**选定：** `{report['chosen']}` —— {report['reason']}")
    elif report["ambiguous"]:
        lines.append(f"**需要确认：** {report['reason']}")
        for path in report["qualified"]:
            lines.append(f"- 候选：`{path}`")
    else:
        lines.append(f"**环境不满足（退出码 {EXIT_ENV}）：** {report['reason']}")
        lines.append("")
        lines.append("> ⚠️ **依赖缺失 ≠ 源不可用 ≠ 没人做过。** 不得把解释器选错写成"
                     "「检索未达饱和」，更不得据此推断「无人在研究」。")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="env_probe.py",
        description="确认「工作解释器」并做依赖自检（SKILL.md §0.2）",
    )
    parser.add_argument("--check", action="store_true", help="打印自检报告")
    parser.add_argument("--ensure", nargs="*", metavar="MODULE",
                        help="只校验依赖是否就绪；不满足则退出码 4")
    parser.add_argument("--which", nargs="*", metavar="MODULE",
                        help="打印选定的解释器路径（无则打印空行）")
    parser.add_argument("--modules", default=",".join(DEFAULT_MODULES),
                        help=f"要检查的依赖，逗号分隔（默认 {','.join(DEFAULT_MODULES)}）")
    parser.add_argument("--start", default=None, help="项目搜索起点（默认当前目录）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    modules = tuple(m.strip() for m in args.modules.split(",") if m.strip())

    explicit = args.ensure if args.ensure else args.which
    if explicit:
        modules = tuple(explicit)

    report = discover(modules, Path(args.start).expanduser() if args.start else None)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.check:
        print(render(report))
    elif args.which:
        print(report["chosen"] or "")
    elif args.ensure is not None:
        pass  # 只靠退出码
    else:
        print(render(report))

    if report["chosen"] is None:
        return EXIT_ENV
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
