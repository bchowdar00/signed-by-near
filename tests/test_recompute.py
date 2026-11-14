"""End to end: analysis/recompute.py on synthetic collector output for the frozen design
(tests/simulate.py), so the whole pipeline is exercised without any counted row."""
import json, os, shutil, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'analysis'))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
import recompute  # noqa: E402
import simulate  # noqa: E402

INSTANTS = os.path.join(ROOT, 'frozen', 'instants.json')


class TestEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp()
        simulate.simulate(INSTANTS, cls.d, seed=11)
        cls.R = recompute.run(INSTANTS, cls.d, os.path.join(cls.d, 'out'))
        cls.inc = tempfile.mkdtemp()
        simulate.simulate(INSTANTS, cls.inc, seed=12, incomplete=40)
        cls.RI = recompute.run(INSTANTS, cls.inc, os.path.join(cls.inc, 'out'))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d)
        shutil.rmtree(cls.inc)

    def test_no_neardata_makes_2a_readings_not_completed(self):
        d = tempfile.mkdtemp()
        try:
            simulate.simulate(INSTANTS, d, seed=13)
            shutil.rmtree(os.path.join(d, 'nd'))
            R = recompute.run(INSTANTS, d, os.path.join(d, 'out'))
            self.assertEqual(R['errors'], [])
            self.assertEqual(R['trend']['excluding class 3 and 2a']['state'], 'not completed')
            self.assertEqual(R['trend']['excluding 2a only (class 3 kept)']['state'], 'not completed')
            self.assertNotEqual(R['trend']['raw']['state'], 'not completed')
        finally:
            shutil.rmtree(d)

    def test_results_bytes_repeat_and_charts_written(self):
        out2 = os.path.join(self.d, 'out2')
        recompute.run(INSTANTS, self.d, out2)
        with open(os.path.join(self.d, 'out', 'results.json'), 'rb') as f1, open(os.path.join(out2, 'results.json'), 'rb') as f2:
            self.assertEqual(f1.read(), f2.read())
        for f in ('chart1-routes.svg', 'chart2-callers-cost.svg'):
            self.assertTrue(os.path.exists(os.path.join(out2, f)))
        self.assertGreater(self.R['inputs']['data']['files'], 0)

    def test_main_without_sweat_carries_the_2b_signer_bound(self):
        for r in self.R['M4_M5']:
            if r['attributed']:
                mws = r['main_without_sweat']
                self.assertIn('signer_bound', mws, r['month'])
                self.assertLessEqual(mws['lo'], mws['signer_bound'][0] + 1e-12)
                self.assertGreaterEqual(mws['hi'], mws['signer_bound'][1] - 1e-12)

    def test_m8_totals_and_reconcile_survive_a_failed_read(self):
        t = self.R['M8']['totals']
        self.assertAlmostEqual(t['executed_near'], 338436.08, places=2)
        self.assertAlmostEqual(t['pending_near'], 8436.40, places=2)
        self.assertAlmostEqual(t['proposed_near'], 76864.52, places=2)
        rec = self.R['M8']['reconcile']
        self.assertTrue(rec['2026-05']['no_participant_set'])  # the 2026-06 read failed in the simulator
        self.assertIn('matched', rec['2026-09'])

    def test_runs_clean_and_writes(self):
        self.assertEqual(self.R['errors'], [])
        for f in ('results.json', 'tables.md'):
            self.assertTrue(os.path.exists(os.path.join(self.d, 'out', f)))
        with open(os.path.join(self.d, 'out', 'results.json')) as f:
            self.assertEqual(json.load(f)['B'], 2000)
        self.assertTrue(all(c.get('completed') == sum(c.values()) for c in self.R['completeness'].values()))

    def test_c2b_structure(self):
        btc = self.R['C2b']['BTC']
        self.assertIn(btc['verdict'], ('consistent', 'partly', 'inconclusive', 'contradicted', 'not measurable'))
        self.assertTrue(self.R['C2b']['BTC']['verdict_given'])
        for g in ('SOL', 'Solana stablecoins (USD)'):
            self.assertFalse(self.R['C2b'][g]['verdict_given'])
            self.assertNotIn('verdict', self.R['C2b'][g])
            self.assertNotIn('state', self.R['C2b'][g]['primary'])
        p = btc['primary']
        self.assertLessEqual(p['L'], p['U'])

    def test_m1_counts(self):
        c = self.R['M1']['counts']
        self.assertEqual(c['capability_documented']['count'], 10)
        self.assertEqual(c['observed']['of'], 28)
        self.assertGreaterEqual(c['dominant']['favourable_yes_plus_unknown'], 20)  # METHOD §7: C1 not identified

    def test_sign_months_and_trend(self):
        self.assertEqual([r['month'] for r in self.R['M3']][0], '2024-08')
        self.assertEqual(len(self.R['M3']), 28)
        self.assertTrue(self.R['trend']['complete'])
        flagged = {r['month']: r.get('flagged_days') for r in self.R['M3']}
        self.assertAlmostEqual(flagged['2026-09'], 2.0)
        self.assertAlmostEqual(flagged['2026-10'], 4.0)
        self.assertIsNone(flagged['2026-08'])

    def test_m4_attribution_only_with_neardata(self):
        rows = {r['month']: r for r in self.R['M4_M5']}
        self.assertFalse(rows['2025-10']['attributed'])
        self.assertTrue(rows['2025-11']['attributed'])
        self.assertIn('range', rows['2025-10']['main'])
        self.assertIn('signer_bound', rows['2026-10']['main'])

    def test_incomplete_windows_propagate(self):
        nc = sum(c.get('not_completed', 0) for c in self.RI['completeness'].values())
        self.assertEqual(nc, 40)
        states = [self.RI['C2b']['BTC']['verdict']] + [r['verdict'] for r in self.RI['M10'].values()] + \
                 [self.RI['trend']['verdict']]
        # with 40 of 526 windows missing, at least one reading must say so
        self.assertIn('not completed', states + [r['dominant_route'] for r in self.RI['M1']['chains']])


if __name__ == '__main__':
    unittest.main()
