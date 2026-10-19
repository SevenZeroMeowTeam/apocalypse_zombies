package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.client.model.OrbitSatelliteGeoModel;
import com.apocalypse.zombies.entity.OrbitSatellite;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import software.bernie.geckolib.renderer.GeoEntityRenderer;

/**
 * 轨道卫星渲染器：GeckoLib 骨骼模型，静态展示（无动画）。
 *
 * <p>命中箱 4×4×4 格（模型 14 格长，允许略微出头），shadow 关闭 —— 太空里没有地面接影子。</p>
 */
public class OrbitSatelliteRenderer extends GeoEntityRenderer<OrbitSatellite> {

    public OrbitSatelliteRenderer(EntityRendererProvider.Context context) {
        super(context, new OrbitSatelliteGeoModel());
        this.shadowRadius = 0.0F;
    }
}
