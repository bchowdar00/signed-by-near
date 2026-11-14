"""neardata sampler (METHOD §6.8) and block-height plan. Keyless; neardata states "The public
access rate limit is 180 requests per minute per IP"; this paces at about 100 a minute and backs
off on 429.

  plan <T0 iso> <out nd_plan.json>   month-start heights from 2025-01 to T0 and the T0 height,
                                     150 seeded random heights per month for the last 12 months,
                                     and the 2,000-block contiguous run ending at T0.
  run  <nd_plan.json> <data_dir>     fetches every planned block (resumable) and writes, per
                                     block, the v1.signer receipts with full arguments, signer,
                                     predecessor, deposit and outcome status. Whole blocks are
                                     never written.
"""
import base64, datetime, hashlib, json, os, random, sys, time, urllib.error, urllib.request

BASE = 'https://mainnet.neardata.xyz/v0'
UA = 'research-readonly (NEAR hackathon thesis entry; keyless GET)'
PACE = 0.6
SEED = 20261114
N_PER_MONTH = 150
N_CONTIG = 2000
FIRST_PLAN_MONTH = '2025-01'
UTC = datetime.timezone.utc


def get(url, tries=8):
    back = 5.0
    for _ in range(tries):
        time.sleep(PACE)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=30) as r:
                return r.status, json.loads(r.read() or b'null')
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(back)
                back = min(back * 2, 300)
                continue
            return e.code, None
        except Exception:
            time.sleep(back)
            back = min(back * 2, 300)
    return 0, None


def block(h):
    st, b = get(f'{BASE}/block/{h}')
    return b if (st == 200 and b) else None


def ts_of(b):
    return int(b['block']['header']['timestamp'])


def present_at_or_after(h, limit=50):
    for k in range(limit):
        b = block(h + k)
        if b:
            return h + k, b
    raise RuntimeError(f'no block near {h}')


def height_at(target_ns, lo, hi):
    """Smallest present height whose timestamp >= target_ns, by bisection on [lo, hi)."""
    while hi - lo > 1:
        mid = (lo + hi) // 2
        hm, b = present_at_or_after(mid)
        if hm >= hi:
            hi = mid
            continue
        if ts_of(b) >= target_ns:
            hi = mid
        else:
            lo = hm
    h, b = present_at_or_after(hi)
    return h, ts_of(b)


def month_starts(first, T0):
    y, m = map(int, first.split('-'))
    out = []
    while True:
        t = datetime.datetime(y, m, 1, tzinfo=UTC).timestamp()
        if t >= T0:
            break
        out.append((f'{y}-{m:02d}', t))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def plan(T0_iso, out):
    T0 = datetime.datetime.strptime(T0_iso, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC).timestamp()
    st, last = get(f'{BASE}/last_block/final')
    top = last['block']['header']['height']
    bounds = {}
    lo = 100_000_000
    for ym, t in month_starts(FIRST_PLAN_MONTH, T0) + [('T0', T0)]:
        h, hts = height_at(int(t * 1e9), lo, top)
        bounds[ym] = {'height': h, 'ts_ns': hts}
        lo = h
        print(ym, h, flush=True)
    months = [ym for ym in bounds if ym != 'T0']
    keys = months + ['T0']
    T365 = T0 - 365 * 86400
    sample = {}
    for i, ym in enumerate(months):
        nxt = bounds[keys[i + 1]]
        a, b = bounds[ym]['height'], nxt['height']
        month_end_t = nxt['ts_ns'] / 1e9
        if month_end_t <= T365:
            continue
        rng = random.Random(int(hashlib.sha256(f'{SEED}|nd|{ym}'.encode()).hexdigest()[:16], 16))
        sample[ym] = sorted(rng.sample(range(a, b), N_PER_MONTH))
    hT0 = bounds['T0']['height']
    p = {'T0_utc': T0_iso, 'seed': SEED, 'bounds': bounds, 'sample': sample,
         'contiguous': [hT0 - N_CONTIG, hT0], 'note': 'heights are block heights; [a, b) half-open'}
    json.dump(p, open(out, 'w'), indent=1, sort_keys=True)


def extract(h, b):
    calls = []
    for sh in b.get('shards', []) or []:
        for o in sh.get('receipt_execution_outcomes', []) or []:
            rc = o.get('receipt') or {}
            if rc.get('receiver_id') != 'v1.signer':
                continue
            act = (rc.get('receipt') or {}).get('Action') or {}
            out = (o.get('execution_outcome') or {}).get('outcome') or {}
            status = out.get('status')
            for a in act.get('actions', []) or []:
                fc = a.get('FunctionCall')
                if not fc:
                    continue
                try:
                    args = json.loads(base64.b64decode(fc.get('args') or ''))
                except Exception:
                    args = {'_undecoded_b64': fc.get('args')}
                calls.append({'height': h, 'ts_ns': ts_of(b), 'receipt_id': rc.get('receipt_id'),
                              'method': fc.get('method_name'), 'predecessor': rc.get('predecessor_id'),
                              'signer': act.get('signer_id'), 'deposit_yocto': fc.get('deposit'),
                              'status': status, 'args': args,
                              'execution_block_hash': (o.get('execution_outcome') or {}).get('block_hash')})
    return calls


def run(plan_path, data_dir):
    p = json.load(open(plan_path))
    os.makedirs(os.path.join(data_dir, 'nd'), exist_ok=True)
    path = os.path.join(data_dir, 'nd', 'blocks.jsonl')
    done = set()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip():
                    e = json.loads(line)
                    if e['http'] == 200:   # a failed fetch is retried on the next run
                        done.add((e['part'], e['height']))
    jobs = [('sample:' + ym, h) for ym, hs in sorted(p['sample'].items()) for h in hs]
    a, b = p['contiguous']
    jobs += [('contiguous', h) for h in range(a, b)]
    t0 = time.time()
    failed = 0
    with open(path, 'a') as f:
        for k, (part, h) in enumerate(jobs):
            if (part, h) in done:
                continue
            st, blk = get(f'{BASE}/block/{h}')
            rec = {'part': part, 'height': h, 'http': st, 'present': bool(blk)}
            failed += st != 200
            if blk:
                rec['ts_ns'] = ts_of(blk)
                rec['calls'] = extract(h, blk)
            f.write(json.dumps(rec, sort_keys=True) + '\n')
            f.flush()
            if k % 200 == 0:
                print(f'{k}/{len(jobs)} {part} {h} t={round(time.time() - t0)}s', flush=True)
    if failed:
        raise SystemExit(f'{failed} blocks failed; rerun to retry them')
    open(os.path.join(data_dir, 'nd', 'DONE'), 'w').write(datetime.datetime.now(UTC).isoformat() + '\n')


if __name__ == '__main__':
    if sys.argv[1] == 'plan':
        plan(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'run':
        run(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
