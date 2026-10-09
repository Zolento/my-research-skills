#!/usr/bin/env python3
"""Managed execution permission/dispatch. Default run is dry; --execute is explicit.

Route-local receipts are integrity controls, not an adversarial security boundary.
No shell is used. Remote/detaching jobs require an external scheduler adapter.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import subprocess
import time

import evidence_outcome as eo
import execution_gate as eg
import state_check as sc


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as f: f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


class Ledger:
    """A locked, authenticated append-only event chain; no scientific state writes."""
    def __init__(self, directory, policy=None):
        self.directory = Path(directory)
        self.requested_policy = policy

    @contextmanager
    def locked(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / 'lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            keypath, events = self.directory / 'key', self.directory / 'events.jsonl'
            created = not keypath.exists()
            if created:
                if events.exists(): raise ValueError('LEDGER_KEY_MISSING: do not reset history')
                fd = os.open(keypath, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'wb') as out: out.write(secrets.token_bytes(32))
                events.touch(exist_ok=False)
            elif not events.exists(): raise ValueError('LEDGER_HISTORY_MISSING: do not reset counters')
            self.key = keypath.read_bytes(); self.events = []
            for line in events.read_text(encoding='utf-8').splitlines():
                event = json.loads(line); seal = event.pop('seal')
                if not hmac.compare_digest(seal, self.seal(event)) or event['previous'] != (eo.digest(self.events[-1]) if self.events else None): raise ValueError('LEDGER_TAMPERED')
                event['seal'] = seal; self.events.append(event)
            head = self.directory / 'head'
            if not created and (not self.events or not head.exists() or head.read_text().strip() != eo.digest(self.events[-1])): raise ValueError('LEDGER_TRUNCATED_OR_INCOMPLETE')
            if not self.events:
                policy = self.requested_policy or eg.DEFAULT_POLICY
                if set(policy) != set(eg.DEFAULT_POLICY) or any(type(v) not in (int,float) or v <= 0 for v in policy.values()) or any(type(policy[k]) is not int for k in ('max_preflight_revisions','max_equivalent_diagnostics','max_pilot_runs','receipt_ttl_seconds')):
                    raise ValueError('INVALID_EXECUTION_POLICY')
                self.append({'kind': 'policy', 'policy': policy})
            self.policy = self.events[0]['policy']
            if self.requested_policy is not None and self.policy != self.requested_policy: raise ValueError('FROZEN_POLICY: cannot reset budgets through config')
            yield self

    def seal(self, value):
        return hmac.new(self.key, eo.digest(value).encode('ascii'), hashlib.sha256).hexdigest()

    def append(self, event):
        event = dict(event, previous=eo.digest(self.events[-1]) if self.events else None)
        event['seal'] = self.seal(event)
        with (self.directory / 'events.jsonl').open('a', encoding='utf-8') as out:
            out.write(json.dumps(event, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n'); out.flush(); os.fsync(out.fileno())
        self.events.append(event)
        pending = self.directory / '.head.pending'
        with pending.open('w',encoding='ascii') as out:
            out.write(eo.digest(event)); out.flush(); os.fsync(out.fileno())
        os.replace(pending,self.directory/'head')
        return event


def config_binding(protocol):
    return {k: protocol[k] for k in ('arms', 'intervention', 'evaluation')}


def manifest_binding(state, experiment, manifest):
    errors = eg.schema_errors(manifest, 'execution-manifest.schema.json')
    if errors: raise ValueError('INVALID_MANIFEST: ' + '; '.join(errors))
    cwd = Path(manifest['cwd']).resolve()
    if not cwd.is_dir(): raise ValueError('EXECUTION_CWD_MISSING')
    bindings = []; kinds = set(); paths = set()
    for item in manifest['files']:
        path = Path(item['path']); path = path if path.is_absolute() else cwd / path
        path = path.resolve(); data = path.read_bytes()
        if str(path) in paths: raise ValueError('DUPLICATE_MANIFEST_FILE')
        paths.add(str(path)); kinds.add(item['kind'])
        bindings.append({'kind': item['kind'], 'path': str(path), 'sha256': hashlib.sha256(data).hexdigest()})
        if item['kind'] == 'config' and json.loads(data).get('execution_design') != config_binding(experiment['execution_protocol']): raise ValueError('CONFIG_PROTOCOL_MISMATCH')
        if item['kind'] == 'data_split' and json.loads(data).get('data_split') != experiment['data_split']: raise ValueError('SPLIT_PROTOCOL_MISMATCH')
        if item['kind'] == 'preregistration' and json.loads(data) != experiment['preregistration']: raise ValueError('PREREGISTRATION_FILE_MISMATCH')
    if kinds != {'code','config','data_split','preregistration'}: raise ValueError('MISSING_CONTENT_BINDING')
    mask = ','.join(manifest['gpu_devices'])
    if any(',' in d for d in manifest['gpu_devices']) or manifest['env'].get('CUDA_VISIBLE_DEVICES',mask) != mask: raise ValueError('GPU_MASK_MISMATCH')
    argv = manifest['argv']
    executable = Path(argv[0]); local = executable if executable.is_absolute() else cwd / executable
    if local.is_file() and str(local.resolve()) not in paths: raise ValueError('UNBOUND_EXECUTABLE')
    for arg in argv[1:]:
        local = cwd / arg
        if local.is_file() and str(local.resolve()) not in paths: raise ValueError('UNBOUND_COMMAND_FILE: ' + arg)
    engine = {str(path.relative_to(eg.ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((eg.ROOT/'schemas').glob('*.json'))}
    for name in ('execution_gate.py','experiment_execute.py','evidence_outcome.py','state_check.py'):
        engine['scripts/'+name] = hashlib.sha256((eg.ROOT/'scripts'/name).read_bytes()).hexdigest()
    return {'state_digest': eo.digest(state), 'experiment_id': experiment['id'],
            'experiment_design': {k: experiment.get(k) for k in ('stage','claim_targeted','hypothesis_targeted','alternative_targeted','code_commit','data_split','seed','metric','outcome_protocol')},
            'protocol_digest': eo.digest(experiment['execution_protocol']),
            'preregistration_digest': eo.digest(experiment['preregistration']),
            'manifest_digest': eo.digest(manifest), 'files': bindings, 'engine': engine}


def execution_review_digest(state, experiment, manifest):
    binding = manifest_binding(state,experiment,manifest)
    targets = set(eg.target_lineage(state,experiment['claim_targeted'] + experiment.get('hypothesis_targeted',[]) + experiment.get('alternative_targeted',[])))
    scientific_targets = {collection:sorted([obj for obj in state[collection] if obj['id'] in targets],key=lambda obj:obj['id']) for collection in ('claims','hypotheses')}
    return eo.digest({'design':eg.review_digest(experiment['execution_protocol']),
                      'experiment_design':binding['experiment_design'],
                      'scientific_targets':scientific_targets,
                      'preregistration':experiment['preregistration'],
                      'manifest':manifest,'files':binding['files']})


def diagnose(state, diagnostic, ledger):
    if not sc.check_state(state).ok: return {'status': 'HOLD', 'errors': ['STATE_INVALID']}
    with ledger.locked():
        result = eg.diagnostic_check(state, diagnostic, ledger.events, ledger.policy)
        ledger.append({'kind':'diagnosis','key':result.get('key'), 'state_digest':eo.digest(state),
                       'diagnostic_digest':eg.diagnostic_digest(diagnostic,state), 'result':result})
        return result


def diagnostic_for(state, x, ledger):
    lineage = set(eg.target_lineage(state,x['claim_targeted']))
    targeted = [r for r in state.get('repairs', []) if set(eg.target_lineage(state,r.get('targets', []))) & lineage and r.get('disposition') in ('RUN_TEST','NARROW_SCOPE','FIX_IMPLEMENTATION')]
    prior_negative = any(old.get('outcome_analysis') and old['outcome_analysis']['analysis']['outcome'] != 'POSITIVE_EVIDENCE' and set(eg.target_lineage(state,old['claim_targeted'])) & lineage for old in state['experiments'])
    diagnoses = [r['diagnostic_protocol'] for r in targeted if r.get('diagnostic_protocol') and r['diagnostic_protocol']['experiment_id'] == x['id']]
    if not targeted and not prior_negative: return None, []
    if len(diagnoses) != 1: return None, ['AALG_REQUIRED: register one decision-bearing diagnosis in the R10 repair']
    d = diagnoses[0]; dg = eg.diagnostic_digest(d,state)
    used = {event.get('diagnosis_seal') for event in ledger.events if event.get('kind') == 'issue'}
    matches = [event for event in ledger.events if event.get('kind') == 'diagnosis' and event.get('diagnostic_digest') == dg and event.get('state_digest') == eo.digest(state) and event['result']['status'] == 'PASS' and event['seal'] not in used]
    if not matches: return None, ['AALG_REQUIRED: bounded diagnosis authorization missing or already used']
    if any(event.get('kind') == 'diagnosis' and event.get('key') == matches[-1]['key'] and event['result']['status'] == 'STOP_DIAGNOSIS' for event in ledger.events): return None, ['STOP_DIAGNOSIS: finite REDESIGN/T8 required']
    return matches[-1]['seal'], []


def issue(state, experiment_id, manifest, ledger, now=None, scheduler=None):
    now = time.time() if now is None else now
    x = eo.index(state, 'experiments')[experiment_id]
    family = eg.family_key(state, x)
    with ledger.locked():
        gate_kind = 'formal' if (x.get('execution_protocol') or {}).get('mode') == 'formal' else 'diagnostic'
        holds = sum(e.get('kind') == 'preflight' and e.get('family') == family and e.get('gate_kind') == gate_kind and e['result']['status'] == 'HOLD' for e in ledger.events)
        gate = eg.peig(state, experiment_id)
        if holds >= ledger.policy['max_preflight_revisions']:
            gate = {'status': 'HOLD', 'errors': ['PREFLIGHT_REVISION_LIMIT: finite REDESIGN; no automatic card/document loop'], 'decision': 'REDESIGN'}
        if not sc.check_state(state).ok: gate = {'status':'HOLD','errors':gate.get('errors', []) + ['STATE_INVALID']}
        scheduling = eg.scheduler_check(state,scheduler or {})
        if scheduling['status'] != 'PASS': gate = {'status':'HOLD','errors':gate.get('errors',[]) + ['SCHEDULER_GATE: ' + '; '.join(scheduling['errors'])]}
        if x['status'] != 'planned' or x.get('result') or x.get('result_at_state_version') is not None: gate = {'status':'HOLD','errors':['POST_EXECUTION_PREREGISTRATION: planned, result-free execution required']}
        diagnosis_seal, diagnostics = diagnostic_for(state, x, ledger)
        if diagnostics: gate = {'status':'HOLD','errors':gate.get('errors', []) + diagnostics}
        if gate['status'] != 'HOLD':
            budget = gate['budget_hours']; requested = manifest.get('requested_hours', 0)
            if type(requested) not in (float,int) or not 0 < requested <= budget: gate = {'status':'HOLD','errors':['REQUESTED_BUDGET_EXCEEDS_PROTOCOL']}
            spent = [e for e in ledger.events if e.get('kind') == 'consume' and e.get('family') == family]
            if gate['status'] == 'PILOT_ONLY':
                limits = x['execution_protocol']['pilot']
                pilots = [e for e in spent if e['permission'] == 'PILOT_ONLY']
                if len(pilots) >= min(limits['max_runs'], ledger.policy['max_pilot_runs']) or sum(e['hours'] for e in pilots) + requested > min(limits['max_hours'],ledger.policy['max_pilot_hours']): gate = {'status':'HOLD','errors':['PILOT_BUDGET_EXHAUSTED']}
            elif gate['status'] == 'PASS':
                formal = [e for e in spent if e['permission'] == 'PASS']
                prior_limits = [e['budget_hours'] for e in ledger.events if e.get('kind') == 'issue' and e.get('family') == family and e['receipt']['permission'] == 'PASS']
                cap = min([budget] + prior_limits)
                if any(e['experiment_id'] == experiment_id for e in spent) or sum(e['hours'] for e in formal) + requested > cap: gate = {'status':'HOLD','errors':['FORMAL_BUDGET_EXHAUSTED']}
        binding = None
        if gate['status'] != 'HOLD':
            try:
                binding = manifest_binding(state, x, manifest)
                if x['execution_protocol']['scientific_review']['execution_digest'] != execution_review_digest(state,x,manifest): raise ValueError('EXECUTION_REVIEW_MISMATCH: review the actual argv and file contents')
            except (OSError, ValueError, TypeError) as exc: gate = {'status':'HOLD','errors':[str(exc)]}
        ledger.append({'kind':'preflight','family':family,'mode':(x.get('execution_protocol') or {}).get('mode'),'gate_kind':gate_kind,'result':gate})
        if gate['status'] == 'HOLD': return gate
        exception = x['execution_protocol'].get('human_exception')
        if exception and (exception['expires_at'] <= now or manifest['requested_hours'] > exception['max_hours'] or exception['scope'] not in (x['data_split'], x['execution_protocol']['pilot']['goal'])):
            return {'status':'HOLD','errors':['EXPIRED_OR_OUT_OF_SCOPE_HUMAN_EXCEPTION']}
        receipt = {'schema':'execution-receipt@1', 'id':secrets.token_hex(16), 'binding':binding,
                   'issued_at':now, 'expires_at':now + ledger.policy['receipt_ttl_seconds'],
                   'permission':gate['status'],'family':family, 'requested_hours':manifest['requested_hours'],
                   'peig':gate, 'human_exception':exception, 'scheduler_digest':eo.digest(scheduler)}
        receipt['seal'] = ledger.seal(receipt)
        ledger.append({'kind':'issue','family':family,'receipt':receipt,'budget_hours':gate['budget_hours'],'diagnosis_seal':diagnosis_seal})
        return {'status':gate['status'], 'errors':[], 'receipt':receipt}


def run(state, experiment_id, manifest, receipt, ledger, execute=False, now=None, scheduler=None):
    now = time.time() if now is None else now
    with ledger.locked():
        value = dict(receipt); seal = value.pop('seal', '')
        if not isinstance(seal, str) or not hmac.compare_digest(seal, ledger.seal(value)): return {'status':'HOLD','errors':['FORGED_RECEIPT']}
        registered = any(e.get('kind') == 'issue' and e['receipt'] == receipt for e in ledger.events)
        # A preview never consumes; historical ledgers may still carry `dry_run: true` consume
        # events from before the preview semantics were fixed, and those must not block the one
        # legitimate execution either (the ledger itself is never rewritten or reset).
        consumed = any(e.get('kind') == 'consume' and e['receipt_id'] == receipt['id']
                       and e.get('dry_run') is not True for e in ledger.events)
        if not registered or consumed: return {'status':'HOLD','errors':['UNKNOWN_OR_USED_RECEIPT']}
        if now < receipt['issued_at'] or now >= receipt['expires_at']: return {'status':'HOLD','errors':['EXPIRED_RECEIPT']}
        if eo.digest(scheduler) != receipt['scheduler_digest'] or eg.scheduler_check(state,scheduler or {})['status'] != 'PASS': return {'status':'HOLD','errors':['SCHEDULER_RECEIPT_MISMATCH']}
        failed = sum(e.get('kind') == 'preflight' and e.get('family') == receipt['family'] and e.get('gate_kind') == ('formal' if receipt['permission'] == 'PASS' else 'diagnostic') and e['result']['status'] == 'HOLD' for e in ledger.events)
        if failed >= ledger.policy['max_preflight_revisions']: return {'status':'HOLD','errors':['PREFLIGHT_REVISION_LIMIT']}
        issue_event = next(e for e in ledger.events if e.get('kind') == 'issue' and e['receipt'] == receipt)
        if issue_event.get('diagnosis_seal'):
            diagnosis_event = next(e for e in ledger.events if e['seal'] == issue_event['diagnosis_seal'])
            if any(e.get('kind') == 'diagnosis' and e.get('key') == diagnosis_event['key'] and e['result']['status'] == 'STOP_DIAGNOSIS' for e in ledger.events): return {'status':'HOLD','errors':['STOP_DIAGNOSIS']}
        x = eo.index(state,'experiments')[experiment_id]
        try: binding = manifest_binding(state, x, manifest)
        except (OSError, ValueError, TypeError) as exc: return {'status':'HOLD','errors':[str(exc)]}
        if binding != receipt['binding']: return {'status':'HOLD','errors':['RECEIPT_CONTENT_MISMATCH']}
        gate = eg.peig(state, experiment_id)
        if not sc.check_state(state).ok or x['status'] != 'planned' or gate['status'] != receipt['permission']: return {'status':'HOLD','errors':['GATE_CHANGED']}
        # Recheck reservations under the same lock: issued receipts do not reserve yet.
        spent = [e for e in ledger.events if e.get('kind') == 'consume'
                 and e.get('dry_run') is not True
                 and e.get('family') == receipt['family'] and e['permission'] == receipt['permission']]
        p = x['execution_protocol']; hours = receipt['requested_hours']
        if receipt['permission'] == 'PILOT_ONLY':
            if len(spent) >= min(p['pilot']['max_runs'],ledger.policy['max_pilot_runs']) or sum(e['hours'] for e in spent) + hours > min(p['pilot']['max_hours'],ledger.policy['max_pilot_hours']): return {'status':'HOLD','errors':['PILOT_BUDGET_EXHAUSTED']}
        else:
            caps = [e['budget_hours'] for e in ledger.events if e.get('kind') == 'issue' and e.get('family') == receipt['family'] and e['receipt']['permission'] == 'PASS']
            if any(e['experiment_id'] == experiment_id for e in spent) or sum(e['hours'] for e in spent) + hours > min(caps): return {'status':'HOLD','errors':['FORMAL_BUDGET_EXHAUSTED']}
        if receipt['human_exception'] and now >= receipt['human_exception']['expires_at']: return {'status':'HOLD','errors':['EXPIRED_HUMAN_EXCEPTION']}
        if not execute:
            # Preview: every gate above has been re-checked under the lock, and nothing is
            # consumed. The receipt stays valid for exactly one real execution, so a preview can
            # never burn GPU hours, pilot runs or the single-use receipt.
            return {'status':'PASS','errors':[],'dry_run':True,'preview':True,'consumed':False,
                    'command_started':False,'receipt_id':receipt['id'],
                    'execution_record':{'receipt':receipt,'launch_seal':None,'dry_run':True},
                    'would_execute':{'argv':list(manifest['argv']),'cwd':manifest['cwd'],
                                     'gpu_devices':list(manifest['gpu_devices']),
                                     'requested_hours':hours,'permission':receipt['permission'],
                                     'family':receipt['family']},
                    'budget':{'spent_runs':len(spent),'spent_hours':sum(e['hours'] for e in spent)}}
        # Real execution consumes atomically before the external command can start (no double launch).
        consumption = ledger.append({'kind':'consume','family':receipt['family'],'receipt_id':receipt['id'], 'experiment_id':experiment_id,
                       'permission':receipt['permission'],'hours':hours,'dry_run':False,'timestamp':now})
    execution_record = {'receipt':receipt, 'launch_seal':consumption['seal'], 'dry_run':False}
    # Invoke only after atomic consumption. No retries or implicit detached jobs.
    try:
        log_path = ledger.directory / ('run-' + receipt['id'] + '.log')
        environment = dict(os.environ); environment.update(manifest['env']); environment['CUDA_VISIBLE_DEVICES']=','.join(manifest['gpu_devices'])
        with log_path.open('x',encoding='utf-8') as log:
            completed = subprocess.run(manifest['argv'], cwd=manifest['cwd'], env=environment, timeout=hours*3600/len(manifest['gpu_devices']), stdout=log, stderr=subprocess.STDOUT, check=False)
        return {'status':'PASS' if completed.returncode == 0 else 'FAIL','errors':[] if completed.returncode == 0 else ['EXECUTION_FAILED'],'returncode':completed.returncode,'log_path':str(log_path),'receipt_id':receipt['id'], 'execution_record':execution_record}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'status':'FAIL','errors':['EXECUTION_FAILED: '+str(exc)],'receipt_id':receipt['id'], 'execution_record':execution_record}


def verify_result_execution(state, ledger):
    errors = []
    with ledger.locked():
        for x in state['experiments']:
            if not x.get('execution_protocol') or x['status'] == 'planned': continue
            record = x.get('execution_record')
            if not isinstance(record,dict) or set(record) != {'receipt','launch_seal','dry_run'} or not isinstance(record['receipt'],dict) or not record['receipt'].get('id'):
                errors.append(x['id'] + ': missing execution record'); continue
            receipt = record['receipt']
            issued = any(e.get('kind') == 'issue' and e['receipt'] == receipt for e in ledger.events)
            consumed = any(e.get('kind') == 'consume' and e['receipt_id'] == receipt['id'] and e['seal'] == record['launch_seal'] and e['experiment_id'] == x['id'] and e['dry_run'] is False for e in ledger.events)
            if not issued or not consumed or record['dry_run'] is not False: errors.append(x['id'] + ': unexecuted or forged execution provenance')
    return errors


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    for command in ('issue','run','diagnose','scheduler-check'):
        p=sub.add_parser(command);p.add_argument('--state',type=Path,required=True)
        if command in ('issue','run'): p.add_argument('--experiment',required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--scheduler',type=Path,required=True)
        if command in ('issue','run','diagnose'): p.add_argument('--ledger',type=Path);p.add_argument('--policy',type=Path)
        if command == 'issue': p.add_argument('--output',type=Path,required=True)
        if command == 'run': p.add_argument('--receipt',type=Path,required=True);p.add_argument('--execute',action='store_true')
        if command == 'diagnose': p.add_argument('--diagnostic',type=Path,required=True)
        if command == 'scheduler-check': p.add_argument('--scheduler',type=Path,required=True)
    args=parser.parse_args(argv)
    def read(path): return json.loads(path.read_text(encoding='utf-8'))
    try:
        state=read(args.state)
        if args.command == 'scheduler-check': result=eg.scheduler_check(state,read(args.scheduler))
        else:
            ledger=Ledger(args.ledger or args.state.parent/'.execution',read(args.policy) if args.policy else None)
            if args.command == 'diagnose': result=diagnose(state,read(args.diagnostic),ledger)
            elif args.command == 'issue':
                if args.output.exists(): raise ValueError('Receipt output exists; choose a new path')
                result=issue(state,args.experiment,read(args.manifest),ledger,scheduler=read(args.scheduler))
                if 'receipt' in result: write_new(args.output,result.pop('receipt'));result['receipt_path']=str(args.output)
            else: result=run(state,args.experiment,read(args.manifest),read(args.receipt),ledger,args.execute,scheduler=read(args.scheduler))
    except (OSError,UnicodeError,ValueError,TypeError,KeyError,AttributeError) as exc:
        result={'status':'INVALID','errors':[str(exc)]}
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    return 0 if result['status'] in ('PASS','PILOT_ONLY') else 4 if result['status']=='INVALID' else 3


if __name__ == '__main__': raise SystemExit(main())
