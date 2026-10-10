package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.CatGirlEntity;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import net.minecraft.client.Minecraft;
import net.minecraft.client.model.HumanoidModel;
import net.minecraft.client.model.geom.EntityModelSet;
import net.minecraft.client.model.geom.ModelLayers;
import net.minecraft.client.model.geom.ModelPart;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.item.ArmorItem;
import net.minecraft.world.item.ItemStack;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;
import software.bernie.geckolib.model.GeoModel;
import software.bernie.geckolib.renderer.GeoRenderer;
import software.bernie.geckolib.renderer.layer.GeoRenderLayer;
import software.bernie.geckolib.util.RenderUtils;

/**
 * 让她的甲**看得见**：把原版盔甲网格（{@code HumanoidModel} 的 layer_1 / layer_2）贴到她的骨骼上。
 *
 * <p>GeckoLib 自带的 {@code GeoArmorRenderer} 只认 {@code GeoArmorItem}（自己注册的几何盔甲），
 * 对原版/模组盔甲物品是无效的 —— 而她的甲是任意盔甲，所以这里自己写一层：
 * 按骨骼名找到要挂的位置（head / body / left_arm / …），把原版网格按她的块体尺寸缩放后画上去。</p>
 *
 * <p><b>摆放规则</b>：原版盔甲网格和她的模型用的是同一套坐标系（1 单位 = 1/16 格、脚底 y=0、Y 向上），
 * 所以只要把网格在每根轴上的区间「贴合」到骨骼的包围盒区间即可 —— 缩放 s、平移 t 由
 * {@code t = (她的低端 − 原版低端 × s) / 16} 算出，避免逐件手调魔数。</p>
 *
 * <p>骨骼变换用 GeckoLib 自己的 {@link RenderUtils#prepMatrixForBone}，所以她的走路/甩尾动画
 * 会带着盔甲一起动。</p>
 */
public class CatGirlArmorLayer extends GeoRenderLayer<CatGirlEntity> {

    /** 一件盔甲 = 原版网格上的哪个部件 + 挂到哪根骨骼 + 原版区间 → 她的区间（单位：1/16 格）。 */
    private record Piece(ModelPart part, String bone, float[] vanilla, float[] her) {
    }

    private HumanoidModel<CatGirlEntity> inner;
    private HumanoidModel<CatGirlEntity> outer;

    public CatGirlArmorLayer(GeoRenderer<CatGirlEntity> renderer) {
        super(renderer);
    }

    /** 原版模型的延迟烘焙：挂层时实体模型集可能还没准备好。 */
    private void ensureModels() {
        if (this.inner != null) {
            return;
        }
        EntityModelSet models = Minecraft.getInstance().getEntityModels();
        this.inner = new HumanoidModel<>(models.bakeLayer(ModelLayers.PLAYER_INNER_ARMOR));
        this.outer = new HumanoidModel<>(models.bakeLayer(ModelLayers.PLAYER_OUTER_ARMOR));
    }

    // 原版盔甲网格的区间（x / y / z 各 [低, 高]，1/16 格；脚底 y=0）
    private static final float[] V_HEAD = {-4F, 4F, 24F, 32F, -4F, 4F};
    private static final float[] V_BODY = {-4F, 4F, 12F, 24F, -2F, 2F};
    private static final float[] V_ARM_R = {-8F, -4F, 12F, 24F, -2F, 2F};
    private static final float[] V_ARM_L = {4F, 8F, 12F, 24F, -2F, 2F};
    private static final float[] V_LEG_R = {-4F, 0F, 0F, 12F, -2F, 2F};
    private static final float[] V_LEG_L = {0F, 4F, 0F, 12F, -2F, 2F};

    // 她模型的对应区间（取自 cat_girl.geo.json 的骨骼包围盒）
    private static final float[] H_HEAD = {-3.0F, 3.0F, 23.3F, 30.2F, -2.8F, 2.8F};
    private static final float[] H_BODY = {-3.5F, 3.5F, 14.4F, 24.1F, -2.2F, 1.9F};
    private static final float[] H_ARM_R = {1.9F, 5.2F, 16.0F, 23.0F, -1.4F, 1.6F};
    private static final float[] H_ARM_L = {-5.2F, -1.9F, 16.0F, 23.0F, -1.4F, 1.6F};
    private static final float[] H_LEG_R = {-0.1F, 2.4F, 1.4F, 14.0F, -1.3F, 1.3F};
    private static final float[] H_LEG_L = {-2.4F, -0.1F, 1.4F, 14.0F, -1.3F, 1.3F};
    private static final float[] H_FOOT_R = {0.0F, 2.2F, 0.0F, 2.4F, -2.4F, 1.7F};
    private static final float[] H_FOOT_L = {-2.2F, 0.0F, 0.0F, 2.4F, -2.4F, 1.7F};

