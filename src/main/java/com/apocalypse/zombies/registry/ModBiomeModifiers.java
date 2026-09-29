package com.apocalypse.zombies.registry;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.world.EliteSpawnBiomeModifier;
import com.mojang.serialization.Codec;

import net.minecraftforge.common.world.BiomeModifier;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

/**
 * 生物群系修饰器的序列化器。注册表键是 {@link ForgeRegistries.Keys#BIOME_MODIFIER_SERIALIZERS}，
 * 数据包里的 {@code data/apocalypse_zombies/forge/biome_modifier/*.json} 靠 {@code type} 字段对上这里的名字。
 */
public final class ModBiomeModifiers {

    public static final DeferredRegister<Codec<? extends BiomeModifier>> SERIALIZERS =
            DeferredRegister.create(ForgeRegistries.Keys.BIOME_MODIFIER_SERIALIZERS, ApocalypseZombies.MOD_ID);

    public static final RegistryObject<Codec<EliteSpawnBiomeModifier>> ELITE_SPAWNS =
            SERIALIZERS.register("elite_spawns", () -> EliteSpawnBiomeModifier.CODEC);

    private ModBiomeModifiers() {
    }

    public static void register(IEventBus modBus) {
        SERIALIZERS.register(modBus);
    }
}
