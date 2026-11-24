/* Vector files (docs/51 section 2): the format, read byte by byte, little-endian, whatever the byte order of the machine.
 *
 *   file    = "PMVEC001" kind:u8 name_len:u16 name  state_size:u32 count:u32  [kind 1: base state, state_size bytes]  count x record
 *   kind 1  (a call on a World):  nargs:u8 args:i32[nargs]  nrnd:u16 rnd:u8[nrnd]  has_ret:u8 ret:i32  diff(before from base)  diff(after from before)  npokey:u16 (addr:u16 value:u8)[npokey]
 *   kind 2  (a pure call):        nargs:u8 value[nargs]  value(result)
 *   diff    = nruns:u16 (start:u16 len:u16 bytes[len])[nruns]       over the packed state of world_pack()
 *   value   = tag:u8 (0: i32 | 1: n:u16 i32[n] | 2: none | 3: nsub:u16 (n:u16 i32[n])[nsub])
 *
 *   kind 3  (a collision scene, stage 77a): after the count, charset:u8[1024] and the base cells:u8[920]; a record is  mode:u8 mask:u16 diff(cells, 920 bytes) hpos:u8[8] 5 x diff(page, 256 bytes)
 *           [mode 3: latch_in:u8[16]] expected:u8[16]   (mode 0 no latch, 1 latch cleared, 2 latch carried, 3 latch set from the file; the scene is ORed into it; mask = the registers compared)
 *
 * tools/vecfmt.py writes it; this reads it.  PM_TEST_SWAP_ENDIAN builds the reader with the opposite byte order (the byte-order test of docs/51 section 2a: such a build must not accept the files). */
#ifndef PM_TESTS_VECTOR_H
#define PM_TESTS_VECTOR_H

#include <stdint.h>

#include "../core/world.h"
#include "../platform/fs.h"

#define VEC_SCENE_CELLS 920
#define VEC_SCENE_CHARSET 1024
#define VEC_MAX_ARGS 16
#define VEC_MAX_RND 65535
#define VEC_MAX_NAME 64

#ifdef PM_TEST_SWAP_ENDIAN
#define VEC_U16(b) ((uint16_t)(((unsigned)(b)[0] << 8) | (unsigned)(b)[1]))
#define VEC_U32(b) (((uint32_t)(b)[0] << 24) | ((uint32_t)(b)[1] << 16) | ((uint32_t)(b)[2] << 8) | (uint32_t)(b)[3])
#else
#define VEC_U16(b) ((uint16_t)((unsigned)(b)[0] | ((unsigned)(b)[1] << 8)))
#define VEC_U32(b) ((uint32_t)(b)[0] | ((uint32_t)(b)[1] << 8) | ((uint32_t)(b)[2] << 16) | ((uint32_t)(b)[3] << 24))
#endif

typedef struct VecFile {
    PmFile *f;
    uint8_t kind;
    char name[VEC_MAX_NAME];
    uint32_t state_size;
    uint32_t count;
    uint32_t next;                  /* records read */
    uint8_t base[PM_STATE_SIZE];
    uint8_t charset[1024];          /* kind 3 */
    uint8_t cells[920];             /* kind 3: the header's maze cells */
} VecFile;

#define VEC_MAX_SEQ 256
#define VEC_MAX_SUB 8

typedef struct VecValue {
    uint8_t tag;                    /* 0 int, 1 sequence, 2 none, 3 sequence of sequences */
    int32_t n;                      /* the int, or the length of the sequence, or the number of sequences */
    uint16_t sub_len[VEC_MAX_SUB];  /* tag 3: the length of each sequence; the values follow one another in seq */
    int32_t seq[VEC_MAX_SEQ];
} VecValue;

typedef struct WorldVec {
    uint8_t nargs;
    int32_t args[VEC_MAX_ARGS];
    uint16_t nrnd;
    uint8_t rnd[VEC_MAX_RND];
    uint8_t has_ret;
    int32_t ret;
    uint8_t before[PM_STATE_SIZE];
    uint8_t after[PM_STATE_SIZE];
    uint16_t npokey;
    uint16_t pokey_addr[PM_POKEY_MAX];
    uint8_t pokey_val[PM_POKEY_MAX];
} WorldVec;

typedef struct SceneVec {
    uint8_t mode;
    uint16_t mask;
    uint8_t cells[VEC_SCENE_CELLS];
    uint8_t hpos[8];
    uint8_t pages[5][256];
    uint8_t latch_in[16];
    uint8_t expected[16];
} SceneVec;

typedef struct PureVec {
    uint8_t nargs;
    VecValue args[VEC_MAX_ARGS];
    VecValue result;
} PureVec;

/* 0 on success, else a message in `err` (a refused path, a bad magic, a truncated file ...) */
int vec_open(VecFile *v, const char *path, const char *err[1]);
int vec_next_world(VecFile *v, WorldVec *r, const char *err[1]);   /* the next recorded call of a World function: 0 and `*r` filled, 1 and a message in `err` at the end of the set or on a bad record */
int vec_next_scene(VecFile *v, SceneVec *r, const char *err[1]);   /* the same for a scene (the collision registers) */
int vec_next_pure(VecFile *v, PureVec *r, const char *err[1]);   /* the same for a pure function */
void vec_close(VecFile *v);   /* closes the file */

#endif
