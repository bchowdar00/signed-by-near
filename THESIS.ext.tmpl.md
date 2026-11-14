<!-- Blocks that publish/fill.py puts in THESIS.md at each `<!-- extension:NAME -->` line of THESIS.tmpl.md:
     the "ran" part if an extension pass ran (combined.json → extension.ran), else the "not ran" part.
     Every number here comes from a placeholder under "extension"; the text outside them has no digit. -->

<!-- block migration -->
<!-- ran -->
**A secondary reading: the {{extension/label::str}}.** It does not replace the table above, which stays as frozen. The pass re-read only the windows the counted run had not completed, under a plan written and timestamped before the deadline, and it is shown whatever it shows (`POST-FREEZE.md`). Migration windows completed after it: {{extension/results/completeness/migration/completed::int}} of {{extension/results/rule/windows_by_family/migration::int}}. A series with a window still unfinished reads "not completed".

| series | early | late, to the cutoff | reading |
|---|---|---|---|
| SOL | {{extension/results/M10/SOL/readings/amount/early::iv1}} | {{extension/results/M10/SOL/readings/amount/late::iv1}} | {{extension/results/M10/SOL/verdict::str}} |
| ZEC | {{extension/results/M10/ZEC/readings/amount/early::iv1}} | {{extension/results/M10/ZEC/readings/amount/late::iv1}} | {{extension/results/M10/ZEC/verdict::str}} |
| BTC | {{extension/results/M10/BTC/readings/amount/early::iv1}} | {{extension/results/M10/BTC/readings/amount/late::iv1}} | {{extension/results/M10/BTC/verdict::str}} |
| ETH (a POA control) | {{extension/results/M10/ETH (POA control)/readings/amount/early::iv1}} | {{extension/results/M10/ETH (POA control)/readings/amount/late::iv1}} | {{extension/results/M10/ETH (POA control)/verdict::str}} |

Of the {{rule/n_masked_readings::int}} readings not completed at the deadline, the pass completed {{extension/n_readings_completed::int}}; every value that differs from the primary reading is listed in `out/combined.json`.
<!-- not ran -->
No pass ran after the deadline. A series whose early or late windows were not all completed at the deadline reads "not completed" above, with no interval (`POST-FREEZE.md`).
<!-- end -->

<!-- block callers -->
<!-- ran -->
**The same chart from the secondary reading** ({{extension/label::str}}). Signer windows completed after it: {{extension/results/completeness/sign/completed::int}} of {{extension/results/rule/windows_by_family/sign::int}}.

![Who calls the signer: the secondary reading](out-ext/published/chart2-callers-cost.svg)
<!-- not ran -->
<!-- end -->
