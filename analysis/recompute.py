"""The one offline command (METHOD §9): recompute every published number from the rows.

  python3 -I analysis/recompute.py <instants.json> <data_dir> <out_dir>

Reads only local files: the frozen design (`instants.json`, with `tokens.json` and `nd_plan.json`
beside it), `registry/callers.json`, `inputs/reference.json`, `inputs/hsp007-ledger.json`, and the
collector's output under data_dir (nb/, nd/, rpc/). Writes results.json, tables.md and the two
charts. No network. results.json holds no clock time or machine path, so the same inputs give the
same bytes and its sha256 can be published and re-checked.
"""
import hashlib, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import core  # noqa: E402
import measures as M  # noqa: E402
import charts  # noqa: E402


def sha(p):
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def jl(p):
    with open(p) as f:
        return [json.loads(l) for l in f if l.strip()]


READ = ('nb/windows.jsonl', 'nb/RESOLVED', 'nb/resolve.jsonl', 'nb/pages/', 'nb/txns/', 'nd/blocks.jsonl', 'nd/DONE', 'rpc/supply.jsonl',
        'rpc/operators.jsonl', 'rpc/DONE')


def data_digest(data_dir):
    """sha256 over the sorted (relative path, sha256) of every collector file the analysis reads, and their count."""
    rows = []
    for base, _, files in os.walk(data_dir):
        for name in files:
            rel = os.path.relpath(os.path.join(base, name), data_dir).replace(os.sep, '/')
            if any(rel == r or (r.endswith('/') and rel.startswith(r)) for r in READ):
                rows.append(f'{rel} {sha(os.path.join(base, name))}')
    rows.sort()
    return {'files': len(rows), 'sha256': hashlib.sha256('\n'.join(rows).encode()).hexdigest()}


def load_inputs(instants_path, data_dir):
    fz = os.path.dirname(os.path.abspath(instants_path))
    instants_path = os.path.abspath(instants_path)
    paths = {'instants': instants_path, 'tokens': os.path.join(fz, 'tokens.json'),
             'nd_plan': os.path.join(fz, 'nd_plan.json'), 'registry': os.path.join(ROOT, 'registry', 'callers.json'),
             'reference': os.path.join(ROOT, 'inputs', 'reference.json'),
             'hsp007': os.path.join(ROOT, 'inputs', 'hsp007-ledger.json')}
    inp = {'paths': {k: os.path.relpath(v, ROOT) if v.startswith(ROOT) else os.path.basename(v) for k, v in paths.items()},
           'sha256': {k: sha(v) for k, v in paths.items() if os.path.exists(v)}}
    with open(paths['registry']) as f:
        inp['registry'] = json.load(f)
    with open(paths['reference']) as f:
        inp['reference'] = json.load(f)
    with open(paths['nd_plan']) as f:
        inp['nd_plan'] = json.load(f)
    inp['hsp_path'] = paths['hsp007']
    nd_path = os.path.join(data_dir, 'nd', 'blocks.jsonl')
    inp['nd_done'] = os.path.exists(os.path.join(data_dir, 'nd', 'DONE'))
    inp['nd_path'] = nd_path if os.path.exists(nd_path) else None
    rpc = os.path.join(data_dir, 'rpc')
    inp['rpc_done'] = os.path.exists(os.path.join(rpc, 'DONE'))
    inp['supply'] = jl(os.path.join(rpc, 'supply.jsonl')) if os.path.exists(os.path.join(rpc, 'supply.jsonl')) else []
    inp['operators'] = jl(os.path.join(rpc, 'operators.jsonl')) if os.path.exists(os.path.join(rpc, 'operators.jsonl')) else []
    return inp, paths


