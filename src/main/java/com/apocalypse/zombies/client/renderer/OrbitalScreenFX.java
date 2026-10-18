package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.client.OrbitalStrikeClientState;
import com.apocalypse.zombies.orbital.engine.StrikeProtocol;
import com.apocalypse.zombies.orbital.engine.StrikeProtocols;
import com.apocalypse.zombies.item.OrbitalStrikeRemoteItem;
import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.Camera;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.core.BlockPos;
import net.minecraft.util.Mth;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.client.event.ViewportEvent;

/**
 * 轨道打击的屏幕级特效：HUD 倒计时、屏幕边缘色晕、落地白闪、镜头震动、FOV 冲击、
 * 演出黑边、目标标记与角框。
 *
 * <p>这一层与 {@link OrbitalStrikeHighlighter}（世界里的光柱/冲击环/裂纹）互补 ——
 * 那边管「世界里的东西」，这边管「你的屏幕」与「镜头」。</p>
 *
 * <p><b>配色</b>：整套轨道打击只用自己的「冷白 + 电青」色板（{@link #HUD_CYAN} /
 * {@link #CORE_WHITE}），不借用参考 mod 的红。青白是这台天基武器在模组里的识别色 ——
 * 与手里遥控器的选区框同一条色带。</p>
 *
 * <p><b>1.8.0 的打击感三件套</b>（本版保留）：落地帧白闪顶格 + 镜头慢摇冻结
 * {@link #FREEZE_TICKS}（伪 hit-stop，随后白闪衰减、震动才起）；FOV 在落地瞬间顿扩
 * {@link #FOV_PUNCH_DEGREES}° 后指数回弹；落地后屏幕边缘泛青白。</p>
 *
 * <p>全部状态从 {@link OrbitalStrikeClientState} 推算（开始时刻 + 服务端给定的锁定时长），
 * 不另存时间戳，也不用发包。</p>
 */
public final class OrbitalScreenFX {

    /** 伪 hit-stop：落地帧白闪顶格、震动/慢摇都迟这 2 tick 才开始（先「停」后「炸」）。 */
    private static final int FREEZE_TICKS = 2;
    /** 落地白闪持续 tick（约 0.35 s：顶格 2 + 衰减 5）。 */
    private static final int FLASH_TICKS = 7;
    /** 白闪峰值不透明度。 */
    private static final float FLASH_ALPHA = 0.85F;
    /** 能量泛光持续 tick（约 2 s）—— 白闪管「炸的一瞬间」，泛光管「能量还在翻涌」。 */
    private static final int GLOW_TICKS = 40;
    /** 镜头震动持续 tick（从冻结结束后起算）。 */
    private static final int SHAKE_TICKS = 8;
    /** 镜头震动最大偏转角（度）。 */
    private static final float SHAKE_DEGREES = 2.2F;
    /** FOV 冲击：落地帧视野顿扩的度数。 */
    private static final float FOV_PUNCH_DEGREES = 13.0F;
    /** FOV 冲击的总时长（指数回弹的时间常数见实现）。 */
    private static final int FOV_PUNCH_TICKS = 12;
    /** 演出机位的长焦压缩：镜头拉出去的同时视野收窄几度（压扁空间、强调尺度）。 */
    private static final float CINEMATIC_FOV_DEGREES = 5.0F;
    /** 白闪/色晕/泛光/FOV 在多少格内全强度，多少格外消失。 */
    private static final double NEAR_RADIUS = 40.0D;
    private static final double FAR_RADIUS = 160.0D;
    /** 我们自己的识别色：天基武器的电青（与选区框同色）。 */
    private static final int HUD_CYAN = 0x9BF7FF;
    /** 白热芯：所有「正在烧」的东西都用它提亮。 */
    private static final int CORE_WHITE = 0xEAFEFF;

    private OrbitalScreenFX() {
    }

    /** 距离衰减：{@code NEAR_RADIUS} 内全强度，线性降到 {@code FAR_RADIUS} 外消失。 */
    private static float distanceFalloff(Minecraft minecraft) {
        double distance = OrbitalStrikeClientState.distanceToPlayer();
        return Mth.clamp((float) (1.0D - (distance - NEAR_RADIUS) / (FAR_RADIUS - NEAR_RADIUS)), 0.0F, 1.0F);
    }

