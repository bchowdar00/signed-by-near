"""Compare every published thesis number with the independent re-derivation.

Reads the published numbers from <repo>/out/published/results.json and
<repo>/out/published/tables.md, and the independent numbers from this run's family
outputs in out/ (plus out/page_extras.json and mc-seeds/sweep.json). It recomputes
nothing random: the family outputs already carry seeds 1 and 2. Writes out/compare.json
and RESULTS.md, or, when run with a sources folder, out/compare-with-sources.json and
RESULTS-with-sources.md; all deterministic (no timestamps, no absolute paths).

Status per number (row status = the weakest of its numbers, in this order):
  agree > source check > needs source file > not recomputed > differs
  - agree: recomputed by shipped code and equal. Deterministic values equal at the
    published precision. A bootstrap end agrees if |published - nearer of seeds 1,2|
    <= max(0.05*|p|,0.01) for shares, else <= 0.05*|p|; or, where mc-seeds/sweep.json
    has a sweep for it, if the published value lies in the sweep's min..max.
  - source check: checked against a named file, not recomputed by code.
  - needs source file: the code for it needs a file that was not shipped.
  - not recomputed: no shipped code produces it.
  - differs: anything else (explained).
python3 -I.
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PUB_DIR = os.path.join(REPO, 'out', 'published')
DATA_DIR = os.environ.get('RD_DATA') or os.path.join(REPO, 'data')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def load(p):
    return json.load(open(p)) if os.path.exists(p) else None


PUB = load(os.path.join(PUB_DIR, 'results.json'))
TABLES_PATH = os.path.join(PUB_DIR, 'tables.md')
F = {fam: load(os.path.join(HERE, 'out', fam + '.json'))
     for fam in ('c2b-m10', 'm9-m1', 'm3-m8-m7', 'm4-m5-trend')}
PE = load(os.path.join(HERE, 'out', 'page_extras.json'))
SW = load(os.path.join(HERE, 'mc-seeds', 'sweep.json'))
COMB = load(os.path.join(REPO, 'out', 'combined.json'))

# The page itself, read at run time. Sections for each number are discovered from it,
# and page-sentence values are parsed from it; nothing about the page is hard-coded.
THESIS_PATH = os.path.join(REPO, 'THESIS.md')
THESIS = open(THESIS_PATH, encoding='utf-8').read() if os.path.exists(THESIS_PATH) else ''
TABLES = open(TABLES_PATH, encoding='utf-8').read() if os.path.exists(TABLES_PATH) else ''

# Source files that ship with no repository copy (checked by presence, like the families do).
SOURCES_DIR = os.environ.get('RD_SOURCES') or None


SOURCES = json.load(open(os.path.join(HERE, 'sources.json')))['files']
SOURCE_PROBLEMS = {}   # name -> why a copy given was not used


def source_present(name):
    """True only if the folder given holds this file and it is the 2026-11-09 copy."""
    if not SOURCES_DIR:
        return False
    p = os.path.join(SOURCES_DIR, name)
    if not os.path.exists(p):
        return False
    if sha256(p) != SOURCES[name]['sha256']:
        SOURCE_PROBLEMS[name] = 'the copy given is not the 2026-11-09 copy (sha256 differs)'
        return False
    return True


def source_text(name):
    """The text of a source file, with HTML tags removed and spaces collapsed."""
    import html as _html
    t = open(os.path.join(SOURCES_DIR, name), encoding='utf-8', errors='replace').read()
    if name.endswith('.html'):
        t = _html.unescape(re.sub(r'<[^>]+>', ' ', t))
    return re.sub(r'\s+', ' ', t)


def source_desc(name):
    s = SOURCES[name]
    return '%s (%s; sha256 %s)' % (name, s['url'], s['sha256'])


def thread_text(name):
    """The posts of a saved Discourse thread (its .json), joined, tags removed."""
    import html as _html
    d = json.load(open(os.path.join(SOURCES_DIR, name), encoding='utf-8'))
    t = ' '.join(p.get('cooked', '') for p in d['post_stream']['posts'])
    return re.sub(r'\s+', ' ', _html.unescape(re.sub(r'<[^>]+>', ' ', t)))


_OMNI = 'web-docs.near.org_omnibridge_overview.html'


def _ref():
    return json.load(open(os.path.join(REPO, 'inputs', 'reference.json'), encoding='utf-8'))


def _cap_in_28():
    r = _ref()
    c28 = set(x for v in r['chains28'].values() for x in v)
    return len([c for c in r['capability13'] if c in c28])


def _omni_page_check():
    """With the saved Omni overview: the chains it lists as '<Chain> - (... + Chain Signatures)'
    that are among the 28, against the page's count. Without it, nothing is added: the count
    above needs only the shipped lists."""
    if not source_present(_OMNI):
        return []
    on_page = re.findall(r'([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?) - \([^)]*Chain Signatures[^)]*\)', source_text(_OMNI))
    c28 = set(x for v in _ref()['chains28'].values() for x in v)
    return [N_source("chains NEAR's Omni overview lists with Chain Signatures that are among the 28",
                     len([c for c in on_page if c in c28]), _OMNI,
                     PAGE("NEAR's own Omni overview documents 10 of the 28", 0), 'THESIS')]


_MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']


def iso_date(text):
    """The first date in text, written 'June 22, 2026', 'Dec 30, 2026' or '30 December 2026',
    as 'YYYY-MM-DD'; MISSING if there is none."""
    m = re.search(r'\b([A-Z][a-z]{2,8})\.? (\d{1,2}), (\d{4})\b', text)
    if m and m.group(1)[:3].lower() in _MONTHS:
        mo, d, y = m.group(1), m.group(2), m.group(3)
    else:
        m = re.search(r'\b(\d{1,2}) ([A-Z][a-z]{2,8}) (\d{4})\b', text)
        if not (m and m.group(2)[:3].lower() in _MONTHS):
            return MISSING
        d, mo, y = m.group(1), m.group(2), m.group(3)
    return '%s-%02d-%02d' % (y, _MONTHS.index(mo[:3].lower()) + 1, int(d))


def thesis_sections(text):
    """Every '##' / '###' heading under which the exact substring `text` appears in
    THESIS.md, joined with '; '. Returns None if the substring is not present."""
    if not text or text not in THESIS:
        return None
    secs, cur = [], None
    want = set()
    # mark the character ranges of each heading's body, then see which contain `text`
    lines = THESIS.split('\n')
    heads = []  # (title, start_char, end_char)
    pos = 0
    open_head = None
    for ln in lines:
        m = __import__('re').match(r'^(#{2,3})\s+(.*)', ln)
        if m:
            if open_head is not None:
                heads.append((open_head[0], open_head[1], pos))
            open_head = (m.group(2).strip(), pos)
        pos += len(ln) + 1
    if open_head is not None:
        heads.append((open_head[0], open_head[1], len(THESIS)))
    start = 0
    while True:
        i = THESIS.find(text, start)
        if i < 0:
            break
        for title, a, b in heads:
            if a <= i < b and title not in secs:
                secs.append(title)
        start = i + 1
    return '; '.join(secs) if secs else 'front matter'  # found, but above the first heading


_NUMRE = __import__('re')


def page_nums(page_text):
    """All numbers in a page sentence, as floats (percent/comma/B/M aware is left to callers)."""
    if not page_text or page_text not in THESIS:
        return None
    return [float(x.replace(',', '')) for x in _NUMRE.findall(r'-?\d[\d,]*\.?\d*', page_text)]


MISSING = object()


def g(d, path):
    """Dotted/slashed path lookup; list indices as integers. Returns MISSING if absent."""
    cur = d
    if cur is None:
        return MISSING
    for seg in path.split('/'):
        if seg == '':
            continue
        if isinstance(cur, list):
            try:
                cur = cur[int(seg)]
            except (ValueError, IndexError):
                return MISSING
        elif isinstance(cur, dict):
            if seg not in cur:
                return MISSING
            cur = cur[seg]
        else:
            return MISSING
    return cur


def m3_month(month, path):
    """Independent M3 month entry value by month id."""
    months = g(F['m3-m8-m7'] or {}, 'm3/months')
    if months is MISSING or month not in months:
        return MISSING
    return g(months[month], path)


def pub_m3_month(month, path):
    arr = g(PUB, 'M3')
    if arr is not MISSING:
        for e in arr:
            if e.get('month') == month:
                return Pub(g(e, path), 'results')
    return Pub(MISSING, 'results')


def comb_m1_unit(chain, unit):
    """Published per-unit M1 Omni amount-share upper end from out/combined.json."""
    chs = g(COMB, 'M1/chains')
    if chs is not MISSING:
        for c in chs:
            if c.get('chain') == chain:
                return Pub(g(c, 'amount_share_by_unit/%s/U' % unit), 'combined')
    return Pub(MISSING, 'combined')


# --- tagged published-value fetchers -------------------------------------------------
# Every published value passed to a number builder is wrapped by one of these, which
# records the file it came from. A builder unwraps it; a bare literal is not a Pub, so the
# enforcement at the end of the file makes compare.py exit. A wrapper (not a side channel)
# is used so that an independent expression calling a fetcher cannot mis-tag a pub literal.
_SENT_LOG = []  # page sentences read while building the current row (for its sections)


class Pub:
    __slots__ = ('v', 'k')

    def __init__(self, value, kind):
        self.v = value
        self.k = kind


def R(path):
    """A value from results.json by key path."""
    return Pub(g(PUB, path), 'results')


def C(path):
    """A value from combined.json by key path."""
    return Pub(g(COMB, path), 'combined')


def PAGE(page_text, i=0):
    """The i-th number parsed from an exact sentence of THESIS.md."""
    _SENT_LOG.append(page_text)
    ns = page_nums(page_text)
    return Pub(ns[i] if (ns and i < len(ns)) else MISSING, 'page')


_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
          'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12}


def PAGEWORD(page_text, word):
    """A number written as a word in an exact sentence of THESIS.md (for example 'six')."""
    _SENT_LOG.append(page_text)
    ok = bool(page_text) and page_text in THESIS and (' %s ' % word) in (' %s ' % page_text)
    return Pub(_WORDS[word] if ok else MISSING, 'page')


def PAGEPHRASE(page_text):
    """An exact phrase of THESIS.md, kept as text (a claim stated in words)."""
    _SENT_LOG.append(page_text)
    return Pub(page_text if (page_text and page_text in THESIS) else MISSING, 'page')


def PAGEDATE(page_text):
    """The date in an exact sentence of THESIS.md, as 'YYYY-MM-DD'."""
    _SENT_LOG.append(page_text)
    return Pub(iso_date(page_text) if (page_text and page_text in THESIS) else MISSING, 'page')


def PAGES(page_text):
    """All numbers parsed from an exact sentence of THESIS.md, as a list (or MISSING)."""
    _SENT_LOG.append(page_text)
    ns = page_nums(page_text)
    return Pub(ns if ns else MISSING, 'page')


def TBL(marker, col, after=None):
    """A number from a tables.md row: the `col`-th number on the first line that contains
    `marker` (and `after`, if given). Line-based, so reading ids with '|' do not confuse it."""
    started = after is None
    for ln in TABLES.split('\n'):
        if after is not None and after in ln:
            started = True
        if started and marker in ln:
            nums = _NUMRE.findall(r'-?\d[\d,]*\.?\d*', ln)
            if col < len(nums):
                return Pub(float(nums[col].replace(',', '')), 'tables')
    return Pub(MISSING, 'tables')


def PCHAIN(chain, key):
    """Published per-chain M9 by-chain-scenario value from results.json (pub_chain table)."""
    return Pub((pub_chain.get(chain) or {}).get(key, MISSING), 'results')


def pub_m45(month, path):
    """A value from the published results.json M4_M5 month entry, by sub-path."""
    for e in (g(PUB, 'M4_M5') or []):
        if e.get('month') == month:
            return Pub(g(e, path), 'results')
    return Pub(MISSING, 'results')


# ---------------------------------------------------------------------------
# status helpers
# ---------------------------------------------------------------------------

def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def status_exact(ind, pub, places):
    if ind is MISSING or pub is MISSING:
        return 'differs', 'missing value'
    if not (is_num(ind) and is_num(pub)):
        return ('agree', 'equal') if ind == pub else ('differs', 'unequal %r vs %r' % (ind, pub))
    if round(ind, places) == round(pub, places):
        return 'agree', 'equal at %d dp' % places
    return 'differs', 'exact mismatch: ind %.10g vs pub %.10g' % (ind, pub)


def status_bootstrap(ind_seeds, pub, is_share):
    """ind_seeds = (seed1, seed2). Agree if |pub - nearer seed| <= tol."""
    if pub is MISSING or ind_seeds[0] is MISSING or ind_seeds[1] is MISSING:
        return 'differs', 'missing value', None
    tol = max(0.05 * abs(pub), 0.01) if is_share else 0.05 * abs(pub)
    gap = min(abs(pub - ind_seeds[0]), abs(pub - ind_seeds[1]))
    rule = 'bootstrap tol=%.6g (|p-nearer seed|=%.6g)' % (tol, gap)
    return ('agree' if gap <= tol else 'differs', rule, gap)


def status_sweep(pub, lo, hi):
    if pub is MISSING or lo is MISSING or hi is MISSING:
        return 'differs', 'missing value'
    inside = lo <= pub <= hi
    return ('agree' if inside else 'differs',
            'sweep min..max [%.6g, %.6g]' % (lo, hi))


WEAK = {'agree': 0, 'source check': 1, 'needs source file': 2, 'not recomputed': 3, 'differs': 4}


# ---------------------------------------------------------------------------
# A number is a dict produced by one of these builders. Each returns a dict with
# status, rule, published, independent (and seeds for bootstrap), source.
# ---------------------------------------------------------------------------

def _unwrap(pub):
    """Unwrap a Pub into (value, source_kind). A bare literal is untagged (kind None),
    which the enforcement at the end of the file rejects."""
    if isinstance(pub, Pub):
        return pub.v, pub.k
    return pub, None


def _psk(pubv, kind):
    return kind if pubv is not None else None


def N_exact(label, ind, pub, places, src, pub_where):
    pub, kind = _unwrap(pub)
    st, rule = status_exact(ind, pub, places)
    pubv = None if pub is MISSING else pub
    return {'label': label, 'kind': 'exact', 'status': st, 'rule': rule,
            'published': pubv, 'published_source_kind': _psk(pubv, kind),
            'independent': None if ind is MISSING else ind,
            'source': src, 'published_where': pub_where}


def N_boot(label, seed1, seed2, pub, is_share, src, pub_where, sweep=None):
    pub, kind = _unwrap(pub)
    if sweep is not None:
        lo, hi = sweep
        st, rule = status_sweep(pub, lo, hi)
        gap = None
    else:
        st, rule, gap = status_bootstrap((seed1, seed2), pub, is_share)
    pubv = None if pub is MISSING else pub
    return {'label': label, 'kind': 'bootstrap', 'status': st, 'rule': rule,
            'published': pubv, 'published_source_kind': _psk(pubv, kind),
            'independent': {'seed1': None if seed1 is MISSING else seed1,
                            'seed2': None if seed2 is MISSING else seed2},
            'source': src, 'published_where': pub_where}


def N_source(label, value, src_file, pub, pub_where):
    """A value read by this code from a named source file, compared with the page."""
    pub, kind = _unwrap(pub)
    pubv = None if pub is MISSING else pub
    ok = value is not MISSING and pub is not MISSING and value == pub
    return {'label': label, 'kind': 'source check', 'status': 'source check' if ok else 'differs',
            'rule': ('read from %s and equal to the page' if ok else
                     'read from %s and NOT equal to the page') % src_file,
            'published': pubv, 'published_source_kind': _psk(pubv, kind),
            'independent': None if value is MISSING else value,
            'source': src_file, 'published_where': pub_where}


def N_needs(label, src_file, pub, pub_where):
    pub, kind = _unwrap(pub)
    pubv = None if pub is MISSING else pub
    names = src_file if isinstance(src_file, list) else [src_file]
    why = ['%s: %s' % (n, SOURCE_PROBLEMS[n]) for n in names if n in SOURCE_PROBLEMS]
    return {'label': label, 'kind': 'needs source file', 'status': 'needs source file',
            'rule': 'needs source file ' + '; '.join(source_desc(n) for n in names) +
                    (' [' + '; '.join(why) + ']' if why else ''),
            'published': pubv, 'published_source_kind': _psk(pubv, kind), 'independent': None,
            'source': ' + '.join(names), 'published_where': pub_where}


def N_notrecomp(label, pub, pub_where, note):
    pub, kind = _unwrap(pub)
    pubv = None if pub is MISSING else pub
    return {'label': label, 'kind': 'not recomputed', 'status': 'not recomputed',
            'rule': note, 'published': pubv, 'published_source_kind': _psk(pubv, kind),
            'independent': None, 'source': None, 'published_where': pub_where}


def N_input(label, value, pub, src, pub_where):
    """A value the page restates from an input file (a stamp, a frozen instant, a figure
    reported by a third party). This code reads the same file, so the number is shown but not
    counted as recomputed. If it is not equal to the published value, it differs."""
    pub, kind = _unwrap(pub)
    pubv = None if pub is MISSING else pub
    ok = value is not MISSING and pub is not MISSING and value == pub
    return {'label': label, 'kind': 'input', 'status': 'not recomputed' if ok else 'differs',
            'rule': ('an input read from %s, equal to the published value; not a computation' if ok else
                     'an input read from %s, NOT equal to the published value') % src,
            'published': pubv, 'published_source_kind': _psk(pubv, kind),
            'independent': None if value is MISSING else value,
            'source': src, 'published_where': pub_where}


def N_differs(label, ind, pub, note, src, pub_where):
    pub, kind = _unwrap(pub)
    pubv = None if pub is MISSING else pub
    return {'label': label, 'kind': 'differs', 'status': 'differs', 'rule': note,
            'published': pubv, 'published_source_kind': _psk(pubv, kind),
            'independent': None if ind is MISSING else ind,
            'source': src, 'published_where': pub_where}


# convenience
c2b = F['c2b-m10'] or {}
m9m1 = F['m9-m1'] or {}
s1 = F['m3-m8-m7'] or {}
s2 = F['m4-m5-trend'] or {}



def share(x):
    return True


# Build the rows. Each entry: (num, section, [numbers], optional dict extras)
ROWS = []


# Where each row's numbers are printed on the page, when they are read from results.json rather
# than parsed from a page sentence. These are places, not values: each must be an exact substring
# of THESIS.md, or the row is flagged "page text not found".
ANCHORS = {1: ['Data cutoff (T0): 2026-11-10T11:00:00'], 6: ["Omni carried [100.0%, 100.0%] of Intents' bridged BTC in the claim window"],
           7: ['by count as well as amount, in each direction'], 8: ['over the whole 90 days ([99.7%, 100.0%])'],
           9: ['Omni carried [24.7%, 100.0%] of bridged SOL'], 10: ['([32.1%, 100.0%])'], 11: ['[43.2%, 100.0%] of Solana USDC and USDT'],
           16: ['their upper ends, 73.1% to 94.0%'], 17: ['100.0% of SOL and 94.3% of ZEC'], 18: ['41.3% [21.1%, 89.5%]'],
           19: ['19.2% [6.2%, 78.6%]'], 20: ['$3,072.6M per 30 days'], 21: ['$1,163.2M to $2,586.2M'], 22: ['3.70 times'],
           23: ['V = $831.3M'], 24: ["Omni's share would be 89.5%; if none were, 21.1%"], 25: ['1.56 times 2V'], 26: ['read 88.2% and 14.0%'],
           32: ['14,046 a day in October 2026'], 34: ['0.89 [0.75, 1.06]'], 35: ['2.37 [1.65, 3.70]'],
           37: ["3.5% of October's calls [1.7%, 17.4%]", 'With Sweat: 37.5%'], 38: ["(34.0%), Omni's bridge contract (25.1%)"],
           39: ["made 3.5% [1.7%, 5.9%] of October's calls"], 41: ['2.0%, 2.0%, 3.5%; lower ends 0.9%, 0.4%, 1.7%'],
           49: ['252 of the 255'], 56: ['the bootstrap alone gives [25.2%, 57.3%]'], 57: ['cover 88.3% of V'], 58: ['$3,714.7M']}


def row(num, section, numbers, page_text=None, note=None):
    # The row's sections come from every page sentence its numbers were read from, plus any
    # page_text given here; all are looked up in THESIS.md at run time.
    given = [page_text] if isinstance(page_text, str) else (list(page_text.values()) if isinstance(page_text, dict) else [])
    sents = list(dict.fromkeys([t for t in given + _SENT_LOG + ANCHORS.get(num, []) if t]))
    _SENT_LOG.clear()
    ROWS.append({'row': num, 'section': section, 'numbers': numbers,
                 'page_text': sents or None, 'note': note})


# ---- Rows 1-52 (ordered as in COMPARISON.md) ----

_instants = load(os.path.join(REPO, 'frozen', 'instants.json'))
row(1, None, [N_input('T0 instant', g(_instants, 'meta/T0_utc'), R('T0_utc'),
      'frozen/instants.json meta/T0_utc', 'results.json T0_utc')])

row(2, None, [
    N_exact('windows read', g(c2b, 'completion/totals/completed'), PAGE('490 of 526 windows', 0), 0, 'c2b-m10 completion/totals/completed', 'THESIS'),
    N_exact('not completed', g(c2b, 'completion/totals/not_completed'), PAGE('rest on the other 36', 0), 0, 'c2b-m10 completion/totals/not_completed', 'THESIS'),
])

row(3, None, [
    N_exact('Intents tokens in the design (15)', len(g(load(os.path.join(REPO, 'frozen', 'tokens.json')), 'tokens') or []),
            PAGE('for each of 15 Intents tokens on 8 chains', 0), 0, 'frozen/tokens.json (tokens, counted)', 'THESIS'),
    N_exact('chains of those tokens (8)', len(set(t.get('chain') for t in (g(load(os.path.join(REPO, 'frozen', 'tokens.json')), 'tokens') or []))),
            PAGE('for each of 15 Intents tokens on 8 chains', 1), 0, 'frozen/tokens.json (chains, counted)', 'THESIS'),
    N_exact('chains with a measured token', len(g(m9m1, 'm1_census/chains_with_measured') or []), PAGE('can read 8 chains', 0), 0, 'm9-m1 m1_census/chains_with_measured', 'THESIS'),
])

def _count(x):
    """A count the part stored either as a list or already as its length."""
    if x is MISSING or x is None:
        return 0
    return len(x) if isinstance(x, (list, dict)) else x


row(4, None, [
    N_exact('audit read whole', g(c2b, 'resolution/audit/read'), TBL('Resolution audit', 0), 0, 'c2b-m10 resolution/audit/read', 'tables.md Resolution audit'),
    N_exact('audit differ', _count(g(c2b, 'resolution/audit/differ')), TBL('Resolution audit', 1), 0, 'c2b-m10 resolution/audit/differ', 'tables.md Resolution audit'),
])

_RESOLVED = load(os.path.join(DATA_DIR, 'nb', 'RESOLVED')) if os.path.exists(os.path.join(DATA_DIR, 'nb', 'RESOLVED')) else None
row(5, None, [
    N_notrecomp('included transactions (2,522)', Pub(g(_RESOLVED, 'included_transactions'), 'data'), 'data/nb/RESOLVED included_transactions',
                "the c2b-m10 part's make_results.py types 2522 instead of counting it, so it is not counted as recomputed"),
    N_exact('resolution candidates (0)', g(c2b, 'resolution/my_candidates'), Pub(g(_RESOLVED, 'candidates'), 'data'), 0,
            'c2b-m10 resolution/my_candidates', 'data/nb/RESOLVED candidates'),
])

# BTC C2b (row 6 claim|amount|both point + bounds; row 7 count; row 8 90d)
btc = g(c2b, 'c2b/BTC') or {}
row(6, None, [
    N_exact('BTC claim|amount point', g(btc, 'claim|amount|both/point_unknown_not'), R('C2b/BTC/primary/point_unknown_not_omni'), 4, 'c2b-m10 c2b/BTC', 'C2b/BTC/primary/point_unknown_not_omni'),
    N_exact('BTC primary L', g(btc, 'claim|amount|both/L'), R('C2b/BTC/primary/L'), 4, 'c2b-m10 c2b/BTC/.../L', 'C2b/BTC/primary/L'),
    N_exact('BTC primary U', g(btc, 'claim|amount|both/U'), R('C2b/BTC/primary/U'), 4, 'c2b-m10 c2b/BTC/.../U', 'C2b/BTC/primary/U'),
])
row(7, None, [
    N_exact('BTC count L', g(btc, 'claim|count|both/L'), R('C2b/BTC/readings/claim|count|both/L'), 4, 'c2b-m10 c2b/BTC claim|count|both', 'C2b/BTC/readings'),
    N_exact('BTC count U', g(btc, 'claim|count|both/U'), R('C2b/BTC/readings/claim|count|both/U'), 4, 'c2b-m10 c2b/BTC claim|count|both', 'C2b/BTC/readings'),
])
row(8, None, [
    N_exact('BTC 90d amount point', g(btc, '90d|amount|both/point_unknown_not'), R('C2b/BTC/readings/90d|amount|both/point_unknown_not_omni'), 5, 'c2b-m10 c2b/BTC 90d', 'C2b/BTC/readings/90d/point_unknown_not_omni'),
    N_boot('BTC 90d amount L', g(btc, '90d|amount|both/bootstrap/1/boot_L'), g(btc, '90d|amount|both/bootstrap/2/boot_L'), R('C2b/BTC/readings/90d|amount|both/L'), True, 'c2b-m10 c2b/BTC 90d bootstrap', 'C2b/BTC/readings/90d/L', sweep=(g(SW, 'btc_90d_amount_lower/min'), g(SW, 'btc_90d_amount_lower/max'))),
])

sol = g(c2b, 'c2b/SOL') or {}
row(9, None, [
    N_exact('SOL claim amount L', g(sol, 'claim|amount|both/L'), R('C2b/SOL/primary/L'), 4, 'c2b-m10 c2b/SOL', 'C2b/SOL/primary/L'),
])
row(10, None, [
    N_exact('SOL claim count point', g(sol, 'claim|count|both/point_unknown_not'), R('C2b/SOL/readings/claim|count|both/point_unknown_not_omni'), 3, 'c2b-m10 c2b/SOL claim|count', 'C2b/SOL/readings/claim|count|both/point_unknown_not_omni'),
    N_exact('SOL 90d amount point', g(sol, '90d|amount|both/point_unknown_not'), R('C2b/SOL/readings/90d|amount|both/point_unknown_not_omni'), 3, 'c2b-m10 c2b/SOL 90d', 'C2b/SOL/readings/90d|amount|both/point_unknown_not_omni'),
])
stab = g(c2b, 'c2b/STABLE') or {}
row(11, None, [
    N_exact('stablecoins claim amount L', g(stab, 'claim|amount|both/L'), R('C2b/Solana stablecoins (USD)/primary/L'), 4, 'c2b-m10 c2b/STABLE', 'C2b/Solana stablecoins (USD)/primary/L'),
])
# row 12: transfers and windows for each C2b reading. The published "transfers / windows"
# column is tables.md (results.json's own "windows" is the stratum window count, a different
# quantity); it is parsed by splitting each table row into logical columns and rejoining the
# reading id, so a reading id's own "|" does not break the parse. Compared to the family's
# distinct and windows_with_transfer.
_c2b_tbl = {}
_in_c2b = False
for _ln in TABLES.split('\n'):
    if _ln.startswith('## C2b'):
        _in_c2b = True
        continue
    if _in_c2b and _ln.startswith('## '):
        break
    if _in_c2b and _ln.startswith('|'):
        _cells = [c.strip() for c in _ln.strip().strip('|').split('|')]
        if len(_cells) >= 5 and '/' in _cells[-1] and '[' in _cells[-3]:
            _grp = _cells[0]
            _rid = '|'.join(_cells[1:-3])
            try:
                _t, _w = [int(x.strip().replace(',', '')) for x in _cells[-1].split('/')]
            except ValueError:
                continue
            _c2b_tbl[(_grp, _rid)] = (_t, _w)
_grpmap = [('BTC', 'BTC'), ('SOL', 'SOL'), ('STABLE', 'Solana stablecoins (USD)')]
_r12 = []
for _fg, _tg in _grpmap:
    _fam = g(c2b, 'c2b/%s' % _fg)
    if _fam is MISSING or not isinstance(_fam, dict):
        continue
    for _r in _fam:
        _fo = g(_fam, _r)
        if not isinstance(_fo, dict):
            continue
        _key = (_tg, _r)
        if _key not in _c2b_tbl:
            continue
        _t, _w = _c2b_tbl[_key]
        _r12.append(N_exact('C2b %s %s transfers' % (_tg, _r), g(_fo, 'distinct'),
            Pub(_t, 'tables'), 0, 'c2b-m10 c2b/%s/%s/distinct' % (_fg, _r),
            'tables.md C2b %s %s transfers' % (_tg, _r)))
        _r12.append(N_exact('C2b %s %s windows' % (_tg, _r), g(_fo, 'windows_with_transfer'),
            Pub(_w, 'tables'), 0, 'c2b-m10 c2b/%s/%s/windows_with_transfer' % (_fg, _r),
            'tables.md C2b %s %s windows' % (_tg, _r)))
if not _r12:
    _r12 = [N_notrecomp('transfers/windows on the C2b readings', MISSING, 'tables.md C2b',
            'no C2b table rows resolved against the family output')]
row(12, None, _r12)

row(13, None, [
    N_exact('readable (chains with a measured token)', len(g(m9m1, 'm1_census/chains_with_measured') or []), PAGE('can read the flow on 8', 0), 0, 'm9-m1 m1_census/chains_with_measured', 'THESIS'),
    N_exact('dominant yes', g(m9m1, 'm1_dominant/dominant_yes'), R('M1/counts/dominant/unfavourable_yes'), 0, 'm9-m1 m1_dominant/dominant_yes', 'M1/counts/dominant/unfavourable_yes'),
    N_exact('seen in use', g(m9m1, 'm1_census/observed_yes'), R('M1/counts/observed/unfavourable_yes'), 0, 'm9-m1 m1_census/observed_yes', 'M1/counts/observed/unfavourable_yes'),
    # m9-m1's assemble.py writes this count as a typed 10 (an expected value its brief gave);
    # it is not used here. The count is taken from the shipped lists instead.
    N_exact('Omni overview chains among the 28 (counted from the lists in inputs/reference.json)', _cap_in_28(), R('M1/counts/capability_documented/count'), 0, 'compare.py: inputs/reference.json capability13 that are in chains28', 'M1/counts/capability_documented'),
] + _omni_page_check())
_NEARSTATS = 'nearstats-api-near-summary.json'
_t14 = 'NearStats listed 39 supported chains for Intents on Nov 9, 2026'
if source_present(_NEARSTATS):
    _ns = json.load(open(os.path.join(SOURCES_DIR, _NEARSTATS), encoding='utf-8'))
    _gen = g(_ns, 'generatedAt')
    row(14, None, [
        N_source('chains NearStats lists as supported for Intents (intents/supportedAssets/supportedChains)',
                 g(_ns, 'intents/supportedAssets/supportedChains'), _NEARSTATS, PAGE(_t14, 0), 'THESIS'),
        N_source("the feed's date (generatedAt)", _gen[:10] if isinstance(_gen, str) else MISSING,
                 _NEARSTATS, PAGEDATE(_t14), 'THESIS')])
else:
    row(14, None, [
        N_needs('chains NearStats lists as supported for Intents', _NEARSTATS, PAGE(_t14, 0), 'THESIS'),
        N_needs("the feed's date", _NEARSTATS, PAGEDATE(_t14), 'THESIS')])
row(15, None, [
    N_differs('census tokens (counted rows outside the window segments)', len(g(m9m1, 'm1_census/census_tokens') or {}),
              Pub(len(g(PUB, 'census/tokens') or {}), 'results'),
              "This implementation counted census rows outside the windows' segments as well (21 tokens, 1,675 rows); counted inside the segments, as METHOD M1 says, the census has 15 tokens and 1,030 rows, as published. Left as written.", 'm9-m1 m1_census/census_tokens', 'results.json census/tokens (count)'),
    N_differs('census rows (counted rows outside the window segments)', sum((g(m9m1, 'm1_census/census_tokens') or {}).values()),
              Pub(sum((g(PUB, 'census/tokens') or {}).values()), 'results'),
              'The same departure as the line above: 1,675 rows counted, against 1,030 inside the segments as published.',
              'm9-m1 m1_census/census_tokens (rows summed)', 'results.json census/tokens (rows summed)'),
    N_exact('census E seconds', g(m9m1, 'm1_census/E_s'), R('census/exposure_s'), 2, 'm9-m1 m1_census/E_s', 'results.json census/exposure_s'),
])

# row 16-17 per-chain POA upper ends (by_chain), 5 POA chains
bychain_rows = g(m9m1, 'bychain/rows') or {}
pub_chain = {c['chain']: c for c in (g(PUB, 'M9/by_chain_scenario/chains') or [])}
row(16, None, [
    N_exact('%s %s U' % (chain, unit),
            g(m9m1, 'm1_dominant/chains/%s/groups/%s/U' % (chain, unit)),
            comb_m1_unit(chain, unit), 4,
            'm9-m1 m1_dominant/chains/%s/groups/%s/U' % (chain, unit),
            'combined.json M1/chains/%s/amount_share_by_unit/%s/U' % (chain, unit))
    for chain, unit in [('Arbitrum', 'USD'), ('Base', 'USD'), ('Ethereum', 'ETH'),
                        ('Ethereum', 'USD'), ('Tron', 'USD'), ('XRP', 'XRP')]
])
row(17, None, [
    N_exact('SOL U', g(bychain_rows, 'solana/hullU'), PCHAIN('Solana', 'U'), 3, 'm9-m1 bychain/rows/solana/hullU', 'chains'),
    N_exact('ZEC U', g(bychain_rows, 'zcash/hullU'), PCHAIN('Zcash', 'U'), 4, 'm9-m1 bychain/rows/zcash/hullU', 'chains'),
    N_exact('SOL floor L', g(bychain_rows, 'solana/hullL'), PCHAIN('Solana', 'L'), 4, 'm9-m1 bychain/rows/solana/hullL', 'chains'),
    N_exact('ZEC floor L', g(bychain_rows, 'zcash/hullL'), PCHAIN('Zcash', 'L'), 4, 'm9-m1 bychain/rows/zcash/hullL', 'chains'),
])

row(18, None, [
    N_exact('p point', g(m9m1, 'm9_partial/p/point_L_unknown_not_omni'), R('M9/p/point_unknown_not_omni'), 6, 'm9-m1 m9_partial/p', 'M9/p'),
    N_exact('p L', g(m9m1, 'm9_partial/p/hull_L'), R('M9/p/L'), 6, 'm9-m1 m9_partial/p/hull_L', 'M9/p/L'),
    N_exact('p U', g(m9m1, 'm9_partial/p/hull_U'), R('M9/p/U'), 6, 'm9-m1 m9_partial/p/hull_U', 'M9/p/U'),
])
row(19, None, [
    N_exact('p_CS point', g(m9m1, 'm9_partial/p_CS/point_L_unknown_not_omni'), R('M9/p_CS/point_unknown_not_omni'), 6, 'm9-m1 m9_partial/p_CS', 'M9/p_CS'),
    N_exact('p_CS L', g(m9m1, 'm9_partial/p_CS/hull_L'), R('M9/p_CS/L'), 6, 'm9-m1 m9_partial/p_CS/hull_L', 'M9/p_CS/L'),
    N_exact('p_CS U', g(m9m1, 'm9_partial/p_CS/hull_U'), R('M9/p_CS/U'), 6, 'm9-m1 m9_partial/p_CS/hull_U', 'M9/p_CS/U'),
])
row(20, None, [
    N_exact('measured value per 30 days', g(m9m1, 'm9_partial/measured_value/per30d'), R('M9/measured_usd_per_30d/point'), 0, 'm9-m1 m9_partial/measured_value/per30d', 'M9/measured_usd_per_30d/point'),
])
row(21, None, [
    N_boot('non-Omni low per 30d', g(m9m1, 'm9_partial/non_omni/low_boot_seed1_per30d/0'), g(m9m1, 'm9_partial/non_omni/low_boot_seed2_per30d/0'), R('M9/non_omni_usd_per_30d/lo'), False, 'm9-m1 m9_partial/non_omni low boot', 'THESIS', sweep=(g(SW, 'nonomni_30d_whole_fixed/low_min'), g(SW, 'nonomni_30d_whole_fixed/low_max'))),
    N_boot('non-Omni high per 30d', g(m9m1, 'm9_partial/non_omni/high_boot_seed1_per30d/1'), g(m9m1, 'm9_partial/non_omni/high_boot_seed2_per30d/1'), R('M9/non_omni_usd_per_30d/hi'), False, 'm9-m1 m9_partial/non_omni high boot', 'THESIS', sweep=(g(SW, 'nonomni_30d_whole_fixed/high_min'), g(SW, 'nonomni_30d_whole_fixed/high_max'))),
])
row(22, None, [
    N_exact('c vs 2V (capped, 100.0%)', g(m9m1, 'm9_partial/c/vs_2V_capped'), R('M9/c_against_2V/point'), 6, 'm9-m1 m9_partial/c/vs_2V_capped', 'M9/c_against_2V/point'),
    N_exact('c vs V (3.70x)', g(m9m1, 'm9_partial/c/vs_V'), R('M9/c_against_V/point'), 6, 'm9-m1 m9_partial/c/vs_V', 'M9/c_against_V/point'),
    N_exact('headline point 0.827', g(m9m1, 'm9_partial/c/vs_headline'), R('M9/c_against_headline/point'), 6, 'm9-m1 m9_partial/c/vs_headline', 'M9/c_against_headline/point'),
])
_REFV = _ref()
if source_present(_NEARSTATS):
    row(23, None, [N_source("V = $831.3M, NearStats' 30-day swap volume (intents/timeframes/30d/volumeUsd)",
                            g(_ns, 'intents/timeframes/30d/volumeUsd'), _NEARSTATS, R('M9/V_usd'), 'M9/V_usd')])
else:
    row(23, None, [N_input('V = $831.3M', g(_REFV, 'V_usd'), R('M9/V_usd'), 'inputs/reference.json V_usd (NearStats, reported)', 'M9/V_usd')])
row(24, None, [
    N_exact('scenario S_L (=p L, c capped)', g(m9m1, 'm9_partial/scenarios/S_L'), R('M9/scenarios/S_L_unfavourable'), 6, 'm9-m1 m9_partial/scenarios/S_L', 'M9/scenarios/S_L_unfavourable'),
    N_exact('scenario S_U', g(m9m1, 'm9_partial/scenarios/S_U'), R('M9/scenarios/S_U_favourable'), 6, 'm9-m1 m9_partial/scenarios/S_U', 'M9/scenarios/S_U_favourable'),
])
_V2 = 2 * g(_ref(), 'V_usd') if is_num(g(_ref(), 'V_usd')) else MISSING   # 2V from inputs/reference.json
_nohi1 = g(m9m1, 'm9_partial/non_omni/high_boot_seed1_per30d/1')
_nohi2 = g(m9m1, 'm9_partial/non_omni/high_boot_seed2_per30d/1')
row(25, None, [
    N_boot('non-Omni upper end as x 2V (1.56)',
           (_nohi1 / _V2) if (is_num(_nohi1) and is_num(_V2)) else MISSING,
           (_nohi2 / _V2) if (is_num(_nohi2) and is_num(_V2)) else MISSING,
           R('M9/non_omni_usd_per_30d/share_of_2V/hi'), False,
           'm9-m1 non_omni high bootstrap / 2V', 'M9/non_omni_usd_per_30d/share_of_2V/hi'),
])
row(26, None, [
    N_boot('by-chain S_L', g(m9m1, 'bychain/S_L'), g(m9m1, 'bychain/S_L'), R('M9/by_chain_scenario/S_L_unfavourable'), True, 'm9-m1 bychain/S_L', 'M9/by_chain_scenario/S_L_unfavourable'),
    N_boot('by-chain S_U', g(m9m1, 'bychain/S_U'), g(m9m1, 'bychain/S_U'), R('M9/by_chain_scenario/S_U_favourable'), True, 'm9-m1 bychain/S_U', 'M9/by_chain_scenario/S_U_favourable'),
])

# row 27 BTC early [0, 96.3]; 28 BTC difference; 29 not completed
m10btc = g(c2b, 'm10/BTC') or {}
row(27, None, [
    N_exact('BTC early U (percent)', 100 * g(m10btc, 'early/amount/U') if is_num(g(m10btc, 'early/amount/U')) else MISSING, PAGE('[0.0%, 96.3%] in early', 1), 1, 'c2b-m10 m10/BTC/early/amount/U (x100)', 'THESIS'),
])
_bU = g(m10btc, 'early/amount/U')
_sw_min = g(SW, 'btc_90d_amount_lower/min')
_sw_max = g(SW, 'btc_90d_amount_lower/max')
_gap_min = (_sw_min - _bU) if (is_num(_sw_min) and is_num(_bU)) else MISSING
_gap_max = (_sw_max - _bU) if (is_num(_sw_max) and is_num(_bU)) else MISSING
row(28, None, [
    N_exact('BTC migration early upper end (96.3%)', 100 * _bU if is_num(_bU) else MISSING, PAGE('[0.0%, 96.3%] in early', 1), 1,
            'c2b-m10 m10/BTC/early/amount/U (x100)', 'THESIS'),
    N_boot('BTC late lower end (pub 99.7%)', g(m10btc, 'late/amount/bootstrap/1/boot_L'),
           g(m10btc, 'late/amount/bootstrap/2/boot_L'), R('C2b/BTC/readings/90d|amount|both/L'), True,
           'c2b-m10 m10/BTC/late bootstrap + 60-seed sweep btc_90d_amount_lower', 'tables',
           sweep=(_sw_min, _sw_max)),
    N_boot('TEST 5: gap, late lower end minus early upper end, in points (page 3.4)',
           100 * g(m10btc, 'difference/diff_L') if is_num(g(m10btc, 'difference/diff_L')) else MISSING,
           100 * (g(m10btc, 'late/amount/bootstrap/2/boot_L') - _bU) if (is_num(g(m10btc, 'late/amount/bootstrap/2/boot_L')) and is_num(_bU)) else MISSING,
           PAGE('they are only 3.4 points apart (96.3% against 99.7%)', 0), False,
           'c2b-m10 m10/BTC difference/diff_L (seed 1), late seed-2 lower end minus early upper end; sweep: 60-seed BTC 90-day lower end minus early upper end',
           'THESIS', sweep=((100 * _gap_min) if is_num(_gap_min) else MISSING, (100 * _gap_max) if is_num(_gap_max) else MISSING)),
    N_exact('TEST 5: reading at the lowest sweep seed (gap > 0 is "moving to Omni")',
            ('moving to Omni' if (is_num(_gap_min) and _gap_min > 0) else 'not moving'), R('M10/BTC/verdict'), 0,
            '60-seed sweep: smallest gap %s points' % (('%.4f' % (100 * _gap_min)) if is_num(_gap_min) else 'missing'),
            'results.json M10/BTC/verdict'),
    N_exact('BTC M10 verdict', g(m10btc, 'difference/state'),
            R('M10/BTC/verdict'), 0, 'c2b-m10 m10/BTC/difference/state', 'results.json M10/BTC/verdict'),
])
_M10_KEYS = [('SOL', 'SOL'), ('ZEC', 'ZEC'), ('ETH (POA control)', 'ETH')]
row(29, None, [
    N_exact('%s widening verdict' % pubk, g(c2b, 'm10/%s/difference/state' % indk),
            R('M10/%s/verdict' % pubk), 0,
            'c2b-m10 m10/%s/difference/state' % indk, 'results.json M10/%s/verdict' % pubk)
    for pubk, indk in _M10_KEYS
], page_text='| ETH (a POA control) | not completed | not completed | not completed |')
row(30, None, [N_notrecomp('chart 1 per-month route flows + the 28 completion cells',
      Pub(len(g(PUB, 'chart1_flows') or []), 'results'), 'results.json chart1_flows + completeness',
      'results.json chart1_flows publishes a per-month OMNI/POA/UNKNOWN USD total and the completion grid has '
      '28 cells, but no shipped family step produces matching per-month OMNI/POA/UNKNOWN route totals (the '
      'families output per-reading and per-chain figures, not per-month route splits), so this series is not '
      'recomputed here rather than asserted')])

# row 31 M10b 24 points
m10b = g(c2b, 'm10b') or {}
row(31, None, [
    *[N_exact('supply share %s' % _pt.get('point'), _pt.get('omni_share'),
              Pub(next((x.get('omni_share') for x in (g(PUB, 'M10b') or []) if x.get('point') == _pt.get('point')), MISSING), 'results'),
              6, 'c2b-m10 m10b/points[%s]/omni_share' % _pt.get('point'), 'results.json M10b[%s]/omni_share' % _pt.get('point'))
      for _pt in (g(m10b, 'points') or [])],
    *[N_exact('supply share on the page, %s (percent)' % _lbl,
              100 * next((x.get('omni_share') for x in (g(m10b, 'points') or []) if x.get('point') == _ptk), MISSING)
              if is_num(next((x.get('omni_share') for x in (g(m10b, 'points') or []) if x.get('point') == _ptk), MISSING)) else MISSING,
              PAGE('0.0% at the start of 2025, 66.3% in July 2025, 10.1% in March 2026, 69.8% on Nov 1, 2026 and 64.9% at T0', _i), 1,
              'c2b-m10 m10b/points[%s] (x100)' % _ptk, 'THESIS')
      for _lbl, _ptk, _i in [('start of 2025', '2025-01', 0), ('July 2025', '2025-07', 2), ('March 2026', '2026-03', 4), ('Nov 1, 2026', '2026-11', 6)]],
    N_exact('M10b T0 share (percent, 64.9%)', 100 * g(m10b, 't0_share') if is_num(g(m10b, 't0_share')) else MISSING, PAGE('64.9%', 0), 1, 'c2b-m10 m10b/t0_share (x100)', 'THESIS'),
], page_text='of all bridged BTC on NEAR, Omni holds 64.9%')

# row 32 October sign rate per day + Garwood + bootstrap
row(32, None, [
    N_exact('Oct rate/day', m3_month('2026-10', 'rate_per_day'), pub_m3_month('2026-10', 'raw/per_day'), 2, 'm3-m8-m7 m3/months/2026-10/rate_per_day', 'M3 2026-10'),
    N_exact('Oct Garwood lo', m3_month('2026-10', 'garwood_rate_lo'), pub_m3_month('2026-10', 'raw/garwood/0'), 2, 'm3-m8-m7 m3/months/2026-10/garwood_rate_lo', 'M3 2026-10'),
    N_exact('Oct Garwood hi', m3_month('2026-10', 'garwood_rate_hi'), pub_m3_month('2026-10', 'raw/garwood/1'), 2, 'm3-m8-m7 m3/months/2026-10/garwood_rate_hi', 'M3 2026-10'),
    N_boot('Oct bootstrap lo', m3_month('2026-10', 'boot_seed1/0'), m3_month('2026-10', 'boot_seed2/0'), pub_m3_month('2026-10', 'raw/boot/0'), False, 'm3-m8-m7 m3/months/2026-10 boot', 'M3 2026-10/raw/boot'),
    N_boot('Oct bootstrap hi', m3_month('2026-10', 'boot_seed1/1'), m3_month('2026-10', 'boot_seed2/1'), pub_m3_month('2026-10', 'raw/boot/1'), False, 'm3-m8-m7 m3/months/2026-10 boot', 'M3 2026-10/raw/boot'),
])
# row 33: every published M3 month compared cell by cell. The independent family output is the
# frozen one (it computes a number for every month); the published M3 applies the post-freeze
# "not completed" rule to 10 months, so those carry null and are compared only on completeness,
# while the complete months are compared exactly (bootstrap ends by the bootstrap rule).
_m3_nums = []
for _e in (g(PUB, 'M3') or []):
    _mo = _e.get('month')
    _pub_nc = g(_e, 'raw/not_completed') is True
    _pd = g(_e, 'raw/per_day')
    if _pub_nc or _pd is None or _pd is MISSING:
        continue  # published applied the not-completed rule; frozen family still has a number
    _m3_nums.append(N_exact('M3 %s per_day' % _mo, m3_month(_mo, 'rate_per_day'), pub_m3_month(_mo, 'raw/per_day'), 2, 'm3-m8-m7 m3/months/%s/rate_per_day' % _mo, 'results.json M3 %s raw/per_day' % _mo))
    _m3_nums.append(N_exact('M3 %s garwood lo' % _mo, m3_month(_mo, 'garwood_rate_lo'), pub_m3_month(_mo, 'raw/garwood/0'), 2, 'm3-m8-m7 m3/months/%s/garwood_rate_lo' % _mo, 'results.json M3 %s raw/garwood/0' % _mo))
    _m3_nums.append(N_exact('M3 %s garwood hi' % _mo, m3_month(_mo, 'garwood_rate_hi'), pub_m3_month(_mo, 'raw/garwood/1'), 2, 'm3-m8-m7 m3/months/%s/garwood_rate_hi' % _mo, 'results.json M3 %s raw/garwood/1' % _mo))
    _m3_nums.append(N_exact('M3 %s raw_count' % _mo, m3_month(_mo, 'raw_count'), pub_m3_month(_mo, 'raw/raw_count'), 0, 'm3-m8-m7 m3/months/%s/raw_count' % _mo, 'results.json M3 %s raw/raw_count' % _mo))
    _m3_nums.append(N_boot('M3 %s bootstrap lo' % _mo, m3_month(_mo, 'boot_seed1/0'), m3_month(_mo, 'boot_seed2/0'), pub_m3_month(_mo, 'raw/boot/0'), False, 'm3-m8-m7 m3/months/%s boot' % _mo, 'results.json M3 %s raw/boot/0' % _mo))
    _m3_nums.append(N_boot('M3 %s bootstrap hi' % _mo, m3_month(_mo, 'boot_seed1/1'), m3_month(_mo, 'boot_seed2/1'), pub_m3_month(_mo, 'raw/boot/1'), False, 'm3-m8-m7 m3/months/%s boot' % _mo, 'results.json M3 %s raw/boot/1' % _mo))
row(33, None, _m3_nums)

# row 34-36 trend
tr = g(s2, 'trend') or {}
row(34, None, [
    N_exact('trend raw point', g(tr, 'raw/point'), R('trend/raw/point'), 6, 'm4-m5-trend trend/raw/point', 'results.json trend/raw/point'),
    N_boot('trend raw lo', g(tr, 'raw/bootstrap/1/lo'), g(tr, 'raw/bootstrap/2/lo'), R('trend/raw/lo'), False, 'm4-m5-trend trend/raw boot', 'results.json trend/raw/lo'),
    N_boot('trend raw hi', g(tr, 'raw/bootstrap/1/hi'), g(tr, 'raw/bootstrap/2/hi'), R('trend/raw/hi'), False, 'm4-m5-trend trend/raw boot', 'results.json trend/raw/hi'),
])
row(35, None, [
    N_exact('trend no3_no2a point', g(tr, 'no3_no2a/point'), R('trend/excluding class 3 and 2a/point'), 6, 'm4-m5-trend trend/no3_no2a/point', 'results.json trend/excluding class 3 and 2a/point'),
    N_boot('trend no3_no2a lo', g(tr, 'no3_no2a/bootstrap/1/lo'), g(tr, 'no3_no2a/bootstrap/2/lo'), R('trend/excluding class 3 and 2a/lo'), False, 'm4-m5-trend trend/no3_no2a boot', 'results.json trend/excluding class 3 and 2a/lo'),
    N_boot('trend no3_no2a hi', g(tr, 'no3_no2a/bootstrap/1/hi'), g(tr, 'no3_no2a/bootstrap/2/hi'), R('trend/excluding class 3 and 2a/hi'), False, 'm4-m5-trend trend/no3_no2a boot', 'results.json trend/excluding class 3 and 2a/hi'),
])
row(36, None, [
    N_exact('trend no2a point', g(tr, 'no2a/point'), R('trend/excluding 2a only (class 3 kept)/point'), 6, 'm4-m5-trend trend/no2a/point', 'results.json trend/excluding 2a only (class 3 kept)/point'),
    N_boot('trend no2a lo', g(tr, 'no2a/bootstrap/1/lo'), g(tr, 'no2a/bootstrap/2/lo'), R('trend/excluding 2a only (class 3 kept)/lo'), False, 'm4-m5-trend trend/no2a boot', 'results.json trend/excluding 2a only (class 3 kept)/lo'),
    N_boot('trend no2a hi', g(tr, 'no2a/bootstrap/1/hi'), g(tr, 'no2a/bootstrap/2/hi'), R('trend/excluding 2a only (class 3 kept)/hi'), False, 'm4-m5-trend trend/no2a boot', 'results.json trend/excluding 2a only (class 3 kept)/hi'),
])

# row 37 October beyond infrastructure (M4 main / main_no_sweat for 2026-10)
m4oct = g(s2, 'M4/2026-10') or {}
row(37, None, [
    N_exact('Oct main_no_sweat point', g(m4oct, 'classifications/main_no_sweat'), pub_m45('2026-10', 'main_without_sweat/point'), 9, 'm4-m5-trend M4/2026-10/classifications/main_no_sweat', 'results.json M4_M5 2026-10 main_without_sweat/point'),
    N_exact('Oct main point', g(m4oct, 'classifications/main'), pub_m45('2026-10', 'main/point'), 9, 'm4-m5-trend M4/2026-10/classifications/main', 'results.json M4_M5 2026-10 main/point'),
])
# row 38 largest caller 34.0%; top3
m5oct = g(s2, 'M5/2026-10') or {}
row(38, None, [
    N_exact('top1 share', g(m5oct, 'top1/share'), pub_m45('2026-10', 'concentration/top1/point'), 9, 'm4-m5-trend M5/2026-10/top1/share', 'results.json M4_M5 2026-10 concentration/top1/point'),
    N_exact('top3 total share', g(m5oct, 'top3_share'), pub_m45('2026-10', 'concentration/top3/point'), 9, 'm4-m5-trend M5/2026-10/top3_share', 'results.json M4_M5 2026-10 concentration/top3/point'),
])
# row 39 class 4 (narrow) 3.5%
row(39, None, [
    N_exact('Oct narrow (class 4) point', g(m4oct, 'classifications/narrow'), pub_m45('2026-10', 'narrow/point'), 9, 'm4-m5-trend M4/2026-10/classifications/narrow', 'results.json M4_M5 2026-10 narrow/point'),
])
# row 40: every complete published M4_M5 month, each field mapped to the frozen family's own
# M4/M5 output (the nine class shares, the four classification ends, concentration top1/top3).
# A published point that is null/absent (the post-freeze rule leaves some month-fields empty) is
# skipped, not asserted.
_m40 = []
_m40_cls = [('narrow', 'classifications/narrow'), ('main', 'classifications/main'),
            ('broad', 'classifications/broad'), ('main_without_sweat', 'classifications/main_no_sweat'),
            ('broad_class3_as_5', 'broad_class3_to_5')]


def _n_2b(rules):
    """Class-2b signers the registry names: a rule of class 2b, or a 2b subclass inside a
    class-2 rule's subclass_by_transaction_signer (where the registry puts 2a and 2c)."""
    n = 0
    for r in rules:
        if str(r.get('class')) == '2b':
            n += 1
        for v in (r.get('subclass_by_transaction_signer') or {}).values():
            if isinstance(v, dict) and str(v.get('subclass')) == '2b':
                n += 1
    return n


