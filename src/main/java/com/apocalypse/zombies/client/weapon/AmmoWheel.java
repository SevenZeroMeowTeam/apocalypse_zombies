package com.apocalypse.zombies.client.weapon;

import com.apocalypse.zombies.client.KeyBindings;
import com.apocalypse.zombies.item.AmmoType;
import com.apocalypse.zombies.item.GunItem;
import com.apocalypse.zombies.network.NetworkHandler;
import com.apocalypse.zombies.network.ReloadPacket;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.network.chat.Component;
import net.minecraft.world.item.ItemStack;

import java.util.List;

/**
 * 按住 {@code R} 弹出的弹种轮盘。
 *
 * <h2>交互</h2>
 * 按下弹轮盘、松开装填 —— 中途把光标移回中心（或按 Esc 关掉界面）就等于放弃。轮盘打开时会
 * <b>释放鼠标</b>：不释放的话光标被锁在准心上，玩家根本指不了方向；代价是这几百毫秒里转不了视角，
 * 而那正好是选弹时不该做的事。
 *
 * <h2>为什么取消的点选要回到"普通弹"</h2>
 * 光标停在中心附近时 {@link #selected} 保持不动（不跳选项），但松开时如果从没离开过死区，
 * 发出去的仍然是当前高亮那个 —— 于是"按住 R 直接松"等于"装枪上原本那种弹"，也就是这次改动之前
 * R 键的行为。习惯不用改。
 */
public final class AmmoWheel {

    /** 光标离屏幕中心多近算"没在选"。 */
    private static final double DEAD_ZONE = 10.0D;
    /** 标签环半径，占屏幕短边的比例。 */
    private static final float RADIUS_FRACTION = 0.17F;
    private static final int LABEL_W = 48;
    private static final int LABEL_H = 11;

    private static final int BACKDROP = 0x90101014;
    private static final int LABEL_BG = 0xC0202024;
    private static final int LABEL_BG_SELECTED = 0xF0E8B33C;
    private static final int TEXT = 0xFFE0E0E0;
    private static final int TEXT_SELECTED = 0xFF101014;
    private static final int HINT = 0xFFB0B0B0;

    private static boolean open;
    private static int selected;
    /** 我们释放过鼠标，关的时候要还回去。 */
    private static boolean released;
    /** 打开那一刻这把枪能装哪些弹 —— 中途切枪不重算，免得选项在光标底下变。 */
    private static List<AmmoType> options = List.of();
    private static String hint = "";

    private AmmoWheel() {
    }

    public static boolean isOpen() {
        return open;
    }

    /** 每 client tick 一次：管住 R 的按下 / 松开，以及光标指向哪个选项。 */
    public static void tick(Minecraft minecraft) {
        LocalPlayer player = minecraft.player;
        ItemStack stack = player == null ? ItemStack.EMPTY : player.getMainHandItem();
        GunItem gun = stack.getItem() instanceof GunItem g ? g : null;

        // 打开条件：手里是我们的枪、没开别的界面、R 真的被按住
        boolean holding = gun != null && minecraft.screen == null && KeyBindings.RELOAD.isDown();

        if (holding && !open) {
            open(minecraft, gun, stack);
        } else if (!holding && open) {
            // 松开 = 确认。发出去以后由服务端裁决能不能装（可能正忙、可能已经满了）。
            AmmoType chosen = options.isEmpty() ? AmmoType.STANDARD : options.get(selected);
            NetworkHandler.CHANNEL.sendToServer(
                    new ReloadPacket(minecraft.options.keyShift.isDown(), chosen.id()));
            dismiss(minecraft);
            return;
        }

        if (open) {
            updateSelection(minecraft);
        }
    }

