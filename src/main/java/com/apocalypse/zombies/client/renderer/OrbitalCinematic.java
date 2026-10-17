package com.apocalypse.zombies.client.renderer;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.client.OrbitalStrikeClientState;
import net.minecraft.client.Camera;
import net.minecraft.client.CameraType;
import net.minecraft.client.Minecraft;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.client.event.ViewportEvent;

import java.lang.reflect.Method;

/**
 * 轨道打击的「见证机位」：把镜头从玩家眼里拉出去，远远地看着这一击从天而降 ——
 * 就像参考 mod（the-shooting-star）那样，玩家不再是从一个贴地的视角里「猜」发生了什么，
 * 而是看见完整的一击：锁定收束 → 光柱坠落 → 落地白光 → 弹坑一圈圈塌下去。
 *
 * <p><b>时间轴</b>（以 {@link OrbitalStrikeClientState} 的锁定/下落时长为基准）：
 * 锁定结束前 {@link #PULL_LEAD_TICKS}（0.7 s）开始从眼位平滑拉出；下落与落地全程保持远机位，
 * 落地后 {@link #HOLD_TICKS}（1.4 s）内镜头绕目标点慢摇；再用 {@link #OUT_TICKS}（0.6 s）
 * 平滑插值回玩家眼位与视角 —— 最后一帧与原版第一人称完全重合，全程没有一个硬切。</p>
 *
 * <p><b>机位怎么摆</b>：以目标点为锚，沿「目标 → 玩家」的水平方向拉出（近的一侧始终是玩家这一侧，
 * 不会忽然跑到背对玩家的面去），距离与高度按半径缩放（默认半径 24 → 44 格外、27 格高，
 * 正好把 49 格宽的弹坑连同从天而降的光柱一起装进画面）。落地后机位以
 * {@link #DRIFT_DEGREES_PER_TICK} 缓慢绕目标转，给画面一点「纪录机」的味道。</p>
 *
 * <p><b>实现</b>：挂在 {@code ViewportEvent.ComputeCameraAngles}（与 {@link OrbitalScreenFX}
 * 的镜头震动同一个挂点，震动叠在演出机位之上）。1.20.1 的 {@link Camera#setPosition} /
 * {@link Camera#setRotation} 是 protected —— 拿反射调，名字在开发环境（官方名）与生产环境
 * （SRG 名）里各查一次，全都没有就安静地放弃演出（功能退化成「不拉远」，绝不崩）。
 * 事件上的 yaw/pitch 与相机本体**都要改**：渲染矩阵读的是事件值，声音监听等读的是相机本体。</p>
 *
 * <p><b>机身可见性</b>：只有全距机位（e≈1）期间临时把相机切到第三人称（玩家模型入画，
 * 看见自己站在弹坑边上），切入/回位的过渡段保持第一人称 —— 眼位附近渲染自己的模型会穿头。
 * 演出结束原样恢复玩家自己切过的视角模式。</p>
 */
public final class OrbitalCinematic {

    /** 锁定结束前多少 tick 开始拉出（0.7 s，正好接上倒计时的「1」）。 */
    private static final int PULL_LEAD_TICKS = 14;
    /** 落地后保持全距机位的时长（1.4 s：白闪、冲击波、蘑菇云都在这段里）。 */
    private static final int HOLD_TICKS = 28;
    /** 从机位平滑回位的时长（0.6 s；HOLD+OUT = 40 = 客户端状态的余晖长度，不越界）。 */
    private static final int OUT_TICKS = 12;
    /** 落地后机位绕目标点慢摇的角速度（度/tick；40 tick 共 10°）。 */
    private static final double DRIFT_DEGREES_PER_TICK = 0.25D;
    /** 玩家离目标超过这个距离就不演（与屏幕特效的 160 格衰减半径一致，远处看了也是白看）。 */
    private static final double MAX_DISTANCE = 160.0D;
    /** 注视点比落点抬高多少（半径比例）：机位看得稍微偏上，光柱与弹坑同框。 */
    private static final double LOOK_UP_FACTOR = 0.3D;

