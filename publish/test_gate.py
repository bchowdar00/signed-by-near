"""Tests for publish/counted_read_gate.py, on synthetic data only (no counted row, no network).

  python3 -I -m unittest discover -s publish -p 'test_gate.py'

Both ways: with no GO file the gate holds and reads nothing; with a GO file that names the stamped
manifest, and a manifest that matches disk, it runs steps 1-4 on tests/simulate.py's rows; a wrong
hash, a changed file, a missing receipt or a malformed GO file is refused and nothing is read. The
clock and the explorer are injected.
"""
import datetime, hashlib, json, os, shutil, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for d in (HERE, os.path.join(ROOT, 'tests')):
    sys.path.insert(0, d)
import simulate  # noqa: E402
import counted_read_gate as G  # noqa: E402
import rule  # noqa: E402  (the module the gate imports after the go, so the spy below reaches it)
import dest_audit  # noqa: E402

INSTANTS = os.path.join(ROOT, 'frozen', 'instants.json')
FIX = os.path.join(HERE, 'fixtures')
UTC = datetime.timezone.utc
T0 = datetime.datetime(2026, 11, 13, 10, 59, 0, tzinfo=UTC)


def sha(p):
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


class Clock:
    """A fake clock: sleep() moves it forward."""
    def __init__(self, t):
        self.t, self.slept = t, []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += datetime.timedelta(seconds=s)


class Explorer:
    """Every BITCOIN lookup is not found (404); every ZCASH lookup is an empty Blockchair answer."""
    def __init__(self):
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        if 'mempool' in url:
            return 404, open(os.path.join(FIX, 'btc-missing.json'), 'rb').read()
        return 200, open(os.path.join(FIX, 'zec-missing.json'), 'rb').read()


