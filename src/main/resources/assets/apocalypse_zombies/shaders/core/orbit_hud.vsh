#version 150

// orbit_hud —— 我们的 HUD 图形层：一个形状 = 一个四边形。
//
// 顶点的位置已经被 Java 侧乘上过 GUI 的位姿矩阵（GuiGraphics.pose()），
// 这里再乘上 Minecraft 当前的模型矩阵与投影矩阵，把四边形放到屏幕上的正确位置。
// UV0 携带四边形自己的像素尺寸，顶点色携带形状本身，两样都在片元着色器里解释。

uniform mat4 ModelViewMat;
uniform mat4 ProjMat;

in vec3 Position;
in vec2 UV0;
in vec4 Color;

out vec2 texCoord0;
out vec4 vertexColor;

void main() {
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);
    texCoord0 = UV0;
    vertexColor = Color;
}
