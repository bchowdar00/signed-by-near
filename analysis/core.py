"""Stage-2 core (METHOD §3, §4.0, §7): loading the counted sample, turning windows into items,
and the estimators every measure shares.

Rule (COLLECTOR-DESIGN, stage 2): this code is frozen and stamped before it reads any counted
row. Until then it runs only on uncounted data (the shakedown, the pilots, tests/fixtures).

Estimators (METHOD §4.0):
- Totals are Horvitz–Thompson, sum_h sum_i w_hi y_hi, with each window's frozen weight.
- Every estimate carries 2,000 stratified bootstrap draws (class Est). For each stratum the
  draws resample its windows with replacement, seeded by design.seed_for('boot', stratum name),
  so every measure that uses a stratum sees the same draws and joint quantities (ratios across
  strata, the trend, M8, M9) are computed draw by draw. A stratum read whole keeps every window
  in every draw. Blocks of a neardata month are resampled the same way, seeded
  design.seed_for('boot-nd', month).
- A share is a ratio of two totals. Its 95% interval is the hull of the bootstrap percentile
  interval (draws with a zero denominator dropped and counted; more than 5% dropped makes the
  share "unstable") and the window-level bound (Kish's effective count over the window
  denominators in each stratum where both routes can occur, Clopper–Pearson, combined with
  weights T_h; c = s_h in one-route strata and strata read whole).
- Percentiles are the linear-interpolation kind (type 7) at 2.5% and 97.5%.
- Transfer shares are computed twice: unknown counted as not Omni (its lower end is L) and as
  Omni (its upper end is U). NEAR-side transfers are dropped from both. The interval read is [L, U].
- Sparse rule: no window with a transfer in the denominator is "none observed (0 of 0)"; fewer
  than 10 distinct transfers, or fewer than 3 windows with any, is "too sparse (x of n)", x the
  distinct (transaction, token) pairs and n the windows with any.
- Rates: the hull of the bootstrap interval and an exact (Garwood) Poisson interval on the
  windows' raw count over their covered time.
- States of a share, in METHOD §7's order: not completed, not measurable, inconclusive,
  consistent, contradicted, partly.
"""
import glob, json, math, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'collector'))
import flows  # noqa: E402
import intervals  # noqa: E402
import design  # noqa: E402

B = 2000
ALPHA = 0.05
DROP_MAX = 0.05
SPARSE_MIN_TRANSFERS = 10
SPARSE_MIN_WINDOWS = 3
DAY = 86400.0


# ---------------------------------------------------------------- estimates with their draws

def _ap(a, b, f):
    if a is None or b is None:
        return None
    return f(a, b)


def _div(a, b):
    return None if (a is None or b is None or b == 0) else a / b


class Est:
    """A point estimate with B bootstrap draws; arithmetic is draw by draw, None propagates
    (a None draw is a dropped draw)."""
    __slots__ = ('point', 'draws')

    def __init__(self, point, draws):
        self.point = point
        self.draws = list(draws)
        if len(self.draws) != B:
            raise ValueError('an Est needs exactly B draws')

    @staticmethod
    def const(c):
        return Est(c, [c] * B)

    @staticmethod
    def wrap(o):
        return o if isinstance(o, Est) else Est.const(o)

    def _bin(self, o, f):
        o = Est.wrap(o)
        return Est(f(self.point, o.point), [f(a, b) for a, b in zip(self.draws, o.draws)])

    def __add__(self, o):
        return self._bin(o, lambda a, b: _ap(a, b, lambda x, y: x + y))

    __radd__ = __add__

    def __sub__(self, o):
        return self._bin(o, lambda a, b: _ap(a, b, lambda x, y: x - y))

    def __rsub__(self, o):
        return Est.wrap(o) - self

    def __mul__(self, o):
        return self._bin(o, lambda a, b: _ap(a, b, lambda x, y: x * y))

    __rmul__ = __mul__

    def __truediv__(self, o):
        return self._bin(o, _div)

    def __rtruediv__(self, o):
        return Est.wrap(o) / self

    def dropped(self):
        return sum(1 for d in self.draws if d is None)

    def interval(self, alpha=ALPHA):
        """(lo, hi, dropped) by percentile over the draws that are not None."""
        xs = sorted(d for d in self.draws if d is not None)
        dr = B - len(xs)
        if not xs:
            return None, None, dr
        return percentile(xs, alpha / 2), percentile(xs, 1 - alpha / 2), dr

    def unstable(self):
        return self.dropped() > DROP_MAX * B


