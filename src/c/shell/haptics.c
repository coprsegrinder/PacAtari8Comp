/* shell/haptics.c - the rumble and the light bar of the pad (docs/71); see haptics.h. */
#include <string.h>

#include "haptics.h"

#define PELLET_STRONG 140
#define PELLET_WEAK 230
#define PELLET_FRAMES 22
#define EATEN_STRONG 230
#define EATEN_WEAK 255
#define EATEN_FRAMES 28
#define DEATH_STRONG 255
#define DEATH_WEAK 255
#define DEATH_FRAMES 80
#define LIFE_STRONG 180
#define LIFE_WEAK 230
#define LIFE_FRAMES 36
#define BOARD_STRONG 220
#define BOARD_WEAK 220
#define BOARD_FRAMES 44
#define FLASH_FRAMES 12
#define GOLD_FRAMES 90
#define GOLD_STRONG 110
#define GOLD_WEAK 170
#define GOLD_PULSE_FRAMES 16

void haptics_init(Haptics *h)
{
    memset(h, 0, sizeof *h);
}

static void add(Haptics *h, int strong, int weak, int frames, int shape)
{
    int i, slot = 0, least = 1 << 30;

    for (i = 0; i < HAP_MAX_EFFECTS; i++) {
        if (h->fx[i].left <= 0) {
            slot = i;
            break;
        }
        if (h->fx[i].left < least) {                         /* all busy: the one nearest its end is replaced */
            least = h->fx[i].left;
            slot = i;
        }
    }
    h->fx[slot].left = frames;
    h->fx[slot].total = frames;
    h->fx[slot].strong = strong;
    h->fx[slot].weak = weak;
    h->fx[slot].shape = shape;
}

static int level_of(const HapEffect *e, int v)
{
    long k;

    if (e->left <= 0 || e->total <= 0) {
        return 0;
    }
    if (e->shape == 1) {                                     /* full until the last quarter, then down */
        int tail = e->total / 4;
        k = e->left > tail ? 256 : (long)e->left * 256 / (tail > 0 ? tail : 1);
    } else {
        k = (long)e->left * 256 / e->total;
    }
    return (int)((long)v * k / 256);
}

void haptics_achievement(Haptics *h)
{
    add(h, GOLD_STRONG, GOLD_WEAK, GOLD_PULSE_FRAMES, 1);
    h->gold = GOLD_FRAMES;
}

void haptics_idle(HapOut *out)
{
    out->strong = 0;
    out->weak = 0;
    out->r = 255;                                            /* Pac-Man yellow */
    out->g = 190;
    out->b = 0;
}

void haptics_pause(Haptics *h, HapOut *out)
{
    memset(h->fx, 0, sizeof h->fx);
    h->flash = 0;
    h->dying = 0;
    h->gold = 0;
    out->strong = 0;
    out->weak = 0;
    out->r = 70;
    out->g = 55;
    out->b = 0;
}

void haptics_step(Haptics *h, const HapSnapshot *s, HapOut *out)
{
    int i, strong = 0, weak = 0;

    if (h->have_prev && h->prev.player == s->player) {
        if (s->death_freeze != 0 && h->prev.death_freeze == 0) {                 /* caught */
            add(h, DEATH_STRONG, DEATH_WEAK, DEATH_FRAMES, 1);
            h->dying = DEATH_FRAMES;
        }
        if (s->frightened > h->prev.frightened) {                                /* a power pellet (a ghost joins the frightened ones) */
            add(h, PELLET_STRONG, PELLET_WEAK, PELLET_FRAMES, 1);
        }
        if (s->eyes > h->prev.eyes) {                                            /* a ghost eaten */
            add(h, EATEN_STRONG, EATEN_WEAK, EATEN_FRAMES, 1);
            h->flash = FLASH_FRAMES;
        }
        if (s->lives > h->prev.lives && h->prev.lives > 0 && s->death_freeze == 0 && h->prev.death_freeze == 0) {   /* an extra life (the start of a life takes one: that is a fall) */
            add(h, LIFE_STRONG, LIFE_WEAK, LIFE_FRAMES, 1);
        }
        if (s->level_complete != 0 && h->prev.level_complete == 0) {             /* the board is cleared */
            add(h, BOARD_STRONG, BOARD_WEAK, BOARD_FRAMES, 1);
        }
    }
    h->prev = *s;
    h->have_prev = 1;

    for (i = 0; i < HAP_MAX_EFFECTS; i++) {
        int a = level_of(&h->fx[i], h->fx[i].strong), b = level_of(&h->fx[i], h->fx[i].weak);
        if (a > strong) {
            strong = a;
        }
        if (b > weak) {
            weak = b;
        }
        if (h->fx[i].left > 0) {
            h->fx[i].left--;
        }
    }
    out->strong = (uint8_t)(strong > 255 ? 255 : strong);
    out->weak = (uint8_t)(weak > 255 ? 255 : weak);

    if (h->dying > 0) {                                      /* red, fading back to yellow */
        int k = h->dying * 255 / DEATH_FRAMES;
        out->r = 255;
        out->g = (uint8_t)(190 * (255 - k) / 255);
        out->b = 0;
        h->dying--;
    } else if (h->gold > 0) {                                /* gold, with a lighter gold every 8 frames, for an achievement */
        int on = (h->gold / 8) & 1;
        out->r = 255;
        out->g = on ? 230 : 170;
        out->b = on ? 120 : 0;
        h->gold--;
    } else if (h->flash > 0) {                               /* white for a ghost eaten */
        out->r = 255;
        out->g = 255;
        out->b = 255;
        h->flash--;
    } else if (s->frightened > 0) {                          /* blue while the ghosts are frightened */
        out->r = 20;
        out->g = 50;
        out->b = 255;
    } else {
        out->r = 255;
        out->g = 190;
        out->b = 0;
    }
}
