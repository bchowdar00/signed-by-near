"""Hand-written SVG charts for the write-up (METHOD §10). Python 3 standard library only.

  render(results, out_dir) -> [chart1_path, chart2_path]

`results` is the parsed results.json that analysis/recompute.py writes. Output is
deterministic (same input -> same bytes). A missing value (None) is drawn as absent,
never as zero, and noted. Every data mark carries a <title> so a browser shows its
exact label and value on hover. Colours are CSS classes with a dark-mode block, so the
charts read in a GitHub README in either theme. No scripts, no external fonts or files.

Design follows the project's data-viz standard: thin marks, 2px surface gaps, hairline
recessive gridlines, text always in ink tokens, a legend for two or more series, never a
dual axis (two scales share an x axis across two panels instead).
"""
import math
import os

# ---------------------------------------------------------------------------
# palette (light / dark). Categorical slots 1..7 are the standard's fixed order;
# "unknown route" is neutral grey, never a categorical slot.
STYLE = """
text{font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
.bg{fill:#fcfcfb}
.ink{fill:#0b0b0b}
.ink2{fill:#52514e}
.mut{fill:#898781}
.grid{stroke:#e1e0d9;stroke-width:1}
.axis{stroke:#c3c2b7;stroke-width:1}
.surf{fill:#fcfcfb}
.ring{stroke:#fcfcfb;stroke-width:2}
.con{stroke:#c3c2b7;stroke-width:1.5}
.s1{fill:#2a78d6}.s2{fill:#eb6834}.s3{fill:#1baf7a}.s4{fill:#eda100}
.s5{fill:#e87ba4}.s6{fill:#008300}.s7{fill:#6250d6}.sU{fill:#b5b3ab}
.k1{stroke:#2a78d6}.k2{stroke:#eb6834}.k3{stroke:#1baf7a}.k4{stroke:#eda100}
.k5{stroke:#e87ba4}.k6{stroke:#008300}.k7{stroke:#6250d6}.kU{stroke:#b5b3ab}
.ln{fill:none;stroke:#2a78d6;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
@media (prefers-color-scheme: dark){
.bg{fill:#1a1a19}.surf{fill:#1a1a19}.ring{stroke:#1a1a19}
.ink{fill:#f0efec}.ink2{fill:#c3c2b7}.mut{fill:#898781}
.grid{stroke:#2c2c2a}.axis{stroke:#383835}.con{stroke:#383835}
.s1{fill:#3987e5}.s2{fill:#d95926}.s3{fill:#199e70}.s4{fill:#c98500}
.s5{fill:#d55181}.s6{fill:#008300}.s7{fill:#9085e9}.sU{fill:#5a5955}
.k1{stroke:#3987e5}.k2{stroke:#d95926}.k3{stroke:#199e70}.k4{stroke:#c98500}
.k5{stroke:#d55181}.k6{stroke:#008300}.k7{stroke:#9085e9}.kU{stroke:#5a5955}
.ln{stroke:#3987e5}
}
"""

W = 960
PAD = 24

# ---------------------------------------------------------------------------
# formatting / safety helpers


def _num(x):
    """float(x) for a real finite number, else None. Guards against NaN/inf and None."""
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        v = float(x)
        if v != v or v in (float("inf"), float("-inf")):
            return None
        return v
    return None


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _nf(x):
    """Coordinate number -> compact deterministic string (2dp, no trailing zeros)."""
    v = _num(x)
    if v is None:
        v = 0.0
    v = round(v, 2)
    if abs(v) < 0.005:
        v = 0.0
    if v == int(v):
        return str(int(v))
    return (f"{v:.2f}").rstrip("0").rstrip(".")


def _usd_compact(v):
    v = _num(v)
    if v is None:
        return ""
    if v == 0:
        return "$0"
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= div:
            q = (f"{v / div:.1f}").rstrip("0").rstrip(".")
            return f"${q}{suf}"
    return f"${v:.0f}"


def _usd_full(v):
    v = _num(v)
    if v is None:
        return "not measured"
    return "$" + format(int(round(v)), ",d")


