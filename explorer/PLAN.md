# The Explorer read: plan

Status: plan, written before any call inside the 90 days. Written 2026-11-13T23:35:16Z.
Last reconciled: 2026-11-13T23:35:16Z.
Known gaps: the rules that put a token ID in a bridge family are fixed in stage 2 (section 6), not here; the API's terms limit what can be published (section 8); nobody without a key can repeat the pull.

## 1. What this is, and what it is not

The five tests of this entry were run on sources that need no account. That left three things out of sight, and `THESIS.md` says so: HOT's flow, the 20 chains with no readable token, and Intents' own swap volume. The hackathon's track names the Intents Explorer API as a source for the third. It needs a key. A key was issued to the author for the hackathon on Nov 13, after the counted read and after the page was written.

This plan uses that key for one descriptive read. It is an addition made after the read:

- It changes no test, no threshold, no interval and no word of the claim. The five tests stay as frozen.
- It is reported whichever way it falls, in a part of the page marked as added after the read, and logged in `AFTER-READ.md`.
- It measures one channel, 1Click swaps, by the API's own records. It does not observe a bridge's custody leg on chain, which the frozen method does.

## 2. Source

`GET https://explorer.near-intents.org/api/v0/transactions` (the NEAR Intents Explorer API; public specification at `https://explorer.near-intents.org/api/v0/openapi.yaml`, linked from docs.near-intents.org). It returns 1Click swap transactions with their status, time, origin and destination asset IDs, deposit and recipient type, and amounts in USD. The limit is one request every 5 seconds.

## 3. Population

Every transaction with status `SUCCESS` and `createdAt` in the 90 days to T0: from 2026-08-12T11:00:00.000Z, included, to 2026-11-10T11:00:00.000Z, not included. T0 is the cutoff of the frozen study.

## 4. How it is read

- The 90 days are cut into 90 blocks of 24 hours, numbered 0 to 89 from the start.
- The blocks are read in a random order fixed now: `random.Random(20261113).sample(range(90), 90)` in Python 3 (`python3 -I explorer/pull.py order` prints it).
- Each block is read whole: pages of 1,000, newest first, following the API's cursor until a page comes back short. Rows are kept only if their time is inside the block, and a row seen twice is counted once. A block whose pages are out of order, or that fails five times on one page, is not counted and is tried once more after the others.
- Requests start at least 5.3 seconds apart. On a 429 the collector waits 30 seconds and widens the gap by half a second; on a 401 or 403 it stops.
- **Stop rule.** The pull ends when all 90 blocks are read, or at 2026-11-14T04:00:00Z: no block is started after that time, and a block in progress at that time is finished and counted. Whether a block is counted therefore depends on the fixed order and on the size of the blocks before it, never on its own contents.
- A block that is not finished is never estimated from the pages that were read.

## 5. What is kept

No transaction row is written to disk. As each block is read, its rows are summed in memory into cells keyed by (origin asset, destination asset, deposit type, recipient type). A cell holds a count, the sum of `amountInUsd`, the sum of `amountOutUsd`, and how many rows had no USD figure on each side. One line per finished block goes to `explorer/data/blocks.jsonl`: the block, its bounds, the number of pages and rows, the SHA-256 of each page as received, and the cells. No address, memo, hash, sender or recipient is kept.

## 6. What is computed (stage 2)

The analysis code is written, hashed and submitted to OpenTimestamps before any cell is read, as the frozen study's was. It will compute:

1. **Withdrawals by bridge family.** Over rows whose recipient type is `DESTINATION_CHAIN`, the sum of `amountOutUsd` by the family of the destination asset, and each family's share. This is the read that sits beside the page's "the part Chain Signatures signs, Omni's withdrawals".
2. **Deposits by bridge family.** Over rows whose deposit type is `ORIGIN_CHAIN`, the sum of `amountInUsd` by the family of the origin asset.
3. **The same two by chain**, so that the 20 chains the keyless sample could not read, and HOT, each get a line.
4. **Total completed 1Click value** over the 90 days and over the 30 days to T0, beside NearStats' 30-day figure that the page already uses.

Families, by the form of the token ID: tokens of the Omni bridge; tokens of the POA bridge; POA-form tokens that the Intents SDK lists as moved to Omni (the 17 on the list already cited in `afterread/NEXT-READS.md`, kept as their own line because that label is the SDK's, not an observation); HOT's tokens; tokens native to NEAR, which cross no bridge; and unclassified. Which ID forms belong to which family is decided from primary sources and written into the stage 2 code before any cell is read. A form no source settles is unclassified, and every share is then given twice, with the unclassified value counted for Omni and against it.

If all 90 blocks are read, the figures are a census of the 90 days and carry no sampling interval. If fewer are read, the finished blocks are a simple random sample of the 90: totals are scaled by 90 over the number read, and each share gets a 95% interval from a bootstrap over blocks (10,000 resamples, seed 20261113, percentile method).

After the pull, three blocks picked with the same seed are read again and compared with the first reading, cell by cell, and the result is reported.

## 7. Expectation, written before the pull

Judgement, not measurement: POA-family tokens carry more than half of 1Click's withdrawal value over the 90 days; the Omni family, with the SDK-listed tokens counted in, carries less than half; HOT carries under 10%. If Omni's side came out above half, that would cut against this entry's reading of T1 for this channel, and the page will say so.

## 8. Limits and the terms

- **One channel.** 1Click swaps are not all of Intents' flow. Nothing here speaks for flows that do not pass through 1Click.
- **Family from the token ID.** A token's ID shows whose token it is, not the leg a given transfer took. The frozen study labels routes from the counterparties of Intents' own legs; this read does not.
- **USD figures are the API's.** They are not re-priced here.
- **Not repeatable without a key.** A reader with their own key can run `explorer/pull.py`; a reader without one can check the arithmetic from `explorer/data/blocks.jsonl` and nothing before it.
- **Terms (graded grey, and named).** The 1Click terms of service (docs.near-intents.org, last updated Oct 7, 2026, as read on Nov 13) bar storing API data for more than 24 hours. This plan therefore keeps no rows at all and publishes only sums by asset pair and day. Whether sums of this kind count as "API data" under those terms is not settled by their text; the track itself names this API as a source for a thesis. The key is the author's and is not in this repository.

## 9. Calls made before this plan was timestamped

All on one 10-minute window outside the 90 days (2026-11-12, 00:00 to 00:10Z), to learn the reply's shape and to test paging:

- one request for the whole window: 128 rows; the asset IDs, deposit and recipient types and the sum of `amountOutUsd` (about $70,000) were printed;
- three requests with pages of 50, by hand, then three more through `pull.py pilot`: the same 128 rows, none twice, newest first;
- one more through `pull.py pilot` on a part of that window, to check that a row at the start time is returned and a row at the end time is not (one of its two requests was refused with a 429 and retried).

No request for any time inside the 90 days was made before the timestamp of this plan.