    // ---------------------------------------------------------------- HUD

    /** 锁定阶段：屏幕中央上方的倒计时数字 + 屏幕四边色晕。挂在 {@code RenderGuiEvent.Post}。 */
    public static void renderHud(GuiGraphics graphics, Minecraft minecraft, float partialTick) {
        if (!OrbitalStrikeClientState.isActive() || !OrbitalStrikeClientState.isLockPhase()) {
            return;
        }
        if (minecraft.options.hideGui || minecraft.player == null) {
            return;
        }
        int width = graphics.guiWidth();
        int height = graphics.guiHeight();

        // —— 屏幕边缘脉冲（越接近落地越亮）
        float lockProgress = OrbitalStrikeClientState.lockProgress();
        float pulse = 0.55F + 0.45F * Mth.sin((minecraft.level.getGameTime() + partialTick) * 0.8F);
        float edgeAlpha = (0.10F + 0.20F * lockProgress) * pulse;
        int edgeColor = ((int) (edgeAlpha * 255.0F) << 24) | HUD_CYAN;
        int edgeWidth = Math.max(6, (int) (width * 0.06F));
        graphics.fill(0, 0, width, edgeWidth, edgeColor);                 // 上
        graphics.fill(0, height - edgeWidth, width, height, edgeColor);   // 下
        graphics.fill(0, 0, edgeWidth, height, edgeColor);                // 左
        graphics.fill(width - edgeWidth, 0, width, height, edgeColor);    // 右

        // —— 中央倒计时：剩余秒数（向上取整），3、2、1 大字
        long remaining = OrbitalStrikeClientState.lockTicks() - OrbitalStrikeClientState.elapsed();
        if (remaining < 0) {
            remaining = 0;
        }
        int seconds = (int) Math.ceil(remaining / 20.0D);
        if (seconds <= 0) {
            return;
        }
        String text = String.valueOf(seconds);
        PoseStack pose = graphics.pose();
        pose.pushPose();
        pose.translate(width / 2.0F, height * 0.28F, 0.0F);
        float scale = 4.0F;
        pose.scale(scale, scale, 1.0F);
        int textWidth = minecraft.font.width(text);
        // 数字颜色随倒计时从电青 → 白热：越接近 0 越亮（不是「越红越危险」，我们不用红色警告）
        float danger = 1.0F - Mth.clamp((float) remaining / Math.max(1, OrbitalStrikeClientState.lockTicks()), 0.0F, 1.0F);
        int r = (int) Mth.lerp(danger, 120.0F, 255.0F);
        int g = (int) Mth.lerp(danger, 235.0F, 255.0F);
        int b = (int) Mth.lerp(danger, 255.0F, 255.0F);
        int color = 0xFF000000 | (r << 16) | (g << 8) | b;
        graphics.drawString(minecraft.font, text, -textWidth / 2, 0, color, true);
        pose.popPose();
    }

