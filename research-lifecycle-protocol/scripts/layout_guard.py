#!/usr/bin/env python3
"""layout_guard.py — 项目组织规范（DI-1—DI-8）的机械闸门。

**为什么需要它：** `references/project-layout.md` 的八条 DI invariant 与 §7 手工检查清单
写在文档里，执行者是散文。实测六个真实项目全部漂移：未声明的顶层目录、`log/` 与 `logs/`
并存、路线控制目录里 31 份 `research-state.*.json` 备份、`routes/<R>/docs/figures/` 子目录、
缺 `STATUS.md` 的路线。**散文禁令已被证伪，路径合规必须有执行器。**

本脚本只回答一个问题：**这个路径允许写入吗？** 它不判断科学有效性、不判断证据资格、
不做沙箱隔离。科研门禁仍归 `state_check.py` / `experiment_execute.py` / `evidence_outcome.py`。

四层分工（v2.4.0 起）

    项目根 AGENTS.md      → 执行边界：入口、写入边界、文件归属、交付检查
    RLP Skill             → 科研生命周期：R0—R14、state、证据资格、门禁
    项目契约 / 预注册      → 具体实验：配置、判据、预算、数据划分
    本脚本                → 目录合规：DI-1—DI-8 的可执行部分

用法

    python3 layout_guard.py preflight --path routes/A/docs/A003-proposal.md --kind route-doc
    python3 layout_guard.py check                 # 只查 Git 新增/暂存新增文件
    python3 layout_guard.py audit                 # 全树审计（存量项目 triage，不改文件）
    python3 layout_guard.py audit --json          # 机器可读
    python3 layout_guard.py selftest              # 内置自检（发布闸门用）
    python3 layout_guard.py list-kinds

退出码：0 通过 / 3 有 block 级违规 / 4 环境问题（根不存在、双存储根、策略文件非法）。

判定来源

    <control>/project/route-registry.json    路线已注册
    <control>/project/layout-policy.json     允许的例外（窄模式 + 理由 + 授权）
    <control>/routes/<R>/experiments/<XID>/preregistration.json   实验已预注册
    experiments/<R>/<XID>-<slug>/manifest.json                    实验已登记
    <control>/routes/<R>/research-state.json  experiments[].id    状态侧登记
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import rlp_paths as rlp

ROUTE = re.compile(r"^[A-Z]$")
PHASE_DIR = re.compile(r"^R\d{1,2}$")
XID = re.compile(r"^X\d{1,5}$")
XID_SLUG = re.compile(r"^X\d{1,5}-[a-z0-9][a-z0-9-]*$")
REVIEW = re.compile(r"^([A-Z])\d{3}-review-r\d{2,3}\.md$")
DOC = re.compile(
    r"^([A-Z])(\d{3})-(anchor|field-map|discovery|theory|evidence|proposal|"
    r"experiment-plan|result-analysis|decision|narrative)\.md$"
)
ROUTE_DOC_IN_DOCS = re.compile(r"^[A-Z]\d{3}-")

ROOT_FILES = {
    "AGENTS.md", "README.md", "INDEX.md", "LICENSE", "LICENSE.md", "Makefile",
    ".gitignore", ".gitattributes", ".editorconfig", ".gitmodules",
    "pyproject.toml", "setup.py", "setup.cfg", "environment.yml", "CITATION.cff",
}
ROOT_FILE_PATTERNS = ("requirements.txt", "requirements-dev.txt")
PROJECT_DOC_SUBDIRS = {"refs", "dev", "latex", "notes", "theory", "decisions"}

# 标准布局的顶层目录（references/project-layout.md §1）。
LAYOUT_TOP_LEVEL = {
    "src", "scripts", "tests", "configs", "dataset", "docs", "routes",
    "experiments", "results", "logs", "checkpoints", "shared", "store",
}
# 允许存在但不代表布局的隐藏目录：出现即审计告警，不阻断。
DOT_TOLERATED = {".git", ".github", ".gitlab", ".dsh", ".agents", ".agents-home",
                 ".claude", ".idea", ".vscode", ".pytest_cache", "__pycache__",
                 ".mypy_cache", ".ruff_cache", ".venv", ".agent-teams",
                 ".figure-drafts", ".mesh-shim"}
# RLP 自有维护目录（migrate_project_root 用），允许存在。
RLP_OWNED_DOT = {rlp.MAINTENANCE_DIR}
PROTECTED_ROOTS = {"dataset", "store", ".git"}

#: Skill 注入的受管块。与 `mri_training.py` 的 BEGIN/END 标记一致。
MANAGED_BLOCKS = (("<!-- BEGIN RLP MRI TRAINING -->", "<!-- END RLP MRI TRAINING -->"),)

KINDS = ("code", "script", "test", "config", "route-doc", "project-doc",
         "manuscript", "experiment", "result", "log", "checkpoint", "control",
         "scratch")

BLOCK, WARN = "block", "warn"


class GuardEnvError(RuntimeError):
    """环境问题（退出码 4），与路径违规（3）严格分离。"""


# --------------------------------------------------------------------------- #
# 策略与注册表
# --------------------------------------------------------------------------- #

def control_root(project: Path) -> Path:
    """只读解析控制根；双根并存 fail closed（与 rlp_paths 一致）。"""
    try:
        return rlp.resolve_storage_root(project).root
    except rlp.AmbiguousStorageRoot as exc:  # 双存储根不允许静默选一个
        raise GuardEnvError(str(exc)) from None


def _policy_path(project: Path, control: Path) -> Optional[Path]:
    preferred = control / "project" / "layout-policy.json"
    if preferred.is_file():
        return preferred
    legacy = project / "docs" / "dev" / "path-allowlist.json"  # 参考工具的旧位置
    return legacy if legacy.is_file() else None


def load_policy(project: Path, control: Path) -> Dict[str, Any]:
    path = _policy_path(project, control)
    if path is None:
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GuardEnvError(f"{path}: {exc}") from None
    if not isinstance(obj, dict):
        raise GuardEnvError(f"{path}: 顶层必须是对象")
    extra = obj.get("additional_paths", [])
    if not isinstance(extra, list):
        raise GuardEnvError(f"{path}: additional_paths 必须是数组")
    for pattern in extra:
        if not isinstance(pattern, str) or not _narrow_pattern(pattern):
            raise GuardEnvError(f"{path}: 不合法的例外模式 {pattern!r}")
    for key in ("allow_top_level", "additional_doc_subdirs"):
        if not isinstance(obj.get(key, []), list):
            raise GuardEnvError(f"{path}: {key} 必须是数组")
    return obj


def _narrow_pattern(pattern: str) -> bool:
    """例外必须窄：不得以通配符开头、不得越级、不得覆盖受保护根。"""
    if pattern.startswith(("/", "**", "./", "../")) or "/" not in pattern:
        return False
    if "\\" in pattern or ".." in pattern.split("/"):
        return False
    head = pattern.split("/")[0]
    if any(ch in head for ch in "*?[]"):
        return False
    return head not in PROTECTED_ROOTS | {rlp.LEGACY_STORAGE_ROOT}


def registered_routes(project: Path, control: Path) -> Tuple[set, str]:
    """路线注册来源：registry（权威）→ 路线 README（兜底）。"""
    routes: set = set()
    registry = control / "project" / "route-registry.json"
    if registry.is_file():
        try:
            payload = json.loads(registry.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise GuardEnvError(f"{registry}: {exc}") from None
        routes |= _routes_from_registry(payload)
        if routes:
            return routes, str(registry)
    on_disk = {p.name for p in (project / "routes").glob("*")
               if p.is_dir() and ROUTE.match(p.name) and (p / "README.md").is_file()}
    return routes | on_disk, str(project / "routes") if on_disk else "none"


def _routes_from_registry(payload: Any) -> set:
    """只认显式字段，不做任意文本推断（避免把标题里的字母当路线）。"""
    routes: set = set()

    def add_route(value: Any) -> None:
        if isinstance(value, str):
            candidate = value.strip().rstrip("/")
            if ROUTE.match(candidate):
                routes.add(candidate)
            elif candidate.startswith("routes/"):
                seg = candidate.split("/")
                if len(seg) >= 2 and ROUTE.match(seg[1]):
                    routes.add(seg[1])

    def walk(node: Any, key: Optional[str] = None) -> None:
        if isinstance(node, dict):
            for name in ("name", "id", "route"):
                if name in node:
                    add_route(node[name])
            if "path" in node:
                add_route(node["path"])
            for name, value in node.items():
                if ROUTE.match(str(name)) and isinstance(value, dict):
                    routes.add(name)
                walk(value, name)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, str):
                    add_route(item)
                else:
                    walk(item, key)

    walk(payload)
    return routes


# ---------------------------------------------------------------------------
# 正式文档 ID（DI-8）：唯一分配 + 独占创建
# ---------------------------------------------------------------------------
# 真实事故：两个并行会话各自把同一条路线的新文档编成 F009，第二个写盘时才发现。
# 这里只做两件事：把「已占用的 ID」算出来，以及用 O_EXCL 建新文件。不建第二套登记库。

DOC_ID_PREFIX = re.compile(r"^([A-Z])(\d{3})-")
DOC_ID_FILE = re.compile(r"^([A-Z])(\d{3})-([a-z0-9][a-z0-9-]*)\.md$")


def doc_dirs(project: Path, control: Path, route: str) -> List[Path]:
    """一条路线上所有可能存放正式文档的目录（运行时控制根 + 旧根）。"""
    seen: List[Path] = []
    # 正式文档住在项目侧 routes/<R>/docs；控制根与旧根里也可能有历史副本。
    for base in (project, control, project / rlp.LEGACY_STORAGE_ROOT):
        candidate = base / "routes" / route / "docs"
        if candidate.is_dir() and candidate not in seen:
            seen.append(candidate)
    return seen


REVIEW_ID = re.compile(r"^([A-Z])(\d{3})-review-r(\d{2,3})\.md$")


def _doc_files(project: Path, control: Path, route: str) -> List[Path]:
    files: List[Path] = []
    for directory in doc_dirs(project, control, route):
        files.extend(sorted(directory.glob("*.md")))
    return files


def _display(project: Path, path: Path) -> str:
    try:
        return path.relative_to(project).as_posix()
    except ValueError:
        return str(path)


def doc_id_index(project: Path, control: Path, route: str) -> Dict[str, List[str]]:
    """ID → 占用它的**主文档**。

    关联 review（`F003-review-r01.md`）共享主文档的 ID，是合法布局：
    `F003-theory.md` 与 `F003-review-r01.md` 可以同时存在。review 由
    :func:`review_index` 单独统计。
    """
    index: Dict[str, List[str]] = {}
    for entry in _doc_files(project, control, route):
        if REVIEW_ID.match(entry.name):
            continue
        match = DOC_ID_PREFIX.match(entry.name)
        if not match:
            continue
        doc_id = match.group(1) + match.group(2)
        index.setdefault(doc_id, []).append(_display(project, entry))
    return index


def review_index(project: Path, control: Path, route: str
                 ) -> Dict[str, Dict[str, List[str]]]:
    """ID → {轮次: [文件名]}。同一轮次出现在多处才是冲突。"""
    index: Dict[str, Dict[str, List[str]]] = {}
    for entry in _doc_files(project, control, route):
        match = REVIEW_ID.match(entry.name)
        if not match:
            continue
        doc_id = match.group(1) + match.group(2)
        round_no = match.group(3)
        index.setdefault(doc_id, {}).setdefault(round_no, []).append(
            _display(project, entry))
    return index


def doc_id_conflicts(project: Path, control: Path, route: str) -> List[Dict[str, Any]]:
    """只报真正的冲突。

    - `main_duplicate`：两个主文档抢同一个 ID —— BLOCK。
    - `review_duplicate`：同一轮 review 出现两份 —— BLOCK。
    - `review_without_main`：只有 review、没有主文档 —— 需要人确认。
    """
    conflicts: List[Dict[str, Any]] = []
    main_ids = doc_id_index(project, control, route)
    reviews = review_index(project, control, route)
    for doc_id, files in sorted(main_ids.items()):
        if len(files) > 1:
            conflicts.append({"id": doc_id, "route": route, "kind": "main_duplicate",
                              "severity": "block", "files": files})
    for doc_id, rounds in sorted(reviews.items()):
        for round_no, files in sorted(rounds.items()):
            if len(files) > 1:
                conflicts.append({"id": doc_id, "route": route,
                                  "kind": "review_duplicate", "severity": "block",
                                  "round": round_no, "files": files})
        if doc_id not in main_ids:
            conflicts.append({"id": doc_id, "route": route,
                              "kind": "review_without_main", "severity": "warn",
                              "files": sorted(name for files in rounds.values()
                                              for name in files)})
    return conflicts


def occupied_ids(project: Path, control: Path, route: str) -> List[int]:
    """主文档与 review 共同占用的序号。删掉主文档后 review 仍在，ID 也不能重用。"""
    numbers = {int(doc_id[1:]) for doc_id in doc_id_index(project, control, route)}
    numbers |= {int(doc_id[1:]) for doc_id in review_index(project, control, route)}
    return sorted(numbers)


def next_doc_id(project: Path, control: Path, route: str) -> str:
    """该路线下一个未占用的 ID（只读计算，不创建任何文件）。"""
    used = occupied_ids(project, control, route)
    candidate = (max(used) + 1) if used else 1
    if candidate > 999:
        raise GuardEnvError(f"路线 {route} 的文档 ID 已用尽（超过 999）")
    return f"{route}{candidate:03d}"


DOC_FILE_NAME = re.compile(r"^([A-Z])(\d{3})-([a-z0-9][a-z0-9-]*)\.md$")

#: 分配 ID 的短时锁。放在控制根里，和迁移用的维护锁分开：两者生命周期完全不同。
DOC_LOCK_NAME = ".doc-id.lock"
DOC_LOCK_TIMEOUT = 5.0


@contextlib.contextmanager
def doc_id_lock(control: Path, timeout: float = DOC_LOCK_TIMEOUT):
    """短时排他锁：覆盖「查最大 ID → 选号 → 建文件」这一小段。"""
    import time
    handle = os.open(str(control / DOC_LOCK_NAME), os.O_CREAT | os.O_RDWR, 0o644)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise GuardEnvError(
                        f"等待文档 ID 锁超时（{timeout:g}s）：{control / DOC_LOCK_NAME}")
                time.sleep(0.01)
        yield
    finally:
        try:
            fcntl.flock(handle, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(handle)


def _validate_route(project: Path, control: Path, route: str) -> None:
    if not re.fullmatch(r"[A-Z]", route or ""):
        raise GuardEnvError(f"路线编号必须是单个大写字母：{route!r}")
    routes, source = registered_routes(project, control)
    if route not in routes:
        raise GuardEnvError(
            f"路线 {route} 未注册（来源 {source}）：先按目录规范建 routes/{route}/ 并登记，"
            "分配器不会为未授权路线创建任何目录")


def _doc_directory(project: Path, control: Path, route: str) -> Path:
    """已存在的路线文档目录；一个都没有就拒绝，不替调用者建目录。"""
    directories = doc_dirs(project, control, route)
    if not directories:
        raise GuardEnvError(
            f"路线 {route} 没有 docs 目录：先建 routes/{route}/docs/（项目侧优先），"
            "分配器不创建路线骨架")
    return directories[0]


#: preflight 接受的路线文档 slug（DI-8 枚举）。分配器只造这些名字。
#: 自由 slug（如 `F009-mist-inr-candidate.md`）能通过 audit，但过不了 preflight，
#: 所以不在这里自动生成 —— 那是既有规则，本轮不为新工具放宽。
DOC_SLUGS = ("anchor", "field-map", "discovery", "theory", "evidence", "proposal",
             "experiment-plan", "result-analysis", "decision", "narrative")


def allocate_doc(project: Path, route: str, slug: Any = None,
                 doc_type: Any = None) -> Dict[str, Any]:
    """在短时锁内分配 ID 并独占创建骨架文件。

    `slug` 与 `doc_type` 都必须是 DI-8 枚举值；只给 `doc_type` 时用它当 slug。
    骨架里写好 frontmatter，`preflight` 与 `doc_quality check` 都能直接通过。
    """
    project = Path(project).expanduser().resolve()
    control = control_root(project)
    candidate = doc_type or slug
    if slug and doc_type and slug != doc_type:
        raise GuardEnvError(f"slug 与 type 不一致：{slug} / {doc_type}")
    if not candidate:
        raise GuardEnvError("需要 --type（或 --slug），取值：" + ", ".join(DOC_SLUGS))
    if candidate not in DOC_SLUGS:
        raise GuardEnvError(
            f"slug {candidate!r} 不是 DI-8 枚举值；preflight 会拒绝自由 slug。"
            "可用：" + ", ".join(DOC_SLUGS))
    _validate_route(project, control, route)
    directory = _doc_directory(project, control, route)
    attempts = 0
    with doc_id_lock(control):
        if candidate == "anchor":
            if doc_id_index(project, control, route).get(f"{route}000"):
                raise GuardEnvError(f"路线 {route} 已有 anchor；一条路线只有一个 000")
            doc_id = f"{route}000"
            name = f"{doc_id}-anchor.md"
            attempts = 1
            target = directory / name
            if target.exists():
                raise GuardEnvError(f"anchor 文件已存在：{target}")
            handle = os.open(str(target), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        else:
            handle = None
            for _ in range(1000):
                attempts += 1
                doc_id = next_doc_id(project, control, route)
                name = f"{doc_id}-{candidate}.md"
                if not DOC_FILE_NAME.match(name):
                    raise GuardEnvError(f"生成的文件名不符合 <R><NNN>-<slug>.md：{name}")
                target = directory / name
                if not str(target.resolve()).startswith(str(directory.resolve()) + os.sep):
                    raise GuardEnvError(f"目标路径逃出文档目录：{target}")
                try:
                    handle = os.open(str(target), os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                                     0o644)
                    break
                except FileExistsError:
                    continue
            if handle is None:
                raise GuardEnvError("连续 1000 次都拿不到空闲 ID，疑似并发写入失控")
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(
                f"---\nid: {doc_id}\nroute: {route}\ntype: {candidate}\n"
                f"subtype: null\nstatus: draft\n---\n\n# {doc_id} \n\n")
    return {"id": doc_id, "path": str(target), "created": True,
            "attempts": attempts, "locked": True, "type": candidate}


def xid_registered(project: Path, control: Path, route: str, xid: str) -> Tuple[bool, str]:
    """实验必须真的登记过：预注册 / manifest / canonical state 三处之一。"""
    prereg = control / "routes" / route / "experiments" / xid / "preregistration.json"
    if prereg.is_file():
        return True, "preregistration"
    for directory in (project / "experiments" / route).glob(f"{xid}-*"):
        if directory.is_dir() and (directory / "manifest.json").is_file():
            return True, "manifest"
    state = control / "routes" / route / "research-state.json"
    if state.is_file():
        try:
            payload = json.loads(state.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False, "state 不可读"
        for entry in payload.get("experiments", []) or []:
            if isinstance(entry, dict) and str(entry.get("id", "")).split("-")[0] == xid:
                return True, "state"
    return False, "未登记"


# --------------------------------------------------------------------------- #
# 路径分类
# --------------------------------------------------------------------------- #

def normalize(raw: str) -> Tuple[Optional[str], str]:
    if not raw or "\\" in raw:
        return None, "使用仓库相对 POSIX 路径（禁止反斜杠）"
    parts = raw.split("/")
    if raw.startswith("/") or PurePosixPath(raw).is_absolute():
        return None, "禁止绝对路径"
    if any(part in {"", ".", ".."} for part in parts) or raw.endswith("/"):
        return None, "禁止空段、点段与结尾斜杠"
    return str(PurePosixPath(raw)), ""


def classify(rel: str, project: Path, control: Path, policy: Dict[str, Any]) -> Tuple[Optional[str], str]:
    parts = rel.split("/")
    head = parts[0]
    control_name = control.name

    if PHASE_DIR.match(head):
        return None, "R 阶段是系统行为，不得成为目录（DI-1）"
    if head in PROTECTED_ROOTS:
        return None, f"{head}/ 是只读入口，禁止经本闸门写入"
    if head == rlp.LEGACY_STORAGE_ROOT and control_name != rlp.LEGACY_STORAGE_ROOT:
        return None, f"{rlp.LEGACY_STORAGE_ROOT}/ 是旧控制根，只读"
    if len(parts) == 1:
        if rel in ROOT_FILES or any(rel.startswith(p[:-4]) and rel.endswith(".txt")
                                    for p in ROOT_FILE_PATTERNS):
            return "project-doc", ""
        return None, "根级新文件需要显式批准（AGENTS.md 的已批准路径）"

    if head == control_name:
        if control_name == rlp.LEGACY_STORAGE_ROOT:
            return None, "旧控制根只读；先运行 migrate_project_root.py"
        return ("scratch" if "runtime" in parts[:3] else "control"), ""

    if head == ".github" and len(parts) > 2 and parts[1] in {"workflows", "ISSUE_TEMPLATE"}:
        return "config", ""

    if head in {"src", "shared"} and len(parts) > 1:
        return "code", ""
    if head == "scripts" and len(parts) > 1:
        return "script", ""
    if head == "tests" and len(parts) > 1:
        return "test", ""
    if head == "configs" and len(parts) > 1:
        if len(parts) > 3 and parts[1] == "routes":
            route = parts[2]
            if not ROUTE.match(route):
                return None, "configs/routes/<R>/ 的 <R> 必须是单个大写字母"
            known, _ = registered_routes(project, control)
            if route not in known:
                return None, f"路线 {route} 未注册；先由 RLP 授权并创建"
        return "config", ""

    if head == "docs":
        if len(parts) < 3:
            return None, "docs/ 下必须有项目级类别子目录"
        if parts[1] not in PROJECT_DOC_SUBDIRS | set(policy.get("additional_doc_subdirs", [])):
            return None, f"docs/{parts[1]}/ 不是已声明的项目级类别"
        if parts[1] == "latex":
            return "manuscript", ""
        if parts[1] == "refs":
            return "project-doc", ""
        if ROUTE_DOC_IN_DOCS.match(parts[-1]):
            return None, "路线正式文档必须放 routes/<R>/docs/"
        return "project-doc", ""

    if head == "routes":
        if len(parts) < 3 or not ROUTE.match(parts[1]):
            return None, "routes/ 下必须是单字母路线目录"
        route = parts[1]
        known, _ = registered_routes(project, control)
        if route not in known:
            return None, f"路线 {route} 未注册；RLP 授权后才能创建"
        if len(parts) == 3 and parts[2] in {"README.md", "STATUS.md", "INDEX.md"}:
            return "project-doc", ""
        if len(parts) == 4 and parts[2] == "docs":
            doc = DOC.match(parts[3])
            review = REVIEW.match(parts[3])
            if doc and doc.group(1) == route and (
                (doc.group(3) == "anchor") == (doc.group(2) == "000")
            ):
                return "route-doc", ""
            if review and review.group(1) == route:
                return "route-doc", ""
            return None, "路线文档必须用 RLP 枚举 slug 与 ID，且保持扁平"
        return None, "禁止嵌套路线文档、routes/*/src/ 或任意路线子目录"

    if head in {"experiments", "results", "logs", "checkpoints"}:
        if len(parts) < 4 or not ROUTE.match(parts[1]):
            return None, "必须是 <root>/<路线>/<XID>/..."
        route = parts[1]
        known, _ = registered_routes(project, control)
        if route not in known:
            return None, f"路线 {route} 未注册"
        raw_xid = parts[2]
        match = XID.match(raw_xid) or XID_SLUG.match(raw_xid)
        if not match:
            return None, "必须使用已登记的 XID，例如 X021 或 X021-identifiability"
        xid = raw_xid.split("-", 1)[0]
        ok, source = xid_registered(project, control, route, xid)
        if not ok:
            return None, f"{xid} 未登记（{source}）；先走 RLP issue/run"
        if head == "experiments":
            if "-" not in raw_xid:
                return None, "实验目录需要 XID-slug"
            if len(parts) != 4 or parts[3] not in {"README.md", "manifest.json", "config.yaml"}:
                return None, "实验登记只允许 README.md / manifest.json / config.yaml"
        if head in {"results", "logs", "checkpoints"} and "-" in raw_xid:
            return None, f"{head}/ 只允许裸 XID，不带 slug"
        return {"experiments": "experiment", "results": "result",
                "logs": "log", "checkpoints": "checkpoint"}[head], ""

    for pattern in policy.get("additional_paths", []):
        if PurePosixPath(rel).match(pattern):
            return "project-doc", f"已批准例外：{pattern}"
    return None, "未识别的位置；请复用已允许目录，或登记窄范围例外"


def check_path(project: Path, path: str, kind: Optional[str] = None,
               control: Optional[Path] = None,
               policy: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """单路径判定。软链接穿越一律拒绝（保守）；受保护入口先于分类拒绝。"""
    project = Path(project).resolve()
    control = control or control_root(project)
    policy = policy if policy is not None else load_policy(project, control)
    rel, error = normalize(path)
    if rel is None:
        return False, error
    target = project / rel
    try:
        if not target.resolve(strict=False).is_relative_to(project):
            return False, "路径经软链接逃出仓库"
    except OSError:
        return False, "路径无法解析"
    node = project
    for part in rel.split("/"):
        node = node / part
        if node.is_symlink():
            return False, f"软链接穿越受保护：{node.relative_to(project)}"
    actual, reason = classify(rel, project, control, policy)
    if actual is None:
        return False, reason
    if kind and kind != actual:
        return False, f"类型不符：请求 {kind}，判定 {actual}"
    return True, f"判定 {actual}" + (f"（{reason}）" if reason else "")


# --------------------------------------------------------------------------- #
# 全树审计（存量项目 triage）
# --------------------------------------------------------------------------- #

def managed_block_bytes(data: bytes) -> int:
    """Skill 注入的受管块字节数（`BEGIN/END RLP MRI TRAINING`，可有多段同类块）。"""
    text = data.decode("utf-8", "replace")
    total = 0
    for begin, end in MANAGED_BLOCKS:
        start = 0
        while True:
            left = text.find(begin, start)
            if left < 0:
                break
            right = text.find(end, left)
            if right < 0:
                break
            total += len(text[left:right + len(end)].encode("utf-8"))
            start = right + len(end)
    return total


def audit(project: Path) -> List[Dict[str, str]]:
    project = Path(project).resolve()
    control = control_root(project)
    policy = load_policy(project, control)
    findings: List[Dict[str, str]] = []

    def add(severity: str, code: str, path: str, message: str) -> None:
        findings.append({"severity": severity, "code": code, "path": path,
                         "message": message})

    allowed = LAYOUT_TOP_LEVEL | set(policy.get("allow_top_level", []))
    allowed |= {control.name, rlp.LEGACY_STORAGE_ROOT}  # 兼容旧控制根

    for entry in sorted(project.iterdir()):
        name = entry.name
        if name.startswith(".") and name not in allowed:
            if name in ROOT_FILES:
                continue
            if name in {".rlp-archive", ".rlp-backup", ".rlp-tmp"}:
                add(WARN, "ROOT-2", name + "/", "RLP 自制备份目录，建议归档")
                continue
            if name in RLP_OWNED_DOT or name in DOT_TOLERATED:
                continue
            add(WARN, "ROOT-1", name + ("/" if entry.is_dir() else ""),
                "未声明的隐藏条目")
            continue
        if PHASE_DIR.match(name) and entry.is_dir():
            add(BLOCK, "DI-1", name + "/", "R 阶段是系统行为，不得成为目录（DI-1）")
            continue
        if name == "log":
            add(BLOCK, "ROOT-3", "log/", "日志统一用 logs/，禁止 log/ 与 logs/ 并存")
            continue
        if entry.is_dir():
            if name not in allowed:
                add(BLOCK, "ROOT-1", name + "/", "未声明的顶层目录")
        elif name not in allowed:
            if name in ROOT_FILES or any(name.startswith(p[:-4]) and name.endswith(".txt")
                                         for p in ROOT_FILE_PATTERNS):
                continue
            add(BLOCK, "ROOT-1", name, "未声明的根级文件（根级只留 AGENTS/README/INDEX）")

    agents = project / "AGENTS.md"
    limit = int(policy.get("agents_max_bytes", 20480))
    warn_at = int(policy.get("agents_warn_bytes", 12000))
    if agents.is_file():
        size = agents.stat().st_size
        # Skill 托管的块不是项目自己写的内容：它由 mri_training.py 注入并按 SHA 校验，
        # 手改即违规。体量预算只计**项目自撰部分**，否则「加一段受管规则」就会让
        # 项目被迫删掉自己的执行边界。这不是放宽阈值，是把被注入的部分排除在计分外。
        owned = managed_block_bytes(agents.read_bytes())
        measured = size - owned
        suffix = f"（已扣除 Skill 受管块 {owned} B，实测项目自撰 {measured} B）" if owned else ""
        if measured > limit:
            add(BLOCK, "AGENTS-1", "AGENTS.md",
                f"项目自撰部分 {measured} B 超过上限 {limit} B{suffix}："
                "AGENTS.md 管执行边界，不承载 RLP 规则副本")
        elif measured > warn_at:
            add(WARN, "AGENTS-1", "AGENTS.md",
                f"项目自撰部分 {measured} B 超过告警线 {warn_at} B{suffix}")

    routes_dir = project / "routes"
    if routes_dir.is_dir():
        known, _ = registered_routes(project, control)
        for route_dir in sorted(p for p in routes_dir.iterdir() if p.is_dir()):
            route = route_dir.name
            rel_route = f"routes/{route}"
            if not ROUTE.match(route):
                add(BLOCK, "ROOT-4", rel_route + "/", "路线目录必须是单个大写字母")
                continue
            for needed in ("README.md", "STATUS.md", "INDEX.md"):
                if not (route_dir / needed).is_file():
                    add(BLOCK, "DI-4", f"{rel_route}/{needed}", "路线三件套缺失")
            for child in sorted(route_dir.iterdir()):
                if child.name == "docs":
                    continue
                if child.name in {"README.md", "STATUS.md", "INDEX.md"}:
                    continue
                if child.is_dir() and child.name == "src":
                    add(BLOCK, "DI-6", f"{rel_route}/src/", "路线不得复制代码（DI-6）")
                else:
                    add(WARN, "ROUTE-1", f"{rel_route}/{child.name}",
                        "路线根只放三件套与 docs/")
            docs = route_dir / "docs"
            if docs.is_dir():
                for child in sorted(docs.iterdir()):
                    if child.is_dir():
                        add(BLOCK, "DI-4", f"{rel_route}/docs/{child.name}/",
                            "routes/<R>/docs/ 必须扁平，禁止子目录")
                    elif not (DOC.match(child.name) or REVIEW.match(child.name)):
                        add(WARN, "DI-8", f"{rel_route}/docs/{child.name}",
                            "文件名不符合 <R><NNN>-<slug>.md 或 review 命名")
            if route not in known:
                add(WARN, "REG-1", rel_route + "/", "路线未在 route-registry.json 登记")

    docs_root = project / "docs"
    if docs_root.is_dir():
        for child in sorted(docs_root.iterdir()):
            if child.is_file() and ROUTE_DOC_IN_DOCS.match(child.name):
                add(BLOCK, "DI-8", f"docs/{child.name}", "路线正式文档不得放根 docs/")
            elif child.is_dir() and child.name not in (PROJECT_DOC_SUBDIRS |
                                                      set(policy.get("additional_doc_subdirs", []))):
                add(WARN, "DI-8", f"docs/{child.name}/", "未声明的项目级类别子目录")

    for area in ("experiments", "results", "logs", "checkpoints"):
        area_dir = project / area
        if not area_dir.is_dir():
            continue
        for route_dir in sorted(p for p in area_dir.iterdir() if p.is_dir()):
            route = route_dir.name
            if not ROUTE.match(route):
                add(BLOCK, "DI-5", f"{area}/{route}/", "必须是 <area>/<路线>/")
                continue
            known, _ = registered_routes(project, control)
            if route not in known:
                add(BLOCK, "DI-5", f"{area}/{route}/", f"路线 {route} 未注册")
            for xid_dir in sorted(p for p in route_dir.iterdir() if p.is_dir()):
                name = xid_dir.name
                if not (XID.match(name) or XID_SLUG.match(name)):
                    add(BLOCK, "DI-5", f"{area}/{route}/{name}/", "目录名不是合法 XID")
                    continue
                xid = name.split("-", 1)[0]
                if area in {"results", "logs", "checkpoints"} and "-" in name:
                    add(BLOCK, "DI-5", f"{area}/{route}/{name}/", f"{area}/ 只允许裸 XID")
                ok, source = xid_registered(project, control, route, xid)
                if not ok:
                    add(BLOCK, "DI-5", f"{area}/{route}/{name}/",
                        f"{xid} 未登记（{source}）")
                if area == "experiments":
                    extra = [c.name for c in xid_dir.iterdir()
                             if c.name not in {"README.md", "manifest.json", "config.yaml"}]
                    if extra:
                        add(WARN, "DI-5", f"{area}/{route}/{name}/",
                            "实验登记目录只放 README/manifest/config：" + ", ".join(extra[:4]))

    if control.is_dir():
        for state_dir in sorted((control / "routes").glob("*")):
            if not state_dir.is_dir():
                continue
            for stray in sorted(state_dir.glob("research-state.*.json")):
                add(BLOCK, "DI-3", f"{control.name}/routes/{state_dir.name}/{stray.name}",
                    "一条路线只允许一个 canonical state；历史进 history/")
        for stray in sorted(control.glob("*.json")):
            if stray.name != "preset-registry.json" and stray.name not in {
                "router-fixtures.json", "release.json"
            }:
                add(WARN, "CTRL-1", f"{control.name}/{stray.name}", "控制根散落的 json")
    return findings


# --------------------------------------------------------------------------- #
# Git 新增文件
# --------------------------------------------------------------------------- #

def git_new_files(project: Path) -> List[str]:
    def run(args: Sequence[str]) -> bytes:
        proc = subprocess.run(["git", "-C", str(project), *args],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise GuardEnvError("git 不可用或无仓库：" +
                                proc.stderr.decode("utf-8", "replace").strip()[:200])
        return proc.stdout

    untracked = run(["ls-files", "--others", "--exclude-standard", "-z"])
    staged = run(["diff", "--cached", "--name-only", "--diff-filter=A", "-z"])
    return sorted({chunk.decode("utf-8", "surrogateescape")
                   for chunk in (untracked + staged).split(b"\0") if chunk})


# --------------------------------------------------------------------------- #
# 自检
# --------------------------------------------------------------------------- #

def _fixture(root: Path) -> None:
    (root / "routes/A").mkdir(parents=True)
    (root / "routes/A/README.md").write_text("# A", encoding="utf-8")
    control = root / rlp.STORAGE_ROOT / "routes/A/experiments/X021"
    control.mkdir(parents=True)
    (control / "preregistration.json").write_text("{}", encoding="utf-8")
    (root / rlp.STORAGE_ROOT / "project").mkdir(parents=True)
    (root / "docs/refs").mkdir(parents=True)


def selftest() -> int:
    failures = 0

    def expect(label: str, condition: bool) -> None:
        nonlocal failures
        if not condition:
            failures += 1
            print(f"FAIL  {label}")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "proj"
        _fixture(root)
        for path, kind in [
            ("src/models/net.py", "code"), ("scripts/train.py", "script"),
            ("tests/test_fft.py", "test"), ("configs/routes/A/X021.yaml", "config"),
            ("routes/A/docs/A003-proposal.md", "route-doc"),
            ("routes/A/docs/A000-anchor.md", "route-doc"),
            ("routes/A/docs/A003-review-r01.md", "route-doc"),
            ("experiments/A/X021-trial/README.md", "experiment"),
            ("results/A/X021/figures/comparison.png", "result"),
            ("logs/A/X021/run1/train.log", "log"),
            ("checkpoints/A/X021/run1/best_val.pt", "checkpoint"),
            ("docs/refs/papers/paper.pdf", "project-doc"),
            (f"{rlp.STORAGE_ROOT}/runtime/temp.txt", "scratch"),
        ]:
            ok, reason = check_path(root, path, kind)
            expect(f"allow {path} ({reason})", ok)
        for path in [
            "random-output/final.md", "R0/study.md", "R9/experiment.md",
            "routes/A/src/net.py", "routes/A/docs/new-plan.md",
            "routes/A/docs/extra/A004-theory.md", "routes/A/docs/B001-proposal.md",
            "routes/A/docs/A000-proposal.md", "routes/A/docs/A001-anchor.md",
            "experiments/A/X021-trial/model.pt", "results/A/X021-trial/metrics.json",
            "results/A/X999/metrics.json", "docs/A001-proposal.md",
            "dataset/raw/sample.h5", "store/weights.pt", "log/A/X021/train.log",
            "../escape.md", "/tmp/move.txt", "results_new/X021/foo.json",
            "docs/unknown-category/x.md",
        ]:
            ok, reason = check_path(root, path)
            expect(f"block {path} ({reason})", not ok)
        ok, _ = check_path(root, "docs/dev/dev-notes.md", "route-doc")
        expect("kind mismatch blocked", not ok)

        outside = Path(tmp) / "outside"
        outside.mkdir()
        (root / "results").symlink_to(outside, target_is_directory=True)
        ok, reason = check_path(root, "results/A/X021/output.pt")
        expect(f"symlink escape blocked ({reason})", not ok)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "proj"
        _fixture(root)
        (root / f"{rlp.STORAGE_ROOT}/project/layout-policy.json").write_text(
            json.dumps({"additional_paths": ["paper/*.tex"]}), encoding="utf-8")
        ok, _ = check_path(root, "paper/main.tex")
        expect("narrow allowlist allows one level", ok)
        ok, _ = check_path(root, "paper/arbitrary/extra.tex")
        expect("narrow allowlist does not cover deeper paths", not ok)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "proj"
        _fixture(root)
        (root / f"{rlp.STORAGE_ROOT}/project/layout-policy.json").write_text(
            json.dumps({"additional_paths": ["**/*.md"]}), encoding="utf-8")
        try:
            check_path(root, "x/y.md")
            expect("unsafe pattern rejected", False)
        except GuardEnvError:
            pass

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "proj"
        _fixture(root)
        (root / "routes/B").mkdir()
        (root / "routes/B/README.md").write_text("# B", encoding="utf-8")
        (root / "R9").mkdir()
        (root / "log").mkdir()
        (root / "routes/A/docs/figures").mkdir(parents=True)
        (root / f"{rlp.STORAGE_ROOT}/routes/A/research-state.v2.json").write_text("{}", encoding="utf-8")
        (root / "docs/A004-theory.md").write_text("x", encoding="utf-8")
        (root / "AGENTS.md").write_text("x" * 30000, encoding="utf-8")
        codes = {f["code"] for f in audit(root)}
        for code in ("DI-1", "DI-3", "DI-4", "DI-8", "ROOT-3", "AGENTS-1"):
            expect(f"audit reports {code}", code in codes)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "proj"
        _fixture(root)
        (root / f"{rlp.STORAGE_ROOT}/project/route-registry.json").write_text(
            json.dumps({"routes": [{"name": "A", "path": "routes/A"}]}), encoding="utf-8")
        routes, source = registered_routes(root, root / rlp.STORAGE_ROOT)
        expect(f"registry routes parsed ({source})", routes == {"A"})
        (root / f"{rlp.STORAGE_ROOT}/project/route-registry.json").write_text(
            json.dumps({"routes": [{"name": "标题含 A 的路线", "path": "routes/A/"}]}),
            encoding="utf-8")
        routes, _ = registered_routes(root, root / rlp.STORAGE_ROOT)
        expect("title is not a route id", routes == {"A"})

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "proj"
        _fixture(root)
        legacy = root / "legacy"
        (legacy / "routes/A").mkdir(parents=True)
        (legacy / "routes/A/research-state.json").write_text(
            json.dumps({"experiments": [{"id": "X7"}]}), encoding="utf-8")
        ok, source = xid_registered(root, legacy, "A", "X7")
        expect(f"state-only XID accepted ({source})", ok)

    print(f"selftest: {failures} failure(s)")
    return 1 if failures else 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _count_by_code(findings: Iterable[Dict[str, str]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for finding in findings:
        counts[finding["code"]] = counts.get(finding["code"], 0) + 1
    return counts


def report(payload: Dict[str, Any], args: argparse.Namespace,
           entries: Sequence[Any]) -> None:
    """统一的输出层：`--json` 机器读、`--quiet` 正常时静默、`--summary` 一行。

    门禁语义不变：`--quiet` 只影响**正常通过**时的可见性，违规与阻塞一律照常打印。
    """
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return
    blocked = payload.get("blocked", 0)
    if args.quiet and not blocked:
        return
    if args.summary:
        if "checked" in payload:
            print(f"layout_guard: {payload['checked']} path(s), blocked {blocked}")
        else:
            print(f"layout_guard: block {blocked}, warn {payload.get('warned', 0)}")
        return
    for entry in entries:
        if isinstance(entry, dict) and "severity" in entry:
            mark = "BLOCK" if entry["severity"] == BLOCK else "WARN "
            print(f"{mark}  [{entry['code']}] {entry['path']}: {entry['message']}")
        elif isinstance(entry, dict):
            print(f"{'PASS  ' if entry['ok'] else 'BLOCK '}  {entry['path']}: {entry['reason']}")
    if "checked" in payload:
        print(f"checked {payload['checked']} path(s); blocked {blocked}")
    else:
        counts = payload.get("by_code", {})
        if counts:
            print("按规则汇总：" + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        print(f"audit: {blocked} block(s), {payload.get('warned', 0)} warning(s)")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["preflight", "check", "audit", "selftest",
                                           "list-kinds", "doc-ids", "allocate"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--kind", choices=sorted(KINDS))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-per-code", type=int, default=5,
                        help="audit 每个规则最多打印几项（默认 5）")
    parser.add_argument("--quiet", action="store_true",
                        help="正常通过时不打印任何内容（退出码不变，违规仍会打印）")
    parser.add_argument("--summary", action="store_true",
                        help="只打印一行汇总：block / warn 计数")
    parser.add_argument("--route", help="doc-ids / allocate 使用的路线编号")
    parser.add_argument("--slug", help="allocate 使用的 DI-8 枚举 slug")
    parser.add_argument("--type", dest="doc_type",
                        help="allocate 使用文档类型（等价于 --slug，取 DI-8 枚举值）")
    args = parser.parse_args(argv)

    if args.action == "selftest":
        return selftest()
    if args.action == "list-kinds":
        for kind in sorted(KINDS):
            print(kind)
        return 0

    project = Path(args.root).resolve()
    if not project.is_dir():
        print(f"环境错误：{project} 不是目录", file=sys.stderr)
        return 4
    try:
        control = control_root(project)
        policy = load_policy(project, control)
    except GuardEnvError as exc:
        print(f"环境错误：{exc}", file=sys.stderr)
        return 4

    if args.action == "audit":
        try:
            findings = audit(project)
        except GuardEnvError as exc:
            print(f"环境错误：{exc}", file=sys.stderr)
            return 4
        blocks = [f for f in findings if f["severity"] == BLOCK]
        warns = [f for f in findings if f["severity"] == WARN]
        counts = _count_by_code(findings)
        payload = {"root": str(project), "blocked": len(blocks), "warned": len(warns),
                   "by_code": counts, "findings": findings}
        report(payload, args, findings)
        return 3 if blocks else 0

    if args.action in ("doc-ids", "allocate"):
        if not args.route:
            print("环境错误：需要 --route", file=sys.stderr)
            return 4
        try:
            if args.action == "doc-ids":
                index = doc_id_index(project, control, args.route)
                conflicts = doc_id_conflicts(project, control, args.route)
                payload = {"root": str(project), "route": args.route,
                           "next": next_doc_id(project, control, args.route),
                           "used": index, "conflicts": conflicts}
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    print(f"路线 {args.route}：下一个可用 ID {payload['next']}")
                    for doc_id, names in sorted(index.items()):
                        print(f"  {doc_id}  {', '.join(names)}")
                    for conflict in conflicts:
                        print(f"  [冲突] {conflict['id']}: {', '.join(conflict['files'])}")
                return 3 if conflicts else 0
            if not args.slug and not args.doc_type:
                print("环境错误：allocate 需要 --type（或 --slug）", file=sys.stderr)
                return 4
            result = allocate_doc(project, args.route, args.slug, args.doc_type)
        except GuardEnvError as exc:
            print(f"环境错误：{exc}", file=sys.stderr)
            return 4
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"已创建 {result['id']}：{result['path']}")
        return 0

    if args.action == "preflight" and not args.path:
        parser.error("preflight 至少需要一个 --path")
    if args.action == "check" and args.kind:
        parser.error("--kind 只用于 preflight")
    try:
        paths = args.path if args.action == "preflight" else git_new_files(project)
    except GuardEnvError as exc:
        print(f"环境错误：{exc}", file=sys.stderr)
        return 4

    results = []
    for path in paths:
        ok, reason = check_path(project, path, args.kind, control, policy)
        results.append({"path": path, "ok": ok, "reason": reason})
    payload = {"root": str(project), "checked": len(results),
               "blocked": sum(1 for item in results if not item["ok"]),
               "results": results}
    report(payload, args, results)
    return 3 if payload["blocked"] else 0


if __name__ == "__main__":
    sys.exit(main())
