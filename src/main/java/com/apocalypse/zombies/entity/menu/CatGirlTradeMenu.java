package com.apocalypse.zombies.entity.menu;

import net.minecraft.network.chat.Component;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.Container;
import net.minecraft.world.SimpleContainer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.AbstractContainerMenu;
import net.minecraft.world.inventory.ClickType;
import net.minecraft.world.inventory.ResultContainer;
import net.minecraft.world.inventory.ResultSlot;
import net.minecraft.world.inventory.Slot;
import net.minecraft.world.inventory.TransientCraftingContainer;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.crafting.CraftingRecipe;
import net.minecraft.world.item.crafting.RecipeType;
import net.minecraft.world.item.enchantment.EnchantmentHelper;
import net.minecraft.world.level.Level;

import com.mojang.logging.LogUtils;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.CatGirlCrafting;
import com.apocalypse.zombies.entity.CatGirlEntity;

import static com.apocalypse.zombies.entity.CatGirlEntity.GOODS_BACKPACK;
import com.apocalypse.zombies.registry.ModItems;
import com.apocalypse.zombies.registry.ModMenus;
import org.slf4j.Logger;

/**
 * 猫耳娘的工作台菜单：出售 / 附魔 / 合成 / 购买，四个区域一张界面。
 *
 * <ul>
 *   <li><b>出售</b>：给予格放任意物品（含模组物品，爱心币除外）→ 回报格出等值爱心币。</li>
 *   <li><b>附魔</b>：物品格放一件可附魔的物品 → 附魔格给出随机的适用附魔版本，
 *       取走时扣 {@link Config#CAT_GIRL_ENCHANT_COST} 枚爱心币。
 *       结果只在她那里「重掷」一次并缓存，直到物品格内容变化 —— 否则菜单每 tick
 *       重算会让附魔在格子里疯狂跳变。</li>
 *   <li><b>合成</b>：标准 3×3 配方网格 + 结果格，走原版 {@code RecipeManager}，
 *       所以<b>模组配方照样能合</b>（数据驱动，不需要知道任何具体配方）。</li>
 *   <li><b>购买</b>：她伐木挖矿攒下的库存，用爱心币买走。槽位本体不可拾取，
 *       购买在 {@link #clicked} 里由服务端结算。</li>
 * </ul>
 *
 * <p>输入格与合成网格里的东西在关界面时全部还回玩家（含附魔格）—— 界面关掉就吞东西
 * 是最容易挨骂的 bug，服务端与客户端各执行一次同一段 {@code clearContainer} 是原版做法。</p>
 */
public class CatGirlTradeMenu extends AbstractContainerMenu {

    public static final int SELL_INPUT = 0;
    public static final int SELL_RESULT = 1;
    public static final int ENCHANT_INPUT = 2;
    public static final int ENCHANT_RESULT = 3;
    public static final int CRAFT_START = 4;
    public static final int CRAFT_COUNT = 9;
    public static final int CRAFT_RESULT = CRAFT_START + CRAFT_COUNT;
    public static final int GOODS_START = CRAFT_RESULT + 1;
    /** 面板高度（只有她的部分）：界面底部落在快捷栏那一行下面。 */
    public static final int PANEL_HEIGHT = 226;

    /** 她的库存第一行（背包第一行）的 y。 */
    public static final int GOODS_Y = 114;

    /** 一行 9 格的间距。 */
    public static final int SLOT_PITCH = 18;

    /**
     * 玩家背包 27 格的 y —— 面板外（10000 = 屏幕外）：
     * 这个界面按需求「只显示她自己的东西」，玩家那 27 格槽位仍然注册着、shift 搬货照常可用，
     * 只是不画在面板里。玩家只剩底部快捷栏那一行留在面板里给「给予格 / 合成网格」供料。
     */
    public static final int PLAYER_ROW_Y = 10000;

