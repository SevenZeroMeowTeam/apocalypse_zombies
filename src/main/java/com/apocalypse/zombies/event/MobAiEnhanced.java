package com.apocalypse.zombies.event;

import java.util.List;
import java.util.UUID;
import java.util.function.Supplier;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.GunAttackGoal;
import com.apocalypse.zombies.entity.KeepDistanceGoal;
import com.apocalypse.zombies.entity.MarksmanSkeleton;
import com.apocalypse.zombies.entity.ai.GiantArrowGoal;
import com.apocalypse.zombies.entity.ai.GolemGuardGoal;
import com.apocalypse.zombies.entity.ai.PreyTargetGoal;
import com.apocalypse.zombies.entity.ai.SharedAggroGoal;
import com.apocalypse.zombies.entity.ai.SkirmishGoal;
import com.apocalypse.zombies.entity.ai.SurroundGoal;
import com.apocalypse.zombies.moon.MoonEventManager;

import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.Brain;
import net.minecraft.world.entity.ai.attributes.Attribute;
import net.minecraft.world.entity.ai.attributes.AttributeInstance;
import net.minecraft.world.entity.ai.attributes.AttributeModifier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.entity.ai.goal.GoalSelector;
import net.minecraft.world.entity.ai.goal.RangedAttackGoal;
import net.minecraft.world.entity.ai.goal.RangedBowAttackGoal;
import net.minecraft.world.entity.ai.goal.WrappedGoal;
import net.minecraft.world.entity.ai.memory.MemoryModuleType;
import net.minecraft.world.entity.ai.memory.WalkTarget;
import net.minecraft.world.entity.ai.navigation.FlyingPathNavigation;
import net.minecraft.world.entity.animal.IronGolem;
import net.minecraft.world.entity.monster.AbstractSkeleton;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.schedule.Activity;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.entity.EntityJoinLevelEvent;
import net.minecraftforge.event.entity.living.LivingEvent;
import net.minecraftforge.event.entity.living.MobSpawnEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * AI 增强的统一收口：敌对生物锁敌与围猎、骷髅重箭、村民呼救、铁傀儡护民。
 *
 * <p>为什么走事件而不是给每个实体类写一遍 {@code registerGoals}：目标里既有大量原版怪
 * （僵尸 / 骷髅 / 蜘蛛 / 苦力怕 …），也有别的模组注册的怪 —— 那些类根本不在本仓库里，
 * 挨个改是不可能的。事件层能一次覆盖，判据只有「它是不是 {@link Monster}」。</p>
 *
 * <p>三个钩子各管一段：</p>
 * <ol>
 *   <li>{@link EntityJoinLevelEvent} —— 实体进入世界时挂 Goal 与属性。<b>只做一次</b>：
 *       Goal 靠「目标类身份」判重、属性靠固定 UUID 判重，于是区块反复加载不会越挂越多。</li>
 *   <li>{@link MobSpawnEvent.FinalizeSpawn} —— 刷怪那一刻的随机抽取（破门能力），
 *       顺便能读当月月相（血月提高概率）。</li>
 *   <li>{@link LivingEvent.LivingTickEvent} —— 村民这一支。它必须走 tick：村民用的是
 *       <b>Brain/活动系统</b>，没有 {@code goalSelector}，加 Goal 等于没加。</li>
 * </ol>
 *
 * <p>性能纪律：怪物侧<b>没有任何每 tick 的全量扫描</b>（只在这个实体加入世界时做一次，以及
 * 各自 Goal 内部的抽样扫描）；村民侧的扫描按实体 id 打散相位并节流到
 * {@code ai_enhance.villager_interval} tick 一次。几百只怪同屏时这两条决定了它能不能用。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID)
public final class MobAiEnhanced {

    /** 敌对生物追击范围的修饰符 UUID（固定值：用来判断这一只加过没有）。 */
    private static final UUID HOSTILE_RANGE_ID = UUID.fromString("6f1c0a94-4dbe-4f9c-9c1e-0f2a7c3b8d11");

    /** 铁傀儡追击范围与击退的修饰符 UUID。 */
    private static final UUID GOLEM_RANGE_ID = UUID.fromString("6f1c0a94-4dbe-4f9c-9c1e-0f2a7c3b8d12");
    private static final UUID GOLEM_KNOCKBACK_ID = UUID.fromString("6f1c0a94-4dbe-4f9c-9c1e-0f2a7c3b8d13");

    private MobAiEnhanced() {
    }

    // ------------------------------------------------------------------ 1. 进入世界

    @SubscribeEvent
    public static void onEntityJoin(EntityJoinLevelEvent event) {
        if (event.getLevel().isClientSide()) {
            return;
        }
        if (event.getEntity() instanceof IronGolem golem) {
            enhanceGolem(golem);
            return;
        }
        if (event.getEntity() instanceof Monster monster && eligible(monster)) {
            enhanceHostile(monster);
        }
    }

