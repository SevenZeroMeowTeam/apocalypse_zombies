# -*- coding: utf-8 -*-
"""1.1.73 第一批：她按玩家那套 3x3 摆料自制 / 订做指定物品（命令 + 界面下单槽）/ 内部熔炉熔炼。"""
from pathlib import Path

J = 'src/main/java/com/apocalypse/zombies/'
LANG = 'src/main/resources/assets/apocalypse_zombies/lang/'

# ============================================================ ① CatGirlCrafting 重写
Path(J + 'entity/CatGirlCrafting.java').write_text('''package com.apocalypse.zombies.entity;

import net.minecraft.core.RegistryAccess;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.SimpleContainer;
import net.minecraft.world.entity.player.Player;
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
     * 她那张 3x3。<b>故意传 null 菜单</b>：{@code TransientCraftingContainer.setChanged()} 会回调
     * {@code menu.slotsChanged}，所以下面一处都不调 {@code setChanged()} —— 只借它的 {@code getWidth/getHeight}。
     */
    private static TransientCraftingContainer grid() {
        return new TransientCraftingContainer(null, 3, 3);
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
        if (com.apocalypse.zombies.Config.CAT_GIRL_AUTO_CRAFT.get() && time % 40L == 0L) {
            craftOne(cat, level);
        }
        if (com.apocalypse.zombies.Config.CAT_GIRL_SMELT.get() && time % 60L == 0L) {
            smeltOne(cat, level);
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
''', encoding='utf-8')
print('(1) CatGirlCrafting 重写：3x3 精确摆放 / 自制 / 订做 / 爱心币 / 内部熔炉')

# ============================================================ ② Config 开关
p = Path(J + 'Config.java'); s = p.read_text(encoding='utf-8')
old = '    /** 她会捡地上的东西塞进自己库存（捡到的东西就是她的货架）。 */'
assert old in s, 'Config 锚点'
s = s.replace(old, '''    /** 订做一件成品的手续费（爱心币）。0 = 不收。 */
    public static final ForgeConfigSpec.IntValue CAT_GIRL_CRAFT_FEE;

    /** 她有个内部熔炉：有矿石 + 燃料就把矿石烧成锭。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_SMELT;

    /** 她的盔甲在模型上画出来（关掉只影响画面，装备本身照样生效）。 */
    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_ARMOR_RENDER;

    /** 血月期间主动在她/玩家附近刷怪。 */
    public static final ForgeConfigSpec.BooleanValue BLOOD_MOON_SPAWN_ENABLED;

    /** 血月刷怪间隔（tick）。 */
    public static final ForgeConfigSpec.IntValue BLOOD_MOON_SPAWN_INTERVAL;

    /** 血月每次刷怪数量（每名玩家）。 */
    public static final ForgeConfigSpec.IntValue BLOOD_MOON_SPAWN_COUNT;

''' + old, 1)
old = '''        CAT_GIRL_PICKUP = b.comment("她会捡地上的东西收进自己库存（捡到的就是她的货架）。")'''
assert old in s, 'Config 定义锚点'
s = s.replace(old, '''        CAT_GIRL_CRAFT_FEE = b.comment("订做一件成品的手续费（爱心币）。")
                .defineInRange("craft_fee", 2, 0, 64);
        CAT_GIRL_SMELT = b.comment("她有个内部熔炉：有矿石 + 燃料就把矿石烧成锭（矿石/生铁 → 锭）。")
                .define("smelt", true);
        CAT_GIRL_ARMOR_RENDER = b.comment("把她的盔甲画在模型上（只影响画面）。")
                .define("armor_render", true);
        BLOOD_MOON_SPAWN_ENABLED = b.comment("血月期间主动刷怪。")
                .define("blood_moon_spawn", true);
        BLOOD_MOON_SPAWN_INTERVAL = b.comment("血月刷怪间隔（tick）。")
                .defineInRange("blood_moon_spawn_interval", 200, 20, 12000);
        BLOOD_MOON_SPAWN_COUNT = b.comment("血月每次刷怪数量（每名玩家）。")
                .defineInRange("blood_moon_spawn_count", 2, 1, 20);
''' + old, 1)
p.write_text(s, encoding='utf-8')
print('(2) Config：+ craft_fee / smelt / armor_render / blood_moon_spawn*')

# ============================================================ ③ 实体：改叫 tick()
p = Path(J + 'entity/CatGirlEntity.java'); s = p.read_text(encoding='utf-8')
old = '''        if (Config.CAT_GIRL_AUTO_CRAFT.get() && this.level() instanceof ServerLevel server
                && --this.craftTicks <= 0) {
            this.craftTicks = 40;
            CatGirlCrafting.craftOne(this, server);
        }'''
