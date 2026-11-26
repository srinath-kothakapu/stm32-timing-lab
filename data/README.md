# Raw capture logs

One file per board per experiment, written by `python -m stm32timing capture`:
`<experiment>_<label>.log`, e.g. `e3_ref_hse_A.log`.

Commit logs gzip-compressed (`gzip data/*.log` → `.log.gz`); the analysis reads both.
Raw `.log` files are git-ignored. Every number in `docs/REPORT.md` must be reproducible
from a file in this folder with `python -m stm32timing analyze <file>`.
