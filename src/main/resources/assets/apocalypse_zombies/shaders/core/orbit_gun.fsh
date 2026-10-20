#version 150

// ============================================================================
// 轨道炮「弧光长矛」ARCLIGHT LANCE v1.0 —— 原创解析 SDF 炮体（轨道维度近景演出）
// ----------------------------------------------------------------------------
// 移植自参考包 star_gun.fsh 的**技术路线**：
//   · 解析 SDF（sphere tracing）建模 + 超松弛（over-relaxed）步进
//   · GGX / 各向异性 GGX 金属着色 + 主光 + 环境补光 + 菲涅尔边缘光
//   · 充电波沿炮身自炮闩向炮口推进、开火闪光与后坐
// **造型与配色全部原创**，与参考包无关：
//   圆角箱体船身 + 腹下龙骨 + 背脊导轨 + 8 圈加速线圈（每三圈一重型箍）
//   + 三瓣喇叭护箍 + 三根聚焦爪 + 尾部三片散热鳍 + 环形反应堆 + 三段推进喷口。
//   能量配色为「弧光青」，船身为石墨哑光装甲，金属件为拉丝蓝钢。
//
// 坐标约定（枪身局部空间）：
//   +Z = 炮闩（后方），-Z = 炮口（前方），射线沿 -Z 射出。
//   炮口世界坐标 = (0, 0, -18)，与 rays pass 的 Muzzle 约定一致。
//
// 摄像机完全在 shader 空间：Java 每帧给 CamPos / CamForward / CamRight /
// CamUp / TanHalf / Aspect，片元按参考包 main() 的方式逐像素重建视线方向。
//
// 约定：本文件不引用任何外部片段（MC 的 core 预处理器只认 moj_import），
// 全部辅助函数就地定义；所有 uniform 都在使用点之前声明。
// ============================================================================

uniform vec3 CamPos;        // 相机位置（枪身空间）
uniform vec3 CamForward;    // 相机前向（枪身空间）
uniform vec3 CamRight;      // 相机右向（枪身空间）
uniform vec3 CamUp;         // 相机上向（枪身空间）
uniform float TanHalf;      // 垂直视场半角正切
uniform float Aspect;       // 画面宽高比
uniform float PixelSize;    // 每像素的张切空间尺寸 = 2*TanHalf/画面高度
uniform float Charge;       // 充能 0..1
uniform float Fired;        // 开火后秒数；< 0 = 未开火
uniform float GameTime;     // 场景时间（秒）
uniform float Alpha;        // 全局不透明度

in vec2 vUV;                // NDC（-1..1），由顶点着色器给出
out vec4 fragColor;

// ---------------------------------------------------------------- 常量

const float PI = 3.14159265;
const float TAU = 6.2831853;

const float GUN_MUZZLE_Z = -18.0;   // 炮口平面
const float GUN_BREECH_Z = 7.0;     // 炮闩（充电波起点）
const int GUN_COILS = 8;            // 加速线圈数
const float GUN_COIL_Z0 = -12.0;    // 最前一圈（靠炮口）
const float GUN_COIL_STEP = 1.05;   // 圈距

const vec3 ARC = vec3(0.30, 0.82, 1.00);       // 弧光（能量主色）
const vec3 ARC_HOT = vec3(0.86, 0.97, 1.00);   // 白热
const vec3 KEY_COL = vec3(1.00, 0.88, 0.72);   // 恒星主光（暖白）
const vec3 FILL_COL = vec3(0.26, 0.40, 0.72);  // 星云补光（冷蓝）
const vec3 KEY_DIR = vec3(-0.4462, 0.6693, 0.5950);   // 主光方向（已归一）
const vec3 FILL_DIR = vec3(0.6000, -0.2000, -0.7746); // 补光方向（已归一）

// 材质编号（沿用「距离 + 材质」二元组的写法）
#define M_HULL   1.0   // 哑光装甲
#define M_ARMOR  2.0   // 拉丝蓝钢（各向异性高光）
#define M_COIL   3.0   // 加速线圈（带发光凹槽）
#define M_CHANNEL 4.0  // 加速通道 / 指示灯（自发光）
#define M_CORE   5.0   // 反应堆核心（自发光）
#define M_DARK   6.0   // 橡胶、缆线、暗色支架
#define M_FIN    7.0   // 散热鳍

// ---------------------------------------------------------------- 全局状态

float gTime = 0.0;
float gCharge = 0.0;
float gFired = -1.0;
float gRecoil = 0.0;
float gFlash = 0.0;
float gPix = 0.001;

// ---------------------------------------------------------------- 基础工具

float gunSq(float x) { return x * x; }

float gunSat(float x) { return clamp(x, 0.0, 1.0); }

