"""Small, auditable financial question engine. No model or network calls."""
import json
import re
import time
from reviews import is_review_request, research_review
from pathlib import Path

DATA = json.loads((Path(__file__).parent / 'data/companies.json').read_text(encoding='utf-8'))
EXAMPLES = [
    'Compare revenue for TCS, Infosys and HCLTech in FY2024',
    'Which company had the highest operating margin in FY2024?',
    'How did Infosys revenue grow from FY2023 to FY2024?',
    'How did TCS operating margin change from FY2023 to FY2024?',
    'Show HCLTech operating profit in FY2024',
]


def indian_number(value):
    s = str(abs(int(round(value))))
    groups = [s[-3:]]
    s = s[:-3]
    while s:
        groups.insert(0, s[-2:])
        s = s[:-2]
    return ('-' if value < 0 else '') + ','.join(groups)


def _refuse(reason):
    return {'status': 'insufficient_information', 'answer': reason,
            'rows': [], 'evidence': [], 'calculations': [], 'warnings': [],
            'suggestions': EXAMPLES, 'mode': 'Deterministic evidence engine; no LLM'}


def _years(text):
    # Indian FY2023-24 and FY23-24 both mean the year ending March 2024.
    text = re.sub(r'\b(?:fy\s*)?(20\d{2})\s*[-/]\s*(\d{2})\b', lambda m: '20' + m[2], text)
    text = re.sub(r'\bfy\s*(\d{2})\s*[-/]\s*(\d{2})\b', lambda m: '20' + m[2], text)
    text = re.sub(r'\bfy\s*(\d{2})\b', lambda m: '20' + m[1], text)
    text = re.sub(r'\bfy\s*(?=20\d{2})', '', text)
    return sorted(set(re.findall(r'\b20\d{2}\b', text)))


def answer(question):
    start = time.perf_counter()
    result = _answer(question)
    result['latency_ms'] = round((time.perf_counter() - start) * 1000, 3)
    result['model_calls'] = 0
    result['model_cost_inr'] = 0
    result['snapshot'] = DATA['snapshot']
    result['verified_on'] = DATA['verified_on']
    return result


