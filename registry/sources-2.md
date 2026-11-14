# Caller-class sources, batch 2

Public-web research only. nearblocks.io address pages returned HTTP 403 on every direct fetch attempt in this session (confirmed on acc.ref-labs.near, kernel-usdc.meteor-vaults.near, meteor-vaults.near, passivefund.near, and usdt.meteor-vaults.near/fr); web.archive.org fetches are also blocked for this tool. Where a nearblocks label is cited below it comes from a search-engine snippet of an indexed nearblocks page, not a direct read — flagged as **reported** and lower-confidence than the brief's "fine to read" assumption anticipated. This is a tooling limitation, not an improvisation; flagging per the stop-and-report rule.

---

## 1. btc-connector.bridge.near, zcash-connector.bridge.near, omni-relayer.bridge.near

- **Owner/app:** NEAR Omni Bridge (the cross-chain bridge connecting NEAR to Bitcoin, Zcash, Ethereum, Solana and others).
- **Kind:** bridge infrastructure (connector contracts for BTC/ZEC + the relayer that finalizes transfers).
- **Builder:** Near One. Confirmed as the entity behind NEAR's protocol/chain-abstraction R&D via NEAR Foundation's own blog: "the Pagoda team developing the core NEAR blockchain protocol is now Near One" — [near.org blog](https://www.near.org/blog/ecosystem-update-announcing-near-one-chain-abstraction-spinouts) (confirmed, official). The GitHub org "Near-One" owns the `omni-bridge`, `btc-bridge`, `bridge-sdk-rs` and `bridge-sdk-js` repos; the org bio itself gives no self-description.
- **Sources:**
  - **confirmed** — Near-One's own repo names the account directly: "Ready refunds on btc-connector.bridge.near can sit unexecuted for weeks after their lock ends." [Near-One/btc-bridge issue #96](https://github.com/Near-One/btc-bridge/issues/96)
  - **confirmed** — Aurora Labs' own docs name the relayer account: "Transaction will be finalized automatically for you by omni-relayer.bridge.near account on the NEAR side." [doc.aurora.dev Omni Bridge tutorial](https://doc.aurora.dev/blog/omnibridge-tutorial/) (footer: "© 2026 Aurora Labs")
  - **confirmed** — official NEAR docs describe the mechanism generally (does not name the specific accounts): "It solves key challenges in cross-chain communication by leveraging Chain Signatures," listing Bitcoin and Zcash as "Light client + Chain Signatures." [docs.near.org Omni Bridge Overview](https://docs.near.org/chain-abstraction/omnibridge/overview)
  - **reported** — a third-party privacy review names zcash-connector.bridge.near and omni-relayer.bridge.near specifically: "The wrapped ZEC is burned through the Zcash connector zcash-connector.bridge.near," and "The multisig or omni-relayer.bridge.near can reject the refund until then." [ethbeat.org Zcash/NEAR Intents review](https://ethbeat.org/privacy/projects/zcash-near-intents) (no listed author; independent review site, not Near One's own)

---

## 2. kernel-usdc.meteor-vaults.near, kernel-usdt.meteor-vaults.near, kernel-zec.meteor-vaults.near, kernel-near.meteor-vaults.near

- **Owner/app:** Meteor Wallet, operated through its sister company **Dew Finance** (yield-vault product; "Meteor Savings").
- **Kind:** production app (multichain yield vaults), using Chain Signatures and Shade Agents per the owner's own announcement.
- **Builder:** independent team — Meteor Wallet / Dew Finance (not NEAR Foundation, Near One, Defuse Labs, Proximity Labs or Aurora).
- **Sources:**
  - **confirmed** — Dew Finance's own statement on a public forum: "we are partner of RHEA Finance and we are the team of meteor wallet in NEAR Protocol." [Zcash Community Forum, Dew Finance reply](https://forum.zcashcommunity.com/t/zcash-vault-by-dew-finance-8-apy/55900)
  - **confirmed** — NEAR Protocol's own official account describes why Chain Signatures would be used: "Introducing Dew Finance, our sister company, designed to enhance yield opportunities through multichain compatibility, powered by NEAR Intent, Chain Signature and Shade Agent." [@NEARProtocol post](https://x.com/NEARProtocol/status/1968000555059679594)
  - **reported** (search-snippet only, not independently read) — a sibling account on the same root is indexed by nearblocks as "Meteor Savings USDT," created by meteor-vaults.near, per a search-engine snippet of `nearblocks.io/fr/address/usdt.meteor-vaults.near` (direct fetch returned 403).
  - **"kernel" naming:** not confirmed anywhere. No source — Dew Finance's own posts, NEAR's post, or any search — uses the word "kernel" for these vaults. The four account names are a lead only: they plausibly follow the same `<asset>.meteor-vaults.near` pattern as the confirmed `usdt.meteor-vaults.near`, just under a "kernel" sub-brand I could not find documented. Flagging per the rule against guessing from the name alone.

---

## 3. acc.ref-labs.near

- **Owner (namespace):** Ref Finance, now rebranded **RHEA Finance**. Confirmed rebrand: "In 2025, Ref Finance merged with Burrow, the lending protocol on NEAR, and rebranded as RHEA Finance." [guide.rhea.finance/history](https://guide.rhea.finance/history) (confirmed, owner's own guide).
- **ref-labs.near as Ref's namespace:** found only via search-engine summary of Ref's own contracts guide (direct fetch of `guide.ref.finance` and `docs.ref.finance` both failed with DNS errors — the domain may have moved since the RHEA rebrand). The summary quotes Ref's guide listing `boostfarm.ref-labs.near` (Farming), `ref-ve.ref-labs.near` (veTokenomics) and `dclv2.ref-labs.near` (Concentrated Liquidity) as official contracts — **reported**, since I could not load the primary page myself.
- **acc.ref-labs.near specifically:** NOT named in that contracts list, and NOT confirmed as a Ref/RHEA-owned account by any source read. It appears only as the parent suffix for Bitcoin-wallet-mapped NEAR accounts (format `<btc-address>.acc.ref-labs.near`) in third-party bug reports against a separate project: "Mainnet BTC-mapped NEAR account cannot send assets" — **reported**, [Near-Bridge-Lab/satoshi-wallet issue #96](https://github.com/Near-Bridge-Lab/satoshi-wallet/issues/96). That issue describes "a same-chain NEAR transfer, not a BTC bridge withdrawal," and says the account holds "one secp256k1 FULL_ACCESS key," but does not name Chain Signatures, v1.signer, or confirm Ref/RHEA as the operator of this specific sub-account — it only shares the `ref-labs.near` parent name. The `Near-Bridge-Lab` GitHub org (which owns `satoshi-wallet`, `btc-bridge` fork, `satoshi-bridge-sdk`) has no public bio and no stated members, so I cannot confirm its relationship to Ref/RHEA from the org page itself.
- **Chain Signatures use:** not confirmed for this account. Inferred only (not stated) from the general pattern that BTC-wallet-mapped NEAR accounts with a FULL_ACCESS secp256k1 key are typically signed via Chain Signatures elsewhere in the NEAR ecosystem (e.g., BitHive, item 6). Flagging as inference, not a source-backed claim.
- **Net:** the owner of the `ref-labs.near` parent namespace is confirmed as Ref/RHEA Finance (reported-tier primary source), but the specific `acc.ref-labs.near` account's purpose and operator are not confirmed at a primary source — only a name-pattern lead plus third-party bug reports.

---

## 4. Trezu

- **What it is:** an open-source, non-custodial multisig treasury-management platform for NEAR DAOs. Repo About section: "Frontend and back-end for Trezu." [NEAR-DevHub/trezu](https://github.com/NEAR-DevHub/trezu) (confirmed, repo's own page)
- **Builder:** **Near Dev Inc**, per a NEAR Forum discussion citing Trezu's own Terms of Use as naming Near Dev Inc as the interface developer/maintainer, with the public code hosted under the NEAR-DevHub GitHub org and funded by a NearDevHub grant — [NEAR Forum thread](https://gov.near.org/t/trezu-for-near-storage-security-team-audits-and-real-user-experiences/42679) (reported: forum post describing the Terms of Use, not the Terms of Use itself).
- **NEAR account(s) calling v1.signer:** not a single fixed account. A GitHub issue describing Trezu's own backend code says: Trezu's confidential setup "files a `v1.signer.sign` proposal, votes it and takes the MPC signature" (citing Trezu's own source file `nt-be/src/handlers/treasury/confidential_setup.rs`) — **reported**, [MultiAgency/platform issue #13](https://github.com/MultiAgency/platform/issues/13) (a different repo discussing/quoting Trezu's code, not Trezu's own issue tracker). This means each customer treasury's own Sputnik DAO account is the caller, routed through proposal/vote, not a single Trezu-controlled signer account. The same issue names two specific DAOs in this context: `agentic.sputnik-dao.near` (described as "the mainnet DAO that owns the platform's staging agent") and `council.sputnik-dao.near` (the e2e-test DAO).
- Separately, `sponsor.trezu.near` is a known Trezu-controlled account (a storage-deposit sponsor account, subject of a drain-exploit bug report), but it is not described as a v1.signer caller — [NEAR-DevHub/trezu issue #1871](https://github.com/NEAR-DevHub/trezu/issues/1871).

---

## 5. v0.shadeagent.near, v1.shadeagent.near, ac-sandbox.shadeainexa.near

- **Framework builder:** **Proximity Labs**. Confirmed via Proximity Labs' own announcement: "Say hello to Shade Agents: The First Truly Autonomous AI Agents 🕶️ Shade Agents are multichain, verifiable AI agents capable of signing transactions, managing assets, and executing financial workflows onchain." [@proximityfi post](https://x.com/proximityfi/status/1892637998560195004) (confirmed, owner's own account). The open-source framework repo sits under the `NearDeFi` GitHub org; that repo page does not itself name Proximity Labs as maintainer.
- **v0.shadeagent.near:** confirmed as a **demo/example** account, not production. NearDeFi's own repo for shade-agent-twitter: "This repository is an example of a Shade Agent" — a worker agent that scores tweet sentiment and mints tokens, live as @shadeagent007 on X, using "account_id: v0.shadeagent.near, path: shadeagent007" for its Chain Signatures call. [NearDeFi/shade-agent-twitter](https://github.com/NearDeFi/shade-agent-twitter) (confirmed, builder's own repo).
- **v1.shadeagent.near:** none found. No search or page located this account; it is a naming-pattern lead only (v0 → v1), not source-backed. Searches tried: `"v1.shadeagent.near"`, general Shade Agent searches.
- **ac-sandbox.shadeainexa.near:** none found. The string "shadeainexa" returns zero relevant results in web search — no project, repo, or account by that name turned up. Searches tried: `"ac-sandbox.shadeainexa.near"`, `"shadeainexa" NEAR`. Given the "sandbox" in the name and zero search footprint, this reads as a staging/sandbox account by name only — unconfirmed.
- **Status flag (stop-and-report item):** as of November 2026 the official NEAR docs team is removing the Shade Agents page — PR title "docs: remove Shade Agents" — [near/docs PR #3165](https://github.com/near/docs/pull/3165) (confirmed, repo's own PR, opened by a near/docs maintainer, dated Nov 3 2026). The framework repo itself also warns: "This technology has not yet undergone a formal audit," per search-engine summary of [NearDeFi/shade-agent-framework](https://github.com/NearDeFi/shade-agent-framework) (reported — not independently re-read in full). Flagging because this materially changes "kind" classification going forward: Shade Agents may be winding down as an officially supported NEAR framework even though Proximity Labs still promotes it.

---

## 6. stg1.btchive0.near, bithive-staging.near

- **BitHive builder:** **Allstake**. GitHub org bio: "Omnichain Restaking, Trustless Scaling." [github.com/allstake](https://github.com/allstake) (confirmed, org's own page). BitHive's own repo: "BitHive is a native staking protocol for Bitcoin." [allstake/bithive](https://github.com/allstake/bithive) (confirmed, repo's own README).
- **stg1.btchive0.near and bithive-staging.near specifically:** none found. Neither the BitHive repo, its architecture docs (docs.bithive.fi — direct fetch failed with a DNS error in this tool), the Allstake org page, nor any web search surfaced these two account names. Searches tried: `"stg1.btchive0.near" OR "bithive-staging.near"`, `bithive.near BitHive NEAR bitcoin staking`. Given BitHive's confirmed ownership and the plain "staging" wording in one of the names, treating these as BitHive staging/sandbox accounts is a plausible read of the name alone, but it is NOT source-confirmed — flagged per the no-guessing rule.

---

## 7. rri.sputnik-dao.near

- **What it is:** a DAO instance on the Sputnik DAO v2 factory (the standard `<name>.sputnik-dao.near` pattern). No source found that says what "rri" stands for or who its members/owners are.
- **Tied to an app:** yes, tied to **Trezu**. It appears in Trezu's own issue tracker, in a bug report about Trezu's confidential-ledger accounting: the issue gives `rri.sputnik-dao.near` as one of several affected DAO treasuries and notes "third-party inbound confidential deposits are invisible since the balance-snapshot poller was removed." [NEAR-DevHub/trezu issue #1891](https://github.com/NEAR-DevHub/trezu/issues/1891) (confirmed as Trezu's own repo naming this DAO as one of its platform's treasuries; the issue does not say whether it is Trezu's own operating DAO or a customer's).
- Searches tried beyond the above: `rri.sputnik-dao.near` (general), `nearblocks.io/address/sputnik-dao.near` context pages (general factory docs only, no "rri"-specific hit).

---

## 8. passivefund.near

- **None found.** No repo, doc, blog, forum post, or indexed explorer snippet names this account or describes an app/organization behind it.
- Searches tried: `passivefund.near NEAR`, `"passivefund.near" nearblocks OR github OR twitter`, `passivefund near protocol vault strategy fund`.
- Pages tried: direct nearblocks.io address page (403 Forbidden, could not read on-chain label).
- This is a stop-and-report item in the sense that I have nothing beyond the bare name — treat as "unknown" per the brief, not as a guess.

---

## Telemetry

- Items done: 8 / 8
- Items with at least one confirmed source: 7 (items 1, 2, 3 [owner only], 4, 5 [builder + v0 account], 6 [builder only], 7 [DAO-Trezu tie])
- Items with only reported sources for their core claim: 0 full items, but several sub-claims are reported-only (item 2's "kernel" naming, item 3's acc.ref-labs.near specifics, item 4's signer-account detail, item 5's v1/ac-sandbox accounts, item 6's staging-account names)
- Items with none found: 1 (item 8, passivefund.near), plus three sub-items inside others (v1.shadeagent.near, ac-sandbox.shadeainexa.near, stg1.btchive0.near/bithive-staging.near, and the "rri" meaning)
- Pages fetched (WebFetch calls, including failures): 35 attempted; 13 failed outright (nearblocks.io 403 ×5, docs.bithive.fi DNS ×2, guide.ref.finance / docs.ref.finance DNS ×2, web.archive.org unsupported ×2, docs.near.org/ai/shade-agents 404, proximity.dev/shadeagents 404)
