/* The first-run installation of the game's data file from the player's ROM (src/c/assets/rom_install.c; docs/75): the ROM given as bytes (a file chosen anywhere on the machine), refused when it is not the NTSC
 * cartridge, the data file written once, a damaged one replaced, a folder that cannot be written to reported.  Needs the player's ROM at original/Pac-Man.rom (like the other ctest tests that run the game);
 * works in folders below build/rom_install_check, nothing in the main folder. */
#include <stdio.h>
#include <string.h>

#include "../assets/assets.h"
#include "../assets/rom_install.h"
#include "../assets/rom_layout.h"
#include "../platform/fs.h"

static int failures;

#define CHECK(cond)                                                        \
    do {                                                                   \
        if (!(cond)) {                                                     \
            printf("FAILED line %d: %s\n", __LINE__, #cond);               \
            failures++;                                                    \
        }                                                                  \
    } while (0)

static uint8_t rom[ROM_SIZE + 1u], blob_buf[ASSET_BLOB_MAX];

static int exists(const char *path)
{
    PmFile *f = pm_fs_open(path, "rb");
    if (f == NULL) {
        return 0;
    }
    pm_fs_close(f);
    return 1;
}

int main(void)
{
    PmFile *f = pm_fs_open(ROM_DEFAULT_PATH, "rb");
    size_t n;
    Assets a;
    uint8_t bad[ROM_SIZE];
    uint8_t first[ASSET_BLOB_MAX], second[ASSET_BLOB_MAX];
    size_t n1, n2;

    CHECK(f != NULL);
    if (f == NULL) {
        printf("rom_install_check: needs %s\n", ROM_DEFAULT_PATH);
        return 1;
    }
    n = pm_fs_read(f, rom, sizeof rom);
    pm_fs_close(f);
    CHECK(n == ROM_SIZE);
    CHECK(pm_fs_mkdir("build/rom_install_check") == 0);
    CHECK(pm_fs_set_root("build/rom_install_check") == 0);
    CHECK(pm_fs_mkdir("bad") == 0 && pm_fs_mkdir("ok") == 0 && pm_fs_mkdir("blocked") == 0);

    /* not the cartridge: refused, nothing written */
    CHECK(pm_fs_set_root(NULL) == 0);
    CHECK(pm_fs_set_root("build/rom_install_check/bad") == 0);
    CHECK(rom_install_bytes(rom, ROM_SIZE - 1u, ASSET_DEFAULT_PATH) == ROM_BAD_SIZE);
    CHECK(rom_install_bytes(rom, ROM_SIZE + 1u, ASSET_DEFAULT_PATH) == ROM_BAD_SIZE);
    CHECK(rom_install_bytes(rom, 0, ASSET_DEFAULT_PATH) == ROM_BAD_SIZE);
    memcpy(bad, rom, ROM_SIZE);
    bad[1234] ^= 1u;
    CHECK(rom_install_bytes(bad, ROM_SIZE, ASSET_DEFAULT_PATH) == ROM_BAD_HASH);
    memset(bad, 0, sizeof bad);
    CHECK(rom_install_bytes(bad, ROM_SIZE, ASSET_DEFAULT_PATH) == ROM_BAD_HASH);
    CHECK(!exists(ASSET_DEFAULT_PATH));
    CHECK(rom_install("original/Pac-Man.rom", ASSET_DEFAULT_PATH) == ROM_OPEN_FAILED && !exists(ASSET_DEFAULT_PATH));           /* no ROM in this folder */

    /* the cartridge: the data file is written (its folders made), and loads */
    CHECK(pm_fs_set_root(NULL) == 0);
    CHECK(pm_fs_set_root("build/rom_install_check/ok") == 0);
    CHECK(rom_install_bytes(rom, ROM_SIZE, ASSET_DEFAULT_PATH) == ROM_OK);
    CHECK(assets_load(&a, ASSET_DEFAULT_PATH, blob_buf, sizeof blob_buf) == ASSETS_OK);
    f = pm_fs_open(ASSET_DEFAULT_PATH, "rb");
    n1 = f != NULL ? pm_fs_read(f, first, sizeof first) : 0;
    if (f != NULL) {
        pm_fs_close(f);
    }
    CHECK(n1 > 1000);

    /* a damaged data file is replaced by the same bytes (the file is a function of the ROM only) */
    f = pm_fs_open(ASSET_DEFAULT_PATH, "wb");
    CHECK(f != NULL);
    if (f != NULL) {
        pm_fs_write(f, "damaged", 7);
        pm_fs_close(f);
    }
    CHECK(assets_load(&a, ASSET_DEFAULT_PATH, blob_buf, sizeof blob_buf) != ASSETS_OK);
    CHECK(rom_install_bytes(rom, ROM_SIZE, ASSET_DEFAULT_PATH) == ROM_OK);
    CHECK(assets_load(&a, ASSET_DEFAULT_PATH, blob_buf, sizeof blob_buf) == ASSETS_OK);
    f = pm_fs_open(ASSET_DEFAULT_PATH, "rb");
    n2 = f != NULL ? pm_fs_read(f, second, sizeof second) : 0;
    if (f != NULL) {
        pm_fs_close(f);
    }
    CHECK(n1 == n2 && memcmp(first, second, n1) == 0);

    /* a refused ROM does not touch a good data file */
    CHECK(rom_install_bytes(bad, ROM_SIZE, ASSET_DEFAULT_PATH) == ROM_BAD_HASH);
    CHECK(assets_load(&a, ASSET_DEFAULT_PATH, blob_buf, sizeof blob_buf) == ASSETS_OK);

    /* a folder that cannot be written to: a file where the folder `resources` should be */
    CHECK(pm_fs_set_root(NULL) == 0);
    CHECK(pm_fs_set_root("build/rom_install_check/blocked") == 0);
    f = pm_fs_open("resources", "wb");
    CHECK(f != NULL);
    if (f != NULL) {
        pm_fs_write(f, "x", 1);
        pm_fs_close(f);
    }
    CHECK(rom_install_bytes(rom, ROM_SIZE, ASSET_DEFAULT_PATH) == ROM_WRITE_FAILED);
    CHECK(pm_fs_set_root(NULL) == 0);

    if (failures == 0) {
        printf("rom_install_check: OK\n");
        return 0;
    }
    printf("rom_install_check: %d failures\n", failures);
    return 1;
}
