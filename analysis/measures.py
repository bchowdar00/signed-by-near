"""Stage-2 measures (METHOD §4 M1–M10b, §7 readings) on top of core.py.

Every function takes a core.Study and the frozen inputs and returns plain JSON-able dicts. The
interpretations METHOD leaves open are listed in DEVIATIONS.md (stage 2) and referred to here
as "interp. N". Nothing here reads anything but the study's data directory and the frozen inputs.
"""
import collections, json, math, os, random, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core  # noqa: E402
from core import Est, B, DAY  # noqa: E402
import intervals  # noqa: E402
import design  # noqa: E402

TAU = 0.90
TAUS_SENS = (0.80, 0.95)
SOLANA_SOL = ['sol.omft.near']
SOLANA_STABLE = ['sol-5ce3bf3a31af18be40ba30f721101b4341690186.omft.near',
                 'sol-c800a4bd850783ccb82c2b2c7e84175443606352.omft.near']
BTC = ['nbtc.bridge.near', 'btc.omft.near']
M10_SERIES = {'SOL': ['sol.omft.near'], 'ZEC': ['zec.omft.near'], 'BTC': ['btc.omft.near', 'nbtc.bridge.near'],
              'ETH (POA control)': ['eth.omft.near']}
TREND_A = ['2026-08', '2026-09', '2026-10']   # last 3 complete months before T0 (2026-11-10T11:00Z)
TREND_B = ['2026-05', '2026-06', '2026-07']   # the 3 months before them
SWEAT_END = 'sweat-relayer.near'
CLASS3_PLOT = ('ping-account.near', 'tx-bench.near')


def pub(r):
    """Drop private (Est) fields before writing results."""
    if isinstance(r, dict):
        return {k: pub(v) for k, v in r.items() if not k.startswith('_')}
    if isinstance(r, list):
        return [pub(x) for x in r]
    return r


def est_summary(e, alpha=core.ALPHA):
    lo, hi, dr = e.interval(alpha)
    return {'point': e.point, 'lo': lo, 'hi': hi, 'dropped': dr, 'unstable': dr > core.DROP_MAX * B}


# ---------------------------------------------------------------- strata helpers

def flow_strata(S, tokens, periods=('claim', 'outside')):
    return [S.stratum(f'flow:{t}:{p}') for t in tokens for p in periods]


def early_strata(S, tokens):
    return [S.stratum(f'migration:{t}:early') for t in tokens]


def chart_strata(S, tokens, ym):
    return [S.stratum(f'migration:{t}:chart:{ym}') for t in tokens if f'migration:{t}:chart:{ym}' in S.strata]


def add_usd(S, prices):
    """METHOD M9: each measured transfer valued at the frozen reference price of its unit group."""
    for w in S.windows:
        if w['family'] in ('flow', 'migration') and S.window_complete(w):
            ug = S.token_info.get(w['token'], {}).get('unit_group')
            for t in S.transfers(w):
                t['usd'] = t['units'] * prices[ug] if (t['units'] is not None and ug in prices) else None


def tokens_by_chain(S):
    out = collections.OrderedDict()
    for tok, info in S.token_info.items():
        out.setdefault(info['chain'], []).append(tok)
    return out


# ---------------------------------------------------------------- M2 / C2b

def share_reading(strata, tau=TAU, **kw):
    r = core.transfer_share(strata, **kw)
    r['state'] = core.state(r, tau)
    r['sensitivity_tau'] = {str(t): core.state(r, t) for t in TAUS_SENS}
    return r


def c2b(S):
    """METHOD M2 and §7 C2b. BTC gets states; Solana gets estimates only."""
    out = {}
    groups = {'BTC': (BTC, 'units', True), 'SOL': (SOLANA_SOL, 'units', False),
              'Solana stablecoins (USD)': (SOLANA_STABLE, 'units', False)}
    for g, (toks, kind, verdict) in groups.items():
        res = {}
        for period, ps in (('claim', ('claim',)), ('90d', ('claim', 'outside'))):
            st = flow_strata(S, toks, ps)
            for k in (kind, 'count'):
                for d in ('both', 'in', 'out'):
                    sel = None if d == 'both' else (lambda t, d=d: t['direction'] == d)
                    r = core.transfer_share(st, select=sel, kind=k)
                    key = f'{period}|{"amount" if k != "count" else "count"}|{d}'
                    if verdict:
                        r['state'] = core.state(r, TAU)
                        r['sensitivity_tau'] = {str(t): core.state(r, t) for t in TAUS_SENS}
                    res[key] = pub(r)
        prim = res['claim|amount|both']
        out[g] = {'tokens': toks, 'verdict_given': verdict, 'primary': prim, 'readings': res}
        if verdict:
            out[g]['verdict'] = prim['state']
    out['_note'] = ('Primary: claim window 2026-10-09 to 2026-11-06, amount share, deposits and withdrawals pooled, '
                    'tau 90%. Solana halves are estimates only (METHOD §7); no state is computed for them.')
    return out


# ---------------------------------------------------------------- M1

def census_chain(token, ref):
    if token in ref['census_exact']:
        return ref['census_exact'][token]
    for suf, ch in ref['census_suffix'].items():
        if token.endswith(suf):
            return ch
    m = re.match(r'^([a-z]+)(?:-[^.]+)?\.(?:omft|omdep)\.near$', token or '')
    if m and m.group(1) in ref['census_prefix']:
        return ref['census_prefix'][m.group(1)]
    return None


