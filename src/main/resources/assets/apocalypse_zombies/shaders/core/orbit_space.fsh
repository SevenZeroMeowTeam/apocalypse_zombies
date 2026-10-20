#version 150

// 轨道打击的「太空全景」：全屏光线步进（raymarch）出的行星系外景。
//
// 做法照搬参考包 the-shooting-star 的 star_space.fsh：整幅画面由一个片元着色器画出来 ——
// 相机在 shader 空间里，天空、行星、行星环、恒星全都在这个 pass 里算，
// 不用在世界里摆模型、也不用画公告板。
//
// 与参考包不同的是：
//   * 贴图全部是我们自己烘焙的（space_panorama.png / planet_albedo.png），
//     不用参考包的 NASA 素材；
//   * 相机是「轨道机位」给的，绕着地球转，模拟卫星绕飞；
//   * 行星只有一个（地球），不做完整太阳系 —— 打击演出里观众只看得到近处这个。
//
// 由 OrbitSpacePass 每帧喂相机四元组。

uniform vec3 CamPos;        // 相机位置（以地球半径为单位）
uniform vec3 CamForward;    // 相机前向
uniform vec3 CamRight;      // 相机右向
uniform vec3 CamUp;         // 相机上向
uniform float TanHalf;      // 垂直视场半角正切
uniform float Aspect;       // 画面宽高比
uniform float Alpha;        // 整体不透明度
uniform float Reveal;       // 0..1 演出揭示进度

uniform sampler2D Panorama;    // 2048×1024 等距柱状银河全景
uniform sampler2D PlanetMap;   // 1024×1024 行星表面图（RGB=反照率, A=云）

// 顶点着色器传来的屏幕坐标（-1..1）
in vec2 texCoord0;

out vec4 fragColor;

const float PI = 3.14159265;
const float TAU = 6.2831853;
/** 地球半径（场景单位）。相机在 1.35 半径处 —— 轨道高度。 */
const float EARTH_R = 1.0;
const float ATMO_R = 1.045;

// ------------------------------------------------------------------ 工具

float sqr(float x) { return x * x; }

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

/** 方向 → 等距柱状 uv。 */
vec2 dirToEquirect(vec3 d) {
    float lon = atan(d.z, d.x);
    float lat = asin(clamp(d.y, -1.0, 1.0));
    return vec2(lon / TAU + 0.5, 0.5 - lat / PI);
}

/** 射线与球求交。返回命中距离，未命中返回 -1。 */
float raySphere(vec3 ro, vec3 rd, vec3 center, float radius) {
    vec3 oc = ro - center;
    float b = dot(oc, rd);
    float c = dot(oc, oc) - radius * radius;
    float h = b * b - c;
    if (h < 0.0) {
        return -1.0;
    }
    float t = -b - sqrt(h);
    return t > 0.0 ? t : -1.0;
}

// ------------------------------------------------------------------ 天空

/**
 * 银河全景：等距柱状贴图 + 一点点程序化抖动。
 *
 * <p>抖动是为了打散 2048 宽贴图在 1080p 上的采样阶梯感 ——
 * 一点点噪声让星星看起来有大小差别。</p>
 */
vec3 skyColor(vec3 rd) {
    vec2 uv = dirToEquirect(rd);
    // 采样点的微小抖动 → 星星有「实」有「虚」
    float dither = hash12(floor(uv * 2048.0)) - 0.5;
    vec3 col = texture(Panorama, uv + vec2(dither, dither) * (0.6 / 2048.0)).rgb;
    return col;
}

// ------------------------------------------------------------------ 行星

/**
 * 地球表面：反照率贴图 + 云层 + 晨昏线。
 *
 * @param n      表面法线
 * @param sunDir 太阳方向（单位向量）
 * @param uv     表面 uv
 */
vec3 planetSurface(vec3 n, vec3 sunDir, vec2 uv) {
    vec4 map = texture(PlanetMap, uv);
    vec3 albedo = map.rgb;
    float clouds = map.a;

    // 漫反射：Lambert + 一点边缘变暗（掠射角）
    float ndl = max(dot(n, sunDir), 0.0);
    float limb = pow(max(dot(n, -normalize(CamPos)), 0.0), 0.35);
    float light = ndl * mix(0.75, 1.0, limb);

    vec3 col = albedo * light;

    // 云：按自己的法线受光，比地面亮一点
    if (clouds > 0.001) {
        // 云的法线用球面法线近似（云是薄层）
        float cloudLight = ndl * 1.15;
        col = mix(col, vec3(0.94, 0.96, 1.0) * cloudLight, clouds * 0.85);
    }

    // 海面镜面高光：只有低频反照率（偏蓝）的地方才有
    float ocean = 1.0 - smoothstep(0.18, 0.42, dot(albedo, vec3(0.33)));
    if (ocean > 0.01 && ndl > 0.0) {
        vec3 h = normalize(sunDir - normalize(CamPos));
        float spec = pow(max(dot(n, h), 0.0), 90.0);
        col += vec3(1.0, 0.9, 0.72) * spec * ocean * ndl * 0.9;
    }

    // 夜面：不是纯黑，留一点城市灯的暖色
    float night = 1.0 - smoothstep(0.0, 0.12, ndl);
    col += vec3(0.16, 0.10, 0.045) * night * (1.0 - clouds * 0.6);

    return col;
}