def _pct(x):
    v = _num(x)
    if v is None:
        return "not measured"
    return _nf(round(v * 100.0, 1)) + "%"


def _near(v):
    v = _num(v)
    if v is None:
        return "not measured"
    return (f"{v:.4f}").rstrip("0").rstrip(".") + " NEAR"


def _nice(vmax, n=6):
    """Nice tick values 0..top covering vmax; returns (ticks, top)."""
    vmax = _num(vmax) or 0.0
    if vmax <= 0:
        return [0.0, 1.0], 1.0
    raw = vmax / n
    mag = 10 ** math.floor(math.log10(raw))
    step = 10 * mag
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            step = m * mag
            break
    top = math.ceil(vmax / step) * step
    ticks = []
    v = 0.0
    while v <= top + step * 1e-9:
        ticks.append(round(v, 6))
        v += step
    return ticks, top


def _rot_bottom(labels, size):
    """Pixels a set of -45deg (anchor-end) labels reach below their baseline.

    Mirrors the layout test's model: a rotated label's lowest corner is 0.7071 * width
    below the baseline, with width = 0.58 * size * len. Used to drop following text clear
    of the rotated tick labels."""
    widths = [0.58 * size * len(str(lbl)) for lbl in labels if str(lbl)]
    return 0.7071 * max(widths, default=0.0)


# ---------------------------------------------------------------------------
# svg primitives (each returns a well-formed XML string)


def _text(x, y, s, cls="ink", anchor="start", size=11, rot=None, weight=None):
    t = f' transform="rotate({_nf(rot)} {_nf(x)} {_nf(y)})"' if rot is not None else ""
    w = f' font-weight="{weight}"' if weight else ""
    return (f'<text x="{_nf(x)}" y="{_nf(y)}" class="{cls}" font-size="{_nf(size)}"'
            f' text-anchor="{anchor}"{w}{t}>{_esc(s)}</text>')


def _line(x1, y1, x2, y2, cls="grid", w=None):
    sw = f' stroke-width="{_nf(w)}"' if w is not None else ""
    return (f'<line x1="{_nf(x1)}" y1="{_nf(y1)}" x2="{_nf(x2)}" y2="{_nf(y2)}"'
            f' class="{cls}"{sw}/>')


def _rect(x, y, w, h, cls, title=None, opacity=None):
    op = f' opacity="{_nf(opacity)}"' if opacity is not None else ""
    body = (f'<rect x="{_nf(x)}" y="{_nf(y)}" width="{_nf(max(0, w))}"'
            f' height="{_nf(max(0, h))}" class="{cls}"{op}')
    if title:
        return body + f'><title>{_esc(title)}</title></rect>'
    return body + "/>"


def _rrect_right(x, y, w, h, r, cls, title=None):
    """Rect with only its right (data-end) corners rounded."""
    w = max(0, w)
    h = max(0, h)
    r = max(0, min(r, h / 2.0, w))
    if r <= 0:
        return _rect(x, y, w, h, cls, title)
    d = (f"M{_nf(x)},{_nf(y)} H{_nf(x + w - r)} A{_nf(r)},{_nf(r)} 0 0 1 {_nf(x + w)},{_nf(y + r)}"
         f" V{_nf(y + h - r)} A{_nf(r)},{_nf(r)} 0 0 1 {_nf(x + w - r)},{_nf(y + h)}"
         f" H{_nf(x)} Z")
    body = f'<path d="{d}" class="{cls}"'
    if title:
        return body + f'><title>{_esc(title)}</title></path>'
    return body + "/>"


def _circle(cx, cy, r, cls, ring=False, title=None):
    # ring=True adds the .ring class: a 2px surface-coloured stroke, so the filled
    # marker stays legible where it crosses a line or another marker.
    klass = f"{cls} ring" if ring else cls
    body = f'<circle cx="{_nf(cx)}" cy="{_nf(cy)}" r="{_nf(r)}" class="{klass}"'
    if title:
        return body + f'><title>{_esc(title)}</title></circle>'
    return body + "/>"


