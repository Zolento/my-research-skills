#!/usr/bin/env python3
"""R9.O Evidence Outcome Analysis gates and R10/R11 copy-on-write state updates.

The agent supplies source-grounded scientific judgments. This module checks their
contracts and transitions; it does not infer causality or validity from log wording.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

OUTCOMES = ('POSITIVE_EVIDENCE', 'NEGATIVE_EVIDENCE', 'MIXED_EVIDENCE', 'INCONCLUSIVE', 'INVALID_EXPERIMENT')
SUPPORT = ('SUPPORTED', 'WEAKENED', 'FALSIFIED', 'UNRESOLVED', 'NOT_TESTED')
DECISIONS = ('CONTINUE', 'RETRY', 'REDESIGN', 'PIVOT', 'STOP', 'HOLD')
FAILURES = ('implementation_failure', 'optimization_failure', 'data_failure', 'protocol_failure',
            'measurement_failure', 'evaluation_failure', 'baseline_failure', 'statistical_power_failure',
            'identifiability_failure', 'hypothesis_failure', 'theory_failure', 'assumption_violation',
            'distribution_shift', 'unknown')
CHECKS = ('result_faithful', 'validity_grounded', 'inference_calibrated', 'scope_preserved',
          'attributions_grounded', 'confirmation_bias_checked', 'replication_grounded',
          'alternatives_grounded', 'decisions_justified')
LEVELS = ('high', 'medium', 'low')
TIERS = ('T0', 'T1', 'T2', 'T3', 'T4', 'T5')
POLICY_KEYS = {'schema', 'frozen_at_state_version', 'min_valid_runs', 'min_seeds', 'min_datasets',
               'require_independent_replication', 'min_verification_tier'}
ANALYSIS_KEYS = {'schema', 'id', 'experiment_id', 'base_state_digest', 'context_digest', 'packet_digest', 'outcome',
                 'validity_checks', 'verification_tier', 'claim_updates', 'hypothesis_updates',
                 'failure_attributions', 'alternatives', 'decisions', 'stop_rules', 'followups',
                 'negative_knowledge', 'repairs', 'open_questions', 'uncertainty_updates', 'unchanged', 'reasoning_summary'}


def digest(value: Any) -> str:
    payload = value if isinstance(value, str) else json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def text(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value, nonempty=False):
    return isinstance(value, list) and (not nonempty or bool(value)) and all(text(x) for x in value) and len(value) == len(set(value))


def integer(value):
    return type(value) is int and value >= 0


def index(state, key):
    return {x['id']: x for x in state.get(key, [])}


def protocol_signature(experiment):
    """Seed and implementation commit do not turn an unchanged scientific design into a new design."""
    if experiment.get('execution_protocol'):
        import execution_gate
        return digest({'targets': sorted(experiment['claim_targeted'] + experiment.get('hypothesis_targeted', [])),
                       'design': execution_gate.design_projection(experiment['execution_protocol'])})
    design = {k: experiment.get(k) for k in ('stage', 'data_split', 'metric', 'claim_targeted',
                                             'hypothesis_targeted', 'alternative_targeted', 'outcome_protocol')}
    preregistration = experiment.get('preregistration')
    design['preregistration'] = {k: v for k, v in preregistration.items() if k != 'frozen_at_state_version'} if isinstance(preregistration, dict) else preregistration
    return digest(design)


def policy_errors(policy, version):
    if not isinstance(policy, dict) or set(policy) != POLICY_KEYS or policy['schema'] != 'evidence-outcome-policy@1':
        return ['invalid outcome policy']
    if not integer(policy['frozen_at_state_version']) or policy['frozen_at_state_version'] > version:
        return ['outcome policy must be frozen before results']
    if any(not integer(policy[k]) or policy[k] < 1 for k in ('min_valid_runs', 'min_seeds', 'min_datasets')) or type(policy['require_independent_replication']) is not bool or policy['min_verification_tier'] not in TIERS[2:]:
        return ['invalid project replication standard']
    return []


def packet_errors(packet, experiment):
    required = {'schema', 'experiment_id', 'experiment_digest', 'execution_status', 'result_summary', 'sources', 'observations'}
    if not isinstance(packet, dict) or set(packet) != required or packet['schema'] != 'evidence-result@1' or packet['experiment_id'] != experiment['id'] or packet['experiment_digest'] != digest(experiment):
        return ['invalid or stale source experiment binding']
    errors, sources, observations = [], {}, {}
    if packet['execution_status'] not in ('completed', 'failed') or not text(packet['result_summary']):
        errors.append('result collection needs actual execution status and result summary')
    for source in packet['sources']:
        if set(source) != {'id', 'kind', 'location', 'content', 'digest'} or not all(text(source[k]) for k in ('id', 'kind', 'location', 'content')) or source['kind'] not in ('log', 'metric', 'config', 'protocol', 'result') or source['digest'] != digest(source['content']) or source['id'] in sources:
            errors.append('result sources need exact content, locator and hash')
        else:
            sources[source['id']] = source
    if not sources:
        errors.append('result sources are required')
    for observation in packet['observations']:
        if set(observation) != {'id', 'statement', 'scope', 'source_ids'} or not text(observation['id']) or observation['id'] in observations or not text(observation['statement']) or not text(observation['scope']) or not strings(observation['source_ids'], True) or not set(observation['source_ids']) <= set(sources):
            errors.append('observation must trace to result sources and a scope')
        else:
            observations[observation['id']] = observation
    if not observations:
        errors.append('an actual observation, including an execution failure, is required')
    return errors


def previous_status(target, scope):
    matching = [x for x in target.get('scoped_outcomes', []) if x['scope'] == scope and x.get('applied', True)]
    return matching[-1]['status'] if matching else 'UNRESOLVED'


def replication(state, packet, analysis, update):
    """Count actual valid negative experiment records, never a judge's claimed run count."""
    policy = state['contract']['outcome_policy']
    experiments = index(state, 'experiments')
    ids = update['replication_ids']
    if not strings(ids, True) or analysis['experiment_id'] not in ids or any(x not in experiments for x in ids):
        return False
    eligible = []
    for xid in ids:
        x = experiments[xid]
        if xid == analysis['experiment_id']:
            effects, valid, tier = analysis['claim_updates'] + analysis['hypothesis_updates'], experiment_validity(packet, analysis), analysis['verification_tier']
        else:
            record = x.get('outcome_analysis')
            if not record:
                continue
            a = record['analysis']
            effects, valid, tier = a['claim_updates'] + a['hypothesis_updates'], experiment_validity(record['packet'], a), a['verification_tier']
        current = experiments[analysis['experiment_id']]
        same_design = x['metric'] == current['metric'] and x.get('outcome_protocol', {}).get('design') == current.get('outcome_protocol', {}).get('design')
        if not same_design or x.get('validity', {}).get('status') != 'valid' or valid != 'VALID' or TIERS.index(tier) < TIERS.index(policy['min_verification_tier']):
            continue
        if any(e['id'] == update['id'] and e['scope'] == update['scope'] and e['direction'] == 'negative' and e['identification'] == 'PASS' for e in effects):
            eligible.append(x)
    seeds = {x['seed'] for x in eligible}
    datasets = {x.get('outcome_protocol', {}).get('dataset', x['data_split']) for x in eligible}
    independent = any(x.get('outcome_protocol', {}).get('independent_replication') is True for x in eligible)
    # Root claims and their explicitly marked central hypotheses require more than one run.
    target = index(state, 'claims').get(update['id']) or index(state, 'hypotheses').get(update['id'])
    central = update['id'].startswith('C') and target.get('parent') is None or target.get('central') is True
    floor = max(policy['min_valid_runs'], 2 if central else 1)
    return len(eligible) >= floor and len(seeds) >= policy['min_seeds'] and len(datasets) >= policy['min_datasets'] and (not policy['require_independent_replication'] or independent)


