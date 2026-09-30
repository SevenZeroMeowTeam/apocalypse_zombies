package com.apocalypse.zombies.registry;

import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;
import net.minecraftforge.event.entity.EntityAttributeCreationEvent;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.entity.AcidProjectile;
import com.apocalypse.zombies.entity.BouquetProjectile;
import com.apocalypse.zombies.entity.BrideZombie;
import com.apocalypse.zombies.entity.BulletProjectile;
import com.apocalypse.zombies.entity.CharmedZombie;
import com.apocalypse.zombies.entity.CorroderZombie;
import com.apocalypse.zombies.entity.CrusherZombie;
import com.apocalypse.zombies.entity.MarksmanSkeleton;
import com.apocalypse.zombies.entity.ScreamerZombie;
import com.apocalypse.zombies.entity.SoldierZombie;
import com.apocalypse.zombies.entity.GiantArrow;
import com.apocalypse.zombies.entity.HordeOverlord;

/**
 * 特殊敌对生物的实体注册。
 *
 * <p>命中盒沿用原版僵尸/骷髅的尺度（碎颅者略大一圈，它的渲染器会同步放大），
 * 这样贴脸判定、朝向、被推动这些手感都和原版一致，不用重新调。</p>
 *
 * <p>{@code EntityType.Builder.<T>of(...)} 的类型见证不能省：构造函数收的是
 * {@code EntityType<? extends T>}，不给见证时推断会塌成 {@code Entity}，编译不过。
 * 原版注册表也全是这么写的。</p>
 *
 * <p>这里不注册 {@code SpawnPlacements}：这四只不参与生物群系刷怪表，
 * 由血月围城的波次和刷怪蛋投放，见 {@code HordeManager}。</p>
 */
public final class ModEntities {

    public static final DeferredRegister<EntityType<?>> ENTITY_TYPES =
            DeferredRegister.create(ForgeRegistries.ENTITY_TYPES, ApocalypseZombies.MOD_ID);

    public static final RegistryObject<EntityType<ScreamerZombie>> SCREAMER =
            ENTITY_TYPES.register("screamer_zombie", () -> EntityType.Builder
                    .<ScreamerZombie>of(ScreamerZombie::new, MobCategory.MONSTER)
                    .sized(0.6F, 1.95F)
                    .clientTrackingRange(10)
                    .build("screamer_zombie"));

    public static final RegistryObject<EntityType<CrusherZombie>> CRUSHER =
            ENTITY_TYPES.register("crusher_zombie", () -> EntityType.Builder
                    .<CrusherZombie>of(CrusherZombie::new, MobCategory.MONSTER)
                    .sized(0.7F, 2.25F)
                    .clientTrackingRange(10)
                    .build("crusher_zombie"));

    public static final RegistryObject<EntityType<CorroderZombie>> CORRODER =
            ENTITY_TYPES.register("corroder_zombie", () -> EntityType.Builder
                    .<CorroderZombie>of(CorroderZombie::new, MobCategory.MONSTER)
                    .sized(0.6F, 1.95F)
                    .clientTrackingRange(10)
                    .build("corroder_zombie"));

    public static final RegistryObject<EntityType<MarksmanSkeleton>> MARKSMAN =
            ENTITY_TYPES.register("marksman_skeleton", () -> EntityType.Builder
                    .<MarksmanSkeleton>of(MarksmanSkeleton::new, MobCategory.MONSTER)
                    .sized(0.6F, 1.99F)
                    .clientTrackingRange(12)
                    .build("marksman_skeleton"));

    public static final RegistryObject<EntityType<BrideZombie>> BRIDE =
            ENTITY_TYPES.register("bride_zombie", () -> EntityType.Builder
                    .<BrideZombie>of(BrideZombie::new, MobCategory.MONSTER)
                    .sized(0.6F, 2.0F)
                    .clientTrackingRange(10)
                    .build("bride_zombie"));

    public static final RegistryObject<EntityType<CharmedZombie>> CHARMED =
            ENTITY_TYPES.register("charmed_zombie", () -> EntityType.Builder
                    .<CharmedZombie>of(CharmedZombie::new, MobCategory.MONSTER)
                    .sized(0.6F, 1.95F)
                    .clientTrackingRange(10)
                    .build("charmed_zombie"));

    /** 残兵：军装僵尸士兵。持弓（弓建在骨骼树里）+ 投掷点燃的 TNT，两种远程手段。 */
    public static final RegistryObject<EntityType<SoldierZombie>> SOLDIER =
            ENTITY_TYPES.register("soldier_zombie", () -> EntityType.Builder
                    .<SoldierZombie>of(SoldierZombie::new, MobCategory.MONSTER)
                    .sized(0.6F, 2.0F)
                    .clientTrackingRange(12)
                    .build("soldier_zombie"));