float gunHash11(float p) {
    p = fract(p * 0.1031);
    p *= p + 33.33;
    p *= p + p;
    return fract(p);
}

float gunHash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float gunHash13(vec3 p) {
    p = fract(p * 0.3183099 + vec3(0.1, 0.2, 0.3));
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

/** 值噪声（自建前缀，避开 GLSL 内建名）。 */
float gunNoise2(vec2 x) {
    vec2 i = floor(x);
    vec2 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(gunHash12(i), gunHash12(i + vec2(1.0, 0.0)), f.x),
               mix(gunHash12(i + vec2(0.0, 1.0)), gunHash12(i + vec2(1.0, 1.0)), f.x), f.y);
}

// ---------------------------------------------------------------- SDF 图元

float gunSdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}

float gunSdRBox(vec3 p, vec3 b, float r) {
    vec3 q = abs(p) - b + r;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0) - r;
}

float gunSdRBox2(vec2 p, vec2 b, float r) {
    vec2 q = abs(p) - b + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

float gunSdSeg(vec3 p, vec3 a, vec3 b, float r) {
    vec3 pa = p - a;
    vec3 ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h) - r;
}

/** 沿 z 轴的封口圆柱，半长 h。 */
float gunSdCylZ(vec3 p, float r, float h) {
    vec2 d = vec2(length(p.xy) - r, abs(p.z) - h);
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
}

/** 沿 z 轴的圆环面。 */
float gunSdTorusZ(vec3 p, float R, float r) {
    return length(vec2(length(p.xy) - R, p.z)) - r;
}

/** 沿 z 轴的封口截锥：z = -h 处半径 rFront，z = +h 处半径 rBack。 */
float gunSdConeZ(vec3 p, float h, float rFront, float rBack) {
    vec2 q = vec2(length(p.xy), p.z);
    vec2 k1 = vec2(rBack, h);
    vec2 k2 = vec2(rBack - rFront, 2.0 * h);
    vec2 ca = vec2(q.x - min(q.x, (q.y < 0.0) ? rFront : rBack), abs(q.y) - h);
    vec2 cb = q - k1 + k2 * clamp(dot(k1 - q, k2) / dot(k2, k2), 0.0, 1.0);
    float s = (cb.x < 0.0 && ca.y < 0.0) ? -1.0 : 1.0;
    return s * sqrt(min(dot(ca, ca), dot(cb, cb)));
}

float gunSmin(float a, float b, float k) {
    float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
    return mix(b, a, h) - k * h * (1.0 - h);
}

/** 并集：返回更近的那个（距离 + 材质）。 */
vec2 gunOpU(vec2 a, vec2 b) {
    return (a.x < b.x) ? a : b;
}

/** 把 xy 折进 3 等分的一个扇区（沿 +x），offset = 第一个分量的方位角。 */
vec2 gunFold3(vec2 p, float offset) {
    float step = TAU / 3.0;
    float a = atan(p.y, p.x) - offset;
    float k = floor(a / step + 0.5) * step;
    float ang = offset + k;
    float c = cos(ang);
    float s = sin(ang);
    return vec2(c * p.x + s * p.y, -s * p.x + c * p.y);
}

// ---------------------------------------------------------------- 炮体

/**
 * 一圈加速线圈。k = 0 最靠炮口。每三圈一圈是重型箍（更粗、外径更大、带卡箍）。
 * 返回（距离，材质）。
 */
vec2 gunCoil(vec3 p, float k) {
    float zc = GUN_COIL_Z0 + k * GUN_COIL_STEP;
    vec3 cp = p - vec3(0.0, 0.0, zc);
    float heavy = step(mod(k, 3.0), 0.5);
    float outer = mix(1.35, 1.62, heavy);
    float thick = mix(0.16, 0.26, heavy);
    // 圆角方环
    float ring = max(gunSdRBox2(cp.xy, vec2(outer, outer), 0.42),
                     -gunSdRBox2(cp.xy, vec2(0.88, 0.88), 0.30));
    ring = max(ring, abs(cp.z) - thick);
    vec2 res = vec2(ring, M_COIL);
    if (heavy > 0.5) {
        // 四角卡箍（折到对角线）
        vec2 aq = abs(cp.xy);
        aq = (aq.x > aq.y) ? aq : aq.yx;
        float clamp = gunSdRBox(vec3(aq.x - outer - 0.10, aq.y, cp.z),
                                vec3(0.20, 0.20, thick + 0.09), 0.05);
        res = gunOpU(res, vec2(clamp, M_ARMOR));
    }
    return res;
}

