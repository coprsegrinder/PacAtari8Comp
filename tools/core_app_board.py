"""Stage 78b (docs/51 section 3): THE BOARD, THE TURN, THE END OF A LEVEL, THE READY! INTRO AND THE LABELS IN PORT FORM, on the named World of tools/core_world.py - the second part of the application layer.  Each function is
the logic of one ROM routine (named in its docstring); tools/check_app_board.py runs each against the routine on the concrete 6502 from random states (the whole zero page except the `$A5` temporary, the maze and its
copies, the status rows, the shadows, the player-missile pages, the positions, the picture buffers and the ordered chip writes compared).
  AdvanceLevel $AC75        a new board for the next level: the maze, a life back, the level counter, the level indicator, the READY! screen, the wait
  level_end_step $AC18      the level-end sequence the frame dispatcher calls while LevelComplete is set: the stop, the flashing, the new board (steps 0-3, then AdvanceLevel)
  TurnControl $AA2D         what happens when a life is lost or a board is cleared: the hand-over between two players (the maze swap), the next board, the end of the game and its countdown
  DrawLevelIndicator $AC93  the row of bonus items of the levels played (the cells $0DEF-$0DF8 and the item row), the colour of the item
  DrawReadyScreen $AD0E     the four ghosts and Pac-Man where they stand, one life used, the life icons
  ClearReadyText $AD5E, BlinkPlayerLabel $AD69, DrawLabel2UP $AD87, DrawLabel1UP $AD9F, CompareHighScore $AB26
The game-over countdown is started by TurnControl (CountdownActive, CountdownTimer); its decrement and the 1UP / 2UP labels it shows are in the frame dispatcher (stage 78c)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core_app_init as AI  # noqa: E402
import core_draw as D  # noqa: E402
import core_play as PL  # noqa: E402
import core_score as S  # noqa: E402
import core_sound as SO  # noqa: E402
import core_tables as T  # noqa: E402

COLPF3 = 0xD019
BONUS_ITEM_CODES = 0xBD26      # BonusItemCodes: 13 bytes, the first glyph of each level's bonus item


# ------------------------------------------------------------------------------------------------ the labels and the READY! text
def draw_label_1up(w):
    """DrawLabel1UP $AD9F: the text 1UP in the status row"""
    w.status[4], w.status[5], w.status[6] = 0x11, 0x35, 0x30


def draw_label_2up(w):
    """DrawLabel2UP $AD87: the text 2UP in the status row"""
    w.status[0x21], w.status[0x22], w.status[0x23] = 0x12, 0x35, 0x30


def blink_player_label(w):
    """BlinkPlayerLabel $AD69: every 16th jiffy the label of the player on turn is shown or blanked"""
    if w.RTCLOK2 & 0x0F:
        return
    w.LabelBlink = 1 if w.LabelBlink == 0 else 0
    if w.CurrentPlayer == 0:
        if w.LabelBlink:
            draw_label_1up(w)
        else:
            w.status[4] = w.status[5] = w.status[6] = 0
    else:
        if w.LabelBlink:
            draw_label_2up(w)
        else:
            w.status[0x21] = w.status[0x22] = w.status[0x23] = 0


def clear_ready_text(w):
    """ClearReadyText $AD5E: the 14 cells of the READY! text ($0DED-$0DFA)"""
    for x in range(0x0D, -1, -1):
        w.maze[0x1ED + x] = 0


def draw_ready_screen(w):
    """DrawReadyScreen $AD0E: the ghosts and Pac-Man drawn where they stand, one life used for this board, the life icons"""
    D.draw_all_in_place(w)
    w.Lives[w.CurrentPlayer] = (w.Lives[w.CurrentPlayer] - 1) & 0xFF
    S.draw_lives(w)


def compare_high_score(w, x):
    """CompareHighScore $AB26: the six digit cells of the score at status[x] against the high score at status[$39]: the first digit that differs decides, and a higher score is copied over the high score from there on"""
    for y in range(6):
        a, b = w.status[x + y], w.status[0x39 + y]
        if a == b:
            continue
        if a < b:
            return
        for k in range(y, 6):
            w.status[0x39 + k] = w.status[x + k]
        return


# ------------------------------------------------------------------------------------------------ the level indicator
def draw_level_indicator(w):
    """DrawLevelIndicator $AC93: ten cells of the item row, the item colour, and the bonus items of the levels played: up to six items from the right while the level is below 6, seven from the table above"""
    a = 0xA2
    for x in range(10):
        w.maze[0x1EF + x] = a
        a = (a + 1) & 0xFF
    lv = w.Level[w.CurrentPlayer]
    w.ItemColor = 0xDA if 6 <= lv < 10 else 0x44
    if lv < 6:
        w.Scratch2A = lv
        w.DstPtr[0], w.DstPtr[1] = 0x92, 0x0F
        x = 0
        while True:
            a = T.rom(BONUS_ITEM_CODES + x)
            ptr = w.DstPtr[0] | w.DstPtr[1] << 8
            w.maze[ptr - 0x0C00] = a
            w.DstPtr[0] = (w.DstPtr[0] + 1) & 0xFF
            ptr = w.DstPtr[0] | w.DstPtr[1] << 8
            w.maze[ptr - 0x0C00] = (a + 1) & 0xFF
            if x == w.Scratch2A:
                return
            x += 1
            w.DstPtr[0] = (w.DstPtr[0] - 3) & 0xFF
            assert w.DstPtr[0] != 0                                     # the code would fall into the other branch: not a state of the game
    a = min(lv, 0x12) - 6
    w.Scratch2A = a
    src = 0xBD3E - a
    w.SrcPtr[0], w.SrcPtr[1] = src & 0xFF, src >> 8
    x = 0
    for y in range(7):
        c = T.rom(src + y)
        w.maze[0x386 + x] = c
        w.maze[0x387 + x] = (c + 1) & 0xFF
        x += 2


# ------------------------------------------------------------------------------------------------ the next level and the level end
def advance_level(w):
    """AdvanceLevel $AC75: the new board of the next level"""
    AI.new_board_init(w)
    p = w.CurrentPlayer
    w.Lives[p] = (w.Lives[p] + 1) & 0xFF
    w.Level[p] = (w.Level[p] + 1) & 0xFF
    draw_level_indicator(w)
    draw_ready_screen(w)
    w.LevelComplete = 0
    w.LevelEndStep = 0
    w.WaitState = 2
    w.WaitTimer = 0x40


def level_end_step(w):
    """the level-end sequence `$AC18` (the frame dispatcher jumps to it while LevelComplete is set): step 0 stops the sound and draws everything where it stands, 1 waits 64 frames then hides the ghosts and starts the
    flashing, 2 flashes the maze colour 6 times every 16 frames, 3 initialises the board; later steps are AdvanceLevel"""
    s = w.LevelEndStep
    if s == 0:
        SO.clear_pokey(w)
        D.draw_all_in_place(w)
        w.LevelEndDelay = 0x40
        w.LevelEndStep = (w.LevelEndStep + 1) & 0xFF
        return
    if s == 1:
        if w.LevelEndDelay:
            w.LevelEndDelay = (w.LevelEndDelay - 1) & 0xFF
            return
        for x in (3, 2, 1, 0):
            w.hpos[x] = 0                                               # the ghosts leave the screen
        w.shadow[0xC4] = 0x0C                                           # COLOR0
        w.LevelEndFlashes = 7
        w.LevelEndDelay = 0x10
        w.LevelEndStep = (w.LevelEndStep + 1) & 0xFF
        return
    if s == 2:
        if w.LevelEndDelay:
            w.LevelEndDelay = (w.LevelEndDelay - 1) & 0xFF
            return
        w.LevelEndFlashes = (w.LevelEndFlashes - 1) & 0xFF
        if w.LevelEndFlashes == 0:
            w.LevelEndStep = (w.LevelEndStep + 1) & 0xFF
            return
        w.shadow[0xC4] = 0x0C if w.LevelEndFlashes & 1 else 0x86
        w.LevelEndDelay = 0x10
        return
    if s == 3:
        AI.init_board(w)
        w.LevelEndStep = (w.LevelEndStep + 1) & 0xFF
        return
    advance_level(w)


# ------------------------------------------------------------------------------------------------ the turn
def turn_control(w):
    """TurnControl $AA2D: a life was lost or a board cleared.  TurnSwitchState is the stage of a hand-over between two players (1: player 2 -> 1, 2: player 1 -> 2, 3 and 4 the stages after the swap) and is 0
    otherwise; with a stage in progress the routine waits (WaitTimer), swaps the mazes and the labels, and at the end falls into the common ending below; with none it decides: hand over (and start the wait), go on
    with the same player (InitBoard, the indicator, READY!), or end the game (GAME OVER text, high score, the countdown)"""
    PL.show_power_pellets(w)
    if w.TurnSwitchState != 0:
        if w.WaitTimer != 0:
            w.WaitTimer = (w.WaitTimer - 1) & 0xFF
            return
        st = w.TurnSwitchState
        if st == 1:
            w.maze = list(w.saved1)
            draw_label_2up(w)
            w.CurrentPlayer = 0
            w.TurnSwitchState = 3
            return
        if st == 2:
            w.maze = list(w.saved2)
            draw_label_1up(w)
            w.CurrentPlayer = 1
            w.TurnSwitchState = 3
            return
        PL.show_power_pellets(w)
        w.TurnSwitchState = 0
    else:
        if w.TwoPlayers:
            if w.CurrentPlayer == 0:
                if w.Lives[1] != 0:
                    if w.Lives[0] == 0:
                        w.TurnSwitchState = 2
                        w.WaitTimer = 0x30
                        return _game_over_text(w)
                    AI.copy_0c00_to_1000(w)
                    w.WaitTimer = 0x30
                    w.TurnSwitchState = 2
                    return
            else:
                if w.Lives[0] != 0:
                    if w.Lives[1] == 0:
                        w.TurnSwitchState = 1
                        w.WaitTimer = 0x30
                        return _game_over_text(w)
                    AI.copy_0c00_to_1400(w)
                    w.WaitTimer = 0x30
                    w.TurnSwitchState = 1
                    return
    p = w.CurrentPlayer
    if w.Lives[p] != 0:
        AI.init_board(w)
        draw_level_indicator(w)
        return draw_ready_screen(w)
    return _game_over_text(w)


def _game_over_text(w):
    """$AAEF: the GAME OVER text (the 14 cells from $AC), its colour; when no hand-over is in progress the high score is updated and the countdown starts"""
    for x in range(0x0E):
        w.maze[0x1ED + x] = (0xAC + x) & 0xFF
    w.shadow[0xC7] = 0x44                                               # COLOR3
    SO.wr(w, COLPF3, 0x44)
    if w.TurnSwitchState != 0:
        return
    compare_high_score(w, 0x2A)
    compare_high_score(w, 0x47)
    w.WaitState = 0
    w.CountdownActive = 1
    w.CountdownTimer = 0xE2
    draw_label_1up(w)
    PL.show_power_pellets(w)
