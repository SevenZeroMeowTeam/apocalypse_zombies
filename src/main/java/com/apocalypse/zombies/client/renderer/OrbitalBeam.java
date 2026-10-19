package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import com.apocalypse.zombies.orbital.engine.StrikeProtocols;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.BufferUploader;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.Tesselator;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.blaze3d.vertex.VertexFormat;
import net.minecraft.client.Camera;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.ShaderInstance;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.api.distmarker.OnlyIn;
import net.minecraftforge.client.event.RegisterShadersEvent;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * 实体光柱 v5.1：移植参考包 {@code star_beam.fsh} 的体积渐变，改用世界空间圆柱 quad。
 *
 * <p>参考包是屏幕空间深度重建（需要 {@code scenePosAt}/{@code skyAt} 的深度副本）；
 * 我们不建深度副本（Embeddium 下 FBO 风险高），改由 Java 每帧画一根<b>面向相机的圆柱 quad</b>，
 * UV0 = (绕柱角/TAU, 沿柱高度)，片元着色器据此重建「面向相机程度」并算出四段体积渐变。</p>
 *
 * <p>只画三种协议的柱体：焚城（动能弹通道）、隔离（引力柱）、黑雨（陨石通道）。
 * 断层的矛、蜂群的巢荚、黎明的光速束保持原有的线条/圆环节奏 —— 它们的形态本来就不同。</p>
 *
 * <p>失败即静默：shader 注册失败时整个类不画，退回原有渲染，不影响游戏。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.MOD)
public final class OrbitalBeam {

    private static final int SEGMENTS = 20;
    private static ShaderInstance shader;

    private OrbitalBeam() {
    }

    @SubscribeEvent
    public static void onRegisterShaders(RegisterShadersEvent event) throws java.io.IOException {
        ShaderInstance instance = new ShaderInstance(event.getResourceProvider(),
                new ResourceLocation(ApocalypseZombies.MOD_ID, "orbit_beam"),
                DefaultVertexFormat.POSITION_TEX_COLOR);
        event.registerShader(instance, loaded -> shader = loaded);
    }

