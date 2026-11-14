"""Window design (METHOD §6): generates `instants.json` from T0, the seed and the pilot rates,
and selects the design by the clock (METHOD §6.10). Deterministic: the same inputs give the
same file, byte for byte.

Placement (every window family). A stratum is a set of real-time pieces, laid end to end on a
compressed line [0, D). A window of nominal length l starts at u ~ Uniform[-l, D) and covers
[max(u, 0), min(u + l, D)), mapped back to real time (one or more segments). Every instant of
the stratum is then covered by a given window with probability l / (D + l), so the
Horvitz-Thompson weight of each window is w = (D + l) / (n l) and sum_i w * y_i is unbiased for
the stratum total of y.

Usage:
  python3 -I design.py plan    <rates.json> <T0 iso> <out instants.json>
  python3 -I design.py select  <rates.json> <freeze iso> <ledger.jsonl> <out instants.json>
"""
import calendar, datetime, hashlib, json, math, random, sys

UTC = datetime.timezone.utc
DAY = 86400.0
SEED = 20261114
GUARD_S = 30.0            # flow and migration windows fetch 30 s either side to complete transactions
TARGET_ROWS = 20.0        # rows a window is sized to expect, guards included
PAGE = 25
RETRY_ALLOWANCE = 1.10    # budget multiplier for retries
DEADLINE = '2026-11-13T00:00:00Z'
CLAIM = ('2026-10-09T00:00:00Z', '2026-11-06T00:00:00Z')
FLAG = ('2026-09-29T00:00:00Z', '2026-10-05T00:00:00Z')   # Sep 29 to Oct 4 inclusive
EARLY = ('2025-01-01T00:00:00Z', '2025-07-01T00:00:00Z')  # M10 early period
CHART_MONTHS = ['2025-07', '2025-09', '2025-11', '2026-01', '2026-03', '2026-05', '2026-07']
SIGN_START = '2024-08'
N_SIGN_HIST, N_SIGN_RECENT_PER_90D = 6, 48
N_FLOW = 6                # per token per stratum (claim window, outside), unless overridden below
# Solana's claim-window strata carry C2b's Solana estimates, whose window-level interval narrows only
# with many windows (METHOD §4.0, §7): 18 each. Tokens that serve no verdict (not C2b, not M10) get
# 4 windows outside the claim window. Census 48.
SOLANA_TOKENS = ('sol.omft.near', 'sol-5ce3bf3a31af18be40ba30f721101b4341690186.omft.near',
                 'sol-c800a4bd850783ccb82c2b2c7e84175443606352.omft.near')
VERDICT_TOKENS = SOLANA_TOKENS + ('nbtc.bridge.near', 'btc.omft.near', 'zec.omft.near', 'eth.omft.near')
N_FLOW_CLAIM_SOLANA = 18
N_FLOW_OUTSIDE_MINOR = 4
# Read whole, not sampled (METHOD §4.0, §6.5): btc.omft.near carries about 1.2 rows a day, so 6
# windows of about 16 days would nearly cover each stratum and overlap, and their window-level bound
# would stay wide enough that BTC could not read "contradicted" even if POA carried it. Read whole,
# the stratum is exact, and it costs fewer pages.
WHOLE_TOKENS = ('btc.omft.near',)
N_CENSUS = 48
RESOLVE_CREDITS = 30      # tier 1: a seeded audit of 20 included transactions plus a reserve of 10 for
                          # candidates, each resolved with one /v3/txns/{hash}/fts call (METHOD §3, §6.10)
