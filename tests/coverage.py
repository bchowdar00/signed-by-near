"""Coverage of the frozen design's intervals on synthetic replays (no counted data).

  python3 -I tests/coverage.py <instants.json> <work_dir> <n_seeds> <out.json>

For each seed, tests/simulate.py writes collector-shaped output from a known population at the
frozen planning rates, analysis/recompute.py reads it, and the published intervals are compared
with the population's true values: M3's monthly rates, the trend, and the count shares of SOL,
the Solana stablecoins and BTC in the claim window (BTC against the realised count of
btc.omft.near, which the design reads whole). Synthetic transfers are Poisson in time, so
this checks the estimators and code, not how clustered the real flow is.
"""
import json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'analysis'))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
import recompute  # noqa: E402
import simulate  # noqa: E402


def truths(instants):
    sign = {}
    rate = {}
    for w in instants['windows']:
        if w['family'] == 'sign':
            sign.setdefault(w['month'], {})[w['stratum']] = (w['rate_plan_per_day'], w['D_s'])
        if w['family'] == 'flow':
            rate[w['stratum']] = w['rate_plan_per_day'] / simulate.ROWS_PER_TRANSFER
    m3 = {m: sum(a * d for a, d in v.values()) / sum(d for _, d in v.values()) for m, v in sign.items()}
    days = {m: sum(d for _, d in v.values()) for m, v in sign.items()}
    A, B = ['2026-08', '2026-09', '2026-10'], ['2026-05', '2026-06', '2026-07']
    tr = (sum(m3[m] * days[m] for m in A) / sum(days[m] for m in A)) / \
         (sum(m3[m] * days[m] for m in B) / sum(days[m] for m in B))
    P = simulate.POP
    sol = 'sol.omft.near'
    usdc, usdt = 'sol-5ce3bf3a31af18be40ba30f721101b4341690186.omft.near', 'sol-c800a4bd850783ccb82c2b2c7e84175443606352.omft.near'
    rn, rb = rate['flow:nbtc.bridge.near:claim'], rate['flow:btc.omft.near:claim']
    ru, rt = rate[f'flow:{usdc}:claim'], rate[f'flow:{usdt}:claim']
    shares = {
        'SOL': (P[sol][1], P[sol][1] + P[sol][2]),
        'Solana stablecoins (USD)': ((ru * P[usdc][1] + rt * P[usdt][1]) / (ru + rt),) * 2,
        'BTC': ((rn * (P['nbtc.bridge.near'][1] + P['nbtc.bridge.near'][2])) / (rn + rb),) * 2,
    }
    return m3, tr, shares


def main(instants_path, work, n, out):
    with open(instants_path) as f:
        I = json.load(f)
    m3t, trt, sht = truths(I)
    w_n = [w for w in I['windows'] if w['stratum'] == 'flow:nbtc.bridge.near:claim'][0]
    btc_n_expected = w_n['rate_plan_per_day'] / simulate.ROWS_PER_TRANSFER * w_n['D_s'] / 86400.0
    res = {'seeds': [], 'm3': [0, 0], 'trend': [0, 0], 'shares': {g: [0, 0] for g in sht}}
    for seed in range(100, 100 + n):
        d = os.path.join(work, f's{seed}')
        shutil.rmtree(d, ignore_errors=True)
        simulate.simulate(instants_path, d, seed=seed)
        R = recompute.run(instants_path, d, os.path.join(d, 'out'))
        row = {'seed': seed, 'm3_missed': []}
        for r in R['M3']:
            x = r['raw']
            ok = x['lo'] is not None and x['lo'] <= m3t[r['month']] <= x['hi']
            res['m3'][0] += ok
            res['m3'][1] += 1
            if not ok:
                row['m3_missed'].append(r['month'])
        t = R['trend']['raw']
        okt = t['lo'] is not None and t['lo'] <= trt <= t['hi']
        res['trend'][0] += okt
        res['trend'][1] += 1
        row['trend'] = [t['lo'], t['point'], t['hi'], okt]
        for g, (lo_t, hi_t) in sht.items():
            p = R['C2b'][g]['readings']['claim|count|both']
            if g == 'BTC':
                # btc.omft.near is read whole, so the target is its realised count, not its expectation
                ps = {x['stratum']: x['T_h'] for x in p['reading_L']['per_stratum']}
                nb_ = btc_n_expected
                lo_t = hi_t = nb_ / (nb_ + ps.get('flow:btc.omft.near:claim', 0.0))
            ok = p['L'] is not None and p['L'] <= lo_t and hi_t <= p['U']
            res['shares'][g][0] += ok
            res['shares'][g][1] += 1
            row[g] = [p['L'], p['U'], ok, lo_t, hi_t]
        res['seeds'].append(row)
        shutil.rmtree(d, ignore_errors=True)
        print(seed, 'trend', okt, 'm3 missed', row['m3_missed'], flush=True)
    res['truth'] = {'trend': trt, 'shares': sht}
    with open(out, 'w') as f:
        json.dump(res, f, indent=1)
    print('m3', res['m3'], 'trend', res['trend'], 'shares', res['shares'])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4])
