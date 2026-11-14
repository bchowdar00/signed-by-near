"""Assemble the S1 family's results.json from the per-deliverable outputs.

This script only concatenates the JSON that the deliverable scripts already wrote
(m3_results.json, m8_results.json, m7_results.json, hsp007_ledger.json,
index_results.json, audit_check_results.json) and re-aggregates the HSP-007 ledger
with the deliverable's own hsp007.summarise(). It computes nothing new. Sections for
scripts that were skipped (e.g. HSP-007 / M8 when the source file is absent) are left out.
python3 -I.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hsp007

HERE = os.path.dirname(os.path.abspath(__file__))


def load(n):
    p = os.path.join(HERE, n)
    return json.load(open(p)) if os.path.exists(p) else None


R = {}
m3 = load('m3_results.json')
if m3 is not None:
    R['m3'] = m3
m8 = load('m8_results.json')
if m8 is not None:
    R['m8'] = m8
m7 = load('m7_results.json')
if m7 is not None:
    R['m7'] = m7
led = load('hsp007_ledger.json')
if led is not None:
    R['hsp007_ledger'] = led
idx = load('index_results.json')
if idx is not None:
    R['index'] = {k: idx[k] for k in ('per_month', 'eligible_btc_n', 'eligible_zec_n')}
aud = load('audit_check_results.json')
if aud is not None:
    R['dest_audit_check'] = aud
if led is not None:
    agg = hsp007.summarise(led)
    tot = {}
    for mo, nets in agg.items():
        tot[mo] = {}
        for net, stats in nets.items():
            tot[mo][net] = {}
            for stt, (s, n) in stats.items():
                tot[mo][net][stt] = {'sum': round(s, 2), 'n': n}
    R['hsp007_totals'] = tot

json.dump(R, open('results.json', 'w'), indent=1)
print('wrote results.json with sections:', list(R.keys()))
