#version 150

// 太空烘焙 shader（v6.1）：把自己的太空场景烘成等距柱状贴图。
//
// **为什么单独一份**（而不是复用 orbit_sky.fsh 的 BakeMode）：
// 用户给的参考图（宇宙.png / 小地球.png）定下了两个视觉目标，而 orbit_sky 那份
// 是「游戏内实时解析体」的调法，方向不一样：
//
//   ◆ 宇宙：**彩色星云**（品红 / 青蓝 / 金橙三团，絮状亮边）+ 斜穿的银河尘带
//             + 大量分色星点 + 一块明亮的旋涡核心。整体比原来的烘焙亮且**有颜色**。
//   ◆ 小地球：**陆地色彩饱和**（绿/棕）、海是深蓝、云成片偏白、
//              明显的晨昏线（背光侧压黑）、边缘一圈薄大气。
//
// 参考图本身是多天区拼贴（逐块独立调色、不连续），**不能直接当全景贴图用** ——
// 这里只取它的色彩与构图特征，画面全部由本 shader 程序化生成。
//
// 本文件只被 tools/space_bake.py 离线调用，游戏内不参与渲染。

uniform float BakeMode;    // 1 = 全景天空，2 = 行星反照率
uniform float BakePixel;   // 一个纹素对应的角尺寸（弧度）
uniform vec2 BakeSize;     // 贴图像素尺寸（宽, 高）

in vec2 vUV;
out vec4 fragColor;

const float PI = 3.14159265;
const float TAU = 6.2831853;

float sqr(float x) { return x * x; }

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

// ------------------------------------------------------------------ 噪声

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

float fbm2(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 5; i++) {
        v += a * vnoise2(p);
        p *= 2.03;
        a *= 0.5;
    }
    return v;
}

/** 三维 fbm：地表噪声用（二维在极点会挤成一团）。 */
float fbm3(vec3 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 5; i++) {
        v += a * (vnoise2(p.xy + p.z * 17.0) * 0.5 + vnoise2(p.yz + p.x * 23.0) * 0.5);
        p *= 2.07;
        a *= 0.5;
    }
    return v;
}

// ------------------------------------------------------------------ 彩色星云

/**
 * 彩色星云：品红 / 青蓝 / 金橙三团絮状云。
 *
 * <p><b>为什么现在这么克制</b>：v6.1 第一版把星云做成「整屏涂抹」——
 * {@code exp(-r*r*0.5)} 在大范围几乎不衰减，加上 fbm 的值域偏高，
 * 结果全屏 100% 被涂白（p50 直接到 253）。
 * 参考图的星云是**几块独立的团**，团与团之间是黑透的深空，所以这里：</p>
 * <ul>
 *   <li>衰减改成 {@code exp(-r*r*1.6)}（更紧，团外快速归零）；</li>
 *   <li>阈值整体上移（{@code smoothstep(0.68, 0.24, d)} 的高端从 0.62 提到 0.68，
 *       且 <b>d 先乘回 fbm 的值域</b>：fbm2 的返回值在 0.45..0.55 附近，几乎恒定，</li>
 *       所以这里改用 {@code (d - 0.42) * 2.6} 把它的动态范围拉出来再用）；</li>
 *   <li>总强度降到 0.55。</li>
 * </ul>
 */
vec3 nebula(vec2 uv) {
    vec3 col = vec3(0.0);
    vec2 cs[3];
    cs[0] = vec2(0.26, 0.34);
    cs[1] = vec2(0.61, 0.20);
    cs[2] = vec2(0.44, 0.74);
    vec3 ts[3];
    ts[0] = vec3(0.92, 0.16, 0.52);   // 品红
    ts[1] = vec3(0.13, 0.52, 0.96);   // 青蓝
    ts[2] = vec3(0.98, 0.60, 0.14);   // 金橙

    for (int i = 0; i < 3; i++) {
        vec2 c = cs[i];
        vec3 tint = ts[i];
        // 团内细节的尺度。**这个值直接决定星云占多大地方**：
        // v6.1 第一版用 3.0，结果三团铺满全屏（覆盖率 99%，整幅发白）。
        // 14 左右覆盖降到 40% 上下，团与团之间留出黑透的深空，才是参考图的样子。
        float scale = i == 0 ? 14.0 : i == 1 ? 16.0 : 12.0;
        vec2 q = (uv - c) * scale;
        vec2 warp = vec2(fbm2(q * 1.7 + 11.0), fbm2(q * 1.7 + 37.0)) - 0.5;
        float d = fbm2(q + warp * 1.5);
        float density = clamp((d - 0.42) * 2.6, 0.0, 1.0);
        float r = length(q) * 0.30;
        float cloud = smoothstep(0.72, 0.26, density) * exp(-r * r * 2.5);
        if (cloud < 0.001) {
            continue;
        }
        vec3 hot = mix(tint, vec3(1.0), pow(cloud, 3.0) * 0.55);
        col += hot * cloud * 0.55;
    }
    return col;
}

