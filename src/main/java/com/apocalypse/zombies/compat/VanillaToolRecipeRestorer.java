package com.apocalypse.zombies.compat;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import net.minecraft.core.NonNullList;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.ReloadableServerResources;
import net.minecraft.server.packs.resources.PreparableReloadListener;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraft.tags.ItemTags;
import net.minecraft.util.GsonHelper;
import net.minecraft.util.Unit;
import net.minecraft.util.profiling.ProfilerFiller;
import net.minecraft.world.item.crafting.CraftingBookCategory;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.crafting.Ingredient;
import net.minecraft.world.item.crafting.Recipe;
import net.minecraft.world.item.crafting.RecipeManager;
import net.minecraft.world.item.crafting.ShapedRecipe;
import net.minecraftforge.event.AddReloadListenerEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;

import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

/**
 * 恢复被外家模组用「屏障假配方」禁用的原版工具配方（当前针对 {@code hcsurvival}）。
 *
 * <p><b>病根</b>：{@code hcsurvival} 把 {@code data/minecraft/recipes/} 下的原版配方整个换成
 * 「1 个屏障」的假配方（{@code stone_sword/pickaxe/axe/shovel/hoe} 五件全套 +
 * {@code wooden_axe/pickaxe/hoe} 三件），把玩家推向它自己的燧石工具链。屏障在生存里拿不到，
 * 这些配方一辈子合不出来 —— 但配方书 / REI 里它们照常显示，玩家摆上真材料也永远等不到产物。
 * 「铁制」与「木剑 / 木锹」的配方它没动，本来就能合成（v6.3.0 实测核对过 0.19.2 的全部数据）。</p>
 *
 * <p><b>判定是结构化的，不写死 hcsurvival</b>：配方 id 在 {@code minecraft} 命名空间，且
 * <b>每个非空材料格都只认屏障</b> —— 屏障是创造专属物品，这样的配方在生存里永远合不出来，
 * 无论出自哪个数据包，剔掉都不会破坏任何合法玩法；而材料格还认别的物品的配方（哪怕含屏障选项）
 * 仍然可能被合成，一律不碰。目前全整合包只有 hcsurvival 用这个手法。</p>
 *
 * <p><b>修法是「换真货」，不是「删假货」</b>：假配方若是我们认得的原版工具（木 / 石 / 铁 ×
 * 剑 / 镐 / 斧 / 锹 / 锄），用代码原样重建原版配方（图案、材料、产物逐格照抄原版 jar 里的
 * JSON —— 石质工具的材料是 {@code #minecraft:stone_tool_materials} 标签，不是只有圆石）顶回
 * 同一个 id（{@code minecraft:stone_axe} …），配方书解锁状态与 REI 显示都还指着这个名字。
 * 认不得的假配方（未来 hcsurvival 再禁别的）则直接剔除 —— 反正生存里合不出来，剔掉只是不再骗人。</p>
 *
 * <p><b>为什么不把自己的原版配方 JSON 塞进 {@code data/minecraft/recipes/}</b>：两个模组写同一条
 * {@code minecraft:recipes/stone_axe.json} 时谁赢取决于资源栈顺序（模组加载顺序），赌不起；
 * 运行期在 barrier 之后原地替换是确定性的（与 {@link CopperGearRecipeCompat} 同一条路 ——
 * {@link #onAddReloadListeners} 里我们排在原版 RecipeManager 之后，再等全部 prepare 结束才动手）。</p>
 *
 * <p><b>接线</b>：主类构造里显式 {@code MinecraftForge.EVENT_BUS.register}。想关掉：
 * 配置 {@code compat.restore_vanilla_recipes=false}，行为立刻回到原样。</p>
 */
public final class VanillaToolRecipeRestorer {

    private VanillaToolRecipeRestorer() {
    }

    /** 主类构造里调用：把本类挂到 FORGE 总线上（静态 {@code @SubscribeEvent} 处理器）。 */
    public static void register() {
        net.minecraftforge.common.MinecraftForge.EVENT_BUS.register(VanillaToolRecipeRestorer.class);
    }

    /** 一件工具的重建规格：产物 id 后缀 + 原版图案（X = 材料，# = 木棍）。一行一条，门禁逐行核对。 */
    private record ToolSpec(String id, String material, String... rows) {
    }

    /** 原版材料的重建凭据：三个前缀各对应原版 JSON 里 key "X" 的那一项。 */
    private static final String PLANKS = "planks";
    private static final String STONE = "stone_tool_materials";
    private static final String IRON = "iron_ingot";

