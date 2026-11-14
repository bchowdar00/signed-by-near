"""Tests of the Explorer read's code, on made-up cells. No network, no key.

    python3 -I -m unittest discover -s explorer
"""
import decimal
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyse  # noqa: E402
import pull  # noqa: E402

D = decimal.Decimal
with open(os.path.join(HERE, "data", "assets.json")) as fh:
    ASSETS = {a: v[0] for a, v in json.load(fh)["assets"].items()}
HOT = analyse.hot_chain_ids(ASSETS)

ETH = "nep141:eth.omft.near"
SOL = "nep141:sol.omft.near"
BNB = "nep141:bnb.omdep.near"
HOTBNB = "nep245:v2_1.omni.hot.tg:56_11111111111111111111"
BTCO = "1cs_v1:btc:native:coin"
WNEAR = "nep141:wrap.near"
CHAIN, INT = "DESTINATION_CHAIN", "INTENTS"
OCHAIN = "ORIGIN_CHAIN"


def block(i, cells):
    return {"block": i, "pages": 1, "rows": sum(c[4] for c in cells), "dropped_outside": 0,
            "duplicates": 0, "began": "2026-01-01T00:00:00Z", "finished": "2026-01-01T00:01:00Z",
            "page_sha256": [], "cells": cells}


class Forms(unittest.TestCase):
    def leg(self, asset, typ=CHAIN):
        return analyse.leg(asset, typ, CHAIN, ASSETS, HOT)

    def test_each_form(self):
        self.assertEqual(self.leg(ETH), ("poa", "eth"))
        self.assertEqual(self.leg(SOL), ("sdk", "sol"))
        self.assertEqual(self.leg("nep141:zec.omft.near"), ("sdk", "zec"))
        self.assertEqual(self.leg(BNB), ("omni", "bsc"))
        self.assertEqual(self.leg(HOTBNB), ("hot", "bsc"))
        self.assertEqual(self.leg(BTCO), ("omni", "btc"))
        self.assertEqual(self.leg("1cs_v1:sol:spl:3ZLekZYq2qkZiSpnSvabjit34tUkjSwD1JFuW9as9wBG"),
                         ("unclassified", "sol"))

    def test_tokens_on_near_cross_no_bridge(self):
        for a in (WNEAR, "nep141:nbtc.bridge.near", "1cs_v1:near:nep141:zec.omft.near",
                  "nep141:usdt.tether-token.near"):
            self.assertEqual(self.leg(a), ("near", "near"), a)

    def test_an_intents_balance_is_not_a_bridge_leg(self):
        self.assertEqual(self.leg(ETH, INT), ("inside", None))

    def test_a_token_missing_from_the_list_is_read_from_its_id(self):
        self.assertEqual(self.leg("nep141:doge-abc.omft.near"), ("poa", "doge"))
        self.assertEqual(self.leg("nep141:bnb-0xabc.omdep.near"), ("omni", "bsc"))
        self.assertEqual(self.leg("nep245:v2_1.omni.hot.tg:424242_x"), ("hot", "hot-chain-424242"))

    def test_the_sdk_list_has_17_ids(self):
        self.assertEqual(len(analyse.SDK_LIST), 17)
        self.assertEqual(sum(1 for a in analyse.SDK_LIST if a.startswith("sol")), 12)


