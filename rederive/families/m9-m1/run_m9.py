import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import analyze, build, statlib
from collections import defaultdict

REF = json.load(open(os.path.join(build.REPO, 'inputs/reference.json')))
V = REF['V_usd']; HEAD = REF['V_headline_usd']; V_ch = REF['V_ch']
TOK = build.load_tokens()
wins = analyze.load_flow_windows()
MEAS_DAYS = 84; SCALE = 30.0 / MEAS_DAYS
res = {}

# ---------- p and p_CS ----------
def share_block(name, num_sel, label):
    # point L (olo) and U (ohi)
    pL, nL, dL = analyze.point_share(wins, analyze.usd, num_sel, analyze.olo)
    pU, nU, dU = analyze.point_share(wins, analyze.usd, num_sel, analyze.ohi)
    b1 = analyze.bootstrap_share(wins, analyze.usd, num_sel, analyze.olo, seed=1)
    b2 = analyze.bootstrap_share(wins, analyze.usd, num_sel, analyze.olo, seed=2)
    b1U = analyze.bootstrap_share(wins, analyze.usd, num_sel, analyze.ohi, seed=1)
    b2U = analyze.bootstrap_share(wins, analyze.usd, num_sel, analyze.ohi, seed=2)
    wlL, _, detL = analyze.window_level_bound(wins, analyze.usd, num_sel, analyze.olo)
    _, wlU, detU = analyze.window_level_bound(wins, analyze.usd, num_sel, analyze.ohi)
    # hull: L from olo components, U from ohi components (DEVIATIONS 2)
    L = min(x for x in [b1[0], b2[0], wlL] if x is not None)
    U = max(x for x in [b1U[1], b2U[1], wlU] if x is not None)
    srcL = 'window-bound' if wlL == L else 'bootstrap'
    srcU = 'window-bound' if wlU == U else 'bootstrap'
    out = {'point_L_unknown_not_omni': pL, 'point_U_unknown_omni': pU,
           'bootstrap_seed1_lo': b1[0], 'bootstrap_seed1_hi': b1[1], 'bootstrap_seed1_dropped': b1[2],
           'bootstrap_seed2_lo': b2[0], 'bootstrap_seed2_hi': b2[1], 'bootstrap_seed2_dropped': b2[2],
           'window_bound_L': wlL, 'window_bound_U': wlU,
           'hull_L': L, 'hull_U': U, 'hull_srcL': srcL, 'hull_srcU': srcU}
    res[name] = out
    print(f'\n=== {label} ===')
    print(f'  point L={pL:.6f} U={pU:.6f}')
    print(f'  bootstrap seed1 [{b1[0]:.6f},{b1[1]:.6f}] dropped={b1[2]}  seed2 [{b2[0]:.6f},{b2[1]:.6f}] dropped={b2[2]}')
    print(f'  window bound [{wlL:.6f},{wlU:.6f}]')
    print(f'  HULL [L={L:.6f} ({srcL}), U={U:.6f} ({srcU})]')
    return out

p = share_block('p', lambda t: True, 'p (Omni share of all measured USD value, 90d)')
pcs = share_block('p_CS', lambda t: t['direction'] == 'out', 'p_CS (Omni withdrawals as share of all measured value)')

# ---------- measured value per 30 days (HT total * 30/84) ----------
def bootstrap_total(wins, valfn, seed, ndraw=2000):
    strata = analyze.strata_of(wins)
    sdata = []
    for st, ws in strata.items():
        arr = np.array([w['weight'] * sum(valfn(t) for t in w['transfers']) for w in ws])
        sdata.append((arr, len(ws)))
    rng = np.random.default_rng(seed)
    vals = np.empty(ndraw)
    for i in range(ndraw):
        tot = 0.0
        for arr, n in sdata:
            idx = rng.integers(0, n, n)
            tot += arr[idx].sum()
        vals[i] = tot
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))

ht_total = sum(w['weight'] * sum(analyze.usd(t) for t in w['transfers']) for w in wins)
mv30 = ht_total * SCALE
mvb1 = bootstrap_total(wins, analyze.usd, 1); mvb2 = bootstrap_total(wins, analyze.usd, 2)
mv30_b1 = (mvb1[0] * SCALE, mvb1[1] * SCALE); mv30_b2 = (mvb2[0] * SCALE, mvb2[1] * SCALE)
res['measured_value'] = {'ht_total_84d': ht_total, 'per30d': mv30, 'measured_days': MEAS_DAYS,
                         'boot_seed1_per30d': mv30_b1, 'boot_seed2_per30d': mv30_b2}
