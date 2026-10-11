package com.apocalypse.zombies.item;

import com.apocalypse.zombies.Config;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.SoundType;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;

/**
 * 子弹与方块的约定：<b>叶子放行、玻璃打碎</b>，其余照旧挡住。
 *
 * <p>玩家那 8 把枪原来各自抄了一遍 {@code level.clip(... COLLIDER ...)}，射线撞到什么就结算在什么上 ——
 * 包括一片树叶。这里把那段统一收进来：撞上树叶就从叶背接着往前找，直到撞上真挡路的东西
 * （墙、地、玻璃……）；撞上玻璃先打碎，再按 {@link Config#BULLETS_PASS_GLASS} 决定停在原地还是继续飞。</p>
 *
 * <p>怪物那发子弹是实体，命中判定在原版 {@code Projectile} 里、插不上手，所以换一条路：
 * 撞上之后不消散，改判成「从叶背继续飞」——见 {@link #resolveProjectileHit}。规则与玩家那条完全同源，
 * 同一份配置管两边。</p>
 *
 * <p>口径上只认两件事：<b>树叶</b>看原版 {@code minecraft:leaves} 标签（带这个标签的模组树叶一样放行）；
 * <b>玻璃</b>看原版 {@code SoundType.GLASS}（玻璃、玻璃板、染色玻璃、遮光玻璃一网打尽，不写死方块 id）。
 * 打不动的方块（信标那种硬度 -1）与带方块实体的方块一律不动 —— 子弹不该能拆家。</p>
 */
public final class BulletRay {

    /** 一条射线最多连穿这么多块叶子；再多就按命中结算（防病态密林把这一枪算成死循环）。 */
    private static final int MAX_SKIPS = 64;

    /** 穿出去之后多走 1 mm：足够让下一段射线不再咬到刚穿过的这一块。 */
    private static final double SKIN = 1.0E-3D;

    private BulletRay() {
    }

    /**
     * 玩家枪械那条「眼睛射线」：语义与 {@code level.clip(eye, reach, COLLIDER, NONE, shooter)} 一致，
     * 只多两件事 —— 命中树叶从叶背继续走，命中玻璃先打碎。
     *
     * @return 最终挡下这一枪的方块命中（没有东西挡就是 {@link HitResult.Type#MISS}）
     */
    public static BlockHitResult trace(Level level, Entity shooter, Vec3 from, Vec3 to) {
        Vec3 start = from;
        for (int i = 0; i < MAX_SKIPS; i++) {
            BlockHitResult hit = level.clip(new ClipContext(start, to,
                    ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, shooter));
            if (hit.getType() != HitResult.Type.BLOCK) {
                return hit;
            }
            Vec3 dir = to.subtract(start);
            if (dir.lengthSqr() < 1.0E-9D) {
                return hit;
            }
            dir = dir.normalize();

            BlockPos pos = hit.getBlockPos();
            BlockState state = level.getBlockState(pos);
            boolean leaves = Config.BULLETS_PASS_LEAVES.get() && isLeaves(state);
            boolean glass = Config.BULLETS_BREAK_GLASS.get() && isGlass(level, pos, state);
            if (!leaves && !glass) {
                return hit;
            }

            if (leaves) {
                // 叶子蹭出一小撮绿粒子，让「打穿了」看得见
                puff(level, hit.getLocation());
            }
            if (glass) {
                shatter(level, pos);
                if (!Config.BULLETS_PASS_GLASS.get()) {
                    return hit;
                }
            }

            // 叶子要算叶背出口；碎掉的玻璃已经是空气，往前挪 1 mm 就够
            Vec3 exit = leaves ? exitOf(level, pos, state, hit.getLocation(), dir) : null;
            Vec3 next = exit != null ? exit : hit.getLocation().add(dir.scale(SKIN));
            if (next.distanceToSqr(to) >= start.distanceToSqr(to)) {
                return hit; // 没往前走动就没什么可穿的，按命中结算
            }
            start = next;
        }
        return miss(to);
    }

