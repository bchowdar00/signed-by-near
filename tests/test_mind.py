"""The change-our-mind tests (measures.mind): met, not met, or undecided (None), never a verdict
drawn from a reading that is not completed, not measurable or unstable (METHOD §7)."""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'analysis'))
import measures as M  # noqa: E402


def share(L, U, complete=True, sparse=None, unstable=False):
    return {'L': L, 'U': U, 'complete': complete, 'sparse': sparse, 'unstable': unstable}


def est(point, lo, hi, unstable=False):
    return {'point': point, 'lo': lo, 'hi': hi, 'dropped': 0, 'unstable': unstable}


def chain(dom, parts_ok=True):
    p = share(0.6, 0.9) if parts_ok else share(0.6, 0.9, sparse='too sparse (4 of 2)')
    return {'measured_tokens': ['t'], 'dominant_route': dom, 'count_share': p, 'amount_share_by_unit': {'u': p}}


def base():
    """A results dict on which every test is decided and none is met."""
    return {
        'M9': {'complete': True, 'p': share(0.50, 0.70), 'non_omni_usd_per_30d': {'share_of_2V': {'hi': 0.4}}},
        'M1': {'chains': [chain('yes'), chain('yes'), chain('no'), chain('no'), chain('no'), chain('no'),
                          chain('no'), chain('no')]},
        'M4_M5': [{'month': m, 'complete': True, 'main_without_sweat': est(0.10, 0.05, 0.15)}
                  for m in ('2026-08', '2026-09', '2026-10')],
        'M8': {'months': [{'month': m, 'complete': True,
                           'per_request_executed_plus_pending': est(p, p - 0.001, p + 0.001),
                           'per_request_executed': est(p, p - 0.001, p + 0.001)}
                          for m, p in (('2026-07', 0.05), ('2026-08', 0.08), ('2026-09', 0.09))]},
        'trend': {'raw': dict(est(1.5, 1.2, 1.9), state='growing')},
        'M10': {s: {'verdict': 'moving to Omni'} for s in ('SOL', 'ZEC', 'BTC')},
    }


