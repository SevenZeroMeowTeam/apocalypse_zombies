package com.apocalypse.zombies.entity;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.item.GunProfile;
import com.apocalypse.zombies.registry.ModEntities;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.phys.Vec3;

import java.util.EnumSet;

/**
 * 「手里有枪就开枪」：给怪物用的开火 Goal。
 *
 * <p>装到任何 {@link Mob} 上都行，它自己每 tick 看主手拿的是不是枪（{@link GunProfile#of}），
 * 不是枪就完全不介入。谁配枪、配什么枪由各自的刷怪逻辑管，这条 Goal 只管开火。</p>
 *
 * <p>四条刻意的设计：</p>
 * <ul>
 *   <li><b>占 MOVE 标记，但会还</b> —— 原版近战 Goal 用的是同一个标记，所以「正在开枪」期间
 *       近战抢不到执行权，这就是「发射而不是近战」在引擎层的实现方式。但<b>占着不还就等于
 *       近战永远失效</b>：目标贴到 {@link #MELEE_HANDOFF} 以内时 {@code canUse} 转假、把通道
 *       还回去，原版近战立刻接手抡爪子。射程内长时间没有视线时同理让位，让原版寻路去绕障碍，
 *       而不是顶着墙站着。</li>
 *   <li><b>游走射击</b> —— 射程内不再原地站桩：每 {@link #STRAFE_INTERVAL} tick 换一条侧向
 *       腿，左右交替地保持半径绕圈。站着不动的枪手既好打又像木桩。</li>
 *   <li><b>预判走位但只打七折</b> —— 按弹丸飞行时间提前量瞄准，再乘 {@value #LEAD_FACTOR}：
 *       不预判则永远打不中跑动的人，满预判则走位失去意义。</li>
 *   <li><b>换弹不停步</b> —— 换弹只掐掉开火，走位照走（旧版是原地站着换完）。</li>
 * </ul>
 */
public class GunAttackGoal extends Goal {

    /**
     * 目标进到这个距离就交还 MOVE，让原版近战接手。
     *
     * <p>这是「敌人靠近自动切近战」的全部机关所在：不给近战让路，枪手占着 MOVE 就永远是
     * 站桩开枪。实际距离读 {@link Config#GUN_MELEE_HANDOFF_RANGE}，填 0 即关掉。</p>
     */
    private static final double MELEE_HANDOFF = 3.0D;

    /** 提前量的折扣：1.0 = 完美预判，0 = 完全按当前坐标瞄。 */
    private static final double LEAD_FACTOR = 0.7D;

    /** 枪口前移量（格）：子弹从眼睛前方出膛，别从脸里冒出来。 */
    private static final double MUZZLE_FORWARD = 0.7D;

    /** 游走射击：每隔这么多 tick 换一条腿。 */
    private static final int STRAFE_INTERVAL = 30;

    /** 一条腿侧移多远（格）。 */
    private static final double STRAFE_STEP = 3.0D;

    /** 侧移时的移动速度倍率。 */
    private static final double STRAFE_SPEED = 1.0D;

    private final Mob mob;

    /** 距离下一发还有多少 tick。 */
    private int cooldown;

    /** 当前弹匣里还剩几发；{@code -1} 表示还没装载（见到枪才填满）。 */
    private int rounds = -1;

    /** 换弹还需要多少 tick；> 0 期间不开火，但走位照旧。 */
    private int reloadTicks;

    /** 射程内连续看不到目标的 tick 数，数满就让位给原版寻路。 */
    private int blindTicks;

    /** 离换下一条腿还有多少 tick。 */
    private int strafeTicks;

    /** 侧移方向：每次换腿取反，于是左右交替而不是一直往同一边绕圈。 */
    private int strafeSign = 1;

    public GunAttackGoal(Mob mob) {
        this.mob = mob;
        this.setFlags(EnumSet.of(Flag.MOVE, Flag.LOOK));
    }

    @Override
    public boolean canUse() {
        LivingEntity target = this.mob.getTarget();
        if (target == null || this.heldGun() == null) {
            return false;
        }
        double distance = this.mob.distanceTo(target);

        // 贴脸：把 MOVE 交回近战（不还的话原版近战 Goal 一次都跑不了）
        double handoff = Config.GUN_MELEE_HANDOFF_RANGE.get();
        if (handoff > 0.0D && distance <= handoff) {
            return false;
        }
        // 射程内却长时间看不见目标：也让位，让它绕过去
        GunProfile profile = this.heldGunProfile();
        return distance > profile.range() || this.blindTicks < Config.GUN_BLIND_HANDOFF_TICKS.get();
    }

    @Override
    public boolean canContinueToUse() {
        // 与 canUse 同一套判据：近距离与「看不见」都算主动让出通道，不是还在开火
        return this.canUse();
    }

    @Override
    public void start() {
        if (this.rounds < 0) {
            GunProfile profile = this.heldGunProfile();
            this.rounds = profile == null ? 0 : profile.magazineSize();
        }
        this.cooldown = 10;
        this.blindTicks = 0;
        this.strafeTicks = 0;
    }

    @Override
    public void stop() {
        this.mob.getNavigation().stop();
        // 让位时清零：否则「数满 40 tick」会一直成立，这条 Goal 再也不会重新接管
        this.blindTicks = 0;
    }

