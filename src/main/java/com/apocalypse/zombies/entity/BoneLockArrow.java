package com.apocalypse.zombies.entity;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.registry.ModEntities;

import net.minecraft.core.Holder;
import net.minecraft.core.particles.ParticleOptions;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.damagesource.DamageType;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.projectile.Arrow;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.EntityHitResult;
import net.minecraft.world.phys.Vec3;

/**
 * 骨矢 —— 骸骨射手「骨矢锁定」的必中弹体。
 *
 * <p>飞行物理完全照抄 {@link GiantArrow}（限速转向 + 前导 + 自毁计时），区别全在结算上：
 * 转向速率默认 60 度 / tick，直行、侧闪、绕柱都甩不掉它，所以「必中」是几何意义上的；
 * 命中即碎，不穿透。</p>
 *
 * <p><b>伤害 = 目标最大血量 × {@code Config.AI_MARKSMAN_LOCK_RATIO}</b>（默认 0.25）：
 * 目标是玩家、僵尸还是铁傀儡，挨的都是「自己血条的固定比例」，
 * 于是这一枪对大怪同样有威慑，而不会变成「打轻甲一滴血、打重甲还是这一枪」。</p>
 *
 * <p>伤害类型 {@code apocalypse_zombies:bone_lock} 在数据包里挂了
 * {@code bypasses_armor / bypasses_invulnerability / bypasses_resistance /
 * bypasses_enchantments / bypasses_shield}：护甲、无敌帧、抗性药水、保护附魔、盾牌格挡
 * 都吃不下这一枪。刻意<b>没有</b>挂 {@code is_projectile}（别被名字骗了：盾牌格挡靠的是
 * {@code bypasses_shield}，不是「没挂 is_projectile」）。</p>
 */
public class BoneLockArrow extends GiantArrow {

    /** 伤害类型路径：{@code data/apocalypse_zombies/damage_type/bone_lock.json}。 */
    public static final String DAMAGE_TYPE_PATH = "bone_lock";

    /** 飞行尾迹：灵魂火。和普通重箭的暴击星区分开 —— 骨头烧起来才是这个技能的辨识度。 */
    private static final ParticleOptions TRAIL_PARTICLE = ParticleTypes.SOUL_FIRE_FLAME;
    /** 出膛 / 命中时炸开的灵魂火。 */
    private static final ParticleOptions SOUL_PARTICLE = ParticleTypes.SOUL;
    /** 命中指示器：「这一下算数」的视觉回执。 */
    private static final ParticleOptions HIT_PARTICLE = ParticleTypes.DAMAGE_INDICATOR;

    /** 尾迹喷发间隔（tick）：1 = 每 tick 都喷，不然高速度下会拉成一串断点。 */
    private static final int TRAIL_INTERVAL = 1;

    /** 速度平方低于这个值就算「已经停了」（扎进方块 / 被打掉速度），见 {@link #tick()}。 */
    private static final double STALLED_SPEED_SQR = 1.0E-4D;

    public BoneLockArrow(EntityType<? extends BoneLockArrow> type, Level level) {
        super(type, level);
        // 尾迹是灵魂火：留着原版暴击星只会盖住它；伤害完全自己算，暴击加成也用不上
        this.setCritArrow(false);
    }

    /**
     * 射出一发必中骨矢。
     *
     * <p>参数由调用方（{@code MarksmanSkeleton#fireBoneLock()}）从 Config 取，和
     * {@link GiantArrow#launch} 一个约定 —— 弹体不自己去翻配置。</p>
     */
    public static BoneLockArrow launch(ServerLevel level, LivingEntity shooter, LivingEntity target,
                                       float speed, double turnDegrees, int lifeTicks) {
        BoneLockArrow arrow = new BoneLockArrow(ModEntities.BONE_LOCK_ARROW.get(), level);
        // 基础伤害给 0：真正的伤害在 onHitEntity 里按目标血量算，这里给多少都会被覆盖
        arrow.arm(level, shooter, target, 0.0F, speed, 0, turnDegrees, lifeTicks);
        return arrow;
    }

