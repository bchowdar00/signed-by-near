#!/usr/bin/env python3
"""Compare the Explorer read's results with the second implementation's, value by value.

    python3 -I rederive/explorer/compare.py explorer/results.json rederive/explorer/out/rederived.json

USD sums and counts must be equal to the digit; shares to 1e-25 (the two files carry a
different number of digits). Prints the count compared and every difference; exits 1 on any.
Standard library only; no network.
"""
import decimal
import json
import sys

D = decimal.Decimal
decimal.getcontext().prec = 40
SHARES = (("omni_form", "omni"), ("omni_with_sdk", "omni+sdk"),
          ("omni_with_sdk_and_unclassified", "omni+sdk+unclassified"),
          ("poa", "poa"), ("hot", "hot"), ("unclassified", "unclassified"))
CATS = ("omni", "sdk", "poa", "hot", "unclassified", "near", "inside")


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    with open(argv[1]) as fh:
        a = json.load(fh)
    with open(argv[2]) as fh:
        b = json.load(fh)
    diffs, n = [], 0

    def cmp(name, x, y, tol=D(0)):
        nonlocal n
        n += 1
        x, y = D(str(x)), D(str(y))
        if abs(x - y) > tol:
            diffs.append((name, str(x), str(y)))

    for side in ("withdrawals", "deposits"):
        s, t = a[side], b[side]
        for c in CATS:
            cmp("%s usd %s" % (side, c), s["usd"].get(c, "0"), t["usd_by_category"][c])
            cmp("%s rows %s" % (side, c), s["rows"].get(c, 0), t["rows_by_category"][c])
        cmp("%s bridged" % side, s["bridged_usd"], t["bridged_usd"])
        for x, y in SHARES:
            cmp("%s share %s" % (side, x), s["shares"][x], t["shares_of_bridged"][y], D("1e-25"))
        for x, y in (("read", "sampled8"), ("not_read", "other_chains")):
            g, h = s["by_group"][x], t[y]
            cmp("%s %s bridged" % (side, x), g["bridged_usd"], h["bridged_usd"])
            cmp("%s %s chains" % (side, x), g["chains"], h["chains_with_value_count"])
            for p, q in SHARES:
                if p in g["shares"] and q in h["shares_of_group"]:
                    cmp("%s %s share %s" % (side, x, p), g["shares"][p], h["shares_of_group"][q], D("1e-25"))
        mine = {ch: {k: D(v) for k, v in c.items() if D(v) != 0} for ch, c in s["by_chain"].items()}
        mine = {ch: c for ch, c in mine.items() if c}
        theirs = {ch: {k: D(str(v)) for k, v in c.items() if D(str(v)) != 0}
                  for ch, c in t["bridged_usd_by_chain"].items()}
        theirs = {ch: c for ch, c in theirs.items() if c}
        n += 1
        if set(mine) != set(theirs):
            diffs.append(("%s chains" % side, sorted(set(mine) - set(theirs)), sorted(set(theirs) - set(mine))))
        for ch in sorted(set(mine) & set(theirs)):
            n += 1
            if mine[ch] != theirs[ch]:
                diffs.append(("%s chain %s" % (side, ch), str(mine[ch]), str(theirs[ch])))
    tt = b["totals"]
    cmp("value in, 90 days", a["total_in_usd_90d"], tt["amountInUsd_90d"])
    cmp("value in, blocks 60-89", a["total_in_usd_30d"], tt["amountInUsd_blocks_60_89"])
    cmp("value out, 90 days", a["total_out_usd_90d"], tt["amountOutUsd_90d"])
    cmp("rows", a["rows"], tt["rows"])
    cmp("rows with no USD figure out", a["null_usd_out"], tt["rows_no_amountOutUsd"])
    cmp("rows with no USD figure in", a["null_usd_in"], tt["rows_no_amountInUsd"])
    for d in diffs:
        print("differs:", d)
    print("%d values compared; %d differ" % (n, len(diffs)))
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
