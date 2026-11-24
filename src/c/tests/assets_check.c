/* Stage 80a: checks of the asset blob loader (src/c/assets).
 *   assets_check BLOB [IMAGE]   loads BLOB (through platform/fs.c), runs the checks below and prints "assets_check: ok ..." (exit 0), or "assets_check: error: <text>" (exit 1) when the blob is refused.
 *                               With IMAGE (a 64 KB file) the loader's RAM image must equal it byte for byte.
 *   assets_check --dump BLOB OUT  writes the loader's 64 KB RAM image to OUT.
 * Checks on a good blob: the 79 regions hold 2,246 bytes and every region inside $BA00-$BFFF equals the ROM window of the blob; the blob's tables, ROM window and maze are what the core's tables hold after
 * assets_install_tables (the wiring); the RAM parts do not overlap.  Where the bytes are RIGHT is checked against the ROM by tests/test_c_assets.py (Python code that shares nothing with the installer).
 * Paths are relative to the main folder (the working directory). */
#include <stdio.h>
#include <string.h>

#include "../assets/assets.h"
#include "../core/tables.h"
#include "../assets/sha256.h"
#include "../platform/fs.h"

static int failures;

#define CHECK(cond)                                                        \
    do {                                                                   \
        if (!(cond)) {                                                     \
            printf("FAILED line %d: %s\n", __LINE__, #cond);               \
            failures++;                                                    \
        }                                                                  \
    } while (0)

static uint8_t blob_buf[65536];
static uint8_t image[65536], expected[65536];
static Assets assets;

static int read_file(const char *path, uint8_t *buf, size_t n)
{
    PmFile *f = pm_fs_open(path, "rb");
    size_t got;

    if (f == NULL) {
        return 0;
    }
    got = pm_fs_read(f, buf, n);
    pm_fs_close(f);
    return got == n;
}

static void checks(void)
{
    uint16_t k;
    uint32_t region_bytes = 0;
    unsigned regions = 0;
    const AssetEntry *e;

    CHECK(assets_ram_layout_ok(&assets));
    for (k = 0; k < assets.count; k++) {
        const AssetEntry *r = &assets.entry[k];
        uint32_t i;
        if (r->kind == ASSET_RAM || r->kind == ASSET_ROM_WINDOW) {
            continue;
        }
        regions++;
        region_bytes += r->size;
        CHECK(strncmp(r->name, "region.", 7) == 0);
        /* a region inside $BA00-$BFFF is part of the ROM window */
        if (r->addr >= 0xBA00u && r->addr + r->size <= 0xC000u) {
            const AssetEntry *win = assets_find(&assets, "rom_ba00");
            for (i = 0; win != NULL && i < r->size; i++) {
                if (r->data[i] != win->data[r->addr - 0xBA00u + i]) {
                    printf("region %s differs from the ROM window at $%04X\n", r->name, (unsigned)(r->addr + i));
                    failures++;
                    break;
                }
            }
        }
    }
    CHECK(regions == 79u);
    CHECK(region_bytes == 2246u);
    CHECK(assets_install_tables(&assets) == ASSETS_OK && tables_ready());
    e = assets_find(&assets, "maze");
    CHECK(e != NULL && e->kind == ASSET_RAM && e->addr == 0x0800u && e->size == MAZE_DATA_SIZE && memcmp(e->data, MAZE_DATA, MAZE_DATA_SIZE) == 0);
    e = assets_find(&assets, "ram_0600");
    CHECK(e != NULL && e->kind == ASSET_RAM && e->addr == 0x0600u && e->size == RAM_0600_SIZE && memcmp(e->data, RAM_0600, RAM_0600_SIZE) == 0);
    e = assets_find(&assets, "rom_ba00");
    CHECK(e != NULL && e->kind == ASSET_ROM_WINDOW && e->addr == 0xBA00u && e->size == ROM_BA00_SIZE && memcmp(e->data, ROM_BA00, ROM_BA00_SIZE) == 0);
    for (k = 0; k < 0x600; k++) {
        CHECK(table_rom((uint16_t)(0xBA00u + k)) == ROM_BA00[k]);
    }
    e = assets_find(&assets, "charset.game");
    CHECK(e != NULL && e->addr == 0x3000u && e->size == 808u);
    e = assets_find(&assets, "charset.title");
    CHECK(e != NULL && e->addr == 0x1808u && e->size == 192u);
    e = assets_find(&assets, "font");
    CHECK(e != NULL && e->addr == 0xE000u && e->size == 512u);
    e = assets_find(&assets, "region.TextHighScore");
    CHECK(e != NULL && e->kind == ASSET_TEXT2 && e->size == 10u);        /* the one mode 2 line (the status row) */
    e = assets_find(&assets, "region.TextPlayerGame");
    CHECK(e != NULL && e->kind == ASSET_TEXT6 && e->size > 0u);
    e = assets_find(&assets, "region.CartridgeHeader");
    CHECK(e != NULL && e->addr == 0xBFFAu && e->size == 6u);
    CHECK(assets_find(&assets, "no such entry") == NULL);
}

int main(int argc, char **argv)
{
    AssetsError err;
    if (argc == 3 && strcmp(argv[1], "--sha256") == 0) {      /* the sha256 of a file (up to 64 KB), as 64 hex digits */
        static uint8_t buf[65537];
        uint8_t h[32];
        PmFile *f = pm_fs_open(argv[2], "rb");
        size_t n, i;
        if (f == NULL) {
            printf("assets_check: cannot open %s\n", argv[2]);
            return 2;
        }
        n = pm_fs_read(f, buf, sizeof buf);
        pm_fs_close(f);
        pm_sha256(buf, n, h);
        for (i = 0; i < 32; i++) {
            printf("%02x", h[i]);
        }
        printf("\n");
        return 0;
    }
    int dump = argc >= 2 && strcmp(argv[1], "--dump") == 0;
    const char *blob = argc >= 2 ? argv[dump ? 2 : 1] : NULL;

    if (blob == NULL || (dump && argc != 4) || (!dump && argc > 3)) {
        printf("usage: assets_check BLOB [IMAGE] | --dump BLOB OUT\n");
        return 2;
    }
    err = assets_load(&assets, blob, blob_buf, sizeof blob_buf);
    if (err != ASSETS_OK) {
        printf("assets_check: error: %s\n", assets_error_text(err));
        return 1;
    }
    if (dump) {
        PmFile *f;
        assets_ram_image(&assets, image);
        f = pm_fs_open(argv[3], "wb");
        if (f == NULL || pm_fs_write(f, image, sizeof image) != sizeof image) {
            printf("assets_check: cannot write %s\n", argv[3]);
            return 2;
        }
        pm_fs_close(f);
        return 0;
    }
    checks();
    assets_ram_image(&assets, image);
    if (argc == 3) {
        if (!read_file(argv[2], expected, sizeof expected)) {
            printf("assets_check: cannot read %s\n", argv[2]);
            return 2;
        }
        CHECK(memcmp(image, expected, sizeof image) == 0);
    }
    if (failures) {
        printf("assets_check: %d failures\n", failures);
        return 1;
    }
    printf("assets_check: ok, %u entries\n", (unsigned)assets.count);
    return 0;
}
