#version 150

// 轨道打击用的 bloom 升采样（参考 The Shooting Star 的 fx/bloom_up.fsh）。
//
// 9 抽样 tent 滤波：中心 4 权重、轴向 2 权重、对角 1 权重，除以 16。
// 滤波结果再加到「下面一级」的降采样结果上（AuxSampler），这一步的加法在 shader 里做，
// 不依赖 GL 加法混合 —— 和参考实现一致。
//
// 同一个 program 也兼做最后的合成：Radius = 0 时 9 个抽样全部落在同一个点上，
// tent 权重塌缩成 1.0，于是 fragColor = 被采样的那层 * Strength + AuxSampler。
// 合成时 DiffuseSampler = 最终 bloom 纹理，AuxSampler = 场景，Strength = bloom 强度。
//
// 注意：Minecraft 的 program shader 不允许 #include，辅助代码全部内联。

uniform sampler2D DiffuseSampler;   // 被采样的那一层（更小的一级 / 最终 bloom）
uniform sampler2D AuxSampler;       // 叠加目标（下面一级 / 场景）
uniform vec2 InSize;                // DiffuseSampler 的尺寸，由 PostPass 写入
uniform float Radius;               // tent 滤波半径（输入纹素）；0 = 不滤波
uniform float Strength;             // 被采样那层的贡献强度

in vec2 texCoord;
out vec4 fragColor;

void main() {
    vec2 uv = texCoord;
    vec2 ts = (1.0 / max(InSize, vec2(1.0))) * Radius;
    vec3 s = texture(DiffuseSampler, uv).rgb * 4.0;
    s += (texture(DiffuseSampler, uv + ts * vec2(-1.0, 0.0)).rgb
        + texture(DiffuseSampler, uv + ts * vec2(1.0, 0.0)).rgb
        + texture(DiffuseSampler, uv + ts * vec2(0.0, -1.0)).rgb
        + texture(DiffuseSampler, uv + ts * vec2(0.0, 1.0)).rgb) * 2.0;
    s += texture(DiffuseSampler, uv + ts * vec2(-1.0, -1.0)).rgb
        + texture(DiffuseSampler, uv + ts * vec2(1.0, -1.0)).rgb
        + texture(DiffuseSampler, uv + ts * vec2(-1.0, 1.0)).rgb
        + texture(DiffuseSampler, uv + ts * vec2(1.0, 1.0)).rgb;
    fragColor = vec4(s / 16.0 * Strength + texture(AuxSampler, uv).rgb, 1.0);
}
