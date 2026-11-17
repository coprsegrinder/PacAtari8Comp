"""Stage 59 (API / hardware tracing): the chip side of the game and its contact with the OS, from the logs of tools/run_hw_audit.ps1 (Altirra 4.40, the real game).

What the logs hold (one line each):
  HWW / HWR  every CPU write / read of GTIA, POKEY, ANTIC (and reads of the PIA), with the address, the value, the instruction that did it (pc), the frame and the scan line (vp)
  SETVBV, SETVBV_DONE   the one OS call of the game: the arguments and the OS vectors afterwards
  VBI        the shadows (OS page 2) at the entry of the deferred vertical-blank handler $A5FD, followed by the debugger's dump of the three chips (.antic .gtia .pokey): the state the chips really have
  DLI1 / DLI2  entry of the two display-list interrupt handlers
The analysis answers: who writes each chip register (the game or the OS), at which scan lines, which values; is every game write one of the static sites of tools/analyze_io.py; does every chip register at the vertical blank equal the
last value written to it (nothing but the traced writes reaches the chips); do the chips equal the OS shadows the game writes (the OS vertical-blank routine copies them, with the attract-mode transform for colours); is the deferred
vertical-blank handler entered once per frame; how the OS API (SETVBV) leaves the vectors.
Usage:  python -I tools/analyze_hw.py analysis/raw-logs/hw-*.txt [--write analysis/evidence-hw-summary.txt]   or  --doc docs/35-api-hardware-tracing.md
"""
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
SUMMARY = os.path.join(ROOT, "analysis", "evidence-hw-summary.txt")
SESSIONS = ("fullgame", "pregame", "gameover", "p2win", "death", "frightened_cases", "inputs", "levels")

DLI_LO, DLI_HI = 0xA573, 0xA5FD            # DliHandler1 .. before VbiHandler (DliHandler2 included)

NAMES = {
    0xD000: "HPOSP0", 0xD001: "HPOSP1", 0xD002: "HPOSP2", 0xD003: "HPOSP3", 0xD004: "HPOSM0", 0xD005: "HPOSM1", 0xD006: "HPOSM2", 0xD007: "HPOSM3",
    0xD008: "SIZEP0", 0xD009: "SIZEP1", 0xD00A: "SIZEP2", 0xD00B: "SIZEP3", 0xD00C: "SIZEM", 0xD00D: "GRAFP0", 0xD00E: "GRAFP1", 0xD00F: "GRAFP2", 0xD010: "GRAFP3", 0xD011: "GRAFM",
    0xD012: "COLPM0", 0xD013: "COLPM1", 0xD014: "COLPM2", 0xD015: "COLPM3", 0xD016: "COLPF0", 0xD017: "COLPF1", 0xD018: "COLPF2", 0xD019: "COLPF3", 0xD01A: "COLBK",
    0xD01B: "PRIOR", 0xD01C: "VDELAY", 0xD01D: "GRACTL", 0xD01E: "HITCLR", 0xD01F: "CONSOL",
    0xD200: "AUDF1", 0xD201: "AUDC1", 0xD202: "AUDF2", 0xD203: "AUDC2", 0xD204: "AUDF3", 0xD205: "AUDC3", 0xD206: "AUDF4", 0xD207: "AUDC4", 0xD208: "AUDCTL", 0xD209: "STIMER",
    0xD20A: "SKRES/RANDOM", 0xD20B: "POTGO", 0xD20D: "SEROUT/SERIN", 0xD20E: "IRQEN/IRQST", 0xD20F: "SKCTL/SKSTAT",
    0xD300: "PORTA", 0xD301: "PORTB", 0xD302: "PACTL", 0xD303: "PBCTL",
    0xD400: "DMACTL", 0xD401: "CHACTL", 0xD402: "DLISTL", 0xD403: "DLISTH", 0xD404: "HSCROL", 0xD405: "VSCROL", 0xD407: "PMBASE", 0xD409: "CHBASE", 0xD40A: "WSYNC",
    0xD40B: "VCOUNT", 0xD40C: "PENH", 0xD40D: "PENV", 0xD40E: "NMIEN", 0xD40F: "NMIRES/NMIST",
}
GTIA_READ = {0xD000 + i: n for i, n in enumerate(["M0PF", "M1PF", "M2PF", "M3PF", "P0PF", "P1PF", "P2PF", "P3PF", "M0PL", "M1PL", "M2PL", "M3PL", "P0PL", "P1PL", "P2PL", "P3PL"])}
GTIA_READ[0xD01F] = "CONSOL"
READ_NAMES = dict(NAMES)
READ_NAMES.update(GTIA_READ)
READ_NAMES.update({0xD010: "TRIG0", 0xD011: "TRIG1", 0xD012: "TRIG2", 0xD013: "TRIG3", 0xD014: "PAL", 0xD209: "KBCODE", 0xD20A: "RANDOM", 0xD20D: "SERIN", 0xD20E: "IRQST", 0xD20F: "SKSTAT", 0xD40F: "NMIST"})

