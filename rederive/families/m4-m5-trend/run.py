import sys, json, time, calendar, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import engine, compute, load, statlib
from collections import Counter

T0 = time.time()
P = engine.precompute()
windows = P['windows']; nd = P['nd']; mc = P['mc']; months = P['months']
NDRAW = 2000
SEEDS = [1, 2]
RESULTS = {}
TELEM = {'rows_read': 0, 'windows_completed': 0}


def days(m):
    y, mo = map(int, m.split('-'))
    return calendar.monthrange(y, mo)[1]


def pct(a, q):
    return float(np.percentile(a, q))


def kish_m(fa_arr):
    A = fa_arr[:, 0]
    s = A.sum()
    return 0.0 if s == 0 else float(s * s / (A * A).sum())


# telemetry
for w in windows:
    if w['completed']:
        TELEM['windows_completed'] += 1
        TELEM['rows_read'] += w['total']

# ============================ M4 ============================
m4 = {}
for m in months:
    ht = compute.ht_by_pred(windows, m)
    ct, rules = compute.class_totals(ht)
    allht = sum(ct.values())
    n_fa, sweat, s2a_raw, s2c_raw = compute.fastauth_signer_shares(nd, m)
    fa = ct.get('2', 0.0)
    has_sample = m in nd
    rec = {'completed': mc[m], 'all_HT': allht, 'has_nd_sample': has_sample,
           'n_fastauth_nd': n_fa, 'sweat_nd': sweat, 'fastauth_HT': fa}
    if allht == 0:
        rec['note'] = 'no calls observed'; m4[m] = rec; continue

    def sh(c): return ct.get(c, 0.0) / allht
    # attribution
    if has_sample:
        s2a = (sweat / n_fa) if n_fa > 0 else 0.0
        s2c = 1.0 - s2a
        attr = 'attributed' if fa > 0 else 'attributed (FastAuth HT=0, immaterial)'
    else:
        s2a = 0.0; s2c = 0.0
        attr = 'no nd sample (FastAuth HT=0, so range degenerate)'
    rec['attribution'] = attr
    c2a = fa * s2a; c2b = 0.0; c2c = fa * s2c
    rec['shares'] = {'1': sh('1'), '2_total': sh('2'),
                     '2a': c2a / allht, '2b': 0.0, '2c': c2c / allht,
                     '3': sh('3'), '4': sh('4'), '4x': sh('4x'), '5': sh('5')}
    narrow = sh('4')
    broad = (allht - ct.get('1', 0) - ct.get('3', 0)) / allht
    main = (ct.get('4', 0) + ct.get('4x', 0) + c2a) / allht
    mns = (ct.get('4', 0) + ct.get('4x', 0)) / allht
    rec['classifications'] = {'main': main, 'main_no_sweat': mns, 'narrow': narrow, 'broad': broad}
    if not has_sample:
        rec['main_range_no_sample'] = [mns, (ct.get('4', 0) + ct.get('4x', 0) + fa) / allht]
    # class-3 -> class-5 sensitivity
    ct3 = dict(ct); ct3['5'] = ct3.get('5', 0) + ct3.get('3', 0); ct3['3'] = 0.0
    rec['shares_class3_to_5'] = {c: ct3.get(c, 0.0) / allht for c in ['1', '2', '3', '4', '4x', '5']}
    rec['broad_class3_to_5'] = (allht - ct3.get('1', 0) - ct3.get('3', 0)) / allht

    # intervals only for completed months
    if mc[m]:
        base = (ct.get('4', 0) + ct.get('4x', 0)) / allht
        faterm = fa / allht
        fa_arr = engine.nd_blocks_full(m)[0] if has_sample else np.zeros((0, 2))
        mval = kish_m(fa_arr) if fa > 0 else 0.0
        if fa > 0 and mval > 0:
            sL, sU = statlib.clopper_pearson(s2a * mval, mval)  # sweat successes
            b2bL, b2bU = statlib.clopper_pearson(0.0, mval)
            bound_main = [base + faterm * sL, base + faterm * sU]
            bound_mns = [base + faterm * b2bL, base + faterm * b2bU]
            rec['kish_m'] = mval; rec['sweat_CP'] = [sL, sU]; rec['b2b_CP'] = [b2bL, b2bU]
        else:
            bound_main = [main, main]; bound_mns = [mns, mns]
        arrs = P['month_strata'][m]
        boot = {'main': {}, 'main_no_sweat': {}}; hull = {'main': {}, 'main_no_sweat': {}}
        for seed in SEEDS:
            rng = np.random.default_rng(seed)
            cls = engine.draw_month_classvecs(arrs, rng, NDRAW)
            alld = cls.sum(axis=1); fad = cls[:, 1]; c4d = cls[:, 3]; c4xd = cls[:, 4]
            if fa > 0:
                s_draw, valid_nd = engine.draw_fa_share(fa_arr, rng, NDRAW)
            else:
                s_draw = np.zeros(NDRAW); valid_nd = np.ones(NDRAW, bool)
            with np.errstate(divide='ignore', invalid='ignore'):
                maind = (c4d + c4xd) / alld + (fad / alld) * s_draw
                mnsd = (c4d + c4xd) / alld
            valid = (alld > 0) & ~((fad > 0) & (~valid_nd))
            dropped = int(NDRAW - valid.sum())
            mm = maind[valid]; mn = mnsd[valid]
            unst = dropped > 0.05 * NDRAW
            boot['main'][seed] = {'lo': pct(mm, 2.5), 'hi': pct(mm, 97.5), 'dropped': dropped, 'unstable': unst}
            boot['main_no_sweat'][seed] = {'lo': pct(mn, 2.5), 'hi': pct(mn, 97.5), 'dropped': dropped, 'unstable': unst}
            bL, bU = boot['main'][seed]['lo'], boot['main'][seed]['hi']
            hull['main'][seed] = {'interval': [min(bL, bound_main[0]), max(bU, bound_main[1])],
                                  'lo_from': 'bootstrap' if bL <= bound_main[0] else 'window-bound',
                                  'hi_from': 'bootstrap' if bU >= bound_main[1] else 'window-bound'}
            bL2, bU2 = boot['main_no_sweat'][seed]['lo'], boot['main_no_sweat'][seed]['hi']
            hull['main_no_sweat'][seed] = {'interval': [min(bL2, bound_mns[0]), max(bU2, bound_mns[1])],
                                           'lo_from': 'bootstrap' if bL2 <= bound_mns[0] else 'window-bound',
                                           'hi_from': 'bootstrap' if bU2 >= bound_mns[1] else 'window-bound'}
        rec['window_bound'] = {'main': bound_main, 'main_no_sweat': bound_mns}
        rec['bootstrap'] = boot; rec['hull'] = hull
    m4[m] = rec
