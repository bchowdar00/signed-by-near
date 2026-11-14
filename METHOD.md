# Method (option b, Chain Signatures)

Status: FROZEN, stage 1, v7. The design was selected by the clock at 2026-11-10T11:00:42Z (T0 2026-11-10T11:00Z). This file, copied to the entry's repo as `METHOD.md`, is hashed with the frozen design and code in `frozen/MANIFEST-stage1.txt`, which is stamped with OpenTimestamps before any counted call. It is revised after the fresh outside read (`review/07-codex.md`), its one delta re-read (`review/08-codex.md`) and the parent session's audit of v6, with every finding dispositioned in `review/README.md`. v7 makes C2b's Solana half estimates only, because the design could contradict it but not confirm it at τ = 90%, and reads `btc.omft.near` whole, so that BTC's verdict can go either way (§4.0, §6.5, §7). Four edits were made after v7 was accepted and before the freeze, none changing which windows are drawn: §7 C2b gained one sentence; M9's V is pinned to one NearStats figure, with its leg scale corrected; M1 states Intents' current chain count; NearBlocks calls are paced at 5 a minute, 12.5 s apart, after the Nov 10 pilot's 429s (§6.10; `review/README.md`).
Last reconciled: 2026-11-10T11:51:19Z (Claude).
Known gaps:
- The caller registry (`registry/callers.json`, §5) gives a source for every attributed account. Accounts with only a name lead stay class 5 and are listed as leads.
- NearBlocks' free-plan limits are *reported*, not seen (its pricing page returns 403 to us). The sampler stays under them by ledger (§6.10). On Nov 9, bursts of six calls inside a second drew HTTP 429. On Nov 10, with calls 10.5 s apart, the 6th call inside any 60 s drew 429 in 7 of 7 cases, and calls 1–5 passed in 40 of 40. So the sampler allows 5 calls in any 60 s, 12.5 s apart. NearBlocks sent no rate-limit or Retry-After headers on any of those 47 responses.
- NearBlocks' count endpoints return 403 "This endpoint is currently unavailable" (Nov 9), so totals are estimated from windows, never counted outright.
- HOT's flow (NEP-245 tokens on `v2_1.omni.hot.tg`) cannot be read through NearBlocks' FT endpoints. It enters only M9's scenarios.
- Omni's withdrawals to Solana and the EVM chains are not traced to the destination chain (§6.7).
- M9's reference prices and NearStats' volumes are a third party's (*reported*), fixed at 2026-11-09T09:21Z.
- The budget (§6.10) uses the Nov 9 pilot rates, and the migration windows' lengths the Nov 10 pilot's (10:02–10:13Z). They are planning estimates. The frozen `instants.json` holds the windows.
- C1 and C2a get no verdicts: this design cannot identify C1, and M9's coverage term is not measured on the same population. C2b's Solana half gets estimates, not a verdict: at this budget its share cannot reach "consistent" at τ = 90% (§7).

## 1. Question and the claims it tests

**Question.** Where does NEAR's cross-chain moat actually sit, and is it widening? The moat said to sit there is Chain Signatures, the MPC signer `v1.signer`. Is it broad, carrying Intents across its chains and used by other apps? Or is it a narrower route: NEAR's own Omni bridge on a few chains, beside a custodial bridge and HOT's separate MPC, which carry the rest?

**Published claims under test.** Each claim's wording is *confirmed* at its source; whether it is true is what this method tests.
- **C1, the partner SVRN (March 2026):**
  - "A solver network competes to fulfill these intents across 28 blockchains via NEAR's chain signature architecture" (local copy `svrn-report.txt:59`);
  - "sealed intent routing through Chain Signatures across 28 chains" (`:45`);
  - its glossary defines Chain Signatures as the "cross-chain signing protocol enabling intent fulfillment across 28 chains" (`:659`);
  - its risk table rates "Competition" MEDIUM, mitigated by a "28-chain moat" (`:505`).
- **C2a, Near One's CTO (Oct 23, 2026):** Chain Signatures "powers all the network's cross-chain volume".
- **C2b, the same post:** "Virtually all BTC and Solana cross-chain flow now moves through the NEAR MPC-powered Omnibridge". BTC gets a verdict; Solana gets estimates with intervals, because this design can reach only one side of its verdict (§7).
- **C3, inferred from both (not quoted):** apps beyond NEAR's own infrastructure use Chain Signatures. No source states a threshold for adoption, so C3 gets estimates and no verdict.
- **Verdicts** are given for C2b, the trend and migration. C1 and C2a get estimates and no verdict (§7).

**Why it matters for NEAR.**
- A `sign` call carries a 1-yoctoNEAR deposit, which is a spam guard. So Chain Signatures earns no fee (RESEARCH H).
- NEAR pays the signer's operators from emissions under HSP-007, status Final (*confirmed*):
  - a floor of 4,600 NEAR per eligible node a month;
  - USD-capped at a $3.00 reference price;
  - at most 21 node slots;
  - gated by an SLA.
- The HSP-007 execution thread's ledger records payouts per service month. The ledger text is *confirmed* (saved JSON); that the payments were made is *reported*, because they are not traced on chain here:
  - rows marked executed for March to September 2026 sum to 338,436.08 NEAR (March 36,800, 8 nodes; September 73,293.34, 17 mainnet nodes);
  - 8,436.40 NEAR more is marked pending (April 2,300; August 6,136.40);
  - October's 76,864.52 NEAR is a proposed performance report, whose challenge window runs to Nov 12.
- So the signer's value to NEAR is indirect. It is the moat said to protect Intents from competition (C1), and a cost line paid in new NEAR.

**Disclosure.**
- HSP-007's authors are Sal Ternullo, "CEO of SVRN", and Kendall Cole, founder of Proximity Labs. The proposal states that "SVRN has a clear and expressed intention to become an MPC node provider" (*confirmed*, local copy `hsp-007.md:7,224`).
- SVRN's node `svrn-01.near` "was successfully onboarded to mainnet on June 22, 2026" (execution thread, June performance report, *confirmed*). SVRN's own Oct 15, 2026 release says it went live "in July" (*confirmed*). Both dates are stated.
- The report that makes C1 (March 2026) predates the node. The write-up states these facts and infers nothing about motive.

**What it does not claim.**
- It does not judge Chain Signatures' security or cryptography.
- It does not value NEAR, and it does not model how Intents' fees reach the token.
- Usage counts and flows are not revenue, and a few important integrations can matter more than many calls. §7 reports amounts beside counts for that reason.

