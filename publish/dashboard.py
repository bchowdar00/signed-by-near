"""Writes docs/: the static dashboard page, the write-up as a page in the same colours, a title banner, and the
two charts as byte copies with a recoloured copy of each.

  python3 -I publish/written.py <data_dir>      (calls this after its checks pass)
  python3 -I publish/dashboard.py <data_dir>    (the page alone, after the same checks)

docs/index.html shows the five tests, the 28 chains the partner names, and each chart with the query
behind it and one sentence on what it shows. Nothing on it is typed: every figure is read from
out/combined.json with the formatter the write-up uses (publish/fill.py), the five tests' lines and the
answer are lifted from THESIS.md, the counts stated in words come from publish/check_thesis.py, and the notes
are TABLE-NOTES.md's. A reading that was not completed stops the build; none is drawn as if it were known.
The two charts are copied unchanged from out/published/, where the timestamped code wrote them; the recoloured
copies differ from them in the style block only, which is checked. The grid of 28 chains is drawn here, after
the counted read, from M1's rows. docs/thesis.html is THESIS.md set as a page: the same words in the same
order, which is checked too.

It makes no network call, needs no script to read, and is in no manifest. The page carries no build time, so
the same inputs give the same bytes.
"""
import hashlib, html, json, os, re, shutil, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fill as F  # noqa: E402
import check_thesis as C  # noqa: E402

DOCS = os.path.join(ROOT, 'docs')
CHARTS = ('chart1-routes.svg', 'chart2-callers-cost.svg')
NOTE_AT = {1: '2b', 2: '2b', 3: '2a', 4: 'sample', 5: '2a'}     # which panel each note of TABLE-NOTES.md sits beside


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def val(R, path, f):
    """One reading, formatted as the write-up formats it. A reading not completed stops the build."""
    v, masked = F.resolve(R, path)
    out = F.fmt(v, f)
    if masked or out is None:
        raise SystemExit(f'the dashboard needs a reading that is not completed: {path}')
    return out


def iv(R, path, f=None):
    """An interval as the write-up prints it: percentages by fill.py's own format, anything else end by end."""
    if f is None:
        return val(R, path, 'iv1')
    return f"[{val(R, path + '/lo', f)}, {val(R, path + '/hi', f)}]"


def md(s):
    """The little Markdown the lifted lines use: `code` and **bold**."""
    s = html.escape(s, quote=False)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    return re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)


GROUPS_OF_TESTS = (('T1 to T3 would have shown a broad moat', 3),
                   ('T4 and T5 would have changed the read on cost and on direction', 2))


def lifted(thesis):
    """What the page takes from THESIS.md's first screen, as it stands there: the title, the subtitle, the answer,
    with its five points, the claim, the dated lines on what was fixed when, the paragraph on the pilot, the two
    groups of tests with each test's needed and found, the count of the five, and the three dated next reads
    (written after the counted read) with the sentence before and after them."""
    lines = thesis.split('\n')
    one = lambda prefix: next(l for l in lines if l.startswith(prefix))
    title = lines[0].lstrip('# ').strip()
    sub = next(l for l in lines[1:] if l.startswith('*')).strip('*')
    answer = one('**Narrow today')
    j = lines.index(answer) + 1
    while not lines[j].strip():
        j += 1
    points = []
    for l in lines[j:]:
        if not l.startswith('- **'):
            break
        points.append(l[2:])
    assert len(points) == 5 and points[0].startswith('**On Bitcoin') and points[4].startswith('**What a holder watches next.**'), points
    claim = one('**The claim under test:**')
    i = lines.index(one('### 3.4 What was fixed, and when'))
    while not lines[i + 1].startswith('- **'):
        i += 1
    when = []
    for l in lines[i + 1:]:
        if not l.startswith('- **'):
            break
        when.append(l[2:])
    when = when[:3]            # the three dated lines; the two that follow them are method, not dates
    assert len(when) == 3 and when[0].startswith('**Nov 10.**') and when[2].startswith('**Nov 13.**'), when
    pilot = one('The claim and the tests were both written after an uncounted pilot')
    groups, k = [], 0
    under = one('T1 to T3 would have shown a broad moat; ')      # the sentence under Table 1, which ends with the count
    for head, n in GROUPS_OF_TESTS:
        assert under.count(head) == 1, head
        rows = []
        for key, name in C.TESTS[k:k + n]:
            row = [l for l in lines if l.startswith(f'| T{k + len(rows) + 1} | {name} | ')]
            assert len(row) == 1, name
            cells = [c.strip() for c in row[0].strip('|').split(' | ')]
            assert len(cells) == 5, cells
            needed, found = cells[2], cells[3]
            rows.append((key, f'{cells[0]}. {name}', needed[0].upper() + needed[1:] + '.', found[0].upper() + found[1:] + '.'))
        groups.append((head + '.', rows))
        k += n
    assert k == len(C.TESTS)
    count = under[under.index('All five frozen tests read not met'):]
    head = '**What to watch, and when.** '
    w = lines.index(one(head))
    watch = []
    for l in lines[w + 1:]:
        if not l.startswith('- **'):
            break
        watch.append(l[2:])
    assert len(watch) == 3 and watch[0].startswith('**January 2027'), watch
    after = one('If all three read as expected')
    assert lines.index(after) == w + len(watch) + 2, 'the closing sentence follows the three reads'
    page = lambda t: re.sub(r'§([0-9][0-9.]*[0-9]|[0-9])', r'`THESIS.md` §\1', t)     # a section number means the page's section
    points, when, watch = [page(x) for x in points], [page(x) for x in when], [page(x) for x in watch]
    return title, sub, answer, points, claim, when, page(pilot), groups, count, (page(lines[w][len(head):]), watch, after)


