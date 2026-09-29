package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.entity.BrideZombie;

import net.minecraft.client.renderer.RenderType;
import net.minecraft.resources.ResourceLocation;
import software.bernie.geckolib.model.GeoModel;

/**
 * 美女僵尸 Phase 2 —— GeckoLib 骨骼模型绑定。
 *
 * <p>Phase 1 的人形网格（{@code BrideModel}）是「原版 HumanoidModel 同构 + 两块胸部补块」，
 * 骨骼是原版那套（head/body/arm/leg），摆姿势只能在整体上拧八个零件。Phase 2 换成真骨骼模型：
 * 35 根骨头（含 4 段手臂链、两瓣独立的胸、发髻/鬓发/面纱/头饰、裙摆左右两片独立摆），
 * 所有动作由 {@code animations/bride_zombie.animation.json} 的 Translation/Rotation 关键帧驱动。</p>
 *
 * <p>贴图是 128×128 双层皮肤：1u = 1px，与原版皮肤同密度；上半区基础层必须不透明，
 * 下半区覆盖层（发/面纱/蕾丝/蝴蝶结）允许 alpha 镂空，靠 {@code entityCutoutNoCull} 出效果。
 * 路径在 {@code textures/entity/bride/}——老的 64×64 那张还被魅惑随侍
 * （{@code CharmedZombieRenderer}）用着，不能覆盖。</p>
 *
 * <p><b>下面这组常量与 {@code tools/bride_v2.py} 双向同步</b>：生成器写完 geo 之后会回来读这几行，
 * 对不上就报 FAIL。改胸部规格必须同时改生成器与这里，否则自校验会拦住。</p>
 */
public class BrideGeoModel extends GeoModel<BrideZombie> {

    // ---------------------------------------------------------------- 坐标常量（单位 u，16u = 1 Block）
    /** 16u = 1 Block：写模型尺寸时统一除它，别在代码里散落魔法数。 */
    public static final float TEXEL = 1.0F / 16.0F;

    /** 躯干正面平面（z，负数是身前）。胸部两瓣就是从这张面往前长的。 */
    public static final float CHEST_FRONT_Z = -2.40F;
    /** 每瓣胸的宽 / 高 / 深。 */
    public static final float BUST_WIDTH = 2.0F;
    public static final float BUST_HEIGHT = 3.0F;
    /** 相对躯干正面的前伸量：只凸出 1u（1px），不是 Phase 1 那版的 2u。 */
    public static final float BUST_PROTRUSION = 1.0F;
    /** 两瓣之间的中缝。 */
    public static final float BUST_GAP = 1.0F;

    /** 模型总高（u）：鞋底 0 → 发髻顶 33.2，约 2.08 格，和原版僵尸的 32u 基本对齐。 */
    public static final float MODEL_HEIGHT = 33.2F;

    // ---------------------------------------------------------------- 资源路径
    private static final ResourceLocation MODEL = resource("geo/bride_zombie.geo.json");
    private static final ResourceLocation TEXTURE = resource("textures/entity/bride/bride_zombie.png");
    private static final ResourceLocation ANIMATION = resource("animations/bride_zombie.animation.json");

    private static ResourceLocation resource(String path) {
        return new ResourceLocation(ApocalypseZombies.MOD_ID, path);
    }

    @Override
    public ResourceLocation getModelResource(BrideZombie animatable) {
        return MODEL;
    }

    @Override
    public ResourceLocation getTextureResource(BrideZombie animatable) {
        return TEXTURE;
    }

    @Override
    public ResourceLocation getAnimationResource(BrideZombie animatable) {
        return ANIMATION;
    }

    /**
     * 贴图里有用 alpha 抠出来的面纱蕾丝（宫格镂空），所以要 cutout 而不是 solid；
     * 同时不剔背面：胸衣、裙摆都是薄板围出来的体块，<b>剔背面会把内壁一起裁掉</b>，
     * 侧面换个角度看就会透出背景。内壁在贴图里已经统一刷了衬里色。
     */
    @Override
    public RenderType getRenderType(BrideZombie animatable, ResourceLocation texture) {
        return RenderType.entityCutoutNoCull(texture);
    }
}