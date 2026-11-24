/* Stage 80b: draws one frame of a World image with the renderer (src/c/render) and writes the colour bytes.
 *   render_check IMAGE HPOS OUT [PREV]   IMAGE: a 64 KB memory image (the World is loaded from it), HPOS: HPOSP0-3,HPOSM0-3 as eight decimal numbers separated by commas,
 *                                    OUT: RENDER_W * RENDER_H colour bytes.  Two frames are drawn and the second is written: the first is the World of the image PREV (default: the same
 *                                    image), because the colours of a frame are the OS shadows of the frame before.
 * The tables and the character sets come from the asset blob (install_assets).  Paths are relative to the main folder. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../assets/assets.h"
#include "../assets/rom_install.h"
#include "../core/world.h"
#include "../platform/fs.h"
#include "../render/render.h"
#include "boot_tables.h"

static uint8_t blob_buf[16384];
static uint8_t image[65536], ram_image[65536];
static uint8_t colour[RENDER_W * RENDER_H];
static Assets assets;
static World world, prev;
static Renderer renderer;

int main(int argc, char **argv)
{
    PmFile *f;
    int h[8], i;

    if ((argc != 4 && argc != 5) || sscanf(argv[2], "%d,%d,%d,%d,%d,%d,%d,%d", &h[0], &h[1], &h[2], &h[3], &h[4], &h[5], &h[6], &h[7]) != 8) {
        printf("usage: render_check IMAGE HPOS OUT\n");
        return 2;
    }
    if (boot_tables() != 0) {
        return 2;
    }
    if (assets_load(&assets, ASSET_DEFAULT_PATH, blob_buf, sizeof blob_buf) != ASSETS_OK) {
        printf("cannot load the asset blob\n");
        return 2;
    }
    assets_ram_image(&assets, ram_image);
    f = pm_fs_open(argv[1], "rb");
    if (f == NULL || pm_fs_read(f, image, sizeof image) != sizeof image) {
        printf("cannot read a 64 KB image from %s\n", argv[1]);
        return 2;
    }
    pm_fs_close(f);
    world_init(&world);
    world_init(&prev);
    world_load(&world, image);
    for (i = 0; i < 8; i++) {
        world.hpos[i] = (uint8_t)h[i];
    }
    render_init(&renderer, ram_image);
    if (argc == 5) {
        f = pm_fs_open(argv[4], "rb");
        if (f == NULL || pm_fs_read(f, image, sizeof image) != sizeof image) {
            printf("cannot read a 64 KB image from %s\n", argv[4]);
            return 2;
        }
        pm_fs_close(f);
        world_load(&prev, image);
        render_frame(&renderer, &prev, colour);
    } else {
        render_frame(&renderer, &world, colour);
    }
    render_frame(&renderer, &world, colour);
    f = pm_fs_open(argv[3], "wb");
    if (f == NULL || pm_fs_write(f, colour, sizeof colour) != sizeof colour) {
        printf("cannot write %s\n", argv[3]);
        return 2;
    }
    pm_fs_close(f);
    printf("render_check: ok\n");
    return 0;
}
