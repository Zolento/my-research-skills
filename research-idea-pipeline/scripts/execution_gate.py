#!/usr/bin/env python3
"""Additive PEIG/AALG contract checks. No experiments, model calls or state writes."""
from __future__ import annotations

import json
import math
from pathlib import Path

import evidence_outcome as eo

ROOT = Path(__file__).resolve().parent.parent
MODES = ('formal', 'pilot', 'exploratory', 'sanity', 'calibration')
DEFAULT_POLICY = {'max_preflight_revisions': 3, 'max_equivalent_diagnostics': 2,
                  'max_pilot_runs': 1, 'max_pilot_hours': 2, 'receipt_ttl_seconds': 900}
FAIR = ('compute_hours', 'data_split', 'optimization.tuning_trials')
CAPACITY = ('trainable_parameters', 'training_dof')
OPTIMIZATION = ('optimizer', 'lr', 'schedule', 'batch', 'steps', 'tuning_trials', 'diagnostics')


def schema_errors(value, name):
    """Validate the small bundled JSON Schema vocabulary without optional dependencies."""
    schema = json.loads((ROOT / 'schemas' / name).read_text(encoding='utf-8'))
    errors = []
    def walk(v, s, path):
        types = s.get('type', [])
        if isinstance(types, str): types = [types]
        valid = {'object': isinstance(v, dict), 'array': isinstance(v, list),
                 'string': isinstance(v, str), 'boolean': type(v) is bool,
                 'null': v is None, 'integer': type(v) is int,
                 'number': type(v) in (int, float) and math.isfinite(v)}
        if types and not any(valid[t] for t in types):
            errors.append(path + ': invalid type'); return
        if 'const' in s and v != s['const']: errors.append(path + ': invalid schema version')
        if 'enum' in s and v not in s['enum']: errors.append(path + ': invalid enum')
        if isinstance(v, str) and len(v.strip()) < s.get('minLength', 0): errors.append(path + ': empty text')
        if type(v) in (int, float):
            if not math.isfinite(v): errors.append(path + ': nonfinite number')
            if v < s.get('minimum', -math.inf) or v <= s.get('exclusiveMinimum', -math.inf): errors.append(path + ': below minimum')
        if isinstance(v, dict):
            props = s.get('properties', {})
            for k in s.get('required', []):
                if k not in v: errors.append(path + '.' + k + ': required')
            for k, child in v.items():
                if k in props: walk(child, props[k], path + '.' + k)
                elif s.get('additionalProperties') is False: errors.append(path + '.' + k + ': unknown field')
                elif isinstance(s.get('additionalProperties'), dict): walk(child, s['additionalProperties'], path + '.' + k)
        if isinstance(v, list):
            if len(v) < s.get('minItems', 0): errors.append(path + ': too few items')
            if s.get('uniqueItems') and len({eo.digest(x) for x in v}) != len(v): errors.append(path + ': duplicates')
            for i, child in enumerate(v): walk(child, s.get('items', {}), f'{path}[{i}]')
    walk(value, schema, name)
    return errors


def at(obj, path):
    for key in path.split('.'):
        if not isinstance(obj, dict) or key not in obj: raise ValueError('unknown controlled variable: ' + path)
        obj = obj[key]
    return obj


def source_observation(e):
    source = e.get('diagnostic_observation')
    if isinstance(source, dict) and set(source) == {'kind','location','content','digest'} and all(eo.text(v) for v in source.values()) and source['kind'] in ('log','metric','result') and source['digest'] == eo.digest(source['content']):
        return {'kind':source['kind'], 'content':source['content']}
    return None


def evidence_snapshot(state):
    """Only source-bound observations; IDs, U bookkeeping and document labels do not count."""
    records = []
    for e in state.get('evidence', []):
        if e.get('validity', {}).get('status') == 'valid' and e.get('epistemic_status') in ('Observed','Supported') and e.get('verification_tier') in eo.TIERS[1:]:
            source = source_observation(e)
            if source: records.append(source)
    for x in state.get('experiments', []):
        if x.get('outcome_analysis'):
            packet = x['outcome_analysis']['packet']
            records.extend({'kind':s['kind'], 'content':s['content']} for s in packet['sources'] if s['kind'] in ('log','metric','result'))
    return eo.digest(sorted({eo.digest(r) for r in records}))