_N2B = _n_2b(g(load(os.path.join(REPO, 'registry', 'callers.json')), 'rules') or [])


def _emit40(_lbl, _ind, _pubv, _src, _pw):
    if _pubv is MISSING or _pubv is None:
        return
    _m40.append(N_exact(_lbl, _ind, Pub(_pubv, 'results'), 9, _src, _pw))


for _e in (g(PUB, 'M4_M5') or []):
    if g(_e, 'complete') is not True:
        continue
    _mo = _e.get('month')
    _f4 = g(s2, 'M4/%s' % _mo)
    _f5 = g(s2, 'M5/%s' % _mo)
    if _f4 is MISSING or _f5 is MISSING:
        continue
    for _k in (g(_e, 'class_shares') or {}):
        _fk = '2_total' if _k == '2' else _k
        if _k == '2b':
            # the part types 0.0 for 2b; the 0 follows from the registry naming no 2b signer
            _emit40('M4_M5 %s class 2b' % _mo, 0.0 if _N2B == 0 else MISSING, g(_e, 'class_shares/2b/point'),
                    'compare.py: registry/callers.json names %d class-2b signers, so class 2b is 0 (DEVIATIONS 9)' % _N2B,
                    'results.json M4_M5 %s class_shares/2b' % _mo)
            continue
        _emit40('M4_M5 %s class %s' % (_mo, _k), g(_f4, 'shares/%s' % _fk),
            g(_e, 'class_shares/%s/point' % _k),
            'm4-m5-trend M4/%s/shares/%s' % (_mo, _fk), 'results.json M4_M5 %s class_shares/%s' % (_mo, _k))
    for _pf, _ff in _m40_cls:
        _emit40('M4_M5 %s %s' % (_mo, _pf), g(_f4, _ff), g(_e, '%s/point' % _pf),
            'm4-m5-trend M4/%s/%s' % (_mo, _ff), 'results.json M4_M5 %s %s/point' % (_mo, _pf))
    _emit40('M4_M5 %s top1' % _mo, g(_f5, 'top1/share'), g(_e, 'concentration/top1/point'),
        'm4-m5-trend M5/%s/top1/share' % _mo, 'results.json M4_M5 %s concentration/top1/point' % _mo)
    _emit40('M4_M5 %s top3' % _mo, g(_f5, 'top3_share'), g(_e, 'concentration/top3/point'),
        'm4-m5-trend M5/%s/top3_share' % _mo, 'results.json M4_M5 %s concentration/top3/point' % _mo)
