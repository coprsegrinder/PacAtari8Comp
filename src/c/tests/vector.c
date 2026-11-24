/* The vector file reader (see vector.h for the format). */
#include "vector.h"

#include <string.h>

static int rd(VecFile *v, uint8_t *buf, size_t n)
{
    return pm_fs_read(v->f, buf, n) == n;
}

static int rd8(VecFile *v, uint8_t *x)
{
    return rd(v, x, 1);
}

static int rd16(VecFile *v, uint16_t *x)
{
    uint8_t b[2];
    if (!rd(v, b, 2)) {
        return 0;
    }
    *x = VEC_U16(b);
    return 1;
}

static int rd32(VecFile *v, uint32_t *x)
{
    uint8_t b[4];
    if (!rd(v, b, 4)) {
        return 0;
    }
    *x = VEC_U32(b);
    return 1;
}

static int rdi32(VecFile *v, int32_t *x)
{
    uint32_t u;
    if (!rd32(v, &u)) {
        return 0;
    }
    *x = u >= 0x80000000u ? (int32_t)(u - 0x80000000u) - 2147483647 - 1 : (int32_t)u;
    return 1;
}

static int vec_open_checked(VecFile *v, const char *path, const char *err[1])
{
    uint8_t magic[8];
    uint16_t nl;

    memset(v, 0, sizeof *v);
    v->f = pm_fs_open(path, "rb");
    if (v->f == NULL) {
        err[0] = pm_fs_error_text(pm_fs_error());
        return 1;
    }
    if (!rd(v, magic, 8) || memcmp(magic, "PMVEC001", 8) != 0) {
        err[0] = "not a vector file (bad magic)";
        return 1;
    }
    if (!rd8(v, &v->kind) || v->kind < 1 || v->kind > 3 || !rd16(v, &nl) || nl == 0 || nl >= VEC_MAX_NAME) {
        err[0] = "bad header (kind or name)";
        return 1;
    }
    if (!rd(v, (uint8_t *)v->name, nl)) {
        err[0] = "truncated header";
        return 1;
    }
    v->name[nl] = '\0';
    if (!rd32(v, &v->state_size) || !rd32(v, &v->count)) {
        err[0] = "truncated header";
        return 1;
    }
    if (v->kind == 1) {
        if (v->state_size != PM_STATE_SIZE) {
            err[0] = "state size differs from this build's World";
            return 1;
        }
        if (!rd(v, v->base, PM_STATE_SIZE)) {
            err[0] = "truncated base state";
            return 1;
        }
    }
    if (v->kind == 3) {
        if (v->state_size != 0 || !rd(v, v->charset, VEC_SCENE_CHARSET) || !rd(v, v->cells, VEC_SCENE_CELLS)) {
            err[0] = "truncated scene header";
            return 1;
        }
    }
    return 0;
}

/* a file that is not a good vector file is closed again: the first version leaked the open file on every error return (found by the AddressSanitizer build of stage 88) */
int vec_open(VecFile *v, const char *path, const char *err[1])
{
    int r = vec_open_checked(v, path, err);

    if (r != 0 && v->f != NULL) {
        pm_fs_close(v->f);
        v->f = NULL;
    }
    return r;
}

static int rd_diff_n(VecFile *v, const uint8_t *from, uint8_t *to, uint32_t size, const char *err[1])
{
    uint16_t nruns, i, start, len;
    memcpy(to, from, size);
    if (!rd16(v, &nruns)) {
        err[0] = "truncated diff";
        return 1;
    }
    for (i = 0; i < nruns; i++) {
        if (!rd16(v, &start) || !rd16(v, &len)) {
            err[0] = "truncated diff run";
            return 1;
        }
        if ((uint32_t)start + len > size) {
            err[0] = "diff run outside the state";
            return 1;
        }
        if (!rd(v, to + start, len)) {
            err[0] = "truncated diff bytes";
            return 1;
        }
    }
    return 0;
}

static int rd_diff(VecFile *v, const uint8_t *from, uint8_t *to, const char *err[1])
{
    return rd_diff_n(v, from, to, PM_STATE_SIZE, err);
}

