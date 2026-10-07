"""Outcome transition and counterexample tests, not a semantic-judge accuracy benchmark."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import evidence_outcome as eo
import state_check as sc
from test_golden_path import r0_contract, r2_field_mapping, r3_dual_discovery


TIMESTAMP = '2026-10-08T00:00:00+00:00'


def policy():
    return {'schema': 'evidence-outcome-policy@1', 'frozen_at_state_version': 0,
            'min_valid_runs': 2, 'min_seeds': 2, 'min_datasets': 1,
            'require_independent_replication': False, 'min_verification_tier': 'T2'}


def fixture(outcome='positive', state=None, xid='X1', seed=0):
    s = copy.deepcopy(state) if state is not None else r0_contract()
    if state is None:
        r2_field_mapping(s); r3_dual_discovery(s)
        s['contract']['outcome_policy'] = policy()
        s['narrative_view'] = {'rendered_claims': [s['claims'][0]['id']], 'note': 'Frozen communication view.'}
        s['hypotheses'][0].update(scientific_scope='Dataset A / fixed budget', central=True, statement='Intervention X improves metric M against matched comparator P.', falsifier='The preregistered improvement is absent under matched P.')
        c = s['claims'][0]; c.update(statement='X improves M against P on Dataset A at fixed compute.', scope='Dataset A / fixed budget', status='ungrounded', supporting_evidence=[], refuting_evidence=[], known_flaws=[])
    x = {'id': xid, 'parent': None, 'stage': 'X3', 'claim_targeted': [s['claims'][0]['id']],
         'hypothesis_targeted': ['H1'], 'alternative_targeted': ['ALT-1'], 'code_commit': 'abc123',
         'data_split': 'Dataset A test split', 'seed': seed, 'metric': 'M', 'result': '',
         'interpretation': 'Result not yet interpreted.', 'unexpected': [], 'known_flaws': [], 'next_branches': [],
         'status': 'running', 'preregistration': {'frozen_at_state_version': 0, 'outcomes': [
             {'id': 'O1', 'observation': 'M improves against matched P.', 'update': [{'target': s['claims'][0]['id'], 'op': 'strengthen'}]},
             {'id': 'O2', 'observation': 'M does not improve against matched P.', 'update': [{'target': s['claims'][0]['id'], 'op': 'weaken'}]}]},
         'result_at_state_version': None, 'depends_on': [],
         'validity': {'status': 'valid', 'reason': 'Frozen planned comparison.', 'since_state_version': 0},
         'outcome_protocol': {'dataset': 'Dataset A', 'design': 'X versus P under matched compute', 'scope': 'Dataset A / fixed budget', 'independent_replication': False}}
    s['experiments'].append(x)
    cid = s['claims'][0]['id']
    observation = 'M improves by 0.8 against matched P.' if outcome == 'positive' else 'No improvement against matched P.' if outcome == 'negative' else 'Training crashed with a shape mismatch.'
    content = observation + ' Protocol and metric checked against frozen configuration.'
    packet = {'schema': 'evidence-result@1', 'experiment_id': xid, 'experiment_digest': eo.digest(x),
              'execution_status': 'failed' if outcome == 'invalid' else 'completed', 'result_summary': observation,
              'sources': [{'id': 'S1', 'kind': 'log', 'location': xid + '/run.log', 'content': content, 'digest': eo.digest(content)}],
              'observations': [{'id': 'O1', 'statement': observation, 'scope': 'Dataset A / fixed budget', 'source_ids': ['S1']}]}
    status = 'SUPPORTED' if outcome == 'positive' else 'WEAKENED' if outcome == 'negative' else 'UNRESOLVED'
    direction = 'positive' if outcome == 'positive' else 'negative' if outcome == 'negative' else 'neutral'
    def update(target):
        return {'id': target['id'], 'scope': 'Dataset A / fixed budget', 'scope_relation': 'FULL',
                'previous_status': eo.previous_status(target, 'Dataset A / fixed budget'), 'new_status': status,
                'evidence': ['O1'], 'direction': direction, 'identification': 'PASS', 'reason': observation,
                'replication_ids': [xid]}
    cu = update(s['claims'][0]); cu.update(previous_support=s['claims'][0]['status'], new_support='supported' if outcome == 'positive' else 'partially-supported' if outcome == 'negative' and s['claims'][0]['status']=='supported' else s['claims'][0]['status'], scope_change=None)
    hu = update(s['hypotheses'][0])
    a = {'schema': 'evidence-outcome-analysis@1', 'id': 'OA-' + xid, 'experiment_id': xid,
         'base_state_digest': eo.digest(s), 'context_digest': eo.digest(eo.validation_context(s)), 'packet_digest': eo.digest(packet),
         'outcome': 'POSITIVE_EVIDENCE' if outcome == 'positive' else 'NEGATIVE_EVIDENCE' if outcome == 'negative' else 'INVALID_EXPERIMENT',
         'verification_tier': 'T2', 'validity_checks': {k: {'status': 'FAIL' if k == 'execution' and outcome == 'invalid' else 'PASS', 'reason': 'Inspected the supplied protocol/log fixture.', 'source_ids': ['S1']} for k in ('execution','protocol','measurement','evaluation')},
         'claim_updates': [cu], 'hypothesis_updates': [hu], 'failure_attributions': [], 'alternatives': [],
         'decisions': [{'target_ids': [cid, 'H1'], 'action': 'CONTINUE' if outcome == 'positive' else 'HOLD' if outcome == 'negative' else 'RETRY',
                        'reason': observation, 'required_fixes': ['Fix the tensor shape mismatch before a new run.'] if outcome == 'invalid' else [],
                        'stop_rule_id': None, 'next_action_id': 'N1'}], 'stop_rules': [],
         'followups': [{'id':'N1','target_ids':[cid,'H1'],'description':'Discriminate H1 against its nearest alternative after the stated prerequisite.',
                       'expected_information_gain':'high','cost':'low','scientific_value':'high','risk':'medium','decision_it_resolves':'Whether the proposed intervention changes the measured effect.'}],
         'negative_knowledge': [], 'repairs': [], 'open_questions': [], 'uncertainty_updates': [],
         'unchanged': ['Dataset, metric, comparator, scope and narrative remain unchanged.'], 'reasoning_summary': observation}
    if outcome != 'positive':
        a['failure_attributions'] = [{'type':'unknown' if outcome=='negative' else 'implementation_failure', 'confidence':'low' if outcome=='negative' else 'high', 'evidence':['S1'], 'alternative_explanations':['An unisolated optimization effect remains possible.'], 'what_would_disambiguate':'Inspect training traces and run a controlled replication.'}]
    if outcome == 'negative':
        a['negative_knowledge'] = [memory(t) for t in (cid,'H1')]
    return s, packet, a, audit_for(s,packet,a)


def memory(target):
    return {'target_id':target, 'finding':'No improvement in this scoped comparison.', 'ruled_out':[],
            'not_ruled_out':['Sampling variation and the alternative hypothesis remain possible.'], 'likely_failure_mode':'unknown',
            'retry_allowed':True,'retry_conditions':['A preregistered independent seed provides new information.'],
            'revisit_conditions':['Inspect new discriminating evidence within the same scientific scope.'], 'confidence':'medium'}


def audit_for(s,p,a):
    return {'schema':'evidence-outcome-audit@1','state_digest':eo.digest(s),'packet_digest':eo.digest(p),'analysis_digest':eo.digest(a),
            'checks':{k:{'status':'PASS','reason':'Source-bound transition fixture, not an LLM benchmark.'} for k in eo.CHECKS}}


def refresh(args):
    s,p,a,_=args; a['base_state_digest']=eo.digest(s); a['context_digest']=eo.digest(eo.validation_context(s)); a['packet_digest']=eo.digest(p); args[3]=audit_for(s,p,a)


def set_pivot(args, action='PIVOT'):
    s,p,a,_=args
    a['stop_rules']=[{'id':'SR-'+a['experiment_id'],'target_ids':[u['id'] for u in a['claim_updates']+a['hypothesis_updates']],
                     'scope':'Dataset A / fixed budget','kind':'protocol','rule':'Do not repeat the same protocol without resolving the stated condition.',
                     'protocol_signature':eo.protocol_signature(eo.index(s,'experiments')[a['experiment_id']]),
                     'revisit_conditions':['The disputed scientific assumption changes with inspected evidence.']}]
    a['decisions'][0].update(action=action,stop_rule_id=a['stop_rules'][0]['id'])
    for n in a['negative_knowledge']: n.update(retry_allowed=False,retry_conditions=[])
    refresh(args)


def change_observation(args, statement):
    p=args[1];p['result_summary']=statement
    p['observations'][0]['statement']=statement
    p['sources'][0].update(content=statement,digest=eo.digest(statement))
    for u in args[2]['claim_updates']+args[2]['hypothesis_updates']:u['reason']=statement
    args[2]['reasoning_summary']=statement


def mixed_fixture():
    args=list(fixture('negative'));s,p,a,_=args;scope='Dataset A / fixed budget'
    c=s['claims'][0];cid=c['id'];c['subclaims']=['C2','C3']
    for new_id,statement in [('C2','The predicted mechanism changes proxy Z.'),('C3','X improves M under the declared stress setting across replications.')]:
        child=copy.deepcopy(c);child.update(id=new_id,parent=cid,subclaims=[],statement=statement)
        s['claims'].append(child)
    s['hypotheses'][0].update(statement='The proposed mechanism predicts a change in proxy Z.',falsifier='The predicted proxy Z change is absent under the frozen identifying control.')
    s['hypotheses'][1]['statement']='The performance gain could result from increased capacity.'
    x=s['experiments'][-1];x['claim_targeted']=[cid,'C2','C3'];x['metric']='M and proxy Z'
    x['outcome_protocol']['design']='Matched P comparison, proxy Z measurement and a fixed stress setting'
    x['preregistration']['outcomes'] += [
        {'id':'O3','observation':'The predicted proxy Z change is absent.','update':[{'target':'C2','op':'weaken'},{'target':'H1','op':'weaken'}]},
        {'id':'O4','observation':'The repeated-seed stress comparison identifies an improvement.','update':[{'target':'C3','op':'strengthen'}]}]
    p['experiment_digest']=eo.digest(x)
    statements=['M improves by 0.8 against matched P.','Proxy Z does not change as predicted.','M decreases by 0.4 under stress in one run. Broad robustness is not identified.']
    content=' '.join(statements)+' Matched compute, protocol and measurement checks completed.'
    p.update(result_summary=' '.join(statements),sources=[dict(p['sources'][0],content=content,digest=eo.digest(content))],
             observations=[{'id':'O'+str(i+1),'statement':t,'scope':scope,'source_ids':['S1']} for i,t in enumerate(statements)])
    base=a['claim_updates'][0]
    performance=dict(base,new_status='SUPPORTED',direction='positive',new_support='supported',evidence=['O1'],reason=statements[0])
    mechanism=dict(base,id='C2',evidence=['O2'],reason=statements[1])
    robust=dict(base,id='C3',new_status='UNRESOLVED',direction='neutral',new_support='ungrounded',identification='UNKNOWN',evidence=['O3'],reason=statements[2])
    a['claim_updates']=[performance,mechanism,robust]
    a['hypothesis_updates'][0].update(evidence=['O2'],reason=statements[1])
    a['outcome']='MIXED_EVIDENCE';a['negative_knowledge']=[memory('C2'),memory('H1')]
    for n in a['negative_knowledge']:n['finding']=statements[1]
    a['reasoning_summary']='Performance improves, the mechanism prediction weakens, and robustness remains unresolved. No whole-experiment success label is justified.'
    a['followups'].append(dict(a['followups'][0],id='N2',target_ids=['C2','H1','H2'],description='Preregister a capacity-matched comparison with proxy Z.',decision_it_resolves='Whether capacity rather than the mechanism explains the gain.'))
    a['followups'].append(dict(a['followups'][0],id='N3',target_ids=['C3'],description='Preregister repeated-seed stress comparisons against matched P.',decision_it_resolves='Whether the stress effect persists within this declared condition.'))
    a['alternatives']=[{'hypothesis_id':'H2','evidence_for':['O1','O2'],'evidence_against':[],'status':'UNRESOLVED','discriminating_next_action':'N2'}]
    set_pivot(args);a['stop_rules'][0]['target_ids']=['C2','H1']
    d=a['decisions'][0]
    a['decisions']=[dict(d,target_ids=[cid],action='CONTINUE',stop_rule_id=None),dict(d,target_ids=['C2','H1'],next_action_id='N2'),dict(d,target_ids=['C3'],action='REDESIGN',stop_rule_id=None,next_action_id='N3')]
    a['repairs']=[{'kind':'scientific_redesign','description':'Add a preregistered stress comparison with repeated seeds.','target_ids':['C3']},
                  {'kind':'abandon_or_narrow_claim','description':'Separate the observed performance gain from the unsupported mechanism attribution.','target_ids':['C2','H1']}]
    refresh(args)
    return args


class OutcomeTests(unittest.TestCase):
    def test_positive_transaction_and_narrative_preservation(self):
        args=fixture(); original=copy.deepcopy(args[0]); result=eo.apply(*args,timestamp=TIMESTAMP)
        self.assertEqual(result['status'],'PASS',result)
        self.assertEqual(args[0],original)
        self.assertEqual(result['state']['narrative_view'],original['narrative_view'])
        self.assertEqual(result['state']['experiments'][-1]['interpretation'],args[2]['reasoning_summary'])
        self.assertTrue(sc.check_state(result['state']).ok)

    def test_valid_negative_is_scientific_evidence(self):
        args=fixture('negative'); self.assertEqual(eo.validate(*args)['status'],'PASS')
        out=eo.apply(*args,timestamp=TIMESTAMP); self.assertEqual(out['status'],'PASS',out)
        x=out['state']['experiments'][-1];self.assertEqual(x['status'],'done')
        self.assertEqual(x['outcome_analysis']['analysis']['outcome'],'NEGATIVE_EVIDENCE')
        self.assertEqual(out['state']['hypotheses'][0]['outcome_status'],'WEAKENED')

    def test_training_crash_cannot_falsify(self):
        args=list(fixture('invalid'));args[2]['hypothesis_updates'][0].update(new_status='FALSIFIED',direction='negative');refresh(args)
        self.assertEqual(eo.validate(*args)['status'],'FAIL')
        valid=eo.apply(*fixture('invalid'),timestamp=TIMESTAMP)
        self.assertEqual(valid['status'],'PASS',valid)
        self.assertEqual(valid['state']['claims'][0]['status'],'ungrounded')

    def test_single_negative_run_not_falsified(self):
        args=list(fixture('negative'));args[2]['hypothesis_updates'][0]['new_status']='FALSIFIED';refresh(args)
        self.assertEqual(eo.validate(*args)['status'],'FAIL')

    def test_implementation_failure_needs_log_evidence(self):
        args=list(fixture('invalid'));self.assertEqual(eo.validate(*args)['status'],'PASS')
        args[2]['failure_attributions'][0]['evidence']=[];refresh(args)
        self.assertIn('UNSUPPORTED_FAILURE_ATTRIBUTION',str(eo.validate(*args)['errors']))

    def test_negative_cannot_be_explained_away_by_unsupported_attribution(self):
        args=list(fixture('negative'));args[2]['failure_attributions'][0]['type']='implementation_failure';refresh(args)
        args[3]['checks']['attributions_grounded'].update(status='FAIL',reason='Logs show no implementation fault; a poor result alone does not establish one.')
        self.assertEqual(eo.validate(*args)['status'],'FAIL')

    def test_confounded_experiment_requires_redesign(self):
        args=list(fixture('negative'));a=args[2]
        for u in a['claim_updates']+a['hypothesis_updates']:
            u.update(new_status='UNRESOLVED',direction='neutral',identification='FAIL')
        a['claim_updates'][0]['new_support']=a['claim_updates'][0]['previous_support']
        a.update(outcome='INCONCLUSIVE',negative_knowledge=[])
        a['failure_attributions'][0]['type']='identifiability_failure';a['decisions'][0]['action']='REDESIGN'
        change_observation(args,'M is unchanged, but both component and training budget changed. The comparison cannot isolate the component.');refresh(args)
        self.assertEqual(eo.validate(*args)['status'],'PASS')

    def test_wrong_metric_is_invalid_evaluation(self):
        args=list(fixture('invalid'));args[1]['execution_status']='completed';args[2]['validity_checks']['execution']['status']='PASS';args[2]['validity_checks']['evaluation']['status']='FAIL';args[2]['failure_attributions'][0]['type']='evaluation_failure'
        change_observation(args,'Training completed. Evaluation used an erroneous metric normalization rather than the preregistered M.');refresh(args)
        self.assertEqual(eo.validate(*args)['status'],'PASS')
        self.assertEqual(eo.validate(*args)['experiment_validity'],'INVALID')

    def test_mixed_results_keep_independent_decisions(self):
        args=mixed_fixture();result=eo.apply(*args,timestamp=TIMESTAMP)
        self.assertEqual(result['status'],'PASS',result)
        self.assertEqual([c.get('outcome_status','UNRESOLVED') for c in result['state']['claims']],['SUPPORTED','WEAKENED','UNRESOLVED'])
        self.assertEqual([d['action'] for d in args[2]['decisions']],['CONTINUE','PIVOT','REDESIGN'])
        args[2]['outcome']='POSITIVE_EVIDENCE';refresh(args)
        self.assertEqual(eo.validate(*args)['status'],'FAIL')

    def test_repeated_negative_can_pivot_and_stop(self):
        first=eo.apply(*fixture('negative'),timestamp=TIMESTAMP)['state']
        for action in ('PIVOT','STOP'):
            args=list(fixture('negative',first,'X2',1));a=args[2]
            for u in a['claim_updates']+a['hypothesis_updates']:u.update(new_status='FALSIFIED',replication_ids=['X1','X2'])
            a['claim_updates'][0]['new_support']='contradicted'
            for m in a['negative_knowledge']:m['ruled_out']=['The preregistered improvement prediction within this scope.']
            set_pivot(args,action)
            out=eo.apply(*args,timestamp=TIMESTAMP);self.assertEqual(out['status'],'PASS',out)
            self.assertEqual(out['state']['claims'][0]['status'],'contradicted')
            self.assertTrue(sc.check_state(out['state']).ok)

    def test_negative_knowledge_and_stop_rules_persist_into_planning(self):
        args=list(fixture('negative'));set_pivot(args);out=eo.apply(*args,timestamp=TIMESTAMP)['state']
        self.assertTrue(eo.constraints(out)[0]['negative_knowledge'])
        new=copy.deepcopy(out['experiments'][-1]);new.update(id='X2',seed=99,code_commit='changedimplementation',status='planned');new.pop('outcome_analysis');out['experiments'].append(new)
        self.assertEqual(eo.check_plan(out,'X2')['status'],'FAIL')
        out['failures'][-1]['stop_rules']=[]
        self.assertFalse(sc.check_state(out).ok)

    def test_deprecated_hypothesis_not_silently_restored(self):
        first=eo.apply(*fixture('negative'),timestamp=TIMESTAMP)['state'];args=list(fixture('negative',first,'X2',1))
        for u in args[2]['claim_updates']+args[2]['hypothesis_updates']:u.update(new_status='FALSIFIED',replication_ids=['X1','X2'])
        args[2]['claim_updates'][0]['new_support']='contradicted';set_pivot(args)
        stopped=eo.apply(*args,timestamp=TIMESTAMP)['state']
        attempt=list(fixture('positive',stopped,'X3',2));self.assertEqual(eo.validate(*attempt)['status'],'FAIL')
        stopped['hypotheses'][0]['outcome_status']='SUPPORTED';self.assertFalse(sc.check_state(stopped).ok)

    def test_provenance_and_sources_retained(self):
        out=eo.apply(*fixture('negative'),timestamp=TIMESTAMP)['state'];r=out['experiments'][-1]['outcome_analysis'];trail=r['audit_trail']
        self.assertEqual(trail['source_result'],eo.digest(r['packet']))
        self.assertEqual(trail['timestamp'],TIMESTAMP);self.assertTrue(trail['state_delta'])
        r['packet']['sources'][0]['content']='changed log'
        self.assertFalse(sc.check_state(out).ok)

    def test_missing_unknown_or_stale_audit_cannot_apply(self):
        args=list(fixture());args[3]=None;self.assertEqual(eo.apply(*args)['status'],'NEEDS_REVIEW')
        args=list(fixture());args[3]['checks']['scope_preserved']['status']='UNKNOWN';self.assertEqual(eo.apply(*args)['status'],'NEEDS_REVIEW')
        args=list(fixture());args[0]['state_version']+=1;self.assertEqual(eo.apply(*args)['status'],'FAIL')

    def test_local_negative_does_not_globally_refute(self):
        args=list(fixture('negative'));s,p,a,_=args
        for u in a['claim_updates']+a['hypothesis_updates']:u.update(scope='Dataset A subgroup',scope_relation='LOCAL')
        a['claim_updates'][0]['new_support']='ungrounded';p['observations'][0]['scope']='Dataset A subgroup';refresh(args)
        out=eo.apply(*args,timestamp=TIMESTAMP);self.assertEqual(out['status'],'PASS',out)
        self.assertEqual(out['state']['claims'][0]['status'],'ungrounded')
        self.assertNotIn('outcome_status',out['state']['hypotheses'][0])

    def test_assurance_before_next_action(self):
        out=eo.apply(*fixture(),timestamp=TIMESTAMP)['state']
        self.assertEqual(eo.decision_gate(out,'X1')['decisions'][0]['action'],'HOLD')
        assurance={'schema':'evidence-outcome-assurance@1','state_digest':eo.digest(out),'analysis_digest':eo.digest(out['experiments'][-1]['outcome_analysis']['analysis']),
                   'checks':{k:{'status':'PASS','reason':'Source-bound post-update audit fixture.'} for k in ('integrity','claim_calibration','reproducibility','stop_rule_compliance')}}
        self.assertEqual(eo.decision_gate(out,'X1',assurance)['decisions'][0]['action'],'CONTINUE')
        assurance['checks']['integrity']['status']='FAIL';self.assertEqual(eo.decision_gate(out,'X1',assurance)['status'],'FAIL')

    def test_terminal_coverage_opt_in_and_legacy_compatibility(self):
        s,p,a,au=fixture();s['experiments'][0].update(status='done',result='Raw result',result_at_state_version=0)
        self.assertFalse(sc.check_state(s).ok)
        s['contract'].pop('outcome_policy')
        for x in s['experiments']:
            x.pop('outcome_protocol');x.pop('hypothesis_targeted')
        self.assertTrue(sc.check_state(s).ok)

    def test_no_rule_deletion_and_no_result_reanalysis(self):
        args=list(fixture('negative'));set_pivot(args);s=eo.apply(*args,timestamp=TIMESTAMP)['state']
        s['experiments'][-1]['outcome_analysis']['analysis']['id']='forged';self.assertFalse(sc.check_state(s).ok)

    def test_readonly_validation_and_explicit_copy_output_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);s,p,a,au=fixture()
            for name,value in [('state',s),('packet',p),('analysis',a),('audit',au)]: (root/(name+'.json')).write_text(json.dumps(value))
            args=[sys.executable,str(Path(__file__).with_name('evidence_outcome.py')),'apply']
            for name in ('state','packet','analysis','audit'):args += ['--'+name,str(root/(name+'.json'))]
            original=(root/'state.json').read_bytes()
            proc=subprocess.run(args+['--output',str(root/'next-state.json')],capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
            self.assertEqual((root/'state.json').read_bytes(),original)
            self.assertTrue(sc.check_file(root/'next-state.json').ok)

    def test_invalid_retry_preserves_previous_scientific_support(self):
        supported=eo.apply(*fixture(),timestamp=TIMESTAMP)['state']
        out=eo.apply(*fixture('invalid',supported,'X2',1),timestamp=TIMESTAMP)
        self.assertEqual(out['status'],'PASS',out)
        self.assertEqual(out['state']['hypotheses'][0]['outcome_status'],'SUPPORTED')
        self.assertEqual(out['state']['claims'][0]['status'],'supported')
        self.assertFalse(out['state']['hypotheses'][0]['scoped_outcomes'][-1]['applied'])

    def test_posthoc_replication_policy_cannot_be_weakened(self):
        out=eo.apply(*fixture('negative'),timestamp=TIMESTAMP)['state']
        out['contract']['outcome_policy']['min_valid_runs']=1
        self.assertFalse(sc.check_state(out).ok)

    def test_forged_invalid_refutation_still_fails_after_digest_refresh(self):
        out=eo.apply(*fixture('invalid'),timestamp=TIMESTAMP)['state']
        r=out['experiments'][-1]['outcome_analysis'];r['analysis']['hypothesis_updates'][0].update(new_status='FALSIFIED',direction='negative')
        r['audit']['analysis_digest']=eo.digest(r['analysis'])
        report=sc.check_state(out)
        self.assertFalse(report.ok)
        self.assertIn('invalid or unverified experiment cannot',str(report.as_dict()))

    def test_stop_rule_ignores_preregistration_timestamp_seed_and_commit(self):
        args=list(fixture('negative'));set_pivot(args);out=eo.apply(*args,timestamp=TIMESTAMP)['state']
        x=copy.deepcopy(out['experiments'][-1]);x.pop('outcome_analysis');x.update(id='X2',seed=88,code_commit='new',status='planned',result='',result_at_state_version=None)
        x['preregistration']['frozen_at_state_version']=1
        out['experiments'].append(x)
        self.assertEqual(eo._check_plan(out,'X2')['status'],'FAIL')

    def test_explicit_grounded_clearance_preserves_historical_rule(self):
        args=list(fixture('negative'));set_pivot(args);out=eo.apply(*args,timestamp=TIMESTAMP)['state']
        x=copy.deepcopy(out['experiments'][-1]);x.pop('outcome_analysis');x.update(id='X2',status='planned',result='',result_at_state_version=None)
        out['experiments'].append(x)
        rule=out['failures'][-1]['stop_rules'][0]
        # The fixture supplies the changed-condition judgment, not its scientific proof.
        x['outcome_plan_clearance']={'schema':'evidence-outcome-plan-clearance@1','memory_digest':eo.digest(eo.constraints(out)),
            'experiment_signature':eo.protocol_signature(x),'reviewed_rules':[{'rule_id':rule['id'],'status':'PASS',
            'changed_condition':'An inspected scientific premise was revised.','evidence_ids':['E1'],'reason':'Source-grounded clearance protocol fixture.'}]}
        self.assertEqual(eo.check_plan(out,'X2')['status'],'PASS')
        self.assertEqual(out['failures'][-1]['stop_rules'][0],rule)
        x['outcome_plan_clearance']['reviewed_rules'][0]['evidence_ids']=[]
        self.assertEqual(eo.check_plan(out,'X2')['status'],'FAIL')

    def test_invalid_retry_requires_fix_clearance(self):
        out=eo.apply(*fixture('invalid'),timestamp=TIMESTAMP)['state']
        x=copy.deepcopy(out['experiments'][-1]);x.pop('outcome_analysis');x.update(id='X2',parent='X1',status='planned',result='',result_at_state_version=None,seed=1)
        out['experiments'].append(x)
        gate=eo._check_plan(out,'X2')
        self.assertEqual(gate['status'],'FAIL')
        self.assertEqual(gate['blocked_by'][0]['kind'],'retry_fix')

    def test_uncertainty_partial_reduction_and_invalid_closure(self):
        args=list(fixture());old=args[0]['uncertainties'][0]
        args[2]['uncertainty_updates']=[{'id':old['id'],'previous_level':'high','new_level':'medium',
             'previous_status':'open','new_status':'open','evidence':['O1'],'reason':'The identifying comparison narrows the unresolved range.'}]
        refresh(args);out=eo.apply(*args,timestamp=TIMESTAMP)
        self.assertEqual(out['status'],'PASS',out)
        self.assertEqual(out['state']['uncertainties'][0]['uncertainty'],'medium')
        self.assertEqual(out['state']['uncertainties'][0]['status'],'open')
        invalid=list(fixture('invalid'));invalid[2]['uncertainty_updates']=args[2]['uncertainty_updates'];refresh(invalid)
        self.assertEqual(eo.validate(*invalid)['status'],'FAIL')

    def test_local_evidence_cannot_disappear_silently(self):
        args=list(fixture('negative'))
        for u in args[2]['claim_updates']+args[2]['hypothesis_updates']:u.update(scope='subgroup',scope_relation='LOCAL')
        args[2]['claim_updates'][0]['new_support']='ungrounded';args[1]['observations'][0]['scope']='subgroup';refresh(args)
        out=eo.apply(*args,timestamp=TIMESTAMP)['state']
        out['evidence'].pop()
        self.assertFalse(sc.check_state(out).ok)

    def test_wrong_metric_replicate_does_not_count_toward_falsification(self):
        first=eo.apply(*fixture('negative'),timestamp=TIMESTAMP)['state']
        args=list(fixture('negative',first,'X2',1));x=args[0]['experiments'][-1];x['metric']='A different outcome'
        args[1]['experiment_digest']=eo.digest(x)
        for u in args[2]['claim_updates']+args[2]['hypothesis_updates']:u.update(new_status='FALSIFIED',replication_ids=['X1','X2'])
        args[2]['claim_updates'][0]['new_support']='contradicted';set_pivot(args)
        self.assertEqual(eo.validate(*args)['status'],'FAIL')

    def test_duplicate_failure_memory_cannot_shadow_removed_knowledge(self):
        args=list(fixture('negative'));set_pivot(args);out=eo.apply(*args,timestamp=TIMESTAMP)['state']
        shadow=copy.deepcopy(out['failures'][-1]);shadow['id']='F99';out['failures'].append(shadow);out['experiments'][-1]['known_flaws'].append('F99')
        self.assertFalse(sc.check_state(out).ok)

    def test_history_adoption_returns_unaccepted_backlog_state(self):
        args=list(fixture());s=args[0]
        old=copy.deepcopy(s['experiments'][0]);old.update(id='X-old',status='done',result='Old raw outcome',result_at_state_version=0)
        s['experiments'].append(old);refresh(args)
        result=eo.apply(*args,timestamp=TIMESTAMP)
        self.assertEqual(result['status'],'NEEDS_REVIEW',result)
        self.assertIn('proposed_state',result)
        self.assertFalse(sc.check_state(result['proposed_state']).ok)

    def test_old_decision_is_held_after_later_target_assessment(self):
        first=eo.apply(*fixture(),timestamp=TIMESTAMP)['state']
        later=eo.apply(*fixture('negative',first,'X2',1),timestamp=TIMESTAMP)['state']
        old=later['experiments'][0]['outcome_analysis']['analysis']
        assurance={'schema':'evidence-outcome-assurance@1','state_digest':eo.digest(later),'analysis_digest':eo.digest(old),
                   'checks':{k:{'status':'PASS','reason':'Protocol fixture.'} for k in ('integrity','claim_calibration','reproducibility','stop_rule_compliance')}}
        self.assertEqual(eo.decision_gate(later,'X1',assurance)['decisions'][0]['action'],'HOLD')

    def test_executed_result_cannot_bypass_stopped_plan(self):
        args=list(fixture('negative'));set_pivot(args);first=eo.apply(*args,timestamp=TIMESTAMP)['state']
        attempt=list(fixture('negative',first,'X2',1))
        self.assertIn('planning gate',str(eo.validate(*attempt)['errors']))

    def test_removing_policy_does_not_grandfather_outcome_history(self):
        out=eo.apply(*fixture('negative'),timestamp=TIMESTAMP)['state']
        out['contract'].pop('outcome_policy')
        self.assertFalse(sc.check_state(out).ok)

    def test_alternative_cannot_gain_support_without_assessment(self):
        args=mixed_fixture();args[2]['alternatives'][0]['status']='SUPPORTED';refresh(args)
        self.assertEqual(eo.validate(*args)['status'],'FAIL')
        args=mixed_fixture();args[2]['alternatives'][0]['discriminating_next_action']='missing';refresh(args)
        self.assertEqual(eo.validate(*args)['status'],'FAIL')

    def test_followup_cannot_target_invented_hypothesis(self):
        args=list(fixture());args[2]['followups'][0]['target_ids']=['H999'];refresh(args)
        self.assertEqual(eo.validate(*args)['status'],'FAIL')

    def test_pending_result_lifecycle_receipt_can_finish_atomically(self):
        args=list(fixture());args[0]['experiments'][-1]['result_pending']=True
        args[1]['experiment_digest']=eo.digest(args[0]['experiments'][-1]);refresh(args)
        out=eo.apply(*args,timestamp=TIMESTAMP)
        self.assertEqual(out['status'],'PASS',out)
        self.assertNotIn('result_pending',out['state']['experiments'][-1])

    def test_copy_output_does_not_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,value in zip(('state','packet','analysis','audit'),fixture()): (root/(name+'.json')).write_text(json.dumps(value))
            output=root/'next.json';output.write_text('original unrelated content')
            args=[sys.executable,str(Path(__file__).with_name('evidence_outcome.py')),'apply']
            for name in ('state','packet','analysis','audit'):args+=['--'+name,str(root/(name+'.json'))]
            proc=subprocess.run(args+['--output',str(output)],capture_output=True,text=True)
            self.assertNotEqual(proc.returncode,0)
            self.assertEqual(output.read_text(),'original unrelated content')

    def test_observation_scope_cannot_be_widened_in_update(self):
        args=list(fixture('negative'));args[1]['observations'][0]['scope']='Dataset A subgroup';refresh(args)
        self.assertEqual(eo.validate(*args)['status'],'FAIL')

    def test_original_scientific_gate_cannot_be_repaired_incidentally(self):
        args=list(fixture());args[0]['claims'][0].pop('falsifier');refresh(args)
        self.assertEqual(eo.apply(*args)['status'],'FAIL')

    def test_failure_attribution_memory_is_source_bound(self):
        out=eo.apply(*fixture('invalid'),timestamp=TIMESTAMP)['state']
        out['failures'][-1]['failure_attributions'][0]['type']='hypothesis_failure'
        self.assertFalse(sc.check_state(out).ok)

    def test_forged_or_reordered_scoped_history_cannot_restore_support(self):
        first=eo.apply(*fixture(),timestamp=TIMESTAMP)['state']
        out=eo.apply(*fixture('negative',first,'X2',1),timestamp=TIMESTAMP)['state']
        h=out['hypotheses'][0];original=copy.deepcopy(h)
        forged=copy.deepcopy(h['scoped_outcomes'][-1]);forged['status']='SUPPORTED'
        h['scoped_outcomes'].append(forged);h['outcome_status']='SUPPORTED'
        self.assertFalse(sc.check_state(out).ok)
        h.clear();h.update(original);h['scoped_outcomes'].reverse();h['outcome_status']='SUPPORTED'
        self.assertFalse(sc.check_state(out).ok)

    def test_claim_line_stop_covers_descendant_claim(self):
        args=list(fixture('negative'));set_pivot(args)
        args[2]['stop_rules'][0]['kind']='claim_line';refresh(args)
        out=eo.apply(*args,timestamp=TIMESTAMP)['state']
        parent=out['claims'][0];child=copy.deepcopy(parent);child.update(id='C2',parent=parent['id'],subclaims=[],status='ungrounded',supporting_evidence=[],refuting_evidence=[],known_flaws=[])
        child.pop('outcome_status');child.pop('scoped_outcomes');parent['subclaims'].append('C2');out['claims'].append(child)
        x=copy.deepcopy(out['experiments'][-1]);x.pop('outcome_analysis');x.update(id='X2',claim_targeted=['C2'],hypothesis_targeted=[],status='planned',result='',result_at_state_version=None)
        out['experiments'].append(x)
        self.assertEqual(eo._check_plan(out,'X2')['status'],'FAIL')

    def test_negative_evidence_does_not_upgrade_an_ungrounded_claim(self):
        out=eo.apply(*fixture('negative'),timestamp=TIMESTAMP)['state']
        self.assertEqual(out['claims'][0]['status'],'ungrounded')
        self.assertEqual(out['claims'][0]['outcome_status'],'WEAKENED')
        supported=eo.apply(*fixture(),timestamp=TIMESTAMP)['state']
        weakened=eo.apply(*fixture('negative',supported,'X2',1),timestamp=TIMESTAMP)['state']
        self.assertEqual(weakened['claims'][0]['status'],'partially-supported')

    def test_next_action_must_resolve_the_decision_targets(self):
        args=list(fixture());args[2]['followups'][0]['target_ids']=['H2'];refresh(args)
        self.assertEqual(eo.validate(*args)['status'],'FAIL')

    def test_malformed_artifact_fail_closed(self):
        for value in (None,[],{},True):
            self.assertEqual(eo.validate({},value,value,value)['status'],'FAIL')
            self.assertEqual(eo.apply({},value,value,value)['status'],'FAIL')


class OutcomeReleaseTests(unittest.TestCase):
    def test_shipped_examples_cover_actual_transitions(self):
        import release_check
        self.assertTrue(release_check.step_evidence_outcome()[0])

    def test_release_rejects_mutated_source_even_with_positive_label(self):
        import release_check
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            target=root/'examples'/'evidence-outcome';target.mkdir(parents=True)
            source=release_check.ROOT/'examples'/'evidence-outcome'
            for path in source.glob('*.json'):(target/path.name).write_bytes(path.read_bytes())
            path=target/'positive.json';case=json.loads(path.read_text())
            case['packet']['sources'][0]['content']='Training actually crashed.'
            path.write_text(json.dumps(case))
            with patch.object(release_check,'ROOT',root):
                self.assertFalse(release_check.step_evidence_outcome()[0])


if __name__=='__main__':unittest.main()
