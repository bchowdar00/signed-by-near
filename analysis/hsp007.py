"""Functions over the HSP-007 payout ledger (METHOD-b §M8).

The ledger table is produced by inputs/extract_hsp007.py from the saved execution
thread (gov.near.org topic 42147). This module aggregates it per service month,
turns a month's spend into NEAR/USD per `sign` request, and reconciles the paid
mainnet nodes against the signer contract's participant set read from archival RPC.

All money is handled as decimal.Decimal; amounts are summed from the exact strings
the thread printed (commas stripped, nothing rounded).
"""
import json
from decimal import Decimal

# Display name -> mainnet signer account id. Built only from thread rows that print
# BOTH a node name and its NEAR account: the Eligible Node Registry tables (posts
# 3, 7, 8, 10, 14, 16, 22), the October compensation table (post 26) and the
# September payout ledger (post 27). Names the thread never pairs with an account
# (e.g. the legal-entity names in the August execution report, post 23) are left out
# on purpose and surface as `unmapped_names` in reconcile() rather than being guessed.
NODE_ACCOUNTS = {
    "Near One": "n1-multichain.near",
    "Blacksand": "blacksandtech.near",
    "Luganodes": "mpc-lgns.near",
    "Aurora": "multichain-mainnet-aurora.near",
    "Staking4all": "near-mpc-staking4all-01.near",
    "Node Monster": "nodemonster.near",
    "Everstake": "everstake-mpc-1.near",
    "Stakin": "stakin-mpc.near",
    "Stakin (The TIE)": "stakin-mpc.near",
    "MPCH": "mpch-01.near",
    "SVRN": "svrn-01.near",
    "Greenfield": "greenfield-mpc01.near",
    "HashKey": "hashkeympc.near",
    "Natsai": "natsai-mpc.near",
    "Astrostakers": "astrostakers-mainnet.near",
    "Klever": "klever-nearmpc-01.near",
    "Bitwise": "bitwise-mpc01.near",
    "Nansen": "nansen-ai-mpc.near",
}

# status values that count as money actually paid to a node
_PAID = ("executed",)


def load(path):
    """Read the ledger table written by extract_hsp007.py."""
    with open(path) as fh:
        return json.load(fh)


def _dec(amount_str):
    return Decimal(amount_str.replace(",", ""))


def _next_month(month):
    y, m = (int(x) for x in month.split("-"))
    return "%04d-%02d" % (y + 1, 1) if m == 12 else "%04d-%02d" % (y, m + 1)


def _account_for(name):
    key = name.rstrip("*").strip()
    if key in NODE_ACCOUNTS:
        return NODE_ACCOUNTS[key]
    low = key.lower()
    for k, v in NODE_ACCOUNTS.items():
        if k.lower() == low:
            return v
    return None


def per_month(table):
    """Aggregate the ledger by service month.

    Each value has: executed_near, pending_near, proposed_near,
    mainnet_executed_near, testnet_executed_near (Decimal); nodes_paid_mainnet
    (sorted node names actually paid on mainnet — executed rows, or the proposed
    payees for a provisional month); reference_price_usd (list of Decimal, the
    distinct prices every report for that month states, in order of appearance);
    and provisional (True when the month has only a proposed report)."""
    months = {}
    for r in table["rows"]:
        months.setdefault(r["service_month"], []).append(r)

    # distinct reference prices per month, order preserved, across every report
    prices = {}
    for rep in table["reports"]:
        m = rep["service_month"]
        if m is None:
            continue
        bucket = prices.setdefault(m, [])
        for p in rep["reference_price_usd"]:
            d = Decimal(p)
            if d not in bucket:
                bucket.append(d)

    out = {}
    for month, rows in months.items():
        statuses = {r["status"] for r in rows}
        provisional = statuses == {"proposed"}
        paid_statuses = {"proposed"} if provisional else set(_PAID)

        def _sum(pred):
            return sum((_dec(r["amount_near"]) for r in rows if pred(r)), Decimal("0"))

        paid_mainnet = sorted({
            r["node"] for r in rows
            if r["network"] == "mainnet" and r["status"] in paid_statuses
        })
        out[month] = {
            "executed_near": _sum(lambda r: r["status"] == "executed"),
            "pending_near": _sum(lambda r: r["status"] == "pending"),
            "proposed_near": _sum(lambda r: r["status"] == "proposed"),
            "mainnet_executed_near": _sum(
                lambda r: r["status"] == "executed" and r["network"] == "mainnet"),
            "testnet_executed_near": _sum(
                lambda r: r["status"] == "executed" and r["network"] == "testnet"),
            "nodes_paid_mainnet": paid_mainnet,
            "reference_price_usd": prices.get(month, []),
            "provisional": provisional,
        }
    return out


def expenditure(per_month_row, calls_in_month):
    """Program spend per `sign` request for one month.

    `calls_in_month` is a float (the caller passes a point estimate or a single
    bootstrap draw). Returns NEAR per request and USD per request (one USD figure
    per stated reference price) for the executed total and the executed+pending
    total, plus the proposed total when the month is provisional. This is NEAR's
    spend on the program per request, not the marginal cost of a signature."""
    calls = Decimal(str(calls_in_month))
    if calls <= 0:
        raise ValueError("calls_in_month must be positive, got %r" % (calls_in_month,))
    prices = per_month_row["reference_price_usd"]

    def basis(near):
        per_req = near / calls
        return {"near_per_request": per_req,
                "usd_per_request": [per_req * p for p in prices]}

    executed = per_month_row["executed_near"]
    pending = per_month_row["pending_near"]
    result = {
        "calls_in_month": float(calls_in_month),
        "executed": basis(executed),
        "executed_plus_pending": basis(executed + pending),
    }
    if per_month_row["provisional"]:
        result["proposed"] = basis(per_month_row["proposed_near"])
    return result


def reconcile(per_month_table, operators_rows):
    """Compare each month's paid mainnet nodes with the signer contract's
    participant set at that month's end.

    `operators_rows` are archival-RPC reads: {point, height, ts_ns, status,
    participants, threshold}, where `point` is the month START whose state was
    read. The set at the end of month M is the row whose point is the month after
    M. Node names are mapped to account ids via NODE_ACCOUNTS; names with no sourced
    mapping are returned under `unmapped_names` rather than guessed. For each month:
    matched, paid_not_participant and participant_not_paid are sorted account-id
    lists; `participants_point` names the row used; `no_participant_set` flags a
    month with no matching read."""
    # a read that failed, or did not parse, has no participant list: its month gets no set
    by_point = {row["point"]: set(row["participants"]) for row in operators_rows
                if row.get("status", "value") == "value" and isinstance(row.get("participants"), list)
                and row["participants"]}  # an empty list means the state was not Running or Resharing
    out = {}
    for month, row in per_month_table.items():
        point = _next_month(month)
        if point not in by_point:
            out[month] = {"participants_point": point, "no_participant_set": True}
            continue
        participants = by_point[point]
        paid_accounts, unmapped = set(), []
        for name in row["nodes_paid_mainnet"]:
            acct = _account_for(name)
            if acct is None:
                unmapped.append(name)
            else:
                paid_accounts.add(acct)
        out[month] = {
            "participants_point": point,
            "matched": sorted(paid_accounts & participants),
            "paid_not_participant": sorted(paid_accounts - participants),
            "participant_not_paid": sorted(participants - paid_accounts),
            "unmapped_names": sorted(unmapped),
        }
    return out
