"""Stage-1 freeze manifest (METHOD §9, §10). Hashes the frozen files from disk; nothing is typed.

  python3 -I stage1_manifest.py <repo_dir> <out MANIFEST-stage1.txt>

Writes one line per file, "sha256  relative/path", sorted by path, LF endings. That text file is
what is submitted to OpenTimestamps (collector/ots.py stamp). Anyone with the repository can rerun
this command and compare: the same files give the same bytes.

Required (the command fails if any is missing): METHOD.md, frozen/instants.json,
frozen/nd_plan.json, frozen/rates.json, frozen/tokens.json, frozen/reach-sim.json,
registry/callers.json, run.sh, verify.py, stage1_manifest.py, collector/*.py, analysis/*.py,
tests/*.py and tests/fixtures/*.
"""
import glob, hashlib, os, sys

REQUIRED = ['METHOD.md', 'frozen/instants.json', 'frozen/nd_plan.json', 'frozen/rates.json',
            'frozen/tokens.json', 'frozen/reach-sim.json', 'registry/callers.json', 'run.sh', 'verify.py',
            'stage1_manifest.py']
GLOBS = ['collector/*.py', 'analysis/*.py', 'tests/*.py', 'tests/fixtures/*']


def files(repo):
    missing = [f for f in REQUIRED if not os.path.isfile(os.path.join(repo, f))]
    if missing:
        raise SystemExit('missing: ' + ', '.join(missing))
    out = set(REQUIRED)
    for g in GLOBS:
        hits = [os.path.relpath(p, repo) for p in glob.glob(os.path.join(repo, g)) if os.path.isfile(p)]
        if not hits:
            raise SystemExit(f'no files for {g}')
        out.update(hits)
    return sorted(p.replace(os.sep, '/') for p in out)


def manifest(repo):
    lines = []
    for rel in files(repo):
        with open(os.path.join(repo, rel), 'rb') as f:
            lines.append(f'{hashlib.sha256(f.read()).hexdigest()}  {rel}\n')
    return ''.join(lines)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    txt = manifest(sys.argv[1])
    with open(sys.argv[2], 'w', newline='\n') as f:
        f.write(txt)
    print(f'{txt.count(chr(10))} files; manifest sha256 {hashlib.sha256(txt.encode()).hexdigest()}')