RESULTS['M4'] = m4
print('M4 done %.1fs' % (time.time() - T0))

# ============================ M5 ============================
def caller_ht_month(m):
    ht = compute.ht_by_pred(windows, m)
    callers = {}
    n_fa, sweat, s2a, s2c = compute.fastauth_signer_shares(nd, m)
    for pred, v in ht.items():
        if pred == 'fast-auth.near':
            if m in nd and n_fa > 0:
                sc = Counter(c['signer'] for c in nd[m] if c['predecessor'] == 'fast-auth.near')
                tot = sum(sc.values())
                for sig, cnt in sc.items():
                    key = sig + ' (via FastAuth)'
                    callers[key] = callers.get(key, 0.0) + v * cnt / tot
            else:
                callers['fast-auth.near (whole)'] = callers.get('fast-auth.near (whole)', 0.0) + v
        else:
            callers[pred] = callers.get(pred, 0.0) + v
    return callers

m5 = {}
for m in months:
    ht = compute.ht_by_pred(windows, m); allht = sum(ht.values())
    if allht == 0:
        m5[m] = {'completed': mc[m], 'note': 'no calls'}; continue
    cal = caller_ht_month(m)
    ranked = sorted(cal.items(), key=lambda kv: -kv[1])
    top1 = ranked[0]; top3 = ranked[:3]
    ct, _ = compute.class_totals(ht)
    n_fa, sweat, s2a, s2c = compute.fastauth_signer_shares(nd, m)
    fa = ct.get('2', 0.0)
    sweatshare = (fa * s2a / allht) if (m in nd and s2a is not None) else None
    m5[m] = {'completed': mc[m],
             'top1': {'name': top1[0], 'share': top1[1] / allht},
             'top3': [{'name': k, 'share': v / allht} for k, v in top3],
             'top3_share': sum(v for _, v in top3) / allht,
             'sweat_2a_share': sweatshare}
