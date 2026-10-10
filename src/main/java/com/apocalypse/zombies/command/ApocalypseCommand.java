package com.apocalypse.zombies.command;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.CatGirlCrafting;
import com.apocalypse.zombies.entity.CatGirlEntity;
import com.apocalypse.zombies.entity.CatGirlRecipeTable;
import com.apocalypse.zombies.entity.HordeOverlord;
import com.apocalypse.zombies.horde.HordeManager;
import com.apocalypse.zombies.moon.ApocalypseData;
import com.apocalypse.zombies.moon.MoonEvent;
import com.apocalypse.zombies.moon.MoonEventManager;
import com.apocalypse.zombies.zombie.EvolutionTier;
import com.apocalypse.zombies.zombie.ZombieEvolution;
import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

/** {@code /apocalypse ...} — inspection and authoring tools for testing a night. */
public final class ApocalypseCommand {

    private ApocalypseCommand() {
    }

    public static void register(CommandDispatcher<CommandSourceStack> dispatcher) {
        LiteralArgumentBuilder<CommandSourceStack> root = Commands.literal("apocalypse")
                .requires(source -> source.hasPermission(2));

        root.then(Commands.literal("status").executes(context -> {
            CommandSourceStack source = context.getSource();
            ServerLevel level = source.getLevel();
            MoonEvent moon = MoonEventManager.getMoonEvent(level);
            source.sendSuccess(() -> Component.translatable("command.apocalypse_zombies.status",
                    moon.getDisplayName(),
                    MoonEventManager.getWorldDay(level),
                    MoonEventManager.getEvolutionLevel(level),
                    EvolutionTier.byIndex(MoonEventManager.getEvolutionLevel(level)).getDisplayName(),
                    HordeManager.isActive()
                            ? Component.translatable("command.apocalypse_zombies.status.horde")
                            : Component.translatable("command.apocalypse_zombies.status.calm")), false);
            return 1;
        }));

        LiteralArgumentBuilder<CommandSourceStack> moon = Commands.literal("moon");
        // Register all MoonEvent IDs
        for (MoonEvent event : MoonEvent.values()) {
            moon.then(Commands.literal(event.getId()).executes(context -> setMoon(context.getSource(), event)));
        }
        // Convenient aliases
        moon.then(Commands.literal("clear").executes(context -> setMoon(context.getSource(), MoonEvent.NONE)));
        moon.then(Commands.literal("reset").executes(context -> setMoon(context.getSource(), MoonEvent.NONE)));
        moon.then(Commands.literal("blood").executes(context -> setMoon(context.getSource(), MoonEvent.BLOOD_MOON)));
        moon.then(Commands.literal("super_blood").executes(context -> setMoon(context.getSource(), MoonEvent.SUPER_BLOOD_MOON)));
        moon.then(Commands.literal("yellow").executes(context -> setMoon(context.getSource(), MoonEvent.YELLOW_MOON)));
        moon.then(Commands.literal("super_yellow").executes(context -> setMoon(context.getSource(), MoonEvent.SUPER_YELLOW_MOON)));
        moon.then(Commands.literal("blue").executes(context -> setMoon(context.getSource(), MoonEvent.BLUE_MOON)));
        moon.then(Commands.literal("super_blue").executes(context -> setMoon(context.getSource(), MoonEvent.SUPER_BLUE_MOON)));
        root.then(moon);

        root.then(Commands.literal("horde")
                .then(Commands.literal("start")
                        .executes(context -> startHorde(context.getSource(), Config.HORDE_WAVES.get()))
                        .then(Commands.argument("waves", IntegerArgumentType.integer(1, 12))
                                .executes(context -> startHorde(context.getSource(),
                                        IntegerArgumentType.getInteger(context, "waves")))))
                .then(Commands.literal("stop").executes(context -> {
                    HordeManager.stop(context.getSource().getLevel(), true);
                    context.getSource().sendSuccess(
                            () -> Component.translatable("command.apocalypse_zombies.horde.stopped"), true);
                    return 1;
                })));

        root.then(Commands.literal("evolution")
                .then(Commands.literal("get").executes(context -> {
                    int level = MoonEventManager.getEvolutionLevel(context.getSource().getLevel());
                    context.getSource().sendSuccess(() -> Component.translatable(
                            "command.apocalypse_zombies.evolution.get", level), false);
                    return level;
                }))
                .then(Commands.literal("set")
                        .then(Commands.argument("level", IntegerArgumentType.integer(0, EvolutionTier.MAX_TIER))
                                .executes(context -> {
                                    int level = IntegerArgumentType.getInteger(context, "level");
                                    ServerLevel serverLevel = context.getSource().getLevel();
                                    ApocalypseData data = ApocalypseData.get(serverLevel);
                                    data.setEvolutionLevel(level);
                                    MoonEventManager.sync(serverLevel, data);
                                    context.getSource().sendSuccess(() -> Component.translatable(
                                            "command.apocalypse_zombies.evolution.set", level), true);
                                    return level;
                                })))
                .then(Commands.literal("upgrade")
                        .executes(context -> upgradeNearby(context.getSource()))));

        root.then(Commands.literal("tiers").executes(context -> {
            String tiers = Arrays.stream(EvolutionTier.values())
                    .map(tier -> tier.getIndex() + "=" + tier.getTranslationKey())
                    .collect(Collectors.joining(", "));
            context.getSource().sendSuccess(() -> Component.literal(tiers), false);
            return EvolutionTier.values().length;
        }));

        root.then(Commands.literal("boss").executes(context -> bossStatus(context.getSource())));

        root.then(Commands.literal("catgirl")
                .then(Commands.literal("craft")
                        .then(Commands.argument("item", StringArgumentType.word())
                                .executes(context -> craftOrder(context.getSource(),
                                        StringArgumentType.getString(context, "item"), 1))
                                .then(Commands.argument("count", IntegerArgumentType.integer(1, 64))
                                        .executes(context -> craftOrder(context.getSource(),
                                                StringArgumentType.getString(context, "item"),
                                                IntegerArgumentType.getInteger(context, "count"))))))
                .then(Commands.literal("recipes")
                        .executes(context -> recipeReport(context.getSource(), null))
                        .then(Commands.argument("namespace", StringArgumentType.string())
                                .executes(context -> recipeReport(context.getSource(),
                                        StringArgumentType.getString(context, "namespace")))))
                .then(Commands.literal("auto")
                        .executes(context -> catgirlAuto(context.getSource())))
                .then(Commands.literal("chest")
                        .executes(context -> catgirlChest(context.getSource(), false))
                        .then(Commands.literal("clear")
                                .executes(context -> catgirlChest(context.getSource(), true)))));

        dispatcher.register(root);
    }

