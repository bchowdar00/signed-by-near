# Deviations and interpretations

Status: stage 2, written before the stage-2 hash and before any counted row is read. It lists every
point METHOD.md leaves open and how the analysis code settles it. None changes a threshold, a window
or a reading. Changes made after the stage-2 hash are appended below under their own timestamps, with
a reason.
Last reconciled: see the stage-2 manifest's stamp.
Known gaps: the destination audit's explorer lookups (8) are a manual check; the coverage figures in
`tests/` come from synthetic replays, not from the counted sample.

## Interpretations (stage 2)

1. **Poisson intervals.** M3's Poisson part is the exact two-sided 95% (Garwood) interval, so at zero
   calls its upper end is 3.69 ÷ exposure; METHOD's "(3 ÷ exposure at zero)" is the one-sided figure.
   The census detection limit stays 3 ÷ E, as METHOD §6.6 states it.
2. **The interval read.** [L, U]: L is the lower end of the hull computed with unknown routes as not
   Omni; U is the upper end of the hull computed with unknown routes as Omni.
3. **"Too sparse (x of n)".** x counts distinct (transaction, token) pairs, so a transfer held by two
   windows counts once; n counts windows with at least one transfer in the denominator. A stratum
   read whole counts its pieces as windows.
4. **Migration windows** are tier 2 and come after the collector's resolution phase, so their
   transfers are read from the observed legs. Their edge-risk, mixed and net-zero counts are
   published with M10.
5. **M5's callers** are predecessor accounts. `fast-auth.near` is split into its transaction signers
   by the month's neardata signer shares where a sample exists (the last 12 months), and kept whole
   before that.
