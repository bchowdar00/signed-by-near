#!/usr/bin/env python3
"""Stage 2 of the Explorer read: turn the per-block cells into the figures of explorer/RESULTS.md.

    python3 -I explorer/analyse.py explorer/data/blocks.jsonl explorer/data/assets.json explorer

writes explorer/RESULTS.md and explorer/results.json. With `--check` as a fourth argument it
writes nothing and exits 1 if the two files on disk differ from what it would write.

What it computes is fixed in explorer/PLAN.md (section 6); which token-ID form belongs to which
bridge family is fixed in explorer/STAGE2.md. Both were timestamped before any cell was read.
Standard library only; no network.
"""
import collections
import decimal
import json
import os
import random
import sys

D = decimal.Decimal
N_BLOCKS = 90
SEED = 20261113
BOOT = 10000
LAST30 = range(60, 90)                    # the 30 days to T0
# the 8 chains the keyless sample could read (THESIS.md, section 3)
READ_CHAINS = ("btc", "sol", "zec", "eth", "arb", "base", "tron", "xrp")

# The Intents SDK's list of POA tokens "migrated to Omni Bridge": 17 IDs.
# github.com/defuse-protocol/sdk-monorepo, packages/intents-sdk/src/constants/
# poa-tokens-migrated-to-omni-bridge.ts at commit 930d2816,
# sha256 ed49694cd4641f48041e92b6dfa58bf133918e4cd5fce2f75a505a227fe3eb01.
SDK_LIST = frozenset((
    "sol-57d087fd8c460f612f8701f5499ad8b2eec5ab68.omft.near",
    "sol-c58e6539c2f2e097c251f8edf11f9c03e581f8d4.omft.near",
    "sol-b9c68f94ec8fd160137af8cdfe5e61cd68e2afba.omft.near",
    "sol-bb27241c87aa401cc963c360c175dd7ca7035873.omft.near",
    "sol-c800a4bd850783ccb82c2b2c7e84175443606352.omft.near",
    "sol-91914f13d3b54f8126a2824d71632d4b078d7403.omft.near",
    "sol-5ce3bf3a31af18be40ba30f721101b4341690186.omft.near",
    "sol-df27d7abcc1c656d4ac3b1399bbfbba1994e6d8c.omft.near",
    "sol-1f00bb36e75cfc8e1274c1507cc3054f5b3f3ce1.omft.near",
    "sol-c634d063ceff771aff0c972ec396fd915a6bbd0e.omft.near",
    "sol-d600e625449a4d9380eaf5e3265e54c90d34e260.omft.near",
    "sol.omft.near",
    "aptos.omft.near",
    "aptos-34ee497f210c5a511e8d5b53bc56d75b63612bb5.omft.near",
    "aptos-88cb7619440a914fe6400149a12b443c3ac21d59.omft.near",
    "starknet.omft.near",
    "zec.omft.near",
))

# Family of each token-ID form. The reasons and sources are in explorer/STAGE2.md.
FAMILY_OF_FORM = {
    "omdep": "omni",          # <chain>[-<address>].omdep.near
    "1cs_v1_btc": "omni",     # 1cs_v1:btc:native:coin, which the token list names "BTC(OMNI)"
    "1cs_v1": "unclassified", # any other 1cs_v1:<chain>:<kind>:<address>, chain other than near
    "omft": "poa",            # <chain>[-<address>].omft.near, not on the SDK's list
    "omft_sdk": "sdk",        # .omft.near and on the SDK's list
    "hot": "hot",             # nep245:v2_1.omni.hot.tg:<chain id>_<token>
}
FAMILIES = ("omni", "sdk", "poa", "hot", "unclassified")
LABEL = {
    "omni": "Omni-form tokens",
    "sdk": "POA-form tokens on the SDK's moved-to-Omni list",
    "poa": "POA-form tokens",
    "hot": "HOT's tokens",
    "unclassified": "unclassified",
}
PREFIX_CHAIN = {"bnb": "bsc"}


