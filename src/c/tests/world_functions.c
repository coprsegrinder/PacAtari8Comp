/* The World functions of the vector runner: a wrapper per recorded set that checks the argument shape, calls the C function and returns its value. */
#include <string.h>

#include "../app/board.h"
#include "../app/dispatch.h"
#include "../app/keyloop.h"
#include "../core/gtia.h"
#include "../platform/fs.h"
#include "../app/init.h"
#include "../app/run_frame.h"
#include "../core/draw.h"
#include "../core/frame.h"
#include "../core/ghost.h"
#include "../core/play.h"
#include "../core/sound.h"
#include "../core/pacman.h"
#include "../core/score.h"
#include "world_functions.h"

/* ---- the test functions of stage 75b: an identity and two deliberately broken ones (the negative controls) */
static int fn_identity(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret)
{
    (void)w; (void)args; (void)nargs; (void)rnd;
    *ret = 0;
    return 0;
}

static int fn_broken_identity(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret)
{
    (void)args; (void)nargs; (void)rnd;
    w->GameState = (uint8_t)(w->GameState + 1u);     /* one byte wrong */
    *ret = 0;
    return 0;
}

static int fn_broken_random(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret)
{
    (void)w; (void)args; (void)nargs;
    (void)random_next(rnd);                          /* reads a RANDOM value it should not */
    *ret = 0;
    return 0;
}

/* ---- stage 76b: the ghosts and the house.  The arguments are the ghost number (0-3) and, for step_entity, the direction. */
#define GHOST_ARG(lo, hi) (nargs == 1 && args[0] >= (lo) && args[0] <= (hi))

#define WRAP_GHOST_RND(name, call)                                                           \
    static int name(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret) \
    {                                                                                        \
        *ret = 0;                                                                            \
        if (!GHOST_ARG(0, 3)) {                                                              \
            return 1;                                                                        \
        }                                                                                    \
        call;                                                                                \
        return 0;                                                                            \
    }

#define WRAP_GHOST(name, lo, hi, call)                                                       \
    static int name(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret) \
    {                                                                                        \
        (void)rnd;                                                                           \
        *ret = 0;                                                                            \
        if (!GHOST_ARG(lo, hi)) {                                                            \
            return 1;                                                                        \
        }                                                                                    \
        call;                                                                                \
        return 0;                                                                            \
    }

WRAP_GHOST_RND(g_ghost_behaviour, ghost_behaviour(w, (int)args[0], rnd))
WRAP_GHOST(g_ghost_sees_pacman, 0, 3, ghost_sees_pacman(w, (int)args[0]))
WRAP_GHOST(g_force_chase, 0, 3, force_chase(w, (int)args[0]))
WRAP_GHOST(g_house_bob_step, 0, 3, house_bob_step(w, (int)args[0]))
WRAP_GHOST(g_house_enter_step, 0, 3, house_enter_step(w, (int)args[0]))
WRAP_GHOST(g_house_leave_ghost2, 0, 3, house_leave_ghost2(w, (int)args[0]))
WRAP_GHOST(g_house_leave_ghost3, 0, 3, house_leave_ghost3(w, (int)args[0]))
WRAP_GHOST(g_house_leave_step, 0, 3, house_leave_step(w, (int)args[0]))

static int g_chase_timer_siren_sight(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret)
{
    (void)args; (void)rnd;
    *ret = 0;
    if (nargs != 0) {
        return 1;
    }
    chase_timer_siren_sight(w);
    return 0;
}

static int g_house_waiting_tick(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret)
{
    (void)args; (void)rnd;
    *ret = 0;
    if (nargs != 0) {
        return 1;
    }
    house_waiting_tick(w);
    return 0;
}

static int g_step_entity(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret)
{
    (void)rnd;
    *ret = 0;
    if (nargs != 2 || args[0] < 0 || args[0] > 3) {
        return 1;
    }
    step_entity(w, (int)args[0], args[1]);
    return 0;
}

/* ---- stage 76c: Pac-Man, the score, the drawing.  Most take no argument. */
#define WRAP_NOARG(name, call)                                                                   static int name(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret)     {                                                                                                (void)args;                                                                                  (void)rnd;                                                                                   *ret = 0;                                                                                    if (nargs != 0) {                                                                                return 1;                                                                                }                                                                                            call;                                                                                        return 0;                                                                                }

