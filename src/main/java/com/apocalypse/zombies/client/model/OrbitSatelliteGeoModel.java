package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.entity.OrbitSatellite;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.resources.ResourceLocation;
import software.bernie.geckolib.model.GeoModel;

/**
 * 轨道卫星模型绑定：geo 与贴图由 {@code tools/facility_model.py} 生成（唯一真相源）。
 *
 * <p>贴图 512²、逐面 UV；青/橙区域是图集里的自发光笔法，走
 * {@code entityTranslucentEmissive} 让它们在暗处也亮。</p>
 */
public class OrbitSatelliteGeoModel extends GeoModel<OrbitSatellite> {

    private static final ResourceLocation MODEL =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "geo/satellite.geo.json");
    private static final ResourceLocation TEX =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "textures/entity/facility/satellite.png");
    private static final ResourceLocation ANIM =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "animations/satellite.animation.json");

    @Override
    public ResourceLocation getModelResource(OrbitSatellite animatable) {
        return MODEL;
    }

    @Override
    public ResourceLocation getTextureResource(OrbitSatellite animatable) {
        return TEX;
    }

    @Override
    public ResourceLocation getAnimationResource(OrbitSatellite animatable) {
        return ANIM;
    }

    @Override
    public RenderType getRenderType(OrbitSatellite animatable, ResourceLocation texture) {
        // 金色/青色/橙色区域在图集里带 alpha 边界，走 cutout 避免发灰
        return RenderType.entityCutout(TEX);
    }
}
