# Caller sources, batch 3 (8 items)

Research date: 2026-11-09. `nearblocks.io` address pages returned HTTP 403 Forbidden on every direct fetch attempted (8 attempts, one per item below) — flagged per item rather than silently worked around. Where a nearblocks.io page's content could still be read via a search engine's indexed snippet, that is labeled **reported** (block-explorer label, read second-hand) and the 403 is noted.

## 1. `laikachainab.near`

- Owner/app: **none found.**
- Kind: unknown.
- Builder: unknown.
- Source: none found.
- Searches tried: "laikachainab.near NEAR account"; "laikachain NEAR protocol token"; "\"laikachainab\" near"; "\"laikachainab.near\""; `site:nearblocks.io laikachainab.near`; "\"sign\" \"v1.signer\" \"laikachainab\" OR \"Laika Chain\" sports NEAR AB company".
- Pages tried: coinmarketcap.com/coingecko/coinbase price pages for a token called "Laïka" / "LaikaChain" — confirmed unrelated: that token is on Ethereum and Base ("Ethereum 0x19e...e1b6d6, Base 0xea6...6ecadd"), not NEAR. `github.com/Laika-Chain` org exists but is a Dogecoin L2, no NEAR connection found. `nearblocks.io/address/laikachainab.near` — 403 Forbidden, could not read.

## 2. `mindshare_contract.near`