WRAP_NOARG(g_move_pacman, move_pacman(w))
WRAP_NOARG(g_add_to_score, add_to_score(w))
WRAP_NOARG(g_draw_lives, draw_lives(w))
WRAP_NOARG(g_eat_dot, eat_dot(w))
WRAP_NOARG(g_power_pellet_check, power_pellet_check(w))
WRAP_NOARG(g_clear_player_memory, clear_player_memory(w))
WRAP_NOARG(g_clip_entities_on_tunnel_row, clip_entities_on_tunnel_row(w))
WRAP_NOARG(g_draw_all_in_place, draw_all_in_place(w))

/* ---- stage 76d: the sound, the frame, the play frame.  The ones that read RANDOM values take the feed. */
#define WRAP_NOARG_RND(name, call)                                                           \
    static int name(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret) \
    {                                                                                        \
        (void)args;                                                                          \
        (void)rnd;                                                                           \
        *ret = 0;                                                                            \
        if (nargs != 0) {                                                                    \
            return 1;                                                                        \
        }                                                                                    \
        call;                                                                                \
        return 0;                                                                            \
    }

WRAP_NOARG(g_bonus_sound, bonus_sound(w))
WRAP_NOARG(g_clear_pokey, clear_pokey(w))
WRAP_NOARG(g_death_animation, death_animation(w))
WRAP_NOARG(g_death_sequence, death_sequence(w))
WRAP_NOARG(g_dot_sound_sweep, dot_sound_sweep(w))
WRAP_NOARG(g_eyes_returning_sound, eyes_returning_sound(w))
WRAP_NOARG(g_frightened_sound, frightened_sound(w))
WRAP_NOARG(g_ghost_eaten_pause, ghost_eaten_pause(w))
WRAP_NOARG(g_siren, siren(w))
WRAP_NOARG(g_start_tune_step, (void)start_tune_step(w))
WRAP_NOARG(g_frightened_tick, frightened_tick(w))
WRAP_NOARG_RND(g_eyes_and_house_per_frame, eyes_and_house_per_frame(w, rnd))
WRAP_NOARG_RND(g_vbi_play_frame, vbi_play_frame(w, rnd))

static int g_ghost_eaten(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret)
{
    (void)rnd;
    *ret = 0;
    if (nargs != 1 || args[0] < 0 || args[0] > 3) {
        return 1;
    }
    ghost_eaten(w, (int)args[0]);
    return 0;
}

/* ---- stage 79d: a whole session.  Each recorded call is one frame of the whole program on a platform that replays the inputs of the frame (args: frame number, STICK0, STRIG0, STRIG1, CONSOL, the key code the OS
 * stores in CH, KEYDEL, the clock, DRKMSK, COLRSH) and hands out the frame's RANDOM values; the collision registers are computed by the C's own GTIA model and latch.  The call returns where the main program is
 * (keyloop_state).  Frame 0 starts from the power-on World of the record and runs Start first.  The main program's place and the latch live between the calls (they are not World state). */
typedef struct SessionInputs {
    uint8_t stick0, trig0, trig1, console, key, keydelay, clock, drkmsk, colrsh;
    RandomFeed *rnd;
} SessionInputs;

static KeyLoop session_kl;
static GtiaLatch session_latch;
static uint8_t session_charset[GTIA_CHARSET_SIZE];
static int session_charset_loaded;

static uint8_t ss_stick(void *ctx, int port)
{
    return port == 0 ? ((SessionInputs *)ctx)->stick0 : 0x0F;
}

static uint8_t ss_trigger(void *ctx, int port)
{
    return port == 0 ? ((SessionInputs *)ctx)->trig0 : ((SessionInputs *)ctx)->trig1;
}

static uint8_t ss_console(void *ctx)
{
    return ((SessionInputs *)ctx)->console;
}

static uint8_t ss_key(void *ctx)
{
    return ((SessionInputs *)ctx)->key;
}

static uint8_t ss_key_delay(void *ctx)
{
    return ((SessionInputs *)ctx)->keydelay;
}

static uint8_t ss_clock(void *ctx)
{
    return ((SessionInputs *)ctx)->clock;
}

static void ss_attract(void *ctx, uint8_t *drkmsk, uint8_t *colrsh)
{
    *drkmsk = ((SessionInputs *)ctx)->drkmsk;
    *colrsh = ((SessionInputs *)ctx)->colrsh;
}

