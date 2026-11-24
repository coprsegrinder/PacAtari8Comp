/* The pause menu and the graphics options (src/c/shell/menu.c, docs/68): the key paths, and the layout of the picture for every resolution of the list.  Pure: needs no asset blob. */
#include <stdio.h>
#include <string.h>

#include "../shell/menu.h"

static int failures;

#define CHECK(cond)                                                        \
    do {                                                                   \
        if (!(cond)) {                                                     \
            printf("FAILED line %d: %s\n", __LINE__, #cond);               \
            failures++;                                                    \
        }                                                                  \
    } while (0)

static void test_navigation(void)
{
    Menu m;
    MenuLine l[MENU_MAX_LINES];
    int i;

    menu_init(&m, 0, 5, 0, 0);
    CHECK(!menu_is_open(&m));
    menu_key(&m, MK_UP);                                   /* nothing happens while it is closed, except ESC */
    menu_key(&m, MK_SELECT);
    CHECK(!menu_is_open(&m) && !m.quit && !m.changed);
    menu_key(&m, MK_BACK);
    CHECK(m.screen == MENU_MAIN && m.cursor == 0);
    menu_key(&m, MK_BACK);                                 /* ESC in the main menu resumes */
    CHECK(!menu_is_open(&m));
    menu_key(&m, MK_BACK);
    menu_key(&m, MK_SELECT);                               /* Resume Game */
    CHECK(!menu_is_open(&m) && !m.quit);

    menu_key(&m, MK_BACK);
    menu_key(&m, MK_UP);                                   /* wraps to Quit Game */
    CHECK(m.cursor == 2);
    menu_key(&m, MK_DOWN);
    CHECK(m.cursor == 0);
    menu_key(&m, MK_DOWN);
    menu_key(&m, MK_SELECT);                               /* Graphics Options */
    CHECK(m.screen == MENU_GRAPHICS && m.cursor == 0);
    menu_key(&m, MK_BACK);                                 /* ESC goes back to the main menu, on Graphics Options */
    CHECK(m.screen == MENU_MAIN && m.cursor == 1);
    menu_key(&m, MK_SELECT);
    menu_key(&m, MK_BACK);
    menu_key(&m, MK_BACK);                                 /* and ESC again resumes */
    CHECK(!menu_is_open(&m) && !m.changed);

    menu_key(&m, MK_BACK);
    menu_key(&m, MK_UP);
    menu_key(&m, MK_SELECT);                               /* Quit Game */
    CHECK(m.quit == 1);

    menu_init(&m, 0, 5, 0, 0);                             /* the display mode */
    menu_key(&m, MK_BACK);
    menu_key(&m, MK_DOWN);
    menu_key(&m, MK_SELECT);
    menu_key(&m, MK_RIGHT);
    CHECK(m.fullscreen == 1 && m.changed == 1);
    m.changed = 0;
    menu_key(&m, MK_LEFT);
    CHECK(m.fullscreen == 0 && m.changed == 1);
    m.changed = 0;
    menu_key(&m, MK_DOWN);                                 /* the resolution: every one in turn, both ways round */
    for (i = 0; i < menu_resolution_count; i++) {
        menu_key(&m, MK_RIGHT);
        CHECK(m.res == (5 + 1 + i) % menu_resolution_count && m.changed == 1);
        m.changed = 0;
    }
    CHECK(m.res == 5);
    menu_key(&m, MK_LEFT);
    CHECK(m.res == 4);
    menu_init(&m, 0, -1, 1152, 720);                       /* a window size from the command line is not in the list */
    CHECK(m.res == -1);
    menu_key(&m, MK_BACK);
    menu_key(&m, MK_DOWN);
    menu_key(&m, MK_SELECT);
    menu_key(&m, MK_DOWN);
    menu_lines(&m, l);
    CHECK(strstr(l[3].text, "1152 X 720") != NULL);
    menu_key(&m, MK_RIGHT);
    CHECK(m.res == 0);
}

static void test_fps(void)
{
    Menu m;
    MenuLine l[MENU_MAX_LINES];
    int i, n, start;

    /* the list: native, 30 to 180, uncapped: no "monitor" or "default" entry */
    CHECK(menu_fps_values[0] == MENU_FPS_NATIVE && menu_fps_values[menu_fps_count - 1] == MENU_FPS_UNCAPPED);
    CHECK(menu_fps_values[1] == 30 && menu_fps_values[menu_fps_count - 2] == 180 && menu_fps_count == 10);
    for (i = 2; i < menu_fps_count - 1; i++) {
        CHECK(menu_fps_values[i] > menu_fps_values[i - 1] && menu_fps_values[i] <= 180);
    }
    /* the entry for a monitor: its rate when the list has it, else the nearest number (a tie to the higher); native and uncapped are never picked */
    for (i = 1; i < menu_fps_count - 1; i++) {
        CHECK(menu_fps_values[menu_fps_nearest(menu_fps_values[i])] == menu_fps_values[i]);       /* every number of the list finds itself */
    }
    CHECK(menu_fps_values[menu_fps_nearest(60)] == 60 && menu_fps_values[menu_fps_nearest(59)] == 60 && menu_fps_values[menu_fps_nearest(61)] == 60);
    CHECK(menu_fps_values[menu_fps_nearest(100)] == 90 && menu_fps_values[menu_fps_nearest(105)] == 120 && menu_fps_values[menu_fps_nearest(110)] == 120);
    CHECK(menu_fps_values[menu_fps_nearest(240)] == 180 && menu_fps_values[menu_fps_nearest(360)] == 180 && menu_fps_values[menu_fps_nearest(25)] == 30);
    CHECK(menu_fps_values[menu_fps_nearest(48)] == 60 && menu_fps_values[menu_fps_nearest(50)] == 60 && menu_fps_values[menu_fps_nearest(72)] == 75 && menu_fps_values[menu_fps_nearest(70)] == 75);
    CHECK(menu_fps_values[menu_fps_nearest(0)] == 60 && menu_fps_values[menu_fps_nearest(-5)] == 60);   /* not known: 60 */
    CHECK(menu_fps_values[menu_fps_nearest(143)] == 144 && menu_fps_values[menu_fps_nearest(165)] == 165 && menu_fps_values[menu_fps_nearest(170)] == 165 && menu_fps_values[menu_fps_nearest(175)] == 180);

    menu_init(&m, 0, 5, 0, 0);
    CHECK(menu_fps(&m) == 60);                              /* before the front end has found the monitor */
    m.fps = menu_fps_nearest(180);
    CHECK(menu_fps(&m) == 180);
    menu_key(&m, MK_BACK);
    menu_key(&m, MK_DOWN);
    menu_key(&m, MK_SELECT);                               /* the graphics options */
    menu_key(&m, MK_DOWN);
    menu_key(&m, MK_DOWN);
    CHECK(m.cursor == 2 && !m.fps_changed && !m.changed);
    n = menu_lines(&m, l);
    CHECK(n == 7 && l[4].item && l[4].selected && strstr(l[4].text, "FPS: < 180 >") != NULL);
    start = m.fps;
    menu_key(&m, MK_RIGHT);
    CHECK(m.fps == start + 1 && m.fps_changed && !m.changed && menu_fps(&m) == MENU_FPS_UNCAPPED);
    menu_lines(&m, l);
    CHECK(strstr(l[4].text, "UNCAPPED") != NULL);
    m.fps_changed = 0;
    menu_key(&m, MK_RIGHT);                                /* round to native */
    CHECK(m.fps == 0 && menu_fps(&m) == MENU_FPS_NATIVE);
    menu_lines(&m, l);
    CHECK(strstr(l[4].text, "NATIVE (59.92)") != NULL);
    menu_key(&m, MK_RIGHT);
    CHECK(m.fps == 1 && menu_fps(&m) == 30);
    menu_lines(&m, l);
    CHECK(strstr(l[4].text, "FPS: < 30 >") != NULL);
    menu_key(&m, MK_LEFT);                                 /* and back */
    CHECK(menu_fps(&m) == MENU_FPS_NATIVE);
    menu_key(&m, MK_SELECT);
    CHECK(m.fps == 1);
    m.fps_changed = 0;
    menu_key(&m, MK_UP);                                   /* the other items are still there and do not touch the FPS */
    menu_key(&m, MK_RIGHT);
    CHECK(m.res != 5 && m.changed && !m.fps_changed && m.fps == 1);
    menu_key(&m, MK_UP);
    menu_key(&m, MK_RIGHT);
    CHECK(m.fullscreen == 1 && m.fps == 1);
    menu_key(&m, MK_UP);                                   /* wrap: up from the display mode is the FPS */
    CHECK(m.cursor == 2);
}

static void test_nearest_resolution(void)
{
    int i;

    for (i = 0; i < menu_resolution_count; i++) {          /* a monitor that is in the list finds itself */
        CHECK(menu_res_nearest(menu_resolutions[i].w, menu_resolutions[i].h) == i);
    }
    CHECK(menu_res_nearest(2560, 1440) == 9 && menu_resolutions[menu_res_nearest(2560, 1440)].h == 1440);
    CHECK(menu_resolutions[menu_res_nearest(1920, 1080)].w == 1920 && menu_resolutions[menu_res_nearest(1920, 1080)].h == 1080);
    CHECK(menu_resolutions[menu_res_nearest(3440, 1440)].w == 3440);
    /* a size that is not in the list: the nearest one */
    CHECK(menu_resolutions[menu_res_nearest(1536, 864)].w == 1600 && menu_resolutions[menu_res_nearest(1536, 864)].h == 900);        /* a 1920 x 1080 laptop at 125 % */
    CHECK(menu_resolutions[menu_res_nearest(2880, 1800)].w == 2560 && menu_resolutions[menu_res_nearest(2880, 1800)].h == 1600);     /* a 16:10 laptop panel */
    CHECK(menu_resolutions[menu_res_nearest(2736, 1824)].w == 2560 && menu_resolutions[menu_res_nearest(2736, 1824)].h == 1600);     /* a 3:2 tablet */
    CHECK(menu_resolutions[menu_res_nearest(1366, 768)].w == 1366 && menu_resolutions[menu_res_nearest(1360, 768)].w == 1366);
    CHECK(menu_resolutions[menu_res_nearest(7680, 4320)].w == 5120 || menu_resolutions[menu_res_nearest(7680, 4320)].w == 3840);     /* beyond the list: its largest */
    CHECK(menu_resolutions[menu_res_nearest(320, 200)].w == 640 && menu_resolutions[menu_res_nearest(320, 200)].h == 480);
}

static void test_help(void)
{
    Menu m;
    MenuLine l[MENU_MAX_LINES];
    int n, i, k;
    static const char *const none[] = {"ARROW", "WASD", "FIRE", "STICK", "JOYSTICK", "ESC", "ENTER", "SPACE", "CTRL", "MOVE", "PAUSE"};

    menu_init(&m, 0, 5, 0, 0);                             /* from the game */
    menu_key(&m, MK_HELP);
    CHECK(m.screen == MENU_HELP && menu_is_open(&m) && !m.changed && !m.quit);
    menu_key(&m, MK_UP);                                   /* nothing but closing does anything in the help */
    menu_key(&m, MK_RIGHT);
    menu_key(&m, MK_DOWN);
    CHECK(m.screen == MENU_HELP && !m.changed && !m.quit);
    menu_key(&m, MK_HELP);                                 /* F1 closes it, back to the game */
    CHECK(m.screen == MENU_CLOSED);
    menu_key(&m, MK_HELP);
    menu_key(&m, MK_BACK);                                 /* ESC closes it too */
    CHECK(m.screen == MENU_CLOSED);
    menu_key(&m, MK_BACK);                                 /* from the pause menu: back to the pause menu, on the same item */
    menu_key(&m, MK_DOWN);
    menu_key(&m, MK_HELP);
    CHECK(m.screen == MENU_HELP);
    menu_key(&m, MK_SELECT);
    CHECK(m.screen == MENU_MAIN && m.cursor == 1);
    menu_key(&m, MK_SELECT);                               /* from the graphics options */
    menu_key(&m, MK_DOWN);
    menu_key(&m, MK_HELP);
    menu_key(&m, MK_HELP);
    CHECK(m.screen == MENU_GRAPHICS && m.cursor == 1 && !m.changed);
    menu_key(&m, MK_BACK);
    menu_key(&m, MK_BACK);
    CHECK(!menu_is_open(&m));
    menu_key(&m, MK_HELP);                                 /* the text: only function keys */
    n = menu_lines(&m, l);
    CHECK(n > 3 && l[0].heading);
    for (i = 1; i < n; i++) {
        CHECK(!l[i].item && !l[i].selected);
        for (k = 0; k < (int)(sizeof none / sizeof none[0]); k++) {
            CHECK(strstr(l[i].text, none[k]) == NULL);
        }
    }
    CHECK(strstr(l[2].text, "F1 ") && strstr(l[3].text, "F2 ") && strstr(l[4].text, "F3 ") && strstr(l[5].text, "F4 ") && strstr(l[6].text, "F11 "));
    for (i = 2; i <= 6; i++) {
        CHECK(l[i].text[0] == 'F' && strlen(l[i].text) == strlen(l[2].text));
    }
}

static void test_text(void)
{
    Menu m;
    MenuLine l[MENU_MAX_LINES];
    int n, items = 0, sel = 0, i;

    menu_init(&m, 1, 8, 0, 0);
    CHECK(menu_lines(&m, l) == 0);
    menu_key(&m, MK_BACK);
    n = menu_lines(&m, l);
    for (i = 0; i < n; i++) {
        items += l[i].item;
        sel += l[i].selected;
    }
    CHECK(n > 0 && items == 3 && sel == 1);
    CHECK(strstr(l[2].text, "RESUME GAME") && strstr(l[3].text, "GRAPHICS OPTIONS") && strstr(l[4].text, "QUIT GAME"));
    menu_key(&m, MK_DOWN);
    menu_key(&m, MK_SELECT);
    n = menu_lines(&m, l);
    items = sel = 0;
    for (i = 0; i < n; i++) {
        items += l[i].item;
        sel += l[i].selected;
    }
    CHECK(items == 3 && sel == 1);
    CHECK(strstr(l[2].text, "BORDERLESS FULLSCREEN") != NULL);
    CHECK(strstr(l[3].text, "1920 X 1080 (16:9)") != NULL);
    menu_key(&m, MK_LEFT);
    menu_lines(&m, l);
    CHECK(strstr(l[2].text, "WINDOWED") != NULL);
}

static void test_list(void)
{
    int i, k, n43 = 0, n169 = 0, n1610 = 0, n219 = 0;

    for (i = 0; i < menu_resolution_count; i++) {
        const MenuResolution *r = &menu_resolutions[i];
        long w = r->w, h = r->h;

        if (strcmp(r->aspect, "4:3") == 0) {
            n43++;
            CHECK(w * 3 == h * 4);
        } else if (strcmp(r->aspect, "16:9") == 0) {
            n169++;
            CHECK(w * 9 / 16 - h <= 8 && h - w * 9 / 16 <= 8);          /* 1366 x 768 is the usual 16:9 panel */
        } else if (strcmp(r->aspect, "16:10") == 0) {
            n1610++;
            CHECK(w * 10 == h * 16);
        } else if (strcmp(r->aspect, "21:9") == 0) {
            n219++;
            CHECK(w * 9 >= h * 20 && w * 9 <= h * 24);                  /* 2560 x 1080, 3440 x 1440, 3840 x 1600, 5120 x 2160 are all sold as 21:9 */
        }
        for (k = 0; k < i; k++) {
            CHECK(menu_resolutions[k].w != r->w || menu_resolutions[k].h != r->h);
        }
    }
    CHECK(n43 >= 3 && n169 >= 3 && n1610 >= 3 && n219 >= 3);
}

static void test_fit(void)
{
    DisplayRect r;
    int i, cw, ch;

    for (i = 0; i < menu_resolution_count; i++) {
        cw = menu_resolutions[i].w;
        ch = menu_resolutions[i].h;
        display_fit(cw, ch, cw, ch, &r);
        CHECK((r.w >= MENU_PICTURE_W && r.h >= MENU_PICTURE_H) || cw < MENU_PICTURE_W);
        CHECK((long)r.w * 240 == (long)r.h * 384 || r.integer == 0);   /* a whole-number scale is exactly 1.6 : 1 */
        CHECK(r.w <= cw && r.h <= ch && r.x >= 0 && r.y >= 0 && r.x + r.w <= cw && r.y + r.h <= ch);
        CHECK(r.x == (cw - r.w) / 2 && r.y == (ch - r.h) / 2);        /* centred */
        CHECK(r.w - (long)r.h * 384 / 240 <= 1 && r.w - (long)r.h * 384 / 240 >= -1);   /* the proportions are the picture's, to a pixel */
        CHECK(r.w == cw || r.h == ch || r.integer);                    /* it touches the area on one axis, unless a whole-number scale is used */
    }
    display_fit(1280, 720, 1280, 720, &r);                              /* 3 x exactly */
    CHECK(r.integer && r.scale_num == 3 && r.w == 1152 && r.h == 720 && r.x == 64 && r.y == 0);
    display_fit(1920, 1080, 1920, 1080, &r);                            /* 4 x: 89 % of what fits */
    CHECK(r.integer && r.scale_num == 4 && r.w == 1536 && r.h == 960 && r.x == 192 && r.y == 60);
    display_fit(2560, 1440, 2560, 1440, &r);
    CHECK(r.integer && r.scale_num == 6 && r.w == 2304 && r.h == 1440);
    display_fit(3840, 2160, 3840, 2160, &r);
    CHECK(r.integer && r.scale_num == 9 && r.w == 3456 && r.h == 2160);
    display_fit(1600, 900, 1600, 900, &r);                              /* 3 x would leave 20 %: scaled to fit */
    CHECK(!r.integer && r.w == 1440 && r.h == 900 && r.x == 80 && r.y == 0);
    display_fit(3440, 1440, 3440, 1440, &r);                            /* ultrawide: pillarboxed, 6 x */
    CHECK(r.integer && r.scale_num == 6 && r.w == 2304 && r.h == 1440 && r.x == 568 && r.y == 0);
    display_fit(5120, 2160, 5120, 2160, &r);
    CHECK(r.integer && r.scale_num == 9 && r.h == 2160 && r.x == (5120 - r.w) / 2);
    display_fit(640, 480, 640, 480, &r);                                /* 1 x would be 60 %: 640 x 400 */
    CHECK(!r.integer && r.w == 640 && r.h == 400 && r.y == 40);
    display_fit(320, 200, 320, 200, &r);                                /* smaller than the picture: scaled down, still 1.6 : 1 */
    CHECK(!r.integer && r.w == 320 && r.h == 200);
    display_fit(3840, 2160, 1280, 720, &r);                             /* an area smaller than the screen (borderless): centred in it */
    CHECK(r.integer && r.w == 1152 && r.h == 720 && r.x == (3840 - 1280) / 2 + 64 && r.y == (2160 - 720) / 2);
    display_fit(1920, 1080, 3840, 2160, &r);                            /* an area larger than the screen is clamped to it */
    CHECK(r.w == 1536 && r.h == 960);
    display_fit(1000, 1000, 1000, 1000, &r);                            /* a square area: the picture is wider than tall and not stretched */
    CHECK(r.w == 1000 && r.h == 625 && r.y == 187);
}

int main(void)
{
    test_navigation();
    test_help();
    test_fps();
    test_nearest_resolution();
    test_text();
    test_list();
    test_fit();
    if (failures == 0) {
        printf("menu_check: OK\n");
        return 0;
    }
    printf("menu_check: %d failures\n", failures);
    return 1;
}
