#include "proto.h"

typedef struct {
    char *p;
    char *end; /* one past the last usable byte (space for NUL kept) */
} wr_t;

static void put_ch(wr_t *w, char c)
{
    if (w->p < w->end) {
        *w->p++ = c;
    }
}

static void put_str(wr_t *w, const char *s)
{
    while (s != NULL && *s != '\0') {
        put_ch(w, *s++);
    }
}

static void put_u32(wr_t *w, uint32_t v)
{
    char tmp[10];
    int n = 0;
    do {
        tmp[n++] = (char)('0' + (v % 10u));
        v /= 10u;
    } while (v != 0u);
    while (n > 0) {
        put_ch(w, tmp[--n]);
    }
}

static void put_hex32(wr_t *w, uint32_t v)
{
    static const char hex[] = "0123456789ABCDEF";
    for (int shift = 28; shift >= 0; shift -= 4) {
        put_ch(w, hex[(v >> (unsigned)shift) & 0xFu]);
    }
}

static size_t finish(wr_t *w, char *buf)
{
    put_ch(w, '\n');
    *w->p = '\0';
    return (size_t)(w->p - buf);
}

size_t proto_fmt_header(char *buf, const proto_header_t *h)
{
    wr_t w = {buf, buf + PROTO_LINE_MAX - 1u};
    put_str(&w, "H,");
    put_u32(&w, PROTO_VERSION);
    put_str(&w, ",uid=");
    put_hex32(&w, h->uid);
    put_str(&w, ",target=");
    put_str(&w, h->target);
    put_str(&w, ",clk=");
    put_str(&w, h->clk);
    put_str(&w, ",ftim=");
    put_u32(&w, h->ftim_hz);
    put_str(&w, ",ref=");
    put_u32(&w, h->ref_hz);
    return finish(&w, buf);
}

size_t proto_fmt_capture(char *buf, const ev_t *e)
{
    wr_t w = {buf, buf + PROTO_LINE_MAX - 1u};
    put_str(&w, "C,");
    put_u32(&w, e->seq);
    put_ch(&w, ',');
    put_u32(&w, e->ticks);
    put_ch(&w, ',');
    put_u32(&w, e->lat);
    put_ch(&w, ',');
    put_u32(&w, e->flags);
    return finish(&w, buf);
}

size_t proto_fmt_status(char *buf, const proto_status_t *s)
{
    wr_t w = {buf, buf + PROTO_LINE_MAX - 1u};
    put_str(&w, "S,seq=");
    put_u32(&w, s->seq);
    put_str(&w, ",drop=");
    put_u32(&w, s->drop);
    put_str(&w, ",ovc=");
    put_u32(&w, s->ovc);
    return finish(&w, buf);
}

uint32_t proto_uid_hash(const uint32_t uid_words[3])
{
    uint32_t h = 2166136261u;
    for (int i = 0; i < 3; i++) {
        for (int b = 0; b < 4; b++) {
            h ^= (uid_words[i] >> (8 * b)) & 0xFFu;
            h *= 16777619u;
        }
    }
    return h;
}
