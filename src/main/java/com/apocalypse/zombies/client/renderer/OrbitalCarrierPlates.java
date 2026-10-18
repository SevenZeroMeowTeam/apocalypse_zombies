package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.OrbitalStrikeClientState;
import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import com.apocalypse.zombies.orbital.engine.StrikeProtocols;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import org.joml.Matrix4f;

/**
 * 五种轨道打击的「载体特写」太空镜头（2.5D 电影板）。
 *
 * <p><b>为什么是电影板而不是方块模型</b>：用户给的五张图本身已经是完整的写实太空镜头
 * （载体、地球、光束全在画面里）。把它们作为镜头板，配合充能光、发射光束、命中闪光、
 * 镜头拉开与震动，能保留参考图的全部细节；用方块重拼只会得到一个不像的近似体。</p>
 *
 * <p><b>镜头语言</b>：锁定阶段镜头贴近载体（炮口/ vortex 在画面里，完整光束在画外），
 * 充能越满炮口越亮；命中前的最后 2 tick 开始快速拉开，命中时整幅画面展开，
 * 画好的光束/爆炸随拉镜一起揭示，叠加程序化的炮口焰、束流亮点、冲击环与屏幕震动。
 * 小行星模式没有光束：镜头一路推近，命中时白闪切回地面。</p>
 *
 * <p><b>渲染约束</b>：全部走原版实体渲染类型（{@code entityTranslucentEmissive}）+
 * NEW_ENTITY 全属性顶点；电影板不写深度（COLOR_WRITE），所以后面的线框特效可以正常叠在它上面。
 * 五张电影板 1408×768，随包分发；不建自定义 RenderType、不做 shader/FBO。</p>
 */
public final class OrbitalCarrierPlates {

    // ------------------------------------------------------------------ 资源

    private static final ResourceLocation TEX_CANNON = tex("carrier_cannon");
    private static final ResourceLocation TEX_LANCE = tex("carrier_lance");
    private static final ResourceLocation TEX_SINGULARITY = tex("carrier_singularity");
    private static final ResourceLocation TEX_ASTEROID = tex("carrier_asteroid");
    private static final ResourceLocation TEX_PLASMA = tex("carrier_plasma");
    private static final ResourceLocation TEX_GLOW = tex("glow");
    private static final ResourceLocation TEX_BEAM = tex("beam_strip");

    private static final RenderType RT_CANNON = RenderType.entityTranslucentEmissive(TEX_CANNON);
    private static final RenderType RT_LANCE = RenderType.entityTranslucentEmissive(TEX_LANCE);
    private static final RenderType RT_SINGULARITY = RenderType.entityTranslucentEmissive(TEX_SINGULARITY);
    private static final RenderType RT_ASTEROID = RenderType.entityTranslucentEmissive(TEX_ASTEROID);
    private static final RenderType RT_PLASMA = RenderType.entityTranslucentEmissive(TEX_PLASMA);
    private static final RenderType RT_GLOW = RenderType.entityTranslucentEmissive(TEX_GLOW);
    private static final RenderType RT_BEAM = RenderType.entityTranslucentEmissive(TEX_BEAM);
    /** 行星陨落重做用：星云背景 / 地球 / 小行星抠图。 */
    private static final RenderType RT_SPACE = RenderType.entityTranslucentEmissive(tex("nebula"));
    private static final RenderType RT_EARTH_PLATE = RenderType.entityTranslucentEmissive(tex("earth"));
    private static final RenderType RT_ASTEROID_CUT =
            RenderType.entityTranslucentEmissive(tex("carrier_asteroid_cutout"));

    /** 电影板原始比例（所有图都是 1408×768）。 */
    private static final double TEX_ASPECT = 1408.0D / 768.0D;
    /** 电影板放在镜头前方多远（再按 sceneScale 缩放，低视距也不裁）。 */
    private static final double PLATE_DISTANCE = 24.0D;

    private static final float[] ORANGE = {1.00F, 0.58F, 0.20F};
    private static final float[] BLUE = {0.55F, 0.82F, 1.00F};
    private static final float[] CYAN = {0.70F, 0.95F, 1.00F};
    /** 蜂群 SWARM 的孢子绿。 */
    private static final float[] SWARM_GREEN = {0.55F, 1.00F, 0.55F};
    private static final float[] WHITE = {1.00F, 0.96F, 0.88F};

    /** 等离子风暴的五个落点（电影板上的归一化坐标）。第一个与画里的主爆炸重合。 */
    private static final double[][] STORM_IMPACTS = {
            {0.820D, 0.700D}, {0.725D, 0.660D}, {0.885D, 0.735D},
            {0.765D, 0.715D}, {0.925D, 0.675D}, {0.690D, 0.700D}, {0.845D, 0.635D}};

    private OrbitalCarrierPlates() {
    }

    private static ResourceLocation tex(String name) {
        return new ResourceLocation(ApocalypseZombies.MOD_ID, "textures/environment/" + name + ".png");
    }

    // ------------------------------------------------------------------ 规格

    private enum Style {CANNON, LANCE, GRAVITY, STORM, ASTEROID}

    /**
     * 一种弹种的电影板参数。
     *
     * @param muzzleU/V  炮口在电影板上的归一化坐标
     * @param chargeU/V  充能光的位置（多数弹种就是炮口；等离子放在舰体反应堆上，
     *                   这样特写可以避开画面里已经画好的巨大光束）
     * @param impactU/V  画面上可见的命中点（没有则给光束离开画面的方向点）
     * @param impactVisible 画面上是否有真实的命中点（false = 命中发生在地面，电影板里没有）
     * @param focusU/V   充能特写的中心
     * @param chargeZoom 充能特写的放大倍率
     * @param engines    引擎/姿态喷口的归一化坐标（用于闪烁光）
     */
    private record Spec(RenderType type, Style style,
                        double focusU, double focusV, double chargeZoom,
                        double muzzleU, double muzzleV,
                        double chargeU, double chargeV,
                        double impactU, double impactV,
                        boolean impactVisible,
                        double[][] engines, float[] color) {
    }

