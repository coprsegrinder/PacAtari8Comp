#version 450
/* plain.slang - the picture as it is: the Off of the CRT shader item.  The window of the OpenGL context is always the one that shows the picture, so that choosing a shader or Off changes only what is drawn into it (docs/70).
 * This file is part of the port itself (MIT, like the rest of src/), not one of the third-party shaders. */

layout(std140, set = 0, binding = 0) uniform UBO
{
    mat4 MVP;
} global;

#pragma stage vertex
layout(location = 0) in vec4 Position;
layout(location = 1) in vec2 TexCoord;
layout(location = 0) out vec2 vTexCoord;
void main()
{
    gl_Position = global.MVP * Position;
    vTexCoord = TexCoord;
}

#pragma stage fragment
layout(location = 0) in vec2 vTexCoord;
layout(location = 0) out vec4 FragColor;
layout(set = 0, binding = 2) uniform sampler2D Source;
void main()
{
    FragColor = vec4(texture(Source, vTexCoord).rgb, 1.0);
}
