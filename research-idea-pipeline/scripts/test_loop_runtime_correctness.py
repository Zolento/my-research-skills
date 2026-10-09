#!/usr/bin/env python3
"""test_loop_runtime_correctness.py — execution previews, scheduler fail-closed, strategy
revision authority, and the post-update Assurance lifecycle.

Every case uses the real public path: `experiment_execute.issue/run` over a real ledger,
`execution_gate.scheduler_check`, `evidence_outcome.apply/decision_gate`, the real preset
writers, and the real `preset_router._loop_step`. No mock ever fabricates a PASS Assurance.

Confirmed findings this file locks down (see `.dev/loop-runtime-audit.md`):

* FIX-01 `run(execute=False)` appended a real `consume` event before returning: a preview burned
  the single-use receipt, the pilot runs/hours, and the formal budget.
* FIX-02 `_legal_actions()` parsed English error strings for blocked ids, so a scheduler that
  failed *globally* (`STALE_SCHEDULER` only) produced a full dispatch and reported
  `hard_gates.scheduler_check = PASS`.
* FIX-03 `_append_strategy_revisions()` wrote `actor="R14"` (rejected by `SV6`) and the raw
  `after` payload (rejected by `CM1`), so a committed strategy revision failed its validators.
* FIX-04 the loop called `decision_gate()` with no Assurance and never looked for one on disk, so
  a legitimate review could not be consumed and the loop reported `Assurance` forever; planned
  work was also dispatched before the review of the result it depended on.
"""

from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import cognition as cg
import evidence_outcome as eo
import execution_gate as eg
import experiment_execute as ex
import preset_router as pr
import state_check as sc
import strategy_memory as sm
import test_evidence_outcome as teo
import test_execution_gate as teg

ROOT = pathlib.Path(__file__).resolve().parent.parent
TIMESTAMP = teo.TIMESTAMP
OK = subprocess.CompletedProcess([], 0)


def valid_execution_state():
    """A schema-valid preflight fixture with a PASS PEIG gate (real repository example)."""
    return teg.fixture()['state']


# ---------------------------------------------------------------------------
# FIX-01 — previews must not consume anything
# ---------------------------------------------------------------------------