def experiment_validity(packet, analysis):
    checks = analysis['validity_checks']
    if packet['execution_status'] == 'failed' or any(x['status'] == 'FAIL' for x in checks.values()):
        return 'INVALID'
    return 'VALID' if all(x['status'] == 'PASS' for x in checks.values()) else 'UNKNOWN'



def validation_context(state):
    """Flat historical validation context. Prior receipts never recursively embed contexts."""
    context = copy.deepcopy(state)
    for x in context.get('experiments', []):
        if isinstance(x.get('outcome_analysis'), dict):
            r = x['outcome_analysis']
            x['outcome_analysis'] = {k: copy.deepcopy(r[k]) for k in ('packet', 'analysis', 'audit')}
    return context


def _validate(state, packet, analysis, audit=None, *, bind_state=True):
    errors, unresolved = [], []
    experiment = index(state, 'experiments').get(packet.get('experiment_id'))
    if experiment is None:
        return {'status': 'FAIL', 'errors': ['source experiment does not exist'], 'unresolved': []}
    policy = state.get('contract', {}).get('outcome_policy')
    errors += policy_errors(policy, state['state_version'])
    errors += packet_errors(packet, experiment)
    if errors:
        return {'status': 'FAIL', 'errors': errors, 'unresolved': []}
    if set(analysis) != ANALYSIS_KEYS or analysis['schema'] != 'evidence-outcome-analysis@1' or not text(analysis['id']) or analysis['experiment_id'] != experiment['id'] or (bind_state and analysis['base_state_digest'] != digest(state)) or analysis['context_digest'] != digest(validation_context(state)) or analysis['packet_digest'] != digest(packet) or analysis['outcome'] not in OUTCOMES or analysis['verification_tier'] not in TIERS:
        return {'status': 'FAIL', 'errors': ['invalid or stale analysis proposal'], 'unresolved': []}
    protocol = experiment.get('outcome_protocol')
    if not isinstance(protocol, dict) or not all(text(protocol.get(k)) for k in ('dataset', 'design', 'scope')) or type(protocol.get('independent_replication', False)) is not bool:
        errors.append('declare scientific dataset, design and scope before execution')
    if experiment.get('outcome_analysis'):
        errors.append('an analysed result is immutable; a retry requires a new experiment ID')
    if not isinstance(experiment.get('preregistration'), dict) or policy['frozen_at_state_version'] > experiment['preregistration']['frozen_at_state_version']:
        errors.append('replication policy must precede experimental preregistration')
    if experiment.get('status') not in ('running', 'done', 'failed'):
        errors.append('analysis requires an executed experiment, not a planned result')
    planning = _check_plan(state, experiment['id'])
    if planning['status'] != 'PASS':
        errors.append('execution violated an unresolved stop/retry constraint; resolve the planning gate first')
    if set(analysis['validity_checks']) != {'execution', 'protocol', 'measurement', 'evaluation'}:
        errors.append('all experimental validity checks are required')
    source_ids = {s['id'] for s in packet['sources']}
    observation_ids = {o['id'] for o in packet['observations']}
    observations = {o['id']: o for o in packet['observations']}
    for check in analysis['validity_checks'].values():
        if set(check) != {'status', 'reason', 'source_ids'} or check['status'] not in ('PASS', 'FAIL', 'UNKNOWN') or not text(check['reason']) or not strings(check['source_ids'], True) or not set(check['source_ids']) <= source_ids:
            errors.append('validity judgment needs inspected sources')
    validity = experiment_validity(packet, analysis)
    if validity == 'INVALID' and analysis['outcome'] != 'INVALID_EXPERIMENT' or validity == 'VALID' and analysis['outcome'] == 'INVALID_EXPERIMENT' or validity == 'UNKNOWN' and analysis['outcome'] != 'INCONCLUSIVE':
        errors.append('negative evidence and experiment validity must be classified separately')
    updates, seen = [], set()
    for key, collection, targeted in (('claim_updates', 'claims', 'claim_targeted'), ('hypothesis_updates', 'hypotheses', 'hypothesis_targeted')):
        targets = index(state, collection)
        intended = experiment.get(targeted, [])
        if not strings(intended):
            errors.append('invalid declared experiment targets')
        for update in analysis[key]:
            fields = {'id', 'scope', 'scope_relation', 'previous_status', 'new_status', 'evidence', 'direction', 'identification', 'reason', 'replication_ids'}
            if key == 'claim_updates':
                fields |= {'previous_support', 'new_support', 'scope_change'}
            if set(update) != fields or update['id'] not in targets or update['id'] not in intended or update['id'] in seen or update['new_status'] not in SUPPORT or update['direction'] not in ('positive', 'negative', 'neutral', 'not_tested') or update['scope_relation'] not in ('FULL', 'LOCAL') or update['identification'] not in ('PASS', 'FAIL', 'UNKNOWN') or not text(update['scope']) or not text(update['reason']):
                errors.append('invalid or non-targeted scoped scientific update')
                continue
            seen.add(update['id']); updates.append(update)
            target = targets[update['id']]
            if update['previous_status'] != previous_status(target, update['scope']):
                errors.append('previous scientific status does not match the scoped history')
            declared_scope = target.get('scope') if collection == 'claims' else target.get('scientific_scope')
            if update['scope_relation'] == 'FULL' and update['scope'] != declared_scope:
                errors.append('global update requires the exact declared scientific scope')
            if not strings(update['evidence']) or not set(update['evidence']) <= observation_ids or update['new_status'] not in ('NOT_TESTED',) and not update['evidence']:
                errors.append('scientific update must trace to observations')
            elif any(observations[o]['scope'] != update['scope'] for o in update['evidence']):
                errors.append('scientific update must preserve the cited observation scope')
            if validity != 'VALID' and update['new_status'] not in ('UNRESOLVED', 'NOT_TESTED'):
                errors.append('invalid or unverified experiment cannot support, weaken or falsify a hypothesis')
            if update['identification'] != 'PASS' and update['new_status'] not in ('UNRESOLVED', 'NOT_TESTED'):
                errors.append('non-identifying evidence cannot identify a scientific conclusion')
            expected_direction = {'SUPPORTED': 'positive', 'WEAKENED': 'negative', 'FALSIFIED': 'negative', 'UNRESOLVED': 'neutral', 'NOT_TESTED': 'not_tested'}[update['new_status']]
            if update['direction'] != expected_direction:
                errors.append('scientific status and evidential direction disagree')
            if update['new_status'] == 'FALSIFIED' and not replication(state, packet, analysis, update):
                errors.append('FALSIFIED requires the frozen replication standard; one negative run is insufficient for a central hypothesis')
            if update['previous_status'] == 'FALSIFIED' and update['new_status'] not in ('FALSIFIED', 'NOT_TESTED'):
                errors.append('deprecated scientific hypothesis cannot be silently restored; resolve a new scoped hypothesis explicitly')
            if key == 'claim_updates':
                expected_support = target['status']
                if validity == 'VALID' and update['scope_relation'] == 'FULL':
                    if update['new_status'] == 'SUPPORTED': expected_support = 'supported' if TIERS.index(analysis['verification_tier']) >= 2 else 'partially-supported'
                    elif update['new_status'] == 'WEAKENED' and target['status'] == 'supported': expected_support = 'partially-supported'
                    elif update['new_status'] == 'FALSIFIED': expected_support = 'contradicted'
                if update['previous_support'] != target['status'] or update['new_support'] != expected_support or update['scope_change'] is not None:
                    errors.append('claim lifecycle change exceeds the scoped outcome; scope changes need a separate R10 repair')
                if target['status'] == 'killed' and update['new_support'] != 'killed':
                    errors.append('killed claim cannot be silently resurrected')
        if {x['id'] for x in analysis[key]} != set(intended):
            errors.append('each declared target needs an individual assessment, including NOT_TESTED')
    if experiment['stage'] == 'X2' and updates:
        errors.append('baseline calibration cannot perform claim or hypothesis discrimination')
    directions = {u['direction'] for u in updates} - {'neutral', 'not_tested'}
    expected = 'MIXED_EVIDENCE' if directions == {'positive', 'negative'} else 'POSITIVE_EVIDENCE' if directions == {'positive'} else 'NEGATIVE_EVIDENCE' if directions == {'negative'} else 'INCONCLUSIVE'
    if validity == 'VALID' and updates and analysis['outcome'] != expected:
        errors.append('mixed outcomes must preserve the separate claim effects')
    for attribution in analysis['failure_attributions']:
        if set(attribution) != {'type', 'confidence', 'evidence', 'alternative_explanations', 'what_would_disambiguate'} or attribution['type'] not in FAILURES or attribution['confidence'] not in LEVELS or not strings(attribution['alternative_explanations'], True) or not text(attribution['what_would_disambiguate']):
            errors.append('failure attribution requires confidence, alternatives and a discriminating check')
            continue
        if not strings(attribution['evidence'], True) or not set(attribution['evidence']) <= source_ids:
            errors.append('UNSUPPORTED_FAILURE_ATTRIBUTION: failure explanation lacks source evidence')
        if attribution['type'] in ('implementation_failure', 'optimization_failure', 'protocol_failure', 'measurement_failure', 'evaluation_failure', 'data_failure', 'baseline_failure') and validity == 'VALID':
            errors.append('an established execution/protocol defect contradicts VALID; use unknown for an unverified alternative')
        if attribution['type'] in ('hypothesis_failure', 'theory_failure') and (validity != 'VALID' or 'negative' not in directions):
            errors.append('bad execution cannot establish hypothesis or theory failure')
    if (validity != 'VALID' or analysis['outcome'] in ('NEGATIVE_EVIDENCE', 'MIXED_EVIDENCE', 'INCONCLUSIVE')) and not analysis['failure_attributions']:
        errors.append('nonpositive outcomes need an attribution, including unknown when unresolved')
    alternative_ids = set()
    for alternative in analysis['alternatives']:
        if set(alternative) != {'hypothesis_id', 'evidence_for', 'evidence_against', 'status', 'discriminating_next_action'} or alternative['hypothesis_id'] not in index(state, 'hypotheses') or not strings(alternative['evidence_for']) or not strings(alternative['evidence_against']) or not set(alternative['evidence_for'] + alternative['evidence_against']) <= observation_ids or alternative['status'] not in SUPPORT or not text(alternative['discriminating_next_action']):
            errors.append('alternative explanation must be existing, relevant and evidence-bound')
            continue
        if alternative['hypothesis_id'] in alternative_ids:
            errors.append('duplicate alternative hypothesis')
        alternative_ids.add(alternative['hypothesis_id'])
        if alternative['status'] != 'UNRESOLVED' and not any(u['id'] == alternative['hypothesis_id'] and u['new_status'] == alternative['status'] for u in updates):
            errors.append('alternative support changes require an individually assessed hypothesis update')
    if len(analysis['alternatives']) > 3:
        errors.append('keep only a small set of directly relevant alternative hypotheses')
    followups = {}
    known_targets = set().union(*(set(index(state, k)) for k in ('claims', 'hypotheses', 'experiments', 'uncertainties')))
    for followup in analysis['followups']:
        fields = {'id', 'target_ids', 'description', 'expected_information_gain', 'cost', 'scientific_value', 'risk', 'decision_it_resolves'}
        if set(followup) != fields or not text(followup['id']) or followup['id'] in followups or not strings(followup['target_ids'], True) or not set(followup['target_ids']) <= known_targets or not all(followup[k] in LEVELS for k in ('expected_information_gain', 'cost', 'scientific_value', 'risk')) or not all(text(followup[k]) for k in ('description', 'decision_it_resolves')):
            errors.append('followup needs information gain, cost, scientific value, risk and the decision resolved')
        else: followups[followup['id']] = followup
    for alternative in analysis['alternatives']:
        if alternative.get('discriminating_next_action') not in followups:
            errors.append('alternative hypothesis needs a registered discriminating followup ID')
    stop_rules = {}
    old_rule_ids = {r['id'] for f in state['failures'] for r in f.get('stop_rules', [])}
    for rule in analysis['stop_rules']:
        if set(rule) != {'id', 'target_ids', 'scope', 'kind', 'rule', 'protocol_signature', 'revisit_conditions'} or not text(rule['id']) or rule['id'] in stop_rules or rule['id'] in old_rule_ids or not strings(rule['target_ids'], True) or not set(rule['target_ids']) <= seen or rule['kind'] not in ('protocol', 'claim_line') or not text(rule['scope']) or not text(rule['rule']) or rule['protocol_signature'] != protocol_signature(experiment) or not strings(rule['revisit_conditions'], True):
            errors.append('stop rule needs explicit scoped targets, protocol and revisit conditions')
        else:
            if any(u['id'] in rule['target_ids'] and u['scope'] != rule['scope'] for u in updates):
                errors.append('stop rule must use the assessed scientific scope; do not globally ban a local result')
            stop_rules[rule['id']] = rule
    decision_targets = set()
    for decision in analysis['decisions']:
        if set(decision) != {'target_ids', 'action', 'reason', 'required_fixes', 'stop_rule_id', 'next_action_id'} or decision['action'] not in DECISIONS or not strings(decision['target_ids'], True) or not text(decision['reason']) or not strings(decision['required_fixes']):
            errors.append('invalid per-target decision')
            continue
        affected = [u for u in updates if u['id'] in decision['target_ids']]
        if decision_targets & set(decision['target_ids']): errors.append('target has conflicting decisions')
        decision_targets.update(decision['target_ids'])
        action = decision['action']
        if validity != 'VALID' and action not in ('RETRY', 'HOLD', 'REDESIGN'):
            errors.append('unusable execution must not decide scientific success, pivot or stop')
        if action == 'RETRY' and (validity != 'INVALID' or not decision['required_fixes']):
            errors.append('RETRY requires an invalid experiment and an explicit fix before retry')
        if any(u['identification'] != 'PASS' for u in affected) and action not in ('REDESIGN', 'HOLD', 'RETRY'):
            errors.append('non-identifying experiment requires REDESIGN or HOLD')
        if action == 'CONTINUE' and affected and not all(u['new_status'] == 'SUPPORTED' for u in affected):
            errors.append('CONTINUE must follow the supported line, not hide mixed or negative effects')
        if action in ('PIVOT', 'STOP'):
            rule = stop_rules.get(decision['stop_rule_id'])
            if validity != 'VALID' or not affected or not all(u['new_status'] in ('WEAKENED', 'FALSIFIED') for u in affected) or rule is None or not set(decision['target_ids']) <= set(rule['target_ids']):
                errors.append('PIVOT/STOP requires valid scoped negative evidence and a persistent stop rule')
            if action == 'STOP' and any(len(u['replication_ids']) < 2 or not replication(state, packet, analysis, u) for u in affected):
                errors.append('STOP requires repeated validated evidence meeting project replication criteria')
        elif decision['stop_rule_id'] is not None:
            errors.append('only PIVOT/STOP decisions bind stop rules')
        if decision['next_action_id'] is not None and decision['next_action_id'] not in followups:
            errors.append('next action is missing from the information-gain followup list')
        elif decision['next_action_id'] is not None and not set(decision['target_ids']) <= set(followups[decision['next_action_id']]['target_ids']):
            errors.append('registered next action does not cover the decision targets')
    if decision_targets != (seen or {experiment['id']}):
        errors.append('decision gate must cover each affected target independently')
    negative_targets = {u['id'] for u in updates if u['direction'] == 'negative'}
    memories = set()
    for memory in analysis['negative_knowledge']:
        fields = {'target_id', 'finding', 'ruled_out', 'not_ruled_out', 'likely_failure_mode', 'retry_allowed', 'retry_conditions', 'revisit_conditions', 'confidence'}
        if set(memory) != fields or memory['target_id'] not in negative_targets or memory['target_id'] in memories or not text(memory['finding']) or not strings(memory['ruled_out']) or not strings(memory['not_ruled_out'], True) or memory['likely_failure_mode'] not in FAILURES or type(memory['retry_allowed']) is not bool or not strings(memory['retry_conditions']) or not strings(memory['revisit_conditions'], True) or memory['confidence'] not in LEVELS:
            errors.append('negative knowledge must retain both exclusions and surviving explanations')
        else:
            memories.add(memory['target_id'])
            if memory['retry_allowed'] and not memory['retry_conditions']:
                errors.append('negative-result retry requires an explicit changed condition')
            u = next(u for u in updates if u['id'] == memory['target_id'])
            if u['new_status'] != 'FALSIFIED' and memory['ruled_out']:
                errors.append('weakened evidence does not conclusively rule out a hypothesis')
    if memories != negative_targets:
        errors.append('every valid negative target needs persistent negative knowledge')
    if analysis['outcome'] == 'INVALID_EXPERIMENT' and analysis['negative_knowledge']:
        errors.append('invalid experiments are failure memory, not scientific negative knowledge')
    if not strings(analysis['unchanged'], True) or not text(analysis['reasoning_summary']):
        errors.append('analysis must explain what changed and what did not change')
    for repair in analysis['repairs']:
        if set(repair) != {'kind', 'description', 'target_ids'} or repair['kind'] not in ('implementation_or_protocol_fix', 'scientific_redesign', 'abandon_or_narrow_claim') or not text(repair['description']) or not strings(repair['target_ids'], True) or not set(repair['target_ids']) <= known_targets:
            errors.append('repair path must identify a real type of work and target')
    for question in analysis['open_questions']:
        if set(question) != {'question', 'importance', 'uncertainty'} or not text(question['question']) or question['importance'] not in ('critical', 'high', 'medium', 'low') or question['uncertainty'] not in LEVELS:
            errors.append('invalid scientific open question')
    known_uncertainties = index(state, 'uncertainties')
    changed_uncertainties = set()
    for update in analysis['uncertainty_updates']:
        fields = {'id', 'previous_level', 'new_level', 'previous_status', 'new_status', 'evidence', 'reason'}
        if set(update) != fields or update['id'] not in known_uncertainties or update['id'] in changed_uncertainties or update['new_level'] not in LEVELS or update['new_status'] not in ('open', 'closed') or not text(update['reason']) or not strings(update['evidence'], True) or not set(update['evidence']) <= observation_ids:
            errors.append('uncertainty change needs an existing question and actual result sources')
            continue
        old = known_uncertainties[update['id']]
        if update['previous_level'] != old['uncertainty'] or update['previous_status'] != old['status']:
            errors.append('uncertainty change has a stale previous value')
        if validity != 'VALID' and (update['new_status'] == 'closed' or LEVELS.index(update['new_level']) > LEVELS.index(old['uncertainty'])):
            errors.append('invalid/unverified experiments cannot close or reduce scientific uncertainty')
        if update['new_status'] == 'closed' and not any(u['identification'] == 'PASS' and u['new_status'] in ('SUPPORTED', 'FALSIFIED') for u in updates):
            errors.append('closing a question requires identifying discriminating evidence')
        changed_uncertainties.add(update['id'])
    if audit is None:
        unresolved.append('independent source-grounded outcome audit is required')
    elif set(audit) != {'schema', 'analysis_digest', 'packet_digest', 'state_digest', 'checks'} or audit['schema'] != 'evidence-outcome-audit@1' or audit['analysis_digest'] != digest(analysis) or audit['packet_digest'] != digest(packet) or audit['state_digest'] != analysis['base_state_digest'] or set(audit['checks']) != set(CHECKS):
        errors.append('invalid, incomplete or stale semantic outcome audit')
    else:
        for name, check in audit['checks'].items():
            if set(check) != {'status', 'reason'} or check['status'] not in ('PASS', 'FAIL', 'UNKNOWN') or not text(check['reason']):
                errors.append('invalid local semantic audit check')
            elif check['status'] == 'FAIL': errors.append(('UNSUPPORTED_FAILURE_ATTRIBUTION' if name == 'attributions_grounded' else name) + ': ' + check['reason'])
            elif check['status'] == 'UNKNOWN': unresolved.append(name + ': ' + check['reason'])
    return {'status': 'FAIL' if errors else 'NEEDS_REVIEW' if unresolved else 'PASS', 'errors': errors, 'unresolved': unresolved,
            'experiment_validity': validity, 'outcome': analysis['outcome']}


