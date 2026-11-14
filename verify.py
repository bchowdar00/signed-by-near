"""Re-pull and check (METHOD-b §9). Keyless; needs only Python 3.

  python3 -I verify.py manifest <data_dir>                       writes <data_dir>/PAGES-MANIFEST.json
  python3 -I verify.py check    <instants.json> <data_dir> [--n 20 | --all | --ids id1,id2] [--ledger <ledger.jsonl>]

`manifest` hashes every published page file (SHA-256) after sampling.

`check` does two things:
  1. offline: every page file in <data_dir>/nb/pages matches PAGES-MANIFEST.json, if present;
  2. online: it re-pulls windows from NearBlocks' public API with the same requests the sampler
     made (same before_ts, then the API's cursor) into a fresh folder, with its own credit ledger
     under the free plan's limits (10.5 s between calls, 6 a minute, 300 a day), and compares,
     per window and segment, the set of rows inside the fetched range and their key fields.
By default it checks a seeded sample of 20 windows (about 25 credits, a few minutes). --all
re-pulls every window, which takes about two days at the free plan's pace.
"""
import hashlib, json, os, random, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'collector'))
sys.path.insert(0, os.path.join(HERE, 'analysis'))
import nb, sampler, flows  # noqa: E402

KEY_FIELDS = ('receipt_id', 'event_index', 'affected_account_id', 'involved_account_id', 'cause', 'delta_amount',
              'block_timestamp', 'transaction_hash', 'predecessor_account_id', 'contract_account_id', 'dest_txn')


def page_files(data_dir):
    root = os.path.join(data_dir, 'nb', 'pages')
    for dp, _, fs in os.walk(root):
        for f in sorted(fs):
            if f.endswith('.json'):
                p = os.path.join(dp, f)
                yield os.path.relpath(p, data_dir), p


def sha256(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def manifest(data_dir):
    m = {rel: sha256(p) for rel, p in page_files(data_dir)}
    with open(os.path.join(data_dir, 'PAGES-MANIFEST.json'), 'w') as f:
        json.dump({'files': m, 'n': len(m)}, f, indent=1, sort_keys=True)
    print(f'{len(m)} page files hashed')


def rid(r, fam):
    return str(flows.row_id(r) if fam in ('flow', 'census', 'migration') else (r.get('receipt_id'), r.get('event_index'), r.get('dest_txn')))


def rows_in(pages, lo, hi):
    for p in pages:
        for r in p['rows']:
            t = sampler.row_ts(r)
            if (lo is None or t >= lo) and t < hi:
                yield r


def compare(w, pub, new):
    res = {'id': w['id'], 'key': w['key'], 'family': w['family'], 'segments': []}
    for seg, (lo, hi) in enumerate(sampler.seg_bounds(w)):
        a = {rid(r, w['family']): r for r in rows_in(pub.pages_of(w['id'], seg), lo, hi)}
        b = {rid(r, w['family']): r for r in rows_in(new.pages_of(w['id'], seg), lo, hi)}
        diff = [k for k in set(a) & set(b) if any(str(a[k].get(f)) != str(b[k].get(f)) for f in KEY_FIELDS)]
        res['segments'].append({'published': len(a), 'repulled': len(b), 'only_published': len(set(a) - set(b)),
                                'only_repulled': len(set(b) - set(a)), 'field_differences': len(diff)})
    res['match'] = all(s['only_published'] == 0 and s['only_repulled'] == 0 and s['field_differences'] == 0
                       for s in res['segments'])
    return res


def check(inst_path, data_dir, n=20, ids=None, ledger_path=None):
    with open(inst_path) as f:
        inst = json.load(f)
    ok = True
    mpath = os.path.join(data_dir, 'PAGES-MANIFEST.json')
    if os.path.exists(mpath):
        with open(mpath) as f:
            m = json.load(f)['files']
        bad = [rel for rel, p in page_files(data_dir) if m.get(rel) != sha256(p)]
        missing = [rel for rel in m if not os.path.exists(os.path.join(data_dir, rel))]
        print(json.dumps({'manifest_files': len(m), 'hash_mismatches': len(bad), 'missing': len(missing)}))
        ok = ok and not bad and not missing
    pub = sampler.Sampler(inst, data_dir, client=None, log=lambda m: None, do_resolve=False)
    done = [w for w in inst['windows'] if w['id'] in pub.completed]
    if ids:
        pick = [w for w in done if w['id'] in ids]
    elif n is None:
        pick = done
    else:
        pick = random.Random(20261115).sample(done, min(n, len(done)))
    tmp = tempfile.mkdtemp(prefix='verify-')
    # on a machine that already calls NearBlocks, pass that machine's ledger so the quota is shared
    led = nb.Ledger(ledger_path or os.path.join(tmp, 'ledger.jsonl'))
    client = nb.NB(led, 'verify: re-pull of published windows', log=lambda m: print(m, flush=True))
    new = sampler.Sampler({'meta': inst['meta'], 'windows': pick}, tmp, client, log=lambda m: print(m, flush=True),
                          do_resolve=False)
    new.run()
    results = [compare(w, pub, new) for w in pick]
    for r in results:
        print(json.dumps(r))
    ok = ok and all(r['match'] for r in results)
    print(f"windows re-pulled: {len(results)}; matching: {sum(r['match'] for r in results)}; folder: {tmp}")
    print('PASS' if ok else 'FAIL')
    return ok


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'manifest':
        manifest(sys.argv[2])
    elif len(sys.argv) >= 4 and sys.argv[1] == 'check':
        a = sys.argv
        n = None if '--all' in a else (int(a[a.index('--n') + 1]) if '--n' in a else 20)
        ids = set(a[a.index('--ids') + 1].split(',')) if '--ids' in a else None
        led = a[a.index('--ledger') + 1] if '--ledger' in a else None
        sys.exit(0 if check(a[2], a[3], n, ids, led) else 1)
    else:
        raise SystemExit(__doc__)
