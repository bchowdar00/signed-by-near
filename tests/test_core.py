"""Offline tests of analysis/core.py on synthetic strata and the uncounted shakedown
(tests/fixtures/shakedown, copied from b-shakedown, 2026-11-09T17:43-17:45Z, 15 credits, never counted)."""
import json, math, os, random, shutil, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'analysis'))
sys.path.insert(0, os.path.join(ROOT, 'collector'))
import core  # noqa: E402
import design  # noqa: E402

FIX = os.path.join(ROOT, 'tests', 'fixtures')
SHAKE = os.path.join(FIX, 'shakedown')


def W(weight, i=0, covered=100.0, whole=False):
    return {'weight': weight, 'i': i, 'covered_s': covered, 'segments_ns': [], 'whole': whole}


def T(route, units=1.0, tx=None, token='sol.omft.near', direction='in'):
    T.n += 1
    return {'route': route, 'units': units, 'usd': units, 'tx': tx or f'tx{T.n}', 'token': token,
            'direction': direction}


T.n = 0


def stratum(name, values, weight=1.0, whole=False, two_route=True, complete=True):
    ws = [W(weight, i, whole=whole) for i in range(len(values))]
    return core.Stratum(name, ws, values, whole=whole, two_route=two_route, complete=complete)


class TestEst(unittest.TestCase):
    def test_arithmetic_and_none(self):
        a = core.Est(2.0, [1.0] * (core.B - 1) + [None])
        b = core.Est.const(4.0)
        c = (a + b) / (b - 4.0)
        self.assertIsNone(c.point)
        self.assertEqual(c.dropped(), core.B)
        d = a * 3 + 1
        self.assertEqual(d.point, 7.0)
        self.assertEqual(d.dropped(), 1)

    def test_percentile_type7(self):
        xs = sorted([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertAlmostEqual(core.percentile(xs, 0.5), 3.0)
        self.assertAlmostEqual(core.percentile(xs, 0.025), 1.1)
        self.assertAlmostEqual(core.percentile(xs, 0.975), 4.9)


class TestDraws(unittest.TestCase):
    def test_seeded_and_shared(self):
        d1 = core.draws_for('sign:2026-09:last90', 16)
        core._DRAWS.clear()
        d2 = core.draws_for('sign:2026-09:last90', 16)
        self.assertEqual(d1, d2)
        self.assertNotEqual(d1, core.draws_for('sign:2026-10:last90', 16))
        rng = random.Random(design.seed_for('boot', 'sign:2026-09:last90'))
        self.assertEqual(d1[0], [rng.randrange(16) for _ in range(16)])

    def test_whole_is_identity(self):
        st = stratum('whole-x', [[T('POA', 2.0)], [T('POA', 3.0)]], whole=True)
        tot = core.total([st], lambda v: sum(t['units'] for t in v))
        self.assertEqual(tot.point, 5.0)
        self.assertTrue(all(d == 5.0 for d in tot.draws))


class TestTotals(unittest.TestCase):
    def test_ht_point(self):
        st = core.Stratum('ht', [W(2.5, 0), W(2.5, 1), W(2.5, 2)], [3, 0, 5])
        tot = core.total([st], lambda v: v)
        self.assertAlmostEqual(tot.point, 20.0)

    def test_ht_unbiased_with_design_placement(self):
        """Simulate the frozen placement (design.place) on a two-piece stratum with a flagged cut-out;
        the HT total and the domain total outside a sub-interval are unbiased."""
        rng = random.Random(7)
        pieces = [(0.0, 1000.0), (1500.0, 3000.0)]
        events = sorted(rng.uniform(a, b) for a, b in pieces for _ in range(int((b - a) / 10)))
        sub = (2000.0, 2600.0)
        truth = len(events)
        truth_dom = sum(1 for e in events if not (sub[0] <= e < sub[1]))
        st = design.Stratum('sim', pieces)
        tots, doms = [], []
        for k in range(3000):
            ws = design.place(st, 120.0, 6, random.Random(1000 + k))
            y = [sum(1 for e in events for s, e2 in w['segments'] if s <= e < e2) for w in ws]
            yd = [sum(1 for e in events for s, e2 in w['segments'] if s <= e < e2 and not (sub[0] <= e < sub[1]))
                  for w in ws]
            tots.append(sum(w['weight'] * v for w, v in zip(ws, y)))
            doms.append(sum(w['weight'] * v for w, v in zip(ws, yd)))
        m, md = sum(tots) / len(tots), sum(doms) / len(doms)
        sd = (sum((t - m) ** 2 for t in tots) / (len(tots) - 1)) ** 0.5 / len(tots) ** 0.5
        self.assertLess(abs(m - truth), 4 * sd)
        self.assertLess(abs(md - truth_dom), 4 * sd)


class TestShares(unittest.TestCase):
    def test_worked_example_bound(self):
        """METHOD §4.0: three windows of 100 all-Omni transfers give a lower bound of 29.2%."""
        st = stratum('flow:sol.omft.near:claim-sim', [[T('OMNI') for _ in range(100)] for _ in range(3)])
        r = core.transfer_share([st], kind='count')
        self.assertAlmostEqual(r['L'], 0.025 ** (1 / 3), places=6)
        self.assertAlmostEqual(r['L'], 0.2924, places=4)
        self.assertEqual(r['U'], 1.0)
        self.assertEqual(r['reading_L']['boot'], [1.0, 1.0])

    def test_one_route_and_whole_strata_have_no_bound_width(self):
        one = stratum('flow:nbtc-sim', [[T('OMNI')] * 5 for _ in range(3)], two_route=False)
        whole = stratum('flow:btc-whole-sim', [[T('POA', 2.0)], [T('OMNI', 2.0)]], whole=True)
        r1 = core.transfer_share([one], kind='count')
        self.assertEqual(r1['reading_L']['bound'], [1.0, 1.0])
        r2 = core.transfer_share([whole], kind='units')
        self.assertEqual(r2['reading_L']['bound'], [0.5, 0.5])
        self.assertEqual(r2['reading_L']['boot'], [0.5, 0.5])

    def test_unknowns_both_ways_and_nearside_dropped(self):
        vals = [[T('OMNI'), T('UNKNOWN'), T('POA'), T('NEARSIDE')] for _ in range(12)]
        st = stratum('mix-sim', vals)
        r = core.transfer_share([st], kind='count')
        self.assertAlmostEqual(r['point_unknown_not_omni'], 1 / 3)
        self.assertAlmostEqual(r['point_unknown_omni'], 2 / 3)
        self.assertLessEqual(r['L'], 1 / 3)
        self.assertGreaterEqual(r['U'], 2 / 3)
        self.assertEqual(r['n_unknown'], 12)

    def test_sparse_rules(self):
        empty = stratum('empty-sim', [[] for _ in range(6)])
        self.assertEqual(core.transfer_share([empty])['sparse'], 'none observed (0 of 0)')
        few = stratum('few-sim', [[T('OMNI')] for _ in range(9)])
        self.assertEqual(core.transfer_share([few])['sparse'], 'too sparse (9 of 9)')
        two = stratum('two-sim', [[T('OMNI') for _ in range(10)], [T('OMNI') for _ in range(10)], []])
        self.assertEqual(core.transfer_share([two])['sparse'], 'too sparse (20 of 2)')
        # a transfer held by two windows counts once
        shared = [T('OMNI', tx='same') for _ in range(1)]
        dup = stratum('dup-sim', [list(shared), list(shared), list(shared)] + [[T('OMNI')] for _ in range(9)])
        self.assertEqual(core.transfer_share([dup])['distinct_transfers'], 10)

    def test_unstable(self):
        vals = [[T('OMNI') for _ in range(20)]] + [[] for _ in range(19)]
        st = stratum('unstable-sim', vals)
        r = core.transfer_share([st], kind='count')
        self.assertTrue(r['unstable'])
        self.assertEqual(core.state(dict(r, sparse=None), 0.9), 'inconclusive')

    def test_states_in_order(self):
        base = {'complete': True, 'sparse': None, 'unstable': False}
        self.assertEqual(core.state(dict(base, complete=False, L=0.99, U=1.0), 0.9), 'not completed')
        self.assertEqual(core.state(dict(base, sparse='too sparse (3 of 2)', L=0.99, U=1.0), 0.9), 'not measurable')
        self.assertEqual(core.state(dict(base, L=0.4, U=0.95), 0.9), 'inconclusive')
        self.assertEqual(core.state(dict(base, L=0.91, U=1.0), 0.9), 'consistent')
        self.assertEqual(core.state(dict(base, L=0.1, U=0.49), 0.9), 'contradicted')
        self.assertEqual(core.state(dict(base, L=0.6, U=0.95), 0.9), 'partly')
        self.assertEqual(core.state(dict(base, L=0.4, U=0.85), 0.9), 'partly')

    def test_incomplete_stratum_marks_share(self):
        st = stratum('inc-sim', [[T('OMNI') for _ in range(5)] for _ in range(4)], complete=False)
        self.assertEqual(core.state(core.transfer_share([st]), 0.9), 'not completed')


class TestPoisson(unittest.TestCase):
    def test_garwood_tabulated(self):
        # exact 95% Poisson limits (Garwood 1936), e.g. Ulm (1990) table
        for k, lo, hi in [(0, 0.0, 3.6889), (1, 0.0253, 5.5716), (5, 1.6235, 11.6683), (10, 4.7954, 18.3904)]:
            a, b = core.garwood(k)
            self.assertAlmostEqual(a, lo, places=3)
            self.assertAlmostEqual(b, hi, places=3)
        self.assertAlmostEqual(core.garwood(0)[1], -math.log(0.025), places=9)
        self.assertEqual(core.rule_of_three(1000.0), 0.003)

    def test_rate_hull_at_zero(self):
        st = stratum('rate0-sim', [[] for _ in range(6)])
        r = core.rate([st], len, lambda s, i: s.covered[i], 30.0)
        self.assertEqual(r['per_day'], 0.0)
        self.assertAlmostEqual(r['hi'], 3.6889 / 600.0 * 86400, places=1)
        self.assertEqual(r['lo'], 0.0)


class TestShakedown(unittest.TestCase):
    """End to end on the uncounted shakedown: the readings the shakedown check recorded on Nov 9."""

    def setUp(self):
        self.S = core.Study(os.path.join(SHAKE, 'instants-shakedown.json'), SHAKE,
                            tokens_path=os.path.join(ROOT, 'frozen', 'tokens.json'))

    def test_flow_routes(self):
        sol = self.S.transfers(self.S.by_id['sd-flow-sol'])
        eth = self.S.transfers(self.S.by_id['sd-flow-eth'])
        self.assertEqual((len(sol), sum(t['route'] == 'OMNI' for t in sol)), (12, 12))
        self.assertEqual(sorted(t['direction'] for t in sol).count('out'), 5)
        self.assertEqual((len(eth), sum(t['route'] == 'POA' for t in eth)), (7, 7))
        self.assertEqual(sorted(t['direction'] for t in eth).count('out'), 3)
        self.assertTrue(all(t['units'] > 0 for t in sol))

    def test_sign_calls(self):
        busy = self.S.sign_calls(self.S.by_id['sd-sign-busy'])
        self.assertEqual(len(busy), 120)
        self.assertEqual(len({c['receipt_id'] for c in busy}), 120)
        self.assertEqual(self.S.sign_calls(self.S.by_id['sd-sign-zero']), [])

    def test_census_rows_involve_intents(self):
        c = self.S.census_items(self.S.by_id['sd-census'])
        self.assertEqual(c['off'], 0)
        self.assertGreater(c['rows'], 0)

    def test_flow_window_incomplete_without_resolution(self):
        self.assertFalse(self.S.window_complete(self.S.by_id['sd-flow-sol']))
        self.assertTrue(self.S.window_complete(self.S.by_id['sd-sign-busy']))

    def test_resolution_replaces_and_audit_matches(self):
        d = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(SHAKE, 'nb'), os.path.join(d, 'nb'))
            with open(os.path.join(SHAKE, 'txns-fts-7Y29.json')) as f:
                body = json.load(f)
            h = '7Y29ssQjzRq81rmck3SpLSRPNf2Cc8HwBuaGAKButunB'
            os.makedirs(os.path.join(d, 'nb', 'txns'))
            with open(os.path.join(d, 'nb', 'txns', f'{h}.json'), 'w') as f:
                json.dump({'tx': h, 'http': 200, 'body': body['body']}, f)
            with open(os.path.join(d, 'nb', 'resolve.jsonl'), 'w') as f:
                f.write(json.dumps({'tx': h, 'candidate': True, 'audit': True, 'windows': ['sd-flow-sol'],
                                    'http': 200, 'resolved': True}) + '\n')
                f.write(json.dumps({'tx': 'unreadable', 'candidate': True, 'audit': False, 'windows': ['sd-flow-eth'],
                                    'http': 0, 'resolved': False}) + '\n')
            with open(os.path.join(d, 'nb', 'RESOLVED'), 'w') as f:
                f.write('{}')
            S = core.Study(os.path.join(SHAKE, 'instants-shakedown.json'), d,
                           tokens_path=os.path.join(ROOT, 'frozen', 'tokens.json'))
            sol = S.transfers(S.by_id['sd-flow-sol'])
            self.assertEqual(S.transfer_counters(S.by_id['sd-flow-sol'])['replaced'], 1)
            self.assertEqual(len(sol), 12)
            a = S.audit()
            self.assertEqual((a['audited'], a['differ']), (1, 0))
            self.assertTrue(S.window_complete(S.by_id['sd-flow-sol']))
            self.assertFalse(S.window_complete(S.by_id['sd-flow-eth']))
        finally:
            shutil.rmtree(d)


if __name__ == '__main__':
    unittest.main()


class TestThesisFill(unittest.TestCase):
    def test_fill_and_holes(self):
        import thesis_fill
        res = {'C2b': {'BTC': {'primary': {'L': 0.9123, 'U': None}}}, 'M9': {'V_usd': 831333190.29},
               'M1': {'chains': [{'chain': 'Bitcoin'}]}, 'k': {'claim|amount|both': {'x': 1234.5}}}
        t = ('{{C2b/BTC/primary/L::pct1}} {{M9/V_usd::usdm}} {{M1/chains/0/chain::str}} '
             '{{k/claim|amount|both/x::int}}')
        out, holes = thesis_fill.fill(t, res)
        self.assertEqual(out, '91.2% $831.3M Bitcoin 1,234')
        self.assertEqual(holes, [])
        out, holes = thesis_fill.fill('{{C2b/BTC/primary/U::pct1}} {{nope/x::int}}', res)
        self.assertEqual(len(holes), 2)
