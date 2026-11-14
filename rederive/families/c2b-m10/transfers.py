"""Shared: build transfers for flow / migration windows by token+period/stratum. python3 -I."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import lib

meta, WINDOWS = lib.load_windows()
EV = lib.load_status()
BYID = {w['id']: w for w in WINDOWS}


def flow_windows(token, period=None):
    out = [w for w in WINDOWS if w['family'] == 'flow' and w['token'] == token
           and (period is None or w['period'] == period)]
    return out


def migration_windows(token, stratum_suffix):
    """stratum_suffix: 'early' or 'chart:YYYY-MM'."""
    out = [w for w in WINDOWS if w['family'] == 'migration' and w['token'] == token
           and w['stratum'].endswith(':' + stratum_suffix)]
    return out


def build_for_windows(wins):
    """Return list of (window, [transfers]) and whether every window completed."""
    res = []
    all_ok = True
    for w in wins:
        ok, _ = lib.is_completed(w, EV)
        if not ok:
            all_ok = False
        tr = lib.window_transfers(w) if ok else None
        res.append((w, tr, ok))
    return res, all_ok