**Sources, against the track's example.** The track's example prompt names the NEAR BigQuery dataset and the Intents Explorer API. Both need a sign-up: a Google Cloud billing account, and a JWT from the partner dashboard. The owner's rules allow no sign-ups without his yes. This entry therefore uses keyless sources anyone can re-query: NearBlocks, neardata and archival RPC. THESIS.md states the substitution, and names the metrics this design cannot compute (§9).

## 2. Data sources and access

| Source | Use | Access and terms |
|---|---|---|
| NearBlocks API v3 `GET /v3/accounts/v1.signer/receipts?method=sign&limit=25` | `sign` receipts: predecessor, deposit, status, timestamp, receipt id | Keyless GETs work (*confirmed*, Nov 9). "Each increment of 25 will count towards rate limit" (OpenAPI, *confirmed*), so a page of 25 costs one credit. The free plan is *reported* as 6 calls a minute, 333 a day and 10,000 a month (W15 from a search index; the pricing page returns 403 to us), and keyless limits are unpublished. Attribution is "required" for non-personal use (*confirmed*) |
| NearBlocks `GET /v3/fts/<token>/txns?limit=25` | FT events (`MINT`, `BURN`, `TRANSFER`) with affected and involved accounts, amount, receipt id, event index and transaction hash (M1, M2, M9, M10) | As above |
| NearBlocks `GET /v3/accounts/omni.bridge.near/ft-txns?involved=intents.near&limit=25` | Omni's own FT legs with Intents, all tokens, for the census of chains Omni serves at Intents (M1) | As above |
| NearBlocks `GET /v3/multichain/signatures?limit=25` | Completed signatures with a destination-chain transaction (M6, descriptive) | As above. On Nov 9 its 25 latest SOLANA rows spanned 4.8 days and none came from Omni, while Omni moved 46 SOL withdrawals in 29 minutes (`bridge-flow-probe-…json`, `omni-flow-derived-…json`). It appears to miss Omni's payload-signed withdrawals (its code is not checked), so it is never used for routes |
| NearBlocks `GET /v3/fts/<token>/stats/transfers?limit=25` | Daily transfer counts, used only to size flow windows before the freeze (uncounted pilot) | As above |
| Archival RPC `archival-rpc.mainnet.fastnear.com` | `v1.signer` `state` at month boundaries (M8); `ft_total_supply` of `nbtc.bridge.near` and `btc.omft.near` at month boundaries (M10b, M2 context) | Keyless. No restrictive terms found; provider conditions unverified |
| neardata `mainnet.neardata.xyz` (FastNEAR) | Whole blocks: `sign` arguments (payload, path, `domain_id`), the transaction signer behind FastAuth calls, `sign` → `respond` pairing, a rate cross-check, month-boundary heights | Keyless. "180 requests per minute per IP" stated (*confirmed*); paced at about 100 a minute with 429 backoff. No restrictive terms found; provider conditions unverified |
| HSP-007 execution thread, `gov.near.org/t/42147` | Payouts per service month (M8) | Public forum JSON, saved Nov 9 (`gov-hsp007-execution-42147.json`) |
| Docs: Intents bridging overview and treasury page; NEAR's Omni overview and implementation pages; the Omni bridge README (Near-One/omni-bridge); HOT Protocol paper (arXiv 2512.02287) | Route capability (M1) and route families (§3) | Public; local copies or quoted with links |
| NearStats, 30-day cross-chain volume by chain | One of two weightings in M9 | CC BY 4.0, a third party, *reported* |
| Cross-checks only, never inputs | Dune `proximity_team/v1signer` (to 2026-09-21); soldanoandrea's monthly census of `v1.signer` transactions; NearBlocks' daily FT stats | *Reported* |

## 3. Definitions

