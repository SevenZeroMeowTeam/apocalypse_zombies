package com.apocalypse.zombies.event;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.AbstractEliteZombie;
import com.apocalypse.zombies.horde.HordeManager;
import com.apocalypse.zombies.moon.MoonEvent;
import com.apocalypse.zombies.moon.MoonEventManager;
import com.apocalypse.zombies.network.NetworkHandler;
import com.apocalypse.zombies.network.ZombieTierPacket;
import com.apocalypse.zombies.zombie.ZombieEvolution;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.ai.attributes.AttributeInstance;
import net.minecraft.world.entity.ai.attributes.AttributeModifier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.EntityJoinLevelEvent;
import net.minecraftforge.event.entity.living.LivingDeathEvent;
import net.minecraftforge.event.entity.living.LivingEvent;
import net.minecraftforge.eventbus.api.Event;
import net.minecraft.world.entity.EntityType;
import net.minecraftforge.event.entity.living.MobSpawnEvent;
import net.minecraftforge.event.entity.player.PlayerEvent;
import net.minecraftforge.event.entity.player.PlayerSleepInBedEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.network.PacketDistributor;

import java.util.UUID;

/** Server-side glue: the clock, evolution rolls, sleeping bans and the blue moon's parting gift. */
public final class CommonEvents {

    private CommonEvents() {
    }

    /**
     * 特殊敌对生物（尖啸者 / 碎颅者 / 腐蚀者）不参与进化 tier。
     *
     * <p>它们的数值是手调的，定位靠自己的技能，套上 tier 的体型与属性放大只会把平衡拉爆，
     * 也会让客户端拿着一个不存在的 tier 去缩放它们。所以凡是和 tier 相关的钩子都先用这个筛一遍。</p>
     */
    private static boolean participatesInEvolution(Zombie zombie) {
        return !(zombie instanceof AbstractEliteZombie);
    }

    @SubscribeEvent
    public static void onLevelTick(TickEvent.LevelTickEvent event) {
        if (event.phase != TickEvent.Phase.END || !(event.level instanceof ServerLevel level)) {
            return;
        }
        MoonEventManager.tick(level);
        HordeManager.tick(level);
    }

    @SubscribeEvent
    public static void onLivingTick(LivingEvent.LivingTickEvent event) {
        Entity entity = event.getEntity();
        if (entity instanceof Zombie zombie && !zombie.level().isClientSide()
                && participatesInEvolution(zombie)) {
            ZombieEvolution.tick(zombie);
        }
    }

    /**
     * Gives freshly spawned zombies their starting tier. Horde mobs are handled directly by the
     * horde manager, which assigns an explicit tier right after spawning.
     */
    @SubscribeEvent
    public static void onFinalizeSpawn(MobSpawnEvent.FinalizeSpawn event) {
        if (!(event.getEntity() instanceof Zombie zombie) || !participatesInEvolution(zombie)) {
            return;
        }
        if (!(event.getLevel() instanceof ServerLevel level)) {
            return;
        }
        ZombieEvolution.onSpawn(zombie, level, 0);
    }

    /** Re-applies a saved tier when a zombie is loaded back into the world. */
    @SubscribeEvent
    public static void onEntityJoin(EntityJoinLevelEvent event) {
        if (event.getLevel().isClientSide() || !(event.getEntity() instanceof Zombie zombie)
                || !participatesInEvolution(zombie)) {
            return;
        }
        ZombieEvolution.refresh(zombie);
    }

    /** Blood moons lock every bed in the overworld for the whole night. */
    @SubscribeEvent
    public static void onSleepInBed(PlayerSleepInBedEvent event) {
        Player player = event.getEntity();
        if (player.level().isClientSide() || !Config.BLOOD_MOON_BLOCKS_SLEEP.get()) {
            return;
        }
        MoonEvent moon = MoonEventManager.getMoonEvent(player.level());
        if (!moon.blocksSleep()) {
            return;
        }
        event.setResult(Player.BedSleepingProblem.NOT_POSSIBLE_NOW);
        player.displayClientMessage(
                Component.translatable("sleep.apocalypse_zombies.blocked", moon.getDisplayName()), true);
    }

    /**
     * 血月期间禁止苦力怕 / 蜘蛛 / 洞穴蜘蛛 / 女巫生成。
     *
     * <p>与 Crafting Dead 的 {@code MoonEventHandler.handleCheckSpawn} 同一条规则：血月之夜把舞台
     * 留给僵尸潮，而不是让一堆非僵尸怪跟着凑热闹。用 {@code PositionCheck}（而不是 FinalizeSpawn）
     * 是因为只有它能在怪真正落位之前把这次生成否掉。</p>
     */
    @SubscribeEvent
    public static void onSpawnPositionCheck(MobSpawnEvent.PositionCheck event) {
        // 用实体自己的 level：PositionCheck 给的是 ServerLevelAccessor，不是 Level。
        Level level = event.getEntity().level();
        if (level.isClientSide() || !Config.BLOOD_MOON_BLOCKS_OTHER_MOBS.get()) {
            return;
        }
        MoonEvent moon = MoonEventManager.getMoonEvent(level);
        if (moon != MoonEvent.BLOOD_MOON && moon != MoonEvent.SUPER_BLOOD_MOON) {
            return;
        }
        EntityType<?> type = event.getEntity().getType();
        if (type == EntityType.CREEPER || type == EntityType.SPIDER
                || type == EntityType.CAVE_SPIDER || type == EntityType.WITCH) {
            event.setResult(Event.Result.DENY);
        }
    }

