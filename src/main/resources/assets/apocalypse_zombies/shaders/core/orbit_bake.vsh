#version 150

// 太空烘焙 shader 的顶点入口：全屏四边形。
// 复用 orbit_space.vsh 的做法 —— NDC 坐标原样传给片元，方向由片元自己反算。

in vec3 Position;
out vec2 vUV;

void main() {
    vUV = Position.xy;
    gl_Position = vec4(Position.xy, 0.9999, 1.0);
}
