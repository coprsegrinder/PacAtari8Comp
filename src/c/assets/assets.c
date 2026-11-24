/* assets/assets.c - see assets.h.  The format is read one byte at a time (little-endian by the code, not by the machine). */
#include "assets.h"

#include <string.h>

#include "../core/tables.h"
#include "../platform/fs.h"

#define HEADER_SIZE 44u

static uint32_t rd16(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8);
}

static uint32_t rd32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
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

const char *assets_error_text(AssetsError e)
{
    switch (e) {
    case ASSETS_OK: return "ok";
    case ASSETS_TOO_SHORT: return "the blob is too short";
    case ASSETS_BAD_MAGIC: return "bad magic (not an asset blob)";
    case ASSETS_BAD_VERSION: return "unknown format version";
    case ASSETS_BAD_SCHEMA: return "unknown pack schema";
    case ASSETS_TOO_MANY: return "too many entries";
    case ASSETS_BAD_ENTRY: return "an entry is malformed";
    case ASSETS_DUPLICATE: return "two entries have the same name";
    case ASSETS_BAD_CHECKSUM: return "bad checksum";
    case ASSETS_TRAILING: return "bytes between the last entry and the checksum";
    case ASSETS_OPEN_FAILED: return "the file cannot be opened";
    case ASSETS_READ_FAILED: return "the file cannot be read";
    case ASSETS_TOO_BIG: return "the file does not fit the buffer";
    }
    return "unknown error";
}

static AssetsError fail(Assets *a, AssetsError e)
{
    a->count = 0;
    return e;
}

AssetsError assets_parse(Assets *a, const uint8_t *blob, size_t size)
{
    size_t pos, end, i;
    uint16_t n, k;

    memset(a, 0, sizeof *a);
    if (size < HEADER_SIZE + 4u) {
        return ASSETS_TOO_SHORT;
    }
    if (memcmp(blob, "PMAB", 4) != 0) {
        return ASSETS_BAD_MAGIC;
    }
    if (rd16(blob + 4) != ASSETS_VERSION) {
        return ASSETS_BAD_VERSION;
    }
    if (rd16(blob + 6) != ASSETS_SCHEMA) {
        return ASSETS_BAD_SCHEMA;
    }
    n = (uint16_t)rd16(blob + 8);
    if (n > ASSETS_MAX_ENTRIES) {
        return ASSETS_TOO_MANY;
    }
    end = size - 4u;                                   /* the trailer */
    if (fnv1a(blob, end) != rd32(blob + end)) {
        return ASSETS_BAD_CHECKSUM;
    }
    memcpy(a->rom_sha256, blob + 12, 32);
    pos = HEADER_SIZE;
    for (k = 0; k < n; k++) {
        AssetEntry *e = &a->entry[k];
        size_t len;

        if (pos >= end) {
            return fail(a, ASSETS_BAD_ENTRY);
        }
        len = blob[pos++];
        if (len < 1u || len > ASSETS_NAME_MAX || end - pos < len + 9u) {
            return fail(a, ASSETS_BAD_ENTRY);
        }
        for (i = 0; i < len; i++) {
            if (blob[pos + i] < 0x21u || blob[pos + i] > 0x7Eu) {
                return fail(a, ASSETS_BAD_ENTRY);
            }
            e->name[i] = (char)blob[pos + i];
        }
        e->name[len] = '\0';
        pos += len;
        e->kind = blob[pos];
        e->addr = rd32(blob + pos + 1);
        e->size = rd32(blob + pos + 5);
        pos += 9;
        if (e->kind > ASSET_ROM_WINDOW || e->size > end - pos) {
            return fail(a, ASSETS_BAD_ENTRY);
        }
        e->data = blob + pos;
        pos += e->size;
        for (i = 0; i < k; i++) {
            if (strcmp(a->entry[i].name, e->name) == 0) {
                return fail(a, ASSETS_DUPLICATE);
            }
        }
        a->count = (uint16_t)(k + 1u);
    }
    if (pos != end) {
        return fail(a, ASSETS_TRAILING);
    }
    return ASSETS_OK;
}

AssetsError assets_load(Assets *a, const char *path, uint8_t *buf, size_t cap)
{
    PmFile *f = pm_fs_open(path, "rb");
    size_t got = 0, r;

    memset(a, 0, sizeof *a);
    if (f == NULL) {
        return ASSETS_OPEN_FAILED;
    }
    for (;;) {
        if (got == cap) {                              /* full: one more byte must not exist */
            uint8_t extra;
            r = pm_fs_read(f, &extra, 1);
            pm_fs_close(f);
            return r == 0 ? assets_parse(a, buf, got) : ASSETS_TOO_BIG;
        }
        r = pm_fs_read(f, buf + got, cap - got);
        if (r == 0) {
            break;
        }
        got += r;
    }
    pm_fs_close(f);
    return assets_parse(a, buf, got);
}

const AssetEntry *assets_find(const Assets *a, const char *name)
{
    uint16_t k;

    for (k = 0; k < a->count; k++) {
        if (strcmp(a->entry[k].name, name) == 0) {
            return &a->entry[k];
        }
    }
    return NULL;
}

int assets_ram_layout_ok(const Assets *a)
{
    uint16_t i, k;

    for (i = 0; i < a->count; i++) {
        const AssetEntry *e = &a->entry[i];
        if (e->kind != ASSET_RAM) {
            continue;
        }
        if (e->addr > 0x10000u || e->size > 0x10000u - e->addr) {
            return 0;
        }
        for (k = (uint16_t)(i + 1u); k < a->count; k++) {
            const AssetEntry *o = &a->entry[k];
            if (o->kind == ASSET_RAM && e->addr < o->addr + o->size && o->addr < e->addr + e->size) {
                return 0;
            }
        }
    }
    return 1;
}

void assets_ram_image(const Assets *a, uint8_t image[65536])
{
    uint16_t k;

    memset(image, 0, 65536);
    if (!assets_ram_layout_ok(a)) {
        return;
    }
    for (k = 0; k < a->count; k++) {
        const AssetEntry *e = &a->entry[k];
        if (e->kind == ASSET_RAM) {
            memcpy(image + e->addr, e->data, e->size);
        }
    }
}

AssetsError assets_install_tables(const Assets *a)
{
    const AssetEntry *ram = assets_find(a, "ram_0600");
    const AssetEntry *rom = assets_find(a, "rom_ba00");
    const AssetEntry *maze = assets_find(a, "maze");

    if (ram == NULL || rom == NULL || maze == NULL || ram->kind != ASSET_RAM || rom->kind != ASSET_ROM_WINDOW || maze->kind != ASSET_RAM) {
        return ASSETS_BAD_ENTRY;
    }
    if (rom->addr != 0xBA00u || ram->addr != 0x0600u || maze->addr != 0x0800u) {
        return ASSETS_BAD_ENTRY;
    }
    return tables_set(ram->data, ram->size, rom->data, rom->size, maze->data, maze->size) == 0 ? ASSETS_OK : ASSETS_BAD_ENTRY;
}

AssetsError assets_boot(const char *path)
{
    static uint8_t buf[16384];
    static Assets a;
    AssetsError e = assets_load(&a, path, buf, sizeof buf);

    return e != ASSETS_OK ? e : assets_install_tables(&a);
}