    private static Spec spec(OrbitalStrikeMode mode) {
        return switch (mode) {
            case CANNON -> new Spec(RT_CANNON, Style.CANNON,
                    0.70D, 0.33D, 1.70D,
                    0.455D, 0.515D,
                    0.455D, 0.515D,
                    0.205D, 0.795D, true,
                    new double[][]{{0.84D, 0.28D}, {0.91D, 0.34D}, {0.83D, 0.45D}, {0.78D, 0.20D}},
                    ORANGE);
            case LANCE -> new Spec(RT_LANCE, Style.LANCE,
                    0.36D, 0.38D, 1.55D,
                    0.600D, 0.530D,
                    0.600D, 0.530D,
                    0.970D, 0.760D, false,
                    new double[][]{{0.12D, 0.30D}, {0.46D, 0.58D}, {0.43D, 0.66D}, {0.55D, 0.62D}},
                    BLUE);
            case GRAVITY -> new Spec(RT_SINGULARITY, Style.GRAVITY,
                    0.44D, 0.47D, 1.22D,
                    0.835D, 0.490D,
                    0.835D, 0.490D,
                    1.030D, 0.500D, false,
                    new double[][]{{0.15D, 0.22D}, {0.14D, 0.70D}, {0.62D, 0.83D}, {0.28D, 0.10D}},
                    BLUE);
            case STORM -> new Spec(RT_PLASMA, Style.STORM,
                    0.20D, 0.28D, 2.40D,
                    0.478D, 0.352D,
                    0.300D, 0.300D,
                    0.820D, 0.700D, true,
                    new double[][]{{0.12D, 0.22D}, {0.49D, 0.31D}, {0.15D, 0.45D}},
                    CYAN);
            case PLANET -> new Spec(RT_ASTEROID, Style.ASTEROID,
                    0.49D, 0.47D, 1.00D,
                    0.49D, 0.47D,
                    0.49D, 0.47D,
                    0.49D, 0.58D, false,
                    new double[][]{},
                    ORANGE);
            default -> null;  // LASER 保留原来的程序化卫星舞台
        };
    }

    /** 这个弹种是否有电影板（LASER 没有，继续走 OrbtialSpaceStage 的程序化卫星）。 */
    public static boolean has(OrbitalStrikeMode mode) {
        return spec(mode) != null;
    }

    // ------------------------------------------------------------------ 主入口

    public static void render(PoseStack pose, VertexConsumer lines,
                              MultiBufferSource.BufferSource buffers, Matrix4f matrix,
                              double[] eye, double[] fwd, double[] right, double[] up,
                              float alpha, double time, OrbitalStrikeMode mode,
                              double sceneScale) {
        Spec spec = spec(mode);
        if (spec == null || alpha <= 0.005F) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.level == null) {
            return;
        }
        double elapsed = OrbitalStrikeClientState.elapsed();
        double lock = OrbitalStrikeClientState.lockTicks();
        double fall = Math.max(1.0D, OrbitalStrikeClientState.fallTicks());
        double impactTick = lock + fall;
        double impactAge = elapsed - impactTick;
        double fireAge = elapsed - lock;
        float charge = Mth.clamp((float) (elapsed / Math.max(1.0D, lock)), 0.0F, 1.0F);

        double winAspect = minecraft.getWindow().getWidth()
                / (double) Math.max(1, minecraft.getWindow().getHeight());

        // —— 镜头：充能特写 → 命中前拉开；小行星则一路推近
        double zoom;
        double cu;
        double cv;
        double progress = Mth.clamp((float) (elapsed / Math.max(1.0D, impactTick)), 0.0F, 1.0F);
        double dollyProgress = smooth((float) Mth.clamp(elapsed / Math.max(1.0D, lock * 0.65D),
                0.0D, 1.0D));
        if (spec.style == Style.ASTEROID) {
            // 小行星模式没有载体特写：星云背景缓慢推近，地球和小行星是独立的 2.5D 层。
            zoom = 1.0D + 0.10D * smooth(progress);
            cu = 0.5D;
            cv = 0.5D;
        } else {
            // 轨道炮/长矛/奇点：**发射瞬间就开始拉镜**，让玩家看见平台开火 + 弹体飞出；
            // 等离子风暴保持到命中前才拉（画里的爆炸太抢眼，提前展开会剧透）。
            double pull;
            if (spec.style == Style.STORM) {
                pull = smooth((float) Mth.clamp((impactAge + 4.0D) / 10.0D, 0.0D, 1.0D));
            } else {
                pull = smooth((float) Mth.clamp(fireAge / 12.0D, 0.0D, 1.0D));
            }
            double kick = fireAge >= 0.0D && fireAge < 8.0D ? 0.025D * (1.0D - fireAge / 8.0D) : 0.0D;
            // 由远到近：开场是整幅载体/地球的远景，锁定前 65% 内平滑推近到平台特写。
            double close = Mth.lerp((float) dollyProgress, 1.0F, (float) spec.chargeZoom)
                    + 0.05D * charge + kick;
            zoom = Mth.lerp((float) pull, (float) close, 1.0F);
            cu = Mth.lerp((float) pull,
                    (float) Mth.lerp((float) dollyProgress, 0.5F, (float) spec.focusU), 0.5F);
            cv = Mth.lerp((float) pull,
                    (float) Mth.lerp((float) dollyProgress, 0.5F, (float) spec.focusV), 0.5F);
        }

        // 命中帧的 FOV punch 对 billboard 不产生缩放，这里补一记小幅推近
        if (impactAge >= 0.0D && impactAge < 12.0D) {
            zoom += 0.030D * Math.exp(-impactAge / 4.5D);
        }
        // —— 屏幕震动：发射与命中各一记（电影板是 billboard，镜头抖动带不动它，这里单独抖）
        double shake = 0.0D;
        if (fireAge >= 0.0D && fireAge < 10.0D) {
            shake = Math.max(shake, (1.0D - fireAge / 10.0D) * 0.006D);
        }
        if (impactAge >= 0.0D && impactAge < 14.0D) {
            shake = Math.max(shake, (1.0D - impactAge / 14.0D) * 0.013D);
        }
        double shakeX = Math.sin(time * 6.7D) * shake;
        double shakeY = Math.cos(time * 9.3D) * shake * 0.7D;

        // —— 电影板四角：按当前 FOV 计算尺寸（含命中帧的 FOV punch 余量）
        double fov = minecraft.options.fov().get() + 2.0D;
        if (impactAge >= 0.0D && impactAge < 12.0D) {
            fov += 13.0D * Math.exp(-impactAge / 4.5D);
        }
        double dist = PLATE_DISTANCE * sceneScale;
        double halfH = Math.tan(Math.toRadians(fov * 0.5D)) * dist;
        double halfW = halfH * winAspect;
        double[] center = add(eye, mul(fwd, dist));
        center = add(center, add(mul(right, shakeX * 2.0D * halfW), mul(up, -shakeY * 2.0D * halfH)));

