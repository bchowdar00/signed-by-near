"""Core estimators: HT totals, route/value shares, stratified bootstrap (seeds 1 & 2),
window-level bound (METHOD 4.0), hulls. Builds the per-window transfer cache once.
"""
import sys, json, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import build
import statlib

REPO = build.REPO
PRICES = json.load(open(os.path.join(REPO, 'inputs/reference.json')))['prices_usd']
TOKMETA = build.load_tokens()
NBTC, NZEC, BTCOMFT = 'nbtc.bridge.near', 'nzec.bridge.near', 'btc.omft.near'


def usd(t):
    m = TOKMETA[t['token']]
    return t['amount'] / (10 ** m['decimals']) * PRICES[m['unit_group']]


def native(t):
    m = TOKMETA[t['token']]
    return t['amount'] / (10 ** m['decimals'])


def olo(t):  # unknown counted as NOT omni
    return 1.0 if t['route'] == 'omni' else 0.0


def ohi(t):  # unknown counted as omni
    return 1.0 if t['route'] in ('omni', 'unknown', 'mixed') else 0.0


def is_out(t):
    return t['direction'] == 'out'


def load_flow_windows():
    inst = build.load_instants()
    comp = build.completed_ids()
    out = []
    for w in inst['windows']:
        if w['family'] != 'flow':
            continue
        ok, why = build.check_completion(w, comp)
        trs = build.build_transfers_for_window(w, w['token'])
        # NEAR-side transfers are not cross-chain and are excluded from every share (METHOD 3).
        xfers = [t for t in trs if t['route'] != 'near-side']
        nearside = [t for t in trs if t['route'] == 'near-side']
        out.append({'id': w['id'], 'stratum': w['stratum'], 'token': w['token'],
                    'weight': w['weight'], 'period': w['period'], 'whole': bool(w.get('whole')),
                    'completed': ok, 'why': why, 'transfers': xfers,
                    'nearside': nearside, 'all_transfers': trs})
    return out


def bound_type(token, whole):
    if whole:
        return 'whole'
    if token in (NBTC, NZEC):
        return 'single'
    return 'cp'


class ShareSpec:
    """Defines num/den selectors and value fn for a share."""
    def __init__(self, valfn, num_sel=lambda t: True, o=olo):
        self.valfn, self.num_sel, self.o = valfn, num_sel, o


def window_contribs(win, spec_val, num_sel, ofn):
    """Return (den, num) un-weighted amount sums for a window under a value fn + selectors."""
    den = 0.0
    num = 0.0
    for t in win['transfers']:
        v = spec_val(t)
        den += v
        if num_sel(t):
            num += v * ofn(t)
    return den, num


def point_share(wins, spec_val, num_sel, ofn):
    num = sum(w['weight'] * window_contribs(w, spec_val, num_sel, ofn)[1] for w in wins)
    den = sum(w['weight'] * window_contribs(w, spec_val, num_sel, ofn)[0] for w in wins)
    return (num / den if den > 0 else None), num, den


def strata_of(wins):
    d = {}
    for w in wins:
        d.setdefault(w['stratum'], []).append(w)
    return d


def bootstrap_share(wins, spec_val, num_sel, ofn, seed, ndraw=2000):
    """Stratified percentile bootstrap. Returns (lo, hi, dropped, total)."""
    strata = strata_of(wins)
    # precompute per window weighted num/den
    pw = {}
    for w in wins:
        den, num = window_contribs(w, spec_val, num_sel, ofn)
        pw[w['id']] = (w['weight'] * num, w['weight'] * den)
    rng = np.random.default_rng(seed)
    sdata = []
    for st, ws in strata.items():
        nums = np.array([pw[w['id']][0] for w in ws])
        dens = np.array([pw[w['id']][1] for w in ws])
        sdata.append((nums, dens, len(ws)))
    vals = np.empty(ndraw)
    dropped = 0
    k = 0
    for _ in range(ndraw):
        tn = 0.0
        td = 0.0
        for nums, dens, n in sdata:
            idx = rng.integers(0, n, n)
            tn += nums[idx].sum()
            td += dens[idx].sum()
        if td <= 0:
            dropped += 1
            continue
        vals[k] = tn / td
        k += 1
    vals = vals[:k]
    if k == 0:
        return None, None, dropped, ndraw
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)), dropped, ndraw


def window_level_bound(wins, spec_val, num_sel, ofn):
    """Per-stratum CP/single/whole bound, combined C_L=Σ T_h c_L,h / Σ T_h. Returns (C_L,C_U,details)."""
    strata = strata_of(wins)
    numT = {'L': 0.0, 'U': 0.0}
    denT = 0.0
    details = []
    for st, ws in strata.items():
        tok = ws[0]['token']
        whole = ws[0]['whole']
        bt = bound_type(tok, whole)
        # per-window raw denominator amounts A_i, and omni amount
        A = []
        s_num = 0.0
        s_den = 0.0
        for w in ws:
            den, num = window_contribs(w, spec_val, num_sel, ofn)
            A.append(den)
            s_num += num
            s_den += den
        Th = sum(w['weight'] * window_contribs(w, spec_val, num_sel, ofn)[0] for w in ws)
        if s_den <= 0:
            details.append((st, bt, 0, None, None, Th, 0.0))
            continue
        s_h = s_num / s_den
        if bt in ('whole', 'single'):
            cL = cU = s_h
            m = None
        else:  # cp
            A = np.array(A)
            m = (A.sum() ** 2) / (A ** 2).sum() if (A ** 2).sum() > 0 else 0.0
            cL, cU = statlib.clopper_pearson(s_h * m, m)
        numT['L'] += Th * cL
        numT['U'] += Th * cU
        denT += Th
        details.append((st, bt, m, cL, cU, Th, s_h))
    if denT <= 0:
        return None, None, details
    return numT['L'] / denT, numT['U'] / denT, details


def hull(bootstrap_lo, bootstrap_hi, wl_lo, wl_hi, extra=None):
    """Hull of components; returns (L, U, srcL, srcU)."""
    comps = []
    if bootstrap_lo is not None:
        comps.append(('bootstrap', bootstrap_lo, bootstrap_hi))
    if wl_lo is not None:
        comps.append(('window-bound', wl_lo, wl_hi))
    if extra:
        comps.append(extra)
    L = min(c[1] for c in comps)
    U = max(c[2] for c in comps)
    srcL = min(comps, key=lambda c: c[1])[0]
    srcU = max(comps, key=lambda c: c[2])[0]
    return L, U, srcL, srcU
