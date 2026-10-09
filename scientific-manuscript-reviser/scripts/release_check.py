#!/usr/bin/env python3
"""Standalone package release gate. Exit 0 and final PASS are both required."""
import json
from pathlib import Path
import re
import subprocess
import sys

import architect
import audit_coherence
import compare_invariants
import counterfactual_eval
import evidence_core
import evidence_ledger
import revision_impact
import revision_loop
import validate_style
import validate_suggestions

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def links():
    failures = []
    for path in ROOT.rglob('*.md'):
        if '.dev' in path.relative_to(ROOT).parts:
            continue
        for target in re.findall(r'\[[^\]\n]+\]\(([^)\s]+)\)', path.read_text()):
            if target.startswith(('http:', 'https:', '#')):
                continue
            local = (path.parent / target.split('#')[0]).resolve()
            if not local.is_relative_to(ROOT) or not local.exists() or '.dev' in local.relative_to(ROOT).parts:
                failures.append(str(path.relative_to(ROOT)) + ' → ' + target)
    return failures


def examples():
    errors = []
    folder = ROOT / 'examples' / 'real-section'
    before, after = (folder / 'input.txt').read_text(), (folder / 'proposed-revision.txt').read_text()
    invariance = compare_invariants.compare(before, after, read(folder / 'before-facts.json'),
                                            read(folder / 'after-facts.json'), read(folder / 'semantic-audit.json'))
    coherence = audit_coherence.audit(before, read(folder / 'graph.json'), read(folder / 'coherence-report.json'))
    bank = validate_suggestions.validate(before, read(folder / 'suggestions.json'), coherence)
    if invariance['status'] != 'PASS' or validate_style.validate(after)['status'] != 'PASS':
        errors.append('real-section invariance/style failed')
    if coherence['status'] != 'NEEDS_REVIEW' or coherence['errors'] or bank['status'] != 'PASS' or bank['revision_ready']:
        errors.append('partial real section incorrectly certified or invalid bank')
    folder = ROOT / 'examples' / 'architect-bounded'
    result = architect.validate_blueprint(*(read(folder / p) for p in
                                           ('materials.json', 'graph.json', 'coherence-report.json', 'blueprint.json', 'outline-audit.json')))
    if result['status'] != 'PASS':
        errors.append('Architect source/outline gate failed: ' + str(result['errors']))
    return errors


def evidence_examples():
    """Run the v0.2.0 gates on their bundled examples and check the honest invariants.

    These are deterministic contract and provenance checks. They never measure semantic
    detection ability and never certify a scientific claim.
    """
    errors = []
    if evidence_core.self_check() != 0:
        errors.append('evidence_core contract self-check failed')

    def cli(script, args):
        proc = subprocess.run([sys.executable, str(ROOT / 'scripts' / script), *args],
                              cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.stderr.strip():
            errors.append(script + ' wrote to stderr')
        return proc.returncode

    folder = ROOT / 'examples' / 'evidence-ledger'
    if cli('evidence_ledger.py', [str(folder / 'manuscript.md'), '--ledger', str(folder / 'ledger.json'),
                                  '--graph', str(folder / 'graph.json')]) not in (0, 4):
        errors.append('evidence ledger example did not run cleanly')
    else:
        ledger = read(folder / 'ledger.json')
        for artifact in ledger['artifacts']:
            path = (ROOT / artifact['reference']).resolve()
            if not path.is_file() or evidence_core.source_digest(path) != artifact['digest']:
                errors.append('ledger artifact is unresolvable or stale: ' + artifact['id'])
        for record in ledger['evidence']:
            artifact = next(a for a in ledger['artifacts'] if a['id'] == record['artifact_id'])
            if not evidence_core.defensible_verification(artifact['type'], record['verification_method'],
                                                         record['state']):
                errors.append('unsound evidence state: ' + record['id'])

    folder = ROOT / 'examples' / 'counterfactual'
    case_set = read(folder / 'evaluation.json')
    classes = {case['class'] for case in case_set['cases']}
    if not set(evidence_core.FAULTY_CLASSES) <= classes:
        errors.append('counterfactual example does not cover every faulty class')
    if not set(evidence_core.ROBUSTNESS_CLASSES) <= classes:
        errors.append('counterfactual example lacks a robustness case of each kind')
    for case in case_set['cases']:
        if case['class'] in evidence_core.DEFECT_CLASSES and case['faulty_defect'] not in case['faulty']:
            errors.append('declared defect is absent from the faulty variant: ' + case['id'])
        if case['class'] == 'robustness_paraphrase' and (case['faulty_defect'] or any(case['faulty_span'].values())):
            errors.append('a wording-only robustness case must declare no defect: ' + case['id'])
    if cli('counterfactual_eval.py', [str(folder / 'evaluation.json')]) not in (0, 4):
        errors.append('counterfactual harness did not run cleanly')
    if cli('counterfactual_eval.py', [str(folder / 'evaluation.json'),
                                      '--detection', str(folder / 'detection.json')]) not in (0, 4):
        errors.append('counterfactual harness rejected the bundled detection artifact')

    folder = ROOT / 'examples' / 'revision-impact'
    if cli('revision_impact.py', [str(folder / 'after.md'), '--before', str(folder / 'before.md'),
                                  '--original-facts', str(folder / 'before-facts.json'),
                                  '--revised-facts', str(folder / 'after-facts.json'),
                                  '--plan', str(folder / 'plan.json'),
                                  '--graph', str(folder / 'graph.json')]) not in (0, 4):
        errors.append('revision impact example did not run cleanly')
    if cli('revision_loop.py', [str(folder / 'loop.json')]) not in (0, 3, 4):
        errors.append('bounded revision loop example did not run cleanly')
    return errors


def main():
    checks = []
    proc = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'],
                          cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    tail = [x for x in proc.stdout.splitlines() if x.startswith(('Ran ', 'OK', 'FAILED'))]
    checks.append(('Regression tests', proc.returncode == 0, ' · '.join(tail)))
    if proc.returncode:
        print(proc.stdout)
    try:
        for name, function in (('Self-contained reference links', links),
                               ('Real section and Architect examples', examples),
                               ('Evidence grounding examples and contract', evidence_examples)):
            errors = function()
            checks.append((name, not errors, str(errors) if errors else 'ok'))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        checks.append(('Package artifacts', False, str(exc)))
    for name, passed, message in checks:
        print(('OK   ' if passed else 'FAIL ') + name + ' — ' + message)
    passed = all(x[1] for x in checks)
    print('PASS' if passed else 'FAIL')
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