    /** 机位距离（半径 24 → 44 格；半径小打击也小，机位跟着收）。 */
    private static double pullDistance(int radius) {
        return Mth.clamp(radius * 1.6D + 10.0D, 12.0D, 44.0D);
    }

    /** 机位高度。 */
    private static double pullHeight(int radius) {
        return Mth.clamp(radius * 0.85D + 7.0D, 8.0D, 30.0D);
    }

    // ------------------------------------------------------------------ 状态

    /** 演出期间记录玩家原本的视角模式，结束时原样还回去。null = 没在演出。 */
    private static CameraType restoreType;
    /** 机位方向角（目标 → 玩家，弧度）：演出开始时定格，途中玩家的走动/转视角不影响构图。 */
    private static float baseAngle;
    /** 本帧的演出权重（0 = 完全在玩家眼里，1 = 全距机位）。HUD 黑边 / FOV 收窄读它。 */
    private static float lastWeight;

    // ------------------------------------------------------------------ 反射（Camera.setPosition / setRotation）

    private static Method setPosition;
    private static Method setRotation;
    /** 反射拿不到就整段放弃演出（warn 一次），功能退化成「不拉远」。 */
    private static boolean reflectionDead;

    private static void resolveMethods() {
        if (setPosition != null || reflectionDead) {
            return;
        }
        try {
            // 开发环境类成员是官方名；生产环境（SRG 运行时）是 m_ 名 —— 两个名字都试。
            setPosition = findMethod("setPosition", "m_90584_",
                    double.class, double.class, double.class);
            setRotation = findMethod("setRotation", "m_90572_", float.class, float.class);
            if (setPosition == null || setRotation == null) {
                throw new NoSuchMethodException("Camera.setPosition / setRotation not found");
            }
            setPosition.setAccessible(true);
            setRotation.setAccessible(true);
        } catch (Exception e) {
            reflectionDead = true;
            ApocalypseZombies.LOGGER.warn("[轨道演出] 相机 API 反射失败，拉远演出停用。", e);
        }
    }

    private static Method findMethod(String official, String srg, Class<?>... params) {
        for (String name : new String[]{official, srg}) {
            try {
                return Camera.class.getDeclaredMethod(name, params);
            } catch (NoSuchMethodException ignored) {
            }
        }
        return null;
    }

    private OrbitalCinematic() {
    }

    // ------------------------------------------------------------------ 主入口

