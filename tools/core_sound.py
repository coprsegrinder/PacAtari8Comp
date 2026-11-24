"""OV-67 (stage 66): THE SOUND AND THE DEATH IN PORT FORM on the named World (tools/core_world.py).  Every sound is a small state machine that runs once per frame (or per 4th jiffy) and writes the POKEY registers;
here each function updates its state variables and appends the register writes (address, value) to `w.pokey` in the order the ROM makes them.  Includes the routines whose state the sound drives: the eaten-ghost pause
and the death sequence.  The drawing (player-missile pages and positions, shapes) is left out; the collision clear HITCLR $D01E is kept.  tools/check_sound.py runs every function against the ROM routine and compares the zero page and the register writes.
POKEY: AUDF1 $D200, AUDC1 $D201, AUDF2 $D202, AUDC2 $D203, AUDF3 $D204, AUDC3 $D205, AUDF4 $D206, AUDC4 $D207, AUDCTL $D208."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core_tables as T  # noqa: E402
import core_draw as D  # noqa: E402
import core_ghost as G  # noqa: E402
import core_pacman as P  # noqa: E402
import core_score as S  # noqa: E402

AUDF1, AUDC1, AUDF2, AUDC2, AUDF3, AUDC3, AUDF4, AUDC4, AUDCTL = (0xD200 + k for k in range(9))
HITCLR = 0xD01E


def wr(w, addr, v):
    w.pokey.append((addr, v & 0xFF))


def clear_pokey(w):
    """ClearPokeyRegisters $B0E7: AUDC4 .. AUDF1 (eight registers, last first) to 0"""
    for k in range(7, -1, -1):
        wr(w, AUDF1 + k, 0)


# ------------------------------------------------------------------------------------------------ the dot sound and the bonus sound
def dot_sound_sweep(w):
    """DotSoundSweep $B0BC: the dot's six-note sweep on channel 1, rising and falling in turn"""
    if w.DotSoundActive == 0:
        return
    x = w.DotSoundStep
    if x == 6:
        w.DotSoundActive = w.DotSoundStep = 0
        wr(w, AUDC1, 0)
        return
    a = T.rom(0xBCDF + x) if w.DotSoundAlt else T.rom(0xBCD8 + x)
    w.DotSoundStep = (w.DotSoundStep + 1) & 0xFF
    wr(w, AUDF1, a)
    wr(w, AUDC1, 0xA4)


def bonus_sound(w):
    """BonusSound $ABC9: the bonus item's rising then falling sweep on channel 1 (steps in BonusSoundStep, pitch in BonusSoundPitch)"""
    x = w.BonusSoundStep
    if x == 0:
        return
    a, y = w.BonusSoundPitch, 0xA5
    if x < 7:
        last = a == 0xB4
        if not last:
            a = (a + 5) & 0xFF
            last = a == 0
        if last:                                     # at $B4, or when the sum wraps to 0 (it falls into the same code): the last step
            w.BonusSoundStep = (w.BonusSoundStep + 1) & 0xFF
            y = 0xA3
    else:
        if x == 9:
            w.BonusSoundStep = (w.BonusSoundStep + 1) & 0xFF
        else:
            y = 0xA3
        if a == 0x78:
            w.BonusSoundStep = 0
            a = y = 0
        else:
            a = (a - 5 - (1 if a < 0x78 else 0)) & 0xFF
    w.BonusSoundPitch = a
    wr(w, AUDF1, a)
    wr(w, AUDC1, y)


# ------------------------------------------------------------------------------------------------ the frightened sound, the eyes, the siren
def frightened_sound(w):
    """FrightenedSound $AFD7: the two-tone triangle sweep of the frightened period on channel 2 (E1 pitch, E2 direction, E3 depth, E4 started)"""
    f = w.FrightSound                                # [E1 pitch, E2 phase, E3 volume step, E4 started]
    if f[3] == 0:
        f[2], f[1] = 5, 2
        f[3] += 1
        f[0] = 0x90
    label = "AFE9"
    while True:
        if label == "AFE9":
            if f[1] != 1:
                label = "B00E"
            elif f[0] != 0x90:
                label = "B007"
            else:
                if f[2] == 3:
                    f[2] = 5
                f[2] = (f[2] - 1) & 0xFF
                f[1] = 2
                label = "B01A"
        elif label == "B007":
            a = (f[0] + 0x10) & 0xFF
            if a != 0:
                f[0] = a
                break
            label = "B00E"                           # a sum of 0 falls into $B00E
        elif label == "B00E":
            if f[0] != 0x40:
                label = "B01A"
            else:
                f[1] = 1
                label = "B007"
        else:                                        # B01A
            f[0] = (f[0] - 0x10) & 0xFF
            break
    wr(w, AUDF2, f[0])
    wr(w, AUDC2, f[2] | 0xA0)