        // 小行星模式给整幅画面一点缓慢滚转（星野跟着动，避免完全静止）
        double[] rr = right;
        double[] uu = up;
        if (spec.style == Style.ASTEROID) {
            double roll = Math.toRadians(2.6D * smooth(progress) * Math.sin(time * 0.11D));
            rr = add(mul(right, Math.cos(roll)), mul(up, Math.sin(roll)));
            uu = add(mul(up, Math.cos(roll)), mul(right, -Math.sin(roll)));
        }

        // —— cover 裁切 + 缩放/平移（v=0 是图片顶部）
        double uSpan = 1.0D;
        double vSpan = 1.0D;
        if (winAspect > TEX_ASPECT) {
            vSpan = TEX_ASPECT / winAspect;
        } else {
            uSpan = winAspect / TEX_ASPECT;
        }
        uSpan /= zoom;
        vSpan /= zoom;
        double u0 = Mth.clamp(cu - uSpan * 0.5D, 0.0D, 1.0D - uSpan);
        double v0 = Mth.clamp(cv - vSpan * 0.5D, 0.0D, 1.0D - vSpan);
        double u1 = u0 + uSpan;
        double v1 = v0 + vSpan;

        // —— 行星陨落：不用整张静态小行星板，改成「星云背景 + 地球 + 会飞会变小的小行星」
        if (spec.style == Style.ASTEROID) {
            renderAsteroidScene(lines, buffers, matrix, center, rr, uu, halfW, halfH,
                    u0, v0, u1, v1, alpha, time, elapsed, lock, fall, impactAge, fwd);
            return;
        }

        // —— 1. 电影板本体
        {
            VertexConsumer plate = buffers.getBuffer(spec.type);
            texQuad(plate, matrix, center, rr, uu, halfW, halfH,
                    (float) u0, (float) v0, (float) u1, (float) v1,
                    1.0F, 1.0F, 1.0F, alpha, fwd);
            buffers.endBatch(spec.type);
        }
        // 远景阶段压暗：避免一开场就把画里的光束/爆炸/命中点全剧透；
        // 镜头推近的同时亮度恢复，等画面亮起来时命中点已经在特写画外。
        darken(buffers, matrix, center, rr, uu, halfW, halfH,
                (1.0F - (float) dollyProgress) * 0.70F * alpha);

        // —— 坐标映射
        double[] muzzle = platePoint(spec.muzzleU, spec.muzzleV, center, rr, uu, halfW, halfH,
                u0, v0, u1, v1);
        double[] impact = platePoint(spec.impactU, spec.impactV, center, rr, uu, halfW, halfH,
                u0, v0, u1, v1);
        double[] chargePoint = platePoint(spec.chargeU, spec.chargeV, center, rr, uu, halfW, halfH,
                u0, v0, u1, v1);

        VertexConsumer glow = buffers.getBuffer(RT_GLOW);
        VertexConsumer beam = buffers.getBuffer(RT_BEAM);

        // —— 2. 引擎闪烁
        for (int i = 0; i < spec.engines.length; i++) {
            double[] e = platePoint(spec.engines[i][0], spec.engines[i][1], center, rr, uu,
                    halfW, halfH, u0, v0, u1, v1);
            float flicker = 0.55F + 0.45F * (0.5F + 0.5F * (float) Math.sin(time * 7.3D + i * 1.9D));
            glowQuad(glow, matrix, e, rr, uu, (0.011D + 0.004D * flicker) * halfH,
                    spec.color[0], spec.color[1], spec.color[2],
                    alpha * 0.35F * flicker, fwd);
        }

        switch (spec.style) {
            case CANNON -> renderCannonStyle(lines, glow, beam, matrix, center, rr, uu,
                    halfW, halfH, chargePoint, impact, spec, charge, fireAge, impactAge, fall,
                    alpha, time, fwd, u0, v0, u1, v1);
            case LANCE -> renderLanceStyle(lines, glow, beam, matrix, center, rr, uu,
                    halfW, halfH, chargePoint, impact, charge, fireAge, alpha, time, fwd,
                    u0, v0, u1, v1);
            case GRAVITY -> renderGravityStyle(lines, glow, beam, matrix, center, rr, uu,
                    halfW, halfH, chargePoint, impact, spec, charge, fireAge, alpha, time, fwd,
                    u0, v0, u1, v1);
            case STORM -> renderStormStyle(lines, glow, beam, matrix, center, rr, uu,
                    halfW, halfH, muzzle, chargePoint, spec, charge, elapsed, lock + fall,
                    alpha, time, fwd, u0, v0, u1, v1);
            default -> {
                // ASTEROID 在上面的 renderAsteroidScene 分支提前返回，不会走到这里。
            }
        }

