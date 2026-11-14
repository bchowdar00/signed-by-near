import hashlib, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import stage1_manifest  # noqa: E402


class TestManifest(unittest.TestCase):
    def make_repo(self):
        d = tempfile.mkdtemp(prefix='manifest-test-')
        self.addCleanup(shutil.rmtree, d)
        for rel in stage1_manifest.REQUIRED + ['collector/a.py', 'analysis/b.py', 'tests/test_c.py',
                                                'tests/fixtures/f.json']:
            p = os.path.join(d, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w') as f:
                f.write(rel)
        return d

    def test_deterministic_sorted_and_correct(self):
        d = self.make_repo()
        a, b = stage1_manifest.manifest(d), stage1_manifest.manifest(d)
        self.assertEqual(a, b)
        paths = [line.split('  ', 1)[1] for line in a.splitlines()]
        self.assertEqual(paths, sorted(paths))
        line = [l for l in a.splitlines() if l.endswith('  METHOD.md')][0]
        self.assertEqual(line.split()[0], hashlib.sha256(b'METHOD.md').hexdigest())

    def test_missing_required_file_fails(self):
        d = self.make_repo()
        os.remove(os.path.join(d, 'frozen/instants.json'))
        with self.assertRaises(SystemExit):
            stage1_manifest.manifest(d)


if __name__ == '__main__':
    unittest.main()