def notes(text):
    out = {}
    for l in text.split('\n'):
        m = re.match(r'^(\d+)\. (.*)$', l)
        if m:
            out[int(m.group(1))] = m.group(2)
    assert out, 'TABLE-NOTES.md has its numbered notes'
    return out


def notes_for(N, where):
    got = [(k, v) for k, v in sorted(N.items()) if NOTE_AT.get(k, 'sample') == where]
    if not got:
        return ''
    items = ''.join(f'<li><span class="nn">Note {k}.</span> {md(v)}</li>' for k, v in got)
    return f'<aside class="notes"><h4>Read beside this</h4><ul>{items}</ul></aside>'


# ------------------------------------------------------------------------------------------ the 28 chains
GROUPS = [('dom', 'Omni is the dominant route',
           'The lower end of Omni\'s share is above half, by count and by amount (the rule fixed in <code>METHOD.md</code>, M1).'),
          ('use', 'Omni seen in use, not shown dominant',
           'At least one Omni transfer was seen, in the measured flow or in the census of Omni\'s own legs with Intents.'),
          ('poa', 'Measured, no Omni transfer seen',
           'Every measured transfer moved on the custodial POA bridge. The method calls Omni\'s place here unknown, not absent: '
           'the interval\'s upper end reflects how few windows were read.'),
          ('unk', 'Not read by this sample',
           'No token of the chain can be read through these sources, so only its documented route is shown. Not seen is not the same as absent.')]


def group_of(c):
    if c['dominant_route'] == 'yes':
        return 'dom'
    if c['observed_use'] == 'yes':
        return 'use'
    return 'poa' if c['measured_tokens'] else 'unk'


def bar(R, i, c, unit):
    p = f'M1/chains/{i}/amount_share_by_unit/{unit}'
    u = c['amount_share_by_unit'][unit]
    lo, hi, pt = u['L'], u['U'], u['point_unknown_not_omni']
    label = f"{unit} {val(R, p + '/point_unknown_not_omni', 'pct1')} [{val(R, p + '/L', 'pct1')}, {val(R, p + '/U', 'pct1')}]"
    return (f'<div class="track" role="img" aria-label="Omni\'s share of measured {unit} by amount: {html.escape(label)}">'
            f'<span class="rng" style="left:min({lo * 100:.2f}%, calc(100% - 4px));width:{(hi - lo) * 100:.2f}%"></span>'
            f'<span class="pt" style="left:calc({pt * 100:.2f}% - 5px)"></span></div>'
            f'<div class="cv">{html.escape(label)}</div>')


def cell(R, i, c):
    g = group_of(c)
    body = ''
    if c['measured_tokens']:
        body += ''.join(bar(R, i, c, unit) for unit in c['amount_share_by_unit'])
    if c['observed_in_census']:
        legs = 'leg' if c['census_legs'] == 1 else 'legs'
        body += f"<div class=\"cv\">census: {val(R, f'M1/chains/{i}/census_legs', 'int')} Omni {legs} with Intents</div>"
    doc = ', '.join(c['documented'])
    return (f'<li class="cell g-{g}"><div class="cn"><span class="sw sw-{g}" aria-hidden="true"></span>{html.escape(c["chain"])}</div>'
            f'{body}<div class="cd">documented route: {html.escape(doc)}</div></li>')


def groups(R):
    chains = R['M1']['chains']
    by = {g: [(i, c) for i, c in enumerate(chains) if group_of(c) == g] for g, _, _ in GROUPS}
    counts = R['M1']['counts']
    assert len(by['dom']) == counts['dominant']['unfavourable_yes']
    assert len(by['dom']) + len(by['use']) == counts['observed']['unfavourable_yes']
    assert sum(len(v) for v in by.values()) == counts['observed']['of'] == len(chains)
    return by


def grid(R, D):
    chains = R['M1']['chains']
    by = groups(R)
    assert sorted(c['chain'] for _, c in by['poa']) == sorted(D['poa_names'].replace(' and ', ', ').split(', '))
    out = []
    for g, name, what in GROUPS:
        cells = ''.join(cell(R, i, c) for i, c in by[g])
        out.append(f'<section class="grp"><h3><span class="sw sw-{g}" aria-hidden="true"></span>{name} '
                   f'<span class="ct">{len(by[g])} of {len(chains)}</span></h3><p class="what">{what}</p>'
                   f'<ul class="cells">{cells}</ul></section>')
    return ''.join(out), {g: len(v) for g, v in by.items()}, len(chains)


# ------------------------------------------------------------------------------------------ the panels
def limit():
    with open(os.path.join(ROOT, 'collector', 'sampler.py')) as f:
        return re.search(r'^LIMIT = (\d+)$', f.read(), re.M).group(1)


def panel(letter, title, shows, query, how, extra=''):
    return (f'<article class="panel"><h3><span class="pl">{letter}</span>{title}</h3>'
            f'<p class="shows">{shows}</p>'
            f'<h4>The query behind it</h4><pre class="q">{html.escape(query)}</pre>'
            f'<p class="how">{how}</p>{extra}</article>')


