"""The post-freeze rule for readings that rest on an unfinished stratum (POST-FREEZE.md, T-1).

  python3 -I publish/rule.py <instants.json> <data_dir> <out_dir>

This file is outside both frozen manifests and changes no frozen file. METHOD §6.10 says a measure
with an unfinished stratum is "never estimated from the part done", but the frozen code still writes
a number for it (analysis/core.py:168, :607-608) and the frozen charts draw it. The method governs:
everything the thesis shows a reader takes the values below, in which every reading that rests on
an unfinished stratum has no number.

It first runs the frozen command unchanged, `analysis/recompute.py <instants.json> <data_dir>
<out_dir>`, whose results.json, tables.md and charts are published as they are. It then applies the
rule to the results that command returns (in their original key order, as the frozen charts and
tables receive them). The rule uses only:
  - the frozen design (instants.json): each window's id, family, stratum, month and token;
  - whether each window is finished, by the frozen gate every measure uses,
    analysis/core.py `Study.window_complete` (a `completed` line in nb/windows.jsonl, its transaction
    resolution read, its pages a gapless chain). Nothing else about a window is used.

What it writes into <out_dir>/published/:
  results.json   the frozen results with the rule applied. A masked reading keeps its shape, every
                 value in it becomes null, and it carries "not_completed": true. "rule" lists what
                 was masked and why. Every value it lets through is the frozen value, unchanged.
  tables.md      the frozen analysis/recompute.py `tables()` on those results
  chart1-routes.svg, chart2-callers-cost.svg
                 the frozen analysis/charts.py on those results (it draws a null as absent), plus a
                 visible "not completed" mark and a footnote for every masked reading it would have
                 drawn. With nothing masked, tables.md and both charts equal the frozen output byte
                 for byte, and results.json differs only by "rule" and two lists of month names.
"""
import copy, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'analysis'))
import core  # noqa: E402
import charts  # noqa: E402
import recompute  # noqa: E402

NC = 'not_completed'
WORDS = 'not completed'
# keys that describe a reading rather than measure it: kept inside a masked reading
KEEP = frozenset({NC, 'month', 'days', 'flagged_days', 'complete', 'strata', 'tokens', 'token', 'state',
                  'verdict', 'verdict_given', 'attributed', 'range', 'provisional', 'chain', 'note'})
# M8: the HSP-007 ledger amounts do not rest on any window; only the per-request values do
M8_LEDGER = frozenset({'executed_near', 'executed_plus_pending_near', 'proposed_near', 'mainnet_executed_near',
                       'testnet_executed_near', 'nodes_paid_mainnet', 'reference_price_usd'})
M9_REFERENCE = frozenset({'V_usd', 'V_headline_usd'})  # NearStats' volume, from inputs/reference.json
# M1: what the reference and the design say about a chain, not what the sample saw
M1_DOCUMENTARY = frozenset({'documented', 'capability_omni_overview', 'measured_tokens'})
M1_FLOW = frozenset({'count_share', 'amount_share_by_unit', 'dominant_route', 'observed_in_flow'})  # flows only
# numbers a masked reading may keep: calendar days, which describe the month, not the sample
DESCRIPTIVE_NUMBERS = frozenset({'days', 'flagged_days'})
ND_ONLY = frozenset({'garwood_per_day', 'per_day', 'sampled_heights', 'sign_calls'})  # neardata side
TREND_READINGS = ('raw', 'excluding class 3 and 2a', 'excluding 2a only (class 3 kept)')


class RuleError(Exception):
    """The frozen flags and the windows disagree: stop and report, never guess."""


def _kept(k, x):
    """A describing key keeps its value inside a masked reading only if that value holds no count or
    measure (a list of token names does; census/tokens, a count per token, does not)."""
    return k in KEEP and (k in DESCRIPTIVE_NUMBERS or not _numbers(x, frozenset()))


def _null(v):
    if isinstance(v, dict):
        return {k: (x if _kept(k, x) else _null(x)) for k, x in v.items()}
    if isinstance(v, list):
        return [_null(x) for x in v] if any(isinstance(x, (dict, list)) for x in v) else None
    return None


