/* shell/haptics.h - what a pad's two rumble motors and its light bar do while the game is played (docs/71).  Portable C99: the front end takes a small snapshot of the game's state after each game frame, this
 * finds the events in it (a power pellet, a ghost eaten, Pac-Man caught, an extra life, a board cleared) and answers with the motor strengths and the light colour for that frame.  Nothing here touches the
 * game: the snapshot is read from the World after the frame, so the game's digests are what they were (the front end never writes into the World).
 * A frame is 1/59.92 s of game time: the effects are counted in game frames, so a pause (the menu) stops them and haptics_pause() puts the motors at rest. */
#ifndef PM_SHELL_HAPTICS_H
#define PM_SHELL_HAPTICS_H

#include <stdint.h>

#define HAP_MAX_EFFECTS 6

/* what the front end tells haptics_step about the game after each frame */
typedef struct HapSnapshot {
    int lives;                   /* Lives[CurrentPlayer] */
    int player;                  /* CurrentPlayer */
    int death_freeze;            /* DeathFreeze: non-zero while Pac-Man is being caught (96 counting down) */
    int frightened;              /* ghosts with the frightened bit */
    int eyes;                    /* ghosts that are eyes on their way home */
    int level_complete;          /* LevelComplete */
} HapSnapshot;

/* one rumble effect that is running: the frames left, the motors' strengths, its shape */
typedef struct HapEffect {
    int left, total;             /* frames left, frames in all (0: free) */
    int strong, weak;            /* the motors at the start, 0..255 (strong: the big, low motor; weak: the small, high one) */
    int shape;                   /* 0 falls to nothing, 1 holds then falls over the last quarter */
} HapEffect;

/* what haptics_step answers: the two motor strengths and the light bar colour */
typedef struct HapOut {
    uint8_t strong, weak;        /* motor strengths 0..255 */
    uint8_t r, g, b;             /* the light bar */
} HapOut;

/* the state of the rumble and light bar machine: the last snapshot, the effects running, the flashes */
typedef struct Haptics {
    HapSnapshot prev;
    int have_prev;
    HapEffect fx[HAP_MAX_EFFECTS];
    int flash;                   /* frames of the white flash of a ghost eaten */
    int dying;                   /* frames of the red of a death */
    int gold;                    /* frames of the gold flash of an achievement */
} Haptics;

void haptics_init(Haptics *h);   /* nothing running, nothing seen yet */
/* one game frame with the state after it; fills the strengths and the colour for it */
void haptics_step(Haptics *h, const HapSnapshot *s, HapOut *out);
/* a menu is open (or no game runs): motors at rest, the light bar dimmed; the effects are forgotten (a pause is not a place for a buzz that began before it) */
void haptics_pause(Haptics *h, HapOut *out);
/* the light bar for the title screen / no game yet */
/* an achievement was earned: the light bar flashes gold for 1.5 s (a death's red goes first) and the pad pulses once */
void haptics_achievement(Haptics *h);
void haptics_idle(HapOut *out);   /* the answer when the game is not being played: the motors at rest, Pac-Man yellow */

#endif
