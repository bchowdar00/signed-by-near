"""The destination audit (METHOD §6.7, DEVIATIONS item 8), by the procedure POST-FREEZE.md fixes.

  python3 -I publish/dest_audit.py <out_dir> <audit_dir>

The picks are the frozen ones: <out_dir>/published/results.json → dest_audit_selection, 10 BITCOIN rows
whose requesting account ends in `.bridge.near` and 10 ZCASH rows, drawn with the seed stream
"dest-audit" from the signature-index months that completed. This script only looks them up. Each pick
gets one GET on a public explorer's keyless API, never NearBlocks:
  BITCOIN  https://mempool.space/api/tx/<dest_txn>                      (page: mempool.space/tx/<dest_txn>)
  ZCASH    https://api.blockchair.com/zcash/dashboards/transaction/<dest_txn>
                                                         (page: blockchair.com/zcash/transaction/<dest_txn>)
For each it records: found; confirmed, and the block time if confirmed; whether an input was spent
from the row's dest_address, the address the signer's key controls on that chain; the total of the
outputs to any other address (satoshis or zatoshis; for Zcash, transparent outputs only; change sent to
another address is included, and the index row has no amount to compare it with); the page URL; and
the sha256 of the raw response, which is saved. There are no replacement picks. Calls are 6 s apart.
A network error, HTTP 429 or a 5xx gets one retry after 60 s. Any failure is recorded on its pick, and
the audit goes on. A destination id that is not a 64-character hex id is not looked up. It computes
nothing else.

Writes <audit_dir>/dest-audit.json (publish/combine.py carries it into the write-up), dest-audit.md and
the raw responses under <audit_dir>/raw/.
"""
import datetime, hashlib, http.client, json, os, re, sys, time, urllib.error, urllib.request

EXPLORERS = {
    'BITCOIN': ('https://mempool.space/api/tx/{}', 'https://mempool.space/tx/{}', 'sat'),
    'ZCASH': ('https://api.blockchair.com/zcash/dashboards/transaction/{}',
              'https://blockchair.com/zcash/transaction/{}', 'zat'),
}
UA = 'near-thesis-dest-audit/1 (keyless, one call per pick)'
GAP_S = 6.0
RETRY_S = 60.0
TXID = re.compile(r'[0-9a-fA-F]{64}')
NET_ERRORS = (urllib.error.URLError, OSError, http.client.HTTPException, ValueError)


def http_get(url, timeout=40):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _utc_s(t):
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ') if t else None


def _json(body):
    try:
        return json.loads(body)
    except (ValueError, TypeError):
        raise ValueError('the response is not JSON')


def parse_btc(status, body, addr):
    if status == 404:
        return {'found': False}
    d = _json(body)
    if not isinstance(d, dict):
        raise ValueError('the response is not a transaction')
    ins = [(v.get('prevout') or {}).get('scriptpubkey_address') for v in d.get('vin', [])]
    outs = [(v.get('scriptpubkey_address'), v.get('value') or 0) for v in d.get('vout', [])]
    st = d.get('status') or {}
    conf = bool(st.get('confirmed'))
    return {'found': True, 'confirmed': conf, 'block_time_utc': _utc_s(st.get('block_time')) if conf else None,
            'from_signer_address': (addr in ins) if addr else None,
            'to_other_addresses': sum(v for a, v in outs if a != addr)}


def parse_zec(status, body, addr):
    d = _json(body)
    data = d.get('data') if isinstance(d, dict) else None
    if data == [] or data == {}:
        return {'found': False}
    t = list(data.values())[0] if isinstance(data, dict) and len(data) == 1 else None
    if not isinstance(t, dict):
        raise ValueError('the response holds no transaction record')
    tr = t.get('transaction') or {}
    ins = [i.get('recipient') for i in t.get('inputs', [])]
    outs = [(o.get('recipient'), o.get('value') or 0) for o in t.get('outputs', [])]
    conf = tr.get('block_id') not in (None, -1)
    bt = tr.get('time')
    return {'found': True, 'confirmed': conf, 'block_time_utc': bt.replace(' ', 'T') + 'Z' if (bt and conf) else None,
            'from_signer_address': (addr in ins) if addr else None,
            'to_other_addresses': sum(v for a, v in outs if a != addr)}


PARSE = {'BITCOIN': parse_btc, 'ZCASH': parse_zec}


def _retry(status):
    return status == 429 or 500 <= status < 600


