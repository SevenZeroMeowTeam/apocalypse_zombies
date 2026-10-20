package com.apocalypse.zombies.client.sky;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.ClientConfig;
import com.apocalypse.zombies.client.ClientMoonState;
import com.apocalypse.zombies.orbit.OrbitDimension;
import com.mojang.blaze3d.platform.GlStateManager;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.Tesselator;
import com.mojang.blaze3d.vertex.VertexFormat;
import com.mojang.math.Axis;
import net.minecraft.client.Camera;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.GameRenderer;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraft.world.level.biome.Biome;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.client.event.ViewportEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;

/**
 * v6.1：轻量天空/天气增强（纯客户端演出层：不写世界数据、不发网络包、不建 Mixin）。
 *
 * <p><b>太阳/月亮辉光</b>：在 {@code RenderLevelStageEvent.Stage.AFTER_SKY} 用加性混合
 * （SRC_ALPHA × ONE）在太阳/月亮方位各画一层比原版天体大一圈的光晕 quad。纹理直接复用
 * 原版 {@code textures/environment/sun.png} 与 {@code textures/environment/moon_phases.png}
 * （4×2 相位格的左上格 = 满月），方位变换与原版天体及本模组 {@code ClientEvents#renderMoon}
 * 完全一致：{@code YP.rotationDegrees(-90)} + {@code XP.rotationDegrees(getTimeOfDay * 360)}，
 * quad 落在 ±{@link #HALO_DISTANCE} 的天幕平面上（+Y 朝太阳、-Y 朝月亮）。
 * 月亮事件激活时跳过月亮辉光 —— 那时 {@code ClientEvents} 的 renderSkyWash/renderMoon 已经
 * 接管了月亮表现，两套月亮叠在同一片天空上会打架；太阳辉光不参与互斥，可常驻。
 * 雨雪越大辉光越淡（暴雨基本熄灭），避免与雨幕贴图抢戏。</p>
 *
 * <p><b>天气雾效</b>：挂 {@code ViewportEvent.RenderFog}（往里收雾距；1.20.1 的 Forge 补丁
 * 会无条件采用事件值，该事件也不可 cancel）与 {@code ViewportEvent.ComputeFogColor}（调雾色）：
 * 雨天雾更浓更暗、雪天雾偏白，强度随 {@code level.getRainLevel(partialTick)} 平滑过渡，
 * 雷暴（{@code getThunderLevel}）再加深一层。注意 {@code ClientEvents} 里另有一个
 * {@code onComputeFogColor}（月亮事件/黑雨染色）—— 两个监听者都会被调用，各自按
 * lerp 叠加，互不覆盖。</p>
 *
 * <p><b>维度边界</b>：只在「自然天空」维度生效 —— {@code level.dimensionType().natural()}
 * 为 true 且不是 {@link OrbitDimension#LEVEL}（轨道维度有自己的 OrbitSkyShader /
 * OrbitSpacePass 天幕，不许再叠新效果）。下界/末地（natural=false）与轨道维度一律不碰。</p>
 *
 * <p><b>开关</b>：全部走 {@link ClientConfig}（CLIENT spec，默认全开）：
 * {@code sky.realistic_sky_effects} 总开关 + {@code sky.sky_glow_halos} /
 * {@code sky.weather_fog_enhance}。性能上渲染路径零分配（Tesselator 共享 builder，
 * 事件里只做标量运算与状态切换）。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class SkyWeatherEffects {

    // 复用 minecraft 命名空间的原版天体贴图（并行工作流替换的就是这套路径）。
    // 47.4 起两个 ResourceLocation 构造器都标了 forRemoval，用 Forge 的工厂替代。
    private static final ResourceLocation SUN_LOCATION =
            ResourceLocation.withDefaultNamespace("textures/environment/sun.png");
    private static final ResourceLocation MOON_LOCATION =
            ResourceLocation.withDefaultNamespace("textures/environment/moon_phases.png");

    /** 太阳辉光 quad 的半边长（原版太阳本体是 30，光晕大一圈才读得出「光」）。 */
    private static final float SUN_HALO_SIZE = 62.0F;
    /** 月亮辉光 quad 的半边长（原版月亮本体是 20）。 */
    private static final float MOON_HALO_SIZE = 44.0F;
    /** 辉光所在的天幕距离，与原版太阳/月亮同一平面（+Y 太阳 / -Y 月亮）。 */
    private static final float HALO_DISTANCE = 100.0F;
    /** 晴夜太阳/满月辉光的峰值不透明度（加性混合，亮度由它控）。 */
    private static final float SUN_HALO_ALPHA = 0.50F;
    private static final float MOON_HALO_ALPHA = 0.34F;
    /** 雨雪对辉光的压制比例：rainLevel=1（暴雨/暴雪）时辉光只剩 15%。 */
    private static final float HALO_RAIN_DIM = 0.85F;

    private SkyWeatherEffects() {
    }

    // ------------------------------------------------------------------ 辉光

    @SubscribeEvent
    public static void onRenderLevelStage(RenderLevelStageEvent event) {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_SKY) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        ClientLevel level = minecraft.level;
        if (level == null || !inVanillaSkyDimension(level)) {
            return;
        }
        // v6.1：开关读取（总开关 + 辉光子开关，CLIENT spec，Forge 内部有缓存）。
        if (!ClientConfig.REALISTIC_SKY_EFFECTS.get() || !ClientConfig.SKY_GLOW_HALOS.get()) {
            return;
        }
        float partialTick = event.getPartialTick();
        float fade = 1.0F - level.getRainLevel(partialTick) * HALO_RAIN_DIM;
        if (fade < 0.05F) {
            return;
        }
        renderHalo(event.getPoseStack(), level, partialTick, true, fade);
        // v6.1：月亮事件激活时既有 renderSkyWash/renderMoon 已经接管月亮表现（见
        // ClientEvents.onRenderLevelStage），必须跳过月亮辉光避免叠加打架；太阳辉光照画。
        if (!ClientMoonState.getMoonEvent().isActive()) {
            renderHalo(event.getPoseStack(), level, partialTick, false, fade);
        }
    }

    /**
     * 画一层辉光 quad。进出场状态保存/恢复沿用 {@code ClientEvents#renderMoon} 的同一套写法：
     * pushPose → 变换 → 开混合/关深度写入 → 画 → 逐项还原 → popPose。
     */
    private static void renderHalo(PoseStack pose, ClientLevel level, float partialTick,
                                   boolean sun, float fade) {
        pose.pushPose();
        // 与原版天体同一套时间角变换（参照 ClientEvents.renderMoon：YP(-90) + XP(timeOfDay*360)）。
        pose.mulPose(Axis.YP.rotationDegrees(-90.0F));
        pose.mulPose(Axis.XP.rotationDegrees(level.getTimeOfDay(partialTick) * 360.0F));
        Matrix4f matrix = pose.last().pose();

        float size = sun ? SUN_HALO_SIZE : MOON_HALO_SIZE;
        float y = sun ? HALO_DISTANCE : -HALO_DISTANCE;

        RenderSystem.setShader(GameRenderer::getPositionTexShader);
        RenderSystem.setShaderTexture(0, sun ? SUN_LOCATION : MOON_LOCATION);
        if (sun) {
            RenderSystem.setShaderColor(1.0F, 0.95F, 0.82F, SUN_HALO_ALPHA * fade);
        } else {
            RenderSystem.setShaderColor(0.80F, 0.86F, 1.0F, MOON_HALO_ALPHA * fade);
        }
        RenderSystem.enableBlend();
        // 加性混合：SRC_ALPHA × ONE（alpha 通道 ONE × ZERO 原样保留，不污染目标 alpha）。
        RenderSystem.blendFuncSeparate(
                GlStateManager.SourceFactor.SRC_ALPHA,
                GlStateManager.DestFactor.ONE,
                GlStateManager.SourceFactor.ONE,
                GlStateManager.DestFactor.ZERO);
        RenderSystem.depthMask(false);

        Tesselator tesselator = Tesselator.getInstance();
        BufferBuilder buffer = tesselator.getBuilder();
        buffer.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.POSITION_TEX);
        if (sun) {
            // 与原版太阳 quad 同一绕向（+Y 平面，参照 LevelRenderer.renderSky）。
            buffer.vertex(matrix, -size, y, -size).uv(0.0F, 0.0F).endVertex();
            buffer.vertex(matrix, size, y, -size).uv(1.0F, 0.0F).endVertex();
            buffer.vertex(matrix, size, y, size).uv(1.0F, 1.0F).endVertex();
            buffer.vertex(matrix, -size, y, size).uv(0.0F, 1.0F).endVertex();
        } else {
            // 与本模组 renderMoon 同一绕向（-Y 平面）；满月格 = moon_phases.png 左上 4×2 格的 (0,0)。
            buffer.vertex(matrix, -size, y, size).uv(0.25F, 0.5F).endVertex();
            buffer.vertex(matrix, size, y, size).uv(0.0F, 0.5F).endVertex();
            buffer.vertex(matrix, size, y, -size).uv(0.0F, 0.0F).endVertex();
            buffer.vertex(matrix, -size, y, -size).uv(0.25F, 0.0F).endVertex();
        }
        tesselator.end();

        RenderSystem.depthMask(true);
        RenderSystem.defaultBlendFunc();
        RenderSystem.setShaderColor(1.0F, 1.0F, 1.0F, 1.0F);
        RenderSystem.disableBlend();
        pose.popPose();
    }

    // ------------------------------------------------------------------ 天气雾效

    /** 雾距增强：雨/雪把雾往里收（雪收得少些），雷暴再压一层；下限 0.4 保证暴雨里还能看清身位。 */
    @SubscribeEvent
    public static void onRenderFog(ViewportEvent.RenderFog event) {
        ClientLevel level = Minecraft.getInstance().level;
        if (level == null || !inVanillaSkyDimension(level) || !weatherFogEnabled()) {
            return;
        }
        float rain = level.getRainLevel((float) event.getPartialTick());
        if (rain <= 0.0F) {
            return;
        }
        boolean snow = isSnowfallAt(level, event.getCamera());
        float thunder = level.getThunderLevel((float) event.getPartialTick());
        float dense = (snow ? 0.28F : 0.40F) * rain + 0.12F * thunder;
        event.scaleFarPlaneDistance(Mth.clamp(1.0F - dense, 0.40F, 1.0F));
    }

    /**
     * 雾色增强：雨天更暗更冷、雪天偏白、雷暴再压暗一层。
     * ClientEvents.onComputeFogColor（月亮/黑雨染色）是另一个监听者，两边按 lerp 顺序叠加。
     */
    @SubscribeEvent
    public static void onComputeFogColor(ViewportEvent.ComputeFogColor event) {
        ClientLevel level = Minecraft.getInstance().level;
        if (level == null || !inVanillaSkyDimension(level) || !weatherFogEnabled()) {
            return;
        }
        float rain = level.getRainLevel((float) event.getPartialTick());
        if (rain <= 0.0F) {
            return;
        }
        boolean snow = isSnowfallAt(level, event.getCamera());
        float thunder = level.getThunderLevel((float) event.getPartialTick());
        float red = event.getRed();
        float green = event.getGreen();
        float blue = event.getBlue();
        float luminance = (red + green + blue) * (1.0F / 3.0F);
        if (snow) {
            // 雪天雾偏白：向亮灰白收敛；目标里留 35% 原亮度打底，夜晚不会死白。
            float strength = rain * 0.55F;
            float target = Mth.lerp(0.35F, luminance, 0.80F);
            event.setRed(Mth.lerp(strength, red, target * 0.96F));
            event.setGreen(Mth.lerp(strength, green, target * 0.99F));
            event.setBlue(Mth.lerp(strength, blue, Math.min(1.0F, target * 1.04F)));
        } else {
            // 雨天雾更浓更暗：按当前亮度向冷灰收敛（夜晚只会更暗，不会被反向提亮）。
            float strength = rain * 0.50F;
            event.setRed(Mth.lerp(strength, red, luminance * 0.86F));
            event.setGreen(Mth.lerp(strength, green, luminance * 0.90F));
            event.setBlue(Mth.lerp(strength, blue, luminance * 0.97F));
        }
        if (thunder > 0.0F) {
            // 雷暴再加深一层（雷暴指数由 getThunderLevel 给出，与雨势独立）。
            float darker = thunder * 0.16F;
            event.setRed(Math.max(0.0F, event.getRed() - darker));
            event.setGreen(Math.max(0.0F, event.getGreen() - darker));
            event.setBlue(Math.max(0.0F, event.getBlue() - darker * 1.1F));
        }
    }

    // ------------------------------------------------------------------ 门槛

    /**
     * 只在「自然天空」维度生效：下界/末地的 {@code dimensionType().natural()} 是 false，
     * 轨道维度再显式排除（那里有本模组自己的天幕渲染，见 OrbitSkyShader/OrbitSpacePass）。
     */
    private static boolean inVanillaSkyDimension(ClientLevel level) {
        return level.dimensionType().natural()
                && !level.dimension().equals(OrbitDimension.LEVEL);
    }

    /** 天气雾效开关：总开关 + 子开关（辉光走自己的 SKY_GLOW_HALOS）。 */
    private static boolean weatherFogEnabled() {
        return ClientConfig.REALISTIC_SKY_EFFECTS.get() && ClientConfig.WEATHER_FOG_ENHANCE.get();
    }

    /** 相机所在生物群系此刻的降水形态（getPrecipitationAt 已含温度/高度判定：冷=雪）。 */
    private static boolean isSnowfallAt(ClientLevel level, Camera camera) {
        BlockPos pos = camera.getBlockPosition();
        return level.getBiome(pos).value().getPrecipitationAt(pos) == Biome.Precipitation.SNOW;
    }
}
