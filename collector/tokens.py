"""Token list (METHOD §6.4) with chain, unit group and decimals read from `ft_metadata`.

  make <out tokens.json> <raw dir>

The list is fixed here. Decimals and symbols come from each contract's own `ft_metadata` view at
the latest final block (keyless FastNEAR RPC); the raw responses are kept in <raw dir>.
Amounts are summed only within a unit group (METHOD §4, M1).
"""
import base64, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc  # noqa: E402

# (contract id, chain, unit group, route family of the contract)
TOKENS = [
    ('nbtc.bridge.near', 'bitcoin', 'BTC', 'omni'),
    ('btc.omft.near', 'bitcoin', 'BTC', 'omft'),
    ('zec.omft.near', 'zcash', 'ZEC', 'omft'),
    ('nzec.bridge.near', 'zcash', 'ZEC', 'omni'),
    ('sol.omft.near', 'solana', 'SOL', 'omft'),
    ('sol-5ce3bf3a31af18be40ba30f721101b4341690186.omft.near', 'solana', 'USD', 'omft'),
    ('sol-c800a4bd850783ccb82c2b2c7e84175443606352.omft.near', 'solana', 'USD', 'omft'),
    ('eth.omft.near', 'ethereum', 'ETH', 'omft'),
    ('eth-0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48.omft.near', 'ethereum', 'USD', 'omft'),
    ('eth-0xdac17f958d2ee523a2206206994597c13d831ec7.omft.near', 'ethereum', 'USD', 'omft'),
    ('arb-0xaf88d065e77c8cc2239327c5edb3a432268e5831.omft.near', 'arbitrum', 'USD', 'omft'),
    ('arb-0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9.omft.near', 'arbitrum', 'USD', 'omft'),
    ('base-0x833589fcd6edb6e08f4c7c32d4f71b54bda02913.omft.near', 'base', 'USD', 'omft'),
    ('tron-d28a265909efecdcee7c5028585214ea0b96f015.omft.near', 'tron', 'USD', 'omft'),
    ('xrp.omft.near', 'xrp', 'XRP', 'omft'),
]


def make(out, raw_dir):
    os.makedirs(raw_dir, exist_ok=True)
    st = rpc.call('block', {'finality': 'final'})
    h = st['result']['header']['height']
    rows = []
    for c, chain, unit, fam in TOKENS:
        r = rpc.view(c, 'ft_metadata', h)
        with open(os.path.join(raw_dir, f'ft_metadata-{c}-{h}.json'), 'w') as f:
            json.dump(r, f)
        md = rpc.decode(r) if r else None
        if not md or 'decimals' not in md:
            raise SystemExit(f'no ft_metadata for {c}: {r}')
        rows.append({'contract': c, 'chain': chain, 'unit_group': unit, 'contract_family': fam,
                     'symbol': md.get('symbol'), 'name': md.get('name'), 'decimals': md['decimals'],
                     'metadata_height': h})
        print(c, md.get('symbol'), md['decimals'], flush=True)
    with open(out, 'w') as f:
        json.dump({'source': 'ft_metadata view, FastNEAR archival RPC, keyless', 'height': h,
                   'tokens': rows}, f, indent=1)


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'make':
        make(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