    /** 每帧渲染调用（在 {@code OrbitalScreenFX.shakeCamera} 之前，让落地震动叠在演出机位上）。 */
    public static void apply(ViewportEvent.ComputeCameraAngles event, Minecraft minecraft) {
        if (!inWindow()) {
            lastWeight = 0.0F;
            disengage(minecraft);
            return;
        }
        if (minecraft.player == null || minecraft.level == null
                || minecraft.player.isSpectator() || !Config.ORBITAL_STRIKE_CINEMATIC.get()
                || OrbitalStrikeClientState.distanceToPlayer() > MAX_DISTANCE) {
            lastWeight = 0.0F;
            disengage(minecraft);
            return;
        }
        resolveMethods();
        if (reflectionDead) {
            disengage(minecraft);
            return;
        }

        double elapsed = OrbitalStrikeClientState.elapsed();
        int lock = OrbitalStrikeClientState.lockTicks();
        int fall = OrbitalStrikeClientState.fallTicks();
        double cinemaStart = lock - (double) PULL_LEAD_TICKS;
        double impact = lock + (double) fall;

        float ease;
        if (elapsed < cinemaStart) {
            lastWeight = 0.0F;
            disengage(minecraft);
            return;
        } else if (elapsed < lock) {
            ease = smooth((float) ((elapsed - cinemaStart) / PULL_LEAD_TICKS));
        } else if (elapsed < impact + HOLD_TICKS) {
            ease = 1.0F;
        } else {
            // 回位段先还原视角模式：镜头正飞回眼位，眼位附近不能画自己的模型（会穿头）。
            disengage(minecraft);
            ease = 1.0F - smooth((float) ((elapsed - impact - HOLD_TICKS) / OUT_TICKS));
        }
        // 还没到全距就不切第三人称（眼位附近渲染自己的模型会穿头）；到了全距玩家入画。
        if (ease >= 0.999F) {
            engage(minecraft);
        }
        // HUD 黑边 / 长焦压缩读这个权重：与镜头的位置插值同一拍，收尾不会跳。
        lastWeight = ease;

        // 落地后慢摇：机位绕目标缓缓转过一小段弧。落地帧先冻结 2 tick（伪 hit-stop，
        // 与 OrbitalScreenFX 的白闪顶格/震动延迟同一拍），再起摇。
        double drift = 0.0D;
        long impactAge = OrbitalStrikeClientState.impactAge();
        if (impactAge >= 0) {
            drift = Math.toRadians(Math.max(0L, impactAge - 2L) * DRIFT_DEGREES_PER_TICK);
        }
        double angle = baseAngle + drift;
        int radius = OrbitalStrikeClientState.radius();
        double pull = pullDistance(radius);
        double height = pullHeight(radius);
        // dolly-in：落地后的保持段里镜头缓慢「压」向弹坑（44 → 36 格），
        // 与慢摇叠加就是「绕着一个越来越近的坑转」—— 静止机位会显得像截图。
        double push = impactAge >= 0
                ? smooth(Mth.clamp((float) impactAge / HOLD_TICKS, 0.0F, 1.0F))
                : 0.0D;
        pull *= 1.0D - 0.18D * push;
        height *= 1.0D - 0.10D * push;
        Vec3 anchor = Vec3.atCenterOf(OrbitalStrikeClientState.target());
        double vx = anchor.x + Math.cos(angle) * pull;
        double vz = anchor.z + Math.sin(angle) * pull;
        double vy = anchor.y + height;
        // 注视点：落点上方一点，让「从天而降的光柱」和「地面上的弹坑」同时进画面。
        double lookX = anchor.x;
        double lookY = anchor.y + radius * LOOK_UP_FACTOR;
        double lookZ = anchor.z;

        // 从玩家真实的眼位/视角插值过去（e 的两头正好贴合原版相机，全程无跳变）。
        float partialTick = (float) event.getPartialTick();
        Vec3 eye = minecraft.player.getEyePosition(partialTick);
        double cx = Mth.lerp(ease, eye.x, vx);
        double cy = Mth.lerp(ease, eye.y, vy);
        double cz = Mth.lerp(ease, eye.z, vz);
        float dx = (float) (lookX - cx);
        float dy = (float) (lookY - cy);
        float dz = (float) (lookZ - cz);
        float horiz = Mth.sqrt(dx * dx + dz * dz);
        float yaw = (float) (Math.toDegrees(Math.atan2(dz, dx)) - 90.0D);
        float pitch = (float) (-Math.toDegrees(Math.atan2(dy, Math.max(1.0E-4D, horiz))));
        float cyaw = Mth.rotLerp(ease, minecraft.player.getViewYRot(partialTick), yaw);
        float cpitch = Mth.lerp(ease, minecraft.player.getViewXRot(partialTick), pitch);

        try {
            setPosition.invoke(event.getCamera(), cx, cy, cz);
            setRotation.invoke(event.getCamera(), cyaw, cpitch);
        } catch (Exception e) {
            reflectionDead = true;
            disengage(minecraft);
            ApocalypseZombies.LOGGER.warn("[轨道演出] 相机调用失败，拉远演出停用。", e);
            return;
        }
        // 渲染矩阵读的是事件值，相机本体只喂声音监听等 —— 两处都改才算改了。
        event.setYaw(cyaw);
        event.setPitch(cpitch);
        // 轻微荷兰角：拉远的镜头带 1.4° 侧倾 —— 一眼就能读出「这不是第一人称」。
        event.setRoll(event.getRoll() + 1.4F * ease);
    }

