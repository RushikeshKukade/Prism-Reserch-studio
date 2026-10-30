"""Auditable quality checks and an exact two-step operating-profit bridge."""
import copy
import hashlib
import json
from datetime import date
from pathlib import Path
from engine import DATA

ROOT = Path(__file__).parent


def fingerprint():
    digest = hashlib.sha256()
    for name in ['app.py', 'engine.py', 'analytics.py', 'reviews.py', 'market.py', 'universe.py', 'data/universe.json', 'tests/test_universe.py', 'data/recent_results.json', 'tests/test_market.py', 'evaluate.py', 'data/companies.json', 'data/eval_cases.json', 'tests/test_research.py', 'tests/test_analytics.py']:
        p = ROOT / name
        digest.update(name.encode())
        digest.update(p.read_bytes() if p.exists() else b'MISSING')
    return digest.hexdigest()


def quality_report(data=None, as_of=None):
    data = DATA if data is None else data
    as_of = as_of or date.today()
    checks = []
    def add(company, check, status, detail):
        checks.append(dict(company=company, check=check, status=status, detail=detail))
    add('Dataset', 'Currency and units', 'pass' if data.get('currency') == 'INR' and data.get('unit') == 'crore' else 'fail', 'Expected INR crore; all issuers must share these units.')
    for c in data.get('companies', []):
        name, years, source = c['name'], c.get('years', {}), c.get('source', {})
        complete = all(y in years and all(isinstance(years[y].get(m), (int, float)) and not isinstance(years[y].get(m), bool) for m in ['revenue', 'operating_profit']) for y in ['2023', '2024'])
        add(name, 'Required observations', 'pass' if complete else 'fail', 'Two annual periods × revenue and operating profit required; no filling missing values.')
        valid = complete and all(d['revenue'] > 0 and 0 <= d['operating_profit'] <= d['revenue'] for d in years.values())
        add(name, 'Numeric plausibility', 'pass' if valid else 'fail', 'Revenue > 0 and operating profit between zero and revenue. This heuristic is not proof of accounting accuracy.')
        aligned = all(y in years and years[y].get('period_start') == f'{int(y)-1}-04-01' and years[y].get('period_end') == f'{y}-03-31' for y in ['2023','2024'])
        add(name, 'Fiscal-year alignment', 'pass' if aligned else 'fail', 'April–March annual periods; consolidated scope is documented in issuer basis.')
        add(name, 'Source locator', 'pass' if source.get('url','').startswith('https://') and source.get('locator') else 'fail', source.get('locator') or 'Source URL or document locator missing.')
        add(name, 'Publication timestamp', 'pass' if source.get('publication_date') else 'warning', 'Missing publication date: do not use this snapshot for point-in-time backtests or as-of queries.')
        add(name, 'Operating-profit comparability', 'warning', c.get('basis','Metric basis missing.'))
        try:
            age = (as_of - date.fromisoformat(max(d['period_end'] for d in years.values()))).days
            add(name, 'Observation freshness', 'warning' if age > 730 else 'pass', f'Newest financial period ended {age} days before {as_of.isoformat()}. Historical-demo threshold: 730 days; not the source verification age.')
        except (ValueError, KeyError):
            add(name, 'Observation freshness', 'fail', 'Cannot determine the newest period end.')
    return {'as_of': as_of.isoformat(), 'counts': {s: sum(c['status'] == s for c in checks) for s in ['pass','warning','fail']}, 'checks': checks, 'limitations': 'These are schema, plausibility and metadata checks. They do not independently audit the figures, establish source authenticity, or check live source-link availability. No composite quality score is assigned.'}


def change_bridge(company_id):
    c = next((c for c in DATA['companies'] if c['id'] == company_id), None)
    if c is None:
        raise ValueError('Unknown company')
    a, b = c['years']['2023'], c['years']['2024']
    r0, r1, p0, p1 = a['revenue'], b['revenue'], a['operating_profit'], b['operating_profit']
    m0, m1 = p0 / r0, p1 / r1
    scale, margin = (r1-r0)*m0, r1*(m1-m0)
    return {'company':c['name'], 'company_id':c['id'], 'unit':'INR crore', 'from':'FY2023', 'to':'FY2024',
            'revenue_before':r0, 'revenue_after':r1, 'profit_before':p0, 'profit_after':p1,
            'revenue_growth_pct':(r1/r0-1)*100, 'margin_before_pct':m0*100, 'margin_after_pct':m1*100,
            'margin_change_pp':(m1-m0)*100, 'scale_effect':scale, 'margin_effect':margin,
            'profit_change':p1-p0, 'reconciliation_error':scale+margin-(p1-p0),
            'formulas': ['Scale effect = (FY2024 revenue − FY2023 revenue) × FY2023 operating margin', 'Margin effect = FY2024 revenue × (FY2024 margin − FY2023 margin)', 'Profit change = scale effect + margin effect'],
            'basis':c['basis'], 'source':copy.deepcopy(c['source']),
            'limitation':'Exact arithmetic decomposition, not a causal explanation. Revenue changes first at the old margin; margin changes second at the new revenue. This ordering assigns the interaction term to the margin effect. No FX, acquisition, pricing or volume attribution is available.'}


def saved_evaluation():
    path = ROOT / 'evaluation.json'
    if not path.exists():
        return {'available':False, 'message':'Run python evaluate.py to generate a report.'}
    result = json.loads(path.read_text(encoding='utf-8'))
    result['available'] = True
    result['stale'] = result.get('fingerprint') != fingerprint()
    return result