class TestMind(unittest.TestCase):
    def test_base_all_decided_not_met(self):
        r = M.mind(base())
        for k in ('value_mostly_on_omni', 'omni_dominant_widely', 'broad_adoption', 'falling_spend_per_request',
                  'no_migration'):
            self.assertIs(r[k]['met'], False, k)

    # --- the four counterexamples of pre-audit B (2026-11-10) ---
    def test_no_migration_undecided_when_a_series_is_not_measurable_or_unstable(self):
        res = base()
        res['M10'] = {'SOL': {'verdict': 'not measurable'}, 'ZEC': {'verdict': 'not measurable'},
                      'BTC': {'verdict': 'no clear move (unstable)'}}
        self.assertIsNone(M.mind(res)['no_migration']['met'])

    def test_no_migration_decided_false_if_any_series_moves_to_omni(self):
        res = base()
        res['M10'] = {'SOL': {'verdict': 'not completed'}, 'ZEC': {'verdict': 'moving to Omni'},
                      'BTC': {'verdict': 'no clear move'}}
        self.assertIs(M.mind(res)['no_migration']['met'], False)

    def test_no_migration_met_only_when_all_decided_without_move(self):
        res = base()
        res['M10'] = {s: {'verdict': v} for s, v in (('SOL', 'no clear move'), ('ZEC', 'moving away from Omni'),
                                                       ('BTC', 'no clear move'))}
        self.assertIs(M.mind(res)['no_migration']['met'], True)

    def test_dominance_undecided_when_chains_are_not_completed(self):
        res = base()
        res['M1']['chains'] = [chain('not completed') for _ in range(8)]
        r = M.mind(res)['omni_dominant_widely']
        self.assertIsNone(r['met'])
        self.assertEqual(r['undecided'], 8)

    def test_dominance_straddling_unknown_is_decided_not_yes(self):
        res = base()
        res['M1']['chains'] = [chain('yes')] * 2 + [chain('unknown', parts_ok=True)] * 6
        self.assertIs(M.mind(res)['omni_dominant_widely']['met'], False)

    def test_dominance_sparse_unknown_is_undecided(self):
        res = base()
        res['M1']['chains'] = [chain('yes')] * 2 + [chain('unknown', parts_ok=False)] * 6
        self.assertIsNone(M.mind(res)['omni_dominant_widely']['met'])

    def test_dominance_met_at_five_whatever_the_rest(self):
        res = base()
        res['M1']['chains'] = [chain('yes')] * 5 + [chain('not completed')] * 3
        self.assertIs(M.mind(res)['omni_dominant_widely']['met'], True)

    def test_value_undecided_when_p_is_unstable_or_sparse(self):
        res = base()
        res['M9']['p'] = share(0.95, 0.99, sparse='too sparse (3 of 2)', unstable=True)
        res['M9']['non_omni_usd_per_30d']['share_of_2V']['hi'] = 0.01
        self.assertIsNone(M.mind(res)['value_mostly_on_omni']['met'])

    def test_value_undecided_when_m9_not_completed_even_if_non_omni_is_high(self):
        res = base()
        res['M9']['complete'] = False
        self.assertIsNone(M.mind(res)['value_mostly_on_omni']['met'])

    def test_value_met(self):
        res = base()
        res['M9']['p'] = share(0.95, 0.99)
        res['M9']['non_omni_usd_per_30d']['share_of_2V']['hi'] = 0.01
        self.assertIs(M.mind(res)['value_mostly_on_omni']['met'], True)

    def test_broad_adoption_undecided_when_a_month_is_unstable(self):
        res = base()
        for r in res['M4_M5']:
            r['main_without_sweat'] = est(0.40, 0.30, 0.50)
        res['M4_M5'][1]['main_without_sweat'] = est(0.40, 0.30, 0.50, unstable=True)
        self.assertIsNone(M.mind(res)['broad_adoption']['met'])

    def test_broad_adoption_decided_false_by_one_stable_failing_month(self):
        res = base()
        res['M4_M5'][0]['main_without_sweat'] = est(0.40, 0.30, 0.50, unstable=True)
        self.assertIs(M.mind(res)['broad_adoption']['met'], False)

    def test_falling_spend_met_and_its_executed_only_twin(self):
        res = base()
        res['M8']['months'] = [{'month': m, 'complete': True,
                                'per_request_executed_plus_pending': est(p, p - 0.001, p + 0.001),
                                'per_request_executed': est(p, p - 0.001, p + 0.001)}
                               for m, p in (('2026-07', 0.09), ('2026-08', 0.06), ('2026-09', 0.03))]
        r = M.mind(res)
        self.assertIs(r['falling_spend_per_request']['met'], True)
        self.assertEqual(r['falling_spend_per_request']['numerator'], 'executed plus pending')
        self.assertIs(r['falling_spend_per_request']['executed_only']['met'], True)

    def test_falling_spend_undecided_when_trend_is_unstable(self):
        res = base()
        res['M8']['months'] = [{'month': m, 'complete': True,
                                'per_request_executed_plus_pending': est(p, p - 0.001, p + 0.001),
                                'per_request_executed': est(p, p - 0.001, p + 0.001)}
                               for m, p in (('2026-07', 0.09), ('2026-08', 0.06), ('2026-09', 0.03))]
        res['trend']['raw'] = dict(est(1.5, None, None, unstable=True), state='inconclusive')
        self.assertIsNone(M.mind(res)['falling_spend_per_request']['met'])

    def test_falling_spend_decided_false_when_trend_straddles_one(self):
        res = base()
        res['M8']['months'] = [{'month': m, 'complete': True,
                                'per_request_executed_plus_pending': est(p, p - 0.001, p + 0.001),
                                'per_request_executed': est(p, p - 0.001, p + 0.001)}
                               for m, p in (('2026-07', 0.09), ('2026-08', 0.06), ('2026-09', 0.03))]
        res['trend']['raw'] = dict(est(1.1, 0.9, 1.3), state='inconclusive')
        self.assertIs(M.mind(res)['falling_spend_per_request']['met'], False)


if __name__ == '__main__':
    unittest.main()
