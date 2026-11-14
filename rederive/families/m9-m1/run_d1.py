"""Deliverable 1: economic transfers for all 15 tokens, telemetry, HT totals."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze, build
from collections import defaultdict, Counter

t0 = time.time()
wins = analyze.load_flow_windows()
TOK = build.load_tokens()

# telemetry per (token, period)
rows_read = 0
dedup_rows = 0
by = defaultdict(lambda: {'transfers': 0, 'omni': 0, 'poa': 0, 'unknown': 0, 'mixed': 0, 'near-side': 0,
                         'amt_omni': 0, 'amt_poa': 0, 'amt_other': 0, 'in': 0, 'out': 0,
                         'usd_total': 0.0, 'usd_omni': 0.0, 'n_win': 0, 'n_win_complete': 0})
for w in wins:
    pages = build.load_pages(w['id'])
    rr = sum(len(p['rows']) for p in pages)
    rows_read += rr
    dedup_rows += len(build.dedup_rows(pages))
    key = (w['token'], w['period'])
    by[key]['n_win'] += 1
    if w['completed']:
        by[key]['n_win_complete'] += 1
    for t in w['transfers']:
        d = by[key]
        d['transfers'] += 1
        d[t['route']] += 1
        d[t['direction']] += 1
        d['usd_total'] += w['weight'] * analyze.usd(t)
        if t['route'] == 'omni':
            d['usd_omni'] += w['weight'] * analyze.usd(t)
        nat = analyze.native(t)
        if t['route'] == 'omni':
            d['amt_omni'] += nat
        elif t['route'] == 'poa':
            d['amt_poa'] += nat
        else:
            d['amt_other'] += nat

out = {'tokens': {}, 'telemetry': {}}
print('token/period route splits + native amounts (sum of raw transfer amounts, NOT weighted):')
for (tok, per) in sorted(by):
    d = by[(tok, per)]
    print(f'{tok[:38]:40} {per:7} n={d["transfers"]:4} omni={d["omni"]:4} poa={d["poa"]:4} '
          f'near={d["near-side"]:3} in={d["in"]:4} out={d["out"]:4} HT_usd={d["usd_total"]:.0f}')

# HT totals per token over 90d (both strata), measured value per 30 days
print('\nHT USD totals per token (84 measured days) and per-30-days:')
tok_usd = defaultdict(float)
tok_usd_omni = defaultdict(float)
for w in wins:
    for t in w['transfers']:
        tok_usd[w['token']] += w['weight'] * analyze.usd(t)
        if t['route'] == 'omni':
            tok_usd_omni[w['token']] += w['weight'] * analyze.usd(t)
grand = 0.0
grand_omni = 0.0
for tok in [x['contract'] for x in [TOK[c] for c in TOK]]:
    pass
for tok in TOK:
    u = tok_usd[tok]
    grand += u
    grand_omni += tok_usd_omni[tok]
    print(f'{tok[:40]:42} HT_usd_84d={u:16.2f}  per30d={u*30/84:16.2f}  omni_share={ (tok_usd_omni[tok]/u if u>0 else float("nan")):.4f}')
print(f'\nGRAND HT USD 84d = {grand:.2f}  per30d = {grand*30/84:.2f}')
print(f'GRAND omni USD 84d = {grand_omni:.2f}  overall omni share = {grand_omni/grand:.6f}')
print(f'\nrows_read={rows_read} dedup_rows={dedup_rows} total_transfers={sum(d["transfers"] for d in by.values())}')
print(f'runtime {time.time()-t0:.1f}s')