def target_lineage(state, targets):
    claims, hypotheses = eo.index(state,'claims'), eo.index(state,'hypotheses')
    visited = set(); pending = list(targets)
    while pending:
        target = pending.pop()
        if target in visited: continue
        visited.add(target)
        parent = claims.get(target,{}).get('parent')
        pending.extend(([parent] if parent else []) + hypotheses.get(target,{}).get('parents',[]))
    return sorted(visited)


def target_roots(state, targets):
    claims, hypotheses = eo.index(state,'claims'), eo.index(state,'hypotheses')
    return [t for t in target_lineage(state,targets) if not claims.get(t,{}).get('parent') and not hypotheses.get(t,{}).get('parents')]


def risks(state, claims):
    selected = []
    claims = target_lineage(state,claims)
    for r in state.get('assurance', []) + state.get('uncertainties', []):
        targets = r.get('target', [])
        if isinstance(targets, str): targets = [targets]
        if set(targets) & set(claims):
            # Untyped relevant attacks cannot disappear by omitting severity.
            if r in state.get('assurance', []) or r.get('importance') in ('critical', 'high'):
                selected.append(r)
    return selected


def design_projection(protocol):
    """Ignore arm/control labels and narrative; preserve executable scientific variables."""
    arms = {a['id']: {k: v for k, v in a.items() if k not in ('id', 'role')} for a in protocol['arms']}
    comparisons = []
    for c in protocol['comparisons']:
        comparisons.append({'arms': sorted([eo.digest(arms[c['left']]), eo.digest(arms[c['right']])]),
                            'controlled': sorted(c['controlled_variables']), 'contrast': sorted(c['contrast_variables'])})
    return {'arms': sorted(eo.digest(a) for a in arms.values()), 'comparisons': sorted(eo.digest(c) for c in comparisons),
            'dose_levels': protocol['intervention']['dose_levels'], 'observable': protocol['intervention']['observable'],
            'evaluation': {k: v for k, v in protocol['evaluation'].items() if k != 'seeds'}}


def review_digest(protocol):
    return eo.digest({k: v for k, v in protocol.items() if k not in ('scientific_review', 'human_exception')})


def family_key(state, experiment):
    targets = target_roots(state,experiment['claim_targeted'])
    protocol = experiment.get('execution_protocol')
    exploration = None
    if not targets and protocol and not schema_errors(protocol,'preflight-protocol.schema.json'):
        exploration = {'mode':protocol['mode'],'design':design_projection(protocol)}
    return eo.digest({'claim_line':targets, 'exploration':exploration, 'evidence':evidence_snapshot(state)})


def _comparison_errors(c, arms, competitors):
    errors = []
    if c['left'] == c['right'] or c['left'] not in arms or c['right'] not in arms:
        return [c['id'] + ': comparison needs two existing distinct arms']
    left, right = arms[c['left']], arms[c['right']]
    for field in c['controlled_variables']:
        try:
            if at(left, field) != at(right, field): errors.append(c['id'] + ': unequal control ' + field)
        except ValueError as exc: errors.append(str(exc))
    for field in c['contrast_variables']:
        try:
            if at(left, field) == at(right, field): errors.append(c['id'] + ': contrast does not differ: ' + field)
        except ValueError as exc: errors.append(str(exc))
    if set(c['contrast_variables']) & set(c['controlled_variables']): errors.append(c['id'] + ': contrast/control overlap')
    if any(p['hypothesis_id'] not in competitors for p in c['predictions']) or len({p['hypothesis_id'] for p in c['predictions']}) < 2 or len({p['observation'] for p in c['predictions']}) < 2 or len({p['decision'] for p in c['predictions']}) < 2:
        errors.append(c['id'] + ': predictions must distinguish existing competitors and research decisions')
    # Every changed scientific variable must be exposed as a contrast, never hidden.
    def flatten(v, prefix=''):
        if isinstance(v, dict):
            return {k2: v2 for k, child in v.items() for k2, v2 in flatten(child, prefix + k + '.').items()}
        return {prefix[:-1]: v}
    l, r = flatten({k: v for k, v in left.items() if k not in ('id', 'role')}), flatten({k: v for k, v in right.items() if k not in ('id', 'role')})
    for field in set(l) | set(r):
        if l.get(field) != r.get(field) and not any(field == p or field.startswith(p + '.') for p in c['contrast_variables']):
            errors.append(c['id'] + ': undeclared changed variable ' + field)
    return errors


