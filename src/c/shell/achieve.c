/* shell/achieve.c - the achievements (docs/74); see achieve.h. */
#include <string.h>

#include "achieve.h"
#include "sha256.h"

const AchDef ach_defs[ACH_COUNT] = {
    {"FIRST BITE", "EAT A DOT", 0, 0, 0, 0},
    {"POWER UP", "EAT A POWER PELLET", 0, 0, 0, 0},
    {"GHOST BUSTER", "EAT A GHOST", 0, 0, 0, 0},
    {"DOUBLE TROUBLE", "EAT 2 GHOSTS WITH ONE PELLET", 0, 0, 0, 0},
    {"TRIPLE THREAT", "EAT 3 GHOSTS WITH ONE PELLET", 0, 0, 0, 0},
    {"GHOST SWEEP", "EAT ALL 4 GHOSTS WITH ONE PELLET", 0, 0, 0, 0},
    {"CLEAN SWEEP", "CLEAR A BOARD WITHOUT DYING", 0, 0, 0, 0},
    {"CLOSE CALL", "EAT A GHOST WITH ANOTHER CLOSE BY", 0, 0, 0, 0},
    {"FRUIT SALAD", "EAT THE FRUIT ON 3 BOARDS IN A GAME", 0, 0, 0, 0},
    {"BONUS LIFE", "EARN AN EXTRA LIFE AT 10,000", 0, 0, 0, 1},
    {"HIGH ROLLER", "SCORE 50,000 POINTS", 0, 0, 0, 1},
    {"SIX FIGURES", "SCORE 100,000 POINTS", 0, 0, 0, 1},
    {"ARCADE LEGEND", "SCORE 250,000 POINTS", 0, 0, 0, 1},
    {"NEW RECORD", "BEAT A HIGH SCORE OVER 1,000", 0, 0, 0, 1},
    {"WARMING UP", "REACH LEVEL 3", 0, 0, 0, 1},
    {"FIVE ALIVE", "REACH LEVEL 5", 0, 0, 0, 1},
    {"VETERAN", "REACH LEVEL 8", 0, 0, 0, 1},
    {"UNSTOPPABLE", "REACH LEVEL 12", 0, 0, 0, 1},
    {"MARATHON", "PLAY ONE GAME FOR 15 MINUTES", 0, 0, 0, 0},
    {"SURVIVOR", "CLEAR 3 BOARDS IN A ROW, NO DEATHS", 0, 0, 0, 0},
    {"DOT COLLECTOR", "EAT 1,000 DOTS IN TOTAL", 0, 1, 1000, 0},
    {"DOT HOARDER", "EAT 10,000 DOTS IN TOTAL", 0, 1, 10000, 0},
    {"GHOST HUNTER", "EAT 100 GHOSTS IN TOTAL", 0, 2, 100, 0},
    {"REGULAR", "FINISH 10 GAMES", 0, 3, 10, 0},
    {"TWO'S COMPANY", "FINISH A TWO-PLAYER GAME", 0, 0, 0, 0},
    {"PELLET POPPER", "EAT ALL 4 POWER PELLETS ON ONE BOARD", 1, 0, 0, 0},
    {"QUICK DRAW", "EAT A GHOST WITHIN 2 SECONDS OF A PELLET", 1, 0, 0, 0},
};

#define MARATHON_FRAMES 53928ul      /* 15 minutes of the game's 59.92 frames a second */
#define QUICK_FRAMES 120ul
#define CLOSE_UNITS 12               /* "close by": within 12 position units (a little over two squares; Pac-Man is caught at 2) */
#define COUNT_CAP 4000000000u
#define HIGH_MIN 1000L

/* the seal's key: it keeps a hand-edited file from being taken (a file that is not sealed with it is put aside); it is in the source, so it is no secret from someone who reads the source */
static const char seal_key[] = "Pac-Man Atari 8-bit achievements";

void ach_init(Ach *a)
{
    memset(a, 0, sizeof *a);
    a->last_fruit_level[0] = a->last_fruit_level[1] = -1;
}

int ach_has(const Ach *a, int id)
{
    return id >= 0 && id < ACH_COUNT && ((a->unlocked >> id) & 1u) != 0;
}

int ach_unlocked_count(const Ach *a)
{
    int i, n = 0;

    for (i = 0; i < ACH_COUNT; i++) {
        n += ach_has(a, i);
    }
    return n;
}

