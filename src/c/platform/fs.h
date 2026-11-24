/* platform/fs.h - the only door to files (docs/49, docs/51 section 2a).
 * Every path is RELATIVE to the main folder (the folder the program is started from, or the one set with pm_fs_set_root).
 * A path is refused (NULL, and pm_fs_error() says why) when it is empty, longer than PM_FS_PATH_MAX, absolute, has a drive or UNC prefix, a ':' anywhere,
 * a control character, an embedded NUL (pm_fs_open_n), an empty, "." or ".." component, a device name (CON, NUL, ...), or goes through a link that exists (symbolic link, junction).
 * Nothing else in the C code may open, remove or rename a file: tests/portability_scan.cmake enforces it. */
#ifndef PM_PLATFORM_FS_H
#define PM_PLATFORM_FS_H

#include <stddef.h>

#define PM_FS_PATH_MAX 240

typedef struct PmFile PmFile;

/* why a path or a file call is refused or fails (see pm_fs_error) */
typedef enum PmFsError {
    PM_FS_OK = 0,
    PM_FS_EMPTY,
    PM_FS_TOO_LONG,
    PM_FS_NUL,
    PM_FS_CONTROL,
    PM_FS_ABSOLUTE,
    PM_FS_DRIVE_OR_STREAM,
    PM_FS_DOT_COMPONENT,
    PM_FS_DEVICE_NAME,
    PM_FS_LINK,
    PM_FS_BAD_MODE,
    PM_FS_ROOT,
    PM_FS_OPEN_FAILED
} PmFsError;

/* the main folder; NULL or "" = the current folder.  Set once at start-up from an option, never from the environment. */
int pm_fs_set_root(const char *root);

/* mode: "rb", "wb" or "ab" (text modes are refused: the formats are binary) */
PmFile *pm_fs_open(const char *path, const char *mode);
PmFile *pm_fs_open_n(const char *path, size_t len, const char *mode);   /* pm_fs_open for a path that is not NUL-terminated: `len` bytes */
PmFsError pm_fs_error(void);                       /* the reason of the last refusal or failure */
const char *pm_fs_error_text(PmFsError e);   /* the text of a PmFsError */

/* the check alone: the rules above, and a look for links */
PmFsError pm_fs_check(const char *path, size_t len);

/* make the folder `path` (one level: its parent must exist) under the main folder; the same rules as pm_fs_open (a path outside it is refused).  0 when the folder exists afterwards (made now or already there),
 * -1 otherwise (pm_fs_error says why).  The shell makes `save/` and `logs/` with it. */
int pm_fs_mkdir(const char *path);

size_t pm_fs_read(PmFile *f, void *buf, size_t n);   /* reads up to `n` bytes; returns the count */
size_t pm_fs_write(PmFile *f, const void *buf, size_t n);   /* writes `n` bytes; returns the count */
int pm_fs_printf(PmFile *f, const char *fmt, ...);   /* a formatted write; returns the characters written, or a negative number */
int pm_fs_close(PmFile *f);   /* closes the file; 0 on success */

#endif
