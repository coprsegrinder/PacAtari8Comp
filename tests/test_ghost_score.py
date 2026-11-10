"""Evidence test: the four pop-up shapes are the ghost-eaten scores 200/400/800/1600 (step C11).
Run:  python -I tests/test_ghost_score.py

Chain proven here, all from ROM bytes:
  1. Power pellet ($B3DE): adds 50 (ScoreAdd10 = 5, JSR AddToScore), sets GhostsEaten ($E9) = $FF.
  2. Eating a frightened ghost ($A886): INC GhostsEaten, so the first ghost gives index 0.
  3. The same index selects the pop-up shape (GhostScorePtrs) and the amount added to the score:
     0 -> 200, 1 -> 400, 2 -> 800, 3 -> 1600.
  4. The shapes, drawn side by side with the shared '00' shape, read as those numbers.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import decode_streams as S  # noqa: E402  (provides ROM and rd)

rd = S.rd


def bytes_at(addr, n):
    return bytes(rd(addr + i) for i in range(n))


class GhostScore(unittest.TestCase):
    def test_power_pellet_adds_50_and_resets_counter(self):
        # LDA #$05 / STA $98 / JSR $B423   and   LDA #$FF / STA $E9
        self.assertEqual(bytes_at(0xB3E6, 7), bytes([0xA9, 0x05, 0x85, 0x98, 0x20, 0x23, 0xB4]))
        self.assertEqual(bytes_at(0xB3F1, 4), bytes([0xA9, 0xFF, 0x85, 0xE9]))

    def test_eating_a_frightened_ghost_increments_counter(self):
        self.assertEqual(bytes_at(0xA87F, 6), bytes([0xB5, 0xCE, 0x30, 0x03, 0x4C, 0x23]))  # LDA $CE,X / BMI $A886 / JMP $A923
        self.assertEqual(bytes_at(0xA88C, 2), bytes([0xE6, 0xE9]))                          # INC $E9

    def test_amount_added_matches_index(self):
        # index 0 -> $97=2, 1 -> 4, 2 -> 8, else $96=1 and $97=6   (digits of 200/400/800/1600)
        code = bytes_at(0xA900, 0x23)
        self.assertEqual(code[0:6], bytes([0xA5, 0xE9, 0xD0, 0x04, 0xA9, 0x02]))
        self.assertEqual(code[8:14], bytes([0xC9, 0x01, 0xD0, 0x04, 0xA9, 0x04]))
        self.assertEqual(code[16:22], bytes([0xC9, 0x02, 0xD0, 0x04, 0xA9, 0x08]))
        self.assertEqual(code[24:30], bytes([0xA9, 0x01, 0x85, 0x96, 0xA9, 0x06]))
        self.assertEqual(code[30:35], bytes([0x85, 0x97, 0x4C, 0x23, 0xB4]))                # STA $97 / JMP AddToScore

    def test_score_adder_uses_digits_94_to_99(self):
        self.assertEqual(bytes_at(0xB432, 2), bytes([0xA0, 0x05]))                          # LDY #5
        self.assertEqual(bytes_at(0xB43A, 5), bytes([0x65, 0x9A, 0x79, 0x94, 0x00]))        # ADC $9A / ADC $0094,Y
        self.assertEqual(bytes_at(0xB427, 1), bytes([0xF8]))                                # SED

    def test_shapes_read_as_the_numbers(self):
        zeros = [rd(0xBC13 + i) for i in range(16)]
        art = {0xBC1F: ["..###...##...##.", ".#...#.#..#.#..#", ".....#.#..#.#..#", "...##..#..#.#..#",
                        "..#....#..#.#..#", ".#.....#..#.#..#", ".#####..##...##."],
               0xBC2B: ["....#...##...##.", "...##..#..#.#..#", "..#.#..#..#.#..#", ".#..#..#..#.#..#",
                        ".#####.#..#.#..#", "....#..#..#.#..#", "....#...##...##."],
               0xBC37: ["..###...##...##.", ".#...#.#..#.#..#", ".#...#.#..#.#..#", "..###..#..#.#..#",
                        ".#...#.#..#.#..#", ".#...#.#..#.#..#", "..###...##...##."],
               0xBC43: ["#...##..##...##.", "#..#...#..#.#..#", "#.#....#..#.#..#", "#.###..#..#.#..#",
                        "#.#..#.#..#.#..#", "#.#..#.#..#.#..#", "#..##...##...##."]}
        for ptr, rows in art.items():
            got = []
            for r in range(4, 11):
                b, z = rd(ptr + r), zeros[r]
                got.append("".join("#" if b & (0x80 >> k) else "." for k in range(8)) +
                           "".join("#" if z & (0x80 >> k) else "." for k in range(8)))
            self.assertEqual(got, rows, hex(ptr))

    def test_pointer_table_order(self):
        w = lambda a: rd(a) | rd(a + 1) << 8
        self.assertEqual([w(0xBCD0 + 2 * i) for i in range(4)], [0xBC1F, 0xBC2B, 0xBC37, 0xBC43])


if __name__ == "__main__":
    unittest.main(verbosity=2)
