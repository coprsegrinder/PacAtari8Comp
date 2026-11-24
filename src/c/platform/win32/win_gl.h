/* platform/win32/win_gl.h - the CRT shaders of the Graphics Options (docs/70): an OpenGL 4.5 context in a child window, and the runtime that runs a libretro slang preset (several passes, each its own shader,
 * framebuffers, feedback of the pass before, lookup textures) on the game's picture.  OpenGL comes with Windows (opengl32.dll, loaded through wglGetProcAddress): no library is added.
 * A machine without OpenGL 4.5 gets no CRT shaders (crt_gl_open fails and says why); everything else of the program works without it. */
#ifndef PM_WIN_GL_H
#define PM_WIN_GL_H

#include <stddef.h>
#include <stdint.h>

#include <windows.h>

typedef struct CrtChain CrtChain;

/* a child window of `parent` (as large as its client area, input-less, hidden until crt_gl_show) with an OpenGL 4.5 core context; 0 on success, else the reason in `err` */
int crt_gl_open(HWND parent, char *err, size_t errcap);
void crt_gl_close(void);
int crt_gl_is_open(void);
void crt_gl_show(int visible);
void crt_gl_resize(int w, int h);                      /* the child follows the parent's client area */
const char *crt_gl_renderer(void);                     /* GL_RENDERER and GL_VERSION, for the log */

/* a preset of third-party/crt-shaders/ read, translated and compiled (the context must be open); NULL with the reason in `err` */
CrtChain *crt_chain_load(const char *preset_path, char *err, size_t errcap);
void crt_chain_free(CrtChain *c);
int crt_chain_passes(const CrtChain *c);

/* the picture through the chain: `bgra` is w x h pixels, row 0 the top; the result is drawn into the viewport (vx, vy, vw, vh: client pixels from the top left) of the window's back buffer, which is
 * cleared to black first; `frame` counts the pictures.  0 on success */
int crt_chain_render(CrtChain *c, const uint32_t *bgra, int w, int h, int vx, int vy, int vw, int vh, unsigned frame, char *err, size_t errcap);

void crt_gl_swap(void);                                /* shows what was drawn */
void crt_gl_interval(int n);                           /* the swap waits for every n-th refresh of the monitor (0: it does not wait): the pictures are then paced by the monitor itself */

/* the viewport of the last render as RGBA (row 0 the top), for the tests; call before crt_gl_swap */
int crt_gl_readback(uint8_t *rgba, int vw, int vh);

#endif