def validate(state, packet, analysis, audit=None):
    try:
        import state_check
        baseline = state_check.check_state(state)
        if baseline.shape or baseline.violations:
            return {'status': 'FAIL', 'errors': ['source Research State violates original shape/scientific gates'], 'unresolved': [], 'state_report': baseline.as_dict()}
        return _validate(state, packet, analysis, audit)
    except (TypeError, ValueError, KeyError, IndexError, AttributeError) as exc:
        return {'status': 'FAIL', 'errors': ['invalid outcome artifact: ' + str(exc)], 'unresolved': []}


def _new_id(state, collection, prefix):
    existing = set(index(state, collection))
    n = 1
    while prefix + str(n) in existing: n += 1
    return prefix + str(n)


def _apply(state, packet, analysis, audit, timestamp=None):
    """R10/R11 transaction: validate, copy, mutate allowed scientific fields, check; never edit input."""
    gate = validate(state, packet, analysis, audit)
    if gate['status'] != 'PASS':
        return {'status': gate['status'], 'errors': gate['errors'], 'unresolved': gate['unresolved']}
    out = copy.deepcopy(state)
    version = out['state_version'] + 1
    out['state_version'] = version
    x = index(out, 'experiments')[analysis['experiment_id']]
    x.update(status='failed' if packet['execution_status'] == 'failed' else 'done',
             result=packet['result_summary'], interpretation=analysis['reasoning_summary'], result_at_state_version=version)
    x.pop('result_pending', None)
    if gate['experiment_validity'] == 'INVALID':
        x['validity'] = {'status': 'invalid', 'reason': analysis['reasoning_summary'], 'since_state_version': version}
    elif gate['experiment_validity'] == 'UNKNOWN':
        x['validity'] = {'status': 'stale', 'reason': 'Result validity remains unverified.', 'since_state_version': version}
    updates = analysis['claim_updates'] + analysis['hypothesis_updates']
    evidence_ids = {}
    valid = gate['experiment_validity'] == 'VALID'
    for u in updates:
        collection = 'claims' if u['id'] in index(out, 'claims') else 'hypotheses'
        target = index(out, collection)[u['id']]
        target.setdefault('scoped_outcomes', []).append({'analysis_id': analysis['id'], 'experiment_id': x['id'],
                                                        'scope': u['scope'], 'scope_relation': u['scope_relation'], 'status': u['new_status'],
                                                        'applied': valid and u['identification'] == 'PASS' and u['new_status'] != 'NOT_TESTED'})
        if valid and u['identification'] == 'PASS' and u['scope_relation'] == 'FULL' and u['new_status'] != 'NOT_TESTED': target['outcome_status'] = u['new_status']
        if valid and u['direction'] in ('positive', 'negative'):
            eid = _new_id(out, 'evidence', 'E'); evidence_ids[u['id']] = eid
            claim_id = u['id'] if collection == 'claims' else None
            # V3 forbids evidence-linked ungrounded claims, including negative links.
            # Preserve that lifecycle; keep its weakened prediction in the receipt,
            # ledger and Failure Memory without manufacturing partial support.
            attach = claim_id and u['scope_relation'] == 'FULL' and not (u['new_status'] == 'WEAKENED' and u['previous_support'] == 'ungrounded')
            evidence = {'id': eid, 'kind': 'experiment', 'supports': [claim_id] if attach and u['direction'] == 'positive' else [],
                        'contradicts': [claim_id] if attach and u['direction'] == 'negative' else [],
                        'strength': 'strong' if TIERS.index(analysis['verification_tier']) >= 2 else 'partial',
                        'scope': u['scope'], 'epistemic_status': 'Observed', 'source_ref': x['id'] + '/' + analysis['id'],
                        'verification_tier': analysis['verification_tier'], 'depends_on': [x['id']],
                        'validity': {'status': 'valid', 'reason': u['reason'], 'since_state_version': version},
                        'outcome_observations': u['evidence'], 'hypothesis_target': None if claim_id else u['id'], 'claim_target': claim_id}
            out['evidence'].append(evidence)
            if attach:
                field = 'supporting_evidence' if u['direction'] == 'positive' else 'refuting_evidence'
                target[field].append(eid)
                target['status'] = u['new_support']
                # Recording the R10 disposition is part of this transaction, not an independent self-grade.
                out['repairs'].append({'flaw': u['reason'], 'disposition': 'KILL_BRANCH' if u['new_status'] == 'FALSIFIED' else 'REPAIR_CLAIM',
                                       'state_delta': u['id'] + '.status: ' + u['previous_support'] + ' -> ' + u['new_support'] + '; evidence ' + eid,
                                       'targets': [u['id']], 'closure': 'RESOLVED', 'source_review': None,
                                       'outcome_analysis_id': analysis['id']})
    fid = None
    if analysis['outcome'] != 'POSITIVE_EVIDENCE' or analysis['stop_rules']:
        fid = _new_id(out, 'failures', 'F')
        kind = 'engineering-failure' if gate['experiment_validity'] == 'INVALID' else 'falsified' if any(u['new_status'] == 'FALSIFIED' for u in updates) else 'unsupported' if any(u['direction'] == 'negative' for u in updates) else 'inconclusive'
        failure = {'id': fid, 'kind': kind, 'what': packet['result_summary'], 'why': analysis['reasoning_summary'],
                   'referenced_by': [x['id']] + [u['id'] for u in analysis['claim_updates']], 'depends_on': [],
                   'validity': {'status': 'valid', 'reason': 'Outcome source record retained.', 'since_state_version': version},
                   'source_review': None, 'source_analysis_id': analysis['id'],
                   'failure_attributions': copy.deepcopy(analysis['failure_attributions']),
                   'negative_knowledge': [dict(copy.deepcopy(n), experiment_id=x['id'], evidence_id=evidence_ids.get(n['target_id'])) for n in analysis['negative_knowledge']],
                   'stop_rules': copy.deepcopy(analysis['stop_rules'])}
        out['failures'].append(failure); x['known_flaws'].append(fid)
        for u in analysis['claim_updates']:
            index(out, 'claims')[u['id']]['known_flaws'].append(fid)
    for update in analysis['uncertainty_updates']:
        index(out, 'uncertainties')[update['id']].update(uncertainty=update['new_level'], status=update['new_status'])
    for q in analysis['open_questions']:
        out['uncertainties'].append(dict(copy.deepcopy(q), id=_new_id(out, 'uncertainties', 'U'),
                                         cheapest_discriminating_test='TBD', status='open', depends_on=[],
                                         validity={'status': 'valid', 'reason': analysis['reasoning_summary'], 'since_state_version': version}))
    # Propagate invalid prerequisites to stale, without declaring downstream propositions false.
    first_class = ('claims', 'evidence', 'assumptions', 'hypotheses', 'experiments', 'literature', 'failures', 'uncertainties')
    objects = {o['id']: o for k in first_class for o in out[k]}
    for o in objects.values():
        refs = o.get('depends_on', []) + (o.get('supporting_evidence', []) + o.get('refuting_evidence', []) if o['id'] in index(out, 'claims') else [])
        if o['validity']['status'] == 'valid' and any(objects[r]['validity']['status'] == 'invalid' for r in refs if r in objects):
            o['validity'] = {'status': 'stale', 'reason': 'Invalid prerequisite requires local revalidation.', 'since_state_version': version}
    for planned in out['experiments']:
        if planned['status'] in ('planned', 'running'):
            plan_gate = _check_plan(out, planned['id'])
            if plan_gate['status'] == 'FAIL':
                planned['execution_blocked_by'] = [r['id'] for r in plan_gate.get('blocked_by', [])]
            elif planned.get('outcome_plan_clearance'):
                planned.pop('execution_blocked_by', None)
    delta = []
    for collection in ('claims', 'hypotheses', 'experiments', 'evidence', 'failures', 'uncertainties', 'repairs'):
        old = index(state, collection) if collection != 'repairs' else {str(i): r for i, r in enumerate(state['repairs'])}
        new = index(out, collection) if collection != 'repairs' else {str(i): r for i, r in enumerate(out['repairs'])}
        for identifier, entry in new.items():
            if entry != old.get(identifier): delta.append({'collection': collection, 'id': identifier, 'before': copy.deepcopy(old.get(identifier)), 'after': copy.deepcopy(entry)})
    x['outcome_analysis'] = {'packet': copy.deepcopy(packet), 'analysis': copy.deepcopy(analysis), 'audit': copy.deepcopy(audit),
                             'validation_context': validation_context(state),
                             'audit_trail': {'source_experiment': x['id'], 'source_result': digest(packet),
                                            'previous_state': {'version': state['state_version'], 'digest': digest(state)},
                                            'state_delta': delta, 'decision': copy.deepcopy(analysis['decisions']),
                                            'reasoning_summary': analysis['reasoning_summary'],
                                            'timestamp': timestamp or datetime.now(timezone.utc).isoformat(), 'state_version': version}}
    import state_check
    report = state_check.check_state(out)
    if not report.ok:
        if not report.shape and not report.violations and report.outcome and all('each terminal experiment requires outcome analysis' in v.detail for v in report.outcome):
            return {'status': 'NEEDS_REVIEW', 'errors': [], 'unresolved': [v.detail for v in report.outcome], 'proposed_state': out,
                    'note': 'Historical adoption is incomplete. Finish source-grounded backlog analyses before accepting or using this state.'}
        return {'status': 'FAIL', 'errors': ['transaction violates Research State gates'], 'state_report': report.as_dict()}
    return {'status': 'PASS', 'state': out, 'state_delta': delta, 'decision_status': 'PENDING_ASSURANCE',
            'note': 'Recommendations do not authorize execution; run the post-update Assurance/decision gate.'}


