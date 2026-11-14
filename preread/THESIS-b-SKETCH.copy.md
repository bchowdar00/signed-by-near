# THESIS sketch for option (b): where NEAR's cross-chain moat sits

Status: sketch. Bhargav chose (b) on 2026-11-09. Its claim, thresholds and charts are fixed here before the counted sample and carry into THESIS.md, which is written from the counted, frozen sample. Every number below is a pilot or a documentary reading, labelled so.
Last reconciled: 2026-11-10T12:36:31Z (Claude).
Known gaps:
- The counted sample is being drawn (started 2026-11-10T11:52:19Z); the caller registry was frozen with stage 1.
- Flow is measured by count in one window per token so far, not by amount (RESEARCH H).
- HOT's flow cannot be read through NearBlocks' FT endpoints. C1 and C2a get estimates and a per-chain table, not verdicts. C2b's Solana half gets estimates too: at this budget the design could contradict it but not confirm it at 90% (METHOD-b §7).

## The long-term question

Part of NEAR's long-term case rests on one claim about its cross-chain stack: that Chain Signatures, the MPC signer `v1.signer`, is a broad moat.
- **The partner.** SVRN rates "Competition" a MEDIUM risk, "mitigated" by a "28-chain moat". It says solvers fulfil intents "across 28 blockchains via NEAR's chain signature architecture".
- **The CTO.** Near One's CTO says Chain Signatures "powers all the network's cross-chain volume", and that "virtually all BTC and Solana cross-chain flow now moves through" NEAR's Omni bridge.

Breadth is one input to two judgements a holder makes: how much the partner's "Competition: MEDIUM" rests on the signer, and what the emissions that pay its operators buy. It does not settle either. A narrow moat can still be valuable, and emissions buy security as well as reach. Narrow here means: a few of the measured chains, NEAR's own bridge and a small set of outside apps, beside a custodial bridge that carries most of the measured tokens' flow.

## Claim (written before the counted sample; either answer is publishable)

The claim covers only what the counted sample measures: 15 tokens on 8 of the 28 chains that C1 names, the signer's callers, and NEAR's spend on the program. Intents has since grown past 28: NearStats listed 39 supported chains on Nov 9 (*reported*).

"On the chains this sample can measure, Chain Signatures is a narrow route, not a broad one.
- It carries Intents' BTC, ZEC and SOL through NEAR's own Omni bridge, and that route is growing. On Omni, Chain Signatures signs the withdrawals; deposits are verified by light clients (Bitcoin, Zcash) or Wormhole (Solana).
- On the measured EVM, Tron and XRP tokens, the custodial POA bridge carries the flow.
- Outside NEAR's own bridge, the signer's largest users are one wallet that is closing, which mostly signs NEAR-account transactions rather than cross-chain ones, and one independent bridge, Relay, which signs its withdrawals through contracts on Aurora.
- NEAR pays for the program from emissions."

It says nothing about the other 20 of the 28, HOT's included, beyond their documented capability. Nor does it speak for the chains added since.

The readings (METHOD-b §7) were written from the claims' own words before the counted sample. What the pilot showed first is stated. If the sample shows otherwise, the entry says so.

## Evidence for (pilot and documents, Nov 9)

- **Routes by flow** (RESEARCH H, one window per token, counts):
  - Omni carries SOL, Solana tokens, ZEC and BTC;
  - POA carries ETH, Ethereum, Arbitrum and Base USDC, Tron USDT and XRP;
  - HOT carries BNB-chain assets on its own MPC network (arXiv 2512.02287).
- **Capability.** NEAR's own Omni overview lists 10 of Intents' 28 chains, and Intents' bridging page assigns 17 to POA and 11 to HOT. That is a documentary count, not a ceiling, so the counted test reads flow per chain (M1). Omni's README says "All outbound transfers use Chain Signatures (MPC)", while inbound transfers are verified by light clients (Ethereum, Bitcoin, Zcash) or by Wormhole (Solana, BNB, EVM L2s) (*confirmed*). So on Omni, Chain Signatures signs the withdrawals, and part of the trust in SOL deposits rests on Wormhole.
- **Volume.** The chains on Chain Signatures (Zcash, Bitcoin, Solana) carry $242.5M, 29%, of the $831.3M of 30-day swap volume in NearStats' store of Explorer rows (Nov 9, *reported*). Its ten largest chains sum to 97.5% of that volume, so the chain totals do not double the swap total. NEAR's headline 30-day total, $3.71B, the figure other entries cite, is 4.5 times that store. Why the two differ is not established here, and only the store has a chain split (METHOD-b M9).
- **Callers.** For most of the signer's life, the largest share of sampled `sign` calls came from a 5-minute health check and then a load test. In 2026 the largest users were FastAuth, mostly for Sweat Wallet (which ends in its present form on Dec 30, 2026), NEAR's own bridge, and contracts on Aurora. Those Aurora contracts were traced before the freeze to Relay, an independent cross-chain protocol (verified contract names on Aurora's explorer; Relay's docs place its Allocator, which "Generates MPC withdrawal payloads", on "Aurora (NEAR)"). The pilot's caller shares predate that tracing; the counted sample gives them by the frozen registry.
- **What the calls sign.** In 103 sampled calls, all 49 of Sweat's were Ed25519 signatures on per-user login paths, with no secp256k1. They most likely control NEAR accounts rather than sign for other chains (neardata pilot; an inference from key type and path). The cross-chain-capable calls (secp256k1) came from Omni, its BTC and Zcash connectors, Aurora XCC and a load test.
- **It works.** In 500 contiguous blocks, all 24 requests paired one-to-one with a response within 5 s, median 2.9 s (pilot). 13 of the pairs rest on order within repeated tweaks, so they are not proven. The moat question is about reach, not reliability.
- **Cost.**
  - Executed payouts were 36,800 NEAR for March 2026 and 73,293.34 NEAR for September. October's 76,864.52 NEAR is proposed, pending a challenge window to Nov 12 (HSP-007 execution thread).
  - October's pilot rate was about 13,600 `sign` calls a day. On the proposed October figure that is roughly 0.18 NEAR, about $0.48, per call at the thread's reference price.
  - A `sign` call pays 1 yoctoNEAR.

