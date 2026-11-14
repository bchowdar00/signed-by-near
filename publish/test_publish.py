"""Tests for the post-freeze publishing step (publish/), on synthetic data only.

  python3 -I -m unittest discover -s publish

T-1's proving test is the senior reviewer's A/B pair, regenerated here: run A is tests/simulate.py
with seed 11 (it reproduces the reviewer's outA byte for byte); run B is A with the `completed` lines
of five windows removed (two SOL early windows, the SOL 2026-03 chart window, two windows of
sign:2025-03). T-2's test builds an extension pass for B from A's pages, merges it with
extension/merge.py and checks the secondary reading. No counted row and no network are used.
"""
import copy, hashlib, json, os, re, shutil, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for d in (HERE, os.path.join(ROOT, 'analysis'), os.path.join(ROOT, 'tests'), os.path.join(ROOT, 'extension')):
    sys.path.insert(0, d)
import simulate  # noqa: E402
import thesis_fill as TF  # noqa: E402
import merge  # noqa: E402
import rule  # noqa: E402
import combine  # noqa: E402
import fill  # noqa: E402
import dest_audit  # noqa: E402

INSTANTS = os.path.join(ROOT, 'frozen', 'instants.json')
TMPL = os.path.join(ROOT, 'THESIS.tmpl.md')
DROPPED = ['0b4b7fc26258', 'a82e0e27dcc1', '005ad02070bc', '4855e63b0ef7', '8b2eb8a36710']
CHARTS = ('chart1-routes.svg', 'chart2-callers-cost.svg')
FIX = os.path.join(HERE, 'fixtures')
SYNTH_AUDIT = {'summary': {c: {'picked': 10, 'found': 9, 'not_found': 1, 'unknown': 0, 'confirmed': 9,
                               'from_signer_address': 9} for c in ('BITCOIN', 'ZCASH')}, 'rows': []}


def drop_completed(data_dir, ids):
    p = os.path.join(data_dir, 'nb', 'windows.jsonl')
    with open(p) as f:
        lines = [l for l in f if l.strip()]
    keep = [l for l in lines if not (json.loads(l)['id'] in ids and json.loads(l)['event'] == 'completed')]
    with open(p, 'w') as f:
        f.writelines(keep)
    return len(lines) - len(keep)


def read(p):
    with open(p) as f:
        return f.read()


def titles(svg):
    return re.findall(r'<title>([^<]*)</title>', svg)


def windows():
    return json.loads(read(INSTANTS))['windows']


def first_id(**kv):
    return next(w['id'] for w in windows() if all(w.get(k) == v for k, v in kv.items()))


def let_through_is_frozen(tc, out_dir):
    """Every value the rule lets through is the frozen value (only masked readings differ)."""
    frozen = json.loads(read(os.path.join(out_dir, 'results.json')))
    pub = json.loads(read(os.path.join(out_dir, 'published', 'results.json')))
    masked = [m['path'] for m in pub['rule']['masked']]
    n = 0
    for p in combine.differs(frozen, pub):
        if p.startswith(('rule', 'M6/index_not_completed', 'dest_audit_selection/not_completed_months')):
            continue
        tc.assertTrue(any(p == m or p.startswith(m + '/') for m in masked), p)
        n += 1
    return n


def svg_texts(svg):
    """(x, y, size, text) of every <text> element."""
    return [(float(x), float(y), float(s), t) for x, y, s, t in
            re.findall(r'<text x="([\d.-]+)" y="([\d.-]+)"[^>]*font-size="([\d.]+)"[^>]*>([^<]*)</text>', svg)]


def synth_audit(res):
    """SYNTH_AUDIT with one row per pick of these results, as publish/dest_audit.py would write it."""
    sel = res['dest_audit_selection']
    return dict(SYNTH_AUDIT, rows=[{'receipt_id': p['receipt_id']} for k in ('bitcoin', 'zcash') for p in sel[k]])


def thesis(out_dir, combined=None):
    if combined is None:
        res = json.loads(read(os.path.join(out_dir, 'published', 'results.json')))
        combined = combine.combine(res, dest_audit=synth_audit(res))
    c = combined
    c.setdefault('dest_audit', SYNTH_AUDIT)
    text = fill.expand(read(TMPL), c, os.path.join(ROOT, 'THESIS.ext.tmpl.md'))
    filled, holes = fill.fill(text, c)
    assert not holes, holes
    return filled


