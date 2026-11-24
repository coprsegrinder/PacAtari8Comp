/* render/slang.c - see slang.h. */
#include "slang.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---------------------------------------------------------------- small helpers */

static void fail(char *err, size_t cap, const char *what, const char *detail)
{
    if (err != NULL && cap > 0) {
        snprintf(err, cap, "%s%s%s", what, detail != NULL ? ": " : "", detail != NULL ? detail : "");
    }
}

static char *trim(char *s)
{
    char *e;

    while (*s != '\0' && isspace((unsigned char)*s)) {
        s++;
    }
    e = s + strlen(s);
    while (e > s && isspace((unsigned char)e[-1])) {
        e--;
    }
    *e = '\0';
    return s;
}

static void unquote(char *s)
{
    size_t n = strlen(s);

    if (n >= 2 && s[0] == '"' && s[n - 1] == '"') {
        memmove(s, s + 1, n - 2);
        s[n - 2] = '\0';
    }
}

static int is_true(const char *v)
{
    return strcmp(v, "true") == 0 || strcmp(v, "1") == 0 || strcmp(v, "True") == 0 || strcmp(v, "TRUE") == 0;
}

static void copy(char *dst, size_t cap, const char *src)
{
    size_t n = strlen(src);

    if (n >= cap) {
        n = cap - 1;
    }
    memcpy(dst, src, n);
    dst[n] = '\0';
}

/* ---------------------------------------------------------------- the preset */

static int scale_type(const char *v)
{
    if (strcmp(v, "viewport") == 0) {
        return SLANG_SCALE_VIEWPORT;
    }
    if (strcmp(v, "absolute") == 0) {
        return SLANG_SCALE_ABSOLUTE;
    }
    return SLANG_SCALE_SOURCE;
}

static int wrap_mode(const char *v)
{
    if (strcmp(v, "clamp_to_edge") == 0) {
        return SLANG_WRAP_EDGE;
    }
    if (strcmp(v, "repeat") == 0) {
        return SLANG_WRAP_REPEAT;
    }
    if (strcmp(v, "mirrored_repeat") == 0) {
        return SLANG_WRAP_MIRROR;
    }
    return SLANG_WRAP_BORDER;
}

/* "name<digits>" with the given prefix: the number, or -1 */
static int numbered(const char *key, const char *prefix)
{
    size_t n = strlen(prefix);
    char *end;
    long v;

    if (strncmp(key, prefix, n) != 0 || !isdigit((unsigned char)key[n])) {
        return -1;
    }
    v = strtol(key + n, &end, 10);
    return *end == '\0' ? (int)v : -1;
}

