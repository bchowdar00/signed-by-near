"""Tests for analysis/neardata.py (METHOD M4, M6, M7).

Synthetic cases cover the pairing, purpose and bound logic. Fixture cases run against real
`v1.signer` block extracts fetched AFTER the data cutoff (block 223,906,826), so they lie outside
the frozen sample. The chain top at fetch time was 223,913,158, so the brief's suggested start of
224,000,000 did not exist yet; the fixtures use the post-cutoff range that does exist, which still
satisfies the boundary (heights strictly above the cutoff). See the report for this deviation.

Fixtures (fetched with collector/nd.py get/extract; same jsonl format; extracted calls only).
Fetch time (UTC): 2026-11-10 12:04:58Z (chain top 223,913,158 at fetch time).
  nd-contig.jsonl   heights 223,907,000 .. 223,907,399 (400 contiguous blocks), part 'contiguous'.
                    399 present (http 200), 1 skipped; 41 sign, 41 respond calls.
                    sha256 e28c021e228b59ba2deb3837643e20c637196861d8a5e88dbd66a4bfbfc09a8b (198 KB).
  nd-scatter.jsonl  150 seeded-random heights in [223,908,000, 223,913,000), part 'sample:2026-11'.
                    150 present; 14 sign calls (11 secp256k1, 2 jwt# login, 1 other Ed25519).
                    sha256 62f57fa0aed87dab52135935b2d86005d3d36096cc5f4140a5245d1b286c9658 (51 KB).
On real data every one of the 41 succeeded responds in nd-contig had its (payload, tweak, domain)
equal to a derived `sign` key, confirming the SHA3-256 epsilon-derivation tweak (test below).
"""
import os
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'analysis'))
import neardata as N  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), 'fixtures')
CONTIG = os.path.join(FIX, 'nd-contig.jsonl')
SCATTER = os.path.join(FIX, 'nd-scatter.jsonl')


# --- builders ------------------------------------------------------------------------------------

def sign_new(pred, path, payload_hex, scheme='Ecdsa', domain=0, signer='s.near', ts=0):
    return {'method': 'sign', 'predecessor': pred, 'signer': signer, 'ts_ns': ts,
            'status': {'SuccessReceiptId': 'r'}, 'deposit_yocto': '1',
            'args': {'request': {'path': path, 'payload_v2': {scheme: payload_hex}, 'domain_id': domain}}}


def sign_old(pred, path, payload_bytes, key_version=0, signer='s.near', ts=0):
    return {'method': 'sign', 'predecessor': pred, 'signer': signer, 'ts_ns': ts,
            'status': {'SuccessReceiptId': 'r'}, 'deposit_yocto': '1',
            'args': {'request': {'payload': list(payload_bytes), 'path': path, 'key_version': key_version}}}


def respond(pred, path, payload_hex, scheme='Ecdsa', domain=0, ok=True, tweak_as_list=True, ts=0,
            signer='v1.signer'):
    tw_hex = N.tweak_of(pred, path)
    tweak = list(bytes.fromhex(tw_hex)) if tweak_as_list else tw_hex
    status = {'SuccessValue': ''} if ok else {'Failure': {'ActionError': {}}}
    return {'method': 'respond', 'predecessor': signer, 'signer': signer, 'ts_ns': ts,
            'status': status, 'deposit_yocto': '0',
            'args': {'request': {'tweak': tweak, 'payload': {scheme: payload_hex}, 'domain_id': domain},
                     'response': {'scheme': 'Secp256k1'}}}


def block(height, calls, part='contiguous', ts=0):
    # each call carries its block's height and timestamp, as the real extractor records them
    for c in calls:
        c['height'] = height
        c['ts_ns'] = ts
    return {'part': part, 'height': height, 'present': True, 'http': 200, 'ts_ns': ts, 'calls': calls}


P = 'a' * 64  # a 32-byte payload, as hex


# --- load, sign_calls ----------------------------------------------------------------------------

class TestLoad(unittest.TestCase):
    def test_load_filters_and_exposes_skipped(self):
        recs = [block(1, []), {'part': 'contiguous', 'height': 2, 'present': False, 'http': 200},
                {'part': 'contiguous', 'height': 3, 'present': True, 'http': 500}]
        bl = N.load(recs)
        self.assertEqual(len(bl), 1)
        self.assertEqual(bl.n_total, 3)
        self.assertEqual(len(bl.skipped), 2)

    def test_sign_calls_carries_part(self):
        bl = N.load([block(5, [sign_new('p.near', 'p1', P)], part='sample:2026-11')])
        sc = N.sign_calls(bl)
        self.assertEqual(len(sc), 1)
        self.assertEqual(sc[0]['part'], 'sample:2026-11')


