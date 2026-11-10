"""Evidence tests for PacMouthOffsets / DeathPlotBytes ($BB55-$BB64) and the unread bytes $A000-$A002.
Run:  python -I tests/test_bb56_a000.py
Everything here is checked from ROM bytes; the dynamic results (Altirra) are recorded in docs/12-data-formats.md.
"""
import os
import sys
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), "tools")
sys.path.insert(0, TOOLS)
import decode_streams as S  # noqa: E402
import disasm6502 as D  # noqa: E402

rd = S.rd
at = lambda a, n: bytes(rd(a + i) for i in range(n))
OS = open(os.path.join(os.path.dirname(HERE), "original", "Atari OS Rev B (19xx)(Atari)(NTSC)[400-800].rom"), "rb").read()
CODE, _ = D.trace(S.ROM, 0xA000, [0xA386, 0xA6B4, 0xA5FD, 0xA573, 0xA5CE])


class Chomp(unittest.TestCase):
    def test_table_and_users(self):
        self.assertEqual(at(0xBB55, 3), bytes([0x00, 0x0A, 0x00]))
        self.assertEqual(at(0xB2DB, 8), bytes([0xCA, 0xBD, 0x55, 0xBB, 0xE0, 0x02, 0xD0, 0x04]))  # DEX / LDA $BB55,X / CPX #2 / BNE
        self.assertEqual(at(0xB2E3, 4), bytes([0xA2, 0xFF, 0x86, 0xAB]))                         # wrap: ChompPhase = $FF, then INC -> 0
        self.assertEqual(at(0xB2D3, 8), bytes([0xA6, 0xAB, 0xD0, 0x04, 0xE6, 0xAB, 0xD0, 0xF3]))  # phase 0 -> full circle (LB2CE: Y=0, A=0)
        self.assertEqual(at(0xB2CE, 4), bytes([0xA0, 0x00, 0x98, 0xF0]))

    def test_direction_codes_match_joystick_and_shapes(self):
        # LDA STICK0,X / EOR #$0F : bits 1=up 2=down 4=left 8=right
        self.assertEqual(at(0xB1A1, 5), bytes([0xBD, 0x78, 0x02, 0x49, 0x0F]))
        # handlers pick pointer index Y: up 6 (Up1), down 8 (Down1), left 4 (Left1), right 2 (Right1)
        self.assertEqual(at(0xB20C, 2), bytes([0xA0, 0x06]))     # up handler  (after DEC PacY)
        self.assertEqual(at(0xB23A, 2), bytes([0xA0, 0x08]))     # down handler (after INC PacY)
        self.assertEqual(at(0xB26D, 2), bytes([0xA0, 0x02]))     # right handler (after INC PacX)
        self.assertEqual(at(0xB2A6, 2), bytes([0xA0, 0x04]))     # left handler  (after DEC PacX)
        self.assertEqual(at(0xB1E7, 4), bytes([0xC6, 0x89, 0xC6, 0x89]))   # up: DEC PacY twice
        self.assertEqual(at(0xB215, 4), bytes([0xE6, 0x89, 0xE6, 0x89]))   # down: INC PacY twice
        self.assertEqual(at(0xB251, 2), bytes([0xE6, 0x8E]))                # right: INC PacX
        self.assertEqual(at(0xB283, 2), bytes([0xC6, 0x8E]))                # left: DEC PacX
        w = lambda a: rd(a) | rd(a + 1) << 8
        names = {w(0xBB65 + 2 * i): n for i, n in enumerate(["full", "right", "left", "up", "down"])}
        # the shape at each target really has its mouth on that side (rows of the first frame)
        row = lambda a, r: rd(a + r)
        self.assertEqual(row(0xBB06, 4) & 0x03, 0)   # right: low (right-hand) pixels of the middle rows are empty
        self.assertEqual(row(0xBB1A, 4) & 0xC0, 0)   # left: high (left-hand) pixels are empty
        self.assertEqual(row(0xBB2E, 0), 0x00)       # up: top row empty (notch at the top)
        self.assertEqual(row(0xBB42, 9), 0x00)       # down: bottom row empty
        self.assertEqual(names[0xBB2E], "up")


