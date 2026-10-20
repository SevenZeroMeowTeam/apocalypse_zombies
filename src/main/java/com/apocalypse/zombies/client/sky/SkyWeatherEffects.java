package com.apocalypse.zombies.client.sky;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.ClientConfig;
import com.apocalypse.zombies.client.ClientMoonState;
import com.apocalypse.zombies.moon.MoonEvent;
import com.apocalypse.zombies.orbit.OrbitDimension;
import com.mojang.blaze3d.platform.GlStateManager;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.Tesselator;
import com.mojang.blaze3d.vertex.VertexFormat;
import com.mojang.blaze3d.vertex.VertexSorting;
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
 * <p><b>全帧光照分级</b>：{@code RenderLevelStageEvent.Stage.AFTER_LEVEL} 是关卡渲染的收尾点
 * （见 {@code GameRenderer#renderLevel}：它在 {@code levelRenderer.renderLevel} 之后、手持物与
 * GUI 之前派发，且已回到主 framebuffer），在这里叠一层极低 alpha 的全屏色调，给地面与植被一个
 * 统一的「环境光」感：日出/黄昏偏暖、夜晚偏冷蓝、血月偏红、雨雪向灰收敛并减淡。画的是屏幕空间
 * quad（临时换正交投影，做法与 {@code ClientEvents#renderSkyWash} 一致），只存在于关卡渲染阶段，
 * GUI/聊天栏在它之后由各自的投影重新绘制，永远不会被染色。</p>
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

    /**
     * 天体（太阳/月亮）相对原版的缩放比例：<b>1.0 = 原大小</b>（与 6.0.0 观感一致）。
     * <b>本常量只是比例文档，不参与任何计算。</b>
     *
     * <p><b>为什么不能乘进 quad 常量：</b>屏幕上的天体尺寸 = quad 比例 × 贴图里圆盘的占比，
     * 两个比例是相乘的。45% 已经实现在贴图里 —— {@code sun.png} / {@code moon_phases.png} 的
     * 可见圆盘被 {@code tools/env_celestial_scale.py}（其 SCALE 必须与这里一致）缩到 45% 并居中
     * 回原画布（画布尺寸不变、4×2 相位格各自居中），四周留透明边；原版 {@code LevelRenderer}
     * 写死的 quad（太阳 30、月亮 20 单位）保持原值不动。此时：</p>
     * <ul>
     *   <li>原版自绘太阳：{@code 30 × 1.0 = 30}（原尺寸）；</li>
     *   <li>本模组辉光跨度：{@code 2 × 62 × 1.0 = 124}（原尺寸）；</li>
     *   <li>{@code ClientEvents#renderMoon} 的月亮：{@code 2 × 20 × 1.0 = 40}，与同一时刻原版
     *       月亮的 40 完全对齐。</li>
     * </ul>
     * <p><b>历史：</b>6.1.0 曾把本常量设为 0.45（日月缩到 45%），实机观感“日月失去气势”，
     * 已回退到 1.0。若要重新缩小，只改本常量与 {@code tools/env_celestial_scale.py} 的
     * {@code CELESTIAL_SCALE}，不要动 quad 常量。</p>
     * <p>一旦再把本常量乘进 quad（例如 {@code SUN_HALO_SIZE = 62 * 0.45}），屏幕尺寸就变成
     * 0.45² ≈ 20%：辉光只剩 25.1（原 124），而 {@code renderMoon} 的月亮只剩 8.1 —— 比同一时刻
     * 原版月亮的 18 小一半，那层月亮本来要精确盖住原版月亮，缩小后盖不住，会漏出一圈原版月亮。
     * 所以：<b>禁止</b>把 {@code CELESTIAL_SCALE} 乘进任何 quad 常量。</p>
     */
    public static final float CELESTIAL_SCALE = 1.0F;
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

    // ------------------------------------------------------------------ 全帧光照分级

    /** 分级层在正午的不透明度：几乎只是给整帧加一点暖灰，不压暗画面。 */
    private static final float GRADE_ALPHA_DAY = 0.030F;
    /** 日出/黄昏峰值不透明度（暖色）。 */
    private static final float GRADE_ALPHA_HORIZON = 0.10F;
    /** 深夜峰值不透明度（冷蓝）。 */
    private static final float GRADE_ALPHA_NIGHT = 0.085F;
    /** 地平线暖色带宽：|sin(日高角)| 小于它就按日出/黄昏处理。 */
    private static final float HORIZON_BAND = 0.30F;
    /** 夜晚权重满格所需的「太阳沉到地平线下」幅度。 */
    private static final float NIGHT_RAMP = 0.80F;
    /** 血月对分级层的红色偏移强度（按夜晚权重缩放）。 */
    private static final float BLOOD_RED_BIAS = 0.55F;
    /** 雨雪把分级层向中性灰收敛并减淡的比例（雨幕本身已经压低了对比）。 */
    private static final float GRADE_RAIN_FADE = 0.45F;

    /**
     * 全帧柔和光照分级：只在关卡渲染的最后一阶段画一层极低 alpha 全屏色偏。
     *
     * <p><b>阶段为什么是 AFTER_LEVEL</b>：它在 {@code GameRenderer#renderLevel}（GameRenderer.java
     * :1128）里紧跟 {@code levelRenderer.renderLevel(...)}（:1126）之后派发，前面是手持物
     * （:1130-1133）与 GUI（:945 {@code gui.render}）—— 所以这一层压在所有地面与植被之上，而
     * GUI/聊天栏在它之后用自己的正交投影重画，不会被波及。更早的阶段（如 AFTER_SKY）画了会被后面
     * 的实体/区块/云整片盖掉，只剩天空被染色。</p>
     *
     * <p>不选 AFTER_WEATHER 的理由：它在 LevelRenderer 里分两个分支派发（LevelRenderer.java:1402-1418），
     * Fabulous 画质下位于 {@code WEATHER_TARGET.setupRenderState()}（:1403）与
     * {@code clearRenderState()}（:1408）之间，此时绑定的是天气 framebuffer，分级层会被
     * transparencyChain 二次合成；而 AFTER_LEVEL 在 {@code clearRenderState}（:1408）、
     * {@code transparencyChain.process}（:1409）、{@code bindWrite(false)}（:1410）之后，三种画质
     * 都落在主 framebuffer 上，没有合成歧义。此处的投影仍是关卡透视
     * （GameRenderer.java:1114 → {@code resetProjectionMatrix}:870 用
     * {@code VertexSorting.DISTANCE_TO_ORIGIN}），正是下面还原投影时用的那个。</p>
     */
    @SubscribeEvent
    public static void onRenderLevelStageGrade(RenderLevelStageEvent event) {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_LEVEL) {
            return;
        }
        if (!ClientConfig.REALISTIC_SKY_EFFECTS.get() || !ClientConfig.AMBIENT_LIGHT_GRADE.get()) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        ClientLevel level = minecraft.level;
        if (level == null || !inVanillaSkyDimension(level)) {
            return;
        }
        float partialTick = event.getPartialTick();
        // 原版时间轴：0 = 日出、6000 = 正午、12000 = 日落、18000 = 午夜。
        float dayFraction = ((level.getDayTime() % 24000L) + partialTick) / 24000.0F;
        float sunHeight = Mth.sin(dayFraction * Mth.TWO_PI);   // +1 正午，-1 午夜
        float horizon = Mth.clamp(1.0F - Math.abs(sunHeight) / HORIZON_BAND, 0.0F, 1.0F);
        float night = Mth.clamp(-sunHeight / NIGHT_RAMP, 0.0F, 1.0F);
        float day = Mth.clamp(1.0F - horizon - night, 0.0F, 1.0F);

        float red = 0.72F * horizon + 0.52F * day + 0.20F * night;
        float green = 0.38F * horizon + 0.52F * day + 0.30F * night;
        float blue = 0.20F * horizon + 0.50F * day + 0.58F * night;
        float alpha = GRADE_ALPHA_HORIZON * horizon + GRADE_ALPHA_DAY * day
                + GRADE_ALPHA_NIGHT * night;

        // 月相：血月（含超级血月）在夜里把分级层推红，普通月亮事件不动色相。
        MoonEvent moon = ClientMoonState.getMoonEvent();
        if (moon.isActive() && moon.isBloodMoon()) {
            float bias = BLOOD_RED_BIAS * Math.max(night, 0.25F);
            red = Mth.clamp(red + 0.30F * bias, 0.0F, 1.0F);
            green *= 1.0F - 0.45F * bias;
            blue *= 1.0F - 0.60F * bias;
            alpha += 0.02F * bias;
        }

        // 天气：雨/雪把色偏收敛成中性灰并减淡，暴雨里只剩一层薄雾。
        float rain = level.getRainLevel(partialTick);
        if (rain > 0.0F) {
            float luma = (red + green + blue) * (1.0F / 3.0F);
            float mix = rain * 0.60F;
            red = Mth.lerp(mix, red, luma);
            green = Mth.lerp(mix, green, luma);
            blue = Mth.lerp(mix, blue, luma);
            alpha *= 1.0F - GRADE_RAIN_FADE * rain;
        }

        drawFullScreenGrade(minecraft, red, green, blue, Math.min(alpha, 0.18F));
    }

    /** 屏幕空间全屏 color quad（临时正交投影 + 反解当前 modelview，进出场状态逐项还原）。 */
    private static void drawFullScreenGrade(Minecraft minecraft, float red, float green,
                                            float blue, float alpha) {
        if (alpha <= 0.001F) {
            return;
        }
        int width = minecraft.getWindow().getWidth();
        int height = minecraft.getWindow().getHeight();

        Matrix4f previousProjection = RenderSystem.getProjectionMatrix();
        PoseStack modelView = RenderSystem.getModelViewStack();

        modelView.pushPose();
        modelView.mulPoseMatrix(new Matrix4f(RenderSystem.getModelViewMatrix()).invert());
        RenderSystem.applyModelViewMatrix();
        RenderSystem.setProjectionMatrix(
                new Matrix4f().setOrtho(0.0F, (float) width, (float) height, 0.0F, -1000.0F, 1000.0F),
                VertexSorting.ORTHOGRAPHIC_Z);

        RenderSystem.disableDepthTest();
        RenderSystem.depthMask(false);
        RenderSystem.disableCull();
        RenderSystem.enableBlend();
        RenderSystem.defaultBlendFunc();
        RenderSystem.setShader(GameRenderer::getPositionColorShader);

        Tesselator tesselator = Tesselator.getInstance();
        BufferBuilder buffer = tesselator.getBuilder();
        buffer.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.POSITION_COLOR);
        buffer.vertex(0.0F, (float) height, 0.0F).color(red, green, blue, alpha).endVertex();
        buffer.vertex((float) width, (float) height, 0.0F).color(red, green, blue, alpha).endVertex();
        buffer.vertex((float) width, 0.0F, 0.0F).color(red, green, blue, alpha).endVertex();
        buffer.vertex(0.0F, 0.0F, 0.0F).color(red, green, blue, alpha).endVertex();
        tesselator.end();

        RenderSystem.disableBlend();
        RenderSystem.enableCull();
        RenderSystem.depthMask(true);
        RenderSystem.enableDepthTest();
        RenderSystem.getModelViewStack().popPose();
        RenderSystem.applyModelViewMatrix();
        RenderSystem.setProjectionMatrix(previousProjection, VertexSorting.DISTANCE_TO_ORIGIN);
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
