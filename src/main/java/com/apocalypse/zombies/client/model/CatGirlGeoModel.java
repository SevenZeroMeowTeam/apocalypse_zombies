package com.apocalypse.zombies.client.model;

import net.minecraft.resources.ResourceLocation;
import net.minecraft.client.renderer.RenderType;

import software.bernie.geckolib.model.GeoModel;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.entity.CatGirlEntity;

/**
 * 猫耳娘的 GeckoLib 模型入口：几何 / 贴图 / 动画三份资源。
 *
 * <p>贴图走 {@code entityCutoutNoCull}：刘海、缎带、裙褶都是薄片方块，
 * 不透明管线会把它们之间的缝填实；剔除背面则会从裙褶内侧看穿。</p>
 */
public class CatGirlGeoModel extends GeoModel<CatGirlEntity> {

    private static final ResourceLocation MODEL = resource("geo/cat_girl.geo.json");
    private static final ResourceLocation TEXTURE = resource("textures/entity/cat_girl.png");
    private static final ResourceLocation ANIMATION = resource("animations/cat_girl.animation.json");

    private static ResourceLocation resource(String path) {
        return new ResourceLocation(ApocalypseZombies.MOD_ID, path);
    }

    @Override
    public ResourceLocation getModelResource(CatGirlEntity animatable) {
        return MODEL;
    }

    @Override
    public ResourceLocation getTextureResource(CatGirlEntity animatable) {
        return TEXTURE;
    }

    @Override
    public ResourceLocation getAnimationResource(CatGirlEntity animatable) {
        return ANIMATION;
    }

    @Override
    public RenderType getRenderType(CatGirlEntity animatable, ResourceLocation texture) {
        return RenderType.entityCutoutNoCull(texture);
    }
}