/** 整门炮的距离场。lite = true 时省掉小零件（给环境光遮蔽用）。 */
vec2 gunMap(vec3 p, bool lite) {
    p.z -= gRecoil;

    // 粗包围盒：盒子含住整门炮，盒距离是真实距离的下界，可以安全大步前进
    float bound = gunSdBox(p - vec3(0.0, 0.0, -4.55), vec3(3.45, 3.45, 13.75));
    if (bound > 0.30) return vec2(bound, 0.0);

    vec2 res = vec2(1e5, 0.0);

    // ---- 1) 船体（圆角箱）+ 腹下龙骨 + 背脊导轨
    float hull = gunSdRBox(p - vec3(0.0, 0.0, 2.0), vec3(1.05, 0.85, 6.2), 0.28);
    res = gunOpU(res, vec2(hull, M_HULL));
    float keel = gunSdBox(p - vec3(0.0, -1.20, 1.8), vec3(0.13, 0.42, 5.4));
    res = gunOpU(res, vec2(keel, M_HULL));
    float rail = gunSdRBox(p - vec3(0.0, 0.95, 0.2), vec3(0.22, 0.13, 4.0), 0.05);
    res = gunOpU(res, vec2(rail, M_ARMOR));
    if (!lite) {
        float post = gunSdBox(p - vec3(0.0, 0.72, -2.0), vec3(0.11, 0.24, 0.11));
        res = gunOpU(res, vec2(post, M_DARK));
        // 侧向检修口盖
        float hatch = gunSdRBox(vec3(abs(p.x) - 1.02, p.y, p.z - 3.0), vec3(0.06, 0.34, 0.9), 0.03);
        res = gunOpU(res, vec2(hatch, M_DARK));
    }

    // ---- 2) 炮管（沿 -Z 伸出船身）+ 三条纵向筋 + 顶部加速通道凹槽
    float barrel = gunSdCylZ(p - vec3(0.0, 0.0, -8.40), 0.52, 4.45);
    vec2 fp = gunFold3(p.xy, PI / 6.0);
    float rib = gunSdBox(vec3(fp.x - 0.56, fp.y, p.z + 8.40), vec3(0.10, 0.22, 4.30));
    barrel = min(barrel, rib);
    // 顶部开一条槽，露出里面的加速通道
    float slot = gunSdBox(p - vec3(0.0, 0.46, -8.20), vec3(0.17, 0.26, 4.20));
    barrel = max(barrel, -slot);
    res = gunOpU(res, vec2(barrel, M_ARMOR));
    float channel = gunSdBox(p - vec3(0.0, 0.44, -8.20), vec3(0.14, 0.24, 4.15));
    res = gunOpU(res, vec2(channel, M_CHANNEL));

    // ---- 3) 加速线圈（只看最近两圈）
    float kf = (p.z - GUN_COIL_Z0) / GUN_COIL_STEP;
    float k0 = clamp(floor(kf + 0.5), 0.0, float(GUN_COILS - 1));
    res = gunOpU(res, gunCoil(p, k0));
    float k1 = clamp(k0 + ((kf > k0) ? 1.0 : -1.0), 0.0, float(GUN_COILS - 1));
    if (k1 != k0) {
        res = gunOpU(res, gunCoil(p, k1));
    }

    // ---- 4) 喇叭护箍（把炮管张开成宽口）+ 连接锥
    float collar = max(gunSdCylZ(p - vec3(0.0, 0.0, -13.50), 2.20, 0.50),
                       -gunSdCylZ(p - vec3(0.0, 0.0, -13.50), 1.05, 0.60));
    float lip = max(gunSdCylZ(p - vec3(0.0, 0.0, -13.92), 2.45, 0.16),
                    -gunSdCylZ(p - vec3(0.0, 0.0, -13.92), 1.05, 0.20));
    res = gunOpU(res, vec2(min(collar, lip), M_HULL));
    float cone = gunSdConeZ(p - vec3(0.0, 0.0, -13.10), 0.36, 0.55, 1.08);
    res = gunOpU(res, vec2(cone, M_ARMOR));
    if (!lite) {
        // 护箍上的三块散热片
        vec2 fq = gunFold3(p.xy, PI / 2.0);
        float vane = gunSdBox(vec3(fq.x - 2.30, fq.y, p.z + 13.60), vec3(0.22, 0.30, 0.42));
        res = gunOpU(res, vec2(vane, M_ARMOR));
    }

    // ---- 5) 三根聚焦爪（正上方一根，另两根在下）
    vec2 fw = gunFold3(p.xy, PI / 2.0);
    vec3 w3 = vec3(fw, p.z);
    float prong = min(gunSdSeg(w3, vec3(1.85, 0.0, -14.05), vec3(1.10, 0.0, -16.00), 0.19),
                     gunSdSeg(w3, vec3(1.10, 0.0, -16.00), vec3(0.42, 0.0, -18.15), 0.10));
    res = gunOpU(res, vec2(prong, M_ARMOR));

    // ---- 6) 聚焦环（爪尖上的细环，charge 在此聚集）
    float focus = gunSdTorusZ(p - vec3(0.0, 0.0, -18.20), 0.50, 0.055);
    res = gunOpU(res, vec2(focus, M_ARMOR));

    // ---- 7) 尾部反应堆：核心 + 约束环 + 笼架
    float core = length(p - vec3(0.0, 0.0, 7.00)) - 0.80;
    res = gunOpU(res, vec2(core, M_CORE));
    float ring = gunSdTorusZ(p - vec3(0.0, 0.0, 7.00), 1.60, 0.26);
    res = gunOpU(res, vec2(ring, M_ARMOR));
    vec2 fs = gunFold3(p.xy, PI / 6.0);
    vec3 s3 = vec3(fs, p.z);
    float cage = min(gunSdSeg(s3, vec3(1.50, 0.0, 7.00), vec3(0.85, 0.0, 7.00), 0.10),
                     gunSdSeg(s3, vec3(1.52, 0.0, 5.10), vec3(1.52, 0.0, 8.90), 0.08));
    res = gunOpU(res, vec2(cage, M_DARK));

    // ---- 8) 三片散热鳍（与笼架错开 60°）
    vec2 ff = gunFold3(p.xy, PI / 2.0);
    float fin = gunSdBox(vec3(ff.x - 2.10, ff.y, p.z - 6.00), vec3(0.95, 0.07, 2.40));
    res = gunOpU(res, vec2(fin, M_FIN));
    float finEdge = gunSdBox(vec3(ff.x - 3.00, ff.y, p.z - 6.00), vec3(0.09, 0.11, 2.40));
    res = gunOpU(res, vec2(finEdge, M_ARMOR));

    // ---- 9) 尾部供能块（顶部，带三枚指示灯）
    float feed = gunSdRBox(p - vec3(0.0, 1.02, 4.20), vec3(0.50, 0.30, 1.50), 0.08);
    res = gunOpU(res, vec2(feed, M_DARK));
    for (int i = 0; i < 3; i++) {
        float z = 3.40 + float(i) * 0.80;
        float lamp = gunSdBox(p - vec3(0.0, 1.26, z), vec3(0.30, 0.07, 0.10));
        res = gunOpU(res, vec2(lamp, M_CHANNEL));
    }

    // ---- 10) 尾部推进喷口 + 封板
    float bell = max(gunSdConeZ(p - vec3(0.0, 0.0, 8.60), 0.50, 0.35, 1.00),
                     -gunSdConeZ(p - vec3(0.0, 0.0, 8.60), 0.50, 0.20, 0.85));
    res = gunOpU(res, vec2(bell, M_DARK));
    float plate = gunSdCylZ(p - vec3(0.0, 0.0, 8.30), 1.00, 0.16);
    res = gunOpU(res, vec2(plate, M_HULL));

    return res;
}