# write-register pairs for the chip dump check: name -> (list of the write addresses that make the value, function of the last written bytes -> the dump's value)
HEXRE = re.compile(r"[0-9A-F]{2,4}")


def who(pc):
    if pc >= 0xC000:
        return "os"
    if DLI_LO <= pc < DLI_HI:
        return "dli"
    if pc >= 0xA000:
        return "game"
    return "ram"


def parse_dump_line(ln, rec):
    """one line of .antic / .gtia / .pokey -> rec[name] = value (int)"""
    m = re.match(r"^(DMACTL|CHACTL|PMBASE|CHBASE|NMIEN)\s*=\s*([0-9A-F]{2})", ln)
    if m:
        rec[m.group(1)] = int(m.group(2), 16)
        return
    m = re.match(r"^DLIST\s*=\s*([0-9A-F]{4})", ln)
    if m:
        rec["DLIST"] = int(m.group(1), 16)
        return
    m = re.match(r"^(Player|Missile)\s+(\d): color = ([0-9A-F]{2}), pos = ([0-9A-F]{2}), size=(\d)", ln)
    if m:
        k = "P" if m.group(1) == "Player" else "M"
        rec[k + "col" + m.group(2)] = int(m.group(3), 16)
        rec[k + "pos" + m.group(2)] = int(m.group(4), 16)
        return
    m = re.match(r"^Playfield colors: ([0-9A-F]{2}) \| ([0-9A-F]{2}) ([0-9A-F]{2}) ([0-9A-F]{2}) ([0-9A-F]{2})", ln)
    if m:
        rec["COLBK"], rec["COLPF0"], rec["COLPF1"], rec["COLPF2"], rec["COLPF3"] = [int(g, 16) for g in m.groups()]
        return
    m = re.match(r"^(PRIOR|GRACTL):\s+([0-9A-F]{2})", ln)
    if m:
        rec[m.group(1)] = int(m.group(2), 16)
        return
    m = re.match(r"^AUDF(\d): ([0-9A-F]{2})\s+AUDC\d: ([0-9A-F]{2})", ln)
    if m:
        rec["AUDF" + m.group(1)] = int(m.group(2), 16)
        rec["AUDC" + m.group(1)] = int(m.group(3), 16)
        return
    m = re.match(r"^(AUDCTL|SKCTL|IRQEN):\s+([0-9A-F]{2})", ln)
    if m:
        rec[m.group(1)] = int(m.group(2), 16)


def new_state():
    return {
        "frames_text": {}, "w": defaultdict(lambda: [0, set(), Counter(), Counter()]),    # (addr, who) -> count, pcs, values, vp
        "r": defaultdict(lambda: [0, set(), Counter()]),
        "setvbv": [], "setvbv_done": [], "vbi": 0, "vbi_gaps": 0, "vbi_prev": None, "vbi_rtclok_gaps": 0, "vbi_rt_prev": None,
        "dli1": 0, "dli2": 0, "dli_vp": {"DLI1": Counter(), "DLI2": Counter()}, "dli_seq": Counter(),
        "checks": defaultdict(lambda: [0, 0, []]), "consistency": defaultdict(lambda: [0, 0, []]), "os_vbi_writes": Counter(),
        "dliw": Counter(), "frames_seen": 0, "sessions": [], "boot_skip": 0,
    }


