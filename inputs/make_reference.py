"""Builds inputs/reference.json, the fixed reference figures the analysis uses (METHOD §4 M1, M9), by
script from saved sources, so nothing is typed by hand except what METHOD itself states.

  python3 -I inputs/make_reference.py <nearstats-api-near-summary.json> <integration__bridging__overview.md> <out>

From the NearStats summary (saved 2026-11-09, generatedAt 09:21:11Z; CC BY 4.0, a third party, reported):
  V = intents.timeframes.30d.volumeUsd, its swap count and observed window; V_ch from .chainFlows;
  the headline 30-day total intents.totals.volume30dUsd (context only).
From the Intents bridging overview (saved 2026-11-09): the three "Supported chains" lists, whose union is
  the 28 chains C1 names (METHOD §4 M1).
From METHOD (frozen stage 1), as stated there: the 13 chains of NEAR's Omni overview (M1) and the M9
  reference prices.
"""
import datetime, hashlib, json, os, re, sys

CAPABILITY_13 = ['Ethereum', 'Bitcoin', 'Zcash', 'Solana', 'Base', 'BNB', 'Arbitrum', 'Polygon', 'HyperEVM',
                 'Fogo', 'Abstract', 'Starknet', 'Aptos']          # METHOD §4 M1
PRICES_USD = {'BTC': 74500.0, 'ETH': 2100.0, 'SOL': 87.0, 'ZEC': 1200.0, 'XRP': 1.0, 'USD': 1.0}  # METHOD §4 M9
# tokens.json chain ids -> names in the bridging overview and in NearStats' chainFlows
CHAIN_NAMES = {'bitcoin': ('Bitcoin', 'Bitcoin'), 'zcash': ('Zcash', 'Zcash'), 'solana': ('Solana', 'Solana'),
               'ethereum': ('Ethereum', 'Ethereum'), 'arbitrum': ('Arbitrum', 'Arbitrum'), 'base': ('Base', 'Base'),
               'tron': ('Tron', 'TRON'), 'xrp': ('XRP', 'XRP')}
# census tokens -> chain (METHOD §4 M1: "mapped to chains by their contract ids, and unmapped ones are listed").
# POA and Omni deposit tokens are named <prefix>.omft.near / <prefix>-<address>.omft.near (and .omdep.near).
CENSUS_PREFIX = {'eth': 'Ethereum', 'base': 'Base', 'arb': 'Arbitrum', 'bsc': 'BNB', 'bnb': 'BNB', 'sol': 'Solana',
                 'btc': 'Bitcoin', 'zec': 'Zcash', 'xrp': 'XRP', 'tron': 'Tron', 'gnosis': 'Gnosis', 'gno': 'Gnosis',
                 'bera': 'Berachain', 'bch': 'BCH', 'ltc': 'Litecoin', 'doge': 'Dogecoin', 'sui': 'Sui',
                 'aptos': 'Aptos', 'apt': 'Aptos', 'cardano': 'Cardano', 'ada': 'Cardano', 'starknet': 'Starknet',
                 'strk': 'Starknet', 'pol': 'Polygon', 'polygon': 'Polygon', 'op': 'Optimism', 'avax': 'Avalanche',
                 'scroll': 'Scroll', 'monad': 'Monad', 'ton': 'TON', 'stellar': 'Stellar', 'xlm': 'Stellar'}
CENSUS_EXACT = {'nbtc.bridge.near': 'Bitcoin', 'nzec.bridge.near': 'Zcash'}
CENSUS_SUFFIX = {'.factory.bridge.near': 'Ethereum'}   # Rainbow/Omni ERC-20s minted on NEAR by factory.bridge.near


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def main(ns_path, doc_path, out):
    S = json.load(open(ns_path))
    t = S['intents']['timeframes']['30d']
    doc = open(doc_path).read()
    lists = {}
    for sec, key in (('## Omni Bridge', 'omni'), ('## POA Bridge', 'poa'), ('## HOT Bridge', 'hot')):
        body = doc.split(sec, 1)[1]
        m = re.search(r'\*\*Supported chains:\*\*\s*(.+)', body)
        lists[key] = [c.strip() for c in m.group(1).split(',')]
    union = sorted(set(lists['omni']) | set(lists['poa']) | set(lists['hot']))
    assert (len(lists['omni']), len(lists['poa']), len(lists['hot']), len(union)) == (6, 17, 11, 28), lists
    cap_in_28 = [c for c in CAPABILITY_13 if c in union]
    assert len(cap_in_28) == 10, cap_in_28
    ref = {
        'made_utc': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'sources': {'nearstats_summary': {'file': os.path.basename(ns_path), 'sha256': sha(ns_path),
                                          'generatedAt': S['generatedAt']},
                    'bridging_overview': {'file': os.path.basename(doc_path), 'sha256': sha(doc_path)}},
        'V_usd': t['volumeUsd'], 'V_swaps': t['swapCount'], 'V_window': t['observedWindow'],
        'V_headline_usd': S['intents']['totals']['volume30dUsd'],
        'V_ch': {c['chain']: c['volumeUsd'] for c in t['chainFlows']},
        'chains28': {'omni': lists['omni'], 'poa': lists['poa'], 'hot': lists['hot'], 'union': union},
        'capability13': CAPABILITY_13, 'capability_in_28': cap_in_28,
        'prices_usd': PRICES_USD, 'chain_names': CHAIN_NAMES,
        'census_prefix': CENSUS_PREFIX, 'census_exact': CENSUS_EXACT, 'census_suffix': CENSUS_SUFFIX,
    }
    with open(out, 'w') as f:
        json.dump(ref, f, indent=1, sort_keys=True)
    print('wrote', out, 'V', ref['V_usd'], 'chains', len(union), 'V_ch', len(ref['V_ch']))


if __name__ == '__main__':
    main(*sys.argv[1:4])
