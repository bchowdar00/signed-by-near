"""Stops the counted run from outside at its frozen deadline (parent ruling: option A, 2026-11-12;
see best-price/review/POST-FREEZE.md and repo/extension/PLAN.md, decision 1).

Why: collector/sampler.py checks DEADLINE_UTC only between calls, and nb.NB.get sleeps for ledger
quota without checking it. After about 21:59Z on Nov 12 the sampler sleeps until about 10:02:38Z on
Nov 13 and would then call NearBlocks after the deadline. This timer ends it while it sleeps.

  nohup python3 -I deadline_stop.py arm   <data_dir> <log> >/dev/null 2>&1 &
  python3 -I deadline_stop.py check <data_dir>     # dry run: prints what it sees now, acts on nothing

It reads only the process table, the nb/DONE and STOP markers and the last line of nb/ledger.jsonl.
It never reads pages, windows.jsonl or logs, and never writes in <data_dir> except the STOP file.

arm, in order:
 1. Sleeps until START (2026-11-13T00:00:30Z) by the wall clock, in steps of at most 30 s, with an
    hourly heartbeat line in the log.
 2. If nb/DONE exists, the sampler ended by itself: it skips to step 7.
 3. Logs the ledger's last line. Goes on only if its t is before DEADLINE (00:00:00Z) and at least
    60 s old. nb.py writes t before it sends and times out at 40 s, so no request is in flight.
    Otherwise it logs FAIL, acts on nothing and exits 2.
 4. Needs at most one process whose command line contains 'collector/sampler.py run' and
    ' <data_dir> '. More than one: FAIL, nothing done.
 5. touch <data_dir>/STOP, so run.sh's loop cannot restart the sampler.
 6. Re-reads the sampler PID, nb/DONE and the ledger's last line. If DONE appeared or the ledger
    moved, it kills nothing (FAIL; the loop still ends at STOP). Otherwise SIGTERM, and SIGKILL if
    the process is still alive after 30 s.
 7. Waits up to 5 min for run.sh to exit. run.sh's `wait` also waits for its own
    `caffeinate -dimsu -w <run.sh pid>`, so it cannot exit by itself. Once caffeinate is run.sh's
    only child left (the nb loop has ended), it sends that caffeinate SIGTERM, and run.sh exits.
 8. Logs the ledger's last line again and the outcome. Exit 0 on success, 2 on FAIL.

Environment, for the offline test only: DS_START, DS_DEADLINE (ISO Z), DS_RUNSH (run.sh path),
DS_MIN_AGE_S, DS_EXIT_WAIT_S, DS_TERM_GRACE_S.
"""
import datetime as dt
import json
import os
import signal
import subprocess
import sys
import time

START_UTC = os.environ.get('DS_START', '2026-11-13T00:00:30Z')
DEADLINE_UTC = os.environ.get('DS_DEADLINE', '2026-11-13T00:00:00Z')
RUNSH = os.environ.get('DS_RUNSH', '/Users/bobby/Hackathons/near-2026/best-price/repo/run.sh')
MIN_AGE_S = float(os.environ.get('DS_MIN_AGE_S', '60'))
EXIT_WAIT_S = float(os.environ.get('DS_EXIT_WAIT_S', '300'))
TERM_GRACE_S = float(os.environ.get('DS_TERM_GRACE_S', '30'))
SAMPLER_MARK = 'collector/sampler.py run'


def ts(s):
    return dt.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc).timestamp()


def utc(t=None):
    t = time.time() if t is None else t
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


class Log:
    def __init__(self, path):
        self.path = path

    def __call__(self, msg):
        line = f'{utc()} {msg}'
        if self.path:
            with open(self.path, 'a') as f:
                f.write(line + '\n')
        else:
            print(line, flush=True)


class Fail(Exception):
    pass


def procs():
    out = subprocess.run(['ps', '-axo', 'pid=,ppid=,command='], capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) == 3 and parts[0].isdigit():
            rows.append((int(parts[0]), int(parts[1]), parts[2]))
    return rows


def samplers(data_dir, rows=None):
    me = os.getpid()
    return [(p, c) for p, pp, c in (rows or procs())
            if p != me and SAMPLER_MARK in c and f' {data_dir} ' in c]


def runsh(data_dir, rows=None):
    rows = rows or procs()
    cand = {p: (pp, c) for p, pp, c in rows if 'bash' in c.split(' ', 1)[0] and f'{RUNSH} ' in c
            and c.rstrip().endswith(f' {data_dir}')}
    return [p for p, (pp, c) in cand.items() if pp not in cand]  # the loops are forks of run.sh


def children(pid, rows=None):
    return [(p, c) for p, pp, c in (rows or procs()) if pp == pid]


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def last_ledger(data_dir):
    path = os.path.join(data_dir, 'nb', 'ledger.jsonl')
    last = None
    with open(path, 'rb') as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 65536))
        for line in f.read().decode().splitlines():
            if line.strip():
                last = line
    if last is None:
        raise Fail('ledger is empty')
    return json.loads(last), last


def show_ledger(rec):
    return (f"t={rec['t']} ({utc(float(rec['t']))}) credits={rec.get('credits')} "
            f"attempt={rec.get('attempt')} purpose={rec.get('purpose')!r} url={rec.get('url')}")


