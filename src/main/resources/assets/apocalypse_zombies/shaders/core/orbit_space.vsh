#version 150

// 轨道打击「太空全景」的顶点着色器：全屏四边形。
//
// Minecraft 的 core shader 顶点格式是 POSITION（裁剪空间坐标），
// 这里把 NDC 原样传给片元，由片元按相机四元组重建视线。

in vec3 Position;
out vec2 texCoord0;

void main() {
    texCoord0 = Position.xy;
    gl_Position = vec4(Position.xy, 0.9999, 1.0);
}
