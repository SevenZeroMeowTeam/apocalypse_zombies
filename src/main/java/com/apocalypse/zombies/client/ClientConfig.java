package com.apocalypse.zombies.client;

import net.minecraftforge.common.ForgeConfigSpec;
import net.minecraftforge.fml.ModLoadingContext;
import net.minecraftforge.fml.config.ModConfig;

/**
 * 纯客户端配置（v4.0 P3-c）。
 *
 * <p><b>为什么单独一份 spec 而不是塞进 {@link com.apocalypse.zombies.Config}：</b>
 * 那部分是 COMMON 配置，服务端与客户端共用、值必须一致；而「我要不要看别人的过场」
 * 是每个玩家自己的显示偏好，不该被服务器配置覆盖，也绝不能影响服务端权威逻辑。
 * Forge 的 {@link ModConfig.Type#CLIENT} 正好只存在于客户端游戏实例里。</p>
 *
 * <p><b>注册方式</b>：{@link com.apocalypse.zombies.ApocalypseZombies} 通过
 * {@code DistExecutor.unsafeRunWhenOn(Dist.CLIENT, ...)} 调 {@link #register()} ——
 * 专用服务器上这个类不会被加载，也就不会碰 {@code ModLoadingContext} 的客户端路径。</p>
 *
 * <p>目前只有一项：{@code films.broadcast_films}。默认 true（跟随服务端广播），
 * 关掉之后：仍然收到打击/相位/取消包、世界特效与 HUD 横幅照常，但镜头不会被拉去演过场 ——
 * 适合晕 3D、录屏、或只想第一时间看清脚下地形的玩家。</p>
 *
 * <p>v6.1 新增 {@code sky} 段：轻量天空/天气增强（总开关 + 太阳/月亮辉光 + 天气雾效），
 * v6.2 在同一段里加了植被色调（{@link com.apocalypse.zombies.client.VegetationTintEvents}）
 * 与全帧光照分级；v6.3.1 加 {@code texture_override}（写实日月云雨雪强行装进原版槽位，
 * 见 {@link com.apocalypse.zombies.client.sky.SkyTextureOverrides}）。渲染逻辑见
 * {@link com.apocalypse.zombies.client.sky.SkyWeatherEffects}。游戏内配置界面
 * （ApocalypseConfigScreen）只遍历 COMMON 的 {@code Config.values()}，本 spec 的项
 * （和 films 一样）通过 {@code config/apocalypse_zombies-client.toml} 编辑。</p>
 */
public final class ClientConfig {

    public static final ForgeConfigSpec SPEC;
    /** 是否接受别人（以及自己）打击的过场镜头广播；只影响镜头，不影响任何世界效果。 */
    public static final ForgeConfigSpec.BooleanValue BROADCAST_FILMS;

    // v6.1：轻量天空/天气增强。总开关管两个子开关，渲染实现见 client/sky/SkyWeatherEffects。
    /** 轻量天空/天气增强总开关：关掉 = 完全回到原版天空与雾。 */
    public static final ForgeConfigSpec.BooleanValue REALISTIC_SKY_EFFECTS;
    /** 太阳/满月加性辉光（月亮事件激活时自动跳过月亮那层；雨天随雨势淡出）。 */
    public static final ForgeConfigSpec.BooleanValue SKY_GLOW_HALOS;
    /** 天气雾效增强：雨浓雾暗、雪雾偏白、雷暴更深，随 rainLevel 平滑过渡。 */
    public static final ForgeConfigSpec.BooleanValue WEATHER_FOG_ENHANCE;
    /** 植被色调：草方块/高草/蕨/树叶的去饱和 + 暖偏移 + 轻微压暗（末日枯黄基调）。 */
    public static final ForgeConfigSpec.BooleanValue VEGETATION_TINT;
    /** 全帧环境光分级：关卡渲染末尾一层极低 alpha 的暖/冷/血色偏，统一地面与植被观感。 */
    public static final ForgeConfigSpec.BooleanValue AMBIENT_LIGHT_GRADE;
    /**
     * 把本模组的写实太阳 / 月面 / 云层 / 雨雪强行装进原版 environment 槽位。
     * 关掉 = 退回资源栈（原版、程序员艺术包、用户资源包按 options.txt 顺序生效）。
     */
    public static final ForgeConfigSpec.BooleanValue SKY_TEXTURE_OVERRIDE;

