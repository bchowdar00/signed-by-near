"""neardata analysis of the MPC signer `v1.signer` (METHOD M4, M6, M7), pure Python. Reads the
per-block call extracts the sampler writes (`nd/blocks.jsonl`, one JSON record per block; see
collector/nd.py `extract`). Uncounted: it reads saved files only, never the counted sample.

Three things:
  - M4  FastAuth signer shares per month, with a Clopper-Pearson block-level bound (via intervals).
  - M6  a purpose class for each `sign` call (key type and path).
  - M7  request/response completion on a contiguous run.

`sign` argument shapes seen on mainnet (both handled):
  newer: {"request": {"path": str, "payload_v2": {"Ecdsa": hex} | {"Eddsa": hex}, "domain_id": int}}
  older: {"request": {"payload": [byte, ...], "path": str, "key_version": int}}  -- always secp256k1
`respond` argument shape:
  {"request": {"tweak": [byte, ...], "payload": {"Ecdsa"|"Eddsa": hex}, "domain_id": int},
   "response": {...}}
The respond's request carries the signed payload and the epsilon-derivation tweak of the `sign`
it answers; a `sign`'s tweak is derived here and compared (verified against real data, M7).
"""
import hashlib
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import intervals  # noqa: E402  (kish, clopper_pearson, window_cp)

EPSILON_PREFIX = 'near-mpc-recovery v0.1.0 epsilon derivation:'
FASTAUTH = 'fast-auth.near'


class Blocks(list):
    """A list of kept block records (http 200 and present). `.skipped` holds the dropped records
    and `.n_total` the number read, so callers can report coverage."""

    def __init__(self, kept=(), skipped=(), n_total=0):
        super().__init__(kept)
        self.skipped = list(skipped)
        self.n_total = n_total


def load(path_or_records):
    """A path to an nd blocks.jsonl, or an already-parsed list of records, in; the kept block
    records (http == 200 and present) out, as a `Blocks` whose `.skipped` lists the rest."""
    if isinstance(path_or_records, str):
        records = []
        with open(path_or_records) as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
    else:
        records = list(path_or_records)
    kept, skipped = [], []
    for r in records:
        if r.get('http') == 200 and r.get('present'):
            kept.append(r)
        else:
            skipped.append(r)
    return Blocks(kept, skipped, len(records))


# --- sign calls ----------------------------------------------------------------------------------

def sign_calls(blocks):
    """Every `sign` call across the blocks, each augmented with its block's `part` (the call
    already carries `ts_ns` and `height`)."""
    out = []
    for b in blocks:
        for c in b.get('calls') or []:
            if c.get('method') == 'sign':
                out.append({**c, 'part': b.get('part')})
    return out


# --- M4: FastAuth signer shares ------------------------------------------------------------------

def _is_fastauth(call):
    return call.get('method') == 'sign' and call.get('predecessor') == FASTAUTH


def fastauth_counts_by_block(blocks, month):
    """One Counter per `sample:<month>` block, keyed by transaction signer, over the FastAuth
    `sign` calls in that block. Blocks with no FastAuth call are included as empty Counters.
    Ordered by block height."""
    part = 'sample:' + month
    out = []
    for b in sorted((b for b in blocks if b.get('part') == part), key=lambda b: b.get('height', 0)):
        c = Counter()
        for call in b.get('calls') or []:
            if _is_fastauth(call):
                c[call.get('signer')] += 1
        out.append(c)
    return out


def signer_share(per_block_counters, signer):
    """(share, total_fastauth_calls): the signer's share of all FastAuth calls across the blocks,
    and that total. Share is 0.0 when there are no FastAuth calls."""
    total = sum(sum(c.values()) for c in per_block_counters)
    hit = sum(c.get(signer, 0) for c in per_block_counters)
    return ((hit / total) if total else 0.0, total)


