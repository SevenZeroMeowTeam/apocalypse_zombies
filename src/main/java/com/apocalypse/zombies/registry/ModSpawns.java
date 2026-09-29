package com.apocalypse.zombies.registry;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.SoldierZombie;

import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.AABB;
import net.minecraft.util.RandomSource;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.MobSpawnType;
import net.minecraft.world.entity.SpawnPlacements;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.level.ServerLevelAccessor;
import net.minecraft.world.level.biome.Biomes;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.fml.event.lifecycle.FMLCommonSetupEvent;
import net.minecraftforge.registries.RegistryObject;

/**
 * 自然生成的登记。
 *
 * <p>{@link SpawnPlacements#register} 不登记的话，世界刷怪器根本不会考虑这个 EntityType——biome modifier
 * 里加的生成条目会被静默跳过（刷怪时查不到放置类型就直接否掉），所以这一步和 biome modifier 是配套的，缺一不可。</p>
 *
 * <p>六只都走原版怪物的判定（ON_GROUND + 黑暗度检查），也就是跟僵尸抢同一批刷新名额；
 * 残兵在此基础上多一条同伙上限（见 {@link #canSoldierSpawn}）：它是最适合成群出现在一条街上的那只，
 * 单只稀有度和同屏密度分别有旋钮，见 config 的 soldier_spawn_weight / soldier_max_nearby；
 * 具体出不出、多稀有，由 {@link com.apocalypse.zombies.world.EliteSpawnBiomeModifier} 读 config 的权重决定。</p>
 */
public final class ModSpawns {

    private ModSpawns() {
    }

    public static void register(IEventBus modBus) {
        modBus.addListener(ModSpawns::onCommonSetup);
    }

    private static void onCommonSetup(FMLCommonSetupEvent event) {
        // enqueueWork：SpawnPlacements 的登记不是线程安全的，必须回到主线程做
        event.enqueueWork(() -> {
            registerElite(ModEntities.SCREAMER);
            registerElite(ModEntities.CRUSHER);
            registerElite(ModEntities.CORRODER);
            registerElite(ModEntities.MARKSMAN);
            register(ModEntities.SOLDIER, ModSpawns::canSoldierSpawn);
        });
    }

    private static <T extends Monster> void registerElite(RegistryObject<EntityType<T>> type) {
        register(type, ModSpawns::canEliteSpawn);
    }

    private static <T extends Monster> void register(RegistryObject<EntityType<T>> type,
                                                     SpawnPlacements.SpawnPredicate<T> predicate) {
        SpawnPlacements.register(type.get(), SpawnPlacements.Type.ON_GROUND,
                Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, predicate);
    }

    /** 同伙上限的扫描半径（格）。越远处刷出来的兵不影响近处的观感，所以半径不必覆盖整个视距。 */
    private static final double CROWD_RADIUS = 48.0D;

    /**
     * 残兵：走通用精英判定，再加一条「附近同伙已满就不再刷」。
     *
     * <p>刷怪器只有在按权重抽中残兵时才会调到这里，所以这次扫描不是每 tick 都跑；
     * 上限的意义是挡住「同一片区域连续抽中」——单只稀有度交给
     * {@link Config#SOLDIER_SPAWN_WEIGHT}，成群的问题交给这里。</p>
     */
    private static boolean canSoldierSpawn(EntityType<SoldierZombie> type, ServerLevelAccessor level,
                                          MobSpawnType spawnType, BlockPos pos, RandomSource random) {
        if (!canEliteSpawn(type, level, spawnType, pos, random)) {
            return false;
        }
        int cap = Config.SOLDIER_MAX_NEARBY.get();
        return level.getLevel().getEntitiesOfClass(SoldierZombie.class,
                new AABB(pos).inflate(CROWD_RADIUS)).size() < cap;
    }

    /**
     * 原版怪物判定，外加一条限制：蘑菇岛是主世界里唯一「原版保证一只怪都不刷」的群系。
     *
     * <p>而 {@code #minecraft:is_overworld} 这个标签是包含 {@code minecraft:mushroom_fields} 的
     * （53 个群系，从 mushroom_fields 开始列），所以光靠 biome modifier 的 biomes 字段挡不住它。
     * 少了这一下，精英会把玩家当安全屋用的蘑菇岛破掉——原版苦力怕都不去的地方，不该被模组塞进一只领队。</p>
     *
     * <p>签名里的 {@code T} 必须在这里显式声明（而不是写成 {@code EntityType<? extends Monster>}）：
     * 通配符版本没法跟 {@link SpawnPlacements.SpawnPredicate} 的目标类型对上，编译期会报「推论变量上限不兼容」。</p>
     */
    private static <T extends Monster> boolean canEliteSpawn(EntityType<T> type, ServerLevelAccessor level,
                                                             MobSpawnType spawnType, BlockPos pos, RandomSource random) {
        return Monster.checkMonsterSpawnRules(type, level, spawnType, pos, random)
                && !level.getBiome(pos).is(Biomes.MUSHROOM_FIELDS);
    }
}
