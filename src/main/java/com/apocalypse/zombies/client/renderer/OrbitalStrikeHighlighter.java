package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.client.OrbitalStrikeClientState;
import com.apocalypse.zombies.item.OrbitalStrikeRemoteItem;
import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.core.BlockPos;
import net.minecraft.util.Mth;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import org.joml.Matrix4f;

import java.util.ArrayList;
import java.util.List;

/**
 * 轨道打击的世界层视觉：选区框、光柱、轨道平台、冲击环、地面裂纹。
 *
 * <ol>
 *   <li><b>选区</b>：手持遥控器时，在准星方块中心画一个空心立方体（边长 = 2 × radius）。
 *       冷却中变红。挂了 {@code AFTER_TRANSLUCENT_BLOCKS} 以被水体/玻璃正确遮挡。</li>
 *   <li><b>光柱</b>：收到 {@code OrbitalStrikePacket} 后，从 Y=320 落下的光束 —— 锁定阶段是
 *       一条自上而下逼近的细柱 + 地面圆环，落地后留下正在冷却的光轴。</li>
 *   <li><b>冲击环 / 冲击壳 / 裂纹</b>（1.9.0）：落地后从落点扩散的发光几何 —— 白热快环、
 *       电青慢浪、向上鼓起的圆柱壳、以及从弹坑边缘向外爬的地面裂缝。</li>
 * </ol>
 *
 * <p><b>为什么用 {@code RenderType.debugQuads()} 而不是 {@link RenderType#lightning()}</b>：
 * 两者顶点格式完全一样（POSITION_COLOR / QUADS，Embeddium 侧没有差别），但 lightning 的输出
 * 目标是<b>天气帧缓冲</b>，而原版只在 {@code rainLevel > 0} 时才把天气缓冲合成到屏幕
 * （{@code LevelRenderer.renderSnowAndRain} 在晴天直接 return）—— 也就是说用 lightning 画的
 * 东西在晴天是隐形的。debugQuads 走主帧缓冲、关剔除、半透明混合，才是这里要的。</p>
 *
 * <p><b>配色</b>：本模组自己的「冷白 + 电青」。所有发光几何都用同一条色带，
 * 与 HUD 的 {@code 0x9BF7FF} 同源。</p>
 */
public final class OrbitalStrikeHighlighter {

    /** 比 VeinMineHighlighter 的 INFLATE 大一点：选区要显眼。 */
    private static final double INFLATE = 0.02D;
    /** 立方体默认颜色（青蓝，物品屏幕色）。 */
    private static final float[] READY = new float[]{0.40F, 0.91F, 0.98F};
    /** 冷却中 / 已锁定的颜色（功能性警告色，不属于打击特效的色板）。 */
    private static final float[] LOCKED = new float[]{0.95F, 0.28F, 0.28F};
    /** 光柱基础半径（格）。实际半径随选区半径缩放，见 {@link #beamRadius(int)}。 */
    private static final double BEAM_RADIUS = 0.7D;
    /** 光柱半径上限（格）—— 半径 64 的选区也不要画成一根 8 格粗的水桶。 */
    private static final double BEAM_RADIUS_MAX = 4.0D;
    /** 光柱顶点高度（Y=320 与配置一致，但客户端不读服务端配置，用常量同步感）。 */
    private static final double BEAM_TOP_Y = 320.0D;
    /** 卫星/轨道平台悬浮在光柱顶上方的高度。 */
    private static final double PLATFORM_HEIGHT = 6.0D;
    /** 宇宙激光的行星全息图：球心离地面多高 / 半径多大（光柱从球心穿过去）。 */
    private static final double PLANET_HEIGHT = 300.0D;
    private static final double PLANET_RADIUS = 55.0D;
    /** 行星陨落的那颗「NASA 行星」：更大更远，斜向陨石从它的方向切进来。 */
    private static final double PLANET_SKY_HEIGHT = 330.0D;
    private static final double PLANET_SKY_RADIUS = 95.0D;
    /** 卫星的绘制比例（1 单位 ≈ 本体半宽）。灵魂机位在 84 格外观测，1.8 刚好占画面一角。 */
    private static final double SATELLITE_SCALE = 1.8D;

    /** 打击特效的识别色（电青）。 */
    private static final float CYAN_R = 0.40F;
    private static final float CYAN_G = 0.91F;
    private static final float CYAN_B = 0.98F;
    /** 冲击环的圆周分段：40 段在 44 格外看不出棱角。 */
    private static final int RING_SEGMENTS = 40;
    /** 地面裂纹条数 / 每条折点数。 */
    private static final int CRACK_COUNT = 10;
    private static final int CRACK_POINTS = 10;
    /** 裂纹完全淡出所需 tick（与余晖 40 tick 错开，让地面在画面里「留疤」更久）。 */
    private static final int CRACK_TICKS = 80;

    /** 裂纹几何缓存：以落点 + 半径为止，一击只算一次（高度查询不算便宜）。 */
    private static BlockPos crackKey;
    private static int crackRadius = -1;
    private static List<List<Vec3>> cracks;

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
        // 与服务端同一个上限（1..96）：选区框画的就是真正会被抹掉的范围
        int radius = Mth.clamp(Config.ORBITAL_STRIKE_RADIUS.get(), 1, 96);
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
        ClientLevel level = minecraft.level;
        if (level == null) {
            return;
        }
        long elapsed = OrbitalStrikeClientState.elapsed();
        int lockTicks = OrbitalStrikeClientState.lockTicks();
        long gameTime = level.getGameTime();
        float partial = event.getPartialTick();

        Vec3 camera = event.getCamera().getPosition();
        PoseStack pose = event.getPoseStack();
        MultiBufferSource.BufferSource buffers = minecraft.renderBuffers().bufferSource();
        pose.pushPose();
        pose.translate(-camera.x, -camera.y, -camera.z);
        Matrix4f matrix = pose.last().pose();
        VertexConsumer lines = buffers.getBuffer(RenderType.lines());

        double cx = target.getX() + 0.5D;
        double cz = target.getZ() + 0.5D;
        double gy = target.getY() + 1.0D;
        // 选区半径 → 光柱半径：大范围打击时束要更粗，否则「范围大」看不出来
        int strikeRadius = OrbitalStrikeClientState.radius();
        double beamR = beamRadius(strikeRadius);

        // LASER 的发射段切到相机相对轨道布景：不让主世界天空/地形与有限视距裁剪
        // 抢走画面。布景完全是客户端几何，地面目标仍用同一个服务器坐标结算。
        if (OrbitalCinematic.isSpaceStage()) {
            float spaceOpacity = OrbitalCinematic.spaceOpacity();
            OrbitalSpaceStage.render(pose, lines, buffers, matrix, gameTime, partial, spaceOpacity);
            // 太空布景完全淡出后才画真实世界的落点效果：背景盒写深度，会把身后的
            // 光柱/弹体整根挡掉 —— 等盒子隐去、再让世界里的那一击接上。
            if (spaceOpacity <= 0.01F) {
                renderFallPhase(pose, lines, buffers, matrix, level, target, cx, cz, gy,
                        beamR, strikeRadius, OrbitalStrikeClientState.mode(), elapsed, lockTicks,
                        gameTime, partial);
            }
            pose.popPose();
            buffers.endBatch(RenderType.debugQuads());
            buffers.endBatch(RenderType.lines());
            return;
        }

        OrbitalStrikeMode mode = OrbitalStrikeClientState.mode();
        // —— 「太空里的东西」：普通模式是轨道平台 + 天穹裂缝；
        //    宇宙激光换成「行星全息图 + 卫星」—— 激光就是从卫星发的，再穿过行星打到地面。
        if (mode == OrbitalStrikeMode.LASER) {
            float lockProgress = Mth.clamp((float) elapsed / Math.max(1, lockTicks), 0.0F, 1.0F);
            long impactAge = OrbitalStrikeClientState.impactAge();
            // 行星图：锁定段淡入，落地后 60 tick 内慢慢熄掉
            float planetAlpha = 0.10F + 0.18F * lockProgress;
            if (impactAge >= 0) {
                planetAlpha *= Mth.clamp(1.0F - impactAge / 60.0F, 0.0F, 1.0F);
            }
            renderPlanet(pose, lines, cx, gy + PLANET_HEIGHT, cz, PLANET_RADIUS,
                    planetAlpha, gameTime + partial);
            // 卫星在光柱烧井的几十秒里会一直挂着，落地 40 tick 后淡出，别一直杵在天上
            float satAlpha = 0.62F;
            if (impactAge >= 0) {
                satAlpha *= Mth.clamp(1.0F - impactAge / 40.0F, 0.0F, 1.0F);
            }
            renderSatellite(pose, lines, cx, OrbitalStrikeMode.LASER.originY() + 6.0D, cz,
                    SATELLITE_SCALE, satAlpha, gameTime + partial);
        } else if (mode == OrbitalStrikeMode.PLANET) {
            // 行星陨落：天边浮起一颗 NASA 风格的行星（大陆 + 极冠 + 大气层）
            float lockProgress = Mth.clamp((float) elapsed / Math.max(1, lockTicks), 0.0F, 1.0F);
            long impactAge = OrbitalStrikeClientState.impactAge();
            float planetAlpha = 0.14F + 0.26F * lockProgress;
            if (impactAge >= 0) {
                planetAlpha *= Mth.clamp(1.0F - impactAge / 50.0F, 0.0F, 1.0F);
            }
            renderPlanetNasa(pose, lines, cx, gy + PLANET_SKY_HEIGHT, cz,
                    PLANET_SKY_RADIUS, planetAlpha, gameTime + partial);
        } else {
            renderPlatform(pose, lines, cx, BEAM_TOP_Y + PLATFORM_HEIGHT, cz, gameTime, partial);
            renderSkyFracture(pose, lines, cx, cz, gameTime, partial, strikeRadius);
        }

