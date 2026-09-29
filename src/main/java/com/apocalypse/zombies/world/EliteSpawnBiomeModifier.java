package com.apocalypse.zombies.world;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.registry.ModBiomeModifiers;
import com.apocalypse.zombies.registry.ModEntities;
import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;

import net.minecraft.core.Holder;
import net.minecraft.core.HolderSet;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.MobSpawnSettings;
import net.minecraftforge.common.world.BiomeModifier;
import net.minecraftforge.common.world.MobSpawnSettingsBuilder;
import net.minecraftforge.common.world.ModifiableBiomeInfo;

/**
 * 把六只精英加进主世界的怪物刷新池。
 *
 * <p>没有直接用 Forge 自带的 {@code forge:add_spawns}：它的权重写死在数据包 JSON 里，改个数字要重载数据包。
 * 这里权重现读 {@link Config}，服主在 config 里就能调稀有度，或者整只关掉自然生成。</p>
 *
 * <p>一次只放 1 只（minCount = maxCount = 1）。精英是「今晚撞上的麻烦」，不该像杂兵那样成群刷出来；
 * 想成群出现的地方是尸潮，那边由 HordeManager 按波次单独放。</p>
 */
public record EliteSpawnBiomeModifier(HolderSet<Biome> biomes) implements BiomeModifier {

    public static final Codec<EliteSpawnBiomeModifier> CODEC = RecordCodecBuilder.create(builder -> builder.group(
            Biome.LIST_CODEC.fieldOf("biomes").forGetter(EliteSpawnBiomeModifier::biomes)
    ).apply(builder, EliteSpawnBiomeModifier::new));

    @Override
    public void modify(Holder<Biome> biome, Phase phase, ModifiableBiomeInfo.BiomeInfo.Builder builder) {
        if (phase != Phase.ADD || !this.biomes.contains(biome) || !Config.ELITE_NATURAL_SPAWN.get()) {
            return;
        }
        int weight = Config.ELITE_SPAWN_WEIGHT.get();
        if (weight <= 0) {
            return;
        }
        MobSpawnSettingsBuilder spawns = builder.getMobSpawnSettings();
        spawns.addSpawn(MobCategory.MONSTER, spawn(ModEntities.SCREAMER.get(), weight));
        spawns.addSpawn(MobCategory.MONSTER, spawn(ModEntities.CRUSHER.get(), weight));
        spawns.addSpawn(MobCategory.MONSTER, spawn(ModEntities.CORRODER.get(), weight));
        spawns.addSpawn(MobCategory.MONSTER, spawn(ModEntities.MARKSMAN.get(), weight));
        spawns.addSpawn(MobCategory.MONSTER, spawn(ModEntities.BRIDE.get(), weight));
        int soldierWeight = Config.SOLDIER_SPAWN_WEIGHT.get();
        if (soldierWeight > 0) {
            spawns.addSpawn(MobCategory.MONSTER, spawn(ModEntities.SOLDIER.get(), soldierWeight));
        }
    }

    private static MobSpawnSettings.SpawnerData spawn(EntityType<?> type, int weight) {
        return new MobSpawnSettings.SpawnerData(type, weight, 1, 1);
    }

    @Override
    public Codec<? extends BiomeModifier> codec() {
        return ModBiomeModifiers.ELITE_SPAWNS.get();
    }
}