vec3 gunNormal(vec3 p) {
    const vec2 e = vec2(0.0016, -0.0016);
    return normalize(e.xyy * gunMap(p + e.xyy, false).x
                   + e.yyx * gunMap(p + e.yyx, false).x
                   + e.yxy * gunMap(p + e.yxy, false).x
                   + e.xxx * gunMap(p + e.xxx, false).x);
}

/** 射线与轴对齐盒求交，返回 (tNear, tFar)。 */
vec2 gunBoxHit(vec3 ro, vec3 rd, vec3 lo, vec3 hi) {
    vec3 inv = 1.0 / rd;
    vec3 t0 = (lo - ro) * inv;
    vec3 t1 = (hi - ro) * inv;
    vec3 tmin = min(t0, t1);
    vec3 tmax = max(t0, t1);
    return vec2(max(max(tmin.x, tmin.y), tmin.z), min(min(tmax.x, tmax.y), tmax.z));
}

/** 球体追踪（超松弛步进）。返回 (t, 材质)；未命中返回 (-1, 0)。 */
vec2 gunMarch(vec3 ro, vec3 rd, float tMax) {
    vec2 bx = gunBoxHit(ro, rd, vec3(-3.45, -3.45, -18.40 + gRecoil),
                                  vec3(3.45, 3.45, 9.30 + gRecoil));
    if (bx.y < max(bx.x, 0.0)) return vec2(-1.0, 0.0);
    float t = max(bx.x, 0.0);
    float end = min(bx.y, tMax);
    float omega = 1.20;
    float stride = 0.0;
    float before = 0.0;
    for (int i = 0; i < 150; i++) {
        vec2 h = gunMap(ro + rd * t, false);
        float radius = h.x * 0.82;
        bool overshot = omega > 1.0 && (radius + before < stride);
        if (overshot) {
            stride -= omega * stride;
            omega = 1.0;
        } else {
            float eps = max(gPix * t * 0.6, 0.0010);
            if (h.x < eps) return vec2(t, h.y);
            stride = radius * omega;
        }
        before = radius;
        t += stride;
        if (t > end) break;
    }
    return vec2(-1.0, 0.0);
}