class TestGate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.data = os.path.join(cls.tmp, 'synthetic')
        simulate.simulate(INSTANTS, cls.data, seed=11)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def setUp(self):
        self.d = tempfile.mkdtemp(dir=self.tmp)
        self.root = os.path.join(self.d, 'repo')          # a stand-in for the files the manifest lists
        os.makedirs(os.path.join(self.root, 'publish'))
        for p, body in (('POST-FREEZE.md', 'record\n'), ('publish/rule.py', 'rule\n')):
            with open(os.path.join(self.root, p), 'w') as f:
                f.write(body)
        self.manifest = os.path.join(self.root, 'MANIFEST-postfreeze.txt')
        with open(self.manifest, 'w') as f:
            for p in ('POST-FREEZE.md', 'publish/rule.py'):
                f.write(f'{sha(os.path.join(self.root, p))}  {p}\n')
        with open(self.manifest + '.ots', 'wb') as f:
            f.write(b'\x00OpenTimestamps receipt stand-in')
        self.go = os.path.join(self.d, 'GO-COUNTED-READ')
        self.log = os.path.join(self.d, 'gate.log')
        self.out, self.audit, self.thesis = (os.path.join(self.d, p) for p in ('out', 'audit', 'THESIS.md'))
        self.explorer, self.clock = Explorer(), Clock(T0)
        self.reads = []
        real = rule.run

        def spy(instants, data, out):            # records each read of the rows, and what the log said first
            self.reads.append((data, self.lines()[-1].split('  ')[1]))
            return real(instants, data, out)
        rule.run = spy
        self.addCleanup(setattr, rule, 'run', real)

    def write_go(self, text):
        with open(self.go, 'w') as f:
            f.write(text)

    def lines(self):
        with open(self.log) as f:
            return [l.rstrip('\n') for l in f]

    def events(self):
        return [l.split('  ')[1] for l in self.lines()]

    def gate(self, at=None, data=None):
        return G.run(at or T0 + datetime.timedelta(seconds=30), self.go, self.manifest, data or self.data, self.log,
                     out=self.out, audit=self.audit, thesis=self.thesis, get=self.explorer, sleep=self.clock.sleep,
                     now=self.clock.now, not_before=T0 + datetime.timedelta(seconds=30), manifest_root=self.root)

    def assert_nothing_ran(self):
        self.assertEqual(self.reads, [])
        self.assertEqual(self.explorer.urls, [])
        for p in (self.out, self.audit, self.thesis):
            self.assertFalse(os.path.exists(p), p)

    # --- no GO file: hold ---
    def test_no_go_file_holds_and_reads_nothing(self):
        self.assertEqual(self.gate(), G.HELD)
        self.assertEqual(self.events(), ['ARMED', 'HELD'])
        self.assert_nothing_ran()

    # --- GO file present and right: run steps 1-4 ---
    def test_go_naming_the_manifest_runs_steps_1_to_4(self):
        self.write_go(f'go: the manifest is {sha(self.manifest)}\n')
        self.assertEqual(self.gate(), G.DONE)
        self.assertEqual(self.events(), ['ARMED', 'GO', 'FIRST-COUNTED-READ', 'STEP1-DONE', 'STEP2', 'STEP3',
                                         'STEP3-DONE', 'STEP4', 'DONE'])
        # The first read of the rows comes after the FIRST-COUNTED-READ line; rebuild reads them again.
        self.assertEqual(self.reads, [(self.data, 'FIRST-COUNTED-READ'), (self.data, 'STEP4')])
        for p in ('published/results.json', 'published/tables.md', 'combined.json'):
            self.assertTrue(os.path.exists(os.path.join(self.out, p)), p)
        self.assertTrue(os.path.exists(os.path.join(self.audit, 'dest-audit.json')))
        self.assertTrue(os.path.exists(self.thesis))
        with open(os.path.join(self.out, 'published', 'results.json')) as f:
            sel = json.load(f)['dest_audit_selection']
        picks = [p for k in ('bitcoin', 'zcash') for p in sel[k]]
        looked_up = [p for p in picks if isinstance(p.get('dest_txn'), str) and dest_audit.TXID.fullmatch(p['dest_txn'])]
        self.assertEqual(len(self.explorer.urls), len(looked_up))
        self.assertLessEqual(len(self.explorer.urls), 20)
        self.assertFalse(any('nearblocks' in u for u in self.explorer.urls))
        step2 = json.loads(next(l for l in self.lines() if '  STEP2  ' in l).split('  STEP2  ')[1])
        self.assertIn('completed_line_but_gate_unfinished', step2)

    def test_it_acts_at_the_later_of_at_and_not_before(self):
        self.write_go(sha(self.manifest))
        self.gate(at=T0 - datetime.timedelta(hours=1))      # an --at in the past does not bring it forward
        first_check = next(l for l in self.lines() if '  GO  ' in l)
        self.assertGreaterEqual(first_check[:24], '2026-11-13T10:59:30.000Z')
        self.assertGreater(sum(self.clock.slept[:2]), 0)

    def test_the_cut_is_11_00_utc_on_13_november(self):
        self.assertEqual(G.NOT_BEFORE, datetime.datetime(2026, 11, 13, 11, 0, 0, tzinfo=UTC))

    def test_a_failing_step_is_logged_and_stops(self):
        self.write_go(sha(self.manifest))
        self.assertEqual(self.gate(data=os.path.join(self.d, 'no-such-rows')), G.FAILED)
        ev = self.events()
        self.assertEqual(ev[:4], ['ARMED', 'GO', 'FIRST-COUNTED-READ', 'FAILED'])
        self.assertEqual(set(ev[4:]), {'TRACE'})
        self.assertIn('no nb/windows.jsonl', self.lines()[3])
        self.assertEqual(self.reads, [])
        self.assertEqual(self.explorer.urls, [])

    def test_a_multi_line_message_stays_on_one_log_line(self):
        log = G.Log(self.log, self.clock.now)
        log('FAILED', 'unresolved placeholders:\n{{a}}\n{{b}}')
        self.assertEqual(self.lines(), ['2026-11-13T10:59:00.000Z  FAILED  unresolved placeholders: | {{a}} | {{b}}'])

    # --- GO file present but wrong: refuse ---
    def refused(self, why):
        self.assertEqual(self.gate(), G.REFUSED)
        self.assertEqual(self.events(), ['ARMED', 'REFUSED'])
        self.assertIn(why, self.lines()[-1])
        self.assert_nothing_ran()

    def test_wrong_hash_is_refused(self):
        self.write_go('0' * 64)
        self.refused('but the manifest on disk is')

    def test_a_changed_file_is_refused(self):
        self.write_go(sha(self.manifest))
        with open(os.path.join(self.root, 'publish', 'rule.py'), 'a') as f:
            f.write('# edited after the stamp\n')
        self.refused('1 of 2 files in MANIFEST-postfreeze.txt differ from disk: publish/rule.py')

    def test_a_missing_file_is_refused(self):
        self.write_go(sha(self.manifest))
        os.remove(os.path.join(self.root, 'POST-FREEZE.md'))
        self.refused('POST-FREEZE.md (missing)')

    def test_a_changed_manifest_is_refused(self):
        self.write_go(sha(self.manifest))
        with open(self.manifest, 'a') as f:
            f.write(f'{"1" * 64}  extra.txt\n')
        self.refused('but the manifest on disk is')

    def test_no_receipt_is_refused(self):
        self.write_go(sha(self.manifest))
        os.remove(self.manifest + '.ots')
        self.refused('no OpenTimestamps receipt')

    def test_an_empty_go_file_is_refused(self):
        self.write_go('go\n')
        self.refused('names 0 sha256 values')

    def test_two_hashes_are_refused(self):
        self.write_go(f'{sha(self.manifest)}\n{"2" * 64}\n')
        self.refused('names 2 sha256 values')

    def test_a_malformed_manifest_is_refused(self):
        with open(self.manifest, 'a') as f:
            f.write('not a hash line\n')
        self.write_go(sha(self.manifest))
        self.refused('malformed line')

    def test_an_empty_manifest_is_refused(self):
        open(self.manifest, 'w').close()
        self.write_go(sha(self.manifest))
        self.refused('MANIFEST-postfreeze.txt lists no files')

    def write_manifest(self, *lines):
        with open(self.manifest, 'w') as f:
            f.writelines(lines)
        self.write_go(sha(self.manifest))

    def test_a_path_outside_the_root_is_refused(self):     # F2: hashing it would read before the logged read
        outside = os.path.join(self.d, 'outside.txt')
        with open(outside, 'w') as f:
            f.write('x\n')
        self.write_manifest(f'{sha(outside)}  ../outside.txt\n')
        self.refused('outside the repository')
        self.write_manifest(f'{sha(outside)}  {outside}\n')
        os.remove(self.log)
        self.refused('outside the repository')

    def test_an_unreadable_manifest_is_refused_with_a_reason(self):   # F3
        with open(self.manifest, 'wb') as f:
            f.write(b'\xff\xfe not text\n')
        self.write_go(sha(self.manifest))
        self.refused('could not be checked')

    def test_a_go_path_that_is_a_directory_is_refused_with_a_reason(self):   # F3
        os.makedirs(self.go)
        self.refused('could not be checked')

    def test_a_gate_file_gone_after_arming_is_refused_with_a_reason(self):   # D1
        self.write_go(sha(self.manifest))
        real = G.SELF
        G.SELF = os.path.join(self.d, 'moved-away.py')
        self.addCleanup(setattr, G, 'SELF', real)
        self.refused('could not be checked (FileNotFoundError')

    def test_the_row_code_compiles_from_source(self):   # no bytecode cached before the check is used
        self.write_go(sha(self.manifest))
        real = sys.pycache_prefix
        self.addCleanup(setattr, sys, 'pycache_prefix', real)
        self.assertEqual(self.gate(), G.DONE)
        self.assertTrue(sys.pycache_prefix and sys.pycache_prefix.startswith(tempfile.gettempdir()))

    def test_the_gate_refuses_if_it_changed_after_it_was_armed(self):   # F1
        self.write_go(sha(self.manifest))
        real = G.SELF_SHA
        G.SELF_SHA = '0' * 64
        self.addCleanup(setattr, G, 'SELF_SHA', real)
        self.refused('the gate script changed on disk after it was armed')

    def test_earlier_outputs_are_refused(self):
        self.write_go(sha(self.manifest))
        os.makedirs(os.path.join(self.out, 'published'))
        self.assertEqual(self.gate(), G.REFUSED)
        self.assertIn('already exists', self.lines()[-1])
        self.assertEqual(self.reads, [])
        self.assertEqual(self.explorer.urls, [])

    def test_relative_paths_are_made_absolute_and_logged(self):   # F4
        here = os.getcwd()
        os.chdir(self.d)
        self.addCleanup(os.chdir, here)
        G.run(T0, 'GO-COUNTED-READ', self.manifest, self.data, 'gate.log', out=self.out, audit=self.audit,
              thesis=self.thesis, get=self.explorer, sleep=self.clock.sleep, now=self.clock.now, not_before=T0,
              manifest_root=self.root)
        self.assertIn(f"GO file {os.path.join(os.getcwd(), 'GO-COUNTED-READ')};", self.lines()[0])
        self.assertEqual(self.events(), ['ARMED', 'HELD'])

    def nested(self):
        """The top manifest lists a stamped inner manifest, which lists frozen/code.py."""
        os.makedirs(os.path.join(self.root, 'frozen'))
        code = os.path.join(self.root, 'frozen', 'code.py')
        with open(code, 'w') as f:
            f.write('frozen\n')
        inner = os.path.join(self.root, 'frozen', 'MANIFEST-stage2.txt')
        with open(inner, 'w') as f:
            f.write(f'{sha(code)}  frozen/code.py\n')
        with open(inner + '.ots', 'wb') as f:
            f.write(b'receipt')
        with open(self.manifest, 'a') as f:
            f.write(f'{sha(inner)}  frozen/MANIFEST-stage2.txt\n')
        self.write_go(sha(self.manifest))
        return code, inner

    def test_manifests_it_lists_are_checked_too(self):
        self.nested()
        ok, why = G.check_go(self.go, self.manifest, self.root)
        self.assertTrue(ok, why)
        self.assertIn('its 4 files', why)

    def test_a_changed_file_in_an_inner_manifest_is_refused(self):
        code, _ = self.nested()
        with open(code, 'a') as f:
            f.write('# edited\n')
        self.refused('1 of 1 files in frozen/MANIFEST-stage2.txt differ from disk: frozen/code.py')

    def test_an_inner_manifest_without_a_receipt_is_refused(self):
        _, inner = self.nested()
        os.remove(inner + '.ots')
        self.refused('frozen/MANIFEST-stage2.txt has no OpenTimestamps receipt')

    def test_the_real_chain_verifies(self):
        """The repository's own deadline and stage-2 manifests verify through the same check."""
        ok, why, n = G.check_lines(os.path.join(ROOT, 'deadline', 'MANIFEST-deadline.txt'), ROOT, set())
        self.assertTrue(ok, why)
        self.assertEqual(n, 4 + 75 + 33)          # deadline, then stage 2, then stage 1 (round 3, R2)

    def test_a_manifest_reached_twice_is_checked_once(self):   # round 3, R1: a diamond is not a loop
        code, inner = self.nested()
        outer = os.path.join(self.root, 'frozen', 'MANIFEST-stage3.txt')
        with open(outer, 'w') as f:
            f.write(f'{sha(inner)}  frozen/MANIFEST-stage2.txt\n')
        with open(outer + '.ots', 'wb') as f:
            f.write(b'receipt')
        with open(self.manifest, 'a') as f:
            f.write(f'{sha(outer)}  frozen/MANIFEST-stage3.txt\n')
        self.write_go(sha(self.manifest))
        ok, why = G.check_go(self.go, self.manifest, self.root)
        self.assertTrue(ok, why)
        self.assertIn('its 6 files', why)    # 4 top lines, 1 in stage 3, frozen/code.py once

    # --- the command line ---
    def test_the_rule_code_is_loaded_only_after_the_go(self):   # F1: no code that reads rows is loaded when armed
        code = ('import sys; sys.path.insert(0, %r); import counted_read_gate; '
                'print(sorted(m for m in ("rule", "dest_audit", "recompute", "core", "combine", "fill") if m in sys.modules))'
                % HERE)
        r = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.stdout.strip(), '[]', r.stderr)

    def test_the_script_loads_under_isolated_mode(self):
        r = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'counted_read_gate.py'), '--help'],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('--manifest', r.stdout)


if __name__ == '__main__':
    unittest.main()