int slang_parse_preset(const char *text, SlangPreset *p, char *err, size_t errcap)
{
    char *copy_text, *line, *next;
    int i;
    char texnames[SLANG_MAX_TEXTURES][SLANG_NAME];
    int ntexnames = 0, declared = -1;

    memset(p, 0, sizeof *p);
    copy_text = (char *)malloc(strlen(text) + 1);
    if (copy_text == NULL) {
        fail(err, errcap, "out of memory", NULL);
        return 1;
    }
    strcpy(copy_text, text);
    for (i = 0; i < SLANG_MAX_PASSES; i++) {
        p->pass[i].filter_linear = 0;
        p->pass[i].wrap = SLANG_WRAP_BORDER;
        p->pass[i].scale_type_x = p->pass[i].scale_type_y = SLANG_SCALE_SOURCE;
        p->pass[i].scale_x = p->pass[i].scale_y = 1.0f;
    }
    for (line = copy_text; line != NULL; line = next) {
        char *eq, *key, *val, *hash;
        int n;

        next = strchr(line, '\n');
        if (next != NULL) {
            *next++ = '\0';
        }
        line = trim(line);
        if (*line == '\0' || *line == '#') {
            if (strncmp(line, "#reference", 10) == 0) {
                free(copy_text);
                fail(err, errcap, "a #reference is not supported", NULL);
                return 1;
            }
            continue;
        }
        eq = strchr(line, '=');
        if (eq == NULL) {
            continue;
        }
        *eq = '\0';
        key = trim(line);
        val = eq + 1;
        hash = strstr(val, " #");                              /* a comment after the value */
        if (hash != NULL) {
            *hash = '\0';
        }
        val = trim(val);
        unquote(val);
        val = trim(val);
        if (strcmp(key, "shaders") == 0) {
            declared = atoi(val);
        } else if (strcmp(key, "textures") == 0) {
            char *t = val, *semi;
            while (t != NULL && *t != '\0' && ntexnames < SLANG_MAX_TEXTURES) {
                semi = strchr(t, ';');
                if (semi != NULL) {
                    *semi = '\0';
                }
                copy(texnames[ntexnames++], SLANG_NAME, trim(t));
                t = semi != NULL ? semi + 1 : NULL;
            }
        } else if ((n = numbered(key, "shader")) >= 0 && n < SLANG_MAX_PASSES) {
            copy(p->pass[n].shader, SLANG_PATH, val);
            if (n + 1 > p->npass) {
                p->npass = n + 1;
            }
        } else if ((n = numbered(key, "filter_linear")) >= 0 && n < SLANG_MAX_PASSES) {
            p->pass[n].filter_linear = is_true(val);
        } else if ((n = numbered(key, "wrap_mode")) >= 0 && n < SLANG_MAX_PASSES) {
            p->pass[n].wrap = wrap_mode(val);
        } else if ((n = numbered(key, "mipmap_input")) >= 0 && n < SLANG_MAX_PASSES) {
            p->pass[n].mipmap_input = is_true(val);
        } else if ((n = numbered(key, "float_framebuffer")) >= 0 && n < SLANG_MAX_PASSES) {
            p->pass[n].float_fb = is_true(val);
        } else if ((n = numbered(key, "srgb_framebuffer")) >= 0 && n < SLANG_MAX_PASSES) {
            p->pass[n].srgb_fb = is_true(val);
        } else if ((n = numbered(key, "alias")) >= 0 && n < SLANG_MAX_PASSES) {
            copy(p->pass[n].alias, SLANG_NAME, val);
        } else if ((n = numbered(key, "scale_type_x")) >= 0 && n < SLANG_MAX_PASSES) {
            p->pass[n].scale_type_x = scale_type(val);
            p->pass[n].scale_set = 1;
        } else if ((n = numbered(key, "scale_type_y")) >= 0 && n < SLANG_MAX_PASSES) {
            p->pass[n].scale_type_y = scale_type(val);
            p->pass[n].scale_set = 1;
        } else if ((n = numbered(key, "scale_type")) >= 0 && n < SLANG_MAX_PASSES) {
            p->pass[n].scale_type_x = p->pass[n].scale_type_y = scale_type(val);
            p->pass[n].scale_set = 1;
        } else if ((n = numbered(key, "scale_x")) >= 0 && n < SLANG_MAX_PASSES) {
            p->pass[n].scale_x = (float)atof(val);
            p->pass[n].scale_set = 1;
        } else if ((n = numbered(key, "scale_y")) >= 0 && n < SLANG_MAX_PASSES) {
            p->pass[n].scale_y = (float)atof(val);
            p->pass[n].scale_set = 1;
        } else if ((n = numbered(key, "scale")) >= 0 && n < SLANG_MAX_PASSES) {
            p->pass[n].scale_x = p->pass[n].scale_y = (float)atof(val);
            p->pass[n].scale_set = 1;
        } else if (numbered(key, "frame_count_mod") >= 0) {
            /* not needed: the frame counter is not wrapped */
        } else {
            int t, matched = 0;
            for (t = 0; t < ntexnames; t++) {                  /* a lookup texture: Name = path, Name_linear, Name_wrap_mode, Name_mipmap */
                size_t nn = strlen(texnames[t]);
                if (strncmp(key, texnames[t], nn) == 0) {
                    const char *rest = key + nn;
                    SlangTexture *tx = NULL;
                    int k;
                    for (k = 0; k < p->ntex; k++) {
                        if (strcmp(p->tex[k].name, texnames[t]) == 0) {
                            tx = &p->tex[k];
                        }
                    }
                    if (tx == NULL && p->ntex < SLANG_MAX_TEXTURES) {
                        tx = &p->tex[p->ntex++];
                        memset(tx, 0, sizeof *tx);
                        copy(tx->name, SLANG_NAME, texnames[t]);
                    }
                    if (tx == NULL) {
                        continue;
                    }
                    if (*rest == '\0') {
                        copy(tx->path, SLANG_PATH, val);
                        matched = 1;
                    } else if (strcmp(rest, "_linear") == 0) {
                        tx->linear = is_true(val);
                        matched = 1;
                    } else if (strcmp(rest, "_mipmap") == 0) {
                        tx->mipmap = is_true(val);
                        matched = 1;
                    } else if (strcmp(rest, "_wrap_mode") == 0) {
                        tx->wrap = wrap_mode(val);
                        matched = 1;
                    }
                    if (matched) {
                        break;
                    }
                }
            }
            if (!matched && p->nover < SLANG_MAX_OVERRIDES && (isdigit((unsigned char)val[0]) || val[0] == '-' || val[0] == '.')) {   /* a parameter the preset sets */
                copy(p->over[p->nover].name, SLANG_NAME, key);
                p->over[p->nover].value = (float)atof(val);
                p->nover++;
            }
        }
    }
    free(copy_text);
    if (p->npass < 1 || (declared >= 0 && declared != p->npass)) {
        fail(err, errcap, "the preset's pass list is not complete", NULL);
        return 1;
    }
    for (i = 0; i < p->npass; i++) {
        if (p->pass[i].shader[0] == '\0') {
            fail(err, errcap, "a pass has no shader", NULL);
            return 1;
        }
    }
    if (!p->pass[p->npass - 1].scale_set) {                     /* the last pass fills the viewport unless the preset says otherwise */
        p->pass[p->npass - 1].scale_type_x = p->pass[p->npass - 1].scale_type_y = SLANG_SCALE_VIEWPORT;
    }
    return 0;
}

