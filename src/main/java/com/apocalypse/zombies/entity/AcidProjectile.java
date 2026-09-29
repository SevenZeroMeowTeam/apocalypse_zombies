package com.apocalypse.zombies.entity;

import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.AreaEffectCloud;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.projectile.ThrowableItemProjectile;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.EntityHitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraft.core.particles.ParticleTypes;

/**
 * 腐蚀者的酸液弹。
 *
 * <p>本体只是一颗动能弹（{@link Items#SLIME_BALL} 的贴图，用原版 {@code ThrownItemRenderer} 渲染，
 * 不需要额外美术），命中后真正干活的是留下的那片 {@link AreaEffectCloud}：
 * 毒 + 虚弱，8 秒。腐蚀是削状态，不是直接秒人。</p>
 */
public class AcidProjectile extends ThrowableItemProjectile {

    private static final float IMPACT_DAMAGE = 5.0F;
    private static final float CLOUD_RADIUS = 3.0F;
    private static final int CLOUD_DURATION = 160;

    public AcidProjectile(EntityType<? extends AcidProjectile> type, Level level) {
        super(type, level);
    }

    public AcidProjectile(EntityType<? extends AcidProjectile> type, LivingEntity owner, Level level) {
        super(type, owner, level);
    }

    @Override
    protected Item getDefaultItem() {
        return Items.SLIME_BALL;
    }

    @Override
    protected void onHitEntity(EntityHitResult result) {
        super.onHitEntity(result);
        if (this.level().isClientSide()) {
            return;
        }
        Entity hit = result.getEntity();
        hit.hurt(this.acidDamage(), IMPACT_DAMAGE);
        this.corrode(result.getLocation());
        this.discard();
    }

    @Override
    protected void onHitBlock(BlockHitResult result) {
        super.onHitBlock(result);
        if (this.level().isClientSide()) {
            return;
        }
        this.corrode(result.getLocation());
        this.discard();
    }

    /** 归因给投射者，这样死亡消息和仇恨都能正确落到腐蚀者头上。 */
    private DamageSource acidDamage() {
        LivingEntity owner = this.getOwner() instanceof LivingEntity living ? living : null;
        return this.damageSources().mobProjectile(this, owner);
    }

    private void corrode(Vec3 at) {
        if (!(this.level() instanceof ServerLevel level)) {
            return;
        }
        level.sendParticles(ParticleTypes.ITEM_SLIME, at.x, at.y + 0.1D, at.z, 24, 0.5D, 0.3D, 0.5D, 0.08D);
        this.playSound(net.minecraft.sounds.SoundEvents.SLIME_SQUISH, 1.2F, 0.7F);

        AreaEffectCloud cloud = new AreaEffectCloud(level, at.x, at.y, at.z);
        if (this.getOwner() instanceof LivingEntity owner) {
            cloud.setOwner(owner);
        }
        cloud.setRadius(CLOUD_RADIUS);
        cloud.setRadiusOnUse(-0.1F);
        cloud.setRadiusPerTick(-CLOUD_RADIUS / (float) CLOUD_DURATION);
        cloud.setDuration(CLOUD_DURATION);
        cloud.setWaitTime(10);
        cloud.setParticle(ParticleTypes.ITEM_SLIME);
        cloud.addEffect(new MobEffectInstance(MobEffects.POISON, 80, 0));
        cloud.addEffect(new MobEffectInstance(MobEffects.WEAKNESS, 100, 0));
        level.addFreshEntity(cloud);
    }
}