/** 环境光遮蔽（4 抽样，省略小零件）。 */
float gunOcclusion(vec3 p, vec3 n) {
    float o = 0.0;
    float w = 1.0;
    for (int i = 1; i <= 4; i++) {
        float d = 0.09 * float(i) * float(i) * 0.5 + 0.03;
        o += (d - gunMap(p + n * d, true).x) * w;
        w *= 0.72;
    }
    return gunSat(1.0 - o * 1.9);
}

// ---------------------------------------------------------------- 表面与着色

struct GunMat {
    vec3 albedo;
    vec3 f0;
    float rough;
    float metal;
    float aniso;
    vec3 emit;
};

/** 充电波：返回 (已充能段亮度, 波前强度)。波自炮闩向炮口推进。 */
vec2 gunWave(float z) {
    float front = mix(GUN_BREECH_Z, GUN_MUZZLE_Z - 0.4, gCharge);
    float lit = smoothstep(front - 0.5, front + 0.9, z);
    float crest = exp(-gunSq((z - front) / 0.6));
    return vec2(lit, crest);
}

/** 板缝：按表面主轴投影出的网格线 + 面板编号。 */
float gunSeams(vec3 p, vec3 n, out float panel) {
    vec3 a = abs(n);
    vec2 uv = p.xy;
    if (a.x > a.y && a.x > a.z) uv = p.zy;
    else if (a.y > a.z) uv = p.xz;
    vec2 cell = vec2(0.72, 0.46);
    vec2 g = abs(fract(uv / cell) - 0.5) * cell;
    vec2 id = floor(uv / cell);
    panel = gunHash12(id + 7.0);
    float line = 1.0 - smoothstep(0.004, 0.010, min(g.x, g.y));
    return line;
}