// ------------------------------------------------------------------ 银河

/**
 * 银河尘带：一条斜穿的亮带（参考图左上 → 右下的那道）。
 *
 * @param uv    0..1 的全景 uv
 * @param tilt  带的倾角（弧度）：正数 = 左高右低
 */
vec3 milkyWay(vec2 uv, float tilt) {
    float s = sin(tilt);
    float c = cos(tilt);
    // 带的「横向」坐标：直接由经度 lon 算，保证接缝处（lon=±π）严格相等。
    // 注意不能用 uv.x * c：u=0 与 u=1 时它差一个 c，接缝两侧就对不上。
    float lon = (uv.x - 0.5) * TAU;
    vec2 q = vec2(lon * c - uv.y * s * 6.2831853, lon * s + uv.y * c * 6.2831853);
    // 带中心落在 q.y = 0.52（换成 0..1 的纬度坐标来比）
    float lat01 = uv.y;
    float d = abs(lat01 - 0.52);
    float width = 0.055 + 0.045 * (1.0 - abs(uv.x - 0.5) * 1.6);
    float band = exp(-sqr(d / width));
    // 尘带里的暗纹（尘埃遮光）—— 银河不像「一条白带」的关键。
    // 采样坐标用 sin/cos(lon)（环绕严格相等），避免接缝竖线。
    vec2 laneP = vec2(cos(lon) * 2.0 + 5.0, lat01 * 22.0);
    float lane = fbm2(laneP);
    float dust = smoothstep(0.35, 0.62, lane);
    // 银心方向更亮：以经度差算（同样环绕）
    float coreU = lon - 0.12;
    float core = exp(-sqr(coreU * 1.6));
    vec3 dustCol = mix(vec3(0.85, 0.72, 0.52), vec3(0.55, 0.60, 0.78), dust * 0.6);
    return dustCol * band * (0.55 + 0.9 * core) * (1.0 - dust * 0.45);
}

// ------------------------------------------------------------------ 旋涡星系

/** 一块明亮的旋涡星系（参考图右上那一整条）：对数螺旋臂 + 中央核球。 */
vec3 spiralGalaxy(vec2 uv, vec2 center, float scale, float rot) {
    // 用 lon/lat 的环绕坐标算位置，而不是 uv 直接减 center：
    // uv 在 0 和 1 处不连续，星系横跨接缝时会切成一圈。
    float lon = (uv.x - 0.5) * TAU;
    float lat = (uv.y - 0.5) * PI;
    // 中心也换成 lon/lat
    float clon = (center.x - 0.5) * TAU;
    float clat = (center.y - 0.5) * PI;
    // 经度差按环绕算（最短弧）
    float dlon = lon - clon;
    dlon = dlon - TAU * floor(dlon / TAU + 0.5);
    vec2 q = vec2(dlon, lat - clat) * scale;
    float a = rot;
    vec2 p = vec2(q.x * cos(a) - q.y * sin(a), q.x * sin(a) + q.y * cos(a));
    float r = length(p);
    float ang = atan(p.y, p.x);
    float arms = 0.55 + 0.45 * sin(2.0 * ang - 4.0 * log(r + 0.18) + 1.2);
    float arm = smoothstep(0.35, 0.95, arms);
    float disc = exp(-r * r * 1.5);
    float bulge = exp(-r * r * 13.0);
    vec3 col = vec3(0.72, 0.62, 0.48) * disc * arm * 0.55;
    col += vec3(0.98, 0.88, 0.66) * bulge * 0.9;
    col *= smoothstep(1.6, 0.25, r);
    return col;
}

// ------------------------------------------------------------------ 星场

/**
 * 三层星场：远/中/近三组格点星，星等按哈希幂分布，蓝白→橙金色温。
 * 思路同参考包 star.glsl，参数重调。
 */
vec3 starField(vec3 rd, float pix) {
    vec3 col = vec3(0.0);
    for (int layer = 0; layer < 3; layer++) {
        float fl = float(layer);
        float scale = layer == 0 ? 90.0 : layer == 1 ? 210.0 : 430.0;
        vec3 id = floor(rd * scale);
        float h = hash12(id.xy + id.z * 13.7 + fl * 17.0);
        if (h > (layer == 0 ? 0.055 : layer == 1 ? 0.045 : 0.035)) {
            continue;
        }
        vec3 sd = normalize(id + 0.2 + 0.6 * vec3(hash12(id.xy + 3.1),
                                                  hash12(id.yz + 7.7),
                                                  hash12(id.zx + 11.3)));
        float a = length(rd - sd);
        float size = layer == 0 ? 1.35 : layer == 1 ? 0.95 : 0.65;
        float mag = sqr(sqr(h)) * h * (layer == 0 ? 11.0 : 3.2) + (layer == 2 ? 0.14 : 0.22);
        vec3 tint = mix(vec3(0.60, 0.74, 1.0), vec3(1.0, 0.82, 0.58), hash12(id.xz + 2.3));
        col += tint * mag * exp(-sqr(a / (pix * size))) * 0.42;
    }
    return col;
}

