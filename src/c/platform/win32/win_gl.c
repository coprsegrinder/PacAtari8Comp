/* platform/win32/win_gl.c - see win_gl.h.  The runtime of libretro slang presets on OpenGL 4.5 (docs/70): what RetroArch's filter chain does, for the three presets of the port. */
#include "win_gl.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../../render/png.h"
#include "../../render/slang.h"
#include "../fs.h"

/* ---------------------------------------------------------------- OpenGL: the names the headers of Windows do not have */

typedef unsigned int GLuint;
typedef int GLint;
typedef int GLsizei;
typedef unsigned int GLenum;
typedef unsigned char GLboolean;
typedef float GLfloat;
typedef char GLchar;
typedef ptrdiff_t GLsizeiptr;
typedef ptrdiff_t GLintptr;
typedef unsigned int GLbitfield;

#define GLAPI_ __stdcall
#define GL_TEXTURE_2D 0x0DE1
#define GL_RGBA 0x1908
#define GL_BGRA 0x80E1
#define GL_UNSIGNED_BYTE 0x1401
#define GL_FLOAT 0x1406
#define GL_UNSIGNED_INT 0x1405
#define GL_INT 0x1404
#define GL_FLOAT_VEC2 0x8B50
#define GL_FLOAT_VEC3 0x8B51
#define GL_FLOAT_VEC4 0x8B52
#define GL_FLOAT_MAT4 0x8B5C
#define GL_TRIANGLE_STRIP 0x0005
#define GL_COLOR_BUFFER_BIT 0x4000
#define GL_VERTEX_SHADER 0x8B31
#define GL_FRAGMENT_SHADER 0x8B30
#define GL_COMPILE_STATUS 0x8B81
#define GL_LINK_STATUS 0x8B82
#define GL_INFO_LOG_LENGTH 0x8B84
#define GL_ARRAY_BUFFER 0x8892
#define GL_UNIFORM_BUFFER 0x8A11
#define GL_STATIC_DRAW 0x88E4
#define GL_DYNAMIC_DRAW 0x88E8
#define GL_FRAMEBUFFER 0x8D40
#define GL_COLOR_ATTACHMENT0 0x8CE0
#define GL_FRAMEBUFFER_COMPLETE 0x8CD5
#define GL_TEXTURE0 0x84C0
#define GL_TEXTURE_MIN_FILTER 0x2801
#define GL_TEXTURE_MAG_FILTER 0x2800
#define GL_TEXTURE_WRAP_S 0x2802
#define GL_TEXTURE_WRAP_T 0x2803
#define GL_TEXTURE_BORDER_COLOR 0x1004
#define GL_NEAREST 0x2600
#define GL_LINEAR 0x2601
#define GL_NEAREST_MIPMAP_NEAREST 0x2700
#define GL_LINEAR_MIPMAP_LINEAR 0x2703
#define GL_CLAMP_TO_EDGE 0x812F
#define GL_CLAMP_TO_BORDER 0x812D
#define GL_REPEAT 0x2901
#define GL_MIRRORED_REPEAT 0x8370
#define GL_RGBA8 0x8058
#define GL_SRGB8_ALPHA8 0x8C43
#define GL_RGBA16F 0x881A
#define GL_RGBA32F 0x8814
#define GL_R16F 0x822D
#define GL_R32F 0x822E
#define GL_RG16F 0x822F
#define GL_R8 0x8229
#define GL_RG8 0x822B
#define GL_UNIFORM_BLOCK_DATA_SIZE 0x8A40
#define GL_UNIFORM_BLOCK_ACTIVE_UNIFORMS 0x8A42
#define GL_UNIFORM_BLOCK_ACTIVE_UNIFORM_INDICES 0x8A43
#define GL_UNIFORM_TYPE 0x8A37
#define GL_UNIFORM_OFFSET 0x8A3B
#define GL_UNIFORM_SIZE 0x8A38
#define GL_UNPACK_ALIGNMENT 0x0CF5
#define GL_UNPACK_ROW_LENGTH 0x0CF2
#define GL_PACK_ALIGNMENT 0x0D05
#define GL_VENDOR 0x1F00
#define GL_RENDERER 0x1F01
#define GL_VERSION 0x1F02
#define GL_INVALID_INDEX 0xFFFFFFFFu

#define WGL_CONTEXT_MAJOR_VERSION_ARB 0x2091
#define WGL_CONTEXT_MINOR_VERSION_ARB 0x2092
#define WGL_CONTEXT_PROFILE_MASK_ARB 0x9126
#define WGL_CONTEXT_CORE_PROFILE_BIT_ARB 0x00000001

/* OpenGL 1.1: exported by opengl32.dll */
void GLAPI_ glClear(GLbitfield);
void GLAPI_ glClearColor(GLfloat, GLfloat, GLfloat, GLfloat);
void GLAPI_ glViewport(GLint, GLint, GLsizei, GLsizei);
void GLAPI_ glDrawArrays(GLenum, GLint, GLsizei);
void GLAPI_ glBindTexture(GLenum, GLuint);
void GLAPI_ glGenTextures(GLsizei, GLuint *);
void GLAPI_ glDeleteTextures(GLsizei, const GLuint *);
void GLAPI_ glTexParameteri(GLenum, GLenum, GLint);
void GLAPI_ glPixelStorei(GLenum, GLint);
void GLAPI_ glReadPixels(GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, void *);
void GLAPI_ glTexSubImage2D(GLenum, GLint, GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, const void *);
void GLAPI_ glTexImage2D(GLenum, GLint, GLint, GLsizei, GLsizei, GLint, GLenum, GLenum, const void *);
GLenum GLAPI_ glGetError(void);
const unsigned char *GLAPI_ glGetString(GLenum);
void GLAPI_ glFinish(void);

