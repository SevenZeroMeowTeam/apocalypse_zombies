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
 * <p>物品的摆放见 {@link HeldItemLayer#renderStackForBone} —— 那里记着「该转哪两下」
 * 以及为什么这两下<b>不能</b>照着矩阵推导去删。</p>
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
         * 画她手里的东西：<b>{@code XP(+90)} → {@code YP(180)}，两下都要</b>。
         *
         * <p><b>为什么要自己写这一遍</b>：GeckoLib 的 {@code BlockAndItemGeoLayer} 对物品只做
         * 「平移到骨骼 pivot + 骨骼自身旋转」，然后就调 {@code ItemRenderer.renderStatic}；
         * 而原版实体拿东西走的是 {@code ItemInHandLayer.renderArmWithItem} —— 它在骨骼变换之后
         * 还要补一次基准旋转才交给物品。</p>
         *
         * <p><b>原版那一步（从官方映射 jar 的字节码读出，不是照抄记忆）</b>：</p>
         * <pre>translateToHand(arm) → mulPose(XP, -90°) → mulPose(YP, 180°)
         *   → translate(右臂 +1/16, 0.125, -0.625) → ItemInHandRenderer.renderItem(...)</pre>
         * <p>再往外还有 {@code setupRotations} → {@code scale(-1,-1,1)} → {@code translate(0,-1.501,0)}。
         * 第三行的位移不加：那是照原版「手臂枢轴在肩」算的 0.625 格位移，而我们的挂点骨骼
         * {@code item_righthand} 的 pivot 本来就落在她手心，再补一段会把东西顶到小臂上去。</p>
         *
         * <p><b>为什么是这两下、而不是推导出来的那两下</b>：她的链是 GeckoLib 的
         * {@code applyRotations(180 - bodyRot)} → 骨骼树，<b>没有</b>原版那次 {@code scale(-1,-1,1)}；
         * 记 {@code F = scale(-1,-1,1)}，把她的手部帧写成 {@code F·A_m·F⁻¹} 代进去，纸面上得到的
         * 唯一解是 {@code F·XP(-90)·YP(180) ≡ XP(-90)}（这个恒等式本身没错，验过三遍）。
         * <b>可实机那样摆是上下颠倒的。</b>2026-10-13 在游戏里逐档比对（K 键四档实时切换），
         * 与玩家手里一致的答案是 <b>{@code XP(+90)+YP(180)}</b>，而它恰好等于：</p>
         * <pre>XP(+90)·YP(180) ≡ Ry(180)·XP(-90)</pre>
         * <p>也就是说：她的空间相对「原版模型空间 + F」<b>还差一个绕 Y 的 180°</b>
         * （等价于她的 geo 与我代入的那套差一个 {@code Rx(180)}：X 同号、Y 与 Z 都反）。
         * 这层差异在纸面上没被抓到 —— GeckoLib 在层里又施加了一次骨骼变换
         * （{@code prepMatrixForBone} 之后 {@code translateAndRotateMatrixForBone}）、
         * 以及它不做原版那次翻转，这两件事叠加起来的净效果与朴素推导不等价。</p>
         *
         * <p><b>教训（1.1.90 就是这么改错的）</b>：{@code YP(180)} 这一下是<b>实测需要</b>的，
         * 别因为「矩阵恒等式能把它化掉」就把它删了 —— 恒等式描述的是模型空间，而她不在那个空间里。
         * 要再动这两行，请先把 K 键那套比对重做一遍。</p>
         */
        @Override
        protected void renderStackForBone(PoseStack poseStack, GeoBone bone, ItemStack stack, CatGirlEntity animatable,
                MultiBufferSource bufferSource, float partialTick, int packedLight, int packedOverlay) {
            poseStack.pushPose();
            poseStack.mulPose(Axis.XP.rotationDegrees(90.0F));
            poseStack.mulPose(Axis.YP.rotationDegrees(180.0F));
            Minecraft.getInstance().getItemRenderer().renderStatic(animatable, stack,
                    ItemDisplayContext.THIRD_PERSON_RIGHT_HAND, false, poseStack, bufferSource,
                    animatable.level(), packedLight, packedOverlay, animatable.getId());
            poseStack.popPose();
        }
    }
}
