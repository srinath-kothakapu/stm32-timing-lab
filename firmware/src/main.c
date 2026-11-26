/*
 * STM32 timing lab firmware.
 *
 * Timestamps rising edges on PA0 with TIM2 input capture (hardware-latched, so
 * the timestamp itself has no interrupt-latency jitter), measures interrupt
 * entry latency, generates a reference square wave on PA6, and streams
 * everything as text over the ST-LINK virtual COM port.
 */
#include "board.h"
#include "clock.h"
#include "proto.h"
#include "stm32f4xx.h"
#include "timing.h"
#include "uart.h"

static proto_header_t s_header;

static uint32_t read_uid_hash(void)
{
    const volatile uint32_t *uid = (const volatile uint32_t *)UID_BASE;
    uint32_t words[3] = {uid[0], uid[1], uid[2]};
    return proto_uid_hash(words);
}

static void send_header_and_status(void)
{
    char line[PROTO_LINE_MAX];
    uart_write(line, proto_fmt_header(line, &s_header));

    proto_status_t st;
    __disable_irq();
    st.seq = g_seq;
    st.drop = g_dropped;
    st.ovc = g_overcapture;
    __enable_irq();
    uart_write(line, proto_fmt_status(line, &st));
}

int main(void)
{
    clk_src_t clk = clock_init(CLOCK_USE_HSI ? CLK_HSI : CLK_HSE);

    marker_init();
    uart_init(PCLK1_HZ, UART_BAUD);

    s_header.uid = read_uid_hash();
    s_header.target = BOARD_TARGET_NAME;
    s_header.clk = clock_name(clk);
    s_header.ftim_hz = TIM_CLK_HZ;
    s_header.ref_hz = refout_init(REF_HZ) ? REF_HZ : 0u;

    capture_init();
    send_header_and_status();
    uint32_t last_header = capture_now();

    char line[PROTO_LINE_MAX];
    for (;;) {
        ev_t e;
        if (evring_pop(&g_events, &e)) {
            uart_write(line, proto_fmt_capture(line, &e));
        }
        uint32_t now = capture_now();
        if ((uint32_t)(now - last_header) >= HEADER_INTERVAL_TICKS) {
            last_header = now;
            send_header_and_status();
        }
    }
}
