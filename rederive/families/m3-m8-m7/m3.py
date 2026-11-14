"""M3 monthly sign rate. Uses sign_cache.json. python3 -I."""
import sys, os as _os; sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import json, os
from collections import defaultdict, Counter
import numpy as np
from stats_lib import garwood

BC = os.environ["RD_DATA"]

def month_days(signs_meta):
    strat = defaultdict(dict)
    for w in signs_meta:
        strat[w["month"]][w["stratum"]] = w["D_s"]
    return {m: sum(v.values()) / 86400.0 for m, v in strat.items()}

def load():
    cache = json.load(open("sign_cache.json"))["windows"]
    d = json.load(open(os.path.join(os.environ["RD_REPO"], "frozen", "instants.json")))
    signs_meta = [x for x in d["windows"] if x["family"] == "sign"]
    return cache, signs_meta

# flagged interval [Sep29 00:00Z, Oct5 00:00Z) in ns
import datetime as dt
def utc_ns(y,mo,da):
    return int(dt.datetime(y,mo,da,tzinfo=dt.timezone.utc).timestamp()*1e9)
FLAG_LO = utc_ns(2026,9,29)
FLAG_HI = utc_ns(2026,10,5)

def bootstrap_rate(windows_by_stratum, days, seed, ndraw=2000):
    rng = np.random.default_rng(seed)
    draws = np.empty(ndraw)
    for i in range(ndraw):
        tot = 0.0
        for st, wins in windows_by_stratum.items():
            n = len(wins)
            idx = rng.integers(0, n, n)
            for j in idx:
                w = wins[j]
                tot += w["weight"] * w["y"]
        draws[i] = tot / days
    lo = float(np.percentile(draws, 2.5))
    hi = float(np.percentile(draws, 97.5))
    return lo, hi

def main():
    cache, signs_meta = load()
    days_map = month_days(signs_meta)
    # group completed windows by month and stratum
    by_month = defaultdict(lambda: defaultdict(list))
    strata_by_month = defaultdict(set)
    not_completed_wins = defaultdict(list)
    for wid, v in cache.items():
        by_month[v["month"]][v["stratum"]].append(v)
        strata_by_month[v["month"]].add(v["stratum"])
        if not v["completed"]:
            not_completed_wins[v["month"]].append(v["key"])
    # deposits distribution over all in-window rows
    dep_counter = Counter()
    for wid, v in cache.items():
        for r in v["rows"]:
            dep_counter[str(r["deposit"])] += 1

    results = {}
    months = sorted(by_month.keys())
    for m in months:
        days = days_map[m]
        strata = by_month[m]
        completed = len(not_completed_wins[m]) == 0
        # HT total using ALL windows (completed and not) would be wrong; for completed months use all
        ht = 0.0; ht_fail = 0.0; raw_count = 0; exposure = 0.0
        for st, wins in strata.items():
            for w in wins:
                ht += w["weight"] * w["y"]
                ht_fail += w["weight"] * w["y_fail"]
                raw_count += w["y"]
                exposure += w["covered_s"]
        rate = ht / days
        gar_lo_s, gar_hi_s = garwood(raw_count, exposure)
        gar_lo, gar_hi = gar_lo_s * 86400.0, gar_hi_s * 86400.0
        entry = {
            "days": days, "ht_total": ht, "rate_per_day": rate,
            "raw_count": raw_count, "exposure_s": exposure,
            "garwood_rate_lo": gar_lo, "garwood_rate_hi": gar_hi,
            "failed_share": (ht_fail / ht) if ht > 0 else None,
            "completed": completed,
            "not_completed_windows": sorted(not_completed_wins[m]),
            "n_windows": sum(len(w) for w in strata.values()),
        }
        if completed:
            b1 = bootstrap_rate(strata, days, 1)
            b2 = bootstrap_rate(strata, days, 2)
            entry["boot_seed1"] = b1
            entry["boot_seed2"] = b2
            # hull using union of both boot seeds and garwood
            blo = min(b1[0], b2[0]); bhi = max(b1[1], b2[1])
            hull_lo = min(blo, gar_lo); hull_hi = max(bhi, gar_hi)
            entry["hull"] = [hull_lo, hull_hi]
            entry["hull_lo_src"] = "bootstrap" if blo <= gar_lo else "garwood"
            entry["hull_hi_src"] = "bootstrap" if bhi >= gar_hi else "garwood"
        results[m] = entry

    # flagged-day adjusted rates for 2026-09 and 2026-10
    flagged = {}
    for m, fld in (("2026-09", 2), ("2026-10", 4)):
        strata = by_month[m]
        if len(not_completed_wins[m]) != 0:
            flagged[m] = {"completed": False}
            continue
        tot_out = 0.0
        for st, wins in strata.items():
            for w in wins:
                c_out = sum(1 for r in w["rows"] if not (FLAG_LO <= r["ts_inc"] < FLAG_HI))
                tot_out += w["weight"] * c_out
        days_out = days_map[m] - fld
        flagged[m] = {"rate_outside": tot_out / days_out, "days_outside": days_out,
                      "ht_outside": tot_out, "flagged_days": fld}

    out = {"months": results, "flagged": flagged,
           "deposits": dict(dep_counter),
           "flag_interval_utc": ["2026-09-29T00:00Z", "2026-10-05T00:00Z (exclusive)"]}
    json.dump(out, open("m3_results.json", "w"), indent=1)
    # print summary
    for m in months:
        e = results[m]
        if e["completed"]:
            print(f"{m} days={e['days']:.4f} HT={e['ht_total']:.2f} rate={e['rate_per_day']:.2f} "
                  f"gar=[{e['garwood_rate_lo']:.2f},{e['garwood_rate_hi']:.2f}] "
                  f"b1=[{e['boot_seed1'][0]:.2f},{e['boot_seed1'][1]:.2f}] fail={e['failed_share']}")
        else:
            print(f"{m} NOT COMPLETED windows={e['not_completed_windows']}")
    print("FLAGGED", json.dumps(flagged, indent=0))
    print("DEPOSITS", dict(dep_counter))

if __name__ == "__main__":
    main()
