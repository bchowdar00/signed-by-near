"""Load sign windows, classify predecessors, read neardata sample.
Read-only; opens files by named path or os.listdir of one named dir.
"""
import json
import os
import re

REPO = os.environ['RD_REPO']
DATA = os.environ['RD_DATA']

RELAY_SET = {
    "7eda04920f22ba6a2b9f2573fd9a6f6f1946ff9f.aurora",
    "e12bc514e90e136cad10413669a6ccdeb9e3adb7.aurora",
    "66667945c34b399993ca834587886b8508db39b1.aurora",
    "62e1e3be3df663f0563c4ef48233d42ec988e6d9.aurora",
}
AURORA_RE = re.compile(r'^[0-9a-f]{40}\.aurora$')


def classify(pred):
    """METHOD 5 rules in order. Returns (class_str, rule_label)."""
    if pred.endswith('.bridge.near'):
        return '1', 'suffix .bridge.near'
    if pred == 'fast-auth.near':
        return '2', 'exact fast-auth.near (FastAuth, split by signer)'
    if pred in ('ping-account.near', 'tx-bench.near', 'v0.shadeagent.near'):
        return '3', 'exact class-3 (test/monitor/demo)'
    if pred in RELAY_SET:
        return '4', 'exact_set Relay aurora contracts'
    if AURORA_RE.match(pred):
        return '4x', 'regex <40-hex>.aurora'
    if pred.endswith('.meteor-vaults.near'):
        return '4', 'suffix .meteor-vaults.near'
    if pred == 'acc.ref-labs.near':
        return '4', 'exact acc.ref-labs.near'
    if pred == 'rri.sputnik-dao.near':
        return '4', 'exact rri.sputnik-dao.near'
    if pred.endswith('.peerfolio.near'):
        return '4', 'suffix .peerfolio.near'
    return '5', 'no registry match (default class 5)'


def load_sign_windows():
    inst = json.load(open(os.path.join(REPO, 'frozen/instants.json')))
    return [x for x in inst['windows'] if x['family'] == 'sign']


def completion_map(sign):
    """A window is completed iff: completed event present, and its pages form a
    gapless done chain all HTTP 200 (COMMON/DEVIATIONS 17)."""
    comp_event = set()
    for line in open(os.path.join(DATA, 'nb/windows.jsonl')):
        r = json.loads(line)
        if r.get('family') == 'sign' and r.get('event') == 'completed':
            comp_event.add(r['id'])
    result = {}
    detail = {}
    for w in sign:
        wid = w['id']
        if wid not in comp_event:
            result[wid] = False
            detail[wid] = 'no completed event'
            continue
        pdir = os.path.join(DATA, 'nb/pages', wid)
        if not os.path.isdir(pdir):
            result[wid] = False
            detail[wid] = 'no pages dir'
            continue
        files = [f for f in os.listdir(pdir) if f.endswith('.json')]
        # group pages by seg
        nseg = len(w['segments_ns'])
        ok = True
        why = 'ok'
        for seg in range(nseg):
            segpages = {}
            for f in files:
                s, p = f[:-5].split('-')
                if int(s) == seg:
                    segpages[int(p)] = f
            if not segpages:
                ok = False; why = f'seg {seg} no pages'; break
            maxp = max(segpages)
            # gapless 0..maxp
            if set(segpages) != set(range(maxp + 1)):
                ok = False; why = f'seg {seg} page gap'; break
            lastdone = False
            for p in range(maxp + 1):
                pg = json.load(open(os.path.join(pdir, segpages[p])))
                if pg.get('http') != 200:
                    ok = False; why = f'seg {seg} page {p} http {pg.get("http")}'; break
                if p == maxp:
                    lastdone = bool(pg.get('done'))
            if not ok:
                break
            if not lastdone:
                ok = False; why = f'seg {seg} last page not done'; break
        result[wid] = ok
        detail[wid] = why
    return result, detail


def read_window_calls(w):
    """Return list of (predecessor, status_bool) for distinct sign receipts in window,
    deduped by receipt id, filtered to the window's segment bounds [s,e)."""
    wid = w['id']
    pdir = os.path.join(DATA, 'nb/pages', wid)
    files = [f for f in os.listdir(pdir) if f.endswith('.json')]
    segbounds = [(int(a), int(b)) for a, b in w['segments_ns']]
    seen = {}
    for f in files:
        pg = json.load(open(os.path.join(pdir, f)))
        for row in pg.get('rows', []):
            rid = row['receipt_id']
            ts = int(row['included_in_block_timestamp'])
            inseg = any(a <= ts < b for a, b in segbounds)
            if not inseg:
                continue
            if rid in seen:
                continue
            status = row.get('outcome', {}).get('status', None)
            seen[rid] = (row['predecessor_account_id'], status)
    return list(seen.values())


def month_of_stratum(stratum):
    # 'sign:2026-08:early-part' -> '2026-08'
    s = stratum.split(':')
    return s[1]


def load_nd_sign_sample():
    """Per sample month, list of sign calls with predecessor, signer, domain, path, form."""
    out = {}
    for line in open(os.path.join(DATA, 'nd/blocks.jsonl')):
        r = json.loads(line)
        part = r.get('part', '')
        if not part.startswith('sample:'):
            continue
        month = part.split(':', 1)[1]
        for c in r.get('calls', []):
            if c.get('method') != 'sign':
                continue
            req = c['args'].get('request', c['args'])
            if 'domain_id' in req:
                domain = req.get('domain_id')
                form = 'v2'
            else:
                # older byte-array form (key_version, path, payload) -> domain 0 (secp256k1)
                domain = 0
                form = 'legacy'
            path = req.get('path')
            out.setdefault(month, []).append({
                'predecessor': c.get('predecessor'),
                'signer': c.get('signer'),
                'domain': domain,
                'path': path,
                'form': form,
                'height': r.get('height'),
            })
    return out
