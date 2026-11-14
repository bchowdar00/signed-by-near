"""Core: load frozen windows, check completion, build economic transfers (METHOD 3).
python3 -I. Read-only on the named paths."""
import glob
import json
import os

REPO = os.environ['RD_REPO']  # parent: was this Mac's repo path; set by mc-seeds/sweep.py
DATA = os.environ['RD_DATA']  # parent: was this Mac's data path; set by mc-seeds/sweep.py
INSTANTS = os.path.join(REPO, 'frozen', 'instants.json')
PAGES = os.path.join(DATA, 'nb', 'pages')
WINDOWS_JSONL = os.path.join(DATA, 'nb', 'windows.jsonl')

OMNI_ACCTS = {'omni.bridge.near', 'omni-relayer.bridge.near'}
INTENTS = 'intents.near'


def load_windows():
    d = json.load(open(INSTANTS))
    return d['meta'], d['windows']


def load_status():
    """Return dict id -> last event ('completed'/'not_completed'/...)."""
    ev = {}
    with open(WINDOWS_JSONL) as f:
        for line in f:
            line = line.strip()
            if line:
                e = json.loads(line)
                if e['event'] in ('completed', 'not_completed'):
                    ev[e['id']] = e['event']
    return ev


def seg_count(w):
    return len(w['segments_ns'])


def pages_of(wid, seg):
    """All page dicts for one segment, sorted by page number (like sampler.pages_of)."""
    d = os.path.join(PAGES, wid)
    ps = sorted(glob.glob(os.path.join(d, f'{seg:02d}-*.json')),
                key=lambda p: int(p.rsplit('-', 1)[1][:-5]))
    out = []
    for p in ps:
        with open(p) as f:
            out.append(json.load(f))
    return out


def window_page_count(w):
    n = 0
    for seg in range(seg_count(w)):
        n += len(pages_of(w['id'], seg))
    return n


def is_completed(w, status_ev):
    """DEVIATIONS 17 + COMMON: completed event AND pages form a gapless chain,
    done, all HTTP 200, for every segment. Returns (bool, reason)."""
    if status_ev.get(w['id']) != 'completed':
        return False, 'no completed event (%s)' % status_ev.get(w['id'])
    for seg in range(seg_count(w)):
        ps = pages_of(w['id'], seg)
        if not ps:
            return False, f'seg {seg} has no pages'
        # gapless: page numbers 0..k contiguous
        nums = [p['page'] for p in ps]
        if nums != list(range(len(ps))):
            return False, f'seg {seg} page numbers not gapless: {nums}'
        if not ps[-1].get('done'):
            return False, f'seg {seg} last page not done'
        for p in ps:
            if p.get('http') != 200:
                return False, f'seg {seg} page {p["page"]} http={p.get("http")}'
    return True, 'ok'


# ---------- economic transfers (METHOD 3) ----------
def _is_omni_counterparty(acct):
    return acct in OMNI_ACCTS or acct.endswith('connector.bridge.near')


def _ordinary_near_account(acct, token):
    if acct in ('omft.near', token, 'aurora'):
        return False
    if acct.endswith('.aurora'):
        return False
    for suf in ('.bridge.near', '.omft.near', '.omdep.near'):
        if acct.endswith(suf):
            return False
    return True


def _row_key(r):
    return (r['receipt_id'], r['event_index'], r['affected_account_id'], r['cause'])


def _row_ts(r):
    v = r.get('block_timestamp')
    if v is None:
        v = (r.get('block') or {}).get('block_timestamp')
    return int(v)


def intents_legs_window(rows, token):
    """From window-view rows (fts/<token>/txns), return Intents legs grouped by tx.
    A leg = dict(ts, delta (Intents' signed change), counterparty, cause, mintburn_at_intents).
    Per METHOD 3: type A affected==intents.near (delta = row delta);
    type B TRANSFER with involved==intents.near, affected!=intents (delta = -row delta)."""
    by_tx = {}
    for r in rows:
        if r.get('contract_account_id') != token:
            continue
        aff = r['affected_account_id']
        inv = r.get('involved_account_id')
        cause = r['cause']
        if aff == INTENTS:
            delta = int(r['delta_amount'])
            cp = inv
            mb = cause in ('MINT', 'BURN')
        elif cause == 'TRANSFER' and inv == INTENTS and aff != INTENTS:
            delta = -int(r['delta_amount'])
            cp = aff
            mb = False
        else:
            continue
        leg = {'ts': _row_ts(r), 'delta': delta, 'cp': cp, 'cause': cause, 'mb_at_intents': mb}
        by_tx.setdefault(r['transaction_hash'], []).append(leg)
    return by_tx


