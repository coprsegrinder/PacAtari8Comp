"""Stage 96 (resource documentation): ONE catalogue of every resource of the project - the original materials, what was extracted from the ROM, what was decoded and reconstructed, the files made from them, the third-party font, the evidence
material - with each one's FORMAT, ORIGIN, LOCATION (and whether Git ignores it) and how the resources RELATE (what makes what, what reads what).  GENERATED from the asset pack (tools/asset_pack.py), the blob writer (tools/make_c_assets.py), the manifest
of the originals and `.gitignore`; the curated parts (formats by kind, the relationships, the derived files and their commands) are the tables at the top.  The long treatment of the pack's format is `47`; this chapter is the catalogue.
Usage: python -I tools/analyze_resources_docs.py [--doc docs/62-resources-catalogue.md]
Tests: tests/test_resources_docs.py (the chapter is current; the facts it states hold; every file it names exists or is derived and ignored)."""
import collections
import fnmatch
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import asset_pack as AP  # noqa: E402
import make_c_assets as MA  # noqa: E402

# the format of each kind of ROM region (docs/12, docs/47)
KIND_FORMAT = {
    "stream": "a packed stream `Start` expands into RAM: the character-set stream (run and literal bytes), the maze stream, the nibble stream of the move-delay and junction tables (`12`)",
    "shape": "a picture: one byte a scan line, bit 7 leftmost (a ghost 10 rows, Pac-Man's frames 10 rows, the star); drawn into a player-missile page (`16`)",
    "text": "ANTIC mode 2 screen codes (code + `$20` = ASCII), one byte a letter (`12`)",
    "text6": "ANTIC mode 6 screen codes: the low 6 bits are the letter, the top two the colour (`12`)",
    "bytes": "a table of bytes indexed by level, direction, ghost or step (`14`, `15`)",
    "words": "a table of 16-bit little-endian words (pointers to pictures)",
    "display list": "an ANTIC display list: mode lines, blank lines, a load-memory-scan address, a jump and wait for vertical blank, the interrupt bit (`35`)",
    "header": "the cartridge header at `$BFFA`: RUN, the flags, INIT (`07`)",
}

# the derived files: what, where, made by, format
DERIVED = [
    ("`resources/pack/assets.json`", "the asset pack: all 79 regions with their bytes and the nine decoded views (schema 2)", "`python -I tools/asset_pack.py --write`", "JSON, `47` section 3"),
    ("`resources/pack/manifest.json`", "the schema, the ROM's SHA-256 and the SHA-256 of every other file of the pack", "the same", "JSON"),
    ("`resources/pack/charset_game.png`, `maze.png`, `sprites.png`, `text.png`", "previews of the character set, the maze, the sprites and the text (not colour-accurate)", "the same", "PNG"),
    ("`resources/pack/assets.pmab`", "the asset blob the C port loads: %d entries, %s bytes", "`install_assets` (C) or `tools/make_c_assets.py`", "`PMAB`: magic, version, schema, entry count, the ROM's SHA-256, then entries (name, kind, address, size, bytes); `src/c/assets/assets.h`"),
    ("`resources/decoded/*.bin`", "the raw RAM images `Start` builds: the game character set (`$3000`), the title set (`$1808`), the maze (`$0800`), the nibble tables (`$0600`)", "`python -I tools/decode_streams.py --dump`", "raw bytes"),
    ("`resources/vectors/*.vec`", "the recorded calls of the original's routines and of whole sessions that the C is tested against (made from the Python port, which equals the ROM)", "`python -I tools/make_vectors.py`, `make_app_sequences.py`", "`PMVEC001`: header, then records of arguments, RANDOM values, the state before and after (`tools/vecfmt.py`)"),
    ("`build/` (replays, state dumps, comparison files)", "replays of games for the shell (`PMRP`), the C's per-frame state dumps, the logs of the comparisons with the ROM", "`tools/make_replay.py`, `make_rom_fuzz_replays.py`, `make_rom_edge_replays.py`, `make_rom_bot_replay.py`, `run_regression.py`", "`PMRP`: header, then one record of inputs (and RANDOM bytes) a frame (`src/c/shell/replay.h`)"),
]

