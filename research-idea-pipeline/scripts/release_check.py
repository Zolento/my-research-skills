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
    8. Rhetorical Realization 来源冻结 + 四个实际正文的 RE1–RE5 审计
       —— 文本攻击注入测试必须能把发布闸门判红
    9. Evidence Outcome 的五份来源绑定示例、状态回写和 Assurance 决策
       —— 原始结果变异必须让发布闸门判红
    10. PEIG/AALG schema、模板和 CT→MRI 对照变异
        —— 漏掉容量对照必须拒绝正式执行；启动路径仅用 mock/dry-run 测试
    11. Cognitive Insight Engine 的合成 fixture
        —— 构建 → 校验 → 重建必须一致，且 canonical state 逐字节不变
    12. 预测比较器：判据、冻结完整性、区分力、来源绑定
        —— 判据变异必须让闸门判红；无效执行不得变成预测判定
    13. Legacy Research Handoff：无损接管 + 严重错误阻止写回
        —— 接管必须拒绝 Bootstrap、保持 state/scheduler 逐字节不变
    14. 科学价值与自适应发现：无总分、锚点不可改、算子不被永久封禁
        —— 注入聚合分数或删除探索下限必须让闸门判红
    15. 历史回放：十个对抗 case、泄漏防护、消融与端到端 smoke
        —— 注入未来信息必须让回放拒绝执行

