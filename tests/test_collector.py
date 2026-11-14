"""Offline tests for the collector and the flow rules. No network: the API is faked.
Run: python3 -I -m unittest discover -s tests -v   (from the repo root)"""
import base64, json, os, random, shutil, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'collector'))
sys.path.insert(0, os.path.join(ROOT, 'analysis'))
import nb, design, sampler, flows  # noqa: E402

FIX = os.path.join(ROOT, 'tests', 'fixtures')


class Clock:
    def __init__(self, t):
        self.t = t
        self.slept = []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


class TestLedger(unittest.TestCase):
    def test_caps_and_gap(self):
        with tempfile.TemporaryDirectory() as d:
            L = nb.Ledger(os.path.join(d, 'l.jsonl'), cap24=300, cap60=6, min_gap=10.5)
            t0 = 1_000_000.0
            for i in range(300):
                L.append({'t': t0 + i * 11, 'credits': 1})
            last = t0 + 299 * 11
            # daily cap reached: the next call waits until the first entry ages out
            w = L.wake_time(1, last + 11)
            self.assertAlmostEqual(w, t0 + 86400, delta=1)
            # gap: right after a call, the next one waits min_gap
            L2 = nb.Ledger(os.path.join(d, 'l2.jsonl'), min_gap=10.5)
            L2.append({'t': 100.0, 'credits': 1})
            self.assertAlmostEqual(L2.wake_time(1, 101.0), 110.5, delta=0.01)
            # a 4-credit call needs 4 credits of room
            L3 = nb.Ledger(os.path.join(d, 'l3.jsonl'), cap24=10, min_gap=0)
            L3.append({'t': 0.0, 'credits': 7})
            self.assertAlmostEqual(L3.wake_time(4, 100.0), 86400.0, delta=0.01)
            self.assertEqual(L3.wake_time(3, 100.0), 100.0)

    def test_minute_cap(self):
        with tempfile.TemporaryDirectory() as d:
            L = nb.Ledger(os.path.join(d, 'l.jsonl'), cap60=6, min_gap=0)
            for i in range(6):
                L.append({'t': 10.0 + i, 'credits': 1})
            self.assertAlmostEqual(L.wake_time(1, 16.0), 70.0, delta=0.01)

    def test_default_pacing_never_puts_six_calls_in_60s(self):
        # Nov 10 pilot: the 6th call inside any 60 s drew 429 in 7 of 7 cases; calls 1-5 passed 40 of 40.
        with tempfile.TemporaryDirectory() as d:
            L = nb.Ledger(os.path.join(d, 'l.jsonl'))
            t = 1000.0
            for _ in range(30):
                t = L.wake_time(1, t)
                L.append({'t': t, 'credits': 1})
            ts = [e[0] for e in L.entries]
            for a, b in zip(ts, ts[5:]):
                self.assertGreaterEqual(b - a, 62.0)  # six calls span over 60 s with a 2 s margin
            fin = design.capacity_finish([], 0.0, 6)
            self.assertGreaterEqual(fin, 62.0)
            import inspect
            sig = inspect.signature(design.capacity_finish).parameters
            self.assertEqual((sig['cap60'].default, sig['gap'].default), (nb.CAP_60S, nb.MIN_GAP))

    def test_credits_for(self):
        self.assertEqual(nb.credits_for('/x?limit=25'), 1)
        self.assertEqual(nb.credits_for('/x?limit=100'), 4)
        self.assertEqual(nb.credits_for('/x?limit=26'), 2)
        self.assertEqual(nb.credits_for('/x/count?before_ts=1'), 1)

    def test_retry_is_ledgered(self):
        with tempfile.TemporaryDirectory() as d:
            clk = Clock(1000.0)
            L = nb.Ledger(os.path.join(d, 'l.jsonl'), min_gap=10.5)
            calls = []

            def opener(url):
                calls.append(url)
                return (429, b'') if len(calls) == 1 else (200, b'{"data": []}')
            c = nb.NB(L, 'test', now=clk.now, sleep=clk.sleep, opener=opener, log=lambda m: None)
            st, body = c.get('/a?limit=25')
            self.assertEqual(st, 200)
            self.assertEqual(len(calls), 2)
            self.assertEqual(len(L.entries), 2)
            self.assertGreaterEqual(L.entries[1][0] - L.entries[0][0], 10.5)