def bare(asset):
    for p in ("nep141:", "nep245:"):
        if asset.startswith(p):
            return asset[len(p):]
    return asset


def form_of(asset):
    """The form of a token ID: one of FAMILY_OF_FORM's keys, or 'near' for a token that lives on NEAR."""
    if asset.startswith("1cs_v1:"):
        parts = asset.split(":")
        if len(parts) >= 4 and parts[1] == "near" and parts[2] == "nep141":
            return form_of("nep141:" + ":".join(parts[3:]))
        return "1cs_v1_btc" if asset == "1cs_v1:btc:native:coin" else "1cs_v1"
    if "omni.hot.tg" in asset:
        return "hot"
    b = bare(asset)
    if b.endswith(".omft.near"):
        return "omft_sdk" if b in SDK_LIST else "omft"
    if b.endswith(".omdep.near"):
        return "omdep"
    return "near"


def hot_chain_ids(assets):
    m = {}
    for a, ch in assets.items():
        if "omni.hot.tg:" in a:
            m[a.split("omni.hot.tg:")[1].split("_")[0]] = ch
    return m


def chain_of(asset, assets, hot_ids):
    """The chain a token is delivered on: the public token list's word, else read from the ID."""
    if asset in assets:
        return assets[asset]
    if asset.startswith("1cs_v1:"):
        return asset.split(":")[1]
    if "omni.hot.tg:" in asset:
        cid = asset.split("omni.hot.tg:")[1].split("_")[0]
        return hot_ids.get(cid, "hot-chain-" + cid)
    b = bare(asset)
    for suf in (".omft.near", ".omdep.near"):
        if b.endswith(suf):
            pre = b[:-len(suf)].split("-")[0]
            return PREFIX_CHAIN.get(pre, pre)
    return "near"


def leg(asset, typ, bridge_type, assets, hot_ids):
    """Where one side of a swap sits: 'inside' (an Intents balance, no bridge leg),
    'near' (a token delivered on NEAR, no bridge leg), or the bridge family of the token."""
    if typ != bridge_type:
        return "inside", None
    if not asset:
        return "unclassified", "unknown"
    ch = chain_of(asset, assets, hot_ids)
    f = form_of(asset)
    if ch == "near" or f == "near":
        return "near", "near"
    return FAMILY_OF_FORM[f], ch


def load_blocks(path):
    blocks = {}
    with open(path) as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                blocks[r["block"]] = r
    return blocks


def summarise(block, assets, hot_ids):
    """One block's sums: withdrawals and deposits by category and by (chain, family)."""
    s = {"w": collections.Counter(), "d": collections.Counter(),
         "wn": collections.Counter(), "dn": collections.Counter(),
         "wc": collections.Counter(), "dc": collections.Counter(),
         "in": D(0), "out": D(0), "rows": 0, "null_in": 0, "null_out": 0}
    for o, dst, dtyp, rtyp, n, uin, uout, nin, nout in block["cells"]:
        uin, uout = D(uin), D(uout)
        s["rows"] += n
        s["in"] += uin
        s["out"] += uout
        s["null_in"] += nin
        s["null_out"] += nout
        cat, ch = leg(dst, rtyp, "DESTINATION_CHAIN", assets, hot_ids)
        s["w"][cat] += uout
        s["wn"][cat] += n
        if ch not in (None, "near"):
            s["wc"][(ch, cat)] += uout
        cat, ch = leg(o, dtyp, "ORIGIN_CHAIN", assets, hot_ids)
        s["d"][cat] += uin
        s["dn"][cat] += n
        if ch not in (None, "near"):
            s["dc"][(ch, cat)] += uin
    return s