    /**
     * 尸潮之主：三阶段 Boss，2500 点生命。
     *
     * <p>命中箱 1.6 × 3.1 格是照着模型量的（geo 顶点最高 48.6u = 3.04 格），
     * 不是随手给的 —— GeckoLib 不缩放模型，命中箱对不上就会出现「斧头砍得到、
     * 但碰撞箱碰不到」这种读不出来的失衡。</p>
     *
     * <p>追踪距离 16（256 格）：Boss 的骨刺射程 40 格、血条要一直挂着，
     * 用精英们默认的 10~12 会让玩家绕到 160 格外就看不见它了。</p>
     */
    public static final RegistryObject<EntityType<HordeOverlord>> OVERLORD =
            ENTITY_TYPES.register("horde_overlord", () -> EntityType.Builder
                    .<HordeOverlord>of(HordeOverlord::new, MobCategory.MONSTER)
                    .sized(1.6F, 3.1F)
                    .clientTrackingRange(16)
                    .build("horde_overlord"));

    public static final RegistryObject<EntityType<AcidProjectile>> ACID_PROJECTILE =
            ENTITY_TYPES.register("acid_projectile", () -> EntityType.Builder
                    .<AcidProjectile>of(AcidProjectile::new, MobCategory.MISC)
                    .sized(0.25F, 0.25F)
                    .clientTrackingRange(4)
                    .updateInterval(10)
                    .build("acid_projectile"));

    /**
     * 怪物打出的子弹：一个飞得快、带曳光的小实体。
     *
     * <p>{@code updateInterval(1)} 是必须的 —— 弹速 3~4 格/tick，按默认的间隔发包会在客户端
     * 看成一段段跳，等于把「看得见能躲」这个前提去掉。子弹数量本来就只有几发，代价可以忽略。
     * 追踪距离给到 10（160 格），否则远距离对枪时子弹会先被卸载。</p>
     */
    public static final RegistryObject<EntityType<BulletProjectile>> BULLET =
            ENTITY_TYPES.register("bullet", () -> EntityType.Builder
                    .<BulletProjectile>of(BulletProjectile::new, MobCategory.MISC)
                    .sized(0.15F, 0.15F)
                    .clientTrackingRange(10)
                    .updateInterval(1)
                    .build("bullet"));

    /**
     * 美女僵尸「抛花刺」的花束：保留重力的抛物线投掷物，贴图是自家的 16×16。
     *
     * <p>间隔给 2 而不是酸液那样的 10：它飞得比酸液快（约 0.9 格/tick），
     * 按 10 发包会把它画成一段段跳；但它又不像子弹那样需要每 tick 一颗曳光，
     * 所以取中间值 —— 看得清轨迹，又不至于为了一个技能多发包。</p>
     */
    public static final RegistryObject<EntityType<BouquetProjectile>> BOUQUET_PROJECTILE =
            ENTITY_TYPES.register("bouquet_projectile", () -> EntityType.Builder
                    .<BouquetProjectile>of(BouquetProjectile::new, MobCategory.MISC)
                    .sized(0.3F, 0.3F)
                    .clientTrackingRange(6)
                    .updateInterval(2)
                    .build("bouquet_projectile"));

    /**
     * 骷髅的重箭：原版箭的放大 + 限速跟踪版本。继承 {@code Arrow} ⇒ 伤害走原版
     * {@code DamageSource.arrow}（不需要 {@code damage_type} 数据包），渲染复用原版箭贴图。
     *
     * <p>{@code updateInterval(1)} 与子弹同理：速度 3 格/tick，默认间隔会在客户端看成一段段跳。
     * 追踪距离给 10（160 格），否则远距离放出的箭在玩家那边会先被卸载。</p>
     */
    public static final RegistryObject<EntityType<GiantArrow>> GIANT_ARROW =
            ENTITY_TYPES.register("giant_arrow", () -> EntityType.Builder
                    .<GiantArrow>of(GiantArrow::new, MobCategory.MISC)
                    .sized(0.5F, 0.5F)
                    .clientTrackingRange(10)
                    .updateInterval(1)
                    .build("giant_arrow"));

    private ModEntities() {
    }

    public static void register(IEventBus modBus) {
        ENTITY_TYPES.register(modBus);
        modBus.addListener(ModEntities::registerAttributes);
    }

    /** 属性必须在实体类型注册之后单独喂给原版：{@code createAttributes().build()} 就是那张属性池。 */
    private static void registerAttributes(EntityAttributeCreationEvent event) {
        event.put(SCREAMER.get(), ScreamerZombie.createAttributes().build());
        event.put(CRUSHER.get(), CrusherZombie.createAttributes().build());
        event.put(CORRODER.get(), CorroderZombie.createAttributes().build());
        event.put(MARKSMAN.get(), MarksmanSkeleton.createAttributes().build());
        event.put(BRIDE.get(), BrideZombie.createAttributes().build());
        event.put(CHARMED.get(), CharmedZombie.createAttributes().build());
        event.put(SOLDIER.get(), SoldierZombie.createAttributes().build());
        event.put(OVERLORD.get(), HordeOverlord.createAttributes().build());
    }
}
