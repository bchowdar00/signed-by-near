"""One command that rebuilds every number, table and chart of the write-up from the saved rows, offline.

  python3 -I rebuild.py <data_dir> [--draft] [--ext <merged_data_dir> <extension_dir>]

It makes no network call, and writes out/, out-ext/ (with --ext), out/combined.json and THESIS.md, whose
links assume those places. Without --draft it first checks that no sentence is still to be written, so
it never leaves out/ newer than THESIS.md. In order:
  1. publish/rule.py: the frozen command (analysis/recompute.py) into out/, published there unchanged,
     then the rule for readings not completed into out/published/ (POST-FREEZE.md).
  2. With --ext, the same for the extension pass's merged rows into out-ext/ (the secondary reading).
  3. publish/combine.py: one results file, out/combined.json, with the saved destination-audit
     lookups (audit/dest-audit.json, written by publish/dest_audit.py), checked against the picks.
  4. publish/fill.py: THESIS.md from THESIS.tmpl.md. Without --draft it stops if a sentence still
     to be written remains.
"""
import argparse, hashlib, json, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'publish'))
import rule  # noqa: E402
import combine  # noqa: E402
import fill  # noqa: E402

INSTANTS = os.path.join(ROOT, 'frozen', 'instants.json')


def _sha(p):
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def rebuild(data_dir, out='out', audit='audit', thesis='THESIS.md', ext=None, draft=False):
    out, audit, thesis = (os.path.join(ROOT, p) if not os.path.isabs(p) else p for p in (out, audit, thesis))
    tmpl = os.path.join(ROOT, 'THESIS.tmpl.md')
    with open(tmpl) as f:
        if not draft and '⟪' in f.read():
            raise SystemExit('THESIS.tmpl.md still has sentences to write: rebuild with --draft')
    R = rule.run(INSTANTS, data_dir, out)
    audit_json = os.path.join(audit, 'dest-audit.json')
    if not os.path.exists(audit_json):
        raise SystemExit(f'no saved destination audit at {audit_json}: run '
                         f'python3 -I publish/dest_audit.py {out} {audit} (one keyless explorer call per pick), '
                         'then rebuild again')
    ext_out = ext_dir = None
    if ext:
        ext_out, ext_dir = out.rstrip('/') + '-ext', ext[1]
        rule.run(INSTANTS, ext[0], ext_out)
    combined = os.path.join(out, 'combined.json')
    combine.main(out, combined, ext_out, ext_dir, audit=audit_json)
    fill.main(tmpl, combined, thesis, final=not draft)
    made = [os.path.join(out, 'published', f) for f in ('results.json', 'tables.md', 'chart1-routes.svg',
                                                        'chart2-callers-cost.svg')] + [combined, thesis]
    r = R['rule']
    print(json.dumps({'unfinished_windows': r['unfinished_windows'], 'masked_readings': r['n_masked_readings'],
                      'files': {os.path.relpath(p, ROOT): _sha(p) for p in made}}, indent=1))
    return R


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('data_dir')
    ap.add_argument('--draft', action='store_true')
    ap.add_argument('--ext', nargs=2, metavar=('MERGED_DATA_DIR', 'EXTENSION_DIR'))
    a = ap.parse_args()
    rebuild(a.data_dir, ext=a.ext, draft=a.draft)