print(f'\n=== measured value per 30 days ===')
print(f'  HT total 84d = {ht_total:,.2f}  per30d = {mv30:,.2f}')
print(f'  boot seed1 per30d [{mv30_b1[0]:,.0f},{mv30_b1[1]:,.0f}]  seed2 [{mv30_b2[0]:,.0f},{mv30_b2[1]:,.0f}]')
print(f'  84 days = 90 - (Sep29..Oct4 = 6 days)')

# ---------- coverage c ----------
c_V = mv30 / V; c_2V_un = mv30 / (2 * V); c_2V_cap = min(1.0, c_2V_un); c_head = mv30 / HEAD
res['c'] = {'vs_V': c_V, 'vs_2V_uncapped': c_2V_un, 'vs_2V_capped': c_2V_cap, 'vs_headline': c_head, 'V': V, 'headline': HEAD}
print(f'\n=== coverage c ===  V={V:,.2f} 2V={2*V:,.2f} headline={HEAD:,.2f}')
print(f'  c/V={c_V:.6f}  c/2V uncapped={c_2V_un:.6f}  c/2V capped={c_2V_cap:.6f}  c/headline={c_head:.6f}')

# ---------- scenarios (c against 2V capped) ----------
c = c_2V_cap
S_L = p['hull_L'] * c
S_U = p['hull_U'] * c + (1 - c)
res['scenarios'] = {'c_used': c, 'S_L': S_L, 'S_U': S_U, 'formula': 'S_L=L*c ; S_U=U*c+(1-c)'}
print(f'\n=== scenarios (c={c:.6f} against 2V capped) ===')
print(f'  S_L = L*c = {p["hull_L"]:.6f}*{c:.6f} = {S_L:.6f}')
print(f'  S_U = U*c+(1-c) = {p["hull_U"]:.6f}*{c:.6f}+{1-c:.6f} = {S_U:.6f}')

# ---------- measured non-Omni value per 30 days ----------
def nonomni_val(t, include_unknown):
    # low end: POA only (unknown as omni -> excluded). high end: POA + unknown
    if t['route'] == 'poa':
        return analyze.usd(t)
    if include_unknown and t['route'] in ('unknown', 'mixed'):
        return analyze.usd(t)
    return 0.0

low_ht = sum(w['weight'] * sum(nonomni_val(t, False) for t in w['transfers']) for w in wins)
high_ht = sum(w['weight'] * sum(nonomni_val(t, True) for t in w['transfers']) for w in wins)
lb1 = bootstrap_total(wins, lambda t: nonomni_val(t, False), 1)
lb2 = bootstrap_total(wins, lambda t: nonomni_val(t, False), 2)
hb1 = bootstrap_total(wins, lambda t: nonomni_val(t, True), 1)
hb2 = bootstrap_total(wins, lambda t: nonomni_val(t, True), 2)
low30 = low_ht * SCALE; high30 = high_ht * SCALE
res['non_omni'] = {
    'low_per30d': low30, 'high_per30d': high30,
    'low_boot_seed1_per30d': (lb1[0]*SCALE, lb1[1]*SCALE), 'low_boot_seed2_per30d': (lb2[0]*SCALE, lb2[1]*SCALE),
    'high_boot_seed1_per30d': (hb1[0]*SCALE, hb1[1]*SCALE), 'high_boot_seed2_per30d': (hb2[0]*SCALE, hb2[1]*SCALE),
    'range_per30d': (lb1[0]*SCALE, hb1[1]*SCALE),
    'low_share_V': low30/V, 'low_share_2V': low30/(2*V), 'high_share_V': high30/V, 'high_share_2V': high30/(2*V)}
print(f'\n=== measured non-Omni value per 30 days ===')
print(f'  low (POA only) = {low30:,.2f}  boot s1 [{lb1[0]*SCALE:,.0f},{lb1[1]*SCALE:,.0f}] s2 [{lb2[0]*SCALE:,.0f},{lb2[1]*SCALE:,.0f}]')
print(f'  high (POA+unknown) = {high30:,.2f}  boot s1 [{hb1[0]*SCALE:,.0f},{hb1[1]*SCALE:,.0f}] s2 [{hb2[0]*SCALE:,.0f},{hb2[1]*SCALE:,.0f}]')
print(f'  range [{lb1[0]*SCALE:,.0f}, {hb1[1]*SCALE:,.0f}]')
print(f'  low as share V={low30/V:.6f} 2V={low30/(2*V):.6f}  (V=${V:,.0f}, 2V=${2*V:,.0f})')
print(f'  high as share V={high30/V:.6f} 2V={high30/(2*V):.6f}')

json.dump(res, open('m9_partial.json', 'w'), indent=1)
print('\nwrote m9_partial.json')