def percentile(sorted_xs, p):
    """Type-7 (linear interpolation) quantile of an already sorted list."""
    n = len(sorted_xs)
    if n == 1:
        return sorted_xs[0]
    h = (n - 1) * p
    k = int(math.floor(h))
    if k >= n - 1:
        return sorted_xs[-1]
    return sorted_xs[k] + (h - k) * (sorted_xs[k + 1] - sorted_xs[k])


def emin(*es):
    """Draw-by-draw minimum (used for capped scenarios)."""
    es = [Est.wrap(e) for e in es]
    f = lambda xs: None if any(x is None for x in xs) else min(xs)
    return Est(f([e.point for e in es]), [f(list(t)) for t in zip(*[e.draws for e in es])])


# ---------------------------------------------------------------- bootstrap index draws

_DRAWS = {}


def draws_for(name, n, whole=False, stream='boot'):
    """B lists of n indices for one stratum (or one neardata month), seeded from its name."""
    key = (stream, name, n, whole)
    if key not in _DRAWS:
        if whole or n == 0:
            idx = list(range(n))
            _DRAWS[key] = [idx] * B
        else:
            rng = random.Random(design.seed_for(stream, name))
            _DRAWS[key] = [[rng.randrange(n) for _ in range(n)] for _ in range(B)]
    return _DRAWS[key]


# ---------------------------------------------------------------- strata and totals

class Stratum:
    """One stratum's sampled windows: weights, covered seconds, segments and an item list per window.
    `complete` is False if any of its windows is not completed. `two_route` says whether both routes
    can occur (METHOD §4.0; a *.omft.near token)."""

    def __init__(self, name, windows, values, whole=False, complete=True, two_route=True, stream='boot'):
        self.name = name
        self.windows = windows
        self.values = values
        self.weights = [float(w['weight']) for w in windows]
        self.covered = [float(w.get('covered_s', 0.0)) for w in windows]
        self.segments = [[(int(s), int(e)) for s, e in w.get('segments_ns', [])] for w in windows]
        self.whole = bool(whole)
        self.complete = bool(complete)
        self.two_route = bool(two_route)
        self.stream = stream

    def __len__(self):
        return len(self.values)


def total(strata, f):
    """HT total of f(window items) over the strata, with its draws."""
    point, draws = 0.0, [0.0] * B
    for st in strata:
        ys = [w * f(v) for w, v in zip(st.weights, st.values)]
        point += sum(ys)
        for b, idx in enumerate(draws_for(st.name, len(ys), st.whole, st.stream)):
            draws[b] += sum(ys[i] for i in idx)
    return Est(point, draws)


def window_bound(strata, num, den, alpha=ALPHA):
    """METHOD §4.0 window-level bound: (C_L, C_U), or None if no stratum has a denominator."""
    tl = tu = ts = 0.0
    per = []
    for st in strata:
        nums = [num(v) for v in st.values]
        dens = [den(v) for v in st.values]
        T_h = sum(w * d for w, d in zip(st.weights, dens))
        if T_h <= 0:
            continue
        s_h = sum(w * x for w, x in zip(st.weights, nums)) / T_h
        if st.whole or not st.two_route:
            c = (s_h, s_h)
            m = None
        else:
            m = intervals.kish(dens)
            c = intervals.clopper_pearson(s_h * m, m, alpha)
        per.append({'stratum': st.name, 'T_h': T_h, 's_h': s_h, 'm_eff': m, 'c': list(c)})
        tl += T_h * c[0]
        tu += T_h * c[1]
        ts += T_h
    if ts <= 0:
        return None, per
    return (tl / ts, tu / ts), per