def panels(R, D, N):
    L = limit()
    nb = 'https://api.nearblocks.io/v3'
    chains = R['M1']['chains']
    n_tok = sum(len(c['measured_tokens']) for c in chains)
    n_ch = sum(1 for c in chains if c['measured_tokens'])
    series = list(R['M10'].keys())
    undone = [k for k in series if F.resolve(R, f'M10/{k}/readings/amount/late')[1]]
    states = R['mind']['no_migration']['states']
    assert states['BTC'] == 'moving to Omni' and 'BTC' not in undone and len(undone) == len(series) - 1
    m = D['m10b']
    oct4 = 'by_month/M4/2026-10'
    sep8 = 'by_month/M8/2026-09/per_request_executed_plus_pending'
    months = [('June', D['m8_june'][1], D['m8_june'][0])] + [
        (name, pooled, main) for name, pooled, main in zip(('July', 'August', 'September'), D['m8_pooled'], D['m8_main'])]
    m8_table = ('<table class="t"><caption>NEAR paid per <code>sign</code> request, 2026 (executed plus pending)</caption>'
                '<thead><tr><th>Month</th><th>As charted (testnet rows pooled in)</th><th>Mainnet rows only</th></tr></thead><tbody>'
                + ''.join(f'<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>' for a, b, c in months) + '</tbody></table>')
    one = [
        panel('1a', 'Routes by chain',
              f"Of the value this sample measured, Omni carried {val(R, 'M9/p/point_unknown_not_omni', 'pct1')} "
              f"{iv(R, 'M9/p')} over the 90 days; on {D['poa_names']} none of the measured value moved on Omni.",
              f"GET {nb}/fts/<token>/txns?limit={L}&before_ts=<window end>\n    newest first; later pages follow the API's own cursor, back to the start of each window\n"
              f"    {n_tok} tokens on {n_ch} chains; the windows were drawn by seed before collection began (frozen/instants.json)",
              'A transfer\'s route is read from the counterparties of Intents\' legs in it (<code>METHOD.md</code> §3). '
              'Computed by <code>chart1_flows</code>, <code>m1</code> and <code>m9</code> in <code>analysis/measures.py</code>.'),
        panel('1b', 'Migration, early to late',
              f"Bitcoin is the one series with both readings: Omni's share of Intents' bridged BTC went from "
              f"{iv(R, 'M10/BTC/readings/amount/early')} in early 2025 to {iv(R, 'M10/BTC/readings/amount/late')} in the 90 days "
              f"to T0. For {', '.join(undone[:-1])} and {undone[-1]} the comparison could not be made, because windows it rests on did not finish before the deadline, so they are not drawn.",
              f"GET {nb}/fts/<token>/txns?limit={L}&before_ts=<window end>\n    the same call: for each series an early stratum of windows and the 90-day flow windows,\n"
              f"    and one window in every other month for the monthly points",
              'Computed by <code>m10</code> in <code>analysis/measures.py</code>; the rule for readings not completed is '
              '<code>publish/rule.py</code> (<code>POST-FREEZE.md</code>).'),
        panel('1c', 'Omni\'s share of bridged BTC on NEAR, by supply',
              f"Omni's share of all bridged BTC on NEAR did not climb steadily: {val(R, 'M10b/0/omni_share', 'pct1')} at the "
              f"start of 2025, {val(R, 'M10b/%d/omni_share' % m['2025-07'], 'pct1')} in July 2025, "
              f"{val(R, 'M10b/%d/omni_share' % m['2026-03'], 'pct1')} in March 2026 and {val(R, 'M10b/-1/omni_share', 'pct1')} at T0. "
              f"The fall is not explained here.",
              "POST https://archival-rpc.mainnet.fastnear.com\n    query call_function ft_total_supply, block_id = the first block of each month and T0's\n"
              "    on nbtc.bridge.near (Omni) and btc.omft.near (POA)",
              'A stock, not a flow, and all of NEAR, not only Intents. Computed by <code>m10b</code> in <code>analysis/measures.py</code>.'),
    ]
    two = [
        panel('2a', 'Calls per day, by who calls',
              f"<code>sign</code> calls ran at {val(R, 'by_month/M3/2026-10/raw/per_day', 'int')} a day in October 2026; the largest "
              f"single caller made {val(R, oct4 + '/concentration/top3_callers/0/share', 'pct1')} of them, and apps beyond NEAR's own "
              f"infrastructure, leaving Sweat out, made {val(R, oct4 + '/main_without_sweat/point', 'pct1')} {iv(R, oct4 + '/main_without_sweat')}.",
              f"GET {nb}/accounts/v1.signer/receipts?method=sign&limit={L}\n    in windows drawn by seed before collection began (frozen/instants.json)\n"
              f"GET https://mainnet.neardata.xyz/v0/block/<height>\n    sampled blocks, for the signer behind each FastAuth call",
              'Each caller is classed by <code>registry/callers.json</code>, which gives a source for every account. '
              'Computed by <code>m3</code>, <code>m4_m5</code> and <code>chart2_bands</code> in <code>analysis/measures.py</code>.',
              notes_for(N, '2a')),
        panel('2b', 'What NEAR pays per request',
              f"NEAR paid {val(R, sep8 + '/point', 'f4')} NEAR per <code>sign</code> request in September "
              f"{iv(R, sep8, 'f4')}, from emissions; from July to September the points rose but the intervals overlap, "
              f"so the rise is not established.",
              "inputs/hsp007-ledger.json\n    the rows of the HSP-007 execution thread, each with its link, saved before collection began\n"
              "÷ the month's sign calls, from the receipts query of panel 2a",
              'Computed by <code>m8</code> in <code>analysis/measures.py</code> with <code>analysis/hsp007.py</code>.',
              m8_table + notes_for(N, '2b')),
    ]
    return ''.join(one), ''.join(two)


