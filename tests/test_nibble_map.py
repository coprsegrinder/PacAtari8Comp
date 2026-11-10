"""Evidence tests for the nibble map (RAM $0600-$07D7, ROM $BE95-$BF80). Run:  python -I tests/test_nibble_map.py
Static facts only; the live checks (Altirra traces) are summarised in analysis/evidence-nibble-map-summary.txt.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import decode_streams as S  # noqa: E402

rd = S.rd
NIB, _ = S.split_nibbles(0xBE95)
R = lambda a: NIB[a - 0x600]
at = lambda a, n: bytes(rd(a + i) for i in range(n))
MAZE = S.decode_a(0xA1E1)[0]
YS = [rd(0xBB83 + i) for i in range(10)]
XS = [rd(0xBB8D + i) for i in range(10)]
J = [[R(0x60E + 10 * r + c) for c in range(10)] for r in range(10)]
ROWS = [(y - 36) // 8 for y in YS]
COLS = [(x - 46) // 4 for x in XS]
DIRS = {1: (-1, 0), 2: (1, 0), 4: (0, -1), 8: (0, 1)}
open_ = lambda r, c: 0 <= r < 23 and 0 <= c < 40 and MAZE[r * 40 + c] in (0, 1, 2)


class Layout(unittest.TestCase):
    def test_partition_is_exact(self):
        bounds = [0x600, 0x60E, 0x672, 0x686, 0x6AE, 0x794, 0x7AE, 0x7C6, 0x7CF, 0x7D8]
        sizes = [b - a for a, b in zip(bounds, bounds[1:])]
        self.assertEqual(sizes, [14, 100, 20, 40, 230, 26, 24, 9, 9])
        self.assertEqual(sum(sizes), 472)                       # = 236 bytes = $BE95..$BF80
        self.assertEqual(0xBF80 - 0xBE95 + 1, 236)

    def test_tail_is_displaylist2(self):
        nib = []
        for b in at(0xBF81, 20):
            nib += [b >> 4, b & 15]
        self.assertEqual([R(0x7D8 + i) for i in range(40)], nib)

    def test_start_splits_256_bytes_into_512_nibbles(self):
        self.assertEqual(at(0xA3F6, 4), bytes([0xA9, 0x95, 0x85, 0x3C]))           # SrcPtr = $BE95
        self.assertEqual(at(0xA40A, 3), bytes([0x20, 0xAE, 0xA6]))                 # JSR ReadSrcHighNibble, then WriteDstByte ...
        self.assertEqual(at(0xA418, 3), bytes([0xE8, 0xD0, 0xEF]))                 # INX / BNE: 256 iterations


class Junctions(unittest.TestCase):
    def test_lists_are_exact_lattice_lines(self):
        self.assertEqual(ROWS, [1, 4, 6, 8, 10, 12, 14, 16, 18, 20])
        self.assertEqual(COLS, [3, 6, 9, 13, 18, 21, 26, 30, 33, 36])
        self.assertTrue(all(8 * r + 36 == y for r, y in zip(ROWS, YS)))
        self.assertTrue(all(4 * c + 46 == x for c, x in zip(COLS, XS)))
        self.assertTrue(all(COLS[i] + COLS[9 - i] == 39 for i in range(10)))        # mirror-symmetric maze

    def test_table_is_left_right_mirrored(self):
        swap = {0: 0, 1: 1, 2: 2, 3: 3, 4: 8, 8: 4}
        for r in range(10):
            for c in range(10):
                m = J[r][9 - c]
                mirrored = (m & 3) | (4 if m & 8 else 0) | (8 if m & 4 else 0)
                self.assertEqual(J[r][c], mirrored, (r, c))

    def test_every_nonzero_entry_equals_the_maze_open_neighbour_mask(self):
        def mask(r, c):
            return sum(b for b, (dr, dc) in DIRS.items() if open_(r + dr, c + dc))
        nonzero = 0
        for i in range(10):
            for k in range(10):
                if J[i][k]:
                    nonzero += 1
                    self.assertTrue(open_(ROWS[i], COLS[k]))
                    self.assertEqual(J[i][k], mask(ROWS[i], COLS[k]), (i, k))
        self.assertEqual(nonzero, 90)

    def test_table_contains_every_corner_and_crossing_of_the_maze(self):
        table = {(ROWS[i], COLS[k]) for i in range(10) for k in range(10) if J[i][k]}
        found = 0
        for r in range(23):
            for c in range(40):
                if MAZE[r * 40 + c] in (1, 2):
                    e = sum(b for b, (dr, dc) in DIRS.items() if open_(r + dr, c + dc))
                    if bin(e).count("1") >= 3 or (bin(e).count("1") == 2 and e not in (3, 12)):
                        found += 1
                        self.assertIn((r, c), table)
        self.assertEqual(found, 56)

    def test_the_ten_zero_entries_are_outside_the_corridors(self):
        zeros = [(i, k) for i in range(10) for k in range(10) if J[i][k] == 0]
        self.assertEqual(zeros, [(3, 0), (3, 1), (3, 8), (3, 9), (4, 4), (4, 5), (5, 0), (5, 1), (5, 8), (5, 9)])


class Routes(unittest.TestCase):
    OFFS = [rd(0xBD16 + i) for i in range(16)]

    def walk(self, start, steps):
        r, c = start
        for d in steps:
            if not J[r][c] & d:
                return None
            r, c = r + DIRS[d][0], c + DIRS[d][1]
            if not (0 <= r < 10 and 0 <= c < 10):
                return None
        return (r, c)

    def test_sixteen_patrol_routes_are_closed_loops_from_their_start_positions(self):
        self.assertEqual(self.OFFS[-1] + 29, 230)
        for i in range(16):
            x, y = rd(0xBCEE + 2 * i), rd(0xBCEE + 2 * i + 1)
            start = (YS.index(y), XS.index(x))
            steps, o = [], self.OFFS[i]
            while R(0x6AE + o + len(steps)):
                steps.append(R(0x6AE + o + len(steps)))
            end = o + len(steps)
            if i < 15:
                self.assertEqual(end + 1, self.OFFS[i + 1])                       # each route ends exactly where the next begins
            self.assertEqual(self.walk(start, steps), start, i)

    def test_start_routes(self):
        recs = [(0x686, 13), (0x693, 8), (0x69B, 8), (0x6A3, 11)]
        self.assertEqual(sum(n for _, n in recs), 40)
        for g, (a, n) in enumerate(recs):
            steps = [R(a + i) for i in range(n)]
            self.assertEqual(steps[-1], 0xF)
            valid = [(r, c) for r in range(10) for c in range(10) if J[r][c] and self.walk((r, c), steps[:-1])]
            self.assertTrue(valid, g)
        steps0 = [R(0x686 + i) for i in range(12)]          # ghosts 0 and 3 have exactly one possible start, next to the door
        self.assertEqual([(r, c) for r in range(10) for c in range(10) if J[r][c] and self.walk((r, c), steps0)], [(3, 5)])
        steps3 = [R(0x6A3 + i) for i in range(10)]
        self.assertEqual([(r, c) for r in range(10) for c in range(10) if J[r][c] and self.walk((r, c), steps3)], [(3, 4)])


class SmallTables(unittest.TestCase):
    def test_direction_tables(self):
        self.assertEqual([R(0x7CF + d) for d in (1, 2, 4, 8)], [2, 1, 8, 4])             # reverse direction
        self.assertEqual([R(0x7C6 + d) for d in (1, 2, 4, 8)], [0xD, 0xE, 0x7, 0xB])      # all exits except the reverse one
        self.assertEqual(at(0xB418, 5), bytes([0xB9, 0xCF, 0x07, 0x95, 0x8F]))            # LDA ReverseDir,Y / STA EntityDir,X
        self.assertEqual(at(0xB4E1, 3), bytes([0x39, 0xC6, 0x07]))                         # AND NoReverseMask,Y

    def test_bonus_score_digits(self):
        pairs = [(R(0x794 + 2 * i), R(0x794 + 2 * i + 1)) for i in range(13)]
        self.assertEqual([t * 1000 + h * 100 for t, h in pairs],
                         [100, 300, 500, 500, 700, 700, 1000, 1000, 2000, 2000, 3000, 3000, 5000])
        # the routine clamps Level to 12, doubles it, and adds the pair as thousands and hundreds digits
        self.assertEqual(at(0xA976, 4), bytes([0xC9, 0x0C, 0x90, 0x02]))
        self.assertEqual(at(0xA97E, 3), bytes([0xBD, 0x94, 0x07]))
        self.assertEqual(at(0xA981, 2), bytes([0x85, 0x96]))                               # STA ScoreAdd1000
        self.assertEqual(at(0xA987, 2), bytes([0x85, 0x97]))                               # STA ScoreAdd100

    def test_move_delay_tables(self):
        base_pac = [rd(0xBDB9 + i) for i in range(7)]
        base_ghost = [rd(0xBDC0 + i) for i in range(7)]
        delays = lambda b: [R(0x7AE + b + c) for c in range(4)]
        self.assertEqual(delays(base_ghost[0]), [3, 3, 3, 3])
        self.assertEqual(delays(base_pac[0]), [2, 2, 2, 3])
        self.assertLess(sum(delays(base_pac[0])), sum(delays(base_ghost[0])))              # Pac-Man is faster than the ghosts on level 1
        for lvl in range(6):                                                                 # the tables never slow the game down
            self.assertLessEqual(sum(delays(base_pac[lvl + 1])), sum(delays(base_pac[lvl])))
            self.assertLessEqual(sum(delays(base_ghost[lvl + 1])), sum(delays(base_ghost[lvl])))

    def test_fright_tables(self):
        self.assertEqual(rd(0xBBF8), 0xFF)                                                   # level 1: initial countdown $FF frames
        self.assertEqual([R(0x672 + i) for i in range(20)], [11] * 8 + [7, 11, 11, 7, 7, 7, 11, 7, 1, 7, 1, 1])
        self.assertEqual(at(0xAF74, 5), bytes([0xBD, 0x72, 0x06, 0xC5, 0xFC]))             # LDA FrightenEndPhase,X / CMP FrightenPhase


if __name__ == "__main__":
    unittest.main(verbosity=2)
