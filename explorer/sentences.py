#!/usr/bin/env python3
"""The sentences THESIS.md carries about the Explorer read, built from explorer/results.json.

Every figure of section 4.8 comes from here: the page is written from `section()` and `summary()`,
and `publish/check_thesis.py` requires each of `statements()` on the page, so a figure on the page
cannot differ from the results file. The wording was fixed before the pull finished; which branch
of a sentence is used depends only on the results.

    python3 -I explorer/sentences.py explorer/results.json      (prints the section)

Standard library only; no network.
"""
import decimal
import json
import sys

D = decimal.Decimal
HALF, T1, TENTH = D("0.5"), D("0.9"), D("0.1")
FAMILIES = ("omni", "sdk", "poa", "hot", "unclassified")
READ_CHAINS = ("btc", "sol", "zec", "eth", "arb", "base", "tron", "xrp")   # THESIS.md, section 3


def usd(x):
    return "$%sM" % format(float(D(x)) / 1e6, ",.1f")


def pct(x):
    return "%.1f%%" % (100 * float(D(x)))


def share(side, key):
    s = pct(side["shares"][key])
    if side["intervals"]:
        a, b = side["intervals"][key]
        s += " [%s, %s]" % (pct(a), pct(b))
    return s


def sdk_only(side):
    return pct(D(side["shares"]["omni_with_sdk"]) - D(side["shares"]["omni_form"]))


def split(side, lead):
    return ("%s, Omni-form tokens carried %s, POA-form tokens that the SDK lists as moved to Omni %s, "
            "other POA-form tokens %s, HOT's tokens %s, and %s is unclassified"
            % (lead, share(side, "omni_form"), sdk_only(side), share(side, "poa"), share(side, "hot"),
               pct(side["shares"]["unclassified"])))


def is_named(chain):
    return chain != "unknown" and not chain.startswith("hot-chain-")


def chain_counts(side):
    """Chains with value on them: (named and read by the keyless sample, named and not read, value on chains with no name)."""
    read = other = 0
    loose = D(0)
    for ch, c in side["by_chain"].items():
        v = sum((D(x) for x in c.values()), D(0))
        if v <= 0:
            continue
        if not is_named(ch):
            loose += v
        elif ch in READ_CHAINS:
            read += 1
        else:
            other += 1
    return read, other, loose


def group(g):
    s = g["shares"]
    return ("%s left through a bridge: Omni-form tokens %s, SDK-listed %s, other POA-form %s, HOT's %s, unclassified %s"
            % (usd(g["bridged_usd"]), pct(s["omni_form"]), pct(D(s["omni_with_sdk"]) - D(s["omni_form"])),
               pct(s["poa"]), pct(s["hot"]), pct(s["unclassified"])))


def side_of(lo, hi, mark):
    return "under" if hi < mark else ("over" if lo >= mark else "split")


def position(lo, hi):
    """Where a range sits against half and against T1's 90%."""
    h, t = side_of(lo, hi, HALF), side_of(lo, hi, T1)
    if h == "under":
        return "under half, and so under T1's 90%"
    if t == "over":
        return "at or over T1's 90%"
    if h == "over" and t == "under":
        return "at or over half and under T1's 90%"
    if h == "split" and t == "under":
        return "on both sides of half, and under T1's 90%"
    if h == "over" and t == "split":
        return "at or over half, and on both sides of T1's 90%"
    return "on both sides of half and of T1's 90%"


def verdict(held):
    names = ["POA-form tokens over half", "Omni's side under half", "HOT under 10%"]
    if all(held):
        return "held on all three counts"
    if not any(held):
        return "held on none of its three counts"
    yes = [x for x, h in zip(names, held) if h]
    no = [x for x, h in zip(names, held) if not h]
    return "held on %d of its three counts (%s) and not on the rest (%s)" % (len(yes), "; ".join(yes), "; ".join(no))


