/* shell/achieve.h - achievements of the port (docs/74): earned by playing, found by watching the game's state after each frame (nothing is written into the game), kept between runs in a sealed file.
 * Portable C99, no system call: the front end gives it the World after every game frame and the time, takes the new unlocks to show (a toast, a sound, a pad flash), and reads and writes the file's bytes.
 * Score and level achievements count only in a game started at level 1 (the Option key's starting level must be 0): the owner's rule.  Everything else counts in any game. */
#ifndef PM_SHELL_ACHIEVE_H
#define PM_SHELL_ACHIEVE_H

#include <stddef.h>
#include <stdint.h>

#include "../core/world.h"

#define ACH_COUNT 27
#define ACH_QUEUE 8
#define ACH_FILE_MAX 256
#define ACH_PATH "save/achievements.pma"
#define ACH_BAD_PATH "save/achievements.bad"

/* the achievements, in the order of the table ach_defs (and of the bits of the saved file) */
typedef enum AchId {
    ACH_FIRST_BITE, ACH_POWER_UP, ACH_GHOST_BUSTER, ACH_DOUBLE_TROUBLE, ACH_TRIPLE_THREAT, ACH_GHOST_SWEEP, ACH_CLEAN_SWEEP, ACH_CLOSE_CALL, ACH_FRUIT_SALAD,
    ACH_BONUS_LIFE, ACH_HIGH_ROLLER, ACH_SIX_FIGURES, ACH_ARCADE_LEGEND, ACH_NEW_RECORD, ACH_WARMING_UP, ACH_FIVE_ALIVE, ACH_VETERAN, ACH_UNSTOPPABLE,
    ACH_MARATHON, ACH_SURVIVOR, ACH_DOT_COLLECTOR, ACH_DOT_HOARDER, ACH_GHOST_HUNTER, ACH_REGULAR, ACH_TWOS_COMPANY, ACH_PELLET_POPPER, ACH_QUICK_DRAW
} AchId;

/* an achievement's entry in the table: name, description, whether it is hidden, the lifetime count its progress is of, and whether it needs a game from level 1 */
typedef struct AchDef {
    const char *name;            /* at most 20 characters */
    const char *desc;            /* at most 40 characters */
    int hidden;                  /* shown as ??? until earned */
    int counter;                 /* 0 none, 1 dots, 2 ghosts, 3 games: the lifetime count the progress is of */
    unsigned long target;
    int needs_level1;            /* score and level achievements: only in a game started at level 1 */
} AchDef;

extern const AchDef ach_defs[ACH_COUNT];

/* the achievements of the player (what is kept in the file) and the state of the game being watched (what is not) */
typedef struct Ach {
    /* kept in the file */
    uint32_t unlocked;           /* bit per AchId */
    uint32_t when[ACH_COUNT];    /* when each was earned (seconds since 1970), 0 when not */
    uint32_t dots, ghosts, games;/* lifetime counts: dots eaten, ghosts eaten, games finished */
    /* for the front end */
    int queue[ACH_QUEUE];        /* new unlocks, oldest first, for the toast */
    int nq;
    int dirty;                   /* something to write */
    /* the game being watched (not kept) */
    int armed, have_prev, assisted, two_players, finished;
    unsigned long frames;
    long high_at_start;
    int deaths_on_board[2], streak[2], pellets_on_board[2], fruit_boards[2], last_fruit_level[2];
    unsigned long last_pellet_frame;
    int pellet_seen;
    struct {
        int player, level, flags, dots, death_freeze, eyes, bonus_shown, level_complete, countdown, extra_life;
    } prev;
} Ach;

void ach_init(Ach *a);   /* all locked, no counts, no game being watched */
/* one game frame has run: look for what it did; `now` is the time (seconds since 1970) given to new unlocks */
void ach_step(Ach *a, const World *w, uint32_t now);
int ach_take(Ach *a);                                          /* the next new unlock to show, or -1 */
int ach_has(const Ach *a, int id);
int ach_unlocked_count(const Ach *a);   /* how many are earned */
/* progress of a counting achievement: returns 1 and the count and the target, or 0 when it has no count */
int ach_progress(const Ach *a, int id, unsigned long *cur, unsigned long *target);

/* the file: "PMAC", version, count, the bits, the counts, the times, and a 32-byte HMAC-SHA-256 seal over all of it.  ach_load_bytes takes it only when the seal is right (0), else 1 and `a` is untouched. */
size_t ach_save_bytes(const Ach *a, uint8_t out[ACH_FILE_MAX]);
int ach_load_bytes(Ach *a, const uint8_t *buf, size_t n);   /* takes the file's bytes when the seal is right (0), else 1 and `a` is untouched */

#endif
