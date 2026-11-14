"""Read sign windows, check completion, count receipts in [s,e). python3 -I."""
import json, os
from collections import defaultdict, Counter

BC = os.environ["RD_DATA"]
INSTANTS = os.path.join(os.environ["RD_REPO"], "frozen", "instants.json")
PAGES = os.path.join(BC, "nb", "pages")
WINDOWS = os.path.join(BC, "nb", "windows.jsonl")

def load_completed_ids():
    comp = set()
    with open(WINDOWS) as f:
        for L in f:
            L = L.strip()
            if not L:
                continue
            o = json.loads(L)
            if o.get("event") == "completed":
                comp.add(o["id"])
    return comp

def load_sign_windows():
    d = json.load(open(INSTANTS))
    return [x for x in d["windows"] if x["family"] == "sign"]

def read_pages(wid):
    """Return list of page dicts for a window, ordered by (seg,page)."""
    dpath = os.path.join(PAGES, wid)
    if not os.path.isdir(dpath):
        return None
    out = []
    for fn in os.listdir(dpath):
        if not fn.endswith(".json"):
            continue
        out.append(json.load(open(os.path.join(dpath, fn))))
    out.sort(key=lambda p: (p["seg"], p["page"]))
    return out

def page_chain_ok(pages, nseg):
    """Gapless chain per segment, last page done, all http 200 (DEVIATIONS 17)."""
    if pages is None or not pages:
        return False
    if any(p["http"] != 200 for p in pages):
        return False
    byseg = defaultdict(list)
    for p in pages:
        byseg[p["seg"]].append(p)
    if set(byseg.keys()) != set(range(nseg)):
        return False
    for seg, ps in byseg.items():
        ps.sort(key=lambda p: p["page"])
        nums = [p["page"] for p in ps]
        if nums != list(range(len(ps))):
            return False
        if not ps[-1]["done"]:
            return False
    return True

def window_completed(win, comp_ids, pages):
    return (win["id"] in comp_ids) and page_chain_ok(pages, len(win["segments_ns"]))

def receipts_in_window(win, pages):
    """Distinct receipts whose timestamp lies in any segment [s,e). Dedup by receipt_id.
    Returns (rows list, n_mismatch_ts) where rows have receipt_id,status,deposit,ts_inc,ts_blk,predecessor."""
    segs = win["segments_ns"]
    seen = {}
    mismatch = 0
    for p in pages:
        for r in p.get("rows", []):
            ts_inc = int(r["included_in_block_timestamp"])
            ts_blk = int(r["block"]["block_timestamp"])
            if ts_inc != ts_blk:
                mismatch += 1
            # placement uses included_in_block_timestamp
            inwin = any(s <= ts_inc < e for s, e in segs)
            if not inwin:
                continue
            rid = r["receipt_id"]
            if rid in seen:
                continue
            status = r.get("outcome", {}).get("status", None)
            dep = r.get("actions_agg", {}).get("deposit", None)
            seen[rid] = {
                "receipt_id": rid,
                "status": status,
                "deposit": dep,
                "ts_inc": ts_inc,
                "ts_blk": ts_blk,
                "predecessor": r.get("predecessor_account_id"),
            }
    return list(seen.values()), mismatch

def build():
    comp = load_completed_ids()
    signs = load_sign_windows()
    out = {}
    ts_field_changes = 0  # receipts where ts_inc vs ts_blk changes membership
    for win in signs:
        pages = read_pages(win["id"])
        completed = window_completed(win, comp, pages)
        rows, mism = (([], 0) if pages is None else receipts_in_window(win, pages))
        # check whether ts choice changes window membership for any receipt
        segs = win["segments_ns"]
        if pages:
            for p in pages:
                for r in p.get("rows", []):
                    a = any(s <= int(r["included_in_block_timestamp"]) < e for s, e in segs)
                    b = any(s <= int(r["block"]["block_timestamp"]) < e for s, e in segs)
                    if a != b:
                        ts_field_changes += 1
        out[win["id"]] = {
            "key": win["key"], "stratum": win["stratum"], "month": win["month"],
            "weight": win["weight"], "covered_s": win["covered_s"], "D_s": win["D_s"],
            "completed": completed, "n_pages": (0 if pages is None else len(pages)),
            "rows": rows, "y": len(rows),
            "y_fail": sum(1 for r in rows if r["status"] is not True),
        }
    return out, ts_field_changes

if __name__ == "__main__":
    data, tschanges = build()
    comp_n = sum(1 for v in data.values() if v["completed"])
    print("sign windows", len(data), "completed", comp_n, "ts_field_changes", tschanges)
    json.dump({"ts_field_changes": tschanges, "windows": data},
              open("sign_cache.json", "w"))
    print("wrote sign_cache.json")