def build(r):
    w, d = r["withdrawals"], r["deposits"]
    sample = bool(w["intervals"])
    n = r["blocks_read"]
    rows = format(r["rows"], ",")
    if r["census"]:
        scope = ("all 90 of the 24-hour blocks were read: %s completed swaps, worth %s by the API's own USD figures, "
                 "a count and not a sample" % (rows, usd(r["total_in_usd_90d"])))
    else:
        scope = ("%d of the 90 blocks of 24 hours were read before the stop time, in the random order fixed in the plan: "
                 "%s completed swaps; scaled to the 90 days, about %s by the API's own USD figures. The shares of the main "
                 "families below carry a 95%% interval from a bootstrap over blocks, and a share shown without one is a "
                 "point figure from the blocks read" % (n, rows, usd(r["total_in_usd_90d"])))
    s = [("explorer: what was read", scope)]
    s.append(("explorer: withdrawals by family",
              split(w, "Of the %s that left through a bridge" % usd(w["bridged_usd"]))))
    s.append(("explorer: the Summary's sentence",
              "Intents' own records of 1Click swaps, read with a key after the counted read, put Omni's side of the "
              "bridged withdrawal value at %s with the tokens the SDK lists as moved to Omni, and at %s if the "
              "unclassified value is counted as Omni too"
              % (share(w, "omni_with_sdk"), share(w, "omni_with_sdk_and_unclassified"))))
    s.append(("explorer: Omni's side three ways",
              "Omni's side of the withdrawals is %s on Omni-form tokens alone, %s with the SDK-listed tokens, and %s "
              "if the unclassified value is counted as Omni too"
              % (share(w, "omni_form"), share(w, "omni_with_sdk"), share(w, "omni_with_sdk_and_unclassified"))))
    s.append(("explorer: deposits by family",
              split(d, "Of the %s that came in through a bridge" % usd(d["bridged_usd"]))))

    # the same shares with the value delivered as tokens on NEAR, which cross no bridge, kept in the denominator
    u = {f: D(w["usd"].get(f, "0")) for f in FAMILIES}
    near = D(w["usd"].get("near", "0"))
    bridged = sum(u.values(), D(0))
    wide = bridged + near
    b_lo, b_hi = D(w["shares"]["omni_with_sdk"]), D(w["shares"]["omni_with_sdk_and_unclassified"])
    b_poa, b_hot = D(w["shares"]["poa"]), D(w["shares"]["hot"])
    a_lo, a_hi = (u["omni"] + u["sdk"]) / wide, (u["omni"] + u["sdk"] + u["unclassified"]) / wide
    a_poa, a_hot = u["poa"] / wide, u["hot"] / wide
    s.append(("explorer: with the tokens delivered on NEAR counted in",
              "A further %s was delivered as tokens on NEAR, which cross no bridge. With that value in the denominator "
              "Omni's side is %s, or %s with the unclassified value, and POA-form tokens not on the SDK's list are %s"
              % (usd(near), pct(a_lo), pct(a_hi), pct(a_poa))))

    nr, rd = w["by_group"]["not_read"], w["by_group"]["read"]
    n_read, n_other, loose = chain_counts(w)
    if nr["shares"]:
        text = "On the %d chains here that the keyless sample could not read, %s" % (n_other, group(nr))
        if loose > 0:
            text += " (%s of it on chains the token list does not name)" % usd(loose)
        s.append(("explorer: the chains the sample could not read", text))
    if rd["shares"]:
        s.append(("explorer: the chains the sample could read",
                  "On the %d here that it could read, %s" % (n_read, group(rd))))
    if r.get("total_in_usd_30d") is not None:
        s.append(("explorer: the 30 days to T0",
                  "Over the 30 days to T0 the completed swaps come to %s" % usd(r["total_in_usd_30d"])))

    lo, hi, ends = b_lo, b_hi, ""
    if sample:      # a sample: take the outer ends of the two intervals
        lo = D(w["intervals"]["omni_with_sdk"][0])
        hi = D(w["intervals"]["omni_with_sdk_and_unclassified"][1])
        ends = ", and taking the outer ends of the two intervals"
    s.append(("explorer: against T1's mark and against half",
              "On this channel Omni's side of the bridged withdrawals lies between %s and %s, counting the unclassified "
              "value against it and for it%s: %s" % (pct(lo), pct(hi), ends, position(lo, hi))))

    held_b = [b_poa > HALF, b_lo < HALF, b_hot < TENTH]
    held_a = [a_poa > HALF, a_lo < HALF, a_hot < TENTH]
    lead = ("The expectation written before the pull (POA-form tokens over half of withdrawal value, Omni's side "
            "under half, HOT under 10%)")
    if held_b == held_a:
        exp = "%s %s, whether or not the tokens delivered on NEAR are in the denominator" % (lead, verdict(held_b))
    else:
        exp = ("%s %s as shares of bridged value; with the tokens delivered on NEAR in the denominator it %s"
               % (lead, verdict(held_b), verdict(held_a)))
    if sample:
        exp += ", by the point figures"
    s.append(("explorer: the expectation", exp))
    rc = r.get("recheck")
    if rc and rc.get("blocks"):
        same = sum(1 for b in rc["blocks"] if b["cells_equal"])
        s.append(("explorer: the blocks read twice",
                  "Of %d blocks read a second time after the pull, %d gave the same sums cell for cell"
                  % (len(rc["blocks"]), same)))
    s.append(("explorer: rows with no USD figure",
              "%s of the swaps had no USD figure on the way out and count for nothing in these sums"
              % format(r["null_usd_out"], ",")))
    return dict(s), s


