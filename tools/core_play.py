"""OV-67 (stage 66): ONE FRAME OF PLAY IN PORT FORM - the frame body of FrameDispatch from $A82C (WaitState 0, the game running): the death, the eyes and the house, the eaten-ghost pause, the bonus item, the power pellet,
the contact of Pac-Man with a ghost (eaten or killed), the bonus pick-up, then the frightened tick, the sounds, Pac-Man's pacing and step, the dot, the ghost house, the chase timer and every ghost's pacing and move.
It is the composition of the port-form functions of core_ghost / core_pacman / core_score / core_sound / core_frame plus the glue written here; tools/check_play.py runs it against the ROM from $A82C.
`w.collide` holds the GTIA collision registers ($D000-$D00F) as an input; `rnd` is the iterator of POKEY RANDOM values."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core_draw as D  # noqa: E402
import core_frame as F  # noqa: E402
import core_ghost as G  # noqa: E402
import core_pacman as P  # noqa: E402
import core_ref as R  # noqa: E402
import core_score as S  # noqa: E402
import core_sound as SO  # noqa: E402
import core_tables as T  # noqa: E402

M2PF, M1PL, M2PL = 2, 9, 10                      # index into w.collide
PELLET_CELLS = (0x7B, 0x9C, 0x283)               # the first three power-pellet cells of the maze screen ($0C7B, $0C9C, $0E83 minus $0C00); the fourth is $2A4
LAST_PELLET_CELL = 0x2A4
BONUS_CELLS = 0x1F1                              # $0DF1: five cells of the bonus score picture; the bonus item is at $0DF3-$0DF4


def show_power_pellets(w):
    """ShowPowerPellets $B551: the pellets still on the board are drawn (char 2); the fourth cell is written with the value left in Y"""
    flags = w.PelletFlags[w.CurrentPlayer]
    w.Scratch2A = flags
    for bit, cell in zip((1, 2, 4), PELLET_CELLS):
        if flags & bit:
            w.maze[cell] = 2
    if flags & 8:
        w.maze[LAST_PELLET_CELL] = 2


def blink_power_pellets(w):
    """BlinkPowerPellets $B54B: on every 16th jiffy the pellets are shown, 8 jiffies later they are hidden"""
    a = w.RTCLOK2 & 0x0F
    if a == 0:
        show_power_pellets(w)
    elif a == 8:
        for cell in PELLET_CELLS + (LAST_PELLET_CELL,):
            w.maze[cell] = 0


def bonus_item_update(w):
    """BonusItemUpdate $B62E: the bonus item appears at 80 and at 160 dots eaten (twice a board) for 704 frames; its score picture stays 64 frames after it was eaten"""
    if w.BonusScoreShown:
        if w.BonusScoreTimer == 0:
            w.BonusScoreShown = 0
            for k in range(5):
                w.maze[BONUS_CELLS + k] = 0
        else:
            w.BonusScoreTimer -= 1
        return
    if w.BonusVisible == 0:
        p = w.CurrentPlayer
        dots, t = w.DotsEatenLo[p], w.BonusCount[p]
        if t == 0:
            fire = dots in (0x50, 0xA0)
        elif t == 1:
            fire = dots == 0xA0
        else:
            return
        if not fire:
            return
        w.BonusCount[p] = (t + 1) & 0xFF
        code = R.bonus_glyph(w.Level[p])
        w.maze[0x1F3] = code
        w.maze[0x1F4] = (code + 1) & 0xFF
        w.BonusVisible = 1
        w.BonusTimer[0] = 0xC0
        w.BonusTimer[1] = 2
        return
    if w.BonusTimer[1] == 0 and w.BonusTimer[0] == 0:
        w.maze[0x1F3] = w.maze[0x1F4] = 0
        w.BonusVisible = 0
        return
    w.BonusTimer[0] = (w.BonusTimer[0] - 1) & 0xFF
    if w.BonusTimer[0] == 0:
        w.BonusTimer[1] = (w.BonusTimer[1] - 1) & 0xFF


def move_delay_tick(w, x):
    """MoveDelayTick $B590 on the World: True when entity x moves this frame"""
    moves, w.MoveDelayCycle[x], w.MoveDelayCount[x] = R.move_delay_tick(x, w.Level[w.CurrentPlayer], w.MoveDelayCycle[x], w.MoveDelayCount[x])
    return moves


def _pick_up_bonus(w):
    """$A93D: Pac-Man touched the bonus item (missile 2 on playfield 1): its score picture, 100-5000 points by level, and the bonus sound"""
    lv = min(w.Level[w.CurrentPlayer], 12)
    off = T.BONUS_SCORE_GLYPH_OFFSETS[lv]
    for k in range(5):
        w.maze[BONUS_CELLS + k] = T.BONUS_SCORE_GLYPHS[off + k]
    w.BonusScoreShown = 1
    w.BonusScoreTimer = 0x40
    w.BonusVisible = 0
    w.BonusTimer[0] = w.BonusTimer[1] = 0
    w.BonusSoundStep = 1
    w.BonusSoundPitch = 0x78
    w.ScoreAdd[2] = T.BONUS_SCORE[2 * lv]
    w.ScoreAdd[3] = T.BONUS_SCORE[2 * lv + 1]
    S.add_to_score(w)


def _contact_and_bonus(w):
    """$A843 - $A98B: the pellet, the contact with a ghost (frightened: eaten; otherwise Pac-Man is killed), the bonus pick-up.  Returns True when the frame is over (a ghost was eaten)"""
    bonus_item_update(w)
    S.power_pellet_check(w)
    if not w.LevelComplete:
        y = 1
        for x in range(4):
            if not (w.GhostState[x] << 1) & 0x80 and w.collide[M1PL] & y and w.collide[M2PL] & y:
                d = abs(w.EntityY[4] - w.EntityY[x])
                if d < 5:
                    if w.GhostState[x] & 0x80:
                        F.ghost_eaten(w, x)
                        return True
                    w.PacFrozen |= 0x80                       # the ghost kills Pac-Man: the death sequence starts
                    SO.clear_pokey(w)
                    w.DrawOnly = 1
                    w.DeathState = 1
                    w.DeathFreeze = 0x60
                    break
            y <<= 1
    if w.collide[M2PF] & 2:
        _pick_up_bonus(w)
    SO.wr(w, 0xD01E, 0)                                       # HITCLR
    return False


def play_frame(w, rnd):
    """the frame body of FrameDispatch from $A82C: one frame of the running game"""
    blink_power_pellets(w)
    if w.DeathState:
        SO.death_sequence(w)
        return SO.death_animation(w)
    F.eyes_and_house_per_frame(w, rnd)
    if w.EatPause:
        return SO.ghost_eaten_pause(w)
    if _contact_and_bonus(w):
        return
    if w.DeathState:
        return
    F.frightened_tick(w)
    if w.EatPause:
        return
    SO.dot_sound_sweep(w)
    SO.bonus_sound(w)
    SO.toggle_leg_phase(w)
    if w.PacCornering:
        hold = 0
    elif w.DotDelay:
        hold = w.DotDelay
    else:
        hold = 0 if move_delay_tick(w, 4) else 0xFF
    w.PacHold = hold
    w.PacCornering = 0
    P.move_pacman(w)
    w.DotDelay = 0
    S.eat_dot(w)
    if w.RTCLOK2 & 3 == 0:
        G.house_waiting_tick(w)
    G.chase_timer_siren_sight(w)
    if w.PacCornering:
        return                                                # Pac-Man turned a corner this frame: the ghosts stand still
    for x in (3, 2, 1, 0):
        s = w.GhostState[x]
        if s & 0x7F == 0:
            continue
        if w.RTCLOK2 & 7 == 0 and w.GhostTimer[x]:
            w.GhostTimer[x] -= 1
        s = w.GhostState[x]
        if s & 0x3F == 0 or (s << 1) & 0x80:
            continue
        in_tunnel = w.EntityY[x] == 0x74 and (w.EntityX[x] >= 0xA7 or w.EntityX[x] < 0x52)
        if in_tunnel or s & 0x80:                             # in the tunnel, and while frightened, a ghost moves every second tick
            if move_delay_tick(w, x):
                if w.HalfSpeedToggle[x] == 1:
                    w.HalfSpeedToggle[x] = 0
                    G.ghost_behaviour(w, x, rnd)
                else:
                    w.HalfSpeedToggle[x] = 1
        elif move_delay_tick(w, x):
            G.ghost_behaviour(w, x, rnd)


def vbi_play_frame(w, rnd):
    """the whole deferred vertical-blank handler `$A5FD` for a frame of the running game: the frame body, then - unless a ghost-eaten pause is on - the clipping of the pictures at the tunnel row (ClipEntitiesOnTunnelRow
    $AB48, which also wraps an entity that has gone through the tunnel; OV-69)"""
    play_frame(w, rnd)
    if w.EatPause == 0:
        D.clip_entities_on_tunnel_row(w)
