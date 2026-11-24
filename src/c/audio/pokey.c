/* audio/pokey.c - see pokey.h. */
#include "pokey.h"

#include <math.h>
#include <string.h>

#define EV_MODE 0
#define EV_AUDF 2
#define EV_LEVEL 3

/* Altirra's non-linear mixer (pokey.cpp): the summed volume bits go through a saturation curve; one volume unit = the level of volume bit weight 1 in the linear region */
#define BIT0 (0.12 / 8.24)
#define BIT1 (0.26 / 8.24)
#define BIT23 (0.56 / 8.24)
#define LINEAR_THRESHOLD 0.14
#define CURVE_FACTOR 2.85
#define UNIT (0.56 / 8.24 / 4.0)
#define AC_TAU 0.0025968510736001341332478644258
#define AC_RATE 63920.0
#define AC_HI_COEFF 0.00063413100049954767179657139255229

double pokey_mixer_level(int n0, int n1, int n23)
{
    double x = n0 * BIT0 + n1 * BIT1 + n23 * BIT23;
    double y = x < LINEAR_THRESHOLD ? x : LINEAR_THRESHOLD + (1.0 - exp(-CURVE_FACTOR * (x - LINEAR_THRESHOLD))) / CURVE_FACTOR;

    return y / UNIT;
}

/* ---- the polynomial counters ---- */

static void build_polys(Pokey *p)
{
    uint32_t s = 0;
    int i;

    for (i = 0; i < POKEY_M17; i++) {
        s = (s >> 1) + (~((s << 16) ^ (s << 11)) & 0x10000u);
        p->p17[i] = (uint8_t)((s >> 8) & 1u);
    }
    s = 0;
    for (i = 0; i < POKEY_M9; i++) {
        s = (s >> 1) + (~((s << 8) ^ (s << 3)) & 0x100u);
        p->p9[i] = (uint8_t)(s & 1u);
    }
    s = 0;
    for (i = 0; i < POKEY_M5; i++) {
        s = (s >> 1) + (~((s << 2) ^ (s << 4)) & 16u);
        p->p5[i] = (uint8_t)(s & 1u);
    }
}

static int64_t mod_pos(int64_t a, int64_t m)
{
    int64_t r = a % m;

    return r < 0 ? r + m : r;
}

/* the mode of an AUDC as Altirra's table selects it: 0x20 tone (toggles), 0x80 not gated by poly5, 0x40 poly4 (not modelled) */
static unsigned audcn(uint8_t audc)
{
    static const uint8_t table[8] = {0x00, 0x20, 0x40, 0x20, 0x80, 0xA0, 0xC0, 0xA0};

    return table[audc >> 5];
}

/* ---- the level ---- */

static unsigned high_state(const Pokey *p, int k)
{
    if (k == 0) {
        return (p->vol_ctl & 4u) ? (unsigned)(p->ff[0] ^ p->latch[0] ^ 1u) : p->ff[0];
    }
    if (k == 1) {
        return (p->vol_ctl & 2u) ? (unsigned)(p->ff[1] ^ p->latch[1] ^ 1u) : p->ff[1];
    }
    return (unsigned)(p->ff[k] ^ 1u);
}

static double compute_level(const Pokey *p)
{
    int k, n0 = 0, n1 = 0, n23 = 0;

    for (k = 0; k < 4; k++) {
        unsigned vol = (unsigned)((p->vol_audc[k] >> 5) == 5 ? (p->vol_audc[k] & 15) : 0);
        if (!high_state(p, k)) {
            n0 += (int)(vol & 1u);
            n1 += (int)((vol >> 1) & 1u);
            n23 += (int)(((vol >> 2) & 1u) + 2u * ((vol >> 3) & 1u));
        }
    }
    if (n0 == 0 && n1 == 0 && n23 == 0) {
        return 0.0;
    }
    return -pokey_mixer_level(n0, n1, n23);
}

/* ---- the output chain: 28-cycle cells -> AC coupling -> box average into output samples ---- */

static void ring_push(Pokey *p, float v)
{
    if (p->ring_w - p->ring_r >= POKEY_RING) {
        p->dropped++;
        p->ring_r++;
    }
    p->ring[p->ring_w % POKEY_RING] = v;
    p->ring_w++;
}

