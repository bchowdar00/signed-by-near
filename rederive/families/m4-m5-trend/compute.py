"""Core computation: per-window per-predecessor HT contributions, class aggregation."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import load
from collections import defaultdict

MONTHS = []  # 2024-08 .. 2026-11


def month_list():
    out = []
    for y in (2024, 2025, 2026):
        for m in range(1, 13):
            if y == 2024 and m < 8:
                continue
            if y == 2026 and m > 11:
                continue
            out.append(f'{y}-{m:02d}')
    return out


def build():
    """Returns a dict with per-window data and per-month aggregates."""
    sign = load.load_sign_windows()
    comp, detail = load.completion_map(sign)
    # per window: weight, month, predecessor->count, predecessor->status counts
    windows = []
    for w in sign:
        month = load.month_of_stratum(w['stratum'])
        rec = {'id': w['id'], 'stratum': w['stratum'], 'month': month,
               'weight': w['weight'], 'completed': comp[w['id']],
               'pred_count': defaultdict(int), 'fail_count': 0, 'total': 0}
        if comp[w['id']]:
            calls = load.read_window_calls(w)
            for pred, status in calls:
                rec['pred_count'][pred] += 1
                rec['total'] += 1
                if status is not True:
                    rec['fail_count'] += 1
        windows.append(rec)
    return sign, comp, detail, windows


def month_completed(windows):
    mc = {}
    for w in windows:
        mc.setdefault(w['month'], True)
        if not w['completed']:
            mc[w['month']] = False
    return mc


def ht_by_pred(windows, month):
    """HT total per predecessor for a month (sum w*count over completed windows)."""
    tot = defaultdict(float)
    for w in windows:
        if w['month'] != month or not w['completed']:
            continue
        for pred, c in w['pred_count'].items():
            tot[pred] += w['weight'] * c
    return tot


def ht_fail(windows, month):
    f = 0.0
    for w in windows:
        if w['month'] == month and w['completed']:
            f += w['weight'] * w['fail_count']
    return f


def class_totals(pred_ht):
    """Aggregate predecessor HT into classes 1,2(FastAuth),3,4,4x,5."""
    ct = defaultdict(float)
    rules = {}
    for pred, ht in pred_ht.items():
        cls, rule = load.classify(pred)
        ct[cls] += ht
        rules[pred] = (cls, rule)
    return ct, rules


def fastauth_signer_shares(nd_sample, month):
    """From nd sign sample: among fast-auth.near calls, share by signer -> 2a (sweat) vs 2c.
    Returns (n_fastauth, sweat_count, share_2a, share_2c)."""
    calls = nd_sample.get(month, [])
    fa = [c for c in calls if c['predecessor'] == 'fast-auth.near']
    n = len(fa)
    sweat = sum(1 for c in fa if c['signer'] == 'sweat-relayer.near')
    if n == 0:
        return (0, 0, None, None)
    return (n, sweat, sweat / n, (n - sweat) / n)