    /** 在客户端 {@code RenderLevelStageEvent} 里调用；内部自己判断阶段/协议。 */
    public static void render(RenderLevelStageEvent event) {
        if (shader == null) {
            return;
        }
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_TRANSLUCENT_BLOCKS) {
            return;
        }
        if (OrbitalCinematic.isSpaceStage()) {
            return; // 太空段由轨道舞台画，别叠加
        }
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.level == null || minecraft.player == null) {
            return;
        }
        if (!com.apocalypse.zombies.Config.ORBITAL_STRIKE_BEAM_ENABLED.get()) {
            return;
        }
        if (!com.apocalypse.zombies.client.OrbitalStrikeClientState.isActive()) {
            return;
        }
        net.minecraft.core.BlockPos target =
                com.apocalypse.zombies.client.OrbitalStrikeClientState.target();
        if (target == null) {
            return;
        }

        OrbitalStrikeMode mode = com.apocalypse.zombies.client.OrbitalStrikeClientState.mode();
        // 只有三种协议用实体柱：焚城 / 隔离 / 黑雨
        boolean isCannon = mode == OrbitalStrikeMode.CANNON
                && "cinder".equals(StrikeProtocols.protocolFor(mode).id());
        boolean isGravity = mode == OrbitalStrikeMode.GRAVITY;
        boolean isPlanet = mode == OrbitalStrikeMode.PLANET;
        if (!isCannon && !isGravity && !isPlanet) {
            return;
        }

        long elapsed = com.apocalypse.zombies.client.OrbitalStrikeClientState.elapsed();
        int lockTicks = com.apocalypse.zombies.client.OrbitalStrikeClientState.lockTicks();
        long impactAge = com.apocalypse.zombies.client.OrbitalStrikeClientState.impactAge();
        float partial = event.getPartialTick();
        double time = (minecraft.level.getGameTime() + partial) / 20.0F;

        // —— 时间轴：锁定末段细柱（瞄准线）→ 命中后主柱 12 tick
        double cx = target.getX() + 0.5D;
        double cz = target.getZ() + 0.5D;
        double baseY = target.getY() + 0.5D;
        int strikeRadius = com.apocalypse.zombies.client.OrbitalStrikeClientState.radius();
        double fullR = Math.max(0.6D, strikeRadius * 0.42D);

        float strength;
        float energy;
        float haze;
        float scanline;
        double radius;
        double topY;
        float coreR;
        float coreG;
        float coreB;
        float bodyR;
        float bodyG;
        float bodyB;
        float deepR;
        float deepG;
        float deepB;

        int rgb = StrikeProtocols.protocolFor(mode).color();
        bodyR = ((rgb >> 16) & 0xFF) / 255.0F;
        bodyG = ((rgb >> 8) & 0xFF) / 255.0F;
        bodyB = (rgb & 0xFF) / 255.0F;

        if (isPlanet) {
            // 黑雨：陨石砸出的是「又大又浅的坑」，柱体是冲击柱而不是贯穿井
            radius = fullR * 0.75D;
            topY = baseY + 26.0D;
            coreR = 1.0F; coreG = 0.97F; coreB = 0.90F;
            deepR = 0.55F; deepG = 0.02F; deepB = 0.02F;
            haze = 1.0F;
            scanline = 0.0F;
            energy = 1.0F;
            if (impactAge >= 0) {
                float age = impactAge + partial;
                strength = Mth.clamp(1.0F - age / 14.0F, 0.0F, 1.0F);
            } else {
                strength = 0.0F;
            }
        } else if (isGravity) {
            // 隔离：引力柱全程都在，向内塌缩的视觉由 Ease 曲线给
            radius = fullR * 0.6D;
            topY = baseY + 30.0D;
            coreR = 0.72F; coreG = 0.86F; coreB = 1.0F;
            deepR = 0.10F; deepG = 0.22F; deepB = 0.45F;
            haze = 0.7F;
            scanline = 0.35F;
            energy = 1.0F;
            if (impactAge >= 0) {
                float age = impactAge + partial;
                strength = Mth.clamp(1.0F - age / 20.0F, 0.0F, 1.0F);
            } else if (elapsed < lockTicks) {
                float p = Mth.clamp((float) elapsed / Math.max(1, lockTicks), 0.0F, 1.0F);
                strength = 0.45F * p;
                energy = 0.5F + 0.5F * p;
            } else {
                strength = 0.55F;
            }
        } else {
            // 焚城：动能弹通道 —— 锁定末段一根细瞄准线，命中后是主柱
            coreR = 1.0F; coreG = 0.98F; coreB = 0.92F;
            deepR = 0.62F; deepG = 0.0F; deepB = 0.02F;
            haze = 1.0F;
            scanline = 0.0F;
            if (impactAge >= 0) {
                float age = impactAge + partial;
                radius = fullR;
                topY = baseY + 30.0D;
                strength = Mth.clamp(1.0F - age / 16.0F, 0.0F, 1.0F);
                energy = 1.2F;
            } else {
                radius = Math.max(0.10D, fullR * 0.05D);
                topY = baseY + 220.0D;
                float p = Mth.clamp((float) elapsed / Math.max(1, lockTicks), 0.0F, 1.0F);
                // 只在锁定最后 25% 出现瞄准线
                strength = p < 0.75F ? 0.0F : (p - 0.75F) / 0.25F * 0.35F;
                energy = 0.6F;
            }
        }

        if (strength < 0.01F) {
            return;
        }

        // 顶点色 = 协议色（fsh 只做轻染色）
        float tr = bodyR;
        float tg = bodyG;
        float tb = bodyB;

        PoseStack pose = event.getPoseStack();
        Camera camera = event.getCamera();
        Vec3 camPos = camera.getPosition();
        pose.pushPose();
        pose.translate(-camPos.x, -camPos.y, -camPos.z);

        try {
            RenderSystem.setShader(() -> shader);
            shader.safeGetUniform("GameTime").set((float) time);
            shader.safeGetUniform("Radius").set((float) radius);
            shader.safeGetUniform("Strength").set(strength);
            shader.safeGetUniform("Energy").set(energy);
            shader.safeGetUniform("Haze").set(haze);
            shader.safeGetUniform("Core").set(coreR, coreG, coreB);
            shader.safeGetUniform("Body").set(bodyR, bodyG, bodyB);
            shader.safeGetUniform("Deep").set(deepR, deepG, deepB);
            shader.safeGetUniform("Scanline").set(scanline);
            RenderSystem.enableBlend();
            RenderSystem.defaultBlendFunc();
            RenderSystem.disableCull();
            RenderSystem.disableDepthTest();
            RenderSystem.depthMask(false);
            RenderSystem.setShaderColor(1.0F, 1.0F, 1.0F, 1.0F);

            drawCylinder(pose, cx, baseY, cz, radius, topY - baseY, tr, tg, tb);
        } catch (Throwable error) {
            // 任何 GL 问题只记一次 warn 并停止画（不影响游戏）
            ApocalypseZombies.LOGGER.warn("[天陨] 实体光柱绘制失败，已停用该层。", error);
            shader = null;
        } finally {
            RenderSystem.enableDepthTest();
            RenderSystem.depthMask(true);
            RenderSystem.enableCull();
            RenderSystem.disableBlend();
            pose.popPose();
        }
    }

    /** 画一根面向相机的圆柱：UV0.x 绕柱、UV0.y 沿高度，侧面双面（禁剔除）。 */
    private static void drawCylinder(PoseStack pose, double cx, double baseY, double cz,
                                     double radius, double height, float r, float g, float b) {
        var matrix = pose.last().pose();
        BufferBuilder builder = Tesselator.getInstance().getBuilder();
        builder.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.POSITION_TEX_COLOR);
        for (int i = 0; i < SEGMENTS; i++) {
            float a0 = (float) (Math.PI * 2.0D * i / SEGMENTS);
            float a1 = (float) (Math.PI * 2.0D * (i + 1) / SEGMENTS);
            float u0 = (float) i / SEGMENTS;
            float u1 = (float) (i + 1) / SEGMENTS;
            double x0 = cx + Math.cos(a0) * radius;
            double z0 = cz + Math.sin(a0) * radius;
            double x1 = cx + Math.cos(a1) * radius;
            double z1 = cz + Math.sin(a1) * radius;
            float y0 = (float) baseY;
            float y1 = (float) (baseY + height);
            VertexConsumer vc = builder;
            vc.vertex(matrix, (float) x0, y0, (float) z0).uv(u0, 0.0F).color(r, g, b, 1.0F).endVertex();
            vc.vertex(matrix, (float) x1, y0, (float) z1).uv(u1, 0.0F).color(r, g, b, 1.0F).endVertex();
            vc.vertex(matrix, (float) x1, y1, (float) z1).uv(u1, 1.0F).color(r, g, b, 1.0F).endVertex();
            vc.vertex(matrix, (float) x0, y1, (float) z0).uv(u0, 1.0F).color(r, g, b, 1.0F).endVertex();
        }
        BufferUploader.draw(builder.end());
    }
}
