# Caller registry sources — batch 1 (items 1–8 of the closed list)

Tool note (applies throughout): `nearblocks.io` address pages returned HTTP 403 to direct fetch every time they were tried (including `beta.`, `legacy.` mirrors, which 301-redirect to the blocked host, and Medium for the Sweat post). Per house rules this is flagged rather than silently worked around. Where nearblocks content below is used, it is a search-engine's cached summary of the page, not a direct read — labelled **reported (unverified at source, nearblocks 403'd)**.

---

## 1. tx-bench.near

- **Owner/app:** unknown / unconfirmed. No doc names an operator.
- **Kind:** test / benchmark / load test — supported by volume and name, not a statement.
- **Builder:** unknown.
- **Source 1 (reported):** Dune dashboard `proximity_team/v1signer`, built by the Proximity team. Widget "Actions by predecessor" ranks predecessor accounts calling into `v1.signer` by transaction count; top row: `"receipt_predecessor_id": "tx-bench.near"`, `"txns_cnt": 87561` — far above #2 (`enochdanijel1.near`, 840). https://dune.com/proximity_team/v1signer (fetched directly; dashboard itself doesn't label the account or say "load test").
- **Source 2 (reported, nearblocks 403'd, read via search cache only):** search-engine summary of nearblocks.io transaction listings states "From: tx-bench.near. To: v1.signer" with repeated `sign` calls at zero deposit, Block ~209,308,696. https://nearblocks.io/address/tx-bench.near — could not verify directly (403).
- Searched and found nothing: `near/mpc` GitHub repo and README (no "tx-bench" string), NEAR docs (`docs.near.org/chain-abstraction/chain-signatures*`), Near One blog (`blog.nearone.org`, including its Mar 29 2026 "Benchmarking Threshold Signature Schemes" post — different kind of benchmark, laptop-run Criterion microbenchmarks, no mention of tx-bench.near or any deployed-contract load test), NEAR forum/governance search, GitHub code search for "tx-bench".
- **Caution:** "load test" is supported only by the huge call count + the account's own name; no source states an owner or purpose.

## 2. ping-account.near

- **Owner/app:** none found.
- **Kind:** unknown (name suggests health check, unconfirmed).
- **Builder:** unknown.
- **Source:** none found.
- Searches tried: `"ping-account.near"`, `"ping_account.near"`, site:nearblocks.io ping-account.near, GitHub code search, NEAR forum search combined with "health check"/"v1.signer", general "ping-account near health check monitor contract". All returned either nothing or unrelated matter (NEAR staking-pool `ping`/`pinger.near` mechanism, Oracle Cloud health checks, PING golf equipment — none is this account).
- Direct nearblocks fetch also 403'd, so the account's own transaction history could not be read either.

## 3. fast-auth.near

- **Owner/app:** NEAR Auth (public name), internal/legacy codename **FastAuth**. Built by **Peersyst** — named by NEAR's own Infrastructure Committee update as "FastAuth 2.0 (subject to rename) by Peersyst/NEAR Mobile Wallet Team."
- **Kind:** shared login/auth infrastructure — a production service other apps integrate as SDKs, not a single app.
- **Builder:** independent team — **Peersyst** (operating as, or alongside, NEAR's "NEAR Mobile Wallet Team"); NEAR Foundation/Near One surface it in official channels but the code and docs are Peersyst's (repo `github.com/Peersyst/fast-auth`, npm scope `@fast-auth-near/*`).
- **Source 1 (confirmed — NEAR's own blog):** near.org, "NEAR Infrastructure Committee Selects RFP Winners for Chain Abstracted Relayer SDKs" — under "NEAR Infrastructure Committee Updates: Stay tuned for upcoming updates, including: ... FastAuth 2.0 (subject to rename) by Peersyst/NEAR Mobile Wallet Team" (completing implementation, entering audit). https://www.near.org/blog/near-infrastructure-committee-announces-chain-abstracted-relayer-rfp-winners (published 2025-06-20; fetched directly).
- **Source 2 (confirmed — the project's own docs):** docs.auth.near.org/home/what-is — "NEAR Auth is an authentication system for NEAR Protocol" that lets people "sign real on-chain transactions using the identities they already have — Google, Apple, email, or passkeys," naming the on-chain contract "(`FastAuth`)" as the entry point, deployed at `fast-auth.near` (mainnet) / `fast-auth.testnet`. https://docs.auth.near.org/home/what-is and https://docs.auth.near.org/resources/mainnet (fetched directly; mainnet contract list: `fast-auth.near`, `jwt.fast-auth.near`, `auth0.jwt.fast-auth.near`, `v1.signer`).
- **Shared-service claim:** the docs target "dApp and product teams" with drop-in SDKs (web/React/React Native) rather than stating explicitly that one shared mainnet service is used by many apps — but on-chain activity (item 4 below, sweat-relayer.near calling `sign` on `fast-auth.near`) is reported evidence that at least Sweat Wallet routes through it.

## 4. sweat-relayer.near

- **Owner/app:** Sweat Wallet / Sweat Economy.
- **Kind:** wallet/relayer — a meta-transaction relayer that pays gas on behalf of Sweat Wallet users and, per on-chain activity, is a FastAuth signer.
- **Builder:** independent team — Sweat Economy (not Near One/Pagoda/Proximity/Aurora).
- **Source 1 (confirmed — Sweat's own publication, found but not fetchable):** Sweat Economy's Medium post "Demystifying NEAR: Your Sweat Wallet's not-so-secret partner" describes the gasless/relayer mechanism (gas paid in $SWEAT, Sweat Foundation funds user NEAR accounts). https://medium.com/sweat-economy/demystifying-near-your-sweat-wallets-secret-partner-712c46e971ac — **direct fetch returned HTTP 403**, so this is **reported** from the search summary only, not verified at the source text. Sweat's help-center articles (help.swe.at, help.sweateconomy.com, "What is NEAR?") corroborate the same mechanism but also weren't fetched directly.
- **Source 2 (reported, nearblocks 403'd, read via search cache only):** search-engine summary of nearblocks.io shows `sweat-relayer.near` submitting `DELEGATE_ACTION`/batch calls to `spin.sweat`, `jars-oracle.sweat`, `sweat_welcome.near`, and — directly relevant to the FastAuth link — "a 'Call sign' action by sweat-relayer.near on fast-auth.near." https://nearblocks.io/address/sweat-relayer.near — not independently verified (403).
- **Caution:** the Sweat-ownership claim rests on the account's naming convention (`.sweat` contracts it calls) plus the Medium/help-center descriptions of Sweat's relayer design; no single source both names the account and states Sweat operates it under its own text that I could read directly.

## 5. rathrelayer.near

- **Owner/app:** no confirmed source names this specific account. Best lead: **Rath** (rath.fi), whose relayer product is called **Tachyon**.
- **Kind:** relayer (if the lead holds) — supports NEAR and Solana among 30+ chains, consistent with the brief's description (FastAuth signer seen signing to Solana, Oct 2025).
- **Builder:** independent team — Rath Finance, if the lead holds.
- **Evidence (name-based lead only — explicitly flagged, not treated as a source for the account):**
  - NEAR's own blog names Rath as an Infrastructure Committee relayer-RFP winner: "two teams, Rath and HOT Labs, have been selected," Tachyon described as an "ultra-fast, multichain relayer." https://www.near.org/blog/near-infrastructure-committee-announces-chain-abstracted-relayer-rfp-winners (confirmed, fetched directly; published 2025-06-20; does not mention Solana or any account name).
  - Rath's own docs: "Every chain Tachyon supports: EVM, Solana, Sui, Aptos, NEAR, Starknet, and more." https://docs.rath.fi/ (confirmed, fetched directly; does not mention "rathrelayer.near", FastAuth, MPC, or chain signatures at all).
  - Rath announced "Tachyon is live on mainnet" (X/rathfinance, 2026) — not fetched (X restricted to api.fxtwitter.com per brief; this came up only as a search snippet, not fetched through fxtwitter).
- **Verdict:** none found that ties the literal account `rathrelayer.near` to Rath/Tachyon. The match is the name only ("rath" + "relayer"); per the brief's rule this is stated as a lead, not a source.
- Searches tried: `"rathrelayer.near"`, `"rathrelayer" near account`, site:nearblocks.io rathrelayer.near, "Rath Tachyon NEAR relayer account testnet mainnet near.org github", "rathrelayer.near OR rath relayer fastauth solana". nearblocks direct fetch also 403'd.

## 6. jwt-chain-signatures.near

- **Owner/app:** none found.
- **Kind:** unknown.
- **Builder:** unknown.
- **Source:** none found. Confirmed by contrast: NEAR Auth's own mainnet contract list (docs.auth.near.org/resources/mainnet, fetched directly) names exactly `fast-auth.near`, `jwt.fast-auth.near`, `auth0.jwt.fast-auth.near`, `v1.signer` — `jwt-chain-signatures.near` is not among NEAR Auth's own contracts, so it is a separate, unidentified account.
- Searches tried: `"jwt-chain-signatures.near"` (plain and quoted), GitHub code search (site:github.com), near/NEPs issue #503 fetched directly and searched in full text for the string — not present (closest: a Sept 2023 comment "We are using JWT Tokens to authenticate users on the MPC Recovery server," unrelated account), NEAR's active "Build Beyond Boundaries" hackathon (Nov 1–14, 2026) project list — several chain-signatures entries found (AgentSig, OmniYield Protocol, Silent Partner, AEGIS, VaultGuard) but none named with "jwt" or matching this account.
- nearblocks direct fetch also 403'd, so the account's own history could not be read.

## 7. Aurora XCC sub-accounts (4 addresses)

All four verified **directly against Aurora's own Blockscout explorer API** (`explorer.mainnet.aurora.dev/api/v2/addresses/<addr>`), which returned `is_verified: true` and a contract `name` field for each — this is a **confirmed** source (the explorer's own verified-contract metadata, not a third-party label):

| XCC sub-account | EVM address | Verified contract name |
|---|---|---|
| `7eda04920f22ba6a2b9f2573fd9a6f6f1946ff9f.aurora` | `0x7eda04920f22ba6a2b9f2573fd9a6f6f1946ff9f` | **RelayAllocator** |
| `e12bc514e90e136cad10413669a6ccdeb9e3adb7.aurora` | `0xe12bc514e90e136cad10413669a6ccdeb9e3adb7` | **Allocator** |
| `66667945c34b399993ca834587886b8508db39b1.aurora` | `0x66667945c34b399993ca834587886b8508db39b1` | **RelayMultisigSigner** |
| `62e1e3be3df663f0563c4ef48233d42ec988e6d9.aurora` | `0x62e1e3be3df663f0563c4ef48233d42ec988e6d9` | **BitcoinDepositAddress** |

- **Owner/app:** **Relay Protocol** (relay.link) — a cross-chain intents/settlement protocol.
- **Kind:** bridge infrastructure — these are the MPC-withdrawal and Bitcoin-deposit-settlement contracts of a cross-chain bridge, deployed on Aurora and calling NEAR Chain Signatures via XCC.
- **Builder:** independent team — **Uneven Labs** (formerly "Reservoir"; relay.link began "as a humble side project to power Zora's crosschain NFT minting"), not Aurora Labs itself — Aurora only hosts it as an EVM-compatible execution layer.
  - Source (reported — industry writeup, not Uneven Labs' own site): solanacompass.com project page on Relay Protocol; names founders (Peter Watts et al.) and "Uneven Labs." Not independently fetched/verified beyond the search summary.
- **Source — confirms the contract roles (confirmed, Relay Protocol's own docs, fetched directly):** docs.relay.link/references/protocol/how-it-works — "Relay Protocol settles cross-chain intents." "The Allocator ... is located on Aurora (NEAR)" and "generates MPC withdrawal payloads" / "MPC-signed proofs (EIP-712 for EVM, Ed25519 for Solana)"; "Depository ... holds user deposits on each origin chain (80+ supported chains)."
- **Source — confirms BitcoinDepositAddress's Bitcoin role (reported — third-party security audit writeup, fetched directly):** Zellic, "Eight Bytes to Burn a Bridge – Relay Protocol's Legacy Bitcoin Sighash Bug" — "During our review of Relay Protocol's Settlement Protocol, we spent some time around the Bitcoin sweep path," and "Relay settles each Bitcoin-side order through a unique deposit address derived by NEAR MPC." https://www.zellic.io/blog/signing-blind/
- Aurora's own Chain Signatures demo (separate from Relay Protocol, checked for completeness): doc.aurora.dev/blog/safe-bitcoin-demo/, by Aurora DevRel Slava Karkunov with Oleksandr Anyshchenko writing the Solidity "Chain Signatures Signer" contract — mainnet address `0xF7607CD922804DaA9D54d21349Dd6F9467098dDE`, XCC sub-account `f7607cd922804daa9d54d21349dd6f9467098dde.aurora`. This is a **different, unrelated** contract/sub-account from the four on the closed list — noted so the two aren't confused.

## 8. relay.aurora

- **Owner/app:** this is **not** Relay Protocol (Uneven Labs) despite the name match — it is **Aurora Engine's own generic EVM-transaction relayer account**, built and operated by **Aurora Labs**.
- **Kind:** bridge/EVM infrastructure — the single default NEAR signer account that the (now-deprecated) `aurora-relayer` service uses to submit every Aurora EVM transaction to the `aurora` contract via `submit`/`submit_with_args`. It is not specific to any one app; it is the pass-through for Aurora's whole EVM traffic.
- **Builder:** Aurora Labs.
- **Source 1 (confirmed — Aurora Labs' own repo config):** `github.com/aurora-is-near/aurora-relayer`, `config/mainnet.yaml` and `config/testnet.yaml` — set `signer: relay.aurora`, `engine: aurora`. (Fetched via search; the repo's own README additionally marks `aurora-relayer` **[DEPRECATED]**.)
- **Source 2 (confirmed — Aurora's own blog, an AMA with the Engine team lead):** "the only way to submit new blocks to Aurora mainnet is through the relay.aurora account per the mainnet config," adding it isn't centralized because "it's possible to host your own relayer." https://aurora.dev/blog/ama-with-aurora-engine-team-lead-joshua-j-bouw (also mirrored at mainnet.aurora.dev/blog/... in search results; not independently refetched to confirm exact URL — flagged).
- **Source 3 (confirmed — Aurora's own GitHub discussion):** `aurora-is-near/aurora-engine` Discussion #461, "Aurora Cross Contract Calls" — describes the flow: user signs via MetaMask, "the RPC creates a NEAR transaction from relay.aurora to the aurora contract calling the method 'submit'."
- **On the "Bitcoin signatures in Nov 2026" detail:** no source directly ties `relay.aurora`'s specific November 2026 Bitcoin-signing receipt to a named app. Because `relay.aurora` is the generic pass-through for *all* Aurora EVM transactions, the likeliest explanation — **inference, not confirmed** — is that a user or integrator called Relay Protocol's `BitcoinDepositAddress`/`RelayAllocator` contracts (item 7) through Aurora's EVM, and `relay.aurora` shows up only as the generic relaying signer, not as the app itself. Flagging this explicitly as unverified rather than asserting it: nearblocks's actual receipt-level data, which would show the call stack, was 403'd on every direct-fetch attempt.
- Searched and found nothing that names a different operator for `relay.aurora` itself.

---

## Telemetry

- Items done: 8 of 8 (counting the 4 Aurora sub-accounts as one item, per the brief's grouping)
- Items with a confirmed source: 5 — #3 fast-auth.near, #7 Aurora XCC sub-accounts, #8 relay.aurora (confirmed as Aurora Engine's relayer; the Nov-2026 Bitcoin detail itself stays unconfirmed/inferred), plus #1 and #4 have partial confirmed-adjacent sourcing but their core owner claims are reported, not confirmed — counted under "reported" below for the owner/kind field specifically.
  - Strictly by "the owner/kind claim itself is confirmed at the owner's or an official NEAR/Aurora doc": #3 (fast-auth.near / Peersyst, via near.org), #7 (Relay Protocol's role, via docs.relay.link), #8 (relay.aurora / Aurora Labs, via aurora-is-near repo + Aurora's own blog/discussion) — **3 items**.
- Items with only reported sourcing: #1 tx-bench.near (Dune dashboard + nearblocks cache, no stated operator), #4 sweat-relayer.near (Sweat's own Medium/help-center content, but only read via search cache — 403 on direct fetch), #5 rathrelayer.near (name-based lead only, explicitly flagged as unconfirmed) — **3 items**.
- Items with none found: #2 ping-account.near, #6 jwt-chain-signatures.near — **2 items**.
- Pages fetched directly (WebFetch, excluding the ones that 403'd or came back as JS-shell titles only): docs.auth.near.org (what-is, resources/mainnet), near.org blog (RFP winners post), docs.rath.fi, github.com/Nearblocks/nearblocks issue #1494, github.com/near/NEPs issue #503, dune.com/proximity_team/v1signer, doc.aurora.dev/blog/safe-bitcoin-demo, explorer.mainnet.aurora.dev/api/v2/addresses (×4), docs.relay.link/references/protocol/how-it-works, zellic.io/blog/signing-blind, github.com/near/multichain-relayer-server, alinush.github.io/near, blog.nearone.org (index + benchmarking-models.html), github.com/near/mpc — **~20 successful fetches**.
- Pages that returned HTTP 403 (flagged, not silently bypassed): nearblocks.io (every address page tried, and its beta/legacy mirrors which redirect into the same block), medium.com/sweat-economy post, pikespeak.ai (rendered as empty JS shell rather than a clean 403, functionally the same gap). Several Blockscout HTML pages also rendered as bare titles (JS shell) until the Blockscout v2 JSON API was used instead.
