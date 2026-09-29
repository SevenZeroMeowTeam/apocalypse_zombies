package com.apocalypse.zombies.client.model;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.entity.SoldierZombie;

import net.minecraft.client.renderer.RenderType;
import net.minecraft.resources.ResourceLocation;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.core.animation.AnimationState;
import software.bernie.geckolib.model.GeoModel;

/**
 * 残兵（军装僵尸士兵）—— GeckoLib 骨骼模型绑定。
 *
 * <p>几何与贴图都由 {@code tools/soldier_v2.py} 生成：24 根骨头 / 61 个体块；
 * 贴图 128×128、1u = 1px（与美女僵尸同规范，16u = 1 Block）。</p>
 *
 * <p><b>贴图是双层皮肤</b>：基础层不透明，血渍那一层靠 alpha 镂空出「污渍而不是红方块」，
 * 所以必须走 {@code entityCutoutNoCull}，不能用不透明管线。</p>
 *
 * <p>两个变种贴图对应参考图里三只兵的不同装具（其中一只背箭袋、一只背工兵铲），
 * 变种号由服务端在生成时随机并同步，见 {@code SoldierZombie#getVariant()}。</p>
 *
 * <p><b>这里没有物品层</b>，是刻意的：怪的主手挂着原版弓 / TNT，只是为了满足原版 AI 的
 * 持物判定；玩家看到的装备是建模进骨骼树的 {@code bow / bow_limb_* / bow_string_*}（弓手）
 * 与 {@code tnt / tnt_fuse}（爆破兵，引信亮芯）。一旦有人"顺手"加上
 * {@code BlockAndItemGeoLayer}，手上会多出一件原版物品穿模。</p>
 *
 * <p><b>两个变种共用同一份几何</b>（唯一出口 {@code tools/soldier_v2.py}），装备差异在
 * {@link #setCustomAnimations} 里按变种显隐 —— 而且必须<b>整支子树</b>一起隐：只藏弓把的话，
 * 挂在它下面的弓弦、引信还会留在原地渲染。</p>
 */
public class SoldierGeoModel extends GeoModel<SoldierZombie> {

    private static final ResourceLocation MODEL =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "geo/soldier_zombie.geo.json");
    private static final ResourceLocation ANIM =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "animations/soldier_zombie.animation.json");

    private static final ResourceLocation TEX_ARCHER =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "textures/entity/soldier/soldier_archer.png");
    private static final ResourceLocation TEX_SAPPER =
            new ResourceLocation(ApocalypseZombies.MOD_ID, "textures/entity/soldier/soldier_sapper.png");

    @Override
    public ResourceLocation getModelResource(SoldierZombie animatable) {
        return MODEL;
    }

    @Override
    public ResourceLocation getTextureResource(SoldierZombie animatable) {
        return animatable.getVariant() == SoldierZombie.VARIANT_SAPPER ? TEX_SAPPER : TEX_ARCHER;
    }

    @Override
    public ResourceLocation getAnimationResource(SoldierZombie animatable) {
        return ANIM;
    }

    @Override
    public RenderType getRenderType(SoldierZombie animatable, ResourceLocation texture) {
        return RenderType.entityCutoutNoCull(texture);
    }

    /** 弓那一支的根骨（弓把 + 上/下梢 + 两段弦都在它下面）。 */
    private static final String ARCHER_GEAR = "bow";
    /** 引信点燃的 TNT 的根骨（引信在它下面）。 */
    private static final String SAPPER_GEAR = "tnt";

    /**
     * 按变种显隐装备骨。
     *
     * <p>走这里而不是给两个变种各出一份 geo：几何只有一个出口（{@code tools/soldier_v2.py}），
     * 两份 geo 会让「模型改一次、两处同步」变成常态；而显隐只在一处发生，改错也看得见。</p>
     *
     * <p>必须递归整支子树：GeckoLib 只管这根骨自己的可见性，藏在它下面的子骨照旧渲染 ——
     * 只隐 {@code bow} 的话，两根弦会留在地上一动不动。</p>
     */
    @Override
    public void setCustomAnimations(SoldierZombie animatable, long instanceId,
                                    AnimationState<SoldierZombie> animationState) {
        super.setCustomAnimations(animatable, instanceId, animationState);
        boolean sapper = animatable.getVariant() == SoldierZombie.VARIANT_SAPPER;
        hideSubtree(ARCHER_GEAR, sapper);
        hideSubtree(SAPPER_GEAR, !sapper);
    }

    private void hideSubtree(String rootBone, boolean hidden) {
        CoreGeoBone bone = this.getAnimationProcessor().getBone(rootBone);
        if (bone != null) {
            setHiddenDeep(bone, hidden);
        }
    }

    private static void setHiddenDeep(CoreGeoBone bone, boolean hidden) {
        bone.setHidden(hidden);
        for (CoreGeoBone child : bone.getChildBones()) {
            setHiddenDeep(child, hidden);
        }
    }
}
