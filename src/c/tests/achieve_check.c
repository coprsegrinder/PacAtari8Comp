/* The achievements (src/c/shell/achieve.c, sha256.c; docs/74): every event found in the game's state, the owner's rule for score and level, the sealed file, and the SHA-256 / HMAC the seal is made of.
 * Pure: the World is filled in by hand, no asset blob, no file. */
#include <stdio.h>
#include <string.h>

#include "../shell/achieve.h"
#include "../shell/sha256.h"

static int failures;

#define CHECK(cond)                                                        \
    do {                                                                   \
        if (!(cond)) {                                                     \
            printf("FAILED line %d: %s\n", __LINE__, #cond);               \
            failures++;                                                    \
        }                                                                  \
    } while (0)

static World w;

static void hex(const uint8_t *p, size_t n, char *out)
{
    size_t i;
    for (i = 0; i < n; i++) {
        sprintf(out + 2 * i, "%02x", p[i]);
    }
}

static void test_sha(void)
{
    uint8_t d[32];
    char h[80];
    static uint8_t big[1000];
    uint8_t key[131];

    sha256((const uint8_t *)"", 0, d);
    hex(d, 32, h);
    CHECK(strcmp(h, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855") == 0);
    sha256((const uint8_t *)"abc", 3, d);
    hex(d, 32, h);
    CHECK(strcmp(h, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad") == 0);
    sha256((const uint8_t *)"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq", 56, d);     /* the padding spills into a second block */
    hex(d, 32, h);
    CHECK(strcmp(h, "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1") == 0);
    memset(big, 'a', sizeof big);                                                                  /* 1000 bytes: several whole blocks and a tail */
    sha256(big, 1000, d);
    hex(d, 32, h);
    CHECK(strcmp(h, "41edece42d63e8d9bf515a9ba6932e1c20cbc9f5a5d134645adb5db1b9737ea3") == 0);
    memset(key, 0x0b, 20);                                                                         /* RFC 4231 test case 1 */
    hmac_sha256(key, 20, (const uint8_t *)"Hi There", 8, d);
    hex(d, 32, h);
    CHECK(strcmp(h, "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7") == 0);
    hmac_sha256((const uint8_t *)"Jefe", 4, (const uint8_t *)"what do ya want for nothing?", 28, d);   /* test case 2 */
    hex(d, 32, h);
    CHECK(strcmp(h, "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843") == 0);
    memset(key, 0xaa, 131);                                                                        /* test case 6: a key longer than a block */
    hmac_sha256(key, 131, (const uint8_t *)"Test Using Larger Than Block-Size Key - Hash Key First", 54, d);
    hex(d, 32, h);
    CHECK(strcmp(h, "60e431591ee0b67f0d8a26aacbf5b77f8e0bc6213728c5140546040f0ee37f54") == 0);
}

/* the game's state at a moment of play: a game in progress, play started, player 1, level 1, 3 lives, 4 power pellets, the ghosts at home (state 1, far away) */
static void play_state(int start_level, int high)
{
    int i;
    memset(&w, 0, sizeof w);
    w.GameState = 3;                                          /* the title: a game is about to start */
    w.StartLevel = (uint8_t)start_level;
    for (i = 0; i < 6; i++) {                                 /* the high score */
        w.status[0x39 + i] = 0;
    }
    for (i = 5; i >= 0 && high > 0; i--) {
        w.status[0x39 + i] = (uint8_t)(0x10 + high % 10);
        high /= 10;
    }
    w.PelletFlags[0] = w.PelletFlags[1] = 0x0F;
    for (i = 0; i < 4; i++) {
        w.GhostState[i] = 1;
        w.EntityX[i] = (uint8_t)(20 + 40 * i);
        w.EntityY[i] = 10;
    }
    w.EntityX[4] = 200;
    w.EntityY[4] = 200;
    w.GhostsEaten = 0xFF;
}

static void begin(Ach *a, uint32_t now)                       /* the title frame, then the first frames of the game */
{
    ach_step(a, &w, now);
    w.GameState = 0;
    w.PlayStarted = 1;
    ach_step(a, &w, now);
    ach_step(a, &w, now);
}

static void set_score(int player, long v)
{
    int i;
    for (i = 0; i < 6; i++) {
        w.status[(player ? 0x47 : 0x2A) + i] = 0;
    }
    for (i = 5; i >= 0 && v > 0; i--) {
        w.status[(player ? 0x47 : 0x2A) + i] = (uint8_t)(0x10 + v % 10);
        v /= 10;
    }
}

static void eat_ghost(Ach *a, int ghost, int combo_index)    /* the ghost turns to eyes; GhostsEaten counts up from $FF */
{
    w.GhostState[ghost] = 0x42;
    w.GhostsEaten = (uint8_t)combo_index;                     /* 0 after the first, 1 after the second, ... */
    ach_step(a, &w, 100);
}

static void test_basic_events(void)
{
    Ach a;
    int id;

    ach_init(&a);
    play_state(0, 0);
    begin(&a, 1000);
    CHECK(a.unlocked == 0 && a.nq == 0);
    w.DotsEatenLo[0] = 1;                                     /* a dot */
    ach_step(&a, &w, 1001);
    CHECK(ach_has(&a, ACH_FIRST_BITE) && a.dots == 1 && a.when[ACH_FIRST_BITE] == 1001);
    CHECK(ach_take(&a) == ACH_FIRST_BITE && ach_take(&a) == -1);
    w.DotsEatenLo[0] = 2;
    w.PelletFlags[0] = 0x0E;                                  /* a power pellet: the count goes up by one and the pellet flag is gone: not a dot */
    ach_step(&a, &w, 1002);
    CHECK(ach_has(&a, ACH_POWER_UP) && a.dots == 1 && ach_take(&a) == ACH_POWER_UP);
    w.DotsEatenLo[0] = 3;
    ach_step(&a, &w, 1003);
    CHECK(a.dots == 2);
    w.DotsEatenLo[0] = 0;                                     /* a new board: the count goes back to 0, nothing is eaten */
    ach_step(&a, &w, 1004);
    CHECK(a.dots == 2);
    w.DotsEatenLo[0] = 40;                                    /* a jump of many is not a dot (a state restored, not play) */
    ach_step(&a, &w, 1005);
    CHECK(a.dots == 2);
    for (id = 0; id < ACH_COUNT; id++) {
        CHECK(ach_defs[id].name != NULL && strlen(ach_defs[id].name) <= 20 && strlen(ach_defs[id].desc) <= 40 && strlen(ach_defs[id].desc) > 0);
    }
    CHECK(ach_unlocked_count(&a) == 2);
}

static void test_ghosts(void)
{
    Ach a;

    ach_init(&a);
    play_state(0, 0);
    begin(&a, 1);
    eat_ghost(&a, 0, 0);                                      /* the first ghost of a pellet */
    CHECK(ach_has(&a, ACH_GHOST_BUSTER) && !ach_has(&a, ACH_DOUBLE_TROUBLE) && a.ghosts == 1);
    CHECK(!ach_has(&a, ACH_CLOSE_CALL) && !ach_has(&a, ACH_QUICK_DRAW));     /* the others are far, and there was no pellet */
    eat_ghost(&a, 1, 1);
    CHECK(ach_has(&a, ACH_DOUBLE_TROUBLE) && !ach_has(&a, ACH_TRIPLE_THREAT));
    eat_ghost(&a, 2, 2);
    CHECK(ach_has(&a, ACH_TRIPLE_THREAT) && !ach_has(&a, ACH_GHOST_SWEEP));
    eat_ghost(&a, 3, 3);
    CHECK(ach_has(&a, ACH_GHOST_SWEEP) && a.ghosts == 4);

    ach_init(&a);                                             /* a combo that starts late: one ghost eaten, then the pellet's counter is reset: no double */
    play_state(0, 0);
    begin(&a, 1);
    eat_ghost(&a, 0, 0);
    w.GhostState[0] = 1;
    w.GhostsEaten = 0xFF;                                     /* the next pellet */
    eat_ghost(&a, 1, 0);
    CHECK(ach_has(&a, ACH_GHOST_BUSTER) && !ach_has(&a, ACH_DOUBLE_TROUBLE));

    ach_init(&a);                                             /* close call: another ghost that can catch Pac-Man within 12 units of him when one is eaten */
    play_state(0, 0);
    w.EntityX[4] = 100;
    w.EntityY[4] = 100;
    w.EntityX[3] = 108;
    w.EntityY[3] = 90;
    begin(&a, 1);
    eat_ghost(&a, 0, 0);
    CHECK(ach_has(&a, ACH_CLOSE_CALL));
    ach_init(&a);
    play_state(0, 0);
    w.EntityX[4] = 100;
    w.EntityY[4] = 100;
    w.EntityX[3] = 113;                                       /* 13 away */
    w.EntityY[3] = 100;
    w.EntityX[2] = 100;
    w.EntityY[2] = 100;
    w.GhostState[2] = 0x82;                                   /* a frightened ghost right on top of him is no danger */
    w.EntityX[1] = 101;
    w.EntityY[1] = 101;
    w.GhostState[1] = 0x42;                                   /* nor is eyes */
    begin(&a, 1);
    eat_ghost(&a, 0, 0);
    CHECK(!ach_has(&a, ACH_CLOSE_CALL));

    ach_init(&a);                                             /* quick draw: a ghost within 2 seconds of a power pellet */
    play_state(0, 0);
    begin(&a, 1);
    w.DotsEatenLo[0] = 1;
    w.PelletFlags[0] = 0x0E;
    ach_step(&a, &w, 1);
    { int i; for (i = 0; i < 100; i++) { ach_step(&a, &w, 1); } }
    eat_ghost(&a, 0, 0);
    CHECK(ach_has(&a, ACH_QUICK_DRAW));
    ach_init(&a);
    play_state(0, 0);
    begin(&a, 1);
    w.DotsEatenLo[0] = 1;
    w.PelletFlags[0] = 0x0E;
    ach_step(&a, &w, 1);
    { int i; for (i = 0; i < 130; i++) { ach_step(&a, &w, 1); } }
    eat_ghost(&a, 0, 0);
    CHECK(!ach_has(&a, ACH_QUICK_DRAW) && ach_has(&a, ACH_GHOST_BUSTER));
}

static void test_boards(void)
{
    Ach a;
    int i, b;

    ach_init(&a);                                             /* a board cleared without dying */
    play_state(0, 0);
    begin(&a, 1);
    w.LevelComplete = 0x80;
    ach_step(&a, &w, 1);
    CHECK(ach_has(&a, ACH_CLEAN_SWEEP) && !ach_has(&a, ACH_SURVIVOR));
    w.LevelComplete = 0;                                      /* three in a row */
    for (b = 1; b <= 2; b++) {
        w.Level[0] = (uint8_t)b;
        ach_step(&a, &w, 1);
        w.LevelComplete = 0x80;
        ach_step(&a, &w, 1);
        w.LevelComplete = 0;
        ach_step(&a, &w, 1);
    }
    CHECK(ach_has(&a, ACH_SURVIVOR));

    ach_init(&a);                                             /* a death on the board spoils it, and the streak */
    play_state(0, 0);
    begin(&a, 1);
    w.DeathFreeze = 96;
    ach_step(&a, &w, 1);
    w.DeathFreeze = 0;
    ach_step(&a, &w, 1);
    w.LevelComplete = 0x80;
    ach_step(&a, &w, 1);
    CHECK(!ach_has(&a, ACH_CLEAN_SWEEP));
    w.LevelComplete = 0;
    w.Level[0] = 1;
    ach_step(&a, &w, 1);
    w.LevelComplete = 0x80;                                   /* the next board is clean again, but it is the first of a new streak */
    ach_step(&a, &w, 1);
    CHECK(ach_has(&a, ACH_CLEAN_SWEEP) && !ach_has(&a, ACH_SURVIVOR));
    w.LevelComplete = 0;
    w.Level[0] = 2;
    ach_step(&a, &w, 1);
    w.DeathFreeze = 96;                                       /* a death in the middle of the streak ends it */
    ach_step(&a, &w, 1);
    w.DeathFreeze = 0;
    ach_step(&a, &w, 1);
    w.LevelComplete = 0x80;
    ach_step(&a, &w, 1);
    w.LevelComplete = 0;
    w.Level[0] = 3;
    ach_step(&a, &w, 1);
    w.LevelComplete = 0x80;
    ach_step(&a, &w, 1);
    CHECK(!ach_has(&a, ACH_SURVIVOR));

    ach_init(&a);                                             /* the fruit on three different boards (two fruits on one board count once) */
    play_state(0, 0);
    begin(&a, 1);
    for (b = 0; b < 3; b++) {
        w.Level[0] = (uint8_t)b;
        ach_step(&a, &w, 1);
        w.BonusScoreShown = 1;
        ach_step(&a, &w, 1);
        w.BonusScoreShown = 0;
        ach_step(&a, &w, 1);
        if (b == 1) {
            w.BonusScoreShown = 1;
            ach_step(&a, &w, 1);
            w.BonusScoreShown = 0;
            ach_step(&a, &w, 1);
        }
        CHECK(ach_has(&a, ACH_FRUIT_SALAD) == (b == 2));
    }

    ach_init(&a);                                             /* all four power pellets of one board */
    play_state(0, 0);
    begin(&a, 1);
    for (i = 0; i < 4; i++) {
        static const uint8_t after[4] = {0x0E, 0x0C, 0x08, 0x00};
        w.PelletFlags[0] = after[i];
        ach_step(&a, &w, 1);
        CHECK(ach_has(&a, ACH_PELLET_POPPER) == (i == 3));
    }
}

static void test_score_and_level(void)
{
    Ach a;

    ach_init(&a);                                             /* a game from level 1: the score and the level count */
    play_state(0, 5000);
    begin(&a, 1);
    set_score(0, 4990);
    ach_step(&a, &w, 1);
    CHECK(!ach_has(&a, ACH_BONUS_LIFE) && !ach_has(&a, ACH_NEW_RECORD));            /* under the high score of 5,000 */
    set_score(0, 9990);
    ach_step(&a, &w, 1);
    CHECK(!ach_has(&a, ACH_BONUS_LIFE) && ach_has(&a, ACH_NEW_RECORD));
    set_score(0, 10000);
    w.ExtraLifeFlag[0] = 1;
    ach_step(&a, &w, 1);
    CHECK(ach_has(&a, ACH_BONUS_LIFE) && !ach_has(&a, ACH_HIGH_ROLLER));
    set_score(0, 50000);
    ach_step(&a, &w, 1);
    CHECK(ach_has(&a, ACH_HIGH_ROLLER) && !ach_has(&a, ACH_SIX_FIGURES));
    set_score(0, 100000);
    ach_step(&a, &w, 1);
    CHECK(ach_has(&a, ACH_SIX_FIGURES) && !ach_has(&a, ACH_ARCADE_LEGEND));
    set_score(0, 250000);
    ach_step(&a, &w, 1);
    CHECK(ach_has(&a, ACH_ARCADE_LEGEND));
    w.Level[0] = 1;                                           /* level 2: nothing yet; 3, 5, 8, 12 */
    ach_step(&a, &w, 1);
    CHECK(!ach_has(&a, ACH_WARMING_UP));
    w.Level[0] = 2;
    ach_step(&a, &w, 1);
    CHECK(ach_has(&a, ACH_WARMING_UP) && !ach_has(&a, ACH_FIVE_ALIVE));
    w.Level[0] = 4;
    ach_step(&a, &w, 1);
    CHECK(ach_has(&a, ACH_FIVE_ALIVE) && !ach_has(&a, ACH_VETERAN));
    w.Level[0] = 7;
    ach_step(&a, &w, 1);
    CHECK(ach_has(&a, ACH_VETERAN) && !ach_has(&a, ACH_UNSTOPPABLE));
    w.Level[0] = 11;
    ach_step(&a, &w, 1);
    CHECK(ach_has(&a, ACH_UNSTOPPABLE));

    ach_init(&a);                                             /* a high score of 900 is too low to beat */
    play_state(0, 900);
    begin(&a, 1);
    set_score(0, 5000);
    ach_step(&a, &w, 1);
    CHECK(!ach_has(&a, ACH_NEW_RECORD));

    ach_init(&a);                                             /* a game started at a higher level (the Option key): no score, no level, no extra life; the rest still counts */
    play_state(4, 5000);
    w.Level[0] = 4;
    begin(&a, 1);
    set_score(0, 300000);
    w.ExtraLifeFlag[0] = 1;
    w.Level[0] = 12;
    ach_step(&a, &w, 1);
    CHECK((a.unlocked & ((1u << ACH_BONUS_LIFE) | (1u << ACH_HIGH_ROLLER) | (1u << ACH_SIX_FIGURES) | (1u << ACH_ARCADE_LEGEND) | (1u << ACH_NEW_RECORD) | (1u << ACH_WARMING_UP) | (1u << ACH_FIVE_ALIVE) |
                              (1u << ACH_VETERAN) | (1u << ACH_UNSTOPPABLE))) == 0);
    w.DotsEatenLo[0] = 1;
    ach_step(&a, &w, 1);
    CHECK(ach_has(&a, ACH_FIRST_BITE));
    w.GameState = 3;                                          /* back to the title, and a game from level 1: it counts again */
    ach_step(&a, &w, 1);
    w.StartLevel = 0;
    w.GameState = 0;
    w.Level[0] = 0;
    set_score(0, 60000);
    ach_step(&a, &w, 1);
    ach_step(&a, &w, 1);
    ach_step(&a, &w, 1);
    CHECK(ach_has(&a, ACH_HIGH_ROLLER) && !a.assisted);

    ach_init(&a);                                             /* the old level of the last game, before the new game has set its own, is not play */
    play_state(0, 0);
    w.Level[0] = 9;
    w.GameState = 0;
    w.PlayStarted = 0;
    ach_step(&a, &w, 1);
    ach_step(&a, &w, 1);
    CHECK(a.unlocked == 0);
}

static void test_game_flow(void)
{
    Ach a;
    unsigned long i;

    ach_init(&a);                                             /* a game of 15 minutes; a pause does not count; the menu stops the frames anyway */
    play_state(0, 0);
    begin(&a, 1);
    w.Paused = 1;
    for (i = 0; i < 5000; i++) {
        ach_step(&a, &w, 1);
    }
    w.Paused = 0;
    for (i = 0; i < 53900; i++) {
        ach_step(&a, &w, 1);
    }
    CHECK(!ach_has(&a, ACH_MARATHON));
    for (i = 0; i < 40; i++) {
        ach_step(&a, &w, 1);
    }
    CHECK(ach_has(&a, ACH_MARATHON));

    ach_init(&a);                                             /* games finished: the game-over countdown starting once; ten make Regular; a game left for the title is not finished */
    play_state(0, 0);
    for (i = 0; i < 10; i++) {
        w.GameState = 3;
        w.CountdownActive = 0;
        begin(&a, 1);
        ach_step(&a, &w, 1);
        w.CountdownActive = 1;
        ach_step(&a, &w, 1);
        ach_step(&a, &w, 1);
        ach_step(&a, &w, 1);
        CHECK(a.games == i + 1);
        CHECK(ach_has(&a, ACH_REGULAR) == (i == 9));
    }
    CHECK(!ach_has(&a, ACH_TWOS_COMPANY));
    w.GameState = 3;
    w.CountdownActive = 0;
    begin(&a, 1);
    w.GameState = 3;                                          /* abandoned */
    ach_step(&a, &w, 1);
    CHECK(a.games == 10);

    ach_init(&a);                                             /* a two-player game, finished */
    play_state(0, 0);
    w.TwoPlayers = 1;
    begin(&a, 1);
    w.CountdownActive = 1;
    ach_step(&a, &w, 1);
    CHECK(ach_has(&a, ACH_TWOS_COMPANY) && a.games == 1);

    ach_init(&a);                                             /* the turn goes to player 2: no events from the switch itself; each player has their own board and level */
    play_state(0, 0);
    w.TwoPlayers = 1;
    begin(&a, 1);
    w.TurnSwitchState = 2;
    w.CurrentPlayer = 1;
    w.DotsEatenLo[1] = 77;
    w.PelletFlags[1] = 0x00;
    ach_step(&a, &w, 1);
    CHECK(a.dots == 0 && !ach_has(&a, ACH_POWER_UP));
    w.TurnSwitchState = 0;
    ach_step(&a, &w, 1);
    CHECK(a.dots == 0);
    w.DotsEatenLo[1] = 78;
    ach_step(&a, &w, 1);
    CHECK(a.dots == 1);

    ach_init(&a);                                             /* the lifetime counts and their tiers */
    play_state(0, 0);
    begin(&a, 1);
    a.dots = 999;
    a.ghosts = 99;
    w.DotsEatenLo[0] = 1;
    ach_step(&a, &w, 1);
    CHECK(ach_has(&a, ACH_DOT_COLLECTOR) && !ach_has(&a, ACH_DOT_HOARDER));
    eat_ghost(&a, 0, 0);
    CHECK(ach_has(&a, ACH_GHOST_HUNTER));
    a.dots = 9999;
    w.DotsEatenLo[0] = 2;
    ach_step(&a, &w, 1);
    CHECK(ach_has(&a, ACH_DOT_HOARDER));
    {
        unsigned long c, t;
        CHECK(ach_progress(&a, ACH_DOT_HOARDER, &c, &t) && c == 10000 && t == 10000 && !ach_progress(&a, ACH_FIRST_BITE, &c, &t));
    }
}

static void test_file(void)
{
    Ach a, b, c;
    uint8_t buf[ACH_FILE_MAX], bad[ACH_FILE_MAX];
    size_t n, i;
    int k;

    ach_init(&a);
    a.unlocked = 0x05A5A5Au;
    a.dots = 12345;
    a.ghosts = 678;
    a.games = 9;
    for (k = 0; k < ACH_COUNT; k++) {
        a.when[k] = (uint32_t)(1700000000 + k);
    }
    n = ach_save_bytes(&a, buf);
    CHECK(n > 0 && n < ACH_FILE_MAX);
    ach_init(&b);
    CHECK(ach_load_bytes(&b, buf, n) == 0 && b.unlocked == a.unlocked && b.dots == 12345 && b.ghosts == 678 && b.games == 9 && b.when[5] == a.when[5] && b.when[ACH_COUNT - 1] == a.when[ACH_COUNT - 1]);
    for (i = 0; i < n; i++) {                                 /* any single byte changed: refused, and the achievements are left as they were */
        memcpy(bad, buf, n);
        bad[i] = (uint8_t)(bad[i] ^ 0x01u);
        ach_init(&c);
        c.dots = 7;
        CHECK(ach_load_bytes(&c, bad, n) != 0 && c.dots == 7 && c.unlocked == 0);
    }
    ach_init(&c);
    CHECK(ach_load_bytes(&c, buf, n - 1) != 0 && ach_load_bytes(&c, buf, 0) != 0 && ach_load_bytes(&c, buf, n + 1) != 0);
    {                                                         /* a bit beyond the last achievement, with the seal made right for it: still refused */
        Ach d;
        ach_init(&d);
        d.unlocked = 1u << 30;
        n = ach_save_bytes(&d, bad);
        CHECK(ach_load_bytes(&c, bad, n) != 0);
    }
    ach_init(&a);                                             /* the queue holds eight; the oldest first */
    play_state(0, 0);
    begin(&a, 1);
    w.DotsEatenLo[0] = 1;
    ach_step(&a, &w, 1);
    w.PelletFlags[0] = 0x0E;
    w.DotsEatenLo[0] = 2;
    ach_step(&a, &w, 1);
    CHECK(ach_take(&a) == ACH_FIRST_BITE && ach_take(&a) == ACH_POWER_UP && ach_take(&a) == -1 && a.dirty);
}

int main(void)
{
    test_sha();
    test_basic_events();
    test_ghosts();
    test_boards();
    test_score_and_level();
    test_game_flow();
    test_file();
    if (failures == 0) {
        printf("achieve_check: OK\n");
        return 0;
    }
    printf("achieve_check: %d failures\n", failures);
    return 1;
}