def check(data_dir, log=print):
    rows = procs()
    rec, _ = last_ledger(data_dir)
    now = time.time()
    rs = runsh(data_dir, rows)
    log(f'now={utc(now)} START={START_UTC} DEADLINE={DEADLINE_UTC} data={data_dir}')
    log(f"nb/DONE={os.path.exists(os.path.join(data_dir, 'nb', 'DONE'))} "
        f"STOP={os.path.exists(os.path.join(data_dir, 'STOP'))}")
    log(f'ledger last: {show_ledger(rec)} age_s={now - float(rec["t"]):.0f}')
    log(f'samplers: {[(p, c[:110]) for p, c in samplers(data_dir, rows)]}')
    log(f'run.sh: {rs}')
    for p in rs:
        log(f'  children of {p}: {[(q, c[:70]) for q, c in children(p, rows)]}')


def finish(data_dir, log):
    deadline = ts(DEADLINE_UTC)
    rs = runsh(data_dir)
    if len(rs) != 1:
        log(f'run.sh processes found: {rs}')
    t_end = time.time() + EXIT_WAIT_S
    ended_caff = set()
    while time.time() < t_end:
        rs = [p for p in rs if alive(p)]
        if not rs:
            break
        for p in rs:
            kids = children(p)
            caff = [q for q, c in kids if c.startswith('caffeinate') and f'-w {p}' in c]
            if kids and len(caff) == len(kids):  # only its own caffeinate is left: the loops have ended
                for q in caff:
                    if q not in ended_caff:
                        log(f'run.sh {p}: only its caffeinate {q} is left (the loops have ended); SIGTERM to {q}')
                        os.kill(q, signal.SIGTERM)
                        ended_caff.add(q)
        time.sleep(2)
    rs = [p for p in rs if alive(p)]
    rec, _ = last_ledger(data_dir)
    log(f'ledger last after: {show_ledger(rec)}')
    late = float(rec['t']) >= deadline
    if late:
        log(f'FAIL !!! the ledger has a call at or after the deadline: {show_ledger(rec)}')
    if rs:
        log(f'FAIL !!! run.sh still running after {EXIT_WAIT_S:.0f} s: {rs}; children {[children(p) for p in rs]}')
        return 2
    log(f"run.sh exited. nb/DONE={os.path.exists(os.path.join(data_dir, 'nb', 'DONE'))} "
        f"STOP={os.path.exists(os.path.join(data_dir, 'STOP'))} samplers={samplers(data_dir)}")
    return 2 if late else 0


def arm(data_dir, log):
    start, deadline = ts(START_UTC), ts(DEADLINE_UTC)
    log(f'armed pid={os.getpid()} data={data_dir} START={START_UTC} DEADLINE={DEADLINE_UTC} '
        f'RUNSH={RUNSH} min_age={MIN_AGE_S:.0f}s exit_wait={EXIT_WAIT_S:.0f}s')
    beat = time.time() + 3600
    while time.time() < start:
        time.sleep(max(0.05, min(30.0, start - time.time())))
        if time.time() >= beat:
            log(f'heartbeat: waiting for {START_UTC}')
            beat += 3600
    log('woke')
    done_file = os.path.join(data_dir, 'nb', 'DONE')
    try:
        if os.path.exists(done_file):
            log('nb/DONE present: the sampler ended by itself; nothing to stop')
            return finish(data_dir, log)
        rec, raw = last_ledger(data_dir)
        now = time.time()
        log(f'ledger last: {show_ledger(rec)} age_s={now - float(rec["t"]):.1f}')
        if float(rec['t']) >= deadline:
            raise Fail('the ledger has a call at or after the deadline')
        if now - float(rec['t']) < MIN_AGE_S:
            raise Fail(f'the last call is less than {MIN_AGE_S:.0f} s old; a request may be in flight')
        s = samplers(data_dir)
        log(f'samplers before STOP: {[p for p, c in s]}')
        if len(s) > 1:
            raise Fail(f'more than one sampler process: {s}')
        open(os.path.join(data_dir, 'STOP'), 'a').close()
        log(f"touched {os.path.join(data_dir, 'STOP')}")
        s = samplers(data_dir)
        if len(s) > 1:
            raise Fail(f'more than one sampler process after STOP: {s}; nothing killed')
        if not s:
            log('no sampler process (between restarts); STOP ends the loop')
        else:
            pid = s[0][0]
            rec2, raw2 = last_ledger(data_dir)
            if os.path.exists(done_file):
                raise Fail('nb/DONE appeared after STOP; nothing killed')
            if raw2 != raw:
                raise Fail(f'the ledger moved after STOP ({show_ledger(rec2)}); nothing killed')
            log(f'SIGTERM to sampler {pid}: {s[0][1][:160]}')
            os.kill(pid, signal.SIGTERM)
            t_end = time.time() + TERM_GRACE_S
            while alive(pid) and time.time() < t_end:
                time.sleep(0.5)
            if alive(pid):
                log(f'sampler {pid} still alive after {TERM_GRACE_S:.0f} s: SIGKILL')
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
            log(f'sampler {pid} alive={alive(pid)}')
        return finish(data_dir, log)
    except Fail as e:
        log(f'FAIL !!! {e}. Acted on nothing more; leave it for a human.')
        return 2


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'arm':
        sys.exit(arm(os.path.abspath(sys.argv[2]), Log(sys.argv[3])))
    elif len(sys.argv) == 3 and sys.argv[1] == 'check':
        check(os.path.abspath(sys.argv[2]))
    else:
        raise SystemExit(__doc__)