- **T0**, the data cutoff, is the freeze time rounded down to the hour. Every window lies before T0.
- **Stratum.** A set of real-time pieces (for example, the 90 days to T0 minus the flagged days), laid end to end on a line of length D.
- **Window placement.** A window of nominal length ℓ starts at u, drawn uniformly on [−ℓ, D) from the seed. It covers [max(u, 0), min(u + ℓ, D)), mapped back to real time as one or more segments. Every instant of the stratum is covered by a given window with probability ℓ ÷ (D + ℓ), so each window's Horvitz–Thompson weight is w = (D + ℓ) ÷ (n ℓ), with n windows in the stratum, and Σ w·y over the windows is unbiased for the stratum's total of y. Windows that find nothing are kept.
- **Row identity.** An FT row is identified by (receipt id, event index, affected account, cause), and a `sign` row by its receipt id. Duplicates are dropped *within a window* (a row repeated across that window's pages). An event covered by two sampled windows counts in both windows' totals: the weight w is per window occurrence, and dropping it from one of them would bias the total. Windows are the units the bootstrap resamples. Counts of distinct transfers (the sparse rule, §4.0) count each transfer once.
- **Intents' legs.** NearBlocks lists a `TRANSFER` once, under the receiving account with a positive delta, and a `MINT` or `BURN` under the account whose balance changed (checked on the Nov 9 rows; `tests/fixtures`). So `intents.near`'s legs in a transaction are:
  - rows whose affected account is `intents.near`;
  - `TRANSFER` rows whose involved account is `intents.near` and whose affected account is another, where Intents' change is minus that row's delta.
- **Economic transfer.** One (transaction hash, token) in which Intents' balance changes. Its amount is the absolute net change, and its direction is in (a deposit) or out (a withdrawal).
  - It belongs to a window if its earliest Intents leg lies in [s, e). Each segment is fetched from s − 30 s to e + 30 s, so transactions that start inside the window can be completed.
  - A transaction whose net change is zero (a refund inside it) drops out.
  - A refund in a later transaction counts as a separate deposit. That is a known limit, and the share of such pairs found is reported.
  - A transaction whose last leg falls within 5 s of the fetched range's end is flagged "edge risk" and counted.
  - **Completeness.** A leg outside the fetched range can be missed only if a transaction's Intents legs span at least 30 s. In the Nov 9 rows (414 transaction-token groups, 61 with more than one leg) the longest span was 1.02 s. Two checks guard the rest, both with `GET /v3/txns/{hash}/fts`, which returns every FT event of a transaction:
    - every included transaction flagged edge risk, or whose observed legs span more than 5 s, is read whole, and its whole set of Intents legs replaces the observed one (that endpoint lists both sides of a transfer, so Intents' legs are its rows whose affected account is `intents.near`);
    - a seeded audit (seed stream "audit") of 20 included transactions is read whole and compared with the window's view on first leg, net amount and route. The count that differ is published, and if any differs, every flow reading carries that flag.
    - Both run after the last tier-1 window and before tier 2 (§6.10). A candidate that cannot be read makes its window "not completed" (§7).
- **Route of a transfer,** from the counterparties of Intents' legs in it. A transaction with both an Omni leg and a POA leg is **unknown (mixed)**, because no split between them can be justified. Otherwise:
  - **Omni** if any counterparty is `omni.bridge.near`, `omni-relayer.bridge.near` or a `*connector.bridge.near`;
  - else **POA** if the token is `*.omft.near` and a leg is a `MINT` or `BURN` at `intents.near`, or a `TRANSFER` from or to `omft.near` (a POA deposit mints to `omft.near`, which then transfers to `intents.near`);
  - else **NEAR-side** if every leg is a `TRANSFER` with an ordinary NEAR account. An account is not ordinary if it is `omft.near`, the token itself, `aurora` or `*.aurora`, or ends in `.bridge.near`, `.omft.near` or `.omdep.near`. NEAR-side transfers are not cross-chain and are excluded from every share;
  - else **unknown**, kept and reported. Every reading counts unknowns both ways (§7).
- **Route families:**
  - **Omni.** Omni's README states: "All outbound transfers use Chain Signatures (MPC)". Inbound transfers are verified by light clients (Ethereum, Bitcoin, Zcash) or by Wormhole (Solana, BNB and the EVM L2s) (*confirmed*, saved copy `omni-bridge-README-20261109.md`). So on Omni, withdrawals from NEAR are signed by Chain Signatures, and deposits are not. Bitcoin and Zcash withdrawals are transactions that `v1.signer` signs. For the other chains, Omni signs a payload that its contracts there verify (NEAR's Omni implementation docs, *confirmed*).
  - **POA** is the Intents team's "Proof of Authority" bridge, which is custodial (Intents bridging docs, *confirmed*).
  - **HOT** runs HOT Protocol's own MPC network: "The Multi-Party Computation (MPC) Network manages signing keys" (arXiv 2512.02287, *confirmed* at the abstract). It is not `v1.signer`, despite the contract name `v2_1.omni.hot.tg`.

## 4. Measures

The estimators and intervals used by several measures are defined once, in §4.0.

- **4.0 Estimators and intervals.**
  - **Totals.** A stratum's total is Σ_i w_i y_i over its windows (§3). A period's total is the sum over its strata.
  - **Shares.** For a group of transfers, the share on Omni is Σ_j w_j a_j o_j ÷ Σ_j w_j a_j. Here w_j is the weight of the transfer's window, a_j its amount (or 1 for count shares) and o_j its Omni indicator. Amounts are pooled only within one unit (§4, M2).
  - **Interval.** The 95% interval is the hull of two intervals:
    1. a stratified percentile bootstrap: 2,000 draws, windows resampled with replacement within each stratum. Draws whose denominator is zero are dropped and counted. If more than 5% are dropped, the share is "unstable" and read as inconclusive;
    2. a **window-level bound**. Transfers inside one window are not independent: a route pause or a routing change moves whole stretches of time. So in each stratum h where both routes can occur (a `*.omft.near` token; `nbtc.bridge.near` and `nzec.bridge.near` can only be Omni or unknown), the stratum's Omni share s_h gets a Clopper–Pearson interval [c_L,h, c_U,h] that treats each window as one trial: m_h = (Σ_i A_i)² ÷ Σ_i A_i² trials, with A_i the window's denominator (amount, or count for count shares), and s_h·m_h successes (the beta-quantile form allows a fraction). In a stratum where only one route can occur, c_L,h = c_U,h = s_h. So too in a stratum **read whole** (§6.5): its windows are its pieces, each of weight 1, so its total is exact; the bootstrap keeps them in every draw, adding no variance. The group's bound is C_L = Σ_h T_h c_L,h ÷ Σ_h T_h, and C_U likewise, with T_h the stratum's estimated denominator total.

    Each window's share lies in [0, 1], so with windows of equal weight the share's variance is at most p(1 − p) ÷ m, the binomial's; the bound is conservative then and approximate with unequal weights. It is not called exact. It applies within strata only, because which token a window samples is fixed by the design, not drawn. Example: three windows of 100 all-Omni transfers each give a lower bound of 29.2% (0.025^(1/3)), not the 98.8% that counting 300 transfers would give. With all of a stratum's windows on one route, the best lower bound is 0.025^(1/m): 54.1% at 6 windows, 81.5% at 18, 90.3% at 36.
  - **Unknown routes.** Every share is computed twice: with unknowns counted as not Omni (giving the lower bound L) and as Omni (giving the upper bound U). The interval read is [L, U].
  - **Sparse data.** A share whose windows hold no transfers in the denominator is "none observed (0 of 0)". One with fewer than 10 distinct transfers, or fewer than 3 windows with any, is "too sparse (x of n)". Both are "not measurable" in §7, never 0% or 100%.
- **M1. Route map of Intents' 28 chains** (describes C1). Each chain gets a status at three levels, for its measured tokens only:
  - **Capability (documents).** Omni is documented as supporting the chain.
    - NEAR's Omni overview (Nov 9, no date on the page, *confirmed*) lists 13 chains: Ethereum, Bitcoin, Zcash, Solana, Base, BNB, Arbitrum, Polygon, HyperEVM, Fogo, Abstract, Starknet and Aptos. 10 of those are among Intents' 28.
    - The Intents bridging page lists 6, and its treasury page adds Zcash.
    - This is a documentary count, not a ceiling: another Chain Signatures integration could serve a chain without being listed.
  - **Observed use:** *yes* if at least one Omni-route economic transfer of one of the chain's tokens appears in the flow windows (§6.5) or the Omni census (§6.6). Census tokens are mapped to chains by their contract ids, and unmapped ones are listed. Sampling cannot show absence, so a chain not seen is *unknown*, published with its detection limit.
  - **Dominant route:**
    - *yes* if the lower bound of Omni's share is above 50% by count, pooled across the chain's measured tokens, and the lower bound is above 50% by amount in every unit group the chain has;
    - *no* if the upper bounds are below 50% on both;
    - *unknown* otherwise.

    Chains with no measured token are *unknown*, including HOT's chains.
  - The 28 are the union of the Intents bridging page's three lists: 6 Omni, 17 POA and 11 HOT (*confirmed*, `integration__bridging__overview.md:35,47,57`). That page is a snapshot, not a limit on what Omni can do.
  - Intents now spans more chains than the 28. On Nov 9 NearStats listed 39 supported chains and 216 usable assets, and recorded NEAR's own positioning as "35+ chains" (`nearstats-api-near-summary.json`, *reported*). M1 maps the 28 that C1 names. The other chains lie outside M1, and THESIS.md says so.
- **M2. BTC and Solana by route** (tests C2b).
  - **Units.** Amounts stay in each token's own unit, and units are never summed across, so no price feed is needed:
    - BTC in BTC: `nbtc.bridge.near` (Omni) and `btc.omft.near` (POA, read whole, §6.5), both 8 decimals;
    - SOL in SOL (`sol.omft.near`);
    - Solana USDC and USDT in USD as issued, pooled into one group.
  - Omni's share per group by §4.0, by amount and by count, for deposits, for withdrawals, and for both pooled (the primary reading).
  - **Two periods:**
    - the **claim window**, 2026-10-09T00:00Z to 2026-11-06T00:00Z, 28 days centred on the post of Oct 23 (one stratum per token);
    - the 90 days to T0 without Sep 29 to Oct 4 (two strata per token: inside and outside the claim window), shown beside it.
  - **Context:** `ft_total_supply` of `nbtc.bridge.near` against `btc.omft.near` at T0. On Nov 9 Omni held 166.65 BTC and POA 87.30 BTC, so Omni had 65.6% (*confirmed*).
- **M3. Monthly `sign` rate,** August 2024 to T0.
  - A month's total is the sum of its strata's totals (§4.0); its rate is that total ÷ its days. The interval is the hull of the stratified bootstrap percentile interval and an exact Poisson (Garwood) interval on the windows' total count over their total covered time, so a month whose windows find no calls still gets an upper bound (3 ÷ exposure at zero).
  - Shown with and without Sep 29 to Oct 4: "without" is the estimate of calls outside those days divided by the days outside them.
- **M4. Caller mix by month.** Each class's share is its estimated total ÷ the estimated total of all calls (§4.0), under three classifications (§5). Stratum shares are never averaged.
  - FastAuth calls are attributed to apps by neardata's signer shares for that month (§5). In months without a neardata sample (before the last 12 months), FastAuth is "unattributed", and the main classification is shown as a range, with all of it counted in and with none.
  - The interval draws NearBlocks windows and neardata blocks together, so the attribution's uncertainty is carried. A draw with no FastAuth call among its blocks is dropped and counted, by the same 5% rule as §4.0. Each month's signer shares also get the window-level bound of §4.0 with blocks as the trials (m = the effective number of sampled blocks holding a FastAuth call), so an all-Sweat sample cannot imply certainty.
- **M5. Concentration and fragility.**
  - The top-1 and top-3 callers' shares per month.
  - The share from apps that have announced an end. Sweat Wallet: "Sweat Wallet and the SWEAT token as they exist today end on 30 December 2026" (*confirmed*, update.swe.at). The token continues, so this measure does not assume that every associated call stops.
- **M6. Purpose and direct-signing destinations.**
  - **Purpose, per month** (neardata sample, as a ratio applied to M3). Each `sign` call is classed by key type and path:
    - **secp256k1 (domain 0):** EVM, Bitcoin or Zcash keys, so cross-chain capable;
    - **Ed25519 on a FastAuth login path** (`jwt#…`): most likely NEAR account control;
    - **other Ed25519 (domain 1):** NEAR or Solana, told apart by path where it can be.
  - In the pilot, 49 of 103 sampled calls were Sweat's FastAuth Ed25519 signatures, and none of Sweat's calls used secp256k1 (RESEARCH H). The purpose split decides how much of "use" is cross-chain at all.
  - A descriptive list of completed signatures sent from MPC-derived keys, by destination chain and requesting account, per month (NearBlocks index). It is not used for routes.
- **M7. Completion.** In a contiguous neardata run of 2,000 blocks ending at T0:
  - a `sign` request pairs with a `respond` receipt that succeeded, comes at or after it, and matches it on payload, tweak and domain. Payloads are compared in one canonical form (lower-case hex of the bytes, whichever encoding the call used). The tweak is SHA3-256 of "near-mpc-recovery v0.1.0 epsilon derivation:" + predecessor + "," + path;
  - identical requests (same payload, tweak and domain) are paired in order, each response used once, and their pairs are labelled "by order";
  - the first 100 blocks are read only as context, the last 100 only for responses, and the requests in the middle 1,800 blocks are the ones evaluated. A request with no response by the end is censored, not failed. A request whose repeated-request group (same payload, tweak and domain) has a member in the first 100 blocks is "ambiguous" and is not counted as a proven completion, because a response there could belong to an earlier identical request;
  - reported: the matched share, the censored count, the by-order count, and the median and longest delay, conditional on matched pairs.
  - **Pilot** (500 blocks, Nov 9): all 24 requests and 24 responses paired one-to-one by tweak. 11 pairs were unique within the run's tweak groups, one request and one response each (FastAuth 10, a Meteor vault 1); that is not payload verification. 13 were paired by order within repeated tweaks (Omni 8, BTC connector 3, `tx-bench.near` 2). Median 2.9 s, longest 4.6 s. The pilot kept a truncated link, so payloads were not compared and those 13 pairs are not proven. The collector stores full arguments.
- **M8. Program expenditure per `sign` request.** This is NEAR's spend on the program per request, not the marginal cost of a signature.
  - **Numerator** per service month, from the execution thread's ledger rows, which govern over its summary totals: rows marked executed, plus rows marked pending for that month, shown apart. A month with only a proposed performance report (October 2026, as of Nov 9) is labelled provisional. Mainnet and testnet are shown apart.
  - **Denominator:** M3's calls that month. The signer serves several key domains, so the denominator is every `sign` request in every domain.
  - **Interval:** from M3's bootstrap draws.
  - Reported in NEAR per request, and in USD at each month's own reference price as the thread states it. Where the thread gives inconsistent prices for a month (June), both are shown.
  - Nothing before March 2026, when the program started. Earlier grant funding (Proximity) is not public and is not estimated.
  - **Reconciled:** paid mainnet nodes against the contract's participant set at the month-end height. For October, the proposed report lists 17 nodes, "16 active at month-end following Blacksand's departure", and the set on Nov 1 held exactly those 16 (archival RPC).
  - **Source totals.** The thread's transparency report gives March to September as 344,372.94 NEAR. The executed rows sum to 338,436.08, or 346,872.48 with pending rows. The write-up flags that the source's total does not reconcile, and uses the rows. September's transaction hashes are abbreviated in the thread.
- **M9. Share of Intents' measured cross-chain value on Omni, and on Chain Signatures** (describes C2a). This is a proxy: the CTO's "all the network's cross-chain volume" may include flow outside Intents.
  - **Measured shares.** Each measured token's transfers are valued in USD at reference prices frozen with this file: NearStats' asset prices at 2026-11-09T09:21Z (BTC $74.5K, ETH $2.1K, SOL $87, ZEC $1.2K, XRP $1, stablecoins $1; *reported*). No price feed is pulled. Over the 90 days to T0, two shares by §4.0:
    - p, Omni's share of all measured value;
    - p_CS, Omni's withdrawals as a share of all measured value. These are the transfers Chain Signatures signs (§3).
  - **Coverage c.** The measured value per 30 days divided by V. V is NearStats' 30-day swap volume from its de-duplicated store of Explorer API rows (*reported*): $831,333,190 over 426,236 swaps, 2026-10-10T09:21Z to 2026-11-09T09:20Z. It is `intents.timeframes.30d.volumeUsd` in the saved `nearstats-api-near-summary.json`, the same population as the per-chain V_ch below.
    - NearStats counts each swap once: its rows are "de-duplicated by a stable transaction id" (methodology page). A cross-chain swap can move value through two economic transfers, a deposit and a withdrawal, and both are measured. So c is shown against V and against 2V. The scenarios use the smaller, the one against 2V, capped at 1.
    - NEAR's headline 30-day total in the same file is $3,714,703,670 (revenue.near.org's series). It is the figure DefiLlama and other entries cite. NearStats' row store holds 22% of it, and this method does not establish why. c against that total is shown for context and is not used in the scenarios.
  - **Measured non-Omni value.** The value of measured transfers on POA and other routes, in USD per 30 days at the fixed prices, with its interval.
  - **Two labelled scenarios, not bounds:**
    - favourable S_U = p_U · c + (1 − c), which counts every unmeasured dollar, HOT's included, as Omni;
    - unfavourable S_L = p_L · c, which counts none of it.

    They are not confidence bounds. c compares 90-day bridge transfers at fixed prices with 30-day swap volume, a different population, and its own uncertainty is not propagated.
  - **Second scenario, by chain.** V_ch is NearStats' 30-day volume per chain (`intents.timeframes.30d.chainFlows`, same file; its ten chains sum to 97.5% of V, and all eight chains with measured tokens are among them). With M the chains with a measured share: p = Σ_M V_ch · p_ch ÷ Σ_M V_ch and c = Σ_M V_ch ÷ V, the same two formulas. p_ch is Omni's USD share of the chain's measured tokens. It assumes each measured chain's Omni share equals that of its measured tokens.
