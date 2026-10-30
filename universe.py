"""Official, versioned constituent snapshot; membership is not historical coverage."""
import csv
import hashlib
import io
import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

PATH=Path(__file__).parent/'data/universe.json'
SOURCE='https://www.niftyindices.com/IndexConstituent/ind_nifty200list.csv'


def validate_rows(rows):
    if not 190<=len(rows)<=350:raise ValueError('Unexpected constituent count')
    symbols=[]
    for row in rows:
        if not row.get('Company Name') or not row.get('Industry') or not re.fullmatch(r'[A-Z0-9&.\-]+',row.get('Symbol','')) or row.get('Series')!='EQ':raise ValueError('Unexpected constituent schema')
        symbols.append(row['Symbol'])
    if len(set(symbols))!=len(symbols):raise ValueError('Duplicate constituent symbols')


def refresh():
    req=urllib.request.Request(SOURCE,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=20) as response:raw=response.read()
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    validate_rows(rows)
    result={'name':'NIFTY 200','retrieved_at':datetime.now(timezone(timedelta(hours=5,minutes=30))).isoformat(),'source_url':SOURCE,'source_sha256':hashlib.sha256(raw).hexdigest(),'count':len(rows),'membership_note':'Current constituent snapshot retrieved on the date shown; effective membership date is not independently recorded. It is not a historical or survivorship-free universe.','companies':[{'id':r['Symbol'],'name':r['Company Name'],'sector':r['Industry'],'isin':r.get('ISIN Code'),'exchange':'NSE','provider_symbol':r['Symbol']+'.NS','aliases':[r['Symbol'].lower(),r['Company Name'].lower(),re.sub(r'\s+(?:ltd\.?|limited)$','',r['Company Name'],flags=re.I).lower()]} for r in rows]}
    temp=PATH.with_suffix('.tmp');temp.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');temp.replace(PATH)
    return result


def get_universe():
    return json.loads(PATH.read_text(encoding='utf-8'))


def resolve_company(text):
    q=text.lower().strip()
    aliases={'infosys':'INFY','hcl':'HCLTECH','hcl tech':'HCLTECH','reliance':'RELIANCE','tata consultancy services':'TCS'}
    key=aliases.get(q,q.upper())
    return next((c for c in get_universe()['companies'] if c['id']==key or q in [a.rstrip('.') for a in c['aliases']]),None)


if __name__=='__main__':
    data=refresh()
    print(f"Saved {data['count']} official constituents; {len({c['sector'] for c in data['companies']})} sectors. Source SHA256: {data['source_sha256']}")
