/* Stage 75a: checks of the generated World and tables (src/c/core/world.[ch], tables.[ch]).
 *   world_check                  self test (ctest): no files
 *   world_check IN OUT DUMP      loads the 64 KB image IN into a World, stores it to OUT (a 64 KB image, zero except the stored regions),
 *                                writes DUMP: every region and every table by name (tests/test_c_world.py compares it with tools/core_world.py and core_tables.py)
 * Paths are relative to the main folder (the working directory), opened through platform/fs.c (stage 75b). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../core/tables.h"
#include "../core/world.h"
#include "../platform/fs.h"
#include "boot_tables.h"

static int failures;

#define CHECK(cond)                                                        \
    do {                                                                   \
        if (!(cond)) {                                                     \
            printf("FAILED line %d: %s\n", __LINE__, #cond);               \
            failures++;                                                    \
        }                                                                  \
    } while (0)

static World world, world2;
static uint8_t image[65536], back[65536];

static int self_test(void)
{
    size_t i, k;
    uint32_t n;

    /* the struct holds the regions at the offsets the table says, without overlap */
    for (i = 0; i < PM_WORLD_REGIONS; i++) {
        const WorldRegion *r = &world_regions[i];
        CHECK(r->offset + r->count <= offsetof(World, pokey_addr));
        for (k = i + 1; k < PM_WORLD_REGIONS; k++) {
            const WorldRegion *s = &world_regions[k];
            CHECK(r->offset + r->count <= s->offset || s->offset + s->count <= r->offset);
        }
    }
    CHECK(offsetof(World, GameState) == world_regions[0x19].offset);   /* the 26th field of the sorted table is $19 (every address of $00-$19 has its own field) */

    /* a patterned image: load, store, the stored regions come back, everything else stays zero */
    for (i = 0; i < 65536; i++) {
        image[i] = (uint8_t)((i * 131u + (i >> 8) * 7u + 1u) & 0xFFu);
    }
    world_init(&world);
    world_load(&world, image);
    memset(back, 0, sizeof back);
    world_store(&world, back);
    for (i = 0; i < PM_WORLD_REGIONS; i++) {
        const WorldRegion *r = &world_regions[i];
        if (r->stored) {
            /* the later regions win where two overlap: compare what is in `back` with the image only where no later stored region covers it */
            for (k = 0; k < r->count; k++) {
                size_t a = (size_t)r->addr + k;
                size_t j;
                int covered = 0;
                for (j = i + 1; j < PM_WORLD_REGIONS; j++) {
                    const WorldRegion *s = &world_regions[j];
                    if (s->stored && a >= s->addr && a < (size_t)s->addr + s->count) {
                        covered = 1;
                    }
                }
                if (!covered) {
                    CHECK(back[a] == image[a]);
                }
            }
        }
    }
    CHECK(back[0x0C00] == image[0x0C00] && back[0x0FFF] == image[0x0FFF]);   /* the maze */
    CHECK(back[0x2300] == image[0x2300] && back[0x27FF] == image[0x27FF]);   /* the player-missile pages */
    CHECK(back[0xD008] == 0 && back[0xD00F] == 0);                           /* the collision registers are an input: never stored */
    CHECK(back[0x0100] == 0 && back[0x0500] == 0 && back[0x2800] == 0 && back[0xA000] == 0);     /* outside every region */
    CHECK(back[0x0800] == image[0x0800] && back[0x1000] == image[0x1000] && back[0x1400] == image[0x1400] && back[0x1C00] == image[0x1C00]);   /* the saved mazes and the title screen (78a) */
    CHECK(world.collide[3] == image[0xD003]);

    /* load then load again from a different image: the second replaces everything */
    for (i = 0; i < 65536; i++) {
        image[i] = (uint8_t)(255u - (i & 0xFFu));
    }
    world_pokey(&world, 0xD200, 1);
    world_load(&world, image);
    CHECK(world.pokey_n == 0);
    world_init(&world2);
    world_load(&world2, image);
    CHECK(memcmp(&world, &world2, offsetof(World, pokey_addr)) == 0);

    /* the chip-write log: in order, bounded, with an overflow count */
    world_init(&world);
    for (n = 0; n < PM_POKEY_MAX + 5; n++) {
        world_pokey(&world, (uint16_t)(0xD200u + (n & 15u)), (uint8_t)n);
    }
    CHECK(world.pokey_n == PM_POKEY_MAX);
    CHECK(world.pokey_overflow == 5);
    CHECK(world.pokey_addr[17] == 0xD201 && world.pokey_val[17] == 17);

    /* the tables */
    CHECK(PM_TABLE_COUNT == 17);
    CHECK(JUNCTION_Y[0] == 0x2C && JUNCTION_X[9] == 0xBE && MOVE_DELAY[23] == 0x02);
    for (i = 0; i < PM_TABLE_COUNT; i++) {
        const TableInfo *t = &table_info[i];
        CHECK(t->data != NULL && t->count > 0);
        if (t->is_rom) {
            CHECK(t->addr >= 0xBA00u);
        }
    }
    for (i = 0; i < 0x200; i++) {
        CHECK(table_ram((uint16_t)(0x0600 + i)) == RAM_0600[i]);
    }
    for (i = 0; i < 0x600; i++) {
        CHECK(table_rom((uint16_t)(0xBA00 + i)) == ROM_BA00[i]);
    }
    /* the table copies in the images agree with the separate tables */
    for (i = 0; i < 100; i++) {
        CHECK(JUNCTION_EXITS[i] == table_ram((uint16_t)(0x060E + i)));
    }
    for (i = 0; i < 256; i++) {
        CHECK(FRIGHT_FRAMES[i] == table_rom((uint16_t)(0xBBF8 + i)));
        CHECK(FRIGHT_END[i] == table_ram((uint16_t)(0x0672 + i)));
    }

    if (failures == 0) {
        printf("world_check: OK (%d regions, %d tables)\n", PM_WORLD_REGIONS, PM_TABLE_COUNT);
        return 0;
    }
    printf("world_check: %d failures\n", failures);
    return 1;
}

