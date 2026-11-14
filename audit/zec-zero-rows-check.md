# Zcash picks in the destination audit: the 0-zat rows

Written 2026-11-13T11:07Z, after the first counted read. The input is the audit's saved lookups only (repo/audit/raw/zcash-*.json and repo/audit/dest-audit.json); two pages of mainnet.zcashexplorer.app were fetched to cross-check. No NearBlocks call was made, and no file the manifest lists was touched.

## What the saved Blockchair records show (confirmed, recomputed from the raw files)

Each row is compared against its own pick's signer address (dest_address). There are 5 distinct signer addresses across the 10 picks.

| tx | bytes | in from signer | in from others | out to signer | out to others | transparent in − out |
|---|---|---|---|---|---|---|
| 5c8991c34b82 | 6192 | 10,047,820,241 | 0 | 10,045,742,951 | 0 | 2,077,290 |
| 79828474f4d2 | 242 | 22,822,685,712 | 0 | 22,822,274,767 | 400,945 | 10,000 |
| 9f80a7d279c1 | 6192 | 22,817,361,079 | 0 | 22,815,636,999 | 0 | 1,724,080 |
| a0e0bb381bc3 | 242 | 22,648,291,965 | 0 | 22,647,292,404 | 989,561 | 10,000 |
| 74bd9e36c001 | 6339 | 392,500 | 739,000,000 | 0 | 465,908,354 | 273,484,146 |
| 56f0af944a9c | 6192 | 4,635,408,345 | 0 | 4,535,386,345 | 0 | 100,022,000 |
| 9ce1d8e51584 | 537 | 150,000,000 | 3,596,100,000 | 0 | 3,746,085,000 | 15,000 |
| a22bb65d440a | 6192 | 5,900,000,000 | 0 | 0 | 5,480,726,376 | 419,273,624 |
| e490f63ba8b3 | 6338 | 1,000,000 | 22,500,000 | 0 | 22,510,000 | 990,000 |
| 2a7f2c53f045 | 6338 | 22,510,000 | 25,700,000 | 30,787,498 | 0 | 17,422,502 |

Values are in zat. Every record is version 6, with shielded_value_delta 0 and no Sprout or Sapling fields.

- The three transparent-only transactions (242–537 bytes) have in − out of 10,000–15,000 zat, which is a fee.
- The other seven are 6,192–6,339 bytes, roughly 25 times the size of a plain transparent transaction, and lose 990,000–419,273,624 zat between their transparent inputs and outputs.
- The four rows the audit shows as "0 zat to other addresses" (5c8991c3, 9f80a7d2, 56f0af94, 2a7f2c53) are all among those seven. Their only transparent output goes back to the signer's own address.

## Cross-check on a second explorer (reported, from the pages as fetched at about 11:1xZ)

- mainnet.zcashexplorer.app, tx 5c8991c3…: version 6; "Transaction fee" "0.0001 ZEC"; one transparent input and one output, both the signer's address; "Orchard Action transfers" "0"; "Transferred from/to shielded pool" "0.0 ZEC". Its own input and output leave 0.0207729 ZEC unexplained.
- The same explorer, tx a22bb65d…: version 6; fee "0.0001 ZEC"; a 59.0 ZEC input and a 54.80726376 ZEC output; no shielded parts shown. It leaves about 4.19 ZEC unexplained.

## Reading

**Confirmed:** in seven of the ten Zcash picks, value leaves the transparent view: 990,000–419,273,624 zat, against a stated fee of 0.0001 ZEC (10,000 zat). Neither explorer shows where that value goes.

**Likely, not confirmed:** the transactions carry a version-6 component that neither Blockchair's v2 record nor zcashexplorer.app decodes, most plausibly a shielded bundle. The size fits shielded proofs. Settling it needs a decoder for the v6 format, or a node.

**For the write-up:**
- The four 0-zat rows mean the payout is not visible on the transparent chain. They do not mean nothing was paid.
- "To other addresses" is not always "to the user": in 74bd9e36, 9ce1d8e5, a22bb65d and e490f63b, an output goes to another of the signer's own addresses.
- In 74bd9e36, 9ce1d8e5, e490f63b and 2a7f2c53, most of the inputs come from addresses outside the five signer addresses. "Spent from the signer's address" is true for all ten, but in 74bd9e36 the signer's address supplied only 392,500 of 739,392,500 zat.

**Separately, the picks cluster in time** (counted by script from `audit/dest-audit.json`). Bitcoin: 7 of the 10 share one confirmation time, 2026-09-01T04:24:28Z, so they sit in one block; the 10 span 3 times. Zcash: the 10 span 8 times, all on Oct 13 or Nov 4, with 3 at 2026-10-13T15:43:30Z.
