"""Generated capture logs with known jitter, offset and gaps, used by the tests.

These are not measurements. They let the tests check that the analysis gets the
right answer when the true values are known.
"""

from __future__ import annotations

import numpy as np


def synth_lines(
    n: int = 20000,
    ref_hz: float = 1000.0,
    ftim: int = 84_000_000,
    ppm: float = 0.0,
    jitter_ns: float = 0.0,
    drop_every: int = 0,
    glitch_at: tuple = (),
    start_ticks: int = 0,
    lat_ticks: tuple = (24, 30),
    seed: int = 1,
    uid: str = "5EED0001",
    clk: str = "HSE",
    target: str = "SYNTH",
    wander_ppm: float = 0.0,
    sync: bool = False,
) -> list[str]:
    """Edge timestamps as a board running ``ppm`` fast would record them.

    wander_ppm: size of a random-walk frequency wander (ppm per sqrt(second)).
    sync: reference derived from the board's own clock (loopback), periods exact.
    """
    rng = np.random.default_rng(seed)
    if sync:
        nominal = int(round(ftim / ref_hz))
        ticks = (np.arange(n, dtype=np.int64) * nominal + start_ticks + 1234) % (1 << 32)
        lat = rng.integers(lat_ticks[0], lat_ticks[1] + 1, n)
        lines = ["# synthetic=1", f"H,1,uid={uid},target={target},clk={clk},ftim={ftim},ref={int(ref_hz)}"]
        lines += [f"C,{i},{int(ticks[i])},{lat[i]},0" for i in range(n)]
        lines.append(f"S,seq={n},drop=0,ovc=0")
        return lines
    true_s = np.arange(n) / ref_hz + rng.normal(0.0, jitter_ns * 1e-9, n)
    rate = 1.0 + ppm * 1e-6
    if wander_ppm:
        dt = 1.0 / ref_hz
        y = np.cumsum(rng.normal(0.0, wander_ppm * 1e-6 * np.sqrt(dt), n))  # fractional frequency
        extra = np.concatenate(([0.0], np.cumsum(y[:-1]) * dt))  # integrated phase in seconds
        true_s = true_s + extra
    ticks_f = true_s * ftim * rate + rng.uniform(0, 1)  # random phase vs the timer
    ticks = (np.floor(ticks_f).astype(np.int64) + start_ticks) % (1 << 32)
    lat = rng.integers(lat_ticks[0], lat_ticks[1] + 1, n)
    lines = ["# synthetic=1", f"H,1,uid={uid},target={target},clk={clk},ftim={ftim},ref={int(ref_hz)}"]
    seq = 0
    for i in range(n):
        if i in glitch_at:
            g = (int(ticks[i]) + int(0.3 * ftim / ref_hz)) % (1 << 32)
            lines.append(f"C,{seq},{int(ticks[i])},{lat[i]},0")
            seq += 1
            lines.append(f"C,{seq},{g},{lat[i]},0")
            seq += 1
            continue
        if drop_every and i % drop_every == drop_every - 1:
            seq += 1  # firmware assigned a seq but the line never arrived
            continue
        lines.append(f"C,{seq},{int(ticks[i])},{lat[i]},0")
        seq += 1
    lines.append(f"S,seq={seq},drop=0,ovc=0")
    return lines
