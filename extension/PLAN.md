# Extension pass for the windows the frozen run leaves not completed

Status: DRAFT. Not run, not stamped. It needs Bhargav's yes before any part of it runs. The frozen run's primary reading stands whatever is decided here.
Last reconciled: 2026-11-12T22:23Z (Claude).
Known gaps:
- NearBlocks' real limit is inferred from our own calls, not from its documentation. No rolling-window model fits all of the refusals (see below).
- The timeline assumes NearBlocks accepts the extension's calls the way it accepted every call between 10:06Z and 12:37Z on Nov 11 and Nov 12.
- It also assumes no other caller on this network uses NearBlocks between 00:00Z and the end of the pass.
- The counts are the state at 22:07Z Nov 12, when the ledger was full until 10:02:38Z Nov 13. The pass takes whatever has no `completed` line when the run is stopped.

## Why

At STATUS 2026-11-12T18:50:20Z, when the last window completed, tier 1 was complete and tier 2 was short. NearBlocks has refused every call since 19:05:19Z.

| Family | Done | Total |
|---|---|---|
| migration | 57 | 75 |
| sign tier 2 | 74 | 90 |
| index | 11 | 13 |

The sampler works through the frozen order, so the 36 unfinished windows are the last 36 of `frozen/instants.json` (orders 490 to 525). The first is `migration:zec.omft.near:early#0` (id 857b17689c5e), the page the run is stuck on. Their family counts match STATUS exactly. Their frozen cost estimates are 41.0 credits (plan) and 48.8 (stress).

Losing them costs four readings:
- M10's migration verdicts for SOL and ZEC and the ETH control. Their early strata have only 6, 5 and 7 of their 8 windows; BTC's 16 are complete. SOL's two missing windows are the 31st and 32nd of the 36, so a pass refused part-way can finish ZEC and ETH and still miss SOL.
- 12 of M10's 28 monthly chart points (BTC 4, ETH 3, SOL 3, ZEC 2).
- M3/M4 for 10 of the 15 older months: 2024-08, 2024-10, 2024-12, 2025-01, 2025-02, 2025-05 to 2025-08, and 2025-10.
- Two months of M6's destination list: 2026-02 and 2026-08.

## Decision 1, before 00:00Z: the frozen run does not stop at its deadline on its own

`sampler.py` checks the deadline only between calls. `nb.NB.get` waits for ledger quota without looking at the deadline.

The ledger shows that this already happened twice. Overnight retries of the same URL span the gap:
- attempt 2 at Nov 10 20:54:38Z, then attempt 3 at Nov 11 10:02:38Z;
- attempt 4 at Nov 11 21:59:01Z, then attempt 5 at Nov 12 10:02:38Z.

Tonight's last call was at 22:06:30Z (refused). The ledger then held 300 credits in the last 24 hours, and none of them leaves the window before 10:02:38Z Nov 13. So the sampler sleeps inside `NB.get` until about 10:02:38Z Nov 13, and would then call NearBlocks after the 00:00Z deadline. If that page completed a window, the window would be marked completed with data fetched after the deadline. `nb/DONE` would appear only after that, at about 10:03–10:30Z.

- **A (recommended).** At 2026-11-13T00:00:00Z, run `touch ~/Data/hackathons/near-2026/b-collect/STOP`, then end the sampler process (`collector/sampler.py run`, PID 25971 on Nov 12). At that moment it is asleep waiting for quota with no request in flight; check that the ledger's last line is before 00:00Z. The `nd` and `rpc` loops are already DONE, so `run.sh` then exits.
  - The primary ends at the frozen deadline, and its last call stays at 22:06:30Z.
  - The sampler does not write its `not_completed` lines. The measures do not need them: `core.window_complete` is the only gate, and it needs a `completed` line. The one visible difference is that the completeness table in `recompute`'s output (`measures.completeness`) lists the 36 as "pending" instead of "not completed". THESIS reports them as not completed.
  - `run_ext.py select` accepts this ending (STOP present, deadline passed, no sampler running).
