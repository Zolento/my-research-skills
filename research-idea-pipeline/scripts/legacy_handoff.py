#!/usr/bin/env python3
"""legacy_handoff.py — read-only takeover of an existing research project.

Why this exists
---------------
A project that has already run the pipeline has a canonical `research-state.json`,
accumulated evidence, failure memory, a scheduler, an anchor and possibly a spent
diagnostic budget. Loading a newer skill must never look like a fresh start: **Bootstrap
is for projects with no state, and this is not one of them.**

The handoff does four things and nothing else:

1. **Detects** an initialized project and refuses a fresh Bootstrap.
2. Runs a **read-only compatibility audit** over state, scheduler, contract, experiment
   provenance, failure memory, route documents and existing code.
3. Rebuilds the cognitive layer from canonical evidence, marking everything that could
   not be recovered as `unknown` or `retrospective` — a legacy experiment without a
   preregistration never acquires a frozen prediction after the fact.
4. Writes a **takeover report** and stops. Severe compatibility errors write nothing at
   all; the answer is never "rebuild a new Research State".

Nothing here resets a version, a claim status, an evidence record, an experiment id, an
anchor, a diagnostic budget or a historical decision. The state and the scheduler are
byte-compared before and after.

Rule namespace `LH1`—`LH16`; `S`/`V`/`CM`/`PC` keep their own identities.

Usage
-----
    python3 legacy_handoff.py detect   --state <state.json>
    python3 legacy_handoff.py audit    --state <state.json> [--project <root>]
    python3 legacy_handoff.py take     --state <state.json> [--project <root>]
    python3 legacy_handoff.py rollback --state <state.json>
    python3 legacy_handoff.py guard-bootstrap --state <state.json>
    python3 legacy_handoff.py --selftest

Exit codes: 0 pass, 1 argument error, 3 hard violation / blocked, 4 environment.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cognition as cg

SCHEMA_HANDOFF = "research-idea-pipeline/legacy-handoff@1"

EXIT_OK = cg.EXIT_OK
EXIT_ERROR = cg.EXIT_ERROR
EXIT_HARD = cg.EXIT_HARD
EXIT_ENV = cg.EXIT_ENV

HANDOFF_NAME = "handoff.json"
REPORT_NAME = "handoff-report.md"

BLOCKING = "blocking"
WARNING = "warning"
INFO = "info"

SEVERITY_ORDER = (BLOCKING, WARNING, INFO)

#: Files the handoff owns inside `cognition/`. Rollback removes exactly these.
OWNED_FILES = (cg.INDEX_NAME, cg.BRIEF_NAME, HANDOFF_NAME, REPORT_NAME)

ROUTE_DOCS = ("README.md", "STATUS.md", "INDEX.md")


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

class Finding:
    __slots__ = ("rule", "severity", "path", "detail")

    def __init__(self, rule: str, severity: str, path: str, detail: str) -> None:
        self.rule = rule
        self.severity = severity
        self.path = path
        self.detail = detail

    def render(self) -> str:
        return f"[{self.severity}] {self.rule}  {self.path}  {self.detail}"

    def as_dict(self) -> Dict[str, str]:
        return {"rule": self.rule, "severity": self.severity,
                "path": self.path, "detail": self.detail}


def _dedupe(findings: Sequence[Finding]) -> List[Finding]:
    seen: Dict[Tuple[str, str, str, str], Finding] = {}
    for finding in findings:
        seen.setdefault((finding.rule, finding.severity, finding.path, finding.detail), finding)
    return [seen[key] for key in sorted(seen)]


# ---------------------------------------------------------------------------
# Detection: an initialized project is not a new project
# ---------------------------------------------------------------------------

def detect(state_path: Path) -> Dict[str, Any]:
    """Report whether the project is already initialized. Read-only."""
    canonical = state_path.is_file()
    result: Dict[str, Any] = {
        "state_path": str(state_path),
        "initialized": canonical,
        "bootstrap_forbidden": canonical,
        "route": state_path.parent.name,
    }
    if canonical:
        try:
            state = cg.load_state(state_path)
            result["state_version"] = state.get("state_version")
            result["reason"] = (
                "canonical research-state.json 已存在：这是已初始化项目，"
                "不得执行全新 Bootstrap（B0—B6）")
        except cg.CognitionError as exc:
            result["reason"] = f"canonical state 存在但不可读：{exc}"
            result["unreadable"] = True
    else:
        result["reason"] = "没有 canonical research-state.json：可以按新项目 Bootstrap"
    return result


# ---------------------------------------------------------------------------
# Read-only compatibility audit
# ---------------------------------------------------------------------------

def _history_versions(route_dir: Path) -> List[int]:
    """Versions recorded under `history/`, read without interpreting the entries."""
    history = route_dir / "history"
    versions: List[int] = []
    if not history.is_dir():
        return versions
    for path in sorted(history.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
        candidates: List[Any] = []
        if isinstance(payload, dict):
            candidates.append(payload.get("state_version"))
            entries = payload.get("changes") or payload.get("entries")
            if isinstance(entries, list):
                candidates.extend(entry.get("state_version") for entry in entries
                                  if isinstance(entry, dict))
        for value in candidates:
            if isinstance(value, int) and not isinstance(value, bool):
                versions.append(value)
    return versions


def _state_shape_findings(state: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    try:
        import state_check as sc
    except ImportError:  # pragma: no cover - the checker ships with the skill
        return findings
    report = sc.check_state(state, source="<legacy-handoff>")
    if report.ok:
        return findings
    for violation in report.shape:
        findings.append(Finding("LH1", BLOCKING, violation.path,
                                f"Shape Gate {violation.rule}：{violation.detail}"))
    for violation in report.violations:
        findings.append(Finding("LH1", BLOCKING, violation.path,
                                f"{violation.rule}：{violation.detail}"))
    for violation in report.outcome:
        findings.append(Finding("LH1", BLOCKING, violation.path,
                                f"{violation.rule}：{violation.detail}"))
    return findings


def _scheduler_findings(state: Dict[str, Any], route_dir: Path) -> List[Finding]:
    findings: List[Finding] = []
    scheduler_path = route_dir / "scheduler.json"
    if not scheduler_path.is_file():
        findings.append(Finding("LH4", INFO, str(scheduler_path),
                                "没有 scheduler telemetry：接管不重建，下一轮由 R9/R11 生成"))
        return findings
    try:
        scheduler = json.loads(scheduler_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        findings.append(Finding("LH4", BLOCKING, str(scheduler_path),
                                f"scheduler 存在但不可解析：{exc}"))
        return findings
    if not isinstance(scheduler, dict):
        findings.append(Finding("LH4", BLOCKING, str(scheduler_path), "scheduler 必须是对象"))
        return findings
    state_version = state.get("state_version")
    if scheduler.get("state_version") != state_version:
        findings.append(Finding(
            "LH4", BLOCKING, "scheduler.json:state_version",
            f"scheduler.state_version={scheduler.get('state_version')} 与 "
            f"state.state_version={state_version} 不一致；"
            "先由所属阶段核对产物并按 R11 同步，不得任选一份为真，更不得重建 state"))
    budget = _execution_ledger_findings(route_dir)
    findings.extend(budget)
    return findings


def _execution_ledger_findings(route_dir: Path) -> List[Finding]:
    ledger = route_dir / ".execution"
    if not ledger.exists():
        return []
    entries = sorted(path.name for path in ledger.rglob("*") if path.is_file())
    return [Finding("LH11", INFO, str(ledger),
                    f"存在执行 ledger（{len(entries)} 个文件）：诊断与 pilot 预算已消耗，"
                    "接管不得重置 counters、ID、seed 或 stop rule")]


def _contract_findings(state: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    contract = state.get("contract")
    if not isinstance(contract, dict):
        return [Finding("LH5", WARNING, "contract",
                        "没有研究契约：接管不补写锚点，请让用户确认目标与 primary_anchor")]
    for field in ("goal", "primary_anchor"):
        value = contract.get(field)
        if not isinstance(value, str) or not value.strip():
            findings.append(Finding("LH5", WARNING, f"contract.{field}",
                                    "研究契约缺少该字段：接管不猜测，保留为空并请用户确认"))
    return findings


def _experiment_findings(state: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    for experiment in state.get("experiments", []) or []:
        if not isinstance(experiment, dict):
            continue
        ident = experiment.get("id")
        status = experiment.get("status")
        preregistration = experiment.get("preregistration")
        if status in ("done", "failed"):
            result = experiment.get("result")
            if not isinstance(result, str) or not result.strip():
                findings.append(Finding("LH6", WARNING, f"experiments[{ident}].result",
                                        "终态实验没有结果文本：provenance 不完整"))
            if experiment.get("code_commit") in ("TBD", "", None):
                findings.append(Finding("LH6", WARNING, f"experiments[{ident}].code_commit",
                                        "终态实验没有代码版本：结论不可复现，接管不补写"))
            if not isinstance(preregistration, dict):
                findings.append(Finding(
                    "LH7", BLOCKING, f"experiments[{ident}].preregistration",
                    "终态实验历史上没有预注册：不得事后补造冻结预测，"
                    "也不得据该结果宣告预测成立或失败；先由所属阶段按其权限处理"))
            else:
                frozen = preregistration.get("frozen_at_state_version")
                result_version = experiment.get("result_at_state_version")
                if isinstance(frozen, int) and isinstance(result_version, int) \
                        and frozen > result_version:
                    findings.append(Finding(
                        "LH13", BLOCKING, f"experiments[{ident}].preregistration",
                        f"预测时间泄漏：frozen_at_state_version={frozen} 晚于 "
                        f"result_at_state_version={result_version}；该结果不得当作预测检验"))
        if status == "running":
            findings.append(Finding("LH8", INFO, f"experiments[{ident}]",
                                    "正在执行的实验：恢复真实状态，不重复执行、不自动关闭"))
        if status == "failed":
            findings.append(Finding("LH8", INFO, f"experiments[{ident}]",
                                    "失败实验：保留，不自动关闭、不因换 seed 而放行"))
    return findings


def _failure_findings(state: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    for failure in state.get("failures", []) or []:
        if not isinstance(failure, dict):
            continue
        ident = failure.get("id")
        negative = failure.get("negative_knowledge")
        stop_rules = failure.get("stop_rules")
        if not negative and not stop_rules:
            findings.append(Finding(
                "LH9", WARNING, f"failures[{ident}]",
                "failure memory 没有 negative_knowledge 或 stop_rules："
                "禁止重复条件无法恢复，标为 unknown"))
    return findings


def _repair_findings(state: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    for index, repair in enumerate(state.get("repairs", []) or []):
        if not isinstance(repair, dict):
            continue
        if repair.get("closure") == "ACCEPTED_LIMITATION":
            findings.append(Finding("LH10", INFO, f"repairs[{index}]",
                                    "已接受的限制：作为失效边界恢复，不重新打开"))
    return findings


def _document_findings(project_root: Path, route: str) -> List[Finding]:
    findings: List[Finding] = []
    route_dir = project_root / "routes" / route
    for name in ROUTE_DOCS:
        if not (route_dir / name).is_file():
            findings.append(Finding("LH14", WARNING, f"routes/{route}/{name}",
                                    "路线三件套缺件：接管只报告，不代写文档"))
    code_candidates = [project_root / "src", project_root / "configs" / "routes" / route]
    if not any(path.exists() and any(path.rglob("*")) for path in code_candidates):
        findings.append(Finding("LH15", INFO, "src/",
                                "没有发现现有代码或路线配置：接管不假设代码存在"))
    return findings


def _cognition_findings(state: Dict[str, Any], revisions: Sequence[Dict[str, Any]],
                        cognition_dir: Path) -> List[Finding]:
    """A pre-existing derived layer must be rebuildable, or takeover is refused."""
    index_path = cognition_dir / cg.INDEX_NAME
    if not index_path.is_file():
        return []
    findings: List[Finding] = []
    try:
        stored = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [Finding("LH12", BLOCKING, str(index_path),
                        f"已有认知索引不可解析：{exc}；先人工修复，接管不覆盖未知内容")]
    if not isinstance(stored, dict):
        return [Finding("LH12", BLOCKING, str(index_path), "已有认知索引必须是对象")]
    diagnostics = cg.validate_index(state, revisions, stored)
    for diagnostic in diagnostics:
        findings.append(Finding("LH12", BLOCKING, diagnostic.path,
                                "已有认知索引与 canonical 重建不一致：" + diagnostic.detail))
    return findings


def compatibility_audit(
    state_path: Path,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run every read-only check. Never writes anything, never mutates `state`."""
    route = state_path.parent.name
    route_dir = state_path.parent
    root = project_root if project_root is not None else _infer_project_root(state_path)
    findings: List[Finding] = []

    state = cg.load_state(state_path)
    revisions, parse_diagnostics = cg.load_revisions(route_dir / cg.COGNITION_DIRNAME
                                                     / cg.REVISIONS_NAME)
    for diagnostic in parse_diagnostics:
        findings.append(Finding("LH16", BLOCKING, diagnostic.path,
                                f"修订日志损坏：{diagnostic.detail}"))

    siblings = sorted(route_dir.glob(cg.STATE_NAME))
    if len(siblings) > 1:
        findings.append(Finding("LH2", BLOCKING, str(route_dir),
                                f"该路线下有 {len(siblings)} 份 canonical state，违反 DI-3；"
                                "接管不选择、不合并、不重建"))

    findings.extend(_state_shape_findings(state))

    history = _history_versions(route_dir)
    current = state.get("state_version")
    if isinstance(current, int) and history and max(history) > current:
        findings.append(Finding(
            "LH3", BLOCKING, "state_version",
            f"state_version={current} 低于 history/ 记录的 {max(history)}：疑似回退，"
            "接管不重置版本，也不覆盖历史"))

    findings.extend(_scheduler_findings(state, route_dir))
    findings.extend(_contract_findings(state))
    findings.extend(_experiment_findings(state))
    findings.extend(_failure_findings(state))
    findings.extend(_repair_findings(state))
    findings.extend(_document_findings(root, route))
    findings.extend(_cognition_findings(state, revisions, route_dir / cg.COGNITION_DIRNAME))

    findings = _dedupe(findings)
    counts = {severity: sum(1 for f in findings if f.severity == severity)
              for severity in SEVERITY_ORDER}
    return {
        "route": route,
        "state_path": str(state_path),
        "project_root": str(root),
        "findings": findings,
        "counts": counts,
        "blocking": counts[BLOCKING] > 0,
        "revisions": revisions,
    }


