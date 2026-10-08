"""PEIG/AALG counterexamples and CT→MRI end-to-end mocked dispatch; no GPU training."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import evidence_outcome as eo
import execution_gate as eg
import experiment_execute as ex
import state_check as sc
from test_evidence_outcome import audit_for, memory

ROOT = eg.ROOT


def fixture():
    return json.loads((ROOT/'examples/preflight-identifiability/ct-mri.json').read_text(encoding='utf-8'))


def reviewed(s):
    p=s['experiments'][-1]['execution_protocol'];p['scientific_review']['design_digest']=eg.review_digest(p)


def diagnostic(s):
    d=json.loads((ROOT/'templates/diagnostic-protocol.template.json').read_text())
    d['experiment_id']=s['experiments'][-1]['id'];d['scientific_review']['status']='PASS'
    d['scientific_review']['design_digest']=eg.diagnostic_digest(d,s)
    return d


def resources(s, directory, hours=None):
    root=Path(directory);x=s['experiments'][-1];p=x['execution_protocol']
    files={'code':('mock_train.py','raise RuntimeError("test command must never be invoked")\n'),
           'config':('config.json',json.dumps({'execution_design':ex.config_binding(p)})),
           'data_split':('split.json',json.dumps({'data_split':x['data_split']})),
           'preregistration':('prereg.json',json.dumps(x['preregistration']))}
    for _,(name,content) in files.items(): (root/name).write_text(content)
    manifest = dict(schema='execution-manifest@1',argv=['python3','mock_train.py'],cwd=str(root),env={},
                gpu_devices=['0'],requested_hours=hours or (p['budget_hours'] if p['mode']=='formal' else p['pilot']['max_hours']),
                files=[dict(kind=k,path=v[0]) for k,v in files.items()])
    p['scientific_review']['execution_digest']=ex.execution_review_digest(s,x,manifest)
    return manifest


def scheduler_for(s):
    records=[]
    for x in s['experiments']:
        if x['status']=='done' and x.get('outcome_analysis'):
            delta,rating=eg.actual_eig(x['outcome_analysis'])
            records.append(dict(experiment=x['id'],predicted_information_gain='high',observed_delta=delta,actual_information_gain=rating))
    return dict(state_version=s['state_version'],next_actions=[],eig_calibration=dict(records=records))


def issue(s,x,m,ledger,**kwargs):
    return ex.issue(s,x,m,ledger,scheduler=scheduler_for(s),**kwargs)


def managed_run(s,x,m,receipt,ledger,**kwargs):
    return ex.run(s,x,m,receipt,ledger,scheduler=scheduler_for(s),**kwargs)


class PEIGTests(unittest.TestCase):
    def setUp(self): self.s=fixture()['state'];self.x=self.s['experiments'][-1];self.p=self.x['execution_protocol']
    def gate(self): return eg.peig(self.s,self.x['id'])
    def reject(self,code):
        g=self.gate();self.assertEqual(g['status'],'HOLD',g);self.assertTrue(any(code in e for e in g['errors']),g)

    def test_fair_comparison_pass(self): self.assertEqual(self.gate()['status'],'PASS',self.gate());self.assertTrue(sc.check_state(self.s).ok)
    def test_critical_capacity_no_control(self): self.p['risk_controls'][0]['comparison_ids']=[];reviewed(self.s);self.reject('MISSING_RISK_CONTROL')
    def test_control_id_does_not_resolve_missing_comparison(self): self.p['risk_controls'][0]['comparison_ids']=['fake'];reviewed(self.s);self.reject('MISSING_RISK_CONTROL')
    def test_psi_added_capacity_not_controlled(self): self.p['arms'][0]['trainable_parameters']*=2;reviewed(self.s);self.reject('INEFFECTIVE_RISK_CONTROL')
    def test_omitted_capacity_attack_is_not_ignored(self): self.s['assurance']=[];self.p['risk_controls']=[];self.p['arms'][0]['trainable_parameters']*=2;reviewed(self.s);self.reject('UNREGISTERED_CAPACITY_RISK')
    def test_capacity_extra_with_valid_matched_control_passes(self):
        baseline=copy.deepcopy(self.p['arms'][1]);baseline.update(id='original-baseline',role='baseline',trainable_parameters=512)
        self.p['arms'].append(baseline);self.p['budget_hours']=3;reviewed(self.s)
        self.assertEqual(self.gate()['status'],'PASS',self.gate())
    def test_unfrozen_dose(self): self.p['intervention']['frozen']=False;reviewed(self.s);self.reject('UNFROZEN_DOSE')
    def test_unobservable_dose(self): self.p['intervention']['observable']='';self.reject('empty text')
    def test_asymmetric_tuning(self): self.p['arms'][0]['optimization']['tuning_trials']=5;reviewed(self.s);self.reject('UNFAIR_BUDGET')
    def test_optimization_diagnostic_missing(self): self.p['arms'][0]['optimization']['diagnostics']=[];self.reject('too few items')
    def test_missing_preregistration(self): self.x['preregistration']=None;self.reject('MISSING_PREREGISTRATION')
    def test_comparison_no_distinct_decision(self):
        for v in self.p['comparisons'][0]['predictions']:v['decision']='CONTINUE'
        reviewed(self.s);self.reject('research decisions')
    def test_unidentified_is_finite_hold(self):
        self.p['risk_controls'][0]['disposition']='UNIDENTIFIABLE';reviewed(self.s);self.reject('UNIDENTIFIABLE')
        self.assertNotIn('followups',self.gate())
    def test_scientific_disagreement_finite_hold(self): self.p['scientific_review']['status']='UNKNOWN';self.reject('SCIENTIFIC_REVIEW')
    def test_scope_limit_requires_real_repair(self): self.p['risk_controls'][0]['disposition']='SCOPE_LIMIT';reviewed(self.s);self.reject('INVALID_SCOPE_LIMIT')
    def test_scope_limit_real_r10(self):
        control=self.p['risk_controls'][0];control.update(disposition='SCOPE_LIMIT',limited_scope=self.s['claims'][0]['scope'],excluded_scope='general MRI mechanisms',repair_index=0)
        self.s['repairs'].append(dict(flaw='No broad mechanism identification',disposition='NARROW_SCOPE',state_delta='Keep only fixed patient scope',closure='ACCEPTED_LIMITATION',targets=['C1']))
        reviewed(self.s);self.assertEqual(self.gate()['status'],'PASS',self.gate())
    def test_legacy_readable_not_grandfathered(self):
        self.x.pop('execution_protocol');self.assertTrue(sc.check_state(self.s).ok);self.reject('MISSING_PROTOCOL')
    def test_pilot_has_prospective_checks(self): self.p['mode']='pilot';reviewed(self.s);self.assertEqual(self.gate()['status'],'PILOT_ONLY')
    def test_pilot_missing_prospective_goal(self): self.p['mode']='pilot';self.p['pilot']['goal']='';self.reject('empty text')
    def test_pure_exploration_remains_available(self):
        self.x.update(stage='X1',claim_targeted=[],hypothesis_targeted=[]);self.p.update(mode='exploratory',claims=[],competitors=[],risk_controls=[],arms=[],comparisons=[])
        self.assertEqual(self.gate()['status'],'PILOT_ONLY',self.gate())
    def test_x2_calibration_does_not_confirm(self):
        self.x.update(stage='X2',claim_targeted=[],hypothesis_targeted=[]);self.p.update(mode='calibration',claims=[],risk_controls=[])
        self.assertEqual(self.gate()['status'],'PILOT_ONLY',self.gate())
    def test_templates_schema_parity(self):
        for name in ('preflight-protocol','diagnostic-protocol','execution-manifest'):
            value=json.loads((ROOT/'templates'/f'{name}.template.json').read_text());self.assertEqual(eg.schema_errors(value,f'{name}.schema.json'),[])
    def test_additive_state_shape_nonzero(self): self.p['arms'][0]['optimization']['lr']='high';r=sc.check_state(self.s);self.assertFalse(r.ok);self.assertIn('EX1',[v.rule for v in r.outcome])


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.s=fixture()['state'];self.x=self.s['experiments'][-1];self.manifest=resources(self.s,self.root);self.ledger=ex.Ledger(self.root/'ledger')
    def issue(self,now=100): return issue(self.s,self.x['id'],self.manifest,self.ledger,now=now)
    def dispatch(self,r,**kwargs): return managed_run(self.s,self.x['id'],self.manifest,r,self.ledger,now=101,**kwargs)
    def test_pass_dry_run_never_invokes_gpu(self):
        result=self.issue();self.assertEqual(result['status'],'PASS',result)
        with patch.object(ex.subprocess,'run') as invoke:
            result=self.dispatch(result['receipt']);self.assertEqual(result['status'],'PASS',result);invoke.assert_not_called()
        self.assertTrue(result['dry_run']);self.assertFalse(result['command_started'])
    def test_mock_dispatch_consumes_receipt(self):
        r=self.issue()['receipt']
        with patch.object(ex.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as invoke:
            result=self.dispatch(r,execute=True);self.assertEqual(result['status'],'PASS',result);invoke.assert_called_once()
        self.assertEqual(self.dispatch(r)['errors'],['UNKNOWN_OR_USED_RECEIPT'])
    def test_config_mismatch_before_issue(self):
        (self.root/'config.json').write_text('{}');self.assertEqual(self.issue()['status'],'HOLD')
    def test_modified_config_after_issue(self):
        r=self.issue()['receipt'];(self.root/'config.json').write_text(json.dumps({'execution_design':ex.config_binding(self.x['execution_protocol']),'silent_lr':1}))
        self.assertEqual(self.dispatch(r)['errors'],['RECEIPT_CONTENT_MISMATCH'])
    def test_modified_code_or_split_rejected(self):
        for name in ('mock_train.py','split.json'):
            with self.subTest(name=name):
                resources(self.s,self.root);r=self.issue()['receipt'];p=self.root/name;p.write_text(p.read_text()+'\n')
                self.assertEqual(self.dispatch(r)['errors'],['RECEIPT_CONTENT_MISMATCH'])
    def test_protocol_or_prereg_modified_after_receipt(self):
        r=self.issue()['receipt'];self.x['preregistration']['outcomes'][0]['observation']='Retrofitted result';resources(self.s,self.root)
        self.assertEqual(self.dispatch(r)['errors'],['RECEIPT_CONTENT_MISMATCH'])
    def test_manual_pass_forgery(self):
        r=self.issue()['receipt'];r['permission']='PILOT_ONLY';self.assertEqual(self.dispatch(r)['errors'],['FORGED_RECEIPT'])
    def test_receipt_expiry(self):
        r=self.issue()['receipt'];out=managed_run(self.s,self.x['id'],self.manifest,r,self.ledger,now=r['expires_at']);self.assertEqual(out['errors'],['EXPIRED_RECEIPT'])
    def test_single_use_parallel_issued_receipts(self):
        first=self.issue()['receipt'];second=self.issue()['receipt'];self.assertEqual(self.dispatch(first)['status'],'PASS');self.assertEqual(self.dispatch(second)['errors'],['FORMAL_BUDGET_EXHAUSTED'])
    def test_pilot_budget_cannot_reset_by_seed_id(self):
        self.x['execution_protocol']['mode']='pilot';self.manifest=resources(self.s,self.root)
        r=self.issue();self.assertEqual(r['status'],'PILOT_ONLY',r);self.assertEqual(self.dispatch(r['receipt'])['status'],'PASS')
        self.x.update(id='X200',seed=1);self.s['assurance'][0]['discriminating_test']='X200';self.assertEqual(self.issue()['errors'],['PILOT_BUDGET_EXHAUSTED'])
    def test_preflight_card_loop_finishes_at_configured_limit(self):
        self.x['execution_protocol']['risk_controls'][0]['comparison_ids']=[]
        for i in range(3):
            self.x['id']='X'+str(20+i);self.x['execution_protocol']['conditions']['redesign']='Reworded scope '+str(i);self.assertEqual(self.issue()['status'],'HOLD')
        self.x['execution_protocol']['risk_controls'][0]['comparison_ids']=['CMP-capacity'];reviewed(self.s);self.manifest=resources(self.s,self.root)
        out=self.issue();self.assertEqual(out['status'],'HOLD');self.assertIn('PREFLIGHT_REVISION_LIMIT',out['errors'][0])
    def test_new_evidence_reopens_preflight(self):
        self.x['execution_protocol']['risk_controls'][0]['comparison_ids']=[]
        for _ in range(3): self.issue()
        self.s['evidence'].append(dict(id='E99',kind='observation',supports=[],contradicts=[],strength='weak',scope=self.s['claims'][0]['scope'],epistemic_status='Observed',source_ref='New measured dose log',verification_tier='T2',depends_on=[],validity=dict(status='valid',reason='Actual independent measurement',since_state_version=0)))
        self.s['evidence'][-1]['diagnostic_observation']=dict(kind='metric',location='dose.json',content='New independent gradient dose 0.2',digest=eo.digest('New independent gradient dose 0.2'))
        self.x['execution_protocol']['risk_controls'][0]['comparison_ids']=['CMP-capacity'];reviewed(self.s);self.manifest=resources(self.s,self.root)
        self.assertEqual(self.issue()['status'],'PASS')
    def test_human_exception_is_only_bounded_pilot(self):
        p=self.x['execution_protocol'];p['human_exception']=dict(reviewer='Human',reason='Finite exploratory check',scope=self.x['data_split'],expires_at=200,max_hours=0.1)
        reviewed(self.s);self.assertEqual(self.issue()['status'],'HOLD')
        p['mode']='pilot';self.manifest=resources(self.s,self.root);self.assertEqual(self.issue()['status'],'PILOT_ONLY')
    def test_policy_cannot_be_weakened(self):
        self.issue();policy=dict(eg.DEFAULT_POLICY,max_preflight_revisions=99)
        with self.assertRaisesRegex(ValueError,'FROZEN_POLICY'): issue(self.s,self.x['id'],self.manifest,ex.Ledger(self.root/'ledger',policy))
    def test_tampered_ledger_rejected(self):
        self.issue();p=self.root/'ledger/events.jsonl';p.write_text(p.read_text().replace('"max_preflight_revisions":3','"max_preflight_revisions":99'))
        with self.assertRaisesRegex(ValueError,'LEDGER_TAMPERED'): self.issue()
    def test_formal_revision_limit_allows_one_bounded_pilot(self):
        p=self.x['execution_protocol'];p['risk_controls'][0]['disposition']='UNIDENTIFIABLE'
        for _ in range(3): self.issue()
        p['mode']='pilot';self.manifest=resources(self.s,self.root)
        result=self.issue();self.assertEqual(result['status'],'PILOT_ONLY',result)
        self.assertEqual(self.dispatch(result['receipt'])['status'],'PASS')
        self.assertEqual(self.issue()['status'],'HOLD')
    def test_failed_pilot_card_edits_are_also_finite(self):
        p=self.x['execution_protocol'];p['mode']='pilot';p['pilot']['goal']=''
        for _ in range(3): self.assertEqual(self.issue()['status'],'HOLD')
        p['pilot']['goal']='Fix dose calibration';self.manifest=resources(self.s,self.root)
        self.assertTrue(any('PREFLIGHT_REVISION_LIMIT' in e for e in self.issue()['errors']))
    def test_added_risk_or_hypothesis_id_cannot_reset_preflight(self):
        p=self.x['execution_protocol'];p['risk_controls'][0]['comparison_ids']=[]
        for _ in range(3): self.issue()
        p['risk_controls'][0]['comparison_ids']=['CMP-capacity']
        self.x['hypothesis_targeted']=['H3'];p['competitors']=['H3','H2'];p['comparisons'][0]['predictions'][0]['hypothesis_id']='H3'
        new=copy.deepcopy(self.s['assurance'][0]);new.update(id='new-risk',risk_type='intervention');self.s['assurance'].append(new)
        rc=copy.deepcopy(p['risk_controls'][0]);rc['risk_id']='new-risk';p['risk_controls'].append(rc);reviewed(self.s);self.manifest=resources(self.s,self.root)
        self.assertTrue(any('PREFLIGHT_REVISION_LIMIT' in e for e in self.issue()['errors']))
    def test_command_different_from_review_rejected(self):
        self.manifest['argv'].append('--lr=100')
        self.assertTrue(any('EXECUTION_REVIEW_MISMATCH' in e for e in self.issue()['errors']))
    def test_deleted_ledger_tail_fails_closed(self):
        self.issue();path=self.root/'ledger/events.jsonl';path.write_text(path.read_text().splitlines()[0]+'\n')
        with self.assertRaisesRegex(ValueError,'LEDGER_TRUNCATED'): self.issue()
    def test_stale_scheduler_denies_issue(self):
        scheduler=scheduler_for(self.s);scheduler['state_version']=999
        result=ex.issue(self.s,self.x['id'],self.manifest,self.ledger,scheduler=scheduler)
        self.assertEqual(result['status'],'HOLD');self.assertTrue(any('SCHEDULER_GATE' in e for e in result['errors']))
    def test_scheduler_mutated_after_issue_denies_run(self):
        r=self.issue()['receipt'];scheduler=scheduler_for(self.s);scheduler['next_actions']=[dict(action='R12',type='narrative',target='C1',eig='low',cost='low')]
        result=ex.run(self.s,self.x['id'],self.manifest,r,self.ledger,now=101,scheduler=scheduler)
        self.assertEqual(result['errors'],['SCHEDULER_RECEIPT_MISMATCH'])
    def test_cli_denial_is_nonzero_structured_and_no_output_receipt(self):
        state=self.root/'state.json';manifest=self.root/'manifest.json';self.x['execution_protocol']['risk_controls'][0]['comparison_ids']=[]
        state.write_text(json.dumps(self.s));manifest.write_text(json.dumps(self.manifest));scheduler=self.root/'scheduler.json';scheduler.write_text(json.dumps(scheduler_for(self.s)));receipt=self.root/'receipt.json'
        result=subprocess.run([sys.executable,str(ROOT/'scripts/experiment_execute.py'),'issue','--state',str(state),'--experiment',self.x['id'],'--manifest',str(manifest),'--scheduler',str(scheduler),'--output',str(receipt)],capture_output=True,text=True)
        self.assertEqual(result.returncode,3);self.assertEqual(json.loads(result.stdout)['status'],'HOLD');self.assertFalse(receipt.exists())


class AALGTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.s=fixture()['state'];self.d=diagnostic(self.s);self.ledger=ex.Ledger(self.root/'ledger')
    def check(self): return ex.diagnose(self.s,self.d,self.ledger)
    def test_equal_diagnosis_stops_even_reworded(self):
        self.assertEqual(self.check()['status'],'PASS');self.d['difference']='Renamed bottleneck';self.d['testable_premise']='Rephrased explanation';self.d['scientific_review']['design_digest']=eg.diagnostic_digest(self.d,self.s)
        self.assertEqual(self.check()['status'],'PASS');result=self.check();self.assertEqual(result['status'],'STOP_DIAGNOSIS');self.assertEqual(result['decision'],'REDESIGN');self.assertEqual(result['trigger'],'T8')
    def test_experiment_id_seed_scope_uncertainty_no_reset(self):
        self.check();self.check();x=self.s['experiments'][-1];x.update(id='X999',seed=1);self.s['assurance'][0]['discriminating_test']='X999';self.d['experiment_id']='X999';self.d['scientific_review']['design_digest']=eg.diagnostic_digest(self.d,self.s)
        self.s['claims'][0]['scope']+=' narrower';self.s['uncertainties'][0]['uncertainty']='low'
        self.assertEqual(self.check()['status'],'STOP_DIAGNOSIS')
    def test_new_observed_evidence_allows_diagnosis(self):
        self.check();self.check();e=dict(id='E99',kind='observation',supports=[],contradicts=[],strength='weak',scope=self.s['claims'][0]['scope'],epistemic_status='Observed',source_ref='Independent dose trace',verification_tier='T2',depends_on=[],validity=dict(status='valid',reason='Independent actual trace',since_state_version=0));e['diagnostic_observation']=dict(kind='log',location='independent-trace.json',content='Independent actual dose measurement',digest=eo.digest('Independent actual dose measurement'));self.s['evidence'].append(e)
        self.d['evidence_ids']=['E99'];self.d['scientific_review']['design_digest']=eg.diagnostic_digest(self.d,self.s)
        self.assertEqual(self.check()['status'],'PASS')
    def test_duplicate_evidence_id_is_not_new_evidence(self):
        self.s['evidence'].append(dict(id='E99',kind='observation',supports=[],contradicts=[],strength='weak',scope='fixed',epistemic_status='Observed',source_ref='trace',verification_tier='T2',depends_on=[],validity=dict(status='valid',reason='actual',since_state_version=0)))
        self.s['evidence'][-1]['diagnostic_observation']=dict(kind='metric',location='dose.json',content='Original dose trace',digest=eo.digest('Original dose trace'))
        self.d['scientific_review']['design_digest']=eg.diagnostic_digest(self.d,self.s)
        self.assertEqual(self.check()['status'],'PASS');self.assertEqual(self.check()['status'],'PASS');duplicate=copy.deepcopy(self.s['evidence'][-1]);duplicate['id']='E100';duplicate['source_ref']='same trace reworded';self.s['evidence'].append(duplicate)
        self.assertEqual(self.check()['status'],'STOP_DIAGNOSIS')
    def test_changed_evidence_invalidates_prior_diagnostic_review(self):
        content='New independent dose measurement'
        self.s['evidence'].append(dict(id='E99',kind='observation',supports=[],contradicts=[],strength='weak',scope='fixed',epistemic_status='Observed',source_ref='independent log',verification_tier='T2',depends_on=[],validity=dict(status='valid',reason='Actual observation',since_state_version=0),diagnostic_observation=dict(kind='metric',location='new.json',content=content,digest=eo.digest(content))))
        self.assertIn('DIAGNOSTIC_REVIEW_REQUIRED',self.check()['errors'])
    def test_new_mechanism_with_new_discriminating_design_allowed(self):
        self.check();self.check();x=self.s['experiments'][-1];p=x['execution_protocol'];p['arms'][0]['intervention']['dose']=2;p['intervention']['dose_levels']=[0,2]
        self.d['hypothesis_id']='H3';self.d['predictions'][0]['hypothesis_id']='H3';p['competitors']=['H3','H2'];x['hypothesis_targeted']=['H3'];p['comparisons'][0]['predictions'][0]['hypothesis_id']='H3';reviewed(self.s);self.d['scientific_review']['design_digest']=eg.diagnostic_digest(self.d,self.s)
        self.assertEqual(self.check()['status'],'PASS')
    def test_new_arm_or_control_label_does_not_reset(self):
        self.check();self.check();p=self.s['experiments'][-1]['execution_protocol'];p['arms'][0]['id']='renamed-Psi';p['comparisons'][0]['left']='renamed-Psi';p['comparisons'][0]['id']='new-control-ID'
        self.d['scientific_review']['design_digest']=eg.diagnostic_digest(self.d,self.s)
        self.assertEqual(self.check()['status'],'STOP_DIAGNOSIS')
    def test_no_decision_value_rejected(self):
        for p in self.d['predictions']:p['decision']='CONTINUE'
        self.d['scientific_review']['design_digest']=eg.diagnostic_digest(self.d,self.s);self.assertEqual(self.check()['status'],'HOLD')
    def test_posthoc_not_repackaged_preregistered(self):
        self.d.update(origin='preregistered',generating_evidence_ids=['E-no-source']);self.d['scientific_review']['design_digest']=eg.diagnostic_digest(self.d,self.s)
        result=self.check();self.assertEqual(result['status'],'HOLD');self.assertIn('POST_HOC_IS_EXPLORATORY',result['errors'])
    def test_same_result_cannot_independently_confirm(self):
        e=dict(id='E99',kind='observation',supports=[],contradicts=[],strength='weak',scope='fixed',epistemic_status='Observed',source_ref='trace',verification_tier='T2',depends_on=[],validity=dict(status='valid',reason='actual',since_state_version=0));e['diagnostic_observation']=dict(kind='log',location='independent-trace.json',content='Independent actual dose measurement',digest=eo.digest('Independent actual dose measurement'));self.s['evidence'].append(e)
        self.d.update(evidence_ids=['E99'],generating_evidence_ids=['E99'],independent_confirmation=True);self.d['scientific_review']['design_digest']=eg.diagnostic_digest(self.d,self.s)
        self.assertIn('SAME_RESULT_NOT_INDEPENDENT_CONFIRMATION',self.check()['errors'])
    def test_renamed_source_cannot_independently_confirm(self):
        content='Same hypothesis-generating measurement'
        e=dict(id='E90',kind='observation',supports=[],contradicts=[],strength='weak',scope='fixed',epistemic_status='Observed',source_ref='trace',verification_tier='T2',depends_on=[],validity=dict(status='valid',reason='actual',since_state_version=0),diagnostic_observation=dict(kind='metric',location='first.json',content=content,digest=eo.digest(content)))
        other=copy.deepcopy(e);other['id']='E91';other['diagnostic_observation']['location']='renamed.json';self.s['evidence'].extend([e,other])
        self.d.update(evidence_ids=['E91'],generating_evidence_ids=['E90'],independent_confirmation=True);self.d['scientific_review']['design_digest']=eg.diagnostic_digest(self.d,self.s)
        self.assertIn('SAME_RESULT_NOT_INDEPENDENT_CONFIRMATION',self.check()['errors'])
    def test_r10_cannot_schedule_unregistered_diagnosis(self):
        self.s['repairs'].append(dict(flaw='Need another diagnosis',disposition='RUN_TEST',state_delta='Queue same comparison',closure='RESOLVED',targets=['C1']))
        m=resources(self.s,self.root);out=issue(self.s,'X1',m,self.ledger);self.assertEqual(out['status'],'HOLD');self.assertTrue(any('AALG_REQUIRED' in e for e in out['errors']))
    def test_r10_registered_diagnosis_grants_one_issue(self):
        self.s['repairs'].append(dict(flaw='Capacity check',disposition='RUN_TEST',state_delta='Queue identifying comparison',closure='RESOLVED',targets=['C1'],diagnostic_protocol=self.d))
        m=resources(self.s,self.root);self.assertEqual(self.check()['status'],'PASS');out=issue(self.s,'X1',m,self.ledger);self.assertEqual(out['status'],'PASS',out)
        self.assertEqual(issue(self.s,'X1',m,self.ledger)['status'],'HOLD')


class InstallationTests(unittest.TestCase):
    def test_complete_copy_preserves_schemas_templates_and_cli(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'research-idea-pipeline'
            shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('.dev','__pycache__'))
            for folder in ('schemas','scripts','templates','references'):
                for original in (ROOT/folder).glob('*'):
                    if original.is_file(): self.assertEqual(original.read_bytes(),(target/folder/original.name).read_bytes())
            result=subprocess.run([sys.executable,str(target/'scripts/state_check.py'),'--check',str(target/'templates/research-state.template.json')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout)
            result=subprocess.run([sys.executable,str(target/'scripts/experiment_execute.py'),'--help'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout)



def outcome_case(case, state, execution_record, kind):
    s=copy.deepcopy(state);x=s['experiments'][-1];x.update(status='running',execution_record=execution_record)
    p=copy.deepcopy(case['packet']);a=copy.deepcopy(case['analysis']);p['experiment_digest']=eo.digest(x)
    p['execution_status']='failed' if kind=='invalid' else 'completed'
    p['result_summary']='Mocked '+kind+' measurement-only SSL at matched capacity'
    p['sources'][0].update(content=p['result_summary'],digest=eo.digest(p['result_summary']))
    p['observations'][0]['statement']=p['result_summary']
    a.update(base_state_digest=eo.digest(s),context_digest=eo.digest(eo.validation_context(s)),packet_digest=eo.digest(p),reasoning_summary=p['result_summary'],outcome={'positive':'POSITIVE_EVIDENCE','negative':'NEGATIVE_EVIDENCE','inconclusive':'INCONCLUSIVE','invalid':'INVALID_EXPERIMENT'}[kind])
    for u in a['claim_updates']+a['hypothesis_updates']:
        u.update(reason=p['result_summary'],new_status='SUPPORTED' if kind=='positive' else 'WEAKENED' if kind=='negative' else 'UNRESOLVED',direction='positive' if kind=='positive' else 'negative' if kind=='negative' else 'neutral',identification='PASS' if kind in ('positive','negative') else 'UNKNOWN')
    a['claim_updates'][0]['new_support']='supported' if kind=='positive' else s['claims'][0]['status']
    decision=a['decisions'][0];decision.update(action='CONTINUE' if kind=='positive' else 'RETRY' if kind=='invalid' else 'HOLD',required_fixes=['Fix measured invalid protocol'] if kind=='invalid' else [],reason=p['result_summary'])
    a['negative_knowledge']=[dict(memory(t),finding=p['result_summary']) for t in ('C1','H1')] if kind=='negative' else []
    if kind=='invalid': a['validity_checks']['execution']['status']='FAIL'
    if kind=='inconclusive':
        a['validity_checks']['measurement']['status']='UNKNOWN'
        for u in a['claim_updates']+a['hypothesis_updates']:u['identification']='UNKNOWN'
    if kind!='positive': a['failure_attributions']=[dict(type='unknown' if kind!='invalid' else 'protocol_failure',confidence='low' if kind!='invalid' else 'high',evidence=['S1'],alternative_explanations=['Unverified optimizer explanation remains uncertainty'],what_would_disambiguate='Independent controlled dose experiment')]
    return s,p,a,audit_for(s,p,a)


class EndToEndTests(unittest.TestCase):
    def simulate(self,kind):
        case=fixture();s=case['state'];x=s['experiments'][-1]
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);directory=temporary.name
        m=resources(s,directory);ledger=ex.Ledger(Path(directory)/'ledger');issued=issue(s,x['id'],m,ledger,now=100);self.assertEqual(issued['status'],'PASS',issued)
        with patch.object(ex.subprocess,'run',return_value=subprocess.CompletedProcess([],0)):
            launched=managed_run(s,x['id'],m,issued['receipt'],ledger,execute=True,now=101)
        self.assertEqual(launched['status'],'PASS',launched)
        args=outcome_case(case,s,launched['execution_record'],kind)
        self.assertEqual(ex.verify_result_execution(args[0],ledger),[])
        result=eo.apply(*args,timestamp='2026-10-08T00:00:00+00:00');self.assertEqual(result['status'],'PASS',result)
        out=result['state'];self.assertTrue(sc.check_state(out).ok)
        receipt=out['experiments'][-1]['outcome_analysis'];assurance=dict(schema='evidence-outcome-assurance@1',state_digest=eo.digest(out),analysis_digest=eo.digest(receipt['analysis']),checks={k:dict(status='PASS',reason='Source-bound mock Assurance') for k in ('integrity','claim_calibration','reproducibility','stop_rule_compliance')})
        decision=eo.decision_gate(out,x['id'],assurance);self.assertEqual(decision['status'],'PASS',decision)
        record_delta,rating=eg.actual_eig(receipt)
        scheduler=dict(state_version=out['state_version'],next_actions=[],eig_calibration=dict(records=[] if kind=='invalid' else [dict(experiment=x['id'],predicted_information_gain='high',observed_delta=record_delta,actual_information_gain=rating)]))
        self.assertEqual(eg.scheduler_check(out,scheduler)['status'],'PASS',eg.scheduler_check(out,scheduler))
        return out,ledger,copy.deepcopy(scheduler)
    def test_positive_chain(self): out,_,_=self.simulate('positive');self.assertEqual(out['claims'][0]['outcome_status'],'SUPPORTED')
    def test_negative_not_rescued_by_posthoc_optimizer_guess(self):
        out,_,_=self.simulate('negative');self.assertEqual(out['claims'][0]['outcome_status'],'WEAKENED');self.assertEqual(out['failures'][-1]['failure_attributions'][0]['type'],'unknown')
    def test_inconclusive_chain(self): out,_,_=self.simulate('inconclusive');self.assertNotEqual(out['claims'][0].get('outcome_status'),'SUPPORTED')
    def test_invalid_chain(self): out,_,_=self.simulate('invalid');self.assertEqual(out['experiments'][-1]['status'],'failed');self.assertEqual(out['failures'][-1]['negative_knowledge'],[])
    def test_missing_r7_control_blocks_dispatch(self):
        s=fixture()['state'];s['experiments'][-1]['execution_protocol']['risk_controls']=[]
        with tempfile.TemporaryDirectory() as directory,patch.object(ex.subprocess,'run') as invoke:
            r=issue(s,'X1',resources(s,directory),ex.Ledger(Path(directory)/'ledger'));self.assertEqual(r['status'],'HOLD');invoke.assert_not_called()
    def test_preregistration_rewrite_after_mock_execution_rejected(self):
        out,_,_=self.simulate('positive');out['experiments'][-1]['preregistration']['outcomes'][0]['observation']='Post-result prediction';self.assertFalse(sc.check_state(out).ok)
    def test_eig_forged_uncertainty_delta_rejected(self):
        out,_,scheduler=self.simulate('positive');scheduler['eig_calibration']['records'][0]['observed_delta']['new_uncertainties']=['U999'];self.assertEqual(eg.scheduler_check(out,scheduler)['status'],'FAIL')
    def test_dry_run_cannot_be_scientific_evidence(self):
        s=fixture()['state']
        with tempfile.TemporaryDirectory() as directory:
            m=resources(s,directory);ledger=ex.Ledger(Path(directory)/'ledger');r=issue(s,'X1',m,ledger,now=100)['receipt'];launched=managed_run(s,'X1',m,r,ledger,now=101)
            args=outcome_case(fixture(),s,launched['execution_record'],'positive');self.assertFalse(sc.check_state(args[0]).ok);self.assertTrue(ex.verify_result_execution(args[0],ledger))
    def test_full_negative_loop_stops_and_new_evidence_reopens(self):
        out,ledger,_=self.simulate('negative');x=copy.deepcopy(out['experiments'][-1])
        for k in ('outcome_analysis','execution_record','result_pending'): x.pop(k,None)
        x.update(id='X2',parent='X1',status='planned',result='',result_at_state_version=None,seed=1,known_flaws=[],validity=dict(status='pending',reason='Independent decision-bearing followup',since_state_version=out['state_version']))
        out['experiments'].append(x);out['assurance'][0]['discriminating_test']='X2'
        d=diagnostic(out);out['repairs'].append(dict(flaw='Matched capacity explanation remains unresolved',disposition='RUN_TEST',state_delta='Queue X2 without changing negative scientific status',closure='RESOLVED',targets=['C1'],diagnostic_protocol=d))
        self.assertTrue(sc.check_state(out).ok,sc.check_state(out).as_dict())
        m=resources(out,ledger.directory.parent)
        for _ in range(2): self.assertEqual(ex.diagnose(out,d,ledger)['status'],'PASS')
        self.assertEqual(ex.diagnose(out,d,ledger)['status'],'STOP_DIAGNOSIS')
        denied=issue(out,'X2',m,ledger,now=102);self.assertEqual(denied['status'],'HOLD');self.assertTrue(any('STOP_DIAGNOSIS' in e for e in denied['errors']))
        new_content='Independent measured gradient dose contradicts the prior optimization premise'
        out['evidence'].append(dict(id='E-independent',kind='observation',supports=[],contradicts=[],strength='weak',scope=out['claims'][0]['scope'],epistemic_status='Observed',source_ref='Independent calibration artifact',verification_tier='T2',depends_on=[],validity=dict(status='valid',reason='New source-bound observation',since_state_version=out['state_version']),diagnostic_observation=dict(kind='metric',location='independent-dose.json',content=new_content,digest=eo.digest(new_content))))
        d['evidence_ids']=['E-independent'];d['scientific_review']['design_digest']=eg.diagnostic_digest(d,out)
        self.assertEqual(ex.diagnose(out,d,ledger)['status'],'PASS')
        reopened=issue(out,'X2',m,ledger,now=103);self.assertEqual(reopened['status'],'PASS',reopened)
        scheduler=scheduler_for(out);scheduler['next_actions']=[dict(action='X2',type='discriminating_experiment',target='C1',eig='high',cost='low')]
        self.assertEqual(eg.scheduler_check(out,scheduler)['status'],'PASS')
        self.assertEqual(out['claims'][0]['outcome_status'],'WEAKENED')
    def test_stop_rule_not_bypassed_by_id_seed_or_reworded_prereg(self):
        s=fixture()['state'];x=s['experiments'][-1]
        sr=dict(id='SR-capacity',target_ids=['C1'],scope=s['claims'][0]['scope'],kind='protocol',rule='Stop unchanged capacity protocol',protocol_signature=eo.protocol_signature(x),revisit_conditions=['New independent identifying evidence'])
        s['failures'].append(dict(id='F-stop',kind='inconclusive',what='Protocol exhausted',why='No decision change',referenced_by=['X1'],depends_on=[],validity=dict(status='valid',reason='Registered stop',since_state_version=0),stop_rules=[sr]));x['known_flaws']=['F-stop'];x['execution_blocked_by']=['SR-capacity']
        x.update(id='X222',seed=1);s['failures'][-1]['referenced_by']=['X222'];x['preregistration']['outcomes'][0]['observation']='Reworded hypothesis'
        self.assertEqual(eo._check_plan(s,x['id'])['status'],'FAIL');self.assertEqual(eg.peig(s,x['id'])['status'],'HOLD')
        d=diagnostic(s);result=eg.diagnostic_check(s,d,[],eg.DEFAULT_POLICY);self.assertEqual(result['status'],'PIVOT_RECOMMENDED',result)


if __name__ == '__main__': unittest.main()
