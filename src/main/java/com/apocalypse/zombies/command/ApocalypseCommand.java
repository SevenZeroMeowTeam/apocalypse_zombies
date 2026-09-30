package com.apocalypse.zombies.command;

import com.apocalypse.zombies.Config;
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
}