6. **M3 counts every `sign` receipt**, whatever its outcome; the failed share is published beside it.
7. **M9.**
   - The measured value per 30 days is the HT total over the 84 measured days (the claim window and
     the rest of the 90 days without Sep 29 to Oct 4) × 30 ÷ 84.
   - The scenarios use p's read interval: S_U = U · c + (1 − c) and S_L = L · c, with c the point value
     against 2V, capped at 1.
   - Measured non-Omni value: POA only (unknown as Omni) for the low end, POA plus unknown for the
     high end, each with its bootstrap interval; the published range is [low end's lower limit,
     high end's upper limit].
8. **Destination audit (§6.7).** The selection is fixed here: from the signature-index pages, 10
   BITCOIN rows whose requesting account ends in `.bridge.near` and 10 ZCASH rows, drawn with the
   seed stream "dest-audit". The lookups on a public explorer are done by hand afterwards and
   recorded with their URLs; they compute nothing else.
9. **M4's intervals.** Class shares use the stratified bootstrap, with NearBlocks windows and neardata
   blocks resampled together. For the FastAuth-attributed classes (2a, 2b, 2c) and for the main
   classification, with and without Sweat (2a), the bootstrap interval is hulled with the signer-share bound of M4 carried
   through: (classes 4 + 4x) ÷ all + (FastAuth ÷ all) × [s_L, s_U], with [s_L, s_U] the block-level
   Clopper–Pearson bound (Kish over the blocks' FastAuth counts). §4.0's window-level bound is
   defined for route shares and is not applied to class shares. A neardata draw with no FastAuth call
   is dropped and counted, by §4.0's 5% rule. If the NearBlocks draw has no FastAuth call, the
   attributed count is 0 whatever the neardata draw.
   The frozen registry (`registry/callers.json`) names no 2b signer, so class 2b is empty and "main
   without Sweat" is classes 4 and 4x, hulled with 2b's signer bound (whose lower end is then 0).
10. **Possible refund pairs (§3).** Within one flow window, a withdrawal followed by a deposit of the
    same token, amount and route is counted as a possible refund pair; the share of transfers in such
    pairs is published.
11. **M1's dominant route.** "Above 50%" and "below 50%" are strict. A chain whose count share or any
    unit-group share is too sparse, unstable or without a value is *unknown*. A chain whose strata are
    not completed is "not completed", counted with *unknown* in the favourable count.
12. **Transaction resolution (§3).**
    - For every resolution candidate that was read, the resolved reading replaces the observed one.
      If its resolved first leg falls outside [s, e) it leaves the window; if its resolved net is zero
      it drops; if the resolved transaction has no Intents leg for the token it drops and is counted.
    - Audit-only transactions keep the window's view and are compared with the resolved reading on
      first-leg time, signed net amount and route. Any difference flags every flow reading.
    - A flow window counts as completed only once `nb/RESOLVED` exists and none of its candidates
      failed to be read.
13. **Migration readings.** A share or difference that is unstable reads "no clear move (unstable)".
14. **Trend.** Unstable, or no usable draws, reads inconclusive. Removing class 2a uses each month's
    neardata signer shares (May to October 2026 all have a sample).
15. **Census tokens to chains** (`inputs/reference.json`, built by `inputs/make_reference.py`).
    `<prefix>.omft.near`, `<prefix>-<address>.omft.near` and the same under `.omdep.near` map by a
    fixed prefix table; `nbtc.bridge.near` is Bitcoin and `nzec.bridge.near` Zcash;
    `*.factory.bridge.near` (ERC-20s minted on NEAR by the Ethereum bridge's factory) is Ethereum.
    Anything else is listed as unmapped, not guessed.
16. **Bootstrap seeds and quantiles.** Window draws use `design.seed_for('boot', stratum)`, neardata
    block draws `design.seed_for('boot-nd', month)`. Percentiles are linear-interpolation (type 7).
17. **Page integrity.** A window marked completed whose pages are not a gapless chain, or not done, or
    not all HTTP 200, is treated as not completed.
18. **M6 purpose** is a share of the month's sampled `sign` calls, resampled by block, applied to the
    month's M3 rate (draw by draw). The rate cross-check (METHOD §2 and §6, neardata sample) scales calls per sampled height by
    the month's heights per day, with a Garwood interval on the count.
19. **M8.** NEAR per request is the month's ledger amount ÷ M3's HT total of `sign` calls that month,
    draw by draw: executed, executed plus pending, and (for a provisional month) proposed, each shown
    apart, and in USD at each reference price the thread states for that month. METHOD names June as
    carrying two prices; August does too (the thread's post 16 states a 180-day average of $1.7031 and
    post 23 one of $2.04, checked in the saved thread), so both months show both. The ledger's sums
    are also in results (`M8/totals`), so the write-up types no ledger figure by hand. The operator
    check uses a month-end read only if it returned a non-empty participant list (a failed read, or a
    state other than Running or Resharing, gives that month no participant set).
20. **M10b.** A month-start point where either token's view is neither a value nor an absent account
    is left blank (`rpc.py` retries those, so none is expected).

21. **The change-our-mind tests** (THESIS) were written in the thesis sketch on 2026-11-10 at 05:54Z,
    before the counted sample, and are computed by `measures.mind` from the frozen readings: Omni's
    90-day value share L ≥ 90% with the measured non-Omni value's upper end under 10% of 2V; Omni
    dominant on at least 5 of the 8 measurable chains; in each of August, September and October 2026
    the main classification without Sweat (4, 4x, 2b) at least 25% with its lower end at least 15%;
    NEAR per request falling month on month over July to September 2026 with each interval wholly
    below the one before, while the trend grows; and no "moving to Omni" for SOL, ZEC or BTC.
    - Each test reads met, not met, or undecided. A reading that is not completed, not measurable or
      unstable cannot meet or fail a test, so it leaves the test undecided unless the decided readings
      settle it (a single stable month below 25% fails "broad adoption" whatever the other months; one
      series "moving to Omni" fails "no migration"; five chains at *yes* meet "dominant widely").
    - An M1 chain at *unknown* because its interval straddles 50% is decided as not *yes*; one at
      *unknown* because a share is too sparse or unstable, or one not completed, is undecided.
    - Spend per request uses executed plus pending, as chart 2 shows it; the executed-only reading is
      published beside it. A trend that is inconclusive because its interval straddles 1 counts as
      not growing; one that is inconclusive because it is unstable leaves the test undecided.

22. **M7's matched share** is matched ÷ evaluated: the requests in the middle 1,800 blocks, with the
    ambiguous and censored ones kept in the denominator and reported as counts beside it. Matched ÷
    (evaluated − ambiguous) is shown too. Only a `respond` that succeeded is ever paired, as METHOD
    says, so a failed `respond` followed by a succeeded one pairs with the success; failed responds
    are counted apart. A request of the older argument form (a byte-array payload with
    `key_version`) is keyed on domain 0, since that form is always secp256k1.
23. **M9's second scenario, by chain.** M, "the chains with a measured share", leaves out a chain whose
    share is too sparse (METHOD §4.0: never 0% or 100%) or not completed; each chain's row says whether
    it is in M. An unstable share stays in M and is flagged.
24. **The trend without class 2a** needs every month's neardata signer shares; without them those two
    readings are "not completed" (the raw reading is unaffected).
25. **Recompute output.** `results.json` holds no clock time and no machine path, so the same inputs
    give the same bytes and its sha256 can be published and re-checked. It records the sha256 of each
    frozen input and one digest over every collector file the analysis reads (`inputs/data`).

## Stale text in stage-1 files (not edited, because they are frozen)

- `verify.py`'s docstring still says the re-pull paces at "10.5 s between calls, 6 a minute". Its
  code uses `nb.Ledger`'s defaults, which are 5 calls in any 60 s and 12.5 s apart (the Nov 10 change,
  METHOD §6.10).

- Three stage-1 tests read files from the local data folder rather than the repo:
  `tests/test_collector.py` lines 307 and 408 read the Nov 9 draft pilot rates
  (`b-collect/pilot/rates-plan-draft.json`), and `tests/test_ots.py` reads the OpenTimestamps
  reference example. Neither is a counted row. On a fresh clone the first two fail and the third
  skips. The pilot file is copied to `tests/fixtures/stage1-local/rates-plan-draft.json` (same
  sha256), so a reader can put it where those tests look.

## Coverage of the intervals on synthetic replays (not the counted sample)

`tests/coverage.py` ran the frozen design 40 times on synthetic populations (seeds 100–139) at the
frozen planning rates; results are in `tests/fixtures/coverage/`. Nominal coverage is 95%.
- M3's monthly rates: 1,083 of 1,120 month intervals held the true rate (96.7%).
- The trend: 38 of 40 (95%).
- C2b count shares in the claim window: SOL 40 of 40; the Solana stablecoins 40 of 40 (the
  window-level bound widens these).
- BTC: 30 of 40. METHOD §7 gives BTC's interval only the bootstrap of `nbtc.bridge.near`'s total
  (six windows), and a percentile bootstrap over six windows covers less than 95%; for six Poisson
  windows of the planned size it covers about 87%. Every miss was within 0.005 percentage points of
  the true share (largest 4.7 × 10⁻⁵), and every lower limit was above 99.95%, so at the 90% threshold
  the verdict was the same in all 40. The published BTC interval is read with this in mind.
- Synthetic transfers arrive as a Poisson process, so these figures check the estimators and the
  code, not how clustered the real flow is.

## Changes after the stage-2 hash

None yet.
