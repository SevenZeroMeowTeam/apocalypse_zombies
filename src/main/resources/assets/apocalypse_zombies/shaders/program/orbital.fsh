#version 150

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

in vec2 texCoord;
out vec4 fragColor;

vec3 sampleDiffuse(vec2 uv) {
    return texture(DiffuseSampler, clamp(uv, vec2(0.0015), vec2(0.9985))).rgb;
}

void main() {
    vec2 uv = texCoord;
    vec2 center = vec2(0.5);
    vec2 delta = uv - center;
    float radius = length(delta);
    float strength = clamp(Strength, 0.0, 1.0);
    float radial = clamp(Radial, 0.0, 1.0) * strength;

    // —— 径向模糊：沿「屏幕中心 → 像素」方向多抽样。
    vec3 color = vec3(0.0);
    float weightSum = 0.0;
    float blur = radial * 0.075;
    for (int i = 0; i < 8; i++) {
        float t = float(i) / 7.0;
        float scale = 1.0 + blur * t;
        float weight = 1.0 - 0.55 * t;
        color += sampleDiffuse(center + delta * scale) * weight;
        weightSum += weight;
    }
    color /= weightSum;

    // —— 色差：红/蓝沿径向分离。
    float chroma = clamp(Chroma, 0.0, 1.0) * strength;
    vec2 split = delta * (chroma * 0.014);
    float r = sampleDiffuse(uv + split).r;
    float b = sampleDiffuse(uv - split).b;
    color = mix(color, vec3(r, color.g, b), chroma);

    // —— 廉价 bloom：四向亮度溢出，命中时更强。
    float impact = clamp(Impact, 0.0, 1.0);
    vec3 bloom = vec3(0.0);
    bloom += max(sampleDiffuse(uv + vec2(0.0045, 0.0)) - 0.70, 0.0);
    bloom += max(sampleDiffuse(uv - vec2(0.0045, 0.0)) - 0.70, 0.0);
    bloom += max(sampleDiffuse(uv + vec2(0.0, 0.0045)) - 0.70, 0.0);
    bloom += max(sampleDiffuse(uv - vec2(0.0, 0.0045)) - 0.70, 0.0);
    color += bloom * (0.30 + 0.55 * impact) * strength;

    // —— 命中白闪。
    color = mix(color, vec3(1.0, 0.975, 0.93), clamp(Flash, 0.0, 0.92) * strength);

    // —— 调色（冷紫/协议色由 Java 传入）。
    color *= 1.0 + Grade * 0.55 * strength;
    color += Grade * 0.035 * strength;

    // —— 暗角。
    float vig = smoothstep(0.30, 0.92, radius);
    color *= 1.0 - vig * clamp(Vignette, 0.0, 1.0) * strength;

    fragColor = vec4(max(color, vec3(0.0)), 1.0);
}
