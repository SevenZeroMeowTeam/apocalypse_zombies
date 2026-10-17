package com.apocalypse.zombies.item;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.event.OrbitalStrikeManager;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResultHolder;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;

/**
 * 轨道打击遥控器：手持这件物品时，准星处持续显示一个空心立方体选区（边长 = 选区边长），
 * 右键触发后，1.5 s 锁定 + 从 Y=320 落下能量光柱 + 摧毁选区内方块 + 中心 AOE 伤害生物。
 *
 * <p>权限、冷却、保护名单都在 {@link OrbitalStrikeManager} 一处收口，物品本身只负责
 * 「把准星点传给 manager」+「扣冷却」两件。客户端的描边由
 * {@code com.apocalypse.zombies.client.renderer.OrbitalStrikeHighlighter} 单独负责 —— 
 * 它直接读 {@code minecraft.hitResult}，不依赖这个 item 的 state（避免 NBT 同步）。</p>
 */
public class OrbitalStrikeRemoteItem extends Item {

    /** 服务器侧最大瞄准距离。超过这个距离直接对空地打（仍以射线终点为方块中心）。 */
    private static final double PICK_REACH = 160.0D;

    public OrbitalStrikeRemoteItem(Properties properties) {
        super(properties);
    }

    @Override
    public InteractionResultHolder<ItemStack> use(Level level, Player player, InteractionHand hand) {
        ItemStack stack = player.getItemInHand(hand);
        if (!Config.ORBITAL_STRIKE_ENABLED.get()) {
            return InteractionResultHolder.pass(stack);
        }
        // 客户端：use 也要 consume，否则连按右键会反复跑「长按 + 松手」的预测逻辑。
        if (level.isClientSide()) {
            return InteractionResultHolder.consume(stack);
        }
        if (!(player instanceof ServerPlayer serverPlayer)) {
            return InteractionResultHolder.pass(stack);
        }
        // 冷却为 0 表示「完全无冷却」：跳过 isOnCooldown 检查，也不写冷却。
        int cooldownSeconds = Config.ORBITAL_STRIKE_COOLDOWN.get();
        if (cooldownSeconds > 0 && player.getCooldowns().isOnCooldown(this)) {
            return InteractionResultHolder.fail(stack);
        }
        // 准星取点：射线末端必须是 BLOCK 才算「瞄到地」—— 瞄到空气就让玩家自己再想想。
        HitResult hit = player.pick(PICK_REACH, 0.0F, false);
        if (!(hit instanceof BlockHitResult blockHit) || blockHit.getType() != HitResult.Type.BLOCK) {
            return InteractionResultHolder.fail(stack);
        }
        OrbitalStrikeManager.schedule(serverPlayer, blockHit.getBlockPos().immutable());
        if (cooldownSeconds > 0) {
            player.getCooldowns().addCooldown(this, cooldownSeconds * 20);
        }
        return InteractionResultHolder.consume(stack);
    }
}
