/* The CRT shader presets and shaders (src/c/render/slang.c, png.c, docs/70): the three presets are read, every shader of them is turned into GLSL for OpenGL, and the lookup textures are decoded.
 * Pure: no OpenGL here (that is tests of the Windows program).  Runs in the main folder: it reads third-party/crt-shaders/. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../platform/fs.h"
#include "../render/png.h"
#include "../render/slang.h"

static int failures;

#define CHECK(cond)                                                        \
    do {                                                                   \
        if (!(cond)) {                                                     \
            printf("FAILED line %d: %s\n", __LINE__, #cond);               \
            failures++;                                                    \
        }                                                                  \
    } while (0)

#define ROOT "third-party/crt-shaders/crt/"
static uint8_t buf[1 << 17];

static size_t read_file(const char *rel)
{
    char path[PM_FS_PATH_MAX];
    PmFile *f;
    size_t n;

    snprintf(path, sizeof path, "%s", rel);
    f = pm_fs_open(path, "rb");
    if (f == NULL) {
        return 0;
    }
    n = pm_fs_read(f, buf, sizeof buf - 1);
    pm_fs_close(f);
    buf[n] = 0;
    return n;
}

static int has(const char *text, const char *needle)
{
    return text != NULL && strstr(text, needle) != NULL;
}

static void check_preset(const char *file, int passes, int textures, int *nparams_out)
{
    static SlangPreset pre;
    static SlangShader sh;
    char err[200], path[PM_FS_PATH_MAX];
    int i, total_params = 0, samplers = 0;

    CHECK(read_file(file) > 0);
    CHECK(slang_parse_preset((const char *)buf, &pre, err, sizeof err) == 0);
    printf("  %s: %d passes, %d textures, %d parameter values set\n", file, pre.npass, pre.ntex, pre.nover);
    CHECK(pre.npass == passes && pre.ntex == textures);
    CHECK(pre.pass[pre.npass - 1].scale_type_x == SLANG_SCALE_VIEWPORT && pre.pass[pre.npass - 1].scale_type_y == SLANG_SCALE_VIEWPORT);   /* the last pass fills the viewport */
    for (i = 0; i < pre.npass; i++) {
        char dir[64];
        char *slash;
        size_t n;
        snprintf(dir, sizeof dir, "%s", file);
        slash = strrchr(dir, '/');
        if (slash != NULL) {
            slash[1] = '\0';
        }
        snprintf(path, sizeof path, "%s%s", dir, pre.pass[i].shader);
        n = read_file(path);
        CHECK(n > 0);
        if (n == 0) {
            continue;
        }
        if (slang_translate((const char *)buf, &sh, err, sizeof err) != 0) {
            printf("  %s: %s\n", path, err);
            CHECK(0);
            continue;
        }
        CHECK(sh.vertex != NULL && sh.fragment != NULL && strncmp(sh.vertex, "#version 450", 12) == 0 && strncmp(sh.fragment, "#version 450", 12) == 0);
        CHECK(!has(sh.vertex, "push_constant") && !has(sh.fragment, "push_constant") && !has(sh.vertex, "(set =") && !has(sh.fragment, "(set =") && !has(sh.vertex, ", set =") && !has(sh.fragment, ", set ="));
        CHECK(has(sh.vertex, "void main") && has(sh.fragment, "void main") && !has(sh.vertex, "#pragma stage") && !has(sh.fragment, "#pragma stage"));
        CHECK(has(sh.fragment, "layout(std140, binding = 1) uniform Push") && has(sh.fragment, "layout(std140, binding = 0) uniform UBO"));
        CHECK(sh.nsampler >= 1 && sh.nsampler <= 8);
        total_params += sh.nparam;
        samplers += sh.nsampler;
        slang_shader_free(&sh);
    }
    *nparams_out = total_params;
    printf("    %d parameters and %d samplers over the passes\n", total_params, samplers);
}

static void test_presets(void)
{
    int p1 = 0, p2 = 0, p3 = 0;

    check_preset(ROOT "crt-guest-advanced-ntsc.slangp", 19, 4, &p1);
    check_preset(ROOT "zfast-crt-composite.slangp", 1, 0, &p2);
    check_preset(ROOT "crt-aperture.slangp", 1, 0, &p3);
    CHECK(p1 > 100 && p2 == 10 && p3 >= 5);
}

