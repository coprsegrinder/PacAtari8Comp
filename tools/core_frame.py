"""OV-67 (stage 66): THE REST OF THE GHOST LOGIC THAT RUNS EVERY FRAME, in port form on the named World: the frightened period (FrightenedTick), a ghost eaten (GhostEaten) and the eaten ghosts' way home with the ghost house
(EyesAndHousePerFrame).  They use the movement and house functions of tools/core_ghost.py and the sounds of tools/core_sound.py.  The drawing (the pop-up in the player-missile pages, the sprite positions) is left out; its
pointers in the zero page are kept.  tools/check_frame.py runs them against the ROM."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core_draw as D  # noqa: E402
import core_ghost as G  # noqa: E402
import core_ref as R  # noqa: E402
import core_score as S  # noqa: E402
import core_sound as SO  # noqa: E402
import core_tables as T  # noqa: E402

PCOLR0 = 0xC0           # index of PCOLR0 in w.shadow


def _flash_colours(w):
    """the frightened ghosts alternate blue ($84) and white ($0C) with the phase"""
    y = 0x84 if w.FrightenPhase & 1 else 0x0C
    for x in (3, 2, 1, 0):
        if w.GhostState[x] & 0x80:
            w.shadow[PCOLR0 + x] = y


def frightened_tick(w):
    """FrightenedTick $AF54: the frightened period: the sound, the solid countdown, then the phase steps every 24 frames (flashing) until the level's end phase; the end turns the ghosts back.  Phase 0 is the normal
    siren (it plays when no eaten ghost is returning)"""
    if w.FrightenPhase == 0:
        if w.EyesReturning == 0:
            SO.siren(w)
        return
    if w.EyesReturning == 0:
        SO.frightened_sound(w)
    if w.FrightenCountdown:
        w.FrightenCountdown -= 1
        return _flash_colours(w)
    if R.fright_end_phase(w.Level[w.CurrentPlayer]) == w.FrightenPhase:
        for x in (3, 2, 1, 0):
            if w.GhostState[x] & 0x80:
                w.shadow[PCOLR0 + x] = T.rom(0xBBE2 + x)
        w.GhostState = R.frightened_end(list(w.GhostState))
        w.FrightenPhase = w.FrightenFlashTimer = 0
        w.FrightSound[3] = 0
        w.ChaseTimer = 0xA0
        return
    if w.FrightenFlashTimer == 0:
        w.FrightenPhase = (w.FrightenPhase + 1) & 0xFF
        w.FrightenFlashTimer = 0x18
    w.FrightenFlashTimer = (w.FrightenFlashTimer - 1) & 0xFF
    _flash_colours(w)


def ghost_eaten(w, x):
    """GhostEaten $A886: Pac-Man touches frightened ghost x: it becomes eyes ($42), the count of ghosts eaten goes up, the points (200 / 400 / 800 / 1600 by the count) are added, the game pauses for 34 frames with the falling sweep"""
    w.GhostState[x] = 0x42
    w.EatenGhost = x
    w.GhostsEaten = (w.GhostsEaten + 1) & 0xFF
    w.shadow[0xC7] = 0xDC                            # COLOR3
    w.shadow[PCOLR0 + x] = 0xDC
    D.draw_popup(w, x)
    py, ey = w.EntityY[4], w.EntityY[x]
    a = py if py == ey else ((py + 2) if py < ey else (py - 2)) & 0xFF
    w.PopupMissilePtr[0] = w.PopupPlayerPtr[0] = a
    w.PopupMissilePtr[1] = 0x23
    w.PopupPlayerPtr[1] = (x + 0x23 + 1) & 0xFF
    SO.wr(w, SO.AUDC2, 0)
    w.EatPause = (w.EatPause + 1) & 0xFF
    w.EatPausePitch = 0x84
    w.EatPauseTick = 2
    w.shadow[0x6F] = 0x14                            # GPRIOR: the pop-up in front
    g = w.GhostsEaten
    if g == 0:
        w.ScoreAdd[3] = 2
    elif g == 1:
        w.ScoreAdd[3] = 4
    elif g == 2:
        w.ScoreAdd[3] = 8
    else:
        w.ScoreAdd[2] = 1
        w.ScoreAdd[3] = 6
    S.add_to_score(w)


def eyes_and_house_per_frame(w, rnd):
    """EyesAndHousePerFrame $B69D: every eaten ghost (eyes) steers to the door square and moves every frame (no pacing); at the door it turns into state $44, enters the house and comes out again; the whistle plays
    while eyes are on their way; waiting ghosts in the house leave on every 4th jiffy"""
    w.EyesReturning = 0
    for x in (3, 2, 1, 0):
        s = w.GhostState[x]
        if s == 0x44 or not s & 0x40 or x == w.EatenGhost:
            continue
        w.EyesReturning += 1
        if w.EntityX[x] == G.DOOR_X and w.EntityY[x] == G.DOOR_Y:
            if w.EntityDir[x] == 1:
                w.EntityDir[x] = 4                   # arriving from below: turn left first
            else:
                w.GhostState[x] = 0x44
                w.StartRouteStep[x] = 0xFF
                continue
        mask, on = G.junction_lookup(w, x)
        if on:
            w.TargetX[x], w.TargetY[x] = G.DOOR_X, G.DOOR_Y
            G.steer_to_target(w, x, mask, rnd)
        G.step_entity(w, x, w.EntityDir[x])
    if w.EyesReturning == 0:
        w.EyesSoundStep = 0
    elif w.EatPause == 0:
        SO.eyes_returning_sound(w)
    for x in (3, 2, 1, 0):
        s = w.GhostState[x]
        if not (s >> 2) & 1:
            continue
        if s & 0x40:
            G.house_enter_step(w, x)
        elif w.RTCLOK2 & 3 == 0:
            G.house_leave(w, x)
