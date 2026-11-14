"""Seed sweeps for two bootstrap interval ends printed in THESIS.md, run after the counted read by the
re-deriving session (the NEAR parent session), 2026-11-13.

It re-runs the independent re-derivation's own bootstraps (not the frozen analysis code) over many seeds,
2,000 draws each, to measure the Monte Carlo spread of:
  1. the lower end of Bitcoin's 90-day amount share on Omni (seeds 1-60);
  2. both ends of the measured non-Omni value per 30 days (seeds 1-40), with read-whole strata held
     fixed as METHOD has it, and also resampled (the re-derivation's F2 variant), for comparison.

The modules in vendor/ are byte copies of the re-derivation's code (rederive/f1-c2b-m10 and
rederive/f2-m9-m1) except for one change: their repository and data paths come from the command line.

Usage, offline:  python3 -I sweep.py <repo_dir> <data_dir> [out.json]
  <repo_dir>  the thesis repository (reads frozen/instants.json, frozen/tokens.json, inputs/reference.json)
  <data_dir>  the saved sample (reads nb/windows.jsonl and nb/pages/)
Output: sweep.json beside this file unless out.json is given.
"""
import sys, os, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['RD_REPO'] = os.path.abspath(sys.argv[1])
os.environ['RD_DATA'] = os.path.abspath(sys.argv[2])
OUT = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, 'sweep.json')
out = {}

# 1. BTC 90-day amount share, lower end (re-derivation F1), seeds 1..60
sys.path.insert(0, os.path.join(HERE, 'vendor', 'f1'))
import shares as S
st = S.build_strata([('nbtc.bridge.near', 8), ('btc.omft.near', 8)], ['claim', 'outside'])
lo = []
for s in range(1, 61):
    l, h, d, n = S.bootstrap(st, 'amount', 'both', 'not', s); lo.append(float(l))
out['btc_90d_amount_lower'] = {'seeds': '1-60', 'draws': 2000, 'published': 0.997085,
    'point': [float(x) for x in S.point_share(st, 'amount', 'both', 'not')], 'values': lo,
    'min': min(lo), 'max': max(lo), 'n_round_to_99.8': sum(1 for v in lo if round(v * 100, 1) >= 99.8)}
sys.path.pop(0)

# 2. Non-Omni value per 30 days, both ends (re-derivation F2), seeds 1..40
sys.path.insert(0, os.path.join(HERE, 'vendor', 'f2'))
import analyze

def nonomni_val(t, include_unknown):
    # copied from rederive/f2-m9-m1/run_m9.py. Low end: POA only (unknown counted as Omni); high end: POA + unknown
    if t['route'] == 'poa':
        return analyze.usd(t)
    if include_unknown and t['route'] in ('unknown', 'mixed'):
        return analyze.usd(t)
    return 0.0

wins = analyze.load_flow_windows()
sdata = []
for stn, ws in analyze.strata_of(wins).items():
    arr = np.array([w['weight'] * sum(nonomni_val(t, False) for t in w['transfers']) for w in ws])
    sdata.append((arr, len(ws), all(w.get('whole') for w in ws)))
SCALE = 30 / 84; TWO_V = 2 * 831333190.29

def boot(seed, fix_whole):
    rng = np.random.default_rng(seed); v = np.empty(2000)
    for i in range(2000):
        tot = 0.0
        for arr, n, wh in sdata:
            if fix_whole and wh: tot += arr.sum(); continue
            tot += arr[rng.integers(0, n, n)].sum()
        v[i] = tot
    return float(np.percentile(v, 2.5) * SCALE), float(np.percentile(v, 97.5) * SCALE)

for fw in (True, False):
    lo, hi = zip(*[boot(s, fw) for s in range(1, 41)])
    out['nonomni_30d_' + ('whole_fixed' if fw else 'whole_resampled')] = {
        'seeds': '1-40', 'draws': 2000, 'published_low': 1163180000, 'published_high': 2586210000,
        'low_values': lo, 'high_values': hi, 'low_min': min(lo), 'low_max': max(lo), 'high_min': min(hi), 'high_max': max(hi),
        'high_over_2V_min': min(hi) / TWO_V, 'high_over_2V_max': max(hi) / TWO_V,
        'low_rounded_B_1dp': sorted(set(round(x / 1e9, 1) for x in lo)), 'high_rounded_B_1dp': sorted(set(round(x / 1e9, 1) for x in hi))}
out['n_strata'] = len(sdata)
json.dump(out, open(OUT, 'w'), indent=1)
for k, v in out.items():
    if isinstance(v, dict): print(k, {a: b for a, b in v.items() if not a.endswith('values')})