static void emit_cell(Pokey *p, int64_t cell_start, double avg_level)
{
    double x = avg_level * p->amp;
    double y1 = p->ac_c1 * p->hp1_y + x - p->hp1_x;       /* AC stage 1: y = c y' + x - x' */
    double y2;
    double a = (double)cell_start, b = a + (double)POKEY_TICK;

    p->hp1_x = x;
    p->hp1_y = y1;
    y2 = y1 - p->hp2_acc;                                    /* AC stage 2: y = x - acc; acc += k y */
    p->hp2_acc += AC_HI_COEFF * y2;
    if (a < p->out_pos) {
        a = p->out_pos;
    }
    while (a < b) {
        double end = p->out_pos + p->step;
        double seg = b < end ? b : end;

        p->out_acc += y2 * (seg - a);
        a = seg;
        if (a >= end) {
            ring_push(p, (float)(p->out_acc / p->step));
            p->out_pos = end;
            p->out_acc = 0.0;
        }
    }
}

/* integrate the current level up to cycle t (cells are the 28-cycle intervals counted from cycle 0) */
static void integrate(Pokey *p, int64_t t)
{
    while (p->level_t < t) {
        int64_t cell_end = (p->level_t / POKEY_TICK + 1) * POKEY_TICK;
        int64_t seg = t < cell_end ? t : cell_end;

        p->cell_sum += p->level * (double)(seg - p->level_t);
        p->level_t = seg;
        if (seg == cell_end) {
            emit_cell(p, cell_end - POKEY_TICK, p->cell_sum / (double)POKEY_TICK);
            p->cell_sum = 0.0;
        }
    }
}

/* ---- the events ---- */

static void queue_insert(Pokey *p, int64_t t, uint8_t kind, uint8_t arg, uint8_t val)
{
    int i = p->nq;

    if (p->nq >= POKEY_QUEUE) {
        return;                                              /* cannot happen with writes 4 cycles apart and a lag of 3 */
    }
    while (i > 0 && p->queue[i - 1].t > t) {
        p->queue[i] = p->queue[i - 1];
        i--;
    }
    p->queue[i].t = t;
    p->queue[i].kind = kind;
    p->queue[i].arg = arg;
    p->queue[i].val = val;
    p->nq++;
}

static void queue_remove(Pokey *p, int i)
{
    for (; i + 1 < p->nq; i++) {
        p->queue[i] = p->queue[i + 1];
    }
    p->nq--;
}

static int64_t next_time(const Pokey *p)
{
    int64_t tn = INT64_MAX;
    int k;

    if (p->nq > 0) {
        tn = p->queue[0].t;
    }
    for (k = 0; k < 4; k++) {
        if (p->next_fire[k] < tn) {
            tn = p->next_fire[k];
        }
    }
    return tn;
}

static void fire_effect(Pokey *p, int k, int64_t f)
{
    unsigned cn = audcn(p->mode_audc[k]);
    int pass;

    if (cn & 0x40u) {
        return;                                              /* poly4: not modelled */
    }
    pass = (cn & 0x80u) ? 1 : p->p5[mod_pos(29 - k + f - p->t0_noise, POKEY_M5)];
    if (!pass) {
        return;
    }
    if (cn & 0x20u) {
        p->ff[k] ^= 1u;
    } else if (p->mode_ctl & 0x80u) {
        p->ff[k] = p->p9[mod_pos(POKEY_M9 - 1 - k + f - p->t0_noise, POKEY_M9)];
    } else {
        p->ff[k] = p->p17[mod_pos(POKEY_M17 - 1 - k + f - p->t0_noise, POKEY_M17)];
    }
}