/** 材质表。lp = 枪身局部坐标（不含后坐位移）。 */
GunMat gunMaterial(vec3 lp, vec3 n, float mat) {
    GunMat m;
    m.albedo = vec3(0.05);
    m.f0 = vec3(0.04);
    m.rough = 0.50;
    m.metal = 0.0;
    m.aniso = 0.0;
    m.emit = vec3(0.0);

    float panel;
    float seam = gunSeams(lp, n, panel);
    vec2 w = gunWave(lp.z);
    float lit = w.x;
    float crest = w.y;
    float grime = gunNoise2(lp.xy * 3.1 + lp.zz * 0.7);

    if (mat == M_HULL) {
        // 石墨哑光装甲：每块板略有色差，边缘有磨损
        m.albedo = vec3(0.085, 0.090, 0.104) * (0.78 + 0.44 * panel) * (0.88 + 0.24 * grime);
        m.rough = 0.54 + 0.18 * panel;
        m.metal = 0.20;
        m.f0 = vec3(0.05);
    } else if (mat == M_ARMOR) {
        // 拉丝蓝钢：沿炮身轴向拉长的噪声 + 各向异性高光
        float brushed = gunNoise2(vec2(lp.z * 26.0, (lp.x + lp.y) * 760.0));
        m.albedo = vec3(0.38, 0.41, 0.47);
        m.f0 = vec3(0.54, 0.55, 0.58) * (0.90 + 0.12 * brushed);
        m.rough = 0.15 + 0.11 * brushed + 0.10 * grime;
        m.metal = 1.0;
        m.aniso = 0.75;
        // 爪尖与聚焦环：充能时发白热
        float tip = smoothstep(-17.10, -18.20, lp.z);
        float arrive = gunSat((gCharge - 0.45) * 2.0);
        m.emit += mix(ARC, ARC_HOT, arrive) * tip * (0.15 + 2.4 * arrive) * (0.85 + 0.15 * sin(gTime * 60.0));
    } else if (mat == M_COIL) {
        // 线圈：暗金属本体 + 内缘与端面凹槽里的电弧
        m.albedo = vec3(0.085, 0.092, 0.108);
        m.f0 = vec3(0.40, 0.41, 0.44);
        m.rough = 0.30 + 0.10 * grime;
        m.metal = 1.0;
        float r = length(lp.xy);
        float rim = 1.0 - smoothstep(0.0, 0.11, abs(r - 0.90));
        float groove = (1.0 - smoothstep(0.02, 0.06, abs(r - 1.22))) * gunSat(abs(n.z) * 1.6);
        // 开火后电弧自炮口倒着跑回炮闩
        float shotWave = 0.0;
        if (gFired >= 0.0) {
            float k = (lp.z - GUN_COIL_Z0) / GUN_COIL_STEP;
            shotWave = exp(-gunSq((gFired * 42.0 - k) / 1.5)) * 5.0;
        }
        float hum = 0.80 + 0.20 * sin(gTime * 26.0 + lp.z * 3.0);
        m.emit += ARC * rim * (0.06 + 2.2 * lit * hum + 7.0 * crest + shotWave);
        m.emit += ARC * groove * (0.10 + 1.4 * lit + 4.0 * crest + 0.5 * shotWave);
        m.emit += ARC_HOT * (rim + groove) * crest * 2.5;
    } else if (mat == M_CHANNEL) {
        // 加速通道 / 指示灯
        m.albedo = vec3(0.02);
        m.f0 = vec3(0.07);
        m.rough = 0.10;
        m.metal = 0.0;
        float pulse = 0.75 + 0.25 * sin(gTime * 7.0 + lp.z * 2.0);
        m.emit += ARC * (0.10 + 2.4 * lit * pulse + 9.0 * crest);
        m.emit += ARC_HOT * crest * 3.0;
    } else if (mat == M_CORE) {
        // 反应堆核心：随充能由青转白
        float pulse = 0.82 + 0.18 * sin(gTime * 5.0);
        m.albedo = vec3(0.02);
        m.f0 = vec3(0.05);
        m.rough = 0.15;
        m.emit += mix(ARC, ARC_HOT, gCharge * gCharge) * (2.2 + 5.0 * gCharge) * pulse;
    } else if (mat == M_FIN) {
        // 散热鳍：暗金属，靠近反应堆的一侧发红
        m.albedo = vec3(0.075, 0.078, 0.086);
        m.f0 = vec3(0.26);
        m.rough = 0.44;
        m.metal = 0.80;
        float heat = gunSat(1.0 - length(lp.xy) / 3.2);
        vec3 hot = mix(vec3(0.35, 0.03, 0.0), vec3(1.0, 0.35, 0.06), heat);
        m.emit += hot * heat * heat * (0.10 + 0.45 * gCharge) * (0.7 + 0.3 * sin(gTime * 1.6 + lp.z));
    } else {
        // M_DARK：缆线、支架、喷口
        m.albedo = vec3(0.036, 0.038, 0.044) * (0.85 + 0.30 * grime);
        m.rough = 0.66;
        m.metal = 0.15;
        m.f0 = vec3(0.06);
    }

    m.albedo *= 1.0 - seam * 0.45;
    m.rough = min(m.rough + seam * 0.25, 1.0);
    return m;
}

/** 各向异性 GGX 的 D 项（Filament 形式）。 */
float gunDGGXAniso(float at, float ab, float ht, float hb, float nh) {
    float a2 = at * ab;
    vec3 v = vec3(ab * ht, at * hb, a2 * nh);
    float v2 = dot(v, v);
    float w2 = a2 / max(v2, 1e-8);
    return a2 * w2 * w2 * (1.0 / PI);
}

/** 各向异性 GGX 的 V 项（含 1/(4 NoL NoV) 因子）。 */
float gunVSmitAniso(float at, float ab, float tv, float bv, float tl, float bl, float nv, float nl) {
    float lv = nl * length(vec3(at * tv, ab * bv, nv));
    float ll = nv * length(vec3(at * tl, ab * bl, nl));
    return 0.5 / max(lv + ll, 1e-5);
}

/** 一次光照的 BRDF（已乘 NoL）。 */
vec3 gunBRDF(vec3 n, vec3 v, vec3 l, GunMat m) {
    float nl = max(dot(n, l), 0.0);
    if (nl <= 0.0) return vec3(0.0);
    vec3 h = normalize(l + v);
    float nv = max(dot(n, v), 1e-3);
    float nh = max(dot(n, h), 0.0);
    float vh = max(dot(h, v), 0.0);
    vec3 F = m.f0 + (1.0 - m.f0) * pow(1.0 - vh, 5.0);
    float a = max(m.rough * m.rough, 0.0025);
    vec3 spec;
    if (m.aniso > 0.01) {
        vec3 T = vec3(0.0, 0.0, 1.0) - n * n.z;
        float tl = length(T);
        T = (tl > 1e-3) ? (T / tl) : vec3(1.0, 0.0, 0.0);
        vec3 B = cross(n, T);
        float at = max(a * (1.0 + m.aniso), 0.0025);
        float ab = max(a * (1.0 - m.aniso), 0.0025);
        float D = gunDGGXAniso(at, ab, dot(h, T), dot(h, B), nh);
        float V = gunVSmitAniso(at, ab, dot(v, T), dot(v, B), dot(l, T), dot(l, B), nv, nl);
        spec = F * D * V;
    } else {
        float d = nh * nh * (a * a - 1.0) + 1.0;
        float D = (a * a) / (PI * d * d);
        float k = (m.rough + 1.0) * (m.rough + 1.0) / 8.0;
        float G = (nv / (nv * (1.0 - k) + k)) * (nl / (nl * (1.0 - k) + k));
        spec = F * D * G / (4.0 * nv * nl + 1e-4);
    }
    vec3 diff = m.albedo * (1.0 - m.metal) / PI;
    return (diff + spec) * nl;
}

