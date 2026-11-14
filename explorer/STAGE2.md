# The Explorer read: stage 2, the family rules

Status: rules fixed before any cell was read. Written 2026-11-13T23:40:57Z.
Last reconciled: 2026-11-13T23:40:57Z.
Known gaps: one family rests on the operator's label and not on a statement of the route (rule 5); the custody of the POA bridge is taken from its code, and the names of its key holders were not checked.

`explorer/PLAN.md` left one thing to this stage: which form of token ID belongs to which bridge family. The rules below are in `explorer/analyse.py` (`form_of`, `FAMILY_OF_FORM`). They were written while the pull ran. Before this file was timestamped, the pull's log had shown the number of pages and rows of the blocks finished so far; no cell of `explorer/data/blocks.jsonl` had been opened or read by anyone, and the tests of this code ran on made-up cells only.

## The rules

A side of a swap counts as a bridge leg only if the API marks it so (deposit type `ORIGIN_CHAIN`, recipient type `DESTINATION_CHAIN`) and the token is delivered on a chain other than NEAR. The chain is the one the public 1Click token list gives for the asset ID (`explorer/data/assets.json`; the list at https://1click.chaindefuser.com/v0/tokens needs no key, fetched 2026-11-13T23:36:55Z, 231 assets); for an ID missing from that list it is read from the ID itself.

| # | form of the ID | family | source, and its standing |
|---|---|---|---|
| 1 | `<chain>.omft.near`, `<chain>-<address>.omft.near`, not on the SDK's list | POA | **confirmed.** The Intents SDK's `PoaBridge` class handles these IDs (github.com/defuse-protocol/sdk-monorepo, `packages/intents-sdk/src/bridges/poa-bridge/poa-bridge.ts`); the token contract's minting is gated to its owner (github.com/near/intents, `poa-token/src/contract.rs`). |
| 2 | `.omft.near` and on the SDK's list of 17 | POA-form, listed by the SDK as moved to Omni | **confirmed as a list.** `poa-tokens-migrated-to-omni-bridge.ts` at commit `930d2816`, sha256 `ed49694cd4641f48041e92b6dfa58bf133918e4cd5fce2f75a505a227fe3eb01`, fetched again on Nov 13 with the same hash. It is the SDK's label, not an observed route, so it is a line of its own. |
| 3 | `<chain>.omdep.near`, `<chain>-<address>.omdep.near` | Omni | **confirmed.** `omdep.near` is in the Omni Bridge repository's own list of its mainnet contracts on NEAR, and the same README says: "All outbound transfers use Chain Signatures (MPC)." (github.com/Near-One/omni-bridge, `README.md`, read Nov 13, sha256 `70545b26c1476c9c93133ec1e554de36fbf5a1b435b2fd98eb2b8e47c1f12d5e`). The README lists the account without saying in words what it does; the repository's `near/token-deployer` contract is the one that creates such token accounts. |
| 4 | `nep245:v2_1.omni.hot.tg:<chain id>_<token>` | HOT | **confirmed.** HOT's documentation describes deposits and withdrawals on the `v2_1.omni.hot.tg` contract as validated by "HOT MPC networks", HOT's own, not NEAR's signer (docs.hotdao.ai/omni-tokens). |
| 5 | `1cs_v1:btc:native:coin` | Omni | **on the operator's label.** The public token list and the supported-assets table (docs.intents.aurora.dev/intents-swap/supported-assets) name this asset "BTC(OMNI)", beside "BTC" for `btc.omft.near`. No source read states the route in a sentence. Counting it as Omni leans against this entry's reading of T1, which is the safer way to be wrong. |
| 6 | any other `1cs_v1:<chain>:…` on a chain other than NEAR | unclassified | **not found.** The 1Click documentation shows `1cs_v1:` is the API's own ID scheme for assets on their home chain; nothing read says which bridge moves them. Every Omni share is given with this value counted against Omni and for it. |
| 7 | everything else (`wrap.near`, `nbtc.bridge.near`, `*.factory.bridge.near`, `1cs_v1:near:…`) | a token on NEAR: no bridge leg | the public token list gives `near` as the chain for each of these. |

The worker's notes behind this table, with every address fetched, are kept outside this repository; the three lines marked confirmed for rules 3, 4 and 5 were read again at the source by the author's session before this file was written.

## What the analysis writes

`explorer/analyse.py` writes `explorer/RESULTS.md` and `explorer/results.json` from the cells: the four figures of the plan's section 6, with the Omni share given three ways (Omni-form tokens only; with the SDK-listed tokens; with the unclassified value too), each chain's line, and the 8 chains the keyless sample could read against every other chain. `explorer/recheck.py` reads the first three blocks of the fixed order (22, 2 and 16) a second time and compares the cells.
