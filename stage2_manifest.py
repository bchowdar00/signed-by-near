"""Stage-2 freeze manifest (METHOD §9): the analysis code, hashed before any counted row is read.

  python3 -I stage2_manifest.py <repo_dir> <out MANIFEST-stage2.txt>

First checks that every file in frozen/MANIFEST-stage1.txt is unchanged on disk (it fails if not),
then writes one line per file, "sha256  relative/path", sorted by path, LF endings: the stage-1
manifest (so the two stages chain; its .ots receipt is left out because upgrading it changes its
bytes), every file stage 1 froze, and
the stage-2 additions (DEVIATIONS.md, inputs/, analysis/, tests/ and all fixtures, this script).
That text file is what is submitted to OpenTimestamps (collector/ots.py stamp).
"""
import glob, hashlib, os, sys

STAGE1 = 'frozen/MANIFEST-stage1.txt'
REQUIRED = [STAGE1, 'DEVIATIONS.md', 'stage2_manifest.py', 'inputs/reference.json',
            'inputs/hsp007-ledger.json', 'inputs/make_reference.py', 'inputs/extract_hsp007.py',
            'analysis/core.py', 'analysis/measures.py', 'analysis/recompute.py', 'analysis/neardata.py',
            'analysis/hsp007.py', 'analysis/charts.py']
GLOBS = ['analysis/*.py', 'tests/*.py', 'tests/fixtures/**/*', 'inputs/*']


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def check_stage1(repo):
    bad = []
    with open(os.path.join(repo, STAGE1)) as f:
        lines = [l.split('  ', 1) for l in f.read().splitlines() if l.strip()]
    for h, rel in lines:
        p = os.path.join(repo, rel)
        if not os.path.isfile(p) or sha(p) != h:
            bad.append(rel)
    if bad:
        raise SystemExit('stage-1 files changed or missing: ' + ', '.join(bad))
    return [rel for _, rel in lines]


def files(repo):
    s1 = check_stage1(repo)
    missing = [f for f in REQUIRED if not os.path.isfile(os.path.join(repo, f))]
    if missing:
        raise SystemExit('missing: ' + ', '.join(missing))
    out = set(s1) | set(REQUIRED)
    for g in GLOBS:
        out.update(os.path.relpath(p, repo) for p in glob.glob(os.path.join(repo, g), recursive=True) if os.path.isfile(p))
    return sorted(p.replace(os.sep, '/') for p in out if '__pycache__' not in p)


def manifest(repo):
    return ''.join(f'{sha(os.path.join(repo, rel))}  {rel}\n' for rel in files(repo))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    txt = manifest(sys.argv[1])
    with open(sys.argv[2], 'w', newline='\n') as f:
        f.write(txt)
    print(f'{txt.count(chr(10))} files; manifest sha256 {hashlib.sha256(txt.encode()).hexdigest()}')
