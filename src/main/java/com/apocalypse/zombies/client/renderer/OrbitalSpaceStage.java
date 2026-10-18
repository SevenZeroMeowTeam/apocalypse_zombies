package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.client.OrbitalStrikeClientState;
import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import net.minecraft.client.Camera;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.util.Mth;
import net.minecraft.util.RandomSource;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;

/**
 * 「全部打击都从外太空发起」的轨道舞台。
 *
 * <p>六种弹种共用一套深空底 + 写实地球，再各自挂一个轨道发射装置：
 * 轨道炮台（动能弹）、轨道长矛台、奇点、五枚投放舱（等离子风暴）、卫星（宇宙激光）、
 * 掠地陨石（行星陨落）。所有几何都按相机的 yaw/pitch 三轴摆放 —— 世界坐标在这里没有意义
 * （PoseStack 已经 translate(-camera)，而相机在 Y≥460）。</p>
 *
 * <p><b>渲染约束</b>：只用 {@link RenderType#debugQuads()}（面）和 {@link RenderType#lines()}
 * （线，{@code line()} 带法线，不能塞进 POSITION_COLOR 缓冲），不建自定义 RenderType、
 * 不做全屏 shader/FBO —— 与 Embeddium/Sodium 的历史崩溃保持距离。</p>
 *
 * <p><b>权威边界</b>：这里全是客户端装饰。伤害、地形改动、挖穿到虚空都在服务端的落点结算，
 * 客户端只负责把「谁在开火、从哪打过来」演给玩家看。</p>
 */
public final class OrbitalSpaceStage {

    private static final float CYAN_R = 0.40F;
    private static final float CYAN_G = 0.91F;
    private static final float CYAN_B = 0.98F;
    /** 深空底：包围相机的盒子半距 / 面片半宽。 */
    private static final double BACKDROP_FAR = 170.0D;
    private static final double BACKDROP_EXTENT = 220.0D;
    /** 地球：镜头前方多远、半径多大。 */
    private static final double EARTH_FORWARD = 112.0D;
    private static final double EARTH_SIDE = -28.0D;
    private static final double EARTH_HEIGHT = -14.0D;
    private static final double EARTH_RADIUS = 21.0D;
    /** 太阳方向（相机平面内的角度）：约左上 137°。 */
    private static final double SUN_ANGLE = Math.toRadians(137.0D);
    /**
     * 视距自适应：原版远裁剪面 = 有效视距 × 16 × 4。低视距（2~6 区块）下 170 格外的
     * 深空底会被裁掉、地球也会顶到裁剪面，所以整场布景按比例拉近，构图不变。
     */
    private static double sceneScale = 1.0D;

    private OrbitalSpaceStage() {
    }

    /**
     * 画一帧轨道舞台。
     *
     * @param stageOpacity 布景整体不透明度（回位段淡出用；0 = 完全交给真实世界）
     */
    public static void render(PoseStack pose, VertexConsumer lines,
                              MultiBufferSource.BufferSource buffers, Matrix4f matrix,
                              long gameTime, float partial, float stageOpacity) {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.level == null || stageOpacity <= 0.005F) {
            return;
        }
        double far = Math.max(160.0D, minecraft.options.getEffectiveRenderDistance() * 16.0D * 4.0D);
        sceneScale = Mth.clamp(far / 768.0D, 0.42D, 1.0D);
        Camera cam = minecraft.gameRenderer.getMainCamera();
        Vec3 camPos = cam.getPosition();
        double yaw = Math.toRadians(cam.getYRot());
        double pitch = Math.toRadians(cam.getXRot());
        double sy = Math.sin(yaw);
        double cy = Math.cos(yaw);
        double sp = Math.sin(pitch);
        double cp = Math.cos(pitch);
        // 相机三轴（Minecraft yaw：0 = 朝 +Z；右侧 = -X 方向）。
        double[] fwd = new double[]{-sy * cp, -sp, cy * cp};
        double[] right = new double[]{-cy, 0.0D, -sy};
        double[] up = new double[]{-sy * sp, cp, cy * sp};
        double[] eye = new double[]{camPos.x, camPos.y, camPos.z};
        double time = gameTime + partial;

        // 布景从镜头离开地面时淡入；回位段再由 stageOpacity 淡出。
        float fadeIn = Mth.clamp((float) ((OrbitalStrikeClientState.elapsed()
                - (OrbitalStrikeClientState.lockTicks() - OrbitalCinematic.pullLeadTicks())) / 14.0D),
                0.0F, 1.0F);
        float fade = smooth(fadeIn) * stageOpacity;
        if (fade <= 0.005F) {
            return;
        }

        VertexConsumer quads = buffers.getBuffer(RenderType.debugQuads());
        drawBackdrop(pose, lines, quads, matrix, eye, fwd, right, up, time, fade);

        double[] earth = offset(eye, fwd, right, up, EARTH_FORWARD, EARTH_SIDE, EARTH_HEIGHT);
        renderEarth(pose, lines, quads, matrix, earth, fwd, right, up, EARTH_RADIUS * sceneScale, fade, time);

