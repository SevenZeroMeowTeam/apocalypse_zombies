package com.apocalypse.zombies.entity.ai;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.entity.CharmedZombie;

import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.entity.OwnableEntity;
import net.minecraft.world.entity.TamableAnimal;
import net.minecraft.world.entity.player.Player;
import net.minecraftforge.registries.ForgeRegistries;

/**
 * 阵营判据：谁是「自己人」。
 *
 * <p>为什么需要它：原版 {@code HurtByTargetGoal.canUse()} 只做「看得见 + 够得着」判定
 * （1.20.1 源码链：{@code HurtByTargetGoal.canUse} → {@code TargetGoal.canAttack} →
 * {@code TargetingConditions}），<b>完全不看阵营</b>。于是本模组自己的范围伤害一旦擦到同类
 * —— 爆破兵的 TNT 爆炸、枪怪流弹、腐蚀液、抛花刺 —— 被打的那个 {@code LastHurtByMob}
 * 就被写下，下一 tick 立刻回击。内斗的全部来源就是这一条。</p>
 *
 * <p>三档归属，各按各的规矩：</p>
 * <ul>
 *   <li><b>亡者阵营</b>（{@link #isHorde}）—— 天然的敌对生物，也就是「不会互相攻击」这条
 *       规则保护的双方。</li>
 *   <li><b>美女僵尸那边的人</b>（{@link #isBrideSide}）—— {@link CharmedZombie}（策反来的
 *       僵尸 / 选妃小队 / 摄魂幽灵）。它们的目标表里<b>故意没有玩家、只打僵尸</b>，
 *       整条技能树就是为了让僵尸咬起来；把它们算进「自己人」等于把技能删了。
 *       所以它们<b>整类豁免</b>：与任何一方的冲突都照旧。</li>
 *   <li><b>玩家那边的人</b>（{@link #isPlayerSide}）—— 被驯服的、主人是玩家的召唤物。
 *       它们打怪是玩家在打怪，不该被这条规则拦住。</li>
 * </ul>
 */
public final class AllyJudge {

    private AllyJudge() {
    }

    /**
     * 是不是「天然敌对生物」—— 本模组的怪与原版怪一视同仁，因为事件层里根本分不出
     * 别的模组注册的怪（那些类不在本仓库）。
     */
    public static boolean isHorde(Entity entity) {
        return entity instanceof Monster && !isBrideSide(entity) && !isPlayerSide(entity);
    }

    /** 美女僵尸的召唤物 / 策反物：整类豁免，它们的战斗是设计内容。 */
    public static boolean isBrideSide(Entity entity) {
        return entity instanceof CharmedZombie;
    }

    /** 玩家阵营：被驯服的生物，以及主人是玩家的召唤物。 */
    public static boolean isPlayerSide(Entity entity) {
        if (entity instanceof TamableAnimal tameable && tameable.isTame()) {
            return true;
        }
        return entity instanceof OwnableEntity ownable && ownable.getOwner() instanceof Player;
    }

    /** 两只生物是不是同一阵营的自己人（双方都在亡者阵营才算）。 */
    public static boolean isAlly(Entity a, Entity b) {
        return isHorde(a) && isHorde(b);
    }

    /** 是不是本模组注册的怪 —— 只按注册名的命名空间判，不列类名清单（加了新怪自动算进来）。 */
    public static boolean isModMob(Entity entity) {
        ResourceLocation id = ForgeRegistries.ENTITY_TYPES.getKey(entity.getType());
        return id != null && ApocalypseZombies.MOD_ID.equals(id.getNamespace());
    }
}
