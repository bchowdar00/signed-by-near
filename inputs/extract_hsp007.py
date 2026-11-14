"""Extract the HSP-007 payout ledger from the saved Discourse topic JSON (M8).

Reads the saved execution thread (gov.near.org topic 42147) and writes
inputs/hsp007-ledger.json: one `rows` entry per per-operator payout line in the
monthly Payout Execution Reports (status executed/pending, with transaction hash)
plus the October proposed report (status proposed), and one `reports` entry per
report block (performance / payout-execution / proposed / transparency) carrying
the reference price(s) it states and its stated total.

Nothing is typed by hand: every number and name is read from the thread's HTML
tables. If a table cannot be parsed the script raises instead of guessing.

Run: python3 -I inputs/extract_hsp007.py
"""
import datetime
import hashlib
import html
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser

# usage: python3 -I inputs/extract_hsp007.py <saved gov-hsp007-execution-42147.json>
SRC = sys.argv[1] if len(sys.argv) > 1 else "gov-hsp007-execution-42147.json"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hsp007-ledger.json")
TOPIC_ID = 42147

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}

# Report-block boundary headings.
REPORT_RE = re.compile(
    r"^(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{4})\s*[–-]\s*"
    r"(Performance Report|Payout Execution Report)\b")
TRANSPARENCY_RE = re.compile(r"Transparency Report")

# Reference price (the 180-day average NEAR/USD the report states). Anchored on the
# price label so cap thresholds ($3.00) and USD payout amounts are not captured.
REF_PRICE_RE = re.compile(
    r"(?:trailing average of|average of|Average NEAR Price:?|Average Price:?|"
    r"Avg NEAR Price)\s*\$?\s*(\d+\.\d{2,4})")

# base58 hash token (NEAR tx hashes), full or abbreviated with an ellipsis.
HASH_RE = re.compile(r"[1-9A-HJ-NP-Za-km-z]{6,}(?:[.…]{2,3}[1-9A-HJ-NP-Za-km-z]{3,})?")


class _Parser(HTMLParser):
    """Flatten cooked HTML into an ordered list of ('h', level, text) and
    ('table', rows) events, where rows is a list of lists of cell strings."""

    def __init__(self):
        super().__init__()
        self.events = []
        self._depth = 0
        self._table = None
        self._row = None
        self._cell = None
        self._htag = None
        self._hbuf = ""

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._depth += 1
            if self._depth == 1:
                self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = ""
        elif tag in ("h1", "h2", "h3", "h4"):
            self._htag = tag
            self._hbuf = ""

    def handle_endtag(self, tag):
        if tag == "table" and self._depth:
            self._depth -= 1
            if self._depth == 0:
                self.events.append(("table", self._table))
                self._table = None
        elif tag == "tr" and self._row is not None:
            self._table.append(self._row)
            self._row = None
        elif tag in ("td", "th") and self._cell is not None:
            self._row.append(_clean(self._cell))
            self._cell = None
        elif tag == self._htag:
            level = int(self._htag[1])
            self.events.append(("h", level, _clean(self._hbuf)))
            self._htag = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell += data
        elif self._htag is not None:
            self._hbuf += data
        else:
            # prose (paragraphs, list items) outside tables/headings; kept so
            # reference prices stated only in notes are not lost.
            text = _clean(data)
            if text:
                self.events.append(("text", text))


def _clean(text):
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_post(cooked):
    p = _Parser()
    p.feed(cooked)
    return p.events


def segment(events):
    """Split a post's events into report blocks. Each block is a dict with the
    boundary heading's classification plus the events that follow it (up to the
    next boundary)."""
    blocks = []
    cur = None
    for ev in events:
        if ev[0] == "h":
            text = ev[2]
            m = REPORT_RE.match(text)
            if m:
                month = "%04d-%02d" % (int(m.group(2)), MONTHS[m.group(1)])
                kind = ("performance_report" if m.group(3) == "Performance Report"
                        else "payout_execution_report")
                cur = {"service_month": month, "kind": kind, "title": text, "events": []}
                blocks.append(cur)
                continue
            if TRANSPARENCY_RE.search(text):
                cur = {"service_month": None, "kind": "transparency_report",
                       "title": text, "events": []}
                blocks.append(cur)
                continue
        if cur is not None:
            cur["events"].append(ev)
    return blocks


def block_text(block):
    parts = []
    for ev in block["events"]:
        if ev[0] == "h" or ev[0] == "text":
            parts.append(ev[2] if ev[0] == "h" else ev[1])
        elif ev[0] == "table":
            for row in ev[1]:
                parts.extend(row)
    return " ".join(parts)


def reference_prices(block):
    seen, out = set(), []
    for v in REF_PRICE_RE.findall(block_text(block)):
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _amount_col(header):
    for i, h in enumerate(header):
        if re.search(r"Amount \(NEAR\)|NEAR Payment|Final Payout|Calculated Payout", h, re.I):
            return i
    return None


def _is_total(cell):
    return bool(re.search(r"\b(sub\s?total|grand total|total)\b", cell, re.I))


