"""Synthetic collector output for the frozen design, for end-to-end tests of the analysis without
any counted row. It writes, for every window of instants.json, NearBlocks-shaped pages generated from
a known synthetic population (one page per segment, done), plus neardata blocks and RPC rows, into a
fresh directory. Nothing here touches the real data directory or the network.

  python3 -I tests/simulate.py <instants.json> <out_dir> [--seed N] [--incomplete K]

Population (per second rates, routes and callers) is set in POP below; truth() gives the true
values the tests compare against.
"""
import json, math, os, random, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'collector'))
import design  # noqa: E402

DAY = 86400.0
# per-token: (unused rate), P(Omni), P(unknown), mean units, decimals; window rates come from the frozen design
POP = {
    'nbtc.bridge.near': (40, 0.97, 0.03, 0.05, 8), 'btc.omft.near': (1.2, 0.0, 0.0, 0.08, 8),
    'zec.omft.near': (60, 0.9, 0.02, 5.0, 8), 'nzec.bridge.near': (0.6, 1.0, 0.0, 2.0, 8),
    'sol.omft.near': (300, 0.95, 0.01, 3.0, 9),
    'sol-5ce3bf3a31af18be40ba30f721101b4341690186.omft.near': (150, 0.9, 0.0, 400.0, 6),
    'sol-c800a4bd850783ccb82c2b2c7e84175443606352.omft.near': (40, 0.9, 0.0, 300.0, 6),
    'eth.omft.near': (300, 0.0, 0.0, 0.5, 18),
    'eth-0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48.omft.near': (180, 0.0, 0.0, 900.0, 6),
    'eth-0xdac17f958d2ee523a2206206994597c13d831ec7.omft.near': (270, 0.0, 0.0, 900.0, 6),
    'arb-0xaf88d065e77c8cc2239327c5edb3a432268e5831.omft.near': (95, 0.0, 0.0, 300.0, 6),
    'arb-0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9.omft.near': (22, 0.0, 0.0, 300.0, 6),
    'base-0x833589fcd6edb6e08f4c7c32d4f71b54bda02913.omft.near': (240, 0.0, 0.0, 200.0, 6),
    'tron-d28a265909efecdcee7c5028585214ea0b96f015.omft.near': (230, 0.0, 0.0, 700.0, 6),
    'xrp.omft.near': (98, 0.0, 0.0, 400.0, 6),
}
ROWS_PER_TRANSFER = 1.0  # synthetic transfers are mostly one row; rates follow the frozen planning rates
CALLERS = [('ping-account.near', 0.02), ('fast-auth.near', 0.55), ('omni.bridge.near', 0.15),
           ('7eda04920f22ba6a2b9f2573fd9a6f6f1946ff9f.aurora', 0.10), ('x.meteor-vaults.near', 0.03),
           ('btc-connector.bridge.near', 0.05), ('somebody.near', 0.10)]
FA_SIGNERS = [('sweat-relayer.near', 0.8), ('rathrelayer.near', 0.2)]
CENSUS_TOKENS = [('sol.omft.near', 0.5), ('nbtc.bridge.near', 0.2), ('zec.omft.near', 0.2),
                 ('sol-5ce3bf3a31af18be40ba30f721101b4341690186.omft.near', 0.1)]


def _w(path, text):
    with open(path, 'w') as f:
        f.write(text)


def _j(path, obj, **kw):
    with open(path, 'w') as f:
        json.dump(obj, f, **kw)


def pick(rng, pairs):
    x, acc = rng.random(), 0.0
    for k, p in pairs:
        acc += p
        if x < acc:
            return k
    return pairs[-1][0]


def poisson_times(rng, lo, hi, per_day):
    lam = per_day / DAY * 1e-9  # per ns
    out, t = [], lo
    if lam <= 0:
        return out
    while True:
        t += int(rng.expovariate(lam)) + 1
        if t >= hi:
            return out
        out.append(t)


