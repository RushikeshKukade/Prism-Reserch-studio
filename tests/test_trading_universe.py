import copy
import unittest
from trading_universe import liquidity_metrics, screen, build_universe


class TradingUniverseTests(unittest.TestCase):
    def setUp(self):
        self.company={'id':'EXAMPLE','name':'Example','series':'EQ'}
        self.obs={'id':'EXAMPLE','price':100,'freshness':'recent_observation',
                  'indicators_stale':False,'history_count':210,'turnover20_crore':5.0}

    def test_turnover_uses_unadjusted_price_times_volume(self):
        history=[{'date':str(i),'close':100,'adjusted_close':50,'volume':1000000} for i in range(20)]
        metrics=liquidity_metrics(history)
        self.assertEqual(metrics['turnover20_crore'],10)
        self.assertEqual(metrics['volume20_valid_sessions'],20)

    def test_missing_latest_volume_is_not_replaced_by_older_data(self):
        history=[{'close':100,'volume':100} for _ in range(30)]
        history[-1]['volume']=None
        self.assertIsNone(liquidity_metrics(history)['turnover20_crore'])
        self.assertIsNone(liquidity_metrics(history[:19])['turnover20_crore'])

    def test_threshold_boundaries_and_non_eq_exclusion(self):
        self.assertTrue(screen(self.company,self.obs,min_price=100,min_turnover_crore=5)['eligible'])
        self.assertFalse(screen(self.company,self.obs,min_price=101)['eligible'])
        self.assertFalse(screen(self.company,self.obs,min_turnover_crore=5.01)['eligible'])
        for series in ('BE','RR'):
            self.assertFalse(screen({**self.company,'series':series},self.obs)['eligible'])

    def test_missing_stale_short_and_failed_refresh_are_excluded(self):
        self.assertFalse(screen(self.company,None)['eligible'])
        for change in ({'freshness':'stale'},{'indicators_stale':True},{'history_count':199},
                       {'refresh_error':'offline'},{'turnover20_crore':None},{'turnover20_crore':0}):
            self.assertFalse(screen(self.company,{**self.obs,**change})['eligible'])

    def test_selected_membership_only_and_report_does_not_mutate_snapshot(self):
        universe={'name':'Fixture','count':1,'companies':[self.company]}
        snapshot={'series':[self.obs,{'id':'OUTSIDE'}],'fundamentals':{'companies':[{'id':'OUTSIDE'}]}}
        original=copy.deepcopy(snapshot)
        report=build_universe(universe,snapshot)
        self.assertEqual(report['counts'],{'constituents':1,'price_available':1,'eligible':1,'verified_filings':0})
        self.assertEqual(snapshot,original)

    def test_invalid_screen_parameters_are_rejected(self):
        for settings in ({'min_price':float('nan')},{'min_turnover_crore':float('inf')},
                         {'min_history':19},{'min_history':True},{'min_price':-1}):
            with self.assertRaises(ValueError):build_universe({'companies':[]},{},**settings)

    def test_diagnostics_count_overlapping_failures_and_sector_shift(self):
        companies=[{**self.company,'sector':'Technology'},
                   {'id':'OTHER','series':'RR','sector':'Property'}]
        report=build_universe({'companies':companies},{'series':[self.obs]})
        self.assertEqual(report['diagnostics']['excluded'],1)
        self.assertEqual(sum(r['count'] for r in report['diagnostics']['exclusion_reasons']),2)
        tech=next(r for r in report['diagnostics']['sector_composition'] if r['sector']=='Technology')
        self.assertEqual((tech['universe_pct'],tech['eligible_pct']),(50,100))

    def test_empty_screen_has_no_invented_sector_share(self):
        report=build_universe({'companies':[{**self.company,'sector':'Tech'}]},{'series':[]})
        self.assertIsNone(report['diagnostics']['sector_composition'][0]['eligible_pct'])
        self.assertEqual(build_universe({'companies':[]},{})['diagnostics']['sector_composition'],[])

    def test_report_fingerprint_is_reproducible_and_sensitive_to_evidence(self):
        import hashlib
        import json
        universe={'companies':[self.company]}
        report=build_universe(universe,{'series':[self.obs]})
        digest=report.pop('report_sha256')
        canonical=report.pop('canonical_report_json')
        self.assertEqual(digest,hashlib.sha256(canonical.encode('utf-8')).hexdigest())
        self.assertEqual(digest,hashlib.sha256(json.dumps(report,sort_keys=True,
            ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest())
        self.assertEqual(digest,build_universe(universe,{'series':[self.obs]})['report_sha256'])
        self.assertNotEqual(digest,build_universe(universe,{'series':[{**self.obs,'price':101}]})['report_sha256'])