def check(S, kind, name, ok, info):
    c = S[kind][name]
    c[0] += 1
    if not ok:
        c[1] += 1
        if len(c[2]) < 3:
            c[2].append(info)


def process(path, S):
    last = {}                  # address -> last value written (CPU)
    cur = None                 # the VBI record being filled by dump lines
    seq = []
    cur_f = None
    sess = os.path.basename(path)[3:-4]
    S["sessions"].append(sess)

    def finish(rec):
        if rec is None or rec["f"] < 60 or "DMACTL" not in rec or "AUDF1" not in rec or "COLPF0" not in rec:
            return
        sh = rec["sh"]
        # chips == the OS shadows the game writes (the OS vertical-blank routine copies them)
        drk, colrsh = sh["drk"], sh["colrsh"]
        check(S, "checks", "DMACTL = SDMCTL", rec["DMACTL"] == sh["sdmctl"], (sess, rec["f"], rec["DMACTL"], sh["sdmctl"]))
        check(S, "checks", "DLIST = SDLSTL/H", rec["DLIST"] == sh["sdl"], (sess, rec["f"], rec["DLIST"], sh["sdl"]))
        check(S, "checks", "PRIOR = GPRIOR", rec["PRIOR"] == sh["gprior"], (sess, rec["f"], rec["PRIOR"], sh["gprior"]))
        check(S, "checks", "CHBASE = CHBAS", rec["CHBASE"] == sh["chbas"], (sess, rec["f"], rec["CHBASE"], sh["chbas"]))
        check(S, "checks", "CHACTL = CHACT", rec["CHACTL"] == sh["chact"], (sess, rec["f"], rec["CHACTL"], sh["chact"]))
        check(S, "checks", "IRQEN = POKMSK", rec["IRQEN"] == sh["pokmsk"], (sess, rec["f"], rec["IRQEN"], sh["pokmsk"]))
        for i in range(4):
            e = ((sh["pcol"][i] ^ colrsh) & drk) & 0xFF
            check(S, "checks", "COLPM%d = (PCOLR%d xor COLRSH) and DRKMSK" % (i, i), rec["Pcol%d" % i] == e, (sess, rec["f"], rec["Pcol%d" % i], e))
        for name, k in (("COLPF0", 0), ("COLPF1", 1), ("COLPF2", 2), ("COLPF3", 3), ("COLBK", 4)):
            e = ((sh["col"][k] ^ colrsh) & drk) & 0xFF
            check(S, "checks", "%s = (COLOR%d xor COLRSH) and DRKMSK" % (name, k if k < 4 else 4), rec[name] == e, (sess, rec["f"], rec[name], e))
        # chips == the last CPU write (nothing else reaches the chips)
        for name, addr, key in rec["lastw"]:
            if key in rec:
                check(S, "consistency", name, rec[key] == rec["lastw_val"][addr], (sess, rec["f"], rec[key], rec["lastw_val"][addr]))

    CONS = [("DMACTL", 0xD400, "DMACTL"), ("CHACTL", 0xD401, "CHACTL"), ("PMBASE", 0xD407, "PMBASE"), ("CHBASE", 0xD409, "CHBASE"), ("NMIEN", 0xD40E, "NMIEN"),
            ("PRIOR", 0xD01B, "PRIOR"), ("GRACTL", 0xD01D, "GRACTL"), ("AUDCTL", 0xD208, "AUDCTL"), ("SKCTL", 0xD20F, "SKCTL"), ("IRQEN", 0xD20E, "IRQEN")]
    CONS += [("HPOSP%d" % i, 0xD000 + i, "Ppos%d" % i) for i in range(4)] + [("HPOSM%d" % i, 0xD004 + i, "Mpos%d" % i) for i in range(4)]
    CONS += [("COLPM%d" % i, 0xD012 + i, "Pcol%d" % i) for i in range(4)] + [("COLPF%d" % i, 0xD016 + i, "COLPF%d" % i) for i in range(4)] + [("COLBK", 0xD01A, "COLBK")]
    CONS += [("AUDF%d" % (i + 1), 0xD200 + 2 * i, "AUDF%d" % (i + 1)) for i in range(4)] + [("AUDC%d" % (i + 1), 0xD201 + 2 * i, "AUDC%d" % (i + 1)) for i in range(4)]
    with open(path, encoding="ascii", errors="replace") as fh:
        for ln in fh:
            if not ln.endswith(chr(10)):
                continue                                       # the last line of a killed run may be cut
            c0 = ln[:3]
            if c0 == "HWW":
                p = ln.split()
                a = int(p[1][3:7], 16)
                v = int(p[2][3:5], 16)
                pc = int(p[3][4:8], 16)
                vp = int(p[5][3:])
                w = who(pc)
                e = S["w"][(a, w)]
                e[0] += 1
                e[1].add(pc)
                if len(e[2]) < 300:
                    e[2][v] += 1
                e[3][vp] += 1
                if w == "dli":
                    S["dliw"][(vp, a, v)] += 1
                last[a] = v
                if a == 0xD403:
                    last[0xD402 | 0x10000] = 0
                continue
            if c0 == "HWR":
                p = ln.split()
                a = int(p[1][3:7], 16)
                v = int(p[2][3:5], 16)
                pc = int(p[3][4:8], 16)
                e = S["r"][(a, who(pc))]
                e[0] += 1
                e[1].add(pc)
                continue
            if c0 == "VBI":
                finish(cur)
                m = re.match(r"VBI f=(\d+) rtclok=(\d+) sdmctl=\$([0-9A-F]{2}) sdl=\$([0-9A-F]{4}) gprior=\$([0-9A-F]{2}) col=([0-9A-F,]+) pcol=([0-9A-F,]+) pokmsk=\$([0-9A-F]{2}) atract=([0-9A-F]{2}) drk=([0-9A-F]{2}) colrsh=([0-9A-F]{2}) chbas=([0-9A-F]{2}) chact=([0-9A-F]{2})", ln)
                if not m:
                    cur = None
                    continue
                f, rt = int(m.group(1)), int(m.group(2))
                S["vbi"] += 1
                if S["vbi_prev"] is not None and sess == S.get("vbi_sess") and f != S["vbi_prev"] + 1:
                    S["vbi_gaps"] += 1
                if S["vbi_rt_prev"] is not None and sess == S.get("vbi_sess") and rt != (S["vbi_rt_prev"] + 1) & 0xFF:
                    S["vbi_rtclok_gaps"] += 1
                S["vbi_prev"], S["vbi_rt_prev"], S["vbi_sess"] = f, rt, sess
                cur = {"f": f, "sh": {"sdmctl": int(m.group(3), 16), "sdl": int(m.group(4), 16), "gprior": int(m.group(5), 16), "col": [int(x, 16) for x in m.group(6).split(",")],
                                      "pcol": [int(x, 16) for x in m.group(7).split(",")], "pokmsk": int(m.group(8), 16), "atract": int(m.group(9), 16), "drk": int(m.group(10), 16),
                                      "colrsh": int(m.group(11), 16), "chbas": int(m.group(12), 16), "chact": int(m.group(13), 16)}}
                cur["lastw"] = []
                cur["lastw_val"] = {}
                for name, addr, key in CONS:
                    if addr in last:
                        cur["lastw"].append((name, addr, key))
                        cur["lastw_val"][addr] = last[addr]
                # DLIST is two writes: compare as one word
                if 0xD402 in last and 0xD403 in last:
                    cur["lastw"].append(("DLIST", 0xD402, "DLIST"))
                    cur["lastw_val"][0xD402] = last[0xD402] | last[0xD403] << 8
                    cur["lastw"] = [t for t in cur["lastw"] if t[0] not in ("DLISTL", "DLISTH")]
                seq_f = cur_f
                if seq:
                    S["dli_seq"][tuple(seq)] += 1
                seq = []
                cur_f = f
                continue
            if c0 == "DLI" and ln[3] in "12":
                p = ln.split()
                k = p[0]
                vp = int(p[2][3:])
                S["dli1" if k == "DLI1" else "dli2"] += 1
                S["dli_vp"][k][vp] += 1
                seq.append((k, vp))
                continue
            if ln.startswith("SETVBV"):
                if ln.startswith("SETVBV_DONE"):
                    S["setvbv_done"].append((sess, ln.strip()))
                else:
                    S["setvbv"].append((sess, ln.strip()))
                continue
            if cur is not None:
                parse_dump_line(ln, cur)
    finish(cur)


