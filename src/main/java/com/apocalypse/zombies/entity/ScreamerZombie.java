package com.apocalypse.zombies.entity;

import java.util.List;
import javax.annotation.Nullable;

import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.DifficultyInstance;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.MobSpawnType;
import net.minecraft.world.entity.SpawnGroupData;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.ServerLevelAccessor;
import net.minecraft.world.phys.AABB;

/**
 * 尖啸者 —— 指挥型。自己打不痛，但会把附近所有僵尸变成一波冲脸的兽群。
 *
 * <p>技能「尖啸」：范围 12 内的僵尸获得速度 II + 力量 I（10 秒），同时当场召唤 1~2 只普通僵尸。
 * 死亡被动：倒下再喊一次，留下 2 只僵尸。</p>
 */
public class ScreamerZombie extends AbstractEliteZombie {

    /** 增益覆盖半径。 */
    private static final double BUFF_RADIUS = 12.0D;
    private static final int BUFF_DURATION = 200;
    /** 召唤增援前场上最多容许多少只僵尸，避免无限滚雪球。 */
    private static final int SUMMON_CAP = 12;

    public ScreamerZombie(EntityType<? extends Zombie> type, Level level) {
        super(type, level);
    }

    public static AttributeSupplier.Builder createAttributes() {
        return eliteAttributes()
                .add(Attributes.MAX_HEALTH, 30.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.22D)
                .add(Attributes.ATTACK_DAMAGE, 2.0D)
                .add(Attributes.ARMOR, 2.0D)
                .add(Attributes.FOLLOW_RANGE, 40.0D);
    }

    @Override
    protected EliteAbility ability() {
        return EliteAbility.SCREAM;
    }

    @Override
    protected int abilityCooldownTicks() {
        return 240;
    }

    /** 看见目标就吼，不用贴身。 */
    @Override
    protected boolean canStartAbility() {
        return this.hasTargetInRange(2.0D, 14.0D);
    }

    @Override
    protected void onAbilityStart() {
        this.playSound(SoundEvents.RAVAGER_ROAR, 1.6F, 0.7F);
    }

    @Override
    protected void onAbilityImpact() {
        if (!(this.level() instanceof ServerLevel level)) {
            return;
        }
        this.playSound(SoundEvents.WARDEN_SONIC_BOOM, 1.2F, 1.4F);
        level.sendParticles(ParticleTypes.SONIC_BOOM,
                this.getX(), this.getEyeY() + 0.3D, this.getZ(), 1, 0.0D, 0.0D, 0.0D, 0.0D);

        List<Zombie> pack = level.getEntitiesOfClass(Zombie.class,
                new AABB(this.blockPosition()).inflate(BUFF_RADIUS), Zombie::isAlive);
        for (Zombie member : pack) {
            if (member == this) {
                continue;
            }
            member.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SPEED, BUFF_DURATION, 1));
            member.addEffect(new MobEffectInstance(MobEffects.DAMAGE_BOOST, BUFF_DURATION, 0));
            level.sendParticles(ParticleTypes.ANGRY_VILLAGER,
                    member.getX(), member.getEyeY() + 0.5D, member.getZ(), 2, 0.3D, 0.3D, 0.3D, 0.0D);
        }

        int living = pack.size();
        if (living < SUMMON_CAP) {
            int count = 1 + this.random.nextInt(2);
            for (int i = 0; i < count; i++) {
                this.summonReinforcement(level);
            }
        }
    }

    /** 在自身周围找个能站的位置放一只普通僵尸，并把当前目标告诉它。 */
    private void summonReinforcement(ServerLevel level) {
        for (int attempt = 0; attempt < 8; attempt++) {
            double angle = this.random.nextDouble() * Math.PI * 2.0D;
            double distance = 3.0D + this.random.nextDouble() * 3.0D;
            BlockPos spawn = BlockPos.containing(
                    this.getX() + Math.cos(angle) * distance,
                    this.getY(),
                    this.getZ() + Math.sin(angle) * distance);
            if (!level.isEmptyBlock(spawn) || !level.isEmptyBlock(spawn.above())) {
                continue;
            }

            Zombie zombie = EntityType.ZOMBIE.create(level);
            if (zombie == null) {
                return;
            }
            zombie.moveTo(spawn.getX() + 0.5D, spawn.getY(), spawn.getZ() + 0.5D,
                    this.random.nextFloat() * 360.0F, 0.0F);
            LivingEntity target = this.getTarget();
            if (target != null) {
                zombie.setTarget(target);
            }
            zombie.finalizeSpawn(level,
                    level.getCurrentDifficultyAt(zombie.blockPosition()),
                    MobSpawnType.MOB_SUMMONED, null, null);
            level.addFreshEntity(zombie);
            level.sendParticles(ParticleTypes.SCULK_SOUL,
                    zombie.getX(), zombie.getEyeY(), zombie.getZ(), 6, 0.2D, 0.3D, 0.2D, 0.02D);
            return;
        }
    }

    /** 死亡被动：倒下再喊一声，留两只僵尸收场。 */
    @Override
    public void die(DamageSource source) {
        if (this.level() instanceof ServerLevel level) {
            this.playSound(SoundEvents.RAVAGER_DEATH, 1.4F, 0.8F);
            for (int i = 0; i < 2; i++) {
                this.summonReinforcement(level);
            }
        }
        super.die(source);
    }

    @Override
    protected SoundEvent getAmbientSound() {
        return SoundEvents.ZOMBIE_AMBIENT;
    }

    @Override
    protected SoundEvent getHurtSound(DamageSource source) {
        return SoundEvents.ZOMBIE_HURT;
    }

    @Override
    protected SoundEvent getDeathSound() {
        return SoundEvents.RAVAGER_DEATH;
    }
}