def peig(state, experiment_id):
    """Finite design decision; it never generates additional tests or documents."""
    errors = []
    try:
        x = eo.index(state, 'experiments')[experiment_id]
        p = x.get('execution_protocol')
        if p is None: return {'status': 'HOLD', 'errors': ['MISSING_PROTOCOL: historical execution is not grandfathered']}
        errors.extend(schema_errors(p, 'preflight-protocol.schema.json'))
        if errors: return {'status': 'HOLD', 'errors': errors}
        prereg = x.get('preregistration')
        if not isinstance(prereg, dict) or not eo.integer(prereg.get('frozen_at_state_version')) or prereg['frozen_at_state_version'] > state['state_version'] or not prereg.get('outcomes'):
            errors.append('MISSING_PREREGISTRATION: freeze outcomes before execution')
        if not isinstance(state.get('contract',{}).get('outcome_policy'),dict): errors.append('OUTCOME_POLICY_REQUIRED: adopt source-grounded outcome handling')
        if x.get('execution_blocked_by'): errors.append('STOP_RULE: explicit execution hold')
        plan = eo._check_plan(state, experiment_id)
        if plan['status'] != 'PASS': errors.append('STOP_RULE: ' + eo.digest(plan))
        formal = p['mode'] == 'formal'
        if x['stage'] in ('X3', 'X4', 'X5') or x['stage'] == 'X6' and x['claim_targeted']:
            if p['mode'] not in ('formal', 'pilot'): errors.append('STAGE_PERMISSION: claim validation requires formal or calibration pilot')
        elif formal: errors.append('STAGE_PERMISSION: X1/X2/exploration cannot confirm claims')
        if p['claims'] != x['claim_targeted']: errors.append('TARGET_MISMATCH: protocol must bind exact claim targets')
        if formal and set(p['competitors']) != set(x.get('hypothesis_targeted', []) + x['alternative_targeted']): errors.append('COMPETITOR_BINDING_MISMATCH')
        if formal and isinstance(prereg, dict):
            registered = {o['id']:o for o in prereg.get('outcomes', [])}
            if any(o['preregistration_id'] not in registered or registered[o['preregistration_id']]['observation'] != o['criterion'] for o in p['outcomes'].values()): errors.append('OUTCOME_PREREGISTRATION_MISMATCH')
        if not set(p['competitors']) <= set(eo.index(state, 'hypotheses')): errors.append('MISSING_COMPETITOR: hypotheses must exist')
        if p['evaluation']['data_split'] != x['data_split'] or p['evaluation']['metric'] != x['metric'] or x['seed'] not in p['evaluation']['seeds']:
            errors.append('EVALUATION_MISMATCH: split/metric/seed differs')
        arms = {a['id']: a for a in p['arms']}; comparisons = {c['id']: c for c in p['comparisons']}
        if len(arms) != len(p['arms']) or len(comparisons) != len(p['comparisons']): errors.append('DUPLICATE_DESIGN_ID')
        for c in p['comparisons']: errors.extend(_comparison_errors(c, arms, p['competitors']))
        if formal:
            if len(arms) < 2 or not comparisons or len(p['competitors']) < 2 or not p['claims']: errors.append('MISSING_IDENTIFYING_COMPARISON')
            if not any(a['role'] == 'method' for a in arms.values()) or not any(a['role'] in ('baseline', 'control') for a in arms.values()): errors.append('MISSING_VALID_COMPARATOR')
            for c in comparisons.values():
                if c['left'] in arms and c['right'] in arms:
                    for field in FAIR:
                        if at(arms[c['left']], field) != at(arms[c['right']], field): errors.append('UNFAIR_BUDGET: ' + field)
            if not p['intervention']['frozen'] or len(set(p['intervention']['dose_levels'])) < 2 or 0 not in p['intervention']['dose_levels']:
                errors.append('UNFROZEN_DOSE: need frozen observable dose including zero')
            if len(set(p['evaluation']['seeds'])) != len(p['evaluation']['seeds']): errors.append('DUPLICATE_SEEDS')
            if sum(a['compute_hours'] for a in arms.values()) > p['budget_hours']: errors.append('BUDGET_MISMATCH: arms exceed frozen formal budget')
        for arm in arms.values():
            if arm['data_split'] != p['evaluation']['data_split'] or arm['intervention']['dose'] not in p['intervention']['dose_levels']: errors.append('ARM_PROTOCOL_MISMATCH')
        inventory = risks(state, p['claims'] + x.get('hypothesis_targeted', []) + x.get('alternative_targeted', []))
        risk_ids = [r.get('id') for r in inventory]
        if any(not eo.text(r.get('id')) or r.get('severity', r.get('importance')) not in ('critical','high','medium','low') or not eo.text(r.get('risk_type')) for r in inventory): errors.append('UNTYPED_R7_RISK: id/severity/risk_type required')
        controls = {r['risk_id']: r for r in p['risk_controls']}
        if len(controls) != len(p['risk_controls']) or set(controls) != set(risk_ids): errors.append('RISK_TRACEABILITY: every relevant risk needs exactly one disposition')
        # Method capacity increases require capacity controls even if R7 omitted the risk.
        capacity_diff = len({(a['trainable_parameters'], tuple(sorted(a['training_dof']))) for a in arms.values()}) > 1
        if formal and capacity_diff and not any(r.get('risk_type') == 'capacity' for r in inventory): errors.append('UNREGISTERED_CAPACITY_RISK: R7 must register the alternative')
        unresolved = []
        for risk in inventory:
            control = controls.get(risk.get('id'))
            if not control: continue
            disposition = control['disposition']
            if disposition == 'UNIDENTIFIABLE': unresolved.append(risk['id']); continue
            if disposition == 'SCOPE_LIMIT':
                claims = eo.index(state, 'claims'); idx = control['repair_index']
                targets = [risk['target']] if isinstance(risk['target'], str) else risk['target']
                if idx < 0 or idx >= len(state['repairs']) or state['repairs'][idx]['disposition'] != 'NARROW_SCOPE' or not set(targets) <= set(state['repairs'][idx].get('targets', [])) or any(claims[t]['scope'] != control['limited_scope'] for t in targets) or control['limited_scope'] == control['excluded_scope']:
                    errors.append('INVALID_SCOPE_LIMIT: explicit scoped claim and R10 repair required')
                continue
            ids = control['comparison_ids']
            if not ids or any(i not in comparisons for i in ids): errors.append('MISSING_RISK_CONTROL: ' + risk['id']); continue
            required = CAPACITY if risk['risk_type'] == 'capacity' else FAIR if risk['risk_type'] == 'fairness' else tuple('optimization.' + k for k in OPTIMIZATION) if risk['risk_type'] == 'optimization' else ()
            if required and not any((risk['risk_type'] != 'capacity' or 'method' in (arms[comparisons[i]['left']]['role'],arms[comparisons[i]['right']]['role'])) and all(at(arms[comparisons[i]['left']], f) == at(arms[comparisons[i]['right']], f) and any(f == v or f.startswith(v + '.') for v in comparisons[i]['controlled_variables']) for f in required) for i in ids if comparisons[i]['left'] in arms and comparisons[i]['right'] in arms):
                errors.append('INEFFECTIVE_RISK_CONTROL: ' + risk['id'])
        review = p['scientific_review']
        reviewed = review['status'] == 'PASS' and review['design_digest'] == review_digest(p)
        if formal and not reviewed: errors.append('SCIENTIFIC_REVIEW: disputed or unreviewed design gives finite HOLD')
        if formal and unresolved: errors.append('UNIDENTIFIABLE: ' + ','.join(unresolved))
        if p['human_exception'] is not None and formal: errors.append('HUMAN_EXCEPTION: cannot masquerade as formal PASS')
        if not formal:
            pilot = p['pilot']
            if len({v['observation'] for v in pilot['decisions']}) < 2 or len({v['decision'] for v in pilot['decisions']}) < 2: errors.append('PILOT_NO_DECISION_VALUE')
            if p['mode'] == 'sanity' and x['stage'] != 'X1' or p['mode'] == 'calibration' and x['stage'] != 'X2': errors.append('STAGE_PERMISSION')
        return {'status': 'HOLD' if errors else 'PASS' if formal else 'PILOT_ONLY', 'errors': errors,
                'unresolved_risks': unresolved, 'design_digest': review_digest(p),
                'budget_hours': p['budget_hours'] if formal else p['pilot']['max_hours']}
    except (KeyError, ValueError, TypeError) as exc:
        return {'status': 'HOLD', 'errors': ['INVALID_PROTOCOL: ' + str(exc)]}


