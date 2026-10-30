"""Dated public-provider observations, complete-session indicators and cache safety."""
import copy
import json
import math
import statistics
import threading
import time
from universe import get_universe, resolve_company
from trading_universe import liquidity_metrics
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).parent
CACHE=ROOT/'data/current_market.json'
IST=timezone(timedelta(hours=5,minutes=30))
SYMBOLS={'NIFTY50':('^NSEI','NIFTY 50','index'),'NIFTYIT':('^CNXIT','NIFTY IT','index'),'INDIAVIX':('^INDIAVIX','India VIX','volatility'),'TCS':('TCS.NS','TCS','equity'),'INFY':('INFY.NS','Infosys','equity'),'HCLTECH':('HCLTECH.NS','HCLTech','equity')}
UNIVERSE=get_universe()
SYMBOLS.update({c['id']:(c['provider_symbol'],c['name'],'reit' if c.get('series')=='RR' else 'equity') for c in UNIVERSE['companies'] if c['id'] not in SYMBOLS})
_lock=threading.Lock()
_joblock=threading.Lock()
_job={'state':'idle','completed':0,'total':len(SYMBOLS),'errors':0}


def now_ist():return datetime.now(IST)


def valid_number(n):return isinstance(n,(int,float)) and not isinstance(n,bool) and math.isfinite(n) and n>0


def observation_state(timestamp, now=None):
    now=now or now_ist()
    if not isinstance(timestamp,(int,float)) or not math.isfinite(timestamp):return 'unavailable'
    hours=(now.timestamp()-timestamp)/3600
    return 'invalid_future' if hours < -0.25 else 'stale' if hours>96 else 'recent_observation'


def parse_chart(payload, key, now=None):
    now=now or now_ist()
    symbol,name,kind=SYMBOLS[key]
    chart=payload.get('chart',{})
    if chart.get('error') or not chart.get('result'):raise ValueError('Provider returned no valid chart')
    raw=chart['result'][0];meta=raw.get('meta',{})
    if meta.get('symbol')!=symbol or meta.get('currency')!='INR':raise ValueError('Symbol or currency mismatch')
    quote=raw.get('indicators',{}).get('quote',[{}])[0]
    closes=quote.get('close',[]);volumes=quote.get('volume',[])
    adjusted=raw.get('indicators',{}).get('adjclose',[{}])[0].get('adjclose',[])
    use_adjusted=bool(adjusted) and len(adjusted)==len(closes)
    price_series=adjusted if use_adjusted else closes
    bars=[]
    for i,t in enumerate(raw.get('timestamp',[])):
        day=datetime.fromtimestamp(t,IST)
        # Exclude today's incomplete daily bar. No forward-filled missing sessions.
        complete=day.date()<now.date() or day.date()==now.date() and (now.hour,now.minute)>=(15,35)
        if complete and i<len(price_series) and i<len(closes) and valid_number(price_series[i]) and valid_number(closes[i]):
            bars.append({'date':day.date().isoformat(),'close':closes[i],'adjusted_close':price_series[i],'volume':volumes[i] if i<len(volumes) else None})
    if len({b['date'] for b in bars})!=len(bars):raise ValueError('Duplicate daily observations')
    bars.sort(key=lambda b:b['date'])
    if not bars:raise ValueError('No complete daily observations')
    prices=[b['adjusted_close'] for b in bars]
    latest=meta.get('regularMarketPrice');ts=meta.get('regularMarketTime')
    if not valid_number(latest) or observation_state(ts,now)=='invalid_future':raise ValueError('Invalid quote or future provider timestamp')
    previous=meta.get('chartPreviousClose')
    # chartPreviousClose can be the start of the requested range; never use it for daily change.
    quote_date=datetime.fromtimestamp(ts,IST).date().isoformat()
    earlier=[b for b in bars if b['date']<quote_date]
    previous=earlier[-1]['close'] if earlier else None
    returns=[prices[i]/prices[i-1]-1 for i in range(1,len(prices))]
    sma=lambda n:statistics.fmean(prices[-n:]) if len(prices)>=n else None
    sma50,sma200=sma(50),sma(200)
    trend='insufficient_history' if sma50 is None or sma200 is None else 'above_50_and_200' if prices[-1]>sma50 and prices[-1]>sma200 else 'below_50_and_200' if prices[-1]<sma50 and prices[-1]<sma200 else 'mixed'
    high=prices[0];drawdown=0
    for value in prices:
        high=max(high,value);drawdown=min(drawdown,value/high-1)
    return {'id':key,'symbol':symbol,'name':name,'kind':kind,'price':latest,'currency':'INR','unit':'volatility index points' if kind=='volatility' else 'index points' if kind=='index' else 'INR per unit' if kind=='reit' else 'INR per share','provider_timestamp':datetime.fromtimestamp(ts,IST).isoformat(),'provider_epoch':ts,'freshness':observation_state(ts,now),'day_change_pct':(latest/previous-1)*100 if previous else None,'previous_close':previous,'completed_session':bars[-1]['date'],'completed_close':bars[-1]['close'],'sma50':sma50,'sma200':sma200,'momentum20_pct':(prices[-1]/prices[-21]-1)*100 if len(prices)>=21 else None,'volatility20_pct':statistics.stdev(returns[-20:])*math.sqrt(252)*100 if len(returns)>=20 else None,'max_drawdown_window_pct':drawdown*100,'trend':trend,'history_count':len(bars),'price_basis':'provider adjusted close' if use_adjusted else 'unadjusted close (adjustment data unavailable)','history':bars,'source_url':'https://finance.yahoo.com/quote/'+urllib.parse.quote(symbol,safe='')+'/history/','retrieved_at':now.isoformat()}