    private static void enhanceHostile(Monster monster) {
        if (Config.AI_HOSTILE_ENABLED.get()) {
            addOnce(monster.targetSelector, 0, SharedAggroGoal.class,
                    () -> new SharedAggroGoal(monster, Config.AI_AGGRO_RADIUS.get(),
                            Config.AI_AGGRO_INTERVAL.get()));
            // 优先级 1：夹在「同伴传仇恨」（0）之下、原版玩家（2）/ 村民（3）/ 铁傀儡（3）之上。
            // 原来的 ScentTargetGoal 挂在 0 且 mustSee / mustReach 全 false，会锁着「看得见
            // 够不着」的目标把整张表饿死（站在村民/铁傀儡旁边一动不动那个缺陷），已换成这条。
            addOnce(monster.targetSelector, 1, PreyTargetGoal.class, () -> new PreyTargetGoal(monster));
            applyModifier(monster, Attributes.FOLLOW_RANGE, HOSTILE_RANGE_ID, "apocalypse_ai_range",
                    Config.AI_FOLLOW_RANGE.get());
            if (Config.AI_SURROUND_ENABLED.get() && !hasRangedIdentity(monster)) {
                // 优先级 1：必须比原版近战 Goal（僵尸 2 / 蜘蛛 3）更优先，否则拿不到 MOVE
                addOnce(monster.goalSelector, 1, SurroundGoal.class,
                        () -> new SurroundGoal(monster, 1.0D, Config.AI_SURROUND_RANGE.get(), 2.0D));
            }
        }
        // 精英骸骨射手自己 registerGoals 里带重箭（概率与伤害另调一档），这里不重复挂
        if (Config.AI_SKELETON_ENABLED.get() && monster instanceof AbstractSkeleton skeleton
                && !(monster instanceof MarksmanSkeleton)) {
            addOnce(skeleton.goalSelector, 1, GiantArrowGoal.class,
                    () -> new GiantArrowGoal(skeleton, 6.0D, 32.0D,
                            Config.AI_SKELETON_GIANT_CHANCE.get().floatValue(),
                            Config.AI_SKELETON_GIANT_DAMAGE.get().floatValue(),
                            Config.AI_GIANT_ARROW_SPEED.get().floatValue(), 2,
                            Config.AI_GIANT_ARROW_TURN.get(), Config.AI_SKELETON_GIANT_COOLDOWN.get(),
                            Config.AI_GIANT_ARROW_WINDUP.get(), Config.AI_GIANT_ARROW_LIFE.get()));
            addOnce(skeleton.goalSelector, 3, SkirmishGoal.class,
                    () -> new SkirmishGoal(skeleton, 1.2D, 3.5D, 9.0D));
        }
    }

    private static void enhanceGolem(IronGolem golem) {
        if (!Config.AI_GOLEM_ENABLED.get()) {
            return;
        }
        addOnce(golem.targetSelector, 0, GolemGuardGoal.class,
                () -> new GolemGuardGoal(golem, Config.AI_GOLEM_GUARD_RADIUS.get(), 8.0D, 20));
        applyModifier(golem, Attributes.FOLLOW_RANGE, GOLEM_RANGE_ID, "apocalypse_golem_range",
                Config.AI_GOLEM_FOLLOW_RANGE.get());
        applyModifier(golem, Attributes.ATTACK_KNOCKBACK, GOLEM_KNOCKBACK_ID, "apocalypse_golem_knockback",
                Config.AI_GOLEM_KNOCKBACK.get());
    }

    // ------------------------------------------------------------------ 2. 刷怪那一刻

    @SubscribeEvent
    public static void onFinalizeSpawn(MobSpawnEvent.FinalizeSpawn event) {
        if (!Config.AI_HOSTILE_ENABLED.get()) {
            return;
        }
        if (!(event.getEntity() instanceof Zombie zombie) || !eligible(zombie)) {
            return;
        }
        if (!(event.getLevel() instanceof ServerLevel level)) {
            return;
        }
        boolean bloodMoon = MoonEventManager.getMoonEvent(level).isBloodMoon();
        double chance = bloodMoon ? Config.AI_DOOR_BREAK_BLOOD_MOON.get() : Config.AI_DOOR_BREAK_CHANCE.get();
        if (chance <= 0.0D || zombie.getRandom().nextDouble() >= chance) {
            return;
        }
        zombie.setCanBreakDoors(true);
    }

    // ------------------------------------------------------------------ 3. 村民（Brain）