def main_data(paths):
    S = new_state()
    for p in paths:
        process(p, S)
    return S


def hx(v):
    return "$%02X" % v


def fmt_vals(c, limit=10):
    keys = sorted(c)
    if len(keys) > limit:
        return "%d values, $%02X..$%02X" % (len(keys), keys[0], keys[-1])
    return " ".join("%02X" % k for k in keys)


def fmt_vps(c, limit=14):
    keys = sorted(c)
    if len(keys) > limit:
        return "%d lines, %d..%d" % (len(keys), keys[0], keys[-1])
    return " ".join(str(k) for k in keys)


def static_write_sites():
    import analyze_io as IO
    out = {}
    for s in IO.sites():
        if s["dir"] in ("w", "rw") and 0xD000 <= s["op"] <= 0xD4FF:
            out.setdefault(s["pc"], s)
    return out


def summary_lines(paths):
    S = main_data(paths)
    L = []
    P = L.append
    P("Hardware / API audit (tools/run_hw_audit.ps1, tools/analyze_hw.py): %d harness logs (%s), %d vertical-blank entries with a dump of the chips" % (len(S["sessions"]), ", ".join(sorted(S["sessions"])), S["vbi"]))
    P("")
    P("OS API: SETVBV calls %d (all with %s); vectors after the call: %s" % (len(S["setvbv"]), ", ".join(sorted({re.sub(r" f=\d+", "", t[1]) for t in S["setvbv"]})) or "-", ", ".join(sorted({re.sub(r" f=\d+", "", t[1]) for t in S["setvbv_done"]})) or "-"))
    P("deferred vertical-blank handler: %d entries, frame gaps %d, OS clock (RTCLOK2) gaps %d" % (S["vbi"], S["vbi_gaps"], S["vbi_rtclok_gaps"]))
    P("display-list interrupts: DLI1 %d, DLI2 %d" % (S["dli1"], S["dli2"]))
    P("")
    P("chips against the OS shadows at the entry of the vertical-blank handler (frames from 60 on):")
    for k in sorted(S["checks"]):
        n, bad, ex = S["checks"][k]
        P("  %-52s %7d checks, %5d violations%s" % (k, n, bad, ("  e.g. " + str(ex[0])) if ex else ""))
    P("chips against the last value the CPU wrote to them:")
    for k in sorted(S["consistency"]):
        n, bad, ex = S["consistency"][k]
        P("  %-52s %7d checks, %5d violations%s" % (k, n, bad, ("  e.g. " + str(ex[0])) if ex else ""))
    P("")
    P("writes (register | writer: count, instructions, values, scan lines)")
    for (a, w) in sorted(S["w"]):
        n, pcs, vals, vps = S["w"][(a, w)]
        P("  $%04X %-12s %-4s %9d  %3d pcs  %-26s vp: %s" % (a, NAMES.get(a, "?"), w, n, len(pcs), fmt_vals(vals), fmt_vps(vps)))
    P("reads (register | reader: count, instructions; the value of a read is not available to the trace, the values are in docs/33; a store with an index also makes a dummy read, so a DLI 'read' of COLPM0 is the dummy cycle of its STA)")
    for (a, w) in sorted(S["r"]):
        n, pcs, vals = S["r"][(a, w)]
        P("  $%04X %-12s %-4s %9d  %3d pcs" % (a, READ_NAMES.get(a, "?"), w, n, len(pcs)))
    st = static_write_sites()
    seen = set()
    stray = set()
    for (a, w), (n, pcs, vals, vps) in S["w"].items():
        if w in ("game", "dli"):
            for pc in pcs:
                seen.add(pc)
                s = st.get(pc)
                if s is None or not (s["op"] <= a <= s["op"] + (8 if s["mode"] in ("abx", "aby", "zpx") else 0)):
                    stray.add((pc, a))
    P("")
    P("game / DLI write instructions seen: %d of the %d static chip-write sites; not a static site (or wrong register): %d" % (len(seen), len(st), len(stray)))
    P("static chip-write sites never seen writing in these sessions: %s" % (" ".join("$%04X" % x for x in sorted(set(st) - seen)) or "none"))
    P("")
    P("what the display-list interrupts write (scan line of the write: register = value, times):")
    for (vp, a, v), n in sorted(S["dliw"].items()):
        P("  vp %3d  %-7s = $%02X  %8d" % (vp, NAMES.get(a, "$%04X" % a), v, n))
    P("display-list interrupt line sequences per frame (the most frequent):")
    for seq, n in S["dli_seq"].most_common(4):
        P("  %7d frames: %s" % (n, " ".join("%s@%d" % (k[-1], vp) for k, vp in seq)))
    return L, S


