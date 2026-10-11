package com.apocalypse.zombies.client.renderer;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;

import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
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
 * <p>物品的摆放见 {@link HeldItemLayer#renderStackForBone} —— 她那套模型空间与原版实体不是同一个
 * 坐标系（她的 geo 按原版「翻转之后」的空间画的），该转几次、往哪转，推导都写在那一个方法上。</p>
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

        /**
         * 画她手里的东西。
         *
         * <p><b>为什么要自己写这一遍</b>：GeckoLib 的 {@code BlockAndItemGeoLayer} 对物品只做
         * 「平移到骨骼 pivot + 骨骼自身旋转」，然后就调 {@code ItemRenderer.renderStatic}；
         * 而原版实体拿东西走的是 {@code ItemInHandLayer.renderArmWithItem} —— 它在骨骼变换之后
         * 还要先补一次基准旋转才交给物品。</p>
         *
         * <p><b>补哪一次、为什么只剩半截</b>：原版那一步是
         * {@code mulPose(XP,-90)} → {@code mulPose(YP,180)} → {@code translate(±1/16, 0.125, -0.625)}，
         * 可它是写给<b>翻转前</b>那个模型空间的 —— 原版实体渲染器在模型之外还压了一次
         * {@code scale(-1,-1,1)}（把模型里「Y 向下」翻成世界向上，顺带把模型 +X 映射到世界 -X）。
         * 她的 geo 是按<b>翻转之后</b>那个空间画的（{@code right_arm} 在 +X、头在 +Y 上方、刘海在 -Z、
         * 尾巴在 +Z），GeckoLib 又不像原版那样补那次翻转 —— 于是她的模型空间本身就是原版的
         * <b>已翻转空间</b>。记 F = {@code scale(-1,-1,1)} 代进去算：</p>
         *
         * <pre>F · XP(-90) · YP(180) ≡ XP(-90)   ← 物品的上 / 面 / 右三根基向量逐个验过</pre>
         *
         * <p>所以她这里<b>只需要 XP -90 这一次</b>。多补那个 YP 180 等于给手里的东西又套了一层 F：
         * 物品的「面」从朝上翻成朝下、自身右轴从她的右翻到她的左 —— 看起来就是「倒着的、跟玩家拿反了」，
         * 斧刃朝里也是同一条因。1.1.90 修掉的就是这个（1.1.80 那次多加了）。</p>
         *
         * <p>第三行的平移照旧不加：那是照原版「手臂枢轴在肩」算的 0.625 格位移，而我们的挂点骨骼
         * {@code item_righthand} 的 pivot 本来就落在她手心，再补一段会把东西顶到小臂上去。</p>
         */
        @Override
        protected void renderStackForBone(PoseStack poseStack, GeoBone bone, ItemStack stack, CatGirlEntity animatable,
                MultiBufferSource bufferSource, float partialTick, int packedLight, int packedOverlay) {
            poseStack.pushPose();
            poseStack.mulPose(Axis.XP.rotationDegrees(-90.0F));
            Minecraft.getInstance().getItemRenderer().renderStatic(animatable, stack,
                    ItemDisplayContext.THIRD_PERSON_RIGHT_HAND, false, poseStack, bufferSource,
                    animatable.level(), packedLight, packedOverlay, animatable.getId());
            poseStack.popPose();
        }
    }
}
