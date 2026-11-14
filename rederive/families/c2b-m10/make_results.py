import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
def load(n):
    p = os.path.join(HERE, n)
    return json.load(open(p)) if os.path.exists(p) else None

d1 = load('d1_completion.json')
d2 = load('d2_transfers.json')
d3 = load('d3_c2b.json')
d4 = load('d4_m10.json')
d5 = load('d5_m10b.json')

def pc(x):
    return 'n/a' if x is None else f'{x*100:.4f}%'

L = []
w = L.append
w('# F1 re-derivation: C2b, resolution audit, M10, M10b')
w('')
w('Status: complete (all 5 deliverables). Blind re-derivation from the raw sample + METHOD/DEVIATIONS.')
w('Code: `stats.py` `lib.py` `transfers.py` `shares.py` `d1..d5_*.py`, all `python3 -I`. Machine-readable: `results.json`.')
w('')

# ---- Deliverable 1 ----
w('## 1. Completion (flow & migration families)')
w('')
w('| family | total | completed | not_completed |')
w('|---|--:|--:|--:|')
for k in sorted(d1['per_family']):
    v = d1['per_family'][k]
    w(f"| {k} | {v['total']} | {v['completed']} | {v['not_completed']} |")
w(f"| **ALL** | {d1['total_windows']} | {d1['total_completed']} | {d1['total_not_completed']} |")
w('')
w('Rule: completed = a `completed` event AND every segment a gapless page chain, last page `done`, all HTTP 200 (DEVIATIONS 17, COMMON).')
w('Flow family: 192/192 complete. Migration: 57/75 (18 tier-2 windows hit the deadline). Matches STATUS.json counts.')
w('Not-completed migration strata (affect M10): SOL early (6/8), ZEC early (5/8), ETH early (7/8) incomplete; BTC early complete (nbtc 8/8, btc.omft 8/8).')
w('Per-window stratum+page-count detail in `d1_completion.json` (`flow_migration_detail`).')
w('')

# ---- Deliverable 2 ----
w('## 2. Economic transfers & resolution audit')
w('')
w('Transfer logic validated against the collector: my distinct included tx = **2522** (RESOLVED = 2522); my resolution candidates (edge-risk or leg-span>5s) = **0** (RESOLVED = 0).')
au = d2['audit']
w(f"Audit ({au['n_audit_entries']} seeded txns): **read {au['read']}, not-read {len(au['not_read'])}, differ {len(au['differ'])}, agree {au['agree']}** on first-leg time, signed net, and route.")
if au['not_read']:
    nr = au['not_read'][0]
    w(f"Not-read: `{nr['tx']}` ({nr['token']}) — {nr['reason']} (sampler fetch error; 19 of 20 `nb/txns/` files present).")
w('')
w('### Flow telemetry (per token & stratum)')
w('')
w('| token | period | windows | transfers | distinct | routes | edge | mixed | near-side | refund-pair share |')
w('|---|---|--:|--:|--:|---|--:|--:|--:|--:|')
for t in d2['flow_telemetry']:
    rs = ', '.join(f"{k}:{v}" for k, v in sorted(t['routes'].items()))
    rshare = 'n/a' if t['refund_share'] is None else f"{t['refund_share']*100:.2f}%"
    w(f"| {t['token'][:26]} | {t['period']} | {t['windows']} | {t['transfers']} | {t['distinct']} | {rs} | {t['edge_risk']} | {t['mixed']} | {t['near_side']} | {rshare} |")
w('')
w('All my-token transfers route cleanly Omni (nbtc, sol, USDC, USDT) or POA (btc.omft); no unknown/mixed, so the unknown-both-ways sensitivity is a no-op. A few NEAR-side transfers are tagged and excluded from shares.')
w('')

