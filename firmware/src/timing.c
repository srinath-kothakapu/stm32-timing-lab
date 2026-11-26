#include "timing.h"

#include "board.h"
#include "calc.h"
#include "stm32f4xx.h"

evring_t g_events;
volatile uint32_t g_seq;
volatile uint32_t g_dropped;
volatile uint32_t g_overcapture;

static void gpio_af(GPIO_TypeDef *port, uint32_t pin, uint32_t af)
{
    port->MODER = (port->MODER & ~(3u << (2u * pin))) | (2u << (2u * pin));
    port->OSPEEDR |= (3u << (2u * pin));
    port->PUPDR &= ~(3u << (2u * pin));
    volatile uint32_t *afr = &port->AFR[pin >> 3];
    uint32_t shift = 4u * (pin & 7u);
    *afr = (*afr & ~(0xFu << shift)) | (af << shift);
}

void marker_init(void)
{
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN;
    (void)RCC->AHB1ENR;
    GPIOA->BSRR = (1u << (MARKER_PIN + 16u));
    GPIOA->MODER = (GPIOA->MODER & ~(3u << (2u * MARKER_PIN))) | (1u << (2u * MARKER_PIN));
    GPIOA->OSPEEDR |= (3u << (2u * MARKER_PIN)); /* very high speed: sharp edges for the scope */
}

bool refout_init(uint32_t f_hz)
{
    uint32_t psc, arr;
    if (!calc_timer_psc_arr(TIM_CLK_HZ, f_hz, &psc, &arr)) {
        return false;
    }
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN;
    RCC->APB1ENR |= RCC_APB1ENR_TIM3EN;
    (void)RCC->APB1ENR;
    gpio_af(GPIOA, 6u, 2u); /* PA6 = TIM3_CH1 */

    TIM3->CR1 = 0u;
    TIM3->PSC = psc;
    TIM3->ARR = arr;
    TIM3->CCR1 = (arr + 1u) / 2u;
    TIM3->CCMR1 = (6u << TIM_CCMR1_OC1M_Pos) | TIM_CCMR1_OC1PE; /* PWM mode 1 */
    TIM3->CCER = TIM_CCER_CC1E;
    TIM3->EGR = TIM_EGR_UG;
    TIM3->CR1 = TIM_CR1_ARPE | TIM_CR1_CEN;
    return true;
}

void capture_init(void)
{
    evring_init(&g_events);
    g_seq = 0u;
    g_dropped = 0u;
    g_overcapture = 0u;

    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN;
    RCC->APB1ENR |= RCC_APB1ENR_TIM2EN;
    (void)RCC->APB1ENR;
    gpio_af(GPIOA, 0u, 1u); /* PA0 = TIM2_CH1 */

    TIM2->CR1 = 0u;
    TIM2->PSC = 0u;          /* one tick per timer clock: 11.905 ns */
    TIM2->ARR = 0xFFFFFFFFu; /* free-running 32-bit, wraps every 51.1 s */
    TIM2->CCMR1 = (1u << TIM_CCMR1_CC1S_Pos) | ((CAPTURE_FILTER & 0xFu) << TIM_CCMR1_IC1F_Pos);
    TIM2->CCER = TIM_CCER_CC1E; /* rising edge (CC1P = CC1NP = 0) */
    TIM2->EGR = TIM_EGR_UG;
    TIM2->SR = 0u;
    TIM2->DIER = TIM_DIER_CC1IE;

    NVIC_SetPriority(TIM2_IRQn, 0u);
    NVIC_EnableIRQ(TIM2_IRQn);
    TIM2->CR1 = TIM_CR1_CEN;
}

uint32_t capture_now(void)
{
    return TIM2->CNT;
}

void TIM2_IRQHandler(void)
{
    GPIOA->BSRR = (1u << MARKER_PIN);
    uint32_t now = TIM2->CNT;

    if ((TIM2->SR & TIM_SR_CC1IF) != 0u) {
        ev_t e;
        e.ticks = TIM2->CCR1; /* reading CCR1 clears CC1IF */
        e.flags = 0u;
        if ((TIM2->SR & TIM_SR_CC1OF) != 0u) {
            TIM2->SR = ~TIM_SR_CC1OF; /* rc_w0 */
            e.flags |= EV_FLAG_OVERCAPTURE;
            g_overcapture++;
        }
        uint32_t lat = now - e.ticks;
        e.lat = (uint16_t)(lat > 0xFFFFu ? 0xFFFFu : lat);
        e.seq = g_seq++;
        e._pad = 0u;
        if (!evring_push(&g_events, &e)) {
            g_dropped++;
        }
    }

    GPIOA->BSRR = (1u << (MARKER_PIN + 16u));
}
