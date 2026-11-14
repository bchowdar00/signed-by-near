"""Checks the counts THESIS.md states that no placeholder can carry, and the conditions its wording rests on.

  python3 -I publish/check_thesis.py out/combined.json THESIS.md <data_dir>

publish/fill.py fills every reading from out/combined.json. A handful of statements are counts over those
readings or over the saved rows (how many of the five tests were met, the windows read in full, which chains
are which, how the destination-audit picks cluster, how many operators were paid, the mainnet and testnet
rows of the HSP-007 ledger, the deposits `sign` calls attach, the early windows of SOL that did not finish,
the duplicate requests among M7's censored ones, the inputs of the Zcash picks, the Monte Carlo spread of two
interval ends, how the chains split under the dominant-route rule, how far apart Bitcoin's two intervals are, the
early Bitcoin windows, the order of the saved pages), and
out/combined.json does not hold them, so THESIS.written.tmpl.md states them in words. This command derives
each one from out/combined.json, out/results.json (the frozen output, unmasked), inputs/hsp007-ledger.json,
rederive/mc-seeds/sweep.json, audit/raw/ and the saved sample in <data_dir> (read with the frozen analysis code, imported
read-only), asserts every condition the surrounding sentences depend on (for example that the first two
tests were not met, or that the spend intervals overlap), and checks that THESIS.md says exactly that. It
exits non-zero on any mismatch. It reads only; it writes nothing. It is not part of any manifest.

The first screen's dates and times, and what it says the pilot showed, are words from the records. RECORDS below
lists each with the file that must contain it, and the check fails if one is missing.

It also holds the text of TABLE-NOTES.md (table_notes): the notes to read beside the tables and charts, which
timestamped code writes and which were therefore left as they are. The check fails if TABLE-NOTES.md differs
from that text. With --notes as a fifth argument it prints the text and checks nothing:

  python3 -I publish/check_thesis.py out/combined.json THESIS.md <data_dir> --notes > TABLE-NOTES.md
"""
import hashlib, json, os, sys
from collections import defaultdict
from decimal import Decimal

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.append(os.path.join(ROOT, 'analysis'))   # the frozen analysis code, imported, never changed
import fill as F  # noqa: E402
import core  # noqa: E402
import hsp007  # noqa: E402
import neardata  # noqa: E402

TESTS = [('value_mostly_on_omni', 'Value mostly on Omni'), ('omni_dominant_widely', 'Omni dominant widely'),
         ('broad_adoption', 'Broad adoption'), ('falling_spend_per_request', 'Falling spend per request'),
         ('no_migration', 'No migration')]
STATUS = {True: 'met', False: 'not met', None: 'undecided'}
MONTH = {'01': 'January', '02': 'February', '03': 'March', '04': 'April', '05': 'May', '06': 'June',
         '07': 'July', '08': 'August', '09': 'September', '10': 'October', '11': 'November', '12': 'December'}
WORD = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine'}
TIMED_OUT = 'This sign request has timed out, was completed, or never existed'
# what the first screen says happened when, and what the pilot showed: (file, the words it must contain)
RECORDS = [('METHOD.md', 'Last reconciled: 2026-11-10T11:51:19Z'),
           ('POST-FREEZE.md', 'from the start of the counted run (2026-11-10T11:52Z)'),
           ('POST-FREEZE.md', '`DEADLINE_UTC`, 2026-11-13T00:00:00Z'),
           ('AFTER-READ.md', '`frozen/MANIFEST-stage1.txt.ots.bak`, was written at 2026-11-10T11:51:41Z'),
           ('AFTER-READ.md', '`frozen/MANIFEST-stage2.txt.ots.bak`, at 2026-11-10T13:04:50Z'),
           ('AFTER-READ.md', 'stage 1 and stage 2, 975308 at 2026-11-10T14:41:27Z'),
           ('AFTER-READ.md', 'earliest block 975641 at 2026-11-13T07:25:27Z'),
           ('preread/HOLDER-READ.md', 'Written: 2026-11-13T05:46:06Z'),
           ('preread/HOLDER-READ.md', 'The first read is set for 2026-11-13T11:00:30Z'),
           ('preread/HOLDER-READ.md', "## The claim under test (the sketch's words, 2026-11-10)"),
           ('preread/HOLDER-READ.md', '(tests 1 and 2 not met; a series moving to Omni): a moat under construction.'),
           ('preread/HOLDER-READ.md', 'Today the signer is a cost that holders carry through dilution.'),
           ('preread/HOLDER-READ.md', 'Low breadth makes it a cost that buys little flow.'),
           ('preread/THESIS-b-SKETCH.copy.md', 'SOL and ZEC moved to it'),
           ('DEVIATIONS.md', 'were written in the thesis sketch on 2026-11-10 at 05:54Z'),
           ('METHOD.md', 'The readings were written after an uncounted pilot and the documents, and before the counted draw.'),
           ('METHOD.md', '  - SOL, ZEC and BTC transfers went through Omni;'),
           ('METHOD.md', '  - ETH, USDC on Ethereum, Arbitrum and Base, Tron USDT and XRP went through POA;'),
           ('METHOD.md', '  - one window per token, Nov 9 (RESEARCH H).'),
           ('METHOD.md', "In the pilot, 49 of 103 sampled calls were Sweat's FastAuth Ed25519 signatures"),
           ('METHOD.md', '**POA** is the Intents team\'s "Proof of Authority" bridge, which is custodial'),
           ('METHOD.md', 'the **claim window**, 2026-10-09T00:00Z to 2026-11-06T00:00Z, 28 days centred on the post of Oct 23'),
           ('METHOD.md', '**Interval.** The 95% interval is the hull of two intervals:'),
           ('METHOD.md', '150 random blocks per month'),
           ('METHOD.md', 'On Nov 9 NearStats listed 39 supported chains')]