def audit(selection, raw_dir, get=http_get, sleep=time.sleep):
    os.makedirs(raw_dir, exist_ok=True)
    rows, first = [], True
    for key, chain in (('bitcoin', 'BITCOIN'), ('zcash', 'ZCASH')):
        api, page, unit = EXPLORERS[chain]
        for p in selection.get(key, []):
            txid = p.get('dest_txn')
            row = {'chain': chain, 'receipt_id': p.get('receipt_id'), 'account_id': p.get('account_id'),
                   'dest_txn': txid, 'dest_address': p.get('dest_address'), 'unit': unit, 'url': None}
            rows.append(row)
            if not txid:
                row.update(found=None, note='no destination transaction in the index row')
                continue
            if not (isinstance(txid, str) and TXID.fullmatch(txid)):
                row.update(found=None, note='the destination id is not a 64-character hex id, so it was not looked up')
                continue
            row['url'] = page.format(txid)
            if not first:
                sleep(GAP_S)
            first = False
            status, body, err = None, None, None
            for attempt in (0, 1):
                try:
                    status, body = get(api.format(txid))
                    err = None
                except NET_ERRORS as e:
                    status, body, err = None, None, f'{type(e).__name__}: {e}'
                if attempt == 0 and (err or _retry(status)):
                    sleep(RETRY_S)
                    continue
                break
            row['http'] = status
            if err:
                row.update(found=None, error=err, response_sha256=None)
                continue
            with open(os.path.join(raw_dir, f'{chain.lower()}-{txid}.json'), 'wb') as f:
                f.write(body or b'')
            row['response_sha256'] = hashlib.sha256(body or b'').hexdigest()
            if status != 200 and not (chain == 'BITCOIN' and status == 404):
                row.update(found=None)
                continue
            try:
                row.update(PARSE[chain](status, body, p.get('dest_address')))
            except (ValueError, AttributeError, TypeError, KeyError) as e:
                row.update(found=None, error=str(e))
    summary = {}
    for chain in EXPLORERS:
        rs = [r for r in rows if r['chain'] == chain]
        summary[chain] = {'picked': len(rs), 'found': sum(1 for r in rs if r.get('found') is True),
                          'not_found': sum(1 for r in rs if r.get('found') is False),
                          'unknown': sum(1 for r in rs if r.get('found') is None),
                          'confirmed': sum(1 for r in rs if r.get('confirmed') is True),
                          'from_signer_address': sum(1 for r in rs if r.get('from_signer_address') is True)}
    return {'rows': rows, 'summary': summary, 'available': selection.get('available'),
            'not_completed_months': selection.get('not_completed_months', [])}


def table(a):
    L = ['| chain | NEAR receipt | destination transaction | found | confirmed (UTC) | from the signer\'s address '
         '| to other addresses |', '|---|---|---|---|---|---|---|']
    yn = {True: 'yes', False: 'no', None: '–'}
    for r in a['rows']:
        tx = f"[{r['dest_txn'][:12]}…]({r['url']})" if r.get('url') else (f"`{r['dest_txn']}`" if r.get('dest_txn') else '–')
        if r.get('found'):
            conf = (r.get('block_time_utc') or 'yes') if r.get('confirmed') else 'no'
            L.append(f"| {r['chain']} | {r['receipt_id']} | {tx} | yes | {conf} | {yn[r.get('from_signer_address')]} | "
                     f"{r['to_other_addresses']:,} {r['unit']} |")
        else:
            why = yn[r.get('found')]
            if r.get('found') is None:
                why = 'error' if r.get('error') else (f"http {r['http']}" if r.get('http') else 'not looked up')
            L.append(f"| {r['chain']} | {r['receipt_id']} | {tx} | {why} | – | – | – |")
    nc = a.get('not_completed_months') or []
    L += ['', 'Picks drawn from the completed signature-index months'
          + (f"; not completed at the deadline: {', '.join(nc)}." if nc else '.')]
    notes = [f"- {r['receipt_id']}: {r.get('error') or r.get('note')}" for r in a['rows'] if r.get('error') or r.get('note')]
    if notes:
        L += ['', 'Lookups with no answer:'] + notes
    return '\n'.join(L) + '\n'


def main(out_dir, audit_dir, get=http_get, sleep=time.sleep):
    with open(os.path.join(out_dir, 'published', 'results.json')) as f:
        sel = json.load(f)['dest_audit_selection']
    a = audit(sel, os.path.join(audit_dir, 'raw'), get=get, sleep=sleep)
    a['run_utc'] = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    with open(os.path.join(audit_dir, 'dest-audit.json'), 'w') as f:
        json.dump(a, f, indent=1, sort_keys=True)
    with open(os.path.join(audit_dir, 'dest-audit.md'), 'w') as f:
        f.write(table(a))
    print(json.dumps(a['summary']))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:3])
