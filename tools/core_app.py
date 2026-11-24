"""Stage 78d (docs/51 section 3): THE WHOLE PROGRAM IN PORT FORM - the start-up, the main program (the key loop) and the frame, on the named World of tools/core_world.py; with 78a-78c this is the application layer.
  power_on_world   the RAM the OS leaves before the cartridge runs: zeros, and the few OS-owned values the game reads (docs/37 section 4)
  start            `Start` $A386 up to the first pass of the key loop: the HIGH SCORE text, `$18-$3F` and `$80-$FF` cleared, GameState 1, CopyrightEnd, the maze expanded to $0800, the restart's clear of `$20-$3F`,
                   the chip cleared, the maze copied to the screen and the two saved mazes.  The tables, the character sets and the chip set-up are not World state (the tables are in the C data, the sets are assets, the chip
                   registers are the platform's)
  KeyLoop          the main program `$A4BA-$A572` as a machine with five places: TOP (a pass), READ (the console), DEBOUNCE (waits for the handler to count `$45` to 0), RELEASE (waits for the key to go) and CLOCK_WAIT
                   (the restart waits for the OS clock to move).  The real program is preempted by the vertical-blank handler at any instruction; here it runs after the handler in every frame, to the point where it can only wait
                   for the next frame (a pass that changes nothing, or one of the three waits): the state at the next handler entry is the same unless an input changes in the middle of a frame
  App              one frame: the inputs from the platform, the deferred vertical-blank handler (78c), the main program
`frame_class(w)` is the class the dispatcher will choose (docs/38 section 4), for the story of a game."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core_app_board as AB  # noqa: E402
import core_app_frame as AF  # noqa: E402
import core_app_init as AI  # noqa: E402
import core_sound as SO  # noqa: E402
import core_tables as T  # noqa: E402
import core_world as W  # noqa: E402

COLORS_DLI = 0xBBEE          # ColorsDli: 4 bytes
TEXT_HIGH_SCORE = 0xBDC7     # 10 bytes
TOP, READ, DEBOUNCE, RELEASE, CLOCK_WAIT = "top", "read", "debounce", "release", "clock_wait"
CONSOL_NONE, CONSOL_START, CONSOL_SELECT, CONSOL_OPTION = 7, 6, 5, 3     # the values of CONSOL with the key pressed


# ------------------------------------------------------------------------------------------------ power-on and Start
def power_on_world(clock=0):
    """RAM after the OS's power-on clear, with the OS-owned values the game reads (docs/37 section 4, docs/33): POKMSK, the clock, the stick and trigger shadows, the keyboard shadow, DliColors left by the OS"""
    w = W.World()
    w.POKMSK = 0xC0
    w.RTCLOK2 = clock & 0xFF
    w.DliColors[0], w.DliColors[1] = 0x42, 0x9C
    w.stick = [0x0F] * 4
    w.shadow[0x84] = w.shadow[0x85] = 1                    # STRIG0 / STRIG1: not pressed
    w.shadow[0xFC] = 0xFF                                  # CH: no key
    return w


def maze_stream():
    """the 920 bytes Start expands from the type A stream at $A1E1 (tools/decode_streams.py, checked against the ROM's own expansion by algorithm_models.check_start_expansion)"""
    import decode_streams as S
    return list(S.decode_a(0xA1E1)[0])


def start(w, maze=None):
    """Start $A386 to the first pass of the key loop"""
    for x in range(9, -1, -1):
        w.status[0x0F + x] = T.rom(TEXT_HIGH_SCORE + x)
    AI.clear_zp(w, 0x18, 0x40)
    AI.clear_zp(w, 0x80, 0x100)
    w.GameState = (w.GameState + 1) & 0xFF
    w.CopyrightEnd = (w.RTCLOK2 - 1) & 0xFF
    m = maze if maze is not None else maze_stream()
    w.maze_orig = list(m) + [0] * (0x400 - len(m))          # the tail $0B98-$0BFF is what the OS left: zeros
    w.POKMSK = w.POKMSK | 0x40                              # the keyboard interrupt
    SO.wr(w, 0xD20E, w.POKMSK)                              # IRQEN: the keyboard interrupt on
    SO.wr(w, 0xD20F, 7)                                     # SKCTL
    w.shadow[0x2F] = 0x3E                                   # SDMCTL: the display DMA (the other chip registers Start writes are the platform's)
    _restart_clear(w)


