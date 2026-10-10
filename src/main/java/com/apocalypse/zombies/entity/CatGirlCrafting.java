package com.apocalypse.zombies.entity;

import net.minecraft.core.RegistryAccess;
import net.minecraft.resources.ResourceKey;
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
import net.minecraft.world.level.Level;
import net.minecraft.core.registries.BuiltInRegistries;

import com.mojang.logging.LogUtils;
import org.slf4j.Logger;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 猫耳娘自己动手：从她的库存（{@code goods}）里凑材料，按**原版配方表**做出东西，
 * 做完放进库存 —— 也就是摆上她的货架，玩家用爱心币就能换走。
 *
 * <p><b>摆放概念</b>：她不像玩家那样有格子，但这里**照样按玩家的 3x3 摆放来判定** ——
 * 把配方自己的形状（{@code getIngredients()} 的位置）铺到一张 3x3 网格里，
 * 材料从她库存取出来摆进去，再让原版 {@link CraftingRecipe#matches} 自己点头才算数。
 * 所以「同材料的斧/镐」不会再随便挑一个：形状对不上就是做不了。</p>
 *
 * <p><b>她会自己做「材料」</b>：只认成品装备的话，她手里有原木有圆石也永远做不出石镐 ——
 * 因为石镐要木棍，而木棍原来不在白名单里，她连木板都不会劈。现在按**配方图闭包**
 * （{@link #ensureGraph}）算出「为了做出装备，她自己得先做出来哪些中间材料」
 * （木板、木棍、圆石、锭……递归 {@link #MATERIAL_DEPTH} 层），缺料时**递归补齐**
 * （{@link #makeInto}）：缺木棍就劈木板、缺木板就劈原木、缺锭就烧矿。缺什么补什么、
 * 绝不多囤（她一共只有 9 格）。</p>
 *
 * <p>白名单分两层，别混：{@link #isHerCraftable} 是「能卖给你的成品」（装备类），
 * {@link #isHerMaterial} 是「为了做装备而自己产出的中间材料」，对外统一走
 * {@link #isHerMakeable}。没有第二层她就永远缺料。</p>
 */
public final class CatGirlCrafting {

    private static final Logger LOGGER = LogUtils.getLogger();

    /** 中间材料的递归深度上限：原木 → 木板 → 木棍 已经 2 层，3 层够用。 */
    private static final int MATERIAL_DEPTH = 3;

    /** 一次自动制作里最多顺手做几件中间材料（防止某一拍里做一长串把服务端按住）。 */
    private static final int MAX_SUB_CRAFTS = 4;

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

    // ------------------------------------------------------------ 缓存 / 配方图

    /** 产物是「她的成品」的合成配方。 */
    private static List<CraftingRecipe> gearRecipes;
    /** 产物 id → 合成配方（全表，含中间材料）。 */
    private static Map<String, List<CraftingRecipe>> craftByOutput;
    /** 产物 id → 熔炼配方（矿石 → 锭）。 */
    private static Map<String, List<SmeltingRecipe>> smeltByOutput;
    /** 她自己会做出来的中间材料 id 集合。 */
    private static Set<String> materialIds;

    /** 配方表变了（数据包重载）就清缓存。 */
    public static synchronized void invalidate() {
        gearRecipes = null;
        craftByOutput = null;
        smeltByOutput = null;
        materialIds = null;
    }

    /**
     * 建「配方图」：谁是她的成品、为了成品她得会做哪些中间材料、哪些料只能烧出来。
     * 按服务器实例缓存，重载数据包后走 {@link #invalidate()}。
     */
    public static synchronized void ensureGraph(ServerLevel level) {
        if (craftByOutput != null || level == null) {
            return;
        }
        RegistryAccess access = level.registryAccess();
        Map<String, List<CraftingRecipe>> byOut = new HashMap<>();
        List<CraftingRecipe> gear = new ArrayList<>();
        for (CraftingRecipe recipe : level.getRecipeManager().getAllRecipesFor(RecipeType.CRAFTING)) {
            ItemStack result = recipe.getResultItem(access);
            if (result.isEmpty()) {
                continue;
            }
            byOut.computeIfAbsent(idOf(result), key -> new ArrayList<>()).add(recipe);
            if (isHerCraftable(result)) {
                gear.add(recipe);
            }
        }
        Map<String, List<SmeltingRecipe>> bySmelt = new HashMap<>();
        for (SmeltingRecipe recipe : level.getRecipeManager().getAllRecipesFor(RecipeType.SMELTING)) {
            ItemStack result = recipe.getResultItem(access);
            if (!result.isEmpty()) {
                bySmelt.computeIfAbsent(idOf(result), key -> new ArrayList<>()).add(recipe);
            }
        }

        // 闭包：从「成品」出发沿着材料往下走。能合成 → 算中间材料并继续往下；
        // 只能烧出来（生铁 → 铁锭那种）→ 也算她会做，但不再往下（矿石得靠挖）。
        Set<String> mats = new LinkedHashSet<>();
        Map<String, Integer> seen = new HashMap<>();
        Deque<String> queue = new ArrayDeque<>();
        for (CraftingRecipe recipe : gear) {
            for (String id : ingredientIds(recipe)) {
                if (byOut.containsKey(id)) {
                    if (seen.putIfAbsent(id, 1) == null) {
                        queue.add(id);
                    }
                } else if (bySmelt.containsKey(id)) {
                    mats.add(id); // 缺锭她会自己烧
                }
            }
        }
        while (!queue.isEmpty()) {
            String id = queue.poll();
            mats.add(id);
            int depth = seen.getOrDefault(id, MATERIAL_DEPTH);
            if (depth >= MATERIAL_DEPTH) {
                continue;
            }
            for (CraftingRecipe recipe : byOut.getOrDefault(id, List.of())) {
                for (String ing : ingredientIds(recipe)) {
                    if (byOut.containsKey(ing)) {
                        if (seen.putIfAbsent(ing, depth + 1) == null) {
                            queue.add(ing);
                        }
                    } else if (bySmelt.containsKey(ing)) {
                        mats.add(ing);
                    }
                }
            }
        }

        craftByOutput = byOut;
        smeltByOutput = bySmelt;
        gearRecipes = List.copyOf(gear);
        materialIds = Set.copyOf(mats);
        LOGGER.info("[cat_girl] 配方图：成品配方 {} 条 / 中间材料 {} 种（含只能烧出来的）",
                gearRecipes.size(), materialIds.size());
    }

    private static String idOf(ItemStack stack) {
        return BuiltInRegistries.ITEM.getKey(stack.getItem()).toString();
    }

    /** 一条合成配方要的材料的物品 id（标签会展开成它的所有成员）。 */
    private static List<String> ingredientIds(CraftingRecipe recipe) {
        List<String> ids = new ArrayList<>();
        for (Ingredient ingredient : recipe.getIngredients()) {
            if (ingredient.isEmpty()) {
                continue;
            }
            for (ItemStack option : ingredient.getItems()) {
                ids.add(idOf(option));
            }
        }
        return ids;
    }

    // ------------------------------------------------------------ 白名单

    /** 她「该卖」的成品：装备类。 */
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

    /** 中间材料：做装备路上她得先自己做出来的东西（木板 / 木棍 / 圆石…）。要先 {@link #ensureGraph}。 */
    public static boolean isHerMaterial(ItemStack stack) {
        return !stack.isEmpty() && materialIds != null && materialIds.contains(idOf(stack));
    }

    /**
     * 她做得出来的东西 = 成品装备 ∪ 中间材料。
     * <p>「手上有没有料」是另一回事，由 {@link #craftOrder} / {@link #makeInto} 判定。</p>
     */
    public static boolean isHerMakeable(ItemStack stack) {
        return isHerCraftable(stack) || isHerMaterial(stack);
    }

    private static int desiredCount(ItemStack result) {
        return result.getItem() instanceof ArrowItem ? Math.min(64, result.getMaxStackSize()) : 1;
    }

    /** 同类只留最好的那件：镐跟镐比、斧跟斧比（原版工具/武器/盔甲都适用）。 */
    private static final List<String> KIND_SUFFIX = List.of(
            "pickaxe", "shovel", "hoe", "axe", "sword", "helmet", "chestplate",
            "leggings", "boots", "crossbow", "bow", "shield", "arrow", "trident");

    private static String kindOf(ItemStack stack) {
        String path = idOf(stack);
        int colon = path.indexOf(':');
        if (colon >= 0) {
            path = path.substring(colon + 1);
        }
        for (String suffix : KIND_SUFFIX) {
            if (path.endsWith(suffix)) {
                return suffix;
            }
        }
        return path;
    }

    /** 好不好用：拿最大耐久当档位（木 59、石 131、铁 250、钻 1561、下界合金 2031）。 */
    private static int rankOf(ItemStack stack) {
        return stack.getMaxDamage();
    }

    /** 她已经有一件同类的、且不比这件差的东西吗（同类不重复做，省她那 9 格）。 */
    private static boolean alreadyHasAtLeast(SimpleContainer goods, ItemStack candidate) {
        String kind = kindOf(candidate);
        int rank = rankOf(candidate);
        for (int i = 0; i < goods.getContainerSize(); i++) {
            ItemStack stack = goods.getItem(i);
            if (stack.isEmpty() || !kindOf(stack).equals(kind)) {
                continue;
            }
            if (rankOf(stack) >= rank) {
                return true;
            }
        }
        return false;
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

    private static boolean has(SimpleContainer goods, Ingredient want) {
        for (int i = 0; i < goods.getContainerSize(); i++) {
            ItemStack stack = goods.getItem(i);
            if (!stack.isEmpty() && want.test(stack)) {
                return true;
            }
        }
        return false;
    }

    /** 库存里「认这件料」的东西一共有几个 —— {@link #has} 只看有没有，这个才看够不够。 */
    private static int countMatching(SimpleContainer goods, Ingredient want) {
        int total = 0;
        for (int i = 0; i < goods.getContainerSize(); i++) {
            ItemStack stack = goods.getItem(i);
            if (!stack.isEmpty() && want.test(stack)) {
                total += stack.getCount();
            }
        }
        return total;
    }

    /** 一种料（按它能被哪些物品满足来归并）+ 一条配方里要几个。 */
    private static final class Need {
        final Ingredient want;
        int required;

        Need(Ingredient want) {
            this.want = want;
        }
    }

    /**
     * 一条配方「每种料各要几个」。
     *
     * <p>为什么不能只用 {@link #has}：配方里同一种料占几格就是要几个 —— 铁镐要 3 个铁锭就是
     * 3 个 ingredient。只问「有没有」时，她手里捏着 1 个铁锭也会以为料齐了：{@code layOut}
     * 摆不出来，补料那圈又以为什么都不缺，于是**永远卡住**（1.1.76 实测：她手里 1 块木板 +
     * 5 根原木，50 秒里一块木板都没再劈出来）。所以这里按「物品集合」归并同一种料并记账。</p>
     */
    private static Map<String, Need> needsOf(CraftingRecipe recipe) {
        Map<String, Need> needs = new LinkedHashMap<>();
        for (Ingredient ingredient : recipe.getIngredients()) {
            if (ingredient.isEmpty()) {
                continue;
            }
            StringBuilder key = new StringBuilder();
            for (ItemStack option : ingredient.getItems()) {
                key.append(idOf(option)).append(',');
            }
            needs.computeIfAbsent(key.toString(), k -> new Need(ingredient)).required++;
        }
        return needs;
    }

    /** 差什么料：把配方缺的材料名列出来（去重）。 */
    private static String describeGap(CraftingRecipe recipe, SimpleContainer goods) {
        List<String> missing = new ArrayList<>();
        for (Ingredient ingredient : recipe.getIngredients()) {
            if (ingredient.isEmpty() || has(goods, ingredient)) {
                continue;
            }
            ItemStack[] options = ingredient.getItems();
            if (options.length > 0) {
                String name = options[0].getHoverName().getString();
                if (!missing.contains(name)) {
                    missing.add(name);
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

    // ------------------------------------------------------------ 补料：缺的材料她自己做

    /** 一次自制里还能顺手做几件中间材料。 */
    private static final class Budget {
        int sub = MAX_SUB_CRAFTS;
    }

    /**
     * 把一条配方做出来 —— 缺料就**先把缺的料自己做出来**（递归，深度上限 {@link #MATERIAL_DEPTH}）。
     *
     * @return 产物（已进她库存）；做不了返回 null
     */
    private static ItemStack makeInto(CatGirlEntity cat, ServerLevel level, CraftingRecipe recipe,
                                      TransientCraftingContainer grid, int depth,
                                      Set<String> visiting, Budget budget) {
        SimpleContainer goods = cat.getGoods();
        String outId = idOf(recipe.getResultItem(level.registryAccess()));
        if (!visiting.add(outId)) {
            return null; // 成环（A 要 B、B 又要 A）就放弃这条
        }
        try {
            int[] used = layOut(recipe, goods, level, grid);
            if (used == null) {
                if (depth >= MATERIAL_DEPTH) {
                    return null;
                }
                // 缺料：按「要几个」而不是「有没有」来补 —— 手里 1 块木板不算有 3 块木板。
                for (Need need : needsOf(recipe).values()) {
                    while (countMatching(goods, need.want) < need.required) {
                        if (budget.sub <= 0) {
                            return null;
                        }
                        int before = countMatching(goods, need.want);
                        if (!fill(cat, level, need.want, grid, depth + 1, visiting, budget)) {
                            return null; // 这个是真的没有（要挖 / 要玩家给），放弃
                        }
                        // 补了但没变多（配方产物对不上号之类）→ 别在这儿死转
                        if (countMatching(goods, need.want) <= before) {
                            return null;
                        }
                    }
                }
                used = layOut(recipe, goods, level, grid);
                if (used == null) {
                    return null;
                }
            }
            ItemStack product = recipe.assemble(grid, level.registryAccess()).copy();
            consume(goods, used);
            if (depth > 0) {
                budget.sub--;
            }
            deliver(cat, level, product);
            return product;
        } finally {
            visiting.remove(outId);
        }
    }

    /**
     * 让库存里出现「认得这件料」的东西：先试自己合成（递归），再试自己烧。
     *
     * @return 真的补上了（或本来就有）返回 true
     */
    private static boolean fill(CatGirlEntity cat, ServerLevel level, Ingredient want,
                                TransientCraftingContainer grid, int depth,
                                Set<String> visiting, Budget budget) {
        // 注意：这里**不能**「已经有就不补」—— 调用方要的是「凑够几个」，手里有 1 个不等于够。
        RegistryAccess access = level.registryAccess();
        for (ItemStack option : want.getItems()) {
            for (CraftingRecipe recipe : craftByOutput.getOrDefault(idOf(option), List.of())) {
                ItemStack result = recipe.getResultItem(access);
                // 做出来不是缺的那样（比如另一种木头）→ 不做
                if (result.isEmpty() || !want.test(result) || !isHerMakeable(result)) {
                    continue;
                }
                if (makeInto(cat, level, recipe, grid, depth, visiting, budget) != null) {
                    return true;
                }
            }
        }
        for (ItemStack option : want.getItems()) {
            if (smeltFor(cat, level, idOf(option))) {
                return true;
            }
        }
        return false;
    }

    /** 缺的料先自己补齐（玩家点单路径用；补不上就拉倒，照旧报「差什么」）。 */
    private static void fillMissing(CatGirlEntity cat, ServerLevel level, CraftingRecipe recipe,
                                    TransientCraftingContainer grid) {
        Set<String> visiting = new HashSet<>();
        Budget budget = new Budget();
        SimpleContainer goods = cat.getGoods();
        for (Need need : needsOf(recipe).values()) {
            while (countMatching(goods, need.want) < need.required) {
                if (budget.sub <= 0) {
                    return;
                }
                int before = countMatching(goods, need.want);
                if (!fill(cat, level, need.want, grid, 0, visiting, budget)
                        || countMatching(goods, need.want) <= before) {
                    return;
                }
            }
        }
    }

    // ------------------------------------------------------------ 自制（她自己那份）

    /**
     * 上一次「自制 / 熔炼」的 gameTime（按维度记：不同世界 gameTime 不同源）。
     *
     * <p>为什么是「距上次多久」而不是 {@code time % 40 == 0}：这个 tick 由实体
     * {@code aiStep()} 每 20 tick 叫一次，**不是每一 tick 都进来**。用取模对拍等于赌
     * 她的维护节拍落点相位 —— 相位错开 20 就永远对不上 40 的倍数，她会**一次都不做**
     * （1.1.76 实测：给她原木+圆石，站了几分钟一块木板都没劈出来）。</p>
     */
    private static final Map<java.util.UUID, long[]> LAST_RUN = new HashMap<>();

    /** 每 20 tick 的维护节拍里叫她一声：缺什么做什么（含先自己做材料），有燃料就烧一炉。 */
    public static void tick(CatGirlEntity cat, ServerLevel level) {
        long time = level.getGameTime();
        try {
            // 按**她本人**记账，不是按维度：节拍是每只实体各跑一次的，同 tick 内第二只
            // 会被第一只刚写下的时间戳挡掉 —— 用维度做键 = 一群猫耳娘里只有一只会做东西。
            if (LAST_RUN.size() > 256) {
                LAST_RUN.clear();
            }
            long[] stamps = LAST_RUN.computeIfAbsent(cat.getUUID(), key -> new long[]{0L, 0L});
            if (com.apocalypse.zombies.Config.CAT_GIRL_AUTO_CRAFT.get() && time - stamps[0] >= 40L
                    && atStation(cat, level, CatGirlStation.Kind.CRAFTING_TABLE)) {
                stamps[0] = time;
                craftOne(cat, level);
            }
            if (com.apocalypse.zombies.Config.CAT_GIRL_SMELT.get() && time - stamps[1] >= 60L
                    && atStation(cat, level, CatGirlStation.Kind.FURNACE)) {
                stamps[1] = time;
                smeltOne(cat, level);
            }
        } catch (RuntimeException e) {
            // 这段跑在实体的服务端 tick 里：异常逃出去 = 把服务端一起带走。
            // 记一条日志、这一拍跳过，下一拍再试 —— 别让某个奇怪配方毁掉存档。
            LOGGER.error("cat_girl 自动制作/熔炼这一拍失败，跳过", e);
        }
    }

    /**
     * 站台门槛：{@code station_use} 打开时，她要真站在对应的方块边上才动手
     * （合成去合成台、熔炼去熔炉；她自己放下去的那个也算）。
     *
     * <p><b>为什么留了退路</b>：就近压根没有这类方块就放行（退回原地空手做）。
     * 否则「没台子 + 做不出台子」会让她从此停工 —— 那是把一个新功能变成一场事故。</p>
     */
    private static boolean atStation(CatGirlEntity cat, ServerLevel level, CatGirlStation.Kind kind) {
        if (!com.apocalypse.zombies.Config.CAT_GIRL_STATION_USE.get()) {
            return true;
        }
        if (cat.isAtStation(kind)) {
            return true;
        }
        return cat.stationNear(kind, com.apocalypse.zombies.Config.CAT_GIRL_STATION_RADIUS.get()) == null;
    }

    /**
     * 只探需求、不动库存：她现在「想不想」用合成台 / 熔炉。
     *
     * <p>刻意不复用 {@link #smeltNeeded} —— 那个函数会真的开炉（有副作用），
     * 拿来当探测等于每 tick 给她烧一炉。</p>
     *
     * <p>只认「炉子专属」的产物（原版配方里烧得出、工作台又做不出的），
     * 免得她为了一块铁锭跑去站在合成台前干等。</p>
     */
    public static CatGirlStation.Kind wantedWork(CatGirlEntity cat, ServerLevel level) {
        ensureGraph(level);
        if (gearRecipes == null) {
            return CatGirlStation.Kind.NONE;
        }
        boolean wantTable = false;
        boolean wantFurnace = false;
        SimpleContainer goods = cat.getGoods();
        RegistryAccess access = level.registryAccess();
        for (CraftingRecipe recipe : gearRecipes) {
            ItemStack result = recipe.getResultItem(access);
            if (result.isEmpty() || countIn(goods, result) >= desiredCount(result)) {
                continue;
            }
            if (desiredCount(result) == 1 && alreadyHasAtLeast(goods, result)) {
                continue;
            }
            String id = BuiltInRegistries.ITEM.getKey(result.getItem()).toString();
            boolean furnaceOnly = smeltByOutput != null && smeltByOutput.containsKey(id)
                    && recipeFor(level, result) == null;
            if (furnaceOnly) {
                wantFurnace = true;
            } else if (com.apocalypse.zombies.Config.CAT_GIRL_AUTO_CRAFT.get()) {
                wantTable = true;
                break;
            }
        }
        if (wantTable) {
            return CatGirlStation.Kind.CRAFTING_TABLE;
        }
        return wantFurnace && com.apocalypse.zombies.Config.CAT_GIRL_SMELT.get()
                ? CatGirlStation.Kind.FURNACE : CatGirlStation.Kind.NONE;
    }

    /**
     * 她自己做一件东西进自己库存（不走玩家下单、不收费、不扣爱心币）。
     * 「就近没有工作方块就自己做一个」用的就是这条路。
     */
    public static Result selfMake(CatGirlEntity cat, ServerLevel level, ItemStack wanted, int count) {
        if (wanted.isEmpty() || count <= 0) {
            return Result.nothing();
        }
        ensureGraph(level);
        CraftingRecipe recipe = recipeFor(level, wanted);
        if (recipe == null) {
            return new Result(Status.NO_RECIPE, ItemStack.EMPTY, 0, 0, "");
        }
        SimpleContainer goods = cat.getGoods();
        RegistryAccess access = level.registryAccess();
        TransientCraftingContainer grid = grid();
        ItemStack produced = ItemStack.EMPTY;
        int made = 0;
        for (int i = 0; i < count; i++) {
            int[] used = layOut(recipe, goods, level, grid);
            if (used == null && i == 0) {
                fillMissing(cat, level, recipe, grid);
                used = layOut(recipe, goods, level, grid);
            }
            if (used == null) {
                break;
            }
            ItemStack product = recipe.assemble(grid, access).copy();
            consume(goods, used);
            deliver(cat, level, product);
            produced = product.copy();
            made += product.getCount();
        }
        return made > 0 ? new Result(Status.OK, produced, made, 0, "") : Result.nothing();
    }

    /**
     * 自己做一件（不用花钱，材料她自己的）：缺哪件装备就做哪件，缺的料**自己先做出来**。
     * 同类只做最好的那件（有石镐就不再劈木镐），箭除外（按 {@link #desiredCount} 攒到一组）。
     */
    public static Result craftOne(CatGirlEntity cat, ServerLevel level) {
        ensureGraph(level);
        SimpleContainer goods = cat.getGoods();
        RegistryAccess access = level.registryAccess();
        TransientCraftingContainer grid = grid();
        for (CraftingRecipe recipe : gearRecipes) {
            ItemStack result = recipe.getResultItem(access);
            if (result.isEmpty() || countIn(goods, result) >= desiredCount(result)) {
                continue;
            }
            if (desiredCount(result) == 1 && alreadyHasAtLeast(goods, result)) {
                continue; // 同类的更好的她已经有了，别占格子
            }
            ItemStack product = makeInto(cat, level, recipe, grid, 0, new HashSet<>(), new Budget());
            if (product != null) {
                return new Result(Status.OK, product, product.getCount(), 0, "");
            }
        }
        return Result.nothing();
    }

    // ------------------------------------------------------------ 订做（玩家点单）

    /** 玩家要的那件东西的配方 —— 按产物 id 找。 */
    private static CraftingRecipe recipeFor(ServerLevel level, ItemStack wanted) {
        ensureGraph(level);
        ItemStack one = wanted.copyWithCount(1);
        for (CraftingRecipe recipe : gearRecipes) {
            if (ItemStack.isSameItem(recipe.getResultItem(level.registryAccess()), one)) {
                return recipe;
            }
        }
        // 中间材料、以及白名单外的（玩家点了一根木棍）也接单：按产物 id 在整张表里找
        for (CraftingRecipe recipe : level.getRecipeManager().getAllRecipesFor(RecipeType.CRAFTING)) {
            if (ItemStack.isSameItem(recipe.getResultItem(level.registryAccess()), one)) {
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
     * <p>料不够时她会**先把缺的材料自己做出来**（劈木板 / 做木棍 / 烧锭）再动手做成品。</p>
     */
    public static Result craftOrder(CatGirlEntity cat, ServerLevel level, ItemStack wanted, int count, Player payer) {
        if (wanted.isEmpty()) {
            return new Result(Status.NO_RECIPE, ItemStack.EMPTY, 0, 0, "");
        }
        ensureGraph(level);
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
            if (used == null && i == 0) {
                fillMissing(cat, level, recipe, grid); // 缺料：她自己先把材料做出来
                used = layOut(recipe, goods, level, grid);
            }
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

    /** 在给定的配方池里烧一炉（需要炉料 + 一份燃料）。 */
    private static boolean smeltFrom(CatGirlEntity cat, ServerLevel level, Iterable<SmeltingRecipe> pool) {
        SimpleContainer goods = cat.getGoods();
        RegistryAccess access = level.registryAccess();
        for (SmeltingRecipe recipe : pool) {
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
                if (!stack.isEmpty() && input.test(stack) && !isFuel(stack)
                        && !isHerCraftable(stack)) {
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
            return true;
        }
        return false;
    }

    /** 专门烧出某一产物（缺铁锭时她自己烧）。 */
    private static boolean smeltFor(CatGirlEntity cat, ServerLevel level, String outId) {
        List<SmeltingRecipe> pool = smeltByOutput == null ? null : smeltByOutput.get(outId);
        return pool != null && smeltFrom(cat, level, pool);
    }

    /**
     * 烧一炉：**只烧她自己装备链上真缺的那种料**。
     *
     * <p>以前这里遍历全部 {@code minecraft:smelting} 配方，实测后果是她在拿玩家的材料做减法：
     * 圆石→石头→平滑石（12 个圆石被烧成 7 个平滑石），缺铁的时候还把自己的铁剑烧成铁粒
     * （原版就有「铁制工具/盔甲烧成铁粒」的配方）。这是败家，不是"做材料"。所以现在改成
     * 需求驱动：只在「有件她想做、还没做出来的成品」里找缺的 ingredient，且只烧那个产物。</p>
     */
    public static Result smeltOne(CatGirlEntity cat, ServerLevel level) {
        ensureGraph(level);
        if (smeltByOutput == null || gearRecipes == null) {
            return Result.nothing();
        }
        return smeltNeeded(cat, level)
                ? new Result(Status.OK, ItemStack.EMPTY, 1, 0, "")
                : Result.nothing();
    }

    /** 她的成品链上缺的料，能不能靠烧补上（矿石→锭那一类）。能补一炉返回 true。 */
    private static boolean smeltNeeded(CatGirlEntity cat, ServerLevel level) {
        SimpleContainer goods = cat.getGoods();
        RegistryAccess access = level.registryAccess();
        for (CraftingRecipe recipe : gearRecipes) {
            ItemStack result = recipe.getResultItem(access);
            if (result.isEmpty() || !isHerMakeable(result)) {
                continue;
            }
            if (countIn(goods, result) >= desiredCount(result)) {
                continue;
            }
            if (desiredCount(result) == 1 && alreadyHasAtLeast(goods, result)) {
                continue;
            }
            for (Need need : needsOf(recipe).values()) {
                if (countMatching(goods, need.want) >= need.required) {
                    continue;
                }
                for (ItemStack option : need.want.getItems()) {
                    String id = idOf(option);
                    if (smeltByOutput.containsKey(id) && smeltFor(cat, level, id)) {
                        return true;
                    }
                }
            }
        }
        return false;
    }
}
