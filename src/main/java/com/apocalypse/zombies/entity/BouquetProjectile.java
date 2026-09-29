package com.apocalypse.zombies.entity;

import com.apocalypse.zombies.registry.ModItems;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.projectile.ThrowableItemProjectile;
import net.minecraft.world.item.Item;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.EntityHitResult;
import net.minecraft.world.phys.Vec3;

/**
 * 美女僵尸远程技能「抛花刺」甩出去的那束花。
 *
 * <p>与 {@link AcidProjectile} 同一个路子：一个看得见、飞得慢、能躲的实体，命中结算完就消失。
 * 但这一发<b>保留重力</b>（{@code ThrowableItemProjectile} 的默认行为，不调 {@code setNoGravity}）——
 * 它是被「甩」出来的花束，走一条抛物线出去，玩家看得到它从高处落下来，跟子弹那种平飞直线是两种观感。
 * 抛物线也天然限制了它的有效射程：远距离自己先落地，不会变成一发跨半张地图的狙击。</p>
 *
 * <p>贴图是自家画的 16×16（{@code tools/bouquet_dart_icon.py} 生成，可复现），
 * 走原版 {@code ThrownItemRenderer}，不需要额外渲染器代码。</p>
 */
public class BouquetProjectile extends ThrowableItemProjectile {

    /** 直接命中伤害。比她的近战横扫（8）轻一半：远程是用来消耗和骚扰的。 */
    private static final float IMPACT_DAMAGE = 4.0F;

    /** 花刺扎进去的余韵：中毒 + 缓慢，都是短时长低等级，叠在近战上才致命。 */
    private static final int POISON_TICKS = 60;
    private static final int SLOW_TICKS = 80;

    public BouquetProjectile(EntityType<? extends BouquetProjectile> type, Level level) {
        super(type, level);
    }

    public BouquetProjectile(EntityType<? extends BouquetProjectile> type,
                             LivingEntity owner, Level level) {
        super(type, owner, level);
    }

    @Override
    protected Item getDefaultItem() {
        return ModItems.BOUQUET_DART.get();
    }

    @Override
    protected void onHitEntity(EntityHitResult result) {
        super.onHitEntity(result);
        if (this.level().isClientSide()) {
            return;
        }
        Entity hit = result.getEntity();
        hit.hurt(this.bouquetDamage(), IMPACT_DAMAGE);
        if (hit instanceof LivingEntity living) {
            living.addEffect(new MobEffectInstance(MobEffects.POISON, POISON_TICKS, 0));
            living.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SLOWDOWN, SLOW_TICKS, 0));
        }
        this.burst(result.getLocation());
        this.discard();
    }

    @Override
    protected void onHitBlock(BlockHitResult result) {
        super.onHitBlock(result);
        if (this.level().isClientSide()) {
            return;
        }
        this.burst(result.getLocation());
        this.discard();
    }

    /**
     * 归因给投掷者：死亡消息会写成「被美女僵尸杀死了」，仇恨和击杀统计也落在她头上。
     * 用 {@code mobProjectile} 而不是 {@code mobAttack} —— 后者会让这一发看起来像近战挥击。
     */
    private DamageSource bouquetDamage() {
        LivingEntity owner = this.getOwner() instanceof LivingEntity living ? living : null;
        return this.damageSources().mobProjectile(this, owner);
    }

    /** 命中处撒一把花瓣：命中与否肉眼可辨，也让「被花扎了」这件事有反馈。 */
    private void burst(Vec3 at) {
        if (!(this.level() instanceof ServerLevel level)) {
            return;
        }
        level.sendParticles(ParticleTypes.CHERRY_LEAVES, at.x, at.y + 0.2D, at.z,
                12, 0.25D, 0.25D, 0.25D, 0.03D);
        this.playSound(net.minecraft.sounds.SoundEvents.GRASS_BREAK, 0.8F, 1.4F);
    }

    /**
     * 飞行途中零星掉花瓣。
     *
     * <p>写在 {@code tick} 而不是靠渲染层 —— 只让服务端发，粒子走原版同步给周围的客户端，
     * 远处看不见就不发，不额外花带宽。</p>
     */
    @Override
    public void tick() {
        super.tick();
        if (!this.level().isClientSide() && this.tickCount % 4 == 0) {
            if (this.level() instanceof ServerLevel level) {
                level.sendParticles(ParticleTypes.CHERRY_LEAVES, this.getX(), this.getY(), this.getZ(),
                        1, 0.05D, 0.05D, 0.05D, 0.0D);
            }
        }
    }
}
