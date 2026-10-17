package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.client.OrbitalStrikeClientState;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.network.chat.Component;
import net.minecraft.util.Mth;
import net.minecraftforge.client.event.ViewportEvent;

/**
 * 轨道打击的屏幕级特效：HUD 倒计时、屏幕边缘红晕、落地白闪、镜头震动。
 *
 * <p>这一层与 {@link OrbitalStrikeHighlighter}（世界里的光柱/平台/圆环）互补 ——
 * 那边管「世界里的东西」，这边管「你的屏幕」。落地那一瞬间的白闪 + 镜头抖动
 * 是「被天基炮正面砸中」这件事最直接的观感来源，比粒子便宜得多。</p>
 *
 * <p>全部状态从 {@link OrbitalStrikeClientState} 推算（开始时刻 + 服务端给定的锁定时长），
 * 不另存时间戳，也不用发包。</p>
 */
public final class OrbitalScreenFX {

    /** 落地白闪持续 tick（约 0.3 s）。 */
    private static final int FLASH_TICKS = 6;
    /** 白闪峰值不透明度。 */
    private static final float FLASH_ALPHA = 0.85F;
    /** 镜头震动持续 tick。 */
    private static final int SHAKE_TICKS = 6;
    /** 镜头震动最大偏转角（度）。 */
    private static final float SHAKE_DEGREES = 2.2F;
    /** 白闪/红晕在多少格内全强度，多少格外消失。 */
    private static final double NEAR_RADIUS = 40.0D;
    private static final double FAR_RADIUS = 160.0D;

    private OrbitalScreenFX() {
    }

    // ---------------------------------------------------------------- HUD

    /** 锁定阶段：屏幕中央上方的倒计时数字 + 屏幕四边红晕。挂在 {@code RenderGuiEvent.Post}。 */
    public static void renderHud(GuiGraphics graphics, Minecraft minecraft, float partialTick) {
        if (!OrbitalStrikeClientState.isActive() || !OrbitalStrikeClientState.isLockPhase()) {
            return;
        }
        if (minecraft.options.hideGui || minecraft.player == null) {
            return;
        }
        int width = graphics.guiWidth();
        int height = graphics.guiHeight();

        // —— 屏幕边缘红色脉冲（越接近落地越亮）
        float lockProgress = OrbitalStrikeClientState.lockProgress();
        float pulse = 0.55F + 0.45F * Mth.sin((minecraft.level.getGameTime() + partialTick) * 0.8F);
        float edgeAlpha = (0.10F + 0.20F * lockProgress) * pulse;
        int edgeColor = ((int) (edgeAlpha * 255.0F) << 24) | 0xE02020;
        int edgeWidth = Math.max(6, (int) (width * 0.06F));
        graphics.fill(0, 0, width, edgeWidth, edgeColor);                 // 上
        graphics.fill(0, height - edgeWidth, width, height, edgeColor);   // 下
        graphics.fill(0, 0, edgeWidth, height, edgeColor);                // 左
        graphics.fill(width - edgeWidth, 0, width, height, edgeColor);    // 右

        // —— 中央倒计时：剩余秒数（向上取整），3、2、1 大字
        long remaining = OrbitalStrikeClientState.lockTicks() - OrbitalStrikeClientState.elapsed();
        if (remaining < 0) {
            remaining = 0;
        }
        int seconds = (int) Math.ceil(remaining / 20.0D);
        if (seconds <= 0) {
            return;
        }
        Component text = Component.literal(String.valueOf(seconds));
        PoseStack pose = graphics.pose();
        pose.pushPose();
        pose.translate(width / 2.0F, height * 0.28F, 0.0F);
        float scale = 4.0F;
        pose.scale(scale, scale, 1.0F);
        int textWidth = minecraft.font.width(text);
        // 数字颜色随倒计时从青 → 白 → 红：越接近 0 越危险
        float danger = 1.0F - Mth.clamp((float) remaining / Math.max(1, OrbitalStrikeClientState.lockTicks()), 0.0F, 1.0F);
        int r = (int) Mth.lerp(danger, 120.0F, 255.0F);
        int g = (int) Mth.lerp(danger, 235.0F, 90.0F);
        int b = (int) Mth.lerp(danger, 255.0F, 90.0F);
        int color = 0xFF000000 | (r << 16) | (g << 8) | b;
        graphics.drawString(minecraft.font, text, -textWidth / 2, 0, color, true);
        pose.popPose();
    }

    /** 落地瞬间的全屏白闪。挂在 {@code RenderGuiEvent.Post}（在 HUD 之前调用也行）。 */
    public static void renderImpactFlash(GuiGraphics graphics, Minecraft minecraft) {
        if (!OrbitalStrikeClientState.isActive()) {
            return;
        }
        long impactAge = OrbitalStrikeClientState.impactAge();
        if (impactAge < 0 || impactAge >= FLASH_TICKS) {
            return;
        }
        if (minecraft.options.hideGui || minecraft.player == null) {
            return;
        }
        // 距离越远越弱：远处只看到一点白光，近处直接糊脸
        double distance = OrbitalStrikeClientState.distanceToPlayer();
        float falloff = (float) (1.0D - (distance - NEAR_RADIUS) / (FAR_RADIUS - NEAR_RADIUS));
        falloff = Mth.clamp(falloff, 0.0F, 1.0F);
        if (falloff <= 0.0F) {
            return;
        }
        // 从 1 平滑衰减到 0
        float t = 1.0F - (float) impactAge / FLASH_TICKS;
        int alpha = (int) (FLASH_ALPHA * falloff * t * 255.0F);
        if (alpha <= 0) {
            return;
        }
        graphics.fill(0, 0, graphics.guiWidth(), graphics.guiHeight(), (alpha << 24) | 0xFFFFFF);
    }

    // ---------------------------------------------------------------- 镜头震动

    /**
     * 落地瞬间把镜头轻微抖一下。挂在 {@code ViewportEvent.ComputeCameraAngles}。
     *
     * <p>用正弦 + 随机相位的组合（而不是纯随机）—— 纯随机每帧跳，观感是「画面失灵」；
     * 正弦衰减更像一次真实冲击的余震。</p>
     */
    public static void shakeCamera(ViewportEvent.ComputeCameraAngles event, Minecraft minecraft) {
        if (!OrbitalStrikeClientState.isActive()) {
            return;
        }
        long impactAge = OrbitalStrikeClientState.impactAge();
        if (impactAge < 0 || impactAge >= SHAKE_TICKS) {
            return;
        }
        if (minecraft.player == null) {
            return;
        }
        double distance = OrbitalStrikeClientState.distanceToPlayer();
        float falloff = (float) (1.0D - (distance - NEAR_RADIUS) / (FAR_RADIUS - NEAR_RADIUS));
        if (falloff <= 0.0F) {
            return;
        }
        // 衰减包络：从 1 降到 0
        float envelope = 1.0F - (float) impactAge / SHAKE_TICKS;
        float phase = (float) (minecraft.level.getGameTime() + event.getPartialTick()) * 1.3F;
        float amp = SHAKE_DEGREES * falloff * envelope;
        event.setYaw(event.getYaw() + Mth.sin(phase) * amp);
        event.setPitch(event.getPitch() + Mth.cos(phase * 1.7F) * amp * 0.7F);
        event.setRoll(event.getRoll() + Mth.sin(phase * 2.3F) * amp * 0.5F);
    }
}
