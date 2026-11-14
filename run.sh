#!/bin/bash
# Counted run (METHOD-b §6, §10). Starts the three collectors, each in a restart loop that ends
# only when its DONE file exists, all under caffeinate so the Mac does not sleep.
#
#   ./run.sh <frozen instants.json> <nd_plan.json> <data_dir>
#
# Logs: <data_dir>/logs/{nb,nd,rpc}.log. Stop with: touch <data_dir>/STOP (each loop exits after
# its current process ends); or kill the loops' process group. Never edit this file while it runs.
set -u
INST="$1"; PLAN="$2"; D="$3"
HERE="$(cd "$(dirname "$0")" && pwd)"
C="$HERE/collector"
mkdir -p "$D/logs" "$D/nb" "$D/nd" "$D/rpc"
[ -f "$INST" ] && [ -f "$PLAN" ] || { echo "missing instants or plan"; exit 1; }

loop() {  # name, done-file, command...
  local name="$1" done="$2"; shift 2
  until [ -f "$done" ] || [ -f "$D/STOP" ]; do
    echo "$(date -u +%FT%TZ) start $name" >> "$D/logs/$name.log"
    "$@" >> "$D/logs/$name.log" 2>&1
    echo "$(date -u +%FT%TZ) exit $name code=$?" >> "$D/logs/$name.log"
    [ -f "$done" ] || sleep 60
  done
  echo "$(date -u +%FT%TZ) loop $name ended" >> "$D/logs/$name.log"
}

caffeinate -dimsu -w $$ &
loop nb  "$D/nb/DONE"  python3 -I "$C/sampler.py" run "$INST" "$D" --purpose counted --ledger "$D/nb/ledger.jsonl" &
loop nd  "$D/nd/DONE"  python3 -I "$C/nd.py" run "$PLAN" "$D" &
loop rpc "$D/rpc/DONE" python3 -I "$C/rpc.py" run "$PLAN" "$D" &
wait
