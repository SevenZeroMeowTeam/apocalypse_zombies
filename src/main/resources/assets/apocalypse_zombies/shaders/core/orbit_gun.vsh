#version 150

// 轨道炮「弧光长矛」ARCLIGHT LANCE v1.0：顶点着色器。
// 与 orbit_sky 一样是一个全屏四边形：MC 用 POSITION 顶点格式把 (-1,-1)~(1,1)
// 的裁剪坐标直接送进来，这里原样传给片元，片元据此逐像素重建视线。
// 炮体本身完全在 shader 空间里光线步进，Java 侧只需给相机四元组。

in vec3 Position;
out vec2 vUV;

void main() {
    vUV = Position.xy;
    gl_Position = vec4(Position.xy, 0.9999, 1.0);
}
