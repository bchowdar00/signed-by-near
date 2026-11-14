"""Fills THESIS.md from THESIS.written.tmpl.md and checks it: the one command after rebuild.py.

  python3 -I rebuild.py <data_dir> --draft
  python3 -I publish/written.py <data_dir>

THESIS.tmpl.md is kept as stamped (postfreeze/MANIFEST-postfreeze.txt), with its sentences still to write, so
rebuild.py runs with --draft: it writes out/, out/published/, out/combined.json and a draft THESIS.md.
THESIS.written.tmpl.md is the same template with its sentences written after the counted read and its
presentation changed; AFTER-READ.md lists each change. This command fills it with the stamped publish/fill.py
(--final: no sentence may be left to write) and replaces THESIS.md only if two checks pass:
  1. no reading that a written line shows is masked (not completed): the written lines are the lines of the
     written template that the stamped template does not have, after each "if completed" block has chosen
     its text;
  2. publish/check_thesis.py: every condition a written sentence rests on holds, and every count the page
     states in words matches the results and the saved sample in <data_dir>, and TABLE-NOTES.md (the notes to
     read beside the tables and charts) is the text check_thesis.py holds for it.
If either fails it exits non-zero and leaves THESIS.md as it was. It makes no network call and is in no
manifest. publish/selftest_written.py plants a wrong count and a masked reading and checks that each is caught.

When both pass it also writes docs/ (publish/dashboard.py): the dashboard page, built from the same results
and the page just checked, and byte copies of the two charts. The dashboard is prepared before anything is
written, so a failure there leaves THESIS.md and docs/ as they were.
"""
import hashlib, json, os, sys, tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fill  # noqa: E402
import check_thesis  # noqa: E402
import dashboard  # noqa: E402


def masked_in_written_lines(R, written, stamped):
    """Placeholders on the written lines whose reading is masked."""
    ext = os.path.join(ROOT, 'THESIS.ext.tmpl.md')
    texts = []
    for p in (written, stamped):
        with open(p) as f:
            texts.append(fill.expand(f.read(), R, ext))
    old = set(texts[1].split('\n'))
    bad = []
    for line in texts[0].split('\n'):
        if line not in old:
            for m in fill.TF.PH.finditer(line):
                try:
                    masked = fill.resolve(R, m.group(1))[1]
                except (TypeError, KeyError, IndexError):   # a path that runs on below a masked reading, whose parts are empty
                    masked = True
                if masked:
                    bad.append(m.group(0))
    return sorted(set(bad))


def main(data_dir, combined=None, thesis=None):
    whole = combined is None and thesis is None      # the real run; a trial on other paths writes no docs/
    tmpl = os.path.join(ROOT, 'THESIS.written.tmpl.md')
    thesis = thesis or os.path.join(ROOT, 'THESIS.md')
    combined = combined or os.path.join(ROOT, 'out', 'combined.json')
    with open(combined) as f:
        R = json.load(f)
    bad = masked_in_written_lines(R, tmpl, os.path.join(ROOT, 'THESIS.tmpl.md'))
    if bad:
        raise SystemExit('a written line shows a reading that is not completed; THESIS.md is left as it was:\n'
                         + '\n'.join(bad))
    fd, tmp = tempfile.mkstemp(suffix='.md')
    os.close(fd)
    try:
        fill.main(tmpl, combined, tmp, final=True)
        with open(tmp) as f:
            text = f.read()
    finally:
        os.remove(tmp)
    D, bad = check_thesis.check(R, text, data_dir)
    if bad:
        for b in bad:
            print('MISMATCH', b)
        raise SystemExit('THESIS.md is left as it was')
    docs = dashboard.render(R, text, D) if whole else None
    with open(thesis, 'w') as f:
        f.write(text)
    if whole:
        print(f'docs/index.html sha256 {dashboard.write(docs)}')
    print(f'ok: {len(check_thesis.expected(D)) + len(check_thesis.TESTS)} statements match; '     # the last line, as the page says
          f'{os.path.relpath(thesis, ROOT)} sha256 {hashlib.sha256(text.encode()).hexdigest()}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
