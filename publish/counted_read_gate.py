"""The gate in front of the first counted read (POST-FREEZE.md).

  python3 -I publish/counted_read_gate.py --at <UTC> --go <GO file> --manifest <manifest> --data <data_dir> --log <log>

It waits until --at, and never acts before 2026-11-13T11:00:00Z whatever --at says. Then, once:
  - No GO file: it reads nothing and runs nothing, logs HELD, and exits 3.
  - The GO file must hold exactly one 64-character hex string, and it must equal the sha256 of the
    manifest file; the manifest's OpenTimestamps receipt (<manifest>.ots) must exist; and every
    `<sha256>  <path>` line of the manifest (paths from the repository root) must match the file on
    disk. A listed file named MANIFEST-*.txt is a manifest too: its receipt must exist and its lines
    must match, and so on down (post-freeze -> deadline -> stage 2, which holds the frozen analysis
    code). If not, it reads nothing and runs nothing, logs REFUSED with the reason, and exits 4.
  - A manifest path outside the repository is refused before it is hashed; so is anything that stops
    the check itself (an unreadable file), with the reason. It also refuses if this script has changed
    on disk since it was armed, or if out/, audit/ or THESIS.md already exist (move them to the Trash).
  - The code that reads the rows (publish/rule.py, the frozen analysis it imports, publish/dest_audit.py,
    rebuild.py) is loaded only after the go is accepted, compiled from source (a fresh bytecode cache),
    so what runs is what the manifests checked.
  - Otherwise it runs, in order, logging each step with its time:
      1. publish/rule.py on the counted data into out/ (the frozen command, then the rule). The log
         line just before it is the time of the first counted read. A data directory with no
         nb/windows.jsonl fails here (the frozen command would read it as nothing completed).
      2. It logs the unfinished windows by family and the windows that have a completed line but fail
         the frozen gate (rule/completed_line_but_gate_unfinished).
      3. publish/dest_audit.py out audit: one keyless explorer call per pick, never NearBlocks.
      4. rebuild.py --draft: the same results again, then the combine and the fill (THESIS.md).
    It exits 0, or logs FAILED with the error at the first step that fails and exits 1.
It edits no stamped file. The time of the first counted read, and everything after it, goes into
AFTER-READ.md (never into POST-FREEZE.md, which the stamp covers), quoted from this log; the log itself is
not published, since it carries local paths.
"""
import argparse, datetime, hashlib, json, os, re, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SELF = os.path.abspath(__file__)
sys.path.insert(0, HERE)

NOT_BEFORE = datetime.datetime(2026, 11, 13, 11, 0, 0, tzinfo=datetime.timezone.utc)
INSTANTS = os.path.join(ROOT, 'frozen', 'instants.json')
HELD, REFUSED, FAILED, DONE = 3, 4, 1, 0
HEX64 = re.compile(r'\b[0-9a-f]{64}\b')


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(t):
    return t.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def _sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


SELF_SHA = _sha(SELF)   # this script as armed


class Log:
    def __init__(self, path, now=utc_now):
        self.path, self.now = path, now

    def __call__(self, event, detail=''):
        detail = ' | '.join(str(detail).splitlines())   # one event per line
        line = f'{_iso(self.now())}  {event}  {detail}'.rstrip()
        with open(self.path, 'a') as f:
            f.write(line + '\n')
            f.flush()
            os.fsync(f.fileno())
        print(line, flush=True)


def check_go(go_path, manifest_path, manifest_root=ROOT):
    """None if the GO file is absent; else (ok, reason)."""
    if not os.path.exists(go_path):
        return None
    with open(go_path) as f:
        named = HEX64.findall(f.read().lower())
    if len(named) != 1:
        return False, f'the GO file names {len(named)} sha256 values, not exactly one'
    if not os.path.exists(manifest_path):
        return False, 'the manifest file does not exist'
    actual = _sha(manifest_path)
    if actual != named[0]:
        return False, f'the GO file names {named[0]}, but the manifest on disk is {actual}'
    ok, why, n = check_lines(manifest_path, manifest_root, set())
    if not ok:
        return False, why
    return True, f'GO names the manifest {actual}; its {n} files, and those of the manifests it lists, match disk'


NESTED = re.compile(r'MANIFEST-[A-Za-z0-9_.-]+\.txt')


