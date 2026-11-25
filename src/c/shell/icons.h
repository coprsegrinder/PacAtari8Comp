/* shell/icons.h - the small pictures of the Controls page (keycaps, the pad's cross and stick, the Xbox and PlayStation buttons), drawn by the program itself into the 384 x 240 picture (docs/71).  Portable C99,
 * no image files: every icon is made of rectangles, discs, rings and lines, and the text of a keycap is drawn with the 8 x 8 font of the game (the OS character set: screen codes for ASCII $20-$5F).
 * `ctest icons_check` draws each one and checks that nothing falls outside its box. */
#ifndef PM_SHELL_ICONS_H
#define PM_SHELL_ICONS_H

#include <stdint.h>

#include "controls.h"

#define ICON_H 14                /* every icon is this tall (a row of the page is 16 lines) */

typedef struct IconCanvas {
    uint8_t *bgra;               /* w x h pixels, 4 bytes each: blue, green, red, unused */
    int w, h;
    const uint8_t *font;         /* 64 glyphs of 8 bytes: the characters $20-$5F, bit 7 = the leftmost pixel */
} IconCanvas;

/* the width in pixels of a glyph (an IC_KEY depends on its label) */
int icon_width(const ControlGlyph *g);
/* draws the glyph with its top left corner at x, y (it covers icon_width x ICON_H pixels and no others); returns its width */
int icon_draw(IconCanvas *c, int x, int y, const ControlGlyph *g);
/* the width of a whole row of glyphs, with `gap` pixels between glyphs, and its drawing */
int icon_row_width(const ControlGlyph *g, int n, int gap);
int icon_row_draw(IconCanvas *c, int x, int y, const ControlGlyph *g, int n, int gap);
/* text in the game's font (upper case; other characters are skipped); returns the width */
int icon_text(IconCanvas *c, int x, int y, const char *t, unsigned r, unsigned g, unsigned b);

#endif