// ------------------------------------------------------------------ 大气

/**
 * 大气：沿视线在球壳里积分一点光学深度。
 *
 * <p>不做完整 Rayleigh/Mie（那是参考包的做法，要 12 步积分），
 * 这里用更省的解析近似：算出视线穿过大气层的「深度」，再按太阳角度染色。</p>
 */
vec3 atmosphere(vec3 rd, vec3 sunDir, vec3 center) {
    vec3 oc = CamPos - center;
    float b = dot(oc, rd);
    float c = dot(oc, oc) - ATMO_R * ATMO_R;
    float h = b * b - c;
    if (h < 0.0) {
        return vec3(0.0);
    }
    float t = -b - sqrt(h);
    if (t < 0.0) {
        t = 0.0;
    }
    // 视线在大气里的「厚度」（切线越靠边越厚）
    float chord = 2.0 * sqrt(max(h, 0.0));
    float thick = chord / (2.0 * ATMO_R);
    // 太阳越斜，红色越多（大气把蓝光散射掉了）
    float sunAmount = max(dot(rd, sunDir), 0.0);
    vec3 tint = mix(vec3(1.0, 0.45, 0.20), vec3(0.30, 0.55, 1.0), sunAmount);
    float power = pow(1.0 - thick, 3.0);
    return tint * power * 0.9;
}

// ------------------------------------------------------------------ 主

void main() {
    // —— 射线：从相机四元组重建
    //    texCoord0 就是顶点的 NDC 坐标（Minecraft 的 core shader 里
    //    Position 送进来的就是裁剪空间坐标，范围 -1..1），
    //    **不能再做一次 *2-1**，否则视线会平移一倍、把地球推出画面。
    vec2 ndc = texCoord0;
    vec3 rd = normalize(CamForward
            + CamRight * (ndc.x * TanHalf * Aspect)
            + CamUp * (ndc.y * TanHalf));
    vec3 ro = CamPos;

    // —— 太阳：方向固定在画面左上（与 3D 舞台的 SUN_ANGLE 一致的观感）
    // —— 太阳方向：**跟随相机**（左上方），所以镜头绕地球飞时，
    //    朝着我们这一面永远是亮的，晨昏线落在盘子右侧。
    //    （纯世界坐标的固定太阳，镜头转到夜面时整个地球全黑 —— 那样不好看。）
    //    注意方向：太阳方向是「从表面指向太阳」。
    //    地球朝着我们的那一面，其法线 n ≈ -CamForward，
    //    所以要让这一面被照亮，sunDir 必须有 **-CamForward** 分量（太阳在镜头背后）。
    vec3 sunDir = normalize(-CamForward * 0.80 - CamRight * 0.44 + CamUp * 0.40);

    vec3 col;

    // —— 行星
    float t = raySphere(ro, rd, vec3(0.0), EARTH_R);
    if (t > 0.0) {
        vec3 hit = ro + rd * t;
        vec3 n = normalize(hit);
        // 球面 uv（绕 Y 轴）
        float lon = atan(hit.z, hit.x);
        float lat = asin(clamp(n.y, -1.0, 1.0));
        vec2 uv = vec2(lon / TAU + 0.5, 0.5 - lat / PI);
        col = planetSurface(n, sunDir, uv);
        // 大气：命中行星时，天空那一层不画（被行星挡住），但边缘的大气辉光要加
        col += atmosphere(rd, sunDir, vec3(0.0)) * 0.35;
    } else {
        // —— 天空
        col = skyColor(rd);
        // 大气：没命中行星时，视线穿过大气层（在行星背后）
        col += atmosphere(rd, sunDir, vec3(0.0));
        // —— 太阳
        float sd = length(rd - sunDir);
        // 日面 + 光晕
        col += vec3(1.0, 0.92, 0.78) * smoothstep(0.012, 0.006, sd) * 6.0;
        col += vec3(1.0, 0.80, 0.55) * (0.06 / (sd * sd + 0.0009)) * 0.5;
    }

    // —— 演出揭示：从全黑里淡入
    col *= clamp(Reveal, 0.0, 1.0);

    fragColor = vec4(col, Alpha);
}