def cursor(r):
    return base64.b64encode(json.dumps({'k': r['receipt_id']}).encode()).decode()


class TestQuotaHeaders(unittest.TestCase):
    def test_headers_logged_and_retry_after_honoured(self):
        with tempfile.TemporaryDirectory() as d:
            led = nb.Ledger(os.path.join(d, 'ledger.jsonl'))
            clock = [1000.0]
            slept = []
            def sleep(x):
                slept.append(x)
                clock[0] += x
            c = nb.NB(led, 'test', now=lambda: clock[0], sleep=sleep, log=lambda m: None)
            replies = [(429, b'', {'Retry-After': '120', 'X-RateLimit-Remaining': '0'}),
                       (200, b'{"data": []}', {'X-RateLimit-Remaining': '299', 'Content-Type': 'application/json'})]
            def opener(url):
                st, body, h = replies.pop(0)
                c.last_headers = h
                return st, body
            c.opener = opener
            st, body = c.get('/fts/x/txns?limit=25&before_ts=1')
            self.assertEqual(st, 200)
            self.assertIn(120.0, slept)
            logged = [json.loads(l) for l in open(os.path.join(d, 'ratelimit-headers.jsonl'))]
            self.assertEqual([l['status'] for l in logged], [429, 200])
            self.assertNotIn('Content-Type', logged[1]['headers'])
            self.assertEqual(len([l for l in open(os.path.join(d, 'ledger.jsonl'))]), 2)  # both tries ledgered


class FakeAPI:
    """Serves rows (sorted newest first) with before_ts and next cursors, like NearBlocks v3."""

    def __init__(self, rows, fail_after=None):
        self.rows = sorted(rows, key=lambda r: (-int(r['block_timestamp']), r['receipt_id']))
        self.calls = []
        self.fail_after = fail_after

    def get(self, path):
        self.calls.append(path)
        if self.fail_after is not None and len(self.calls) > self.fail_after:
            raise KeyboardInterrupt('simulated crash')
        from urllib.parse import urlsplit, parse_qs
        q = parse_qs(urlsplit(path).query)
        if 'next' in q:
            k = json.loads(base64.b64decode(q['next'][0]))['k']
            i = [r['receipt_id'] for r in self.rows].index(k) + 1
        else:
            b = int(q['before_ts'][0])
            i = next((j for j, r in enumerate(self.rows) if int(r['block_timestamp']) < b), len(self.rows))
        page = self.rows[i:i + 25]
        meta = {'next_page': cursor(page[-1])} if len(page) == 25 else {}
        return 200, {'data': page, 'meta': meta}


class LedgerStub:
    def used(self, now):
        return (0, 0)


class Client:
    def __init__(self, api):
        self.api = api
        self.ledger = LedgerStub()

    def get(self, path):
        return self.api.get(path)


def mkrows(times_ns, prefix='r'):
    return [{'receipt_id': f'{prefix}{i}', 'block_timestamp': str(t), 'predecessor_account_id': 'x.near'}
            for i, t in enumerate(times_ns)]


def instants_one(window):
    return {'meta': {'T0_utc': 'test'}, 'windows': [window]}


