package com.apocalypse.zombies.client.renderer;

import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.world.item.ItemDisplayContext;
import net.minecraft.world.item.ItemStack;

import software.bernie.geckolib.cache.object.GeoBone;
import software.bernie.geckolib.renderer.GeoEntityRenderer;
import software.bernie.geckolib.renderer.GeoRenderer;
import software.bernie.geckolib.renderer.layer.BlockAndItemGeoLayer;

import com.apocalypse.zombies.client.model.CatGirlGeoModel;
import com.apocalypse.zombies.entity.CatGirlEntity;

/**
 * 猫耳娘的渲染器。
 *
 * <p><b>与美女僵尸 / 残兵不同，这只带物品层</b>：她的武器与工具是玩家交给她的真实
 * 物品（存在主手槽里），不是画进骨骼树里的固定模型，所以必须用
 * {@link BlockAndItemGeoLayer} 把 {@code entity.getMainHandItem()} 挂到
 * 骨骼 {@code item_righthand} 上。</p>
 *
 * <p>显示上下文用 {@code THIRD_PERSON_RIGHT_HAND}：这样物品会套用「被人握在手里」
 * 的那套变换（缩放、旋转、握持点），剑和镐看起来才是握着而不是插在手上。</p>
 */
public class CatGirlGeoRenderer extends GeoEntityRenderer<CatGirlEntity> {

    /** 手上的挂点骨骼名（geo 里的空骨骼，只用来定位）。 */
    public static final String ITEM_BONE = "item_righthand";

    public CatGirlGeoRenderer(EntityRendererProvider.Context context) {
        super(context, new CatGirlGeoModel());
        this.shadowRadius = 0.45F;
        this.addRenderLayer(new HeldItemLayer(this));
        this.addRenderLayer(new CatGirlArmorLayer(this));
    }

    /** 只认主手物品 + 挂点骨骼的物品层。 */
    private static final class HeldItemLayer extends BlockAndItemGeoLayer<CatGirlEntity> {

        private HeldItemLayer(GeoRenderer<CatGirlEntity> renderer) {
            super(renderer,
                    (bone, animatable) -> ITEM_BONE.equals(bone.getName()) && !animatable.getMainHandItem().isEmpty()
                            ? animatable.getMainHandItem()
                            : null,
                    (bone, animatable) -> null);
        }

        @Override
        protected ItemDisplayContext getTransformTypeForStack(GeoBone bone, ItemStack stack, CatGirlEntity animatable) {
            return ItemDisplayContext.THIRD_PERSON_RIGHT_HAND;
        }
    }
}