int ach_take(Ach *a)
{
    int id, i;

    if (a->nq <= 0) {
        return -1;
    }
    id = a->queue[0];
    for (i = 1; i < a->nq; i++) {
        a->queue[i - 1] = a->queue[i];
    }
    a->nq--;
    return id;
}

int ach_progress(const Ach *a, int id, unsigned long *cur, unsigned long *target)
{
    if (id < 0 || id >= ACH_COUNT || ach_defs[id].counter == 0) {
        return 0;
    }
    *cur = ach_defs[id].counter == 1 ? a->dots : ach_defs[id].counter == 2 ? a->ghosts : a->games;
    *target = ach_defs[id].target;
    return 1;
}

static void unlock(Ach *a, int id, uint32_t now)
{
    if (id < 0 || id >= ACH_COUNT || ach_has(a, id)) {
        return;
    }
    a->unlocked |= 1u << id;
    a->when[id] = now != 0 ? now : 1u;
    a->dirty = 1;
    if (a->nq < ACH_QUEUE) {
        a->queue[a->nq++] = id;
    }
}

static void add_count(uint32_t *c, unsigned n)
{
    *c = *c > COUNT_CAP - n ? COUNT_CAP : *c + n;
}

/* a six-digit score as the game draws it: $10 + digit, $00 a blank leading zero; -1 for anything else */
static long digits_of(const uint8_t *cells)
{
    long v = 0;
    int i;

    for (i = 0; i < 6; i++) {
        if (cells[i] == 0u) {
            v *= 10;
        } else if (cells[i] >= 0x10u && cells[i] <= 0x19u) {
            v = v * 10 + (long)(cells[i] - 0x10u);
        } else {
            return -1;
        }
    }
    return v;
}

static int pop4(int f)
{
    return (f & 1) + ((f >> 1) & 1) + ((f >> 2) & 1) + ((f >> 3) & 1);
}

static void new_game(Ach *a, const World *w)
{
    a->have_prev = 0;
    a->assisted = w->StartLevel != 0;
    a->two_players = w->TwoPlayers != 0;
    a->finished = 0;
    a->frames = 0;
    a->high_at_start = digits_of(w->status + 0x39);
    memset(a->deaths_on_board, 0, sizeof a->deaths_on_board);
    memset(a->streak, 0, sizeof a->streak);
    memset(a->pellets_on_board, 0, sizeof a->pellets_on_board);
    memset(a->fruit_boards, 0, sizeof a->fruit_boards);
    a->last_fruit_level[0] = a->last_fruit_level[1] = -1;
    a->pellet_seen = 0;
    a->last_pellet_frame = 0;
}

static void remember(Ach *a, const World *w, int p, int level, int flags, int dots, int eyes, int countdown)
{
    a->prev.player = p;
    a->prev.level = level;
    a->prev.flags = flags;
    a->prev.dots = dots;
    a->prev.death_freeze = w->DeathFreeze != 0;
    a->prev.eyes = eyes;
    a->prev.bonus_shown = w->BonusScoreShown != 0;
    a->prev.level_complete = w->LevelComplete != 0;
    a->prev.countdown = countdown;
    a->prev.extra_life = w->ExtraLifeFlag[p] != 0;
}