// ------------------------------------------------------------------ 地表

/**
 * 行星地表：fbm 地形 + 冰盖 + 云量 + 沙漠/森林分区着色。
 *
 * <p>按参考图目标调：陆地要**有颜色**（绿/棕），不是一片灰。</p>
 */
vec3 planetSurface(vec3 dir, out float clouds) {
    float land = fbm3(dir * 2.05 + 4.7);
    float detail = fbm3(dir * 6.3);
    // 纬度分区：赤道偏森林，副热带偏沙漠，两极冰盖
    float lat = abs(dir.y);
    float desert = exp(-sqr((lat - 0.30) / 0.16));
    float forest = 1.0 - desert;

    vec3 ocean = vec3(0.020, 0.075, 0.240);
    vec3 deepOcean = vec3(0.008, 0.030, 0.130);
    vec3 green = vec3(0.14, 0.34, 0.12);
    vec3 dry = vec3(0.52, 0.42, 0.24);
    vec3 ice = vec3(0.86, 0.90, 0.94);

    float depth = smoothstep(0.42, 0.52, land);
    vec3 sea = mix(ocean, deepOcean, depth * 0.7);
    vec3 landCol = mix(green, dry, desert);
    landCol = mix(landCol, vec3(0.40, 0.36, 0.22), smoothstep(0.50, 0.66, land) * 0.5);
    landCol += vec3(0.22, 0.18, 0.14) * smoothstep(0.30, 0.55, detail) * forest * 0.55;

    vec3 surf = mix(sea, landCol, smoothstep(0.485, 0.515, land));
    float iceMask = smoothstep(0.80, 0.95, lat) + smoothstep(0.60, 0.70, land) * 0.35;
    surf = mix(surf, ice, clamp(iceMask, 0.0, 1.0) * 0.85);

    // 云：中频 fbm 做成片（参考图的云是成片的，不是均匀涂抹）
    float cl = fbm3(dir * 3.4 + vec3(19.0, 0.0, 7.0));
    clouds = smoothstep(0.52, 0.74, cl);

    return surf;
}

// ------------------------------------------------------------------ 主

void main() {
    // 纹素中心 → uv。
    //
    // **环绕无缝的做法**：u = x / (W-1)。
    //   - x=0 → u=0 → lon=-π；x=W-1 → u=1 → lon=+π。首末列落在**同一条经线**，
    //     取值完全相同 → 环绕没有竖缝。
    //   - 注意：不能用 NDC 反算（大三角形的 vUV 在最左/最右列有半像素误差，
    //     会让首末列差出整整一颗星）；也不能用 (x+0.5)/W（首末列差一个纹素）。
    // 各层（银河 / 星云 / 旋涡 / 星场）拿到的 bu 都是这个环绕值，
    // 所以它们沿接缝也自然连续。
    float bu = floor(gl_FragCoord.x) / max(BakeSize.x - 1.0, 1.0);
    float bv = 1.0 - floor(gl_FragCoord.y) / max(BakeSize.y - 1.0, 1.0);
    float lon = (bu - 0.5) * TAU;
    float lat = (0.5 - bv) * PI;
    vec3 dir = vec3(cos(lat) * cos(lon), sin(lat), cos(lat) * sin(lon));

    if (BakeMode > 1.5) {
        // —— 行星反照率：RGB = 地表，A = 云量
        float clouds;
        vec3 surf = planetSurface(dir, clouds);
        fragColor = vec4(surf, clouds);
        return;
    }

    // —— 全景天空
    vec3 col = vec3(0.010, 0.014, 0.032);   // 深空底色（比原来亮一档）

    col += milkyWay(vec2(bu, bv), -0.245) * 0.6;          // 银河尘带
    col += nebula(vec2(bu, bv)) * 3.0;             // 彩色星云
    col += spiralGalaxy(vec2(bu, bv), vec2(0.68, 0.42), 1.5, 0.35) * 0.30;
    col += spiralGalaxy(vec2(bu, bv), vec2(0.20, 0.72), 2.2, -0.5) * 0.5;
    col += starField(dir, BakePixel);

    // 细微的星际介质起伏，让深空不「死」
    col += vec3(0.030, 0.026, 0.042) * smoothstep(0.42, 0.75, fbm3(dir * 5.5)) * 0.5;

    fragColor = vec4(col, 1.0);
}
