"""Compares a rebuilt out/ with another one, for example the committed one with a fresh rebuild.

  python3 -I publish/same_out.py <out_a> <out_b>

The tables and the charts must be the same bytes. The three results files (results.json, published/results.json,
combined.json) are the same bytes except for the order of one list, M7/pairs: the frozen code builds it by
looping over a set of strings (analysis/neardata.py, the loop over `keys`), and Python orders such a set by a
hash it seeds anew for each process. So those three files get a different sha256 on every run, while every
reading in them is the same. This command sorts that one list on both sides and then requires equality.
It exits non-zero on any difference. It reads only, and is in no manifest.
"""
import json, os, sys

sys.dont_write_bytecode = True
BYTES = ('tables.md', 'chart1-routes.svg', 'chart2-callers-cost.svg', 'published/tables.md',
         'published/chart1-routes.svg', 'published/chart2-callers-cost.svg')
RESULTS = ('results.json', 'published/results.json', 'combined.json')


def load(p):
    with open(p) as f:
        r = json.load(f)
    n = len(r['M7']['pairs'])
    r['M7']['pairs'] = sorted(r['M7']['pairs'], key=lambda x: json.dumps(x, sort_keys=True))
    return r, n


def main(a, b):
    bad = []
    for name in BYTES:
        with open(os.path.join(a, name), 'rb') as f, open(os.path.join(b, name), 'rb') as g:
            if f.read() != g.read():
                bad.append(name)
    for name in RESULTS:
        (ra, na), (rb, nb) = load(os.path.join(a, name)), load(os.path.join(b, name))
        if ra != rb:
            bad.append(name)
        print(f'{name}: equal once M7/pairs ({na} rows) is sorted' if ra == rb else f'{name}: DIFFERS')
    if bad:
        raise SystemExit('different: ' + ', '.join(bad))
    print(f'ok: {len(BYTES)} files are the same bytes, and {len(RESULTS)} results files are equal up to the order of M7/pairs')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
