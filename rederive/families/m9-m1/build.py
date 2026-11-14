"""Build economic transfers from the frozen flow windows and check completion (METHOD 3, 4.0, 6.5;
DEVIATIONS 3, 10, 12, 17). Data formats only are taken from the collector; all route logic here is
re-derived from METHOD 3. No network, no recursive search: pages are listed with os.listdir on the
one named window directory.
"""
import json, os

REPO = os.environ['RD_REPO']
DATA = os.environ['RD_DATA']
INTENTS = 'intents.near'

# ---------- load frozen windows ----------

def load_instants():
    return json.load(open(os.path.join(REPO, 'frozen/instants.json')))


def load_tokens():
    d = json.load(open(os.path.join(REPO, 'frozen/tokens.json')))
    return {t['contract']: t for t in d['tokens']}


def completed_ids():
    ids = set()
    for line in open(os.path.join(DATA, 'nb/windows.jsonl')):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get('event') == 'completed':
            ids.add(r['id'])
    return ids


# ---------- page loading + completion ----------

def _page_files(wid):
    d = os.path.join(DATA, 'nb/pages', wid)
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


def load_pages(wid):
    out = []
    d = os.path.join(DATA, 'nb/pages', wid)
    for fn in _page_files(wid):
        if fn.endswith('.json'):
            out.append(json.load(open(os.path.join(d, fn))))
    return out


def check_completion(win, comp_ids):
    """A window is completed iff: it has a completed event; one gapless done page-chain per segment,
    all HTTP 200 (DEVIATIONS 17). Returns (ok, reason)."""
    wid = win['id']
    if wid not in comp_ids:
        return False, 'no completed event'
    pages = load_pages(wid)
    if not pages:
        return False, 'no pages'
    if any(p.get('http') != 200 for p in pages):
        return False, 'non-200 page'
    nseg = len(win['segments_ns'])
    byseg = {}
    for p in pages:
        byseg.setdefault(p['seg'], []).append(p)
    if set(byseg) != set(range(nseg)):
        return False, f'segment set {sorted(byseg)} != {list(range(nseg))}'
    for seg, ps in byseg.items():
        ps = sorted(ps, key=lambda p: p['page'])
        nums = [p['page'] for p in ps]
        if nums != list(range(len(ps))):
            return False, f'seg {seg} page gap {nums}'
        # gapless chain: each non-final page has a next cursor, final page done
        for i, p in enumerate(ps):
            if i < len(ps) - 1 and not p.get('next'):
                return False, f'seg {seg} page {i} no next cursor'
        if not ps[-1].get('done'):
            return False, f'seg {seg} last page not done'
    return True, 'ok'


# ---------- row dedup ----------

def dedup_rows(pages):
    seen = set()
    rows = []
    for p in pages:
        for r in p['rows']:
            key = (r['receipt_id'], r['event_index'], r['affected_account_id'], r['cause'])
            if key in seen:
                continue
            seen.add(key)
            rows.append(r)
    return rows


# ---------- account / route helpers (METHOD 3) ----------

def is_omni_counterparty(acc):
    if acc is None:
        return False
    return acc in ('omni.bridge.near', 'omni-relayer.bridge.near') or acc.endswith('connector.bridge.near')


def is_ordinary_near(acc, token):
    """Not ordinary if omft.near, the token itself, aurora/*.aurora, or ends in
    .bridge.near / .omft.near / .omdep.near (METHOD 3 NEAR-side clause)."""
    if acc is None:
        return False
    if acc == 'omft.near' or acc == token or acc == 'aurora' or acc.endswith('.aurora'):
        return False
    if acc.endswith('.bridge.near') or acc.endswith('.omft.near') or acc.endswith('.omdep.near'):
        return False
    return True


def intents_legs(group_rows, token):
    """Return Intents' legs for a (tx, token) group: list of dicts {delta, counterparty, cause, ts, affected}."""
    legs = []
    for r in group_rows:
        aff = r['affected_account_id']
        inv = r['involved_account_id']
        cause = r['cause']
        delta = int(r['delta_amount'])
        ts = int(r['block_timestamp'])
        if aff == INTENTS:
            legs.append({'delta': delta, 'counterparty': inv, 'cause': cause, 'ts': ts, 'affected': aff})
        elif cause == 'TRANSFER' and inv == INTENTS and aff != INTENTS:
            legs.append({'delta': -delta, 'counterparty': aff, 'cause': 'TRANSFER', 'ts': ts, 'affected': aff})
    return legs


def route_of(legs, token):
    """Route per METHOD 3 from the counterparties of Intents' legs."""
    omft = token.endswith('.omft.near')
    has_omni = any(is_omni_counterparty(l['counterparty']) for l in legs)
    # POA leg: token is *.omft.near AND (MINT/BURN at intents.near, OR TRANSFER from/to omft.near)
    has_poa = False
    if omft:
        for l in legs:
            if l['cause'] in ('MINT', 'BURN') and l['affected'] == INTENTS:
                has_poa = True
            elif l['cause'] == 'TRANSFER' and l['counterparty'] == 'omft.near':
                has_poa = True
    if has_omni and has_poa:
        return 'mixed'
    if has_omni:
        return 'omni'
    if has_poa:
        return 'poa'
    # NEAR-side: every leg is a TRANSFER with an ordinary NEAR account
    if legs and all(l['cause'] == 'TRANSFER' and is_ordinary_near(l['counterparty'], token) for l in legs):
        return 'near-side'
    return 'unknown'


def build_transfers_for_window(win, token):
    """Economic transfers in one flow window (observed legs; candidates==0 so no resolution)."""
    pages = load_pages(win['id'])
    rows = dedup_rows(pages)
    segs = win['segments_ns']
    # group by transaction hash (token is fixed for this window's endpoint)
    groups = {}
    for r in rows:
        groups.setdefault(r['transaction_hash'], []).append(r)
    transfers = []
    for tx, grows in groups.items():
        legs = intents_legs(grows, token)
        if not legs:
            continue
        net = sum(l['delta'] for l in legs)
        earliest = min(l['ts'] for l in legs)
        latest = max(l['ts'] for l in legs)
        in_window = any(s <= earliest < e for (s, e) in segs)
        if not in_window:
            continue
        if net == 0:
            continue  # net-zero drops
        route = route_of(legs, token)
        # edge risk: last leg within 5 s of a fetched range end (fetched = seg +/- 30 s guard)
        edge = any((s - 30_000_000_000) <= latest and latest >= (e + 30_000_000_000) - 5_000_000_000
                   and latest <= (e + 30_000_000_000) for (s, e) in segs)
        span = latest - earliest
        transfers.append({'tx': tx, 'token': token, 'net': net, 'amount': abs(net),
                          'direction': 'in' if net > 0 else 'out', 'route': route,
                          'earliest': earliest, 'span_ns': span, 'edge': edge, 'nlegs': len(legs)})
    return transfers


if __name__ == '__main__':
    inst = load_instants()
    comp = completed_ids()
    flow = [w for w in inst['windows'] if w['family'] == 'flow']
    census = [w for w in inst['windows'] if w['family'] == 'census']
    bad = []
    for w in flow + census:
        ok, why = check_completion(w, comp)
        if not ok:
            bad.append((w['family'], w['id'], w.get('stratum'), why))
    print('flow windows', len(flow), 'census', len(census))
    print('not completed:', len(bad))
    for b in bad[:20]:
        print(' ', b)