class TestSampler(unittest.TestCase):
    def window(self, s, e, fam='sign'):
        return {'id': 'w1', 'key': 'k#0', 'family': fam, 'tier': 1, 'segments_ns': [[s, e]], 'cost_plan': 1.0}

    def test_busy_window_paged_to_start(self):
        S = 10**18
        times = [S + i * 10**9 for i in range(400)]  # one row per second
        api = FakeAPI(mkrows(times))
        with tempfile.TemporaryDirectory() as d:
            w = self.window(S + 100 * 10**9, S + 260 * 10**9)  # 160 rows inside
            smp = sampler.Sampler(instants_one(w), d, Client(api), now=lambda: 0, sleep=lambda s: None, deadline=1e12,
                                  log=lambda m: None)
            self.assertEqual(smp.run(), 'complete')
            pages = smp.pages_of('w1', 0)
            self.assertGreater(len(pages), 6)
            got = [r for p in pages for r in p['rows'] if S + 100 * 10**9 <= int(r['block_timestamp']) < S + 260 * 10**9]
            self.assertEqual(len({r['receipt_id'] for r in got}), 160)
            self.assertTrue(pages[-1]['done'])

    def test_zero_count_window_written(self):
        S = 10**18
        api = FakeAPI(mkrows([S, S + 10**12]))
        with tempfile.TemporaryDirectory() as d:
            w = self.window(S + 10**11, S + 2 * 10**11)
            smp = sampler.Sampler(instants_one(w), d, Client(api), now=lambda: 0, sleep=lambda s: None, deadline=1e12,
                                  log=lambda m: None)
            smp.run()
            ev = [json.loads(l) for l in open(os.path.join(d, 'nb', 'windows.jsonl'))]
            self.assertEqual(ev[-1]['event'], 'completed')
            self.assertEqual(len(smp.pages_of('w1', 0)), 1)

    def test_restart_does_not_repeat_calls(self):
        S = 10**18
        times = [S + i * 10**9 for i in range(400)]
        rows = mkrows(times)
        w = self.window(S + 50 * 10**9, S + 300 * 10**9)
        with tempfile.TemporaryDirectory() as d:
            api1 = FakeAPI(rows, fail_after=3)
            smp = sampler.Sampler(instants_one(w), d, Client(api1), now=lambda: 0, sleep=lambda s: None, deadline=1e12,
                                  log=lambda m: None)
            with self.assertRaises(KeyboardInterrupt):
                smp.run()
            api2 = FakeAPI(rows)
            smp2 = sampler.Sampler(instants_one(w), d, Client(api2), now=lambda: 0, sleep=lambda s: None, deadline=1e12,
                                   log=lambda m: None)
            smp2.run()
            all_calls = api1.calls[:3] + api2.calls
            self.assertEqual(len(all_calls), len(set(all_calls)))
            pages = smp2.pages_of('w1', 0)
            self.assertEqual(len(pages), len(all_calls))
            got = {r['receipt_id'] for p in pages for r in p['rows'] if S + 50 * 10**9 <= int(r['block_timestamp']) < S + 300 * 10**9}
            self.assertEqual(len(got), 250)

    def test_tied_timestamps_not_skipped(self):
        S = 10**18
        times = [S + (i // 10) * 10**9 for i in range(200)]  # ten rows share each timestamp
        api = FakeAPI(mkrows(times))
        with tempfile.TemporaryDirectory() as d:
            w = self.window(S, S + 30 * 10**9)
            smp = sampler.Sampler(instants_one(w), d, Client(api), now=lambda: 0, sleep=lambda s: None, deadline=1e12,
                                  log=lambda m: None)
            smp.run()
            got = {r['receipt_id'] for p in smp.pages_of('w1', 0) for r in p['rows'] if S <= int(r['block_timestamp']) < S + 30 * 10**9}
            self.assertEqual(len(got), 200)

    def test_deadline_marks_not_completed(self):
        api = FakeAPI(mkrows([10**18]))
        with tempfile.TemporaryDirectory() as d:
            w = self.window(10**18 - 10**9, 10**18 + 10**9)
            smp = sampler.Sampler(instants_one(w), d, Client(api), now=lambda: 100.0, sleep=lambda s: None, deadline=50.0,
                                  log=lambda m: None)
            self.assertEqual(smp.run(), 'deadline')
            ev = [json.loads(l) for l in open(os.path.join(d, 'nb', 'windows.jsonl'))]
            self.assertEqual(ev[-1]['event'], 'not_completed')
            self.assertEqual(api.calls, [])


class TestResolution(unittest.TestCase):
    def test_resolution_runs_between_tiers(self):
        S = 10**18
        def ft(i, t, tx, aff='intents.near', inv='omni.bridge.near', delta='5'):
            return {'receipt_id': f'f{i}', 'event_index': 0, 'affected_account_id': aff, 'involved_account_id': inv,
                    'cause': 'TRANSFER', 'delta_amount': delta, 'block_timestamp': str(t), 'transaction_hash': tx,
                    'contract_account_id': 'sol.omft.near', 'predecessor_account_id': 'x.near'}
        rows = [ft(i, S + i * 10**10, f'T{i}') for i in range(30)]
        rows.append(ft(99, S + 5 * 10**10 + 9 * 10**9, 'T5'))  # T5's legs span 9 s: a candidate
        base = FakeAPI(rows)
        calls = []
        class API:
            def get(self, path):
                calls.append(path)
                if path.startswith('/txns/'):
                    return 200, {'txns': []}
                return base.get(path)
        flow = {'id': 'wf', 'key': 'flow#0', 'family': 'flow', 'tier': 1, 'token': 'sol.omft.near', 'guard_s': 30.0,
                'segments_ns': [[S + 2 * 10**10, S + 20 * 10**10]], 'cost_plan': 1.0}
        sign = {'id': 'ws', 'key': 'sign#0', 'family': 'sign', 'tier': 2,
                'segments_ns': [[S, S + 10**10]], 'cost_plan': 1.0}
        with tempfile.TemporaryDirectory() as d:
            smp = sampler.Sampler({'meta': {}, 'windows': [flow, sign]}, d, Client(API()), now=lambda: 0,
                                  sleep=lambda s: None, deadline=1e12, log=lambda m: None)
            self.assertEqual(smp.run(), 'complete')
            res = [json.loads(l) for l in open(os.path.join(d, 'nb', 'resolve.jsonl'))]
            txs = {r['tx'] for r in res}
            self.assertIn('T5', txs)                                  # the candidate is resolved
            self.assertTrue(all(r['resolved'] for r in res))
            self.assertEqual(sum(r['audit'] for r in res), 18)        # T2..T19 included; all audited (< 20)
            first_txn = min(i for i, c in enumerate(calls) if c.startswith('/txns/'))
            last_txn = max(i for i, c in enumerate(calls) if c.startswith('/txns/'))
            first_sign = min(i for i, c in enumerate(calls) if 'v1.signer' in c)
            self.assertLess(last_txn, first_sign)                     # before tier 2
            self.assertTrue(all('/fts/' in c for c in calls[:first_txn]))
            marker = json.load(open(os.path.join(d, 'nb', 'RESOLVED')))
            self.assertEqual(marker['candidates'], 1)


class TestPilotM10(unittest.TestCase):
    def test_rate_rule(self):
        import pilot_m10
        t_p = 1_000_000.0
        rows = [{'block_timestamp': str(int((t_p - k * 100) * 1e9))} for k in range(1, 26)]  # 25 rows over 2,500 s
        r, n, span = pilot_m10.rate_from_page(rows, t_p)
        self.assertEqual(n, 25)
        self.assertAlmostEqual(span, 2500.0)
        self.assertAlmostEqual(r, 25 / 2500 * 86400)
        self.assertEqual(pilot_m10.rate_from_page([], t_p)[0], 0.0)
        one = [{'block_timestamp': str(int((t_p - 86400 * 3) * 1e9))}]
        self.assertAlmostEqual(pilot_m10.rate_from_page(one, t_p)[0], 1 / 3)

    def test_periods_and_zero_rate_length(self):
        import pilot_m10
        T0 = design.ts('2026-11-10T11:00:00Z')
        names = [p[0] for p in pilot_m10.periods(T0)]
        self.assertEqual(names[0], 'early')
        self.assertEqual(len(names), 8)
        rates = json.load(open(os.path.expanduser('~/Data/hackathons/near-2026/b-collect/pilot/rates-plan-draft.json')))
        rates['m10_rate_per_day']['nbtc.bridge.near']['early'] = 0.0
        ws = [w for w in design.build(rates, T0) if w['family'] == 'migration' and w['token'] == 'nbtc.bridge.near'
              and w['period'] == 'early']
        self.assertEqual(len(ws), 8)
        D = design.ts(design.EARLY[1]) - design.ts(design.EARLY[0])
        self.assertTrue(all(abs(w['nominal_s'] - D) < 1 for w in ws))


class TestRpc(unittest.TestCase):
    def setUp(self):
        import rpc
        self.rpc = rpc
        with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'rpc-shapes.json')) as f:
            self.shapes = json.load(f)

    def test_classify_live_shapes(self):
        c = self.rpc.classify
        self.assertEqual(c(self.shapes['absent']), ('absent', None))
        self.assertEqual(c(self.shapes['method_missing'])[0], 'contract_error')
        self.assertEqual(c(self.shapes['value']), ('value', '195782492'))
        self.assertEqual(c(None), ('fail', None))
        self.assertEqual(c({'jsonrpc': '2.0', 'error': {'name': 'HANDLER_ERROR', 'cause': {'name': 'UNKNOWN_BLOCK'}}}),
                         ('fail', None))
        self.assertEqual(c({'jsonrpc': '2.0', 'error': {'name': 'HANDLER_ERROR', 'cause': {'name': 'NO_CONTRACT_CODE'}}}),
                         ('absent', None))

    def plan(self, d):
        p = {'bounds': {'2025-01': {'height': 136000000, 'ts_ns': 1}, '2026-04': {'height': 200000000, 'ts_ns': 2},
                        'T0': {'height': 223800034, 'ts_ns': 3}}}
        path = os.path.join(d, 'nd_plan.json')
        with open(path, 'w') as f:
            json.dump(p, f)
        return path

    def test_absent_is_final_and_done_written(self):
        d = tempfile.mkdtemp(prefix='rpc-test-')
        self.addCleanup(shutil.rmtree, d)
        shapes = self.shapes

        def viewer(contract, fn, h):
            if contract == 'nbtc.bridge.near' and h == 136000000:
                return shapes['absent']
            if contract == 'v1.signer':
                return {'jsonrpc': '2.0', 'result': {'result': list(json.dumps({'Running': {}}).encode())}}
            return shapes['value']
        self.rpc.run(self.plan(d), d, viewer=viewer)
        self.assertTrue(os.path.exists(os.path.join(d, 'rpc', 'DONE')))
        with open(os.path.join(d, 'rpc', 'supply.jsonl')) as f:
            rows = [json.loads(l) for l in f]
        early = [r for r in rows if r['point'] == '2025-01' and r['token'] == 'nbtc.bridge.near'][0]
        self.assertEqual((early['status'], early['ok'], early['total_supply']), ('absent', True, None))
        self.assertEqual(len(os.listdir(os.path.join(d, 'rpc', 'raw'))), 8)

    def test_transient_failure_blocks_done(self):
        d = tempfile.mkdtemp(prefix='rpc-test-')
        self.addCleanup(shutil.rmtree, d)
        with self.assertRaises(SystemExit):
            self.rpc.run(self.plan(d), d, viewer=lambda c, fn, h: None)
        self.assertFalse(os.path.exists(os.path.join(d, 'rpc', 'DONE')))