class TestRule(unittest.TestCase):
    """T-1."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.A = os.path.join(cls.tmp, 'A')
        cls.B = os.path.join(cls.tmp, 'B')
        simulate.simulate(INSTANTS, cls.A, seed=11)
        shutil.copytree(cls.A, cls.B)
        assert drop_completed(cls.B, set(DROPPED)) == 5
        cls.RA = rule.run(INSTANTS, cls.A, os.path.join(cls.A, 'out'))
        cls.RB = rule.run(INSTANTS, cls.B, os.path.join(cls.B, 'out'))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def out(self, run, *p):
        return os.path.join(run, 'out', *p)

    def test_frozen_output_shows_the_defect_and_is_left_as_written(self):
        t = read(self.out(self.B, 'tables.md'))
        self.assertIn('| 2025-03 (not completed) | 30 [13, 45] |', t)   # the part-done number T-1 found
        self.assertNotIn('not completed', read(self.out(self.B, 'chart2-callers-cost.svg')))

    def test_identity_when_nothing_is_unfinished(self):
        self.assertEqual(self.RA['rule']['masked'], [])
        for f in ('tables.md',) + CHARTS:
            self.assertEqual(read(self.out(self.A, f)), read(self.out(self.A, 'published', f)), f)

    def test_masks_exactly_the_readings_on_the_five_windows(self):
        self.assertEqual(self.RB['rule']['unfinished_strata'],
                         ['migration:sol.omft.near:chart:2026-03', 'migration:sol.omft.near:early', 'sign:2025-03'])
        self.assertEqual(sorted(m['path'] for m in self.RB['rule']['masked']), sorted([
            'M10/SOL/readings', 'M10/SOL/chart/4', 'M10/SOL/migration_window_counters',
            'M3/7/raw', 'M3/7/failed_share', 'M4_M5/7',
            'by_month/M3/2025-03/raw', 'by_month/M3/2025-03/failed_share', 'by_month/M4/2025-03']))

    def test_every_value_let_through_is_the_frozen_value(self):
        self.assertGreater(let_through_is_frozen(self, self.out(self.B)), 0)

    def test_thesis_B_differs_from_A_only_where_the_rule_blanks_a_reading(self):
        a = thesis(self.out(self.A)).split('\n')
        b = thesis(self.out(self.B)).split('\n')
        self.assertEqual(len(a), len(b))
        diff = [(x, y) for x, y in zip(a, b) if x != y]
        self.assertEqual(len(diff), 2, diff)
        self.assertTrue(diff[0][0].startswith('- **After the freeze.**') and ' 5 of its 526 windows' in diff[0][1])
        self.assertTrue(diff[1][0].startswith('| SOL | [54.1%, 100.0%] | [54.7%, 100.0%] |'))
        self.assertEqual(diff[1][1], '| SOL | not completed | not completed | not completed |')

    def test_charts_B_hold_only_values_of_A_and_mark_the_gaps(self):
        for f in CHARTS:
            ta, tb = titles(read(self.out(self.A, 'published', f))), titles(read(self.out(self.B, 'published', f)))
            self.assertTrue(set(tb) <= set(ta), f)
            gone = [t for t in ta if t not in tb]
            self.assertEqual(len(gone), 5, gone)
            self.assertTrue(all(t.startswith(('SOL — ', '2025-03 — ')) for t in gone), gone)
        self.assertGreaterEqual(read(self.out(self.B, 'published', 'chart2-callers-cost.svg')).count('not completed'), 1)
        c1 = read(self.out(self.B, 'published', 'chart1-routes.svg'))
        self.assertIn('early and late: not completed', c1)
        self.assertIn('monthly: 1 not completed', c1)
        self.assertIn('SOL: early and late shares; monthly 2026-03.', c1)

    def test_chart1_marks_clear_the_monthly_markers(self):
        """A3 P3: the in-plot mark sits above the row's monthly markers, never on them."""
        c1 = read(self.out(self.B, 'published', 'chart1-routes.svg'))
        marks = [(x, y, s) for x, y, s, t in svg_texts(c1) if t == 'early and late: not completed']
        self.assertEqual(len(marks), 1)
        dots = [(float(cx), float(cy), float(r)) for cx, cy, r in
                re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"', c1)]
        x, y, s = marks[0]
        row = [d for d in dots if abs(d[1] - y) < 20]
        self.assertTrue(row)
        for cx, cy, r in row:
            self.assertLess(y + 0.3 * s, cy - r - 1, (x, y, cx, cy))

    def test_ruled_tables_B_show_no_number_for_a_masked_reading(self):
        a = read(self.out(self.A, 'published', 'tables.md')).split('\n')
        b = read(self.out(self.B, 'published', 'tables.md')).split('\n')
        diff = [(x, y) for x, y in zip(a, b) if x != y]
        self.assertEqual([y for _, y in diff], [
            '| migration | 72 | 0 | 3 |', '| sign | 196 | 0 | 2 |',
            '| SOL | [–, –] | [–, –] | [–, –] | not completed |',
            '| 2025-03 (not completed) | – [–, –] | – [–, –] | – [–, –] | – | – |'])
        tail = b[len(a):]
        self.assertIn('## Not completed at the deadline', tail)
        self.assertIn('- `M10/SOL/readings`: an early or late stratum of the series is unfinished '
                      '(the whole measure, POST-FREEZE ruling)', tail)
        self.assertFalse(any('by_month/' in l for l in tail))

    def test_frozen_manifests_still_verify(self):
        for man in ('MANIFEST-stage1.txt', 'MANIFEST-stage2.txt'):
            for line in read(os.path.join(ROOT, 'frozen', man)).splitlines():
                h, p = line.split(None, 1)
                with open(os.path.join(ROOT, p.strip()), 'rb') as f:
                    self.assertEqual(hashlib.sha256(f.read()).hexdigest(), h, p)

    def test_a_disagreement_between_frozen_counts_and_the_gate_stops(self):
        res = json.loads(read(self.out(self.B, 'results.json')))
        windows = json.loads(read(INSTANTS))['windows']
        U = [w for w in windows if w['id'] in DROPPED[:4]]
        with self.assertRaises(rule.RuleError):
            rule.apply(res, windows, U)

    def test_fill_with_old_style_placeholders_matches_the_frozen_fill(self):
        res = json.loads(read(self.out(self.A, 'published', 'results.json')))
        res['dest_audit'] = SYNTH_AUDIT
        text = re.sub(r'\{\{([^{}:]+)::iv1\}\}', r'[{{\1/L::pct1}}, {{\1/U::pct1}}]', read(TMPL))
        text = re.sub(r'\n*<!-- extension:[a-z]+ -->\n*', '\n\n', text)
        ours, h1 = fill.fill(text, res)
        frozen, h2 = TF.fill(text, res)
        self.assertEqual((h1, h2), ([], []))
        self.assertEqual(ours, frozen)
        self.assertEqual(fill.fill('{{M10/SOL/readings/amount/early::iv1}}', res)[0],
                         fill.fill('[{{M10/SOL/readings/amount/early/L::pct1}}, {{M10/SOL/readings/amount/early/U::pct1}}]', res)[0])

    def test_a_malformed_if_completed_block_stops_the_fill(self):
        res = json.loads(read(self.out(self.A, 'published', 'results.json')))
        ok = '<!-- if completed: M9 -->\nA\n<!-- otherwise -->\nB\n<!-- end if -->\n'
        self.assertEqual(fill.conditionals('x\n' + ok + ok + 'y\n', res), 'x\nA\nA\ny\n')
        for bad in (ok.replace('<!-- end if -->\n', '') + ok,              # first end missing
                    ok.replace('<!-- end if -->', '<!-- end if -->  ') + ok,  # trailing spaces
                    ok.replace('<!-- otherwise -->\n', '') + ok,          # otherwise missing
                    ok.replace('M9', 'M9/no_such_reading')):
            with self.assertRaises(fill.FillError, msg=bad):
                fill.conditionals('x\n' + bad + 'y\n', res)

    def test_a_null_outside_a_masked_reading_still_stops_the_fill(self):
        res = json.loads(read(self.out(self.B, 'published', 'results.json')))
        res['M9']['p']['L'] = None
        self.assertEqual(fill.fill('{{M9/p/L::pct1}}', res)[1], ['{{M9/p/L::pct1}}'])
        self.assertEqual(fill.fill('{{M10/SOL/readings/amount/early/L::pct1}}', res)[0], 'not completed')
        self.assertEqual(fill.fill('{{no/such/path::pct1}}', res)[1], ['{{no/such/path::pct1}}'])


class TestHeavyIncomplete(unittest.TestCase):
    """40 random windows unfinished, in every family: the rule finds no reading flagged not complete that
    still shows a number (apply() checks this itself and raises otherwise), and the charts render."""

    def test_random_unfinished_windows(self):
        tmp = tempfile.mkdtemp()
        try:
            simulate.simulate(INSTANTS, tmp, seed=12, incomplete=40)
            R = rule.run(INSTANTS, tmp, os.path.join(tmp, 'out'))
            fams = R['rule']['unfinished_by_family']
            self.assertEqual(sum(fams.values()), 40)
            self.assertTrue({'flow', 'census', 'sign', 'migration'} <= set(fams), fams)
            self.assertTrue(R['M9']['not_completed'])
            self.assertIn('not completed', read(os.path.join(tmp, 'out', 'published', 'chart1-routes.svg')))
            t = thesis(os.path.join(tmp, 'out'))
            self.assertNotIn('{{', t)
        finally:
            shutil.rmtree(tmp)


class TestAdversarial(unittest.TestCase):
    """Pre-audit A3's drop patterns: one kind of unfinished window each, beyond the reviewer's pair."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.A = os.path.join(cls.tmp, 'A')
        simulate.simulate(INSTANTS, cls.A, seed=11)
        cls.RA = rule.run(INSTANTS, cls.A, os.path.join(cls.A, 'out'))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def variant(self, name, ids=(), remove=()):
        d = os.path.join(self.tmp, name)
        shutil.copytree(self.A, d, ignore=shutil.ignore_patterns('out'))
        self.assertEqual(drop_completed(d, set(ids)), len(ids))
        for p in remove:
            os.remove(os.path.join(d, p))
        return os.path.join(d, 'out'), rule.run(INSTANTS, d, os.path.join(d, 'out'))

    def chain(self, R, name):
        return next(r for r in R['M1']['chains'] if r['chain'] == name)

    def test_a_flow_window_masks_the_route_counts_its_chain_and_the_mind_test(self):
        out, R = self.variant('flow', [first_id(stratum='flow:nbtc.bridge.near:claim')])
        c = R['M1']['counts']
        self.assertTrue(c['dominant'][rule.NC] and c['observed'][rule.NC])
        self.assertEqual((c['dominant']['unfavourable_yes'], c['dominant']['of']), (None, 28))
        self.assertEqual(c['capability_documented'], self.RA['M1']['counts']['capability_documented'])
        btc, btc_a = self.chain(R, 'Bitcoin'), self.chain(self.RA, 'Bitcoin')
        self.assertEqual((btc['observed_use'], btc['dominant_route']), (None, None))
        self.assertEqual(btc['documented'], btc_a['documented'])
        self.assertEqual(self.chain(R, 'Ethereum')['dominant_route'], self.chain(self.RA, 'Ethereum')['dominant_route'])
        w = R['mind']['omni_dominant_widely']
        self.assertTrue(w[rule.NC])
        self.assertEqual((w['dominant_yes'], w['undecided'], w['of_measured']), (None, None, 8))
        # DEVIATIONS item 21: an unfinished reading leaves the test undecided unless the decided readings
        # settle it; here they do (the frozen verdict: not met), so the verdict stays and only the counts,
        # which the unfinished window could still change, are masked (R8-c).
        frozen_w = json.loads(read(os.path.join(out, 'results.json')))['mind']['omni_dominant_widely']
        self.assertEqual((frozen_w['met'], frozen_w['undecided']), (False, 1))
        self.assertIs(w['met'], False)
        self.assertTrue(R['M9'][rule.NC])
        self.assertGreater(let_through_is_frozen(self, out), 0)
        t = thesis(out)
        self.assertNotIn('Omni is the dominant route on', t)
        self.assertIn('How many of them run on Omni is not completed at the deadline', t)
        self.assertNotIn('Measured value: not completed', t)
        tb = read(os.path.join(out, 'published', 'tables.md'))
        self.assertRegex(tb, r'\n\| Bitcoin \|[^\n]*\| not completed \| not completed \|\n')
        c1 = read(os.path.join(out, 'published', 'chart1-routes.svg'))
        lab = [(x, y) for x, y, s, t in svg_texts(c1) if t == 'Bitcoin' and s == 10]
        self.assertEqual(len(lab), 1)
        self.assertTrue(any(t == rule.WORDS and abs(y - lab[0][1]) < 0.01 and x > lab[0][0]
                            for x, y, s, t in svg_texts(c1)))

    def test_a_census_window_masks_its_token_counts_and_observed_use_only(self):
        out, R = self.variant('census', [first_id(family='census')])
        self.assertTrue(R['census'][rule.NC])
        self.assertEqual(set(R['census']['tokens'].values()), {None})
        self.assertEqual(R['census']['windows'], 48)
        self.assertTrue(R['M1']['counts']['observed'][rule.NC])
        self.assertEqual(R['M1']['counts']['dominant'], self.RA['M1']['counts']['dominant'])
        for r, ra in zip(R['M1']['chains'], self.RA['M1']['chains']):
            self.assertEqual(r['dominant_route'], ra['dominant_route'], r['chain'])
            self.assertIsNone(r['observed_use'])
        self.assertNotIn(rule.NC, R['mind']['omni_dominant_widely'])
        let_through_is_frozen(self, out)

    def test_an_index_month_is_named_and_left_out_of_the_picks(self):
        out, R = self.variant('index', [first_id(family='index', month='2026-02')])
        self.assertEqual(R['M6']['index_not_completed'], ['2026-02'])
        self.assertEqual(R['dest_audit_selection']['not_completed_months'], ['2026-02'])
        self.assertNotIn('2026-02', [r['month'] for r in R['M6']['index']])
        self.assertEqual(R['rule']['masked'], [])
        let_through_is_frozen(self, out)
        self.assertIn('Signature-index months not completed at the deadline: 2026-02.',
                      read(os.path.join(out, 'published', 'tables.md')))
        self.assertIn("picked by seed from the signature index's completed months (12 of 13; the others are named "
                      "in `audit/dest-audit.md`)", thesis(out))     # R8-g

    def test_a_window_with_a_completed_line_that_fails_the_gate_is_masked_and_listed(self):
        out, R = self.variant('gate', remove=[os.path.join('nb', 'RESOLVED')])
        self.assertGreaterEqual(len(R['rule']['completed_line_but_gate_unfinished']), 192)
        self.assertTrue(R['M9'][rule.NC] and R['M1']['counts']['dominant'][rule.NC])
        let_through_is_frozen(self, out)
        self.assertNotIn('{{', thesis(out))

    def test_sign_windows_mask_the_rates_not_the_neardata_shares_and_mark_both_panels(self):
        ids = [first_id(stratum='sign:2026-10:last90'), first_id(stratum='sign:2026-09:last90')]
        out, R = self.variant('sign', ids)
        for m in ('2026-09', '2026-10'):
            row = next(r for r in R['M6']['purpose'] if r['month'] == m)
            ra = next(r for r in self.RA['M6']['purpose'] if r['month'] == m)
            self.assertEqual((row['share'], row['blocks'], row['sign_calls_in_sample']),
                             (ra['share'], ra['blocks'], ra['sign_calls_in_sample']))
            self.assertTrue(row['per_day'][rule.NC])
        let_through_is_frozen(self, out)
        c2 = read(os.path.join(out, 'published', 'chart2-callers-cost.svg'))
        self.assertEqual(sum(1 for *_, t in svg_texts(c2) if t == rule.WORDS), 4)   # bars and per-request, 2 months
        t = thesis(out)
        for bad in ('not completed a day', 'not completed of October', 'not completed NEAR in September'):
            self.assertNotIn(bad, t)
        self.assertIn('`sign` calls in October 2026 and the trend are not completed at the deadline', t)

    def test_many_unfinished_months_wrap_their_footnotes_inside_the_chart(self):
        months = sorted({w['stratum'] for w in windows() if w['family'] == 'sign' and w['tier'] == 2})
        out, R = self.variant('wrap', [first_id(stratum=m) for m in months])
        c2 = read(os.path.join(out, 'published', 'chart2-callers-cost.svg'))
        h = rule._height(c2)
        foot = [(y, t) for x, y, s, t in svg_texts(c2) if s == 9 and x == charts_pad()]
        self.assertTrue(foot)
        for y, t in foot:
            self.assertLessEqual(len(t), rule.FOOT_CHARS)
            self.assertLess(y, h)
        joined = ' '.join(t for _, t in foot)
        for m in months:
            self.assertIn(m.split(':')[1], joined)


def charts_pad():
    import charts
    return float(charts.PAD)


class TestDestAudit(unittest.TestCase):
    """R4-k: the lookups, parsed offline from saved explorer responses (real public transactions)."""

    def stub(self, url):
        name = {'1e744e3384b4d9eabf7c44413981140babd4216db76cd6cc10a348c582366e07': 'btc-1e744e33.json',
                'c237f068cda1cbd972a4d0a93722ea238d1dd4f74300bfab592db5217502b61e': 'zec-spend.json'}
        for k, f in name.items():
            if url.endswith(k):
                return 200, open(os.path.join(FIX, f), 'rb').read()
        if 'mempool' in url:
            return 404, open(os.path.join(FIX, 'btc-missing.json'), 'rb').read()
        return 200, open(os.path.join(FIX, 'zec-missing.json'), 'rb').read()

    def test_lookups(self):
        sel = {'bitcoin': [{'receipt_id': 'r1', 'dest_txn': '1e744e3384b4d9eabf7c44413981140babd4216db76cd6cc10a348c582366e07',
                            'dest_address': 'bc1qp42j7hn3lup7gck6y6eks6x2lmnp800t6gy7sk'},
                           {'receipt_id': 'r2', 'dest_txn': '00' * 32, 'dest_address': 'bc1qx'},
                           {'receipt_id': 'r3', 'dest_txn': None}],
               'zcash': [{'receipt_id': 'r4', 'dest_txn': 'c237f068cda1cbd972a4d0a93722ea238d1dd4f74300bfab592db5217502b61e',
                          'dest_address': 't1cDnEJfCUJFfoetvRG3CjTVyPvyegT71zf'},
                         {'receipt_id': 'r5', 'dest_txn': '11' * 32, 'dest_address': 't1x'}],
               'not_completed_months': ['2026-02']}
        tmp = tempfile.mkdtemp()
        try:
            slept = []
            a = dest_audit.audit(sel, tmp, get=self.stub, sleep=slept.append)
        finally:
            shutil.rmtree(tmp)
        r = {x['receipt_id']: x for x in a['rows']}
        self.assertEqual((r['r1']['found'], r['r1']['confirmed'], r['r1']['from_signer_address'],
                          r['r1']['to_other_addresses']), (True, True, True, 129956))
        self.assertEqual(r['r1']['block_time_utc'], '2026-11-08T12:04:47Z')
        self.assertEqual(r['r1']['url'], 'https://mempool.space/tx/1e744e3384b4d9eabf7c44413981140babd4216db76cd6cc10a348c582366e07')
        self.assertIs(r['r2']['found'], False)
        self.assertIsNone(r['r3']['found'])
        self.assertEqual((r['r4']['found'], r['r4']['from_signer_address'], r['r4']['to_other_addresses']),
                         (True, True, 104000 + 28223170500))   # every output not to dest_address, change included
        self.assertIs(r['r5']['found'], False)
        self.assertEqual(a['summary']['BITCOIN'], {'picked': 3, 'found': 1, 'not_found': 1, 'unknown': 1, 'confirmed': 1,
                                                   'from_signer_address': 1})
        self.assertEqual(slept, [dest_audit.GAP_S] * 3)   # four lookups, 6 s apart; none for a row without a txid
        self.assertIn('not completed at the deadline: 2026-02.', dest_audit.table(a))

    def test_failures_are_recorded_per_pick_and_the_audit_goes_on(self):
        import http.client
        btc = '1e744e3384b4d9eabf7c44413981140babd4216db76cd6cc10a348c582366e07'
        zec = 'c237f068cda1cbd972a4d0a93722ea238d1dd4f74300bfab592db5217502b61e'
        unconf = json.loads(read(os.path.join(FIX, 'zec-spend.json')))
        unconf['data'][zec]['transaction']['block_id'] = -1
        seen = []

        def get(url):
            seen.append(url)
            t = url.rsplit('/', 1)[1]
            n = sum(1 for u in seen if u == url)
            if t == 'aa' * 32:
                return 200, b'<html>busy</html>'
            if t == 'bb' * 32:
                return 200, json.dumps({'data': {t: None}}).encode()
            if t == 'cc' * 32:
                raise http.client.IncompleteRead(b'')
            if t == 'dd' * 32:
                return 503, b'down'
            if t == btc:
                return (429, b'') if n == 1 else (200, read(os.path.join(FIX, 'btc-1e744e33.json')).encode())
            if t == zec:
                return 200, json.dumps(unconf).encode()
            raise AssertionError(url)
        sel = {'bitcoin': [{'receipt_id': f'b{i}', 'dest_txn': t, 'dest_address': 'bc1qp42j7hn3lup7gck6y6eks6x2lmnp800t6gy7sk'}
                           for i, t in enumerate(['aa' * 32, 'cc' * 32, btc, '../../x'])],
               'zcash': [{'receipt_id': f'z{i}', 'dest_txn': t, 'dest_address': 't1cDnEJfCUJFfoetvRG3CjTVyPvyegT71zf'}
                         for i, t in enumerate(['bb' * 32, 'dd' * 32, zec])]}
        tmp = tempfile.mkdtemp()
        try:
            slept = []
            a = dest_audit.audit(sel, tmp, get=get, sleep=slept.append)
            self.assertEqual(sorted(os.listdir(tmp)), sorted(f'{c}-{t}.json' for c, t in
                             [('bitcoin', 'aa' * 32), ('bitcoin', btc), ('zcash', 'bb' * 32), ('zcash', 'dd' * 32),
                              ('zcash', zec)]))
        finally:
            shutil.rmtree(tmp)
        r = {x['receipt_id']: x for x in a['rows']}
        self.assertEqual(len(r), 7)
        self.assertIsNone(r['b0']['found'])
        self.assertIn('not JSON', r['b0']['error'])
        self.assertIsNone(r['b1']['found'])
        self.assertIn('IncompleteRead', r['b1']['error'])
        self.assertIsNone(r['b1']['response_sha256'])
        self.assertEqual((r['b2']['found'], r['b2']['http'], r['b2']['to_other_addresses']), (True, 200, 129956))
        self.assertIsNone(r['b3']['found'])
        self.assertIn('not a 64-character hex id', r['b3']['note'])
        self.assertIsNone(r['z0']['found'])
        self.assertEqual((r['z1']['found'], r['z1']['http']), (None, 503))
        self.assertEqual((r['z2']['found'], r['z2']['confirmed'], r['z2']['block_time_utc']), (True, False, None))
        self.assertEqual(sum(1 for u in seen if u.endswith(btc)), 2)            # the 429 was retried once
        self.assertEqual(sum(1 for u in seen if u.endswith('cc' * 32)), 2)      # the network error too
        self.assertEqual(sum(1 for u in seen if u.endswith('dd' * 32)), 2)      # and the 503
        self.assertEqual(slept.count(60.0), 3)
        t = dest_audit.table(a)
        lines = {l.split(' | ')[1]: l for l in t.splitlines() if l.startswith('| ') and ' | ' in l}
        self.assertIn('| http 503 |', lines['z1'])
        self.assertIn('| error |', lines['b1'])
        self.assertIn('| yes | no |', lines['z2'])
        self.assertNotIn('T', lines['z2'].split(' | ')[4])                      # no block time for an unconfirmed one


class TestCombined(unittest.TestCase):
    """T-2: the secondary reading is printed from the combined file's "extension" key, never typed."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.A = os.path.join(cls.tmp, 'A')
        cls.B = os.path.join(cls.tmp, 'B')
        simulate.simulate(INSTANTS, cls.A, seed=11)
        shutil.copytree(cls.A, cls.B)
        drop_completed(cls.B, set(DROPPED))
        cls.RA = rule.run(INSTANTS, cls.A, os.path.join(cls.A, 'out'))
        rule.run(INSTANTS, cls.B, os.path.join(cls.B, 'out'))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def extension(self, name, ids):
        """A synthetic pass over B's five windows that completes `ids` with A's pages, then the merge."""
        ext = os.path.join(self.tmp, f'ext-{name}')
        os.makedirs(os.path.join(ext, 'nb', 'pages'))
        with open(os.path.join(ext, 'selection.json'), 'w') as f:
            json.dump({'windows': len(DROPPED), 'ids': DROPPED}, f)
        with open(os.path.join(ext, 'nb', 'windows.jsonl'), 'w') as f:
            for i in DROPPED:
                if i in ids:
                    shutil.copytree(os.path.join(self.A, 'nb', 'pages', i), os.path.join(ext, 'nb', 'pages', i))
                    f.write(json.dumps({'id': i, 'event': 'completed'}) + '\n')
                else:
                    f.write(json.dumps({'id': i, 'event': 'not_completed'}) + '\n')
        with open(os.path.join(ext, 'nb', 'DONE'), 'w') as f:
            f.write(json.dumps({'result': 'synthetic'}) + '\n')
        merged = os.path.join(self.tmp, f'merged-{name}')
        merge.merge(self.B, ext, merged)
        rule.run(INSTANTS, merged, os.path.join(merged, 'out'))
        cpath = os.path.join(self.tmp, f'combined-{name}.json')
        return combine.main(os.path.join(self.B, 'out'), cpath, os.path.join(merged, 'out'), ext)

    def test_full_pass_restores_run_A_as_the_secondary_reading(self):
        c = self.extension('full', set(DROPPED))
        e = c['extension']
        self.assertTrue(e['ran'])
        self.assertEqual(e['results']['rule']['masked'], [])
        a = json.loads(read(os.path.join(self.A, 'out', 'published', 'results.json')))
        self.assertEqual([p for p in combine.differs(a, e['results']) if not p.startswith('completeness')], [])
        self.assertIn('M10/SOL/verdict', e['differs'])
        self.assertEqual(e['n_differs'], len(e['differs']))
        t = thesis(None, c)
        self.assertIn('| SOL | [54.1%, 100.0%] | [54.7%, 100.0%] | no clear move |', t)   # from the extension key
        self.assertIn('| SOL | not completed | not completed | not completed |', t)        # the primary, unchanged
        self.assertIn('Migration windows completed after it: 75 of 75.', t)

    def test_no_digit_in_the_secondary_reading_comes_from_outside_a_placeholder(self):
        c = self.extension('digits', set(DROPPED))
        c['dest_audit'] = SYNTH_AUDIT
        text = fill.expand(read(TMPL), c, os.path.join(ROOT, 'THESIS.ext.tmpl.md'))
        marked, holes = fill.fill(text, c, mark=lambda s: '\x00' + s + '\x01')
        self.assertEqual(holes, [])
        blocks = fill.blocks(os.path.join(ROOT, 'THESIS.ext.tmpl.md'))
        for name, (ran, _) in blocks.items():
            body, _ = fill.fill(ran, c, mark=lambda s: '\x00' + s + '\x01')
            bare = re.sub(r'\x00[^\x01]*\x01', '', body)
            bare = re.sub(r'\]\([^)]*\)', ']()', bare)   # image paths are file names, not numbers
            self.assertIsNone(re.search(r'\d', bare), (name, bare))
        self.assertIn('**A secondary reading: the \x00extension pass after the frozen deadline', marked)
        self.assertIn('**The same chart from the secondary reading**', marked)

    def test_the_fill_stops_without_the_extension_key(self):
        c = json.loads(read(os.path.join(self.B, 'out', 'published', 'results.json')))
        with self.assertRaises(fill.FillError):
            fill.expand(read(TMPL), c, os.path.join(ROOT, 'THESIS.ext.tmpl.md'))
        c['extension'] = {'ran': True}
        text = fill.expand(read(TMPL), c, os.path.join(ROOT, 'THESIS.ext.tmpl.md'))
        self.assertTrue(fill.fill(text, c)[1])   # every extension placeholder is a hole

    def test_a_pass_that_ends_early_leaves_short_strata_not_completed(self):
        c = self.extension('partial', {'4855e63b0ef7', '8b2eb8a36710', '005ad02070bc'})  # not SOL early
        R = c['extension']['results']
        self.assertTrue(R['M10']['SOL']['readings']['not_completed'])
        self.assertEqual(R['M10']['SOL']['verdict'], 'not completed')
        self.assertNotIn('not_completed', R['M10']['SOL']['chart'][4])
        self.assertNotIn('not_completed', R['by_month']['M4']['2025-03'])
        t = thesis(None, c)
        self.assertEqual(t.count('| SOL | not completed | not completed | not completed |'), 2)

    def test_the_rebuild_command_writes_the_same_page_offline(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('rebuild', os.path.join(ROOT, 'rebuild.py'))
        rb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rb)
        res = json.loads(read(os.path.join(self.B, 'out', 'published', 'results.json')))
        audit = os.path.join(self.tmp, 'audit-rb')
        with self.assertRaises(SystemExit):
            rb.rebuild(self.B, out=os.path.join(self.tmp, 'out-rb'), audit=audit, thesis=os.path.join(self.tmp, 'T.md'))
        with self.assertRaises(SystemExit):   # no saved audit: stops after the rule, before the combine
            rb.rebuild(self.B, out=os.path.join(self.tmp, 'out-rb'), audit=audit, thesis=os.path.join(self.tmp, 'T.md'),
                       draft=True)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, 'out-rb', 'combined.json')))
        os.makedirs(audit)
        with open(os.path.join(audit, 'dest-audit.json'), 'w') as f:
            json.dump(synth_audit(res), f)
        with self.assertRaises(SystemExit):   # sentences still to write: only --draft lets them through
            rb.rebuild(self.B, out=os.path.join(self.tmp, 'out-rb2'), audit=audit, thesis=os.path.join(self.tmp, 'T.md'))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, 'out-rb2')))   # stopped before writing anything
        rb.rebuild(self.B, out=os.path.join(self.tmp, 'out-rb'), audit=audit, thesis=os.path.join(self.tmp, 'T.md'),
                   draft=True)
        self.assertEqual(read(os.path.join(self.tmp, 'T.md')), thesis(os.path.join(self.B, 'out')))
        for f in ('tables.md',) + CHARTS:
            self.assertEqual(read(os.path.join(self.tmp, 'out-rb', 'published', f)),
                             read(os.path.join(self.B, 'out', 'published', f)), f)

    def test_a_stale_destination_audit_stops_the_combine(self):
        res = json.loads(read(os.path.join(self.B, 'out', 'published', 'results.json')))
        good = synth_audit(res)
        self.assertEqual(combine.combine(res, dest_audit=good)['dest_audit'], good)
        stale = dict(good, rows=good['rows'][1:] + good['rows'][:1])
        with self.assertRaises(combine.StaleAudit):
            combine.combine(res, dest_audit=stale)

    def test_no_extension_prints_the_fixed_sentence(self):
        t = thesis(os.path.join(self.B, 'out'))
        self.assertIn('No pass ran after the deadline.', t)
        self.assertNotIn('secondary reading', t)
        self.assertNotIn('\n\n\n', t)


if __name__ == '__main__':
    unittest.main()
