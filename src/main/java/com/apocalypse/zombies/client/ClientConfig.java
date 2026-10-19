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
 */
public final class ClientConfig {

    public static final ForgeConfigSpec SPEC;
    /** 是否接受别人（以及自己）打击的过场镜头广播；只影响镜头，不影响任何世界效果。 */
    public static final ForgeConfigSpec.BooleanValue BROADCAST_FILMS;

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
