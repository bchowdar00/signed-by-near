import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import numpy as np
import lib
import stats
import shares as S
import transfers as T

# M10 series: token group (in native unit), and flow-token set for late period
SERIES = {
    'SOL': {'tokens': [('sol.omft.near', 9)]},
    'ZEC': {'tokens': [('zec.omft.near', 8)]},
    'BTC': {'tokens': [('btc.omft.near', 8), ('nbtc.bridge.near', 8)]},
    'ETH': {'tokens': [('eth.omft.near', 18)]},
}
CHART_MONTHS = ['2025-07', '2025-09', '2025-11', '2026-01', '2026-03', '2026-05', '2026-07']


def mig_strata(tokens, suffix):
    """Build share-strata from migration windows (one stratum per token)."""
    strata = []
    all_ok = True
    for token, dec in tokens:
        wins = T.migration_windows(token, suffix)
        if not wins:
            continue
        wlist = []
        whole = False
        for w in wins:
            ok, _ = lib.is_completed(w, T.EV)
            if not ok:
                all_ok = False
                continue
            tr = [t for t in lib.window_transfers(w) if t['route'] != 'near-side']
            wlist.append((w['weight'], tr, dec))
        strata.append({'key': (token, suffix), 'token': token, 'whole': whole,
                       'single_route': not token.endswith('.omft.near'), 'windows': wlist})
    return strata, all_ok


def flow_strata(tokens, period_set):
    return S.build_strata(tokens, period_set)


def period_reading(strata, all_ok, mode, direction='both'):
    if not all_ok:
        return {'completed': False}
    r = S.read_interval(strata, mode, direction)
    r['completed'] = True
    return r


def diff_bootstrap(strata_late, strata_early, mode, seed, ndraw=2000):
    """Difference late-early, draws independent across periods. unknown as not for L?
    We compute the diff point and its bootstrap distribution (unknown counted 'not' here for
    a central estimate); the read difference interval is hulled with [L_late-U_early, U_late-L_early]."""
    def pre(strata, unk):
        sw = []
        for st in strata:
            wins = []
            for weight, tr, dec in st['windows']:
                n = d = 0.0
                for t in tr:
                    a = 1.0 if mode == 'count' else t['amount_raw'] / 10.0 ** dec
                    n += weight * a * S.omni_indicator(t['route'], unk)
                    d += weight * a
                wins.append((n, d))
            sw.append((st['whole'], np.array([w[0] for w in wins]), np.array([w[1] for w in wins])))
        return sw
    rng = np.random.default_rng(seed)
    late = pre(strata_late, 'not')
    early = pre(strata_early, 'not')

    def draw(sw):
        tn = td = 0.0
        for whole, narr, darr in sw:
            k = len(narr)
            if k == 0:
                continue
            if whole:
                tn += narr.sum(); td += darr.sum()
            else:
                idx = rng.integers(0, k, k)
                tn += narr[idx].sum(); td += darr[idx].sum()
        return (tn / td) if td > 0 else None
    diffs = []
    dropped = 0
    for _ in range(ndraw):
        a = draw(late); b = draw(early)
        if a is None or b is None:
            dropped += 1
            continue
        diffs.append(a - b)
    if not diffs:
        return None, None, dropped
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5)), dropped


