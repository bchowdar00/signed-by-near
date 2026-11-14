# The saved rows

Status: the sample this entry's numbers are computed from, exactly as the two commands in `README.md` read it: 773 files, 15 MB, collected between 2026-11-10T11:52Z and 2026-11-13T00:00Z. This folder was added to the repo on 2026-11-13, after the counted read. It is in no timestamped manifest: the manifests fix the method, the list of windows and the code, not the rows. `MANIFEST-data.txt` lists each file's sha256 as published. Known gaps: 36 of the 526 planned windows did not finish before the deadline, so they have no complete set of pages here; one of the 3,951 neardata block requests got no answer and is recorded as such.

## What each file is

| Path | Files | What it is | Where it came from |
|---|---|---|---|
| `nb/pages/<window>/<segment>-<page>.json` | 746, in 491 window folders | One page of one request, as answered. Each file records the request it answers (`path`), when it was made (`utc`), the HTTP status (`http`) and the rows returned. The collector drops only the paging metadata (`collector/sampler.py`, `slim`). | NearBlocks' public API, `https://api.nearblocks.io/v3` + `path`, keyless |
| `nb/txns/<hash>.json` | 19 | One transaction's token transfers, read whole, for the seeded audit of 20 included transactions. | NearBlocks' public API, `/v3/txns/{hash}/fts` |
| `nb/windows.jsonl`, `nb/resolve.jsonl`, `nb/RESOLVED` | 3 | The collector's own ledger: which windows finished, with how many pages and rows; the audit's picks; the mark that the audit phase ended. | written by `collector/sampler.py` |
| `nd/blocks.jsonl`, `nd/DONE` | 2 | 3,951 sampled blocks, each with the `v1.signer` calls found in it. | `https://mainnet.neardata.xyz/v0/block/{height}`, keyless |
| `rpc/supply.jsonl`, `rpc/operators.jsonl`, `rpc/DONE` | 3 | Token total supplies at monthly points (48 answers) and the signer's node operators at 9 points. | FastNEAR's archival RPC, `https://archival-rpc.mainnet.fastnear.com`, keyless |

The NearBlocks requests are of four kinds, and every page file names its own:

| Request | Pages |
|---|---|
| `/fts/{token}/txns` (a token's transfers) | 415 |
| `/accounts/v1.signer/receipts?method=sign` (the signer's `sign` calls) | 253 |
| `/accounts/{account}/ft-txns?involved=intents.near` (a bridge account's transfers with Intents) | 67 |
| `/multichain/signatures` | 11 |

## Credit

Powered by Nearblocks.io APIs. The files under `nb/pages/` and `nb/txns/` are NearBlocks' answers to the requests named in them, made between 2026-11-10 and 2026-11-12; the original and current data is at https://nearblocks.io and `https://api.nearblocks.io`. They are published here as the sample behind this entry's numbers, so that anyone can recompute them. If NearBlocks asks for these files to be removed, they will be removed: open an issue on this repository.

Blocks are from neardata.xyz (FastNEAR). Supplies and operator sets are from FastNEAR's archival RPC.

## Check and reuse

- `shasum -a 256 -c data/MANIFEST-data.txt`, run from the repo's root, checks all 773 files.
- `python3 -I verify.py check frozen/instants.json data` re-pulls a seeded sample of 20 windows from NearBlocks and compares them with these files (network, keyless).
- Without this folder, the tests and the manifest checks in `README.md` still run, and the committed `out/`, `THESIS.md` and `docs/` can be read as they are. Recomputing needs the rows; `collector/sampler.py` can pull them again, keyless, over three days or more.
