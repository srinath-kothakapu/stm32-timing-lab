#ifndef CLOCK_H
#define CLOCK_H

typedef enum {
    CLK_HSE = 0,          /* PLL from 8 MHz HSE bypass (ST-LINK MCO) */
    CLK_HSI = 1,          /* PLL from 16 MHz internal RC, requested */
    CLK_HSI_FALLBACK = 2, /* HSE requested but did not start; running on HSI */
} clk_src_t;

/* Configure flash wait states, PLL and bus dividers. Returns the clock
 * source that is actually in use. */
clk_src_t clock_init(clk_src_t requested);

const char *clock_name(clk_src_t src);

#endif /* CLOCK_H */
