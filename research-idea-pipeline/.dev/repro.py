#!/usr/bin/env python3
"""Phase 1 reproduction for fix/loop-runtime-correctness (FIX-01..FIX-04)."""
import copy, json, sys, tempfile, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'scripts'))

import evidence_outcome as eo
import execution_gate as eg
import experiment_execute as ex
import preset_router as pr
import strategy_memory as sm
import test_evidence_outcome as teo
import test_execution_gate as teg

print("=" * 72)
print("FIX-01: dry-run consumes the formal receipt / budget")
print("=" * 72)
with tempfile.TemporaryDirectory() as temp:
    root = pathlib.Path(temp)
    state = teg.fixture()['state']
    x = state['experiments'][-1]
    manifest = teg.resources(state, root)
    ledger = ex.Ledger(root / 'ledger')
    issued = teg.issue(state, x['id'], manifest, ledger)
    print("  issue:", issued['status'])
    dry = teg.managed_run(state, x['id'], manifest, issued['receipt'], ledger, execute=False)
    consumes = [e for e in ledger.events if e.get('kind') == 'consume']
    print("  dry-run:", dry['status'], '| command_started:', dry.get('command_started'),
          '| consume 事件:', len(consumes), '| dry_run 标记:', [e.get('dry_run') for e in consumes])
    real = teg.managed_run(state, x['id'], manifest, issued['receipt'], ledger, execute=True)
    print("  随后正式执行:", real['status'], real.get('errors'))

print()
print("=" * 72)
print("FIX-02: scheduler global FAIL still yields a dispatch")
print("=" * 72)
state = __import__('evidence_outcome').apply(*teo.fixture('negative'), timestamp=teo.TIMESTAMP)['state']
scheduler = {"state_version": state['state_version'] + 7, "next_actions": [
    {"action": "X1", "type": "repair", "target": "C1", "eig": "high", "cost": "low"}],
    "eig_calibration": {"records": []},
    "operator_stats": {"by_operator": {}, "recurring_failure_patterns": []}}
report = eg.scheduler_check(state, scheduler)
decision = sm.strategy_decision(state, {}, scheduler, [])
print("  scheduler_check:", report['status'], report['errors'])
print("  hard_gates.scheduler_check:", decision['hard_gates']['scheduler_check'],
      "| blocked_actions:", decision['hard_gates']['blocked_actions'])
print("  chosen:", decision['chosen'], "| strategy_applied:", decision['strategy_applied'])

print()
print("=" * 72)
print("FIX-03: written strategy revision vs SV6 actor policy")
print("=" * 72)
print("  cognition.REVISION_ACTORS:", list(pr.cg.REVISION_ACTORS))
fake = {"kind": "strategy_update", "subject": "local", "summary": "s",
        "actor": "R14", "refs": {"hypotheses": ["H1"]}, "after": {"operator": "local"}}
diags = sm.validate_strategy_revisions(state, [fake])
print("  validate_strategy_revisions(actor=R14):", [d.render() for d in diags] or "PASS")
fake['actor'] = 'CIE'
print("  validate_strategy_revisions(actor=CIE):",
      [d.render() for d in sm.validate_strategy_revisions(state, [fake])] or "PASS")

print()
print("=" * 72)
print("FIX-04: post-update Assurance cannot be consumed by the loop")
print("=" * 72)
state = __import__('evidence_outcome').apply(*teo.fixture('positive'), timestamp=teo.TIMESTAMP)['state']
with tempfile.TemporaryDirectory() as temp:
    route = pathlib.Path(temp)
    state_path = route / 'research-state.json'
    state_path.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
    ctx = {"state": state, "index": {"state_version": state['state_version']},
           "index_missing": False, "scheduler": None, "revisions": [],
           "route_dir": route, "state_path": state_path}
    first = pr._loop_step(ctx)
    print("  无 Assurance:", first['step'], '|', (first.get('decision_gate') or [])[:1])
    receipt = state['experiments'][-1]['outcome_analysis']
    assurance = {"schema": "evidence-outcome-assurance@1",
                 "state_digest": eo.digest(state),
                 "analysis_digest": eo.digest(receipt['analysis']),
                 "checks": {k: {"status": "PASS", "reason": "reviewed"} for k in
                            ("integrity", "claim_calibration", "reproducibility",
                             "stop_rule_compliance")}}
    gate = eo.decision_gate(state, 'X1', assurance)
    print("  真实 decision_gate(带合格 Assurance):", gate['status'])
    (route / 'assurance').mkdir(exist_ok=True)
    (route / 'assurance' / 'outcome').mkdir(exist_ok=True)
    (route / 'assurance' / 'outcome' / (receipt['analysis']['id'] + '.json')).write_text(
        json.dumps(assurance), encoding='utf-8')
    second = pr._loop_step(ctx)
    print("  同一 state 已有合格 Assurance 落盘后再跑 Loop:", second['step'])