    /**
     * 打击全程的「火控 HUD」：四角 L 括号 + 顶部「天陨-01」识别条 + 状态行 + 跟随轨道平台的
     * 屏幕准星标记（平台在视野外时钉在屏幕边缘）。挂在 {@code RenderGuiEvent.Post}。
     *
     * <p>投影是把相机到平台的方向量按相机朝向拆成右/上/前三轴、再用 FOV 归一 —— 纯数学，
     * 不依赖 render 事件的矩阵；FOV punch 带来的几度误差对 12px 的标记无所谓。</p>
     */
    public static void renderTargetingHud(GuiGraphics graphics, Minecraft minecraft, float partialTick) {
        // 用 isHudActive 而不是 isActive：宇宙激光的光柱要烧到虚空，HUD 不能陪跑几十秒
        if (!OrbitalStrikeClientState.isHudActive() || minecraft.options.hideGui || minecraft.player == null) {
            return;
        }
        float strength = distanceFalloff(minecraft);
        if (strength <= 0.0F) {
            return;
        }
        int width = graphics.guiWidth();
        int height = graphics.guiHeight();
        long elapsed = OrbitalStrikeClientState.elapsed();
        int lockTicks = OrbitalStrikeClientState.lockTicks();
        int fallTicks = OrbitalStrikeClientState.fallTicks();
        float pulse = 0.7F + 0.3F * Mth.sin((minecraft.level.getGameTime() + partialTick) * 0.8F);
        int alpha = (int) (strength * pulse * 255.0F);
        int cyan = (alpha << 24) | HUD_CYAN;
        int dimCyan = ((alpha * 2 / 3) << 24) | HUD_CYAN;

        // —— 四角 L 括号（原创火控框）
        int inset = 10;
        int len = 22;
        hudCorner(graphics, inset, inset, 1, 1, len, cyan);
        hudCorner(graphics, width - inset, inset, -1, 1, len, cyan);
        hudCorner(graphics, inset, height - inset, 1, -1, len, cyan);
        hudCorner(graphics, width - inset, height - inset, -1, -1, len, cyan);

        // —— 顶部识别条 + 状态行
        String status;
        int statusColor;
        if (elapsed < lockTicks) {
            status = String.format("锁定中 %02d%%", (int) (OrbitalStrikeClientState.lockProgress() * 100.0F));
            statusColor = cyan;
        } else if (elapsed < lockTicks + fallTicks) {
            status = "弹头坠落";
            statusColor = 0xFFFFFFFF;
        } else {
            status = "命中确认";
            statusColor = (alpha << 24) | CORE_WHITE;
        }
        OrbitalStrikeMode mode = OrbitalStrikeClientState.mode();
        StrikeProtocol protocol = StrikeProtocols.protocolFor(mode);
        boolean v2 = protocol.migrated();
        int protocolColor = (alpha << 24) | (protocol.color() & 0xFFFFFF);
        String callsign = v2 ? protocol.codename() : "天陨-01 · SKYFALL";
        graphics.drawString(minecraft.font, callsign,
                width / 2 - minecraft.font.width(callsign) / 2, inset + len + 6,
                v2 ? protocolColor : dimCyan, true);
        graphics.drawString(minecraft.font, status,
                width / 2 - minecraft.font.width(status) / 2, inset + len + 18, statusColor, true);
        // 当前弹种/协议：切换后立刻看得到（潜行右键循环）
        String modeLine = v2
                ? protocol.display() + " · " + protocol.phaseLabel(
                        protocol.phaseAt(elapsed, lockTicks, fallTicks))
                : mode.display() + " · " + mode.codename();
        graphics.drawString(minecraft.font, modeLine,
                width / 2 - minecraft.font.width(modeLine) / 2, inset + len + 30,
                v2 ? protocolColor : dimCyan, true);
        if (v2 && "swarm".equals(protocol.id())) {
            String warn = "警告：巢荚会唤醒尸群";
            graphics.drawString(minecraft.font, warn,
                    width / 2 - minecraft.font.width(warn) / 2, inset + len + 42,
                    (alpha << 24) | 0xB6FF9A, true);
        }
        // v2 电影：K 跳过提示（跳过后不再显示）
        if (v2 && OrbitalCinematic.isEngaged() && !OrbitalCinematic.isSkipped()) {
            String skip = "[K] SKIP // 跳过过场";
            graphics.drawString(minecraft.font, skip,
                    width - minecraft.font.width(skip) - 12, height - 16, 0xCCFFFFFF, true);
        }

        // 前摇进度条：锁定时在屏幕下三分之一处，一条会从左往右填满的细条。
        // 7 秒的前摇光靠数字倒计时太干，给一条「能量正在灌进去」的读数。
        if (elapsed < lockTicks) {
            float progress = OrbitalStrikeClientState.lockProgress();
            int barW = Math.min(220, width / 3);
            int barH = 4;
            int bx = (width - barW) / 2;
            int by = height - 44;
            int frame = (alpha / 2) << 24;
            safeFill(graphics, bx - 1, by - 1, bx + barW + 1, by + barH + 1, frame | 0x0A2A33);
            int filled = (int) (barW * progress);
            if (filled > 0) {
                safeFill(graphics, bx, by, bx + filled, by + barH, cyan);
            }
            // 进度头部一个亮点，读起来像「正在推进」
            if (filled > 2) {
                safeFill(graphics, bx + filled - 2, by - 1, bx + filled, by + barH + 1,
                        (alpha << 24) | CORE_WHITE);
            }
        }

        // —— 跟随轨道平台的准星标记
        drawSatelliteMarker(graphics, minecraft, partialTick, width, height, cyan, dimCyan);
    }

