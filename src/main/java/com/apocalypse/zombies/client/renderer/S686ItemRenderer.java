package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.client.model.S686GeoModel;
import com.apocalypse.zombies.item.S686Item;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.world.item.ItemDisplayContext;
import net.minecraft.world.item.ItemStack;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.renderer.GeoItemRenderer;

/**
 * Draws Gold Plate - S686 from its GeckoLib model, in every context it can appear (hand, GUI, ground, item
 * frame).
 *
 * <p>Forge applies the model's {@code display} block — see {@code models/item/s686.json} — before this renderer
 * is called, which is what makes the gun the right size in the hand. The hold stance (sights up while aiming,
 * the kick of a shot) is <em>not</em> applied here: the first-person pass owns that, because the arms are
 * built on the same pose ({@code ClientEvents.onRenderHand} → {@code WeaponHandGrip.apply}). Two places moving
 * the gun is one too many.</p>
 *
 * <p>What this renderer does add is the answer to "where did the gun end up". GeckoLib captures its own base
 * matrix in {@code preRender}, and by the time {@code super.renderByItem} returns the bones hold this frame's
 * clip values, so both are handed to {@link S686GeoModel#capture} — and the arms, drawn a few lines later in the
 * same frame, read it. The gun moves, the hands ride it. The two <em>part</em> bones go with it, because this
 * gun's hands ride parts that move on their own: the fore-end folds with the barrel, and a fresh shell comes
 * home on its own bone.</p>
 */
public class S686ItemRenderer extends GeoItemRenderer<S686Item> {

    /**
     * The bone the clips animate; everything else hangs off it, so a hand target transformed by its chain ends
     * up wherever the gun is.
     */
    private static final String MOVE_BONE = "move";

    /** The barrel group — the fold clips rotate it, and the fore-end hangs off it. */
    private static final String BARREL_BONE = "barrel";

    /** The upper shell — the reload clips drive it, and the hand rides it home. */
    private static final String SHELL_BONE = "shell_upper";

    /**
     * Where the gun sits in the hand, third person — a model-space (blocks, pre-display-scale) offset.
     *
     * <h2>Why it is needed</h2>
     * {@code ItemInHandLayer}'s chain (translateToHand, X(−90), Y(180), then the
     * {@code (±1/16, 0.125, −0.625)} anchor) is written for Bedrock's hold convention: a model authored
     * <em>y-down</em>, its origin on a block corner. This model is authored y-up around its own centre, so the
     * chain leaves it hanging off the fist — rotated onto its side, caught by the muzzle end, a good half block
     * above the hand. The {@code thirdperson_*} display rotation in {@code models/item/s686.json} pitches it back
     * upright with the muzzle forward; this offset then brings the grip into the hand.
     *
     * <h2>The numbers</h2>
     * Solved from {@code T = S⁻¹Rᵀ(−A) − nudge − grip/16}, with {@code R} the hand layer's X+90 rotation (so
     * {@code Rᵀ(−A) = (−Aₓ, −A_z, A_y)}), {@code S = 0.58} this gun's third-person display scale (see the model
     * file: 19.50 u of gun between the M1's 17.63 u at 0.60 and the Mosin's 22.90 u at 0.55), {@code A = (±1/16,
     * 0.125, −0.625)} the layer's anchor, GeckoLib's {@code (0.5, 0.51, 0.5)} nudge from {@code preRender}, and
     * {@code grip} this gun's trigger-hand rest point ({@code S686GeoModel} {@code {0.00, −0.80, 4.90}} — further
     * back than the Uzi's, which is why these are bigger across the board).
     *
     * <p>Because it is a model-space offset it is applied <em>before</em> {@code super}, i.e. under the
     * display's own scale and rotation, exactly like GeckoLib's nudge next to it.</p>
     *
     * <p>Only {@code Aₓ} flips between hands — the anchor's own mirror, which is also why the gun sits a little
     * further out on the right: {@code −0.608} against {@code −0.392}, a difference of exactly
     * {@code 2·(1/16)/S}. The grip point is not mirrored, because it is the same physical part of the same gun
     * either way.</p>
     *
     * <p>These are solved, not eyeballed: the same closed form {@code tools/uzi_tp_solve.py} uses for the other
     * guns, re-run for this model's scale and grip point ({@code build/s686_pose_solve.js} is that solver as a
     * Node port, since this machine has no Python — it reproduces the Uzi's and the M1's own constants to
     * 4·10⁻⁴ before it is allowed to answer for this gun).</p>
     */
    private static final float TP_X_RIGHT = -0.608F;
    private static final float TP_X_LEFT = -0.392F;
    private static final float TP_Y = 0.618F;
    private static final float TP_Z = -0.591F;

    public S686ItemRenderer() {
        super(new S686GeoModel());
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
            CoreGeoBone barrel = getGeoModel().getAnimationProcessor().getBone(BARREL_BONE);
            CoreGeoBone shell = getGeoModel().getAnimationProcessor().getBone(SHELL_BONE);
            S686GeoModel.capture(itemRenderTranslations, move, barrel, shell,
                    com.apocalypse.zombies.client.GunAimState.getAimProgress());
        }
    }
}