    static {
        ForgeConfigSpec.Builder builder = new ForgeConfigSpec.Builder();
        builder.comment("Client-only presentation options (never synced, never affect the server).")
                .push("films");
        BROADCAST_FILMS = builder
                .comment("Play the orbital-strike cutscene when a nearby strike is broadcast to you.",
                        "False = you keep the world effects and the spectator banner, but the camera",
                        "stays in your own eyes (also affects your own strike if it is broadcast).")
                .define("broadcast_films", true);
        builder.pop();

        // v6.1：轻量天空/天气增强（渲染实现见 client/sky/SkyWeatherEffects）。
        builder.comment("Lightweight sky / weather presentation (v6.1), client-only.",
                        "realistic_sky_effects is the master switch for everything below.")
                .push("sky");
        REALISTIC_SKY_EFFECTS = builder
                .comment("Master switch for the sky/weather enhancements (glow halos, weather fog).",
                        "False = vanilla sky and fog, nothing else.")
                .define("realistic_sky_effects", true);
        SKY_GLOW_HALOS = builder
                .comment("Additive glow halos around the sun and the full moon, drawn on vanilla's own",
                        "sky transform. The moon halo is skipped while a lunar event is active",
                        "(ClientEvents owns the moon then) and both halos fade out with rain intensity.",
                        "Needs realistic_sky_effects.")
                .define("sky_glow_halos", true);
        WEATHER_FOG_ENHANCE = builder
                .comment("Denser, darker fog while raining and whiter fog while snowing; thunderstorms go",
                        "further. Strength follows the rain level smoothly. Natural-sky dimensions only",
                        "(never the Nether, the End or the orbit dimension). Needs realistic_sky_effects.")
                .define("weather_fog_enhance", true);
        VEGETATION_TINT = builder
                .comment("Desaturate and warm the biome colour of grass, tall grass, ferns and every",
                        "leaf block, so the ground reads as dry and sun-bleached. Biome differences",
                        "are kept (the adjustment is the same affine shift for every biome).",
                        "The result is baked into chunk meshes: rebuilding a chunk picks up a change.",
                        "Needs realistic_sky_effects.")
                .define("vegetation_tint", true);
        AMBIENT_LIGHT_GRADE = builder
                .comment("A very low-alpha full-frame colour grade at the end of the level render:",
                        "warm at dawn/dusk, cold blue at night, red during a blood moon, greyer and",
                        "dimmer in rain. Gives the ground and the vegetation one shared ambient",
                        "light. Drawn during level rendering only, so the GUI and chat are never",
                        "tinted. Needs realistic_sky_effects.")
                .define("ambient_light_grade", true);
        SKY_TEXTURE_OVERRIDE = builder
                .comment("Force this mod's realistic sun / moon / clouds / rain / snow into vanilla's",
                        "environment texture slots (minecraft:textures/environment/*), so vanilla,",
                        "programmer_art and high_contrast packs cannot cover them — those packs sit",
                        "above mod_resources in the resource stack on this instance.",
                        "False = fall back to the resource stack (vanilla discs). Needs realistic_sky_effects.")
                .define("texture_override", true);
        builder.pop();
        SPEC = builder.build();
    }

    private ClientConfig() {
    }

    /** 只应在客户端模组构造阶段调用（由主类的 DistExecutor 分支进来）。 */
    public static void register() {
        ModLoadingContext.get().registerConfig(ModConfig.Type.CLIENT, SPEC,
                "apocalypse_zombies-client.toml");
    }
}
