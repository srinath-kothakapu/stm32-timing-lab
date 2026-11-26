#include "uart.h"

#include "calc.h"
#include "stm32f4xx.h"

void uart_init(uint32_t pclk_hz, uint32_t baud)
{
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN;
    RCC->APB1ENR |= RCC_APB1ENR_USART2EN;
    (void)RCC->APB1ENR;

    /* PA2 -> AF7 (USART2_TX), high speed */
    GPIOA->MODER = (GPIOA->MODER & ~(3u << (2u * 2u))) | (2u << (2u * 2u));
    GPIOA->OSPEEDR |= (3u << (2u * 2u));
    GPIOA->AFR[0] = (GPIOA->AFR[0] & ~(0xFu << (4u * 2u))) | (7u << (4u * 2u));

    USART2->CR1 = 0u;
    USART2->BRR = calc_usart_brr(pclk_hz, baud);
    USART2->CR1 = USART_CR1_TE | USART_CR1_UE;
}

void uart_write(const char *s, size_t n)
{
    while (n-- > 0u) {
        while ((USART2->SR & USART_SR_TXE) == 0u) {
        }
        USART2->DR = (uint8_t)*s++;
    }
}