def _numbers(v, allow, path=''):
    """Paths of numeric values (not bools) in v, outside the keys in allow."""
    out = []
    if isinstance(v, dict):
        for k, x in v.items():
            if k not in allow:
                out += _numbers(x, allow, f'{path}/{k}')
    elif isinstance(v, list):
        for i, x in enumerate(v):
            out += _numbers(x, allow, f'{path}/{i}')
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        out.append(path)
    return out


def unfinished(instants_path, data_dir):
    """The windows the frozen gate counts as not finished, and those of them that have a completed line."""
    S = core.Study(instants_path, data_dir)
    U = [w for w in S.windows if not S.window_complete(w)]
    gate_only = sorted(w['id'] for w in U if w['id'] in S.completed)
    return S.windows, U, gate_only


class Masker:
    def __init__(self, R):
        self.R = R
        self.masked = {}   # path -> reason

    def mask(self, node, path, reason, keep=KEEP):
        """Null every value in node except describing keys (KEEP, see _kept) and the named extra keys
        (keep - KEEP), which the caller names because they do not rest on the unfinished windows."""
        if not isinstance(node, dict):
            raise RuleError(f'{path}: expected a reading, found {type(node).__name__}')
        extra = keep - KEEP
        for k in list(node):
            if not (k in extra or _kept(k, node[k])):
                node[k] = _null(node[k])
        node[NC] = True
        self.masked.setdefault(path, reason)


