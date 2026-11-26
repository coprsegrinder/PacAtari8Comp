/* shell/controls.h - what the controls of each input device are, for the Controls page of the pause menu (docs/71).  Portable C99: the front end says which device the player is using (the keyboard or the
 * pad last used), this says what to show: one row per action, each with the keys or buttons that do it as glyphs (icons.h draws them).  The table is the one the front end really maps (win_main.c keys_now,
 * pad_menu_poll, wnd_proc); `ctest controls_check` pins it against the help text and the icons. */
#ifndef PM_SHELL_CONTROLS_H
#define PM_SHELL_CONTROLS_H

#define CONTROLS_MAX_ROWS 10
#define CONTROLS_MAX_GLYPHS 8

/* the devices the Controls page can show the controls of */
typedef enum ControlDevice { CD_KEYBOARD = 0, CD_XINPUT = 1, CD_DS4 = 2, CD_DUALSENSE = 3, CD_COUNT = 4 } ControlDevice;

/* IconId: the pictures a row can show; IC_KEY is a keycap with the text of `label` */
typedef enum IconId {
    IC_NONE = 0,
    IC_KEY,                      /* a keycap with a label */
    IC_ARROWS,                   /* the four arrow keys */
    IC_DPAD,                     /* a pad's direction cross */
    IC_STICK,                    /* a pad's left stick */
    IC_XA, IC_XB, IC_XX, IC_XY,  /* Xbox face buttons: green A, red B, blue X, yellow Y */
    IC_XMENU,                    /* the pad's right middle button (Start / Menu) */
    IC_XVIEW,                    /* the pad's left middle button (Back / View) */
    IC_CROSS, IC_CIRCLE, IC_SQUARE, IC_TRIANGLE,   /* PlayStation face buttons */
    IC_OPTIONS,                  /* DualShock 4 / DualSense Options */
    IC_SHARE,                    /* DualShock 4 Share */
    IC_CREATE,                   /* DualSense Create */
    IC_SLASH,                    /* "or" between alternatives */
    IC_PLUS,                     /* "and": pressed together */
    IC_COUNT
} IconId;

/* one picture of a row: which icon, and the text of a keycap */
typedef struct ControlGlyph {
    int icon;                    /* IconId */
    const char *label;           /* the text of an IC_KEY, else NULL */
} ControlGlyph;

/* one line of the Controls page: the action's text and the glyphs that do it */
typedef struct ControlRow {
    const char *action;          /* upper case, at most CONTROLS_ACTION_CHARS */
    int n;                       /* glyphs, 0 for a row that is only text */
    ControlGlyph g[CONTROLS_MAX_GLYPHS];
} ControlRow;

#define CONTROLS_ACTION_CHARS 20

/* the name of the device as the page's heading shows it ("KEYBOARD", "XBOX / XINPUT PAD", "DUALSHOCK 4", "DUALSENSE") */
const char *controls_device_name(int device);
/* the rows of a device, in the order shown; returns the number (at most CONTROLS_MAX_ROWS) */
int controls_rows(int device, ControlRow out[CONTROLS_MAX_ROWS]);
/* 1 when the device is a pad (a pad is told apart from the keyboard by what the front end finds connected) */
int controls_is_pad(int device);

#endif