    /**
     * 木 / 石 / 铁 × 剑 / 镐 / 斧 / 锹 / 锄，图案与材料逐格照抄原版 1.20.1 jar。
     *
     * <p>斧与锄的「左右手另一摆」不用单列：{@code ShapedRecipe.matches} 对同一个图案本来就会
     * 同时试正摆与镜像摆（原版 JSON 也只发一份）。铁的那 10 件（含木剑 / 木锹）当前并没有被
     * 谁禁用 —— 列在这只是兜底：哪天外家把假配方的手伸过去，这里现成接着。</p>
     */
    private static final List<ToolSpec> TOOL_SPECS = List.of(
            new ToolSpec("wooden_sword", PLANKS, "X", "X", "#"),
            new ToolSpec("wooden_pickaxe", PLANKS, "XXX", " # ", " # "),
            new ToolSpec("wooden_axe", PLANKS, "XX", "X#", " #"),
            new ToolSpec("wooden_shovel", PLANKS, "X", "#", "#"),
            new ToolSpec("wooden_hoe", PLANKS, "XX", " #", " #"),
            new ToolSpec("stone_sword", STONE, "X", "X", "#"),
            new ToolSpec("stone_pickaxe", STONE, "XXX", " # ", " # "),
            new ToolSpec("stone_axe", STONE, "XX", "X#", " #"),
            new ToolSpec("stone_shovel", STONE, "X", "#", "#"),
            new ToolSpec("stone_hoe", STONE, "XX", " #", " #"),
            new ToolSpec("iron_sword", IRON, "X", "X", "#"),
            new ToolSpec("iron_pickaxe", IRON, "XXX", " # ", " # "),
            new ToolSpec("iron_axe", IRON, "XX", "X#", " #"),
            new ToolSpec("iron_shovel", IRON, "X", "#", "#"),
            new ToolSpec("iron_hoe", IRON, "XX", " #", " #"));

    @SubscribeEvent
    public static void onAddReloadListeners(AddReloadListenerEvent event) {
        ReloadableServerResources resources = event.getServerResources();
        event.addListener(new PreparableReloadListener() {
            @Override
            public CompletableFuture<Void> reload(PreparableReloadListener.PreparationBarrier barrier,
                                                  ResourceManager resourceManager,
                                                  ProfilerFiller preparationsProfiler,
                                                  ProfilerFiller reloadProfiler,
                                                  Executor backgroundExecutor,
                                                  Executor gameExecutor) {
                // 与 CopperGearRecipeCompat 同一条约定：barrier 之后回到主线程再动手，
                // 这时 RecipeManager 已经是最终内容。
                return barrier.wait(Unit.INSTANCE)
                        .thenRunAsync(() -> restore(resources.getRecipeManager()), gameExecutor);
            }
        });
    }

    /** 现场重铺配方表：屏障假配方 → 原版真配方（认得的换、认不得的剔）。 */
    private static void restore(RecipeManager manager) {
        try {
            if (!Config.RESTORE_VANILLA_RECIPES.get()) {
                return;
            }
            Collection<Recipe<?>> recipes = manager.getRecipes();

            Map<ResourceLocation, Recipe<?>> rebuilt = new LinkedHashMap<>();
            List<String> replaced = new ArrayList<>();
            List<String> removed = new ArrayList<>();
            boolean changed = false;
            for (Recipe<?> recipe : recipes) {
                ResourceLocation id = recipe.getId();
                if (!"minecraft".equals(id.getNamespace()) || !isBarrierGated(recipe)) {
                    rebuilt.put(id, recipe);
                    continue;
                }
                changed = true;
                Recipe<?> fixed = rebuild(id.getPath());
                if (fixed != null) {
                    rebuilt.put(fixed.getId(), fixed);
                    replaced.add(id.toString());
                } else {
                    removed.add(id.toString());
                }
            }
            if (!changed) {
                return;
            }
            manager.replaceRecipes(new ArrayList<>(rebuilt.values()));
            if (!replaced.isEmpty()) {
                ApocalypseZombies.LOGGER.info(
                        "[原版配方恢复] {} 条屏障假配方换回真原版配方（摆对材料必定出原版工具）：{}",
                        replaced.size(), replaced);
            }
            if (!removed.isEmpty()) {
                ApocalypseZombies.LOGGER.warn(
                        "[原版配方恢复] 剔除 {} 条「只认屏障」的假配方（不是本表认得的原版工具，"
                                + "生存里本来就合不出来）：{} —— 若这是你想要的配方，请到 compat."
                                + "restore_vanilla_recipes 关闭本开关或反馈给模组作者补全重建表",
                        removed.size(), removed);
            }
        } catch (Exception e) {
            // 配方表是游戏的地基，这里任何意外都不该把世界加载搞崩：记一行，照常继续。
            ApocalypseZombies.LOGGER.warn("[原版配方恢复] 未完成，配方表保持原样。", e);
        }
    }

