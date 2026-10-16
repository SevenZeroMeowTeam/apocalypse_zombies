package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.client.model.Win94GeoModel;
import com.apocalypse.zombies.item.Win94Item;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.world.item.ItemDisplayContext;
import net.minecraft.world.item.ItemStack;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.renderer.GeoItemRenderer;

/**
 * Draws the 温彻斯特 M1894 from its GeckoLib model, in every context it can appear (hand, GUI, ground,
 * item frame).
 *
 * <p>Like the other rifles the first-person pose lives in {@code WeaponHandGrip}, not here — this class
 * only hands the live bone chains to {@link Win94GeoModel#capture} after the clip has run, so the arms
 * drawn a few lines later in the same frame ride the gun wherever it actually is. The driven part is the
 * {@code lever} rather than a bolt handle: its 85° swing is the whole action.</p>
 */
public class Win94ItemRenderer extends GeoItemRenderer<Win94Item> {

    /** The bone the clips animate; everything else hangs off it. */
    private static final String MOVE_BONE = "move";

    /** The lever — its live pose is what the right hand is put on while the clip cycles the action. */
    private static final String LEVER_BONE = "lever";

    public Win94ItemRenderer() {
        super(new Win94GeoModel());
    }

    @Override
    public void renderByItem(ItemStack stack, ItemDisplayContext displayContext, PoseStack poseStack,
                             MultiBufferSource bufferSource, int packedLight, int packedOverlay) {
        super.renderByItem(stack, displayContext, poseStack, bufferSource, packedLight, packedOverlay);

        if (displayContext.firstPerson()) {
            CoreGeoBone move = getGeoModel().getAnimationProcessor().getBone(MOVE_BONE);
            CoreGeoBone lever = getGeoModel().getAnimationProcessor().getBone(LEVER_BONE);
            Win94GeoModel.capture(itemRenderTranslations, move, lever,
                    com.apocalypse.zombies.client.GunAimState.getAimProgress());
        }
    }
}