def ft_rows(rng, tok, t, uid):
    rate, p_omni, p_unk, mean, dec = POP[tok]
    amt = max(1, int(rng.expovariate(1.0 / mean) * 10 ** dec))
    out = rng.random() < 0.5
    r = rng.random()
    route = 'OMNI' if r < p_omni else ('UNKNOWN' if r < p_omni + p_unk else 'POA')
    tx = f'tx{uid}'
    base = {'contract_account_id': tok, 'block_timestamp': str(t), 'block': {'block_timestamp': str(t)},
            'transaction_hash': tx, 'meta': {'contract': tok, 'decimals': dec}}
    rows = []
    if route == 'OMNI' or (route == 'UNKNOWN' and not tok.endswith('.omft.near')):
        if out:
            rows.append(dict(base, affected_account_id='omni.bridge.near', involved_account_id='intents.near',
                             cause='TRANSFER', delta_amount=str(amt), receipt_id=f'r{uid}a', event_index=0))
        else:
            rows.append(dict(base, affected_account_id='intents.near', involved_account_id='omni.bridge.near',
                             cause='TRANSFER', delta_amount=str(amt), receipt_id=f'r{uid}a', event_index=0))
        if route == 'UNKNOWN':
            rows.append(dict(base, affected_account_id='intents.near', involved_account_id='mystery.near',
                             cause='MINT', delta_amount='1', receipt_id=f'r{uid}c', event_index=2))
    elif route == 'UNKNOWN':  # mixed Omni and POA legs in one transaction
        rows.append(dict(base, affected_account_id='intents.near', involved_account_id='omni.bridge.near',
                         cause='TRANSFER', delta_amount=str(amt), receipt_id=f'r{uid}a', event_index=0))
        rows.append(dict(base, affected_account_id='intents.near', involved_account_id=None,
                         cause='MINT', delta_amount='1', receipt_id=f'r{uid}b', event_index=1))
    else:
        if out:
            rows.append(dict(base, affected_account_id='intents.near', involved_account_id=None, cause='BURN',
                             delta_amount=str(-amt), receipt_id=f'r{uid}a', event_index=0))
        else:
            rows.append(dict(base, affected_account_id='intents.near', involved_account_id='omft.near',
                             cause='TRANSFER', delta_amount=str(amt), receipt_id=f'r{uid}a', event_index=0))
    return rows


def write_page(d, wid, seg, rows, lo, hi):
    os.makedirs(os.path.join(d, 'nb', 'pages', wid), exist_ok=True)
    rows = sorted(rows, key=lambda r: -int(r.get('block_timestamp') or r['block']['block_timestamp']))
    with open(os.path.join(d, 'nb', 'pages', wid, f'{seg:02d}-0.json'), 'w') as f:
        json.dump({'window': wid, 'seg': seg, 'page': 0, 'path': 'synthetic', 'utc': 'synthetic', 'http': 200,
                   'n_rows': len(rows), 'next': None, 'done': True, 'lo_ns': lo, 'hi_ns': hi, 'rows': rows}, f)


