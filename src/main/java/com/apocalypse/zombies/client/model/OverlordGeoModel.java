package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.entity.HordeOverlord;

import net.minecraft.client.renderer.RenderType;
import net.minecraft.resources.ResourceLocation;
import software.bernie.geckolib.model.GeoModel;

/**
 * 尸潮之主 —— GeckoLib 骨骼模型绑定。
 *
 * <p>45 根骨头：三段躯干环、头颅（含可开合的下颚、骨冠、双角）、两段手臂链 + 爪、
 * 背后尸笼（两条会转的箍 + 笼中魂火）、三段披风链 + 左右翼、双腿骨链，
 * 以及挂在右手上的巨斧骨 {@code axe} —— 挥砍是真实骨骼变换，不是整体旋转。</p>
 *
 * <p>全部动作由 {@code animations/horde_overlord.animation.json} 的 Rotation/Position 关键帧驱动，
 * <b>没有任何 scale 通道</b>：整体缩放式假动画在本项目是禁止项，生成器的自校验会逐个通道验。</p>
 *
 * <p><b>下面这组常量与 {@code tools/boss_v1.py} 双向同步</b>：生成器写完 geo/anim 之后会回来读这几行，
 * 对不上就报 FAIL。改模型规格必须同时改生成器与这里。</p>
 */
public class OverlordGeoModel extends GeoModel<HordeOverlord> {

    // ---------------------------------------------------------------- 坐标常量（单位 u，16u = 1 Block）

    /** 16u = 1 Block：写模型尺寸时统一除它，别在代码里散落魔法数。 */
    public static final float TEXEL = 1.0F / 16.0F;

    /** 模型总高（u）：脚底 0 → 骨冠/角顶 48.6，约 3.04 格（普通僵尸 1.95 格）。 */
    public static final float MODEL_HEIGHT = 48.6F;

    /** 躯干正面平面（z，负数是身前）—— 胸甲分片就是从这张面往前长的。 */
    public static final float CHEST_FRONT_Z = -3.90F;

    /** 双肩枢轴（x）：巨斧与爪的位置都从这对数推。 */
    public static final float SHOULDER_X = 5.20F;

    /** 贴图规格：512×512，逐面 UV 图集，躯干 2px/u、脸 4px/u。 */
    public static final int TEXTURE_SIZE = 512;

    // ---------------------------------------------------------------- 资源路径
    private static final ResourceLocation MODEL = resource("geo/horde_overlord.geo.json");
    private static final ResourceLocation TEXTURE = resource("textures/entity/horde_overlord.png");
    private static final ResourceLocation ANIMATION = resource("animations/horde_overlord.animation.json");

    private static ResourceLocation resource(String path) {
        return new ResourceLocation(ApocalypseZombies.MOD_ID, path);
    }

    @Override
    public ResourceLocation getModelResource(HordeOverlord animatable) {
        return MODEL;
    }

    @Override
    public ResourceLocation getTextureResource(HordeOverlord animatable) {
        return TEXTURE;
    }

    @Override
    public ResourceLocation getAnimationResource(HordeOverlord animatable) {
        return ANIMATION;
    }

    /**
     * 模型是薄板围出来的体块（躯干环、披风、尸笼骨条），<b>剔背面会把内壁一起裁掉</b>，
     * 换个角度就会透出背景。内壁在贴图里已经统一刷了衬里色，所以走 {@code entityCutoutNoCull}。
     */
    @Override
    public RenderType getRenderType(HordeOverlord animatable, ResourceLocation texture) {
        return RenderType.entityCutoutNoCull(texture);
    }
}
