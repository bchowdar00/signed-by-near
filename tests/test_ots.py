import hashlib, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'collector'))
import ots

REF = os.path.expanduser('~/Data/hackathons/near-2026/b-collect/ots-reference/hello-world.txt.ots')


class TestOts(unittest.TestCase):
    def test_varuint(self):
        for n in (0, 1, 127, 128, 300, 2**32 + 7):
            self.assertEqual(ots.Reader(ots.varuint(n)).varuint(), n)

    @unittest.skipUnless(os.path.exists(REF), 'reference example not present')
    def test_reference_example_round_trip(self):
        data = open(REF, 'rb').read()
        digest, tree = ots.parse_file(data)
        self.assertEqual(digest.hex(), '03ba204e50d126e4674c005e04d82e84c21366780af1f43bd54a37816b6ab340')
        self.assertEqual(ots.file_bytes(digest, tree), data)
        bt = [a for _, a in ots.attestations(tree) if a['kind'] == 'bitcoin']
        self.assertEqual([a['height'] for a in bt], [358391])
        # the attested message is block 358391's Merkle root, byte-reversed (checked online by `ots.py verify`)
        self.assertEqual(bt[0]['msg'][::-1].hex(), '8a1b66ecb7cbd07d8139a7e7d7f2c41aab1f5009b8364aaf61d03ad245e47e00')

    def test_hand_built_proof_parses(self):
        digest = hashlib.sha256(b'x').digest()
        n1, n2 = b'\x01' * 16, b'\x02' * 16
        pend = lambda uri: b'\x00' + ots.PENDING + ots.varbytes(ots.varbytes(uri))
        body1 = pend(b'https://a.example')
        body2 = b'\xf1' + ots.varbytes(b'pre') + b'\x08' + pend(b'https://b.example')
        out = ots.MAGIC + b'\x01\x08' + digest + b'\xff\xf0' + ots.varbytes(n1) + b'\x08' + body1 + \
            b'\xf0' + ots.varbytes(n2) + b'\x08' + body2
        d2, tree = ots.parse_file(out)
        att = [a for _, a in ots.attestations(tree)]
        self.assertEqual(sorted(a['uri'] for a in att), ['https://a.example', 'https://b.example'])
        m1 = hashlib.sha256(digest + n1).digest()
        self.assertIn(m1, [a['msg'] for a in att])
        m2 = hashlib.sha256(b'pre' + hashlib.sha256(digest + n2).digest()).digest()
        self.assertIn(m2, [a['msg'] for a in att])
        self.assertEqual(ots.file_bytes(d2, tree), out)


if __name__ == '__main__':
    unittest.main()