def diagnostic_digest(d, state=None):
    design = {k: v for k, v in d.items() if k != 'scientific_review'}
    if state is not None:
        x = eo.index(state,'experiments')[d['experiment_id']]
        h = eo.index(state,'hypotheses')[d['hypothesis_id']]
        design = {'diagnostic':design, 'protocol':review_digest(x['execution_protocol']),
                  'hypothesis':{k:h.get(k) for k in ('statement','falsifier','structural_signature')},
                  'evidence_snapshot':evidence_snapshot(state)}
    return eo.digest(design)


def diagnostic_check(state, d, history, policy):
    errors = schema_errors(d, 'diagnostic-protocol.schema.json')
    if errors: return {'status': 'HOLD', 'errors': errors, 'decision': 'REDESIGN'}
    try:
        x = eo.index(state, 'experiments')[d['experiment_id']]
        h = eo.index(state, 'hypotheses')[d['hypothesis_id']]
        if not set(d['claim_ids']) <= set(x['claim_targeted']): errors.append('DIAGNOSTIC_TARGET_MISMATCH')
        inventory = risks(state,d['claim_ids'] + x.get('hypothesis_targeted',[]) + x.get('alternative_targeted',[]))
        if not d['risk_ids'] and inventory: errors.append('DIAGNOSTIC_RISK_BINDING_REQUIRED')
        if not set(d['risk_ids']) <= {r.get('id') for r in inventory}: errors.append('DIAGNOSTIC_RISK_MISMATCH')
        evidence = eo.index(state, 'evidence')
        bound_observations = {e['id'] for e in state.get('evidence',[]) if source_observation(e)} | {e['id'] for e in state.get('evidence',[]) if e.get('outcome_observations') and any(old.get('outcome_analysis') and old['id'] in e.get('depends_on',[]) for old in state['experiments'])}
        for eid in d['evidence_ids'] + d['generating_evidence_ids']:
            e = evidence.get(eid)
            if not e or e.get('validity', {}).get('status') != 'valid' or e.get('epistemic_status') not in ('Observed','Supported') or e.get('verification_tier') not in eo.TIERS[1:]: errors.append('NO_OBSERVED_EVIDENCE: ' + eid)
            if eid not in bound_observations: errors.append('NO_SOURCE_BOUND_EVIDENCE: ' + eid)
        if d['origin'] == 'preregistered' and diagnostic_digest(d,state) not in x.get('preregistration',{}).get('diagnostic_protocols',[]): errors.append('POST_HOC_IS_EXPLORATORY')
        if d['origin'] == 'preregistered' and (d['generating_evidence_ids'] or any(evidence[e].get('depends_on') == [x['id']] for e in d['evidence_ids'] if e in evidence)):
            errors.append('POST_HOC_IS_EXPLORATORY')
        if d['origin'] == 'preregistered' and d['hypothesis_id'] not in x.get('hypothesis_targeted', []): errors.append('HYPOTHESIS_NOT_PREREGISTERED')
        if d['independent_confirmation'] and (not d['evidence_ids'] or set(d['evidence_ids']) & set(d['generating_evidence_ids']) or any(x['id'] in evidence[e].get('depends_on', []) for e in d['evidence_ids'] if e in evidence)):
            errors.append('SAME_RESULT_NOT_INDEPENDENT_CONFIRMATION')
        generating_sources = {eo.digest(source_observation(evidence[e])) for e in d['generating_evidence_ids'] if e in evidence and source_observation(evidence[e])}
        confirmation_sources = {eo.digest(source_observation(evidence[e])) for e in d['evidence_ids'] if e in evidence and source_observation(evidence[e])}
        if d['independent_confirmation'] and generating_sources & confirmation_sources: errors.append('SAME_RESULT_NOT_INDEPENDENT_CONFIRMATION')
        preds = d['predictions']
        if any(v['hypothesis_id'] not in eo.index(state, 'hypotheses') for v in preds) or len({v['hypothesis_id'] for v in preds}) < 2 or len({v['observation'] for v in preds}) < 2 or len({v['decision'] for v in preds}) < 2:
            errors.append('NO_DISCRIMINATION_OR_DECISION_VALUE')
        if d['hypothesis_id'] not in {v['hypothesis_id'] for v in preds}: errors.append('NEW_HYPOTHESIS_NEEDS_ITS_OWN_PREDICTIONS')
        p = x.get('execution_protocol')
        if p and d['hypothesis_id'] not in p['competitors']: errors.append('NEW_HYPOTHESIS_NEEDS_INDEPENDENT_PROTOCOL')
        if not p or schema_errors(p, 'preflight-protocol.schema.json'): errors.append('NEW_HYPOTHESIS_NEEDS_INDEPENDENT_PROTOCOL')
        key = eo.digest({'claims': target_roots(state,d['claim_ids']), 'risks': sorted({r.get('risk_type') for r in inventory if r.get('id') in d['risk_ids']}), 'evidence': evidence_snapshot(state),
                         'design': design_projection(p) if p else None})
        attempts = sum(e.get('kind') == 'diagnosis' and e.get('key') == key for e in history)
        review = d['scientific_review']
        if review['status'] != 'PASS' or review['design_digest'] != diagnostic_digest(d,state): errors.append('DIAGNOSTIC_REVIEW_REQUIRED')
        if errors: return {'status': 'HOLD', 'errors': errors, 'key': key, 'decision': 'REDESIGN'}
        if eo._check_plan(state, x['id'])['status'] != 'PASS' or x.get('execution_blocked_by'):
            return {'status': 'PIVOT_RECOMMENDED', 'errors': ['STOP_RULE_ACTIVE'], 'key': key, 'decision': 'PIVOT', 'next_phase': 'R14'}
        if attempts >= policy['max_equivalent_diagnostics']:
            return {'status': 'STOP_DIAGNOSIS', 'errors': ['EQUIVALENT_DIAGNOSIS_LIMIT'], 'key': key, 'decision': 'REDESIGN', 'trigger': 'T8', 'next_phase': 'R5.1→R3/R6'}
        return {'status': 'PASS', 'errors': [], 'key': key, 'attempt': attempts + 1, 'decision': d['fallback']}
    except (KeyError, ValueError, TypeError) as exc:
        return {'status': 'HOLD', 'errors': ['INVALID_DIAGNOSIS: ' + str(exc)], 'decision': 'REDESIGN'}