/** 一盏点光对表面的贡献。 */
vec3 gunPointLight(vec3 p, vec3 n, vec3 v, GunMat m, vec3 lp, vec3 lc, float power) {
    vec3 toL = lp - p;
    float d2 = dot(toL, toL);
    float d = sqrt(max(d2, 1e-4));
    return gunBRDF(n, v, toL / d, m) * lc * power / (d2 + 0.6);
}

/** 全部光照（不含追踪反射）。 */
vec3 gunLighting(vec3 p, vec3 n, vec3 v, GunMat m, float ao) {
    vec3 col = vec3(0.0);
    // 主光：远处的恒星
    col += gunBRDF(n, v, KEY_DIR, m) * KEY_COL * 3.8;
    // 补光：上方的星云
    float wrap = gunSat(dot(n, FILL_DIR) * 0.5 + 0.5);
    col += m.albedo * (1.0 - m.metal * 0.65) * FILL_COL * wrap * wrap * 0.70 * ao;
    // 环境底色
    col += m.albedo * vec3(0.045, 0.055, 0.085) * ao;
    // 枪自己的两盏灯：反应堆 + 炮口电荷
    float arrive = gunSat((gCharge - 0.45) * 2.0);
    col += gunPointLight(p, n, v, m, vec3(0.0, 0.0, 7.00 + gRecoil),
                         mix(ARC, ARC_HOT, gCharge * 0.6), 6.0 + 34.0 * gCharge);
    col += gunPointLight(p, n, v, m, vec3(0.0, 0.0, GUN_MUZZLE_Z + gRecoil),
                         mix(ARC, ARC_HOT, 0.4), 46.0 * arrive * arrive);
    if (gFired >= 0.0) {
        col += gunPointLight(p, n, v, m, vec3(0.0, 0.0, GUN_MUZZLE_Z + gRecoil),
                             vec3(1.0, 0.95, 0.90), 2600.0 * gFlash);
    }
    // 菲涅尔边缘光
    float fres = pow(1.0 - gunSat(dot(n, v)), 4.0);
    col += ARC * fres * (0.06 + 0.22 * gCharge) * ao;
    return col * mix(0.45, 1.0, ao) + m.emit;
}

/** 一个命中点的最终颜色。 */
vec3 gunShade(vec3 p, vec3 rd, float mat) {
    vec3 n = gunNormal(p);
    vec3 lp = vec3(p.x, p.y, p.z - gRecoil);
    GunMat m = gunMaterial(lp, n, mat);
    vec3 v = -rd;
    float ao = gunOcclusion(p, n);
    return gunLighting(p, n, v, m, ao);
}

// ---------------------------------------------------------------- 枪自己的光

/** 射线到点的距离（t 为射线参数）。 */
float gunRayPointDist(vec3 ro, vec3 rd, vec3 pt, out float t) {
    vec3 v = pt - ro;
    t = dot(v, rd);
    if (t < 0.0) t = 0.0;
    return length(v - rd * t);
}

/** 射线到 z 轴线段（a→b）的距离。 */
float gunRaySegDist(vec3 ro, vec3 rd, vec3 a, vec3 b, out float tRay) {
    vec3 dir = b - a;
    float len2 = dot(dir, dir);
    if (len2 < 1e-6) return gunRayPointDist(ro, rd, a, tRay);
    // 射线到线段的最近距离：先求无限直线的垂距
    vec3 v = ro - a;
    float t = -dot(v, rd);
    tRay = max(t, 0.0);
    vec3 closest = ro + rd * t;
    float s = dot(closest - a, dir) / len2;
    s = clamp(s, 0.0, 1.0);
    vec3 q = a + dir * s;
    float td;
    return gunRayPointDist(ro, rd, q, td);
}

