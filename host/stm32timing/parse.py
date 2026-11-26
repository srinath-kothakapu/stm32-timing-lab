"""Parse raw capture logs written by ``stm32timing capture``.

Log format (one line per record, see firmware/src/common/proto.h)::

    # key=value                                     capture metadata (host side)
    H,1,uid=1A2B3C4D,target=F411RE,clk=HSE,ftim=84000000,ref=1000
    C,<seq>,<ticks>,<lat>,<flags>
    S,seq=<n>,drop=<n>,ovc=<n>

Anything else (e.g. a half line from attaching mid-transmission) is counted
and ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np

U32 = 1 << 32


@dataclass
class Run:
    """One continuous capture from one board."""

    header: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    seq: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int64))
    ticks: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int64))
    lat: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int64))
    flags: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int64))
    status: list = field(default_factory=list)
    bad_lines: int = 0
    segments: int = 1  # >1 means the board reset during the log; the longest segment is kept
    source: str = ""

    @property
    def ftim_hz(self) -> int:
        return int(self.header["ftim"])

    def __len__(self) -> int:
        return len(self.ticks)


def unwrap_u32(values: np.ndarray) -> np.ndarray:
    """Unwrap a sequence of free-running uint32 counter values into int64.

    Assumes consecutive samples are less than 2**32 counts apart
    (51.1 s at 84 MHz).
    """
    v = np.asarray(values, dtype=np.int64)
    if v.size == 0:
        return v
    d = np.diff(v) % U32
    out = np.empty_like(v)
    out[0] = v[0]
    out[1:] = v[0] + np.cumsum(d)
    return out


def _parse_kv(fields: Iterable[str]) -> dict:
    out = {}
    for f in fields:
        if "=" in f:
            k, v = f.split("=", 1)
            v = v.strip()
            out[k.strip()] = int(v) if v.isdigit() else v
    return out


def parse_lines(lines: Iterable[str], source: str = "") -> Run:
    run = Run(source=source)
    headers: list[dict] = []
    seq, ticks, lat, flags = [], [], [], []

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            run.meta.update(_parse_kv([line[1:].strip()]))
            continue
        parts = line.split(",")
        tag = parts[0]
        try:
            if tag == "C" and len(parts) == 5 and all(p.isdigit() for p in parts[1:]):
                s, t, la, fl = (int(p) for p in parts[1:])
                if s >= U32 or t >= U32 or la > 0xFFFF or fl > 0xFF:
                    raise ValueError
                seq.append(s)
                ticks.append(t)
                lat.append(la)
                flags.append(fl)
            elif tag == "H" and len(parts) >= 3 and parts[1] == "1":
                h = _parse_kv(parts[2:])
                if not {"uid", "ftim"} <= h.keys():
                    raise ValueError
                headers.append(h)
            elif tag == "S" and len(parts) >= 2:
                run.status.append(_parse_kv(parts[1:]))
            else:
                raise ValueError
        except ValueError:
            run.bad_lines += 1

    if not headers:
        raise ValueError(f"{source or 'log'}: no header line (H,...) found - is this a capture log?")
    uids = {h["uid"] for h in headers}
    if len(uids) > 1:
        raise ValueError(f"{source}: log mixes data from several boards: {sorted(uids)}")
    run.header = headers[-1]

    seq_a = unwrap_u32(np.array(seq, dtype=np.int64)) if seq else np.zeros(0, np.int64)
    # A firmware reset restarts seq at 0: split there and keep the longest segment.
    # (A genuine uint32 wrap of seq - after 49 days at 1 kHz - jumps from near 2**32.)
    raw_seq = np.array(seq, dtype=np.int64)
    if raw_seq.size > 1:
        d = np.diff(raw_seq)
        back = np.nonzero((d < 0) & ~((d < -(U32 >> 1)) & (raw_seq[:-1] > U32 - (1 << 20))))[0]
        if back.size:
            bounds = np.concatenate(([0], back + 1, [raw_seq.size]))
            lengths = np.diff(bounds)
            i = int(np.argmax(lengths))
            lo, hi = bounds[i], bounds[i + 1]
            run.segments = len(lengths)
            seq, ticks, lat, flags = seq[lo:hi], ticks[lo:hi], lat[lo:hi], flags[lo:hi]
            seq_a = unwrap_u32(np.array(seq, dtype=np.int64))

    run.seq = seq_a
    run.ticks = unwrap_u32(np.array(ticks, dtype=np.int64)) if ticks else np.zeros(0, np.int64)
    run.lat = np.array(lat, dtype=np.int64)
    run.flags = np.array(flags, dtype=np.int64)
    return run


def load(path: str | Path) -> Run:
    """Load a .log or gzip-compressed .log.gz capture."""
    path = Path(path)
    if path.suffix == ".gz":
        import gzip

        with gzip.open(path, "rt", encoding="ascii", errors="replace") as f:
            return parse_lines(f, source=str(path))
    with path.open("r", encoding="ascii", errors="replace") as f:
        return parse_lines(f, source=str(path))
