"""Plants two faults and checks that publish/written.py catches each. It changes no file of the repository.

  python3 -I publish/selftest_written.py <data_dir>

1. A wrong count: one count the page states in words is changed in a copy of THESIS.md, and
   publish/check_thesis.py must report it.
2. A masked reading: in a copy of out/combined.json a reading that a written sentence shows (M9/p, Omni's share
   of the measured value) is marked not completed, as publish/rule.py marks one, and publish/written.py must
   stop with a non-zero exit and write no page.
"""
import contextlib, io, json, os, sys, tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fill  # noqa: E402
import check_thesis  # noqa: E402
import written  # noqa: E402


def main(data_dir):
    with open(os.path.join(ROOT, 'out', 'combined.json')) as f:
        R = json.load(f)
    with open(os.path.join(ROOT, 'THESIS.md')) as f:
        page = f.read()
    D, bad = check_thesis.check(R, page, data_dir)
    assert not bad, 'the page as it stands must pass first'
    right = f"{D['windows_read']} of {D['windows_total']} windows read in full"
    wrong = page.replace(right, f"{D['windows_read'] + 1} of {D['windows_total']} windows read in full")
    assert wrong != page
    _, bad = check_thesis.check(R, wrong, data_dir)
    assert [b[0] for b in bad] == ['the windows read in full'], bad
    print('1. a planted wrong count is reported:', bad[0][0])

    M = json.loads(json.dumps(R))
    node = M['M9']['p']
    for k in list(node):
        node[k] = None
    node[fill.NC] = True
    with tempfile.TemporaryDirectory() as tmp:
        cj, out = os.path.join(tmp, 'combined.json'), os.path.join(tmp, 'THESIS.md')
        with open(cj, 'w') as f:
            json.dump(M, f)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                written.main(data_dir, combined=cj, thesis=out)
        except SystemExit as e:
            assert e.code not in (0, None) and 'M9/p' in str(e.code), e.code
        else:
            raise AssertionError('written.py did not stop on a masked reading')
        assert not os.path.exists(out), 'no page may be written'
    print('2. a planted masked reading stops written.py, and no page is written')
    print('ok: 2 planted faults caught')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