class TestDesign(unittest.TestCase):
    def test_inclusion_probability_uniform(self):
        st = design.Stratum('t', [(0.0, 50.0), (80.0, 100.0)])  # D = 70
        ell = 30.0
        rng = random.Random(1)
        pts = [1.0, 25.0, 49.0, 81.0, 99.0]
        hits = {p: 0 for p in pts}
        N = 40000
        for w in design.place(st, ell, N, rng):
            for p in pts:
                if any(s <= p < e for s, e in w['segments']):
                    hits[p] += 1
        for p in pts:
            self.assertAlmostEqual(hits[p] / N, ell / (st.D + ell), delta=0.01)

    def test_ht_unbiased(self):
        st = design.Stratum('t', [(0.0, 100.0)])
        events = [random.Random(2).uniform(0, 100) ** 1.0 for _ in range(500)]
        events = [x for x in events if x < 30] * 3 + events  # uneven intensity
        truth = len(events)
        rng = random.Random(3)
        ests = []
        for _ in range(3000):
            ws = design.place(st, 7.0, 6, rng)
            ests.append(sum(w['weight'] * sum(1 for x in events if any(s <= x < e for s, e in w['segments'])) for w in ws))
        mean = sum(ests) / len(ests)
        self.assertAlmostEqual(mean / truth, 1.0, delta=0.02)

    def test_whole_strata_are_exact(self):
        st = design.Stratum('t', [(0.0, 50.0), (80.0, 100.0)])
        ws = design.whole(st)
        self.assertEqual([w['segments'] for w in ws], [[(0.0, 50.0)], [(80.0, 100.0)]])
        self.assertTrue(all(w['weight'] == 1.0 and w['whole'] for w in ws))
        events = [random.Random(4).uniform(0, 100) for _ in range(300)]
        inside = sum(1 for x in events if x < 50 or x >= 80)
        est = sum(w['weight'] * sum(1 for x in events if any(s <= x < e for s, e in w['segments'])) for w in ws)
        self.assertEqual(est, inside)

    def test_btc_omft_flow_read_whole(self):
        rates = json.load(open(os.path.expanduser('~/Data/hackathons/near-2026/b-collect/pilot/rates-plan-draft.json')))
        T0 = design.ts('2026-11-10T11:00:00Z')
        ws = design.build(rates, T0)
        b = [w for w in ws if w['family'] == 'flow' and w['token'] == 'btc.omft.near']
        claim = [w for w in b if w['period'] == 'claim']
        out = [w for w in b if w['period'] == 'outside']
        self.assertEqual([w['segments'] for w in claim], [[(design.ts(design.CLAIM[0]), design.ts(design.CLAIM[1]))]])
        pieces = design.subtract(design.subtract([(T0 - 90 * design.DAY, T0)],
                                                 (design.ts(design.CLAIM[0]), design.ts(design.CLAIM[1]))),
                                 (design.ts(design.FLAG[0]), design.ts(design.FLAG[1])))
        self.assertEqual(sorted(s for w in out for s in w['segments']), sorted(pieces))
        self.assertTrue(all(w['weight'] == 1.0 for w in b))
        # every other flow token is still sampled
        self.assertTrue(all(not w.get('whole') for w in ws if w['family'] == 'flow' and w['token'] != 'btc.omft.near'))

    def test_to_real_maps_pieces(self):
        st = design.Stratum('t', [(0.0, 10.0), (20.0, 30.0)])
        self.assertEqual(st.to_real(5.0, 15.0), [(5.0, 10.0), (20.0, 25.0)])

    def test_pages_model(self):
        self.assertAlmostEqual(design.expected_pages(20.0), 1.15677, places=4)
        self.assertAlmostEqual(design.expected_pages(20.0, True), 1.4113, places=3)