N_EARLY = 8
# Design rulings, copied into the frozen file's selection log. Figures from analysis/reach.py on the
# uncounted shakedown window sd-flow-sol and the Nov 9 rates (reach-sim.json), and from build() and
# select() at a freeze of 2026-11-10T11:00Z on the ledger of the evening of Nov 9.
RULINGS = [
    {'id': 'C2b-solana-estimates', 'date_utc': '2026-11-09', 'method': 'METHOD §7 C2b',
     'ruling': "C2b's Solana half (SOL; the Solana stablecoins pooled) gets estimates with intervals, not "
               "a verdict. A verdict must be reachable both ways at its primary tau (90%). The window-level "
               "bound gives an all-Omni stratum a lower limit of 0.025^(1/m), which reaches 90% only at "
               "m >= 36 (35 gives 0.89997, 36 gives 0.90261), m being Kish's effective count over window "
               "amounts, never above the window count. Option 1 (enough windows) does not fit: it needs 36 "
               "to 54 more windows even with equal window amounts, and about 162 more at SOL's measured "
               "spread, against 23 credits to spare.",
     'figures': {'windows_per_solana_claim_stratum': 18, 'solana_claim_strata': 3,
                 'sol_amounts_n': 14, 'sol_amounts_log_sd': 1.551,
                 'kish_lognormal_mean': {'18': 13.1, '36': 25.4, '54': 37.7, '72': 50.3, '108': 72.8},
                 'p_kish_ge_36_lognormal': {'18': 0.0, '36': 0.0, '54': 0.71, '72': 0.96, '108': 0.98},
                 'kish_resampled_mean': {'18': 16.3, '36': 32.6, '54': 48.8},
                 'extra_windows_needed': {'equal_amounts': '36 to 54', 'measured_spread': 162},
                 'credits_to_spare_at_11Z_freeze': 23},
     'kept': '18 windows per Solana token in the claim window, for the estimates\' precision'},
    {'id': 'btc-omft-read-whole', 'date_utc': '2026-11-09', 'method': 'METHOD §4.0, §6.5, §7 C2b',
     'ruling': "btc.omft.near is read whole in both flow strata (one window per piece, weight 1), so that "
               "BTC's verdict can go either way. With 6 sampled windows of about 16 days in the 28-day "
               "claim stratum, the all-POA upper limit stayed at or above 50% in most simulated draws, so "
               "BTC could not read contradicted even if POA carried it.",
     'figures': {'rate_rows_per_day': 1.22, 'window_days': 16.39,
                 'p_upper_below_50_by_log_sd': {'1.0': 0.07875, '1.55': 0.027, '2.0': 0.00875},
                 'median_upper_by_log_sd': {'1.0': 0.571, '1.55': 0.617, '2.0': 0.671},
                 'pages_whole_plan_stress': [6.85, 6.82], 'pages_12_windows_plan_stress': [17.37, 19.09]}},
]
OMNI_ACCOUNT = 'omni.bridge.near'
INTENTS = 'intents.near'
SIGN_LEN_CLIP = (60.0, 6 * 3600.0)


def ts(iso):
    return datetime.datetime.strptime(iso, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC).timestamp()


def iso(t):
    return datetime.datetime.fromtimestamp(t, UTC).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def ns(t):
    return int(round(t * 1e6)) * 1000


def seed_for(*parts):
    h = hashlib.sha256(('|'.join([str(SEED)] + [str(p) for p in parts])).encode()).hexdigest()
    return int(h[:16], 16)


def month_start(ym):
    y, m = map(int, ym.split('-'))
    return datetime.datetime(y, m, 1, tzinfo=UTC).timestamp()


def next_month(ym):
    y, m = map(int, ym.split('-'))
    return f'{y + (m == 12)}-{(m % 12) + 1:02d}'


def ym_of(t):
    d = datetime.datetime.fromtimestamp(t, UTC)
    return f'{d.year}-{d.month:02d}'


def subtract(pieces, cut):
    """Remove interval cut=(a,b) from a list of pieces."""
    a, b = cut
    out = []
    for s, e in pieces:
        if e <= a or s >= b:
            out.append((s, e))
        else:
            if s < a:
                out.append((s, a))
            if e > b:
                out.append((b, e))
    return [(s, e) for s, e in out if e > s]


