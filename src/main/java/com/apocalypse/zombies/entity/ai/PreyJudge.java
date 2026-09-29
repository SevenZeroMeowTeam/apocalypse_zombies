package com.apocalypse.zombies.entity.ai;

import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.level.pathfinder.Node;
import net.minecraft.world.level.pathfinder.Path;

/**
 * 「这个猎物用得上吗」—— 目标调度（{@link PreyTargetGoal}）与仇恨传播
 * （{@link SharedAggroGoal}）共用的同一套判据，两边不许各判各的。
 *
 * <p><b>为什么需要它：</b>原版 {@code TargetGoal} 一旦锁定，就每 tick 把目标重新钉回去
 * （{@code canContinueToUse} 内部 {@code setTarget}），而它拿的 {@code mustSee} /
 * {@code mustReach} 参数在她的表里全是 {@code false} —— 也就是<b>锁上就永不放手</b>，
 * 且持有 TARGET 标志位把优先级更低的同表条目全部饿死。于是「看得见但走不到」的东西
 * （石头壳里的村民、柱顶上的村民、飞在天上的玩家）会占死整条通道：技能起手要求视线、
 * 近战要求距离 ⇒ 她既打不着也换不了人，表现就是站在村民/铁傀儡旁边一动不动。
 * 判据必须把「用得上」定清楚：</p>
 *
 * <ul>
 *   <li><b>有视线 ≠ 用得上</b> —— 看得见却走不到的村民正是那次死锁的现场，所以视线不做判据。</li>
 *   <li><b>判据取「走得到」</b> —— 与 {@code TargetGoal#canReachTarget} 同一套路径判定
 *       （路径存在，且终点贴在目标所在格附近），并沿用原版的节流：路径查询不便宜。</li>
 *   <li><b>贴脸例外</b> —— {@code close} 格内不再问路径：近战与技能本来就够得着，
 *       偶尔的寻路怪癖不该让她放掉眼前的目标。</li>
 * </ul>
 */
public final class PreyJudge {

    /** 「走得到吗」的判定间隔（tick）。原版 mustReach 是 10~15，这里对齐上沿。 */
    private static final int REACH_TICKS = 15;

    /** 贴脸半径：这个距离内不必问路径（近战上探 ~2.6 格 + 技能射程）。 */
    public static final double CLOSE = 3.0D;

    private final Mob mob;
    private final double close;

    /** 「走得到吗」的结果缓存：同一个对象在 {@link #REACH_TICKS} 拍内不重复问路。 */
    private LivingEntity reachFor;
    private boolean reachVerdict;
    private int reachCooldown;

    public PreyJudge(Mob mob) {
        this(mob, CLOSE);
    }

    public PreyJudge(Mob mob, double close) {
        this.mob = mob;
        this.close = Math.max(0.0D, close);
    }

    /**
     * 追随距离。读属性而不是读配置：事件层是先挂 Goal 再抬属性，运行期也可能被别的模组改。
     */
    public double range() {
        return this.mob.getAttributeValue(Attributes.FOLLOW_RANGE);
    }

    /** 便宜的那半：活着、打得到、在追随距离内。 */
    public boolean inRange(LivingEntity candidate) {
        if (candidate == null || !candidate.isAlive() || !this.mob.canAttack(candidate)) {
            return false;
        }
        double range = this.range();
        return this.mob.distanceToSqr(candidate) <= range * range;
    }

    /** 完整的「用得上」：便宜那半 + （贴脸 或 走得到）。 */
    public boolean usable(LivingEntity candidate) {
        if (!this.inRange(candidate)) {
            return false;
        }
        return this.mob.distanceToSqr(candidate) <= this.close * this.close || this.reachable(candidate);
    }

    private boolean reachable(LivingEntity candidate) {
        if (this.reachFor == candidate && this.reachCooldown > 0) {
            this.reachCooldown--;
            return this.reachVerdict;
        }
        this.reachFor = candidate;
        this.reachCooldown = REACH_TICKS;
        this.reachVerdict = canPathTo(candidate);
        return this.reachVerdict;
    }

    /**
     * 与原版 {@code TargetGoal#canReachTarget} 同一判据，但**补上垂直方向**。
     *
     * <p>原版只比 x/z（路径终点距目标所在格的水平距离）：柱顶村民的柱子底部与它 x/z 完全
     * 相同，于是「看得见却要爬 5 格」的目标会被判成走得到 —— 第一版修法就是这么漏过去的
     * （埋点显示她仍锁着柱顶村民）。地面的怪爬不上去，所以这里加一条「终点高度也得到位」。</p>
     */
    private boolean canPathTo(LivingEntity candidate) {
        Path path = this.mob.getNavigation().createPath(candidate, 0);
        if (path == null) {
            return false;
        }
        Node end = path.getEndNode();
        if (end == null) {
            return false;
        }
        int dx = end.x - candidate.getBlockX();
        int dz = end.z - candidate.getBlockZ();
        // 高度容差 1 格：台阶/半砖这些原版寻路本来就能上下，不该因此丢掉目标。
        int dy = end.y - candidate.getBlockY();
        return (double) (dx * dx + dz * dz) <= 2.25D && Math.abs(dy) <= 1;
    }
}
