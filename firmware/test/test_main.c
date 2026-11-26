/*
 * Host-side unit tests for the hardware-independent firmware modules:
 * evring.h, proto.c, calc.c. Build with the host compiler (see CMakeLists.txt).
 */
#include <stdio.h>
#include <string.h>

#include "calc.h"
#include "evring.h"
#include "proto.h"

static int g_fail;
static int g_pass;

#define CHECK(cond)                                                                \
    do {                                                                           \
        if (cond) {                                                                \
            g_pass++;                                                              \
        } else {                                                                   \
            g_fail++;                                                              \
            fprintf(stderr, "%s:%d: CHECK failed: %s\n", __FILE__, __LINE__, #cond); \
        }                                                                          \
    } while (0)

#define CHECK_STR(a, b) CHECK(strcmp((a), (b)) == 0)

static evring_t ring;

static void test_evring_basic(void)
{
    evring_init(&ring);
    ev_t e = {0}, out;
    CHECK(evring_count(&ring) == 0u);
    CHECK(!evring_pop(&ring, &out));

    e.seq = 7u;
    e.ticks = 0xDEADBEEFu;
    e.lat = 42u;
    CHECK(evring_push(&ring, &e));
    CHECK(evring_count(&ring) == 1u);
    CHECK(evring_pop(&ring, &out));
    CHECK(out.seq == 7u && out.ticks == 0xDEADBEEFu && out.lat == 42u);
    CHECK(evring_count(&ring) == 0u);
}

static void test_evring_full_and_wrap(void)
{
    evring_init(&ring);
    ev_t e = {0}, out;
    uint32_t pushed = 0u;
    while (evring_push(&ring, &e)) {
        e.seq++;
        pushed++;
    }
    CHECK(pushed == EVRING_CAPACITY - 1u);
    CHECK(evring_count(&ring) == EVRING_CAPACITY - 1u);

    /* drain half, refill across the wrap point, check order */
    for (uint32_t i = 0; i < EVRING_CAPACITY / 2u; i++) {
        CHECK(evring_pop(&ring, &out));
        CHECK(out.seq == i);
    }
    for (uint32_t i = 0; i < EVRING_CAPACITY / 2u; i++) {
        CHECK(evring_push(&ring, &e));
        e.seq++;
    }
    CHECK(!evring_push(&ring, &e));
    uint32_t expect = EVRING_CAPACITY / 2u;
    while (evring_pop(&ring, &out)) {
        CHECK(out.seq == expect);
        expect++;
    }
    CHECK(expect == e.seq);
}

static void test_proto_capture(void)
{
    char buf[PROTO_LINE_MAX];
    ev_t e = {.seq = 123u, .ticks = 4294967295u, .lat = 27u, .flags = EV_FLAG_OVERCAPTURE};
    size_t n = proto_fmt_capture(buf, &e);
    CHECK_STR(buf, "C,123,4294967295,27,1\n");
    CHECK(n == strlen(buf));

    ev_t z = {0};
    proto_fmt_capture(buf, &z);
    CHECK_STR(buf, "C,0,0,0,0\n");
}

static void test_proto_header_status(void)
{
    char buf[PROTO_LINE_MAX];
    proto_header_t h = {
        .uid = 0x00A1B2C3u, .target = "F411RE", .clk = "HSE", .ftim_hz = 84000000u, .ref_hz = 1000u};
    size_t n = proto_fmt_header(buf, &h);
    CHECK_STR(buf, "H,1,uid=00A1B2C3,target=F411RE,clk=HSE,ftim=84000000,ref=1000\n");
    CHECK(n == strlen(buf));

    proto_status_t s = {.seq = 10u, .drop = 0u, .ovc = 3u};
    proto_fmt_status(buf, &s);
    CHECK_STR(buf, "S,seq=10,drop=0,ovc=3\n");
}

static void test_proto_truncation(void)
{
    char buf[PROTO_LINE_MAX];
    char longname[200];
    memset(longname, 'x', sizeof longname - 1u);
    longname[sizeof longname - 1u] = '\0';
    proto_header_t h = {.uid = 1u, .target = longname, .clk = "HSE", .ftim_hz = 1u, .ref_hz = 1u};
    size_t n = proto_fmt_header(buf, &h);
    CHECK(n == PROTO_LINE_MAX - 1u); /* never overflows, still NUL-terminated */
    CHECK(buf[n] == '\0');
}

static void test_uid_hash(void)
{
    const uint32_t a[3] = {0x00350041u, 0x3436510Au, 0x38343530u};
    const uint32_t b[3] = {0x00350041u, 0x3436510Au, 0x38343531u};
    CHECK(proto_uid_hash(a) == proto_uid_hash(a));
    CHECK(proto_uid_hash(a) != proto_uid_hash(b));
    const uint32_t zero[3] = {0u, 0u, 0u};
    /* FNV-1a of 12 zero bytes */
    uint32_t h = 2166136261u;
    for (int i = 0; i < 12; i++) {
        h *= 16777619u;
    }
    CHECK(proto_uid_hash(zero) == h);
}

static void test_calc_brr(void)
{
    CHECK(calc_usart_brr(42000000u, 460800u) == 91u);
    CHECK(calc_usart_baud(42000000u, 91u) == 461538u);
    /* baud error must stay well below the ~2 % UART tolerance */
    uint32_t actual = calc_usart_baud(42000000u, calc_usart_brr(42000000u, 460800u));
    double err = ((double)actual - 460800.0) / 460800.0;
    CHECK(err < 0.005 && err > -0.005);
    CHECK(calc_usart_brr(16000000u, 115200u) == 139u);
    CHECK(calc_usart_brr(1u, 0u) == 0u);
}

static void test_calc_timer(void)
{
    uint32_t psc, arr;
    CHECK(calc_timer_psc_arr(84000000u, 1000u, &psc, &arr));
    CHECK((psc + 1u) * (arr + 1u) == 84000u);
    CHECK(arr <= 0xFFFFu);
    CHECK(psc == 1u); /* smallest prescaler that fits 16 bits: 2 x 42000 */

    CHECK(calc_timer_psc_arr(84000000u, 1u, &psc, &arr));
    CHECK((uint64_t)(psc + 1u) * (arr + 1u) == 84000000u);
    CHECK(arr <= 0xFFFFu && psc <= 0xFFFFu);

    CHECK(calc_timer_psc_arr(84000000u, 10000u, &psc, &arr));
    CHECK(psc == 0u && arr == 8399u);

    CHECK(!calc_timer_psc_arr(84000000u, 0u, &psc, &arr));
    CHECK(!calc_timer_psc_arr(84000000u, 999u, &psc, &arr)); /* not an exact divisor */
    CHECK(!calc_timer_psc_arr(84000000u, 50000000u, &psc, &arr));
}

int main(void)
{
    test_evring_basic();
    test_evring_full_and_wrap();
    test_proto_capture();
    test_proto_header_status();
    test_proto_truncation();
    test_uid_hash();
    test_calc_brr();
    test_calc_timer();
    printf("%d checks passed, %d failed\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
