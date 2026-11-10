"""Evidence tests for what the level counter does (step C11). Run:  python -I tests/test_levels.py
Static checks of the code and tables behind docs/14-levels.md; the live sweep (levels 0-50, 99-109, 199-209, 250-255 and the 8-bit wrap)
is summarised in analysis/evidence-levels-summary.txt.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import analyze_levels_log as A  # noqa: E402
import decode_streams as S  # noqa: E402
import disasm6502 as D  # noqa: E402

at = lambda a, n: bytes(S.rd(a + i) for i in range(n))
hx = bytes.fromhex
CODE, _ = D.trace(S.ROM, 0xA000, [0xA386, 0xA6B4, 0xA5FD, 0xA573, 0xA5CE])


class LevelReaders(unittest.TestCase):
    def test_exactly_these_instructions_touch_the_level_counter(self):
        sites = set()
        for a in CODE:
            n, m, mode, op = D.decode(S.ROM, 0xA000, a)
            if op in (0x30, 0x31) and mode in ("zp", "zpx", "abs", "aby") and m not in ("jsr", "jmp"):
                sites.add((a, m))
        self.assertEqual(sorted(sites), [
            (0xA93F, "lda"), (0xA974, "lda"), (0xAC7C, "inc"), (0xACA4, "lda"), (0xADBE, "lda"), (0xADF9, "sta"), (0xADFB, "sta"),
            (0xAE0A, "lda"), (0xAF71, "lda"), (0xB3F7, "lda"), (0xB5A5, "lda"), (0xB662, "lda")])

    def test_clamps(self):
        clamp12 = hx("C90C9002A90C")
        self.assertEqual(at(0xA941, 6), clamp12)        # bonus score glyph record
        self.assertEqual(at(0xA976, 6), clamp12)        # bonus score digits
        self.assertEqual(at(0xB664, 6), clamp12)        # bonus item in the maze
        clamp6 = hx("C9069002A906")
        self.assertEqual(at(0xADC0, 6), clamp6)         # InitBoard: MoveDelay for Pac-Man and the ghosts
        self.assertEqual(at(0xB5A8, 6), clamp6)         # MoveDelayTick
        self.assertEqual(at(0xAE2B, 4), hx("C0039002"))  # SetReleaseTimers: Y clamped to 3

    def test_two_lookups_are_not_clamped(self):
        self.assertEqual(at(0xB3F7, 6), hx("B530AABDF8BB"))   # FrightenFrames[Level]
        self.assertEqual(at(0xAF71, 6), hx("B530AABD7206"))   # FrightenEndPhase[Level]

    def test_level_is_an_eight_bit_counter_incremented_after_the_board_setup(self):
        self.assertEqual(at(0xAC75, 9), hx("2002AEA62BF62CF630"))   # JSR SetupBoard(AE02) / LDX player / INC zp_2C,X / INC Level,X
        self.assertEqual(at(0xADF7, 6), hx("A51B85308531"))   # StartLevel -> Level of both players

    def test_start_levels_reachable_with_option(self):
        seq, v = [], 0
        for _ in range(8):
            seq.append(v)
            v = v + 1 if v < 2 else (0 if v == 12 else v + 2)
        self.assertEqual(seq, [0, 1, 2, 4, 6, 8, 10, 12])


class Tables(unittest.TestCase):
    def test_move_delay_classes(self):
        e = A.expected
        self.assertEqual([e(l)["pac_delays"] for l in (0, 1, 2, 3, 4, 5, 6, 200)],
                         [[2, 2, 2, 3]] * 3 + [[2, 2, 2, 2], [2, 2, 2, 1]] + [[1, 2, 1, 2]] * 3)
        self.assertEqual([e(l)["ghost_delays"] for l in (0, 1, 2, 3, 4, 5, 6, 200)],
                         [[3, 3, 3, 3], [3, 2, 3, 2], [2, 2, 2, 3], [2, 2, 2, 3], [2, 2, 2, 2]] + [[2, 2, 2, 1]] * 3)

    def test_frightened_tables_including_the_overrun(self):
        e = A.expected
        self.assertEqual([e(l)["fright_frames"] for l in range(15)], [255, 192, 128, 64, 0, 192, 0, 0, 0, 192, 0, 0, 0, 64, 0])
        # past the 15-entry table the lookup reads the next ROM bytes (StarShape, popup shapes, ...)
        self.assertEqual([e(l)["fright_frames"] for l in range(15, 24)], [0, 0, 0, 0, 0, 146, 84, 0, 198])
        self.assertEqual([e(l)["fright_end_phase"] for l in range(20)], [11] * 8 + [7, 11, 11, 7, 7, 7, 11, 7, 1, 7, 1, 1])
        # past the 20-entry table it reads the start routes and patrol routes (RAM $0686...)
        self.assertEqual([e(l)["fright_end_phase"] for l in range(20, 29)], [4, 4, 2, 4, 1, 1, 1, 8, 8])
        zero = [l for l in range(256) if e(l)["fright_end_phase"] == 0]
        self.assertEqual(zero, [70, 81, 92, 103, 110, 117, 124, 131, 142, 155, 168, 187, 212, 241])

    def test_bonus_tables(self):
        e = A.expected
        self.assertEqual([e(l)["bonus_score"][0] * 1000 + e(l)["bonus_score"][1] * 100 for l in range(14)],
                         [100, 300, 500, 500, 700, 700, 1000, 1000, 2000, 2000, 3000, 3000, 5000, 5000])
        self.assertEqual([e(l)["bonus_glyph"] for l in range(14)], [0x3A, 0x3C, 0x3E, 0x3E, 0x40, 0x40, 0x42, 0x42, 0x46, 0x46, 0x4A, 0x4A, 0x4C, 0x4C])
        for l in (12, 13, 99, 255):
            self.assertEqual(e(l)["bonus_score"], (5, 0))
            self.assertEqual(e(l)["bonus_glyph"], 0x4C)

    def test_indicator_shape(self):
        ind = A.expected(0)["indicator"]
        self.assertEqual(ind[12:], [0x3A, 0x3B])                       # level 0: one item at the right end
        self.assertTrue(all(v is None for v in ind[:12]))
        i5 = A.expected(5)["indicator"]                                  # level 5: six items
        self.assertEqual(sum(v is not None for v in i5), 12)
        i6 = A.expected(6)["indicator"]                                  # level >= 6: seven items
        self.assertEqual(sum(v is not None for v in i6), 14)
        self.assertEqual(A.expected(18)["indicator"], A.expected(200)["indicator"])   # clamped at 18

    def test_house_release(self):
        self.assertEqual(at(0xBBF2, 6), hx("906030040000"))
        self.assertEqual(A.release_timer_options(1), [(0x04, 0x30, 0x60), (0x30, 0x60, 0x90)])   # board 2 may get either (RTCLOK2)
        self.assertEqual(A.release_timer_options(2), [(0x00, 0x04, 0x30)])
        self.assertEqual(A.release_timer_options(3), [(0x00, 0x00, 0x04)])
        self.assertEqual(A.release_timer_options(77), [(0x00, 0x00, 0x04)])
        # house timers tick every 4th jiffy (Sub_B7A5), active ghost timers every 8th
        self.assertEqual(at(0xA9C5, 9), hx("A5142903D00320A5B7"))
        self.assertEqual(at(0xA9DD, 6), hx("A5142907D006"))
        # level-start choice: Y = Level+1, or Y = 0 on level 0 when RTCLOK2 has bit 7 set
        self.assertEqual(at(0xAE0A, 9), hx("B530A8D00AA5141006"))
        self.assertEqual(at(0xAE19, 3), hx("C8D0F7"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