/* later versions: through wglGetProcAddress */
#define GLFUNCS(X)                                                                                                                                                                            \
    X(GLuint, glCreateShader, (GLenum))                                                                                                                                                       \
    X(void, glShaderSource, (GLuint, GLsizei, const GLchar *const *, const GLint *))                                                                                                          \
    X(void, glCompileShader, (GLuint))                                                                                                                                                        \
    X(void, glGetShaderiv, (GLuint, GLenum, GLint *))                                                                                                                                         \
    X(void, glGetShaderInfoLog, (GLuint, GLsizei, GLsizei *, GLchar *))                                                                                                                       \
    X(void, glDeleteShader, (GLuint))                                                                                                                                                         \
    X(GLuint, glCreateProgram, (void))                                                                                                                                                        \
    X(void, glAttachShader, (GLuint, GLuint))                                                                                                                                                 \
    X(void, glLinkProgram, (GLuint))                                                                                                                                                          \
    X(void, glGetProgramiv, (GLuint, GLenum, GLint *))                                                                                                                                        \
    X(void, glGetProgramInfoLog, (GLuint, GLsizei, GLsizei *, GLchar *))                                                                                                                      \
    X(void, glUseProgram, (GLuint))                                                                                                                                                           \
    X(void, glDeleteProgram, (GLuint))                                                                                                                                                        \
    X(GLuint, glGetUniformBlockIndex, (GLuint, const GLchar *))                                                                                                                               \
    X(void, glGetActiveUniformBlockiv, (GLuint, GLuint, GLenum, GLint *))                                                                                                                     \
    X(void, glGetActiveUniformsiv, (GLuint, GLsizei, const GLuint *, GLenum, GLint *))                                                                                                        \
    X(void, glGetActiveUniformName, (GLuint, GLuint, GLsizei, GLsizei *, GLchar *))                                                                                                           \
    X(void, glGenBuffers, (GLsizei, GLuint *))                                                                                                                                                \
    X(void, glBindBuffer, (GLenum, GLuint))                                                                                                                                                   \
    X(void, glBufferData, (GLenum, GLsizeiptr, const void *, GLenum))                                                                                                                         \
    X(void, glBufferSubData, (GLenum, GLintptr, GLsizeiptr, const void *))                                                                                                                    \
    X(void, glBindBufferBase, (GLenum, GLuint, GLuint))                                                                                                                                       \
    X(void, glDeleteBuffers, (GLsizei, const GLuint *))                                                                                                                                       \
    X(void, glGenVertexArrays, (GLsizei, GLuint *))                                                                                                                                           \
    X(void, glBindVertexArray, (GLuint))                                                                                                                                                      \
    X(void, glVertexAttribPointer, (GLuint, GLint, GLenum, GLboolean, GLsizei, const void *))                                                                                                 \
    X(void, glEnableVertexAttribArray, (GLuint))                                                                                                                                              \
    X(void, glActiveTexture, (GLenum))                                                                                                                                                        \
    X(void, glGenerateMipmap, (GLenum))                                                                                                                                                       \
    X(void, glTexStorage2D, (GLenum, GLsizei, GLenum, GLsizei, GLsizei))                                                                                                                      \
    X(void, glGenFramebuffers, (GLsizei, GLuint *))                                                                                                                                           \
    X(void, glBindFramebuffer, (GLenum, GLuint))                                                                                                                                              \
    X(void, glFramebufferTexture2D, (GLenum, GLenum, GLenum, GLuint, GLint))                                                                                                                  \
    X(GLenum, glCheckFramebufferStatus, (GLenum))                                                                                                                                             \
    X(void, glDeleteFramebuffers, (GLsizei, const GLuint *))                                                                                                                                  \
    X(void, glGenSamplers, (GLsizei, GLuint *))                                                                                                                                               \
    X(void, glBindSampler, (GLuint, GLuint))                                                                                                                                                  \
    X(void, glSamplerParameteri, (GLuint, GLenum, GLint))                                                                                                                                     \
    X(void, glSamplerParameterfv, (GLuint, GLenum, const GLfloat *))                                                                                                                          \
    X(void, glDeleteSamplers, (GLsizei, const GLuint *))

#define X_TYPEDEF(ret, name, args) typedef ret(GLAPI_ *name##_t) args;
GLFUNCS(X_TYPEDEF)
#undef X_TYPEDEF
#define X_PTR(ret, name, args) static name##_t name##_p;
GLFUNCS(X_PTR)
#undef X_PTR
#define glCreateShader glCreateShader_p
#define glShaderSource glShaderSource_p
#define glCompileShader glCompileShader_p
#define glGetShaderiv glGetShaderiv_p
#define glGetShaderInfoLog glGetShaderInfoLog_p
#define glDeleteShader glDeleteShader_p
#define glCreateProgram glCreateProgram_p
#define glAttachShader glAttachShader_p
#define glLinkProgram glLinkProgram_p
#define glGetProgramiv glGetProgramiv_p
#define glGetProgramInfoLog glGetProgramInfoLog_p
#define glUseProgram glUseProgram_p
#define glDeleteProgram glDeleteProgram_p
#define glGetUniformBlockIndex glGetUniformBlockIndex_p
#define glGetActiveUniformBlockiv glGetActiveUniformBlockiv_p
#define glGetActiveUniformsiv glGetActiveUniformsiv_p
#define glGetActiveUniformName glGetActiveUniformName_p
#define glGenBuffers glGenBuffers_p
#define glBindBuffer glBindBuffer_p
#define glBufferData glBufferData_p
#define glBufferSubData glBufferSubData_p
#define glBindBufferBase glBindBufferBase_p
#define glDeleteBuffers glDeleteBuffers_p
#define glGenVertexArrays glGenVertexArrays_p
#define glBindVertexArray glBindVertexArray_p
#define glVertexAttribPointer glVertexAttribPointer_p
#define glEnableVertexAttribArray glEnableVertexAttribArray_p
#define glActiveTexture glActiveTexture_p
#define glGenerateMipmap glGenerateMipmap_p
#define glTexStorage2D glTexStorage2D_p
#define glGenFramebuffers glGenFramebuffers_p
#define glBindFramebuffer glBindFramebuffer_p
#define glFramebufferTexture2D glFramebufferTexture2D_p
#define glCheckFramebufferStatus glCheckFramebufferStatus_p
#define glDeleteFramebuffers glDeleteFramebuffers_p
#define glGenSamplers glGenSamplers_p
#define glBindSampler glBindSampler_p
#define glSamplerParameteri glSamplerParameteri_p
#define glSamplerParameterfv glSamplerParameterfv_p
#define glDeleteSamplers glDeleteSamplers_p

typedef HGLRC(WINAPI *CreateContextAttribsFn)(HDC, HGLRC, const int *);
typedef BOOL(WINAPI *SwapIntervalFn)(int);

/* ---------------------------------------------------------------- the context */

static HWND gl_wnd;
static HDC gl_dc;
static HGLRC gl_rc;
static SwapIntervalFn gl_swap_interval;
static int gl_interval_now = -1;
static GLuint gl_vao, gl_vbo_fbo, gl_vbo_screen;
static char gl_info[320];
static int gl_w = 1, gl_h = 1;

static LRESULT CALLBACK gl_proc(HWND h, UINT m, WPARAM w, LPARAM l)
{
    if (m == WM_ERASEBKGND) {
        return 1;
    }
    return DefWindowProcA(h, m, w, l);
}

typedef void (*GenericFn)(void);

static GenericFn gl_proc_address(const char *name)
{
    GenericFn p = (GenericFn)wglGetProcAddress(name);

    if ((uintptr_t)p <= 3u || (uintptr_t)p == (uintptr_t)-1) {
        HMODULE m = GetModuleHandleA("opengl32.dll");
        p = m != NULL ? (GenericFn)GetProcAddress(m, name) : NULL;
    }
    return p;
}

static void setmsg(char *err, size_t cap, const char *fmt, const char *a)
{
    if (err != NULL && cap > 0) {
        snprintf(err, cap, fmt, a);
    }
}

