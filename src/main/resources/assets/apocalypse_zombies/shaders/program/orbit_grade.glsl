#version 150

// 轨道打击合成器的共享工具（v5.0）。
// 算法移植自参考包 composite.fsh / star.glsl：黑体色温、色差随半径平方缩放、
// 径向变焦模糊、soft-screen bloom、对比分级、胶片颗粒、局部自适应阈值的冲击帧。
// 参数与配色按本模组重调；不使用参考包的任何资产。

float sqr(float x) { return x * x; }

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float vnoise2(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash12(i);
    float b = hash12(i + vec2(1.0, 0.0));
    float c = hash12(i + vec2(0.0, 1.0));
    float d = hash12(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

vec3 blackbody(float x) {
    vec3 c = mix(vec3(0.3, 0.01, 0.0), vec3(1.0, 0.25, 0.02), smoothstep(0.0, 0.45, x));
    c = mix(c, vec3(1.0, 0.68, 0.22), smoothstep(0.4, 0.85, x));
    return mix(c, vec3(1.0, 0.95, 0.85), smoothstep(0.85, 1.25, x));
}

/**
 * 冲击帧：Sobel 墨线 + 局部自适应阈值 + 旋转网点（移植自参考包 composite.fsh）。
 *
 * 关键点：阈值不是全局常数，而是与**周围 8 点平均亮度**比较 —— 所以白闪把画面推向全白时，
 * 形状依然成立（参考包特意解决过的问题）。
 *
 * mode 0  墨线（双色调 + 墨边）
 * mode 1  反相
 * mode 2  绯红（红黑双色）
 * mode 3  墨线 + 青饰
 * mode 4  半调网点（旋转点阵，点径随中间调暗度）
 * mode 5  余烬线稿（黑体色描边）
 */
vec3 impactFrame(vec2 texCoord, vec2 outSize, float time, float strength, float mode,
                 vec3 accent, vec2 center) {
    float aspect = outSize.x / max(outSize.y, 1.0);
    vec2 step1 = 1.5 / outSize;
    float gx = lum(texture(DiffuseSampler, texCoord + vec2(step1.x, 0.0)).rgb)
             - lum(texture(DiffuseSampler, texCoord - vec2(step1.x, 0.0)).rgb);
    float gy = lum(texture(DiffuseSampler, texCoord + vec2(0.0, step1.y)).rgb)
             - lum(texture(DiffuseSampler, texCoord - vec2(0.0, step1.y)).rgb);
    float ink = smoothstep(0.06, 0.18, length(vec2(gx, gy)));
    float l = lum(texture(DiffuseSampler, texCoord).rgb);

    float avg = 0.0;
    for (int i = 0; i < 8; i++) {
        float a = float(i) * 0.785398;
        avg += lum(texture(DiffuseSampler,
                texCoord + vec2(cos(a) / aspect, sin(a)) * 0.045).rgb);
    }
    avg /= 8.0;

    vec2 d = (texCoord - center) * vec2(aspect, 1.0);
    float ang = atan(d.y, d.x);
    vec3 frame;
    float core = step(avg + 0.18, l);

    if (mode < 0.5) {
        // 0 墨线
        float two = step(avg + 0.004, l);
        vec3 paper = vec3(0.96, 0.94, 0.90);
        frame = mix(vec3(0.04, 0.04, 0.05), paper, two);
        frame = mix(frame, vec3(0.02), ink * 0.85);
        frame = mix(frame, vec3(1.0), core * 0.85);
    } else if (mode < 1.5) {
        // 1 反相
        frame = mix(vec3(0.02, 0.02, 0.03), vec3(0.98, 0.97, 0.95),
                    step(avg + 0.02, l));
        frame = 1.0 - frame;
    } else if (mode < 2.5) {
        // 2 绯红
        float two = step(avg + 0.004, l);
        frame = mix(vec3(0.16, 0.01, 0.02), vec3(1.0, 0.86, 0.80), two);
        frame = mix(frame, accent * 0.5, ink * 0.5);
    } else if (mode < 3.5) {
        // 3 墨线 + 青饰
        float two = step(avg + 0.004, l);
        frame = mix(vec3(0.03, 0.04, 0.06), vec3(0.93, 0.95, 0.97), two);
        float edge = pow(ink, 1.2);
        frame = mix(frame, accent * 1.4, edge * 0.75);
        frame = mix(frame, vec3(1.0), core * 0.7);
    } else if (mode < 4.5) {
        // 4 半调网点（移植自参考包的旋转点阵）
        vec2 tp = mat2(0.7071, -0.7071, 0.7071, 0.7071) * (texCoord * outSize) / 5.0;
        float tone = clamp((l - avg) * 5.0 + 0.5, 0.0, 1.0);
        float dots = step(length(fract(tp) - 0.5),
                          sqrt(clamp(1.0 - tone, 0.0, 1.0)) * 0.62);
        float mid = smoothstep(0.15, 0.35, tone) * (1.0 - smoothstep(0.65, 0.85, tone));
        frame = mix(vec3(0.05), vec3(0.97, 0.96, 0.93), tone);
        frame = mix(frame, vec3(0.06), dots * (0.35 + 0.4 * mid));
        frame = mix(frame, vec3(1.0), core * 0.9);
    } else {
        // 5 余烬线稿（黑体色描边）
        float two = step(avg + 0.004, l);
        frame = mix(vec3(0.02, 0.01, 0.01), vec3(0.14, 0.09, 0.06), two);
        frame = mix(frame, blackbody(0.55 + 0.45 * pow(ink, 0.7)) * 1.6,
                    pow(ink, 0.8) * 0.9);
        frame = mix(frame, blackbody(1.1), core);
    }
    // 边缘按 strength 淡出，中心保持（冲击从落点扩散）
    float falloff = 1.0 - smoothstep(0.15, 1.35, length(d)) * 0.55;
    return mix(vec3(l), frame, clamp(strength * falloff, 0.0, 1.0));
}

/** 色差抽样：r/b 沿径向分离，强度随到中心距离的平方增长（移植自参考包 fetch()）。 */
vec3 chromaticFetch(vec2 uv, vec2 dir, float ca) {
    if (ca < 1e-5) {
        return texture(DiffuseSampler, clamp(uv, 0.0015, 0.9985)).rgb;
    }
    return vec3(
        texture(DiffuseSampler, clamp(uv + dir * ca, 0.0015, 0.9985)).r,
        texture(DiffuseSampler, clamp(uv, 0.0015, 0.9985)).g,
        texture(DiffuseSampler, clamp(uv - dir * ca, 0.0015, 0.9985)).b);
}

/** 径向变焦模糊：沿「中心 → 像素」方向多抽样（移植自参考包的 10 tap 循环）。 */
vec3 zoomBlurSample(vec2 uv, vec2 c, float amount) {
    vec3 acc = texture(DiffuseSampler, clamp(uv, 0.0015, 0.9985)).rgb;
    float total = 1.0;
    for (int i = 1; i < 10; i++) {
        float k = float(i) / 10.0;
        vec2 suv = 0.5 + c * (1.0 - amount * 0.12 * k);
        float w = 1.0 - k * 0.6;
        acc += texture(DiffuseSampler, clamp(suv, 0.0015, 0.9985)).rgb * w;
        total += w;
    }
    return acc / total;
}
