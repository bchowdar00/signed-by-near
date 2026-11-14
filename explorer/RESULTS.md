# The Explorer read: results

Written by `explorer/analyse.py` from `explorer/data/blocks.jsonl`; do not edit by hand. The plan is `explorer/PLAN.md`, the family rules `explorer/STAGE2.md`. This is an addition made after the counted read. It changes no test of `THESIS.md`.

All 90 blocks of 24 hours were read, so these figures are a count of every completed 1Click swap the API returned for the 90 days to T0, not a sample.

- Completed swaps read: 1,934,126, in 1,979 pages, pulled between 2026-11-13T23:35:26Z and 2026-11-14T02:46:08Z.
- Rows outside their block's bounds and dropped: 0. Rows seen twice and counted once: 0. Rows with no USD figure: 0 on the way in, 0 on the way out.
- Value of all completed swaps over the 90 days, by `amountInUsd`: $3,850.7 million.
- Over the 30 days to T0: $1,054.7 million (30 of those 30 blocks read).

## Withdrawals: value that left through a bridge

Rows with recipient type `DESTINATION_CHAIN`, summed by `amountOutUsd`, by the family of the token on that side.

| family | value | share of bridged value | swaps |
|---|---|---|---|
| Omni-form tokens | $490.7 million | 14.0% | 66,478 |
| POA-form tokens on the SDK's moved-to-Omni list | $589.0 million | 16.8% | 367,412 |
| POA-form tokens | $2,191.2 million | 62.4% | 1,054,884 |
| HOT's tokens | $200.7 million | 5.7% | 229,036 |
| unclassified | $41.8 million | 1.2% | 3,694 |
| all bridged | $3,513.4 million | 100.0% | 1,721,504 |
| a token on NEAR (no bridge leg) | $105.9 million | not counted | 113,063 |
| an Intents balance (no bridge leg) | $209.5 million | not counted | 99,559 |

- Omni's share of bridged value, Omni-form tokens only: 14.0%.
- With the tokens on the SDK's moved-to-Omni list counted as Omni: 30.7%.
- With the unclassified value counted as Omni too: 31.9%.
- POA-form tokens not on the SDK's list: 62.4%. HOT's tokens: 5.7%.
- The 8 chains the keyless sample could read (8 chains here): $3,240.9 million bridged; Omni-form 15.1%, SDK-listed 18.1%, POA-form 66.2%, HOT 0.0%, unclassified 0.5%.
- Every other chain (29 chains here): $272.5 million bridged; Omni-form 0.3%, SDK-listed 0.3%, POA-form 16.3%, HOT 73.7%, unclassified 9.4%.

| chain | read by the keyless sample | value | Omni-form | SDK-listed | POA-form | HOT | unclassified |
|---|---|---|---|---|---|---|---|
| eth | yes | $1,147.0 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| tron | yes | $773.1 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| btc | yes | $489.4 million | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| sol | yes | $307.4 million | 0.1% | 94.6% | 0.0% | 0.0% | 5.3% |
| zec | yes | $297.3 million | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% |
| bsc | no | $155.8 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| arb | yes | $108.1 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| base | yes | $80.6 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| xrp | yes | $37.9 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| hypercore | no | $25.0 million | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% |
| pol | no | $22.8 million | 3.7% | 0.0% | 0.0% | 96.3% | 0.0% |
| ltc | no | $14.3 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| ton | no | $11.9 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| avax | no | $6.4 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| sui | no | $6.0 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| doge | no | $5.8 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| gnosis | no | $5.6 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| aleo | no | $2.8 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| cardano | no | $2.6 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| dash | no | $2.2 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| stellar | no | $2.1 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| hood | no | $2.0 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| plasma | no | $1.9 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| op | no | $1.3 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| bch | no | $1.0 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| aptos | no | $1.0 million | 0.0% | 39.7% | 0.0% | 0.0% | 60.3% |
| monad | no | $0.7 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| starknet | no | $0.5 million | 0.0% | 98.0% | 0.0% | 0.0% | 2.0% |
| xlayer | no | $0.5 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| prl | no | $0.2 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| adi | no | $0.1 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| scroll | no | $0.0 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| fogo | no | $0.0 million | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| bera | no | $0.0 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| qtc | no | $0.0 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| movement | no | $0.0 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| miden | no | $0.0 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |

