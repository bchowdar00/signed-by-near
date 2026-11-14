# S2: M4 caller mix, M5 concentration, the trend, M6 purpose

Read `COMMON.md` first; its rules bind you. Output goes in this folder. The deliverables are in priority order. Write RESULTS.md after each one.

## 1. Inputs
- **Sign windows.** Build your own reading of every `sign` window in `instants.json`:
  - whether it completed (COMMON's rule);
  - the calls inside its segments, counting each distinct receipt id once within the window;
  - each call's predecessor;
  - the HT weight.
- **The neardata sample.** Read `nd/blocks.jsonl` rows with `part` `sample:YYYY-MM`. For each month give:
  - the blocks present and the blocks missing;
  - the sign calls, with predecessor and `signer`;
  - the FastAuth calls (predecessor `fast-auth.near`), split by `signer`.
- **Classes.** Apply METHOD §5 with `registry/callers.json`, in its rule order, to every predecessor you see. List each predecessor seen with its class and its HT total. Predecessors that are not in the registry are class 5, unless a rule in §5 places them (for example `*.bridge.near` or `<40-hex>.aurora`). Say which rule placed each one.

## 2. M4 (METHOD M4, §5; DEVIATIONS 5, 9)
For each calendar month from 2024-08 to 2026-11:
- **Class shares** of all calls (HT), for 1, 2a, 2b, 2c, 3, 4, 4x and 5. FastAuth is split by that month's neardata signer shares where a sample exists (state which months have one), and is unattributed before that.
- **The four classifications:**
  - main = 4 + 4x + 2a + 2b;
  - main without Sweat = 4 + 4x + 2b;
  - narrow = 4;
  - broad = everything except 1 and 3.
- **Intervals for main and main without Sweat**, per DEVIATIONS 9:
  - the stratified bootstrap with the NearBlocks windows and the neardata blocks resampled together (seeds 1 and 2), with the dropped-draw count;
  - hulled with (4 + 4x) ÷ all + (FastAuth ÷ all) × [s_L, s_U], where [s_L, s_U] is the block-level Clopper–Pearson bound and m is the Kish effective number of sampled blocks holding a FastAuth call. Give s, m and the bound.
- **Months without a sample.** For main, give the range with all of FastAuth counted in and with none.
- **Class-3 sensitivity.** Give every share again with class 3 moved into class 5.
- **"Not completed"** where any of the month's strata has an uncompleted window.

## 3. M5 (METHOD M5; DEVIATIONS 5)
For each month:
- the top-1 and top-3 callers by HT share, with their names. FastAuth is split into its signers where a sample exists, and kept whole before that;
- the share from apps that have announced an end (Sweat, class 2a).

Also name the single largest caller in October 2026, and give its share.

## 4. Trend (METHOD §7 Trend; DEVIATIONS 14, 24)
Give the ratio of the mean daily rate in the last 3 complete months before T0 to that in the 3 months before them. State which months these are, and their day counts. Give it three ways:
- raw;
- excluding classes 3 and 2a;
- excluding 2a only (class 3 kept).

For each: the point; the stratified-bootstrap interval for seeds 1 and 2, with 2a removed by each month's signer shares inside the draw; and the reading (growing, shrinking or inconclusive).

## 5. M6 purpose (METHOD M6; DEVIATIONS 18). Lower priority, so do it last.
For each month with a neardata sample:
- the share of the sampled sign calls that are secp256k1 (domain 0), Ed25519 on a FastAuth login path (`jwt#…`), and other Ed25519 (domain 1);
- those shares applied to that month's M3 rate.

State how you read the domain and the path from the call args.
