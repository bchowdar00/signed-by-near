import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
from collections import defaultdict
import lib
import transfers as T

FLOW_TOKENS = [
    'nbtc.bridge.near', 'btc.omft.near', 'sol.omft.near',
    'sol-5ce3bf3a31af18be40ba30f721101b4341690186.omft.near',  # USDC
    'sol-c800a4bd850783ccb82c2b2c7e84175443606352.omft.near',  # USDT
]
MIG_TOKENS = ['btc.omft.near', 'nbtc.bridge.near', 'sol.omft.near',
              'zec.omft.near', 'eth.omft.near']

# ---- Telemetry per token+stratum over flow windows ----
telem = []
my_candidates = []
for tok in FLOW_TOKENS:
    for period in ('claim', 'outside'):
        wins = T.flow_windows(tok, period)
        if not wins:
            continue
        res, all_ok = T.build_for_windows(wins)
        n_tr = 0
        routes = defaultdict(int)
        edge = mixed = nearside_excluded = 0
        refund_pairs = 0
        distinct = set()
        wins_with = 0
        for w, tr, ok in res:
            if tr is None:
                continue
            if tr:
                wins_with += 1
            # possible refund pairs within this window (DEVIATIONS 10): withdrawal then deposit,
            # same token, amount, route
            outs = [t for t in tr if t['direction'] == 'out']
            ins = [t for t in tr if t['direction'] == 'in']
            used = set()
            for o in outs:
                for i, d in enumerate(ins):
                    if i in used:
                        continue
                    if d['amount_raw'] == o['amount_raw'] and d['route'] == o['route'] and d['first'] > o['first']:
                        used.add(i)
                        refund_pairs += 2
                        break
            for t in tr:
                n_tr += 1
                routes[t['route']] += 1
                if t['edge']:
                    edge += 1
                if t['route'] == 'mixed':
                    mixed += 1
                if t['resolve']:
                    my_candidates.append((w['id'], t['tx']))
                distinct.add((t['tx'], t['token']))
        telem.append({
            'token': tok, 'period': period, 'windows': len(wins), 'completed': all_ok,
            'transfers': n_tr, 'distinct': len(distinct), 'windows_with_transfer': wins_with,
            'routes': dict(routes), 'edge_risk': edge, 'mixed': mixed,
            'near_side': routes.get('near-side', 0),
            'refund_pair_transfers': refund_pairs,
            'refund_share': (refund_pairs / n_tr) if n_tr else None,
        })

# ---- Resolution audit ----
RESOLVED = json.load(open(os.path.join(lib.DATA, 'nb', 'RESOLVED')))
resolve_entries = []
with open(os.path.join(lib.DATA, 'nb', 'resolve.jsonl')) as f:
    for line in f:
        if line.strip():
            resolve_entries.append(json.loads(line))

audit_entries = [e for e in resolve_entries if e.get('audit')]

def whole_read(tx, token):
    path = os.path.join(lib.DATA, 'nb', 'txns', tx + '.json')
    if not os.path.exists(path):
        return None
    body = json.load(open(path))['body']
    rows = body.get('data') or []
    legs = lib.intents_legs_whole(rows, token)
    if not legs:
        return {'empty': True}
    net = sum(l['delta'] for l in legs)
    first = min(l['ts'] for l in legs)
    route = lib.route_of(legs, token)
    return {'empty': False, 'first': first, 'net': net, 'route': route, 'n_legs': len(legs)}

audit_cmp = {'read': 0, 'not_read': [], 'differ': [], 'agree': 0, 'detail': []}
for e in audit_entries:
    tx = e['tx']
    wids = e.get('windows', [])
    # token from the window
    tok = None
    for wid in wids:
        if wid in T.BYID:
            tok = T.BYID[wid]['token']
            break
    # window view transfer for this (tx, token)
    wv = None
    for wid in wids:
        w = T.BYID.get(wid)
        if not w:
            continue
        for t in lib.window_transfers(w):
            if t['tx'] == tx and t['token'] == tok:
                wv = t
                break
        if wv:
            break
    wr = whole_read(tx, tok)
    if wr is None:
        audit_cmp['not_read'].append({'tx': tx, 'reason': 'no txns file', 'token': tok})
        continue
    audit_cmp['read'] += 1
    if wr.get('empty'):
        audit_cmp['detail'].append({'tx': tx, 'token': tok, 'note': 'whole read has no intents leg'})
        continue
    if wv is None:
        audit_cmp['detail'].append({'tx': tx, 'token': tok, 'note': 'no window-view transfer found'})
        continue
    d_first = wv['first'] != wr['first']
    d_net = wv['net'] != wr['net']
    d_route = wv['route'] != wr['route']
    rec = {'tx': tx, 'token': tok, 'wv_first': wv['first'], 'wr_first': wr['first'],
           'wv_net': wv['net'], 'wr_net': wr['net'], 'wv_route': wv['route'], 'wr_route': wr['route'],
           'differ_first': d_first, 'differ_net': d_net, 'differ_route': d_route}
    if d_first or d_net or d_route:
        audit_cmp['differ'].append(rec)
    else:
        audit_cmp['agree'] += 1
    audit_cmp['detail'].append(rec)

out = {
    'flow_telemetry': telem,
    'my_candidate_count': len(my_candidates),
    'my_candidates': my_candidates,
    'RESOLVED': RESOLVED,
    'audit': {
        'n_audit_entries': len(audit_entries),
        'read': audit_cmp['read'],
        'not_read': audit_cmp['not_read'],
        'agree': audit_cmp['agree'],
        'differ': audit_cmp['differ'],
        'detail': audit_cmp['detail'],
    },
}
json.dump(out, open('d2_transfers.json', 'w'), indent=1)

print('My resolution candidates (edge/span>5s):', len(my_candidates), '| RESOLVED candidates:', RESOLVED['candidates'])
print('Audit entries:', len(audit_entries), 'read:', audit_cmp['read'], 'not_read:', len(audit_cmp['not_read']),
      'agree:', audit_cmp['agree'], 'differ:', len(audit_cmp['differ']))
if audit_cmp['not_read']:
    print('  not read:', audit_cmp['not_read'])
if audit_cmp['differ']:
    for r in audit_cmp['differ']:
        print('  DIFFER:', r)
print('--- flow telemetry ---')
for t in telem:
    print(f"{t['token'][:20]:22} {t['period']:8} win={t['windows']:2} tr={t['transfers']:3} dist={t['distinct']:3} "
          f"routes={t['routes']} edge={t['edge_risk']} mixed={t['mixed']} refund={t['refund_pair_transfers']}")