def ratio_share(strata, num, den, alpha=ALPHA):
    """One reading of a share (num/den per window): point, bootstrap, window bound and hull."""
    N, D = total(strata, num), total(strata, den)
    R = N / D
    blo, bhi, dropped = R.interval(alpha)
    bound, per = window_bound(strata, num, den, alpha)
    los = [x for x in (blo, bound[0] if bound else None) if x is not None]
    his = [x for x in (bhi, bound[1] if bound else None) if x is not None]
    return {'point': R.point, 'boot': [blo, bhi], 'bound': list(bound) if bound else None,
            'lo': min(los) if los else None, 'hi': max(his) if his else None,
            'dropped': dropped, 'unstable': dropped > DROP_MAX * B, 'per_stratum': per,
            'num_total': N.point, 'den_total': D.point, '_est': R}


# ---------------------------------------------------------------- transfer shares (§4.0, §7)

def amount_of(kind):
    if kind == 'count':
        return lambda t: 1.0
    if kind == 'units':
        return lambda t: t['units']
    if kind == 'usd':
        return lambda t: t['usd']
    if callable(kind):
        return kind
    raise ValueError(kind)


def transfer_share(strata, select=None, kind='units', alpha=ALPHA, num_pred=None):
    """Omni's share of the selected transfers, unknowns both ways (METHOD §4.0). `num_pred`
    narrows the numerator (e.g. withdrawals only, for p_CS in M9); an unknown-route transfer that
    meets it counts as Omni in the U reading."""
    sel_f = select or (lambda t: True)
    np_ = num_pred or (lambda t: True)
    a = amount_of(kind)

    def sel(v):
        return [t for t in v if t['route'] != 'NEARSIDE' and sel_f(t)]

    def numL(v):
        return sum(a(t) for t in sel(v) if t['route'] == 'OMNI' and np_(t))

    def numU(v):
        return sum(a(t) for t in sel(v) if t['route'] in ('OMNI', 'UNKNOWN') and np_(t))

    def den(v):
        return sum(a(t) for t in sel(v))

    rL = ratio_share(strata, numL, den, alpha)
    rU = ratio_share(strata, numU, den, alpha)
    distinct = set()
    windows_any = 0
    for st in strata:
        for v in st.values:
            s = sel(v)
            if s:
                windows_any += 1
            distinct.update((t['tx'], t['token']) for t in s)
    x, n = len(distinct), windows_any
    if n == 0:
        sparse = 'none observed (0 of 0)'
    elif x < SPARSE_MIN_TRANSFERS or n < SPARSE_MIN_WINDOWS:
        sparse = f'too sparse ({x} of {n})'
    else:
        sparse = None
    out = {'L': rL['lo'], 'U': rU['hi'], 'point_unknown_not_omni': rL['point'], 'point_unknown_omni': rU['point'],
           'reading_L': _public(rL), 'reading_U': _public(rU),
           'unstable': rL['unstable'] or rU['unstable'], 'sparse': sparse,
           'distinct_transfers': x, 'windows_with_any': n, 'windows': sum(len(st) for st in strata),
           'complete': all(st.complete for st in strata), 'strata': [st.name for st in strata],
           'n_unknown': sum(1 for st in strata for v in st.values for t in sel(v) if t['route'] == 'UNKNOWN')}
    out['_estL'], out['_estU'] = rL['_est'], rU['_est']
    return out


def _public(r):
    return {k: v for k, v in r.items() if not k.startswith('_')}


def state(r, tau):
    """METHOD §7, in order of precedence."""
    if not r['complete']:
        return 'not completed'
    if r['sparse']:
        return 'not measurable'
    L, U = r['L'], r['U']
    if r['unstable'] or L is None or U is None or (L < 0.5 and U >= tau):
        return 'inconclusive'
    if L >= tau:
        return 'consistent'
    if U < 0.5:
        return 'contradicted'
    return 'partly'


# ---------------------------------------------------------------- Poisson (Garwood) intervals

def gammainc_lower(a, x):
    """Regularized lower incomplete gamma P(a, x), a > 0 (Numerical Recipes 6.2)."""
    if x <= 0:
        return 0.0
    gln = math.lgamma(a)
    if x < a + 1.0:
        ap, s, d = a, 1.0 / a, 1.0 / a
        for _ in range(10000):
            ap += 1.0
            d *= x / ap
            s += d
            if abs(d) < abs(s) * 1e-15:
                break
        return s * math.exp(-x + a * math.log(x) - gln)
    tiny = 1e-300
    b = x + 1.0 - a
    c, d = 1.0 / tiny, 1.0 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-15:
            break
    return 1.0 - math.exp(-x + a * math.log(x) - gln) * h


