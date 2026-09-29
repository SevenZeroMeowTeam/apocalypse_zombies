package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.client.model.SoldierGeoModel;
import com.apocalypse.zombies.entity.SoldierZombie;

import net.minecraft.client.renderer.entity.EntityRendererProvider;
import software.bernie.geckolib.renderer.GeoEntityRenderer;

/**
 * 残兵渲染器：GeckoLib 骨骼模型，走 {@code GeoEntityRenderer}（直接继承 {@code EntityRenderer}，
 * 不经过 {@code LivingEntityRenderer}）。
 *
 * <p><b>不要加物品层</b>：这只怪的主手确实拿着原版弓，但那是给原版 AI 判定用的，
 * 可见的弓是骨骼树里的 {@code bow} 分支。加了 {@code BlockAndItemGeoLayer} 就会同时出现两把弓。</p>
 *
 * <p>命中盒由 {@code ModEntities.SOLDIER} 按原版僵尸尺度注册（0.6 × 2.0），
 * 模型本体 33.6u（2.10 格）会略微出头，和美女僵尸同样处理，不改命中盒手感。</p>
 */
public class SoldierGeoRenderer extends GeoEntityRenderer<SoldierZombie> {

    public SoldierGeoRenderer(EntityRendererProvider.Context context) {
        super(context, new SoldierGeoModel());
        this.shadowRadius = 0.5F;
    }
}