static uint8_t ss_random(void *ctx)
{
    return random_next(((SessionInputs *)ctx)->rnd);
}

static void ss_collisions(void *ctx, const World *w, uint8_t out[16])
{
    (void)ctx;
    (void)w;
    memcpy(out, session_latch.reg, 16);
}

static void ss_frame_done(void *ctx, const World *w)
{
    (void)ctx;
    gtia_latch_frame_done(&session_latch, w, session_charset);
}

static int g_app_frame(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret)
{
    SessionInputs in;
    Platform p;

    *ret = 0;
    if (nargs != 10) {
        return 1;
    }
    if (args[0] == 0) {
        PmFile *f;
        if (!session_charset_loaded) {
            f = pm_fs_open("resources/vectors/gtia.charset.bin", "rb");
            if (f == NULL || pm_fs_read(f, session_charset, sizeof session_charset) != sizeof session_charset) {
                return 1;
            }
            pm_fs_close(f);
            session_charset_loaded = 1;
        }
        keyloop_init(&session_kl);
        gtia_latch_init(&session_latch);
        start(w);
    }
    in.stick0 = (uint8_t)args[1];
    in.trig0 = (uint8_t)args[2];
    in.trig1 = (uint8_t)args[3];
    in.console = (uint8_t)args[4];
    in.key = (uint8_t)args[5];
    in.keydelay = (uint8_t)args[6];
    in.clock = (uint8_t)args[7];
    in.drkmsk = (uint8_t)args[8];
    in.colrsh = (uint8_t)args[9];
    in.rnd = rnd;
    p.ctx = &in;
    p.stick = ss_stick;
    p.trigger = ss_trigger;
    p.console = ss_console;
    p.key = ss_key;
    p.key_delay = ss_key_delay;
    p.clock = ss_clock;
    p.attract = ss_attract;
    p.random = ss_random;
    p.collisions = ss_collisions;
    p.frame_done = ss_frame_done;
    (void)app_frame(w, &session_kl, &p);
    *ret = (int32_t)keyloop_state(&session_kl);
    return 0;
}

/* the RAM after the OS's power-on clear (arg: the clock); the World the call gets is replaced as a whole */
static int g_power_on_world(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret)
{
    (void)rnd;
    *ret = 0;
    if (nargs != 1 || args[0] < 0 || args[0] > 255) {
        return 1;
    }
    power_on_world(w, (uint8_t)args[0]);
    return 0;
}

/* the main program from a given place (args: the place - 0 top, 2 debounce, 3 release, 4 clock wait -, the accumulator, the clock of the wait, the console): the return value is where it is afterwards */
static int g_key_loop(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret)
{
    KeyLoop kl;

    (void)rnd;
    *ret = 0;
    if (nargs != 4 || args[0] < 0 || args[0] > 4 || args[0] == 1) {
        return 1;
    }
    kl.pc = (int)args[0];
    kl.acc = (uint8_t)args[1];
    kl.clock = (uint8_t)args[2];
    if (key_loop(w, &kl, (uint8_t)args[3]) != 0) {
        return 1;
    }
    *ret = (int32_t)keyloop_state(&kl);
    return 0;
}

/* ---- stage 79c: the frame dispatcher (the handler and the dispatch take the RANDOM feed) */
WRAP_NOARG_RND(g_frame_dispatch, frame_dispatch(w, rnd))
WRAP_NOARG_RND(g_vbi_handler, vbi_handler(w, rnd))

/* ---- stage 79a: the state initialisation */
WRAP_NOARG(g_init_board, init_board(w))
WRAP_NOARG(g_new_game_init, new_game_init(w))
WRAP_NOARG(g_new_board_init, new_board_init(w))
WRAP_NOARG(g_load_shadow_colors, load_shadow_colors(w))
WRAP_NOARG(g_copy_0800_to_0c00, copy_0800_to_0c00(w))
WRAP_NOARG(g_copy_0c00_to_1000, copy_0c00_to_1000(w))
WRAP_NOARG(g_copy_0c00_to_1400, copy_0c00_to_1400(w))

static int g_clear_player_counters(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret)
{
    (void)rnd;
    *ret = 0;
    if (nargs != 1 || args[0] < 0 || args[0] > 1) {
        return 1;
    }
    clear_player_counters(w, (int)args[0]);
    return 0;
}