# --- M4: FastAuth shares and bound ---------------------------------------------------------------

class TestFastAuth(unittest.TestCase):
    def test_counts_by_block_includes_zero_blocks(self):
        blocks = N.load([
            block(1, [sign_new(N.FASTAUTH, 'jwt#a', P, scheme='Eddsa', signer='sweat.near')],
                  part='sample:2026-11'),
            block(2, [], part='sample:2026-11'),  # zero FastAuth -> empty Counter
            block(3, [sign_new('other.near', 'p', P)], part='sample:2026-11'),  # not FastAuth
            block(4, [sign_new(N.FASTAUTH, 'jwt#b', P, scheme='Eddsa', signer='meteor.near')],
                  part='sample:2026-10'),  # wrong month, excluded
        ])
        cs = N.fastauth_counts_by_block(blocks, '2026-11')
        self.assertEqual(len(cs), 3)
        self.assertEqual(cs[0], Counter({'sweat.near': 1}))
        self.assertEqual(cs[1], Counter())
        self.assertEqual(cs[2], Counter())

    def test_signer_share(self):
        cs = [Counter({'x.near': 3}), Counter({'y.near': 1}), Counter()]
        share, total = N.signer_share(cs, 'x.near')
        self.assertEqual(total, 4)
        self.assertAlmostEqual(share, 0.75)
        self.assertEqual(N.signer_share([], 'x.near'), (0.0, 0))

    def test_signer_bound_worked_example(self):
        # three blocks, equal FastAuth counts, all one signer -> m = 3, share = 1, lower = 0.025^(1/3)
        cs = [Counter({'x.near': 5}), Counter({'x.near': 5}), Counter({'x.near': 5})]
        lo, hi = N.signer_bound(cs, 'x.near')
        self.assertAlmostEqual(lo, 0.025 ** (1 / 3), places=4)
        self.assertAlmostEqual(lo, 0.2924, places=4)
        self.assertEqual(hi, 1.0)

    def test_signer_bound_none_without_fastauth(self):
        self.assertIsNone(N.signer_bound([Counter(), Counter()], 'x.near'))


# --- M6: purpose ---------------------------------------------------------------------------------

class TestPurpose(unittest.TestCase):
    def test_secp256k1_old_form(self):
        c = sign_old('p.near', 'bridge-1', bytes(range(32)))
        self.assertEqual(N.purpose_of(c), 'secp256k1')

    def test_secp256k1_ecdsa_v2(self):
        self.assertEqual(N.purpose_of(sign_new('p.near', 'x', P, scheme='Ecdsa')), 'secp256k1')

    def test_ed25519_fastauth_login(self):
        c = sign_new('fast-auth.near', 'jwt#abc', P, scheme='Eddsa')
        self.assertEqual(N.purpose_of(c), 'ed25519_fastauth_login')

    def test_ed25519_other_solana(self):
        c = sign_new('p.near', 'solana-1', P, scheme='Eddsa')
        self.assertEqual(N.purpose_of(c), 'ed25519_other_solana')

    def test_ed25519_other_near(self):
        c = sign_new('p.near', 'near-wallet', P, scheme='Eddsa')
        self.assertEqual(N.purpose_of(c), 'ed25519_other_near')

    def test_ed25519_other_unknown(self):
        c = sign_new('p.near', 'misc-path', P, scheme='Eddsa')
        self.assertEqual(N.purpose_of(c), 'ed25519_other_unknown')

    def test_unparsed(self):
        self.assertEqual(N.purpose_of({'method': 'sign', 'args': {'_undecoded_b64': 'zzz'}}), 'unparsed')
        self.assertEqual(N.purpose_of({'method': 'sign', 'args': {}}), 'unparsed')
        self.assertEqual(N.purpose_of({'method': 'sign', 'args': 'nope'}), 'unparsed')

    def test_purpose_by_month(self):
        blocks = N.load([
            block(1, [sign_new('p.near', 'x', P, scheme='Ecdsa'),
                      sign_new('fast-auth.near', 'jwt#a', P, scheme='Eddsa')], part='sample:2026-11'),
            block(2, [sign_new('p.near', 'x', P, scheme='Ecdsa')], part='sample:2026-10'),
            block(3, [sign_new('p.near', 'x', P)], part='contiguous'),  # not a sample block
        ])
        by_month, by_pred = N.purpose_by_month(blocks)
        self.assertEqual(by_month['2026-11'], Counter({'secp256k1': 1, 'ed25519_fastauth_login': 1}))
        self.assertEqual(by_month['2026-10'], Counter({'secp256k1': 1}))
        self.assertNotIn('contiguous', by_month)
        self.assertEqual(by_pred['2026-11']['fast-auth.near'], Counter({'ed25519_fastauth_login': 1}))