- **M10. Route migration (is the moat widening?).**
  - Omni's share of economic transfers, by amount in native units (the verdict metric) and by count (shown beside it), for four series: `sol.omft.near`, `zec.omft.near`, BTC (`btc.omft.near` with `nbtc.bridge.near`), and `eth.omft.near` as a POA control.
  - **Early period:** 2025-01-01 to 2025-07-01, one stratum per token with 8 windows. **Late period:** the 90 days to T0 (the flow windows, §6.5). Both are fixed now.
  - The difference, late minus early, uses unknowns both ways: the lower bound pairs late-as-not-Omni with early-as-Omni, and the upper bound the reverse. Its interval is the hull of the bootstrap percentile interval (draws independent across periods) and [L_late − U_early, U_late − L_early] from §4.0's intervals.
  - A series with no transfer in either period is "not measurable".
  - **Monthly chart** (descriptive, no verdict): one window per token in each of 2025-07, 2025-09, 2025-11, 2026-01, 2026-03, 2026-05 and 2026-07. Months between are not sampled, and the chart says so.
- **M10b. BTC custody by route** (exact, descriptive). Omni's share of bridged BTC on NEAR is `ft_total_supply` of `nbtc.bridge.near` ÷ (that + `btc.omft.near`'s), at every month start from 2025-01 and at T0 (archival RPC). It is a stock, not a flow, and it covers all of NEAR, not only Intents. A token whose account does not exist yet at a height has no supply there and counts 0: `nbtc.bridge.near` did not exist at height 136,000,000 (2024-12-28; *confirmed*, archival RPC, `UNKNOWN_ACCOUNT`). A view that fails for any other reason is retried, never read as 0.