def signer_bound(per_block_counters, signer, alpha=0.05):
    """Clopper-Pearson bound for the signer's share, blocks as trials (METHOD M4, S4.0):
    m = Kish effective count over the per-block FastAuth totals a (blocks with a > 0), successes
    = share * m. Returns (lower, upper), or None when there are no FastAuth calls."""
    totals = [t for t in (sum(c.values()) for c in per_block_counters) if t > 0]
    if not totals:
        return None
    m = intervals.kish(totals)
    share, _ = signer_share(per_block_counters, signer)
    return intervals.clopper_pearson(share * m, m, alpha)


# --- M6: purpose ---------------------------------------------------------------------------------

def _payload_hex(obj):
    """Canonical lower-case hex of a payload, whichever encoding the call used: a byte list, a
    hex string, or a {scheme: hex} wrapper. Returns (hex, scheme) with scheme in
    {'Ecdsa', 'Eddsa', None}, or (None, None) if unreadable."""
    if isinstance(obj, list):
        try:
            return bytes(obj).hex(), None
        except (ValueError, TypeError):
            return None, None
    if isinstance(obj, dict):
        for scheme in ('Ecdsa', 'Eddsa'):
            if scheme in obj:
                v = obj[scheme]
                if isinstance(v, list):
                    try:
                        return bytes(v).hex(), scheme
                    except (ValueError, TypeError):
                        return None, None
                if isinstance(v, str):
                    return v.lower(), scheme
        return None, None
    if isinstance(obj, str):
        return obj.lower(), None
    return None, None


def _solana_or_near(path):
    """Tell a non-login Ed25519 path's chain apart ONLY where the path makes it explicit, per M6;
    otherwise 'unknown'. Conservative substring match on the path."""
    p = (path or '').lower()
    if 'solana' in p or p.startswith('sol,') or p.startswith('sol#') or p == 'sol':
        return 'ed25519_other_solana'
    if 'near' in p:
        return 'ed25519_other_near'
    return 'ed25519_other_unknown'


def purpose_of(call):
    """Purpose class of a `sign` call (METHOD M6):
      'secp256k1'                - domain 0: EVM / Bitcoin / Zcash, cross-chain capable;
      'ed25519_fastauth_login'   - Ed25519 whose path starts with 'jwt#';
      'ed25519_other_near' | 'ed25519_other_solana' | 'ed25519_other_unknown' - other Ed25519;
      'unparsed'                 - the arguments cannot be read.
    The payload tag (Ecdsa/Eddsa) decides the key type; the older byte-array form is secp256k1."""
    args = call.get('args')
    if not isinstance(args, dict) or '_undecoded_b64' in args:
        return 'unparsed'
    req = args.get('request')
    if not isinstance(req, dict):
        return 'unparsed'
    path = req.get('path')
    if 'payload' in req and 'payload_v2' not in req:
        # older form: a byte-array payload, always secp256k1 (domain 0)
        hexp, _ = _payload_hex(req.get('payload'))
        return 'secp256k1' if hexp is not None else 'unparsed'
    if 'payload_v2' in req:
        hexp, scheme = _payload_hex(req.get('payload_v2'))
        if hexp is None or scheme is None:
            return 'unparsed'
        if scheme == 'Ecdsa':
            return 'secp256k1'
        # Eddsa -> Ed25519 (domain 1)
        if isinstance(path, str) and path.startswith('jwt#'):
            return 'ed25519_fastauth_login'
        return _solana_or_near(path)
    return 'unparsed'


def purpose_by_month(blocks):
    """(by_month, by_month_predecessor) over `sign` calls in `sample:<month>` blocks:
      by_month             = {month: Counter(purpose)}
      by_month_predecessor = {month: {predecessor: Counter(purpose)}}."""
    by_month = defaultdict(Counter)
    by_pred = defaultdict(lambda: defaultdict(Counter))
    for call in sign_calls(blocks):
        part = call.get('part') or ''
        if not part.startswith('sample:'):
            continue
        month = part.split('sample:', 1)[1]
        p = purpose_of(call)
        by_month[month][p] += 1
        by_pred[month][call.get('predecessor')][p] += 1
    by_month = {m: c for m, c in by_month.items()}
    by_pred = {m: {pred: cc for pred, cc in d.items()} for m, d in by_pred.items()}
    return by_month, by_pred