    /**
     * 尸潮之主的阶段机读出口：{@code /apocalypse boss}。
     *
     * <p>阶段推进只有副作用（buff / 标题 / 轮转表），没有可读的 NBT 字段，光靠
     * {@code /data get} 只能靠猜。这个子命令把每只在场 Boss 的阶段、当前技能与进度、
     * 轮转槽位、入场技和两个一次性开关直接打出来 —— 排「没有第 N 阶段」这类问题靠它。</p>
     */
    private static int bossStatus(CommandSourceStack source) {
        Vec3 origin = source.getPosition();
        List<HordeOverlord> bosses = source.getLevel().getEntitiesOfClass(
                HordeOverlord.class, new AABB(origin, origin).inflate(256.0D));
        if (bosses.isEmpty()) {
            source.sendFailure(Component.translatable("command.apocalypse_zombies.boss.none"));
            return 0;
        }
        for (HordeOverlord boss : bosses) {
            source.sendSuccess(() -> Component.literal(boss.debugStatus()), false);
        }
        return bosses.size();
    }

    private static int setMoon(CommandSourceStack source, MoonEvent event) {
        ServerLevel level = source.getLevel();
        if (event == MoonEvent.NONE) {
            ApocalypseData data = ApocalypseData.get(level);
            data.setMoonEvent(MoonEvent.NONE);
            MoonEventManager.sync(level, data);
            HordeManager.stop(level, false);
        } else {
            MoonEventManager.forceMoon(level, event);
        }
        source.sendSuccess(() -> Component.translatable(
                "command.apocalypse_zombies.moon.set", event.getDisplayName()), true);
        return 1;
    }