int crt_gl_open(HWND parent, char *err, size_t errcap)
{
    WNDCLASSA wc;
    PIXELFORMATDESCRIPTOR pfd;
    int fmt;
    HGLRC old;
    CreateContextAttribsFn create_attribs;
    SwapIntervalFn swap_interval;
    RECT rc;
    static const int attribs[] = {WGL_CONTEXT_MAJOR_VERSION_ARB, 4, WGL_CONTEXT_MINOR_VERSION_ARB, 5, WGL_CONTEXT_PROFILE_MASK_ARB, WGL_CONTEXT_CORE_PROFILE_BIT_ARB, 0};

    if (gl_wnd != NULL) {
        return 0;
    }
    memset(&wc, 0, sizeof wc);
    wc.style = CS_OWNDC;
    wc.lpfnWndProc = gl_proc;
    wc.hInstance = GetModuleHandleA(NULL);
    wc.lpszClassName = "PacManA8PortGL";
    if (!RegisterClassA(&wc) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS) {
        setmsg(err, errcap, "%s", "the window class of the CRT shaders could not be made");
        return 1;
    }
    GetClientRect(parent, &rc);
    gl_wnd = CreateWindowExA(0, wc.lpszClassName, "", WS_CHILD | WS_DISABLED | WS_CLIPSIBLINGS, 0, 0, rc.right > 0 ? rc.right : 1, rc.bottom > 0 ? rc.bottom : 1, parent, NULL, wc.hInstance, NULL);
    if (gl_wnd == NULL) {
        setmsg(err, errcap, "%s", "the window of the CRT shaders could not be made");
        return 1;
    }
    gl_dc = GetDC(gl_wnd);
    memset(&pfd, 0, sizeof pfd);
    pfd.nSize = sizeof pfd;
    pfd.nVersion = 1;
    pfd.dwFlags = PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL | PFD_DOUBLEBUFFER;
    pfd.iPixelType = PFD_TYPE_RGBA;
    pfd.cColorBits = 32;
    pfd.cAlphaBits = 8;
    fmt = ChoosePixelFormat(gl_dc, &pfd);
    if (fmt == 0 || !SetPixelFormat(gl_dc, fmt, &pfd)) {
        setmsg(err, errcap, "%s", "no OpenGL pixel format for the window");
        crt_gl_close();
        return 1;
    }
    old = wglCreateContext(gl_dc);
    if (old == NULL || !wglMakeCurrent(gl_dc, old)) {
        setmsg(err, errcap, "%s", "OpenGL could not be started");
        if (old != NULL) {
            wglDeleteContext(old);
        }
        crt_gl_close();
        return 1;
    }
    create_attribs = (CreateContextAttribsFn)gl_proc_address("wglCreateContextAttribsARB");
    if (create_attribs == NULL) {
        setmsg(err, errcap, "%s", "this OpenGL has no wglCreateContextAttribsARB (no OpenGL 4.5)");
        wglMakeCurrent(NULL, NULL);
        wglDeleteContext(old);
        crt_gl_close();
        return 1;
    }
    gl_rc = create_attribs(gl_dc, NULL, attribs);
    wglMakeCurrent(NULL, NULL);
    wglDeleteContext(old);
    if (gl_rc == NULL || !wglMakeCurrent(gl_dc, gl_rc)) {
        setmsg(err, errcap, "%s", "this graphics driver has no OpenGL 4.5 (the CRT shaders need it)");
        crt_gl_close();
        return 1;
    }
#define X_LOAD(ret, name, args)                                                                  \
    name##_p = (name##_t)gl_proc_address(#name);                                   \
    if (name##_p == NULL) {                                                                      \
        setmsg(err, errcap, "OpenGL function missing: %s", #name);                               \
        crt_gl_close();                                                                          \
        return 1;                                                                                \
    }
    GLFUNCS(X_LOAD)
#undef X_LOAD
    swap_interval = (SwapIntervalFn)gl_proc_address("wglSwapIntervalEXT");
    gl_swap_interval = swap_interval;
    crt_gl_interval(0);                                                                        /* the program paces the pictures itself, unless it asks the monitor to */
    snprintf(gl_info, sizeof gl_info, "%s, OpenGL %s", (const char *)glGetString(GL_RENDERER), (const char *)glGetString(GL_VERSION));
    glGenVertexArrays(1, &gl_vao);
    glBindVertexArray(gl_vao);
    {
        float a[24], b[24];
        static const float xs[4] = {-1, 1, -1, 1}, ys[4] = {-1, -1, 1, 1};
        int v;
        for (v = 0; v < 4; v++) {
            a[v * 6 + 0] = xs[v];
            a[v * 6 + 1] = ys[v];
            a[v * 6 + 2] = 0;
            a[v * 6 + 3] = 1;
            a[v * 6 + 4] = (xs[v] + 1) * 0.5f;
            a[v * 6 + 5] = (ys[v] + 1) * 0.5f;            /* the pass targets: v = 0 at the first row of the target */
            memcpy(b + v * 6, a + v * 6, sizeof(float) * 6);
            b[v * 6 + 5] = 1.0f - a[v * 6 + 5];             /* the window: v = 0 at the top */
        }
        glGenBuffers(1, &gl_vbo_fbo);
        glBindBuffer(GL_ARRAY_BUFFER, gl_vbo_fbo);
        glBufferData(GL_ARRAY_BUFFER, sizeof a, a, GL_STATIC_DRAW);
        glGenBuffers(1, &gl_vbo_screen);
        glBindBuffer(GL_ARRAY_BUFFER, gl_vbo_screen);
        glBufferData(GL_ARRAY_BUFFER, sizeof b, b, GL_STATIC_DRAW);
    }
    glEnableVertexAttribArray(0);
    glEnableVertexAttribArray(1);
    gl_w = rc.right > 0 ? rc.right : 1;
    gl_h = rc.bottom > 0 ? rc.bottom : 1;
    return 0;
}

void crt_gl_close(void)
{
    if (gl_rc != NULL) {
        wglMakeCurrent(NULL, NULL);
        wglDeleteContext(gl_rc);
        gl_rc = NULL;
    }
    if (gl_wnd != NULL) {
        if (gl_dc != NULL) {
            ReleaseDC(gl_wnd, gl_dc);
            gl_dc = NULL;
        }
        DestroyWindow(gl_wnd);
        gl_wnd = NULL;
    }
}

int crt_gl_is_open(void)
{
    return gl_rc != NULL;
}

void crt_gl_show(int visible)
{
    if (gl_wnd != NULL) {
        ShowWindow(gl_wnd, visible ? SW_SHOWNA : SW_HIDE);
    }
}

void crt_gl_resize(int w, int h)
{
    if (gl_wnd != NULL && w > 0 && h > 0) {
        SetWindowPos(gl_wnd, HWND_TOP, 0, 0, w, h, SWP_NOACTIVATE);
        gl_w = w;
        gl_h = h;
    }
}

const char *crt_gl_renderer(void)
{
    return gl_info;
}

void crt_gl_interval(int n)
{
    if (gl_swap_interval != NULL && n != gl_interval_now) {
        gl_swap_interval(n);
        gl_interval_now = n;
    }
}

void crt_gl_swap(void)
{
    if (gl_dc != NULL) {
        SwapBuffers(gl_dc);
    }
}

int crt_gl_readback(uint8_t *rgba, int vw, int vh)
{
    int y;
    uint8_t *tmp;

    tmp = (uint8_t *)malloc((size_t)vw * (size_t)vh * 4u);
    if (tmp == NULL) {
        return 1;
    }
    glPixelStorei(GL_PACK_ALIGNMENT, 1);
    glReadPixels(0, 0, vw, vh, GL_RGBA, GL_UNSIGNED_BYTE, tmp);                    /* of the back buffer, row 0 the bottom */
    for (y = 0; y < vh; y++) {
        memcpy(rgba + (size_t)y * (size_t)vw * 4u, tmp + (size_t)(vh - 1 - y) * (size_t)vw * 4u, (size_t)vw * 4u);
    }
    free(tmp);
    return 0;
}

/* ---------------------------------------------------------------- the chain */

#define REF_NONE 0
#define REF_SOURCE 1
#define REF_ORIGINAL 2
#define REF_HISTORY 3
#define REF_PASS 4
#define REF_FEEDBACK 5
#define REF_USER 6

typedef struct Ref {
    int kind, index;
} Ref;

enum { M_NONE = 0, M_MVP, M_OUTPUT_SIZE, M_SOURCE_SIZE, M_ORIGINAL_SIZE, M_FINAL_SIZE, M_FRAME_COUNT, M_FRAME_DIR, M_TEXSIZE, M_PARAM };

typedef struct Member {
    int block, offset, type, kind, index;
    Ref ref;
} Member;

typedef struct PassSampler {
    int unit;
    Ref ref;
} PassSampler;

typedef struct Pass {
    SlangPass cfg;
    SlangShader sh;
    GLuint prog;
    GLenum ifmt;
    GLuint tex[2], fbo[2];
    int cur, feedback, mips;
    int w, h;
    int nmember;
    Member member[96];
    int nsamp;
    PassSampler samp[SLANG_MAX_SAMPLERS];
    GLuint ubo[2];
    int ubo_size[2];
} Pass;

typedef struct UserTex {
    char name[SLANG_NAME];
    GLuint tex;
    int w, h, linear, wrap, mipmap;
} UserTex;

typedef struct ParamValue {
    char name[SLANG_NAME];
    float value;
} ParamValue;

struct CrtChain {
    SlangPreset preset;
    int npass;
    Pass *pass;
    int nuser;
    UserTex user[SLANG_MAX_TEXTURES];
    int nparam;
    ParamValue param[SLANG_MAX_PARAMS * 2];
    GLuint orig;
    int ow, oh, orig_mips;
    GLuint sampler[2][2][4];                    /* [linear][mipmap][wrap] */
    unsigned frame;
};

static char *read_text_file(const char *path, size_t *size_out)
{
    PmFile *f = pm_fs_open(path, "rb");
    size_t cap = 1u << 16, n = 0, got;
    char *buf;

    if (f == NULL) {
        return NULL;
    }
    buf = (char *)malloc(cap + 1);
    while (buf != NULL) {
        got = pm_fs_read(f, buf + n, cap - n);
        n += got;
        if (got == 0 || n < cap) {
            break;
        }
        cap *= 2;
        buf = (char *)realloc(buf, cap + 1);
    }
    pm_fs_close(f);
    if (buf == NULL) {
        return NULL;
    }
    buf[n] = '\0';
    if (size_out != NULL) {
        *size_out = n;
    }
    return buf;
}

static void dir_of(const char *path, char *dir, size_t cap)
{
    const char *slash = strrchr(path, '/');
    size_t n = slash != NULL ? (size_t)(slash - path) + 1 : 0;

    if (n >= cap) {
        n = cap - 1;
    }
    memcpy(dir, path, n);
    dir[n] = '\0';
}

static GLenum format_of(const char *pragma, int float_fb, int srgb_fb)
{
    if (strcmp(pragma, "R16G16B16A16_SFLOAT") == 0) { return GL_RGBA16F; }
    if (strcmp(pragma, "R32G32B32A32_SFLOAT") == 0) { return GL_RGBA32F; }
    if (strcmp(pragma, "R8G8B8A8_SRGB") == 0) { return GL_SRGB8_ALPHA8; }
    if (strcmp(pragma, "R16_SFLOAT") == 0) { return GL_R16F; }
    if (strcmp(pragma, "R32_SFLOAT") == 0) { return GL_R32F; }
    if (strcmp(pragma, "R16G16_SFLOAT") == 0) { return GL_RG16F; }
    if (strcmp(pragma, "R8_UNORM") == 0) { return GL_R8; }
    if (strcmp(pragma, "R8G8_UNORM") == 0) { return GL_RG8; }
    if (strcmp(pragma, "R8G8B8A8_UNORM") == 0) { return GL_RGBA8; }
    return float_fb ? GL_RGBA16F : (srgb_fb ? GL_SRGB8_ALPHA8 : GL_RGBA8);
}

static int parse_trailing_number(const char *s, const char *prefix, int *num)
{
    size_t n = strlen(prefix);
    char *end;

    if (strncmp(s, prefix, n) != 0 || s[n] < '0' || s[n] > '9') {
        return 0;
    }
    *num = (int)strtol(s + n, &end, 10);
    return *end == '\0';
}

/* what a name in a shader stands for: a texture of the chain */
static Ref resolve(const CrtChain *c, const char *name)
{
    Ref r = {REF_NONE, 0};
    int i, n;

    if (strcmp(name, "Source") == 0) {
        r.kind = REF_SOURCE;
    } else if (strcmp(name, "Original") == 0) {
        r.kind = REF_ORIGINAL;
    } else if (parse_trailing_number(name, "OriginalHistory", &n)) {
        r.kind = n == 0 ? REF_ORIGINAL : REF_HISTORY;
        r.index = n;
    } else if (parse_trailing_number(name, "PassFeedback", &n)) {
        r.kind = REF_FEEDBACK;
        r.index = n;
    } else if (parse_trailing_number(name, "Pass", &n)) {
        r.kind = REF_PASS;
        r.index = n;
    } else {
        for (i = 0; i < c->npass; i++) {
            const char *a = c->pass[i].cfg.alias;
            size_t an = strlen(a);
            if (an == 0) {
                continue;
            }
            if (strcmp(name, a) == 0) {
                r.kind = REF_PASS;
                r.index = i;
                return r;
            }
            if (strncmp(name, a, an) == 0 && strcmp(name + an, "Feedback") == 0) {
                r.kind = REF_FEEDBACK;
                r.index = i;
                return r;
            }
        }
        for (i = 0; i < c->nuser; i++) {
            if (strcmp(name, c->user[i].name) == 0) {
                r.kind = REF_USER;
                r.index = i;
                return r;
            }
        }
    }
    return r;
}

static int param_index(const CrtChain *c, const char *name)
{
    int i;

    for (i = 0; i < c->nparam; i++) {
        if (strcmp(c->param[i].name, name) == 0) {
            return i;
        }
    }
    return -1;
}

static GLuint compile(GLenum type, const char *src, char *err, size_t errcap, const char *what)
{
    GLuint s = glCreateShader(type);
    GLint ok = 0;

    glShaderSource(s, 1, &src, NULL);
    glCompileShader(s);
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[1500];
        GLsizei n = 0;
        glGetShaderInfoLog(s, sizeof log - 1, &n, log);
        log[n] = '\0';
        if (err != NULL && errcap > 0) {
            snprintf(err, errcap, "%s did not compile: %s", what, log);
        }
        glDeleteShader(s);
        return 0;
    }
    return s;
}

