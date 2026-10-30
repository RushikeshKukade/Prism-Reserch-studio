import copy
import unittest
from datetime import date
from analytics import quality_report, change_bridge
from engine import DATA


class AnalyticsEvaluation(unittest.TestCase):
    def test_bridge_reconciles_for_all_companies(self):
        for company, delta in [('TCS',5074),('INFY',842),('HCLTECH',1544)]:
            b = change_bridge(company)
            self.assertEqual(b['profit_change'],delta)
            self.assertAlmostEqual(b['scale_effect']+b['margin_effect'],delta,places=8)
            self.assertAlmostEqual(b['reconciliation_error'],0,places=8)
        self.assertLess(change_bridge('INFY')['margin_effect'],0)

    def test_missing_and_invalid_data_are_flagged(self):
        data=copy.deepcopy(DATA)
        del data['companies'][0]['years']['2024']['revenue']
        q=quality_report(data,date(2026,10,30))
        self.assertGreater(q['counts']['fail'],0)
        data=copy.deepcopy(DATA);data['unit']='million'
        self.assertEqual(quality_report(data,date(2026,10,30))['checks'][0]['status'],'fail')

    def test_known_metadata_gaps_not_hidden(self):
        q=quality_report(as_of=date(2026,10,30))
        self.assertEqual(q['counts']['fail'],0)
        self.assertEqual(q['counts']['warning'],9)
        self.assertEqual(sum(c['check']=='Publication timestamp' and c['status']=='warning' for c in q['checks']),3)

    def test_unknown_company_fails(self):
        with self.assertRaises(ValueError):change_bridge('WIPRO')
