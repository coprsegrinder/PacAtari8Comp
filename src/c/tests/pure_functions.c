/* The table of the pure functions for the vector runner (stage 76a): each wrapper reads its arguments from a recorded call (integers and sequences of integers, as tools/make_vectors.py
 * wrote them), calls the function of core/ref.c and writes the result in the same shape as the Python function returned it. */
#include <string.h>

#include "pure_functions.h"

/* argument accessors: a wrong shape makes the call fail (status 1), it is never guessed */
static int is_int(const PureVec *in, int i)
{
    return i < in->nargs && in->args[i].tag == 0;
}

static int is_seq(const PureVec *in, int i, int32_t len)
{
    return i < in->nargs && in->args[i].tag == 1 && in->args[i].n == len;
}

#define ARG(i) (in->args[i].n)

static void set_int(VecValue *out, int32_t v)
{
    memset(out, 0, sizeof *out);
    out->tag = 0;
    out->n = v;
}

static void set_seq(VecValue *out, const int32_t *v, int n)
{
    int i;
    memset(out, 0, sizeof *out);
    out->tag = 1;
    out->n = n;
    for (i = 0; i < n; i++) {
        out->seq[i] = v[i];
    }
}

static void set_bytes(VecValue *out, const uint8_t *v, int n)
{
    int32_t t[8];
    int i;
    for (i = 0; i < n; i++) {
        t[i] = v[i];
    }
    set_seq(out, t, n);
}

static void set_none(VecValue *out)
{
    memset(out, 0, sizeof *out);
    out->tag = 2;
}

static int bytes4(const PureVec *in, int i, uint8_t out[4])
{
    int k;
    if (!is_seq(in, i, 4)) {
        return 0;
    }
    for (k = 0; k < 4; k++) {
        out[k] = (uint8_t)in->args[i].seq[k];
    }
    return 1;
}

/* ---- the 16 recorded functions */
static int p_bonus_glyph(const PureVec *in, VecValue *out, int *rnd_ok)
{
    (void)rnd_ok;
    if (!is_int(in, 0)) {
        return 1;
    }
    set_int(out, ref_bonus_glyph((uint8_t)ARG(0)));
    return 0;
}

static int p_bonus_points(const PureVec *in, VecValue *out, int *rnd_ok)
{
    (void)rnd_ok;
    if (!is_int(in, 0)) {
        return 1;
    }
    set_int(out, ref_bonus_points((uint8_t)ARG(0)));
    return 0;
}

static int p_bonus_popup_glyphs(const PureVec *in, VecValue *out, int *rnd_ok)
{
    uint8_t g[5];
    (void)rnd_ok;
    if (!is_int(in, 0)) {
        return 1;
    }
    ref_bonus_popup_glyphs((uint8_t)ARG(0), g);
    set_bytes(out, g, 5);
    return 0;
}

static int p_count_dot(const PureVec *in, VecValue *out, int *rnd_ok)
{
    uint8_t lo, hi;
    int32_t t[3];
    int done;
    (void)rnd_ok;
    if (!is_int(in, 0) || !is_int(in, 1)) {
        return 1;
    }
    done = ref_count_dot((uint8_t)ARG(0), (uint8_t)ARG(1), &lo, &hi);
    t[0] = lo;
    t[1] = hi;
    t[2] = done;
    set_seq(out, t, 3);
    return 0;
}

static int p_force_chase(const PureVec *in, VecValue *out, int *rnd_ok)
{
    uint8_t s[4], r[4];
    (void)rnd_ok;
    if (!bytes4(in, 0, s) || !is_int(in, 1) || ARG(1) < 0 || ARG(1) > 3) {
        return 1;
    }
    ref_force_chase(s, ARG(1), r);
    set_bytes(out, r, 4);
    return 0;
}

static int p_fright_end_phase(const PureVec *in, VecValue *out, int *rnd_ok)
{
    (void)rnd_ok;
    if (!is_int(in, 0)) {
        return 1;
    }
    set_int(out, ref_fright_end_phase((uint8_t)ARG(0)));
    return 0;
}