def apply(results, windows, U, gate_only=()):
    """The rule. Returns the published results (a new object; `results` is not changed)."""
    R = copy.deepcopy(results)
    mk = Masker(R)
    Us = {w['stratum'] for w in U}
    fam = {}
    for w in U:
        fam[w['family']] = fam.get(w['family'], 0) + 1
    # the frozen completeness table counts the same windows (pending or not_completed)
    for f, c in R.get('completeness', {}).items():
        if c.get('pending', 0) + c.get('not_completed', 0) != fam.get(f, 0):
            raise RuleError(f'completeness/{f}: frozen counts {c} but the gate finds {fam.get(f, 0)} unfinished')
    sign_m = sorted({w['month'] for w in U if w['family'] == 'sign'})
    index_m = sorted({w['month'] for w in U if w['family'] == 'index'})
    flow_tok = {w['token'] for w in U if w['family'] == 'flow'}
    mig_tok = {w['token'] for w in U if w['family'] == 'migration'}
    census_short = any(w['family'] == 'census' for w in U)

    # sign months: M3, M4/M5, M8 per request, M6 purpose, the neardata rate check, and the trend
    def sign_rows(rows, base, by_month=False):
        items = rows.items() if by_month else enumerate(rows)
        for i, row in items:
            if row.get('month') in sign_m:
                yield f'{base}/{i}', row

    why_sign = 'a sign window of this month is unfinished'
    for base, rows, bm in (('M3', R.get('M3', []), False), ('by_month/M3', R.get('by_month', {}).get('M3', {}), True)):
        for p, row in sign_rows(rows, base, bm):
            for k in ('raw', 'without_sep29_oct4', 'failed_share'):
                if isinstance(row.get(k), dict):
                    mk.mask(row[k], f'{p}/{k}', why_sign)
    for base, rows, bm in (('M4_M5', R.get('M4_M5', []), False), ('by_month/M4', R.get('by_month', {}).get('M4', {}), True)):
        for p, row in sign_rows(rows, base, bm):
            mk.mask(row, p, why_sign)
    for base, rows, bm in (('M8/months', R.get('M8', {}).get('months', []), False),
                           ('by_month/M8', R.get('by_month', {}).get('M8', {}), True)):
        for p, row in sign_rows(rows, base, bm):
            for k in list(row):
                if (k == 'calls_in_month' or k.startswith('per_request_')) and isinstance(row[k], dict):
                    mk.mask(row[k], f'{p}/{k}', why_sign)
    if isinstance(R.get('M6'), dict):
        # the shares come from the neardata sample alone; only the rates per day use the month's sign calls
        for p, row in sign_rows(R['M6'].get('purpose', []), 'M6/purpose'):
            if isinstance(row.get('per_day'), dict) and row['per_day']:
                mk.mask(row['per_day'], f'{p}/per_day', why_sign)
        R['M6']['index_not_completed'] = index_m
    for p, row in sign_rows(R.get('nd_rate_check', []), 'nd_rate_check'):
        mk.mask(row, p, why_sign, keep=KEEP | ND_ONLY)
    tr = R.get('trend')
    if isinstance(tr, dict) and set(sign_m) & set(tr.get('A', []) + tr.get('B', [])):
        for k in TREND_READINGS:
            if isinstance(tr.get(k), dict):
                mk.mask(tr[k], f'trend/{k}', 'a sign month of the trend is unfinished')

    # migration (M10): the whole series if its early or late stratum is short; each monthly point alone
    for s, node in R.get('M10', {}).items():
        toks = node.get('tokens', [])
        series = {f'migration:{t}:early' for t in toks} | {f'flow:{t}:{p}' for t in toks for p in ('claim', 'outside')}
        if series & Us:
            mk.mask(node['readings'], f'M10/{s}/readings', 'an early or late stratum of the series is unfinished '
                    '(the whole measure, POST-FREEZE ruling)')
        for i, pt in enumerate(node.get('chart', [])):
            if {f"migration:{t}:chart:{pt.get('month')}" for t in toks} & Us:
                mk.mask(pt, f'M10/{s}/chart/{i}', 'this monthly window is unfinished')
        if set(toks) & mig_tok and isinstance(node.get('migration_window_counters'), dict):
            mk.mask(node['migration_window_counters'], f'M10/{s}/migration_window_counters',
                    'a migration window of the series is unfinished')

    # flows and census (tier 1): M9 rests on every flow stratum; chart 1 panel a and M1 per chain
    why_flow = 'a flow window is unfinished'
    if flow_tok:
        if isinstance(R.get('M9'), dict):
            mk.mask(R['M9'], 'M9', why_flow, keep=KEEP | M9_REFERENCE)
        v = R.get('mind', {}).get('value_mostly_on_omni')
        if isinstance(v, dict):
            mk.mask(v, 'mind/value_mostly_on_omni', why_flow, keep=KEEP | {'met'})
        for k in ('flow_quality', 'audit'):
            if isinstance(R.get(k), dict):
                mk.mask(R[k], k, why_flow)
    for i, row in enumerate(R.get('chart1_flows', [])):
        if set(row.get('tokens', [])) & flow_tok:
            mk.mask(row, f'chart1_flows/{i}', 'a flow window of this chain is unfinished')
    if census_short and isinstance(R.get('census'), dict):
        mk.mask(R['census'], 'census', 'a census window is unfinished', keep=KEEP | {'windows'})
    # M1: a chain's dominant route rests on its own flow strata; whether Omni is seen in use on it rests
    # on those and on the census. The counts over the 28 rest on every row, and the mind test on the
    # dominant routes.
    m1 = R.get('M1', {})
    obs_short = dom_short = False
    for i, row in enumerate(m1.get('chains', [])):
        if set(row.get('measured_tokens') or []) & flow_tok:
            mk.mask(row, f'M1/chains/{i}', 'a flow window of this chain is unfinished', keep=KEEP | M1_DOCUMENTARY)
            obs_short = dom_short = True
        elif census_short:
            mk.mask(row, f'M1/chains/{i}', 'a census window is unfinished (observed use only)',
                    keep=KEEP | M1_DOCUMENTARY | M1_FLOW)
            obs_short = True
    counts = m1.get('counts', {})
    for k, short, why in (('observed', obs_short, 'a census or flow window is unfinished'),
                          ('dominant', dom_short, 'a flow window is unfinished')):
        if short and isinstance(counts.get(k), dict):
            mk.mask(counts[k], f'M1/counts/{k}', why, keep=KEEP | {'of'})
    # The change-our-mind test keeps its frozen verdict: by DEVIATIONS item 21 an unfinished reading
    # leaves it undecided unless the decided readings settle it, and the frozen code counts a chain with
    # an unfinished flow stratum as undecided. Only its counts, which that window could still change, go.
    w = R.get('mind', {}).get('omni_dominant_widely')
    if dom_short and isinstance(w, dict):
        mk.mask(w, 'mind/omni_dominant_widely', 'a flow window is unfinished (the verdict stays, DEVIATIONS item 21)',
                keep=KEEP | {'of_measured', 'met'})

    # index: the picks come from completed months only (frozen); name the months that are not
    if isinstance(R.get('dest_audit_selection'), dict):
        R['dest_audit_selection']['not_completed_months'] = index_m

    # every remaining reading that lists an unfinished stratum, or that the frozen code itself
    # calls "not completed"
    def walk(v, path, under):
        if isinstance(v, dict):
            here = under or bool(v.get(NC))
            if not here:
                st = v.get('strata')
                if isinstance(st, list) and set(st) & Us:
                    mk.mask(v, path, 'it rests on an unfinished stratum')
                    here = True
                elif v.get('state') == WORDS and _numbers(v, KEEP):
                    mk.mask(v, path, 'the frozen code calls it not completed')
                    here = True
            for k, x in v.items():
                walk(x, f'{path}/{k}' if path else k, here)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, f'{path}/{i}', under)
    walk(R, '', False)

    # check: nothing the frozen code flags as not complete still shows a number
    allow = {'M8/months': KEEP | M8_LEDGER, 'by_month/M8': KEEP | M8_LEDGER, 'M9': KEEP | M9_REFERENCE,
             'census': KEEP | {'windows'}, 'M1/chains': KEEP | M1_DOCUMENTARY | M1_FLOW}
    bad = []

    def check(v, path):
        if isinstance(v, dict):
            if v.get('complete') is False or v.get('state') == WORDS or v.get('verdict') == WORDS:
                a = next((s for p, s in allow.items() if path == p or path.startswith(p + '/')), KEEP)
                if v.get('verdict') == WORDS and 'chart' in v:   # an M10 series: its points are judged alone
                    a = a | {'chart', 'migration_window_counters'}
                bad.extend(path + x for x in _numbers(v, a - {'tokens'}))   # a count per token is a measure
            for k, x in v.items():
                if k not in ('rule',):
                    check(x, f'{path}/{k}' if path else k)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                check(x, f'{path}/{i}')
    check(R, '')
    if bad:
        raise RuleError('a reading flagged not complete still has numbers: ' + ', '.join(bad[:20]))

    R['rule'] = {
        'source': 'POST-FREEZE.md, "Readings that rest on an unfinished stratum"',
        'unfinished_windows': len(U), 'unfinished_by_family': dict(sorted(fam.items())),
        'windows_total': len(windows), 'windows_by_family': dict(sorted(_count(windows).items())),
        'unfinished_strata': sorted(Us), 'unfinished_sign_months': sign_m, 'unfinished_index_months': index_m,
        'completed_line_but_gate_unfinished': list(gate_only),
        'masked': [{'path': p, 'reason': r} for p, r in sorted(mk.masked.items())],
        'n_masked_readings': sum(1 for p in mk.masked if not p.startswith('by_month/')),  # by_month repeats rows
    }
    return R


