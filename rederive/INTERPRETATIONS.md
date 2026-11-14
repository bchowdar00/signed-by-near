# Choices each part made

Each part's brief told its session to say, in a section "Interpretations I made", where the data contradicted the method, a file was missing or malformed, or `METHOD.md` and `DEVIATIONS.md` did not settle a choice, with the choice and its alternative (`briefs/COMMON.md`). Below is that section of each session's report, copied word for word. The rest of each report is not shipped; the code and its outputs are.

## `families/c2b-m10/`

1. **NEAR-side kept in the transfer list, excluded only from shares.** METHOD §3 says NEAR-side is "excluded from every share", not from the included/audited transaction set. Keeping them makes my included-tx count = 2522 and reproduces the audit pool exactly (one audit tx is a NEAR-side ZEC transfer). Shares still exclude route==near-side.
2. **Mixed route counted as unknown** (both-ways). No mixed transfers occur in my tokens, so it is inert.
3. **Window-bound degeneracy:** a stratum is degenerate (c_L=c_U=s_h) if read whole (exact) OR a single-route token (nbtc/nzec, Omni-or-unknown). Only sampled *.omft strata get the Clopper–Pearson m_h bound. This makes BTC's interval bootstrap-only, as METHOD §7 states.
3b. **Bootstrap for read-whole strata** keeps their windows fixed every draw (no variance), per METHOD §4.0.
4. **Difference interval** = hull of the cross-period bootstrap (unknown-as-notOmni central draw) and [L_late−U_early, U_late−L_early] from the read intervals (which already embed both unknown readings). No unknowns exist, so the choice is inert.
5. **Decimals** taken from tokens.json / row metadata (BTC 8, SOL 9, USD 6) — identical in both.

## `families/m9-m1/`

1. **NEAR-side excluded everywhere.** METHOD §3 excludes NEAR-side transfers from "every share";
   I also exclude them from the M9 measured-value total and coverage c, reading them as not
   cross-chain. 28 near-side transfers, ~$72M HT over 84 days (~0.8% of measured). Reported
   separately in telemetry. (An early draft wrongly kept them in denominators, which depressed
   Bitcoin's Omni share from ~1.0 to 0.91; fixed.)
2. **p_CS window-level bound.** §4.0's bound is defined for a route (Omni) share; p_CS's indicator is
   the composite (Omni ∧ withdrawal). I applied the same per-stratum structure (CP for *.omft strata;
   exact c=s_h for nbtc/nzec single-route and for the btc.omft whole stratum). Treating a single-route
   stratum as exact for the *composite* is a choice, since direction still varies there; the dominant
   contribution is from the *.omft strata regardless. The point and bootstrap are unaffected.
3. **Hull across both bootstrap seeds.** The reported [L,U] hulls seed-1 and seed-2 bootstrap with the
   window bound (min of lower ends, max of upper ends). Both seeds reported for Monte-Carlo spread.
4. **Measured-token / dominant denominators** exclude near-side (consistent with 1). "distinct" for
   the sparse rule counts distinct (tx, token) pairs; "n windows with any" counts windows with ≥1
   qualifying transfer.

## `families/m3-m8-m7/`

- **M3 days** = sum of distinct strata lengths `D_s`/86400. `D_s` is the stratum length stored on
  every window, not a per-window value; 2026-08 has two strata (early-part 11.4583 d + last90
  19.5417 d = 31), 2026-11 runs to T0 = 9.4583 d. Alternative (calendar days) differs only for 2026-11.
- **Flag interval** read as `[Sep 29 00:00Z, Oct 5 00:00Z)` (through end of Oct 4 inclusive). If
  "to Oct 4" is end-exclusive (Oct 4 00:00), October loses 3 days not 4; cheap to switch if wanted.
- **Hull** combines the union of both bootstrap seeds with the Garwood interval; each end's source
  is in `m3_results.json` (`hull_lo_src`, `hull_hi_src`).
- **Deposits** counted over the deduped in-window rows (the M3-counted population), not raw page rows.

## `families/m4-m5-trend/`

1. **"Mean daily rate" in the trend** = total calls over the 3-month block ÷ total days (92). The
   alternative (average of three monthly rates) gives 0.8866 / 2.3719 / 1.7373 — immaterial. Both in
   `results.json → trend` and `trend_alt_def`.
2. **Trend uses full-month HT** including the flagged days Sep 29–Oct 4 (sign strata cover whole
   months; METHOD §7 does not ask the trend to exclude them — that "without" variant is M3's, not
   requested here). Noted, not computed both ways.
3. **Months with an nd sample but zero FastAuth calls** (2025-11…2026-03) are treated as *attributed*
   (main well-defined), not "no sample" — FastAuth HT is 0 in their sign windows, so attribution is
   immaterial. "No sample" handling (range) applies only before 2025-11, where FastAuth HT is also 0.
4. **Hull components**: lower end of main's hull is the Clopper–Pearson window bound in all recent
   months; upper end is the bootstrap. Stated per-end in `results.json → M4[...].hull`.
5. **M6 "other Ed25519 (domain 1)"** = domain-1 calls whose path does not start `jwt#` (paths seen:
   empty, `0x…` Relay, `near-…`). Told apart from FastAuth by the path only, per METHOD §6 M6.
