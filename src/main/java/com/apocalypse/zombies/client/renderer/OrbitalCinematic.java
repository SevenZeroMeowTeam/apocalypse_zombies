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
    /** 宇宙激光「灵魂出窍」的最低高度（绝对 Y）：卫星在 466，所以至少升到这里。 */
    private static final double SOUL_HEIGHT = 460.0D;
    /** 灵魂出窍上升至轨道视点；随后留出独立太空发射镜头，不压缩进普通锁定收尾。 */
    private static final int SOUL_PULL_LEAD_TICKS = 40;
    /** 发射前太空构图停留时长。 */
    private static final int SOUL_SPACE_HOLD_TICKS = 30;
    /** 发射后展示卫星光束穿过行星的时长。 */
    private static final int SOUL_BEAM_HOLD_TICKS = 35;
    /** 发射后回看地面贯穿效果的短镜头。 */
    private static final int SOUL_GROUND_HOLD_TICKS = 20;
    /** 演出最后回到玩家眼位；不依赖世界挖掘余晖的长度。 */
    private static final int SOUL_OUT_TICKS = 24;
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

    /** 所有弹种都走轨道机位：打击一律从外太空发起，地面上不再出现「天际线」。 */
    private static boolean isSpaceShot() {
        return true;
    }

    /** 拉出时长：要飞 400 格到轨道，慢一点才不像瞬移。 */
    public static int pullLeadTicks() {
        return isSpaceShot() ? SOUL_PULL_LEAD_TICKS : PULL_LEAD_TICKS;
    }

    private static int holdTicks() {
        return isSpaceShot()
                ? SOUL_SPACE_HOLD_TICKS + SOUL_BEAM_HOLD_TICKS + SOUL_GROUND_HOLD_TICKS
                : HOLD_TICKS;
    }

    private static int outTicks() {
        return isSpaceShot() ? SOUL_OUT_TICKS : OUT_TICKS;
    }

    /** 轨道展示段的长度（供屏幕转场计算「返回大气层」的时刻）。 */
    public static int spaceHoldTicks() {
        return holdTicks();
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
            // 权重必须归零：太空舞台/黑边都读它，留着旧值会「没有镜头却把世界遮黑」。
            lastWeight = 0.0F;
            disengage(minecraft);
            return;
        }

        double elapsed = OrbitalStrikeClientState.elapsed();
        int lock = OrbitalStrikeClientState.lockTicks();
        int fall = OrbitalStrikeClientState.fallTicks();
        int pullLead = pullLeadTicks();
        int hold = holdTicks();
        int out = outTicks();
        double cinemaStart = lock - (double) pullLead;
        double impact = lock + (double) fall;
        double cinemaEnd = impact + hold + out;

        float ease;
        if (elapsed < cinemaStart) {
            lastWeight = 0.0F;
            disengage(minecraft);
            return;
        } else if (elapsed < lock) {
            ease = smooth((float) ((elapsed - cinemaStart) / Math.max(1, pullLead)));
        } else if (elapsed < impact + hold) {
            ease = 1.0F;
        } else if (elapsed <= cinemaEnd) {
            // 回位段先还原视角模式：镜头正飞回眼位，眼位附近不能画自己的模型（会穿头）。
            disengage(minecraft);
            ease = 1.0F - smooth((float) ((elapsed - impact - hold) / Math.max(1, out)));
        } else {
            lastWeight = 0.0F;
            disengage(minecraft);
            return;
        }
        // 还没到全距就不切第三人称（眼位附近渲染自己的模型会穿头）；到了全距玩家入画。
        if (ease >= 0.999F) {
            engage(minecraft);
        }
        // HUD 黑边 / 长焦压缩读这个权重：与镜头的位置插值同一拍，收尾不会跳。
        lastWeight = ease;

        // 全部弹种共用同一套轨道机位：升到 Y≥460、水平外移、看地球弧面。
        // 落点只决定「地球上的哪一块」，机位角度仍按玩家所在方向定，构图稳定。
        long impactAge = OrbitalStrikeClientState.impactAge();
        double elapsedAfterImpact = elapsed - impact;
        double angle = baseAngle;
        int radius = OrbitalStrikeClientState.radius();
        Vec3 anchor = Vec3.atCenterOf(OrbitalStrikeClientState.target());
        double pull = Mth.clamp(radius * 2.0D + 34.0D, 72.0D, 150.0D);
        double height = Math.max(anchor.y + 92.0D, SOUL_HEIGHT) - anchor.y;
        double lookX = anchor.x;
        double lookY = anchor.y + radius * LOOK_UP_FACTOR;
        double lookZ = anchor.z;
        {
            double lockProgress = Mth.clamp((elapsed - (lock - pullLead)) / Math.max(1.0D, pullLead), 0.0D, 1.0D);
            double phase = elapsedAfterImpact;
            double groundBlend = phase < SOUL_SPACE_HOLD_TICKS + SOUL_BEAM_HOLD_TICKS
                    ? 0.0D
                    : smooth((float) Mth.clamp((phase - SOUL_SPACE_HOLD_TICKS - SOUL_BEAM_HOLD_TICKS)
                    / SOUL_GROUND_HOLD_TICKS, 0.0D, 1.0D));
            // 锁定阶段先盯住蓝白轨道目标；命中后留在轨道看投放/光束，最后短暂俯回地面，
            // 交代真实落点（此时太空底已淡出，世界里的贯穿效果接上）。
            double orbitalLookY = anchor.y + 300.0D;
            double launchLookY = anchor.y + 245.0D;
            double groundLookY = anchor.y + radius * 0.9D;
            if (elapsed < lock) {
                lookY = Mth.lerp((float) smooth((float) lockProgress),
                        anchor.y + radius * 1.6D, orbitalLookY);
            } else if (phase < SOUL_SPACE_HOLD_TICKS) {
                lookY = orbitalLookY;
            } else if (phase < SOUL_SPACE_HOLD_TICKS + SOUL_BEAM_HOLD_TICKS) {
                lookY = launchLookY;
            } else {
                lookY = Mth.lerp((float) groundBlend, launchLookY, groundLookY);
            }
        }
        double vx = anchor.x + Math.cos(angle) * pull;
        double vz = anchor.z + Math.sin(angle) * pull;
        double vy = anchor.y + height;

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
            lastWeight = 0.0F;
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

    /** 保存的本地降水（<0 = 当前没有压制）。 */
    private static float savedRain = -1.0F;
    private static float savedThunder = -1.0F;

    /**
     * 太空演出期间把本地降水压到 0。
     *
     * <p>原版雨雪是绕着<b>相机</b>画的（±10 格），镜头升到 Y=460 以后雨丝就悬在太空底前面，
     * 一眼破戏。这里只改客户端视觉字段（不发包、不改服务器天气），演出结束原样恢复；
     * 若服务器恰好在窗口内改变了天气，下一次天气包会重新同步。</p>
     */
    public static void tickWeather(Minecraft minecraft) {
        if (minecraft.level == null) {
            savedRain = -1.0F;
            return;
        }
        if (isSpaceStage()) {
            if (savedRain < 0.0F) {
                savedRain = minecraft.level.rainLevel;
                savedThunder = minecraft.level.thunderLevel;
            }
            minecraft.level.setRainLevel(0.0F);
            minecraft.level.setThunderLevel(0.0F);
            // 同时清掉插值源，否则 getRainLevel(partial) 还会从旧值淡出一帧。
            minecraft.level.oRainLevel = 0.0F;
            minecraft.level.oThunderLevel = 0.0F;
        } else if (savedRain >= 0.0F) {
            minecraft.level.setRainLevel(savedRain);
            minecraft.level.setThunderLevel(savedThunder);
            minecraft.level.oRainLevel = savedRain;
            minecraft.level.oThunderLevel = savedThunder;
            savedRain = -1.0F;
        }
    }

    /** 太空舞台只在轨道过场内绘制；落点挖掘/余晖不触发全屏空间遮罩。 */
    public static boolean isSpaceStage() {
        Minecraft minecraft = Minecraft.getInstance();
        if (!isSpaceShot() || !Config.ORBITAL_STRIKE_CINEMATIC.get()
                || !OrbitalStrikeClientState.isActive() || minecraft.player == null || minecraft.level == null
                || minecraft.player.isSpectator()
                || OrbitalStrikeClientState.distanceToPlayer() > MAX_DISTANCE) {
            return false;
        }
        double elapsed = OrbitalStrikeClientState.elapsed();
        double lock = OrbitalStrikeClientState.lockTicks();
        double start = lock - SOUL_PULL_LEAD_TICKS;
        double impact = lock + OrbitalStrikeClientState.fallTicks();
        double end = impact + SOUL_SPACE_HOLD_TICKS + SOUL_BEAM_HOLD_TICKS
                + SOUL_GROUND_HOLD_TICKS + SOUL_OUT_TICKS;
        return elapsed >= start && elapsed <= end && lastWeight > 0.01F;
    }

    /**
     * 太空布景的不透明度：发射段全开，最后一段「压回地面」时淡出，
     * 让真实世界的地表/光柱在回位前先露出来（否则会从黑箱里硬切回世界）。
     */
    public static float spaceOpacity() {
        if (!isSpaceStage()) {
            return 0.0F;
        }
        double elapsed = OrbitalStrikeClientState.elapsed();
        double lock = OrbitalStrikeClientState.lockTicks();
        double impact = lock + OrbitalStrikeClientState.fallTicks();
        double phase = elapsed - impact;
        double fadeStart = SOUL_SPACE_HOLD_TICKS + SOUL_BEAM_HOLD_TICKS;
        if (phase <= fadeStart) {
            return 1.0F;
        }
        return Mth.clamp((float) (1.0D - (phase - fadeStart) / Math.max(1.0D, SOUL_GROUND_HOLD_TICKS)),
                0.0F, 1.0F);
    }

    /** 开火进度 0..1：锁定末段充能，服务端命中时刻打满（各弹种共用同一拍）。 */
    public static float spaceFireProgress() {
        if (!isSpaceStage()) {
            return 0.0F;
        }
        double elapsed = OrbitalStrikeClientState.elapsed();
        double lock = OrbitalStrikeClientState.lockTicks();
        double impact = lock + OrbitalStrikeClientState.fallTicks();
        // 光束在锁定末尾充能、在服务端命中时刻打满：视觉发射点与真实结算同拍，
        // 之后的太空镜头只是让观众看清「卫星 → 行星 → 地表」这条线。
        double beamStart = lock - 10.0D;
        double beamEnd = impact + 2.0D;
        return Mth.clamp((float) ((elapsed - beamStart) / Math.max(1.0D, beamEnd - beamStart)), 0.0F, 1.0F);
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
        double cinemaStart = OrbitalStrikeClientState.lockTicks() - (double) pullLeadTicks();
        double cinemaEnd = OrbitalStrikeClientState.lockTicks() + OrbitalStrikeClientState.fallTicks()
                + holdTicks() + outTicks();
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
