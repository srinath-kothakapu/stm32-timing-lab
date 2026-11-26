import json
import math

import numpy as np
import pytest

from stm32timing import analysis, parse, report
from stm32timing.__main__ import main
from stm32timing.synth import synth_lines

TICK_NS = 1e9 / 84e6


# ---------------------------------------------------------------- parsing


def test_unwrap_u32_across_wrap():
    raw = np.array([2**32 - 100, 2**32 - 10, 5, 2**31, 2**32 - 1, 3])
    u = parse.unwrap_u32(raw)
    assert list(np.diff(u)) == [90, 15, 2**31 - 5, 2**31 - 1, 4]


def test_parse_header_capture_status_and_garbage():
    lines = [
        "# note=bench test",
        "0,12,3",  # half line from attaching mid-transmission
        "H,1,uid=00A1B2C3,target=F411RE,clk=HSE,ftim=84000000,ref=1000",
        "C,0,100,25,0",
        "C,1,84100,27,1",
        "C,2,abc,1,0",  # corrupt
        "C,3,168100,26",  # truncated
        "S,seq=4,drop=0,ovc=1",
    ]
    run = parse.parse_lines(lines)
    assert run.header["uid"] == "00A1B2C3"
    assert run.header["ftim"] == 84_000_000
    assert run.meta["note"] == "bench test"
    assert list(run.seq) == [0, 1]
    assert list(run.ticks) == [100, 84100]
    assert list(run.flags) == [0, 1]
    assert run.status[-1] == {"seq": 4, "drop": 0, "ovc": 1}
    assert run.bad_lines == 3


def test_parse_requires_header():
    with pytest.raises(ValueError, match="no header"):
        parse.parse_lines(["C,0,1,2,0"])


def test_parse_rejects_mixed_boards():
    lines = synth_lines(n=10, uid="AAAA0001") + synth_lines(n=10, uid="BBBB0002")
    with pytest.raises(ValueError, match="several boards"):
        parse.parse_lines(lines)


def test_parse_reset_keeps_longest_segment():
    first = synth_lines(n=50)
    second = [l for l in synth_lines(n=200, seed=2) if l.startswith("C,")]
    run = parse.parse_lines(first + second)
    assert run.segments == 2
    assert len(run) == 200


def test_firmware_and_host_agree_on_line_format():
    # exact strings produced by firmware/test/test_main.c
    run = parse.parse_lines(
        ["H,1,uid=00A1B2C3,target=F411RE,clk=HSE,ftim=84000000,ref=1000", "C,123,4294967295,27,1", "S,seq=10,drop=0,ovc=3"]
    )
    assert run.ticks[0] == 4294967295 and run.lat[0] == 27 and run.flags[0] == 1 and run.bad_lines == 0


# ---------------------------------------------------------------- analysis


def _analyze(**kw):
    return analysis.analyze(parse.parse_lines(synth_lines(**kw)), kw.get("ref_hz", 1000.0))


def test_synchronous_reference_has_zero_jitter():
    # loopback case: reference derived from the same clock as the timer,
    # 84 MHz / 1 kHz = exactly 84000 ticks every period, no quantisation noise
    r = _analyze(n=20000)
    assert r.ppm == 0.0 or abs(r.ppm) < 1e-9
    assert r.period_ns.std == 0.0
    assert r.missing_cycles == 0 and r.glitch_edges == 0


def test_asynchronous_ideal_reference_is_at_quantization_floor():
    # independent clocks: the edge phase walks through the tick, periods are N or N+1 ticks
    r = _analyze(n=20000, ppm=3.7)
    assert r.period_ns.pk_pk <= TICK_NS * 1.001
    assert r.period_ns.std < r.quantization_floor_ns * 1.25
    assert r.period_ns.std > 0


@pytest.mark.parametrize("ppm", [-37.5, 12.3, 250.0, -8000.0])
def test_frequency_offset_recovered(ppm):
    r = _analyze(n=20000, ppm=ppm, jitter_ns=10)
    assert r.ppm == pytest.approx(ppm, abs=0.05)
    assert r.ppm_ci95 < 0.05
    # accumulated drift = ppm * duration
    assert r.drift_total_us == pytest.approx(ppm * r.duration_s, rel=0.01, abs=0.05)


def test_gaussian_jitter_recovered():
    r = _analyze(n=50000, jitter_ns=50.0)
    # period = difference of two independently jittered edges -> sqrt(2) * sigma, plus quantisation
    expected = math.sqrt(2 * 50.0**2 + r.quantization_floor_ns**2)
    assert r.period_ns.std == pytest.approx(expected, rel=0.03)
    # cycle-to-cycle of white edge jitter: sqrt(6) * sigma
    assert r.c2c_ns.std == pytest.approx(math.sqrt(6) * 50.0, rel=0.05)


