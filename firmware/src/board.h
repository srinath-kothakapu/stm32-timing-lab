/*
 * board.h - target configuration for NUCLEO-F411RE and NUCLEO-F446RE.
 *
 * Both targets are clocked so that the APB1 timer clock is 84 MHz, which makes
 * one TIM2 tick = 11.905 ns on either board and keeps results comparable.
 *
 * Pin map (identical on both Nucleo-64 boards):
 *   PA0  TIM2_CH1  input capture  <- reference signal (Arduino A0, CN8 pin 1)
 *   PA6  TIM3_CH1  reference out  -> 50 % square wave at REF_HZ (Arduino D12)
 *   PA5  GPIO      ISR marker     -> high while the capture ISR runs (D13, LD2)
 *   PA2  USART2_TX                -> ST-LINK virtual COM port
 *
 * HSE: by default the Nucleo-64 feeds an 8 MHz clock from the ST-LINK MCO into
 * PH0 (HSE bypass). That clock comes from the ST-LINK's own 8 MHz crystal.
 */
#ifndef BOARD_H
#define BOARD_H

#if defined(TARGET_F411RE)
#define BOARD_TARGET_NAME "F411RE"
#define SYSCLK_HZ 84000000u
#define PLL_N 336u
#define PLL_P 4u
#define PLL_Q 7u
#define FLASH_WAIT_STATES FLASH_ACR_LATENCY_2WS
#define APB1_DIV RCC_CFGR_PPRE1_DIV2
#define APB2_DIV RCC_CFGR_PPRE2_DIV1
#elif defined(TARGET_F446RE)
#define BOARD_TARGET_NAME "F446RE"
#define SYSCLK_HZ 168000000u /* 168 MHz: no over-drive needed */
#define PLL_N 336u
#define PLL_P 2u
#define PLL_Q 7u
#define FLASH_WAIT_STATES FLASH_ACR_LATENCY_5WS
#define APB1_DIV RCC_CFGR_PPRE1_DIV4
#define APB2_DIV RCC_CFGR_PPRE2_DIV2
#else
#error "Define TARGET_F411RE or TARGET_F446RE"
#endif

#define PCLK1_HZ 42000000u
#define TIM_CLK_HZ 84000000u /* APB1 timer clock = 2 x PCLK1 */

#ifndef REF_HZ
#define REF_HZ 1000u
#endif

#ifndef UART_BAUD
#define UART_BAUD 460800u
#endif

/* Clock source request: 0 = HSE (ST-LINK MCO, crystal derived), 1 = HSI (internal RC) */
#ifndef CLOCK_USE_HSI
#define CLOCK_USE_HSI 0
#endif

/* Input capture digital filter (TIMx_CCMR1.IC1F, 0..15). 0 = off.
 * A filter adds a constant delay, so it does not change measured periods. */
#ifndef CAPTURE_FILTER
#define CAPTURE_FILTER 0u
#endif

/* Header and status are re-sent at least this often (in TIM2 ticks). */
#define HEADER_INTERVAL_TICKS (2u * TIM_CLK_HZ)

#define MARKER_PIN 5u

#endif /* BOARD_H */
