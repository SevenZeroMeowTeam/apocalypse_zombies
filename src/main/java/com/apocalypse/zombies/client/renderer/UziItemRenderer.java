package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.client.model.UziGeoModel;
import com.apocalypse.zombies.item.UziItem;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.world.item.ItemDisplayContext;
import net.minecraft.world.item.ItemStack;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.renderer.GeoItemRenderer;

/**
 * Draws the Uzi from its GeckoLib model, in every context it can appear (hand, GUI, ground, item frame).
 *
 * <p>Forge applies the model's {@code display} block — see {@code models/item/uzi.json} — before this renderer
 * is called, which is what makes the gun the right size in the hand. The hold stance (sights up while aiming,
 * the kick of a burst) is <em>not</em> applied here: the first-person pass owns that, because the arms are
 * built on the same pose ({@code ClientEvents.onRenderHand} → {@code WeaponHandGrip.apply}). Two places moving
 * the gun is one too many.</p>
 *
 * <p>What this renderer does add is the answer to "where did the gun end up". GeckoLib captures its own base
 * matrix in {@code preRender}, and by the time {@code super.renderByItem} returns the bones hold this frame's
 * clip values, so both are handed to {@link UziGeoModel#capture} — and the arms, drawn a few lines later in the
 * same frame, read it. The gun moves, the hands ride it.</p>
 */
public class UziItemRenderer extends GeoItemRenderer<UziItem> {

    /**
     * The bone the clips animate; everything else hangs off it, so a hand target transformed by its chain ends
     * up wherever the gun is.
     */
    private static final String MOVE_BONE = "move";

    /**
     * Where the gun sits in the hand, third person — a model-space (blocks, pre-display-scale) offset.
     *
     * <h2>Why it is needed</h2>
     * {@code ItemInHandLayer}'s chain (translateToHand, X(−90), Y(180), then the
     * {@code (±1/16, 0.125, −0.625)} anchor) is written for Bedrock's hold convention: a model authored
     * <em>y-down</em>, its origin on a block corner. This model is authored y-up around its own centre, so the
     * chain leaves it hanging off the fist — rotated onto its side, caught by the muzzle end, a good half block
     * above the hand. The {@code thirdperson_*} display rotation in {@code models/item/uzi.json} pitches it back
     * upright with the muzzle forward; this offset then brings the grip into the hand.
     *
     * <h2>The numbers</h2>
     * Solved from {@code T = S⁻¹Rᵀ(−A) − nudge − grip/16}, with {@code R} the hand layer's X+90 rotation (so
     * {@code Rᵀ(−A) = (−Aₓ, −A_z, A_y)}), {@code S = 0.67} the display scale, {@code A = (±1/16, 0.125, −0.625)}
     * the layer's anchor, GeckoLib's {@code (0.5, 0.51, 0.5)} nudge from {@code preRender}, and {@code grip}
     * this gun's trigger-hand rest point ({@code UziGeoModel} {@code {0.00, 0.50, 2.00}}).
     *
     * <p>Because it is a model-space offset it is applied <em>before</em> {@code super}, i.e. under the
     * display's own scale and rotation, exactly like GeckoLib's nudge next to it.</p>
     *
     * <p>Only {@code Aₓ} flips between hands — the anchor's own mirror, which is also why the gun sits a little
     * further out on the right: {@code −0.593} against {@code −0.407}. The grip point is not mirrored, because
     * it is the same physical part of the same gun either way.</p>
     *
     * <p>These are checked: {@code tools/pose_measure.py uzi} re-solves the chain from the geo and the display
     * block and fails if these constants drift more than 0.02 from it.</p>
     */
    private static final float TP_X_RIGHT = -0.593F;
    private static final float TP_X_LEFT = -0.407F;
    private static final float TP_Y = 0.392F;
    private static final float TP_Z = -0.438F;

    public UziItemRenderer() {
        super(new UziGeoModel());
    }

    @Override
    public void renderByItem(ItemStack stack, ItemDisplayContext displayContext, PoseStack poseStack,
                             MultiBufferSource bufferSource, int packedLight, int packedOverlay) {
        if (displayContext == ItemDisplayContext.THIRD_PERSON_RIGHT_HAND) {
            poseStack.translate(TP_X_RIGHT, TP_Y, TP_Z);
        } else if (displayContext == ItemDisplayContext.THIRD_PERSON_LEFT_HAND) {
            poseStack.translate(TP_X_LEFT, TP_Y, TP_Z);
        }

        super.renderByItem(stack, displayContext, poseStack, bufferSource, packedLight, packedOverlay);

        if (displayContext.firstPerson()) {
            CoreGeoBone move = getGeoModel().getAnimationProcessor().getBone(MOVE_BONE);
            UziGeoModel.capture(itemRenderTranslations, move,
                    com.apocalypse.zombies.client.GunAimState.getAimProgress());
        }
    }
}