def gammainv(p, a):
    """x with P(a, x) = p, by bisection."""
    lo, hi = 0.0, max(10.0, a * 10.0 + 50.0)
    for _ in range(300):
        mid = (lo + hi) / 2
        if gammainc_lower(a, mid) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-12 * max(1.0, hi):
            break
    return (lo + hi) / 2


def garwood(k, alpha=ALPHA):
    """Exact two-sided Poisson interval for a count k (Garwood 1936): at k = 0 it is
    (0, -ln(alpha/2)) = (0, 3.689) at 95% (DEVIATIONS interpretation 1)."""
    lo = 0.0 if k <= 0 else gammainv(alpha / 2, k)
    hi = gammainv(1 - alpha / 2, k + 1)
    return lo, hi


def rule_of_three(exposure):
    return 3.0 / exposure if exposure > 0 else None


def rate(strata, count, exposure, days, alpha=ALPHA):
    """Rate per day: HT total ÷ days with its bootstrap interval, hulled with Garwood on the raw
    count over the covered exposure (seconds). count(v) is a window's count; exposure(st, i) its
    covered seconds."""
    T = total(strata, count)
    R = T / days
    blo, bhi, dropped = R.interval(alpha)
    k = sum(count(v) for st in strata for v in st.values)
    E = sum(exposure(st, i) for st in strata for i in range(len(st)))
    g = None
    if E > 0:
        glo, ghi = garwood(k, alpha)
        g = [glo / E * DAY, ghi / E * DAY]
    los = [x for x in (blo, g[0] if g else None) if x is not None]
    his = [x for x in (bhi, g[1] if g else None) if x is not None]
    return {'per_day': R.point, 'boot': [blo, bhi], 'garwood': g, 'lo': min(los) if los else None,
            'hi': max(his) if his else None, 'raw_count': k, 'exposure_s': E, 'days': days,
            'complete': all(st.complete for st in strata), 'strata': [st.name for st in strata],
            '_est': R, '_total': T}


def overlap_s(segments, cut):
    a, b = cut
    return sum(max(0, min(e, b) - max(s, a)) for s, e in segments) / 1e9


# ---------------------------------------------------------------- loading the counted sample

def _ns(iso):
    return int(round(design.ts(iso))) * 1_000_000_000


CLAIM_NS = (_ns(design.CLAIM[0]), _ns(design.CLAIM[1]))
FLAG_NS = (_ns(design.FLAG[0]), _ns(design.FLAG[1]))