# --- M7: completion ------------------------------------------------------------------------------

def tweak_of(predecessor, path):
    """The epsilon-derivation tweak of a `sign`: SHA3-256 of the prefix + predecessor + ',' + path,
    as lower-case hex (METHOD M7; verified equal to the respond's tweak on real data)."""
    return hashlib.sha3_256((EPSILON_PREFIX + (predecessor or '') + ',' + (path or '')).encode()).hexdigest()


def _succeeded(status):
    return isinstance(status, dict) and any(k.startswith('Success') for k in status)


def _sign_key(call):
    """(payload_hex, tweak_hex, domain) for a `sign` call, or None if unreadable."""
    args = call.get('args')
    if not isinstance(args, dict):
        return None
    req = args.get('request')
    if not isinstance(req, dict):
        return None
    if 'payload' in req and 'payload_v2' not in req:
        hexp, _ = _payload_hex(req.get('payload'))
        domain = 0  # the older form is always secp256k1, which is domain 0 (key_version is not a domain)
    else:
        hexp, _ = _payload_hex(req.get('payload_v2'))
        domain = req.get('domain_id')
    if hexp is None:
        return None
    tw = tweak_of(call.get('predecessor'), req.get('path'))
    return (hexp, tw, domain)


def _respond_key(call):
    """(payload_hex, tweak_hex, domain) for a `respond` call, or None if unreadable."""
    args = call.get('args')
    if not isinstance(args, dict):
        return None
    req = args.get('request')
    if not isinstance(req, dict):
        return None
    hexp, _ = _payload_hex(req.get('payload'))
    tw = req.get('tweak')
    if isinstance(tw, list):
        try:
            tw = bytes(tw).hex()
        except (ValueError, TypeError):
            tw = None
    elif isinstance(tw, str):
        tw = tw.lower()
    else:
        tw = None
    if hexp is None or tw is None:
        return None
    return (hexp, tw, req.get('domain_id'))