class Sums(unittest.TestCase):
    def cells(self, k=1):
        # origin, destination, deposit type, recipient type, n, usd in, usd out, null in, null out
        return [[ETH, BNB, OCHAIN, CHAIN, 2, str(100 * k), str(99 * k), 0, 0],
                [BNB, ETH, OCHAIN, CHAIN, 1, str(300 * k), str(297 * k), 0, 0],
                [ETH, SOL, OCHAIN, CHAIN, 1, str(50 * k), str(49 * k), 0, 0],
                [ETH, WNEAR, OCHAIN, CHAIN, 1, str(10 * k), str(9 * k), 0, 0],
                [HOTBNB, ETH, INT, INT, 1, str(7 * k), str(6 * k), 0, 1]]

    def test_a_sample_of_two_blocks(self):
        blocks = {0: block(0, self.cells()), 61: block(61, self.cells(3))}
        r = analyse.analyse(blocks, ASSETS)
        self.assertFalse(r["census"])
        w = r["withdrawals"]
        # withdrawals over both blocks: omni 99*4, poa 297*4, sdk 49*4, scaled by 90/2
        self.assertEqual(D(w["usd"]["omni"]), D(99 * 4 * 45))
        self.assertEqual(D(w["usd"]["poa"]), D(297 * 4 * 45))
        self.assertEqual(D(w["usd"]["sdk"]), D(49 * 4 * 45))
        self.assertEqual(D(w["usd"]["near"]), D(9 * 4 * 45))
        self.assertEqual(D(w["usd"]["inside"]), D(6 * 4 * 45))
        self.assertEqual(D(w["shares"]["omni_form"]), D(99) / D(445))
        self.assertEqual(D(w["shares"]["omni_with_sdk"]), D(148) / D(445))
        self.assertEqual(D(w["shares"]["omni_with_sdk_and_unclassified"]), D(148) / D(445))
        lo, hi = (D(x) for x in w["intervals"]["omni_form"])
        self.assertEqual(lo, hi)  # both blocks have the same mix, so the interval has no width
        d = r["deposits"]
        self.assertEqual(D(d["usd"]["poa"]), D(160 * 4 * 45))
        self.assertEqual(D(d["usd"]["omni"]), D(300 * 4 * 45))
        self.assertEqual(D(d["usd"]["inside"]), D(7 * 4 * 45))
        self.assertEqual(D(r["total_in_usd_90d"]), D(467 * 4 * 45))
        self.assertEqual(D(r["total_in_usd_30d"]), D(467 * 3 * 30))
        self.assertEqual(r["null_usd_out"], 2)
        self.assertEqual(w["by_group"]["read"]["chains"], 2)       # eth, sol
        self.assertEqual(w["by_group"]["not_read"]["chains"], 1)   # bsc
        self.assertEqual(D(w["by_chain"]["bsc"]["omni"]), D(99 * 4 * 45))

    def test_all_90_blocks_is_a_census(self):
        blocks = {i: block(i, self.cells()) for i in range(90)}
        r = analyse.analyse(blocks, ASSETS)
        self.assertTrue(r["census"])
        self.assertIsNone(r["withdrawals"]["intervals"])
        self.assertEqual(D(r["withdrawals"]["usd"]["omni"]), D(99 * 90))
        self.assertEqual(D(r["total_in_usd_30d"]), D(467 * 30))
        text = analyse.render(r, None)
        self.assertIn("not a sample", text)
        self.assertIn("| bsc | no |", text)

    def test_an_interval_has_width_when_blocks_differ(self):
        a = [[ETH, BNB, OCHAIN, CHAIN, 1, "100", "100", 0, 0]]
        b = [[BNB, ETH, OCHAIN, CHAIN, 1, "100", "100", 0, 0]]
        r = analyse.analyse({0: block(0, a), 1: block(1, b), 2: block(2, a)}, ASSETS)
        lo, hi = (D(x) for x in r["withdrawals"]["intervals"]["omni_form"])
        self.assertLess(lo, hi)
        self.assertIn("[", analyse.render(r, None))


class Blocks(unittest.TestCase):
    def test_the_blocks_tile_the_90_days(self):
        self.assertEqual(pull.iso(pull.block_bounds(0)[0]), "2026-08-12T11:00:00.000Z")
        self.assertEqual(pull.block_bounds(89)[1], pull.T0)
        for i in range(89):
            self.assertEqual(pull.block_bounds(i)[1], pull.block_bounds(i + 1)[0])
        self.assertEqual(sorted(pull.block_order()), list(range(90)))
        self.assertEqual(pull.block_order()[:3], [22, 2, 16])

    def test_times(self):
        t = pull.parse_time("2026-11-12T02:09:55.526123+02:00")
        self.assertEqual(pull.iso(t), "2026-11-12T00:09:55.526Z")


if __name__ == "__main__":
    unittest.main()
