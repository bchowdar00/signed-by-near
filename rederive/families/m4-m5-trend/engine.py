"""Bootstrap engine and per-month precompute. numpy only."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import compute, load
from collections import defaultdict

CLASSES = ['1', '2', '3', '4', '4x', '5']  # index order; '2' = FastAuth total
CIDX = {c: i for i, c in enumerate(CLASSES)}


def precompute():
    sign, comp, detail, windows = compute.build()
    nd = load.load_nd_sign_sample()
    mc = compute.month_completed(windows)
    months = compute.month_list()

    # per month -> per stratum -> array (n_win, 6) of weight*count by class
    month_strata = {}
    for m in months:
        strata = defaultdict(list)
        for w in windows:
            if w['month'] != m or not w['completed']:
                continue
            strata[w['stratum']].append(w)
        arrs = {}
        for st, ws in strata.items():
            A = np.zeros((len(ws), len(CLASSES)))
            for i, w in enumerate(ws):
                for pred, cnt in w['pred_count'].items():
                    cls, _ = load.classify(pred)
                    A[i, CIDX[cls]] += w['weight'] * cnt
            arrs[st] = A
        month_strata[m] = arrs

    # per month -> nd block arrays: fa_count, sweat_count per block (for attribution)
    # and M6 per-block: secp0, jwt1, other1 counts
    month_nd = {}
    for m, calls_by_block in _blocks_by_month(nd).items():
        fa = []
        m6 = []
        for blk in calls_by_block:
            fac = sum(1 for c in blk if c['predecessor'] == 'fast-auth.near')
            swc = sum(1 for c in blk if c['predecessor'] == 'fast-auth.near'
                      and c['signer'] == 'sweat-relayer.near')
            fa.append([fac, swc])
            s0 = j1 = o1 = 0
            for c in blk:
                if c['domain'] == 0:
                    s0 += 1
                elif c['domain'] == 1:
                    p = c['path']
                    if isinstance(p, str) and p.startswith('jwt#'):
                        j1 += 1
                    else:
                        o1 += 1
            m6.append([s0, j1, o1])
        month_nd[m] = {'fa': np.array(fa) if fa else np.zeros((0, 2)),
                       'm6': np.array(m6) if m6 else np.zeros((0, 3))}
    return {'sign': sign, 'comp': comp, 'windows': windows, 'nd': nd, 'mc': mc,
            'months': months, 'month_strata': month_strata, 'month_nd': month_nd}


def _blocks_by_month(nd):
    """Reconstruct per-month list of blocks (each a list of its sign calls)
    from the flat nd sample, grouped by height."""
    out = {}
    for m, calls in nd.items():
        byh = defaultdict(list)
        for c in calls:
            byh[c['height']].append(c)
        out[m] = list(byh.values())
    return out


def nd_blocks_full(month):
    """All sampled blocks for a month incl. zero-call blocks, as fa/m6 arrays.
    We need every sampled block (150) so resampling reflects FA sparsity."""
    # rebuilt directly from blocks.jsonl to include zero-call blocks
    import json
    fa = []
    m6 = []
    for line in open(os.path.join(load.DATA, 'nd/blocks.jsonl')):
        r = json.loads(line)
        if r.get('part') != f'sample:{month}':
            continue
        signs = [c for c in r.get('calls', []) if c.get('method') == 'sign']
        fac = sum(1 for c in signs if c.get('predecessor') == 'fast-auth.near')
        swc = sum(1 for c in signs if c.get('predecessor') == 'fast-auth.near'
                  and c.get('signer') == 'sweat-relayer.near')
        fa.append([fac, swc])
        s0 = j1 = o1 = 0
        for c in signs:
            req = c['args'].get('request', c['args'])
            dom = req.get('domain_id', 0) if 'domain_id' in req else 0
            path = req.get('path')
            if dom == 0:
                s0 += 1
            elif dom == 1:
                if isinstance(path, str) and path.startswith('jwt#'):
                    j1 += 1
                else:
                    o1 += 1
        m6.append([s0, j1, o1])
    return np.array(fa, dtype=float), np.array(m6, dtype=float)


def draw_month_classvecs(arrs, rng, ndraw):
    """Return (ndraw, 6) class-HT totals from resampling windows within each stratum."""
    total = np.zeros((ndraw, len(CLASSES)))
    for st, A in arrs.items():
        n = A.shape[0]
        idx = rng.integers(0, n, size=(ndraw, n))
        total += A[idx].sum(axis=1)
    return total


def draw_fa_share(fa_arr, rng, ndraw):
    """Resample nd blocks; return sweat share among FA calls per draw, and mask of valid (fa>0)."""
    n = fa_arr.shape[0]
    if n == 0:
        return np.zeros(ndraw), np.zeros(ndraw, dtype=bool)
    idx = rng.integers(0, n, size=(ndraw, n))
    sums = fa_arr[idx].sum(axis=1)  # (ndraw,2) [fa,sweat]
    fac = sums[:, 0]
    swc = sums[:, 1]
    valid = fac > 0
    s = np.zeros(ndraw)
    s[valid] = swc[valid] / fac[valid]
    return s, valid
