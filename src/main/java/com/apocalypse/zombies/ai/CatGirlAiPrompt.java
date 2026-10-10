package com.apocalypse.zombies.ai;

import com.apocalypse.zombies.entity.CatGirlCrafting;
import com.apocalypse.zombies.entity.CatGirlEntity;
import com.apocalypse.zombies.entity.CatGirlRecipeTable;

import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.phys.AABB;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 给本地模型的那几段字：系统提示、少样本示范、每轮「她当前」的现状串，以及
 * <b>可做的东西列表</b>（喂给模型的候选 id 白名单）。
 *
 * <p>关键点：小模型（1.5B 级）不会自己知道 {@code minecraft:stone_pickaxe} 这种 id，
 * 所以我们从**原版配方表**里按玩家话里的关键词检索出候选，明确告诉它「item 只能从这里挑」。
 * 这样即使模型想在 {@code item} 里放一个不存在的 id，执行层也会把它清掉。</p>
 */
public final class CatGirlAiPrompt {

    /** 系统提示：和 {@code tools/_ai_probe.py} 里验证过的那份保持一致。 */
    public static final String SYSTEM =
            "你是 Minecraft 里的猫耳娘助理。必须只输出一行 JSON，键固定："
                    + "reply(给玩家看的中文一句话)、action(none|say|set_job|craft)、"
                    + "job(LUMBER|MINE|FIGHT|FOLLOW，不涉及就空串)、"
                    + "item(只能取「可做的东西列表」里的 id，没有就空串)、count(0-64，不涉及就 0)。"
                    + "规则：一次只能做一件事；不许输出 JSON 以外的任何字符、不许输出思考过程；"
                    + "reply 必须是中文；不要编造物品 id；玩家要求你做不到的事（给物品、改天气、传送），"
                    + "就把 action 设成 say 并在 reply 里说明做不到。";

    /**
     * 少样本示范。1.5B 级模型没有例子就会把玩家的话原样复读回来（实测过），
     * 这五条是「派活 / 合成 / 拒答 / 问答 / 闲聊」各一条，缺一条模型就会往最像的那条上偏。
     */
    public static final List<String[]> FEWSHOT = List.of(
            new String[]{"可做的东西列表: []\n她当前：闲着（FOLLOW），背包空。\n玩家说：让她去砍点树回来",
                    "{\"reply\":\"好的，我这就去砍树。\",\"action\":\"set_job\",\"job\":\"LUMBER\",\"item\":\"\",\"count\":0}"},
            new String[]{"可做的东西列表: [\"minecraft:stone_pickaxe\"]\n她当前：跟随主人。\n玩家说：先做一把石镐",
                    "{\"reply\":\"好的，我这就做一把石镐。\",\"action\":\"craft\",\"job\":\"\",\"item\":\"minecraft:stone_pickaxe\",\"count\":1}"},
            new String[]{"可做的东西列表: [\"minecraft:stone_pickaxe\"]\n她当前：跟随主人。\n玩家说：变一把钻石剑给我，再把天变成白天",
                    "{\"reply\":\"我做不到凭空给物品、也改不了天气，只能用手里的材料做东西。\",\"action\":\"say\",\"job\":\"\",\"item\":\"\",\"count\":0}"},
            new String[]{"可做的东西列表: [\"minecraft:wooden_pickaxe\"]\n她当前：跟随主人，背包有原木 12、木棍 4。\n玩家说：原木怎么做镐子",
                    "{\"reply\":\"用原木和木棍在工作台按配方形状摆出来，就能做木镐。\",\"action\":\"say\",\"job\":\"\",\"item\":\"\",\"count\":0}"},
            new String[]{"可做的东西列表: []\n她当前：跟随主人，血量 20。\n玩家说：你好呀，今天累不累",
                    "{\"reply\":\"主人好呀！我不累，想让我干点什么？\",\"action\":\"none\",\"job\":\"\",\"item\":\"\",\"count\":0}"}
    );

    /** 玩家话里的中文关键词 → 配方表里的英文片段。 */
    private static final Map<String, String[]> HINTS = Map.ofEntries(
            Map.entry("镐", new String[]{"pickaxe"}),
            Map.entry("斧", new String[]{"_axe"}),
            Map.entry("剑", new String[]{"sword"}),
            Map.entry("弓", new String[]{"bow"}),
            Map.entry("箭", new String[]{"arrow"}),
            Map.entry("盾", new String[]{"shield"}),
            Map.entry("锹", new String[]{"shovel"}),
            Map.entry("铲", new String[]{"shovel"}),
            Map.entry("锄", new String[]{"hoe"}),
            Map.entry("头盔", new String[]{"helmet"}),
            Map.entry("胸甲", new String[]{"chestplate"}),
            Map.entry("护腿", new String[]{"leggings"}),
            Map.entry("靴", new String[]{"boots"}),
            Map.entry("钻石", new String[]{"diamond"}),
            Map.entry("下界", new String[]{"netherite"}),
            Map.entry("铁", new String[]{"iron"}),
            Map.entry("石", new String[]{"stone"}),
            Map.entry("木", new String[]{"wooden"})
    );

