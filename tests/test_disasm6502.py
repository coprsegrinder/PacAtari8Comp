"""Tests for tools/disasm6502.py (Step C8).  Run:  python -I tests/test_disasm6502.py

The key test is independent of the disassembler's own opcode table: every official opcode is
decoded, printed in ca65 syntax, reassembled with the real ca65/ld65, and the bytes compared.
"""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import disasm6502 as D  # noqa: E402

BIN = os.environ.get("CC65_BIN", r"F:\Ports\Pac-Man-tools\cc65\bin")


class Basics(unittest.TestCase):
    def test_table_complete(self):
        self.assertEqual(len(D.OPCODES), 151)

    def test_known(self):
        self.assertEqual(D.decode(bytes([0xA9, 0x42]), 0, 0), (2, "lda", "imm", 0x42))
        self.assertEqual(D.decode(bytes([0x4C, 0x86, 0xA3]), 0, 0), (3, "jmp", "abs", 0xA386))
        self.assertEqual(D.decode(bytes([0xD0, 0xFE]), 0x1000, 0x1000), (2, "bne", "rel", 0x1000))
        self.assertEqual(D.decode(bytes([0xF0, 0x7F]), 0x1000, 0x1000)[3], 0x1081)
        self.assertEqual(D.decode(bytes([0xF0, 0x80]), 0x1000, 0x1000)[3], 0x0F82)

    def test_illegal_and_truncated(self):
        self.assertIsNone(D.decode(bytes([0x02]), 0, 0))      # illegal opcode
        self.assertIsNone(D.decode(bytes([0xAD, 0x00]), 0, 0))  # truncated operand

    def test_trace_stops(self):
        # LDA #1 ; BNE +1 ; RTS ; NOP ; RTS     (the NOP after the first RTS is reached via the branch)
        data = bytes([0xA9, 1, 0xD0, 1, 0x60, 0xEA, 0x60])
        code, targets = D.trace(data, 0x2000, [0x2000])
        self.assertEqual(sorted(code), [0x2000, 0x2002, 0x2004, 0x2005, 0x2006])
        self.assertEqual(targets, {0x2005})


@unittest.skipUnless(os.path.exists(os.path.join(BIN, "ca65.exe")), "ca65 not installed")
class RoundTrip(unittest.TestCase):
    def test_all_opcodes_reassemble_identically(self):
        blob, pcs = bytearray(), []
        for op in sorted(D.OPCODES):
            mnem, mode = D.OPCODES[op]
            for operand in ([0x34, 0x12], [0x10, 0x00], [0xFE, 0xFF]):   # normal, high byte 0, high values (not $xxFF: ca65 rejects jmp ($xxFF))
                raw = bytes([op] + operand[:D.SIZE[mode]])
                pcs.append((len(blob), raw))
                blob += raw
        data, lines = bytes(blob), []
        for off, raw in pcs:
            n, mnem, mode, op = D.decode(data, 0xA000, 0xA000 + off)
            self.assertEqual(raw, data[off:off + n])
            pc = 0xA000 + off
            # ca65 rejects a bare absolute branch target in a relocatable segment, so write it as *+n
            rel = (lambda t, pc=pc: "*%+d" % (t - pc)) if mode == "rel" else None
            lines.append("        " + D.instr_text(mnem, mode, op, rel))
        with tempfile.TemporaryDirectory() as tmp:
            src, obj, out = (os.path.join(tmp, n) for n in ("t.s", "t.o", "t.bin"))
            open(src, "w").write('.segment "CODE"\n' + "\n".join(lines) + "\n")
            subprocess.run([os.path.join(BIN, "ca65.exe"), "--cpu", "6502", src, "-o", obj], check=True)
            subprocess.run([os.path.join(BIN, "ld65.exe"), "-C", os.path.join(HERE, "flat_a000.cfg"),
                            obj, "-o", out], check=True)
            with open(out, "rb") as fh:
                self.assertEqual(fh.read(), data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
