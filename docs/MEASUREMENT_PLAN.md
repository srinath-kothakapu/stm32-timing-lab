# Measurement plan

Each experiment produces one raw log per board in `data/` and a generated results section in
`reports/`. Record the context in `--note` (wiring, generator settings, room temperature,
how long the board had been powered) so each run can be explained later.

General rules:

- Power the boards for **≥ 10 minutes** before a frequency measurement (warm-up drift).
- Keep the boards out of drafts and off warm surfaces; note the room temperature.
- Default run: 1 kHz reference, **600 s** (600 000 edges). For GPS PPS: 1 Hz, ≥ 1800 s.
- After each run: `gzip data/<name>_*.log` and commit the `.log.gz` files together with the report.

Find the serial ports with `python -m serial.tools.list_ports` (Windows: `COMx`, Linux: `/dev/ttyACMx`).

---

## E1 — Loopback self-test (validates the whole chain)

**Wiring:** board A, PA6 (D12) → PA0 (A0).
**Firmware:** `f411-hse` (or `f446-hse`).

```
python -m stm32timing capture --port COM5:A --seconds 120 --name e1_loopback --note "PA6->PA0 jumper, 22C"
python -m stm32timing analyze data/e1_loopback_A.log --title "E1 loopback"
```

**What to expect and why:** the reference is generated from the same 84 MHz clock that is
counting it, so every period should be **exactly 84 000 ticks**: period jitter 0, offset
0.000 ppm. Anything else points to a wiring or firmware problem (bad ground, ringing → glitch
edges, UART overflow → missing cycles). The ISR latency histogram is valid in this
experiment and shows the interrupt response of the MCU.

## E2 — Interrupt latency cross-checked with the oscilloscope

**Wiring:** as E1 (or E3); scope CH1 on PA0 (A0), CH2 on PA5 (D13), trigger CH1 rising.

1. Measure *delay CH1↑ → CH2↑* with the scope's measurement statistics over
   ≥ 1000 acquisitions; note mean / min / max / std. Take a screenshot with infinite persistence.
2. Capture 60 s of firmware data at the same time and compare to the
   *ISR latency mean / max* from the report.

**What to expect and why:** the firmware's latency is "edge → first `TIM2->CNT` read", the
scope's is "edge → marker pin high". The marker store and the counter read are adjacent
instructions in the ISR (check with `arm-none-eabi-objdump -d`), so the scope delay ≈ firmware
latency ± a few CPU cycles + GPIO output delay. The two
should differ by an approximately constant amount; agreement of the *spread* (max − min) is
the real cross-check. Also note the input synchroniser: the timer latches the edge 2–3 timer
clocks after it reaches the pin, a constant offset that affects neither periods nor ppm.

Save scope screenshots in `docs/img/` as `e2_latency_*.png`.

## E3 — Two boards against one external reference (absolute offset of each board)

**Wiring:** reference → PA0 of board A **and** board B (short wires or a T-connector), common GND.
Scope CH1 on the reference to confirm amplitude and clean edges.

```
python -m stm32timing capture --port COM5:A --port COM7:B --seconds 600 --name e3_ref_hse \
    --note "Rigol DG1022 1kHz 3.3Vpp ext-10MHz-ref, boards warmed 15 min, 22C"
python -m stm32timing compare data/e3_ref_hse_A.log data/e3_ref_hse_B.log --ref-hz 1000
```

Use `--ref-hz 1` and `--seconds 1800` for a GPS PPS.

**What to expect and why:** each board reports its own frequency offset against the reference
(a crystal is typically within a few tens of ppm). Because both boards see the same edges at the
same time, the *difference* A − B does not depend on how accurate the reference is.

Repeat with both boards on `*-hsi` firmware → `e3_ref_hsi`.

## E4 — Board-to-board without an external reference

**Wiring:** A: PA6 (D12) → A: PA0 **and** B: PA0. Board A measures itself (as E1), board B
measures board A's clock.

```
python -m stm32timing capture --port COM5:A --port COM7:B --seconds 600 --name e4_a_to_b
python -m stm32timing analyze data/e4_a_to_b_B.log --title "E4 B measuring A"
```

**Consistency check:** B's offset here must match `ppm_B − ppm_A` from E3 (same firmware,
same warm-up) to within the confidence intervals plus a little drift between the runs. This
checks the method itself, which the CV numbers rely on.

## E5 — HSE vs HSI

Same as E3 (or E4) with HSI firmware on board B. Compare: ppm offset (HSI: up to ±1 % =
±10 000 ppm), period jitter and the Allan deviation curve. Expect the RC oscillator to show
much larger offset and wander than the crystal.

## E6 (optional) — Temperature sensitivity

During an E3/E4 run, warm board B gently (hand on the board, or a hair dryer at a distance),
then let it cool. Mark times in `--note`. The drift plot shows the frequency change. Crystals
and RC oscillators react very differently, so try both HSE and HSI.

---

## Run log

| Date | Exp. | Boards (target/UID) | Firmware commit | Reference | Duration | Log files | Notes |
|---|---|---|---|---|---|---|---|
| | E1 | | | loopback | | | |
| | E2 | | | | | | |
| | E3 | | | | | | |
| | E4 | | | | | | |
| | E5 | | | | | | |