def _restart_clear(w):
    """$A477-$A48A: the restart: `$20-$3F` cleared, the chip cleared, the stored maze to the screen and to both saved mazes"""
    AI.clear_zp(w, 0x20, 0x40)
    SO.clear_pokey(w)
    AI.copy_0800_to_0c00(w)
    AI.copy_0c00_to_1000(w)
    AI.copy_0c00_to_1400(w)


def _restart_tail(w):
    """$A49B-$A4B6 (GameState 0 only, after the wait for the clock): the display list, the priority, the first board, the title scores, the board start"""
    w.shadow[0x30] = 0xA3                                   # SetDisplayList(x = $A3, y = $73)
    w.shadow[0x31] = 0xBF
    w.shadow[0x00] = 0x73
    w.shadow[0x01] = 0xA5
    w.shadow[0x6F] = 0x11                                   # GPRIOR
    AI.init_board(w)
    AI.new_game_init(w)
    if w.TwoPlayers:
        AF.title_clear_scores_2p(w)
    else:
        AF.title_clear_scores_1p(w)
    w.IntroRequest = 2


# ------------------------------------------------------------------------------------------------ the main program
class KeyLoop:
    """where the main program is, between two frames: `pc` one of TOP, READ, DEBOUNCE, RELEASE, CLOCK_WAIT; `acc` the accumulator of the debounce and the release (the OR of the console reads); `clock` the clock the restart waits to change"""

    def __init__(self):
        self.pc = TOP
        self.acc = 0
        self.clock = 0

    def state(self):
        return (self.pc, self.acc if self.pc in (DEBOUNCE, RELEASE) else 0, self.clock if self.pc == CLOCK_WAIT else 0)


def _colours(w):
    for x in range(3, -1, -1):
        w.DliColors[x] = (T.rom(COLORS_DLI + x) ^ w.COLRSH) & w.DRKMSK


def _new_game(w, kl):
    """$A537: START or a trigger"""
    w.CountdownActive = 0
    w.GameState = 0
    w.IntroRequest = 1
    _restart_clear(w)                                       # (the ROM's `lda GameState / bne $A4BA` after the copies only skips the rest for the call from Start, where GameState is 1: `start` above)
    kl.clock = w.RTCLOK2                                    # the wait for the next tick of the OS clock (`$A491-$A495`)
    kl.pc = CLOCK_WAIT


def _set_title(w, kl):
    """$A550: GameState 3 (the title menu), ATRACT 3"""
    w.GameState = 3
    w.ATRACT = 3
    kl.pc = TOP


def _pass(w, kl):
    """one pass from `$A4BA` to the next branch point; sets kl.pc"""
    _colours(w)
    if w.GameState == 0:
        if w.shadow[0xF1] == 0 and w.shadow[0xFC] == 0x21:      # KEYDEL clear and the space bar: pause or resume
            w.Paused = 0 if w.Paused else 1
            w.shadow[0xFC] = 0xFF
        if w.CountdownActive == 0:
            kl.pc = READ
            return
        if w.CountdownTimer == 0:                               # the game-over countdown is over: back to the title
            w.GameState = 4
            w.ATRACT = 4
            kl.pc = TOP
            return
    w.shadow[0xFC] = 0xFF                                       # $A4F5: CH cleared, the triggers start a game
    if w.shadow[0x84] == 0 or w.shadow[0x85] == 0:
        return _new_game(w, kl)
    kl.pc = READ


def _read(w, p, kl, console):
    """$A504: the console; a key starts the debounce"""
    if console == CONSOL_NONE:
        kl.pc = TOP
        return
    w.KeyValue = console
    w.KeyDebounce = 1
    kl.acc = console                                            # `ora CONSOL` once before the first look at the counter
    kl.pc = DEBOUNCE


def _released(w, kl):
    """$A521: the key has been released: what it meant"""
    k = w.KeyValue
    if k == CONSOL_START:
        return _new_game(w, kl)
    if w.GameState < 3:                                         # the copyright screen, and a game in progress: any key leaves it for the title
        return _set_title(w, kl)
    if k == CONSOL_OPTION:                                      # the start level: 0 -> 1 -> 2 -> 4 -> 6 -> 8 -> 10 -> 12 -> 0
        if w.StartLevel < 2:
            w.StartLevel = (w.StartLevel + 1) & 0xFF
        elif w.StartLevel == 0x0C:
            w.StartLevel = 0
        else:
            w.StartLevel = (w.StartLevel + 2) & 0xFF
        return _set_title(w, kl)
    if k == CONSOL_SELECT:                                      # one or two players
        w.TwoPlayers = 0 if w.TwoPlayers else 1
        return _set_title(w, kl)
    kl.pc = TOP