assert old in s, 'aiStep 自制锚点'
s = s.replace(old, '''        if (this.level() instanceof ServerLevel server) {
            CatGirlCrafting.tick(this, server);
        }''', 1)
p.write_text(s, encoding='utf-8')
print('(3) CatGirlEntity：自制/熔炼交给 CatGirlCrafting.tick')

# ============================================================ ④ 菜单：下单槽
p = Path(J + 'entity/menu/CatGirlTradeMenu.java'); s = p.read_text(encoding='utf-8')
old = '    private final Container enchantInput = new SimpleContainer(1);'
assert old in s, '菜单容器锚点'
s = s.replace(old, '''    private final Container enchantInput = new SimpleContainer(1);
    /** 下单：放一件样品，她照这个做（材料用她的、手续费扣你的爱心币）。 */
    private final Container orderInput = new SimpleContainer(1);
    private final Container orderResult = new SimpleContainer(1);
    /** 上次给她报过的原因，避免每 tick 刷屏。 */
    private String lastOrderHint = "";''', 1)

old = '''        // ---- 合成区（原版 3×3，模组配方一样走 RecipeManager）----'''
assert old in s, '合成区锚点'
s = s.replace(old, '''        // ---- 下单区：左边放样品，右边出成品（材料她的、手续费你的爱心币）----
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

''' + old, 1)

old = '''    public CatGirlEntity getCatGirl() {
        return this.catGirl;
    }'''
assert old in s, 'getCatGirl 锚点'
s = s.replace(old, old + '''

    /**
     * 下单逻辑放在这里：{@code broadcastChanges} 由服务端每 tick 调一次，
     * 不用挂网络包，槽位同步交给 {@code super} 照旧。
     *
     * <p>语义：<b>样品留在左边 = 一直做</b>；成品取走后材料 + 币还够就再做一件；
     * 把样品拿回去 = 停单。</p>
     */
    @Override
    public void broadcastChanges() {
        if (this.catGirl != null && !this.player.level().isClientSide) {
            this.updateOrder();
        }
        super.broadcastChanges();
    }

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
        CatGirlCrafting.Result result = CatGirlCrafting.craftOrder(
                this.catGirl, server, sample.copyWithCount(1), 1, this.player);
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
    }''', 1)
if 'import com.apocalypse.zombies.entity.CatGirlCrafting;' not in s:
    s = s.replace('import com.apocalypse.zombies.entity.CatGirlEntity;',
                  'import com.apocalypse.zombies.entity.CatGirlCrafting;' + chr(10)
                  + 'import com.apocalypse.zombies.entity.CatGirlEntity;', 1)
p.write_text(s, encoding='utf-8')
print('(4) 菜单：下单槽 + broadcastChanges 自动接单')

# ============================================================ ⑤ 界面：标签
p = Path(J + 'client/gui/CatGirlTradeScreen.java'); s = p.read_text(encoding='utf-8')
old = '''        guiGraphics.drawString(this.font, Component.translatable("cat_girl.trade.stock"), 8, 80, LABEL_DARK, false);'''
assert old in s, '界面标签锚点'
s = s.replace(old, old + '''
        guiGraphics.drawString(this.font, Component.translatable("cat_girl.trade.order"), 128, 80, LABEL_DARK, false);
        guiGraphics.drawString(this.font, Component.translatable("cat_girl.trade.order_fee",
                this.menu.getCraftFee()), 128, 100, PRICE_GOLD, false);''', 1)
p.write_text(s, encoding='utf-8')
print('(5) 界面：下单标签 + 手续费')

# ============================================================ ⑥ 命令：/apocalypse catgirl craft <物品id> [数量]
p = Path(J + 'command/ApocalypseCommand.java'); s = p.read_text(encoding='utf-8')
old = '''        root.then(Commands.literal("catgirl")
                .then(Commands.literal("recipes")'''
assert old in s, '命令锚点'
s = s.replace(old, '''        root.then(Commands.literal("catgirl")
                .then(Commands.literal("craft")
                        .then(Commands.argument("item", StringArgumentType.word())
                                .executes(context -> craftOrder(context.getSource(),
                                        StringArgumentType.getString(context, "item"), 1))
                                .then(Commands.argument("count", IntegerArgumentType.integer(1, 64))
                                        .executes(context -> craftOrder(context.getSource(),
                                                StringArgumentType.getString(context, "item"),
                                                IntegerArgumentType.getInteger(context, "count"))))))
                .then(Commands.literal("recipes")''', 1)