def test_dropped_lines_do_not_bias_offset():
    r = _analyze(n=20000, ppm=42.0, drop_every=97)
    assert r.missing_cycles == 20000 // 97
    assert r.ppm == pytest.approx(42.0, abs=0.01)
    assert r.period_ns.pk_pk <= TICK_NS * 1.001  # periods spanning a gap are excluded


def test_glitch_edges_are_rejected():
    r = _analyze(n=5000, ppm=5.0, glitch_at=(100, 2000, 4000))
    assert r.glitch_edges == 3
    assert r.ppm == pytest.approx(5.0, abs=0.02)
    assert r.period_ns.pk_pk <= TICK_NS * 1.001


def test_counter_wrap_mid_run():
    # start 2 s before the 32-bit wrap, run 10 s at 1 kHz
    r = _analyze(n=10000, ppm=-20.0, start_ticks=2**32 - 2 * 84_000_000)
    assert r.ppm == pytest.approx(-20.0, abs=0.01)
    assert r.duration_s == pytest.approx(10.0, rel=1e-3)


def test_wrong_ref_hz_is_reported():
    run = parse.parse_lines(synth_lines(n=1000, ref_hz=1000))
    with pytest.raises(ValueError, match="check --ref-hz"):
        analysis.analyze(run, 500.0)


def test_latency_in_ns():
    r = _analyze(n=2000, lat_ticks=(24, 24))
    assert r.latency_ns.mean == pytest.approx(24 * TICK_NS)
    assert r.latency_ticks.min == r.latency_ticks.max == 24


def test_adev_white_phase_noise_slope():
    # white PM: sigma_y(tau) ~ 1/tau
    r = _analyze(n=40000, ref_hz=1000.0, jitter_ns=100.0)
    taus, devs = np.array(r.adev_tau_s), np.array(r.adev)
    slope = np.polyfit(np.log10(taus), np.log10(devs), 1)[0]
    assert slope == pytest.approx(-1.0, abs=0.1)
    assert r.adev_1s is not None


def test_adev_constant_offset_is_removed():
    a = _analyze(n=20000, ppm=0.0, seed=3)
    b = _analyze(n=20000, ppm=100.0, seed=3)
    # a pure frequency offset does not change the Allan deviation (only quantisation remains)
    assert b.adev[-1] < 1e-8
    assert b.adev[-1] == pytest.approx(a.adev[-1], rel=0.5)


def test_compare_two_boards():
    a = _analyze(n=20000, ppm=15.0, uid="AAAA0001")
    b = _analyze(n=20000, ppm=-6.0, seed=7, uid="BBBB0002")
    c = analysis.compare(a, b)
    assert c.ppm_a_minus_b == pytest.approx(21.0, abs=0.02)
    assert "Different boards" in c.note


# ---------------------------------------------------------------- report / CLI


def test_report_files(tmp_path):
    r = _analyze(n=5000, ppm=3.0, jitter_ns=20)
    md = report.write_report(r, tmp_path / "rep", "E0 synthetic")
    text = md.read_text()
    assert "Period jitter, 1σ" in text and "ppm" in text
    for f in ("period_hist.png", "drift.png", "tie.png", "adev.png", "latency_hist.png", "summary.json"):
        assert (tmp_path / "rep" / f).stat().st_size > 0
    js = json.loads((tmp_path / "rep" / "summary.json").read_text())
    assert js["ppm"] == pytest.approx(3.0, abs=0.05)
    assert "pk_pk" in js["period_ns"]


def test_cli_analyze_and_compare(tmp_path):
    a = tmp_path / "a.log"
    b = tmp_path / "b.log"
    a.write_text("\n".join(synth_lines(n=3000, ppm=10, uid="AAAA0001")))
    b.write_text("\n".join(synth_lines(n=3000, ppm=-10, seed=5, uid="BBBB0002")))
    assert main(["analyze", str(a), "--ref-hz", "1000", "--out", str(tmp_path / "ra")]) == 0
    assert (tmp_path / "ra" / "results.md").exists()
    assert main(["compare", str(a), str(b), "--ref-hz", "1000", "--out", str(tmp_path / "cmp")]) == 0
    assert "+20.0" in (tmp_path / "cmp" / "comparison.md").read_text()
    assert main(["analyze", str(tmp_path / "missing.log")]) == 2


def test_load_gzip(tmp_path):
    import gzip

    p = tmp_path / "run.log.gz"
    with gzip.open(p, "wt") as f:
        f.write("\n".join(synth_lines(n=500, ppm=1.0)))
    run = parse.load(p)
    assert len(run) == 500