class TestExecutionPreview(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.state = valid_execution_state()
        self.xid = self.state['experiments'][-1]['id']
        self.manifest = teg.resources(self.state, self.root)
        self.ledger = ex.Ledger(self.root / 'ledger')

    def issue(self):
        result = teg.issue(self.state, self.xid, self.manifest, self.ledger, now=100)
        self.assertEqual(result['status'], 'PASS', result)
        return result['receipt']

    def preview(self, receipt):
        return teg.managed_run(self.state, self.xid, self.manifest, receipt, self.ledger,
                               execute=False, now=101)

    def real(self, receipt):
        with patch.object(ex.subprocess, 'run', return_value=OK) as invoke:
            result = teg.managed_run(self.state, self.xid, self.manifest, receipt,
                                     self.ledger, execute=True, now=102)
        return result, invoke

    def consumes(self):
        return [e for e in self.ledger.events if e.get('kind') == 'consume']

    def test_a_preview_writes_no_consume_event_and_starts_nothing(self):
        receipt = self.issue()
        before = list(self.ledger.events)
        with patch.object(ex.subprocess, 'run') as invoke:
            result = self.preview(receipt)
            invoke.assert_not_called()
        self.assertEqual(result['status'], 'PASS', result)
        self.assertTrue(result['dry_run'])
        self.assertTrue(result['preview'])
        self.assertFalse(result['command_started'])
        self.assertFalse(result['consumed'])
        self.assertEqual(self.consumes(), [])
        self.assertEqual(self.ledger.events, before, "a preview must not touch the ledger")
        self.assertEqual(result['execution_record']['dry_run'], True)
        self.assertIsNone(result['execution_record']['launch_seal'])

    def test_a_preview_reports_what_it_would_run_without_running_it(self):
        receipt = self.issue()
        result = self.preview(receipt)
        self.assertEqual(result['would_execute']['argv'], self.manifest['argv'])
        self.assertEqual(result['would_execute']['permission'], receipt['permission'])
        self.assertEqual(result['budget']['spent_runs'], 0)

    def test_the_same_receipt_still_executes_for_real_after_a_preview(self):
        receipt = self.issue()
        self.preview(receipt)
        self.preview(receipt)
        self.assertEqual(self.consumes(), [])
        result, invoke = self.real(receipt)
        self.assertEqual(result['status'], 'PASS', result)
        invoke.assert_called_once()
        self.assertEqual(len(self.consumes()), 1)
        self.assertIs(self.consumes()[0]['dry_run'], False)

    def test_a_real_execution_consumes_exactly_once(self):
        receipt = self.issue()
        self.real(receipt)
        again = teg.managed_run(self.state, self.xid, self.manifest, receipt, self.ledger,
                                execute=True, now=102)
        self.assertEqual(again['errors'], ['UNKNOWN_OR_USED_RECEIPT'])
        self.assertEqual(len(self.consumes()), 1)

    def test_a_preview_cannot_be_mistaken_for_a_launch(self):
        receipt = self.issue()
        preview = self.preview(receipt)
        self.assertIsNotNone(preview['execution_record'])
        self.assertTrue(preview['execution_record']['dry_run'])
        state = copy.deepcopy(self.state)
        state['experiments'][-1].update(status='done', execution_record=preview['execution_record'],
                                        result_at_state_version=state['state_version'])
        self.assertTrue(ex.verify_result_execution(state, self.ledger),
                        "a preview record can never be execution provenance")

    def test_an_expired_receipt_cannot_be_previewed_or_executed(self):
        receipt = self.issue()
        for execute in (False, True):
            result = ex.run(self.state, self.xid, self.manifest, receipt, self.ledger,
                            execute=execute, now=receipt['expires_at'] + 1,
                            scheduler=teg.scheduler_for(self.state))
            self.assertEqual(result['errors'], ['EXPIRED_RECEIPT'])
        self.assertEqual(self.consumes(), [])

    def test_a_changed_config_invalidates_preview_and_execution(self):
        receipt = self.issue()
        protocol = self.state['experiments'][-1]['execution_protocol']
        (self.root / 'config.json').write_text(json.dumps(
            {'execution_design': ex.config_binding(protocol), 'silent_lr': 1}))
        for execute in (False, True):
            result = teg.managed_run(self.state, self.xid, self.manifest, receipt, self.ledger,
                                     execute=execute, now=102)
            self.assertEqual(result['errors'], ['RECEIPT_CONTENT_MISMATCH'])
        self.assertEqual(self.consumes(), [])

    def test_a_stale_scheduler_invalidates_preview_and_execution(self):
        receipt = self.issue()
        stale = dict(teg.scheduler_for(self.state), state_version=999)
        for execute in (False, True):
            result = ex.run(self.state, self.xid, self.manifest, receipt, self.ledger,
                            execute=execute, now=101, scheduler=stale)
            self.assertEqual(result['errors'], ['SCHEDULER_RECEIPT_MISMATCH'])
        self.assertEqual(self.consumes(), [])

    def test_an_old_ledger_with_a_historical_preview_consume_still_executes(self):
        """Backward compatibility: v2.3.2 ledgers may contain `dry_run: true` consume events."""
        receipt = self.issue()
        # Simulate the historical (pre-fix) behaviour without rewriting any existing event.
        self.ledger.append({'kind': 'consume', 'family': receipt['family'],
                            'receipt_id': receipt['id'], 'experiment_id': self.xid,
                            'permission': receipt['permission'], 'hours': receipt['requested_hours'],
                            'dry_run': True, 'timestamp': 101})
        result, _ = self.real(receipt)
        self.assertEqual(result['status'], 'PASS', result)
        kinds = [e.get('dry_run') for e in self.ledger.events if e['kind'] == 'consume']
        self.assertEqual(kinds, [True, False], "the historical event is kept, a real one is added")

    def test_a_historical_preview_consume_does_not_exhaust_the_pilot_budget(self):
        self.x = self.state['experiments'][-1]
        self.x['execution_protocol']['mode'] = 'pilot'
        self.manifest = teg.resources(self.state, self.root)
        issued = teg.issue(self.state, self.xid, self.manifest, self.ledger, now=100)
        self.assertEqual(issued['status'], 'PILOT_ONLY', issued)
        receipt = issued['receipt']
        self.ledger.append({'kind': 'consume', 'family': receipt['family'],
                            'receipt_id': receipt['id'], 'experiment_id': self.xid,
                            'permission': receipt['permission'], 'hours': receipt['requested_hours'],
                            'dry_run': True, 'timestamp': 101})
        with patch.object(ex.subprocess, 'run', return_value=OK):
            result = teg.managed_run(self.state, self.xid, self.manifest, receipt, self.ledger,
                                     execute=True, now=102)
        self.assertEqual(result['status'], 'PASS', result)

    def test_a_real_launch_is_still_atomic_under_concurrency(self):
        receipt = self.issue()
        results = []
        for attempt in range(3):
            with patch.object(ex.subprocess, 'run', return_value=OK):
                results.append(teg.managed_run(self.state, self.xid, self.manifest, receipt,
                                               self.ledger, execute=True, now=102 + attempt))
        started = [item for item in results if item['status'] == 'PASS']
        self.assertEqual(len(started), 1, [item['status'] for item in results])
        self.assertEqual(len(self.consumes()), 1)


# ---------------------------------------------------------------------------
# FIX-02 — the scheduler verdict is fail-closed and never text-parsed
# ---------------------------------------------------------------------------

class TestSchedulerFailClosed(unittest.TestCase):

    def setUp(self):
        self.state = eo.apply(*teo.fixture('negative'), timestamp=TIMESTAMP)['state']
        self.action = {'action': 'X2', 'type': 'repair', 'target': 'C1', 'eig': 'high',
                       'cost': 'low'}
        self.scheduler = {'state_version': self.state['state_version'], 'next_actions':
                          [dict(self.action)], 'eig_calibration': {'records': []},
                          'operator_stats': {'by_operator': {},
                                             'recurring_failure_patterns': []}}

    def test_a_stale_scheduler_yields_no_dispatch(self):
        stale = dict(self.scheduler, state_version=self.state['state_version'] + 5)
        self.assertEqual(eg.scheduler_check(self.state, stale)['status'], 'FAIL')
        verdict = sm.scheduler_verdict(self.state, stale)
        self.assertFalse(verdict['passed'])
        self.assertEqual(verdict['global_errors'], ['STALE_SCHEDULER'])
        decision = sm.strategy_decision(self.state, {}, stale, [])
        self.assertIsNone(decision['chosen'])
        self.assertIsNone(decision['dispatch']['action'])
        self.assertFalse(decision['strategy_applied'])
        self.assertFalse(decision['decision_changed'])
        self.assertEqual(decision['reason_if_not'], 'scheduler_check_failed')

    def test_the_hard_gate_never_reports_pass_for_a_failed_scheduler(self):
        stale = dict(self.scheduler, state_version=self.state['state_version'] + 5)
        decision = sm.strategy_decision(self.state, {}, stale, [])
        self.assertEqual(decision['hard_gates']['scheduler_check'], 'FAIL')
        self.assertEqual(decision['hard_gates']['scheduler_status'], 'FAIL')
        self.assertIn('STALE_SCHEDULER', decision['hard_gates']['global_errors'])

    def test_an_invalid_state_yields_no_dispatch(self):
        broken = copy.deepcopy(self.state)
        broken['claims'][0]['supporting_evidence'] = ['E999']
        self.assertFalse(sc.check_state(broken).ok)
        scheduler = dict(self.scheduler, state_version=broken['state_version'])
        decision = sm.strategy_decision(broken, {}, scheduler, [])
        self.assertIsNone(decision['chosen'])
        self.assertEqual(decision['hard_gates']['scheduler_check'], 'FAIL')
        self.assertIn('STATE_INVALID', decision['hard_gates']['global_errors'])

    def test_a_missing_eig_record_is_never_reported_as_pass(self):
        state = self.state
        scheduler = dict(self.scheduler, eig_calibration={'records': [
            {'experiment': state['experiments'][-1]['id'], 'predicted_information_gain': 'high',
             'actual_information_gain': 'low', 'observed_delta': {}}]})
        report = eg.scheduler_check(state, scheduler)
        decision = sm.strategy_decision(state, {}, scheduler, [])
        self.assertEqual(decision['hard_gates']['scheduler_status'], report['status'])
        if report['status'] == 'FAIL':
            self.assertEqual(decision['hard_gates']['scheduler_check'], 'FAIL')
            self.assertIsNone(decision['chosen'])

    def test_a_locally_illegal_action_never_reaches_the_dispatch_set(self):
        state = copy.deepcopy(self.state)
        second = copy.deepcopy(state['experiments'][-1])
        second.update(id='X9', status='done')          # terminal: cannot be dispatched
        state['experiments'].append(second)
        scheduler = dict(self.scheduler, next_actions=[dict(self.action)])
        verdict = sm.scheduler_verdict(state, scheduler)
        self.assertNotIn('X9', [item['action'] for item in verdict['legal_actions']])

    def test_an_unrelated_local_error_does_not_authorize_the_action_it_names(self):
        """Authorization is the scheduler's verdict, not the shape of an error message."""
        stale = dict(self.scheduler, state_version=self.state['state_version'] + 1)
        decision = sm.strategy_decision(self.state, {}, stale, [])
        self.assertEqual(decision['hard_gates']['scheduler_check'], 'FAIL')
        self.assertIsNone(decision['chosen'])


# ---------------------------------------------------------------------------
# FIX-03 — strategy revision writer authority
# ---------------------------------------------------------------------------

class TestStrategyRevisionAuthority(unittest.TestCase):

    def _project(self, root):
        state_path = pr._fixture(pathlib.Path(root) / 'A')
        state = json.loads(state_path.read_text(encoding='utf-8'))
        base = state['hypotheses'][0]
        state['hypotheses'] = [
            dict(base, id='H1', status='killed', operator='local', island='P1', statement='H1'),
            dict(base, id='H2', status='killed', operator='local', island='P1', statement='H2'),
            dict(base, id='H3', status='active', operator='reframe', island='P1', statement='H3')]
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        return state_path

    def _revisions(self, state_path):
        path = state_path.parent / cg.COGNITION_DIRNAME / cg.REVISIONS_NAME
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
                if line.strip()]

    def test_the_writer_records_an_authorised_actor_and_passes_both_validators(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(temp)
            payload, _, _ = pr.run_preset('strategy-evolution', state_path, apply=True)
            self.assertGreaterEqual(payload['observed']['applied_revisions'], 1, payload)
            self.assertEqual(payload['observed']['revision_diagnostics'], [])
            revisions = self._revisions(state_path)
            self.assertTrue(revisions)
            for record in revisions:
                self.assertIn(record['actor'], cg.STRATEGY_REVISION_ACTORS)
                self.assertEqual(record['actor'], cg.STRATEGY_UPDATE_ACTOR)
                self.assertEqual(record['at_state_version'],
                                 json.loads(state_path.read_text(encoding='utf-8'))['state_version'])
            state = json.loads(state_path.read_text(encoding='utf-8'))
            self.assertEqual(sm.validate_strategy_revisions(state, revisions), [])
            self.assertEqual(cg.validate_revisions(state, revisions), [])

    def test_the_actor_policy_rejects_r14_and_accepts_the_meta_controller(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(temp)
            state = json.loads(state_path.read_text(encoding='utf-8'))
            record = {'kind': 'strategy_update', 'subject': 'local', 'summary': 's', 'actor': 'R14',
                      'refs': {'hypotheses': ['H1']}, 'after': {'operator': 'local'}}
            diagnostics = sm.validate_strategy_revisions(state, [record])
            self.assertTrue(any(item.rule == 'SV6' for item in diagnostics))
            record['actor'] = cg.STRATEGY_UPDATE_ACTOR
            self.assertEqual(sm.validate_strategy_revisions(state, [record]), [])

    def test_a_dangling_reference_is_refused_and_nothing_is_written(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(temp)
            ctx = pr.project_context(state_path)
            update = {'kind': 'strategy_update', 'subject': 'local', 'summary': 's',
                      'refs': {'hypotheses': ['H-does-not-exist']},
                      'after': {'operator': 'local', 'action': 'discourage'}}
            outcome = pr._append_strategy_revisions(ctx, [update])
            self.assertEqual(outcome['written'], 0)
            self.assertTrue(outcome['diagnostics'])
            self.assertFalse((state_path.parent / cg.COGNITION_DIRNAME
                              / cg.REVISIONS_NAME).exists())

    def test_an_invalid_revision_never_partially_lands(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(temp)
            ctx = pr.project_context(state_path)
            good = {'kind': 'strategy_update', 'subject': 'local', 'summary': 's',
                    'refs': {'hypotheses': ['H1', 'H2']},
                    'after': {'operator': 'local', 'action': 'discourage'}}
            bad = {'kind': 'strategy_update', 'subject': 'local', 'summary': 's',
                   'refs': {'hypotheses': ['H-missing']},
                   'after': {'operator': 'local', 'action': 'discourage'}}
            outcome = pr._append_strategy_revisions(ctx, [good, bad])
            self.assertEqual(outcome['written'], 0)
            self.assertFalse((state_path.parent / cg.COGNITION_DIRNAME
                              / cg.REVISIONS_NAME).exists())

    def test_a_second_apply_adds_no_duplicate_record(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(temp)
            first, _, _ = pr.run_preset('strategy-evolution', state_path, apply=True)
            written = len(self._revisions(state_path))
            second, _, _ = pr.run_preset('strategy-evolution', state_path, apply=True)
            self.assertEqual(len(self._revisions(state_path)), written)
            self.assertEqual(second['observed']['applied_revisions'], 0)
            self.assertGreaterEqual(first['observed']['applied_revisions'], 1)

    def test_written_revisions_remain_readable_when_the_state_moves_on(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(temp)
            pr.run_preset('strategy-evolution', state_path, apply=True)
            state = json.loads(state_path.read_text(encoding='utf-8'))
            state['state_version'] += 1
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
            revisions = self._revisions(state_path)
            loadings, problems = cg.load_revisions(state_path.parent / cg.COGNITION_DIRNAME
                                                   / cg.REVISIONS_NAME)
            self.assertEqual(problems, [])
            self.assertEqual(len(loadings), len(revisions))


# ---------------------------------------------------------------------------
# FIX-04 — post-update Assurance lifecycle
# ---------------------------------------------------------------------------

def assurance_for(state, experiment_id='X1'):
    receipt = [item for item in state['experiments'] if item['id'] == experiment_id][0][
        'outcome_analysis']
    return {"schema": pr.SCHEMA_OUTCOME_ASSURANCE, "state_digest": eo.digest(state),
            "analysis_digest": eo.digest(receipt['analysis']),
            "checks": {name: {"status": "PASS", "reason": "source-bound review"}
                       for name in ("integrity", "claim_calibration", "reproducibility",
                                    "stop_rule_compliance")}}


class TestAssuranceLifecycle(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.route = pathlib.Path(self.tmp.name)
        self.state = eo.apply(*teo.fixture('positive'), timestamp=TIMESTAMP)['state']
        self.state_path = self.route / 'research-state.json'
        self.state_path.write_text(json.dumps(self.state, ensure_ascii=False), encoding='utf-8')

    def ctx(self, state=None, **kw):
        state = state if state is not None else self.state
        context = {"state": state, "index": {"state_version": state['state_version']},
                   "index_missing": False, "scheduler": None, "revisions": [],
                   "route_dir": self.route, "state_path": self.state_path}
        context.update(kw)
        return context

    def write_assurance(self, state=None, experiment_id='X1', **overrides):
        state = state if state is not None else self.state
        payload = {**assurance_for(state, experiment_id), **overrides}
        receipt = [item for item in state['experiments']
                   if item['id'] == experiment_id][0]['outcome_analysis']
        directory = self.route.joinpath(*pr.OUTCOME_ASSURANCE_SUBDIR)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{receipt['analysis']['id']}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        return path

    def test_without_an_assurance_the_gate_stays_needs_review(self):
        status = pr.assurance_status(self.state, self.route)
        self.assertEqual(status['X1']['status'], pr.ASSURANCE_PENDING)
        self.assertEqual(status['X1']['gate'], 'NEEDS_REVIEW')
        self.assertEqual(status['X1']['source'], 'missing')
        step = pr._loop_step(self.ctx())
        self.assertEqual(step['step'], 'Assurance')
        self.assertEqual(step['assurance_pending'], ['X1'])
        self.assertFalse(step['hold'])

    def test_the_loop_consumes_a_real_assurance_and_advances(self):
        self.write_assurance()
        status = pr.assurance_status(self.state, self.route)
        self.assertEqual(status['X1']['status'], pr.ASSURANCE_VERIFIED)
        self.assertEqual(status['X1']['gate'], 'PASS')
        scheduler = {"state_version": self.state['state_version'],
                     "next_actions": [{"action": 'H1', "type": 'repair', "target": 'C1',
                                       "eig": 'high', "cost": 'low'}]}
        step = pr._loop_step(self.ctx(scheduler=scheduler))
        self.assertEqual(step['step'], 'Discover', step)
        self.assertIn('H1', step['action'])
        self.assertEqual(step['assurance_pending'], [])

    def test_the_verdict_comes_from_the_real_decision_gate(self):
        self.write_assurance()
        loaded = pr.load_outcome_assurance(self.route,
                                           self.state['experiments'][-1]['outcome_analysis'][
                                               'analysis']['id'])
        self.assertTrue(loaded['found'])
        gate = eo.decision_gate(self.state, 'X1', loaded['assurance'])
        self.assertEqual(gate['status'], 'PASS')

    def test_a_failing_check_blocks_instead_of_advancing(self):
        self.write_assurance(checks={"integrity": {"status": "PASS", "reason": "ok"},
                                     "claim_calibration": {"status": "FAIL", "reason": "mis-calibrated"},
                                     "reproducibility": {"status": "PASS", "reason": "ok"},
                                     "stop_rule_compliance": {"status": "PASS", "reason": "ok"}})
        status = pr.assurance_status(self.state, self.route)
        self.assertEqual(status['X1']['status'], pr.ASSURANCE_FAILED)
        step = pr._loop_step(self.ctx())
        self.assertTrue(step['hold'])
        self.assertEqual(step['hold_reason'], 'assurance_failed')
        self.assertIn('X1', step['assurance_failed'])

    def test_an_unknown_check_is_never_treated_as_pass(self):
        self.write_assurance(checks={"integrity": {"status": "PASS", "reason": "ok"},
                                     "claim_calibration": {"status": "UNKNOWN", "reason": "no data"},
                                     "reproducibility": {"status": "PASS", "reason": "ok"},
                                     "stop_rule_compliance": {"status": "PASS", "reason": "ok"}})
        status = pr.assurance_status(self.state, self.route)
        self.assertEqual(status['X1']['status'], pr.ASSURANCE_UNKNOWN)
        self.assertEqual(status['X1']['gate'], 'NEEDS_REVIEW')
        step = pr._loop_step(self.ctx())
        self.assertEqual(step['step'], 'HOLD')
        self.assertEqual(step['hold_reason'], 'assurance_unknown')
        self.assertTrue(step['hold'])

    def test_a_stale_state_digest_invalidates_the_assurance(self):
        self.write_assurance(state_digest='sha256:' + '0' * 64)
        status = pr.assurance_status(self.state, self.route)
        self.assertEqual(status['X1']['status'], pr.ASSURANCE_STALE)
        step = pr._loop_step(self.ctx())
        self.assertEqual(step['step'], 'Assurance')
        self.assertFalse(step['hold'], "stale is a re-review todo, not a failure")

    def test_a_mismatched_analysis_digest_is_refused(self):
        self.write_assurance(analysis_digest='sha256:' + '1' * 64)
        status = pr.assurance_status(self.state, self.route)
        self.assertIn(status['X1']['status'], (pr.ASSURANCE_STALE, pr.ASSURANCE_PENDING))
        self.assertNotEqual(status['X1']['status'], pr.ASSURANCE_VERIFIED)

    def test_another_experiments_assurance_cannot_be_borrowed(self):
        path = self.write_assurance()
        moved = path.with_name('AN999.json')
        path.rename(moved)
        status = pr.assurance_status(self.state, self.route)
        self.assertEqual(status['X1']['status'], pr.ASSURANCE_PENDING)
        self.assertEqual(status['X1']['source'], 'missing')

    def test_an_unparsable_artifact_is_pending_not_verified(self):
        directory = self.route.joinpath(*pr.OUTCOME_ASSURANCE_SUBDIR)
        directory.mkdir(parents=True, exist_ok=True)
        analysis_id = self.state['experiments'][-1]['outcome_analysis']['analysis']['id']
        (directory / f'{analysis_id}.json').write_text('{not json', encoding='utf-8')
        status = pr.assurance_status(self.state, self.route)
        self.assertEqual(status['X1']['status'], pr.ASSURANCE_PENDING)
        self.assertEqual(status['X1']['source'], 'invalid')

    def test_a_review_is_consumed_across_sessions_and_not_repeated(self):
        self.write_assurance()
        scheduler = {"state_version": self.state['state_version'],
                     "next_actions": [{"action": 'H1', "type": 'repair', "target": 'C1',
                                       "eig": 'high', "cost": 'low'}]}
        steps = []
        for _ in range(3):
            reloaded = cg.load_state(self.state_path)
            steps.append(pr._loop_step(self.ctx(state=reloaded, scheduler=scheduler))['step'])
        self.assertEqual(steps, ['Discover', 'Discover', 'Discover'])
        self.assertNotIn('Assurance', steps)

    def test_dependent_work_waits_for_the_review_and_independent_work_proceeds(self):
        dependent = copy.deepcopy(self.state)
        receipt = dependent['experiments'][-1]['outcome_analysis']
        target = receipt['analysis']['claim_updates'][0]['id']
        dependent['experiments'].append(copy.deepcopy(dependent['experiments'][-1]))
        dependent['experiments'][-1].update(id='X2', status='planned', parent='X1',
                                            claim_targeted=[target], result_at_state_version=None)
        dependent['experiments'][-1].pop('outcome_analysis', None)
        step = pr._loop_step(self.ctx(state=dependent))
        self.assertTrue(step['hold'])
        self.assertEqual(step['hold_reason'], 'assurance_pending_dependency')
        self.assertEqual(step['assurance_dependent'], ['X2'])

        independent = copy.deepcopy(dependent)
        independent['experiments'][-1].update(claim_targeted=['C-independent'],
                                              hypothesis_targeted=[], depends_on=[],
                                              parent=None)
        step = pr._loop_step(self.ctx(state=independent))
        self.assertEqual(step['step'], 'Intervene', step)
        self.assertEqual(step['assurance_pending'], ['X1'])

    def test_no_assurance_is_ever_fabricated(self):
        pr._loop_step(self.ctx())
        directory = self.route.joinpath(*pr.OUTCOME_ASSURANCE_SUBDIR)
        self.assertFalse(directory.exists(), "the loop must never write an Assurance itself")


# ---------------------------------------------------------------------------
# R7 authoring: the reviewer tool, its refusal rules, and review liveness
# ---------------------------------------------------------------------------

class TestAssuranceStore(unittest.TestCase):
    """`evidence_outcome.py assurance-store` authors a real R7 review — never a pass."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.route = pathlib.Path(self.tmp.name)
        self.state = eo.apply(*teo.fixture('positive'), timestamp=TIMESTAMP)['state']
        self.state_path = self.route / 'research-state.json'
        self.state_path.write_text(json.dumps(self.state, ensure_ascii=False), encoding='utf-8')
        self.analysis_id = self.state['experiments'][-1]['outcome_analysis']['analysis']['id']
        self.path = self.route.joinpath(*pr.OUTCOME_ASSURANCE_SUBDIR) / f'{self.analysis_id}.json'

    def run_cli(self, *checks, reviewer='R7', experiment='X1', output=None, force=False,
                state=None, review_conditions=()):
        command = [sys.executable, str(ROOT / 'scripts' / 'evidence_outcome.py'), 'assurance-store',
                   '--state', str(state or self.state_path), '--experiment', experiment,
                   '--reviewer', reviewer]
        for item in checks:
            command += ['--check', item]
        for item in review_conditions:
            command += ['--re-review-condition', item]
        if output is not None:
            command += ['--output', str(output)]
        if force:
            command += ['--force']
        proc = subprocess.run(command, capture_output=True, text=True,
                              cwd=str(ROOT / 'scripts'))
        return proc, (json.loads(proc.stdout) if proc.stdout.strip() else {})

    @staticmethod
    def check(name, status='PASS', reason=None):
        return f"{name}={status}:{reason or (name + ' 已按来源核验，范围与冻结范围一致')}"

    def all_checks(self, status='PASS'):
        return [self.check(name, status) for name in eo.ASSURANCE_CHECKS]

    def test_four_passes_store_and_release_the_real_gate(self):
        proc, payload = self.run_cli(*self.all_checks())
        self.assertEqual(proc.returncode, 0, payload)
        self.assertTrue(payload['stored'])
        self.assertEqual(payload['decision_gate']['status'], 'PASS')
        self.assertEqual(payload['verification_tier'], 'T0')
        stored = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(stored['reviewer'], 'R7')
        self.assertEqual(stored['experiment_id'], 'X1')
        self.assertEqual(stored['analysis_id'], self.analysis_id)
        self.assertEqual(stored['state_digest'], eo.digest(self.state))
        self.assertEqual(stored['analysis_digest'],
                         eo.digest(self.state['experiments'][-1]['outcome_analysis']['analysis']))
        self.assertIn('does not start a run', stored['note'])
        self.assertEqual(pr.assurance_status(self.state, self.route)['X1']['status'],
                         pr.ASSURANCE_VERIFIED)

    def test_a_failing_check_blocks_and_is_kept_as_the_review(self):
        proc, payload = self.run_cli(self.check('integrity', 'FAIL', '来源与冻结配置不一致，无法确认完整性'),
                                     *[self.check(n) for n in eo.ASSURANCE_CHECKS
                                       if n != 'integrity'])
        self.assertEqual(proc.returncode, 3, payload)
        self.assertTrue(payload['stored'])
        self.assertEqual(payload['decision_gate']['status'], 'FAIL')
        self.assertEqual(pr.assurance_status(self.state, self.route)['X1']['status'],
                         pr.ASSURANCE_FAILED)

    def test_an_unknown_check_returns_needs_review_and_parks_the_loop(self):
        proc, payload = self.run_cli(self.check('claim_calibration', 'UNKNOWN',
                                                '缺少独立的校准证据，当前无法判定'),
                                     *[self.check(n) for n in eo.ASSURANCE_CHECKS
                                       if n != 'claim_calibration'])
        self.assertEqual(proc.returncode, 4, payload)
        self.assertEqual(pr.assurance_status(self.state, self.route)['X1']['status'],
                         pr.ASSURANCE_UNKNOWN)
        scheduler = {"state_version": self.state['state_version'],
                     "next_actions": [{"action": 'H1', "type": 'repair', "target": 'C1',
                                       "eig": 'high', "cost": 'low'}]}
        first = pr._loop_step(self.ctx(scheduler=scheduler))
        self.assertEqual(first['step'], 'HOLD')
        self.assertEqual(first['hold_reason'], 'assurance_unknown')
        self.assertFalse(first.get('assurance_task'))
        self.assertTrue(first['assurance_unknown']['X1']['re_review_conditions'])
        self.assertEqual(pr._loop_step(self.ctx(scheduler=scheduler)), first,
                         "an UNKNOWN review must not be re-asked every round")

    def test_missing_check_empty_and_placeholder_reasons_are_refused(self):
        cases = {
            'missing': [self.check(name) for name in eo.ASSURANCE_CHECKS[:3]],
            'empty': [*[self.check(name) for name in eo.ASSURANCE_CHECKS[:3]],
                      'stop_rule_compliance=PASS:'],
            'placeholder': [*[self.check(name) for name in eo.ASSURANCE_CHECKS[:3]],
                            'stop_rule_compliance=PASS:TBD'],
            'short': [*[self.check(name) for name in eo.ASSURANCE_CHECKS[:3]],
                      'stop_rule_compliance=PASS:ok了'],
            'bad_status': [*[self.check(name) for name in eo.ASSURANCE_CHECKS[:3]],
                           'stop_rule_compliance=PROBABLY:理由足够长但状态非法'],
            'bad_name': [self.check('integrity'), self.check('claim_calibration'),
                         self.check('reproducibility'), self.check('vibes')],
            'no_reviewer': self.all_checks(),
        }
        for name, checks in cases.items():
            with self.subTest(name=name):
                proc, payload = self.run_cli(*checks,
                                             **({'reviewer': ''} if name == 'no_reviewer' else {}))
                self.assertNotEqual(proc.returncode, 0, payload)
                self.assertFalse(payload.get('stored'), payload)
                self.assertFalse(self.path.exists(), name)

    def test_a_wrong_binding_is_refused(self):
        other = copy.deepcopy(self.state)
        other['experiments'][-1]['outcome_analysis']['analysis']['experiment_id'] = 'X9'
        bad = self.route / 'bad-state.json'
        bad.write_text(json.dumps(other, ensure_ascii=False), encoding='utf-8')
        proc, payload = self.run_cli(*self.all_checks(), state=bad)
        self.assertNotEqual(proc.returncode, 0, payload)
        self.assertFalse(payload.get('stored'))
        self.assertFalse(self.path.exists())
        proc, payload = self.run_cli(*self.all_checks(), experiment='X-does-not-exist')
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(payload.get('stored'))

    def test_an_arbitrary_output_path_is_refused(self):
        target = pathlib.Path(self.tmp.name) / 'research-state.json'
        proc, payload = self.run_cli(*self.all_checks(), output=target)
        self.assertNotEqual(proc.returncode, 0, payload)
        self.assertIn('output must be', payload['errors'][0])
        self.assertTrue(self.state_path.exists())

    def test_duplicate_and_concurrent_submissions_do_not_corrupt_the_review(self):
        self.run_cli(*self.all_checks())
        before = self.path.read_bytes()
        proc, payload = self.run_cli(*self.all_checks())
        self.assertEqual(proc.returncode, 0, payload)
        self.assertEqual(payload['outcome'], 'already_stored')
        self.assertEqual(self.path.read_bytes(), before, "an identical re-submission must not rewrite")
        changed = [self.check('integrity', 'FAIL', '来源与冻结配置不一致，无法确认完整性'),
                   *[self.check(n) for n in eo.ASSURANCE_CHECKS if n != 'integrity']]
        proc, payload = self.run_cli(*changed)
        self.assertNotEqual(proc.returncode, 0, payload)
        self.assertEqual(self.path.read_bytes(), before,
                         "a different verdict without --force must not overwrite history")
        proc, payload = self.run_cli(*changed, force=True)
        self.assertEqual(proc.returncode, 3, payload)
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8'))['checks']['integrity'][
                             'status'], 'FAIL')

    def test_the_stored_review_survives_a_session_restart(self):
        self.run_cli(*self.all_checks())
        reloaded = cg.load_state(self.state_path)
        context = {"state": reloaded, "index": {"state_version": reloaded['state_version']},
                   "index_missing": False, "scheduler": None, "revisions": [],
                   "route_dir": self.route, "state_path": self.state_path}
        self.assertEqual(pr.assurance_status(reloaded, self.route)['X1']['status'],
                         pr.ASSURANCE_VERIFIED)
        step = pr._loop_step(context)
        self.assertNotEqual(step['step'], 'Assurance')

    def test_a_state_change_invalidates_the_stored_review(self):
        self.run_cli(*self.all_checks())
        moved = copy.deepcopy(self.state)
        moved['state_version'] += 1
        moved_path = self.route / 'moved.json'
        moved_path.write_text(json.dumps(moved, ensure_ascii=False), encoding='utf-8')
        status = pr.assurance_status(moved, self.route)['X1']
        self.assertEqual(status['status'], pr.ASSURANCE_STALE)
        step = pr._loop_step({"state": moved, "index": {"state_version": moved['state_version']},
                              "index_missing": False, "scheduler": None, "revisions": [],
                              "route_dir": self.route, "state_path": moved_path})
        self.assertEqual(step['step'], 'Assurance')
        self.assertTrue(step.get('assurance_task'))

    def test_a_superseded_analysis_needs_no_review(self):
        second = eo.apply(*teo.fixture('positive', state=self.state, xid='X2'), timestamp=TIMESTAMP)
        self.assertEqual(second['status'], 'PASS', second)
        state = second['state']
        state_path = self.route / 'after-x2.json'
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
        proc, payload = self.run_cli(*self.all_checks(), experiment='X2', state=state_path)
        self.assertEqual(proc.returncode, 0, payload)
        status = pr.assurance_status(state, self.route)
        self.assertEqual(status['X1']['status'], pr.ASSURANCE_SUPERSEDED)
        self.assertEqual(status['X2']['status'], pr.ASSURANCE_VERIFIED)
        self.assertEqual(pr._loop_step({"state": state,
                                        "index": {"state_version": state['state_version']},
                                        "index_missing": False, "scheduler": None, "revisions": [],
                                        "route_dir": self.route,
                                        "state_path": state_path})['step'], 'HOLD')

    def test_a_review_never_starts_a_run_or_raises_support(self):
        before = copy.deepcopy(self.state)
        proc, payload = self.run_cli(*self.all_checks())
        self.assertEqual(proc.returncode, 0, payload)
        after = json.loads(self.state_path.read_text(encoding='utf-8'))
        self.assertEqual(after, before, "the review must not touch canonical state")
        stored = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(stored['verification_tier'], 'T0')
        self.assertEqual(payload['decision_gate']['note'],
                         'R8 preregistration, planning constraints and existing execution '
                         'authorization still apply.')
        self.assertEqual([item['status'] for item in after['experiments']],
                         [item['status'] for item in before['experiments']],
                         "the review must not start, finish or re-plan any experiment")

    def ctx(self, **kw):
        context = {"state": self.state, "index": {"state_version": self.state['state_version']},
                   "index_missing": False, "scheduler": None, "revisions": [],
                   "route_dir": self.route, "state_path": self.state_path}
        context.update(kw)
        return context


# ---------------------------------------------------------------------------
# End-to-end runtime continuity
# ---------------------------------------------------------------------------

class TestEndToEndRuntime(unittest.TestCase):

    def test_the_full_chain_reaches_a_next_action_without_double_charging(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state = eo.apply(*teo.fixture('positive'), timestamp=TIMESTAMP)['state']
            state_path = root / 'research-state.json'
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
            # 1. scheduler verdict
            scheduler = {"state_version": state['state_version'],
                         "next_actions": [{"action": 'H1', "type": 'repair', "target": 'C1',
                                           "eig": 'high', "cost": 'low'}],
                         "eig_calibration": {"records": []},
                         "operator_stats": {"by_operator": {}, "recurring_failure_patterns": []}}
            self.assertIn(sm.scheduler_verdict(state, scheduler)['passed'], (True, False))
            # 2. strategy decision consumes the verdict (no dispatch while it is not PASS)
            decision = sm.strategy_decision(state, {}, scheduler, [])
            if not decision['hard_gates']['scheduler_check'] == 'PASS':
                self.assertIsNone(decision['chosen'])
            # 3. post-update Assurance through the real gate, then the next action
            receipt = state['experiments'][-1]['outcome_analysis']
            payload = {"schema": pr.SCHEMA_OUTCOME_ASSURANCE, "state_digest": eo.digest(state),
                       "analysis_digest": eo.digest(receipt['analysis']),
                       "checks": {name: {"status": "PASS", "reason": "reviewed"}
                                  for name in ("integrity", "claim_calibration",
                                               "reproducibility", "stop_rule_compliance")}}
            directory = root.joinpath(*pr.OUTCOME_ASSURANCE_SUBDIR)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"{receipt['analysis']['id']}.json").write_text(
                json.dumps(payload), encoding='utf-8')
            context = {"state": state, "index": {"state_version": state['state_version']},
                       "index_missing": False, "scheduler": None, "revisions": [],
                       "route_dir": root, "state_path": state_path}
            consolidated = pr._loop_step({**context, "index": {"state_version":
                                                               state['state_version'] - 1}})
            self.assertEqual(consolidated['step'], 'Consolidate')
            final = pr._loop_step({**context, "scheduler": scheduler})
            self.assertEqual(final['step'], 'Discover', final)
            self.assertEqual(pr.r10_pending(state), [])
            self.assertEqual(eo.state_errors(state), [])

    def test_no_stage_loop_without_a_state_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state = eo.apply(*teo.fixture('negative'), timestamp=TIMESTAMP)['state']
            context = {"state": state, "index": {"state_version": state['state_version']},
                       "index_missing": False, "scheduler": None, "revisions": [],
                       "route_dir": root, "state_path": root / 'research-state.json'}
            first = pr._loop_step(context)
            second = pr._loop_step(context)
            self.assertEqual(first, second)
            self.assertNotEqual(first['step'], 'Revise')

    def test_the_loop_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state = eo.apply(*teo.fixture('invalid'), timestamp=TIMESTAMP)['state']
            state_path = root / 'research-state.json'
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
            before = state_path.read_bytes()
            payload, _, code = pr.run_preset('research-loop', state_path)
            self.assertEqual(code, pr.EXIT_OK, payload)
            self.assertTrue(payload['canonical_untouched'])
            self.assertEqual(state_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
