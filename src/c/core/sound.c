/* core/sound.c - the sound and the death (stage 76d).  Twin of tools/core_sound.py: read the two side by side. */
#include "sound.h"

#include "draw.h"
#include "ghost.h"
#include "pacman.h"
#include "score.h"
#include "tables.h"
#include "constants.h"

void sound_wr(World *w, uint16_t addr, int value)
{
    world_pokey(w, addr, (uint8_t)(value & 0xFF));
}

void clear_pokey(World *w)
{
    int k;
    for (k = 7; k >= 0; k--) {
        sound_wr(w, (uint16_t)(POKEY_AUDF1 + k), 0);
    }
}

/* ------------------------------------------------------------------------------------------------ the dot sound and the bonus sound */
void dot_sound_sweep(World *w)
{
    int x, a;
    if (w->DotSoundActive == 0) {
        return;
    }
    x = w->DotSoundStep;
    if (x == 6) {
        w->DotSoundActive = 0;
        w->DotSoundStep = 0;
        sound_wr(w, POKEY_AUDC1, 0);
        return;
    }
    a = w->DotSoundAlt ? table_rom((uint16_t)(0xBCDF + x)) : table_rom((uint16_t)(0xBCD8 + x));
    w->DotSoundStep = (uint8_t)(w->DotSoundStep + 1u);
    sound_wr(w, POKEY_AUDF1, a);
    sound_wr(w, POKEY_AUDC1, 0xA4);
}

void bonus_sound(World *w)
{
    int x = w->BonusSoundStep;
    int a, y;

    if (x == 0) {
        return;
    }
    a = w->BonusSoundPitch;
    y = 0xA5;
    if (x < 7) {
        int last = a == 0xB4;
        if (!last) {
            a = (a + 5) & 0xFF;
            last = a == 0;
        }
        if (last) {                                  /* at $B4, or when the sum wraps to 0 (it falls into the same code): the last step */
            w->BonusSoundStep = (uint8_t)(w->BonusSoundStep + 1u);
            y = 0xA3;
        }
    } else {
        if (x == 9) {
            w->BonusSoundStep = (uint8_t)(w->BonusSoundStep + 1u);
        } else {
            y = 0xA3;
        }
        if (a == 0x78) {
            w->BonusSoundStep = 0;
            a = 0;
            y = 0;
        } else {
            a = (a - 5 - (a < 0x78 ? 1 : 0)) & 0xFF;
        }
    }
    w->BonusSoundPitch = (uint8_t)a;
    sound_wr(w, POKEY_AUDF1, a);
    sound_wr(w, POKEY_AUDC1, y);
}

/* ------------------------------------------------------------------------------------------------ the frightened sound, the eyes, the siren */
enum { L_AFE9, L_B007, L_B00E, L_B01A };

void frightened_sound(World *w)
{
    uint8_t *f = w->FrightSound;                     /* [E1 pitch, E2 phase, E3 volume step, E4 started] */
    int label = L_AFE9;

    if (f[3] == 0) {
        f[2] = 5;
        f[1] = 2;
        f[3] = (uint8_t)(f[3] + 1u);
        f[0] = 0x90;
    }
    for (;;) {
        if (label == L_AFE9) {
            if (f[1] != 1) {
                label = L_B00E;
            } else if (f[0] != 0x90) {
                label = L_B007;
            } else {
                if (f[2] == 3) {
                    f[2] = 5;
                }
                f[2] = (uint8_t)(f[2] - 1u);
                f[1] = 2;
                label = L_B01A;
            }
        } else if (label == L_B007) {
            uint8_t a = (uint8_t)(f[0] + 0x10u);
            if (a != 0) {
                f[0] = a;
                break;
            }
            label = L_B00E;                          /* a sum of 0 falls into $B00E */
        } else if (label == L_B00E) {
            if (f[0] != 0x40) {
                label = L_B01A;
            } else {
                f[1] = 1;
                label = L_B007;
            }
        } else {                                     /* $B01A */
            f[0] = (uint8_t)(f[0] - 0x10u);
            break;
        }
    }
    sound_wr(w, POKEY_AUDF2, f[0]);
    sound_wr(w, POKEY_AUDC2, f[2] | 0xA0);
}

void eyes_returning_sound(World *w)
{
    if (w->EyesSoundStep == 0) {
        w->EyesSoundStep = 0x0C;
    } else if (w->EyesSoundStep == 0x17) {
        w->EyesSoundStep = 0x0C;
    }
    w->EyesSoundStep = (uint8_t)(w->EyesSoundStep + 1u);
    sound_wr(w, POKEY_AUDF2, w->EyesSoundStep);
    sound_wr(w, POKEY_AUDC2, 0xA4);
}

