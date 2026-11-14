"""Second uncounted rate pilot, for the migration windows' lengths (METHOD §6.7). Run just before
the freeze; its data is never counted.

  run <rates-draft.json> <T0 iso> <out rates.json> [--ledger <ledger.jsonl>]

For each M10 token and each M10 period (the early period, and each chart month that ends before
T0 - 90 days), one page of `GET /v3/fts/<token>/txns?limit=25&before_ts=<t_p>` at a pilot
instant t_p drawn uniformly in the period from the pilot seed (20261110; the counted seed is
never used here). The rate rule, fixed before the pilot runs:
  - n rows on the page (FT rows, the unit the cost model and window lengths use, METHOD §6.5);
  - n = 0: rate 0, and the period's windows take the period's whole length;
  - n >= 1: rate = n / (t_p - t_oldest) per second, t_oldest the oldest row's timestamp
    (strictly before t_p, so the span is positive), times 86,400 for a daily rate.
design.py then sets each window's length to 20 / rate - 60 s, at least 60 s (and the whole
period at rate 0). The pages are kept raw; the output copies the draft rates and replaces only
m10_rate_per_day, with each period's pilot instant, n and span beside it.
"""
import copy, datetime, hashlib, json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nb, design  # noqa: E402

PILOT_SEED = 20261110


def pilot_instant(tok, period, a, b):
    h = hashlib.sha256(f'{PILOT_SEED}|m10pilot|{tok}|{period}'.encode()).hexdigest()
    return a + (b - a) * random.Random(int(h[:16], 16)).random()


def periods(T0):
    T90 = T0 - 90 * design.DAY
    out = [('early', design.ts(design.EARLY[0]), design.ts(design.EARLY[1]))]
    for ym in design.CHART_MONTHS:
        a, b = design.month_start(ym), design.month_start(design.next_month(ym))
        if b <= T90:
            out.append((f'chart:{ym}', a, b))
    return out


def rate_from_page(rows, t_p):
    """Rows per day by the frozen rule; returns (rate, n, span_s)."""
    n = len(rows)
    if n == 0:
        return 0.0, 0, None
    oldest = min(design_row_ts(r) for r in rows) / 1e9
    span = t_p - oldest
    if span <= 0:
        raise ValueError('a row at or after the pilot instant')
    return n / span * design.DAY, n, span


def design_row_ts(r):
    v = r.get('block_timestamp')
    if v is None:
        v = (r.get('block') or {}).get('block_timestamp')
    return int(v)


def run(draft_path, T0_iso, out_path, ledger_path):
    with open(draft_path) as f:
        draft = json.load(f)
    T0 = design.ts(T0_iso)
    raw_dir = os.path.join(os.path.dirname(out_path), 'pilot-m10-pages')
    os.makedirs(raw_dir, exist_ok=True)
    client = nb.NB(nb.Ledger(ledger_path), 'pilot: M10 migration rates (uncounted)', log=lambda m: print(m, flush=True))
    rates = copy.deepcopy(draft)
    rates['m10_rate_per_day'] = {}
    detail = {}
    for tok in draft['m10_tokens']:
        rates['m10_rate_per_day'][tok] = {}
        for pname, a, b in periods(T0):
            t_p = pilot_instant(tok, pname, a, b)
            path = f'/fts/{tok}/txns?limit=25&before_ts={design.ns(t_p)}'
            raw = os.path.join(raw_dir, f"{tok}-{pname.replace(':', '_')}.json")
            if os.path.exists(raw):
                with open(raw) as f:
                    saved = json.load(f)
                st, body = saved['http'], saved['body']
            else:
                st, body = client.get(path)
                with open(raw, 'w') as f:
                    json.dump({'path': path, 'http': st, 'body': body, 'pilot_instant_utc': design.iso(t_p)}, f)
            if st != 200 or not isinstance(body, dict):
                raise SystemExit(f'pilot page failed: {tok} {pname} http {st}; rerun to retry (saved pages are reused)')
            r, n, span = rate_from_page(body.get('data') or [], t_p)
            rates['m10_rate_per_day'][tok][pname] = r
            detail[f'{tok}|{pname}'] = {'pilot_instant_utc': design.iso(t_p), 'rows': n, 'span_s': span, 'rate_per_day': r}
            print(tok, pname, n, r, flush=True)
    rates['m10_rate_source'] = {'rule': 'METHOD-b §6.7 (pilot_m10.py docstring)', 'pilot_seed': PILOT_SEED,
                                'utc': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                'periods': detail}
    rates['note'] = 'final rates for the freeze: draft rates with M10 rates from the second uncounted pilot'
    with open(out_path, 'w') as f:
        json.dump(rates, f, indent=1, sort_keys=True)


if __name__ == '__main__':
    if len(sys.argv) >= 5 and sys.argv[1] == 'run':
        led = sys.argv[sys.argv.index('--ledger') + 1] if '--ledger' in sys.argv else \
            os.path.expanduser('~/Data/hackathons/near-2026/b-collect/nb/ledger.jsonl')
        run(sys.argv[2], sys.argv[3], sys.argv[4], led)
    else:
        raise SystemExit(__doc__)
