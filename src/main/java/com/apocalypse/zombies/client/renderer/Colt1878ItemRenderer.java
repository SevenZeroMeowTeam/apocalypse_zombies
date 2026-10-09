package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.client.model.Colt1878GeoModel;
import com.apocalypse.zombies.item.Colt1878Item;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.world.item.ItemDisplayContext;
import net.minecraft.world.item.ItemStack;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.renderer.GeoItemRenderer;

/**
 * Draws the 柯尔特 1878 教练枪 from its GeckoLib model, in every context it can appear (hand, GUI, ground,
 * item frame).
 *
 * <p>Forge applies the model's {@code display} block — see {@code models/item/colt_1878.json} — before this
 * renderer is called, which is what makes the gun the right size in the hand. The pose it is held in (sights up
 * while aiming, the kick of a shot) is <em>not</em> applied here: the first-person pass owns that, because the
 * arms have to be built on the same pose ({@code ClientEvents.onRenderHand} →
 * {@code WeaponHandGrip.apply}), and two places moving the gun is one too many.</p>
 *
 * <p>What this renderer adds is the answer to "where did the gun end up": GeckoLib captures its own base matrix
 * in {@code preRender}, and by the time {@code super.renderByItem} returns the bones hold this frame's clip
 * values, so both are handed to {@link Colt1878GeoModel#capture} — and the arms, drawn a few lines later in the
 * same frame, read it. The <b>barrel</b> and <b>bolt_loaded</b> bones go along too: the first is what the fold
 * clips rotate (the support hand rides the fore-end, which is its child), the second is what the reload clips
 * drive (the support hand rides the fresh pair home).</p>
 */
public class Colt1878ItemRenderer extends GeoItemRenderer<Colt1878Item> {

    /** The bone the clips animate; everything else hangs off it. */
    private static final String MOVE_BONE = "move";
    /** The barrel group — the fold pivots here, and the fore-end folds with it. */
    private static final String BARREL_BONE = "barrel";
    /** The fresh pair of shells, which the support hand carries into the chambers. */
    private static final String SHELL_BONE = "bolt_loaded";

    public Colt1878ItemRenderer() {
        super(new Colt1878GeoModel());
    }

    @Override
    public void renderByItem(ItemStack stack, ItemDisplayContext displayContext, PoseStack poseStack,
                             MultiBufferSource bufferSource, int packedLight, int packedOverlay) {
        super.renderByItem(stack, displayContext, poseStack, bufferSource, packedLight, packedOverlay);

        if (displayContext.firstPerson()) {
            CoreGeoBone move = getGeoModel().getAnimationProcessor().getBone(MOVE_BONE);
            CoreGeoBone barrel = getGeoModel().getAnimationProcessor().getBone(BARREL_BONE);
            CoreGeoBone shell = getGeoModel().getAnimationProcessor().getBone(SHELL_BONE);
            Colt1878GeoModel.capture(itemRenderTranslations, move, barrel, shell,
                    com.apocalypse.zombies.client.GunAimState.getAimProgress());
        }
    }
}
