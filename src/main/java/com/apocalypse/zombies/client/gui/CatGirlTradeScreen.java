package com.apocalypse.zombies.client.gui;

import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.network.chat.Component;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.item.ItemStack;

import com.apocalypse.zombies.entity.CatGirlEntity;
import com.apocalypse.zombies.entity.menu.CatGirlTradeMenu;

/**
 * 猫耳娘交易界面。
 *
 * <p>不挂 GUI 贴图，背景与槽框全部用 {@code fill()} 现画 —— 这是一张布局独有的菜单，
 * 为它养一张 176×166 的 PNG 不如把坐标写进代码里，改布局时也没有「贴图对不上槽位」
 * 的暗坑。</p>
 *
 * <p>她的库存按玩家同款排布显示：上面三行是背包（27 格，槽位 9–35），
 * 隔一条细线，最下面一行是物品栏（9 格，槽位 0–8）。</p>
 *
 * <p>价格标注（库存格右下角的金字）是<b>客户端本地按配置算的预估值</b>：
 * 实价以服务端点击结算为准（专用服务器上若两端配置不同，以服务器为准）。</p>
 */
public class CatGirlTradeScreen extends net.minecraft.client.gui.screens.inventory.AbstractContainerScreen<CatGirlTradeMenu> {

    /** 面板配色：粉白底、暖灰边、槽位浅灰。 */
    private static final int PANEL_BORDER = 0xFFCBADC2;
    private static final int PANEL_FILL = 0xFFF7EEF4;
    private static final int PANEL_INNER = 0xFFFDF9FB;
    private static final int SLOT_FRAME = 0xFFB9A7B6;
    private static final int SLOT_FILL = 0xFFE9DDE6;
    private static final int LABEL_DARK = 0xFF5C4A57;
    private static final int PRICE_GOLD = 0xFFC08A2E;

    public CatGirlTradeScreen(CatGirlTradeMenu menu, Inventory inventory, Component title) {
        super(menu, inventory, title);
        this.imageWidth = 176;
        // 面板只包她自己的部分（交易行 / 她的库存 / 底部快捷栏），玩家的 27 格不在这块面板里。
        this.imageHeight = CatGirlTradeMenu.PANEL_HEIGHT;
        // 玩家背包标题也挪出可视区：槽位已经藏在面板外，标题不该飘在别人的界面上。
        this.inventoryLabelY = 10000;
    }

    @Override
    protected void renderBg(GuiGraphics guiGraphics, float partialTick, int mouseX, int mouseY) {
        int x = this.leftPos;
        int y = this.topPos;
        // 外框 + 内衬
        guiGraphics.fill(x - 1, y - 1, x + this.imageWidth + 1, y + this.imageHeight + 1, PANEL_BORDER);
        guiGraphics.fill(x, y, x + this.imageWidth, y + this.imageHeight, PANEL_FILL);
        guiGraphics.fill(x + 5, y + 16, x + this.imageWidth - 5, y + 74, PANEL_INNER);
        // 分隔线
        guiGraphics.fill(x + 5, y + 76, x + this.imageWidth - 5, y + 77, PANEL_BORDER);
        // 她的「背包 27」与「物品栏 9」之间那条细线：和原版玩家背包 + 快捷栏的分组感一致
        guiGraphics.fill(x + 5, y + CatGirlTradeMenu.GOODS_HOTBAR_Y - 3,
                x + this.imageWidth - 5, y + CatGirlTradeMenu.GOODS_HOTBAR_Y - 2, PANEL_BORDER);
        // 交易行 / 她的库存 / 玩家快捷栏 的槽位框
        for (net.minecraft.world.inventory.Slot slot : this.menu.slots) {
            if (slot.y >= this.imageHeight) {
                continue; // 面板外的槽（玩家的 27 格）不画
            }
            guiGraphics.fill(x + slot.x - 1, y + slot.y - 1, x + slot.x + 17, y + slot.y + 17, SLOT_FRAME);
            guiGraphics.fill(x + slot.x, y + slot.y, x + slot.x + 16, y + slot.y + 16, SLOT_FILL);
        }
        // 给予 → 回报 的箭头
        int arrowY = y + 20;
        guiGraphics.fill(x + 52, arrowY + 7, x + 74, arrowY + 9, LABEL_DARK);
        guiGraphics.fill(x + 68, arrowY + 4, x + 71, arrowY + 12, LABEL_DARK);
        guiGraphics.fill(x + 71, arrowY + 6, x + 74, arrowY + 10, LABEL_DARK);
    }

    @Override
    protected void renderLabels(GuiGraphics guiGraphics, int mouseX, int mouseY) {
        guiGraphics.drawString(this.font, this.title, 8, 6, LABEL_DARK, false);
        guiGraphics.drawString(this.font, Component.translatable("cat_girl.trade.give"), 22, 42, LABEL_DARK, false);
        guiGraphics.drawString(this.font, Component.translatable("cat_girl.trade.reward"), 76, 42, LABEL_DARK, false);
        guiGraphics.drawString(this.font, Component.translatable("cat_girl.trade.stock",
                CatGirlEntity.GOODS_BACKPACK, CatGirlEntity.GOODS_HOTBAR),
                CatGirlTradeMenu.goodsSlotX(0), 104, LABEL_DARK, false);
        guiGraphics.drawString(this.font, Component.translatable("cat_girl.trade.order"), 128, 80, LABEL_DARK, false);
        guiGraphics.drawString(this.font, Component.translatable("cat_girl.trade.order_fee",
                this.menu.getCraftFee()), 128, 100, PRICE_GOLD, false);

        // 库存价格：按价值 × 数量，压在格子右下角（一格里画 36 行标签没地方放，金字带阴影压在物品上最省地方）
        CatGirlEntity cat = this.menu.getCatGirl();
        if (cat != null) {
            for (int i = 0; i < CatGirlTradeMenu.GOODS_COUNT; i++) {
                ItemStack stack = cat.getGoods().getItem(i);
                if (stack.isEmpty()) {
                    continue;
                }
                int price = Math.max(1, CatGirlEntity.coinValue(stack) * stack.getCount());
                String text = String.valueOf(price);
                int slotX = CatGirlTradeMenu.goodsSlotX(i);
                int slotY = CatGirlTradeMenu.goodsSlotY(i);
                guiGraphics.drawString(this.font, text, slotX + 16 - this.font.width(text), slotY + 9, PRICE_GOLD, true);
            }
        }
    }
}