        if (elapsed < lockTicks) {
            float progress = Mth.clamp((float) elapsed / Math.max(1, lockTicks), 0.0F, 1.0F);
            renderLockPhase(pose, lines, cx, cz, gy, beamR, strikeRadius, mode, progress, gameTime, partial);
        } else {
            renderFallPhase(pose, lines, buffers, matrix, level, target, cx, cz, gy,
                    beamR, strikeRadius, mode, elapsed, lockTicks, gameTime, partial);
        }

        pose.popPose();
        // 先画面、后画线：两类几何现在都落在主帧缓冲并写深度。先画圆柱面会把同一半径上的
        // 1px 边线挡掉（depth LEQUAL 失败），所以面先落笔、线后落笔，边线还要略微外扩。
        buffers.endBatch(RenderType.debugQuads());
        buffers.endBatch(RenderType.lines());
    }

    /**
     * 锁定阶段（前摇动画）。四条线索一起走：
     * <ol>
     *   <li><b>收拢环</b>：地面上的环从 1.8R 收到 0.95R，进度越满越亮 —— 这是「前摇在推进」的主读数；</li>
     *   <li><b>模式签名</b>：轨道炮一根激光、长矛三根更实的矛线、奇点三圈悬空环、风暴五个落点；</li>
     *   <li><b>平台充能</b>：{@link #renderPlatform} 的核心随进度加速脉动；</li>
     *   <li><b>落点标记</b>：只在自己的模式里出现，避免四种形态互相打架。</li>
     * </ol>
     */
    private static void renderLockPhase(PoseStack pose, VertexConsumer lines,
                                        double cx, double cz, double gy,
                                        double beamR, int strikeRadius,
                                        OrbitalStrikeMode mode, float progress,
                                        long gameTime, float partial) {
        float pulse = 0.55F + 0.45F * Mth.sin((gameTime + partial) * 0.6F);

        // —— 收拢环：前摇动画的主线索
        double ringR = Mth.lerp(progress, strikeRadius * 1.8D, strikeRadius * 0.95D);
        float ringAlpha = (0.18F + 0.62F * progress) * (0.7F + 0.3F * pulse);
        drawCircle(pose, lines, cx, gy + 0.04D, cz, ringR, CYAN_R, CYAN_G, CYAN_B, ringAlpha);
        // 第二圈错相位，随进度一起收紧（「两个环在夹」）
        double outerR = ringR + strikeRadius * (0.30D - 0.24D * progress);
        drawCircle(pose, lines, cx, gy + 0.07D, cz, outerR, CYAN_R, CYAN_G, CYAN_B,
                ringAlpha * 0.40F * (1.0F - pulse));

        switch (mode) {
            case LANCE -> {
                // 长矛：矛尖从平台缓缓向下伸（没有整根激光），沿途三圈是「矛身正在成形」
                double topY = BEAM_TOP_Y + PLATFORM_HEIGHT - 2.0D;
                double tipY = Mth.lerp(progress, BEAM_TOP_Y, BEAM_TOP_Y - 90.0D);
                float a = 0.30F + 0.62F * progress;
                line(pose, lines, cx, topY, cz, cx, tipY, cz, CYAN_R, CYAN_G, CYAN_B, a, 0, -1, 0);
                // 尖端：一小段白热 + 一个亮点
                line(pose, lines, cx, tipY, cz, cx, tipY - 6.0D, cz, 1.0F, 1.0F, 1.0F, 0.9F * progress, 0, -1, 0);
                for (int i = 0; i < 3; i++) {
                    double ry = Mth.lerp(i / 3.0D, tipY, topY);
                    drawCircle(pose, lines, cx, ry, cz, 0.45D + 0.55D * i,
                            CYAN_R, CYAN_G, CYAN_B, 0.30F * progress);
                }
                drawCircle(pose, lines, cx, gy + 0.10D, cz, Math.max(0.8D, beamR * 1.4D),
                        CYAN_R, CYAN_G, CYAN_B, 0.85F * progress);
            }
            case GRAVITY -> {
                // 奇点：三圈倾斜的环绕着一个悬空焦点旋转、收缩（没有激光）
                double focusY = gy + 6.0D + 4.0D * (1.0D - progress);
                double orbit = Mth.lerp(progress, strikeRadius * 1.15D, Math.max(0.8D, strikeRadius * 0.28D));
                for (int ring = 0; ring < 3; ring++) {
                    double tilt = (gameTime + partial) * 0.05D + ring * (Math.PI * 2.0D / 3.0D);
                    drawTiltedRing(pose, lines, cx, focusY, cz, orbit, tilt,
                            CYAN_R, CYAN_G, CYAN_B, 0.35F + 0.45F * progress);
                }
                drawCircle(pose, lines, cx, gy + 0.10D, cz, ringR * 0.55D,
                        CYAN_R, CYAN_G, CYAN_B, 0.55F * progress);
            }
            case STORM -> {
                // 风暴：五个落点各自冒电，相邻落点之间拉出锯齿电弧 —— 一片雷暴在蓄势
                double[][] offsets = OrbitalStrikeMode.stormOffsets(
                        OrbitalStrikeClientState.target(), strikeRadius);
                float a = 0.22F + 0.58F * progress;
                for (double[] offset : offsets) {
                    drawCircle(pose, lines, cx + offset[0], gy + 0.08D, cz + offset[1],
                            Math.max(0.8D, strikeRadius * 0.30D), CYAN_R, CYAN_G, CYAN_B, 0.50F * progress);
                }
                for (int i = 0; i < offsets.length; i++) {
                    double[] p1 = offsets[i];
                    double[] p2 = offsets[(i + 1) % offsets.length];
                    jaggedArc(pose, lines,
                            cx + p1[0], gy + 0.25D, cz + p1[1],
                            cx + p2[0], gy + 0.25D, cz + p2[1],
                            i * 1.7D, gameTime + partial, a * 0.65F);
                }
            }
            case LASER -> {
                // 卫星充能：目标区最大的一圈 + 卫星下方一圈圈收紧的光环
                double targetR = strikeRadius * (1.30D - 0.12D * progress);
                drawCircle(pose, lines, cx, gy + 0.05D, cz, targetR,
                        CYAN_R, CYAN_G, CYAN_B, 0.22F + 0.55F * progress);
                drawCircle(pose, lines, cx, gy + 0.05D, cz, targetR * 0.45D,
                        CYAN_R, CYAN_G, CYAN_B, (0.20F + 0.40F * progress) * pulse);
                double originY = OrbitalStrikeMode.LASER.originY();
                // 卫星下方的充能环：从 14 格收到 5 格
                double chargeR = Mth.lerp(progress, 14.0D, 5.0D);
                drawCircle(pose, lines, cx, originY, cz, chargeR,
                        1.0F, 1.0F, 1.0F, 0.30F + 0.55F * progress);
                drawCircle(pose, lines, cx, originY, cz, chargeR * 1.7D,
                        CYAN_R, CYAN_G, CYAN_B, 0.25F * progress);
                // 最后 30% 出现瞄准细线 —— 已经对准了，只等扣扳机
                if (progress > 0.70F) {
                    float k = (progress - 0.70F) / 0.30F;
                    line(pose, lines, cx, originY, cz, cx, gy, cz,
                            CYAN_R, CYAN_G, CYAN_B, 0.30F * k, 0, -1, 0);
                }
            }
            case PLANET -> {
                // 陨石落点：一圈大准星 + 行星方向一颗正在脱离的亮点
                double targetR = strikeRadius * (1.25D - 0.15D * progress);
                drawCircle(pose, lines, cx, gy + 0.05D, cz, targetR,
                        CYAN_R, CYAN_G, CYAN_B, 0.25F + 0.50F * progress);
                for (int i = 0; i < 4; i++) {
                    double a = i * Math.PI / 2.0D;
                    line(pose, lines,
                            cx + Math.cos(a) * targetR * 0.80D, gy + 0.05D, cz + Math.sin(a) * targetR * 0.80D,
                            cx + Math.cos(a) * targetR * 1.25D, gy + 0.05D, cz + Math.sin(a) * targetR * 1.25D,
                            CYAN_R, CYAN_G, CYAN_B, 0.50F + 0.40F * progress, 0, 1, 0);
                }
                double[] offset = OrbitalStrikeMode.meteorOffset(OrbitalStrikeClientState.target());
                double px = cx + offset[0] * 0.55D;
                double pz = cz + offset[1] * 0.55D;
                double py = gy + PLANET_SKY_HEIGHT - 60.0D;
                drawCircle(pose, lines, px, py, pz, 1.2D + 2.0D * progress,
                        1.0F, 1.0F, 1.0F, 0.20F + 0.70F * progress);
            }
            default -> {
                // 轨道炮：地面瞄准标（同心环 + 四角标）+ 平台下方的弹体充能球 —— 没有激光
                double r1 = strikeRadius * (1.15D - 0.10D * progress);
                drawCircle(pose, lines, cx, gy + 0.05D, cz, r1,
                        CYAN_R, CYAN_G, CYAN_B, 0.30F + 0.45F * progress);
                drawCircle(pose, lines, cx, gy + 0.05D, cz, r1 * 0.55D,
                        CYAN_R, CYAN_G, CYAN_B, (0.22F + 0.42F * progress) * pulse);
                for (int i = 0; i < 4; i++) {
                    double a = i * Math.PI / 2.0D + Math.PI / 4.0D;
                    double ix = cx + Math.cos(a) * r1 * 0.82D;
                    double iz = cz + Math.sin(a) * r1 * 0.82D;
                    double ox = cx + Math.cos(a) * r1 * 1.18D;
                    double oz = cz + Math.sin(a) * r1 * 1.18D;
                    line(pose, lines, ix, gy + 0.05D, iz, ox, gy + 0.05D, oz,
                            CYAN_R, CYAN_G, CYAN_B, 0.45F + 0.40F * progress, 0, 1, 0);
                }
                // 抬头能看到平台下面有一颗弹体在充能
                double chargeR = 0.8D + 2.2D * progress;
                double chargeY = BEAM_TOP_Y + PLATFORM_HEIGHT - 1.6D;
                for (int i = 0; i < 3; i++) {
                    drawTiltedRing(pose, lines, cx, chargeY, cz, chargeR,
                            i * Math.PI / 3.0D + (gameTime + partial) * 0.10D,
                            1.0F, 1.0F, 1.0F, 0.55F * progress);
                }
            }
        }
    }

    /** 一段锯齿电弧：两端固定、中间随机偏移，随时间抖动（风暴的地面放电）。 */
    private static void jaggedArc(PoseStack pose, VertexConsumer buffer,
                                  double x1, double y1, double z1,
                                  double x2, double y2, double z2,
                                  double seed, double time, float alpha) {
        int segments = 8;
        double prevX = x1;
        double prevY = y1;
        double prevZ = z1;
        for (int i = 1; i <= segments; i++) {
            double t = i / (double) segments;
            double x = Mth.lerp(t, x1, x2);
            double y = Mth.lerp(t, y1, y2);
            double z = Mth.lerp(t, z1, z2);
            if (i < segments) {
                double jitter = Math.sin(t * Math.PI) * 1.1D;
                x += Math.sin(seed + i * 2.1D + time * 0.5D) * jitter;
                z += Math.cos(seed * 1.3D + i * 1.9D + time * 0.4D) * jitter;
            }
            line(pose, buffer, prevX, prevY, prevZ, x, y, z, CYAN_R, CYAN_G, CYAN_B, alpha, 0, -1, 0);
            prevX = x;
            prevY = y;
            prevZ = z;
        }
    }

    /** 一道锯齿闪电：两端固定在轴上、中间抖动，从 {@code topY} 打到 {@code bottomY}。 */
    private static void jaggedBolt(PoseStack pose, VertexConsumer buffer,
                                   double cx, double cz, double topY, double bottomY,
                                   double time, double seed, float alpha) {
        int segments = 14;
        double prevX = cx;
        double prevY = topY;
        double prevZ = cz;
        for (int i = 1; i <= segments; i++) {
            double t = i / (double) segments;
            double y = Mth.lerp(t, topY, bottomY);
            double jitter = Math.sin(t * Math.PI) * 2.4D;
            double x = cx + Math.sin(seed + i * 2.3D + time * 0.9D) * jitter;
            double z = cz + Math.cos(seed * 1.3D + i * 1.9D + time * 0.7D) * jitter;
            line(pose, buffer, prevX, prevY, prevZ, x, y, z, CYAN_R, CYAN_G, CYAN_B, alpha, 0, -1, 0);
            prevX = x;
            prevY = y;
            prevZ = z;
        }
        drawCircle(pose, buffer, cx, bottomY, cz, 0.85D, 1.0F, 1.0F, 1.0F, alpha);
    }

    /** 一个绕 X 轴倾斜 {@code phase} 弧度的圆环（奇点的轨道环）。 */
    private static void drawTiltedRing(PoseStack pose, VertexConsumer buffer,
                                       double cx, double cy, double cz,
                                       double radius, double phase,
                                       float r, float g, float b, float a) {
        int segments = 24;
        double sinPhase = Math.sin(phase);
        double cosPhase = Math.cos(phase);
        for (int i = 0; i < segments; i++) {
            double a1 = i * Math.PI * 2.0D / segments;
            double a2 = (i + 1) * Math.PI * 2.0D / segments;
            line(pose, buffer,
                    cx + Math.cos(a1) * radius,
                    cy + Math.sin(a1) * radius * sinPhase,
                    cz + Math.sin(a1) * radius * cosPhase,
                    cx + Math.cos(a2) * radius,
                    cy + Math.sin(a2) * radius * sinPhase,
                    cz + Math.sin(a2) * radius * cosPhase,
                    r, g, b, a, 0, 1, 0);
        }
    }

    /** 下落 / 落地 / 余晖阶段。 */
    private static void renderFallPhase(PoseStack pose, VertexConsumer lines,
                                        MultiBufferSource.BufferSource buffers, Matrix4f matrix,
                                        ClientLevel level, BlockPos target,
                                        double cx, double cz, double gy,
                                        double beamR, int strikeRadius, OrbitalStrikeMode mode,
                                        long elapsed, int lockTicks,
                                        long gameTime, float partial) {
        long fallElapsed = elapsed - lockTicks;
        int fallTicks = OrbitalStrikeClientState.fallTicks();
        float fall = Mth.clamp((float) fallElapsed / fallTicks, 0.0F, 1.0F);
        // 余晖衰减（落地后 40 tick 内从 1 缩到 0）
        float glow = fall >= 1.0F
                ? Mth.clamp(1.0F - (float) (fallElapsed - fallTicks)
                / OrbitalStrikeClientState.AFTERGLOW_TICKS, 0.0F, 1.0F)
                : 1.0F;
        // 弹体/矛尖的「头」：从 Y=320 往下走到地面
        double headY = Mth.lerp(fall, BEAM_TOP_Y, gy);

        // —— 四种模式四套形态：炮弹 / 长矛 / 奇点 / 闪电 / 宇宙激光 —— 不再共用一根激光柱
        switch (mode) {
            case GRAVITY -> renderSingularityFall(pose, lines, cx, cz, gy, headY, fall,
                    strikeRadius, gameTime, partial);
            case LANCE -> renderSpearFall(pose, lines, buffers, matrix, cx, cz, headY, fall, gameTime, partial);
            case STORM -> renderStormFall(pose, lines, cx, cz, gy, fallElapsed, fallTicks,
                    strikeRadius, gameTime, partial);
            case LASER -> renderLaserFall(pose, lines, buffers, matrix, cx, cz, gy,
                    strikeRadius, gameTime, partial);
            case PLANET -> renderMeteorFall(pose, lines, buffers, matrix, cx, cz, gy,
                    fall, strikeRadius, target, gameTime, partial);
            default -> renderShellFall(pose, lines, buffers, matrix, cx, cz, headY, fall,
                    strikeRadius, gameTime, partial);
        }

        // —— 落地形态同样按模式分
        long impactAge = OrbitalStrikeClientState.impactAge();
        if (impactAge >= 0) {
            float age = impactAge + partial;
            VertexConsumer quads = buffers.getBuffer(RenderType.debugQuads());
            switch (mode) {
                case LANCE -> renderLanceImpact(quads, matrix, cx, gy, cz, beamR, strikeRadius, age);
                case GRAVITY -> renderImplosion(quads, matrix, cx, gy, cz, beamR, strikeRadius, age);
                case STORM -> renderStormImpact(quads, lines, matrix, cx, gy, cz, beamR,
                        strikeRadius, age, target, pose, gameTime, partial);
                case LASER -> renderLaserImpact(quads, matrix, cx, gy, cz, strikeRadius, age);
                default -> {
                    renderImpactRings(quads, matrix, cx, gy, cz, beamR, strikeRadius, age, glow);
                    renderCracks(quads, matrix, level, target, strikeRadius, age);
                }
            }
        }
    }

    /**
     * 轨道炮的下落：一颗<b>动能弹</b>，不是激光。
     *
     * <p>弹体是一个短粗的发光圆柱（外壳）+ 头部三圈十字环（球感）+ 向上拖出的一串尾迹环。
     * 从地面抬头看是「一个东西在掉下来」，而不是「一道光一直照着地面」——
     * 这是它和长矛/风暴最直观的区别。</p>
     */
    private static void renderShellFall(PoseStack pose, VertexConsumer lines,
                                        MultiBufferSource.BufferSource buffers, Matrix4f matrix,
                                        double cx, double cz, double headY, float fall,
                                        int strikeRadius, long gameTime, float partial) {
        long impactAge = OrbitalStrikeClientState.impactAge();
        int digTicks = OrbitalStrikeClientState.estimateDigTicks();
        double shellY = headY;
        float life = 1.0F;
        if (impactAge >= 0) {
            // 落地后弹体**不消失**：跟着井深一路下钻 —— 与服务端的整列挖掘同速
            // （每 tick 4000 格，一层是 (2r+1)² 格），下到世界底层（虚空）才熄。
            double cellsPerLayer = (2.0D * strikeRadius + 1.0D) * (2.0D * strikeRadius + 1.0D);
            double depth = impactAge * 4000.0D / Math.max(1.0D, cellsPerLayer);
            ClientLevel level = Minecraft.getInstance().level;
            double floorY = level == null ? headY - 384.0D : level.getMinBuildHeight();
            shellY = Math.max(floorY, headY - depth);
            // 前 80% 满亮度，最后 20% 收 —— 和宇宙激光同一套节奏
            float fadeStart = digTicks * 0.8F;
            life = Mth.clamp(1.0F - (impactAge - fadeStart) / Math.max(1.0F, digTicks - fadeStart),
                    0.0F, 1.0F);
            if (life <= 0.01F) {
                return;
            }
        }
        double shellR = Math.max(1.1D, strikeRadius * 0.20D);
        VertexConsumer quads = buffers.getBuffer(RenderType.debugQuads());
        // 弹体外壳：底边跟着弹体走（落地后就是井底）
        cylinderWall(quads, matrix, cx, shellY, cz, shellR, 5.5D, 1.0F, 0.96F, 0.88F, 0.95F * life, 12);
        cylinderWall(quads, matrix, cx, shellY, cz, shellR * 1.45D, 3.6D,
                CYAN_R, CYAN_G, CYAN_B, 0.30F * life, 12);
        // 尾迹：一串越来越小的环往上拖（读作「大气被烧出来的尾」）
        for (int i = 1; i <= 7; i++) {
            double y = shellY + 6.0D + i * 4.0D;
            double r = Math.max(0.12D, shellR * (1.15D - i * 0.13D));
            drawCircle(pose, lines, cx, y, cz, r, CYAN_R, CYAN_G, CYAN_B,
                    0.38F * (1.0F - i / 8.0F) * life);
        }
        // 头部三圈：给弹体一点体积感
        for (int i = 0; i < 3; i++) {
            drawTiltedRing(pose, lines, cx, shellY + 2.5D, cz, shellR * 1.2D,
                    i * Math.PI / 3.0D + (gameTime + partial) * 0.08D,
                    1.0F, 1.0F, 1.0F, 0.55F * life);
        }
        drawCircle(pose, lines, cx, shellY, cz, shellR * 0.9D, 1.0F, 1.0F, 1.0F, 0.85F * life);
    }

    /**
     * 天基长矛的下落：一根<b>上宽下尖的四面锥</b>，尖端朝下扎。
     *
     * <p>没有圆柱光柱 —— 矛身是实心渐收的几何，外加一条细芯线与沿矛身盘旋的能量环。
     * 落地后由 {@link #renderLanceImpact} 接成一根继续向下的锥形穿刺。</p>
     */
    private static void renderSpearFall(PoseStack pose, VertexConsumer lines,
                                        MultiBufferSource.BufferSource buffers, Matrix4f matrix,
                                        double cx, double cz, double headY, float fall,
                                        long gameTime, float partial) {
        if (fall >= 0.999F) {
            return;
        }
        double topY = headY + 52.0D;
        double topR = 0.55D;
        double tipR = 0.02D;
        VertexConsumer quads = buffers.getBuffer(RenderType.debugQuads());
        // 四个侧面：上宽下尖（QUADS 关剔除，绕序不影响可见性）
        for (int i = 0; i < 4; i++) {
            double a1 = i * Math.PI / 2.0D;
            double a2 = (i + 1) * Math.PI / 2.0D;
            double c1 = Math.cos(a1);
            double s1 = Math.sin(a1);
            double c2 = Math.cos(a2);
            double s2 = Math.sin(a2);
            quad(quads, matrix,
                    cx + c1 * topR, topY, cz + s1 * topR,
                    cx + c2 * topR, topY, cz + s2 * topR,
                    cx + c2 * tipR, headY, cz + s2 * tipR,
                    cx + c1 * tipR, headY, cz + s1 * tipR,
                    1.0F, 1.0F, 1.0F, 0.85F);
        }
        // 芯线：从尖端一直拖到矛尾之上，像一道被拉长的光
        line(pose, lines, cx, headY, cz, cx, topY + 60.0D, cz, CYAN_R, CYAN_G, CYAN_B, 0.55F, 0, -1, 0);
        // 沿矛身盘旋的能量环
        for (int i = 0; i < 6; i++) {
            double y = headY + 6.0D + i * 8.0D;
            if (y > topY) {
                break;
            }
            double rr = 0.72D + 0.18D * (y - headY) / 52.0D;
            drawCircle(pose, lines, cx, y, cz, rr, CYAN_R, CYAN_G, CYAN_B, 0.30F);
        }
        // 尖端亮点
        drawCircle(pose, lines, cx, headY, cz, 0.5D, 1.0F, 1.0F, 1.0F, 0.95F);
    }

    /**
     * 等离子风暴的下落：五个落点各一道<b>锯齿闪电</b>，逐道错开 2 tick 落下。
     *
     * <p>闪电每帧重新抖动（用时间当相位），所以是「噼啪作响」而不是一根静止的柱子；
     * 两端固定在轴上，中间随机偏移，落点必然精确。</p>
     */
    private static void renderStormFall(PoseStack pose, VertexConsumer lines,
                                        double cx, double cz, double gy,
                                        long fallElapsed, int fallTicks, int strikeRadius,
                                        long gameTime, float partial) {
        double[][] offsets = OrbitalStrikeMode.stormOffsets(
                OrbitalStrikeClientState.target(), strikeRadius);
        for (int i = 0; i < offsets.length; i++) {
            // 五道闪电**分批落地**：第 i 道比第一道晚 i × STORM_STAGGER_TICKS 落地，
            // 所以它的下落窗口整体后移同样的 tick 数（下落段结束后仍在画接下来的几道）。
            double boltFall = Mth.clamp((fallElapsed - i * (double) OrbitalStrikeMode.STORM_STAGGER_TICKS)
                    / fallTicks, 0.0D, 1.0D);
            if (boltFall >= 0.999D) {
                continue;
            }
            double bottom = Mth.lerp(boltFall, BEAM_TOP_Y, gy);
            jaggedBolt(pose, lines, cx + offsets[i][0], cz + offsets[i][1],
                    BEAM_TOP_Y, bottom, gameTime + partial, i * 3.7D, 0.85F);
        }
    }

    /**
     * 宇宙激光的下落 —— 严格说没有「下落」：光速，充能完成的那一帧整根光柱就已经从
     * Y=460 的卫星连到地面。落地后它**不停**：一路往下烧，光柱一直延伸到世界底层，
     * 随着整列挖掘一层层变深，直到井挖穿到虚空才熄灭 —— 「激光不消失，直到虚空」。
     */
    private static void renderLaserFall(PoseStack pose, VertexConsumer lines,
                                        MultiBufferSource.BufferSource buffers, Matrix4f matrix,
                                        double cx, double cz, double gy, int strikeRadius,
                                        long gameTime, float partial) {
        long impactAge = OrbitalStrikeClientState.impactAge();
        int digTicks = OrbitalStrikeClientState.estimateDigTicks();
        // 前 80% 满亮度（一直在烧），最后 20% 才收 —— 对应「井快挖到底了才熄」
        float life;
        if (impactAge < 0) {
            life = 1.0F;
        } else {
            float fadeStart = digTicks * 0.8F;
            life = Mth.clamp(1.0F - (impactAge - fadeStart) / Math.max(1.0F, digTicks - fadeStart),
                    0.0F, 1.0F);
        }
        if (life <= 0.01F) {
            return;
        }
        double originY = OrbitalStrikeMode.LASER.originY();
        // 落地前光柱止于地表；落地后一路延伸到世界底层（被挖开的部分才会露出来）
        double bottomY = gy;
        if (impactAge >= 0) {
            ClientLevel level = Minecraft.getInstance().level;
            if (level != null) {
                bottomY = Math.min(gy, level.getMinBuildHeight());
            }
        }
        double height = originY - bottomY;
        if (height <= 0.5D) {
            return;
        }
        double width = Math.max(1.6D, strikeRadius * 0.10D);
        float pulse = 0.85F + 0.15F * Mth.sin((gameTime + partial) * 1.9F);
        float a = life * pulse;

        VertexConsumer quads = buffers.getBuffer(RenderType.debugQuads());
        // 三层：越里面的越白越实
        cylinderWall(quads, matrix, cx, bottomY, cz, width * 2.4D, height,
                CYAN_R, CYAN_G, CYAN_B, 0.18F * a, 12);
        cylinderWall(quads, matrix, cx, bottomY, cz, width, height,
                CYAN_R, CYAN_G, CYAN_B, 0.55F * a, 12);
        cylinderWall(quads, matrix, cx, bottomY, cz, width * 0.35D, height,
                1.0F, 1.0F, 1.0F, 0.95F * a, 12);

        // 卫星端：星核 + 光晕；地表/井口一个亮点
        drawCircle(pose, lines, cx, originY, cz, 2.6D, 1.0F, 1.0F, 1.0F, a);
        drawCircle(pose, lines, cx, originY, cz, 7.0D, CYAN_R, CYAN_G, CYAN_B, 0.35F * a);
        drawCircle(pose, lines, cx, gy + 0.10D, cz, width * 1.8D, 1.0F, 1.0F, 1.0F, a);
    }

    /**
     * 宇宙激光的落地：三道环一起推开 —— 白热主环 2.4R、电青副环 3.4R、弹坑口余温。
     * 比其它模式都大一圈，因为这是「极强破坏」的那一发。
     */
    private static void renderLaserImpact(VertexConsumer buffer, Matrix4f matrix,
                                          double cx, double gy, double cz,
                                          int strikeRadius, float age) {
        // 白热主环
        float fast = Mth.clamp(age / 16.0F, 0.0F, 1.0F);
        if (fast < 1.0F) {
            double outer = Mth.lerp(fast, 1.0D, strikeRadius * 2.4D);
            double width = 2.0D + 8.0D * fast;
            groundRing(buffer, matrix, cx, gy + 0.10D, cz,
                    Math.max(0.2D, outer - width), outer,
                    1.0F, 1.0F, 1.0F, 0.95F * (1.0F - fast) * (1.0F - fast), 48);
        }
        // 电青副环（更慢、更远）
        float slow = Mth.clamp(age / 40.0F, 0.0F, 1.0F);
        if (slow < 1.0F) {
            double outer = Mth.lerp(slow, 1.0D, strikeRadius * 3.4D);
            double width = 3.0D + 12.0D * slow;
            groundRing(buffer, matrix, cx, gy + 0.04D, cz,
                    Math.max(0.2D, outer - width), outer,
                    CYAN_R, CYAN_G, CYAN_B, 0.50F * (1.0F - slow) * (1.0F - slow), 48);
        }
        // 冲击壳
        if (fast < 1.0F) {
            double radius = Mth.lerp(fast, 1.0D, strikeRadius * 1.15D);
            shell(buffer, matrix, cx, gy, cz, radius, 2.0D + 22.0D * fast,
                    CYAN_R, CYAN_G, CYAN_B, 0.32F * (1.0F - fast), 36);
        }
        // 弹坑口余温
        float glow = Mth.clamp(1.0F - age / 40.0F, 0.0F, 1.0F);
        if (glow > 0.01F) {
            groundRing(buffer, matrix, cx, gy + 0.06D, cz,
                    strikeRadius * 0.95D, strikeRadius * 1.05D,
                    CYAN_R, CYAN_G, CYAN_B, 0.30F * glow, 48);
        }
    }

    /** 奇点的下落：没有光柱，只有一个发光的焦点在下坠，三圈轨道环跟着收。 */
    private static void renderSingularityFall(PoseStack pose, VertexConsumer lines,
                                              double cx, double cz, double gy,
                                              double headY, float fall, int strikeRadius,
                                              long gameTime, float partial) {
        // 落地帧交给 renderImplosion，不再画下坠形态
        if (fall >= 0.999F) {
            return;
        }
        double t = gameTime + partial;
        double orbit = strikeRadius * (0.35D + 0.55D * (1.0D - fall));
        for (int ring = 0; ring < 3; ring++) {
            double tilt = t * 0.09D + ring * (Math.PI * 2.0D / 3.0D);
            drawTiltedRing(pose, lines, cx, headY, cz, orbit, tilt,
                    CYAN_R, CYAN_G, CYAN_B, 0.55F);
        }
        // 下坠的轨迹：一条暗线 + 地面收拢环
        line(pose, lines, cx, BEAM_TOP_Y, cz, cx, headY, cz, CYAN_R, CYAN_G, CYAN_B, 0.18F, 0, -1, 0);
        double groundR = Mth.lerp(fall, strikeRadius * 2.0D, strikeRadius * 0.55D);
        drawCircle(pose, lines, cx, gy + 0.08D, cz, groundR, CYAN_R, CYAN_G, CYAN_B, 0.30F + 0.45F * fall);
        // 焦点
        drawCircle(pose, lines, cx, headY, cz, 0.45D, 1.0F, 1.0F, 1.0F, 0.95F);
    }

    /** 奇点落地：先收（环从 2.2R 收到 0.35R），再炸（白环冲出去）——「塌缩 → 反弹」。 */
    private static void renderImplosion(VertexConsumer buffer, Matrix4f matrix,
                                        double cx, double gy, double cz,
                                        double beamR, int strikeRadius, float age) {
        float in = Mth.clamp(age / 10.0F, 0.0F, 1.0F);
        if (in < 1.0F) {
            double r = Mth.lerp(in, strikeRadius * 2.2D, strikeRadius * 0.35D);
            groundRing(buffer, matrix, cx, gy + 0.04D, cz, Math.max(0.1D, r - 1.6D), r,
                    CYAN_R, CYAN_G, CYAN_B, 0.75F * (1.0F - in), RING_SEGMENTS);
            shell(buffer, matrix, cx, gy, cz, Math.max(0.5D, r), 18.0D * (1.0F - in) + 1.5D,
                    CYAN_R, CYAN_G, CYAN_B, 0.40F * (1.0F - in), 28);
        }
        float out = Mth.clamp((age - 10.0F) / 14.0F, 0.0F, 1.0F);
        if (age >= 10.0F && out < 1.0F) {
            double r = Mth.lerp(out, beamR, strikeRadius * 1.9D);
            groundRing(buffer, matrix, cx, gy + 0.09D, cz,
                    Math.max(beamR * 0.4D, r - (1.2D + 5.0D * out)), r,
                    1.0F, 1.0F, 1.0F, 0.85F * (1.0F - out) * (1.0F - out), RING_SEGMENTS);
        }
    }

    /** 长矛落地：一根穿到地下几十格的细柱 + 一圈小环 —— 「扎穿」而不是「炸开」。 */
    private static void renderLanceImpact(VertexConsumer buffer, Matrix4f matrix,
                                          double cx, double gy, double cz,
                                          double beamR, int strikeRadius, float age) {
        float t = Mth.clamp(age / 16.0F, 0.0F, 1.0F);
        double r = Math.max(0.35D, beamR * 0.35D);
        float a = 0.90F * (1.0F - t);
        // 阶梯收细的三段：读作一根扎进地层的锥形矛（不是一根等粗的柱子）
        cylinderWall(buffer, matrix, cx, gy - 34.0D, cz, r * 0.30D, 26.0D,
                1.0F, 1.0F, 1.0F, a * 0.55F, 8);
        cylinderWall(buffer, matrix, cx, gy - 10.0D, cz, r * 0.70D, 12.0D,
                1.0F, 1.0F, 1.0F, a * 0.75F, 10);
        cylinderWall(buffer, matrix, cx, gy, cz, r * 1.35D, 8.0D,
                1.0F, 1.0F, 1.0F, a, 10);
        // 矛尾的余焰：从地面往上快速缩掉
        cylinderWall(buffer, matrix, cx, gy, cz, r * 0.8D, 14.0D * (1.0F - t),
                CYAN_R, CYAN_G, CYAN_B, 0.40F * (1.0F - t), 8);
        groundRing(buffer, matrix, cx, gy + 0.06D, cz, Math.max(0.2D, r * 2.0D),
                Math.max(0.4D, beamR * 1.4D) + strikeRadius * 0.5D * t,
                1.0F, 1.0F, 1.0F, 0.85F * (1.0F - t) * (1.0F - t), RING_SEGMENTS);
    }

    /** 风暴落地：五个小落点各自一圈环 + 一根短光柱。 */
    private static void renderStormImpact(VertexConsumer buffer, VertexConsumer lines, Matrix4f matrix,
                                          double cx, double gy, double cz,
                                          double beamR, int strikeRadius, float age, BlockPos target,
                                          PoseStack pose, long gameTime, float partial) {
        double[][] offsets = OrbitalStrikeMode.stormOffsets(target, strikeRadius);
        // 与服务端同一个夹取范围：小半径时坑不会小于 2，大半径时封顶 12
        double subR = Mth.clamp(strikeRadius * 0.45D, 2.0D, 12.0D);
        for (int i = 0; i < offsets.length; i++) {
            // 每道闪电有自己的落地时刻：第 i 道在 age = i × STAGGER 才落地
            float boltAge = age - i * (float) OrbitalStrikeMode.STORM_STAGGER_TICKS;
            if (boltAge < 0.0F) {
                continue;
            }
            float t = Mth.clamp(boltAge / 14.0F, 0.0F, 1.0F);
            if (t >= 1.0F) {
                continue;
            }
            double sx = cx + offsets[i][0];
            double sz = cz + offsets[i][1];
            double outer = Mth.lerp(t, Math.max(0.3D, beamR * 0.5D), subR * 1.8D);
            groundRing(buffer, matrix, sx, gy + 0.06D, sz,
                    Math.max(0.1D, outer - (1.0D + 3.0D * t)), outer,
                    CYAN_R, CYAN_G, CYAN_B, 0.70F * (1.0F - t) * (1.0F - t), 24);
            // 闪电残影：从落点往上 14 格，先亮后收（写进 lines 缓冲 —— POSITION_COLOR 不能塞法线）
            jaggedBolt(pose, lines, sx, sz, gy + 14.0D * (1.0F - t), gy,
                    gameTime + partial, i * 3.7D, 0.55F * (1.0F - t));
        }
    }

    /**
     * 落地后的扩散几何 —— 参考包最值得学的一点：冲击波要是「世界里的一个环」，
     * 不是贴在屏幕上的一张图。这里用真正的环形四边形带，半径随时间外扩、宽度变粗、
     * 亮度按 (1-t)² 衰减；再加一面向上鼓起的圆柱壳，做出「空气被整片推起来」的体积感。
     */
    private static void renderImpactRings(VertexConsumer buffer, Matrix4f matrix,
                                          double cx, double gy, double cz,
                                          double beamR, int strikeRadius,
                                          float age, float glowAlpha) {
        // —— 电青慢浪：能量本身在铺开（1.4 s）。最宽最淡，先落笔
        float slow = Mth.clamp(age / 28.0F, 0.0F, 1.0F);
        if (slow < 1.0F) {
            double outer = Mth.lerp(slow, beamR, strikeRadius * 2.2D);
            double width = 2.5D + 9.0D * slow;
            groundRing(buffer, matrix, cx, gy + 0.04D, cz,
                    Math.max(0.10D, outer - width), outer,
                    CYAN_R, CYAN_G, CYAN_B, 0.45F * (1.0F - slow) * (1.0F - slow), RING_SEGMENTS);
        }
        // —— 冲击壳：向上鼓起的圆柱墙（空气被整片推起来）
        float fast = Mth.clamp(age / 10.0F, 0.0F, 1.0F);
        if (fast < 1.0F) {
            double radius = Mth.lerp(fast, beamR, strikeRadius * 1.10D);
            double height = 2.0D + 16.0D * fast;
            shell(buffer, matrix, cx, gy, cz, radius, height,
                    CYAN_R, CYAN_G, CYAN_B, 0.32F * (1.0F - fast), 32);
        }
        // —— 白热快环：空气被推开的头一圈（0.5 s 内冲出去）。最亮，最后落笔
        if (fast < 1.0F) {
            double outer = Mth.lerp(fast, beamR, strikeRadius * 1.45D);
            double width = 1.4D + 5.0D * fast;
            groundRing(buffer, matrix, cx, gy + 0.09D, cz,
                    Math.max(beamR * 0.4D, outer - width), outer,
                    1.0F, 1.0F, 1.0F, 0.90F * (1.0F - fast) * (1.0F - fast), RING_SEGMENTS);
        }
        // —— 弹坑口余温环：余晖还在时一直亮着，慢慢熄灭
        if (glowAlpha > 0.01F) {
            double pulse = 1.0D + 0.03D * Math.sin(age * 0.35D);
            groundRing(buffer, matrix, cx, gy + 0.05D, cz,
                    strikeRadius * 0.93D * pulse, strikeRadius * 1.02D * pulse,
                    CYAN_R, CYAN_G, CYAN_B, 0.30F * glowAlpha, RING_SEGMENTS);
        }
    }

    // ---------------------------------------------------------------- 裂纹

    /**
     * 地面裂纹：从方形弹坑的边缘向外爬的发光裂缝。几何只算一次（按落点缓存），
     * 之后只做「生长 / 淡出」的时间动画 —— 每帧重算高度查询会明显掉帧。
     */
    private static void renderCracks(VertexConsumer buffer, Matrix4f matrix,
                                     ClientLevel level, BlockPos target, int radius, float age) {
        float reveal = Mth.clamp(age / 10.0F, 0.0F, 1.0F);
        float fade = age < 24.0F ? 1.0F : Mth.clamp(1.0F - (age - 24.0F) / CRACK_TICKS, 0.0F, 1.0F);
        if (fade <= 0.01F) {
            return;
        }
        List<List<Vec3>> all = crackGeometry(level, target, radius);
        for (int c = 0; c < all.size(); c++) {
            List<Vec3> points = all.get(c);
            // 每条裂纹错开一点起裂，像真的从中心一路裂过去
            float grown = Mth.clamp((reveal - c * 0.02F) / 0.8F, 0.0F, 1.0F);
            if (grown <= 0.0F) {
                continue;
            }
            int last = (int) (grown * (points.size() - 1));
            for (int i = 0; i < last; i++) {
                Vec3 p = points.get(i);
                Vec3 q = points.get(i + 1);
                double t = i / (double) (points.size() - 1);
                double width = 0.26D * (1.0D - 0.65D * t);
                // 先铺一层宽的弱光，再压一条细的亮芯 —— 加色叠加出「裂口里在发光」
                ribbon(buffer, matrix, p, q, width * 3.0D, CYAN_R, CYAN_G, CYAN_B, 0.16F * fade);
                ribbon(buffer, matrix, p, q, width, 1.0F, 1.0F, 1.0F, 0.52F * fade);
            }
        }
    }

    private static List<List<Vec3>> crackGeometry(ClientLevel level, BlockPos target, int radius) {
        if (cracks != null && target.equals(crackKey) && radius == crackRadius) {
            return cracks;
        }
        List<List<Vec3>> out = new ArrayList<>(CRACK_COUNT);
        // 用落点坐标做种子：同一击每帧的裂纹长得一模一样，换个落点就换一套
        RandomSource random = RandomSource.create(target.asLong() * 0x9E3779B97F4A7C15L);
        double cx = target.getX() + 0.5D;
        double cz = target.getZ() + 0.5D;
        int baseY = target.getY() + 1;
        for (int i = 0; i < CRACK_COUNT; i++) {
            double angle = (i + (random.nextFloat() - 0.5F) * 0.5F)
                    * (Math.PI * 2.0D / CRACK_COUNT);
            double cos = Math.cos(angle);
            double sin = Math.sin(angle);
            // 方形弹坑的边界距离：沿这个方向走多远才出坑（对角线上更远）
            double rim = radius / Math.max(1.0E-4D, Math.max(Math.abs(cos), Math.abs(sin)));
            double start = rim * 1.02D + 0.7D;
            double length = rim * (0.28D + random.nextDouble() * 0.34D);
            double phase = random.nextDouble() * Math.PI * 2.0D;
            List<Vec3> points = new ArrayList<>(CRACK_POINTS);
            for (int k = 0; k < CRACK_POINTS; k++) {
                double t = k / (double) (CRACK_POINTS - 1);
                double radial = start + length * t;
                // 横向抖动 + 越远越收敛（裂纹从边缘散开、末端收尖）
                double lateral = Math.sin(t * 4.4D + phase) * (1.0D - t) * 1.5D
                        + Math.sin(t * 9.7D + phase * 2.0D) * 0.4D;
                double x = cx + cos * radial - sin * lateral;
                double z = cz + sin * radial + cos * lateral;
                double y = level.getHeight(Heightmap.Types.MOTION_BLOCKING, Mth.floor(x), Mth.floor(z)) + 0.06D;
                // 别顺着山爬：裂缝贴着落点附近的原始地表
                y = Mth.clamp(y, baseY - 2.0D, baseY + 7.0D);
                points.add(new Vec3(x, y, z));
            }
            out.add(points);
        }
        cracks = out;
        crackKey = target.immutable();
        crackRadius = radius;
        return out;
    }

    // ---------------------------------------------------------------- 轨道平台 / 天穹

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
            int segments = 24;
            for (int i = 0; i < segments; i++) {
                double a1 = i * Math.PI * 2.0D / segments;
                double a2 = (i + 1) * Math.PI * 2.0D / segments;
                line(pose, buffer,
                        cx + Math.cos(a1) * radius, cy + Math.sin(a1 * 2.0D + phase) * 0.8D, cz + Math.sin(a1) * radius,
                        cx + Math.cos(a2) * radius, cy + Math.sin(a2 * 2.0D + phase) * 0.8D, cz + Math.sin(a2) * radius,
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
                line(pose, buffer,
                        cx + Math.cos(a1) * radius, cy + Math.sin(a1 * 3.0D + phase) * 0.5D, cz + Math.sin(a1) * radius,
                        cx + Math.cos(a2) * radius, cy + Math.sin(a2 * 3.0D + phase) * 0.5D, cz + Math.sin(a2) * radius,
                        0.45F, 0.80F, 1.0F, 0.35F, 0, 1, 0);
            }
        }
    }

    /**
     * 行星全息图：一圈圈**纬线 + 经线**组成的线框球，光柱从球心穿过去 ——
     * 「从外太空穿过行星打到地面」的那张图。整球缓慢自转，颜色沿用打击的电青。
     *
     * <p>纯线框、不写深度冲突（`RenderType.lines` 不写深度），所以不会挡住后面的光柱。</p>
     */
    private static void renderPlanet(PoseStack pose, VertexConsumer buffer,
                                     double cx, double cy, double cz, double radius,
                                     float alpha, double time) {
        if (alpha <= 0.01F) {
            return;
        }
        // 五条纬线（-60° / -30° / 赤道 / +30° / +60°）
        for (int lat = -2; lat <= 2; lat++) {
            double phi = lat * (Math.PI / 6.0D);
            double r = radius * Math.cos(phi);
            double y = cy + radius * Math.sin(phi);
            drawCircle(pose, buffer, cx, y, cz, r, CYAN_R, CYAN_G, CYAN_B, alpha * 0.55F);
        }
        // 十二条经线（包含 Y 轴的大圆，整体绕 Y 轴慢转）
        int meridians = 12;
        int segments = 32;
        double spin = time * 0.02D;
        for (int m = 0; m < meridians; m++) {
            double theta = spin + m * Math.PI / meridians;
            double cosT = Math.cos(theta);
            double sinT = Math.sin(theta);
            for (int i = 0; i < segments; i++) {
                double a1 = i * Math.PI * 2.0D / segments;
                double a2 = (i + 1) * Math.PI * 2.0D / segments;
                double c1 = Math.cos(a1);
                double c2 = Math.cos(a2);
                line(pose, buffer,
                        cx + c1 * cosT * radius, cy + Math.sin(a1) * radius, cz + c1 * sinT * radius,
                        cx + c2 * cosT * radius, cy + Math.sin(a2) * radius, cz + c2 * sinT * radius,
                        CYAN_R, CYAN_G, CYAN_B, alpha * 0.30F, 0, 1, 0);
            }
        }
    }

    /**
     * NASA 风格的行星：密集经纬网 + 绿色大陆斑块 + 白色极冠 + 大气层外晕。
     * 和宇宙激光那张纯线框全息图不同 —— 这张有「地表」的层次。
     */
    private static void renderPlanetNasa(PoseStack pose, VertexConsumer buffer,
                                         double cx, double cy, double cz, double radius,
                                         float alpha, double time) {
        if (alpha <= 0.01F) {
            return;
        }
        double spin = time * 0.012D;
        // 9 条纬线：赤道偏青、两极偏白（极冠）
        for (int lat = -4; lat <= 4; lat++) {
            double phi = lat * (Math.PI / 10.0D);
            double r = radius * Math.cos(phi);
            double y = cy + radius * Math.sin(phi);
            float polar = Math.abs(lat) / 4.0F;
            drawCircle(pose, buffer, cx, y, cz, r,
                    Mth.lerp(polar, CYAN_R, 1.0F),
                    Mth.lerp(polar, CYAN_G, 1.0F),
                    Mth.lerp(polar, CYAN_B, 1.0F),
                    alpha * 0.55F);
        }
        // 18 条经线
        int meridians = 18;
        int segments = 36;
        for (int m = 0; m < meridians; m++) {
            double theta = spin + m * Math.PI / meridians;
            double cosT = Math.cos(theta);
            double sinT = Math.sin(theta);
            for (int i = 0; i < segments; i++) {
                double a1 = i * Math.PI * 2.0D / segments;
                double a2 = (i + 1) * Math.PI * 2.0D / segments;
                double c1 = Math.cos(a1);
                double c2 = Math.cos(a2);
                line(pose, buffer,
                        cx + c1 * cosT * radius, cy + Math.sin(a1) * radius, cz + c1 * sinT * radius,
                        cx + c2 * cosT * radius, cy + Math.sin(a2) * radius, cz + c2 * sinT * radius,
                        CYAN_R, CYAN_G, CYAN_B, alpha * 0.26F, 0, 1, 0);
            }
        }
        // 大陆：6 个斑块（每个是三条平行的纬向短弧）—— 绿色，读作陆地
        RandomSource random = RandomSource.create(0x4E415341L);
        for (int c = 0; c < 6; c++) {
            double lat = -0.8D + random.nextDouble() * 1.6D;
            double lon0 = random.nextDouble() * Math.PI * 2.0D;
            double span = 0.35D + random.nextDouble() * 0.6D;
            for (int k = 0; k < 3; k++) {
                double phi = Mth.clamp(lat + k * 0.075D, -1.3D, 1.3D);
                double rr = radius * Math.cos(phi);
                double y = cy + radius * Math.sin(phi);
                int steps = 9;
                for (int i = 0; i < steps; i++) {
                    double a1 = lon0 + spin + (i / (double) steps) * span;
                    double a2 = lon0 + spin + ((i + 1) / (double) steps) * span;
                    line(pose, buffer,
                            cx + Math.cos(a1) * rr, y, cz + Math.sin(a1) * rr,
                            cx + Math.cos(a2) * rr, y, cz + Math.sin(a2) * rr,
                            0.55F, 0.88F, 0.62F, alpha * 0.80F, 0, 1, 0);
                }
            }
        }
        // 大气层：两圈外晕
        drawCircle(pose, buffer, cx, cy, cz, radius * 1.02D, CYAN_R, CYAN_G, CYAN_B, alpha * 0.50F);
        drawCircle(pose, buffer, cx, cy, cz, radius * 1.07D, CYAN_R, CYAN_G, CYAN_B, alpha * 0.18F);
    }

    /**
     * 行星陨落的陨石：从行星方向**斜着**切进来，头部是一个发光的小柱体 + 三圈光环，
     * 身后拖 12 节越来越小的尾环和一条火线。
     */
    private static void renderMeteorFall(PoseStack pose, VertexConsumer lines,
                                         MultiBufferSource.BufferSource buffers, Matrix4f matrix,
                                         double cx, double cz, double gy,
                                         float fall, int strikeRadius, BlockPos target,
                                         long gameTime, float partial) {
        double[] offset = OrbitalStrikeMode.meteorOffset(target);
        double startX = cx + offset[0];
        double startZ = cz + offset[1];
        double startY = OrbitalStrikeMode.PLANET.originY();
        double hx = Mth.lerp(fall, startX, cx);
        double hy = Mth.lerp(fall, startY, gy);
        double hz = Mth.lerp(fall, startZ, cz);
        double dx = cx - startX;
        double dy = gy - startY;
        double dz = cz - startZ;
        double len = Math.max(1.0E-4D, Math.sqrt(dx * dx + dy * dy + dz * dz));
        dx /= len;
        dy /= len;
        dz /= len;
        double meteorR = Math.max(1.4D, strikeRadius * 0.16D);
        VertexConsumer quads = buffers.getBuffer(RenderType.debugQuads());
        // 弹体 + 头部三圈
        cylinderWall(quads, matrix, hx, hy, hz, meteorR, meteorR * 2.2D,
                1.0F, 0.90F, 0.72F, 0.95F, 10);
        for (int i = 0; i < 3; i++) {
            drawTiltedRing(pose, lines, hx, hy + meteorR, hz, meteorR * 1.4D,
                    i * Math.PI / 3.0D + (gameTime + partial) * 0.20D,
                    1.0F, 1.0F, 1.0F, 0.55F);
        }
        // 尾迹：沿反方向 12 节环
        for (int i = 1; i <= 12; i++) {
            double d = i * (meteorR * 2.2D + 1.0D);
            double tx = hx - dx * d;
            double ty = hy - dy * d;
            double tz = hz - dz * d;
            double rr = Math.max(0.15D, meteorR * (1.25D - i * 0.09D));
            drawCircle(pose, lines, tx, ty, tz, rr, CYAN_R, CYAN_G, CYAN_B,
                    0.55F * (1.0F - i / 14.0F));
        }
        // 火线 + 头部亮点
        line(pose, lines, hx, hy, hz,
                hx - dx * 46.0D, hy - dy * 46.0D, hz - dz * 46.0D,
                1.0F, 0.62F, 0.42F, 0.55F, 0, -1, 0);
        drawCircle(pose, lines, hx, hy, hz, meteorR * 0.9D, 1.0F, 1.0F, 1.0F, 0.92F);
    }

    /**
     * 轨道卫星：本体 + 两片太阳能板 + 天线碟。宇宙激光就是从这里发射的 ——
     * 光柱顶在卫星下方 6 格，抬头能看见「是谁在开火」。
     */
    private static void renderSatellite(PoseStack pose, VertexConsumer buffer,
                                        double cx, double cy, double cz, double scale,
                                        float alpha, double time) {
        if (alpha <= 0.01F) {
            return;
        }
        double s = scale;
        // 本体
        drawCube(pose, buffer, cx - 1.5D * s, cy - 1.0D * s, cz - 1.0D * s,
                cx + 1.5D * s, cy + 1.0D * s, cz + 1.0D * s,
                0.75F, 0.97F, 1.0F, alpha);
        // 两片太阳能板（薄板 + 三条栅线）
        for (int side = -1; side <= 1; side += 2) {
            double x1 = cx + side * 2.4D * s;
            double x2 = cx + side * 6.2D * s;
            double minX = Math.min(x1, x2);
            double maxX = Math.max(x1, x2);
            drawCube(pose, buffer, minX, cy - 0.12D * s, cz - 1.7D * s,
                    maxX, cy + 0.12D * s, cz + 1.7D * s,
                    CYAN_R, CYAN_G, CYAN_B, alpha * 0.75F);
            for (int i = 1; i <= 3; i++) {
                double gx = Mth.lerp(i / 4.0D, minX, maxX);
                line(pose, buffer, gx, cy + 0.13D * s, cz - 1.7D * s,
                        gx, cy + 0.13D * s, cz + 1.7D * s,
                        CYAN_R, CYAN_G, CYAN_B, alpha * 0.45F, 0, 1, 0);
            }
        }
        // 天线碟：朝下的一个小圆 + 十字
        double dishY = cy - 1.6D * s;
        drawCircle(pose, buffer, cx, dishY, cz, 0.9D * s, CYAN_R, CYAN_G, CYAN_B, alpha * 0.8F);
        line(pose, buffer, cx - 0.9D * s, dishY, cz, cx + 0.9D * s, dishY, cz,
                CYAN_R, CYAN_G, CYAN_B, alpha * 0.6F, 0, 1, 0);
        line(pose, buffer, cx, dishY, cz - 0.9D * s, cx, dishY, cz + 0.9D * s,
                CYAN_R, CYAN_G, CYAN_B, alpha * 0.6F, 0, 1, 0);
        // 导航灯：随时间的明暗脉冲
        float blink = 0.35F + 0.65F * (0.5F + 0.5F * (float) Math.sin(time * 0.22D));
        drawCircle(pose, buffer, cx, cy + 1.6D * s, cz, 0.35D * s,
                1.0F, 1.0F, 1.0F, alpha * blink);
    }
    private static void renderSkyFracture(PoseStack pose, VertexConsumer buffer,
                                          double cx, double cz, long gameTime, float partial, int strikeRadius) {
        double skyY = BEAM_TOP_Y + 10.0D;
        double skySpin = (gameTime + partial) * 0.02D;
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

    // ---------------------------------------------------------------- 加色几何

    /**
     * 朝上的圆环带：内圈 → 外圈之间的四边形带。
     * debugQuads 关剔除，绕序不影响可见性（但这里仍按上法线排，便于将来换回剔除型 RenderType）。
     */
    private static void groundRing(VertexConsumer buffer, Matrix4f matrix,
                                   double cx, double cy, double cz,
                                   double inner, double outer,
                                   float r, float g, float b, float a, int segments) {
        double innerR = Math.max(0.02D, inner);
        double outerR = Math.max(innerR + 0.02D, outer);
        for (int i = 0; i < segments; i++) {
            double a1 = i * Math.PI * 2.0D / segments;
            double a2 = (i + 1) * Math.PI * 2.0D / segments;
            double c1 = Math.cos(a1);
            double s1 = Math.sin(a1);
            double c2 = Math.cos(a2);
            double s2 = Math.sin(a2);
            quad(buffer, matrix,
                    cx + c1 * innerR, cy, cz + s1 * innerR,
                    cx + c2 * innerR, cy, cz + s2 * innerR,
                    cx + c2 * outerR, cy, cz + s2 * outerR,
                    cx + c1 * outerR, cy, cz + s1 * outerR,
                    r, g, b, a);
        }
    }

    /**
     * 竖直圆柱壁：底边满亮度、顶边透明（能量往上升就淡掉）。
     * debugQuads 关剔除，单面几何从里外都看得见 —— 不必再补一遍内壁。
     */
    private static void shell(VertexConsumer buffer, Matrix4f matrix,
                              double cx, double cy, double cz,
                              double radius, double height,
                              float r, float g, float b, float a, int segments) {
        double top = cy + height;
        for (int i = 0; i < segments; i++) {
            double a1 = i * Math.PI * 2.0D / segments;
            double a2 = (i + 1) * Math.PI * 2.0D / segments;
            float x1 = (float) (cx + Math.cos(a1) * radius);
            float z1 = (float) (cz + Math.sin(a1) * radius);
            float x2 = (float) (cx + Math.cos(a2) * radius);
            float z2 = (float) (cz + Math.sin(a2) * radius);
            vertex(buffer, matrix, x1, (float) top, z1, r, g, b, 0.0F);
            vertex(buffer, matrix, x2, (float) top, z2, r, g, b, 0.0F);
            vertex(buffer, matrix, x2, (float) cy, z2, r, g, b, a);
            vertex(buffer, matrix, x1, (float) cy, z1, r, g, b, a);
        }
    }

    /** 不透明圆柱壁（光柱本体）：从底到顶同亮度、同颜色。 */
    private static void cylinderWall(VertexConsumer buffer, Matrix4f matrix,
                                     double cx, double bottom, double cz,
                                     double radius, double height,
                                     float r, float g, float b, float a, int segments) {
        double top = bottom + height;
        for (int i = 0; i < segments; i++) {
            double a1 = i * Math.PI * 2.0D / segments;
            double a2 = (i + 1) * Math.PI * 2.0D / segments;
            float x1 = (float) (cx + Math.cos(a1) * radius);
            float z1 = (float) (cz + Math.sin(a1) * radius);
            float x2 = (float) (cx + Math.cos(a2) * radius);
            float z2 = (float) (cz + Math.sin(a2) * radius);
            vertex(buffer, matrix, x1, (float) top, z1, r, g, b, a);
            vertex(buffer, matrix, x2, (float) top, z2, r, g, b, a);
            vertex(buffer, matrix, x2, (float) bottom, z2, r, g, b, a);
            vertex(buffer, matrix, x1, (float) bottom, z1, r, g, b, a);
        }
    }

    /** 贴地飘带（裂纹用）：沿 p→q 铺一条宽 2w 的四边形，法线朝上。 */
    private static void ribbon(VertexConsumer buffer, Matrix4f matrix,
                               Vec3 p, Vec3 q, double halfWidth,
                               float r, float g, float b, float a) {
        double dx = q.x - p.x;
        double dz = q.z - p.z;
        double len = Math.sqrt(dx * dx + dz * dz);
        if (len < 1.0E-4D) {
            return;
        }
        double px = -dz / len * halfWidth;
        double pz = dx / len * halfWidth;
        quad(buffer, matrix,
                p.x + px, p.y, p.z + pz,
                q.x + px, q.y, q.z + pz,
                q.x - px, q.y, q.z - pz,
                p.x - px, p.y, p.z - pz,
                r, g, b, a);
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
