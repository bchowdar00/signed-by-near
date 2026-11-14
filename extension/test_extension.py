"""Offline tests for the extension draft: fake clock, fake NearBlocks, no network, no real data.

  python3 -I -m unittest discover -s extension -p 'test_*.py'
"""
import json, os, shutil, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, 'collector'))
import run_ext as X  # noqa: E402
import sampler  # noqa: E402

FROZEN = os.path.join(REPO, 'frozen', 'instants.json')


class Clock:
    def __init__(self, t):
        self.t = t

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += max(s, 0.001)


def fake_primary(d, tail_k, done=True):
    with open(FROZEN) as f:
        W = json.load(f)['windows']
    os.makedirs(os.path.join(d, 'nb'))
    with open(os.path.join(d, 'nb', 'windows.jsonl'), 'w') as f:
        for i, w in enumerate(W):
            ev = 'not_completed' if i >= len(W) - tail_k else 'completed'
            f.write(json.dumps({'id': w['id'], 'event': ev, 'rows': 999}) + '\n')
    with open(os.path.join(d, 'nb', 'ledger.jsonl'), 'w') as f:
        f.write(json.dumps({'t': 0.0, 'credits': 1, 'url': 'x', 'purpose': 'counted'}) + '\n')
    if done:
        open(os.path.join(d, 'nb', 'DONE'), 'w').write('deadline\n')


class TestExtension(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.p, self.e = os.path.join(self.tmp, 'primary'), os.path.join(self.tmp, 'ext')

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_select_takes_the_tail_and_never_writes_the_primary(self):
        fake_primary(self.p, 5)
        before = {f: open(os.path.join(self.p, 'nb', f), 'rb').read() for f in ('windows.jsonl', 'ledger.jsonl')}
        X.select(FROZEN, self.p, self.e)
        sel = json.load(open(os.path.join(self.e, 'selection.json')))
        self.assertEqual(sel['windows'], 5)
        W = json.load(open(FROZEN))['windows']
        self.assertEqual(sel['ids'], [w['id'] for w in W[-5:]])
        for f, b in before.items():
            self.assertEqual(open(os.path.join(self.p, 'nb', f), 'rb').read(), b)

    def test_select_refuses_before_the_frozen_run_ends(self):
        fake_primary(self.p, 5, done=False)
        with self.assertRaises(SystemExit):
            X.select(FROZEN, self.p, self.e, now=lambda: sampler.ts(sampler.DEADLINE_UTC) + 1, running=lambda: False)
        open(os.path.join(self.p, 'STOP'), 'w').close()
        with self.assertRaises(SystemExit):  # stopped, but the sampler is still running
            X.select(FROZEN, self.p, self.e, now=lambda: sampler.ts(sampler.DEADLINE_UTC) + 1, running=lambda: True)
        with self.assertRaises(SystemExit):  # stopped before the deadline
            X.select(FROZEN, self.p, self.e, now=lambda: sampler.ts(sampler.DEADLINE_UTC) - 1, running=lambda: False)
        X.select(FROZEN, self.p, self.e, now=lambda: sampler.ts(sampler.DEADLINE_UTC) + 1, running=lambda: False)
        self.assertEqual(json.load(open(os.path.join(self.e, 'selection.json')))['windows'], 5)

    def test_first_429_stops_the_pass_with_no_retry(self):
        fake_primary(self.p, 6)
        X.select(FROZEN, self.p, self.e)
        clock = Clock(sampler.ts(X.NOT_BEFORE_UTC) - 5)
        calls = []

        def opener(url):
            calls.append(url)
            if len(calls) <= 2:
                return 200, json.dumps({'data': [], 'meta': {}}).encode()
            return 429, b''
        end = X.run(self.e, now=clock.now, sleep=clock.sleep, opener=opener, log=lambda m: None)
        self.assertEqual(end['result'], 'deadline')
        self.assertEqual(end['stopped_by']['status'], 429)
        self.assertEqual(len(calls), 3)  # two pages, one refusal, no retry
        ev = [json.loads(l) for l in open(os.path.join(self.e, 'nb', 'windows.jsonl'))]
        self.assertTrue(all(e['event'] in ('completed', 'not_completed') for e in ev))
        self.assertEqual(len({e['id'] for e in ev}), 6)
        led = [json.loads(l) for l in open(os.path.join(self.e, 'nb', 'ledger.jsonl'))]
        self.assertEqual(sum(1 for r in led if r.get('purpose') == X.PURPOSE), 3)
        self.assertGreaterEqual(min(r['t'] for r in led if r.get('purpose') == X.PURPOSE), sampler.ts(X.NOT_BEFORE_UTC))

    def test_cap_holds_when_the_ledger_is_full(self):
        fake_primary(self.p, 3)
        X.select(FROZEN, self.p, self.e)
        t0 = sampler.ts(X.NOT_BEFORE_UTC)
        with open(os.path.join(self.e, 'nb', 'ledger.jsonl'), 'a') as f:
            for i in range(X.CAP_24H):  # a full cap, made within the last hour before the start
                f.write(json.dumps({'t': t0 - 3600 + i, 'credits': 1, 'url': 'y', 'purpose': 'counted'}) + '\n')
        clock = Clock(t0)
        calls = []
        end = X.run(self.e, now=clock.now, sleep=clock.sleep,
                    opener=lambda u: calls.append(u) or (200, b'{"data": [], "meta": {}}'), log=lambda m: None)
        self.assertEqual(calls, [])  # the cap frees only after the deadline, so no call is made
        self.assertEqual(end['result'], 'deadline')


if __name__ == '__main__':
    unittest.main()
