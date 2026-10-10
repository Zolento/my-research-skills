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

RESIDUAL RISK（即使修完下列缺陷，本机制仍**无法**阻止的事项）
-------------------------------------------------------------
* **相同内容的硬链接**：`guard_write` 现在比对 `st_dev`/`st_ino`，能拒绝
  “硬链接指向受保护 inode”的写入；但 `manifest()`/`verify()` **只比对内容
  摘要、不比对 inode**（否则安装副本核验会因 inode 不同而失效）。因此
  “把受保护文件链接到别处、写入新内容后再写回原内容”在内容层面与原状
  完全一致，清单无法区分。这是有意保留的残余风险。
* **拥有任意文件系统写权限的进程**：可以直接改写源码、删除清单、删除或
  重写审计日志及其 `head` 摘要。哈希链只能证明“被读过时是否自洽”，不能
  证明“写者是谁”。
* **检查与写入之间的 TOCTOU**：`SourceFreeze` 是进入/退出两次快照的比对，
  无法证明窗口内未被改动。本模块**未**修复 E-16：窗口内“改了又改回”
  仍然不可检测（只有内容有净变化时才会被发现）。
* **提示词级别的禁止条款**不是安全边界。要真正只读，必须依赖 OS 层只读
  挂载、独立 uid、权限位或 `chattr +i`。

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
#: 遍历只在**受保护根的第一层**排除 `EXCLUDED_DIRS_TOP` 里的目录名；受保护树
#: 内部出现的同名目录（例如 `scripts/.dev/`、`references/__pycache__/`）**不会**
#: 被排除，它们的文件会进入清单并在 `verify` 中作为 `added` 报告。
PROTECTED: Tuple[str, ...] = (
    "SKILL.md", "shared-contract.md", "preset-registry.json", "router-fixtures.json",
    "references", "presets", "scripts", "templates", "schemas",
)

#: 顶层同名目录（开发态 / 评测 fixture / VCS / 缓存）：仅在扫描根的**第一层**排除。
#: 使用名字保留给已有调用方读取；实际生效的排除因为 `PROTECTED` 本身就是顶层条目，
#: 由 `_iter_protected_entries` 在每一层只应用 `EXCLUDED_DIRS_ANYWHERE`。
EXCLUDED_DIRS: Tuple[str, ...] = (".dev", "__pycache__", ".git", "examples")

#: 这些目录名在**任意深度**都被排除。
#: * `.git` —— VCS 元数据，跨层出现没有合法用途；
#: * `__pycache__` —— **解释器生成的字节码缓存，不是 Skill 源码**。把它纳入冻结清单会让
#:   「删掉 .pyc 后第一次运行」被误判为源码改动（新增 .pyc → `verify()` VIOLATION → HOLD），
#:   这是真实的部署级误报，因此必须在任意深度排除。
#: `.dev` / `examples` 只在扫描根的第一层排除（它们不进入安装副本），受保护树**内部**的
#: 同名目录仍被遍历，其文件进入清单，以保证「补一个 `scripts/.dev/evil.py`」可被发现。
EXCLUDED_DIRS_ANYWHERE: Tuple[str, ...] = (".git", "__pycache__")

INTEGRITY_NAME = "source-integrity.jsonl"
INTEGRITY_LOCK_NAME = ".source-integrity.lock"
#: 尾部摘要 sidecar：镜像 `decision_trajectory` 的 `<store>.head`，用于检测尾部截断。
INTEGRITY_HEAD_SUFFIX = ".head"

STATE_NAME = "research-state.json"