def shares(tot):
    """Omni's share of bridged value three ways, and POA's and HOT's."""
    bridged = sum((tot[f] for f in FAMILIES), D(0))
    if bridged == 0:
        return None
    return {
        "omni_form": tot["omni"] / bridged,
        "omni_with_sdk": (tot["omni"] + tot["sdk"]) / bridged,
        "omni_with_sdk_and_unclassified": (tot["omni"] + tot["sdk"] + tot["unclassified"]) / bridged,
        "poa": tot["poa"] / bridged,
        "hot": tot["hot"] / bridged,
        "unclassified": tot["unclassified"] / bridged,
    }


def add(counters):
    t = collections.Counter()
    for c in counters:
        for k, v in c.items():
            t[k] += v
    return t


def bootstrap(per_block, key, rng):
    """95% percentile intervals for the shares, resampling blocks."""
    ids = sorted(per_block)
    n = len(ids)
    draws = collections.defaultdict(list)
    for _ in range(BOOT):
        pick = [per_block[ids[rng.randrange(n)]][key] for _ in range(n)]
        sh = shares(add(pick))
        if sh:
            for k, v in sh.items():
                draws[k].append(v)
    out = {}
    for k, v in draws.items():
        v.sort()
        out[k] = (v[int(0.025 * (len(v) - 1))], v[int(round(0.975 * (len(v) - 1)))])
    return out


def usd_m(x):
    return "$%s million" % format(float(x) / 1e6, ",.1f")


def pct(x):
    return "%.1f%%" % (100 * float(x))


def analyse(blocks, assets):
    hot_ids = hot_chain_ids(assets)
    per = {i: summarise(b, assets, hot_ids) for i, b in blocks.items()}
    n = len(per)
    census = n == N_BLOCKS
    scale = D(N_BLOCKS) / D(n)
    rng = random.Random(SEED)
    res = {"blocks_read": n, "blocks_total": N_BLOCKS, "census": census,
           "rows": sum(p["rows"] for p in per.values()),
           "pages": sum(b["pages"] for b in blocks.values()),
           "dropped_outside": sum(b["dropped_outside"] for b in blocks.values()),
           "duplicates": sum(b["duplicates"] for b in blocks.values()),
           "null_usd_in": sum(p["null_in"] for p in per.values()),
           "null_usd_out": sum(p["null_out"] for p in per.values()),
           "first_began": min(b["began"] for b in blocks.values()),
           "last_finished": max(b["finished"] for b in blocks.values())}
    res["total_in_usd_90d"] = str(sum((p["in"] for p in per.values()), D(0)) * scale)
    res["total_out_usd_90d"] = str(sum((p["out"] for p in per.values()), D(0)) * scale)
    last = [i for i in per if i in LAST30]
    res["blocks_read_last30"] = len(last)
    res["total_in_usd_30d"] = (str(sum((per[i]["in"] for i in last), D(0)) * D(30) / D(len(last)))
                               if last else None)
    for side, key, nkey, ckey in (("withdrawals", "w", "wn", "wc"), ("deposits", "d", "dn", "dc")):
        tot = add(p[key] for p in per.values())
        cnt = add(p[nkey] for p in per.values())
        sh = shares(tot)
        ci = None if census else bootstrap(per, key, rng)
        side_res = {"usd": {k: str(v * scale) for k, v in tot.items()},
                    "rows": dict(cnt),
                    "bridged_usd": str(sum((tot[f] for f in FAMILIES), D(0)) * scale),
                    "shares": {k: str(v) for k, v in sh.items()} if sh else None,
                    "intervals": ({k: [str(a), str(b)] for k, (a, b) in ci.items()} if ci else None)}
        bychain = add(p[ckey] for p in per.values())
        chains = collections.defaultdict(lambda: collections.Counter())
        for (ch, fam), v in bychain.items():
            chains[ch][fam] += v
        side_res["by_chain"] = {ch: {f: str(c[f] * scale) for f in FAMILIES if c[f]}
                                for ch, c in chains.items()}
        groups = {"read": collections.Counter(), "not_read": collections.Counter()}
        for ch, c in chains.items():
            g = groups["read" if ch in READ_CHAINS else "not_read"]
            for f, v in c.items():
                g[f] += v
        side_res["by_group"] = {}
        for g, c in groups.items():
            s = shares(c)
            side_res["by_group"][g] = {"bridged_usd": str(sum((c[f] for f in FAMILIES), D(0)) * scale),
                                       "chains": sum(1 for ch in chains if (ch in READ_CHAINS) == (g == "read")),
                                       "shares": {k: str(v) for k, v in s.items()} if s else None}
        res[side] = side_res
    return res


