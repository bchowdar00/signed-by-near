# Results (T0 2026-11-10T11:00:00.000000Z, B = 2000)

## Completeness

| family | completed | not completed | pending |
|---|---|---|---|
| census | 48 | 0 | 0 |
| flow | 192 | 0 | 0 |
| index | 11 | 0 | 2 |
| migration | 57 | 0 | 18 |
| sign | 182 | 0 | 16 |

Resolution audit: 19 transactions read whole, 0 differ from the window view.

## C2b (M2): BTC verdict, Solana estimates

| group | reading | Omni share [L, U] | state | transfers / windows |
|---|---|---|---|---|
| BTC | claim|amount|both | [100.0%, 100.0%] | consistent | 106 / 7 |
| BTC | claim|count|both | [99.9%, 100.0%] | consistent | 106 / 7 |
| BTC | claim|amount|in | [100.0%, 100.0%] | consistent | 69 / 4 |
| BTC | claim|amount|out | [100.0%, 100.0%] | consistent | 37 / 6 |
| BTC | 90d|amount|both | [99.7%, 100.0%] | consistent | 230 / 16 |
| SOL | claim|amount|both | [24.7%, 100.0%] | estimate only | 220 / 17 |
| SOL | claim|count|both | [76.9%, 100.0%] | estimate only | 220 / 17 |
| SOL | claim|amount|in | [26.0%, 100.0%] | estimate only | 104 / 17 |
| SOL | claim|amount|out | [14.9%, 100.0%] | estimate only | 116 / 17 |
| SOL | 90d|amount|both | [32.1%, 100.0%] | estimate only | 349 / 23 |
| Solana stablecoins (USD) | claim|amount|both | [43.2%, 100.0%] | estimate only | 647 / 36 |
| Solana stablecoins (USD) | claim|count|both | [77.7%, 100.0%] | estimate only | 647 / 36 |
| Solana stablecoins (USD) | claim|amount|in | [42.3%, 100.0%] | estimate only | 362 / 36 |
| Solana stablecoins (USD) | claim|amount|out | [40.5%, 100.0%] | estimate only | 285 / 36 |
| Solana stablecoins (USD) | 90d|amount|both | [26.4%, 100.0%] | estimate only | 882 / 48 |

## M1: route map of the 28 chains (C1, no verdict)

| chain | documented | Omni overview | observed use | dominant route |
|---|---|---|---|---|
| Adi | hot |  | unknown | unknown |
| Aptos | poa | yes | yes | unknown |
| Arbitrum | omni, poa | yes | unknown | unknown |
| Avalanche | hot |  | unknown | unknown |
| BCH | poa |  | unknown | unknown |
| BNB | omni, hot | yes | yes | unknown |
| Base | omni, poa | yes | unknown | unknown |
| Berachain | poa |  | unknown | unknown |
| Bitcoin | omni, poa | yes | yes | yes |
| Cardano | poa |  | unknown | unknown |
| Dogecoin | poa |  | unknown | unknown |
| Ethereum | omni, poa | yes | unknown | unknown |
| Gnosis | poa |  | unknown | unknown |
| LayerX | hot |  | unknown | unknown |
| Litecoin | poa |  | unknown | unknown |
| Monad | hot |  | unknown | unknown |
| Optimism | hot |  | unknown | unknown |
| Plasma | hot |  | unknown | unknown |
| Polygon | hot | yes | yes | unknown |
| Scroll | hot |  | unknown | unknown |
| Solana | omni, poa | yes | yes | unknown |
| Starknet | poa | yes | yes | unknown |
| Stellar | hot |  | unknown | unknown |
| Sui | poa |  | unknown | unknown |
| TON | hot |  | unknown | unknown |
| Tron | poa |  | unknown | unknown |
| XRP | poa |  | unknown | unknown |
| Zcash | poa | yes | yes | unknown |

Observed: 7 yes, 28 yes or unknown, of 28. Dominant: 1 yes, 28 yes or unknown. Documented capability: 10 of 28.

## M9 (C2a, estimates only)

- p, Omni's share of measured value: [21.1%, 89.5%]; p_CS (Omni withdrawals): [6.2%, 78.6%]
- measured value per 30 days: $3,072,610,861 [2,175,937,307, 4,111,835,516]
- c against V 369.6%, against 2V 100.0%, against the headline 82.7% (context)
- scenarios: S_L 21.1%, S_U 89.5%
- measured non-Omni value per 30 days: [1,163,179,892, 2,586,210,008] USD, [70.0%, 155.5%] of 2V

## M10: migration (amount, native units)

| series | early [L, U] | late [L, U] | difference | state |
|---|---|---|---|---|
| SOL | [–, –] | [–, –] | [–, –] | not completed |
| ZEC | [–, –] | [–, –] | [–, –] | not completed |
| BTC | [0.0%, 96.3%] | [99.7%, 100.0%] | [3.4%, 100.0%] | moving to Omni |
| ETH (POA control) | [–, –] | [–, –] | [–, –] | not completed |

