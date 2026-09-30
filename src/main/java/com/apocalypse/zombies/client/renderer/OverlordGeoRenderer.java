package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.client.model.OverlordGeoModel;
import com.apocalypse.zombies.entity.HordeOverlord;

import net.minecraft.client.renderer.entity.EntityRendererProvider;
import software.bernie.geckolib.renderer.GeoEntityRenderer;

/**
 * 尸潮之主渲染器：GeckoLib 骨骼模型直接上，不做任何模型缩放。
 *
 * <p>它的体型是几何决定的（模型 3.04 格高，命中箱同步到 3.1 格），
 * 不是靠 {@code scale} 撑出来的 —— 那正是本项目禁止的假动画来源。</p>
 *
 * <p>影子半径给 1.0：三格高的怪配 0.5 的影子看着像浮在地上。</p>
 */
public class OverlordGeoRenderer extends GeoEntityRenderer<HordeOverlord> {

    public OverlordGeoRenderer(EntityRendererProvider.Context context) {
        super(context, new OverlordGeoModel());
        this.shadowRadius = 1.0F;
    }
}