def apply(state, packet, analysis, audit, timestamp=None):
    """Reject malformed transactions without mutating their source snapshot."""
    try:
        return _apply(state, packet, analysis, audit, timestamp)
    except (TypeError, ValueError, KeyError, IndexError, AttributeError) as exc:
        return {'status': 'FAIL', 'errors': ['invalid outcome transaction: ' + str(exc)]}


def constraints(state):
    """Discovery/planning input, projected only from scientific Failure Memory."""
    return [{'failure_id': f['id'], 'negative_knowledge': copy.deepcopy(f.get('negative_knowledge', [])),
             'stop_rules': copy.deepcopy(f.get('stop_rules', [])),
             'failure_attributions': copy.deepcopy(f.get('failure_attributions', [])),
             'source_analysis_id': f.get('source_analysis_id')} for f in state.get('failures', [])
            if f.get('negative_knowledge') or f.get('stop_rules') or f.get('source_analysis_id')]


def _check_plan(state, experiment_id):
    try:
        experiment = index(state, 'experiments')[experiment_id]
        targets = set(experiment['claim_targeted'] + experiment.get('hypothesis_targeted', []))
        hypotheses = index(state, 'hypotheses')
        claims = index(state, 'claims')
        pending = list(targets)
        while pending:
            target = pending.pop()
            parents = hypotheses.get(target, {}).get('parents', [])
            claim_parent = claims.get(target, {}).get('parent')
            for parent in parents + ([claim_parent] if claim_parent else []):
                if parent not in targets:
                    targets.add(parent); pending.append(parent)
        signature = protocol_signature(experiment)
        blocked = []
        for memory in constraints(state):
            for rule in memory['stop_rules']:
                if targets & set(rule['target_ids']) and (rule['kind'] == 'claim_line' or rule['protocol_signature'] == signature):
                    blocked.append(rule)
        for old in state['experiments']:
            receipt = old.get('outcome_analysis')
            if old['id'] == experiment_id or not receipt:
                continue
            a = receipt['analysis']
            if a['outcome'] == 'INVALID_EXPERIMENT' and (experiment.get('parent') == old['id'] or protocol_signature(old) == signature):
                fixes = list(dict.fromkeys(fix for d in a['decisions'] if d['action'] == 'RETRY' for fix in d['required_fixes']))
                if fixes:
                    blocked.append({'id': 'RETRY-' + a['id'], 'kind': 'retry_fix', 'rule': 'Fix the evidenced implementation/protocol problem before retry.', 'required_fixes': fixes, 'source_experiment': old['id']})
        if blocked:
            clearance = experiment.get('outcome_plan_clearance')
            fields = {'schema', 'memory_digest', 'experiment_signature', 'reviewed_rules'}
            if isinstance(clearance, dict) and set(clearance) == fields and clearance['schema'] == 'evidence-outcome-plan-clearance@1' and clearance['memory_digest'] == digest(constraints(state)) and clearance['experiment_signature'] == signature:
                covered = []
                evidence = index(state, 'evidence')
                for review in clearance['reviewed_rules']:
                    if set(review) != {'rule_id', 'status', 'changed_condition', 'evidence_ids', 'reason'} or review['status'] != 'PASS' or not text(review['changed_condition']) or not text(review['reason']) or not strings(review['evidence_ids'], True):
                        continue
                    if all(e in evidence and evidence[e]['validity']['status'] == 'valid' and evidence[e]['epistemic_status'] in ('Observed', 'Supported') and evidence[e]['verification_tier'] in TIERS[1:] for e in review['evidence_ids']):
                        covered.append(review['rule_id'])
                if len(covered) == len(set(covered)) and set(covered) == {r['id'] for r in blocked}:
                    return {'status': 'PASS', 'blocked_by': [], 'released_rules': covered,
                            'note': 'An explicit source-grounded planning audit judged the changed conditions. It did not delete historical stop rules.'}
        return {'status': 'FAIL' if blocked else 'PASS', 'blocked_by': blocked,
                'reason': 'No silent repeat or resurrection. A changed scientific design/condition requires a new reviewed plan.'}
    except (KeyError, TypeError, ValueError) as exc:
        return {'status': 'FAIL', 'errors': ['invalid experiment plan: ' + str(exc)]}


