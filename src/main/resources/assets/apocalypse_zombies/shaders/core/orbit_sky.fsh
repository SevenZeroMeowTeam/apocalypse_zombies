#version 150

// 程序化太空背景 v5.0：星空 + 银河 + 星云 + 地球 + 月球 + 太阳。
// 星空/星云/云的算法移植自参考包 star.glsl（三层星点+星等分布+闪烁、fbm 银河尘带、
// 黑体色温），参数与配色按本模组重调；地球/月球为本项目原创解析球体。
//
// 由 OrbitSkyShader 每帧传入相机三轴、FOV 与 GameTime（秒）。

uniform vec3 CamForward;
uniform vec3 CamRight;
uniform vec3 CamUp;
uniform float TanHalf;
uniform float Aspect;
uniform float Alpha;
uniform float GameTime;

in vec2 vUV;
out vec4 fragColor;

const float TAU = 6.2831853;
const float PI = 3.14159265;

float hash13(vec3 p) {
    p = fract(p * 0.3183099 + vec3(0.1, 0.2, 0.3));
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float noise(vec3 x) {
    vec3 i = floor(x);
    vec3 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(
        mix(mix(hash13(i), hash13(i + vec3(1, 0, 0))), mix(hash13(i + vec3(0, 1, 0)), hash13(i + vec3(1, 1, 0))), f.y),
        mix(mix(hash13(i + vec3(0, 0, 1)), hash13(i + vec3(1, 0, 1))), mix(hash13(i + vec3(0, 1, 1)), hash13(i + vec3(1, 1, 1))), f.y),
        f.z);
}

float fbm(vec3 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 5; i++) {
        v += a * noise(p);
        p *= 2.03;
        a *= 0.5;
    }
    return v;
}

float sqr(float x) { return x * x; }

/** 黑体色温（移植自参考包 star.glsl）：高温→白热，低温→暗红。 */
vec3 blackbody(float x) {
    vec3 c = mix(vec3(0.3, 0.01, 0.0), vec3(1.0, 0.25, 0.02), smoothstep(0.0, 0.45, x));
    c = mix(c, vec3(1.0, 0.68, 0.22), smoothstep(0.4, 0.85, x));
    return mix(c, vec3(1.0, 0.95, 0.85), smoothstep(0.85, 1.25, x));
}

/** 点光源：硬核 + 长而软的晕（移植自参考包 star.glsl）。 */
float pointGlow(float d, float pix, float size) {
    float x = d / (pix * size);
    return exp(-x * x) + 0.06 / (1.0 + x * x * 0.4);
}

/** 面向某方向的平面坐标轴（移植自参考包 star.glsl）。 */
void facing(vec3 n, out vec3 ax, out vec3 ay) {
    ax = normalize(cross(n, abs(n.y) < 0.9 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0)));
    ay = cross(ax, n);
}

/**
 * 三层星空：远/中/近三组格点星，星等按哈希幂分布，各自频率闪烁，
 * 色温在蓝白→橙金之间分布。移植自参考包 star.glsl 的 starField，参数重调。
 */
vec3 starField(vec3 rd, float pix) {
    vec3 col = vec3(0.0);
    for (int layer = 0; layer < 3; layer++) {
        float fl = float(layer);
        float scale = layer == 0 ? 90.0 : layer == 1 ? 210.0 : layer == 2 ? 430.0;
        vec3 id = floor(rd * scale);
        float h = hash13(id + fl * 17.0);
        if (h > (layer == 0 ? 0.055 : layer == 1 ? 0.045 : 0.035)) continue;
        vec3 sd = normalize(id + 0.2 + 0.6 * vec3(hash13(id + 3.1), hash13(id + 7.7), hash13(id + 11.3)));
        float a = length(rd - sd);
        float size = layer == 0 ? 1.15 : layer == 1 ? 0.85 : 0.6;
        float mag = sqr(sqr(hash13(id + 5.9))) * hash13(id + 5.9) * (layer == 0 ? 7.0 : 2.2)
                + (layer == 2 ? 0.10 : 0.18);
        float twinkle = 0.78 + 0.22 * sin(GameTime * (2.0 + h * 40.0) + h * 97.0);
        vec3 tint = mix(vec3(0.62, 0.76, 1.0), vec3(1.0, 0.84, 0.64), hash13(id + 2.3));
        col += tint * mag * twinkle * exp(-sqr(a / (pix * size))) * 0.35;
    }
    return col;
}

/**
 * 深场：远处星系的小光斑与螺旋（移植自参考包 star.glsl 的 deepField，简化）。
 */