#: 允许自主写入的 route 内 scope：`guard_write` 在 route（显式 `allowed_roots`）内部
#: **实际强制**这些顶层目录/文件名；canonical state 与完整性审计日志是显式例外。
ALLOWED_WRITE_SCOPES: Tuple[str, ...] = (
    "policy", "decision-trajectory", "decision-trajectory.jsonl", "scheduler.json",
    "cognition", ".execution", "assurance", "source-integrity.jsonl",
    "recovery-log.jsonl",
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
#: Unambiguous shell-command constructs. A bare `;` / `|` / `>` is NOT included: ordinary
#: English prose ("test; this avoids waste", "ratio 3/4 > half") would be rejected, which is
#: a false positive that makes the scan useless rather than safe. Command separators are
#: matched as a separator followed by an actual command word.
_SHELL_TOKENS: Tuple[str, ...] = ("&&", "||", "$(", "`", ">|", ">>")
_EXEC_TOKENS: Tuple[str, ...] = (
    "import ", "exec(", "eval(", "__import__", "os.system", "subprocess",
)

#: A dangerous command name at a word boundary. These are not ordinary English words, so
#: matching them costs little and closes the "no separator" case (`sudo chmod 777 /`).
_DANGEROUS_COMMAND_RE = re.compile(
    r"\b(?:rm|curl|wget|chmod|chown|sudo|dd|mkfs|nc|netcat)\b")

#: `;` or `|` followed (within a few words) by a real command name.
_SHELL_SEPARATOR_RE = re.compile(
    r"(?:;|\|)\s*(?:\w+\s+){0,3}(?:rm|curl|wget|chmod|chown|python3?|bash|sh|sudo|"
    r"cat|mv|cp|dd|mkfs|nc|netcat)\b")

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

    排除规则（与 docstring 一致）：`EXCLUDED_DIRS_ANYWHERE`（`.git`、`__pycache__`）
    在任意深度被排除；`.dev` / `examples` 只在扫描根的第一层有意义（它们不进入安装副本），
    受保护树**内部**的同名目录仍然被遍历，其文件进入清单。
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
                if dirname in EXCLUDED_DIRS_ANYWHERE:
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
    """确定性源码清单：排序、逐文件 sha256、symlink 越界记录。

    RESIDUAL RISK：清单只记录**内容摘要**与 `realpath`/`symlink`，**不记录
    inode**（否则安装副本核验会因 inode 不同而失效）。因此内容完全相同的硬
    链接在清单层面与原文件不可区分；“经硬链接改写后又写回原内容”只能靠
    `guard_write` 的 `st_dev`/`st_ino` 在写入授权时拦截，事后比对看不到。
    """
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
    """把当前受保护树与清单比对。缺文件不抛异常，直接返回 VIOLATION。

    畸形清单（`files[rel]` 不是对象）同样返回 `VIOLATION`，并把相关相对路径放进
    `malformed`，而不是抛 `AttributeError`（保持文档化的退出码契约）。
    """
    root = Path(root)
    expected = manifest_payload.get("files") if isinstance(manifest_payload, dict) else None
    if not isinstance(expected, dict):
        expected = {}
    malformed = sorted(rel for rel, info in expected.items()
                       if not isinstance(info, dict))
    current: Dict[str, Dict[str, Any]] = {}
    for path in protected_files(root):
        info = source_digest(path, root)
        current[info["path"]] = info

    changed = sorted(
        rel for rel, info in current.items()
        if rel in expected and (
            not isinstance(expected[rel], dict)
            or expected[rel].get("sha256") != info["sha256"]))
    added = sorted(rel for rel in current if rel not in expected)
    removed = sorted(rel for rel in expected if rel not in current)
    escapes = _symlink_escapes(root)

    status = ("PASS" if not (changed or added or removed or escapes or malformed)
              else "VIOLATION")
    return {
        "status": status,
        "changed": changed,
        "added": added,
        "removed": removed,
        "malformed": malformed,
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


def _stat_identity(path: Path) -> Optional[Tuple[int, int]]:
    """目标的 `(st_dev, st_ino)`；无法 stat（尚不存在 / 无权限）时返回 None。"""
    try:
        info = os.stat(path)
    except OSError:
        return None
    return (info.st_dev, info.st_ino)


def _protected_identities(root: Path) -> set:
    """受保护文件（含嵌套 .dev/__pycache__ 等）的 inode 身份集合。"""
    identities: set = set()
    for entry in protected_files(root):
        try:
            info = os.stat(entry)
        except OSError:
            continue
        identities.add((info.st_dev, info.st_ino))
    return identities


def _resolve_allowed_root(allowed: Any, *, skill_root: Path) -> Optional[Path]:
    """把 `allowed_roots` 的单项解析为真实路径。

    相对路径按**当前工作目录**解析（绝不按 `skill_root` 解析，否则
    `allowed_roots=["."]` 会静默放行整个 Skill）。无法安全解析时返回 None。
    """
    raw = os.path.expanduser(str(allowed))
    if not raw:
        return None
    lexical = Path(raw)
    if not lexical.is_absolute():
        lexical = Path.cwd() / lexical
    try:
        return normalize_target(lexical, root=skill_root)
    except Exception:  # noqa: BLE001 - 无法解析的允许范围忽略
        return None


def _write_scope_of(resolved: Path, roots: Sequence[Path]) -> Optional[str]:
    """目标在某个显式允许 root 下的顶层 scope 名；不在任何 root 下返回 None。"""
    matching = [candidate for candidate in roots if _is_inside(resolved, candidate)]
    if not matching:
        return None
    base = max(matching, key=lambda item: len(item.parts))
    rel = Path(os.path.relpath(str(resolved), str(base)))
    return rel.parts[0] if len(rel.parts) > 1 else rel.name


def _scope_allowed(scope: str) -> bool:
    """Whether a top-level scope under an explicit root is a declared write scope."""
    if scope in ALLOWED_WRITE_SCOPES:
        return True
    # A route-root file is its own scope; accept the stem so `decision-trajectory.jsonl`
    # and its declared stem both work.
    stem = Path(scope).stem
    return stem in ALLOWED_WRITE_SCOPES or scope.removesuffix(".jsonl") in ALLOWED_WRITE_SCOPES


def _is_audit_artifact(name: str) -> bool:
    """审计日志本体、其 head 摘要 sidecar 与锁文件。"""
    return (name == INTEGRITY_NAME
            or name == INTEGRITY_LOCK_NAME
            or name.startswith(INTEGRITY_NAME + "."))


def guard_write(target: Any, *, skill_root: Path = SKILL_ROOT,
                allowed_roots: Sequence[Any] = (), allow_canonical: bool = False,
                ) -> Dict[str, Any]:
    """判定一次写入是否被允许。任何解析失败都 fail-closed。

    写入白名单语义（**fail-closed**）：

    * `skill_root` 本身、受保护源码、隐藏评测数据、canonical state（除非显式
      `allow_canonical=True`）一律拒绝。
    * 目标**不在** `skill_root` 内时，必须落在某个显式非空 `allowed_roots`
      里才放行；默认 `allowed_roots=()` 不再等于“全盘放行”。
    * 目标与某个受保护文件共享 `st_dev`/`st_ino`（硬链接）时拒绝，即使路径
      看起来不在受保护树内。
    * 相对 `allowed_roots` 按当前工作目录解析，绝不按 `skill_root` 解析。
    * 落在 `allowed_roots` 内的写入还必须是 route 的已知 scope
      （`ALLOWED_WRITE_SCOPES`）；canonical state 与完整性审计日志是显式例外。
    """
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

    # Skill 根目录本身：定义上它的保护集是全部，拒绝（避免 ALLOWED 目录授权）。
    if resolved == root_real:
        return _deny("PROTECTED_SKILL_SOURCE",
                     "目标是 Skill 根目录本身，任何写入都不允许。", resolved)

    inside_root = _is_inside(resolved, root_real)
    if inside_root:
        rel = Path(os.path.relpath(str(resolved), str(root_real)))
        if _protected_relpath(rel):
            return _deny("PROTECTED_SKILL_SOURCE",
                         f"目标是受保护 Skill 源码：{rel.as_posix()}", resolved)
        hidden = _hidden_eval_reason(rel)
        if hidden:
            return _deny("HIDDEN_EVALUATION_DATA",
                         f"目标是隐藏评测数据或发布元数据：{rel.as_posix()}（{hidden}）",
                         resolved)

    # 受保护条目缺失：硬链接检测依赖 inode 集合，若原件被删除，集合就不再包含它。
    missing = [name for name in PROTECTED if not (Path(skill_root) / name).exists()]
    if missing:
        return _deny("PROTECTED_SOURCE_MISSING",
                     "受保护 Skill 源码缺失，无法判定写入边界（fail-closed）："
                     + ", ".join(sorted(missing)[:5]), resolved)

    # 硬链接：路径可以漂白，inode 不能。
    identity = _stat_identity(resolved)
    if identity is not None and identity in _protected_identities(skill_root):
        return _deny("HARD_LINK_TO_PROTECTED",
                     "目标与受保护 Skill 源码共享同一 inode（硬链接），拒绝写入。",
                     resolved)

    if resolved.name == STATE_NAME and not allow_canonical:
        return _deny("CANONICAL_REQUIRES_STAGE",
                     f"canonical {STATE_NAME} 只能由阶段机写入；"
                     "确需写入请显式 allow_canonical=True", resolved)

    roots: List[Path] = []
    if allowed_roots is None:
        allowed_sequence: Sequence[Any] = ()
    elif isinstance(allowed_roots, (str, bytes, os.PathLike, Path)):
        # A single path is one root. Iterating it would walk characters and make "/" an
        # allowed root, which silently allowed every absolute path.
        allowed_sequence = [allowed_roots]
    else:
        try:
            allowed_sequence = list(allowed_roots)
        except TypeError:
            return _deny("RESOLUTION_ERROR",
                         f"allowed_roots 不是路径序列：{type(allowed_roots).__name__}", resolved)
    for allowed in allowed_sequence:
        if isinstance(allowed, (int, float, bool)) or allowed is None:
            return _deny("RESOLUTION_ERROR",
                         f"allowed_roots 含非路径项 {allowed!r}", resolved)
        candidate = _resolve_allowed_root(allowed, skill_root=skill_root)
        if candidate is None:
            return _deny("RESOLUTION_ERROR",
                         f"allowed_roots 含无法解析的项 {allowed!r}", resolved)
        roots.append(candidate)

    # 完整性审计日志只能在显式 route 内写；否则连审计记录本身都可被目标目录污染。
    if _is_audit_artifact(resolved.name):
        if not any(_is_inside(resolved, candidate) for candidate in roots):
            return _deny("AUDIT_LOG_OUTSIDE_ROUTE",
                         "完整性审计日志只能写入显式 allowed_roots（route）内："
                         f"{resolved}", resolved)
        return _allow(resolved)

    if roots and not any(_is_inside(resolved, candidate) for candidate in roots):
        return _deny("OUTSIDE_ALLOWED_SCOPE",
                     f"目标不在允许写入范围内：{resolved}", resolved)

    # 不在 skill_root 内、且没有任何显式范围：fail-closed。
    if not inside_root and not roots:
        return _deny("OUTSIDE_ALLOWED_SCOPE",
                     "目标不在 skill_root 内且未提供 allowed_roots，按 fail-closed 拒绝："
                     f"{resolved}", resolved)

    # 显式 route 内：只放行已知 scope（canonical 已在上方按 allow_canonical 处理）。
    canonical_ok = (resolved.name == STATE_NAME and allow_canonical)
    if not canonical_ok:
        scope = _write_scope_of(resolved, roots)
        if scope is not None and not _scope_allowed(scope):
            return _deny("OUTSIDE_WRITE_SCOPE",
                         f"目标不是 route 的已知写入 scope（{scope!r}）：{resolved}",
                         resolved)

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
        command = _SHELL_SEPARATOR_RE.search(text) or _DANGEROUS_COMMAND_RE.search(text)
        if command:
            add(f"SHELL_COMMAND: 候选包含可执行命令 {command.group(0)[:40]!r}（{where}）")
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

def _integrity_path(route_dir: Path) -> Path:
    return Path(route_dir) / INTEGRITY_NAME


def _integrity_head_path(path: Path) -> Path:
    """尾部摘要 sidecar：镜像 `decision_trajectory.head_path`。"""
    return Path(path).parent / (Path(path).name + INTEGRITY_HEAD_SUFFIX)


def record_integrity_event(route_dir: Path, event: Dict[str, Any]) -> Path:
    """在 `<route_dir>/source-integrity.jsonl` 追加一条哈希链事件。

    链字段（`schema`/`seq`/`recorded_at`/`previous`）在合并**之后**写入，调用方
    传入的同名键一律被覆盖，因此 `event` 无法伪造链或回放时间戳。写入后同时
    原子更新 `source-integrity.jsonl.head`，使尾部截断可检测。
    """
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
        record = dict(event)
        # 链字段最后写入：调用方不得覆盖。
        record["schema"] = SCHEMA_INTEGRITY_EVENT
        record["seq"] = len(lines) + 1
        record["recorded_at"] = datetime.now(timezone.utc).isoformat()
        record["previous"] = _line_digest(lines[-1]) if lines else None
        body = json.dumps(record, ensure_ascii=False, separators=(",", ":"),
                          allow_nan=False)
        line = body + "\n"
        with path.open("a", encoding="utf-8") as out:
            out.write(line)
            out.flush()
            os.fsync(out.fileno())
        head = _integrity_head_path(path)
        pending = head.with_name(head.name + ".pending")
        with pending.open("w", encoding="ascii") as out:
            out.write(_line_digest(body))
            out.flush()
            os.fsync(out.fileno())
        os.replace(pending, head)
    return path


def _load_integrity_chain(route_dir: Path, *, tolerant: bool = False
                          ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """读取并核验审计链，返回 `(records, diagnostics)`。

    镜像 `decision_trajectory.load_chained`：校验每行 `previous` 与
    `seq`，并校验尾部 `head` 摘要 sidecar。`tolerant=False` 时遇到第一处问题
    抛 `SourceFreezeError`；`tolerant=True` 时收集诊断并返回。
    """
    path = _integrity_path(route_dir)
    diagnostics: List[Dict[str, str]] = []

    def fail(where: str, message: str) -> None:
        diagnostics.append({"rule": "SF0", "path": where, "message": message})
        if not tolerant:
            raise SourceFreezeError(f"SF0 {where} {message}")

    if not path.exists():
        if _integrity_head_path(path).exists():
            fail(str(_integrity_head_path(path)),
                 "存在 head 摘要但日志缺失：整份审计日志被删除")
        return [], diagnostics
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:  # pragma: no cover
        fail(str(path), f"审计日志不可读：{exc}")
        return [], diagnostics

    records: List[Dict[str, Any]] = []
    bodies: List[str] = []
    for index, body in enumerate(text.splitlines(), start=1):
        if not body.strip():
            continue
        try:
            record = json.loads(body)
        except json.JSONDecodeError as exc:
            fail(f"{path.name}:{index}", f"不是合法 JSON（拒绝截断/损坏的日志）：{exc.msg}")
            continue
        if not isinstance(record, dict):
            fail(f"{path.name}:{index}", "记录必须是对象")
            continue
        expected_previous = _line_digest(bodies[-1]) if bodies else None
        if record.get("previous") != expected_previous:
            fail(f"{path.name}:{index}", "哈希链断裂：历史行被改写或被删除")
        if record.get("seq") != len(records) + 1:
            fail(f"{path.name}:{index}",
                 f"seq 不连续：期望 {len(records) + 1}，实际 {record.get('seq')!r}")
        records.append(record)
        bodies.append(body)

    head = _integrity_head_path(path)
    expected_head = _line_digest(bodies[-1]) if bodies else None
    if head.exists():
        try:
            actual_head = head.read_text(encoding="ascii").strip()
        except (OSError, UnicodeDecodeError) as exc:  # pragma: no cover
            fail(str(head), f"head 摘要不可读：{exc}")
            actual_head = None
        if actual_head != expected_head:
            fail(str(head), "尾部摘要与 head 不一致：最后一行被改写或历史被截断")
    elif bodies:
        fail(str(head), "日志有记录但缺少 head 摘要文件")
    return records, diagnostics


def load_integrity_chained(route_dir: Path, *, tolerant: bool = False
                           ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """`_load_integrity_chain` 的公开别名，便于与 `decision_trajectory` 对照。"""
    return _load_integrity_chain(route_dir, tolerant=tolerant)


def integrity_events(route_dir: Path, *, tolerant: bool = False) -> Any:
    """读取 route 的完整性事件。

    默认 `tolerant=False`：链断裂 / seq 不连续 / head 不一致时抛
    `SourceFreezeError`（镜像 `decision_trajectory.load_chained`）。
    `tolerant=True` 时返回 `(records, diagnostics)` 二元组，不抛异常。
    """
    records, diagnostics = _load_integrity_chain(route_dir, tolerant=tolerant)
    if tolerant:
        return records, diagnostics
    return records


def integrity_diagnostics(route_dir: Path) -> List[Dict[str, str]]:
    """只取诊断，不抛异常（`tolerant=True` 的便捷形式）。"""
    _, diagnostics = _load_integrity_chain(route_dir, tolerant=True)
    return diagnostics


def hold_on_violation(route_dir: Path, verification: Any, *,
                      context: str = "") -> Dict[str, Any]:
    """违规时写 HOLD 事件。**只记录，不修复源码。**

    fail-closed：`verification` 不是 dict（`None`/列表/字符串）或缺少可识别的
    `status` 时，一律按 HOLD（未知完整性）记录，绝不返回 PASS。
    """
    if isinstance(verification, dict) and verification.get("status") == "PASS":
        return {"status": "PASS", "reason": "源码完整性通过，无需 HOLD", "event": None}

    if not isinstance(verification, dict):
        reason = "源码完整性未知（未提供有效的 verify 结果），按 fail-closed 记为 HOLD"
        if context:
            reason += f"：{context}"
        event_path = record_integrity_event(route_dir, {
            "action": "HOLD",
            "status": "UNKNOWN",
            "context": context,
            "reason": reason,
            "changed": [],
            "added": [],
            "removed": [],
            "malformed": [],
            "symlink_escapes": [],
            "repair_attempted": False,
        })
        return {"status": "HOLD", "reason": reason, "event": str(event_path)}

    parts: List[str] = []
    for key, label in (("changed", "被修改"), ("added", "新增"),
                       ("removed", "缺失"), ("malformed", "清单畸形"),
                       ("symlink_escapes", "symlink 越界")):
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
        "malformed": list(verification.get("malformed") or []),
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
            "运行前后核验（changed / added / removed / symlink 越界 / 畸形清单）",
            "规范化路径写入白名单（fail-closed：受保护源码、隐藏评测数据、"
            "canonical state、硬链接、非 route 范围）",
            "带哈希链与 head 尾部摘要的只追加审计事件（读取时核验）",
        ],
        "residual_risks": [
            "本模块是完整性与写入白名单检查，不是安全边界。",
            "拥有任意文件系统写权限的进程可以直接改写源码、删除清单、伪造或删改审计日志与 head 摘要。",
            "symlink 检测基于 realpath 快照，存在 TOCTOU：检查与写入之间的替换无法被本模块阻止。",
            "内容完全相同的硬链接在清单层面不可与受保护文件区分；guard_write 仅在授权时按 "
            "st_dev/st_ino 拒绝。",
            "SourceFreeze 是进入/退出快照比对：窗口内“改了又改回”不可检测（未修复 E-16）。",
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
        check("guard allows canonical state with explicit flag and route",
              guard_write(route / STATE_NAME, skill_root=root,
                          allowed_roots=[route], allow_canonical=True)["allowed"])
        check("guard fails closed on canonical state without any route",
              guard_write(route / STATE_NAME, skill_root=root,
                          allow_canonical=True)["code"] == "OUTSIDE_ALLOWED_SCOPE")
        check("guard allows route policy write",
              guard_write(route / "policy" / "p.json", skill_root=root,
                          allowed_roots=[route])["allowed"])
        check("guard fails closed outside skill root without allowed_roots",
              guard_write(Path(temp) / "outside" / "x.txt", skill_root=root)["code"]
              == "OUTSIDE_ALLOWED_SCOPE")
        check("guard denies skill root itself",
              guard_write(root, skill_root=root)["code"] == "PROTECTED_SKILL_SOURCE")
        check("guard enforces allowed_roots",
              guard_write(Path(temp) / "elsewhere" / "x.json", skill_root=root,
                          allowed_roots=[route])["code"] == "OUTSIDE_ALLOWED_SCOPE")
        check("guard denies symlink escape",
              _selftest_symlink_escape(root, temp))
        check("guard denies hard link to protected source",
              _selftest_hard_link(root, route))
        check("guard denies audit log outside its route",
              guard_write(root / INTEGRITY_NAME, skill_root=root,
                          allowed_roots=[route])["code"] == "AUDIT_LOG_OUTSIDE_ROUTE")

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
        check("integrity head sidecar exists",
              (route / (INTEGRITY_NAME + INTEGRITY_HEAD_SUFFIX)).is_file())
        check("integrity chain fields are not caller-overridable",
              _selftest_chain_fields(route))
        check("integrity chain detects a middle-line deletion",
              _selftest_chain_tamper(route))

        # HOLD 不修复源码
        hold = hold_on_violation(route, missing, context="selftest")
        check("hold writes HOLD event", hold["status"] == "HOLD"
              and Path(hold["event"]).is_file())
        check("hold fails closed on non-dict verification",
              hold_on_violation(route, None, context="selftest")["status"] == "HOLD")
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


def _selftest_hard_link(root: Path, route: Path) -> bool:
    """在 route 里造一个指向受保护文件的硬链接，确认守卫按 inode 拒绝。"""
    link = Path(route) / "hard-SKILL.md"
    try:
        if link.exists() or link.is_symlink():
            link.unlink()
        os.link(root / "SKILL.md", link)
    except OSError:  # pragma: no cover - 文件系统不支持硬链接
        return True
    result = guard_write(link, skill_root=root, allowed_roots=[route])
    return result["code"] == "HARD_LINK_TO_PROTECTED"


def _selftest_chain_fields(route: Path) -> bool:
    """调用方不能覆盖 seq / previous / recorded_at。"""
    before = len(integrity_events(route))
    record_integrity_event(route, {
        "action": "FORGED", "seq": 999,
        "previous": "sha256:deadbeef",
        "recorded_at": "1999-01-01T00:00:00+00:00",
    })
    last = integrity_events(route)[-1]
    return (last["seq"] == before + 1
            and last["previous"] != "sha256:deadbeef"
            and last["recorded_at"] != "1999-01-01T00:00:00+00:00")


def _selftest_chain_tamper(route: Path) -> bool:
    """删掉中间一行后，非宽容读取必须抛错，宽容读取必须给出诊断。"""
    tamper = Path(route).parent / "_selftest-tamper"
    tamper.mkdir(parents=True, exist_ok=True)
    log = _integrity_path(tamper)
    head = _integrity_head_path(log)
    for stale in (log, head):
        if stale.exists():
            stale.unlink()
    for index in range(3):
        record_integrity_event(tamper, {"action": f"E{index}"})
    lines = log.read_text(encoding="utf-8").splitlines()
    log.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")
    try:
        integrity_events(tamper)
    except SourceFreezeError:
        raise_detected = True
    else:
        raise_detected = False
    _, diagnostics = integrity_events(tamper, tolerant=True)
    return raise_detected and bool(diagnostics)


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
