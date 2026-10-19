#version 150

// 轨道打击合成器 v5.0：变焦模糊 + 色差 + bloom + 曝光 + 分级 + 颗粒 + 冲击帧。
// 算法移植自参考包 composite.fsh（10 tap 变焦、r² 色差、soft-screen bloom、
// 去饱和/对比分级、胶片颗粒、局部自适应阈值冲击帧），本模组另加黑体色温与协议色。
//
// 输入 DiffuseSampler 是主画面（OrbitalPostFx 的单趟 pass）。

#include "orbit_grade.glsl"

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
// v5.0 新增
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

in vec2 texCoord;
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
