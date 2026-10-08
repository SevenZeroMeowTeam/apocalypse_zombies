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
 * Q 弹（squash &amp; stretch）状态机：生物受到冲击时被压扁、XZ 鼓起，随后带旋转地阻尼回弹。
 *
 * <p>锚点在<b>脚底</b>：两个渲染钩子（{@code RenderLivingEvent.Pre} 与
 * {@code GeoRenderEvent.Entity.Pre}）触发时，PoseStack 里只有「相机 → 实体世界坐标」，
 * 原点正落在脚底，所以在这里缩放天然不会把怪压进地里。要让形变像果冻而不是
 * 「从地面长出来」，再套一层 {@code 抬到身体中心 → 缩放 → 落回脚底} 的三明治。</p>
 *
 * <p><b>为什么不发包</b>：受伤读血量（见 {@link #observeHurt}），落地/起跳/击退用客户端自己
 * 逐 tick 追踪的 {@code onGround} 与 {@code deltaMovement}，都是客户端已经拿得到的东西。
 * 因此整套效果是纯客户端的，服务端（含专用服务器）不需要加载这个类。</p>
 *
 * <p><b>观察时机</b>：只在渲染钩子里「顺便观察」，不做全实体扫描 —— 这样血月围城里
 * 上百只怪也不会多出一轮遍历，天然只处理屏幕上可见的实体。</p>
 */
public final class SquashStretch {

    /** 冲击的存活上限：超过这个 tick 数振幅已衰减到看不见，直接回收。 */
    private static final int MAX_AGE_TICKS = 60;

    /** 低于这个缩放差就不值得动矩阵了（省掉一次 push/pop 与矩阵乘法）。 */
    private static final float DEAD_ZONE = 0.002F;

    private static final Map<Integer, Impact> IMPACTS = new ConcurrentHashMap<>();
    /**
     * 上一帧看到的血量。受伤检测就看它掉没掉 —— 见 {@link #observeHurt} 里为什么不用 hurtTime。
     */
    private static final Map<Integer, Float> LAST_HEALTH = new ConcurrentHashMap<>();
    private static final Map<Integer, Boolean> LAST_ON_GROUND = new ConcurrentHashMap<>();
    private static final Map<Integer, Double> LAST_VY = new ConcurrentHashMap<>();
    private static final Map<Integer, Double> LAST_HORIZONTAL = new ConcurrentHashMap<>();
    /** 本帧已经 push 过的实体 id：Pre 可被别的模组取消（取消后 Post 不触发），
     *  所以 pop 必须靠这个集合判定，不能靠「Pre 里算出来非零」这种带条件的推断。 */
    private static final Set<Integer> PUSHED = ConcurrentHashMap.newKeySet();

    /** 只在第一次真正弹起来时写一行日志，用来证明事件确实接上了。 */
    private static boolean announced;

    private SquashStretch() {
    }

    private static final class Impact {
        int ageTicks;
        /** 0..1，冲击强度：受伤按掉血比例，落地按竖直速度，起跳给小值。 */
        float strength;
        /** 每只怪不同的相位种子，避免整群怪像广播体操一样同相位弹。 */
        float seed;
    }

    // ------------------------------------------------------------------ 观察

    /**
     * 受伤：看<b>血量</b>掉没掉。
     *
     * <p>这里原本读的是 {@link LivingEntity#hurtTime}，那是错的 —— 1.19.4 起受伤动画走
     * {@code ClientboundHurtAnimationPacket}，而翻遍 1.20.1 的源码，构造那个包的只有
     * {@code ServerPlayer} 一处（它只把「自己被打」发给自己）。也就是说除了玩家本人，
     * <b>任何生物的 {@code hurtTime} 在客户端永远是 0</b>，靠它触发等于永不触发。</p>
     *
     * <p>血量则不同：它走 {@code SynchedEntityData}，对所有生物都同步。所以掉血就是受伤，
     * 掉多少决定弹多狠。吸收伤害（金苹果那层）也算，否则「打不掉血」的那一下会没有反馈。</p>
     */
    public static void observeHurt(LivingEntity entity) {
        int id = entity.getId();
        float health = entity.getHealth() + entity.getAbsorptionAmount();
        Float prev = LAST_HEALTH.put(id, health);
        if (prev == null || health >= prev - 0.01F) {
            return;                      // 第一次见到它，或者没掉血
        }
        float lost = prev - health;
        float max = Math.max(1.0F, entity.getMaxHealth());
        // 掉 25% 血就吃满强度；只蹭掉一点也保证有 0.5 的起手，不然轻击完全看不出来
        trigger(entity, Math.min(1.0F, 0.5F + lost / max * 2.2F));
    }

    /** 落地 / 起跳 / 被击退：只用客户端已有的运动学字段，客户端预测的位移也一并算数。 */
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
                // 落地：竖直速度越大压得越扁（跳下三格以上就吃满强度）
                trigger(entity, (float) Math.min(1.0D, 0.5D + Math.abs(prevVy) / 1.4D) * 0.85F);
            } else if (prevGround && !onGround && vy > 0.30D) {
                // 起跳：轻微拉伸，给动作一个「弹起来」的起手
                trigger(entity, 0.45F);
            }
        }
        if (prevHorizontal != null && prevGround != null && prevGround && onGround) {
            double jump = horizontal - prevHorizontal;
            if (jump > 0.32D) {
                // 被击退：水平速度突变。这类冲击比落地轻，但要能看出来
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
        // 相位种子由实体 id 派生：同一只怪始终同一个种子（回弹手感稳定），
        // 不同怪之间错开（不会整齐划一）
        impact.seed = (id * 0.6180339F) % 1.0F;
        impact.strength = Math.max(impact.strength * 0.35F, Math.min(1.0F, strength));
        impact.ageTicks = 0;

        if (!announced) {
            announced = true;
            ApocalypseZombies.LOGGER.info("[Q弹] 已生效：{} 触发了一次挤压（强度 {}）",
                    entity.getName().getString(), String.format("%.2f", strength));
        }
    }

    // ------------------------------------------------------------------ 施加

    /**
     * 往 PoseStack 上叠加本帧形变。调用方负责保证与 {@link #popIfApplied} 成对。
     *
     * @return true 表示确实 push 了（调用方无需关心，配对由内部集合兜底）
     */
    public static boolean apply(LivingEntity entity, PoseStack pose, float partialTick) {
        if (!Config.SQUASH_ENABLED.get()) {
            return false;
        }
        if (entity instanceof Player) {
            // 玩家渲染会同时触发 RenderPlayerEvent 与 RenderLivingEvent（Forge 在
            // PlayerRenderer.render 里先 post Player 事件再调 super.render），
            // 两边都做就是双倍形变。本需求只针对生物，直接排除玩家。
            return false;
        }
        Impact impact = IMPACTS.get(entity.getId());
        if (impact == null) {
            return false;
        }

        float seconds = (impact.ageTicks + partialTick) / 20.0F;
        double damping = Config.SQUASH_DAMPING.get();
        // 频率按种子微调：起手始终是「立刻压到最深」（t=0 时 cos=1），
        // 但后续几次回弹的节奏各怪不同，比整群同频自然得多
        double frequency = Config.SQUASH_FREQUENCY.get() + impact.seed * 3.0D;
        float wave = (float) (Math.exp(-seconds * damping) * Math.cos(seconds * frequency));
        float amplitude = impact.strength * Config.SQUASH_INTENSITY.get().floatValue();
        float squash = amplitude * wave;
        if (Math.abs(squash) < DEAD_ZONE) {
            return false;
        }

        float yScale = 1.0F - squash;                 // 正冲击 → Y 变矮
        float xzScale = 1.0F + squash * 0.6F;         // XZ 鼓起，保住体积感
        float halfHeight = Math.max(0.5F, entity.getBbHeight() * 0.5F);

        pose.pushPose();
        // 三明治：抬到身体中心 → 非等比缩放 → 落回脚底。这样压扁是「绕身体中心」发生的，
        // 底面仍然贴地（直接 scale 的话观感像从地里长出来）
        pose.translate(0.0F, halfHeight, 0.0F);
        pose.scale(xzScale, yScale, xzScale);
        pose.translate(0.0F, -halfHeight, 0.0F);

        // Q 弹的另一半：回弹时的旋转摆动（绕 Z 侧倾 + 少量绕 X 前后俯仰）
        float roll = amplitude * Config.SQUASH_MAX_ROLL.get().floatValue()
                * (float) Math.sin(seconds * frequency * 0.72D + impact.seed * 6.2832D);
        pose.mulPose(Axis.ZP.rotationDegrees(roll));
        pose.mulPose(Axis.XP.rotationDegrees(roll * 0.45F));

        PUSHED.add(entity.getId());
        return true;
    }

    /** 与 {@link #apply} 严格配对：只有本帧真的 push 过才 pop。 */
    public static void popIfApplied(LivingEntity entity, PoseStack pose) {
        if (PUSHED.remove(entity.getId())) {
            pose.popPose();
        }
    }

    // ------------------------------------------------------------------ 驱动

    /** 每客户端 tick 推进一次年龄并回收过期记录。 */
    public static void tick() {
        if (IMPACTS.isEmpty() && LAST_HEALTH.isEmpty()) {
            return;
        }
        for (Impact impact : IMPACTS.values()) {
            impact.ageTicks++;
        }
        IMPACTS.entrySet().removeIf(entry -> entry.getValue().ageTicks > MAX_AGE_TICKS);

        // 实体卸载后这些 id 会永远留在表里，顺手清掉不在当前世界里的
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

    /** 退出世界时整体清空：世界对象换了，id 空间也换了，留着只会串味。 */
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