def eyes_returning_sound(w):
    """EyesReturningSound $B02C: the rising whistle of the eaten ghosts' eyes on channel 2 (EyesSoundStep $0C-$17)"""
    if w.EyesSoundStep == 0:
        w.EyesSoundStep = 0x0C
    elif w.EyesSoundStep == 0x17:
        w.EyesSoundStep = 0x0C
    w.EyesSoundStep = (w.EyesSoundStep + 1) & 0xFF
    wr(w, AUDF2, w.EyesSoundStep)
    wr(w, AUDC2, 0xA4)


def siren(w):
    """the siren $B508: a triangle between $28 and $40 on channel 2, SirenStep per frame (it grows with the dots eaten)"""
    w.FrightSound[3] = 0                             # the frightened sound starts afresh the next time
    if w.SirenInit == 0:
        w.SirenTone = 0x28
        w.SirenInit = 1
        w.SirenDir = 1
    step = w.SirenStep
    label = "51A"
    while True:
        de = w.SirenTone
        if label == "51A":
            if w.SirenDir == 1:
                if de >= 0x40:
                    w.SirenDir = 2
                    label = "53F"
                else:
                    label = "52C"
            else:
                label = "533"
        elif label == "52C":
            a = (step + de) & 0xFF
            if a != 0:
                break
            label = "533"
        elif label == "533":
            if de >= 0x28:
                label = "53F"
            else:
                w.SirenDir = 1
                label = "52C"
        else:
            a = (de - step) & 0xFF
            break
    w.SirenTone = a
    wr(w, AUDF2, a)
    wr(w, AUDC2, 0xA1)


# ------------------------------------------------------------------------------------------------ the eaten-ghost pause
def ghost_eaten_pause(w):
    """GhostEatenPause $B04D: 34 frames of a falling two-channel sweep after a ghost was eaten; then the sound stops, the game goes on and Pac-Man steps once"""
    w.EatPauseTick = (w.EatPauseTick - 1) & 0xFF
    if w.EatPauseTick == 0:
        w.EatPauseTick = 2
        w.EatPausePitch = (w.EatPausePitch - 3) & 0xFF
        for r in (AUDF1, AUDF3, AUDF4):
            wr(w, r, w.EatPausePitch)
        wr(w, AUDC3, 0xA8)
        a = 0xA8
    else:
        w.EatPausePitch = (w.EatPausePitch - 4) & 0xFF
        if w.EatPausePitch == 0x10:
            return _eaten_pause_end(w)
        wr(w, AUDF1, w.EatPausePitch)
        wr(w, AUDF4, w.EatPausePitch)
        wr(w, AUDCTL, 0x84)
        a = 0xA4
    wr(w, AUDC4, a)
    wr(w, AUDC1, a)


def _eaten_pause_end(w):
    clear_pokey(w)
    wr(w, AUDCTL, 0)
    w.EatPause = 0
    w.PacHold = 0
    w.EatenGhost = 0xFF                              # Y after ClearPokeyRegisters
    w.shadow[0xC7] = 0x2A                            # COLOR3
    w.shadow[0x6F] = 0x11                            # GPRIOR
    for x in (3, 2, 1, 0):
        if w.shadow[0xC0 + x] == 0xDC:               # PCOLR0 + x: the ghost shown in the pop-up colour
            w.shadow[0xC0 + x] = 0x0C
            wr(w, HITCLR, 0)
            w.PacHold = 0
            P.move_pacman(w)
            w.PacCornering = (w.PacCornering + 1) & 0xFF
            S.eat_dot(w)
            return


