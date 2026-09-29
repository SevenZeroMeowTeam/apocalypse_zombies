package com.apocalypse.zombies.client;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.entity.AbstractEliteZombie;
import com.apocalypse.zombies.zombie.EvolutionTier;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.model.EntityModel;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLivingEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Makes evolved zombies visibly bigger, scaling about their feet so they stay on the ground. */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class ZombieRenderEvents {

    private ZombieRenderEvents() {
    }

    @SubscribeEvent
    public static void onRenderLivingPre(RenderLivingEvent.Pre<LivingEntity, EntityModel<LivingEntity>> event) {
        float scale = scaleFor(event.getEntity());
        if (scale == 1.0F) {
            return;
        }
        PoseStack pose = event.getPoseStack();
        pose.pushPose();
        pose.scale(scale, scale, scale);
    }

    @SubscribeEvent
    public static void onRenderLivingPost(RenderLivingEvent.Post<LivingEntity, EntityModel<LivingEntity>> event) {
        if (scaleFor(event.getEntity()) == 1.0F) {
            return;
        }
        event.getPoseStack().popPose();
    }

    private static float scaleFor(LivingEntity entity) {
        // 特殊敌对生物不走进化 tier，体型固定，别被 tier 表的默认值误伤
        if (!(entity instanceof Zombie) || entity instanceof AbstractEliteZombie) {
            return 1.0F;
        }
        EvolutionTier tier = ClientZombieTiers.getTier(entity.getId());
        return tier.getRenderScale();
    }
}
