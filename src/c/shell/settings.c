/* shell/settings.c - the menu's settings as text and back (docs/73); see settings.h. */
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "settings.h"

static const char *const crt_keys[4] = {"off", "guest", "zfast", "aperture"};
static const char *const level_keys[3] = {"off", "light", "heavy"};
static const char *const filter_keys[3] = {"off", "soft", "warm"};

size_t settings_format(const Menu *m, char *buf, size_t cap)
{
    int w, h, n, fps = menu_fps(m);
    char fpsbuf[16];
    char resbuf[24];

    if (fps == MENU_FPS_NATIVE) {
        snprintf(fpsbuf, sizeof fpsbuf, "native");
    } else if (fps == MENU_FPS_UNCAPPED) {
        snprintf(fpsbuf, sizeof fpsbuf, "uncapped");
    } else {
        snprintf(fpsbuf, sizeof fpsbuf, "%d", fps);
    }
    if (m->res >= 0) {
        menu_size(m, &w, &h);
        snprintf(resbuf, sizeof resbuf, "%dx%d", w, h);
    } else {
        snprintf(resbuf, sizeof resbuf, "window");
    }
    n = snprintf(buf, cap,
                 "# Pac-Man (Atari 8-bit) C port: the pause menu's settings, kept between runs.\n"
                 "# Edit with the game closed, or delete this file to go back to the defaults.\n"
                 "version=1\n"
                 "display_mode=%s\n"
                 "resolution=%s\n"
                 "fps=%s\n"
                 "crt_shader=%s\n"
                 "vibration=%s\n"
                 "light_bar=%s\n"
                 "volume=%d\n"
                 "mute=%s\n"
                 "output_filter=%s\n",
                 m->fullscreen ? "fullscreen" : "windowed", resbuf, fpsbuf, crt_keys[(m->crt >= 0 && m->crt < 4) ? m->crt : 0], level_keys[(m->vibration >= 0 && m->vibration < 3) ? m->vibration : 2],
                 level_keys[(m->lightbar >= 0 && m->lightbar < 3) ? m->lightbar : 2], m->sound_volume * 10, m->sound_mute ? "on" : "off", filter_keys[(m->sound_filter >= 0 && m->sound_filter < 3) ? m->sound_filter : 1]);
    return (n > 0 && (size_t)n < cap) ? (size_t)n : 0;
}

static int index_of(const char *const *keys, int count, const char *v)
{
    int i;

    for (i = 0; i < count; i++) {
        if (strcmp(keys[i], v) == 0) {
            return i;
        }
    }
    return -1;
}

/* a whole non-negative number, nothing else (-1 when it is not one) */
static long number_of(const char *v)
{
    char *end;
    long n;

    if (*v == '\0' || !isdigit((unsigned char)*v)) {
        return -1;
    }
    n = strtol(v, &end, 10);
    return (*end == '\0' && n < 100000) ? n : -1;
}

static int take(Menu *m, const char *key, const char *v)
{
    int i;
    long n;

    if (strcmp(key, "display_mode") == 0) {
        if (strcmp(v, "fullscreen") == 0 || strcmp(v, "windowed") == 0) {
            m->fullscreen = v[0] == 'f';
            return 1;
        }
    } else if (strcmp(key, "resolution") == 0) {
        int w, h;
        char x;
        if (sscanf(v, "%dx%d%c", &w, &h, &x) == 2) {
            for (i = 0; i < menu_resolution_count; i++) {
                if (menu_resolutions[i].w == w && menu_resolutions[i].h == h) {
                    m->res = i;
                    return 1;
                }
            }
        }
    } else if (strcmp(key, "fps") == 0) {
        int want = strcmp(v, "native") == 0 ? MENU_FPS_NATIVE : strcmp(v, "uncapped") == 0 ? MENU_FPS_UNCAPPED : (int)number_of(v);
        for (i = 0; want != -1 && i < menu_fps_count; i++) {
            if (menu_fps_values[i] == want) {
                m->fps = i;
                return 1;
            }
        }
    } else if (strcmp(key, "crt_shader") == 0) {
        i = index_of(crt_keys, 4, v);
        if (i >= 0 && i < menu_crt_count) {
            m->crt = i;
            return 1;
        }
    } else if (strcmp(key, "vibration") == 0 || strcmp(key, "light_bar") == 0) {
        i = index_of(level_keys, 3, v);
        if (i >= 0) {
            if (key[0] == 'v') {
                m->vibration = i;
            } else {
                m->lightbar = i;
            }
            return 1;
        }
    } else if (strcmp(key, "volume") == 0) {
        n = number_of(v);
        if (n >= 0 && n <= 100) {
            m->sound_volume = (int)((n + 5) / 10);
            return 1;
        }
    } else if (strcmp(key, "mute") == 0) {
        if (strcmp(v, "on") == 0 || strcmp(v, "off") == 0) {
            m->sound_mute = v[1] == 'n';
            return 1;
        }
    } else if (strcmp(key, "output_filter") == 0) {
        i = index_of(filter_keys, 3, v);
        if (i >= 0) {
            m->sound_filter = i;
            return 1;
        }
    }
    return 0;
}

int settings_parse(Menu *m, const char *text)
{
    char line[160];
    int taken = 0;
    const char *p = text;

    while (*p != '\0') {
        size_t n = 0;
        char *eq, *k, *v, *e;

        while (*p != '\0' && *p != '\n') {
            if (n + 1 < sizeof line) {
                line[n++] = *p;
            }
            p++;
        }
        if (*p == '\n') {
            p++;
        }
        line[n] = '\0';
        k = line;
        while (*k == ' ' || *k == '\t' || *k == '\r') {
            k++;
        }
        if (*k == '#' || *k == '\0') {
            continue;
        }
        eq = strchr(k, '=');
        if (eq == NULL) {
            continue;
        }
        *eq = '\0';
        v = eq + 1;
        e = eq;
        while (e > k && (e[-1] == ' ' || e[-1] == '\t')) {
            *--e = '\0';
        }
        while (*v == ' ' || *v == '\t') {
            v++;
        }
        e = v + strlen(v);
        while (e > v && (e[-1] == ' ' || e[-1] == '\t' || e[-1] == '\r')) {
            *--e = '\0';
        }
        for (e = k; *e != '\0'; e++) {
            *e = (char)tolower((unsigned char)*e);
        }
        for (e = v; *e != '\0'; e++) {
            *e = (char)tolower((unsigned char)*e);
        }
        taken += take(m, k, v);
    }
    return taken;
}