class Stratum:
    def __init__(self, name, pieces):
        self.name = name
        self.pieces = sorted((float(s), float(e)) for s, e in pieces if e > s)
        self.D = sum(e - s for s, e in self.pieces)

    def to_real(self, x0, x1):
        segs, off = [], 0.0
        for s, e in self.pieces:
            L = e - s
            a, b = max(x0, off), min(x1, off + L)
            if b > a:
                segs.append((s + (a - off), s + (b - off)))
            off += L
        return segs


def place(stratum, ell, n, rng):
    ell = min(ell, stratum.D)
    out = []
    for i in range(n):
        u = -ell + (stratum.D + ell) * rng.random()
        x0, x1 = max(u, 0.0), min(u + ell, stratum.D)
        segs = stratum.to_real(x0, x1) if x1 > x0 else []
        out.append({'i': i, 'u': u, 'segments': segs, 'covered_s': x1 - x0 if x1 > x0 else 0.0,
                    'nominal_s': ell, 'D_s': stratum.D, 'n_h': n, 'weight': (stratum.D + ell) / (n * ell)})
    return out


def whole(stratum):
    """A stratum read whole: one window per piece, each of weight 1. No sampling, so its total is exact."""
    return [{'i': i, 'u': None, 'segments': [(s, e)], 'covered_s': e - s, 'nominal_s': e - s,
             'D_s': stratum.D, 'n_h': len(stratum.pieces), 'weight': 1.0, 'whole': True}
            for i, (s, e) in enumerate(stratum.pieces)]


_EP = {}


def _ep(l):
    """E[floor(N/25) + 1] for N ~ Poisson(l), from one pass over the pmf (log-space start)."""
    if l <= 0:
        return 1.0
    key = float('%.4g' % l)
    if key in _EP:
        return _EP[key]
    l = key
    top = int(l + 12 * math.sqrt(l) + 60)
    # pmf by recursion from the mode in log space to avoid underflow
    logp = [0.0] * (top + 1)
    logp[0] = -l
    for j in range(1, top + 1):
        logp[j] = logp[j - 1] + math.log(l) - math.log(j)
    cdf, val, acc = 0.0, 1.0, 0.0
    # E[floor(N/25)] = sum_{k>=1} P(N >= 25k)
    cum = []
    for j in range(top + 1):
        acc += math.exp(logp[j])
        cum.append(acc)
    k = 1
    while PAGE * k <= top:
        val += max(0.0, 1.0 - cum[PAGE * k - 1])
        k += 1
    _EP[key] = val
    return val


def expected_pages(lam, stress=False):
    """E[floor(N/25) + 1], N ~ Poisson(lam); under stress lam is multiplied by exp(Z - 1/2), Z ~ N(0,1)."""
    if not stress:
        return _ep(lam)
    tot = wsum = 0.0
    for j in range(-160, 161):
        z = j / 20.0
        w = math.exp(-0.5 * z * z)
        tot += w * _ep(lam * math.exp(z - 0.5))
        wsum += w
    return tot / wsum


def n_flow(tok, period):
    if period == 'claim' and tok in SOLANA_TOKENS:
        return N_FLOW_CLAIM_SOLANA
    if period == 'outside' and tok not in VERDICT_TOKENS:
        return N_FLOW_OUTSIDE_MINOR
    return N_FLOW