old = '''    private static int recipeReport('''
assert old in s, 'recipeReport 锚点'
s = s.replace(old, '''    /**
     * {@code /apocalypse catgirl craft <物品id> [数量]} —— 找最近的、属于你的猫耳娘订做：
     * 材料用她的库存，手续费按 {@code CAT_GIRL_CRAFT_FEE} 从你的爱心币里扣，成品直接给你。
     */
    private static int craftOrder(CommandSourceStack source, String itemId, int count) {
        ServerPlayer player;
        try {
            player = source.getPlayerOrException();
        } catch (Exception e) {
            source.sendFailure(Component.literal("这个命令要玩家来跑（要用你的爱心币付款）。"));
            return 0;
        }
        ItemStack wanted = CatGirlCrafting.itemById(itemId);
        if (wanted.isEmpty()) {
            source.sendFailure(Component.literal("没有这个物品：" + itemId
                    + "（写 id，例如 minecraft:diamond_pickaxe 或 apocalypse_zombies:love_coin）"));
            return 0;
        }
        CatGirlEntity girl = player.level().getEntitiesOfClass(CatGirlEntity.class,
                        player.getBoundingBox().inflate(16.0D), cat -> cat.isOwnedBy(player))
                .stream()
                .min(java.util.Comparator.comparingDouble(cat -> cat.distanceToSqr(player)))
                .orElse(null);
        if (girl == null) {
            source.sendFailure(Component.literal("16 格内没有你的猫耳娘。"));
            return 0;
        }
        if (!(player.level() instanceof ServerLevel level)) {
            return 0;
        }
        CatGirlCrafting.Result result = CatGirlCrafting.craftOrder(girl, level, wanted, count, player);
        String name = wanted.getHoverName().getString();
        switch (result.status) {
            case OK -> source.sendSuccess(() -> Component.literal("她做出来了：" + name + " ×"
                    + result.made + "（材料从她库存扣，手续费 " + result.feePaid + " 枚爱心币）"), false);
            case NO_MATERIALS -> source.sendFailure(Component.literal(
                    "她材料不够" + (result.missing.isEmpty() ? "" : "，缺：" + result.missing)
                            + "（把材料丢给她捡，或拿材料右键她）"));
            case NO_COINS -> source.sendFailure(Component.literal("你的爱心币不够（需要 "
                    + Config.CAT_GIRL_CRAFT_FEE.get() + " 枚，你有 " + result.feePaid + " 枚）。"));
            default -> source.sendFailure(Component.literal("她不会做 " + name + "（没有对应配方）。"));
        }
        return result.status == CatGirlCrafting.Status.OK ? result.made : 0;
    }

    private static int recipeReport(''', 1)
s = s.replace('import com.apocalypse.zombies.entity.CatGirlRecipeTable;',
              'import com.apocalypse.zombies.entity.CatGirlCrafting;\n'
              'import com.apocalypse.zombies.entity.CatGirlEntity;\n'
              'import com.apocalypse.zombies.entity.CatGirlRecipeTable;', 1)
s = s.replace('import net.minecraft.world.entity.Mob;',
              'import net.minecraft.world.entity.Mob;\nimport net.minecraft.world.item.ItemStack;', 1)
p.write_text(s, encoding='utf-8')
print('(6) 命令：/apocalypse catgirl craft <物品id> [数量]')

# ============================================================ ⑦ lang
for fname, add in {
    'zh_cn.json': {
        'cat_girl.trade.order': '下单（放样品，她照做）',
        'cat_girl.trade.order_fee': '手续费 %s 枚/件',
        'cat_girl.order.no_materials': '她材料不够，缺：%s',
        'cat_girl.order.no_coins': '爱心币不够付手续费',
        'cat_girl.order.no_recipe': '她不会做这个（没有配方）',
    },
    'en_us.json': {
        'cat_girl.trade.order': 'Order (put a sample)',
        'cat_girl.trade.order_fee': 'Fee %s per item',
        'cat_girl.order.no_materials': 'She is missing: %s',
        'cat_girl.order.no_coins': 'Not enough love coins',
        'cat_girl.order.no_recipe': 'She has no recipe for that',
    },
}.items():
    p = Path(LANG + fname); s = p.read_text(encoding='utf-8')
    assert '"cat_girl.trade.title"' in s, fname + ' 锚点'
    lines = ['  "%s": "%s",' % (k, v) for k, v in add.items()]
    s = s.replace('  "cat_girl.trade.title"', '\n'.join(lines) + '\n  "cat_girl.trade.title"', 1)
    p.write_text(s, encoding='utf-8')
print('(7) lang：下单相关 5 键（中英）')

# ============================================================ ⑧ 版本
g = Path('gradle.properties'); t = g.read_text(encoding='utf-8')
g.write_text(t.replace('mod_version=1.1.72', 'mod_version=1.1.73'), encoding='utf-8')
print('(8) mod_version=1.1.73')
