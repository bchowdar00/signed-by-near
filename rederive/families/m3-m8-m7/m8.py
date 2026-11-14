"""M8 program spend per sign request. python3 -I."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from collections import defaultdict

BC = os.environ["RD_DATA"]

REF_PRICES = {
    "2026-03": [1.7010], "2026-04": [1.2962], "2026-05": [1.4553],
    "2026-06": [1.5409, 1.4553], "2026-07": [1.5906],
    "2026-08": [1.7031, 2.04], "2026-09": [2.04], "2026-10": [2.65],
}

def month_days(signs):
    strat = defaultdict(dict)
    for w in signs:
        strat[w["month"]][w["stratum"]] = w["D_s"]
    return {m: sum(v.values()) / 86400.0 for m, v in strat.items()}

def boot_draws(windows_by_stratum, days, seed, ndraw=2000):
    rng = np.random.default_rng(seed)
    out = np.empty(ndraw)
    for i in range(ndraw):
        tot = 0.0
        for st, wins in windows_by_stratum.items():
            n = len(wins)
            idx = rng.integers(0, n, n)
            for j in idx:
                tot += wins[j]["weight"] * wins[j]["y"]
        out[i] = tot / days
    return out  # draws of rate/day; HT draw = rate*days

def main():
    cache = json.load(open("sign_cache.json"))["windows"]
    d = json.load(open(os.path.join(os.environ["RD_REPO"], "frozen", "instants.json")))
    signs = [x for x in d["windows"] if x["family"] == "sign"]
    days = month_days(signs)
    by_month = defaultdict(lambda: defaultdict(list))
    for v in cache.values():
        by_month[v["month"]][v["stratum"]].append(v)
    ledger = json.load(open("hsp007_ledger.json"))
    # per month numerators (mainnet+testnet)
    num = defaultdict(lambda: {"executed": 0.0, "pending": 0.0, "proposed": 0.0})
    for r in ledger:
        num[r["month"]][r["status"]] += r["amount"]

    results = {}
    for mo in ["2026-%02d" % m for m in range(3, 11)]:
        strata = by_month[mo]
        ht = sum(w["weight"] * w["y"] for ws in strata.values() for w in ws)
        exe = num[mo]["executed"]; pend = num[mo]["pending"]; prop = num[mo]["proposed"]
        provisional = (mo == "2026-10")
        numer_primary = (prop if provisional else exe + pend)
        near_per_req = numer_primary / ht
        near_per_req_exec = (prop if provisional else exe) / ht if provisional else exe / ht
        # bootstrap ratio draws: numerator / HT_draw
        dr1 = boot_draws(strata, days[mo], 1) * days[mo]  # HT draws
        dr2 = boot_draws(strata, days[mo], 2) * days[mo]
        def ratio_ci(numval, draws):
            r = numval / draws
            return [float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))]
        ci1 = ratio_ci(numer_primary, dr1)
        ci2 = ratio_ci(numer_primary, dr2)
        usd = {str(p): near_per_req * p for p in REF_PRICES[mo]}
        results[mo] = {
            "ht_calls": ht, "executed": exe, "pending": pend, "proposed": prop,
            "numerator_primary": numer_primary, "provisional": provisional,
            "near_per_request": near_per_req,
            "near_per_request_executed_only": (exe / ht),
            "ci_seed1": ci1, "ci_seed2": ci2,
            "usd_per_request": usd, "ref_prices": REF_PRICES[mo],
        }
    json.dump(results, open("m8_results.json", "w"), indent=1)
    print("month   HTcalls      NEAR/req(exec+pend)  NEAR/req(exec)  ci1                 USD/req")
    for mo, e in results.items():
        tag = " (PROV,proposed)" if e["provisional"] else ""
        print(f"{mo} {e['ht_calls']:>10.1f}  {e['near_per_request']:.6f}  {e['near_per_request_executed_only']:.6f}  "
              f"[{e['ci_seed1'][0]:.6f},{e['ci_seed1'][1]:.6f}]  {e['usd_per_request']}{tag}")

if __name__ == "__main__":
    main()