def run(instants_path, data_dir, out_dir):
    inp, paths = load_inputs(instants_path, data_dir)
    S = core.Study(instants_path, data_dir, tokens_path=paths['tokens'])
    ref = inp['reference']
    M.add_usd(S, ref['prices_usd'])
    res = {'inputs': {'paths': inp['paths'], 'sha256': inp['sha256'], 'data': data_digest(data_dir)},
           'T0_utc': S.meta['T0_utc'], 'seed': S.meta['seed'], 'B': core.B, 'errors': []}
    res['completeness'] = M.completeness(S)
    res['neardata_done'] = inp['nd_done']
    res['rpc_done'] = inp['rpc_done']

    # neardata
    nd, blocks = {}, []
    neardata = None
    try:
        import neardata  # noqa: F401
        if inp['nd_path'] and inp['nd_done']:
            blocks = neardata.load(inp['nd_path'])
            nd = M.nd_by_month(blocks, neardata)
    except Exception as e:  # recorded, never hidden
        res['errors'].append(f'neardata: {type(e).__name__}: {e}')
    sg = M.Signs(S, inp['registry'], nd)

    # flows
    res['audit'] = S.audit()
    res['audit']['flag'] = res['audit']['differ'] > 0
    res['flow_quality'] = M.flow_quality(S)
    res['C2b'] = M.c2b(S)
    res['census'] = M.census(S, ref)
    res['M1'] = M.m1(S, ref, res['census'])
    res['M9'] = M.m9(S, ref)
    res['chart1_flows'] = M.chart1_flows(S, ref)
    res['M10'] = M.m10(S)
    res['M10b'] = M.m10b(inp['supply']) if inp['rpc_done'] else []

    # sign
    res['M3'] = M.m3(sg)
    res['trend'] = M.trend(sg)
    res['M4_M5'] = M.m4_m5(sg)

    # index (descriptive)
    index_rows = {w['month']: S.index_rows(w) for w in S.windows if w['family'] == 'index' and S.window_complete(w)}
    res['dest_audit_selection'] = M.dest_audit_selection(index_rows)
    if neardata is not None and blocks:
        try:
            res['M6'] = M.m6(blocks, neardata, sg, index_rows)
            res['M7'] = core_pub(neardata.completion(blocks))
            res['nd_rate_check'] = M.nd_rate_check(blocks, inp['nd_plan'], sg)
        except Exception as e:
            res['errors'].append(f'M6/M7: {type(e).__name__}: {e}')
    else:
        res['M6'] = M.m6_index_only(index_rows)

    # M8
    try:
        import hsp007
        if os.path.exists(inp['hsp_path']):
            table = hsp007.load(inp['hsp_path'])
            res['M8'] = M.m8(sg, hsp007, table, inp['operators'] if inp['rpc_done'] else [])
    except Exception as e:
        res['errors'].append(f'M8: {type(e).__name__}: {e}')

    res['by_month'] = {'M3': {r['month']: r for r in res['M3']}, 'M4': {r['month']: r for r in res['M4_M5']},
                       'M8': {r['month']: r for r in res.get('M8', {}).get('months', [])}}
    res['mind'] = M.mind(M.pub(res))
    res = M.pub(res)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'results.json'), 'w') as f:
        json.dump(res, f, indent=1, sort_keys=True, default=_jdefault)
    with open(os.path.join(out_dir, 'tables.md'), 'w') as f:
        f.write(tables(res))
    charts.render(json.loads(json.dumps(res, default=_jdefault)), out_dir)
    return res


def core_pub(x):
    return M.pub(x)


def _jdefault(o):
    try:
        import decimal
        if isinstance(o, decimal.Decimal):
            return str(o)
    except Exception:
        pass
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    return str(o)


# ---------------------------------------------------------------- tables.md

def pct(x):
    return '–' if x is None else f'{100 * x:.1f}%'


def num(x, nd=0):
    return '–' if x is None else f'{x:,.{nd}f}'


def iv(r):
    return f"[{pct(r.get('L', r.get('lo')))}, {pct(r.get('U', r.get('hi')))}]"


