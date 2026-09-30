package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.client.model.MosinNagantGeoModel;
import com.apocalypse.zombies.item.MosinNagantItem;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.world.item.ItemDisplayContext;
import net.minecraft.world.item.ItemStack;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.renderer.GeoItemRenderer;

/**
 * Draws the 莫辛-纳甘 M91/30 from its GeckoLib model, in every context it can appear (hand, GUI, ground, item
 * frame).
 *
 * <p>Forge applies the model's {@code display} block — see {@code models/item/mosin_nagant.json} — before this
 * renderer is called, which is what makes the rifle the right size in the hand. The pose the gun is held in
 * (sights up while aiming, the kick of a shot) is <em>not</em> applied here: the first-person pass owns that,
 * because the arms have to be built on the same pose ({@code ClientEvents.onRenderHand} →
 * {@code WeaponHandGrip.apply}), and two places moving the gun is one too many.</p>
 *
 * <p>This rifle shares the AWM's third-person layout (its {@code display} block is the same one), so unlike the
 * Garand it needs no model-space offset here — see the long note on {@link M1GarandItemRenderer} for the case
 * where that rotation is the +90° one. What this renderer does add is the answer to "where did the gun end up":
 * GeckoLib captures its own base matrix in {@code preRender}, and by the time {@code super.renderByItem}
 * returns the bones hold this frame's clip values, so both are handed to {@link MosinNagantGeoModel#capture} —
 * and the arms, drawn a few lines later in the same frame, read it. The gun moves, the hands ride it.</p>
 */
public class MosinNagantItemRenderer extends GeoItemRenderer<MosinNagantItem> {

    /**
     * The bone the clips animate; everything else hangs off it, so a hand target transformed by its chain ends
     * up wherever the gun is.
     */
    private static final String MOVE_BONE = "move";

    /** The bolt — its live pose is what the right hand is put on while the clip works the handle. */
    private static final String BOLT_BONE = "bolt";

    public MosinNagantItemRenderer() {
        super(new MosinNagantGeoModel());
    }

    @Override
    public void renderByItem(ItemStack stack, ItemDisplayContext displayContext, PoseStack poseStack,
                             MultiBufferSource bufferSource, int packedLight, int packedOverlay) {
        super.renderByItem(stack, displayContext, poseStack, bufferSource, packedLight, packedOverlay);

        if (displayContext.firstPerson()) {
            CoreGeoBone move = getGeoModel().getAnimationProcessor().getBone(MOVE_BONE);
            CoreGeoBone bolt = getGeoModel().getAnimationProcessor().getBone(BOLT_BONE);
            MosinNagantGeoModel.capture(itemRenderTranslations, move, bolt,
                    com.apocalypse.zombies.client.GunAimState.getAimProgress());
        }
    }
}