def fetch_symbol(key):
    time.sleep(0.15)
    symbol=SYMBOLS[key][0]
    url='https://query1.finance.yahoo.com/v8/finance/chart/'+urllib.parse.quote(symbol,safe='')+'?range=1y&interval=1d'
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=12) as response:
        payload=json.load(response)
    return parse_chart(payload,key)


def read_cache():
    try:return json.loads(CACHE.read_text(encoding='utf-8'))
    except (OSError,ValueError):return {'series':[],'errors':{},'attempted_at':None}


def refresh_snapshot(progress=None):
    with _lock:
        result=read_cache();now=now_ist()
        attempted=result.get('attempted_at')
        elapsed=(now-datetime.fromisoformat(attempted)).total_seconds() if attempted else float('inf')
        if elapsed<60:return result
        existing={r['id']:r for r in result.get('series',[]) if r['id'] in SYMBOLS}
        errors={}
        def get(key):
            try:return key,fetch_symbol(key),None
            except Exception as exc:return key,None,type(exc).__name__+': '+str(exc)[:160]
        with ThreadPoolExecutor(max_workers=6) as pool:
            for completed,(key,row,error) in enumerate(pool.map(get,SYMBOLS),1):
                if row:existing[key]=row
                if error:errors[key]=error
                if progress:progress(completed,len(SYMBOLS),len(errors))
        result={'attempted_at':now.isoformat(),'series':[existing[k] for k in SYMBOLS if k in existing],'errors':errors,'provider':'Yahoo Finance public chart endpoint (unofficial; may be delayed, throttled or unavailable)'}
        temp=CACHE.with_suffix('.tmp')
        temp.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');temp.replace(CACHE)
        return result


def current_market(refresh=False,progress=None):
    result=refresh_snapshot(progress) if refresh else read_cache()
    result=copy.deepcopy(result);now=now_ist()
    company_map={c['id']:c for c in UNIVERSE['companies']}
    for row in result.get('series',[]):
        row.update(liquidity_metrics(row.get('history', [])))
        row['freshness']=observation_state(row.get('provider_epoch'),now)
        row['refresh_error']=result.get('errors',{}).get(row['id'])
        row['sector']=company_map.get(row['id'],{}).get('sector','Benchmark')
        history_age=(now.date()-datetime.fromisoformat(row['completed_session']).date()).days
        row['indicators_stale']=history_age>4
    result['as_of']=now.isoformat()
    result['expected_series']=len(SYMBOLS)
    result['universe_count']=UNIVERSE['count']
    result['fundamentals']=json.loads((ROOT/'data/recent_results.json').read_text(encoding='utf-8'))
    result['fundamentals']['needs_review']=(now.date()-datetime.fromisoformat(result['fundamentals']['verified_on']).date()).days>120
    result['limitations']='Current NIFTY 200/500 constituent snapshots, not historical survivorship-free universes. Public observations may be delayed or unavailable. Quote and indicator dates differ; freshness allows 96 elapsed hours, not a latest-session guarantee. Financial filings are verified for a subset only. No strategy backtest or order placement.'
    return result