def _count(windows):
    c = {}
    for w in windows:
        c[w['family']] = c.get(w['family'], 0) + 1
    return c


# ---------------------------------------------------------------- tables and charts

def tables(R):
    """The frozen tables() on the ruled results. A masked count prints as a dash, like a masked share;
    a masked M1 route reads "not completed", the frozen code's own word. If anything was not completed,
    a last section lists the readings masked and why, and the signature-index months not completed."""
    V = copy.deepcopy(R)
    for row in V.get('M1', {}).get('chains', []):
        if row.get(NC):
            for k in ('observed_use', 'dominant_route'):
                if row.get(k) is None:
                    row[k] = WORDS
    t = recompute.tables(V).replace('None', '–')
    r = R.get('rule') or {}
    if not (r.get('unfinished_windows') or r.get('masked')):
        return t
    fam = ', '.join(f'{f} {n}' for f, n in r.get('unfinished_by_family', {}).items())
    L = ['', '## Not completed at the deadline', '',
         f"{r.get('unfinished_windows')} of {r.get('windows_total')} windows were not completed at the deadline "
         f"({fam}). A dash (–) or \"not completed\" above marks a reading that rests on one of them: by the "
         f"method it has no number (`POST-FREEZE.md`). The readings, each with the reason:", '']
    L += [f"- `{m['path']}`: {m['reason']}" for m in r.get('masked', []) if not m['path'].startswith('by_month/')]
    if r.get('unfinished_index_months'):
        L += ['', 'Signature-index months not completed at the deadline: '
              + ', '.join(r['unfinished_index_months']) + '.']
    return t.rstrip('\n') + '\n' + '\n'.join(L) + '\n'