static void classify_members(CrtChain *c, Pass *p, int pass_index, char *err, size_t errcap)
{
    int blk;
    static const char *const blocks[2] = {"UBO", "Push"};

    (void)pass_index;
    (void)err;
    (void)errcap;
    p->nmember = 0;
    for (blk = 0; blk < 2; blk++) {
        GLuint bi = glGetUniformBlockIndex(p->prog, blocks[blk]);
        GLint n = 0, size = 0, *idx;
        int k;
        p->ubo_size[blk] = 0;
        if (bi == GL_INVALID_INDEX) {
            continue;
        }
        glGetActiveUniformBlockiv(p->prog, bi, GL_UNIFORM_BLOCK_DATA_SIZE, &size);
        glGetActiveUniformBlockiv(p->prog, bi, GL_UNIFORM_BLOCK_ACTIVE_UNIFORMS, &n);
        p->ubo_size[blk] = size;
        idx = (GLint *)malloc(sizeof(GLint) * (size_t)(n > 0 ? n : 1));
        if (idx == NULL) {
            continue;
        }
        glGetActiveUniformBlockiv(p->prog, bi, GL_UNIFORM_BLOCK_ACTIVE_UNIFORM_INDICES, idx);
        for (k = 0; k < n && p->nmember < (int)(sizeof p->member / sizeof p->member[0]); k++) {
            GLuint ui = (GLuint)idx[k];
            GLint off = 0, type = 0;
            char name[96], *dot;
            GLsizei len = 0;
            Member *m = &p->member[p->nmember];
            glGetActiveUniformsiv(p->prog, 1, &ui, GL_UNIFORM_OFFSET, &off);
            glGetActiveUniformsiv(p->prog, 1, &ui, GL_UNIFORM_TYPE, &type);
            glGetActiveUniformName(p->prog, ui, sizeof name - 1, &len, name);
            name[len] = '\0';
            dot = strrchr(name, '.');
            memset(m, 0, sizeof *m);
            m->block = blk;
            m->offset = off;
            m->type = type;
            if (strcmp(dot != NULL ? dot + 1 : name, "MVP") == 0) {
                m->kind = M_MVP;
            } else {
                const char *nm = dot != NULL ? dot + 1 : name;
                int h;
                if (strcmp(nm, "OutputSize") == 0) {
                    m->kind = M_OUTPUT_SIZE;
                } else if (strcmp(nm, "SourceSize") == 0) {
                    m->kind = M_SOURCE_SIZE;
                } else if (strcmp(nm, "OriginalSize") == 0) {
                    m->kind = M_ORIGINAL_SIZE;
                } else if (strcmp(nm, "FinalViewportSize") == 0) {
                    m->kind = M_FINAL_SIZE;
                } else if (strcmp(nm, "FrameCount") == 0) {
                    m->kind = M_FRAME_COUNT;
                } else if (strcmp(nm, "FrameDirection") == 0) {
                    m->kind = M_FRAME_DIR;
                } else if (parse_trailing_number(nm, "OriginalHistorySize", &h)) {
                    m->kind = M_TEXSIZE;
                    m->ref.kind = h == 0 ? REF_ORIGINAL : REF_HISTORY;
                    m->ref.index = h;
                } else {
                    size_t ln = strlen(nm);
                    int pi = param_index(c, nm);
                    if (pi >= 0) {
                        m->kind = M_PARAM;
                        m->index = pi;
                    } else if (ln > 4 && strcmp(nm + ln - 4, "Size") == 0) {
                        char base[SLANG_NAME];
                        snprintf(base, sizeof base, "%.*s", (int)(ln - 4), nm);
                        m->ref = resolve(c, base);
                        m->kind = m->ref.kind != REF_NONE ? M_TEXSIZE : M_NONE;
                    }
                }
            }
            p->nmember++;
        }
        free(idx);
    }
}