CSS = """
:root{--bg:#02070c;--surf:#06131c;--ink:#dff6ff;--ink2:#8db4c4;--line:#0f2c3d;--edge:#1e5a75;--omni:#6ee7ff;--poa:#ff8a1f;--unk:#4b6676;--glow:rgba(110,231,255,.45);--disp:"Eurostile","Microgramma D Extended","Bank Gothic","Avenir Next","Futura","Segoe UI",system-ui,sans-serif;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1040px;margin:0 auto;padding:40px 20px 72px}
h1{font-size:clamp(34px,6vw,54px);line-height:1.05;margin:0 0 10px;letter-spacing:-.02em}
h2{font-size:24px;line-height:1.2;margin:56px 0 6px;letter-spacing:-.01em}
h3{font-size:17px;margin:0 0 6px}
h4{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink2);margin:16px 0 6px;font-weight:600}
p{margin:0 0 12px}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.86em}
code{background:var(--surf);padding:1px 5px;border-radius:4px}
.sub{color:var(--ink2);font-size:18px;max-width:46em;margin:0 0 28px}
.lede{color:var(--ink2);max-width:46em}
.answer{font-size:21px;line-height:1.4;max-width:40em;margin:0 0 14px}
.claim{border-left:3px solid var(--omni);padding:2px 0 2px 14px;max-width:44em}
.small{font-size:14px;color:var(--ink2);max-width:52em}
.tests{width:100%;border-collapse:collapse;margin:18px 0 10px}
.tests th{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink2);text-align:left;font-weight:600;padding:8px 12px 8px 0;border-bottom:1px solid var(--edge)}
.tests td{vertical-align:top;padding:12px 12px 12px 0;border-bottom:1px solid var(--line)}
.tests td:first-child{font-weight:600;width:19%}
.tests tr.grp td{font-weight:600;width:auto;padding-top:20px;color:var(--ink)}
.when,.points{max-width:52em;padding-left:1.2em;margin:10px 0 14px}
.points li{margin:0 0 8px}
.when li{margin:0 0 8px}
.tests td:nth-child(2){width:34%;color:var(--ink2)}
.chip{display:inline-block;border:1px solid var(--edge);border-radius:999px;padding:1px 10px;font-size:13px;white-space:nowrap}
.grp{margin:22px 0 0}
.grp h3{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.ct{color:var(--ink2);font-weight:400;font-size:14px}
.what{color:var(--ink2);font-size:14px;margin:0 0 10px;max-width:56em}
.cells{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(212px,1fr));gap:10px}
.cell{border:1px solid var(--line);border-radius:8px;padding:10px 12px;background:var(--bg)}
.g-dom{border-color:var(--omni)}
.cn{font-weight:600;display:flex;align-items:center;gap:8px;margin-bottom:6px}
.cv{font-size:13px;margin:4px 0 0;font-variant-numeric:tabular-nums}
.cd{font-size:13px;color:var(--ink2);margin-top:4px}
.sw{display:inline-block;width:12px;height:12px;border-radius:3px;flex:none}
.sw-dom{background:var(--omni)}
.sw-use{border:2px solid var(--omni)}
.sw-poa{background:var(--poa)}
.sw-unk{background:var(--unk)}
.track{position:relative;height:12px;margin:8px 0 2px}
.track::before{content:"";position:absolute;left:0;right:0;top:5px;height:2px;border-radius:1px;background:var(--line)}
.rng{position:absolute;top:4px;height:4px;min-width:4px;border-radius:2px;background:var(--ink2)}
.pt{position:absolute;top:0;width:12px;height:12px;border-radius:50%;background:var(--omni);border:2px solid var(--bg)}
.key{font-size:13px;color:var(--ink2);margin:14px 0 0}
figure{margin:18px 0 8px}
figure img{display:block;width:100%;height:auto;border:1px solid var(--line);border-radius:8px}
figcaption{font-size:13px;color:var(--ink2);margin-top:6px}
.panels{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin:14px 0 0}
.panel{border:1px solid var(--line);border-radius:8px;padding:16px 16px 12px;min-width:0}
.pl{display:inline-block;font-variant-numeric:tabular-nums;color:var(--ink2);margin-right:8px}
.shows{font-size:16px}
.how{font-size:14px;color:var(--ink2)}
pre.q{margin:0 0 10px;padding:10px 12px;background:var(--surf);border-radius:6px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.45}
.notes{border-top:1px solid var(--line);margin-top:12px}
.notes ul{margin:0;padding:0;list-style:none}
.notes li{font-size:14px;color:var(--ink2);margin:0 0 8px}
.nn{color:var(--ink);font-weight:600}
table.t{border-collapse:collapse;width:100%;margin:12px 0 4px;font-size:14px;font-variant-numeric:tabular-nums}
table.t caption{text-align:left;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink2);font-weight:600;padding-bottom:6px}
table.t th{text-align:left;font-weight:600;color:var(--ink2);padding:5px 10px 5px 0;border-bottom:1px solid var(--edge);vertical-align:bottom}
table.t td{padding:5px 10px 5px 0;border-bottom:1px solid var(--line)}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.box{border:1px solid var(--line);border-radius:8px;padding:16px;min-width:0}
.sha{word-break:break-all}
footer{margin-top:56px;padding-top:16px;border-top:1px solid var(--line);font-size:13px;color:var(--ink2)}
@media (max-width:640px){.tests thead{display:none}.tests td{display:block;width:auto!important;padding:4px 0;border:0}.tests tr{display:block;padding:12px 0;border-bottom:1px solid var(--line)}}
/* the grid theme: one dark look, luminous cyan for NEAR's own route and orange for the custodial one */
body{background:linear-gradient(rgba(110,231,255,.045) 1px,transparent 1px) 0 0/100% 56px,linear-gradient(90deg,rgba(110,231,255,.045) 1px,transparent 1px) 0 0/56px 100%,radial-gradient(1200px 520px at 50% -140px,rgba(110,231,255,.16),transparent 70%),var(--bg);background-attachment:fixed;font-family:"Avenir Next","Segoe UI",system-ui,-apple-system,sans-serif}
h1,h2,h3,h4,.tests th,table.t caption,table.t th{font-family:var(--disp);text-transform:uppercase}
h1{font-weight:300;letter-spacing:.2em;color:#f4fdff;text-shadow:0 0 22px var(--glow),0 0 2px #fff}
h2{font-size:19px;font-weight:500;letter-spacing:.16em;color:var(--omni);text-shadow:0 0 14px var(--glow);border-bottom:1px solid var(--edge);padding-bottom:9px;position:relative}
h2::after{content:"";position:absolute;left:0;bottom:-1px;width:132px;height:1px;background:var(--omni);box-shadow:0 0 10px var(--omni),0 0 2px #fff}
h3{font-size:14px;font-weight:500;letter-spacing:.12em;color:#f4fdff}
h4{letter-spacing:.16em;color:var(--omni)}
header{border-bottom:1px solid var(--omni);box-shadow:0 14px 26px -24px var(--omni);padding-bottom:20px}
.sub{letter-spacing:.02em}
.answer strong{color:var(--omni);text-shadow:0 0 12px var(--glow)}
.claim{border-left:2px solid var(--omni);box-shadow:-10px 0 18px -14px var(--omni)}
code{background:#07202d;color:#aef1ff;border:1px solid var(--line);border-radius:2px}
pre.q{background:#041019;border:1px solid var(--line);border-left:2px solid var(--omni);border-radius:0;color:#bfeeff}
pre.q code{background:none;border:0}
.cell,.panel,.box{background:rgba(6,19,28,.74);border:1px solid var(--edge);border-radius:2px;box-shadow:inset 0 0 24px rgba(110,231,255,.05)}
.g-dom{border-color:var(--omni);box-shadow:0 0 16px rgba(110,231,255,.3),inset 0 0 24px rgba(110,231,255,.09)}
.chip{border-radius:2px;border-color:var(--omni);color:var(--omni);font-family:var(--disp);font-size:11px;letter-spacing:.12em;text-transform:uppercase;box-shadow:0 0 8px rgba(110,231,255,.25)}
.sw{border-radius:0}.sw-dom{box-shadow:0 0 8px var(--omni)}.sw-poa{box-shadow:0 0 8px var(--poa)}
.pt{box-shadow:0 0 10px var(--omni)}.rng{background:var(--edge)}
figure img{border:1px solid var(--edge);border-radius:2px;box-shadow:0 0 28px rgba(110,231,255,.14)}
.tests td:first-child{color:#f4fdff}
.tests tr.grp td{color:var(--poa);font-family:var(--disp);letter-spacing:.12em;text-transform:uppercase;font-size:12px;text-shadow:0 0 10px rgba(255,138,31,.45)}
.tests th,table.t th,table.t caption{letter-spacing:.14em;color:var(--omni)}
a{color:var(--omni)}
footer{border-top:1px solid var(--edge)}
::selection{background:var(--omni);color:#02070c}
nav.top{display:flex;gap:22px;align-items:center;flex-wrap:wrap;font-family:var(--disp);text-transform:uppercase;letter-spacing:.16em;font-size:12px;margin:0 0 34px;padding-bottom:12px;border-bottom:1px solid var(--line)}
nav.top a{color:var(--ink2);text-decoration:none}
nav.top a[aria-current]{color:var(--omni);text-shadow:0 0 10px var(--glow)}
nav.top .mark{color:#f4fdff;margin-right:auto}
article h3{margin:32px 0 8px}
article p,article li{max-width:47em}
article ul{padding-left:1.2em;margin:8px 0 14px}
article li{margin:0 0 8px}
article li p{margin:8px 0 0}
article strong{color:#f4fdff}
article em{color:var(--ink2)}
article .wrap{overflow-x:auto;margin:14px 0 18px}
article table.t td,article table.t th{vertical-align:top;padding-right:14px}
article a{overflow-wrap:anywhere}
"""