def statements(r):
    """(name, text, times) for publish/check_thesis.py: each must be on the page exactly once."""
    return [(name, text, 1) for name, text in build(r)[1]]


def summary(r):
    """The one sentence the Summary carries."""
    return build(r)[0]["explorer: the Summary's sentence"]


def section(r):
    """The lines of section 4.8 as the page carries them."""
    t, _ = build(r)
    L = ["### 4.8 The same question on Intents' own records (added after the read)", ""]
    L += ["**Added after the read; it changes no test.** The five tests could not use the Intents Explorer API, which "
          "needs a key (§3.1). A key was issued to the author on Nov 13, after the counted read. With it, "
          + t["explorer: what was read"] + ". The plan was timestamped before the first request inside the 90 days, and the "
          "rules that sort tokens into bridges before any figure was read (`explorer/PLAN.md`, `explorer/STAGE2.md`).", ""]
    L += ["This is a different measure from the tests'. It covers one channel, 1Click swaps. It sorts value by whose token "
          "was delivered, since a token's ID names its bridge, and not by the leg a transfer was seen to take on chain, "
          "which is how the tests label a route. The USD figures are the API's.", ""]
    L += ["**Withdrawals.** These are the legs Chain Signatures signs when the token is Omni's. "
          + t["explorer: withdrawals by family"] + ". " + t["explorer: Omni's side three ways"] + ". "
          + t["explorer: with the tokens delivered on NEAR counted in"] + ".", ""]
    L += ["**Deposits.** " + t["explorer: deposits by family"] + ".", ""]
    chains = [t[k] for k in ("explorer: the chains the sample could not read", "explorer: the chains the sample could read") if k in t]
    if chains:
        L += ["**The chains the keyless sample could not read.** " + ". ".join(chains)
              + ". Each chain has its own line in `explorer/RESULTS.md`.", ""]
    tail = [t["explorer: against T1's mark and against half"], t["explorer: the expectation"]]
    if "explorer: the 30 days to T0" in t:
        tail.append(t["explorer: the 30 days to T0"])
    if "explorer: the blocks read twice" in t:
        tail.append(t["explorer: the blocks read twice"])
    tail.append(t["explorer: rows with no USD figure"])
    L += ["**Against T1 and against the expectation.** " + ". ".join(tail) + ".", ""]
    L += ["What this read cannot show: flows that do not pass through 1Click, and the route a given transfer took. "
          "A reader without a key cannot repeat the pull; the sums it rests on are published, and "
          "`python3 -I explorer/analyse.py explorer/data/blocks.jsonl explorer/data/assets.json explorer --check` "
          "recomputes every figure in this section from them.", ""]
    return L


if __name__ == "__main__":
    with open(sys.argv[1]) as fh:
        print("\n".join(section(json.load(fh))))
