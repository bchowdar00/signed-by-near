"""Run the independent re-derivation from a clone of this repository, offline.

    python3 -I rederive/run.py [data_dir] [--sources DIR]

The repository is the parent of the folder this file sits in. data_dir defaults to
<repo>/data. Sources (files that are NOT in the repository, e.g. the HSP-007 forum
JSON) are read from --sources DIR if given, else from <this folder>/sources if that
exists, else treated as absent. Scripts that need an absent source file are skipped,
together with everything downstream of them; the rows they would have produced are
reported by compare.py as "needs source file".

It runs the four families in order, copies each family's results.json to
out/<family>.json (and leaves everything else each family writes under out/<family>/),
runs the page-extras checks, then runs compare.py. Standard library + numpy only.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True  # no .pyc caches anywhere in the shipped tree

HERE = os.path.dirname(os.path.abspath(__file__))     # the rederive/ folder
REPO = os.path.dirname(HERE)                           # the repository root
PY = sys.executable

# Source files some scripts need but that are not shipped in the repository: name, URL and
# the sha256 of the copy saved on 2026-11-09 (sources.json, shared with compare.py).
import json
SOURCES = json.load(open(os.path.join(HERE, 'sources.json')))['files']


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


# Each family is an ordered list of steps. A step may require a source file (by name)
# and/or output files produced by earlier steps; if any required input is missing the
# step is skipped and its outputs never appear.
FAMILIES = {
    'c2b-m10': [
        ('d1_completion.py', None, [], ['d1_completion.json']),
        ('d2_transfers.py', None, [], ['d2_transfers.json']),
        ('d3_c2b.py', None, [], ['d3_c2b.json']),
        ('d4_m10.py', None, [], ['d4_m10.json']),
        ('d5_m10b.py', None, [], ['d5_m10b.json']),
        ('make_results.py', None, [], ['results.json']),
    ],
    'm9-m1': [
        ('run_d1.py', None, [], []),
        ('run_m9.py', None, [], ['m9_partial.json']),
        ('run_bychain.py', None, [], ['bychain.json']),
        ('run_m1.py', None, [], ['m1_census.json']),
        ('run_dominant.py', None, [], ['m1_dominant.json']),
        ('assemble.py', None, ['m9_partial.json', 'bychain.json', 'm1_census.json', 'm1_dominant.json'], ['results.json']),
    ],
    'm3-m8-m7': [
        ('sign_core.py', None, [], ['sign_cache.json']),
        ('m3.py', None, ['sign_cache.json'], ['m3_results.json']),
        ('hsp007.py', 'gov-hsp007-execution-42147.json', [], ['hsp007_ledger.json']),
        ('m8.py', None, ['sign_cache.json', 'hsp007_ledger.json'], ['m8_results.json']),
        ('m7.py', None, [], ['m7_results.json']),
        ('index_audit.py', None, [], ['index_results.json']),
        ('audit_check.py', None, ['index_results.json'], ['audit_check_results.json']),
        ('assemble.py', None, [], ['results.json']),
    ],
    'm4-m5-trend': [
        ('run.py', None, [], ['results.json']),
    ],
}


def run_family(fam, env, sources_dir, skipped):
    src_code = os.path.join(HERE, 'families', fam)
    work = os.path.join(HERE, 'out', fam)
    if os.path.isdir(work):
        shutil.rmtree(work)
    os.makedirs(work)
    # Stage the family's code in its own working directory so that its relative reads
    # and writes (and HERE = dirname(__file__)) all resolve inside out/<fam>/.
    for fn in os.listdir(src_code):
        if fn.endswith('.py'):
            shutil.copy2(os.path.join(src_code, fn), os.path.join(work, fn))
    print('\n=== family %s ===' % fam)
    for script, need_src, need_files, produces in FAMILIES[fam]:
        reason = None
        if need_src is not None and (sources_dir is None or
                                     not os.path.exists(os.path.join(sources_dir, need_src))):
            reason = 'missing source file %s' % need_src
        elif need_src is not None and sha256(os.path.join(sources_dir, need_src)) != SOURCES[need_src]['sha256']:
            reason = 'the copy of %s given is not the 2026-11-09 copy (sha256 differs)' % need_src
        else:
            for nf in need_files:
                if not os.path.exists(os.path.join(work, nf)):
                    reason = 'missing upstream output %s' % nf
                    break
        if reason is not None:
            print('  SKIP %-20s (%s)' % (script, reason))
            skipped.append((fam, script, need_src, reason))
            continue
        r = subprocess.run([PY, '-I', '-B', script], cwd=work, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if r.returncode != 0:
            sys.stderr.write(r.stderr.decode('utf-8', 'replace'))
            raise SystemExit('FAILED: %s/%s returned %d' % (fam, script, r.returncode))
        print('  ran  %s' % script)
    # publish the family's results
    res = os.path.join(work, 'results.json')
    if os.path.exists(res):
        shutil.copy2(res, os.path.join(HERE, 'out', fam + '.json'))
        print('  -> out/%s.json' % fam)
    else:
        print('  (no results.json produced for %s)' % fam)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data_dir', nargs='?', default=None)
    ap.add_argument('--sources', default=None)
    args = ap.parse_args()

    data_dir = os.path.abspath(args.data_dir) if args.data_dir else os.path.join(REPO, 'data')
    if args.sources:
        sources_dir = os.path.abspath(args.sources)
    elif os.path.isdir(os.path.join(HERE, 'sources')):
        sources_dir = os.path.join(HERE, 'sources')
        print('using bundled sources at %s' % os.path.relpath(sources_dir, REPO))
    else:
        sources_dir = None

    print('repo     :', REPO)
    print('data_dir :', data_dir)
    print('sources  :', sources_dir if sources_dir else '(none)')
    if not os.path.isdir(data_dir):
        raise SystemExit('data_dir not found: %s' % data_dir)

    env = dict(os.environ)
    env['RD_REPO'] = REPO
    env['RD_DATA'] = data_dir
    if sources_dir is not None:
        env['RD_SOURCES'] = sources_dir

    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    skipped = []
    for fam in ('c2b-m10', 'm9-m1', 'm3-m8-m7', 'm4-m5-trend'):
        run_family(fam, env, sources_dir, skipped)

    # page-extras checks (rows 53+); needs no source file
    print('\n=== checks/page_extras.py ===')
    pe_out = os.path.join(HERE, 'out', 'page_extras.json')
    r = subprocess.run([PY, '-I', '-B', os.path.join(HERE, 'checks', 'page_extras.py'),
                        REPO, data_dir, os.path.join(HERE, 'mc-seeds', 'vendor', 'f1'), pe_out],
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if r.returncode != 0:
        sys.stderr.write(r.stderr.decode('utf-8', 'replace'))
        raise SystemExit('FAILED: page_extras.py returned %d' % r.returncode)
    print('  -> out/page_extras.json')

    if skipped:
        print('\n=== skipped (missing source files) ===')
        for fam, script, need_src, reason in skipped:
            print('  %s/%s: %s' % (fam, script, reason))
            if need_src in SOURCES:
                s = SOURCES[need_src]
                print('     need %s' % need_src)
                print('       url    : %s' % s['url'])
                print('       sha256 : %s' % s['sha256'])

    # comparison. Flush our own stdout first so that, when stdout is a pipe or
    # file (block-buffered), compare.py's summary — which must be the last line —
    # is written after this banner rather than before it.
    print('\n=== compare.py ===')
    sys.stdout.flush()
    r = subprocess.run([PY, '-I', '-B', os.path.join(HERE, 'compare.py')], cwd=HERE, env=env)
    raise SystemExit(r.returncode)


if __name__ == '__main__':
    main()