def names(xs):
    return ', '.join(xs[:-1]) + ' and ' + xs[-1]


def m8_ledger(R):
    """The HSP-007 ledger by (month, network, status), checked against the frozen M8 months."""
    led = hsp007.load(os.path.join(ROOT, 'inputs', 'hsp007-ledger.json'))
    s = {}
    for r in led['rows']:
        k = (r['service_month'], r['network'], r['status'])
        s[k] = s.get(k, Decimal(0)) + hsp007._dec(r['amount_near'])
    for m in R['M8']['months']:
        mo = m['month']
        assert abs(float(s.get((mo, 'mainnet', 'executed'), 0)) - m['mainnet_executed_near']) < 0.005, mo
        assert abs(float(s.get((mo, 'testnet', 'executed'), 0)) - m['testnet_executed_near']) < 0.005, mo
        both = sum((v for (mm, _, st), v in s.items() if mm == mo and st in ('executed', 'pending')), Decimal(0))
        assert abs(float(both) - m['executed_plus_pending_near']) < 0.005, mo
    return s


def m7_duplicates(data_dir, M7):
    """M7's censored requests, found as the frozen pairing finds them (analysis/neardata.py completion),
    with the identical request before each and the failed responds for the same payload."""
    blocks = neardata.load(os.path.join(data_dir, 'nd', 'blocks.jsonl'))
    again = neardata.completion(blocks)
    for k in ('n_blocks', 'evaluated', 'matched', 'censored', 'ambiguous', 'failed_responses_seen'):
        assert again[k] == M7[k], k
    contig = sorted((b for b in blocks if b.get('part') == 'contiguous'), key=lambda b: b.get('height', 0))
    n = len(contig)
    rank = {b['height']: i for i, b in enumerate(contig)}
    mid = lambda h: 100 <= rank[h] < n - 100   # completion()'s defaults: 100 context and 100 tail blocks
    reqs, oks, failed = defaultdict(list), defaultdict(list), defaultdict(list)
    for b in contig:
        for i, c in enumerate(b.get('calls') or []):
            pos = (b['height'], i)
            if c.get('method') == 'sign':
                k = neardata._sign_key(c)
                if k is not None:
                    reqs[k].append(pos)
            elif c.get('method') == 'respond':
                k = neardata._respond_key(c)
                if neardata._succeeded(c.get('status')):
                    if k is not None and rank[b['height']] >= 100:
                        oks[k].append(pos)
                else:
                    failed[k].append((pos, json.dumps(c.get('status'))))
    out = []
    for k, rs in reqs.items():
        rs.sort()
        resp, used = sorted(oks.get(k, [])), set()
        for p in (p for p in rs if mid(p[0])):
            j = next((j for j, q in enumerate(resp) if j not in used and q >= p), None)
            if j is None:
                before = [q for q in rs if q < p]
                assert len(before) == 1 and len(rs) == 2, 'the second of two identical requests'
                fl = [(q, st) for q, st in failed.get(k, []) if q > p]
                assert fl and all(TIMED_OUT in st for _, st in fl), 'a failed respond with the contract message'
                out.append(rank[p[0]] - rank[before[0][0]])
            else:
                used.add(j)
    assert len(out) == M7['censored']
    return sorted(out)


def page_order(S):
    """The saved pages of the `sign` windows: how many windows have any, how many pages, how many page-to-page
    steps, and how many of each are out of order (the API is read newest first; collector/sampler.py stops at the
    first page that holds a row older than the window's start, which is right only in that order)."""
    import flows
    sign = [w for w in S.windows if w['family'] == 'sign']
    with_pages = pages = steps = bad_pages = bad_steps = 0
    for w in sign:
        n0 = pages
        for seg in range(S.n_segments(w)):
            prev = None
            for p in S.seg_pages(w['id'], seg):
                ts = [flows.row_ts(r) for r in p['rows']]
                pages += 1
                bad_pages += any(a < b for a, b in zip(ts, ts[1:]))      # equal times on neighbouring rows are in order
                if prev and ts:
                    steps += 1
                    bad_steps += max(ts) > min(prev)
                prev = ts or prev
        with_pages += pages > n0
    return {'windows': len(sign), 'with_pages': with_pages, 'pages': pages, 'steps': steps,
            'bad_pages': bad_pages, 'bad_steps': bad_steps}


def month_windows(S, month):
    """A month's `sign` windows: calls kept in each, its length, and whether its last page reaches past its start."""
    import flows
    out = []
    for w in (w for w in S.windows if w['family'] == 'sign' and w['stratum'] == f'sign:{month}'):
        assert S.window_complete(w) and len(w['segments_ns']) == 1
        s, e = (int(x) for x in w['segments_ns'][0])
        last = S.seg_pages(w['id'], 0)[-1]
        out.append({'kept': len(S.sign_calls(w)), 'seconds': (e - s) / 1e9,
                    'past_start': min(flows.row_ts(r) for r in last['rows']) < s})
    return out