    private static int startHorde(CommandSourceStack source, int waves) {
        HordeManager.start(source.getLevel(), waves);
        source.sendSuccess(() -> Component.translatable(
                "command.apocalypse_zombies.horde.started", waves), true);
        return waves;
    }

    /** Forces every zombie close to the caller up to the world's current tier, for eyeballing. */
    private static int upgradeNearby(CommandSourceStack source) {
        ServerPlayer player = source.getPlayer();
        if (player == null) {
            return 0;
        }
        ServerLevel level = source.getLevel();
        int tier = Math.min(EvolutionTier.MAX_TIER, MoonEventManager.getEvolutionLevel(level));
        AABB box = player.getBoundingBox().inflate(48.0D);
        int upgraded = 0;
        for (Mob mob : level.getEntitiesOfClass(Mob.class, box)) {
            if (mob instanceof net.minecraft.world.entity.monster.Zombie zombie) {
                ZombieEvolution.setTier(zombie, tier, false);
                upgraded++;
            }
        }
        int finalUpgraded = upgraded;
        source.sendSuccess(() -> Component.translatable(
                "command.apocalypse_zombies.evolution.upgrade", finalUpgraded, tier), true);
        return upgraded;
    }

    /** 猫耳娘配方表：总数 / 来源 / 命名空间；给了命名空间就列出它名下的配方。 */
    /**
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

    /**
     * {@code /apocalypse catgirl auto} —— 开关她的自主模式。
     *
     * <p>开着时她自己按需求挑活干（缺木→伐木、缺矿→挖矿、有敌人在主人身边→打）；
     * 你一旦手动给她切过工种（给工具 / 空手右键）这个个体就自动关了，用这条再打开。</p>
     */
    private static int catgirlAuto(CommandSourceStack source) {
        CatGirlEntity girl = nearestOwned(source);
        if (girl == null) {
            return 0;
        }
        boolean next = !girl.isAutoJob();
        girl.setAutoJob(next);
        if (next) {
            source.sendSuccess(() -> Component.literal(
                    "自动模式：开 —— 她自己按需求挑活干（缺木伐木 / 缺矿挖矿 / 有敌人在你身边就上）。"), false);
        } else {
            source.sendSuccess(() -> Component.literal(
                    "自动模式：关 —— 她只干你指定的活（给工具或空手右键切工种；命令切不会关自动模式）。"), false);
        }
        return 1;
    }

    /**
     * {@code /apocalypse catgirl chest [clear]} —— 绑定 / 解绑她的储物点。
     *
     * <p>她的「储物点」只能这么绑（原版分不出哪个箱子是玩家的）：绑定后她会把多余的成品
     * 收进去、背包里缺矿石时从那里取一组；<b>没绑她一个容器都不碰</b>。</p>
     */
    private static int catgirlChest(CommandSourceStack source, boolean clear) {
        CatGirlEntity girl = nearestOwned(source);
        if (girl == null) {
            return 0;
        }
        if (clear) {
            girl.setStorage(null);
            source.sendSuccess(() -> Component.literal("储物点已解绑 —— 她不会再碰任何容器。"), false);
            return 1;
        }
        net.minecraft.core.BlockPos found = null;
        for (net.minecraft.core.BlockPos pos : net.minecraft.core.BlockPos.betweenClosed(
                girl.blockPosition().offset(-6, -2, -6), girl.blockPosition().offset(6, 2, 6))) {
            if (girl.level().getBlockEntity(pos) instanceof net.minecraft.world.Container) {
                found = pos.immutable();
                break;
            }
        }
        if (found == null) {
            source.sendFailure(Component.literal(
                    "她附近 6 格内没有容器（箱子 / 木桶 / 潜影盒……）—— 先把她带到箱子旁边。"));
            return 0;
        }
        girl.setStorage(found);
        String at = found.getX() + ", " + found.getY() + ", " + found.getZ();
        source.sendSuccess(() -> Component.literal("储物点已绑定到 " + at
                + " —— 她会把多余成品收进去，缺矿石时从那里取；换绑定就再跑一次。"), false);
        return 1;
    }

