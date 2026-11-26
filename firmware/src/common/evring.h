/*
 * evring.h - single-producer / single-consumer ring buffer for capture events.
 *
 * Producer: TIM2 capture ISR. Consumer: main loop.
 * Lock-free: head is written only by the producer, tail only by the consumer.
 * Capacity must be a power of two; one slot is never used, so the ring holds
 * EVRING_CAPACITY - 1 events.
 *
 * Portable C99, no hardware dependencies, unit-tested on the host.
 */
#ifndef EVRING_H
#define EVRING_H

#include <stdbool.h>
#include <stdint.h>

#ifndef EVRING_CAPACITY
#define EVRING_CAPACITY 512u
#endif

#if (EVRING_CAPACITY & (EVRING_CAPACITY - 1u)) != 0u
#error "EVRING_CAPACITY must be a power of two"
#endif

#define EV_FLAG_OVERCAPTURE 0x01u /* an edge was lost before CCR1 was read */

typedef struct {
    uint32_t seq;   /* edge sequence number, increments for every captured edge */
    uint32_t ticks; /* TIM2 counter value latched by hardware at the edge */
    uint16_t lat;   /* ISR entry latency: TIM2->CNT - ticks, in timer ticks (saturated) */
    uint8_t flags;  /* EV_FLAG_* */
    uint8_t _pad;
} ev_t;

typedef struct {
    volatile uint32_t head; /* next slot to write (producer) */
    volatile uint32_t tail; /* next slot to read (consumer) */
    ev_t buf[EVRING_CAPACITY];
} evring_t;

static inline void evring_init(evring_t *r)
{
    r->head = 0u;
    r->tail = 0u;
}

static inline uint32_t evring_count(const evring_t *r)
{
    return (r->head - r->tail) & (EVRING_CAPACITY - 1u);
}

/* Returns false (and stores nothing) when the ring is full. */
static inline bool evring_push(evring_t *r, const ev_t *e)
{
    uint32_t head = r->head;
    uint32_t next = (head + 1u) & (EVRING_CAPACITY - 1u);
    if (next == r->tail) {
        return false;
    }
    r->buf[head] = *e;
    __asm__ volatile("" ::: "memory"); /* publish data before the index */
    r->head = next;
    return true;
}

/* Returns false when the ring is empty. */
static inline bool evring_pop(evring_t *r, ev_t *out)
{
    uint32_t tail = r->tail;
    if (tail == r->head) {
        return false;
    }
    __asm__ volatile("" ::: "memory");
    *out = r->buf[tail];
    __asm__ volatile("" ::: "memory");
    r->tail = (tail + 1u) & (EVRING_CAPACITY - 1u);
    return true;
}

#endif /* EVRING_H */
