"""Cross-check the author's 20 destination-audit picks against repo/audit/raw/. python3 -I."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

AUD = os.path.join(os.environ["RD_REPO"], "audit")
RAW = os.path.join(AUD, "raw")

def btc_check(row, raw):
    txid_ok = raw.get("txid") == row["dest_txn"]
    vin_addrs = set()
    for v in raw.get("vin", []):
        a = v.get("prevout", {}).get("scriptpubkey_address")
        if a:
            vin_addrs.add(a)
    from_signer = row["dest_address"] in vin_addrs
    confirmed = raw.get("status", {}).get("confirmed", None)
    to_other = sum(o.get("value", 0) for o in raw.get("vout", [])
                   if o.get("scriptpubkey_address") != row["dest_address"])
    amt_ok = (to_other == row.get("to_other_addresses"))
    return txid_ok, from_signer, confirmed, to_other, amt_ok

def zec_check(row, raw):
    data = raw.get("data", {})
    tx = data.get(row["dest_txn"])
    if tx is None:
        return False, False, None, None, False
    txid_ok = tx["transaction"]["hash"] == row["dest_txn"]
    in_addrs = set(i.get("recipient") for i in tx.get("inputs", []))
    from_signer = row["dest_address"] in in_addrs
    confirmed = tx["transaction"].get("block_id") is not None
    to_other = sum(o.get("value", 0) for o in tx.get("outputs", [])
                   if o.get("recipient") != row["dest_address"])
    amt_ok = (to_other == row.get("to_other_addresses"))
    return txid_ok, from_signer, confirmed, to_other, amt_ok

def main():
    da = json.load(open(os.path.join(AUD, "dest-audit.json")))
    idx = json.load(open("index_results.json"))
    elig_btc_rid = {r["receipt_id"] for r in idx["eligible_btc"]}
    elig_zec_rid = {r["receipt_id"] for r in idx["eligible_zec"]}
    per = {"BITCOIN": {"picked": 0, "in_eligible": 0, "found": 0, "confirmed": 0,
                       "from_signer": 0, "amount_ok": 0},
           "ZCASH": {"picked": 0, "in_eligible": 0, "found": 0, "confirmed": 0,
                     "from_signer": 0, "amount_ok": 0}}
    issues = []
    for row in da["rows"]:
        chain = row["chain"]
        per[chain]["picked"] += 1
        elig = elig_btc_rid if chain == "BITCOIN" else elig_zec_rid
        in_elig = row["receipt_id"] in elig
        if in_elig:
            per[chain]["in_eligible"] += 1
        else:
            issues.append(f"{chain} {row['dest_txn'][:12]} receipt {row['receipt_id'][:10]} NOT in my eligible pool")
        fn = os.path.join(RAW, f"{chain.lower()}-{row['dest_txn']}.json")
        if not os.path.exists(fn):
            issues.append(f"{chain} {row['dest_txn'][:12]} raw file missing")
            continue
        raw = json.load(open(fn))
        if chain == "BITCOIN":
            txid_ok, from_signer, confirmed, to_other, amt_ok = btc_check(row, raw)
        else:
            txid_ok, from_signer, confirmed, to_other, amt_ok = zec_check(row, raw)
        if txid_ok:
            per[chain]["found"] += 1
        else:
            issues.append(f"{chain} {row['dest_txn'][:12]} raw txid mismatch")
        if confirmed:
            per[chain]["confirmed"] += 1
        else:
            issues.append(f"{chain} {row['dest_txn'][:12]} not confirmed in raw")
        if from_signer:
            per[chain]["from_signer"] += 1
        else:
            issues.append(f"{chain} {row['dest_txn'][:12]} dest_address not in inputs")
        if amt_ok:
            per[chain]["amount_ok"] += 1
        else:
            issues.append(f"{chain} {row['dest_txn'][:12]} amount {to_other} != claimed {row.get('to_other_addresses')}")
        # cross-check author's own flags
        for f, mine in (("found", txid_ok), ("confirmed", bool(confirmed)), ("from_signer_address", from_signer)):
            if row.get(f) != mine:
                issues.append(f"{chain} {row['dest_txn'][:12]} author's '{f}'={row.get(f)} but I get {mine}")
    out = {"per_chain": per, "issues": issues, "available": da.get("available"),
           "not_completed_months": da.get("not_completed_months")}
    json.dump(out, open("audit_check_results.json", "w"), indent=1)
    print(json.dumps(per, indent=1))
    print("available(author):", da.get("available"), "mine: btc", len(elig_btc_rid), "zec", len(elig_zec_rid))
    print("not_completed(author):", da.get("not_completed_months"))
    print("ISSUES:", len(issues))
    for i in issues:
        print("  -", i)

if __name__ == "__main__":
    main()