def tables(res):
    L = [f"# Results (T0 {res['T0_utc']}, B = {res['B']})", '']
    if res['errors']:
        L += ['**Errors:** ' + '; '.join(res['errors']), '']
    L += ['## Completeness', '', '| family | completed | not completed | pending |', '|---|---|---|---|']
    for f, c in sorted(res['completeness'].items()):
        L.append(f"| {f} | {c.get('completed', 0)} | {c.get('not_completed', 0)} | {c.get('pending', 0)} |")
    a = res['audit']
    L += ['', f"Resolution audit: {a['audited']} transactions read whole, {a['differ']} differ from the window view"
          + (' (every flow reading carries this flag).' if a['flag'] else '.'), '']
    L += ['## C2b (M2): BTC verdict, Solana estimates', '',
          '| group | reading | Omni share [L, U] | state | transfers / windows |', '|---|---|---|---|---|']
    for g in ('BTC', 'SOL', 'Solana stablecoins (USD)'):
        G = res['C2b'][g]
        for key in ('claim|amount|both', 'claim|count|both', 'claim|amount|in', 'claim|amount|out', '90d|amount|both'):
            r = G['readings'][key]
            stt = r.get('state', 'estimate only') if G['verdict_given'] else 'estimate only'
            sp = f" ({r['sparse']})" if r['sparse'] else ''
            L.append(f"| {g} | {key} | {iv(r)} | {stt}{sp} | {r['distinct_transfers']} / {r['windows_with_any']} |")
    L += ['', '## M1: route map of the 28 chains (C1, no verdict)', '',
          '| chain | documented | Omni overview | observed use | dominant route |', '|---|---|---|---|---|']
    for r in res['M1']['chains']:
        L.append(f"| {r['chain']} | {', '.join(r['documented'])} | {'yes' if r['capability_omni_overview'] else ''} | "
                 f"{r['observed_use']} | {r['dominant_route']} |")
    c = res['M1']['counts']
    L += ['', f"Observed: {c['observed']['unfavourable_yes']} yes, {c['observed']['favourable_yes_plus_unknown']} yes or unknown, "
          f"of {c['observed']['of']}. Dominant: {c['dominant']['unfavourable_yes']} yes, "
          f"{c['dominant']['favourable_yes_plus_unknown']} yes or unknown. Documented capability: "
          f"{c['capability_documented']['count']} of {c['capability_documented']['of']}.", '']
    m9 = res['M9']
    L += ['## M9 (C2a, estimates only)', '',
          f"- p, Omni's share of measured value: {iv(m9['p'])}; p_CS (Omni withdrawals): {iv(m9['p_CS'])}",
          f"- measured value per 30 days: ${num(m9['measured_usd_per_30d']['point'])} "
          f"[{num(m9['measured_usd_per_30d']['lo'])}, {num(m9['measured_usd_per_30d']['hi'])}]",
          f"- c against V {pct(m9['c_against_V']['point'])}, against 2V {pct(m9['c_against_2V']['point'])}, "
          f"against the headline {pct(m9['c_against_headline']['point'])} (context)",
          f"- scenarios: S_L {pct(m9['scenarios']['S_L_unfavourable'])}, S_U {pct(m9['scenarios']['S_U_favourable'])}",
          f"- measured non-Omni value per 30 days: [{num(m9['non_omni_usd_per_30d']['lo'])}, "
          f"{num(m9['non_omni_usd_per_30d']['hi'])}] USD, [{pct(m9['non_omni_usd_per_30d']['share_of_2V']['lo'])}, "
          f"{pct(m9['non_omni_usd_per_30d']['share_of_2V']['hi'])}] of 2V", '']
    L += ['## M10: migration (amount, native units)', '', '| series | early [L, U] | late [L, U] | difference | state |',
          '|---|---|---|---|---|']
    for s, r in res['M10'].items():
        a = r['readings']['amount']
        d = a['difference']
        L.append(f"| {s} | {iv(a['early'])} | {iv(a['late'])} | [{pct(d.get('lo'))}, {pct(d.get('hi'))}] | {a['state']} |")
    t = res['trend']
    L += ['', '## Trend (M3)', '']
    for k in ('raw', 'excluding class 3 and 2a', 'excluding 2a only (class 3 kept)'):
        x = t[k]
        L.append(f"- {k}: {num(x['point'], 2)} [{num(x['lo'], 2)}, {num(x['hi'], 2)}], {x['state']}")
    L += ['', '## M3 and M4 by month', '', '| month | calls/day [95%] | main | main without Sweat | narrow | broad |',
          '|---|---|---|---|---|---|']
    m4 = {r['month']: r for r in res['M4_M5']}
    for r in res['M3']:
        x = r['raw']
        k = m4.get(r['month'], {})
        mn, mw = k.get('main', {}), k.get('main_without_sweat', {})
        L.append(f"| {r['month']}{'' if r['complete'] else ' (not completed)'} | {num(x['per_day'])} [{num(x['lo'])}, {num(x['hi'])}] | "
                 f"{pct(mn.get('point'))} [{pct(mn.get('lo'))}, {pct(mn.get('hi'))}] | "
                 f"{pct(mw.get('point'))} [{pct(mw.get('lo'))}, {pct(mw.get('hi'))}] | "
                 f"{pct(k.get('narrow', {}).get('point'))} | {pct(k.get('broad', {}).get('point'))} |")
    if 'M8' in res:
        L += ['', '## M8: program expenditure per request', '', '| month | NEAR executed (+pending) | calls | NEAR per request |',
              '|---|---|---|---|']
        for r in res['M8']['months']:
            pr = r.get('per_request_executed_plus_pending') or r.get('per_request_proposed') or {}
            L.append(f"| {r['month']}{' (provisional)' if r['provisional'] else ''} | {num(r['executed_plus_pending_near'], 2)}"
                     f" | {num(r['calls_in_month']['point'])} | {num(pr.get('point'), 4)} [{num(pr.get('lo'), 4)}, {num(pr.get('hi'), 4)}] |")
    if 'M7' in res:
        L += ['', '## M7: completion', '', '```', json.dumps({k: v for k, v in res['M7'].items() if k != 'pairs'}, indent=1), '```']
    return '\n'.join(L) + '\n'


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    t0 = time.time()
    r = run(*sys.argv[1:4])
    print('wrote', sys.argv[3], 'errors:', r['errors'], 'seconds:', round(time.time() - t0, 1))
