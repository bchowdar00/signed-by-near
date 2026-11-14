# Independent re-derivation of the thesis numbers: common rules

Written 2026-11-13T11:14Z by the reviewing session. It applies to every analyst brief in this folder.

## Objective

The author has published numbers for a frozen, pre-registered method. Your job is to re-derive your family's numbers **independently**, from the raw sample and the written method alone. A second implementation that agrees is strong evidence; one that disagrees shows where to look. You are not shown the published numbers, and you must not look for them. Agreement is judged by the reviewing session, not by you.

## The spec (read in full before coding)

- `repo/METHOD.md` (345 lines). This is the frozen method.
- `repo/DEVIATIONS.md` (153 lines). Its "Interpretations (stage 2)" settle the points METHOD leaves open, so follow them. Where they conflict with METHOD, follow DEVIATIONS and say so.

## Files you may read (closed list)

Repo, at `repo/`:
- `METHOD.md`, `DEVIATIONS.md`;
- `frozen/instants.json`: every window, with id, key, family, stratum, segments_ns/segments_utc, weight, n_h, D_s, covered_s, nominal_s, tier, token, month, period, whole and guard_s; `meta` holds T0, the seed and so on;
- `frozen/nd_plan.json`, `frozen/rates.json`, `frozen/tokens.json`;
- `registry/callers.json`, plus `registry/BRIEF-callers.md` and `registry/sources-*.md` if you need a class's evidence;
- `inputs/reference.json`: frozen prices, NearStats V figures and chain lists. Check its figures against the source files below wherever your brief says so;
- `collector/design.py`, `collector/nb.py`, `collector/nd.py`, `collector/rpc.py`, `collector/tokens.py` and `collector/sampler.py`, **for data formats and the window design only**. sampler.py imports a module `flows` from `analysis/`. Do not open it.

Raw sample, at `<data_dir>`:
- `nb/windows.jsonl`: execution events; a window is done if it has an `event: completed` line;
- `nb/pages/<window id>/<seg>-<page>.json`. Each page has keys done, hi_ns, lo_ns, http, n_rows, next, page, path, rows, seg, utc and window. Enumerate a window's pages with `os.listdir` on that one named directory, taking the window ids from `instants.json`;
- `nb/txns/<tx hash>.json`, `nb/resolve.jsonl`, `nb/RESOLVED`;
- `nd/blocks.jsonl`: neardata blocks. `part` is `sample:YYYY-MM` or `contiguous`. `calls` holds the sign and respond receipts in that block with args, signer, predecessor, status and ts_ns;
- `rpc/supply.jsonl`, `rpc/operators.jsonl`, and `rpc/raw/` if needed;
- `STATUS.json`.

Sources, at `<sources_dir>`, only the files your brief names.

## Files and actions that are forbidden

- **Anything that shows the author's results or analysis:**
  - `repo/analysis/`, `repo/publish/`, `repo/out/`, `repo/tests/`;
  - `repo/rebuild.py`, `repo/verify.py`;
  - `repo/THESIS*.md`, `repo/POST-FREEZE.md`, `repo/AFTER-READ.md`;
  - `repo/postfreeze/`, `repo/deadline/`, `repo/extension/`, `repo/audit/` (S1 may read `repo/audit/` only for its last step);
  - `repo/inputs/*.py`, `repo/inputs/hsp007-ledger.json`;
  - the author's review notes, and any other file not listed above.
- **No network at all.** No HTTP call to NearBlocks, RPC, neardata or anything else. Everything is computed offline from the files above.
- Write nothing outside your own output folder. Edit no file anywhere else.
- No `pip install`. Python is `python3 -I` with numpy 2.5.1 only (no scipy, pandas or statsmodels). Implement the beta and chi-square quantiles yourself with `math` (lgamma, the continued fraction for the regularized incomplete beta, the series or continued fraction for the incomplete gamma, then bisection). Test them before use against these known values:
  - Clopper–Pearson lower bound with all successes = 0.025^(1/m): m = 3 → 0.29240, 6 → 0.54074, 18 → 0.81470, 36 → 0.90261;
  - Garwood two-sided 95% upper bound at k = 0 is 3.6889 per unit exposure;
  - Garwood at k = 10 is [4.7954, 18.3904].

## How to compute

- **Bootstrap.** 2,000 draws, stratified, with windows resampled with replacement within each stratum. Run every bootstrap **twice, with seeds 1 and 2**, and report both intervals, so the Monte Carlo spread is visible. Percentiles use numpy's default (linear, type 7). Count the draws dropped for a zero denominator. If more than 5% are dropped, the reading is "unstable".
- **Hulls.** For every hulled interval, say which component set each end: the bootstrap, the window-level bound or Garwood.
- Report numbers at full precision (at least 6 significant figures), not rounded.
- **Completion.** A window is completed only if it has a `completed` event and its pages form a gapless chain that is done, all HTTP 200 (DEVIATIONS 17). A reading with any stratum holding an uncompleted window is "not completed". Never estimate from the part done; say "not completed" and name the windows.

## Stop-and-report rule

If the data contradict the method, a file is missing or malformed, or METHOD and DEVIATIONS do not settle a choice:
- say so in a section "Interpretations I made", with the choice and its alternative;
- where cheap, compute both;
- never silently pick one.

If you are about to run out of turns, write what you have first.

## Output (in your own folder)

- your code (`*.py`), runnable with `python3 -I`;
- `RESULTS.md`, updated after each deliverable rather than only at the end, with:
  - a table: quantity | value | method or formula | inputs | notes;
  - a "Telemetry" section: windows read per family and stratum, rows read, rows deduplicated, transfers built, transfers dropped and why, run time;
  - "Interpretations I made";
  - "Anomalies";
- `results.json` with the same numbers, machine-readable.

Your final message to the reviewing session is short: what you computed, the path to RESULTS.md, what you could not compute and why, and every anomaly. Do not paste long tables into the message.
