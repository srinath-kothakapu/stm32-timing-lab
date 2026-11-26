/*
 * calc.h - pure helper calculations (no register access), unit-tested on the host.
 */
#ifndef CALC_H
#define CALC_H

#include <stdbool.h>
#include <stdint.h>

/* USART BRR value for 16x oversampling: round(pclk / baud). */
uint32_t calc_usart_brr(uint32_t pclk_hz, uint32_t baud);

/* Actual baud rate produced by a BRR value (16x oversampling). */
uint32_t calc_usart_baud(uint32_t pclk_hz, uint32_t brr);

/*
 * Prescaler / auto-reload for a 16-bit timer so that
 *   f_out = f_tim / ((psc + 1) * (arr + 1))   equals f_out_hz exactly.
 * Picks the smallest prescaler (best duty-cycle resolution).
 * Returns false if f_out_hz cannot be generated exactly.
 */
bool calc_timer_psc_arr(uint32_t f_tim_hz, uint32_t f_out_hz, uint32_t *psc, uint32_t *arr);

#endif /* CALC_H */
