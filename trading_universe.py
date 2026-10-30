"""Transparent research eligibility, not broker eligibility or a trading signal."""
import hashlib
import json
from collections import Counter
import math
import statistics


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def liquidity_metrics(history):
    window = history[-20:]
    valid = [b for b in window if number(b.get('close')) and b['close'] > 0
             and number(b.get('volume')) and b['volume'] >= 0]
    complete = len(window) == 20 and len(valid) == 20
    return {'turnover20_crore': statistics.fmean(b['close'] * b['volume'] for b in window) / 10000000 if complete else None,
            'volume20_valid_sessions': len(valid),
            'turnover_window_end': window[-1].get('date') if window else None}


def screen(company, observation, min_history=200, min_price=0, min_turnover_crore=0):
    reasons = []
    if company.get('series') != 'EQ':
        reasons.append('Non-EQ series excluded from this equity research screen')
    if not observation:
        reasons.append('Price history unavailable')
        return {'eligible': False, 'reasons': reasons}
    if observation.get('freshness') != 'recent_observation':
        reasons.append('Quote missing, stale or invalid')
    if observation.get('indicators_stale', True):
        reasons.append('Completed-session history is stale')
    if observation.get('refresh_error'):
        reasons.append('Latest provider refresh failed')
    if observation.get('history_count', 0) < min_history:
        reasons.append(f'Fewer than {min_history} completed observations')
    price = observation.get('price')
    if not number(price) or price <= 0 or price < min_price:
        reasons.append('Price below minimum or invalid')
    turnover = observation.get('turnover20_crore')
    if not number(turnover) or turnover <= 0:
        reasons.append('Positive turnover unavailable for the latest 20 completed observations')
    elif turnover < min_turnover_crore:
        reasons.append('Average traded value below selected minimum')
    return {'eligible': not reasons, 'reasons': reasons}


def build_universe(universe, snapshot, min_history=200, min_price=0, min_turnover_crore=0):
    if (type(min_history) is not int or not 20 <= min_history <= 2000
            or not number(min_price) or not 0 <= min_price <= 10000000
            or not number(min_turnover_crore) or not 0 <= min_turnover_crore <= 10000000):
        raise ValueError('Invalid screen settings: history 20â€“2000; price and turnover 0â€“10000000')
    observations = {r['id']: r for r in snapshot.get('series', [])}
    filings = {c['id'] for c in snapshot.get('fundamentals', {}).get('companies', [])}
    rows = []
    for company in universe['companies']:
        obs = observations.get(company['id'])
        rows.append({**company, 'observation': obs, 'filing': company['id'] in filings,
                     'screen': screen(company, obs, min_history, min_price, min_turnover_crore)})
    report = {'universe': {k: v for k, v in universe.items() if k != 'companies'}, 'rows': rows,
            'as_of': snapshot.get('as_of'),
            'parameters': {'min_history': min_history, 'min_price': min_price,
                           'min_turnover_crore': min_turnover_crore, 'series': 'EQ'},
            'counts': {'constituents': len(rows), 'price_available': sum(r['observation'] is not None for r in rows),
                       'eligible': sum(r['screen']['eligible'] for r in rows),
                       'verified_filings': sum(r['filing'] for r in rows)},
            'methodology': 'Traded value proxy = mean(unadjusted daily close Ã— provider volume) over the latest 20 completed observations Ã· 10,000,000. All 20 values must be valid. Missing values are not backfilled. Defaults are research controls, not optimised trading rules. Freshness allows 96 elapsed hours and four calendar days for history; no exchange calendar is used. No market-cap ranking, index weights, borrow checks, circuit limits or broker eligibility are provided.'}

    reasons = Counter(reason for row in rows for reason in row['screen']['reasons'])
    sectors = Counter(row.get('sector', 'Unknown') for row in rows)
    passed = Counter(row.get('sector', 'Unknown') for row in rows if row['screen']['eligible'])
    report['diagnostics'] = {
        'excluded': len(rows) - report['counts']['eligible'],
        'exclusion_reasons': [{'reason': reason, 'count': count} for reason, count in reasons.most_common()],
        'sector_composition': [{'sector': sector, 'universe_count': count,
            'eligible_count': passed[sector],
            'universe_pct': round(100 * count / len(rows), 2),
            'eligible_pct': round(100 * passed[sector] / report['counts']['eligible'], 2) if report['counts']['eligible'] else None}
            for sector, count in sorted(sectors.items())],
        'note': 'Reasons overlap: one security can fail multiple checks. Sector shares are equal-count shares, not index or portfolio weights. This is a research screen, not a return forecast.'}
    canonical = json.dumps(report, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    report['canonical_report_json'] = canonical
    report['report_sha256'] = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    return report