## 5. Caller classes (registry frozen before the counted sample)

Every predecessor in the sample is classed by these rules, in order. The evidence for each account is kept in `callers.json`, and an account without a source goes to class 5.

1. **NEAR-built infrastructure:** `omni.bridge.near`, `btc-connector.bridge.near`, `zcash-connector.bridge.near` and other `*.bridge.near` contracts documented by NEAR, Near One or the Intents team.
2. **FastAuth, a shared login service** (`fast-auth.near`, now NEAR Auth), attributed to the app behind each call by the receipt's transaction signer:
   - **2a** Sweat Wallet (`sweat-relayer.near`), an independent app that is closing;
   - **2b** other named apps;
   - **2c** unknown.

   NearBlocks' receipt rows do not carry the signer. neardata's block sample does, so each month's FastAuth count is split by that sample's signer shares (§4, M4).
3. **Tests, demos and monitoring:** only accounts with a source that documents them as a test, a benchmark, a demo or example, or a monitor, or whose own published description says so. A name containing "test" is not enough. The registry gives the source, or the observed behaviour where there is no document (for example, `ping-account.near` calls every 5 minutes, 288 a day). Every result that uses class 3 is also shown with class 3 moved into class 5.
4. **Independent apps calling directly:** the contracts or relayers of a named app not built by NEAR Foundation, Near One, the Intents team or Proximity, each with a public source. Examples: `*.meteor-vaults.near`, `acc.ref-labs.near` (Ref, now RHEA), Trezu.
   - **4x** Aurora XCC sub-accounts, `<40-hex>.aurora`. Aurora names one for each EVM address as `format!("{}.aurora", hex::encode(address))` (*confirmed*, doc.aurora.dev). The name identifies an EVM contract on Aurora, not who owns it or whether it is in production. So 4x is kept apart unless the contract's owner is found. Four were traced before the freeze: Aurora's explorer shows them as verified contracts named `RelayAllocator`, `Allocator`, `RelayMultisigSigner` and `BitcoinDepositAddress` (*confirmed*, raw responses saved), and Relay's protocol docs place its Allocator, which "Generates MPC withdrawal payloads", on "Aurora (NEAR)" (*confirmed*). They are class 4 (Relay); the tie of each contract to Relay is *reported*.
   - A sub-account inherits its parent's attribution: "Accounts cannot create sub-accounts of other accounts" (*confirmed*, docs.near.org, account ID). So every `*.bridge.near` account was created by Near One's `bridge.near`, and every `*.meteor-vaults.near` by `meteor-vaults.near`.