def census(S, ref):
    st = S.stratum('census')
    E = sum(st.covered[i] for i in range(len(st)))
    toks = collections.Counter()
    off = 0
    for v in st.values:
        toks.update(v['tokens'])
        off += v['off']
    chains = collections.Counter()
    unmapped = {}
    for t, n in toks.items():
        ch = census_chain(t, ref)
        if ch:
            chains[ch] += n
        else:
            unmapped[t] = n
    legs = core.total([st], lambda v: v['rows'])
    return {'complete': st.complete, 'windows': len(st), 'exposure_s': E,
            'detection_limit_per_day': core.rule_of_three(E) * DAY if E > 0 else None,
            'tokens': dict(toks), 'chains': dict(chains), 'unmapped_tokens': unmapped, 'rows_not_involving_intents': off,
            'omni_legs_with_intents_per_day': est_summary(legs / (st.windows[0]['D_s'] / DAY))}


def m1(S, ref, cen):
    names = {k: v[0] for k, v in ref['chain_names'].items()}
    by_chain = tokens_by_chain(S)
    rows = []
    for chain in ref['chains28']['union']:
        cid = next((k for k, v in names.items() if v == chain), None)
        toks = by_chain.get(cid, []) if cid else []
        row = {'chain': chain, 'documented': [k for k in ('omni', 'poa', 'hot') if chain in ref['chains28'][k]],
               'capability_omni_overview': chain in ref['capability13'], 'measured_tokens': toks}
        omni_seen_flow = False
        complete = True
        if toks:
            st = flow_strata(S, toks)
            complete = all(s.complete for s in st)
            omni_seen_flow = any(t['route'] == 'OMNI' for s in st for v in s.values for t in v)
            cnt = core.transfer_share(st, kind='count')
            groups = collections.defaultdict(list)
            for t in toks:
                groups[S.token_info[t]['unit_group']].append(t)
            amt = {g: core.transfer_share(flow_strata(S, ts), kind='units') for g, ts in groups.items()}
            row['count_share'] = pub(cnt)
            row['amount_share_by_unit'] = {g: pub(r) for g, r in amt.items()}
            parts = [cnt] + list(amt.values())
            if not complete:
                dom = 'not completed'
            elif any(p['sparse'] or p['unstable'] or p['L'] is None for p in parts):
                dom = 'unknown'
            elif all(p['L'] > 0.5 for p in parts):
                dom = 'yes'
            elif all(p['U'] < 0.5 for p in parts):
                dom = 'no'
            else:
                dom = 'unknown'
        else:
            dom = 'unknown'
        seen_census = cen['chains'].get(chain, 0) > 0
        if omni_seen_flow or seen_census:
            obs = 'yes'
        else:
            obs = 'not completed' if (not complete or not cen['complete']) else 'unknown'
        row.update({'observed_use': obs, 'observed_in_flow': omni_seen_flow, 'observed_in_census': seen_census,
                    'census_legs': cen['chains'].get(chain, 0), 'dominant_route': dom})
        if obs == 'unknown':
            row['detection_limit_per_day'] = cen['detection_limit_per_day']
        rows.append(row)
    counts = {}
    for lvl, key in (('observed', 'observed_use'), ('dominant', 'dominant_route')):
        yes = sum(1 for r in rows if r[key] == 'yes')
        unk = sum(1 for r in rows if r[key] in ('unknown', 'not completed'))
        counts[lvl] = {'unfavourable_yes': yes, 'favourable_yes_plus_unknown': yes + unk, 'of': len(rows)}
    counts['capability_documented'] = {'count': sum(r['capability_omni_overview'] for r in rows), 'of': len(rows),
                                       'note': 'documentary, not a ceiling'}
    return {'chains': rows, 'counts': counts, 'verdict': 'none (C1 is not identified by this design, METHOD §7)'}


# ---------------------------------------------------------------- M9 / C2a