static int load_pass(CrtChain *c, int i, const char *dir, char *err, size_t errcap)
{
    Pass *p = &c->pass[i];
    char path[PM_FS_PATH_MAX], *text;
    char e2[1600];
    GLuint vs, fs;
    GLint linked = 0;
    int s;

    p->cfg = c->preset.pass[i];
    snprintf(path, sizeof path, "%s%s", dir, p->cfg.shader);
    text = read_text_file(path, NULL);
    if (text == NULL) {
        snprintf(err, errcap, "cannot read %s", path);
        return 1;
    }
    if (slang_translate(text, &p->sh, e2, sizeof e2) != 0) {
        snprintf(err, errcap, "%s: %s", path, e2);
        free(text);
        return 1;
    }
    free(text);
    for (s = 0; s < p->sh.nparam; s++) {                                                     /* the parameters of the shader join the chain's, with the default of the shader or the preset's value */
        if (param_index(c, p->sh.param[s].name) < 0 && c->nparam < (int)(sizeof c->param / sizeof c->param[0])) {
            int o;
            snprintf(c->param[c->nparam].name, SLANG_NAME, "%s", p->sh.param[s].name);
            c->param[c->nparam].value = p->sh.param[s].init;
            for (o = 0; o < c->preset.nover; o++) {
                if (strcmp(c->preset.over[o].name, p->sh.param[s].name) == 0) {
                    c->param[c->nparam].value = c->preset.over[o].value;
                }
            }
            c->nparam++;
        }
    }
    snprintf(e2, sizeof e2, "%s", path);
    vs = compile(GL_VERTEX_SHADER, p->sh.vertex, err, errcap, "a vertex shader");
    if (vs == 0) {
        char more[1700];
        snprintf(more, sizeof more, "%s: %s", path, err);
        snprintf(err, errcap, "%s", more);
        return 1;
    }
    fs = compile(GL_FRAGMENT_SHADER, p->sh.fragment, err, errcap, "a fragment shader");
    if (fs == 0) {
        char more[1700];
        snprintf(more, sizeof more, "%s: %s", path, err);
        snprintf(err, errcap, "%s", more);
        glDeleteShader(vs);
        return 1;
    }
    p->prog = glCreateProgram();
    glAttachShader(p->prog, vs);
    glAttachShader(p->prog, fs);
    glLinkProgram(p->prog);
    glDeleteShader(vs);
    glDeleteShader(fs);
    glGetProgramiv(p->prog, GL_LINK_STATUS, &linked);
    if (!linked) {
        char log[1500];
        GLsizei n = 0;
        glGetProgramInfoLog(p->prog, sizeof log - 1, &n, log);
        log[n] = '\0';
        snprintf(err, errcap, "%s did not link: %s", path, log);
        return 1;
    }
    p->ifmt = format_of(p->sh.format, p->cfg.float_fb, p->cfg.srgb_fb);
    return 0;
}