def _hollow(cx, cy, r, kcls, title=None):
    """Hollow marker: surface fill + coloured stroke."""
    body = (f'<circle cx="{_nf(cx)}" cy="{_nf(cy)}" r="{_nf(r)}" class="surf {kcls}"'
            f' stroke-width="1.5"')
    if title:
        return body + f'><title>{_esc(title)}</title></circle>'
    return body + "/>"


def _swatch(x, y, cls, label, size=10, tsize=10):
    return (_rect(x, y - size, size, size, cls)
            + _text(x + size + 5, y - 1, label, "ink2", size=tsize))


def _wrap(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {_nf(h)}"'
            f' width="{w}" height="{_nf(h)}" font-size="11">'
            f"<style>{STYLE}</style>"
            f'<rect x="0" y="0" width="{w}" height="{_nf(h)}" class="bg"/>'
            + "".join(body) + "</svg>")


# ---------------------------------------------------------------------------
# chart 1

_ROUTES = [
    ("OMNI", "s1", "Omni (withdrawals signed by Chain Signatures)"),
    ("POA", "s2", "POA (custodial)"),
    ("UNKNOWN", "sU", "unknown route"),
]


def _chart1(res):
    E = []
    flows = res.get("chart1_flows") or []
    m1 = (res.get("M1") or {}).get("chains") or []
    m10 = res.get("M10") or {}
    m10b = res.get("M10b") or []

    E.append(_text(PAD, 26, "Where Intents' measured cross-chain flow runs", "ink",
                   size=17, weight="600"))
    y = 46

    # ---- panel a: routes by chain -----------------------------------------
    E.append(_text(PAD, y, "a · Routes by chain — USD per 30 days, measured tokens",
                   "ink", size=12, weight="600"))
    y += 14
    labelW = 86
    plotX0 = PAD + labelW
    plotX1 = W - PAD
    plotW = plotX1 - plotX0
    rows = []
    for r in flows:
        if not isinstance(r, dict):
            continue
        seg = {k: _num((r.get(k) or {}).get("point")) for k, _, _ in _ROUTES}
        total = sum(v for v in seg.values() if v is not None)
        rows.append((total, str(r.get("chain", "")), seg))
    rows.sort(key=lambda t: (-t[0], t[1]))
    vmax = max([t[0] for t in rows], default=0.0)
    ticks, top = _nice(vmax)
    barsTop = y + 6
    rowH = 26
    barH = 18
    barsBottom = barsTop + rowH * len(rows)
    # gridlines + axis labels
    for tv in ticks:
        gx = plotX0 + (tv / top * plotW if top else 0)
        E.append(_line(gx, barsTop, gx, barsBottom, "grid"))
        E.append(_text(gx, barsBottom + 14, _usd_compact(tv), "mut", anchor="middle", size=9))
    for i, (total, chain, seg) in enumerate(rows):
        ry = barsTop + i * rowH
        cy = ry + barH / 2.0
        E.append(_text(plotX0 - 6, cy + 3.5, chain, "ink2", anchor="end", size=10))
        x = plotX0
        present = [(k, cls, lbl) for k, cls, lbl in _ROUTES
                   if seg.get(k) is not None and seg.get(k) > 0]
        for j, (k, cls, lbl) in enumerate(present):
            v = seg[k]
            wseg = v / top * plotW if top else 0
            title = f"{chain} — {lbl}: {_usd_full(v)} / 30 days"
            last = j == len(present) - 1
            draww = wseg - 2 if not last else wseg  # 2px surface gap between segments
            if last:
                E.append(_rrect_right(x, ry, max(0, draww), barH, 4, cls, title))
            else:
                E.append(_rect(x, ry, max(0, draww), barH, cls, title))
            x += wseg
    E.append(_line(plotX0, barsBottom, plotX1, barsBottom, "axis"))
    # legend sits a clear step (>=8px) below the x tick labels (baseline barsBottom+14)
    y = barsBottom + 34
    # legend
    lx = plotX0
    for k, cls, lbl in _ROUTES:
        E.append(_swatch(lx, y, cls, lbl))
        lx += 20 + 7.2 * len(lbl)
    y += 18

    # not-measured chains (text, not bars)
    nm = []
    for c in m1:
        if not isinstance(c, dict):
            continue
        mt = c.get("measured_tokens")
        if isinstance(mt, list) and len(mt) == 0:
            docs = c.get("documented") or []
            docs = [str(d) for d in docs if d is not None]
            nm.append((str(c.get("chain", "")), ", ".join(docs) if docs else "—"))
    if nm:
        E.append(_text(PAD, y + 10,
                       "Not measured: no readable token in this sample; documented routes shown",
                       "ink2", size=10, weight="600"))
        y += 22
        ncol = 4
        colW = (W - 2 * PAD) / ncol
        nrow = (len(nm) + ncol - 1) // ncol
        for idx, (chain, docs) in enumerate(nm):
            col = idx // nrow
            rowi = idx % nrow
            tx = PAD + col * colW
            ty = y + rowi * 15 + 10
            E.append(_text(tx, ty, f"{chain}: {docs}", "mut", size=9.5))
        y += nrow * 15 + 8

    # ---- panel b: migration -----------------------------------------------
    y += 10
    E.append(_text(PAD, y, "b · Migration — early to late Omni share, by amount",
                   "ink", size=12, weight="600"))
    y += 8
    bLabelW = 112  # longest series label ("ETH (POA control)") ends >=10px before x(0%)
    verW = 150
    bX0 = PAD + bLabelW
    bX1 = W - PAD - verW
    bW = bX1 - bX0
    series = list(m10.keys())
    bTop = y + 10
    bRowH = 40
    bBottom = bTop + bRowH * len(series)
    for tv in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
        gx = bX0 + tv * bW
        E.append(_line(gx, bTop, gx, bBottom, "grid"))
        E.append(_text(gx, bBottom + 14, _pct(tv), "mut", anchor="middle", size=9))

    def _xp(p):
        return bX0 + max(0.0, min(1.0, p)) * bW

    for i, s in enumerate(series):
        node = m10.get(s) or {}
        rd = (node.get("readings") or {}).get("amount") or {}
        early = rd.get("early") or {}
        late = rd.get("late") or {}
        cyr = bTop + i * bRowH + bRowH / 2.0 - 6
        E.append(_text(PAD, cyr + 3.5, str(s), "ink2", anchor="start", size=10))
        ep = _num(early.get("point_unknown_not_omni"))
        lp = _num(late.get("point_unknown_not_omni"))
        # early rides a line 4px above the row centre, late 4px below, so their
        # interval bars (4px tall) never overlap and each dot sits on its own line.
        ey = cyr - 4
        ly = cyr + 4
        # connector early->late, between the two dots
        if ep is not None and lp is not None:
            E.append(_line(_xp(ep), ey, _xp(lp), ly, "con", w=2))
        # interval bars [L,U]
        for dd, cls, yy, nm_lbl in (
                (early, "s2", ey, "early"), (late, "s1", ly, "late")):
            L = _num(dd.get("L"))
            U = _num(dd.get("U"))
            if L is not None and U is not None:
                x0 = _xp(min(L, U))
                x1 = _xp(max(L, U))
                E.append(_rect(x0, yy - 2, x1 - x0, 4, cls,
                               title=f"{s} — {nm_lbl} interval: {_pct(L)} to {_pct(U)}",
                               opacity=0.3))
        # monthly hollow markers (descriptive, one window each), on the row centre
        for pt_ in (node.get("chart") or []):
            if not isinstance(pt_, dict):
                continue
            amt = pt_.get("amount") or {}
            mv = _num(amt.get("unknown_not_omni"))
            if mv is None:
                continue
            E.append(_hollow(_xp(mv), cyr, 3.5, "kU",
                             title=f"{s} — {pt_.get('month','')}: {_pct(mv)} (monthly, descriptive)"))
        # early / late point markers, each on its own interval's line
        if ep is not None:
            E.append(_circle(_xp(ep), ey, 5, "s2", ring=True,
                             title=f"{s} — early Omni share: {_pct(ep)}"))
        if lp is not None:
            E.append(_circle(_xp(lp), ly, 5, "s1", ring=True,
                             title=f"{s} — late Omni share: {_pct(lp)}"))
        verdict = node.get("verdict")
        if verdict:
            E.append(_text(bX1 + 10, cyr + 3.5, str(verdict), "ink2", size=10))
    y = bBottom + 24
    # legend + note for panel b
    E.append(_circle(bX0 + 4, y, 5, "s2", ring=True))
    E.append(_text(bX0 + 14, y + 3.5, "early", "ink2", size=10))
    E.append(_circle(bX0 + 74, y, 5, "s1", ring=True))
    E.append(_text(bX0 + 84, y + 3.5, "late", "ink2", size=10))
    E.append(_hollow(bX0 + 144, y, 3.5, "kU"))
    E.append(_text(bX0 + 154, y + 3.5, "monthly points: one window each, descriptive",
                   "ink2", size=10))
    y += 16

    # ---- panel c: BTC custody line ----------------------------------------
    y += 12
    E.append(_text(PAD, y,
                   "c · Omni's share of bridged BTC on NEAR (supply, all of NEAR)",
                   "ink", size=12, weight="600"))
    y += 8
    cX0 = PAD + 30
    cX1 = W - PAD
    cW = cX1 - cX0
    cTop = y + 8
    cH = 120
    cBottom = cTop + cH
    pts = [p for p in m10b if isinstance(p, dict)]
    n = len(pts)
    for tv in (0.0, 0.25, 0.5, 0.75, 1.0):
        gy = cBottom - tv * cH
        E.append(_line(cX0, gy, cX1, gy, "grid"))
        E.append(_text(cX0 - 6, gy + 3.5, _pct(tv), "mut", anchor="end", size=9))

    def _cx(i):
        return cX0 + (i * cW / (n - 1) if n > 1 else cW / 2.0)

    # build polyline segments, breaking at None
    seg_pts = []
    segments = []
    missing_c = 0
    markers = []
    for i, p in enumerate(pts):
        sv = _num(p.get("omni_share"))
        label = str(p.get("point", ""))
        if sv is None:
            missing_c += 1
            if seg_pts:
                segments.append(seg_pts)
                seg_pts = []
            continue
        px = _cx(i)
        py = cBottom - max(0.0, min(1.0, sv)) * cH
        seg_pts.append((px, py))
        markers.append((px, py, label, sv))
    if seg_pts:
        segments.append(seg_pts)
    for sp in segments:
        if len(sp) >= 2:
            d = "M" + " L".join(f"{_nf(x)},{_nf(yy)}" for x, yy in sp)
            E.append(f'<path d="{d}" class="ln"/>')
    for px, py, label, sv in markers:
        E.append(_circle(px, py, 3.5, "s1", ring=True,
                         title=f"{label}: {_pct(sv)} Omni share of bridged BTC"))
    # x labels (every month label used)
    for i, p in enumerate(pts):
        E.append(_text(_cx(i), cBottom + 14, str(p.get("point", "")), "mut",
                       anchor="end", size=8, rot=-45))
    E.append(_line(cX0, cBottom, cX1, cBottom, "axis"))
    # drop following text a clear step (>=8px) below the rotated month labels
    y = cBottom + 14 + _rot_bottom([p.get("point", "") for p in pts], 8) + 18
    if missing_c:
        E.append(_text(cX0, y, f"Gap = {missing_c} month(s) with no readable value (drawn absent).",
                       "mut", size=9))
        y += 14

    y += 4
    E.append(_text(PAD, y,
                   "Measured tokens only. Sources: NearBlocks, archival RPC; see METHOD.md.",
                   "mut", size=10))
    H = y + 18
    return _wrap(W, H, E)