def m9(S, ref):
    alltoks = list(S.token_info)
    st = flow_strata(S, alltoks)
    usd_ok = lambda t: t.get('usd') is not None
    p = core.transfer_share(st, select=usd_ok, kind='usd')
    pcs = core.transfer_share(st, select=usd_ok, kind='usd', num_pred=lambda t: t['direction'] == 'out')
    days = sum(s.windows[0]['D_s'] for s in st if s.name.startswith(f'flow:{alltoks[0]}:')) / DAY  # 28 + 56
    tot = core.total(st, lambda v: sum(t['usd'] for t in v if t['route'] != 'NEARSIDE' and usd_ok(t)))
    per30 = tot / days * 30.0
    V, VH = ref['V_usd'], ref['V_headline_usd']
    cV, c2V = per30 / V, core.emin(per30 / (2 * V), 1.0)
    cH = per30 / VH
    c = c2V.point
    scen = {'c_against_2V': c, 'S_U_favourable': (p['U'] * c + (1 - c)) if p['U'] is not None else None,
            'S_L_unfavourable': (p['L'] * c) if p['L'] is not None else None,
            'note': 'labelled scenarios, not bounds; c is not propagated (METHOD M9; interp. 7)'}
    non_lo = core.total(st, lambda v: sum(t['usd'] for t in v if t['route'] == 'POA' and usd_ok(t))) / days * 30.0
    non_hi = core.total(st, lambda v: sum(t['usd'] for t in v if t['route'] in ('POA', 'UNKNOWN') and usd_ok(t))) \
        / days * 30.0
    a, b = non_lo.interval(), non_hi.interval()
    non = {'point_unknown_omni': non_lo.point, 'point_unknown_not_omni': non_hi.point, 'lo': a[0], 'hi': b[1],
           'share_of_2V': {'point_lo': non_lo.point / (2 * V), 'point_hi': non_hi.point / (2 * V),
                           'lo': a[0] / (2 * V) if a[0] is not None else None,
                           'hi': b[1] / (2 * V) if b[1] is not None else None}}
    # second scenario, by chain
    by_chain = tokens_by_chain(S)
    nsname = {k: v[1] for k, v in ref['chain_names'].items()}
    rows, sv, svl, svu = [], 0.0, 0.0, 0.0
    for cid, toks in by_chain.items():
        r = core.transfer_share(flow_strata(S, toks), select=usd_ok, kind='usd')
        vch = ref['V_ch'].get(nsname[cid])
        in_m = (vch is not None and r['L'] is not None and r['U'] is not None and not r['sparse']
                and r['complete'])
        rows.append({'chain': nsname[cid], 'V_ch': vch, 'L': r['L'], 'U': r['U'], 'sparse': r['sparse'],
                     'complete': r['complete'], 'unstable': r['unstable'], 'in_M': in_m})
        if in_m:
            sv += vch
            svl += vch * r['L']
            svu += vch * r['U']
    c_ch = sv / V
    second = {'chains': rows, 'c': c_ch, 'p_L': svl / sv if sv else None, 'p_U': svu / sv if sv else None}
    if sv:
        second['S_L_unfavourable'] = second['p_L'] * c_ch
        second['S_U_favourable'] = second['p_U'] * c_ch + (1 - c_ch)
    return {'p': pub(p), 'p_CS': pub(pcs), 'measured_usd_per_30d': est_summary(per30), 'days_measured': days,
            'c_against_V': est_summary(cV), 'c_against_2V': est_summary(c2V), 'c_against_headline': est_summary(cH),
            'V_usd': V, 'V_headline_usd': VH, 'scenarios': scen, 'non_omni_usd_per_30d': non,
            'by_chain_scenario': second, 'complete': p['complete'], 'verdict': 'none (estimates only, METHOD §7)'}


def chart1_flows(S, ref):
    """Chart 1: measured value per 30 days by route for each measured chain (point estimates)."""
    by_chain = tokens_by_chain(S)
    nm = {k: v[0] for k, v in ref['chain_names'].items()}
    out = []
    for cid, toks in by_chain.items():
        st = flow_strata(S, toks)
        days = st[0].windows[0]['D_s'] / DAY + st[1].windows[0]['D_s'] / DAY
        row = {'chain': nm[cid], 'tokens': toks}
        for route in ('OMNI', 'POA', 'UNKNOWN'):
            e = core.total(st, lambda v, r=route: sum(t['usd'] for t in v if t['route'] == r and t.get('usd') is not None))
            row[route] = est_summary(e / days * 30.0)
        out.append(row)
    return out


# ---------------------------------------------------------------- M10, M10b

def diff_reading(late, early):
    """METHOD M10: late minus early, unknowns both ways; hull of the bootstrap (lower: late-as-not-Omni
    minus early-as-Omni; upper: the reverse) and [L_late - U_early, U_late - L_early]."""
    dL = late['_estL'] - early['_estU']
    dU = late['_estU'] - early['_estL']
    blo, bhi = dL.interval()[0], dU.interval()[1]
    if None in (late['L'], late['U'], early['L'], early['U']):
        return {'lo': None, 'hi': None}
    rlo, rhi = late['L'] - early['U'], late['U'] - early['L']
    lo = min(x for x in (blo, rlo) if x is not None)
    hi = max(x for x in (bhi, rhi) if x is not None)
    return {'boot': [blo, bhi], 'bound': [rlo, rhi], 'lo': lo, 'hi': hi, 'unstable': dL.unstable() or dU.unstable()}


def migration_state(late, early, d):
    if not (late['complete'] and early['complete']):
        return 'not completed'
    if late['sparse'] or early['sparse']:
        return 'not measurable'
    if d['lo'] is None or d['unstable'] or late['unstable'] or early['unstable']:
        return 'no clear move (unstable)'
    if d['lo'] > 0:
        return 'moving to Omni'
    if d['hi'] < 0:
        return 'moving away from Omni'
    return 'no clear move'


def m10(S):
    out = {}
    for name, toks in M10_SERIES.items():
        res = {}
        for kind in ('units', 'count'):
            late = core.transfer_share(flow_strata(S, toks), kind=kind)
            early = core.transfer_share(early_strata(S, toks), kind=kind)
            d = diff_reading(late, early)
            res['amount' if kind == 'units' else 'count'] = {
                'late': pub(late), 'early': pub(early), 'difference': d, 'state': migration_state(late, early, d)}
        chart = []
        for ym in design.CHART_MONTHS:
            cs = chart_strata(S, toks, ym)
            if not cs:
                continue
            ra = core.transfer_share(cs, kind='units')
            rc = core.transfer_share(cs, kind='count')
            chart.append({'month': ym, 'amount': {'unknown_not_omni': ra['point_unknown_not_omni'],
                                                  'unknown_omni': ra['point_unknown_omni']},
                          'count': {'unknown_not_omni': rc['point_unknown_not_omni'], 'unknown_omni': rc['point_unknown_omni']},
                          'transfers': rc['distinct_transfers'], 'complete': rc['complete']})
        edge = collections.Counter()
        for t in toks:
            for w in S.windows:
                if w['family'] == 'migration' and w['token'] == t and S.window_complete(w):
                    edge.update({k: v for k, v in S.transfer_counters(w).items() if k in ('edge_risk', 'mixed', 'net_zero')})
        out[name] = {'tokens': toks, 'verdict': res['amount']['state'], 'readings': res, 'chart': chart,
                     'migration_window_counters': dict(edge)}
    return out


