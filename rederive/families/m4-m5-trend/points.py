import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compute, load
from collections import defaultdict

sign, comp, detail, windows = compute.build()
nd = load.load_nd_sign_sample()
mc = compute.month_completed(windows)
months = compute.month_list()

print('=== M4 class shares per month (point, FastAuth attributed) ===')
print('month      compl  all_HT     c1     c2(FA)  c3     c4     c4x    c5    | 2a    2c   nFA sweat | main  mainNoSw narrow broad')
for m in months:
    ht = compute.ht_by_pred(windows, m)
    ct, rules = compute.class_totals(ht)
    allht = sum(ct.values())
    n, sweat, s2a, s2c = compute.fastauth_signer_shares(nd, m)
    fa = ct.get('2', 0.0)
    if allht == 0:
        print(f'{m}  no calls'); continue
    def sh(c): return ct.get(c, 0.0) / allht
    c2a = fa * s2a / allht if s2a is not None else None
    c2c = fa * s2c / allht if s2c is not None else None
    narrow = sh('4')
    broad = (allht - ct.get('1', 0) - ct.get('3', 0)) / allht
    if s2a is not None:
        main = (ct.get('4', 0) + ct.get('4x', 0) + fa * s2a) / allht
        mainNoSw = (ct.get('4', 0) + ct.get('4x', 0)) / allht  # 2b empty
        a2s = f'{c2a:.4f}'; c2s = f'{c2c:.4f}'; ms = f'{main:.4f}'; mns = f'{mainNoSw:.4f}'
    else:
        a2s = 'unattr'; c2s = 'unattr'; ms = 'range'; mns = 'range'
    cf = 'OK ' if mc[m] else 'NC '
    print(f'{m}  {cf} {allht:10.1f} {sh("1"):.4f} {sh("2"):.4f} {sh("3"):.4f} {sh("4"):.4f} {sh("4x"):.4f} {sh("5"):.4f} | {a2s} {c2s} {n:3d} {sweat:3d} | {ms} {mns} {narrow:.4f} {broad:.4f}')
