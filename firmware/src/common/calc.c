#include "calc.h"

uint32_t calc_usart_brr(uint32_t pclk_hz, uint32_t baud)
{
    if (baud == 0u) {
        return 0u;
    }
    return (uint32_t)(((uint64_t)pclk_hz + baud / 2u) / baud);
}

uint32_t calc_usart_baud(uint32_t pclk_hz, uint32_t brr)
{
    if (brr == 0u) {
        return 0u;
    }
    return (uint32_t)(((uint64_t)pclk_hz + brr / 2u) / brr);
}

bool calc_timer_psc_arr(uint32_t f_tim_hz, uint32_t f_out_hz, uint32_t *psc, uint32_t *arr)
{
    if (f_out_hz == 0u || f_out_hz > f_tim_hz / 2u || (f_tim_hz % f_out_hz) != 0u) {
        return false;
    }
    uint32_t total = f_tim_hz / f_out_hz; /* (psc + 1) * (arr + 1) */
    for (uint32_t p = 1u; p <= 65536u; p++) {
        if ((total % p) == 0u) {
            uint32_t a = total / p;
            if (a >= 2u && a <= 65536u) {
                *psc = p - 1u;
                *arr = a - 1u;
                return true;
            }
        }
    }
    return false;
}
