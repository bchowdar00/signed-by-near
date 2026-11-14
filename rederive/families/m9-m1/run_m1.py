import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze, build, statlib
from collections import defaultdict, Counter

REF = json.load(open(os.path.join(build.REPO, 'inputs/reference.json')))
TOK = build.load_tokens()
INST = build.load_instants()
COMP = build.completed_ids()
INTENTS = 'intents.near'

# ---------- the 28 chains ----------
ch28 = REF['chains28']
union = ch28['union']
calc_union = sorted(set(ch28['omni']) | set(ch28['poa']) | set(ch28['hot']))
assert sorted(union) == calc_union, (len(union), len(calc_union))
print('28 chains union size:', len(union), '== computed', len(calc_union), '->', len(union) == 28)

# ---------- census token mapping (DEVIATIONS 15) ----------
cex = REF['census_exact']; cpre = REF['census_prefix']; csuf = REF['census_suffix']

def map_token_chain(contract):
    if contract in cex:
        return cex[contract]
    for suf, chn in csuf.items():
        if contract.endswith(suf):
            return chn
    # prefix: token like '<prefix>.omft.near' or '<prefix>-<addr>.omft.near' (also .omdep.near)
    base = contract
    for tail in ('.omft.near', '.omdep.near'):
        if base.endswith(tail):
            base = base[:-len(tail)]
            break
    pre = base.split('-')[0].split('.')[0]
    return cpre.get(pre)

# ---------- census windows ----------
census = [w for w in INST['windows'] if w['family'] == 'census']
rows_total = 0
rows_not_intents = 0
tokens_seen = Counter()
token_chain = {}
E = 0.0
for w in census:
    ok, why = build.check_completion(w, COMP)
    assert ok, (w['id'], why)
    E += w['covered_s']
    pages = build.load_pages(w['id'])
    # dedup within window by row identity
    seen = set()
    for p in pages:
        for r in p['rows']:
            key = (r['receipt_id'], r['event_index'], r['affected_account_id'], r['cause'])
            if key in seen:
                continue
            seen.add(key)
            rows_total += 1
            aff = r['affected_account_id']; inv = r['involved_account_id']
            if aff != INTENTS and inv != INTENTS:
                rows_not_intents += 1
            c = r['contract_account_id']
            tokens_seen[c] += 1
            token_chain[c] = map_token_chain(c)

unmapped = [t for t in tokens_seen if token_chain[t] is None]
census_chains = set(v for v in token_chain.values() if v)
det_limit = 3.0 / E  # per the exposure E (seconds); 3/E per day requires E in days
E_days = E / 86400.0
det_limit_per_day = 3.0 / E_days
print(f'\ncensus windows: {len(census)}  rows(dedup within window): {rows_total}  rows without intents.near: {rows_not_intents}')
print(f'distinct token contracts seen: {len(tokens_seen)}  unmapped: {unmapped}')
print(f'census chains: {sorted(census_chains)}')
print(f'E = sum covered_s = {E:,.2f} s = {E_days:.4f} days ; detection limit 3/E = {det_limit_per_day:.6f} per day')

# ---------- observed use (flow omni transfers + census) ----------
wins = analyze.load_flow_windows()
# chain -> has omni-route flow transfer?
flow_omni_chains = set()
chain_of_token = {c: m['chain'] for c, m in TOK.items()}
# map token chain name (tokens.json lowercase) to display name used in 28 list
# tokens.json chains: bitcoin,zcash,solana,ethereum,arbitrum,base,tron,xrp
disp = {'bitcoin': 'Bitcoin', 'zcash': 'Zcash', 'solana': 'Solana', 'ethereum': 'Ethereum',
        'arbitrum': 'Arbitrum', 'base': 'Base', 'tron': 'Tron', 'xrp': 'XRP'}
for w in wins:
    for t in w['transfers']:
        if t['route'] == 'omni':
            flow_omni_chains.add(disp[chain_of_token[w['token']]])
observed_chains = set(flow_omni_chains) | set(census_chains)
# note: census uses 'Tron' spelling? census_prefix tron->'Tron'; 28-list uses 'Tron'
print(f'\nflow omni-route chains: {sorted(flow_omni_chains)}')
print(f'observed (flow OR census): {sorted(observed_chains)}')

observed = {}
for ch in union:
    observed[ch] = 'yes' if ch in observed_chains else 'unknown'
n_obs_yes = sum(1 for v in observed.values() if v == 'yes')
print(f'observed yes: {n_obs_yes} / 28 ; yes-or-unknown: 28')

# ---------- chains with measured tokens ----------
# measured token = one of the 15 flow tokens with >=1 cross-chain transfer in flow windows
measured_by_chain = defaultdict(int)
distinct_by_chain = defaultdict(set)
for w in wins:
    ch = disp[chain_of_token[w['token']]]
    for t in w['transfers']:
        measured_by_chain[ch] += 1
        distinct_by_chain[ch].add((t['tx'], t['token']))
chains_with_measured = sorted(c for c in measured_by_chain if measured_by_chain[c] > 0)
print(f'\nchains with >=1 measured cross-chain transfer: {chains_with_measured} ({len(chains_with_measured)})')

json.dump({'union28': union, 'census_rows': rows_total, 'census_rows_not_intents': rows_not_intents,
           'census_tokens': dict(tokens_seen), 'census_token_chain': token_chain, 'unmapped': unmapped,
           'E_s': E, 'E_days': E_days, 'det_limit_per_day': det_limit_per_day,
           'observed': observed, 'observed_yes': n_obs_yes,
           'flow_omni_chains': sorted(flow_omni_chains), 'census_chains': sorted(census_chains),
           'chains_with_measured': chains_with_measured},
          open('m1_census.json', 'w'), indent=1)
print('wrote m1_census.json')
