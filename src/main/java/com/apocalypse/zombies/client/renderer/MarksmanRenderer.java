package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.model.MarksmanModel;
import com.apocalypse.zombies.entity.MarksmanSkeleton;

import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.resources.ResourceLocation;

/** 骸骨射手：骨架体型（0.6 × 1.99），贴图沿用原版骷髅的 64×32 布局。 */
public class MarksmanRenderer extends EliteMobRenderer<MarksmanSkeleton, MarksmanModel> {

    private static final ResourceLocation TEXTURE = new ResourceLocation(
            ApocalypseZombies.MOD_ID, "textures/entity/marksman_skeleton.png");

    public MarksmanRenderer(EntityRendererProvider.Context context) {
        super(context, new MarksmanModel(context.bakeLayer(MarksmanModel.LAYER)), TEXTURE, 0.5F, 1.0F);
    }
}