## Evidence against (what cuts the other way)

- **The CTO's BTC-and-Solana sentence looks right on chain.** On the routes where it is used, Omni carries nearly all the measured flow, and Chain Signatures signs its withdrawals. Those include the hard chains. Bitcoin and Zcash have no smart contracts, so a withdrawal needs keys that someone holds, and Chain Signatures is how NEAR holds them without a single custodian.
- **The route map is moving towards Omni.** SOL and ZEC moved to it while the Intents docs still list POA, and Omni's capability (13 chains) is wider than its use. A narrow moat can widen; M10 measures whether it is.
- **Use beyond NEAR's own infrastructure exists, and one user is a competitor's kind of product.** Relay, an independent cross-chain intents protocol, settles withdrawals with signatures from `v1.signer`, through its Allocator contract on Aurora. A rival intents network choosing NEAR's signer is evidence the signer has reach of its own, apart from Intents. Others: Sweat (through FastAuth), Meteor and Dew vaults, Ref, Trezu treasuries and Peerfolio.
- **Counts are not value.** One BTC withdrawal can move more value than a thousand logins. A few important integrations can justify the signer, and a subsidised operator set does not by itself make a weak moat.
- **Sweat's exit** is one app's decision, not a verdict on the technology.

## What would change our mind

The readings in METHOD-b §7 decide each claim. The sketch's claim would be wrong if the counted sample shows any of these, with the thresholds fixed now:
- **Measured value mostly on Omni.** The lower bound of Omni's share of the measured tokens' value (p, M9) is at least 90% over the 90 days, and the measured non-Omni value per 30 days is under 10% of 2V, twice NearStats' 30-day swap volume, because the measured value counts a swap's deposit and its withdrawal (M9).
- **Omni dominant widely.** Omni is the dominant route (M1, *yes*) on at least 5 of the 8 measurable chains, not 3.
- **Broad adoption.** In each of the last 3 complete months, the main classification without Sweat (classes 4, 4x and 2b) carries at least 25% of `sign` calls, with lower bounds of at least 15% (M4, M5).
- **Falling spend per request.** Program expenditure per request (M8) falls month on month across the last three executed months, with each interval below the one before, while M3's rate grows.
- **No migration.** M10 shows no clear move to Omni for SOL, ZEC and BTC.

## The two charts

1. **Where Intents' measured cross-chain flow runs.** The 8 measurable chains as bars of the measured tokens' flow, coloured by route: Omni (withdrawals signed by Chain Signatures, deposits verified by light clients or Wormhole), POA (custodial) and unknown. The 20 chains the sample cannot read, HOT's among them, are listed beside the bars with their documented route, not drawn as flow. A second panel shows each M10 series' Omni share early and late, with the monthly chart points, and BTC custody by route (M10b).
2. **Who calls the signer, and what the program costs per request.** Monthly `sign` calls by caller class from August 2024 to the cutoff, with the health-check, load-test and Sweat bands shaded. Program expenditure per request, from March 2026 (executed plus pending; October provisional), is a second panel below it on the same month axis. (Changed on 2026-11-10 from "a second axis": two y scales on one plot invite a false reading of where the lines cross. The data and thresholds are unchanged.)

## What this does not cover

It does not model how Intents' fees reach the NEAR token, or value NEAR. Those belong to a value-capture analysis, which this entry deliberately is not. Nor does it re-check NEAR's headline totals (volume, users, TVL, fees). It asks which route carries the cross-chain flow behind them. The thesis stops at where the moat is, whether it is widening, and what NEAR pays for it.
