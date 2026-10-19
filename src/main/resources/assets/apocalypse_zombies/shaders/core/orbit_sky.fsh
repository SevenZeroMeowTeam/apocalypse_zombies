#version 150

// 程序化太空背景：星空 + 银河带 + 星云（无贴图、无 FBO）。
// 由 OrbitSkyShader 每帧传入相机三轴与 FOV，片元里按屏幕坐标重建视线方向。

uniform vec3 CamForward;
uniform vec3 CamRight;
uniform vec3 CamUp;
uniform float TanHalf;
uniform float Aspect;
uniform float Alpha;
uniform float GameTime;

in vec2 vUV;
out vec4 fragColor;

float hash(vec3 p) {
    p = fract(p * 0.3183099 + vec3(0.1, 0.2, 0.3));
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float noise(vec3 x) {
    vec3 i = floor(x);
    vec3 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(
        mix(mix(hash(i + vec3(0, 0, 0)), hash(i + vec3(1, 0, 0)), f.x),
            mix(hash(i + vec3(0, 1, 0)), hash(i + vec3(1, 1, 0)), f.x), f.y),
        mix(mix(hash(i + vec3(0, 0, 1)), hash(i + vec3(1, 0, 1)), f.x),
            mix(hash(i + vec3(0, 1, 1)), hash(i + vec3(1, 1, 1)), f.x), f.y),
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

void main() {
    vec3 dir = normalize(CamForward
            + CamRight * (vUV.x * TanHalf * Aspect)
            + CamUp * (vUV.y * TanHalf));

    // 星云：低频 FBM + 缓慢流动
    vec3 flow = dir * 2.6 + vec3(0.0, GameTime * 0.0025, GameTime * 0.0015);
    float n = fbm(flow);
    float n2 = fbm(dir * 6.0 - vec3(GameTime * 0.001));

    vec3 col = vec3(0.008, 0.010, 0.022);
    col += vec3(0.22, 0.05, 0.30) * smoothstep(0.52, 0.92, n) * 0.55;
    col += vec3(0.05, 0.16, 0.30) * smoothstep(0.48, 0.88, n2) * 0.50;

    // 银河带：沿一个倾斜大圆
    float band = exp(-pow((dir.y * 2.6 + sin(dir.x * 2.0) * 0.18), 2.0) * 3.0);
    col += vec3(0.20, 0.19, 0.26) * band * 0.45;
    col += vec3(0.55, 0.58, 0.70) * pow(band, 6.0) * 0.20;

    // 星点：网格哈希，越靠近银河带越密
    vec3 q = dir * 240.0;
    vec3 cell = floor(q);
    vec3 f = fract(q) - 0.5;
    float h = hash(cell);
    float threshold = 0.986 - band * 0.010;
    if (h > threshold) {
        float star = max(0.0, 1.0 - length(f) * 2.2);
        star = pow(star, 1.8);
        vec3 tint = mix(vec3(0.75, 0.85, 1.0), vec3(1.0, 0.88, 0.70), hash(cell + 7.0));
        col += tint * star * 1.6;
    }

    // 远处太阳
    vec3 sunDir = normalize(vec3(0.55, 0.22, 0.80));
    float sun = pow(max(dot(dir, sunDir), 0.0), 220.0);
    float halo = pow(max(dot(dir, sunDir), 0.0), 18.0);
    col += vec3(1.0, 0.88, 0.68) * sun * 2.2;
    col += vec3(1.0, 0.72, 0.42) * halo * 0.18;

    // —— 地球：解析球体 + 程序化大陆/云/夜面灯光/大气边缘
    vec3 earthDir = normalize(vec3(-0.35, -0.12, 0.93));
    float er = 0.255;
    float eb = dot(dir, earthDir);
    float earthCos = cos(er);
    if (eb > earthCos) {
        vec3 t = normalize(cross(earthDir, vec3(0.0, 1.0, 0.0)));
        vec3 s = cross(earthDir, t);
        float sinR = sin(er);
        vec2 p = vec2(dot(dir, t), dot(dir, s)) / sinR;
        float z = sqrt(max(0.0, 1.0 - dot(p, p)));
        vec3 n = normalize(t * p.x + s * p.y - earthDir * z);

        float land = fbm(n * 3.1 + 11.0);
        float detail = fbm(n * 9.0);
        vec3 ocean = vec3(0.025, 0.09, 0.26);
        vec3 landCol = mix(vec3(0.09, 0.23, 0.09), vec3(0.36, 0.30, 0.16),
                           smoothstep(0.25, 0.65, detail));
        vec3 surf = mix(ocean, landCol, smoothstep(0.50, 0.58, land));

        float clouds = smoothstep(0.52, 0.72, fbm(n * 5.0 + vec3(GameTime * 0.0009)));
        surf = mix(surf, vec3(0.92, 0.94, 0.97), clouds * 0.85);

        float light = clamp(dot(n, sunDir) * 1.7 + 0.12, 0.0, 1.0);
        surf *= light;
        float city = step(0.975, hash(floor(n * 110.0))) * (1.0 - light);
        surf += vec3(1.0, 0.74, 0.32) * city * 0.45;

        float rim = smoothstep(0.78, 1.0, length(p));
        surf += vec3(0.28, 0.58, 1.0) * rim * 0.55;
        col = surf;
    }
    // 大气外晕
    float earthHalo = smoothstep(cos(er * 1.20), cos(er), eb) - step(earthCos, eb);
    col += vec3(0.20, 0.46, 1.0) * max(earthHalo, 0.0) * 0.35;

    fragColor = vec4(col * Alpha, Alpha);
}