static int bind_samplers(CrtChain *c, int i, char *err, size_t errcap)
{
    Pass *p = &c->pass[i];
    int s;

    p->nsamp = 0;
    for (s = 0; s < p->sh.nsampler; s++) {
        Ref r = resolve(c, p->sh.sampler[s].name);
        if (r.kind == REF_NONE || r.kind == REF_HISTORY) {
            snprintf(err, errcap, "pass %d (%s): the texture \"%s\" is not one this runtime knows", i, p->cfg.shader, p->sh.sampler[s].name);
            return 1;
        }
        if ((r.kind == REF_PASS && r.index >= i) || (r.kind == REF_FEEDBACK && r.index >= c->npass)) {
            snprintf(err, errcap, "pass %d (%s): \"%s\" refers to a pass that is not made before it", i, p->cfg.shader, p->sh.sampler[s].name);
            return 1;
        }
        p->samp[p->nsamp].unit = p->sh.sampler[s].binding;
        p->samp[p->nsamp].ref = r;
        p->nsamp++;
        if (r.kind == REF_FEEDBACK) {
            c->pass[r.index].feedback = 1;
        }
    }
    return 0;
}

CrtChain *crt_chain_load(const char *preset_path, char *err, size_t errcap)
{
    CrtChain *c;
    char *text, dir[64], e2[200];
    int i;

    if (!crt_gl_is_open()) {
        snprintf(err, errcap, "OpenGL is not open");
        return NULL;
    }
    text = read_text_file(preset_path, NULL);
    if (text == NULL) {
        snprintf(err, errcap, "cannot read %s", preset_path);
        return NULL;
    }
    c = (CrtChain *)calloc(1, sizeof *c);
    if (c == NULL) {
        free(text);
        snprintf(err, errcap, "out of memory");
        return NULL;
    }
    if (slang_parse_preset(text, &c->preset, e2, sizeof e2) != 0) {
        snprintf(err, errcap, "%s: %s", preset_path, e2);
        free(text);
        free(c);
        return NULL;
    }
    free(text);
    dir_of(preset_path, dir, sizeof dir);
    c->npass = c->preset.npass;
    c->pass = (Pass *)calloc((size_t)c->npass, sizeof(Pass));
    if (c->pass == NULL) {
        free(c);
        snprintf(err, errcap, "out of memory");
        return NULL;
    }
    for (i = 0; i < c->preset.ntex; i++) {                                                      /* the lookup textures */
        const SlangTexture *t = &c->preset.tex[i];
        char path[PM_FS_PATH_MAX];
        size_t n = 0;
        char *png;
        uint8_t *rgba = NULL;
        int w = 0, h = 0;
        UserTex *u = &c->user[c->nuser];
        snprintf(path, sizeof path, "%s%s", dir, t->path);
        png = read_text_file(path, &n);
        if (png == NULL || png_decode_rgba((const uint8_t *)png, n, &rgba, &w, &h) != 0) {
            snprintf(err, errcap, "cannot read the texture %s", path);
            free(png);
            crt_chain_free(c);
            return NULL;
        }
        free(png);
        snprintf(u->name, SLANG_NAME, "%s", t->name);
        u->w = w;
        u->h = h;
        u->linear = t->linear;
        u->wrap = t->wrap;
        u->mipmap = t->mipmap;
        glGenTextures(1, &u->tex);
        glBindTexture(GL_TEXTURE_2D, u->tex);
        glTexStorage2D(GL_TEXTURE_2D, 1, GL_RGBA8, w, h);
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, rgba);
        free(rgba);
        c->nuser++;
    }
    for (i = 0; i < c->npass; i++) {
        if (load_pass(c, i, dir, err, errcap) != 0) {
            crt_chain_free(c);
            return NULL;
        }
    }
    for (i = 0; i < c->npass; i++) {
        if (bind_samplers(c, i, err, errcap) != 0) {
            crt_chain_free(c);
            return NULL;
        }
        classify_members(c, &c->pass[i], i, err, errcap);
        glGenBuffers(2, c->pass[i].ubo);
        for (e2[0] = 0; e2[0] < 2; e2[0]++) {
            int b = e2[0];
            glBindBuffer(GL_UNIFORM_BUFFER, c->pass[i].ubo[b]);
            glBufferData(GL_UNIFORM_BUFFER, c->pass[i].ubo_size[b] > 0 ? c->pass[i].ubo_size[b] : 16, NULL, GL_DYNAMIC_DRAW);
        }
        if (i + 1 < c->npass && c->pass[i + 1].cfg.mipmap_input) {
            c->pass[i].mips = 1;
        }
    }
    {
        int w, l, m;                                                                          /* the sampler objects */
        for (l = 0; l < 2; l++) {
            for (m = 0; m < 2; m++) {
                for (w = 0; w < 4; w++) {
                    static const GLenum wraps[4] = {GL_CLAMP_TO_BORDER, GL_CLAMP_TO_EDGE, GL_REPEAT, GL_MIRRORED_REPEAT};
                    static const float border[4] = {0, 0, 0, 0};
                    GLuint s;
                    glGenSamplers(1, &s);
                    glSamplerParameteri(s, GL_TEXTURE_MIN_FILTER, m ? (l ? GL_LINEAR_MIPMAP_LINEAR : GL_NEAREST_MIPMAP_NEAREST) : (l ? GL_LINEAR : GL_NEAREST));
                    glSamplerParameteri(s, GL_TEXTURE_MAG_FILTER, l ? GL_LINEAR : GL_NEAREST);
                    glSamplerParameteri(s, GL_TEXTURE_WRAP_S, (GLint)wraps[w]);
                    glSamplerParameteri(s, GL_TEXTURE_WRAP_T, (GLint)wraps[w]);
                    glSamplerParameterfv(s, GL_TEXTURE_BORDER_COLOR, border);
                    c->sampler[l][m][w] = s;
                }
            }
        }
    }
    c->orig_mips = c->preset.pass[0].mipmap_input;
    return c;
}

int crt_chain_passes(const CrtChain *c)
{
    return c->npass;
}