static int g_set_release_timers(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret)
{
    (void)rnd;
    *ret = 0;
    if (nargs != 1 || args[0] < 0 || args[0] > 255) {
        return 1;
    }
    set_release_timers(w, (int)args[0]);
    return 0;
}

/* ---- stage 79b: the board, the turn, the end of a level, the intro, the labels */
WRAP_NOARG(g_turn_control, turn_control(w))
WRAP_NOARG(g_level_end_step, level_end_step(w))
WRAP_NOARG(g_advance_level, advance_level(w))
WRAP_NOARG(g_draw_level_indicator, draw_level_indicator(w))
WRAP_NOARG(g_draw_ready_screen, draw_ready_screen(w))
WRAP_NOARG(g_clear_ready_text, clear_ready_text(w))
WRAP_NOARG(g_blink_player_label, blink_player_label(w))
WRAP_NOARG(g_draw_label_1up, draw_label_1up(w))
WRAP_NOARG(g_draw_label_2up, draw_label_2up(w))

static int g_compare_high_score(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret)
{
    (void)rnd;
    *ret = 0;
    if (nargs != 1 || (args[0] != 0x2A && args[0] != 0x47)) {
        return 1;
    }
    compare_high_score(w, (int)args[0]);
    return 0;
}

static int g_draw_pacman(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret)
{
    (void)rnd;
    *ret = 0;
    if (nargs != 2 || args[0] < 0 || args[0] > 255) {
        return 1;
    }
    draw_pacman(w, args[0], args[1]);
    return 0;
}

/* ---- stage 77b: run_frame on a platform that replays the inputs the recorded call had in its before-state (the stick shadows 0 and 1, the collision registers, the clock, the attract values)
 * and hands out the call's RANDOM values.  STICK2 / STICK3 are not inputs of the game (docs/45): run_frame sets them to $0F, the recorded state kept random values, so they are put back. */
typedef struct ReplayInputs {
    uint8_t stick[2];
    uint8_t collide[16];
    uint8_t clock, drkmsk, colrsh;
    RandomFeed *rnd;
} ReplayInputs;

static uint8_t rp_stick(void *ctx, int port)
{
    return ((ReplayInputs *)ctx)->stick[port & 1];
}

static uint8_t rp_zero(void *ctx)
{
    (void)ctx;
    return 0;
}

static uint8_t rp_trigger(void *ctx, int port)
{
    (void)ctx;
    (void)port;
    return 1;
}

static uint8_t rp_console(void *ctx)
{
    (void)ctx;
    return 7;
}

static uint8_t rp_key(void *ctx)
{
    (void)ctx;
    return 0xFF;
}

static uint8_t rp_clock(void *ctx)
{
    return ((ReplayInputs *)ctx)->clock;
}

static void rp_attract(void *ctx, uint8_t *drkmsk, uint8_t *colrsh)
{
    *drkmsk = ((ReplayInputs *)ctx)->drkmsk;
    *colrsh = ((ReplayInputs *)ctx)->colrsh;
}

static uint8_t rp_random(void *ctx)
{
    return random_next(((ReplayInputs *)ctx)->rnd);
}

static void rp_collisions(void *ctx, const World *w, uint8_t out[16])
{
    (void)w;
    memcpy(out, ((ReplayInputs *)ctx)->collide, 16);
}

static int g_platform_run_frame(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret)
{
    ReplayInputs in;
    Platform p;
    uint8_t s2, s3;

    (void)args;
    *ret = 0;
    if (nargs != 0) {
        return 1;
    }
    in.stick[0] = w->stick[0];
    in.stick[1] = w->stick[1];
    memcpy(in.collide, w->collide, 16);
    in.clock = w->RTCLOK2;
    in.drkmsk = w->DRKMSK;
    in.colrsh = w->COLRSH;
    in.rnd = rnd;
    s2 = w->stick[2];
    s3 = w->stick[3];
    p.ctx = &in;
    p.stick = rp_stick;
    p.trigger = rp_trigger;
    p.console = rp_console;
    p.key = rp_key;
    p.key_delay = rp_zero;
    p.clock = rp_clock;
    p.attract = rp_attract;
    p.random = rp_random;
    p.collisions = rp_collisions;
    p.frame_done = NULL;
    (void)run_frame(w, &p);
    w->stick[2] = s2;
    w->stick[3] = s3;
    return 0;
}

