#!/usr/bin/env python3
"""Read the 90 days to T0 from the NEAR Intents Explorer API, one 24-hour block at a time.

The plan this follows is explorer/PLAN.md. In short: the 90 blocks are read in a random order
fixed by a seed, each block is read whole, and no transaction row is written to disk. Each
block's rows are summed in memory into cells keyed by (origin asset, destination asset, deposit
type, recipient type), and one line per finished block is appended to the output file.

The API needs a key. This script never opens the key: curl reads it as a header file
(`curl -H @file`), and the path comes from the environment variable EXPLORER_HDR.

    EXPLORER_HDR=/path/to/header-file python3 -I explorer/pull.py run explorer/data/blocks.jsonl
    EXPLORER_HDR=/path/to/header-file python3 -I explorer/pull.py pilot START END [PAGE]
    python3 -I explorer/pull.py order          (prints the block order; no network)

`pilot` reads one window given as two ISO times, prints counts only and writes nothing.
Standard library only.
"""
import datetime as dt
import decimal
import hashlib
import json
import os
import random
import subprocess
import sys
import time
import urllib.parse

BASE = "https://explorer.near-intents.org/api/v0/transactions"
UTC = dt.timezone.utc
T0 = dt.datetime(2026, 11, 10, 11, 0, 0, tzinfo=UTC)      # the study's data cutoff
N_BLOCKS = 90                                             # 24-hour blocks ending at T0
BLOCK = dt.timedelta(days=1)
SEED = 20261113
PAGE = 1000                                               # the API's maximum page size
STATUSES = "SUCCESS"
SPACING = 5.3                                             # seconds between request starts
STOP_AT = dt.datetime(2026, 11, 14, 4, 0, 0, tzinfo=UTC)  # no block is started after this
MS = dt.timedelta(milliseconds=1)


class Stop(Exception):
    """The run must stop and be reported (bad key, or the limit kept refusing)."""


def block_bounds(i):
    start = T0 - N_BLOCKS * BLOCK + i * BLOCK
    return start, start + BLOCK


def block_order():
    return random.Random(SEED).sample(range(N_BLOCKS), N_BLOCKS)


