"""Official constituent snapshots; index membership is not a trading recommendation."""
import argparse
import csv
import hashlib
import io
import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
DEFINITIONS = {
    'nifty200': {'name': 'NIFTY 200', 'target_count': 200, 'path': ROOT/'data/universe.json',
                 'source_url': 'https://www.niftyindices.com/IndexConstituent/ind_nifty200list.csv'},
    'nifty500': {'name': 'NIFTY 500', 'target_count': 500, 'path': ROOT/'data/universe_nifty500.json',
                 'source_url': 'https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv'},
}


def is_placeholder(row):
    return (row.get('Symbol', '').startswith('DUMMY')
            and row.get('Company Name', '').lower().startswith('dummy ')
            and row.get('ISIN Code', '').startswith('DUM'))


def validate_rows(rows, index='nifty200'):
    definition = DEFINITIONS[index]
    expected = definition['target_count']
    if not expected - 10 <= len(rows) <= expected + 20:
        raise ValueError('Unexpected constituent count; inspect the official source')
    symbols, isins = [], []
    for row in rows:
        if (not row.get('Company Name') or not row.get('Industry')
                or not re.fullmatch(r'[A-Z0-9&.\-]+', row.get('Symbol', ''))
                or row.get('Series') not in {'EQ', 'BE', 'RR'}
                or not (re.fullmatch(r'IN[A-Z0-9]{10}', row.get('ISIN Code', '')) or is_placeholder(row))):
            raise ValueError('Unexpected constituent schema')
        symbols.append(row['Symbol'])
        isins.append(row['ISIN Code'])
    if len(set(symbols)) != len(symbols) or len(set(isins)) != len(isins):
        raise ValueError('Duplicate constituent symbol or ISIN')


def snapshot_from_csv(raw, index):
    definition = DEFINITIONS[index]
    rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    validate_rows(rows, index)
    source_count = len(rows)
    excluded = [{'symbol': r['Symbol'], 'name': r['Company Name'], 'isin': r['ISIN Code'],
                 'reason': 'Explicit dummy placeholder in source; not a tradeable issuer identifier'}
                for r in rows if is_placeholder(r)]
    rows = [r for r in rows if not is_placeholder(r)]
    warnings = []
    if excluded:
        warnings.append(f"Excluded {len(excluded)} explicit dummy placeholder from {source_count} source rows; the raw CSV and exclusion audit are retained.")
    if len(rows) != definition['target_count']:
        warnings.append(f"Official source contains {len(rows)} securities for {definition['name']}; all source rows are retained.")
    non_eq = sum(r['Series'] != 'EQ' for r in rows)
    if non_eq:
        warnings.append(f"{non_eq} securities have a non-EQ series and are excluded by the default EQ-only research screen.")
    return {
        'id': index, 'name': definition['name'], 'target_count': definition['target_count'],
        'retrieved_at': datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
        'source_url': definition['source_url'], 'source_sha256': hashlib.sha256(raw).hexdigest(),
        'count': len(rows), 'source_row_count': source_count, 'excluded_source_rows': excluded, 'warnings': warnings,
        'membership_note': 'Current official index snapshot; not a strict market-cap ranking or a point-in-time historical universe. Effective membership date is not independently recorded.',
        'companies': [{
            'id': r['Symbol'], 'name': r['Company Name'], 'sector': r['Industry'],
            'series': r['Series'], 'isin': r['ISIN Code'], 'exchange': 'NSE',
            'provider_symbol': r['Symbol'] + '.NS',
            'aliases': [r['Symbol'].lower(), r['Company Name'].lower(),
                        re.sub(r'\s+(?:ltd\.?|limited)$', '', r['Company Name'], flags=re.I).lower()],
        } for r in rows],
    }


def save_snapshot(raw, index):
    result = snapshot_from_csv(raw, index)
    path = DEFINITIONS[index]['path']
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)
    source_path = ROOT/'data/constituents'/f'{index}.csv'
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(raw)
    return result


def refresh(index='nifty500'):
    req = urllib.request.Request(DEFINITIONS[index]['source_url'], headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read()
    return save_snapshot(raw, index)


def get_universe(index='nifty500'):
    if index not in DEFINITIONS:
        raise ValueError('Choose nifty200 or nifty500')
    return json.loads(DEFINITIONS[index]['path'].read_text(encoding='utf-8'))


def get_universes():
    return {key: get_universe(key) for key in DEFINITIONS}


def resolve_company(text):
    q = text.lower().strip()
    aliases = {'infosys': 'INFY', 'hcl': 'HCLTECH', 'hcl tech': 'HCLTECH',
               'reliance': 'RELIANCE', 'tata consultancy services': 'TCS'}
    key = aliases.get(q, q.upper())
    return next((c for c in get_universe()['companies']
                 if c['id'] == key or q in [a.rstrip('.') for a in c['aliases']]), None)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', choices=['all', *DEFINITIONS], default='all')
    args = parser.parse_args()
    for key in DEFINITIONS if args.index == 'all' else [args.index]:
        data = refresh(key)
        print(f"{data['name']}: saved {data['count']} securities; SHA256 {data['source_sha256']}")
        for warning in data['warnings']:
            print(warning)