enum { S_51A, S_52C, S_533, S_53F };

void siren(World *w)
{
    int step, label = S_51A, de, a;

    w->FrightSound[3] = 0;                           /* the frightened sound starts afresh the next time */
    if (w->SirenInit == 0) {
        w->SirenTone = 0x28;
        w->SirenInit = 1;
        w->SirenDir = 1;
    }
    step = w->SirenStep;
    for (;;) {
        de = w->SirenTone;
        if (label == S_51A) {
            if (w->SirenDir == 1) {
                if (de >= 0x40) {
                    w->SirenDir = 2;
                    label = S_53F;
                } else {
                    label = S_52C;
                }
            } else {
                label = S_533;
            }
        } else if (label == S_52C) {
            a = (step + de) & 0xFF;
            if (a != 0) {
                break;
            }
            label = S_533;
        } else if (label == S_533) {
            if (de >= 0x28) {
                label = S_53F;
            } else {
                w->SirenDir = 1;
                label = S_52C;
            }
        } else {
            a = (de - step) & 0xFF;
            break;
        }
    }
    w->SirenTone = (uint8_t)a;
    sound_wr(w, POKEY_AUDF2, a);
    sound_wr(w, POKEY_AUDC2, 0xA1);
}

/* ------------------------------------------------------------------------------------------------ the eaten-ghost pause */
static void eaten_pause_end(World *w)
{
    int x;

    clear_pokey(w);
    sound_wr(w, POKEY_AUDCTL, 0);
    w->EatPause = 0;
    w->PacHold = 0;
    w->EatenGhost = 0xFF;                            /* Y after ClearPokeyRegisters */
    w->shadow[0xC7] = 0x2A;                          /* COLOR3 */
    w->shadow[0x6F] = PRIORITY_NORMAL;                          /* GPRIOR */
    for (x = 3; x >= 0; x--) {
        if (w->shadow[0xC0 + x] == 0xDC) {           /* PCOLR0 + x: the ghost shown in the pop-up colour */
            w->shadow[0xC0 + x] = 0x0C;
            sound_wr(w, GTIA_HITCLR, 0);
            w->PacHold = 0;
            move_pacman(w);
            w->PacCornering = (uint8_t)(w->PacCornering + 1u);
            eat_dot(w);
            return;
        }
    }
}

void ghost_eaten_pause(World *w)
{
    int a, r;

    w->EatPauseTick = (uint8_t)(w->EatPauseTick - 1u);
    if (w->EatPauseTick == 0) {
        w->EatPauseTick = 2;
        w->EatPausePitch = (uint8_t)(w->EatPausePitch - 3u);
        sound_wr(w, POKEY_AUDF1, w->EatPausePitch);
        sound_wr(w, POKEY_AUDF3, w->EatPausePitch);
        sound_wr(w, POKEY_AUDF4, w->EatPausePitch);
        sound_wr(w, POKEY_AUDC3, POKEY_FREQ_BASE);
        a = POKEY_FREQ_BASE;
    } else {
        w->EatPausePitch = (uint8_t)(w->EatPausePitch - 4u);
        if (w->EatPausePitch == 0x10) {
            eaten_pause_end(w);
            return;
        }
        sound_wr(w, POKEY_AUDF1, w->EatPausePitch);
        sound_wr(w, POKEY_AUDF4, w->EatPausePitch);
        sound_wr(w, POKEY_AUDCTL, 0x84);
        a = 0xA4;
    }
    r = a;
    sound_wr(w, POKEY_AUDC4, r);
    sound_wr(w, POKEY_AUDC1, r);
}

/* ------------------------------------------------------------------------------------------------ the start tune */
int start_tune_step(World *w)
{
    int x;

    if (w->RTCLOK2 & 3) {
        return 0;
    }
    x = w->TuneStep;
    if (x == 0x40) {
        w->PlayStarted = (uint8_t)(w->PlayStarted + 1u);
        w->GhostState[0] = (uint8_t)(w->GhostState[0] + 1u);
        return 3;
    }
    sound_wr(w, POKEY_AUDF1, table_rom((uint16_t)(0xBC50 + x)));
    sound_wr(w, POKEY_AUDF2, table_rom((uint16_t)(0xBC90 + x)));
    sound_wr(w, POKEY_AUDC1, 0xA8);
    sound_wr(w, POKEY_AUDC2, 0xA4);
    w->TuneStep = (uint8_t)(w->TuneStep + 1u);
    if (x == 0x28) {
        draw_all_in_place(w);                        /* DrawReadyScreen $AD0E: the four ghosts where they stand, Pac-Man's full disc */
        w->Lives[w->CurrentPlayer] = (uint8_t)(w->Lives[w->CurrentPlayer] - 1u);   /* then one life is used for this board */
        draw_lives(w);
        return 2;
    }
    return 1;
}

