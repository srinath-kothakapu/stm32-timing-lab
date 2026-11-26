# Measurement report — STM32 timing and synchronisation

> **Status: template. No measurements yet.** Every number in this report must come
> from a log in `data/` and the generated sections in `reports/`. Replace each
> _TBD_ only with values from a real run.

Author: Srinath Reddy Kothakapu · Date: _TBD_ · Firmware commit: _TBD_

## 1. Summary

_TBD — 3–4 sentences once E1–E4 are done, e.g. period jitter, offset of each board, board-to-board
offset, ISR latency, and whether E3 and E4 agree._

## 2. Setup

| Item | Details |
|---|---|
| Board A | _TBD (NUCLEO-F4xxRE, UID from header)_ |
| Board B | _TBD_ |
| Reference | _TBD (instrument, settings, 10 MHz lock yes/no)_ |
| Oscilloscope | _TBD (model, bandwidth, probes)_ |
| Environment | _TBD (room temperature, warm-up time)_ |

Wiring and clock tree: see [HARDWARE.md](HARDWARE.md). Procedure: see [MEASUREMENT_PLAN.md](MEASUREMENT_PLAN.md).

## 3. Method

- Rising edges on PA0 are latched in hardware by TIM2 input capture (32-bit, 84 MHz, 11.905 ns
  resolution). The timestamp therefore does not depend on interrupt latency.
- The ISR stores (sequence number, capture value, latency) in a lock-free ring buffer; the main
  loop streams the events as text at 460 800 baud.
- On the host, the 32-bit counter is unwrapped, each edge is given a reference-cycle index
  (robust to dropped lines and glitch edges), and the following are computed: period jitter,
  cycle-to-cycle jitter, frequency offset (least-squares fit), accumulated drift, time interval
  error and overlapping Allan deviation.
- Resolution limit: for a reference asynchronous to the timer, the period of a perfect signal
  is N or N+1 ticks, giving a quantisation floor of about tick/√6 ≈ 4.9 ns (1σ).
- The analysis code is unit-tested against synthetic data with known offset, jitter, gaps and
  glitches (`host/tests`). The synthetic data is used only for testing and never appears in this report.

## 4. Results

### E1 Loopback

_Paste `reports/e1_loopback_A/results.md` here._

### E2 ISR latency: firmware vs oscilloscope

| | Firmware (TIM2 count) | Oscilloscope (PA0↑ → PA5↑) |
|---|---|---|
| Mean | _TBD_ | _TBD_ |
| Min / max | _TBD_ | _TBD_ |
| Samples | _TBD_ | _TBD_ |

_Scope screenshot: `img/e2_latency.png`_

### E3 Two boards, common reference (HSE)

_Paste `reports/compare_.../comparison.md` here._

### E4 Board-to-board, and consistency with E3

| | Value |
|---|---|
| E3: ppm_B − ppm_A | _TBD_ |
| E4: B measuring A | _TBD_ |
| Difference | _TBD_ |

### E5 HSE vs HSI

_TBD_

## 5. Discussion

Points to address (and to be able to explain in an interview):

1. Why does the loopback run (E1) show exactly zero period jitter?
2. Is the measured jitter limited by the reference, the input path or the timer resolution?
3. What sets the ISR latency floor (exception entry, flash wait states, bus clock ratio) and what
   causes its spread?
4. Do E3 and E4 agree? If not, what changed between the runs (temperature, warm-up)?
5. How does the HSI result compare with the datasheet (±1 % at 25 °C)?

## 6. Limitations

- "HSE" on a Nucleo-64 is the ST-LINK's 8 MHz crystal, not a crystal on the target MCU.
- The 95 % confidence interval on ppm assumes white residuals; with wander it is optimistic.
- _TBD — reference accuracy, temperature not controlled, …_

## 7. Conclusion

_TBD_
