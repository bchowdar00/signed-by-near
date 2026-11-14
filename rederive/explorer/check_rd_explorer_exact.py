"""Synthetic check of rd_explorer_exact.py: made-up cells with answers worked by hand.
Usage: python3 -I check_rd_explorer_exact.py <assets.json> <sdk_list.ts> <scratch_dir>"""
import sys, os, json, subprocess
from decimal import Decimal as D
assets, sdk, d = sys.argv[1:4]
HERE = os.path.dirname(os.path.abspath(__file__))
OM, OMNEAR = 'nep141:abs.omdep.near', 'nep141:strk-0xe646ef2a705bf5147ceffc8dfbcc7bee4946b8f7.omdep.near'
HOT, BTCN, CS_SOL = 'nep245:v2_1.omni.hot.tg:10_11111111111111111111', '1cs_v1:btc:native:coin', '1cs_v1:sol:spl:3ZLekZYq2qkZiSpnSvabjit34tUkjSwD1JFuW9as9wBG'
SOL, ETH, WRAP, ZEC = 'nep141:sol.omft.near', 'nep141:eth.omft.near', 'nep141:wrap.near', 'nep141:zec.omft.near'
UNLISTED_POA = 'nep141:xyz-0xabc.omft.near'
Dt, O, I = 'DESTINATION_CHAIN', 'ORIGIN_CHAIN', 'INTENTS'
b0 = [[ETH, SOL, O, Dt, 2, '100.1', '99.2', 0, 0],      # dep poa(eth) 100.1; wd sdk(sol) 99.2
      [WRAP, OM, I, Dt, 1, '50', '49.05', 0, 0],        # dep inside 50; wd omni(abs) 49.05
      [BTCN, HOT, O, Dt, 3, '30', '29', 0, 1],          # dep omni(btc) 30; wd hot 29; 1 row no USD out
      [CS_SOL, WRAP, O, I, 1, '20', '19', 0, 0],        # dep unclassified(sol) 20; wd inside 19
      [ZEC, OMNEAR, O, Dt, 1, '10', '9', 0, 0],         # dep sdk(zec) 10; wd near 9 (list puts it on near)
      [WRAP, UNLISTED_POA, I, Dt, 1, '5', '4', 1, 0],   # dep inside 5 (1 row no USD in); wd poa(xyz) 4
      [ETH, WRAP, O, Dt, 1, '0.1', '0.2', 0, 0]]        # dep poa(eth) 0.1; wd near 0.2
b65 = [[ETH, SOL, O, Dt, 1, '40', '39', 0, 0]]          # dep poa 40; wd sdk 39
def line(b, start, end, cells):
    return {'block': b, 'start': start, 'end': end, 'began': '2026-11-13T23:00:00Z', 'finished': '2026-11-13T23:01:00Z',
            'pages': 1, 'rows': sum(c[4] for c in cells), 'dropped_outside': 0, 'duplicates': 0,
            'page_sha256': ['0' * 64], 'cells': cells}
lines = [line(0, '2026-08-12T11:00:00.000Z', '2026-08-13T11:00:00.000Z', b0),
         line(65, '2026-10-16T11:00:00.000Z', '2026-10-17T11:00:00.000Z', b65)]
os.makedirs(d, exist_ok=True)
bp, op = os.path.join(d, 'blocks.synthetic.jsonl'), os.path.join(d, 'out.synthetic.json')
open(bp, 'w').write(''.join(json.dumps(x) + '\n' for x in lines))
subprocess.run([sys.executable, '-I', os.path.join(HERE, 'rd_explorer_exact.py'), bp, assets, sdk, op], check=True, capture_output=True)
r = json.load(open(op))
fails = []
def eq(name, got, want):
    ok = (got is None and want is None) or (got is not None and want is not None and D(str(got)) == D(str(want)))
    print('%-4s %-44s got %-34s want %s' % ('ok' if ok else 'FAIL', name, got, want))
    if not ok: fails.append(name)
def q(a, b):
    from decimal import localcontext
    with localcontext() as c:
        c.prec = 30
        return D(a) / D(b)
w, p, t = r['withdrawals'], r['deposits'], r['totals']
wc, pc = w['usd_by_category'], p['usd_by_category']
for k, v in {'omni': '49.05', 'sdk': '138.2', 'poa': '4', 'hot': '29', 'unclassified': '0', 'near': '9.2', 'inside': '19'}.items():
    eq('wd ' + k, wc[k], v)
eq('wd bridged', w['bridged_usd'], '220.25')
eq('wd share omni', w['shares_of_bridged']['omni'], q('49.05', '220.25'))
eq('wd share omni+sdk', w['shares_of_bridged']['omni+sdk'], q('187.25', '220.25'))
eq('wd share hot', w['shares_of_bridged']['hot'], q('29', '220.25'))
eq('wd sampled8 bridged', w['sampled8']['bridged_usd'], '138.2')
eq('wd sampled8 chains', w['sampled8']['chains_with_value_count'], 1)
eq('wd other bridged', w['other_chains']['bridged_usd'], '82.05')
eq('wd other chains', w['other_chains']['chains_with_value_count'], 3)
for k, v in {'omni': '30', 'sdk': '10', 'poa': '140.2', 'hot': '0', 'unclassified': '20', 'near': '0', 'inside': '55'}.items():
    eq('dep ' + k, pc[k], v)
eq('dep bridged', p['bridged_usd'], '200.2')
eq('dep share omni+sdk+uncl', p['shares_of_bridged']['omni+sdk+unclassified'], q('60', '200.2'))
eq('in 90d', t['amountInUsd_90d'], '255.2')
eq('in 60-89', t['amountInUsd_blocks_60_89'], '40')
eq('out 90d', t['amountOutUsd_90d'], '248.45')
eq('rows', t['rows'], 11)
eq('rows no out', t['rows_no_amountOutUsd'], 1)
eq('rows no in', t['rows_no_amountInUsd'], 1)
eq('bad bounds', len(r['checks']['bad_bounds']), 0)
eq('rows key mismatch', len(r['checks']['rows_key_mismatch']), 0)
print('failures:', len(fails), fails)
sys.exit(1 if fails else 0)