/* the events of one frame, from what the state was and is */
static void events(Ach *a, const World *w, uint32_t now, int p, int level, int flags, int dots, int eyes)
{
    int i, same_level = level == a->prev.level, pellet_event = 0;
    long score;

    if (!w->Paused) {
        a->frames++;
        if (a->frames >= MARATHON_FRAMES) {
            unlock(a, ACH_MARATHON, now);
        }
    }
    if (!same_level) {                                                            /* a new board for this player */
        a->deaths_on_board[p] = 0;
        a->pellets_on_board[p] = 0;
    }
    if (w->DeathFreeze != 0 && !a->prev.death_freeze) {                            /* Pac-Man is caught */
        a->deaths_on_board[p]++;
        a->streak[p] = 0;
    }
    if (same_level && pop4(a->prev.flags) - pop4(flags) == 1) {                    /* a power pellet */
        pellet_event = 1;
        unlock(a, ACH_POWER_UP, now);
        a->pellets_on_board[p]++;
        if (a->pellets_on_board[p] >= 4) {
            unlock(a, ACH_PELLET_POPPER, now);
        }
        a->pellet_seen = 1;
        a->last_pellet_frame = a->frames;
    }
    if (same_level && dots - a->prev.dots >= 1 && dots - a->prev.dots <= 2) {     /* dots (the count includes the power pellets) */
        int n = dots - a->prev.dots - pellet_event;
        if (n > 0) {
            add_count(&a->dots, (unsigned)n);
            unlock(a, ACH_FIRST_BITE, now);
            a->dirty = 1;
            if (a->dots >= ach_defs[ACH_DOT_COLLECTOR].target) {
                unlock(a, ACH_DOT_COLLECTOR, now);
            }
            if (a->dots >= ach_defs[ACH_DOT_HOARDER].target) {
                unlock(a, ACH_DOT_HOARDER, now);
            }
        }
    }
    if (eyes > a->prev.eyes) {                                                    /* a ghost eaten */
        int combo = ((int)w->GhostsEaten + 1) & 0xFF, near_one = 0;
        add_count(&a->ghosts, (unsigned)(eyes - a->prev.eyes));
        a->dirty = 1;
        unlock(a, ACH_GHOST_BUSTER, now);
        if (a->ghosts >= ach_defs[ACH_GHOST_HUNTER].target) {
            unlock(a, ACH_GHOST_HUNTER, now);
        }
        if (combo >= 2 && combo <= 4) {
            unlock(a, ACH_DOUBLE_TROUBLE, now);
        }
        if (combo >= 3 && combo <= 4) {
            unlock(a, ACH_TRIPLE_THREAT, now);
        }
        if (combo == 4) {
            unlock(a, ACH_GHOST_SWEEP, now);
        }
        if (a->pellet_seen && a->frames - a->last_pellet_frame <= QUICK_FRAMES) {
            unlock(a, ACH_QUICK_DRAW, now);
        }
        for (i = 0; i < 4; i++) {                                                 /* another ghost that can still catch Pac-Man (not frightened, not eyes) within a couple of squares */
            if ((w->GhostState[i] & 0xC0) == 0) {
                int dx = (int)w->EntityX[i] - (int)w->EntityX[4], dy = (int)w->EntityY[i] - (int)w->EntityY[4];
                dx = dx < 0 ? -dx : dx;
                dy = dy < 0 ? -dy : dy;
                if (dx <= CLOSE_UNITS && dy <= CLOSE_UNITS) {
                    near_one = 1;
                }
            }
        }
        if (near_one) {
            unlock(a, ACH_CLOSE_CALL, now);
        }
    }
    if (w->BonusScoreShown && !a->prev.bonus_shown && a->last_fruit_level[p] != level) {   /* the bonus fruit eaten */
        a->last_fruit_level[p] = level;
        a->fruit_boards[p]++;
        if (a->fruit_boards[p] >= 3) {
            unlock(a, ACH_FRUIT_SALAD, now);
        }
    }
    if (w->LevelComplete != 0 && !a->prev.level_complete && a->deaths_on_board[p] == 0) {   /* a board cleared without dying */
        unlock(a, ACH_CLEAN_SWEEP, now);
        a->streak[p]++;
        if (a->streak[p] >= 3) {
            unlock(a, ACH_SURVIVOR, now);
        }
    }
    if (!a->assisted) {                                                           /* score and level: only in a game that began at level 1 */
        score = digits_of(w->status + (p == 0 ? 0x2A : 0x47));
        if (w->ExtraLifeFlag[p] != 0 && !a->prev.extra_life) {
            unlock(a, ACH_BONUS_LIFE, now);
        }
        if (score >= 50000L) {
            unlock(a, ACH_HIGH_ROLLER, now);
        }
        if (score >= 100000L) {
            unlock(a, ACH_SIX_FIGURES, now);
        }
        if (score >= 250000L) {
            unlock(a, ACH_ARCADE_LEGEND, now);
        }
        if (a->high_at_start >= HIGH_MIN && score > a->high_at_start) {
            unlock(a, ACH_NEW_RECORD, now);
        }
        if (level + 1 >= 3) {
            unlock(a, ACH_WARMING_UP, now);
        }
        if (level + 1 >= 5) {
            unlock(a, ACH_FIVE_ALIVE, now);
        }
        if (level + 1 >= 8) {
            unlock(a, ACH_VETERAN, now);
        }
        if (level + 1 >= 12) {
            unlock(a, ACH_UNSTOPPABLE, now);
        }
    }
}