    /**
     * 怪物那发实体子弹撞上方块时的处理。
     *
     * @return {@code true} = 这一发不算命中、别消散（叶子放行 / 玻璃碎完继续飞）
     */
    public static boolean resolveProjectileHit(Level level, Entity bullet, BlockHitResult hit) {
        BlockPos pos = hit.getBlockPos();
        BlockState state = level.getBlockState(pos);

        if (Config.BULLETS_PASS_LEAVES.get() && isLeaves(state)) {
            Vec3 motion = bullet.getDeltaMovement();
            if (motion.lengthSqr() < 1.0E-9D) {
                return false;
            }
            Vec3 exit = exitOf(level, pos, state, hit.getLocation(), motion.normalize());
            if (exit == null) {
                return false;
            }
            puff(level, hit.getLocation());
            bullet.setPos(exit.x, exit.y, exit.z);
            return true;
        }

        if (Config.BULLETS_BREAK_GLASS.get() && isGlass(level, pos, state)) {
            shatter(level, pos);
            // 玻璃已经没了，想接着飞就直接飞；不然跟打墙一样停下
            return Config.BULLETS_PASS_GLASS.get();
        }
        return false;
    }

    /** 树叶：认原版 {@code minecraft:leaves} 标签。 */
    public static boolean isLeaves(BlockState state) {
        return state.is(BlockTags.LEAVES);
    }

    /**
     * 玻璃：看原版 {@code SoundType.GLASS}，玻璃 / 玻璃板 / 染色玻璃 / 遮光玻璃全在里头，
     * 模组玻璃只要声音类型对也一样算。打不动的（硬度 -1）与带方块实体的排除掉。
     */
    public static boolean isGlass(Level level, BlockPos pos, BlockState state) {
        if (state.isAir() || state.hasBlockEntity()) {
            return false;
        }
        if (state.getDestroySpeed(level, pos) < 0.0F) {
            return false;
        }
        return state.getSoundType() == SoundType.GLASS;
    }

    /** 打碎：走原版 {@code destroyBlock(pos, true)} —— 音效、粒子、邻块更新都照原版来。 */
    private static void shatter(Level level, BlockPos pos) {
        if (level.isClientSide()) {
            return;
        }
        level.destroyBlock(pos, true);
    }

    /**
     * 从 {@code from} 沿 {@code dir} 走出 {@code pos} 这一块的碰撞盒的位置（叶背出口）。
     *
     * <p>用碰撞盒而不是整格：树叶在个别资源包里不是满方块，按整格算会多穿一截。
     * 三个轴各自求「到远侧那个面的 t」取最小，就是从盒子里出来的那一刻。</p>
     *
     * @return 出口坐标（已往外挪 {@link #SKIN}）；算不出来返回 {@code null}
     */
    private static Vec3 exitOf(Level level, BlockPos pos, BlockState state, Vec3 from, Vec3 dir) {
        AABB box = state.getCollisionShape(level, pos).isEmpty()
                ? new AABB(pos)
                : state.getCollisionShape(level, pos).bounds().move(pos);
        double t = Double.MAX_VALUE;
        if (dir.x > 1.0E-7D) {
            t = Math.min(t, (box.maxX - from.x) / dir.x);
        } else if (dir.x < -1.0E-7D) {
            t = Math.min(t, (box.minX - from.x) / dir.x);
        }
        if (dir.y > 1.0E-7D) {
            t = Math.min(t, (box.maxY - from.y) / dir.y);
        } else if (dir.y < -1.0E-7D) {
            t = Math.min(t, (box.minY - from.y) / dir.y);
        }
        if (dir.z > 1.0E-7D) {
            t = Math.min(t, (box.maxZ - from.z) / dir.z);
        } else if (dir.z < -1.0E-7D) {
            t = Math.min(t, (box.minZ - from.z) / dir.z);
        }
        if (t == Double.MAX_VALUE || t < 0.0D || !Double.isFinite(t)) {
            return null;
        }
        return from.add(dir.scale(t + SKIN));
    }

    /** 打穿叶子时那一撮绿粒子（骨粉同款，服务端发）。 */
    private static void puff(Level level, Vec3 at) {
        if (!(level instanceof ServerLevel server)) {
            return;
        }
        server.sendParticles(ParticleTypes.COMPOSTER, at.x, at.y, at.z, 4, 0.15D, 0.15D, 0.15D, 0.02D);
    }

    /** 跟原版 clip 的兜底一样：射线走完什么都没撞上。 */
    private static BlockHitResult miss(Vec3 to) {
        return BlockHitResult.miss(to, Direction.getNearest(to.x, to.y, to.z), BlockPos.containing(to));
    }
}
