package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.entity.CharmedZombie;

import net.minecraft.client.model.HumanoidModel;
import net.minecraft.client.model.ZombieModel;
import net.minecraft.client.model.geom.ModelLayerLocation;
import net.minecraft.client.model.geom.builders.CubeDeformation;
import net.minecraft.client.model.geom.builders.LayerDefinition;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.client.renderer.entity.MobRenderer;
import net.minecraft.client.renderer.entity.layers.ItemInHandLayer;
import net.minecraft.resources.ResourceLocation;

/**
 * 魅惑召奬的渲染器：网格直接用原版僵尸的，只按 {@link CharmedZombie.Variant} 换贴图。
 *
 * <p>共用原版 {@code ModelLayers.ZOMBIE} 会有多个模型抢同一个 {@code ModelPart} 的问题，
 * 所以这里注册自己的层，网格定义仍与 {@code ModelLayers.ZOMBIE} 完全一致。</p>
 *
 * <p>选妃 / 幽灵两种召奬借用美女僵尸自己的贴图（她召出来的东西长得像她），
 * 被策反来的普通召奬用原版僵尸贴图——玩家一眼就能分清「原本就在场上的那只」和「她带来的那几只」。</p>
 */
public class CharmedZombieRenderer extends MobRenderer<CharmedZombie, ZombieModel<CharmedZombie>> {

    public static final ModelLayerLocation LAYER = new ModelLayerLocation(
            new ResourceLocation(ApocalypseZombies.MOD_ID, "charmed_zombie"), "main");

    private static final ResourceLocation VANILLA_ZOMBIE = new ResourceLocation(
            "minecraft", "textures/entity/zombie/zombie.png");
    private static final ResourceLocation BRIDE_TEXTURE = new ResourceLocation(
            ApocalypseZombies.MOD_ID, "textures/entity/bride_zombie.png");

    public CharmedZombieRenderer(EntityRendererProvider.Context context) {
        super(context, new ZombieModel<>(context.bakeLayer(LAYER)), 0.5F);
        // 原版 ZombieRenderer 自带这一层，我们是自己 bake 的网格所以必须显式加回来：
        // 少了它，召奬手里那把枪**在客户端根本不会被画出来**（服务端数据是全的，
        // 只是纯视觉缺失 —— 排查起来会以为是没发装备）。
        this.addLayer(new ItemInHandLayer<>(this, context.getItemInHandRenderer()));
    }

    /** 和 {@code ModelLayers.ZOMBIE} 同构的人形网格（64×64）。 */
    public static LayerDefinition createBodyLayer() {
        return LayerDefinition.create(HumanoidModel.createMesh(CubeDeformation.NONE, 0.0F), 64, 64);
    }

    @Override
    public ResourceLocation getTextureLocation(CharmedZombie entity) {
        return entity.getVariant() == CharmedZombie.Variant.CHARMED ? VANILLA_ZOMBIE : BRIDE_TEXTURE;
    }
}