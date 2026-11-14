import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import lib

rows = [json.loads(l) for l in open(os.path.join(lib.DATA, 'rpc', 'supply.jsonl')) if l.strip()]
# group by point
pts = {}
for r in rows:
    p = r['point']
    pts.setdefault(p, {})[r['token']] = r

points = []
for p in sorted(pts, key=lambda x: (x != 'T0', x)):  # keep natural order
    pass
# order: month points then T0; just sort with T0 last
order = sorted([p for p in pts if p != 'T0']) + (['T0'] if 'T0' in pts else [])

anomalies = []
for p in order:
    d = pts[p]
    nb = d.get('nbtc.bridge.near')
    bo = d.get('btc.omft.near')
    def supply(x):
        if x is None:
            return 0, 'missing-row'
        if x['status'] == 'absent' or x['total_supply'] is None:
            return 0, 'absent'  # counts as 0
        if x['status'] == 'value':
            return int(x['total_supply']), 'value'
        return None, x['status']
    nb_raw, nb_st = supply(nb)
    bo_raw, bo_st = supply(bo)
    if nb_raw is None or bo_raw is None:
        anomalies.append({'point': p, 'nbtc_status': nb_st, 'btc_status': bo_st})
        share = None
    else:
        nb_btc = nb_raw / 1e8
        bo_btc = bo_raw / 1e8
        tot = nb_btc + bo_btc
        share = (nb_btc / tot) if tot > 0 else None
    points.append({'point': p, 'nbtc_btc': nb_raw / 1e8 if nb_raw is not None else None,
                   'btc_omft_btc': bo_raw / 1e8 if bo_raw is not None else None,
                   'nbtc_status': nb_st, 'btc_status': bo_st, 'omni_share': share})

shares = [(pt['point'], pt['omni_share']) for pt in points if pt['omni_share'] is not None]
mn = min(shares, key=lambda x: x[1])
mx = max(shares, key=lambda x: x[1])
t0 = next((pt['omni_share'] for pt in points if pt['point'] == 'T0'), None)

out = {'points': points, 'min_share': {'point': mn[0], 'value': mn[1]},
       'max_share': {'point': mx[0], 'value': mx[1]}, 't0_share': t0, 'anomalies': anomalies}
json.dump(out, open('d5_m10b.json', 'w'), indent=1)

for pt in points:
    s = pt['omni_share']
    print(f"{pt['point']:8} nbtc={pt['nbtc_btc']:.8f}({pt['nbtc_status']}) btc.omft={pt['btc_omft_btc']:.8f}({pt['btc_status']}) "
          f"Omni_share={'None' if s is None else f'{s*100:.4f}%'}")
print(f"MIN share: {mn[1]*100:.4f}% at {mn[0]}")
print(f"MAX share: {mx[1]*100:.4f}% at {mx[0]}")
print(f"T0 share: {t0*100:.4f}%" if t0 is not None else "T0 share: None")
print("anomalies:", anomalies)
