#version 150

// orbit_hud —— 我们自己的 HUD 图形层（原创实现）。
//
// 手法只有一个：**一个形状 = 一个四边形**。四边形的 UV0 携带它自己的像素尺寸，
// 顶点色携带形状本身（模式 + 参数 + RGB565 颜色 + 透明度），
// 于是无论外面套多少层缩放/旋转，形状都还是那个形状。
//
// 顶点色的编码（与 Java 侧 OrbitHudShapes 完全对应）：
//   texCoord0.x = 宽 + 0.25，texCoord0.y = 高 + 0.25；四个角各差 0.5，
//                 着色器用 (uv - floor(uv) - 0.25) * 2 还原出 0..1 的局部坐标。
//   vertexColor.r = RGB565 的高字节
//   vertexColor.g = RGB565 的低字节
//   vertexColor.b = 元素透明度 0..255
//   vertexColor.a = 0x80 | (参数 << 4) | 模式
//                 bit7   = 1，标记「这是一个图形四边形」（不是贴图四边形）
//                 bit4-6 = 参数，3 bit，含义随模式而变
//                 bit0-3 = 模式
//
// 模式与参数：
//   0 面板   参数 bit0-1 圆角档位（0=2px 1=4px 2=8px 3=胶囊），bit2 描边
//   1 投影   参数 bit0-1 圆角档位，bit2 大模糊（四边形要比面板本体大一圈）
//   2 圆盘   参数 = 样式：0 实心 1 细环 2 辉光 3 粗环 4 斜面
//   3 进度弧 参数 = 已填充的档位 0..7（0 和 7 分别是空和满）
//   6 准星   参数 = 锁定档位 0..7（越大越收紧）
//   7 标尺   参数 = 已画出的档位 0..7
//
// 抗锯齿：每个形状都在**四边形自己的像素空间**里用 fwidth 算出覆盖率，
// 所以边缘永远是一个像素宽，缩放再多次也不会糊成一片或者碎成锯齿。

uniform vec4 ColorModulator;
uniform vec2 ScreenSize;

in vec2 texCoord0;
in vec4 vertexColor;

out vec4 fragColor;

const float TAU = 6.28318530718;

vec3 gCol = vec3(0.0);
float gA = 0.0;

float sqr(float x) {
    return x * x;
}

// RGB565：hi 是高字节，lo 是低字节
vec3 rgb565(float hi, float lo) {
    float v = hi * 256.0 + lo;
    return vec3(floor(v / 2048.0) / 31.0, mod(floor(v / 32.0), 64.0) / 63.0, mod(v, 32.0) / 31.0);
}

void put(vec3 col, float a) {
    gCol = col;
    gA = clamp(a, 0.0, 1.0);
}

// 覆盖率：d 是到形状边界的距离（内部为负），aa 是一个屏幕像素在局部空间里的长度
float cover(float d, float aa) {
    return 1.0 - smoothstep(-aa * 0.5, aa * 0.5, d);
}

