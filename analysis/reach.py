"""Can each C2b verdict go both ways? (METHOD §6.5, §7). Uncounted; reads saved files only.

  python3 -I reach.py <shakedown sd-flow-sol page dir> <rates-plan-draft.json> [out.json]

1. Solana. The window-level bound (§4.0) gives an all-Omni stratum a lower limit of 0.025^(1/m),
   with m Kish's effective count over the windows' amounts; 90% needs m >= 36. Window amounts are
   simulated as the sum of N ~ Poisson(20) transfer amounts (the window is sized to expect 20 rows),
   drawn from (a) the shakedown window's own SOL amounts into intents.near, resampled, and (b) a
   lognormal with that sample's log-sd. 400 replications per window count, seed 1.
2. BTC. btc.omft.near's 6 claim-window windows (length 20 / rate days, starts uniform on [-l, D),
   clipped to the 28-day stratum) with every window on POA: the share's upper limit is
   1 - 0.025^(1/m). "Contradicted" needs it below 50%. 4,000 replications per log-sd, seed 7.
"""
import glob, json, math, os, random, statistics as st, sys


def kish(ws):
    s = sum(ws)
    return s * s / sum(w * w for w in ws) if s else 0


def solana(page_dir):
    rows = []
    for f in sorted(glob.glob(os.path.join(page_dir, '*.json'))):
        with open(f) as fh:
            rows += json.load(fh)['rows']
    a = [abs(int(r['delta_amount'])) / 1e9 for r in rows if r['affected_account_id'] == 'intents.near']
    sig = st.stdev([math.log(x) for x in a if x > 0])
    R = random.Random(1)

    def pois(l):
        L, k, p = math.exp(-l), 0, 1.0
        while True:
            p *= R.random()
            if p < L:
                return k
            k += 1
    out = {'n_amounts': len(a), 'log_sd': sig, 'by_model': {}}
    for label, draw in (('bootstrap', lambda: R.choice(a)), ('lognormal', lambda: math.exp(R.gauss(0, sig)))):
        res = []
        for n in (18, 36, 54, 72, 108, 144):
            ks = sorted(kish([sum(draw() for _ in range(pois(20))) for _ in range(n)]) for _ in range(400))
            res.append({'windows': n, 'mean_kish': sum(ks) / len(ks), 'p10_kish': ks[40],
                        'p_kish_ge_36': sum(k >= 36 for k in ks) / len(ks)})
        out['by_model'][label] = res
    return out


def btc(rates_path):
    with open(rates_path) as f:
        rate = json.load(f)['flow_rate_per_day']['btc.omft.near']
    D, n = 28.0, 6
    ell = 20 / rate - 120 / 86400
    R = random.Random(7)

    def pois(l):
        L, k, p = math.exp(-l), 0, 1.0
        while True:
            p *= R.random()
            if p < L:
                return k
            k += 1
    out = {'rate_per_day': rate, 'window_days': ell, 'windows': n, 'by_log_sd': []}
    for sig in (1.0, 1.55, 2.0):
        cu = []
        for _ in range(4000):
            ws = []
            for i in range(n):
                u = -ell + (D + ell) * R.random()
                cov = max(0, min(u + ell, D) - max(u, 0))
                ws.append(sum(math.exp(R.gauss(0, sig)) for _ in range(pois(rate * cov))))
            s, q = sum(ws), sum(w * w for w in ws)
            m = s * s / q if q else 0
            cu.append(1 - 0.025 ** (1 / m) if m > 0 else 1)
        cu.sort()
        out['by_log_sd'].append({'log_sd': sig, 'median_upper': cu[2000],
                                 'p_upper_below_50': sum(c < 0.5 for c in cu) / 4000})
    return out


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    res = {'solana': solana(sys.argv[1]), 'btc_omft_windows': btc(sys.argv[2])}
    txt = json.dumps(res, indent=1, sort_keys=True)
    print(txt)
    if len(sys.argv) > 3:
        with open(sys.argv[3], 'w') as f:
            f.write(txt + '\n')
