"""Independent re-derivation of the Explorer read, in the categories the thesis lead asked for
(round 1, 2026-11-14), with exact decimal sums.

Written by the parent session from explorer/PLAN.md (sha256 019d347a...), explorer/STAGE2.md
(3a86eb5c...), explorer/data/assets.json (ca5b7fd9...) and the SDK's list of 17 migrated tokens
(poa-tokens-migrated-to-omni-bridge.ts at 930d2816, sha256 ed49694c..., the hash STAGE2.md gives).
explorer/analyse.py, sentences.py, recheck.py, test_explorer.py, RESULTS.md, results.json and
THESIS.md were not read. The rule functions are copied unchanged from rd_explorer.py.

Usage: python3 -I rd_explorer_exact.py <blocks.jsonl> <assets.json> <sdk_list.ts> <out.json>
Standard library only. Sums are exact (decimal.Decimal over the file's decimal strings);
shares are quotients at 30 significant digits.
"""
import sys, json, re, hashlib, datetime as dt
from collections import defaultdict
from decimal import Decimal, localcontext

T_START = dt.datetime(2026, 8, 12, 11, 0, tzinfo=dt.timezone.utc)   # PLAN section 3
NBLOCKS = 90
LAST30 = range(60, 90)                                               # the 30 days to T0
SAMPLED8 = ('btc', 'sol', 'zec', 'eth', 'arb', 'base', 'tron', 'xrp')
HOT_PREFIX = 'nep245:v2_1.omni.hot.tg:'
SDK_SHA = 'ed49694cd4641f48041e92b6dfa58bf133918e4cd5fce2f75a505a227fe3eb01'
FAMILY_CAT = {'Omni': 'omni', 'POA, SDK-listed as moved to Omni': 'sdk', 'POA': 'poa',
              'HOT': 'hot', 'unclassified': 'unclassified',
              'a token on NEAR': 'other_form_on_non_near_chain'}
BRIDGED = ('omni', 'sdk', 'poa', 'hot', 'unclassified')
CATS = BRIDGED + ('near', 'inside', 'other_form_on_non_near_chain')
ZERO = Decimal(0)


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


# ---- rule functions, unchanged from rd_explorer.py ----
def load_sdk_list(path):
    ids = re.findall(r'"([a-z0-9-]+\.omft\.near)"\s*:\s*ChainKind\.', open(path).read())
    assert len(ids) == 17 and len(set(ids)) == 17, ('SDK list must hold 17 tokens', len(ids))
    return set(ids)


def load_assets(path):
    a = json.load(open(path))['assets']
    chain = {k: v[0] for k, v in a.items()}
    hot_ids = defaultdict(set)
    for k, c in chain.items():
        if k.startswith(HOT_PREFIX):
            hot_ids[k[len(HOT_PREFIX):].split('_', 1)[0]].add(c)
    hot_chain = {i: next(iter(cs)) for i, cs in hot_ids.items() if len(cs) == 1}
    return chain, hot_chain


def bare(asset):
    return asset[len('nep141:'):] if asset.startswith('nep141:') else asset


PREFIX_CHAIN = {}   # filled in main(): ID prefix -> the token list's chain code, where the list is consistent


def prefix_map(chain):
    """For .omft.near / .omdep.near IDs the list does give, the chain code it gives each ID prefix
    (e.g. the list files nep141:bnb-...omdep.near under 'bsc'). Only prefixes with one code."""
    seen = defaultdict(set)
    for k, c in chain.items():
        b = bare(k)
        if c != 'near' and k.startswith('nep141:') and (b.endswith('.omft.near') or b.endswith('.omdep.near')):
            seen[re.split(r'[.-]', b, maxsplit=1)[0]].add(c)
    return {p: next(iter(cs)) for p, cs in seen.items() if len(cs) == 1}


def chain_of(asset, chain, hot_chain):
    """The chain the token is delivered on: the token list's, else read from the ID (STAGE2).
    Change from rd_explorer.py: an unlisted ID's prefix is translated by the list's own convention."""
    if asset in chain:
        return chain[asset], 'list'
    b = bare(asset)
    if b.endswith('.omft.near') or b.endswith('.omdep.near'):
        p = re.split(r'[.-]', b, maxsplit=1)[0]
        return PREFIX_CHAIN.get(p, p), ('id, prefix by the list' if p in PREFIX_CHAIN and PREFIX_CHAIN[p] != p else 'id')
    if asset.startswith(HOT_PREFIX):
        cid = asset[len(HOT_PREFIX):].split('_', 1)[0]
        return hot_chain.get(cid, 'hot-chain-id-' + cid), 'id'
    if asset.startswith('1cs_v1:'):
        return asset.split(':')[1], 'id'
    if asset.startswith('nep141:') and b.endswith('.near') or b in ('token.sweat',):
        return 'near', 'id'
    return 'unknown', 'id'


