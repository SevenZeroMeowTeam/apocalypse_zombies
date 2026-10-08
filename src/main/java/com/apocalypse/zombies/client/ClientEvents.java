package com.apocalypse.zombies.client;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.weapon.WeaponArms;
import com.apocalypse.zombies.client.weapon.WeaponHandGrip;
import com.apocalypse.zombies.item.GunItem;
import com.apocalypse.zombies.moon.MoonEvent;
import com.apocalypse.zombies.network.FirePacket;
import com.apocalypse.zombies.network.NetworkHandler;
import com.apocalypse.zombies.client.weapon.AmmoWheel;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.Tesselator;
import com.mojang.blaze3d.vertex.VertexFormat;
import com.mojang.blaze3d.vertex.VertexSorting;
import com.mojang.math.Axis;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.client.renderer.GameRenderer;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.item.ItemDisplayContext;
import net.minecraft.world.item.ItemStack;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ClientPlayerNetworkEvent;
import net.minecraftforge.client.event.InputEvent;
import net.minecraftforge.client.event.RenderGuiEvent;
import net.minecraftforge.client.event.RenderGuiOverlayEvent;
import net.minecraftforge.client.event.RenderHandEvent;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.client.event.ViewportEvent;
import net.minecraftforge.client.gui.overlay.VanillaGuiOverlay;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;

