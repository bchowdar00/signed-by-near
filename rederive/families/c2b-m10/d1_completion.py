import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import lib
from collections import defaultdict

meta, windows = lib.load_windows()
ev = lib.load_status()

per_family = defaultdict(lambda: {'total': 0, 'completed': 0, 'not_completed': 0, 'windows': []})
not_completed = defaultdict(list)
detail = {'flow': [], 'migration': []}

for w in windows:
    fam = w['family']
    ok, reason = lib.is_completed(w, ev)
    pc = lib.window_page_count(w)
    per_family[fam]['total'] += 1
    if ok:
        per_family[fam]['completed'] += 1
    else:
        per_family[fam]['not_completed'] += 1
        not_completed[fam].append({'id': w['id'], 'key': w['key'], 'reason': reason})
    if fam in ('flow', 'migration'):
        detail[fam].append({'id': w['id'], 'stratum': w['stratum'], 'completed': ok,
                            'pages': pc, 'reason': reason if not ok else ''})

out = {
    'per_family': {k: {'total': v['total'], 'completed': v['completed'],
                       'not_completed': v['not_completed']} for k, v in per_family.items()},
    'total_windows': sum(v['total'] for v in per_family.values()),
    'total_completed': sum(v['completed'] for v in per_family.values()),
    'total_not_completed': sum(v['not_completed'] for v in per_family.values()),
    'not_completed_detail': {k: v for k, v in not_completed.items()},
    'flow_migration_detail': detail,
}
json.dump(out, open('d1_completion.json', 'w'), indent=1)

print('TOTAL windows:', out['total_windows'], 'completed:', out['total_completed'],
      'not_completed:', out['total_not_completed'])
for k, v in sorted(per_family.items()):
    print(f"  {k}: total={v['total']} completed={v['completed']} not_completed={v['not_completed']}")
print('not-completed by family:')
for k, v in not_completed.items():
    print(' ', k, [(x['id'], x['reason']) for x in v])
