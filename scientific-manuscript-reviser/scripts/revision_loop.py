#!/usr/bin/env python3
"""Evaluate a bounded, problem-driven revision loop.

Read-only. The loop records what each round intended to change, whether the
completion condition was met, and what a human still has to decide. It never
expands its own scope, invents evidence or calls an unresolved disagreement solved.

    python3 scripts/revision_loop.py loop.json [--iterations n]

``--iterations n`` is a caller-supplied cap. When the loop declares more rounds
than the cap, only the first n are processed and the truncation is reported.
Exit 0 PASS, 3 FAIL, 4 NEEDS_REVIEW or invalid input.
"""
import argparse
import json
from pathlib import Path

from compare_invariants import nonempty
from evidence_core import (AGREEMENTS, ESCALATION_STATUS, LOOP_STATUS, PROBLEM_STATES, SCHEMAS,
                           STOP_REASONS, SUCCESSFUL_STOPS)
from validate_suggestions import SEVERITY

SCHEMA = SCHEMAS['loop']
RESULTS = ('progress', 'no_change', 'blocked')
LOOP_REQUIRED = {'goal', 'problems', 'iterations', 'stop_reason', 'completion_condition',
                 'completion_met', 'new_evidence'}
LOOP_OPTIONAL = {'schema', 'escalations', 'status'}
PROBLEM_FIELDS = {'id', 'statement', 'severity', 'state', 'iterations', 'resolution'}
ITERATION_REQUIRED = {'id', 'problem_ids', 'target_change', 'completion_criteria',
                      'scientific_disagreement', 'result'}
ITERATION_OPTIONAL = {'new_evidence', 'resolves_problem_ids'}
ESCALATION_FIELDS = {'problem_id', 'issue', 'status', 'resolution'}

NOTE = ('The loop reports bounded progress. ready_to_accept means every processed round carried '
        'a target change and completion criteria, no escalation is pending and the completion '
        'condition is met; it is not an acceptance of the revision. A stop for no progress, '
        'disagreement or an iteration limit with an unmet completion condition stays NEEDS_REVIEW, '
        'and a human decides what remains.')


def _validate_problems(problems):
    errors, clean, seen = [], [], set()
    for index, problem in enumerate(problems):
        label = (problem.get('id') if isinstance(problem, dict) and nonempty(problem.get('id'))
                 else 'problem #%d' % index)
        if not isinstance(problem, dict) or set(problem) != PROBLEM_FIELDS:
            errors.append('invalid problem fields: ' + label)
            continue
        if not nonempty(problem['id']) or not nonempty(problem['statement']):
            errors.append('invalid problem identity or statement: ' + label)
            continue
        if problem['severity'] not in SEVERITY or problem['state'] not in PROBLEM_STATES:
            errors.append('invalid problem severity or state: ' + label)
        if not isinstance(problem['iterations'], list) or any(not nonempty(x) for x in problem['iterations']):
            errors.append('problem iterations must be a list of round ids: ' + label)
        if not isinstance(problem['resolution'], str):
            errors.append('problem resolution must be a string: ' + label)
        if problem['id'] in seen:
            errors.append('duplicate problem id: ' + problem['id'])
            continue
        seen.add(problem['id'])
        clean.append(problem)
    return clean, errors