def state_errors(state):
    errors = []
    for e in state.get('evidence', []):
        if e.get('diagnostic_observation') is not None and source_observation(e) is None: errors.append(e['id'] + ': source observation content/digest required')
    for x in state.get('experiments', []):
        p = x.get('execution_protocol')
        if p is None: continue
        errors.extend(x['id'] + ': ' + e for e in schema_errors(p, 'preflight-protocol.schema.json'))
        execution = x.get('execution_record')
        if x['status'] in ('running','done','failed'):
            if not isinstance(execution, dict) or set(execution) != {'receipt','launch_seal','dry_run'}:
                errors.append(x['id'] + ': executed protocol requires managed execution record')
            else:
                if type(execution['dry_run']) is not bool: errors.append(x['id'] + ': execution dry_run flag must be boolean')
                binding = execution['receipt']['binding']
                design = {k: x.get(k) for k in ('stage','claim_targeted','hypothesis_targeted','alternative_targeted','code_commit','data_split','seed','metric','outcome_protocol')}
                if binding.get('protocol_digest') != eo.digest(p) or binding.get('preregistration_digest') != eo.digest(x['preregistration']) or binding.get('experiment_id') != x['id'] or binding.get('experiment_design') != design:
                    errors.append(x['id'] + ': executed/preregistered contents differ from receipt')
                if execution['dry_run']: errors.append(x['id'] + ': dry-run is telemetry, never scientific evidence')
        elif execution is not None: errors.append(x['id'] + ': planned experiment cannot contain execution result')
        r = x.get('outcome_analysis')
        if r:
            old = eo.index(r['validation_context'], 'experiments').get(x['id'], {})
            if old.get('execution_protocol') != p: errors.append(x['id'] + ': executed protocol is immutable')
    for i, repair in enumerate(state.get('repairs', [])):
        if repair.get('diagnostic_protocol') is not None:
            errors.extend(f'repairs[{i}]: ' + e for e in schema_errors(repair['diagnostic_protocol'], 'diagnostic-protocol.schema.json'))
    return errors


