package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.client.OrbitalStrikeClientState;
import com.apocalypse.zombies.item.OrbitalStrikeRemoteItem;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import net.minecraft.client.Minecraft;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.core.BlockPos;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.client.event.RenderLevelStageEvent;

/**
 * 轨道打击的客户端视觉：两层，各自独立开关。
 *
 * <ol>
 *   <li><b>选区</b>：手持遥控器时，在准星方块中心画一个空心立方体（边长 = 2 × radius）。
 *       冷却中变红。挂了 {@code AFTER_TRANSLUCENT_BLOCKS} 以被水体/玻璃正确遮挡。</li>
 *   <li><b>光柱</b>：收到 {@code OrbitalStrikePacket} 后，从 Y=320 落下的光束 —— 锁定阶段是
 *       一条自上而下逼近的细柱 + 地面红环闪烁，落地后变白扩散余晖。这是「从宇宙之外打下来」
 *       的观感担当：竖直的白/青线条比原版粒子更硬朗，而粒子负责柔光。</li>
 * </ol>
 */
public final class OrbitalStrikeHighlighter {

    /** 比 VeinMineHighlighter 的 INFLATE 大一点：选区要显眼。 */
    private static final double INFLATE = 0.02D;
    /** 立方体默认颜色（青蓝，物品屏幕色）。 */
    private static final float[] READY = new float[]{0.40F, 0.91F, 0.98F};
    /** 冷却中 / 已锁定的颜色。 */
    private static final float[] LOCKED = new float[]{0.95F, 0.28F, 0.28F};
    /** 光柱基础半径（格）。实际半径随选区半径缩放，见 {@link #beamRadius(int)}。 */
    private static final double BEAM_RADIUS = 0.7D;
    /** 光柱半径上限（格）—— 半径 64 的选区也不要画成一根 8 格粗的水桶。 */
    private static final double BEAM_RADIUS_MAX = 4.0D;
    /** 光柱顶点高度（Y=320 与配置一致，但客户端不读服务端配置，用常量同步感）。 */
    private static final double BEAM_TOP_Y = 320.0D;
    /** 卫星/轨道平台悬浮在光柱顶上方的高度。 */
    private static final double PLATFORM_HEIGHT = 6.0D;

    private OrbitalStrikeHighlighter() {
    }

