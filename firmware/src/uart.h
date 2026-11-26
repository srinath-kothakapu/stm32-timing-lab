#ifndef UART_H
#define UART_H

#include <stddef.h>
#include <stdint.h>

/* USART2 on PA2 (TX only), 8N1. */
void uart_init(uint32_t pclk_hz, uint32_t baud);

/* Blocking write. */
void uart_write(const char *s, size_t n);

#endif /* UART_H */
