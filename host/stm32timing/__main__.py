"""Command line: python -m stm32timing {capture,analyze,compare} ..."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import analysis, parse, report


def _cmd_capture(a: argparse.Namespace) -> int:
    from .capture import record

    record(a.port, a.seconds, a.out, a.name, a.baud, a.note)
    return 0


def _cmd_analyze(a: argparse.Namespace) -> int:
    run = parse.load(a.log)
    r = analysis.analyze(run, a.ref_hz)
    out = Path(a.out) if a.out else Path("reports") / Path(a.log).name.split(".")[0]
    md = report.write_report(r, out, a.title)
    print(md.read_text())
    print(f"written: {md}")
    return 0


def _cmd_compare(a: argparse.Namespace) -> int:
    ra = analysis.analyze(parse.load(a.log_a), a.ref_hz)
    rb = analysis.analyze(parse.load(a.log_b), a.ref_hz)
    c = analysis.compare(ra, rb)
    out = Path(a.out) if a.out else Path("reports") / f"compare_{Path(a.log_a).stem}_{Path(a.log_b).stem}"
    report.write_report(ra, out / "A")
    report.write_report(rb, out / "B")
    md = report.write_comparison(c, out)
    print(md.read_text())
    print(f"written: {md}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="stm32timing", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("capture", help="record raw logs from one or more boards")
    c.add_argument("--port", action="append", required=True, help="serial port, optionally PORT:label; repeat for several boards")
    c.add_argument("--seconds", type=float, default=600)
    c.add_argument("--baud", type=int, default=460800)
    c.add_argument("--out", default="data")
    c.add_argument("--name", required=True, help="experiment name, e.g. e1_loopback")
    c.add_argument("--note", default="", help="free text stored in the log (wiring, generator settings, temperature)")
    c.set_defaults(fn=_cmd_capture)

    z = sub.add_parser("analyze", help="statistics, plots and a Markdown results section for one log")
    z.add_argument("log")
    z.add_argument("--ref-hz", type=float, default=None, help="nominal reference frequency (default: from firmware header)")
    z.add_argument("--out", default=None)
    z.add_argument("--title", default=None)
    z.set_defaults(fn=_cmd_analyze)

    m = sub.add_parser("compare", help="compare two boards that captured the same reference")
    m.add_argument("log_a")
    m.add_argument("log_b")
    m.add_argument("--ref-hz", type=float, default=None)
    m.add_argument("--out", default=None)
    m.set_defaults(fn=_cmd_compare)

    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