if not _m40:
    _m40 = [N_notrecomp('M4_M5 per-month fields', MISSING, 'results.json M4_M5',
            'no complete published M4_M5 month resolved against the family output')]
row(40, None, _m40)
row(41, None, [
    N_exact('broad-adoption Oct', g(m4oct, 'classifications/main_no_sweat'), pub_m45('2026-10', 'main_without_sweat/point'), 9, 'm4-m5-trend M4/2026-10 main_no_sweat', 'results.json M4_M5 2026-10 main_without_sweat/point'),
])
# row 42 M6: 12 calls + 13 months shares agree; intervals NOT recomputed
m6oct = g(s2, 'M6/2026-10') or {}
row(42, None, [
    N_exact('M6 Oct sampled sign calls (12)', g(m6oct, 'n_sampled_sign_calls'), PAGE("October's held 12", 0), 0, 'm4-m5-trend M6/2026-10/n_sampled_sign_calls', 'THESIS'),
    N_exact('M6 Oct FastAuth-login share (percent, 58.3%)', 100 * g(m6oct, 'shares/ed25519_fastauth_jwt') if is_num(g(m6oct, 'shares/ed25519_fastauth_jwt')) else MISSING, PAGE('Of the 12, 58.3%', 1), 1, 'm4-m5-trend M6/2026-10/shares (x100)', 'THESIS'),
    N_notrecomp('M6 Oct CI [30.0%,87.5%] etc', MISSING, 'THESIS', 'discrete MC intervals are not produced by shipped family code (hand/block bootstrap)'),
])
# row 43 HSP-007 totals (needs source)
has_hsp = g(s1, 'hsp007_totals') is not MISSING and g(s1, 'hsp007_totals') is not None
def hsp_mainnet(month, status):
    v = g(s1, 'hsp007_totals/%s/mainnet/%s/sum' % (month, status))
    return v
