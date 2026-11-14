# Next reads: what this entry expects, and when

Status: written on 2026-11-13, after the first counted read (11:00:30Z), and timestamped before it was published (`MANIFEST-afterread.txt` and its receipt). It is not one of the frozen tests and it changes no frozen result. It adds one comparison of scale, three dated readings with a threshold and an expectation each, and one source found after the read.
Known gaps: no later sample has been collected, and none is promised here; the expectations are judgement, not measurement; whether the deployed SDK matches the cited code was not checked.

## 1. The scale of the cost

The proposed payout to the signer's operators for October 2026 is 76,864.52 NEAR. Twelve months at that rate is 922,374.24 NEAR, equal to 2.8% of the most NEAR the protocol can issue in a year (32,789,997.54 NEAR: a total supply of 1,311,599,901.41 NEAR at block 224,372,919, times the maximum inflation rate of 1/40; `inputs/chain-params.json`).

This is a comparison of scale, not a share of issuance. HSP-007 pays the operators from "protocol emissions held in `treasury.near`": NEAR emitted earlier, which diluted holders then. The programme spends it and adds no new supply. The protocol's reward rate to the treasury is 0/1 today.

## 2. Three next reads

Each uses a series and a threshold that were frozen before the read (`METHOD.md`; `THESIS.md`, "What would change my mind"). The expectation beside each was written on 2026-11-13. Anyone can make these reads with the frozen method and the collector in this repo.

**A. Adoption after Sweat. When: January 2027, the first full month after Sweat ends in its present form on 2026-12-30; readable from February 2027.**
- Series: the share of `sign` calls made by apps beyond NEAR's own infrastructure. In October 2026, leaving Sweat out, it was 3.5% [1.7%, 17.4%]; Sweat alone made 34.0% of the calls, and the signer took 14,046 calls a day.
- Threshold (frozen test 3): at least 25%, with a lower end of at least 15%.
- Expectation: not met; the share stays under 25%. If Sweat's calls stop and nothing else changes, the same apps would make 5.2% of the calls that remain, and the signer would take about 9,270 calls a day; a January figure above that means the other callers grew.
- Against the expectation: a share of 25% or more with a lower end of 15% or more.

**B. Cost per request. When: the day October 2026's payout is executed on the HSP-007 thread, and each monthly report after it.**
- Series: NEAR paid per `sign` request. September 2026: 0.1065 [0.0884, 0.1324].
- Threshold (frozen test 4): falling month on month, each interval wholly below the one before, while calls grow.
- Expectation: not met, and higher than September's. If October is paid as proposed, 76,864.52 NEAR over October's 435,432 calls [335,044, 544,604] is 0.1765 NEAR per request [0.1411, 0.2294].
- Against the expectation: an executed October figure below September's 0.1065.

**C. Solana and Zcash. When: the first sample by this method, with a cutoff after 2026-12-30, in which every SOL and ZEC window is completed.**
- Series: Omni's share of Intents' bridged SOL and ZEC over 90 days. In this sample Omni carried 100.0% of the sampled SOL and 94.3% of the sampled ZEC, with intervals reaching down to 32.1% and 16.8%.
- Threshold (the method's rule for a dominant route): the lower end of Omni's share above 50%, by count and by amount.
- Expectation: both read dominant. That would make Omni the dominant route on 3 of the 8 readable chains, up from 1, and still under the 5 that frozen test 2 needs.
- Against the expectation: with every window completed, a lower end at or below 50% on either.

**What the three add up to.** If A and B read as expected and C does too, the signer is a route that is widening by chain (Bitcoin, then Solana and Zcash) while its use by apps outside NEAR's own stack stays small and its cost per signature rises. What keeps flow on NEAR on the other measured chains is then still Intents' own network, not Chain Signatures.

## 3. A source found after the read

The Intents team's SDK carries a list of tokens that "originally were PoA Bridge tokens but have since been migrated to Omni Bridge": 17 tokens, 12 on Solana (SOL, USDC and USDT among them), 3 on Aptos, Starknet's token and `zec.omft.near`. No Ethereum, Arbitrum, Base, Tron or XRP token is on it. Source: github.com/defuse-protocol/sdk-monorepo, `packages/intents-sdk/src/constants/poa-tokens-migrated-to-omni-bridge.ts` at commit `930d2816`, read 2026-11-13, sha256 `ed49694cd4641f48041e92b6dfa58bf133918e4cd5fce2f75a505a227fe3eb01`.

- It is a list in the SDK's code of which tokens the SDK treats as Omni, not a measurement of flow.
- Its history: first listed on 2026-01-08 (three Solana tokens, behind an opt-in switch); the switch was removed on 2026-08-14; Zcash was added on 2026-09-01. The last two dates fall inside the 90 days this sample measures. When SOL, USDC and USDT joined the list was not checked.
- It bears on this entry's reading both ways. It agrees with the sample on the EVM, Tron and XRP tokens, where no sampled transfer moved on Omni. It says the team routes SOL and ZEC through Omni, which the sample's intervals were too wide to confirm.
- No frozen test result changes, and nothing was re-run. The route of every sampled transfer comes from the counterparties of Intents' own legs, not from token names, so the list cannot have changed a label (`METHOD.md`, section 3).