- Owner/app: **Mindshare Index AI Agent**, built by **Yonder Labs**. Confidence caveat: no source states the literal on-chain account ID "mindshare_contract.near" — the link is the exact name-match to Yonder Labs' public repo `Yonder-Labs/mindshare_contract`. Per the brief's rule, the name is the lead; I treat the app identity as confirmed and the specific account-ID match as inferred from that name.
- Kind: production app (autonomous trading agent).
- Builder: independent team — Yonder Labs, operating inside NEAR's Shade Agent ecosystem (not NEAR Foundation/Near One/Defuse/Aurora itself, though covered by NEAR's and Proximity Labs' own content).
- Source (confirmed, NEAR's own blog): https://www.near.org/blog/introducing-the-mindshare-index-ai-agent-autonomous-trading-powered-by-shade-agents — "Smart contract: https://github.com/Yonder-Labs/mindshare_contract/" sits beside "Agent code: https://github.com/Yonder-Labs/mindshare_agent/", describing "a fully autonomous trading system" that trades on NEAR using chain signatures and NEAR Intents.
- Source (confirmed, the repo itself): https://github.com/Yonder-Labs/mindshare_contract — README describes "A secure and verifiable smart contract system for managing worker agents in a Trusted Execution Environment," with no account ID given (deploy instructions use a placeholder `<account-id>`).

## 3. `acc.toalice.near` and `brg.toalice.near` ("toalice")

- Owner/app: **none found.**
- Kind: unknown.
- Builder: unknown.
- One weak, unverified data point: a search-engine-indexed snippet of a nearblocks.io page (not independently re-confirmed — the live page 403'd) showed a transaction where `watcher05.ref-watchdog.near` called `update_gas_token_price` on `acc.toalice.near` (0 Ⓝ deposit, ~4 months before the search, i.e. roughly mid-2025). This hints `toalice` might be a gas-price oracle contract watched by a Ref Finance-adjacent bot, but no source names what app "toalice" is, and the caller name alone is not evidence. Label: **reported**, and thin.
- Searches tried: "toalice.near NEAR protocol"; "\"toalice\" near.org OR github OR app"; "\"toalice.near\" relayer OR \"gas station\" OR meta-transaction NEAR"; "\"toalice.near\""; `site:nearblocks.io "acc.toalice.near" OR "brg.toalice.near"`; `site:github.com ... "toalice.near"`.
- Pages tried: a GitHub user "toAlice" (NvidiaTeslaP40forGaming, Minecraft scripts) — unrelated individual, not pursued further per the brief's rule against researching private individuals. `nearblocks.io/address/acc.toalice.near` — 403 Forbidden, could not read directly.

## 4. `margin-toward.kronos-heyelsa.near` and `twist-hollow.heyelsa.near` ("HeyElsa")

**Stop-and-report: the official HeyElsa source contradicts the premise that these are HeyElsa's accounts.**

- Owner/app: HeyElsa is a real product — "the crypto agent layer that turns intent → action," per its own litepaper — but HeyElsa's own documentation names only Ethereum, Base, and Solana (plus bridges/venues like Wormhole, Portal, Solend, Hyperliquid) and its $ELSA token runs on Base. No source found ties HeyElsa to NEAR, chain signatures, or any `*.near` account.
- Kind: unknown for these specific accounts.
- Builder: unknown for these specific accounts; if they are HeyElsa's, no confirming source exists.
- Source (confirmed, HeyElsa's own blog): https://blog.heyelsa.ai/heyelsa-the-crypto-agent-layer-litepaper/ — "Elsa makes DeFi feel like typing a message," with named chains Ethereum/Base/Solana and no mention of NEAR.
- Searches tried: "HeyElsa heyelsa.near chain signatures"; "\"heyelsa.near\" chain signatures account"; "HeyElsa NEAR chain abstraction account github dhawalshah agent"; "HeyElsa NEAR Shade Agents chain signatures partnership announcement"; "\"HeyElsa\" NEAR.org blog OR pages.near.org"; `site:nearblocks.io "margin-toward.kronos-heyelsa.near" OR "twist-hollow.heyelsa.near"`.
- Pages tried: dappradar.com/dapp/heyelsa-ai — 403 Forbidden, could not read. nearblocks.io/address/heyelsa.near — 403 Forbidden.
- The account names ("margin-toward", "twist-hollow") read like auto-generated two-word identifiers (the style used by random pet-name generators for test/sandbox accounts), which is a further reason not to assume they're an official HeyElsa integration from the name alone. Flagging this whole item rather than guessing.

## 5. `ptke2.auth-v0.peerfolio.near` (Peerfolio)

- Owner/app: **Peerfolio** — an autonomous/AI-agent trading-account system ("MPC Secured Agent Autonomy").
- Kind: production app / wallet-and-agent infrastructure (a proxy-factory contract that creates bounded-permission trading accounts for an AI agent).
- Builder: independent team — Peerfolio (GitHub org `beneviolabs`; on-chain factory owner is a DAO, `peerfolio.sputnik-dao.near`).
- Source (confirmed, the project's own repo): https://github.com/beneviolabs/autonomous-trading-account — "NEAR smart contracts that give an AI agent limited, revocable authority to trade on a user's behalf." The same repo's PR #184 states "auth.dev.peerfolio.near is a second mainnet factory for Peerfolio Backend's staging and local dev."
- Discrepancy to flag: the live README I fetched directly names the current/previous factories as `auth.peerfolio.near` and `auth-v1.peerfolio.near` ("The previous mainnet factory, `auth-v1.peerfolio.near`, was replaced in January 2026") — it does **not** contain the string "auth-v0" on a direct re-fetch. But a search engine's indexed copy of the same repository (surfaced independently across two separate queries) shows an **earlier** version of this README naming `auth-v0.peerfolio.near` as the ProxyFactory contract, with per-user trading accounts at `user.auth-v0.peerfolio.near` and setup variable `FACTORY_ACCOUNT="auth-v0.peerfolio.$NETWORK"` — which matches your target item's pattern exactly (`ptke2.auth-v0.peerfolio.near`). I could not re-fetch that older version directly (web.archive.org is not reachable from this tool) to confirm it live, so label that specific "auth-v0" detail **reported** (search-index only), while the Peerfolio ownership itself is **confirmed** from the live repo.

## 6. `dew-rneardefi-kernel.near`

- Owner/app: **none found for "kernel" specifically.** A same-family, documented account is `dew-rneardefi-vault.near` ("Dew NEAR Liquid Staking Defi Vault Share," ticker dewNEAR), which search results connect to Meteor Wallet's vault system (transfers with `near.meteor-vaults.near`) and to the rNEAR liquid-staking token ecosystem (Rhea Finance — the Ref Finance/Burrow merger — issues a different rNEAR at `lst.rhealab.near`). No source found specifically describes a "kernel" contract in this family, who builds "Dew," or whether it's Rhea Finance's own product.
- Kind: unknown (plausibly a DeFi vault/strategy contract, unconfirmed).
- Builder: unknown.
- Source (reported, block-explorer page title via search index, not independently re-confirmed — live fetch 403'd): nearblocks.io's page title "Dew NEAR Liquid Staking Defi Vault Share (dewNEAR) Stats, Price, Holders & Transactions" for `dew-rneardefi-vault.near`.
- Searches tried: "rneardefi-kernel.near NEAR"; "\"rneardefi\" OR \"rNEAR\" kernel vault meteor near"; "\"rneardefi-kernel\""; "Meteor Wallet vaults \"kernel\" contract NEAR strategy"; "\"dew\" NEAR liquid staking vault \"Dew\" protocol who built"; `site:nearblocks.io "dew-rneardefi-kernel.near"`.

## 7. `xrp-pi23guf5k47lb3kfbob5gs7z2fr3dsgpdpq2jo4l.acmore.near` and `xrp-air7253p7nkvdy2ixjr7dfcftra4oy7pcsmxto3n.acmore.near` ("acmore.near")

- Owner/app: **none found.**
- Kind: unknown.
- Builder: unknown.
- Technical background only (not a source about this account): NEAR's own Chain Signatures docs and reporting confirm the mechanism these names fit — Chain Signatures natively derives addresses on XRP Ledger from a NEAR account plus a derivation path, and the long strings after `xrp-` are consistent with that derivation pattern. This explains the shape of the names but says nothing about who "acmore" is.
- A GitHub user handle "acmore" exists (Singapore-based, 10 repos: okdev, scripts, skill-map, etc.) with no NEAR, XRP, or chain-signature repos — flagged only because the name coincided in search results; no evidence connects this individual to the NEAR account, so this is not pursued further (and would not be pursued even if it matched, per the rule against researching private individuals).
- Searches tried: "acmore.near NEAR account"; "\"acmore.near\""; "\"acmore.near\" xrp OR bridge OR chain signatures github"; "github.com \"acmore\" near xrp OR hackathon OR signer"; `site:nearblocks.io acmore.near`; `site:github.com ... "acmore.near"`.
- Pages tried: `nearblocks.io/address/acmore.near` — 403 Forbidden. `github.com/codingshot/near-ecosystem` (a NEAR ecosystem aggregator repo) — no match for "acmore" in its README.

## 8. `contract.stp-p0.near`

- Owner/app: **Possible match, not confirmed:** the Stablecoin Transport Protocol (STP), built by Yonder Labs within the Proximity Labs/NEAR ecosystem. "P0" plausibly reads as a phase/pilot marker, but no source ties the literal account `contract.stp-p0.near` to STP — this is a name/topic match, not a confirmed identification.
- Kind (if the match holds): bridge/settlement infrastructure for cross-chain stablecoin swaps — unconfirmed for this specific account.
- Builder (if the match holds): independent team — Yonder Labs, within Proximity Labs' ecosystem.
- Source (confirmed, via api.fxtwitter.com, Proximity Labs' own account): https://x.com/proximityfi/status/2008584528613519688 — Proximity Labs' post introducing "the Stablecoin Transport Protocol (STP) litepaper. Developed by Yonder Labs, STP enables cross-chain stablecoin swaps in sizes of 1M to 10M+ with no slippage and very low fees (1 to 3bp)," linking to stablecointransport.com (unreachable when I tried to fetch it directly: connection refused).
- Source (confirmed, DapDap's own docs — the live frontend for this protocol): https://docs.dapdap.net/apps/stableflow/how-stableflow-works — "All transfers are atomically settled by the Verifier Smart Contract on NEAR Protocol." This page does not name the contract's account ID and does not mention "stp-p0" or STP by name.
- Searches tried: "stp-p0.near NEAR contract"; "\"stp-p0\" near github chain signatures"; "\"stp-p0.near\""; "\"stp-p0\" OR \"stp.near\" sports NEAR prediction"; "gov.near.org \"stp-p0\" OR \"STP\" grant proposal sports"; "Yonder Labs \"Stablecoin Transport Protocol\" NEAR STP contract"; "\"Stablecoin Transport Protocol\" \"stp-p0\" OR \"p0\" NEAR"; "\"stp-p0.near\" OR \"contract.stp-p0\" StableFlow DapDapMeUp".
- Pages tried: `nearblocks.io/address/contract.stp-p0.near` — 403 Forbidden. `stablecointransport.com` — connection refused.

## Telemetry

- Items done: 8 / 8
- Items with a confirmed source: 2 full (items 2, 5 — app identity confirmed from the builder's own repo/blog; one sub-detail in item 5 stays reported) plus 1 confirmed-but-contradicting (item 4, HeyElsa's own litepaper confirms the app but contradicts the NEAR link) plus 1 confirmed-but-unconfirmed-match (item 8, STP's builder is confirmed, the account match is not)
- Items with only reported sources: 2 (items 3, 6 — thin, second-hand block-explorer content only)
- Items with none found: 2 (items 1, 7)
- Pages fetched (WebFetch calls, including 403s and failures): 21