    public static void render(RenderLevelStageEvent event) {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_TRANSLUCENT_BLOCKS) {
            return;
        }
        renderBeam(event);          // 先画光柱（深度上它在该画的地方）
        renderSelection(event);     // 再画手持选区
    }

    // ---------------------------------------------------------------- 选区

    private static void renderSelection(RenderLevelStageEvent event) {
        if (!Config.ORBITAL_STRIKE_ENABLED.get()) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        LocalPlayer player = minecraft.player;
        if (player == null || minecraft.level == null || minecraft.options.hideGui) {
            return;
        }
        if (!(player.getMainHandItem().getItem() instanceof OrbitalStrikeRemoteItem)) {
            return;
        }
        if (!(minecraft.hitResult instanceof BlockHitResult hit) || hit.getType() != HitResult.Type.BLOCK) {
            return;
        }
        BlockPos pos = hit.getBlockPos();
        int radius = Mth.clamp(Config.ORBITAL_STRIKE_RADIUS.get(), 1, 16);
        boolean cooling = player.getCooldowns().isOnCooldown(player.getMainHandItem().getItem());
        float[] color = cooling ? LOCKED : READY;

        Vec3 camera = event.getCamera().getPosition();
        PoseStack pose = event.getPoseStack();
        MultiBufferSource.BufferSource buffers = minecraft.renderBuffers().bufferSource();
        VertexConsumer buffer = buffers.getBuffer(RenderType.lines());
        pose.pushPose();
        pose.translate(-camera.x, -camera.y, -camera.z);
        drawCube(pose, buffer, pos.getX() - radius, pos.getY() - radius, pos.getZ() - radius,
                pos.getX() + 1 + radius, pos.getY() + 1 + radius, pos.getZ() + 1 + radius,
                color[0], color[1], color[2], 0.85F);
        pose.popPose();
        buffers.endBatch(RenderType.lines());
    }

    // ---------------------------------------------------------------- 光柱

    private static void renderBeam(RenderLevelStageEvent event) {
        if (!Config.ORBITAL_STRIKE_ENABLED.get() || !OrbitalStrikeClientState.isActive()) {
            return;
        }
        BlockPos target = OrbitalStrikeClientState.target();
        if (target == null) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.level == null) {
            return;
        }
        long elapsed = OrbitalStrikeClientState.elapsed();
        int lockTicks = OrbitalStrikeClientState.lockTicks();
        long gameTime = minecraft.level.getGameTime();

        Vec3 camera = event.getCamera().getPosition();
        PoseStack pose = event.getPoseStack();
        MultiBufferSource.BufferSource buffers = minecraft.renderBuffers().bufferSource();
        VertexConsumer buffer = buffers.getBuffer(RenderType.lines());
        pose.pushPose();
        pose.translate(-camera.x, -camera.y, -camera.z);

        double cx = target.getX() + 0.5D;
        double cz = target.getZ() + 0.5D;
        double gy = target.getY() + 1.0D;
        // 选区半径 → 光柱半径：大范围打击时束要更粗，否则「范围大」看不出来
        int strikeRadius = OrbitalStrikeClientState.radius();
        double beamR = beamRadius(strikeRadius);
        long tick = gameTime;
        float partial = event.getPartialTick();

        // —— 「太空里的东西」：轨道平台从锁定第一帧就悬在光柱顶上。
        // 它不是实体/方块，纯渲染 —— 玩家在哪、瞄哪，平台就飘在哪的正上方。
        renderPlatform(pose, buffer, cx, BEAM_TOP_Y + PLATFORM_HEIGHT, cz, tick, partial);

        // —— 天穹裂缝：Y=330 处一圈大环 + 24 条放射裂纹，缓慢旋转。大范围打击时环也跟着放大。
        {
            double skyY = BEAM_TOP_Y + 10.0D;
            double skySpin = (tick + partial) * 0.02D;
            double skyR = Math.max(40.0D, strikeRadius * 2.5D);
            drawCircle(pose, buffer, cx, skyY, cz, skyR, 0.35F, 0.65F, 1.0F, 0.30F);
            for (int i = 0; i < 24; i++) {
                double a = i * Math.PI * 2.0D / 24.0D + skySpin;
                double r0 = skyR;
                double r1 = skyR * 1.45D + Math.sin(a * 3.0D) * 4.0D;
                line(pose, buffer,
                        cx + Math.cos(a) * r0, skyY + Math.sin(a * 2.0D) * 2.0D, cz + Math.sin(a) * r0,
                        cx + Math.cos(a) * r1, skyY + 3.0D, cz + Math.sin(a) * r1,
                        0.40F, 0.78F, 1.0F, 0.24F, 0, 1, 0);
            }
        }

        if (elapsed < lockTicks) {
            // —— 锁定阶段：地面红环闪烁 + 从 Y=320 射下来的红色激光（the-shooting-star 的标志观感）
            float pulse = 0.55F + 0.45F * Mth.sin((gameTime + partial) * 0.6F);
            drawCircle(pose, buffer, cx, gy + 0.02D, cz, Math.max(1.5D, OrbitalStrikeClientState.radius()),
                    0.95F, 0.28F, 0.28F, 0.55F * pulse);
            // 红激光：一条细红线从天顶笔直落到目标点（锁定期间一直亮着，落地前最亮）
            float laserAlpha = 0.35F + 0.25F * pulse;
            line(pose, buffer, cx, BEAM_TOP_Y, cz, cx, gy, cz, 0.98F, 0.22F, 0.22F, laserAlpha, 0, -1, 0);
            // 激光落点的十字标记（红）
            double markLen = 0.9D;
            line(pose, buffer, cx - markLen, gy + 0.02D, cz, cx + markLen, gy + 0.02D, cz,
                    0.98F, 0.22F, 0.22F, laserAlpha, 0, 1, 0);
            line(pose, buffer, cx, gy + 0.02D, cz - markLen, cx, gy + 0.02D, cz + markLen,
                    0.98F, 0.22F, 0.22F, laserAlpha, 0, 1, 0);
        } else {
            // —— 下落 / 余晖阶段
            long fallElapsed = elapsed - lockTicks;
            int fallTicks = OrbitalStrikeClientState.fallTicks();
            float fall = Mth.clamp((float) fallElapsed / fallTicks, 0.0F, 1.0F);
            // 余晖衰减（落地后 40 tick 内从 1 缩到 0）
            float glow = fall >= 1.0F
                    ? Mth.clamp(1.0F - (float) (fallElapsed - fallTicks)
                    / OrbitalStrikeClientState.AFTERGLOW_TICKS, 0.0F, 1.0F)
                    : 1.0F;
            // 光柱的「头」：从头顶点往下走到地面
            double headY = Mth.lerp(fall, BEAM_TOP_Y, gy);
            // 颜色：下落白热 → 落地后青白
            float wr = Mth.lerp(fall, 1.0F, 0.55F);
            float wg = Mth.lerp(fall, 1.0F, 0.85F);
            float wb = Mth.lerp(fall, 1.0F, 1.0F);
            float alpha = 0.9F * glow;

            // —— 发光光柱：RenderType.lightning（原版闪电同款，additive 发光）。
            // 1.5.0 用 beaconBeam 自建 RenderType 实例，在 Embeddium 的动态
            // buffer 上崩（Not filled all elements of the vertex，SodiumBufferBuilder
            // 对 4 元素格式的 uv2 链有兼容问题）；改用 fixed buffer 的 lightning
            // 类型（POSITION_COLOR 2 元素，原版闪电每帧都在用），双层圆柱叠出辉光。
            double beamHeight = BEAM_TOP_Y - headY;
            if (beamHeight > 0.5D) {
                VertexConsumer beamBuffer = buffers.getBuffer(RenderType.lightning());
                var matrix = pose.last().pose();
                int segments = 10;
                // 内层白热实心 + 外层青色辉光，叠加出「亮得发光」的观感
                for (int layer = 0; layer < 2; layer++) {
                    double lr = layer == 0 ? beamR : beamR * 1.55D;
                    float la = layer == 0 ? alpha : alpha * 0.35F;
                    float cr = layer == 0 ? wr : 0.35F;
                    float cg = layer == 0 ? wg : 0.85F;
                    float cb = layer == 0 ? wb : 1.0F;
                    for (int i = 0; i < segments; i++) {
                        double a1 = i * Math.PI * 2.0D / segments;
                        double a2 = (i + 1) * Math.PI * 2.0D / segments;
                        float x1 = (float) (cx + Math.cos(a1) * lr);
                        float z1 = (float) (cz + Math.sin(a1) * lr);
                        float x2 = (float) (cx + Math.cos(a2) * lr);
                        float z2 = (float) (cz + Math.sin(a2) * lr);
                        beamBuffer.vertex(matrix, x1, (float) BEAM_TOP_Y, z1).color(cr, cg, cb, la).endVertex();
                        beamBuffer.vertex(matrix, x2, (float) BEAM_TOP_Y, z2).color(cr, cg, cb, la).endVertex();
                        beamBuffer.vertex(matrix, x2, (float) headY, z2).color(cr, cg, cb, la).endVertex();
                        beamBuffer.vertex(matrix, x1, (float) headY, z1).color(cr, cg, cb, la).endVertex();
                    }
                }
                buffers.endBatch(RenderType.lightning());
            }

            // 12 条竖线围成圆柱，从 Y=320 到地面（1.2.7：8 边 → 12 边，更圆更粗）
            for (int i = 0; i < 12; i++) {
                double angle = i * Math.PI * 2.0D / 12.0D;
                double bx = cx + Math.cos(angle) * beamR;
                double bz = cz + Math.sin(angle) * beamR;
                line(pose, buffer, bx, BEAM_TOP_Y, bz, bx, headY, bz, wr, wg, wb, alpha, 0, -1, 0);
            }
            // 中心一条更亮的芯线（芯色偏青）
            line(pose, buffer, cx, BEAM_TOP_Y, cz, cx, headY, cz, 0.65F, 0.95F, 1.0F, alpha, 0, -1, 0);

            // 能量环：光柱上每隔 20 格一个会随高度脉动的环（旋转的错觉靠相位差做）
            if (fall < 1.0F) {
                float pulsePhase = (gameTime + partial) * 0.35F;
                for (int ring = 0; ring < 3; ring++) {
                    double ringY = headY + 20.0D + ring * 20.0D;
                    if (ringY > BEAM_TOP_Y) {
                        continue;
                    }
                    double ringR = beamR + 1.2D + 0.5D * (double) Mth.sin(pulsePhase + ring * 1.3F);
                    drawCircle(pose, buffer, cx, ringY, cz, ringR,
                            0.75F, 0.98F, 1.0F, alpha * 0.35F);
                }
            }

            // 头部的横向亮圈（像枪口焰/冲击波）
            drawCircle(pose, buffer, cx, headY, cz, beamR + 0.8D, 1.0F, 1.0F, 1.0F, alpha * 0.8F);
            // 地面冲击波：落地后扩散
            if (fall >= 1.0F) {
                double shockRadius = beamR + 1.2D + (1.0D - glow) * OrbitalStrikeClientState.radius() * 1.8D;
                drawCircle(pose, buffer, cx, gy + 0.04D, cz, shockRadius, 0.6F, 0.95F, 1.0F, glow * 0.55F);
            }
        }
        pose.popPose();
        buffers.endBatch(RenderType.lines());
    }

    /**
     * 「轨道平台」：悬浮在光柱顶上方 6 格的一个发光体 —— 三层套方框（核心 / 外环 / 内环）
     * 加两圈缓慢旋转的环带。不依赖实体或方块，纯线框，所以不会出现在世界存档里。
     */
    private static void renderPlatform(PoseStack pose, VertexConsumer buffer,
                                       double cx, double cy, double cz, long gameTime, float partial) {
        float t = gameTime + partial;
        // 核心：3×3×3 方框，白光
        double core = 1.5D;
        drawCube(pose, buffer, cx - core, cy - core, cz - core, cx + core, cy + core, cz + core,
                0.70F, 0.97F, 1.0F, 0.85F);
        // 中环：半径 3.2，上下交替的两圈（错相，看起来像在转）
        for (int ring = 0; ring < 2; ring++) {
            double phase = t * 0.08D + ring * Math.PI;
            double radius = 3.2D;
            // 圆环的「倾角」用 y 随角度起伏实现：y = cy + sin(angle*2 + phase) * 0.8
            int segments = 24;
            for (int i = 0; i < segments; i++) {
                double a1 = i * Math.PI * 2.0D / segments;
                double a2 = (i + 1) * Math.PI * 2.0D / segments;
                double y1 = cy + Math.sin(a1 * 2.0D + phase) * 0.8D;
                double y2 = cy + Math.sin(a2 * 2.0D + phase) * 0.8D;
                line(pose, buffer,
                        cx + Math.cos(a1) * radius, y1, cz + Math.sin(a1) * radius,
                        cx + Math.cos(a2) * radius, y2, cz + Math.sin(a2) * radius,
                        0.55F, 0.90F, 1.0F, 0.55F, 0, 1, 0);
            }
        }
        // 外环：半径 5.2，缓慢反向旋转 + 更淡
        {
            double phase = -t * 0.05D;
            double radius = 5.2D;
            int segments = 24;
            for (int i = 0; i < segments; i++) {
                double a1 = i * Math.PI * 2.0D / segments;
                double a2 = (i + 1) * Math.PI * 2.0D / segments;
                double y1 = cy + Math.sin(a1 * 3.0D + phase) * 0.5D;
                double y2 = cy + Math.sin(a2 * 3.0D + phase) * 0.5D;
                line(pose, buffer,
                        cx + Math.cos(a1) * radius, y1, cz + Math.sin(a1) * radius,
                        cx + Math.cos(a2) * radius, y2, cz + Math.sin(a2) * radius,
                        0.45F, 0.80F, 1.0F, 0.35F, 0, 1, 0);
            }
        }
    }

    // ---------------------------------------------------------------- 基础图元

    /** 选区半径 → 光柱半径：小范围细束，大范围粗柱（上限 {@link #BEAM_RADIUS_MAX}）。 */
    private static double beamRadius(int strikeRadius) {
        return Math.max(BEAM_RADIUS, Math.min(BEAM_RADIUS_MAX, strikeRadius * 0.12D));
    }

    /** 12 条棱组成的空心立方体。 */
    private static void drawCube(PoseStack pose, VertexConsumer buffer,
                                 double minX, double minY, double minZ,
                                 double maxX, double maxY, double maxZ,
                                 float r, float g, float b, float a) {
        minX -= INFLATE; minY -= INFLATE; minZ -= INFLATE;
        maxX += INFLATE; maxY += INFLATE; maxZ += INFLATE;
        line(pose, buffer, minX, minY, minZ, maxX, minY, minZ, r, g, b, a, 0, -1, 0);
        line(pose, buffer, maxX, minY, minZ, maxX, minY, maxZ, r, g, b, a, 0, -1, 0);
        line(pose, buffer, maxX, minY, maxZ, minX, minY, maxZ, r, g, b, a, 0, -1, 0);
        line(pose, buffer, minX, minY, maxZ, minX, minY, minZ, r, g, b, a, 0, -1, 0);
        line(pose, buffer, minX, maxY, minZ, maxX, maxY, minZ, r, g, b, a, 0, 1, 0);
        line(pose, buffer, maxX, maxY, minZ, maxX, maxY, maxZ, r, g, b, a, 0, 1, 0);
        line(pose, buffer, maxX, maxY, maxZ, minX, maxY, maxZ, r, g, b, a, 0, 1, 0);
        line(pose, buffer, minX, maxY, maxZ, minX, maxY, minZ, r, g, b, a, 0, 1, 0);
        line(pose, buffer, minX, minY, minZ, minX, maxY, minZ, r, g, b, a, -1, 0, 0);
        line(pose, buffer, maxX, minY, minZ, maxX, maxY, minZ, r, g, b, a, 1, 0, 0);
        line(pose, buffer, maxX, minY, maxZ, maxX, maxY, maxZ, r, g, b, a, 1, 0, 0);
        line(pose, buffer, minX, minY, maxZ, minX, maxY, maxZ, r, g, b, a, -1, 0, 0);
    }

    /** 水平圆环：用 32 段折线近似（足够圆，且比真圆省顶点）。 */
    private static void drawCircle(PoseStack pose, VertexConsumer buffer,
                                   double cx, double cy, double cz, double radius,
                                   float r, float g, float b, float a) {
        int segments = 32;
        for (int i = 0; i < segments; i++) {
            double a1 = i * Math.PI * 2.0D / segments;
            double a2 = (i + 1) * Math.PI * 2.0D / segments;
            line(pose, buffer,
                    cx + Math.cos(a1) * radius, cy, cz + Math.sin(a1) * radius,
                    cx + Math.cos(a2) * radius, cy, cz + Math.sin(a2) * radius,
                    r, g, b, a, 0, 1, 0);
        }
    }

    private static void line(PoseStack pose, VertexConsumer buffer,
                             double x1, double y1, double z1,
                             double x2, double y2, double z2,
                             float r, float g, float b, float a,
                             float nx, float ny, float nz) {
        var m = pose.last();
        buffer.vertex(m.pose(), (float) x1, (float) y1, (float) z1)
                .color(r, g, b, a)
                .normal(m.normal(), nx, ny, nz)
                .endVertex();
        buffer.vertex(m.pose(), (float) x2, (float) y2, (float) z2)
                .color(r, g, b, a)
                .normal(m.normal(), nx, ny, nz)
                .endVertex();
    }
}
