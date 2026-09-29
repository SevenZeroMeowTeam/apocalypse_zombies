package com.apocalypse.zombies.entity;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.item.GunProfile;
import net.minecraft.core.Holder;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.core.registries.Registries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.damagesource.DamageType;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.projectile.ThrowableItemProjectile;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.EntityHitResult;
import net.minecraft.world.phys.Vec3;

/**
 * 怪物打出去的子弹：看得见、能躲、有弹速。
 *
 * <p>玩家那一把是「眼睛射线、命中即结算」—— 那是给会瞄准的人准备的，一枪一个准。怪物不会瞄准，
 * 所以它的子弹是<b>世界里的实体</b>：有速度、有曳光、能被走位躲开，也会被墙接住。
 * 观感与枪械同源（{@code END_ROD} 曳光、同一套第三人称枪声），但弹道数字另立一张表
 * （{@link GunProfile}），两套口径互不干扰 —— 改玩家手感不会顺手改掉怪物强度，反之亦然。</p>
 *
 * <p>贴图借 {@link Items#IRON_NUGGET}：一颗小金属弹头，配自发光渲染就是曳光弹，
 * 不需要额外美术（与 {@link AcidProjectile} 同一个做法）。</p>
 *
 * <p>伤害类型按<b>枪</b>分（弩 / 莫辛 / 加兰德 / AWM 各有一份 {@code *_bullet}），
 * 于是死亡消息与玩家开枪时是同一句，护甲、抗性、击退也都照常走原版流程。</p>
 */
public class BulletProjectile extends ThrowableItemProjectile {

    /** 曳光：每 tick 一颗。飞多快都是一条看得见的虚线。 */
    private static final int TRAIL_INTERVAL = 1;

    /** 最多飞这么多 tick 就自然消散，免得一发没打中的子弹绕着世界继续转。 */
    private static final int MAX_LIFETIME = 60;

    /** 由发射者写入：这一发打多少、算哪种伤害。 */
    private float damage;
    private String damageTypePath = "awm_bullet";

    public BulletProjectile(EntityType<? extends BulletProjectile> type, Level level) {
        super(type, level);
        // 平飞：怪物不会算弹道，让它算等于让它的命中率随距离崩掉
        this.setNoGravity(true);
    }

    public BulletProjectile(EntityType<? extends BulletProjectile> type, LivingEntity owner, Level level) {
        super(type, owner, level);
        this.setNoGravity(true);
    }

    @Override
    protected Item getDefaultItem() {
        return Items.IRON_NUGGET;
    }

    /** 装订弹道参数。必须在 {@code addFreshEntity} 之前调用。 */
    public void load(GunProfile profile) {
        this.damage = profile.damage();
        this.damageTypePath = profile.damageTypePath();
    }

    @Override
    public void tick() {
        super.tick();
        if (this.tickCount > MAX_LIFETIME) {
            this.discard();
            return;
        }
        if (this.level() instanceof ServerLevel level && this.tickCount % TRAIL_INTERVAL == 0) {
            level.sendParticles(ParticleTypes.END_ROD,
                    this.getX(), this.getY(), this.getZ(), 1, 0.0D, 0.0D, 0.0D, 0.0D);
        }
    }

    @Override
    protected void onHitEntity(EntityHitResult result) {
        super.onHitEntity(result);
        if (this.level().isClientSide()) {
            return;
        }
        Entity hit = result.getEntity();
        hit.invulnerableTime = 0;
        hit.hurt(this.bulletSource(), this.damage);
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
     * 归因给射手：直接来源是这颗子弹，间接来源是开枪的那只怪。
     * 这样死亡消息、仇恨、以及「谁把我打死的」都能落到正确的人头上。
     */
    private DamageSource bulletSource() {
        Holder<DamageType> holder = this.level().registryAccess()
                .registryOrThrow(Registries.DAMAGE_TYPE)
                .getHolderOrThrow(ResourceKey.create(Registries.DAMAGE_TYPE,
                        new ResourceLocation(ApocalypseZombies.MOD_ID, this.damageTypePath)));
        return new DamageSource(holder, this, this.getOwner());
    }

    private void burst(Vec3 at) {
        if (!(this.level() instanceof ServerLevel level)) {
            return;
        }
        level.sendParticles(ParticleTypes.CRIT, at.x, at.y, at.z, 8, 0.1D, 0.1D, 0.1D, 0.12D);
        this.playSound(net.minecraft.sounds.SoundEvents.FIREWORK_ROCKET_BLAST, 0.7F, 1.8F);
    }

    @Override
    public void addAdditionalSaveData(CompoundTag tag) {
        super.addAdditionalSaveData(tag);
        tag.putFloat("BulletDamage", this.damage);
        tag.putString("BulletType", this.damageTypePath);
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag) {
        super.readAdditionalSaveData(tag);
        this.damage = tag.getFloat("BulletDamage");
        if (tag.contains("BulletType")) {
            this.damageTypePath = tag.getString("BulletType");
        }
    }
}