    @Override
    public void tick() {
        LivingEntity target = this.mob.getTarget();
        GunProfile profile = this.heldGunProfile();
        if (target == null || profile == null) {
            return;
        }
        if (this.rounds < 0) {
            this.rounds = profile.magazineSize();
        }

        // ---- 走位：放在开火之前，枪手不该为了开枪变成雕像，换弹期间也照走
        double distance = this.mob.distanceTo(target);
        this.mob.getLookControl().setLookAt(target, 30.0F, 30.0F);
        boolean sighted = this.mob.getSensing().hasLineOfSight(target);

        // ---- 走位放在开火之前：枪手不该为了开枪变成雕像，换弹期间也照走
        if (distance > profile.range()) {
            // 太远就靠上去；「看不见」的计数在这里清零（本来就在往近处走）
            this.blindTicks = 0;
            this.mob.getNavigation().moveTo(target, 1.0D);
            return;
        }
        if (sighted) {
            this.blindTicks = 0;
            if (Config.GUN_STRAFE_ENABLED.get()) {
                this.strafe();
            } else {
                this.mob.getNavigation().stop();
            }
        } else {
            // 射程内但看不见：一边往前挤一边数，数满由 canUse 让位给寻路
            this.blindTicks++;
            this.mob.getNavigation().moveTo(target, 1.0D);
        }

        if (this.reloadTicks > 0) {
            if (--this.reloadTicks == 0) {
                this.rounds = profile.magazineSize();
                this.mob.playSound(profile.reloadSound().get(), 1.2F, 1.0F);
            }
            return;
        }
        if (this.cooldown > 0) {
            this.cooldown--;
            return;
        }
        if (!sighted) {
            return;
        }
        if (this.rounds <= 0) {
            this.reloadTicks = profile.reloadTicks();
            return;
        }
        this.fire(target, profile);
    }

    /**
     * 游走射击：保持与目标的距离、左右交替地侧移。
     *
     * <p>一条腿只下一次移动指令 —— 每 tick 重发会让寻路反复作废，看起来像原地抽搐。
     * 落点取 {@code mob.position() + side × STEP}，天然保持当前半径，不会越绕越近。</p>
     */
    private void strafe() {
        if (--this.strafeTicks > 0) {
            return;
        }
        this.strafeTicks = STRAFE_INTERVAL;
        this.strafeSign = -this.strafeSign;

        LivingEntity target = this.mob.getTarget();
        if (target == null) {
            return;
        }
        Vec3 toTarget = target.position().subtract(this.mob.position());
        Vec3 flat = new Vec3(toTarget.x, 0.0D, toTarget.z);
        if (flat.lengthSqr() < 1.0E-4D) {
            return;
        }
        Vec3 forward = flat.normalize();
        Vec3 side = new Vec3(-forward.z * this.strafeSign, 0.0D, forward.x * this.strafeSign);
        Vec3 spot = this.mob.position().add(side.scale(STRAFE_STEP));
        this.mob.getNavigation().moveTo(spot.x, spot.y, spot.z, STRAFE_SPEED);
    }

    /** 打一发：出膛 + 曳光（子弹自己带）+ 枪声 + 枪口烟火。 */
    private void fire(LivingEntity target, GunProfile profile) {
        if (!(this.mob.level() instanceof ServerLevel level)) {
            return;
        }
        Vec3 eye = this.mob.getEyePosition();
        Vec3 aim = target.position()
                .add(0.0D, target.getBbHeight() * 0.55D, 0.0D)
                .add(target.getDeltaMovement().scale(
                        this.mob.distanceTo(target) / profile.bulletSpeed() * LEAD_FACTOR));
        Vec3 direction = this.spread(aim.subtract(eye).normalize(), profile.spread());
        Vec3 muzzle = eye.add(direction.scale(MUZZLE_FORWARD));

        BulletProjectile bullet = new BulletProjectile(ModEntities.BULLET.get(), this.mob, level);
        bullet.load(profile);
        bullet.setPos(muzzle.x, muzzle.y, muzzle.z);
        bullet.shoot(direction.x, direction.y, direction.z, profile.bulletSpeed(), 0.0F);
        level.addFreshEntity(bullet);

        level.sendParticles(ParticleTypes.SMOKE, muzzle.x, muzzle.y, muzzle.z, 4,
                0.05D, 0.05D, 0.05D, 0.02D);
        level.sendParticles(ParticleTypes.FLAME, muzzle.x, muzzle.y, muzzle.z, 2,
                0.02D, 0.02D, 0.02D, 0.0D);
        // 枪声走 LivingEntity#playSound：周围玩家都听得到，这正是「第三人称枪声」的用途
        this.mob.playSound(profile.shotSound().get(), 1.5F, 1.0F);

        this.rounds--;
        this.cooldown = profile.cooldownTicks();
    }

    /**
     * 在以 {@code direction} 为轴的圆锥里取一个随机方向。
     * 取的是圆盘上的均匀分布（半径用开方）而不是半径均匀 —— 后者会全都挤在圆周上。
     */
    private Vec3 spread(Vec3 direction, float degrees) {
        if (degrees <= 0.0F) {
            return direction;
        }
        Vec3 side = direction.cross(new Vec3(0.0D, 1.0D, 0.0D));
        if (side.lengthSqr() < 1.0E-6D) {
            side = new Vec3(1.0D, 0.0D, 0.0D);
        }
        side = side.normalize();
        Vec3 up = side.cross(direction).normalize();
        double angle = this.mob.getRandom().nextDouble() * Math.PI * 2.0D;
        double radius = Math.tan(Math.toRadians(degrees)) * Math.sqrt(this.mob.getRandom().nextDouble());
        return direction.add(side.scale(Math.cos(angle) * radius))
                .add(up.scale(Math.sin(angle) * radius))
                .normalize();
    }

    private ItemStack heldGun() {
        ItemStack stack = this.mob.getMainHandItem();
        return GunProfile.of(stack) == null ? null : stack;
    }

    private GunProfile heldGunProfile() {
        return GunProfile.of(this.mob.getMainHandItem());
    }

    /** 供刷怪逻辑与调试用：这只怪现在会不会开枪。 */
    public boolean hasAmmo() {
        return this.rounds != 0;
    }
}