static void test_one_shader_details(void)
{
    static SlangShader sh;
    char err[200];
    int i, found_src = 0, found_param = 0;

    CHECK(read_file(ROOT "shaders/zfast_crt/zfast_crt_composite.slang") > 0);
    CHECK(slang_translate((const char *)buf, &sh, err, sizeof err) == 0);
    for (i = 0; i < sh.nsampler; i++) {
        found_src |= strcmp(sh.sampler[i].name, "Source") == 0 && sh.sampler[i].binding == 2;
    }
    CHECK(found_src && sh.nsampler == 1);
    for (i = 0; i < sh.nparam; i++) {
        if (strcmp(sh.param[i].name, "WARP") == 0) {
            found_param = sh.param[i].init > 0.029f && sh.param[i].init < 0.031f && sh.param[i].max > 0.29f && strcmp(sh.param[i].desc, "Curvature") == 0;
        }
    }
    CHECK(found_param);
    slang_shader_free(&sh);
    CHECK(slang_translate("#version 450\n#include \"x.inc\"\n", &sh, err, sizeof err) != 0);          /* an #include is refused */
    CHECK(slang_translate("#version 450\nvoid main() {}\n", &sh, err, sizeof err) != 0);               /* a shader without the two stages */
}

static void test_preset_details(void)
{
    static SlangPreset pre;
    char err[200];

    CHECK(slang_parse_preset("shaders = 2\nshader0 = a.slang\nfilter_linear0 = true\nscale_type0 = source\nscale0 = 2.0\nalias0 = First \nshader1 = b.slang\nwrap_mode1 = repeat\nmipmap_input1 = true\n"
                             "textures = \"Lut\"\nLut = x.png\nLut_linear = true\nMyParam = 1.5\nOther = -2\nlist = no\n", &pre, err, sizeof err) == 0);
    CHECK(pre.npass == 2 && pre.pass[0].filter_linear && pre.pass[0].scale_x == 2.0f && strcmp(pre.pass[0].alias, "First") == 0);
    CHECK(pre.pass[1].wrap == SLANG_WRAP_REPEAT && pre.pass[1].mipmap_input && pre.pass[1].scale_type_x == SLANG_SCALE_VIEWPORT);       /* the last pass defaults to the viewport */
    CHECK(pre.ntex == 1 && strcmp(pre.tex[0].name, "Lut") == 0 && strcmp(pre.tex[0].path, "x.png") == 0 && pre.tex[0].linear);
    CHECK(pre.nover == 2 && strcmp(pre.over[0].name, "MyParam") == 0 && pre.over[0].value == 1.5f && pre.over[1].value == -2.0f);
    CHECK(slang_parse_preset("shaders = 3\nshader0 = a.slang\n", &pre, err, sizeof err) != 0);                                        /* fewer passes than declared */
    CHECK(slang_parse_preset("shaders = 1\n#reference \"x.slangp\"\n", &pre, err, sizeof err) != 0);
}

static void test_png(void)
{
    static const char *const luts[4] = {"trinitron-lut.png", "inv-trinitron-lut.png", "nec-lut.png", "ntsc-lut.png"};
    static uint8_t stored[] = {0x01, 0x03, 0x00, 0xFC, 0xFF, 'a', 'b', 'c'};      /* a stored deflate block holding "abc" */
    static uint8_t fixedb[] = {0x4B, 0x4C, 0x4A, 0x06, 0x00};                    /* the fixed-Huffman deflate stream of "abc" */
    uint8_t out[16];
    int i;

    CHECK(png_inflate(stored, sizeof stored, out, sizeof out) == 3 && memcmp(out, "abc", 3) == 0);
    CHECK(png_inflate(fixedb, sizeof fixedb, out, sizeof out) == 3 && memcmp(out, "abc", 3) == 0);
    CHECK(png_inflate(stored, 3, out, sizeof out) == -1);                           /* cut short */
    for (i = 0; i < 4; i++) {
        char path[PM_FS_PATH_MAX];
        size_t n;
        uint8_t *rgba = NULL;
        int w = 0, h = 0, x, distinct = 0;

        snprintf(path, sizeof path, "%sshaders/guest/advanced/lut/%s", ROOT, luts[i]);
        n = read_file(path);
        CHECK(n > 1000);
        CHECK(png_decode_rgba(buf, n, &rgba, &w, &h) == 0);
        CHECK(w == 1024 && h == 32 && rgba != NULL);
        if (rgba != NULL) {
            for (x = 1; x < w * h; x++) {
                distinct += memcmp(rgba + 4 * x, rgba + 4 * (x - 1), 3) != 0;
            }
            CHECK(distinct > 5000);                                                 /* a lookup table: not a flat image */
            CHECK(rgba[3] == 255 && rgba[4 * (w * h - 1) + 3] == 255);
            printf("  %s: %d x %d, %d changes of colour along the image\n", luts[i], w, h, distinct);
        }
        free(rgba);
    }
    CHECK(png_decode_rgba((const uint8_t *)"not a png at all, no, really not.......", 40, &(uint8_t *){NULL}, &i, &i) == 1);
}

int main(void)
{
    test_presets();
    test_one_shader_details();
    test_preset_details();
    test_png();
    if (failures == 0) {
        printf("slang_check: OK\n");
        return 0;
    }
    printf("slang_check: %d failures\n", failures);
    return 1;
}
