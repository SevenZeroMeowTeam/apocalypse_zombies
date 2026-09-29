package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.model.CrusherModel;
import com.apocalypse.zombies.entity.CrusherZombie;

import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.resources.ResourceLocation;

/**
 * 碎颅者：碰撞箱比原版僵尸大一圈（0.7 × 2.25 对 0.6 × 1.95），
 * 模型按同样的比例放大，免得视觉和碰撞箱对不上。
 */
public class CrusherRenderer extends EliteMobRenderer<CrusherZombie, CrusherModel> {

    /** 2.25 / 1.95 ≈ 1.154，和碰撞箱的放大比例对齐。 */
    private static final float MODEL_SCALE = 1.15F;

    private static final ResourceLocation TEXTURE = new ResourceLocation(
            ApocalypseZombies.MOD_ID, "textures/entity/crusher_zombie.png");

    public CrusherRenderer(EntityRendererProvider.Context context) {
        super(context, new CrusherModel(context.bakeLayer(CrusherModel.LAYER)), TEXTURE, 0.6F, MODEL_SCALE);
    }
}
