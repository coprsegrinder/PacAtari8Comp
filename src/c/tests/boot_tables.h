/* tests/boot_tables.h - what every test program that uses the core's tables does first (stage 80a): installs them from the asset blob,
 * which install_assets makes from the owner's ROM.  Without the blob the tables are zero and the program refuses to run (exit 2). */
#ifndef PM_TESTS_BOOT_TABLES_H
#define PM_TESTS_BOOT_TABLES_H

#include <stdio.h>

#include "../assets/assets.h"
#include "../assets/rom_install.h"

/* 0 when the tables are installed, 2 (to be returned from main) when not */
static int boot_tables(void)
{
    AssetsError e = assets_boot(ASSET_DEFAULT_PATH);

    if (e != ASSETS_OK) {
        printf("tables not installed: %s: %s (run install_assets with the ROM in original/)\n", ASSET_DEFAULT_PATH, assets_error_text(e));
        return 2;
    }
    return 0;
}

#endif