/* ---------------------------------------------------------------- the shader */

typedef struct Buf {
    char *s;
    size_t n, cap;
} Buf;

static int buf_add(Buf *b, const char *t, size_t n)
{
    if (n > ((size_t)1 << 28) || b->n > ((size_t)1 << 28)) {
        return 0;
    }
    if (b->s == NULL || b->n + n + 1 > b->cap) {
        size_t c = b->cap == 0 ? 4096 : b->cap;
        char *m;
        while (c < b->n + n + 1) {
            c *= 2;
        }
        m = (char *)realloc(b->s, c);
        if (m == NULL) {
            return 0;
        }
        b->s = m;
        b->cap = c;
    }
    memcpy(b->s + b->n, t, n);
    b->n += n;
    b->s[b->n] = '\0';
    return 1;
}

/* the content of a layout(...) qualifier made fit for OpenGL: `set = N` goes, a push_constant block becomes a std140 block at binding 1 */
static void fix_layout(const char *in, size_t n, char *out, size_t cap)
{
    char tmp[256];
    char *tok, *save;
    size_t len = n < sizeof tmp - 1 ? n : sizeof tmp - 1;
    int first = 1;

    memcpy(tmp, in, len);
    tmp[len] = '\0';
    out[0] = '\0';
    for (tok = tmp; tok != NULL; tok = save) {
        char *comma = strchr(tok, ',');
        char *t;
        char piece[96];
        save = NULL;
        if (comma != NULL) {
            *comma = '\0';
            save = comma + 1;
        }
        t = trim(tok);
        if (strncmp(t, "set", 3) == 0 && (t[3] == ' ' || t[3] == '=')) {
            continue;
        }
        if (strcmp(t, "push_constant") == 0) {
            snprintf(piece, sizeof piece, "std140, binding = 1");
        } else {
            snprintf(piece, sizeof piece, "%s", t);
        }
        if (piece[0] == '\0') {
            continue;
        }
        if (strlen(out) + strlen(piece) + 3 < cap) {
            if (!first) {
                strcat(out, ", ");
            }
            strcat(out, piece);
            first = 0;
        }
    }
}