    private static void drawSatelliteMarker(GuiGraphics graphics, Minecraft minecraft, float partialTick,
                                            int width, int height, int cyan, int dimCyan) {
        BlockPos target = OrbitalStrikeClientState.target();
        if (target == null) {
            return;
        }
        // 太空舞台里的卫星是按相机相对坐标画的，屏幕上本来就看得到；
        // 再按世界坐标投一个角框会指到画面外去，反而穿帮。
        if (OrbitalCinematic.isSpaceStage()) {
            return;
        }
        Vec3 satellite = new Vec3(target.getX() + 0.5D, 320.0D + 6.0D, target.getZ() + 0.5D);
        Camera camera = minecraft.gameRenderer.getMainCamera();
        Vec3 eye = camera.getPosition();
        double dx = satellite.x - eye.x;
        double dy = satellite.y - eye.y;
        double dz = satellite.z - eye.z;
        float yawRad = (float) Math.toRadians(camera.getYRot());
        float pitchRad = (float) Math.toRadians(camera.getXRot());
        float sy = Mth.sin(yawRad);
        float cy = Mth.cos(yawRad);
        float sp = Mth.sin(pitchRad);
        float cp = Mth.cos(pitchRad);
        // 相机三轴（Minecraft yaw：0 = 朝 +Z、顺时针增；roll 恒 0）
        double fx = -sy * cp;
        double fy = -sp;
        double fz = cy * cp;
        double rx = -cy;
        double rz = -sy;
        double ux = -sy * sp;
        double uy = cp;
        double uz = cy * sp;
        double depth = dx * fx + dy * fy + dz * fz;
        double camX = dx * rx + dz * rz;
        double camY = dx * ux + dy * uy + dz * uz;
        int px;
        int py;
        boolean onScreen = depth > 0.1D;
        if (onScreen) {
            float fovDeg = minecraft.options.fov().get().floatValue();
            double tanHalf = Math.tan(Math.toRadians(fovDeg) / 2.0D);
            double aspect = width / (double) height;
            double ndcX = camX / (depth * tanHalf * aspect);
            double ndcY = camY / (depth * tanHalf);
            px = (int) ((ndcX + 1.0D) * 0.5D * width);
            py = (int) ((1.0D - ndcY) * 0.5D * height);
            onScreen = px > 14 && px < width - 14 && py > 14 && py < height - 14;
        } else {
            // 相机背后：按相机空间水平分量贴到左/右边缘中点
            px = camX >= 0.0D ? width - 22 : 22;
            py = height / 2;
        }
        if (!onScreen) {
            // 边缘钉一个小点就行 —— 不抢戏
            graphics.fill(px - 1, py - 1, px + 1, py + 1, dimCyan);
            return;
        }
        // 括号准星（四角）
        int half = 6;
        int arm = 3;
        hudCorner(graphics, px - half, py - half, 1, 1, arm, cyan);
        hudCorner(graphics, px + half, py - half, -1, 1, arm, cyan);
        hudCorner(graphics, px - half, py + half, 1, -1, arm, cyan);
        hudCorner(graphics, px + half, py + half, -1, -1, arm, cyan);
        String label = "天陨-01";
        graphics.drawString(minecraft.font, label,
                px - minecraft.font.width(label) / 2, py - half - 12, cyan, true);
    }

    /** HUD 角上的 L 括号：横臂 + 竖臂，方向由 (dx, dy) 决定。 */
    private static void hudCorner(GuiGraphics graphics, int x, int y, int dx, int dy, int len, int color) {
        safeFill(graphics, x, y, x + dx * len, y + dy * 2, color);
        safeFill(graphics, x, y, x + dx * 2, y + dy * len, color);
    }

    /** fill 的坐标顺序安全版（负方向臂不会画出空矩形）。 */
    private static void safeFill(GuiGraphics graphics, int x1, int y1, int x2, int y2, int color) {
        graphics.fill(Math.min(x1, x2), Math.min(y1, y2), Math.max(x1, x2), Math.max(y1, y2), color);
    }