if has_hsp:
    # executed Mar-Sep mainnet+testnet = 338436.08; from ledger totals
    led_exec = R('M8/totals/executed_near')
    row(43, None, [
        N_exact('executed Mar-Sep', round(sum(g(s1, 'hsp007_totals/%s/%s/executed/sum' % (m, net)) or 0
                                              for m in ('2026-03', '2026-04', '2026-05', '2026-06', '2026-07', '2026-08', '2026-09')
                                              for net in ('mainnet', 'testnet')
                                              if is_num(g(s1, 'hsp007_totals/%s/%s/executed/sum' % (m, net)))), 6),
                led_exec, 2, 'm3-m8-m7 hsp007_totals/<2026-03..09>/<mainnet,testnet>/executed/sum (summed)', 'M8/totals/executed_near'),
        N_exact('pending', round(sum(g(s1, 'hsp007_totals/%s/%s/pending/sum' % (m, net)) or 0
                                     for m in ('2026-03', '2026-04', '2026-05', '2026-06', '2026-07', '2026-08', '2026-09')
                                     for net in ('mainnet', 'testnet')
                                     if is_num(g(s1, 'hsp007_totals/%s/%s/pending/sum' % (m, net)))), 6),
                R('M8/totals/pending_near'), 2, 'm3-m8-m7 hsp007_totals/<2026-03..09>/<mainnet,testnet>/pending/sum (summed)', 'M8/totals/pending_near'),
        N_exact('October proposed', round(sum(g(s1, 'hsp007_totals/2026-10/%s/proposed/sum' % net)
                                              for net in ('mainnet', 'testnet')
                                              if is_num(g(s1, 'hsp007_totals/2026-10/%s/proposed/sum' % net))), 6),
                PAGE('76,864.52 NEAR for 2026-10', 0), 2, 'm3-m8-m7 hsp007_totals/2026-10/<mainnet,testnet>/proposed/sum', 'page sentence (76,864.52 NEAR)'),
    ])
    oct_npr = g(s1, 'm8/2026-09/near_per_request')
    row(44, None, [
        N_exact('Sep NEAR/request', g(s1, 'm8/2026-09/near_per_request'), PAGE('the figures are 0.0702, 0.0820 and 0.1065', 2), 4, 'm3-m8-m7 m8/2026-09/near_per_request', 'THESIS'),
    ])
    row(45, None, [
        N_exact('July NEAR/req (pooled)', g(s1, 'm8/2026-07/near_per_request'), PAGE('the figures are 0.0702, 0.0820 and 0.1065', 0), 4, 'm3-m8-m7 m8/2026-07', 'THESIS'),
        N_exact('Aug NEAR/req (pooled)', g(s1, 'm8/2026-08/near_per_request'), PAGE('the figures are 0.0702, 0.0820 and 0.1065', 1), 4, 'm3-m8-m7 m8/2026-08', 'THESIS'),
        N_exact('June NEAR/req (pooled)', g(s1, 'm8/2026-06/near_per_request'),
                Pub(next((x.get('per_request_executed_plus_pending', {}).get('point') for x in (g(PUB, 'M8/months') or []) if x.get('month') == '2026-06'), MISSING), 'results'),
                4, 'm3-m8-m7 m8/2026-06/near_per_request', 'results.json M8/months[2026-06]/per_request_executed_plus_pending/point'),
    ])
