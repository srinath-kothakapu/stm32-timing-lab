#ifndef TIMING_H
#define TIMING_H

#include <stdbool.h>
#include <stdint.h>

#include "evring.h"

extern evring_t g_events;
extern volatile uint32_t g_seq;         /* next sequence number */
extern volatile uint32_t g_dropped;     /* ring full */
extern volatile uint32_t g_overcapture; /* timer over-capture */

/* PA5 as push-pull output, driven high for the duration of the capture ISR. */
void marker_init(void);

/* TIM3_CH1 on PA6: 50 % square wave at f_hz. Returns false if f_hz is not
 * exactly reachable from the 84 MHz timer clock. */
bool refout_init(uint32_t f_hz);

/* TIM2 free-running 32-bit counter at TIM_CLK_HZ, CH1 (PA0) rising-edge capture. */
void capture_init(void);

/* Current TIM2 count (shared time base). */
uint32_t capture_now(void);

#endif /* TIMING_H */
