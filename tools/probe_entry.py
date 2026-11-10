"""Step C9 helper: judge whether a candidate address looks like code.

Usage: python -I tools/probe_entry.py ADDR [ADDR...]   (hex, CPU addresses $A000-$BFFF)
Traces from each address alone and reports instructions reached, whether any path hit an
undecodable byte or left the ROM, and a few lines of listing. Read-only.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import disasm6502 as D  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = open(os.path.join(ROOT, "original", "Pac-Man.rom"), "rb").read()
for arg in sys.argv[1:]:
    a = int(arg, 16)
    code, tg = D.trace(data, 0xA000, [a])
    bad = []
    for pc, n in code.items():
        _, m, mode, op = D.decode(data, 0xA000, pc)
        if m in D.BRANCHES or m in ("jsr", "jmp") and mode == "abs":
            if not 0xA000 <= op < 0xC000 and not 0xE000 <= op < 0x10000 and not op < 0x100:
                bad.append("%04X->%04X" % (pc, op))
    end = max(code) + code[max(code)] if code else a
    print("$%04X: %d instrs, bytes $%04X-$%04X, odd targets: %s" % (a, len(code), min(code) if code else a, end, bad[:4] or "none"))
    p = a
    for _ in range(6):
        d = D.decode(data, 0xA000, p)
        if not d:
            print("    %04X  <undecodable %02X>" % (p, data[p - 0xA000]))
            break
        print("    %04X  %s" % (p, D.instr_text(d[1], d[2], d[3])))
        p += d[0]
