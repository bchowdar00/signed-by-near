"""Economic transfers and routes (METHOD §3), from NearBlocks FT rows.

Row semantics (checked on the Nov 9 pilot rows, tests/fixtures): `/v3/fts/<token>/txns` lists a
TRANSFER once, under the receiving account (affected_account_id, positive delta_amount, with the
sender as involved_account_id); a MINT or BURN is listed under the account whose balance changed.
So intents.near's legs in a transaction are
  - rows with affected_account_id == intents.near (its own TRANSFER-in, MINT or BURN), and
  - TRANSFER rows with involved_account_id == intents.near and another affected account
    (intents.near sent tokens; its own change is minus that row's delta).

An economic transfer is one (transaction hash, token) in which intents.near's balance changes;
its amount is the absolute net change, its direction the sign. It is assigned to a window when
its earliest intents.near leg lies in [s, e). Rows are deduplicated by (receipt id, event index,
affected account, cause).

Route, from the counterparties of intents.near's legs in that transaction:
  OMNI     if any counterparty is omni.bridge.near, omni-relayer.bridge.near or *connector.bridge.near;
  POA      else, if the token is *.omft.near and a leg is a MINT or BURN at intents.near or a
           TRANSFER whose counterparty is omft.near (a POA deposit mints to omft.near, which then
           transfers to intents.near);
  NEARSIDE else, if every counterparty is an ordinary NEAR account (not bridge-like, see below);
  UNKNOWN  otherwise.
"""

INTENTS = 'intents.near'
OMNI_EXACT = {'omni.bridge.near', 'omni-relayer.bridge.near'}


def is_omni(a):
    return bool(a) and (a in OMNI_EXACT or a.endswith('connector.bridge.near'))


def bridge_like(a, token):
    if not a:
        return True
    return (a == 'omft.near' or a == token or a.endswith('.bridge.near') or a.endswith('.omft.near')
            or a.endswith('.omdep.near') or a == 'aurora' or a.endswith('.aurora'))


def row_ts(r):
    v = r.get('block_timestamp')
    if v is None:
        v = (r.get('block') or {}).get('block_timestamp')
    return int(v)


def row_id(r):
    return (r.get('receipt_id'), r.get('event_index'), r.get('affected_account_id'), r.get('cause'))


def dedupe(rows):
    seen, out = set(), []
    for r in rows:
        k = row_id(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def intents_legs(rows, token=None):
    for r in rows:
        if token and r.get('contract_account_id') not in (None, token):
            continue
        aff, inv, cause = r.get('affected_account_id'), r.get('involved_account_id'), r.get('cause')
        d = int(r.get('delta_amount') or 0)
        if aff == INTENTS:
            yield {'row': r, 'delta': d, 'cp': inv, 'cause': cause, 'ts': row_ts(r)}
        elif inv == INTENTS and cause == 'TRANSFER' and aff != INTENTS:
            yield {'row': r, 'delta': -d, 'cp': aff, 'cause': cause, 'ts': row_ts(r)}


def has_omni(legs):
    return any(is_omni(l['cp']) for l in legs)


def has_poa(legs, token):
    return token.endswith('.omft.near') and any(l['cause'] in ('MINT', 'BURN') or l['cp'] == 'omft.near' for l in legs)


def route_of(legs, token):
    """METHOD §3: Omni, else POA, else NEAR-side, else unknown; a transaction with both Omni and POA
    legs is unknown (mixed), because no allocation between them is justified."""
    omni, poa = has_omni(legs), has_poa(legs, token)
    if omni and poa:
        return 'UNKNOWN'
    if omni:
        return 'OMNI'
    if poa:
        return 'POA'
    if all(l['cause'] == 'TRANSFER' and not bridge_like(l['cp'], token) for l in legs):
        return 'NEARSIDE'
    return 'UNKNOWN'


def transfers(rows, token, s_ns, e_ns, hi_ns=None, edge_ns=5_000_000_000, span_ns=5_000_000_000):
    """Economic transfers whose earliest intents.near leg lies in [s_ns, e_ns).
    Returns (list of transfers, counters). A transfer is a resolution candidate (METHOD §3) if its
    last observed leg is within edge_ns of the fetched range's end (hi_ns) or its observed legs span
    more than span_ns."""
    rows = dedupe(rows)
    by_tx = {}
    for l in intents_legs(rows, token):
        by_tx.setdefault(l['row'].get('transaction_hash'), []).append(l)
    out, c = [], {'tx_seen': len(by_tx), 'net_zero': 0, 'outside': 0, 'edge_risk': 0, 'mixed': 0}
    for h, legs in by_tx.items():
        first = min(l['ts'] for l in legs)
        if not (s_ns <= first < e_ns):
            c['outside'] += 1
            continue
        net = sum(l['delta'] for l in legs)
        if net == 0:
            c['net_zero'] += 1
            continue
        route = route_of(legs, token)
        mixed = has_omni(legs) and has_poa(legs, token)
        c['mixed'] += mixed
        last = max(l['ts'] for l in legs)
        edge = hi_ns is not None and last > hi_ns - edge_ns
        c['edge_risk'] += edge
        span = last - first
        resolve = edge or span > span_ns
        c['resolve_candidates'] = c.get('resolve_candidates', 0) + resolve
        out.append({'tx': h, 'token': token, 'ts_ns': first, 'amount': abs(net), 'direction': 'in' if net > 0 else 'out',
                    'route': route, 'mixed': mixed, 'edge_risk': edge, 'span_ns': span, 'resolve': resolve,
                    'n_legs': len(legs), 'counterparties': sorted({str(l['cp']) for l in legs})})
    return out, c


def resolved_legs(body, token):
    """Intents' legs of one transaction read whole from /v3/txns/{hash}/fts (METHOD §3). That endpoint
    lists both sides of a TRANSFER and every token's events, so Intents' legs are exactly the rows of
    this token whose affected account is intents.near, with their own signed deltas."""
    legs = []
    for r in (body or {}).get('data') or []:
        if r.get('contract_account_id') != token or r.get('affected_account_id') != INTENTS:
            continue
        legs.append({'ts': row_ts(r), 'delta': int(r['delta_amount']), 'cp': r.get('involved_account_id'),
                     'cause': r.get('cause'), 'row': r})
    return legs


def resolved_transfer(body, token):
    """(first leg ns, net, route) of a resolved transaction for this token, or None if Intents has no leg."""
    legs = resolved_legs(body, token)
    if not legs:
        return None
    return min(l['ts'] for l in legs), sum(l['delta'] for l in legs), route_of(legs, token)


def census_tokens(rows):
    """Omni census rows (account endpoint for omni.bridge.near, involved=intents.near): tokens seen
    moving between Omni and intents.near, and whether every row involves intents.near."""
    rows = dedupe(rows)
    toks, off = {}, 0
    for r in rows:
        if r.get('involved_account_id') != INTENTS:
            off += 1
            continue
        toks[r.get('contract_account_id')] = toks.get(r.get('contract_account_id'), 0) + 1
    return toks, off
