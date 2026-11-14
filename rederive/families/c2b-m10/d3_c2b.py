import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import shares as S

USDC = 'sol-5ce3bf3a31af18be40ba30f721101b4341690186.omft.near'
USDT = 'sol-c800a4bd850783ccb82c2b2c7e84175443606352.omft.near'

GROUPS = {
    'BTC': {'tokens': [('nbtc.bridge.near', 8), ('btc.omft.near', 8)], 'verdict': True, 'tau': 0.90,
            'sens_tau': [0.80, 0.95]},
    'SOL': {'tokens': [('sol.omft.near', 9)], 'verdict': False, 'tau': 0.90, 'sens_tau': [0.80, 0.95]},
    'STABLE': {'tokens': [(USDC, 6), (USDT, 6)], 'verdict': False, 'tau': 0.90, 'sens_tau': [0.80, 0.95]},
}

READINGS = [
    ('claim|amount|both', ['claim'], 'amount', 'both'),
    ('claim|count|both', ['claim'], 'count', 'both'),
    ('claim|amount|in', ['claim'], 'amount', 'in'),
    ('claim|amount|out', ['claim'], 'amount', 'out'),
    ('90d|amount|both', ['claim', 'outside'], 'amount', 'both'),
]

out = {}
for gname, g in GROUPS.items():
    gout = {}
    for rname, pset, mode, direction in READINGS:
        strata = S.build_strata(g['tokens'], pset)
        r = S.read_interval(strata, mode, direction)
        tau = g['tau']
        st = {str(tau): S.state_of(r, tau)}
        for t2 in g['sens_tau']:
            st[str(t2)] = S.state_of(r, t2)
        r['state'] = st
        r['verdict'] = g['verdict']
        if not g['verdict']:
            r['label'] = 'estimate only, no verdict'
        gout[rname] = r
    out[gname] = gout

json.dump(out, open('d3_c2b.json', 'w'), indent=1)

def fmt(x):
    return 'None' if x is None else f'{x*100:.4f}%'

for gname in ['BTC', 'SOL', 'STABLE']:
    print('=====', gname, '=====')
    for rname, *_ in READINGS:
        r = out[gname][rname]
        b1 = r['bootstrap'][1]
        print(f"  {rname}: pt(not)={fmt(r['point_unknown_not'])} pt(omni)={fmt(r['point_unknown_omni'])} "
              f"| L={fmt(r['L'])}[{r['L_source']}] U={fmt(r['U'])}[{r['U_source']}]")
        print(f"      boot s1 L={fmt(b1['boot_L'])} U={fmt(b1['boot_U'])} drop={b1['dropped_not']}/{b1['dropped_omni']} "
              f"| distinct={r['distinct']} nwin={r['windows_with_transfer']} sparse={r['sparse']} "
              f"unstable={r['unstable']} state@tau={r['state']}")