def m10b(supply_rows):
    """Omni's share of bridged BTC on NEAR at each month start and T0 (rpc/supply.jsonl)."""
    by = collections.defaultdict(dict)
    for r in supply_rows:
        by[r['point']][r['token']] = r
    out = []
    for pt in sorted(by, key=lambda p: (p == 'T0', p)):
        a, b = by[pt].get('nbtc.bridge.near'), by[pt].get('btc.omft.near')
        if not a or not b:
            continue
        def val(r):
            if r['status'] == 'absent':
                return 0
            if r['status'] == 'value':
                return int(r['total_supply'])
            return None
        x, y = val(a), val(b)
        share = None if (x is None or y is None or x + y == 0) else x / (x + y)
        out.append({'point': pt, 'height': a['height'], 'omni_btc': None if x is None else x / 1e8,
                    'poa_btc': None if y is None else y / 1e8, 'omni_share': share,
                    'status': [a['status'], b['status']]})
    return out


# ---------------------------------------------------------------- sign: M3, M4, M5, trend

def classify(pred, registry):
    for r in registry['rules']:
        m, p = r['match'], r['pattern']
        if (m == 'exact' and pred == p) or (m == 'suffix' and pred.endswith(p)) or \
                (m == 'regex' and re.match(p, pred)) or (m == 'exact_set' and pred in p):
            return r['class']
    return '5'


def fastauth_subclass(signer, registry):
    sub = next(r for r in registry['rules'] if r['pattern'] == 'fast-auth.near')['subclass_by_transaction_signer']
    return (sub.get(signer) or sub['_default'])['subclass']


def sign_months(S):
    months = collections.OrderedDict()
    for name, ws in sorted(S.strata.items()):
        if ws[0]['family'] == 'sign':
            months.setdefault(ws[0]['month'], []).append(name)
    return months


class Signs:
    """Per-month sign strata and the per-class / per-caller totals every sign measure shares."""

    def __init__(self, S, registry, nd=None):
        self.S, self.reg = S, registry
        self.months = sign_months(S)
        self.strata = {m: [S.stratum(n) for n in names] for m, names in self.months.items()}
        self.days = {m: sum(s.windows[0]['D_s'] for s in st) / DAY for m, st in self.strata.items()}
        self.nd = nd or {}
        self._cls = {}

    def complete(self, m):
        return all(s.complete for s in self.strata[m])

    def tot(self, m, f):
        return core.total(self.strata[m], f)

    def all_calls(self, m):
        return self.tot(m, len)

    def by_class(self, m):
        if m not in self._cls:
            classes = sorted({classify(c['predecessor'], self.reg) for s in self.strata[m] for v in s.values for c in v}
                             | {'1', '2', '3', '4', '4x', '5'})
            self._cls[m] = {k: self.tot(m, lambda v, k=k: sum(1 for c in v if classify(c['predecessor'], self.reg) == k))
                            for k in classes}
        return self._cls[m]

    def callers(self, m):
        preds = sorted({c['predecessor'] for s in self.strata[m] for v in s.values for c in v})
        return {p: self.tot(m, lambda v, p=p: sum(1 for c in v if c['predecessor'] == p)) for p in preds}

    # -- FastAuth attribution from the neardata month sample (METHOD M4) --
    def nd_month(self, m):
        return self.nd.get(m)

    def signer_share(self, m, members):
        """Est of the share of FastAuth calls whose signer is in `members` (a set or a predicate), blocks
        resampled (stream 'boot-nd'), plus the block-level bound (interp. 8)."""
        blocks = self.nd_month(m)
        if blocks is None:
            return None, None
        inm = members if callable(members) else (lambda s: s in members)
        num = [sum(n for s, n in c.items() if inm(s)) for c in blocks]
        den = [sum(c.values()) for c in blocks]
        idx = core.draws_for(m, len(blocks), stream='boot-nd')
        point = core._div(sum(num), sum(den))
        draws = [core._div(sum(num[i] for i in ix), sum(den[i] for i in ix)) for ix in idx]
        bound = intervals.window_cp(point, [d for d in den if d > 0]) if point is not None else None
        return Est(point, draws), bound

    def attributed(self, m, F, members):
        """Calls attributed to FastAuth signers in `members`: F x share, 0 where F is 0."""
        sh, bound = self.signer_share(m, members)
        if sh is None:
            return None, None, None
        f = lambda a, b: 0.0 if a == 0 else (None if (a is None or b is None) else a * b)
        return Est(f(F.point, sh.point), [f(a, b) for a, b in zip(F.draws, sh.draws)]), sh, bound


def _share_with_bound(num, den, base_point=None, F_over_all=None, sbound=None):
    r = est_summary(num / den)
    if sbound is not None and F_over_all is not None:
        lo = (base_point or 0.0) + F_over_all * sbound[0]
        hi = (base_point or 0.0) + F_over_all * sbound[1]
        r['signer_bound'] = [lo, hi]
        r['lo'] = min(x for x in (r['lo'], lo) if x is not None)
        r['hi'] = max(x for x in (r['hi'], hi) if x is not None)
    return r


