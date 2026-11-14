# What the result will mean for a NEAR holder, written before the first look

Written: 2026-11-13T05:46:06Z. Status: a pre-read commitment, not yet approved for use; it can be published or dropped whole, never edited.
At this time no counted row of the sample has been read by anyone or used in any computation. The first read is set for 2026-11-13T11:00:30Z and the gate logs its time (`POST-FREEZE.md`). This file and a byte copy of the thesis sketch of 2026-11-10 are hashed in `MANIFEST-preread.txt`, which is submitted to OpenTimestamps before that read. It changes no reading, no threshold and no frozen file.
Known gaps: the receipt is pending until Bitcoin confirms it; this file proves when the words existed, not that they are right.

## The claim under test (the sketch's words, 2026-11-10)

"On the chains this sample can measure, Chain Signatures is a narrow route, not a broad one."

## The five results that would prove it wrong (`DEVIATIONS.md` item 21, frozen with the analysis code)

1. **Value mostly on Omni.** The lower end of Omni's share of the measured value over the 90 days is at least 90%, and the measured non-Omni value's upper end is under 10% of twice NearStats' 30-day swap volume.
2. **Omni dominant widely.** Omni is the dominant route on at least 5 of the 8 measurable chains.
3. **Broad adoption.** In each of August, September and October 2026, apps beyond NEAR's own infrastructure, without Sweat, make at least 25% of `sign` calls, with a lower end of at least 15%.
4. **Falling spend per request.** NEAR paid per request falls month on month over July to September 2026, each interval wholly below the one before, while calls grow.
5. **No migration.** No clear move to Omni for SOL, ZEC or BTC.

Each reads met (the claim is wrong on that point), not met, or undecided (a reading it needs was not completed).

## How the first screen will be worded, whatever the result

- The first screen gives the count: how many of the five were met, not met and undecided, with each test named.
- If test 1 or test 2 is met, the first sentence says the claim was wrong on breadth: the measured flow runs on NEAR's signer.
- If tests 1 and 2 are both not met, the first sentence says the claim held on breadth.
- If neither is met and either is undecided, the first sentence says this sample does not settle breadth, and only the decided readings are shown.
- Tests 3, 4 and 5 qualify that sentence (who else uses the signer, what it costs, which way the route is moving). They do not reverse it.

## What each reading means for someone who holds NEAR

NEAR's cross-chain case has three layers: Intents' own contract and solver network on NEAR; the bridge that moves an asset in and out; and, on NEAR's own bridge (Omni), the signer that signs each withdrawal. This entry measures the second and third.

| Reading | If it comes in high | If it comes in low |
|---|---|---|
| Omni's share of measured value (test 1; the BTC and Solana rows) | That flow cannot leave without a signature only NEAR's signer makes. To move it elsewhere a rival has to replace the signer and its operators. The partner's "mitigated" has measured support on these chains. | Most measured value moves on a custodial bridge that holds its own keys and never calls the signer. What keeps that flow on NEAR is Intents' own network, not Chain Signatures. A holder who prices NEAR on "28 blockchains via NEAR's chain signature architecture" is pricing the wrong component. |
| Chains where Omni dominates (test 2) | The partner's own unit, chains, supports the claim on the chains that can be read. | The moat is a few chains wide where it can be read; the other 20 stay unread, and the entry says so. |
| Direction (test 5) | If a series is moving to Omni: narrow today can still be widening, and the question becomes how fast. | If none is moving: the split between the two bridges is stable. |
| Outside apps' share of calls (test 3) | The signer has reach of its own, apart from NEAR's bridge. | After Sweat Wallet's change on 2026-12-30 the signer is mostly a utility for NEAR's own bridge. The first month that can show this is January 2027. |
| NEAR paid per request (test 4) | — | — |

On cost the read is the same in every outcome: a `sign` call attaches 1 yoctoNEAR, so the signer charges no fee for a signature, and its operators are paid from emissions. Today the signer is a cost that holders carry through dilution. High breadth makes it a cost that buys a dependency. Low breadth makes it a cost that buys little flow. Falling cost per request while calls grow would show scale; anything else means the subsidy grows with the operator set.

## The combined reads

- **Broad** (test 1 or 2 met): the moat is where NEAR's side says it is. The open question for a holder is price: the dependency exists and charges nothing.
- **Narrow and widening** (tests 1 and 2 not met; a series moving to Omni): a moat under construction. The holder watches the monthly Omni share of SOL, ZEC and BTC.
- **Narrow and static** (tests 1 and 2 not met; test 5 met): on the measured chains the moat claim does not hold. Intents' value to NEAR then rests on Intents itself: its fees, its solvers, and where it chooses to settle.
- **Not settled** (test 1 or 2 undecided, neither met): the entry says so first and gives no breadth verdict.

## What the entry will not say under any outcome

No price target and no valuation of NEAR. The signer charges no fee for a signature, so any value reaches the token through Intents' fees and gas, which this sample does not measure. The entry will state that as a limit, in one sentence, beside the read above.

## Reading it again

The five tests are thresholds on public data, and one command re-pulls the sample without a key. Anyone can read them again. The dates that matter: January 2027 for test 3 (the first full month after 2026-12-30), and each month's HSP-007 report for test 4.
