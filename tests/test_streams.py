"""Tests for the ROM data formats (step C11). Run:  python -I tests/test_streams.py

The stream decoders in tools/decode_streams.py were written from the code. These tests check them against
facts that do NOT come from the decoders: where the streams must end, how big the RAM images must be, and
what the display lists need.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import decode_streams as S  # noqa: E402


class Streams(unittest.TestCase):
    def test_streams_end_exactly_where_the_next_data_begins(self):
        self.assertEqual(S.decode_b(0xA003)[1], 0xA1E1)   # next stream starts at $A1E1 (pointer set in Start)
        self.assertEqual(S.decode_a(0xA1E1)[1], 0xA386)   # code (Start) begins right after
        self.assertEqual(S.decode_b(0xBE13)[1], 0xBE75)   # 32-byte tail table copied right after

    def test_output_sizes(self):
        self.assertEqual(len(S.decode_b(0xA003)[0]), 101 * 8)       # whole number of 8-byte glyphs
        self.assertEqual(len(S.decode_a(0xA1E1)[0]), 23 * 40)       # 23 mode-4 rows x 40 columns in DisplayList1
        self.assertEqual(len(S.decode_b(0xBE13)[0]) + 32, 0x18C8 - 0x1808)  # $1808..$18A7 then 32 bytes to $18C7
        self.assertEqual(len(S.decode_b(0xBE13)[0]) % 8, 0)

    def test_display_list_row_count_matches_maze_stream(self):
        rom = S.ROM
        a, rows = 0xBFA3, 0
        while True:
            b = rom[a - 0xA000]
            mode = b & 0x0F
            if mode == 1:
                break
            if mode == 4:
                rows += 1
            a += 3 if (b & 0x40) and mode != 0 else 1
        self.assertEqual(rows * 40, len(S.decode_a(0xA1E1)[0]))

    def test_pixel_table_index_63_unused(self):
        for src in (0xA003, 0xBE13):
            a = src
            while S.rd(a) != 0xFF:
                self.assertLess(S.rd(a) & 0x3F, 63)
                a += 1

    def test_pac_shape_pointer_table(self):
        w = lambda a: S.rd(a) | S.rd(a + 1) << 8
        self.assertEqual([w(0xBB65 + 2 * i) for i in range(5)], [0xBAFC, 0xBB06, 0xBB1A, 0xBB2E, 0xBB42])


if __name__ == "__main__":
    unittest.main(verbosity=2)
