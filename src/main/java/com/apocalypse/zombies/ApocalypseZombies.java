package com.apocalypse.zombies;

import com.apocalypse.zombies.command.ApocalypseCommand;
import com.apocalypse.zombies.event.CommonEvents;
import com.apocalypse.zombies.network.NetworkHandler;
import com.apocalypse.zombies.registry.ModBiomeModifiers;
import com.apocalypse.zombies.registry.ModEffects;
import com.apocalypse.zombies.registry.ModEntities;
import com.apocalypse.zombies.registry.ModItems;
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
        ModEffects.register(modBus);
        ModSounds.register(modBus);
        ModBiomeModifiers.register(modBus);
        ModSpawns.register(modBus);

        ModLoadingContext.get().registerConfig(ModConfig.Type.COMMON, Config.SPEC, "apocalypse_zombies-common.toml");

        MinecraftForge.EVENT_BUS.register(CommonEvents.class);
        MinecraftForge.EVENT_BUS.addListener(this::onRegisterCommands);

        NetworkHandler.register();

        LOGGER.info("Apocalypse Zombies loaded: the night is no longer yours.");
    }

    private void onRegisterCommands(RegisterCommandsEvent event) {
        ApocalypseCommand.register(event.getDispatcher());
    }
}
