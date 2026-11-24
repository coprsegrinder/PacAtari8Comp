"""Stage 78c (docs/51 section 3): THE FRAME DISPATCHER IN PORT FORM - the third part of the application layer.  `FrameDispatch` ($A6CC) decides, by GameState and the flags of the game in the order of the code, which of the
15 frame classes of docs/38 this frame is, and runs it:
   GameState 1  copyright setup  (InitDisplay2, the title memory cleared, the copyright text and the logo)        GameState 2  copyright wait (until the jiffy clock reaches CopyrightEnd)
   GameState 3, 4  the title menu (the players, the start level, the texts; at 3 the scores are cleared)
   GameState 0  the game: the countdown byte falls every 8th jiffy; paused -> the chip cleared; the player label blinks; board start (IntroRequest 2); the game-over countdown's labels; the level end; the start idle / the start
                tune; then WaitState: turn control (1), the READY! wait (2, any other non-zero value too), and WaitState 0 the frame of play (core_play, which has the death and the eaten pause first)
`vbi_handler` is the deferred vertical-blank handler $A5FD: the band counter, the key debounce, the dispatch, and the tunnel clip unless the eaten-ghost pause is on.
tools/check_app_frame.py runs each class against the ROM from random states.  What is not modelled (no state of the World): the writes to the ANTIC and GTIA registers other than the positions (the display-list pointer,
$D402-$D403, and the colour of COLPF3 are the screen set-up the renderer derives from the shadows); the 16 bytes InitDisplay2 writes into the ROM at $A5xx (ignored by the machine, found in docs/42)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core_app_board as AB  # noqa: E402
import core_draw as D  # noqa: E402
import core_play as PL  # noqa: E402
import core_sound as SO  # noqa: E402
import core_tables as T  # noqa: E402

COLORS_TITLE = 0xBBEA        # ColorsTitle: 4 bytes, COLOR0-3 of the title
TEXT_COPYRIGHT = 0xBDF7      # 14 bytes
TEXT_PLAYER_GAME = 0xBFC6    # 11 bytes
TEXT_PRESS_SELECT_FOR = 0xBFD1   # 16 bytes
TEXT_PRESS_OPTION_TO = 0xBFE1    # 16 bytes
TEXT_PRESS_START_TO = 0xBDE7     # 16 bytes
TEXT_CHANGE_DIFFICULTY = 0xBDD6  # 17 bytes
TEXT_PLAY_GAME = 0xBFF1      # 9 bytes
LEVEL_ICON_CODES = 0xBE05


# ------------------------------------------------------------------------------------------------ the display and the title scores
def init_display2(w):
    """InitDisplay2 $A610: the eight positions and the eight sound registers to 0, the display list and its interrupt vector (shadows), the title colours.  It ends in the drawing routine's tail with the X register left over from
    SetDisplayList ($81): DstPtr's high byte becomes $24 + $81 = $A5 (16 bytes are then copied INTO THE ROM, which does nothing: docs/42)"""
    for x in range(7, -1, -1):
        w.hpos[x] = 0
        SO.wr(w, 0xD200 + x, 0)
    w.shadow[0x30] = 0x81                          # SDLSTL
    w.shadow[0x31] = 0xBF                          # SDLSTH
    w.shadow[0x00] = 0xCE                          # VDSLST
    w.shadow[0x01] = 0xA5
    for y in range(3, -1, -1):
        w.shadow[0xC4 + y] = T.rom(COLORS_TITLE + y)
    w.DstPtr[1] = 0xA5


def title_clear_scores_1p(w):
    """TitleClearScores1P $A632: both players' scores and the 1UP area cleared, the 1UP label, the two leading digit cells of the high-score line"""
    for x in range(6, -1, -1):
        w.status[0x20 + x] = 0
        w.status[0x47 + x] = 0
        w.status[0x2A + x] = 0
    _tail(w)


def title_clear_scores_2p(w):
    """TitleClearScores2P $A64E"""
    for x in range(6, -1, -1):
        w.status[0x2A + x] = 0
        w.status[0x47 + x] = 0
    AB.draw_label_2up(w)
    w.status[0x4B] = 0x10
    w.status[0x4C] = 0x10
    _tail(w)


def _tail(w):
    AB.draw_label_1up(w)
    w.status[0x2E] = 0x10
    w.status[0x2F] = 0x10


# ------------------------------------------------------------------------------------------------ the copyright screens and the title menu
def copyright_setup(w):
    """GameState 1 ($A6D7-$A70A): the display, the title memory $1C00-$1DFF and the maze page $0F00 cleared, COLOR1 0, the copyright text, the 12 + 12 cells of the logo, GameState 2"""
    init_display2(w)
    for x in range(256):
        w.title[x] = 0
        w.title[0x100 + x] = 0
        w.maze[0x300 + x] = 0
    w.shadow[0xC5] = 0
    for x in range(13, -1, -1):
        w.title[0x157 + x] = T.rom(TEXT_COPYRIGHT + x)
    for x in range(12):
        w.title[0x18 + x] = (x + 0xC1) & 0xFF
        w.title[0x2C + x] = (x + 0xCD) & 0xFF
    w.GameState = (w.GameState + 1) & 0xFF