        OrbitalStrikeMode mode = OrbitalStrikeClientState.mode();
        double phase = OrbitalCinematic.spaceFireProgress();
        switch (mode) {
            case CANNON -> renderCannon(pose, lines, quads, matrix, eye, fwd, right, up,
                    earth, EARTH_RADIUS * sceneScale, fade, time, phase);
            case LANCE -> renderLance(pose, lines, quads, matrix, eye, fwd, right, up,
                    earth, EARTH_RADIUS * sceneScale, fade, time, phase);
            case GRAVITY -> renderSingularity(pose, lines, quads, matrix, eye, fwd, right, up,
                    earth, EARTH_RADIUS * sceneScale, fade, time, phase);
            case STORM -> renderStorm(pose, lines, quads, matrix, eye, fwd, right, up,
                    earth, EARTH_RADIUS * sceneScale, fade, time);
            case PLANET -> renderMeteor(pose, lines, quads, matrix, eye, fwd, right, up,
                    earth, EARTH_RADIUS * sceneScale, fade, time);
            default -> renderSatelliteBeam(pose, lines, quads, matrix, eye, fwd, right, up,
                    earth, EARTH_RADIUS * sceneScale, fade, time, phase);
        }
    }

    // ------------------------------------------------------------------ 背景

    /**
     * 宇宙全景：相机中心的全天球，而不是几个大面片。
     *
     * <p>由远到近叠五层：暗蓝渐变穹顶（18×36 小面片，避免任何巨大单面）→ 银河带星群 →
     * 三团彩色星云 → 一个遥远旋涡星系 → 约 900 颗分色恒星，最后加两粒偶发流星。
     * 全部程序化生成（固定种子，每次播放同一片星空），不使用外部贴图。</p>
     */
    private static void drawBackdrop(PoseStack pose, VertexConsumer lines, VertexConsumer quads,
                                     Matrix4f matrix, double[] eye,
                                     double[] fwd, double[] right, double[] up,
                                     double time, float alpha) {
        double radius = 150.0D * sceneScale;
        drawDome(quads, matrix, eye, fwd, right, up, radius, alpha);
        drawMilkyWay(pose, lines, eye, fwd, right, up, radius * 0.97D, alpha, time);
        drawNebulae(quads, matrix, eye, fwd, right, up, radius * 0.95D, alpha, time);
        drawGalaxy(pose, lines, quads, matrix, eye, fwd, right, up, radius * 0.93D, alpha, time);
        drawDistantGalaxies(pose, lines, eye, fwd, right, up, radius * 0.94D, alpha);
        drawStars(pose, lines, eye, fwd, right, up, radius * 0.99D, alpha, time);
        drawShootingStars(pose, lines, eye, fwd, right, up, radius * 0.98D, alpha, time);
    }

    /** 暗蓝渐变穹顶：越朝天顶越黑，越朝地平线越偏蓝（大气散射的错觉）。 */
    private static void drawDome(VertexConsumer quads, Matrix4f matrix, double[] eye,
                                 double[] fwd, double[] right, double[] up, double radius, float alpha) {
        final int rings = 18;
        final int segs = 36;
        for (int ri = 0; ri < rings; ri++) {
            double t0 = Math.PI * ri / rings;
            double t1 = Math.PI * (ri + 1) / rings;
            for (int si = 0; si < segs; si++) {
                double p0 = Math.PI * 2.0D * si / segs;
                double p1 = Math.PI * 2.0D * (si + 1) / segs;
                double[] a = spherePoint(eye, fwd, right, up, radius, t0, p0);
                double[] b = spherePoint(eye, fwd, right, up, radius, t0, p1);
                double[] c = spherePoint(eye, fwd, right, up, radius, t1, p1);
                double[] d = spherePoint(eye, fwd, right, up, radius, t1, p0);
                // 中点朝向的「世界向上」分量：+1 天顶，-1 天底
                double midT = (t0 + t1) * 0.5D;
                double midP = (p0 + p1) * 0.5D;
                double[] mid = sphereDir(fwd, right, up, midT, midP);
                double upDot = mid[0] * up[0] + mid[1] * up[1] + mid[2] * up[2];
                float f = (float) ((upDot + 1.0D) * 0.5D);
                float r = Mth.lerp(f, 0.012F, 0.003F);
                float g = Mth.lerp(f, 0.024F, 0.006F);
                float bl = Mth.lerp(f, 0.048F, 0.016F);
                // 极轻微的面片抖动，避免大面积色带
                double n = Math.sin(ri * 12.9898D + si * 78.233D) * 43758.5453D;
                n -= Math.floor(n);
                float jitter = (float) n * 0.0020F;
                quad(quads, matrix,
                        a[0], a[1], a[2], b[0], b[1], b[2],
                        c[0], c[1], c[2], d[0], d[1], d[2],
                        r + jitter, g + jitter, bl + jitter, alpha * 0.995F);
            }
        }
    }

    /** 银河：沿一个倾斜大圆聚集的星群 + 两条很淡的辉光带。 */
    private static void drawMilkyWay(PoseStack pose, VertexConsumer lines, double[] eye,
                                     double[] fwd, double[] right, double[] up,
                                     double radius, float alpha, double time) {
        double[] normal = norm(add(add(mul(right, 0.32D), mul(up, 0.58D)), mul(fwd, 0.75D)));
        RandomSource random = RandomSource.create(0x4D494C4B59574159L);
        for (int i = 0; i < 620; i++) {
            double[] dir = randomDirection(random);
            double dist = dir[0] * normal[0] + dir[1] * normal[1] + dir[2] * normal[2];
            double w = Math.exp(-(dist * dist) / (2.0D * 0.16D * 0.16D));
            if (random.nextDouble() > w * 0.95D) {
                continue;
            }
            double[] p = add(eye, mul(dir, radius));
            float a = alpha * (0.10F + 0.22F * (float) w)
                    * (0.6F + 0.4F * (0.5F + 0.5F * (float) Math.sin(time * 0.04D + i * 2.1D)));
            double s = 0.10D + 0.22D * random.nextDouble();
            line(pose, lines, p[0] - s, p[1], p[2], p[0] + s, p[1], p[2],
                    0.78F, 0.84F, 1.0F, a, 0, 0, 1);
            line(pose, lines, p[0], p[1] - s, p[2], p[0], p[1] + s, p[2],
                    0.78F, 0.84F, 1.0F, a, 0, 0, 1);
        }
    }

    /**
     * 彩色星云（按参考图）：四团 — 品红/橙金/冰蓝/青绿，每团由几十个小色块 +
     * 几颗亮结叠成，位置固定在画面左侧与下方，和右侧的大星系形成冷暖对比。
     */
    private static void drawNebulae(VertexConsumer quads, Matrix4f matrix, double[] eye,
                                    double[] fwd, double[] right, double[] up,
                                    double radius, float alpha, double time) {
        RandomSource random = RandomSource.create(0x4E4542554C4145L);
        double[][] centers = {
                {0.30D, 0.55D, 0.62D},     // 左上：品红
                {-0.55D, 0.30D, 0.55D},    // 左中：橙金
                {-0.35D, -0.55D, 0.60D},   // 左下：冰蓝
                {0.45D, -0.45D, 0.62D}};   // 右下：青绿
        float[][] palette = {
                {0.62F, 0.16F, 0.46F},
                {0.62F, 0.30F, 0.10F},
                {0.16F, 0.34F, 0.62F},
                {0.10F, 0.44F, 0.40F}};
        for (int c = 0; c < centers.length; c++) {
            double[] center = cameraDir(fwd, right, up, centers[c][0], centers[c][1], centers[c][2]);
            for (int i = 0; i < 78; i++) {
                double[] dir = norm(add(center, new double[]{
                        (random.nextDouble() - 0.5D) * 0.62D,
                        (random.nextDouble() - 0.5D) * 0.62D,
                        (random.nextDouble() - 0.5D) * 0.62D}));
                double[] p = add(eye, mul(dir, radius * (0.94D + random.nextDouble() * 0.08D)));
                double size = (2.0D + random.nextDouble() * 8.0D) * sceneScale;
                float breathe = 0.70F + 0.30F * (0.5F + 0.5F * (float) Math.sin(time * 0.03D + c * 2.0D + i));
                float[] col = palette[c];
                // 少量更亮的核心色块
                float boost = i % 17 == 0 ? 1.6F : 1.0F;
                planeQuad(quads, matrix, p, right, up,
                        -size, -size * 0.60D, size, size * 0.60D,
                        col[0] * boost, col[1] * boost, col[2] * boost,
                        alpha * (0.035F + 0.035F * random.nextFloat()) * breathe);
            }
            // 星云里的亮结（年轻星团）
            for (int k = 0; k < 4; k++) {
                double[] dir = norm(add(center, new double[]{
                        (random.nextDouble() - 0.5D) * 0.30D,
                        (random.nextDouble() - 0.5D) * 0.30D,
                        (random.nextDouble() - 0.5D) * 0.30D}));
                double[] p = add(eye, mul(dir, radius * 0.96D));
                solidDisc(quads, matrix, p, right, up, (0.35D + random.nextDouble() * 0.75D) * sceneScale,
                        1.0F, 0.95F, 1.0F, alpha * 0.55F);
            }
        }
    }

    /**
     * 大螺旋星系（按参考图）：暖白核心 + 四条对数螺旋臂 + 臂间星点 + 倾斜盘面，
     * 固定在画面右上方；色温从核心的暖金过渡到外缘的冷白。
     */
    private static void drawGalaxy(PoseStack pose, VertexConsumer lines, VertexConsumer quads,
                                   Matrix4f matrix, double[] eye,
                                   double[] fwd, double[] right, double[] up,
                                   double radius, float alpha, double time) {
        double[] center = add(eye, mul(cameraDir(fwd, right, up, 0.72D, 0.52D, 0.16D), radius));
        // 倾斜盘面的基：把 right/up 旋一下并压扁
        double rot = 0.55D;
        double[] gr = add(mul(right, Math.cos(rot)), mul(up, Math.sin(rot)));
        double[] gu = mul(add(mul(up, Math.cos(rot)), mul(right, -Math.sin(rot))), 0.52D);
        // 外层柔光
        for (int i = 8; i >= 1; i--) {
            double rr = 34.0D * i / 8.0D * sceneScale;
            planeRingDirect(quads, matrix, center, gr, gu, rr,
                    1.0F, 0.92F, 0.78F, alpha * 0.020F);
            planeRingDirect(quads, matrix, center, gr, gu, rr * 0.98D,
                    0.90F, 0.94F, 1.0F, alpha * 0.012F);
        }
        // 核心：暖白到金黄
        solidDisc(quads, matrix, center, gr, gu, 5.2D * sceneScale,
                1.0F, 0.94F, 0.80F, alpha * 0.85F);
        solidDisc(quads, matrix, center, gr, gu, 3.0D * sceneScale,
                1.0F, 0.98F, 0.90F, alpha * 0.95F);
        planeRing(pose, lines, center, gr, gu, 5.4D * sceneScale,
                1.0F, 0.90F, 0.70F, alpha * 0.35F);
        // 四条对数螺旋臂
        RandomSource random = RandomSource.create(0x47414C415859L);
        for (int arm = 0; arm < 4; arm++) {
            double base = arm * Math.PI * 0.5D + 0.35D;
            double prevX = 0.0D;
            double prevY = 0.0D;
            for (int k = 1; k <= 26; k++) {
                double t = k / 26.0D;
                double rr = (3.0D + 30.0D * t) * sceneScale;
                double ang = base + t * 3.4D;
                double x = Math.cos(ang) * rr;
                double y = Math.sin(ang) * rr * 0.55D;
                if (k > 1) {
                    line(pose, lines,
                            center[0] + gr[0] * prevX + gu[0] * prevY,
                            center[1] + gr[1] * prevX + gu[1] * prevY,
                            center[2] + gr[2] * prevX + gu[2] * prevY,
                            center[0] + gr[0] * x + gu[0] * y,
                            center[1] + gr[1] * x + gu[1] * y,
                            center[2] + gr[2] * x + gu[2] * y,
                            0.92F, 0.92F, 1.0F, alpha * 0.16F * (1.0F - (float) t * 0.6F), 0, 0, 1);
                }
                // 臂上的星点：越往外越蓝
                for (int dot = 0; dot < 3; dot++) {
                    double jx = (random.nextDouble() - 0.5D) * 2.2D * sceneScale;
                    double jy = (random.nextDouble() - 0.5D) * 1.4D * sceneScale;
                    double sx = center[0] + gr[0] * (x + jx) + gu[0] * (y + jy);
                    double sy = center[1] + gr[1] * (x + jx) + gu[1] * (y + jy);
                    double sz = center[2] + gr[2] * (x + jx) + gu[2] * (y + jy);
                    float warm = 1.0F - (float) t;
                    float cr = 0.80F + 0.20F * warm;
                    float cg = 0.86F + 0.10F * warm;
                    float cb = 1.0F;
                    float ca = alpha * (0.20F + 0.40F * random.nextFloat()) * (0.4F + 0.6F * warm);
                    double ss = (0.18D + random.nextDouble() * 0.28D) * sceneScale;
                    line(pose, lines, sx - ss, sy, sz, sx + ss, sy, sz, cr, cg, cb, ca, 0, 0, 1);
                    line(pose, lines, sx, sy - ss, sz, sx, sy + ss, sz, cr, cg, cb, ca, 0, 0, 1);
                }
                prevX = x;
                prevY = y;
            }
        }
    }

    /** 十几个遥远的星系：小椭圆盘 + 少数带旋臂，冷/暖色混杂。 */
    private static void drawDistantGalaxies(PoseStack pose, VertexConsumer lines, double[] eye,
                                            double[] fwd, double[] right, double[] up,
                                            double radius, float alpha) {
        RandomSource random = RandomSource.create(0x44495354414EL);
        for (int i = 0; i < 14; i++) {
            double[] dir = randomDirection(random);
            double[] center = add(eye, mul(dir, radius));
            double size = (1.0D + random.nextDouble() * 3.0D) * sceneScale;
            double tilt = random.nextDouble() * Math.PI;
            double flat = 0.35D + random.nextDouble() * 0.55D;
            boolean warm = random.nextBoolean();
            float r = warm ? 1.0F : 0.78F;
            float g = warm ? 0.86F : 0.88F;
            float b = warm ? 0.66F : 1.0F;
            planeEllipse(pose, lines, center, right, up, size, size * flat, tilt,
                    r, g, b, alpha * (0.14F + random.nextFloat() * 0.16F));
            if (i % 4 == 0) {
                planeEllipse(pose, lines, center, right, up, size * 0.55D, size * 0.30D, tilt + 0.6D,
                        1.0F, 1.0F, 1.0F, alpha * 0.20F);
            }
        }
    }

    /** 约 900 颗恒星：分色（蓝白/白/暖黄）、分大小、各自缓慢脉动。 */
    private static void drawStars(PoseStack pose, VertexConsumer lines, double[] eye,
                                  double[] fwd, double[] right, double[] up,
                                  double radius, float alpha, double time) {
        RandomSource random = RandomSource.create(0x53504143454CL);
        for (int i = 0; i < 900; i++) {
            double[] dir = randomDirection(random);
            double[] p = add(eye, mul(dir, radius * (0.94D + random.nextDouble() * 0.08D)));
            float tint = random.nextFloat();
            float r;
            float g;
            float b;
            if (tint < 0.16F) {
                r = 0.72F;
                g = 0.82F;
                b = 1.0F;
            } else if (tint < 0.28F) {
                r = 1.0F;
                g = 0.90F;
                b = 0.72F;
            } else {
                r = 0.88F;
                g = 0.93F;
                b = 1.0F;
            }
            float pulse = 0.45F + 0.55F * (0.5F + 0.5F * (float) Math.sin(time * 0.045D + i * 1.37D));
            float a = alpha * pulse * (0.30F + 0.55F * random.nextFloat());
            double s = (i % 37 == 0 ? 0.42D : 0.14D + random.nextDouble() * 0.14D) * sceneScale;
            line(pose, lines, p[0] - s, p[1], p[2], p[0] + s, p[1], p[2], r, g, b, a, 0, 0, 1);
            line(pose, lines, p[0], p[1] - s, p[2], p[0], p[1] + s, p[2], r, g, b, a, 0, 0, 1);
            // 最亮的一批带四芒星（参考图里亮星的十字星芒）
            if (i % 37 == 0) {
                double spike = s * 6.0D;
                line(pose, lines, p[0] - spike, p[1], p[2], p[0] + spike, p[1], p[2],
                        r, g, b, a * 0.35F, 0, 0, 1);
                line(pose, lines, p[0], p[1] - spike, p[2], p[0], p[1] + spike, p[2],
                        r, g, b, a * 0.35F, 0, 0, 1);
            }
        }
    }

    /** 偶发流星：两粒，按周期在天空划过一小段。 */
    private static void drawShootingStars(PoseStack pose, VertexConsumer lines, double[] eye,
                                          double[] fwd, double[] right, double[] up,
                                          double radius, float alpha, double time) {
        for (int k = 0; k < 2; k++) {
            double cycle = ((time * 0.012D + k * 0.53D) % 1.0D);
            if (cycle > 0.09D) {
                continue;
            }
            double progress = cycle / 0.09D;
            double[] startDir = norm(new double[]{
                    Math.sin(k * 3.1D + 0.4D), 0.35D + k * 0.18D, 0.62D});
            double[] endDir = norm(add(startDir, new double[]{0.42D, -0.30D, 0.0D}));
            double[] p = add(eye, mul(lerp3(startDir, endDir, progress), radius));
            double[] q = add(eye, mul(lerp3(startDir, endDir, Math.max(0.0D, progress - 0.16D)), radius));
            float fade = (float) Math.sin(progress * Math.PI);
            line(pose, lines, q[0], q[1], q[2], p[0], p[1], p[2],
                    1.0F, 1.0F, 1.0F, alpha * fade * 0.85F, 0, 0, 1);
            line(pose, lines, q[0], q[1] + 0.5D * sceneScale, q[2], p[0], p[1], p[2],
                    CYAN_R, CYAN_G, CYAN_B, alpha * fade * 0.40F, 0, 0, 1);
        }
    }

    /** 实心圆环带（大气泛光用）：内径到外径之间整圈填色。 */
    private static void glowRing(VertexConsumer quads, Matrix4f matrix, double[] c,
                                 double[] right, double[] up,
                                 double inner, double outer,
                                 float r, float g, float b, float a) {
        int segments = 56;
        for (int i = 0; i < segments; i++) {
            double a1 = i * Math.PI * 2.0D / segments;
            double a2 = (i + 1) * Math.PI * 2.0D / segments;
            double c1 = Math.cos(a1);
            double s1 = Math.sin(a1);
            double c2 = Math.cos(a2);
            double s2 = Math.sin(a2);
            quad(quads, matrix,
                    c[0] + right[0] * c1 * inner + up[0] * s1 * inner,
                    c[1] + right[1] * c1 * inner + up[1] * s1 * inner,
                    c[2] + right[2] * c1 * inner + up[2] * s1 * inner,
                    c[0] + right[0] * c2 * inner + up[0] * s2 * inner,
                    c[1] + right[1] * c2 * inner + up[1] * s2 * inner,
                    c[2] + right[2] * c2 * inner + up[2] * s2 * inner,
                    c[0] + right[0] * c2 * outer + up[0] * s2 * outer,
                    c[1] + right[1] * c2 * outer + up[1] * s2 * outer,
                    c[2] + right[2] * c2 * outer + up[2] * s2 * outer,
                    c[0] + right[0] * c1 * outer + up[0] * s1 * outer,
                    c[1] + right[1] * c1 * outer + up[1] * s1 * outer,
                    c[2] + right[2] * c1 * outer + up[2] * s1 * outer,
                    r, g, b, a);
        }
    }

    /**
     * 不规则岩质天体：外轮廓按角度做噪声起伏，表面分面带明暗，上面压几个深色陨石坑。
     * 旋转由 {@code spin} 驱动（轮廓噪声与明暗一起转，看起来是整块石头在翻滚）。
     */
    private static void renderRock(PoseStack pose, VertexConsumer quads, VertexConsumer lines, Matrix4f matrix,
                                   double[] c, double[] right, double[] up,
                                   double radius, double spin, float alpha) {
        final int rings = 9;
        final int segs = 24;
        for (int ri = 0; ri < rings; ri++) {
            double f0 = (double) ri / rings;
            double f1 = (double) (ri + 1) / rings;
            for (int si = 0; si < segs; si++) {
                double a1 = Math.PI * 2.0D * si / segs;
                double a2 = Math.PI * 2.0D * (si + 1) / segs;
                double r1 = radius * noiseRadius(a1, spin);
                double r2 = radius * noiseRadius(a2, spin);
                // 明暗：光从左上来（参考图的高光在左上，右下是暗面）
                double midA = (a1 + a2) * 0.5D;
                double lit = Math.max(0.0D, Math.cos(midA - Math.PI * 0.78D));
                float shade = (float) (0.22D + 0.78D * lit) * (0.80F + 0.20F * (float) f0);
                float cr = 0.40F * shade;
                float cg = 0.37F * shade;
                float cb = 0.33F * shade;
                // 表面凹凸：按格给一点点色差
                double n = Math.sin(ri * 12.9898D + si * 78.233D + spin) * 43758.5453D;
                n -= Math.floor(n);
                float jitter = (float) n * 0.09F - 0.045F;
                planeQuad4(quads, matrix, c, right, up,
                        r1 * f0 * Math.cos(a1), r1 * f0 * Math.sin(a1),
                        r1 * f0 * Math.cos(a2), r1 * f0 * Math.sin(a2),
                        r2 * f1 * Math.cos(a2), r2 * f1 * Math.sin(a2),
                        r2 * f1 * Math.cos(a1), r2 * f1 * Math.sin(a1),
                        Math.max(0.02F, cr + jitter), Math.max(0.02F, cg + jitter), Math.max(0.02F, cb + jitter),
                        alpha);
            }
        }
        // 陨石坑：深色实心盘 + 亮边（位置固定在岩石坐标里，随旋转移动）
        double[][] craters = {{-0.35D, 0.35D, 0.28D}, {0.30D, 0.12D, 0.20D},
                {0.05D, -0.38D, 0.23D}, {-0.15D, 0.02D, 0.12D}};
        for (double[] ck : craters) {
            double ca = spin + 0.4D;
            double x = (ck[0] * Math.cos(ca) - ck[1] * Math.sin(ca)) * radius;
            double y = (ck[0] * Math.sin(ca) + ck[1] * Math.cos(ca)) * radius;
            double[] cc = add(c, add(mul(right, x), mul(up, y)));
            double crr = ck[2] * radius;
            solidDisc(quads, matrix, cc, right, up, crr, 0.13F, 0.12F, 0.11F, alpha * 0.85F);
            planeRing(pose, lines, cc, right, up, crr, 0.55F, 0.52F, 0.48F, alpha * 0.30F);
        }
    }

    /** 岩石外轮廓噪声：低频 + 高频两层，保证是「圆但不规则」的岩块。 */
    private static double noiseRadius(double a, double spin) {
        return 0.84D + 0.12D * Math.sin(3.0D * a + spin) + 0.06D * Math.sin(7.0D * a - spin * 1.7D);
    }

    /** 相机基里的方向：w 为三个权重（前 / 右 / 上），归一化后返回世界方向。 */
    private static double[] cameraDir(double[] fwd, double[] right, double[] up,
                                      double wFwd, double wRight, double wUp) {
        return norm(add(add(mul(fwd, wFwd), mul(right, wRight)), mul(up, wUp)));
    }

    /** 用实心四边形拼出的圆环（给星系柔光/星云亮结；不需要法线）。 */
    private static void planeRingDirect(VertexConsumer quads, Matrix4f matrix, double[] c,
                                        double[] right, double[] up, double radius,
                                        float r, float g, float b, float a) {
        int segments = 40;
        for (int i = 0; i < segments; i++) {
            double a1 = i * Math.PI * 2.0D / segments;
            double a2 = (i + 1) * Math.PI * 2.0D / segments;
            double r0 = Math.max(0.0D, radius - 0.55D * sceneScale);
            double c1 = Math.cos(a1);
            double s1 = Math.sin(a1);
            double c2 = Math.cos(a2);
            double s2 = Math.sin(a2);
            quad(quads, matrix,
                    c[0] + right[0] * c1 * r0 + up[0] * s1 * r0,
                    c[1] + right[1] * c1 * r0 + up[1] * s1 * r0,
                    c[2] + right[2] * c1 * r0 + up[2] * s1 * r0,
                    c[0] + right[0] * c2 * r0 + up[0] * s2 * r0,
                    c[1] + right[1] * c2 * r0 + up[1] * s2 * r0,
                    c[2] + right[2] * c2 * r0 + up[2] * s2 * r0,
                    c[0] + right[0] * c2 * radius + up[0] * s2 * radius,
                    c[1] + right[1] * c2 * radius + up[1] * s2 * radius,
                    c[2] + right[2] * c2 * radius + up[2] * s2 * radius,
                    c[0] + right[0] * c1 * radius + up[0] * s1 * radius,
                    c[1] + right[1] * c1 * radius + up[1] * s1 * radius,
                    c[2] + right[2] * c1 * radius + up[2] * s1 * radius,
                    r, g, b, a);
        }
    }

    /** 球面方向（以相机前/右/上为基）：theta 自前方起，phi 绕前方旋转。 */
    private static double[] sphereDir(double[] fwd, double[] right, double[] up,
                                      double theta, double phi) {
        double st = Math.sin(theta);
        double ct = Math.cos(theta);
        return new double[]{
                fwd[0] * ct + right[0] * st * Math.cos(phi) + up[0] * st * Math.sin(phi),
                fwd[1] * ct + right[1] * st * Math.cos(phi) + up[1] * st * Math.sin(phi),
                fwd[2] * ct + right[2] * st * Math.cos(phi) + up[2] * st * Math.sin(phi)};
    }

    private static double[] spherePoint(double[] eye, double[] fwd, double[] right, double[] up,
                                        double radius, double theta, double phi) {
        double[] dir = sphereDir(fwd, right, up, theta, phi);
        return new double[]{eye[0] + dir[0] * radius, eye[1] + dir[1] * radius, eye[2] + dir[2] * radius};
    }

    /** 均匀球面随机方向。 */
    private static double[] randomDirection(RandomSource random) {
        double theta = random.nextDouble() * Math.PI * 2.0D;
        double cosPhi = random.nextDouble() * 2.0D - 1.0D;
        double sinPhi = Math.sqrt(Math.max(0.0D, 1.0D - cosPhi * cosPhi));
        return new double[]{Math.cos(theta) * sinPhi, cosPhi, Math.sin(theta) * sinPhi};
    }

    // ------------------------------------------------------------------ 地球

    /**
     * 写实向的原创地球：昼夜线、海洋/大陆/冰盖分色、云带、夜面城市灯光、大气外晕。
     * 全部程序化（大陆位置由固定种子生成），不依赖任何外部贴图。
     */
    private static void renderEarth(PoseStack pose, VertexConsumer lines, VertexConsumer quads,
                                    Matrix4f matrix, double[] c, double[] fwd,
                                    double[] right, double[] up,
                                    double radius, float alpha, double time) {
        final int rings = 30;
        final int segs = 48;
        // 云、灯、晨昏线都比球面更靠近镜头一点：同一深度写两次会 z-fighting。
        double[] surface = add(c, mul(fwd, -0.30D));
        // 太阳方向极缓慢漂移：晨昏线在几秒里挪一点点，球面才有「在转」的错觉。
        double sun = SUN_ANGLE + Math.sin(time * 0.012D) * 0.025D;
        double cloudSpin = time * 0.0018D;
        // 大陆种子（归一化圆盘坐标）
        RandomSource seed = RandomSource.create(0x45415254484CL);
        double[] sx = new double[9];
        double[] sy = new double[9];
        double[] sr = new double[9];
        for (int i = 0; i < 9; i++) {
            sx[i] = (seed.nextDouble() * 2.0D - 1.0D) * 0.74D;
            sy[i] = (seed.nextDouble() * 2.0D - 1.0D) * 0.74D;
            sr[i] = 0.17D + seed.nextDouble() * 0.20D;
        }

        for (int ri = 0; ri < rings; ri++) {
            double r0 = radius * ri / rings;
            double r1 = radius * (ri + 1) / rings;
            double midR = (ri + 0.5D) / rings;
            for (int si = 0; si < segs; si++) {
                double a1 = Math.PI * 2.0D * si / segs;
                double a2 = Math.PI * 2.0D * (si + 1) / segs;
                double midA = (a1 + a2) * 0.5D;
                double nx = Math.cos(midA) * midR;
                double ny = Math.sin(midA) * midR;
                boolean land = false;
                for (int k = 0; k < 9 && !land; k++) {
                    double dx = nx - sx[k];
                    double dy = ny - sy[k];
                    land = dx * dx + dy * dy < sr[k] * sr[k];
                }
                boolean ice = Math.abs(ny) > 0.83D + 0.035D * Math.sin(midA * 4.0D);
                double litRaw = 0.5D + 0.5D * Math.cos(midA - sun);
                // 晨昏线不要一条硬边：0.15~0.35 之间过渡
                double day = smooth01((litRaw - 0.18D) / 0.30D);

                float dr;
                float dg;
                float db;
                float nr;
                float ng;
                float nb;
                if (ice) {
                    dr = 0.86F;
                    dg = 0.93F;
                    db = 1.00F;
                    nr = 0.05F;
                    ng = 0.09F;
                    nb = 0.15F;
                } else if (land) {
                    dr = 0.14F;
                    dg = 0.38F;
                    db = 0.19F;
                    nr = 0.010F;
                    ng = 0.042F;
                    nb = 0.026F;
                } else {
                    dr = 0.035F;
                    dg = 0.21F;
                    db = 0.47F;
                    nr = 0.003F;
                    ng = 0.011F;
                    nb = 0.032F;
                }
                float cr = (float) Mth.lerp(day, nr, dr);
                float cg = (float) Mth.lerp(day, ng, dg);
                float cb = (float) Mth.lerp(day, nb, db);
                // 海面镜面高光：太阳一侧的窄亮斑（参考图里那块发白的海面反光）
                if (!ice && !land) {
                    double sd = Math.max(0.0D, Math.cos(midA - sun - 0.28D));
                    float spec = (float) Math.pow(sd, 22.0D) * 0.55F * (float) day;
                    cr = Math.min(1.0F, cr + spec);
                    cg = Math.min(1.0F, cg + spec);
                    cb = Math.min(1.0F, cb + spec);
                }
                planeQuad4(quads, matrix, c, right, up,
                        r0 * Math.cos(a1), r0 * Math.sin(a1),
                        r0 * Math.cos(a2), r0 * Math.sin(a2),
                        r1 * Math.cos(a2), r1 * Math.sin(a2),
                        r1 * Math.cos(a1), r1 * Math.sin(a1),
                        cr, cg, cb, alpha * 0.94F);

                // 夜面城市灯光：只在大陆的夜半球、且稀疏
                if (land && day < 0.22D && ((ri * 31 + si * 17) % 23 == 0)) {
                    double px = Math.cos(midA) * radius * midR;
                    double py = Math.sin(midA) * radius * midR;
                    // 城市灯光按各自相位闪烁（窗口里看着像活的）
                    float twinkle = 0.45F + 0.55F * (0.5F + 0.5F * (float) Math.sin(
                            time * 0.22D + (ri * 7 + si) * 1.7D));
                    planeQuad(quads, matrix, surface, right, up,
                            px - 0.22D, py - 0.22D, px + 0.22D, py + 0.22D,
                            1.0F, 0.86F, 0.55F, alpha * (float) (0.62D * (1.0D - day)) * twinkle);
                }
            }
        }

        // 云带：几条贯穿圆盘的白色薄带（略带波动，避免像直尺画出来的）
        RandomSource cloudSeed = RandomSource.create(0x434C4F554453L);
        for (int band = 0; band < 10; band++) {
            double y = (cloudSeed.nextDouble() * 2.0D - 1.0D) * 0.80D;
            double thickness = 0.035D + cloudSeed.nextDouble() * 0.045D;
            double wobble = cloudSeed.nextDouble() * Math.PI * 2.0D;
            double half = Math.sqrt(Math.max(0.0D, 1.0D - y * y)) * 0.96D;
            int steps = 22;
            double cs = Math.cos(cloudSpin);
            double sn = Math.sin(cloudSpin);
            for (int s = 0; s < steps; s++) {
                double x0 = -half + 2.0D * half * s / steps;
                double x1 = -half + 2.0D * half * (s + 1) / steps;
                double yy = y + Math.sin(x0 * 3.0D + wobble) * 0.018D
                        + Math.sin(x0 * 7.0D + wobble * 1.7D) * 0.010D;
                if (x0 * x0 + y * y >= 0.985D) {
                    continue;
                }
                // 整层云绕球心缓慢旋转：四角各自转，读起来是「云在飘」。
                double ax0 = x0 * radius;
                double ay0 = yy * radius;
                double ax1 = x1 * radius;
                double ay1 = (yy + thickness) * radius;
                planeQuad4(quads, matrix, surface, right, up,
                        ax0 * cs - ay0 * sn, ax0 * sn + ay0 * cs,
                        ax1 * cs - ay0 * sn, ax1 * sn + ay0 * cs,
                        ax1 * cs - ay1 * sn, ax1 * sn + ay1 * cs,
                        ax0 * cs - ay1 * sn, ax0 * sn + ay1 * cs,
                        1.0F, 1.0F, 1.0F, alpha * (0.07F + 0.05F * (float) cloudSeed.nextDouble()));
            }
        }

        // 大气层：三圈外晕，越外越淡（写实照片里那层薄蓝边）
        float breath = 0.85F + 0.15F * (0.5F + 0.5F * (float) Math.sin(time * 0.07D));
        // 大气不是一条线，而是一圈从亮到淡的蓝色泛光（参考图最显眼的特征）
        glowRing(quads, matrix, c, right, up, radius * 1.005D, radius * 1.030D,
                0.42F, 0.76F, 1.0F, alpha * 0.30F * breath);
        glowRing(quads, matrix, c, right, up, radius * 1.030D, radius * 1.060D,
                0.32F, 0.62F, 0.98F, alpha * 0.16F * breath);
        glowRing(quads, matrix, c, right, up, radius * 1.060D, radius * 1.105D,
                0.24F, 0.48F, 0.92F, alpha * 0.075F * breath);
        planeRing(pose, lines, c, right, up, radius * 1.006D,
                0.55F, 0.82F, 1.0F, alpha * 0.55F * breath);
        // 昼夜线：一条很淡的终止符弧（帮助读出球面）
        int term = 20;
        double tr = radius * 1.004D;
        for (int i = 0; i < term; i++) {
            double a1 = sun + Math.PI * 0.5D + Math.PI * i / term;
            double a2 = sun + Math.PI * 0.5D + Math.PI * (i + 1) / term;
            line(pose, lines,
                    surface[0] + right[0] * Math.cos(a1) * tr + up[0] * Math.sin(a1) * tr,
                    surface[1] + right[1] * Math.cos(a1) * tr + up[1] * Math.sin(a1) * tr,
                    surface[2] + right[2] * Math.cos(a1) * tr + up[2] * Math.sin(a1) * tr,
                    surface[0] + right[0] * Math.cos(a2) * tr + up[0] * Math.sin(a2) * tr,
                    surface[1] + right[1] * Math.cos(a2) * tr + up[1] * Math.sin(a2) * tr,
                    surface[2] + right[2] * Math.cos(a2) * tr + up[2] * Math.sin(a2) * tr,
                    0.55F, 0.72F, 0.90F, alpha * 0.10F, 0, 0, 1);
        }
    }

    // ------------------------------------------------------------------ 轨道炮

    /** 轨道炮：桁架炮台 + 一根指向地球的炮管，动能弹沿炮管方向命中地球晨昏线附近。 */
    private static void renderCannon(PoseStack pose, VertexConsumer lines, VertexConsumer quads,
                                     Matrix4f matrix, double[] eye, double[] fwd,
                                     double[] right, double[] up, double[] earth, double earthR,
                                     float alpha, double time, double phase) {
        double[] stationBase = offset(eye, fwd, right, up, 52.0D, 30.0D, 22.0D);
        double[] dir = norm(sub(earth, stationBase));
        // 开火后坐：炮台沿炮管反方向退 1.6 格，8 tick 内回位。
        double recoil = phase >= 0.999F
                ? Math.max(0.0D, 1.0D - OrbitalStrikeClientState.impactAge() / 8.0D) * 1.6D * sceneScale
                : 0.0D;
        double[] station = add(stationBase, mul(dir, -recoil));
        renderDreadnought(pose, quads, lines, station, right, up, fwd, 1.15D * sceneScale, alpha, time);

        double[] muzzle = add(station, mul(dir, 9.0D));
        // 炮管：三条平行线（近似厚度）
        for (double k : new double[]{-0.55D, 0.0D, 0.55D}) {
            double[] offRight = mul(right, k);
            double[] a = add(station, offRight);
            double[] b = add(muzzle, offRight);
            line(pose, lines, a[0], a[1], a[2], b[0], b[1], b[2],
                    0.68F, 0.88F, 1.0F, alpha * 0.62F, 0, 0, 1);
        }
        // 炮口制退器：实心环座（线框炮管上的一个实体段落）
        double[] brake = sub(muzzle, mul(dir, 1.6D * sceneScale));
        solidBox(quads, matrix, brake, right, up, fwd,
                1.4D * sceneScale, 1.4D * sceneScale, 1.6D * sceneScale,
                0.44F, 0.50F, 0.56F, alpha);
        planeRing(pose, lines, muzzle, right, up, 2.9D, 1.0F, 0.62F, 0.22F, alpha * 0.55F);
        planeRing(pose, lines, brake, right, up, 2.2D, 1.0F, 0.82F, 0.45F, alpha * 0.30F);
        float charge = Mth.clamp((float) OrbitalStrikeClientState.lockProgress(), 0.0F, 1.0F);
        if (phase < 0.999D) {
            planeRing(pose, lines, muzzle, right, up, 3.8D - 1.4D * charge,
                    1.0F, 0.55F, 0.18F, alpha * (0.18F + 0.38F * charge));
        }

        double[] contact = sub(earth, mul(dir, earthR * 0.94D));
        double[] slug = lerp3(muzzle, contact, smooth01(phase));
        if (phase > 0.01D) {
            // 弹体 + 尾焰
            dot3(pose, lines, slug, 0.65D, 1.0F, 0.92F, 0.75F, alpha * 0.98F);
            // 橙白高热弹芯：一条粗光束从炮口连到弹体（参考图里的橙色能量束）
            line(pose, lines, muzzle[0], muzzle[1], muzzle[2], slug[0], slug[1], slug[2],
                    1.0F, 0.58F, 0.18F, alpha * 0.75F * (float) phase, 0, 0, 1);
            line(pose, lines,
                    muzzle[0] - right[0] * 0.5D, muzzle[1] - right[1] * 0.5D, muzzle[2] - right[2] * 0.5D,
                    slug[0] - right[0] * 0.5D, slug[1] - right[1] * 0.5D, slug[2] - right[2] * 0.5D,
                    1.0F, 0.86F, 0.55F, alpha * 0.55F * (float) phase, 0, 0, 1);
            for (int i = 1; i <= 9; i++) {
                double[] t = sub(slug, mul(dir, i * 2.4D));
                double rr = Math.max(0.10D, 1.0D - i * 0.10D);
                planeRing(pose, lines, t, right, up, rr, 1.0F, 0.58F, 0.20F,
                        alpha * (0.55F - i * 0.05F) * (float) phase);
            }
            double[] tail = sub(slug, mul(dir, 26.0D));
            line(pose, lines, slug[0], slug[1], slug[2], tail[0], tail[1], tail[2],
                    1.0F, 0.86F, 0.62F, alpha * 0.55F * (float) phase, 0, 0, 1);
            // 马赫环：弹体尾流里一串交替大小的亮环（高速尾焰的经典特征）
            for (int d = 1; d <= 5; d++) {
                double[] p = sub(slug, mul(dir, d * 3.4D));
                double rr = d % 2 == 0 ? 0.85D : 0.55D;
                planeRing(pose, lines, p, right, up, rr,
                        1.0F, 0.70F, 0.32F, alpha * 0.50F * (float) phase * (1.0F - d * 0.15F));
            }
        }
        if (phase >= 0.999F) {
            muzzleFlash(pose, lines, muzzle, right, up, alpha, time);
            earthImpact(pose, lines, contact, right, up, alpha, OrbitalStrikeClientState.impactAge());
        }
        if (phase >= 0.999D) {
            // 命中：地球晨昏线附近的白闪 + 扩散环
            double pulse = 0.6D + 0.4D * Math.sin(time * 0.55D);
            planeRing(pose, lines, contact, right, up, 2.0D + 1.4D * pulse,
                    1.0F, 1.0F, 1.0F, alpha * 0.80F);
            planeRing(pose, lines, contact, right, up, 5.0D + 3.0D * pulse,
                    CYAN_R, CYAN_G, CYAN_B, alpha * 0.30F);
        }
    }

    // ------------------------------------------------------------------ 长矛

    /** 天基长矛：细长的轨道矛台，锁定时收束成一针，命中时整根光矛扎进地球。 */
    private static void renderLance(PoseStack pose, VertexConsumer lines, VertexConsumer quads,
                                    Matrix4f matrix,
                                    double[] eye, double[] fwd, double[] right, double[] up,
                                    double[] earth, double earthR, float alpha, double time,
                                    double phase) {
        double[] stationBase = offset(eye, fwd, right, up, 46.0D, 25.0D, 24.0D);
        double[] dir = norm(sub(earth, stationBase));
        double recoil = phase >= 0.999F
                ? Math.max(0.0D, 1.0D - OrbitalStrikeClientState.impactAge() / 10.0D) * 1.2D * sceneScale
                : 0.0D;
        double[] station = add(stationBase, mul(dir, -recoil));
        renderStation(pose, quads, lines, station, right, up, fwd, 0.85D * sceneScale, alpha, time);
        double[] contact = sub(earth, mul(dir, earthR * 0.94D));
        double[] tip = lerp3(station, contact, smooth01(phase));
        double reach = len(sub(tip, station));
        // 矛身：三条收束的线 + 沿线能量环
        for (double k : new double[]{-0.75D, 0.0D, 0.75D}) {
            double[] offRight = mul(right, k * (1.0D - 0.55D * phase));
            line(pose, lines,
                    station[0] + offRight[0], station[1] + offRight[1], station[2] + offRight[2],
                    tip[0] + offRight[0] * 0.25D, tip[1] + offRight[1] * 0.25D, tip[2] + offRight[2] * 0.25D,
                    1.0F, 1.0F, 1.0F, alpha * (0.35F + 0.55F * (float) phase), 0, 0, 1);
        }
        for (int i = 1; i <= 5; i++) {
            double[] p = lerp3(station, tip, i / 6.0D);
            planeRing(pose, lines, p, right, up, 1.1D - i * 0.12D,
                    CYAN_R, CYAN_G, CYAN_B, alpha * (0.25F + 0.45F * (float) phase));
        }
        dot3(pose, lines, tip, 1.4D, 1.0F, 1.0F, 1.0F, alpha * 0.9F);
        if (reach > 1.0D && phase > 0.98D) {
            muzzleFlash(pose, lines, station, right, up, alpha, time);
            earthImpact(pose, lines, contact, right, up, alpha, OrbitalStrikeClientState.impactAge());
        }
    }

    // ------------------------------------------------------------------ 奇点

    /** 引力奇点：球心全黑、吸积盘倾斜旋转、物质向内旋落；命中时向地球方向释放冲击环。 */
    private static void renderSingularity(PoseStack pose, VertexConsumer lines, VertexConsumer quads,
                                          Matrix4f matrix, double[] eye, double[] fwd,
                                          double[] right, double[] up, double[] earth, double earthR,
                                          float alpha, double time, double phase) {
        double[] core = offset(eye, fwd, right, up, 72.0D, 6.0D, 9.0D);
        double coreR = 3.6D - 1.1D * phase;
        // 黑核：用环带拼一个纯黑圆盘，边缘一圈冷光
        int rings = 10;
        for (int i = 0; i < rings; i++) {
            double r0 = coreR * i / rings;
            double r1 = coreR * (i + 1) / rings;
            for (int s = 0; s < 20; s++) {
                double a1 = Math.PI * 2.0D * s / 20.0D;
                double a2 = Math.PI * 2.0D * (s + 1) / 20.0D;
                planeQuad4(quads, matrix, core, right, up,
                        r0 * Math.cos(a1), r0 * Math.sin(a1),
                        r0 * Math.cos(a2), r0 * Math.sin(a2),
                        r1 * Math.cos(a2), r1 * Math.sin(a2),
                        r1 * Math.cos(a1), r1 * Math.sin(a1),
                        0.004F, 0.006F, 0.012F, alpha * 0.98F);
            }
        }
        planeRing(pose, lines, core, right, up, coreR * 1.03D, 0.72F, 0.92F, 1.0F, alpha * 0.85F);
        // 爱因斯坦环：紧贴视界的一圈细亮环 + 外层暗环（引力透镜的读法）
        planeRing(pose, lines, core, right, up, coreR * 1.14D, 1.0F, 1.0F, 1.0F, alpha * 0.45F);
        planeRing(pose, lines, core, right, up, coreR * 1.75D,
                0.66F, 0.86F, 1.0F, alpha * 0.16F);
        // 吸积盘：三条椭圆，时间驱动的倾角
        for (int i = 0; i < 3; i++) {
            double rx = (11.0D - i * 1.6D) * (1.0D - 0.35D * phase);
            double ry = rx * (0.20D + 0.05D * i);
            planeEllipse(pose, lines, core, right, up, rx, ry,
                    time * 0.05D + i * 1.05D, CYAN_R, CYAN_G, CYAN_B,
                    alpha * (0.55F - i * 0.12F));
        }
        // 旋落物质：每条从外圈螺旋向内，相位随 time 流动
        for (int i = 0; i < 26; i++) {
            double a0 = i * 2.39996D + time * 0.03D;
            double rOuter = 8.5D + (i % 5) * 0.9D;
            double prevX = 0.0D;
            double prevY = 0.0D;
            boolean first = true;
            for (int k = 0; k <= 8; k++) {
                double t = k / 8.0D;
                double rr = rOuter * (1.0D - t * 0.86D);
                double aa = a0 + t * 2.4D;
                double x = Math.cos(aa) * rr;
                double y = Math.sin(aa) * rr * 0.55D;
                if (!first) {
                    line(pose, lines,
                            core[0] + right[0] * prevX + up[0] * prevY,
                            core[1] + right[1] * prevX + up[1] * prevY,
                            core[2] + right[2] * prevX + up[2] * prevY,
                            core[0] + right[0] * x + up[0] * y,
                            core[1] + right[1] * x + up[1] * y,
                            core[2] + right[2] * x + up[2] * y,
                            0.70F, 0.92F, 1.0F, alpha * 0.28F, 0, 0, 1);
                }
                prevX = x;
                prevY = y;
                first = false;
            }
        }
        if (phase >= 0.999D) {
            double[] dir = norm(sub(earth, core));
            double[] contact = sub(earth, mul(dir, earthR * 0.92D));
            muzzleFlash(pose, lines, core, right, up, alpha, time);
            earthImpact(pose, lines, contact, right, up, alpha, OrbitalStrikeClientState.impactAge());
        }
    }

    // ------------------------------------------------------------------ 等离子风暴

    /** 等离子风暴：五枚轨道投放舱，逐 8 tick 向地球不同位置打下一道锯齿闪电。 */
    private static void renderStorm(PoseStack pose, VertexConsumer lines, VertexConsumer quads,
                                    Matrix4f matrix, double[] eye, double[] fwd,
                                    double[] right, double[] up, double[] earth, double earthR,
                                    float alpha, double time) {
        long elapsed = OrbitalStrikeClientState.elapsed();
        int impactTick = OrbitalStrikeClientState.lockTicks() + OrbitalStrikeClientState.fallTicks();
        int stagger = OrbitalStrikeMode.STORM_STAGGER_TICKS;
        for (int i = 0; i < OrbitalStrikeMode.STORM_POINTS; i++) {
            double[] pod = offset(eye, fwd, right, up, 44.0D + i * 2.4D,
                    20.0D + i * 2.6D, 17.0D + (i % 2) * 5.0D);
            renderPod(pose, quads, lines, pod, right, up, fwd, alpha, time, i);
            double angle = i * (Math.PI * 2.0D / OrbitalStrikeMode.STORM_POINTS) + 0.35D;
            // earthR 已经是缩放后的世界单位，这里直接加，不能再走 offset（会二次缩放）。
            double[] contact = add(earth, add(mul(fwd, -0.6D),
                    add(mul(right, Math.cos(angle) * earthR * 0.62D),
                            mul(up, Math.sin(angle) * earthR * 0.62D))));
            double fireAt = impactTick + i * (double) stagger;
            double chargeAt = fireAt - 9.0D;
            if (elapsed >= chargeAt && elapsed < fireAt) {
                double p = Mth.clamp((elapsed - chargeAt) / 9.0D, 0.0D, 1.0D);
                planeRing(pose, lines, pod, right, up, 3.4D - 1.6D * p,
                        1.0F, 1.0F, 1.0F, alpha * (0.20F + 0.45F * (float) p));
            }
            if (elapsed >= fireAt) {
                double age = elapsed - fireAt;
                float life = Mth.clamp(1.0F - (float) age / 14.0F, 0.0F, 1.0F);
                if (life > 0.01F) {
                    jaggedBolt(pose, lines, pod, contact, right, up, yawJitter(i, time), alpha * life);
                    // 两条分叉：从主闪电中段甩出去（等离子放电的经典形态）
                    double[] mid = lerp3(pod, contact, 0.52D);
                    for (int b = 0; b < 2; b++) {
                        double side = b == 0 ? -1.0D : 1.0D;
                        double[] branchEnd = add(mid, add(
                                mul(right, side * (3.0D + 1.2D * Math.sin(time * 0.7D + i)) * sceneScale),
                                mul(up, (2.0D + 1.0D * Math.cos(time * 0.9D + b)) * sceneScale)));
                        jaggedBolt(pose, lines, mid, branchEnd, right, up,
                                yawJitter(i * 3 + b, time), alpha * life * 0.50F);
                    }
                    earthImpact(pose, lines, contact, right, up, alpha, (long) age);
                }
            }
        }
    }

    /** 一枚投放舱：实心金色舱体 + 两片深蓝太阳能板 + 朝向地球的发射口。 */
    private static void renderPod(PoseStack pose, VertexConsumer quads, VertexConsumer lines,
                                  double[] pod, double[] right, double[] up, double[] fwd,
                                  float alpha, double time, int index) {
        double s = 0.75D * sceneScale;
        solidBox(quads, matrixOf(pose), pod, right, up, fwd,
                1.1D * s, 0.9D * s, 1.1D * s, 0.60F, 0.52F, 0.36F, alpha);
        solidBox(quads, matrixOf(pose), add(pod, mul(up, 0.95D * s)), right, up, fwd,
                0.8D * s, 0.12D * s, 0.8D * s, 0.72F, 0.76F, 0.80F, alpha);
        for (int side = -1; side <= 1; side += 2) {
            double[] arm = add(pod, mul(right, side * 2.3D * s));
            solidBox(quads, matrixOf(pose), arm, right, up, fwd,
                    1.2D * s, 0.09D * s, 0.75D * s, 0.08F, 0.14F, 0.30F, alpha);
        }
        double[] mouth = add(pod, mul(up, -1.2D * s));
        planeRing(pose, lines, mouth, right, up, 0.55D * s,
                1.0F, 1.0F, 1.0F, alpha * 0.65F);
        float blink = 0.35F + 0.65F * (0.5F + 0.5F * (float) Math.sin(time * 0.18D + index * 1.3D));
        planeRing(pose, lines, add(pod, mul(up, 1.1D * s)), right, up, 0.30D * s,
                1.0F, 1.0F, 1.0F, alpha * blink);
    }

    /** 从 PoseStack 取当前矩阵（solidBox 的便捷入口）。 */
    private static Matrix4f matrixOf(PoseStack pose) {
        return pose.last().pose();
    }

    /** 锯齿闪电：两端固定、中间按正弦抖动的折线（每帧重抖 = 噼啪感）。 */
    private static void jaggedBolt(PoseStack pose, VertexConsumer lines, double[] from, double[] to,
                                   double[] right, double[] up, double seed, float alpha) {
        final int segments = 9;
        double[] prev = from;
        for (int i = 1; i <= segments; i++) {
            double t = i / (double) segments;
            double[] p = lerp3(from, to, t);
            if (i < segments) {
                double amp = 2.6D * Math.sin(Math.PI * t) * (0.45D + 0.55D * Math.sin(seed + i * 2.7D));
                p = add(p, add(mul(right, amp), mul(up, amp * 0.55D * Math.cos(seed * 1.3D + i * 1.9D))));
            }
            line(pose, lines, prev[0], prev[1], prev[2], p[0], p[1], p[2],
                    0.92F, 0.99F, 1.0F, alpha * 0.90F, 0, 0, 1);
            prev = p;
        }
    }

    // ------------------------------------------------------------------ 行星陨落

    /** 行星陨落：一颗岩质陨石从画面上方切入，拖火尾砸进地球（服务器落点在地球下方）。 */
    private static void renderMeteor(PoseStack pose, VertexConsumer lines, VertexConsumer quads,
                                     Matrix4f matrix, double[] eye, double[] fwd,
                                     double[] right, double[] up, double[] earth, double earthR,
                                     float alpha, double time) {
        double fall = Mth.clamp((float) ((OrbitalStrikeClientState.elapsed()
                - OrbitalStrikeClientState.lockTicks())
                / Math.max(1, OrbitalStrikeClientState.fallTicks())), 0.0F, 1.0F);
        double[] start = offset(eye, fwd, right, up, 150.0D, 62.0D, 52.0D);
        double[] dir = norm(sub(earth, start));
        double[] contact = sub(earth, mul(dir, earthR * 0.92D));
        double t = smooth01(fall);
        double[] pos = lerp3(start, contact, t);
        // 岩质本体：不规则多面体 + 陨石坑，缓慢翻滚（按参考图的灰色石质小行星）
        double r = 5.2D * sceneScale;
        renderRock(pose, quads, lines, matrix, pos, right, up, r, time * 0.30D, alpha);
        // 尾焰：一串向后的火环 + 一条火线，越靠近地球越亮
        double heat = 0.55D + 0.45D * t;
        for (int i = 1; i <= 11; i++) {
            double[] tail = sub(pos, mul(dir, i * (r * 1.7D)));
            double rr = Math.max(0.4D, r * (1.35D - i * 0.09D));
            float a = alpha * (float) (0.55D - i * 0.04D) * (float) heat;
            planeRing(pose, lines, tail, right, up, rr, 1.0F, 0.58F, 0.30F, a);
        }
        double[] trailEnd = sub(pos, mul(dir, 58.0D * heat * sceneScale));
        line(pose, lines, pos[0], pos[1], pos[2],
                trailEnd[0], trailEnd[1], trailEnd[2], 1.0F, 0.70F, 0.42F, alpha * 0.7F, 0, 0, 1);
        if (fall >= 0.999F) {
            long age = OrbitalStrikeClientState.impactAge();
            earthImpact(pose, lines, contact, right, up, alpha, age);
            // 碎裂：岩块炸成几片，沿撞击点向外飞散
            if (age >= 0 && age < 26) {
                float fade = 1.0F - age / 26.0F;
                for (int i = 0; i < 6; i++) {
                    double ang = i * Math.PI * 2.0D / 6.0D + 0.4D;
                    double dist = (2.5D + age * 0.9D) * sceneScale;
                    double[] frag = add(contact, add(mul(right, Math.cos(ang) * dist),
                            mul(up, Math.sin(ang) * dist)));
                    double size = (0.8D - age * 0.022D) * sceneScale;
                    if (size <= 0.05D) {
                        continue;
                    }
                    camBox(pose, lines, frag, right, up, fwd, size, size * 0.8D, size,
                            0.62F, 0.34F, 0.22F, alpha * fade * 0.85F);
                }
            }
        }
    }

    // ------------------------------------------------------------------ 宇宙激光

    /** 宇宙激光：轨道卫星把束流打进地球；接触点白闪 + 贯穿方向的双层扩散环。 */
    private static void renderSatelliteBeam(PoseStack pose, VertexConsumer lines, VertexConsumer quads,
                                            Matrix4f matrix, double[] eye, double[] fwd,
                                            double[] right, double[] up, double[] earth, double earthR,
                                            float alpha, double time, double phase) {
        double[] station = offset(eye, fwd, right, up, 54.0D, 28.0D, 19.0D);
        renderStation(pose, quads, lines, station, right, up, fwd, 1.0D * sceneScale, alpha, time);
        double[] dir = norm(sub(earth, station));
        double[] muzzle = add(station, mul(dir, 8.0D));
        double[] contact = sub(earth, mul(dir, earthR * 0.92D));
        planeRing(pose, lines, muzzle, right, up, 2.4D, CYAN_R, CYAN_G, CYAN_B, alpha * 0.45F);

        if (phase > 0.01D) {
            float p = (float) phase;
            float flicker = 0.88F + 0.12F * (0.5F + 0.5F * (float) Math.sin(time * 2.4D));
            for (double k : new double[]{-0.45D, 0.0D, 0.45D}) {
                double[] off = mul(right, k);
                line(pose, lines,
                        muzzle[0] + off[0], muzzle[1] + off[1], muzzle[2] + off[2],
                        contact[0] + off[0], contact[1] + off[1], contact[2] + off[2],
                        1.0F, 1.0F, 1.0F, alpha * (k == 0.0D ? 0.95F : 0.35F) * p * flicker, 0, 0, 1);
            }
            earthImpact(pose, lines, contact, right, up, alpha, OrbitalStrikeClientState.impactAge());
            planeRing(pose, lines, contact, right, up, 1.6D + 1.8D * p,
                    1.0F, 1.0F, 1.0F, alpha * 0.80F * p);
            planeRing(pose, lines, contact, right, up, 4.0D + 4.0D * p,
                    CYAN_R, CYAN_G, CYAN_B, alpha * 0.30F * p);
            planeRing(pose, lines, muzzle, right, up, 2.6D + 0.3D * Math.sin(time * 0.5D),
                    1.0F, 1.0F, 1.0F, alpha * 0.70F * p);
        }
    }

    // ------------------------------------------------------------------ 轨道站

    /**
     * 实体卫星（按参考图重做）：金色隔热膜舱体 + 朝镜头的大白色抛物面天线 +
     * 两侧各三片深蓝太阳能翼（金色边框、电池片网格）+ 顶部仪器 + 底部推进器。
     *
     * <p>参考图里的比例：天线几乎和舱体一样大、太阳翼展开宽度约舱体的 6 倍、
     * 舱体表面是起皱的金色隔热膜。这里用实心方体拼出这些体块，网格与灯走线。</p>
     */
    private static void renderStation(PoseStack pose, VertexConsumer quads, VertexConsumer lines,
                                      double[] center, double[] right, double[] up, double[] fwd,
                                      double scale, float alpha, double time) {
        double s = scale;
        // —— 金色隔热膜舱体
        solidBox(quads, matrixOf(pose), center, right, up, fwd,
                1.45D * s, 1.55D * s, 1.15D * s, 0.66F, 0.54F, 0.26F, alpha);
        // 朝镜头的白色仪器面板
        solidBox(quads, matrixOf(pose), add(center, mul(fwd, -1.20D * s)), right, up, fwd,
                1.05D * s, 1.15D * s, 0.10D * s, 0.82F, 0.84F, 0.86F, alpha);
        // 顶部仪器：三个圆柱状组件（小方体 + 顶盖）
        for (int i = -1; i <= 1; i++) {
            double[] inst = add(center, add(mul(up, 1.85D * s), mul(right, i * 0.55D * s)));
            solidBox(quads, matrixOf(pose), inst, right, up, fwd,
                    0.26D * s, 0.36D * s, 0.26D * s, 0.62F, 0.64F, 0.66F, alpha);
            solidBox(quads, matrixOf(pose), add(inst, mul(up, 0.40D * s)), right, up, fwd,
                    0.30D * s, 0.05D * s, 0.30D * s, 0.76F, 0.78F, 0.80F, alpha);
        }
        // 底部推进器：两个黑喷口 + 橙色余晖
        for (int side = -1; side <= 1; side += 2) {
            double[] nozzle = add(center, add(mul(up, -1.95D * s), mul(right, side * 0.65D * s)));
            solidBox(quads, matrixOf(pose), nozzle, right, up, fwd,
                    0.30D * s, 0.38D * s, 0.30D * s, 0.12F, 0.13F, 0.15F, alpha);
            planeRing(pose, lines, add(nozzle, mul(up, -0.42D * s)), right, up, 0.22D * s,
                    1.0F, 0.60F, 0.20F, alpha * 0.55F);
        }
        // —— 两侧太阳能翼：每侧三片，向外展开
        for (int side = -1; side <= 1; side += 2) {
            double[] arm = add(center, mul(right, side * 3.10D * s));
            solidBox(quads, matrixOf(pose), arm, right, up, fwd,
                    1.55D * s, 0.12D * s, 0.24D * s, 0.55F, 0.48F, 0.28F, alpha);
            for (int k = 0; k < 3; k++) {
                double[] panel = add(center, mul(right, side * (4.85D + k * 2.95D) * s));
                // 金色边框
                solidBox(quads, matrixOf(pose), panel, right, up, fwd,
                        1.42D * s, 0.075D * s, 2.12D * s, 0.58F, 0.45F, 0.18F, alpha);
                // 深蓝电池片
                solidBox(quads, matrixOf(pose), panel, right, up, fwd,
                        1.28D * s, 0.105D * s, 1.98D * s, 0.045F, 0.085F, 0.22F, alpha);
                // 电池片网格（贴着翼面）
                double[] gridBase = add(panel, mul(up, 0.115D * s));
                for (int g = -1; g <= 1; g++) {
                    double off = g * 0.62D * s;
                    double[] a = add(gridBase, mul(right, off));
                    line(pose, lines,
                            a[0] - fwd[0] * 1.92D * s, a[1] - fwd[1] * 1.92D * s, a[2] - fwd[2] * 1.92D * s,
                            a[0] + fwd[0] * 1.92D * s, a[1] + fwd[1] * 1.92D * s, a[2] + fwd[2] * 1.92D * s,
                            0.36F, 0.55F, 0.80F, alpha * 0.60F, 0, 0, 1);
                }
                for (int g = -1; g <= 1; g++) {
                    double off = g * 0.88D * s;
                    double[] a = add(gridBase, mul(fwd, off));
                    line(pose, lines,
                            a[0] - right[0] * 1.22D * s, a[1] - right[1] * 1.22D * s, a[2] - right[2] * 1.22D * s,
                            a[0] + right[0] * 1.22D * s, a[1] + right[1] * 1.22D * s, a[2] + right[2] * 1.22D * s,
                            0.36F, 0.55F, 0.80F, alpha * 0.45F, 0, 0, 1);
                }
            }
        }
        // —— 大抛物面天线：朝镜头，几乎与舱体同高
        double[] dish = add(center, add(mul(right, 2.55D * s), mul(fwd, 0.10D * s)));
        solidDisc(quads, matrixOf(pose), dish, right, up, 2.00D * s,
                0.84F, 0.86F, 0.88F, alpha);
        planeRing(pose, lines, dish, right, up, 2.00D * s,
                0.94F, 0.96F, 1.0F, alpha * 0.55F);
        // 馈源：盘心伸出的支杆 + 小圆柱
        double[] feed = add(dish, mul(fwd, -1.15D * s));
        line(pose, lines, dish[0], dish[1], dish[2], feed[0], feed[1], feed[2],
                0.72F, 0.74F, 0.76F, alpha * 0.75F, 0, 0, 1);
        solidBox(quads, matrixOf(pose), feed, right, up, fwd,
                0.30D * s, 0.30D * s, 0.34D * s, 0.55F, 0.56F, 0.58F, alpha);
        // 天线与舱体之间的两根支撑
        double[] dishLeft = add(dish, mul(right, -1.6D * s));
        double[] dishRight = add(dish, mul(right, 1.6D * s));
        double[] hull = add(center, mul(right, 1.2D * s));
        line(pose, lines, dishLeft[0], dishLeft[1], dishLeft[2], hull[0], hull[1], hull[2],
                0.55F, 0.52F, 0.40F, alpha * 0.55F, 0, 0, 1);
        line(pose, lines, dishRight[0], dishRight[1], dishRight[2], hull[0], hull[1], hull[2],
                0.55F, 0.52F, 0.40F, alpha * 0.55F, 0, 0, 1);
        // 导航灯
        float blink = 0.35F + 0.65F * (0.5F + 0.5F * (float) Math.sin(time * 0.20D));
        planeRing(pose, lines, add(center, mul(up, 2.32D * s)), right, up, 0.22D * s,
                1.0F, 1.0F, 1.0F, alpha * blink);
        planeRing(pose, lines, add(center, mul(right, -1.62D * s)), right, up, 0.16D * s,
                1.0F, 0.35F, 0.28F, alpha * blink);
    }

    /**
     * 天基炮（按参考图重做）：多模块战舰式炮台 —— 金属灰主舰体、橙色发光核心环、
     * 侧面武器舱、背部散热板、尾部橙色推进焰。炮口朝地球方向。
     */
    private static void renderDreadnought(PoseStack pose, VertexConsumer quads, VertexConsumer lines,
                                          double[] center, double[] right, double[] up, double[] fwd,
                                          double scale, float alpha, double time) {
        double s = scale;
        // 主舰体
        solidBox(quads, matrixOf(pose), center, right, up, fwd,
                4.2D * s, 1.15D * s, 1.45D * s, 0.42F, 0.44F, 0.47F, alpha);
        // 背部脊梁 + 散热板
        solidBox(quads, matrixOf(pose), add(center, mul(up, 1.35D * s)), right, up, fwd,
                3.2D * s, 0.32D * s, 1.0D * s, 0.50F, 0.52F, 0.55F, alpha);
        for (int side = -1; side <= 1; side += 2) {
            solidBox(quads, matrixOf(pose), add(center, add(mul(up, 1.75D * s), mul(right, side * 2.0D * s))),
                    right, up, fwd, 1.0D * s, 0.08D * s, 1.6D * s, 0.66F, 0.68F, 0.70F, alpha);
            // 侧面武器舱
            solidBox(quads, matrixOf(pose), add(center, add(mul(right, side * 3.4D * s), mul(up, -0.25D * s))),
                    right, up, fwd, 0.75D * s, 0.55D * s, 1.25D * s, 0.36F, 0.38F, 0.41F, alpha);
            // 橙色能量条
            line(pose, lines,
                    center[0] + right[0] * side * 4.15D * s + up[0] * 0.55D * s,
                    center[1] + right[1] * side * 4.15D * s + up[1] * 0.55D * s,
                    center[2] + right[2] * side * 4.15D * s + up[2] * 0.55D * s,
                    center[0] + right[0] * side * 4.15D * s - up[0] * 0.75D * s,
                    center[1] + right[1] * side * 4.15D * s - up[1] * 0.75D * s,
                    center[2] + right[2] * side * 4.15D * s - up[2] * 0.75D * s,
                    1.0F, 0.56F, 0.18F, alpha * 0.65F, 0, 0, 1);
        }
        // 中央发光核心：橙色实心环 + 两圈环 + 脉动
        float pulse = 0.6F + 0.4F * (0.5F + 0.5F * (float) Math.sin(time * 0.9D));
        double[] core = add(center, mul(fwd, -1.55D * s));
        solidDisc(quads, matrixOf(pose), core, right, up, 1.35D * s,
                1.0F, 0.50F, 0.12F, alpha * 0.95F);
        planeRing(pose, lines, core, right, up, 1.35D * s, 1.0F, 0.78F, 0.40F, alpha * 0.80F);
        planeRing(pose, lines, core, right, up, (1.8D + 0.15D * pulse) * s, 1.0F, 0.55F, 0.16F, alpha * 0.45F);
        planeRing(pose, lines, core, right, up, (2.5D + 0.25D * pulse) * s, 1.0F, 0.42F, 0.10F, alpha * 0.22F);
        // 尾部推进焰（朝向镜头一侧的反方向）
        for (int side = -1; side <= 1; side += 2) {
            double[] thr = add(center, add(mul(fwd, 1.55D * s), mul(right, side * 1.5D * s)));
            planeRing(pose, lines, thr, right, up, 0.45D * s, 1.0F, 0.55F, 0.16F, alpha * 0.50F);
            double[] tail = add(thr, mul(fwd, 2.2D * s));
            line(pose, lines, thr[0], thr[1], thr[2], tail[0], tail[1], tail[2],
                    1.0F, 0.62F, 0.24F, alpha * 0.35F, 0, 0, 1);
        }
    }

    /** 实心长方体：六个面都填色，按朝向给不同亮度，读出体积。 */
    private static void solidBox(VertexConsumer quads, Matrix4f matrix, double[] c,
                                 double[] right, double[] up, double[] fwd,
                                 double hx, double hy, double hz,
                                 float r, float g, float b, float a) {
        boxFace(quads, matrix, c, right, up, fwd, hx, hy, hz,
                1, 0, 0, 0.88F, r, g, b, a);       // +right
        boxFace(quads, matrix, c, right, up, fwd, hx, hy, hz,
                -1, 0, 0, 0.62F, r, g, b, a);      // -right
        boxFace(quads, matrix, c, right, up, fwd, hx, hy, hz,
                0, 1, 0, 1.02F, r, g, b, a);       // +up（受光面）
        boxFace(quads, matrix, c, right, up, fwd, hx, hy, hz,
                0, -1, 0, 0.40F, r, g, b, a);      // -up（背光面）
        boxFace(quads, matrix, c, right, up, fwd, hx, hy, hz,
                0, 0, 1, 0.56F, r, g, b, a);       // +fwd（背向镜头的远面）
        boxFace(quads, matrix, c, right, up, fwd, hx, hy, hz,
                0, 0, -1, 0.94F, r, g, b, a);      // -fwd（朝向镜头）
    }

    /** 长方体的一个面（axis 指定法线方向，shade 是该面的亮度系数）。 */
    private static void boxFace(VertexConsumer quads, Matrix4f matrix, double[] c,
                                double[] right, double[] up, double[] fwd,
                                double hx, double hy, double hz,
                                int ax, int ay, int az, float shade,
                                float r, float g, float b, float a) {
        // 面中心 = 中心 + 法线轴上的半长；四个角在另外两根轴上取 ±
        double[] fc = add(c, add(add(mul(right, ax * hx), mul(up, ay * hy)), mul(fwd, az * hz)));
        double[] u;
        double[] v;
        double hu;
        double hv;
        if (ax != 0) {
            u = up;
            v = fwd;
            hu = hy;
            hv = hz;
        } else if (ay != 0) {
            u = right;
            v = fwd;
            hu = hx;
            hv = hz;
        } else {
            u = right;
            v = up;
            hu = hx;
            hv = hy;
        }
        float rr = Math.min(1.0F, r * shade);
        float gg = Math.min(1.0F, g * shade);
        float bb = Math.min(1.0F, b * shade);
        quad(quads, matrix,
                fc[0] - u[0] * hu - v[0] * hv, fc[1] - u[1] * hu - v[1] * hv, fc[2] - u[2] * hu - v[2] * hv,
                fc[0] + u[0] * hu - v[0] * hv, fc[1] + u[1] * hu - v[1] * hv, fc[2] + u[2] * hu - v[2] * hv,
                fc[0] + u[0] * hu + v[0] * hv, fc[1] + u[1] * hu + v[1] * hv, fc[2] + u[2] * hu + v[2] * hv,
                fc[0] - u[0] * hu + v[0] * hv, fc[1] - u[1] * hu + v[1] * hv, fc[2] - u[2] * hu + v[2] * hv,
                rr, gg, bb, a);
    }

    /** 实心圆盘：同心环带填满，中心比边缘亮一点（受光的天线碟）。 */
    private static void solidDisc(VertexConsumer quads, Matrix4f matrix, double[] c,
                                  double[] right, double[] up, double radius,
                                  float r, float g, float b, float a) {
        int rings = 10;
        int segs = 24;
        for (int ri = 0; ri < rings; ri++) {
            double r0 = radius * ri / rings;
            double r1 = radius * (ri + 1) / rings;
            float shade = 1.0F - 0.45F * (ri / (float) rings);
            for (int si = 0; si < segs; si++) {
                double a1 = Math.PI * 2.0D * si / segs;
                double a2 = Math.PI * 2.0D * (si + 1) / segs;
                planeQuad4(quads, matrix, c, right, up,
                        r0 * Math.cos(a1), r0 * Math.sin(a1),
                        r0 * Math.cos(a2), r0 * Math.sin(a2),
                        r1 * Math.cos(a2), r1 * Math.sin(a2),
                        r1 * Math.cos(a1), r1 * Math.sin(a1),
                        r * shade, g * shade, b * shade, a);
            }
        }
    }

    /** 炮口激波：白热环 + 青环 + 五道火花（发射瞬间的「枪口焰」）。 */
    private static void muzzleFlash(PoseStack pose, VertexConsumer lines, double[] at,
                                    double[] right, double[] up, float alpha, double time) {
        float pulse = 0.55F + 0.45F * (0.5F + 0.5F * (float) Math.sin(time * 1.9D));
        planeRing(pose, lines, at, right, up, 4.5D * sceneScale * pulse,
                1.0F, 1.0F, 1.0F, alpha * 0.80F);
        planeRing(pose, lines, at, right, up, 8.0D * sceneScale * pulse,
                CYAN_R, CYAN_G, CYAN_B, alpha * 0.30F);
        for (int i = 0; i < 5; i++) {
            double ang = i * Math.PI * 2.0D / 5.0D + time * 0.35D;
            double r0 = 2.0D * sceneScale;
            double r1 = (5.0D + 2.0D * Math.sin(time * 1.3D + i)) * sceneScale;
            double c = Math.cos(ang);
            double s = Math.sin(ang);
            line(pose, lines,
                    at[0] + right[0] * c * r0 + up[0] * s * r0,
                    at[1] + right[1] * c * r0 + up[1] * s * r0,
                    at[2] + right[2] * c * r0 + up[2] * s * r0,
                    at[0] + right[0] * c * r1 + up[0] * s * r1,
                    at[1] + right[1] * c * r1 + up[1] * s * r1,
                    at[2] + right[2] * c * r1 + up[2] * s * r1,
                    1.0F, 0.92F, 0.70F, alpha * 0.55F, 0, 0, 1);
        }
    }

    /**
     * 地球上的命中：白热闪光 + 三层扩散环 + 十二道碎片射线 + 中心余辉。
     * {@code impactAge} 取客户端状态的「命中后 tick」（小于 0 表示还没命中）。
     */
    private static void earthImpact(PoseStack pose, VertexConsumer lines, double[] at,
                                    double[] right, double[] up, float alpha, long impactAge) {
        if (impactAge < 0L) {
            return;
        }
        float fade = 1.0F - Mth.clamp(impactAge / 70.0F, 0.0F, 1.0F);
        if (fade <= 0.01F) {
            return;
        }
        float t = Mth.clamp(impactAge / 20.0F, 0.0F, 1.0F);
        float t2 = Mth.clamp(impactAge / 55.0F, 0.0F, 1.0F);
        // 白热闪环
        planeRing(pose, lines, at, right, up, (1.2D + 8.0D * t) * sceneScale,
                1.0F, 1.0F, 1.0F, alpha * 0.85F * fade);
        // 主扩散环
        planeRing(pose, lines, at, right, up, (2.0D + 17.0D * t) * sceneScale,
                CYAN_R, CYAN_G, CYAN_B, alpha * 0.55F * fade);
        // 慢一圈的余波
        planeRing(pose, lines, at, right, up, (2.0D + 26.0D * t2) * sceneScale,
                0.72F, 0.92F, 1.0F, alpha * 0.22F * (1.0F - t2));
        // 碎片射线：从接触点向外甩出的短划
        for (int i = 0; i < 12; i++) {
            double ang = i * Math.PI * 2.0D / 12.0D + 0.23D;
            double c = Math.cos(ang);
            double s = Math.sin(ang);
            double r0 = (1.6D + 11.0D * t) * sceneScale;
            double r1 = r0 + (2.2D + 1.6D * (1.0F - t)) * sceneScale;
            line(pose, lines,
                    at[0] + right[0] * c * r0 + up[0] * s * r0,
                    at[1] + right[1] * c * r0 + up[1] * s * r0,
                    at[2] + right[2] * c * r0 + up[2] * s * r0,
                    at[0] + right[0] * c * r1 + up[0] * s * r1,
                    at[1] + right[1] * c * r1 + up[1] * s * r1,
                    at[2] + right[2] * c * r1 + up[2] * s * r1,
                    1.0F, 0.88F, 0.66F, alpha * 0.50F * fade, 0, 0, 1);
        }
        if (impactAge < 22L) {
            planeRing(pose, lines, at, right, up, 1.8D * sceneScale,
                    1.0F, 1.0F, 1.0F, alpha * 0.55F * (1.0F - impactAge / 22.0F));
        }
    }

    // ------------------------------------------------------------------ 图元

    /** 相机平面内的圆环。 */
    private static void planeRing(PoseStack pose, VertexConsumer buffer, double[] center,
                                  double[] right, double[] up, double radius,
                                  float r, float g, float b, float a) {
        int segments = 32;
        for (int i = 0; i < segments; i++) {
            double a1 = i * Math.PI * 2.0D / segments;
            double a2 = (i + 1) * Math.PI * 2.0D / segments;
            double c1 = Math.cos(a1) * radius;
            double s1 = Math.sin(a1) * radius;
            double c2 = Math.cos(a2) * radius;
            double s2 = Math.sin(a2) * radius;
            line(pose, buffer,
                    center[0] + right[0] * c1 + up[0] * s1,
                    center[1] + right[1] * c1 + up[1] * s1,
                    center[2] + right[2] * c1 + up[2] * s1,
                    center[0] + right[0] * c2 + up[0] * s2,
                    center[1] + right[1] * c2 + up[1] * s2,
                    center[2] + right[2] * c2 + up[2] * s2,
                    r, g, b, a, 0, 0, 1);
        }
    }

    /** 相机平面内的椭圆环（吸积盘）：tilt 为平面内旋转角。 */
    private static void planeEllipse(PoseStack pose, VertexConsumer buffer, double[] center,
                                     double[] right, double[] up, double rx, double ry,
                                     double tilt, float r, float g, float b, float a) {
        int segments = 40;
        double ct = Math.cos(tilt);
        double st = Math.sin(tilt);
        for (int i = 0; i < segments; i++) {
            double a1 = i * Math.PI * 2.0D / segments;
            double a2 = (i + 1) * Math.PI * 2.0D / segments;
            double x1 = Math.cos(a1) * rx;
            double y1 = Math.sin(a1) * ry;
            double x2 = Math.cos(a2) * rx;
            double y2 = Math.sin(a2) * ry;
            double rx1 = x1 * ct - y1 * st;
            double ry1 = x1 * st + y1 * ct;
            double rx2 = x2 * ct - y2 * st;
            double ry2 = x2 * st + y2 * ct;
            line(pose, buffer,
                    center[0] + right[0] * rx1 + up[0] * ry1,
                    center[1] + right[1] * rx1 + up[1] * ry1,
                    center[2] + right[2] * rx1 + up[2] * ry1,
                    center[0] + right[0] * rx2 + up[0] * ry2,
                    center[1] + right[1] * rx2 + up[1] * ry2,
                    center[2] + right[2] * rx2 + up[2] * ry2,
                    r, g, b, a, 0, 0, 1);
        }
    }

    /** 相机平面内的矩形。 */
    private static void planeQuad(VertexConsumer buffer, Matrix4f matrix, double[] center,
                                  double[] right, double[] up,
                                  double x1, double y1, double x2, double y2,
                                  float r, float g, float b, float a) {
        planeQuad4(buffer, matrix, center, right, up,
                x1, y1, x2, y1, x2, y2, x1, y2, r, g, b, a);
    }

    /** 相机平面内的任意四边形。 */
    private static void planeQuad4(VertexConsumer buffer, Matrix4f matrix, double[] center,
                                   double[] right, double[] up,
                                   double x1, double y1, double x2, double y2,
                                   double x3, double y3, double x4, double y4,
                                   float r, float g, float b, float a) {
        quad(buffer, matrix,
                center[0] + right[0] * x1 + up[0] * y1,
                center[1] + right[1] * x1 + up[1] * y1,
                center[2] + right[2] * x1 + up[2] * y1,
                center[0] + right[0] * x2 + up[0] * y2,
                center[1] + right[1] * x2 + up[1] * y2,
                center[2] + right[2] * x2 + up[2] * y2,
                center[0] + right[0] * x3 + up[0] * y3,
                center[1] + right[1] * x3 + up[1] * y3,
                center[2] + right[2] * x3 + up[2] * y3,
                center[0] + right[0] * x4 + up[0] * y4,
                center[1] + right[1] * x4 + up[1] * y4,
                center[2] + right[2] * x4 + up[2] * y4,
                r, g, b, a);
    }

    /** 相机基里的一个盒子（12 条棱）。 */
    private static void camBox(PoseStack pose, VertexConsumer buffer, double[] c,
                               double[] right, double[] up, double[] fwd,
                               double hx, double hy, double hz,
                               float r, float g, float b, float a) {
        double[][] corners = new double[8][3];
        int idx = 0;
        for (int i = -1; i <= 1; i += 2) {
            for (int j = -1; j <= 1; j += 2) {
                for (int k = -1; k <= 1; k += 2) {
                    corners[idx++] = new double[]{
                            c[0] + right[0] * hx * i + up[0] * hy * j + fwd[0] * hz * k,
                            c[1] + right[1] * hx * i + up[1] * hy * j + fwd[1] * hz * k,
                            c[2] + right[2] * hx * i + up[2] * hy * j + fwd[2] * hz * k};
                }
            }
        }
        int[][] edges = {
                {0, 1}, {2, 3}, {4, 5}, {6, 7},
                {0, 2}, {1, 3}, {4, 6}, {5, 7},
                {0, 4}, {1, 5}, {2, 6}, {3, 7}};
        for (int[] e : edges) {
            double[] p = corners[e[0]];
            double[] q = corners[e[1]];
            line(pose, buffer, p[0], p[1], p[2], q[0], q[1], q[2], r, g, b, a, 0, 0, 1);
        }
    }

    /** 小亮点：三轴十字（不用贴图，任何角度都能看到）。必须走带 normal 的线格式。 */
    private static void dot3(PoseStack pose, VertexConsumer lines, double[] p, double size,
                             float r, float g, float b, float a) {
        line(pose, lines, p[0] - size, p[1], p[2], p[0] + size, p[1], p[2], r, g, b, a, 0, 0, 1);
        line(pose, lines, p[0], p[1] - size, p[2], p[0], p[1] + size, p[2], r, g, b, a, 0, 0, 1);
        line(pose, lines, p[0], p[1], p[2] - size, p[0], p[1], p[2] + size, r, g, b, a, 0, 0, 1);
    }

    private static void quad(VertexConsumer buffer, Matrix4f matrix,
                             double x1, double y1, double z1,
                             double x2, double y2, double z2,
                             double x3, double y3, double z3,
                             double x4, double y4, double z4,
                             float r, float g, float b, float a) {
        vertex(buffer, matrix, x1, y1, z1, r, g, b, a);
        vertex(buffer, matrix, x2, y2, z2, r, g, b, a);
        vertex(buffer, matrix, x3, y3, z3, r, g, b, a);
        vertex(buffer, matrix, x4, y4, z4, r, g, b, a);
    }

    private static void vertex(VertexConsumer buffer, Matrix4f matrix,
                               double x, double y, double z,
                               float r, float g, float b, float a) {
        buffer.vertex(matrix, (float) x, (float) y, (float) z).color(r, g, b, a).endVertex();
    }

    private static void line(PoseStack pose, VertexConsumer buffer,
                             double x1, double y1, double z1,
                             double x2, double y2, double z2,
                             float r, float g, float b, float a,
                             float nx, float ny, float nz) {
        buffer.vertex(pose.last().pose(), (float) x1, (float) y1, (float) z1)
                .color(r, g, b, a).normal(pose.last().normal(), nx, ny, nz).endVertex();
        buffer.vertex(pose.last().pose(), (float) x2, (float) y2, (float) z2)
                .color(r, g, b, a).normal(pose.last().normal(), nx, ny, nz).endVertex();
    }

    // ------------------------------------------------------------------ 向量

    private static double[] offset(double[] from, double[] fwd, double[] right, double[] up,
                                   double forward, double side, double height) {
        return new double[]{
                from[0] + (fwd[0] * forward + right[0] * side + up[0] * height) * sceneScale,
                from[1] + (fwd[1] * forward + right[1] * side + up[1] * height) * sceneScale,
                from[2] + (fwd[2] * forward + right[2] * side + up[2] * height) * sceneScale};
    }

    private static double[] add(double[] a, double[] b) {
        return new double[]{a[0] + b[0], a[1] + b[1], a[2] + b[2]};
    }

    private static double[] sub(double[] a, double[] b) {
        return new double[]{a[0] - b[0], a[1] - b[1], a[2] - b[2]};
    }

    private static double[] mul(double[] a, double k) {
        return new double[]{a[0] * k, a[1] * k, a[2] * k};
    }

    private static double len(double[] a) {
        return Math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]);
    }

    private static double[] norm(double[] a) {
        double l = len(a);
        if (l < 1.0E-6D) {
            return new double[]{0.0D, 0.0D, 1.0D};
        }
        return new double[]{a[0] / l, a[1] / l, a[2] / l};
    }

    private static double[] lerp3(double[] a, double[] b, double t) {
        t = Mth.clamp(t, 0.0D, 1.0D);
        return new double[]{
                a[0] + (b[0] - a[0]) * t,
                a[1] + (b[1] - a[1]) * t,
                a[2] + (b[2] - a[2]) * t};
    }

    private static double smooth01(double t) {
        t = Mth.clamp(t, 0.0D, 1.0D);
        return t * t * (3.0D - 2.0D * t);
    }

    private static float smooth(float t) {
        t = Mth.clamp(t, 0.0F, 1.0F);
        return t * t * (3.0F - 2.0F * t);
    }

    private static double yawJitter(int index, double time) {
        return time * 0.9D + index * 2.7D;
    }
}