def _infer_project_root(state_path: Path) -> Path:
    """`<root>/.research-idea-pipeline/routes/<R>/research-state.json` → `<root>`."""
    route_dir = state_path.parent
    routes_dir = route_dir.parent
    control = routes_dir.parent
    if routes_dir.name == "routes" and control.name == ".research-idea-pipeline":
        return control.parent
    return route_dir


# ---------------------------------------------------------------------------
# Recovery summary
# ---------------------------------------------------------------------------

def _recovered(state: Dict[str, Any], index: Dict[str, Any]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for key in cg.REF_KEYS:
        entries = state.get(key)
        counts[key] = len(entries) if isinstance(entries, list) else 0
    return {
        "state_version": state.get("state_version"),
        "contract_present": isinstance(state.get("contract"), dict),
        "decision_present": isinstance(state.get("decision"), dict),
        "objects": counts,
        "mechanisms": index["counts"]["mechanisms"],
        "legacy_mechanisms": index["counts"]["legacy_mechanisms"],
        "anomalies": index["counts"]["anomalies"],
        "competitions": index["counts"]["competitions"],
        "boundaries": index["counts"]["boundaries"],
        "provenance_mode": index.get("provenance_mode"),
    }


def _unrecovered(state: Dict[str, Any], findings: Sequence[Finding]) -> List[Dict[str, str]]:
    """Everything the takeover explicitly does **not** claim to know."""
    items: List[Dict[str, str]] = []
    for experiment in state.get("experiments", []) or []:
        if not isinstance(experiment, dict):
            continue
        ident = experiment.get("id")
        if experiment.get("status") in ("done", "failed") \
                and not isinstance(experiment.get("preregistration"), dict):
            items.append({
                "path": f"experiments[{ident}]",
                "status": "retrospective",
                "detail": "历史上没有预注册：不补造冻结预测，也不反推预测成功或失败",
            })
        elif isinstance(experiment.get("preregistration"), dict):
            outcomes = experiment["preregistration"].get("outcomes")
            for outcome in outcomes if isinstance(outcomes, list) else []:
                if isinstance(outcome, dict) and not isinstance(outcome.get("criterion"), dict):
                    items.append({
                        "path": f"experiments[{ident}].preregistration.outcomes[{outcome.get('id')}]",
                        "status": "retrospective",
                        "detail": "冻结结果没有可判定判据：不追溯判定预测是否成立，"
                                  "只有在结果产生前补齐判据才可用",
                    })
        if experiment.get("status") == "running":
            items.append({
                "path": f"experiments[{ident}]",
                "status": "in_flight",
                "detail": "正在执行：恢复真实状态，不重复执行、不自动关闭",
            })
    for finding in findings:
        if finding.severity == WARNING and finding.rule in ("LH5", "LH9", "LH14", "LH15"):
            items.append({"path": finding.path, "status": "unknown", "detail": finding.detail})
    items.sort(key=lambda item: (item["status"], item["path"]))
    return items


def _important_mechanisms(index: Dict[str, Any], limit: int = 8) -> List[Dict[str, Any]]:
    rank = {level: order for order, level in enumerate(
        ("experiment_supported", "literature_supported", "hypothesis", "speculative", "refuted"))}
    mechanisms = [m for m in index.get("mechanisms", []) if not m.get("stale")]
    mechanisms.sort(key=lambda m: (rank.get(m.get("support_level"), 9), str(m.get("id"))))
    return [{"id": m.get("id"), "support_level": m.get("support_level"),
             "status": m.get("status"), "statement": m.get("statement", ""),
             "scope": m.get("scope", ""),
             "refs": m.get("canonical_refs", {}),
             "retrospective": bool((m.get("provenance") or {}).get("retrospective"))}
            for m in mechanisms[:limit]]


def _unresolved_anomalies(index: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{"id": anomaly.get("id"), "observation": anomaly.get("observation", ""),
             "importance": anomaly.get("importance"),
             "reproduced": anomaly.get("reproduced"),
             "exploratory": anomaly.get("exploratory", False)}
            for anomaly in index.get("anomalies", []) if not anomaly.get("stale")]


def _forbidden_repeats(index: Dict[str, Any]) -> List[Dict[str, Any]]:
    kinds = ("stop_rule", "retry_forbidden", "failed_repeat")
    return [item for item in index.get("boundaries", []) if item.get("kind") in kinds]


def _in_flight(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for experiment in state.get("experiments", []) or []:
        if not isinstance(experiment, dict):
            continue
        status = experiment.get("status")
        if status not in ("running", "failed", "planned"):
            continue
        if status == "planned" and experiment.get("parent") is None:
            continue
        items.append({
            "id": experiment.get("id"),
            "status": status,
            "parent": experiment.get("parent"),
            "stage": experiment.get("stage"),
            "must_not_rerun": status in ("running", "failed"),
            "must_not_auto_close": True,
            "result_at_state_version": experiment.get("result_at_state_version"),
            "execution_blocked_by": experiment.get("execution_blocked_by"),
        })
    items.sort(key=lambda item: str(item["id"]))
    return items


def _next_action(state: Dict[str, Any], index: Dict[str, Any],
                 route_dir: Path) -> Dict[str, Any]:
    scheduler_path = route_dir / "scheduler.json"
    if scheduler_path.is_file():
        try:
            scheduler = json.loads(scheduler_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            scheduler = None
        actions = scheduler.get("next_actions") if isinstance(scheduler, dict) else None
        if isinstance(actions, list) and actions:
            first = actions[0]
            if isinstance(first, dict):
                return {"action": first.get("action"), "type": first.get("type"),
                        "target": first.get("target"), "source": "scheduler.json",
                        "reason": "接管不重排既有 next_actions；按 scheduler 的选择继续"}
    return {"action": None, "source": "cognition",
            "reason": cg.next_action_hint(cg.CanonicalView(state), index)}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _clip(value: Any, limit: int = 120) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render_report(handoff: Dict[str, Any]) -> str:
    audit = handoff["audit"]
    lines: List[str] = []
    lines.append("# Legacy Research Handoff Report")
    lines.append("")
    lines.append("Read-only takeover of an already initialized research project.")
    lines.append("Nothing in `research-state.json`, `scheduler.json`, the `.execution` ledger")
    lines.append("or any route document was modified. This report is a projection.")
    lines.append("")
    lines.append(f"- route: `{handoff['route']}`")
    lines.append(f"- state_version: {handoff['state_version']}（未重置）")
    lines.append(f"- state digest: `{handoff['state_digest']}`")
    lines.append(f"- audit: blocking={audit['counts'][BLOCKING]} "
                 f"warning={audit['counts'][WARNING]} info={audit['counts'][INFO]}")
    lines.append("")

    lines.append("## 1. Recovered")
    recovered = handoff["recovered"]
    lines.append(f"- provenance_mode: `{recovered['provenance_mode']}`")
    if recovered["legacy_mechanisms"]:
        lines.append(f"- {recovered['legacy_mechanisms']} 条机制是从 canonical 状态**重建**的"
                     "（retrospective）：它们没有历史修订记录，也不携带任何未冻结的预测")
    lines.append("- first-class objects: "
                 + ", ".join(f"{key}={value}" for key, value in sorted(recovered["objects"].items())))
    lines.append(f"- derived: mechanisms={recovered['mechanisms']}"
                 f"（legacy {recovered['legacy_mechanisms']}）, "
                 f"anomalies={recovered['anomalies']}, competitions={recovered['competitions']}, "
                 f"boundaries={recovered['boundaries']}")
    lines.append(f"- contract present: {recovered['contract_present']}; "
                 f"decision present: {recovered['decision_present']}")
    lines.append("")

    lines.append("## 2. Not recovered")
    if not handoff["unrecovered"]:
        lines.append("- (nothing was left as unknown or retrospective)")
    for item in handoff["unrecovered"]:
        lines.append(f"- [{item['status']}] `{item['path']}` — {_clip(item['detail'])}")
    lines.append("")

    lines.append("## 3. Important mechanisms")
    if not handoff["important_mechanisms"]:
        lines.append("- (none)")
    for mechanism in handoff["important_mechanisms"]:
        tag = " [RETROSPECTIVE]" if mechanism["retrospective"] else ""
        lines.append(f"- `{mechanism['id']}` [{mechanism['support_level']}/{mechanism['status']}]"
                     f"{tag} {_clip(mechanism['statement'])}")
    lines.append("")

    lines.append("## 4. Unresolved anomalies")
    if not handoff["unresolved_anomalies"]:
        lines.append("- (none)")
    for anomaly in handoff["unresolved_anomalies"]:
        flag = "exploratory" if anomaly["exploratory"] else "frozen-prediction"
        lines.append(f"- `{anomaly['id']}` [{anomaly['importance']}/{flag}] "
                     f"{_clip(anomaly['observation'])}")
    lines.append("")

    lines.append("## 5. Directions forbidden to repeat")
    if not handoff["forbidden_repeats"]:
        lines.append("- (none recorded)")
    for item in handoff["forbidden_repeats"]:
        lines.append(f"- [{item.get('kind')}] `{item.get('target')}` {_clip(item.get('rule', ''))}")
        if item.get("revisit_conditions"):
            lines.append(f"  - revisit only if: {_clip(item['revisit_conditions'])}")
    lines.append("")

    lines.append("## 6. In-flight experiments (no rerun, no auto-close)")
    if not handoff["in_flight"]:
        lines.append("- (none)")
    for item in handoff["in_flight"]:
        lines.append(f"- `{item['id']}` [{item['status']}] stage={item['stage']} "
                     f"parent={item['parent']} must_not_rerun={item['must_not_rerun']}")
    lines.append("")

    lines.append("## 7. Next valuable research action")
    action = handoff["next_action"]
    lines.append(f"- source: `{action['source']}`")
    if action.get("action"):
        lines.append(f"- action: `{action['action']}` type={action.get('type')} "
                     f"target={action.get('target')}")
    lines.append(f"- reason: {_clip(action['reason'])}")
    lines.append("")

    lines.append("## 8. How to continue")
    lines.append("- Entry stays `continue-research`; no fifth entry was added.")
    lines.append(f"- Read `{cg.COGNITION_DIRNAME}/{cg.BRIEF_NAME}` before the next stage; "
                 "no manual memory path is needed.")
    lines.append(f"- After each round run `python3 scripts/cognition.py build --state "
                 f"{handoff['state_path']}`; `check` must exit 0.")
    lines.append("- Roll back this derived layer with "
                 "`python3 scripts/legacy_handoff.py rollback`; it removes only the files "
                 "this handoff created.")
    lines.append("")

    lines.append("## 9. Audit findings")
    if not handoff["audit"]["findings"]:
        lines.append("- (none)")
    for finding in handoff["audit"]["findings"]:
        lines.append(f"- [{finding['severity']}] {finding['rule']} `{finding['path']}` "
                     f"{_clip(finding['detail'])}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def _take(state_path: Path, project_root: Optional[Path]) -> int:
    state_before = cg.state_fingerprint(state_path)
    audit = compatibility_audit(state_path, project_root)
    route_dir = state_path.parent
    cognition_dir = route_dir / cg.COGNITION_DIRNAME
    if audit["blocking"]:
        print("BLOCKED — 严重兼容性错误，未写回任何内容：", file=sys.stderr)
        for finding in audit["findings"]:
            if finding.severity == BLOCKING:
                print("  " + finding.render(), file=sys.stderr)
        print("不得通过重建一份新 Research State 绕过这些问题；"
              "请先修好 canonical 产物，再重新接管。", file=sys.stderr)
        return EXIT_HARD

    state = cg.load_state(state_path)
    route = audit["route"]
    revisions = audit["revisions"]
    index, index_diagnostics = cg.full_index(state, revisions, route)
    brief = cg.render_brief(index, state)
    handoff_path = cognition_dir / HANDOFF_NAME
    already = handoff_path.is_file()

    handoff = {
        "_schema": SCHEMA_HANDOFF,
        "route": route,
        "state_path": str(state_path),
        "project_root": audit["project_root"],
        "state_version": state.get("state_version"),
        "state_digest": cg.digest_of(state),
        "canonical_untouched": True,
        "audit": {"counts": audit["counts"],
                  "findings": [finding.as_dict() for finding in audit["findings"]]},
        "recovered": _recovered(state, index),
        "unrecovered": _unrecovered(state, audit["findings"]),
        "important_mechanisms": _important_mechanisms(index),
        "unresolved_anomalies": _unresolved_anomalies(index),
        "forbidden_repeats": _forbidden_repeats(index),
        "in_flight": _in_flight(state),
        "next_action": _next_action(state, index, route_dir),
        "wrote": list(OWNED_FILES),
    }
    cognition_dir.mkdir(parents=True, exist_ok=True)
    (cognition_dir / cg.INDEX_NAME).write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (cognition_dir / cg.BRIEF_NAME).write_text(brief, encoding="utf-8")
    (cognition_dir / HANDOFF_NAME).write_text(
        json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (cognition_dir / REPORT_NAME).write_text(render_report(handoff), encoding="utf-8")

    if cg.state_fingerprint(state_path) != state_before:
        print("canonical state was modified during handoff; aborting", file=sys.stderr)
        return EXIT_HARD
    print(json.dumps({
        "status": "PASS",
        "already_initialized": already,
        "idempotent": already,
        "route": route,
        "state_version": handoff["state_version"],
        "cognition_dir": str(cognition_dir),
        "report": str(cognition_dir / REPORT_NAME),
        "blocking": 0,
        "warnings": audit["counts"][WARNING],
        "info": audit["counts"][INFO],
        "mechanisms": index["counts"]["mechanisms"],
        "legacy_mechanisms": index["counts"]["legacy_mechanisms"],
        "diagnostics": len(index_diagnostics),
        "canonical_untouched": True,
    }, ensure_ascii=False, indent=2))
    return EXIT_OK


def _audit(state_path: Path, project_root: Optional[Path]) -> int:
    audit = compatibility_audit(state_path, project_root)
    for finding in audit["findings"]:
        print(finding.render())
    print(json.dumps({"route": audit["route"], "counts": audit["counts"],
                      "blocking": audit["blocking"]}, ensure_ascii=False))
    return EXIT_HARD if audit["blocking"] else EXIT_OK


def _rollback(state_path: Path) -> int:
    """Remove only the artifacts this handoff created. Refuses on unknown content."""
    route_dir = state_path.parent
    cognition_dir = route_dir / cg.COGNITION_DIRNAME
    handoff_path = cognition_dir / HANDOFF_NAME
    if not handoff_path.is_file():
        print(f"environment error: no handoff record at {handoff_path}", file=sys.stderr)
        return EXIT_ENV
    try:
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"environment error: handoff record is not valid JSON: {exc.msg}", file=sys.stderr)
        return EXIT_ENV
    owned = set(handoff.get("wrote") or OWNED_FILES)
    owned.add(HANDOFF_NAME)
    present = {path.name for path in cognition_dir.iterdir() if path.is_file()}
    foreign = sorted(present - owned)
    if foreign:
        print("refusing to roll back: unknown files would be deleted or orphaned: "
              + ", ".join(foreign), file=sys.stderr)
        return EXIT_HARD
    if handoff.get("route") != route_dir.name:
        print("refusing to roll back: handoff record belongs to another route", file=sys.stderr)
        return EXIT_HARD
    state_before = cg.state_fingerprint(state_path)
    for name in sorted(present):
        target = (cognition_dir / name).resolve()
        if target.parent != cognition_dir.resolve():
            print(f"refusing to roll back: path escapes the cognition directory: {target}",
                  file=sys.stderr)
            return EXIT_HARD
        target.unlink()
    cognition_dir.rmdir()
    if cg.state_fingerprint(state_path) != state_before:
        print("canonical state changed during rollback", file=sys.stderr)
        return EXIT_HARD
    print(json.dumps({"status": "ROLLED_BACK", "removed": sorted(present),
                      "cognition_dir": str(cognition_dir),
                      "canonical_untouched": True}, ensure_ascii=False, indent=2))
    return EXIT_OK


def _guard_bootstrap(state_path: Path) -> int:
    result = detect(state_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["bootstrap_forbidden"]:
        print("Bootstrap refused: this project is already initialized. "
              "Use `continue-research` (Legacy Research Handoff on first load).", file=sys.stderr)
        return EXIT_HARD
    return EXIT_OK


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _legacy_state() -> Dict[str, Any]:
    def validity(reason: str, version: int) -> Dict[str, Any]:
        return {"status": "valid", "reason": reason, "since_state_version": version}
    return {
        "state_version": 7,
        "contract": {"goal": "判断机制 A 是否解释目标现象", "primary_anchor": "phenomenon",
                     "constraints": [], "resources": [],
                     "provisional_anchor_rationale": "先形式化", "out_of_scope": []},
        "claims": [{
            "id": "C1", "statement": "机制 A 解释目标现象", "parent": None, "subclaims": [],
            "status": "partially-supported", "supporting_evidence": ["E1"], "refuting_evidence": [],
            "nearest_alternative": "机制 B 解释同一现象", "falsifier": "解耦后现象不变",
            "scope": "数据集 A", "known_flaws": ["F1"], "depends_on": [],
            "validity": validity("已按预注册写入", 6),
            "contract": {"statement": "机制 A", "scope": "数据集 A",
                         "critical_assumptions": [], "supporting_required": ["E1"],
                         "refuting": "解耦后不变", "nearest_alternative": "机制 B",
                         "minimal_discriminating_experiment": "X2",
                         "expected_outcomes": {"O1": "落差下降", "O2": "落差不变"},
                         "kill_rule": "若 O2 出现则降级", "expansion_rule": "O1 且 X3 通过则扩展"},
        }],
        "evidence": [{
            "id": "E1", "kind": "experiment", "supports": ["C1"], "contradicts": [],
            "strength": "strong", "scope": "数据集 A", "epistemic_status": "Observed",
            "source_ref": "X1（seed=0）", "verification_tier": "T2", "depends_on": ["X1"],
            "validity": validity("X1 done", 6),
        }],
        "assumptions": [], "hypotheses": [],
        "experiments": [{
            "id": "X1", "parent": None, "stage": "X4", "claim_targeted": ["C1"],
            "alternative_targeted": ["ALT-1"], "code_commit": "legacy0001",
            "data_split": "A/train", "seed": 0, "metric": "落差", "result": "落差 0.8",
            "interpretation": "初步", "unexpected": ["中心 C 方向相反"], "known_flaws": [],
            "next_branches": [], "status": "done",
            "preregistration": {"frozen_at_state_version": 5, "outcomes": [
                {"id": "O1", "observation": "落差下降", "update": [{"target": "C1", "op": "strengthen"}]}]},
            "result_at_state_version": 6, "depends_on": [], "validity": validity("按预注册写入", 6),
            "outcome_analysis": None, "execution_protocol": None,
        }, {
            "id": "X2", "parent": "X1", "stage": "X3", "claim_targeted": ["C1"],
            "alternative_targeted": ["ALT-2"], "code_commit": "TBD", "data_split": "A/fixed",
            "seed": 0, "metric": "落差变化", "result": "", "interpretation": "尚未运行",
            "unexpected": [], "known_flaws": [], "next_branches": [], "status": "running",
            "preregistration": {"frozen_at_state_version": 6, "outcomes": [
                {"id": "O1", "observation": "下降", "criterion": {
                    "kind": "quantitative", "quantity": "落差变化（dB）",
                    "expected_range": [-3.0, -0.5], "tolerance": 0.1, "rule": "下降"},
                 "update": [{"target": "C1", "op": "strengthen"}]}]},
            "result_at_state_version": None, "depends_on": ["X1"],
            "validity": {"status": "pending", "reason": "正在执行", "since_state_version": 6},
            "outcome_analysis": None, "execution_protocol": None,
        }],
        "literature": [], "failures": [{
            "id": "F1", "kind": "failed-to-reproduce", "what": "提高正则强度消除落差",
            "why": "两中心零效应", "referenced_by": ["C1", "X1"], "depends_on": [],
            "validity": validity("未受波及", 6), "source_review": None,
        }],
        "uncertainties": [{"id": "U1", "question": "机制 A 在数据集 B 是否成立？",
                           "importance": "critical", "uncertainty": "high",
                           "cheapest_discriminating_test": "TBD", "status": "open",
                           "depends_on": [], "validity": validity("未受波及", 6)}],
        "assurance": [], "repairs": [],
    }


def selftest() -> int:
    import tempfile

    failures = 0

    def check(name: str, condition: bool) -> None:
        nonlocal failures
        if not condition:
            failures += 1
            print(f"[FAIL] {name}")

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        state_path = root / cg.STATE_NAME
        state_path.write_text(json.dumps(_legacy_state(), ensure_ascii=False), encoding="utf-8")
        before = state_path.read_bytes()

        detection = detect(state_path)
        check("an existing canonical state is an initialized project",
              detection["initialized"] and detection["bootstrap_forbidden"])
        check("bootstrap is refused for an initialized project",
              _guard_bootstrap(state_path) == EXIT_HARD)

        audit = compatibility_audit(state_path, root)
        check("a valid legacy project has no blocking finding",
              not audit["blocking"], )
        check("the running experiment is reported", any(f.rule == "LH8" for f in audit["findings"]))

        check("takeover succeeds", _take(state_path, root) == EXIT_OK)
        check("canonical state is byte-identical after takeover",
              state_path.read_bytes() == before)
        cognition_dir = state_path.parent / cg.COGNITION_DIRNAME
        first = {name: (cognition_dir / name).read_bytes() for name in OWNED_FILES}
        check("takeover report exists", (cognition_dir / REPORT_NAME).is_file())
        handoff = json.loads((cognition_dir / HANDOFF_NAME).read_text(encoding="utf-8"))
        check("handoff records that nothing canonical was touched",
              handoff["canonical_untouched"] is True)
        check("a frozen outcome without a criterion is retrospective, not a verdict",
              any(item["status"] == "retrospective" for item in handoff["unrecovered"]))
        check("missing route documents are marked unknown",
              any(item["status"] == "unknown" for item in handoff["unrecovered"]))
        check("reconstructed mechanisms are flagged retrospective",
              handoff["recovered"]["legacy_mechanisms"] > 0)
        check("the running experiment is not auto-closed",
              any(item["must_not_rerun"] for item in handoff["in_flight"]))

        # idempotent re-takeover
        check("second takeover succeeds", _take(state_path, root) == EXIT_OK)
        second = {name: (cognition_dir / name).read_bytes() for name in OWNED_FILES}
        check("repeated takeover is byte-identical", first == second)
        check("state still untouched", state_path.read_bytes() == before)

        # rollback removes only owned files
        check("rollback succeeds", _rollback(state_path) == EXIT_OK)
        check("rollback removed the cognition directory", not cognition_dir.exists())
        check("rollback left the canonical state alone", state_path.read_bytes() == before)

        # rollback refuses foreign content
        _take(state_path, root)
        (cognition_dir / "notes.txt").write_text("foreign", encoding="utf-8")
        check("rollback refuses unknown files", _rollback(state_path) == EXIT_HARD)
        (cognition_dir / "notes.txt").unlink()
        _rollback(state_path)

        # a terminal experiment with no preregistration must not acquire one
        unregistered = _legacy_state()
        unregistered["experiments"][0]["preregistration"] = None
        unregistered["experiments"][0]["known_flaws"] = ["F1"]
        unregistered_path = root / cg.STATE_NAME
        unregistered_path.write_text(json.dumps(unregistered, ensure_ascii=False),
                                     encoding="utf-8")
        check("a terminal experiment without a preregistration blocks takeover",
              _take(unregistered_path, root) == EXIT_HARD)
        check("blocked takeover invents no prediction", not cognition_dir.exists())

        # blocking findings write nothing
        broken = _legacy_state()
        broken["experiments"][0]["preregistration"]["frozen_at_state_version"] = 99
        broken_path = root / cg.STATE_NAME
        broken_path.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
        check("prediction time leakage blocks", _take(broken_path, root) == EXIT_HARD)
        check("blocked takeover writes nothing", not cognition_dir.exists())

        # missing state
        try:
            _audit(root / "nope" / cg.STATE_NAME, root)
            check("missing state is an environment error", False)
        except cg.CognitionError:
            check("missing state is an environment error", True)
        check("forbidden repeats are recovered from failure memory",
              any(item["kind"] == "failed_repeat" for item in handoff["forbidden_repeats"]))

    print(f"selftest: {'PASS' if failures == 0 else 'FAIL'} ({failures} failures)")
    return EXIT_OK if failures == 0 else EXIT_ERROR


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # noqa: D401 - argparse hook
        self.print_usage(sys.stderr)
        print(f"argument error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(description="Legacy Research Handoff (read-only takeover)")
    parser.add_argument("command", nargs="?",
                        choices=["detect", "audit", "take", "rollback", "guard-bootstrap"])
    parser.add_argument("--state", help="path to research-state.json")
    parser.add_argument("--project", help="project root (inferred when omitted)")
    parser.add_argument("--selftest", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.command:
        build_parser().print_usage(sys.stderr)
        print("argument error: a command is required", file=sys.stderr)
        return EXIT_ERROR
    if not args.state:
        print("argument error: --state is required", file=sys.stderr)
        return EXIT_ERROR
    state_path = Path(args.state).expanduser()
    project = Path(args.project).expanduser() if args.project else None
    try:
        if args.command == "detect":
            print(json.dumps(detect(state_path), ensure_ascii=False, indent=2))
            return EXIT_OK
        if args.command == "guard-bootstrap":
            return _guard_bootstrap(state_path)
        if args.command == "audit":
            return _audit(state_path, project)
        if args.command == "take":
            return _take(state_path, project)
        if args.command == "rollback":
            return _rollback(state_path)
    except cg.CognitionError as exc:
        print(f"environment error: {exc}", file=sys.stderr)
        return EXIT_ENV
    print(f"argument error: unknown command {args.command!r}", file=sys.stderr)
    return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
