"""Explicitly scoped research review, not a live trading recommendation."""
import re
from datetime import datetime, timezone, timedelta


def is_review_request(question):
    q = question.lower()
    return bool(re.search(r'\b(review|suggestions?|assess)\b', q) and re.search(r'\b(approach|strategy|prototype|india|market|trading)\b', q))


def research_review():
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date().isoformat()
    return {
        'status':'research_review', 'mode':'Deterministic research review; no LLM',
        'answer':'Use this prototype to investigate Indian IT fundamentals and build a research watchlist. Current-market trading suitability is unverified: the dataset ends in FY2024, and there are no entry/exit rules, live prices or strategy backtests.',
        'rows':[], 'calculations':[], 'evidence':[], 'warnings':[], 'suggestions':[],
        'review':{
            'review_date':today,
            'verdict':'Useful research workflow; unvalidated trading hypothesis',
            'sections':[
                {'title':'Review: what is useful', 'text':'Revenue growth, operating-margin changes and the profit bridge help distinguish expansion in business scale from changes in disclosed profitability. Source links and accounting-basis warnings make comparisons easier to audit. This is a financial diagnostic, not evidence of future stock returns.'},
                {'title':'A strategy hypothesis to test', 'text':'Test whether Indian IT companies with stronger recently published revenue growth and stable or improving operating margins subsequently outperform a sector benchmark. Predefine a broader universe, ranking rule, position sizing, rebalance schedule and exit rule before testing. Do not treat the current three-company snapshot as a trading signal.'},
                {'title':'Why it might help — and why it might fail', 'text':'The economic hypothesis is that sustained growth with resilient margins may indicate stronger underlying business performance. But prices may already reflect that information; high valuations, currency movements, one-off adjustments or sector-wide moves can overwhelm it. The prototype has not tested whether the hypothesis predicts returns.'},
                {'title':'Suggestion for current Indian markets', 'text':'Start with a paper-research watchlist. Refresh official company results, announcement timestamps and adjusted prices; check market trend, volatility and liquidity using dated observations. No current market regime or buy/sell conclusion is inferred here because those feeds are not connected.'},
                {'title':'What must survive a proper test', 'text':'Use only filings available before each rebalance, preserve delisted names, and account for corporate actions. Compare against an appropriate sector benchmark out of sample. Include applicable Indian trading charges, spread, slippage and size-dependent impact cost. Stress-test weaker market periods and turnover before considering implementation.'}
            ],
            'references':[
                {'title':'NSE corporate financial results: reporting basis and broadcast timestamps', 'url':'https://www.nseindia.com/companies-listing/corporate-filings-financial-results'},
                {'title':'NSE impact cost: execution cost depends on size and available liquidity', 'url':'https://www.nseindia.com/static/products-services/indices-impact-cost'}
            ],
            'reference_note':'Methodology references; not current market observations. Reviewed 30 October 2026. No live market feed or return-predictability evidence is supplied.'
        }
    }
