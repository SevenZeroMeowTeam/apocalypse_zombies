package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.client.model.BrideGeoModel;
import com.apocalypse.zombies.entity.BrideZombie;

import net.minecraft.client.renderer.entity.EntityRendererProvider;
import software.bernie.geckolib.renderer.GeoEntityRenderer;

/**
 * 美女僵尸 Phase 2 渲染器：把人形模型（{@code BrideRenderer}）换成 GeckoLib 骨骼模型。
 *
 * <p>跟 {@link EliteMobRenderer} 的区别只在继承链：GeckoLib 的 {@code GeoEntityRenderer}
 * 直接继承 {@code EntityRenderer}（不走 {@code LivingEntityRenderer}），
 * 动画、姿态、贴图全部由 {@link BrideGeoModel} + 动画 JSON 提供，
 * 所以模型缩放必须保持 1.0——精英怪的「越大越强」是僵尸进化 tier 的表现，不是这里该做的事。</p>
 *
 * <p>影子半径沿用 Phase 1 的 0.5，和别的精英保持一致的落地感。</p>
 */
public class BrideGeoRenderer extends GeoEntityRenderer<BrideZombie> {

    public BrideGeoRenderer(EntityRendererProvider.Context context) {
        super(context, new BrideGeoModel());
        this.shadowRadius = 0.5F;
    }
}