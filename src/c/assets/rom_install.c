/* assets/rom_install.c - see rom_install.h.  Twin of tools/decode_streams.py (the three expansions of Start / ExpandData) and tools/make_c_assets.py (the blob). */
#include "rom_install.h"

#include <string.h>

#include "../platform/fs.h"
#include "assets.h"
#include "rom_layout.h"
#include "sha256.h"

#define GAME_CHARSET_BYTES 808u
#define TITLE_CHARSET_BYTES 192u
#define MAZE_BYTES 920u
#define TABLES_BYTES 512u              /* the 256 source bytes give 512 nibbles at $0600-$07FF */
#define ROM_WINDOW_ADDR 0xBA00u
#define ROM_WINDOW_BYTES 0x600u
#define NIBBLE_SOURCE_BYTES 256u

#define ADDR_GAME_CHARSET_STREAM 0xA003u     /* type B -> $3000 */
#define ADDR_MAZE_STREAM 0xA1E1u             /* type A -> $0800 */
#define ADDR_TITLE_CHARSET_STREAM 0xBE13u    /* type B -> $1808, followed by TitleCharsetTail */
#define ADDR_NIBBLES 0xBE95u                 /* nibble split -> $0600 */
#define ADDR_TYPE_B_TABLE 0xBD7Au            /* 64 byte values of the type B streams */

const char *rom_error_text(RomError e)
{
    switch (e) {
    case ROM_OK: return "ok";
    case ROM_OPEN_FAILED: return "the ROM file cannot be opened";
    case ROM_BAD_SIZE: return "the ROM is not 8192 bytes";
    case ROM_BAD_HASH: return "the ROM is not the NTSC Pac-Man cartridge this port is made from (sha256 differs)";
    case ROM_BAD_STREAM: return "a compressed stream of the ROM is malformed";
    case ROM_BUFFER_TOO_SMALL: return "the output buffer is too small";
    case ROM_WRITE_FAILED: return "the asset blob cannot be written";
    }
    return "unknown error";
}

RomError rom_check(const uint8_t *rom, size_t size)
{
    uint8_t h[32];

    if (size != ROM_SIZE) {
        return ROM_BAD_SIZE;
    }
    pm_sha256(rom, size, h);
    return memcmp(h, ROM_SHA256, 32) == 0 ? ROM_OK : ROM_BAD_HASH;
}

/* ---- the three expansions ---- */

typedef struct Dec {
    const uint8_t *rom;
    uint8_t *out;
    size_t cap, len;
    int bad;
} Dec;

static unsigned rd(Dec *d, unsigned addr)
{
    if (addr < ROM_BASE || addr - ROM_BASE >= ROM_SIZE) {
        d->bad = 1;
        return 0;
    }
    return d->rom[addr - ROM_BASE];
}

static void put(Dec *d, unsigned v, unsigned times)
{
    while (times-- > 0u) {
        if (d->len >= d->cap) {
            d->bad = 1;
            return;
        }
        d->out[d->len++] = (uint8_t)v;
    }
}

/* type A (code $A3BA): c < $80 literal; $80-$BF repeat the next byte (c & $3F) + 1 times; $C0-$FE three bytes (c & $3F, high nibble, low nibble of the next byte); $FF end */
static int decode_a(Dec *d, unsigned a)
{
    for (;;) {
        unsigned c = rd(d, a);
        if (d->bad) {
            return 0;
        }
        if (c < 0x80u) {
            put(d, c, 1);
            a += 1;
        } else if (c == 0xFFu) {
            return !d->bad;
        } else if (c < 0xC0u) {
            put(d, rd(d, a + 1), (c & 0x3Fu) + 1u);
            a += 2;
        } else {
            unsigned b = rd(d, a + 1);
            put(d, c & 0x3Fu, 1);
            put(d, b >> 4, 1);
            put(d, b & 0x0Fu, 1);
            a += 2;
        }
        if (d->bad) {
            return 0;
        }
    }
}

