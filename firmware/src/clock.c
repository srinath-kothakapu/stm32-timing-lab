#include "clock.h"

#include "board.h"
#include "stm32f4xx.h"

uint32_t SystemCoreClock = 16000000u; /* HSI after reset */

/* Called from the startup code before main() and before .data/.bss init. */
void SystemInit(void)
{
    SCB->CPACR |= (0xFu << 20); /* full access to CP10/CP11 (FPU) */
    __DSB();
    __ISB();
}

static int wait_set(volatile uint32_t *reg, uint32_t mask)
{
    for (uint32_t n = 0; n < 500000u; n++) {
        if ((*reg & mask) != 0u) {
            return 1;
        }
    }
    return 0;
}

clk_src_t clock_init(clk_src_t requested)
{
    clk_src_t got = requested;

    RCC->APB1ENR |= RCC_APB1ENR_PWREN;
    (void)RCC->APB1ENR;
    PWR->CR |= PWR_CR_VOS; /* regulator scale 1 (must be set while PLL is off) */

    if (requested == CLK_HSE) {
        RCC->CR |= RCC_CR_HSEBYP; /* external clock on PH0, not a crystal */
        RCC->CR |= RCC_CR_HSEON;
        if (!wait_set(&RCC->CR, RCC_CR_HSERDY)) {
            RCC->CR &= ~RCC_CR_HSEON;
            RCC->CR &= ~RCC_CR_HSEBYP;
            got = CLK_HSI_FALLBACK;
        }
    }

    uint32_t pllcfgr;
    if (got == CLK_HSE) {
        pllcfgr = RCC_PLLCFGR_PLLSRC_HSE | (8u << RCC_PLLCFGR_PLLM_Pos); /* 1 MHz VCO input */
    } else {
        pllcfgr = RCC_PLLCFGR_PLLSRC_HSI | (16u << RCC_PLLCFGR_PLLM_Pos);
    }
    pllcfgr |= (PLL_N << RCC_PLLCFGR_PLLN_Pos) | (((PLL_P / 2u) - 1u) << RCC_PLLCFGR_PLLP_Pos) |
               (PLL_Q << RCC_PLLCFGR_PLLQ_Pos);
#ifdef RCC_PLLCFGR_PLLR_Pos
    pllcfgr |= (2u << RCC_PLLCFGR_PLLR_Pos); /* keep PLLR at a legal value (F446) */
#else
    pllcfgr |= RCC->PLLCFGR & 0xF0000000u; /* bits 31:28 reserved on F411, keep reset value */
#endif
    RCC->PLLCFGR = pllcfgr;
    RCC->CR |= RCC_CR_PLLON;
    while ((RCC->CR & RCC_CR_PLLRDY) == 0u) {
    }

    FLASH->ACR = FLASH_ACR_ICEN | FLASH_ACR_DCEN | FLASH_ACR_PRFTEN | FLASH_WAIT_STATES;
    while ((FLASH->ACR & FLASH_ACR_LATENCY) != FLASH_WAIT_STATES) {
    }

    RCC->CFGR = (RCC->CFGR & ~(RCC_CFGR_HPRE | RCC_CFGR_PPRE1 | RCC_CFGR_PPRE2)) | RCC_CFGR_HPRE_DIV1 |
                APB1_DIV | APB2_DIV;
    RCC->CFGR = (RCC->CFGR & ~RCC_CFGR_SW) | RCC_CFGR_SW_PLL;
    while ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_PLL) {
    }

    SystemCoreClock = SYSCLK_HZ;
    return got;
}

const char *clock_name(clk_src_t src)
{
    switch (src) {
    case CLK_HSE:
        return "HSE";
    case CLK_HSI:
        return "HSI";
    default:
        return "HSI_FALLBACK";
    }
}

/* newlib's __libc_init_array (called by the ST startup code) expects _init/_fini
 * from crti.o; we link with -nostartfiles, so provide empty ones. */
void _init(void);
void _fini(void);
void _init(void) {}
void _fini(void) {}