out = {}
for sname, s in SERIES.items():
    so = {}
    toks = s['tokens']
    # Early stratum (migration 'early')
    est, eok = mig_strata(toks, 'early')
    early_amt = period_reading(est, eok, 'amount')
    early_cnt = period_reading(est, eok, 'count')
    so['early'] = {'completed': eok, 'amount': early_amt, 'count': early_cnt}
    # Late period (flow windows, 90d = claim+outside)
    lst = flow_strata(toks, ['claim', 'outside'])
    # late completion: all flow windows complete
    lok = all(lib.is_completed(w, T.EV)[0] for tk, _ in toks for w in T.flow_windows(tk))
    late_amt = period_reading(lst, lok, 'amount')
    late_cnt = period_reading(lst, lok, 'count')
    so['late'] = {'completed': lok, 'amount': late_amt, 'count': late_cnt}
    # Difference (amount, verdict metric)
    if eok and lok:
        # L_late - U_early and U_late - L_early from read intervals
        comp_lo = late_amt['L'] - early_amt['U']
        comp_hi = late_amt['U'] - early_amt['L']
        db1 = diff_bootstrap(lst, est, 'amount', 1)
        db2 = diff_bootstrap(lst, est, 'amount', 2)
        dL = min(comp_lo, db1[0]) if db1[0] is not None else comp_lo
        dU = max(comp_hi, db1[1]) if db1[1] is not None else comp_hi
        unstable = (db1[2] / 2000 > 0.05) or (db2[2] / 2000 > 0.05)
        if unstable:
            state = 'no clear move (unstable)'
        elif dL > 0:
            state = 'moving to Omni'
        elif dU < 0:
            state = 'moving away from Omni'
        else:
            state = 'no clear move'
        so['difference'] = {'completed': True, 'comp_interval': [comp_lo, comp_hi],
                            'boot_s1': db1[:2], 'boot_s2': db2[:2], 'dropped_s1': db1[2], 'dropped_s2': db2[2],
                            'diff_L': dL, 'diff_U': dU, 'state': state,
                            'late_point_not': late_amt['point_unknown_not'],
                            'early_point_not': early_amt['point_unknown_not']}
    else:
        so['difference'] = {'completed': False,
                            'state': 'not completed',
                            'reason': f'early_completed={eok} late_completed={lok}'}
    # Chart months (descriptive)
    charts = {}
    for cm in CHART_MONTHS:
        cst, cok = mig_strata(toks, 'chart:' + cm)
        if not cok:
            charts[cm] = {'completed': False}
            continue
        amt = S.read_interval(cst, 'amount', 'both')
        cnt = S.read_interval(cst, 'count', 'both')
        charts[cm] = {'completed': True,
                      'amount_L': amt['L'], 'amount_U': amt['U'],
                      'count_L': cnt['L'], 'count_U': cnt['U'],
                      'distinct': amt['distinct']}
    so['charts'] = charts
    out[sname] = so

json.dump(out, open('d4_m10.json', 'w'), indent=1)

def fmt(x):
    return 'None' if x is None else f'{x*100:.3f}%'

for sname in ['SOL', 'ZEC', 'BTC', 'ETH']:
    so = out[sname]
    print('=====', sname, '=====')
    e = so['early']; l = so['late']
    if e['completed']:
        print(f"  early amount L={fmt(e['amount']['L'])} U={fmt(e['amount']['U'])} count L={fmt(e['count']['L'])} U={fmt(e['count']['U'])} distinct={e['amount']['distinct']}")
    else:
        print('  early: NOT COMPLETED')
    print(f"  late  amount L={fmt(l['amount']['L'])} U={fmt(l['amount']['U'])} count L={fmt(l['count']['L'])} U={fmt(l['count']['U'])} distinct={l['amount']['distinct']}")
    d = so['difference']
    if d['completed']:
        print(f"  DIFF late-early: comp={[round(x,4) for x in d['comp_interval']]} boot_s1={[round(x,4) if x else None for x in d['boot_s1']]} -> [{d['diff_L']:.4f},{d['diff_U']:.4f}] STATE={d['state']}")
    else:
        print(f"  DIFF: {d['state']} ({d.get('reason')})")
    inc = [cm for cm, c in so['charts'].items() if not c['completed']]
    print('  charts incomplete:', inc)
    for cm, c in so['charts'].items():
        if c['completed']:
            print(f"    {cm}: amount[{fmt(c['amount_L'])},{fmt(c['amount_U'])}] count[{fmt(c['count_L'])},{fmt(c['count_U'])}] distinct={c['distinct']}")