/* type B (ExpandData, $A668): c < $40 table[c]; c >= $40 table[c & $3F] (c >> 6) + 1 times; $FF end */
static int decode_b(Dec *d, unsigned a)
{
    for (;;) {
        unsigned c = rd(d, a);
        if (d->bad) {
            return 0;
        }
        if (c == 0xFFu) {
            return 1;
        }
        put(d, rd(d, ADDR_TYPE_B_TABLE + (c & 0x3Fu)), (c >> 6) + 1u);
        if (d->bad) {
            return 0;
        }
        a += 1;
    }
}

/* ---- the blob ---- */

typedef struct Blob {
    uint8_t *out;
    size_t cap, len;
    int over;
    uint16_t count;
} Blob;

static void b_byte(Blob *b, unsigned v)
{
    if (b->len >= b->cap) {
        b->over = 1;
        return;
    }
    b->out[b->len++] = (uint8_t)v;
}

static void b_u16(Blob *b, unsigned v)
{
    b_byte(b, v & 0xFFu);
    b_byte(b, (v >> 8) & 0xFFu);
}

static void b_u32(Blob *b, uint32_t v)
{
    b_u16(b, (unsigned)(v & 0xFFFFu));
    b_u16(b, (unsigned)(v >> 16));
}

static void b_entry(Blob *b, const char *name, unsigned kind, unsigned addr, const uint8_t *data, size_t size)
{
    size_t n = strlen(name), i;

    b_byte(b, (unsigned)n);
    for (i = 0; i < n; i++) {
        b_byte(b, (unsigned char)name[i]);
    }
    b_byte(b, kind);
    b_u32(b, addr);
    b_u32(b, (uint32_t)size);
    for (i = 0; i < size; i++) {
        b_byte(b, data[i]);
    }
    b->count++;
}

static uint32_t fnv1a(const uint8_t *p, size_t n)
{
    uint32_t h = 0x811C9DC5u;
    size_t i;

    for (i = 0; i < n; i++) {
        h = (h ^ p[i]) * 0x01000193u;
    }
    return h;
}

