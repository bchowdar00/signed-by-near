# For judges and screening agents

Status: written after the counted read; not one of the timestamped files. Known gaps: the re-pull (`verify.py check`) has not been timed since the read; 36 of the 526 windows did not finish, and every reading that rests on one is marked "not completed".

The home page says previous NEAR hackathons "evaluated technical implementation, design, impact, originality and sustainability — a good guide to prepare by". This file takes those five in turn: what this entry offers on each, and the file or command that shows it. Nothing here is a new claim about NEAR: every reading is in `THESIS.md` and is rebuilt by the two commands below. The counts of tests and files describe this repo.

## What to run first

Offline, Python 3 standard library only, no key, no install.

| Do | See | Takes |
|---|---|---|
| `sh check.sh` | The rows below down to the manifests, in one command, with the Explorer read's offline checks. It stops at the first step that fails; its last line starts `ALL OK` | about three minutes |
| `cp -R out out-committed` | A copy of the committed outputs, to compare with | at once |
| `python3 -I rebuild.py data --draft` | The sha256 of each file it wrote; `out/published/tables.md` reads `cd05cf5f…afdd76` | a few seconds |
| `python3 -I publish/written.py data` | A last line starting `ok:` with the sha256 of `THESIS.md`, equal to `shasum -a 256 THESIS.md` on the committed file | a few seconds |
| `python3 -I publish/same_out.py out-committed out` | `ok: 6 files are the same bytes, and 3 results files are equal up to the order of M7/pairs` | at once |
| `python3 -I -m unittest discover -s publish` | `Ran 59 tests`, `OK` | about a minute and a half |
| `H=$(mktemp -d) && mkdir -p "$H/Data/hackathons/near-2026/b-collect/pilot" && cp tests/fixtures/stage1-local/rates-plan-draft.json "$H/Data/hackathons/near-2026/b-collect/pilot/" && HOME="$H" python3 -I -m unittest discover -s tests` | `Ran 149 tests`, `OK (skipped=2)`. Two frozen tests read a draft pilot file from the home folder; this gives them the shipped copy in a temporary one. Without it a clone ends `FAILED (errors=2, skipped=2)` (`DEVIATIONS.md`) | about 20 seconds |
| `python3 -I publish/selftest_written.py data` | `ok: 2 planted faults caught` | a few seconds |
| `shasum -a 256 -c postfreeze/MANIFEST-postfreeze.txt` | 16 lines, each `OK` | at once |
| `shasum -a 256 -c data/MANIFEST-data.txt` | 773 lines, each `OK`: the saved rows (`data/README.md`) | at once |
| `shasum -a 256 -c deadline/MANIFEST-deadline.txt` | 4 lines, each `OK` | at once |
| `python3 -I rederive/run.py data` (needs numpy) | A last line reading `49 rows agree, recomputed by code; 0 checked against a source file; 7 need a source file not shipped; 6 not recomputed; 1 differ`: a second implementation's numbers against the published ones | about 15 seconds |
| `shasum -a 256 -c afterread/MANIFEST-afterread.txt` | 2 lines, each `OK`: the dated next reads, stamped after the read and before publication | at once |

Three results files (`out/results.json`, `out/published/results.json`, `out/combined.json`) get a different sha256 on every run: the frozen code builds one list, `M7/pairs`, by looping over a set, and Python orders a set differently in each process. Every reading in them is the same, which `publish/same_out.py` checks by sorting that list. The tables, the charts, `THESIS.md` and `docs/` are the same bytes on every run; `README.md` lists their sha256.

Then open `docs/index.html`: what was fixed and when, the five tests, the 28 chains one by one, and each chart with its query.

## The five criteria