- **B.** Leave it. The primary then calls NearBlocks at about 10:02Z Nov 13. Any window it completes after 00:00Z would need its own rule (a deviation) before the reading.
- **Ruled: A** (parent, 2026-11-12, about 14:00Z). A nohup'd timer carries it out at 00:00:30Z: `review/deadline-stop/deadline_stop.py`, PID 57431. Its checks, its test and the deviation text are in `best-price/review/POST-FREEZE.md`.
  - run.sh cannot exit by itself, because its `wait` also waits for its own `caffeinate -w $$`. The timer ends that caffeinate once the loops have ended.
  - So if this pass is approved, run it under its own `caffeinate -i`.

## What NearBlocks actually allowed

These counts come from the ledger (944 lines at 22:07Z Nov 12), the 88 `nb status=429` lines of `logs/nb.log` and the 7 of `logs/pilot-m10.log`, matched one to one by URL and attempt.

| Day | Accepted | Refused | Refusals |
|---|---|---|---|
| Nov 10 | 266: 256 from 10:02:38Z to 12:37:08Z (40 pilot, 216 counted), 10 from 17:09:10Z to 17:21:13Z | 34 | 7 pilot calls from 10:03:30Z to 10:11:48Z, each the 6th inside 60 s at the pilot's 10.5 s spacing; 27 from 17:21:25Z to 20:54:38Z |
| Nov 11 | 262 (10:06:38Z to 12:37:08Z) | 38 | one at 10:02:38Z; 37 from 17:09:10Z to 21:59:01Z |
| Nov 12 | 277: 262 from 10:17:39Z to 12:37:08Z, 15 from 17:09:10Z to 18:50:18Z | 23 | one at 10:02:38Z; 22 from 19:05:19Z to 22:06:30Z |

- On Nov 11 and Nov 12 the first morning call (10:02:38Z) was refused. After it every call was accepted to 12:37Z: from 10:06:38Z on Nov 11 and from 10:17:39Z on Nov 12.
- No rolling-window count of our calls (24 to 48 hours, accepted-only or all calls) separates accepted calls from refused ones. NearBlocks is counting something our ledger does not: refused calls on another clock, coarser time buckets, or calls from elsewhere on this IP.
- Each refusal used a ledger credit, and the retries kept the evening slots full. That is the loop.

## The pass

**Code:** `extension/run_ext.py` (select, run), `extension/merge.py`, `extension/test_extension.py` (4 offline tests, passing). It imports the frozen `collector/sampler.py` and `collector/nb.py` unchanged.

1. **Select.** Run after the primary has ended (decision 1).
   - It reads only the `id` and `event` of each `nb/windows.jsonl` line. The windows with no `completed` line form the set, which must be the tail of the frozen order, or the pass stops.
   - It writes `<ext>/instants-ext.json` (frozen instants, those windows only) and `<ext>/selection.json`.
   - It copies the primary ledger into `<ext>/nb/ledger.jsonl`, so the cap sees every earlier call. Nothing in the primary folder is written.
2. **Run** in a separate folder, `~/Data/hackathons/near-2026/b-extension/`, with ledger purpose `extension (after the frozen run; extension/PLAN.md)`.
   - **Cap:** 262 credits in any rolling 24 hours, counting every ledger line, refused ones too. 262 is the number NearBlocks accepted on each of the last two mornings (Nov 11 and Nov 12). Nov 10's morning had 263 calls, but 7 of them were the pilot's per-minute refusals, so 256 were accepted. The frozen pacing (5 a minute, 12.5 s apart) is kept.
   - **Hours:** not before 10:45Z Nov 13. Refusals cleared somewhere between 10:02:38Z and 10:06:38Z on Nov 11, and between 10:02:38Z and 10:17:39Z on Nov 12, so 10:45Z leaves 27 minutes after the later. The later start costs no time (below). The hard stop is 13:00Z, and no call is made whose quota frees after it.
   - **One try per request.** The first 429, or any status other than 200, ends the pass, and every unfinished window is marked `not_completed` in the extension folder. A network error gets one retry after 60 s. Nothing loops.
   - **No transaction resolution.** Migration windows are tier 2 and are read from their observed legs (DEVIATIONS 4). Sign and index windows do not need it.
3. **Merge** into a fresh third folder: copies, never links.
   - It holds the primary's `nb/`, `nd/` and `rpc/`. The selected windows' pages come from the extension only, and the extension's status lines are appended.
   - Then the frozen command, unchanged: `python3 -I analysis/recompute.py frozen/instants.json <merged> <out-extended>`.

