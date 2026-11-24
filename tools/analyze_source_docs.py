"""Stage 91 (source code documentation): the reference of the C port's source, GENERATED from `src/c` so that it cannot go out of date: the modules and their files, every structure and enumeration, every function declared in a header with its
description and, where it is a routine of the original, its address in the ROM, the algorithms with their C functions, their Python twins and the chapter that explains them, and the implementation decisions.
The curated parts (the purpose of each module, the algorithm table, the decisions) are the tables at the top of this file; everything else is read from the sources.
Checks (tests/test_source_docs.py): every file starts with a comment that says what it is; every function declared in a header, and every structure and enumeration, has a comment; every `Name $ADDR` comment names the address of that label in src/asm/pacman.s;
the chapter is current.
Usage: python -I tools/analyze_source_docs.py [--doc docs/57-source-code-reference.md]"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src", "c")
sys.path.insert(0, HERE)                          # (python -I does not put the script's folder on the path)

MODULES = [
    ("platform", "The one door to the outside: files (`fs`: relative paths under the main folder only, links and 44 kinds of escaping path refused), the clock (`timer`), the inputs of a frame as a table of functions (`hal.h`, the 14 inputs of `45`), the scripted platform used by the tests (`hal_scripted`), and the POKEY RANDOM model (`pokey_random`).", "docs/45, docs/49, docs/51 section 2a"),
    ("core", "The game, in port form: the `World` (all state, generated from the variable catalogue), the lookup tables (installed from the owner's ROM), the pure functions of levels, scoring and the ghosts' steering (`ref`), the ghosts, the ghost house, Pac-Man, scoring, drawing into the player-missile pages, the sound, the frame (`frame`, `play`), and the collision geometry (`gtia`). No file, no allocation, no global state, no system call.", "docs/44, docs/48, docs/50"),
    ("app", "The application layer over the core: the state initialisation, the board, the turn, the level end, the READY! intro, the frame dispatcher with its 15 frame classes, the key loop as a machine with five places, the new game, start-up, and `app_frame` (one frame on a platform).", "docs/38, docs/41 to docs/43, docs/46, docs/51"),
    ("assets", "The data of the game that is not code: the blob format and its loader, the installer that makes the blob from the owner's own NTSC ROM (SHA-256 checked), the layout of the 79 regions (no byte of the ROM is in the sources), and the open font.", "docs/47, docs/49"),
    ("render", "The picture of the screen from the World: ANTIC's display lists, the character sets, GTIA's player-missile priority, the display-list interrupts' colour changes, and the measured NTSC palette. Pure C99, no state outside the `Renderer`.", "docs/42, docs/35, docs/47"),
    ("audio", "The sound: a model of the POKEY from timed register writes to PCM, and the frame-level front end that gives the writes of a frame their cycles (a measured write clock).", "docs/22, docs/35"),
    ("shell", "The headless shell: the frame loop over a replay of recorded inputs, a hash of the state after every frame, the picture and the sound on request, the high score and options under `save/`, a log under `logs/`, the `--states` and `--time` options.", "docs/51, docs/49 D3, docs/52, docs/54"),
    ("tests", "The C tests: the toolchain facts, the World, the vector runner (the recorded calls of the original's routines, replayed), the file sandbox, the portability scan, and the self tests of the platform, assets, audio and shell.", "docs/51, docs/52, docs/55"),
]

# algorithm, C functions, Python twin, chapter
ALGORITHMS = [
    ("Speed pacing: when an entity moves in a frame, by level", "ref_pacing_delay, ref_move_delay_tick, move_delay_tick_w", "core_ref.py, core_play.py", "docs/31 (algorithm 3), docs/44"),
    ("Release timers of the ghosts, by level", "ref_release_timers, set_release_timers, house_waiting_tick, house_leave_step", "core_ref.py, core_ghost.py", "docs/31, docs/13, docs/44"),
    ("Junction lookup: the exits of the lattice point under an entity", "ref_junction_exits, junction_lookup", "core_ref.py", "docs/31, docs/41"),
    ("Steering: the direction at a junction, with RANDOM", "ref_wants, ref_steer, steer_to_target", "core_ref.py, core_ghost.py", "docs/31, docs/13"),
    ("Ghost state machine: start route, patrol, chase, corner, frightened, eaten, house", "ghost_behaviour, ghost_start_route, ghost_patrol, ghost_chase, ghost_go_to_corner, chase_timer_siren_sight, ghost_sees_pacman, force_chase", "core_ghost.py", "docs/13, docs/17, docs/18, docs/44"),
    ("Frightened period: the phases, the power pellet, the end", "frightened_tick, power_pellet_check, ref_power_pellet_ghosts, ref_frightened_end, ref_fright_frames", "core_frame.py, core_score.py", "docs/14, docs/18"),
    ("Scoring: BCD addition, the extra life, ghost points, bonus items", "add_to_score, ref_score_add, ref_ghost_points, bonus_item_update, ref_bonus_points", "core_score.py, core_ref.py", "docs/31 (algorithm 2), docs/20"),
    ("Pac-Man: joystick, buffered turn, step, tunnel wrap, mouth", "move_pacman, read_joystick", "core_pacman.py", "docs/41, docs/20, docs/44"),
    ("Drawing into the player-missile pages, the tunnel clip", "draw_ghost, draw_pacman, step_and_draw_entity, clip_entity_at_tunnel", "core_draw.py", "docs/42, docs/16, docs/44"),
    ("Collision registers of the GTIA, with the latch", "gtia_scene_of_world, gtia_latch_frame_done, gtia_collision_registers", "gtia_collisions.py, platform_iface.py", "docs/50"),
    ("Death sequence and animation", "death_sequence, death_animation, death_animation_draw", "core_sound.py", "docs/20, docs/22"),
    ("Sound: siren, dot sound, frightened, eyes, start tune, bonus", "siren, dot_sound_sweep, frightened_sound, eyes_returning_sound, start_tune_step, bonus_sound", "core_sound.py", "docs/22, docs/44"),
    ("One frame of play, in the order of the original", "play_frame, vbi_play_frame", "core_play.py", "docs/44, docs/48 section 3"),
    ("The frame dispatcher: the 15 frame classes", "frame_dispatch, game_frame, wait_state, turn_control, level_end_step", "core_app_frame.py, core_app_board.py", "docs/38, docs/34"),
    ("The key loop: five places, console, debounce, release", "key_loop, new_game, restart_clear, restart_tail, start", "core_app.py", "docs/38, docs/40, docs/41"),
    ("The board: set-up, the maze copies, the level end, the READY! intro", "init_board, new_board_init, advance_level, draw_ready_screen, draw_level_indicator", "core_app_init.py, core_app_board.py", "docs/43, docs/14"),
]

DECISIONS = [
    ("A faithful port", "The C game has the frame structure and the state of the original: one `play_frame` over the same variables, behind a thin `Platform` layer. Equivalence means the whole state after every frame.", "docs/49 (decisions 71, 72)"),
    ("C99, strict", "`-std=c99 -Wall -Wextra -Wpedantic -Wconversion -Werror`; clang and gcc; CMake (Ninja). No extension, no pragma, no inline assembly. Compiles unchanged under C11, C17 and C2x.", "docs/49 (73), docs/54"),
    ("All game state is one `World`", "Every zero-page variable by its catalogue name (an array for a multi-byte one, the original address in the comment), the maze and its copies, the status rows, the shadows, the player-missile pages, the positions and the sound-write log. The core functions take a `World *` and nothing else global.", "docs/25, docs/44, `core/world.h`"),
    ("8-bit arithmetic is written out", "The original's byte arithmetic wraps; the C writes every wrap as an explicit cast (`(uint8_t)(x + 1u)`), so that the same code is correct with `-Wconversion` and on any word size. `tests/toolchain_check.c` checks `CHAR_BIT == 8` and the wrap.", "docs/49 (73), docs/28"),
    ("Pointers are offsets", "The original's pointers (`MazePtr`, `SrcPtr`, ...) are 16-bit offsets into the World's regions, not C pointers, so the whole state can be compared byte by byte.", "docs/29"),
    ("RANDOM is injected", "The core reads RANDOM only through a `RandomFeed`: the replays of the equivalence runs inject the recorded bytes; the playable port uses the POKEY polynomial model (seedable).", "docs/49 (D1)"),
    ("Everything the outside does is behind `platform/`", "The 14 inputs of the game are a table of functions (`hal.h`); files go only through `fs.c`, which works on relative paths under the main folder and refuses anything that leaves it; a source scan fails the build if a system header or a file function appears elsewhere.", "docs/45, docs/49 (constraints), docs/51 section 2a"),
    ("No allocation, no global state in the game", "Nothing is allocated while a game runs; the game's state is the `World`; the only globals are the shell's buffers.", "docs/54"),
    ("The data comes from the owner's ROM", "No byte of the cartridge is in the sources: the tables, the maze and the pictures are installed at start-up from `original/Pac-Man.rom` through a blob made by the installer (SHA-256 checked); NTSC only.", "docs/47, docs/49, C-112, C-113"),
    ("Twins of the Python port", "Each C module has a Python twin (`tools/core_*.py`) that was checked against the ROM first; the C was then checked against the twin (vectors) and finally against the ROM itself. A comment `Name $ADDR` after a declaration names the routine of the original and its address; a test checks it against the assembly.", "docs/48 section 7, docs/52"),
    ("One state, one frame, then the next", "A frame is: inputs, the OS clock, the vertical-blank handler, the main program (the key loop) to its next wait, the platform's `frame_done`. The main program is a machine with five places, run after the handler to the place where it waits.", "docs/38, docs/46"),
]

DECL = re.compile(r"^\s*(?:static\s+)?(?:const\s+)?[A-Za-z_][\w\s\*]*?\b([a-z_][a-z_0-9]*)\s*\(([^;{}]*)\)\s*;")
ADDR = re.compile(r"([A-Za-z0-9_]+)\s+\$([0-9A-F]{4})")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def files():
    out = []
    for m, _, _ in MODULES:
        d = os.path.join(SRC, m)
        for f in sorted(os.listdir(d)):
            if f.endswith((".c", ".h")):
                out.append((m, f, os.path.join(d, f)))
    return out


def first_comment(text):
    t = text.lstrip()
    if not t.startswith("/*"):
        return None
    end = t.index("*/")
    body = re.sub(r"^\s*\*\s?", "", t[2:end], flags=re.M).strip()
    body = re.sub(r"\s+", " ", body)
    return body


def summary(text, name):
    c = first_comment(text)
    if c is None:
        return None
    c = re.sub(r"^[\w./-]+\s+-\s+", "", c)                 # "core/score.h - ..."
    c = re.sub(r"^GENERATED by [^:]*:\s*", "", c)
    s = re.split(r"(?<=[.;:])\s", c, maxsplit=1)[0]
    return (s[:170] + "...") if len(s) > 170 else s


def describe(lines, i):
    """the description of the declaration on line i: a comment on the same line, else the comment lines just above"""
    m = re.search(r"/\*\s*(.*?)\s*\*/", lines[i])
    if m:
        return m.group(1)
    j = i - 1
    while j >= 0 and lines[j].strip() == "":
        break
    block = []
    while j >= 0 and (lines[j].strip().startswith(("/*", "*", "//")) or lines[j].strip().endswith("*/")):
        block.insert(0, lines[j].strip())
        j -= 1
        if block[0].startswith("/*"):
            break
    if block:
        t = " ".join(re.sub(r"^(/\*+|\*+/?|//)\s*", "", b).replace("*/", "").strip() for b in block)
        return re.sub(r"\s+", " ", t).strip()
    return None


def functions():
    """[(module, header, name, signature, description, routine name, address, defined in)]"""
    defs = {}
    for m, f, p in files():
        if f.endswith(".c"):
            for i, l in enumerate(read(p).splitlines()):
                mm = re.match(r"^(?:static\s+)?[A-Za-z_][\w\s\*]*?\b([a-z_][a-z_0-9]*)\s*\([^;]*\)\s*$", l)
                if mm and not l.startswith(("static", " ", "\t", "#")) and not l.rstrip().endswith(";"):
                    defs.setdefault(mm.group(1), "%s/%s:%d" % (m, f, i + 1))
    out = []
    for m, f, p in files():
        if not f.endswith(".h") or m == "tests":
            continue
        lines = read(p).splitlines()
        for i, l in enumerate(lines):
            d = DECL.match(l)
            if not d or l.lstrip().startswith(("#", "typedef", "return", "extern")):
                continue
            name = d.group(1)
            sig = re.sub(r"\s*/\*.*?\*/\s*$", "", l.strip()).rstrip(";").strip()
            desc = describe(lines, i)
            rn = ad = None
            if desc:
                a = ADDR.search(desc)
                if a:
                    rn, ad = a.group(1), a.group(2)
            out.append((m, f, name, sig, desc, rn, ad, defs.get(name, "")))
    return out


def structures():
    out = []
    for m, f, p in files():
        if not f.endswith(".h") or m == "tests":
            continue
        t = read(p)
        lines = t.splitlines()
        for i, l in enumerate(lines):
            s = re.match(r"^typedef struct (\w+)?\s*\{", l)
            if s:
                j = i
                while j < len(lines) and not re.match(r"^\}\s*(\w+);", lines[j]):
                    j += 1
                name = re.match(r"^\}\s*(\w+);", lines[j]).group(1) if j < len(lines) else s.group(1)
                nf = sum(1 for k in range(i + 1, j) if re.search(r";", lines[k]))
                out.append((m, f, name, "struct", nf, describe(lines, i)))
            e = re.match(r"^typedef enum (\w+)?\s*\{", l)
            if e:
                j = i
                while j < len(lines) and not re.match(r"^\}\s*(\w+);", lines[j]):
                    j += 1
                name = re.match(r"^\}\s*(\w+);", lines[j]).group(1) if j < len(lines) else e.group(1)
                out.append((m, f, name, "enum", sum(1 for k in range(i + 1, j) if lines[k].strip()), describe(lines, i)))
            e = re.match(r"^enum (\w+)\s*\{", l)
            if e:
                out.append((m, f, e.group(1), "enum", 0, describe(lines, i)))
    return out


def asm_labels():
    lines = read(os.path.join(ROOT, "src", "asm", "pacman.s")).splitlines()
    out = {}
    for i, l in enumerate(lines):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*$", l)
        if m:
            for j in range(i + 1, min(i + 6, len(lines))):
                mm = re.search(r";\s*([0-9A-F]{4})\s+[0-9A-F]{2}", lines[j])
                if mm:
                    out[m.group(1)] = mm.group(1)
                    break
    return out


def gaps():
    """-> (files that do not start with a comment, declarations with no description, comments with a wrong address)"""
    nofile = [f for m, f, p in files() if first_comment(read(p)) is None]
    nodecl = [(m + "/" + f, name) for m, f, name, sig, desc, rn, ad, d in functions() if not desc]
    lab = asm_labels()
    wrong = [(m + "/" + f, name, rn, ad, lab[rn]) for m, f, name, sig, desc, rn, ad, d in functions() if rn in lab and lab[rn] != ad]
    nostruct = [(m + "/" + f, name) for m, f, name, kind, n, desc in structures() if not desc]
    return nofile, nodecl + nostruct, wrong


def enrich(desc, rn):
    """a comment that only names the routine (`DrawLives $AD15`) gets the one-line role the architecture chapter gives that routine (tools/analyze_architecture.py)"""
    if not desc or not rn:
        return desc
    rest = re.sub(r"[A-Za-z0-9_]+ \$[0-9A-F]{4}|[+;:,()]", " ", desc).strip()
    if len(rest.split()) >= 4:
        return desc
    try:
        import analyze_architecture as AA
        role = AA.ROUTINE_PORT.get(rn)
    except Exception:                                    # the architecture tool is not there: the comment stays as it is
        role = None
    return desc + " - " + role[2] if role else desc


def esc(s):
    return (s or "").replace("|", "\\|")


def doc():
    L = []
    P = L.append
    fs = files()
    fn = functions()
    st = structures()
    nl = sum(read(p).count("\n") + 1 for m, f, p in fs)
    P("# 57 - Source code reference (checklist stage 91)")
    P("")
    P("GENERATED by `python -I tools/analyze_source_docs.py --doc docs/57-source-code-reference.md` from `src/c` and `src/asm/pacman.s`; the curated parts (the purpose of each module, the algorithm table, the implementation decisions) are the tables at the top of the tool. Tests: `tests/test_source_docs.py` (the chapter is current; every file starts with a comment; every function declared in a header has a comment; every `Name $ADDR` comment is the address of that label in the assembly).")
    P("")
    P("Checklist stage 91: \"Document functions, variables, structures, algorithms, modules, and implementation decisions.\" This is the reference for the reconstructed source (the C port). The original (the ROM and its disassembly) is documented in `06`-`09`, `23`-`31`; this chapter says where each part of it lives in the C.")
    P("")
    P("## 1. The source at a glance")
    P("")
    P("- **%d files, %d lines** under `src/c` (%d headers, %d implementation files), in %d modules; plus the C-free build files (`CMakeLists.txt` in each folder). C99, clang / gcc, CMake (Ninja)." % (len(fs), nl, sum(1 for _, f, _ in fs if f.endswith(".h")), sum(1 for _, f, _ in fs if f.endswith(".c")), len(MODULES)))
    P("- **%d functions declared in headers** (without the tests), **%d structures and enumerations**; %d of the functions are routines of the original and carry its name and ROM address in their comment." % (len(fn), len(st), sum(1 for x in fn if x[5])))
    P("- **Layers** (an arrow is \"uses\"): `shell` -> `app` -> `core`; `shell` -> `render`, `audio`, `assets`; `app`, `assets`, `core` -> `platform`; `render`, `audio` -> `core`. Nothing in `core` or `app` includes a system header or opens a file.")
    P("")
    P("```mermaid")
    P("flowchart TD")
    P("  shell --> app --> core")
    P("  shell --> render --> core")
    P("  shell --> audio --> core")
    P("  shell --> assets --> platform")
    P("  app --> platform")
    P("  platform --> core")
    P("```")
    P("")
    P("## 2. The modules")
    P("")
    P("| Module | Purpose | Explained in |")
    P("|---|---|---|")
    for m, purpose, where in MODULES:
        P("| `%s/` | %s | %s |" % (m, esc(purpose), where))
    P("")
    for m, purpose, where in MODULES:
        P("### `%s/`" % m)
        P("")
        P("| File | Lines | What it is |")
        P("|---|---|---|")
        for mm, f, p in fs:
            if mm == m:
                t = read(p)
                P("| `%s` | %d | %s |" % (f, t.count("\n") + 1, esc(summary(t, f))))
        P("")
    P("## 3. Structures and enumerations")
    P("")
    P("| Name | Kind | In | Entries | What it is |")
    P("|---|---|---|---|---|")
    for m, f, name, kind, n, desc in st:
        P("| `%s` | %s | `%s/%s` | %s | %s |" % (name, kind, m, f, n if n else "", esc((desc or "")[:200])))
    P("")
    P("The `World` (`core/world.h`, generated by `tools/make_c_world.py`) holds, by name, every zero-page variable of `25` that the game uses (an array for a multi-byte variable), the bytes of the zero page the game does not use as `zp_XX`, and the regions: the maze `$0C00`, the status rows `$2000`, the OS shadows `$0200`, the stick shadows, the collision registers, the player-missile pages `$2300`, the eight positions, the picture buffers `$0400`, the stored maze `$0800`, the two saved mazes and the title screen, and the log of sound-chip writes. `PM_STATE_SIZE` bytes of it are the packed state that the comparisons use (`docs/43`).")
    P("")
    P("## 4. The functions")
    P("")
    P("Every function declared in a header, by module. **ROM** is the routine of the original it is the port of (the address of its label in `src/asm/pacman.s`, checked by a test); a function without one is a helper, a table access or part of the platform. **Defined** is where the body is.")
    P("")
    cur = None
    for m, f, name, sig, desc, rn, ad, d in fn:
        if (m, f) != cur:
            cur = (m, f)
            P("")
            P("### `%s/%s`" % (m, f))
            P("")
            P("| Function | ROM | Defined | What it does |")
            P("|---|---|---|---|")
        P("| `%s` | %s | %s | %s |" % (name, ("%s `$%s`" % (rn, ad)) if rn else "", ("`%s`" % d) if d else "", esc(enrich(desc, rn))))
    P("")
    P("## 5. The algorithms")
    P("")
    P("| Algorithm | C functions | Python twin (`tools/`) | Explained in |")
    P("|---|---|---|---|")
    names = {x[2] for x in fn}
    for a, cf, tw, ch in ALGORITHMS:
        P("| %s | %s | %s | %s |" % (a, ", ".join("`%s`" % c.strip() for c in cf.split(",")), ", ".join("`%s`" % c.strip() for c in tw.split(",")), ch))
    P("")
    P("## 6. Implementation decisions")
    P("")
    P("| Decision | What it means | Recorded in |")
    P("|---|---|---|")
    for a, b, c in DECISIONS:
        P("| %s | %s | %s |" % (a, esc(b), c))
    P("")
    P("## 7. Conventions")
    P("")
    P("- **Names.** C functions are the snake-case names of the Python twins; a routine of the original keeps its meaning in the name, the label and address in the comment (`/* GhostEaten $A886 */`). World fields are the catalogue names of `25` (`PacHold`, `DotsEatenLo`, ...). Constants of the original are `#define`d with the name of `31`.")
    P("- **Comments.** Every file starts with a comment that says what it is, the stage that wrote it and the chapter that explains it. Every function declared in a header has a comment on its line or just above; a routine of the original names it and its address.")
    P("- **Generated files** (`core/world.h`, `core/world.c` regions, `core/tables.h`, `core/constants.h`, `assets/rom_layout.[ch]`, `render/palette.[ch]`, the collision tables) say `GENERATED by tools/make_c_*.py` on their first line and must not be edited: `tests/test_regression.py` runs every generator and checks that it writes the same bytes.")
    P("- **Where a function is tested.** `tests/` (C): the vector sets (`ctest vectors_*`) call each core and app function with the recorded arguments of the original's own calls; `tests/test_c_*.py` (Python) check the generated sources and the vector sets; `tests/test_c_vs_rom.py`, `test_behaviour.py`, `test_regression.py` check the whole program against the ROM and against the golden games.")
    P("")
    P("## 8. What the documentation does not do")
    P("")
    P("The descriptions of the functions are the comments of the sources, in one line each; the reasons and the evidence are in the chapters named in the tables. The `tests/` folder's helper functions are not listed in section 4. The Python tools and tests (`tools/`, `tests/`) are described in `02` and `04`; each starts with a docstring that says what it is (checked). The reference was checked for completeness (no file and no declaration without a comment) and for the ROM addresses; it was not checked that every sentence of every comment is true: that is what the vector tests and the comparisons with the ROM do for the behaviour.")
    return "\n".join(L) + "\n"


def main():
    nofile, nodecl, wrong = gaps()
    text = doc()
    if "--doc" in sys.argv:
        o = sys.argv[sys.argv.index("--doc") + 1]
        with open(os.path.join(ROOT, o) if not os.path.isabs(o) else o, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("wrote", o)
    print("files without a first comment: %d; declarations without a description: %d; wrong ROM addresses: %d" % (len(nofile), len(nodecl), len(wrong)))
    for x in nofile + nodecl + wrong:
        print("  ", x)
    sys.exit(1 if (nofile or nodecl or wrong) else 0)


if __name__ == "__main__":
    main()
