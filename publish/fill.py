"""Fills THESIS.md from the published results, so no number in it is typed by hand.

  python3 -I publish/fill.py <THESIS.tmpl.md> <combined.json> <out THESIS.md> [--final]

<combined.json> is publish/combine.py's output: the published (ruled) primary results at the root,
the extension pass's under "extension". This file is outside both frozen manifests. It uses the frozen
analysis/thesis_fill.py for the placeholder syntax ({{path::format}}), the path walk and every one of
its formats, and adds:

  iv1    a reading's interval, "[L, U]", each end in the pct1 format (from L and U, or lo and hi)
  a reading the rule masked (publish/rule.py): a null inside a node that carries "not_completed":
         true prints "not completed". Any other null, or a path that does not resolve, stops the
         command, as in the frozen fill: the write-up is never published with a hole in it.
  `<!-- extension:NAME -->` on a line of its own is replaced by block NAME of THESIS.ext.tmpl.md
         (beside the template): its "ran" part if combined["extension"]["ran"], else its "not ran"
         part. Without an "extension" key the command stops.
  `<!-- if completed: PATH, PATH -->` TEXT `<!-- otherwise -->` OTHER `<!-- end if -->`, each marker on
         a line of its own, keeps TEXT unless a listed reading is masked, and then keeps OTHER. So a
         sentence whose numbers the rule masks is replaced whole by one that says so, instead of reading
         "not completed" where a number stood. A listed path that does not resolve stops the command.

With --final, a ⟪ ⟫ sentence still in the output also stops it.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'analysis'))
import thesis_fill as TF  # noqa: E402

NC = 'not_completed'
WORDS = 'not completed'
MARKER = re.compile(r'\n*^<!-- extension:([a-z0-9_-]+) -->$\n*', re.M)
BLOCK = re.compile(r'<!-- block ([a-z0-9_-]+) -->\n<!-- ran -->\n(.*?)<!-- not ran -->\n(.*?)<!-- end -->', re.S)
IF = re.compile(r'^<!-- if completed: ([^\n]+?) -->\n(.*?)^<!-- otherwise -->\n(.*?)^<!-- end if -->\n', re.S | re.M)


class FillError(Exception):
    pass


def resolve(res, path):
    """The value at path, and whether any node on the way (or the value itself) is a masked reading."""
    cur, nc = res, False
    for part in path.strip().split('/'):
        if isinstance(cur, dict) and cur.get(NC):
            nc = True
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    if isinstance(cur, dict) and cur.get(NC):
        nc = True
    return cur, nc


def fmt(v, f):
    if v is None:
        return None
    if f == 'iv1':
        if not isinstance(v, dict):
            raise FillError('iv1 needs a reading')
        lo, hi = v.get('L', v.get('lo')), v.get('U', v.get('hi'))
        if lo is None or hi is None:
            return None
        return f"[{TF.fmt(lo, 'pct1')}, {TF.fmt(hi, 'pct1')}]"
    return None if v is None else TF.fmt(v, f)


def fill(text, res, mark=None):
    """Returns (filled text, holes). mark(s), if given, wraps each placeholder's output (for tests)."""
    holes = []

    def sub(m):
        path, f = m.group(1), m.group(2)
        try:
            v, nc = resolve(res, path)
        except (KeyError, IndexError, ValueError, TypeError):
            v, nc = None, False
        out = fmt(v, f)
        if out is None:
            if not nc:
                holes.append(m.group(0))
                return m.group(0)
            out = WORDS
        return mark(out) if mark else out

    return TF.PH.sub(sub, text), holes


def blocks(path):
    with open(path) as f:
        return {m.group(1): (m.group(2), m.group(3)) for m in BLOCK.finditer(f.read())}


def conditionals(text, res):
    def pick(m):
        masked = False
        for path in m.group(1).split(','):
            try:
                _, nc = resolve(res, path)
            except (KeyError, IndexError, ValueError, TypeError):
                raise FillError(f'"if completed" path does not resolve: {path.strip()}')
            masked = masked or nc
        if any(t in m.group(2) + m.group(3) for t in ('<!-- if completed:', '<!-- end if -->')) \
                or '<!-- otherwise -->' in m.group(3):
            raise FillError(f'an "if completed" block is malformed: {m.group(1).strip()}')
        return m.group(3) if masked else m.group(2)
    out = IF.sub(pick, text)
    if '<!-- if completed:' in out or '<!-- otherwise -->' in out or '<!-- end if -->' in out:
        raise FillError('an "if completed" block is malformed')
    return out


def expand(text, res, ext_path):
    names = MARKER.findall(text)
    if not names:
        return conditionals(text, res)
    if 'extension' not in res:
        raise FillError('the results have no "extension" key: run publish/combine.py first')
    ran = bool(res['extension'].get('ran'))
    B = blocks(ext_path)
    missing = [n for n in names if n not in B]
    if missing:
        raise FillError(f'no block {missing} in {os.path.basename(ext_path)}')
    def put(m):
        b = B[m.group(1)][0 if ran else 1].strip('\n')
        return f'\n\n{b}\n\n' if b else '\n\n'
    return conditionals(MARKER.sub(put, text), res)


def main(tmpl, combined, out, final=False):
    with open(tmpl) as f:
        text = f.read()
    with open(combined) as f:
        res = json.load(f)
    text = expand(text, res, os.path.join(os.path.dirname(os.path.abspath(tmpl)), 'THESIS.ext.tmpl.md'))
    filled, holes = fill(text, res)
    if holes:
        raise SystemExit('unresolved placeholders:\n' + '\n'.join(sorted(set(holes))))
    left = filled.count('⟪')
    if final and left:
        raise SystemExit(f'{left} ⟪ ⟫ sentence(s) still to write')
    with open(out, 'w') as f:
        f.write(filled)
    print(f'filled {len(TF.PH.findall(text))} placeholders into {out}; {left} ⟪ ⟫ sentence(s) still to write')


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if x != '--final']
    if len(a) != 3:
        raise SystemExit(__doc__)
    main(*a, final='--final' in sys.argv[1:])