5. **Unattributed:** named or implicit accounts with no app found.

**Three classifications for "beyond NEAR's own infrastructure"** (C3). All three are published:
- **narrow:** class 4;
- **main:** 4, 4x, 2a and 2b;
- **broad:** everything except classes 1 and 3.

## 6. Sampling (the counted sample)

The window list is generated by `collector/design.py` from T0, the seed and the pilot rates, and frozen as `instants.json` (§6.10). The figures below are planning estimates for the selected design at T0 2026-11-10T11:00Z, from the Nov 9 pilot rates and, for migration, the Nov 10 pilot's.

- **6.1 Seed.** 20261114. Each stratum draws from its own stream, derived as SHA-256 of the seed and the stratum's name, so the windows do not depend on the order of generation. The pilot's seed, 20261109, is never reused, and pilot data is never counted.
- **6.2 `sign` windows (M3–M5).**
  - **Strata.**
    - Each calendar month from 2024-08 up to T0 − 90 days is a stratum with 6 windows. The month that straddles T0 − 90 days keeps only its earlier part.
    - Within the 90 days to T0, each calendar-month part is a stratum with max(4, round(48 × days ÷ 90)) windows: about 48 in all.
  - **Window length** for month m is ℓ_m = 20 ÷ r_m, clipped to [60 s, 6 h]. r_m is the pilot's median rate for that month, so that a window expects about 20 calls.
  - **Paging.** `receipts?method=sign&limit=25&before_ts=e`, then the API's next-page cursor, until a page holds a receipt older than s, holds fewer than 25 rows, or has no cursor. The cursor encodes timestamp, shard and event index, so rows that share a timestamp are never skipped (31 of the 84 pilot pages had ties). There is no page cap.
  - **Cost.** About 198 windows: about 130 credits for the last 12 months and 99 for the older months (stress about 155 and 116).
