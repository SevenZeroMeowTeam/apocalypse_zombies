package com.apocalypse.zombies.client;

import com.apocalypse.zombies.client.gui.ApocalypseConfigScreen;

import net.minecraftforge.client.ConfigScreenHandler;
import net.minecraftforge.fml.ModLoadingContext;

/**
 * 把模组配置界面挂到「模组列表 → 配置」按钮上（1.1.79）。
 *
 * <p>为什么单独一个类：{@link ConfigScreenHandler} 与 {@link ApocalypseConfigScreen} 都是
 * 纯客户端的（{@code Screen} / {@code Minecraft} 这些类在专用服务器上根本不存在）。
 * 注册动作只能从主类经 {@code DistExecutor.unsafeRunWhenOn(Dist.CLIENT, ...)} 进来 ——
 * 服务器上这个方法**永远不会被调用**，类也就永远不会被加载。</p>
 *
 * <p>Forge 1.19 起就没有内置的配置编辑器了（老的 {@code ConfigurationScreen} 已被移除），
 * 所以要自己画一个：{@link ApocalypseConfigScreen} 直接读 {@link com.apocalypse.zombies.Config}
 * 的静态配置项，改完写回同一份 {@code config/apocalypse_zombies-common.toml}。</p>
 */
public final class ModConfigScreens {

    private ModConfigScreens() {
    }

    /** 只应在客户端调用（注册扩展点必须在模组构造阶段）。 */
    public static void register() {
        ModLoadingContext.get().registerExtensionPoint(
                ConfigScreenHandler.ConfigScreenFactory.class,
                () -> new ConfigScreenHandler.ConfigScreenFactory(
                        (minecraft, parent) -> new ApocalypseConfigScreen(parent)));
    }
}
