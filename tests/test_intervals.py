import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'analysis'))
import intervals as I


class TestIntervals(unittest.TestCase):
    def test_betainc_known(self):
        # I_x(1,1) = x; I_x(2,1) = x^2; I_0.5(a,a) = 0.5
        self.assertAlmostEqual(I.betainc(1, 1, 0.3), 0.3, places=12)
        self.assertAlmostEqual(I.betainc(2, 1, 0.3), 0.09, places=12)
        self.assertAlmostEqual(I.betainc(7.5, 7.5, 0.5), 0.5, places=12)

    def test_cp_closed_forms(self):
        for n in (1, 3, 6, 12, 36, 300):
            lo, hi = I.clopper_pearson(n, n)
            self.assertAlmostEqual(lo, 0.025 ** (1 / n), places=9)
            self.assertEqual(hi, 1.0)
            lo, hi = I.clopper_pearson(0, n)
            self.assertEqual(lo, 0.0)
            self.assertAlmostEqual(hi, 1 - 0.025 ** (1 / n), places=9)

    def test_cp_published_values(self):
        # standard two-sided 95% Clopper–Pearson limits
        lo, hi = I.clopper_pearson(5, 10)
        self.assertAlmostEqual(lo, 0.187086, places=5)
        self.assertAlmostEqual(hi, 0.812914, places=5)
        lo, hi = I.clopper_pearson(1, 10)
        self.assertAlmostEqual(lo, 0.002529, places=5)
        self.assertAlmostEqual(hi, 0.445016, places=5)

    def test_codex_counterexample(self):
        # three occupied windows of 100 equal all-Omni transfers: transfer-level n_eff = 300 gave 98.78%;
        # the window-level bound counts 3 windows, so the lower limit is 0.025^(1/3) = 29.2%
        self.assertAlmostEqual(I.clopper_pearson(300, 300)[0], 0.98778, places=4)
        lo, hi = I.window_cp(1.0, [100, 100, 100, 0, 0, 0])
        self.assertAlmostEqual(lo, 0.025 ** (1 / 3), places=9)
        self.assertEqual(hi, 1.0)

    def test_kish(self):
        self.assertAlmostEqual(I.kish([1, 1, 1, 1]), 4.0)
        self.assertAlmostEqual(I.kish([10, 0, 0]), 1.0)
        self.assertAlmostEqual(I.kish([3, 1]), 16 / 10)

    def test_monotone_near_boundary(self):
        # one minority transfer must not tighten the interval (the perverse case a transfer-level n invites)
        m = [20.0] * 18
        lo_all = I.window_cp(1.0, m)[0]
        lo_one = I.window_cp(1 - 1 / 360, m)[0]
        self.assertLessEqual(lo_one, lo_all)
        self.assertGreater(lo_one, lo_all - 0.02)


if __name__ == '__main__':
    unittest.main()
