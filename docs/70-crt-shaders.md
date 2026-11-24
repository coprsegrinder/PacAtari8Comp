# 70 - The CRT shaders (an addition to stage J)

Asked for by the owner on 2026-11-24, with permission to download, implement and document three shaders of the libretro project: **crt-guest-advanced-ntsc**, **zfast-crt-composite** and **crt-aperture**. The Graphics Options (docs/68) get a fourth setting, **CRT SHADER**: Off (the default), CRT-GUEST-ADVANCED-NTSC, ZFAST-CRT-COMPOSITE, CRT-APERTURE. The game does not change: the shaders only decide how the picture the game made is drawn on the screen. Source: `src/c/render/slang.[ch]` (presets and shaders, portable), `src/c/render/png.[ch]` (the lookup textures, portable), `src/c/platform/win32/win_gl.[ch]` (OpenGL and the passes), `src/c/platform/win32/win_main.c` (the menu and the window), `src/c/shell/menu.[ch]` (the option); the shaders themselves are **third-party files**, `third-party/crt-shaders/` (below).

## 1. What the player gets

| | |
|---|---|
| **Where** | Graphics Options, the last item: `CRT SHADER: < OFF >`; Left / Right change it, as the other items |
| **Off** | the picture as before (GDI, docs/67); nothing of OpenGL is started |
| **crt-guest-advanced-ntsc** | guest.r's advanced CRT: the NTSC colour signal (the artifact colours of a composite picture) is made and decoded, afterglow of the phosphors, halation and bloom, scanlines, a shadow mask, a sharpened picture; 19 passes, 4 lookup textures |
| **zfast-crt-composite** | a fast shader: composite (YIQ) blur and a little curvature, scanlines that vary with brightness, a monochrome aperture mask; 1 pass |
| **crt-aperture** | EasyMode's aperture-grille CRT: scanlines and an aperture grille; 1 pass |
| **Combined with** | every FPS choice (the in-between pictures are made first, the shader draws them), every display mode and resolution (the shader draws into the picture's rectangle of docs/68), the menu and the help (they are drawn into the picture, so the shader draws them too, like a menu on a CRT) |
| **When it cannot** | the machine has no OpenGL 4.5 (a very old driver or a virtual machine), or the shader files are not in `third-party/crt-shaders/`: the item goes back to OFF and says `NOT AVAILABLE`, `logs/shell.log` says why; nothing else is affected |

The three presets are used **as their authors made them**, with their own default parameters (no parameter menu: not asked for).

## 2. How it works

OpenGL comes with Windows (`opengl32.dll`); the program asks it for a 4.5 core context through `wglCreateContextAttribsARB` and loads the functions it needs with `wglGetProcAddress`. **No library is added** (the program still links `user32 gdi32 ole32 uuid mmdevapi`, now with `opengl32`). The context is in a **child window** of the game's window (input-less, as large as its client area, shown only while a shader is on), so the plain GDI path of the other modes is untouched.

The presets are in the **slang** format of RetroArch: Vulkan-style GLSL. `render/slang.c` reads the preset (passes, filters, scale types, framebuffer formats, aliases, lookup textures) and turns each shader into GLSL 450 for OpenGL by text changes only: the vertex and fragment parts are separated (`#pragma stage`), the `#pragma parameter` lines are read (name, default, range), `set =` is dropped from the `layout` qualifiers, the **push-constant block becomes a second uniform block** (binding 1; the `UBO` block keeps binding 0), and the sampler names and bindings are listed. `win_gl.c` then does what RetroArch's filter chain does for these presets:

- one program per pass; the **uniform blocks are filled by name** from what OpenGL reports (`MVP`, `SourceSize`, `OriginalSize`, `OutputSize`, `FinalViewportSize`, `FrameCount`, `FrameDirection`, the `<name>Size` of every texture, and the parameters with the default of the shader);
- the **textures a pass reads** by name: `Source` (the pass before), `Original` (the game's picture), `OriginalHistory0`, `PassN`, the pass **aliases** (`StockPass`, `NPass1`, `LinearizePass`, ...), `PassFeedbackN` and `<alias>Feedback` (the pass's own picture of the frame before, two textures kept), and the lookup textures (PNG files read by `render/png.c`, which has an inflate of its own);
- the **size of every pass's picture**: relative to its input (`source`), to the viewport, or absolute; **float framebuffers** (`RGBA16F`) and the `#pragma format` of a shader; **mip levels** for the passes that ask (`mipmap_input`), made with `glGenerateMipmap`; **filter and wrap** (clamp to border) as sampler objects; the last pass into the window's viewport (the picture's rectangle, upside down as OpenGL has it);
- what it does **not** do, because the three presets do not need it: `OriginalHistory1` and older, `srgb_framebuffer` (treated as plain 8 bit), `#include`, `frame_count_mod`, `#reference`, user parameters in the menu. A preset that needs one of them is refused with a message.

**The picture the shaders get is the game's own 384 x 240** (the Atari's pixels, the size these shaders were made for), in BGRA, one texture upload a picture. With an FPS choice other than Native the in-between pictures (docs/69) are made at 384 x 240 for the shader, so **an object moves in whole game pixels and whole lines** with a shader on (without one it moves in fractions of a pixel at the size shown): a wider source (tried: every pixel three times across) changes what the shaders do (their blur and mask are in texels, and the guest shader's geometry follows the width), so it was not used.

## 3. How it was checked

| Check | Where | Result |
|---|---|---|
| The three presets read (19 / 1 / 1 passes, 4 lookup textures, the last pass the viewport), every one of the 21 shaders turned into GLSL (no `push_constant`, no `set =`, a `Push` block at binding 1 and a `UBO` block at binding 0, the two stages, the samplers listed), the parameters (246 over the passes of the guest preset; 10 for zfast with `WARP` 0.03, range 0 to 0.3), the preset's keys, an `#include` and a missing stage refused; the PNG reader (inflate of stored and fixed blocks, the four 1024 x 32 lookup tables of the guest preset: 29,000 to 32,000 changes of colour along each) | `ctest slang_check` | pass |
| **Every pass compiles and links on the real driver and runs**, on a frame of play, windowed (1152 x 720) and in borderless fullscreen at the monitor's size (2304 x 1440): the pictures are lit (10 to 22 % of the pixels), no OpenGL error; compile times 1 to 22 ms (the driver's cache) | `pacman_a8_play --crttest`, `tools/check_front_end.py` | 3 of 3, gcc and clang |
| **The picture read back from the OpenGL window** after each shader was chosen **through the menu in the running game** (with the 180 pictures a second of the FPS option): 1152 x 720, 15 to 21 % of the pixels lit, 19 to 24 (of 255) different from the plain picture, no failed picture; and OFF puts the plain picture back (no chain, the OpenGL window hidden) | `pacman_a8_play --menutest --windowed` | 4 of 4, 98 checks, each compiler |
| **Looked at** (the pictures read back, in `analysis/evidence-crt-*.png`): all three show the scanlines, the mask or grille and the glow of a CRT, the maze, the dots, the four ghosts and the status rows in the right colours and places; the guest shader has the strongest glow and a slight colour fringe of the NTSC signal | by eye, by the model that wrote this | see the pictures |
| The speed: with a shader on at 180 pictures a second, borderless fullscreen 2560 x 1440 (`--trace`): 170 to 176 pictures a second, the game at 59.85 frames/s, never going back; the shaders cost the CPU nothing noticeable (the GPU does the work) | `tools/analyze_trace.py` | see left |
| The game is the same: a game recorded through the menu (with the CRT shaders chosen in it) replays headless to the same state, run, video and audio digests | `tools/check_front_end.py` | equal |

## 4. The licences, and a decision for the owner

The shader files stay **exactly as in the libretro repository** (`tools/fetch_crt_shaders.py` downloads them from commit `02bf134555c4595bd6b69be89feaff923da83754` and records every file's SHA-256 in `third-party/crt-shaders/SOURCES.txt`; `.gitattributes` keeps their bytes as they are). **Authors and licences**: guest.r (crt-guest-advanced-ntsc, 2018-2025) and Greg Hogan / SoltanGris42 with metallic77 (zfast_crt_composite, 2017) **GNU GPL version 2 or later**; EasyMode (crt-aperture) **"License: GPL"** without a version. The GPL text is `third-party/crt-shaders/COPYING-GPL-2.0.txt`. The rest of the project is MIT.

The C code written for this addition (the slang reader, the translation, the OpenGL runtime, the PNG reader) is the port's own and contains **none of the shaders' code**: it reads them from files when the player chooses one. The usual reading of the GPL is that distributing separate GPL files next to a program (mere aggregation), and a program that reads and runs them as data, does not make the program a copy of them; **embedding the shaders in the executable, or distributing the whole as one work, would make that combination GPL**. NOTICE and `third-party/README.md` say so. This was **not examined by a lawyer** and is the owner's decision (it was open at stage 99 whether the release carries third-party material; OV-79). If the owner prefers not to ship GPL files at all, `third-party/crt-shaders/` can be left out of the release and the item then says `NOT AVAILABLE`: nothing else changes.

## 5. Limits (OV-79)

- **One machine, one graphics card**: NVIDIA GeForce RTX 5070, OpenGL 4.5.0 NVIDIA 621.24, Windows 11. Other drivers (AMD, Intel) may reject GLSL that this driver takes (`#define gl_FragCoord` in the guest shaders is the likely one); the item then says `NOT AVAILABLE` and the log has the compiler's message. Not tried.
- **OpenGL 4.5 is required** (the shaders use `layout(binding = N)` on samplers and uniform blocks and `#version 450`); older hardware cannot use the CRT shaders.
- **Looked at in stills only**: the pictures were read back and looked at; the look of the motion (afterglow of the guest shader on a moving ghost, the flicker of scanlines at 180 pictures a second) was not.
- **Whole game pixels with a shader** (section 2); the parameters of the presets cannot be changed in the program.
- **The first pass of a guest-shader frame after a change of size makes new framebuffers** (about 20 of them at the viewport's size): a hitch of a few frames when the window is resized or the display mode is changed while the shader is on (the first picture after choosing it, in fullscreen, took 55 to 65 ms).
- **The GPL question** of section 4.
- sRGB framebuffers, `OriginalHistory1` and older, `#include` and `#reference` are not implemented (the three presets do not use them).
