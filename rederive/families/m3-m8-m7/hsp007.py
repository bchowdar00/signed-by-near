"""Independent extraction of the HSP-007 ledger from the forum JSON. python3 -I."""
import json, re, html, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SRC = os.path.join(os.environ.get("RD_SOURCES", ""), "gov-hsp007-execution-42147.json")

def tables(c):
    out = []
    for tm in re.findall(r"<table.*?</table>", c, re.S):
        rows = []
        for tr in re.findall(r"<tr.*?</tr>", tm, re.S):
            cells = re.findall(r"<t[dh].*?>(.*?)</t[dh]>", tr, re.S)
            cells = [html.unescape(re.sub("<[^>]+>", "", x)).strip() for x in cells]
            rows.append(cells)
        out.append(rows)
    return out

def num(s):
    return float(s.replace(",", "").replace("NEAR", "").replace("$", "").strip())

# payout execution report tables: (post, table_index, service_month)
PAYOUTS = [
    (7, 5, "2026-03"), (8, 5, "2026-04"), (11, 1, "2026-05"),
    (15, 0, "2026-06"), (15, 1, "2026-06"),
    (18, 0, "2026-07"), (18, 1, "2026-07"),
    (23, 0, "2026-08"), (23, 1, "2026-08"),
    (27, 0, "2026-09"),
]

def extract():
    d = json.load(open(SRC))
    posts = {p["post_number"]: p for p in d["post_stream"]["posts"]}
    ledger = []
    for pn, ti, month in PAYOUTS:
        t = tables(posts[pn]["cooked"])[ti]
        hdr = [h.lower() for h in t[0]]
        # amount column index
        ai = next(i for i, h in enumerate(hdr) if "amount" in h)
        txi = next(i for i, h in enumerate(hdr) if "transaction" in h)
        ni = 0  # operator name
        # network from subtotal label in this table
        network = "mainnet"
        for r in t:
            if r and "testnet" in r[0].lower():
                network = "testnet"
        for r in t[1:]:
            name = r[ni]
            low = name.lower()
            if low.startswith("subtotal") or low.startswith("total") or low.startswith("grand"):
                continue
            if len(r) <= max(ai, txi):
                continue
            amt = num(r[ai])
            txraw = r[txi]
            # status
            if re.search(r"pending", txraw, re.I):
                status = "pending"; tx = None
            elif txraw.strip() in ("-", "—", "–", ""):
                status = "executed"; tx = None
            else:
                status = "executed"
                m = re.search(r"([1-9A-HJ-NP-Za-km-z]{20,})", txraw)
                tx = m.group(1) if m else txraw
            ledger.append({"month": month, "network": network, "node": name,
                           "amount": amt, "status": status, "tx": tx, "post": pn})
    # October proposed (post 26 table 0)
    t = tables(posts[26]["cooked"])[0]
    pay_i = next(i for i, h in enumerate([x.lower() for x in t[0]]) if "payment" in h)
    for r in t[1:]:
        if not r or r[0].lower().startswith("total"):
            continue
        ledger.append({"month": "2026-10", "network": "mainnet", "node": r[0],
                       "amount": num(r[pay_i]), "status": "proposed", "tx": None, "post": 26})
    return ledger

def summarise(ledger):
    from collections import defaultdict
    agg = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0.0, 0])))
    # month -> network -> status -> [sum, count]
    for row in ledger:
        a = agg[row["month"]][row["network"]][row["status"]]
        a[0] += row["amount"]; a[1] += 1
    return agg

if __name__ == "__main__":
    ledger = extract()
    json.dump(ledger, open("hsp007_ledger.json", "w"), indent=1)
    agg = summarise(ledger)
    # executed mainnet 2026-03..2026-09
    months7 = ["2026-%02d" % m for m in range(3, 10)]
    exe_main = 0.0; pend = 0.0; test_exe = 0.0
    print("month   | mainnet exec (n) | mainnet pend (n) | testnet exec (n) | testnet pend (n)")
    for mo in months7 + ["2026-10"]:
        me = agg[mo]["mainnet"].get("executed", [0,0])
        mp = agg[mo]["mainnet"].get("pending", [0,0])
        te = agg[mo]["testnet"].get("executed", [0,0])
        tp = agg[mo]["testnet"].get("pending", [0,0])
        prop = agg[mo]["mainnet"].get("proposed", [0,0])
        print(f"{mo} | {me[0]:>10.2f} ({me[1]}) | {mp[0]:>8.2f} ({mp[1]}) | {te[0]:>8.2f} ({te[1]}) | {tp[0]:>8.2f} ({tp[1]}) | proposed {prop[0]:.2f} ({prop[1]})")
        if mo in months7:
            exe_main += me[0]; pend += mp[0] + tp[0]; test_exe += te[0]
    print()
    print(f"MAINNET executed Mar-Sep: {exe_main:.2f}")
    print(f"TESTNET executed Mar-Sep: {test_exe:.2f}")
    print(f"mainnet+testnet executed Mar-Sep: {exe_main+test_exe:.2f}  (METHOD 338436.08)")
    print(f"pending (main+test) Mar-Sep: {pend:.2f}  (METHOD 8436.40)")
    print(f"executed+pending: {exe_main+test_exe+pend:.2f}  (METHOD 346872.48)")