def check_plan(state, experiment_id):
    import state_check
    report = state_check.check_state(state)
    if not report.ok:
        return {'status': 'FAIL', 'errors': ['Research State must pass before a plan can be executed'], 'state_report': report.as_dict()}
    result = _check_plan(state, experiment_id)
    experiment = index(state, 'experiments').get(experiment_id, {})
    if result['status'] == 'PASS' and experiment.get('execution_protocol'):
        import execution_gate
        peig = execution_gate.peig(state, experiment_id)
        result['peig'] = peig
        if peig['status'] == 'HOLD': result['status'] = 'FAIL'
    return result


def decision_gate(state, experiment_id, assurance=None):
    """The six scientific decisions stay separate from R14 route/anchor authority."""
    try:
        import state_check
        report = state_check.check_state(state)
        if not report.ok:
            return {'status': 'FAIL', 'errors': ['Research State no longer passes its scientific gates'], 'state_report': report.as_dict()}
        record = index(state, 'experiments')[experiment_id]['outcome_analysis']
        for u in record['analysis']['claim_updates'] + record['analysis']['hypothesis_updates']:
            target = index(state, 'claims').get(u['id']) or index(state, 'hypotheses').get(u['id'])
            subsequent = [s for s in target.get('scoped_outcomes', []) if s['scope'] == u['scope']]
            if subsequent and subsequent[-1]['analysis_id'] != record['analysis']['id']:
                return {'status': 'NEEDS_REVIEW', 'decisions': [{'action': 'HOLD', 'reason': 'Later results superseded this target assessment. Reassess the next action against current evidence.'}]}
        checks = ('integrity', 'claim_calibration', 'reproducibility', 'stop_rule_compliance')
        if assurance is None:
            return {'status': 'NEEDS_REVIEW', 'decisions': [{'action': 'HOLD', 'reason': 'Post-update Assurance is required.'}]}
        if set(assurance) != {'schema', 'state_digest', 'analysis_digest', 'checks'} or assurance['schema'] != 'evidence-outcome-assurance@1' or assurance['state_digest'] != digest(state) or assurance['analysis_digest'] != digest(record['analysis']) or set(assurance['checks']) != set(checks):
            return {'status': 'FAIL', 'errors': ['invalid or stale post-update Assurance']}
        unknown = []
        for name, c in assurance['checks'].items():
            if set(c) != {'status', 'reason'} or c['status'] not in ('PASS', 'FAIL', 'UNKNOWN') or not text(c['reason']):
                return {'status': 'FAIL', 'errors': ['invalid Assurance verdict']}
            if c['status'] == 'FAIL': return {'status': 'FAIL', 'errors': [name + ': ' + c['reason']]}
            if c['status'] == 'UNKNOWN': unknown.append(name)
        if unknown: return {'status': 'NEEDS_REVIEW', 'decisions': [{'action': 'HOLD', 'reason': ', '.join(unknown)}]}
        return {'status': 'PASS', 'decisions': copy.deepcopy(record['analysis']['decisions']),
                'followups': copy.deepcopy(record['analysis']['followups']),
                'note': 'R8 preregistration, planning constraints and existing execution authorization still apply.'}
    except (KeyError, TypeError, ValueError) as exc:
        return {'status': 'FAIL', 'errors': ['invalid decision input: ' + str(exc)]}


