#version 150

// 轨道光柱 v5.1（移植参考包 star_beam.fsh 的体积渐变，改用世界空间圆柱 quad 提供径向坐标）。
//
// 参考包用屏幕空间深度重建；我们不建深度副本（Embeddium 下风险高），改由 Java 画一根面向相机的
// 圆柱 quad，UV0.x = 绕柱角度 / TAU，UV0.y = 沿柱高度 0..1，fsh 据此算 x = 面向相机程度。
//
// 算法照抄：四段体积渐变（heart 白热 / hot / red / deep）、绕柱能量条纹、边缘皮肤、
// 空气雾、上下端淡出。

uniform mat4 ModelViewMat;
uniform mat4 ProjMat;
uniform vec4 ColorModulator;

uniform float GameTime;   // 秒
uniform float Radius;     // 柱半径（格）
uniform float Strength;   // 总强度 0..1
uniform float Energy;     // 能量条纹强度 0..1
uniform float Haze;       // 空气雾 0..1
uniform vec3 Core;        // 中心色（白热）
uniform vec3 Body;        // 主体色
uniform vec3 Deep;        // 外缘色
uniform float Scanline;   // 绕柱扫描线速度（0 = 关）

in vec2 texCoord0;
in vec4 vertexColor;
out vec4 fragColor;

const float PI = 3.14159265;

float sqr(float x) { return x * x; }

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float bnoise2(vec2 x) {
    vec2 i = floor(x);
    vec2 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x),
               mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}

float fbm2(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 4; i++) {
        v += a * bnoise2(p);
        p *= 2.03;
        a *= 0.5;
    }
    return v;
}

/** 黑体色温（与 orbit_sky 同一套）。 */
vec3 blackbody(float x) {
    vec3 c = mix(vec3(0.3, 0.01, 0.0), vec3(1.0, 0.25, 0.02), smoothstep(0.0, 0.45, x));
    c = mix(c, vec3(1.0, 0.68, 0.22), smoothstep(0.4, 0.85, x));
    return mix(c, vec3(1.0, 0.95, 0.85), smoothstep(0.85, 1.25, x));
}

void main() {
    // UV0.x：0..1 绕柱一周；UV0.y：0 柱底 → 1 柱顶
    float ang = texCoord0.x * PI * 2.0;
    float h = texCoord0.y;
    // 面向相机一侧：用 cos(ang)，背面的亮度低一些（体积感）
    float faceT = 0.5 + 0.5 * cos(ang);

    float x = faceT;                       // 0 背缘 → 1 中心线
    float R = max(Radius, 0.05);

    // —— 四段体积渐变（deep / red / hot / heart），照抄参考包的过渡位置
    vec3 c = mix(Deep, Body, smoothstep(0.55, 0.18, x));
    c = mix(c, Core * 0.92, smoothstep(0.42, 0.10, x));
    c = mix(c, Core, smoothstep(0.24, 0.0, x) * 0.85);

    // —— 绕柱能量条纹：fbm 沿高度滚动 + 角向条带
    float fall = GameTime * (60.0 + 200.0 * Energy);
    float streak = fbm2(vec2(ang * R * 0.05 + h * 0.6, (h * 220.0 + fall) * 0.016));
    float bands = 0.5 + 0.5 * sin((h * 260.0 + fall * 1.5) * 0.04 + ang * 3.0);
    float energy = (0.7 + 0.45 * streak * (0.6 + 0.4 * bands)) * Energy;
    c *= energy;
    // 中心线上更亮（白热芯）
    c += Core * pow(x, 6.0) * 0.9 * Energy;

    // —— 绕柱扫描线：一道亮环沿柱上升（协议特效用）
    if (Scanline > 0.001) {
        float s = fract(h * 1.3 - GameTime * Scanline);
        c += Core * exp(-sqr(s - 0.5) * 260.0) * 0.55;
    }

    // —— 边缘加亮（skin）：贴柱壁一圈炽热
    float skin = exp(-sqr(1.0 - x) * 7.0);
    c += Body * skin * 0.35;

    // —— 上下端淡出：避免 quad 边界硬切
    float cap = smoothstep(0.0, 0.06, h) * smoothstep(1.0, 0.94, h);
    float alpha = clamp(Strength * (0.35 + 0.65 * faceT) * cap, 0.0, 1.0);

    // —— 空气雾：靠近柱壁时混一层主体色
    if (Haze > 0.001) {
        float nearEdge = 1.0 - x;
        c = mix(c, Body * 1.5, clamp(Haze * nearEdge * 1.4, 0.0, 0.55));
    }

    // 顶点色（协议色调）只做轻微染色，别把体积渐变压掉
    vec3 tint = vertexColor.rgb * ColorModulator.rgb;
    c = mix(c, c * tint * 1.6, 0.22);

    fragColor = vec4(max(c, vec3(0.0)), alpha);
}
