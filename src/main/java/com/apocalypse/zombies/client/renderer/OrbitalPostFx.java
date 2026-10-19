package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.client.OrbitalStrikeClientState;
import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import com.apocalypse.zombies.orbital.engine.StrikeProtocols;
import com.mojang.blaze3d.pipeline.RenderTarget;
import com.mojang.blaze3d.pipeline.TextureTarget;
import com.mojang.blaze3d.systems.RenderSystem;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.EffectInstance;
import net.minecraft.client.renderer.PostPass;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraft.util.Mth;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.api.distmarker.OnlyIn;
import org.joml.Matrix4f;

/**
 * 一条轻量后处理链（v4.0.3）：把世界画面先画进 swap，再用
 * {@code apocalypse_zombies:orbital} 做「径向模糊 + 色差 + 廉价 bloom + 白闪 + 调色 + 暗角」，
 * 最后用 passthrough 画回主目标。
 *
 * <p><b>为什么不用 {@code PostChain}</b>：{@code PostChain} 不暴露 pass 列表，没法每帧写自定义
 * uniform。这里直接组合两个 {@link PostPass}（效果 → blit），拿到 {@code getEffect()} 设置
 * Strength/Radial/Chroma/Impact/Flash/Vignette/Grade。</p>
 *
 * <p><b>失败即回退</b>：任何异常（驱动不支持 GLSL 150、程序编译失败、窗口重建）都会把
 * {@link #failed} 置真并永久关闭这条链；{@code OrbitalScreenFX} 里的纯 GUI 近似层继续工作。
 * 配置 {@code [orbital_strike] post_shader=false} 可手动关闭。</p>
 *
 * <p>只在打击演出期间运行；没有打击时这张 pass 完全不参与，零常态开销。</p>
 */
@OnlyIn(Dist.CLIENT)
public final class OrbitalPostFx {

    private static TextureTarget swap;
    private static PostPass effectPass;
    private static PostPass blitPass;
    private static int width = -1;
    private static int height = -1;
    private static boolean failed;

    private OrbitalPostFx() {
    }

    /** 后处理链是否可用（配置开且没失败）。GUI 近似层据此决定要不要让位。 */
    public static boolean active() {
        return !failed && Config.ORBITAL_STRIKE_POST_FX.get();
    }

    /** 每帧在 GUI 之前调用：把当前主画面做一次后处理再画回去。 */
    public static void process(float partialTick) {
        if (!active()) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.level == null || minecraft.player == null) {
            return;
        }
        if (!OrbitalStrikeClientState.isActive()) {
            return;
        }
        long elapsed = OrbitalStrikeClientState.elapsed();
        int lock = OrbitalStrikeClientState.lockTicks();
        int fall = OrbitalStrikeClientState.fallTicks();
        long impactAge = OrbitalStrikeClientState.impactAge();

        // 太空段从升空开始淡入。
        double ascent = OrbitalCinematic.ascentStartTicks();
        float space = Mth.clamp((float) ((elapsed - ascent) / 24.0D), 0.0F, 1.0F);

        // 弹体下落段：径向模糊拉满。
        float radial = 0.0F;
        double radialStart = lock * 0.55D;
        if (elapsed >= radialStart && elapsed <= (long) lock + fall) {
            float in = Mth.clamp((float) ((elapsed - radialStart) / Math.max(1.0D, lock * 0.45D)), 0.0F, 1.0F);
            float out = Mth.clamp((float) (((long) lock + fall - elapsed) / Math.max(1.0D, fall * 0.6D)), 0.0F, 1.0F);
            radial = (float) Math.sin(in * Math.PI * 0.5D) * out;
        }

        float chroma = 0.0F;
        float impact = 0.0F;
        float flash = 0.0F;
        if (impactAge >= 0L) {
            chroma = impactAge < 12L ? (1.0F - impactAge / 12.0F) : 0.0F;
            impact = Mth.clamp(1.0F - impactAge / 18.0F, 0.0F, 1.0F);
            flash = impactAge < 8L ? (1.0F - impactAge / 8.0F) * 0.9F : 0.0F;
        }
        float vignette = Math.max(space * 0.5F, impact * 0.25F);
        float strength = Math.max(Math.max(space, radial), Math.max(chroma, flash));
        if (strength < 0.01F) {
            return;
        }