    /**
     * 落地后的「能量泛光」：全屏淡青白渐隐 + 四边更亮的边条（不写 shader 的
     * bloom 替代 —— 屏幕边缘叠亮色，观感是画面在发光）。与 {@link #renderImpactFlash}
     * 一起挂在 {@code RenderGuiEvent.Post}，泛光先画（更暗的一层），白闪后画（最亮）。
     */
    public static void renderImpactGlow(GuiGraphics graphics, Minecraft minecraft) {
        if (!OrbitalStrikeClientState.isActive()) {
            return;
        }
        long impactAge = OrbitalStrikeClientState.impactAge();
        if (impactAge < 0 || impactAge >= GLOW_TICKS) {
            return;
        }
        if (minecraft.options.hideGui || minecraft.player == null) {
            return;
        }
        float falloff = distanceFalloff(minecraft);
        if (falloff <= 0.0F) {
            return;
        }
        float t = 1.0F - (float) impactAge / GLOW_TICKS;
        // 「涌」的感觉：正弦呼吸叠在线性衰减上，能量不是线性熄灭
        float breathe = (0.8F + 0.2F * Mth.sin(t * Mth.PI)) * t;
        int base = (int) (80.0F * falloff * breathe * 255.0F);
        if (base <= 0) {
            return;
        }
        int w = graphics.guiWidth();
        int h = graphics.guiHeight();
        int rgb = HUD_CYAN;
        // 全屏淡青白
        graphics.fill(0, 0, w, h, (base << 24) | rgb);
        // 四边更亮：屏幕边缘泛光
        int edge = Math.min(255, (int) (base * 1.9F));
        int bandH = (int) (h * 0.14F);
        int bandW = (int) (w * 0.04F);
        graphics.fill(0, 0, w, bandH, (edge << 24) | rgb);
        graphics.fill(0, h - bandH, w, h, (edge << 24) | rgb);
        graphics.fill(0, 0, bandW, h, (edge << 24) | rgb);
        graphics.fill(w - bandW, 0, w, h, (edge << 24) | rgb);
    }

    /**
     * 落地瞬间的全屏白闪。伪 hit-stop：先顶格 {@link #FREEZE_TICKS}（画面「停」住），
     * 再快速衰减 —— 与镜头慢摇冻结同步，先「停」后「炸」。挂在 {@code RenderGuiEvent.Post}。
     *
     * <p>三层同心矩形近似径向渐变：最外一圈带一点电青，中心是纯白热 —— 白闪也守我们的色板。</p>
     */
    public static void renderImpactFlash(GuiGraphics graphics, Minecraft minecraft) {
        if (!OrbitalStrikeClientState.isActive()) {
            return;
        }
        long impactAge = OrbitalStrikeClientState.impactAge();
        if (impactAge < 0 || impactAge >= FLASH_TICKS) {
            return;
        }
        if (minecraft.options.hideGui || minecraft.player == null) {
            return;
        }
        // 距离越远越弱：远处只看到一点白光，近处直接糊脸
        float falloff = distanceFalloff(minecraft);
        if (falloff <= 0.0F) {
            return;
        }
        // 冻结期满 alpha，随后线性衰减到 0
        float t = impactAge < FREEZE_TICKS
                ? 1.0F
                : 1.0F - (float) (impactAge - FREEZE_TICKS) / (FLASH_TICKS - FREEZE_TICKS);
        int alpha = (int) (FLASH_ALPHA * falloff * t * 255.0F);
        if (alpha <= 0) {
            return;
        }
        int w = graphics.guiWidth();
        int h = graphics.guiHeight();
        graphics.fill(0, 0, w, h, ((int) (alpha * 0.45F) << 24) | HUD_CYAN);
        int half1 = (int) (alpha * 0.7F);
        safeFill(graphics, w / 4, h / 4, w * 3 / 4, h * 3 / 4, (half1 << 24) | CORE_WHITE);
        safeFill(graphics, w * 3 / 8, h * 3 / 8, w * 5 / 8, h * 5 / 8, (alpha << 24) | 0xFFFFFF);
    }