def family_of(asset, sdk):
    """STAGE2 rules 1-7, by the form of the ID."""
    b = bare(asset)
    if asset.startswith('nep141:') and b.endswith('.omft.near'):
        return 'POA, SDK-listed as moved to Omni' if b in sdk else 'POA'          # rules 2, 1
    if asset.startswith('nep141:') and b.endswith('.omdep.near'):
        return 'Omni'                                                               # rule 3
    if asset.startswith(HOT_PREFIX):
        return 'HOT'                                                                # rule 4
    if asset == '1cs_v1:btc:native:coin':
        return 'Omni'                                                               # rule 5
    if asset.startswith('1cs_v1:') and asset.split(':')[1] != 'near':
        return 'unclassified'                                                       # rule 6
    return 'a token on NEAR'                                                        # rule 7
# ---- end of copied rule functions ----


def category(asset, marked, sdk, chain, hot_chain):
    """(category, chain, how the chain was found) for one side of a cell."""
    c, how = chain_of(asset, chain, hot_chain)
    if not marked:
        return 'inside', c, how
    if c == 'near':
        return 'near', c, how
    return FAMILY_CAT[family_of(asset, sdk)], c, how


def dstr(x):
    return format(x, 'f')


def share(num, den):
    if not den:
        return None
    with localcontext() as ctx:
        ctx.prec = 30
        return dstr(num / den)