static int p_fright_frames(const PureVec *in, VecValue *out, int *rnd_ok)
{
    (void)rnd_ok;
    if (!is_int(in, 0)) {
        return 1;
    }
    set_int(out, ref_fright_frames((uint8_t)ARG(0)));
    return 0;
}

static int p_fright_total_frames(const PureVec *in, VecValue *out, int *rnd_ok)
{
    int32_t v = 0;
    (void)rnd_ok;
    if (!is_int(in, 0)) {
        return 1;
    }
    if (ref_fright_total_frames((uint8_t)ARG(0), &v)) {
        set_int(out, v);
    } else {
        set_none(out);
    }
    return 0;
}

static int p_frightened_end(const PureVec *in, VecValue *out, int *rnd_ok)
{
    uint8_t s[4], r[4];
    (void)rnd_ok;
    if (!bytes4(in, 0, s)) {
        return 1;
    }
    ref_frightened_end(s, r);
    set_bytes(out, r, 4);
    return 0;
}

static int p_ghost_points(const PureVec *in, VecValue *out, int *rnd_ok)
{
    (void)rnd_ok;
    if (!is_int(in, 0) || ARG(0) < 0) {
        return 1;
    }
    set_int(out, ref_ghost_points(ARG(0)));
    return 0;
}

static int p_junction_exits(const PureVec *in, VecValue *out, int *rnd_ok)
{
    int on = 0;
    int32_t t[2];
    (void)rnd_ok;
    if (!is_int(in, 0) || !is_int(in, 1) || !is_int(in, 2) || !is_int(in, 3) || !is_int(in, 4) || ARG(3) < 0 || ARG(3) > 8) {
        return 1;
    }
    t[0] = ref_junction_exits(ARG(0), ARG(1), ARG(2), ARG(3), ARG(4), &on);
    t[1] = on;
    set_seq(out, t, 2);
    return 0;
}

static int p_move_delay_tick(const PureVec *in, VecValue *out, int *rnd_ok)
{
    int32_t cycle;
    uint8_t count;
    int32_t t[3];
    (void)rnd_ok;
    if (!is_int(in, 0) || !is_int(in, 1) || !is_int(in, 2) || !is_int(in, 3) || ARG(2) < 0 || ARG(2) > 3) {
        return 1;
    }
    cycle = ARG(2);
    count = (uint8_t)ARG(3);
    t[0] = ref_move_delay_tick(ARG(0), (uint8_t)ARG(1), &cycle, &count);
    t[1] = cycle;
    t[2] = count;
    set_seq(out, t, 3);
    return 0;
}

static int p_power_pellet_ghosts(const PureVec *in, VecValue *out, int *rnd_ok)
{
    uint8_t s[4], d[4], rs[4], rd[4];
    int k;
    (void)rnd_ok;
    if (!bytes4(in, 0, s) || !bytes4(in, 1, d)) {
        return 1;
    }
    for (k = 0; k < 4; k++) {
        if (d[k] > 8) {
            return 1;
        }
    }
    ref_power_pellet_ghosts(s, d, rs, rd);
    memset(out, 0, sizeof *out);
    out->tag = 3;
    out->n = 2;
    out->sub_len[0] = 4;
    out->sub_len[1] = 4;
    for (k = 0; k < 4; k++) {
        out->seq[k] = rs[k];
        out->seq[4 + k] = rd[k];
    }
    return 0;
}

static int p_release_timers(const PureVec *in, VecValue *out, int *rnd_ok)
{
    uint8_t t[3];
    (void)rnd_ok;
    if (!is_int(in, 0)) {
        return 1;
    }
    ref_release_timers((uint8_t)ARG(0), t);
    set_bytes(out, t, 3);
    return 0;
}