退出码
------
0  PASS
1  FAIL（任何一项不过）
"""

from __future__ import annotations

import pathlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
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
        if rel.startswith("docs/") or ".git" in rel or ".dev" in path.relative_to(ROOT).parts:
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


def step_rhetorical_realization() -> Tuple[bool, str]:
    """Run real source projection and recheck every emitted narrative, not metadata alone."""
    import validate_rhetorical_variant as rv
    source = ROOT / "examples" / "narrative-realization" / "source-state.json"
    manifest = ROOT / "examples" / "narrative-realization" / "manifest.json"
    code, out = _run(["scripts/rhetorical_realization.py", "generate", "--state", str(source),
                      "--manifest", str(manifest)])
    if code != 0:
        return False, f"generation exit={code} {out.strip()[-120:]}"
    batch = json.loads(out)
    variants = batch["variants"]
    if len(variants) != len(rv.registry()["profiles"]) or {v["profile"] for v in variants} != set(rv.registry()["profiles"]):
        return False, "pre-registered profile coverage differs"
    state = json.loads(source.read_text(encoding="utf-8"))
    for variant in variants:
        gate = rv.validate(state, batch["snapshot"], variant)
        if gate["status"] != "PASS":
            return False, f"{variant['variant_id']}: {gate['errors']}"
    return True, f"冻结来源 + {len(variants)} 份实际正文全通过 RE 门禁"


def step_evidence_outcome() -> Tuple[bool, str]:
    """Exercise independent shipped artifacts through proposal, state and decision gates."""
    import evidence_outcome as eo
    import state_check as sc
    paths = sorted((ROOT / 'examples' / 'evidence-outcome').glob('*.json'))
    required = {'positive', 'valid-negative', 'invalid-experiment', 'pivot', 'mixed'}
    if {p.stem for p in paths} != required:
        return False, 'positive/negative/invalid/pivot/mixed artifact coverage differs'
    for path in paths:
        case = json.loads(path.read_text(encoding='utf-8'))
        if case.get('schema') != 'evidence-outcome-example@1' or case.get('scenario') != path.stem:
            return False, f'{path.name}: invalid example envelope'
        gate = eo.validate(case['state'], case['packet'], case['analysis'], case['audit'])
        if gate['status'] != 'PASS' or gate['outcome'] != case['expected_outcome']:
            return False, f'{path.name}: outcome gate {gate}'
        result = eo.apply(case['state'], case['packet'], case['analysis'], case['audit'], timestamp=case['timestamp'])
        if result['status'] != 'PASS' or not sc.check_state(result['state']).ok:
            return False, f'{path.name}: state transaction {result}'
        decision = eo.decision_gate(result['state'], case['packet']['experiment_id'], case['assurance'])
        if decision['status'] != 'PASS' or [d['action'] for d in decision['decisions']] != case['expected_decisions']:
            return False, f'{path.name}: Assurance decision {decision}'
        if result['state'].get('narrative_view') != case['state'].get('narrative_view'):
            return False, f'{path.name}: communication view was modified'
    return True, f'{len(paths)} 份来源/状态/决策全通过 EO 门禁（科学判断为示例，不是模型准确率）'


def step_cognitive_memory() -> Tuple[bool, str]:
    """Cognitive Insight Engine: build → check → rebuild must agree, state untouched.

    The fixture is copied into a temporary route directory so the shipped example
    stays a pure input. Two things are asserted mechanically: `check` passes after
    `build`, and the canonical state file is byte-identical afterwards. Without the
    second assertion a projection could quietly become a second authority.
    """
    source = ROOT / "examples" / "cognition"
    state_source = source / "state.json"
    revisions_source = source / "model-revisions.jsonl"
    if not state_source.is_file() or not revisions_source.is_file():
        return False, "examples/cognition fixture is incomplete"
    with tempfile.TemporaryDirectory() as temp:
        route = pathlib.Path(temp) / "routeA"
        (route / "cognition").mkdir(parents=True)
        state_path = route / "research-state.json"
        shutil.copy(state_source, state_path)
        shutil.copy(revisions_source, route / "cognition" / "model-revisions.jsonl")
        before = state_path.read_bytes()
        code, out = _run(["scripts/cognition.py", "build", "--state", str(state_path)])
        if code != 0:
            return False, f"build exit={code} {out.strip()[-160:]}"
        if state_path.read_bytes() != before:
            return False, "cognitive build modified the canonical state"
        code, out = _run(["scripts/cognition.py", "check", "--state", str(state_path)])
        if code != 0:
            return False, f"check exit={code} {out.strip()[-160:]}"
        first = (route / "cognition" / "index.json").read_bytes()
        code, out = _run(["scripts/cognition.py", "build", "--state", str(state_path)])
        if code != 0 or (route / "cognition" / "index.json").read_bytes() != first:
            return False, "cognitive index is not reproducible from the same inputs"
        index = json.loads(first.decode("utf-8"))
        if index.get("diagnostics"):
            return False, f"fixture carries diagnostics: {index['diagnostics'][:1]}"
    return True, (f"fixture build/check/rebuild green, "
                  f"mechanisms={len(index['mechanisms'])}, state byte-identical")


def step_prediction_comparator() -> Tuple[bool, str]:
    """Predictions must be decidable, frozen, and never self-certified.

    The step mutates a valid packet and a valid criterion: a gate that cannot be made red
    by a mutation is not a gate.
    """
    import prediction_compare as pc
    fixture = ROOT / "examples" / "cognition"
    state = json.loads((fixture / "state.json").read_text(encoding="utf-8"))
    packet = json.loads((fixture / "prediction-observation.json").read_text(encoding="utf-8"))
    assessment, diagnostics = pc.assess_experiment(state, packet)
    if assessment["outcome_class"] != "PREDICTION_HELD" or diagnostics:
        return False, f"fixture observation did not compare cleanly: {assessment['outcome_class']}"
    for outcome in state["experiments"][0]["preregistration"]["outcomes"]:
        if pc.criterion_errors(outcome.get("criterion"), "criterion"):
            return False, "fixture criterion is malformed"
    forged = json.loads(json.dumps(state))
    forged["experiments"][0]["preregistration"]["outcomes"][0]["criterion"]["expected_range"] = [0.95, 3.0]
    changed, _ = pc.assess_experiment(forged, packet)
    if changed["outcome_class"] == "PREDICTION_HELD":
        return False, "a mutated criterion escaped the comparator"
    crippled = json.loads(json.dumps(state))
    del crippled["experiments"][0]["preregistration"]["outcomes"][0]["criterion"]
    legacy, legacy_diagnostics = pc.assess_experiment(crippled, packet)
    if legacy["predictions"][0]["verdict"] != "UNTESTABLE":
        return False, "an outcome without a criterion produced a verdict"
    if not any(d.rule == "PC1" for d in legacy_diagnostics):
        return False, "a missing criterion was not reported"
    invalid = json.loads(json.dumps(packet))
    invalid["execution"]["validity"] = "INVALID"
    broken, _ = pc.assess_experiment(state, invalid)
    if broken["outcome_class"] != "INVALID_EXECUTION":
        return False, "an invalid execution became a scientific verdict"
    card = json.loads((fixture / pc.INSIGHT_CARDS_NAME).read_text(encoding="utf-8"))
    if pc.insight_card_errors(card, state):
        return False, "the fixture insight card does not validate"
    self_certified = json.loads(json.dumps(card))
    self_certified["declared_class"] = "evidence_supported_insight"
    if not any(d.rule == "PC7" for d in pc.insight_card_errors(self_certified, state)):
        return False, "a self-certified insight card escaped PC7"
    return True, "criterion mutation + missing criterion + invalid run + self-certification 全部判红"


def step_legacy_handoff() -> Tuple[bool, str]:
    """Takeover of an initialized project: lossless, idempotent, no fabricated history."""
    import cognition as cg
    import legacy_handoff as lh
    fixture = ROOT / "examples" / "cognition"
    with tempfile.TemporaryDirectory() as temp:
        route = pathlib.Path(temp) / ".research-idea-pipeline" / "routes" / "A"
        route.mkdir(parents=True)
        state_path = route / cg.STATE_NAME
        shutil.copy(fixture / "state.json", state_path)
        scheduler = route / "scheduler.json"
        scheduler.write_text(json.dumps({"state_version": 5, "next_actions": [],
                                         "eig_calibration": {"records": []}}), encoding="utf-8")
        state_before = state_path.read_bytes()
        scheduler_before = scheduler.read_bytes()
        if lh.detect(state_path)["bootstrap_forbidden"] is not True:
            return False, "an initialized project did not refuse a fresh Bootstrap"
        code, out = _run(["scripts/legacy_handoff.py", "take", "--state", str(state_path)])
        if code != 0:
            return False, f"take exit={code} {out.strip()[-160:]}"
        if state_path.read_bytes() != state_before:
            return False, "takeover modified the canonical state"
        if scheduler.read_bytes() != scheduler_before:
            return False, "takeover reset scheduler telemetry"
        cognition_dir = route / cg.COGNITION_DIRNAME
        first = {name: (cognition_dir / name).read_bytes() for name in lh.OWNED_FILES}
        code, out = _run(["scripts/legacy_handoff.py", "take", "--state", str(state_path)])
        if code != 0:
            return False, f"second take exit={code}"
        if {name: (cognition_dir / name).read_bytes() for name in lh.OWNED_FILES} != first:
            return False, "repeated takeover is not idempotent"
        if not json.loads(out)["already_initialized"]:
            return False, "repeated takeover was not reported"
        unregistered = json.loads(state_before.decode("utf-8"))
        unregistered["experiments"][0]["preregistration"] = None
        state_path.write_text(json.dumps(unregistered, ensure_ascii=False), encoding="utf-8")
        shutil.rmtree(cognition_dir)
        code, out = _run(["scripts/legacy_handoff.py", "take", "--state", str(state_path)])
        if code != 3 or cognition_dir.exists():
            return False, "a terminal experiment without a preregistration did not block"
    return True, "无损接管 + 幂等 + Bootstrap 拒绝 + 缺失预注册阻止写回"


def step_scientific_value() -> Tuple[bool, str]:
    """Per-dimension value, read-only anchors, and no permanent operator ban."""
    import cognition as cg
    import strategy_memory as sm
    state, revisions, scheduler = sm._fixture()
    index, _ = cg.full_index(state, revisions, "A", None, scheduler)
    assessment = sm.value_assessment(state, index, "H1", scheduler)
    if sm.validate_value(assessment):
        return False, "the fixture value assessment does not validate"
    for key in sm.BANNED_AGGREGATE_KEYS:
        if key in assessment:
            return False, f"an aggregate score was produced: {key}"
    scored = dict(assessment, score=0.9)
    if not any(d.rule == "SV1" for d in sm.validate_value(scored)):
        return False, "an injected aggregate escaped SV1"
    baseless = json.loads(json.dumps(assessment))
    baseless["decision_value"]["changes_route"]["basis"] = []
    if not any(d.rule == "SV2" for d in sm.validate_value(baseless)):
        return False, "a dimension without a source escaped SV2"
    priors = sm.operator_priors(state, index, scheduler)
    if sm.validate_priors(priors):
        return False, "the fixture operator priors do not validate"
    stripped = json.loads(json.dumps(priors))
    stripped["exploration_floor"] = []
    if not any(d.rule == "SV7" for d in sm.validate_priors(stripped)):
        return False, "removing the exploration floor escaped SV7"
    banned = json.loads(json.dumps(priors))
    banned["by_operator"]["theory_lens"] = {"status": "forbidden", "failures": [], "successes": []}
    if not any(d.rule == "SV5" for d in sm.validate_priors(banned)):
        return False, "a permanent operator ban escaped SV5"
    before = json.dumps(scheduler, sort_keys=True)
    recommendation = sm.recommend_strategy(state, index, scheduler, revisions)
    if json.dumps(scheduler, sort_keys=True) != before:
        return False, "strategy learning wrote into scheduler telemetry"
    if recommendation["exploration_rounds_delta"] != 0:
        return False, "the recommendation added exploration rounds unconditionally"
    if state["contract"]["primary_anchor"] != "phenomenon":
        return False, "a strategy computation changed the research anchor"
    return True, "per-dimension value + no aggregate + floor kept + no ban + telemetry read-only"


def step_discovery_replay() -> Tuple[bool, str]:
    """Replay fixtures, the leak guard, the ablation ladder and the end-to-end smoke."""
    import research_replay as rr
    cases = rr.load_cases(ROOT / "examples" / "replay" / "adversarial")
    if len(cases) != 10:
        return False, f"expected 10 adversarial cases, found {len(cases)}"
    generated = rr.adversarial_cases()
    if [case["id"] for case in cases] != [case["id"] for case in generated]:
        return False, "shipped cases drifted from the generator"
    for case in cases:
        visible = rr.visible_view(case)
        if rr.leak_scan(case, visible):
            return False, f"{case['id']}: hidden content is reachable from the visible view"
        if rr.case_errors(case):
            return False, f"{case['id']}: {rr.case_errors(case)[0].render()}"
    leaking = json.loads(json.dumps(cases[0]))
    leaking["visible"]["known_conditions"].append(leaking["hidden"]["later_results"][0])
    try:
        rr.run_case(leaking)
        return False, "a leaking case ran instead of being refused"
    except Exception:
        pass
    report = rr.run_suite(cases, runs=1)
    if report["per_arm"]["baseline"]["pass_rate"] != 0.0:
        return False, "the baseline arm passed the adversarial suite"
    if report["per_arm"]["full_cie"]["pass_rate"] != 1.0:
        return False, "the full arm failed the adversarial suite"
    if report["per_arm"]["baseline"]["dimensions"]["prediction_quality"]["mean"] is not None:
        return False, "an arm without the comparator produced prediction quality"
    tiny = rr.run_suite(cases[:1], runs=1)
    if tiny["sufficient_sample"] or "不得宣称提升" not in tiny["claim"]:
        return False, "an undersized sample claimed an improvement"
    if not report["undifferentiated_arms"]:
        return False, "indistinguishable arms were not reported"
    with tempfile.TemporaryDirectory() as temp:
        smoke = rr.smoke(pathlib.Path(temp))
        if not smoke["passed"]:
            return False, f"smoke failed: {[s for s in smoke['steps'] if not s['ok']]}"
        if not smoke["canonical_untouched"]:
            return False, "the smoke test modified the canonical state"
    return True, (f"{len(cases)} cases leak-checked; baseline 0% vs full 100%; "
                  "comparator capability visible; undersized sample claims nothing; smoke green")


def step_execution_identifiability() -> Tuple[bool, str]:
    import execution_gate as eg
    case = json.loads((ROOT/'examples/preflight-identifiability/ct-mri.json').read_text(encoding='utf-8'))
    if case.get('schema') != 'preflight-e2e@1': return False, 'invalid CT→MRI fixture envelope'
    state = case['state']; x = state['experiments'][-1]
    gate = eg.peig(state,x['id'])
    if gate['status'] != 'PASS': return False, str(gate)
    for name in ('preflight-protocol','diagnostic-protocol','execution-manifest'):
        template = json.loads((ROOT/'templates'/f'{name}.template.json').read_text(encoding='utf-8'))
        errors = eg.schema_errors(template,f'{name}.schema.json')
        if errors: return False, str(errors)
    scheduler = json.loads((ROOT/'templates/scheduler.template.json').read_text(encoding='utf-8'))
    if eg.schema_errors(scheduler,'scheduler.schema.json'): return False, 'scheduler template/schema mismatch'
    x['execution_protocol']['arms'][0]['trainable_parameters'] *= 2
    if eg.peig(state,x['id'])['status'] != 'HOLD': return False, 'capacity mutation escaped gate'
    return True, 'CT→MRI design + schemas/templates + capacity mutation (mock execution is covered by tests)'


STEPS = (
    ("离线测试（含 golden path / parity / linter / deprecated / links）", step_tests),    ("state_check --selftest", step_selftest),
    ("模板自身通过校验", step_template),
    ("规则表逐字比对（S1—S7 + V1—V24）", step_rule_table_parity),
    ("三方读写表逐格比对", step_readwrite_parity),
    ("文档引用的脚本存在", step_referenced_scripts_exist),
    ("Structural Equivalence（EQ1—EQ13 + NN1—NN14）自检 + 模板 + fixture", step_structural_equivalence),
    ("Rhetorical Realization（RE1–RE5）来源与正文", step_rhetorical_realization),
    ("Evidence Outcome 来源/回写/Assurance/决策", step_evidence_outcome),
    ("PEIG/AALG schemas/templates/CT→MRI mutation", step_execution_identifiability),
    ("Cognitive Insight Engine 合成 fixture（构建/校验/重建/状态不变）", step_cognitive_memory),
    ("预测比较器（判据/冻结/区分力/来源绑定变异）", step_prediction_comparator),
    ("Legacy Handoff（无损接管/幂等/Bootstrap 拒绝/阻止写回）", step_legacy_handoff),
    ("科学价值与自适应发现（无总分/锚点只读/算子不封禁）", step_scientific_value),
    ("历史回放（对抗 case/泄漏防护/消融/端到端 smoke）", step_discovery_replay),
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