else:
    SRCF = 'gov-hsp007-execution-42147.json'
    row(43, None, [N_needs('executed/pending/proposed', SRCF, R('M8/totals/executed_near'), 'M8/totals')])
    row(44, None, [N_needs('Sep NEAR/request', SRCF, PAGE('0.1065 NEAR in September', 0), 'THESIS')])
    row(45, None, [N_needs('Jun/Jul/Aug NEAR/request', SRCF, PAGE('the figures are 0.0702, 0.0820 and 0.1065', 0), 'THESIS')])

row(46, None, [
    N_exact('July calls (744,017)', m3_month('2026-07', 'ht_total'), PAGE('from 744,017 to 688,516', 0), 0, 'm3-m8-m7 m3/months/2026-07/ht_total', 'THESIS'),
    N_exact('Sep calls (688,516)', m3_month('2026-09', 'ht_total'), PAGE('from 744,017 to 688,516', 1), 0, 'm3-m8-m7 m3/months/2026-09/ht_total', 'THESIS'),
])
# row 47 of the first comparison is retired: it compared a figure (16 operators on Nov 1) that is
# printed neither on the page nor in the published results.
_dep = g(s1, 'm3/deposits')
_dep = _dep if isinstance(_dep, dict) else {}
_one_yocto = _dep.get('1', MISSING)
_dep_total = sum(_dep.values()) if _dep else MISSING
_P48 = page_nums('4,013 of 4,058 sampled calls attached exactly that') or []
row(48, None, [
    N_exact('1-yoctoNEAR deposits', _one_yocto, PAGE('4,013 of 4,058 sampled calls', 0), 0,
            'm3-m8-m7 m3/deposits["1"]', 'page sentence (4,013 of 4,058)'),
    N_exact('sampled deposit calls total', _dep_total, PAGE('4,013 of 4,058 sampled calls', 1), 0,
            'm3-m8-m7 sum(m3/deposits)', 'page sentence (4,013 of 4,058)'),
], page_text='4,013 of 4,058 sampled calls attached exactly that')

