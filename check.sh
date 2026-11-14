#!/bin/sh
# One command for the whole check, offline: recompute every number, table and chart from the saved rows,
# fill the write-up and the pages, compare with the committed outputs, run the tests and check the manifests.
#
#   sh check.sh
#
# Python 3 only, no key, no install, about three minutes. It runs steps 1 to 6 of README.md, "Reproduce it",
# in order, with the Explorer read's offline checks, and stops at the first step that fails. Its last line is
# "ALL OK" with what was checked. Written after the counted read; not one of the timestamped files.
set -eu
cd "$(dirname "$0")"
step() { printf '\n== %s\n' "$1"; }
if command -v shasum >/dev/null 2>&1; then SUM='shasum -a 256'; else SUM=sha256sum; fi

step '1 of 7: keep the committed outputs to compare with'
# kept from an earlier run if it is there: after step 2, out/ no longer holds the committed results files
[ -d out-committed ] || cp -R out out-committed

step '2 of 7: recompute every number, table and chart from the saved rows'
python3 -I rebuild.py data --draft

step '3 of 7: fill the write-up and the pages, and check them'
python3 -I publish/written.py data

step '4 of 7: compare with the committed outputs'
python3 -I publish/same_out.py out-committed out

step '5 of 7: the tests'
python3 -I -m unittest discover -s publish
H=$(mktemp -d)
mkdir -p "$H/Data/hackathons/near-2026/b-collect/pilot"
cp tests/fixtures/stage1-local/rates-plan-draft.json "$H/Data/hackathons/near-2026/b-collect/pilot/"
HOME="$H" python3 -I -m unittest discover -s tests
python3 -I -m unittest discover -s explorer

step '6 of 7: the Explorer read, recomputed from its published sums and set beside the second implementation'
python3 -I explorer/analyse.py explorer/data/blocks.jsonl explorer/data/assets.json explorer --check
python3 -I rederive/explorer/compare.py explorer/results.json rederive/explorer/out/rederived.json

step '7 of 7: the manifests'
for m in postfreeze/MANIFEST-postfreeze.txt frozen/MANIFEST-stage2.txt frozen/MANIFEST-stage1.txt \
         deadline/MANIFEST-deadline.txt afterread/MANIFEST-afterread.txt data/MANIFEST-data.txt \
         explorer/MANIFEST-explorer-stage1.txt explorer/MANIFEST-explorer-stage2.txt explorer/MANIFEST-explorer-stage3.txt; do
  $SUM -c "$m" >/dev/null
  echo "ok: $m"
done
(cd preread && $SUM -c MANIFEST-preread.txt >/dev/null)
echo 'ok: preread/MANIFEST-preread.txt'

printf '\nALL OK: every number, table and chart recomputed from the saved rows; the write-up and the pages are the committed bytes; the tests pass; 10 manifests check.\n'
