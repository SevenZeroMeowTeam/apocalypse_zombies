package com.apocalypse.zombies.client.anim;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.Config;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import net.minecraft.client.Minecraft;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;

import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Q 弹（squash &amp; stretch）：生物压扁、回弹、转圈。
 *
 * <p>曲线与幅度照「朋友的酒」(friendswine) 的果冻效果实现 —— 那套数据的来源是它的
 * {@code JellyAnimation} / {@code DollRenderer.applyAnimation}：</p>
 *
 * <pre>
 *   squash = smoothstep 关键帧，周期 0.91667 s，一个周期走 0 → 1 → 0 → 1 → 0
 *   scale(1 + width·s, 1 − compression·s, 1)     // Z 轴不动
 *   自转 = 绕 Y 轴，一个周期 −360°（逆时针一圈）
 * </pre>
 *
 * <p>三点和朴素写法不一样、但正是那套效果的关键：</p>
 * <ul>
 *   <li><b>smoothstep 而不是正弦</b>：每段是 {@code 3t² − 2t³}，两端速度为零 —— 所以是「duang」
 *       地弹一下再停住，而不是一直匀速晃。</li>
 *   <li><b>Z 轴不缩放</b>：只压宽度与高度。这是正面压扁，不是体积守恒的压扁；配合绕 Y 自转，
 *       形变方向跟着转，正面看始终是标准的卡通压扁。</li>
 *   <li><b>锚点在脚底</b>：钩子触发时 PoseStack 的原点正落在脚底，所以直接 scale 就是绕脚底压，
 *       不会陷进地里，也不需要「抬到中心再落回」那层三明治。</li>
 * </ul>
 *
 * <p>在这层持续律动之上，受击 / 落地 / 被击退会再叠一次更强的冲击（取两者中更狠的那个），
 * 让打中东西时还有额外的反馈。</p>
 *
 * <p>纯客户端：专用服务器不加载这个类。</p>
 */
public final class SquashStretch {

    /** 一个律动周期的长度，秒 —— 与参考实现同值。 */
    public static final double PERIOD = 0.91667D;

    /** 关键帧：一个周期内两次「压到底」。取值与参考实现逐字相同。 */
    private static final double[] JELLY_TIMES = {0.0D, 0.25D, 0.45833D, 0.70833D, 0.91667D};
    private static final double[] JELLY_VALUES = {0.0D, 1.0D, 0.0D, 1.0D, 0.0D};

    /** 低于这个缩放差就不值得动矩阵了。 */
    private static final float DEAD_ZONE = 0.002F;

    /** 冲击的存活上限：超过这个 tick 数振幅已衰减到看不见。 */
    private static final int MAX_AGE_TICKS = 60;

    private static final Map<Integer, Impact> IMPACTS = new ConcurrentHashMap<>();
    /** 上一帧看到的血量 —— 受伤检测看它掉没掉。 */
    private static final Map<Integer, Float> LAST_HEALTH = new ConcurrentHashMap<>();
    private static final Map<Integer, Boolean> LAST_ON_GROUND = new ConcurrentHashMap<>();
    private static final Map<Integer, Double> LAST_VY = new ConcurrentHashMap<>();
    private static final Map<Integer, Double> LAST_HORIZONTAL = new ConcurrentHashMap<>();
    /** 本帧已经 push 过的实体：Pre 可被别的模组取消（取消后 Post 不触发），所以 pop 靠这个集合兜底。 */
    private static final Set<Integer> PUSHED = ConcurrentHashMap.newKeySet();

    /** 只在第一次真正形变时写一行日志，用来证明事件确实接上了。 */
    private static boolean announced;

    private SquashStretch() {
    }

    private static final class Impact {
        int ageTicks;
        float strength;
    }

    // ------------------------------------------------------------------ 曲线

    /** 周期内的相位，0 … {@link #PERIOD}。 */
    public static double phase(double seconds) {
        return Math.max(0.0D, seconds) % PERIOD;
    }

    /**
     * 持续律动的压扁量，0 … 1：一个周期里走 0 → 1 → 0 → 1 → 0，两段各用 smoothstep
     * （{@code 3t² − 2t³}）插值，所以每一下都是「弹到位再停住」。
     */
    public static float jelly(double seconds) {
        double g = phase(seconds);
        int i = 0;
        while (i < JELLY_TIMES.length - 2 && g > JELLY_TIMES[i + 1]) {
            i++;
        }
        double span = JELLY_TIMES[i + 1] - JELLY_TIMES[i];
        double t = span <= 1.0E-9D ? 0.0D : (g - JELLY_TIMES[i]) / span;
        double eased = t * t * (3.0D - 2.0D * t);
        return (float) (JELLY_VALUES[i] + (JELLY_VALUES[i + 1] - JELLY_VALUES[i]) * eased);
    }