- **6.3 Signature index (M6).** One instant per month for the 12 months to T0 (13 calendar months, the partial ones included), one page each: 13 credits, descriptive only.
- **6.4 Token list** (frozen, with exact contract ids):
  - BTC: `nbtc.bridge.near`, `btc.omft.near`;
  - Zcash: `zec.omft.near`, and Omni's `nzec.bridge.near` (found on chain on Nov 9; about 0.6 transfers a day);
  - Solana: `sol.omft.near`, USDC `sol-5ce3bf3a31af18be40ba30f721101b4341690186.omft.near` and USDT `sol-c800a4bd850783ccb82c2b2c7e84175443606352.omft.near` (symbols from NearBlocks' token metadata; both moved through Omni in the Nov 9 probe);
  - Ethereum: `eth.omft.near`, USDC `eth-0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48.omft.near`, USDT `eth-0xdac17f958d2ee523a2206206994597c13d831ec7.omft.near`;
  - Arbitrum: USDC `arb-0xaf88d065e77c8cc2239327c5edb3a432268e5831.omft.near`, USDT0 `arb-0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9.omft.near`;
  - Base USDC `base-0x833589fcd6edb6e08f4c7c32d4f71b54bda02913.omft.near`; Tron USDT `tron-d28a265909efecdcee7c5028585214ea0b96f015.omft.near`; XRP `xrp.omft.near`;
  - BNB chain: HOT tokens, which are not readable and enter only through M9's scenarios.

  That is 15 readable tokens on 8 chains.
- **6.5 Flow windows (M1, M2, M9, and M10's late period).**
  - Per token, two strata: the claim window and the rest of the 90 days to T0 without Sep 29 to Oct 4 (placed across its pieces). 6 windows each, with two exceptions fixed by what each token serves:
    - Solana's three tokens have 18 windows each in the claim window, because C2b's Solana estimates rest on them and the window-level bound narrows only with many windows (§4.0);
    - the 8 tokens that serve no verdict (not C2b, not M10: `nzec.bridge.near`, the Ethereum, Arbitrum and Base stablecoins, Tron USDT, XRP) have 4 outside the claim window;
    - `btc.omft.near` is **read whole** in both strata, one window per piece with weight 1, and not sampled. At about 1.2 rows a day, its 6 windows would each run about 16 days, nearly covering the 28-day claim stratum and overlapping. Simulated with every window on POA, their upper bound stays above 50% in 92–99% of draws (log-sd of amounts 1.0 to 2.0). So BTC could not read "contradicted" even if POA carried it. Read whole, the stratum is exact, and it costs about 7 pages instead of about 17.
  - **Length** per token: ℓ_k = 20 ÷ r_k − 60 s, at least 60 s. r_k is the token's mean daily rows over its 25 most recent active days (NearBlocks daily stats, Nov 9, uncounted), so a window expects about 20 rows with its guards. For `btc.omft.near`, at 1.2 transfers a day, that is about 16 days, and its windows are clipped at the stratum's ends (§3).
  - Each segment is paged fully, with 30 s guards (§3).
  - 192 windows (4 of them `btc.omft.near`'s pieces read whole), about 230 credits (stress about 276).
- **6.6 Omni census (M1, observed use).**
  - 48 windows over the 90 days to T0 without Sep 29 to Oct 4, on `GET /v3/accounts/omni.bridge.near/ft-txns?involved=intents.near`, each paged fully. The length is fixed from the Nov 9 rate (8,905 Omni legs with Intents a day) to expect about 20 rows.
  - The shakedown checks that the `involved` filter restricts rows to Intents. If it does not, the census runs unfiltered and keeps Intents' rows, at a cost recomputed before the freeze.
  - Every token seen moving between Omni and `intents.near` is mapped to its chain.
  - **Detection limit.** With total exposure E, a chain whose Omni legs with Intents arrive at rate λ is missed with probability e^(−λE); a chain not seen is published with the 95% upper bound on its rate, 3 ÷ E. These are Poisson-model limits. They cover only legs visible on this account. Connector-routed deposits, such as `btc-connector.bridge.near` → `intents.near`, are not on it.
  - About 56 credits (stress 68).
- **6.7 Migration windows (M10) and destination audit.**
  - Per M10 token: the early stratum (8 windows) and one window in each chart month (§4). 75 windows.
  - **Length** per token and period from a second uncounted pilot, run just before the freeze (`collector/pilot_m10.py`, pilot seed 20261110): one page of the token's FT rows at a pilot instant drawn uniformly in each period. The rule, fixed before the pilot runs:
    - n rows on the page, counted as FT rows, the unit of §6.5;
    - n = 0: rate 0, and the period's windows take its whole length (each then costs one page);
    - n ≥ 1: rate = n ÷ (t_p − t_oldest), with t_oldest the oldest row's timestamp, which lies strictly before the instant t_p;
    - the window length is 20 ÷ rate − 60 s, at least 60 s, as in §6.5.

    The pilot's pages are kept, and its rates are recorded in the frozen rates file. So a busier past does not inflate the cost.
  - 75 windows, about 86 credits (stress about 105), at the Nov 10 pilot's rates.
  - **Audit.** 10 Omni BTC withdrawals and 10 ZEC withdrawals from M6 rows are checked on a public explorer for existence and amount. Solana and EVM withdrawals are not traced. The audit depends on the signature index, so it is dropped with it.
- **6.8 neardata.**
  - 150 random blocks per month, uniform over the heights of each month in the last 12 months to T0. Month-boundary heights are found by bisection on block timestamps before the freeze and frozen with the heights in `nd_plan.json`. They serve FastAuth attribution (§5), `domain_id` (M6) and a rate cross-check against M3.
  - One contiguous run of 2,000 blocks ending at T0 (M7).
- **6.9 RPC.** `v1.signer` `state` at each month start from 2026-04 and at T0 (M8). `ft_total_supply` of the two BTC tokens at each month start from 2025-01 and at T0 (M10b, M2).
- **6.10 Budget, tiers and pacing (NearBlocks).**
  - **Cost.** Expected about 644 credits (sign 229, index 13, flow 230, census 56, migration 86, transaction resolution 30), and about 762 under the stress model. In the stress model each window's rate is the planning rate times a mean-preserving lognormal factor e^(Z − 1/2), Z ~ N(0, 1). Tier 1 alone: about 445, stress 529. These are planning estimates, not bounds.
  - **Limits.** At most 300 credits in any rolling 24 hours, at most 5 calls in any 60 s, and at least 12.5 s between calls (the Nov 10 pilot's 429s, above). Every NearBlocks call from this machine since 2026-11-09 counts. The ledger is seeded from the Nov 9 probe logs (250 credits, each batch stamped at its end, the margin included). Every later call, pilot and shakedown included, is reserved in the ledger before it is sent.
  - **Tiers.** Tier 1 is the mandatory floor: every flow window, the census, the `sign` windows for the last 12 months, and the transaction resolution (§3; 30 credits planned: the 20-transaction audit and a reserve of 10 for candidates). Tier 2 is the migration windows, the older `sign` windows and the signature index. Tier 1 runs first; within a tier, windows run in an order drawn from the seed.
  - **Design selection, at the freeze and before anything is hashed.** The start is taken as one hour after the freeze. "Fits" means this: a simulation of one-credit calls from the start, under the ledger's limits and its entries at that moment, issues the design's stress cost × 1.10 (retry allowance, rounded up) before the sampling deadline, 2026-11-13T00:00Z. If the whole design does not fit, tier-2 parts are removed in this fixed order: the signature index (and with it the destination audit), then the `sign` windows more than 12 months old, then the migration windows. The choice depends only on the clock and the ledger, never on data. `instants.json` is then generated for the selected design and hashed with this file. Its `selection_log` records each test.
  - **If tier 1 alone does not fit,** nothing is started, and Bhargav decides between a later sampling deadline (which shortens the analysis) and the neardata-only fallback. **Selection at the freeze:** it ran at 2026-11-10T11:00:42Z, against the ledger at that moment, with the 47-credit migration pilot included. The whole design fits, and no part is removed. It needs 839 credits with the allowance (plan 643.79, stress 762.15), and the simulated last call is 2026-11-12T17:25:36.785Z, before the deadline (`instants.json` → `meta.selection_log.fit_tests`).
  - **No cost-dependent drop.** After the freeze, the sampler waits for quota and completes every selected window. A failed page is retried, never skipped.
  - **Backstop.** Execution status is kept apart from the frozen list, in `nb/windows.jsonl`. At the sampling deadline, every window not completed, whether not started or started and unfinished, is marked "not_completed". Every measure with an incomplete stratum is then "not completed" (§7), never estimated from the part done.
  - **Time.** At least 12.5 s a call, so about 3 hours of calls in all, spread over about two days by the daily limit. neardata and RPC run in parallel.

## 7. Readings (written before the counted draw)

**Principle.**
- A claim is called **contradicted** only if it fails at its most generous reading, and **consistent** only if it holds at its literal reading. Anything between is **partly**.
- Every estimate is published with its interval and sensitivity, so a reader can apply another reading.

**States of one share, in order of precedence.** For a share with interval [L, U] (§4.0) and threshold τ:
1. **not completed** if any of its strata has a window marked not_completed;
2. **not measurable** if it is "none observed" or "too sparse";
3. **inconclusive** if it is unstable, or if L < 50% and U ≥ τ;
4. **consistent** if L ≥ τ;
5. **contradicted** if U < 50%;
6. **partly** otherwise.

**Claims.**
- **C1** (M1): **not identified by this design, so no verdict.** Only the 8 chains with listed tokens can get a measured dominant-route status. So "consistent" (28 of 28) is impossible, and at the dominant level the favourable count cannot fall below 20, whatever the data. The entry publishes:
  - the per-chain table at the observed and dominant levels;
  - the unfavourable count (chains marked *yes*) and the favourable count (*yes* plus *unknown*), at each level;
  - the capability count (10 of 28 documented), stated beside them as documentary, not a ceiling.
- **C2a** (M9): **estimates only, no verdict,** because M9's coverage term is not measured on the same population. Published: p and p_CS with their intervals, the measured non-Omni value in USD per 30 days, and the two labelled scenarios beside NearStats' volume.
- **C2b** (M2). The primary reading is Omni's amount share in the claim window, deposits and withdrawals pooled, at τ = 90%. A verdict must be reachable both ways at its primary τ. A share that can reach only one side gets estimates, not a verdict.
  - **BTC** is read by the states above, and both sides are reachable. `nbtc.bridge.near` can only be Omni or unknown, and `btc.omft.near` is read whole (§6.5), so BTC's interval comes only from the bootstrap of `nbtc.bridge.near`'s total and the two readings of unknown routes. That interval can lie above 90% (consistent) or below 50% (contradicted).
  - **Solana: estimates only, no verdict.** SOL (in SOL) and the Solana stablecoins (pooled, in USD) each get Omni's amount share with its interval (§4.0) and the sensitivities below, reported beside BTC's verdict. The reasons:
    - With the window-level bound, a part's lower limit can reach 90% only if its strata have about 36 effective windows each (0.025^(1/36) = 90.3%; the stablecoins' bound is the average of their two strata's, weighted by their totals), and an effective count never exceeds the number of windows.
    - Even with equal window amounts, that needs 36 to 54 more windows than the 54 planned. At SOL's measured spread, a 90% chance of 36 effective windows needs about 72 windows per stratum, about 162 more for the three. That spread is a log-sd of 1.55 over the 14 transfers of the shakedown window, fitted as a lognormal. The budget has 23 credits to spare (§6.10).
    - So the design could contradict the Solana half but not confirm it, and a test that can go only one way is reported as estimates.
    - The write-up gives each Solana interval, and calls no Solana result consistent, partly or contradicted. It says plainly that at this sample size the Solana half could not be confirmed even by an all-Omni sample, so the absence of a verdict is not evidence against the claim.
  - **Sensitivity** (published, not verdicts): τ = 80% and τ = 95%, with the 50% line unchanged; count shares; each direction alone; the 90-day period. For Solana these are estimates too.
  - These limits are stated before the draw.
- **C3.** Estimates only: the three classifications' shares with intervals, the class-3 sensitivity, and the fragility share from apps that have announced an end.
- **Trend** (M3): the ratio of the mean daily rate in the last 3 complete months before T0 to that in the 3 months before them, raw, then excluding class 3 and 2a. Its interval comes from the stratified bootstrap. It is growing if the interval lies above 1, shrinking if it lies below 1, and inconclusive otherwise. It is not completed if any of its strata is.
- **Migration** (M10, per series): moving to Omni if the interval of the difference (§4, M10) lies above 0; moving away from Omni if it lies below 0; no clear move otherwise. It is not measurable or not completed under the same rules as a share.
- **How blind these are.** The readings were written after an uncounted pilot and the documents, and before the counted draw. The write-up states what the pilot showed:
  - SOL, ZEC and BTC transfers went through Omni;
  - ETH, USDC on Ethereum, Arbitrum and Base, Tron USDT and XRP went through POA;
  - one window per token, Nov 9 (RESEARCH H).

## 8. Flags and exclusions

- **Sep 29 to Oct 4, 2026 is flagged.** It covers the NEAR Intents exploit and the route pauses:
  - the notice of Oct 1, 12:53Z, kept 11 networks closed about 12 more hours;
  - CertiK places the drain on HOT's bridge (`v2_1.omni.hot.tg`, BSC payouts), not on `v1.signer`.

  Rates are reported with and without these days. Flow and census windows avoid them.
- **Sweat Wallet's closing window** (Oct 1 to Dec 30, 2026) is flagged, because exits can inflate calls.
- Pilot data (Nov 9, seed 20261109, and the uncounted rate pilots) is exploratory and never counted.

## 9. Reproducibility

- Every input is public chain data that anyone can re-query: NearBlocks with the frozen windows and seed, the token list, neardata block heights, archival RPC heights, and the saved forum JSON.
- The repo ships:
  - `instants.json` (every window, its segments, weight and stratum), `nd_plan.json`, `tokens.json` and `callers.json`;
  - the collector (`collector/`), its offline tests (`tests/`), and the pages as fetched: every row with its identifiers, timestamps, accounts, amounts and status, plus each page's request and cursor;
  - one keyless command that re-pulls every window and checks the new pull against the published rows and hashes;
  - one offline command that recomputes every published number from the rows.
- **Two-stage freeze.**
  - Stage 1, before any counted call: this file, `instants.json`, `nd_plan.json`, `tokens.json`, `callers.json`, the frozen rates file, and a SHA-256 manifest of the collector code and tests, including `analysis/flows.py`, which the collector uses to find resolution candidates.
  - Stage 2, before any counted row is read by any analysis: a SHA-256 manifest of the analysis code. Before that hash, the analysis code is tested only on uncounted data: the pilot rows, the shakedown and `tests/fixtures`. Any change after the hash, including one prompted by running it on counted rows, is logged in `DEVIATIONS.md`. The collector's own transaction resolution (§3) reads counted rows by the stage-1 rule; it computes nothing that is published beyond its own log.

  Both manifests are submitted to OpenTimestamps.
- **What these sources cannot give**, stated in THESIS.md: daily active accounts and contract usage across NEAR (BigQuery, not used); Intents' own swap volume (Explorer API, not used); HOT's flow; and the destination-chain leg of Omni's Solana and EVM withdrawals.
- Attribution: "Powered by Nearblocks.io APIs".

## 10. Timeline: four separate times

1. **Method freeze (stage 1):** before any counted call, by 2026-11-10T18:00Z. The design is selected by the clock (§6.10). Then the SHA-256 manifest of this file, `instants.json`, `nd_plan.json`, `tokens.json`, `callers.json` and the collector code is submitted to OpenTimestamps. Submission is immediate; the Bitcoin-confirmed proof follows some hours later, and the repo is upgraded with it when available. The code has no git commit yet, because a commit needs Bhargav's approval of the exact files and title; the manifest hashes the files themselves.
2. **Data cutoff T0:** the freeze time rounded down to the hour. Nothing after T0 is sampled.
3. **Analysis:** stage 2 freezes the analysis code before any counted row is read; analysis is complete by 2026-11-13T12:00Z. Sampling stops by 2026-11-13T00:00Z (§6.10).
4. **Publication:** internal cut 2026-11-14T06:00Z, ahead of the Devpost deadline of 23:59Z. Nothing is pushed or submitted without his yes.

## 11. Deviations

Any change after the freeze is logged in `DEVIATIONS.md` with a timestamp and a reason.
