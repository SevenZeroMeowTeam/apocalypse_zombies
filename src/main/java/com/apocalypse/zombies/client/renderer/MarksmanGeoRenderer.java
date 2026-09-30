package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.client.model.MarksmanGeoModel;
import com.apocalypse.zombies.entity.MarksmanSkeleton;

import net.minecraft.client.renderer.entity.EntityRendererProvider;
import software.bernie.geckolib.renderer.GeoEntityRenderer;

/**
 * 骸骨射手渲染器：GeckoLib 骨骼模型直接上，不做任何模型缩放。
 *
 * <p>体型是几何决定的（模型 32u = 2.0 格，与 {@code ModEntities.MARKSMAN} 的命中箱一致），
 * 不是靠 {@code scale} 撑出来的 —— 那正是本项目禁止的假动画来源。</p>
 *
 * <p><b>不要加物品层</b>：主手的原版弓只给 AI 判定用，可见的弓是骨骼树里的 {@code bow}。</p>
 *
 * <p>影子半径 0.5：两格高的瘦骨架配更大的影子会看着像浮在地上
 * （同 {@code SoldierGeoRenderer}）。</p>
 */
public class MarksmanGeoRenderer extends GeoEntityRenderer<MarksmanSkeleton> {

    public MarksmanGeoRenderer(EntityRendererProvider.Context context) {
        super(context, new MarksmanGeoModel());
        this.shadowRadius = 0.5F;
    }
}
