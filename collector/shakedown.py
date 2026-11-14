"""Shakedown (uncounted): hand-picked windows outside the frozen list, run through the real
sampler with the shared ledger, then checked.

  make  <out instants-shakedown.json>
  check <instants-shakedown.json> <data_dir>
"""
import json, os, sys, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'analysis'))
import design, sampler, flows  # noqa: E402


def w(id_, family, s, e, **kw):
    d = {'id': id_, 'key': f'shakedown:{id_}', 'family': family, 'tier': 1, 'order': 0, 'stratum': 'shakedown',
         'i': 0, 'segments_ns': [[design.ns(design.ts(s)), design.ns(design.ts(e))]], 'cost_plan': 1.0}
    d.update(kw)
    return d


def make(out):
    ws = [
        w('sd-sign-busy', 'sign', '2026-11-08T12:00:00Z', '2026-11-08T12:18:00Z'),
        w('sd-sign-zero', 'sign', '2024-08-20T03:00:00Z', '2024-08-20T03:01:00Z'),
        w('sd-flow-sol', 'flow', '2026-11-08T12:00:00Z', '2026-11-08T12:04:00Z', token='sol.omft.near', guard_s=30.0),
        w('sd-flow-eth', 'flow', '2026-11-08T12:00:00Z', '2026-11-08T12:04:00Z', token='eth.omft.near', guard_s=30.0),
        w('sd-census', 'census', '2026-11-08T12:00:00Z', '2026-11-08T12:03:00Z'),
        {'id': 'sd-index', 'key': 'shakedown:sd-index', 'family': 'index', 'tier': 1, 'order': 0, 'stratum': 'shakedown',
         'i': 0, 'segments_ns': [], 'instant_ns': design.ns(design.ts('2026-11-08T12:00:00Z')), 'cost_plan': 1.0},
    ]
    for k, x in enumerate(ws):
        x['order'] = k
    json.dump({'meta': {'T0_utc': 'shakedown', 'note': 'uncounted shakedown windows, not in the frozen list'},
               'windows': ws}, open(out, 'w'), indent=1)


def check(inst_path, d):
    inst = json.load(open(inst_path))
    S = sampler.Sampler(inst, d, client=None, log=lambda m: None)
    res = {}
    for x in inst['windows']:
        pages = S.pages_of(x['id'], 0)
        r = {'pages': len(pages), 'http': [p['http'] for p in pages], 'rows': sum(p['n_rows'] for p in pages),
             'done': bool(pages and pages[-1]['done'])}
        rows = [row for p in pages for row in p['rows']]
        if rows:
            r['row_keys'] = sorted(rows[0].keys())
        # continuity between pages: each page's newest row is not newer than the previous page's oldest,
        # and no row identity repeats
        ids = [flows.row_id(row) if x['family'] in ('flow', 'census', 'migration') else row.get('receipt_id') for row in rows]
        r['duplicate_rows'] = len(ids) - len(set(map(str, ids)))
        cont = []
        for a, b in zip(pages, pages[1:]):
            if a['rows'] and b['rows']:
                cont.append(min(flows.row_ts(q) for q in a['rows']) >= max(flows.row_ts(q) for q in b['rows']))
        r['pages_continuous'] = all(cont) if cont else None
        if x['family'] == 'sign':
            s, e = x['segments_ns'][0]
            inside = [row for row in rows if s <= flows.row_ts(row) < e]
            r['in_window'] = len(inside)
            r['oldest_fetched_before_start'] = bool(rows) and min(flows.row_ts(q) for q in rows) < s
            r['predecessors'] = {}
            for q in inside:
                k = q.get('predecessor_account_id')
                r['predecessors'][k] = r['predecessors'].get(k, 0) + 1
        if x['family'] == 'flow':
            s, e = x['segments_ns'][0]
            tr, c = flows.transfers(rows, x['token'], s, e, hi_ns=e + int(30e9))
            r['transfers'] = len(tr)
            r['counters'] = c
            r['routes'] = {}
            for t in tr:
                k = f"{t['route']}/{t['direction']}"
                r['routes'][k] = r['routes'].get(k, 0) + 1
            r['example'] = tr[:3]
        if x['family'] == 'census':
            toks, off = flows.census_tokens(rows)
            r['tokens'] = toks
            r['rows_not_involving_intents'] = off
        if x['family'] == 'index':
            r['example'] = rows[:2]
        res[x['id']] = r
    print(json.dumps(res, indent=1, default=str))


if __name__ == '__main__':
    if sys.argv[1] == 'make':
        make(sys.argv[2])
    else:
        check(sys.argv[2], sys.argv[3])