static void hex(PmFile *f, const uint8_t *p, size_t n)
{
    size_t i;
    for (i = 0; i < n; i++) {
        pm_fs_printf(f, "%02x", p[i]);
    }
}

static int dump_mode(const char *in, const char *out, const char *dump)
{
    PmFile *f;
    size_t i;

    f = pm_fs_open(in, "rb");
    if (f == NULL || pm_fs_read(f, image, 65536) != 65536) {
        printf("cannot read a 64 KB image from %s\n", in);
        return 2;
    }
    pm_fs_close(f);
    world_init(&world);
    world_load(&world, image);
    memset(back, 0, sizeof back);
    world_store(&world, back);
    f = pm_fs_open(out, "wb");
    if (f == NULL || pm_fs_write(f, back, 65536) != 65536) {
        printf("cannot write %s\n", out);
        return 2;
    }
    pm_fs_close(f);
    f = pm_fs_open(dump, "wb");
    if (f == NULL) {
        printf("cannot write %s\n", dump);
        return 2;
    }
    for (i = 0; i < PM_WORLD_REGIONS; i++) {
        const WorldRegion *r = &world_regions[i];
        pm_fs_printf(f, "R %s %u %u ", r->name, (unsigned)r->addr, (unsigned)r->count);
        hex(f, (const uint8_t *)&world + r->offset, r->count);
        pm_fs_printf(f, "\n");
    }
    for (i = 0; i < PM_TABLE_COUNT; i++) {
        const TableInfo *t = &table_info[i];
        pm_fs_printf(f, "T %s %u %u ", t->name, (unsigned)t->addr, (unsigned)t->count);
        hex(f, t->data, t->count);
        pm_fs_printf(f, "\n");
    }
    pm_fs_printf(f, "S %u\n", (unsigned)PM_WORLD_REGIONS);
    pm_fs_close(f);
    return 0;
}

int main(int argc, char **argv)
{
    if (boot_tables() != 0) {
        return 2;
    }
    if (argc == 4) {
        return dump_mode(argv[1], argv[2], argv[3]);
    }
    return self_test();
}