    /**
     * 本帧的演出权重：0 = 完全在玩家眼里，1 = 全距机位。
     * HUD 黑边（{@link OrbitalScreenFX#renderCinematicBars}）与长焦压缩
     * （{@link OrbitalScreenFX#impactFovPunch}）都读它 —— 这样它们和镜头位置插值同一拍，
     * 不会出现「镜头还没飞回来、黑边先没了」的断层。
     */
    public static float weight() {
        return OrbitalStrikeClientState.isActive() ? lastWeight : 0.0F;
    }

    /** 演出机位是否还在（用于藏手：拉远时手里的遥控器不该跟着镜头飞）。 */
    public static boolean isEngaged() {
        return weight() > 0.01F;
    }

    /** 每客户端 tick 兜底：窗口外但还挂着第三人称（比如刚退出世界）就立刻还原。 */
    public static void tickRestore(Minecraft minecraft) {
        if (restoreType != null && !inWindow()) {
            lastWeight = 0.0F;
            disengage(minecraft);
        }
    }

    // ------------------------------------------------------------------ 内部

    /** 演出窗口：锁定末段（PULL_LEAD 前）到落地后 HOLD+OUT（= 余晖结束，isActive 同刻收尾）。 */
    private static boolean inWindow() {
        if (!OrbitalStrikeClientState.isActive()) {
            return false;
        }
        double elapsed = OrbitalStrikeClientState.elapsed();
        double cinemaStart = OrbitalStrikeClientState.lockTicks() - (double) PULL_LEAD_TICKS;
        double cinemaEnd = OrbitalStrikeClientState.lockTicks() + OrbitalStrikeClientState.fallTicks()
                + HOLD_TICKS + OUT_TICKS;
        return elapsed >= cinemaStart && elapsed <= cinemaEnd;
    }

    private static void engage(Minecraft minecraft) {
        if (restoreType != null) {
            return;
        }
        restoreType = minecraft.options.getCameraType();
        baseAngle = vantageAngle(minecraft);
        if (restoreType == CameraType.FIRST_PERSON) {
            minecraft.options.setCameraType(CameraType.THIRD_PERSON_BACK);
        }
    }

    private static void disengage(Minecraft minecraft) {
        if (restoreType == null) {
            return;
        }
        CameraType type = restoreType;
        restoreType = null;
        minecraft.options.setCameraType(type);
    }

    /** 机位方向：目标 → 玩家的水平单位向量；玩家几乎站在目标上时改用「玩家背后」。 */
    private static float vantageAngle(Minecraft minecraft) {
        Vec3 anchor = Vec3.atCenterOf(OrbitalStrikeClientState.target());
        double dx = minecraft.player.getX() - anchor.x;
        double dz = minecraft.player.getZ() - anchor.z;
        double d2 = dx * dx + dz * dz;
        if (d2 < 4.0D) {
            Vec3 back = minecraft.player.getViewVector(1.0F).multiply(1.0D, 0.0D, 1.0D).normalize();
            dx = -back.x;
            dz = -back.z;
        } else {
            double inv = 1.0D / Math.sqrt(d2);
            dx *= inv;
            dz *= inv;
        }
        return (float) Math.atan2(dz, dx);
    }

    /** smoothstep：拉出/回位的首尾速度都是 0，观感是「镜头自己滑过去」而不是匀速平移。 */
    private static float smooth(float t) {
        t = Mth.clamp(t, 0.0F, 1.0F);
        return t * t * (3.0F - 2.0F * t);
    }
}