def build(rates, T0):
    """Return the full design (both tiers) for data cutoff T0 (unix seconds, on the hour)."""
    T90 = T0 - 90 * DAY
    T365 = T0 - 365 * DAY
    claim = (ts(CLAIM[0]), ts(CLAIM[1]))
    flag = (ts(FLAG[0]), ts(FLAG[1]))
    windows = []

    # ---- sign windows (M3-M5) ----
    sign_rate = rates['sign_rate_per_day_by_month']
    ym = SIGN_START
    while month_start(ym) < T90:
        a, b = month_start(ym), min(month_start(next_month(ym)), T90)
        r = sign_rate[ym]
        ell = min(max(TARGET_ROWS / r * DAY, SIGN_LEN_CLIP[0]), SIGN_LEN_CLIP[1])
        st = Stratum(f'sign:{ym}' + (':early-part' if b < month_start(next_month(ym)) else ''), [(a, b)])
        tier = 1 if month_start(next_month(ym)) > T365 else 2
        for w in place(st, ell, N_SIGN_HIST, random.Random(seed_for('sign', st.name))):
            w.update({'family': 'sign', 'tier': tier, 'stratum': st.name, 'month': ym, 'rate_plan_per_day': r})
            windows.append(w)
        ym = next_month(ym)
    # the 90 days to T0, one stratum per calendar-month part
    t = T90
    while t < T0:
        ym = ym_of(t)
        b = min(month_start(next_month(ym)), T0)
        st = Stratum(f'sign:{ym}:last90', [(t, b)])
        n = max(4, int(round(N_SIGN_RECENT_PER_90D * st.D / (90 * DAY))))
        r = sign_rate[ym]
        ell = min(max(TARGET_ROWS / r * DAY, SIGN_LEN_CLIP[0]), SIGN_LEN_CLIP[1])
        for w in place(st, ell, n, random.Random(seed_for('sign', st.name))):
            w.update({'family': 'sign', 'tier': 1, 'stratum': st.name, 'month': ym, 'rate_plan_per_day': r})
            windows.append(w)
        t = b

    # ---- flow windows (M1, M2, M9, late period of M10) ----
    outside = subtract(subtract([(T90, T0)], claim), flag)
    for tok in rates['tokens']:
        r = rates['flow_rate_per_day'][tok]
        ell = max(TARGET_ROWS / r * DAY - 2 * GUARD_S, 60.0)
        for sname, pieces in (('claim', [claim]), ('outside', outside)):
            st = Stratum(f'flow:{tok}:{sname}', pieces)
            if tok in WHOLE_TOKENS:
                ws = whole(st)
            else:
                ws = place(st, ell, n_flow(tok, sname), random.Random(seed_for('flow', st.name)))
            for w in ws:
                w.update({'family': 'flow', 'tier': 1, 'stratum': st.name, 'token': tok, 'period': sname,
                          'rate_plan_per_day': r, 'guard_s': GUARD_S})
                windows.append(w)

    # ---- Omni census (M1 observed use) ----
    st = Stratum('census', subtract([(T90, T0)], flag))
    r = rates['census_rate_per_day']
    for w in place(st, TARGET_ROWS / r * DAY, N_CENSUS, random.Random(seed_for('census'))):
        w.update({'family': 'census', 'tier': 1, 'stratum': st.name, 'rate_plan_per_day': r})
        windows.append(w)

    # ---- migration windows (M10), tier 2 ----
    for tok in rates['m10_tokens']:
        periods = [('early', [(ts(EARLY[0]), ts(EARLY[1]))], N_EARLY)]
        for ym in CHART_MONTHS:
            a, b = month_start(ym), month_start(next_month(ym))
            if b <= T90:
                periods.append((f'chart:{ym}', [(a, b)], 1))
        for pname, pieces, n in periods:
            r = rates['m10_rate_per_day'][tok][pname.split(':')[0] if pname == 'early' else pname]
            ell = max(TARGET_ROWS / r * DAY - 2 * GUARD_S, 60.0) if r > 0 else max(p[1] - p[0] for p in pieces)
            st = Stratum(f'migration:{tok}:{pname}', pieces)
            for w in place(st, ell, n, random.Random(seed_for('migration', st.name))):
                w.update({'family': 'migration', 'tier': 2, 'stratum': st.name, 'token': tok, 'period': pname,
                          'rate_plan_per_day': r, 'guard_s': GUARD_S})
                windows.append(w)

    # ---- signature index (M6, descriptive), tier 2: one instant per month, the 12 months to T0 ----
    ym = SIGN_START
    while month_start(next_month(ym)) <= T365:
        ym = next_month(ym)
    while month_start(ym) < T0:
        a, b = month_start(ym), min(month_start(next_month(ym)), T0)
        rng = random.Random(seed_for('index', ym))
        t_i = a + (b - a) * rng.random()
        windows.append({'family': 'index', 'tier': 2, 'stratum': f'index:{ym}', 'month': ym, 'i': 0,
                        'instant': t_i, 'segments': [], 'covered_s': 0.0, 'nominal_s': 0.0, 'D_s': b - a,
                        'n_h': 1, 'weight': None})
        ym = next_month(ym)

    # ids, plan costs, order
    for w in windows:
        key = f"{w['stratum']}#{w['i']}"
        w['id'] = hashlib.sha256(key.encode()).hexdigest()[:12]
        w['key'] = key
        if w['family'] == 'index':
            w['cost_plan'], w['cost_stress'] = 1.0, 1.0
            continue
        guard = 2 * w.get('guard_s', 0.0) * len(w['segments'])
        lam = w['rate_plan_per_day'] / DAY * (w['covered_s'] + guard)
        pages_per_seg = len(w['segments']) or 0
        # each segment is paged separately; a segment costs at least one page
        if pages_per_seg <= 1:
            w['cost_plan'] = expected_pages(lam) if w['segments'] else 0.0
            w['cost_stress'] = expected_pages(lam, True) if w['segments'] else 0.0
        else:
            lam_seg = [w['rate_plan_per_day'] / DAY * ((e - s) + 2 * w.get('guard_s', 0.0)) for s, e in w['segments']]
            w['cost_plan'] = sum(expected_pages(l) for l in lam_seg)
            w['cost_stress'] = sum(expected_pages(l, True) for l in lam_seg)
    rng = random.Random(seed_for('order'))
    keyed = [(w['tier'], rng.random(), w['key']) for w in sorted(windows, key=lambda w: w['key'])]
    rank = {k: j for j, (_, _, k) in enumerate(sorted(keyed))}
    for w in windows:
        w['order'] = rank[w['key']]
    windows.sort(key=lambda w: w['order'])
    return windows


