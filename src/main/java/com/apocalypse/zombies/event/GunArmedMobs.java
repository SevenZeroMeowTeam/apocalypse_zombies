package com.apocalypse.zombies.event;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.AbstractEliteZombie;
import com.apocalypse.zombies.entity.BrideZombie;
import com.apocalypse.zombies.entity.CharmedZombie;
import com.apocalypse.zombies.entity.CorroderZombie;
import com.apocalypse.zombies.entity.GunAttackGoal;
import com.apocalypse.zombies.entity.SoldierZombie;
import com.apocalypse.zombies.item.GunItem;
import com.apocalypse.zombies.item.GunProfile;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.entity.ai.goal.MeleeAttackGoal;
import net.minecraft.world.entity.ai.goal.WrappedGoal;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraft.world.item.ItemStack;
import net.minecraftforge.event.entity.living.LivingEvent;
import net.minecraftforge.event.entity.living.MobSpawnEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * 「手持武器就发射，不要近战」—— 配枪与挂 Goal 这两件事的落点。
 *
 * <p>这条规则由两个钩子拼成：</p>
 * <ol>
 *   <li><b>刷出时配枪</b>（{@link MobSpawnEvent.FinalizeSpawn}）：按 {@link Config#ELITE_GUN_CHANCE}
 *       给一部分敌对僵尸手里塞一把枪。掉落率刻意设 0 —— 与召奬同一条纪律，
 *       这条路不该变成玩家的免费枪械补给线。</li>
 *   <li><b>每 tick 兜底挂 Goal</b>（{@link LivingEvent.LivingTickEvent}）：只要主手是枪，
 *       就确保有一条 {@link GunAttackGoal}。这样三件事一次覆盖 —— 配枪刷出来的、倒地掉枪后
 *       被别的僵尸捡起来的、以及召奬那种「先出生、后被 {@code armMinion} 塞枪」的。</li>
 * </ol>
 *
 * <p>为什么不做成「给每个僵尸类都写一遍 registerGoals」：原版僵尸、尸潮里刷出的普通僵尸、
 * 以及数不清的其它模组的僵尸都是 {@link Zombie}，挨个改是改不完的；而判定条件只是一句
 * {@code getMainHandItem().getItem() instanceof GunItem}，绝大多数 tick 上第一次 instanceof
 * 就返回了，代价可以忽略。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID)
public final class GunArmedMobs {

    private GunArmedMobs() {
    }

    /** 刷出时配枪。与进化 tier 无关，所以不挂在 {@code CommonEvents} 那个「非精英」分支里。 */
    @SubscribeEvent
    public static void onFinalizeSpawn(MobSpawnEvent.FinalizeSpawn event) {
        if (!(event.getEntity() instanceof Zombie zombie) || hasItsOwnRangedWeapon(zombie)) {
            return;
        }
        if (!(event.getLevel() instanceof ServerLevel level)) {
            return;
        }
        boolean elite = zombie instanceof AbstractEliteZombie;
        double chance = elite ? Config.ELITE_GUN_CHANCE.get() : Config.ZOMBIE_GUN_CHANCE.get();
        if (level.getRandom().nextDouble() >= chance) {
            return;
        }
        GunProfile profile = GunProfile.random(level.getRandom());
        zombie.setItemInHand(InteractionHand.MAIN_HAND, new ItemStack(profile.item()));
        zombie.setDropChance(EquipmentSlot.MAINHAND, 0.0F);
    }

    /** 手里出现枪就补 Goal。判定放在最前面，非持枪僵尸一次 instanceof 就返回。 */
    @SubscribeEvent
    public static void onLivingTick(LivingEvent.LivingTickEvent event) {
        if (event.getEntity().level().isClientSide()) {
            return;
        }
        if (!(event.getEntity() instanceof Zombie zombie)) {
            return;
        }
        if (!(zombie.getMainHandItem().getItem() instanceof GunItem)) {
            return;
        }
        ensureGunGoal(zombie);
    }

    /**
     * 已经有开火 Goal 的不再加第二遍；顺带保证「近战出口」存在。
     *
     * <p>近战出口是「敌人靠近自动切近战」的另一半：{@link GunAttackGoal} 贴脸时会交出 MOVE，
     * 但交出去得有人接。原版僵尸自己带 {@code ZombieAttackGoal}（{@link MeleeAttackGoal} 的
     * 子类，2 号位），所以绝大多数情况这里什么都不用做；只有别的模组那种「有枪没拳头」的怪
     * 才需要补一条。用 {@code instanceof MeleeAttackGoal} 判定而不是比类名，正是为了把
     * {@code ZombieAttackGoal} 这类子类一起算进去，免得补出第二条近战 Goal 变成双倍伤害。</p>
     */
    private static void ensureGunGoal(Zombie zombie) {
        boolean hasGun = false;
        boolean hasMelee = false;
        for (WrappedGoal wrapped : zombie.goalSelector.getAvailableGoals()) {
            Goal goal = wrapped.getGoal();
            if (goal instanceof GunAttackGoal) {
                hasGun = true;
            } else if (goal instanceof MeleeAttackGoal) {
                hasMelee = true;
            }
        }
        if (!hasMelee) {
            zombie.goalSelector.addGoal(2, new MeleeAttackGoal(zombie, 1.0D, false));
        }
        if (!hasGun) {
            zombie.goalSelector.addGoal(1, new GunAttackGoal(zombie));
        }
    }

    /**
     * 已经有自己的远程身份的那几只不该再配枪：残兵是弓 + 投掷 TNT，腐蚀者是酸液弹，
     * 美女僵尸与她召出来的召奬走各自的配枪通道（{@code armMinion}）。
     */
    private static boolean hasItsOwnRangedWeapon(Zombie zombie) {
        return zombie instanceof SoldierZombie
                || zombie instanceof CorroderZombie
                || zombie instanceof CharmedZombie
                || zombie instanceof BrideZombie;
    }
}