def m3(sg):
    out = []
    for m, st in sg.strata.items():
        raw = core.rate(st, len, lambda s, i: s.covered[i], sg.days[m])
        flag_days = core.overlap_s([month_extent_ns(sg.S, m)], core.FLAG_NS) / DAY
        row = {'month': m, 'days': sg.days[m], 'complete': sg.complete(m), 'raw': pub(raw)}
        if flag_days > 0:
            outside = lambda v: sum(1 for c in v if not (core.FLAG_NS[0] <= c['ts_ns'] < core.FLAG_NS[1]))
            expo = lambda s, i: s.covered[i] - core.overlap_s(s.segments[i], core.FLAG_NS)
            wo = core.rate(st, outside, expo, sg.days[m] - flag_days)
            row['without_sep29_oct4'] = pub(wo)
            row['flagged_days'] = flag_days
        fail = sg.tot(m, lambda v: sum(1 for c in v if c['ok'] is False))
        row['failed_share'] = est_summary(fail / sg.all_calls(m))
        out.append(row)
    return out


def month_extent_ns(S, m):
    """The part of calendar month m that the sign strata cover: [month start, min(next month, T0))."""
    a = design.month_start(m)
    b = min(design.month_start(design.next_month(m)), design.ts(S.meta['T0_utc'][:19] + 'Z'))
    return (int(round(a)) * 1_000_000_000, int(round(b)) * 1_000_000_000)


def m4_m5(sg):
    months = []
    for m in sg.strata:
        allc = sg.all_calls(m)
        cls = sg.by_class(m)
        F = cls['2']
        row = {'month': m, 'complete': sg.complete(m), 'calls_per_day': est_summary(allc / sg.days[m]),
               'attributed': sg.nd_month(m) is not None}
        shares = {}
        for k in ('1', '3', '4', '4x', '5', '2'):
            shares[k] = est_summary(cls[k] / allc)
        base = cls['4'] + cls['4x']
        if row['attributed']:
            sub_members, sub_bounds = {}, {}
            for sc in ('2a', '2b', '2c'):
                pred = (lambda s, sc=sc: fastauth_subclass(s, sg.reg) == sc)
                att, sh, bound = sg.attributed(m, F, pred)
                Fa = core._div(F.point, allc.point)
                shares[sc] = _share_with_bound(att, allc, 0.0, Fa, bound)
                shares[sc]['signer_share'] = est_summary(sh)
                shares[sc]['signer_bound'] = bound
                sub_members[sc] = att
                sub_bounds[sc] = bound
            main_pred = lambda s: fastauth_subclass(s, sg.reg) in ('2a', '2b')
            att, sh, bound = sg.attributed(m, F, main_pred)
            main = _share_with_bound(base + att, allc, core._div(base.point, allc.point),
                                     core._div(F.point, allc.point), bound)
            row['main'] = main
            # 2b is FastAuth-attributed, so its signer-share bound is carried into the hull (DEVIATIONS 9)
            row['main_without_sweat'] = _share_with_bound(base + sub_members['2b'], allc, core._div(base.point, allc.point),
                                                          core._div(F.point, allc.point), sub_bounds['2b'])
            row['fragility_sweat'] = shares['2a']
            row['nd_draws_dropped'] = sh.dropped() if sh is not None else None
        else:
            lo = est_summary(base / allc)
            hi = est_summary((base + F) / allc)
            row['main'] = {'range': 'FastAuth unattributed (no neardata sample)', 'lo': lo['lo'], 'hi': hi['hi'],
                           'none_in': lo, 'all_in': hi}
            row['main_without_sweat'] = row['main']
        row['narrow'] = est_summary(cls['4'] / allc)
        broad = allc - cls['1'] - cls['3']
        row['broad'] = est_summary(broad / allc)
        row['broad_class3_as_5'] = est_summary((allc - cls['1']) / allc)
        row['class_shares'] = shares
        row['per_day_by_class'] = {k: (cls[k] / sg.days[m]).point for k in cls}
        callers = sg.callers(m)
        row['per_day_class3_plot'] = {p: (callers[p] / sg.days[m]).point if p in callers else 0.0 for p in CLASS3_PLOT}
        row['concentration'] = concentration(sg, m, callers, F, allc)
        row['chart2_bands'] = chart2_bands(sg, m, cls, callers, shares, allc)
        months.append(row)
    return months


def chart2_bands(sg, m, cls, callers, shares, allc):
    """Chart 2: calls per day by band (point estimates), in a fixed order. FastAuth is split only in
    months with a neardata sample."""
    d = sg.days[m]
    pd = lambda e: (e / d).point if e is not None else None
    c3 = cls['3']
    ping = callers.get('ping-account.near', Est.const(0.0))
    bench = callers.get('tx-bench.near', Est.const(0.0))
    bands = collections.OrderedDict()
    bands['NEAR infrastructure (1)'] = pd(cls['1'])
    if '2a' in shares:
        tot = allc.point or 0.0
        bands['FastAuth: Sweat (2a)'] = shares['2a']['point'] * tot / d if shares['2a']['point'] is not None else None
        o = [shares[k]['point'] for k in ('2b', '2c')]
        bands['FastAuth: other apps (2b, 2c)'] = sum(o) * tot / d if None not in o else None
        bands['FastAuth: unattributed'] = 0.0
    else:
        bands['FastAuth: Sweat (2a)'] = 0.0
        bands['FastAuth: other apps (2b, 2c)'] = 0.0
        bands['FastAuth: unattributed'] = pd(cls['2'])
    bands['health check (ping-account.near)'] = pd(ping)
    bands['load test (tx-bench.near)'] = pd(bench)
    bands['other tests and demos (3)'] = pd(c3 - ping - bench)
    bands['independent apps (4)'] = pd(cls['4'])
    bands['Aurora XCC, owner not found (4x)'] = pd(cls['4x'])
    bands['unattributed (5)'] = pd(cls['5'])
    return bands


