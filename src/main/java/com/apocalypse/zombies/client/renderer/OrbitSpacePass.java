package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
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
 * 「太空全景」全屏 pass（v6.0.0）。
 *
 * <p>把参考包 the-shooting-star 的做法搬过来：<b>整幅太空画面由一个片元着色器画出来</b> ——
 * 银河全景、地球（含云层、海面高光、晨昏线、夜面城市灯）、大气辉光、恒星，
 * 全都在这一个 pass 里用光线步进算出来。不在世界里摆模型，也不画公告板。</p>
 *
 * <p>相机在 shader 空间：Java 给出 {@code CamPos/CamForward/CamRight/CamUp}，
 * 环绕地球缓慢漂移（模拟卫星绕飞），配合演出机位一起转。</p>
 *
 * <p>贴图是自己烘焙的：{@code space_panorama.png}（等距柱状银河全景）与
 * {@code planet_albedo.png}（行星表面图，RGB=反照率 / A=云）。
 * 不用参考包的 NASA 素材 —— 那些是第三方的。</p>
 */
@OnlyIn(Dist.CLIENT)
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.MOD)
public final class OrbitSpacePass {

    private static ShaderInstance shader;
    private static ResourceLocation panorama;
    private static ResourceLocation planetMap;

    /** 地球半径（场景单位）。相机停在 1.35 半径处 —— 低轨道高度。 */
    private static final double ORBIT_RADIUS = 1.35D;

    private OrbitSpacePass() {
    }

    @SubscribeEvent
    public static void onRegisterShaders(RegisterShadersEvent event) throws IOException {
        ShaderInstance instance = new ShaderInstance(event.getResourceProvider(),
                new ResourceLocation(ApocalypseZombies.MOD_ID, "orbit_space"),
                DefaultVertexFormat.POSITION);
        event.registerShader(instance, loaded -> shader = loaded);
        panorama = loadTexture(event.getResourceProvider(),
                new ResourceLocation(ApocalypseZombies.MOD_ID, "textures/environment/space_panorama.png"));
        planetMap = loadTexture(event.getResourceProvider(),
                new ResourceLocation(ApocalypseZombies.MOD_ID, "textures/environment/planet_albedo.png"));
    }

    /** 贴图可能还没烘焙出来 —— 缺了就返回 null，pass 会安静地跳过。 */
    private static ResourceLocation loadTexture(net.minecraft.server.packs.resources.ResourceProvider manager,
                                           ResourceLocation id) {
        try {
            if (manager.getResource(id).isPresent()) {
                return id;
            }
        } catch (Exception ignored) {
            // 资源缺失不致命
        }
        return null;
    }

    /**
     * 在 {@code RenderLevelStageEvent} 里画太空全景。
     *
     * <p>画在 {@code AFTER_SKY}：此时天空已经画完、地面还没画，
     * 我们这张全屏图会盖住天空，随后世界照常画在它上面。</p>
     */
    /**
     * 太空全景 pass 现在是否可用。
     *
     * <p>贴图烘焙出来之前，这个 pass 不画 —— 老的三维舞台继续顶着，
     * 演出不会因为缺贴图而开天窗。</p>
     */
    public static boolean isActive() {
        if (shader == null || panorama == null || planetMap == null) {
            return false;
        }
        try {
            return Config.ORBITAL_STRIKE_SPACE_PASS.get();
        } catch (Throwable t) {
            return true;   // 配置没就绪就当开着
        }
    }

    /**
     * 在 {@code RenderLevelStageEvent} 里画太空全景。
     *
     * <p>画在 {@code AFTER_SKY}：此时天空已经画完、地面还没画，
     * 我们这张全屏图会盖住天空，随后世界照常画在它上面。</p>
     */
    public static void render(RenderLevelStageEvent event) {
        if (!isActive()) {
            return;
        }
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_SKY) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.level == null || minecraft.player == null) {
            return;
        }
        if (!OrbitalCinematic.isSpaceStage()) {
            return;
        }
        float opacity = OrbitalCinematic.spaceOpacity();
        if (opacity <= 0.005F) {
            return;
        }

        Camera camera = event.getCamera();
        double yaw = Math.toRadians(camera.getYRot());
        double pitch = Math.toRadians(camera.getXRot());
        double sy = Math.sin(yaw);
        double cy = Math.cos(yaw);
        double sp = Math.sin(pitch);
        double cp = Math.cos(pitch);

        // —— 相机在世界里的朝向（Minecraft 约定：yaw 0 = +Z）
        double fwdX = -sy * cp;
        double fwdY = -sp;
        double fwdZ = cy * cp;
        double rightX = -cy;
        double rightZ = -sy;
        double upX = -sy * sp;
        double upY = cp;
        double upZ = cy * sp;

        // —— 场景里的相机：绕地球漂移（卫星绕飞），跟随机位一起转
        double t = (minecraft.level.getGameTime() + event.getPartialTick()) / 20.0D;
        double orbit = t * 0.035D;
        double camX = Math.sin(orbit) * ORBIT_RADIUS;
        double camZ = Math.cos(orbit) * ORBIT_RADIUS;
        double camY = 0.28D + Math.sin(t * 0.11D) * 0.05D;

        float fov = (float) Math.toRadians(minecraft.options.fov().get());
        float tanHalf = (float) Math.tan(fov * 0.5F);
        int width = minecraft.getWindow().getWidth();
        int height = minecraft.getWindow().getHeight();
        float aspect = (float) width / Math.max(1.0F, (float) height);

        // 揭示进度：开场从黑里淡入
        double elapsed = OrbitalStrikeClientState.elapsed();
        float reveal = Mth.clamp((float) (elapsed - OrbitalCinematic.ascentStartTicks()) / 20.0F, 0.0F, 1.0F);

        try {
            shader.safeGetUniform("CamPos").set((float) camX, (float) camY, (float) camZ);
            shader.safeGetUniform("CamForward").set((float) fwdX, (float) fwdY, (float) fwdZ);
            shader.safeGetUniform("CamRight").set((float) rightX, 0.0F, (float) rightZ);
            shader.safeGetUniform("CamUp").set((float) upX, (float) upY, (float) upZ);
            shader.safeGetUniform("TanHalf").set(tanHalf);
            shader.safeGetUniform("Aspect").set(aspect);
            shader.safeGetUniform("Alpha").set(opacity);
            shader.safeGetUniform("Reveal").set(reveal);
            shader.safeGetUniform("Panorama").set(0);
            shader.safeGetUniform("PlanetMap").set(1);

            RenderSystem.setShader(() -> shader);
            RenderSystem.disableDepthTest();
            RenderSystem.depthMask(false);
            RenderSystem.disableCull();
            RenderSystem.enableBlend();
            RenderSystem.defaultBlendFunc();
            RenderSystem.setShaderColor(1.0F, 1.0F, 1.0F, 1.0F);

            // 贴图：core shader 的 sampler 用 RenderSystem.setShaderTexture 绑
            RenderSystem.setShaderTexture(0, panorama);
            RenderSystem.setShaderTexture(1, planetMap);

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
            ApocalypseZombies.LOGGER.warn("[天陨] 太空全景渲染失败，跳过这一帧", error);
        }
    }
}
