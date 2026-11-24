# The CRT shaders (docs/70)

Files of the libretro `slang-shaders` repository, unmodified, at commit `02bf134555c4595bd6b69be89feaff923da83754`. The paths are those of the repository (`crt/...`). **Do not edit them**: `python -I tools/fetch_crt_shaders.py --check` compares every file with the SHA-256 in `SOURCES.txt`.

| Preset | Shaders | Author and licence |
|---|---|---|
| `crt/crt-guest-advanced-ntsc.slangp` | 19 passes: `crt/shaders/guest/advanced/*.slang`, `.../ntsc/*.slang`, `crt/shaders/guest/hd/*.slang`, the lookup textures `.../lut/*.png` | Copyright (C) 2018-2025 guest(r), GNU GPL version 2 or later |
| `crt/zfast-crt-composite.slangp` | `crt/shaders/zfast_crt/zfast_crt_composite.slang` | Copyright (C) 2017 Greg Hogan (SoltanGris42), blur by metallic77, GNU GPL version 2 or later |
| `crt/crt-aperture.slangp` | `crt/shaders/crt-aperture.slang` | CRT Shader by EasyMode, "License: GPL" (version not stated) |

The licence text is `COPYING-GPL-2.0.txt` (from https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt). `slang-shaders-README.md` is the repository's own README. The files are data that the program reads at run time; see `../README.md` and `docs/70-crt-shaders.md` for what that means and for how they are run.