# --- M7: completion ------------------------------------------------------------------------------

class TestCompletion(unittest.TestCase):
    def test_unique_pairing(self):
        blocks = [
            block(10, [], ts=0),                                   # context
            block(11, [sign_new('p.near', 'p1', P)], ts=1_000_000_000),  # middle: request
            block(12, [respond('p.near', 'p1', P)], ts=3_500_000_000),   # middle: response
            block(13, [], ts=4_000_000_000),                       # tail
        ]
        r = N.completion(blocks, n_context=1, n_tail=1)
        self.assertEqual((r['evaluated'], r['matched'], r['matched_unique'], r['matched_by_order']),
                         (1, 1, 1, 0))
        self.assertEqual((r['censored'], r['ambiguous']), (0, 0))
        self.assertEqual(r['matched_share'], 1.0)
        self.assertEqual(r['matched_share_unambiguous'], 1.0)
        self.assertAlmostEqual(r['median_delay_s'], 2.5)
        self.assertAlmostEqual(r['max_delay_s'], 2.5)

    def test_repeated_requests_by_order(self):
        blocks = [
            block(10, []),
            block(11, [sign_new('p.near', 'p1', P)], ts=1_000_000_000),
            block(12, [sign_new('p.near', 'p1', P)], ts=2_000_000_000),
            block(13, [respond('p.near', 'p1', P)], ts=3_000_000_000),
            block(14, [respond('p.near', 'p1', P)], ts=5_000_000_000),
            block(15, []),
        ]
        r = N.completion(blocks, n_context=1, n_tail=1)
        self.assertEqual((r['evaluated'], r['matched'], r['matched_by_order'], r['matched_unique']),
                         (2, 2, 2, 0))
        # pairs are in order: req@11 -> resp@13 (2.0s), req@12 -> resp@14 (3.0s)
        delays = sorted(p['delay_s'] for p in r['pairs'])
        self.assertAlmostEqual(delays[0], 2.0)
        self.assertAlmostEqual(delays[1], 3.0)
        self.assertAlmostEqual(r['median_delay_s'], 2.5)

    def test_response_before_request_not_paired(self):
        blocks = [
            block(10, []),
            block(11, [respond('p.near', 'p1', P)], ts=1_000_000_000),  # response first
            block(12, [sign_new('p.near', 'p1', P)], ts=2_000_000_000),  # request after
            block(13, []),
        ]
        r = N.completion(blocks, n_context=1, n_tail=1)
        self.assertEqual((r['evaluated'], r['matched'], r['censored']), (1, 0, 1))
        self.assertEqual(r['unmatched_responses'], 1)
        self.assertEqual(r['matched_share'], 0.0)

    def test_head_block_member_makes_ambiguous(self):
        blocks = [
            block(10, [sign_new('p.near', 'p1', P)]),               # context: identical group member
            block(11, [sign_new('p.near', 'p1', P)]),               # middle request
            block(12, [respond('p.near', 'p1', P)]),                # middle response
            block(13, []),
        ]
        r = N.completion(blocks, n_context=1, n_tail=1)
        self.assertEqual((r['evaluated'], r['ambiguous'], r['matched'], r['censored']), (1, 1, 0, 0))
        self.assertEqual(r['matched_share'], 0.0)
        self.assertIsNone(r['matched_share_unambiguous'])

    def test_censored_no_response(self):
        blocks = [
            block(10, []),
            block(11, [sign_new('p.near', 'p1', P)]),
            block(12, []),
        ]
        r = N.completion(blocks, n_context=1, n_tail=1)
        self.assertEqual((r['evaluated'], r['censored'], r['matched']), (1, 1, 0))

    def test_failed_respond_ignored(self):
        blocks = [
            block(10, []),
            block(11, [sign_new('p.near', 'p1', P)], ts=1_000_000_000),
            block(12, [respond('p.near', 'p1', P, ok=False)], ts=2_000_000_000),  # failed
            block(13, []),
        ]
        r = N.completion(blocks, n_context=1, n_tail=1)
        # a failed respond is never paired: with no succeeded respond the request is censored
        self.assertEqual((r['evaluated'], r['matched'], r['censored']), (1, 0, 1))
        self.assertEqual(r['failed_responses_seen'], 1)
        self.assertEqual(r['matched_share'], 0.0)

    def test_failed_then_succeeded_respond_pairs_with_success(self):
        blocks = [
            block(10, []),
            block(11, [sign_new('p.near', 'p1', P)], ts=1_000_000_000),
            block(12, [respond('p.near', 'p1', P, ok=False)], ts=2_000_000_000),
            block(13, [respond('p.near', 'p1', P)], ts=4_000_000_000),
            block(14, []),
        ]
        r = N.completion(blocks, n_context=1, n_tail=1)
        self.assertEqual((r['evaluated'], r['matched'], r['censored'], r['failed_responses_seen']), (1, 1, 0, 1))
        self.assertAlmostEqual(r['median_delay_s'], 3.0)

    def test_old_form_pairs_on_domain_zero_whatever_key_version(self):
        blocks = [
            block(10, []),
            block(11, [sign_old('p.near', 'p1', bytes.fromhex(P), key_version=1)], ts=1_000_000_000),
            block(12, [respond('p.near', 'p1', P)], ts=2_000_000_000),
            block(13, []),
        ]
        r = N.completion(blocks, n_context=1, n_tail=1)
        self.assertEqual((r['evaluated'], r['matched']), (1, 1))

    def test_canonical_payload_across_encodings(self):
        # sign uses a byte-array payload (older form); respond uses a hex string -> must still pair
        payload_bytes = bytes(range(32))
        payload_hex = payload_bytes.hex()
        blocks = [
            block(10, []),
            block(11, [sign_old('p.near', 'p1', payload_bytes)], ts=1_000_000_000),
            block(12, [respond('p.near', 'p1', payload_hex, tweak_as_list=False)], ts=2_000_000_000),
            block(13, []),
        ]
        r = N.completion(blocks, n_context=1, n_tail=1)
        self.assertEqual((r['evaluated'], r['matched']), (1, 1))
        self.assertEqual(r['pairs'][0]['payload_hex'], payload_hex)


