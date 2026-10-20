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
 * 轨道炮「弧光长矛」特写（v5.2.0）。
 *
 * <p>打击演出的太空段：镜头从地面升到轨道高度后，画面中央出现那门悬在深空里的
 * 轨道炮 —— 充能时一道光波从炮闩推向炮口，开火瞬间炮口爆闪、整炮后坐。</p>
 *
 * <p><b>为什么是 shader 而不是模型</b>：炮体是解析 SDF（距离场）光线步进画出来的，
 * 所以细节（线圈、聚焦爪、反应堆、散热鳍）都是算出来的，不用做网格和贴图。
 * 相机也完全在 shader 空间里（{@code CamPos/CamForward/CamRight/CamUp}），
 * Java 这边只要给一组四元组。</p>
 *
 * <p><b>参考包</b>：the-shooting-star 的 {@code star_gun.fsh} 用的是同一套办法
 * （解析 SDF + 光线步进 + 充能波 + 炮口闪光）。我们换了造型和配色，
 * 并把「每像素角尺寸」单独做成 {@code PixelSize} uniform（core shader 拿不到 OutSize）。</p>
 */
@OnlyIn(Dist.CLIENT)
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.MOD)
public final class OrbitalGunStage {

    private static ShaderInstance shader;

    /** 特写持续时间（tick）：从镜头到位到开火后的一小段。 */
    private static final int CLOSEUP_START = 6;
    private static final int CLOSEUP_END = 46;

    private OrbitalGunStage() {
    }

    @SubscribeEvent
    public static void onRegisterShaders(RegisterShadersEvent event) throws IOException {
        ShaderInstance instance = new ShaderInstance(event.getResourceProvider(),
                new ResourceLocation(ApocalypseZombies.MOD_ID, "orbit_gun"),
                DefaultVertexFormat.POSITION);
        event.registerShader(instance, loaded -> shader = loaded);
    }

    /**
     * 在 {@code RenderLevelStageEvent} 里画特写。
     *
     * <p>只在太空段（镜头已经升到轨道高度）出现：地面上看到一���悬在太空的炮不合理。</p>
     */
    public static void render(RenderLevelStageEvent event) {
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
        long elapsed = OrbitalStrikeClientState.elapsed();
        if (elapsed < CLOSEUP_START || elapsed > CLOSEUP_END) {
            return;
        }

        // —— 淡入淡出：特写不该硬切进来
        float fadeIn = Mth.clamp((elapsed - CLOSEUP_START) / 8.0F, 0.0F, 1.0F);
        float fadeOut = Mth.clamp((CLOSEUP_END - elapsed) / 10.0F, 0.0F, 1.0F);
        float alpha = Math.min(fadeIn, fadeOut);
        if (alpha <= 0.01F) {
            return;
        }

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
        long lock = OrbitalStrikeClientState.lockTicks();
        float charge = lock > 0 ? Mth.clamp((float) elapsed / (float) lock, 0.0F, 1.0F) : 0.0F;

        // —— 开火时刻：锁定结束那一 tick。负数 = 还没开火。
        float fired = elapsed >= lock ? (elapsed - lock) / 20.0F : -1.0F;

        try {
            shader.safeGetUniform("CamPos").set(0.0F, 0.0F, 26.0F);
            shader.safeGetUniform("CamForward").set((float) (-sy * cp), (float) (-sp), (float) (cy * cp));
            shader.safeGetUniform("CamRight").set((float) (-cy), 0.0F, (float) (-sy));
            shader.safeGetUniform("CamUp").set((float) (-sy * sp), (float) cp, (float) (cy * sp));
            shader.safeGetUniform("TanHalf").set(tanHalf);
            shader.safeGetUniform("Aspect").set(aspect);
            // 每像素在「张切空间」里的张角：2*tanHalf / 高度。MC 的 core shader 拿不到 OutSize。
            shader.safeGetUniform("PixelSize").set(2.0F * tanHalf / Math.max(1.0F, (float) height));
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
            ApocalypseZombies.LOGGER.warn("[天陨] 轨道炮特写渲染失败，跳过这一帧", error);
        }
    }
}