**Credits and time.** I simulated the pass with the frozen `nb.Ledger` on a copy of the ledger as it stood at 22:03Z Nov 12, with the 262 cap and one credit and one second per call. I ran it both with and without tonight's last call (22:06:30Z):
- the first call goes at 10:45Z, and 9 or 10 calls fit before 11:52:19Z;
- the 41st call (41.0 credits, plan) lands at 11:58:34–11:58:46Z, the 49th (48.8, stress) at 12:00:14–12:00:26Z, and the 60th at 12:02:32–12:02:44Z;
- the same times hold for a start at 10:20Z, 10:30Z or 11:00Z. The cap sets the pace, not the start.

The pace picks up at 11:52:19Z, when Nov 12's 11:52–12:37Z calls start leaving the ledger's 24-hour window.

Merging and recomputing take about a minute. If NearBlocks refuses, the pass stops at that call. The cost is one credit, and nothing already fetched is lost.

## How it is reported

- **The decision and the stamp come before any counted row is read.**
- **The primary reading stays primary**, exactly as frozen: `recompute` on `b-collect`. The windows not completed read "not completed at the deadline".
- **The extended reading is secondary** and labelled: "extension pass after the frozen deadline, by a plan stamped before that deadline". THESIS shows it beside the primary wherever they differ, and never in its place.
- **The extended reading is published whatever it shows.**
- **If the pass ends early,** the windows it completed count, and every measure with a stratum still short stays "not completed".

## Frozen files

None changes:
- the stage-1 and stage-2 manifests stay as they are;
- `DEVIATIONS.md` is not appended to, because appending would change a stage-2 hash; this file and `review/POST-FREEZE.md` are the deviation record, and the README and THESIS say so;
- `run.sh` is not touched.

Decision 1A ends a process; it does not edit a file.

## Stamp: one manifest, before 2026-11-13T00:00Z

The stop record is stamped whatever the answer, by 23:50Z. Byte copies of `review/POST-FREEZE.md`, `review/deadline-stop/deadline_stop.py` and its offline test go into `repo/deadline/`, listed in one manifest together with the stage-2 manifest. If Bhargav says yes before that stamp, this plan and its code join the same manifest, so there is one stamp. Once stamped, none of the listed files changes.

Not run. Every command runs from the repo's root, `best-price/repo`, whose parent folder holds `review/`:

```bash
mkdir -p deadline
cp -p ../review/POST-FREEZE.md ../review/deadline-stop/deadline_stop.py ../review/deadline-stop/test_deadline_stop.py deadline/
```

With a yes:

```bash
shasum -a 256 deadline/POST-FREEZE.md deadline/deadline_stop.py deadline/test_deadline_stop.py extension/PLAN.md extension/run_ext.py extension/merge.py extension/test_extension.py frozen/MANIFEST-stage2.txt > deadline/MANIFEST-deadline.txt
```

Without:

```bash
shasum -a 256 deadline/POST-FREEZE.md deadline/deadline_stop.py deadline/test_deadline_stop.py frozen/MANIFEST-stage2.txt > deadline/MANIFEST-deadline.txt
```

Then:

```bash
python3 -I collector/ots.py stamp deadline/MANIFEST-deadline.txt
```

## Deviation text, for THESIS and the README

> The counted run reached its frozen deadline (2026-11-13T00:00Z) with 36 tier-2 windows not completed. NearBlocks refused calls each evening below the 300-a-day budget the design assumed. The primary results treat those windows as not completed, as METHOD §7 requires. A separate pass, written and timestamped before the deadline, re-read exactly those windows on Nov 13 into its own folder. It ran under a lower cap and stopped at the first refusal. Its results are shown beside the primary ones as a secondary reading, whatever they show. No frozen file was changed.

## Other callers

No NearBlocks call of any kind from this network between 2026-11-13T00:00Z and the end of the pass (13:00Z at the latest). That includes the build lead's calls and a browser open on nearblocks.io. They are not in this ledger and would use the same allowance. A call that cannot wait is recorded in `<ext>/nb/ledger.jsonl` before it is sent.
