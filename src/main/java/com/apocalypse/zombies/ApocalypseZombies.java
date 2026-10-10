package com.apocalypse.zombies;

import com.apocalypse.zombies.command.ApocalypseCommand;
import com.apocalypse.zombies.event.CommonEvents;
import com.apocalypse.zombies.network.NetworkHandler;
import com.apocalypse.zombies.registry.ModBiomeModifiers;
import com.apocalypse.zombies.registry.ModEffects;
import com.apocalypse.zombies.registry.ModEntities;
import com.apocalypse.zombies.registry.ModItems;
import com.apocalypse.zombies.registry.ModMenus;
import com.apocalypse.zombies.registry.ModSounds;
import com.apocalypse.zombies.registry.ModSpawns;
import com.mojang.logging.LogUtils;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.fml.ModLoadingContext;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.config.ModConfig;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;
import net.minecraftforge.fml.event.config.ModConfigEvent;
import net.minecraftforge.fml.DistExecutor;
import net.minecraftforge.api.distmarker.Dist;
import org.slf4j.Logger;

/**
 * Apocalypse Zombies — a zombie apocalypse that escalates.
 *
 * <p>Zombies climb a six-step evolution ladder as the world ages and can evolve mid-fight; the night
 * sky rolls one of six lunar events that recolour the moon and sky while changing the rules of the
 * night; and blood moons (or unlucky ordinary ones) trigger a four-wave siege whose population is
 * rolled fresh every wave.</p>
 *
 * <p>On top of the vanilla lines sit four hand-tuned special hostiles — 尖啸者 / 碎颅者 / 腐蚀者 /
 * 骸骨射手 — each with its own telegraphed cast and payoff. They deliberately stay outside the
 * evolution ladder; see {@link com.apocalypse.zombies.entity.EliteAbility}.</p>
 */
@Mod(ApocalypseZombies.MOD_ID)
public class ApocalypseZombies {

    public static final String MOD_ID = "apocalypse_zombies";
    public static final Logger LOGGER = LogUtils.getLogger();

    public ApocalypseZombies() {
        IEventBus modBus = FMLJavaModLoadingContext.get().getModEventBus();
        ModItems.register(modBus);
        ModEntities.register(modBus);
        ModMenus.register(modBus);
        ModEffects.register(modBus);
        ModSounds.register(modBus);
        ModBiomeModifiers.register(modBus);
        ModSpawns.register(modBus);

        ModLoadingContext.get().registerConfig(ModConfig.Type.COMMON, Config.SPEC, "apocalypse_zombies-common.toml");

        // 「模组列表 → 配置」按钮：注册的是客户端配置界面，纯客户端类，服务器上这个分支不会走
        // （DistExecutor 保证那个方法连类都不会被加载）。
        DistExecutor.unsafeRunWhenOn(Dist.CLIENT,
                () -> com.apocalypse.zombies.client.ModConfigScreens::register);

        // 启动自检：配置枚举器（= 图形界面列的那几项）在真机上到底数出多少个。
        // 之所以要往日志里写一行：那枚举器是反射实现的，只在编译期断言「源码里有 151 个字段」
        // 证明不了运行期 —— 实机探针就是靠这行日志钉住这个数。
        LOGGER.info("Config registry: {} entries (exactly what the in-game config screen lists).",
                Config.values().size());

        // 运行期真值**不能在这里读** —— 构造阶段配置还没 load，读值会抛
        // `IllegalStateException: Cannot get config value before config is loaded.`，
        // 专用服务器直接起不来（1.1.79 第一版就踩了这个，改成读配置的回调里打）。
        modBus.addListener(this::onConfigLoaded);

        MinecraftForge.EVENT_BUS.register(CommonEvents.class);
        MinecraftForge.EVENT_BUS.addListener(this::onRegisterCommands);

        NetworkHandler.register();

        LOGGER.info("Apocalypse Zombies loaded: the night is no longer yours.");
    }

    private void onRegisterCommands(RegisterCommandsEvent event) {
        ApocalypseCommand.register(event.getDispatcher());
    }

    /**
     * 配置读进内存之后才读得出值 —— 这行日志是实机探针认的「上限到底是多少」的唯一口径：
     * Forge 在**读取时**校正越界值（日志里那句 {@code corrected from 256 to its default, 64}），
     * 所以配置文件里可能还写着越界的数，只有运行期真值算数。
     */
    private void onConfigLoaded(ModConfigEvent.Loading event) {
        LOGGER.info("Cat girl mining: mine_max_blocks={} (domain 1..64), mine_radius={} (domain 4..64).",
                Config.CAT_GIRL_MINE_MAX_BLOCKS.get(), Config.CAT_GIRL_MINE_RADIUS.get());
    }
}
