"""Share estimators, bootstrap and window-level bound (METHOD 4.0). python3 -I."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import lib
import stats
import transfers as T

UNKNOWN_ROUTES = {'unknown', 'mixed'}


def omni_indicator(route, unknown_as):
    if route == 'omni':
        return 1.0
    if route in UNKNOWN_ROUTES:
        return 1.0 if unknown_as == 'omni' else 0.0
    return 0.0  # poa or anything non-omni, non-unknown


def transfer_amount(t, decimals, mode):
    if mode == 'count':
        return 1.0
    return t['amount_raw'] / (10.0 ** decimals)


def direction_ok(t, direction):
    return direction == 'both' or t['direction'] == direction


def build_strata(group, period_set):
    """group: list of (token, decimals). period_set: list of periods.
    Returns list of strata; each stratum = dict(key, token, whole, windows=[list of (weight,[transfers])]).
    Only cross-chain transfers kept (route != near-side)."""
    strata = []
    for token, decimals in group:
        for period in period_set:
            wins = T.flow_windows(token, period)
            if not wins:
                continue
            wlist = []
            whole = all(w.get('whole') for w in wins)
            for w in wins:
                tr = [t for t in lib.window_transfers(w) if t['route'] != 'near-side']
                wlist.append((w['weight'], tr, decimals))
            strata.append({'key': (token, period), 'token': token, 'whole': whole,
                           'single_route': not token.endswith('.omft.near'),
                           'windows': wlist})
    return strata


def point_share(strata, mode, direction, unknown_as):
    num = den = 0.0
    for st in strata:
        for weight, tr, dec in st['windows']:
            for t in tr:
                if not direction_ok(t, direction):
                    continue
                a = transfer_amount(t, dec, mode)
                num += weight * a * omni_indicator(t['route'], unknown_as)
                den += weight * a
    return (num / den) if den > 0 else None, den


def distinct_and_windows(strata, mode, direction):
    """distinct (tx,token) in denominator; windows with >=1 denominator transfer."""
    distinct = set()
    nwin = 0
    for st in strata:
        for weight, tr, dec in st['windows']:
            has = False
            for t in tr:
                if direction_ok(t, direction):
                    distinct.add((t['tx'], t['token']))
                    has = True
            if has:
                nwin += 1
    return len(distinct), nwin


def bootstrap(strata, mode, direction, unknown_as, seed, ndraw=2000):
    rng = np.random.default_rng(seed)
    # precompute per-window (num_contrib, den_contrib) arrays per stratum
    stratum_wins = []
    for st in strata:
        wins = []
        for weight, tr, dec in st['windows']:
            n = d = 0.0
            for t in tr:
                if not direction_ok(t, direction):
                    continue
                a = transfer_amount(t, dec, mode)
                n += weight * a * omni_indicator(t['route'], unknown_as)
                d += weight * a
            wins.append((n, d))
        stratum_wins.append((st['whole'], np.array([w[0] for w in wins]),
                             np.array([w[1] for w in wins])))
    shares = []
    dropped = 0
    for _ in range(ndraw):
        tn = td = 0.0
        for whole, narr, darr in stratum_wins:
            k = len(narr)
            if k == 0:
                continue
            if whole:
                tn += narr.sum()
                td += darr.sum()
            else:
                idx = rng.integers(0, k, k)
                tn += narr[idx].sum()
                td += darr[idx].sum()
        if td <= 0:
            dropped += 1
            continue
        shares.append(tn / td)
    if not shares:
        return None, None, dropped, ndraw
    lo = float(np.percentile(shares, 2.5))
    hi = float(np.percentile(shares, 97.5))
    return lo, hi, dropped, ndraw


def window_bound(strata, mode, direction, unknown_as):
    """Group CP window-level bound. Returns C_L, C_U, and per-stratum detail."""
    num_L = num_U = Tsum = 0.0
    detail = []
    for st in strata:
        # stratum denominator totals and amounts
        A = []       # per-window denominator (unweighted amount sum)
        sh_num = sh_den = 0.0  # weighted for s_h and T_h
        for weight, tr, dec in st['windows']:
            a_i = 0.0
            for t in tr:
                if not direction_ok(t, direction):
                    continue
                a = transfer_amount(t, dec, mode)
                a_i += a
                sh_num += weight * a * omni_indicator(t['route'], unknown_as)
                sh_den += weight * a
            A.append(a_i)
        A = np.array(A)
        Th = sh_den
        if Th <= 0:
            detail.append({'stratum': st['key'], 'Th': 0.0, 'degenerate': True, 'reason': 'empty',
                           's_h': None, 'm_h': 0.0, 'cL': 0.0, 'cU': 1.0})
            continue
        s_h = sh_num / sh_den
        degenerate = st['whole'] or st['single_route']
        reason = 'read whole (exact)' if st['whole'] else ('single-route token (Omni-or-unknown)' if st['single_route'] else '')
        if degenerate:
            cL = cU = s_h
            m_h = float(len(A))
        else:
            ssum = A.sum()
            ss2 = (A ** 2).sum()
            m_h = (ssum ** 2 / ss2) if ss2 > 0 else 0.0
            k = s_h * m_h
            cL, cU = stats.clopper_pearson(k, m_h)
        num_L += Th * cL
        num_U += Th * cU
        Tsum += Th
        detail.append({'stratum': st['key'], 'Th': Th, 'degenerate': degenerate, 'reason': reason,
                       's_h': s_h, 'm_h': m_h, 'cL': cL, 'cU': cU, 'n_windows': int(len(A))})
    if Tsum <= 0:
        return None, None, detail
    return num_L / Tsum, num_U / Tsum, detail


def read_interval(strata, mode, direction, seeds=(1, 2)):
    """Full reading. Returns dict with point shares, bootstrap (both seeds), window bound,
    read interval [L,U] with sources, sparse info."""
    pt_not, den_not = point_share(strata, mode, direction, 'not')
    pt_omni, den_omni = point_share(strata, mode, direction, 'omni')
    distinct, nwin = distinct_and_windows(strata, mode, direction)
    # sparse
    if distinct == 0:
        sparse = 'none observed (0 of 0)'
    elif distinct < 10 or nwin < 3:
        sparse = f'too sparse ({distinct} of {nwin})'
    else:
        sparse = 'ok'
    # bootstrap: L side uses unknown=not, U side unknown=omni
    boot = {}
    unstable = False
    for s in seeds:
        loN, hiN, dropN, nd = bootstrap(strata, mode, direction, 'not', s)
        loO, hiO, dropO, _ = bootstrap(strata, mode, direction, 'omni', s)
        bl = loN
        bu = hiO
        if dropN / nd > 0.05 or dropO / nd > 0.05:
            unstable = True
        boot[s] = {'lo_not': loN, 'hi_not': hiN, 'lo_omni': loO, 'hi_omni': hiO,
                   'dropped_not': dropN, 'dropped_omni': dropO, 'ndraw': nd,
                   'boot_L': bl, 'boot_U': bu}
    # window bound
    cL_not, cU_not, det_not = window_bound(strata, mode, direction, 'not')
    cL_omni, cU_omni, det_omni = window_bound(strata, mode, direction, 'omni')
    # read interval: hull of bootstrap and window bound
    # L from 'not' assignment; U from 'omni' assignment
    cand_L = [('bootstrap', boot[seeds[0]]['boot_L'])] if boot[seeds[0]]['boot_L'] is not None else []
    if cL_not is not None:
        cand_L.append(('window-bound', cL_not))
    cand_U = [('bootstrap', boot[seeds[0]]['boot_U'])] if boot[seeds[0]]['boot_U'] is not None else []
    if cU_omni is not None:
        cand_U.append(('window-bound', cU_omni))
    L_src, L = min(cand_L, key=lambda x: x[1]) if cand_L else (None, None)
    U_src, U = max(cand_U, key=lambda x: x[1]) if cand_U else (None, None)
    return {
        'point_unknown_not': pt_not, 'point_unknown_omni': pt_omni,
        'den_not': den_not, 'distinct': distinct, 'windows_with_transfer': nwin, 'sparse': sparse,
        'bootstrap': boot, 'unstable': unstable,
        'window_bound_not': {'C_L': cL_not, 'C_U': cU_not, 'detail': det_not},
        'window_bound_omni': {'C_L': cL_omni, 'C_U': cU_omni, 'detail': det_omni},
        'L': L, 'L_source': L_src, 'U': U, 'U_source': U_src,
    }


def state_of(reading, tau):
    """METHOD 7 state precedence for a share with interval [L,U]."""
    L, U = reading['L'], reading['U']
    if reading['sparse'].startswith('none observed') or reading['sparse'].startswith('too sparse'):
        return 'not measurable'
    if reading['unstable']:
        return 'inconclusive (unstable)'
    if L is None or U is None:
        return 'not measurable'
    if L < 0.50 and U >= tau:
        return 'inconclusive'
    if L >= tau:
        return 'consistent'
    if U < 0.50:
        return 'contradicted'
    return 'partly'
