/* platform/fs.c - see fs.h.  The only file of the port that opens files. */
#if !defined(_WIN32) && !defined(_POSIX_C_SOURCE)
#define _POSIX_C_SOURCE 200809L          /* lstat, S_ISLNK and mkdir of <sys/stat.h> are not declared by a strict -std=c99 build of glibc without it (found by the Linux build, stage 88) */
#endif
#include "fs.h"

#include <ctype.h>
#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#include <windows.h>
#else
#include <sys/stat.h>
#endif

struct PmFile {
    FILE *fp;
};

#define FULL_MAX (PM_FS_PATH_MAX * 3)

static char root_path[PM_FS_PATH_MAX * 2];
static PmFsError last_error = PM_FS_OK;

const char *pm_fs_error_text(PmFsError e)
{
    switch (e) {
    case PM_FS_OK: return "ok";
    case PM_FS_EMPTY: return "empty path";
    case PM_FS_TOO_LONG: return "path too long";
    case PM_FS_NUL: return "embedded NUL";
    case PM_FS_CONTROL: return "control character in path";
    case PM_FS_ABSOLUTE: return "absolute path";
    case PM_FS_DRIVE_OR_STREAM: return "drive, UNC or stream (':') in path";
    case PM_FS_DOT_COMPONENT: return "empty, '.' or '..' component";
    case PM_FS_DEVICE_NAME: return "device name";
    case PM_FS_LINK: return "path goes through a link";
    case PM_FS_BAD_MODE: return "mode not allowed";
    case PM_FS_ROOT: return "bad main folder";
    case PM_FS_OPEN_FAILED: return "open failed";
    }
    return "?";
}

PmFsError pm_fs_error(void)
{
    return last_error;
}

int pm_fs_set_root(const char *root)
{
    size_t n;
    if (root == NULL || root[0] == '\0') {
        root_path[0] = '\0';
        return 0;
    }
    n = strlen(root);
    if (n >= sizeof root_path - 2) {
        last_error = PM_FS_ROOT;
        return -1;
    }
    memcpy(root_path, root, n + 1);
    while (n > 0 && (root_path[n - 1] == '/' || root_path[n - 1] == '\\')) {
        root_path[--n] = '\0';
    }
    return 0;
}

static int ieq(const char *a, size_t n, const char *b)
{
    size_t i;
    if (strlen(b) != n) {
        return 0;
    }
    for (i = 0; i < n; i++) {
        if (toupper((unsigned char)a[i]) != toupper((unsigned char)b[i])) {
            return 0;
        }
    }
    return 1;
}

static int is_device(const char *c, size_t n)
{
    static const char *const names[] = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", "CLOCK$"};
    size_t i, stem = 0;
    while (stem < n && c[stem] != '.') {
        stem++;
    }
    for (i = 0; i < sizeof names / sizeof names[0]; i++) {
        if (ieq(c, stem, names[i])) {
            return 1;
        }
    }
    if (stem == 4 && (ieq(c, 3, "COM") || ieq(c, 3, "LPT")) && c[3] >= '1' && c[3] <= '9') {
        return 1;
    }
    return 0;
}

static int is_link(const char *full)
{
#if defined(_WIN32)
    DWORD a = GetFileAttributesA(full);
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_REPARSE_POINT) != 0;
#else
    struct stat st;
    return lstat(full, &st) == 0 && S_ISLNK(st.st_mode);
#endif
}