static const struct {
    const char *name;
    WorldFn fn;
} world_table[] = {
    {"platform.run_frame", g_platform_run_frame},
    {"identity", fn_identity},
    {"broken_identity", fn_broken_identity},
    {"broken_random", fn_broken_random},
    {"core_ghost.ghost_behaviour", g_ghost_behaviour},
    {"core_ghost.ghost_sees_pacman", g_ghost_sees_pacman},
    {"core_ghost.chase_timer_siren_sight", g_chase_timer_siren_sight},
    {"core_ghost.force_chase", g_force_chase},
    {"core_ghost.step_entity", g_step_entity},
    {"core_ghost.house_waiting_tick", g_house_waiting_tick},
    {"core_ghost.house_bob_step", g_house_bob_step},
    {"core_ghost.house_enter_step", g_house_enter_step},
    {"core_ghost.house_leave_ghost2", g_house_leave_ghost2},
    {"core_ghost.house_leave_ghost3", g_house_leave_ghost3},
    {"core_ghost.house_leave_step", g_house_leave_step},
    {"core_pacman.move_pacman", g_move_pacman},
    {"core_score.add_to_score", g_add_to_score},
    {"core_score.draw_lives", g_draw_lives},
    {"core_score.eat_dot", g_eat_dot},
    {"core_score.power_pellet_check", g_power_pellet_check},
    {"core_draw.clear_player_memory", g_clear_player_memory},
    {"core_draw.clip_entities_on_tunnel_row", g_clip_entities_on_tunnel_row},
    {"core_draw.draw_all_in_place", g_draw_all_in_place},
    {"core_draw.draw_pacman", g_draw_pacman},
    {"core_draw.step_and_draw_entity", g_step_entity},
    {"core_app_board.turn_control", g_turn_control},
    {"core_app_board.level_end_step", g_level_end_step},
    {"core_app_board.advance_level", g_advance_level},
    {"core_app_board.draw_level_indicator", g_draw_level_indicator},
    {"core_app_board.draw_ready_screen", g_draw_ready_screen},
    {"core_app_board.clear_ready_text", g_clear_ready_text},
    {"core_app_board.blink_player_label", g_blink_player_label},
    {"core_app_board.draw_label_1up", g_draw_label_1up},
    {"core_app_board.draw_label_2up", g_draw_label_2up},
    {"core_app_board.compare_high_score", g_compare_high_score},
    {"app.frame", g_app_frame},
    {"app.key_loop", g_key_loop},
    {"app.power_on_world", g_power_on_world},
    {"core_app_frame.frame_dispatch", g_frame_dispatch},
    {"core_app_frame.vbi_handler", g_vbi_handler},
    {"core_app_init.init_board", g_init_board},
    {"core_app_init.new_game_init", g_new_game_init},
    {"core_app_init.new_board_init", g_new_board_init},
    {"core_app_init.clear_player_counters", g_clear_player_counters},
    {"core_app_init.set_release_timers", g_set_release_timers},
    {"core_app_init.load_shadow_colors", g_load_shadow_colors},
    {"core_app_init.copy_0800_to_0c00", g_copy_0800_to_0c00},
    {"core_app_init.copy_0c00_to_1000", g_copy_0c00_to_1000},
    {"core_app_init.copy_0c00_to_1400", g_copy_0c00_to_1400},
    {"core_sound.bonus_sound", g_bonus_sound},
    {"core_sound.clear_pokey", g_clear_pokey},
    {"core_sound.death_animation", g_death_animation},
    {"core_sound.death_sequence", g_death_sequence},
    {"core_sound.dot_sound_sweep", g_dot_sound_sweep},
    {"core_sound.eyes_returning_sound", g_eyes_returning_sound},
    {"core_sound.frightened_sound", g_frightened_sound},
    {"core_sound.ghost_eaten_pause", g_ghost_eaten_pause},
    {"core_sound.siren", g_siren},
    {"core_sound.start_tune_step", g_start_tune_step},
    {"core_frame.frightened_tick", g_frightened_tick},
    {"core_frame.eyes_and_house_per_frame", g_eyes_and_house_per_frame},
    {"core_frame.ghost_eaten", g_ghost_eaten},
    {"core_play.vbi_play_frame", g_vbi_play_frame},
};

WorldFn world_lookup(const char *name)
{
    size_t i;
    for (i = 0; i < sizeof world_table / sizeof world_table[0]; i++) {
        if (strcmp(world_table[i].name, name) == 0) {
            return world_table[i].fn;
        }
    }
    return NULL;
}
