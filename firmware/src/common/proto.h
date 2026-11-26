/*
 * proto.h - text line protocol streamed over the ST-LINK virtual COM port.
 *
 *   H,1,uid=1A2B3C4D,target=F411RE,clk=HSE,ftim=84000000,ref=1000   header
 *   C,<seq>,<ticks>,<lat>,<flags>                                     capture event
 *   S,seq=<n>,drop=<n>,ovc=<n>                                        status
 *
 * Header and status are repeated periodically so the host can attach at any
 * time. All numbers are unsigned decimal except uid (8 hex digits).
 * The formatter avoids printf so the firmware does not pull in newlib's stdio.
 */
#ifndef PROTO_H
#define PROTO_H

#include <stddef.h>
#include <stdint.h>

#include "evring.h"

#define PROTO_VERSION 1u
#define PROTO_LINE_MAX 96u

typedef struct {
    uint32_t uid;        /* hash of the 96-bit device unique ID */
    const char *target;  /* "F411RE", "F446RE" */
    const char *clk;     /* "HSE", "HSI", "HSI_FALLBACK" */
    uint32_t ftim_hz;    /* capture timer clock */
    uint32_t ref_hz;     /* frequency generated on the reference output pin */
} proto_header_t;

typedef struct {
    uint32_t seq;   /* next sequence number the ISR will assign */
    uint32_t drop;  /* events lost because the ring was full */
    uint32_t ovc;   /* hardware over-captures (edges lost in the timer) */
} proto_status_t;

/* Each function writes a NUL-terminated line ending in '\n' into buf
 * (at least PROTO_LINE_MAX bytes) and returns its length without the NUL. */
size_t proto_fmt_header(char *buf, const proto_header_t *h);
size_t proto_fmt_capture(char *buf, const ev_t *e);
size_t proto_fmt_status(char *buf, const proto_status_t *s);

/* FNV-1a over the three 32-bit UID words (little-endian byte order). */
uint32_t proto_uid_hash(const uint32_t uid_words[3]);

#endif /* PROTO_H */
