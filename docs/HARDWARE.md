# Hardware and wiring

## Bill of materials

| Item | Purpose | Notes |
|---|---|---|
| 2 × NUCLEO-F411RE or NUCLEO-F446RE (any mix) | Device under test, board A and board B | Firmware runs the capture timer at 84 MHz on both, so results are directly comparable |
| 2 × USB cable | Power, flashing, virtual COM port | |
| Oscilloscope, ≥ 2 channels, ≥ 100 MHz | Signal check, ISR-latency cross-check | HKA lab scope is fine |
| Reference source (one of these) | Known-good timing reference | See below |
| Jumper wires, common ground | | Connect all GNDs before connecting signals |

### Reference source options

| Source | Typical accuracy | Use with |
|---|---|---|
| GPS module with PPS output (e.g. u-blox NEO-6M/M8N), antenna with sky view | PPS edge ±10…50 ns, long-term frequency ≪ 0.01 ppm | `--ref-hz 1`; runs of ≥ 30 min |
| Lab function generator locked to a 10 MHz reference (rubidium/GPSDO/OCXO) | ≪ 0.1 ppm | 1 kHz square wave, 0 V / 3.3 V |
| Lab function generator, free-running internal timebase | Check its datasheet (often ±1…20 ppm) | Good for jitter; ppm is then relative to the generator |
| The other Nucleo's PA6 output | Crystal, ±tens of ppm | Board-to-board relative measurements (E4) |

> An oscilloscope timebase is usually specified around ±10…50 ppm. Use the scope for
> signal integrity and latency, not as the frequency reference.

## Pins (same on both Nucleo-64 boards)

| Signal | MCU pin | Arduino header | Morpho header | Direction |
|---|---|---|---|---|
| Reference input (TIM2_CH1 capture) | PA0 | A0 | CN7 pin 28 | in |
| Reference output (TIM3_CH1, 50 % square, `REF_HZ`) | PA6 | D12 | CN10 pin 13 | out |
| ISR marker (high while the capture ISR runs; also LED LD2) | PA5 | D13 | CN10 pin 11 | out |
| UART TX → ST-LINK virtual COM port, 460800 8N1 | PA2 | (internal) | | out |
| GND | | GND | CN7 pin 20/22 | |

Input levels: 0 V / 3.3 V logic. Never drive PA0 negative or above 3.3 V
(set the function generator to *High-Z load*, 3.3 Vpp, 1.65 V offset, or use its TTL output through a divider).

## Clock tree

The firmware configures both targets so that TIM2 runs from an 84 MHz clock
(1 tick = 11.905 ns):

| | NUCLEO-F411RE | NUCLEO-F446RE |
|---|---|---|
| SYSCLK | 84 MHz | 168 MHz |
| PCLK1 | 42 MHz | 42 MHz |
| TIM2 / TIM3 clock | 84 MHz | 84 MHz |
| PLL input | 1 MHz (HSE 8 MHz / 8, or HSI 16 MHz / 16) | same |

**HSE** — on the Nucleo-64 boards the STM32 has no crystal of its own by default. The 8 MHz
HSE comes from the ST-LINK's MCO output (HSE bypass, solder bridges SB16 and SB50 closed —
the factory default). So the "HSE" accuracy you measure is the accuracy of the
**ST-LINK's 8 MHz crystal**. If HSE does not start, the firmware falls back to HSI and reports
`clk=HSI_FALLBACK` in its header, so a wrong solder-bridge setup cannot silently pass as a crystal run.

**HSI** — internal 16 MHz RC oscillator, factory-trimmed (datasheet: ±1 % at 25 °C). Build with the `*-hsi` preset.

## Wiring per experiment

All boards and the reference source share **one ground**.

```
E1 loopback (one board)            E3 common reference (two boards, simultaneous)
                                   
  board A                            reference ──┬──► A: PA0 (A0)
  PA6 (D12) ──► PA0 (A0)                         └──► B: PA0 (A0)
  scope CH1 = A0, CH2 = D13          scope CH1 = reference, CH2 = A: D13

E4 board-to-board                  E2 latency cross-check (scope)
                                   
  A: PA6 (D12) ──┬──► A: PA0 (A0)    CH1 = PA0 (A0)  trigger rising
                 └──► B: PA0 (A0)    CH2 = PA5 (D13) marker
```
