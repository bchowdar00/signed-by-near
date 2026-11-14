import json
import os
import re
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import hsp007 as H

HERE = os.path.dirname(__file__)
LEDGER = os.path.join(HERE, "..", "inputs", "hsp007-ledger.json")
REHEARSAL = os.path.join(HERE, "fixtures", "hsp007-operators-rehearsal.jsonl")

D = lambda s: Decimal(str(s))


def _amt(s):
    return Decimal(s.replace(",", ""))


class TestExtractionChecks(unittest.TestCase):
    """The six checks from METHOD-b §M8, reproduced on the extracted table."""

    @classmethod
    def setUpClass(cls):
        cls.t = H.load(LEDGER)
        cls.rows = cls.t["rows"]
        cls.pm = H.per_month(cls.t)

    def _sum(self, pred):
        return sum((_amt(r["amount_near"]) for r in self.rows if pred(r)), Decimal("0"))

    def test_check1_executed_march_to_september(self):
        got = self._sum(lambda r: r["status"] == "executed"
                        and "2026-03" <= r["service_month"] <= "2026-09")
        self.assertEqual(got, Decimal("338436.08"))

    def test_check2_pending_rows(self):
        apr = self._sum(lambda r: r["status"] == "pending" and r["service_month"] == "2026-04")
        aug = self._sum(lambda r: r["status"] == "pending" and r["service_month"] == "2026-08")
        allp = self._sum(lambda r: r["status"] == "pending")
        execd = self._sum(lambda r: r["status"] == "executed"
                          and "2026-03" <= r["service_month"] <= "2026-09")
        self.assertEqual(apr, Decimal("2300"))
        self.assertEqual(aug, Decimal("6136.40"))
        self.assertEqual(allp, Decimal("8436.40"))
        self.assertEqual(execd + allp, Decimal("346872.48"))

    def test_check3_march_and_september_mainnet(self):
        mar = [r for r in self.rows if r["status"] == "executed"
               and r["service_month"] == "2026-03" and r["network"] == "mainnet"]
        sep = [r for r in self.rows if r["status"] == "executed"
               and r["service_month"] == "2026-09" and r["network"] == "mainnet"]
        self.assertEqual(sum(_amt(r["amount_near"]) for r in mar), Decimal("36800"))
        self.assertEqual(len(mar), 8)
        self.assertEqual(sum(_amt(r["amount_near"]) for r in sep), Decimal("73293.34"))
        self.assertEqual(len(sep), 17)

    def test_check4_october_is_proposed(self):
        prop = [r for r in self.rows if r["status"] == "proposed"]
        self.assertTrue(all(r["service_month"] == "2026-10" for r in prop))
        self.assertEqual(len(prop), 17)
        self.assertEqual(sum(_amt(r["amount_near"]) for r in prop), Decimal("76864.52"))
        self.assertTrue(self.pm["2026-10"]["provisional"])

    def test_check4_text_in_saved_source(self):
        # the proposed report's text names the month-end count after Blacksand left; needs the saved
        # forum JSON (not shipped), located by HSP007_SOURCE and checked against the ledger's sha256
        path = os.environ.get("HSP007_SOURCE")
        if not path or not os.path.exists(path):
            self.skipTest("set HSP007_SOURCE to the saved gov-hsp007-execution-42147.json")
        import hashlib
        with open(path, "rb") as fh:
            self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), self.t["source"]["sha256"])
        with open(path) as fh:
            src = json.load(fh)
        p26 = next(p["cooked"] for p in src["post_stream"]["posts"] if p["post_number"] == 26)
        text = re.sub(r"<[^>]+>", " ", p26)
        self.assertIn("16 active at month-end following", text)
        self.assertIn("departure", text)

    def test_check5_transparency_total_does_not_reconcile(self):
        tr = [rp for rp in self.t["reports"] if rp["kind"] == "transparency_report"]
        self.assertEqual(len(tr), 1)
        self.assertEqual(_amt(tr[0]["stated_total_near"]), Decimal("344372.94"))
        # recorded, not fixed: it matches neither the executed rows nor executed+pending
        self.assertNotEqual(Decimal("344372.94"), Decimal("338436.08"))
        self.assertNotEqual(Decimal("344372.94"), Decimal("346872.48"))

    def test_check6_june_states_two_reference_prices(self):
        self.assertEqual(self.pm["2026-06"]["reference_price_usd"],
                         [Decimal("1.5409"), Decimal("1.4553")])


class TestPerMonth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pm = H.per_month(H.load(LEDGER))

    def test_network_split_sums_to_executed(self):
        for month, row in self.pm.items():
            self.assertEqual(row["mainnet_executed_near"] + row["testnet_executed_near"],
                             row["executed_near"], msg=month)

    def test_node_counts_and_sorting(self):
        self.assertEqual(len(self.pm["2026-03"]["nodes_paid_mainnet"]), 8)
        self.assertEqual(len(self.pm["2026-09"]["nodes_paid_mainnet"]), 17)
        # October has only a proposed report; its payees stand in for paid nodes
        self.assertEqual(len(self.pm["2026-10"]["nodes_paid_mainnet"]), 17)
        for row in self.pm.values():
            self.assertEqual(row["nodes_paid_mainnet"], sorted(row["nodes_paid_mainnet"]))

    def test_provisional_only_for_october(self):
        self.assertEqual({m for m, r in self.pm.items() if r["provisional"]}, {"2026-10"})

    def test_pending_excluded_from_paid_nodes(self):
        # April Blacksand was pending, so it is not among the paid mainnet nodes
        self.assertNotIn("Blacksand", self.pm["2026-04"]["nodes_paid_mainnet"])


