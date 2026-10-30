"""One-command checks plus reproducible example answers and timing summary."""
import json
from datetime import datetime, timezone
from analytics import fingerprint
import statistics
import time
import unittest
from pathlib import Path
from engine import answer, EXAMPLES

if __name__ == '__main__':
    root = Path(__file__).parent
    suite = unittest.defaultTestLoader.discover(str(root / 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    results = [{'question': q, **answer(q)} for q in EXAMPLES]
    timings = []
    for _ in range(200):
        t = time.perf_counter()
        answer(EXAMPLES[2])
        timings.append((time.perf_counter() - t) * 1000)
    report = {'test_methods': result.testsRun, 'all_passed': True,
              'engine_timing': {'iterations': 200, 'median_ms': round(statistics.median(timings), 3), 'p95_ms': round(sorted(timings)[189], 3), 'note': 'Local engine only; excludes browser/network/rendering. Not a production benchmark.'},
              'evaluation_scope': 'Small handcrafted regression suite with mocked OpenAI adapter checks; no live model calls or model-quality assessment. Not an estimate of accuracy on unrestricted financial questions. Citation integrity is checked, not remote source availability.',
              'examples': results}
    cases = json.loads((root / 'data/eval_cases.json').read_text(encoding='utf-8'))
    evaluated = []
    for case in cases:
        actual = answer(case['question'])
        status_ok = actual['status'] == case['status']
        numeric_ok = None
        if 'value' in case:
            matching = [r for r in actual['rows'] if r['company'] == case['company'] and r['year'] == case['year'] and r['metric'] == case['metric']]
            numeric_ok = len(matching) == 1 and abs(matching[0]['value'] - case['value']) <= case.get('tolerance', 0.000001)
        ids = {s['id'] for s in actual['evidence']}
        citation_ok = all(r['source_id'] in ids for r in actual['rows']) and (bool(ids) if actual['status'] == 'answered' else not actual['rows'] and not ids)
        passed = status_ok and numeric_ok is not False and citation_ok
        evaluated.append({**case, 'actual_status':actual['status'], 'actual_answer':actual['answer'], 'status_ok':status_ok, 'numeric_ok':numeric_ok, 'citation_ok':citation_ok, 'passed':passed, 'latency_ms':actual['latency_ms']})
    report.update({'generated_at':datetime.now(timezone.utc).isoformat(), 'fingerprint':fingerprint(), 'cases':evaluated, 'case_count':len(evaluated), 'passed_cases':sum(c['passed'] for c in evaluated), 'model_calls':0, 'model_cost_inr':0})
    report['all_passed'] = report['all_passed'] and all(c['passed'] for c in evaluated)
    (root / 'evaluation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if not report['all_passed']:
        raise SystemExit('Evaluation case failure; inspect evaluation.json.')
    print('Passed. Example answers and evaluation summary written to evaluation.json.')