/* everything that happens at cycle tn, in the order of the rules: mode registers, fires (latches first, then the flip-flops), AUDF writes, level registers */
static void step_time(Pokey *p, int64_t tn)
{
    int firing[4], dropped[4], k, i;
    int ctl_change = 0;

    for (i = 0; i < p->nq;) {
        if (p->queue[i].t == tn && p->queue[i].kind == EV_MODE) {
            if (p->queue[i].arg < 4) {
                p->mode_audc[p->queue[i].arg] = p->queue[i].val;
            } else {
                p->mode_ctl = p->queue[i].val;
            }
            queue_remove(p, i);
        } else {
            i++;
        }
    }
    for (i = 0; i < p->nq; i++) {
        if (p->queue[i].t == tn && p->queue[i].kind == EV_LEVEL && p->queue[i].arg == 4 && p->queue[i].val != p->vol_ctl) {
            ctl_change = 1;
        }
    }
    for (k = 0; k < 4; k++) {
        firing[k] = p->next_fire[k] == tn;
        dropped[k] = ctl_change;
        for (i = 0; i < p->nq; i++) {
            if (p->queue[i].t == tn && p->queue[i].kind == EV_AUDF && p->queue[i].arg == k && p->queue[i].val != p->audf[k]) {
                dropped[k] = 1;
            }
        }
    }
    for (k = 0; k < 4; k++) {
        if (firing[k]) {
            p->next_fire[k] += (int64_t)(p->audf[k] + 1u) * POKEY_TICK;         /* the fire reloads with the AUDF it has: a write at this cycle comes after */
        }
    }
    if (firing[2] && !dropped[2]) {
        p->latch[0] = p->ff[0];                              /* the high-pass flip-flop of channel 1 samples it at channel 3's fire, before channel 1's own edge */
    }
    if (firing[3] && !dropped[3]) {
        p->latch[1] = p->ff[1];
    }
    for (k = 0; k < 4; k++) {
        if (firing[k] && !dropped[k]) {
            fire_effect(p, k, tn);
        }
    }
    for (i = 0; i < p->nq;) {
        if (p->queue[i].t == tn && p->queue[i].kind == EV_AUDF) {
            p->audf[p->queue[i].arg] = p->queue[i].val;
            queue_remove(p, i);
        } else {
            i++;
        }
    }
    for (i = 0; i < p->nq;) {
        if (p->queue[i].t == tn && p->queue[i].kind == EV_LEVEL) {
            if (p->queue[i].arg < 4) {
                p->vol_audc[p->queue[i].arg] = p->queue[i].val;
            } else {
                p->vol_ctl = p->queue[i].val;
            }
            queue_remove(p, i);
        } else {
            i++;
        }
    }
    {
        double lv = compute_level(p);

        if (lv != p->level) {
            integrate(p, tn);
            p->level = lv;
            if (p->on_level != NULL) {
                p->on_level(p->on_level_ctx, tn, lv);
            }
        }
    }
}

static void process_until(Pokey *p, int64_t limit)
{
    for (;;) {
        int64_t tn = next_time(p);

        if (tn > limit) {
            break;
        }
        step_time(p, tn);
    }
    if (limit > p->now) {
        p->now = limit;
    }
}

/* ---- the interface ---- */

void pokey_init(Pokey *p, int64_t t_start, int64_t t0_noise, unsigned phase, double sample_rate)
{
    int k;

    memset(p, 0, sizeof *p);
    build_polys(p);
    p->t0_noise = t0_noise;
    p->phase = phase % POKEY_TICK;
    p->amp = 0.5 * 2.1 * UNIT;
    p->ac_c1 = exp(-1.0 / (AC_RATE * AC_TAU));
    p->step = POKEY_CPU_HZ / sample_rate;
    p->level_t = t_start;
    p->now = t_start - 1;
    p->out_pos = (double)((t_start / POKEY_TICK) * POKEY_TICK);
    for (k = 0; k < 4; k++) {
        p->next_fire[k] = ((t_start - (int64_t)p->phase) / POKEY_TICK + 1) * POKEY_TICK + (int64_t)p->phase;
        if (p->next_fire[k] <= t_start) {
            p->next_fire[k] += POKEY_TICK;
        }
    }
    p->level = compute_level(p);
}

void pokey_set_origin(Pokey *p, double cycle)
{
    p->out_pos = cycle;
    p->out_acc = 0.0;
}

void pokey_write(Pokey *p, int64_t cycle, unsigned reg, uint8_t value)
{
    if (reg > 8) {
        return;
    }
    process_until(p, cycle - 3);                             /* a write reaches back 2 cycles (the mode of a fire is the one 2 cycles after it) */
    integrate(p, cycle - 3);                                 /* the samples up to here are final (the caller takes them before the gap to the next write gets long) */
    if (reg == 8) {
        if (value & 0x79u) {
            p->unsupported++;                                 /* AUDCTL bits 0, 3, 4, 5, 6 */
        }
        queue_insert(p, cycle - 2, EV_MODE, 4, value);
        queue_insert(p, cycle, EV_LEVEL, 4, value);
    } else if (reg & 1u) {
        unsigned k = reg >> 1;
        if ((audcn(value) & 0x40u) || (value & 0x10u)) {
            p->unsupported++;                                 /* poly4 modes, volume-only */
        }
        queue_insert(p, cycle - 2, EV_MODE, (uint8_t)k, value);
        queue_insert(p, cycle, EV_LEVEL, (uint8_t)k, value);
    } else {
        queue_insert(p, cycle, EV_AUDF, (uint8_t)(reg >> 1), value);
    }
}

void pokey_run(Pokey *p, int64_t cycle)
{
    process_until(p, cycle - 3);
    integrate(p, cycle - 3);
}

size_t pokey_take(Pokey *p, float *dst, size_t max)
{
    size_t n = 0;

    while (n < max && p->ring_r != p->ring_w) {
        dst[n++] = p->ring[p->ring_r % POKEY_RING];
        p->ring_r++;
    }
    return n;
}
