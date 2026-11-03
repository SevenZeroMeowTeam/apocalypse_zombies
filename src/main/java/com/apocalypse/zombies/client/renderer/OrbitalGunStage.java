package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.OrbitalStrikeClientState;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.BufferUploader;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.Tesselator;
import com.mojang.blaze3d.vertex.VertexFormat;
import net.minecraft.client.Camera;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.ShaderInstance;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.api.distmarker.OnlyIn;
import net.minecraftforge.client.event.RegisterShadersEvent;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import java.io.IOException;

/**
 * 轨道炮「弧光长矛」的多机位装置电影（v6.1）。
 *
 * <p>打击演出的太空段：画面里那门悬在深空里的轨道炮不再是「一个机位看 2 秒」，
 * 而是像参考包 SS-01 的装置段那样由一串镜头剪出来 ——
 * <b>远景建立 → 沿炮身掠行 → 炮口特写（充能波收束）→ 开火（爆闪 + 后坐 + 推离）
 * → 弹体目送（俯视弹道出画）</b>。机位全部在 Java 侧按时间轴插值，
 * 段与段之间用 smoothstep 连续过渡，全程没有一个硬切。</p>
 *
 * <p><b>为什么是 shader 而不是模型</b>：炮体是解析 SDF（距离场）光线步进画出来的，
 * 所以细节（线圈、聚焦爪、反应堆、散热鳍）都是算出来的，不用做网格和贴图；
 * 相机完全在 shader 空间里（{@code CamPos/CamForward/CamRight/CamUp}），
 * Java 这边只要每帧给一组正交基 —— 这恰好让「多机位运镜」变成纯参数插值，
 * shader 一行都不用改。</p>
 *
 * <p><b>参考包</b>：the-shooting-star 的 {@code star_gun.fsh} 用的是同一套办法
 * （解析 SDF + 光线步进 + 充能波 + 炮口闪光 + 多镜头剪辑）。
 * 我们换了造型和配色，并把「每像素角尺寸」单独做成 {@code PixelSize} uniform。</p>
 */
@OnlyIn(Dist.CLIENT)
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.MOD)
public final class OrbitalGunStage {

    private static ShaderInstance shader;

    /** 特写开始：升空镜头刚稳住（4 tick），alpha 从这里淡入。 */
    private static final int START_TICKS = 4;
    /** 淡入时长（tick）。 */
    private static final int FADE_IN_TICKS = 8;
    /** 开火段时长（tick）：后坐 + 炮口爆闪的运镜。 */
    private static final int FIRE_TICKS = 7;
    /** 目送段时长（tick）：机位上抬俯视弹道，随后 alpha 淡出交还地面镜头。 */
    private static final int WATCH_TICKS = 9;

    // —— 机位关键帧（炮身空间：炮轴 y=0，炮口 z=-18，炮闩 z=+7，整炮长约 27）。
    // 时间轴与位姿分开存：前 4 个刻度是「锁定时长的倍率」，后 2 个是「锁定结束后再过的 tick 数」
    // —— 这样任意锁定时长（20–400 tick 可配）都按同一节奏运镜。
    // 数值与 tools/shader_preview.py 的 gun_camera_at 保持一致。
    private static final double[] CAM_TIMES = {
            0.0D, 0.20D, 0.52D, 1.0D, FIRE_TICKS, FIRE_TICKS + WATCH_TICKS};
    private static final int LOCK_KEY_COUNT = 4;
    // 每行 = {px,py,pz, tx,ty,tz, tanHalf}
    private static final double[][] CAM_POSES = {
            // M0 远景建立：整炮斜入画，缓慢压向炮身
            {-34.0D, 11.0D, 4.0D, -1.0D, 0.0D, -5.0D, 0.50D},
            // M0→M1 边界
            {-30.0D, 9.0D, 1.0D, -0.6D, 0.0D, -6.0D, 0.46D},
            // M1 沿炮身掠行：线圈依次从画面下缘掠过
            {-12.0D, 3.5D, -7.0D, -0.4D, 0.1D, -10.0D, 0.36D},
            // M2 炮口特写：长焦看充能波收束、聚焦爪亮起
            {-6.0D, 2.0D, -13.5D, 0.0D, 0.2D, -16.5D, 0.27D},
            // M3 开火：机位被「冲击」推离（拉到炮口 23 单位外，白闪只占头 2 tick）+ 拉开视场
            {-14.0D, 6.5D, -3.0D, 0.0D, 0.2D, -16.5D, 0.36D},
            // M4 目送：上抬俯视，弹道向深空出画
            {-5.0D, 15.0D, 7.0D, 0.0D, -0.5D, -24.0D, 0.46D},
    };

    /** 本帧的特写不透明度（供程序化舞台避让：特写开着时几何炮台不画）。 */
    private static float lastAlpha;

    private OrbitalGunStage() {
    }