def iso(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (t.microsecond // 1000)


def parse_time(s):
    """ISO 8601 with a Z or an offset and any number of fraction digits."""
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    head, sign, off = s[:19], "+", "00:00"
    rest = s[19:]
    frac = ""
    if rest.startswith("."):
        j = 1
        while j < len(rest) and rest[j].isdigit():
            j += 1
        frac, rest = rest[1:j], rest[j:]
    if rest:
        sign, off = rest[0], rest[1:]
    t = dt.datetime.strptime(head, "%Y-%m-%dT%H:%M:%S")
    micro = int((frac + "000000")[:6]) if frac else 0
    hh, mm = (off.split(":") + ["00"])[:2] if ":" in off else (off[:2], off[2:] or "00")
    delta = dt.timedelta(hours=int(hh), minutes=int(mm))
    if sign == "-":
        delta = -delta
    return t.replace(microsecond=micro, tzinfo=dt.timezone(delta)).astimezone(UTC)


class Client:
    def __init__(self, hdr_path, spacing=SPACING):
        if not hdr_path or not os.path.exists(hdr_path):
            raise SystemExit("EXPLORER_HDR must name the header file (it is never opened here)")
        self.hdr = hdr_path
        self.spacing = spacing
        self.last = 0.0
        self.requests = 0
        self.refused = 0

    def get(self, params):
        """One page. Returns the body as bytes. Raises Stop on 401/403 or repeated 429."""
        url = BASE + "?" + urllib.parse.urlencode(params)
        errors = 0
        refusals = 0
        while True:
            wait = self.last + self.spacing - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.last = time.monotonic()
            self.requests += 1
            p = subprocess.run(
                ["curl", "-sS", "-m", "120", "--compressed", "-H", "@" + self.hdr,
                 "-w", "\n__HTTP__%{http_code}", url],
                capture_output=True)
            out = p.stdout
            cut = out.rfind(b"\n__HTTP__")
            code = int(out[cut + 9:] or b"0") if cut >= 0 else 0
            body = out[:cut] if cut >= 0 else b""
            if code == 200:
                return body
            if code in (401, 403):
                raise Stop("http %d: the key was refused" % code)
            if code == 429:
                refusals += 1
                self.refused += 1
                self.spacing = min(8.0, self.spacing + 0.5)
                if refusals > 6:
                    raise Stop("http 429 seven times in a row")
                time.sleep(30)
                continue
            errors += 1
            if errors > 4:
                raise IOError("http %d after 5 tries (curl exit %d)" % (code, p.returncode))
            time.sleep(20)


def row_key(r):
    return (r.get("depositAddressAndMemo")
            or "|".join(r.get("intentHashes") or [])
            or "%s|%s|%s" % (r.get("createdAt"), r.get("amountIn"), r.get("amountOut")))


def usd(v):
    if v is None or v == "":
        return None
    try:
        d = decimal.Decimal(str(v))
    except decimal.InvalidOperation:
        return None
    return d if d.is_finite() else None


def read_window(client, start, end, page=PAGE):
    """Every SUCCESS row with start <= createdAt < end, summed into cells. No row is kept."""
    base = {"startTimestamp": iso(start - MS), "endTimestamp": iso(end),
            "statuses": STATUSES, "numberOfTransactions": page}
    cells = {}
    seen = set()
    hashes = []
    rows = dropped = dups = 0
    cursor = None
    prev_last = None
    while True:
        params = dict(base)
        if cursor is not None:
            params.update(cursor)
        body = client.get(params)
        hashes.append(hashlib.sha256(body).hexdigest())
        data = json.loads(body)
        if not isinstance(data, list):
            raise IOError("the reply is not a list")
        times = [parse_time(r["createdAt"]) for r in data]
        if any(a < b for a, b in zip(times, times[1:])):
            raise IOError("a page is not in descending time order")
        if times and prev_last is not None and times[0] > prev_last:
            raise IOError("a page starts later than the page before it ended")
        for r, t in zip(data, times):
            if not (start <= t < end):
                dropped += 1
                continue
            k = row_key(r)
            if k in seen:
                dups += 1
                continue
            seen.add(k)
            rows += 1
            key = (r.get("originAsset"), r.get("destinationAsset"),
                   r.get("depositType"), r.get("recipientType"))
            c = cells.setdefault(key, [0, decimal.Decimal(0), decimal.Decimal(0), 0, 0])
            c[0] += 1
            a, b = usd(r.get("amountInUsd")), usd(r.get("amountOutUsd"))
            if a is None:
                c[3] += 1
            else:
                c[1] += a
            if b is None:
                c[4] += 1
            else:
                c[2] += b
        if len(data) < page:
            break
        last = data[-1]
        prev_last = times[-1]
        if last.get("depositAddress"):
            cursor = {"lastDepositAddress": last["depositAddress"], "direction": "next"}
            if last.get("depositMemo"):
                cursor["lastDepositMemo"] = last["depositMemo"]
        else:
            # no address to page from: move the end of the window to just after the last row
            cursor = {"endTimestamp": iso(times[-1] + MS)}
    out = [[k[0], k[1], k[2], k[3], c[0], str(c[1]), str(c[2]), c[3], c[4]]
           for k, c in sorted(cells.items(), key=lambda kv: tuple(str(x) for x in kv[0]))]
    return {"pages": len(hashes), "rows": rows, "dropped_outside": dropped, "duplicates": dups,
            "page_sha256": hashes, "cells": out}


def now():
    return dt.datetime.now(UTC)


def stamp():
    return now().strftime("%Y-%m-%dT%H:%M:%SZ")


def run(out_path):
    client = Client(os.environ.get("EXPLORER_HDR"))
    done = set()
    if os.path.exists(out_path):
        with open(out_path) as f:
            for line in f:
                if line.strip():
                    done.add(json.loads(line)["block"])
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    failed = []
    for attempt, queue in ((1, block_order()), (2, failed)):
        for i in list(queue):
            if i in done:
                continue
            if now() >= STOP_AT:
                print(stamp(), "stop time reached;", len(done), "blocks done", flush=True)
                return 0
            start, end = block_bounds(i)
            began = stamp()
            try:
                res = read_window(client, start, end)
            except Stop as e:
                print(stamp(), "STOP block", i, str(e), flush=True)
                return 3
            except (IOError, ValueError, KeyError) as e:
                print(stamp(), "block", i, "failed on pass", attempt, "-", str(e), flush=True)
                if attempt == 1:
                    failed.append(i)
                continue
            rec = {"block": i, "start": iso(start), "end": iso(end), "began": began,
                   "finished": stamp()}
            rec.update(res)
            with open(out_path, "a") as f:
                f.write(json.dumps(rec, separators=(",", ":")) + "\n")
            done.add(i)
            print(stamp(), "block", i, "pages", res["pages"], "rows", res["rows"],
                  "dropped", res["dropped_outside"], "dups", res["duplicates"],
                  "| done", len(done), "of", N_BLOCKS, "| requests", client.requests,
                  "refused", client.refused, flush=True)
    print(stamp(), "finished;", len(done), "blocks done", flush=True)
    return 0


def pilot(start_s, end_s, page):
    client = Client(os.environ.get("EXPLORER_HDR"))
    res = read_window(client, parse_time(start_s), parse_time(end_s), page)
    print("pages", res["pages"], "rows", res["rows"], "dropped", res["dropped_outside"],
          "dups", res["duplicates"], "cells", len(res["cells"]), "requests", client.requests)
    return 0


def main(argv):
    if len(argv) >= 3 and argv[1] == "run":
        return run(argv[2])
    if len(argv) >= 4 and argv[1] == "pilot":
        return pilot(argv[2], argv[3], int(argv[4]) if len(argv) > 4 else PAGE)
    if len(argv) >= 2 and argv[1] == "order":
        for n, i in enumerate(block_order()):
            s, e = block_bounds(i)
            print(n, i, iso(s), iso(e))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