/**
 * Everything the client draws and reads for the mod: the tinted night sky, and the weapon's controls and HUD.
 *
 * <p>Sky: vanilla paints it before anything else and writes no depth while doing it, so a full-screen wash
 * at {@code AFTER_SKY} reaches exactly the pixels the sky occupies — terrain, entities and weather are all
 * drawn afterwards and paint straight over it. The moon is then drawn again, larger and tinted, because the
 * wash would otherwise drown it.</p>
 *
 * <p>Weapon: this class owns the input half of the gun (left mouse = trigger, right mouse = sight, R =
 * reload) and the readouts that go with it. It holds no authority — every action is a request to the
 * server, and the round count and the state machine live in the stack's NBT on the server. Aiming is the
 * one exception: the zoom, the raised pose and the scope overlay are local, so the state that drives them
 * sits in {@link GunAimState} and is never synced.</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class ClientEvents {

    private static final ResourceLocation MOON_LOCATION =
            new ResourceLocation("textures/environment/moon_phases.png");

    /** Distance vanilla draws the moon quad at. Pulled a hair closer so we beat it on depth. */
    private static final float MOON_DISTANCE = 99.0F;
    /** Vanilla's moon sprite half-size. */
    private static final float MOON_BASE_SIZE = 20.0F;

    /** Ticks between fire requests while the trigger is held. A packet throttle, not the rate of fire. */
    private static final int FIRE_THROTTLE_TICKS = 2;
    /** Fraction of the shorter screen edge the scope's lens fills once fully aimed. */
    private static final float SCOPE_RADIUS_FRACTION = 0.42F;
    /** Peak opacity outside the lens — near-opaque, so the world is only visible through the glass. */
    private static final float SCOPE_DARKNESS = 0.93F;
    /** Quads around the lens ring; 96 reads as a circle at any realistic window size. */
    private static final int SCOPE_SEGMENTS = 96;
    /**
     * Aim progress at which the optic owns the frame and the first-person model — the rifle and both arms —
     * stops being drawn ({@link GunItem#hidesModelWhileAimed()}, {@link #onRenderHand}). One number, to
     * taste: too early and the rifle is yanked out of a screen that is still all world, too late and it
     * disappears at the centre of an almost fully opened lens.
     */
    private static final float SCOPE_HIDE_MODEL_AT = 0.5F;
    /**
     * The clear sight's glass ({@link GunItem.SightStyle#CLEAR_SIGHT}): a pale wash rather than a blackout, so
     * the world still reads through it — that is the whole difference between the two sights. Alpha is the value
     * at full aim and rides the aim progress like {@link #SCOPE_DARKNESS} does.
     */
    private static final int CLEAR_LENS_COLOUR = 0x8FB6C8;
    private static final float CLEAR_LENS_ALPHA = 0.07F;
    /** The ring around that glass, in pixels of thickness and at full-aim alpha. */
    private static final float CLEAR_RIM_THICKNESS = 1.5F;
    private static final float CLEAR_RIM_ALPHA = 0.45F;
    /**
     * The clear sight's crosshair, which is two colours on purpose: a dark core with a pale halo one pixel out
     * on either side. A single-colour cross cannot read against both a bright sky and a dark silhouette, and the
     * telescope does not have to — its lens is black behind the reticle, so anything drawn on it is the only
     * thing there. The clear sight keeps the world, so the reticle has to carry its own contrast.
     */
    private static final int RETICLE_CORE_COLOUR = 0x101010;
    private static final float RETICLE_CORE_ALPHA = 0.85F;
    private static final int RETICLE_HALO_COLOUR = 0xF2F2F2;
    private static final float RETICLE_HALO_ALPHA = 0.45F;
    /** Crosshair geometry, as fractions of the lens radius — the telescope's are inline in {@link #renderReticle}. */
    private static final float RETICLE_ARM_FRACTION = 0.55F;
    private static final float RETICLE_GAP_FRACTION = 0.07F;
    private static final float RETICLE_TICK_FRACTION = 0.045F;

    private ClientEvents() {
    }

    // ------------------------------------------------------------------ fog

    /** Nothing from the old server should survive into the next one. */
    @SubscribeEvent
    public static void onLoggingOut(ClientPlayerNetworkEvent.LoggingOut event) {
        ClientMoonState.reset();
        ClientZombieTiers.clear();
        GunAimState.reset();
        // 轮盘是本地状态：世界没了还挂着的话，回到主菜单会留一圈弹种名，而且鼠标还是释放状态。
        AmmoWheel.dismiss(Minecraft.getInstance());
    }

    @SubscribeEvent
    public static void onComputeFogColor(ViewportEvent.ComputeFogColor event) {
        MoonEvent moon = ClientMoonState.getMoonEvent();
        if (!moon.isActive()) {
            return;
        }
        float strength = Mth.clamp(moon.getSkyAlpha() * 1.6F, 0.0F, 0.95F);
        event.setRed(Mth.lerp(strength, event.getRed(), moon.fogRed()));
        event.setGreen(Mth.lerp(strength, event.getGreen(), moon.fogGreen()));
        event.setBlue(Mth.lerp(strength, event.getBlue(), moon.fogBlue()));
    }

    // ------------------------------------------------------------------ input

    /**
     * Drives the weapon's controls once per tick: the aim state, and holding the trigger down.
     *
     * <p>R is a one-shot request, so its queue is drained even while a screen is open (otherwise clicks
     * banked in a menu would all fire at once on closing it). Left mouse is the opposite — a bolt gun fires
     * for as long as the button is held, at whatever rate the action lock allows — so it is read as a live
     * key state rather than a click. The client never decides anything: no round count, no lock timer, no
     * hit detection lives here. The throttle below only limits pointless packets; the server's lock is what
     * sets the real cadence.</p>
     */
    @SubscribeEvent
    public static void onClientTick(TickEvent.ClientTickEvent event) {
        if (event.phase != TickEvent.Phase.END) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();

        // Local-only: the zoom and the raised pose ease in over the gun's aim time, so this runs every tick.
        GunAimState.tick(minecraft);

        // 弹种轮盘：R 的按下与松开都归它管（按住弹、松开装）。必须排在下面那几个提前 return 之前 ——
        // 手里没枪、或轮盘开着时又开了别的界面，这两种情况都得让"松开 R"这件事被处理掉，否则轮盘会挂住。
        AmmoWheel.tick(minecraft);

        if (minecraft.screen != null || minecraft.player == null) {
            return;
        }
        if (!(minecraft.player.getMainHandItem().getItem() instanceof GunItem)) {
            return;
        }
        if (minecraft.options.keyAttack.isDown()
                && minecraft.player.tickCount % FIRE_THROTTLE_TICKS == 0) {
            NetworkHandler.CHANNEL.sendToServer(new FirePacket());
        }
    }

    /**
     * Takes both mouse buttons away from vanilla while the gun is held.
     *
     * <p>Left mouse would otherwise swing an empty fist and break blocks on every shot; right mouse would
     * open whatever the player is looking at instead of coming up on the sight. Cancelling the interaction
     * is what makes the two buttons the gun's own. Firing is sent from here as well as from the tick poll so
     * that a single click responds on the same frame it happens.</p>
     */
    @SubscribeEvent
    public static void onInteractionKeyMapping(InputEvent.InteractionKeyMappingTriggered event) {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.player == null
                || !(minecraft.player.getMainHandItem().getItem() instanceof GunItem)) {
            return;
        }
        if (event.isAttack()) {
            event.setSwingHand(false);
            event.setCanceled(true);
            NetworkHandler.CHANNEL.sendToServer(new FirePacket());
        } else if (event.isUseItem()) {
            event.setCanceled(true);
        }
    }

    /**
     * Scope magnification, eased in with the same progress that raises the gun so the zoom is attached to
     * the animation rather than snapping on. Only touches the configured field of view, so the spyglass,
     * the nausea wobble and the death screen keep their own values.
     */
    @SubscribeEvent
    public static void onComputeFov(ViewportEvent.ComputeFov event) {
        float progress = GunAimState.getAimProgress();
        if (progress <= 0.0F || !event.usedConfiguredFov()) {
            return;
        }
        event.setFOV(Mth.lerp(progress, event.getFOV(), GunAimState.aimedFov()));
    }

    /**
     * An optic draws its own reticle, so vanilla's centre cross is cancelled while the sight is up. Iron
     * sights keep the crosshair — with no overlay behind it, it is the only aim point the player has.
     */
    @SubscribeEvent
    public static void onRenderGuiOverlayPre(RenderGuiOverlayEvent.Pre event) {
        if (GunAimState.isAiming() && GunAimState.hasScopeOverlay()
                && event.getOverlay().id().equals(VanillaGuiOverlay.CROSSHAIR.id())) {
            event.setCanceled(true);
        }
    }

    // ------------------------------------------------------------------ sky

    /**
     * Puts the weapon in the player's hands: the gun held in our own two arms, instead of vanilla's one arm
     * holding it like a shovel.
     *
     * <p>Order matters and is the whole trick. Vanilla fires this event from inside its hand render, before it
     * draws the arm and the item, and the pose stack at that moment is a clean hand base — so this records that
     * layer first ({@link WeaponArms#captureCleanPose}), then cancels the event. Cancelling is what removes the
     * vanilla arm; the gun is not lost with it, because it is re-drawn from here ({@code renderStatic} puts the
     * item model's {@code display} back on, so it lands exactly where it did before). Our two arms go on after
     * it. Anything that is not one of our guns is left entirely to vanilla.</p>
     *
     * <p>{@code HIGHEST} rather than the default: a clean base is only on the stack until the first handler
     * touches it, and other first-person mods are exactly the kind that touches it.</p>
     *
     * <p>An optic that answers {@link GunItem#hidesModelWhileAimed()} is the one case where nothing is drawn
     * from here at all: past {@link #SCOPE_HIDE_MODEL_AT} of the raise the rifle and the arms are gone and the
     * scope overlay's lens is the only thing the player is looking through.</p>
     */
    /**
     * 一次性诊断开关：右键瞄准时看不到枪和手，打开它会把渲染链的关键分支每秒打一行到日志。
     *
     * <p>默认关闭 —— 与 {@code WeaponArms} 里那个 {@code ARMSDBG} 探针同一条规矩：探针留在原地备用，
     * 平时不写日志。瞄准问题定位完可以整个删掉。</p>
     */
    public static final boolean DIAG_AIM = false;
    private static long lastGripDiag;

    @SubscribeEvent(priority = EventPriority.HIGHEST)
    public static void onRenderHand(RenderHandEvent event) {
        Minecraft minecraft = Minecraft.getInstance();
        LocalPlayer player = minecraft.player;
        if (player == null || minecraft.level == null) {
            return;
        }
        if (!minecraft.options.getCameraType().isFirstPerson()) {
            return;
        }
        if (event.getHand() != InteractionHand.MAIN_HAND) {
            // The guns are two-handed, and the left hand you see on them is ours (WeaponArms): vanilla's
            // off-hand pass would draw its item out of the middle of that same hand — a torch or a shield
            // sticking through the fore-end. So whenever one of our guns is in the main hand, the whole
            // off-hand pass is cancelled, item and arm alike.
            //
            // An optic that owns the whole frame once it is up is the same cancellation for one more reason:
            // an off-hand torch — or the arm under it — floating in the middle of the lens is exactly what an
            // eyepiece is supposed to black out.
            if (player.getMainHandItem().getItem() instanceof GunItem || sightOwnsFrame(event.getPartialTick())) {
                event.setCanceled(true);
            }
            return;
        }
        ItemStack stack = event.getItemStack();
        if (!(stack.getItem() instanceof GunItem gun)) {
            WeaponArms.forgetFrames();
            return;
        }

        WeaponArms.captureCleanPose(event.getPoseStack());
        event.setCanceled(true);

        // Behind the eyepiece there is no rifle and no arm to see — see sightOwnsFrame below. The cancellation
        // above stands in this branch too: it is what keeps vanilla's single arm from coming back in through
        // the gap.
        if (sightOwnsFrame(event.getPartialTick())) {
            WeaponArms.forgetFrames();
            return;
        }

        long now = minecraft.level.getGameTime();
        String action = gun.action(stack, now);
        float progress = gun.actionProgress(stack, now);

        PoseStack pose = event.getPoseStack();
        pose.pushPose();
        boolean gripApplied = WeaponHandGrip.apply(pose, player, player.getMainArm(), stack,
                event.getEquipProgress());
        // 诊断（默认关）：确认渲染链走到哪一步。
        long diagNow = System.currentTimeMillis();
        if (DIAG_AIM && diagNow - lastGripDiag > 2000L) {
            lastGripDiag = diagNow;
            ApocalypseZombies.LOGGER.info(
                    "[瞄准调试] item={} usingItem={} useAnim={} equip={} aim={} sprint={} sightOwns={} gripApplied={}",
                    stack.getItem(), player.isUsingItem(), stack.getUseAnimation(),
                    String.format("%.2f", event.getEquipProgress()),
                    String.format("%.2f", GunAimState.getAimProgress(event.getPartialTick())),
                    String.format("%.2f", GunAimState.getSprintProgress(event.getPartialTick())),
                    sightOwnsFrame(event.getPartialTick()), gripApplied);
        }
        if (gripApplied) {
            // The context carries the hand, so the model's display block lands it exactly where vanilla would.
            minecraft.getItemRenderer().renderStatic(stack, ItemDisplayContext.FIRST_PERSON_RIGHT_HAND,
                    event.getPackedLight(), OverlayTexture.NO_OVERLAY, pose, event.getMultiBufferSource(),
                    minecraft.level, 0);
        }
        pose.popPose();

        WeaponArms.renderHeld(minecraft, pose, event.getMultiBufferSource(), event.getPackedLight(),
                action, progress);
    }

    /**
     * True once the optic in hand has taken the frame over: the sight is one that answers
     * {@link GunItem#hidesModelWhileAimed()}, and it is up past {@link #SCOPE_HIDE_MODEL_AT}.
     *
     * <p>The rule it encodes — a lens is a window, so whatever the first-person pass draws in front of it is
     * what the player would be looking through, and by the end of the raise the rifle sits on the very centre
     * of the screen. The <em>timing</em> is the other half: the overlay's veil covers everything but the lens
     * at {@code SCOPE_DARKNESS × progress}, so handing the frame over halfway up happens under a screen that
     * is already nearly half black, and the rifle is not seen to blink out of existence.</p>
     */
    private static boolean sightOwnsFrame(float partialTick) {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.player == null
                || !(minecraft.player.getMainHandItem().getItem() instanceof GunItem gun)
                || !gun.hidesModelWhileAimed()) {
            return false;
        }
        return GunAimState.getAimProgress(partialTick) >= SCOPE_HIDE_MODEL_AT;
    }

    @SubscribeEvent
    public static void onRenderLevelStage(RenderLevelStageEvent event) {
        MoonEvent moon = ClientMoonState.getMoonEvent();
        if (!moon.isActive()) {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.level == null || minecraft.player == null) {
            return;
        }
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_SKY) {
            return;
        }
        renderSkyWash(minecraft, moon);
        renderMoon(event, moon);
    }

    /** Paints the whole sky in the moon's colour. */
    private static void renderSkyWash(Minecraft minecraft, MoonEvent moon) {
        int width = minecraft.getWindow().getWidth();
        int height = minecraft.getWindow().getHeight();

        Matrix4f previousProjection = RenderSystem.getProjectionMatrix();
        PoseStack modelView = RenderSystem.getModelViewStack();

        // Cancel whatever model-view is currently active so the quad is drawn in raw screen space.
        modelView.pushPose();
        modelView.mulPoseMatrix(new Matrix4f(RenderSystem.getModelViewMatrix()).invert());
        RenderSystem.applyModelViewMatrix();
        RenderSystem.setProjectionMatrix(
                new Matrix4f().setOrtho(0.0F, (float) width, (float) height, 0.0F, -1000.0F, 1000.0F),
                VertexSorting.ORTHOGRAPHIC_Z);

        RenderSystem.disableDepthTest();
        RenderSystem.depthMask(false);
        RenderSystem.disableCull();
        RenderSystem.enableBlend();
        RenderSystem.defaultBlendFunc();
        RenderSystem.setShader(GameRenderer::getPositionColorShader);

        float red = moon.skyRed();
        float green = moon.skyGreen();
        float blue = moon.skyBlue();
        float alpha = moon.getSkyAlpha();

        Tesselator tesselator = Tesselator.getInstance();
        BufferBuilder buffer = tesselator.getBuilder();
        buffer.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.POSITION_COLOR);
        buffer.vertex(0.0F, (float) height, 0.0F).color(red, green, blue, alpha).endVertex();
        buffer.vertex((float) width, (float) height, 0.0F).color(red, green, blue, alpha).endVertex();
        buffer.vertex((float) width, 0.0F, 0.0F).color(red, green, blue, alpha).endVertex();
        buffer.vertex(0.0F, 0.0F, 0.0F).color(red, green, blue, alpha).endVertex();
        tesselator.end();

        RenderSystem.disableBlend();
        RenderSystem.enableCull();
        RenderSystem.depthMask(true);
        RenderSystem.enableDepthTest();

        RenderSystem.getModelViewStack().popPose();
        RenderSystem.applyModelViewMatrix();
        RenderSystem.setProjectionMatrix(previousProjection, VertexSorting.DISTANCE_TO_ORIGIN);
    }
    /**
     * Draws the moon again, bigger and tinted. Uses exactly vanilla's transforms so the sprite lands
     * on top of the one the wash just covered.
     */
    private static void renderMoon(RenderLevelStageEvent event, MoonEvent moon) {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.level == null) {
            return;
        }
        PoseStack pose = event.getPoseStack();
        float size = MOON_BASE_SIZE * moon.getMoonScale();

        pose.pushPose();
        pose.mulPose(Axis.YP.rotationDegrees(-90.0F));
        pose.mulPose(Axis.XP.rotationDegrees(minecraft.level.getTimeOfDay(event.getPartialTick()) * 360.0F));
        Matrix4f matrix = pose.last().pose();

        int phase = minecraft.level.getMoonPhase();
        int column = phase % 4;
        int row = phase / 4 % 2;
        float u0 = (float) column / 4.0F;
        float v0 = (float) row / 2.0F;
        float u1 = (float) (column + 1) / 4.0F;
        float v1 = (float) (row + 1) / 2.0F;

        RenderSystem.setShader(GameRenderer::getPositionTexShader);
        RenderSystem.setShaderTexture(0, MOON_LOCATION);
        RenderSystem.setShaderColor(moon.moonTintRed(), moon.moonTintGreen(), moon.moonTintBlue(), 1.0F);
        RenderSystem.enableBlend();
        RenderSystem.blendFuncSeparate(
                com.mojang.blaze3d.platform.GlStateManager.SourceFactor.SRC_ALPHA,
                com.mojang.blaze3d.platform.GlStateManager.DestFactor.ONE,
                com.mojang.blaze3d.platform.GlStateManager.SourceFactor.ONE,
                com.mojang.blaze3d.platform.GlStateManager.DestFactor.ZERO);
        RenderSystem.depthMask(false);

        Tesselator tesselator = Tesselator.getInstance();
        BufferBuilder buffer = tesselator.getBuilder();
        buffer.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.POSITION_TEX);
        buffer.vertex(matrix, -size, -MOON_DISTANCE, size).uv(u1, v1).endVertex();
        buffer.vertex(matrix, size, -MOON_DISTANCE, size).uv(u0, v1).endVertex();
        buffer.vertex(matrix, size, -MOON_DISTANCE, -size).uv(u0, v0).endVertex();
        buffer.vertex(matrix, -size, -MOON_DISTANCE, -size).uv(u1, v0).endVertex();
        tesselator.end();

        RenderSystem.depthMask(true);
        RenderSystem.defaultBlendFunc();
        RenderSystem.setShaderColor(1.0F, 1.0F, 1.0F, 1.0F);
        RenderSystem.disableBlend();
        pose.popPose();
    }

    // ------------------------------------------------------------------ hud

    /** A small corner readout so players can tell which blessing is running. */
    @SubscribeEvent
    public static void onRenderGui(RenderGuiEvent.Post event) {
        Minecraft minecraft = Minecraft.getInstance();

        // 弹种轮盘画在整个 HUD 之上。必须排在下面那个「今晚没有月相就直接返回」之前 ——
        // 轮盘与月亮无关，不能因为是个平凡的夜晚就不显示。
        AmmoWheel.render(event.getGuiGraphics(), minecraft);

        MoonEvent moon = ClientMoonState.getMoonEvent();
        if (!moon.isActive()) {
            return;
        }
        if (minecraft.options.hideGui || minecraft.player == null || minecraft.level == null) {
            return;
        }
        GuiGraphics graphics = event.getGuiGraphics();
        int color = 0xFF000000 | moon.getMoonTint();
        graphics.drawString(minecraft.font, moon.getDisplayName(), 4, 4, color, true);
        int evolution = ClientMoonState.getEvolutionLevel();
        graphics.drawString(minecraft.font,
                net.minecraft.network.chat.Component.translatable(
                        "command.apocalypse_zombies.evolution.get", evolution),
                4, 4 + 10, 0xFFAAAAAA, true);
    }

    /**
     * The weapon's readouts: the sight's overlay when it is up, then the round counter under it.
     *
     * <p>Both live in one handler because the order matters — whichever overlay is drawn darkens or washes the
     * screen, and the counter has to survive that.</p>
     */
    @SubscribeEvent
    public static void onRenderWeaponGui(RenderGuiEvent.Post event) {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.options.hideGui || minecraft.player == null || minecraft.level == null) {
            return;
        }
        GuiGraphics graphics = event.getGuiGraphics();

        float progress = GunAimState.getAimProgress(event.getPartialTick());
        if (progress > 0.0F && GunAimState.hasScopeOverlay()) {
            if (GunAimState.sightStyle() == GunItem.SightStyle.CLEAR_SIGHT) {
                renderClearSight(graphics, progress);
            } else {
                renderScope(graphics, progress);
            }
        }
        renderAmmoCounter(minecraft, graphics);
    }

    /**
     * The scope view: everything outside a circle goes black, with a reticle in the middle.
     *
     * <p>Built from an annulus of quads instead of a texture, so the mod ships no art for the sight: the
     * inner edge is the lens and the outer edge is far enough out to cover the corners of any window. Radius
     * and darkness both ride the aim progress, which is what makes the sight feel like it opens up as it
     * comes to the eye rather than being pasted on.</p>
     */
    private static void renderScope(GuiGraphics graphics, float progress) {
        int width = graphics.guiWidth();
        int height = graphics.guiHeight();
        float centreX = width / 2.0F;
        float centreY = height / 2.0F;
        float radius = Math.min(width, height) * SCOPE_RADIUS_FRACTION * progress;
        float outer = (float) Math.hypot(width, height);
        float alpha = SCOPE_DARKNESS * progress;

        Matrix4f matrix = graphics.pose().last().pose();

        RenderSystem.enableBlend();
        RenderSystem.defaultBlendFunc();
        RenderSystem.disableCull();
        RenderSystem.setShader(GameRenderer::getPositionColorShader);

        Tesselator tesselator = Tesselator.getInstance();
        BufferBuilder buffer = tesselator.getBuilder();
        buffer.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.POSITION_COLOR);
        for (int segment = 0; segment < SCOPE_SEGMENTS; segment++) {
            double start = segment * (Math.PI * 2.0) / SCOPE_SEGMENTS;
            double end = (segment + 1) * (Math.PI * 2.0) / SCOPE_SEGMENTS;
            float innerX0 = centreX + (float) (Math.cos(start) * radius);
            float innerY0 = centreY + (float) (Math.sin(start) * radius);
            float innerX1 = centreX + (float) (Math.cos(end) * radius);
            float innerY1 = centreY + (float) (Math.sin(end) * radius);
            float outerX0 = centreX + (float) (Math.cos(start) * outer);
            float outerY0 = centreY + (float) (Math.sin(start) * outer);
            float outerX1 = centreX + (float) (Math.cos(end) * outer);
            float outerY1 = centreY + (float) (Math.sin(end) * outer);
            buffer.vertex(matrix, innerX0, innerY0, 0.0F).color(0.0F, 0.0F, 0.0F, alpha).endVertex();
            buffer.vertex(matrix, innerX1, innerY1, 0.0F).color(0.0F, 0.0F, 0.0F, alpha).endVertex();
            buffer.vertex(matrix, outerX1, outerY1, 0.0F).color(0.0F, 0.0F, 0.0F, alpha).endVertex();
            buffer.vertex(matrix, outerX0, outerY0, 0.0F).color(0.0F, 0.0F, 0.0F, alpha).endVertex();
        }
        tesselator.end();

        RenderSystem.enableCull();
        RenderSystem.disableBlend();

        renderReticle(graphics, centreX, centreY, radius, progress);
    }

    /** Crosshair, mil marks and centre dot, all sized off the lens so they scale with the zoom. */
    private static void renderReticle(GuiGraphics graphics, float centreX, float centreY, float radius,
                                      float progress) {
        int crosshair = ((int) (0xCC * progress) << 24) | 0x101010;
        int arm = (int) (radius * 0.55F);
        graphics.fill((int) centreX - arm, (int) centreY - 1, (int) centreX + arm, (int) centreY + 1, crosshair);
        graphics.fill((int) centreX - 1, (int) centreY - arm, (int) centreX + 1, (int) centreY + arm, crosshair);

        // Graduations down the lower stadia, the way a sniper scope is marked up.
        int half = (int) (radius * 0.045F);
        for (int mark = 1; mark <= 4; mark++) {
            int y = (int) (centreY + radius * 0.16F * mark);
            graphics.fill((int) centreX - half, y - 1, (int) centreX + half, y + 1, crosshair);
        }

        // Centre dot, reddish so it reads against both snow and shadow.
        int dot = ((int) (0xE6 * progress) << 24) | 0xB02020;
        graphics.fill((int) centreX - 1, (int) centreY - 1, (int) centreX + 2, (int) centreY + 2, dot);
    }

    /**
     * The clear sight: a lens the player looks <em>past</em> rather than a tube they look <em>through</em> — a
     * pale wash of glass with a ring round it and a cross on the centre of the screen, and no blackout at all.
     *
     * <p>Everything that makes an aim point readable is shared with the telescope's reticle by intent: the cross
     * is on the centre of the screen, arm and gap are fractions of the same lens radius, the graduations run down
     * the lower stadia and the centre dot is the same red. The two differences are the ones that make this one
     * transparent. The glass is {@link #CLEAR_LENS_COLOUR} at {@link #CLEAR_LENS_ALPHA} instead of black at
     * {@link #SCOPE_DARKNESS}, so the world stays visible; and the crosshair carries a pale halo
     * ({@link #RETICLE_HALO_COLOUR}) around its dark core, because unlike the telescope it is drawn over whatever
     * the player is looking at — a bright sky and a dark silhouette in the same field of view.</p>
     *
     * <p>Radius rides the aim progress exactly as the telescope's does, so the sight opens up as it comes to the
     * eye rather than being pasted on. The weapon stays in the frame throughout
     * ({@code CrossbowItem.hidesModelWhileAimed()} answers false for a clear sight): the player is aiming along
     * the crossbow, not into a lens.</p>
     */
    private static void renderClearSight(GuiGraphics graphics, float progress) {
        int width = graphics.guiWidth();
        int height = graphics.guiHeight();
        float centreX = width / 2.0F;
        float centreY = height / 2.0F;
        float radius = Math.min(width, height) * SCOPE_RADIUS_FRACTION * progress;

        // The glass, then its rim. Inner radius 0 makes the first one a disc.
        renderRing(graphics, centreX, centreY, 0.0F, radius, CLEAR_LENS_COLOUR, CLEAR_LENS_ALPHA * progress);
        renderRing(graphics, centreX, centreY, radius - CLEAR_RIM_THICKNESS, radius,
                RETICLE_CORE_COLOUR, CLEAR_RIM_ALPHA * progress);

        renderClearReticle(graphics, centreX, centreY, radius, progress);
    }

    /**
     * One ring of quads between two radii, as {@code POSITION_COLOR} geometry, or a disc when {@code inner} is
     * zero. Built rather than textured for the same reason the telescope's annulus is: the mod ships no art for
     * its sights, so the shape has to come out of arithmetic.
     */
    private static void renderRing(GuiGraphics graphics, float centreX, float centreY, float inner, float outer,
                                   int colour, float alpha) {
        float red = ((colour >> 16) & 0xFF) / 255.0F;
        float green = ((colour >> 8) & 0xFF) / 255.0F;
        float blue = (colour & 0xFF) / 255.0F;

        Matrix4f matrix = graphics.pose().last().pose();

        RenderSystem.enableBlend();
        RenderSystem.defaultBlendFunc();
        RenderSystem.disableCull();
        RenderSystem.setShader(GameRenderer::getPositionColorShader);

        Tesselator tesselator = Tesselator.getInstance();
        BufferBuilder buffer = tesselator.getBuilder();
        buffer.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.POSITION_COLOR);
        for (int segment = 0; segment < SCOPE_SEGMENTS; segment++) {
            double start = segment * (Math.PI * 2.0) / SCOPE_SEGMENTS;
            double end = (segment + 1) * (Math.PI * 2.0) / SCOPE_SEGMENTS;
            float innerX0 = centreX + (float) (Math.cos(start) * inner);
            float innerY0 = centreY + (float) (Math.sin(start) * inner);
            float innerX1 = centreX + (float) (Math.cos(end) * inner);
            float innerY1 = centreY + (float) (Math.sin(end) * inner);
            float outerX0 = centreX + (float) (Math.cos(start) * outer);
            float outerY0 = centreY + (float) (Math.sin(start) * outer);
            float outerX1 = centreX + (float) (Math.cos(end) * outer);
            float outerY1 = centreY + (float) (Math.sin(end) * outer);
            buffer.vertex(matrix, innerX0, innerY0, 0.0F).color(red, green, blue, alpha).endVertex();
            buffer.vertex(matrix, innerX1, innerY1, 0.0F).color(red, green, blue, alpha).endVertex();
            buffer.vertex(matrix, outerX1, outerY1, 0.0F).color(red, green, blue, alpha).endVertex();
            buffer.vertex(matrix, outerX0, outerY0, 0.0F).color(red, green, blue, alpha).endVertex();
        }
        tesselator.end();

        RenderSystem.enableCull();
        RenderSystem.disableBlend();
    }

    /**
     * The clear sight's crosshair: the dark core of the telescope's, plus a pale halo one pixel proud of it on
     * every side, the graduations down the lower stadia and two above for symmetry, and the red centre dot.
     *
     * <p>Haloes go down first and all of them at once, then the cores over the top: at the join the four limbs'
     * haloes meet, and painting a limb's halo after another limb's core would bite a notch out of it.</p>
     */
    private static void renderClearReticle(GuiGraphics graphics, float centreX, float centreY, float radius,
                                           float progress) {
        int core = ((int) (RETICLE_CORE_ALPHA * 255 * progress) << 24) | RETICLE_CORE_COLOUR;
        int halo = ((int) (RETICLE_HALO_ALPHA * 255 * progress) << 24) | RETICLE_HALO_COLOUR;
        int x = (int) centreX;
        int y = (int) centreY;
        int arm = (int) (radius * RETICLE_ARM_FRACTION);
        int gap = Math.max(2, (int) (radius * RETICLE_GAP_FRACTION));
        int half = (int) (radius * RETICLE_TICK_FRACTION);

        // Halos: one pixel out on every side of where the core will land.
        graphics.fill(x - arm - 1, y - 1, x - gap + 2, y + 3, halo);         // left
        graphics.fill(x + gap - 1, y - 1, x + arm + 2, y + 3, halo);         // right
        graphics.fill(x - 1, y - arm - 1, x + 3, y - gap + 2, halo);         // up
        graphics.fill(x - 1, y + gap - 1, x + 3, y + arm + 2, halo);         // down
        for (int mark = 1; mark <= 4; mark++) {
            int tick = (int) (y + radius * 0.16F * mark);
            graphics.fill(x - half - 1, tick - 1, x + half + 2, tick + 3, halo);
        }
        for (int mark = 1; mark <= 2; mark++) {
            int tick = (int) (y - radius * 0.24F * mark);
            graphics.fill(x - half - 1, tick - 1, x + half + 2, tick + 3, halo);
        }

        // Cores, two pixels thick, stopping short of the centre so the dot is not crowded.
        graphics.fill(x - arm, y, x - gap + 1, y + 2, core);
        graphics.fill(x + gap, y, x + arm + 1, y + 2, core);
        graphics.fill(x, y - arm, x + 2, y - gap + 1, core);
        graphics.fill(x, y + gap, x + 2, y + arm + 1, core);
        for (int mark = 1; mark <= 4; mark++) {
            int tick = (int) (y + radius * 0.16F * mark);
            graphics.fill(x - half, tick, x + half + 1, tick + 2, core);
        }
        for (int mark = 1; mark <= 2; mark++) {
            int tick = (int) (y - radius * 0.24F * mark);
            graphics.fill(x - half, tick, x + half + 1, tick + 2, core);
        }

        int dot = ((int) (0xE6 * progress) << 24) | 0xB02020;
        graphics.fill(x - 1, y - 1, x + 2, y + 2, dot);
    }

    /** Rounds left, plus a bar while a magazine swap is in flight. */
    private static void renderAmmoCounter(Minecraft minecraft, GuiGraphics graphics) {
        ItemStack stack = minecraft.player.getMainHandItem();
        if (!(stack.getItem() instanceof GunItem gun)) {
            return;
        }
        Font font = minecraft.font;
        int screenWidth = graphics.guiWidth();
        int screenHeight = graphics.guiHeight();
        int ammo = gun.ammo(stack);

        // The name comes off the stack, so a new gun needs no change here.
        Component name = Component.translatable(stack.getItem().getDescriptionId());
        graphics.drawString(font, name, screenWidth - 8 - font.width(name), screenHeight - 46, 0xFFAAAAAA, true);

        String counter = ammo + " / " + gun.magazineSize();
        int colour = ammo == 0 ? 0xFFFF5555 : 0xFFFFFFFF;
        graphics.drawString(font, counter, screenWidth - 8 - font.width(counter), screenHeight - 34, colour, true);

        long now = minecraft.level.getGameTime();
        if (gun.isReloading(stack, now)) {
            int barWidth = 60;
            int x = screenWidth - 8 - barWidth;
            int y = screenHeight - 20;
            graphics.fill(x, y, x + barWidth, y + 3, 0xAA000000);
            graphics.fill(x, y, x + (int) (barWidth * gun.reloadProgress(stack, now)), y + 3, 0xFFD0A050);
        }
    }
}
