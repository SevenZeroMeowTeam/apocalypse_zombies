package com.apocalypse.zombies.entity.ai;

import java.util.EnumSet;
import java.util.List;

import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.entity.ai.targeting.TargetingConditions;
import net.minecraft.world.entity.animal.IronGolem;
import net.minecraft.world.entity.npc.AbstractVillager;
import net.minecraft.world.entity.player.Player;

/**
 * 可用猎物调度器 —— 取代原来的 {@code ScentTargetGoal}，是「她为什么不打人」那个缺陷的正解。
 *
 * <p><b>缺陷现场（已运行时复现）：</b>她锁上一只「看得见但走不到」的村民（柱顶 / 石壳里）
 * 之后，目标表被 TARGET 标志位占死 —— 技能起手要视线（够不着就放不出来）、近战要距离
 * （够不着就打不出来）、优先级更低的原版条目（村民 / 铁傀儡）全都起不来，于是她站在
 * 6 格外的铁傀儡旁边一动不动，一下都不打。判据：修前铁傀儡 0 伤害、修后正常打死。</p>
 *
 * <p><b>为什么要有这条 Goal，而不是把原版那三条修一修：</b>原版 {@code TargetGoal} 的
 * {@code mustSee = false} 是「锁定后不再复检视线」，{@code mustReach = false} 是「不检查
 * 可达性」—— 后者才是死锁的根。她的表里 p2 玩家 / p3 村民 / p3 铁傀儡都是原版的，改不了；
 * 而「同伴传仇恨」（{@link SharedAggroGoal}）也是别人写好的。所以这里自建一条<b>总调度</b>：
 * 它一旦有候选就占住 TARGET，原版那三条就再也没机会把「够不着」的东西锁成死锁。</p>
 *
 * <p><b>三条设计约束：</b></p>
 * <ul>
 *   <li><b>偏好顺序照抄原版</b>：玩家（p2）→ 村民 → 铁傀儡（p3 的两条，先加的先赢）。
 *       只把「够不着」的候选剔掉，其余体感与 1.1.28 之前一致，不引入新的战术倾向。</li>
 *   <li><b>获取要视线、保持只看可达</b>：视线是原版获取目标的门槛（{@code forCombat()} 自带），
 *       保持则用 {@link PreyJudge#usable} 的路径判据 —— 于是「玩家躲墙后但仍走得到 ⇒ 她继续摸过来」
 *       这个原设计保住了，而「飞在天上 / 关在方块里 ⇒ 永不放手的死盯」被消掉。</li>
 *   <li><b>没有能用的猎物时，持有 TARGET 但把目标置空</b>（空转）：<b>不能</b>直接放手 ——
 *       一放手原版村民目标（{@code mustSee=false}）立刻会把那只够不着的村民再锁上，
 *       死锁原地复活；置空则等于「我现在没目标」，她会照常游荡、也不会去打根本够不着的东西。</li>
 * </ul>
 */
public class PreyTargetGoal extends Goal {

    /** 候选扫描间隔（tick）。原版村民/铁傀儡那两条也是 10；这里只在「目标不中用」时才提前重扫。 */
    private static final int SCAN_INTERVAL = 10;

    private final Mob mob;
    private final PreyJudge judge;
    private final TargetingConditions conditions = TargetingConditions.forCombat();

    /** 本次扫描选中的可用猎物；null = 空转（占着 TARGET 但不打）。 */
    private LivingEntity prey;
    /** 追随距离内是否存在「猎物类型」的生物（不管够不够得着）—— 决定空转还是彻底放手。 */
    private boolean anyPrey;
    private int scanCooldown;

    public PreyTargetGoal(Mob mob) {
        this.mob = mob;
        this.judge = new PreyJudge(mob);
        this.setFlags(EnumSet.of(Goal.Flag.TARGET));
    }

    @Override
    public boolean canUse() {
        this.scanIfDue();
        return this.prey != null || this.anyPrey;
    }

    @Override
    public void start() {
        this.mob.setTarget(this.prey);
    }

    @Override
    public boolean canContinueToUse() {
        if (this.prey != null && this.judge.usable(this.prey)) {
            return true;
        }
        // 目标不中用了（死了 / 走出了追随距离 / 变成够不着）：立刻重扫，不等扫描间隔，
        // 免得目标闪断一拍导致近战 Goal 停一下。
        this.scanCooldown = 0;
        this.scanIfDue();
        if (this.prey != null) {
            this.mob.setTarget(this.prey);
            return true;
        }
        if (this.anyPrey) {
            this.mob.setTarget(null);
            return true;
        }
        return false;
    }

    @Override
    public void stop() {
        // GoalSelector 的换人是「先 stop 旧 owner 再 start 新 owner」，所以这里清空是安全的：
        // 被 SharedAggroGoal / 原版还击抢走 TARGET 时，对方紧接着会把目标设回去。
        this.prey = null;
        this.anyPrey = false;
        this.scanCooldown = 0;
        this.mob.setTarget(null);
    }

    private void scanIfDue() {
        if (this.scanCooldown > 0) {
            this.scanCooldown--;
            return;
        }
        this.scan();
    }

    private void scan() {
        this.scanCooldown = SCAN_INTERVAL;
        this.prey = null;
        this.anyPrey = false;

        double range = this.judge.range();
        this.conditions.range(range);

        // 1) 玩家 —— 原版优先级最高（p2）。注意这里的视线要求来自 forCombat()：她仍然要
        //    「看见过」才能锁上，锁上之后的保持由 usable() 的路径判据负责（原设计的体感）。
        Player player = this.mob.level().getNearestPlayer(this.conditions, this.mob,
                this.mob.getX(), this.mob.getEyeY(), this.mob.getZ());
        if (player != null) {
            this.anyPrey = true;
            if (this.judge.usable(player)) {
                this.prey = player;
                return;
            }
        }

        // 2) 村民 3) 铁傀儡 —— 原版僵尸表 p3 那两条（先加的村民在平级里先赢）。这里换成自己
        //    扫两遍：既能按「用得上」筛，也能顺手记下「范围内到底有没有猎物」。
        if (this.scanPrey(AbstractVillager.class, range)) {
            return;
        }
        this.scanPrey(IronGolem.class, range);
    }

    private <T extends LivingEntity> boolean scanPrey(Class<T> type, double range) {
        List<T> candidates = this.mob.level().getEntitiesOfClass(type,
                this.mob.getBoundingBox().inflate(range), LivingEntity::isAlive);
        if (candidates.isEmpty()) {
            return false;
        }
        this.anyPrey = true;
        LivingEntity nearest = this.mob.level().getNearestEntity(candidates, this.conditions, this.mob,
                this.mob.getX(), this.mob.getEyeY(), this.mob.getZ());
        if (nearest != null && this.judge.usable(nearest)) {
            this.prey = nearest;
            return true;
        }
        return false;
    }
}
