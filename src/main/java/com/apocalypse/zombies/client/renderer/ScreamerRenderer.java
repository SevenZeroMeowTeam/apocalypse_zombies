package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.model.ScreamerModel;
import com.apocalypse.zombies.entity.ScreamerZombie;

import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.resources.ResourceLocation;

/** 尖啸者：体型和原版僵尸一致，贴图 64×64。 */
public class ScreamerRenderer extends EliteMobRenderer<ScreamerZombie, ScreamerModel> {

    private static final ResourceLocation TEXTURE = new ResourceLocation(
            ApocalypseZombies.MOD_ID, "textures/entity/screamer_zombie.png");

    public ScreamerRenderer(EntityRendererProvider.Context context) {
        super(context, new ScreamerModel(context.bakeLayer(ScreamerModel.LAYER)), TEXTURE, 0.5F, 1.0F);
    }
}