/** 炮口电荷点：爪尖之间那颗越聚越亮的弧光球。 */
vec3 gunChargePoint(vec3 rd, float tLimit) {
    float amt = gunSat((gCharge - 0.42) * 2.0);
    if (amt <= 0.001 || gFired >= 0.0) return vec3(0.0);
    vec3 c = vec3(0.0, 0.0, GUN_MUZZLE_Z + gRecoil) - CamPos;
    float t = dot(c, rd);
    if (t <= 0.0 || t > tLimit + 0.4) return vec3(0.0);
    float d = length(c - rd * t);
    float r = max(gPix * t, 0.0025);
    float core = exp(-gunSq(d / (r * 1.3)));
    // 晕：短程（1/d²）但有硬性的作用半径，免得把整幅画面糊成雾
    float halo = 0.05 / (1.0 + gunSq(d / (r * 6.0))) * exp(-d * 0.55);
    return (ARC_HOT * core * 2.6 + ARC * halo * 1.8) * amt;
}

/** 开火闪光：炮口炸开的白团 + 扩散的冲击环。 */
vec3 gunFlash(vec3 rd, float tLimit) {
    if (gFired < 0.0 || gFired > 0.8) return vec3(0.0);
    vec3 c = vec3(0.0, 0.0, GUN_MUZZLE_Z - 0.4 + gRecoil) - CamPos;
    float dist = length(c);
    float t = dot(c, rd);
    if (t <= 0.0) return vec3(0.0);
    float d = length(c - rd * t);
    float lateral = d * dist;
    float hard = exp(-gFired * 22.0);
    float soft = exp(-gFired * 7.0);
    float burst = exp(-lateral / (0.55 + gFired * 9.0)) * 26.0 * soft
                + exp(-lateral / 7.0) * 3.5 * hard;
    // 六道尖刺
    vec3 off = rd - (c / dist) * dot(rd, c / dist);
    float ang = atan(dot(off, CamUp), dot(off, CamRight));
    float spikes = pow(abs(cos(ang * 3.0 + 0.4)), 60.0) * exp(-d / (0.35 + gFired * 1.8)) * 7.0 * soft;
    // 冲击环
    float ring = exp(-gunSq((dist - (1.2 + gFired * 55.0)) / (0.7 + gFired * 6.0))) * 3.0 * soft;
    vec3 col = vec3(1.0, 0.96, 0.93) * (burst + spikes) + ARC * ring;
    return col;
}

/** 出膛弹道：自炮口沿 -Z 的一束白热细光。 */
vec3 gunBeam(vec3 rd, float tLimit) {
    if (gFired < 0.0) return vec3(0.0);
    float reach = 220.0 * gunSat(gFired * 18.0);
    vec3 a = vec3(0.0, 0.0, GUN_MUZZLE_Z + gRecoil);
    vec3 b = vec3(0.0, 0.0, GUN_MUZZLE_Z + gRecoil - reach);
    float t;
    float d = gunRaySegDist(CamPos, rd, a, b, t);
    if (t > tLimit) return vec3(0.0);
    float w = max(gPix * t, 0.02);
    float core = gunSat(1.0 - d / w);
    float glow = exp(-d / (w * 3.0));
    float fade = gunSat(1.0 - gFired * 1.4);
    return (vec3(1.0, 0.97, 0.95) * core * 2.2 + ARC * glow * 1.4) * fade;
}

// ---------------------------------------------------------------- main

void main() {
    gTime = GameTime;
    gCharge = gunSat(Charge);
    gFired = Fired;
    gPix = max(PixelSize, 0.0001);
    gRecoil = (gFired >= 0.0) ? 1.15 * (1.0 - exp(-gFired * 13.0)) * exp(-gFired * 0.85) : 0.0;
    gFlash = (gFired >= 0.0) ? exp(-gFired * 24.0) : 0.0;

    vec2 ndc = vUV;
    vec2 screen = vec2(ndc.x * Aspect, ndc.y);
    vec3 rd = normalize(CamForward + (CamRight * screen.x + CamUp * screen.y) * TanHalf);

    vec2 hit = gunMarch(CamPos, rd, 1e9);
    float tHit = (hit.x > 0.0) ? hit.x : 1e9;

    vec3 col = vec3(0.0);
    float cover = 0.0;
    if (hit.x > 0.0) {
        col = gunShade(CamPos + rd * hit.x, rd, hit.y);
        cover = 1.0;
    }

    // 枪自己的光（画在枪之前）
    vec3 light = gunChargePoint(rd, tHit) + gunFlash(rd, tHit) + gunBeam(rd, tHit);
    col += light;

    col = 1.0 - exp(-col * 1.10);
    col = pow(max(col, vec3(0.0)), vec3(1.0 / 2.2));
    float alpha = gunSat(cover * Alpha + dot(light, vec3(0.30, 0.45, 0.25)) * 0.8);
    fragColor = vec4(col * Alpha, alpha);
}