# row 49 M7
m7 = g(s1, 'm7') or {}
row(49, None, [
    N_exact('M7 evaluated', g(m7, 'evaluated'), R('M7/evaluated'), 0, 'm3-m8-m7 m7/evaluated', 'M7/evaluated'),
    N_exact('M7 matched', g(m7, 'matched'), R('M7/matched'), 0, 'm3-m8-m7 m7/matched', 'M7/matched'),
    N_exact('M7 censored', g(m7, 'censored'), R('M7/censored'), 0, 'm3-m8-m7 m7/censored', 'M7/censored'),
    N_exact('M7 matched share', g(m7, 'matched_share'), R('M7/matched_share'), 6, 'm3-m8-m7 m7/matched_share', 'M7/matched_share'),
    N_exact('M7 median delay', g(m7, 'median_delay_s'), R('M7/median_delay_s'), 3, 'm3-m8-m7 m7/median_delay_s', 'M7/median_delay_s'),
    N_exact('M7 longest delay', g(m7, 'longest_delay_s'), R('M7/max_delay_s'), 3, 'm3-m8-m7 m7/longest_delay_s', 'M7/max_delay_s'),
])
# row 50 destination audit
aud = g(s1, 'dest_audit_check') or {}
_P50 = page_nums('On 4 of the Zcash withdrawals no value went to another transparent address') or []
row(50, None, [
    N_exact('BTC audit found', g(aud, 'per_chain/BITCOIN/found'), PAGE('Bitcoin, 10 of 10 found', 0), 0, 'm3-m8-m7 dest_audit_check/per_chain/BITCOIN/found', 'THESIS'),
    N_exact('ZEC audit found', g(aud, 'per_chain/ZCASH/found'), PAGE('Zcash, 10 of 10 found', 0), 0, 'm3-m8-m7 dest_audit_check/per_chain/ZCASH/found', 'THESIS'),
    N_exact('ZEC withdrawals with no value to another transparent address',
            g(PE, 'zec_no_value_to_other_transparent_address'), PAGE('On 4 of the Zcash withdrawals no value', 0), 0,
            'page_extras zec_no_value_to_other_transparent_address', 'page sentence (4 of the Zcash withdrawals)'),
], page_text='On 4 of the Zcash withdrawals no value went to another transparent address')

# row 51: the five frozen tests, each recomputed from the readings by the DEVIATIONS item-21
# thresholds, then compared to the published verdict in results.json "mind".
_share_nonomni = (max(_nohi1, _nohi2) / _V2) if (is_num(_nohi1) and is_num(_nohi2) and is_num(_V2)) else MISSING
_ba = [g(s2, 'M4/%s/classifications/main_no_sweat' % mo) for mo in ('2026-08', '2026-09', '2026-10')]
_npr = [g(s1, 'm8/%s/near_per_request' % mo) for mo in ('2026-07', '2026-08', '2026-09')]
_states = [g(c2b, 'm10/%s/difference/state' % k) for k in ('BTC', 'SOL', 'ZEC')]


def _met_value_mostly_on_omni():
    if not is_num(_pL) or not is_num(_share_nonomni):
        return MISSING
    return bool(_pL >= 0.90 and _share_nonomni < 0.10)


def _met_dominant_widely():
    dy = g(m9m1, 'm1_dominant/dominant_yes')
    return bool(dy >= 5) if is_num(dy) else MISSING


def _met_broad_adoption():
    """Each of Aug, Sep, Oct 2026: main without Sweat at least 25% with its lower end at least 15%.
    DEVIATIONS 21: a decided (completed, stable) month that fails either condition fails the
    test; otherwise an undecided month leaves the test undecided."""
    months = ('2026-08', '2026-09', '2026-10')
    decided = [g(s2, 'M4/%s/completed' % mo) is True and
               not any(g(s2, 'M4/%s/bootstrap/main_no_sweat/%d/unstable' % (mo, sd)) for sd in (1, 2))
               for mo in months]
    los = []
    for mo in months:
        pair = [g(s2, 'M4/%s/hull/main_no_sweat/%d/interval/0' % (mo, sd)) for sd in (1, 2)]
        los.append(min(pair) if all(is_num(x) for x in pair) else MISSING)
    for d, x, lo in zip(decided, _ba, los):
        if d and ((is_num(x) and x < 0.25) or (is_num(lo) and lo < 0.15)):
            return False
    if not all(decided) or any(not is_num(x) for x in _ba) or any(not is_num(lo) for lo in los):
        return MISSING
    return True


def _met_falling_spend():
    """NEAR per request falling Jul > Aug > Sep 2026, each interval wholly below the one before,
    while the trend grows. DEVIATIONS 21: two final months that already fail settle the test;
    a provisional month otherwise leaves it undecided. A trend whose interval straddles 1 is
    not growing; an unstable one leaves the test undecided."""
    months = ('2026-07', '2026-08', '2026-09')
    final = [g(s1, 'm8/%s/provisional' % mo) is False for mo in months]
    ivs = []
    for mo in months:
        a, b = g(s1, 'm8/%s/ci_seed1' % mo), g(s1, 'm8/%s/ci_seed2' % mo)
        ivs.append((min(a[0], b[0]), max(a[1], b[1])) if (isinstance(a, list) and isinstance(b, list)) else MISSING)
    for k in (1, 2):
        if final[k - 1] and final[k] and is_num(_npr[k - 1]) and is_num(_npr[k]):
            if not _npr[k] < _npr[k - 1]:
                return False
            if ivs[k] is not MISSING and ivs[k - 1] is not MISSING and not ivs[k][1] < ivs[k - 1][0]:
                return False
    if not all(final) or any(not is_num(x) for x in _npr) or any(iv is MISSING for iv in ivs):
        return MISSING
    rd = [g(s2, 'trend/raw/bootstrap/%d/reading' % sd) for sd in (1, 2)]
    if any(r == 'inconclusive (unstable)' for r in rd):
        return MISSING
    return bool(all(r == 'growing' for r in rd))


def _met_no_migration():
    if any(s is MISSING for s in _states):
        return MISSING
    return bool(not any(s == 'moving to Omni' for s in _states))