def completion(blocks, n_context=100, n_tail=100):
    """Request/response completion on the `contiguous` blocks (METHOD M7).

    Blocks of part 'contiguous', sorted by height, are split by rank: the first `n_context`
    are context only, the last `n_tail` are for responses only, and the requests in the middle
    are the ones evaluated. "At or after" is compared on (block height, index of the call within
    the block's `calls` list) -- the within-block order the extractor produced.

    A `sign` request pairs, within its (payload, tweak, domain) group, with a `respond` receipt
    that SUCCEEDED and comes at or after it, in order, each respond used once (METHOD M7: "pairs
    with a respond receipt that succeeded"). Failed responds are never paired; they are counted in
    `failed_responses_seen`. A request with no succeeded respond by the end is censored, not failed.
    A request whose group has a member in the context blocks is ambiguous and is not counted as a
    proven completion. Only responds in the middle/tail region are candidates.

    matched_share = matched / evaluated: ambiguous and censored requests stay in the denominator
    and are reported as counts beside it (DEVIATIONS 22). matched_share_unambiguous = matched /
    (evaluated - ambiguous). Delays are conditional on matched pairs. Returns a dict (see the keys
    assembled at the end)."""
    contig = sorted((b for b in blocks if b.get('part') == 'contiguous'), key=lambda b: b.get('height', 0))
    n = len(contig)
    region = {}  # height -> 'context' | 'middle' | 'tail'
    for i, b in enumerate(contig):
        if i < n_context:
            region[b['height']] = 'context'
        elif i >= n - n_tail:
            region[b['height']] = 'tail'
        else:
            region[b['height']] = 'middle'

    # collect requests and responds with positions
    reqs = defaultdict(list)       # key -> list of {pos, region, call}
    resps = defaultdict(list)      # key -> list of {pos, region, ok, call}
    failed_responses_seen = 0
    for b in contig:
        reg = region[b['height']]
        for idx, c in enumerate(b.get('calls') or []):
            pos = (b['height'], idx)
            m = c.get('method')
            if m == 'sign':
                k = _sign_key(c)
                if k is not None:
                    reqs[k].append({'pos': pos, 'region': reg, 'call': c})
            elif m == 'respond':
                ok = _succeeded(c.get('status'))
                if not ok:
                    failed_responses_seen += 1
                k = _respond_key(c)
                if ok and k is not None and reg in ('middle', 'tail'):
                    resps[k].append({'pos': pos, 'region': reg, 'ok': ok, 'call': c})

    evaluated = matched = matched_unique = matched_by_order = ambiguous = censored = 0
    unmatched_responses = 0
    delays = []
    pairs = []

    keys = set(reqs) | set(resps)
    for k in keys:
        group_reqs = sorted(reqs.get(k, []), key=lambda r: r['pos'])
        group_resps = sorted(resps.get(k, []), key=lambda r: r['pos'])
        has_context_req = any(r['region'] == 'context' for r in group_reqs)
        # non-context request count and succeeded-respond count fix the unique/by-order label
        non_ctx_reqs = [r for r in group_reqs if r['region'] != 'context']
        n_ok_resps = sum(1 for r in group_resps if r['ok'])
        is_unique_group = len(non_ctx_reqs) == 1 and n_ok_resps == 1

        # pair only the middle (evaluated) requests, in order, against middle/tail responds
        middle_reqs = [r for r in group_reqs if r['region'] == 'middle']
        used = [False] * len(group_resps)
        for r in middle_reqs:
            evaluated += 1
            if has_context_req:
                ambiguous += 1
                continue
            # earliest unused respond at or after this request
            paired = None
            for j, rsp in enumerate(group_resps):
                if used[j]:
                    continue
                if rsp['pos'] < r['pos']:
                    continue
                paired = (j, rsp)
                break
            if paired is None:
                censored += 1
                continue
            j, rsp = paired
            used[j] = True
            matched += 1
            delay = (rsp['call'].get('ts_ns', 0) - r['call'].get('ts_ns', 0)) / 1e9
            delays.append(delay)
            label = 'unique' if is_unique_group else 'by order'
            if is_unique_group:
                matched_unique += 1
            else:
                matched_by_order += 1
            pairs.append({'payload_hex': k[0], 'tweak_hex': k[1], 'domain': k[2],
                          'req_height': r['pos'][0], 'resp_height': rsp['pos'][0],
                          'delay_s': delay, 'label': label})
        # succeeded responds in middle/tail never used by any middle request
        for j, rsp in enumerate(group_resps):
            if rsp['ok'] and not used[j]:
                unmatched_responses += 1

    unamb = evaluated - ambiguous
    return {
        'n_blocks': n,
        'evaluated': evaluated,
        'matched': matched,
        'matched_unique': matched_unique,
        'matched_by_order': matched_by_order,
        'ambiguous': ambiguous,
        'censored': censored,
        'failed_responses_seen': failed_responses_seen,
        'unmatched_responses': unmatched_responses,
        'matched_share': (matched / evaluated) if evaluated else None,
        'matched_share_unambiguous': (matched / unamb) if unamb else None,
        'median_delay_s': statistics.median(delays) if delays else None,
        'max_delay_s': max(delays) if delays else None,
        'pairs': pairs,
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    bl = load(sys.argv[1])
    res = {'n_kept': len(bl), 'n_skipped': len(bl.skipped), 'completion': completion(bl)}
    print(json.dumps(res, indent=1, sort_keys=True, default=str))
