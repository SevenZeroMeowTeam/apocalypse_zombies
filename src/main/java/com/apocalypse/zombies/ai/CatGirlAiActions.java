package com.apocalypse.zombies.ai;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.CatGirlCrafting;
import com.apocalypse.zombies.entity.CatGirlEntity;
import com.apocalypse.zombies.entity.CatGirlRecipeTable;

import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;

import java.util.List;

/**
 * 模型的「提议」落到游戏里的唯一入口。
 *
 * <p><b>纪律：模型只负责说，动手全在这里、且必须重新校验一遍。</b>
 * 动作白名单只有 {@code set_job} 和 {@code craft}；工种只认四个枚举，物品必须真的在
 * 原版配方表里、还得是「她这个白名单会做的」（剑/镐/斧/锹/锄/弓弩/箭/盾/盔甲）。
 * 第一版<b>不给</b>凭空给物品、加血、放方块、传送 —— 这些请求模型只能回话拒绝。</p>
 *
 * <p>必须在<b>主线程</b>调用（由 {@link LocalAiClient} 用 {@code server.execute} 回投）。</p>
 */
public final class CatGirlAiActions {

    private CatGirlAiActions() {
    }

    /** 她的回话样式。 */
    private static Component herLine(String text) {
        return Component.literal("[猫耳娘] ").withStyle(ChatFormatting.LIGHT_PURPLE)
                .append(Component.literal(text).withStyle(ChatFormatting.WHITE));
    }

    private static void note(ServerPlayer player, String text) {
        player.sendSystemMessage(Component.literal(text).withStyle(ChatFormatting.GRAY));
    }

    /**
     * 执行一轮答复。
     *
     * @param candidates 这一轮喂给模型的候选 id —— 合成必须落在这个集合里
     */
    public static void apply(CatGirlEntity cat, ServerPlayer player, OllamaWire.Reply reply,
                             List<String> candidates) {
        if (player == null || cat == null) {
            return;
        }
        if (!reply.ok()) {
            player.sendSystemMessage(Component.literal("[猫耳娘] ").withStyle(ChatFormatting.LIGHT_PURPLE)
                    .append(Component.literal("……我又想不明白了（" + reply.error() + "）。").withStyle(ChatFormatting.GRAY)));
            return;
        }
        if (!reply.say().isEmpty()) {
            player.sendSystemMessage(herLine(reply.say()));
        }
        if (!Config.CAT_GIRL_AI_ACTIONS.get()) {
            return; // 只让她说话，不动手
        }
        if (reply.wantsSetJob()) {
            doSetJob(cat, player, reply.job());
        } else if (reply.wantsCraft()) {
            doCraft(cat, player, reply.item(), reply.count(), candidates);
        }
    }

    private static void doSetJob(CatGirlEntity cat, ServerPlayer player, String jobName) {
        CatGirlEntity.Job job;
        try {
            job = CatGirlEntity.Job.valueOf(jobName);
        } catch (IllegalArgumentException e) {
            return; // 线里已经过滤过，这里只是兜底：不认识的工种直接忽略
        }
        CatGirlEntity.Job before = cat.getJob();
        cat.applyPlayerJob(job); // 和「玩家手动指派」同一条路径：自动模式对她关掉
        note(player, "（她切到了「" + jobName + "」" + (before == job ? "，本来就是" : "") + "）");
    }

    private static void doCraft(CatGirlEntity cat, ServerPlayer player, String itemId, int count,
                                List<String> candidates) {
        if (candidates != null && !candidates.isEmpty() && !candidates.contains(itemId)) {
            // 模型报了一个没喂给它的 id：可能是幻觉。配方表里查得到、也落在她的白名单里才放行。
            if (CatGirlRecipeTable.find(itemId).isEmpty()) {
                player.sendSystemMessage(herLine("我不认识「" + itemId + "」这个东西。"));
                return;
            }
        }
        ItemStack wanted = CatGirlCrafting.itemById(itemId);
        if (wanted.isEmpty()) {
            player.sendSystemMessage(herLine("我不认识「" + itemId + "」这个东西。"));
            return;
        }
        if (!(cat.level() instanceof ServerLevel level)) {
            return;
        }
        CatGirlCrafting.ensureGraph(level);
        if (!CatGirlCrafting.isHerMakeable(wanted)) {
            player.sendSystemMessage(herLine("这个我做不了 —— 我只会做剑、镐、斧、锹、锄、弓弩、箭、盾和盔甲，"
                    + "外加做它们要用的材料（木板、木棍、锭那些）。"));
            return;
        }
        if (CatGirlCrafting.countCoins(player) < 1) {
            player.sendSystemMessage(herLine("要做的话得给我爱心币当手续费 —— 你手上一枚都没有。"));
            return;
        }
        CatGirlCrafting.Result result = CatGirlCrafting.craftOrder(cat, level, wanted, count, player);
        switch (result.status) {
            case OK -> note(player, "（她做好了 " + result.product.getHoverName().getString()
                    + " x" + result.made + "，扣了你 " + result.feePaid + " 枚爱心币）");
            case NO_COINS -> player.sendSystemMessage(herLine("爱心币不够，做这个要 " + result.feePaid + " 枚。"));
            case NO_MATERIALS -> player.sendSystemMessage(herLine("料不够：还差 " + result.missing + "。"));
            default -> player.sendSystemMessage(herLine("这个她做不出来（没有对应配方）。"));
        }
    }
}
