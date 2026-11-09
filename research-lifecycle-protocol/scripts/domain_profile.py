#!/usr/bin/env python3
"""domain_profile.py — optional domain research profiles for RLP (loader + validator).

A domain profile extends the Research Lifecycle Protocol with field-specific rules
(currently ``mri-reconstruction``). Three properties are load-bearing:

1. **Explicit activation.** A profile is used only when the project or route declares it
   in a machine-readable config under ``<route>/domain/<profile>.json`` or
   ``<project-root>/domain/<profile>.json`` (route wins). No declaration means plain
   RLP Core behaviour; nothing is inferred from file names or keywords.
2. **Rules, not a second truth.** The config declares which rules apply (frozen
   components, GT boundary, metric thresholds). It never overrides canonical state,
   evidence qualification or the R7/R8/R9.O/R10/R11 gates.
3. **Fail closed when declared.** A declared but invalid config is a hard error (exit 3):
   a domain contract that cannot be parsed must not silently degrade to "no domain rules".

Storage roots are resolved through :mod:`rlp_paths`, so legacy projects
(``.research-idea-pipeline/``) load with the same code path as new projects.

Rules (``DP1``–``DP10``) below are mechanical. Anything that cannot be decided
mechanically is left to the agent and the existing gates.

CLI::

    python3 scripts/domain_profile.py load --state <route>/research-state.json \
        --profile mri-reconstruction
    python3 scripts/domain_profile.py check --state <route>/research-state.json
    python3 scripts/domain_profile.py check --project <project-root>

Exit codes: 0 valid / inactive, 1 usage, 3 invalid config, 4 environment.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import rlp_paths as rlp

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_HARD = 3
EXIT_ENV = 4

#: Frozen protocol namespace (see references/identity-and-compatibility.md). The domain
#: schema id keeps the historical namespace on purpose: it is a data contract, not a brand.
PROFILE_SCHEMA = "research-idea-pipeline/domain-profile@1"
PROFILE_SCHEMA_VERSION = 1

#: Registered domain profiles. A new id must ship with contract docs, validation and tests.
PROFILE_IDS: Tuple[str, ...] = ("mri-reconstruction",)

PROFILE_DOC_DIR = "domain-profiles"

SSL_TYPES = ("ssdu", "noise2noise", "noise2void", "self_deq", "supervised",
             "other_declared")
GT_USAGES = ("none", "audit_only", "development", "full")
SPLIT_ROLES = ("input", "loss", "held_out_validation")


@dataclass
class Finding:
    rule: str
    path: str
    message: str
    severity: str = "hard"          # hard | warning

    def render(self) -> str:
        return f"[{self.rule}] {self.path}: {self.message}"


@dataclass
class ProfileReport:
    profile: str
    state_path: Optional[str] = None
    active: bool = False
    config: Dict[str, Any] = field(default_factory=dict)
    config_path: Optional[str] = None
    level: str = "route"            # route | project | none
    doc: str = ""
    findings: List[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(item.severity == "hard" for item in self.findings)

    def hard_messages(self) -> List[str]:
        return [item.render() for item in self.findings if item.severity == "hard"]

    def to_dict(self) -> Dict[str, Any]:
        return {"profile": self.profile, "active": self.active, "ok": self.ok,
                "config_path": self.config_path, "level": self.level,
                "doc": self.doc, "findings": [
                    {"rule": item.rule, "path": item.path, "message": item.message,
                     "severity": item.severity} for item in self.findings],
                "config": self.config}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _finding(rule: str, path: str, message: str, severity: str = "hard") -> Finding:
    return Finding(rule, path, message, severity)


def profile_doc(profile: str) -> str:
    return f"{PROFILE_DOC_DIR}/{profile}/PROFILE.md"


def config_candidates(route_dir: pathlib.Path, profile: str) -> List[Tuple[str, pathlib.Path]]:
    """Route-level config first, then the project-level one (dual-root aware)."""
    out: List[Tuple[str, pathlib.Path]] = []
    route = pathlib.Path(route_dir).expanduser()
    out.append(("route", route / "domain" / f"{profile}.json"))
    try:
        # The canonical state name is fixed by the Research State policy; using it lets the
        # resolver honour both the new and the legacy storage root. A project carrying
        # both roots raises: two roots are two competing canonical states, never resolved
        # silently here.
        project = rlp.project_root_from_state(route / "research-state.json")
    except (rlp.LayoutError, OSError):
        project = None
    if project is not None:
        out.append(("project", project / "domain" / f"{profile}.json"))
    return out


def discover(route_dir: Any, profile: str) -> Tuple[Optional[pathlib.Path], str]:
    """Return (existing config path, level) or (None, "none")."""
    for level, path in config_candidates(pathlib.Path(route_dir), profile):
        if path.is_file():
            return path, level
    return None, "none"


def _load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        raise ValueError(f"无法解析 {path}: {exc}") from exc


def _check_frozen_metric(metric: Any, path: str, state_version: Optional[int],
                         findings: List[Finding]) -> None:
    if not isinstance(metric, dict):
        findings.append(_finding("DP7", path, "指标声明必须是对象"))
        return
    if not _text(metric.get("name")):
        findings.append(_finding("DP7", path, "缺少指标名 name"))
    threshold = metric.get("threshold")
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        findings.append(_finding("DP7", path, "缺少数值阈值 threshold"))
    if metric.get("frozen_before_results") is not True:
        findings.append(_finding(
            "DP7", path,
            "阈值必须带 frozen_before_results: true（结果产生后不得降低成功标准）"))
    version = metric.get("frozen_at_state_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        findings.append(_finding("DP7", path, "缺少 frozen_at_state_version（非负整数）"))
    elif state_version is not None and version > state_version:
        findings.append(_finding(
            "DP7", path,
            f"frozen_at_state_version={version} 晚于当前 state_version={state_version}："
            "不得声明未来时点的冻结"))


def validate(config: Any, *, state: Optional[Dict[str, Any]] = None,
             profile: str = "mri-reconstruction") -> List[Finding]:
    """Mechanical rules DP1–DP10 for a domain profile config."""
    findings: List[Finding] = []
    if profile not in PROFILE_IDS:
        return [_finding("DP1", "profile", f"未注册的领域 profile：{profile!r}")]
    if not isinstance(config, dict):
        return [_finding("DP1", "<root>", "配置顶层必须是对象")]
    if config.get("_schema") != PROFILE_SCHEMA:
        findings.append(_finding(
            "DP1", "_schema", f"必须是 {PROFILE_SCHEMA!r}（冻结协议命名空间，见 "
            "references/identity-and-compatibility.md）"))
    if config.get("profile") != profile:
        findings.append(_finding(
            "DP2", "profile", f"声明值 {config.get('profile')!r} 与文件所属 profile {profile!r} 不一致"))

    state_version: Optional[int] = None
    if isinstance(state, dict) and isinstance(state.get("state_version"), int):
        state_version = state["state_version"]

    # DP3 — acquisition contract
    acq = config.get("acquisition")
    if not isinstance(acq, dict):
        findings.append(_finding("DP3", "acquisition", "缺少 acquisition 契约"))
        acq = {}
    operators = acq.get("forward_operators")
    if not isinstance(operators, list) or not operators or \
            not all(_text(item) for item in operators):
        findings.append(_finding(
            "DP3", "acquisition.forward_operators",
            "必须逐项列出已确认的物理算子；不得留空或隐式假定"))
    noise = acq.get("noise")
    if not isinstance(noise, dict) or not _text(noise.get("model")):
        findings.append(_finding("DP3", "acquisition.noise.model", "必须声明噪声模型"))
    under = acq.get("undersampling")
    if not isinstance(under, dict) or not _text(under.get("pattern")):
        findings.append(_finding("DP3", "acquisition.undersampling.pattern",
                                 "必须声明欠采样模式"))
    coils = acq.get("coils")
    if coils is not None and (not isinstance(coils, int) or isinstance(coils, bool)
                              or coils < 1):
        findings.append(_finding("DP3", "acquisition.coils", "coils 必须是正整数（单线圈可省略）"))

    # DP4 — GT boundary
    gt = config.get("gt")
    if not isinstance(gt, dict):
        findings.append(_finding("DP4", "gt", "缺少 gt 信息边界声明"))
        gt = {}
    available = gt.get("available")
    if not isinstance(available, bool):
        findings.append(_finding("DP4", "gt.available", "必须是布尔值"))
        available = None
    usage = _text(gt.get("usage"))
    if usage not in GT_USAGES:
        findings.append(_finding("DP4", "gt.usage", f"usage 必须是 {GT_USAGES} 之一"))
    if available is False and usage in ("development", "full"):
        findings.append(_finding(
            "DP4", "gt.usage", "gt.available=false 时 usage 不得是 development/full"))

    # DP5 — SSL information boundary
    ssl = config.get("ssl")
    if not isinstance(ssl, dict):
        findings.append(_finding("DP5", "ssl", "缺少 ssl 自监督信息边界"))
        ssl = {}
    ssl_type = _text(ssl.get("type"))
    if ssl_type not in SSL_TYPES:
        findings.append(_finding("DP5", "ssl.type", f"type 必须是 {SSL_TYPES} 之一"))
    split = ssl.get("split")
    if not isinstance(split, dict):
        findings.append(_finding("DP5", "ssl.split", "必须声明 Θ/Λ/Ω_val 拆分"))
        split = {}
    roles = {role: _text(split.get(role)) for role in SPLIT_ROLES}
    for role in ("input", "loss", "held_out_validation"):
        if not roles[role]:
            findings.append(_finding("DP5", f"ssl.split.{role}", "缺少拆分声明"))
    if roles["input"] and roles["loss"] and roles["input"] == roles["loss"]:
        findings.append(_finding("DP5", "ssl.split", "训练输入与损失留出必须是不同测量集合"))
    if roles["loss"] and roles["held_out_validation"] and \
            roles["loss"] == roles["held_out_validation"]:
        findings.append(_finding(
            "DP5", "ssl.split", "损失测量不得兼任独立验证集合（hidden leakage 风险）"))
    acs = ssl.get("acs")
    if not isinstance(acs, dict) or not _text(acs.get("usage")):
        findings.append(_finding("DP5", "ssl.acs.usage", "必须声明 ACS 处理协议"))

    # DP6 — model selection isolation
    selection = config.get("model_selection")
    if not isinstance(selection, dict):
        findings.append(_finding("DP6", "model_selection", "缺少模型选择协议"))
        selection = {}
    if not _text(selection.get("protocol")):
        findings.append(_finding("DP6", "model_selection.protocol", "必须声明选择协议"))
    uses_gt = selection.get("uses_gt")
    if not isinstance(uses_gt, bool):
        findings.append(_finding("DP6", "model_selection.uses_gt", "必须是布尔值"))
    elif available is False and uses_gt:
        findings.append(_finding(
            "DP6", "model_selection.uses_gt",
            "严格 GT-free 项目不得用 GT 做模型选择（独立离线 GT 评价只能作为外部审计）"))
    if selection.get("uses_loss_measurements") is True:
        findings.append(_finding(
            "DP6", "model_selection.uses_loss_measurements",
            "模型选择不得使用损失留出测量（hidden leakage）"))

    # DP7/DP8 — frozen components and forbidden changes
    frozen = config.get("frozen")
    if not isinstance(frozen, dict):
        findings.append(_finding("DP7", "frozen", "缺少 frozen 冻结边界"))
        frozen = {}
    components = frozen.get("components")
    if components is None:
        if frozen.get("no_frozen_components") is not True:
            findings.append(_finding(
                "DP7", "frozen.components",
                "必须声明冻结组件，或写 no_frozen_components: true 并说明理由"))
        elif not _text(frozen.get("reason")):
            findings.append(_finding("DP7", "frozen.reason",
                                     "无冻结组件时必须说明 reason"))
    elif not isinstance(components, list) or not all(_text(item) for item in components):
        findings.append(_finding("DP7", "frozen.components", "必须是字符串列表"))
    forbidden = frozen.get("forbidden_changes", [])
    if not isinstance(forbidden, list) or not all(_text(item) for item in forbidden):
        findings.append(_finding("DP7", "frozen.forbidden_changes", "必须是字符串列表"))

    # DP8 — metrics and thresholds
    metrics = config.get("metrics")
    if not isinstance(metrics, dict):
        findings.append(_finding("DP8", "metrics", "缺少 metrics 评价契约"))
        metrics = {}
    primary = metrics.get("primary")
    if primary is None:
        findings.append(_finding("DP8", "metrics.primary", "必须声明主指标"))
    else:
        _check_frozen_metric(primary, "metrics.primary", state_version, findings)
    structural = metrics.get("structural", [])
    if not isinstance(structural, list):
        findings.append(_finding("DP8", "metrics.structural", "必须是数组"))
        structural = []
    for index, item in enumerate(structural):
        _check_frozen_metric(item, f"metrics.structural[{index}]", state_version, findings)
    measurement_domain = metrics.get("measurement_domain", [])
    if not isinstance(measurement_domain, list) or \
            not all(_text(item) for item in measurement_domain):
        findings.append(_finding("DP11", "metrics.measurement_domain",
                                 "必须是字符串列表（哪些指标属于测量域目标）"))

    # DP9 — resources
    resources = config.get("resources")
    if not isinstance(resources, dict) or \
            not isinstance(resources.get("gpu_hours_budget"), (int, float)) or \
            isinstance(resources.get("gpu_hours_budget"), bool) or \
            resources.get("gpu_hours_budget") <= 0:
        findings.append(_finding("DP9", "resources.gpu_hours_budget",
                                 "必须声明正的 GPU 预算（小时）"))

    # DP10 — closed top-level sections (typo protection; the config is small by design)
    allowed = {"_schema", "profile", "acquisition", "gt", "ssl", "model_selection",
               "frozen", "metrics", "resources", "notes"}
    unknown = sorted(set(config) - allowed)
    if unknown:
        findings.append(_finding("DP10", "<root>",
                                 f"未知顶层字段：{', '.join(unknown)}"))
    return findings


def load(route_dir: Any, profile: str, *,
         state: Optional[Dict[str, Any]] = None) -> ProfileReport:
    """Load and validate one profile for a route. Inactive is a normal result."""
    report = ProfileReport(profile=profile, doc=profile_doc(profile))
    if profile not in PROFILE_IDS:
        report.findings.append(_finding("DP1", "profile",
                                        f"未注册的领域 profile：{profile!r}"))
        return report
    path, level = discover(pathlib.Path(route_dir), profile)
    if path is None:
        return report
    report.active = True
    report.level = level
    report.config_path = str(path)
    try:
        config = _load_json(path)
    except ValueError as exc:
        report.findings.append(_finding("DP1", str(path), str(exc)))
        return report
    report.config = config if isinstance(config, dict) else {}
    report.findings.extend(validate(report.config, state=state, profile=profile))
    return report


def active_profile(state_path: Any) -> Tuple[str, ProfileReport]:
    """The declared profile for a state's route, or ("", inactive report).

    The declaration is the config file itself. Multiple declared profiles are not
    supported: the first registered profile with a config wins, deterministically.
    """
    route_dir = pathlib.Path(state_path).expanduser().parent
    for profile in PROFILE_IDS:
        report = load(route_dir, profile)
        if report.active:
            return profile, report
    return "", ProfileReport(profile=PROFILE_IDS[0] if PROFILE_IDS else "",
                             doc="", active=False)


def _selftest() -> int:
    import tempfile
    failures: List[str] = []

    def expect(name: str, condition: bool, detail: str = "") -> None:
        print(f"  {'ok  ' if condition else 'FAIL'} {name}"
              + (f" —— {detail}" if detail and not condition else ""))
        if not condition:
            failures.append(name)

    minimal = {
        "_schema": PROFILE_SCHEMA, "profile": "mri-reconstruction",
        "acquisition": {"forward_operators": ["fourier", "undersampling_mask"],
                        "coils": 20,
                        "undersampling": {"pattern": "variable_density"},
                        "noise": {"model": "gaussian"}},
        "gt": {"available": False, "usage": "none"},
        "ssl": {"type": "ssdu",
                "split": {"input": "theta", "loss": "lambda",
                          "held_out_validation": "omega_val"},
                "acs": {"usage": "frozen_protocol"}},
        "model_selection": {"protocol": "omega_val_only", "uses_gt": False},
        "frozen": {"components": ["backbone"], "forbidden_changes": ["推理算法"]},
        "metrics": {"primary": {"name": "nmse", "threshold": 0.02,
                                "frozen_before_results": True,
                                "frozen_at_state_version": 3},
                    "structural": [{"name": "vessel", "threshold": 0.05,
                                    "frozen_before_results": True,
                                    "frozen_at_state_version": 3}]},
        "resources": {"gpu_hours_budget": 12},
    }
    expect("最小合法配置通过", not validate(minimal, state={"state_version": 5}))
    expect("非对象配置被拒", any(f.rule == "DP1" for f in validate([])))
    expect("未知 profile 被拒", any(f.rule == "DP1" for f in validate(minimal, profile="nope")))
    broken = json.loads(json.dumps(minimal))
    broken["_schema"] = "research-lifecycle-protocol/domain-profile@1"
    broken["gt"]["usage"] = "full"
    broken["ssl"]["split"]["loss"] = broken["ssl"]["split"]["input"]
    broken["model_selection"]["uses_gt"] = True
    broken["metrics"]["primary"]["frozen_before_results"] = False
    broken["metrics"]["primary"]["frozen_at_state_version"] = 99
    broken["extra_section"] = {}
    found = validate(broken, state={"state_version": 5})
    rules = {f.rule for f in found}
    expect("协议命名空间改名被拒", "DP1" in rules)
    expect("GT 矛盾被拒", "DP4" in rules)
    expect("输入=损失被拒", "DP5" in rules)
    expect("GT-free 却用 GT 选择被拒", "DP6" in rules)
    expect("未冻结阈值被拒", "DP7" in rules or "DP8" in rules)
    expect("未来冻结被拒", "DP7" in rules or "DP8" in rules)
    expect("未知顶层字段被拒", "DP10" in rules)

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        legacy_route = root / rlp.LEGACY_STORAGE_ROOT / "routes" / "A"
        route_conf = legacy_route / "domain" / "mri-reconstruction.json"
        route_conf.parent.mkdir(parents=True)
        route_conf.write_text(json.dumps(minimal, ensure_ascii=False), encoding="utf-8")
        (legacy_route / "research-state.json").write_text("{}", encoding="utf-8")
        path, level = discover(legacy_route, "mri-reconstruction")
        expect("旧根项目可发现 route 级配置", path == route_conf and level == "route")
        project_conf = root / "domain" / "mri-reconstruction.json"
        project_conf.parent.mkdir(parents=True)
        project_conf.write_text(json.dumps(minimal, ensure_ascii=False), encoding="utf-8")
        route_conf.unlink()
        path, level = discover(legacy_route, "mri-reconstruction")
        expect("回退到项目级配置", path == project_conf and level == "project")
        report = load(legacy_route, "mri-reconstruction", state={"state_version": 5})
        expect("旧根配置可加载且合法", report.active and report.ok)
        both = root / "no-such-root"
        none_report = load(both, "mri-reconstruction")
        expect("未声明 = 不激活", not none_report.active and none_report.ok)

    if failures:
        print(f"[FAIL] {len(failures)} selftest failures")
        return EXIT_ERROR
    print("[ok] domain_profile selftest")
    return EXIT_OK


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="RLP domain profile loader")
    parser.add_argument("--selftest", action="store_true")
    sub = parser.add_subparsers(dest="command")
    load_p = sub.add_parser("load", help="load one profile for a route")
    load_p.add_argument("--state", required=True)
    load_p.add_argument("--profile", default=PROFILE_IDS[0] if PROFILE_IDS else "")
    load_p.add_argument("--json", action="store_true")
    check_p = sub.add_parser("check", help="fail closed on a declared-but-invalid profile")
    target = check_p.add_mutually_exclusive_group(required=True)
    target.add_argument("--state")
    target.add_argument("--project")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    if args.command == "load":
        state_path = pathlib.Path(args.state)
        if not state_path.is_file():
            print(f"[env] state 文件不存在：{state_path}", file=sys.stderr)
            return EXIT_ENV
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            print(f"[env] state 不可读：{exc}", file=sys.stderr)
            return EXIT_ENV
        try:
            report = load(state_path.parent, args.profile,
                          state=state if isinstance(state, dict) else None)
        except rlp.AmbiguousStorageRoot as exc:
            print(f"[FAIL] {exc}", file=sys.stderr)
            return EXIT_LAYOUT
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return EXIT_OK if report.ok else EXIT_HARD
    if args.command == "check":
        if args.state:
            state_path = pathlib.Path(args.state)
            if not state_path.is_file():
                print(f"[env] state 文件不存在：{state_path}", file=sys.stderr)
                return EXIT_ENV
            try:
                profiles = [(profile, load(state_path.parent, profile))
                            for profile in PROFILE_IDS]
            except rlp.AmbiguousStorageRoot as exc:
                print(f"[FAIL] {exc}", file=sys.stderr)
                return EXIT_LAYOUT
        else:
            project = pathlib.Path(args.project)
            if not project.is_dir():
                print(f"[env] 项目目录不存在：{project}", file=sys.stderr)
                return EXIT_ENV
            profiles = []
            for profile in PROFILE_IDS:
                probe = project / "domain" / f"{profile}.json"
                if probe.is_file():
                    profiles.append((profile, load(project, profile)))
        declared = [(profile, report) for profile, report in profiles if report.active]
        if not declared:
            print("[ok] 未声明领域 profile：RLP Core 行为")
            return EXIT_OK
        failed = False
        for profile, report in declared:
            for item in report.hard_messages():
                print(f"[FAIL] {item}", file=sys.stderr)
                failed = True
        if failed:
            print("[FAIL] 已声明的领域配置非法：先修复配置，不得当作无领域规则继续",
                  file=sys.stderr)
            return EXIT_HARD
        for profile, report in declared:
            print(f"[ok] {profile}（{report.level}）：{report.config_path}")
        return EXIT_OK
    parser.error("需要子命令或 --selftest")
    return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())


# ---------------------------------------------------------------------------
# Outcome-claim checks (DP12–DP14): what a result may and may not claim
# ---------------------------------------------------------------------------

def outcome_claim_errors(claim: Any, observation: Any,
                         config: Optional[Dict[str, Any]]) -> List[str]:
    """Mechanical rules DP12–DP14 for a result claim against its observation.

    ``claim``:  {"metric": <name>, "conclusion": <str>, "model_selection_uses_gt": bool,
                 "structural_recovery": {"structure": <str>, "counts_false_structures": bool},
                 "anchor_change_requested": bool}
    ``observation``: {"metrics": {<name>: <number>, ...}} as frozen in preregistration.

    The classic failure this exists for: "the SSL loss went down, therefore the
    reconstruction improved" — and, in wave tasks, "the global NMSE went down, therefore
    the micro-vessels were recovered". Both are objective mismatches, not successes.
    """
    problems: List[str] = []
    if not isinstance(claim, dict) or not isinstance(observation, dict):
        return ["DP12: claim 与 observation 都必须是对象"]
    metrics = (config or {}).get("metrics") or {}
    observation_metrics = observation.get("metrics") if isinstance(
        observation.get("metrics"), dict) else {}
    measurement_domain = [str(item) for item in
                          (metrics.get("measurement_domain") or [])]
    primary = metrics.get("primary") or {}
    primary_name = str(primary.get("name") or "")
    structural_names = [str((item or {}).get("name") or "")
                        for item in (metrics.get("structural") or [])]

    claimed_metric = str(claim.get("metric") or "")
    conclusion = str(claim.get("conclusion") or "")

    # DP12 — a measurement-domain objective cannot claim whole-image improvement.
    # `asserts_image_improvement` is an explicit boolean the reporter declares; the guard
    # never parses prose to decide what a sentence "meant".
    if claimed_metric in measurement_domain and observation_metrics and \
            claim.get("asserts_image_improvement") is True:
        image_metrics = {name: observation_metrics.get(name)
                         for name in ([primary_name] + structural_names) if name}
        improved = [name for name, value in image_metrics.items()
                    if isinstance(value, (int, float))
                    and not isinstance(value, bool) and value < 0]
        if not improved:
            problems.append(
                "DP12: objective mismatch —— 测量域目标改善不能宣称图像重建改善"
                "（ΔL_SSL < 0 ⇏ ΔE_image < 0）；必须作为 R9.O 分析对象")
        elif primary_name and observation_metrics.get(primary_name) is None:
            problems.append(
                "DP12: 结论引用了图像改善但观测中缺少主指标 "
                f"{primary_name}；缺指标只能写 inconclusive")

    # DP13 — a global metric cannot claim structural recovery, and structural recovery
    # must report the false-structure count.
    recovery = claim.get("structural_recovery")
    if isinstance(recovery, dict) and str(recovery.get("structure") or ""):
        if claimed_metric and claimed_metric not in structural_names and \
                claimed_metric == primary_name:
            problems.append(
                "DP13: Lower global NMSE ⇏ Better structure recovery —— 全局指标不得"
                "单独支撑结构恢复结论；必须引用冻结的结构指标")
        if recovery.get("counts_false_structures") is not True:
            problems.append(
                "DP13: 结构恢复结论必须同时报告虚假结构率（幻觉不得计为恢复成功）")

    # DP14 — GT-free model selection boundary at claim time.
    uses_gt = claim.get("model_selection_uses_gt")
    gt_config = (config or {}).get("gt") or {}
    if uses_gt is True and gt_config.get("available") is False:
        problems.append(
            "DP14: 严格 GT-free 项目不得用 GT 做模型选择；该结论只能以 GT-assisted 名义"
            "单独记录，不得进入 GT-free 流程")

    return problems
