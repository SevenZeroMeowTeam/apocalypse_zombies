package com.apocalypse.zombies.client.renderer;

import com.mojang.blaze3d.vertex.PoseStack;

import net.minecraft.client.model.HumanoidModel;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.client.renderer.entity.HumanoidMobRenderer;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.entity.Mob;

/**
 * 精英怪渲染器的公共骨架：一张固定贴图 + 可选的模型缩放。
 *
 * <p>{@link HumanoidMobRenderer} 已经带好了手持物层、头部自定义层和鞘翅层，
 * 所以拿弓的骸骨射手不用额外加层就能把弓显示出来。</p>
 *
 * <p>模型缩放只用来让碰撞箱和视觉对得上（碎颅者的碰撞箱比原版僵尸大一圈），
 * 不拿它做「越大越强」的表现——那是僵尸进化 tier 那套干的事。</p>
 */
public abstract class EliteMobRenderer<T extends Mob, M extends HumanoidModel<T>>
        extends HumanoidMobRenderer<T, M> {

    private final ResourceLocation texture;
    private final float modelScale;

    protected EliteMobRenderer(EntityRendererProvider.Context context, M model, ResourceLocation texture,
                               float shadowRadius, float modelScale) {
        super(context, model, shadowRadius);
        this.texture = texture;
        this.modelScale = modelScale;
    }

    @Override
    public ResourceLocation getTextureLocation(T entity) {
        return this.texture;
    }

    @Override
    protected void scale(T entity, PoseStack pose, float partialTick) {
        if (this.modelScale != 1.0F) {
            pose.scale(this.modelScale, this.modelScale, this.modelScale);
        }
    }
}