    /**
     * 这条配方是不是「生存里永远合不出来」的假配方：id 在 {@code minecraft} 命名空间，且
     * <b>每个非空材料格都只认屏障</b>。只要有一格还认别的物品（哪怕同时认屏障），就照常能被
     * 摆出来，不算假 —— 绝不多手。
     *
     * <p><b>为什么不看解析后的物品（{@code getItems()}）而看配料值结构</b>：配方重载收尾时
     * <b>物品标签还没绑定</b>，原版对「装载不到的标签」给的是一格<b>带「Empty Tag: …」悬停名的
     * 屏障哨兵</b>（{@code Ingredient.TagValue.getItems} 的占位物）。拿解析结果判会把木板 /
     * 木棍 / 工作台 / 铁门……一整票正常配方误判成屏障假配方（userdev 实测 84 条误报）。
     * 所以这里改按 {@link Ingredient#toJson()} 的<b>结构</b>判：{@code {"item": barrier}} 的格子
     * 才算「只认屏障」，带 {@code {"tag": …}} 或自定义配料的格子一律视为「无法判定 → 不动」。
     * hcsurvival 的假配方恰好全部是纯屏障物品格（8/8），结构判据正好管得住。</p>
     */
    private static boolean isBarrierGated(Recipe<?> recipe) {
        if (!"minecraft".equals(recipe.getId().getNamespace())) {
            return false;
        }
        boolean anyCell = false;
        for (Ingredient ingredient : recipe.getIngredients()) {
            if (ingredient.isEmpty()) {
                continue;   // 空槽
            }
            anyCell = true;
            if (!cellIsBarrierOnly(ingredient)) {
                return false;   // 这一格认了别的（或判不了）—— 配方不归我们管
            }
        }
        return anyCell;
    }

    /** 一格配料是否「只认屏障」：序列化后每条值都是不带标签的 {@code minecraft:barrier}。 */
    private static boolean cellIsBarrierOnly(Ingredient ingredient) {
        JsonElement json = ingredient.toJson();
        List<JsonElement> values = new ArrayList<>();
        if (json.isJsonArray()) {
            json.getAsJsonArray().forEach(values::add);
        } else {
            values.add(json);
        }
        for (JsonElement value : values) {
            if (!value.isJsonObject()) {
                return false;   // 认不得的结构 —— 不判死
            }
            JsonObject cell = value.getAsJsonObject();
            if (cell.has("tag") || !cell.has("item")) {
                return false;   // 标签格（或自定义配料）：此刻证据不足，宁可放过
            }
            if (!"minecraft:barrier".equals(GsonHelper.getAsString(cell, "item", ""))) {
                return false;   // 还认别的物品 —— 配方活着
            }
        }
        return true;
    }

    /** 按原版规格重建一件工具；表里没有的返回 null（调用方走剔除）。 */
    private static Recipe<?> rebuild(String path) {
        for (ToolSpec spec : TOOL_SPECS) {
            if (!spec.id().equals(path)) {
                continue;
            }
            return tool(spec);
        }
        return null;
    }

    /** 一条 ToolSpec → 一条原版等价的 ShapedRecipe（组别空、类别 equipment、产物 1 件，都与原版一致）。 */
    private static ShapedRecipe tool(ToolSpec spec) {
        Ingredient material = switch (spec.material()) {
            case PLANKS -> Ingredient.of(ItemTags.PLANKS);
            case STONE -> Ingredient.of(ItemTags.STONE_TOOL_MATERIALS);
            default -> Ingredient.of(Items.IRON_INGOT);
        };
        Ingredient stick = Ingredient.of(Items.STICK);
        String[] rows = spec.rows();
        int height = rows.length;
        int width = rows[0].length();
        NonNullList<Ingredient> grid = NonNullList.withSize(width * height, Ingredient.EMPTY);
        for (int r = 0; r < height; r++) {
            for (int c = 0; c < width; c++) {
                char ch = rows[r].charAt(c);
                if (ch == 'X') {
                    grid.set(r * width + c, material);
                } else if (ch == '#') {
                    grid.set(r * width + c, stick);
                }
            }
        }
        ResourceLocation id = new ResourceLocation("minecraft", spec.id());
        net.minecraft.world.item.Item item = net.minecraft.core.registries.BuiltInRegistries.ITEM.get(id);
        if (item == null || item == net.minecraft.world.item.Items.AIR) {
            throw new IllegalStateException("原版工具不在注册表里：" + spec.id());
        }
        return new ShapedRecipe(id, "", CraftingBookCategory.EQUIPMENT, width, height, grid, new ItemStack(item));
    }
}
