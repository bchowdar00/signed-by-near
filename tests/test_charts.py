"""analysis/charts.py: hand-written SVG charts render from the synthetic results.json.

The fixture numbers are meaningless, so these tests check structure and robustness, never
a value: both files are written, both parse as XML, every required label is present, no
'nan'/'None' leaks into the text, output is byte-for-byte deterministic, and None values
render without error (drawn absent, not as zero)."""
import copy
import json
import math
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'analysis'))
import charts  # noqa: E402

FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'results-synthetic.json')


def _load():
    with open(FIXTURE) as f:
        return json.load(f)


# --- layout geometry (item 7): width 0.58*size*len, height size*1.2 -----------
def _parse_texts(svg):
    ns = '{http://www.w3.org/2000/svg}'
    root = ET.fromstring(svg)
    out = []
    for el in root.iter(ns + 'text'):
        out.append({
            'x': float(el.get('x', 0)),
            'y': float(el.get('y', 0)),
            'size': float(el.get('font-size', 11)),
            'anchor': el.get('text-anchor', 'start'),
            'text': ''.join(el.itertext()),
            'rot': el.get('transform') is not None,   # only rotate(-45 ..) is used
        })
    return out


def _box(t):
    """Axis-aligned box for a non-rotated label."""
    w = 0.58 * t['size'] * len(t['text'])
    a = t['anchor']
    if a == 'end':
        x0, x1 = t['x'] - w, t['x']
    elif a == 'middle':
        x0, x1 = t['x'] - w / 2.0, t['x'] + w / 2.0
    else:
        x0, x1 = t['x'], t['x'] + w
    return (x0, t['y'] - t['size'], x1, t['y'] + 0.2 * t['size'])  # height = 1.2*size


def _rot_aabb(t):
    """AABB of a -45deg (anchor-end) label; SVG y-down rotation (X,Y)=(xc-ys, xs+yc)."""
    c, s = math.cos(math.radians(-45)), math.sin(math.radians(-45))
    w = 0.58 * t['size'] * len(t['text'])
    top, bot = -t['size'], 0.2 * t['size']
    corners = [(-w, top), (0.0, top), (-w, bot), (0.0, bot)]
    xs = [x * c - y * s for x, y in corners]
    ys = [x * s + y * c for x, y in corners]
    return (t['x'] + min(xs), t['y'] + min(ys), t['x'] + max(xs), t['y'] + max(ys))


def _overlap(a, b, eps=0.5):
    return (a[0] < b[2] - eps and b[0] < a[2] - eps
            and a[1] < b[3] - eps and b[1] < a[3] - eps)


class TestCharts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = _load()
        cls.d = tempfile.mkdtemp()
        cls.paths = charts.render(cls.res, cls.d)
        cls.svg = {}
        for p in cls.paths:
            with open(p, encoding='utf-8') as f:
                cls.svg[os.path.basename(p)] = f.read()

    def test_writes_both_files_and_returns_paths(self):
        self.assertEqual([os.path.basename(p) for p in self.paths],
                         ['chart1-routes.svg', 'chart2-callers-cost.svg'])
        for p in self.paths:
            self.assertTrue(os.path.exists(p))

    def test_each_parses_as_xml(self):
        for name, text in self.svg.items():
            try:
                ET.fromstring(text)
            except ET.ParseError as e:
                self.fail(f'{name} is not well-formed XML: {e}')

    def test_titles_present(self):
        self.assertIn("Where Intents' measured cross-chain flow runs",
                      self.svg['chart1-routes.svg'])
        self.assertIn('Who calls the signer, and what the program costs',
                      self.svg['chart2-callers-cost.svg'])

    def test_chart1_contains_every_chain_name(self):
        c1 = self.svg['chart1-routes.svg']
        for row in self.res['chart1_flows']:
            self.assertIn(row['chain'], c1)

    def test_chart1_contains_every_m10_series_name(self):
        c1 = self.svg['chart1-routes.svg']
        for s in self.res['M10']:
            self.assertIn(s, c1)

    def test_chart1_contains_every_month_label_used(self):
        # chart 1 panel c labels every M10b point (month starts then 'T0').
        c1 = self.svg['chart1-routes.svg']
        for p in self.res['M10b']:
            self.assertIn(p['point'], c1)

    def test_chart2_contains_every_month_label_used(self):
        # chart 2 shares one month axis across both panels: every M4_M5 month.
        c2 = self.svg['chart2-callers-cost.svg']
        for row in self.res['M4_M5']:
            self.assertIn(row['month'], c2)

    def test_no_nan_or_none_text(self):
        for name, text in self.svg.items():
            self.assertNotIn('nan', text, name)
            self.assertNotIn('None', text, name)

    def test_deterministic_same_bytes(self):
        d2 = tempfile.mkdtemp()
        paths2 = charts.render(self.res, d2)
        for a, b in zip(self.paths, paths2):
            with open(a, 'rb') as fa, open(b, 'rb') as fb:
                self.assertEqual(fa.read(), fb.read(),
                                 f'{os.path.basename(a)} not byte-identical across renders')

    def test_layout_no_text_overlap(self):
        # No two non-rotated text boxes overlap (skip a label and its own value, which
        # share an anchor exactly); and no non-rotated text sits inside a rotated label.
        for name, text in self.svg.items():
            texts = _parse_texts(text)
            nonrot = [t for t in texts if not t['rot']]
            rot = [t for t in texts if t['rot']]
            for i in range(len(nonrot)):
                for j in range(i + 1, len(nonrot)):
                    a, b = nonrot[i], nonrot[j]
                    if (a['x'], a['y']) == (b['x'], b['y']):
                        continue
                    if _overlap(_box(a), _box(b)):
                        self.fail(f"{name}: non-rotated text overlap "
                                  f"{a['text']!r} & {b['text']!r}")
            for r in rot:
                rb = _rot_aabb(r)
                for a in nonrot:
                    if _overlap(rb, _box(a)):
                        self.fail(f"{name}: non-rotated {a['text']!r} inside the "
                                  f"rotated label {r['text']!r} extent")

    def test_none_values_render_without_error(self):
        r = copy.deepcopy(self.res)
        # an M8 month (a non-provisional one) with no per-request value
        r['M8']['months'][1]['per_request_executed_plus_pending'] = None
        # an M10 'early' interval with no L/U
        r['M10']['BTC']['readings']['amount']['early']['L'] = None
        r['M10']['BTC']['readings']['amount']['early']['U'] = None
        # one M10b omni_share missing (panel c gap)
        r['M10b'][5]['omni_share'] = None
        d = tempfile.mkdtemp()
        paths = charts.render(r, d)
        for p in paths:
            with open(p, encoding='utf-8') as f:
                text = f.read()
            ET.fromstring(text)  # still well-formed
            self.assertNotIn('nan', text)
            self.assertNotIn('None', text)


if __name__ == '__main__':
    unittest.main()
