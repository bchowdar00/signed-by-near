"""NearBlocks sampler (METHOD §6, §6.10). Runs the frozen window list in `instants.json` in its
frozen order, tier 1 first. Every window is paged to its start with no page cap; the ledger
(nb.py) waits for quota instead of dropping anything. At the sampling deadline every window not
completed is marked "not_completed" in nb/windows.jsonl, and the sampler stops. instants.json is
never edited.

Pagination uses the API's own next-page cursor (it encodes timestamp, shard and event index), so
rows that share a timestamp are never skipped. A segment ends when a page holds a row older than
the segment's lower bound, holds fewer rows than the limit, or has no next cursor.

Flow and migration windows fetch [s - guard, e + guard) so that the transactions whose first
intents.near leg lies in [s, e) can be completed; assignment happens in the analysis.

Each page is written atomically to nb/pages/<window id>/<segment>-<page>.json before the next
call, so a restart resumes from the last cursor without repeating a call.

After the last tier-1 window and before the first tier-2 window, the sampler resolves
transactions (METHOD §3): every included transaction flagged as a candidate by analysis/flows.py
(last observed leg within 5 s of the fetched range's end, or legs spanning more than 5 s), plus a
seeded audit of 20 included transactions, each read whole from /v3/txns/{hash}/fts into
nb/txns/<hash>.json and logged in nb/resolve.jsonl; nb/RESOLVED marks the phase done.

Usage:
  python3 -I sampler.py run <instants.json> <data_dir> [--purpose counted|shakedown] [--ledger <ledger.jsonl>] [--no-resolve]
  (--no-resolve is for shakedown and verification runs; the counted run always resolves)
"""
import datetime, glob, json, os, random, sys, time, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'analysis'))
import nb  # noqa: E402
import design  # noqa: E402
import flows  # noqa: E402

AUDIT_N = 20          # seeded audit of included transactions (METHOD §3, §6.10)
RESOLVE_ROUNDS = 3    # rounds of FAIL_WAIT_S before a resolution failure is recorded and skipped

LIMIT = 25
DEADLINE_UTC = '2026-11-13T00:00:00Z'
FAIL_WAIT_S = 600.0


def ts(iso):
    return datetime.datetime.strptime(iso, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).timestamp()


