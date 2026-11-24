# Third-party material

Everything under `third-party/` was written by someone else and is used under the licence shipped next to it. Nothing in this folder is covered by the licence of the rest of the repository.

## EightBit Atari-Regular (font)

| | |
|---|---|
| What | `EightBit Atari-Regular.ttf`, the "real" Atari 8-bit character set as an outline font, one design unit per pixel of the 8 x 8 grid |
| Author | Steve Boswell, 2018: "Font outlines (c)2018 Steve Boswell, no other copyright is expressed or implied." (https://choccyhobnob.com) |
| Licence | **SIL Open Font License, Version 1.1**: the full text is `EightBit-Atari-Fonts/OFL.txt`; no Reserved Font Name is declared. The licence and this notice must stay with every copy of the font. |
| Source | https://github.com/a8bit/EightBit-Atari-Fonts (commit `8b5a19f41f46fc93fe58455355b5bc0c31c31bda`, 2021-01-17), file `Truetype/EightBit Atari-Regular.ttf`; downloaded 2026-11-18. The file is unmodified (sha256 `bd2b3397a1c3c6ef892e463ad821fb812ca00fb2d8768c4c30b57f7b74e5c278`). |
| Upstream README | `EightBit-Atari-Fonts/README.upstream.md`, unmodified: it carries the credits (the Atari bitmaps ripped with Recoil, converted with ImageMagick, Potrace and FontForge; the layout follows Mark Simonson's Atari font, whose glyphs the author redrew because Simonson's licence allows no modification). |
| Use here | `tools/asset_pack.py` renders the 64 glyphs for ANTIC mode 2 / 6 screen codes `$00-$3F` (ASCII `$20-$5F`) into the asset pack's `font` key (docs/47-resources.md, schema 2). The font file itself is not changed; the bitmaps are a rendering of it and are written only to the git-ignored `resources/pack/`. |

**A point about provenance, stated plainly.** `tools/check_assets.py` compares the 64 rendered glyphs with the character set in the Atari OS ROM and finds them **identical, bit for bit**. The font is therefore a faithful outline copy of the Atari OS font, made from the original Atari bitmaps. The OFL licenses Steve Boswell's font software; it cannot license anything Atari owns in the shapes themselves, and "no other copyright is expressed or implied" does not say that Atari has none. Whether the 8 x 8 pixel shapes of the OS font are protected, and whether that matters for a given release, is a decision for the project owner and was not examined by a lawyer. **Decision (2026-11-18, `docs/49-owner-decisions.md`): the owner accepted the font as it is** - the file, its licence and its credit stay in the repository - knowing the risk described here. The font was chosen because it is the openly licensed 8 x 8 Atari font that matches the original; the alternative with a plainly CC0 licence (`damianvila/font-atascii`) has different glyph shapes.

## CRT shaders (libretro slang-shaders)

| | |
|---|---|
| What | The three CRT shaders of the Graphics Options (docs/70): `crt-guest-advanced-ntsc` (19 passes, 4 lookup textures), `zfast-crt-composite` (1 pass) and `crt-aperture` (1 pass), each a **preset** (`.slangp`) with its shader files (`.slang`) and, for the first, its lookup textures (`.png`), exactly as in the repository |
| Authors and licences | `crt-guest-advanced-ntsc`: Copyright (C) 2018-2025 guest(r), **GNU GPL version 2 or (at your option) any later version**. `zfast_crt_composite`: Copyright (C) 2017 Greg Hogan (SoltanGris42), with the blur of metallic77, **GPL version 2 or later**. `crt-aperture`: "CRT Shader by EasyMode, License: GPL" (the file does not say which version). The licence text of the GPL version 2 is `crt-shaders/COPYING-GPL-2.0.txt`; the repository itself has no licence file of its own (`crt-shaders/slang-shaders-README.md` is its README) |
| Source | https://github.com/libretro/slang-shaders at commit `02bf134555c4595bd6b69be89feaff923da83754` (2026-11-20); downloaded 2026-11-24 with `tools/fetch_crt_shaders.py` (the owner gave permission to download, implement and document them). Every file's URL path and SHA-256 is in `crt-shaders/SOURCES.txt` (`python -I tools/fetch_crt_shaders.py --check` compares the files with it). The files are **unmodified** |
| Use here | The program reads them from this folder when the player chooses a CRT shader (`platform/win32/win_gl.c` runs the passes on OpenGL 4.5; `render/slang.c` turns each shader's Vulkan-style GLSL into GLSL for OpenGL; `render/png.c` reads the lookup textures). The program's source does not contain any of their code: they are data files. **Decision of the owner (2026-11-24): the shaders are free to use, and are included with credit to their authors and the information where they were downloaded from** (this table, `crt-shaders/README.md`, `crt-shaders/SOURCES.txt`, `NOTICE`); the files are kept exactly as downloaded, with their own licence headers |