        buffers.endBatch(RT_GLOW);
        buffers.endBatch(RT_BEAM);
    }

    // ------------------------------------------------------------------ 各弹种

    private static void renderCannonStyle(VertexConsumer lines, VertexConsumer glow, VertexConsumer beam,
                                          Matrix4f matrix, double[] c, double[] r, double[] u,
                                          double hw, double hh, double[] muzzle, double[] impact,
                                          Spec spec, float charge, double fireAge, double impactAge,
                                          double fall, float alpha, double time, double[] fwd,
                                          double u0, double v0, double u1, double v1) {
        // 充能：炮口蓄能核 + 两圈收拢环
        chargeGlow(lines, glow, matrix, muzzle, r, u, hh, charge, ORANGE, alpha, time, fwd);
        // 炮身能量脉冲：三团橙光沿画里的炮管向炮口跑（平台在「装弹加压」）
        double[] barrelA = platePoint(0.630D, 0.370D, c, r, u, hw, hh, u0, v0, u1, v1);
        for (int i = 0; i < 3; i++) {
            double f = (time * 0.16D + i * 0.33D) % 1.0D;
            double[] pulse = lerp3(barrelA, muzzle, f);
            glowQuad(glow, matrix, pulse, r, u, 0.017D * hh,
                    1.0F, 0.58F, 0.20F, alpha * charge * 0.45F * (1.0F - (float) f * 0.6F), fwd);
        }
        ellipse(lines, matrix, muzzle, r, u, 0.10D * hh, 0.065D * hh,
                time * 0.8D, ORANGE[0], ORANGE[1], ORANGE[2], alpha * 0.28F * charge, fwd);
        if (fireAge >= 0.0D && fireAge < 10.0D) {
            float k = 1.0F - (float) fireAge / 10.0F;
            glowQuad(glow, matrix, muzzle, r, u, (0.10D + 0.05D * k) * hh,
                    1.0F, 0.86F, 0.62F, alpha * k, fwd);
        }
        // 发射：橙色束流从炮口沿画里的弹道飞向命中点
        if (fireAge >= 0.0D) {
            double p = Mth.clamp((float) (fireAge / Math.max(1.0D, fall)), 0.0F, 1.0F);
            double[] end = lerp3(muzzle, impact, p);
            beamLayers(beam, matrix, c, r, u, muzzle, end, 0.040D * hh, ORANGE,
                    alpha * 0.85F, fwd);
            if (p > 0.02D) {
                // 弹芯：越飞越小，尾部一小段白热
                double[] coreTail = lerp3(muzzle, impact, Math.max(0.0D, p - 0.05D));
                beamLayers(beam, matrix, c, r, u, coreTail, end, 0.012D * hh, WHITE,
                        alpha * 0.80F, fwd);
                glowQuad(glow, matrix, end, r, u,
                        Mth.lerp((float) p, 0.040F, 0.022F) * hh,
                        1.0F, 0.88F, 0.60F, alpha * 0.95F, fwd);
            }
        }
        // 命中：画里的爆点被拉开后露出来，再叠白闪 + 双环
        if (impactAge >= 4.0D) {
            impactBurst(lines, glow, matrix, impact, r, u, hh, (float) (impactAge - 4.0D),
                    ORANGE, alpha, fwd);
        }
    }

    private static void renderLanceStyle(VertexConsumer lines, VertexConsumer glow, VertexConsumer beam,
                                         Matrix4f matrix, double[] c, double[] r, double[] u,
                                         double hw, double hh, double[] muzzle, double[] impact,
                                         float charge, double fireAge, float alpha,
                                         double time, double[] fwd,
                                         double u0, double v0, double u1, double v1) {
        chargeGlow(lines, glow, matrix, muzzle, r, u, hh, charge, BLUE, alpha, time, fwd);
        // 五级电磁线圈：从舰体到炮口依次点亮
        double[][] coils = new double[5][];
        for (int i = 0; i < 5; i++) {
            double f = i / 4.0D;
            coils[i] = platePoint(Mth.lerp(f, 0.400D, 0.600D), Mth.lerp(f, 0.440D, 0.530D),
                    c, r, u, hw, hh, u0, v0, u1, v1);
            float lit = Mth.clamp((float) ((charge - i * 0.16D) / 0.20D), 0.0F, 1.0F);
            ellipse(lines, matrix, coils[i], r, u, 0.034D * hh, 0.024D * hh,
                    time * 0.25D + i * 0.7D, BLUE[0], BLUE[1], BLUE[2],
                    alpha * (0.16F + 0.62F * lit), fwd);
            glowQuad(glow, matrix, coils[i], r, u, 0.014D * hh,
                    BLUE[0], BLUE[1], BLUE[2], alpha * lit * 0.55F, fwd);
        }
        if (charge > 0.42F) {
            for (int i = 0; i < 4; i++) {
                crackle(lines, matrix, coils[i], coils[i + 1], r, u,
                        time * 1.3D + i * 2.1D, 0.65F, 0.90F, 1.0F,
                        alpha * (charge - 0.42F) * 0.55F, fwd);
            }
        }
        if (fireAge >= 0.0D) {
            double p = Mth.clamp((float) (fireAge / 9.0D), 0.0F, 1.0F);
            double[] tip = lerp3(muzzle, impact, p);
            beamLayers(beam, matrix, c, r, u, muzzle, tip, 0.032D * hh, BLUE,
                    alpha * 0.90F, fwd);
            double[] coreTail = lerp3(muzzle, impact, Math.max(0.0D, p - 0.12D));
            beamLayers(beam, matrix, c, r, u, coreTail, tip, 0.010D * hh, WHITE,
                    alpha * 0.85F, fwd);
            glowQuad(glow, matrix, tip, r, u, 0.035D * hh,
                    1.0F, 1.0F, 1.0F, alpha * 0.95F, fwd);
        }
        // 发射瞬间：炮口/导轨端头爆一圈蓝白（特写里能直接看到「矛射出去了」）
        if (fireAge >= 0.0D && fireAge < 10.0D) {
            float k = 1.0F - (float) fireAge / 10.0F;
            glowQuad(glow, matrix, muzzle, r, u, (0.08D + 0.04D * k) * hh,
                    0.62F, 0.88F, 1.0F, alpha * k, fwd);
        }
    }

    private static void renderGravityStyle(VertexConsumer lines, VertexConsumer glow, VertexConsumer beam,
                                           Matrix4f matrix, double[] c, double[] r, double[] u,
                                           double hw, double hh, double[] muzzle, double[] impact,
                                           Spec spec, float charge, double fireAge,
                                           float alpha, double time, double[] fwd,
                                           double u0, double v0, double u1, double v1) {
        // 画面里的奇点涡旋：两圈缓慢旋转的椭圆 + 中心脉动
        double[] vortex = platePoint(0.410D, 0.490D, c, r, u, hw, hh, u0, v0, u1, v1);
        double tilt = time * (0.020D + 0.100D * charge);
        ellipse(lines, matrix, vortex, r, u, 0.125D * hh, 0.095D * hh, tilt,
                0.45F, 0.72F, 1.0F, alpha * (0.18F + 0.32F * charge), fwd);
        ellipse(lines, matrix, vortex, r, u, 0.165D * hh, 0.125D * hh, -tilt * 0.7D,
                0.62F, 0.86F, 1.0F, alpha * (0.12F + 0.24F * charge), fwd);
        glowQuad(glow, matrix, vortex, r, u, (0.055D + 0.090D * charge) * hh,
                0.55F, 0.78F, 1.0F, alpha * (0.16F + 0.35F * charge), fwd);

        chargeGlow(lines, glow, matrix, muzzle, r, u, hh, charge, BLUE, alpha, time, fwd);
        // 炮管四段线圈依次点亮（从涡旋到炮口）
        for (int i = 0; i < 4; i++) {
            double f = i / 3.0D;
            double[] coil = platePoint(Mth.lerp(f, 0.560D, 0.835D), 0.490D,
                    c, r, u, hw, hh, u0, v0, u1, v1);
            float lit = Mth.clamp((float) ((charge - i * 0.20D) / 0.24D), 0.0F, 1.0F);
            ellipse(lines, matrix, coil, r, u, 0.032D * hh, 0.032D * hh,
                    time * 0.4D + i, BLUE[0], BLUE[1], BLUE[2],
                    alpha * (0.18F + 0.62F * lit), fwd);
            glowQuad(glow, matrix, coil, r, u, 0.016D * hh,
                    BLUE[0], BLUE[1], BLUE[2], alpha * lit * 0.55F, fwd);
        }
        // 发射瞬间：奇点向外推一圈
        if (fireAge >= 0.0D && fireAge < 14.0D) {
            float k = 1.0F - (float) fireAge / 14.0F;
            ring(lines, matrix, vortex, r, u, (0.12D + 0.020D * fireAge) * hh,
                    BLUE[0], BLUE[1], BLUE[2], alpha * 0.55F * k, fwd);
        }
        if (fireAge >= 0.0D) {
            double p = Mth.clamp((float) (fireAge / 10.0D), 0.0F, 1.0F);
            double[] end = lerp3(muzzle, impact, p);
            beamLayers(beam, matrix, c, r, u, muzzle, end, 0.036D * hh, BLUE,
                    alpha * 0.85F, fwd);
            double[] coreTail = lerp3(muzzle, impact, Math.max(0.0D, p - 0.08D));
            beamLayers(beam, matrix, c, r, u, coreTail, end, 0.011D * hh, WHITE,
                    alpha * 0.80F, fwd);
            glowQuad(glow, matrix, end, r, u,
                    Mth.lerp((float) p, 0.034F, 0.020F) * hh,
                    0.62F, 0.88F, 1.0F, alpha * 0.92F, fwd);
        }
        // 发射瞬间：炮口爆一圈蓝白
        if (fireAge >= 0.0D && fireAge < 10.0D) {
            float k = 1.0F - (float) fireAge / 10.0F;
            glowQuad(glow, matrix, muzzle, r, u, (0.09D + 0.04D * k) * hh,
                    0.58F, 0.85F, 1.0F, alpha * k, fwd);
        }
    }

    private static void renderStormStyle(VertexConsumer lines, VertexConsumer glow, VertexConsumer beam,
                                         Matrix4f matrix, double[] c, double[] r, double[] u,
                                         double hw, double hh, double[] muzzle, double[] chargePoint,
                                         Spec spec, float charge, double elapsed, double impactTick,
                                         float alpha, double time, double[] fwd,
                                         double u0, double v0, double u1, double v1) {
        float[] bolt = "swarm".equals(StrikeProtocols.protocolFor(
                OrbitalStrikeClientState.mode()).id()) ? SWARM_GREEN : CYAN;
        chargeGlow(lines, glow, matrix, chargePoint, r, u, hh, charge, bolt, alpha, time, fwd);
        // 反应堆约束环 + 能量导管：光团从舰体反应堆一路流向炮口
        for (int i = 0; i < 2; i++) {
            ellipse(lines, matrix, chargePoint, r, u,
                    (0.10D + i * 0.05D) * hh, (0.075D + i * 0.035D) * hh,
                    time * (0.25D + 0.55D * charge) + i * 1.2D,
                    bolt[0], bolt[1], bolt[2], alpha * (0.14F + 0.30F * charge), fwd);
        }
        double[] cannonBase = platePoint(0.460D, 0.340D, c, r, u, hw, hh, u0, v0, u1, v1);
        for (int i = 0; i < 3; i++) {
            double f = (time * 0.22D + i / 3.0D) % 1.0D;
            double[] pulse = lerp3(chargePoint, cannonBase, f);
            glowQuad(glow, matrix, pulse, r, u, 0.013D * hh,
                    0.72F, 0.94F, 1.0F, alpha * charge * 0.50F * (1.0F - (float) f * 0.55F), fwd);
        }

        // 发射瞬间：舰体反应堆先爆一圈白蓝光（炮口在特写画外，靠这一下交代「已经开火」）
        double fireAge = elapsed - (impactTick - OrbitalStrikeClientState.fallTicks());
        if (fireAge >= 0.0D && fireAge < 10.0D) {
            float k = 1.0F - (float) fireAge / 10.0F;
            glowQuad(glow, matrix, chargePoint, r, u, (0.10D + 0.06D * k) * hh,
                    0.82F, 0.96F, 1.0F, alpha * k, fwd);
        }
        // 等离子球：炮口周围的电弧
        for (int i = 0; i < 3; i++) {
            double ang = time * 0.7D + i * Math.PI * 2.0D / 3.0D;
            double[] a = add(chargePoint, add(mul(r, Math.cos(ang) * 0.035D * hh),
                    mul(u, Math.sin(ang) * 0.035D * hh)));
            double[] b = add(chargePoint, add(mul(r, Math.cos(ang + 1.9D) * 0.07D * hh),
                    mul(u, Math.sin(ang + 1.9D) * 0.07D * hh)));
            crackle(lines, matrix, a, b, r, u, time * 1.1D + i * 2.3D,
                    0.80F, 0.96F, 1.0F, alpha * (0.18F + 0.55F * charge), fwd);
        }
        // 五道落点：第一个与画里的爆炸重合，后四个在附近，逐 8 tick 落下
        for (int i = 0; i < STORM_IMPACTS.length; i++) {
            double[] point = platePoint(STORM_IMPACTS[i][0], STORM_IMPACTS[i][1],
                    c, r, u, hw, hh, u0, v0, u1, v1);
            double fireAt = impactTick + i * (double) OrbitalStrikeMode.STORM_STAGGER_TICKS;
            double age = elapsed - fireAt;
            if (age < 0.0D) {
                continue;
            }
            double p = Mth.clamp((float) (age / 4.0D), 0.0F, 1.0F);
            double[] tip = lerp3(muzzle, point, p);
            crackle(lines, matrix, muzzle, tip, r, u, time * 1.7D + i * 2.9D,
                    0.88F, 0.98F, 1.0F, alpha * (1.0F - (float) Math.min(1.0D, age / 14.0D)),
                    fwd);
            beamLayers(beam, matrix, c, r, u, muzzle, tip, 0.028D * hh, bolt,
                    alpha * 0.55F, fwd);
            if (age >= 2.0D) {
                impactBurst(lines, glow, matrix, point, r, u, hh, (float) (age - 2.0D),
                        bolt, alpha, fwd);
            }
        }
    }

    /**
     * 行星陨落：星云背景 + 地球 + 会飞、会变小的小行星。
     *
     * <p>小行星从左上向右下的地球飞来，飞行途中线性缩小到原来的 62%（不会小到看不见），
     * 身后拖一条橙红尾焰；命中点在地球朝向来袭方向的表面上，撞击时白闪 + 双层扩散环。
     * 原来那张「小行星特写」不再整张铺屏，只把本体抠出来当 2.5D 精灵。</p>
     */
    private static void renderAsteroidScene(VertexConsumer lines,
                                            MultiBufferSource.BufferSource buffers, Matrix4f matrix,
                                            double[] c, double[] r, double[] u,
                                            double hw, double hh,
                                            double u0, double v0, double u1, double v1,
                                            float alpha, double time, double elapsed,
                                            double lock, double fall, double impactAge,
                                            double[] fwd) {
        // —— 星云背景（P0 的宇宙全景）
        {
            VertexConsumer space = buffers.getBuffer(RT_SPACE);
            texQuad(space, matrix, c, r, u, hw, hh,
                    (float) u0, (float) v0, (float) u1, (float) v1,
                    0.86F, 0.90F, 1.0F, alpha * 0.96F, fwd);
            buffers.endBatch(RT_SPACE);
        }
        // —— 地球（P0 的参考图地球圆盘）：放在右下，露出上半球
        double earthSize = 0.46D * hh;
        double[] earth = platePoint(0.70D, 0.80D, c, r, u, hw, hh, u0, v0, u1, v1);
        {
            VertexConsumer tex = buffers.getBuffer(RT_EARTH_PLATE);
            texQuad(tex, matrix, earth, r, u, earthSize, earthSize,
                    0.0F, 0.0F, 1.0F, 1.0F, 1.0F, 1.0F, 1.0F, alpha, fwd);
            buffers.endBatch(RT_EARTH_PLATE);
        }
        // 大气外晕
        VertexConsumer glow = buffers.getBuffer(RT_GLOW);
        glowQuad(glow, matrix, earth, r, u, earthSize * 1.10D,
                0.36F, 0.66F, 1.0F, alpha * 0.16F, fwd);
        ring(lines, matrix, earth, r, u, earthSize * 1.02D,
                0.45F, 0.72F, 1.0F, alpha * 0.22F, fwd);
        ring(lines, matrix, earth, r, u, earthSize * 1.06D,
                0.30F, 0.55F, 0.95F, alpha * 0.10F, fwd);

        // —— 小行星飞行：从锁定 25% 处就开始朝地球缓缓压过去（不干等），
        //    到命中时正好落到地球表面；全程线性缩小到原来的 62%，不会小到看不见。
        double approachStart = lock * 0.25D;
        double flight = Mth.clamp((float) ((elapsed - approachStart)
                / Math.max(1.0D, (lock + fall) - approachStart)), 0.0F, 1.0F);
        double move = smooth(flight);
        double au = Mth.lerp(move, 0.30D, 0.60D);
        double av = Mth.lerp(move, 0.32D, 0.63D);
        double as = Mth.lerp(move, 0.34D, 0.21D);
        double[] asteroid = platePoint(au, av, c, r, u, hw, hh, u0, v0, u1, v1);

        // 尾焰：沿「终点 → 起点」方向拖一串橙红光团（在岩体后面）
        double du = 0.30D - 0.60D;
        double dv = 0.32D - 0.63D;
        double dl = Math.max(1.0E-6D, Math.hypot(du, dv));
        for (int i = 1; i <= 10; i++) {
            double f = i * 0.016D;
            double[] tp = platePoint(au + du / dl * f, av + dv / dl * f,
                    c, r, u, hw, hh, u0, v0, u1, v1);
            double size = (0.020D + as * 0.16D) * (1.0D - i * 0.06D) * hh;
            glowQuad(glow, matrix, tp, r, u, Math.max(0.002D, size),
                    1.0F, 0.44F, 0.14F, alpha * 0.26F * (1.0F - i / 12.0F), fwd);
        }
        // 碎屑：绕本体向外飘
        for (int i = 0; i < 12; i++) {
            double ang = time * 0.10D + i * 2.399D;
            double rad = (0.26D + 0.10D * (i % 4) + 0.18D * (float) move) * as / 0.34D * hh;
            double[] p = add(asteroid, add(mul(r, Math.cos(ang) * rad), mul(u, Math.sin(ang) * rad)));
            glowQuad(glow, matrix, p, r, u, 0.009D * hh,
                    1.0F, 0.48F, 0.18F,
                    alpha * 0.22F * (0.4F + 0.6F * (0.5F + 0.5F * (float) Math.sin(time * 3.0D + i))),
                    fwd);
        }
        buffers.endBatch(RT_GLOW);

        if (impactAge < 0.0D) {
            // 迎风激波：两条从岩体前缘张开的斜线（朝地球方向）
            double dirU = 0.60D - 0.30D;
            double dirV = 0.63D - 0.32D;
            double dirLen = Math.max(1.0E-6D, Math.hypot(dirU, dirV));
            dirU /= dirLen;
            dirV /= dirLen;
            double[] nose = platePoint(au + dirU * as * 0.75D, av + dirV * as * 0.75D,
                    c, r, u, hw, hh, u0, v0, u1, v1);
            double[] flareA = platePoint(au + dirU * as * 1.55D + 0.020D,
                    av + dirV * as * 1.55D, c, r, u, hw, hh, u0, v0, u1, v1);
            double[] flareB = platePoint(au + dirU * as * 1.55D - 0.020D,
                    av + dirV * as * 1.55D, c, r, u, hw, hh, u0, v0, u1, v1);
            line(lines, matrix, nose, flareA, 1.0F, 0.62F, 0.26F, alpha * 0.30F, fwd);
            line(lines, matrix, nose, flareB, 1.0F, 0.62F, 0.26F, alpha * 0.30F, fwd);

            // 岩体本体（在尾焰之后画，遮住身后的光）；缓慢自转，像真的在翻滚
            double spin = time * 0.12D + move * 1.6D;
            double[] ar = add(mul(r, Math.cos(spin)), mul(u, Math.sin(spin)));
            double[] au2 = add(mul(u, Math.cos(spin)), mul(r, -Math.sin(spin)));
            VertexConsumer cut = buffers.getBuffer(RT_ASTEROID_CUT);
            texQuad(cut, matrix, asteroid, ar, au2, as * hh, as * hh,
                    0.0F, 0.0F, 1.0F, 1.0F, 1.0F, 1.0F, 1.0F, alpha, fwd);
            buffers.endBatch(RT_ASTEROID_CUT);
            // 本体边缘的热辉（在岩体之后，贴边发光）
            VertexConsumer rim = buffers.getBuffer(RT_GLOW);
            glowQuad(rim, matrix, asteroid, r, u, as * hh * 1.20D,
                    1.0F, 0.42F, 0.12F, alpha * 0.16F, fwd);
            buffers.endBatch(RT_GLOW);
        } else {
            // 撞击地球：在地球上的入射点炸开
            double[] hit = platePoint(0.60D, 0.63D, c, r, u, hw, hh, u0, v0, u1, v1);
            VertexConsumer hitGlow = buffers.getBuffer(RT_GLOW);
            impactBurst(lines, hitGlow, matrix, hit, r, u, hh, (float) impactAge,
                    ORANGE, alpha, fwd);
            buffers.endBatch(RT_GLOW);
        }
    }

    // ------------------------------------------------------------------ 共用特效

    private static void chargeGlow(VertexConsumer lines, VertexConsumer glow, Matrix4f matrix,
                                   double[] at, double[] r, double[] u, double hh,
                                   float charge, float[] color, float alpha, double time,
                                   double[] fwd) {
        float pulse = 0.70F + 0.30F * (0.5F + 0.5F * (float) Math.sin(time * 4.2D));
        glowQuad(glow, matrix, at, r, u, (0.020D + 0.060D * charge) * hh,
                color[0], color[1], color[2], alpha * (0.15F + 0.75F * charge) * pulse, fwd);
        ring(lines, matrix, at, r, u, (0.080D - 0.035D * charge) * hh,
                color[0], color[1], color[2], alpha * 0.55F * charge, fwd);
        ring(lines, matrix, at, r, u, (0.045D - 0.018D * charge) * hh,
                1.0F, 1.0F, 1.0F, alpha * 0.70F * charge, fwd);
    }

    private static void impactBurst(VertexConsumer lines, VertexConsumer glow, Matrix4f matrix,
                                    double[] at, double[] r, double[] u, double hh,
                                    float age, float[] color, float alpha, double[] fwd) {
        float fade = Mth.clamp(1.0F - age / 40.0F, 0.0F, 1.0F);
        if (fade <= 0.01F) {
            return;
        }
        float grow = 1.0F - (float) Math.exp(-age / 6.0D);
        glowQuad(glow, matrix, at, r, u, (0.045D + 0.20D * grow) * hh,
                1.0F, 0.92F, 0.78F, alpha * 0.90F * fade, fwd);
        glowQuad(glow, matrix, at, r, u, (0.030D + 0.12D * grow) * hh,
                color[0], color[1], color[2], alpha * 0.65F * fade, fwd);
        ring(lines, matrix, at, r, u, (0.030D + 0.012D * age) * hh,
                1.0F, 1.0F, 1.0F, alpha * 0.75F * fade, fwd);
        ring(lines, matrix, at, r, u, (0.050D + 0.020D * age) * hh,
                color[0], color[1], color[2], alpha * 0.40F * fade, fwd);
    }

    private static void beamLayers(VertexConsumer beam, Matrix4f matrix,
                                   double[] c, double[] r, double[] u,
                                   double[] a, double[] b, double width,
                                   float[] color, float alpha, double[] fwd) {
        if (alpha <= 0.002F || distance(a, b) < 1.0E-4D) {
            return;
        }
        beamQuad(beam, matrix, c, r, u, a, b, width * 2.6D,
                color[0], color[1], color[2], alpha * 0.16F, fwd);
        beamQuad(beam, matrix, c, r, u, a, b, width * 1.25D,
                color[0], color[1], color[2], alpha * 0.40F, fwd);
        beamQuad(beam, matrix, c, r, u, a, b, width * 0.55D,
                1.0F, 1.0F, 1.0F, alpha * 0.82F, fwd);
    }

    private static void beamQuad(VertexConsumer vc, Matrix4f matrix,
                                 double[] c, double[] r, double[] u,
                                 double[] a, double[] b, double width,
                                 float cr, float cg, float cb, float ca, double[] fwd) {
        double ax = dot(sub(a, c), r);
        double ay = dot(sub(a, c), u);
        double bx = dot(sub(b, c), r);
        double by = dot(sub(b, c), u);
        double dx = bx - ax;
        double dy = by - ay;
        double len = Math.hypot(dx, dy);
        if (len < 1.0E-5D) {
            return;
        }
        double px = -dy / len * width * 0.5D;
        double py = dx / len * width * 0.5D;
        double[] p1 = add(c, add(mul(r, ax + px), mul(u, ay + py)));
        double[] p2 = add(c, add(mul(r, ax - px), mul(u, ay - py)));
        double[] p3 = add(c, add(mul(r, bx - px), mul(u, by - py)));
        double[] p4 = add(c, add(mul(r, bx + px), mul(u, by + py)));
        texQuadCorners(vc, matrix, p1, p2, p3, p4,
                0.0F, 0.0F, 0.0F, 1.0F, 1.0F, 1.0F, 1.0F, 0.0F,
                cr, cg, cb, ca, fwd);
    }

    private static void glowQuad(VertexConsumer vc, Matrix4f matrix, double[] at,
                                 double[] r, double[] u, double size,
                                 float cr, float cg, float cb, float ca, double[] fwd) {
        if (ca <= 0.002F) {
            return;
        }
        texQuad(vc, matrix, at, r, u, size, size,
                0.0F, 0.0F, 1.0F, 1.0F, cr, cg, cb, ca, fwd);
    }

    // ------------------------------------------------------------------ 电影板/点映射

    /**
     * 把电影板上的归一化坐标映射到相机平面上的世界点。
     *
     * <p>电影板自身是 billboard，uv 的 (0,0) 是图片左上角；这里把裁切后的 uv 矩形
     * 线性映射到屏幕四角（v 向下 = 屏幕向下），所以炮口/命中点跟着缩放与平移一起走。</p>
     */
    private static double[] platePoint(double u, double v, double[] c,
                                       double[] r, double[] uu, double hw, double hh,
                                       double u0, double v0, double u1, double v1) {
        double fx = (u - u0) / Math.max(1.0E-6D, u1 - u0);
        double fy = (v - v0) / Math.max(1.0E-6D, v1 - v0);
        return add(c, add(mul(r, (fx - 0.5D) * 2.0D * hw),
                mul(uu, (0.5D - fy) * 2.0D * hh)));
    }

    /** 全屏压暗四边形（debugQuads：POSITION_COLOR，透明混合）。 */
    private static void darken(MultiBufferSource.BufferSource buffers, Matrix4f matrix,
                               double[] c, double[] r, double[] u,
                               double hw, double hh, float alpha) {
        if (alpha <= 0.002F) {
            return;
        }
        VertexConsumer vc = buffers.getBuffer(RenderType.debugQuads());
        double[] p1 = add(c, add(mul(r, -hw), mul(u, hh)));
        double[] p2 = add(c, add(mul(r, hw), mul(u, hh)));
        double[] p3 = add(c, add(mul(r, hw), mul(u, -hh)));
        double[] p4 = add(c, add(mul(r, -hw), mul(u, -hh)));
        darkVertex(vc, matrix, p1, alpha);
        darkVertex(vc, matrix, p2, alpha);
        darkVertex(vc, matrix, p3, alpha);
        darkVertex(vc, matrix, p4, alpha);
        buffers.endBatch(RenderType.debugQuads());
    }

    private static void darkVertex(VertexConsumer vc, Matrix4f matrix, double[] p, float alpha) {
        vc.vertex(matrix, (float) p[0], (float) p[1], (float) p[2])
                .color(0.0F, 0.0F, 0.0F, alpha)
                .endVertex();
    }

    /** 相机平面贴图四边形（uv 为图片坐标：v=0 顶、v=1 底）。 */
    private static void texQuad(VertexConsumer vc, Matrix4f matrix, double[] c,
                                double[] r, double[] u, double hw, double hh,
                                float u0, float v0, float u1, float v1,
                                float cr, float cg, float cb, float ca, double[] fwd) {
        double[] p1 = add(c, add(mul(r, -hw), mul(u, hh)));
        double[] p2 = add(c, add(mul(r, hw), mul(u, hh)));
        double[] p3 = add(c, add(mul(r, hw), mul(u, -hh)));
        double[] p4 = add(c, add(mul(r, -hw), mul(u, -hh)));
        texQuadCorners(vc, matrix, p1, p2, p3, p4,
                u0, v0, u1, v0, u1, v1, u0, v1, cr, cg, cb, ca, fwd);
    }

    private static void texQuadCorners(VertexConsumer vc, Matrix4f matrix,
                                       double[] p1, double[] p2, double[] p3, double[] p4,
                                       float u1, float v1, float u2, float v2,
                                       float u3, float v3, float u4, float v4,
                                       float cr, float cg, float cb, float ca, double[] n) {
        texVertex(vc, matrix, p1, u1, v1, cr, cg, cb, ca, n);
        texVertex(vc, matrix, p2, u2, v2, cr, cg, cb, ca, n);
        texVertex(vc, matrix, p3, u3, v3, cr, cg, cb, ca, n);
        texVertex(vc, matrix, p4, u4, v4, cr, cg, cb, ca, n);
    }

    private static void texVertex(VertexConsumer vc, Matrix4f matrix, double[] p,
                                  float u, float v, float cr, float cg, float cb, float ca,
                                  double[] n) {
        vc.vertex(matrix, (float) p[0], (float) p[1], (float) p[2])
                .color(cr, cg, cb, ca).uv(u, v)
                .overlayCoords(OverlayTexture.NO_OVERLAY)
                .uv2(LightTexture.FULL_BRIGHT)
                .normal((float) n[0], (float) n[1], (float) n[2])
                .endVertex();
    }

    // ------------------------------------------------------------------ 线框

    private static void ring(VertexConsumer vc, Matrix4f matrix, double[] c,
                             double[] r, double[] u, double radius,
                             float cr, float cg, float cb, float ca, double[] n) {
        ellipse(vc, matrix, c, r, u, radius, radius, 0.0D, cr, cg, cb, ca, n);
    }

    private static void ellipse(VertexConsumer vc, Matrix4f matrix, double[] c,
                                double[] r, double[] u, double rx, double ry, double tilt,
                                float cr, float cg, float cb, float ca, double[] n) {
        if (ca <= 0.002F) {
            return;
        }
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
            double[] p1 = add(c, add(mul(r, x1 * ct - y1 * st), mul(u, x1 * st + y1 * ct)));
            double[] p2 = add(c, add(mul(r, x2 * ct - y2 * st), mul(u, x2 * st + y2 * ct)));
            line(vc, matrix, p1, p2, cr, cg, cb, ca, n);
        }
    }

    /** 两点之间的锯齿电弧（在相机平面内抖动，每帧重抖）。 */
    private static void crackle(VertexConsumer vc, Matrix4f matrix, double[] a, double[] b,
                                double[] r, double[] u, double seed,
                                float cr, float cg, float cb, float ca, double[] n) {
        if (ca <= 0.002F) {
            return;
        }
        final int segments = 8;
        double[] prev = a;
        for (int i = 1; i <= segments; i++) {
            double t = i / (double) segments;
            double[] p = lerp3(a, b, t);
            if (i < segments) {
                double amp = distance(a, b) * 0.06D * Math.sin(Math.PI * t);
                p = add(p, add(mul(r, Math.sin(seed + i * 2.3D) * amp),
                        mul(u, Math.cos(seed * 1.7D + i * 1.9D) * amp)));
            }
            line(vc, matrix, prev, p, cr, cg, cb, ca, n);
            prev = p;
        }
    }

    private static void line(VertexConsumer vc, Matrix4f matrix, double[] a, double[] b,
                             float cr, float cg, float cb, float ca, double[] n) {
        vc.vertex(matrix, (float) a[0], (float) a[1], (float) a[2])
                .color(cr, cg, cb, ca)
                .normal((float) n[0], (float) n[1], (float) n[2])
                .endVertex();
        vc.vertex(matrix, (float) b[0], (float) b[1], (float) b[2])
                .color(cr, cg, cb, ca)
                .normal((float) n[0], (float) n[1], (float) n[2])
                .endVertex();
    }

    // ------------------------------------------------------------------ 数学

    private static double[] add(double[] a, double[] b) {
        return new double[]{a[0] + b[0], a[1] + b[1], a[2] + b[2]};
    }

    private static double[] sub(double[] a, double[] b) {
        return new double[]{a[0] - b[0], a[1] - b[1], a[2] - b[2]};
    }

    private static double[] mul(double[] a, double k) {
        return new double[]{a[0] * k, a[1] * k, a[2] * k};
    }

    private static double dot(double[] a, double[] b) {
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    }

    private static double distance(double[] a, double[] b) {
        double dx = a[0] - b[0];
        double dy = a[1] - b[1];
        double dz = a[2] - b[2];
        return Math.sqrt(dx * dx + dy * dy + dz * dz);
    }

    private static double[] lerp3(double[] a, double[] b, double t) {
        t = Mth.clamp(t, 0.0D, 1.0D);
        return new double[]{
                a[0] + (b[0] - a[0]) * t,
                a[1] + (b[1] - a[1]) * t,
                a[2] + (b[2] - a[2]) * t};
    }

    private static double smooth(double t) {
        t = Mth.clamp(t, 0.0D, 1.0D);
        return t * t * (3.0D - 2.0D * t);
    }
}