def _height(svg):
    m = re.match(r'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 (\d+) ([\d.]+)"', svg)
    if not m:
        raise RuleError('unexpected chart header')
    return float(m.group(2))


def _rewrap(svg, extra, add_h):
    """The same chart with `extra` elements appended and add_h px more height below."""
    h = _height(svg)
    prefix = charts._wrap(charts.W, h, [])[:-len('</svg>')]
    if not (svg.startswith(prefix) and svg.endswith('</svg>')):
        raise RuleError('unexpected chart frame')
    body = svg[len(prefix):-len('</svg>')]
    return charts._wrap(charts.W, h + add_h, [body] + extra)


FOOT_CHARS = 150   # at 9 px a character is about 5 px wide, so a line stays inside the 912 px text width


def _wrap_note(s, n=FOOT_CHARS):
    out, cur = [], ''
    for word in s.split(' '):
        if cur and len(cur) + 1 + len(word) > n:
            out.append(cur)
            cur = '    ' + word
        else:
            cur = f'{cur} {word}' if cur else word
    return out + [cur]


def _foot(notes, h0):
    """Footnotes below the frozen chart's last line (which sits 18 px above its bottom), each wrapped.
    Returns the elements and the number of lines."""
    lines = [l for s in notes for l in _wrap_note(s)]
    return [charts._text(charts.PAD, h0 - 4 + 14 * j, s, 'mut', size=9) for j, s in enumerate(lines)], len(lines)


def mark_chart1(svg, R):
    marks, notes = [], []
    for s, node in R.get('M10', {}).items():
        whole = bool(node.get('readings', {}).get(NC))
        pts = [p['month'] for p in node.get('chart', []) if p.get(NC)]
        if not (whole or pts):
            continue
        found = re.findall(rf'<text x="{charts.PAD}" y="([\d.]+)" class="ink2" font-size="10" '
                           rf'text-anchor="start">{re.escape(charts._esc(s))}</text>', svg)
        if len(found) != 1:
            raise RuleError(f'chart 1: expected one row label for {s}, found {len(found)}')
        cyr = float(found[0]) - 3.5
        part = []
        if whole:
            # in the plot, 9 px above the row centre: clear of the monthly markers (radius 3.5 on the centre)
            marks.append(charts._text(charts.PAD + 112 + 6, cyr - 9, 'early and late: not completed', 'mut', size=8))
            part.append('early and late shares')
        if pts:
            # under the verdict, in its column (charts._chart1 panel b: verW 150)
            marks.append(charts._text(charts.W - charts.PAD - 150 + 10, cyr + 14.5,
                                      f'monthly: {len(pts)} not completed', 'mut', size=8))
            part.append('monthly ' + ', '.join(pts))
        notes.append(f'Not completed at the deadline, so not drawn — {s}: ' + '; '.join(part) + '.')
    chains = [r['chain'] for r in R.get('chart1_flows', []) if r.get(NC)]
    for c in chains:
        # panel a: the chain's label sits right-aligned before the bars; the row has no bar left
        found = re.findall(rf'<text x="{charts._nf(charts.PAD + 86 - 6)}" y="([\d.]+)" class="ink2" font-size="10" '
                           rf'text-anchor="end">{re.escape(charts._esc(c))}</text>', svg)
        if len(found) != 1:
            raise RuleError(f'chart 1: expected one route row label for {c}, found {len(found)}')
        marks.append(charts._text(charts.PAD + 86 + 6, float(found[0]), WORDS, 'mut', size=9))
    if chains:
        notes.append('Not completed at the deadline, so not drawn — routes for ' + ', '.join(chains) + '.')
    if not notes:
        return svg
    h0 = _height(svg)
    foot, n = _foot(notes, h0)
    return _rewrap(svg, marks + foot, 14 * n)