def market_summary():
    result=current_market()
    for row in result['series']:row.pop('history',None)
    return result


def refresh_status():
    with _joblock:return copy.deepcopy(_job)


def start_refresh():
    with _joblock:
        if _job['state']=='running':return copy.deepcopy(_job)
        _job.update(state='running',completed=0,total=len(SYMBOLS),errors=0,started_at=now_ist().isoformat(),message='Refreshing dated observations')
    def progress(done,total,errors):
        with _joblock:_job.update(completed=done,total=total,errors=errors)
    def worker():
        try:
            result=current_market(refresh=True,progress=progress)
            with _joblock:_job.update(state='complete',completed=len(SYMBOLS),errors=len(result['errors']),finished_at=now_ist().isoformat(),message='Refresh finished; inspect per-company coverage')
        except Exception as exc:
            with _joblock:_job.update(state='failed',message='Refresh failed: '+str(exc)[:120])
    threading.Thread(target=worker,daemon=True).start()
    return refresh_status()


def current_review(snapshot=None):
    snapshot=current_market() if snapshot is None else snapshot
    rows={r['id']:r for r in snapshot['series']}
    nifty=rows.get('NIFTY50')
    trend={'above_50_and_200':'above both its 50- and 200-session averages','below_50_and_200':'below both its 50- and 200-session averages','mixed':'between its trend measures','insufficient_history':'not supported by enough history'}
    recent=nifty and nifty['freshness']=='recent_observation' and not nifty['indicators_stale']
    context=f"NIFTY 50's completed-session price is {trend[nifty['trend']]} as of {nifty['completed_session']}." if recent else 'Selected-instrument observations are shown below; no full-market regime is inferred.' if len(rows)==1 else 'The benchmark is missing or stale; a current-market interpretation is withheld.'
    details=[]
    for r in snapshot['series']:
        details.append({'title':r['name']+' / '+r['provider_timestamp'], 'text':f"Provider observation: {r['price']:.2f} {r['unit']}; status: {r['freshness']}. Completed daily session: {r['completed_session']}. "+(f"20-session adjusted-price change: {r['momentum20_pct']:+.2f}%." if r['momentum20_pct'] is not None and not r['indicators_stale'] else 'Recent momentum unavailable or stale.')})
    filings=snapshot['fundamentals']
    sections=[{'title':'Current market context','text':context+' This trend label describes observed history, not future returns.'},*details,{'title':'Recent quarterly disclosures','text':(filings['period']+', ended '+filings['period_end']+': '+ '; '.join(f"{c['name']} revenue INR {c['revenue']:,} crore, reported INR YoY growth {c['revenue_yoy_pct']}%, headline operating margin {c['reported_margin_pct']}%" for c in filings['companies'])+'. Manually verified '+filings['verified_on']+'. Issuer margin definitions differ; no normalization or trading conclusion is implied.') if filings['companies'] else 'No quarterly disclosure has been verified for this selected instrument. Market-price coverage is not evidence of revenue or operating profitability.'},{'title':'Suggestion: a paper-research screen','text':'A possible hypothesis is positive recent revenue growth plus resilient margins, evaluated alongside sector-relative price momentum. These are screening inputs, not validated entry or exit rules. Compare like-for-like periods and examine issuer adjustments. No automatic stock recommendation is generated.'},{'title':'Why the hypothesis could help or fail','text':'Improving fundamentals and persistent relative strength may identify business and price resilience. They can also be fully priced in, reverse sharply, or reflect FX, acquisitions and one-off adjustments. This prototype has not established predictive performance or net profitability.'},{'title':'Execution and validation','text':'Define trading rules, exposure and exits; then test out of sample with announcement-date availability, delistings, Indian charges, spread, slippage and market impact. Do not interpret current indicators as a tested trading strategy.'}]
    return {'status':'research_review','answer':'India current-market research review. '+context,'rows':[],'calculations':[],'evidence':[],'warnings':[],'suggestions':[],'latency_ms':0,'model_calls':0,'model_cost_inr':0,'verified_on':snapshot['fundamentals']['verified_on'],'snapshot':'Refreshable market observations + separately verified quarterly filings','review':{'review_date':snapshot['as_of'][:10],'verdict':'Observed market conditions; strategy performance unverified','sections':sections,'references':[{'title':r['name']+' price history — Yahoo Finance','url':r['source_url']} for r in snapshot['series']]+[c['source'] for c in snapshot['fundamentals']['companies']],'reference_note':snapshot['limitations']},'mode':'Deterministic current-market research; no LLM'}