    /** 16 格内最近的、属于命令发起者的猫耳娘；没有就发失败消息并返回 null。 */
    private static CatGirlEntity nearestOwned(CommandSourceStack source) {
        ServerPlayer player;
        try {
            player = source.getPlayerOrException();
        } catch (Exception e) {
            source.sendFailure(Component.literal("这个命令要玩家来跑（得认得出哪只是你的）。"));
            return null;
        }
        CatGirlEntity girl = player.level().getEntitiesOfClass(CatGirlEntity.class,
                        player.getBoundingBox().inflate(16.0D), cat -> cat.isOwnedBy(player))
                .stream()
                .min(java.util.Comparator.comparingDouble(cat -> cat.distanceToSqr(player)))
                .orElse(null);
        if (girl == null) {
            source.sendFailure(Component.literal("16 格内没有你的猫耳娘。"));
        }
        return girl;
    }

    private static int recipeReport(CommandSourceStack source, String namespace) {
        CatGirlRecipeTable.ensureLoaded(source.getServer());
        if (!CatGirlRecipeTable.isPresent()) {
            source.sendFailure(Component.literal(
                    "配方表没载入 —— 跑 py tools/cat_girl_recipes_sync.py 同步后再重进世界"));
            return 0;
        }
        if (namespace != null) {
            List<CatGirlRecipeTable.Entry> hits = CatGirlRecipeTable.all().stream()
                    .filter(e -> e.namespace().equalsIgnoreCase(namespace))
                    .toList();
            source.sendSuccess(() -> Component.literal(
                    "命名空间 " + namespace + "： " + hits.size() + " 条配方"), false);
            for (CatGirlRecipeTable.Entry e : hits.stream().limit(20).toList()) {
                source.sendSuccess(() -> Component.literal(
                        "  " + e.output() + "  <- " + String.join(", ", e.ingredients())
                                + "   [" + e.type() + "]"), false);
            }
            if (hits.size() > 20) {
                source.sendSuccess(() -> Component.literal("  … 另有 " + (hits.size() - 20) + " 条"), false);
            }
            return hits.size();
        }

        StringBuilder sb = new StringBuilder();
        sb.append("猫耳娘配方表：").append(CatGirlRecipeTable.size()).append(" 条");
        sb.append("，指纹 ").append(CatGirlRecipeTable.digest());
        source.sendSuccess(() -> Component.literal(sb.toString()), false);

        var bySource = CatGirlRecipeTable.bySource();
        source.sendSuccess(() -> Component.literal("来源 " + bySource.size() + " 个："), false);
        bySource.entrySet().stream()
                .sorted((a, b) -> Integer.compare(b.getValue(), a.getValue()))
                .limit(12)
                .forEach(e -> source.sendSuccess(() -> Component.literal(
                        "  " + e.getKey() + " —— " + e.getValue() + " 条"), false));

        var byNs = CatGirlRecipeTable.byNamespace();
        source.sendSuccess(() -> Component.literal("命名空间 " + byNs.size() + " 个："), false);
        byNs.entrySet().stream()
                .sorted((a, b) -> Integer.compare(b.getValue(), a.getValue()))
                .limit(20)
                .forEach(e -> source.sendSuccess(() -> Component.literal(
                        "  " + e.getKey() + " —— " + e.getValue() + " 条"), false));
        source.sendSuccess(() -> Component.literal(
                "  /apocalypse catgirl recipes <命名空间> 看明细"), false);
        return CatGirlRecipeTable.size();
    }
}