# ------------------------------------------------------------------------------------------------ the start tune
def start_tune_step(w):
    """the start tune block of FrameDispatch $A7D3: every 4th jiffy the next pair of notes (TuneAudf1/2), 64 steps; at step $28 the READY! screen is drawn (one life is used); after step $40 play starts"""
    if w.RTCLOK2 & 3:
        return "wait"
    x = w.TuneStep
    if x == 0x40:
        w.PlayStarted = (w.PlayStarted + 1) & 0xFF
        w.GhostState[0] = (w.GhostState[0] + 1) & 0xFF
        return "play"
    wr(w, AUDF1, T.rom(0xBC50 + x))
    wr(w, AUDF2, T.rom(0xBC90 + x))
    wr(w, AUDC1, 0xA8)
    wr(w, AUDC2, 0xA4)
    w.TuneStep = (w.TuneStep + 1) & 0xFF
    if x == 0x28:
        D.draw_all_in_place(w)                        # DrawReadyScreen $AD0E: DrawAllInPlace (sets DrawOnly for its own drawing and clears it): the four ghosts where they stand, Pac-Man's full disc
        w.Lives[w.CurrentPlayer] = (w.Lives[w.CurrentPlayer] - 1) & 0xFF      # then one life is used for this board
        S.draw_lives(w)
        return "ready"
    return "tune"


# ------------------------------------------------------------------------------------------------ the death
def toggle_leg_phase(w):
    """ToggleLegPhase $AC05: every 16th jiffy the ghosts' legs change picture"""
    if w.RTCLOK2 & 0x0F == 0:
        w.LegPhase = 0 if w.LegPhase else 1


def death_sequence(w):
    """DeathSequence $AE3E: state 1 freezes the game (97 frames, the ghosts' legs move), state 2 starts the sound and the animation, states 3-5 are the sound glide, state 6 waits and hands over to the turn control (WaitState)"""
    s = w.DeathState
    if s == 1:
        if w.DeathFreeze:
            toggle_leg_phase(w)
            for x in (3, 2, 1, 0):
                G.step_entity(w, x, w.EntityDir[x])
            w.DeathFreeze -= 1
            return
        w.DeathState = s = 2
    if s == 2:
        for x in range(3, -1, -1):
            w.hpos[x] = 0                                # HPOSP0-3: the ghosts leave the screen
        w.DeathPitch = w.DeathBasePitch = 0x35
        clear_pokey(w)
        w.DeathStep = 0
        w.DeathAnimFrame = 0
        w.DeathAnimActive = (w.DeathAnimActive + 1) & 0xFF
        w.DeathAnimDelay = 7
        w.DeathState = 3
        return _glide_up(w)
    if s == 4:
        wr(w, AUDC1, 0xA8)
        wr(w, AUDF1, w.DeathPitch)
        w.DeathPitch = (w.DeathPitch - 8) & 0xFF
        w.DeathStep = (w.DeathStep - 1) & 0xFF
        if w.DeathStep != 0:
            return
        if w.DeathBasePitch == 0x6D:
            w.DeathState = (w.DeathState + 1) & 0xFF
            return
        w.DeathBasePitch = (w.DeathBasePitch + 4) & 0xFF
        w.DeathPitch = w.DeathBasePitch
        w.DeathState = 3
        return
    if s == 5:
        wr(w, AUDC1, 0xA8)
        wr(w, AUDF1, w.DeathBasePitch)
        w.DeathBasePitch = (w.DeathBasePitch - 8) & 0xFF
        if w.DeathBasePitch != 0x25:
            return
        clear_pokey(w)
        w.DeathStep = 0x80
        w.DeathState = (w.DeathState + 1) & 0xFF
        return
    if s == 6:
        if w.DeathStep:
            w.DeathStep -= 1
        else:
            w.WaitState = (w.WaitState + 1) & 0xFF
        return
    return _glide_up(w)                              # state 3, and any other value the chain does not name


def _glide_up(w):
    wr(w, AUDC1, 0xA8)
    wr(w, AUDF1, w.DeathPitch)
    w.DeathPitch = (w.DeathPitch + 8) & 0xFF
    w.DeathStep = (w.DeathStep + 1) & 0xFF
    if w.DeathStep == 4:
        w.DeathState = 4


def death_animation(w):
    """DeathAnimation $AEF7: the counters of the 16-picture animation (8 frames each) and the pictures (core_draw, OV-69)"""
    if w.DeathAnimActive == 0:
        return
    if w.DeathAnimDelay != 0:
        w.DeathAnimDelay = (w.DeathAnimDelay - 1) & 0xFF
        if w.DeathAnimDelay & 0x80 == 0:
            D.death_animation_draw(w)
            return
    if w.DeathAnimFrame == 0x0F:
        D.death_animation_clear(w)
        w.DeathAnimActive = 0
        return
    w.DeathAnimFrame = (w.DeathAnimFrame + 1) & 0xFF
    w.DeathAnimDelay = 7
    D.death_animation_draw(w)