m5['oct2026_largest'] = m5['2026-10']['top1']
RESULTS['M5'] = m5
print('M5 done %.1fs' % (time.time() - T0))

# ============================ Trend ============================
last3 = ['2026-08', '2026-09', '2026-10']; prev3 = ['2026-05', '2026-06', '2026-07']
dl = sum(days(m) for m in last3); dp = sum(days(m) for m in prev3)

def month_adj_point(m, mode):
    ht = compute.ht_by_pred(windows, m); ct, _ = compute.class_totals(ht)
    allht = sum(ct.values()); fa = ct.get('2', 0.0)
    n_fa, sweat, s2a, s2c = compute.fastauth_signer_shares(nd, m)
    c2a = fa * s2a if s2a is not None else 0.0
    c3 = ct.get('3', 0.0)
    if mode == 'raw': return allht
    if mode == 'no2a': return allht - c2a
    if mode == 'no3_no2a': return allht - c3 - c2a

trend = {'last3': last3, 'prev3': prev3, 'days_last3': dl, 'days_prev3': dp,
         'day_counts': {m: days(m) for m in last3 + prev3}}
for mode in ['raw', 'no3_no2a', 'no2a']:
    tl = sum(month_adj_point(m, mode) for m in last3)
    tp = sum(month_adj_point(m, mode) for m in prev3)
    ratio = (tl / dl) / (tp / dp)
    entry = {'point': ratio, 'last3_total': tl, 'prev3_total': tp,
             'rate_last3': tl / dl, 'rate_prev3': tp / dp, 'bootstrap': {}}
    # bootstrap
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        last_tot = np.zeros(NDRAW); prev_tot = np.zeros(NDRAW)
        valid = np.ones(NDRAW, bool)
        for grp, acc in ((last3, 'L'), (prev3, 'P')):
            for m in grp:
                arrs = P['month_strata'][m]
                cls = engine.draw_month_classvecs(arrs, rng, NDRAW)
                alld = cls.sum(axis=1); fad = cls[:, 1]; c3d = cls[:, 2]
                ht = compute.ht_by_pred(windows, m); ct, _ = compute.class_totals(ht)
                fa_arr = engine.nd_blocks_full(m)[0]
                s_draw, vnd = engine.draw_fa_share(fa_arr, rng, NDRAW)
                need_fa = (ct.get('2', 0.0) > 0) and mode in ('no2a', 'no3_no2a')
                if need_fa:
                    valid &= ~((fad > 0) & (~vnd))
                c2ad = fad * s_draw
                if mode == 'raw':
                    tot = alld
                elif mode == 'no2a':
                    tot = alld - c2ad
                else:
                    tot = alld - c3d - c2ad
                if grp is last3:
                    last_tot += tot
                else:
                    prev_tot += tot
        valid &= (prev_tot > 0)
        with np.errstate(divide='ignore', invalid='ignore'):
            r = (last_tot / dl) / (prev_tot / dp)
        rv = r[valid]
        dropped = int(NDRAW - valid.sum())
        unstable = dropped > 0.05 * NDRAW
        lo, hi = pct(rv, 2.5), pct(rv, 97.5)
        if unstable:
            reading = 'inconclusive (unstable)'
        elif lo > 1:
            reading = 'growing'
        elif hi < 1:
            reading = 'shrinking'
        else:
            reading = 'inconclusive'
        entry['bootstrap'][seed] = {'lo': lo, 'hi': hi, 'dropped': dropped,
                                    'unstable': unstable, 'reading': reading}
    trend[mode] = entry
