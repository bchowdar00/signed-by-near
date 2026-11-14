import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze, build
from collections import defaultdict

TOK = build.load_tokens()
wins = analyze.load_flow_windows()
disp = {'bitcoin': 'Bitcoin', 'zcash': 'Zcash', 'solana': 'Solana', 'ethereum': 'Ethereum',
        'arbitrum': 'Arbitrum', 'base': 'Base', 'tron': 'Tron', 'xrp': 'XRP'}
chain_of = {c: disp[m['chain']] for c, m in TOK.items()}
group_of = {c: m['unit_group'] for c, m in TOK.items()}

# chain -> tokens, chain -> {group: tokens}
chain_tokens = defaultdict(list)
chain_groups = defaultdict(lambda: defaultdict(list))
for c, m in TOK.items():
    chain_tokens[chain_of[c]].append(c)
    chain_groups[chain_of[c]][group_of[c]].append(c)

CHAINS = ['Bitcoin', 'Zcash', 'Solana', 'Ethereum', 'Arbitrum', 'Base', 'Tron', 'XRP']

def hull_share(subwins, valfn):
    pL, nL, dL = analyze.point_share(subwins, valfn, lambda t: True, analyze.olo)
    if dL is None or dL <= 0:
        return None
    distinct = len(set((t['tx'], t['token']) for w in subwins for t in w['transfers']))
    nwin_any = sum(1 for w in subwins if any(valfn(t) > 0 for t in w['transfers']))
    b1 = analyze.bootstrap_share(subwins, valfn, lambda t: True, analyze.olo, 1)
    b2 = analyze.bootstrap_share(subwins, valfn, lambda t: True, analyze.olo, 2)
    b1U = analyze.bootstrap_share(subwins, valfn, lambda t: True, analyze.ohi, 1)
    b2U = analyze.bootstrap_share(subwins, valfn, lambda t: True, analyze.ohi, 2)
    wlL, _, _ = analyze.window_level_bound(subwins, valfn, lambda t: True, analyze.olo)
    _, wlU, _ = analyze.window_level_bound(subwins, valfn, lambda t: True, analyze.ohi)
    L = min(x for x in [b1[0], b2[0], wlL] if x is not None)
    U = max(x for x in [b1U[1], b2U[1], wlU] if x is not None)
    drop = max(b1[2], b2[2]) / 2000.0
    sparse = distinct < 10 or nwin_any < 3
    unstable = drop > 0.05
    return {'pt': pL, 'L': L, 'U': U, 'distinct': distinct, 'nwin_any': nwin_any,
            'sparse': sparse, 'unstable': unstable}

results = {}
for ch in CHAINS:
    cw = [w for w in wins if chain_of[w['token']] == ch]
    count = hull_share(cw, lambda t: 1.0)  # count share pooled across chain tokens
    groups = {}
    for g, toks in chain_groups[ch].items():
        gw = [w for w in cw if w['token'] in toks]
        groups[g] = hull_share(gw, analyze.native)
    results[ch] = {'count': count, 'groups': groups}

def decide(ch, r):
    cnt = r['count']
    grps = r['groups']
    if cnt is None or all(g is None for g in grps.values()):
        return 'unknown', 'no measured value'
    # sparsity/instability on count or any group -> unknown
    if cnt['sparse'] or cnt['unstable']:
        return 'unknown', f"count sparse/unstable (distinct={cnt['distinct']})"
    for g, gr in grps.items():
        if gr is None or gr['sparse'] or gr['unstable']:
            return 'unknown', f'group {g} sparse/unstable/none'
    yes = cnt['L'] > 0.5 and all(grps[g]['L'] > 0.5 for g in grps)
    no = cnt['U'] < 0.5 and all(grps[g]['U'] < 0.5 for g in grps)
    if yes:
        return 'yes', 'count L>50% and every group amount L>50%'
    if no:
        return 'no', 'count U<50% and every group amount U<50%'
    return 'unknown', 'straddles 50%'

print(f"{'chain':9} {'cnt[L,U]':>20} {'groups (amount [L,U])':>40}  verdict")
dom = {}
for ch in CHAINS:
    r = results[ch]
    v, why = decide(ch, r)
    dom[ch] = v
    cnt = r['count']
    cs = f"[{cnt['L']:.3f},{cnt['U']:.3f}]" if cnt else 'None'
    gs = '  '.join(f"{g}:[{gr['L']:.3f},{gr['U']:.3f}]" if gr else f"{g}:None" for g, gr in r['groups'].items())
    print(f"{ch:9} {cs:>20} {gs:>40}  {v}  ({why})")

n_dom_yes = sum(1 for v in dom.values() if v == 'yes')
print(f"\ndominant yes: {n_dom_yes}")
# dominant yes-or-unknown over all 28: chains without measured tokens are unknown
# the 28 minus these 8 measured are all unknown
n28 = 28
dom_yes_or_unknown = n28 - sum(1 for v in dom.values() if v == 'no')
print(f"dominant yes-or-unknown (over 28): {dom_yes_or_unknown}")

out = {}
for ch in CHAINS:
    r = results[ch]
    out[ch] = {'verdict': dom[ch],
               'count': r['count'],
               'groups': r['groups']}
json.dump({'chains': out, 'dominant_yes': n_dom_yes, 'dominant_yes_or_unknown_28': dom_yes_or_unknown},
          open('m1_dominant.json', 'w'), indent=1)
print('wrote m1_dominant.json')
