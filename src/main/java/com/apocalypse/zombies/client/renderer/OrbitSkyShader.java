package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.orbit.OrbitDimension;
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
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RegisterShadersEvent;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import java.io.IOException;

/**
 * 轨道维度的程序化太空天幕（v4.0.9）：不建 FBO、不换帧缓冲，只在 {@code AFTER_SKY}
 * 画一个全屏四边形，由 {@code orbit_sky} 片元着色器按相机三轴重建视线方向，
 * 实时生成星空 / 银河带 / 星云 / 远处太阳。
 *
 * <p>这是“shader 地球/星云背景”的第一步：先把太空环境从“几张贴图 billboard”换成
 * 真正随视角变化的天幕；地球球体、行星环与大气层留到同一 shader 的下一步（P1-b）。</p>
 *
 * <p>只作用于 {@code apocalypse_zombies:orbit} 维度，主世界的月亮/天空逻辑完全不受影响；
 * shader 注册失败时静默不画，回退到维度原本的末地天空。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.MOD)
public final class OrbitSkyShader {

    private static ShaderInstance shader;

    private OrbitSkyShader() {
    }

    @SubscribeEvent
    public static void onRegisterShaders(RegisterShadersEvent event) throws IOException {
        ShaderInstance instance = new ShaderInstance(event.getResourceProvider(),
                new ResourceLocation(ApocalypseZombies.MOD_ID, "orbit_sky"),
                DefaultVertexFormat.POSITION);
        event.registerShader(instance, loaded -> shader = loaded);
    }

    /** 在客户端 {@code RenderLevelStageEvent} 里调用；内部自己判断阶段/维度。 */
    public static void render(RenderLevelStageEvent event) {
        if (shader == null || event.getStage() != RenderLevelStageEvent.Stage.AFTER_SKY) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.level == null || minecraft.player == null) {
            return;
        }
        if (!minecraft.level.dimension().equals(OrbitDimension.LEVEL)) {
            return;
        }
        Camera camera = event.getCamera();
        double yaw = Math.toRadians(camera.getYRot());
        double pitch = Math.toRadians(camera.getXRot());
        double sy = Math.sin(yaw);
        double cy = Math.cos(yaw);
        double sp = Math.sin(pitch);
        double cp = Math.cos(pitch);
        float fx = (float) (-sy * cp);
        float fy = (float) (-sp);
        float fz = (float) (cy * cp);
        float rx = (float) (-cy);
        float rz = (float) (-sy);
        float ux = (float) (-sy * sp);
        float uy = (float) cp;
        float uz = (float) (cy * sp);

        float fov = (float) Math.toRadians(minecraft.options.fov().get());
        float tanHalf = (float) Math.tan(fov * 0.5F);
        float aspect = (float) minecraft.getWindow().getWidth()
                / Math.max(1.0F, (float) minecraft.getWindow().getHeight());

        shader.safeGetUniform("CamForward").set(fx, fy, fz);
        shader.safeGetUniform("CamRight").set(rx, 0.0F, rz);
        shader.safeGetUniform("CamUp").set(ux, uy, uz);
        shader.safeGetUniform("TanHalf").set(tanHalf);
        shader.safeGetUniform("Aspect").set(aspect);
        shader.safeGetUniform("Alpha").set(1.0F);
        // v5.0：把真实世界时间喂进 shader（此前 json 未声明该 uniform、Java 也未 set，
        // 星空/星云/云一直是静止的）。用秒，闪烁/流动的速率都按秒调。
        float seconds = (minecraft.level.getGameTime() + event.getPartialTick()) / 20.0F;
        shader.safeGetUniform("GameTime").set(seconds);

        RenderSystem.setShader(() -> shader);
        RenderSystem.disableDepthTest();
        RenderSystem.depthMask(false);
        RenderSystem.disableCull();
        RenderSystem.enableBlend();
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
    }
}