## Deposits: value that came in through a bridge

Rows with deposit type `ORIGIN_CHAIN`, summed by `amountInUsd`, by the family of the token on that side.

| family | value | share of bridged value | swaps |
|---|---|---|---|
| Omni-form tokens | $476.8 million | 14.6% | 151,086 |
| POA-form tokens on the SDK's moved-to-Omni list | $541.2 million | 16.6% | 282,476 |
| POA-form tokens | $1,996.7 million | 61.2% | 908,591 |
| HOT's tokens | $242.8 million | 7.4% | 236,929 |
| unclassified | $5.8 million | 0.2% | 2,758 |
| all bridged | $3,263.3 million | 100.0% | 1,581,840 |
| a token on NEAR (no bridge leg) | $86.6 million | not counted | 92,828 |
| an Intents balance (no bridge leg) | $500.8 million | not counted | 259,458 |

- Omni's share of bridged value, Omni-form tokens only: 14.6%.
- With the tokens on the SDK's moved-to-Omni list counted as Omni: 31.2%.
- With the unclassified value counted as Omni too: 31.4%.
- POA-form tokens not on the SDK's list: 61.2%. HOT's tokens: 7.4%.
- The 8 chains the keyless sample could read (8 chains here): $2,968.3 million bridged; Omni-form 16.1%, SDK-listed 18.2%, POA-form 65.6%, HOT 0.0%, unclassified 0.1%.
- Every other chain (28 chains here): $295.0 million bridged; Omni-form 0.1%, SDK-listed 0.5%, POA-form 16.5%, HOT 82.3%, unclassified 0.5%.

| chain | read by the keyless sample | value | Omni-form | SDK-listed | POA-form | HOT | unclassified |
|---|---|---|---|---|---|---|---|
| eth | yes | $1,136.9 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| tron | yes | $609.9 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| btc | yes | $476.1 million | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| zec | yes | $334.6 million | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% |
| sol | yes | $209.7 million | 0.2% | 97.8% | 0.0% | 0.0% | 2.0% |
| bsc | no | $201.8 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| arb | yes | $98.2 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| base | yes | $62.8 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| xrp | yes | $40.1 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| ltc | no | $19.0 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| pol | no | $15.8 million | 2.2% | 0.0% | 0.0% | 97.8% | 0.0% |
| stellar | no | $9.5 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| cardano | no | $8.9 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| avax | no | $6.7 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| ton | no | $5.2 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| doge | no | $4.8 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| gnosis | no | $4.1 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| sui | no | $3.6 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| hood | no | $2.7 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| op | no | $2.6 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| bch | no | $2.0 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| aptos | no | $1.6 million | 0.0% | 84.3% | 0.0% | 0.0% | 15.7% |
| plasma | no | $1.3 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| dash | no | $1.2 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| hypercore | no | $1.2 million | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% |
| monad | no | $1.0 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| aleo | no | $0.8 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| xlayer | no | $0.6 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| starknet | no | $0.3 million | 0.0% | 80.1% | 0.0% | 0.0% | 19.9% |
| prl | no | $0.2 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| bera | no | $0.1 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| scroll | no | $0.0 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| qtc | no | $0.0 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| fogo | no | $0.0 million | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| adi | no | $0.0 million | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| miden | no | $0.0 million | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |

## The three blocks read twice

| block | swaps, first reading | swaps, second reading | cells equal | value in, first | value in, second |
|---|---|---|---|---|---|
| 22 | 35,543 | 35,543 | yes | $54.8 million | $54.8 million |
| 2 | 20,026 | 20,026 | yes | $22.7 million | $22.7 million |
| 16 | 26,632 | 26,632 | yes | $39.0 million | $39.0 million |