def _answer(question):
    if not isinstance(question, str) or not question.strip():
        return _refuse('Enter a question about revenue, operating profit or operating margin.')
    if len(question) > 1000:
        return _refuse('Keep your question under 1,000 characters.')
    if is_review_request(question):
        return research_review()
    q = question.lower().replace('\u2013', '-').replace('\u2014', '-')
    # Fail closed for unsupported requests, even when mixed with a supported metric.
    unsupported = r'\b(ebitda|eps|net\s+(?:profit|income|margin)|pat|p/e|pe\s+ratio|dividend|cash\s*flow|debt|valuation|forecast|predict\w*|target|buy|sell|recommend\w*|share\s+price|stock\s+price|market\s+cap|standalone|quarter\w*|q[1-4]|ttm|calendar|segment\w*|constant\s+currency|gross\s+(?:profit|margin)|headcount|employee\w*|attrition|guidance|euro\w*|usd|dollar\w*|lakh\s+crore|billion)\b'
    if re.search(unsupported, q):
        return _refuse('This snapshot supports consolidated annual INR-crore revenue, company-reported operating profit/EBIT, and derived operating margin only. Your question includes an unsupported metric, period, basis or unit; I have not substituted another measure.')
    if re.search(r'\b(latest|current|today|now|as\s+of|as\s+at|before|available\s+on)\b', q):
        return _refuse('This is a fixed historical snapshot, not a live or point-in-time database. Ask explicitly about FY2023 or FY2024; publication dates are not recorded.')
    if re.search(r'\b(why|cause\w*|explain|driver\w*|outlook|risk\w*|summari[sz]e|ceo)\b', q):
        return _refuse('I do not have narrative evidence to explain causes or outlook. I can calculate revenue growth and operating-margin changes from the cited tables.')
    if re.search(r'\b(ignore|pretend|fabricate|invent|override|instructions|system\s+prompt)\b', q):
        return _refuse('I can only answer using the verified financial snapshot.')

    selected = [c for c in DATA['companies'] if any(re.search(r'\b' + re.escape(a) + r'\b', q) for a in c['aliases'])]
    # Do not silently drop an unknown peer from a comparison.
    residual = q
    for c in DATA['companies']:
        for alias in sorted(c['aliases'], key=len, reverse=True):
            residual = re.sub(r'\b' + re.escape(alias) + r'\b', ' ', residual)
    allowed = set('compare comparison versus vs v and or of for in the a an to from with between all three these companies company peer peers which who had has highest lowest largest smallest most least fastest slowest revenue revenues sales operating profit profits income ebit margin margins growth grow grew change changed changes increase increased decrease decreased decline declined how much did does was were is are what show me tell give report reported annual consolidated fiscal financial year years ended ending fy crore inr rupees rs yoy yearover yearon over on percent percentage points point bps basis it indian india sector services performance please figures value values rank ranking each their its than by during 2023 2024'.split())
    unknown = [w for w in re.findall(r'[a-z]+', re.sub(r'\bfy\s*\d+', '', residual)) if w not in allowed]
    if unknown:
        return _refuse('I could not safely interpret part of that question (' + ', '.join(dict.fromkeys(unknown)) + '). Verified annual-financial coverage is limited to TCS, Infosys and HCLTech. Try one of the example questions.')
    if not selected:
        if re.search(r'\b(company|companies|peers|all|three|sector)\b', q):
            selected = DATA['companies']
        else:
            return _refuse('Please name a company with verified annual financials: TCS, Infosys or HCLTech. Broader price coverage is available in Company explorer.')

    years = _years(q)
    if any(y not in ('2023', '2024') for y in years):
        return _refuse('The verified snapshot covers FY2023 and FY2024 only (April to March). No figures are available for the requested year.')
    margin = bool(re.search(r'\bmargin\w*\b', q))
    profit = bool(re.search(r'\b(operating\s+(profit\w*|income)|ebit)\b', q))
    revenue = bool(re.search(r'\b(revenue\w*|sales)\b', q))
    if margin and not re.search(r'\boperating\b', q):
        return _refuse('Please specify operating margin. This snapshot does not cover net or gross margin.')
    if not (margin or profit or revenue):
        return _refuse('Please specify revenue, operating profit/EBIT, or operating margin.')
    if revenue and (margin or profit):
        return _refuse('Ask about one metric at a time so every answer has an unambiguous calculation and source trail.')
    metric = 'operating_margin' if margin else 'operating_profit' if profit else 'revenue'
    change = bool(re.search(r'\b(growth|grow|grew|change\w*|increase\w*|decrease\w*|declin\w*|yoy)\b', q))
    if change:
        if years == ['2023']:
            return _refuse('FY2023 growth requires FY2022, which is outside this snapshot.')
        years = ['2023', '2024']
    if not years:
        return _refuse('Please specify FY2023 or FY2024. I do not assume that the snapshot is current.')

    rows, calculations, evidence = [], [], []
    for c in selected:
        vals = {}
        evidence.append({**c['source'], 'company': c['name'], 'basis': c['basis'], 'verified_on': DATA['verified_on'], 'rows': c['source_rows']})
        for y in years:
            d = c['years'][y]
            val = d['operating_profit'] / d['revenue'] * 100 if margin else d[metric]
            vals[y] = val
            rows.append({'company': c['name'], 'company_id': c['id'], 'year': y,
                         'period_end': d['period_end'], 'metric': metric, 'value': val,
                         'display': f'{val:.2f}%' if margin else f'\u20b9{indian_number(val)} crore',
                         'unit': '%' if margin else 'INR crore', 'source_id': c['source']['id']})
            if margin:
                calculations.append({'company': c['name'], 'year': y, 'formula': 'Operating profit / revenue × 100', 'substitution': f"{d['operating_profit']} / {d['revenue']} × 100 = {val:.4f}%", 'source_ids': [c['source']['id']]})
        if change:
            delta = vals['2024'] - vals['2023'] if margin else (vals['2024'] / vals['2023'] - 1) * 100
            rows.append({'company': c['name'], 'company_id': c['id'], 'year': '2023 → 2024', 'period_end': '2024-03-31', 'metric': 'change', 'value': delta, 'display': f'{delta:+.2f} pp' if margin else f'{delta:+.2f}%', 'unit': 'percentage points' if margin else '% YoY', 'source_id': c['source']['id']})
            calculations.append({'company': c['name'], 'year': '2023 → 2024', 'formula': 'FY2024 margin − FY2023 margin (percentage points)' if margin else '(FY2024 / FY2023 − 1) × 100', 'substitution': f'{delta:+.4f} ' + ('pp' if margin else '%'), 'source_ids': [c['source']['id']]})

    label = {'revenue': 'revenue', 'operating_profit': 'company-reported operating profit / EBIT', 'operating_margin': 'derived operating margin'}[metric]
    rank = bool(re.search(r'\b(highest|lowest|largest|smallest|fastest|slowest|rank)\b', q))
    relevant = [r for r in rows if r['metric'] == ('change' if change else metric) and (change or r['year'] == years[-1])]
    if rank:
        ascending = bool(re.search(r'\b(lowest|smallest|slowest)\b', q))
        ranked = sorted(relevant, key=lambda r: r['value'], reverse=not ascending)
        best = ranked[0]
        answer_text = f"Among the {len(selected)} selected companies, {best['company']} has the {'lowest' if ascending else 'highest'} {'change in ' if change else ''}{label}: {best['display']} ({best['year']})."
    elif change:
        answer_text = '; '.join(f"{r['company']}: {label} changed {r['display']} from FY2023 to FY2024" for r in relevant) + '.'
    else:
        answer_text = '; '.join(f"{r['company']} FY{r['year']} {label}: {r['display']}" for r in rows) + '.'
    warnings = ['Historical snapshot only: FY2023 is April 2022–March 2023; FY2024 is April 2023–March 2024. These are consolidated global businesses listed in India; the figures are not India-only revenue.', 'Manually curated numeric rows, not automated PDF ingestion. Source publication dates are not recorded; this is not a point-in-time research dataset.']
    if metric != 'revenue':
        warnings.append('Operating-profit definitions differ across issuers. TCS FY2024 excludes a legal-claim settlement; Infosys reports IFRS operating profit; HCLTech reports earnings before other income, tax and finance cost. Rankings compare disclosed measures, without accounting normalization.')
    if margin:
        warnings.append('Margins are recalculated from INR-crore inputs, not copied from rounded headline percentages; changes are in percentage points, not percent.')
    return {'status': 'answered', 'answer': answer_text, 'metric': metric, 'rows': rows,
            'calculations': calculations, 'evidence': evidence, 'warnings': warnings,
            'mode': 'Deterministic evidence engine; no LLM', 'suggestions': EXAMPLES}