def derive(R, data_dir):
    """The counts the text states, with every condition its wording depends on asserted."""
    for name, words in RECORDS:
        with open(os.path.join(ROOT, name)) as f:
            assert words in f.read(), (name, words)
    D = {}
    mind = R['mind']
    for k, _ in TESTS:
        assert mind[k]['met'] in (True, False, None), k
    D['status'] = {k: STATUS[mind[k]['met']] for k, _ in TESTS}
    D['met'] = sum(mind[k]['met'] is True for k, _ in TESTS)
    D['not_met'] = sum(mind[k]['met'] is False for k, _ in TESTS)
    D['undecided'] = sum(mind[k]['met'] is None for k, _ in TESTS)
    # the first screen: "Three results would have shown a broad moat. None occurred" (tests 1 to 3), "Two more
    # would have changed the read on cost and on direction. Neither occurred" (tests 4 and 5), and
    # "All five frozen tests read not met"
    assert D['met'] == 0 and D['undecided'] == 0 and D['not_met'] == len(TESTS) == 5
    # "the claim held on breadth" and "narrow and widening" (preread/HOLDER-READ.md): tests 1 and 2 not met,
    # and a series moving to Omni.
    assert mind['value_mostly_on_omni']['met'] is False and mind['omni_dominant_widely']['met'] is False
    assert any(v == 'moving to Omni' for v in mind['no_migration']['states'].values())

    rule = R['rule']
    D['windows_total'] = rule['windows_total']
    D['windows_read'] = rule['windows_total'] - rule['unfinished_windows']
    assert D['windows_read'] == sum(v.get('completed', 0) for v in R['completeness'].values())

    M9 = R['M9']
    for k in ('p', 'p_CS'):
        assert M9[k]['complete'] and M9[k]['n_unknown'] == 0
        assert M9[k]['point_unknown_omni'] == M9[k]['point_unknown_not_omni']
    # section 3: both ends of the share's interval are the window-level bound, wider than the bootstrap alone;
    # the dollar ranges are bootstrap intervals of totals (analysis/measures.py m9: core.total(...).interval());
    # the two scenarios equal the interval's ends because coverage is capped at 1; the by-chain one is not capped
    rl = M9['p']['reading_L']
    assert (M9['p']['L'], M9['p']['U']) == tuple(rl['bound']) and rl['bound'][0] < rl['boot'][0] < rl['boot'][1] < rl['bound'][1]
    sc, bc = M9['scenarios'], M9['by_chain_scenario']
    assert sc['c_against_2V'] == 1.0 and (sc['S_L_unfavourable'], sc['S_U_favourable']) == (M9['p']['L'], M9['p']['U'])
    assert bc['c'] < 1 and bc['S_L_unfavourable'] < bc['S_U_favourable']
    assert M9['c_against_2V']['point'] == 1.0 and M9['c_against_V']['point'] > 2, \
        'the text says coverage against 2V is capped, the measured value being more than twice V'

    chains = R['M1']['chains']
    measured = [c for c in chains if c.get('measured_tokens')]
    assert len(measured) == mind['omni_dominant_widely']['of_measured']
    assert [c['chain'] for c in measured if c['dominant_route'] == 'yes'] == ['Bitcoin']
    assert all(c['dominant_route'] == 'unknown' for c in measured if c['chain'] != 'Bitcoin')
    assert mind['omni_dominant_widely']['undecided'] == 0
    poa = [c for c in measured
           if all(u['n_unknown'] == 0 and u['point_unknown_omni'] == 0 == u['point_unknown_not_omni']
                  for u in c['amount_share_by_unit'].values())]
    D['poa_names'] = names([c['chain'] for c in poa])
    # the dominant-route rule over the 8: shown on 1; not shown on 7, of which 2 hold Omni value with intervals
    # too wide (the lower end not above 50%) and 5 hold no Omni value in the sample
    wide = [c['chain'] for c in measured if c['dominant_route'] == 'unknown' and c not in poa]
    assert wide == ['Solana', 'Zcash'] and 1 + len(wide) + len(poa) == len(measured) == 8
    for c in poa:      # no Omni value, yet not "no" under the rule: an upper end is not below 50%
        assert any(u['U'] >= 0.5 for u in c['amount_share_by_unit'].values())
    D['dom_split'] = (1, len(measured), len(measured) - 1, len(wide), names(wide), len(poa))
    assert sorted(c['chain'] for c in poa) == ['Arbitrum', 'Base', 'Ethereum', 'Tron', 'XRP'], \
        'the text calls these the EVM, Tron and XRP chains'
    Us = [u['U'] for c in poa for u in c['amount_share_by_unit'].values()]
    D['poa_U'] = (min(Us), max(Us))
    for ch, unit in (('Solana', 'SOL'), ('Zcash', 'ZEC')):
        c = next(x for x in chains if x['chain'] == ch)
        u = c['amount_share_by_unit'][unit]
        assert u['n_unknown'] == 0 and u['point_unknown_omni'] == u['point_unknown_not_omni'] > 0.5, \
            'the text says Omni carried most of it'
        assert u['L'] < 0.5 and c['dominant_route'] == 'unknown'
    obs = [c for c in chains if c['observed_use'] == 'yes']
    assert len(obs) == R['M1']['counts']['observed']['unfavourable_yes']
    assert all(c['observed_in_census'] for c in obs if not c.get('measured_tokens'))
    D['obs_measured'] = names([c['chain'] for c in obs if c.get('measured_tokens')])
    D['obs_census'] = names([c['chain'] for c in obs if not c.get('measured_tokens')])
    # "The other 20 ... Four of them (...) appear in the census of Intents' own legs; the rest are shown by
    # their documented route only."
    other = [c for c in chains if not c.get('measured_tokens')]
    assert len(chains) == 28 and len(other) == 20
    cen = [c['chain'] for c in other if c['observed_in_census']]
    assert cen == [c['chain'] for c in obs if not c.get('measured_tokens')]
    D['census'] = (WORD[len(cen)].capitalize(), ', '.join(cen))

    c2b = R['C2b']['BTC']
    assert c2b['primary']['state'] == 'consistent' and c2b['primary']['n_unknown'] == 0
    assert all(v['state'] == 'consistent' for v in c2b['readings'].values()), 'every sensitivity reads the same'
    assert set(c2b['primary']['sensitivity_tau'].values()) == {'consistent'}
    # the first screen: "Nearly all of Intents' Bitcoin flow runs on Omni", and the 90% test in plain words
    assert c2b['primary']['L'] > 0.99 and c2b['readings']['90d|amount|both']['L'] > 0.99
    for s in ('SOL', 'Solana stablecoins (USD)'):
        assert 'state' not in R['C2b'][s]['primary'], 'Solana gets estimates only'
    M10 = R['M10']
    assert M10['BTC']['verdict'] == 'moving to Omni'
    # "moving", said with its margin: the two intervals' gap, and what the early sample held
    ba = M10['BTC']['readings']['amount']
    assert ba['state'] == 'moving to Omni' and abs(ba['difference']['lo'] - (ba['late']['L'] - ba['early']['U'])) < 1e-9
    assert ba['difference']['lo'] > 0
    D['btc_gap'] = F.fmt(ba['difference']['lo'] * 100, 'f1')
    assert float(D['btc_gap']) == round(float(F.fmt(ba['late']['L'], 'pct1')[:-1]) - float(F.fmt(ba['early']['U'], 'pct1')[:-1]), 1)
    D['btc_ends'] = (F.fmt(ba['early']['U'], 'pct1'), F.fmt(ba['late']['L'], 'pct1'))
    ea = ba['early']
    assert ea['n_unknown'] == 0 and ea['point_unknown_omni'] == 0 == ea['point_unknown_not_omni'], 'none of them on Omni'
    assert [x['stratum'] for x in ea['reading_L']['per_stratum']] == ['migration:btc.omft.near:early'], \
        'every early BTC transfer in the sample is on the POA token'
    assert ea['reading_L']['per_stratum'][0]['m_eff'] < 1.5, 'most of the amount sat in one window'
    D['btc_early'] = (ea['distinct_transfers'], ea['windows_with_any'], ea['windows'],
                      F.fmt(ea['reading_L']['per_stratum'][0]['m_eff'], 'f1'))
    assert all(M10[s]['verdict'] == 'not completed' for s in ('SOL', 'ZEC', 'ETH (POA control)'))
    # "SOL's share over the 90 days is complete and is in the tables (...); the comparison needs the
    # early-2025 windows too, and 2 of SOL's 8 did not finish."
    with open(os.path.join(ROOT, 'out', 'results.json')) as f:
        frozen = json.load(f)
    sol90 = R['C2b']['SOL']['readings']['90d|amount|both']
    sol_late = frozen['M10']['SOL']['readings']['amount']['late']
    assert sol90['complete'] and (sol90['L'], sol90['U']) == (sol_late['L'], sol_late['U'])
    S = core.Study(os.path.join(ROOT, 'frozen', 'instants.json'), data_dir)
    early = S.strata['migration:sol.omft.near:early']
    D['sol_early'] = (sum(not S.window_complete(w) for w in early), len(early))
    assert D['sol_early'][0] > 0 and 'migration:sol.omft.near:early' in rule['unfinished_strata']
    # "ZEC is the same: its share over the 90 days is complete (...), and 3 of its 8 early-2025 windows did not finish."
    zec90 = next(c for c in R['M1']['chains'] if 'ZEC' in c.get('amount_share_by_unit', {}))['amount_share_by_unit']['ZEC']
    zec_late = frozen['M10']['ZEC']['readings']['amount']['late']
    assert zec90['complete'] and (zec90['L'], zec90['U']) == (zec_late['L'], zec_late['U'])
    zearly = S.strata['migration:zec.omft.near:early']
    D['zec_early'] = (sum(not S.window_complete(w) for w in zearly), len(zearly))
    assert D['zec_early'][0] > 0 and 'migration:zec.omft.near:early' in rule['unfinished_strata']
    # M10b, "did not climb steadily ... by way of a fall to ... in March 2026": each point is a month start
    b10 = R['M10b']
    D['m10b'] = {p: next(i for i, x in enumerate(b10) if x['point'] == p) for p in ('2025-07', '2026-03', '2026-11')}
    assert b10[0]['point'] == '2025-01' and b10[-1]['point'] == 'T0'
    sh = [x['omni_share'] for x in b10]
    i7, i3 = D['m10b']['2025-07'], D['m10b']['2026-03']
    assert sh[i3] == min(sh[i7:]) and sh[i3] < sh[i7] and sh[i3] < sh[-1], 'a fall, to March 2026, then a rise'
    assert sh[-1] < sh[i7] and sh[i7] - sh[-1] < 0.02, 'the supply share is about where it was in July 2025, and no higher'
    D['supply'] = (F.fmt(sh[i7], 'pct1'), F.fmt(sh[-1], 'pct1'))

    bm = R['by_month']
    q = [bm['M8'][m]['per_request_executed_plus_pending'] for m in ('2026-07', '2026-08', '2026-09')]
    assert q[0]['point'] < q[1]['point'] < q[2]['point'], 'the text says the points rose'
    assert q[0]['hi'] > q[1]['lo'] and q[1]['hi'] > q[2]['lo'], 'the text says the intervals overlap'
    assert bm['M8']['2026-07']['calls_in_month']['point'] > bm['M8']['2026-09']['calls_in_month']['point'], \
        'the text says the calls fell'
    assert bm['M8']['2026-10']['calls_in_month']['point'] < bm['M8']['2026-09']['calls_in_month']['point'], \
        "section 6: October's total was lower again"
    m8 = {m['month']: m for m in R['M8']['months']}
    D['nodes'] = (len(m8['2026-07']['nodes_paid_mainnet']), len(m8['2026-09']['nodes_paid_mainnet']))
    assert D['nodes'][0] < D['nodes'][1], 'the text says the operator set grew'
    # mainnet and testnet apart (METHOD M8). The frozen code divides a fixed spend by the bootstrap draws of the
    # month's calls (analysis/measures.py m8), so the per-request interval scales with the spend: mainnet's is
    # the pooled one times mainnet spend / pooled spend. Checked first: the pooled ends are spend / calls ends.
    led = m8_ledger(R)
    tn = sorted({mo for (mo, net, _), v in led.items() if net == 'testnet' and v})
    assert tn == ['2026-06', '2026-07', '2026-08'], 'the text: testnet rows from June to August'
    assert {st for (mo, net, st), v in led.items() if net == 'testnet' and v} <= {'executed', 'pending'}
    D['testnet'] = (F.fmt(float(sum(v for (mo, net, st), v in led.items() if net == 'testnet' and st == 'executed')), 'f2'),
                    F.fmt(float(sum(v for (mo, net, st), v in led.items() if net == 'testnet' and st == 'pending')), 'f2'),
                    f"{MONTH[tn[0][5:]]} to {MONTH[tn[-1][5:]]}")
    main = []
    q6 = bm['M8']['2026-06']['per_request_executed_plus_pending']
    for mo, pooled in zip(('2026-06', '2026-07', '2026-08', '2026-09'), [q6] + q):
        calls = bm['M8'][mo]['calls_in_month']
        spend = m8[mo]['executed_plus_pending_near']
        assert abs(pooled['point'] / (spend / calls['point']) - 1) < 1e-9
        assert abs(pooled['lo'] / (spend / calls['hi']) - 1) < 1e-6 and abs(pooled['hi'] / (spend / calls['lo']) - 1) < 1e-6
        ms = float(led.get((mo, 'mainnet', 'executed'), 0) + led.get((mo, 'mainnet', 'pending'), 0))
        main.append({k: pooled[k] * ms / spend for k in ('point', 'lo', 'hi')})
    D['m8_june'] = (F.fmt(main[0]['point'], 'f4'), F.fmt(q6['point'], 'f4'))
    D['m8_pooled'] = [F.fmt(x['point'], 'f4') for x in q]
    main = main[1:]
    assert main[0]['point'] < main[1]['point'] < main[2]['point'], 'on mainnet too the points rose'
    assert main[0]['hi'] > main[1]['lo'] and main[1]['hi'] > main[2]['lo'], 'on mainnet too the intervals overlap'
    D['m8_main'] = [F.fmt(x['point'], 'f4') for x in main]
    for m in ('2026-08', '2026-09', '2026-10'):
        assert bm['M4'][m]['complete']
    # section 5, the same point with two intervals: main without Sweat is the directly calling class (4, 4x) plus
    # FastAuth's other apps (2b); the sample saw no 2b call, so the points are equal, and the wider upper end is
    # the bound on how many FastAuth calls could be 2b (analysis/measures.py m4_m5, DEVIATIONS 9)
    o = bm['M4']['2026-10']
    cs = o['class_shares']
    assert cs['2b']['point'] == 0 == cs['4x']['point'] and cs['4']['point'] == o['main_without_sweat']['point']
    assert cs['2a']['signer_share']['point'] == 1.0 and cs['2c']['point'] == 0, 'every FastAuth signer the sample read was Sweat\'s'
    assert o['main_without_sweat']['hi'] == o['main_without_sweat']['signer_bound'][1] > cs['4']['hi']
    w = [bm['M4'][m]['main_without_sweat']['point'] for m in ('2026-08', '2026-09', '2026-10')]
    assert w[0] < w[2] and w[1] < w[2], 'the first screen: "in October, and less before"'
    tr = R['trend']
    assert tr['raw']['state'] == 'inconclusive' and tr['excluding class 3 and 2a']['lo'] > 1, \
        'section 5: the headline trend is inconclusive; the one without tests and Sweat lies above 1'
    assert tr['excluding class 3 and 2a']['state'] == 'growing' and tr['raw']['point'] < 1 < tr['raw']['hi'], \
        'evidence against: use leaving out tests and Sweat grew; total calls did not grow'
    top3 = [c['caller'] for c in bm['M4']['2026-10']['concentration']['top3_callers']]
    assert top3 == ['fast-auth.near/sweat-relayer.near', 'omni.bridge.near', 'btc-connector.bridge.near'], \
        'the text names the three largest callers'
    oct6 = [x for x in R['M6']['purpose'] if x['month'] == '2026-10']
    assert len(oct6) == 1 and all(v['point'] == 0 for k, v in oct6[0]['share'].items()
                                  if k not in ('ed25519_fastauth_login', 'secp256k1')), 'two key types only'
    assert oct6[0]['blocks'] == 150, "section 5: October's 150 blocks"
    # "A `sign` call must attach at least 1 yoctoNEAR (N of M sampled calls attached exactly that)"
    calls = [c for w in S.windows if w['family'] == 'sign' for c in S.sign_calls(w)]
    assert all(int(c['deposit']) >= 1 for c in calls)
    D['deposit'] = (F.fmt(sum(1 for c in calls if int(c['deposit']) == 1), 'int'), F.fmt(len(calls), 'int'))
    M7 = R['M7']
    assert M7['evaluated'] == M7['matched'] + M7['censored'] and M7['ambiguous'] == 0
    # the share and the delays are stated in words: the synthetic runs the frozen tests fill the template
    # with have no matched pair, so a placeholder there would leave a hole
    D['m7'] = (F.fmt(M7['matched_share'], 'pct1'), F.fmt(M7['median_delay_s'], 'f1'), F.fmt(M7['max_delay_s'], 'f1'))
    gaps = m7_duplicates(data_dir, M7)
    assert gaps == [0, 0, 5], 'the text: two in the same block as the first, the third five blocks after it'
    D['m7_dup'] = f"{WORD[gaps.count(0)]} in the same block as the first, the third {WORD[gaps[-1]]} blocks after it"

    rows = R['dest_audit']['rows']
    btc = [r for r in rows if r['chain'] == 'BITCOIN']
    t = [r['block_time_utc'] for r in btc]
    assert len({r['dest_txn'] for r in btc}) == len(btc), 'separate transactions'
    D['btc_times'], D['btc_most'] = len(set(t)), max(t.count(x) for x in set(t))
    D['zec_no_other'] = sum(1 for r in rows if r['chain'] == 'ZCASH' and r['to_other_addresses'] == 0)
    assert D['zec_no_other'] > 0
    # the Zcash picks' inputs, from the saved lookups (audit/raw/): value from the signer addresses this audit
    # knows (the picks' own) against value from any other address
    zec = [r for r in rows if r['chain'] == 'ZCASH']
    known = {r['dest_address'] for r in zec}
    split = []
    for r in zec:
        with open(os.path.join(ROOT, 'audit', 'raw', f"zcash-{r['dest_txn']}.json")) as f:
            ins = json.load(f)['data'][r['dest_txn']]['inputs']
        k = sum(i['value'] for i in ins if i['recipient'] in known)
        split.append((k, sum(i['value'] for i in ins)))
        assert r['from_signer_address'] and k > 0, 'each pick still spends from a known signer address'
    outside = [(k, t) for k, t in split if t - k > k]
    assert sum(1 for k, t in split if k == t) + len(outside) == len(zec), 'the other picks: every input is a known address'
    D['zec_all_known'] = len(zec) - len(outside)
    least = min(outside, key=lambda x: x[0] / x[1])
    D['zec_inputs'] = (len(outside), len(zec), WORD[len(known)], F.fmt(least[0], 'int'), F.fmt(least[1], 'int'))
    with open(os.path.join(ROOT, 'out', 'published', 'tables.md'), 'rb') as f:
        raw = f.read()
    D['tables_sha'] = hashlib.sha256(raw).hexdigest()
    # TABLE-NOTES.md: where each note's rows are in the tables, and the facts each note states
    tl = raw.decode().split('\n')
    at = lambda pred: [i + 1 for i, l in enumerate(tl) if pred(l)]
    m8_head = at(lambda l: l.startswith('## M8'))[0]
    row = lambda mo: [i for i in at(lambda l: l.startswith(f'| {mo}')) if i > m8_head][0]
    dash = at(lambda l: '| – [' in l and '(not completed)' not in l)
    for mo, x in bm['M4'].items():      # a month printed with "–" under main: FastAuth has no calls, so main is narrow
        if x.get('complete') and not x.get('attributed'):
            assert x['class_shares']['2']['point'] == 0
            assert (x['main']['lo'], x['main']['hi']) == (x['narrow']['lo'], x['narrow']['hi'])
    assert all(l.startswith('| 2024') or l.startswith('| 2025') for l in (tl[i - 1] for i in dash))
    assert len(dash) == sum(1 for x in bm['M4'].values() if x.get('complete') and not x.get('attributed'))
    au = [r for r in S.resolve_log if r['audit']]
    miss = [r for r in au if not r['resolved']]
    assert len(miss) == 1 and miss[0]['http'] == 429 
    assert sum(1 for r in S.resolve_log if r['tx'] == miss[0]['tx']) == 1, 'the one not read was requested once'
    assert f"Resolution audit: {len(au) - 1} transactions read whole, 0 differ" in tl[at(lambda l: l.startswith('Resolution audit:'))[0] - 1]
    oct_ = m8['2026-10']
    assert oct_['provisional'] and oct_['executed_near'] == 0
    # note 5: May and July 2026, 100 calls each in six 60-second windows, none cut short; and the page order
    m3_head = at(lambda l: l.startswith('## M3'))[0]
    row3 = lambda mo: [i for i in at(lambda l: l.startswith(f'| {mo}')) if m3_head < i < m8_head][0]
    mw = {mo: month_windows(S, mo) for mo in ('2026-05', '2026-07')}
    for mo, ws in mw.items():
        assert len(ws) == 6 and sum(x['kept'] for x in ws) == 100 and all(x['seconds'] == 60 for x in ws), mo
        assert all(x['past_start'] for x in ws), 'each window ends on a page that holds a row older than its start'
    order = page_order(S)
    assert order['bad_pages'] == 0 == order['bad_steps'], 'do not write note 5: send the windows and the counts'
    assert order['windows'] == 198
    D['notes'] = {'m8_rows': (row('2026-06'), row('2026-08')), 'oct_row': row('2026-10'), 'dash': (dash[0], dash[-1]), 'dash_n': WORD[len(dash)],
                  'may_july': (row3('2026-05'), row3('2026-07'), row('2026-05'), row('2026-07')), 'order': order,
                  'audit_line': at(lambda l: l.startswith('Resolution audit:'))[0], 'drawn': len(au), 'read': len(au) - 1,
                  'miss_day': miss[0]['utc'][:10], 'miss_tx': miss[0]['tx'],
                  'oct_proposed': F.fmt(oct_['proposed_near'], 'f2'),
                  'oct_pr': F.fmt(bm['M8']['2026-10']['per_request_proposed']['point'], 'f4')}

    # The Monte Carlo spread of two bootstrap ends (rederive/mc-seeds/, another session's independent code),
    # and "No test's result is near its threshold".
    with open(os.path.join(ROOT, 'rederive', 'mc-seeds', 'sweep.json')) as f:
        sw = json.load(f)
    b, nn = sw['btc_90d_amount_lower'], sw['nonomni_30d_whole_fixed']
    btc90 = c2b['readings']['90d|amount|both']
    assert abs(b['published'] - btc90['L']) < 1e-6 and len(b['values']) == 60 and b['seeds'] == '1-60'
    assert round(nn['published_low'] / 1e4) == round(M9['non_omni_usd_per_30d']['lo'] / 1e4)
    assert len(nn['low_values']) == 40 and nn['seeds'] == '1-40'
    D['mc'] = (len(nn['low_values']), f"${nn['low_min'] / 1e9:.2f}B", f"${nn['low_max'] / 1e9:.2f}B",
               len(b['values']), f"{b['min'] * 100:.2f}%", f"{b['max'] * 100:.2f}%")
    p = M9['p']
    assert p['L'] == p['reading_L']['bound'][0] < p['reading_L']['boot'][0], 'test 1: its lower end is the exact bound'
    assert nn['high_over_2V_min'] > 0.10, 'test 1: the non-Omni upper end stays far above 10% of 2V'
    diff = M10['BTC']['readings']['amount']['difference']
    U_early = M10['BTC']['readings']['amount']['early']['U']
    assert abs(diff['lo'] - (btc90['L'] - U_early)) < 1e-9 and b['min'] - U_early > 0, \
        "test 5: BTC's move stays above 0 at every seed"
    for m in ('2026-08', '2026-09', '2026-10'):
        x = bm['M4'][m]['main_without_sweat']
        assert x['point'] < 0.25 / 2 and x['lo'] < 0.15 / 2, 'test 3: far below its thresholds'
    assert q[1]['hi'] > q[0]['lo'] and q[2]['hi'] > q[1]['lo'], 'test 4: no interval wholly below the one before'
    # the Explorer read (added after the read): its sentences are written by explorer/sentences.py from
    # explorer/results.json; `explorer/analyse.py ... --check` ties that file to the published sums
    D['explorer'] = []
    ex = os.path.join(ROOT, 'explorer', 'results.json')
    if os.path.exists(ex):
        if os.path.join(ROOT, 'explorer') not in sys.path:
            sys.path.append(os.path.join(ROOT, 'explorer'))
        import sentences as explorer_sentences  # noqa: E402
        with open(ex) as f:
            D['explorer'] = explorer_sentences.statements(json.load(f))
    return D


