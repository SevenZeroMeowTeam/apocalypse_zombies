package com.apocalypse.zombies.entity;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

import net.minecraft.core.particles.BlockParticleOption;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.MobType;
import net.minecraft.world.entity.ai.attributes.AttributeInstance;
import net.minecraft.world.entity.ai.attributes.AttributeModifier;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.Vec3;

/**
 * 碎颅者 —— 重装近战。走得不快，但贴上来就是一发蓄力重砸。
 *
 * <p>技能「重砸」：前摇 0.9 秒（双臂过顶），命中瞬间半径 4 内所有非亡灵生物吃 9 点伤害、
 * 被向上击飞，并且护甲 -8 持续 8 秒（破甲）。</p>
 */
public class CrusherZombie extends AbstractEliteZombie {

    private static final double SLAM_RADIUS = 4.0D;
    private static final float SLAM_DAMAGE = 9.0F;
    private static final double SLAM_KNOCKBACK = 1.4D;
    private static final int ARMOR_BREAK_TICKS = 160;
    private static final double ARMOR_BREAK_AMOUNT = -8.0D;

    /** 正在生效的破甲。到期由 {@link #tickArmorBreaks()} 摘掉，不做持久化。 */
    private final List<ArmorBreak> armorBreaks = new ArrayList<>();

    public CrusherZombie(EntityType<? extends Zombie> type, Level level) {
        super(type, level);
    }

    public static AttributeSupplier.Builder createAttributes() {
        return eliteAttributes()
                .add(Attributes.MAX_HEALTH, 45.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.20D)
                .add(Attributes.ATTACK_DAMAGE, 7.0D)
                .add(Attributes.ARMOR, 8.0D)
                .add(Attributes.ARMOR_TOUGHNESS, 4.0D)
                .add(Attributes.KNOCKBACK_RESISTANCE, 0.7D)
                .add(Attributes.FOLLOW_RANGE, 35.0D);
    }

    @Override
    protected EliteAbility ability() {
        return EliteAbility.SLAM;
    }

    @Override
    protected int abilityCooldownTicks() {
        return 90;
    }

    /** 必须已经贴到脸上。 */
    @Override
    protected boolean canStartAbility() {
        return this.hasTargetInRange(0.0D, 3.5D);
    }

    @Override
    protected void onAbilityStart() {
        this.playSound(SoundEvents.RAVAGER_ATTACK, 1.3F, 0.6F);
    }

    @Override
    protected void onAbilityImpact() {
        if (!(this.level() instanceof ServerLevel level)) {
            return;
        }
        this.playSound(SoundEvents.GENERIC_EXPLODE, 1.1F, 0.7F);
        this.playSound(SoundEvents.ANVIL_LAND, 1.0F, 0.6F);

        // 地面震波：踩出一圈尘土
        level.sendParticles(new BlockParticleOption(ParticleTypes.BLOCK, Blocks.DIRT.defaultBlockState()),
                this.getX(), this.getY() + 0.1D, this.getZ(), 60, SLAM_RADIUS * 0.5D, 0.1D, SLAM_RADIUS * 0.5D, 0.15D);
        level.sendParticles(ParticleTypes.EXPLOSION,
                this.getX(), this.getY() + 0.2D, this.getZ(), 3, 1.2D, 0.1D, 1.2D, 0.0D);

        List<LivingEntity> victims = level.getEntitiesOfClass(LivingEntity.class,
                this.getBoundingBox().inflate(SLAM_RADIUS), this::isSlamVictim);
        for (LivingEntity victim : victims) {
            victim.hurt(this.damageSources().mobAttack(this), SLAM_DAMAGE);

            Vec3 push = victim.position().subtract(this.position());
            Vec3 flat = push.horizontalDistanceSqr() < 1.0E-4D
                    ? new Vec3(0.0D, 0.0D, 1.0D)
                    : push.normalize();
            victim.knockback(SLAM_KNOCKBACK, flat.x, flat.z);
            victim.setDeltaMovement(victim.getDeltaMovement().add(0.0D, 0.45D, 0.0D));

            this.applyArmorBreak(victim);
        }
    }

    /** 只打非亡灵，且必须是自己能攻击的对象——免得一波把自己人砸死。 */
    private boolean isSlamVictim(LivingEntity candidate) {
        return candidate != this
                && candidate.isAlive()
                && candidate.getMobType() != MobType.UNDEAD
                && this.canAttack(candidate);
    }

    private void applyArmorBreak(LivingEntity victim) {
        AttributeInstance armor = victim.getAttribute(Attributes.ARMOR);
        if (armor == null) {
            return;
        }
        for (ArmorBreak active : this.armorBreaks) {
            if (active.matches(armor)) {
                active.remaining = ARMOR_BREAK_TICKS;
                return;
            }
        }
        AttributeModifier modifier = new AttributeModifier("Elite slam armor break",
                ARMOR_BREAK_AMOUNT, AttributeModifier.Operation.ADDITION);
        armor.addTransientModifier(modifier);
        this.armorBreaks.add(new ArmorBreak(armor, modifier));

        victim.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SLOWDOWN, 60, 0));
    }

    private void tickArmorBreaks() {
        Iterator<ArmorBreak> iterator = this.armorBreaks.iterator();
        while (iterator.hasNext()) {
            ArmorBreak active = iterator.next();
            if (--active.remaining <= 0) {
                active.remove();
                iterator.remove();
            }
        }
    }

    @Override
    protected void customServerAiStep() {
        super.customServerAiStep();
        this.tickArmorBreaks();
    }

    @Override
    protected SoundEvent getAmbientSound() {
        return SoundEvents.RAVAGER_AMBIENT;
    }

    @Override
    protected SoundEvent getHurtSound(net.minecraft.world.damagesource.DamageSource source) {
        return SoundEvents.RAVAGER_HURT;
    }

    @Override
    protected SoundEvent getDeathSound() {
        return SoundEvents.RAVAGER_DEATH;
    }

    /** 一条破甲记录：谁的护甲、挂的哪个修饰符、还剩多久。 */
    private static final class ArmorBreak {

        private final AttributeInstance armor;
        private final AttributeModifier modifier;
        private int remaining = ARMOR_BREAK_TICKS;

        private ArmorBreak(AttributeInstance armor, AttributeModifier modifier) {
            this.armor = armor;
            this.modifier = modifier;
        }

        private boolean matches(AttributeInstance other) {
            return this.armor == other;
        }

        private void remove() {
            this.armor.removeModifier(this.modifier);
        }
    }
}