/* copies `text` to `b`, changing every layout(...) qualifier by fix_layout */
static int convert_text(Buf *b, const char *text, size_t n)
{
    size_t i = 0;

    while (i < n) {
        if (n - i > 7 && strncmp(text + i, "layout", 6) == 0 && (i == 0 || !(isalnum((unsigned char)text[i - 1]) || text[i - 1] == '_'))) {
            size_t j = i + 6;
            while (j < n && (text[j] == ' ' || text[j] == '\t')) {
                j++;
            }
            if (j < n && text[j] == '(') {
                size_t k = j + 1;
                char fixed[256];
                while (k < n && text[k] != ')') {
                    k++;
                }
                if (k >= n) {
                    return 0;
                }
                fix_layout(text + j + 1, k - j - 1, fixed, sizeof fixed);
                if (!buf_add(b, "layout(", 7) || !buf_add(b, fixed, strlen(fixed)) || !buf_add(b, ")", 1)) {
                    return 0;
                }
                i = k + 1;
                continue;
            }
        }
        if (!buf_add(b, text + i, 1)) {
            return 0;
        }
        i++;
    }
    return 1;
}

/* #pragma parameter NAME "description" initial min max step */
static void parse_parameter(const char *rest, SlangShader *out)
{
    char name[SLANG_NAME], desc[104];
    const char *p = rest, *q;
    float v[4];
    int i;
    SlangParam *pa;

    while (*p == ' ' || *p == '\t') {
        p++;
    }
    for (i = 0; *p != '\0' && !isspace((unsigned char)*p) && i < SLANG_NAME - 1; i++) {
        name[i] = *p++;
    }
    name[i] = '\0';
    while (*p == ' ' || *p == '\t') {
        p++;
    }
    desc[0] = '\0';
    if (*p == '"') {
        q = strchr(p + 1, '"');
        if (q == NULL) {
            return;
        }
        snprintf(desc, sizeof desc, "%.*s", (int)(q - p - 1) < 103 ? (int)(q - p - 1) : 103, p + 1);
        p = q + 1;
    }
    {
        char *end;
        for (i = 0; i < 4; i++) {
            v[i] = (float)strtod(p, &end);
            if (end == p) {
                return;
            }
            p = end;
        }
    }
    for (i = 0; i < out->nparam; i++) {
        if (strcmp(out->param[i].name, name) == 0) {
            return;                                             /* declared once is enough */
        }
    }
    if (out->nparam >= SLANG_MAX_PARAMS) {
        return;
    }
    pa = &out->param[out->nparam++];
    copy(pa->name, SLANG_NAME, name);
    copy(pa->desc, sizeof pa->desc, desc);
    pa->init = v[0];
    pa->min = v[1];
    pa->max = v[2];
    pa->step = v[3];
}

/* uniform sampler2D NAME with layout(... binding = N ...) in front of it */
static void find_samplers(const char *text, SlangShader *out)
{
    const char *p = text;

    while ((p = strstr(p, "sampler2D")) != NULL) {
        const char *line = p;
        int binding = -1;
        char name[SLANG_NAME];
        int i;
        const char *after = p + 9;
        while (line > text && line[-1] != '\n') {
            line--;
        }
        if ((size_t)(p - line) >= 8 && strstr(line, "layout") != NULL && strstr(line, "layout") < p && strstr(line, "uniform") != NULL && strstr(line, "uniform") < p) {
            const char *b = strstr(line, "binding");
            if (b != NULL && b < p) {
                b += 7;
                while (*b == ' ' || *b == '=') {
                    b++;
                }
                binding = atoi(b);
            }
            while (*after == ' ' || *after == '\t') {
                after++;
            }
            for (i = 0; (isalnum((unsigned char)*after) || *after == '_') && i < SLANG_NAME - 1; i++) {
                name[i] = *after++;
            }
            name[i] = '\0';
            if (binding >= 0 && name[0] != '\0' && out->nsampler < SLANG_MAX_SAMPLERS) {
                int k, dup = 0;
                for (k = 0; k < out->nsampler; k++) {
                    dup |= strcmp(out->sampler[k].name, name) == 0;
                }
                if (!dup) {
                    copy(out->sampler[out->nsampler].name, SLANG_NAME, name);
                    out->sampler[out->nsampler].binding = binding;
                    out->nsampler++;
                }
            }
        }
        p += 9;
    }
}