def expected(D):
    """Each statement as THESIS.md must contain it, and how many times."""
    ds, sup = D['dom_split'], D['supply']
    e = [('the two groups of tests', 'T1 to T3 would have shown a broad moat; T4 and T5 would have changed the read on cost and on direction.', 1),
         ('the count of the five', 'All five frozen tests read not met; none was met and none is undecided.', 1),
         ('the count in Table 1', f"| T2 | Omni dominant widely | Omni the dominant route on at least 5 of the 8 chains this sample can read | {ds[0]} of {ds[1]}, Bitcoin |", 1),
         ('the dominant-route split', f"Omni is shown dominant on {ds[0]} of {ds[1]}, Bitcoin. On the other {ds[2]} it is not shown: on {ds[3]} "
                                      f"({ds[4]}) the intervals are too wide, and on {ds[5]} ({D['poa_names']}) the sample "
                                      f"holds no Omni value.", 1),
         ('the split in the table', f"shown dominant on {ds[0]} of {ds[1]}; not shown on {ds[2]} ({ds[3]} with intervals too "
                                    f"wide, {ds[5]} with no Omni value in the sample); 0 undecided", 1),
         ("the gap between Bitcoin's intervals", f"{D['btc_gap']} points apart ({D['btc_ends'][0]} against {D['btc_ends'][1]})", 2),
         ('the gap, named as the weak point', f"a {D['btc_gap']}-point gap between two intervals", 1),
         ('the supply share, July 2025 and T0', f"({sup[0]} then, {sup[1]} at T0)", 1),
         ('the early Bitcoin sample', f"{D['btc_early'][0]} early BTC transfers in {D['btc_early'][1]} of the "
                                      f"{D['btc_early'][2]} early windows, none of them on Omni", 1),
         ('the effective windows', f"an effective {D['btc_early'][3]} windows", 1)]
    mc = D['mc']
    e += [('the windows read in full', f"{D['windows_read']} of {D['windows_total']} windows read in full", 1),
          ('the POA-only chains', f"({D['poa_names']})", 2),
          ('their upper ends', f"upper ends, {F.fmt(D['poa_U'][0], 'pct1')} to {F.fmt(D['poa_U'][1], 'pct1')}", 1),
          ('chains with Omni in use', f"Omni is seen in use on {D['obs_measured']} among the measured chains, "
                                      f"and on {D['obs_census']} in the census", 1),
          ('the census chains', f"{D['census'][0]} of them ({D['census'][1]}) appear in the census of Intents' own legs", 1),
          ('the SOL early windows', f"and {D['sol_early'][0]} of SOL's {D['sol_early'][1]} did not finish", 1),
          ('the ZEC early windows', f"and {D['zec_early'][0]} of its {D['zec_early'][1]} early-2025 windows did not finish", 1),
          ('the operator set', f"grew from {D['nodes'][0]} nodes to {D['nodes'][1]}", 1),
          ('the testnet rows', f"Of these, {D['testnet'][0]} NEAR executed and {D['testnet'][1]} pending are testnet "
                               f"rows ({D['testnet'][2]}); the rest is mainnet.", 1),
          ('mainnet per request', f"On mainnet rows alone NEAR paid {D['m8_main'][0]} NEAR per `sign` request in July, "
                                  f"{D['m8_main'][1]} in August and {D['m8_main'][2]} in September", 1),
          ('mainnet in the table', f"(mainnet rows alone: {', '.join(D['m8_main'])}; same result)", 1),
          ('the deposits', f"must attach at least 1 yoctoNEAR ({D['deposit'][0]} of {D['deposit'][1]} sampled calls "
                           f"attached exactly that)", 1),
          ('the Bitcoin picks', f"confirmed at only {D['btc_times']} distinct times, {D['btc_most']} of them at one", 1),
          ('the Zcash rows', f"On {D['zec_no_other']} of the Zcash withdrawals", 1),
          ('the Zcash inputs', f"In {D['zec_inputs'][0]} of the {D['zec_inputs'][1]} Zcash picks most of the input value came "
                               f"from addresses outside the {D['zec_inputs'][2]} signer addresses this audit knows (in one, the "
                               f"known address supplied {D['zec_inputs'][3]} of {D['zec_inputs'][4]} zatoshi), so for those", 1),
          ('the other Zcash picks', f"In the other {D['zec_all_known']} every input came from a known signer address", 1),
          ('the tables file', f"`out/published/tables.md` should read `{D['tables_sha']}`", 1),
          ('completion', f"requests evaluated ({D['m7'][0]}) were paired", 1),
          ('the duplicates', D['m7_dup'], 1),
          ('the delays', f"the median delay was {D['m7'][1]} s and the longest {D['m7'][2]} s", 1),
          ('the seed sweep', f"over {mc[0]} seeds the non-Omni lower end ran from {mc[1]} to {mc[2]}, and over "
                             f"{mc[3]} seeds Bitcoin's 90-day lower end ran from {mc[4]} to {mc[5]}", 1)]
    return e + list(D.get('explorer') or [])


