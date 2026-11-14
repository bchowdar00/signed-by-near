"""One results file for the write-up: the primary reading at the root, the extension's under one key (T-2).

  python3 -I publish/combine.py <primary out_dir> <out combined.json> [--audit <dest-audit.json>]
                                [<extended out_dir> <extension dir>]

Each out_dir is a publish/rule.py output folder; its published/results.json (the ruled results) is
read. This file is outside both frozen manifests and computes nothing: it copies values.

Without the last two arguments, "extension" is {"ran": false}. With them, "extension" holds:
  ran       true
  label     the label PLAN.md fixes for the secondary reading
  pass      the pass's own record from <extension dir>: selection.json and nb/DONE
  results   the extended reading's published results
  differs   every value path (results.json paths, "inputs" and "rule" left out) whose value is not the
            primary's, and n_differs, their count
  readings_completed, readings_still_not_completed
            the readings the rule masked in the primary that the extension completes, and those it
            leaves masked (by_month's repeated rows left out), with their counts
With --audit, publish/dest_audit.py's output is carried as "dest_audit", after a check that its picks
are the primary's dest_audit_selection (a stale audit stops the command).
THESIS.md takes its secondary numbers from the "extension" key only (THESIS.ext.tmpl.md), so they
are filled like every other number and never typed.
"""
import json, os, sys

LABEL = 'extension pass after the frozen deadline, by a plan stamped before that deadline'
SKIP = ('inputs', 'rule')


def _load(p):
    with open(p) as f:
        return json.load(f)


def differs(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if not path and k in SKIP:
                continue
            p = f'{path}/{k}' if path else k
            if k not in a or k not in b:
                out.append(p)
            else:
                out += differs(a[k], b[k], p)
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += differs(x, y, f'{path}/{i}')
        return out
    return [] if a == b else [path]


class StaleAudit(Exception):
    pass


def check_audit(primary, dest_audit):
    sel = primary.get('dest_audit_selection') or {}
    want = [p.get('receipt_id') for k in ('bitcoin', 'zcash') for p in sel.get(k, [])]
    got = [r.get('receipt_id') for r in dest_audit.get('rows', [])]
    if want != got:
        raise StaleAudit(f'the destination audit looked up {len(got)} picks that are not the {len(want)} '
                         'picks of these results: re-run publish/dest_audit.py')


def combine(primary, extended=None, ext_pass=None, dest_audit=None):
    out = dict(primary)
    if dest_audit is not None:
        check_audit(primary, dest_audit)
        out['dest_audit'] = dest_audit
    if extended is None:
        out['extension'] = {'ran': False}
        return out
    d = differs(primary, extended)
    mp = {m['path'] for m in primary['rule']['masked'] if not m['path'].startswith('by_month/')}
    me = {m['path'] for m in extended['rule']['masked'] if not m['path'].startswith('by_month/')}
    done, short = sorted(mp - me), sorted(mp & me)
    out['extension'] = {'ran': True, 'label': LABEL, 'pass': ext_pass or {}, 'results': extended,
                        'differs': d, 'n_differs': len(d),
                        'readings_completed': done, 'n_readings_completed': len(done),
                        'readings_still_not_completed': short, 'n_readings_still_not_completed': len(short)}
    return out


def main(primary_out, out_path, ext_out=None, ext_dir=None, audit=None):
    primary = _load(os.path.join(primary_out, 'published', 'results.json'))
    extended, ext_pass = None, None
    if ext_out:
        extended = _load(os.path.join(ext_out, 'published', 'results.json'))
        ext_pass = {'selection': _load(os.path.join(ext_dir, 'selection.json'))}
        with open(os.path.join(ext_dir, 'nb', 'DONE')) as f:
            ext_pass['done'] = json.loads(f.read())
    c = combine(primary, extended, ext_pass, _load(audit) if audit else None)
    with open(out_path, 'w') as f:
        json.dump(c, f, indent=1, sort_keys=True)
    e = c['extension']
    print(json.dumps({'extension_ran': e['ran'], 'n_differs': e.get('n_differs')}))
    return c


if __name__ == '__main__':
    a = sys.argv[1:]
    audit = None
    if '--audit' in a:
        i = a.index('--audit')
        audit, a = a[i + 1], a[:i] + a[i + 2:]
    if len(a) not in (2, 4):
        raise SystemExit(__doc__)
    main(*a, audit=audit)
