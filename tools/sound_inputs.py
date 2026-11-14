"""What does each sound routine READ?  (docs/22-sound.md, OPEN-VERIFICATION.md OV-11).  Usage:  python -I tools/sound_inputs.py
Decodes every sound routine of the ROM instruction by instruction (tools/disasm6502.decode) and lists the memory locations it reads: zero page and absolute variables, and the base
of indexed accesses.  Used by tests/test_sound.py to prove that no sound routine reads the level counters (Level $30/$31, StartLevel $1B) or a table indexed by level.
Read-only.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_streams as S  # noqa: E402
import disasm6502 as D  # noqa: E402

READS = {"lda", "ldx", "ldy", "adc", "sbc", "cmp", "cpx", "cpy", "and", "ora", "eor", "bit", "inc", "dec", "asl", "lsr", "rol", "ror"}
MEM = {"zp", "zpx", "zpy", "abs", "abx", "aby", "izx", "izy"}

# (name, first address, address after the last instruction): contiguous code of the routine itself (callees are NOT followed)
ROUTINES = [
    ("start tune loop", 0xA7D3, 0xA800),
    ("ghost eaten: start ($A8EC)", 0xA8EC, 0xA8FD),
    ("bonus item sound Sub_ABC9", 0xABC9, 0xAC05),
    ("death glide (DeathSequence sound part)", 0xAE92, 0xAEEF),
    ("frightened sound Sub_AFD7", 0xAFD7, 0xB02C),
    ("eyes sound Sub_B02C", 0xB02C, 0xB049),
    ("ghost eaten sweep LB049..LB084", 0xB049, 0xB085),
    ("dot sweep Sub_B0BC", 0xB0BC, 0xB0E6),
    ("ClearPokeyRegisters", 0xB0E6, 0xB0F1),
    ("siren LB508..LB54E", 0xB508, 0xB54F),
    ("siren step choice Sub_B5C7..LB5FF", 0xB5C7, 0xB601),
]
NAMES = {0x1B: "StartLevel", 0x14: "RTCLOK2", 0x19: "zp_19", 0x30: "Level", 0x31: "Level+1 (player 2)", 0x2B: "CurrentPlayer",
         0x34: "dots eaten (low byte, player 1/2 = $34/$35)", 0x36: "dots eaten (high byte, $36/$37)", 0x9C: "siren step", 0xDE: "siren AUDF", 0xDF: "siren direction", 0xE0: "siren started",
         0xE1: "frightened AUDF", 0xE2: "frightened direction", 0xE3: "frightened volume", 0xE4: "frightened started", 0xE5: "ghost-eaten sound running", 0xE6: "ghost-eaten phase counter",
         0xE7: "ghost-eaten AUDF", 0xE8: "ghost eaten (index)", 0xF2: "eaten ghosts returning", 0xF3: "eyes AUDF", 0xF4: "dot sweep active", 0xF5: "dot sweep step", 0xF6: "dot sweep direction",
         0xF7: "bonus sound step", 0xF8: "bonus sound AUDF", 0xA3: "tune step", 0xCE: "GhostState", 0xFC: "FrightenPhase", 0xAD: "ChaseTimer", 0xED: "DeathState", 0xEF: "death AUDF", 0xF0: "death AUDF", 0xF1: "death step"}


def reads(lo, hi):
    out = {}
    a = lo
    while a < hi:
        d = D.decode(S.ROM, 0xA000, a)
        if d is None:
            raise ValueError("cannot decode at $%04X" % a)
        n, mnem, mode, op = d
        if mnem in READS and mode in MEM:
            key = (op, "indexed" if mode in ("zpx", "zpy", "abx", "aby") else ("pointer" if mode in ("izx", "izy") else "direct"))
            out.setdefault(key, []).append(a)
        a += n
    if a != hi:
        raise ValueError("range does not end on an instruction boundary: $%04X" % a)
    return out


def main():
    for name, lo, hi in ROUTINES:
        r = reads(lo, hi)
        print("%-44s $%04X-$%04X  reads:" % (name, lo, hi - 1))
        for (addr, kind), sites in sorted(r.items()):
            label = NAMES.get(addr, "")
            print("    $%04X %-8s %-45s at %s" % (addr, kind, label, " ".join("$%04X" % s for s in sites[:4])))


if __name__ == "__main__":
    main()