    @SubscribeEvent
    public static void onLivingTick(LivingEvent.LivingTickEvent event) {
        if (!(event.getEntity() instanceof Villager villager) || villager.level().isClientSide()) {
            return;
        }
        if (!Config.AI_VILLAGER_ENABLED.get()) {
            return;
        }
        int interval = Config.AI_VILLAGER_INTERVAL.get();
        if ((villager.tickCount + villager.getId()) % interval != 0) {
            return;
        }
        Monster threat = nearestThreat(villager, Config.AI_VILLAGER_ALERT_RADIUS.get());
        if (threat == null) {
            return;
        }
        Brain<Villager> brain = villager.getBrain();
        if (!brain.isActive(Activity.PANIC)) {
            brain.setActiveActivityIfPossible(Activity.PANIC);
        }
        // 原版 panic 包会给「背向敌对生物」的落点，但它只认自己传感器探到的那几只；
        // 这里补一个明确的撤离落点，保证「看得见的那只怪」一定会被躲开。
        Vec3 away = villager.position().subtract(threat.position());
        Vec3 flat = new Vec3(away.x, 0.0D, away.z);
        if (flat.horizontalDistanceSqr() < 1.0E-4D) {
            flat = new Vec3(1.0D, 0.0D, 0.0D);
        }
        Vec3 escape = villager.position().add(flat.normalize().scale(8.0D));
        brain.setMemory(MemoryModuleType.WALK_TARGET, new WalkTarget(escape, 0.7F, 1));
        if (villager.hasLineOfSight(threat)) {
            callGolems(villager, threat);
        }
    }

    /** 村民呼救：把威胁交给附近还没进入战斗的铁傀儡。 */
    private static void callGolems(Villager villager, Monster threat) {
        List<IronGolem> golems = villager.level().getEntitiesOfClass(IronGolem.class,
                villager.getBoundingBox().inflate(Config.AI_VILLAGER_CALL_RADIUS.get()),
                IronGolem::isAlive);
        for (IronGolem golem : golems) {
            LivingEntity current = golem.getTarget();
            if (current == null || !current.isAlive()) {
                golem.setTarget(threat);
            }
        }
    }

    private static Monster nearestThreat(LivingEntity from, double radius) {
        List<Monster> monsters = from.level().getEntitiesOfClass(Monster.class,
                from.getBoundingBox().inflate(radius), Monster::isAlive);
        Monster best = null;
        double bestDistance = Double.MAX_VALUE;
        for (Monster monster : monsters) {
            if (!monster.canAttack(from)) {
                continue;
            }
            double distance = from.distanceToSqr(monster);
            if (distance < bestDistance) {
                bestDistance = distance;
                best = monster;
            }
        }
        return best;
    }

    // ------------------------------------------------------------------ 工具

    /**
     * 这只怪是不是「远程身份」。远程怪要拉开距离，不该被包抄 Goal 抢走移动通道：
     * 原版骷髅（弓）、溺尸（三叉戟）、女巫（药水）、掠夺者（弩）都算，
     * 本模组的持枪怪与骸骨射手（{@link KeepDistanceGoal}）也算。
     */
    private static boolean hasRangedIdentity(Mob mob) {
        for (WrappedGoal wrapped : mob.goalSelector.getAvailableGoals()) {
            Goal goal = wrapped.getGoal();
            if (goal instanceof RangedAttackGoal || goal instanceof RangedBowAttackGoal
                    || goal instanceof GunAttackGoal || goal instanceof KeepDistanceGoal) {
                return true;
            }
        }
        return false;
    }

    /**
     * 哪些怪值得增强。飞行怪与「无 AI」的怪一律跳过 —— 给它们挂走位 Goal 只会让它们原地抽搐
     * （幽灵、恶魂、幻翼、凋灵都属于这一类），这类怪由 {@code excluded_mobs} 兜底补充。
     */
    private static boolean eligible(Monster monster) {
        if (monster.isNoAi()) {
            return false;
        }
        if (monster.getNavigation() instanceof FlyingPathNavigation) {
            return false;
        }
        ResourceLocation key = EntityType.getKey(monster.getType());
        return key != null && !Config.AI_EXCLUDED_MOBS.get().contains(key.toString());
    }

    /** 同类 Goal 已经在了就不加第二遍 —— 区块反复加载时这一条是必须的。 */
    private static void addOnce(GoalSelector selector, int priority, Class<? extends Goal> type,
                                Supplier<Goal> factory) {
        for (WrappedGoal wrapped : selector.getAvailableGoals()) {
            if (type.isInstance(wrapped.getGoal())) {
                return;
            }
        }
        selector.addGoal(priority, factory.get());
    }

    /**
     * 把属性抬到 {@code target}（以「基础值 + 差额」的形式加，别模组的改动互不打架）。
     * 重复调用安全：UUID 已经在，且差额没变就直接返回。
     */
    private static void applyModifier(Mob mob, Attribute attribute, UUID id, String name, double target) {
        AttributeInstance instance = mob.getAttribute(attribute);
        if (instance == null) {
            return;
        }
        double delta = target - instance.getBaseValue();
        AttributeModifier existing = instance.getModifier(id);
        if (existing != null) {
            if (Math.abs(existing.getAmount() - delta) < 1.0E-4D) {
                return;
            }
            instance.removeModifier(id);
        }
        if (Math.abs(delta) < 1.0E-4D) {
            return;
        }
        instance.addTransientModifier(new AttributeModifier(id, name, delta, AttributeModifier.Operation.ADDITION));
    }
}
