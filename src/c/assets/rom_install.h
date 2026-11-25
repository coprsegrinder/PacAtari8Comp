/* assets/rom_install.h - install the port's assets from the owner's own cartridge image (stage 80a).
 * The port carries no byte of the ROM in its sources for this: it reads the NTSC Pac-Man cartridge (8,192 bytes, `original/Pac-Man.rom` by default), recognises it by size and sha256, cuts out the 79 regions
 * that are not code (rom_layout.c), expands the compressed pictures and tables the way the game's own start-up does (the character sets, the maze, the tables at $0600) and writes the asset blob that
 * assets.c reads.  A ROM that is not this one is refused and nothing is written.  Only the NTSC cartridge is supported; there is no PAL data. */
#ifndef PM_ASSETS_ROM_INSTALL_H
#define PM_ASSETS_ROM_INSTALL_H

#include <stddef.h>
#include <stdint.h>

#define ROM_DEFAULT_PATH "original/Pac-Man.rom"
#define ASSET_DEFAULT_PATH "resources/pack/assets.pmab"
#define ASSET_BLOB_MAX 16384u       /* the blob is about 7.8 KB */

/* why the ROM is refused or the blob cannot be made */
typedef enum RomError {
    ROM_OK = 0,
    ROM_OPEN_FAILED,
    ROM_BAD_SIZE,
    ROM_BAD_HASH,
    ROM_BAD_STREAM,         /* a compressed stream runs outside the ROM or does not give the size the game expands it to */
    ROM_BUFFER_TOO_SMALL,
    ROM_WRITE_FAILED
} RomError;

const char *rom_error_text(RomError e);   /* the text of a RomError */

/* ROM_OK when `rom` is the NTSC cartridge: exactly ROM_SIZE bytes with the sha256 of ROM_SHA256 */
RomError rom_check(const uint8_t *rom, size_t size);

/* check, then build the blob in memory: `out` holds *len bytes on ROM_OK */
RomError rom_build_blob(const uint8_t *rom, size_t size, uint8_t *out, size_t cap, size_t *len);

/* the same from a ROM already in memory (the player's own file chosen anywhere on the machine: it is read once and never copied into the game folder) */
RomError rom_install_bytes(const uint8_t *rom, size_t size, const char *blob_path);

/* read the ROM from `rom_path`, check it, build the blob and write it to `blob_path` (both relative to the main folder, through platform/fs.c).  Nothing is written unless everything succeeded. */
RomError rom_install(const char *rom_path, const char *blob_path);

#endif