def utc(t=None):
    return datetime.datetime.fromtimestamp(time.time() if t is None else t, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def row_ts(r):
    v = r.get('block_timestamp')
    if v is None:
        v = (r.get('block') or {}).get('block_timestamp')
    return int(v)


def slim(r):
    r = dict(r)
    m = r.get('meta')
    if isinstance(m, dict):
        r['meta'] = {k: m.get(k) for k in ('contract', 'decimals', 'symbol', 'name') if k in m}
    return r


def base_path(w):
    f = w['family']
    if f == 'sign':
        return f'/accounts/v1.signer/receipts?method=sign&limit={LIMIT}'
    if f in ('flow', 'migration'):
        return f"/fts/{w['token']}/txns?limit={LIMIT}"
    if f == 'census':
        return f'/accounts/omni.bridge.near/ft-txns?involved=intents.near&limit={LIMIT}'
    if f == 'index':
        return f'/multichain/signatures?limit={LIMIT}'
    raise ValueError(f)


def page_path(base, before_ns=None, cursor=None):
    if cursor:
        return base + '&next=' + urllib.parse.quote(cursor, safe='')
    return base + f'&before_ts={before_ns}'


def seg_bounds(w):
    """[(lo_ns, hi_ns)] fetched for each segment."""
    if w['family'] == 'index':
        return [(None, int(w['instant_ns']))]
    g = int(round(w.get('guard_s', 0.0) * 1e9))
    return [(int(s) - g, int(e) + g) for s, e in w['segments_ns']]


def atomic_json(path, obj):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(obj, f, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class Deadline(Exception):
    pass


class Sampler:
    def __init__(self, instants, data_dir, client, now=time.time, sleep=time.sleep, deadline=None, log=print,
                 do_resolve=True):
        self.do_resolve = do_resolve
        self.windows = instants['windows']
        self.meta = instants['meta']
        self.dir = data_dir
        self.client, self.now, self.sleep, self.log = client, now, sleep, log
        self.deadline = ts(DEADLINE_UTC) if deadline is None else deadline
        os.makedirs(os.path.join(data_dir, 'nb', 'pages'), exist_ok=True)
        self.status_path = os.path.join(data_dir, 'nb', 'windows.jsonl')
        self.done = set()
        self.completed = set()
        if os.path.exists(self.status_path):
            with open(self.status_path) as f:
                for line in f:
                    if line.strip():
                        e = json.loads(line)
                        if e['event'] in ('completed', 'not_completed'):
                            self.done.add(e['id'])
                        if e['event'] == 'completed':
                            self.completed.add(e['id'])
        self.errors = 0

    def status_event(self, rec):
        with open(self.status_path, 'a') as f:
            f.write(json.dumps(rec, sort_keys=True) + '\n')
            f.flush()
            os.fsync(f.fileno())

    def pages_of(self, wid, seg):
        d = os.path.join(self.dir, 'nb', 'pages', wid)
        ps = sorted(glob.glob(os.path.join(d, f'{seg:02d}-*.json')), key=lambda p: int(p.rsplit('-', 1)[1][:-5]))
        out = []
        for p in ps:
            with open(p) as f:
                out.append(json.load(f))
        return out

    def run_segment(self, w, seg, lo, hi):
        wid = w['id']
        d = os.path.join(self.dir, 'nb', 'pages', wid)
        os.makedirs(d, exist_ok=True)
        prev = self.pages_of(wid, seg)
        if prev and prev[-1]['done']:
            return len(prev), sum(p['n_rows'] for p in prev)
        cursor = prev[-1]['next'] if prev else None
        pno = len(prev)
        base = base_path(w)
        while True:
            if self.now() >= self.deadline:
                raise Deadline()
            path = page_path(base, hi if cursor is None else None, cursor)
            st, body = self.client.get(path)
            if st != 200 or not isinstance(body, dict):
                self.errors += 1
                self.log(f'{utc(self.now())} page failed status={st} window={wid} seg={seg} page={pno}; waiting')
                self.sleep(FAIL_WAIT_S)
                continue
            rows = body.get('data') or []
            nxt = (body.get('meta') or {}).get('next_page')
            tss = [row_ts(r) for r in rows]
            if w['family'] == 'index':
                done = True
            else:
                done = len(rows) < LIMIT or not nxt or (min(tss) < lo if tss else True)
            atomic_json(os.path.join(d, f'{seg:02d}-{pno}.json'),
                        {'window': wid, 'seg': seg, 'page': pno, 'path': path, 'utc': utc(self.now()), 'http': st,
                         'n_rows': len(rows), 'next': nxt, 'done': done, 'lo_ns': lo, 'hi_ns': hi,
                         'rows': [slim(r) for r in rows]})
            pno += 1
            if done:
                ps = self.pages_of(wid, seg)
                return len(ps), sum(p['n_rows'] for p in ps)
            cursor = nxt

    # ---- transaction resolution (METHOD §3): after tier 1, before tier 2 ----
    def resolved(self):
        return (not self.do_resolve) or os.path.exists(os.path.join(self.dir, 'nb', 'RESOLVED'))

    def resolution_jobs(self):
        inc = {}
        for w in self.windows:
            if w['family'] != 'flow' or w['id'] not in self.completed:
                continue
            g = int(round(w.get('guard_s', 0.0) * 1e9))
            for seg, (s, e) in enumerate(w['segments_ns']):
                rows = [r for p in self.pages_of(w['id'], seg) for r in p['rows']]
                tr, _ = flows.transfers(rows, w['token'], int(s), int(e), hi_ns=int(e) + g)
                for t in tr:
                    d = inc.setdefault(t['tx'], {'windows': set(), 'candidate': False})
                    d['windows'].add(w['id'])
                    d['candidate'] = d['candidate'] or t['resolve']
        hashes = sorted(h for h in inc if h)
        rng = random.Random(design.seed_for('audit'))
        audit = set(rng.sample(hashes, min(AUDIT_N, len(hashes))))
        jobs = [(h, inc[h]['candidate'], h in audit, sorted(inc[h]['windows']))
                for h in hashes if inc[h]['candidate'] or h in audit]
        return jobs, len(hashes)

    def resolve(self):
        d = os.path.join(self.dir, 'nb', 'txns')
        os.makedirs(d, exist_ok=True)
        log_path = os.path.join(self.dir, 'nb', 'resolve.jsonl')
        seen = set()
        if os.path.exists(log_path):
            with open(log_path) as f:
                seen = {json.loads(l)['tx'] for l in f if l.strip()}
        jobs, n_included = self.resolution_jobs()
        for h, cand, aud, wids in jobs:
            if h in seen:
                continue
            st, body = 0, None
            for _ in range(RESOLVE_ROUNDS):
                if self.now() >= self.deadline:
                    raise Deadline()
                st, body = self.client.get(f'/txns/{h}/fts')
                if st == 200 and isinstance(body, dict):
                    break
                if st in (400, 403, 404):
                    break
                self.log(f'{utc(self.now())} resolve failed status={st} tx={h}; waiting')
                self.sleep(FAIL_WAIT_S)
            if st == 200 and isinstance(body, dict):
                atomic_json(os.path.join(d, f'{h}.json'), {'tx': h, 'utc': utc(self.now()), 'http': st, 'body': body})
            rec = {'tx': h, 'candidate': cand, 'audit': aud, 'windows': wids, 'http': st,
                   'resolved': st == 200 and isinstance(body, dict), 'utc': utc(self.now())}
            with open(log_path, 'a') as f:
                f.write(json.dumps(rec, sort_keys=True) + '\n')
                f.flush()
                os.fsync(f.fileno())
        atomic_json(os.path.join(self.dir, 'nb', 'RESOLVED'),
                    {'utc': utc(self.now()), 'included_transactions': n_included, 'jobs': len(jobs),
                     'candidates': sum(1 for j in jobs if j[1]), 'audit': sum(1 for j in jobs if j[2])})

    def run(self):
        todo = [w for w in self.windows if w['id'] not in self.done]
        try:
            for w in todo:
                if w['tier'] >= 2 and not self.resolved():
                    self.resolve()
                pages = rows = 0
                for seg, (lo, hi) in enumerate(seg_bounds(w)):
                    p, r = self.run_segment(w, seg, lo, hi)
                    pages += p
                    rows += r
                self.status_event({'id': w['id'], 'key': w['key'], 'family': w['family'], 'tier': w['tier'],
                                   'event': 'completed', 'pages': pages, 'rows': rows, 'utc': utc(self.now())})
                self.done.add(w['id'])
                self.completed.add(w['id'])
                self.write_status()
            if not self.resolved():
                self.resolve()
        except Deadline:
            for w in self.windows:
                if w['id'] not in self.done:
                    self.status_event({'id': w['id'], 'key': w['key'], 'family': w['family'], 'tier': w['tier'],
                                       'event': 'not_completed', 'utc': utc(self.now())})
                    self.done.add(w['id'])
            self.write_status(final=True)
            return 'deadline'
        self.write_status(final=True)
        return 'complete'

    def write_status(self, final=False):
        fam = {}
        for w in self.windows:
            k = f"{w['family']}/tier{w['tier']}"
            d = fam.setdefault(k, {'windows': 0, 'done': 0, 'plan_credits_remaining': 0.0})
            d['windows'] += 1
            if w['id'] in self.done:
                d['done'] += 1
            else:
                d['plan_credits_remaining'] += w.get('cost_plan', 0.0)
        for d in fam.values():
            d['plan_credits_remaining'] = round(d['plan_credits_remaining'], 1)
        now = self.now()
        c24, n60 = self.client.ledger.used(now)
        atomic_json(os.path.join(self.dir, 'STATUS.json'),
                    {'utc': utc(now), 'final': final, 'families': fam, 'errors': self.errors,
                     'ledger_credits_last_24h': c24, 'deadline_utc': DEADLINE_UTC,
                     'T0_utc': self.meta.get('T0_utc')})


def main():
    if sys.argv[1] != 'run':
        raise SystemExit(__doc__)
    instants = json.load(open(sys.argv[2]))
    data_dir = sys.argv[3]
    purpose = 'counted'
    if '--purpose' in sys.argv:
        purpose = sys.argv[sys.argv.index('--purpose') + 1]
    ledger_path = os.path.join(data_dir, 'nb', 'ledger.jsonl')
    if '--ledger' in sys.argv:
        ledger_path = sys.argv[sys.argv.index('--ledger') + 1]
    ledger = nb.Ledger(ledger_path)
    client = nb.NB(ledger, purpose, log=lambda m: print(m, flush=True))
    s = Sampler(instants, data_dir, client, log=lambda m: print(m, flush=True), do_resolve='--no-resolve' not in sys.argv)
    res = s.run()
    print(utc(), 'sampler finished:', res, flush=True)
    if res in ('complete', 'deadline'):
        open(os.path.join(data_dir, 'nb', 'DONE'), 'w').write(f'{res} {utc()}\n')


if __name__ == '__main__':
    main()
