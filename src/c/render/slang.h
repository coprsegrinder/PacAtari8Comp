/* render/slang.h - reading the CRT shader presets of the libretro "slang" format and turning their shaders into GLSL for OpenGL (docs/70).  Portable C99: text in, text and numbers out; no OpenGL here
 * (the OpenGL side is platform/win32/win_gl.c), no file access (the caller reads the files).
 *   - a PRESET (.slangp) lists the passes (shader file, filtering, size, framebuffer format, alias), the lookup textures and the values of the parameters it sets;
 *   - a SHADER (.slang) is Vulkan-style GLSL: one file with a vertex and a fragment part (`#pragma stage`), the parameters (`#pragma parameter`), a push-constant block and a uniform block with
 *     `set =` and `binding =` qualifiers.  slang_translate gives the two stages as GLSL 450 for OpenGL 4.5: the push constants become a second uniform block (binding 1), `set =` is dropped; the
 *     samplers keep their binding numbers (they are the texture units) and are listed with their names, which say what is to be bound to them. */
#ifndef PM_RENDER_SLANG_H
#define PM_RENDER_SLANG_H

#include <stddef.h>

#define SLANG_MAX_PASSES 24
#define SLANG_MAX_TEXTURES 8
#define SLANG_MAX_OVERRIDES 64
#define SLANG_MAX_PARAMS 192
#define SLANG_MAX_SAMPLERS 16
#define SLANG_NAME 56
#define SLANG_PATH 160

/* how a pass's picture is sized: from its input, from the viewport, or in pixels */
typedef enum SlangScale { SLANG_SCALE_SOURCE = 0, SLANG_SCALE_VIEWPORT = 1, SLANG_SCALE_ABSOLUTE = 2 } SlangScale;
/* what a texture gives outside its edges */
typedef enum SlangWrap { SLANG_WRAP_BORDER = 0, SLANG_WRAP_EDGE = 1, SLANG_WRAP_REPEAT = 2, SLANG_WRAP_MIRROR = 3 } SlangWrap;

/* one pass of a preset: its shader file and how it is filtered, sized and stored */
typedef struct SlangPass {
    char shader[SLANG_PATH];       /* relative to the preset's folder */
    int filter_linear;
    int wrap;                      /* SlangWrap */
    int mipmap_input;
    int float_fb, srgb_fb;
    int scale_type_x, scale_type_y;    /* SlangScale */
    float scale_x, scale_y;
    int scale_set;                 /* 1 when the preset says how the pass is scaled; else source 1.0, and the last pass is the viewport */
    char alias[SLANG_NAME];
} SlangPass;

/* a lookup texture of a preset */
typedef struct SlangTexture {
    char name[SLANG_NAME];
    char path[SLANG_PATH];
    int linear, mipmap, wrap;
} SlangTexture;

/* a parameter value the preset sets */
typedef struct SlangOverride {
    char name[SLANG_NAME];
    float value;
} SlangOverride;

/* a whole preset */
typedef struct SlangPreset {
    int npass;
    SlangPass pass[SLANG_MAX_PASSES];
    int ntex;
    SlangTexture tex[SLANG_MAX_TEXTURES];
    int nover;
    SlangOverride over[SLANG_MAX_OVERRIDES];       /* the parameters the preset sets */
} SlangPreset;

/* a parameter of a shader (`#pragma parameter`) */
typedef struct SlangParam {
    char name[SLANG_NAME];
    char desc[104];
    float init, min, max, step;
} SlangParam;

/* a texture a shader reads: its name says what to bind to it, its binding is the texture unit */
typedef struct SlangSampler {
    char name[SLANG_NAME];
    int binding;
} SlangSampler;

/* a shader turned into the two stages of GLSL for OpenGL, with its parameters and samplers */
typedef struct SlangShader {
    char *vertex, *fragment;       /* GLSL 450 text; malloc'd */
    int nparam;
    SlangParam param[SLANG_MAX_PARAMS];
    int nsampler;
    SlangSampler sampler[SLANG_MAX_SAMPLERS];
    char format[40];               /* the `#pragma format` of the shader ("" when none) */
} SlangShader;

/* reads a preset; 0 on success.  `err` gets the reason otherwise */
int slang_parse_preset(const char *text, SlangPreset *p, char *err, size_t errcap);

/* turns the text of a .slang file into the two GLSL stages and the lists above; 0 on success.  An #include is not followed (the three presets of the port have none): it is an error */
int slang_translate(const char *text, SlangShader *out, char *err, size_t errcap);
void slang_shader_free(SlangShader *s);                /* gives the two texts back */

#endif