# --- fixture cases (real data) -------------------------------------------------------------------

@unittest.skipUnless(os.path.exists(CONTIG), 'contiguous fixture not fetched')
class TestFixtures(unittest.TestCase):
    def test_fixture_metadata(self):
        bl = N.load(CONTIG)
        self.assertGreater(len(bl), 0)
        self.assertEqual({b['part'] for b in bl}, {'contiguous'})

    def test_tweak_derivation_matches_real_responses(self):
        # for each real respond, a sign in the run with the same derived (payload, tweak, domain)
        # proves the SHA3-256 epsilon derivation is correct on real data.
        bl = N.load(CONTIG)
        sign_keys = set()
        for b in bl:
            for c in b.get('calls') or []:
                if c.get('method') == 'sign':
                    k = N._sign_key(c)
                    if k is not None:
                        sign_keys.add(k)
        matched_responds = 0
        for b in bl:
            for c in b.get('calls') or []:
                if c.get('method') == 'respond' and N._succeeded(c.get('status')):
                    if N._respond_key(c) in sign_keys:
                        matched_responds += 1
        self.assertGreater(matched_responds, 0,
                           'no respond tweak matched a derived sign tweak on real data')

    def test_completion_runs_on_fixture(self):
        bl = N.load(CONTIG)
        r = N.completion(bl)  # default 100/100
        self.assertGreater(r['evaluated'], 0)
        self.assertGreater(r['matched'], 0)
        self.assertIsNotNone(r['matched_share'])

    @unittest.skipUnless(os.path.exists(SCATTER), 'scatter fixture not fetched')
    def test_purpose_and_shares_run_on_scatter(self):
        bl = N.load(SCATTER)
        by_month, by_pred = N.purpose_by_month(bl)
        self.assertIn('2026-11', by_month)
        self.assertGreater(sum(by_month['2026-11'].values()), 0)


if __name__ == '__main__':
    unittest.main()