int slang_translate(const char *text, SlangShader *out, char *err, size_t errcap)
{
    Buf common = {0, 0, 0}, vert = {0, 0, 0}, frag = {0, 0, 0};
    Buf *cur = &common;
    const char *line = text;
    int ok = 1;

    memset(out, 0, sizeof *out);
    while (*line != '\0' && ok) {
        const char *nl = strchr(line, '\n');
        size_t n = nl != NULL ? (size_t)(nl - line) + 1 : strlen(line);
        const char *t = line;
        while (t < line + n && (*t == ' ' || *t == '\t')) {
            t++;
        }
        if (strncmp(t, "#include", 8) == 0) {
            fail(err, errcap, "an #include is not supported", NULL);
            ok = 0;
            break;
        }
        if (strncmp(t, "#pragma", 7) == 0) {
            const char *r = t + 7;
            while (*r == ' ' || *r == '\t') {
                r++;
            }
            if (strncmp(r, "stage", 5) == 0) {
                r += 5;
                while (*r == ' ' || *r == '\t') {
                    r++;
                }
                if (strncmp(r, "vertex", 6) == 0) {
                    cur = &vert;
                } else if (strncmp(r, "fragment", 8) == 0) {
                    cur = &frag;
                }
                buf_add(cur, "\n", 1);                          /* keeps the line count */
                line += n;
                continue;
            }
            if (strncmp(r, "parameter", 9) == 0) {
                char one[512];
                snprintf(one, sizeof one, "%.*s", (int)(n < 511 ? n : 511), r + 9);
                parse_parameter(one, out);
                buf_add(cur, "\n", 1);
                line += n;
                continue;
            }
            if (strncmp(r, "format", 6) == 0 || strncmp(r, "name", 4) == 0) {
                if (strncmp(r, "format", 6) == 0) {
                    const char *f = r + 6;
                    int i = 0;
                    while (*f == ' ' || *f == '\t') {
                        f++;
                    }
                    while ((isalnum((unsigned char)*f) || *f == '_') && i < 39) {
                        out->format[i++] = *f++;
                    }
                    out->format[i] = '\0';
                }
                buf_add(cur, "\n", 1);
                line += n;
                continue;
            }
        }
        if (!convert_text(cur, line, n)) {
            ok = 0;
        }
        line += n;
    }
    if (ok && (vert.s == NULL || frag.s == NULL || common.s == NULL)) {
        fail(err, errcap, "the shader has no vertex or no fragment stage", NULL);
        ok = 0;
    }
    if (ok) {
        Buf v = {0, 0, 0}, f = {0, 0, 0};
        ok = buf_add(&v, common.s, common.n) && buf_add(&v, vert.s, vert.n) && buf_add(&f, common.s, common.n) && buf_add(&f, frag.s, frag.n);
        if (ok) {
            out->vertex = v.s;
            out->fragment = f.s;
            find_samplers(out->fragment, out);
        } else {
            free(v.s);
            free(f.s);
            fail(err, errcap, "out of memory", NULL);
        }
    }
    free(common.s);
    free(vert.s);
    free(frag.s);
    return ok ? 0 : 1;
}

void slang_shader_free(SlangShader *s)
{
    free(s->vertex);
    free(s->fragment);
    s->vertex = s->fragment = NULL;
}
