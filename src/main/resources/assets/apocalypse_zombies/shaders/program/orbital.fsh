#version 150

// 轨道打击合成器 v5.0：变焦模糊 + 色差 + bloom + 曝光 + 分级 + 颗粒 + 冲击帧。
// 算法移植自参考包 composite.fsh（10 tap 变焦、r² 色差、soft-screen bloom、
// 去饱和/对比分级、胶片颗粒、局部自适应阈值冲击帧），本模组另加黑体色温与协议色。
//
// 输入 DiffuseSampler 是主画面（OrbitalPostFx 的单趟 pass）。

// —— 共享工具（v5.0）：原 orbit_grade.glsl，直接内联。
// Minecraft 的 program 着色器不支持 import（EffectProgram 会报 #error），
// 所以这里必须内联而不是 #include。
uniform sampler2D DiffuseSampler;
uniform vec2 InSize;
uniform vec2 OutSize;
uniform float Time;
uniform float Strength;
uniform float Radial;
uniform float Chroma;
uniform float Impact;
uniform float Flash;
uniform float Vignette;
uniform vec3 Grade;
uniform float ZoomBlur;      // 径向变焦模糊量 0..1
uniform float Bloom;         // bloom 混合量 0..1
uniform float Desaturate;    // 去饱和 0..1
uniform float Contrast;      // 对比分级（黑白压制）0..1
uniform float Grain;         // 胶片颗粒 0..1
uniform float ImpactMode;    // 冲击帧样式 0..5
uniform float ImpactStrength;// 冲击帧强度 0..1
uniform vec2 ImpactCenter;   // 冲击帧中心（uv）
uniform float Exposure;      // 自动曝光开关 0/1
uniform vec3 Accent;         // 冲击帧/色差的强调色（协议色）
uniform vec2 ShaftPos;       // 光轴光源在屏幕上的位置（uv）
uniform float ShaftStrength; // 光轴强度 0..1

// 顶点阶段传来的屏幕坐标。
// **必须写在上面那些函数之前** —— GLSL 要求「先声明后使用」，
// 而下面几个工具函数都要读它。（v5.2 的 lightShafts 就因为这个顺序报错过。）
in vec2 texCoord;

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

/**
 * 光轴：从画面上每个像素往光源方向「走」一段路，把路上遇到的东西收集起来。
 *
 * <p>移植自参考包的 star_rays.fsh 的 {@code shafts()}：40 步、每步采一次画面、
 * 超过阈值的部分按权重累加、权重逐��衰减。抖动一下起点，避免 40 步的条纹感。</p>
 *
 * <p>参考包里这层作用在「炮体特写」那一遍上，靠 alpha 通道区分
 * 「能透光的地方」（天空、枪自己的灯）和「挡住的地方」（炮体），
 * 所以枪的格栅间会漏出光束。我们这边没有独立的炮体缓冲，
 * 改用画面自身的亮度当遮挡：暗的地方挡住光，亮的地方漏光 ——
 * 效果上等价于「光从打击点的亮处往外辐射」。</p>
 */
vec3 lightShafts(vec2 light, float reach, float threshold, float decay) {
    vec2 delta = (light - texCoord) * reach / 40.0;
    vec2 uv = texCoord;
    vec3 sum = vec3(0.0);
    float w = 1.0;
    // 抖动起点：40 步的固定起点会看出条纹
    uv += delta * hash12(texCoord * OutSize);
    for (int i = 0; i < 40; i++) {
        uv += delta;
        if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) {
            break;
        }
        vec3 s = texture(DiffuseSampler, clamp(uv, 0.0015, 0.9985)).rgb;
        float bright = max(lum(s) - threshold, 0.0) / (1.0 - threshold);
        sum += s * bright * w;
        w *= decay;
    }
    return sum / 40.0;
}

// v5.0 新增

out vec4 fragColor;

