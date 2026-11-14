#!/usr/bin/env python3
"""Read three blocks a second time and compare them, cell by cell, with the first reading.

    EXPLORER_HDR=/path/to/header-file python3 -I explorer/recheck.py explorer/data/blocks.jsonl explorer/data/recheck.json

The three are the first three blocks of the fixed order (explorer/PLAN.md, sections 4 and 6).
Like pull.py it keeps no row and never opens the key. Standard library only.
"""
import decimal
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pull  # noqa: E402

D = decimal.Decimal


def usd_in(cells):
    return str(sum((D(c[5]) for c in cells), D(0)))


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    first = {}
    with open(argv[1]) as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                first[r["block"]] = r
    client = pull.Client(os.environ.get("EXPLORER_HDR"))
    out = {"began": pull.stamp(), "blocks": []}
    for i in pull.block_order()[:3]:
        if i not in first:
            print("block", i, "was not read the first time; skipped")
            continue
        start, end = pull.block_bounds(i)
        res = pull.read_window(client, start, end)
        a, b = first[i], res
        out["blocks"].append({
            "block": i, "rows_first": a["rows"], "rows_second": b["rows"],
            "cells_equal": a["cells"] == b["cells"],
            "pages_equal": a["page_sha256"] == b["page_sha256"],
            "usd_in_first": usd_in(a["cells"]), "usd_in_second": usd_in(b["cells"])})
        print(pull.stamp(), "block", i, "rows", a["rows"], b["rows"], "cells equal", a["cells"] == b["cells"], flush=True)
    out["finished"] = pull.stamp()
    with open(argv[2], "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
