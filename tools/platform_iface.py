"""Stage 67: THE PLATFORM INTERFACE OF THE PORT - the only things the game takes from the outside (tools/iface_map.py: 14 declared inputs, nothing else reaches it) as an abstract class, a scripted implementation for
tests, and the glue that gives them to a port-form World (tools/core_world.py) for one frame of play (tools/core_play.py).
What the game gives to the outside is the World itself: the ordered sound-chip writes (`w.pokey`), the screen cells (`w.maze`, `w.status`), the colour shadows (`w.shadow`) and the sprite state (the entity
variables); the frame result is `Frame`.
Not here, and in the port's hands: the keyboard and console of the key loop (docs/38), the drawing, the collision registers of the hardware (`collisions` is an input the port computes from the sprite pictures: OV-68).
Usage: python -I tools/platform_iface.py   (a short headless run, to see it work)"""
import os
import random
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core_play as PL  # noqa: E402
import core_world as W  # noqa: E402


class Platform:
    """what the outside gives the game: every method is one declared input of docs/45 (section 2)"""

    def stick(self, port):
        """STICK0 / STICK1: bit 0 up, 1 down, 2 left, 3 right, 0 = pressed ($0F = nothing)"""
        return 0x0F

    def trigger(self, port):
        """STRIG0 / STRIG1: 0 = pressed"""
        return 1

    def console(self):
        """CONSOL: bit 0 START, 1 SELECT, 2 OPTION, 0 = pressed ($07 = nothing)"""
        return 7

    def key(self):
        """CH: the last key code ($FF = none, $21 = the space bar)"""
        return 0xFF

    def key_delay(self):
        """KEYDEL: the key debounce delay of the OS (0 = a key is accepted)"""
        return 0

    def clock(self):
        """RTCLOK2: the low byte of the jiffy clock, one more at every frame"""
        raise NotImplementedError

    def attract(self):
        """(DRKMSK, COLRSH): the OS attract-mode mask and shift ($FF, $00 outside attract mode)"""
        return 0xFF, 0x00

    def random(self):
        """POKEY RANDOM: one byte at every read"""
        raise NotImplementedError

    def collisions(self, w):
        """the GTIA collision registers $D000-$D00F as a list of 16 bytes (M2PF = [2], M1PL = [9], M2PL = [10] are the three the game reads): the port computes them from the sprite pictures"""
        return [0] * 16


class GtiaCollisions(Platform):
    """the collision registers computed as the GTIA computes them (tools/gtia_collisions.py, docs/50): `scene` is a function of the World that returns the scene on the screen after the frame - the eight positions
    [HPOSP0-3, HPOSM0-3], the missile page (256 bytes), the four player pages and a gtia_collisions.Playfield (the maze cells and the character set) (core_draw.scene(w, charset) makes it from the port's World: the drawing is in port form, OV-69).
    The registers LATCH every overlap shown since the last HITCLR ($D01E): `run_frame` reads them at the start of the frame (`collisions`), the frame may write HITCLR, and `frame_done` then adds the overlaps of the scene
    the frame left on the screen.  A frame without HITCLR (the death, the eaten-ghost pause) leaves the latch as it was, plus what it showed."""

    def __init__(self, scene):
        self.scene = scene
        self.latch = [0] * 16

    def collisions(self, w):
        return list(self.latch)

    def frame_done(self, w):
        import gtia_collisions as G
        if any(a == 0xD01E for a, v in w.pokey):
            self.latch = [0] * 16
        hpos, missile_page, player_pages, playfield = self.scene(w)
        shown = G.collision_registers(hpos, missile_page, player_pages, playfield)
        self.latch = [a | b for a, b in zip(self.latch, shown)]


class ScriptedPlatform(Platform):
    """deterministic: a seeded stick script, the clock counting frames, a seeded RANDOM, collisions given by a function of the World; counts every call (the closure test of tests/test_iface.py)"""

    def __init__(self, seed=1, sticks=None, collide=None, start_clock=0):
        self.rng = random.Random(seed)
        self.sticks = sticks
        self.collide = collide
        self.t = start_clock
        self.calls = Counter()

    def stick(self, port):
        self.calls["stick"] += 1
        if self.sticks:
            return self.sticks[(self.t + port) % len(self.sticks)]
        return 0x0F

    def clock(self):
        self.calls["clock"] += 1
        return self.t & 0xFF

    def random(self):
        self.calls["random"] += 1
        return self.rng.randrange(256)

    def attract(self):
        self.calls["attract"] += 1
        return 0xFF, 0x00

    def collisions(self, w):
        self.calls["collisions"] += 1
        return self.collide(w) if self.collide else [0] * 16


class RandomFeed:
    """the iterator of RANDOM values the port functions take, fed by the platform"""

    def __init__(self, p):
        self.p = p
        self.n = 0

    def __iter__(self):
        return self

    def __next__(self):
        self.n += 1
        return self.p.random()


class Frame:
    """what one frame gave to the outside"""

    def __init__(self, w, randoms):
        self.pokey = list(w.pokey)            # (register address, value) in the order written
        self.maze = list(w.maze)
        self.status = list(w.status)
        self.colours = list(w.shadow[0xC0:0xC9])      # PCOLR0-3, COLOR0-4
        self.randoms = randoms


def read_inputs(w, p):
    """the inputs of one frame: the stick shadows, the collision registers, the clock and the attract-mode variables are copied into the World"""
    w.stick = [p.stick(0) & 0xFF, p.stick(1) & 0xFF, 0x0F, 0x0F]
    w.collide = [v & 0xFF for v in p.collisions(w)]
    w.RTCLOK2 = p.clock() & 0xFF
    w.DRKMSK, w.COLRSH = p.attract()


def run_frame(w, p):
    """one frame of the running game on a platform: read the inputs, run play_frame, collect what it gave"""
    read_inputs(w, p)
    w.pokey = []
    feed = RandomFeed(p)
    PL.play_frame(w, feed)
    if hasattr(p, "frame_done"):
        p.frame_done(w)
    if hasattr(p, "t"):
        p.t += 1
    return Frame(w, feed.n)


def main():
    import algorithm_models as A
    import check_play as CPL
    import check_sound as CSO
    base = A.started_machine()
    rng = random.Random(5)
    m = A.fresh(base, [0] * 12)
    CSO.sound_setup(m, rng)
    CPL.play_pre(m, rng)
    w = W.World().load(m.mem)
    p = ScriptedPlatform(seed=3, sticks=[0x0F, 0x07, 0x0B, 0x0E, 0x0D])
    for i in range(10):
        f = run_frame(w, p)
        print("frame %d: %d RANDOM, %d sound writes" % (i, f.randoms, len(f.pokey)))
    print(dict(p.calls))


if __name__ == "__main__":
    main()