def actual_eig(receipt):
    """Existing rating semantics projected from immutable source transaction."""
    changes = receipt['audit_trail']['state_delta']; a = receipt['analysis']
    claim = []; hypo = []; uncertainty = []; new = []
    for delta in changes:
        before, after = delta['before'], delta['after']; kind = delta['collection']
        if kind == 'claims' and before and before['status'] != after['status']: claim.append({'id': delta['id'], 'from': before['status'], 'to': after['status']})
        if kind == 'hypotheses' and before and before['status'] != after['status']: hypo.append({'id': delta['id'], 'from': before['status'], 'to': after['status']})
        if kind == 'uncertainties':
            if before is None: new.append(delta['id'])
            elif before['uncertainty'] != after['uncertainty'] or before['status'] != after['status']: uncertainty.append({'id': delta['id'], 'level_from': before['uncertainty'], 'level_to': after['uncertainty'], 'status_from': before['status'], 'status_to': after['status']})
    unexpected = next((len(v['after'].get('unexpected', [])) for v in changes if v['collection'] == 'experiments' and v['id'] == a['experiment_id']), 0)
    delta = dict(claim_status_changes=claim,uncertainty_changes=uncertainty,hypothesis_status_changes=hypo,new_uncertainties=new,unexpected_observations=unexpected)
    if claim or any(v['status_to'] == 'closed' for v in uncertainty): rating = 'high'
    elif hypo or new or any(eo.LEVELS.index(v['level_to']) > eo.LEVELS.index(v['level_from']) for v in uncertainty): rating = 'medium'
    elif unexpected or any(v['before'] and any(v['before'].get(k) != v['after'].get(k) for k in ('interpretation','scope','depends_on')) for v in changes): rating = 'low'
    else: rating = 'zero'
    return delta, rating