class Study:
    """The frozen design plus whatever the collector wrote under data_dir."""

    def __init__(self, instants_path, data_dir, tokens_path=None):
        with open(instants_path) as f:
            I = json.load(f)
        self.meta = I['meta']
        self.windows = I['windows']
        self.by_id = {w['id']: w for w in self.windows}
        self.strata = {}
        for w in self.windows:
            self.strata.setdefault(w['stratum'], []).append(w)
        for ws in self.strata.values():
            ws.sort(key=lambda w: w['i'])
        self.dir = data_dir
        tp = tokens_path or os.path.join(os.path.dirname(os.path.abspath(instants_path)), 'tokens.json')
        self.decimals = {}
        self.token_info = {}
        if os.path.exists(tp):
            with open(tp) as f:
                for t in json.load(f)['tokens']:
                    self.decimals[t['contract']] = int(t['decimals'])
                    self.token_info[t['contract']] = t
        self._load_status()
        self._load_resolution()
        self._cache = {}

    # -- execution status (nb/windows.jsonl) --
    def _load_status(self):
        self.completed, self.not_completed = set(), set()
        p = os.path.join(self.dir, 'nb', 'windows.jsonl')
        if os.path.exists(p):
            with open(p) as f:
                for line in f:
                    if line.strip():
                        e = json.loads(line)
                        (self.completed if e['event'] == 'completed' else self.not_completed).add(e['id'])
        self.page_problems = {}

    # -- transaction resolution (METHOD §3) --
    def _load_resolution(self):
        self.resolved_flag = os.path.exists(os.path.join(self.dir, 'nb', 'RESOLVED'))
        self.resolve_log = []
        p = os.path.join(self.dir, 'nb', 'resolve.jsonl')
        if os.path.exists(p):
            with open(p) as f:
                self.resolve_log = [json.loads(l) for l in f if l.strip()]
        self.candidate_tx = {r['tx'] for r in self.resolve_log if r['candidate'] and r['resolved']}
        self.audit_tx = {r['tx'] for r in self.resolve_log if r['audit'] and r['resolved']}
        self.unread_candidate_windows = set()
        for r in self.resolve_log:
            if r['candidate'] and not r['resolved']:
                self.unread_candidate_windows.update(r['windows'])

    def resolved_body(self, tx):
        p = os.path.join(self.dir, 'nb', 'txns', f'{tx}.json')
        if not os.path.exists(p):
            return None
        with open(p) as f:
            return json.load(f)['body']

    def window_complete(self, w):
        wid = w['id']
        if wid not in self.completed or wid in self.unread_candidate_windows:
            return False
        if w['family'] == 'flow' and not self.resolved_flag:
            return False  # resolution is part of completing a flow window (METHOD §3)
        if self.pages_problem(w):
            return False
        return True

    # -- pages --
    def seg_pages(self, wid, seg):
        d = os.path.join(self.dir, 'nb', 'pages', wid)
        ps = glob.glob(os.path.join(d, f'{seg:02d}-*.json'))
        ps.sort(key=lambda p: int(p.rsplit('-', 1)[1][:-5]))
        out = []
        for p in ps:
            with open(p) as f:
                out.append(json.load(f))
        return out

    def n_segments(self, w):
        return 1 if w['family'] == 'index' else len(w['segments_ns'])

    def pages_problem(self, w):
        """A completed window whose pages are not a gapless chain ending in done is not usable."""
        wid = w['id']
        if wid in self.page_problems:
            return self.page_problems[wid]
        prob = None
        for seg in range(self.n_segments(w)):
            ps = self.seg_pages(wid, seg)
            if not ps:
                prob = f'segment {seg} has no pages'
                break
            if [p['page'] for p in ps] != list(range(len(ps))):
                prob = f'segment {seg} pages not contiguous'
                break
            if not ps[-1]['done'] or any(p['http'] != 200 for p in ps):
                prob = f'segment {seg} not done or non-200'
                break
        self.page_problems[wid] = prob
        return prob

    def seg_rows(self, wid, seg):
        return [r for p in self.seg_pages(wid, seg) for r in p['rows']]

    # -- items per window --
    def sign_calls(self, w):
        k = ('sign', w['id'])
        if k in self._cache:
            return self._cache[k]
        out, seen = [], set()
        for seg, (s, e) in enumerate(w['segments_ns']):
            for r in self.seg_rows(w['id'], seg):
                t = flows.row_ts(r)
                rid = r.get('receipt_id')
                if not (int(s) <= t < int(e)) or rid in seen:
                    continue
                seen.add(rid)
                st = (r.get('outcome') or {}).get('status')
                out.append({'receipt_id': rid, 'ts_ns': t, 'predecessor': r.get('predecessor_account_id'),
                            'tx': r.get('transaction_hash'), 'ok': st,
                            'deposit': (r.get('actions_agg') or {}).get('deposit')})
        self._cache[k] = out
        return out

    def transfers(self, w):
        """Economic transfers of a flow or migration window (METHOD §3), each segment by
        flows.transfers with the collector's own hi_ns = e + guard; for flow windows the resolved
        reading replaces the observed one for every resolution candidate that was read."""
        k = ('tr', w['id'])
        if k in self._cache:
            return self._cache[k]
        tok = w['token']
        g = int(round(w.get('guard_s', 0.0) * 1e9))
        dec = self.decimals.get(tok)
        out, observed = [], {}
        cnt = {'tx_seen': 0, 'net_zero': 0, 'outside': 0, 'edge_risk': 0, 'mixed': 0, 'resolve_candidates': 0,
               'replaced': 0, 'moved_out': 0, 'resolved_no_leg': 0, 'net_zero_resolved': 0}
        for seg, (s, e) in enumerate(w['segments_ns']):
            s, e = int(s), int(e)
            tr, c = flows.transfers(self.seg_rows(w['id'], seg), tok, s, e, hi_ns=e + g)
            for key in ('tx_seen', 'net_zero', 'outside', 'edge_risk', 'mixed', 'resolve_candidates'):
                cnt[key] += c.get(key, 0)
            for t in tr:
                t = dict(t, window=w['id'], seg=seg, observed={'ts_ns': t['ts_ns'], 'net': _signed(t),
                                                               'route': t['route']}, resolved=False)
                observed[t['tx']] = t['observed']
                if w['family'] == 'flow' and t['tx'] in self.candidate_tx:
                    body = self.resolved_body(t['tx'])
                    rt = flows.resolved_transfer(body, tok) if body is not None else None
                    if rt is None:
                        cnt['resolved_no_leg'] += 1
                        continue
                    first, net, route = rt
                    if net == 0:
                        cnt['net_zero_resolved'] += 1
                        continue
                    if not (s <= first < e):
                        cnt['moved_out'] += 1
                        continue
                    legs = flows.resolved_legs(body, tok)
                    t.update({'ts_ns': first, 'amount': abs(net), 'direction': 'in' if net > 0 else 'out',
                              'route': route, 'mixed': flows.has_omni(legs) and flows.has_poa(legs, tok),
                              'resolved': True})
                    cnt['replaced'] += 1
                t['units'] = t['amount'] / (10 ** dec) if dec is not None else None
                out.append(t)
        self._cache[k] = out
        self._cache[('trc', w['id'])] = cnt
        self._cache[('obs', w['id'])] = observed
        return out

    def transfer_counters(self, w):
        self.transfers(w)
        return self._cache[('trc', w['id'])]

    def census_items(self, w):
        """Rows of a census window inside its segments: {token: rows involving intents.near}, off."""
        rows = []
        for seg, (s, e) in enumerate(w['segments_ns']):
            rows += [r for r in self.seg_rows(w['id'], seg) if int(s) <= flows.row_ts(r) < int(e)]
        toks, off = flows.census_tokens(rows)
        return {'tokens': toks, 'off': off, 'rows': sum(toks.values())}

    def index_rows(self, w):
        return self.seg_rows(w['id'], 0)

    # -- strata --
    def stratum(self, name, items=None):
        ws = self.strata[name]
        fam = ws[0]['family']
        if items is None:
            items = {'sign': self.sign_calls, 'flow': self.transfers, 'migration': self.transfers,
                     'census': self.census_items}[fam]
        complete = all(self.window_complete(w) for w in ws)
        vals = [items(w) if self.window_complete(w) else _empty(fam) for w in ws]
        tok = ws[0].get('token') or ''
        whole = bool(ws[0].get('whole'))
        return Stratum(name, ws, vals, whole=whole, complete=complete, two_route=tok.endswith('.omft.near'))

    def audit(self):
        """METHOD §3: the seeded audit compared with each window's view (first leg, net, route)."""
        rows, differ = [], set()
        for r in self.resolve_log:
            if not (r['audit'] and r['resolved']):
                continue
            body = self.resolved_body(r['tx'])
            for wid in r['windows']:
                w = self.by_id.get(wid)
                if w is None or w['family'] != 'flow':
                    continue
                self.transfers(w)
                ob = self._cache[('obs', wid)].get(r['tx'])
                rt = flows.resolved_transfer(body, w['token']) if body is not None else None
                res = {'ts_ns': rt[0], 'net': rt[1], 'route': rt[2]} if rt else None
                same = (ob is not None and res is not None and ob == res)
                if not same:
                    differ.add(r['tx'])
                rows.append({'tx': r['tx'], 'window': wid, 'token': w['token'], 'observed': ob, 'resolved': res,
                             'same': same})
        return {'audited': len({r['tx'] for r in rows}), 'differ': len(differ), 'rows': rows}


def _signed(t):
    return t['amount'] if t['direction'] == 'in' else -t['amount']


def _empty(fam):
    return {'tokens': {}, 'off': 0, 'rows': 0} if fam == 'census' else []