def concentration(sg, m, callers, F, allc):
    """M5: top-1 and top-3 callers' shares, callers being predecessors with fast-auth.near split by its
    signers where a neardata sample exists (interp. 5)."""
    parts = {p: e for p, e in callers.items() if p != 'fast-auth.near'}
    blocks = sg.nd_month(m)
    if 'fast-auth.near' in callers:
        if blocks is None:
            parts['fast-auth.near'] = callers['fast-auth.near']
        else:
            signers = sorted({s for c in blocks for s in c})
            for s in signers:
                att, _, _ = sg.attributed(m, F, {s})
                parts[f'fast-auth.near/{s}'] = att
            if not signers:
                parts['fast-auth.near (no signer sample)'] = callers['fast-auth.near']
    names = list(parts)

    def topk(vals, tot, k):
        if tot is None or tot == 0 or any(v is None for v in vals):
            return None
        return sum(sorted(vals, reverse=True)[:k]) / tot

    res = {}
    for k in (1, 3):
        pt = topk([parts[n].point for n in names], allc.point, k)
        dr = [topk([parts[n].draws[b] for n in names], allc.draws[b], k) for b in range(B)]
        res[f'top{k}'] = est_summary(Est(pt, dr))
    order = sorted(names, key=lambda n: -(parts[n].point or 0))
    res['top3_callers'] = [{'caller': n, 'share': core._div(parts[n].point, allc.point)} for n in order[:3]]
    return res


def trend(sg):
    def mean_rate(months, f):
        tot = Est.const(0.0)
        for m in months:
            tot = tot + f(m)
        return tot / sum(sg.days[m] for m in months)

    def raw(m):
        return sg.all_calls(m)

    def no3_2a(m):
        cls = sg.by_class(m)
        att = sg.attributed(m, cls['2'], lambda s: fastauth_subclass(s, sg.reg) == '2a')[0]
        return sg.all_calls(m) - cls['3'] - (att if att is not None else Est.const(None))

    def no2a(m):
        cls = sg.by_class(m)
        att = sg.attributed(m, cls['2'], lambda s: fastauth_subclass(s, sg.reg) == '2a')[0]
        return sg.all_calls(m) - (att if att is not None else Est.const(None))

    complete = all(sg.complete(m) for m in TREND_A + TREND_B)
    # removing class 2a needs each month's neardata signer shares; without them the reading is not completed
    nd_complete = all(sg.nd_month(m) is not None for m in TREND_A + TREND_B)
    out = {'A': TREND_A, 'B': TREND_B, 'complete': complete, 'neardata_complete': nd_complete}
    for name, f in (('raw', raw), ('excluding class 3 and 2a', no3_2a), ('excluding 2a only (class 3 kept)', no2a)):
        r = mean_rate(TREND_A, f) / mean_rate(TREND_B, f)
        s = est_summary(r)
        if not complete or (name != 'raw' and not nd_complete):
            s['state'] = 'not completed'
        elif s['unstable'] or s['lo'] is None:
            s['state'] = 'inconclusive'
        elif s['lo'] > 1:
            s['state'] = 'growing'
        elif s['hi'] < 1:
            s['state'] = 'shrinking'
        else:
            s['state'] = 'inconclusive'
        out[name] = s
    out['verdict'] = out['raw']['state']
    return out


# ---------------------------------------------------------------- neardata: M6, M7, rate cross-check

def nd_by_month(blocks, neardata):
    """{month: [Counter(signer -> FastAuth calls) per sampled present block]}."""
    months = sorted({b['part'].split(':', 1)[1] for b in blocks if b['part'].startswith('sample:')})
    return {m: neardata.fastauth_counts_by_block(blocks, m) for m in months}


def m6(blocks, neardata, sg, index_rows):
    out = {'purpose': [], 'index': []}
    by_block = collections.defaultdict(list)
    for c in neardata.sign_calls(blocks):
        if str(c.get('part', '')).startswith('sample:'):
            by_block[(c['part'].split(':', 1)[1], c['height'])].append(neardata.purpose_of(c))
    heights = collections.defaultdict(list)
    for b in blocks:
        if b['part'].startswith('sample:'):
            heights[b['part'].split(':', 1)[1]].append(b['height'])
    classes = ['secp256k1', 'ed25519_fastauth_login', 'ed25519_other_near', 'ed25519_other_solana',
               'ed25519_other_unknown', 'unparsed']
    for m in sorted(heights):
        hs = sorted(heights[m])
        per = [collections.Counter(by_block.get((m, h), [])) for h in hs]
        idx = core.draws_for(m, len(hs), stream='boot-nd')
        den = [sum(c.values()) for c in per]
        row = {'month': m, 'blocks': len(hs), 'sign_calls_in_sample': sum(den), 'share': {}, 'per_day': {}}
        for k in classes:
            num = [c.get(k, 0) for c in per]
            sh = Est(core._div(sum(num), sum(den)), [core._div(sum(num[i] for i in ix), sum(den[i] for i in ix)) for ix in idx])
            row['share'][k] = est_summary(sh)
            if m in sg.strata:
                row['per_day'][k] = est_summary(sh * (sg.all_calls(m) / sg.days[m]))
        out['purpose'].append(row)
    out['index'] = m6_index_only(index_rows)['index']
    return out


