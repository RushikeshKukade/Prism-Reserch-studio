import unittest
import universe
import market
import json
import hashlib
from unittest.mock import patch


class UniverseEvaluation(unittest.TestCase):
    def test_official_membership_unique_and_in_provider_map(self):
        for key, count in [('nifty200',200),('nifty500',500)]:
            data=universe.get_universe(key)
            self.assertEqual(data['count'],count)
            self.assertEqual(len({c['id'] for c in data['companies']}),count)
            self.assertEqual(len({c['isin'] for c in data['companies']}),count)
            self.assertTrue(all(c['id'] in market.SYMBOLS for c in data['companies']))
        self.assertEqual(len(market.SYMBOLS),503)

    def test_duplicate_or_empty_constituents_rejected(self):
        with self.assertRaises(ValueError):universe.validate_rows([])
        row={'Company Name':'Example Ltd.','Industry':'Example','Symbol':'EXAMPLE','Series':'EQ','ISIN Code':'INE123A01012'}
        with self.assertRaises(ValueError):universe.validate_rows([row]*200)

    def test_snapshot_subset_and_raw_source_hashes(self):
        a,b=universe.get_universe('nifty200'),universe.get_universe('nifty500')
        self.assertTrue({c['id'] for c in a['companies']} <= {c['id'] for c in b['companies']})
        for key,data in [('nifty200',a),('nifty500',b)]:
            raw=(universe.ROOT/'data/constituents'/f'{key}.csv').read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),data['source_sha256'])

    def test_dummy_placeholder_excluded_with_audit_and_series_preserved(self):
        data=universe.get_universe('nifty500')
        self.assertEqual(data['source_row_count'],501)
        self.assertEqual(data['excluded_source_rows'][0]['symbol'],'DUMMYHEG')
        self.assertNotIn('DUMMYHEG',market.SYMBOLS)
        self.assertEqual(sum(c['series']!='EQ' for c in data['companies']),5)
        self.assertTrue({'BE','RR'} <= {c['series'] for c in data['companies']})

    def test_unknown_universe_rejected(self):
        with self.assertRaises(ValueError):universe.get_universe('anything')

    def test_resolver_supports_names_and_nse_symbols(self):
        self.assertEqual(universe.resolve_company('Reliance')['id'],'RELIANCE')
        self.assertEqual(universe.resolve_company('HDFCBANK')['id'],'HDFCBANK')
        self.assertEqual(universe.resolve_company('Reliance Industries Ltd')['id'],'RELIANCE')
        self.assertIsNone(universe.resolve_company('NOTREALCOMPANY'))

    def test_unverified_financials_are_not_fabricated(self):
        result=market.answer_current('Show latest revenue for Reliance')
        self.assertEqual(result['status'],'insufficient_information')
        self.assertEqual(result['rows'],[])
        self.assertIn('not been verified',result['answer'])

    def test_selected_company_does_not_inherit_another_issuers_filings(self):
        filings=json.loads((market.ROOT/'data/recent_results.json').read_text(encoding='utf-8'))
        snapshot={'series':[{'id':'RELIANCE','name':'Reliance Industries Ltd.','price':100,'unit':'INR per share','provider_timestamp':'2026-10-29T15:30:00+05:30','freshness':'recent_observation','completed_session':'2026-10-28','momentum20_pct':2,'indicators_stale':False,'source_url':'https://finance.yahoo.com/quote/RELIANCE.NS/history/'}],'fundamentals':filings,'as_of':'2026-10-30T03:00:00+05:30','limitations':'Fixture; not a real-time feed.'}
        with patch.object(market,'current_market',return_value=snapshot):
            result=market.answer_current('Show current price for Reliance')
        sections=result['review']['sections']
        disclosure=next(s for s in sections if s['title']=='Recent quarterly disclosures')
        self.assertIn('No quarterly disclosure',disclosure['text'])
        self.assertEqual(len(result['review']['references']),1)
