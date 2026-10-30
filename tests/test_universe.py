import unittest
import universe
import market
import json
from unittest.mock import patch


class UniverseEvaluation(unittest.TestCase):
    def test_official_membership_unique_and_in_provider_map(self):
        data=universe.get_universe()
        self.assertEqual(data['count'],200)
        self.assertEqual(len({c['id'] for c in data['companies']}),200)
        self.assertEqual(len({c['isin'] for c in data['companies']}),200)
        self.assertEqual(len(market.SYMBOLS),203)
        self.assertTrue(all(c['id'] in market.SYMBOLS for c in data['companies']))

    def test_duplicate_or_empty_constituents_rejected(self):
        with self.assertRaises(ValueError):universe.validate_rows([])
        row={'Company Name':'Example Ltd.','Industry':'Example','Symbol':'EXAMPLE','Series':'EQ'}
        with self.assertRaises(ValueError):universe.validate_rows([row]*200)

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