def key_loop(w, p, kl, console=None):
    """the main program for the rest of the frame (after the handler): runs until it can only wait for the next frame"""
    c = (p.console() if console is None else console) & 0xFF
    last = None
    for _ in range(400):
        if kl.pc == CLOCK_WAIT:
            if w.RTCLOK2 == kl.clock:
                return
            _restart_tail(w)
            kl.pc = TOP
        elif kl.pc == DEBOUNCE:
            kl.acc |= c
            if w.KeyDebounce != 0:
                return
            kl.pc = READ if kl.acc != w.KeyValue else RELEASE
        elif kl.pc == RELEASE:
            if c == kl.acc:
                return
            _released(w, kl)
        elif kl.pc == READ:
            _read(w, p, kl, c)
        else:
            cur = (_signature(w), kl.state())
            if cur == last:
                return                                           # a pass that changed nothing: every further pass is the same
            last = cur
            _pass(w, kl)
    raise RuntimeError("the main program did not settle")


def _signature(w):
    """what a pass of the main program can change: the colours, the flags and the shadow bytes it writes"""
    return (tuple(w.DliColors), w.Paused, w.GameState, w.ATRACT, w.StartLevel, w.TwoPlayers, w.CountdownActive, w.IntroRequest, w.KeyValue, w.KeyDebounce, w.shadow[0xFC])


# ------------------------------------------------------------------------------------------------ the frame
def read_inputs(w, p):
    """the inputs of one frame into the World, as the OS and the hardware give them (docs/45): the stick, trigger and keyboard shadows, the collision registers, the clock, the attract values"""
    w.stick = [p.stick(0) & 0xFF, p.stick(1) & 0xFF, 0x0F, 0x0F]
    w.shadow[0x84] = p.trigger(0) & 0xFF
    w.shadow[0x85] = p.trigger(1) & 0xFF
    k = p.key() & 0xFF
    if k != 0xFF:
        w.shadow[0xFC] = k                                      # a key press is stored by the OS in CH
    w.shadow[0xF1] = p.key_delay() & 0xFF
    w.collide = [v & 0xFF for v in p.collisions(w)]
    w.RTCLOK2 = p.clock() & 0xFF
    w.DRKMSK, w.COLRSH = p.attract()


class RandomFeed:
    def __init__(self, p):
        self.p = p
        self.n = 0

    def __iter__(self):
        return self

    def __next__(self):
        self.n += 1
        return self.p.random()


class App:
    """the program on a platform: `frame()` is one frame of the real machine - the OS's vertical blank (the clock), the deferred handler, then the main program for the rest of the frame"""

    def __init__(self, platform, clock=0, maze=None):
        self.p = platform
        self.w = power_on_world(clock)
        self.kl = KeyLoop()
        start(self.w, maze)
        self.frames = 0
        self.randoms = 0

    def frame(self):
        w, p = self.w, self.p
        read_inputs(w, p)
        w.pokey = []
        feed = RandomFeed(p)
        AF.vbi_handler(w, feed)
        self.randoms = feed.n
        key_loop(w, p, self.kl)
        if hasattr(p, "frame_done"):
            p.frame_done(w)
        if hasattr(p, "t"):
            p.t += 1
        self.frames += 1
        return feed.n


# ------------------------------------------------------------------------------------------------ the class of a frame
def frame_class(w):
    """the class (docs/38 section 4) the dispatcher chooses for the state `w`, in the order of the code"""
    gs = w.GameState
    if gs == 1:
        return "copyright setup"
    if gs == 2:
        return "copyright wait"
    if gs == 3:
        return "title menu"
    if gs != 0:
        return "title after game"
    if w.Paused:
        return "paused"
    if w.IntroRequest == 2:
        return "board start"
    if w.CountdownActive:
        return "game-over countdown"
    if w.LevelComplete:
        return "level end"
    if w.PlayStarted == 0:
        return "start tune" if w.StartTuneActive else "start idle"
    if w.WaitState == 1:
        return "turn control"
    if w.WaitState != 0:
        return "ready wait"
    if w.DeathState:
        return "death"
    if w.EatPause:
        return "eaten pause"
    return "play"