RELATIONS = [
    ("`original/Pac-Man.rom`", "`tools/asset_pack.py`, `tools/decode_streams.py`", "the pack, the raw images", "extract every non-code byte, decode the streams, label and decode the tables"),
    ("the pack (`assets.json`)", "`tools/make_c_assets.py`, `install_assets`", "`assets.pmab`", "the blob the C loads; made again from the ROM by the installer, never shipped"),
    ("`assets.pmab`", "`assets_load`, `assets_install_tables`, `assets_ram_image`", "the core's tables, the maze, the character sets (`core/tables.h`)", "installed into RAM at start-up"),
    ("the OS font (`third-party/`)", "`tools/asset_pack.py`", "the pack's `font` key and the blob's `font` entry", "64 glyphs rendered to 8 x 8 for the text lines"),
    ("`analysis/palette-ntsc-measured.txt`", "`tools/make_c_palette.py`", "`src/c/render/palette.[ch]`", "the NTSC palette measured from the emulator (256 colours)"),
    ("the blob's character sets, maze, font, the palette", "`render/render.c`", "the picture of a frame", "ANTIC and GTIA as software"),
    ("the sound-chip writes of the core", "`audio/audio.c`, `pokey.c`", "PCM", "no sound is stored in the cartridge: it is code; only the start tune's two tables and two sweeps are data (`22`)"),
    ("`resources/vectors/`, replays", "the vector runner, `pacman_a8`", "the pass / fail of every equivalence test", "`52`-`56`"),
]


# in original/ but not a project material (the owner's decision of 2026-11-23: only the NTSC OS ROM is used): not in the manifest, not checked, may be deleted
UNUSED_ORIGINALS = ["Atari OS Rev B (19xx)(Atari)(PAL)[a800.zip MAME].rom"]


def ignored(path):
    """does .gitignore ignore this path?  (a small matcher for the patterns of this repository: anchored directories, `*.ext`, names)"""
    path = path.replace("\\", "/")
    with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8-sig") as fh:
        for line in fh:
            pat = line.strip()
            if not pat or pat.startswith("#") or pat.startswith("!"):
                continue
            if pat.startswith("/"):
                p = pat[1:]
                if p.endswith("/"):
                    if path.startswith(p) or path == p[:-1]:
                        return True
                elif fnmatch.fnmatch(path, p):
                    return True
            elif pat.endswith("/"):
                if ("/" + path).find("/" + pat) >= 0:
                    return True
            elif fnmatch.fnmatch(os.path.basename(path), pat):
                return True
    return False


def manifest_rows():
    out = []
    with open(os.path.join(ROOT, "docs", "original-manifest.txt"), encoding="utf-8") as fh:
        for line in fh:
            p = line.split()
            if len(p) >= 3 and len(p[0]) == 64:
                out.append((" ".join(p[2:]), int(p[1]), p[0]))                # the path may contain spaces
    return out


def facts():
    P = AP.build()
    f = {"P": P}
    f["blob"] = MA.blob(P)
    f["entries"] = MA.entries(P)
    f["kinds"] = collections.OrderedDict()
    for r in P["regions"]:
        k = f["kinds"].setdefault(r["kind"], [0, 0])
        k[0] += 1
        k[1] += r["size"]
    return f


