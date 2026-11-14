"""Offline test of deadline_stop.py against the real run.sh, copied byte for byte, driving fake
collectors (a sleeping sampler, nd and rpc that finish at once) in a fake data folder. No network,
and nothing outside <base> is touched: every process the timer may match carries <base> paths.

  python3 -I test_deadline_stop.py <base dir>

Cases: A happy path (stop, kill, caffeinate, run.sh exits); B last call too young (FAIL, nothing
done); C a call at the deadline (FAIL, nothing done); D sampler already DONE (nothing killed,
run.sh released). Takes about 90 s: run.sh's loop sleeps 60 s after the sampler exits.
"""
import json, os, shutil, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REAL_RUNSH = '/Users/bobby/Hackathons/near-2026/best-price/repo/run.sh'
REAL_DATA = '/Users/bobby/Data/hackathons/near-2026/b-collect'

FAKE_SAMPLER = '''import os, sys, time
d = sys.argv[3]
if os.environ.get('FAKE_MODE') == 'done':
    open(os.path.join(d, 'nb', 'DONE'), 'w').write('deadline fake\\n'); sys.exit(0)
time.sleep(600)
'''
FAKE_DONE = '''import os, sys
d = sys.argv[3]; sub = os.path.basename(sys.argv[0])[:-3]
os.makedirs(os.path.join(d, sub), exist_ok=True); open(os.path.join(d, sub, 'DONE'), 'w').write('done\\n')
'''


def iso(t):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t))


def world(base):
    repo = os.path.join(base, 'repo')
    os.makedirs(os.path.join(repo, 'collector'), exist_ok=True)
    shutil.copyfile(REAL_RUNSH, os.path.join(repo, 'run.sh'))
    assert open(REAL_RUNSH, 'rb').read() == open(os.path.join(repo, 'run.sh'), 'rb').read()
    open(os.path.join(repo, 'collector', 'sampler.py'), 'w').write(FAKE_SAMPLER)
    for n in ('nd', 'rpc'):
        open(os.path.join(repo, 'collector', f'{n}.py'), 'w').write(FAKE_DONE)
    for n in ('instants.json', 'nd_plan.json'):
        open(os.path.join(repo, n), 'w').write('{}')
    return repo


def start_run(repo, data, mode):
    os.makedirs(os.path.join(data, 'nb'), exist_ok=True)
    env = dict(os.environ, FAKE_MODE=mode)
    # detached like the real one: the outer shell exits, so run.sh is re-parented to launchd
    subprocess.run(['/bin/bash', '-c', f'nohup /bin/bash {repo}/run.sh {repo}/instants.json {repo}/nd_plan.json {data} '
                    '>/dev/null 2>&1 &'], env=env, check=True)
    time.sleep(3)


def ledger(data, t):
    with open(os.path.join(data, 'nb', 'ledger.jsonl'), 'w') as f:
        f.write(json.dumps({'t': t - 100, 'credits': 1, 'url': 'x', 'purpose': 'counted', 'attempt': 1}) + '\n')
        f.write(json.dumps({'t': t, 'credits': 1, 'url': 'y', 'purpose': 'counted', 'attempt': 1}) + '\n')


def mine(data):
    out = subprocess.run(['ps', '-axo', 'pid=,command='], capture_output=True, text=True).stdout
    return [(int(l.split(None, 1)[0]), l.split(None, 1)[1]) for l in out.splitlines()
            if l.strip() and f' {data}' in l]  # run.sh, its loops and the sampler; caffeinate exits with run.sh


def run_timer(repo, data, start, deadline, log):
    env = dict(os.environ, DS_START=iso(start), DS_DEADLINE=iso(deadline), DS_RUNSH=f'{repo}/run.sh',
               DS_EXIT_WAIT_S='150', DS_TERM_GRACE_S='10')
    return subprocess.run([sys.executable, '-I', os.path.join(HERE, 'deadline_stop.py'), 'arm', data, log],
                          env=env, timeout=400).returncode


def cleanup(data):
    for pid, cmd in mine(data):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def case(base, repo, name, mode, ledger_t_of, start_off, deadline_off):
    data = os.path.join(base, f'data-{name}')
    log = os.path.join(base, f'{name}.log')
    start_run(repo, data, mode)
    now = time.time()
    start, deadline = round(now) + start_off, round(now) + deadline_off
    ledger(data, ledger_t_of(start, deadline))
    before = mine(data)
    rc = run_timer(repo, data, start, deadline, log)
    after = mine(data)
    text = open(log).read()
    res = {'rc': rc, 'STOP': os.path.exists(os.path.join(data, 'STOP')),
           'procs_before': len(before), 'procs_after': len(after), 'log': text}
    cleanup(data)
    return res


def main(base):
    os.makedirs(base, exist_ok=True)
    repo = world(base)
    real_sampler_before = subprocess.run(['pgrep', '-f', f'collector/sampler.py run .* {REAL_DATA} '],
                                         capture_output=True, text=True).stdout.split()
    ok = True

    def expect(name, cond, what):
        nonlocal ok
        print(f"{'PASS' if cond else 'FAIL'} {name}: {what}")
        ok &= bool(cond)

    A = case(base, repo, 'A', 'sleep', lambda s, d: s - 120, 6, 3)
    expect('A', A['rc'] == 0, f"exit 0 (got {A['rc']})")
    expect('A', A['STOP'], 'STOP touched')
    expect('A', 'SIGTERM to sampler' in A['log'], 'sampler got SIGTERM')
    expect('A', 'only its caffeinate' in A['log'], 'caffeinate released run.sh')
    expect('A', 'run.sh exited' in A['log'], 'run.sh exited')
    expect('A', A['procs_before'] >= 3 and A['procs_after'] == 0, f"fake processes {A['procs_before']} -> {A['procs_after']}")

    B = case(base, repo, 'B', 'sleep', lambda s, d: s - 30, 6, 3)
    expect('B', B['rc'] == 2 and 'FAIL !!!' in B['log'] and 'less than 60 s old' in B['log'], 'FAIL on a young last call')
    expect('B', not B['STOP'] and B['procs_after'] == B['procs_before'], 'nothing touched or killed')

    C = case(base, repo, 'C', 'sleep', lambda s, d: d, 6, 3)
    expect('C', C['rc'] == 2 and 'at or after the deadline' in C['log'], 'FAIL on a call at the deadline')
    expect('C', not C['STOP'] and C['procs_after'] == C['procs_before'], 'nothing touched or killed')

    D = case(base, repo, 'D', 'done', lambda s, d: s - 120, 6, 3)
    expect('D', D['rc'] == 0 and 'ended by itself' in D['log'] and 'SIGTERM to sampler' not in D['log'],
           'DONE path kills no sampler')
    expect('D', 'only its caffeinate' in D['log'] and 'run.sh exited' in D['log'] and not D['STOP'], 'run.sh released, no STOP')

    real_sampler_after = subprocess.run(['pgrep', '-f', f'collector/sampler.py run .* {REAL_DATA} '],
                                        capture_output=True, text=True).stdout.split()
    expect('real', real_sampler_before == real_sampler_after and real_sampler_after,
           f'real sampler untouched {real_sampler_before} -> {real_sampler_after}')
    expect('real', not os.path.exists(os.path.join(REAL_DATA, 'STOP')), 'no STOP in the real data folder')
    for n, r in (('A', A), ('B', B), ('C', C), ('D', D)):
        print(f'--- log {n}\n{r["log"]}', end='')
    print('ALL PASS' if ok else 'SOME FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(os.path.abspath(sys.argv[1])))
