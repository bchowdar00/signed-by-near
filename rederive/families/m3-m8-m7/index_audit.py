"""Signature index (M6 descriptive) and destination-audit cross-check. python3 -I."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collections import defaultdict, Counter

BC = os.environ["RD_DATA"]
PAGES = os.path.join(BC, "nb", "pages")

def load_completed():
    comp = set()
    with open(os.path.join(BC, "nb", "windows.jsonl")) as f:
        for L in f:
            o = json.loads(L)
            if o.get("event") == "completed":
                comp.add(o["id"])
    return comp

def read_pages(wid):
    dpath = os.path.join(PAGES, wid)
    if not os.path.isdir(dpath):
        return None
    out = [json.load(open(os.path.join(dpath, fn))) for fn in os.listdir(dpath) if fn.endswith(".json")]
    out.sort(key=lambda p: (p["seg"], p["page"]))
    return out

def chain_ok(pages):
    if not pages:
        return False
    if any(p["http"] != 200 for p in pages):
        return False
    byseg = defaultdict(list)
    for p in pages:
        byseg[p["seg"]].append(p)
    for seg, ps in byseg.items():
        ps.sort(key=lambda p: p["page"])
        if [p["page"] for p in ps] != list(range(len(ps))):
            return False
        if not ps[-1]["done"]:
            return False
    return True

def build_index():
    comp = load_completed()
    d = json.load(open(os.path.join(os.environ["RD_REPO"], "frozen", "instants.json")))
    idx = [x for x in d["windows"] if x["family"] == "index"]
    per_month = {}
    eligible_btc = []  # BITCOIN with account_id endswith .bridge.near
    eligible_zec = []  # ZCASH
    for w in sorted(idx, key=lambda z: z["key"]):
        mo = w["month"]
        pages = read_pages(w["id"])
        completed = (w["id"] in comp) and chain_ok(pages)
        chains = Counter()
        rows = []
        if pages:
            seen = set()
            for p in pages:
                for r in p.get("rows", []):
                    rid = r["receipt_id"]
                    if rid in seen:
                        continue
                    seen.add(rid)
                    rows.append(r)
                    chains[r["dest_chain"]] += 1
        per_month[mo] = {"completed": completed, "n_rows": len(rows), "chains": dict(chains)}
        for r in rows:
            if r["dest_chain"] == "BITCOIN" and r["account_id"].endswith(".bridge.near"):
                eligible_btc.append({"month": mo, **{k: r[k] for k in
                    ("account_id", "dest_address", "dest_txn", "receipt_id", "transaction_hash")}})
            if r["dest_chain"] == "ZCASH":
                eligible_zec.append({"month": mo, **{k: r[k] for k in
                    ("account_id", "dest_address", "dest_txn", "receipt_id", "transaction_hash")}})
    return per_month, eligible_btc, eligible_zec

if __name__ == "__main__":
    pm, ebtc, ezec = build_index()
    out = {"per_month": pm, "eligible_btc_n": len(ebtc), "eligible_zec_n": len(ezec),
           "eligible_btc": ebtc, "eligible_zec": ezec}
    json.dump(out, open("index_results.json", "w"), indent=1)
    notc = [m for m, v in pm.items() if not v["completed"]]
    print("INDEX months not completed:", notc)
    for m in sorted(pm):
        v = pm[m]
        print(m, "completed" if v["completed"] else "NOT-COMPLETED", "rows", v["n_rows"], v["chains"])
    print("eligible BITCOIN(.bridge.near):", len(ebtc), " eligible ZCASH:", len(ezec))