def share_line(side_res, key):
    s = pct(side_res["shares"][key])
    if side_res["intervals"]:
        a, b = side_res["intervals"][key]
        s += " [%s, %s]" % (pct(a), pct(b))
    return s


def render(res, recheck):
    L = []
    w = L.append
    w("# The Explorer read: results")
    w("")
    w("Written by `explorer/analyse.py` from `explorer/data/blocks.jsonl`; do not edit by hand. "
      "The plan is `explorer/PLAN.md`, the family rules `explorer/STAGE2.md`. This is an addition made "
      "after the counted read. It changes no test of `THESIS.md`.")
    w("")
    if res["census"]:
        w("All 90 blocks of 24 hours were read, so these figures are a count of every completed 1Click "
          "swap the API returned for the 90 days to T0, not a sample.")
    else:
        w("%d of the 90 blocks of 24 hours were read before the stop time, in the random order fixed in "
          "the plan. Totals are scaled by 90/%d; shares carry 95%% intervals from a bootstrap over blocks."
          % (res["blocks_read"], res["blocks_read"]))
    w("")
    w("- Completed swaps read: %s, in %s pages, pulled between %s and %s."
      % (format(res["rows"], ","), format(res["pages"], ","), res["first_began"], res["last_finished"]))
    w("- Rows outside their block's bounds and dropped: %s. Rows seen twice and counted once: %s. "
      "Rows with no USD figure: %s on the way in, %s on the way out."
      % (format(res["dropped_outside"], ","), format(res["duplicates"], ","),
         format(res["null_usd_in"], ","), format(res["null_usd_out"], ",")))
    w("- Value of all completed swaps over the 90 days, by `amountInUsd`: %s." % usd_m(res["total_in_usd_90d"]))
    if res["total_in_usd_30d"] is not None:
        w("- Over the 30 days to T0: %s (%d of those 30 blocks read)."
          % (usd_m(res["total_in_usd_30d"]), res["blocks_read_last30"]))
    for side, title, verb, col in (
            ("withdrawals", "Withdrawals: value that left through a bridge", "recipient type `DESTINATION_CHAIN`", "amountOutUsd"),
            ("deposits", "Deposits: value that came in through a bridge", "deposit type `ORIGIN_CHAIN`", "amountInUsd")):
        s = res[side]
        w("")
        w("## %s" % title)
        w("")
        w("Rows with %s, summed by `%s`, by the family of the token on that side." % (verb, col))
        w("")
        w("| family | value | share of bridged value | swaps |")
        w("|---|---|---|---|")
        bridged = D(s["bridged_usd"])
        for f in FAMILIES:
            v = D(s["usd"].get(f, "0"))
            w("| %s | %s | %s | %s |" % (LABEL[f], usd_m(v), pct(v / bridged) if bridged else "n/a",
                                         format(s["rows"].get(f, 0), ",")))
        w("| all bridged | %s | 100.0%% | %s |" % (usd_m(bridged), format(sum(s["rows"].get(f, 0) for f in FAMILIES), ",")))
        w("| a token on NEAR (no bridge leg) | %s | not counted | %s |"
          % (usd_m(s["usd"].get("near", "0")), format(s["rows"].get("near", 0), ",")))
        w("| an Intents balance (no bridge leg) | %s | not counted | %s |"
          % (usd_m(s["usd"].get("inside", "0")), format(s["rows"].get("inside", 0), ",")))
        w("")
        if s["shares"]:
            w("- Omni's share of bridged value, Omni-form tokens only: %s." % share_line(s, "omni_form"))
            w("- With the tokens on the SDK's moved-to-Omni list counted as Omni: %s." % share_line(s, "omni_with_sdk"))
            w("- With the unclassified value counted as Omni too: %s." % share_line(s, "omni_with_sdk_and_unclassified"))
            w("- POA-form tokens not on the SDK's list: %s. HOT's tokens: %s."
              % (share_line(s, "poa"), share_line(s, "hot")))
        for g, name in (("read", "The 8 chains the keyless sample could read"),
                        ("not_read", "Every other chain")):
            gg = s["by_group"][g]
            if gg["shares"]:
                w("- %s (%d chains here): %s bridged; Omni-form %s, SDK-listed %s, POA-form %s, HOT %s, unclassified %s."
                  % (name, gg["chains"], usd_m(gg["bridged_usd"]), pct(gg["shares"]["omni_form"]),
                     pct(D(gg["shares"]["omni_with_sdk"]) - D(gg["shares"]["omni_form"])),
                     pct(gg["shares"]["poa"]), pct(gg["shares"]["hot"]), pct(gg["shares"]["unclassified"])))
        w("")
        w("| chain | read by the keyless sample | value | Omni-form | SDK-listed | POA-form | HOT | unclassified |")
        w("|---|---|---|---|---|---|---|---|")
        rows = []
        for ch, c in s["by_chain"].items():
            tot = sum((D(v) for v in c.values()), D(0))
            rows.append((tot, ch, c))
        for tot, ch, c in sorted(rows, key=lambda r: (-r[0], r[1])):
            w("| %s | %s | %s | %s |" % (ch, "yes" if ch in READ_CHAINS else "no", usd_m(tot),
                                         " | ".join(pct(D(c.get(f, "0")) / tot) if tot else "n/a" for f in FAMILIES)))
    if recheck:
        w("")
        w("## The three blocks read twice")
        w("")
        w("| block | swaps, first reading | swaps, second reading | cells equal | value in, first | value in, second |")
        w("|---|---|---|---|---|---|")
        for r in recheck["blocks"]:
            w("| %d | %s | %s | %s | %s | %s |" % (r["block"], format(r["rows_first"], ","), format(r["rows_second"], ","),
                                                   "yes" if r["cells_equal"] else "no",
                                                   usd_m(r["usd_in_first"]), usd_m(r["usd_in_second"])))
    w("")
    return "\n".join(L)


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 2
    blocks_path, assets_path, out_dir = argv[1:4]
    check = len(argv) > 4 and argv[4] == "--check"
    blocks = load_blocks(blocks_path)
    with open(assets_path) as fh:
        assets = {a: v[0] for a, v in json.load(fh)["assets"].items()}
    res = analyse(blocks, assets)
    recheck = None
    rp = os.path.join(out_dir, "data", "recheck.json")
    if os.path.exists(rp):
        with open(rp) as fh:
            recheck = json.load(fh)
        res["recheck"] = recheck
    md = render(res, recheck)
    js = json.dumps(res, indent=1, sort_keys=True) + "\n"
    targets = ((os.path.join(out_dir, "RESULTS.md"), md), (os.path.join(out_dir, "results.json"), js))
    if check:
        bad = [p for p, text in targets if not os.path.exists(p) or open(p).read() != text]
        print("differs: %s" % ", ".join(bad) if bad else "explorer results match")
        return 1 if bad else 0
    for p, text in targets:
        with open(p, "w") as fh:
            fh.write(text)
    print("wrote", ", ".join(p for p, _ in targets), "| blocks", res["blocks_read"], "| census", res["census"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