    private static void open(Minecraft minecraft, GunItem gun, ItemStack stack) {
        options = List.copyOf(gun.ammoTypes(stack));
        AmmoType current = gun.currentAmmo(stack);
        // 打开时高亮膛里已经在用的那一种：这样"按住 R 再松开"装的是同一种弹，不会手滑换掉。
        selected = Math.max(0, options.indexOf(current));
        hint = Component.translatable("wheel.apocalypse_zombies.hint").getString();
        open = true;
        released = false;
        // 释放鼠标，让光标能指方向。已经释放（比如刚关过界面）就别再动它。
        if (minecraft.mouseHandler.isMouseGrabbed()) {
            minecraft.mouseHandler.releaseMouse();
            released = true;
        }
    }

    /** 关掉轮盘并（必要时）把鼠标还给相机。 */
    public static void dismiss(Minecraft minecraft) {
        if (!open) {
            return;
        }
        open = false;
        options = List.of();
        if (released && !minecraft.mouseHandler.isMouseGrabbed()) {
            minecraft.mouseHandler.grabMouse();
        }
        released = false;
    }

    private static void updateSelection(Minecraft minecraft) {
        int count = options.size();
        if (count <= 1) {
            selected = 0;
            return;
        }
        double cx = minecraft.getWindow().getScreenWidth() / 2.0D;
        double cy = minecraft.getWindow().getScreenHeight() / 2.0D;
        double dx = minecraft.mouseHandler.xpos() - cx;
        double dy = cy - minecraft.mouseHandler.ypos();     // 屏幕 y 向下 → 数学 y 向上
        if (Math.hypot(dx, dy) < DEAD_ZONE) {
            return;                                          // 死区里保持当前高亮不跳
        }
        // 从正上方开始顺时针排：光标在上 = 第 0 项，右 = 第 1 项，依此类推。
        double theta = Math.atan2(dy, dx);
        double slice = Math.PI * 2.0D / count;
        double fromTop = (Math.PI / 2.0D - theta) / slice;
        selected = Math.floorMod((int) Math.round(fromTop), count);
    }

    /** 画在 HUD 上（由 ClientEvents 在 GUI overlay 的 Post 阶段调）。 */
    public static void render(GuiGraphics graphics, Minecraft minecraft) {
        if (!open || options.isEmpty()) {
            return;
        }
        int width = graphics.guiWidth();
        int height = graphics.guiHeight();
        double cx = width / 2.0D;
        double cy = height / 2.0D;
        double radius = Math.min(width, height) * RADIUS_FRACTION;
        int count = options.size();

        // 中心到准星之间压一层底，免得轮盘贴在明亮的地形上看不清
        graphics.fill((int) cx - 150, (int) cy - 70, (int) cx + 150, (int) cy + 70, BACKDROP);

        for (int i = 0; i < count; i++) {
            double angle = -Math.PI / 2.0D + i * (Math.PI * 2.0D / count);
            int x = (int) Math.round(cx + Math.cos(angle) * radius);
            int y = (int) Math.round(cy - Math.sin(angle) * radius);
            boolean picked = i == selected;

            int bg = picked ? LABEL_BG_SELECTED : LABEL_BG;
            int fg = picked ? TEXT_SELECTED : TEXT;
            graphics.fill(x - LABEL_W, y - LABEL_H, x + LABEL_W, y + LABEL_H, bg);

            AmmoType ammo = options.get(i);
            Component name = Component.translatable("ammo.apocalypse_zombies." + ammo.id());
            graphics.drawCenteredString(minecraft.font, name, x, y - 8, fg);
            Component detail = Component.translatable("ammo.apocalypse_zombies." + ammo.id() + ".tip");
            graphics.drawCenteredString(minecraft.font, detail, x, y + 3, fg);
        }

        // 中心一行小字：提示怎么操作，以及现在会装哪一种
        AmmoType chosen = options.get(Math.min(selected, options.size() - 1));
        Component centre = Component.translatable("wheel.apocalypse_zombies.selected",
                Component.translatable("ammo.apocalypse_zombies." + chosen.id()));
        graphics.drawCenteredString(minecraft.font, centre, (int) cx, (int) cy - 4, TEXT);
        graphics.drawCenteredString(minecraft.font, hint, (int) cx, (int) cy + height / 2 - 24, HINT);
    }
}
