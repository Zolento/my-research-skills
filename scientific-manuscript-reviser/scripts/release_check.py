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
import validate_style
import validate_suggestions

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def links():
    failures = []
    for path in ROOT.rglob('*.md'):
        for target in re.findall(r'\[[^\]\n]+\]\(([^)\s]+)\)', path.read_text()):
            if target.startswith(('http:', 'https:', '#')):
                continue
            local = (path.parent / target.split('#')[0]).resolve()
            if not local.is_relative_to(ROOT) or not local.exists():
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


def main():
    checks = []
    proc = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'],
                          cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    tail = [x for x in proc.stdout.splitlines() if x.startswith(('Ran ', 'OK', 'FAILED'))]
    checks.append(('Regression tests', proc.returncode == 0, ' · '.join(tail)))
    if proc.returncode:
        print(proc.stdout)
    try:
        for name, function in (('Self-contained reference links', links), ('Real section and Architect examples', examples)):
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