static void free_targets(Pass *p)
{
    int k;

    for (k = 0; k < 2; k++) {
        if (p->tex[k] != 0) {
            glDeleteTextures(1, &p->tex[k]);
            p->tex[k] = 0;
        }
        if (p->fbo[k] != 0) {
            glDeleteFramebuffers(1, &p->fbo[k]);
            p->fbo[k] = 0;
        }
    }
}

void crt_chain_free(CrtChain *c)
{
    int i, a, b, d;

    if (c == NULL) {
        return;
    }
    for (i = 0; i < c->npass; i++) {
        Pass *p = &c->pass[i];
        free_targets(p);
        if (p->prog != 0) {
            glDeleteProgram(p->prog);
        }
        if (p->ubo[0] != 0) {
            glDeleteBuffers(2, p->ubo);
        }
        slang_shader_free(&p->sh);
    }
    for (i = 0; i < c->nuser; i++) {
        glDeleteTextures(1, &c->user[i].tex);
    }
    if (c->orig != 0) {
        glDeleteTextures(1, &c->orig);
    }
    for (a = 0; a < 2; a++) {
        for (b = 0; b < 2; b++) {
            for (d = 0; d < 4; d++) {
                if (c->sampler[a][b][d] != 0) {
                    glDeleteSamplers(1, &c->sampler[a][b][d]);
                }
            }
        }
    }
    free(c->pass);
    free(c);
}

static int levels_for(int w, int h)
{
    int l = 1, m = w > h ? w : h;

    while (m > 1) {
        m >>= 1;
        l++;
    }
    return l;
}

static int make_target(Pass *p, int w, int h, char *err, size_t errcap)
{
    int k, n = p->feedback ? 2 : 1;

    free_targets(p);
    for (k = 0; k < n; k++) {
        GLfloat zero[4] = {0, 0, 0, 0};
        (void)zero;
        glGenTextures(1, &p->tex[k]);
        glBindTexture(GL_TEXTURE_2D, p->tex[k]);
        glTexStorage2D(GL_TEXTURE_2D, p->mips ? levels_for(w, h) : 1, p->ifmt, w, h);
        glGenFramebuffers(1, &p->fbo[k]);
        glBindFramebuffer(GL_FRAMEBUFFER, p->fbo[k]);
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, p->tex[k], 0);
        if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
            snprintf(err, errcap, "a framebuffer of %d x %d is not complete (format %x)", w, h, (unsigned)p->ifmt);
            glBindFramebuffer(GL_FRAMEBUFFER, 0);
            return 1;
        }
        glViewport(0, 0, w, h);
        glClearColor(0, 0, 0, 0);
        glClear(GL_COLOR_BUFFER_BIT);
    }
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    p->w = w;
    p->h = h;
    return 0;
}

static int size_of(int type, float scale, int in, int vp)
{
    float v = type == SLANG_SCALE_VIEWPORT ? (float)vp * scale : (type == SLANG_SCALE_ABSOLUTE ? scale : (float)in * scale);
    int n = (int)floorf(v + 0.5f);

    return n < 1 ? 1 : n;
}

typedef struct TexView {
    GLuint id;
    int w, h;
} TexView;

static TexView view_of(CrtChain *c, const Pass *p, int index, Ref r, int src_w, int src_h, GLuint src_tex)
{
    TexView v = {0, 1, 1};

    (void)index;
    switch (r.kind) {
    case REF_SOURCE:
        v.id = src_tex;
        v.w = src_w;
        v.h = src_h;
        break;
    case REF_ORIGINAL:
        v.id = c->orig;
        v.w = c->ow;
        v.h = c->oh;
        break;
    case REF_PASS: {
        const Pass *q = &c->pass[r.index];
        v.id = q->tex[q->feedback ? q->cur : 0];
        v.w = q->w;
        v.h = q->h;
        break;
    }
    case REF_FEEDBACK: {
        const Pass *q = &c->pass[r.index];
        v.id = q->tex[q->feedback ? 1 - q->cur : 0];
        v.w = q->w;
        v.h = q->h;
        break;
    }
    case REF_USER:
        v.id = c->user[r.index].tex;
        v.w = c->user[r.index].w;
        v.h = c->user[r.index].h;
        break;
    default:
        break;
    }
    (void)p;
    return v;
}

static void put_floats(uint8_t *base, int offset, int type, const float *v, int n)
{
    int k, cnt = type == GL_FLOAT ? 1 : (type == GL_FLOAT_VEC2 ? 2 : (type == GL_FLOAT_VEC3 ? 3 : 4));

    for (k = 0; k < cnt && k < n; k++) {
        memcpy(base + offset + k * 4, &v[k], 4);
    }
}

static const int (*gl_dirty_r)[4];
static int gl_dirty_n = -1;

void crt_gl_dirty(const int (*rects)[4], int n)
{
    gl_dirty_r = rects;
    gl_dirty_n = n;
}