class Death(unittest.TestCase):
    def test_trigger_and_state_machine(self):
        self.assertEqual(at(0xA923, 8), bytes([0xA5, 0xAA, 0x09, 0x80, 0x85, 0xAA, 0x20, 0xE6]))  # non-frightened ghost: LDA $AA / ORA #$80 ...
        self.assertEqual(at(0xA92C, 6), bytes([0xA9, 0x01, 0x85, 0xAE, 0x85, 0xED]))               # DeathState = 1
        self.assertEqual(at(0xA82F, 10), bytes([0xA5, 0xED, 0xF0, 0x06, 0x20, 0x3D, 0xAE, 0x4C, 0xF7, 0xAE]))  # if DeathState: DeathSequence, DeathAnimation
        self.assertEqual(at(0xAE76, 8), bytes([0xE6, 0xEA, 0xA9, 0x07, 0x85, 0xEC, 0xA9, 0x03]))   # DeathAnimActive++, delay 7, state 3
        self.assertEqual(at(0xAF4C, 8), bytes([0x91, 0x3E, 0x88, 0x10, 0xFB, 0x85, 0xEA, 0x60]))   # end: clear 16 rows, DeathAnimActive = 0

    def test_plot_step_and_star(self):
        self.assertEqual(at(0xAF1F, 11), bytes([0xAA, 0xCA, 0xBD, 0x00, 0x06, 0xA8, 0x88, 0xBD, 0x57, 0xBB, 0x91]))
        self.assertEqual(at(0xAF3A, 6), bytes([0xA0, 0x0F, 0xA2, 0x0F, 0xBD, 0x07]))               # frame 15: 16 rows of StarShape

    def test_simulated_frames_collapse_the_shape(self):
        nib, _ = S.split_nibbles(0xBE95)
        up2 = [rd(0xBB38 + i) for i in range(10)]
        buf = [0] * 16
        for x in range(9, -1, -1):
            buf[0x0C - (9 - x)] = up2[x]
        start_ink = sum(bin(b).count("1") for b in buf)
        for x in range(14):
            buf[nib[x] - 1] = rd(0xBB57 + x)
        end_ink = sum(bin(b).count("1") for b in buf)
        self.assertLess(end_ink, start_ink)          # the shape loses pixels
        self.assertEqual(buf[3:7], [0, 0, 0, 0])     # top rows are gone, as in the render


class UnreadBytes(unittest.TestCase):
    def test_no_cartridge_operand_reaches_a000_a002(self):
        for a in CODE:
            n, m, mode, op = D.decode(S.ROM, 0xA000, a)
            if mode in ("abs", "abx", "aby", "ind") and m not in ("jsr", "jmp"):
                self.assertFalse(0x9F01 <= op <= 0xA002, "%04X %s %04X" % (a, m, op))
            if m in ("jsr", "jmp"):
                self.assertFalse(0xA000 <= op <= 0xA002)

    def test_only_one_pointer_is_loaded_with_a0_high_byte(self):
        # $A0 as an immediate feeds SrcPtrH only at $A41F (lo byte $03); the other uses go to zp_AD, which is never a pointer
        feeds = []
        for a in sorted(CODE):
            n, m, mode, op = D.decode(S.ROM, 0xA000, a)
            if mode == "imm" and op == 0xA0 and m == "lda":
                nx = D.decode(S.ROM, 0xA000, a + n)
                feeds.append((a, nx[3]))
        self.assertEqual(feeds, [(0xA41F, 0x3D), (0xAFAD, 0xAD), (0xBABB, 0xAD)])
        self.assertEqual(at(0xA41B, 6), bytes([0xA9, 0x03, 0x85, 0x3C, 0xA9, 0xA0]))  # SrcPtr = $A003

    def test_os_ram_size_test_reads_only_the_first_byte_of_the_page(self):
        o = lambda a, n: bytes(OS[a - 0xD800 + i] for i in range(n))
        # LDY #0 / STY $05 / LDA #$10 / STA $06 / LDA ($05),Y / EOR #$FF / STA ($05),Y / CMP ($05),Y / BNE ... / ADC #$10
        self.assertEqual(o(0xF257, 0x1F), bytes.fromhex("A00084 05A9108506B10549FF9105D105D00D49FF9105A506 18691085 06D0E9".replace(" ", "")))

    def test_decoder_matches_altirra_ram(self):
        # CRC-32 of RAM $3000-$3327 read from Altirra after boot (all five ROM variants): $5E84E650
        self.assertEqual(zlib.crc32(S.decode_b(0xA003)[0]), 0x5E84E650)


if __name__ == "__main__":
    unittest.main(verbosity=2)