PARTS = [  # removal order for tier-2 parts (METHOD §6.10)
    ('index', lambda w: w['family'] == 'index'),
    ('sign_older_than_12m', lambda w: w['family'] == 'sign' and w['tier'] == 2),
    ('migration', lambda w: w['family'] == 'migration'),
]


def budget(windows):
    """Planning cost of a design: the windows plus the tier-1 transaction resolutions."""
    plan = sum(w['cost_plan'] for w in windows) + RESOLVE_CREDITS
    stress = sum(w['cost_stress'] for w in windows) + RESOLVE_CREDITS
    return plan, stress, int(math.ceil(stress * RETRY_ALLOWANCE))


def capacity_finish(ledger_entries, start, credits, cap24=300, cap60=5, gap=12.5):  # mirror nb.CAP_60S, nb.MIN_GAP
    """Simulate greedy one-credit calls from `start` under the ledger caps. Returns the time the
    last of `credits` calls would be issued."""
    entries = sorted(ledger_entries)
    t = start
    issued = 0
    hist = [(et, ec) for et, ec in entries]
    import bisect
    while issued < credits:
        # rolling 24h credits
        lo = t - DAY
        c24 = sum(c for et, c in hist if lo < et <= t)
        n60 = sum(1 for et, c in hist if t - 60 < et <= t)
        last = hist[-1][0] if hist else -1e18
        if c24 + 1 <= cap24 and n60 + 1 <= cap60 and t - last >= gap:
            hist.append((t, 1))
            issued += 1
            t += gap
            continue
        cands = []
        if t - last < gap:
            cands.append(last + gap)
        if c24 + 1 > cap24:
            need = c24 + 1 - cap24
            acc = 0
            for et, ec in hist:
                if lo < et <= t:
                    acc += ec
                    if acc >= need:
                        cands.append(et + DAY + 1e-3)
                        break
        if n60 + 1 > cap60:
            in60 = [et for et, c in hist if t - 60 < et <= t]
            cands.append(in60[0] + 60 + 1e-3)
        t = max(cands)
    return t - gap