    /** 自转角度（度）：一个周期转一整圈，负号 = 逆时针，与参考实现同向。 */
    public static float spin(double seconds) {
        return (float) (-360.0D * phase(seconds) / PERIOD);
    }

    /** 横向鼓起的倍率：{@code 1 + width/100 · squash}。 */
    public static float widthScale(float squash) {
        return 1.0F + Config.SQUASH_WIDTH.get().floatValue() / 100.0F * squash;
    }

    /** 高度压缩的倍率：{@code 1 − compression/100 · squash}。 */
    public static float heightScale(float squash) {
        return 1.0F - Config.SQUASH_COMPRESSION.get().floatValue() / 100.0F * squash;
    }

    // ------------------------------------------------------------------ 观察（冲击层）

    /**
     * 受伤：看血量掉没掉。
     *
     * <p>不能用 {@code hurtTime}：1.20.1 里受伤动画走 {@code ClientboundHurtAnimationPacket}，
     * 而构造那个包的地方只有 {@code ServerPlayer} 一处（它只把「自己被打」发给自己）——
     * 除玩家本人外，任何生物的 {@code hurtTime} 在客户端永远是 0。血量走
     * {@code SynchedEntityData}，对所有生物都同步。</p>
     */
    public static void observeHurt(LivingEntity entity) {
        int id = entity.getId();
        float health = entity.getHealth() + entity.getAbsorptionAmount();
        Float prev = LAST_HEALTH.put(id, health);
        if (prev == null || health >= prev - 0.01F) {
            return;
        }
        float lost = prev - health;
        float max = Math.max(1.0F, entity.getMaxHealth());
        trigger(entity, Math.min(1.0F, 0.5F + lost / max * 2.2F));
    }

    /** 落地 / 起跳 / 被击退：只用客户端已有的运动学字段。 */
    public static void observeMotion(LivingEntity entity) {
        int id = entity.getId();
        boolean onGround = entity.onGround();
        double vy = entity.getDeltaMovement().y;
        double horizontal = entity.getDeltaMovement().horizontalDistance();

        Boolean prevGround = LAST_ON_GROUND.put(id, onGround);
        Double prevVy = LAST_VY.put(id, vy);
        Double prevHorizontal = LAST_HORIZONTAL.put(id, horizontal);

        if (prevGround != null && prevVy != null) {
            if (!prevGround && onGround && prevVy < -0.30D) {
                trigger(entity, (float) Math.min(1.0D, 0.5D + Math.abs(prevVy) / 1.4D) * 0.85F);
            } else if (prevGround && !onGround && vy > 0.30D) {
                trigger(entity, 0.45F);
            }
        }
        if (prevHorizontal != null && prevGround != null && prevGround && onGround) {
            double jump = horizontal - prevHorizontal;
            if (jump > 0.32D) {
                trigger(entity, (float) Math.min(0.75D, 0.35D + jump / 1.6D));
            }
        }
    }

    private static void trigger(LivingEntity entity, float strength) {
        if (strength <= 0.0F) {
            return;
        }
        int id = entity.getId();
        Impact impact = IMPACTS.computeIfAbsent(id, k -> new Impact());
        impact.strength = Math.max(impact.strength * 0.35F, Math.min(1.0F, strength));
        impact.ageTicks = 0;
    }

    // ------------------------------------------------------------------ 施加

    /**
     * 往 PoseStack 上叠加本帧形变。调用方保证与 {@link #popIfApplied} 成对。
     *
     * @return true 表示确实 push 了（配对由内部集合兜底）
     */
    public static boolean apply(LivingEntity entity, PoseStack pose, float partialTick) {
        if (!Config.SQUASH_ENABLED.get()) {
            return false;
        }
        if (entity instanceof Player) {
            // 玩家渲染会同时触发 RenderPlayerEvent 与 RenderLivingEvent —— 两边都做就是双倍形变。
            return false;
        }
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.level == null) {
            return false;
        }

        // 律动：相位取世界时间，于是同一维度里所有生物踩着同一个节拍（参考实现是跟玩偶的音乐走，
        // 我们这里没有玩偶，用世界时间即可 —— 玩家的背景音乐也是从进世界那一刻开始放的）。
        double seconds = (minecraft.level.getGameTime() + partialTick) / 20.0D;
        float squash = jelly(seconds) * Config.SQUASH_SWAY.get().floatValue();

