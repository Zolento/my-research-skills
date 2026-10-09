import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import revision_loop as rl


def problem(pid, state='open', iterations=None, resolution='', severity='major', statement='Located problem.'):
    return {'id': pid, 'statement': statement, 'severity': severity, 'state': state,
            'iterations': list(iterations or []), 'resolution': resolution}


def iteration(iid, problems, target='Restate the claim.', criteria='Claim matches evidence.',
              disagreement='no', result='progress', **extra):
    item = {'id': iid, 'problem_ids': list(problems), 'target_change': target,
            'completion_criteria': criteria, 'scientific_disagreement': disagreement, 'result': result}
    item.update(extra)
    return item


def loop(**overrides):
    base = {'schema': 'bounded-revision-loop@1',
            'goal': 'Repair the located scientific problems.',
            'problems': [problem('P1', 'resolved', ['I1'], 'Claim restated at the evidence strength.')],
            'iterations': [iteration('I1', ['P1'])],
            'stop_reason': 'completion_condition_met',
            'completion_condition': 'Every problem resolved and no escalation pending.',
            'completion_met': True, 'new_evidence': False, 'escalations': []}
    base.update(overrides)
    return base


class RevisionLoopTests(unittest.TestCase):
    def test_met_completion_condition_reaches_ready_to_accept(self):
        result = rl.evaluate(loop())
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['loop_status'], 'ready_to_accept')
        self.assertTrue(result['progress'])
        self.assertEqual(result['open_problems'], [])
        self.assertFalse(result['escalations'])

    def test_stop_with_unmet_completion_is_needs_review(self):
        result = rl.evaluate(loop(stop_reason='no_substantive_progress', completion_met=False))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertEqual(result['loop_status'], 'no_substantive_progress')
        self.assertFalse(result['completion_met'])
        self.assertTrue(result['human_decisions'])

    def test_iteration_limit_with_unmet_completion_is_needs_review(self):
        result = rl.evaluate(loop(stop_reason='iteration_limit', completion_met=False))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertEqual(result['loop_status'], 'iteration_limit')

    def test_user_stop_with_unmet_completion_is_needs_review(self):
        result = rl.evaluate(loop(stop_reason='user_stop', completion_met=False))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertNotIn(result['loop_status'], ('ready_to_accept',))

    def test_reproposed_resolved_problem_fails(self):
        artifact = loop(problems=[problem('P1', 'resolved', ['I1'], 'Claim restated.')],
                        iterations=[iteration('I1', ['P1']),
                                    iteration('I2', ['P1'], result='blocked', disagreement='yes')],
                        stop_reason='scientific_disagreement', completion_met=False)
        result = rl.evaluate(artifact)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('re-proposed by iteration I2' in e for e in result['errors']))

    def test_reproposal_with_declared_new_evidence_is_allowed(self):
        artifact = loop(problems=[problem('P1', 'resolved', ['I1'], 'Claim restated.')],
                        iterations=[iteration('I1', ['P1']),
                                    iteration('I2', ['P1'], result='progress', new_evidence=True)],
                        stop_reason='iteration_limit', completion_met=False)
        result = rl.evaluate(artifact)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['status'], 'NEEDS_REVIEW')

    def test_explicit_resolution_declaration_orders_the_problem(self):
        artifact = loop(problems=[problem('P1', 'resolved', ['I1', 'I2'], 'Claim restated.')],
                        iterations=[iteration('I1', ['P1'], result='progress',
                                              resolves_problem_ids=['P1']),
                                    iteration('I2', ['P1'], result='blocked')],
                        stop_reason='iteration_limit', completion_met=False)
        result = rl.evaluate(artifact)
        self.assertTrue(any('re-proposed by iteration I2' in e for e in result['errors']))

    def test_resolved_problem_needs_a_resolution(self):
        result = rl.evaluate(loop(problems=[problem('P1', 'resolved', ['I1'], '')]))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('needs a non-empty resolution' in e for e in result['errors']))

    def test_iteration_without_target_change_fails(self):
        result = rl.evaluate(loop(iterations=[iteration('I1', ['P1'], target='   ')]))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('target_change' in e for e in result['errors']))

    def test_iteration_without_completion_criteria_fails(self):
        result = rl.evaluate(loop(iterations=[iteration('I1', ['P1'], criteria='')]))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('completion_criteria' in e for e in result['errors']))

    def test_in_progress_problem_must_appear_in_an_iteration(self):
        artifact = loop(problems=[problem('P1', 'in_progress', [], ''),
                                  problem('P2', 'resolved', ['I1'], 'Resolved.')],
                        iterations=[iteration('I1', ['P2'])])
        result = rl.evaluate(artifact)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('appears in no iteration' in e for e in result['errors']))

    def test_scientific_disagreement_creates_a_pending_escalation(self):
        artifact = loop(problems=[problem('P1', 'open', ['I1'])],
                        iterations=[iteration('I1', ['P1'], result='blocked', disagreement='yes')],
                        stop_reason='scientific_disagreement', completion_met=False)
        result = rl.evaluate(artifact)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        pending = [e for e in result['escalations'] if e['status'] == 'pending']
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]['issue'], 'scientific_disagreement')
        self.assertEqual(pending[0]['problem_id'], 'P1')
        self.assertTrue(result['human_decisions'])

    def test_supplied_pending_disagreement_escalation_is_not_duplicated(self):
        artifact = loop(problems=[problem('P1', 'open', ['I1'])],
                        iterations=[iteration('I1', ['P1'], result='blocked', disagreement='yes')],
                        stop_reason='scientific_disagreement', completion_met=False,
                        escalations=[{'problem_id': 'P1', 'issue': 'scientific_disagreement',
                                      'status': 'pending'}])
        result = rl.evaluate(artifact)
        self.assertEqual(len(result['escalations']), 1)

    def test_explicitly_resolved_disagreement_does_not_block_completion(self):
        artifact = loop(problems=[problem('P1', 'resolved', ['I1'], 'Resolved by agreement.')],
                        iterations=[iteration('I1', ['P1'], disagreement='yes')],
                        escalations=[{'problem_id': 'P1', 'issue': 'scientific_disagreement',
                                      'status': 'resolved', 'resolution': 'Authors resolved the scope.'}])
        result = rl.evaluate(artifact)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['loop_status'], 'ready_to_accept')

    def test_resolved_escalation_needs_a_resolution(self):
        result = rl.evaluate(loop(escalations=[{'problem_id': 'P1', 'status': 'resolved'}]))
        self.assertEqual(result['status'], 'FAIL')

    def test_completion_met_with_a_non_success_stop_fails(self):
        result = rl.evaluate(loop(stop_reason='no_substantive_progress', completion_met=True))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('is not a successful stop' in e for e in result['errors']))

    def test_success_stop_requires_completion_met(self):
        result = rl.evaluate(loop(completion_met=False))
        self.assertEqual(result['status'], 'FAIL')

    def test_new_evidence_while_every_result_is_no_change_fails(self):
        result = rl.evaluate(loop(new_evidence=True,
                                  iterations=[iteration('I1', ['P1'], result='no_change')],
                                  stop_reason='iteration_limit', completion_met=False))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('no processed iteration reports substantive progress' in e
                            for e in result['errors']))

    def test_new_evidence_must_be_boolean(self):
        result = rl.evaluate(loop(new_evidence='yes'))
        self.assertEqual(result['status'], 'FAIL')

    def test_invalid_stop_reason_fails(self):
        result = rl.evaluate(loop(stop_reason='stopped_because_we_felt_done'))
        self.assertEqual(result['status'], 'FAIL')

    def test_invalid_problem_state_fails(self):
        artifact = loop(problems=[problem('P1', 'done', ['I1'], 'Resolved.')])
        result = rl.evaluate(artifact)
        self.assertEqual(result['status'], 'FAIL')

    def test_iteration_cap_truncates_and_reports(self):
        artifact = loop(problems=[problem('P1', 'open', ['I2'])],
                        iterations=[iteration('I1', ['P1']),
                                    iteration('I2', ['P1'], result='blocked')],
                        stop_reason='iteration_limit', completion_met=False)
        result = rl.evaluate(artifact, cap=1)
        self.assertEqual(len(result['iterations']), 1)
        self.assertEqual(result['iterations'][0]['id'], 'I1')
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(any('truncated' in u for u in result['unresolved']))
        self.assertTrue(result['human_decisions'])

    def test_cap_does_not_falsely_fail_an_unprocessed_in_progress_problem(self):
        artifact = loop(problems=[problem('P1', 'in_progress', ['I2']),
                                  problem('P2', 'resolved', ['I1'], 'Resolved.')],
                        iterations=[iteration('I1', ['P2']),
                                    iteration('I2', ['P1'], result='blocked')],
                        stop_reason='iteration_limit', completion_met=False)
        result = rl.evaluate(artifact, cap=1)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['status'], 'NEEDS_REVIEW')

    def test_output_reports_open_problems_and_never_claims_acceptance(self):
        artifact = loop(problems=[problem('P1', 'resolved', ['I1'], 'Resolved.'),
                                  problem('P2', 'blocked', ['I2'], '', statement='Missing control.')],
                        iterations=[iteration('I1', ['P1']),
                                    iteration('I2', ['P2'], result='blocked')],
                        stop_reason='scientific_disagreement', completion_met=False)
        result = rl.evaluate(artifact)
        self.assertIn('P2', result['open_problems'])
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertNotIn('accepted', json.dumps(result))
        self.assertTrue(any('P2' in decision for decision in result['human_decisions']))

    def test_bundled_loop_example_stays_needs_review(self):
        path = (pathlib.Path(__file__).resolve().parents[1] / 'examples' / 'revision-impact'
                / 'loop.json')
        result = rl.evaluate(json.loads(path.read_text(encoding='utf-8')))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertEqual(result['loop_status'], 'scientific_disagreement')
        self.assertIn('P2', result['open_problems'])
        self.assertTrue(any(e['status'] == 'pending' for e in result['escalations']))
        self.assertTrue(result['human_decisions'])
        self.assertNotEqual(result['loop_status'], 'ready_to_accept')


if __name__ == '__main__':
    unittest.main()
