/* shell/controls.c - the rows of the Controls page (docs/71); see controls.h. */
#include <string.h>

#include "controls.h"

#define KEY(l) {IC_KEY, l}
#define IC(i) {i, NULL}

const char *controls_device_name(int device)
{
    switch (device) {
    case CD_KEYBOARD: return "KEYBOARD";
    case CD_XINPUT: return "XBOX / XINPUT PAD";
    case CD_DS4: return "DUALSHOCK 4";
    case CD_DUALSENSE: return "DUALSENSE";
    default: return "";
    }
}

int controls_is_pad(int device)
{
    return device == CD_XINPUT || device == CD_DS4 || device == CD_DUALSENSE;
}

static const ControlRow keyboard_rows[] = {
    {"MOVE", 3, {IC(IC_ARROWS), IC(IC_SLASH), KEY("WASD")}},
    {"FIRE", 7, {KEY("CTRL"), IC(IC_SLASH), KEY("Z"), IC(IC_SLASH), KEY("X"), IC(IC_SLASH), KEY("ENTER")}},
    {"START GAME", 3, {KEY("F2"), IC(IC_SLASH), KEY("ENTER")}},
    {"1 OR 2 PLAYERS", 1, {KEY("F3")}},
    {"STARTING LEVEL", 1, {KEY("F4")}},
    {"PAUSE", 3, {KEY("SPACE"), IC(IC_SLASH), KEY("P")}},
    {"PAUSE MENU", 1, {KEY("ESC")}},
    {"HELP", 1, {KEY("F1")}},
    {"FULL SCREEN", 5, {KEY("F11"), IC(IC_SLASH), KEY("ALT"), IC(IC_PLUS), KEY("ENTER")}},
};

static const ControlRow xinput_rows[] = {
    {"MOVE", 3, {IC(IC_DPAD), IC(IC_SLASH), IC(IC_STICK)}},
    {"FIRE", 3, {IC(IC_XA), IC(IC_SLASH), IC(IC_XB)}},
    {"START GAME", 1, {IC(IC_XMENU)}},
    {"1 OR 2 PLAYERS", 1, {IC(IC_XVIEW)}},
    {"STARTING LEVEL", 3, {IC(IC_XX), IC(IC_SLASH), IC(IC_XY)}},
    {"PAUSE MENU", 3, {IC(IC_XMENU), IC(IC_PLUS), IC(IC_XVIEW)}},
    {"IN MENUS: OK/BACK", 3, {IC(IC_XA), IC(IC_SLASH), IC(IC_XB)}},
    {"2ND PAD: PLAYER 2", 0, {{0, NULL}}},
};

static const ControlRow ds4_rows[] = {
    {"MOVE", 3, {IC(IC_DPAD), IC(IC_SLASH), IC(IC_STICK)}},
    {"FIRE", 3, {IC(IC_CROSS), IC(IC_SLASH), IC(IC_CIRCLE)}},
    {"START GAME", 1, {IC(IC_OPTIONS)}},
    {"1 OR 2 PLAYERS", 1, {IC(IC_SHARE)}},
    {"STARTING LEVEL", 3, {IC(IC_SQUARE), IC(IC_SLASH), IC(IC_TRIANGLE)}},
    {"PAUSE MENU", 3, {IC(IC_OPTIONS), IC(IC_PLUS), IC(IC_SHARE)}},
    {"IN MENUS: OK/BACK", 3, {IC(IC_CROSS), IC(IC_SLASH), IC(IC_CIRCLE)}},
    {"2ND PAD: PLAYER 2", 0, {{0, NULL}}},
};

static const ControlRow dualsense_rows[] = {
    {"MOVE", 3, {IC(IC_DPAD), IC(IC_SLASH), IC(IC_STICK)}},
    {"FIRE", 3, {IC(IC_CROSS), IC(IC_SLASH), IC(IC_CIRCLE)}},
    {"START GAME", 1, {IC(IC_OPTIONS)}},
    {"1 OR 2 PLAYERS", 1, {IC(IC_CREATE)}},
    {"STARTING LEVEL", 3, {IC(IC_SQUARE), IC(IC_SLASH), IC(IC_TRIANGLE)}},
    {"PAUSE MENU", 3, {IC(IC_OPTIONS), IC(IC_PLUS), IC(IC_CREATE)}},
    {"IN MENUS: OK/BACK", 3, {IC(IC_CROSS), IC(IC_SLASH), IC(IC_CIRCLE)}},
    {"2ND PAD: PLAYER 2", 0, {{0, NULL}}},
};

int controls_rows(int device, ControlRow out[CONTROLS_MAX_ROWS])
{
    const ControlRow *src;
    int n;

    switch (device) {
    case CD_XINPUT: src = xinput_rows; n = (int)(sizeof xinput_rows / sizeof xinput_rows[0]); break;
    case CD_DS4: src = ds4_rows; n = (int)(sizeof ds4_rows / sizeof ds4_rows[0]); break;
    case CD_DUALSENSE: src = dualsense_rows; n = (int)(sizeof dualsense_rows / sizeof dualsense_rows[0]); break;
    default: src = keyboard_rows; n = (int)(sizeof keyboard_rows / sizeof keyboard_rows[0]); break;
    }
    memcpy(out, src, sizeof(ControlRow) * (size_t)n);
    return n;
}
