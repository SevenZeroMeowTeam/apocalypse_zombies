package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.client.GunAimState;
import com.apocalypse.zombies.client.model.AWMGeoModel;
import com.apocalypse.zombies.item.AWMItem;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.world.item.ItemDisplayContext;
import net.minecraft.world.item.ItemStack;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.renderer.GeoItemRenderer;

/**
 * Draws the AWM from its GeckoLib model, in every context it can appear (hand, GUI, ground, item frame).
 *
 * <p>Forge applies the model's {@code display} block — see {@code models/item/awm.json} — before this renderer
 * is called, which is what makes the gun the right size in the hand. The hold pose (sight up while aiming, the
 * kick of a shot) belongs to the first-person pass instead, so that the arms can be built on the very same pose:
 * see {@code ClientEvents.onRenderHand}. Keeping it there rather than in an animation clip also means the
 * recoil, the bolt and the reload keep playing from their own bones while the gun stays shouldered.</p>
 *
 * <p>The renderer's other job is recording where the gun ended up, so the hands can follow it — see the same
 * note on {@link M1GarandItemRenderer}.</p>
 */
public class AWMItemRenderer extends GeoItemRenderer<AWMItem> {

    /** The bone the clips animate; hand targets transformed by its chain land wherever the gun is. */
    private static final String MOVE_BONE = "move";

    public AWMItemRenderer() {
        super(new AWMGeoModel());
    }

    @Override
    public void renderByItem(ItemStack stack, ItemDisplayContext displayContext, PoseStack poseStack,
                             MultiBufferSource bufferSource, int packedLight, int packedOverlay) {
        super.renderByItem(stack, displayContext, poseStack, bufferSource, packedLight, packedOverlay);

        if (displayContext.firstPerson()) {
            CoreGeoBone move = getGeoModel().getAnimationProcessor().getBone(MOVE_BONE);
            AWMGeoModel.capture(itemRenderTranslations, move, GunAimState.getAimProgress());
        }
    }
}
