/* shell/frontend.c - see frontend.h. */
#include "frontend.h"

static uint8_t stick_value(const FrontPad *p)
{
    uint8_t v = 0x0F;
    int up = p->up != 0, down = p->down != 0, left = p->left != 0, right = p->right != 0;

    if (up && down) {                /* opposite switches cannot both close on a joystick */
        up = down = 0;
    }
    if (left && right) {
        left = right = 0;
    }
    if (up) {
        v = (uint8_t)(v & ~1u);
    }
    if (down) {
        v = (uint8_t)(v & ~2u);
    }
    if (left) {
        v = (uint8_t)(v & ~4u);
    }
    if (right) {
        v = (uint8_t)(v & ~8u);
    }
    return v;
}

void front_init(Frontend *f, uint8_t start_clock)
{
    f->clock = start_clock;
    f->keydelay = 0;
}

void front_frame(Frontend *f, const FrontKeys *k, FrameInput *out)
{
    uint8_t con = 7;

    out->stick0 = stick_value(&k->pad[0]);
    out->stick1 = stick_value(&k->pad[1]);
    out->trig0 = k->pad[0].fire ? 0 : 1;
    out->trig1 = k->pad[1].fire ? 0 : 1;
    if (k->start) {
        con = (uint8_t)(con & ~1u);
    }
    if (k->select) {
        con = (uint8_t)(con & ~2u);
    }
    if (k->option) {
        con = (uint8_t)(con & ~4u);
    }
    out->console = con;
    if (k->pause) {                  /* the keyboard interrupt: CH := code, KEYDEL := 3 */
        out->key = FRONT_PAUSE_CODE;
        f->keydelay = FRONT_KEYDELAY;
    } else {                         /* the OS counts KEYDEL down once a frame */
        out->key = 0xFF;
        if (f->keydelay != 0) {
            f->keydelay--;
        }
    }
    out->keydelay = f->keydelay;
    out->clock = f->clock;
    f->clock = (uint8_t)(f->clock + 1u);
    out->drkmsk = 0xFF;
    out->colrsh = 0;
    out->nrandom = 0;
    out->random = NULL;
}