class TestExpenditure(unittest.TestCase):
    def test_executed_and_pending_math(self):
        row = {"executed_near": Decimal("36800"), "pending_near": Decimal("2300"),
               "proposed_near": Decimal("0"),
               "reference_price_usd": [Decimal("2")], "provisional": False}
        exp = H.expenditure(row, 100.0)
        self.assertEqual(exp["executed"]["near_per_request"], Decimal("368"))
        self.assertEqual(exp["executed"]["usd_per_request"], [Decimal("736")])
        self.assertEqual(exp["executed_plus_pending"]["near_per_request"], Decimal("391"))
        self.assertEqual(exp["executed_plus_pending"]["usd_per_request"], [Decimal("782")])
        self.assertNotIn("proposed", exp)

    def test_provisional_proposed_and_multiple_prices(self):
        row = {"executed_near": Decimal("0"), "pending_near": Decimal("0"),
               "proposed_near": Decimal("1000"),
               "reference_price_usd": [Decimal("2"), Decimal("3")], "provisional": True}
        exp = H.expenditure(row, 10.0)
        self.assertEqual(exp["proposed"]["near_per_request"], Decimal("100"))
        self.assertEqual(exp["proposed"]["usd_per_request"], [Decimal("200"), Decimal("300")])

    def test_nonpositive_calls_raise(self):
        row = {"executed_near": Decimal("1"), "pending_near": Decimal("0"),
               "proposed_near": Decimal("0"), "reference_price_usd": [], "provisional": False}
        with self.assertRaises(ValueError):
            H.expenditure(row, 0.0)


class TestReconcileSynthetic(unittest.TestCase):
    def test_matched_paid_and_missing(self):
        pm = {"2026-01": {"nodes_paid_mainnet": ["Near One", "Blacksand", "Ghost Co LLC"]}}
        ops = [{"point": "2026-02", "participants": ["n1-multichain.near", "x.near"]}]
        rec = H.reconcile(pm, ops)["2026-01"]
        self.assertEqual(rec["participants_point"], "2026-02")
        self.assertEqual(rec["matched"], ["n1-multichain.near"])
        self.assertEqual(rec["paid_not_participant"], ["blacksandtech.near"])
        self.assertEqual(rec["participant_not_paid"], ["x.near"])
        self.assertEqual(rec["unmapped_names"], ["Ghost Co LLC"])

    def test_missing_participant_set_flagged(self):
        pm = {"2026-05": {"nodes_paid_mainnet": ["Near One"]}}
        rec = H.reconcile(pm, [])["2026-05"]
        self.assertTrue(rec["no_participant_set"])
        self.assertEqual(rec["participants_point"], "2026-06")

    def test_year_rollover_point(self):
        pm = {"2026-12": {"nodes_paid_mainnet": ["Near One"]}}
        ops = [{"point": "2027-01", "participants": ["n1-multichain.near"]}]
        rec = H.reconcile(pm, ops)["2026-12"]
        self.assertEqual(rec["participants_point"], "2027-01")
        self.assertEqual(rec["matched"], ["n1-multichain.near"])

    def test_failed_or_empty_reads_give_no_participant_set(self):
        pm = {"2026-09": {"nodes_paid_mainnet": ["Near One"]}}
        for row in ({"point": "2026-10", "status": "value", "participants": []},
                    {"point": "2026-10", "status": "fail", "ok": False},
                    {"point": "2026-10", "status": "value", "parse_error": "KeyError()"}):
            self.assertTrue(H.reconcile(pm, [row])["2026-09"]["no_participant_set"], row)


class TestReconcileRehearsal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pm = H.per_month(H.load(LEDGER))
        cls.ops = [json.loads(l) for l in open(REHEARSAL)]
        cls.rec = H.reconcile(cls.pm, cls.ops)

    def test_september_reconciles_cleanly(self):
        r = self.rec["2026-09"]
        self.assertEqual(len(r["matched"]), 17)
        self.assertEqual(r["paid_not_participant"], [])
        self.assertEqual(r["participant_not_paid"], [])
        self.assertEqual(r["unmapped_names"], [])

    def test_april_blacksand_pending_shows_as_participant_not_paid(self):
        self.assertEqual(self.rec["2026-04"]["participant_not_paid"], ["blacksandtech.near"])

    def test_october_blacksand_proposed_but_departed(self):
        r = self.rec["2026-10"]
        self.assertEqual(r["paid_not_participant"], ["blacksandtech.near"])
        self.assertEqual(len(r["matched"]), 16)

    def test_august_legal_names_are_unmapped_not_guessed(self):
        # the August execution report switched to legal-entity names the thread never
        # pairs with an account, so most are honestly reported as unmapped
        self.assertGreater(len(self.rec["2026-08"]["unmapped_names"]), 10)


if __name__ == "__main__":
    unittest.main()