def state_errors(state):
    """Optional additive gate. Legacy S/V rules and states retain their exact meaning."""
    policy = state.get('contract', {}).get('outcome_policy')
    records_present = any(x.get('outcome_analysis') is not None or x.get('outcome_protocol') is not None or x.get('hypothesis_targeted') or x.get('execution_blocked_by') or x.get('outcome_plan_clearance') for x in state['experiments']) or any(t.get('scoped_outcomes') or t.get('outcome_status') is not None for k in ('claims', 'hypotheses') for t in state[k]) or any(f.get('source_analysis_id') or f.get('negative_knowledge') or f.get('stop_rules') for f in state['failures'])
    if policy is None:
        return ['outcome records require a frozen policy'] if records_present else []
    errors = policy_errors(policy, state['state_version'])
    seen, records = set(), {}
    for x in state['experiments']:
        if x['status'] not in ('done', 'failed'):
            plan_gate = _check_plan(state, x['id'])
            blocked_ids = [r['id'] for r in plan_gate.get('blocked_by', [])]
            if blocked_ids and x.get('execution_blocked_by') != blocked_ids:
                errors.append(x['id'] + ': stop-rule-blocked plan requires an explicit execution hold')
            if not blocked_ids and x.get('execution_blocked_by'):
                errors.append(x['id'] + ': resolved execution hold must be explicitly cleared by planning')
            if 'outcome_analysis' in x: errors.append('unfinished experiment cannot contain an applied outcome')
            continue
        if not isinstance(x.get('outcome_analysis'), dict):
            errors.append(x['id'] + ': each terminal experiment requires outcome analysis')
            continue
        r = x['outcome_analysis']
        if set(r) != {'packet', 'analysis', 'audit', 'validation_context', 'audit_trail'}:
            errors.append(x['id'] + ': invalid outcome receipt'); continue
        a, p, au, trail = r['analysis'], r['packet'], r['audit'], r['audit_trail']
        if set(a) != ANALYSIS_KEYS or a['experiment_id'] != x['id'] or a['id'] in seen or a['packet_digest'] != digest(p) or au['analysis_digest'] != digest(a) or au['packet_digest'] != digest(p) or au['state_digest'] != a['base_state_digest'] or set(au['checks']) != set(CHECKS) or any(c['status'] != 'PASS' for c in au['checks'].values()):
            errors.append(x['id'] + ': stale, incomplete or nonpassing applied audit'); continue
        seen.add(a['id']); records[a['id']] = r
        context = r['validation_context']
        if context.get('contract', {}).get('outcome_policy') != policy:
            errors.append(x['id'] + ': frozen project replication policy was changed after results')
        historical = _validate(context, p, a, au, bind_state=False)
        if historical['status'] != 'PASS':
            errors.extend(x['id'] + ': ' + message for message in historical['errors'] + historical['unresolved'])
        for previous in context['experiments']:
            if previous.get('outcome_analysis'):
                actual = index(state, 'experiments').get(previous['id'])
                if actual is None or {k: actual.get('outcome_analysis', {}).get(k) for k in ('packet', 'analysis', 'audit')} != previous['outcome_analysis']:
                    errors.append(x['id'] + ': previously analysed result was removed or rewritten')
        fields = {'source_experiment', 'source_result', 'previous_state', 'state_delta', 'decision', 'reasoning_summary', 'timestamp', 'state_version'}
        if set(trail) != fields or trail['source_experiment'] != x['id'] or trail['source_result'] != digest(p) or trail['previous_state']['digest'] != a['base_state_digest'] or trail['state_version'] != x['result_at_state_version'] or not integer(trail['state_version']) or trail['state_version'] > state['state_version'] or trail['previous_state']['version'] != trail['state_version'] - 1 or trail['decision'] != a['decisions'] or not text(trail['timestamp']) or not trail['state_delta']:
            errors.append(x['id'] + ': incomplete outcome provenance')
        if x['result'] != p['result_summary'] or x['status'] != ('failed' if p['execution_status'] == 'failed' else 'done'):
            errors.append(x['id'] + ': source result was overwritten')
        snapshot = next((d['before'] for d in trail['state_delta'] if d['collection'] == 'experiments' and d['id'] == x['id']), None)
        if snapshot is None or packet_errors(p, snapshot): errors.append(x['id'] + ': result source snapshot differs')
        if snapshot is not None:
            current_protocol = {k: v for k, v in x.items() if k not in ('status', 'result', 'result_at_state_version', 'outcome_analysis', 'known_flaws', 'interpretation', 'unexpected', 'next_branches', 'validity')}
            old_protocol = {k: v for k, v in snapshot.items() if k not in ('status', 'result', 'result_at_state_version', 'outcome_analysis', 'known_flaws', 'interpretation', 'unexpected', 'next_branches', 'validity', 'result_pending')}
            if current_protocol != old_protocol: errors.append(x['id'] + ': analysed experimental protocol was rewritten')
        for u in a['claim_updates'] + a['hypothesis_updates']:
            target = index(state, 'claims').get(u['id']) or index(state, 'hypotheses').get(u['id'])
            if target is None or not any(s['analysis_id'] == a['id'] and s['experiment_id'] == x['id'] and s['scope'] == u['scope'] and s['status'] == u['new_status'] and s['scope_relation'] == u['scope_relation'] and s.get('applied') == (experiment_validity(p, a) == 'VALID' and u['identification'] == 'PASS' and u['new_status'] != 'NOT_TESTED') for s in target.get('scoped_outcomes', [])):
                errors.append(x['id'] + ': applied scientific outcome disappeared')
        for d in trail['state_delta']:
            if d['collection'] == 'evidence' and d['before'] is None:
                e = index(state, 'evidence').get(d['id'])
                original = d['after']
                if e is None or any(e.get(k) != v for k, v in original.items() if k != 'validity'):
                    errors.append(x['id'] + ': source outcome evidence disappeared or changed')
        if a['outcome'] != 'POSITIVE_EVIDENCE' or a['stop_rules']:
            matching = [f for f in state['failures'] if f.get('source_analysis_id') == a['id']]
            if len(matching) != 1:
                errors.append(x['id'] + ': outcome needs exactly one original Failure Memory record')
            f = next((f for f in state['failures'] if f.get('source_analysis_id') == a['id']), None)
            if f is None or f.get('failure_attributions') != a['failure_attributions'] or f.get('stop_rules') != a['stop_rules'] or [{k: n[k] for k in n if k not in ('experiment_id', 'evidence_id')} for n in f.get('negative_knowledge', [])] != a['negative_knowledge']:
                errors.append(x['id'] + ': negative knowledge or stop rule disappeared')
    for key in ('claims', 'hypotheses'):
        for target in state[key]:
            if target.get('outcome_status') not in SUPPORT + (None,): errors.append('invalid scientific status')
            scoped = target.get('scoped_outcomes', [])
            versions = []
            for s in scoped:
                record = records.get(s.get('analysis_id'))
                if record is None:
                    errors.append('scientific status has no outcome provenance'); continue
                a = record['analysis']
                u = next((u for u in a['claim_updates'] + a['hypothesis_updates'] if u['id'] == target['id']), None)
                expected = None if u is None else {'analysis_id': a['id'], 'experiment_id': a['experiment_id'],
                    'scope': u['scope'], 'scope_relation': u['scope_relation'], 'status': u['new_status'],
                    'applied': experiment_validity(record['packet'], a) == 'VALID' and u['identification'] == 'PASS' and u['new_status'] != 'NOT_TESTED'}
                if s != expected: errors.append('scoped scientific history differs from its source assessment')
                versions.append(record['audit_trail']['state_version'])
            if versions != sorted(set(versions)): errors.append('scoped scientific history was duplicated or reordered')
            full = [s for s in scoped if s['scope_relation'] == 'FULL' and s['status'] != 'NOT_TESTED' and s.get('applied', True)]
            if full and target.get('outcome_status') != full[-1]['status']: errors.append('global scientific outcome was silently restored or changed')
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('validate', 'apply'):
        p = sub.add_parser(command)
        for arg in ('state', 'packet', 'analysis'): p.add_argument('--' + arg, type=Path, required=True)
        p.add_argument('--audit', type=Path)
        p.add_argument('--execution-ledger', type=Path)
        if command == 'apply': p.add_argument('--output', type=Path, required=True)
    for command in ('constraints', 'check-plan', 'decision'):
        p = sub.add_parser(command); p.add_argument('--state', type=Path, required=True)
        if command != 'constraints': p.add_argument('--experiment', required=True)
        if command == 'decision': p.add_argument('--assurance', type=Path)
    args = parser.parse_args(argv)
    read = lambda p: json.loads(p.read_text(encoding='utf-8')) if p else None
    try:
        state = read(args.state)
        if args.command in ('validate', 'apply'):
            if any(x.get('execution_protocol') and x['status'] != 'planned' for x in state['experiments']):
                import experiment_execute
                execution_errors = experiment_execute.verify_result_execution(state, experiment_execute.Ledger(args.execution_ledger or args.state.parent / '.execution'))
                if execution_errors: raise ValueError('; '.join(execution_errors))
            packet, analysis, audit = read(args.packet), read(args.analysis), read(args.audit)
            result = validate(state, packet, analysis, audit) if args.command == 'validate' else apply(state, packet, analysis, audit)
            if args.command == 'apply' and result['status'] == 'PASS':
                if args.output.resolve() == args.state.resolve(): raise ValueError('write a new state copy; do not overwrite the source snapshot')
                with args.output.open('x', encoding='utf-8') as output:
                    output.write(json.dumps(result['state'], ensure_ascii=False, indent=2) + '\n')
                result.pop('state'); result['output'] = str(args.output)
        elif args.command == 'constraints':
            import state_check
            report = state_check.check_state(state)
            result = {'status': 'PASS', 'constraints': constraints(state)} if report.ok else {'status': 'FAIL', 'errors': ['Failure Memory must come from a passing Research State'], 'state_report': report.as_dict()}
        elif args.command == 'check-plan': result = check_plan(state, args.experiment)
        else: result = decision_gate(state, args.experiment, read(args.assurance))
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        result = {'status': 'INVALID', 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result['status'] == 'PASS' else 3 if result['status'] == 'FAIL' else 4


if __name__ == '__main__':
    raise SystemExit(main())
