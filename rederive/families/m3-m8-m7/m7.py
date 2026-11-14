"""M7 completion in the 2,000-block contiguous neardata run. python3 -I."""
import json, os, sys, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collections import defaultdict

BC = os.environ["RD_DATA"]
PREFIX = "near-mpc-recovery v0.1.0 epsilon derivation:"

def payload_hex(req):
    """canonical payload as lowercase hex."""
    if "payload_v2" in req:
        p = req["payload_v2"]
        v = next(iter(p.values()))  # Ecdsa/Eddsa hex
        return v.lower()
    p = req["payload"]
    if isinstance(p, list):
        return bytes(p).hex()
    if isinstance(p, dict):
        return next(iter(p.values())).lower()
    return str(p).lower()

def req_domain(req):
    if "payload_v2" in req:
        return req["domain_id"]
    # old byte-array + key_version form -> domain 0 (secp256k1)
    return 0

def req_tweak_hex(predecessor, path):
    h = hashlib.sha3_256((PREFIX + predecessor + "," + path).encode()).hexdigest()
    return h

def load_contig():
    blocks = []
    with open(os.path.join(BC, "nd", "blocks.jsonl")) as f:
        for L in f:
            o = json.loads(L)
            if o.get("part") == "contiguous":
                blocks.append(o)
    blocks.sort(key=lambda b: b["height"])
    return blocks

def resp_ok(c):
    s = c.get("status")
    return isinstance(s, dict) and "SuccessValue" in s

def main():
    blocks = load_contig()
    n = len(blocks)
    # 1-based rank; middle = ranks 101..1900
    requests = []   # dict with key, height, ts, rank, call
    responses = []  # succeeded respond calls, all ranks
    all_req_by_key = defaultdict(list)  # includes first-100 for ambiguity
    failed_resp = 0
    for rank, b in enumerate(blocks, start=1):
        for c in b["calls"]:
            if c["method"] == "sign":
                req = c["args"].get("request", c["args"])
                try:
                    ph = payload_hex(req)
                    dom = req_domain(req)
                    tw = req_tweak_hex(c["predecessor"], req["path"])
                except Exception as e:
                    continue
                key = (ph, tw, dom)
                rec = {"key": key, "rank": rank, "height": b["height"], "ts": c["ts_ns"],
                       "predecessor": c["predecessor"], "path": req.get("path"),
                       "receipt_id": c["receipt_id"]}
                all_req_by_key[key].append(rec)
                if 101 <= rank <= 1900:
                    requests.append(rec)
            elif c["method"] == "respond":
                if not resp_ok(c):
                    failed_resp += 1
                    continue
                req = c["args"]["request"]
                ph = next(iter(req["payload"].values())).lower()
                tw = bytes(req["tweak"]).hex()
                dom = req.get("domain_id", 0)
                responses.append({"key": (ph, tw, dom), "rank": rank,
                                  "height": b["height"], "ts": c["ts_ns"]})
    # group responses by key, sorted by rank
    resp_by_key = defaultdict(list)
    for r in responses:
        resp_by_key[r["key"]].append(r)
    for k in resp_by_key:
        resp_by_key[k].sort(key=lambda r: (r["height"], r["ts"]))

    # pairing: for each key, pair the key's requests (sorted) in order with responses at/after
    # We pair across ALL requests of a key (incl first-100) so ordering is consistent, but
    # only evaluate middle requests.
    used = defaultdict(set)  # key -> set of response indices used
    pair_of = {}  # id(request rec) -> response rec
    for key, reqs in all_req_by_key.items():
        reqs_sorted = sorted(reqs, key=lambda r: (r["height"], r["ts"]))
        resps = resp_by_key.get(key, [])
        ri = 0
        for req in reqs_sorted:
            # find earliest unused response with height >= req height
            j = ri
            while j < len(resps) and resps[j]["height"] < req["height"]:
                j += 1
            if j < len(resps):
                pair_of[id(req)] = resps[j]
                # mark used: remove it from pool by advancing a pointer-like deletion
                resps.pop(j)
    # now classify evaluated requests
    evaluated = len(requests)
    matched = 0; censored = 0; ambiguous = 0
    matched_unique = 0; matched_by_order = 0
    delays = []
    matched_by_tweak_alone = 0
    for req in requests:
        key = req["key"]
        group_reqs = all_req_by_key[key]
        has_first100 = any(r["rank"] <= 100 for r in group_reqs)
        is_amb = has_first100
        if is_amb:
            ambiguous += 1
        resp = pair_of.get(id(req))
        if resp is not None:
            matched += 1
            delays.append((resp["ts"] - req["ts"]) / 1e9)
            # unique if group has exactly 1 request total and exactly 1 response total
            nreq = len(group_reqs)
            nresp_total = len([1 for r in responses if r["key"] == key])
            if nreq == 1 and nresp_total == 1:
                matched_unique += 1
                matched_by_tweak_alone += 1
            else:
                matched_by_order += 1
        else:
            censored += 1
    # unmatched responses: responses never paired to any request
    total_resp = len(responses)
    paired_resp = len(pair_of)
    unmatched_resp = total_resp - paired_resp
    import statistics
    res = {
        "blocks": n, "first_height": blocks[0]["height"], "last_height": blocks[-1]["height"],
        "evaluated": evaluated, "matched": matched, "matched_unique": matched_unique,
        "matched_by_order": matched_by_order, "ambiguous": ambiguous, "censored": censored,
        "failed_responses": failed_resp, "total_succeeded_responses": total_resp,
        "unmatched_responses": unmatched_resp,
        "matched_by_tweak_alone": matched_by_tweak_alone,
        "matched_share": matched / evaluated,
        "matched_share_ex_ambiguous": matched / (evaluated - ambiguous) if evaluated - ambiguous else None,
        "median_delay_s": statistics.median(delays) if delays else None,
        "longest_delay_s": max(delays) if delays else None,
    }
    json.dump(res, open("m7_results.json", "w"), indent=1)
    for k, v in res.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()