    /** 当前帧特写的不透明度（0 = 没在画）；程序化舞台读它做避让。 */
    public static float closeupAlpha() {
        return OrbitalStrikeClientState.isActive() ? lastAlpha : 0.0F;
    }

    @SubscribeEvent
    public static void onRegisterShaders(RegisterShadersEvent event) throws IOException {
        ShaderInstance instance = new ShaderInstance(event.getResourceProvider(),
                new ResourceLocation(ApocalypseZombies.MOD_ID, "orbit_gun"),
                DefaultVertexFormat.POSITION);
        event.registerShader(instance, loaded -> shader = loaded);
    }

    /**
     * 在 {@code RenderLevelStageEvent} 里画装置电影。
     *
     * <p>从升空结束一路演到开火后目送段结束：锁定段是「建立 → 掠行 → 特写」的
     * 三段运镜，开火段交给 shader 的后坐/爆闪/弹道，目送段机位俯视弹道出画后淡出，
     * 地面镜头（光柱、挖掘余晖）平滑接手。</p>
     */
    public static void render(RenderLevelStageEvent event) {
        lastAlpha = 0.0F;
        if (shader == null) {
            return;
        }
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_SKY) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.level == null || minecraft.player == null) {
            return;
        }
        if (!OrbitalStrikeClientState.isActive()) {
            return;
        }
        if (!OrbitalCinematic.isEngaged()) {
            return;
        }
        double elapsed = OrbitalStrikeClientState.elapsed();
        double lock = Math.max(1.0D, OrbitalStrikeClientState.lockTicks());
        double end = lock + FIRE_TICKS + WATCH_TICKS;
        if (elapsed < START_TICKS || elapsed > end) {
            return;
        }

        // —— 淡入淡出：镜头不该硬切进来；目送段末尾让位给地面镜头
        float fadeIn = Mth.clamp((float) ((elapsed - START_TICKS) / FADE_IN_TICKS), 0.0F, 1.0F);
        float fadeOut = Mth.clamp((float) ((end - elapsed) / 6.0D), 0.0F, 1.0F);
        float alpha = Math.min(fadeIn, fadeOut);
        if (alpha <= 0.01F) {
            return;
        }
        lastAlpha = alpha;

        // —— 机位：按关键帧时间轴插值（位置 / 注视点 / 视场一起过渡）
        double[] cam = cameraAt(elapsed, lock);
        double px = cam[0];
        double py = cam[1];
        double pz = cam[2];
        double tx = cam[3];
        double ty = cam[4];
        double tz = cam[5];
        // 开火瞬间的机位震动：叠加在推离运镜上，衰减极快
        double fireAge = elapsed - lock;
        if (fireAge >= 0.0D && fireAge < 10.0D) {
            double k = (1.0D - fireAge / 10.0D) * 0.09D;
            px += Math.sin(elapsed * 2.17D) * k;
            py += Math.cos(elapsed * 3.31D) * k * 0.7D;
        }

        // —— 正交基（世界 up 为参考，避免运镜翻滚；目送段保留一点荷兰角由 shader 端 up 处理）
        double fx = tx - px;
        double fy = ty - py;
        double fz = tz - pz;
        double fl = Math.sqrt(fx * fx + fy * fy + fz * fz);
        if (fl < 1.0E-4D) {
            return;
        }
        fx /= fl;
        fy /= fl;
        fz /= fl;
        // right = normalize(cross(fwd, worldUp))，up = cross(right, fwd)
        double rx = -fz;
        double ry = 0.0D;
        double rz = fx;
        double rl = Math.sqrt(rx * rx + rz * rz);
        if (rl < 1.0E-4D) {
            // 视线几乎竖直：退回用任意水平向量
            rx = 1.0D;
            rz = 0.0D;
            rl = 1.0D;
        }
        rx /= rl;
        rz /= rl;
        double ux = ry * fz - rz * fy;
        double uy = rz * fx - rx * fz;
        double uz = rx * fy - ry * fx;

        Camera camera = event.getCamera();
        double yaw = Math.toRadians(camera.getYRot());
        double pitch = Math.toRadians(camera.getXRot());
        double sy = Math.sin(yaw);
        double cy = Math.cos(yaw);
        double sp = Math.sin(pitch);
        double cp = Math.cos(pitch);

        float fov = (float) Math.toRadians(minecraft.options.fov().get());
        float tanHalf = (float) Math.tan(fov * 0.5F);
        int width = minecraft.getWindow().getWidth();
        int height = minecraft.getWindow().getHeight();
        float aspect = (float) width / Math.max(1.0F, (float) height);

        // —— 充能进度：0→1 对应「锁定中」这一段
        long lockTicks = OrbitalStrikeClientState.lockTicks();
        float charge = lockTicks > 0 ? Mth.clamp((float) elapsed / (float) lockTicks, 0.0F, 1.0F) : 0.0F;
        // —— 开火时刻：锁定结束那一 tick。负数 = 还没开火。
        float fired = elapsed >= lockTicks ? (float) ((elapsed - lockTicks) / 20.0D) : -1.0F;

        // 运镜机位的视场与玩家 FOV 无关（那是「贴在画面上的镜头参数」），
        // 但保留玩家 FOV 的一点点影响，避免极端 FOV 设置下穿帮。
        float shotTan = (float) cam[6];
        float blended = shotTan + (tanHalf - shotTan) * 0.15F;

        try {
            shader.safeGetUniform("CamPos").set((float) px, (float) py, (float) pz);
            shader.safeGetUniform("CamForward").set((float) fx, (float) fy, (float) fz);
            shader.safeGetUniform("CamRight").set((float) rx, (float) ry, (float) rz);
            shader.safeGetUniform("CamUp").set((float) ux, (float) uy, (float) uz);
            shader.safeGetUniform("TanHalf").set(blended);
            shader.safeGetUniform("Aspect").set(aspect);
            // 每像素在「张切空间」里的张角：2*tanHalf / 高度。MC 的 core shader 拿不到 OutSize。
            shader.safeGetUniform("PixelSize").set(2.0F * blended / Math.max(1.0F, (float) height));
            shader.safeGetUniform("Charge").set(charge);
            shader.safeGetUniform("Fired").set(fired);
            shader.safeGetUniform("GameTime").set((minecraft.level.getGameTime() + event.getPartialTick()) / 20.0F);
            shader.safeGetUniform("Alpha").set(alpha);

            RenderSystem.setShader(() -> shader);
            RenderSystem.disableDepthTest();
            RenderSystem.depthMask(false);
            RenderSystem.disableCull();
            RenderSystem.enableBlend();
            // 炮体是实体，要盖住后面的星空 → 用普通 alpha 混合
            RenderSystem.defaultBlendFunc();
            RenderSystem.setShaderColor(1.0F, 1.0F, 1.0F, 1.0F);

            BufferBuilder buffer = Tesselator.getInstance().getBuilder();
            buffer.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.POSITION);
            buffer.vertex(-1.0F, -1.0F, 0.0F).endVertex();
            buffer.vertex(1.0F, -1.0F, 0.0F).endVertex();
            buffer.vertex(1.0F, 1.0F, 0.0F).endVertex();
            buffer.vertex(-1.0F, 1.0F, 0.0F).endVertex();
            BufferUploader.draw(buffer.end());

            RenderSystem.disableBlend();
            RenderSystem.enableDepthTest();
            RenderSystem.depthMask(true);
            RenderSystem.enableCull();
        } catch (Throwable error) {
            // 画不出来就安静地跳过这一帧，不要把整个渲染链带崩
            ApocalypseZombies.LOGGER.warn("[天陨] 轨道炮装置电影渲染失败，跳过这一帧", error);
        }
    }

    /**
     * 机位时间轴：按 {@code CAM_KEYS} 的刻度插值出 (px,py,pz, tx,ty,tz, tanHalf)。
     *
     * <p>刻度里的锁定段用「锁定时长的倍率」表达，开火段用固定 tick 数，
     * 所以任意锁定时长（20–400 tick 可配）都按同一节奏运镜。
     * 段内 smoothstep，段边界两侧的关键帧相同 —— 连续，无跳切。</p>
     */
    private static double[] cameraAt(double elapsed, double lock) {
        double[] a = CAM_POSES[0];
        double[] b = CAM_POSES[0];
        double t = 0.0D;
        for (int i = 0; i < CAM_POSES.length - 1; i++) {
            double t0 = keyTime(i, lock);
            double t1 = keyTime(i + 1, lock);
            if (elapsed >= t0 && elapsed <= t1) {
                a = CAM_POSES[i];
                b = CAM_POSES[i + 1];
                t = t1 > t0 ? (elapsed - t0) / (t1 - t0) : 0.0D;
                break;
            }
            if (elapsed < t0) {
                a = CAM_POSES[i];
                b = CAM_POSES[i];
                t = 0.0D;
                break;
            }
            a = CAM_POSES[i + 1];
            b = CAM_POSES[i + 1];
            t = 1.0D;
        }
        double s = smooth(t);
        double[] out = new double[7];
        for (int c = 0; c < 7; c++) {
            out[c] = Mth.lerp(s, a[c], b[c]);
        }
        return out;
    }

    /** 第 i 个关键帧的 tick 时刻：前段是「锁定时长的倍率」，发射段是「锁定结束后再过的 tick 数」。 */
    private static double keyTime(int i, double lock) {
        return i < LOCK_KEY_COUNT ? CAM_TIMES[i] * lock : lock + CAM_TIMES[i];
    }

    private static float smooth(double t) {
        t = Mth.clamp(t, 0.0D, 1.0D);
        return (float) (t * t * (3.0D - 2.0D * t));
    }
}
