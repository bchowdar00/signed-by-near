Seed sweep of the Monte Carlo error in two bootstrap interval ends printed in THESIS.md. It is another session's independent re-derivation code, run after the counted read (2026-11-13); it is not one of the 128 timestamped files, and no test suite imports it.
Run it offline (needs numpy): `python3 -I -B rederive/mc-seeds/sweep.py <repo_dir> <data_dir>`, where `<data_dir>` is the saved sample (it reads `nb/windows.jsonl` and `nb/pages/`).
Expected: `sweep.json` with sha256 `0b078f1a5fe3717b3bca80b8b4c22f58df32bfc2db5f7e933defa4056ea7b4e7`.
