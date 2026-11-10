"""Steps C9/C11: generate the annotated ca65 disassembly of Pac-Man.rom into src/asm/pacman.s.

Usage (project root):  python -I tools/make_asm.py        then   python -I tools/build_rom.py
Code = recursive trace from the entry points below; symbols come from tools/labels.py; data that is
referenced by code gets a D_xxxx label; known structures (display lists, text, cartridge header) are
rendered with comments. The result must always rebuild byte-for-byte (tools/build_rom.py).
Read-only on the ROM; writes src/asm/pacman.s and src/asm/pacman.cfg.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import disasm6502 as D  # noqa: E402
import labels as LB  # noqa: E402

ROOT = os.path.dirname(HERE)
BASE, SIZE = 0xA000, 0x2000
with open(os.path.join(ROOT, "original", "Pac-Man.rom"), "rb") as fh:
    data = fh.read()
assert len(data) == SIZE

# Entry points (address: evidence).
ENTRIES = {
    0xA386: "cartridge RUN vector at $BFFA",
    0xA6B4: "cartridge INIT vector at $BFFE (the routine is just RTS)",
    0xA5FD: "SETVBV (A=7 deferred VBI, X=$A5, Y=$FD) called at $A460; ends with JMP XITVBV at $A60D",
    0xA573: "VDSLST set to $A573 by SetDisplayList (X=$A3, Y=$73) at $A49B; saves A/X, ends RTI",
    0xA5CE: "VDSLST set to $A5CE by SetDisplayList (X=$81, Y=$CE) at $A621; saves A/X/Y, ends RTI",
}

code, targets = D.trace(data, BASE, list(ENTRIES))
inside = set()
for a, n in code.items():
    inside.update(range(a + 1, a + n))
bad = sorted(t for t in targets if t in inside)
if bad:
    sys.exit("targets inside an instruction: " + " ".join("%04X" % t for t in bad))
jsr_targets = {D.decode(data, BASE, a)[3] for a in code if D.decode(data, BASE, a)[1] == "jsr"}

# ---- references from code into non-code ROM => data labels -------------------------------
data_refs = {}
for a in sorted(code):
    n, m, mode, op = D.decode(data, BASE, a)
    if mode in ("abs", "abx", "aby") and m not in ("jsr", "jmp") and BASE <= op < BASE + SIZE and op not in code:
        data_refs.setdefault(op, a)
names = {}
for t in targets:
    if BASE <= t < BASE + SIZE and t in jsr_targets:
        names[t] = "Sub_%04X" % t
for a in data_refs:
    names[a] = "D_%04X" % a
names.update({a: n for a, n in LB.ROM_NAMES.items() if BASE <= a < BASE + SIZE})
names.update(LB.OS_ENTRY)

# ---- chunks: structured data --------------------------------------------------------------
chunks = {}


def screen_text(bs):
    """Atari internal screen codes -> readable text; runs of inverse-video characters are put in [ ]."""
    out, inv = "", False
    for b in bs:
        c = b & 0x7F
        ch = chr(c + 0x20) if c < 0x40 else (chr(c) if c >= 0x60 else "?")
        if bool(b & 0x80) != inv and ch != " ":
            out += "[" if not inv else "]"
            inv = not inv
        out += ch
    return out + ("]" if inv else "")


def screen_text6(bs):
    """ANTIC mode 6 screen codes: low 6 bits = glyph (code + $20 as ASCII), top 2 bits = colour register.
    Runs of one colour are shown as cN"text"; spaces stay with the current run."""
    out, cur, color = [], "", None
    for b in bs:
        ch, c = chr((b & 0x3F) + 0x20), b >> 6
        if ch != " " and c != color:
            if cur.strip():
                out.append('c%d"%s"' % (color, cur))
            cur, color = "", c
        cur += ch
    if cur.strip():
        out.append('c%d"%s"' % (color, cur))
    return " ".join(out)


def antic_dl(start):
    """Render a display list from `start` up to and including its JVB: list of (addr, length, text)."""
    rows, a = [], start
    while True:
        b = data[a - BASE]
        mode = b & 0x0F
        dli = ", DLI" if b & 0x80 else ""
        if mode == 0:
            rows.append((a, 1, "        .byte $%02X                      ; %04X  %d blank lines%s" % (
                b, a, ((b >> 4) & 7) + 1, dli)))
            a += 1
        elif mode == 1:
            tgt = data[a - BASE + 1] | data[a - BASE + 2] << 8
            kind = "jump and wait for vertical blank" if b & 0x40 else "jump"
            rows.append((a, 3, "        .byte $%02X                      ; %04X  %s\n        .word %s" % (
                b, a, kind, names.get(tgt, "$%04X" % tgt))))
            a += 3
            if b & 0x40:
                return rows
        elif b & 0x40:
            tgt = data[a - BASE + 1] | data[a - BASE + 2] << 8
            rows.append((a, 3, "        .byte $%02X                      ; %04X  mode %X, load memory scan%s\n        .word $%04X" % (
                b, a, mode, dli, tgt)))
            a += 3
        else:
            rows.append((a, 1, "        .byte $%02X                      ; %04X  mode %X%s" % (b, a, mode, dli)))
            a += 1


for dl_start in (0xBF81, 0xBFA3):
    rows = antic_dl(dl_start)
    i = 0
    while i < len(rows):
        a, n, text = rows[i]
        j = i + 1
        if n == 1:
            key = data[a - BASE]
            while j < len(rows) and rows[j][1] == 1 and data[rows[j][0] - BASE] == key:
                j += 1
        if j - i > 1:
            mode = text.split("; ")[1][6:]
            chunks[a] = (j - i, "        .byte %-40s ; %04X  %dx %s" % (
                ",".join(["$%02X" % key] * (j - i)), a, j - i, mode.split("  ", 1)[-1]))
        else:
            chunks[a] = (n, text)
        i = j

# ---- data regions from tools/labels.py (formats and evidence: docs/12-data-formats.md) ----------
for first, last, kind, name, comment in LB.DATA:
    names[first] = name
    if any(a in code for a in range(first, last + 1)):
        sys.exit("data region %s overlaps code" % name)


def bitmap(b):
    return "".join("#" if b & (0x80 >> k) else "." for k in range(8))


def region_rows(first, last, kind, name, comment):
    """Yield (addr, length, text) rows for one data region; rows never swallow a label."""
    a, rows, head = first, [], ("        ; %s\n" % comment) if comment else ""
    step = {"stream": 16, "bytes": 8, "shape": 1, "words": 2, "text": last - first + 1, "text6": last - first + 1}[kind]
    while a <= last:
        n = min(step, last + 1 - a)
        for k in range(1, n):  # split at labels inside the row
            if (a + k) in names:
                n = k
                break
        if kind == "bytes" and name == "ThresholdLists":
            for k in range(n):
                if data[a - BASE + k] == 0xFF:
                    n = k + 1
                    break
        chunk = data[a - BASE:a - BASE + n]
        if kind == "words" and n == 2:
            v = chunk[0] | chunk[1] << 8
            body = "        .word %-30s ; %04X" % (names.get(v, "$%04X" % v), a)
        elif kind == "shape":
            body = "        .byte $%02X                      ; %04X  %s" % (chunk[0], a, bitmap(chunk[0]))
        elif kind == "text6":
            body = "        .byte %-40s ; %04X  %s" % (",".join("$%02X" % b for b in chunk), a, screen_text6(chunk))
        elif kind == "text":
            body = "        .byte %-40s ; %04X  \"%s\"" % (",".join("$%02X" % b for b in chunk), a, screen_text(chunk).rstrip())
        else:
            body = "        .byte %-40s ; %04X" % (",".join("$%02X" % b for b in chunk), a)
        rows.append((a, n, head + body))
        head = ""
        a += n
    return rows


for region in LB.DATA:
    for a, n, text in region_rows(*region):
        chunks[a] = (n, text)

# cartridge header $BFFA-$BFFF
chunks[0xBFFA] = (2, "        .word Start                      ; BFFA  RUN vector")
chunks[0xBFFC] = (1, "        .byte $00                        ; BFFC  cartridge present")
chunks[0xBFFD] = (1, "        .byte $04                        ; BFFD  option byte: run the cartridge")
chunks[0xBFFE] = (2, "        .word Init                       ; BFFE  INIT vector")

# A chunk must not swallow a labelled address: such chunks fall back to plain .byte lines.
for a in list(chunks):
    n = chunks[a][0]
    if any((a + k) in names for k in range(1, n)):
        del chunks[a]

# ---- symbol hooks ---------------------------------------------------------------------------
used_zp, used_abs = set(), {}


def sym_zp(a):
    used_zp.add(a)
    return LB.zp_name(a)


def sym_abs(a, mnem):
    n = LB.hw_name(a, mnem)
    if n:
        used_abs[a] = n
    return n


uncovered = [a for a in range(BASE, BASE + SIZE) if a not in inside and a not in code
             and not any(c <= a < c + n for c, (n, _) in chunks.items())]
print("data bytes not covered by any region: %d %s" % (len(uncovered), " ".join("%04X" % a for a in uncovered[:16])))

body = io.StringIO()
D.listing(data, BASE, code, targets, names=names, out=body, sym_zp=sym_zp, sym_abs=sym_abs, chunks=chunks)

used_os_entry = {a for a in LB.OS_ENTRY if a in targets}
with open(os.path.join(ROOT, "src", "asm", "pacman.s"), "w", newline="\n") as fh:
    fh.write("; Pac-Man (Atari 8-bit) -- disassembly of original/Pac-Man.rom, $A000-$BFFF, 8,192 bytes\n")
    fh.write("; GENERATED by tools/make_asm.py + tools/labels.py (steps C9, C11); rebuild check: tools/build_rom.py.\n")
    fh.write("; Comments show address and original bytes. Derived from copyrighted code: keep this repository private.\n\n")
    fh.write("; Entry points\n")
    for a, why in sorted(ENTRIES.items()):
        fh.write("; %-14s $%04X  %s\n" % (names.get(a, "L%04X" % a), a, why))
    fh.write("\n; OS entry points\n")
    for a in sorted(used_os_entry):
        fh.write("%-8s = $%04X\n" % (LB.OS_ENTRY[a], a))
    fh.write("\n; Hardware registers and OS variables used (standard Atari 400/800 names)\n")
    for a in sorted(used_abs):
        fh.write("%-8s = $%04X\n" % (used_abs[a], a))
    fh.write("\n; Zero page: names without the zp_ prefix are OS variables; zp_xx are the game's own, not yet named\n")
    for a in sorted(used_zp):
        fh.write("%-8s = $%02X\n" % (LB.zp_name(a), a))
    fh.write('\n.segment "CODE"\n\n')
    fh.write(body.getvalue())

with open(os.path.join(ROOT, "src", "asm", "pacman.cfg"), "w", newline="\n") as fh:
    fh.write("MEMORY { ROM: start = $A000, size = $2000, file = %O, fill = yes, fillval = $00; }\n")
    fh.write("SEGMENTS { CODE: load = ROM, type = ro; }\n")

covered = sum(code.values())
print("code: %d instructions, %d bytes (%.1f%%); data: %d bytes; subroutines: %d; data labels: %d; chunks: %d"
      % (len(code), covered, 100.0 * covered / SIZE, SIZE - covered, len(jsr_targets), len(data_refs), len(chunks)))