    /** Blue moons pay out: evolved zombies carry bonus loot while the blessing is running. */
    @SubscribeEvent
    public static void onLivingDeath(LivingDeathEvent event) {
        if (!(event.getEntity() instanceof Zombie zombie) || !participatesInEvolution(zombie)) {
            return;
        }
        Level level = zombie.level();
        if (!(level instanceof ServerLevel serverLevel)) {
            return;
        }
        MoonEvent moon = MoonEventManager.getMoonEvent(serverLevel);
        if (moon.getEffect() != MoonEvent.MoonEffect.LUCK) {
            return;
        }
        int tier = ZombieEvolution.getTierIndex(zombie);
        double chance = (moon.isSuperMoon() ? 0.55D : 0.30D) + Math.min(0.20D, tier * 0.04D);
        if (serverLevel.getRandom().nextDouble() >= chance) {
            return;
        }
        ItemStack loot = serverLevel.getRandom().nextBoolean()
                ? new ItemStack(Items.IRON_INGOT, 1 + serverLevel.getRandom().nextInt(2))
                : new ItemStack(Items.GOLD_INGOT, 1 + serverLevel.getRandom().nextInt(2));
        ItemEntity drop = zombie.spawnAtLocation(loot);
        if (drop != null) {
            drop.setGlowingTag(true);
        }
    }

    @SubscribeEvent
    public static void onPlayerLoggedIn(PlayerEvent.PlayerLoggedInEvent event) {
        if (event.getEntity() instanceof ServerPlayer player) {
            MoonEventManager.syncTo(player);
            applyPlayerHealth(player);
        }
    }

    /** 死亡重生与跨维度都会重建玩家实体，属性虽会被拷走，仍在这里确认一遍。 */
    @SubscribeEvent
    public static void onPlayerClone(PlayerEvent.Clone event) {
        applyPlayerHealth(event.getEntity());
    }

    /** 玩家生命上限修饰符的固定 UUID（反复登录不会叠成 +160）。 */
    private static final UUID PLAYER_HEALTH_ID =
            UUID.fromString("7f4a2c81-9e35-4d6b-8c10-2a5e6b3f9d47");

    /**
     * 把玩家的生命上限顶到 {@link Config#PLAYER_MAX_HEALTH}。
     *
     * <p>用固定 UUID 的 <b>ADDITION 修饰符</b>，而不是去改基础值 20：基础值是原版定的，
     * 别的模组和玩家自己的 {@code /attribute} 命令都会动它；摆成「基础值 + 这 80」两边互不打架，
     * 配置填回 20 就等于关掉。</p>
     *
     * <p>血量按<b>比例</b>换算而不是无条件回满：老存档 20/20 进新世界变 100/100，
     * 而 8/20 的残血只变成 40/100。无条件回满等于每次进游戏白送一次治疗。</p>
     */
    private static void applyPlayerHealth(Player player) {
        AttributeInstance health = player.getAttribute(Attributes.MAX_HEALTH);
        if (health == null) {
            return;
        }
        double bonus = Config.PLAYER_MAX_HEALTH.get() - health.getBaseValue();
        AttributeModifier existing = health.getModifier(PLAYER_HEALTH_ID);
        if (existing != null && Math.abs(existing.getAmount() - bonus) < 1.0E-4D) {
            return;                            // 已经套好了：不动血量，登录/重生都是空操作
        }
        float before = player.getHealth();
        float beforeMax = player.getMaxHealth();
        if (existing != null) {
            health.removeModifier(existing);   // 配置改过 ⇒ 换成新的差值
        }
        if (bonus > 0.0D) {
            health.addPermanentModifier(new AttributeModifier(PLAYER_HEALTH_ID,
                    "apocalypse_player_health", bonus, AttributeModifier.Operation.ADDITION));
        }
        if (beforeMax > 0.0F) {
            player.setHealth(Math.min(player.getMaxHealth(),
                    Math.max(1.0F, before / beforeMax * player.getMaxHealth())));
        }
    }

    /**
     * A client cannot derive a zombie's tier from anything vanilla syncs, so hand it over as soon as
     * the zombie becomes visible to that player.
     */
    @SubscribeEvent
    public static void onStartTracking(PlayerEvent.StartTracking event) {
        if (!(event.getEntity() instanceof ServerPlayer player)) {
            return;
        }
        if (!(event.getTarget() instanceof Zombie zombie) || !participatesInEvolution(zombie)) {
            return;
        }
        NetworkHandler.CHANNEL.send(PacketDistributor.PLAYER.with(() -> player),
                new ZombieTierPacket(zombie.getId(), ZombieEvolution.getTierIndex(zombie)));
    }

    @SubscribeEvent
    public static void onPlayerLoggedOut(PlayerEvent.PlayerLoggedOutEvent event) {
        if (event.getEntity() instanceof ServerPlayer player
                && player.level() instanceof ServerLevel level) {
            // The boss bar is tracked per player; make sure a leaving player stops hearing about it.
            HordeManager.onPlayerLeft(level, player);
        }
    }
}