def select(windows, ledger_entries, freeze_t):
    start = freeze_t + 3600.0
    deadline = ts(DEADLINE)
    removed = []
    cur = list(windows)
    log = []
    while True:
        plan, stress, need = budget(cur)
        fin = capacity_finish(ledger_entries, start, need)
        log.append({'removed': list(removed), 'plan': round(plan, 2), 'stress': round(stress, 2),
                    'credits_with_allowance': need, 'last_call_utc': iso(fin), 'fits': fin < deadline})
        if fin < deadline:
            return cur, removed, log
        if len(removed) == len(PARTS):
            return None, removed, log
        name, pred = PARTS[len(removed)]
        cur = [w for w in cur if not pred(w)]
        removed.append(name)


def summarize(windows):
    by = {}
    for w in windows:
        k = (w['family'], w['tier'])
        d = by.setdefault(k, {'windows': 0, 'plan': 0.0, 'stress': 0.0})
        d['windows'] += 1
        d['plan'] += w['cost_plan']
        d['stress'] += w['cost_stress']
    return {f'{f}/tier{t}': {'windows': v['windows'], 'plan': round(v['plan'], 2), 'stress': round(v['stress'], 2)}
            for (f, t), v in sorted(by.items())}


def to_json(windows, meta):
    out = []
    for w in windows:
        o = {k: w[k] for k in ('id', 'key', 'family', 'tier', 'order', 'stratum', 'i', 'n_h', 'D_s',
                               'nominal_s', 'covered_s', 'weight', 'cost_plan', 'cost_stress') if k in w}
        for k in ('token', 'period', 'month', 'rate_plan_per_day', 'guard_s', 'whole'):
            if k in w:
                o[k] = w[k]
        o['segments_ns'] = [[ns(s), ns(e)] for s, e in w['segments']]
        o['segments_utc'] = [[iso(s), iso(e)] for s, e in w['segments']]
        if w['family'] == 'index':
            o['instant_ns'] = ns(w['instant'])
            o['instant_utc'] = iso(w['instant'])
        out.append(o)
    return json.dumps({'meta': meta, 'windows': out}, indent=1, sort_keys=True)


def load_ledger(path):
    es = []
    for line in open(path):
        line = line.strip()
        if line:
            e = json.loads(line)
            es.append((float(e['t']), int(e['credits'])))
    return es


def main():
    cmd = sys.argv[1]
    rates = json.load(open(sys.argv[2]))
    if cmd == 'plan':
        T0 = ts(sys.argv[3])
        ws = build(rates, T0)
        print(json.dumps(summarize(ws), indent=1))
        print('total plan/stress/with-allowance', budget(ws))
        meta = {'T0_utc': sys.argv[3], 'seed': SEED, 'note': 'planning draft, not frozen'}
        open(sys.argv[4], 'w').write(to_json(ws, meta))
    elif cmd == 'select':
        freeze_t = ts(sys.argv[3])
        T0 = math.floor(freeze_t / 3600) * 3600
        ws = build(rates, T0)
        led = load_ledger(sys.argv[4])
        sel, removed, log = select(ws, led, freeze_t)
        print(json.dumps(log, indent=1))
        if sel is None:
            print('TIER 1 DOES NOT FIT: nothing starts; Bhargav decides (METHOD §6.10)')
            sys.exit(2)
        meta = {'T0_utc': iso(T0), 'freeze_utc': sys.argv[3], 'seed': SEED, 'removed_parts': removed,
                'selection_log': {'rulings': RULINGS, 'fit_tests': log}, 'guard_s': GUARD_S, 'target_rows': TARGET_ROWS,
                'retry_allowance': RETRY_ALLOWANCE, 'deadline_utc': DEADLINE, 'summary': summarize(sel),
                'rates_file_sha256': hashlib.sha256(open(sys.argv[2], 'rb').read()).hexdigest()}
        open(sys.argv[5], 'w').write(to_json(sel, meta))
        print(json.dumps(summarize(sel), indent=1))


if __name__ == '__main__':
    main()