        // 冲击：受伤 / 落地 / 被击退再压一下，谁更狠听谁的
        Impact impact = IMPACTS.get(entity.getId());
        if (impact != null) {
            float t = (impact.ageTicks + partialTick) / 20.0F;
            float wave = (float) (Math.exp(-t * Config.SQUASH_DAMPING.get())
                    * Math.cos(t * Config.SQUASH_FREQUENCY.get()));
            float shock = impact.strength * wave;
            if (shock > squash) {
                squash = shock;
            }
        }
        if (squash < 0.0F) {
            squash = 0.0F;
        }

        float spinDegrees = 0.0F;
        if (Config.SQUASH_ROTATE.get()) {
            spinDegrees = spin(seconds) * Config.SQUASH_SPIN_SPEED.get().floatValue();
        }

        // 绕圈：身体沿一个小圆周走（参考实现管这个叫「逆时针绕圈」）。用自己的相位而不是 spinDegrees，
        // 这样即使把自转关掉、绕圈照样转；相位在周期边界连续（cos/sin 走满一圈回到原点）。
        float orbitRadius = Config.SQUASH_ORBIT.get().floatValue();
        double orbitX = 0.0D;
        double orbitZ = 0.0D;
        if (orbitRadius > 0.0F) {
            double theta = -2.0D * Math.PI * phase(seconds) / PERIOD
                    * Config.SQUASH_SPIN_SPEED.get().floatValue();
            orbitX = Math.cos(theta) * orbitRadius;
            orbitZ = Math.sin(theta) * orbitRadius;
        }

        float xScale = widthScale(squash);
        float yScale = heightScale(squash);
        if (Math.abs(xScale - 1.0F) < DEAD_ZONE && Math.abs(yScale - 1.0F) < DEAD_ZONE
                && Math.abs(spinDegrees) < 0.01F && orbitRadius <= 0.0F) {
            return false;
        }

        pose.pushPose();
        if (orbitRadius > 0.0F) {
            pose.translate(orbitX, 0.0D, orbitZ);
        }
        if (spinDegrees != 0.0F) {
            pose.mulPose(Axis.YP.rotationDegrees(spinDegrees));
        }
        // Z 轴不缩放 —— 与参考实现一致：只压宽度与高度（正面压扁）
        pose.scale(xScale, yScale, 1.0F);
        PUSHED.add(entity.getId());

        if (!announced) {
            announced = true;
            ApocalypseZombies.LOGGER.info("[Q弹] 已生效：{} 正在做果冻律动（压扁 {} / 鼓起 {} / 自转 {}°）",
                    entity.getName().getString(),
                    String.format("%.3f", yScale), String.format("%.3f", xScale),
                    String.format("%.1f", spinDegrees));
        }
        return true;
    }

    /** 与 {@link #apply} 严格配对：只有本帧真的 push 过才 pop。 */
    public static void popIfApplied(LivingEntity entity, PoseStack pose) {
        if (PUSHED.remove(entity.getId())) {
            pose.popPose();
        }
    }

    // ------------------------------------------------------------------ 驱动

    /** 每客户端 tick 推进冲击的年龄并回收过期记录。 */
    public static void tick() {
        if (IMPACTS.isEmpty() && LAST_HEALTH.isEmpty()) {
            return;
        }
        for (Impact impact : IMPACTS.values()) {
            impact.ageTicks++;
        }
        IMPACTS.entrySet().removeIf(entry -> entry.getValue().ageTicks > MAX_AGE_TICKS);

        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.level == null) {
            clear();
            return;
        }
        if (minecraft.level.getGameTime() % 200L == 0L) {
            prune(LAST_HEALTH, minecraft);
            prune(LAST_ON_GROUND, minecraft);
            prune(LAST_VY, minecraft);
            prune(LAST_HORIZONTAL, minecraft);
        }
    }

    private static void prune(Map<Integer, ?> table, Minecraft minecraft) {
        table.keySet().removeIf(id -> !(minecraft.level.getEntity(id) instanceof LivingEntity));
    }

    /** 退出世界时整体清空：世界换了，实体 id 空间也换了。 */
    public static void clear() {
        IMPACTS.clear();
        LAST_HEALTH.clear();
        LAST_ON_GROUND.clear();
        LAST_VY.clear();
        LAST_HORIZONTAL.clear();
        PUSHED.clear();
    }

    /** 仅供调试：当前有多少只怪带着未衰减完的冲击。 */
    public static int activeCount() {
        return IMPACTS.size();
    }
}