PmFsError pm_fs_check(const char *path, size_t len)
{
    size_t i, start, k;
    char prefix[FULL_MAX];

    if (path == NULL || len == 0) {
        return PM_FS_EMPTY;
    }
    if (len > PM_FS_PATH_MAX) {
        return PM_FS_TOO_LONG;
    }
    for (i = 0; i < len; i++) {
        unsigned char c = (unsigned char)path[i];
        if (c == 0) {
            return PM_FS_NUL;
        }
        if (c < 0x20 || c == 0x7F) {
            return PM_FS_CONTROL;
        }
        if (c == ':') {
            return PM_FS_DRIVE_OR_STREAM;
        }
    }
    if (path[0] == '/' || path[0] == '\\') {
        return PM_FS_ABSOLUTE;
    }
    /* components: '/' and '\' both separate */
    start = 0;
    for (i = 0; i <= len; i++) {
        if (i == len || path[i] == '/' || path[i] == '\\') {
            size_t n = i - start;
            const char *c = path + start;
            if (n == 0) {
                return PM_FS_DOT_COMPONENT;          /* "a//b" and a trailing separator: an empty component is refused */
            } else {
                size_t t = n;
                while (t > 0 && (c[t - 1] == '.' || c[t - 1] == ' ')) {
                    t--;                              /* Windows ignores trailing dots and spaces: "..." and ".. " mean ".." */
                }
                if (t == 0) {
                    return PM_FS_DOT_COMPONENT;
                }
                if (is_device(c, t)) {
                    return PM_FS_DEVICE_NAME;
                }
            }
            start = i + 1;
        }
    }
    /* a link that exists anywhere along the path, after the main folder */
    k = strlen(root_path);
    memcpy(prefix, root_path, k);
    if (k > 0) {
        prefix[k++] = '/';
    }
    start = 0;
    for (i = 0; i <= len; i++) {
        if (i == len || path[i] == '/' || path[i] == '\\') {
            size_t n = i - start;
            memcpy(prefix + k, path + start, n);
            prefix[k + n] = '\0';
            if (is_link(prefix)) {
                return PM_FS_LINK;
            }
            prefix[k + n] = '/';
            k += n + 1;
            start = i + 1;
        }
    }
    return PM_FS_OK;
}

PmFile *pm_fs_open_n(const char *path, size_t len, const char *mode)
{
    char full[FULL_MAX];
    size_t k, i;
    PmFile *f;
    PmFsError e;

    if (mode == NULL || !(strcmp(mode, "rb") == 0 || strcmp(mode, "wb") == 0 || strcmp(mode, "ab") == 0)) {
        last_error = PM_FS_BAD_MODE;
        return NULL;
    }
    e = pm_fs_check(path, len);
    if (e != PM_FS_OK) {
        last_error = e;
        return NULL;
    }
    k = strlen(root_path);
    memcpy(full, root_path, k);
    if (k > 0) {
        full[k++] = '/';
    }
    for (i = 0; i < len; i++) {
        full[k + i] = path[i] == '\\' ? '/' : path[i];
    }
    full[k + len] = '\0';
    f = (PmFile *)malloc(sizeof *f);
    if (f == NULL) {
        last_error = PM_FS_OPEN_FAILED;
        return NULL;
    }
    f->fp = fopen(full, mode);
    if (f->fp == NULL) {
        free(f);
        last_error = PM_FS_OPEN_FAILED;
        return NULL;
    }
    last_error = PM_FS_OK;
    return f;
}

int pm_fs_mkdir(const char *path)
{
    char full[FULL_MAX];
    size_t len = path == NULL ? 0 : strlen(path), k, i;
    PmFsError e = pm_fs_check(path, len);

    if (e != PM_FS_OK) {
        last_error = e;
        return -1;
    }
    k = strlen(root_path);
    memcpy(full, root_path, k);
    if (k > 0) {
        full[k++] = '/';
    }
    for (i = 0; i < len; i++) {
        full[k + i] = path[i] == '\\' ? '/' : path[i];
    }
    full[k + len] = '\0';
#if defined(_WIN32)
    if (!CreateDirectoryA(full, NULL) && GetLastError() != ERROR_ALREADY_EXISTS) {
        last_error = PM_FS_OPEN_FAILED;
        return -1;
    }
#else
    if (mkdir(full, 0777) != 0 && errno != EEXIST) {
        last_error = PM_FS_OPEN_FAILED;
        return -1;
    }
#endif
    last_error = PM_FS_OK;
    return 0;
}

PmFile *pm_fs_open(const char *path, const char *mode)
{
    return pm_fs_open_n(path, path == NULL ? 0 : strlen(path), mode);
}

size_t pm_fs_read(PmFile *f, void *buf, size_t n)
{
    return fread(buf, 1, n, f->fp);
}

size_t pm_fs_write(PmFile *f, const void *buf, size_t n)
{
    return fwrite(buf, 1, n, f->fp);
}

int pm_fs_printf(PmFile *f, const char *fmt, ...)
{
    int r;
    va_list ap;
    va_start(ap, fmt);
    r = vfprintf(f->fp, fmt, ap);
    va_end(ap);
    return r;
}

int pm_fs_close(PmFile *f)
{
    int r = fclose(f->fp);
    free(f);
    return r;
}
