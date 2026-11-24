/* assets/install_assets.c - the installer as a program (stage 80a): checks the owner's NTSC Pac-Man ROM and writes the asset blob.
 *   install_assets [ROM [BLOB]]     defaults: original/Pac-Man.rom, resources/pack/assets.pmab (relative to the main folder, through platform/fs.c)
 * Exit 0 and "install_assets: ok" on success; 1 and "install_assets: error: <text>" when the ROM is missing or is not the NTSC cartridge (nothing is written). */
#include <stdio.h>

#include "../platform/fs.h"
#include "rom_install.h"

int main(int argc, char **argv)
{
    const char *rom = argc > 1 ? argv[1] : ROM_DEFAULT_PATH;
    const char *blob = argc > 2 ? argv[2] : ASSET_DEFAULT_PATH;
    RomError e;

    if (argc > 3) {
        printf("usage: install_assets [ROM [BLOB]]\n");
        return 2;
    }
    e = rom_install(rom, blob);
    if (e != ROM_OK) {
        printf("install_assets: error: %s\n", rom_error_text(e));
        return 1;
    }
    printf("install_assets: ok (%s -> %s)\n", rom, blob);
    return 0;
}