def m6_index_only(index_rows):
    """M6's descriptive list: completed signatures by destination chain and requesting account, per month."""
    return {'index': [{'month': m, 'rows': len(rows),
                       'dest_chain': dict(collections.Counter(r.get('dest_chain') for r in rows)),
                       'account': dict(collections.Counter(r.get('account_id') for r in rows))}
                      for m, rows in sorted(index_rows.items())]}


def nd_rate_check(blocks, nd_plan, sg):
    """METHOD Checks 1: neardata block-sample rate against M3, per month (a cross-check, not a validation)."""
    out = []
    bounds = nd_plan['bounds']
    keys = sorted(bounds)
    calls = collections.Counter()
    for b in blocks:
        if b['part'].startswith('sample:'):
            calls[b['part'].split(':', 1)[1]] += sum(1 for c in b['calls'] if c.get('method') == 'sign')
    for m, hs in sorted(nd_plan['sample'].items()):
        if m not in bounds:
            continue
        nxt = keys[keys.index(m) + 1] if keys.index(m) + 1 < len(keys) else None
        if nxt is None:
            continue
        h0, h1 = bounds[m]['height'], bounds[nxt]['height']
        days = (bounds[nxt]['ts_ns'] - bounds[m]['ts_ns']) / 1e9 / DAY
        per_height = calls[m] / len(hs)
        k = calls[m]
        lo, hi = core.garwood(k)
        f = (h1 - h0) / days / len(hs)
        out.append({'month': m, 'sampled_heights': len(hs), 'sign_calls': k, 'per_day': per_height * (h1 - h0) / days,
                    'garwood_per_day': [lo * f, hi * f],
                    'm3_per_day': (sg.all_calls(m) / sg.days[m]).point if m in sg.strata else None})
    return out


# ---------------------------------------------------------------- M8

def m8(sg, hsp, table, operators_rows):
    pm = hsp.per_month(table)
    rows = []
    for m in sorted(pm):
        if m not in sg.strata:
            continue
        r = pm[m]
        calls = sg.all_calls(m)
        ex = float(r['executed_near'])
        expd = float(r['executed_near'] + r['pending_near'])
        prop = float(r['proposed_near'])
        row = {'month': m, 'provisional': bool(r['provisional']), 'complete': sg.complete(m),
               'executed_near': ex, 'executed_plus_pending_near': expd, 'proposed_near': prop,
               'mainnet_executed_near': float(r['mainnet_executed_near']),
               'testnet_executed_near': float(r['testnet_executed_near']),
               'nodes_paid_mainnet': r['nodes_paid_mainnet'],
               'reference_price_usd': [float(p) for p in r['reference_price_usd']],
               'calls_in_month': est_summary(calls)}
        for key, num in (('per_request_executed', ex), ('per_request_executed_plus_pending', expd),
                         ('per_request_proposed', prop)):
            if num > 0:
                e = num / calls
                row[key] = est_summary(e)
                row[key + '_usd'] = {str(p): est_summary(e * p) for p in row['reference_price_usd']}
        rows.append(row)
    rec = hsp.reconcile(pm, operators_rows) if operators_rows else None
    ex_m = sorted(m for m, r in pm.items() if r['executed_near'] > 0)
    totals = {'executed_near': float(sum(r['executed_near'] for r in pm.values())),
              'pending_near': float(sum(r['pending_near'] for r in pm.values())),
              'proposed_near': float(sum(r['proposed_near'] for r in pm.values())),
              'executed_first_month': ex_m[0] if ex_m else None, 'executed_last_month': ex_m[-1] if ex_m else None,
              'proposed_months': sorted(m for m, r in pm.items() if r['proposed_near'] > 0)}
    return {'months': rows, 'reconcile': rec, 'totals': totals}


# ---------------------------------------------------------------- data-quality figures

def flow_quality(S):
    agg = collections.Counter()
    refund_pairs, transfers = 0, 0
    for w in S.windows:
        if w['family'] != 'flow' or not S.window_complete(w):
            continue
        agg.update(S.transfer_counters(w))
        tr = sorted(S.transfers(w), key=lambda t: t['ts_ns'])
        transfers += len(tr)
        used = set()
        for i, a in enumerate(tr):
            if a['direction'] != 'out':
                continue
            for j in range(i + 1, len(tr)):
                b = tr[j]
                if j not in used and b['direction'] == 'in' and b['amount'] == a['amount'] and b['route'] == a['route']:
                    used.add(j)
                    refund_pairs += 1
                    break
    return {'counters': dict(agg), 'transfers': transfers, 'possible_refund_pairs': refund_pairs,
            'possible_refund_pair_share': (2 * refund_pairs / transfers) if transfers else None}


def completeness(S):
    out = collections.defaultdict(lambda: collections.Counter())
    for w in S.windows:
        k = 'completed' if S.window_complete(w) else ('not_completed' if w['id'] in S.not_completed else 'pending')
        out[w['family']][k] += 1
    return {f: dict(c) for f, c in out.items()}


def dest_audit_selection(index_rows):
    """§6.7: 10 Omni BTC and 10 ZEC withdrawals from the index rows, seeded ('dest-audit'); the explorer
    lookups are a manual check recorded beside the selection (interp. 9)."""
    rows = [r for m in sorted(index_rows) for r in index_rows[m]]
    btc = sorted([r for r in rows if r.get('dest_chain') == 'BITCOIN' and str(r.get('account_id', '')).endswith('.bridge.near')],
                 key=lambda r: r['receipt_id'])
    zec = sorted([r for r in rows if r.get('dest_chain') == 'ZCASH'], key=lambda r: r['receipt_id'])
    rng = random.Random(design.seed_for('dest-audit'))
    pick = lambda xs: [{k: r.get(k) for k in ('receipt_id', 'account_id', 'dest_chain', 'dest_txn', 'dest_address')}
                       for r in rng.sample(xs, min(10, len(xs)))]
    return {'bitcoin': pick(btc), 'zcash': pick(zec), 'available': {'bitcoin': len(btc), 'zcash': len(zec)}}