_pL = g(m9m1, 'm9_partial/p/hull_L')
row(51, None, [
    N_exact('test: value mostly on Omni', _met_value_mostly_on_omni(), R('mind/value_mostly_on_omni/met'), 0, 'readings: p_L >= 0.90 and non-Omni upper end < 10% of 2V', 'results.json mind/value_mostly_on_omni/met'),
    N_exact('test: Omni dominant widely', _met_dominant_widely(), R('mind/omni_dominant_widely/met'), 0, 'readings: dominant on >= 5 of 8', 'results.json mind/omni_dominant_widely/met'),
    N_exact('test: broad adoption', _met_broad_adoption(), R('mind/broad_adoption/met'), 0, 'readings: Aug/Sep/Oct main-no-Sweat each >= 25% with lower end >= 15% (a stable, completed month under 25% fails)', 'results.json mind/broad_adoption/met'),
    (N_exact('test: falling spend per request', _met_falling_spend(), R('mind/falling_spend_per_request/met'), 0, 'readings: NEAR/request Jul>Aug>Sep, each interval wholly below the one before, while the raw trend grows', 'results.json mind/falling_spend_per_request/met')
     if has_hsp else
     N_needs('test: falling spend per request', 'gov-hsp007-execution-42147.json', R('mind/falling_spend_per_request/met'), 'results.json mind/falling_spend_per_request/met')),
    N_exact('test: no migration', _met_no_migration(), R('mind/no_migration/met'), 0, 'readings: no "moving to Omni" for BTC/SOL/ZEC', 'results.json mind/no_migration/met'),
], page_text='All five frozen tests read not met; none was met and none is undecided.')

_SVRN_SRC = 'gov-hsp007-execution-42147.json'
_SWEAT = 'web-update.swe.at_.html'
_t52a = 'onboarded on June 22, 2026'
_t52b = 'that app ends in its present form on Dec 30, 2026'
_r52 = []
if source_present(_SVRN_SRC):
    _m = re.search(r'SVRN was successfully onboarded to mainnet on ([A-Z][a-z]+ \d{1,2}, \d{4})', thread_text(_SVRN_SRC))
    _r52.append(N_source("SVRN's mainnet onboarding date, by the thread's own report", iso_date(_m.group(1)) if _m else MISSING,
                         _SVRN_SRC, PAGEDATE(_t52a), 'THESIS'))
else:
    _r52.append(N_needs("SVRN's mainnet onboarding date, by the thread's own report", _SVRN_SRC, PAGEDATE(_t52a), 'THESIS'))
if source_present(_SWEAT):
    _m = re.search(r'Sweat Wallet and SWEAT in their present form will end on (\d{1,2} [A-Z][a-z]+ \d{4})', source_text(_SWEAT))
    _r52.append(N_source('the date Sweat Wallet ends in its present form, by its notice', iso_date(_m.group(1)) if _m else MISSING,
                         _SWEAT, PAGEDATE(_t52b), 'THESIS'))
else:
    _r52.append(N_needs('the date Sweat Wallet ends in its present form, by its notice', _SWEAT, PAGEDATE(_t52b), 'THESIS'))
row(52, None, _r52)

# ---- Rows 53-64 ----
row(53, None, [
    N_exact("the bound's arithmetic for the page's example of three all-Omni windows, 0.025^(1/3) (percent, 29%)", 100 * g(PE, 'cp_all_success_m3') if is_num(g(PE, 'cp_all_success_m3')) else MISSING, PAGE('lower bound of 29%', 0), 0, 'checks/page_extras cp_all_success_m3 (x100)', 'THESIS'),
])
row(54, None, [
    N_exact('BTC Omni-token 90-day windows (twelve)', (g(PE, 'btc_omni_token_90d_windows/claim') or 0) + (g(PE, 'btc_omni_token_90d_windows/outside') or 0),
            PAGEWORD('rests on twelve windows of the Omni token', 'twelve'), 0, 'checks/page_extras btc_omni_token_90d_windows (claim + outside)', 'THESIS'),
    N_exact('of them inside the claim window (six)', g(PE, 'btc_omni_token_90d_windows/claim'),
            PAGEWORD('six inside the claim window', 'six'), 0, 'checks/page_extras btc_omni_token_90d_windows/claim', 'THESIS'),
    N_exact('of them outside it (six)', g(PE, 'btc_omni_token_90d_windows/outside'),
            PAGEWORD('and six outside it', 'six'), 0, 'checks/page_extras btc_omni_token_90d_windows/outside', 'THESIS'),
])
# row 55: six readings; 10 to 20 windows each; effective windows between one and three (all agree)
import math as _math
_u16 = [g(m9m1, 'm1_dominant/chains/%s/groups/%s/U' % (c, u)) for c, u in
        [('Arbitrum', 'USD'), ('Base', 'USD'), ('Ethereum', 'ETH'),
         ('Ethereum', 'USD'), ('Tron', 'USD'), ('XRP', 'XRP')]]
eff = [_math.log(0.025) / _math.log(1 - U) for U in _u16 if is_num(U) and 0 < U < 1]
eff_lo, eff_hi = (min(eff), max(eff)) if eff else (MISSING, MISSING)
wpr = g(PE, 'evm_tron_xrp_windows_per_reading_range')
row(55, None, [
    N_exact('readings on these chains (six)', g(PE, 'evm_tron_xrp_readings'),
            PAGEWORD('These five chains have six readings', 'six'), 0, 'checks/page_extras evm_tron_xrp_readings', 'THESIS'),
    N_exact('windows per reading range (10 to 20)', wpr, PAGES('rests on 10 to 20 windows'), 0,
            'checks/page_extras evm_tron_xrp_windows_per_reading_range', 'THESIS'),
    {'label': 'effective windows "between one and three"', 'kind': 'exact',
     'status': ('agree' if (is_num(eff_lo) and eff_lo >= 1.0 and eff_hi <= 3.0
                            and PAGEPHRASE('between one and three').v is not MISSING) else 'differs'),
     'rule': ('effective-window range [%.4f, %.4f] within one..three' % (eff_lo, eff_hi)
              if is_num(eff_lo) else 'missing'),
     'published': PAGEPHRASE('between one and three').v, 'published_source_kind': 'page',
     'independent': [eff_lo, eff_hi] if is_num(eff_lo) else None,
     'source': 'm1_dominant/chains/<Chain>/groups/<unit>/U -> m=ln(0.025)/ln(1-U)',
     'published_where': 'THESIS'},
], page_text={'readings': 'six readings',
              'windows_per_reading': 'each reading rests on 10 to 20 windows',
              'effective_windows': 'between one and three'})
row(56, None, [
    N_boot('bootstrap-alone p L (25.2%)', g(m9m1, 'm9_partial/p/bootstrap_seed1_lo'), g(m9m1, 'm9_partial/p/bootstrap_seed2_lo'), R('M9/p/reading_L/boot/0'), True, 'm9-m1 m9_partial/p bootstrap', 'results.json M9/p/reading_L/boot/0'),
    N_boot('bootstrap-alone p U (57.3%)', g(m9m1, 'm9_partial/p/bootstrap_seed1_hi'), g(m9m1, 'm9_partial/p/bootstrap_seed2_hi'), R('M9/p/reading_L/boot/1'), True, 'm9-m1 m9_partial/p bootstrap', 'results.json M9/p/reading_L/boot/1'),
])
row(57, None, [
    N_exact('measured chains cover 88.3% of V', g(m9m1, 'bychain/c'), R('M9/by_chain_scenario/c'), 3, 'm9-m1 bychain/c', 'THESIS'),
])
if source_present(_NEARSTATS):
    row(58, None, [N_source("NEAR headline $3,714.7M, NearStats' 30-day total (intents/totals/volume30dUsd)",
                            g(_ns, 'intents/totals/volume30dUsd'), _NEARSTATS, R('M9/V_headline_usd'), 'M9/V_headline_usd')])
else:
    row(58, None, [N_input('NEAR headline $3,714.7M', g(_REFV, 'V_headline_usd'), R('M9/V_headline_usd'),
                           'inputs/reference.json V_headline_usd (NearStats, reported)', 'M9/V_headline_usd')])
# row 59 early BTC transfers 45, in 6 of 16 early windows, effective 1.1
row(59, None, [
    N_exact('early BTC distinct transfers (45)', g(m10btc, 'early/amount/distinct'), PAGE('45 early BTC transfers in 6 of the 16', 0), 0, 'c2b-m10 m10/BTC/early/amount/distinct', 'THESIS'),
    N_exact('early BTC windows with transfer (6)', g(m10btc, 'early/amount/windows_with_transfer'), PAGE('45 early BTC transfers in 6 of the 16', 1), 0, 'c2b-m10 m10/BTC/early/amount/windows_with_transfer', 'THESIS'),
    N_exact('early BTC windows total (16)', g(PE, 'btc_early_windows'), PAGE('45 early BTC transfers in 6 of the 16', 2), 0, 'checks/page_extras btc_early_windows', 'THESIS'),
])
row(60, None, [
    N_exact('blocks per month (150)', (g(PE, 'nd_blocks_per_month') or [None])[0], PAGE('150 random blocks', 0), 0, 'checks/page_extras nd_blocks_per_month', 'THESIS'),
])
# row 61 testnet executed/pending (needs source)
if has_hsp:
    row(61, None, [
        N_exact('testnet executed 10,317.00', sum(g(s1, 'hsp007_totals/%s/testnet/executed/sum' % mo) or 0 for mo in ('2026-06','2026-07','2026-08')), PAGE('10,317.00 NEAR executed and 1,536.40 pending', 0), 2, 'm3-m8-m7 hsp007_totals testnet', 'THESIS'),
        N_exact('testnet pending 1,536.40', g(s1, 'hsp007_totals/2026-08/testnet/pending/sum'), PAGE('10,317.00 NEAR executed and 1,536.40 pending', 1), 2, 'm3-m8-m7 hsp007_totals/2026-08/testnet/pending', 'THESIS'),
    ])
else:
    row(61, None, [N_needs('testnet executed/pending', 'gov-hsp007-execution-42147.json', PAGE('10,317.00 NEAR executed and 1,536.40 pending', 0), 'THESIS')])
# row 62 October 435,432 calls [335,044, 544,604]
oct_ht = m3_month('2026-10', 'ht_total')
oct_days = m3_month('2026-10', 'days')
b1 = m3_month('2026-10', 'boot_seed1')
b2 = m3_month('2026-10', 'boot_seed2')
def htboot(b, days, i):
    return (b[i] * days) if (b is not MISSING and days is not MISSING) else MISSING