def check_lines(manifest_path, manifest_root, seen):
    """(ok, reason, files checked) for one manifest and every manifest it lists."""
    real = os.path.realpath(manifest_path)
    rel = os.path.relpath(real, os.path.realpath(manifest_root))
    if real in seen:       # already checked (a manifest reached twice); a loop is impossible, since each
        return True, '', 0  # manifest would have to hold the other's hash
    seen.add(real)
    if not os.path.isfile(manifest_path + '.ots'):
        return False, f'{rel} has no OpenTimestamps receipt (.ots) beside it', 0
    bad, n, top, nested = [], 0, os.path.realpath(manifest_root), []
    with open(manifest_path) as f:
        for line in f:
            if not line.strip():
                continue
            parts = line.split(None, 1)
            if len(parts) != 2 or not re.fullmatch(r'[0-9a-f]{64}', parts[0]):
                return False, f'{rel} has a malformed line: {line.strip()[:80]}', 0
            h, p = parts[0], parts[1].strip()
            full = os.path.realpath(os.path.join(manifest_root, p))
            if not full.startswith(top + os.sep):      # never hash (read) a file outside the repository
                return False, f'{rel} lists a path outside the repository: {p}', 0
            n += 1
            if not os.path.isfile(full):
                bad.append(f'{p} (missing)')
            elif _sha(full) != h:
                bad.append(p)
            elif NESTED.fullmatch(os.path.basename(full)):
                nested.append(full)
    if n == 0:
        return False, f'{rel} lists no files', 0
    if bad:
        return False, f'{len(bad)} of {n} files in {rel} differ from disk: ' + ', '.join(bad[:10]), 0
    for m in nested:
        ok, why, k = check_lines(m, manifest_root, seen)
        if not ok:
            return False, why, 0
        n += k
    return True, '', n


def run(at, go, manifest, data, log_path, out='out', audit='audit', thesis='THESIS.md',
        get=None, sleep=time.sleep, now=utc_now, not_before=NOT_BEFORE, manifest_root=ROOT):
    out, audit, thesis = (os.path.join(ROOT, p) if not os.path.isabs(p) else p for p in (out, audit, thesis))
    go, manifest, data, log_path = (os.path.abspath(p) for p in (go, manifest, data, log_path))
    log = Log(log_path, now)
    target = max(at, not_before) if not_before else at
    log('ARMED', f'acts at {_iso(target)}; GO file {go}; manifest {manifest}')
    while now() < target:
        sleep(min(60.0, max(0.05, (target - now()).total_seconds())))
    try:
        g = check_go(go, manifest, manifest_root)
        if g is not None and g[0] and _sha(SELF) != SELF_SHA:
            g = (False, 'the gate script changed on disk after it was armed')
    except Exception as e:
        g = (False, f'the go could not be checked ({type(e).__name__}: {e})')
    if g is None:
        log('HELD', 'no GO file: nothing read, nothing run')
        return HELD
    ok, why = g
    if ok:
        there = [p for p in (out, audit, thesis) if os.path.exists(p)]
        if there:
            ok, why = False, f'{there[0]} already exists (move it to the Trash first)'
    if not ok:
        log('REFUSED', why + ': nothing read, nothing run')
        return REFUSED
    log('GO', why)
    try:
        import tempfile
        sys.pycache_prefix = tempfile.mkdtemp(prefix='gate-pycache-')   # no bytecode cached before the check
        import rule, dest_audit   # loaded now, after the check, from the files it checked
        get = get or dest_audit.http_get
        log('FIRST-COUNTED-READ', f'step 1, publish/rule.py on {data}')
        if not os.path.isfile(os.path.join(data, 'nb', 'windows.jsonl')):   # the frozen command runs on an
            raise FileNotFoundError(f'no nb/windows.jsonl under {data}')     # empty directory, so check first
        R = rule.run(INSTANTS, data, out)['rule']
        log('STEP1-DONE', json.dumps({'unfinished_windows': R['unfinished_windows'],
                                      'masked_readings': R['n_masked_readings']}))
        log('STEP2', json.dumps({'unfinished_by_family': R['unfinished_by_family'],
                                 'completed_line_but_gate_unfinished': R['completed_line_but_gate_unfinished']}))
        log('STEP3', 'publish/dest_audit.py: one keyless explorer call per pick')
        dest_audit.main(out, audit, get=get, sleep=sleep)
        with open(os.path.join(audit, 'dest-audit.json')) as f:
            log('STEP3-DONE', json.dumps(json.load(f)['summary']))
        log('STEP4', 'rebuild.py --draft')
        import importlib.util
        spec = importlib.util.spec_from_file_location('rebuild', os.path.join(ROOT, 'rebuild.py'))
        rb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rb)
        rb.rebuild(data, out=out, audit=audit, thesis=thesis, draft=True)
        log('DONE', f'steps 1-4 ran; THESIS draft at {thesis}')
        return DONE
    except BaseException as e:   # SystemExit included: log it, stop, and say so
        log('FAILED', f'{type(e).__name__}: {e}')
        for line in traceback.format_exc().strip().splitlines():
            log('TRACE', line)
        return FAILED


def _parse_at(s):
    return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--at', required=True, type=_parse_at)
    ap.add_argument('--go', required=True)
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--data', required=True)
    ap.add_argument('--log', required=True)
    a = ap.parse_args()
    sys.exit(run(a.at, a.go, a.manifest, a.data, a.log))
