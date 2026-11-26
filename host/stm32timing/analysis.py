"""Timing statistics from a captured run.

Terminology used throughout (all times in the board's own timebase):

* **period** - time between consecutive reference edges.
* **period jitter** - standard deviation / peak-to-peak of the periods.
* **cycle-to-cycle jitter** - std of the difference between adjacent periods.
* **frequency offset (ppm)** - from a least-squares fit of edge time against
  cycle index. Positive means the board clock runs *fast* relative to the
  reference (it counts more ticks per reference period than nominal).
* **phase error / accumulated drift** - edge time minus ``k * nominal_period``;
  how far the board's notion of time walks away from the reference.
* **TIE** (time interval error) - edge time minus the *fitted* line, i.e. what
  is left after removing the constant frequency offset (jitter + wander).
* **ADEV** - overlapping Allan deviation of fractional frequency, computed
  from the phase error.
* **ISR latency** - TIM2 count read at ISR entry minus the hardware capture
  value. It does not affect the timestamps (they are latched by hardware) but
  shows how quickly software can react to the edge.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np

from .parse import Run

GLITCH_TOLERANCE = 0.10  # an interval must be within 10 % of a whole number of periods


@dataclass
class Stats:
    mean: float
    std: float
    min: float
    max: float
    p50: float
    p99: float
    p999: float

    @property
    def pk_pk(self) -> float:
        return self.max - self.min

    @classmethod
    def of(cls, x: np.ndarray) -> "Stats":
        x = np.asarray(x, dtype=np.float64)
        if x.size == 0:
            nan = float("nan")
            return cls(nan, nan, nan, nan, nan, nan, nan)
        return cls(
            mean=float(x.mean()),
            std=float(x.std(ddof=1)) if x.size > 1 else 0.0,
            min=float(x.min()),
            max=float(x.max()),
            p50=float(np.percentile(x, 50)),
            p99=float(np.percentile(x, 99)),
            p999=float(np.percentile(x, 99.9)),
        )


@dataclass
class Result:
    source: str
    board_uid: str
    target: str
    clock: str
    ftim_hz: int
    ref_hz: float
    tick_ns: float
    n_edges: int
    duration_s: float
    missing_cycles: int  # reference periods with no captured edge (dropped / lost)
    glitch_edges: int  # edges that did not fall on a whole period (noise, ringing)
    overcaptures: int
    fw_dropped: int
    bad_lines: int
    segments: int
    period_ns: Stats
    period_dev_ns: Stats  # period minus nominal
    c2c_ns: Stats
    quantization_floor_ns: float  # expected period std from timer resolution alone
    ppm: float
    ppm_ci95: float
    drift_total_us: float  # accumulated phase error at the end of the run
    tie_ns: Stats
    latency_ns: Stats
    latency_ticks: Stats
    adev_tau_s: list = field(default_factory=list)
    adev: list = field(default_factory=list)
    adev_1s: float | None = None
    warnings: list = field(default_factory=list)
    # bulky series for plotting (not serialised)
    t_s: np.ndarray | None = field(default=None, repr=False)
    phase_ns: np.ndarray | None = field(default=None, repr=False)
    tie_series_ns: np.ndarray | None = field(default=None, repr=False)
    periods_series_ns: np.ndarray | None = field(default=None, repr=False)
    latency_series_ns: np.ndarray | None = field(default=None, repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("t_s", "phase_ns", "tie_series_ns", "periods_series_ns", "latency_series_ns"):
            d.pop(k, None)
        for k in ("period_ns", "period_dev_ns", "c2c_ns", "tie_ns", "latency_ns", "latency_ticks"):
            d[k]["pk_pk"] = getattr(self, k).pk_pk
        return d


def cycle_index(t: np.ndarray, nominal: float) -> tuple[np.ndarray, np.ndarray]:
    """Assign each edge a reference-cycle index from the time since the previous kept edge.

    Returns (keep_mask, k). Edges whose interval is not close to a whole number
    of nominal periods are treated as glitches and dropped. Robust to missing
    edges and to frequency offsets far larger than any crystal or RC (< 10 %).
    """
    n = t.size
    keep = np.ones(n, dtype=bool)
    k = np.zeros(n, dtype=np.int64)
    if n < 2:
        return keep, k
    r = np.diff(t) / nominal
    m = np.rint(r)
    ok = (m >= 1) & (np.abs(r - m) <= GLITCH_TOLERANCE)
    if ok.all():
        k[1:] = np.cumsum(m.astype(np.int64))
        return keep, k
    # slow path: walk edges, measuring each interval from the last *kept* edge
    last_t, last_k = t[0], 0
    for i in range(1, n):
        ri = (t[i] - last_t) / nominal
        mi = round(ri)
        if mi >= 1 and abs(ri - mi) <= GLITCH_TOLERANCE:
            last_k += mi
            last_t = t[i]
            k[i] = last_k
        else:
            keep[i] = False
    return keep, k


def overlapping_adev(x_s: np.ndarray, tau0_s: float, ms: list[int]) -> tuple[list, list]:
    """Overlapping Allan deviation from phase data x (seconds) sampled every tau0."""
    taus, devs = [], []
    n = x_s.size
    for m in ms:
        if m < 1 or 2 * m >= n:
            continue
        d = x_s[2 * m :] - 2.0 * x_s[m:-m] + x_s[: -2 * m]
        tau = m * tau0_s
        taus.append(tau)
        devs.append(float(math.sqrt(np.mean(d * d) / (2.0 * tau * tau))))
    return taus, devs


def _adev_ms(n: int, ref_hz: float) -> list[int]:
    ms = set()
    for dec in range(0, 9):
        for mult in (1, 2, 5):
            ms.add(mult * 10**dec)
    one_s = int(round(ref_hz))  # tau = 1 s
    keep = {m for m in ms if m <= n // 4}
    if one_s >= 1 and 2 * one_s < n:
        keep.add(one_s)
    return sorted(keep)


def _longest_run(mask: np.ndarray) -> tuple[int, int]:
    """[lo, hi) of the longest run of True values."""
    best = (0, 0)
    start = None
    for i, v in enumerate(np.append(mask, False)):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start > best[1] - best[0]:
                best = (start, i)
            start = None
    return best


def analyze(run: Run, ref_hz: float | None = None) -> Result:
    if len(run) < 10:
        raise ValueError(f"{run.source}: only {len(run)} edges captured - is the reference connected to PA0?")
    warnings: list[str] = []
    ftim = run.ftim_hz
    tick_ns = 1e9 / ftim
    if ref_hz is None:
        ref_hz = float(run.header.get("ref", 0)) or None
        if not ref_hz:
            raise ValueError("reference frequency unknown: pass ref_hz")
        warnings.append(
            f"Nominal reference frequency taken from the firmware header ({ref_hz:g} Hz). "
            "Pass --ref-hz if the reference came from another source."
        )
    nominal = ftim / ref_hz

    t_all = run.ticks - run.ticks[0]
    med = float(np.median(np.diff(t_all)))
    if abs(med / nominal - 1) > 0.05:
        raise ValueError(
            f"median edge interval {med * tick_ns / 1e3:.3f} us does not match the nominal "
            f"{nominal * tick_ns / 1e3:.3f} us ({ref_hz:g} Hz). Actual reference is about "
            f"{ftim / med:.3f} Hz - check --ref-hz."
        )

    keep, k_all = cycle_index(t_all.astype(np.float64), nominal)
    glitches = int((~keep).sum())
    t = t_all[keep].astype(np.float64)
    k = k_all[keep]
    lat = run.lat[keep]
    missing = int(k[-1] - (k.size - 1))

    dk = np.diff(k)
    dt = np.diff(t)
    periods = dt[dk == 1]
    period_ns = periods * tick_ns

    # frequency offset: least-squares line t = a + b*k (centred for conditioning)
    kc = k - k.mean()
    b, a = np.polyfit(kc, t, 1)
    resid = t - (a + b * kc)
    ppm = (b / nominal - 1.0) * 1e6
    # 95 % CI of the slope (white residuals assumption - optimistic if wander dominates)
    dof = max(k.size - 2, 1)
    se_b = math.sqrt(float(np.sum(resid**2)) / dof / float(np.sum(kc**2)))
    ppm_ci = 1.96 * se_b / nominal * 1e6

    phase_ns = (t - k * nominal) * tick_ns
    tie_ns = resid * tick_ns

    # Allan deviation on the longest stretch without missing cycles
    lo, hi = _longest_run(np.append(dk == 1, False))
    seg = phase_ns[lo : hi + 1] * 1e-9 if hi > lo else np.zeros(0)
    taus, devs = overlapping_adev(seg, 1.0 / ref_hz, _adev_ms(seg.size, ref_hz))
    adev_1s = None
    for tau, dev in zip(taus, devs):
        if abs(tau - 1.0) < 1e-9:
            adev_1s = dev

    if glitches:
        warnings.append(f"{glitches} edges did not land on a whole reference period and were ignored (noise/ringing on PA0?).")
    if missing:
        warnings.append(f"{missing} reference cycles had no captured edge (UART overflow or lost edges).")
    ovc = int(np.count_nonzero(run.flags & 1))
    if ovc:
        warnings.append(f"{ovc} over-capture events: edges arrived faster than the ISR could read them.")
    fw_drop = int(run.status[-1].get("drop", 0)) if run.status else 0
    if run.segments > 1:
        warnings.append(f"Board reset during the log ({run.segments} segments); analysed the longest one.")
    if run.bad_lines > 5:
        warnings.append(f"{run.bad_lines} unparseable lines (serial noise or wrong baud rate?).")

    qfloor = tick_ns / math.sqrt(6.0)
    return Result(
        source=run.source,
        board_uid=str(run.header.get("uid", "?")),
        target=str(run.header.get("target", "?")),
        clock=str(run.header.get("clk", "?")),
        ftim_hz=ftim,
        ref_hz=float(ref_hz),
        tick_ns=tick_ns,
        n_edges=int(k.size),
        duration_s=float(t[-1] / ftim),
        missing_cycles=missing,
        glitch_edges=glitches,
        overcaptures=ovc,
        fw_dropped=fw_drop,
        bad_lines=run.bad_lines,
        segments=run.segments,
        period_ns=Stats.of(period_ns),
        period_dev_ns=Stats.of(period_ns - nominal * tick_ns),
        c2c_ns=Stats.of(np.diff(period_ns)),
        quantization_floor_ns=qfloor,
        ppm=float(ppm),
        ppm_ci95=float(ppm_ci),
        drift_total_us=float(phase_ns[-1] / 1e3),
        tie_ns=Stats.of(tie_ns),
        latency_ns=Stats.of(lat * tick_ns),
        latency_ticks=Stats.of(lat),
        adev_tau_s=taus,
        adev=devs,
        adev_1s=adev_1s,
        warnings=warnings,
        t_s=t / ftim,
        phase_ns=phase_ns,
        tie_series_ns=tie_ns,
        periods_series_ns=period_ns,
        latency_series_ns=lat * tick_ns,
    )


@dataclass
class Comparison:
    a: Result
    b: Result
    ppm_a_minus_b: float
    ppm_ci95: float
    note: str


def compare(a: Result, b: Result) -> Comparison:
    """Compare two boards that captured the same reference at the same time.

    Each board's ppm is relative to the reference, so the reference's own error
    cancels in the difference: ppm_a - ppm_b is the offset between the two
    board clocks, independent of how good the reference is.
    """
    if a.board_uid == b.board_uid:
        note = "Both logs come from the same board (same UID) - this compares two runs, not two boards."
    else:
        note = "Different boards. If both captured the same reference simultaneously, the reference error cancels."
    return Comparison(
        a=a,
        b=b,
        ppm_a_minus_b=a.ppm - b.ppm,
        ppm_ci95=math.hypot(a.ppm_ci95, b.ppm_ci95),
        note=note,
    )
