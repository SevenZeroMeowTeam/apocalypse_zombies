#version 150

// 把场景深度逐像素拷进 FX 快照（参考 The Shooting Star 的 fx/depth_copy.fsh）。
//
// 用采样 + gl_FragDepth 而不是 framebuffer blit：1.20.1 的深度附件格式由驱动挑，
// NVIDIA 甚至会报通用 DEPTH_COMPONENT，blit 会直接失败（参考实现里整个特效层都不显示）。
//
// 需要：深度测试开着 + 深度写入开着（GL_DEPTH_TEST 关掉时深度缓冲不会被写）。
// 输出颜色恒为 0（这个 pass 只关心深度）。

uniform sampler2D DepthSampler;     // 场景深度纹理

in vec2 texCoord;
out vec4 fragColor;

void main() {
    gl_FragDepth = texture(DepthSampler, texCoord).r;
    fragColor = vec4(0.0);
}
