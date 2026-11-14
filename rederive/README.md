# `rederive/`: a second implementation

This folder recomputes the numbers in `THESIS.md` with code written apart from the analysis code. The sessions that wrote the four parts below were given the method and the saved rows, and told not to read the analysis code or any result. `rebuild.py` shows that the frozen code gives the same output on every run. This folder checks whether different code, written from `METHOD.md` and `DEVIATIONS.md`, gets the same numbers from the same rows in `data/`.

It was written and run on 2026-11-13, after the first read of counted results (11:00:30Z, logged in `AFTER-READ.md`); the common brief is stamped 11:14Z. It is not among the stamped files and no test imports it. One sentence of `THESIS.md`, in §3.2 ("Sampling and intervals"), cites its seed sweeps, and `publish/check_thesis.py` reads `mc-seeds/sweep.json` to check that sentence.

## Run it

```bash
python3 -I rederive/run.py data
```

Offline. Python 3 with numpy, and nothing else. It takes about 15 seconds on a laptop. It runs the four parts and `checks/page_extras.py`, writes their outputs to `rederive/out/`, then compares them with the published results and writes `rederive/RESULTS.md` and `rederive/out/compare.json`. From a clone with nothing added, its last line is:

```
49 rows agree, recomputed by code; 0 checked against a source file; 7 need a source file not shipped; 6 not recomputed; 1 differ
```

It exits 1 if any number differs other than the two census numbers that `RESULTS.md` explains (row 15), or if a sentence a row quotes is no longer in `THESIS.md`.

### Files this repository does not ship

Some numbers come from third-party pages and feeds that were saved on Nov 9, 2026 and are not in this repository. `sources.json` gives each file's name, the URL it was saved from, the sha256 of the saved copy, and what reads it.

| File | Saved from | Read by |
|---|---|---|
| `gov-hsp007-execution-42147.json` | HSP-007's execution thread on gov.near.org | `families/m3-m8-m7/hsp007.py` (the payout ledger); `compare.py` (SVRN's onboarding date) |
| `nearstats-api-near-summary.json` | NearStats' summary feed | `compare.py` (the chains it lists as supported for Intents; its 30-day swap volume V and its 30-day total) |
| `web-update.swe.at_.html` | The Sweat Foundation's notice | `compare.py` (the date Sweat Wallet ends in its present form) |
| `web-docs.near.org_omnibridge_overview.html` | NEAR's Omni overview | `compare.py` (the chains it lists with Chain Signatures) |

Without them, `run.py` skips the code that reads them. It prints each missing file's name, URL and sha256, and counts those rows as "need a source file", never as agreeing. With copies in a folder:

```bash
python3 -I rederive/run.py data --sources <folder>
```

A copy is used only if its sha256 equals the one in `sources.json`. Live pages change, so a fresh download will usually not match, and its rows stay "need a source file". This run writes its own pair of files, `RESULTS-with-sources.md` and `out/compare-with-sources.json`, so it never overwrites the run from a bare clone. With the four Nov 9 copies, its last line is:

```
53 rows agree, recomputed by code; 5 checked against a source file; 0 need a source file not shipped; 4 not recomputed; 1 differ
```

## What each part computes

Each of the four parts was written by a separate AI coding session (the same tool that wrote the rest of this entry; see the main `README.md`, "Who and what made this"). Each had its own brief, in `briefs/`.

| Part | Folder | What it recomputes | Where on the page |
|---|---|---|---|
| Flow shares and migration | `families/c2b-m10/` | Which windows finished; the resolution audit; Omni's share for BTC, SOL and the Solana stablecoins; the early-2025 against 90-day comparison | Summary; §4.5 and §4.6; §6; §7.2 |
| Value and chains | `families/m9-m1/` | Omni's share of measured value; measured value and non-Omni value; coverage against NearStats; the census of Intents' legs; the chain-by-chain dominance test | Summary; §3.2; §4.1 and §4.2; §5; §6; §7.1 |
| Signer use, cost and service | `families/m3-m8-m7/` | `sign` calls a day by month; HSP-007's ledger, read from the saved thread; cost per request; request–response pairing; a check of the destination audit's saved lookups | §4.3, §4.4 and §4.7 |
| Who calls the signer | `families/m4-m5-trend/` | Caller classes by month; the largest callers; the trend ratio three ways; what October's calls signed | §4.3; §5; §7.1 |