// 圆角矩形的距离场，p 是相对中心的坐标，half_ 是半边长，r 是圆角半径
float roundBox(vec2 p, vec2 half_, float r) {
    vec2 q = abs(p) - half_ + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

// 参数低两位 = 圆角档位：0=2px 1=4px 2=8px 3=胶囊
float cornerRadius(int param, vec2 size) {
    float r = 2.0;
    if ((param & 3) == 1) {
        r = 4.0;
    } else if ((param & 3) == 2) {
        r = 8.0;
    } else if ((param & 3) == 3) {
        r = min(size.x, size.y) * 0.5;
    }
    return min(r, min(size.x, size.y) * 0.5);
}

// 参数低三位 = 0..7 的档位，映射到 0..1（0 和 1 都在内）
float level7(int param) {
    return float(param & 7) / 7.0;
}

// 屏幕空间的细抖动：投影、辉光这类大渐变在 8bit 下容易出色带，
// 加一点几乎看不见的噪声即可，图案锚在屏幕上所以不会随形状抖动。
float dither(vec2 fragCoord, vec2 screen) {
    vec2 cell = floor(fragCoord / max(screen, vec2(1.0)) * 512.0);
    return fract(sin(dot(cell, vec2(12.9898, 78.233))) * 43758.5453) - 0.5;
}

// 模式 0：面板。参数 bit0-1 圆角档位，bit2 描边。
void shapePlate(vec2 q, vec2 size, vec2 st, vec3 fill, float alpha, int param, float aa) {
    vec2 half_ = size * 0.5;
    float r = cornerRadius(param, size);
    float d = roundBox(q - half_, half_, r);
    float cov = cover(d, aa);
    // 冷调面板：整体压暗，往上渐渐透出一点亮
    vec3 col = fill * (0.88 + 0.22 * (1.0 - st.y));
    if ((param & 4) != 0) {
        // 描边：贴着边缘内侧一条亮线
        float inner = cover(d + 1.5, aa);
        float edge = clamp(cov - inner, 0.0, 1.0);
        col = mix(col, mix(fill, vec3(1.0), 0.45), edge);
    }
    put(col, cov * alpha);
}

// 模式 1：投影。参数 bit0-1 圆角档位，bit2 大模糊。
// 四边形要比面板本体大一圈，模糊就在这一圈里化开。
void shapeShadow(vec2 q, vec2 size, vec3 tint, float alpha, int param) {
    float m = 6.0;
    if ((param & 4) != 0) {
        m = 14.0;
    }
    vec2 inner = size - 2.0 * m;
    float r = min(cornerRadius(param, size), min(inner.x, inner.y) * 0.5);
    float d = roundBox(q - size * 0.5, inner * 0.5, r);
    float sigma = m * 0.55;
    float g = exp(-sqr(max(d, 0.0)) / (2.0 * sigma * sigma));
    float inside = smoothstep(-3.0, 0.0, d);
    float a = g * inside * (1.0 - smoothstep(m * 0.8, m, d));
    put(tint, a * alpha);
}

// 模式 2：圆盘。参数 = 样式：0 实心 1 细环 2 辉光 3 粗环 4 斜面。
void shapeDisc(vec2 q, vec2 size, vec2 st, vec3 col, float alpha, int param, float aa) {
    float rad = min(size.x, size.y) * 0.5;
    float dist = length(q - size * 0.5);
    int style = param & 7;
    if (style == 2) {
        // 辉光：中间实，尾巴散掉
        float k = 1.0 - smoothstep(0.0, rad, dist);
        put(col, k * k * alpha);
        return;
    }
    if (style == 1 || style == 3) {
        float w = 1.2;
        if (style == 3) {
            w = 2.8;
        }
        // 环要整个落在四边形里，所以半径往里收半个环宽
        float rr = rad - w * 0.5;
        float cov = cover(abs(dist - rr) - w * 0.5, aa);
        put(col, cov * alpha);
        return;
    }
    float cov = cover(dist - rad, aa);
    vec3 face = col;
    if (style == 4) {
        // 斜面：上面受光、内缘一圈亮边
        face = col * (0.86 + 0.30 * (1.0 - st.y));
        float rim = cover(dist - rad + 1.6, aa);
        face = mix(face, vec3(1.0), clamp(cov - rim, 0.0, 1.0) * 0.4);
    }
    put(face, cov * alpha);
}

// 模式 3：进度弧。参数 = 已填充的档位 0..7；从正上方开始顺时针。
void shapeArc(vec2 q, vec2 size, vec3 col, float alpha, int param, float aa) {
    vec2 p = q - size * 0.5;
    float rad = min(size.x, size.y) * 0.5 - 2.0;
    float w = 3.0;
    float ring = cover(abs(length(p) - rad) - w * 0.5, aa);
    float ang = atan(p.x, -p.y);
    if (ang < 0.0) {
        ang = ang + TAU;
    }
    float frac = level7(param);
    float lit = step(ang / TAU, frac);
    // 没画到的那一段留一条暗轨道
    vec3 c = mix(col * 0.25, col, lit);
    float head = 1.0 - smoothstep(0.0, 0.05, abs(ang / TAU - frac));
    c = mix(c, vec3(1.0), head * 0.5 * lit);
    put(c, ring * alpha);
}

// 模式 6：准星。参数 = 锁定档位 0..7；越锁越紧，刻度越短，中心越亮。
void shapeReticle(vec2 q, vec2 size, vec3 col, float alpha, int param, float aa) {
    vec2 p = q - size * 0.5;
    float m = min(size.x, size.y);
    float lock = level7(param);
    float rad = mix(m * 0.30, m * 0.17, lock);
    float ring = cover(abs(length(p) - rad) - 0.7, aa);
    // 四个方向的刻度
    float along = max(abs(p.x), abs(p.y));
    float across = min(abs(p.x), abs(p.y));
    float tickLen = mix(m * 0.16, m * 0.07, lock);
    float tickMid = rad + 2.0 + tickLen * 0.5;
    float tick = cover(max(across - 0.7, abs(along - tickMid) - tickLen * 0.5), aa);
    // 中心点
    float dotR = mix(m * 0.05, m * 0.085, lock);
    float dotShape = cover(length(p) - dotR, aa);
    vec3 c = mix(col, mix(col, vec3(1.0), 0.55), lock);
    put(c, max(max(ring, tick), dotShape) * alpha);
}

// 模式 7：标尺。参数 = 已画出的档位 0..7；线头有一小簇火花。
void shapeRule(vec2 q, vec2 size, vec3 col, float alpha, int param, float aa) {
    float y = abs(q.y - size.y * 0.5);
    float line = cover(y - 0.6, aa);
    float frac = level7(param);
    float head = frac * size.x;
    float body = 1.0 - smoothstep(head - 1.0, head, q.x);
    float after = smoothstep(head - 1.0, head + 1.0, q.x);
    float track = after * (1.0 - smoothstep(size.x * 0.45, size.x, q.x));
    float spark = exp(-sqr((q.x - head) / 3.0)) * exp(-sqr(y / 2.0));
    vec3 c = mix(col * 0.28, col, body);
    c = mix(c, vec3(1.0), clamp(spark, 0.0, 1.0) * 0.75);
    float a = max(line * max(body, track * 0.55), spark);
    put(c, a * alpha);
}

void main() {
    vec2 size = floor(texCoord0);
    vec2 st = (texCoord0 - size - 0.25) * 2.0;
    vec2 q = st * size;
    vec4 c = vertexColor;
    float r = floor(c.r * 255.0 + 0.5);
    float g = floor(c.g * 255.0 + 0.5);
    float b = floor(c.b * 255.0 + 0.5);
    int aByte = int(floor(c.a * 255.0 + 0.5));
    int mode = aByte & 15;
    int param = (aByte >> 4) & 7;
    // 一个屏幕像素在四边形自己的像素空间里有多长
    float aa = max(length(fwidth(q)) * 0.7071, 1e-4);
    vec3 col = rgb565(r, g);
    float alpha = b / 255.0;

    if (mode == 0) {
        shapePlate(q, size, st, col, alpha, param, aa);
    } else if (mode == 1) {
        shapeShadow(q, size, col, alpha, param);
    } else if (mode == 2) {
        shapeDisc(q, size, st, col, alpha, param, aa);
    } else if (mode == 3) {
        shapeArc(q, size, col, alpha, param, aa);
    } else if (mode == 6) {
        shapeReticle(q, size, col, alpha, param, aa);
    } else if (mode == 7) {
        shapeRule(q, size, col, alpha, param, aa);
    }

    if (gA <= 0.003) {
        discard;
    }
    gCol = min(gCol, vec3(1.0));
    gCol = gCol + (dither(gl_FragCoord.xy, ScreenSize) / 255.0);
    fragColor = vec4(gCol * ColorModulator.rgb, gA * ColorModulator.a);
}