row(62, None, [
    N_exact('October calls total (435,432)', oct_ht, PAGE('435,432 calls [335,044, 544,604]', 0), 0, 'm3-m8-m7 m3/months/2026-10/ht_total', 'THESIS'),
    N_boot('October calls bootstrap lo', htboot(b1, oct_days, 0), htboot(b2, oct_days, 0), PAGE('435,432 calls [335,044, 544,604]', 1), False, 'm3-m8-m7 m3/months/2026-10 boot*days', 'THESIS'),
    N_boot('October calls bootstrap hi', htboot(b1, oct_days, 1), htboot(b2, oct_days, 1), PAGE('435,432 calls [335,044, 544,604]', 2), False, 'm3-m8-m7 m3/months/2026-10 boot*days', 'THESIS'),
])
# row 63 Zcash audit signer addresses / inputs
row(63, None, [
    N_exact('ZEC signer addresses (five)', g(PE, 'zec_signer_addresses'),
            PAGEWORD('outside the five signer addresses this audit knows', 'five'), 0, 'checks/page_extras zec_signer_addresses', 'THESIS'),
    N_exact('ZEC picks mostly from outside (4)', g(PE, 'zec_most_input_from_outside_known'), PAGE('In 4 of the 10 Zcash picks', 0), 0, 'checks/page_extras zec_most_input_from_outside_known', 'THESIS'),
    N_exact('ZEC picks all from known (6)', g(PE, 'zec_all_inputs_from_known'), PAGE('In the other 6 every input', 0), 0, 'checks/page_extras zec_all_inputs_from_known', 'THESIS'),
    N_exact('ZEC 74bd9e36: input from the signer address (392,500 zat)', g(PE, 'zec_inputs/74bd9e36c001/from_own_signer'),
            PAGE('supplied 392,500 of 739,392,500', 0), 0, 'checks/page_extras zec_inputs/74bd9e36c001/from_own_signer', 'THESIS'),
    N_exact('ZEC 74bd9e36: all transparent input (739,392,500 zat)', g(PE, 'zec_inputs/74bd9e36c001/total_in'),
            PAGE('supplied 392,500 of 739,392,500', 1), 0, 'checks/page_extras zec_inputs/74bd9e36c001/total_in', 'THESIS'),
])
# row 64 Monte Carlo sentence. The page sentence is the read-whole-fixed one, so use the
# whole_fixed sweep variant (not whole_resampled). Both numbers are computed by shipped mc-seeds
# code, so they "agree" when they round to the page's figures.
_sw_lowmin = g(SW, 'nonomni_30d_whole_fixed/low_min')
_sw_lowmax = g(SW, 'nonomni_30d_whole_fixed/low_max')
_sw_btcmin = g(SW, 'btc_90d_amount_lower/min')
_sw_btcmax = g(SW, 'btc_90d_amount_lower/max')
_ind_lowB = [round(_sw_lowmin / 1e9, 2), round(_sw_lowmax / 1e9, 2)] if (is_num(_sw_lowmin) and is_num(_sw_lowmax)) else MISSING
_ind_btcpct = [round(_sw_btcmin * 100, 2), round(_sw_btcmax * 100, 2)] if (is_num(_sw_btcmin) and is_num(_sw_btcmax)) else MISSING
_pg_low = page_nums('non-Omni lower end ran from $1.11B to $1.17B')
_pg_btc = page_nums('lower end ran from 99.68% to 99.77%')
row(64, None, [
    N_exact('non-Omni lower end $B over 40 seeds (whole_fixed)', _ind_lowB, PAGES('non-Omni lower end ran from $1.11B to $1.17B'), 0,
            'mc-seeds/sweep.json nonomni_30d_whole_fixed low_min/low_max -> $B, 2dp', 'page sentence ($1.11B to $1.17B)'),
    N_exact('BTC 90d lower end % over 60 seeds', _ind_btcpct, PAGES('lower end ran from 99.68% to 99.77%'), 0,
            'mc-seeds/sweep.json btc_90d_amount_lower min/max -> %, 2dp', 'page sentence (99.68% to 99.77%)'),
], page_text="over 40 seeds the non-Omni lower end ran from $1.11B to $1.17B, and over 60 seeds Bitcoin's 90-day lower end ran from 99.68% to 99.77%")


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------
def row_status(numbers):
    return max(numbers, key=lambda n: WEAK[n['status']])['status']


def row_section(r):
    """Section(s) for a row, discovered from THESIS.md at run time. Returns (section_str,
    page_text_not_found). With a page_text, lists every heading the text sits under (or
    'front matter'); if the text is not in THESIS.md, flags it. With no page_text, says
    whether the row's published values are tables-only or results-only."""
    pt = r['page_text']
    subs = [pt] if isinstance(pt, str) else (list(pt.values()) if isinstance(pt, dict) else (list(pt) if isinstance(pt, list) else []))
    if subs:
        found, missing = [], False
        for s in subs:
            sec = thesis_sections(s)
            if sec is None:
                missing = True
            else:
                for part in sec.split('; '):
                    if part not in found:
                        found.append(part)
        if missing:
            return 'page text not found', True
        return '; '.join(found), False
    wheres = ' '.join((n.get('published_where') or '') for n in r['numbers']).lower()
    tables_only = ('tables' in wheres and not any(w in wheres for w in
                   ('results', 'combined', 'm9', 'm3', 'm1', 'm7', 'm8')))
    if 'data/nb/' in wheres:
        return 'not on the page (data/nb/RESOLVED)', False
    return ('not on the page (tables.md)' if tables_only else 'not on the page (results.json)'), False


PAGE_NOT_FOUND = {'label': 'page text not found', 'kind': 'differs', 'status': 'differs',
                  'rule': 'page_text is not an exact substring of the current THESIS.md; the page '
                          'may have changed', 'published': None, 'independent': None,
                  'source': 'THESIS.md', 'published_where': 'THESIS.md'}

rows_out = []
status_rows = {k: 0 for k in WEAK}
status_nums = {k: 0 for k in WEAK}
max_gap = 0.0
for r in ROWS:
    sec, notfound = row_section(r)
    if notfound:
        r['numbers'] = list(r['numbers']) + [dict(PAGE_NOT_FOUND)]
    rs = row_status(r['numbers'])
    status_rows[rs] += 1
    for n in r['numbers']:
        status_nums[n['status']] += 1
    rows_out.append({'row': r['row'], 'section': sec, 'status': rs,
                     'page_text': r['page_text'], 'numbers': r['numbers']})

# Every published value must reach a number builder through one of the readers above
# (R, C, TBL, PAGE, PAGEWORD, PAGEPHRASE, PAGEDATE, PCHAIN...), which tag it with the file it
# came from. A bare number has no tag, so this stops a value typed by mistake; it cannot stop
# one deliberately wrapped by hand, which is why the readers are few and short.
_untagged = [(r['row'], n['label']) for r in rows_out for n in r['numbers']
             if n.get('published') is not None and
             n.get('published_source_kind') not in ('results', 'combined', 'tables', 'page', 'data')]
if _untagged:
    sys.stderr.write('UNTAGGED / TYPED published values (no file source):\n')
    for rn, lab in _untagged:
        sys.stderr.write('  row %s: %s\n' % (rn, lab))
    sys.exit(3)

# bootstrap largest relative gap (for stdout)
for r in ROWS:
    for n in r['numbers']:
        if n['kind'] == 'bootstrap' and n['status'] == 'agree' and 'tol=' in (n['rule'] or ''):
            try:
                gap = float(n['rule'].split('|p-nearer seed|=')[1].rstrip(')'))
                pub = n['published']
                if is_num(pub) and pub:
                    max_gap = max(max_gap, abs(gap) / abs(pub))
            except Exception:
                pass

A = status_rows['agree']
B = status_rows['source check']
C = status_rows['needs source file']
D = status_rows['not recomputed']
E = status_rows['differs']

compare_json = {
    'total_rows': len(ROWS),
    'rows_by_status': status_rows,
    'numbers_by_status': status_nums,
    'python_version': sys.version,
    'numpy_version': __import__('numpy').__version__,
    'published_results_sha256': sha256(os.path.join(PUB_DIR, 'results.json')),
    'published_tables_sha256': sha256(TABLES_PATH),
    'combined_sha256': sha256(os.path.join(REPO, 'out', 'combined.json')),
    'thesis_sha256': sha256(THESIS_PATH),
    'sources_present': bool(SOURCES_DIR),
    'sources_used': sorted(nm for nm in SOURCES if source_present(nm)),
    'rows': rows_out,
}
# A run with a sources folder writes its own pair of files, so the run from a bare clone
# (RESULTS.md, out/compare.json) is never overwritten by one that used the saved copies.
_SUFFIX = '-with-sources' if SOURCES_DIR else ''
json.dump(compare_json, open(os.path.join(HERE, 'out', 'compare%s.json' % _SUFFIX), 'w'), indent=1, sort_keys=True)

# RESULTS.md
L = ['# Independent re-derivation vs the published thesis numbers', '',
     'Generated by `compare.py` (deterministic). Published numbers are read from four files: '
     '`out/published/results.json`, `out/published/tables.md`, `out/combined.json`, and the page '
     '`THESIS.md` (values parsed from the sentence a row quotes); independent numbers come from '
     'this run\'s family outputs in `out/`. Section names are discovered from `THESIS.md` at run '
     'time (sha256 `%s`).' % sha256(THESIS_PATH), '',
     *(['This run was given a folder of source files; it used those whose sha256 matches '
        '`sources.json`: %s.' % (', '.join('`%s`' % nm for nm in sorted(SOURCES) if source_present(nm)) or 'none'), '']
       if SOURCES_DIR else
       ['This run had no source files. The rows that need one are listed at the end, with each '
        "file's URL and the sha256 of the copy saved on 2026-11-09.", '']),
     '| row | section | status | published | independent | rule / source |',
     '|---|---|---|---|---|---|']


def fmt(v):
    if v is None:
        return ''
    if isinstance(v, float):
        return '%.6g' % v
    if isinstance(v, dict):
        return '/'.join('%s=%s' % (k, fmt(x)) for k, x in v.items())
    if isinstance(v, list):
        return '[' + ', '.join(fmt(x) for x in v) + ']'
    return str(v)


for r in rows_out:
    for i, n in enumerate(r['numbers']):
        sec = r['section'] if i == 0 else ''
        rn = str(r['row']) if i == 0 else ''
        L.append('| %s | %s | %s | %s | %s | %s |' % (
            rn, sec, n['status'], fmt(n['published']), fmt(n['independent']),
            (n['rule'] or '') + ' — ' + (n['source'] or n['published_where'] or '')))

explained = []
for r in rows_out:
    if r['status'] == 'differs':
        for n in r['numbers']:
            if n['status'] == 'differs':
                explained.append('- row %d, %s: %s' % (r['row'], n['label'], n['rule']))
L += ['', '## Rows that differ (each explained)', ''] + (explained or ['- none'])
L += ['', '## Not recomputed', '']
for r in rows_out:
    for n in r['numbers']:
        if n['status'] == 'not recomputed':
            L.append('- row %d, %s: %s' % (r['row'], n['label'], n['rule']))
L += ['', '## Need a source file not shipped', '']
anyneed = False
for r in rows_out:
    for n in r['numbers']:
        if n['status'] == 'needs source file':
            anyneed = True
            L.append('- row %d, %s: %s' % (r['row'], n['label'], n['rule']))
if not anyneed:
    L.append('- none (run included the source files)')
_need_names = sorted(set(nm for r in rows_out for x in r['numbers'] if x['status'] == 'needs source file'
                         for nm in (x['source'] or '').split(' + ') if nm in SOURCES))
if _need_names:
    L += ['', 'Each file, where it was published, and the sha256 of the copy saved on 2026-11-09 '
              '(also in `sources.json`):', '']
    for nm in _need_names:
        L.append('- `%s`: %s, sha256 `%s`%s' % (nm, SOURCES[nm]['url'], SOURCES[nm]['sha256'],
                 ' (%s)' % SOURCE_PROBLEMS[nm] if nm in SOURCE_PROBLEMS else ''))

last = ('%d rows agree, recomputed by code; %d checked against a source file; '
        '%d need a source file not shipped; %d not recomputed; %d differ' % (A, B, C, D, E))
L += ['', '**' + last + '**', '']
open(os.path.join(HERE, 'RESULTS%s.md' % _SUFFIX), 'w').write('\n'.join(L) + '\n')

if _need_names:
    print('source files missing, or not the 2026-11-09 copy; the rows that need them count as "need a source file":')
    for nm in _need_names:
        print('  %s' % nm)
        print('    url    : %s' % SOURCES[nm]['url'])
        print('    sha256 : %s' % SOURCES[nm]['sha256'])
        if nm in SOURCE_PROBLEMS:
            print('    note   : %s' % SOURCE_PROBLEMS[nm])
print('rows:', len(ROWS), 'by status:', status_rows)
print('numbers by status:', status_nums)
if max_gap:
    print('largest bootstrap relative gap to nearer seed: %.3f%%' % (max_gap * 100))
print(last)
# Exit 1 if any number differs other than the two census numbers RESULTS.md explains (row 15);
# a page sentence that no longer matches THESIS.md also counts as an unexplained difference.
EXPLAINED_DIFFERS = {(15, 'census tokens (counted rows outside the window segments)'),
                     (15, 'census rows (counted rows outside the window segments)')}
_unexplained = sorted(set(r['row'] for r in rows_out for n in r['numbers']
                          if n['status'] == 'differs' and (r['row'], n['label']) not in EXPLAINED_DIFFERS))
if _unexplained:
    print('rows that differ and are not explained:', _unexplained)
sys.exit(1 if _unexplained else 0)
