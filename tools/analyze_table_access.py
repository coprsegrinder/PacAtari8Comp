"""Audit of the bot's path-table RAM (OPEN-VERIFICATION.md OV-47).  Usage:  python -I tools/analyze_table_access.py <log> [--summary-file out.txt]     exit code 1 if the game touched the table
The log comes from tools/altirra_sound_bot2.cmd generated with WATCH=1: every CPU read (TBLR) and write (TBLW) in $5000-$76FF with the program counter and the frame.
Allowed: the boot (frame < 100: the OS RAM test at $F25F-$F26B and the RAM clear at $F140 run before the harness loads the table) and the harness's own loads (a debugger write is logged with the PC of the
breakpoint it runs in, $A537, which is the first instruction of the new-game code `lda #$00`, not a store).  Everything else - the game, or the OS after the boot - is a failure.
"""
import collections
import re
import sys

args = sys.argv[1:]
summ = None
if "--summary-file" in args:
    i = args.index("--summary-file")
    summ = args[i + 1]
    del args[i:i + 2]
cnt = collections.Counter()
other = []
newgames = []
last_other = 0
with open(args[0], encoding="utf-8", errors="replace") as fh:
    for line in fh:
        m = re.match(r"TBL([WR]) a=\$([0-9A-F]{4})(?: v=\$[0-9A-F]{2})? pc=\$([0-9A-F]{4}) f=(\d+)", line)
        if m:
            k, a, pc, f = m.group(1), int(m.group(2), 16), int(m.group(3), 16), int(m.group(4))
            if f < 100:
                cnt[("boot", k)] += 1
            elif pc == 0xA537 and k == "W":
                cnt[("harness load", k)] += 1
                newgames.append(f)
            else:
                other.append((k, a, pc, f))
            continue
        if line.startswith("NEWGAME f="):
            newgames.append(None)
out = []
P = lambda *a: out.append(" ".join(str(x) for x in a))
loads = cnt[("harness load", "W")]
games = sum(1 for l in open(args[0], encoding="utf-8", errors="replace") if l.startswith("NEWGAME f="))
P("Accesses to $5000-$76FF: boot (frames < 100) reads %d writes %d; harness loads %d writes (%d games x 10,000 bytes = %d); every other access: %d" % (cnt[("boot", "R")], cnt[("boot", "W")], loads, games, games * 10000, len(other)))
for k, a, pc, f in other[:20]:
    P("  NOT ALLOWED: %s $%04X pc=$%04X frame %d" % (k, a, pc, f))
ok = not other and loads == games * 10000 and games > 0
P("RESULT: " + ("the game and the OS never read or wrote the table after the boot" if ok else "FAIL"))
text = "\n".join(out)
print(text)
if summ:
    open(summ, "w", encoding="utf-8").write(text + "\n")
sys.exit(0 if ok else 1)
