/* The settings kept between runs (src/c/shell/settings.c; docs/73): the menu's settings as text and back.  Pure: no files. */
#include <stdio.h>
#include <string.h>

#include "../shell/settings.h"

static int failures;

#define CHECK(cond)                                                        \
    do {                                                                   \
        if (!(cond)) {                                                     \
            printf("FAILED line %d: %s\n", __LINE__, #cond);               \
            failures++;                                                    \
        }                                                                  \
    } while (0)

static int same(const Menu *a, const Menu *b)
{
    return a->fullscreen == b->fullscreen && a->res == b->res && a->fps == b->fps && a->crt == b->crt && a->vibration == b->vibration && a->lightbar == b->lightbar && a->sound_volume == b->sound_volume &&
           a->sound_mute == b->sound_mute && a->sound_filter == b->sound_filter;
}

int main(void)
{
    Menu a, b, d;
    char text[SETTINGS_MAX_TEXT], small[20];
    size_t n;
    int i, j;

    menu_init(&d, 1, 9, 0, 0);                                /* the defaults */
    menu_init(&a, 0, 5, 0, 0);
    n = settings_format(&a, text, sizeof text);               /* the defaults make a file that gives the defaults back */
    CHECK(n > 0 && n == strlen(text) && n < SETTINGS_MAX_TEXT && settings_format(&a, small, sizeof small) == 0);
    menu_init(&b, 1, 9, 0, 0);
    CHECK(settings_parse(&b, text) == 9);
    CHECK(b.fullscreen == 0 && b.res == 5 && b.sound_volume == 10 && b.vibration == 2 && b.sound_filter == 1);

    for (i = 0; i < menu_resolution_count; i++) {             /* every choice survives the round trip */
        for (j = 0; j < menu_fps_count; j++) {
            menu_init(&a, i & 1, i, 0, 0);
            a.fps = j;
            a.crt = (i + j) % menu_crt_count;
            a.vibration = (i + j) % 3;
            a.lightbar = (i * 2 + j) % 3;
            a.sound_volume = (i + j) % 11;
            a.sound_mute = (i + j) & 1;
            a.sound_filter = (i + 2 * j) % 3;
            n = settings_format(&a, text, sizeof text);
            menu_init(&b, 0, 0, 0, 0);
            CHECK(n > 0 && settings_parse(&b, text) == 9 && same(&a, &b));
        }
    }

    menu_init(&b, 1, 9, 0, 0);                                /* nothing, junk, a damaged file: the defaults stay */
    CHECK(settings_parse(&b, "") == 0 && same(&b, &d));
    CHECK(settings_parse(&b, "\x01\x02 garbage \xff=\n=\n====\nvolume\n") == 0 && same(&b, &d));
    CHECK(settings_parse(&b, "volume=abc\nvolume=-5\nvolume=101\nvolume=5x\nmute=maybe\noutput_filter=loud\nfps=75x\nfps=61\nresolution=123x456\nresolution=1280x720x\ncrt_shader=vhs\ndisplay_mode=both\nvibration=max\n") == 0 && same(&b, &d));

    CHECK(settings_parse(&b, "# a comment\n  Volume = 70  \r\nMUTE=ON\r\nunknown_key=1\nfps=native\n") == 3);   /* spaces, capitals, CR LF, an unknown line */
    CHECK(b.sound_volume == 7 && b.sound_mute == 1 && menu_fps(&b) == MENU_FPS_NATIVE);
    CHECK(settings_parse(&b, "fps=uncapped\nvolume=44\nresolution=1920x1080\n") == 3 && menu_fps(&b) == MENU_FPS_UNCAPPED && b.sound_volume == 4 && menu_resolutions[b.res].w == 1920);
    CHECK(settings_parse(&b, "volume=0\nvolume=100\n") == 2 && b.sound_volume == 10);        /* the last good line wins */
    CHECK(settings_parse(&b, "volume=95\n") == 1 && b.sound_volume == 10);                   /* rounded to the nearest tenth */

    menu_init(&b, 0, -1, 384, 240);                           /* a window of its own size has no entry in the list: "window", and it is not taken back */
    n = settings_format(&b, text, sizeof text);
    CHECK(n > 0 && strstr(text, "resolution=window") != NULL);
    menu_init(&a, 1, 9, 0, 0);
    CHECK(settings_parse(&a, text) == 8 && a.res == 9);

    if (failures == 0) {
        printf("settings_check: OK\n");
        return 0;
    }
    printf("settings_check: %d failures\n", failures);
    return 1;
}