def page(R, thesis, D, notes_text, chart_sha):
    title, sub, answer, points, claim, when, pilot, groups, count, (watch_lede, watch, watch_after) = lifted(thesis)
    N = notes(notes_text)
    grid_html, by, n_chains = grid(R, D)
    one, two = panels(R, D, N)
    status = D['status']
    rows = ''.join(f'<tr class="grp"><td colspan="4">{md(head)}</td></tr>'
                   + ''.join(f'<tr><td>{html.escape(name)}</td><td>{md(needed)}</td><td>{md(found)}</td>'
                             f'<td><span class="chip">{status[key]}</span></td></tr>' for key, name, needed, found in tests)
                   for head, tests in groups)
    when_html = ''.join(f'<li>{md(l)}</li>' for l in when)
    points_html = ''.join(f'<li>{md(l)}</li>' for l in points)
    watch_html = ''.join(f'<li>{md(l)}</li>' for l in watch)
    comp = R['completeness']
    fam = ''.join(f"<tr><td>{html.escape(k)}</td><td>{v['completed']}</td><td>{v.get('pending', 0)}</td></tr>"
                  for k, v in sorted(comp.items()))
    assert sum(v['completed'] for v in comp.values()) == D['windows_read']
    assert sum(v['completed'] + v.get('pending', 0) for v in comp.values()) == D['windows_total']
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} Dashboard</title>
<style>{CSS}</style>
</head>
<body>
<main>
{NAV.format(a=CUR, b="")}
<header>
<h1>{html.escape(title)}</h1>
<p class="sub">{md(sub)}</p>
<p class="answer">{md(answer)}</p>
<ul class="points">{points_html}</ul>
<p class="claim">{md(claim)}</p>
</header>

