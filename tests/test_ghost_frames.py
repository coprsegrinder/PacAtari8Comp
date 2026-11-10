"""Evidence tests for the ghost frames (step C11). Run:  python -I tests/test_ghost_frames.py
Static checks of the frame-selection code and the bitmaps; the live check (47,510 ghost draws, 0 deviations) is in
analysis/evidence-ghost-frames-summary.txt and docs/16-ghost-frames.md.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import analyze_ghost_frames_log as G  # noqa: E402
import decode_streams as S  # noqa: E402

rd = S.rd
at = lambda a, n: bytes(rd(a + i) for i in range(n))
hx = bytes.fromhex
SHAPES = [[rd(0xBAC0 + 0x0A * i + r) for r in range(10)] for i in range(6)]


def holes(sh):
    """Pixels of the background that the body encloses (eyes, mouth): flood-fill the outside, the rest is inside."""
    H, W = len(sh), 8
    grid = [[(sh[r] >> (7 - c)) & 1 for c in range(W)] for r in range(H)]
    seen, stack = set(), [(-1, -1)]
    while stack:
        r, c = stack.pop()
        if (r, c) in seen or r < -1 or r > H or c < -1 or c > W or (0 <= r < H and 0 <= c < W and grid[r][c]):
            continue
        seen.add((r, c))
        stack += [(r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)]
    return [(r, c) for r in range(H) for c in range(W) if not grid[r][c] and (r, c) not in seen]


class FrameSelection(unittest.TestCase):
    def test_code(self):
        # LDY State / BPL / LDA #$28 | TAY / LDA State / ASL / BMI eyes | TYA / LDY LegPhase / BEQ / LDY #$AA ... / LDY #$54 | LDA #$32 / LDY #0 | STY $041C
        self.assertEqual(at(0xB93F, 43), hx("B4CE1002A928A8B5CE0A300D98A4AFF004A0AAD008A054D004A932A0008C1C041869C0853CA90069BA853D"))
        self.assertEqual(at(0xB96A, 14), hx("A009B13C9912048810F8A910853C"))      # copy 10 shape rows to $0412.., then 16 rows from $0410 to player memory
        # direction -> offset (in 10-row shapes): up $00, down $0A, left $14, right $1E (the LDA before each BNE/BEQ to $B93F)
        self.assertEqual([at(a, 2) for a in (0xB90E, 0xB91E, 0xB92C, 0xB93A)], [hx("A900"), hx("A90A"), hx("A914"), hx("A91E")])

    def test_rule_function(self):
        for d, off in ((1, 0x00), (2, 0x0A), (4, 0x14), (8, 0x1E)):
            self.assertEqual(G.expect(0x01, d, 0), (0xBAC0 + off, 0x54))
            self.assertEqual(G.expect(0x08, d, 1), (0xBAC0 + off, 0xAA))
            self.assertEqual(G.expect(0x82, d, 0), (0xBAE8, 0x54))      # frightened overrides the direction
            self.assertEqual(G.expect(0x42, d, 1), (0xBAF2, 0x00))      # eaten overrides everything, no feet

    def test_leg_phase_toggle(self):
        self.assertEqual(at(0xAC05, 19), hx("A514290FD00CA5AFF006A90085AFF002E6AF60"))    # every 16th jiffy: LegPhase 0 <-> 1
        self.assertEqual(at(0xA9A1, 3), hx("2005AC"))                                      # called from the main game step
        self.assertEqual(at(0xAE47, 3), hx("2005AC"))                                      # ... and from the death sequence


class Bitmaps(unittest.TestCase):
    def test_direction_shapes_differ_only_in_the_eyes(self):
        for i in range(1, 4):
            for r in (0, 1, 9):
                self.assertEqual(SHAPES[i][r], SHAPES[0][r])
        for i in range(4):
            self.assertEqual(len(holes(SHAPES[i])), 6)                 # two eyes of three pixels

    def test_eyes_look_where_the_ghost_goes(self):
        def centre(i):
            h = holes(SHAPES[i])
            return sum(r for r, c in h) / len(h), sum(c for r, c in h) / len(h)
        up, down, left, right = (centre(i) for i in range(4))
        self.assertEqual((up[0], up[1]), (3.0, 3.0))                   # rows 2-4
        self.assertEqual((down[0], down[1]), (7.0, 3.0))               # rows 6-8
        self.assertLess(left[1], 3.0)                                  # columns 1 and 3
        self.assertGreater(right[1], 3.0)                              # columns 3 and 5
        self.assertEqual((left[1], right[1]), (2.0, 4.0))
        self.assertLess(up[0], down[0])

    def test_frightened_and_eyes_shapes(self):
        fr = holes(SHAPES[4])
        self.assertEqual(sorted(set(r for r, c in fr)), [3, 4, 5, 7, 8])        # eyes (rows 3-5) and a zigzag mouth (rows 7-8)
        self.assertEqual([(r, c) for r in range(10) for c in range(8) if (SHAPES[5][r] >> (7 - c)) & 1],
                         [(3, 2), (3, 4), (4, 2), (4, 4), (5, 2), (5, 4)])     # two vertical bars
        self.assertEqual(SHAPES[4][:2], SHAPES[0][:2])                         # same head top as the normal ghosts

    def test_feet_rows(self):
        self.assertEqual(0x54, 0b01010100)
        self.assertEqual(0xAA, 0b10101010)
        self.assertEqual(0x54 ^ 0xAA, 0xFE)                                    # complementary patterns: the legs wiggle


class ScreenshotChecker(unittest.TestCase):
    """The pixel check itself needs captures of the running emulator (local, not committed; results in analysis/evidence-ghost-screenshots-summary.txt);
    these tests cover the parts that come from the ROM."""

    def test_eleven_pictures(self):
        import check_ghost_screenshots as K
        self.assertEqual(len(K.PICS), 11)
        self.assertEqual(len({tuple(v) for v in K.PICS.values()}), 11)
        self.assertEqual(K.PICS["Eyes"][10], 0)                                  # no feet row
        self.assertEqual({v[10] for k, v in K.PICS.items() if k != "Eyes"}, {0x54, 0xAA})

    def test_tunnel_clip_seen_in_player_memory(self):
        import check_ghost_screenshots as K
        # a ghost at the right edge of the tunnel was found in its player memory as the frightened picture ANDed with $F8 (feet $54 -> $50)
        self.assertEqual([r & 0xF8 for r in K.PICS["Frightened/feet54"]], [0x38, 0x78, 0xF8, 0xD0, 0xD0, 0xD0, 0xF8, 0xD0, 0xA8, 0xF8, 0x50])
        self.assertIn(0xF8, K.CLIPS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
