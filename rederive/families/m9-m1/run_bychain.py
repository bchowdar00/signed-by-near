import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze, build

REF = json.load(open(os.path.join(build.REPO, 'inputs/reference.json')))
V = REF['V_usd']; V_ch = REF['V_ch']
CHNAME = REF['chain_names']  # tokenchain -> [display, nearstats]
TOK = build.load_tokens()
wins = analyze.load_flow_windows()

# tokens per chain (from tokens.json 'chain')
chain_tokens = {}
for c, m in TOK.items():
    chain_tokens.setdefault(m['chain'], []).append(c)

# the 8 chains in the brief order
CHAINS = ['bitcoin', 'zcash', 'solana', 'ethereum', 'arbitrum', 'base', 'tron', 'xrp']

def chain_share(chain):
    toks = set(chain_tokens[chain])
    cw = [w for w in wins if w['token'] in toks]
    pL, nL, dL = analyze.point_share(cw, analyze.usd, lambda t: True, analyze.olo)
    pU, nU, dU = analyze.point_share(cw, analyze.usd, lambda t: True, analyze.ohi)
    ntr = sum(len(w['transfers']) for w in cw)
    distinct = len(set((t['tx'], t['token']) for w in cw for t in w['transfers']))
    if dL is None or dL <= 0 or distinct == 0:
        return {'measured': False, 'reason': 'none observed (0 of 0)', 'ntr': ntr, 'distinct': distinct,
                'pL': None, 'pU': None, 'denom_usd': dL}
    b1 = analyze.bootstrap_share(cw, analyze.usd, lambda t: True, analyze.olo, 1)
    b2 = analyze.bootstrap_share(cw, analyze.usd, lambda t: True, analyze.olo, 2)
    b1U = analyze.bootstrap_share(cw, analyze.usd, lambda t: True, analyze.ohi, 1)
    b2U = analyze.bootstrap_share(cw, analyze.usd, lambda t: True, analyze.ohi, 2)
    wlL, _, _ = analyze.window_level_bound(cw, analyze.usd, lambda t: True, analyze.olo)
    _, wlU, _ = analyze.window_level_bound(cw, analyze.usd, lambda t: True, analyze.ohi)
    L = min(x for x in [b1[0], b2[0], wlL] if x is not None)
    U = max(x for x in [b1U[1], b2U[1], wlU] if x is not None)
    too_sparse = distinct < 10
    return {'measured': not too_sparse, 'reason': 'too sparse' if too_sparse else 'measured',
            'ntr': ntr, 'distinct': distinct, 'pL': pL, 'pU': pU, 'hullL': L, 'hullU': U,
            'denom_usd': dL}

rows = {}
print(f"{'chain':9} {'V_ch':>16} {'p_pt':>8} {'p[L]':>8} {'p[U]':>8}  inM  distinct")
sumV = {'L': 0.0, 'U': 0.0}
num = {'L': 0.0, 'U': 0.0}
cV = 0.0
for ch in CHAINS:
    nm = CHNAME[ch][1]
    vch = V_ch[nm]
    r = chain_share(ch)
    rows[ch] = {'V_ch': vch, 'nearstats_name': nm, **r}
    inM = r['measured']
    pL = r.get('hullL'); pU = r.get('hullU')
    print(f"{ch:9} {vch:16,.0f} {('%.4f'%r['pL']) if r['pL'] is not None else 'None':>8} "
          f"{('%.4f'%pL) if pL is not None else 'None':>8} {('%.4f'%pU) if pU is not None else 'None':>8}  "
          f"{str(inM):5} {r['distinct']}")
    if inM:
        sumV['L'] += vch; sumV['U'] += vch
        num['L'] += vch * pL; num['U'] += vch * pU
        cV += vch

p_L = num['L'] / sumV['L']; p_U = num['U'] / sumV['U']
c = cV / V
S_L = p_L * c
S_U = p_U * c + (1 - c)
print(f'\nM = {[ch for ch in CHAINS if rows[ch]["measured"]]}')
print(f'Sigma_M V_ch = {cV:,.2f}')
print(f'p_L = {p_L:.6f}  p_U = {p_U:.6f}')
print(f'c = Sigma_M V_ch / V = {c:.6f}')
print(f'S_L = p_L*c = {S_L:.6f}')
print(f'S_U = p_U*c + (1-c) = {S_U:.6f}')
json.dump({'rows': rows, 'p_L': p_L, 'p_U': p_U, 'c': c, 'S_L': S_L, 'S_U': S_U,
           'sum_M_Vch': cV, 'M': [ch for ch in CHAINS if rows[ch]['measured']]},
          open('bychain.json', 'w'), indent=1)
print('wrote bychain.json')
