"""Uncounted pilot: per-token FT row rates, used only to set window lengths before the freeze.

NearBlocks `/v3/fts/<token>/stats/transfers?limit=25` returns daily transfer counts for the
token's 25 most recent active days. The mean count per calendar day over the span those rows
cover sets the planning rate for the flow windows (METHOD §6.5). Nothing here is counted.

Usage: python3 -I pilot_rates.py <ledger.jsonl> <out.json> <token> [<token> ...]
"""
import json, sys, datetime
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import nb


def main():
    ledger, out, tokens = sys.argv[1], sys.argv[2], sys.argv[3:]
    client = nb.NB(nb.Ledger(ledger), 'pilot: FT daily stats for window lengths (uncounted)')
    res = {}
    for t in tokens:
        st, d = client.get(f'/fts/{t}/stats/transfers?limit=25', max_tries=2)
        rows = (d or {}).get('data') or []
        days = sorted(r['date'] for r in rows)
        total = sum(int(r['transfers_count']) for r in rows)
        span_days = None
        if days:
            a = datetime.date.fromisoformat(days[0]); b = datetime.date.fromisoformat(days[-1])
            span_days = (b - a).days + 1
        res[t] = {'http': st, 'n_days_listed': len(rows), 'first': days[0] if days else None,
                  'last': days[-1] if days else None, 'span_days': span_days, 'transfers': total,
                  'rate_per_day': round(total / span_days, 3) if span_days else None, 'rows': rows}
        print(t, st, res[t]['n_days_listed'], res[t]['first'], res[t]['last'], res[t]['rate_per_day'], flush=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    json.dump({'taken_utc': stamp, 'source': 'api.nearblocks.io v3 /fts/<token>/stats/transfers?limit=25, keyless; '
               'Powered by Nearblocks.io APIs', 'purpose': 'uncounted pilot for window lengths', 'tokens': res},
              open(out, 'w'), indent=1)


if __name__ == '__main__':
    main()