    /** 她的物品栏（快捷栏）那一行的 y：背包 3 行下留 4px，与原版背包同款。 */
    public static final int GOODS_HOTBAR_Y = GOODS_Y + GOODS_BACKPACK / 9 * SLOT_PITCH + 4;

    /** 玩家快捷栏那一行在面板里的 y：她那一行下面留 4px，两排快捷栏不贴在一起。 */
    public static final int HOTBAR_Y = GOODS_HOTBAR_Y + SLOT_PITCH + 4;

    public static final int GOODS_COUNT = CatGirlEntity.GOODS_SIZE;

    /**
     * 她库存第 i 格在面板里的坐标：0–8 是物品栏（最下面一行），9–35 是背包（上面三行）。
     * 菜单坐标与界面坐标必须同源，所以这里只留这一份算法，界面直接调它。
     */
    public static int goodsSlotX(int index) {
        return 8 + (index % 9) * SLOT_PITCH;
    }

    /** 见 {@link #goodsSlotX}：物品栏在最后一行（原版玩家的快捷栏在底部）。 */
    public static int goodsSlotY(int index) {
        if (index < CatGirlEntity.GOODS_HOTBAR) {
            return GOODS_HOTBAR_Y;
        }
        return GOODS_Y + (index - CatGirlEntity.GOODS_HOTBAR) / 9 * SLOT_PITCH;
    }
    public static final int PLAYER_START = GOODS_START + GOODS_COUNT;

    /** 附魔等级（等效于附魔台 20 级投入）。 */
    private static final int ENCHANT_LEVEL = 20;

    private final CatGirlEntity catGirl;
    private final Player player;

    private final Container sellInput = new SimpleContainer(1);
    private final Container sellResult = new SimpleContainer(1);
    private final Container enchantInput = new SimpleContainer(1);
    /** 下单：放一件样品，她照这个做（材料用她的、手续费扣你的爱心币）。 */
    private final Container orderInput = new SimpleContainer(1);
    private final Container orderResult = new SimpleContainer(1);
    /** 上次给她报过的原因，避免每 tick 刷屏。 */
    private String lastOrderHint = "";
    private final Container enchantResult = new SimpleContainer(1);
    private static final Logger LOGGER = LogUtils.getLogger();

    private final TransientCraftingContainer craftSlots;
    private final ResultContainer craftResult = new ResultContainer();

    /** 附魔结果缓存：物品格内容不变就不重掷。 */
    private ItemStack enchantOffer = ItemStack.EMPTY;
    private ItemStack enchantOfferSource = ItemStack.EMPTY;