def intents_legs_whole(rows, token):
    """From whole-tx rows (txns/<h>/fts body.data): Intents legs are rows with
    affected==intents.near; delta = row delta; counterparty = involved."""
    legs = []
    for r in rows:
        if r.get('contract_account_id') != token:
            continue
        if r['affected_account_id'] == INTENTS:
            legs.append({'ts': _row_ts(r), 'delta': int(r['delta_amount']),
                         'cp': r.get('involved_account_id'),
                         'cause': r['cause'],
                         'mb_at_intents': r['cause'] in ('MINT', 'BURN')})
    return legs


def route_of(legs, token):
    """METHOD 3 route of a transfer from its Intents legs."""
    has_omni = any(_is_omni_counterparty(l['cp']) for l in legs if l['cp'])
    is_omft = token.endswith('.omft.near')
    has_poa = False
    if is_omft:
        for l in legs:
            if l['mb_at_intents'] and l['cause'] in ('MINT', 'BURN'):
                has_poa = True
            if l['cause'] == 'TRANSFER' and l['cp'] == 'omft.near':
                has_poa = True
    if has_omni and has_poa:
        return 'mixed'
    if has_omni:
        return 'omni'
    if has_poa:
        return 'poa'
    if all(l['cause'] == 'TRANSFER' and l['cp'] and _ordinary_near_account(l['cp'], token) for l in legs):
        return 'near-side'
    return 'unknown'


def build_transfers(rows, token, s_ns, e_ns, hi_ns, dedup=True):
    """Build economic transfers for a window from its (deduped) window-view rows.
    s_ns,e_ns = segment [s,e); hi_ns = fetched range end (e+guard).
    Returns list of transfers assigned to [s,e)."""
    if dedup:
        seen = set()
        uniq = []
        for r in rows:
            k = _row_key(r)
            if k in seen:
                continue
            seen.add(k)
            uniq.append(r)
        rows = uniq
    by_tx = intents_legs_window(rows, token)
    out = []
    for tx, legs in by_tx.items():
        net = sum(l['delta'] for l in legs)
        if net == 0:
            continue  # net-zero group dropped
        tss = [l['ts'] for l in legs]
        first = min(tss)
        last = max(tss)
        if not (s_ns <= first < e_ns):
            continue
        route = route_of(legs, token)
        # NEAR-side kept here (tagged); excluded only at share computation (METHOD 3)
        edge = last > hi_ns - 5_000_000_000
        span = last - first
        out.append({
            'tx': tx, 'token': token, 'amount_raw': abs(net),
            'direction': 'in' if net > 0 else 'out', 'net': net,
            'first': first, 'last': last, 'span_ns': span,
            'route': route, 'edge': edge,
            'resolve': edge or span > 5_000_000_000,
            'n_legs': len(legs),
        })
    return out


def window_rows(w):
    """All deduped page rows across all segments of a window, with per-seg [s,e,hi]."""
    segs = []
    g = int(round(w.get('guard_s', 0.0) * 1e9))
    for seg, (s, e) in enumerate(w['segments_ns']):
        rows = [r for p in pages_of(w['id'], seg) for r in p['rows']]
        segs.append((rows, int(s), int(e), int(e) + g))
    return segs


def window_transfers(w):
    """Transfers for a whole window across its segments (dedup within window overall)."""
    g = int(round(w.get('guard_s', 0.0) * 1e9))
    # dedup across the whole window
    seen = set()
    all_rows_by_seg = []
    for seg, (s, e) in enumerate(w['segments_ns']):
        rows = []
        for p in pages_of(w['id'], seg):
            for r in p['rows']:
                k = _row_key(r)
                if k in seen:
                    continue
                seen.add(k)
                rows.append(r)
        all_rows_by_seg.append((rows, int(s), int(e), int(e) + g))
    out = []
    for rows, s, e, hi in all_rows_by_seg:
        out.extend(build_transfers(rows, w['token'], s, e, hi, dedup=False))
    return out