Three more pieces do the rest:

- `mc-seeds/` re-runs two parts' bootstrap code over 40 and 60 seeds, to measure how far two interval ends move (§3.2; §4.1 and §4.5). It has its own `README.md`.
- `checks/page_extras.py` recomputes, from the saved files, counts the page states that the four parts do not output: the windows behind a bound, the readings per chain and unit, the blocks read per month, and the Zcash picks' inputs (§3.2; §4.2, §4.3, §4.5 and §4.7).
- `compare.py` compares everything, and reads the source files above for the rows that need them.

## How it was kept separate

Each of the four sessions got a brief with a closed list of files it could read (`briefs/`). The list held `METHOD.md`, `DEVIATIONS.md`, the window list and plans in `frozen/`, the caller registry, `inputs/reference.json`, the collector's code (for data formats only), the saved rows and named source files. It forbade the analysis code, the publishing code, the tests, `rebuild.py`, `verify.py`, every output in `out/`, `THESIS.md` and its templates, `POST-FREEZE.md`, `AFTER-READ.md` and the audit's own files. It also forbade network calls. The briefs did not give the published numbers, with two exceptions: the brief for `m9-m1` said the Omni overview's chains among the 28 "should be 10", and the brief for `m3-m8-m7` asked it to check October's "16 active at month-end".

This separation rests on the instructions, not on anything a reader can verify. The briefs are here so a reader can see exactly what each session was told. In `briefs/`, local paths and the names of internal roles have been rewritten, three internal notes are named together as "the author's review notes", and 2 lines that name the author's local folders have been removed. One of them told each session not to search the data and project folders recursively, and to open files by their named paths; the other forbade reading folders unrelated to this entry. `briefs/README.md` lists each change.

The rest was not written under these briefs: `run.py`, `compare.py`, `sources.json`, `checks/page_extras.py`, `mc-seeds/sweep.py`, and `families/m3-m8-m7/assemble.py`, which only gathers that part's outputs into one file. These were written by the session that compared the results, which had read the page and the published results. They take their values from the four parts' code and from the saved files, but their author knew the values they check. The same session moved the file paths in the parts' code to environment variables set by `run.py`, and reworded comments and three messages in `families/m3-m8-m7/audit_check.py` that named internal roles; none of those messages appears in today's outputs. No other line of the parts' code was changed.

## How the numbers are compared

`compare.py` reads the published side from `out/published/results.json`, `out/published/tables.md`, `out/combined.json`, the sentence of `THESIS.md` that each row quotes and, for one row, the collector's record in `data/nb/RESOLVED`. It reads the independent side from this folder's `out/`. Every published value passes through one of a few short readers in `compare.py` (`R`, `C`, `TBL`, `PAGE` and the like), which record the file it came from; `compare.py` stops with an error if a bare number is passed instead. For each number, `out/compare.json` records both values, the rule applied, the file each came from and the section of `THESIS.md` where it is printed. `RESULTS.md` shows the same for reading.

Each number gets one status:

- **agree**: recomputed by this code, and equal.
  - A value with no randomness (a point, a count, a sum, or an interval end set by the window-level Clopper–Pearson bound or by Garwood's bound) must be equal at the published precision.
  - An end set by the bootstrap cannot be equal to the digit, because the two implementations draw different random numbers. It agrees if it is within 5% of the published value of this code's end at seed 1 or seed 2. For shares the tolerance is 5% or 1 percentage point, whichever is larger.
  - For the ends with a sweep in `mc-seeds/` (Bitcoin's 90-day lower end over 60 seeds, and the non-Omni value's lower and upper ends per 30 days over 40), the published end must lie inside the sweep's range instead. Test 5's gap is checked against the range of gaps over the same 60 seeds.
- **source check**: read by `compare.py` from one of the files in `sources.json`, and equal to the published value.
- **needs source file**: the code for it reads a file this repository does not ship (see "Run it").
- **not recomputed**: no code here produces it, or it is an input the page restates (the freeze instant, or a figure NearStats reported), which this code reads from the same file the analysis read. Such an input is shown with its value under this status.
- **differs**: explained number by number in `RESULTS.md`.

A row takes the status of its weakest number. Rows are numbered 1 to 64; 47 is not used.

The 5% was set after the first comparison, not before. It is about the widest spread over 40 seeds in `mc-seeds/sweep.json`: across the 40 seeds the non-Omni upper end moves by 4.9% of its value, and its lower end by 4.8%. Two seeds can sit further apart where a stratum has few windows. The largest gap in the comparison is the April 2026 lower end of `sign` calls a day, which is in `out/published/results.json` but not on the page: 12,293 at seed 1 and 10,966 at seed 2, against 11,716 published, so 4.9% from the nearer seed. Every gap is printed in `RESULTS.md`, so a reader can apply a tighter rule.

The random seeds are fixed (1 and 2), so the numbers and `RESULTS.md` are the same on every run with the same numpy. Run after `rebuild.py`, `out/compare.json` differs in two lines only: the sha256 it records for `out/combined.json` and `out/published/results.json`, which the frozen code writes with one list in a different order on each run (the main `README.md`, step 4). It was run with Python 3.14.6 and numpy 2.5.1. `out/compare.json` records both versions and the sha256 of `THESIS.md` and of each published file it compared.

## What it found

From `out/compare.json` and `out/compare-with-sources.json` (`rows_by_status`, `numbers_by_status`):

| Run | Rows agree | Checked against a source file | Need a source file | Not recomputed | Differ | Numbers compared |
|---|---|---|---|---|---|---|
| From a clone | 49 | 0 | 7 | 6 | 1 | 570: 553 agree, 9 need a source file, 6 not recomputed, 2 differ |
| With the four Nov 9 copies | 53 | 5 | 0 | 4 | 1 | 576: 563 agree, 7 source checks, 4 not recomputed, 2 differ |

The run with the copies compares more numbers because the code that reads them adds its own. With them, NearStats' V and 30-day total move from "not recomputed" to "source check".

**Test 5, whether BTC is moving to Omni (§4.5; `RESULTS.md`, row 28).** The early upper end is 96.28%, with no randomness in it; the page prints 96.3%. The late lower end is 99.75% at seed 1 and 99.77% at seed 2, and 99.68% to 99.77% over the 60-seed sweep; the published 99.71% lies inside that range. The gap between the two ends is 3.47 points at seed 1, and 3.40 to 3.48 points over the sweep; the page says 3.4 points (96.3% against 99.7%). At every seed the test reads "moving to Omni".

**The row that differs (row 15).** The census of Intents' own legs, in `out/published/results.json` (`census/tokens`): this code counted the census rows outside the windows' segments as well, and finds 21 tokens and 1,675 rows. Counted inside the segments, as `METHOD.md` M1 says, the census has 15 tokens and 1,030 rows, as published. The code is left as written.

**Not recomputed (from a clone).**
- Chart 1's data in `out/published/results.json`: the per-month route flows and the completion grid (row 30).
- The interval [30.0%, 87.5%] around the share of October's 12 sampled `sign` calls that were FastAuth logins (§4.3; row 42; the 12 and the 58.3% are recomputed).
- The count of included transactions, 2,522 (row 5): the part's code types it instead of counting it.
- Three inputs the page restates: the freeze instant T0 (row 1), and NearStats' V, $831.3M, and 30-day total, $3,714.7M (rows 23 and 58). With the Nov 9 copy, `compare.py` reads V and the total from NearStats' feed.

While it was being compared, the second implementation also raised points that changed the page. None changed a reading or a test. Each is logged in `AFTER-READ.md`:

| Point | Where it is logged |
|---|---|
| HSP-007's payouts pool mainnet and testnet for June to August, while `METHOD.md` M8 shows them apart. The page now gives the mainnet figures beside the pooled ones | "The reviewer's round-1 fixes", finding 1 |
| One of the resolution audit's 20 transactions was refused by the server (HTTP 429) and never retried | finding 3 |
| M7's three unanswered requests are each the second of two identical requests, and a node's later response for each failed | finding 4 |
| Omni's share of all bridged BTC on NEAR fell to 10.1% in March 2026 before it recovered | finding 5 |
| Bootstrap ends carry Monte Carlo error larger than their last printed digit | finding 6 |
| Wording: chains seen in the census; SOL's 90-day share; the 1 yoctoNEAR deposit; two quotations | finding 7 and "Quotes" |
| HSP-007 pays from NEAR already minted and held in `treasury.near`, not from new issuance | the log row of 2026-11-13T14:18:19Z on HSP-007's funding |

## The Explorer read

`explorer/` holds a second implementation of the Explorer read (`THESIS.md` §4.8), written on 2026-11-14, after the pull. The session that wrote it was given `explorer/PLAN.md`, `explorer/STAGE2.md`, the token list (`explorer/data/assets.json`), the published sums (`explorer/data/blocks.jsonl`) and the SDK's list of 17 tokens. It was told not to read `explorer/analyse.py`, `explorer/sentences.py`, the results or `THESIS.md`. It is not among the stamped files, and `run.py` does not run it.

```bash
python3 -I rederive/explorer/rd_explorer_exact.py explorer/data/blocks.jsonl explorer/data/assets.json rederive/explorer/poa-tokens-migrated-to-omni-bridge.930d2816.ts <a new file>
python3 -I rederive/explorer/compare.py explorer/results.json rederive/explorer/out/rederived.json
```

Offline, standard library only. The first command writes the same bytes as `rederive/explorer/out/rederived.json`. The second prints `155 values compared; 0 differ`: for withdrawals and deposits, the USD sum and the count of swaps in each family, the bridged total, the six shares, the totals and shares for the chains the keyless sample read and for the others, and every chain's sum by family; then the 90-day and 30-day totals, the count of swaps and the count with no USD figure. Sums and counts must be equal to the digit, shares to 1e-25. `check_rd_explorer_exact.py` runs that code on made-up cells worked by hand (32 checks).

`poa-tokens-migrated-to-omni-bridge.930d2816.ts` is the Intents SDK's own file at commit `930d2816`, with the sha256 that `explorer/STAGE2.md` gives. The notes of the session that wrote it, on how it read the rules, are in the `readings` list of the output. One finding is worth knowing: the rule that places native BTC with Omni, on the operator's label, carries 99.73% of the Omni-form withdrawal value.

## What this does not show

- It was run after the read, so it is not pre-registered. It shows the published numbers follow from the method and the rows. It does not show the method was fixed in advance; the stamps do that.
- It reads the same saved rows as the analysis, so it does not test the collection. `verify.py` re-pulls a sample of windows for that.
- It follows the same `METHOD.md`, so it does not test the method's choices: the strata, the window-level bound, the prices fixed on Nov 9 or the five tests' thresholds.
- Both implementations were written by AI sessions of the same kind, so they can share a misreading of the method. Where the method left a choice open, each session's brief told it to say what it chose. `INTERPRETATIONS.md` gives those notes word for word.
- Some of this code departs from the method or types a value, and is left as written:
  - `families/m9-m1/` counts the census outside the windows' segments (row 15, above).
  - `families/m9-m1/assemble.py` writes the Omni overview count as a typed 10, the value its brief gave, and writes its row counts as typed telemetry. `compare.py` uses neither. It counts the Omni overview's chains among the 28 itself, from the lists in `inputs/reference.json` and, with the source copies, from NEAR's page.
  - `families/c2b-m10/make_results.py` types the count of included transactions (2,522). `compare.py` shows it as not recomputed (row 5).
  - `families/m4-m5-trend/run.py` types class 2b's share as 0. `compare.py` takes the 0 from the caller registry instead, which names no 2b signer (`DEVIATIONS.md` item 9).

## Files

```
rederive/
  README.md                       this file
  run.py                          the one command: runs every part, then compare.py
  compare.py                      compares; writes RESULTS.md and out/compare.json
  sources.json                    the files not shipped: name, URL, sha256, what reads them
  RESULTS.md                      the comparison, number by number, from a bare clone
  RESULTS-with-sources.md         the same, run with the four Nov 9 copies
  out/compare.json                the comparison as data, with counts, versions and input hashes
  out/compare-with-sources.json   the same, run with the four Nov 9 copies
  INTERPRETATIONS.md              each part's own list of the choices it made
  briefs/                         what each of the four sessions was told
  families/<part>/                each part's code, as written, file paths moved to variables;
                                  m3-m8-m7/assemble.py added to gather that part's outputs
  checks/page_extras.py           counts on the page that the parts do not output
  mc-seeds/                       the seed sweeps (its own README.md)
  explorer/                       the Explorer read a second time ("The Explorer read", above)
```

`run.py` also writes each part's working files under `out/`. They are rebuilt on every run.