static int p_score_add(const PureVec *in, VecValue *out, int *rnd_ok)
{
    int64_t s;
    int32_t e, l, t[3];
    (void)rnd_ok;
    if (!is_int(in, 0) || !is_int(in, 1) || !is_int(in, 2) || !is_int(in, 3) || ARG(0) < 0 || ARG(1) < 0) {
        return 1;
    }
    ref_score_add(ARG(0), ARG(1), ARG(2), ARG(3), &s, &e, &l);
    t[0] = (int32_t)s;
    t[1] = e;
    t[2] = l;
    set_seq(out, t, 3);
    return 0;
}

/* steer(ey, ex, ty, tx, state, mask, rnd): the last argument is the RANDOM values the Python function took (0 or 1 of them) */
static int p_steer(const PureVec *in, VecValue *out, int *rnd_ok)
{
    uint8_t vals[VEC_MAX_SEQ];
    RandomFeed rf;
    int32_t n, k;
    int d;
    if (in->nargs != 7 || !is_int(in, 0) || !is_int(in, 1) || !is_int(in, 2) || !is_int(in, 3) || !is_int(in, 4) || !is_int(in, 5)) {
        return 1;
    }
    if (in->args[6].tag != 1 || in->args[6].n > 8) {
        return 1;
    }
    n = in->args[6].n;
    for (k = 0; k < n; k++) {
        vals[k] = (uint8_t)in->args[6].seq[k];
    }
    random_feed_init(&rf, vals, (uint32_t)n);
    d = ref_steer(ARG(0), ARG(1), ARG(2), ARG(3), ARG(4), ARG(5), &rf);
    *rnd_ok = rf.used == (uint32_t)n && rf.overrun == 0;
    set_int(out, d);
    return 0;
}

static const PureEntry pure_table[] = {
    {"core_ref.bonus_glyph", p_bonus_glyph},
    {"core_ref.bonus_points", p_bonus_points},
    {"core_ref.bonus_popup_glyphs", p_bonus_popup_glyphs},
    {"core_ref.count_dot", p_count_dot},
    {"core_ref.force_chase", p_force_chase},
    {"core_ref.fright_end_phase", p_fright_end_phase},
    {"core_ref.fright_frames", p_fright_frames},
    {"core_ref.fright_total_frames", p_fright_total_frames},
    {"core_ref.frightened_end", p_frightened_end},
    {"core_ref.ghost_points", p_ghost_points},
    {"core_ref.junction_exits", p_junction_exits},
    {"core_ref.move_delay_tick", p_move_delay_tick},
    {"core_ref.power_pellet_ghosts", p_power_pellet_ghosts},
    {"core_ref.release_timers", p_release_timers},
    {"core_ref.score_add", p_score_add},
    {"core_ref.steer", p_steer},
};

PureFn pure_lookup(const char *name)
{
    size_t i;
    for (i = 0; i < sizeof pure_table / sizeof pure_table[0]; i++) {
        if (strcmp(pure_table[i].name, name) == 0) {
            return pure_table[i].fn;
        }
    }
    return NULL;
}

size_t pure_count(void)
{
    return sizeof pure_table / sizeof pure_table[0];
}

const char *pure_name(size_t i)
{
    return pure_table[i].name;
}

int value_equal(const VecValue *a, const VecValue *b)
{
    int32_t i, total = 0;
    if (a->tag != b->tag) {
        return 0;
    }
    switch (a->tag) {
    case 0:
        return a->n == b->n;
    case 1:
        if (a->n != b->n) {
            return 0;
        }
        total = a->n;
        break;
    case 2:
        return 1;
    case 3:
        if (a->n != b->n) {
            return 0;
        }
        for (i = 0; i < a->n; i++) {
            if (a->sub_len[i] != b->sub_len[i]) {
                return 0;
            }
            total += a->sub_len[i];
        }
        break;
    default:
        return 0;
    }
    for (i = 0; i < total; i++) {
        if (a->seq[i] != b->seq[i]) {
            return 0;
        }
    }
    return 1;
}
