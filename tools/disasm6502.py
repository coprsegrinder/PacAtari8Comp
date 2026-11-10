"""6502 disassembler for the Pac-Man (Atari 8-bit) project -- Step C8.

Emits ca65-compatible source so the output can be reassembled byte-for-byte (Step C10).
Only the 151 official NMOS 6502 opcodes are decoded; anything else is reported as data.

Library use:
    from disasm6502 import decode, trace, listing
CLI (from the project root):
    python -I tools/disasm6502.py original/Pac-Man.rom --base A000 --entry A386 --entry A6B4
    python -I tools/disasm6502.py ROM --base A000 --linear          # linear sweep of everything
Read-only: never modifies the input file.
"""
import argparse
import sys

# mode -> (operand size in bytes)
SIZE = {"imp": 0, "acc": 0, "imm": 1, "zp": 1, "zpx": 1, "zpy": 1, "izx": 1, "izy": 1,
        "rel": 1, "abs": 2, "abx": 2, "aby": 2, "ind": 2}

_TABLE = {
    "adc": dict(imm=0x69, zp=0x65, zpx=0x75, abs=0x6D, abx=0x7D, aby=0x79, izx=0x61, izy=0x71),
    "and": dict(imm=0x29, zp=0x25, zpx=0x35, abs=0x2D, abx=0x3D, aby=0x39, izx=0x21, izy=0x31),
    "asl": dict(acc=0x0A, zp=0x06, zpx=0x16, abs=0x0E, abx=0x1E),
    "bcc": dict(rel=0x90), "bcs": dict(rel=0xB0), "beq": dict(rel=0xF0),
    "bit": dict(zp=0x24, abs=0x2C),
    "bmi": dict(rel=0x30), "bne": dict(rel=0xD0), "bpl": dict(rel=0x10),
    "brk": dict(imp=0x00), "bvc": dict(rel=0x50), "bvs": dict(rel=0x70),
    "clc": dict(imp=0x18), "cld": dict(imp=0xD8), "cli": dict(imp=0x58), "clv": dict(imp=0xB8),
    "cmp": dict(imm=0xC9, zp=0xC5, zpx=0xD5, abs=0xCD, abx=0xDD, aby=0xD9, izx=0xC1, izy=0xD1),
    "cpx": dict(imm=0xE0, zp=0xE4, abs=0xEC),
    "cpy": dict(imm=0xC0, zp=0xC4, abs=0xCC),
    "dec": dict(zp=0xC6, zpx=0xD6, abs=0xCE, abx=0xDE),
    "dex": dict(imp=0xCA), "dey": dict(imp=0x88),
    "eor": dict(imm=0x49, zp=0x45, zpx=0x55, abs=0x4D, abx=0x5D, aby=0x59, izx=0x41, izy=0x51),
    "inc": dict(zp=0xE6, zpx=0xF6, abs=0xEE, abx=0xFE),
    "inx": dict(imp=0xE8), "iny": dict(imp=0xC8),
    "jmp": dict(abs=0x4C, ind=0x6C), "jsr": dict(abs=0x20),
    "lda": dict(imm=0xA9, zp=0xA5, zpx=0xB5, abs=0xAD, abx=0xBD, aby=0xB9, izx=0xA1, izy=0xB1),
    "ldx": dict(imm=0xA2, zp=0xA6, zpy=0xB6, abs=0xAE, aby=0xBE),
    "ldy": dict(imm=0xA0, zp=0xA4, zpx=0xB4, abs=0xAC, abx=0xBC),
    "lsr": dict(acc=0x4A, zp=0x46, zpx=0x56, abs=0x4E, abx=0x5E),
    "nop": dict(imp=0xEA),
    "ora": dict(imm=0x09, zp=0x05, zpx=0x15, abs=0x0D, abx=0x1D, aby=0x19, izx=0x01, izy=0x11),
    "pha": dict(imp=0x48), "php": dict(imp=0x08), "pla": dict(imp=0x68), "plp": dict(imp=0x28),
    "rol": dict(acc=0x2A, zp=0x26, zpx=0x36, abs=0x2E, abx=0x3E),
    "ror": dict(acc=0x6A, zp=0x66, zpx=0x76, abs=0x6E, abx=0x7E),
    "rti": dict(imp=0x40), "rts": dict(imp=0x60),
    "sbc": dict(imm=0xE9, zp=0xE5, zpx=0xF5, abs=0xED, abx=0xFD, aby=0xF9, izx=0xE1, izy=0xF1),
    "sec": dict(imp=0x38), "sed": dict(imp=0xF8), "sei": dict(imp=0x78),
    "sta": dict(zp=0x85, zpx=0x95, abs=0x8D, abx=0x9D, aby=0x99, izx=0x81, izy=0x91),
    "stx": dict(zp=0x86, zpy=0x96, abs=0x8E),
    "sty": dict(zp=0x84, zpx=0x94, abs=0x8C),
    "tax": dict(imp=0xAA), "tay": dict(imp=0xA8), "tsx": dict(imp=0xBA),
    "txa": dict(imp=0x8A), "txs": dict(imp=0x9A), "tya": dict(imp=0x98),
}

OPCODES = {}  # opcode byte -> (mnemonic, mode)
for _m, _modes in _TABLE.items():
    for _mode, _op in _modes.items():
        assert _op not in OPCODES, hex(_op)
        OPCODES[_op] = (_m, _mode)