def answer_current(question):
    import re
    q=question.lower().strip().rstrip('?.!')
    fundamental=re.fullmatch(r'(?:show |what is )?(?:the )?(?:latest|recent|current) (revenue|operating margin)(?: for| of)? (.+)',q)
    if fundamental:
        f=json.loads((ROOT/'data/recent_results.json').read_text(encoding='utf-8'))
        resolved=resolve_company(fundamental[2])
        if resolved is None:return None
        name=resolved['id']
        c=next((c for c in f['companies'] if c['id']==name),None)
        if c is None:
            from engine import answer
            result=answer('')
            result['answer']=resolved['name']+' is in the market-data universe, but its quarterly financial disclosure has not been verified in this prototype. No financial figure is inferred from its share price.'
            return result
        metric='revenue' if fundamental[1]=='revenue' else 'reported_operating_margin'
        value=c['revenue'] if metric=='revenue' else c['reported_margin_pct']
        display=f"INR {value:,} crore" if metric=='revenue' else f"{value:.1f}%"
        sid=c['id']+'-Q2FY27'
        source={**c['source'],'id':sid,'company':c['name'],'basis':c['basis'],'verified_on':f['verified_on'],'publication_date':c['announced_on'],'rows':[f"Q2 FY2027 revenue INR {c['revenue']} crore; headline operating margin {c['reported_margin_pct']}%."]}
        return {'status':'answered','answer':f"{c['name']} {f['period']} {fundamental[1]}: {display}. Period ended {f['period_end']}; announcement {c['announced_on']}. This is the most recent manually verified disclosure in this app, not a guarantee of the latest filing today.",'metric':metric,'rows':[{'company':c['name'],'company_id':c['id'],'year':f['period'],'period_end':f['period_end'],'metric':metric,'value':value,'display':display,'unit':f['unit'] if metric=='revenue' else '%','source_id':sid}],'calculations':[],'evidence':[source],'warnings':[c['basis'],f['update_method']+' Last verified '+f['verified_on']+'.'],'latency_ms':0,'model_calls':0,'model_cost_inr':0,'snapshot':'Manually verified quarterly disclosures','verified_on':f['verified_on'],'mode':'Deterministic quarterly-filing lookup'}
    broad=q in ['review current indian markets','show current indian markets','current india market overview','review this research approach for current indian markets','review this approach for india']
    match=re.fullmatch(r'(?:show |what is )?(?:the )?(?:current|latest) (?:price|trend|momentum)(?: for| of)? (.+)',q)
    if not broad and not match:return None
    snapshot=current_market()
    if match:
        benchmarks={'nifty 50':'NIFTY50','nifty it':'NIFTYIT','india vix':'INDIAVIX'}
        resolved=resolve_company(match[1])
        key=benchmarks.get(match[1],resolved['id'] if resolved else None)
        if key is None:return None
        snapshot['series']=[r for r in snapshot['series'] if r['id']==key]
        snapshot['fundamentals']['companies']=[c for c in snapshot['fundamentals']['companies'] if c['id']==key]
    else:
        snapshot['series']=[r for r in snapshot['series'] if r['id'] in ('NIFTY50','NIFTYIT','INDIAVIX','TCS','INFY','HCLTECH')]
    return current_review(snapshot)


if __name__=='__main__':
    def progress(done,total,errors):
        if done%25==0 or done==total:print(f'Refreshed {done}/{total}; provider errors: {errors}',flush=True)
    result=current_market(refresh=True,progress=progress)
    print(json.dumps({'attempted_at':result['attempted_at'],'observations_loaded':len(result['series']),'errors':result['errors']},ensure_ascii=False,indent=2))
