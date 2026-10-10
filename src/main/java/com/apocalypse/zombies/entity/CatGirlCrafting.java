package com.apocalypse.zombies.entity;

import net.minecraft.core.RegistryAccess;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.SimpleContainer;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.AbstractContainerMenu;
import net.minecraft.world.inventory.TransientCraftingContainer;
import net.minecraft.world.item.ArrowItem;
import net.minecraft.world.item.ArmorItem;
import net.minecraft.world.item.BowItem;
import net.minecraft.world.item.CrossbowItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.ShieldItem;
import net.minecraft.world.item.TieredItem;
import net.minecraft.world.item.TridentItem;
import net.minecraft.world.item.crafting.CraftingRecipe;
import net.minecraft.world.item.crafting.Ingredient;
import net.minecraft.world.item.crafting.RecipeType;
import net.minecraft.world.item.crafting.SmeltingRecipe;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.entity.AbstractFurnaceBlockEntity;
import net.minecraft.core.registries.BuiltInRegistries;

import com.mojang.logging.LogUtils;
import org.slf4j.Logger;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * 猫耳娘自己动手：从她的库存（{@code goods}）里凑材料，按**原版配方表**做出东西，
 * 做完放进库存 —— 也就是摆上她的货架，玩家用爱心币就能换走。
 *
 * <p><b>摆放概念</b>：她不像玩家那样有格子，但这里**照样按玩家的 3x3 摆放来判定** ——
 * 把配方自己的形状（{@code getIngredients()} 的位置）铺到一张 3x3 网格里，
 * 材料从她库存取出来摆进去，再让原版 {@link CraftingRecipe#matches} 自己点头才算数。
 * 所以「同材料的斧/镐」不会再随便挑一个：形状对不上就是做不了。</p>
 *
 * <p>白名单：只做「她自己的装备」—— 工具（剑/镐/斧/锹/锄）、弓弩、盔甲、箭、盾、三叉戟。
 * 不设白名单她会把玩家交给她的一堆材料做成木棍、台阶，库存立刻变垃圾场。</p>
 */
public final class CatGirlCrafting {

    private static final Logger LOGGER = LogUtils.getLogger();

    private CatGirlCrafting() {
    }

    /** 下单结果。 */
    public enum Status {
        OK,
        NO_RECIPE,
        NO_MATERIALS,
        NO_COINS,
        NOTHING
    }

    /** 一次下单/自制的结论。 */
    public static final class Result {
        public final Status status;
        public final ItemStack product;
        public final int made;
        public final int feePaid;
        /** 差什么料（材料不足时给出，最多列几样）。 */
        public final String missing;

        Result(Status status, ItemStack product, int made, int feePaid, String missing) {
            this.status = status;
            this.product = product;
            this.made = made;
            this.feePaid = feePaid;
            this.missing = missing;
        }

        static Result nothing() {
            return new Result(Status.NOTHING, ItemStack.EMPTY, 0, 0, "");
        }
    }

    /** 候选配方缓存：工程里一千多条配方，每次遍历会把服务端拖慢。 */
    private static List<CraftingRecipe> candidates;
    private static List<SmeltingRecipe> smeltables;

    /** 配方表变了（数据包重载）就清缓存。 */
    public static void invalidate() {
        candidates = null;
        smeltables = null;
    }

    // ------------------------------------------------------------ 白名单 / 缓存

    /** 她「该做」的产物。 */
    public static boolean isHerCraftable(ItemStack result) {
        if (result.isEmpty()) {
            return false;
        }
        Item item = result.getItem();
        return item instanceof TieredItem
                || item instanceof BowItem
                || item instanceof CrossbowItem
                || item instanceof ArmorItem
                || item instanceof ArrowItem
                || item instanceof ShieldItem
                || item instanceof TridentItem;
    }

    private static int desiredCount(ItemStack result) {
        return result.getItem() instanceof ArrowItem ? Math.min(64, result.getMaxStackSize()) : 1;
    }

    private static List<CraftingRecipe> candidates(ServerLevel level) {
        if (candidates == null) {
            RegistryAccess access = level.registryAccess();
            List<CraftingRecipe> list = new ArrayList<>();
            for (CraftingRecipe recipe : level.getRecipeManager().getAllRecipesFor(RecipeType.CRAFTING)) {
                if (isHerCraftable(recipe.getResultItem(access))) {
                    list.add(recipe);
                }
            }
            candidates = List.copyOf(list);
        }
        return candidates;
    }

    private static List<SmeltingRecipe> smeltables(ServerLevel level) {
        if (smeltables == null) {
            smeltables = List.copyOf(level.getRecipeManager().getAllRecipesFor(RecipeType.SMELTING));
        }
        return smeltables;
    }

    // ------------------------------------------------------------ 3x3 摆放

    /**
     * 她那张 3x3。<b>必须配一张菜单</b>：{@code TransientCraftingContainer.setItem()} 内部**就会**回调
     * {@code menu.slotsChanged(this)}，菜单为 {@code null} 时第一次 {@code setItem} 立刻 NPE
     * （1.1.75 就这么把服务端崩了：{@code layOut → TransientCraftingContainer.setItem}）。
     * 所以这里给一张空壳菜单：它的 {@code slotsChanged} 走默认空实现，永远不碰真实窗口。
     */
    private static TransientCraftingContainer grid() {
        return new TransientCraftingContainer(new GridMenu(), 3, 3);
    }

    /**
     * 只为了满足 {@link TransientCraftingContainer} 的菜单回调契约而存在的假菜单：
     * 不打开、不渲染、不持有玩家；{@code slotsChanged} 用默认空实现（这正是我们要的）。
     */
    private static final class GridMenu extends AbstractContainerMenu {

        GridMenu() {
            super(null, -1);
        }

        @Override
        public ItemStack quickMoveStack(Player player, int index) {
            return ItemStack.EMPTY;
        }

        @Override
        public boolean stillValid(Player player) {
            return true;
        }
    }

    /**
     * 试着把配方摆进她的 3x3：形状按配方自己的 ingredients 铺，材料从她库存取。
     *
     * @return 成功时返回每个库存格被吃掉的个数（下标对齐 goods），失败返回 null
     */
    private static int[] layOut(CraftingRecipe recipe, SimpleContainer goods, ServerLevel level,
                                TransientCraftingContainer grid) {
        List<Ingredient> ingredients = recipe.getIngredients();
        int n = ingredients.size();
        int slots = goods.getContainerSize();
        for (int w = 1; w <= 3; w++) {
            if (n % w != 0) {
                continue;
            }
            int h = n / w;
            if (h < 1 || h > 3) {
                continue;
            }
            for (int dx = 0; dx + w <= 3; dx++) {
                for (int dy = 0; dy + h <= 3; dy++) {
                    for (int i = 0; i < 9; i++) {
                        grid.setItem(i, ItemStack.EMPTY);
                    }
                    int[] used = new int[slots];
                    boolean ok = true;
                    for (int i = 0; i < n && ok; i++) {
                        Ingredient ingredient = ingredients.get(i);
                        if (ingredient.isEmpty()) {
                            continue; // 配方里的空格
                        }
                        int gx = dx + (i % w);
                        int gy = dy + (i / w);
                        boolean found = false;
                        for (int s = 0; s < slots; s++) {
                            ItemStack stack = goods.getItem(s);
                            if (stack.getCount() > used[s] && ingredient.test(stack)) {
                                used[s]++;
                                grid.setItem(gy * 3 + gx, stack.copyWithCount(1));
                                found = true;
                                break;
                            }
                        }
                        if (!found) {
                            ok = false;
                        }
                    }
                    // 最后让原版自己认一次：形状 / 尺寸 / 空位全对才算真的摆出来了
                    if (ok && recipe.matches(grid, level)) {
                        return used;
                    }
                }
            }
        }
        return null;
    }

    /** 差什么料：挑「缺得最少」的那条配方，把它缺的材料名列出来。 */
    private static String describeGap(CraftingRecipe recipe, SimpleContainer goods) {
        List<String> missing = new ArrayList<>();
        List<Ingredient> ingredients = recipe.getIngredients();
        for (Ingredient ingredient : ingredients) {
            if (ingredient.isEmpty()) {
                continue;
            }
            boolean have = false;
            for (int s = 0; s < goods.getContainerSize(); s++) {
                if (ingredient.test(goods.getItem(s))) {
                    have = true;
                    break;
                }
            }
            if (!have) {
                ItemStack[] options = ingredient.getItems();
                if (options.length > 0) {
                    String name = options[0].getHoverName().getString();
                    if (!missing.contains(name)) {
                        missing.add(name);
                    }
                }
            }
        }
        return String.join("、", missing);
    }

    private static void consume(SimpleContainer goods, int[] used) {
        for (int i = 0; i < used.length && i < goods.getContainerSize(); i++) {
            if (used[i] > 0) {
                goods.removeItem(i, used[i]);
            }
        }
        goods.setChanged();
    }

    /** 库存里已经有多少件这种东西。 */
    private static int countIn(SimpleContainer goods, ItemStack like) {
        int total = 0;
        for (int i = 0; i < goods.getContainerSize(); i++) {
            ItemStack stack = goods.getItem(i);
            if (!stack.isEmpty() && ItemStack.isSameItemSameTags(stack, like)) {
                total += stack.getCount();
            }
        }
        return total;
    }

    private static void deliver(CatGirlEntity cat, ServerLevel level, ItemStack stack) {
        ItemStack leftover = cat.getGoods().addItem(stack.copy());
        cat.getGoods().setChanged();
        if (!leftover.isEmpty()) {
            Block.popResource(level, cat.blockPosition(), leftover);
        }
    }

    // ------------------------------------------------------------ 自制（她自己那份）

    /** 每 20 tick 的维护节拍里叫她一声：够料就自己做一件，够燃料就烧一炉。 */
    public static void tick(CatGirlEntity cat, ServerLevel level) {
        long time = level.getGameTime();
        try {
            if (com.apocalypse.zombies.Config.CAT_GIRL_AUTO_CRAFT.get() && time % 40L == 0L) {
                craftOne(cat, level);
            }
            if (com.apocalypse.zombies.Config.CAT_GIRL_SMELT.get() && time % 60L == 0L) {
                smeltOne(cat, level);
            }
        } catch (RuntimeException e) {
            // 这段跑在实体的服务端 tick 里：异常逃出去 = 把服务端一起带走。
            // 记一条日志、这一拍跳过，下一拍再试 —— 别让某个奇怪配方毁掉存档。
            LOGGER.error("cat_girl 自动制作/熔炼这一拍失败，跳过", e);
        }
    }

    /** 自己做一件（不用花钱，材料她自己的）。 */
    public static Result craftOne(CatGirlEntity cat, ServerLevel level) {
        SimpleContainer goods = cat.getGoods();
        RegistryAccess access = level.registryAccess();
        TransientCraftingContainer grid = grid();
        for (CraftingRecipe recipe : candidates(level)) {
            ItemStack result = recipe.getResultItem(access);
            if (result.isEmpty() || countIn(goods, result) >= desiredCount(result)) {
                continue;
            }
            int[] used = layOut(recipe, goods, level, grid);
            if (used == null) {
                continue;
            }
            ItemStack product = recipe.assemble(grid, access).copy();
            consume(goods, used);
            deliver(cat, level, product);
            return new Result(Status.OK, product, product.getCount(), 0, "");
        }
        return Result.nothing();
    }

    // ------------------------------------------------------------ 订做（玩家点单）

    /** 玩家要的那件东西的配方 —— 按产物 id 找（取第一条能做出来的）。 */
    private static CraftingRecipe recipeFor(ServerLevel level, ItemStack wanted) {
        for (CraftingRecipe recipe : candidates(level)) {
            ItemStack result = recipe.getResultItem(level.registryAccess());
            if (!result.isEmpty() && ItemStack.isSameItem(result, wanted)) {
                return recipe;
            }
        }
        // 白名单外的（比如玩家点了一个木棍）也允许：按产物 id 在整个配方表里找
        for (CraftingRecipe recipe : level.getRecipeManager().getAllRecipesFor(RecipeType.CRAFTING)) {
            ItemStack result = recipe.getResultItem(level.registryAccess());
            if (!result.isEmpty() && ItemStack.isSameItem(result, wanted)) {
                return recipe;
            }
        }
        return null;
    }

    /** 按物品 id 找配方（命令用；白名单外也接单）。 */
    public static ItemStack itemById(String id) {
        ResourceLocation key = ResourceLocation.tryParse(id.contains(":") ? id : "minecraft:" + id);
        if (key == null) {
            return ItemStack.EMPTY;
        }
        return BuiltInRegistries.ITEM.getOptional(key).map(ItemStack::new).orElse(ItemStack.EMPTY);
    }

    /**
     * 玩家下单：她照样品做 {@code count} 件 —— 用她库存的材料，按 {@code feePerItem} 枚爱心币一件收费。
     * 成品交给玩家（背包放不下就掉在脚边）。
     */
    public static Result craftOrder(CatGirlEntity cat, ServerLevel level, ItemStack wanted, int count, Player payer) {
        if (wanted.isEmpty()) {
            return new Result(Status.NO_RECIPE, ItemStack.EMPTY, 0, 0, "");
        }
        CraftingRecipe recipe = recipeFor(level, wanted);
        if (recipe == null) {
            return new Result(Status.NO_RECIPE, ItemStack.EMPTY, 0, 0, "");
        }
        SimpleContainer goods = cat.getGoods();
        RegistryAccess access = level.registryAccess();
        TransientCraftingContainer grid = grid();

        int fee = Math.max(0, com.apocalypse.zombies.Config.CAT_GIRL_CRAFT_FEE.get());
        // 手续费按「造出来的件数」收：先看钱够做几件，再看能不能做出来，逐件扣。
        int rounds = fee <= 0 ? count : Math.min(count, countCoins(payer) / fee);
        if (rounds <= 0) {
            return new Result(Status.NO_COINS, ItemStack.EMPTY, 0, countCoins(payer), "");
        }

        ItemStack produced = ItemStack.EMPTY;
        int made = 0;
        int roundsDone = 0;
        for (int i = 0; i < rounds; i++) {
            int[] used = layOut(recipe, goods, level, grid);
            if (used == null) {
                break;
            }
            ItemStack product = recipe.assemble(grid, access).copy();
            consume(goods, used);
            produced = product.copy();
            made += product.getCount();
            roundsDone++;
            ItemStack give = product.copy();
            if (!payer.getInventory().add(give)) {
                payer.drop(give, false);
            }
        }
        if (roundsDone == 0) {
            return new Result(Status.NO_MATERIALS, ItemStack.EMPTY, 0, 0, describeGap(recipe, goods));
        }
        int paid = fee * roundsDone;
        if (paid > 0) {
            consumeCoins(payer, paid);
        }
        cat.playSound(net.minecraft.sounds.SoundEvents.ITEM_PICKUP, 1.0F, 1.2F);
        return new Result(Status.OK, produced, made, paid, "");
    }

    // ------------------------------------------------------------ 爱心币

    /** 玩家背包里有多少枚爱心币（含副手）。 */
    public static int countCoins(Player player) {
        int total = 0;
        for (int i = 0; i < player.getInventory().getContainerSize(); i++) {
            ItemStack stack = player.getInventory().getItem(i);
            if (stack.is(com.apocalypse.zombies.registry.ModItems.LOVE_COIN.get())) {
                total += stack.getCount();
            }
        }
        return total;
    }

    /** 收走 {@code amount} 枚爱心币，不够就尽量收（调用前自己判断）。 */
    public static void consumeCoins(Player player, int amount) {
        int left = amount;
        for (int i = 0; i < player.getInventory().getContainerSize() && left > 0; i++) {
            ItemStack stack = player.getInventory().getItem(i);
            if (!stack.is(com.apocalypse.zombies.registry.ModItems.LOVE_COIN.get())) {
                continue;
            }
            int take = Math.min(left, stack.getCount());
            stack.shrink(take);
            left -= take;
        }
    }

    // ------------------------------------------------------------ 内部熔炉

    /** 燃料值：原版熔炉认什么她就认什么（煤/木炭/木板/熔岩桶…）。 */
    private static boolean isFuel(ItemStack stack) {
        return AbstractFurnaceBlockEntity.isFuel(stack);
    }

    /**
     * 烧一炉：矿石/生铁 → 锭（走原版 {@code minecraft:smelting} 配方）。
     * 需要炉料 + 一份燃料；燃料本身不烧（否则她会把自己的木头全烧成炭）。
     */
    public static Result smeltOne(CatGirlEntity cat, ServerLevel level) {
        SimpleContainer goods = cat.getGoods();
        RegistryAccess access = level.registryAccess();
        for (SmeltingRecipe recipe : smeltables(level)) {
            ItemStack result = recipe.getResultItem(access);
            if (result.isEmpty()) {
                continue;
            }
            Ingredient input = recipe.getIngredients().isEmpty()
                    ? Ingredient.EMPTY : recipe.getIngredients().get(0);
            if (input.isEmpty()) {
                continue;
            }
            int oreSlot = -1;
            for (int i = 0; i < goods.getContainerSize(); i++) {
                ItemStack stack = goods.getItem(i);
                if (!stack.isEmpty() && input.test(stack) && !isFuel(stack)) {
                    oreSlot = i;
                    break;
                }
            }
            if (oreSlot < 0) {
                continue;
            }
            if (ItemStack.isSameItem(result, goods.getItem(oreSlot))) {
                continue;
            }
            int fuelSlot = -1;
            for (int i = 0; i < goods.getContainerSize(); i++) {
                if (i == oreSlot) {
                    continue;
                }
                ItemStack stack = goods.getItem(i);
                if (!stack.isEmpty() && isFuel(stack)) {
                    fuelSlot = i;
                    break;
                }
            }
            if (fuelSlot < 0) {
                continue; // 有矿没燃料：她会等（玩家给她煤）
            }
            goods.removeItem(oreSlot, 1);
            goods.removeItem(fuelSlot, 1);
            deliver(cat, level, result);
            return new Result(Status.OK, result.copy(), result.getCount(), 0, "");
        }
        return Result.nothing();
    }
}
