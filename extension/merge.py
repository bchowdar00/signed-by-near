"""Builds the extended data folder for the secondary reading (DRAFT; extension/PLAN.md).

  python3 -I extension/merge.py <primary data dir> <ext dir> <merged dir>

The merged folder is a fresh copy (never hard links, so nothing written there can reach the
primary): the primary's nb/, nd/ and rpc/, except that for every window the extension selected,
the primary's pages are left out and the extension's pages are used instead, and the extension's
status lines are appended to the copied nb/windows.jsonl (analysis/core.py counts a window as
completed if any of its lines says so). Then the frozen command runs unchanged on it:

  python3 -I analysis/recompute.py frozen/instants.json <merged dir> <out-extended>

The primary folder is only read. Nothing in it changes.
"""
import json, os, shutil, sys


def merge(primary, ext, merged):
    if os.path.exists(merged):
        raise SystemExit(f'{merged} exists; use a fresh path')
    with open(os.path.join(ext, 'selection.json')) as f:
        ids = set(json.load(f)['ids'])
    if not os.path.exists(os.path.join(ext, 'nb', 'DONE')):
        raise SystemExit('the extension pass has not ended (no nb/DONE)')
    os.makedirs(merged)
    for d in ('nd', 'rpc'):
        if os.path.isdir(os.path.join(primary, d)):
            shutil.copytree(os.path.join(primary, d), os.path.join(merged, d))
    skip = lambda src, names: [n for n in names if os.path.basename(src) == 'pages' and n in ids]
    shutil.copytree(os.path.join(primary, 'nb'), os.path.join(merged, 'nb'), ignore=skip)
    for wid in ids:
        src = os.path.join(ext, 'nb', 'pages', wid)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(merged, 'nb', 'pages', wid))
    with open(os.path.join(ext, 'nb', 'windows.jsonl')) as f:
        add = [line for line in f if line.strip()]
    with open(os.path.join(merged, 'nb', 'windows.jsonl'), 'a') as f:
        f.writelines(add)
    n_done = sum(1 for line in add if json.loads(line)['event'] == 'completed')
    print(json.dumps({'merged': merged, 'extension_windows': len(ids), 'completed_by_extension': n_done}))


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    merge(*sys.argv[1:4])