# ---------------------------------------------------------------------------
# chart 2

# bottom-to-top band order; each entry: (legend label, css fill class, [source keys summed])
_BANDS = [
    ("NEAR infrastructure (1)", "s1", ["NEAR infrastructure (1)"]),
    ("FastAuth: Sweat (2a)", "s2", ["FastAuth: Sweat (2a)"]),
    ("FastAuth: other or not attributed", "s3",
     ["FastAuth: other apps (2b, 2c)", "FastAuth: unattributed"]),
    ("health check (ping-account.near)", "s4", ["health check (ping-account.near)"]),
    ("load test (tx-bench.near)", "s5", ["load test (tx-bench.near)"]),
    ("independent apps (4)", "s6", ["independent apps (4)"]),
    ("other and unattributed", "s7",
     ["Aurora XCC, owner not found (4x)", "other tests and demos (3)", "unattributed (5)"]),
]


def _band_value(bands, keys):
    vals = [_num(bands.get(k)) for k in keys]
    present = [v for v in vals if v is not None]
    if not present:
        return None
    return sum(present)


def _chart2(res):
    E = []
    m45 = [r for r in (res.get("M4_M5") or []) if isinstance(r, dict)]
    m8 = [r for r in ((res.get("M8") or {}).get("months") or []) if isinstance(r, dict)]
    months = [str(r.get("month", "")) for r in m45]
    n = len(months)
    idx = {mo: i for i, mo in enumerate(months)}

    E.append(_text(PAD, 26, "Who calls the signer, and what the program costs", "ink",
                   size=17, weight="600"))

    plotX0 = PAD + 48
    plotX1 = W - PAD
    plotW = plotX1 - plotX0
    step = plotW / n if n else plotW
    colW = min(20.0, max(2.0, step - 4))

    def _colx(i):
        return plotX0 + i * step + (step - colW) / 2.0

    # ---- panel a: calls per day by caller band ----------------------------
    E.append(_text(PAD, 46, "a · Calls per day by caller band", "ink", size=12, weight="600"))
    aTop = 56
    aH = 150
    aBottom = aTop + aH
    totals = []
    for r in m45:
        bands = r.get("chart2_bands") or {}
        tot = sum(v for v in (_band_value(bands, b[2]) for b in _BANDS) if v is not None)
        totals.append(tot)
    amax = max(totals, default=0.0)
    aticks, atop = _nice(amax, 5)
    for tv in aticks:
        gy = aBottom - (tv / atop * aH if atop else 0)
        E.append(_line(plotX0, gy, plotX1, gy, "grid"))
        E.append(_text(plotX0 - 6, gy + 3.5, _usd_compact(tv).lstrip("$"), "mut",
                       anchor="end", size=9))
    for i, r in enumerate(m45):
        bands = r.get("chart2_bands") or {}
        x = _colx(i)
        acc = 0.0
        stack = []
        for lbl, cls, keys in _BANDS:
            v = _band_value(bands, keys)
            if v is None or v <= 0:
                continue
            stack.append((lbl, cls, v))
        for j, (lbl, cls, v) in enumerate(stack):
            h = v / atop * aH if atop else 0
            yb = aBottom - acc - h
            drawh = h - 2 if j < len(stack) - 1 else h  # 2px surface gap between segments
            E.append(_rect(x, yb, colW, max(0, drawh), cls,
                           title=f"{months[i]} — {lbl}: {_nf(round(v, 1))} calls/day"))
            acc += h
    E.append(_line(plotX0, aBottom, plotX1, aBottom, "axis"))
    # legend (7 bands, two rows)
    ly = aBottom + 26
    lx = plotX0
    per_row = 4
    for bi, (lbl, cls, keys) in enumerate(_BANDS):
        if bi == per_row:
            lx = plotX0
            ly += 16
        E.append(_swatch(lx, ly, cls, lbl, tsize=9.5))
        lx += 24 + 6.6 * len(lbl)
    panelA_legend_bottom = ly + 10

    # ---- panel b: program expenditure per request -------------------------
    bTopHdr = panelA_legend_bottom + 14
    E.append(_text(PAD, bTopHdr, "b · Program expenditure per request (NEAR per sign request)",
                   "ink", size=12, weight="600"))
    bTop = bTopHdr + 14
    bH = 120
    bBottom = bTop + bH
    # gather values
    rendered = []
    missing_b = 0
    for r in m8:
        mo = str(r.get("month", ""))
        if mo not in idx:
            continue
        prov = bool(r.get("provisional"))
        key = "per_request_proposed" if prov else "per_request_executed_plus_pending"
        m = r.get(key)
        pt = _num(m.get("point")) if isinstance(m, dict) else None
        lo = _num(m.get("lo")) if isinstance(m, dict) else None
        hi = _num(m.get("hi")) if isinstance(m, dict) else None
        if pt is None:
            missing_b += 1
            continue
        rendered.append((idx[mo], mo, prov, pt, lo, hi))
    bmax = max([max(filter(lambda z: z is not None, (pt, hi))) for _, _, _, pt, lo, hi in rendered],
               default=0.0) if rendered else 0.0
    bticks, btop = _nice(bmax, 5)
    for tv in bticks:
        gy = bBottom - (tv / btop * bH if btop else 0)
        E.append(_line(plotX0, gy, plotX1, gy, "grid"))
        E.append(_text(plotX0 - 6, gy + 3.5, _nf(round(tv, 3)), "mut", anchor="end", size=9))

    def _by(v):
        return bBottom - (v / btop * bH if btop else 0)

    for i, mo, prov, pt, lo, hi in rendered:
        cx = plotX0 + i * step + step / 2.0
        if lo is not None and hi is not None:
            E.append(_line(cx, _by(lo), cx, _by(hi), "k1", w=2))
        tip = (f"{mo}: {_near(pt)} per request"
               + (f" [{_near(lo)}–{_near(hi)}]" if lo is not None and hi is not None else "")
               + (" — provisional (proposed report)" if prov else ""))
        if prov:
            E.append(_hollow(cx, _by(pt), 5, "k1", title=tip))
        else:
            E.append(_circle(cx, _by(pt), 5, "s1", ring=True, title=tip))
    E.append(_line(plotX0, bBottom, plotX1, bBottom, "axis"))

    # shared month axis labels (every month label used), at the bottom of panel b.
    # the last month is partial — it runs only up to the T0 cut — so mark it, taking the
    # month from the data so the label follows the real T0 month.
    last = len(months) - 1
    axis_labels = []
    for i, mo in enumerate(months):
        mx = plotX0 + i * step + step / 2.0
        lab = f"{mo} (to T0)" if i == last else mo
        axis_labels.append(lab)
        E.append(_text(mx, bBottom + 14, lab, "mut", anchor="end", size=8, rot=-45))
    # drop following text a clear step (>=8px) below the rotated month labels
    y = bBottom + 14 + _rot_bottom(axis_labels, 8) + 18
    # legend for panel b
    E.append(_circle(plotX0 + 4, y, 5, "s1", ring=True))
    E.append(_text(plotX0 + 14, y + 3.5, "executed + pending", "ink2", size=10))
    E.append(_hollow(plotX0 + 160, y, 5, "k1"))
    E.append(_text(plotX0 + 170, y + 3.5, "provisional (proposed report)", "ink2", size=10))
    y += 16
    E.append(_text(PAD, y,
                   "NEAR paid to signer operators (HSP-007 ledger rows) ÷ M3's sign calls that month.",
                   "mut", size=9))
    y += 14
    if missing_b:
        E.append(_text(PAD, y, f"{missing_b} month(s) with no per-request value (drawn absent).",
                       "mut", size=9))
        y += 14
    y += 4
    E.append(_text(PAD, y,
                   "Sources: NearBlocks windows, neardata blocks, HSP-007 execution thread; see METHOD.md.",
                   "mut", size=10))
    H = y + 18
    return _wrap(W, H, E)


# ---------------------------------------------------------------------------


def render(results, out_dir):
    """Write chart1-routes.svg and chart2-callers-cost.svg into out_dir; return their paths."""
    os.makedirs(out_dir, exist_ok=True)
    p1 = os.path.join(out_dir, "chart1-routes.svg")
    p2 = os.path.join(out_dir, "chart2-callers-cost.svg")
    with open(p1, "w") as f:
        f.write(_chart1(results or {}))
    with open(p2, "w") as f:
        f.write(_chart2(results or {}))
    return [p1, p2]