def table_notes(D):
    """TABLE-NOTES.md, whole: the notes a reader needs beside the tables and charts, which stamped code writes."""
    n = D['notes']
    o = n['order']
    return f"""# Notes on the tables and charts

`out/published/tables.md` and the two charts are written by timestamped code (`publish/rule.py`), so they were not edited after the counted read. These notes say what a reader should know beside them. This file is generated by `publish/check_thesis.py` from the results and the saved rows, and `publish/written.py` checks it; it is not edited by hand.

1. **M8 is shown pooled.** `tables.md`, "M8: program expenditure per request", lines {n['m8_rows'][0]} to {n['m8_rows'][1]}, and chart 2's cost panel. The amounts for {D['testnet'][2]} 2026 include testnet payouts, and the calls are mainnet calls. On mainnet rows alone NEAR paid {D['m8_june'][0]} NEAR per request in June, {D['m8_main'][0]} in July and {D['m8_main'][1]} in August; the table shows {D['m8_june'][1]}, {D['m8_pooled'][0]} and {D['m8_pooled'][1]}. The other months have no testnet rows. `THESIS.md` §4.4 gives both sets for July to September.
2. **October's M8 row.** `tables.md` line {n['oct_row']}. The "0.00" is the amount executed. The {n['oct_pr']} beside it is the {n['oct_proposed']} NEAR of a proposed report, not yet executed, over October's calls.
3. **The "–" under main.** `tables.md`, "M3 and M4 by month", lines {n['dash'][0]} to {n['dash'][1]}, the {n['dash_n']} completed months before 2025-11. The dash means no point is printed, not that a window did not finish: for a month with no neardata sample the code prints main as a range with no point. FastAuth had no calls in those months' samples, so main equals narrow: the point is in the narrow column and the interval in the main column.
4. **The resolution audit.** `tables.md` line {n['audit_line']} says "{n['read']} transactions read whole, 0 differ". {n['drawn']} were drawn; one, `{n['miss_tx']}`, drew HTTP 429 on {n['miss_day']} and was not requested again, so it is not among the {n['read']}.
5. **Two months with exactly 100 calls.** May and July 2026 each had 100 `sign` calls in their six 60-second windows (`tables.md` lines {n['may_july'][0]}, {n['may_july'][1]}, {n['may_july'][2]} and {n['may_july'][3]}). The collector pages newest first and stops at the first page that holds a row older than the window's start; each of these 12 windows ends on such a page, so none was cut short. That stop rule is right only if the pages come newest first, so the order was counted: {o['with_pages']} of the {o['windows']} `sign` windows have saved pages (the other {o['windows'] - o['with_pages']} were not started before the deadline), {o['pages']} pages in all, and 0 pages hold a row newer than the row before it; of the {o['steps']} steps from one page to the next, 0 begin with a row newer than the page before ends with.
"""


