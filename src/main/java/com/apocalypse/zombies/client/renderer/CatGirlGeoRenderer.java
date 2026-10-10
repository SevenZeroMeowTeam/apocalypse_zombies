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

import com.apocalypse.zombies.Config;
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
 * <p>物品的摆放补齐了原版第三人称「手」的那一步基准旋转，见
 * {@link HeldItemLayer#renderStackForBone} —— 缺它的时候物品会按自己的坐标系直立站着，
 * 看起来就是「手上的东西方向不对」。</p>
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
         * <b>先额外转两下</b>再交给物品：<br>
         * {@code mulPose(XP, -90)} → {@code mulPose(YP, 180)} →
         * {@code translate(±1/16, 0.125, -0.625)}（从手臂枢轴挪到手心）。</p>
         *
         * <p>缺少前两步的直接后果：平物品（方块、锭、食物）会<b>立着</b>摆在她手里当一张牌子，
         * 工具（镐 / 斧 / 剑，父模型 {@code item/handheld}）也少一截倾角 —— 这就是「手持物品
         * 方向不对」。所以这里补上这两次旋转，再走原版的 display 变换。</p>
         *
         * <p>第三行的平移<b>故意不加</b>：那是照原版「手臂枢轴在肩」算的 0.625 格位移，而我们的
         * 挂点骨骼 {@code item_righthand} 的 pivot（{@code [2.75, 10.4, 0]}）本来就落在她手心，
         * 再补一段会把手里的东西顶到小臂上去。</p>
         *
         * <p>{@link Config#CAT_GIRL_HELD_ITEM_MIRROR} = true 时改走原版<b>左手</b>那一条
         * （{@code leftHand} 位取反 ry/rz），只翻贴图的左右朝向，倾角与摆位不变。</p>
         */
        @Override
        protected void renderStackForBone(PoseStack poseStack, GeoBone bone, ItemStack stack, CatGirlEntity animatable,
                MultiBufferSource bufferSource, float partialTick, int packedLight, int packedOverlay) {
            boolean mirror = Config.CAT_GIRL_HELD_ITEM_MIRROR.get();
            poseStack.pushPose();
            poseStack.mulPose(Axis.XP.rotationDegrees(-90.0F));
            poseStack.mulPose(Axis.YP.rotationDegrees(180.0F));
            Minecraft.getInstance().getItemRenderer().renderStatic(animatable, stack,
                    mirror ? ItemDisplayContext.THIRD_PERSON_LEFT_HAND : ItemDisplayContext.THIRD_PERSON_RIGHT_HAND,
                    mirror, poseStack, bufferSource, animatable.level(), packedLight, packedOverlay,
                    animatable.getId());
            poseStack.popPose();
        }
    }
}