void main() {
    vec2 uv = texCoord;
    float t = Time;
    float strength = clamp(Strength, 0.0, 1.0);

    // —— 镜头抖动：两路噪声抖动整幅 uv（参考包 Shake 的简化版）
    vec2 jitter = vec2(vnoise2(vec2(t * 31.0, 1.7)), vnoise2(vec2(5.3, t * 29.0))) - 0.5;
    uv += jitter * 0.012 * strength;

    vec2 c = uv - 0.5;
    float aspect = OutSize.x / max(OutSize.y, 1.0);
    vec2 dir = c * vec2(aspect, 1.0);

    // —— 色差：强度随到中心距离平方增长
    float ca = clamp(Chroma, 0.0, 1.0) * 0.018 * dot(dir, dir) * 2.0 * strength;
    vec3 color = chromaticFetch(uv, dir, ca);

    // —— 径向变焦模糊（参考包 ZoomBlur）
    float zoom = clamp(ZoomBlur, 0.0, 1.0) * strength;
    if (zoom > 0.001) {
        color = mix(color, zoomBlurSample(uv, c, zoom), zoom);
    }

    // —— 径向速度模糊（参考包 composite.fsh 的 RadialBlur）：
    // 弹体朝镜头压下来时，画面沿「中心 → 像素」被拉出速度线。
    // Radial 由 Java 每帧给（下落段拉满），InSize 是主画面尺寸（用来按像素定步长）。
    float radial = clamp(Radial, 0.0, 1.0) * strength;
    if (radial > 0.001) {
        vec2 dirStep = dir / max(InSize.x, 1.0) * 26.0 * radial;
        vec3 acc = color;
        float wsum = 1.0;
        for (int i = 1; i < 6; i++) {
            float k = float(i) / 5.0;
            vec3 s = texture(DiffuseSampler, clamp(uv - dirStep * k, 0.0015, 0.9985)).rgb;
            float w = 1.0 - k * 0.55;
            acc += s * w;
            wsum += w;
        }
        color = acc / wsum;
    }

    // —— 廉价 bloom：四向亮度溢出
    float bloomAmount = clamp(Bloom, 0.0, 1.0) * strength;
    if (bloomAmount > 0.001) {
        float k = 0.0045;
        vec3 bloom = vec3(0.0);
        bloom += max(texture(DiffuseSampler, clamp(uv + vec2(k, 0.0), 0.0015, 0.9985)).rgb - 0.70, 0.0);
        bloom += max(texture(DiffuseSampler, clamp(uv - vec2(k, 0.0), 0.0015, 0.9985)).rgb - 0.70, 0.0);
        bloom += max(texture(DiffuseSampler, clamp(uv + vec2(0.0, k), 0.0015, 0.9985)).rgb - 0.70, 0.0);
        bloom += max(texture(DiffuseSampler, clamp(uv - vec2(0.0, k), 0.0015, 0.9985)).rgb - 0.70, 0.0);
        float impact = clamp(Impact, 0.0, 1.0);
        color += bloom * bloomAmount * (0.30 + 0.55 * impact);
    }

    // —— 光轴（移植自参考包 star_rays.fsh 的 shafts()）：
    // 从落点往外辐射的光束。ShaftPos 是光源在屏幕上的位置（Java 每帧算好），
    // ShaftStrength 控制强度，Threshold 是「多亮才算能透光」。
    float shaftStrength = clamp(ShaftStrength, 0.0, 1.0) * strength;
    if (shaftStrength > 0.001) {
        vec3 rays = lightShafts(ShaftPos, 1.0, 0.55, 0.975);
        // 光束取协议色（Accent），这样每种打击的光轴颜色不一样
        color += rays * Accent * shaftStrength * 2.2;
    }

    // —— 自动曝光：4×4 抽样估算场景亮度，亮则收光圈（参考包 exposure 的简化）
    if (Exposure > 0.5) {
        float added = 0.0;
        for (int i = 0; i < 16; i++) {
            vec2 p = (vec2(float(i - (i / 4) * 4), float(i / 4)) + 0.5) / 4.0;
            added += lum(texture(DiffuseSampler, p).rgb);
        }
        added /= 16.0;
        float ev = 1.0 / (1.0 + max(added - 0.05, 0.0) * 3.0);
        color *= mix(1.0, ev, strength);
    }

    // —— 冲击帧（移植自参考包，6 种样式 + 局部自适应阈值）
    float frameStrength = clamp(ImpactStrength, 0.0, 1.0) * strength;
    if (frameStrength > 0.001) {
        color = impactFrame(uv, OutSize, t, frameStrength, ImpactMode, Accent, ImpactCenter);
    } else if (Flash > 0.001) {
        // 没有冲击帧时，白闪按旧行为叠
        color = mix(color, vec3(1.0, 0.975, 0.93), clamp(Flash, 0.0, 0.92) * strength);
    }

    // —— 分级：去饱和 → 对比压制 → 协议色调色
    float grey = lum(color);
    color = mix(color, vec3(grey) * vec3(0.92, 1.0, 0.97), clamp(Desaturate, 0.0, 1.0) * strength);
    if (Contrast > 0.001) {
        color = clamp((color - 0.42) * (1.0 + clamp(Contrast, 0.0, 1.0) * strength) + 0.42, 0.0, 1.6);
    }
    color *= 1.0 + Grade * 0.55 * strength;
    color += Grade * 0.035 * strength;

    // —— 胶片颗粒（参考包 Grade.y）
    if (Grain > 0.001) {
        color += (hash12(texCoord * OutSize + fract(t * 7.3) * 431.0) - 0.5)
                 * clamp(Grain, 0.0, 1.0) * 0.2 * strength;
    }

    // —— 暗角
    float vig = smoothstep(0.30, 0.92, length(dir));
    color *= 1.0 - vig * clamp(Vignette, 0.0, 1.0) * strength;

    fragColor = vec4(max(color, vec3(0.0)), 1.0);
}
