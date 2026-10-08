package com.apocalypse.zombies.event;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.item.AmmoType;
import com.apocalypse.zombies.item.GunItem;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.monster.Enemy;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.entity.living.LivingHurtEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * 弹种命中敌对生物之后的特殊效果：铝热弹点燃、爆炸弹炸开。
 *
 * <p><b>为什么全部落在一个事件上</b>：五把枪的命中逻辑各不相同（S686 是逐颗弹丸判定、栓动枪是单发
 * hitscan、Uzi 是连发），但它们最终都会落到一次 {@code hurt()} 上，也就是这个事件。所以这里一处就
 * 覆盖了全部武器 —— 「给所有武器加铝热弹 / 爆炸弹」是零逐枪改动的，将来新增的枪也自动生效。</p>
 *
 * <p>两条共同的前提：只对 {@link Enemy} 生效（打中自己的狗、村民或队友都不点火也不炸），以及
 * 玩家自己永远不在伤害范围内（贴脸开枪不该把自己炸了）。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class AmmoEffects {

    private AmmoEffects() {
    }

    @SubscribeEvent
    public static void onLivingHurt(LivingHurtEvent event) {
        if (!(event.getSource().getEntity() instanceof Player player)) {
            return;
        }
        if (!(event.getEntity() instanceof Enemy)) {
            return;
        }
        if (!(player.level() instanceof ServerLevel level)) {
            return;
        }
        ItemStack stack = player.getMainHandItem();
        if (!(stack.getItem() instanceof GunItem gun)) {
            return;
        }

        // Enemy 只是个标记接口，不继承 Entity —— 真正要操作的是那次 hurt 的受害者本体
        LivingEntity target = event.getEntity();
        AmmoType ammo = gun.currentAmmo(stack);
        if (ammo.fireSeconds() > 0) {
            // 铝热弹：已经烧起来的只刷新时长，不叠加 —— 否则连发枪能把目标钉在火里无限期
            target.setSecondsOnFire(Math.max(target.getRemainingFireTicks() / 20, ammo.fireSeconds()));
        }
        if (ammo == AmmoType.EXPLOSIVE) {
            detonate(level, player, target);
        }
    }

    /**
     * 在目标身上炸开一小片。只结算伤害，不破坏方块、不点火 —— 一颗子弹不该改变地形。
     */
    private static void detonate(ServerLevel level, Player player, LivingEntity target) {
        Vec3 at = target.position().add(0.0D, target.getBbHeight() * 0.5D, 0.0D);
        level.sendParticles(ParticleTypes.EXPLOSION_EMITTER, at.x, at.y, at.z, 1, 0.0D, 0.0D, 0.0D, 0.0D);
        level.playSound(null, at.x, at.y, at.z, SoundEvents.GENERIC_EXPLODE,
                SoundSource.PLAYERS, 1.0F, 1.0F);

        // 原版的爆炸伤害类型：死亡消息与免疫规则都跟着走，不必自造一套
        DamageSource source = player.damageSources().explosion(player, player);
        double radius = AmmoType.EXPLOSION_RADIUS;
        for (LivingEntity victim : level.getEntitiesOfClass(LivingEntity.class,
                new AABB(at, at).inflate(radius))) {
            if (victim == player || !(victim instanceof Enemy)) {
                continue;
            }
            double distance = victim.position().distanceTo(at);
            float damage = AmmoType.EXPLOSION_DAMAGE * (float) Math.max(0.0D, 1.0D - distance / radius);
            if (damage <= 0.0F) {
                continue;
            }
            // 弹丸刚打中的那个目标正处于受击无敌帧里，不清掉的话爆炸对它一点用没有
            victim.invulnerableTime = 0;
            victim.hurt(source, damage);
        }
    }
}
