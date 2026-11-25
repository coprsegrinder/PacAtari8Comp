/* The Controls page and the pads (src/c/shell/controls.c, icons.c, haptics.c, padhid.c; docs/71): the table of controls per device, the icons, the rumble / light bar events and the byte layouts of the
 * DualShock 4 and DualSense reports.  Pure: needs no asset blob, no device.  The layouts are checked against reports written out by hand (not against a pad: OV-81). */
#include <stdio.h>
#include <string.h>

#include "../shell/controls.h"
#include "../shell/haptics.h"
#include "../shell/icons.h"
#include "../shell/padhid.h"

static int failures;

#define CHECK(cond)                                                        \
    do {                                                                   \
        if (!(cond)) {                                                     \
            printf("FAILED line %d: %s\n", __LINE__, #cond);               \
            failures++;                                                    \
        }                                                                  \
    } while (0)

/* ------------------------------------------------------------------ the table */

static int has_icon(const ControlRow *rows, int n, int icon)
{
    int i, j;

    for (i = 0; i < n; i++) {
        for (j = 0; j < rows[i].n; j++) {
            if (rows[i].g[j].icon == icon) {
                return 1;
            }
        }
    }
    return 0;
}

static int has_key(const ControlRow *rows, int n, const char *label)
{
    int i, j;

    for (i = 0; i < n; i++) {
        for (j = 0; j < rows[i].n; j++) {
            if (rows[i].g[j].icon == IC_KEY && strcmp(rows[i].g[j].label, label) == 0) {
                return 1;
            }
        }
    }
    return 0;
}

static void test_table(void)
{
    int d;

    for (d = 0; d < CD_COUNT; d++) {
        ControlRow rows[CONTROLS_MAX_ROWS];
        int n = controls_rows(d, rows), i, j;

        CHECK(n >= 6 && n <= CONTROLS_MAX_ROWS);
        CHECK(strlen(controls_device_name(d)) > 3);
        for (i = 0; i < n; i++) {
            CHECK(rows[i].action != NULL && rows[i].action[0] != '\0' && strlen(rows[i].action) <= CONTROLS_ACTION_CHARS);
            CHECK(rows[i].n >= 0 && rows[i].n <= CONTROLS_MAX_GLYPHS);
            CHECK(icon_row_width(rows[i].g, rows[i].n, 3) <= 190);          /* leaves room for the action's text inside the 384 pixel picture */
            for (j = 0; j < rows[i].n; j++) {
                const ControlGlyph *g = &rows[i].g[j];
                CHECK(g->icon > IC_NONE && g->icon < IC_COUNT);
                CHECK((g->icon == IC_KEY) == (g->label != NULL));
            }
        }
    }
    {
        ControlRow k[CONTROLS_MAX_ROWS], x[CONTROLS_MAX_ROWS], p4[CONTROLS_MAX_ROWS], ps[CONTROLS_MAX_ROWS];
        int nk = controls_rows(CD_KEYBOARD, k), nx = controls_rows(CD_XINPUT, x), n4 = controls_rows(CD_DS4, p4), n5 = controls_rows(CD_DUALSENSE, ps);

        CHECK(!controls_is_pad(CD_KEYBOARD) && controls_is_pad(CD_XINPUT) && controls_is_pad(CD_DS4) && controls_is_pad(CD_DUALSENSE));
        CHECK(has_key(k, nk, "F1") && has_key(k, nk, "F2") && has_key(k, nk, "F3") && has_key(k, nk, "F4") && has_key(k, nk, "F11") && has_key(k, nk, "ESC"));   /* the keys the help names */
        CHECK(has_key(k, nk, "CTRL") && has_key(k, nk, "Z") && has_key(k, nk, "X") && has_key(k, nk, "SPACE") && has_key(k, nk, "WASD") && has_icon(k, nk, IC_ARROWS));
        CHECK(!has_icon(x, nx, IC_KEY) && !has_icon(p4, n4, IC_KEY) && !has_icon(ps, n5, IC_KEY));                       /* a pad shows no keys */
        CHECK(has_icon(x, nx, IC_XA) && has_icon(x, nx, IC_XB) && has_icon(x, nx, IC_XX) && has_icon(x, nx, IC_XY) && has_icon(x, nx, IC_XMENU) && has_icon(x, nx, IC_XVIEW));
        CHECK(!has_icon(x, nx, IC_CROSS) && !has_icon(x, nx, IC_OPTIONS));
        CHECK(has_icon(p4, n4, IC_CROSS) && has_icon(p4, n4, IC_CIRCLE) && has_icon(p4, n4, IC_SQUARE) && has_icon(p4, n4, IC_TRIANGLE) && has_icon(p4, n4, IC_OPTIONS) && has_icon(p4, n4, IC_SHARE));
        CHECK(!has_icon(p4, n4, IC_CREATE) && !has_icon(p4, n4, IC_XA));
        CHECK(has_icon(ps, n5, IC_CREATE) && has_icon(ps, n5, IC_OPTIONS) && !has_icon(ps, n5, IC_SHARE) && !has_icon(ps, n5, IC_XA));
    }
}

/* ------------------------------------------------------------------ the icons */

static uint8_t sfont[64 * 8];

#define CW 120
#define CH 40
#define BX 30
#define BY 12

static void test_icons(void)
{
    static uint8_t px[IC_COUNT][CW * CH * 4];
    int id, k;

    for (k = 0; k < (int)sizeof sfont; k++) {                /* a font whose every glyph is a block with a hole: not blank, not solid */
        sfont[k] = (uint8_t)((k & 7) == 0 || (k & 7) == 7 ? 0xFF : 0x81);
    }
    for (id = IC_KEY; id < IC_COUNT; id++) {
        IconCanvas c;
        ControlGlyph g;
        int w, i, j, lit = 0, outside = 0;

        memset(px[id], 0, sizeof px[id]);
        c.bgra = px[id];
        c.w = CW;
        c.h = CH;
        c.font = sfont;
        g.icon = id;
        g.label = id == IC_KEY ? "AB" : NULL;
        w = icon_width(&g);
        CHECK(w > 0 && w <= 60);
        CHECK(icon_draw(&c, BX, BY, &g) == w);
        for (j = 0; j < CH; j++) {
            for (i = 0; i < CW; i++) {
                const uint8_t *p = px[id] + 4 * (j * CW + i);
                if (p[0] != 0 || p[1] != 0 || p[2] != 0) {
                    lit++;
                    if (i < BX || i >= BX + w || j < BY || j >= BY + ICON_H) {
                        outside++;
                    }
                }
            }
        }
        CHECK(outside == 0);                                 /* nothing outside its box */
        CHECK(lit >= 8);                                     /* and something inside it */
    }
    for (id = IC_ARROWS; id < IC_COUNT; id++) {              /* every icon is its own picture */
        for (k = id + 1; k < IC_COUNT; k++) {
            CHECK(memcmp(px[id], px[k], sizeof px[id]) != 0);
        }
    }
    {
        ControlGlyph a = {IC_KEY, "F11"}, b = {IC_KEY, "ESC"};                      /* a keycap is as wide as its label */
        CHECK(icon_width(&a) == 8 * 3 + 6 && icon_width(&b) == icon_width(&a));
        a.label = "F1";
        CHECK(icon_width(&a) == 8 * 2 + 6);
    }
    {
        ControlGlyph row[3] = {{IC_XA, NULL}, {IC_SLASH, NULL}, {IC_XB, NULL}};
        CHECK(icon_row_width(row, 3, 2) == 14 + 8 + 14 + 4);
        CHECK(icon_row_width(row, 0, 2) == 0);
    }
}

/* ------------------------------------------------------------------ the rumble and the light bar */

static HapSnapshot snap(int lives, int death, int fright, int eyes, int done)
{
    HapSnapshot s;

    s.lives = lives;
    s.player = 0;
    s.death_freeze = death;
    s.frightened = fright;
    s.eyes = eyes;
    s.level_complete = done;
    return s;
}

static void test_haptics(void)
{
    Haptics h;
    HapOut o;
    HapSnapshot s;
    int i, last;

    haptics_init(&h);
    s = snap(3, 0, 0, 0, 0);
    haptics_step(&h, &s, &o);                                /* the first snapshot: nothing happened yet */
    CHECK(o.strong == 0 && o.weak == 0 && o.r == 255 && o.b == 0);
    for (i = 0; i < 50; i++) {
        haptics_step(&h, &s, &o);
        CHECK(o.strong == 0 && o.weak == 0);                 /* quiet game, quiet pad */
    }
    s = snap(3, 0, 4, 0, 0);                                 /* a power pellet: all four ghosts frightened */
    haptics_step(&h, &s, &o);
    CHECK(o.weak >= 200 && o.strong < o.weak && o.b == 255 && o.r < 60);   /* a buzz, the light bar blue */
    last = o.weak;
    for (i = 0; i < 30; i++) {
        haptics_step(&h, &s, &o);
        CHECK(o.weak <= last);
        last = o.weak;
        CHECK(o.b == 255);                                   /* blue the whole time they are frightened */
    }
    CHECK(o.weak == 0 && o.strong == 0);                     /* and the buzz is over after a few frames */
    s = snap(3, 0, 3, 1, 0);                                 /* a ghost eaten: a firm knock and a white flash */
    haptics_step(&h, &s, &o);
    CHECK(o.strong >= 200 && o.weak >= 240 && o.r == 255 && o.g == 255 && o.b == 255);
    for (i = 0; i < 30; i++) {
        haptics_step(&h, &s, &o);
    }
    CHECK(o.strong == 0 && o.r == 20 && o.b == 255);         /* back to blue */
    s = snap(3, 0, 0, 0, 0);
    haptics_step(&h, &s, &o);
    CHECK(o.r == 255 && o.g == 190 && o.b == 0 && o.strong == 0);   /* frightened ends: yellow, and ghosts coming back is no event */
    s = snap(2, 96, 0, 0, 0);                                /* caught: the hardest rumble, the light bar red */
    haptics_step(&h, &s, &o);
    CHECK(o.strong == 255 && o.weak == 255 && o.r == 255 && o.g < 20);
    last = 256;
    for (i = 0; i < 100; i++) {
        s = snap(2, 96 - i < 1 ? 0 : 96 - i, 0, 0, 0);
        haptics_step(&h, &s, &o);
        CHECK((int)o.strong <= last);                        /* it only dies away */
        last = o.strong;
    }
    CHECK(o.strong == 0 && o.weak == 0 && o.r == 255 && o.g == 190);
    s = snap(1, 0, 0, 0, 0);                                 /* the next life starts: one life less is not an event */
    haptics_step(&h, &s, &o);
    CHECK(o.strong == 0 && o.weak == 0);
    s = snap(2, 0, 0, 0, 0);                                 /* an extra life */
    haptics_step(&h, &s, &o);
    CHECK(o.strong >= 150 && o.strong < 255);
    for (i = 0; i < 40; i++) {
        haptics_step(&h, &s, &o);
    }
    s = snap(2, 0, 0, 0, 1);                                 /* the board is cleared */
    haptics_step(&h, &s, &o);
    CHECK(o.strong >= 200 && o.weak >= 200);
    haptics_pause(&h, &o);                                   /* a menu: at rest, the effects dropped */
    CHECK(o.strong == 0 && o.weak == 0 && o.r < 100);
    haptics_step(&h, &s, &o);
    CHECK(o.strong == 0 && o.weak == 0);
    {
        Haptics h2;                                          /* the other player's turn is not an event */
        HapSnapshot a = snap(3, 0, 0, 0, 0), b = snap(3, 96, 0, 0, 0);

        haptics_init(&h2);
        haptics_step(&h2, &a, &o);
        b.player = 1;
        haptics_step(&h2, &b, &o);
        CHECK(o.strong == 0);
    }
    haptics_idle(&o);
    CHECK(o.strong == 0 && o.weak == 0 && o.r == 255);
}

/* ------------------------------------------------------------------ the reports of the pads */

static void test_haptics_gold(void)
{
    Haptics h;
    HapSnapshot s;
    HapOut o;
    int i, seen_pulse = 0, golds = 0, lighter = 0, darker = 0;

    memset(&s, 0, sizeof s);
    s.lives = 3;
    haptics_init(&h);
    haptics_step(&h, &s, &o);
    CHECK(o.r == 255 && o.g == 190 && o.b == 0 && o.strong == 0 && o.weak == 0);
    haptics_achievement(&h);
    for (i = 0; i < 100; i++) {                               /* 1.5 s of gold, a pulse of the motors, then yellow again with the motors at rest */
        haptics_step(&h, &s, &o);
        if (o.strong > 0 || o.weak > 0) {
            seen_pulse = 1;
        }
        if (i < 90) {
            golds += o.r == 255 && o.b < 130 && o.g >= 170;
            lighter += o.g == 230;
            darker += o.g == 170;
        }
    }
    CHECK(seen_pulse && golds == 90 && lighter > 20 && darker > 20 && o.r == 255 && o.g == 190 && o.b == 0 && o.strong == 0 && o.weak == 0);
    haptics_achievement(&h);                                  /* a death's red goes first, and the gold waits behind it */
    s.death_freeze = 96;
    haptics_step(&h, &s, &o);
    haptics_step(&h, &s, &o);
    CHECK(o.r == 255 && o.g < 100 && o.b == 0);
    haptics_achievement(&h);                                  /* a menu opened: everything at rest, and no gold afterwards */
    haptics_pause(&h, &o);
    CHECK(o.strong == 0 && o.weak == 0);
    s.death_freeze = 0;
    haptics_step(&h, &s, &o);
    CHECK(o.g == 190 && o.b == 0);
}

static void test_crc(void)
{
    const uint8_t digits[] = "23456789";

    CHECK(padhid_crc32('1', digits, 8) == 0xCBF43926u);      /* the usual check value of CRC-32, "123456789" */
    CHECK(padhid_crc32(0xA2, NULL, 0) == padhid_crc32(0xA2, digits, 0));
}

static void test_kinds(void)
{
    CHECK(padhid_kind(0x054C, 0x05C4) == PAD_DS4 && padhid_kind(0x054C, 0x09CC) == PAD_DS4 && padhid_kind(0x054C, 0x0BA0) == PAD_DS4);
    CHECK(padhid_kind(0x054C, 0x0CE6) == PAD_DUALSENSE && padhid_kind(0x054C, 0x0DF2) == PAD_DUALSENSE);
    CHECK(padhid_kind(0x054C, 0x0001) == PAD_NONE && padhid_kind(0x045E, 0x05C4) == PAD_NONE && padhid_kind(0x045E, 0x0B12) == PAD_NONE);
}

static void test_parse(void)
{
    uint8_t r[80];
    PadState s, keep;
    int hat;
    static const int up[9] = {1, 1, 0, 0, 0, 0, 0, 1, 0}, right[9] = {0, 1, 1, 1, 0, 0, 0, 0, 0}, down[9] = {0, 0, 0, 1, 1, 1, 0, 0, 0}, left[9] = {0, 0, 0, 0, 0, 1, 1, 1, 0};

    /* DualShock 4, USB: id 1, sticks, then the hat and face buttons, the others, the PS button */
    memset(r, 0, sizeof r);
    r[0] = 0x01; r[1] = 0; r[2] = 255; r[3] = 128; r[4] = 128;
    r[5] = (uint8_t)(0x08 | 0x20 | 0x40);                    /* hat released, cross and circle */
    r[6] = 0x20 | 0x10;                                      /* options, share */
    r[7] = 0x01 | 0x02;                                      /* ps, touch pad */
    CHECK(padhid_parse(PAD_DS4, r, 64, &s));
    CHECK(s.lx == -32768 && s.ly == -32512 && !s.up && !s.down && !s.left && !s.right);
    CHECK(s.buttons == (PB_CROSS | PB_CIRCLE | PB_OPTIONS | PB_SHARE | PB_PS | PB_TOUCH));
    for (hat = 0; hat < 9; hat++) {
        r[5] = (uint8_t)(hat | 0x80);
        CHECK(padhid_parse(PAD_DS4, r, 64, &s));
        CHECK(s.up == up[hat] && s.right == right[hat] && s.down == down[hat] && s.left == left[hat] && s.buttons & PB_TRIANGLE);
    }
    r[1] = 128; r[2] = 0;                                    /* the stick pushed up: positive y, as XInput */
    r[5] = 0x08 | 0x10; r[6] = 0x01 | 0x04; r[7] = 0;
    CHECK(padhid_parse(PAD_DS4, r, 64, &s) && s.ly == 32767 && s.lx == 0 && s.buttons == (PB_SQUARE | PB_L1 | PB_L2));
    /* DualShock 4, Bluetooth full report 0x11: the same fields three bytes on */
    memset(r, 0, sizeof r);
    r[0] = 0x11; r[1] = 0xC0; r[2] = 0x00; r[3] = 255; r[4] = 128; r[7] = 0x02 | 0x40;          /* stick right; hat east, circle */
    r[8] = 0x80 | 0x08;                                      /* r2, r3 */
    CHECK(padhid_parse(PAD_DS4, r, 78, &s) && s.lx == 32512 && s.right && !s.left && s.buttons == (PB_CIRCLE | PB_R2 | PB_R3));
    /* the short Bluetooth report before the pad is switched: report 1, 10 bytes */
    memset(r, 0, sizeof r);
    r[0] = 0x01; r[1] = 128; r[2] = 128; r[5] = 0x04 | 0x20; r[6] = 0x20;
    CHECK(padhid_parse(PAD_DS4, r, 10, &s) && s.down && s.buttons == (PB_CROSS | PB_OPTIONS));
    /* DualSense, USB: id 1, sticks, two triggers, a counter, then the buttons at 8, 9, 10 */
    memset(r, 0, sizeof r);
    r[0] = 0x01; r[1] = 255; r[2] = 128; r[3] = 7; r[4] = 9; r[5] = 200; r[6] = 100; r[7] = 55;
    r[8] = 0x06 | 0x40 | 0x10;                               /* hat south-west... 6 = west; circle, square */
    r[9] = 0x10 | 0x20;                                      /* create, options */
    r[10] = 0x01;
    CHECK(padhid_parse(PAD_DUALSENSE, r, 64, &s));
    CHECK(s.lx == 32512 && s.ly == 0 && s.left && !s.up && !s.down && !s.right);
    CHECK(s.buttons == (PB_CIRCLE | PB_SQUARE | PB_SHARE | PB_OPTIONS | PB_PS));
    /* DualSense, Bluetooth full report 0x31: one byte before the fields */
    memset(r, 0, sizeof r);
    r[0] = 0x31; r[1] = 0x01; r[2] = 128; r[3] = 0; r[9] = 0x00 | 0x20; r[10] = 0x20; r[11] = 0x00;     /* stick up, hat north, cross, options */
    CHECK(padhid_parse(PAD_DUALSENSE, r, 78, &s) && s.up && s.ly == 32767 && s.buttons == (PB_CROSS | PB_OPTIONS));
    /* DualSense, the short Bluetooth report */
    memset(r, 0, sizeof r);
    r[0] = 0x01; r[1] = 128; r[2] = 128; r[5] = 0x02 | 0x80; r[6] = 0x10; r[7] = 0x01;
    CHECK(padhid_parse(PAD_DUALSENSE, r, 10, &s) && s.right && s.buttons == (PB_TRIANGLE | PB_SHARE | PB_PS));
    /* what is not a report of the pad is refused and nothing is written */
    memset(&keep, 0x5A, sizeof keep);
    s = keep;
    r[0] = 0x07;
    CHECK(!padhid_parse(PAD_DS4, r, 64, &s) && memcmp(&s, &keep, sizeof s) == 0);
    CHECK(!padhid_parse(PAD_DUALSENSE, r, 64, &s) && !padhid_parse(PAD_NONE, r, 64, &s) && !padhid_parse(PAD_DS4, NULL, 0, &s));
    r[0] = 0x11;
    CHECK(!padhid_parse(PAD_DS4, r, 5, &s) && !padhid_parse(PAD_DUALSENSE, r, 78, &s));
    r[0] = 0x31;
    CHECK(!padhid_parse(PAD_DS4, r, 78, &s) && !padhid_parse(PAD_DUALSENSE, r, 8, &s));
    CHECK(memcmp(&s, &keep, sizeof s) == 0);
}

static void check_crc(const uint8_t *b, size_t len)
{
    uint32_t c = padhid_crc32(0xA2, b, 74);

    CHECK(len == 78);
    CHECK(b[74] == (uint8_t)c && b[75] == (uint8_t)(c >> 8) && b[76] == (uint8_t)(c >> 16) && b[77] == (uint8_t)(c >> 24));
}

static void test_output(void)
{
    uint8_t b[PADHID_OUT_MAX];
    size_t len;

    /* DualShock 4, USB: report 5, flags, small motor at 4, big motor at 5, the colour at 6 to 8 */
    memset(b, 0xEE, sizeof b);
    len = padhid_build_output(PAD_DS4, 0, 0, 0, 200, 100, 1, 2, 3, b);
    CHECK(len == 32 && b[0] == 0x05 && b[1] == 0x03 && b[2] == 0x04 && b[4] == 100 && b[5] == 200 && b[6] == 1 && b[7] == 2 && b[8] == 3);
    CHECK(b[3] == 0 && b[9] == 0 && b[10] == 0 && b[31] == 0);   /* no blinking, the rest zero */
    /* DualShock 4, Bluetooth: report 0x11 with the same fields three bytes on and the CRC */
    len = padhid_build_output(PAD_DS4, 1, 0, 0, 200, 100, 1, 2, 3, b);
    CHECK(b[0] == 0x11 && b[1] == 0xC0 && b[3] == 0x03 && b[4] == 0x04 && b[6] == 100 && b[7] == 200 && b[8] == 1 && b[9] == 2 && b[10] == 3);
    check_crc(b, len);
    /* DualSense, USB: report 2, flags 0 and 1, motors at 3 (right, small) and 4 (left, big), flag 2 at 39, the colour at 45 to 47 */
    len = padhid_build_output(PAD_DUALSENSE, 0, 0, 0, 200, 100, 10, 20, 30, b);
    CHECK(len == 63 && b[0] == 0x02 && b[1] == 0x03 && b[2] == 0x04 && b[3] == 100 && b[4] == 200 && b[39] == 0x04 && b[42] == 0 && b[45] == 10 && b[46] == 20 && b[47] == 30);
    len = padhid_build_output(PAD_DUALSENSE, 0, 0, 1, 0, 0, 10, 20, 30, b);      /* the first one also puts the start-up light out */
    CHECK(b[39] == 0x06 && b[42] == 2 && b[3] == 0 && b[4] == 0);
    /* DualSense, Bluetooth: report 0x31, a counter in the high nibble, tag 0x10, the fields three bytes on, the CRC */
    len = padhid_build_output(PAD_DUALSENSE, 1, 0x1B, 0, 200, 100, 10, 20, 30, b);
    CHECK(b[0] == 0x31 && b[1] == 0xB0 && b[2] == 0x10 && b[3] == 0x03 && b[4] == 0x04 && b[5] == 100 && b[6] == 200 && b[41] == 0x04 && b[47] == 10 && b[48] == 20 && b[49] == 30);
    check_crc(b, len);
    CHECK(padhid_build_output(PAD_NONE, 0, 0, 0, 1, 1, 1, 1, 1, b) == 0);
    {
        uint8_t b2[PADHID_OUT_MAX];                          /* a changed byte changes the CRC */
        (void)padhid_build_output(PAD_DUALSENSE, 1, 0x1B, 0, 201, 100, 10, 20, 30, b2);
        CHECK(memcmp(b + 74, b2 + 74, 4) != 0);
    }
}

int main(void)
{
    test_table();
    test_icons();
    test_haptics();
    test_haptics_gold();
    test_crc();
    test_kinds();
    test_parse();
    test_output();
    if (failures == 0) {
        printf("controls_check: OK\n");
        return 0;
    }
    printf("controls_check: %d failures\n", failures);
    return 1;
}
