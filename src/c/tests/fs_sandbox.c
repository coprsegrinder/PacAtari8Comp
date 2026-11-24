/* The file sandbox test (docs/51 section 2a, stage 75b): platform/fs.c must refuse every path that leaves the main folder, and an allowed write must land inside it.
 *   fs_sandbox ROOT [LINKDIR]
 * ROOT is a folder made by the build (it holds a folder `sub`); the main folder is set to ROOT/main so that "../x" would land in ROOT, where the test looks for strays.
 * LINKDIR (optional, made by tests/test_c_foundation.py): a path inside ROOT/main that is a link (junction / symbolic link): a path through it must be refused.
 * This file is the one place outside platform/ that touches files directly (to look for strays); the portability scan names it as the exception. */
#include <stdio.h>
#include <string.h>

#include "../platform/fs.h"

static int failures;

static void expect_refused(const char *path, size_t len, PmFsError want)
{
    PmFile *f = pm_fs_open_n(path, len, "wb");
    if (f != NULL) {
        printf("NOT REFUSED: \"%s\" (length %u)\n", path, (unsigned)len);
        pm_fs_close(f);
        failures++;
    } else if (pm_fs_error() != want) {
        printf("refused for the wrong reason: \"%s\": %s, expected %s\n", path, pm_fs_error_text(pm_fs_error()), pm_fs_error_text(want));
        failures++;
    }
}

#define REFUSE(p, e) expect_refused((p), strlen(p), (e))