    @Override
    public void tick() {
        super.tick();
        if (this.level().isClientSide() || this.isRemoved()) {
            return;
        }
        // 卡住的骨矢就地碎掉：原版箭会插在墙上，但一支插在墙上还继续冒灵魂火的骨矢
        // 比直接消失难看得多（而且它会一直往外喷粒子到寿命结束）
        if (this.getDeltaMovement().lengthSqr() < STALLED_SPEED_SQR) {
            this.discard();
            return;
        }
        if (this.tickCount % TRAIL_INTERVAL == 0 && this.level() instanceof ServerLevel level) {
            Vec3 at = this.position();
            level.sendParticles(TRAIL_PARTICLE, at.x, at.y, at.z, 2, 0.03D, 0.03D, 0.03D, 0.0D);
        }
    }

    /**
     * 命中结算：不走原版箭那套「基础伤害 + 暴击骰子」。
     *
     * <p>也<b>不调用 super</b>：父类那套会再算一遍原版伤害、播原版箭的声音、还要判穿透层数，
     * 而我们只要「按目标最大血量吃一口，然后消失」这一件事。</p>
     */
    @Override
    protected void onHitEntity(EntityHitResult result) {
        if (this.level().isClientSide()) {
            return;
        }
        Entity hit = result.getEntity();
        if (hit == this.getOwner() || hit.isSpectator()) {
            return;
        }
        if (!(hit instanceof LivingEntity target)) {
            return;
        }
        // 伤害 = 目标最大血量 × 比例（Config.AI_MARKSMAN_LOCK_RATIO，默认 0.25）
        float damage = target.getMaxHealth() * Config.AI_MARKSMAN_LOCK_RATIO.get().floatValue();
        // 无视无敌帧（这一条只能靠代码，标签做不到）：1.20.1 的 hurt() 在 invulnerableTime > 10 时
        // 只补「本次伤害 − 上次伤害」的差额 —— 目标先挨 1 点普通伤害，骨矢 25 就只掉 24.0（实测）。
        // 而这个分支没有任何 DamageTypeTags 能跳过（bypasses_cooldown 是 1.20.5+ 才加的），
        // 所以清零计数器，让这一发走完整结算。技能本身有冷却，不构成 DPS 漏洞。
        target.invulnerableTime = 0;
        target.hurt(boneLockSource(), damage);
        if (this.level() instanceof ServerLevel level) {
            level.sendParticles(SOUL_PARTICLE, this.getX(), this.getY(0.5D), this.getZ(),
                    10, 0.25D, 0.25D, 0.25D, 0.02D);
            level.sendParticles(HIT_PARTICLE, this.getX(), this.getY(0.5D), this.getZ(),
                    14, 0.3D, 0.4D, 0.3D, 0.12D);
        }
        // 不穿透：扎进去就碎
        this.discard();
    }

    /** 出膛特效：灵魂火柱 + 伤害指示器（和 {@link #tick()} 的尾迹同色，视觉上是一根同源的线）。 */
    @Override
    protected void spawnMuzzleParticles(ServerLevel level, Vec3 muzzle) {
        level.sendParticles(SOUL_PARTICLE, muzzle.x, muzzle.y, muzzle.z, 12,
                0.12D, 0.12D, 0.12D, 0.02D);
        level.sendParticles(HIT_PARTICLE, muzzle.x, muzzle.y, muzzle.z, 6,
                0.2D, 0.2D, 0.2D, 0.05D);
    }

    /**
     * 伤害来源：直接来源是这支骨矢，间接来源是放箭的骸骨射手 —— 死亡消息、仇恨、
     * 「谁把我打死的」都落到正确的头上（与 {@code BulletProjectile} 同一写法）。
     */
    private DamageSource boneLockSource() {
        Holder<DamageType> holder = this.level().registryAccess()
                .registryOrThrow(Registries.DAMAGE_TYPE)
                .getHolderOrThrow(ResourceKey.create(Registries.DAMAGE_TYPE,
                        new ResourceLocation(ApocalypseZombies.MOD_ID, DAMAGE_TYPE_PATH)));
        return new DamageSource(holder, this, this.getOwner());
    }
}