def copyright_wait(w):
    """GameState 2 ($A70D): wait until the jiffy clock equals CopyrightEnd, then GameState 3"""
    if w.CopyrightEnd == w.RTCLOK2:
        w.GameState = (w.GameState + 1) & 0xFF


def title_menu(w):
    """GameState 3 and 4 ($A719-$A78B): the title screen, redrawn every frame: the number of players, 'PLAYER GAME', the display again, the three lines of text, the start-level icon, 'CHANGE DIFFICULTY', 'PLAY GAME'.
    In state 3 (the first title frame of a session) the scores are cleared first"""
    gs = w.GameState
    w.title[0x54] = ((w.TwoPlayers + 1) & 0xFF) | 0x50
    if w.TwoPlayers == 0:
        if gs == 3:
            title_clear_scores_1p(w)
        a = 0x12
    else:
        if gs == 3:
            title_clear_scores_2p(w)
        a = 0x11
    w.title[0x90] = a
    for x in range(0x0A, -1, -1):
        c = T.rom(TEXT_PLAYER_GAME + x)
        w.title[0x92 + x] = c
        w.title[0x56 + x] = c | 0x40
    init_display2(w)
    for x in range(0x0F, -1, -1):
        w.title[0x7A + x] = T.rom(TEXT_PRESS_SELECT_FOR + x)
        w.title[0xF2 + x] = T.rom(TEXT_PRESS_OPTION_TO + x)
        w.title[0x156 + x] = T.rom(TEXT_PRESS_START_TO + x)
    a = T.rom(LEVEL_ICON_CODES + w.StartLevel)
    w.title[0xC6] = a
    w.title[0xC7] = (a + 1) & 0xFF
    for x in range(0x10, -1, -1):
        w.title[0x105 + x] = T.rom(TEXT_CHANGE_DIFFICULTY + x)
    for x in range(8, -1, -1):
        w.title[0x16D + x] = T.rom(TEXT_PLAY_GAME + x)


# ------------------------------------------------------------------------------------------------ the game
def _wait_state(w, rnd):
    """$A805: the WaitState dispatch (the READY! wait ends into the frame of play in the same frame)"""
    while True:
        if w.WaitState == 0:
            return PL.play_frame(w, rnd)
        if w.WaitState == 1:
            AB.turn_control(w)
            if w.TurnSwitchState != 0:
                return
            if w.CountdownActive != 0:
                return
            w.WaitState = (w.WaitState + 1) & 0xFF
            w.WaitTimer = 0x40
            return
        if w.WaitTimer != 0:
            w.WaitTimer = (w.WaitTimer - 1) & 0xFF
            return
        w.WaitState = 0
        w.GhostState[0] = (w.GhostState[0] + 1) & 0xFF                  # LA800: ghost 0 leaves its start state
        AB.clear_ready_text(w)


def game_frame(w, rnd):
    """GameState 0 ($A78C)"""
    if w.CountdownTimer != 0 and w.RTCLOK2 & 7 == 0:
        w.CountdownTimer = (w.CountdownTimer - 1) & 0xFF
    if w.Paused:
        return SO.clear_pokey(w)
    AB.blink_player_label(w)
    if w.IntroRequest == 2:                                             # board start
        w.StartTuneActive = (w.StartTuneActive + 1) & 0xFF
        w.ATRACT = 0
        w.IntroRequest = 0
        return AB.draw_level_indicator(w)
    if w.CountdownActive:                                               # the game-over countdown: the labels
        if w.TwoPlayers:
            AB.draw_label_2up(w)
        return AB.draw_label_1up(w)
    if w.LevelComplete:
        return AB.level_end_step(w)
    if w.PlayStarted == 0:
        if w.StartTuneActive == 0:
            return
        if SO.start_tune_step(w) != "play":
            return
        AB.clear_ready_text(w)
    return _wait_state(w, rnd)


def frame_dispatch(w, rnd):
    """FrameDispatch $A6CC: one frame of the game or the title"""
    gs = w.GameState
    if gs == 0:
        return game_frame(w, rnd)
    if gs == 1:
        return copyright_setup(w)
    if gs == 2:
        return copyright_wait(w)
    return title_menu(w)


def vbi_handler(w, rnd):
    """the deferred vertical-blank handler $A5FD (up to its jump to the OS exit): the band counter of the display-list interrupts to 0, the key debounce down by one, the frame, and the tunnel clip unless a ghost-eaten pause
    is on"""
    w.BandCounter = 0
    w.KeyDebounce = (w.KeyDebounce - 1) & 0xFF
    frame_dispatch(w, rnd)
    if w.EatPause == 0:
        D.clip_entities_on_tunnel_row(w)