    public CatGirlTradeMenu(int windowId, Inventory playerInventory, int entityId) {
        super(ModMenus.CAT_GIRL_TRADE.get(), windowId);
        this.player = playerInventory.player;
        Entity entity = this.player.level().getEntity(entityId);
        this.catGirl = entity instanceof CatGirlEntity girl ? girl : null;
        Container goods = this.catGirl != null ? this.catGirl.getGoods() : new SimpleContainer(GOODS_COUNT);
        this.craftSlots = new TransientCraftingContainer(this, 3, 3);

        // ---- 出售区 ----
        this.addSlot(new Slot(this.sellInput, 0, 24, 18) {
            @Override
            public boolean mayPlace(ItemStack stack) {
                return !stack.is(ModItems.LOVE_COIN.get());
            }
        });
        this.addSlot(new Slot(this.sellResult, 0, 74, 18) {
            @Override
            public boolean mayPlace(ItemStack stack) {
                return false;
            }

            @Override
            public boolean mayPickup(Player player) {
                return !CatGirlTradeMenu.this.sellInput.getItem(0).isEmpty();
            }

            @Override
            public void onTake(Player player, ItemStack stack) {
                if (!player.level().isClientSide) {
                    ItemStack in = CatGirlTradeMenu.this.sellInput.getItem(0);
                    CatGirlTradeMenu.this.sellInput.removeItem(0, in.getCount());
                }
                super.onTake(player, stack);
            }
        });

        // ---- 附魔区 ----
        this.addSlot(new Slot(this.enchantInput, 0, 120, 18));
        this.addSlot(new Slot(this.enchantResult, 0, 150, 18) {
            @Override
            public boolean mayPlace(ItemStack stack) {
                return false;
            }

            @Override
            public boolean mayPickup(Player player) {
                return !CatGirlTradeMenu.this.enchantInput.getItem(0).isEmpty()
                        && CatGirlTradeMenu.this.countCoins(player) >= Config.CAT_GIRL_ENCHANT_COST.get();
            }

            @Override
            public void onTake(Player player, ItemStack stack) {
                if (!player.level().isClientSide) {
                    CatGirlTradeMenu.this.enchantInput.removeItem(0, 1);
                    CatGirlTradeMenu.this.consumeCoins(player, Config.CAT_GIRL_ENCHANT_COST.get());
                }
                super.onTake(player, stack);
            }
        });

        // ---- 下单区：左边放样品，右边出成品（材料她的、手续费你的爱心币）----
        this.addSlot(new Slot(this.orderInput, 0, 128, 90) {
            @Override
            public boolean mayPlace(ItemStack stack) {
                return !stack.is(ModItems.LOVE_COIN.get());
            }
        });
        this.addSlot(new Slot(this.orderResult, 0, 152, 90) {
            @Override
            public boolean mayPlace(ItemStack stack) {
                return false;
            }

            @Override
            public boolean mayPickup(Player player) {
                return !CatGirlTradeMenu.this.orderResult.getItem(0).isEmpty();
            }
        });

        // ---- 合成区（原版 3×3，模组配方一样走 RecipeManager）----
        for (int row = 0; row < 3; row++) {
            for (int col = 0; col < 3; col++) {
                this.addSlot(new Slot(this.craftSlots, col + row * 3, 24 + col * 18, 50 + row * 18));
            }
        }
        this.addSlot(new ResultSlot(this.player, this.craftSlots, this.craftResult, 0, 104, 68));

        // ---- 她的库存：只读展示，购买在 clicked() 里做 ----
        for (int i = 0; i < GOODS_COUNT; i++) {
            this.addSlot(new Slot(goods, i, goodsSlotX(i), goodsSlotY(i)) {
                @Override
                public boolean mayPlace(ItemStack stack) {
                    return false;
                }

                @Override
                public boolean mayPickup(Player player) {
                    return false;
                }
            });
        }

        // ---- 玩家背包 ----
        // 她的界面按需求「只显示她自己的东西」：玩家那 27 格整块挪到面板外面（PLAYER_ROW_Y = 屏幕外），
        // 槽位本身仍然存在 —— 所以 shift 一件件搬进背包、关界面把给予/合成格还回玩家都照常可用；
        // 但只把**快捷栏那一行**留在面板底部：不然界面上一个玩家来源格都没有，
        // 给予格要放东西、3x3 合成要拿材料，就全都没法填了。
        for (int row = 0; row < 3; row++) {
            for (int col = 0; col < 9; col++) {
                this.addSlot(new Slot(playerInventory, col + row * 9 + 9, 8 + col * 18,
                        PLAYER_ROW_Y + row * 18));
            }
        }
        for (int col = 0; col < 9; col++) {
            this.addSlot(new Slot(playerInventory, col, 8 + col * 18, HOTBAR_Y));
        }
    }

    public CatGirlEntity getCatGirl() {
        return this.catGirl;
    }