def simulate(instants_path, out, seed=1, incomplete=0):
    rng = random.Random(seed)
    with open(instants_path) as f:
        I = json.load(f)
    os.makedirs(os.path.join(out, 'nb'), exist_ok=True)
    status = open(os.path.join(out, 'nb', 'windows.jsonl'), 'w')
    uid = 0
    skip = set(w['id'] for w in rng.sample(I['windows'], incomplete)) if incomplete else set()
    for w in I['windows']:
        if w['id'] in skip:
            status.write(json.dumps({'id': w['id'], 'event': 'not_completed'}) + '\n')
            continue
        fam = w['family']
        if fam == 'index':
            rows = [{'account_id': rng.choice(['omni-relayer.bridge.near', 'btc-connector.bridge.near', 'x.near']),
                     'dest_chain': rng.choice(['BITCOIN', 'ZCASH', 'ETHEREUM']), 'dest_txn': f'd{uid + i}',
                     'receipt_id': f'ix{uid + i}', 'block_timestamp': str(int(w['instant_ns']) - i)} for i in range(25)]
            uid += 25
            write_page(out, w['id'], 0, rows, None, int(w['instant_ns']))
        else:
            g = int(round(w.get('guard_s', 0.0) * 1e9))
            for seg, (s, e) in enumerate(w['segments_ns']):
                lo, hi = int(s) - g, int(e) + g
                rows = []
                if fam == 'sign':
                    for t in poisson_times(rng, lo, hi, w['rate_plan_per_day']):
                        uid += 1
                        rows.append({'actions': [{'action': 'FUNCTION_CALL', 'method': 'sign'}],
                                     'actions_agg': {'deposit': '1'}, 'block': {'block_timestamp': str(t)},
                                     'outcome': {'status': rng.random() > 0.01}, 'predecessor_account_id': pick(rng, CALLERS),
                                     'receipt_id': f's{uid}', 'transaction_hash': f'st{uid}', 'receiver_account_id': 'v1.signer'})
                elif fam in ('flow', 'migration'):
                    for t in poisson_times(rng, lo, hi, w['rate_plan_per_day'] / ROWS_PER_TRANSFER):
                        uid += 1
                        rows += ft_rows(rng, w['token'], t, uid)
                elif fam == 'census':
                    for t in poisson_times(rng, lo, hi, w['rate_plan_per_day']):
                        uid += 1
                        tok = pick(rng, CENSUS_TOKENS)
                        rows.append({'affected_account_id': 'omni.bridge.near', 'involved_account_id': 'intents.near',
                                     'cause': 'TRANSFER', 'contract_account_id': tok, 'delta_amount': '5',
                                     'block_timestamp': str(t), 'block': {'block_timestamp': str(t)},
                                     'receipt_id': f'c{uid}', 'event_index': 0, 'transaction_hash': f'ct{uid}'})
                write_page(out, w['id'], seg, rows, lo, hi)
        status.write(json.dumps({'id': w['id'], 'event': 'completed'}) + '\n')
    status.close()
    _w(os.path.join(out, 'nb', 'resolve.jsonl'), '')
    _j(os.path.join(out, 'nb', 'RESOLVED'), {'synthetic': True})
    # neardata
    fz = os.path.dirname(os.path.abspath(instants_path))
    with open(os.path.join(fz, 'nd_plan.json')) as f:
        plan = json.load(f)
    os.makedirs(os.path.join(out, 'nd'), exist_ok=True)
    with open(os.path.join(out, 'nd', 'blocks.jsonl'), 'w') as f:
        for m, hs in sorted(plan['sample'].items()):
            for h in hs:
                calls = []
                for k in range(rng.choice([0, 0, 0, 1, 1, 2])):
                    pred = pick(rng, CALLERS)
                    signer = pick(rng, FA_SIGNERS) if pred == 'fast-auth.near' else pred
                    if pred == 'fast-auth.near':
                        req = {'path': f'jwt#https://x#{k}', 'payload_v2': {'Eddsa': '00' * 32}, 'domain_id': 1}
                    else:
                        req = {'path': 'p', 'payload_v2': {'Ecdsa': '11' * 32}, 'domain_id': 0}
                    calls.append({'height': h, 'ts_ns': 0, 'receipt_id': f'n{h}-{k}', 'method': 'sign',
                                  'predecessor': pred, 'signer': signer, 'deposit_yocto': '1',
                                  'status': {'SuccessValue': ''}, 'args': {'request': req}, 'execution_block_hash': 'x'})
                f.write(json.dumps({'part': f'sample:{m}', 'height': h, 'http': 200, 'present': True, 'ts_ns': 0,
                                    'calls': calls}) + '\n')
        a, b = plan['contiguous']
        for h in range(a, b):
            f.write(json.dumps({'part': 'contiguous', 'height': h, 'http': 200, 'present': True, 'ts_ns': h * 10 ** 9,
                                'calls': []}) + '\n')
    _w(os.path.join(out, 'nd', 'DONE'), 'synthetic\n')
    # rpc
    os.makedirs(os.path.join(out, 'rpc'), exist_ok=True)
    with open(os.path.join(out, 'rpc', 'supply.jsonl'), 'w') as f:
        for i, pt in enumerate(sorted(plan['bounds'])):
            for tok, v in (('nbtc.bridge.near', 10 ** 8 * (i + 1)), ('btc.omft.near', 10 ** 8 * 2)):
                f.write(json.dumps({'point': pt, 'height': plan['bounds'][pt]['height'], 'ts_ns': 0, 'token': tok,
                                    'status': 'value', 'total_supply': str(v), 'ok': True, 'detail': None}) + '\n')
    sys.path.insert(0, os.path.join(ROOT, 'analysis'))
    import hsp007  # noqa: E402
    accts = sorted(set(hsp007.NODE_ACCOUNTS.values()))
    with open(os.path.join(out, 'rpc', 'operators.jsonl'), 'w') as f:
        for pt in sorted(plan['bounds']):
            if pt != 'T0' and pt < '2026-04':
                continue
            b = plan['bounds'][pt]
            if pt == '2026-06':  # one failed read, as rpc.py writes it
                row = {'point': pt, 'height': b['height'], 'ts_ns': b['ts_ns'], 'status': 'fail', 'ok': False}
            else:
                row = {'point': pt, 'height': b['height'], 'ts_ns': b['ts_ns'], 'status': 'value', 'ok': True,
                       'threshold': 11, 'participants': accts[:16], 'state_kind': 'Running'}
            f.write(json.dumps(row, sort_keys=True) + '\n')
    _w(os.path.join(out, 'rpc', 'DONE'), 'synthetic\n')
    truth = {'p_omni': {t: v[1] for t, v in POP.items()}, 'p_unknown': {t: v[2] for t, v in POP.items()},
             'sign_rate_by_month': {}}
    for w in I['windows']:
        if w['family'] == 'sign':
            truth['sign_rate_by_month'].setdefault(w['month'], {})[w['stratum']] = (w['rate_plan_per_day'], w['D_s'])
    r = {m: sum(a * d for a, d in v.values()) / sum(d for _, d in v.values()) for m, v in truth['sign_rate_by_month'].items()}
    truth['sign_rate_by_month'] = r
    _j(os.path.join(out, 'truth.json'), truth, indent=1)
    return {'windows': len(I['windows']), 'skipped': len(skip)}


if __name__ == '__main__':
    args = sys.argv[1:]
    seed = int(args[args.index('--seed') + 1]) if '--seed' in args else 1
    inc = int(args[args.index('--incomplete') + 1]) if '--incomplete' in args else 0
    print(simulate(args[0], args[1], seed, inc))
