package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.model.CorroderModel;
import com.apocalypse.zombies.entity.CorroderZombie;

import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.resources.ResourceLocation;

/** 腐蚀者：体型和原版僵尸一致，贴图 64×64。 */
public class CorroderRenderer extends EliteMobRenderer<CorroderZombie, CorroderModel> {

    private static final ResourceLocation TEXTURE = new ResourceLocation(
            ApocalypseZombies.MOD_ID, "textures/entity/corroder_zombie.png");

    public CorroderRenderer(EntityRendererProvider.Context context) {
        super(context, new CorroderModel(context.bakeLayer(CorroderModel.LAYER)), TEXTURE, 0.5F, 1.0F);
    }
}