/* ------------------------------------------------------------------------------------------------ the death */
void toggle_leg_phase(World *w)
{
    if ((w->RTCLOK2 & 0x0F) == 0) {
        w->LegPhase = w->LegPhase ? 0 : 1;
    }
}

static void glide_up(World *w)
{
    sound_wr(w, POKEY_AUDC1, POKEY_FREQ_BASE);
    sound_wr(w, POKEY_AUDF1, w->DeathPitch);
    w->DeathPitch = (uint8_t)(w->DeathPitch + 8u);
    w->DeathStep = (uint8_t)(w->DeathStep + 1u);
    if (w->DeathStep == 4) {
        w->DeathState = 4;
    }
}

void death_sequence(World *w)
{
    int s = w->DeathState;
    int x;

    if (s == 1) {
        if (w->DeathFreeze) {
            toggle_leg_phase(w);
            for (x = 3; x >= 0; x--) {
                step_entity(w, x, w->EntityDir[x]);
            }
            w->DeathFreeze = (uint8_t)(w->DeathFreeze - 1u);
            return;
        }
        w->DeathState = 2;
        s = 2;
    }
    if (s == 2) {
        for (x = 3; x >= 0; x--) {
            w->hpos[x] = 0;                          /* HPOSP0-3: the ghosts leave the screen */
        }
        w->DeathPitch = 0x35;
        w->DeathBasePitch = 0x35;
        clear_pokey(w);
        w->DeathStep = 0;
        w->DeathAnimFrame = 0;
        w->DeathAnimActive = (uint8_t)(w->DeathAnimActive + 1u);
        w->DeathAnimDelay = DEATH_ANIM_DELAY;
        w->DeathState = 3;
        glide_up(w);
        return;
    }
    if (s == 4) {
        sound_wr(w, POKEY_AUDC1, POKEY_FREQ_BASE);
        sound_wr(w, POKEY_AUDF1, w->DeathPitch);
        w->DeathPitch = (uint8_t)(w->DeathPitch - 8u);
        w->DeathStep = (uint8_t)(w->DeathStep - 1u);
        if (w->DeathStep != 0) {
            return;
        }
        if (w->DeathBasePitch == 0x6D) {
            w->DeathState = (uint8_t)(w->DeathState + 1u);
            return;
        }
        w->DeathBasePitch = (uint8_t)(w->DeathBasePitch + 4u);
        w->DeathPitch = w->DeathBasePitch;
        w->DeathState = 3;
        return;
    }
    if (s == 5) {
        sound_wr(w, POKEY_AUDC1, POKEY_FREQ_BASE);
        sound_wr(w, POKEY_AUDF1, w->DeathBasePitch);
        w->DeathBasePitch = (uint8_t)(w->DeathBasePitch - 8u);
        if (w->DeathBasePitch != 0x25) {
            return;
        }
        clear_pokey(w);
        w->DeathStep = 0x80;
        w->DeathState = (uint8_t)(w->DeathState + 1u);
        return;
    }
    if (s == 6) {
        if (w->DeathStep) {
            w->DeathStep = (uint8_t)(w->DeathStep - 1u);
        } else {
            w->WaitState = (uint8_t)(w->WaitState + 1u);
        }
        return;
    }
    glide_up(w);                                     /* state 3, and any other value the chain does not name */
}

void death_animation(World *w)
{
    if (w->DeathAnimActive == 0) {
        return;
    }
    if (w->DeathAnimDelay != 0) {
        w->DeathAnimDelay = (uint8_t)(w->DeathAnimDelay - 1u);
        if ((w->DeathAnimDelay & 0x80) == 0) {
            death_animation_draw(w);
            return;
        }
    }
    if (w->DeathAnimFrame == 0x0F) {
        death_animation_clear(w);
        w->DeathAnimActive = 0;
        return;
    }
    w->DeathAnimFrame = (uint8_t)(w->DeathAnimFrame + 1u);
    w->DeathAnimDelay = DEATH_ANIM_DELAY;
    death_animation_draw(w);
}
