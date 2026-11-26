"""Synthetic capture logs with known properties - FOR TESTS ONLY.

Nothing generated here is a measurement. It exists so the analysis code can be
checked against inputs whose true jitter / offset / drift are known exactly.
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
) -> list[str]:
    """Edge timestamps as a board running ``ppm`` fast would record them."""
    rng = np.random.default_rng(seed)
    true_s = np.arange(n) / ref_hz + rng.normal(0.0, jitter_ns * 1e-9, n)
    ticks_f = true_s * ftim * (1.0 + ppm * 1e-6) + rng.uniform(0, 1)  # random phase vs the timer
    ticks = (np.floor(ticks_f).astype(np.int64) + start_ticks) % (1 << 32)
    lat = rng.integers(lat_ticks[0], lat_ticks[1] + 1, n)
    lines = [f"# synthetic=1", f"H,1,uid={uid},target=SYNTH,clk={clk},ftim={ftim},ref={int(ref_hz)}"]
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