def _validate_iterations(iterations, problem_ids, known_ids=None):
    """Structural validation only. ``known_ids`` accumulates ids across calls."""
    known_ids = known_ids if known_ids is not None else set()
    errors, clean, seen = [], [], set()
    for index, iteration in enumerate(iterations):
        label = (iteration.get('id') if isinstance(iteration, dict) and nonempty(iteration.get('id'))
                 else 'iteration #%d' % index)
        if not isinstance(iteration, dict):
            errors.append('invalid iteration: ' + label)
            continue
        unknown = set(iteration) - ITERATION_REQUIRED - ITERATION_OPTIONAL
        missing = ITERATION_REQUIRED - set(iteration)
        if unknown or missing:
            parts = []
            if missing:
                parts.append('missing fields: ' + ', '.join(sorted(missing)))
            if unknown:
                parts.append('unknown fields: ' + ', '.join(sorted(unknown)))
            errors.append(label + ': ' + '; '.join(parts))
            continue
        if not nonempty(iteration['id']):
            errors.append('iteration id must be a non-empty string')
            continue
        if not nonempty(iteration['target_change']):
            errors.append('iteration %s needs a non-empty target_change to be a bounded round'
                          % iteration['id'])
        if not nonempty(iteration['completion_criteria']):
            errors.append('iteration %s needs non-empty completion_criteria to be a bounded round'
                          % iteration['id'])
        ids = iteration['problem_ids']
        if not isinstance(ids, list) or any(not nonempty(x) for x in ids) or len(ids) != len(set(ids)):
            errors.append('iteration %s has invalid problem_ids' % iteration['id'])
        elif any(x not in problem_ids for x in ids):
            errors.append('iteration %s names unknown problems' % iteration['id'])
        if iteration['scientific_disagreement'] not in AGREEMENTS:
            errors.append('iteration %s needs a yes/no scientific_disagreement' % iteration['id'])
        if iteration['result'] not in RESULTS:
            errors.append('iteration %s has an invalid result' % iteration['id'])
        for key in ('new_evidence',):
            if key in iteration and type(iteration[key]) is not bool:
                errors.append('iteration %s field %s must be boolean' % (iteration['id'], key))
        resolves = iteration.get('resolves_problem_ids', [])
        if not isinstance(resolves, list) or any(not nonempty(x) for x in resolves) or len(resolves) != len(set(resolves)):
            errors.append('iteration %s has invalid resolves_problem_ids' % iteration['id'])
        elif any(x not in problem_ids for x in resolves):
            errors.append('iteration %s resolves unknown problems' % iteration['id'])
        if iteration['id'] in seen:
            errors.append('duplicate iteration id: ' + iteration['id'])
            continue
        seen.add(iteration['id'])
        known_ids.add(iteration['id'])
        clean.append(iteration)
    return clean, errors, known_ids


def _validate_escalations(escalations):
    errors, clean = [], []
    for index, escalation in enumerate(escalations):
        label = 'escalation #%d' % index
        if not isinstance(escalation, dict) or set(escalation) - ESCALATION_FIELDS:
            errors.append('invalid escalation fields: ' + label)
            continue
        if not nonempty(escalation.get('problem_id')) and not nonempty(escalation.get('issue')):
            errors.append('escalation needs a problem_id or an issue: ' + label)
            continue
        if escalation.get('status') not in ESCALATION_STATUS:
            errors.append('escalation needs a pending/resolved status: ' + label)
            continue
        if escalation['status'] == 'resolved' and not nonempty(escalation.get('resolution')):
            errors.append('a resolved escalation needs a resolution: ' + label)
        clean.append(escalation)
    return clean, errors


def _agreement_covered(escalation, iteration):
    """A matching escalation already records the disagreement, pending or resolved."""
    if escalation.get('status') not in ESCALATION_STATUS:
        return False
    if escalation.get('problem_id') is not None:
        return escalation['problem_id'] in iteration['problem_ids']
    return escalation.get('issue') == 'scientific_disagreement'


