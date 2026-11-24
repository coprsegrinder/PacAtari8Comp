/* assets/assets.h - the asset blob (stage 80a, docs/47, docs/51).  The blob is written by tools/make_c_assets.py (derived from the ROM, not committed);
 * its byte format is documented there: little-endian, read one byte at a time, a trailer with an FNV-1a checksum.
 * The loader keeps pointers into the caller's buffer: the buffer must outlive the Assets.  Nothing here allocates. */
#ifndef PM_ASSETS_ASSETS_H
#define PM_ASSETS_ASSETS_H

#include <stddef.h>
#include <stdint.h>

#define ASSETS_VERSION 1
#define ASSETS_SCHEMA 2
#define ASSETS_MAX_ENTRIES 128
#define ASSETS_NAME_MAX 63

/* what an entry of the asset blob is */
typedef enum AssetKind {
    ASSET_REGION = 0,   /* a region of the ROM that is not code (addr = its ROM address) */
    ASSET_TEXT2 = 1,    /* a text line, ANTIC mode 2 screen codes */
    ASSET_TEXT6 = 2,    /* a text line, ANTIC mode 6 screen codes (the colour in the top two bits) */
    ASSET_RAM = 3,      /* a part of the RAM image the original builds (addr = its RAM address) */
    ASSET_ROM_WINDOW = 4 /* a window of the ROM image, code bytes included (addr = its ROM address): what the core indexes into */
} AssetKind;

/* why a blob is refused or cannot be loaded */
typedef enum AssetsError {
    ASSETS_OK = 0,
    ASSETS_TOO_SHORT,
    ASSETS_BAD_MAGIC,
    ASSETS_BAD_VERSION,
    ASSETS_BAD_SCHEMA,
    ASSETS_TOO_MANY,
    ASSETS_BAD_ENTRY,       /* a name, a kind or a size that is not allowed, or an entry that runs past the end */
    ASSETS_DUPLICATE,
    ASSETS_BAD_CHECKSUM,
    ASSETS_TRAILING,        /* bytes between the last entry and the trailer */
    ASSETS_OPEN_FAILED,
    ASSETS_READ_FAILED,
    ASSETS_TOO_BIG          /* the file does not fit the buffer */
} AssetsError;

/* one named entry of the blob: kind, address in the original's memory, size, and its bytes */
typedef struct AssetEntry {
    char name[ASSETS_NAME_MAX + 1];
    uint8_t kind;
    uint32_t addr;
    uint32_t size;
    const uint8_t *data;
} AssetEntry;

/* a parsed blob: the SHA-256 of the ROM it was made from, and its entries */
typedef struct Assets {
    uint8_t rom_sha256[32];
    uint16_t count;
    AssetEntry entry[ASSETS_MAX_ENTRIES];
} Assets;

const char *assets_error_text(AssetsError e);   /* the text of an AssetsError */

/* parse a blob held in memory; on an error `a` is left empty (count 0) */
AssetsError assets_parse(Assets *a, const uint8_t *blob, size_t size);

/* read the file `path` (relative to the main folder, through platform/fs.c) into `buf` (capacity `cap`) and parse it */
AssetsError assets_load(Assets *a, const char *path, uint8_t *buf, size_t cap);

/* the entry called `name`, or NULL */
const AssetEntry *assets_find(const Assets *a, const char *name);

/* the 64 KB image with every ASSET_RAM entry at its address (the rest zero): the character sets, the maze, the tables at $0600 and the OS font page, as `Start` and the OS leave them */
void assets_ram_image(const Assets *a, uint8_t image[65536]);

/* hand the tables the core indexes (the RAM tables at $0600, the ROM window $BA00-$BFFF, the maze) to core/tables.c; ASSETS_BAD_ENTRY when one is missing or has the wrong size */
AssetsError assets_install_tables(const Assets *a);

/* load the blob `path` (relative to the main folder) and install the tables: the one call a program makes at start-up */
AssetsError assets_boot(const char *path);

/* 1 when every ASSET_RAM entry fits inside 64 KB and no two of them overlap */
int assets_ram_layout_ok(const Assets *a);

#endif
