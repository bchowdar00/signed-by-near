"""Numbers on THESIS.md that the four parts do not output directly, recomputed from the saved files.
Offline. Usage: python3 -I page_extras.py <repo_dir> <data_dir> <vendor_f1_dir> [out.json]
  <vendor_f1_dir>: mc-seeds/vendor/f1, the second implementation's share code."""
import sys, os, json, glob
from collections import Counter
REPO, DATA = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
os.environ['RD_REPO'], os.environ['RD_DATA'] = REPO, DATA
sys.path.insert(0, os.path.abspath(sys.argv[3]))
import shares as S
out = {}

# 1. "Three all-Omni windows give a lower bound of 29%": Clopper-Pearson lower end with all successes is 0.025^(1/m)
out['cp_all_success_m3'] = 0.025 ** (1 / 3)

# 2. Windows of the two BTC tokens (frozen/instants.json)
W = json.load(open(os.path.join(REPO, 'frozen', 'instants.json')))['windows']
c = Counter((w['family'], w.get('token'), w.get('period')) for w in W if w.get('token') in ('nbtc.bridge.near', 'btc.omft.near'))
out['btc_omni_token_90d_windows'] = {'claim': c[('flow', 'nbtc.bridge.near', 'claim')], 'outside': c[('flow', 'nbtc.bridge.near', 'outside')]}
out['btc_early_windows'] = c[('migration', 'nbtc.bridge.near', 'early')] + c[('migration', 'btc.omft.near', 'early')]

# 3. Blocks per month whose call arguments are read (frozen/nd_plan.json)
plan = json.load(open(os.path.join(REPO, 'frozen', 'nd_plan.json')))['sample']
out['nd_blocks_per_month'] = sorted(set(len(v) for v in plan.values()))

# 4. EVM, Tron and XRP tokens over the 90 days: windows, windows with a transfer, Kish effective windows behind the upper end
tok = json.load(open(os.path.join(REPO, 'frozen', 'tokens.json')))['tokens']
ev = {}
for t in tok:
    if t['chain'] not in ('ethereum', 'arbitrum', 'base', 'tron', 'xrp'):
        continue
    st = S.build_strata([(t['contract'], t['decimals'])], ['claim', 'outside'])
    L, U, det = S.window_bound(st, 'amount', 'both', 'not')
    d, nwin = S.distinct_and_windows(st, 'amount', 'both')
    import math
    m_eff = math.log(0.025) / math.log(1 - U) if 0 < U < 1 else None  # the m that gives this upper end with no Omni value
    ev[t['contract']] = {'chain': t['chain'], 'windows': sum(x.get('n_windows') or 0 for x in det), 'windows_with_transfer': nwin,
                         'transfers': d, 'U': float(U), 'effective_windows': m_eff}
out['evm_tron_xrp_tokens'] = ev
# per reading, as the page counts them: one reading per chain and unit (a chain's own coin, or its dollar tokens);
# the frozen M1 keeps units apart (amount_share_by_unit), so Ethereum has two readings, ETH and USD
unit_of = {t['contract']: (t['chain'], t['unit_group']) for t in tok}
rd = Counter('%s %s' % unit_of[w['token']] for w in W if w['family'] == 'flow' and w.get('token') in unit_of
             and unit_of[w['token']][0] in ('ethereum', 'arbitrum', 'base', 'tron', 'xrp'))
out['evm_tron_xrp_readings'] = len(rd)
out['evm_tron_xrp_windows_per_reading'] = dict(sorted(rd.items()))
out['evm_tron_xrp_windows_per_reading_range'] = [min(rd.values()), max(rd.values())]
out['evm_tron_xrp_windows_range'] = [min(v['windows'] for v in ev.values()), max(v['windows'] for v in ev.values())]
out['evm_tron_xrp_effective_range'] = [min(v['effective_windows'] for v in ev.values()), max(v['effective_windows'] for v in ev.values())]

# 5. Zcash picks of the destination audit: inputs by address, from the saved explorer records (audit/raw)
A = json.load(open(os.path.join(REPO, 'audit', 'dest-audit.json')))
rows = A['rows']
z = [r for r in rows if str(r.get('chain', '')).upper() == 'ZCASH']
def find(o, k):
    if isinstance(o, dict):
        for a, b in o.items():
            if a == k: yield b
            yield from find(b, k)
    elif isinstance(o, list):
        for b in o: yield from find(b, k)
signers = sorted(set(r['dest_address'] for r in z))
zz = {}
for r in z:
    f = glob.glob(os.path.join(REPO, 'audit', 'raw', 'zcash-' + r['dest_txn'] + '.json'))
    ins = next(find(json.load(open(f[0])), 'inputs'))
    own = sum(i['value'] for i in ins if i['recipient'] == r['dest_address'])
    known = sum(i['value'] for i in ins if i['recipient'] in signers)
    tot = sum(i['value'] for i in ins)
    outs = next(find(json.load(open(f[0])), 'outputs'))
    to_other = sum(o['value'] for o in outs if o.get('recipient') != r['dest_address'])  # to any address but the pick's own signer address
    zz[r['dest_txn'][:12]] = {'from_own_signer': own, 'from_known_signers': known, 'total_in': tot, 'out_to_other_addresses': to_other}
out['zec_picks'] = len(z)
out['zec_signer_addresses'] = len(signers)
out['zec_inputs'] = zz
out['zec_most_input_from_outside_known'] = sum(1 for v in zz.values() if v['from_known_signers'] * 2 < v['total_in'])
out['zec_all_inputs_from_known'] = sum(1 for v in zz.values() if v['from_known_signers'] == v['total_in'])
out['zec_no_value_to_other_transparent_address'] = sum(1 for v in zz.values() if v['out_to_other_addresses'] == 0)

o = sys.argv[4] if len(sys.argv) > 4 else 'page_extras.json'
json.dump(out, open(o, 'w'), indent=1, default=float)
for k, v in out.items():
    if k not in ('evm_tron_xrp_tokens', 'zec_inputs'): print(k, v)
print('74bd9e36c001', zz.get('74bd9e36c001'))
