/* shell/menu.c - the pause menu and the graphics options (docs/68); see menu.h. */
#include <stdio.h>
#include <string.h>

#include "menu.h"

const MenuResolution menu_resolutions[] = {
    {640, 480, "4:3"},    {800, 600, "4:3"},    {1024, 768, "4:3"},   {1280, 960, "4:3"},   {1600, 1200, "4:3"},
    {1280, 720, "16:9"},  {1366, 768, "16:9"},  {1600, 900, "16:9"},  {1920, 1080, "16:9"}, {2560, 1440, "16:9"}, {3840, 2160, "16:9"},
    {1280, 800, "16:10"}, {1440, 900, "16:10"}, {1680, 1050, "16:10"}, {1920, 1200, "16:10"}, {2560, 1600, "16:10"},
    {2560, 1080, "21:9"}, {3440, 1440, "21:9"}, {3840, 1600, "21:9"}, {5120, 2160, "21:9"},
};
const int menu_resolution_count = (int)(sizeof menu_resolutions / sizeof menu_resolutions[0]);

#define MAIN_ITEMS 3        /* Resume Game, Graphics Options, Quit Game */
#define GRAPHICS_ITEMS 2    /* Display Mode, Resolution */

void menu_init(Menu *m, int fullscreen, int res, int custom_w, int custom_h)
{
    memset(m, 0, sizeof *m);
    m->fullscreen = fullscreen != 0;
    m->res = (res >= 0 && res < menu_resolution_count) ? res : -1;
    m->custom_w = custom_w;
    m->custom_h = custom_h;
}

int menu_is_open(const Menu *m)
{
    return m->screen != MENU_CLOSED;
}

void menu_size(const Menu *m, int *w, int *h)
{
    if (m->res >= 0) {
        *w = menu_resolutions[m->res].w;
        *h = menu_resolutions[m->res].h;
    } else {
        *w = m->custom_w;
        *h = m->custom_h;
    }
}

static void step_resolution(Menu *m, int dir)
{
    int n = menu_resolution_count;

    if (m->res < 0) {
        m->res = dir > 0 ? 0 : n - 1;
    } else {
        m->res = (m->res + dir + n) % n;
    }
    m->changed = 1;
}

static void toggle_mode(Menu *m)
{
    m->fullscreen = !m->fullscreen;
    m->changed = 1;
}

void menu_key(Menu *m, MenuKey k)
{
    if (m->screen == MENU_CLOSED) {
        if (k == MK_BACK) {
            m->screen = MENU_MAIN;
            m->cursor = 0;
        }
        return;
    }
    if (m->screen == MENU_MAIN) {
        switch (k) {
        case MK_UP:
            m->cursor = (m->cursor + MAIN_ITEMS - 1) % MAIN_ITEMS;
            break;
        case MK_DOWN:
            m->cursor = (m->cursor + 1) % MAIN_ITEMS;
            break;
        case MK_BACK:
            m->screen = MENU_CLOSED;                     /* ESC in the main menu resumes */
            break;
        case MK_SELECT:
            if (m->cursor == 0) {
                m->screen = MENU_CLOSED;
            } else if (m->cursor == 1) {
                m->screen = MENU_GRAPHICS;
                m->cursor = 0;
            } else {
                m->quit = 1;
            }
            break;
        default:
            break;
        }
        return;
    }
    switch (k) {                                          /* the graphics options */
    case MK_UP:
        m->cursor = (m->cursor + GRAPHICS_ITEMS - 1) % GRAPHICS_ITEMS;
        break;
    case MK_DOWN:
        m->cursor = (m->cursor + 1) % GRAPHICS_ITEMS;
        break;
    case MK_BACK:
        m->screen = MENU_MAIN;
        m->cursor = 1;                                    /* back on "Graphics Options" */
        break;
    case MK_LEFT:
    case MK_RIGHT:
    case MK_SELECT:
        if (m->cursor == 0) {
            toggle_mode(m);
        } else {
            step_resolution(m, k == MK_LEFT ? -1 : 1);
        }
        break;
    default:
        break;
    }
}

static void put_line(MenuLine *l, const char *text, int heading, int item, int selected)
{
    snprintf(l->text, sizeof l->text, "%s", text);
    l->heading = heading;
    l->item = item;
    l->selected = selected;
}

int menu_lines(const Menu *m, MenuLine out[MENU_MAX_LINES])
{
    int n = 0, w, h;
    char buf[MENU_LINE_CHARS];

    memset(out, 0, sizeof(MenuLine) * MENU_MAX_LINES);
    if (m->screen == MENU_MAIN) {
        put_line(&out[n++], "PAUSED", 1, 0, 0);
        put_line(&out[n++], "", 0, 0, 0);
        put_line(&out[n++], "RESUME GAME", 0, 1, m->cursor == 0);
        put_line(&out[n++], "GRAPHICS OPTIONS", 0, 1, m->cursor == 1);
        put_line(&out[n++], "QUIT GAME", 0, 1, m->cursor == 2);
        put_line(&out[n++], "", 0, 0, 0);
        put_line(&out[n++], "ESC: RESUME", 0, 0, 0);
    } else if (m->screen == MENU_GRAPHICS) {
        menu_size(m, &w, &h);
        put_line(&out[n++], "GRAPHICS OPTIONS", 1, 0, 0);
        put_line(&out[n++], "", 0, 0, 0);
        snprintf(buf, sizeof buf, "DISPLAY MODE: < %s >", m->fullscreen ? "BORDERLESS FULLSCREEN" : "WINDOWED");
        put_line(&out[n++], buf, 0, 1, m->cursor == 0);
        snprintf(buf, sizeof buf, "RESOLUTION: < %d X %d (%s) >", w, h, m->res >= 0 ? menu_resolutions[m->res].aspect : "WINDOW");
        put_line(&out[n++], buf, 0, 1, m->cursor == 1);
        put_line(&out[n++], "", 0, 0, 0);
        put_line(&out[n++], "ESC: BACK", 0, 0, 0);
    }
    return n;
}

void display_fit(int cw, int ch, int aw, int ah, DisplayRect *r)
{
    int fw, fh, s, ox, oy;

    if (aw > cw) {
        aw = cw;
    }
    if (ah > ch) {
        ah = ch;
    }
    if (aw < 1 || ah < 1) {
        memset(r, 0, sizeof *r);
        r->scale_num = r->scale_den = 1;
        return;
    }
    if ((long)aw * MENU_PICTURE_H <= (long)ah * MENU_PICTURE_W) {         /* the largest 1.6 : 1 picture inside the area */
        fw = aw;
        fh = (int)((long)aw * MENU_PICTURE_H / MENU_PICTURE_W);
    } else {
        fh = ah;
        fw = (int)((long)ah * MENU_PICTURE_W / MENU_PICTURE_H);
    }
    s = aw / MENU_PICTURE_W;
    if (ah / MENU_PICTURE_H < s) {
        s = ah / MENU_PICTURE_H;
    }
    if (s >= 1 && (long)s * MENU_PICTURE_W * 100 >= (long)fw * MENU_FILL_PERCENT) {
        r->w = s * MENU_PICTURE_W;
        r->h = s * MENU_PICTURE_H;
        r->scale_num = s;
        r->scale_den = 1;
        r->integer = 1;
    } else {
        r->w = fw;
        r->h = fh;
        r->scale_num = fw;
        r->scale_den = MENU_PICTURE_W;
        r->integer = 0;
    }
    ox = (cw - aw) / 2;
    oy = (ch - ah) / 2;
    r->x = ox + (aw - r->w) / 2;
    r->y = oy + (ah - r->h) / 2;
}