<section aria-labelledby="h-when">
<h2 id="h-when">What was fixed, and when</h2>
<p class="lede">All dates are 2026, UTC. The Bitcoin block times can be checked by anyone; the other times are this entry's own record.</p>
<ul class="when">{when_html}</ul>
<p class="small">{md(pilot)}</p>
</section>

<section aria-labelledby="h-tests">
<h2 id="h-tests">The five tests</h2>
<p class="lede">Each row is what a test needed against what was found. {md(count)}</p>
<table class="tests"><thead><tr><th>Test</th><th>Needed</th><th>Found</th><th>Result</th></tr></thead><tbody>{rows}</tbody></table>
</section>

<section aria-labelledby="h-watch">
<h2 id="h-watch">What to watch, and when</h2>
<p class="lede">{md(watch_lede)}</p>
<ul class="when">{watch_html}</ul>
<p class="small">{md(watch_after)}</p>
</section>

<section aria-labelledby="h-grid">
<h2 id="h-grid">The 28 chains, one by one</h2>
<p class="lede">The partner's report names a "28-chain moat". This is where each of the 28 stands in this sample: Omni is the dominant route on {by['dom']}, seen in use on {by['dom'] + by['use']}, and {by['unk']} cannot be read at all.</p>
{grid_html}
<p class="key">Each line runs from 0% at the left to 100% at the right. The bright dot is Omni's share of the chain's measured flow by amount; the bar behind it is its interval, which is wide where few windows were read. Drawn here after the counted read, from the rows of <code>M1</code> in <code>out/combined.json</code>; <code>THESIS.md</code> section 2 has the same readings in words.</p>
</section>

<section aria-labelledby="h-c1">
<h2 id="h-c1">Chart 1. Where Intents' measured cross-chain flow runs</h2>
<figure><img src="{grid_name(CHARTS[0])}" alt="Chart 1, three panels: measured value by chain and route; Omni's share early and late for four series; Omni's share of bridged BTC on NEAR by month. Each panel is described below.">
<figcaption>The timestamped code's chart, shown in this page's colours: only its style block differs. The chart as written is beside this page, unchanged: <a href="{CHARTS[0]}"><code>{CHARTS[0]}</code></a> (sha256 <span class="sha">{chart_sha[CHARTS[0]]}</span>).</figcaption></figure>
<div class="panels">{one}</div>
</section>

<section aria-labelledby="h-c2">
<h2 id="h-c2">Chart 2. Who calls the signer, and what the program costs</h2>
<figure><img src="{grid_name(CHARTS[1])}" alt="Chart 2, two panels: sign calls per day by caller class, by month; NEAR paid per sign request, by month. Each panel is described below.">
<figcaption>The timestamped code's chart, shown in this page's colours: only its style block differs. The chart as written is beside this page, unchanged: <a href="{CHARTS[1]}"><code>{CHARTS[1]}</code></a> (sha256 <span class="sha">{chart_sha[CHARTS[1]]}</span>).</figcaption></figure>
<div class="panels">{two}</div>
</section>

<section aria-labelledby="h-sample">
<h2 id="h-sample">The sample, and how to rebuild all of this</h2>
<div class="two">
<div class="box">
<h3>{D['windows_read']} of {D['windows_total']} windows read in full</h3>
<p class="small">The windows were drawn by seed, and their list was hashed before collection began. A reading that rests on a window that did not finish is marked "not completed" and is never drawn as if it were known. Data cutoff (T0): {html.escape(val(R, 'T0_utc', 'str'))}.</p>
<table class="t"><thead><tr><th>Family of windows</th><th>Read in full</th><th>Not finished</th></tr></thead><tbody>{fam}</tbody></table>
{notes_for(N, 'sample')}
</div>
<div class="box">
<h3>Two commands, offline</h3>
<pre class="q">python3 -I rebuild.py data --draft
python3 -I publish/written.py data</pre>
<p class="small"><code>sh check.sh</code> runs both, then the comparisons, the tests and the manifests, and ends <code>ALL OK</code>. The first recomputes every number, table and chart from the saved rows. The second fills <code>THESIS.md</code>, checks it against the results, and writes this page. Neither makes a network call. When they worked:</p>
<p class="small"><code>out/published/tables.md</code> sha256 <span class="sha">{D['tables_sha']}</span><br>
<code>THESIS.md</code> sha256 <span class="sha">{_sha(thesis.encode())}</span></p>
<p class="small">The full write-up is <code>THESIS.md</code>, set as a page <a href="thesis.html">here</a>; the method, hashed before collection began, is <code>METHOD.md</code>; what changed after the counted read is in <code>AFTER-READ.md</code>.</p>
</div>
</div>
</section>

