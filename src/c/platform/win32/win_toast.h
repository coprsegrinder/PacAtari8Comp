/* platform/win32/win_toast.h - the box that says an achievement was earned (docs/74).  It is drawn INTO the game's own picture (the 384 x 240 picture, or the same picture at the size of the window), after the game
 * and before the picture goes to the screen, by every way the program shows the picture: the plain one, the in-between pictures of the FPS option, the CRT shaders.  (Two earlier versions were windows of their own over
 * the game window: they were put on the desktop - a screen capture showed them - but the owner never saw them: a full screen picture of this kind can reach the display without the desktop compositor, which is
 * where such a window is drawn.  What is in the picture is on the display whatever the display does with the window.)
 * The style: the game's own 8 x 8 font, a dark box with a gold rim and a gold cup, "ACHIEVEMENT UNLOCKED", the name and the description, at the top left of the picture, faded in and out, 4.5 s each, queued. */
#ifndef PM_WIN_TOAST_H
#define PM_WIN_TOAST_H

#include <stddef.h>
#include <stdint.h>

/* `font` is the game's character set (64 glyphs of 8 bytes: $20-$5F) */
void wtoast_init(const uint8_t *font);
/* an achievement to show (name and description, upper case): queued, shown one after the other */
void wtoast_show(const char *name, const char *desc);
/* called often (every pass of the main loop): starts the next toast, ends the one that has run its time */
void wtoast_tick(void);
/* 1 while a toast is up (the front end shows every picture in full then, and once more when it ends, so that the box goes) */
int wtoast_active(void);
/* how long the toast on show has been up, in milliseconds (0 when none) */
unsigned long wtoast_age_ms(void);
/* draws the toast into a BGRA picture of w x h pixels (the 384 x 240 picture scaled to that size: nearest pixel), faded as it is now; returns the number of pixels it changed */
int wtoast_overlay(uint8_t *bgra, int w, int h);
/* the box in the 384 x 240 picture: where it is and how big (the test looks at that part of the screen) */
void wtoast_box(int *x, int *y, int *w, int *h);
/* counts, for the test: toasts started, and pictures it was drawn into */
int wtoast_count(void);
unsigned long wtoast_pictures(void);
void wtoast_shutdown(void);

#endif