vec3 deepField(vec3 rd, float pix) {
    vec3 col = vec3(0.0);
    for (int layer = 0; layer < 2; layer++) {
        float fl = float(layer);
        float scale = layer == 0 ? 26.0 : 60.0;
        vec3 cell = floor(rd * scale);
        float h = hash13(cell + fl * 31.0);
        if (h > (layer == 0 ? 0.06 : 0.08)) continue;
        vec3 c = normalize(cell + 0.3 + 0.4 * vec3(hash13(cell + 1.3), hash13(cell + 2.9), hash13(cell + 5.1)));
        vec3 ax, ay;
        facing(c, ax, ay);
        vec3 d = rd - c;
        vec2 q = vec2(dot(d, ax), dot(d, ay)) / pix;
        float size = (layer == 0 ? 3.6 : 2.1) * (0.5 + hash13(cell + 11.0));
        q.y /= mix(0.22, 1.0, hash13(cell + 9.1));
        float r = length(q) / size;
        if (r > 4.0) continue;
        float spiral = step(0.45, hash13(cell + 13.0));
        float arms = spiral * (0.55 + 0.45 * sin(2.0 * atan(q.y, q.x + 1e-6) - 4.0 * log(r + 0.15)));
        float body = exp(-r * r * 1.4) * mix(1.0, arms, 0.6 * spiral) + exp(-r * r * 14.0) * 0.9;
        vec3 tint = mix(vec3(1.0, 0.78, 0.5), vec3(0.62, 0.74, 1.0), hash13(cell + 17.0));
        col += tint * body * (layer == 0 ? 0.22 : 0.12);
    }
    return col;
}

/** 地球/月球共用的表面计算（fbm 地形 + 云 + 光照 + 冰盖 + 海面镜面高光）。 */
vec3 bodySurface(vec3 dir, vec3 centerDir, float er, vec3 sunDir,
                 float landFreq, vec3 landA, vec3 landB, vec3 ocean,
                 float cloudFreq, float cloudAmount, float cityAmount, float rimColor) {
    vec3 t = normalize(cross(centerDir, abs(centerDir.y) < 0.9 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0)));
    vec3 s = cross(centerDir, t);
    vec2 p = vec2(dot(dir, t), dot(dir, s)) / sin(er);
    float z = sqrt(max(0.0, 1.0 - dot(p, p)));
    vec3 n = normalize(t * p.x + s * p.y - centerDir * z);

    float land = fbm(n * landFreq + 11.0);
    float detail = fbm(n * (landFreq * 3.0));
    vec3 surf = mix(ocean, mix(landA, landB, smoothstep(0.25, 0.65, detail)),
                    smoothstep(0.50, 0.58, land));
    // 高纬冰盖
    float ice = smoothstep(0.72, 0.93, abs(n.y));
    surf = mix(surf, vec3(0.86, 0.90, 0.95), ice * 0.85);
    // 海面镜面高光（参考图里最明显的那一块）
    float spec = pow(max(dot(reflect(-sunDir, n), normalize(dir - centerDir * 0.0)), 0.0), 40.0);
    surf += vec3(1.0, 0.86, 0.66) * spec * (1.0 - ice) * 0.55 * step(0.5, land);

    if (cloudAmount > 0.0) {
        float clouds = smoothstep(0.52, 0.72, fbm(n * cloudFreq + vec3(GameTime * 0.0009, 0.0, 0.0)));
        surf = mix(surf, vec3(0.92, 0.94, 0.97), clouds * cloudAmount);
    }

    float light = clamp(dot(n, sunDir) * 1.7 + 0.12, 0.0, 1.0);
    surf *= light;
    if (cityAmount > 0.0) {
        float city = step(0.974, hash13(floor(n * 110.0))) * (1.0 - light);
        surf += vec3(1.0, 0.74, 0.32) * city * cityAmount;
    }
    float rim = smoothstep(0.78, 1.0, length(p));
    surf += vec3(0.28, 0.58, 1.0) * rim * rimColor;
    return surf;
}

