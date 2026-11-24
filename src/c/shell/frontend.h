/* shell/frontend.h - what any interactive front end does between the player and the game (stage J, docs/67): the keys, pad directions and buttons of the moment become the FrameInput of the frame the way
 * the Atari's hardware and OS made them.  Portable C99 (no system call): the Windows front end (platform/win32) and a test drive it the same way.
 *   - the stick is the joystick's four switches: a direction pressed together with its opposite gives neither (a stick cannot do both);
 *   - the trigger is 0 when pressed; the console keys START, SELECT, OPTION are 0 when pressed;
 *   - the pause key (the space bar of the original) is a key PRESS, not a held key: the OS keyboard interrupt stores the code $21 in CH once and sets the debounce KEYDEL to 3, which the OS counts down at every
 *     frame (docs/45): the game accepts the key at KEYDEL = 0 and clears CH itself (docs/41); a key held down does not repeat it;
 *   - the OS clock RTCLOK2 counts one at every frame from the power-on value;  DRKMSK $FF and COLRSH 0: attract mode never engages (the game writes ATRACT at every key press and screen change, and a front
 *     end plays at the keyboard).  The RANDOM bytes come from the model (the seed), not from the frame. */
#ifndef PM_SHELL_FRONTEND_H
#define PM_SHELL_FRONTEND_H

#include <stdint.h>

#include "replay.h"

#define FRONT_KEYDELAY 3        /* the OS sets KEYDEL to 3 with a key press */
#define FRONT_PAUSE_CODE 0x21   /* the keyboard code of the space bar: what the game takes as the pause key */

/* the five switches of one joystick: 1 = pressed */
typedef struct FrontPad {
    uint8_t up, down, left, right, fire;
} FrontPad;

/* what is pressed at the moment of the frame; `pause` is 1 for exactly one frame per press (the edge) */
typedef struct FrontKeys {
    FrontPad pad[2];            /* the joystick ports 0 and 1 (player 1, player 2) */
    uint8_t start, select, option;
    uint8_t pause;
} FrontKeys;

/* the front end's state between frames: the OS clock and the key delay */
typedef struct Frontend {
    uint8_t clock;              /* RTCLOK2 of the next frame */
    uint8_t keydelay;           /* KEYDEL */
} Frontend;

/* the front end at power-on: the OS clock starts at `start_clock`, no key is pending */
void front_init(Frontend *f, uint8_t start_clock);
/* the FrameInput of one frame from what is pressed now: no RANDOM bytes (the model gives them); counts the key delay down and the clock up */
void front_frame(Frontend *f, const FrontKeys *k, FrameInput *out);

#endif