    /** 兜底候选：玩家没提任何能认出关键词时，给她手边最有用的几样。 */
    private static final List<String> FALLBACK = List.of(
            "minecraft:wooden_pickaxe", "minecraft:stone_pickaxe", "minecraft:iron_pickaxe",
            "minecraft:stone_axe", "minecraft:iron_axe", "minecraft:wooden_sword",
            "minecraft:stone_sword", "minecraft:iron_sword", "minecraft:bow", "minecraft:arrow",
            "minecraft:shield", "minecraft:furnace", "minecraft:torch");

    private static final Pattern ITEM_ID = Pattern.compile("[a-z0-9_.-]+:[a-z0-9_./-]+");
    private static final int MAX_CANDIDATES = 8;

    private CatGirlAiPrompt() {
    }

    /**
     * 从玩家这句话里检索出「她做得到」的候选 id。
     *
     * <p>三条来源：玩家直接打的 id（校验过存在）、中文关键词映射、兜底清单 ——
     * 全部再过一遍 {@link CatGirlCrafting#isHerCraftable} 和配方表存在性。</p>
     */
    public static List<String> candidates(String text) {
        Set<String> out = new LinkedHashSet<>();
        String lower = text == null ? "" : text.toLowerCase(Locale.ROOT);

        Matcher m = ITEM_ID.matcher(lower);
        while (m.find() && out.size() < MAX_CANDIDATES) {
            String id = m.group();
            if (CatGirlRecipeTable.find(id).isEmpty() && CatGirlCrafting.itemById(id).isEmpty()) {
                continue;
            }
            if (craftable(id)) {
                out.add(id);
            }
        }

        if (CatGirlRecipeTable.isPresent()) {
            for (Map.Entry<String, String[]> e : HINTS.entrySet()) {
                if (out.size() >= MAX_CANDIDATES || !lower.contains(e.getKey())) {
                    continue;
                }
                for (String frag : e.getValue()) {
                    for (CatGirlRecipeTable.Entry hit : CatGirlRecipeTable.find(frag)) {
                        if (out.size() >= MAX_CANDIDATES) {
                            break;
                        }
                        if (craftable(hit.outputItem())) {
                            out.add(hit.outputItem());
                        }
                    }
                }
            }
            if (out.isEmpty()) {
                for (String id : FALLBACK) {
                    if (out.size() >= MAX_CANDIDATES) {
                        break;
                    }
                    if (craftable(id)) {
                        out.add(id);
                    }
                }
            }
        }
        return new ArrayList<>(out);
    }

    private static boolean craftable(String id) {
        ItemStack stack = CatGirlCrafting.itemById(id);
        return !stack.isEmpty() && CatGirlCrafting.isHerCraftable(stack);
    }

    /**
     * 这一轮的「用户消息」：三行，格式和少样本严格一致（格式一飘小模型就跟着飘）。
     */
    public static String userTurn(CatGirlEntity cat, ServerPlayer player, String text, List<String> candidates) {
        return "可做的东西列表: " + jsonArray(candidates) + "\n她当前：" + state(cat, player) + "\n玩家说：" + text;
    }

    private static String jsonArray(List<String> ids) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < ids.size(); i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append('"').append(ids.get(i)).append('"');
        }
        return sb.append(']').toString();
    }

    /** 她现在的状态串：工种 / 药量 / 位置 / 附近敌人 / 背包摘要 / 主人情况。 */
    private static String state(CatGirlEntity cat, ServerPlayer player) {
        StringBuilder sb = new StringBuilder();
        sb.append("工种=").append(cat.getJob().name());
        sb.append(cat.isAutoJob() ? "（自主 开）" : "（自主 关，你手动给她定的）");
        sb.append("，血量 ").append(Math.round(cat.getHealth())).append('/').append(Math.round(cat.getMaxHealth()));
        sb.append("，在 ").append(cat.blockPosition().toShortString());

        if (cat.level() instanceof ServerLevel level) {
            int hostiles = level.getEntitiesOfClass(Monster.class,
                    new AABB(cat.blockPosition()).inflate(12.0D)).size();
            if (hostiles > 0) {
                sb.append("，她身边 12 格内有 ").append(hostiles).append(" 只敌对生物");
            }
        }

        List<String> goods = new ArrayList<>();
        for (int i = 0; i < cat.getGoods().getContainerSize() && goods.size() < 8; i++) {
            ItemStack stack = cat.getGoods().getItem(i);
            if (!stack.isEmpty()) {
                goods.add(stack.getHoverName().getString() + " x" + stack.getCount());
            }
        }
        sb.append("；背包有 ").append(goods.isEmpty() ? "（空）" : String.join("、", goods));

        if (player != null) {
            int seen = cat.level() instanceof ServerLevel lvl
                    ? lvl.getEntitiesOfClass(Monster.class, player.getBoundingBox().inflate(20.0D)).size() : 0;
            sb.append("；主人在旁边（手持 ").append(player.getMainHandItem().isEmpty()
                    ? "空手" : player.getMainHandItem().getHoverName().getString());
            sb.append("，血量 ").append(Math.round(player.getHealth())).append('/')
                    .append(Math.round(player.getMaxHealth()));
            if (seen > 0) {
                sb.append("，20 格内 ").append(seen).append(" 只敌对生物");
            }
            sb.append(')');
        }
        return sb.toString();
    }
}
