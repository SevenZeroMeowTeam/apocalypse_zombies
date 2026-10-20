package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.client.OrbitalStrikeClientState;
import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import com.apocalypse.zombies.orbital.engine.StrikeProtocols;
import com.mojang.blaze3d.pipeline.RenderTarget;
import com.mojang.blaze3d.pipeline.TextureTarget;
import com.mojang.blaze3d.systems.RenderSystem;
import net.minecraft.client.Camera;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.EffectInstance;
import net.minecraft.client.renderer.PostPass;
import net.minecraft.core.BlockPos;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.api.distmarker.OnlyIn;
import org.joml.Matrix4f;
import org.lwjgl.opengl.GL11;

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
    private static boolean announced;
    private static boolean runtimeOff;

    private OrbitalPostFx() {
    }

    /** 后处理链是否可用（配置开、没失败、没被运行时关掉）。GUI 近似层据此决定要不要让位。 */
    public static boolean active() {
        return !failed && !runtimeOff && Config.ORBITAL_STRIKE_POST_FX.get();
    }

    /**
     * 运行时开关（{@code /orbitpost on|off}）：v5.0 加，用来在「配置开但画面异常」时
     * 不必退出游戏或改文件就能立刻切回 GUI 近似层。
     */
    public static void setRuntimeEnabled(boolean enabled) {
        runtimeOff = !enabled;
        if (runtimeOff) {
            // 立刻回收 FBO，避免关掉之后还占一份显存
            close();
        }
    }

    public static boolean runtimeEnabled() {
        return !runtimeOff;
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
        float accentR = ((rgb >> 16) & 0xFF) / 255.0F;
        float accentG = ((rgb >> 8) & 0xFF) / 255.0F;
        float accentB = (rgb & 0xFF) / 255.0F;

        // v5.0：冲击帧样式按协议分配（6 种，见 orbit_grade.glsl 的 impactFrame）
        float impactMode = switch (mode) {
            case CANNON -> 0.0F;   // 墨线：动能弹的硬直
            case LANCE -> 3.0F;    // 墨线 + 青饰：贯穿
            case GRAVITY -> 5.0F;  // 余烬线稿：奇点灼烧
            case STORM -> 4.0F;    // 半调网点：多点击碎的噪点
            case LASER -> 1.0F;    // 反相：过曝
            case PLANET -> 2.0F;   // 绯红：陨石
        };
        // 冲击帧强度：命中后 12 tick 从 1 衰减到 0
        float frameStrength = impactAge >= 0L && impactAge < 12L
                ? (1.0F - impactAge / 12.0F) * 0.95F : 0.0F;
        // 变焦模糊：命中后同样 12 tick，制造「撞过来」的推镜
        float zoomBlur = impactAge >= 0L && impactAge < 12L
                ? (1.0F - impactAge / 12.0F) * 0.75F : 0.0F;
        float desaturate = space * 0.35F + impact * 0.5F;
        float contrast = impact * 0.55F;
        float grain = 0.35F * Math.max(space, impact);
        float exposure = 1.0F;
        // 冲击帧中心：优先落在屏幕上的落点，取不到就居中
        float centerX = 0.5F;
        float centerY = 0.5F;
        try {
            BlockPos target = OrbitalStrikeClientState.target();
            Camera camera = minecraft.gameRenderer.getMainCamera();
            if (target != null) {
                Vec3 to = Vec3.atCenterOf(target).subtract(camera.getPosition());
                double dist = to.length();
                if (dist > 0.01D) {
                    double yaw = Math.toRadians(camera.getYRot());
                    double pitch = Math.toRadians(camera.getXRot());
                    // 相机三轴（Minecraft yaw：0 = 朝 +Z；右侧 = -X）
                    double sx = -Math.sin(yaw) * Math.cos(pitch);
                    double sy = -Math.sin(pitch);
                    double sz = Math.cos(yaw) * Math.cos(pitch);
                    double rx = -Math.cos(yaw);
                    double rz = -Math.sin(yaw);
                    double ux = -Math.sin(yaw) * Math.sin(pitch);
                    double uy = Math.cos(pitch);
                    double uz = Math.cos(yaw) * Math.sin(pitch);
                    double nx = to.x / dist;
                    double ny = to.y / dist;
                    double nz = to.z / dist;
                    double z = nx * sx + ny * sy + nz * sz;
                    if (z > 0.05D) {
                        double tanHalf = Math.tan(
                                Math.toRadians(minecraft.options.fov().get()) * 0.5D);
                        double aspect = (double) minecraft.getWindow().getWidth()
                                / Math.max(1.0D, (double) minecraft.getWindow().getHeight());
                        double px = (nx * rx + nz * rz) / (z * tanHalf * aspect);
                        double py = (nx * ux + ny * uy + nz * uz) / (z * tanHalf);
                        centerX = (float) Mth.clamp(0.5D + px * 0.5D, 0.0D, 1.0D);
                        centerY = (float) Mth.clamp(0.5D - py * 0.5D, 0.0D, 1.0D);
                    }
                }
            }
        } catch (Throwable ignored) {
            // 落点取不到就用屏幕中心，冲击帧照常
        }

        try {
            EffectInstance fx = effectPass.getEffect();
            RenderTarget main = minecraft.getMainRenderTarget();
            // 画面尺寸：OutSize 决定宽高比（色差/暗角/冲击帧的取样步长都靠它），
            // InSize 是主画面像素尺寸（径向速度模糊按像素定步长）。
            // v5.2 之前这两个 uniform 从没被赋值过，一直是 json 里的默认 (1,1)，
            // 所以宽高比是 1:1、非方屏上色差和暗角都是歪的。
            fx.safeGetUniform("OutSize").set((float) main.width, (float) main.height);
            fx.safeGetUniform("InSize").set((float) main.width, (float) main.height);
            fx.safeGetUniform("Time").set((minecraft.level.getGameTime() + partialTick) / 20.0F);
            fx.safeGetUniform("Strength").set(strength);
            fx.safeGetUniform("Radial").set(radial);
            fx.safeGetUniform("Chroma").set(chroma);
            fx.safeGetUniform("Impact").set(impact);
            fx.safeGetUniform("Flash").set(flash);
            fx.safeGetUniform("Vignette").set(vignette);
            fx.safeGetUniform("Grade").set(gradeR, gradeG, gradeB);
            fx.safeGetUniform("ZoomBlur").set(zoomBlur);
            fx.safeGetUniform("Bloom").set(0.65F);
            fx.safeGetUniform("Desaturate").set(desaturate);
            fx.safeGetUniform("Contrast").set(contrast);
            fx.safeGetUniform("Grain").set(grain);
            fx.safeGetUniform("ImpactMode").set(impactMode);
            fx.safeGetUniform("ImpactStrength").set(frameStrength);
            fx.safeGetUniform("ImpactCenter").set(centerX, centerY);
            fx.safeGetUniform("Exposure").set(exposure);
            fx.safeGetUniform("Accent").set(accentR, accentG, accentB);
            // 光轴（v5.2，移植参考包 star_rays.fsh）：光源就是屏幕上的落点，
            // 强度在落地那一下拉满，随后随冲击帧一起退下去。
            float shaft = Math.max(impact, impactAge >= 0L && impactAge < 24L
                    ? (1.0F - impactAge / 24.0F) * 0.6F : 0.0F);
            fx.safeGetUniform("ShaftPos").set(centerX, centerY);
            fx.safeGetUniform("ShaftStrength").set(shaft);

            // 关键：PostPass 画的是一个全屏四边形，默认的背面剔除会把整个画面剔掉
            // （GUI 前这个状态还留着世界渲染的 cull = on），结果是主目标被 clear 成黑。
            RenderSystem.disableCull();
            RenderSystem.disableDepthTest();
            float time = (minecraft.level.getGameTime() + partialTick) / 20.0F;
            effectPass.process(time);
            blitPass.process(time);

            // 后处理在部分驱动上会留下 GL 错误；一旦出现就永久关闭，避免继续刷黑屏。
            int glError = GL11.glGetError();
            if (glError != 0) {
                failed = true;
                ApocalypseZombies.LOGGER.warn("[天陨] 后处理 GL 错误 0x{}，已关闭后处理。",
                        Integer.toHexString(glError));
            }

            // PostPass 结束时会 unbindWrite；必须把主目标重新绑回来，
            // 否则后面的 GUI 会画到默认帧缓冲，最终 blit 出来的就是黑屏。
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
            if (!announced) {
                announced = true;
                ApocalypseZombies.LOGGER.info("[天陨] 后处理链已启用 {}x{}（实验性，可在配置关闭）",
                        main.width, main.height);
            }
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