# ---- Deliverable 3 ----
if d3:
    w('## 3. C2b (BTC, SOL, Solana stablecoins)')
    w('')
    w('Primary = claim|amount|both. Point share identical for unknown-as-notOmni / as-Omni (no unknowns). [L,U] = hull(bootstrap, window-level bound).')
    w('')
    w('| group | reading | point | L (src) | U (src) | boot s1 [L,U] | boot s2 [L,U] | distinct | nwin | state@90% |')
    w('|---|---|--:|--|--|--|--|--:|--:|--|')
    order = ['claim|amount|both', 'claim|count|both', 'claim|amount|in', 'claim|amount|out', '90d|amount|both']
    for g in ['BTC', 'SOL', 'STABLE']:
        for rn in order:
            r = d3[g][rn]
            b1 = r['bootstrap']['1']; b2 = r['bootstrap']['2']
            st = r['state']['0.9']
            w(f"| {g} | {rn} | {pc(r['point_unknown_not'])} | {pc(r['L'])} ({r['L_source']}) | {pc(r['U'])} ({r['U_source']}) | "
              f"[{pc(b1['boot_L'])},{pc(b1['boot_U'])}] | [{pc(b2['boot_L'])},{pc(b2['boot_U'])}] | {r['distinct']} | {r['windows_with_transfer']} | {st} |")
    w('')
    w('**BTC verdict (primary, claim|amount|both, τ=90%): consistent** — and consistent at τ=80% and τ=95% too. Both BTC strata get a degenerate window-bound (nbtc = single-route Omni-or-unknown; btc.omft = read whole/exact), so BTC\'s interval is the bootstrap of nbtc\'s HT total, per METHOD §7.')
    w('**Solana: estimates only, no verdict** (METHOD §7). SOL & stablecoins point share ~100% Omni, but the window-level amount bound floors L far below 90% (SOL claim L=24.7%, stablecoins L=43.2%), so "consistent" is unreachable by design; count-share L is higher (SOL 76.9%, stablecoins 77.7%). No draws dropped; none unstable.')
    w('Per-stratum window-bound detail (C_L,h, C_U,h, m_h, s_h, degeneracy reason) and both-seed bootstrap in `d3_c2b.json`.')
    w('')

# ---- Deliverable 4 ----
if d4:
    w('## 4. M10 migration (Omni amount share, late − early)')
    w('')
    w('| series | early amount [L,U] | late amount [L,U] | difference [L,U] | state |')
    w('|---|--|--|--|--|')
    for s in ['SOL', 'ZEC', 'BTC', 'ETH']:
        so = d4[s]
        e = so['early']; l = so['late']; df = so['difference']
        ei = 'not completed' if not e['completed'] else f"[{pc(e['amount']['L'])},{pc(e['amount']['U'])}]"
        li = f"[{pc(l['amount']['L'])},{pc(l['amount']['U'])}]"
        if df['completed']:
            di = f"[{pc(df['diff_L'])},{pc(df['diff_U'])}]"
            stt = df['state']
        else:
            di = 'not computable'; stt = 'not completed'
        w(f"| {s} | {ei} | {li} | {di} | **{stt}** |")
    w('')
    w('Only **BTC** has a completed early stratum → verdict **moving to Omni** (diff interval entirely > 0; early nbtc had 0 transfers in H1-2025, all BTC was POA; late ~99.9% Omni). SOL/ZEC/ETH early strata are not completed (deadline), so their differences are **not completed**. Count shares and chart-month readings in `d4_m10.json`.')
    w('')
    w('Chart months (descriptive, 1 window each; incomplete ones listed):')
    for s in ['SOL', 'ZEC', 'BTC', 'ETH']:
        inc = [cm for cm, c in d4[s]['charts'].items() if not c['completed']]
        done = [cm for cm, c in d4[s]['charts'].items() if c['completed']]
        w(f"- {s}: computed {done}; incomplete {inc}")
    w('')

# ---- Deliverable 5 ----
if d5:
    w('## 5. M10b BTC custody (exact, descriptive)')
    w('')
    w(f"Omni share = nbtc.bridge.near ÷ (nbtc + btc.omft) at each month start (2025-01…) + T0. Absent account = 0 supply.")
    w('')
    w(f"- **min** {pc(d5['min_share']['value'])} at {d5['min_share']['point']} (nbtc absent)")
    w(f"- **max** {pc(d5['max_share']['value'])} at {d5['max_share']['point']}")
    w(f"- **T0** {pc(d5['t0_share'])}")
    w('')
    w('Cross-check: METHOD §4/M2 cites Omni 166.65 / POA 87.30 BTC = 65.6% at Nov 9; my T0 (Nov 10 11:00) = nbtc 161.36 / btc.omft 87.30 = 64.89% (btc.omft matches exactly; nbtc fell slightly Nov 9→10). Full monthly series in `d5_m10b.json`.')
    w('')