assert len(OPCODES) == 151

BRANCHES = {"bcc", "bcs", "beq", "bmi", "bne", "bpl", "bvc", "bvs"}


def decode(data, base, addr):
    """Decode one instruction at CPU address `addr`.

    Returns (length, mnemonic, mode, operand) or None if the byte is not an official opcode or
    the instruction runs past the end of `data`. For 'rel' the operand is the absolute target.
    """
    i = addr - base
    if not 0 <= i < len(data) or data[i] not in OPCODES:
        return None
    mnem, mode = OPCODES[data[i]]
    n = 1 + SIZE[mode]
    if i + n > len(data):
        return None
    if SIZE[mode] == 0:
        op = None
    elif SIZE[mode] == 1:
        op = data[i + 1]
        if mode == "rel":
            op = (addr + 2 + (op - 256 if op >= 128 else op)) & 0xFFFF
    else:
        op = data[i + 1] | data[i + 2] << 8
    return n, mnem, mode, op


def operand_text(mode, op, label=None, mnem=None):
    """ca65 operand text. `label(addr)` may return a symbol name for a code address or None."""
    sym = (lambda a: (label(a) if label else None) or "$%04X" % a)
    if mode in ("imp",):
        return ""
    if mode == "acc":
        return "a"
    if mode == "imm":
        return "#$%02X" % op
    if mode == "zp":
        return "z:$%02X" % op
    if mode == "zpx":
        return "z:$%02X,x" % op
    if mode == "zpy":
        return "z:$%02X,y" % op
    if mode == "izx":
        return "($%02X,x)" % op
    if mode == "izy":
        return "($%02X),y" % op
    if mode == "rel":
        return sym(op)
    # Absolute forms: force 16-bit encoding when the address is below $0100 (ca65 would pick zp).
    # JMP/JSR have no zero-page form, so they never need the prefix.
    pre = "a:" if op < 0x100 and mnem not in ("jmp", "jsr") else ""
    text = sym(op) if (mode == "abs" and op >= 0x100) else pre + "$%04X" % op
    if mode == "abx":
        return text + ",x"
    if mode == "aby":
        return text + ",y"
    if mode == "ind":
        return "(" + text + ")"
    return text


def instr_text(mnem, mode, op, label=None):
    t = operand_text(mode, op, label, mnem)
    return mnem + (" " + t if t else "")


def trace(data, base, entries):
    """Recursive descent. Returns (code, targets): code = {addr: length} of reachable
    instructions, targets = set of addresses that are jump/branch/call destinations.

    Follows branches, JSR (and assumes it returns), JMP abs. Stops at RTS, RTI, BRK, JMP, and at
    any byte that is not an official opcode. Indirect JMP and computed jumps are NOT followed;
    they must be supplied as extra entries.
    """
    code, targets, work = {}, set(), list(entries)
    end = base + len(data)
    while work:
        a = work.pop()
        while base <= a < end and a not in code:
            d = decode(data, base, a)
            if d is None:
                break
            n, mnem, mode, op = d
            code[a] = n
            if mnem in BRANCHES:
                targets.add(op)
                work.append(op)
            elif mnem == "jsr":
                targets.add(op)
                work.append(op)
            elif mnem == "jmp":
                if mode == "abs":
                    targets.add(op)
                    work.append(op)
                break
            elif mnem in ("rts", "rti", "brk"):
                break
            a += n
    return code, targets


def listing(data, base, code, targets, names=None, out=sys.stdout):
    """Print a ca65-style listing: decoded code where `code` says so, `.byte` runs elsewhere."""
    names = names or {}
    end0 = base + len(data)
    # Only addresses inside the image get generated labels; outside ones stay numeric unless named.
    label = lambda a: names.get(a) or ("L%04X" % a if a in targets and base <= a < end0 else None)
    a, end = base, end0
    while a < end:
        lab = label(a)
        if a in code:
            _, mnem, mode, op = decode(data, base, a)
            if lab:
                print("%s:" % lab, file=out)
            raw = " ".join("%02X" % data[a - base + k] for k in range(code[a]))
            print("        %-22s ; %04X  %s" % (instr_text(mnem, mode, op, label), a, raw), file=out)
            a += code[a]
        else:
            if lab:
                print("%s:" % lab, file=out)
            run = []
            while a < end and a not in code and (not run or label(a) is None):
                run.append(data[a - base])
                a += 1
                if len(run) == 8:
                    break
            print("        .byte %-40s ; %04X" % (",".join("$%02X" % b for b in run), a - len(run)), file=out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom")
    ap.add_argument("--base", default="A000", help="CPU address of first byte (hex)")
    ap.add_argument("--entry", action="append", default=[], help="code entry address (hex), repeatable")
    ap.add_argument("--linear", action="store_true", help="decode every byte linearly instead of tracing")
    a = ap.parse_args()
    data = open(a.rom, "rb").read()
    base = int(a.base, 16)
    if a.linear:
        code, targets, p = {}, set(), base
        while p < base + len(data):
            d = decode(data, base, p)
            if d is None:
                p += 1
                continue
            code[p] = d[0]
            if d[1] in BRANCHES or d[1] in ("jsr", "jmp") and d[2] == "abs":
                targets.add(d[3])
            p += d[0]
    else:
        code, targets = trace(data, base, [int(e, 16) for e in a.entry])
    listing(data, base, code, targets)


if __name__ == "__main__":
    main()