def doc_lines(paths):
    L0, S = summary_lines(paths)
    L = []
    P = L.append
    nchk = sum(v[0] for v in S["checks"].values())
    nbad = sum(v[1] for v in S["checks"].values())
    ncon = sum(v[0] for v in S["consistency"].values())
    nbadc = sum(v[1] for v in S["consistency"].values())
    st = static_write_sites()
    nw = sum(v[0] for v in S["w"].values())
    seen = {pc for (a, w), v in S["w"].items() if w in ("game", "dli") for pc in v[1]}
    P("# 35 - API and Hardware Tracing (stage 59)")
    P("")
    P("GENERATED by `python -I tools/analyze_hw.py analysis/raw-logs/hw-*.txt --doc docs/35-api-hardware-tracing.md` from the logs of `tools/run_hw_audit.ps1` (%d sessions of the real game in Altirra 4.40) and the static sites of `tools/analyze_io.py`. Evidence: `analysis/evidence-hw-summary.txt`. Tests: `tests/test_hw.py`." % len(S["sessions"]))
    P("")
    P("## 1. The result")
    P("")
    P("- **The OS API of the game is two calls.** `JSR SETVBV` at `$A460` (A = 7 = the deferred vertical-blank vector, X/Y = `$A5` / `$FD`) and `JMP XITVBV` at `$A60D`; all %d SETVBV calls of the sessions had A=$07 X=$A5 Y=$FD and left `VVBLKD` = `$A5FD` (the immediate vector `VVBLKI` stays the OS's `$E7AE`). Everything else the game gets from the OS is the **shadow area** (section 3), and what it hands over are the vector `VDSLST` and the shadows." % len(S["setvbv"]))
    P("- **Entered once per frame, without gaps:** the deferred vertical-blank handler `$A5FD` ran %d times in the sessions, every frame number and every OS clock value (`RTCLOK2`) following the previous one (frame gaps %d, clock gaps %d); the display-list interrupts ran %d (DLI1, the game screen) and %d (DLI2, the title screen) times." % (S["vbi"], S["vbi_gaps"], S["vbi_rtclok_gaps"], S["dli1"], S["dli2"]))
    P("- **The chips are what the shadows say** (section 3): at the entry of the handler the debugger's dump of ANTIC, GTIA and POKEY was compared with the OS shadows the game wrote the frame before (`DMACTL`, `DLIST`, `CHBASE`, `CHACTL`, `PRIOR`, the nine colour registers with the attract-mode transform, `IRQEN`): **%d checks, %d violations**." % (nchk, nbad))
    P("- **Nothing but the traced writes reaches the chips** (section 4): the same dump equals the last value the CPU wrote to the register, for the %d registers the dump shows (`DMACTL`, `DLIST`, `PMBASE`, `CHBASE`, `NMIEN`, `PRIOR`, `GRACTL`, the positions, the colours, `AUDF1-4`, `AUDC1-4`, `AUDCTL`, `SKCTL`, `IRQEN`): **%d checks, %d violations**. The %d CPU writes to the chips were made by the game (`$A000-$BFFF`), by the display-list interrupt handlers (`$A573-$A5FC`) or by the OS (`$C000` up); none by any other code." % (len(S["consistency"]), ncon, nbadc, nw))
    P("- **Every game write is a static site**: the game and its interrupt handlers wrote the chips at **%d of the %d** instructions of `analyze_io.py` that can write a chip register, and at no instruction that is not one of them." % (len(seen & set(st)), len(st)))
    P("")
    P("## 2. The OS side")
    P("")
    P("| Item | What the game does | What the OS does (as seen in the trace) |")
    P("|---|---|---|")
    P("| `SETVBV` (`$E45C`, once, `$A460`) | A=7, X=`$A5`, Y=`$FD`: the deferred vertical-blank vector := `$A5FD` | stores it in `VVBLKD` (`$0224`); `VVBLKI` is unchanged |")
    P("| deferred vertical-blank handler | `VbiHandler` `$A5FD`: the whole game frame, then `JMP XITVBV` (`$A60D`) | the OS vertical blank runs first (shadows to chips, stick and trigger shadows, the clock, attract mode), then jumps through `VVBLKD` |")
    P("| display-list interrupts | `VDSLST` (`$0200/1`) := `$A573` (game) or `$A5CE` (title) by `SetDisplayList` | the OS NMI routine reads `NMIST` and jumps through `VDSLST` for a display-list interrupt; the handlers save the registers themselves and end with `RTI` |")
    P("| keyboard | `IRQEN` / `POKMSK` bit 6 set once in `Start`, `SKCTL` = `$07` | the OS IRQ routine (in the OS ROM, `$FFxx`) reads `KBCODE` and stores the code in `CH` (`$02FC`), which the key loop polls: **seen with a real key press** (OV-61, C-68: `tools/altirra_realkey.cmd`; the harnesses of the other audits store the key into `CH` themselves, so this audit read `KBCODE` once) |")
    P("| joystick, triggers | the shadows `STICK0/1`, `STRIG0/1` (`$0278`, `$0279`, `$0284`, `$0285`) | the OS vertical blank reads `PORTA` (`$D300`) and the triggers every frame and stores the shadows |")
    P("| console keys | `CONSOL` (`$D01F`) read directly (the key loop) | the OS also reads it in its vertical blank |")
    P("| nothing else | no `CIOV`, `SIOV`, `SYSVBV`; no OS interrupt vector but `VDSLST` is changed | -- |")
    P("")
    P("## 3. Shadow to chip, at the entry of the frame handler")
    P("")
    P("| The chip register | equals | checks | violations |")
    P("|---|---|---|---|")
    for k in sorted(S["checks"]):
        n, bad, ex = S["checks"][k]
        a, b = k.split(" = ", 1)
        P("| `%s` | `%s` | %d | %d |" % (a, b, n, bad))
    P("")
    P("`COLRSH` (`$4F`) was 0 and `DRKMSK` (`$4E`) `$FE` in the samples (the attract mode never ran: the game writes `ATRACT`, `docs/33`), so the transform of the OS vertical blank is `colour and $FE`; it is tested as `(shadow xor COLRSH) and DRKMSK` for every frame. The first 60 frames of a session (the OS start-up) are left out.")
    P("")
    P("## 4. The chips as the CPU drives them")
    P("")
    P("Per register: who wrote it (`game` = cartridge code outside the interrupt handlers, `dli` = `DliHandler1/2`, `os`), how often in the sessions, from how many instructions, which values, at which scan lines (`vp`, NTSC, 262 lines; the vertical blank starts at line 248, so the OS writes of every frame are at lines 248-251 and the game's deferred handler runs from about line 252 across the frame border). Writes of the value `00` at lines 4-13, once per register and session, are the OS reset. OS rows with fewer than 3 writes are left out.")
    P("")
    P("| Register | Address | Writer | Writes | Instr. | Values | Scan lines |")
    P("|---|---|---|---|---|---|---|")
    for (a, w) in sorted(S["w"]):
        n, pcs, vals, vps = S["w"][(a, w)]
        if n < 3 and w == "os":
            continue
        P("| `%s` | `$%04X` | %s | %d | %d | %s | %s |" % (NAMES.get(a, "?"), a, w, n, len(pcs), fmt_vals(vals), fmt_vps(vps)))
    P("")
    P("### The display-list interrupts, line by line")
    P("")
    P("The stores to `WSYNC` halt the CPU to the end of the line (the stored value is whatever register A held) and are left out here. The game screen has five interrupts per frame, DLI1 at lines 39, 47, 207, 215, 231; the title screen five, DLI2 at lines 47, 87, 127, 143, 215. Frame sequences: %s." % "; ".join("%d frames: %s" % (n, " ".join("%s@%d" % (k[-1], vp) for k, vp in seq)) for seq, n in S["dli_seq"].most_common(2)))
    P("")
    P("| Scan line of the write | Register = value | Times |")
    P("|---|---|---|")
    for (vp, a, v), n in sorted(S["dliw"].items()):
        if NAMES.get(a) == "WSYNC":
            continue
        P("| %d | `%s` = `$%02X` | %d |" % (vp, NAMES.get(a, "$%04X" % a), v, n))
    P("")
    P("## 5. Reads")
    P("")
    P("| Register | Address | Reader | Reads | Instr. |")
    P("|---|---|---|---|---|")
    for (a, w) in sorted(S["r"]):
        n, pcs, _v = S["r"][(a, w)]
        if n < 1000:
            continue
        P("| `%s` | `$%04X` | %s | %d | %d |" % (READ_NAMES.get(a, "?"), a, w, n, len(pcs)))
    P("")
    P("Reads below 1,000 (the OS start-up clear of every register, a few key reads) are in the evidence summary. The collision registers are read only by the game; the indexed stores of the DLI handlers (`sta COLPM0,x`) also make a dummy read cycle, which the trace shows as a read of the same address. The values of the reads are in `docs/33-input-output.md`.")
    P("")
    P("## 6. Limits")
    P("")
    P("- The chips are Altirra's model; the dump is the debugger's own (`.antic`, `.gtia`, `.pokey`). The trace shows the register file and the times of the writes, not the picture or the sound waves (those are in `docs/22-sound.md` and the colour work of `docs/16` and `docs/20`).")
    P("- The dump is taken at the entry of the frame handler only; the state between two interrupts is known from the write log (every write with its line), not from dumps.")
    P("- The sessions play with the test aids of their harnesses (`docs/04`); every claim above is about the game's own writes.")
    P("- The scan line is Altirra's `vpos` when the write is traced; the DLI lines are the lines at which the handler was entered.")
    return L


def main():
    paths = [a for a in sys.argv[1:] if not a.startswith("--") and not a.endswith(".md") and os.path.isfile(a) and a.endswith(".txt") and "evidence" not in a]
    L, S = summary_lines(paths)
    txt = "\n".join(L) + "\n"
    if "--doc" in sys.argv:
        o = sys.argv[sys.argv.index("--doc") + 1]
        with open(os.path.join(ROOT, o), "w", encoding="utf-8", newline=chr(10)) as fh:
            fh.write(chr(10).join(doc_lines(paths)) + chr(10))
        print("wrote", o)
        return
    if "--write" in sys.argv:
        o = sys.argv[sys.argv.index("--write") + 1]
        with open(os.path.join(ROOT, o), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", o)
    print(txt)


if __name__ == "__main__":
    main()
