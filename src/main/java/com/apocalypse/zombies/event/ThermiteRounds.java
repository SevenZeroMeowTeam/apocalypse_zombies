package com.apocalypse.zombies.event;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.item.AmmoType;
import com.apocalypse.zombies.item.GunItem;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.monster.Enemy;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraftforge.event.entity.living.LivingHurtEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * 铝热弹：装了它的枪打中敌对生物，就把对方点着。
 *
 * <p><b>为什么做成一件事而不是五件事</b>：五把枪的命中逻辑各不相同（S686 是逐颗弹丸判定、
 * 栓动枪是单发 hitscan），但它们最终都会落到一次 {@code hurt()} 上，也就是这个事件。所以这里一处
 * 覆盖全部武器 —— 将来新增的枪也自动生效，不需要各自记得去调用什么。这也是"其他武器新增铝热弹"
 * 这个需求能一行不改地落到 AWM / M1 / 莫辛 / Uzi / 十字弩上的原因。</p>
 *
 * <p>只烧 {@link Enemy}：打中自己的狗、村民或队友都不该点着火。伤害数值本身不动，价值在灼烧 ——
 * 那正是玩家选它的理由（对高血量目标比多打几发划算）。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class ThermiteRounds {

    private ThermiteRounds() {
    }

    @SubscribeEvent
    public static void onLivingHurt(LivingHurtEvent event) {
        if (!(event.getSource().getEntity() instanceof Player player)) {
            return;
        }
        if (!(event.getEntity() instanceof Enemy)) {
            return;
        }
        ItemStack stack = player.getMainHandItem();
        if (!(stack.getItem() instanceof GunItem gun)) {
            return;
        }
        AmmoType ammo = gun.currentAmmo(stack);
        if (ammo.fireSeconds() <= 0) {
            return;
        }
        LivingEntity target = event.getEntity();
        // 已经烧起来的就刷新时长，而不是叠加 —— 否则连发枪能把目标钉在火里无限期
        target.setSecondsOnFire(Math.max(target.getRemainingFireTicks() / 20, ammo.fireSeconds()));
    }
}
