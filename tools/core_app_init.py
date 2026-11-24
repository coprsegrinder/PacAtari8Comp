"""Stage 78a (docs/51 section 3): STATE INITIALISATION IN PORT FORM, on the named World of tools/core_world.py - the first part of the application layer, the part of the game that was specified by measurement only (docs/43, 46).
Each function is the logic of one ROM routine (named in its docstring); tools/check_app_init.py runs each against the routine on the concrete 6502 from random states (the whole zero page, the maze and its saved copies, the
status rows, the shadows, the player-missile pages, the ordered chip writes compared).
  InitBoard             `$ADAF`  the start of every turn and every board: the player-missile pages cleared, `$80-$FF` cleared, the start positions and directions, the colours, the move delays, the release timers
  NewGameInit           `$ADF1`  lives 3, the start level for both players, the counters of player 2, then NewBoardInit
  NewBoardInit          `$AE02`  a new maze for the player on turn (the stored maze copied to the screen), the lives icons, the release timers, the counters of the player on turn
  ClearPlayerCounters   `$AE1E`  the pellet flags $0F, the bonus count, the dots eaten (16 bits) of player X
  SetReleaseTimers      `$AE2B`  the release timers of ghosts 1-3 from the table, a window that slides with Y (clamped at 3)
  LoadShadowColors      `$B113`  the eight colour shadows PCOLR0-3, COLOR0-3 from the game's colour table
  Copy0800To0C00 / Copy0C00To1000 / Copy0C00To1400   `$B11F` `$B13D` `$B15B`  the stored maze to the screen; the screen to player 1's saved maze and to player 2's
The state they keep in screen memory (the stored maze `$0800`, the saved mazes `$1000` and `$1400`) is in the World as `maze_orig`, `saved1`, `saved2`."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core_draw as D  # noqa: E402
import core_score as S  # noqa: E402
import core_sound as SO  # noqa: E402
import core_tables as T  # noqa: E402
import core_world as W  # noqa: E402

COLORS_GAME = 0xBBE2          # ColorsGame: 8 bytes (PCOLR0-3, COLOR0-3)
ZERO_PAGE_INIT_80 = 0xBB6F    # ZeroPageInit80: 20 bytes copied to $80-$93
HITCLR = 0xD01E

ADDR = {}                      # zero-page address -> (field name, index or None)
for _name, _addr, _n in W.FIELDS:
    for _k in range(_n):
        ADDR[_addr + _k] = (_name, None if _n == 1 else _k)


def set_zp(w, addr, value):
    """a zero-page byte by its address (a field, or one element of an array field)"""
    name, k = ADDR[addr]
    if k is None:
        setattr(w, name, value & 0xFF)
    else:
        getattr(w, name)[k] = value & 0xFF


def clear_zp(w, lo, hi):
    """the zero-page bytes lo .. hi-1 to 0"""
    for a in range(lo, hi):
        set_zp(w, a, 0)


# ------------------------------------------------------------------------------------------------ the maze copies and the colours
def copy_0800_to_0c00(w):
    """Copy0800To0C00 $B11F: the stored maze to the maze screen"""
    w.maze = list(w.maze_orig)


def copy_0c00_to_1000(w):
    """Copy0C00To1000 $B13D: the maze screen to player 1's saved maze"""
    w.saved1 = list(w.maze)


def copy_0c00_to_1400(w):
    """Copy0C00To1400 $B15B: the maze screen to player 2's saved maze"""
    w.saved2 = list(w.maze)


def load_shadow_colors(w):
    """LoadShadowColors $B113: PCOLR0-3 and COLOR0-3 (the shadows $02C0-$02C7) from ColorsGame"""
    for x in range(7, -1, -1):
        w.shadow[0xC0 + x] = T.rom(COLORS_GAME + x)


# ------------------------------------------------------------------------------------------------ the counters and the timers
def clear_player_counters(w, x):
    """ClearPlayerCounters $AE1E: player x (0 or 1): all four power pellets still there, no bonus shown yet, no dot eaten"""
    w.PelletFlags[x] = 0x0F
    w.BonusCount[x] = 0
    w.DotsEatenLo[x] = 0
    w.DotsEatenHi[x] = 0


def set_release_timers(w, y):
    """SetReleaseTimers $AE2B: the release timers of ghosts 1, 2, 3 are the three bytes of HouseReleaseTimers from Y on, in the order ghost 3, 2, 1 (Y clamped at 3)"""
    y = min(y & 0xFF, 3)
    for x in (2, 1, 0):
        w.GhostTimer[1 + x] = T.rom(0xBBF2 + y)
        y += 1


# ------------------------------------------------------------------------------------------------ the start of a board
def init_board(w):
    """InitBoard $ADAF: the start of every turn and of every board"""
    D.clear_player_memory(w)
    clear_zp(w, 0x80, 0x100)
    load_shadow_colors(w)
    lv = min(w.Level[w.CurrentPlayer], 6)
    w.MoveDelayCount[4] = T.MOVE_DELAY[T.PAC_DELAY_BASE[lv]]               # Pac-Man's pacing
    for x in (3, 2, 1, 0):
        w.MoveDelayCount[x] = T.MOVE_DELAY[T.GHOST_DELAY_BASE[lv]]          # the four ghosts: the same entry (Y does not move in the loop)
    for x in range(19, -1, -1):
        set_zp(w, 0x80 + x, T.rom(ZERO_PAGE_INIT_80 + x))                  # MazePtr, PacSubX, LastCell, the start positions and directions
    set_release_timers(w, 0)
    SO.wr(w, HITCLR, 0)


def new_board_init(w):
    """NewBoardInit $AE02: a new maze for the player on turn; the release timers depend on the level (and, on level 0, on the clock: the code's quirk); the player's counters"""
    copy_0800_to_0c00(w)
    S.draw_lives(w)
    p = w.CurrentPlayer
    y = w.Level[p]
    if y == 0 and w.RTCLOK2 & 0x80:
        set_release_timers(w, 0)                                           # LAE13 with Y = 0
    else:
        y = (y + 1) & 0xFF                                                 # LAE19: iny; bne LAE13 (a level of 255 skips the timers)
        if y != 0:
            set_release_timers(w, y)
    clear_player_counters(w, p)


def new_game_init(w):
    """NewGameInit $ADF1: three lives each, the start level for both, player 2's counters, then the first board"""
    w.Lives[0] = w.Lives[1] = 3
    w.Level[0] = w.Level[1] = w.StartLevel
    clear_player_counters(w, 1)
    new_board_init(w)