def doc():
    f = facts()
    P = f["P"]
    L = []
    W = L.append
    W("# 62 - Resources: the Catalogue (checklist stage 96)")
    W("")
    W("GENERATED by `python -I tools/analyze_resources_docs.py --doc docs/62-resources-catalogue.md` from the asset pack (`tools/asset_pack.py`), the blob writer (`tools/make_c_assets.py`), the manifest of the originals and `.gitignore`; the formats by kind, the derived files and the relationships are tables in the tool. Tests: `tests/test_resources_docs.py`.")
    W("")
    W("Checklist stage 96: \"Catalogue extracted and reconstructed resources, their formats, origins, locations, and relationships.\" The project has **no resource that is not derived from the owner's ROM, except one third-party font**; this chapter lists them all. The format of the pack in full is `47`; the data regions one by one are `59` section 6; the data structures they fill are `60`.")
    W("")
    W("## 1. How the resources relate")
    W("")
    W("```mermaid")
    W("flowchart LR")
    W("  ROM[original/Pac-Man.rom<br/>8,192 bytes] -->|extract, decode| PACK[resources/pack<br/>assets.json + previews]")
    W("  ROM -->|expand the streams| DEC[resources/decoded<br/>raw RAM images]")
    W("  FONT[third-party font<br/>EightBit Atari-Regular] -->|render 64 glyphs| PACK")
    W("  PACK -->|make_c_assets / install_assets| BLOB[assets.pmab<br/>the blob]")
    W("  BLOB -->|assets_load, install tables| CORE[the core's tables, maze,<br/>character sets in RAM]")
    W("  BLOB --> REND[renderer: picture]")
    W("  PAL[measured NTSC palette] --> REND")
    W("  CORE --> AUD[audio: PCM from the chip writes]")
    W("  ROM -->|run on the 6502| VEC[resources/vectors<br/>recorded calls and sessions]")
    W("  VEC --> TEST[the equivalence tests]")
    W("```")
    W("")
    W("| From | By | To | What happens |")
    W("|---|---|---|---|")
    for a, b, c, d in RELATIONS:
        W("| %s | %s | %s | %s |" % (a, b, c, d))
    W("")
    W("## 2. The original materials")
    W("")
    W("Never modified, never committed (`/original/` and `*.rom` are in `.gitignore`: they are copyrighted); a read-only backup and the manifest are kept (`03`). `python -I tools/verify_originals.py` checks them.")
    W("")
    W("| File | Bytes | SHA-256 | What it is | Ignored by Git |")
    W("|---|---|---|---|---|")
    what = {"original/Pac-Man.rom": "the cartridge image: the one subject of the project (`59`)", "original/Decompilation steps.txt": "the 100-stage checklist the work follows", "original/reference-AtariAge-thread-291065.htm": "a saved web page, evidence for the ROM's identity (`03`)"}
    for path, size, sha in manifest_rows():
        desc = what.get(path) or "the Atari OS Rev B, NTSC: the reference of all measurements; the emulator needs it (not the port); the game takes only the clock, the shadow registers and two OS calls from it (`45`)"
        W("| `%s` | %s | `%s` | %s | %s |" % (path, "{:,}".format(size), sha[:16] + "...", desc, "yes" if ignored(path) else "no"))
    W("")
    W("**Only the NTSC OS ROM is used** (the owner's decision of 2026-11-23). The folder also holds `%s`, left from the PAL sound verification of 2026-11-13 (register C-24 to C-26): it is not in the manifest, not checked and not needed by anything (the port builds and runs from the cartridge ROM alone; the PAL evidence stays in `analysis/`); it may be deleted." % ", ".join(UNUSED_ORIGINALS))
    W("")
    W("## 3. Extracted from the ROM")
    W("")
    W("**%d regions, %s bytes: every byte of the cartridge that is not code** (the code is the other 5,946 bytes, `59`). Each is in the pack with its address, its kind and its bytes." % (len(P["regions"]), "{:,}".format(sum(r["size"] for r in P["regions"]))))
    W("")
    W("| Kind | Regions | Bytes | Format |")
    W("|---|---|---|---|")
    for k, (n, b) in sorted(f["kinds"].items(), key=lambda kv: -kv[1][1]):
        W("| %s | %d | %d | %s |" % (k, n, b, KIND_FORMAT.get(k, "")))
    W("")
    W("### 3.1 The pictures (%d shapes)" % len(P["sprites"]["shapes"]))
    W("")
    W("| Shape | Address | Rows |")
    W("|---|---|---|")
    for name, s in P["sprites"]["shapes"].items():
        W("| `%s` | `$%s` | %d |" % (name, s["addr"] if isinstance(s["addr"], str) else "%04X" % s["addr"], len(s["rows"])))
    W("")
    W("### 3.2 The text (%d strings)" % len(P["text"]["strings"]))
    W("")
    W("| Name | Address | ANTIC mode | Text |")
    W("|---|---|---|---|")
    for name, t in P["text"]["strings"].items():
        W("| `%s` | `$%s` | %d | %s |" % (name, t["addr"], t["mode"], t["ascii"]))
    W("")
    W("### 3.3 The packed streams")
    W("")
    W("| Stream | Address | Bytes | Expands to |")
    W("|---|---|---|---|")
    for r in P["regions"]:
        if r["kind"] == "stream":
            W("| `%s` | `$%s` | %d | %s |" % (r["name"], r["addr"], r["size"], r["note"] or ""))
    W("")
    W("## 4. Decoded and reconstructed")
    W("")
    W("| Resource | What it is | Origin | Where |")
    W("|---|---|---|---|")
    W("| Game character set | %d glyphs of 8 rows (ANTIC mode 4: 4 pixels of 2 bits a row), RAM `$%s` | expanded from the character-set stream | pack `charsets.game`, blob `charset.game` |" % (P["charsets"]["game"]["glyphs"], P["charsets"]["game"]["ram"]))
    W("| Title character set | %d glyphs in the RAM image of the title set (the stream's 160 bytes are the 20 glyphs of the PAC-MAN logo; codes from 1, glyph 0 is not in the ROM; `47`), RAM `$%s` | the title stream | pack `charsets.title` |" % (P["charsets"]["title"]["glyphs"], P["charsets"]["title"]["ram"]))
    W("| Maze | %d rows of %d cells, %d dots and %d power pellets (screen codes of the game set) | expanded from the maze stream | pack `maze`, blob `maze` |" % (P["maze"]["rows"], P["maze"]["cols"], P["maze"]["dots"], len(P["maze"]["power_pellets"])))
    W("| Start tune | %d notes of two voices (AUDF values), a step every %d jiffies, and two frequency sweeps; **the other sounds are computed by code, not stored** | tables in the ROM | pack `tunes` |" % (len(P["tunes"]["start_tune"]["audf1"]), P["tunes"]["start_tune"]["step_jiffies"]))
    W("| Colours | the 8 game colours (PCOLR0-3, COLOR0-3), the 4 title colours, the 4 display-list colours: Atari colour bytes (hue high nibble, luminance low) | tables in the ROM | pack `colours` |")
    W("| Tables | the 472 nibbles of the RAM tables at `$0600` and the nine nibble tables built from them (junction exits, move delays, routes ...) and 17 ROM tables | the nibble stream and ROM tables | pack `tables`, blob `ram_0600`, `rom_ba00` |")
    W("| Display lists | the game's and the title's, decoded into entries | ROM | pack `display_lists` |")
    W("| **The OS font** | the 64 glyphs (screen codes `$00-$3F`) the text lines use, 8 x 8, RAM `$%s`: **not in the cartridge** (ANTIC mode 6 and the status row read the OS ROM's set) | rendered from the open font below | pack `font`, blob `font` |" % P["font"]["ram"])
    W("| The NTSC palette | 256 colours as the emulator shows them | **measured** from Altirra 4.40 (`analysis/palette-ntsc-measured.txt`), not from a formula | `src/c/render/palette.[ch]` (generated) |")
    W("")
    W("## 5. Files made from them (derived, regenerated, not committed)")
    W("")
    W("All of `/resources/` and `/build/` are in `.gitignore` (%s): they are derived from the owner's ROM and rebuilt by the commands below. A port needs only the ROM and the installer." % ("both ignored" if ignored("resources/x") and ignored("build/x") else "CHECK"))
    W("")
    W("| File | What it is | Made by | Format |")
    W("|---|---|---|---|")
    for a, b, c, d in DERIVED:
        if "%d entries" in b:
            b = b % (len(f["entries"]), "{:,}".format(len(f["blob"])))
        W("| %s | %s | %s | %s |" % (a, b, c, d))
    W("")
    W("The C sources hold **no byte of the ROM**: `src/c/assets/rom_layout.[ch]` has only the layout (name, address, size, kind of the 79 regions), the ROM's SHA-256 and the font's glyphs; the tables, the maze and the pictures are installed at start-up from the owner's ROM (`47`, C-112, C-113).")
    W("")
    W("## 6. Third-party material")
    W("")
    s = P["font"]["source"]
    W("| | |")
    W("|---|---|")
    W("| What | `%s`, the Atari 8-bit character set as an outline font; its glyphs equal the Atari OS ROM's set bit for bit (provenance question, accepted by the owner on 2026-11-18, `49`) |" % os.path.basename(s["file"]))
    W("| Author | %s |" % s["author"])
    W("| Licence | %s |" % s["license"])
    W("| Source | %s, commit `%s` |" % (s["url"], s["commit"]))
    W("| SHA-256 | `%s` |" % s["sha256"])
    W("| Location | `third-party/EightBit-Atari-Fonts/` (committed with its licence and upstream README: `third-party/README.md`) |")
    W("")
    W("## 7. Evidence material")
    W("")
    W("Not resources of the game, but resources of the project: what the measurements were made from and what they produced. All local to `analysis/` (the summaries and the small logs are committed; the screenshots (`.png`, `.jpg`), the recordings (`.wav`, except `start-tune.wav`) and the raw logs are ignored by `.gitignore`: %s)." % ("checked" if ignored("analysis/x.png") and ignored("analysis/x.jpg") and ignored("analysis/x.wav") and ignored("analysis/raw-logs/x.txt") and not ignored("analysis/evidence-behaviour-summary.txt") else "CHECK"))
    W("")
    W("| Kind | Where | What |")
    W("|---|---|---|")
    W("| Evidence summaries | `analysis/evidence-*-summary.txt` | the output of each audit, quoted by the register (`OPEN-VERIFICATION.md`) |")
    W("| Recordings | `analysis/*.wav` | the emulator's audio output, the references of the sound model and the audio of the port (`22`) |")
    W("| Screenshots | `analysis/*.png`, `*.jpg` | emulator captures: the references of the renderer (`42`, C-114) |")
    W("| Raw logs | `analysis/raw-logs/` | register and memory traces of the live sessions (`32`-`35`) |")
    W("| Palette | `analysis/palette-ntsc-measured.txt` | the measured NTSC palette |")
    W("")
    W("## 8. What is not here")
    W("")
    W("No resource is stored that the ROM does not hold: the sounds of the game are code; the colours come from the tables; the NTSC palette and the OS font are the two things the cartridge does not carry and the port needs (the measured palette is project work; the font is third-party). No PAL resource exists (NTSC only, `49`).")
    return "\n".join(L) + "\n"


def main():
    text = doc()
    if "--doc" in sys.argv:
        o = sys.argv[sys.argv.index("--doc") + 1]
        with open(os.path.join(ROOT, o) if not os.path.isabs(o) else o, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("wrote", o)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
