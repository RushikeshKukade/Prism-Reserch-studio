import copy
import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
import market


def chart(now, n=211):
    dates=[now-timedelta(days=n-i) for i in range(n)]
    ts=[int(d.replace(hour=9,minute=15,second=0,microsecond=0).timestamp()) for d in dates]
    return {'chart':{'result':[{'meta':{'symbol':'TCS.NS','currency':'INR','regularMarketPrice':211,'regularMarketTime':ts[-1]+22500,'chartPreviousClose':9999},'timestamp':ts,'indicators':{'quote':[{'close':list(range(1,n+1)),'volume':[100]*n}],'adjclose':[{'adjclose':list(range(1,n+1))}]}}],'error':None}}


class MarketEvaluation(unittest.TestCase):
    def setUp(self):self.now=datetime(2026,10,30,1,0,tzinfo=market.IST)

    def test_indicator_oracles_and_correct_previous_day(self):
        r=market.parse_chart(chart(self.now),'TCS',self.now)
        self.assertEqual(r['sma50'],186.5)
        self.assertEqual(r['sma200'],111.5)
        self.assertAlmostEqual(r['momentum20_pct'],(211/191-1)*100)
        self.assertEqual(r['previous_close'],210)
        self.assertAlmostEqual(r['day_change_pct'],(211/210-1)*100)
        self.assertEqual(r['trend'],'above_50_and_200')

    def test_incomplete_today_bar_is_excluded(self):
        now=self.now.replace(hour=12)
        payload=chart(now)
        raw=payload['chart']['result'][0]
        raw['timestamp'][-1]=int(now.replace(hour=9,minute=15).timestamp())
        raw['meta']['regularMarketTime']=int(now.timestamp())
        r=market.parse_chart(payload,'TCS',now)
        self.assertEqual(r['history_count'],210)
        self.assertLess(r['completed_session'],now.date().isoformat())

    def test_missing_null_and_short_history(self):
        payload=chart(self.now,10)
        payload['chart']['result'][0]['indicators']['adjclose'][0]['adjclose'][0]=None
        r=market.parse_chart(payload,'TCS',self.now)
        self.assertEqual(r['history_count'],9)
        self.assertIsNone(r['sma50'])
        self.assertIsNone(r['momentum20_pct'])
        self.assertIsNone(r['volatility20_pct'])

    def test_bad_currency_and_future_quotes_are_rejected(self):
        payload=chart(self.now)
        payload['chart']['result'][0]['meta']['currency']='USD'
        with self.assertRaises(ValueError):market.parse_chart(payload,'TCS',self.now)
        payload=chart(self.now)
        payload['chart']['result'][0]['meta']['regularMarketTime']=int((self.now+timedelta(hours=1)).timestamp())
        with self.assertRaises(ValueError):market.parse_chart(payload,'TCS',self.now)

    def test_stale_observations_and_no_clock_relabelling(self):
        self.assertEqual(market.observation_state((self.now-timedelta(days=5)).timestamp(),self.now),'stale')
        self.assertEqual(market.observation_state((self.now-timedelta(hours=12)).timestamp(),self.now),'recent_observation')

    def test_failed_refresh_retains_original_observation_time(self):
        old=market.parse_chart(chart(self.now),'TCS',self.now)
        cached={'attempted_at':(self.now-timedelta(days=1)).isoformat(),'series':[old],'errors':{}}
        with patch.object(market,'read_cache',return_value=cached),patch.object(Path,'write_text'),patch.object(Path,'replace'),patch.object(market,'now_ist',return_value=self.now),patch.object(market,'fetch_symbol',side_effect=OSError('offline')):
            result=market.current_market(refresh=True)
        self.assertEqual(result['series'][0]['provider_timestamp'],old['provider_timestamp'])
        self.assertEqual(len(result['errors']),len(market.SYMBOLS))
        self.assertIn('offline',result['series'][0]['refresh_error'])

    def test_recent_filing_oracle_and_unsupported_queries(self):
        r=market.answer_current('Show latest revenue for Infosys')
        self.assertEqual(r['rows'][0]['value'],49244)
        self.assertEqual(r['rows'][0]['period_end'],'2026-09-30')
        self.assertIn('not a guarantee',r['answer'])
        self.assertIsNone(market.answer_current('Show current price for NOTREALCOMPANY'))
        self.assertIsNone(market.answer_current('Buy TCS today'))