    /**
     * 下单逻辑放在这里：{@code broadcastChanges} 由服务端每 tick 调一次，
     * 不用挂网络包，槽位同步交给 {@code super} 照旧。
     *
     * <p>语义：<b>样品留在左边 = 一直做</b>；成品取走后材料 + 币还够就再做一件；
     * 把样品拿回去 = 停单。</p>
     */
    private void updateOrder() {
        ItemStack sample = this.orderInput.getItem(0);
        if (sample.isEmpty()) {
            this.orderResult.setItem(0, ItemStack.EMPTY);
            this.lastOrderHint = "";
            return;
        }
        if (!this.orderResult.getItem(0).isEmpty()) {
            return; // 上一件还没拿走
        }
        if (!(this.player.level() instanceof net.minecraft.server.level.ServerLevel server)) {
            return;
        }
        CatGirlCrafting.Result result;
        try {
            result = CatGirlCrafting.craftOrder(this.catGirl, server, sample.copyWithCount(1), 1, this.player);
        } catch (RuntimeException e) {
            // 这条路径跑在服务端每 tick 的 broadcastChanges 里：异常逃出去 = 整个服务端崩
            // （1.1.75 的崩溃就是这么出来的）。记日志、当作这次没做成，绝不带崩存档。
            LOGGER.error("cat_girl 下单这一拍失败（样品 {}），跳过", sample, e);
            return;
        }
        String hint;
        switch (result.status) {
            case OK -> {
                this.orderResult.setItem(0, result.product.copy());
                this.lastOrderHint = "";
                return;
            }
            case NO_MATERIALS -> hint = "cat_girl.order.no_materials";
            case NO_COINS -> hint = "cat_girl.order.no_coins";
            case NO_RECIPE -> hint = "cat_girl.order.no_recipe";
            default -> {
                return;
            }
        }
        if (!hint.equals(this.lastOrderHint)) {
            this.lastOrderHint = hint;
            this.player.displayClientMessage(net.minecraft.network.chat.Component.translatable(
                    hint, result.missing.isEmpty() ? "-" : result.missing), true);
        }
    }

    public int getCraftFee() {
        return Config.CAT_GIRL_CRAFT_FEE.get();
    }

    public int getEnchantCost() {
        return Config.CAT_GIRL_ENCHANT_COST.get();
    }

    @Override
    public void broadcastChanges() {
        if (!this.player.level().isClientSide) {
            this.updateSellResult();
            this.updateEnchantOffer();
            if (this.catGirl != null) {
                this.updateOrder();
            }
        }
        super.broadcastChanges();
    }

    /** 合成结果跟随网格变化。 */
    @Override
    public void slotsChanged(Container container) {
        super.slotsChanged(container);
        if (container == this.craftSlots && !this.player.level().isClientSide) {
            this.updateCraftResult();
        }
    }

    private void updateSellResult() {
        ItemStack in = this.sellInput.getItem(0);
        if (in.isEmpty()) {
            this.sellResult.setItem(0, ItemStack.EMPTY);
            return;
        }
        int coins = Math.min(64, CatGirlEntity.coinValue(in) * in.getCount());
        this.sellResult.setItem(0, coins <= 0 ? ItemStack.EMPTY : new ItemStack(ModItems.LOVE_COIN.get(), coins));
    }

    private void updateEnchantOffer() {
        ItemStack in = this.enchantInput.getItem(0);
        if (in.isEmpty() || !in.isEnchantable()) {
            this.enchantOffer = ItemStack.EMPTY;
            this.enchantOfferSource = ItemStack.EMPTY;
            this.enchantResult.setItem(0, ItemStack.EMPTY);
            return;
        }
        if (!ItemStack.matches(in, this.enchantOfferSource)) {
            this.enchantOfferSource = in.copy();
            ItemStack out = in.copyWithCount(1);
            this.enchantOffer = EnchantmentHelper.enchantItem(this.player.getRandom(), out, ENCHANT_LEVEL, false);
        }
        this.enchantResult.setItem(0, this.enchantOffer);
    }

    private void updateCraftResult() {
        Level level = this.player.level();
        ItemStack result = level.getRecipeManager()
                .getRecipeFor(RecipeType.CRAFTING, this.craftSlots, level)
                .map(recipe -> recipe.assemble(this.craftSlots, level.registryAccess()))
                .orElse(ItemStack.EMPTY);
        this.craftResult.setItem(0, result);
    }