RomError rom_build_blob(const uint8_t *rom, size_t size, uint8_t *out, size_t cap, size_t *len)
{
    static uint8_t game[GAME_CHARSET_BYTES], title[TITLE_CHARSET_BYTES], maze[MAZE_BYTES], tables[TABLES_BYTES];
    uint8_t nib[2u * NIBBLE_SOURCE_BYTES];   /* equal to TABLES_BYTES */
    Blob b;
    Dec d;
    RomError e = rom_check(rom, size);
    size_t i, tail = 0;
    unsigned k;

    *len = 0;
    if (e != ROM_OK) {
        return e;
    }
    /* the character sets, the maze: their streams must give exactly the sizes the game expands them to */
    d.rom = rom; d.out = game; d.cap = sizeof game; d.len = 0; d.bad = 0;
    if (!decode_b(&d, ADDR_GAME_CHARSET_STREAM) || d.len != GAME_CHARSET_BYTES) {
        return ROM_BAD_STREAM;
    }
    d.out = maze; d.cap = sizeof maze; d.len = 0;
    if (!decode_a(&d, ADDR_MAZE_STREAM) || d.len != MAZE_BYTES) {
        return ROM_BAD_STREAM;
    }
    d.out = title; d.cap = sizeof title; d.len = 0;
    if (!decode_b(&d, ADDR_TITLE_CHARSET_STREAM)) {
        return ROM_BAD_STREAM;
    }
    for (k = 0; k < ROM_REGION_COUNT; k++) {            /* the title set goes on with the region TitleCharsetTail */
        if (strcmp(ROM_REGIONS[k].name, "TitleCharsetTail") == 0) {
            unsigned a = ROM_REGIONS[k].addr;
            tail = ROM_REGIONS[k].size;
            if (a < ROM_BASE || a - ROM_BASE + tail > ROM_SIZE || d.len + tail != TITLE_CHARSET_BYTES) {
                return ROM_BAD_STREAM;
            }
            memcpy(title + d.len, rom + (a - ROM_BASE), tail);
        }
    }
    if (tail == 0u) {
        return ROM_BAD_STREAM;
    }
    /* the nibble split at $BE95: each byte gives its high, then its low nibble */
    for (i = 0; i < NIBBLE_SOURCE_BYTES; i++) {
        unsigned v = rom[ADDR_NIBBLES - ROM_BASE + i];
        nib[2u * i] = (uint8_t)(v >> 4);
        nib[2u * i + 1u] = (uint8_t)(v & 0x0Fu);
    }
    memcpy(tables, nib, TABLES_BYTES);

    b.out = out; b.cap = cap; b.len = 0; b.over = 0; b.count = 0;
    b_byte(&b, 'P'); b_byte(&b, 'M'); b_byte(&b, 'A'); b_byte(&b, 'B');
    b_u16(&b, ASSETS_VERSION);
    b_u16(&b, ASSETS_SCHEMA);
    b_u16(&b, 6u + ROM_REGION_COUNT);
    b_u16(&b, 0);
    for (i = 0; i < 32; i++) {
        b_byte(&b, ROM_SHA256[i]);
    }
    b_entry(&b, "charset.game", ASSET_RAM, 0x3000u, game, sizeof game);
    b_entry(&b, "charset.title", ASSET_RAM, 0x1808u, title, sizeof title);
    b_entry(&b, "maze", ASSET_RAM, 0x0800u, maze, sizeof maze);
    b_entry(&b, "ram_0600", ASSET_RAM, 0x0600u, tables, sizeof tables);
    b_entry(&b, "font", ASSET_RAM, 0xE000u, FONT_DATA, FONT_SIZE);
    b_entry(&b, "rom_ba00", ASSET_ROM_WINDOW, ROM_WINDOW_ADDR, rom + (ROM_WINDOW_ADDR - ROM_BASE), ROM_WINDOW_BYTES);
    for (k = 0; k < ROM_REGION_COUNT; k++) {
        const RomRegion *r = &ROM_REGIONS[k];
        char name[ASSETS_NAME_MAX + 1];
        size_t n = strlen(r->name);
        if (r->addr < ROM_BASE || (size_t)(r->addr - ROM_BASE) + r->size > ROM_SIZE || n + 8u > sizeof name) {
            return ROM_BAD_STREAM;
        }
        memcpy(name, "region.", 7);
        memcpy(name + 7, r->name, n + 1u);
        b_entry(&b, name, r->kind, r->addr, rom + (r->addr - ROM_BASE), r->size);
    }
    if (b.over || b.len + 4u > b.cap) {
        return ROM_BUFFER_TOO_SMALL;
    }
    b_u32(&b, fnv1a(b.out, b.len));
    *len = b.len;
    return ROM_OK;
}

/* the folders of `path` (everything before the last name) under the main folder, made one level at a time: a clean checkout has no `resources/` yet (found by tools/check_clean_build.py, stage 97) */
static void make_parent_folders(const char *path)
{
    char prefix[256];
    size_t i, n = strlen(path);

    if (n >= sizeof prefix) {
        return;
    }
    for (i = 1; i < n; i++) {
        if (path[i] == '/' || path[i] == '\\') {
            memcpy(prefix, path, i);
            prefix[i] = '\0';
            (void)pm_fs_mkdir(prefix);                  /* an error shows when the file itself cannot be opened */
        }
    }
}

RomError rom_install(const char *rom_path, const char *blob_path)
{
    static uint8_t rom[ROM_SIZE + 1u];
    static uint8_t blob[ASSET_BLOB_MAX];
    PmFile *f = pm_fs_open(rom_path, "rb");
    size_t got, len;
    RomError e;

    if (f == NULL) {
        return ROM_OPEN_FAILED;
    }
    got = pm_fs_read(f, rom, sizeof rom);               /* one byte more than the ROM: a longer file is refused */
    pm_fs_close(f);
    e = rom_build_blob(rom, got, blob, sizeof blob, &len);
    if (e != ROM_OK) {
        return e;
    }
    make_parent_folders(blob_path);
    f = pm_fs_open(blob_path, "wb");
    if (f == NULL) {
        return ROM_WRITE_FAILED;
    }
    if (pm_fs_write(f, blob, len) != len) {
        pm_fs_close(f);
        return ROM_WRITE_FAILED;
    }
    return pm_fs_close(f) == 0 ? ROM_OK : ROM_WRITE_FAILED;
}
