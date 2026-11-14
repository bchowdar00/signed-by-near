# After the freeze: how the counted run ends

Status: the stop is armed but has not run yet. Timer PID 57431 wakes at 2026-11-13T00:00:30Z. The outcome below is filled in from its log after it runs. This file also fixes the rule for readings that rest on unfinished strata. This version is the one copied byte for byte into `repo/deadline/`, with the stop script and its test, for an OpenTimestamps stamp at 2026-11-12T23:35Z (`repo/deadline/MANIFEST-deadline.txt`).
Last reconciled: 2026-11-12T23:35Z (Claude, Best Price lead).
Known gaps:
- The outcome section stays empty until the timer has run.
- The script that applies the rule for readings on unfinished strata (below) is not written yet.
- The extension pass is a separate draft, not stamped, and needs Bhargav's yes (`repo/extension/PLAN.md`).
- Open, a publication call: whether `repo/deadline/` goes public whole. The byte copies of `deadline_stop.py` and `test_deadline_stop.py` carry local paths and cannot be edited, because their hashes are the proof. The parent leans toward publishing the manifest, the `.ots` and the hash lines, and keeping those two copies out with a line saying they are available on request.

This file is outside both frozen manifests. Nothing here changes a frozen file or a collected row.

## The gap

- **The sampler.** `collector/sampler.py` checks `DEADLINE_UTC` (2026-11-13T00:00:00Z) only between calls, and `nb.NB.get` waits for ledger quota without checking it.
  - The ledger shows two retries of the same URL that slept across the night: attempt 2 to 3 (Nov 10 20:54:38Z to Nov 11 10:02:38Z), and attempt 4 to 5 (Nov 11 21:59:01Z to Nov 12 10:02:38Z).
  - Tonight's last call was at 22:06:30Z, and NearBlocks refused it. The ledger then held 300 credits in the last 24 hours, and none of them leaves the window before 10:02:38Z Nov 13. So the sampler sleeps until about 10:02:38Z Nov 13 and would then call NearBlocks after the deadline. At 00:00:30Z its last call will be almost two hours old, so the timer's checks should pass.
- **run.sh.** It cannot exit by itself either: its `wait` also waits for its own `caffeinate -dimsu -w $$`, which in turn waits for run.sh. I reproduced this offline with a replica.

## The ruling and the stop

- **Ruling.** The parent session ruled on 2026-11-12, before the deadline, for option A: the sampler is stopped from outside at the deadline, by a nohup'd timer rather than by a chat session. The parent first re-checked the gap at the source.
- **The timer.**
  - Script: `review/deadline-stop/deadline_stop.py`, sha256 79113bf9be2ea8471a52495b1c4dfc94f9fc5ee34f3e930e90f43c89248a62c5.
  - Started 2026-11-12T14:00:41Z under nohup. PID 57431, re-parented to launchd. Log: `~/Data/hackathons/near-2026/watch/deadline-stop.log`.
- **What the timer does at 00:00:30Z:**
  1. It logs the ledger's last line. It goes on only if that line's `t` is before 00:00:00Z and at least 60 s old. `nb.py` writes `t` before it sends and times out at 40 s, so no request can still be in flight. If either check fails, it logs FAIL and acts on nothing.
  2. It touches `b-collect/STOP`, so run.sh's loop cannot restart the sampler.
  3. It finds the sampler afresh: the one process whose command line contains `collector/sampler.py run` and the data folder. It re-checks that `nb/DONE` is absent and the ledger has not moved, then sends SIGTERM, and SIGKILL after 30 s if the process is still alive.
  4. It waits up to 5 minutes. Once run.sh's only remaining child is its own caffeinate (the loops have ended), it ends that caffeinate, and run.sh exits.
  5. It logs the ledger's last line again.
  - If `nb/DONE` already exists at 00:00:30Z, it kills nothing and does only step 4.
- **Offline test.** `review/deadline-stop/test_deadline_stop.py` (sha256 529857fe7b2bdcdcf9219b8eb4836f235502780c29c87c88b3d51c0acf287a01) runs the real run.sh, copied byte for byte, with fake collectors in a scratch folder. 4 cases, 14 checks, all passing at 2026-11-12T14:00Z:
  - a normal stop;
  - a last call too young to be finished (FAIL, nothing touched);
  - a call at the deadline (FAIL, nothing touched);
  - the sampler already finished (nothing killed, run.sh released).
  - The real sampler and the real data folder were untouched.
- **Dry run against the live run** (`check`, which acts on nothing). It matched exactly sampler 25971 and run.sh 25958, whose children are caffeinate 25964 and the nb loop 25965. The ledger's last line was at 12:37:08.637Z.

## What it means for the data and the reading

- The sampler is ended while asleep, so it never writes the `not_completed` lines of the windows it has not finished. There is no `nb/DONE`, unless the sampler ends by itself first. Nothing is added by hand, and `nb/windows.jsonl` is not touched.
- The completeness table in `recompute` (`measures.completeness`) lists those windows as **pending**. Here "pending" means **"not completed at the deadline"**.
- Every measure gates on `core.window_complete`, which needs a `completed` line. So pending and not_completed give the same reading.
- THESIS uses the words "not completed at the deadline".

**Deviation text, for THESIS and the README:**

> The counted run's sampler checks its deadline only between calls. At the deadline, 2026-11-13T00:00Z, it was asleep waiting for its call quota and due to call again at about 10:02Z. Under a ruling made before the deadline, a timer stopped it from outside at 00:00:30Z, after checking that its last call was made before the deadline and had finished. The windows it had not completed carry no "not completed" line, and the results list them as pending, meaning not completed at the deadline. No frozen file and no collected row was changed.

## Readings that rest on an unfinished stratum: the method governs

