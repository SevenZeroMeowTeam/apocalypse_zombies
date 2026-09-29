package com.apocalypse.zombies.entity.ai;

import java.util.EnumSet;

import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.goal.Goal;

/**
 * 围猎：接近的过程中散开包抄，而不是排成一列纵队冲上来。
 *
 * <p>原版近战怪只有「冲」这一种走位，十几只僵尸会挤在同一条直线上，前排挡后排、看起来像一坨。
 * 这条 Goal 在<b>进入近身距离之前</b>接管移动：绕到目标周围的等分方位上再压上，
 * 于是尸群呈扇形合围，玩家会同时感到「前后左右都有人」。</p>
 *
 * <p>关键取巧：<b>方位由实体 id 决定</b>，不是随机抽的。同一只怪在整场追击里守住自己的方位
 * （队伍自然散开、不会互相抢位），也不会出现「两只怪每次都抽到同一格」。</p>
 *
 * <p>两条硬约束，写反任何一条这条 Goal 都会变成死代码：</p>
 * <ol>
 *   <li><b>优先级必须比近战 Goal 的数字小</b>（也就是更优先）。近战 Goal 的 {@code canUse}
 *       通常只看「有没有目标」，它会一直占着 MOVE；挂在其后的 Goal 一次都拿不到移动通道。</li>
 *   <li><b>{@code canUse} 必须在「还没贴身」时为真</b>（{@code distance > engage}）。
 *       进了近身距离就退出，把移动通道交还给近战/攻击 Goal。</li>
 * </ol>
 *
 * <p>同样因为这个理由，已经有远程攻击 Goal 的怪不该挂这条：它们要的是拉距离而不是贴身，
 * 交由调用方（{@code MobAiEnhanced}）判断。</p>
 */
public class SurroundGoal extends Goal {

    /** 等分方位数：八方向足够散开，再多会挤在目标背后。 */
    private static final int SLOTS = 8;

    /** 包抄窗口：从 engage 再往外这么多格之内才值得绕位，更远就直接冲过去。 */
    private static final double CHASE_WINDOW = 12.0D;

    private final Mob mob;
    private final double speed;
    private final double engage;
    private final double ringRadius;

    private int slot;
    private int refresh;

    public SurroundGoal(Mob mob, double speed, double engage, double ringRadius) {
        this.mob = mob;
        this.speed = speed;
        this.engage = engage;
        this.ringRadius = ringRadius;
        this.setFlags(EnumSet.of(Goal.Flag.MOVE));
    }

    @Override
    public boolean canUse() {
        LivingEntity target = this.mob.getTarget();
        if (target == null || !target.isAlive()) {
            return false;
        }
        double distance = this.mob.distanceTo(target);
        // 还没贴身才包抄；进了近身距离就退出，把 MOVE 让给近战/攻击 Goal
        return distance > this.engage && distance <= this.engage + CHASE_WINDOW;
    }

    @Override
    public boolean canContinueToUse() {
        LivingEntity target = this.mob.getTarget();
        if (target == null || !target.isAlive()) {
            return false;
        }
        double distance = this.mob.distanceTo(target);
        // 1 格迟滞：避免在 engage 边界上反复进出、每 tick 换一次走位目标
        return distance > this.engage - 1.0D && distance <= this.engage + CHASE_WINDOW + 4.0D;
    }

    @Override
    public void start() {
        this.slot = Math.abs(this.mob.getId()) % SLOTS;
        this.refresh = 0;
    }

    @Override
    public void stop() {
        this.mob.getNavigation().stop();
    }

    @Override
    public void tick() {
        if (--this.refresh > 0) {
            return;
        }
        this.refresh = 40;
        LivingEntity target = this.mob.getTarget();
        if (target == null) {
            return;
        }
        double angle = this.slot * (Math.PI * 2.0D) / SLOTS;
        double x = target.getX() + Math.cos(angle) * this.ringRadius;
        double z = target.getZ() + Math.sin(angle) * this.ringRadius;
        this.mob.getNavigation().moveTo(x, target.getY(), z, this.speed);
    }
}
