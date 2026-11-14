"""Archival RPC views (METHOD §6.9 and M10b), keyless FastNEAR archival RPC.

  run <nd_plan.json> <data_dir>
    - ft_total_supply of nbtc.bridge.near (Omni) and btc.omft.near (POA) at every month-start
      height from 2025-01 and at T0 (M10b, BTC custody by route; M2 context);
    - v1.signer `state` at every month-start height from 2026-04 (the set at the end of each
      service month from March 2026) and at T0 (M8 operators).
Every raw response is kept in rpc/raw/; derived rows go in rpc/supply.jsonl and rpc/operators.jsonl.

A view at a fixed height is deterministic, so some errors are final answers, not failures:
  - "absent": the account does not exist at that height, or has no contract code (nbtc.bridge.near
    did not exist at height 136,000,000, 2024-12-28). M10b counts an absent token's supply as 0;
  - "contract_error": the contract ran and failed (for example MethodNotFound);
  - "decode_error": the contract returned bytes that are not JSON.
Only "fail" (no response, or a server-side error such as a timeout or an unknown block) is retried:
the run exits non-zero and run.sh restarts it. DONE is written only when no view failed.
"""
import base64, json, os, sys, time, urllib.error, urllib.request

RPC = 'https://archival-rpc.mainnet.fastnear.com'
UA = 'research-readonly (NEAR hackathon thesis entry; keyless)'
FINAL_ABSENT = ('UNKNOWN_ACCOUNT', 'NO_CONTRACT_CODE')


def call(method, params, tries=6):
    body = json.dumps({'jsonrpc': '2.0', 'id': 'r', 'method': method, 'params': params}).encode()
    back = 3.0
    for _ in range(tries):
        time.sleep(0.5)
        try:
            req = urllib.request.Request(RPC, data=body, headers={'User-Agent': UA, 'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(back)
            back = min(back * 2, 120)
    return None


def view(contract, fn, height, args=b'{}'):
    return call('query', {'request_type': 'call_function', 'block_id': height, 'account_id': contract,
                          'method_name': fn, 'args_base64': base64.b64encode(args).decode()})


def classify(r):
    """(status, value) for a call_function response; status 'fail' is the only retryable one."""
    if not isinstance(r, dict):
        return 'fail', None
    if 'error' in r:
        err = r['error'] if isinstance(r['error'], dict) else {}
        cause = (err.get('cause') or {}).get('name')
        if cause in FINAL_ABSENT:
            return 'absent', None
        if cause == 'CONTRACT_EXECUTION_ERROR':
            return 'contract_error', err.get('data')
        return 'fail', None
    res = r.get('result')
    if not isinstance(res, dict):
        return 'fail', None
    if 'error' in res:
        return 'contract_error', res['error']
    if 'result' not in res:
        return 'fail', None
    try:
        return 'value', json.loads(bytes(res['result']).decode())
    except Exception:
        return 'decode_error', None


def keep_raw(d, contract, fn, h, r):
    with open(os.path.join(d, 'raw', f'{contract}-{fn}-{h}.json'), 'w') as f:
        json.dump(r, f)


def operators_row(label, b, status, st):
    row = {'point': label, 'height': b['height'], 'ts_ns': b['ts_ns'], 'status': status, 'ok': status != 'fail'}
    if status == 'value':
        try:
            run_ = st.get('Running') or st.get('Resharing') or {}
            params = run_.get('parameters') or {}
            parts = params.get('participants') or {}
            plist = parts.get('participants') or []
            row['threshold'] = params.get('threshold')
            row['participants'] = sorted(x[0] if isinstance(x, list) else x.get('account_id') for x in plist)
            row['state_kind'] = next(iter(st.keys()))
        except Exception as e:
            row['parse_error'] = repr(e)
    return row


def run(plan_path, data_dir, viewer=view):
    with open(plan_path) as f:
        p = json.load(f)
    d = os.path.join(data_dir, 'rpc')
    os.makedirs(os.path.join(d, 'raw'), exist_ok=True)
    pts = sorted((k, v) for k, v in p['bounds'].items() if k != 'T0') + [('T0', p['bounds']['T0'])]
    bad = 0
    with open(os.path.join(d, 'supply.jsonl'), 'w') as fs, open(os.path.join(d, 'operators.jsonl'), 'w') as fo:
        for label, b in pts:
            h = b['height']
            for tok in ('nbtc.bridge.near', 'btc.omft.near'):
                r = viewer(tok, 'ft_total_supply', h)
                keep_raw(d, tok, 'ft_total_supply', h, r)
                status, v = classify(r)
                bad += status == 'fail'
                fs.write(json.dumps({'point': label, 'height': h, 'ts_ns': b['ts_ns'], 'token': tok, 'status': status,
                                     'total_supply': v if status == 'value' else None,
                                     'detail': v if status == 'contract_error' else None,
                                     'ok': status != 'fail'}, sort_keys=True) + '\n')
            if label == 'T0' or label >= '2026-04':
                r = viewer('v1.signer', 'state', h)
                keep_raw(d, 'v1.signer', 'state', h, r)
                status, st = classify(r)
                bad += status == 'fail'
                fo.write(json.dumps(operators_row(label, b, status, st), sort_keys=True) + '\n')
            print(label, h, flush=True)
    if bad:
        raise SystemExit(f'{bad} views failed; rerun to retry (the files are rewritten)')
    with open(os.path.join(d, 'DONE'), 'w') as f:
        f.write('done\n')


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'run':
        run(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
