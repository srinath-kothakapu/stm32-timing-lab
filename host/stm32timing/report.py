"""Write plots, a JSON summary and a Markdown results section for a run."""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .analysis import Comparison, Result  # noqa: E402


def _fmt(x: float, nd: int = 2) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x:.{nd}f}"


_WATERMARK: str | None = None


def set_watermark(text: str | None) -> None:
    """Stamp every following plot with text (used for the simulated demo)."""
    global _WATERMARK
    _WATERMARK = text


def _save(fig, path: Path) -> str:
    fig.tight_layout()
    if _WATERMARK:
        fig.text(0.5, 0.5, _WATERMARK, fontsize=34, color="grey", alpha=0.25,
                 ha="center", va="center", rotation=20, transform=fig.transFigure)
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path.name


def plots(r: Result, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    files = {}

    fig, ax = plt.subplots(figsize=(7, 3.5))
    dev = r.periods_series_ns - r.ref_hz**-1 * 1e9
    lo, hi = np.floor(dev.min() / r.tick_ns), np.ceil(dev.max() / r.tick_ns)
    bins = np.arange(lo - 0.5, hi + 1.5) * r.tick_ns  # one bin per timer tick
    if bins.size > 400:
        bins = 200
    ax.hist(dev, bins=bins, color="#3b6ea8")
    ax.set_yscale("log")
    ax.set_xlabel("period - nominal [ns]  (bin = 1 timer tick)")
    ax.set_ylabel("count")
    ax.set_title(f"Period deviation, {r.n_edges} edges, 1σ = {r.period_ns.std:.1f} ns")
    files["period_hist"] = _save(fig, out / "period_hist.png")

    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(r.t_s, r.phase_ns / 1e3, lw=0.8, color="#a83b3b", label="phase error vs nominal")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("accumulated time error [µs]")
    ax.set_title(f"Drift: {r.ppm:+.3f} ppm, {r.drift_total_us:+.2f} µs after {r.duration_s:.0f} s")
    ax.grid(alpha=0.3)
    files["drift"] = _save(fig, out / "drift.png")

    fig, ax = plt.subplots(figsize=(7, 3.5))
    step = max(1, r.t_s.size // 20000)
    ax.plot(r.t_s[::step], r.tie_series_ns[::step], lw=0.5, color="#3ba86e")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("TIE after removing offset [ns]")
    ax.set_title(f"Time interval error, pk-pk {r.tie_ns.pk_pk:.0f} ns (jitter + wander)")
    ax.grid(alpha=0.3)
    files["tie"] = _save(fig, out / "tie.png")

    if r.adev and max(r.adev) > 0:
        fig, ax = plt.subplots(figsize=(5.5, 4))
        ax.loglog(r.adev_tau_s, r.adev, "o-", color="#6e3ba8")
        ax.set_xlabel("τ [s]")
        ax.set_ylabel("Allan deviation σ_y(τ)")
        ax.set_title("Overlapping Allan deviation")
        ax.grid(which="both", alpha=0.3)
        files["adev"] = _save(fig, out / "adev.png")

    fig, ax = plt.subplots(figsize=(7, 3.5))
    lat_t = r.latency_series_ns / r.tick_ns
    ax.hist(r.latency_series_ns, bins=np.arange(lat_t.min() - 0.5, lat_t.max() + 1.5) * r.tick_ns, color="#a8873b")
    ax.set_yscale("log")
    ax.set_xlabel("ISR entry latency [ns]  (edge -> first TIM2->CNT read)")
    ax.set_ylabel("count")
    ax.set_title(f"Interrupt latency, mean {r.latency_ns.mean:.0f} ns, max {r.latency_ns.max:.0f} ns")
    files["latency"] = _save(fig, out / "latency_hist.png")
    return files


def markdown(r: Result, files: dict, title: str | None = None) -> str:
    title = title or Path(r.source).stem
    p, t, la = r.period_ns, r.tie_ns, r.latency_ns
    lines = [
        f"## {title}",
        "",
        f"Source log: `{r.source}`  ",
        f"Board: {r.target}, UID `{r.board_uid}`, clock **{r.clock}**, timer {r.ftim_hz / 1e6:g} MHz "
        f"(1 tick = {r.tick_ns:.3f} ns)  ",
        f"Reference: {r.ref_hz:g} Hz nominal, {r.n_edges} edges over {r.duration_s:.1f} s",
        "",
        "| Quantity | Value |",
        "|---|---|",
        f"| Period jitter, 1σ | {_fmt(p.std)} ns |",
        f"| Period jitter, peak-to-peak | {_fmt(p.pk_pk, 1)} ns ({_fmt(p.pk_pk / r.tick_ns, 0)} ticks) |",
        f"| Cycle-to-cycle jitter, 1σ | {_fmt(r.c2c_ns.std)} ns |",
        f"| Timer quantisation floor (tick/√6) | {_fmt(r.quantization_floor_ns)} ns |",
        f"| Frequency offset vs reference | {r.ppm:+.3f} ppm (±{r.ppm_ci95:.2g}, 95 %) |",
        f"| Accumulated drift at end of run | {r.drift_total_us:+.2f} µs after {r.duration_s:.1f} s |",
        f"| TIE (offset removed), peak-to-peak | {_fmt(t.pk_pk, 1)} ns |",
        f"| Allan deviation at τ = 1 s | {('%.2e' % r.adev_1s) if r.adev_1s is not None else 'n/a'} |",
        f"| ISR latency mean / p99.9 / max | {_fmt(la.mean, 0)} / {_fmt(la.p999, 0)} / {_fmt(la.max, 0)} ns |",
        f"| ISR latency in ticks (min..max) | {r.latency_ticks.min:.0f} .. {r.latency_ticks.max:.0f} |",
        f"| Missing cycles / glitch edges / over-captures | {r.missing_cycles} / {r.glitch_edges} / {r.overcaptures} |",
        "",
    ]
    if p.std == 0:
        lines += [
            f"_Every period is exactly {r.ftim_hz / r.ref_hz:.0f} ticks: the reference is synchronous with "
            "the capture timer (expected when a board measures its own output)._",
            "",
        ]
    elif p.pk_pk <= r.tick_ns * 1.001:
        lines += [
            "_Periods differ by at most one timer tick: the result is limited by the "
            f"{r.tick_ns:.1f} ns timer resolution, and the true jitter of the reference is below that._",
            "",
        ]
    if r.warnings:
        lines += ["**Warnings**", ""] + [f"- {w}" for w in r.warnings] + [""]
    for key, label in (
        ("period_hist", "Period deviation histogram"),
        ("drift", "Accumulated time error"),
        ("tie", "Time interval error"),
        ("adev", "Allan deviation"),
        ("latency", "ISR latency histogram"),
    ):
        if key in files:
            lines.append(f"![{label}]({files[key]})")
    lines.append("")
    return "\n".join(lines)


def write_report(r: Result, out_dir: str | Path, title: str | None = None) -> Path:
    out = Path(out_dir)
    files = plots(r, out)
    (out / "summary.json").write_text(json.dumps(r.to_dict(), indent=2))
    md = out / "results.md"
    md.write_text(markdown(r, files, title))
    return md


def write_comparison(c: Comparison, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 3.5))
    for r, name in ((c.a, "A"), (c.b, "B")):
        ax.plot(r.t_s, r.phase_ns / 1e3, lw=0.8, label=f"{name}: {r.target} {r.board_uid} {r.clock} ({r.ppm:+.3f} ppm)")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("accumulated time error [µs]")
    ax.set_title("Two boards against the same reference")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    img = _save(fig, out / "compare_drift.png")
    rows = [
        "## Board comparison",
        "",
        "| | Board A | Board B |",
        "|---|---|---|",
        f"| Log | `{c.a.source}` | `{c.b.source}` |",
        f"| Target / UID / clock | {c.a.target} / `{c.a.board_uid}` / {c.a.clock} | {c.b.target} / `{c.b.board_uid}` / {c.b.clock} |",
        f"| Duration | {c.a.duration_s:.1f} s | {c.b.duration_s:.1f} s |",
        f"| Offset vs reference | {c.a.ppm:+.3f} ppm | {c.b.ppm:+.3f} ppm |",
        f"| Period jitter 1σ | {c.a.period_ns.std:.2f} ns | {c.b.period_ns.std:.2f} ns |",
        f"| ISR latency mean / max | {c.a.latency_ns.mean:.0f} / {c.a.latency_ns.max:.0f} ns | {c.b.latency_ns.mean:.0f} / {c.b.latency_ns.max:.0f} ns |",
        "",
        f"**Offset A − B: {c.ppm_a_minus_b:+.3f} ppm (±{c.ppm_ci95:.2g}, 95 %)** - "
        f"the two clocks separate by {abs(c.ppm_a_minus_b) * 3.6:.1f} ms per hour.",
        "",
        f"_{c.note}_",
        "",
        f"![Drift of both boards]({img})",
        "",
    ]
    md = out / "comparison.md"
    md.write_text("\n".join(rows))
    return md