def scheduler_check(state, scheduler):
    import state_check
    errors = schema_errors(scheduler, 'scheduler.schema.json')
    if errors: return {'status':'FAIL','errors':errors}
    if not state_check.check_state(state).ok: errors.append('STATE_INVALID')
    if scheduler.get('state_version') != state['state_version']: errors.append('STALE_SCHEDULER')
    experiments = eo.index(state, 'experiments')
    seen = set()
    for record in scheduler.get('eig_calibration', {}).get('records', []):
        xid = record.get('experiment'); x = experiments.get(xid)
        if xid in seen: errors.append('DUPLICATE_EIG_RECORD')
        seen.add(xid)
        if not x or x['status'] != 'done' or not x.get('outcome_analysis'):
            errors.append('EIG_NEEDS_SOURCE_RECEIPT: ' + str(xid)); continue
        delta, rating = actual_eig(x['outcome_analysis'])
        if record.get('observed_delta') != delta or record.get('actual_information_gain') != rating: errors.append('FABRICATED_EIG: ' + xid)
        if record.get('predicted_information_gain') not in ('high','medium','low'): errors.append('INVALID_PREDICTED_EIG')
    for x in experiments.values():
        if x['status'] == 'done' and x.get('outcome_analysis') and x['id'] not in seen: errors.append('MISSING_EIG: ' + x['id'])
    for action in scheduler.get('next_actions', []):
        xid = action.get('action')
        if xid in experiments:
            x = experiments[xid]
            if x['status'] != 'planned' or eo._check_plan(state, xid)['status'] != 'PASS' or x.get('execution_blocked_by'): errors.append('BLOCKED_SCHEDULED_EXPERIMENT: ' + xid)
            if x.get('execution_protocol') and peig(state, xid)['status'] == 'HOLD': errors.append('PEIG_HOLD: ' + xid)
    return {'status': 'FAIL' if errors else 'PASS', 'errors': errors}
