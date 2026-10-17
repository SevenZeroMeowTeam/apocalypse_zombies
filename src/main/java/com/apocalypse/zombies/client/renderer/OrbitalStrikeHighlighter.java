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
    /** 光柱：中心半径（格）。 */
    private static final double BEAM_RADIUS = 0.42D;
    /** 光柱顶点高度（Y=320 与配置一致，但客户端不读服务端配置，用常量同步感）。 */
    private static final double BEAM_TOP_Y = 320.0D;

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

        if (elapsed < lockTicks) {
            // —— 锁定阶段：地面红环闪烁 + 地面上方一小段引线
            float pulse = 0.55F + 0.45F * Mth.sin((gameTime + event.getPartialTick()) * 0.6F);
            drawCircle(pose, buffer, cx, gy + 0.02D, cz, Math.max(1.5D, OrbitalStrikeClientState.radius()),
                    0.95F, 0.28F, 0.28F, 0.55F * pulse);
            // 引线：从目标上方 6 格的一点指向目标
            line(pose, buffer, cx, gy + 6.0D, cz, cx, gy, cz, 0.95F, 0.28F, 0.28F, 0.65F, 0, -1, 0);
        } else {
            // —— 下落 / 余晖阶段
            long fallElapsed = elapsed - lockTicks;
            float fall = Mth.clamp((float) fallElapsed / OrbitalStrikeClientState.FALL_TICKS, 0.0F, 1.0F);
            // 余晖衰减（落地后 40 tick 内从 1 缩到 0）
            float glow = fall >= 1.0F
                    ? Mth.clamp(1.0F - (float) (fallElapsed - OrbitalStrikeClientState.FALL_TICKS)
                    / OrbitalStrikeClientState.AFTERGLOW_TICKS, 0.0F, 1.0F)
                    : 1.0F;
            // 光柱的「头」：从头顶点往下走到地面
            double headY = Mth.lerp(fall, BEAM_TOP_Y, gy);
            // 颜色：下落白热 → 落地后青白
            float wr = Mth.lerp(fall, 1.0F, 0.55F);
            float wg = Mth.lerp(fall, 1.0F, 0.85F);
            float wb = Mth.lerp(fall, 1.0F, 1.0F);
            float alpha = 0.9F * glow;

            // 8 条竖线围成圆柱（BEAM_RADIUS 半径），从 Y=320 到地面
            for (int i = 0; i < 8; i++) {
                double angle = i * Math.PI * 2.0D / 8.0D;
                double bx = cx + Math.cos(angle) * BEAM_RADIUS;
                double bz = cz + Math.sin(angle) * BEAM_RADIUS;
                line(pose, buffer, bx, BEAM_TOP_Y, bz, bx, headY, bz, wr, wg, wb, alpha, 0, -1, 0);
            }
            // 中心一条更亮的芯线（芯色偏青）
            line(pose, buffer, cx, BEAM_TOP_Y, cz, cx, headY, cz, 0.65F, 0.95F, 1.0F, alpha, 0, -1, 0);
            // 头部的横向亮圈（像枪口焰/冲击波）
            drawCircle(pose, buffer, cx, headY, cz, BEAM_RADIUS + 0.6D, 1.0F, 1.0F, 1.0F, alpha * 0.8F);
            // 地面冲击波：落地后扩散
            if (fall >= 1.0F) {
                double shockRadius = BEAM_RADIUS + 1.0D + (1.0D - glow) * OrbitalStrikeClientState.radius() * 1.6D;
                drawCircle(pose, buffer, cx, gy + 0.04D, cz, shockRadius, 0.6F, 0.95F, 1.0F, glow * 0.55F);
            }
        }
        pose.popPose();
        buffers.endBatch(RenderType.lines());
    }

    // ---------------------------------------------------------------- 基础图元

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