RESULTS['trend'] = trend
print('trend done %.1fs' % (time.time() - T0))

# ============================ M6 ============================
m3_rate = {}
for m in months:
    ht = compute.ht_by_pred(windows, m); allht = sum(ht.values())
    m3_rate[m] = allht / days(m)
m6 = {}
for m in sorted(nd):
    fa_arr, m6_arr = engine.nd_blocks_full(m)
    tot = m6_arr.sum(axis=0)  # [secp0, jwt1, other1]
    n = tot.sum()
    if n == 0:
        m6[m] = {'note': 'no sampled sign calls'}; continue
    shares = {'secp256k1_domain0': tot[0] / n, 'ed25519_fastauth_jwt': tot[1] / n,
              'other_ed25519_domain1': tot[2] / n}
    rate = m3_rate[m]
    m6[m] = {'n_sampled_sign_calls': int(n), 'completed': mc[m], 'shares': shares,
             'applied_to_M3_rate_per_day': {k: v * rate for k, v in shares.items()},
             'm3_rate_per_day': rate}
RESULTS['M6'] = m6
print('M6 done %.1fs' % (time.time() - T0))


# ============================ Predecessor inventory ============================
inv = {}
for m in months:
    if not mc[m]:
        continue
    for w in windows:
        if w['month'] == m and w['completed']:
            for pred, c in w['pred_count'].items():
                cls, rule = load.classify(pred)
                e = inv.setdefault(pred, {'class': cls, 'rule': rule, 'HT_total_completed': 0.0})
                e['HT_total_completed'] += w['weight'] * c
RESULTS['predecessor_inventory'] = inv

# ============================ nd sample summary ============================
import json as _json
plan = _json.load(open(os.path.join(load.REPO, 'frozen/nd_plan.json')))
byheight = {}
for line in open(os.path.join(load.DATA, 'nd/blocks.jsonl')):
    r = _json.loads(line); part = r.get('part', '')
    if part.startswith('sample:'):
        byheight[(part.split(':')[1], r['height'])] = r.get('present')
ndsum = {}
for mm in sorted(plan['sample']):
    hs = plan['sample'][mm]
    pt = sum(1 for h in hs if byheight.get((mm, h)) == True)
    pf = sum(1 for h in hs if byheight.get((mm, h)) == False)
    miss = [h for h in hs if (mm, h) not in byheight]
    nsign = len(nd.get(mm, []))
    nfa = sum(1 for c in nd.get(mm, []) if c['predecessor'] == 'fast-auth.near')
    sweat = sum(1 for c in nd.get(mm, []) if c['predecessor'] == 'fast-auth.near' and c['signer'] == 'sweat-relayer.near')
    ndsum[mm] = {'planned': len(hs), 'present': pt, 'absent_block': pf, 'missing_rows': len(miss),
                 'sign_calls': nsign, 'fastauth_calls': nfa, 'fastauth_sweat': sweat,
                 'fastauth_other_signers': sorted(set(c['signer'] for c in nd.get(mm, []) if c['predecessor'] == 'fast-auth.near' and c['signer'] != 'sweat-relayer.near'))}
RESULTS['nd_sample_summary'] = ndsum

# ============================ Trend alternative definition ============================
def month_rate_point(m, mode):
    return month_adj_point(m, mode) / days(m)
trend_alt = {}
for mode in ['raw', 'no3_no2a', 'no2a']:
    rl = sum(month_rate_point(m, mode) for m in last3) / 3.0
    rp = sum(month_rate_point(m, mode) for m in prev3) / 3.0
    trend_alt[mode] = {'point_mean_of_monthly_rates': rl / rp, 'rate_last3': rl, 'rate_prev3': rp}
RESULTS['trend_alt_def'] = trend_alt

TELEM['runtime_s'] = time.time() - T0
RESULTS['telemetry'] = TELEM
json.dump(RESULTS, open('results.json', 'w'), indent=1, default=float)
print('ALL done, wrote results.json, %.1fs' % (time.time() - T0))
