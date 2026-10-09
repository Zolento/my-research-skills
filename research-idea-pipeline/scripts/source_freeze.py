#!/usr/bin/env python3
"""source_freeze.py — Skill 源码冻结：清单 + 规范化路径写入守卫 + 审计事件。

为什么需要它
------------
自主策略演进在一次科研运行中**绝不允许修改 Skill 源码**。宿主 harness 没有
OS 级别的沙箱，因此本模块提供的是**机械可检**的三件事：

1. **清单（manifest）** —— 对 `SKILL.md`、`shared-contract.md`、
   `preset-registry.json`、`router-fixtures.json` 以及 `references/`、
   `presets/`、`scripts/`、`templates/`、`schemas/` 逐个文件做 sha256，
   得到确定性摘要，可在运行前后比对。
2. **规范化路径写入守卫（guard_write / normalize_target）** —— 任何写入目标
   先展开 `~`、拒绝 `..`、解析 symlink，阻止对受保护源码、隐藏评测 fixture、
   发布元数据与 canonical `research-state.json` 的写入。
3. **审计事件（source-integrity.jsonl）** —— 在 route 目录下以 flock + fsync
   追加带哈希链的事件；违规时写入 `HOLD` 并**不做任何修复**。

诚实的边界声明（docs-as-data）
------------------------------
本模块**不是安全边界**。一个有任意文件系统写权限的进程可以绕过清单、绕过
守卫、甚至改写审计日志。`read_only_deployment_plan()` 给出推荐的只读部署
（chmod / 只读挂载、独立 uid、安装副本核验），并明确写出剩余风险：
**提示词级别的禁止条款不是安全边界。**

用法
----
    python3 source_freeze.py freeze --root <dir> [--out <manifest.json>]
    python3 source_freeze.py verify --manifest <manifest.json> [--root <dir>]
    python3 source_freeze.py guard  --target <path> [--root <dir>] [--route <dir>]
    python3 source_freeze.py plan
    python3 source_freeze.py selftest
    python3 source_freeze.py --selftest

退出码（沿用 cognition.py 的约定）
---------------------------------
    0  pass
    1  参数错误
    3  hard violation（verify=VIOLATION / guard=DENY）
    4  环境不满足（清单缺失 / 非法 JSON / 不可读）
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import cognition as _cognition

# 复用 cognition 的退出码与摘要工具，避免出现第二套约定。
EXIT_OK = _cognition.EXIT_OK
EXIT_ERROR = _cognition.EXIT_ERROR
EXIT_HARD = _cognition.EXIT_HARD
EXIT_ENV = _cognition.EXIT_ENV

digest_of = _cognition.digest_of
canonical_json = _cognition.canonical_json

SCHEMA_MANIFEST = "research-idea-pipeline/source-freeze@1"
SCHEMA_INTEGRITY_EVENT = "research-idea-pipeline/source-integrity-event@1"

#: Skill 根目录：本文件位于 `<root>/scripts/source_freeze.py`。
SKILL_ROOT = Path(__file__).resolve().parent.parent

#: 受保护条目：顶层文件与目录名。目录下的**全部文件**都进入清单。
PROTECTED: Tuple[str, ...] = (
    "SKILL.md", "shared-contract.md", "preset-registry.json", "router-fixtures.json",
    "references", "presets", "scripts", "templates", "schemas",
)

#: 这些目录名在遍历时被排除（开发态 / 评测 fixture / VCS / 缓存）。
EXCLUDED_DIRS: Tuple[str, ...] = (".dev", "__pycache__", ".git", "examples")

INTEGRITY_NAME = "source-integrity.jsonl"
INTEGRITY_LOCK_NAME = ".source-integrity.lock"

STATE_NAME = "research-state.json"

#: 允许自主写入的 route 内 scope（文档性常量；实际放行由 `allowed_roots` 决定）。
ALLOWED_WRITE_SCOPES: Tuple[str, ...] = (
    "policy", "decision-trajectory", "scheduler.json", "cognition",
    ".execution", "assurance", "source-integrity.jsonl", "recovery-log.jsonl",
)

#: 隐藏评测 fixture / 发布元数据：写入即拒绝。
_HIDDEN_EVAL_DIRS: Tuple[str, ...] = (".dev", "examples", "__pycache__", ".git")
_HIDDEN_EVAL_FILES: Tuple[str, ...] = ("README.md", "CHANGELOG.md")
_HIDDEN_EVAL_PREFIXES: Tuple[Tuple[str, ...], ...] = (("docs", "releases"),)

#: `guard_errors` 的对抗词表。
_PROTECTED_TOKENS: Tuple[str, ...] = (
    "SKILL.md", "presets/", "scripts/", "references/", "templates/",
    "preset-registry.json", "shared-contract.md", "schemas/", "router-fixtures.json",
)
_SHELL_TOKENS: Tuple[str, ...] = (";", "&&", "|", "$(", "`", ">")
_EXEC_TOKENS: Tuple[str, ...] = (
    "import ", "exec(", "eval(", "__import__", "os.system", "subprocess",
)

_ABSOLUTE_RE = re.compile(r"^([A-Za-z]:[\\/]|/)")


class SourceFreezeError(Exception):
    """环境级失败：清单缺失、不可读、非法 JSON。"""


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def _relpath_str(path: Path, root: Path) -> str:
    """相对 `root` 的词法路径（不解析 symlink），统一成 POSIX 风格。"""
    return Path(os.path.relpath(str(path), str(root))).as_posix()


def _is_inside(path: Path, root: Path) -> bool:
    """`path` 是否等于 `root` 或位于其下。两侧都应是规范化后的真实路径。"""
    try:
        return path == root or path.is_relative_to(root)
    except (AttributeError, ValueError):  # pragma: no cover - 旧解释器兜底
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False


def _real(path: Any) -> Path:
    return Path(os.path.realpath(str(path)))


def _line_digest(line: str) -> str:
    return "sha256:" + hashlib.sha256(line.encode("utf-8")).hexdigest()


def _deny(code: str, reason: str, resolved: Any) -> Dict[str, Any]:
    return {"allowed": False, "code": code, "reason": reason, "resolved": str(resolved)}


def _allow(resolved: Path) -> Dict[str, Any]:
    return {"allowed": True, "code": "ALLOWED",
            "reason": f"目标可写：{resolved}", "resolved": str(resolved)}


def _protected_relpath(rel: Path) -> bool:
    parts = rel.parts
    return bool(parts) and parts[0] in PROTECTED


def _hidden_eval_reason(rel: Path) -> str:
    parts = rel.parts
    for part in parts:
        if part in _HIDDEN_EVAL_DIRS:
            return f"位于被排除的隐藏/评测目录 {part!r}"
    for prefix in _HIDDEN_EVAL_PREFIXES:
        if parts[:len(prefix)] == prefix:
            return "发布元数据目录 " + "/".join(prefix) + "/"
    if parts and parts[-1] in _HIDDEN_EVAL_FILES:
        return f"发布元数据文件 {parts[-1]!r}"
    return ""


# ---------------------------------------------------------------------------
# 受保护文件遍历
# ---------------------------------------------------------------------------

def _iter_protected_entries(root: Path) -> Iterable[Path]:
    """产出受保护条目下的所有文件，以及**symlink 目录本身**（用于越界检测）。

    `os.walk` 默认不跟随 symlink 目录，因此这里不会递归进越界目录；
    越界的 symlink 目录会被单独产出，交给调用方判定 escape。
    """
    for name in PROTECTED:
        base = Path(root) / name
        if base.is_symlink() or base.is_file():
            yield base
            continue
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            kept: List[str] = []
            for dirname in sorted(dirnames):
                if dirname in EXCLUDED_DIRS:
                    continue
                child = Path(dirpath) / dirname
                if child.is_symlink():
                    yield child          # 只登记，不递归
                else:
                    kept.append(dirname)
            dirnames[:] = kept
            for filename in sorted(filenames):
                yield Path(dirpath) / filename


def protected_files(root: Path = SKILL_ROOT) -> List[Path]:
    """受保护的文件列表，按相对路径排序，确定性。"""
    root = Path(root)
    files: List[Path] = []
    for entry in _iter_protected_entries(root):
        try:
            if entry.is_dir():      # symlink 到目录：不当作文件
                continue
        except OSError:             # pragma: no cover - 不可 stat 时仍保守登记
            pass
        files.append(entry)
    files.sort(key=lambda item: _relpath_str(item, root))
    return files


def source_digest(path: Any, root: Any) -> Dict[str, Any]:
    """单个受保护文件的指纹。`symlink=True` 表示该路径本身是符号链接。"""
    path = Path(path)
    root = Path(root)
    symlink = path.is_symlink()
    real = os.path.realpath(str(path))
    sha256: Optional[str]
    try:
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        sha256 = None
    return {
        "path": _relpath_str(path, root),
        "sha256": sha256,
        "realpath": real,
        "symlink": bool(symlink),
    }


def _symlink_escapes(root: Path) -> List[str]:
    """受保护树内所有真实路径越出 root 的 symlink（去重、排序）。"""
    root_real = _real(root)
    escapes: List[str] = []
    for entry in _iter_protected_entries(root):
        if not entry.is_symlink():
            continue
        if not _is_inside(_real(entry), root_real):
            escapes.append(_relpath_str(entry, root))
    return sorted(set(escapes))


# ---------------------------------------------------------------------------
# 清单
# ---------------------------------------------------------------------------

def manifest(root: Path = SKILL_ROOT) -> Dict[str, Any]:
    """确定性源码清单：排序、逐文件 sha256、symlink 越界记录。"""
    root = Path(root)
    files: Dict[str, Dict[str, Any]] = {}
    for path in protected_files(root):
        info = source_digest(path, root)
        files[info["path"]] = {
            "sha256": info["sha256"],
            "realpath": info["realpath"],
            "symlink": info["symlink"],
        }
    escapes = _symlink_escapes(root)
    payload: Dict[str, Any] = {
        "schema": SCHEMA_MANIFEST,
        "root": str(root.resolve()),
        "count": len(files),
        "digest": digest_of(files),
        "files": files,
        "excluded": list(EXCLUDED_DIRS),
    }
    if escapes:
        payload["symlink_escapes"] = escapes
    return payload


def write_manifest(path: Path, root: Path = SKILL_ROOT) -> Dict[str, Any]:
    """原子写清单：`.pending` + `os.replace`。"""
    payload = manifest(root)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    pending.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    os.replace(pending, path)
    return payload


def load_manifest(path: Path) -> Dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise SourceFreezeError(f"清单文件不存在：{path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceFreezeError(f"清单文件不是合法 JSON：{path}（{exc}）") from exc
    if not isinstance(doc, dict):
        raise SourceFreezeError(f"清单根必须是 JSON 对象：{path}")
    return doc


def verify(manifest_payload: Dict[str, Any], root: Path = SKILL_ROOT) -> Dict[str, Any]:
    """把当前受保护树与清单比对。缺文件不抛异常，直接返回 VIOLATION。"""
    root = Path(root)
    expected = manifest_payload.get("files") if isinstance(manifest_payload, dict) else None
    if not isinstance(expected, dict):
        expected = {}
    current: Dict[str, Dict[str, Any]] = {}
    for path in protected_files(root):
        info = source_digest(path, root)
        current[info["path"]] = info

    changed = sorted(
        rel for rel, info in current.items()
        if rel in expected and expected[rel].get("sha256") != info["sha256"])
    added = sorted(rel for rel in current if rel not in expected)
    removed = sorted(rel for rel in expected if rel not in current)
    escapes = _symlink_escapes(root)

    status = "PASS" if not (changed or added or removed or escapes) else "VIOLATION"
    return {
        "status": status,
        "changed": changed,
        "added": added,
        "removed": removed,
        "symlink_escapes": escapes,
        "checked": len(expected),
    }


# ---------------------------------------------------------------------------
# 规范化路径与写入守卫
# ---------------------------------------------------------------------------

def normalize_target(target: Any, *, root: Path = SKILL_ROOT) -> Path:
    """展开 `~`、拒绝 `..`、解析 symlink，返回真实路径。

    * 词法路径（含 `..`）直接判 `PATH_TRAVERSAL`，在解析之前拦截。
    * 词法上位于 `root` 内、但 realpath 越出 `root` 的 symlink 技巧判
      `SYMLINK_ESCAPE`。
    """
    raw = os.path.expanduser(str(target))
    if not raw:
        raise ValueError(f"PATH_TRAVERSAL: 空目标路径：{target!r}")
    lexical = Path(raw)
    if any(part == ".." for part in lexical.parts):
        raise ValueError(f"PATH_TRAVERSAL: 目标路径包含 '..'：{raw}")

    root_real = _real(root)
    lexical_path = lexical if lexical.is_absolute() else (root_real / lexical)
    lexical_norm = Path(os.path.normpath(str(lexical_path)))
    real = Path(os.path.realpath(str(lexical_path)))

    if _is_inside(lexical_norm, root_real) and not _is_inside(real, root_real):
        raise ValueError(
            f"SYMLINK_ESCAPE: 词法路径位于 skill root 内但真实路径越界：{real}")
    return real


def guard_write(target: Any, *, skill_root: Path = SKILL_ROOT,
                allowed_roots: Sequence[Any] = (), allow_canonical: bool = False,
                ) -> Dict[str, Any]:
    """判定一次写入是否被允许。任何解析失败都 fail-closed。"""
    raw = str(target)
    try:
        resolved = normalize_target(target, root=skill_root)
    except Exception as exc:  # noqa: BLE001 - fail-closed 是设计目标
        message = str(exc)
        if message.startswith("PATH_TRAVERSAL"):
            code = "PATH_TRAVERSAL"
        elif message.startswith("SYMLINK_ESCAPE"):
            code = "SYMLINK_ESCAPE"
        else:
            code = "RESOLUTION_ERROR"
        return _deny(code, f"路径无法安全解析：{message}", raw)

    root_real = _real(skill_root)
    if _is_inside(resolved, root_real):
        rel = Path(os.path.relpath(str(resolved), str(root_real)))
        if _protected_relpath(rel):
            return _deny("PROTECTED_SKILL_SOURCE",
                         f"目标是受保护 Skill 源码：{rel.as_posix()}", resolved)
        hidden = _hidden_eval_reason(rel)
        if hidden:
            return _deny("HIDDEN_EVALUATION_DATA",
                         f"目标是隐藏评测数据或发布元数据：{rel.as_posix()}（{hidden}）",
                         resolved)

    if resolved.name == STATE_NAME and not allow_canonical:
        return _deny("CANONICAL_REQUIRES_STAGE",
                     f"canonical {STATE_NAME} 只能由阶段机写入；"
                     "确需写入请显式 allow_canonical=True", resolved)

    if allowed_roots:
        roots: List[Path] = []
        for allowed in allowed_roots:
            try:
                roots.append(normalize_target(allowed, root=skill_root))
            except Exception:  # noqa: BLE001 - 无法解析的允许范围忽略
                continue
        if not any(_is_inside(resolved, candidate) for candidate in roots):
            return _deny("OUTSIDE_ALLOWED_SCOPE",
                         f"目标不在允许写入范围内：{resolved}", resolved)

    return _allow(resolved)


# ---------------------------------------------------------------------------
# 候选策略对抗扫描
# ---------------------------------------------------------------------------

def _is_absolute(text: str) -> bool:
    return bool(text) and bool(_ABSOLUTE_RE.match(text))


def guard_errors(candidate: Any) -> List[str]:
    """扫描结构化策略候选，返回人类可读的拒绝理由；干净时返回 []。

    拒绝：受保护目标、shell 元字符、可执行内容、绝对路径、`../` 穿越。
    """
    reasons: List[str] = []
    seen: set = set()

    def add(reason: str) -> None:
        if reason not in seen:
            seen.add(reason)
            reasons.append(reason)

    def inspect(text: str, where: str) -> None:
        for token in _PROTECTED_TOKENS:
            if token in text:
                add(f"PROTECTED_TARGET: 候选引用了受保护目标 {token!r}（{where}）")
        for token in _SHELL_TOKENS:
            if token in text:
                add(f"SHELL_METACHARACTER: 候选包含 shell 元字符 {token!r}（{where}）")
        for token in _EXEC_TOKENS:
            if token in text:
                add(f"EXECUTABLE_CONTENT: 候选包含可执行内容 {token!r}（{where}）")
        if "../" in text or text == "..":
            add(f"PATH_TRAVERSAL: 候选包含路径穿越 {text!r}（{where}）")
        if _is_absolute(text):
            add(f"ABSOLUTE_PATH: 候选包含绝对路径 {text!r}（{where}）")

    def walk(node: Any, where: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                inspect(str(key), f"{where}.{key}")
                walk(value, f"{where}.{key}")
        elif isinstance(node, (list, tuple)):
            for index, value in enumerate(node):
                walk(value, f"{where}[{index}]")
        elif isinstance(node, str):
            inspect(node, where)

    walk(candidate, "$")
    return reasons


# ---------------------------------------------------------------------------
# 审计事件（哈希链，flock + fsync）
# ---------------------------------------------------------------------------

def record_integrity_event(route_dir: Path, event: Dict[str, Any]) -> Path:
    """在 `<route_dir>/source-integrity.jsonl` 追加一条哈希链事件。"""
    route_dir = Path(route_dir)
    route_dir.mkdir(parents=True, exist_ok=True)
    path = route_dir / INTEGRITY_NAME
    lock_path = route_dir / INTEGRITY_LOCK_NAME
    with lock_path.open("a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        lines: List[str] = []
        if path.exists():
            try:
                lines = [line for line in path.read_text(encoding="utf-8").splitlines()
                         if line.strip()]
            except (OSError, UnicodeDecodeError):  # pragma: no cover - 保守从零续链
                lines = []
        base = {
            "schema": SCHEMA_INTEGRITY_EVENT,
            "seq": len(lines) + 1,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "previous": _line_digest(lines[-1]) if lines else None,
        }
        record = {**base, **dict(event)}
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"),
                          allow_nan=False) + "\n"
        with path.open("a", encoding="utf-8") as out:
            out.write(line)
            out.flush()
            os.fsync(out.fileno())
    return path


def integrity_events(route_dir: Path) -> List[Dict[str, Any]]:
    """读取 route 的完整性事件；空行与坏行跳过，不抛异常。"""
    path = Path(route_dir) / INTEGRITY_NAME
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):  # pragma: no cover
        return []
    records: List[Dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def hold_on_violation(route_dir: Path, verification: Dict[str, Any], *,
                      context: str = "") -> Dict[str, Any]:
    """违规时写 HOLD 事件。**只记录，不修复源码。**"""
    if not isinstance(verification, dict) or verification.get("status") == "PASS":
        return {"status": "PASS", "reason": "源码完整性通过，无需 HOLD", "event": None}

    parts: List[str] = []
    for key, label in (("changed", "被修改"), ("added", "新增"),
                       ("removed", "缺失"), ("symlink_escapes", "symlink 越界")):
        values = verification.get(key) or []
        if values:
            parts.append(f"{label} " + ", ".join(str(value) for value in values))
    reason = "源码冻结违规（" + "；".join(parts) + "）"
    if context:
        reason += f"：{context}"

    event_path = record_integrity_event(route_dir, {
        "action": "HOLD",
        "status": "VIOLATION",
        "context": context,
        "reason": reason,
        "changed": list(verification.get("changed") or []),
        "added": list(verification.get("added") or []),
        "removed": list(verification.get("removed") or []),
        "symlink_escapes": list(verification.get("symlink_escapes") or []),
        "repair_attempted": False,
    })
    return {"status": "HOLD", "reason": reason, "event": str(event_path)}


# ---------------------------------------------------------------------------
# 只读部署建议（docs-as-data，含剩余风险）
# ---------------------------------------------------------------------------

def read_only_deployment_plan() -> Dict[str, Any]:
    """推荐的只读部署，以及本模块**无法**消除的剩余风险。"""
    return {
        "schema": "research-idea-pipeline/source-freeze-deployment@1",
        "recommended": {
            "install_copy_verification": (
                "把 Skill 安装为独立副本（例如 ~/.agents/skills/research-idea-pipeline），"
                "安装后用 `freeze` 生成清单并 `verify`，确保运行副本与发布副本逐字节一致。"),
            "filesystem_read_only": (
                "对 Skill 源码目录设置只读：`chmod -R a-w <skill_root>`，"
                "或把源码以只读方式挂载（bind mount ro / 只读卷）。"),
            "separate_uid": (
                "以独立 uid/gid 运行科研流程，Skill 源码归属于另一个 uid 且对运行用户只读；"
                "需要写的内容只能落在 route 目录。"),
            "immutable_attribute": (
                "支持时用 `chattr +i` 固化发布副本，防止同 uid 进程就地改写。"),
            "integrity_verification": (
                "运行前后各执行一次 `freeze`/`verify`；违规时调用 "
                "`hold_on_violation()` 写 HOLD 审计事件并停止推进，而不是修复源码。"),
        },
        "enforced_by_this_module": [
            "受保护源码清单与确定性摘要（sha256）",
            "运行前后核验（changed / added / removed / symlink 越界）",
            "规范化路径写入白名单（受保护源码、隐藏评测数据、canonical state）",
            "带哈希链的只追加审计事件",
        ],
        "residual_risks": [
            "本模块是完整性与写入白名单检查，不是安全边界。",
            "拥有任意文件系统写权限的进程可以直接改写源码、删除清单、伪造或删改审计日志。",
            "symlink 检测基于 realpath 快照，存在 TOCTOU：检查与写入之间的替换无法被本模块阻止。",
        ],
        "residual_risk": (
            "剩余风险：本模块只能机械地检测与记录，无法阻止一个有任意文件系统写权限的进程；"
            "提示词级别的禁止条款不是安全边界（a prompt-level prohibition is not a "
            "security boundary）。要真正只读，必须依赖 OS 层的只读挂载、独立 uid 或权限位。"),
    }


# ---------------------------------------------------------------------------
# 运行前后冻结上下文
# ---------------------------------------------------------------------------

class SourceFreeze:
    """上下文管理器：进入时取清单，退出时核验并记录事件。

    **违规不抛异常**：`self.result` 暴露 `verify()` 结果，调用方决定是否
    `hold_on_violation()`。上下文管理器本身也**从不修复源码**。
    """

    def __init__(self, root: Path = SKILL_ROOT, route_dir: Optional[Path] = None,
                 context: str = "") -> None:
        self.root = Path(root)
        self.route_dir = Path(route_dir) if route_dir is not None else None
        self.context = context
        self.start: Optional[Dict[str, Any]] = None
        self.result: Optional[Dict[str, Any]] = None
        self.event: Optional[Path] = None
        self.hold: Optional[Dict[str, Any]] = None

    def __enter__(self) -> "SourceFreeze":
        self.start = manifest(self.root)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self.result = verify(self.start or {}, self.root)
        if self.route_dir is not None:
            if self.result["status"] != "PASS":
                self.hold = hold_on_violation(self.route_dir, self.result,
                                              context=self.context)
                if self.hold.get("event"):
                    self.event = Path(self.hold["event"])
            else:
                self.event = record_integrity_event(self.route_dir, {
                    "action": "VERIFY_PASS",
                    "status": "PASS",
                    "context": self.context,
                    "checked": self.result["checked"],
                })
        return False


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------

def _selftest_tree(root: Path) -> None:
    for rel in ("SKILL.md", "shared-contract.md", "preset-registry.json",
                "router-fixtures.json", "scripts/guard.py", "scripts/util.py",
                "presets/research-loop.md", "references/policy.md",
                "templates/state.template.json", "schemas/x.schema.json",
                ".dev/hidden-answer.md", "examples/demo.md"):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {rel}\n", encoding="utf-8")


def selftest() -> int:
    failures: List[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"  ok   {name}")
        else:
            failures.append(name)
            print(f"  FAIL {name} {detail}")

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "skill"
        root.mkdir()
        _selftest_tree(root)
        route = Path(temp) / "project" / ".research-idea-pipeline" / "routes" / "A"
        route.mkdir(parents=True)

        first = manifest(root)
        second = manifest(root)
        check("manifest is deterministic", canonical_json(first) == canonical_json(second))
        check("manifest count matches protected_files",
              first["count"] == len(protected_files(root)))
        check("manifest excludes .dev", ".dev/hidden-answer.md" not in first["files"])
        check("clean tree verifies PASS", verify(first, root)["status"] == "PASS")

        # 篡改检测
        (root / "SKILL.md").write_text("tampered\n", encoding="utf-8")
        changed = verify(first, root)
        check("changed file is detected",
              changed["status"] == "VIOLATION" and "SKILL.md" in changed["changed"])
        (root / "SKILL.md").write_text("# SKILL.md\n", encoding="utf-8")

        # 新增 / 缺失
        (root / "scripts" / "extra.py").write_text("# extra\n", encoding="utf-8")
        check("added protected file is detected",
              "scripts/extra.py" in verify(first, root)["added"])
        (root / "scripts" / "extra.py").unlink()
        (root / "scripts" / "util.py").unlink()
        missing = verify(first, root)
        check("removed protected file is detected",
              "scripts/util.py" in missing["removed"])

        # 写入守卫
        check("guard denies SKILL.md",
              guard_write(root / "SKILL.md", skill_root=root)["code"]
              == "PROTECTED_SKILL_SOURCE")
        check("guard denies scripts/*.py",
              guard_write(root / "scripts" / "guard.py", skill_root=root)["code"]
              == "PROTECTED_SKILL_SOURCE")
        check("guard denies traversal",
              guard_write(str(root / ".." / "escape.txt"), skill_root=root)["code"]
              == "PATH_TRAVERSAL")
        check("guard denies hidden evaluation data",
              guard_write(root / ".dev" / "hidden-answer.md", skill_root=root)["code"]
              == "HIDDEN_EVALUATION_DATA")
        check("guard denies canonical state",
              guard_write(route / STATE_NAME, skill_root=root)["code"]
              == "CANONICAL_REQUIRES_STAGE")
        check("guard allows canonical state with explicit flag",
              guard_write(route / STATE_NAME, skill_root=root,
                          allow_canonical=True)["allowed"])
        check("guard allows route policy write",
              guard_write(route / "policy" / "p.json", skill_root=root)["allowed"])
        check("guard enforces allowed_roots",
              guard_write(Path(temp) / "elsewhere" / "x.json", skill_root=root,
                          allowed_roots=[route])["code"] == "OUTSIDE_ALLOWED_SCOPE")
        check("guard denies symlink escape",
              _selftest_symlink_escape(root, temp))

        # 候选扫描
        check("guard_errors rejects SKILL.md edit",
              bool(guard_errors({"action": "write", "target": "SKILL.md"})))
        check("guard_errors rejects shell command",
              bool(guard_errors({"steps": ["rm -rf x && echo done"]})))
        check("guard_errors rejects import os",
              bool(guard_errors({"note": "import os"})))
        check("guard_errors rejects ../",
              bool(guard_errors({"target": "../outside"})))
        check("guard_errors accepts clean candidate",
              guard_errors({"action": "adjust_prior", "scope": "exploration"}) == [])

        # 审计链
        record_integrity_event(route, {"action": "VERIFY_PASS", "status": "PASS"})
        record_integrity_event(route, {"action": "VERIFY_PASS", "status": "PASS"})
        events = integrity_events(route)
        check("integrity chain has two events", len(events) == 2)
        first_line = (route / INTEGRITY_NAME).read_text(
            encoding="utf-8").splitlines()[0]
        check("integrity chain links previous line",
              events[1]["previous"] == _line_digest(first_line))

        # HOLD 不修复源码
        hold = hold_on_violation(route, missing, context="selftest")
        check("hold writes HOLD event", hold["status"] == "HOLD"
              and Path(hold["event"]).is_file())
        check("hold does not repair source",
              integrity_events(route)[-1].get("repair_attempted") is False
              and not (root / "scripts" / "util.py").exists())

    plan = read_only_deployment_plan()
    check("deployment plan states residual risk",
          bool(plan.get("residual_risk"))
          and "not a security boundary" in plan["residual_risk"])

    if failures:
        print(f"selftest: FAIL ({len(failures)} failures)")
        return EXIT_ERROR
    print("selftest OK")
    return EXIT_OK


def _selftest_symlink_escape(root: Path, temp: str) -> bool:
    """在 tmp 树里造一个指向 root 外的 symlink，确认守卫拒绝。"""
    outside = Path(temp) / "outside"
    outside.mkdir(exist_ok=True)
    (outside / "payload.txt").write_text("x\n", encoding="utf-8")
    link = root / "scripts" / "escape-link"
    try:
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - 平台不支持
        return True
    result = guard_write(link / "payload.txt", skill_root=root)
    return result["code"] == "SYMLINK_ESCAPE"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # noqa: D401 - argparse hook
        self.print_usage(sys.stderr)
        print(f"argument error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(description="Skill 源码冻结：清单 / 写入守卫 / 完整性审计")
    parser.add_argument("command", nargs="?",
                        choices=["freeze", "verify", "guard", "plan", "selftest"])
    parser.add_argument("--root", type=Path, default=SKILL_ROOT,
                        help="Skill 根目录（默认：本模块所在 Skill）")
    parser.add_argument("--out", type=Path, help="freeze 的清单输出路径")
    parser.add_argument("--manifest", type=Path, help="verify 读取的清单路径")
    parser.add_argument("--target", help="guard 判定的写入目标")
    parser.add_argument("--route", type=Path, help="guard 的允许写入范围（route 目录）")
    parser.add_argument("--selftest", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.selftest or args.command == "selftest":
        return selftest()

    if args.command == "freeze":
        if args.out:
            payload = write_manifest(args.out, args.root)
        else:
            payload = manifest(args.root)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return EXIT_OK

    if args.command == "verify":
        if not args.manifest:
            print("argument error: verify 需要 --manifest", file=sys.stderr)
            return EXIT_ERROR
        try:
            payload = load_manifest(args.manifest)
        except SourceFreezeError as exc:
            print(str(exc), file=sys.stderr)
            return EXIT_ENV
        result = verify(payload, args.root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return EXIT_OK if result["status"] == "PASS" else EXIT_HARD

    if args.command == "guard":
        if not args.target:
            print("argument error: guard 需要 --target", file=sys.stderr)
            return EXIT_ERROR
        allowed_roots = [args.route] if args.route else []
        result = guard_write(args.target, skill_root=args.root,
                             allowed_roots=allowed_roots)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return EXIT_OK if result["allowed"] else EXIT_HARD

    if args.command == "plan":
        print(json.dumps(read_only_deployment_plan(), ensure_ascii=False, indent=2))
        return EXIT_OK

    build_parser().print_help()
    return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