| Criterion | What this entry offers | Where to check |
|---|---|---|
| Technical implementation | A sampling design, the analysis code and five tests, hashed on Nov 10 and held in a Bitcoin block of that day, before any analysis read a collected row. The stop at the deadline and the rule for readings not completed, stamped on Nov 13 before the first read. Four manifests in all (128 lines for 95 distinct paths), each with an OpenTimestamps receipt. A fifth, also stamped after the sample was collected and before it was first read, holds the claim's sentence and the holder's read. Intervals on every estimate. A rule, also stamped before the read, for readings whose windows did not finish: they are masked, never drawn. A check that every count the page states in words matches the results, with a self-test that plants a wrong count and a masked reading. A second implementation, written after the read by AI sessions told not to read the analysis code or any result, recomputes 553 of the 570 numbers it compares from a clone and finds them equal (bootstrap ends within a stated tolerance); the 2 that differ are explained, and its seed sweeps show how far two interval ends move. | `METHOD.md`, `frozen/`, `deadline/`, `postfreeze/`, `preread/` (manifests and `.ots` receipts); `publish/check_thesis.py`; `publish/selftest_written.py`; `POST-FREEZE.md` and `AFTER-READ.md` for the receipts' Bitcoin blocks; `rederive/README.md`, `rederive/RESULTS.md`, `rederive/mc-seeds/` (need numpy) |
| Design | The write-up leads with the answer and one table of the five tests, each as what was needed against what was found; its results are in the order of the tests, each opening with its verdict; and it says in three dated lines what was fixed when. The dashboard is static, has no script, loads nothing from elsewhere, and shows each chart with its query and one sentence; it and the write-up as a page (`docs/thesis.html`) are set in one dark look, in which the charts are recoloured copies that differ from the timestamped charts in the style block only. Readings not completed are labelled, not interpolated. | `THESIS.md`, "Summary" and section 3.4; `docs/index.html`; `TABLE-NOTES.md` |
| Impact | It tests two public claims about NEAR's cross-chain reach, a partner's "28-chain moat" and the NEAR blog's sentences on Bitcoin and Solana flow, and says for a NEAR holder where the moat sits. The result cuts both ways: the Bitcoin sentence holds on chain; breadth beyond Bitcoin is not shown; and the page names the weak point of its own "moving to Omni" reading. | `THESIS.md`: sections 1, 4.1, 4.2, 4.5 and 4.6, section 6 ("What this means for a NEAR holder") and section 5 ("Evidence against this reading") |
| Originality | The question. It measures three things the public dashboards do not show: the share of Intents' flow by bridge route, which apps are behind the signer's calls (a public dashboard charts callers by raw account; here the login service's calls are attributed to the app behind them, with intervals), and what NEAR pays per signature. The tests and the claim's sentence were in Bitcoin blocks before any counted result was read, so the result could have gone against the author and the reader can verify the order. The page says what the author had already seen in an uncounted pilot. A destination audit follows 20 sampled withdrawals to Bitcoin and Zcash explorers. | `THESIS.md` sections 4.2, 4.3 and 4.4; `preread/`, `frozen/MANIFEST-stage1.txt.ots`; `audit/dest-audit.md` |
| Sustainability | Anyone can re-pull the sample without a key and check it against the published rows. The method is fixed in one file and can be re-run at a later cutoff. The write-up lists the readings that would change its conclusion, and three of them are dated: January 2027 for adoption without Sweat, October's payout for cost, and the next complete Solana and Zcash sample for breadth, each with its threshold and this entry's expectation, timestamped before publication so the entry can be marked right or wrong. | `python3 -I verify.py check frozen/instants.json data` (network; a seeded sample of 20 windows); `METHOD.md`; `THESIS.md`, section 7 ("What would change my mind": the tests in full, then the next reads); `afterread/NEXT-READS.md` |

## What this entry does not do

- It gives no price target and no valuation.
- It does not measure chains whose flow these public sources cannot read: 16 of the 28 are shown by their documented route only.
- It does not establish whether SOL or ZEC moved to Omni: the before-and-after comparison could not be made for them, because windows it rests on did not finish before the deadline.
- Its five tests do not use BigQuery or the Intents Explorer API, which the track suggests: both need a sign-up. `README.md` says what is used instead. The Explorer API was read in one pull after the counted read, with a key issued on Nov 13, as a marked addition that changes no test (`THESIS.md` §4.8, `explorer/PLAN.md`). It covers every completed 1Click swap the API returned for the 90 days and puts Omni's side of the bridged withdrawal value under half; a second implementation gives the same figures (`rederive/explorer/`).
- The dashboard, this file and `afterread/` were made after the counted read. `AFTER-READ.md` lists everything that was. Nothing in `afterread/` changes a test result.
