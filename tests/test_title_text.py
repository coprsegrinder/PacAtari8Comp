"""Evidence tests for TextCopyright ($BDF7) and LevelIconCodes ($BE05). Run:  python -I tests/test_title_text.py
Screen evidence (kept locally in analysis/*.png, not committed) is described in docs/12-data-formats.md.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import decode_streams as S  # noqa: E402

rd = S.rd
at = lambda a, n: bytes(rd(a + i) for i in range(n))


class Copyright(unittest.TestCase):
    def test_copy_destination_is_row18_mode6(self):
        # LDX #$0D / LDA $BDF7,X / STA $1D57,X / DEX / BPL
        self.assertEqual(at(0xA6EC, 10), bytes([0xA2, 0x0D, 0xBD, 0xF7, 0xBD, 0x9D, 0x57, 0x1D, 0xCA, 0x10]))

    def test_mode6_decoding_reads_copyright(self):
        codes = at(0xBDF7, 14)
        text = "".join(chr((b & 0x3F) + 0x20) for b in codes)
        self.assertEqual(text, "(C) ATARI 1982")
        self.assertTrue(all((b >> 6) == 3 for b in codes if (b & 0x3F) != 0 or b))   # colour register 3 throughout

    def test_title_text_lines_decode(self):
        dec = lambda a, n: "".join(chr((b & 0x3F) + 0x20) for b in at(a, n))
        self.assertEqual(dec(0xBDD6, 17), "CHANGE DIFFICULTY")
        self.assertEqual(dec(0xBDE7, 16), "PRESS START TO  ")
        self.assertEqual(dec(0xBFC6, 11), "PLAYER GAME")
        self.assertEqual(dec(0xBFD1, 16), "PRESS SELECT FOR")
        self.assertEqual(dec(0xBFE1, 16), "PRESS OPTION TO ")
        self.assertEqual(dec(0xBFF1, 9), "PLAY GAME")


class LevelIcons(unittest.TestCase):
    def test_option_key_cycles_start_level(self):
        # CONSOL value $03 (OPTION pressed) branches to LA559
        self.assertEqual(at(0xA52D, 4), bytes([0xC9, 0x03, 0xF0, 0x28]))
        # LA559: if StartLevel < 2: INC; elif == $0C: 0 else +2
        self.assertEqual(at(0xA559, 22), bytes.fromhex("A51BC902B004E61BD0EDC90CF006E61BE61BD0E3A900"))
        seq, v = [], 0
        for _ in range(9):
            seq.append(v)
            v = v + 1 if v < 2 else (0 if v == 12 else v + 2)
        self.assertEqual(seq, [0, 1, 2, 4, 6, 8, 10, 12, 0])

    def test_start_level_becomes_the_level_counter(self):
        # Sub_ADF1: LDA $1B / STA $30 / STA $31
        self.assertEqual(at(0xADF7, 6), bytes([0xA5, 0x1B, 0x85, 0x30, 0x85, 0x31]))

    def test_icon_table_and_use(self):
        # LDX $1B / LDA $BE05,X / STA $1CC6 / CLC / ADC #1 / STA $1CC7
        self.assertEqual(at(0xA767, 12), bytes([0xA6, 0x1B, 0xBD, 0x05, 0xBE, 0x8D, 0xC6, 0x1C, 0x18, 0x69, 0x01, 0x8D]))
        tab = list(at(0xBE05, 14))
        self.assertEqual(tab, [0x3A, 0x3C, 0x3E, 0x3E, 0x40, 0x40, 0x44, 0x44, 0x48, 0x48, 0x4A, 0x4A, 0x4C, 0x4C])
        reachable = [tab[i] for i in (0, 1, 2, 4, 6, 8, 10, 12)]
        self.assertEqual(len(set(reachable)), 8)            # eight different icons
        self.assertEqual(tab[2], tab[3])                    # the screen showed identical icons for 2 and 3
        self.assertEqual(tab[12], tab[13])                  # ... and for 12 and 13
        cs = S.decode_b(0xA003)[0]
        for c in tab:                                       # both glyphs of every icon exist in the 101-glyph charset and are not blank
            self.assertLess(c + 1, len(cs) // 8)
            self.assertTrue(any(cs[c * 8:c * 8 + 8]) and any(cs[(c + 1) * 8:(c + 1) * 8 + 8]))

    def test_icon_row_uses_the_game_charset(self):
        # DliChbaseTable entry 2 = $30 applies to the band that contains row 11 (DLI on row 10)
        self.assertEqual(at(0xBDD1, 5), bytes([0x18, 0xE0, 0x30, 0xE0, 0x30]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