int vec_next_scene(VecFile *v, SceneVec *r, const char *err[1])
{
    static const uint8_t zero_page[256];
    int p, k;

    if (v->kind != 3 || v->next >= v->count) {
        err[0] = "no more scene records";
        return 1;
    }
    if (!rd8(v, &r->mode) || r->mode > 3 || !rd16(v, &r->mask)) {
        err[0] = "bad scene header";
        return 1;
    }
    if (rd_diff_n(v, v->cells, r->cells, VEC_SCENE_CELLS, err) || !rd(v, r->hpos, 8)) {
        err[0] = "truncated scene";
        return 1;
    }
    for (p = 0; p < 5; p++) {
        if (rd_diff_n(v, zero_page, r->pages[p], 256, err)) {
            return 1;
        }
    }
    if (r->mode == 3 && !rd(v, r->latch_in, 16)) {
        err[0] = "truncated latch";
        return 1;
    }
    if (r->mode != 3) {
        for (k = 0; k < 16; k++) {
            r->latch_in[k] = 0;
        }
    }
    if (!rd(v, r->expected, 16)) {
        err[0] = "truncated registers";
        return 1;
    }
    v->next++;
    return 0;
}

int vec_next_world(VecFile *v, WorldVec *r, const char *err[1])
{
    uint8_t i;
    uint16_t k;

    if (v->kind != 1 || v->next >= v->count) {
        err[0] = "no more world records";
        return 1;
    }
    if (!rd8(v, &r->nargs) || r->nargs > VEC_MAX_ARGS) {
        err[0] = "bad argument count";
        return 1;
    }
    for (i = 0; i < r->nargs; i++) {
        if (!rdi32(v, &r->args[i])) {
            err[0] = "truncated arguments";
            return 1;
        }
    }
    if (!rd16(v, &r->nrnd) || !rd(v, r->rnd, r->nrnd)) {
        err[0] = "truncated RANDOM values";
        return 1;
    }
    if (!rd8(v, &r->has_ret) || !rdi32(v, &r->ret)) {
        err[0] = "truncated return value";
        return 1;
    }
    if (rd_diff(v, v->base, r->before, err) || rd_diff(v, r->before, r->after, err)) {
        return 1;
    }
    if (!rd16(v, &r->npokey) || r->npokey > PM_POKEY_MAX) {
        err[0] = "bad chip-write count";
        return 1;
    }
    for (k = 0; k < r->npokey; k++) {
        if (!rd16(v, &r->pokey_addr[k]) || !rd8(v, &r->pokey_val[k])) {
            err[0] = "truncated chip writes";
            return 1;
        }
    }
    v->next++;
    return 0;
}

static int rd_value(VecFile *v, VecValue *x)
{
    uint16_t n, i;
    if (!rd8(v, &x->tag)) {
        return 0;
    }
    if (x->tag == 0) {
        return rdi32(v, &x->n);
    }
    if (x->tag == 1) {
        if (!rd16(v, &n) || n > VEC_MAX_SEQ) {
            return 0;
        }
        x->n = n;
        for (i = 0; i < n; i++) {
            if (!rdi32(v, &x->seq[i])) {
                return 0;
            }
        }
        return 1;
    }
    if (x->tag == 3) {
        uint16_t ns, s, total = 0, len;
        if (!rd16(v, &ns) || ns > VEC_MAX_SUB) {
            return 0;
        }
        x->n = ns;
        for (s = 0; s < ns; s++) {
            if (!rd16(v, &len) || total + len > VEC_MAX_SEQ) {
                return 0;
            }
            x->sub_len[s] = len;
            for (i = 0; i < len; i++) {
                if (!rdi32(v, &x->seq[total + i])) {
                    return 0;
                }
            }
            total = (uint16_t)(total + len);
        }
        return 1;
    }
    return x->tag == 2;
}

int vec_next_pure(VecFile *v, PureVec *r, const char *err[1])
{
    uint8_t i;
    if (v->kind != 2 || v->next >= v->count) {
        err[0] = "no more pure records";
        return 1;
    }
    if (!rd8(v, &r->nargs) || r->nargs > VEC_MAX_ARGS) {
        err[0] = "bad argument count";
        return 1;
    }
    for (i = 0; i < r->nargs; i++) {
        if (!rd_value(v, &r->args[i])) {
            err[0] = "bad argument value";
            return 1;
        }
    }
    if (!rd_value(v, &r->result)) {
        err[0] = "bad result value";
        return 1;
    }
    v->next++;
    return 0;
}

void vec_close(VecFile *v)
{
    if (v->f != NULL) {
        pm_fs_close(v->f);
        v->f = NULL;
    }
}