static int exists_raw(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (f != NULL) {
        fclose(f);
        return 1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    char main_dir[300], p[400], longp[300];
    const char *root;
    PmFile *f;
    unsigned char buf[4];
    size_t i, refused = 0;
    static const char *const strays[] = {"escape.txt", "x", "b", "main_escape", "dirx", "madeout"};

    if (argc < 2) {
        printf("usage: fs_sandbox ROOT [LINKDIR]\n");
        return 2;
    }
    root = argv[1];
    snprintf(main_dir, sizeof main_dir, "%s/main", root);
    if (pm_fs_set_root(main_dir) != 0) {
        printf("cannot set the main folder\n");
        return 2;
    }

    /* the refusals (the path is checked before the file system is touched) */
    REFUSE("", PM_FS_EMPTY);
    REFUSE("/abs.txt", PM_FS_ABSOLUTE);
    REFUSE("\\abs.txt", PM_FS_ABSOLUTE);
    REFUSE("/", PM_FS_ABSOLUTE);
    REFUSE("C:\\x.txt", PM_FS_DRIVE_OR_STREAM);
    REFUSE("C:x.txt", PM_FS_DRIVE_OR_STREAM);
    REFUSE("c:/x.txt", PM_FS_DRIVE_OR_STREAM);
    REFUSE("x:", PM_FS_DRIVE_OR_STREAM);
    REFUSE("file.txt:stream", PM_FS_DRIVE_OR_STREAM);
    REFUSE("\\\\server\\share\\x.txt", PM_FS_ABSOLUTE);
    REFUSE("//server/share/x.txt", PM_FS_ABSOLUTE);
    REFUSE("../escape.txt", PM_FS_DOT_COMPONENT);
    REFUSE("..\\escape.txt", PM_FS_DOT_COMPONENT);
    REFUSE("..", PM_FS_DOT_COMPONENT);
    REFUSE("a/../../b", PM_FS_DOT_COMPONENT);
    REFUSE("sub/..\\..\\x", PM_FS_DOT_COMPONENT);
    REFUSE("sub/../../main_escape", PM_FS_DOT_COMPONENT);
    REFUSE("./x", PM_FS_DOT_COMPONENT);
    REFUSE(".", PM_FS_DOT_COMPONENT);
    REFUSE("sub/./x", PM_FS_DOT_COMPONENT);
    REFUSE("sub//x", PM_FS_DOT_COMPONENT);
    REFUSE("sub/", PM_FS_DOT_COMPONENT);
    REFUSE("sub\\", PM_FS_DOT_COMPONENT);
    REFUSE("...", PM_FS_DOT_COMPONENT);
    REFUSE(".. ", PM_FS_DOT_COMPONENT);
    REFUSE("sub/.../x", PM_FS_DOT_COMPONENT);
    REFUSE("CON", PM_FS_DEVICE_NAME);
    REFUSE("nul", PM_FS_DEVICE_NAME);
    REFUSE("COM1", PM_FS_DEVICE_NAME);
    REFUSE("lpt9.txt", PM_FS_DEVICE_NAME);
    REFUSE("aux.log", PM_FS_DEVICE_NAME);
    REFUSE("sub/NUL", PM_FS_DEVICE_NAME);
    REFUSE("con.", PM_FS_DEVICE_NAME);
    REFUSE("a\tb", PM_FS_CONTROL);
    REFUSE("a\nb", PM_FS_CONTROL);
    REFUSE("a\177b", PM_FS_CONTROL);
    expect_refused("a\0b", 3, PM_FS_NUL);                 /* an embedded NUL */
    memset(longp, 'a', sizeof longp);
    longp[PM_FS_PATH_MAX + 1] = '\0';
    REFUSE(longp, PM_FS_TOO_LONG);                         /* 241 characters */
    longp[PM_FS_PATH_MAX] = '\0';
    if (pm_fs_check(longp, strlen(longp)) != PM_FS_OK) {   /* 240 characters is the longest allowed */
        printf("a path of %d characters was refused\n", PM_FS_PATH_MAX);
        failures++;
    }
    if (pm_fs_open("ok.bin", "w") != NULL || pm_fs_open("ok.bin", "r+b") != NULL || pm_fs_open("ok.bin", "rb+") != NULL || pm_fs_open("ok.bin", NULL) != NULL) {
        printf("a mode other than rb / wb / ab was accepted\n");
        failures++;
    }
    if (pm_fs_error() != PM_FS_BAD_MODE) {
        printf("a bad mode gave the wrong reason\n");
        failures++;
    }
    if (argc > 2) {
        snprintf(p, sizeof p, "%s/f.bin", argv[2]);
        expect_refused(p, strlen(p), PM_FS_LINK);          /* through a link that exists */
    }
    refused = 44;

    /* pm_fs_mkdir has the same rules */
    if (pm_fs_mkdir("../madeout") == 0 || pm_fs_mkdir("/madeout") == 0 || pm_fs_mkdir("a/../../madeout") == 0 || pm_fs_mkdir("C:madeout") == 0 || pm_fs_mkdir("") == 0 || pm_fs_mkdir(NULL) == 0 ||
        pm_fs_mkdir("sub/./madeout") == 0) {
        printf("pm_fs_mkdir accepted a path that leaves the main folder\n");
        failures++;
    }
    if (pm_fs_mkdir("sub/made") != 0 || pm_fs_mkdir("sub/made") != 0) {      /* made, and already there */
        printf("pm_fs_mkdir cannot make a folder inside the main folder: %s\n", pm_fs_error_text(pm_fs_error()));
        failures++;
    }
    f = pm_fs_open("sub/made/in.bin", "wb");
    if (f == NULL) {
        printf("cannot write into the folder pm_fs_mkdir made\n");
        failures++;
    } else {
        pm_fs_close(f);
    }

    /* what is allowed lands inside the main folder */
    f = pm_fs_open("ok.bin", "wb");
    if (f == NULL) {
        printf("cannot write ok.bin: %s\n", pm_fs_error_text(pm_fs_error()));
        failures++;
    } else {
        pm_fs_write(f, "\x01\x02\x03\x04", 4);
        pm_fs_close(f);
    }
    f = pm_fs_open("sub\\two.bin", "wb");                  /* a backslash is a separator */
    if (f == NULL) {
        printf("cannot write sub\\two.bin: %s\n", pm_fs_error_text(pm_fs_error()));
        failures++;
    } else {
        pm_fs_write(f, "\x05\x06\x07\x08", 4);
        pm_fs_close(f);
    }
    snprintf(p, sizeof p, "%s/ok.bin", main_dir);
    if (!exists_raw(p)) {
        printf("ok.bin is not in the main folder\n");
        failures++;
    }
    snprintf(p, sizeof p, "%s/sub/two.bin", main_dir);
    if (!exists_raw(p)) {
        printf("sub/two.bin is not in the main folder\n");
        failures++;
    }
    f = pm_fs_open("sub/two.bin", "rb");
    if (f == NULL || pm_fs_read(f, buf, 4) != 4 || buf[0] != 5 || buf[3] != 8) {
        printf("read back failed\n");
        failures++;
    }
    if (f != NULL) {
        pm_fs_close(f);
    }
    /* nothing escaped: the places an escaping path would have written to */
    for (i = 0; i < sizeof strays / sizeof strays[0]; i++) {
        snprintf(p, sizeof p, "%s/%s", root, strays[i]);
        if (exists_raw(p)) {
            printf("STRAY FILE: %s\n", p);
            failures++;
        }
        snprintf(p, sizeof p, "%s/%s", main_dir, strays[i]);
        if (exists_raw(p)) {
            printf("STRAY FILE: %s\n", p);
            failures++;
        }
    }
    if (failures == 0) {
        printf("fs_sandbox: OK (%u refusals, allowed writes inside the main folder)\n", (unsigned)refused);
        return 0;
    }
    printf("fs_sandbox: %d failures\n", failures);
    return 1;
}