def check(R, text, data_dir):
    D = derive(R, data_dir)
    bad = [(label, s, text.count(s)) for label, s, n in expected(D) if text.count(s) != n]
    notes = os.path.join(ROOT, 'TABLE-NOTES.md')
    if not os.path.exists(notes) or open(notes).read() != table_notes(D):
        bad.append(('TABLE-NOTES.md', 'differs from the text check_thesis.py generates', 0))
    for i, (k, name) in enumerate(TESTS, 1):   # each test's result, in the three places the page states it
        row = [l for l in text.split('\n') if l.startswith(f'| **{name}.**')]
        if len(row) != 1 or not row[0].endswith(f"| {D['status'][k]} |"):
            bad.append((f'{name}, the table of the tests in full', D['status'][k], len(row)))
        row = [l for l in text.split('\n') if l.startswith(f'| T{i} | {name} |')]
        if len(row) != 1 or not row[0].endswith(f"| {D['status'][k]} |"):
            bad.append((f'{name}, Table 1', D['status'][k], len(row)))
        row = [l for l in text.split('\n') if l.startswith(f'**T{i}, ')]
        if len(row) != 1 or not row[0].startswith(f"**T{i}, {D['status'][k]}.**"):
            bad.append((f'{name}, the line that opens its result', D['status'][k], len(row)))
    return D, bad


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[4] == '--notes':
        with open(sys.argv[1]) as f:
            sys.stdout.write(table_notes(derive(json.load(f), sys.argv[3])))
        raise SystemExit(0)
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    with open(sys.argv[1]) as f:
        R = json.load(f)
    with open(sys.argv[2]) as f:
        text = f.read()
    D, bad = check(R, text, sys.argv[3])
    if bad:
        for b in bad:
            print('MISMATCH', b)
        raise SystemExit(1)
    print(f'ok: {len(expected(D)) + len(TESTS)} statements match {sys.argv[1]}')