This rule holds whatever is decided on the extension. If the extension pass runs, the rule covers whatever is still short after it.

> **Readings that rest on an unfinished stratum.** The frozen code still writes a number for a stratum whose windows did not all complete. An unfinished window keeps its frozen weight with empty values (`analysis/core.py:168`, `:607-608`), so totals and rates come from the finished windows only and run low. The frozen outputs then show those numbers:
> - `results.json` carries them with `complete: false`;
> - `tables.md` prints them beside "(not completed)";
> - THESIS prints the M10 early intervals beside a "not completed" verdict;
> - the charts draw them with no flag, because `analysis/charts.py` never reads `complete`.
>
> METHOD §6.10 says such a measure is "never estimated from the part done". The method governs. Everything the thesis shows a reader follows one rule: THESIS.md, its tables and both charts. A reading that rests on any unfinished stratum shows "not completed" and no number, interval, bar or dot.
>
> The rule depends only on which windows have a completed line. It was fixed and timestamped before any counted row was read. The frozen `results.json` and `tables.md` are published unchanged, with this note beside them. A script outside the frozen manifest applies the rule to make the published charts and the values THESIS.md prints. It changes no number it lets through.

What the rule covers:
- **M3, M4 and M5:** every month with `complete: false`.
- **M10, for a series with any unfinished M10 stratum (early or late):** its early, late and difference readings and its verdict all read "not completed". Tonight that is SOL, ZEC and the ETH control, whose early strata are short.
  - **Ruling.** This is the parent session's ruling (2026-11-12, about 22:15Z; reversible, and Bhargav can overrule it). It replaces a narrower draft that kept the finished late side.
  - **Reason.** The method's unit is the measure, not the reading. §6.10's Backstop says "Every measure with an incomplete stratum is then 'not completed'", and §7 item 1 calls a measure "not completed if any of its strata has a window marked not_completed". M10/SOL has an incomplete early stratum, so all of M10/SOL is not completed, however complete its late side is.
  - **Where the late share can still be read.** For SOL, the same 90-day share appears among C2b's sensitivities in tables.md (row `90d|amount|both`): the same flow strata, the same function and the same bootstrap, seeded by stratum name. For ZEC and the ETH control, which are not C2b groups, the late-period share is not shown for an M10 series with an unfinished stratum.
- **Chart 1, panel b:** for those series, no early or late dot or interval is drawn; a "not completed" mark stands in their place.
- **Chart 2:** an unfinished month's bars become a marked gap labelled "not completed".
- **M10's monthly chart points and the signature-index months:** an unfinished one gets a visible "not completed" mark, not a silent gap. The destination-audit picks come from completed months only, and the list names the months that are not completed.

The proving test is the reviewer's synthetic pair in `senior-review/workers/thesis-incomplete-evidence/`. Run A is complete. Run B removes the completed lines of five windows: two SOL early windows, one SOL chart month and two windows of `sign:2025-03`. The script passes if three things hold:
- in run B, THESIS.md and both charts hold no value that differs from run A's, apart from "not completed" marks where the list above blanks a reading. For M10/SOL that is its early, late and difference readings and its verdict;
- `grep -c "not completed"` on chart 2 gives at least 1;
- the stage-2 manifest still verifies.

Source: senior reviewer's finding T-1, `senior-review/THESIS-INCOMPLETE-RULE.md` (sha256 b27b8a2072c2f623a1638a473e259995112a0030b1f4e1608a9fa4e97e30b364). The Best Price lead re-checked every anchor at the frozen source at 22:12Z Nov 12, and METHOD.md line 270 holds the quoted text. The lead also re-read three of the synthetic results:
- run B's `tables.md` 2025-03 row reads 30 [13, 45] calls a day against run A's 42 [32, 54];
- SOL's early interval reads [43.2%, 100.0%] against [54.1%, 100.0%], while its late interval is [54.7%, 100.0%] in both;
- chart 2 holds no "not completed" string in either run.

The script and its test are not written yet; they come on Nov 13, and their hashes are recorded here when they are.

## What was read in the counted run's folder since the freeze

- **Best Price lead (confirmed against its session transcript, 1,651 tool calls, checked at 22:06Z Nov 12).** It read:
  - the ledger;
  - the 429 lines of `logs/nb.log` and `logs/pilot-m10.log`;
  - `STATUS.json`;
  - the `nb/DONE` and `STOP` markers;
  - two directory listings on Nov 12 (names and sizes only).
  - It opened no page, txns, resolve, `windows.jsonl`, `nd` or `rpc` file.
- **Parent session (its own report).** At 21:59Z Nov 12 it loaded the lines of `nb/windows.jsonl` in Python and printed only the window ids and the first line's key names. No `pages` or `rows` value was shown to it.
- **Senior reviewer (confirmed against its session transcript, 22:23Z Nov 12).** It read: the ledger (also copied to its scratchpad); the 429 lines and the last three lines of `logs/nb.log`; `STATUS.json`; listings of `logs/` and `nb/` and folder sizes (names and sizes only). It loaded the lines of `nb/windows.jsonl` in Python three times and printed only event counts, counts of completed ids by family and stratum against `frozen/instants.json`, and a line count. No `pages` or `rows` value was shown to it. It opened no page, txns, resolve, `nd` or `rpc` file. Its auditor worker ran the analysis on synthetic data only.
- Each `completed` line of `nb/windows.jsonl` carries the window's `pages` and `rows` counts (`collector/sampler.py`, line 254). Counting the lines or reading their ids does not show those values.

## Outcome

(To be filled in from `deadline-stop.log` after 00:00:30Z: the ledger's last line before and after, the sampler's exit, run.sh's exit, and the watch's FINAL line.)
