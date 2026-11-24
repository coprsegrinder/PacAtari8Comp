/* shell/menu.h - the pause menu and the graphics options of the interactive front end (docs/68).  Portable C99 (no system call): the Windows front end (platform/win32) feeds it keys and draws what it
 * says; `ctest menu_check` drives it the same way.
 *   - the menu is a pause: while it is open the front end runs no game frame at all, so nothing of the game moves (the menu never touches the World);
 *   - F1 opens the help (what the function keys do; nothing about the other controls) from anywhere, the game and both menus; F1 or ESC closes it and goes back to where it was;
 *   - ESC opens it; in the main menu ESC resumes; in the graphics options ESC goes back to the main menu;
 *   - the graphics options are three settings: the display mode (windowed / borderless fullscreen), the resolution (the size of the area the picture may use) and the FPS (how many pictures a second are
 *     shown: the monitor's refresh rate, the game's own 59.92 ("native"), a number from 30 to 180, or as many as there are);
 *   - display_fit() is the layout: the 384 x 240 picture (1.6 : 1) at the largest whole-number scale when that uses the area well, otherwise as large as the area allows, never stretched, centred, nearest
 *     pixel (the caller draws it that way), black elsewhere. */
#ifndef PM_SHELL_MENU_H
#define PM_SHELL_MENU_H

#define MENU_PICTURE_W 384
#define MENU_PICTURE_H 240
#define MENU_FILL_PERCENT 85     /* a whole-number scale is used when its picture is at least this share of the largest picture that fits; below it the picture is scaled to fit */
#define MENU_DEFAULT_RES 5       /* 1280 x 720: the window of the picture at 3 x (1152 x 720), the size the front end always started with */
#define MENU_FPS_MONITOR (-1)    /* the FPS choices: the monitor's refresh rate (the default), */
#define MENU_FPS_NATIVE 0        /* the game's own rate, 59.92: no in-between pictures, */
#define MENU_FPS_UNCAPPED (-2)   /* as many as there are, */
                                 /* or a number of pictures a second */
#define MENU_MAX_LINES 12
#define MENU_LINE_CHARS 48

/* one entry of the resolution list: the size of the area the picture may use, and the aspect ratio it is filed under */
typedef struct MenuResolution {
    int w, h;
    const char *aspect;          /* "4:3", "16:9", "16:10", "21:9" */
} MenuResolution;

extern const MenuResolution menu_resolutions[];
extern const int menu_resolution_count;

/* the values the FPS option goes through, in order: MENU_FPS_MONITOR, MENU_FPS_NATIVE, 30 ... 180, MENU_FPS_UNCAPPED */
extern const int menu_fps_values[];
extern const int menu_fps_count;

/* which screen of the menu is shown (closed: the game runs) */
typedef enum MenuScreen { MENU_CLOSED = 0, MENU_MAIN = 1, MENU_GRAPHICS = 2, MENU_HELP = 3 } MenuScreen;
/* the keys the menu understands (the front end maps keyboard and pad onto them) */
typedef enum MenuKey { MK_UP, MK_DOWN, MK_LEFT, MK_RIGHT, MK_SELECT, MK_BACK, MK_HELP } MenuKey;

/* the menu's whole state: the screen shown, the cursor, and the two display settings */
typedef struct Menu {
    int screen;                  /* MenuScreen */
    int cursor;                  /* the item selected on the screen shown */
    int fullscreen;              /* the display mode: 1 borderless fullscreen, 0 windowed */
    int res;                     /* index into menu_resolutions, or -1: the size of the window the command line asked for (custom_w x custom_h) */
    int custom_w, custom_h;
    int fps;                     /* index into menu_fps_values (0: the monitor's refresh rate) */
    int monitor_hz;              /* the monitor's refresh rate, set by the front end (0: not known) */
    int fps_changed;             /* set when the FPS changed: the front end applies it and clears this */
    int help_from;               /* the screen the help was opened from (MENU_CLOSED: the game), where closing it goes back to */
    int quit;                    /* set by Quit Game */
    int changed;                 /* set when the display mode or the resolution changed: the front end applies it and clears this */
} Menu;

/* one line of the menu as the front end draws it */
typedef struct MenuLine {
    char text[MENU_LINE_CHARS];
    int heading;                 /* 1 for a title line, 0 for an item or a hint */
    int item;                    /* 1 when the line is an item the cursor can be on */
    int selected;                /* 1 when the cursor is on it */
} MenuLine;

/* where the picture goes in a client area, and at what scale */
typedef struct DisplayRect {
    int x, y, w, h;              /* the picture, in the client area */
    int scale_num, scale_den;    /* the scale as a ratio: whole when scale_den is 1 */
    int integer;                 /* 1 when the scale is a whole number */
} DisplayRect;

/* a closed menu with these display settings (res -1: the window size custom_w x custom_h) */
void menu_init(Menu *m, int fullscreen, int res, int custom_w, int custom_h);
/* 1 while a menu is shown: the game is paused */
int menu_is_open(const Menu *m);
void menu_key(Menu *m, MenuKey k);                 /* closed: only MK_BACK (ESC) and MK_HELP (F1) do anything, they open the menu and the help */
int menu_lines(const Menu *m, MenuLine out[MENU_MAX_LINES]);   /* the text to draw; returns the number of lines */
void menu_size(const Menu *m, int *w, int *h);     /* the selected resolution */
int menu_fps(const Menu *m);                       /* the FPS to show: MENU_FPS_NATIVE, MENU_FPS_UNCAPPED, or pictures a second (the monitor's rate for the monitor choice, 60 when it is not known) */

/* the picture in a client area of cw x ch when the picture may use the centred area aw x ah of it (aw, ah are clamped to the client) */
void display_fit(int cw, int ch, int aw, int ah, DisplayRect *r);

#endif