int crt_chain_render(CrtChain *c, const uint32_t *bgra, int w, int h, int vx, int vy, int vw, int vh, unsigned frame, char *err, size_t errcap)
{
    int whole = 1;
    int i, src_w, src_h;
    GLuint src_tex;
    GLenum e;

    if (c == NULL || !crt_gl_is_open() || vw < 1 || vh < 1) {
        return 1;
    }
    if (c->orig == 0 || c->ow != w || c->oh != h) {                                           /* the picture's texture */
        if (c->orig != 0) {
            glDeleteTextures(1, &c->orig);
        }
        glGenTextures(1, &c->orig);
        glBindTexture(GL_TEXTURE_2D, c->orig);
        glTexStorage2D(GL_TEXTURE_2D, c->orig_mips ? levels_for(w, h) : 1, GL_RGBA8, w, h);
        c->ow = w;
        c->oh = h;
    } else if (gl_dirty_n >= 0 && gl_dirty_r != NULL) {
        whole = 0;
    }
    glBindTexture(GL_TEXTURE_2D, c->orig);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
    if (whole) {
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_BGRA, GL_UNSIGNED_BYTE, bgra);
    } else {                                                                                    /* only what changed since the last picture */
        int ri;
        glPixelStorei(GL_UNPACK_ROW_LENGTH, w);
        for (ri = 0; ri < gl_dirty_n; ri++) {
            int x0 = gl_dirty_r[ri][0], y0 = gl_dirty_r[ri][1], x1 = gl_dirty_r[ri][2], y1 = gl_dirty_r[ri][3];
            if (x0 < 0) { x0 = 0; }
            if (y0 < 0) { y0 = 0; }
            if (x1 > w) { x1 = w; }
            if (y1 > h) { y1 = h; }
            if (x1 > x0 && y1 > y0) {
                glTexSubImage2D(GL_TEXTURE_2D, 0, x0, y0, x1 - x0, y1 - y0, GL_BGRA, GL_UNSIGNED_BYTE, bgra + (size_t)y0 * (size_t)w + (size_t)x0);
            }
        }
        glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);
    }
    gl_dirty_n = -1;
    glBindVertexArray(gl_vao);
    src_tex = c->orig;
    src_w = w;
    src_h = h;
    for (i = 0; i < c->npass; i++) {
        Pass *p = &c->pass[i];
        int last = i == c->npass - 1;
        int ow = last ? vw : size_of(p->cfg.scale_type_x, p->cfg.scale_x, src_w, vw);
        int oh = last ? vh : size_of(p->cfg.scale_type_y, p->cfg.scale_y, src_h, vh);
        int s, m, blk;
        uint8_t *data[2];
        static uint8_t scratch[2][4096];

        if (!last && (p->tex[0] == 0 || p->w != ow || p->h != oh)) {
            if (make_target(p, ow, oh, err, errcap) != 0) {
                return 1;
            }
        }
        if (last) {
            p->w = ow;
            p->h = oh;
        }
        if (p->cfg.mipmap_input) {                                                              /* the input of this pass gets its mip levels */
            glBindTexture(GL_TEXTURE_2D, src_tex);
            glGenerateMipmap(GL_TEXTURE_2D);
        }
        glUseProgram(p->prog);
        for (blk = 0; blk < 2; blk++) {                                                         /* the two uniform blocks, filled by name */
            int size = p->ubo_size[blk];
            data[blk] = size > 0 && size <= (int)sizeof scratch[0] ? scratch[blk] : NULL;
            if (data[blk] == NULL) {
                continue;
            }
            memset(data[blk], 0, (size_t)size);
        }
        for (m = 0; m < p->nmember; m++) {
            const Member *mb = &p->member[m];
            uint8_t *base = data[mb->block];
            float v[16];
            if (base == NULL) {
                continue;
            }
            switch (mb->kind) {
            case M_MVP:
                memset(v, 0, sizeof v);
                v[0] = v[5] = v[10] = v[15] = 1.0f;
                memcpy(base + mb->offset, v, sizeof v);
                break;
            case M_OUTPUT_SIZE:
                v[0] = (float)ow; v[1] = (float)oh; v[2] = 1.0f / (float)ow; v[3] = 1.0f / (float)oh;
                put_floats(base, mb->offset, mb->type, v, 4);
                break;
            case M_SOURCE_SIZE:
                v[0] = (float)src_w; v[1] = (float)src_h; v[2] = 1.0f / (float)src_w; v[3] = 1.0f / (float)src_h;
                put_floats(base, mb->offset, mb->type, v, 4);
                break;
            case M_ORIGINAL_SIZE:
                v[0] = (float)w; v[1] = (float)h; v[2] = 1.0f / (float)w; v[3] = 1.0f / (float)h;
                put_floats(base, mb->offset, mb->type, v, 4);
                break;
            case M_FINAL_SIZE:
                v[0] = (float)vw; v[1] = (float)vh; v[2] = 1.0f / (float)vw; v[3] = 1.0f / (float)vh;
                put_floats(base, mb->offset, mb->type, v, 4);
                break;
            case M_FRAME_COUNT: {
                uint32_t f = frame;
                memcpy(base + mb->offset, &f, 4);
                break;
            }
            case M_FRAME_DIR: {
                int32_t d = 1;
                memcpy(base + mb->offset, &d, 4);
                break;
            }
            case M_TEXSIZE: {
                TexView t = view_of(c, p, i, mb->ref, src_w, src_h, src_tex);
                v[0] = (float)t.w; v[1] = (float)t.h; v[2] = 1.0f / (float)(t.w > 0 ? t.w : 1); v[3] = 1.0f / (float)(t.h > 0 ? t.h : 1);
                put_floats(base, mb->offset, mb->type, v, 4);
                break;
            }
            case M_PARAM:
                v[0] = c->param[mb->index].value;
                if (mb->type == GL_INT || mb->type == GL_UNSIGNED_INT) {
                    int32_t iv = (int32_t)v[0];
                    memcpy(base + mb->offset, &iv, 4);
                } else {
                    put_floats(base, mb->offset, mb->type, v, 1);
                }
                break;
            default:
                break;
            }
        }
        for (blk = 0; blk < 2; blk++) {
            if (data[blk] != NULL) {
                glBindBuffer(GL_UNIFORM_BUFFER, p->ubo[blk]);
                glBufferSubData(GL_UNIFORM_BUFFER, 0, p->ubo_size[blk], data[blk]);
                glBindBufferBase(GL_UNIFORM_BUFFER, (GLuint)blk, p->ubo[blk]);
            }
        }
        for (s = 0; s < p->nsamp; s++) {                                                        /* the textures */
            const PassSampler *ps = &p->samp[s];
            TexView t = view_of(c, p, i, ps->ref, src_w, src_h, src_tex);
            int linear = p->cfg.filter_linear, mip = p->cfg.mipmap_input && (ps->ref.kind == REF_SOURCE || ps->ref.kind == REF_ORIGINAL), wrap = p->cfg.wrap;
            if (ps->ref.kind == REF_USER) {
                linear = c->user[ps->ref.index].linear;
                mip = 0;
                wrap = c->user[ps->ref.index].wrap;
            }
            glActiveTexture(GL_TEXTURE0 + (GLenum)ps->unit);
            glBindTexture(GL_TEXTURE_2D, t.id);
            glBindSampler((GLuint)ps->unit, c->sampler[linear ? 1 : 0][mip ? 1 : 0][wrap]);
        }
        glBindBuffer(GL_ARRAY_BUFFER, last ? gl_vbo_screen : gl_vbo_fbo);
        glVertexAttribPointer(0, 4, GL_FLOAT, 0, 6 * sizeof(float), (const void *)0);
        glVertexAttribPointer(1, 2, GL_FLOAT, 0, 6 * sizeof(float), (const void *)(4 * sizeof(float)));
        if (last) {
            glBindFramebuffer(GL_FRAMEBUFFER, 0);
            glViewport(0, 0, gl_w, gl_h);
            glClearColor(0, 0, 0, 1);
            glClear(GL_COLOR_BUFFER_BIT);
            glViewport(vx, gl_h - vy - vh, vw, vh);
        } else {
            glBindFramebuffer(GL_FRAMEBUFFER, p->fbo[p->feedback ? p->cur : 0]);
            glViewport(0, 0, ow, oh);
        }
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
        if (!last) {
            src_tex = p->tex[p->feedback ? p->cur : 0];
            src_w = ow;
            src_h = oh;
        }
    }
    for (i = 0; i < c->npass; i++) {                                                            /* the pass that is looked at again next time keeps this picture, and draws the next one into the other texture */
        if (c->pass[i].feedback) {
            c->pass[i].cur = 1 - c->pass[i].cur;
        }
    }
    for (i = 0; i < 16; i++) {
        glBindSampler((GLuint)i, 0);
    }
    c->frame = frame;
    e = glGetError();
    if (e != 0) {
        snprintf(err, errcap, "OpenGL error 0x%x", (unsigned)e);
        return 1;
    }
    return 0;
}