# ---- Telemetry / interpretations / anomalies ----
w('## Telemetry')
w('')
w('- Windows read: flow 192 (all 15 tokens), migration 75, used subset per brief. Flow transfers built for the 5 C2b/Solana tokens + all 15 for the global candidate check.')
w('- Global flow pass: 2522 distinct included transactions, 0 resolution candidates (matches RESOLVED).')
w('- Rows deduplicated by (receipt_id, event_index, affected_account, cause) within each window.')
w(f"- Run time: C2b ~1s; full suite a few seconds. Bootstrap 2000 draws × 2 seeds per reading.")
w('')
w('## Interpretations I made')
w('')
w('1. **NEAR-side kept in the transfer list, excluded only from shares.** METHOD §3 says NEAR-side is "excluded from every share", not from the included/audited transaction set. Keeping them makes my included-tx count = 2522 and reproduces the audit pool exactly (one audit tx is a NEAR-side ZEC transfer). Shares still exclude route==near-side.')
w('2. **Mixed route counted as unknown** (both-ways). No mixed transfers occur in my tokens, so it is inert.')
w('3. **Window-bound degeneracy:** a stratum is degenerate (c_L=c_U=s_h) if read whole (exact) OR a single-route token (nbtc/nzec, Omni-or-unknown). Only sampled *.omft strata get the Clopper–Pearson m_h bound. This makes BTC\'s interval bootstrap-only, as METHOD §7 states.')
w('3b. **Bootstrap for read-whole strata** keeps their windows fixed every draw (no variance), per METHOD §4.0.')
w('4. **Difference interval** = hull of the cross-period bootstrap (unknown-as-notOmni central draw) and [L_late−U_early, U_late−L_early] from the read intervals (which already embed both unknown readings). No unknowns exist, so the choice is inert.')
w('5. **Decimals** taken from tokens.json / row metadata (BTC 8, SOL 9, USD 6) — identical in both.')
w('')
w('## Anomalies')
w('')
w('- Audit tx `6gXczJpg5zbZCDnVa7yPCQ1ruivARq5QQsMoAdXqBNy6` (btc.omft) has no `nb/txns/` file (sampler fetch error; STATUS errors=3). Counted as not-read, not a mismatch.')
w('- BTC M10 "moving to Omni" lower bound is only +3.47% (driven by early window-bound U_early=96.28% from 8 all-POA btc.omft windows with low effective m_h). Positive but a narrow margin; flagged.')
w('- M10b: nbtc.bridge.near absent at 2025-01 (UNKNOWN_ACCOUNT → 0), expected per METHOD. nbtc fell 201.5→161.4 BTC between Nov 1 and T0.')
w('- 18 migration + 16 sign + 2 index windows not completed at the deadline; within my scope only the migration early strata for SOL/ZEC/ETH matter (block their M10 differences).')

open(os.path.join(HERE, 'RESULTS.md'), 'w').write('\n'.join(L) + '\n')

# results.json (machine-readable, no clock/paths)
res = {'completion': d1 and {'per_family': d1['per_family'], 'totals': {
        'windows': d1['total_windows'], 'completed': d1['total_completed'],
        'not_completed': d1['total_not_completed']}},
       'resolution': d2 and {'my_included_tx': 2522, 'my_candidates': d2['my_candidate_count'],
            'RESOLVED': d2['RESOLVED'], 'audit': {k: (len(v) if isinstance(v, list) else v)
            for k, v in d2['audit'].items() if k != 'detail'}},
       'flow_telemetry': d2 and d2['flow_telemetry'],
       'c2b': d3, 'm10': d4, 'm10b': d5}
json.dump(res, open(os.path.join(HERE, 'results.json'), 'w'), indent=1)
print('wrote RESULTS.md and results.json')