def evaluate(artifact, cap=None):
    errors, unresolved, human_decisions = [], [], []
    if not isinstance(artifact, dict):
        return {'schema': SCHEMA, 'status': 'INVALID', 'errors': ['loop artifact must be an object']}
    unknown = set(artifact) - LOOP_REQUIRED - LOOP_OPTIONAL
    missing = LOOP_REQUIRED - set(artifact)
    if unknown or missing:
        parts = []
        if missing:
            parts.append('missing fields: ' + ', '.join(sorted(missing)))
        if unknown:
            parts.append('unknown fields: ' + ', '.join(sorted(unknown)))
        errors.append('invalid loop fields: ' + '; '.join(parts))
    if 'schema' in artifact and artifact['schema'] != SCHEMA:
        errors.append('invalid loop schema')
    goal = artifact.get('goal')
    completion_condition = artifact.get('completion_condition')
    if not nonempty(goal):
        errors.append('goal must be a non-empty string')
    if not nonempty(completion_condition):
        errors.append('completion_condition must be a non-empty string')
    completion_met = artifact.get('completion_met')
    new_evidence = artifact.get('new_evidence')
    if type(completion_met) is not bool:
        errors.append('completion_met must be boolean')
    if type(new_evidence) is not bool:
        errors.append('new_evidence must be boolean')
    stop_reason = artifact.get('stop_reason')
    if stop_reason not in STOP_REASONS:
        errors.append('invalid stop_reason')
    problems = artifact.get('problems') if isinstance(artifact.get('problems'), list) else []
    if not isinstance(artifact.get('problems'), list):
        errors.append('problems must be a list')
    problems, problem_errors = _validate_problems(problems)
    errors.extend(problem_errors)
    problem_ids = {p['id'] for p in problems}
    raw_iterations = artifact.get('iterations') if isinstance(artifact.get('iterations'), list) else []
    if not isinstance(artifact.get('iterations'), list):
        errors.append('iterations must be a list')
    all_iterations, iteration_errors, _ = _validate_iterations(raw_iterations, problem_ids)
    errors.extend(iteration_errors)
    iteration_ids = {i['id'] for i in all_iterations}
    for problem in problems:
        if any(x not in iteration_ids for x in problem['iterations']):
            errors.append('problem %s cites an unknown iteration' % problem['id'])
    raw_escalations = artifact.get('escalations', [])
    if not isinstance(raw_escalations, list):
        errors.append('escalations must be a list')
        raw_escalations = []
    escalations, escalation_errors = _validate_escalations(raw_escalations)
    errors.extend(escalation_errors)

    processed = all_iterations
    if cap is not None:
        if type(cap) is not int or cap < 0:
            errors.append('iteration cap must be a non-negative integer')
        else:
            processed = all_iterations[:cap]
            if len(all_iterations) > cap:
                unresolved.append('iteration cap %d truncated %d later iteration(s); only the first '
                                  '%d were processed' % (cap, len(all_iterations) - cap, cap))

    order = {iteration['id']: index for index, iteration in enumerate(all_iterations)}
    resolved_at, resolution_errors = {}, []
    for iteration in processed:
        for problem_id in iteration.get('resolves_problem_ids', []):
            if problem_id in resolved_at:
                resolution_errors.append('problem %s is resolved more than once' % problem_id)
            else:
                resolved_at[problem_id] = order[iteration['id']]
    for problem in problems:
        declared = resolved_at.get(problem['id'])
        if declared is not None and problem['state'] != 'resolved':
            resolution_errors.append('iteration %s declares problem %s resolved but its state is %s'
                                     % (all_iterations[declared]['id'], problem['id'], problem['state']))
    errors.extend(resolution_errors)

    for problem in problems:
        pid = problem['id']
        if problem['state'] == 'resolved' and not nonempty(problem['resolution']):
            errors.append('resolved problem %s needs a non-empty resolution' % pid)
        names = [order[i['id']] for i in processed if pid in i['problem_ids']]
        declared_names = [order[i['id']] for i in all_iterations if pid in i['problem_ids']]
        if pid in resolved_at:
            base = resolved_at[pid]
        elif problem['iterations']:
            known = [order[x] for x in problem['iterations'] if x in order]
            base = max(known) if known else (min(names) if names else -1)
        else:
            base = min(names) if names else -1
        if problem['state'] == 'resolved':
            for iteration in processed:
                if (pid in iteration['problem_ids'] and order[iteration['id']] > base
                        and not iteration.get('new_evidence', False)):
                    errors.append('resolved problem %s is re-proposed by iteration %s without new '
                                  'evidence' % (pid, iteration['id']))
        if problem['state'] == 'in_progress' and not declared_names:
            errors.append('in_progress problem %s appears in no iteration' % pid)

    if completion_met and stop_reason not in SUCCESSFUL_STOPS:
        errors.append('completion_met is true but stop_reason %s is not a successful stop'
                      % stop_reason)
    if stop_reason in SUCCESSFUL_STOPS and not completion_met:
        errors.append('stop_reason completion_condition_met requires completion_met true')

    if new_evidence and (not processed or all(i['result'] == 'no_change' for i in processed)):
        errors.append('new_evidence is true while no processed iteration reports substantive progress')

    for iteration in processed:
        if iteration['scientific_disagreement'] != 'yes':
            continue
        if not any(_agreement_covered(e, iteration) for e in escalations):
            entry = {'issue': 'scientific_disagreement', 'status': 'pending'}
            if iteration['problem_ids']:
                entry['problem_id'] = iteration['problem_ids'][0]
            escalations.append(entry)

    pending = [e for e in escalations if e.get('status') == 'pending']
    for escalation in pending:
        if escalation.get('problem_id'):
            human_decisions.append('Resolve the pending %s escalation for problem %s before any '
                                   'next-round or acceptance decision.'
                                   % (escalation.get('issue', 'scientific'), escalation['problem_id']))
        else:
            human_decisions.append('Resolve the pending %s escalation before any next-round or '
                                   'acceptance decision.' % escalation.get('issue', 'scientific'))
    for problem in problems:
        if problem['state'] == 'blocked':
            human_decisions.append('Decide how to unblock problem %s: %s' % (problem['id'], problem['statement']))
    if stop_reason in ('no_substantive_progress', 'iteration_limit') and not completion_met:
        human_decisions.append('Decide whether to continue the revision or accept the unmet completion '
                               'condition after %s.' % stop_reason)
    if stop_reason == 'user_stop' and not completion_met:
        human_decisions.append('Decide whether to resume the loop after the explicit user stop and the '
                               'unmet completion condition.')
    if unresolved:
        human_decisions.append('Decide whether to review the iterations beyond the supplied cap.')
    human_decisions = list(dict.fromkeys(human_decisions))

    progress = any(i['result'] == 'progress' for i in processed)
    open_problems = [p['id'] for p in problems if p['state'] in ('open', 'in_progress', 'blocked')]
    if stop_reason == 'completion_condition_met' and completion_met:
        loop_status = 'ready_to_accept'
    elif stop_reason in LOOP_STATUS:
        loop_status = stop_reason
    else:
        loop_status = 'in_progress'
    if errors:
        status = 'FAIL'
    elif pending or unresolved or stop_reason not in SUCCESSFUL_STOPS:
        status = 'NEEDS_REVIEW'
    else:
        status = 'PASS'
    return {'schema': SCHEMA, 'goal': goal, 'problems': problems, 'iterations': processed,
            'stop_reason': stop_reason, 'completion_condition': completion_condition,
            'completion_met': completion_met, 'new_evidence': new_evidence, 'status': status,
            'loop_status': loop_status, 'escalations': escalations, 'progress': progress,
            'open_problems': open_problems, 'human_decisions': human_decisions,
            'errors': errors, 'unresolved': unresolved, 'note': NOTE}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('loop', type=Path)
    parser.add_argument('--iterations', type=int, default=None,
                        help='process at most this many declared rounds')
    args = parser.parse_args()
    try:
        result = evaluate(json.loads(args.loop.read_text(encoding='utf-8')), args.iterations)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, AttributeError) as exc:
        result = {'status': 'INVALID', 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return {'PASS': 0, 'FAIL': 3}.get(result.get('status'), 4)


if __name__ == '__main__':
    raise SystemExit(main())
