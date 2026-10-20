#version 150

// 轨道打击用的 bloom 降采样（参考 The Shooting Star 的 fx/bloom_down.fsh）。
//
// 13 抽样 Jimenez/COD 滤波：4 个角点抽样 + 4 个轴向抽样 + 4 个内对角抽样 + 中心点。
//
// 首级（Prefilter = 1）先做一次亮部提取，两种模式：
//   DiffPrefilter = 0：普通阈值提取（Threshold 软拐点），整个画面一起进金字塔。
//   DiffPrefilter = 1：差分提取（移植参考包的 Prefilter 分支）——
//                      AuxSampler 拿的是「特效之前的那张画面」，
//                      差值就是特效本身，这样原版的天空和雪地不会整片糊掉。
//
// 注意：Minecraft 的 program shader 不允许 #include（EffectProgram 会直接报
// “#error Import statement not supported”），所以辅助函数全部内联在这里。

uniform sampler2D DiffuseSampler;   // 输入（场景或上一级）
uniform sampler2D AuxSampler;       // 特效之前的画面（只在 DiffPrefilter = 1 时用）
uniform vec2 InSize;                // 输入纹理尺寸（像素），由 PostPass 写入
uniform float Threshold;            // 亮部阈值（DiffPrefilter = 0 时用）
uniform float Prefilter;            // 1 = 做亮部提取，0 = 直接降采样
uniform float DiffPrefilter;        // 1 = 用差分提取，0 = 用阈值提取

in vec2 texCoord;
out vec4 fragColor;

// 亮度：线性空间的 Rec.709 权重
float bloomLuma(vec3 c) {
    return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

// 软拐点亮部提取：低于阈值的部分直接砍掉，过渡区用二次曲线软化，
// 避免阈值边缘出现硬邦邦的一圈。
vec3 bloomBrightPass(vec3 c) {
    float br = bloomLuma(c);
    float knee = max(Threshold * 0.5, 1.0e-4);
    float soft = clamp(br - Threshold + knee, 0.0, 2.0 * knee);
    soft = soft * soft / (4.0 * knee);
    float contrib = max(soft, br - Threshold) / max(br, 1.0e-4);
    return c * contrib;
}

/**
 * **差分**亮部提取（移植自参考包 bloom_down.fsh 的 Prefilter 分支）。
 *
 * <p>参考包拿 AuxSampler（原始场景）和当前画面相减，只让「打击特效新加上去的光」发光 ——
 * 这样原版的天空和雪地不会整片糊掉。</p>
 *
 * <p>我们这里 AuxSampler 在首级是「特效之前的那张画面」，所以差值就是特效本身。
 * 没有 AuxSampler 时（其余各级）退化成普通阈值提取。</p>
 */
vec3 bloomBrightPassDiff(vec3 c, vec3 original) {
    vec3 diff = c - original;
    vec3 added = max(diff, vec3(0.0));
    // 某一通道被压低（变色）时不该用互补色发光 —— 只按真正增加的亮度算
    float lo = min(diff.r, min(diff.g, diff.b));
    float hi = max(diff.r, max(diff.g, diff.b));
    float additive = lo >= 0.0 ? 1.0 : clamp(1.0 + lo / max(0.1 * hi, 1.0e-4), 0.0, 1.0);
    float gained = max(bloomLuma(c) - bloomLuma(original), 0.0);
    vec3 recoloured = c * (gained / max(bloomLuma(c), 1.0e-4));
    vec3 res = mix(recoloured, added, additive);
    // 差分之外，还要让「本来就特别亮」的东西（特效的高光）也能发光
    float br = bloomLuma(c);
    float knee = smoothstep(0.82, 0.98, br);
    return res * 0.55 + c * knee * 0.12;
}

vec3 bloomTap(vec2 uv) {
    vec3 c = texture(DiffuseSampler, uv).rgb;
    if (Prefilter > 0.5) {
        // 有原始场景可比 → 差分提取；没有 → 普通阈值提取
        if (DiffPrefilter > 0.5) {
            vec3 original = texture(AuxSampler, uv).rgb;
            c = bloomBrightPassDiff(c, original);
        } else {
            c = bloomBrightPass(c);
        }
    }
    return c;
}

void main() {
    vec2 uv = texCoord;
    // 抽样步长 = 输入纹素大小（和参考实现一致：TexelSize = 1 / 输入尺寸）
    vec2 ts = 1.0 / max(InSize, vec2(1.0));
    vec3 a = bloomTap(uv + ts * vec2(-2.0, 2.0));
    vec3 b = bloomTap(uv + ts * vec2(0.0, 2.0));
    vec3 c = bloomTap(uv + ts * vec2(2.0, 2.0));
    vec3 d = bloomTap(uv + ts * vec2(-2.0, 0.0));
    vec3 e = bloomTap(uv);
    vec3 f = bloomTap(uv + ts * vec2(2.0, 0.0));
    vec3 g = bloomTap(uv + ts * vec2(-2.0, -2.0));
    vec3 h = bloomTap(uv + ts * vec2(0.0, -2.0));
    vec3 i = bloomTap(uv + ts * vec2(2.0, -2.0));
    vec3 j = bloomTap(uv + ts * vec2(-1.0, 1.0));
    vec3 k = bloomTap(uv + ts * vec2(1.0, 1.0));
    vec3 l = bloomTap(uv + ts * vec2(-1.0, -1.0));
    vec3 m = bloomTap(uv + ts * vec2(1.0, -1.0));
    vec3 col = e * 0.125
        + (a + c + g + i) * 0.03125
        + (b + d + f + h) * 0.0625
        + (j + k + l + m) * 0.125;
    fragColor = vec4(col, 1.0);
}
