/* shell/settings.h - the menu's settings kept between runs (docs/73): written as a small text file in the game's own folder (save/settings.ini), read back at the start.
 * Portable and pure: it turns a Menu into text and text into a Menu; the front end does the reading and writing of the file.  Only what is valid is taken from a file; anything else (a missing line, a
 * value that is not one of the choices, a line it does not know, a damaged file) leaves the menu's own default for that setting, so a bad file can never stop the game starting. */
#ifndef PM_SETTINGS_H
#define PM_SETTINGS_H

#include <stddef.h>

#include "menu.h"

#define SETTINGS_PATH "save/settings.ini"
#define SETTINGS_MAX_TEXT 1024

/* the text of the settings (display mode, resolution, FPS, CRT shader, vibration, light bar, volume, mute, output filter); returns its length (0 when cap is too small) */
size_t settings_format(const Menu *m, char *buf, size_t cap);
/* takes every valid setting of `text` into the menu; returns how many were taken */
int settings_parse(Menu *m, const char *text);

#endif