    /**
     * 手持遥控器时的常驻模式提示：当前弹种 + （潜行时）「右键切到下一个」。
     * 没有这条提示，四种模式只能靠背包里的 tooltip 才发现。
     */
    public static void renderModeHint(GuiGraphics graphics, Minecraft minecraft) {
        if (!Config.ORBITAL_STRIKE_ENABLED.get() || minecraft.options.hideGui || minecraft.player == null) {
            return;
        }
        // 打击进行中：顶部 HUD 已经在显示模式名了，不要重复（用短窗口，光柱烧井时不挡视野）
        if (OrbitalStrikeClientState.isHudActive()) {
            return;
        }
        ItemStack main = minecraft.player.getMainHandItem();
        if (!(main.getItem() instanceof OrbitalStrikeRemoteItem)) {
            return;
        }
        OrbitalStrikeMode mode = OrbitalStrikeRemoteItem.getMode(main);
        int width = graphics.guiWidth();
        int height = graphics.guiHeight();
        String line = mode.display() + " · " + mode.codename();
        graphics.drawString(minecraft.font, line,
                width / 2 - minecraft.font.width(line) / 2, height - 62, HUD_CYAN, true);
        if (minecraft.player.isShiftKeyDown() && Config.ORBITAL_STRIKE_ALLOW_MODE_SWITCH.get()) {
            String hint = "右键 → " + mode.next().display();
            graphics.drawString(minecraft.font, hint,
                    width / 2 - minecraft.font.width(hint) / 2, height - 74, 0xFF6FC7D8, true);
        }
    }

    /**
     * 穿大气层转场：升空时屏幕边缘泛蓝 + 竖直速度线；返回时一层暖蓝闪光。
     * 画在所有 HUD/黑边之前（最底层），不抢火控读数。
     */
    public static void renderSpaceTransition(GuiGraphics graphics, Minecraft minecraft, float partialTick) {
        if (!Config.ORBITAL_STRIKE_CINEMATIC.get() || !OrbitalStrikeClientState.isActive()) {
            return;
        }
        if (minecraft.options.hideGui || minecraft.player == null) {
            return;
        }
        long elapsed = OrbitalStrikeClientState.elapsed();
        int lock = OrbitalStrikeClientState.lockTicks();
        int fall = OrbitalStrikeClientState.fallTicks();
        double start = OrbitalCinematic.ascentStartTicks();
        double ascent = OrbitalCinematic.ascentTicks();
        double impact = lock + fall;
        int w = graphics.guiWidth();
        int h = graphics.guiHeight();
        // —— 升空：蓝色大气边缘 + 速度线，强度先增后减
        if (elapsed >= start && elapsed <= start + ascent + 4.0D) {
            float p = Mth.clamp((float) ((elapsed - start) / Math.max(1.0D, ascent)),
                    0.0F, 1.0F);
            float a = (float) Math.sin(p * Math.PI) * 0.34F;
            int edge = ((int) (a * 255.0F) << 24) | 0x6FC7FF;
            int band = (int) (h * 0.20F);
            graphics.fill(0, 0, w, band, edge);
            graphics.fill(0, h - band, w, h, edge);
            graphics.fill(0, 0, w, h, ((int) (a * 0.30F * 255.0F) << 24) | 0x3A7FBF);
            long t = minecraft.level == null ? 0L : minecraft.level.getGameTime();
            int streak = ((int) (a * 150.0F) << 24) | 0xCFEFFF;
            for (int i = 0; i < 36; i++) {
                int x = (int) ((i * 97L + t * 3L) % Math.max(1, w));
                int len = 24 + (i * 13) % 56;
                int y = (int) ((i * 211L + t * 7L) % (h + len)) - len;
                graphics.fill(x, y, x + 1, y + len, streak);
            }
        }
        // —— 返回：进入大气层的暖色闪光，快速衰减
        double entry = impact + OrbitalCinematic.spaceHoldTicks();
        if (elapsed >= entry - 4.0D && elapsed <= entry + 22.0D) {
            float q = Mth.clamp((float) ((elapsed - (entry - 4.0D)) / 26.0F), 0.0F, 1.0F);
            float a = (1.0F - q) * 0.42F;
            graphics.fill(0, 0, w, h, ((int) (a * 255.0F) << 24) | 0xFFB36B);
            int edge = ((int) (a * 0.8F * 255.0F) << 24) | 0xFFD9A8;
            int band = (int) (h * 0.16F);
            graphics.fill(0, 0, w, band, edge);
            graphics.fill(0, h - band, w, h, edge);
        }
    }