    @Override
    public void clicked(int slotId, int button, ClickType clickType, Player player) {
        // 库存格 = 购买，不走原版点击流程
        if (slotId >= GOODS_START && slotId < GOODS_START + GOODS_COUNT) {
            if (!player.level().isClientSide) {
                this.tryBuy(slotId - GOODS_START, player);
            }
            return;
        }
        super.clicked(slotId, button, clickType, player);
    }

    /** 用爱心币买下第 index 格：价格 = 价值 × 数量，钱不够给一记催肥粒子。 */
    private void tryBuy(int index, Player player) {
        if (this.catGirl == null) {
            return;
        }
        ItemStack goodsStack = this.catGirl.getGoods().getItem(index);
        if (goodsStack.isEmpty()) {
            return;
        }
        int price = Math.max(1, CatGirlEntity.coinValue(goodsStack) * goodsStack.getCount());
        if (this.countCoins(player) < price) {
            this.catGirl.angryParticles();
            player.displayClientMessage(Component.translatable("cat_girl.trade.not_enough", price), true);
            return;
        }
        this.consumeCoins(player, price);
        ItemStack bought = this.catGirl.getGoods().removeItem(index, goodsStack.getCount());
        if (!player.getInventory().add(bought)) {
            player.drop(bought, false);
        }
        player.playSound(SoundEvents.ITEM_PICKUP, 0.7F, 1.4F);
    }

    private int countCoins(Player player) {
        int count = 0;
        Inventory inv = player.getInventory();
        for (int i = 0; i < inv.getContainerSize(); i++) {
            ItemStack stack = inv.getItem(i);
            if (stack.is(ModItems.LOVE_COIN.get())) {
                count += stack.getCount();
            }
        }
        return count;
    }

    private void consumeCoins(Player player, int amount) {
        int remaining = amount;
        Inventory inv = player.getInventory();
        for (int i = 0; i < inv.getContainerSize() && remaining > 0; i++) {
            ItemStack stack = inv.getItem(i);
            if (!stack.is(ModItems.LOVE_COIN.get())) {
                continue;
            }
            int take = Math.min(remaining, stack.getCount());
            stack.shrink(take);
            remaining -= take;
        }
    }

    @Override
    public ItemStack quickMoveStack(Player player, int index) {
        if (index >= GOODS_START && index < GOODS_START + GOODS_COUNT) {
            // 库存格不许 shift 直取（那是白拿），要买请左键点击
            return ItemStack.EMPTY;
        }
        Slot slot = this.slots.get(index);
        if (slot == null || !slot.hasItem()) {
            return ItemStack.EMPTY;
        }
        ItemStack stack = slot.getItem();
        ItemStack copy = stack.copy();
        if (index < PLAYER_START) {
            // 菜单内 → 背包
            if (!this.moveItemStackTo(stack, PLAYER_START, this.slots.size(), true)) {
                return ItemStack.EMPTY;
            }
        } else {
            // 背包 → 给予格（shift 一件件搬会把整叠塞进去，这里就按原版规则来）
            if (!this.moveItemStackTo(stack, SELL_INPUT, SELL_INPUT + 1, false)) {
                return ItemStack.EMPTY;
            }
        }
        if (stack.isEmpty()) {
            slot.setByPlayer(ItemStack.EMPTY);
        } else {
            slot.setChanged();
        }
        return copy;
    }

    /** 关界面时把四个输入区的东西还回玩家，一格都不吞。 */
    @Override
    public void removed(Player player) {
        super.removed(player);
        this.clearContainer(player, this.sellInput);
        this.clearContainer(player, this.enchantInput);
        this.clearContainer(player, this.craftSlots);
    }

    @Override
    public boolean stillValid(Player player) {
        return this.catGirl != null
                && this.catGirl.isAlive()
                && this.catGirl.isTame()
                && player.distanceToSqr(this.catGirl) <= 64.0D;
    }
}