    @Override
    public void render(PoseStack poseStack, CatGirlEntity animatable, BakedGeoModel model, RenderType renderType,
                       MultiBufferSource bufferSource, VertexConsumer buffer, float partialTick,
                       int packedLight, int packedOverlay) {
        if (!Config.CAT_GIRL_ARMOR_RENDER.get()) {
            return;
        }
        this.ensureModels();
        GeoModel<CatGirlEntity> geoModel = this.getGeoModel();

        for (EquipmentSlot slot : new EquipmentSlot[]{
                EquipmentSlot.HEAD, EquipmentSlot.CHEST, EquipmentSlot.LEGS, EquipmentSlot.FEET}) {
            ItemStack stack = animatable.getItemBySlot(slot);
            if (!(stack.getItem() instanceof ArmorItem armor) || armor.getEquipmentSlot() != slot) {
                continue;
            }
            boolean leggings = slot == EquipmentSlot.LEGS;
            HumanoidModel<CatGirlEntity> armorModel = leggings ? this.inner : this.outer;
            ResourceLocation texture = new ResourceLocation(
                    "textures/models/armor/" + armor.getMaterial().getName()
                            + "_layer_" + (leggings ? 1 : 2) + ".png");
            VertexConsumer consumer = bufferSource.getBuffer(RenderType.armorCutoutNoCull(texture));

            for (Piece piece : piecesFor(slot, armorModel)) {
                GeoBone bone = geoModel.getBone(piece.bone()).orElse(null);
                if (bone == null) {
                    continue;
                }
                poseStack.pushPose();
                RenderUtils.prepMatrixForBone(poseStack, bone);
                fit(poseStack, piece.vanilla(), piece.her());
                piece.part().render(poseStack, consumer, packedLight, OverlayTexture.NO_OVERLAY, 1F, 1F, 1F, 1F);
                poseStack.popPose();
            }
        }
    }

    private Piece[] piecesFor(EquipmentSlot slot, HumanoidModel<CatGirlEntity> armorModel) {
        return switch (slot) {
            case HEAD -> new Piece[]{
                    new Piece(armorModel.head, "head", V_HEAD, H_HEAD)};
            case CHEST -> new Piece[]{
                    new Piece(armorModel.body, "body", V_BODY, H_BODY),
                    new Piece(armorModel.rightArm, "right_arm", V_ARM_R, H_ARM_R),
                    new Piece(armorModel.leftArm, "left_arm", V_ARM_L, H_ARM_L)};
            case LEGS -> new Piece[]{
                    new Piece(armorModel.body, "body", V_BODY, H_BODY),
                    new Piece(armorModel.rightLeg, "right_leg", V_LEG_R, H_LEG_R),
                    new Piece(armorModel.leftLeg, "left_leg", V_LEG_L, H_LEG_L)};
            case FEET -> new Piece[]{
                    new Piece(armorModel.rightLeg, "right_foot", V_LEG_R, H_FOOT_R),
                    new Piece(armorModel.leftLeg, "left_foot", V_LEG_L, H_FOOT_L)};
            default -> new Piece[0];
        };
    }

    /**
     * 把原版网格的区间贴合到她的区间：每根轴先平移再缩放（几何点 p → s·p + t）。
     * 网格顶点已经在「格」单位上（烘焙时除过 16），所以平移量要 /16。
     */
    private static void fit(PoseStack poseStack, float[] vanilla, float[] her) {
        float sx = span(her, 0) / span(vanilla, 0);
        float sy = span(her, 1) / span(vanilla, 1);
        float sz = span(her, 2) / span(vanilla, 2);
        float tx = (her[0] - vanilla[0] * sx) / 16F;
        float ty = (her[2] - vanilla[2] * sy) / 16F;
        float tz = (her[4] - vanilla[4] * sz) / 16F;
        poseStack.translate(tx, ty, tz);
        poseStack.scale(sx, sy, sz);
    }

    private static float span(float[] box, int axis) {
        return box[axis * 2 + 1] - box[axis * 2];
    }
}