        if (!ensure(minecraft)) {
            return;
        }

        OrbitalStrikeMode mode = OrbitalStrikeClientState.mode();
        int rgb = StrikeProtocols.protocolFor(mode).color();
        float gradeR = ((rgb >> 16) & 0xFF) / 255.0F * 0.16F;
        float gradeG = ((rgb >> 8) & 0xFF) / 255.0F * 0.16F;
        float gradeB = (rgb & 0xFF) / 255.0F * 0.16F;

        try {
            EffectInstance fx = effectPass.getEffect();
            fx.safeGetUniform("Strength").set(strength);
            fx.safeGetUniform("Radial").set(radial);
            fx.safeGetUniform("Chroma").set(chroma);
            fx.safeGetUniform("Impact").set(impact);
            fx.safeGetUniform("Flash").set(flash);
            fx.safeGetUniform("Vignette").set(vignette);
            fx.safeGetUniform("Grade").set(gradeR, gradeG, gradeB);

            // 关键：PostPass 画的是一个全屏四边形，默认的背面剔除会把整个画面剔掉
            // （GUI 前这个状态还留着世界渲染的 cull = on），结果是主目标被 clear 成黑。
            RenderSystem.disableCull();
            RenderSystem.disableDepthTest();
            float time = (minecraft.level.getGameTime() + partialTick) / 20.0F;
            effectPass.process(time);
            blitPass.process(time);

            // PostPass 结束时会 unbindWrite；必须把主目标重新绑回来，
            // 否则后面的 GUI 会画到默认帧缓冲，最终 blit 出来的就是黑屏。
            RenderTarget main = minecraft.getMainRenderTarget();
            main.bindWrite(false);
            RenderSystem.viewport(0, 0, main.width, main.height);
            RenderSystem.disableDepthTest();
            RenderSystem.enableBlend();
            RenderSystem.defaultBlendFunc();
            RenderSystem.setShaderColor(1.0F, 1.0F, 1.0F, 1.0F);
        } catch (Throwable error) {
            failed = true;
            ApocalypseZombies.LOGGER.warn("[天陨] 后处理链启动失败，回退到 GUI 近似层。", error);
        }
    }

    private static boolean ensure(Minecraft minecraft) {
        RenderTarget main = minecraft.getMainRenderTarget();
        if (main == null) {
            return false;
        }
        if (swap != null && width == main.width && height == main.height) {
            return true;
        }
        close();
        try {
            ResourceManager resources = minecraft.getResourceManager();
            swap = new TextureTarget(main.width, main.height, false, Minecraft.ON_OSX);
            swap.setClearColor(0.0F, 0.0F, 0.0F, 0.0F);
            effectPass = new PostPass(resources, "apocalypse_zombies:orbital", main, swap);
            blitPass = new PostPass(resources, "apocalypse_zombies:orbital_blit", swap, main);
            Matrix4f ortho = new Matrix4f().setOrtho(0.0F, main.width, 0.0F, main.height, 0.1F, 1000.0F);
            effectPass.setOrthoMatrix(ortho);
            blitPass.setOrthoMatrix(ortho);
            width = main.width;
            height = main.height;
            return true;
        } catch (Throwable error) {
            failed = true;
            ApocalypseZombies.LOGGER.warn("[天陨] 后处理程序加载失败（{}x{}），回退到 GUI 近似层。",
                    main.width, main.height, error);
            return false;
        }
    }

    private static void close() {
        if (blitPass != null) {
            blitPass.close();
            blitPass = null;
        }
        if (effectPass != null) {
            effectPass.close();
            effectPass = null;
        }
        if (swap != null) {
            swap.destroyBuffers();
            swap = null;
        }
        width = -1;
        height = -1;
    }
}
