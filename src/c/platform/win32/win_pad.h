/* platform/win32/win_pad.h - the PlayStation pads (DualShock 4, DualSense) on Windows, through the raw HID interface (docs/71).  XInput does not see them, so they are found by their USB vendor and product
 * numbers among the system's HID devices, opened for reading and writing, read with overlapped reads (never blocking), and sent their rumble and light bar colour as output reports.  The bytes of the reports
 * are in shell/padhid.c (portable, tested); this file only moves them.  Connection by USB cable or by Bluetooth; a pad that goes away is closed and found again when it returns.
 * NOT yet tried with a real pad (OV-81). */
#ifndef PM_WIN_PAD_H
#define PM_WIN_PAD_H

#include <stdint.h>

#include "../../shell/padhid.h"

#define WPAD_MAX 4

/* a line of the log (what was found, what could not be opened and why); NULL: none */
void wpad_set_log(void (*fn)(const char *line));
/* the pads present now: looks for new ones about every two seconds, reads the reports that have come, closes a pad that has gone; cheap enough to call every frame */
void wpad_poll(void);
int wpad_count(void);
/* the newest state of pad `i` (0 .. wpad_count() - 1); returns 0 when there is none yet */
int wpad_state(int i, PadKind *kind, int *bluetooth, PadState *out);
/* tells every PlayStation pad its rumble (0..255 each) and light bar colour; only what changed is sent (and a motor that is on is refreshed every 100 ms); returns the number of pads written to */
int wpad_feedback(uint8_t strong, uint8_t weak, uint8_t r, uint8_t g, uint8_t b);
/* motors off, the light bar back to a dim blue, and everything closed */
void wpad_shutdown(void);

#endif