def main(blocks_p, assets_p, sdk_p, out_p):
    assert sha(sdk_p) == SDK_SHA, 'SDK list hash differs from STAGE2.md'
    sdk = load_sdk_list(sdk_p)
    chain, hot_chain = load_assets(assets_p)
    PREFIX_CHAIN.update(prefix_map(chain))
    translated = {p: c for p, c in PREFIX_CHAIN.items() if p != c}

    side_cat = {s: defaultdict(Decimal) for s in ('wd', 'dep')}
    side_rows = {s: defaultdict(int) for s in ('wd', 'dep')}
    side_chain = {s: defaultdict(lambda: defaultdict(Decimal)) for s in ('wd', 'dep')}
    id_seen = {}
    tot = {'in_90': ZERO, 'out_90': ZERO, 'in_60_89': ZERO, 'out_60_89': ZERO}
    rows = rows_no_in = rows_no_out = rows_60_89 = 0
    pages = 0
    checks = {'blocks': [], 'bad_bounds': [], 'rows_key_mismatch': [], 'dropped': 0, 'duplicates': 0}
    seen = set()
    for ln, line in enumerate(open(blocks_p), 1):
        o = json.loads(line)
        b = o['block']
        assert isinstance(b, int) and 0 <= b < NBLOCKS and b not in seen, ('block', ln, b)
        seen.add(b)
        a = T_START + dt.timedelta(days=b)
        want = (a.strftime('%Y-%m-%dT%H:%M:%S.000Z'), (a + dt.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S.000Z'))
        if (o['start'], o['end']) != want:
            checks['bad_bounds'].append([b, o['start'], o['end'], list(want)])
        checks['dropped'] += o['dropped_outside']
        checks['duplicates'] += o['duplicates']
        pages += o['pages']
        nb = 0
        for c in o['cells']:
            assert len(c) == 9, ('cell shape', ln)
            oa, da, dtype, rtype, n, sin, sout, nin, nout = c
            assert isinstance(sin, str) and isinstance(sout, str), ('amounts must be decimal strings', ln)
            sin, sout = Decimal(sin), Decimal(sout)
            assert n >= 1 and 0 <= nin <= n and 0 <= nout <= n, ('cell counts', ln)
            nb += n
            rows += n; rows_no_in += nin; rows_no_out += nout
            tot['in_90'] += sin; tot['out_90'] += sout
            if b in LAST30:
                tot['in_60_89'] += sin; tot['out_60_89'] += sout; rows_60_89 += n
            for s, asset, marked, amt in (('wd', da, rtype == 'DESTINATION_CHAIN', sout),
                                          ('dep', oa, dtype == 'ORIGIN_CHAIN', sin)):
                k, ch, how = category(asset, marked, sdk, chain, hot_chain)
                side_cat[s][k] += amt
                side_rows[s][k] += n
                if k in BRIDGED or k == 'other_form_on_non_near_chain':
                    side_chain[s][ch][k] += amt
                if marked:
                    id_seen[asset] = (k, ch, how)
        if nb != o['rows']:
            checks['rows_key_mismatch'].append([b, o['rows'], nb])
    checks['blocks'] = [len(seen), sorted(seen) == list(range(NBLOCKS))]

    def side_block(s, with_groups):
        cats = {k: dstr(side_cat[s][k]) for k in CATS}
        bridged = sum((side_cat[s][k] for k in BRIDGED), ZERO)
        def shares(get, den):
            return {'omni': share(get('omni'), den),
                    'omni+sdk': share(get('omni') + get('sdk'), den),
                    'omni+sdk+unclassified': share(get('omni') + get('sdk') + get('unclassified'), den),
                    'sdk': share(get('sdk'), den),
                    'poa': share(get('poa'), den), 'hot': share(get('hot'), den),
                    'unclassified': share(get('unclassified'), den)}
        r = {'usd_by_category': cats,
             'rows_by_category': {k: side_rows[s][k] for k in CATS},
             'bridged_usd': dstr(bridged),
             'shares_of_bridged': shares(lambda k: side_cat[s][k], bridged)}
        byc = {ch: {k: dstr(v) for k, v in sorted(d.items())} for ch, d in
               sorted(side_chain[s].items(), key=lambda kv: -sum(kv[1].values()))}
        r['bridged_usd_by_chain'] = byc
        if with_groups:
            for g, member in (('sampled8', lambda ch: ch in SAMPLED8), ('other_chains', lambda ch: ch not in SAMPLED8)):
                chs = [ch for ch in side_chain[s] if member(ch)]
                gsum = defaultdict(Decimal)
                for ch in chs:
                    for k, v in side_chain[s][ch].items():
                        gsum[k] += v
                gb = sum((gsum[k] for k in BRIDGED), ZERO)
                with_value = sorted(ch for ch in chs if sum((side_chain[s][ch][k] for k in BRIDGED), ZERO) > 0)
                r[g] = {'bridged_usd': dstr(gb),
                        'usd_by_category': {k: dstr(gsum[k]) for k in BRIDGED},
                        'shares_of_group': shares(lambda k: gsum[k], gb),
                        'share_of_all_bridged': share(gb, bridged),
                        'chains_with_value_count': len(with_value),
                        'chains_with_value': with_value}
        return r

    out = {
        'source': {'blocks_jsonl_sha256': sha(blocks_p), 'assets_json_sha256': sha(assets_p),
                   'sdk_list_sha256': sha(sdk_p), 'lines': len(seen), 'pages': pages},
        'checks': checks,
        'prefixes_translated_by_the_list': translated,
        'withdrawals': side_block('wd', True),
        'deposits': side_block('dep', True),
        'totals': {'amountInUsd_90d': dstr(tot['in_90']), 'amountInUsd_blocks_60_89': dstr(tot['in_60_89']),
                   'amountOutUsd_90d': dstr(tot['out_90']), 'amountOutUsd_blocks_60_89': dstr(tot['out_60_89']),
                   'rows': rows, 'rows_blocks_60_89': rows_60_89,
                   'rows_no_amountInUsd': rows_no_in, 'rows_no_amountOutUsd': rows_no_out},
        'ids_on_marked_sides': {a: list(v) for a, v in sorted(id_seen.items())},
        'readings': [
            'Withdrawal category of a cell: recipientType not DESTINATION_CHAIN -> inside; else the destination '
            "asset's chain (assets.json, else from the ID) is near -> near; else its STAGE2 family.",
            'Deposit category: the same with depositType ORIGIN_CHAIN and the origin asset.',
            'Bridged = omni+sdk+poa+hot+unclassified. A rule-7 form whose chain is not near would go to '
            'other_form_on_non_near_chain, outside bridged; its value is reported beside the categories.',
            'Census: all 90 blocks read, so no scaling and no bootstrap (PLAN section 6). Shares at 30 '
            'significant digits; sums exact.',
            'Chains named by the token list codes; a chain group counts a chain once it has bridged value above zero.',
            "An ID missing from the list takes its chain from its prefix, translated by the list's own convention "
            "where the list is consistent (bnb -> bsc: the list files every nep141:bnb-...omdep.near it holds under "
            "'bsc'). Read literally, the prefix would add 'bnb' as a 31st chain name for the same chain."],
    }
    json.dump(out, open(out_p, 'w'), indent=1)
    for s in ('withdrawals', 'deposits'):
        r = out[s]
        print(s, 'bridged', r['bridged_usd'])
        for k, v in r['usd_by_category'].items():
            print('   %-30s %s' % (k, v))
        for k, v in r['shares_of_bridged'].items():
            print('   share %-24s %s' % (k, v))
    print('checks', json.dumps(checks)[:300])
    print('totals', json.dumps(out['totals']))


if __name__ == '__main__':
    main(*sys.argv[1:5])
