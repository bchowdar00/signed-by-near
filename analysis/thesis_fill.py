"""Fills the write-up's numbers from results.json, so no number in THESIS.md is typed by hand.

  python3 -I analysis/thesis_fill.py <THESIS.tmpl.md> <results.json> <out THESIS.md>

A placeholder is {{path::format}}. The path walks results.json with "/" (list items by index), for
example {{C2b/BTC/primary/L::pct1}} or {{M9/V_usd::usdm}}. Formats:
  pct0, pct1    a share as a percentage (0.1234 -> 12%, 12.3%)
  int           a whole number with thousands separators
  f1, f2, f4    a number with that many decimals
  usdm, usdb    US dollars in millions or billions ($831.3M, $3.71B)
  str           the value as written
A path that does not resolve, or resolves to null, stops the command with an error listing every
such placeholder: the write-up is never published with a hole in it.
"""
import json, re, sys

PH = re.compile(r'\{\{([^{}:]+)::([a-z0-9]+)\}\}')


def walk(obj, path):
    for part in path.strip().split('/'):
        if isinstance(obj, list):
            obj = obj[int(part)]
        else:
            obj = obj[part]
    return obj


def fmt(v, f):
    if f == 'str':
        return str(v)
    v = float(v)
    if f == 'pct0':
        return f'{100 * v:.0f}%'
    if f == 'pct1':
        return f'{100 * v:.1f}%'
    if f == 'int':
        return f'{v:,.0f}'
    if f in ('f1', 'f2', 'f4'):
        return f'{v:,.{int(f[1])}f}'
    if f == 'usdm':
        return f'${v / 1e6:,.1f}M'
    if f == 'usdb':
        return f'${v / 1e9:,.2f}B'
    raise ValueError(f'unknown format {f}')


def fill(text, results):
    holes = []

    def sub(m):
        path, f = m.group(1), m.group(2)
        try:
            v = walk(results, path)
        except (KeyError, IndexError, ValueError, TypeError):
            v = None
        if v is None:
            holes.append(m.group(0))
            return m.group(0)
        return fmt(v, f)

    out = PH.sub(sub, text)
    return out, holes


def main(tmpl, results_path, out):
    with open(tmpl) as f:
        text = f.read()
    with open(results_path) as f:
        res = json.load(f)
    filled, holes = fill(text, res)
    if holes:
        raise SystemExit('unresolved placeholders:\n' + '\n'.join(sorted(set(holes))))
    with open(out, 'w') as f:
        f.write(filled)
    print(f'filled {len(PH.findall(text))} placeholders into {out}')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    main(*sys.argv[1:4])