void main() {
    vec3 dir = normalize(CamForward
            + CamRight * (vUV.x * TanHalf * Aspect)
            + CamUp * (vUV.y * TanHalf));
    float pix = TanHalf / 720.0;   // 每像素对应的角尺寸（近似）

    // —— 深空底色
    vec3 col = vec3(0.006, 0.008, 0.020);

    // —— 银河：沿一条倾斜大圆，尘带用 fbm 做出明暗絮状
    float band = exp(-pow((dir.y * 2.6 + sin(dir.x * 2.0) * 0.18), 2.0) * 3.0);
    float dust = fbm(dir * 7.0 + 3.0);
    float dustLane = 1.0 - smoothstep(0.35, 0.62, dust);
    col += vec3(0.20, 0.19, 0.26) * band * (0.42 + 0.25 * dustLane);
    col += vec3(0.55, 0.58, 0.70) * pow(band, 6.0) * 0.20;
    // 银河亮核（人马座方向）
    vec3 coreDir = normalize(vec3(-0.55, 0.32, 0.77));
    col += vec3(0.95, 0.82, 0.62) * pow(max(dot(dir, coreDir), 0.0), 8.0) * band * 0.35;

    // —— 星云：低频 FBM + 缓慢流动
    float n = fbm(dir * 2.6 + vec3(0.0, GameTime * 0.0025, GameTime * 0.0015));
    float n2 = fbm(dir * 6.0 - vec3(GameTime * 0.001));
    col += vec3(0.22, 0.05, 0.30) * smoothstep(0.52, 0.92, n) * 0.50;
    col += vec3(0.05, 0.16, 0.30) * smoothstep(0.48, 0.88, n2) * 0.45;

    // —— 星点：参考包的三层星场（星等 + 闪烁 + 色温）
    col += starField(dir, pix);

    // —— 深场星系
    col += deepField(dir, pix);

    // —— 太阳：黑体色 + pointGlow 晕
    vec3 sunDir = normalize(vec3(0.55, 0.22, 0.80));
    float sunD = length(dir - sunDir);
    col += blackbody(1.15) * pointGlow(sunD, pix, 3.0) * 2.4;
    col += vec3(1.0, 0.72, 0.42) * pow(max(dot(dir, sunDir), 0.0), 18.0) * 0.16;

    // —— 地球：解析球体
    vec3 earthDir = normalize(vec3(-0.35, -0.12, 0.93));
    float er = 0.255;
    float eb = dot(dir, earthDir);
    float earthCos = cos(er);
    if (eb > earthCos) {
        col = bodySurface(dir, earthDir, er, sunDir,
                3.1, vec3(0.09, 0.23, 0.09), vec3(0.36, 0.30, 0.16), vec3(0.025, 0.09, 0.26),
                5.0, 0.85, 0.45, 0.55);
    }
    // 大气外晕：三层外扩 + 蓝边
    float earthHalo = smoothstep(cos(er * 1.20), cos(er), eb) - step(earthCos, eb);
    col += vec3(0.20, 0.46, 1.0) * max(earthHalo, 0.0) * 0.35;

    // —— 月球：更小、无云、无海、环形山（与地球同日照方向）
    vec3 moonDir = normalize(vec3(0.62, 0.30, -0.42));
    float mr = 0.075;
    float mb = dot(dir, moonDir);
    if (mb > cos(mr)) {
        vec3 t = normalize(cross(moonDir, abs(moonDir.y) < 0.9 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0)));
        vec3 s = cross(moonDir, t);
        vec2 p = vec2(dot(dir, t), dot(dir, s)) / sin(mr);
        vec3 n = normalize(t * p.x + s * p.y - moonDir * sqrt(max(0.0, 1.0 - dot(p, p))));
        // 月海（暗玄武岩）+ 高地（亮岩）
        float mare = smoothstep(0.44, 0.58, fbm(n * 4.0 + 21.0));
        vec3 surf = mix(vec3(0.44, 0.42, 0.40), vec3(0.66, 0.64, 0.62), 1.0 - mare);
        // 环形山：径向冲击的圆形凹陷
        float craters = 0.0;
        for (int i = 0; i < 3; i++) {
            vec3 cid = floor(n * (14.0 + float(i) * 26.0));
            float ch = hash13(cid + float(i) * 7.0);
            if (ch < 0.90) continue;
            vec3 cp = (cid + 0.5) / (14.0 + float(i) * 26.0);
            float cd = length(n - normalize(cp));
            float crater = step(cd, 0.16 / (1.0 + float(i)));
            craters += crater * (0.25 + 0.35 * hash13(cid + 3.0));
        }
        surf *= 1.0 - craters * 0.35;
        // 边缘暗化 + 自发光夜面（新月时也能看见轮廓）
        float light = clamp(dot(n, sunDir) * 1.7 + 0.12, 0.0, 1.0);
        surf *= light;
        float rim = smoothstep(0.80, 1.0, length(p));
        col = surf + vec3(0.55, 0.60, 0.72) * rim * 0.18;
    }

    fragColor = vec4(col * Alpha, Alpha);
}