## Trend (M3)

- raw: 0.89 [0.75, 1.06], inconclusive
- excluding class 3 and 2a: 2.37 [1.65, 3.70], growing
- excluding 2a only (class 3 kept): 1.73 [1.35, 2.27], growing

## M3 and M4 by month

| month | calls/day [95%] | main | main without Sweat | narrow | broad |
|---|---|---|---|---|---|
| 2024-08 (not completed) | – [–, –] | – [–, –] | – [–, –] | – | – |
| 2024-09 | 18 [0, 53] | – [0.0%, 0.0%] | – [0.0%, 0.0%] | 0.0% | 3.7% |
| 2024-10 (not completed) | – [–, –] | – [–, –] | – [–, –] | – | – |
| 2024-11 | 1,094 [95, 2,943] | – [0.0%, 0.0%] | – [0.0%, 0.0%] | 0.0% | 0.5% |
| 2024-12 (not completed) | – [–, –] | – [–, –] | – [–, –] | – | – |
| 2025-01 (not completed) | – [–, –] | – [–, –] | – [–, –] | – | – |
| 2025-02 (not completed) | – [–, –] | – [–, –] | – [–, –] | – | – |
| 2025-03 | 5 [1, 10] | – [0.0%, 0.0%] | – [0.0%, 0.0%] | 0.0% | 85.7% |
| 2025-04 | 77 [28, 129] | – [2.9%, 21.4%] | – [2.9%, 21.4%] | 14.8% | 21.7% |
| 2025-05 (not completed) | – [–, –] | – [–, –] | – [–, –] | – | – |
| 2025-06 (not completed) | – [–, –] | – [–, –] | – [–, –] | – | – |
| 2025-07 (not completed) | – [–, –] | – [–, –] | – [–, –] | – | – |
| 2025-08 (not completed) | – [–, –] | – [–, –] | – [–, –] | – | – |
| 2025-09 | 1,558 [1,290, 1,864] | – [0.0%, 14.0%] | – [0.0%, 14.0%] | 5.0% | 5.9% |
| 2025-10 (not completed) | – [–, –] | – [–, –] | – [–, –] | – | – |
| 2025-11 | 2,994 [2,200, 3,859] | 37.3% [27.3%, 45.1%] | 37.3% [27.3%, 45.1%] | 37.3% | 37.3% |
| 2025-12 | 3,844 [3,222, 4,549] | 18.5% [14.6%, 21.5%] | 18.5% [14.6%, 21.5%] | 18.5% | 19.3% |
| 2026-01 | 4,736 [3,886, 5,869] | 38.5% [25.0%, 49.3%] | 38.5% [25.0%, 49.3%] | 38.5% | 39.3% |
| 2026-02 | 8,036 [4,475, 12,847] | 47.3% [32.3%, 59.2%] | 47.3% [32.3%, 59.2%] | 47.3% | 63.5% |
| 2026-03 | 9,212 [5,040, 13,383] | 50.9% [24.5%, 71.4%] | 50.9% [24.5%, 71.4%] | 50.9% | 66.0% |
| 2026-04 | 25,395 [11,716, 41,036] | 87.7% [73.1%, 92.1%] | 19.8% [12.9%, 36.9%] | 19.8% | 88.4% |
| 2026-05 | 24,001 [19,200, 29,190] | 81.0% [68.6%, 86.4%] | 9.0% [2.3%, 21.4%] | 9.0% | 85.0% |
| 2026-06 | 22,929 [18,072, 28,370] | 76.3% [58.5%, 85.9%] | 4.2% [0.8%, 22.0%] | 4.2% | 77.1% |
| 2026-07 | 24,001 [17,760, 30,481] | 71.0% [59.8%, 77.1%] | 3.0% [0.8%, 14.2%] | 3.0% | 72.0% |
| 2026-08 | 25,894 [21,475, 30,418] | 50.0% [39.7%, 57.7%] | 2.0% [0.9%, 12.4%] | 2.0% | 50.0% |
| 2026-09 | 22,951 [18,450, 27,631] | 43.5% [32.7%, 54.1%] | 2.0% [0.4%, 12.8%] | 2.0% | 43.5% |
| 2026-10 | 14,046 [10,808, 17,568] | 37.5% [23.5%, 47.7%] | 3.5% [1.7%, 17.4%] | 3.5% | 38.9% |
| 2026-11 | 13,095 [7,290, 19,846] | 36.1% [21.4%, 55.6%] | 4.1% [2.7%, 18.8%] | 4.1% | 37.1% |

## M8: program expenditure per request

