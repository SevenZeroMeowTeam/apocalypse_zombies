#version 150

// 轨道光柱 v5.1：顶点着色器（世界空间圆柱 quad）。
// Java 每帧给出 24 段的圆柱网格，UV0 = (绕柱角/TAU, 沿柱高度)，法线只用于 ColorModulator。

uniform mat4 ModelViewMat;
uniform mat4 ProjMat;
uniform vec4 ColorModulator;

in vec3 Position;
in vec2 UV0;
in vec4 Color;

out vec2 texCoord0;
out vec4 vertexColor;

void main() {
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);
    texCoord0 = UV0;
    vertexColor = Color * ColorModulator;
}
