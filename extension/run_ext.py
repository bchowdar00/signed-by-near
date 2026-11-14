"""Extension pass (DRAFT, not run, not stamped; needs Bhargav's yes). See extension/PLAN.md.

Re-pages, after the frozen run has ended, exactly the windows that run marked not_completed, in
their frozen order, into a separate data folder. It uses the frozen collector code unchanged
(collector/sampler.py, collector/nb.py) and changes no frozen file.

  python3 -I extension/run_ext.py select <frozen instants.json> <primary data dir> <ext dir>
  python3 -I extension/run_ext.py run    <ext dir>

select: needs the primary's nb/DONE. Reads only the id and event of each line of the primary's
        nb/windows.jsonl, and checks that the not_completed windows are the tail of the frozen order.
        Writes <ext>/instants-ext.json (the frozen instants with only those windows) and
        <ext>/selection.json. Copies the primary ledger to <ext>/nb/ledger.jsonl, so the quota
        sees every earlier call while the primary folder is never written to.
run:    pages those windows into <ext>/nb/pages/, with these rules (PLAN.md):
        - it does not start before NOT_BEFORE_UTC and stops at DEADLINE_UTC;
        - its rolling 24 h ledger cap is CAP_24H (262), the number NearBlocks accepted on each of
          the last two mornings, and it keeps the frozen 5-a-minute, 12.5 s pacing;
        - each request is tried once. The first 429 ends the pass: every window not yet completed
          is marked not_completed, and nothing is retried, so it cannot enter the retry loop
          that kept the frozen run's evenings full. A network error gets one retry after 60 s.
"""
import json, os, shutil, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'collector'))
import nb  # noqa: E402
import sampler  # noqa: E402

PURPOSE = 'extension (after the frozen run; extension/PLAN.md)'
CAP_24H = 262
NOT_BEFORE_UTC = '2026-11-13T10:45:00Z'
DEADLINE_UTC = '2026-11-13T13:00:00Z'


class Stop(Exception):
    pass


class OnceClient:
    """Wraps nb.NB: one try per request; the first 429 (or any status but 200) stops the pass."""

    def __init__(self, inner, deadline, sleep=time.sleep, log=print):
        self.inner, self.ledger, self.sleep, self.log = inner, inner.ledger, sleep, log
        self.deadline, self.stopped = deadline, None

    def get(self, path):
        for attempt in range(2):
            # nb.NB.get waits for quota without looking at the deadline (the frozen sampler checks it
            # only between calls), so a call whose quota frees after the deadline is never made here
            if self.ledger.wake_time(nb.credits_for(path), self.inner.now()) >= self.deadline:
                raise sampler.Deadline()
            st, body = self.inner.get(path, max_tries=1)
            if st == 200 and isinstance(body, dict):
                return st, body
            if st == 0 and attempt == 0:  # network error: one retry
                self.sleep(60.0)
                continue
            self.stopped = {'status': st, 'path': path, 'utc': sampler.utc(self.inner.now())}
            self.log(f'extension stop: status={st} path={path}')
            raise sampler.Deadline()
        raise sampler.Deadline()


def sampler_running():
    import subprocess
    out = subprocess.run(['pgrep', '-f', 'collector/sampler.py run'], capture_output=True, text=True).stdout
    return bool(out.strip())


def select(instants_path, primary, ext, now=time.time, running=sampler_running):
    """The frozen run has ended either with its own nb/DONE, or (if it was stopped at the deadline
    while asleep waiting for quota, PLAN.md decision 1) with nb/STOP present, the deadline passed and
    no sampler process left. The selected windows are those with no 'completed' line."""
    done = os.path.exists(os.path.join(primary, 'nb', 'DONE'))
    stopped = (os.path.exists(os.path.join(primary, 'STOP')) and now() >= sampler.ts(sampler.DEADLINE_UTC)
               and not running())
    if not (done or stopped):
        raise SystemExit('the frozen run has not ended (no nb/DONE, and not stopped after the deadline)')
    with open(instants_path) as f:
        I = json.load(f)
    events = {}
    with open(os.path.join(primary, 'nb', 'windows.jsonl')) as f:
        for line in f:
            if line.strip():
                e = json.loads(line)
                if e['event'] == 'completed':
                    events[e['id']] = 'completed'  # only id and event are read
    W = I['windows']
    nc = [w for w in W if events.get(w['id']) != 'completed']
    k = len(nc)
    if [w['id'] for w in nc] != [w['id'] for w in W[len(W) - k:]]:
        raise SystemExit('not_completed windows are not the tail of the frozen order: stop and report')
    os.makedirs(os.path.join(ext, 'nb'), exist_ok=True)
    out = dict(I, windows=nc)
    out['meta'] = dict(I['meta'], extension={'of_instants_sha256': nb_sha(instants_path), 'windows': k,
                                             'purpose': PURPOSE})
    with open(os.path.join(ext, 'instants-ext.json'), 'w') as f:
        json.dump(out, f, sort_keys=True)
    sel = {'windows': k, 'ids': [w['id'] for w in nc], 'keys': [w['key'] for w in nc],
           'plan_credits': round(sum(w.get('cost_plan', 0.0) for w in nc), 1),
           'stress_credits': round(sum(w.get('cost_stress', 0.0) for w in nc), 1),
           'cap_24h': CAP_24H, 'not_before_utc': NOT_BEFORE_UTC, 'deadline_utc': DEADLINE_UTC}
    with open(os.path.join(ext, 'selection.json'), 'w') as f:
        json.dump(sel, f, indent=1, sort_keys=True)
    shutil.copy2(os.path.join(primary, 'nb', 'ledger.jsonl'), os.path.join(ext, 'nb', 'ledger.jsonl'))
    print(json.dumps({k_: v for k_, v in sel.items() if k_ not in ('ids', 'keys')}))


def nb_sha(p):
    import hashlib
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def run(ext, now=time.time, sleep=time.sleep, opener=None, log=print):
    with open(os.path.join(ext, 'instants-ext.json')) as f:
        I = json.load(f)
    start = sampler.ts(NOT_BEFORE_UTC)
    while now() < start:
        sleep(min(start - now(), 300.0))
    ledger = nb.Ledger(os.path.join(ext, 'nb', 'ledger.jsonl'), cap24=CAP_24H)
    inner = nb.NB(ledger, PURPOSE, now=now, sleep=sleep, opener=opener, log=log)
    client = OnceClient(inner, sampler.ts(DEADLINE_UTC), sleep=sleep, log=log)
    s = sampler.Sampler(I, ext, client, now=now, sleep=sleep, deadline=sampler.ts(DEADLINE_UTC), log=log,
                        do_resolve=False)
    res = s.run()
    end = {'result': res, 'stopped_by': client.stopped, 'utc': sampler.utc(now())}
    with open(os.path.join(ext, 'nb', 'DONE'), 'w') as f:
        f.write(json.dumps(end, sort_keys=True) + '\n')
    log(json.dumps(end))
    return end


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == 'select':
        select(*sys.argv[2:5])
    elif len(sys.argv) == 3 and sys.argv[1] == 'run':
        run(sys.argv[2], log=lambda m: print(m, flush=True))
    else:
        raise SystemExit(__doc__)