    /**
     * 演出黑边：随「见证机位」权重升起的上下黑条（宽银幕）。参考 mod 的过场感来源 ——
     * 画面被压成一条横幅，观众的注意力自动聚焦到中间那一击。
     *
     * <p>只在 {@code orbital_strike.cinematic} 打开时出现（关掉演出的人也不会被黑边挡住视野）。
     * 画在所有 HUD 之前，火控角框与白闪都叠在黑边之上。</p>
     */
    public static void renderCinematicBars(GuiGraphics graphics, Minecraft minecraft) {
        if (!Config.ORBITAL_STRIKE_CINEMATIC.get() || minecraft.options.hideGui) {
            return;
        }
        if (OrbitalCinematic.isSkipped()) {
            return;
        }
        float weight = OrbitalCinematic.weight();
        if (weight <= 0.02F) {
            return;
        }
        int width = graphics.guiWidth();
        int height = graphics.guiHeight();
        int bar = (int) (height * 0.105F * weight);
        if (bar <= 0) {
            return;
        }
        int black = ((int) (255.0F * Mth.clamp(weight, 0.0F, 1.0F)) << 24);
        graphics.fill(0, 0, width, bar, black);
        graphics.fill(0, height - bar, width, height, black);
    }

    // ---------------------------------------------------------------- 镜头

    /**
     * 落地瞬间把镜头轻微抖一下。挂在 {@code ViewportEvent.ComputeCameraAngles}。
     *
     * <p>用正弦 + 随机相位的组合（而不是纯随机）—— 纯随机每帧跳，观感是「画面失灵」；
     * 正弦衰减更像一次真实冲击的余震。1.8.0：震动从伪 hit-stop 冻结结束后才起。</p>
     */
    public static void shakeCamera(ViewportEvent.ComputeCameraAngles event, Minecraft minecraft) {
        if (!OrbitalStrikeClientState.isActive()) {
            return;
        }
        long impactAge = OrbitalStrikeClientState.impactAge();
        if (impactAge < FREEZE_TICKS || impactAge >= SHAKE_TICKS) {
            return;
        }
        if (minecraft.player == null) {
            return;
        }
        float falloff = distanceFalloff(minecraft);
        if (falloff <= 0.0F) {
            return;
        }
        // 衰减包络：从 1 降到 0
        float envelope = 1.0F - (float) (impactAge - FREEZE_TICKS) / (SHAKE_TICKS - FREEZE_TICKS);
        float phase = (float) (minecraft.level.getGameTime() + event.getPartialTick()) * 1.3F;
        float amp = SHAKE_DEGREES * falloff * envelope;
        event.setYaw(event.getYaw() + Mth.sin(phase) * amp);
        event.setPitch(event.getPitch() + Mth.cos(phase * 1.7F) * amp * 0.7F);
        event.setRoll(event.getRoll() + Mth.sin(phase * 2.3F) * amp * 0.5F);
    }

    /**
     * FOV 冲击：落地帧视野骤然扩张再指数回弹（重击反馈的标配 punch）。
     * 挂在 {@code ViewportEvent.ComputeFov}，与瞄准变焦互不覆盖（都只往自己的方向加）。
     *
     * <p>另有演出机位的长焦压缩：镜头在外面时视野收窄 {@link #CINEMATIC_FOV_DEGREES}°，
     * 落地那一下再被 punch 顶开 —— 「收 → 炸」的对比比单纯的 FOV 冲击更响。</p>
     */
    public static void impactFovPunch(ViewportEvent.ComputeFov event, Minecraft minecraft) {
        if (!event.usedConfiguredFov()) {
            return;
        }
        float weight = OrbitalCinematic.weight();
        if (weight > 0.001F) {
            event.setFOV(event.getFOV() - CINEMATIC_FOV_DEGREES * weight);
        }
        if (!OrbitalStrikeClientState.isActive()) {
            return;
        }
        long impactAge = OrbitalStrikeClientState.impactAge();
        if (impactAge < 0 || impactAge >= FOV_PUNCH_TICKS) {
            return;
        }
        if (minecraft.player == null) {
            return;
        }
        float falloff = distanceFalloff(minecraft);
        if (falloff <= 0.0F) {
            return;
        }
        float envelope = (float) Math.exp(-impactAge / 4.5D);
        event.setFOV(event.getFOV() + FOV_PUNCH_DEGREES * falloff * envelope);
    }
}