| month | NEAR executed (+pending) | calls | NEAR per request |
|---|---|---|---|
| 2026-03 | 36,800.00 | 285,569 | 0.1289 [0.0887, 0.2355] |
| 2026-04 | 34,500.00 | 761,845 | 0.0453 [0.0280, 0.0982] |
| 2026-05 | 38,878.00 | 744,017 | 0.0523 [0.0439, 0.0653] |
| 2026-06 | 45,340.66 | 687,883 | 0.0659 [0.0533, 0.0836] |
| 2026-07 | 52,219.94 | 744,017 | 0.0702 [0.0553, 0.0948] |
| 2026-08 | 65,840.54 | 802,700 | 0.0820 [0.0698, 0.0989] |
| 2026-09 | 73,293.34 | 688,516 | 0.1065 [0.0884, 0.1324] |
| 2026-10 (provisional) | 0.00 | 435,432 | 0.1765 [0.1411, 0.2294] |

## M7: completion

```
{
 "n_blocks": 2000,
 "evaluated": 255,
 "matched": 252,
 "matched_unique": 241,
 "matched_by_order": 11,
 "ambiguous": 0,
 "censored": 3,
 "failed_responses_seen": 3,
 "unmatched_responses": 9,
 "matched_share": 0.9882352941176471,
 "matched_share_unambiguous": 0.9882352941176471,
 "median_delay_s": 2.923521993,
 "max_delay_s": 5.490712115
}
```

## Not completed at the deadline

36 of 526 windows were not completed at the deadline (index 2, migration 18, sign 16). A dash (–) or "not completed" above marks a reading that rests on one of them: by the method it has no number (`POST-FREEZE.md`). The readings, each with the reason:

- `M10/BTC/chart/0`: this monthly window is unfinished
- `M10/BTC/chart/1`: this monthly window is unfinished
- `M10/BTC/chart/3`: this monthly window is unfinished
- `M10/BTC/chart/6`: this monthly window is unfinished
- `M10/BTC/migration_window_counters`: a migration window of the series is unfinished
- `M10/ETH (POA control)/chart/4`: this monthly window is unfinished
- `M10/ETH (POA control)/chart/5`: this monthly window is unfinished
- `M10/ETH (POA control)/chart/6`: this monthly window is unfinished
- `M10/ETH (POA control)/migration_window_counters`: a migration window of the series is unfinished
- `M10/ETH (POA control)/readings`: an early or late stratum of the series is unfinished (the whole measure, POST-FREEZE ruling)
- `M10/SOL/chart/1`: this monthly window is unfinished
- `M10/SOL/chart/3`: this monthly window is unfinished
- `M10/SOL/chart/4`: this monthly window is unfinished
- `M10/SOL/migration_window_counters`: a migration window of the series is unfinished
- `M10/SOL/readings`: an early or late stratum of the series is unfinished (the whole measure, POST-FREEZE ruling)
- `M10/ZEC/chart/4`: this monthly window is unfinished
- `M10/ZEC/chart/5`: this monthly window is unfinished
- `M10/ZEC/migration_window_counters`: a migration window of the series is unfinished
- `M10/ZEC/readings`: an early or late stratum of the series is unfinished (the whole measure, POST-FREEZE ruling)
- `M3/0/failed_share`: a sign window of this month is unfinished
- `M3/0/raw`: a sign window of this month is unfinished
- `M3/10/failed_share`: a sign window of this month is unfinished
- `M3/10/raw`: a sign window of this month is unfinished
- `M3/11/failed_share`: a sign window of this month is unfinished
- `M3/11/raw`: a sign window of this month is unfinished
- `M3/12/failed_share`: a sign window of this month is unfinished
- `M3/12/raw`: a sign window of this month is unfinished
- `M3/14/failed_share`: a sign window of this month is unfinished
- `M3/14/raw`: a sign window of this month is unfinished
- `M3/2/failed_share`: a sign window of this month is unfinished
- `M3/2/raw`: a sign window of this month is unfinished
- `M3/4/failed_share`: a sign window of this month is unfinished
- `M3/4/raw`: a sign window of this month is unfinished
- `M3/5/failed_share`: a sign window of this month is unfinished
- `M3/5/raw`: a sign window of this month is unfinished
- `M3/6/failed_share`: a sign window of this month is unfinished
- `M3/6/raw`: a sign window of this month is unfinished
- `M3/9/failed_share`: a sign window of this month is unfinished
- `M3/9/raw`: a sign window of this month is unfinished
- `M4_M5/0`: a sign window of this month is unfinished
- `M4_M5/10`: a sign window of this month is unfinished
- `M4_M5/11`: a sign window of this month is unfinished
- `M4_M5/12`: a sign window of this month is unfinished
- `M4_M5/14`: a sign window of this month is unfinished
- `M4_M5/2`: a sign window of this month is unfinished
- `M4_M5/4`: a sign window of this month is unfinished
- `M4_M5/5`: a sign window of this month is unfinished
- `M4_M5/6`: a sign window of this month is unfinished
- `M4_M5/9`: a sign window of this month is unfinished

Signature-index months not completed at the deadline: 2026-02, 2026-08.