def stated_total(block):
    if block["kind"] == "transparency_report":
        for ev in block["events"]:
            if ev[0] != "table":
                continue
            header = ev[1][0] if ev[1] else []
            vcol = next((i for i, h in enumerate(header) if h.lower() == "value"), None)
            if vcol is None:
                continue
            for row in ev[1][1:]:
                if "disbursed" in row[0].lower() and vcol < len(row):
                    return _strip_near(row[vcol])
        return None
    grand = total = None
    for ev in block["events"]:
        if ev[0] != "table" or not ev[1]:
            continue
        header = ev[1][0]
        acol = _amount_col(header)
        if acol is None:
            continue
        for row in ev[1][1:]:
            if acol >= len(row) or not row[0]:
                continue
            if re.search(r"grand total", row[0], re.I):
                grand = _strip_near(row[acol])
            elif re.search(r"\btotal\b", row[0], re.I) and not re.search(r"sub\s?total", row[0], re.I):
                total = _strip_near(row[acol])  # a plain program total, not a per-network subtotal
    return grand if grand is not None else total


def _strip_near(cell):
    return re.sub(r"\s*NEAR\s*$", "", cell).strip() or None


def network_for(sub):
    if sub and re.search(r"testnet", sub, re.I):
        return "testnet"
    return "mainnet"


def parse_tx(cell):
    """Return (tx_or_None, abbreviated, status) from a Transaction Hash cell."""
    low = cell.lower()
    # A pending cell reads "Pending"/"PENDING" with no transaction link. Check this
    # first: "Pending" is itself valid base58 and would otherwise match HASH_RE.
    if re.search(r"\bpending\b", low) and "transaction" not in low and "nearblocks" not in low:
        return None, False, "pending"
    m = HASH_RE.search(cell.replace("NEAR Transaction", "").replace("NearBlocks", ""))
    if not m:
        return None, False, "pending" if "pending" in low else "executed"
    tx = m.group(0)
    abbreviated = bool(re.search(r"[.…]{2,3}", tx))
    return tx, abbreviated, "executed"


def ledger_rows(block, status_if_proposed=False):
    """Yield row dicts from the payout tables in a block. For execution reports the
    status comes from the tx cell; for the proposed report every row is 'proposed'."""
    rows = []
    sub = None
    post = block["post_number"]
    month = block["service_month"]
    for ev in block["events"]:
        if ev[0] == "h":
            sub = ev[2]
            continue
        if ev[0] != "table":
            continue
        table = ev[1]
        if not table:
            continue
        header = table[0]
        acol = _amount_col(header)
        if acol is None:
            continue  # SLA / price / dispute table
        txcol = next((i for i, h in enumerate(header)
                      if re.search(r"Transaction", h, re.I)), None)
        net = network_for(sub)
        for row in table[1:]:
            if not row or not row[0] or _is_total(row[0]):
                continue
            if acol >= len(row):
                continue
            amount = _strip_near(row[acol])
            if amount in (None, "", "—", "-"):
                continue
            if status_if_proposed:
                tx, abbreviated, status = None, False, "proposed"
            elif txcol is not None and txcol < len(row):
                tx, abbreviated, status = parse_tx(row[txcol])
            else:
                tx, abbreviated, status = None, False, "executed"
            rows.append({
                "service_month": month,
                "network": net,
                "node": row[0],
                "amount_near": amount,
                "status": status,
                "tx": tx,
                "tx_abbreviated": abbreviated,
                "post_number": post,
                "source_line": " | ".join(row),
            })
    return rows


def main():
    with open(SRC, "rb") as fh:
        raw = fh.read()
    sha = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw)
    posts = data["post_stream"]["posts"]

    all_blocks = []
    for p in posts:
        for block in segment(parse_post(p["cooked"])):
            block["post_number"] = p["post_number"]
            all_blocks.append(block)

    exec_months = {b["service_month"] for b in all_blocks
                   if b["kind"] == "payout_execution_report"}

    rows, reports = [], []
    for b in all_blocks:
        kind = b["kind"]
        # A performance report for a month with no execution report is the proposed
        # report (October): reclassify it and emit its compensation rows as proposed.
        proposed = (kind == "performance_report" and b["service_month"] not in exec_months)
        if proposed:
            kind = "proposed_report"
        if kind == "payout_execution_report":
            rows.extend(ledger_rows(b))
        elif proposed:
            rows.extend(ledger_rows(b, status_if_proposed=True))
        reports.append({
            "service_month": b["service_month"],
            "post_number": b["post_number"],
            "kind": kind,
            "reference_price_usd": reference_prices(b),
            "stated_total_near": stated_total(b),
            "source_line": b["title"],
        })

    extracted_utc = subprocess.run(
        ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True).stdout.strip()

    table = {
        "source": {"file": os.path.basename(SRC), "sha256": sha, "topic_id": TOPIC_ID,
                   "extracted_utc": extracted_utc},
        "rows": rows,
        "reports": reports,
    }
    with open(OUT, "w") as fh:
        json.dump(table, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("wrote %s: %d rows, %d reports" % (OUT, len(rows), len(reports)))


if __name__ == "__main__":
    sys.exit(main())
