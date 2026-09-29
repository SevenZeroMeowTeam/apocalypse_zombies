package com.apocalypse.zombies.entity;

import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.entity.projectile.Arrow;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;

/**
 * 超大号跟踪箭 —— 骷髅的「重箭」。
 *
 * <p>刻意<b>继承原版 {@link Arrow}</b> 而不是自己造一个 {@code Entity}：箭的伤害走原版
 * {@code DamageSource.arrow}，省掉整套 {@code damage_type} 数据包注册；箭的物理（穿墙判定、
 * 卡进方块、插在地上）与渲染（{@link net.minecraft.client.renderer.entity.ArrowRenderer}）
 * 全部复用，本类只加两件事 —— <b>限速转向</b>与<b>自毁计时</b>。</p>
 *
 * <p>追踪强度写成「每秒最多转多少度」：{@value #DEFAULT_TURN_DEGREES}°/tick（≈120°/s）
 * 是一条刻意留了活路的线 —— 直着跑必中，但侧向急转、绕柱、进掩体都能甩掉它，
 * 玩家有得操作而不是只能挨打。转向用<b>方向插值</b>实现（把当前朝向朝目标朝向混一点），
 * 而不是绕轴旋转：两者在小角度下等价，前者不需要处理「反向时转轴退化」的边界。</p>
 *
 * <p>朝向不需要自己维护：原版 {@code AbstractArrow.tick()} 会按速度矢量反解 yaw/pitch，
 * 所以改完速度，下一 tick 模型自己就转过去了。</p>
 */
public class GiantArrow extends Arrow {

    /** 默认转向速率（度 / tick）。 */
    public static final double DEFAULT_TURN_DEGREES = 6.0D;

    /** 默认自毁计时（tick），免得一发没中的箭绕着世界飞半分钟。 */
    public static final int DEFAULT_LIFE = 120;

    private int seekerId = -1;
    private double turnDegrees = DEFAULT_TURN_DEGREES;
    private int lifeTicks = DEFAULT_LIFE;

    public GiantArrow(EntityType<? extends Arrow> type, Level level) {
        super(type, level);
        this.pickup = AbstractArrow.Pickup.DISALLOWED;
        this.setNoGravity(true);
        this.setCritArrow(true);
    }

    /**
     * 发射一发。参数全部显式传进来，不读全局状态 —— 这样「普通骷髅」与「骸骨射手」两套档位
     * 可以共用这一个入口，强度差异只体现在调用参数上。
     */
    public static GiantArrow launch(ServerLevel level, LivingEntity shooter, LivingEntity target,
                                    float baseDamage, float speed, int knockback,
                                    double turnDegrees, int lifeTicks) {
        GiantArrow arrow = new GiantArrow(com.apocalypse.zombies.registry.ModEntities.GIANT_ARROW.get(), level);
        arrow.setOwner(shooter);
        arrow.setBaseDamage(baseDamage);
        arrow.setKnockback(knockback);
        arrow.turnDegrees = turnDegrees;
        arrow.lifeTicks = lifeTicks;
        arrow.seekerId = target.getId();

        Vec3 eye = shooter.getEyePosition();
        Vec3 aim = new Vec3(target.getX(), target.getY(0.5D), target.getZ());
        Vec3 direction = aim.subtract(eye).normalize();
        Vec3 muzzle = eye.add(direction.scale(0.9D));
        arrow.setPos(muzzle.x, muzzle.y, muzzle.z);
        arrow.shoot(direction.x, direction.y, direction.z, speed, 0.0F);
        level.addFreshEntity(arrow);

        level.sendParticles(ParticleTypes.CRIT, muzzle.x, muzzle.y, muzzle.z, 10,
                0.15D, 0.15D, 0.15D, 0.2D);
        // 低音调 = 更重的一发，与普通箭的 ARROW_SHOOT 区分开
        shooter.playSound(SoundEvents.ARROW_SHOOT, 1.8F, 0.55F);
        return arrow;
    }

    @Override
    public void tick() {
        super.tick();
        if (this.level().isClientSide()) {
            return;
        }
        if (this.lifeTicks-- <= 0) {
            this.discard();
            return;
        }
        if (this.inGround) {
            return;
        }
        if (!(this.level() instanceof ServerLevel level) || this.seekerId < 0) {
            return;
        }
        Entity seeker = level.getEntity(this.seekerId);
        if (!(seeker instanceof LivingEntity target) || !target.isAlive()) {
            return;
        }

        Vec3 current = this.getDeltaMovement();
        double speed = current.length();
        if (speed < 1.0E-4D) {
            return;
        }
        Vec3 currentDir = current.scale(1.0D / speed);

        // 轻微预判：按剩余飞行时间的一半提前，追得上横跑的玩家，又不至于打提前量打成过冲
        Vec3 aim = new Vec3(target.getX(), target.getY(0.5D), target.getZ())
                .add(target.getDeltaMovement().scale(0.5D));
        Vec3 wantDir = aim.subtract(this.position()).normalize();

        double dot = Mth.clamp(currentDir.dot(wantDir), -1.0D, 1.0D);
        double angle = Math.acos(dot);
        double maxTurn = Math.toRadians(this.turnDegrees);
        double mix = angle <= 1.0E-6D ? 1.0D : Math.min(1.0D, maxTurn / angle);

        Vec3 steered = currentDir.scale(1.0D - mix).add(wantDir.scale(mix));
        if (steered.lengthSqr() < 1.0E-8D) {
            return;
        }
        this.setDeltaMovement(steered.normalize().scale(speed));
    }

    /** 这一发的转向速率（度 / tick）。转发给箭的 NBT，存档再读回来时用得上。 */
    public double getTurnDegrees() {
        return this.turnDegrees;
    }

    @Override
    public void addAdditionalSaveData(CompoundTag tag) {
        super.addAdditionalSaveData(tag);
        tag.putInt("GiantSeeker", this.seekerId);
        tag.putDouble("GiantTurn", this.turnDegrees);
        tag.putInt("GiantLife", this.lifeTicks);
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag) {
        super.readAdditionalSaveData(tag);
        this.seekerId = tag.getInt("GiantSeeker");
        if (tag.contains("GiantTurn")) {
            this.turnDegrees = tag.getDouble("GiantTurn");
        }
        if (tag.contains("GiantLife")) {
            this.lifeTicks = tag.getInt("GiantLife");
        }
    }
}