# ---------------------------------------------------------------- what would change our mind

MIND_LAST3_EXECUTED = ['2026-07', '2026-08', '2026-09']


def _all_of(parts):
    """Parts that must all hold: False if any is decided False, None if any is undecided, else True."""
    if any(x is False for x in parts):
        return False
    if any(x is None for x in parts):
        return None
    return True


def _share_undecided(r):
    return (not r.get('complete', True)) or bool(r.get('sparse')) or bool(r.get('unstable')) or r.get('L') is None


def _est_undecided(e):
    return e is None or e.get('unstable') or e.get('lo') is None or e.get('hi') is None or e.get('point') is None


def _falling(rows, trend_raw):
    """Spend per request falls month on month (each interval wholly below the one before) while the
    raw trend grows. rows: (complete, est) per month in order."""
    parts = []
    for (ca, a), (cb, b) in zip(rows, rows[1:]):
        if not (ca and cb) or _est_undecided(a) or _est_undecided(b):
            parts.append(None)
        else:
            parts.append(bool(b['point'] < a['point'] and b['hi'] < a['lo']))
    st = (trend_raw or {}).get('state')
    if st == 'growing':
        parts.append(True)
    elif st == 'shrinking' or (st == 'inconclusive' and not _est_undecided(trend_raw)):
        parts.append(False)
    else:  # not completed, or inconclusive because unstable
        parts.append(None)
    return _all_of(parts)


def mind(res):
    """The sketch's change-our-mind tests (THESIS-b-SKETCH, written 2026-11-10T05:54Z, before the counted
    sample), computed from the frozen readings. Each test's 'met' is True (met: the sketch's claim is wrong
    on that point), False (not met) or None (undecided: a reading it needs is not completed, not
    measurable or unstable, and the decided readings do not settle it). DEVIATIONS 21."""
    out = {}
    # 1. measured value mostly on Omni: p's L >= 90% and the measured non-Omni value's upper end < 10% of 2V
    m9 = res.get('M9', {})
    p, non = m9.get('p', {}), m9.get('non_omni_usd_per_30d', {}).get('share_of_2V', {})
    a = None if (not m9.get('complete') or _share_undecided(p)) else bool(p['L'] >= 0.90)
    b = None if (not m9.get('complete') or non.get('hi') is None) else bool(non['hi'] < 0.10)
    out['value_mostly_on_omni'] = {'met': _all_of([a, b]), 'p_L': p.get('L'), 'non_omni_hi_share_of_2V': non.get('hi')}
    # 2. Omni dominant (M1 'yes') on at least 5 of the measurable chains
    chains = [c for c in res.get('M1', {}).get('chains', []) if c.get('measured_tokens')]
    yes = sum(1 for c in chains if c['dominant_route'] == 'yes')

    def undecided_chain(c):
        if c['dominant_route'] == 'not completed':
            return True
        if c['dominant_route'] != 'unknown':
            return False
        parts = [c.get('count_share') or {}] + list((c.get('amount_share_by_unit') or {}).values())
        return any(_share_undecided(x) for x in parts)
    und = sum(1 for c in chains if undecided_chain(c))
    met = True if yes >= 5 else (False if yes + und < 5 else None)
    out['omni_dominant_widely'] = {'met': met, 'dominant_yes': yes, 'undecided': und, 'of_measured': len(chains)}
    # 3. broad adoption: main classification without Sweat >= 25%, lower end >= 15%, in each of Aug-Oct 2026
    m4 = {r['month']: r for r in res.get('M4_M5', [])}
    parts = []
    for m in TREND_A:
        r = m4.get(m)
        e = (r or {}).get('main_without_sweat')
        if r is None or not r.get('complete') or _est_undecided(e):
            parts.append(None)
        else:
            parts.append(bool(e['point'] >= 0.25 and e['lo'] >= 0.15))
    out['broad_adoption'] = {'met': _all_of(parts), 'months': TREND_A}
    # 4. falling spend per request over the last three executed months, while the trend grows
    m8 = {r['month']: r for r in res.get('M8', {}).get('months', [])}
    tr = res.get('trend', {}).get('raw')
    rows = [(bool(m8.get(m, {}).get('complete')), m8.get(m, {}).get('per_request_executed_plus_pending'))
            for m in MIND_LAST3_EXECUTED]
    rows_ex = [(bool(m8.get(m, {}).get('complete')), m8.get(m, {}).get('per_request_executed'))
               for m in MIND_LAST3_EXECUTED]
    out['falling_spend_per_request'] = {'met': _falling(rows, tr), 'numerator': 'executed plus pending',
                                        'months': MIND_LAST3_EXECUTED,
                                        'executed_only': {'met': _falling(rows_ex, tr)}}
    # 5. no migration: no clear move to Omni for SOL, ZEC and BTC
    states = {s: res.get('M10', {}).get(s, {}).get('verdict') for s in ('SOL', 'ZEC', 'BTC')}
    if any(v == 'moving to Omni' for v in states.values()):
        met = False
    elif any(v in (None, 'not completed', 'not measurable', 'no clear move (unstable)') for v in states.values()):
        met = None
    else:
        met = True
    out['no_migration'] = {'met': met, 'states': states}
    return out