def load_fixture(name):
    return json.load(open(os.path.join(FIX, name)))['data']


class TestFlows(unittest.TestCase):
    def all_transfers(self, rows, token):
        ts = [flows.row_ts(r) for r in rows]
        return flows.transfers(rows, token, min(ts), max(ts) + 1)

    def test_poa_deposit_and_withdrawal(self):
        rows = load_fixture('ft-eth-omft.json')
        tr, c = self.all_transfers(rows, 'eth.omft.near')
        routes = {(t['route'], t['direction']) for t in tr}
        self.assertIn(('POA', 'in'), routes)   # MINT at omft.near + TRANSFER omft.near -> intents.near
        self.assertIn(('POA', 'out'), routes)  # BURN at intents.near
        self.assertNotIn('OMNI', {t['route'] for t in tr})

    def test_omni_solana(self):
        rows = load_fixture('ft-sol-omft.json')
        tr, c = self.all_transfers(rows, 'sol.omft.near')
        self.assertEqual({t['route'] for t in tr}, {'OMNI'})
        self.assertEqual({t['direction'] for t in tr}, {'in', 'out'})

    def test_zec_connector_and_nearside(self):
        rows = load_fixture('ft-zec-omft.json')
        tr, c = self.all_transfers(rows, 'zec.omft.near')
        routes = {t['route'] for t in tr}
        self.assertIn('OMNI', routes)
        self.assertIn('NEARSIDE', routes)  # intents.near -> ordinary account

    def test_net_zero_refund_dropped_and_window_by_first_leg(self):
        base = 10**18
        rows = [
            {'receipt_id': 'a', 'event_index': 0, 'affected_account_id': 'intents.near', 'involved_account_id': 'omni.bridge.near',
             'cause': 'TRANSFER', 'delta_amount': '100', 'block_timestamp': str(base + 10), 'transaction_hash': 'T1',
             'contract_account_id': 'sol.omft.near'},
            {'receipt_id': 'b', 'event_index': 0, 'affected_account_id': 'omni.bridge.near', 'involved_account_id': 'intents.near',
             'cause': 'TRANSFER', 'delta_amount': '100', 'block_timestamp': str(base + 20), 'transaction_hash': 'T1',
             'contract_account_id': 'sol.omft.near'},
            {'receipt_id': 'c', 'event_index': 0, 'affected_account_id': 'intents.near', 'involved_account_id': 'omni.bridge.near',
             'cause': 'TRANSFER', 'delta_amount': '7', 'block_timestamp': str(base - 5), 'transaction_hash': 'T2',
             'contract_account_id': 'sol.omft.near'},
            {'receipt_id': 'd', 'event_index': 1, 'affected_account_id': 'intents.near', 'involved_account_id': 'omni.bridge.near',
             'cause': 'TRANSFER', 'delta_amount': '3', 'block_timestamp': str(base + 5), 'transaction_hash': 'T2',
             'contract_account_id': 'sol.omft.near'},
        ]
        tr, c = flows.transfers(rows + rows[:1], 'sol.omft.near', base, base + 100)
        self.assertEqual(c['net_zero'], 1)   # T1 refunds within the transaction
        self.assertEqual(c['outside'], 1)    # T2 starts before the window
        self.assertEqual(tr, [])

    def test_mixed_omni_and_poa_is_unknown(self):
        base = 10**18
        def row(rid, aff, inv, cause, delta, t):
            return {'receipt_id': rid, 'event_index': 0, 'affected_account_id': aff, 'involved_account_id': inv,
                    'cause': cause, 'delta_amount': delta, 'block_timestamp': str(base + t), 'transaction_hash': 'TM',
                    'contract_account_id': 'sol.omft.near'}
        rows = [row('a', 'intents.near', 'omni.bridge.near', 'TRANSFER', '50', 1),
                row('b', 'intents.near', None, 'MINT', '20', 2)]
        tr, c = flows.transfers(rows, 'sol.omft.near', base, base + 100)
        self.assertEqual(len(tr), 1)
        self.assertEqual(tr[0]['route'], 'UNKNOWN')
        self.assertTrue(tr[0]['mixed'])
        self.assertEqual(c['mixed'], 1)

    def test_resolution_candidates(self):
        base = 10**18
        s9 = 9_000_000_000
        def row(rid, t, tx):
            return {'receipt_id': rid, 'event_index': 0, 'affected_account_id': 'intents.near',
                    'involved_account_id': 'omni.bridge.near', 'cause': 'TRANSFER', 'delta_amount': '5',
                    'block_timestamp': str(base + t), 'transaction_hash': tx, 'contract_account_id': 'sol.omft.near'}
        rows = [row('a', 10, 'SHORT'), row('b', 10 + 600_000_000, 'SHORT'),   # 0.6 s span: not a candidate
                row('c', 20, 'LONG'), row('d', 20 + s9, 'LONG'),             # 9 s span: candidate
                row('e', 90 * 10**9, 'EDGE')]                                 # last leg within 5 s of hi
        tr, c = flows.transfers(rows, 'sol.omft.near', base, base + 100 * 10**9, hi_ns=base + 93 * 10**9)
        by = {t['tx']: t for t in tr}
        self.assertFalse(by['SHORT']['resolve'])
        self.assertTrue(by['LONG']['resolve'])
        self.assertTrue(by['EDGE']['resolve'])
        self.assertEqual(c['resolve_candidates'], 2)

    def test_resolved_transaction_matches_window_view(self):
        body = json.load(open(os.path.join(FIX, 'txns-fts-sol-omni-out.json')))['body']
        first, net, route = flows.resolved_transfer(body, 'sol.omft.near')
        self.assertEqual(net, -274663988)          # one Intents leg, not two
        self.assertEqual(route, 'OMNI')
        self.assertEqual(first, 1794139437285116632)
        self.assertIsNone(flows.resolved_transfer(body, 'eth.omft.near'))

    def test_census_filter_check(self):
        rows = load_fixture('omni-ft-txns.json')  # this pilot pull was unfiltered
        toks, off = flows.census_tokens(rows)
        self.assertGreater(off, 0)
        self.assertIn('sol.omft.near', toks)


if __name__ == '__main__':
    unittest.main()
