package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.GiantArrow;
import com.mojang.blaze3d.vertex.PoseStack;

import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.entity.ArrowRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;

/**
 * 超大号跟踪箭的渲染：复用原版箭贴图与 {@link ArrowRenderer} 的全部几何，只改一处缩放。
 *
 * <p>缩放必须<b>绕正确的原点</b>做。原版箭的模型头端在实体坐标前方
 * {@value #TIP_AHEAD} 格（{@code ArrowRenderer} 里 {@code translate(-4,0,0)} 之后头部顶点在局部 x=-12，
 * 再乘它自己的 0.05625 缩放），所以直接 {@code scale(s)} 会把<b>箭尖推到落点前面</b>
 * {@code (s-1)×0.675} 格 —— 命中判定发生在实体位置，画面上的箭尖却已经穿进墙里或穿过怪。
 * 因此在缩放之前先沿视线方向回退同样的距离：箭尖钉在原处，多出来的长度全部长在箭尾。</p>
 *
 * <p>贴图借用原版 {@code arrow.png}，与「怪物子弹借铁粒贴图」同一做法：不新增美术资产。</p>
 */
public class GiantArrowRenderer extends ArrowRenderer<GiantArrow> {

    /** 原版箭模型的头端到实体位置的距离（格）：12 × 0.05625。 */
    private static final double TIP_AHEAD = 0.675D;

    private static final ResourceLocation ARROW_TEXTURE =
            new ResourceLocation("minecraft", "textures/entity/projectiles/arrow.png");

    public GiantArrowRenderer(EntityRendererProvider.Context context) {
        super(context);
    }

    @Override
    public ResourceLocation getTextureLocation(GiantArrow arrow) {
        return ARROW_TEXTURE;
    }

    @Override
    public void render(GiantArrow arrow, float yaw, float partialTick, PoseStack pose,
                       MultiBufferSource buffer, int packedLight) {
        float scale = Config.AI_GIANT_ARROW_SCALE.get().floatValue();
        if (scale <= 1.001F) {
            super.render(arrow, yaw, partialTick, pose, buffer, packedLight);
            return;
        }
        Vec3 look = Vec3.directionFromRotation(arrow.getXRot(), arrow.getYRot());
        double back = (1.0D - scale) * TIP_AHEAD;
        pose.pushPose();
        pose.translate(look.x * back, look.y * back, look.z * back);
        pose.scale(scale, scale, scale);
        super.render(arrow, yaw, partialTick, pose, buffer, packedLight);
        pose.popPose();
    }
}