void ach_step(Ach *a, const World *w, uint32_t now)
{
    int p = w->CurrentPlayer & 1, i, in_game = w->GameState == 0, active = in_game && w->PlayStarted != 0;
    int level = w->Level[p], flags = w->PelletFlags[p], dots = w->DotsEatenLo[p] | (w->DotsEatenHi[p] << 8);
    int eyes = 0, countdown = w->CountdownActive != 0;

    if (!active) {                                                                /* the title, or a game that has not begun to play (a new game, by Start from the title or in the middle of a game, clears PlayStarted) */
        a->armed = 1;
        a->have_prev = 0;
        return;
    }
    if (a->armed) {                                                               /* play has begun: a new game */
        a->armed = 0;
        new_game(a, w);
    }
    for (i = 0; i < 4; i++) {
        eyes += (w->GhostState[i] & 0x40) != 0;
    }
    if (!a->have_prev || a->prev.player != p || w->TurnSwitchState != 0) {         /* the first frame of a game, or the turn has gone to the other player: nothing to compare with yet */
        a->have_prev = w->TurnSwitchState == 0;
        remember(a, w, p, level, flags, dots, eyes, countdown);
        return;
    }
    if (countdown && !a->prev.countdown && !a->finished) {                        /* the game is over: the game-over countdown starts once, when the last player is out */
        a->finished = 1;
        add_count(&a->games, 1);
        a->dirty = 1;
        if (a->games >= ach_defs[ACH_REGULAR].target) {
            unlock(a, ACH_REGULAR, now);
        }
        if (a->two_players) {
            unlock(a, ACH_TWOS_COMPANY, now);
        }
    }
    if (!countdown) {
        events(a, w, now, p, level, flags, dots, eyes);
    }
    remember(a, w, p, level, flags, dots, eyes, countdown);
}

/* ---------------------------------------------------------------- the file */

#define FILE_HEAD 8
#define FILE_BODY (FILE_HEAD + 16 + 4 * ACH_COUNT)

static void put32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
    p[2] = (uint8_t)(v >> 16);
    p[3] = (uint8_t)(v >> 24);
}

static uint32_t get32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

size_t ach_save_bytes(const Ach *a, uint8_t out[ACH_FILE_MAX])
{
    int i;

    memset(out, 0, ACH_FILE_MAX);
    memcpy(out, "PMAC", 4);
    out[4] = 1;                                                 /* version */
    out[6] = (uint8_t)ACH_COUNT;
    put32(out + FILE_HEAD, a->unlocked);
    put32(out + FILE_HEAD + 4, a->dots);
    put32(out + FILE_HEAD + 8, a->ghosts);
    put32(out + FILE_HEAD + 12, a->games);
    for (i = 0; i < ACH_COUNT; i++) {
        put32(out + FILE_HEAD + 16 + 4 * i, a->when[i]);
    }
    hmac_sha256((const uint8_t *)seal_key, sizeof seal_key - 1u, out, FILE_BODY, out + FILE_BODY);
    return FILE_BODY + 32;
}

int ach_load_bytes(Ach *a, const uint8_t *buf, size_t n)
{
    uint8_t mac[32], diff = 0;
    uint32_t bits;
    int i;

    if (n != FILE_BODY + 32 || memcmp(buf, "PMAC", 4) != 0 || buf[4] != 1 || buf[5] != 0 || buf[6] != ACH_COUNT || buf[7] != 0) {
        return 1;
    }
    hmac_sha256((const uint8_t *)seal_key, sizeof seal_key - 1u, buf, FILE_BODY, mac);
    for (i = 0; i < 32; i++) {
        diff = (uint8_t)(diff | (mac[i] ^ buf[FILE_BODY + i]));
    }
    bits = get32(buf + FILE_HEAD);
    if (diff != 0 || (bits >> ACH_COUNT) != 0) {
        return 1;
    }
    a->unlocked = bits;
    a->dots = get32(buf + FILE_HEAD + 4);
    a->ghosts = get32(buf + FILE_HEAD + 8);
    a->games = get32(buf + FILE_HEAD + 12);
    for (i = 0; i < ACH_COUNT; i++) {
        a->when[i] = get32(buf + FILE_HEAD + 16 + 4 * i);
    }
    return 0;
}