<footer>
<p>This page is written by <code>publish/dashboard.py</code> from <code>out/combined.json</code>, <code>THESIS.md</code> and <code>TABLE-NOTES.md</code>. It was made after the counted read and is not one of the timestamped files; the two charts and every reading on it are. The charts are shown recoloured; the files as the timestamped code wrote them are beside this page. No colour or typeface is loaded from elsewhere.</p>
</footer>
</main>
</body>
</html>
"""


GRID_STYLE = """
text{font-family:"Avenir Next","Segoe UI",system-ui,-apple-system,sans-serif}
.bg{fill:#02070c}
.ink{fill:#eafaff}
.ink2{fill:#9cc7d6}
.mut{fill:#7397a6}
.grid{stroke:#0f2c3d;stroke-width:1}
.axis{stroke:#1e5a75;stroke-width:1}
.surf{fill:#02070c}
.ring{stroke:#02070c;stroke-width:2}
.con{stroke:#1e5a75;stroke-width:1.5}
.s1{fill:#6ee7ff}.s2{fill:#ff8a1f}.s3{fill:#2f6bff}.s4{fill:#ffd23f}
.s5{fill:#ff4d4d}.s6{fill:#e9fbff}.s7{fill:#7f9aa8}.sU{fill:#4b6676}
.k1{stroke:#6ee7ff}.k2{stroke:#ff8a1f}.k3{stroke:#2f6bff}.k4{stroke:#ffd23f}
.k5{stroke:#ff4d4d}.k6{stroke:#e9fbff}.k7{stroke:#7f9aa8}.kU{stroke:#4b6676}
.s1{filter:drop-shadow(0 0 3px rgba(110,231,255,.7))}.s2{filter:drop-shadow(0 0 3px rgba(255,138,31,.7))}
.ln{fill:none;stroke:#6ee7ff;stroke-width:2;stroke-linejoin:round;stroke-linecap:round;filter:drop-shadow(0 0 4px rgba(110,231,255,.85))}
"""
_STYLE = re.compile(r'<style>.*?</style>', re.S)


def grid_name(name):
    return name[:-len('.svg')] + '-grid.svg'


def recolour(svg):
    """The timestamped chart in the page's colours: its one style block is replaced and nothing else."""
    s = svg.decode()
    if len(_STYLE.findall(s)) != 1:
        raise SystemExit('a chart must have exactly one style block')
    out = _STYLE.sub(lambda m: '<style>' + GRID_STYLE + '</style>', s)
    if _STYLE.sub('', out) != _STYLE.sub('', s):
        raise SystemExit('recolouring changed more than the style block')
    return out.encode()


NAV = ('<nav class="top" aria-label="Pages"><span class="mark">Signed by NEAR?</span>'
       '<a href="index.html"{a}>Dashboard</a><a href="thesis.html"{b}>Write-up</a></nav>')
CUR = ' aria-current="page"'
BANNER = 'banner-grid.svg'
DISP = 'Eurostile,Microgramma D Extended,Bank Gothic,Avenir Next,Futura,Segoe UI,system-ui,sans-serif'


def banner(title, sub):
    """The title as an image for the repository's front page, in the page's colours. It carries no figure."""
    W, H, Y0 = 1280, 300, 196
    cx = W / 2
    fan = ''.join(f'<line x1="{cx + k * 20:.1f}" y1="{Y0}" x2="{cx + k * 168:.1f}" y2="{H}"/>' for k in range(-16, 17))
    rows = ''.join(f'<line x1="0" y1="{Y0 + (H - Y0) * (t / 6) ** 2:.1f}" x2="{W}" y2="{Y0 + (H - Y0) * (t / 6) ** 2:.1f}"/>'
                   for t in range(1, 6))
    words = sub.rstrip('.').split(': ')
    words = [w + ':' for w in words[:-1]] + words[-1:]
    lines = ''.join(f'<text x="64" y="{150 + 26 * i}" font-size="19" fill="#8db4c4" letter-spacing=".4">{html.escape(w, quote=False)}</text>'
                    for i, w in enumerate(words))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(title)}">
<defs>
<radialGradient id="sky" cx="50%" cy="0%" r="80%"><stop offset="0" stop-color="#6ee7ff" stop-opacity=".2"/><stop offset="1" stop-color="#6ee7ff" stop-opacity="0"/></radialGradient>
<linearGradient id="floor" gradientUnits="userSpaceOnUse" x1="0" y1="{Y0}" x2="0" y2="{H}"><stop offset="0" stop-color="#6ee7ff" stop-opacity=".5"/><stop offset="1" stop-color="#6ee7ff" stop-opacity=".12"/></linearGradient>
<filter id="glow" filterUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}"><feGaussianBlur stdDeviation="7" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<rect width="{W}" height="{H}" fill="#02070c"/>
<rect width="{W}" height="{H}" fill="url(#sky)"/>
<g stroke="url(#floor)" stroke-width="1" fill="none">{fan}{rows}</g>
<line x1="0" y1="{Y0}" x2="{W}" y2="{Y0}" stroke="#6ee7ff" stroke-width="1.5" filter="url(#glow)"/>
<line x1="64" y1="{Y0}" x2="244" y2="{Y0}" stroke="#ff8a1f" stroke-width="3" filter="url(#glow)"/>
<text x="64" y="104" font-family="{DISP}" font-size="62" font-weight="300" letter-spacing="13" fill="#f4fdff" filter="url(#glow)">{html.escape(title.upper(), quote=False)}</text>
<g font-family="Avenir Next,Segoe UI,system-ui,sans-serif">{lines}</g>
</svg>
"""


def inline(s):
    """The inline Markdown THESIS.md uses: `code`, **bold**, *emphasis* and bare links. Anything else stops the build."""
    out = []
    for part in re.split(r'(`[^`]+`)', s):
        if len(part) > 2 and part[0] == '`' == part[-1]:
            out.append('<code>' + html.escape(part[1:-1], quote=False) + '</code>')
            continue
        part = html.escape(part, quote=False)
        part = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', part)
        part = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', part)
        if '*' in part or '`' in part:
            raise SystemExit(f'thesis page: markup not understood in: {s[:80]}')
        out.append(re.sub(r'(https?://[^\s<>()]*[^\s<>().,;:])', r'<a href="\1">\1</a>', part))
    return ''.join(out)


def _cells(line):
    """A table row's cells; a bar inside `code` does not split."""
    cells, cur, code = [], '', False
    for ch in line.strip()[1:-1]:
        if ch == '`':
            code = not code
        if ch == '|' and not code:
            cells.append(cur.strip())
            cur = ''
        else:
            cur += ch
    return cells + [cur.strip()]


_BLOCK = re.compile(r'#{1,3} |\||- |```|!\[|<!--')
_IMG = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)$')


def thesis_body(text, files):
    """THESIS.md's blocks as HTML: headings, paragraphs, lists, tables, command blocks and the two charts."""
    L = text.split('\n')
    out, i, n = [], 0, len(L)
    while i < n:
        l = L[i]
        if not l.strip() or l.startswith('<!--'):
            i += 1
        elif re.match(r'#{1,3} ', l):
            k, head = l.index(' '), l[l.index(' ') + 1:]
            out.append(f'<h{k} id="{re.sub("[^a-z0-9]+", "-", head.lower()).strip("-")}">{inline(head)}</h{k}>')
            i += 1
        elif l.startswith('```'):
            j = L.index('```', i + 1)
            out.append('<pre class="q">' + html.escape('\n'.join(L[i + 1:j]), quote=False) + '</pre>')
            i = j + 1
        elif l.startswith('|'):
            j = i
            while j < n and L[j].startswith('|'):
                j += 1
            rows = [_cells(x) for x in L[i:j]]
            if len({len(r) for r in rows}) != 1 or set(''.join(rows[1])) - set('-: '):
                raise SystemExit(f'thesis page: a table is not regular near: {l[:60]}')
            out.append('<div class="wrap"><table class="t"><thead><tr>' + ''.join(f'<th>{inline(c)}</th>' for c in rows[0])
                       + '</tr></thead><tbody>'
                       + ''.join('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>' for r in rows[2:])
                       + '</tbody></table></div>')
            i = j
        elif l.startswith('- '):
            items = []
            while i < n and (L[i].startswith('- ') or L[i].startswith('  ')
                             or (not L[i].strip() and i + 1 < n and L[i + 1].startswith('  '))):
                if L[i].startswith('- '):
                    items.append([L[i][2:]])
                elif L[i].strip():
                    items[-1].append(L[i].strip())
                i += 1
            out.append('<ul>' + ''.join('<li>' + inline(it[0]) + ''.join(f'<p>{inline(x)}</p>' for x in it[1:]) + '</li>'
                                        for it in items) + '</ul>')
        elif _IMG.match(l):
            alt, src = _IMG.match(l).groups()
            base = os.path.basename(src)
            plain = base.replace('-grid.svg', '.svg')
            if plain not in CHARTS or grid_name(plain) not in files:
                raise SystemExit(f'thesis page: an image that is not one of the two charts: {src}')
            out.append(f'<figure><img src="{grid_name(plain)}" alt="{html.escape(alt)}"><figcaption>{html.escape(alt, quote=False)}. '
                       f'Shown in this page\'s colours; the chart as the timestamped code wrote it: '
                       f'<a href="{plain}"><code>{plain}</code></a>.</figcaption></figure>')
            i += 1
        else:
            j = i
            while j < n and L[j].strip() and not _BLOCK.match(L[j]):
                j += 1
            out.append('<p>' + inline(' '.join(L[i:j])) + '</p>')
            i = j
    return '\n'.join(out)


def _words(s):
    return re.findall(r'\w+', s)


def thesis_page(thesis, files):
    """docs/thesis.html: THESIS.md set as a page. Its words must be THESIS.md's words, in order."""
    body = thesis_body(thesis, files)
    shown = html.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'<figure>.*?</figure>', ' ', body)))
    source = '\n'.join(l for l in thesis.split('\n')
                       if not (l.startswith('<!--') or l.startswith('```') or _IMG.match(l)
                               or (l.startswith('|') and not set(l) - set('|-: '))))
    if _words(shown) != _words(source):
        raise SystemExit('thesis page: the page does not carry the words of THESIS.md in order')
    title = thesis.split('\n', 1)[0].lstrip('# ').strip()
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} The write-up</title>
<style>{CSS}</style>
</head>
<body>
<main>
{NAV.format(a="", b=CUR)}
<article>
{body}
</article>
<footer>
<p>This page is <code>THESIS.md</code> (sha256 <span class="sha">{_sha(thesis.encode())}</span>) set in this entry's colours by <code>publish/dashboard.py</code>, which checks that it carries the same words in the same order. The two charts are shown recoloured; the files as the timestamped code wrote them are beside this page. It was made after the counted read and is not one of the timestamped files.</p>
</footer>
</main>
</body>
</html>
"""


def render(R, thesis, D):
    """The files of docs/, as bytes by name. Every check runs here; nothing is written."""
    with open(os.path.join(ROOT, 'TABLE-NOTES.md')) as f:
        notes_text = f.read()
    files = {}
    for name in CHARTS:
        with open(os.path.join(ROOT, 'out', 'published', name), 'rb') as f:
            files[name] = f.read()
        files[grid_name(name)] = recolour(files[name])
    files['index.html'] = page(R, thesis, D, notes_text, {n: _sha(b) for n, b in files.items()}).encode()
    files['thesis.html'] = thesis_page(thesis, files).encode()
    title, sub = lifted(thesis)[:2]
    files[BANNER] = banner(title, sub).encode()
    return files


def write(files):
    os.makedirs(DOCS, exist_ok=True)
    for name, b in files.items():
        with open(os.path.join(DOCS, name), 'wb') as f:
            f.write(b)
    return _sha(files['index.html'])


def main(R, thesis, D):
    return write(render(R, thesis, D))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    with open(os.path.join(ROOT, 'out', 'combined.json')) as f:
        R = json.load(f)
    with open(os.path.join(ROOT, 'THESIS.md')) as f:
        thesis = f.read()
    D, bad = C.check(R, thesis, sys.argv[1])
    if bad:
        for b in bad:
            print('MISMATCH', b)
        raise SystemExit('docs/ is left as it was')
    print(f'ok: docs/index.html sha256 {main(R, thesis, D)}')