def mark_chart2(svg, R):
    rows = R.get('M4_M5', [])
    months = [str(r.get('month', '')) for r in rows]
    n = len(months)
    a_bottom = 56 + 150                     # charts._chart2: aTop 56, aH 150
    x0, x1 = charts.PAD + 48, charts.W - charts.PAD
    if n and f'<line x1="{charts._nf(x0)}" y1="{a_bottom}" x2="{charts._nf(x1)}" y2="{a_bottom}" class="axis"/>' not in svg:
        raise RuleError('chart 2: panel a axis not where expected')
    marks, notes = [], []
    gap = [i for i, r in enumerate(rows) if r.get(NC)]
    step = (x1 - x0) / n if n else 0
    for i in gap:
        cx = x0 + i * step + step / 2.0
        lab = f'{months[i]} (to T0)' if i == n - 1 else months[i]
        if not re.search(rf'<text x="{re.escape(charts._nf(cx))}" y="[\d.]+" class="mut" font-size="8" '
                         rf'text-anchor="end" transform="rotate\(-45 [^"]+\)">{re.escape(lab)}</text>', svg):
            raise RuleError(f'chart 2: month label {lab} not where expected')
        marks.append(charts._text(cx + 3, a_bottom - 4, WORDS, 'mut', size=9, rot=-90))
    if gap:
        notes.append('Not completed at the deadline, so no bars drawn: ' + ', '.join(months[i] for i in gap) + '.')
    pr = [r['month'] for r in R.get('M8', {}).get('months', [])
          if any(isinstance(v, dict) and v.get(NC) for k, v in r.items() if k.startswith('per_request_'))]
    if pr:
        # panel b (charts._chart2): its header line, then bTop = header + 14 and bBottom = bTop + 120
        hdr = re.findall(r'<text x="[\d.]+" y="([\d.]+)" class="ink" font-size="12" text-anchor="start" '
                         r'font-weight="600">b · Program expenditure per request', svg)
        if len(hdr) != 1:
            raise RuleError('chart 2: panel b header not where expected')
        b_bottom = float(hdr[0]) + 14 + 120
        if f'<line x1="{charts._nf(x0)}" y1="{charts._nf(b_bottom)}" x2="{charts._nf(x1)}" ' \
           f'y2="{charts._nf(b_bottom)}" class="axis"/>' not in svg:
            raise RuleError('chart 2: panel b axis not where expected')
        for mo in pr:
            if mo in months:
                i = months.index(mo)
                marks.append(charts._text(x0 + i * step + step / 2.0 + 3, b_bottom - 4, WORDS, 'mut', size=9, rot=-90))
        notes.append('Not completed at the deadline, so no per-request value drawn: ' + ', '.join(pr) + '.')
    if not notes:
        return svg
    h0 = _height(svg)
    foot, n = _foot(notes, h0)
    return _rewrap(svg, marks + foot, 14 * n)


def render(R, out_dir):
    view = json.loads(json.dumps(R))
    p1, p2 = charts.render(view, out_dir)
    for p, fn in ((p1, mark_chart1), (p2, mark_chart2)):
        with open(p) as f:
            svg = f.read()
        out = fn(svg, view)
        if out != svg:
            with open(p, 'w') as f:
                f.write(out)
    return [p1, p2]


def run(instants_path, data_dir, out_dir):
    res = recompute.run(instants_path, data_dir, out_dir)          # the frozen command, unchanged
    res = json.loads(json.dumps(res, default=recompute._jdefault))  # as charts.render receives it
    windows, U, gate_only = unfinished(instants_path, data_dir)
    R = apply(res, windows, U, gate_only)
    pub_out = os.path.join(out_dir, 'published')
    os.makedirs(pub_out, exist_ok=True)
    with open(os.path.join(pub_out, 'results.json'), 'w') as f:
        json.dump(R, f, indent=1, sort_keys=True)
    with open(os.path.join(pub_out, 'tables.md'), 'w') as f:
        f.write(tables(R))
    render(R, pub_out)
    return R


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    r = run(*sys.argv[1:4])['rule']
    print(json.dumps({k: r[k] for k in ('unfinished_windows', 'unfinished_by_family')}), len(r['masked']), 'readings masked')
