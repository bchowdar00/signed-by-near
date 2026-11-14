"""NearBlocks v3 client with a credit ledger. Keyless GETs only.

Every NearBlocks call made from this machine for this entry goes through `NB.get`, which
first reserves its credits in an append-only ledger (`ledger.jsonl`) and only then sends the
request. Before reserving, it waits until the call keeps
  - the credits in any rolling 24 hours at or under CAP_24H (300), and
  - the calls in any rolling 60 seconds at or under CAP_60S (5), at least MIN_GAP (12.5 s) apart.
The free plan is reported as 6 calls a minute, 333 a day and 10,000 a month; keyless limits
are unpublished. Observed on Nov 10 (M10 pilot, 10.5 s spacing): the 6th call inside any 60 s
drew HTTP 429 in 7 of 7 cases, and calls 1-5 passed in 40 of 40, so the keyless limit behaves as
5 per rolling 60 s. 12.5 s spacing keeps any six calls 62.5 s apart, a 2.5 s margin. "Each increment of 25 will count towards rate limit" (NearBlocks OpenAPI), so
a request with limit=L costs ceil(L/25) credits; a request without limit (counts) costs one.
Failed requests are counted too.

Attribution: "Powered by Nearblocks.io APIs".
"""
import json, math, os, time, urllib.parse, urllib.request, urllib.error

BASE = 'https://api.nearblocks.io/v3'
UA = 'research-readonly (NEAR hackathon thesis entry; keyless GET)'
CAP_24H = 300
CAP_60S = 5      # the 6th call inside 60 s drew 429 in 7 of 7 cases on Nov 10
MIN_GAP = 12.5   # seconds between calls; six calls then span 62.5 s
DAY = 86400.0


def credits_for(path_and_query):
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(path_and_query).query)
    if 'limit' in q:
        return max(1, math.ceil(int(q['limit'][0]) / 25))
    return 1


class Ledger:
    """Append-only ledger. Each line: {"t": unix seconds, "credits": n, "url": ..., "purpose": ...}.
    Seed lines (calls made before this tool existed) carry "seed": true."""

    def __init__(self, path, cap24=CAP_24H, cap60=CAP_60S, min_gap=MIN_GAP):
        self.path, self.cap24, self.cap60, self.min_gap = path, cap24, cap60, min_gap
        self.entries = []
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        e = json.loads(line)
                        self.entries.append((float(e['t']), int(e['credits'])))

    def used(self, now):
        c24 = sum(c for t, c in self.entries if now - DAY < t <= now)
        n60 = sum(1 for t, c in self.entries if now - 60 < t <= now and c > 0)
        return c24, n60

    def wake_time(self, credits, now):
        """Earliest time >= now at which reserving `credits` keeps both caps and the minimum gap."""
        if credits > self.cap24:
            raise ValueError('a single call cannot exceed the daily cap')
        t = now
        for _ in range(10000):
            c24, n60 = self.used(t)
            ok24 = c24 + credits <= self.cap24
            ok60 = n60 + 1 <= self.cap60
            last = max((et for et, ec in self.entries if et <= t), default=None)
            okgap = last is None or t - last >= self.min_gap
            if ok24 and ok60 and okgap:
                return t
            nxt = []
            if not okgap:
                nxt.append(last + self.min_gap + 1e-3)
            if not ok24:
                # time when enough of the oldest in-window credits expire
                need = c24 + credits - self.cap24
                acc = 0
                for et, ec in sorted(e for e in self.entries if t - DAY < e[0] <= t):
                    acc += ec
                    if acc >= need:
                        nxt.append(et + DAY + 1e-3)
                        break
            if not ok60:
                in60 = sorted(et for et, ec in self.entries if t - 60 < et <= t and ec > 0)
                nxt.append(in60[0] + 60 + 1e-3)
            t = max(nxt)
        raise RuntimeError('ledger wake computation did not converge')

    def append(self, rec):
        line = json.dumps(rec, sort_keys=True)
        with open(self.path, 'a') as f:
            f.write(line + '\n')
            f.flush()
            os.fsync(f.fileno())
        self.entries.append((float(rec['t']), int(rec['credits'])))


class NB:
    def __init__(self, ledger, purpose, now=time.time, sleep=time.sleep, opener=None, log=print):
        self.ledger, self.purpose = ledger, purpose
        self.now, self.sleep, self.log = now, sleep, log
        self.opener = opener or self._urlopen
        self.last_headers = {}
        self.header_log = os.path.join(os.path.dirname(os.path.abspath(ledger.path)), 'ratelimit-headers.jsonl') \
            if getattr(ledger, 'path', None) else None

    def _urlopen(self, url):
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                self.last_headers = dict(r.headers.items())
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            self.last_headers = dict(e.headers.items()) if e.headers else {}
            return e.code, e.read() if hasattr(e, 'read') else b''

    def _log_quota_headers(self, url, status, now):
        """Logs any rate-limit headers the server sends, as its own view of the quota."""
        h = {k: v for k, v in (self.last_headers or {}).items()
             if 'ratelimit' in k.lower() or 'rate-limit' in k.lower() or k.lower() == 'retry-after'}
        self.last_headers = {}
        if h and self.header_log:
            with open(self.header_log, 'a') as f:
                f.write(json.dumps({'t': round(now, 3), 'url': url, 'status': status, 'headers': h}, sort_keys=True) + '\n')
        return h

    def get(self, path_and_query, max_tries=8):
        """GET BASE+path_and_query. Waits for quota, reserves, sends. Retries 429/5xx/network
        errors with backoff; each try is a separate ledger entry. Returns (status, json or None)."""
        credits = credits_for(path_and_query)
        url = BASE + path_and_query
        backoff = 30.0
        for attempt in range(max_tries):
            now = self.now()
            wake = self.ledger.wake_time(credits, now)
            while wake > now:
                self.sleep(min(wake - now, 300.0))
                now = self.now()
                wake = self.ledger.wake_time(credits, now)
            self.ledger.append({'t': round(now, 3), 'credits': credits, 'url': url, 'purpose': self.purpose,
                                'attempt': attempt})
            try:
                status, body = self.opener(url)
            except Exception as e:  # network error: counted, retried
                status, body = 0, repr(e).encode()
            quota = self._log_quota_headers(url, status, now)
            if status == 200:
                try:
                    return status, json.loads(body)
                except Exception:
                    status = -1
            self.log(f'nb status={status} attempt={attempt} url={url}')
            if status in (400, 403, 404):
                return status, None
            retry_after = next((v for k, v in quota.items() if k.lower() == 'retry-after'), None)
            try:
                wait = max(backoff, float(retry_after)) if retry_after is not None else backoff
            except ValueError:
                wait = backoff
            self.sleep(wait)
            backoff = min(backoff * 2, 900.0)
        return status, None
