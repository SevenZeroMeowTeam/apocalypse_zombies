package com.apocalypse.zombies.entity;

import java.util.List;
import java.util.UUID;

import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.core.particles.SimpleParticleType;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.MobSpawnType;
import net.minecraft.world.entity.ai.attributes.AttributeInstance;
import net.minecraft.world.entity.ai.attributes.AttributeModifier;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

import software.bernie.geckolib.animatable.GeoEntity;
import software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache;
import software.bernie.geckolib.core.animation.AnimatableManager;
import software.bernie.geckolib.core.animation.AnimationController;
import software.bernie.geckolib.core.animation.AnimationState;
import software.bernie.geckolib.core.animation.RawAnimation;
import software.bernie.geckolib.core.object.PlayState;
import software.bernie.geckolib.util.GeckoLibUtil;

import com.apocalypse.zombies.moon.MoonEvent;
import com.apocalypse.zombies.moon.MoonEventManager;
import com.apocalypse.zombies.registry.ModEntities;
import com.apocalypse.zombies.item.GunProfile;
import com.apocalypse.zombies.registry.ModItems;

/**
 * 美女僵尸 —— 尸潮里的「新娘」。指挥型 + 控场型，自己近战很弱，威胁全在技能上。
 *
 * <p>跟其他四只精英最大的区别是它不是「一招鲜」，而是<b>八套技能循环轮转</b>：
 * {@code 亡语魅惑 → 血月选妃 → 摄魂尖啸 → 白纱缚足 → 抛花束 → 鬼嫁之吻 → 献祭召奬 → 血纱回春 → ...}，
 * 前几套带召唤，而且各自有独立冷却（{@link #ROTATION_COOLDOWN}）。轮转让玩家没法靠背一招就通关，
 * 独立冷却则保证出手顺序不会卡死在某个还没冷却完的技能上。</p>
 *
 * <ul>
 *   <li><b>亡语魅惑</b>：策反半径内最多 4 只普通僵尸为己方（约 10 秒），并召唤 2 只魅惑召奬。
 *       这招同时是死亡被动——她倒下时照样放一次，所以叫「亡语」。</li>
 *   <li><b>血月选妃</b>：召来 3~4 只选妃小队（血月 5~6 只）并给自己叠速度 / 力量 / 回血；
 *       血月期间召唤量、buff 时长和强度全部上调。</li>
 *   <li><b>摄魂尖啸</b>：半径 8 的尖啸，对玩家造成伤害 + 减速 + 短暂失明，
 *       同时把玩家往自己身上拽，并按命中人数吸血；再抽出 2~3 只幽灵召奬。</li>
 *   <li><b>白纱缚足</b>：半径 7 的裙纱暴涨，缠住范围内玩家定身（极重缓速 + 禁跳）。</li>
 *   <li><b>抛花束</b>：朝正前方锥形甩出花束，锥内玩家受伤并被减速。</li>
 *   <li><b>鬼嫁之吻</b>：拉近 3.5 格内最近的玩家并吸食其血，顺手挂虚弱。</li>
 *   <li><b>献祭召奬</b>：献祭场上最多 2 只召奬，换自身回血 / 抗性 / 力量；没召奬可献就只剩弱化版。</li>
 *   <li><b>血纱回春</b>：持续回血——命中瞬间自己与半径 12 内的召奬一起挂上<b>低等级再生</b>
 *       （每 50 tick 回 1 点，足足 20 秒）。是「拖住这场战斗」而不是「一口回满」，
 *       玩家打断她仍能拿到收益。血月期间时长与吸收层数全部上调。</li>
 * </ul>
 *
 * <p>召唤物另有一条：{@link #summonMinion} 里有概率给它塞一把枪（{@link #MINION_ARM_CHANCE}，
 * 血月更高）。僵尸不会开枪，所以这是表现力 + 一点近战加伤，不是远程威胁；
 * 掉落概率刻意设为 0，免得玩家靠刷她的召奬白拿枪械。</p>
 *
 * <p>召唤物一律是 {@link CharmedZombie}，且总量有 {@link #MINION_CAP} 封顶——
 * 带召唤的技能有四个，不封顶就是指数级的麻烦。</p>
 */
public class BrideZombie extends AbstractEliteZombie implements GeoEntity {

    /** 轮转顺序。改这里就能改技能顺序，不用动逻辑。 */
    private static final EliteAbility[] ROTATION = {
            EliteAbility.DEATH_CHIME, EliteAbility.CONSORT, EliteAbility.SOUL_SHRIEK,
            EliteAbility.VEIL_SNARE, EliteAbility.BOUQUET, EliteAbility.BRIDAL_KISS,
            EliteAbility.SACRIFICE, EliteAbility.BLOOD_REGEN,
            EliteAbility.VEIL_SWIPE, EliteAbility.FLOWER_DART,
            EliteAbility.VEIL_CHOP};

    /** 每套技能自己的冷却（tick），下标跟 {@link #ROTATION} 一一对应。 */
    private static final int[] ROTATION_COOLDOWN = {400, 300, 240, 260, 220, 200, 500, 320, 180, 220, 260};

    /**
     * 轮转到的这一套「距离条件不成立」持续多少 tick 就跳过它。
     *
     * <p>没有这条兜底，近战槽会在玩家站远处时把整个轮转永久卡住 —— 她再也放不出任何技能，
     * 玩家在十几格外看到她呆站着抡空气。100 tick（5 秒）是「玩家真的没打算靠近」的尺度。</p>
     */
    private static final int ROTATION_SKIP_TICKS = 100;

    /** 轮转两套之间的公共间隔：让她出手之间有个能被玩家读到的空档。 */
    private static final int ROTATION_GAP = 60;

    /** 亡语魅惑：波动半径、最多策反几只、策反后的存活时长（约 10 秒）。 */
    private static final double CHARM_RADIUS = 10.0D;
    private static final int CHARM_MAX_VICTIMS = 4;
    private static final int CHARM_DURATION = 200;

    /** 摄魂尖啸：半径、基础伤害、每人吸血量。 */
    private static final double SHRIEK_RADIUS = 8.0D;
    private static final double SHRIEK_DAMAGE = 4.0D;
    private static final double SHRIEK_LIFESTEAL_PER_VICTIM = 1.5D;
    private static final int SPECTER_LIFETIME = 260;

    /** 场上最多容许多少只召奬，防止无限滚雪球。 */
    private static final int MINION_CAP = 10;

    /** 白纱缚足：缠绕半径、定身时长（tick）。 */
    private static final double VEIL_RADIUS = 7.0D;
    private static final int VEIL_SNARE_TICKS = 60;

    /** 抛花束：射程、锥形半角（度）、伤害、减速时长。 */
    private static final double BOUQUET_RANGE = 7.0D;
    private static final double BOUQUET_HALF_ANGLE = 60.0D;
    private static final double BOUQUET_DAMAGE = 3.0D;
    private static final int BOUQUET_SLOW_TICKS = 80;

    /**
     * 纱袖横扫（近战）。起手距离比命中半径多 1.5 格余量：玩家绕着她侧身走位时，
     * 「刚好够得着」的那一帧不该让她因为差半格而干等。
     */
    private static final double SWIPE_TRIGGER_RANGE = 4.5D;
    private static final double SWIPE_RADIUS = 3.0D;
    private static final double SWIPE_HALF_ANGLE = 75.0D;
    /** 重击：比原版僵尸爪击（3）重一倍多，贴脸站桩的代价要能感觉到。 */
    private static final double SWIPE_DAMAGE = 8.0D;
    private static final double SWIPE_KNOCKBACK = 2.0D;
    private static final int SWIPE_SLOW_TICKS = 40;

    /** 抛花刺（远程）。4 格以内用横扫更划算，所以下限设在 4 格。 */
    private static final double DART_MIN_RANGE = 4.0D;
    private static final double DART_MAX_RANGE = 16.0D;
    /** 出膛速度（格/tick）。抛物线 + 这个速度决定它大约能飞十几格就落地。 */
    private static final double DART_SPEED = 0.9D;
    private static final float DART_INACCURACY = 2.0F;
    /** 瞄高处补偿：抛物线会往下掉，按距离把出膛方向抬高一点，否则中距离全部打在地上。 */
    private static final double DART_ARC_LIFT = 0.14D;

    /**
     * 纱袖下劈（近战，走**垂直面**）。与横扫的分工：横扫是「面」（±75° / 3 格 / 伤 8 / 击退 2），
     * 下劈是「点」（±32° / 2.2 格 / 伤 12 / 几乎不推）。窄扇面 + 长缓慢就是她全部的威胁：
     * 站在她正前方硬吃这一下，比被扫到更疼。
     */
    private static final double CHOP_TRIGGER_RANGE = 3.5D;
    private static final double CHOP_RADIUS = 2.2D;
    private static final double CHOP_HALF_ANGLE = 32.0D;
    private static final double CHOP_DAMAGE = 12.0D;
    private static final double CHOP_KNOCKBACK = 0.6D;
    private static final int CHOP_SLOW_TICKS = 70;

    /** 鬼嫁之吻：抓取距离、伤害、吸血量。 */
    private static final double KISS_RANGE = 3.5D;
    private static final double KISS_DAMAGE = 5.0D;
    private static final double KISS_LIFESTEAL = 3.0D;

    /** 献祭召奬：最多献祭几只、每只换来多久的强化。 */
    private static final int SACRIFICE_MAX = 2;
    private static final int SACRIFICE_BUFF_TICKS = 200;

    /** 血纱回春：「缓慢回血」= 低等级 + 长时长，而不是一次大治疗。 */
    private static final int REGEN_TICKS = 400;
    private static final int REGEN_ABSORPTION_TICKS = 200;
    private static final double REGEN_MINION_RADIUS = 12.0D;
    /** 命中那一 tick 的即时回血：让玩家当场看到血条动，慢回交给 REGENERATION。 */
    private static final float REGEN_BURST_HEAL = 4.0F;

    /** 召奬带武器的概率（血月更高）。 */
    private static final float MINION_ARM_CHANCE = 0.28F;
    private static final float MINION_ARM_CHANCE_BLOOD = 0.45F;
    /** 持械召奬的近战加伤 —— 免得「持武器」只是贴图上的摆设。 */
    private static final double ARMED_DAMAGE_BONUS = 2.0D;
    private static final UUID ARMED_DAMAGE_ID =
            UUID.fromString("9d1e5b90-2f4b-4c3a-9a6e-1c7b5e0d3f21");

    /** 召奬出生时抽到「迅捷」的概率（血月更高）。 */
    private static final float MINION_SWIFT_CHANCE = 0.30F;
    private static final float MINION_SWIFT_CHANCE_BLOOD = 0.50F;
    /**
     * 迅捷召奬的移速加成，按基础值的倍数算。
     *
     * <p>25% 是「一眼看得出」的下限：僵尸基础移速 0.23，加成后约 0.288，
     * 在混战里能明显看到它先一步贴到目标身上；再高就会开始出现「追着人跑不掉」的体感问题。</p>
     */
    private static final double SWIFT_SPEED_BONUS = 0.25D;
    private static final UUID SWIFT_SPEED_ID =
            UUID.fromString("3c9f1d27-6b4e-4a58-8e2f-7d1a4c0b9e33");

    /** 施法期间每多少 tick 撒一次光环粒子。 */
    private static final int AURA_PERIOD = 4;

    /** 每套技能自己的剩余冷却。 */
    private final int[] skillCooldown = new int[ROTATION.length];

    /** 轮转到第几套技能。 */
    private int rotationIndex;

    /**
     * 轮转到的这一套「距离条件不成立」已经持续了多少 tick。
     *
     * <p>见 {@link #ROTATION_SKIP_TICKS}：光有距离条件会让整条轮转卡死，这是那种
     * 「编译过、日志干净、技能永远放不出来」的坑。</p>
     */
    private int rotationStallTicks;

    // ------------------------------------------------------------------ 动画层（Phase 2 GeckoLib）
    //
    // 只驱动「外观」：技能的逻辑、数值、冷却、掉落一律没动，这里只是把本类已有的
    // 施法状态（getAbility / getAbilityTick）翻译成剪辑名。剪辑本身住在
    // assets/apocalypse_zombies/animations/bride_zombie.animation.json，由
    // tools/bride_v2.py 生成；下面这几行字符串是两边的接口约定，生成器会回来核对。

    /** 静置。 */
    public static final String ANIM_IDLE = "idle";
    /** 行走（基础循环：两步交替 + 裙摆/面纱跟随）。 */
    public static final String ANIM_WALK = "walk";
    /** 召唤：命中那一刻的手与冠的动作，与施法剪辑并行播。 */
    public static final String ANIM_SUMMON = "summon";
    /** 亡语魅惑。 */
    public static final String ANIM_DEATH_CHIME = "skill_death_chime";
    /** 血月选妃。 */
    public static final String ANIM_CONSORT = "skill_consort";
    /** 摄魂尖啸。 */
    public static final String ANIM_SOUL_SHRIEK = "skill_soul_shriek";
    /** 白纱缚足。 */
    public static final String ANIM_VEIL_SNARE = "skill_veil_snare";
    /** 献祭召奬。 */
    public static final String ANIM_SACRIFICE = "skill_sacrifice";
    /** 抛花束。 */
    public static final String ANIM_BOUQUET = "skill_bouquet";
    /** 鬼嫁之吻。 */
    public static final String ANIM_BRIDAL_KISS = "skill_bridal_kiss";

    /** 血纱回春。 */
    public static final String ANIM_BLOOD_REGEN = "skill_blood_regen";

    /** 纱袖横扫：提袖后引 → 扇面横扫 → 收招（2.0s，命中 1.0s）。 */
    public static final String ANIM_VEIL_SWIPE = "skill_veil_swipe";

    /** 抛花刺：侧身低抛 → 甩出手 → 收招（1.8s，命中 0.9s）。 */
    public static final String ANIM_FLOWER_DART = "skill_flower_dart";

    /** 纱袖下劈（第三条纯输出技能，垂直面近战）。 */
    public static final String ANIM_VEIL_CHOP = "skill_veil_chop";

    /** 召唤动作在命中之后还允许播多久（tick）。剪辑 0.9s = 18 tick，留 2 tick 余量。 */
    private static final int SUMMON_WINDOW = 20;

    private final AnimatableInstanceCache geoCache = GeckoLibUtil.createInstanceCache(this);

    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache() {
        return this.geoCache;
    }

    /**
     * 三条控制器各管一摊：
     * <ul>
     *   <li>{@code movement}：静置 / 行走；施法期间整体让位（返回 STOP，不参与混合），
     *       否则「走路的腿」会和「施法的腿」互相盖。</li>
     *   <li>{@code cast}：三套技能各自的施法剪辑。剪辑时长 == 技能时长，
     *       关键帧的收放点对齐 {@link EliteAbility#getImpactTick()}。</li>
     *   <li>{@code summon}：命中窗口内叠上去的召唤动作。它只驱动 hand_r / hand_l / crown
     *       三根骨头，和施法剪辑的骨骼集合不相交，所以能同时播而不打架
     *       （生成器的自校验里有一条专门验这个）。</li>
     * </ul>
     */
    @Override
    public void registerControllers(AnimatableManager.ControllerRegistrar controllers) {
        controllers.add(new AnimationController<>(this, "movement", 3, BrideZombie::movementAnimation));
        controllers.add(new AnimationController<>(this, "cast", 1, BrideZombie::castAnimation));
        controllers.add(new AnimationController<>(this, "summon", 0, BrideZombie::summonAnimation));
    }

    /** 静置 / 行走：步子按实际位移缩放，脚不容易打滑。 */
    private static PlayState movementAnimation(AnimationState<BrideZombie> state) {
        if (state.getAnimatable().isCasting()) {
            return PlayState.STOP;
        }
        state.setControllerSpeed(Mth.clamp(0.55F + 0.9F * state.getLimbSwingAmount(), 0.5F, 2.2F));
        return state.setAndContinue(state.isMoving()
                ? RawAnimation.begin().thenLoop(ANIM_WALK)
                : RawAnimation.begin().thenLoop(ANIM_IDLE));
    }

    /** 施法：轮到哪一套就播哪一段。每段剪辑首尾都归零，接上/断开都不会跳变。 */
    private static PlayState castAnimation(AnimationState<BrideZombie> state) {
        String clip = switch (state.getAnimatable().getAbility()) {
            case DEATH_CHIME -> ANIM_DEATH_CHIME;
            case CONSORT -> ANIM_CONSORT;
            case SOUL_SHRIEK -> ANIM_SOUL_SHRIEK;
            case VEIL_SNARE -> ANIM_VEIL_SNARE;
            case SACRIFICE -> ANIM_SACRIFICE;
            case BOUQUET -> ANIM_BOUQUET;
            case BRIDAL_KISS -> ANIM_BRIDAL_KISS;
            case BLOOD_REGEN -> ANIM_BLOOD_REGEN;
            case VEIL_SWIPE -> ANIM_VEIL_SWIPE;
            case FLOWER_DART -> ANIM_FLOWER_DART;
            case VEIL_CHOP -> ANIM_VEIL_CHOP;
            default -> null;
        };
        if (clip == null) {
            return PlayState.STOP;
        }
        return state.setAndContinue(RawAnimation.begin().thenPlay(clip));
    }

    /**
     * 这套技能会不会召唤召奬。
     *
     * <p>四套扩充技能都不召唤，所以它们不能在命中窗口叠召唤动作 —— 一方面那三段手势
     * 会和它们自己的手臂关键帧打架，另一方面「白纱缚足」打出个召唤手势会让玩家读错招。</p>
     */
    private static boolean summonsMinions(EliteAbility ability) {
        return switch (ability) {
            case DEATH_CHIME, CONSORT, SOUL_SHRIEK -> true;
            default -> false;
        };
    }

    /** 召唤：带召唤的几套技能，召唤动作只在命中窗口里叠上去。 */
    private static PlayState summonAnimation(AnimationState<BrideZombie> state) {
        BrideZombie bride = state.getAnimatable();
        EliteAbility ability = bride.getAbility();
        if (ability.isIdle() || !summonsMinions(ability)) {
            return PlayState.STOP;
        }
        int tick = bride.getAbilityTick();
        if (tick < ability.getImpactTick() || tick > ability.getImpactTick() + SUMMON_WINDOW) {
            return PlayState.STOP;
        }
        return state.setAndContinue(RawAnimation.begin().thenPlay(ANIM_SUMMON));
    }

    public BrideZombie(EntityType<? extends Zombie> type, Level level) {
        super(type, level);
        this.xpReward = 20;
    }

    /**
     * 血量 / 伤害比尖啸者略高、移速略快：她得贴到玩家身边才放得出尖啸，
     * 站桩型的数值会让她连技能都放不出来就死了。
     */
    public static AttributeSupplier.Builder createAttributes() {
        return eliteAttributes()
                .add(Attributes.MAX_HEALTH, 34.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.235D)
                .add(Attributes.ATTACK_DAMAGE, 3.0D)
                .add(Attributes.ARMOR, 3.0D)
                .add(Attributes.FOLLOW_RANGE, 42.0D);
    }

    // ------------------------------------------------------------------ 轮转

    /** 驱动器的「当前技能」= 轮转到的这一套。 */
    @Override
    protected EliteAbility ability() {
        return ROTATION[this.rotationIndex % ROTATION.length];
    }

    @Override
    protected int abilityCooldownTicks() {
        return ROTATION_GAP;
    }

    /**
     * 起手条件 = 轮转到的技能没在自己冷却 + 该技能的距离条件成立。
     *
     * <p>驱动器只有一个冷却计时器，所以「每套技能独立冷却」这一条得自己兜：
     * 轮转到的技能还在冷却就整个不起手，等它转好——顺序不会乱，也不会白放。</p>
     */
    @Override
    protected boolean canStartAbility() {
        int index = this.rotationIndex % ROTATION.length;
        if (this.skillCooldown[index] > 0) {
            // 冷却就是等：它自己会走完。把冷却中的槽跳过去只会让技能顺序变得不可预测
            return false;
        }
        if (this.slotInRange(index)) {
            this.rotationStallTicks = 0;
            return true;
        }
        // 距离条件不成立是另一回事：玩家可能整场都不靠近。数满就跳过这一槽，
        // 否则「轮转到近战、玩家在远处」会把她剩下的所有技能一起锁死。
        if (++this.rotationStallTicks >= ROTATION_SKIP_TICKS) {
            this.rotationStallTicks = 0;
            this.rotationIndex = (this.rotationIndex + 1) % ROTATION.length;
        }
        return false;
    }

    /** 轮转到的这一套，距离条件成立吗？ */
    private boolean slotInRange(int index) {
        return switch (ROTATION[index]) {
            // 魅惑要身边有僵尸可以策反，不然白放。召奬数量封顶交给 summonMinions，
            // 不写在这里：写在这里会让「召奬满员」把整个轮转卡死在第一套技能上
            case DEATH_CHIME -> this.hasTargetInRange(1.0D, 16.0D);
            // 选妃只是召唤 + 自我强化，有目标就能放
            case CONSORT -> this.hasTargetInRange(2.0D, 24.0D);
            // 尖啸是贴脸控场，得让玩家进圈才有意义
            case SOUL_SHRIEK -> this.hasTargetInRange(1.0D, SHRIEK_RADIUS);
            // 缚足也是圈内控场，留 1 格余量：玩家站在边缘外一点点不该让她干等
            case VEIL_SNARE -> this.hasTargetInRange(1.0D, VEIL_RADIUS + 1.0D);
            // 花束是投掷，得跟玩家拉开一点距离才好看
            case BOUQUET -> this.hasTargetInRange(2.0D, 16.0D);
            // 吻要贴脸才抓得到
            case BRIDAL_KISS -> this.hasTargetInRange(1.0D, KISS_RANGE + 1.0D);
            // 献祭故意不要求「场上有召奬」：那会让「召奬死光」把轮转永久卡死在她的回合上，
            // 跟 DEATH_CHIME 的处理一样 —— 没召奬可献就只结算弱化版的自我强化
            case SACRIFICE -> this.hasTargetInRange(2.0D, 24.0D);
            // 回春只在挂彩时才放，且要有人在附近：否则她会站在远处无限自愈，玩家永远等不到收割窗口
            case BLOOD_REGEN -> this.getHealth() < this.getMaxHealth() * 0.65F
                    && this.hasTargetInRange(1.0D, 20.0D);
            // 横扫是近战：要贴到脸上才有意义；够不着就交给 ROTATION_SKIP_TICKS 跳过这一槽
            case VEIL_SWIPE -> this.hasTargetInRange(1.0D, SWIPE_TRIGGER_RANGE);
            // 抛花刺是远程：4 格以内用横扫更划算，太远抛物线自己先落地
            case FLOWER_DART -> this.hasTargetInRange(DART_MIN_RANGE, DART_MAX_RANGE);
            // 下劈也是近战，但比横扫更贴脸：窄扇面（±32°），站偏一点就打不着
            case VEIL_CHOP -> this.hasTargetInRange(1.0D, CHOP_TRIGGER_RANGE);
            default -> false;
        };
    }

    @Override
    protected void onAbilityStart() {
        switch (this.getAbility()) {
            case DEATH_CHIME -> {
                this.playSound(SoundEvents.ELDER_GUARDIAN_CURSE, 1.4F, 1.1F);
                this.ambientRing();
            }
            case CONSORT -> {
                if (this.isBloodMoon(this.level())) {
                    this.playSound(SoundEvents.RAVAGER_ROAR, 1.4F, 1.3F);
                } else {
                    this.playSound(SoundEvents.EVOKER_PREPARE_SUMMON, 1.3F, 1.2F);
                }
                this.ambientRing();
            }
            case SOUL_SHRIEK -> {
                this.playSound(SoundEvents.WARDEN_SONIC_CHARGE, 1.4F, 1.6F);
                this.ambientRing();
            }
            case VEIL_SNARE -> {
                // 低语 + 白丝：起手就该让玩家意识到「脚要没了」
                this.playSound(SoundEvents.AMBIENT_CAVE.value(), 1.2F, 0.7F);
                this.ambientRing();
            }
            case SACRIFICE -> {
                this.playSound(SoundEvents.ELDER_GUARDIAN_CURSE, 1.2F, 0.6F);
                this.ambientRing();
            }
            case BOUQUET -> {
                this.playSound(SoundEvents.AMETHYST_BLOCK_CHIME, 1.3F, 1.6F);
                this.ambientRing();
            }
            case BRIDAL_KISS -> {
                this.playSound(SoundEvents.AMBIENT_CAVE.value(), 1.1F, 1.4F);
                this.ambientRing();
            }
            case BLOOD_REGEN -> {
                // 低沉的一声「充能」：她把血从纱里收回来
                this.playSound(SoundEvents.BEACON_ACTIVATE, 1.1F, 1.6F);
                this.ambientRing();
            }
            case VEIL_SWIPE -> {
                // 布料破风的一声：重击要有预警，玩家听见还有 1 秒可以退
                this.playSound(SoundEvents.PLAYER_ATTACK_SWEEP, 1.4F, 0.8F);
                this.ambientRing();
            }
            case FLOWER_DART -> {
                this.playSound(SoundEvents.SNOWBALL_THROW, 1.3F, 1.5F);
                this.ambientRing();
            }
            case VEIL_CHOP -> {
                // 破空的长音：抬臂过顶到劈下有 1 秒以上，声音要让玩家来得及退开
                this.playSound(SoundEvents.PLAYER_ATTACK_CRIT, 1.4F, 0.7F);
                this.ambientRing();
            }
            default -> {
            }
        }
    }

    @Override
    protected void onAbilityImpact() {
        if (!(this.level() instanceof ServerLevel level)) {
            return;
        }
        switch (this.getAbility()) {
            case DEATH_CHIME -> this.castDeathChime(level);
            case CONSORT -> this.castConsort(level);
            case SOUL_SHRIEK -> this.castSoulShriek(level);
            case VEIL_SNARE -> this.castVeilSnare(level);
            case SACRIFICE -> this.castSacrifice(level);
            case BOUQUET -> this.castBouquet(level);
            case BRIDAL_KISS -> this.castBridalKiss(level);
            case BLOOD_REGEN -> this.castBloodRegen(level);
            case VEIL_SWIPE -> this.castVeilSwipe(level);
            case FLOWER_DART -> this.castFlowerDart(level);
            case VEIL_CHOP -> this.castVeilChop(level);
            default -> {
            }
        }
    }

    /** 收招：记下这一套的冷却，然后轮转到下一套。 */
    @Override
    protected void onAbilityEnd() {
        int index = this.rotationIndex % ROTATION.length;
        this.skillCooldown[index] = ROTATION_COOLDOWN[index];
        this.rotationIndex = (this.rotationIndex + 1) % ROTATION.length;
    }

    /** 技能自己的冷却自己数（驱动器的计时器管不到三套技能各自的节奏）。 */
    @Override
    protected void customServerAiStep() {
        super.customServerAiStep();
        if (!(this.level() instanceof ServerLevel)) {
            return;
        }
        for (int i = 0; i < this.skillCooldown.length; i++) {
            if (this.skillCooldown[i] > 0) {
                this.skillCooldown[i]--;
            }
        }
        // 施法光环：整个前摇/收招期间持续撒粒子，别只在起手那一瞬出现
        if (!this.getAbility().isIdle() && this.tickCount % AURA_PERIOD == 0) {
            this.castAura();
        }
    }

    // ------------------------------------------------------------------ 技能一：亡语魅惑

    /**
     * 一圈魅惑波动：策反周围普通僵尸，再召唤 2 只魅惑召奬。
     * 血月期间半径更大、召奬活得更久。
     */
    private void castDeathChime(ServerLevel level) {
        boolean blood = this.isBloodMoon(level);
        this.playSound(SoundEvents.AMETHYST_BLOCK_CHIME, 1.6F, 1.2F);
        level.sendParticles(ParticleTypes.HEART, this.getX(), this.getEyeY(), this.getZ(),
                16, 1.2D, 0.7D, 1.2D, 0.02D);

        double radius = blood ? CHARM_RADIUS + 2.0D : CHARM_RADIUS;
        int converted = this.charmNearbyZombies(level, radius, CHARM_MAX_VICTIMS);
        int summoned = this.summonMinions(level, CharmedZombie.Variant.CHARMED,
                2, blood ? CHARM_DURATION + 100 : CHARM_DURATION);
        level.sendParticles(ParticleTypes.HEART, this.getX(), this.getY() + 1.2D, this.getZ(),
                4 * (converted + summoned), 0.6D, 0.6D, 0.6D, 0.03D);
    }

    /**
     * 把半径内的普通僵尸类「策反」成魅惑召奬，最多 {@code max} 只。
     *
     * <p>做法是把原来的僵尸原地换成一只 {@link CharmedZombie}（血量按比例继承，目标一并交接），
     * 而不是只挂一个数据标记：目标表是僵尸 AI 里最难临时改写的一层，
     * 换成另一种实体才真正做到「不攻击玩家、攻击其他僵尸」，也顺手拿到存活时限。</p>
     */
    private int charmNearbyZombies(ServerLevel level, double radius, int max) {
        List<Zombie> candidates = level.getEntitiesOfClass(Zombie.class,
                new AABB(this.blockPosition()).inflate(radius),
                zombie -> zombie.isAlive()
                        && !(zombie instanceof CharmedZombie)
                        && !(zombie instanceof BrideZombie));
        // 最近的先策反：玩家会看到「离她最近的那几只先倒戈」，读得出来是她在施法
        candidates.sort((a, b) -> Double.compare(this.distanceToSqr(a), this.distanceToSqr(b)));

        int converted = 0;
        for (Zombie candidate : candidates) {
            if (converted >= max) {
                break;
            }
            CharmedZombie charmed = ModEntities.CHARMED.get().create(level);
            if (charmed == null) {
                break;
            }
            float healthRatio = candidate.getMaxHealth() > 0.0F
                    ? candidate.getHealth() / candidate.getMaxHealth()
                    : 1.0F;
            LivingEntity inheritedTarget = candidate.getTarget() != null
                    ? candidate.getTarget()
                    : this.getTarget();

            charmed.moveTo(candidate.getX(), candidate.getY(), candidate.getZ(),
                    candidate.getYRot(), candidate.getXRot());
            charmed.arm(CHARM_DURATION, CharmedZombie.Variant.CHARMED, inheritedTarget);
            charmed.setHealth(Math.max(1.0F, charmed.getMaxHealth() * healthRatio));

            level.sendParticles(ParticleTypes.HEART,
                    candidate.getX(), candidate.getEyeY(), candidate.getZ(),
                    6, 0.3D, 0.3D, 0.3D, 0.0D);
            candidate.discard();
            if (level.addFreshEntity(charmed)) {
                converted++;
            }
        }
        return converted;
    }

    /** 死亡被动：倒下那一刻照样放一次魅惑波动，再留 2 只召奬收场。 */
    @Override
    public void die(DamageSource source) {
        if (this.level() instanceof ServerLevel level) {
            this.playSound(SoundEvents.AMETHYST_BLOCK_CHIME, 1.6F, 0.8F);
            level.sendParticles(ParticleTypes.HEART, this.getX(), this.getEyeY(), this.getZ(),
                    20, 1.0D, 0.6D, 1.0D, 0.03D);
            this.charmNearbyZombies(level, CHARM_RADIUS + 2.0D, CHARM_MAX_VICTIMS);
            this.summonMinions(level, CharmedZombie.Variant.CHARMED, 2, CHARM_DURATION);
        }
        super.die(source);
    }

    // ------------------------------------------------------------------ 技能二：血月选妃

    /**
     * 召来选妃小队并给自己上 buff。血月是她的主场：
     * 召唤量 3~4 → 5~6，buff 时长翻倍多，速度和力量各加一级。
     */
    private void castConsort(ServerLevel level) {
        boolean blood = this.isBloodMoon(level);
        this.playSound(blood ? SoundEvents.RAVAGER_ROAR : SoundEvents.EVOKER_CAST_SPELL, 1.4F, 1.2F);
        level.sendParticles(ParticleTypes.HAPPY_VILLAGER, this.getX(), this.getEyeY(), this.getZ(),
                12, 1.0D, 0.6D, 1.0D, 0.02D);

        int count = blood ? 5 + this.random.nextInt(2) : 3 + this.random.nextInt(2);
        this.summonMinions(level, CharmedZombie.Variant.CONSORT, count, blood ? 400 : 260);

        int buffTicks = blood ? 600 : 240;
        this.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SPEED, buffTicks, blood ? 1 : 0));
        this.addEffect(new MobEffectInstance(MobEffects.DAMAGE_BOOST, buffTicks, blood ? 1 : 0));
        this.addEffect(new MobEffectInstance(MobEffects.REGENERATION, buffTicks / 2, blood ? 1 : 0));
        level.sendParticles(ParticleTypes.HEART, this.getX(), this.getY() + 1.4D, this.getZ(),
                8, 0.5D, 0.5D, 0.5D, 0.02D);
    }

    // ------------------------------------------------------------------ 技能三：摄魂尖啸

    /**
     * 范围尖啸：伤害 + 减速 + 短暂失明，把玩家往自己身上拽，按命中人数吸血，
     * 再抽出 2~3 只幽灵召奬。
     */
    private void castSoulShriek(ServerLevel level) {
        boolean blood = this.isBloodMoon(level);
        this.playSound(SoundEvents.WARDEN_SONIC_BOOM, 1.3F, 1.5F);
        level.sendParticles(ParticleTypes.SONIC_BOOM,
                this.getX(), this.getEyeY() + 0.2D, this.getZ(), 1, 0.0D, 0.0D, 0.0D, 0.0D);
        level.sendParticles(ParticleTypes.SCULK_SOUL,
                this.getX(), this.getEyeY(), this.getZ(), 28, 1.2D, 1.0D, 1.2D, 0.05D);

        float damage = (float) (SHRIEK_DAMAGE + (blood ? 2.0D : 0.0D));
        List<Player> victims = level.getEntitiesOfClass(Player.class,
                new AABB(this.blockPosition()).inflate(SHRIEK_RADIUS),
                player -> player.isAlive() && !player.isCreative() && !player.isSpectator());

        for (Player victim : victims) {
            victim.hurt(this.damageSources().mobAttack(this), damage);
            victim.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SLOWDOWN,
                    blood ? 160 : 100, blood ? 2 : 1));
            victim.addEffect(new MobEffectInstance(MobEffects.BLINDNESS,
                    blood ? 100 : 60, 0));
            level.sendParticles(ParticleTypes.SCULK_SOUL,
                    victim.getX(), victim.getEyeY(), victim.getZ(), 6, 0.3D, 0.3D, 0.3D, 0.02D);

            // 往她身上拽：水平方向归一化，竖直方向只给一点点，免得直接把人掀起来
            Vec3 pull = new Vec3(this.getX() - victim.getX(), 0.0D, this.getZ() - victim.getZ());
            if (pull.lengthSqr() > 1.0E-4D) {
                pull = pull.normalize().scale(blood ? 1.4D : 0.9D);
            }
            victim.push(pull.x, 0.18D, pull.z);
            victim.hurtMarked = true;
        }

        if (!victims.isEmpty()) {
            this.heal((float) Math.min(victims.size() * SHRIEK_LIFESTEAL_PER_VICTIM, 10.0D));
        }
        this.summonMinions(level, CharmedZombie.Variant.SPECTER,
                2 + this.random.nextInt(2), SPECTER_LIFETIME);
    }

    // ------------------------------------------------------------------ 技能四：白纱缚足

    /**
     * 白纱暴涨缠住周围玩家：极重缓速 + 挖掘疲劳，给足"被纱裹住"的手感。
     *
     * <p>不断言"禁止跳跃"：原版那套「JumpBoost 128 = 不能跳」的写法依赖的是没写进文档的
     * 数值溢出行为，这里不做这种赌注 —— 走不动本身就是这招的核心，原地跳没有意义。</p>
     */
    private void castVeilSnare(ServerLevel level) {
        this.playSound(SoundEvents.SLIME_SQUISH, 1.3F, 0.8F);
        // 白丝从裙底往外抽：三层不同半径的环，读起来像"纱在扩散"
        for (double r : new double[]{1.5D, 3.5D, 5.5D}) {
            level.sendParticles(ParticleTypes.END_ROD,
                    this.getX(), this.getY() + 0.15D, this.getZ(),
                    18, r * 0.5D, 0.1D, r * 0.5D, 0.01D);
        }
        level.sendParticles(ParticleTypes.ITEM_SLIME,
                this.getX(), this.getY() + 0.1D, this.getZ(), 20, 1.2D, 0.2D, 1.2D, 0.02D);

        List<Player> victims = level.getEntitiesOfClass(Player.class,
                new AABB(this.blockPosition()).inflate(VEIL_RADIUS),
                player -> player.isAlive() && !player.isCreative() && !player.isSpectator());

        for (Player victim : victims) {
            victim.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SLOWDOWN, VEIL_SNARE_TICKS, 6));
            victim.addEffect(new MobEffectInstance(MobEffects.DIG_SLOWDOWN, VEIL_SNARE_TICKS, 2));
            level.sendParticles(ParticleTypes.END_ROD,
                    victim.getX(), victim.getY() + 0.1D, victim.getZ(), 10, 0.35D, 0.1D, 0.35D, 0.02D);
        }
    }

    // ------------------------------------------------------------------ 技能五：献祭召奬

    /**
     * 献祭最近的召奬换自身强化：每献祭一只给一档回血 / 抗性 / 力量。
     *
     * <p>这是她唯一"消耗自己资源"的技能，所以强度给得比别的招高。场上没召奬可献时
     * 只结算一档短回血 —— 而不是整个不起手，否则召奬死光会把轮转卡在这一格。</p>
     */
    private void castSacrifice(ServerLevel level) {
        this.playSound(SoundEvents.EVOKER_CAST_SPELL, 1.5F, 0.7F);

        List<CharmedZombie> minions = level.getEntitiesOfClass(CharmedZombie.class,
                new AABB(this.blockPosition()).inflate(24.0D), CharmedZombie::isAlive);
        // 最近的先献：和她一起施法的收尾动作对得上
        minions.sort((a, b) -> Double.compare(this.distanceToSqr(a), this.distanceToSqr(b)));

        int sacrificed = 0;
        for (CharmedZombie minion : minions) {
            if (sacrificed >= SACRIFICE_MAX) {
                break;
            }
            level.sendParticles(ParticleTypes.SOUL,
                    minion.getX(), minion.getEyeY(), minion.getZ(), 16, 0.3D, 0.5D, 0.3D, 0.04D);
            minion.discard();
            sacrificed++;
        }

        if (sacrificed > 0) {
            this.heal(6.0F * sacrificed);
            this.addEffect(new MobEffectInstance(MobEffects.DAMAGE_RESISTANCE,
                    SACRIFICE_BUFF_TICKS, Math.min(sacrificed - 1, 1)));
            this.addEffect(new MobEffectInstance(MobEffects.DAMAGE_BOOST,
                    SACRIFICE_BUFF_TICKS, Math.min(sacrificed - 1, 1)));
            this.addEffect(new MobEffectInstance(MobEffects.REGENERATION,
                    SACRIFICE_BUFF_TICKS, Math.min(sacrificed - 1, 1)));
            level.sendParticles(ParticleTypes.SOUL_FIRE_FLAME,
                    this.getX(), this.getEyeY(), this.getZ(), 20, 0.5D, 0.6D, 0.5D, 0.03D);
        } else {
            this.heal(4.0F);
            this.addEffect(new MobEffectInstance(MobEffects.REGENERATION, SACRIFICE_BUFF_TICKS / 2, 0));
        }
    }

    // ------------------------------------------------------------------ 技能六：抛花束

    /**
     * 朝正前方甩出花束：锥形范围内的玩家受伤并被减速。
     *
     * <p>用「水平朝向夹角」判定锥形，不看竖直方向 —— 玩家站高一层台阶不该因此躲过。</p>
     */
    private void castBouquet(ServerLevel level) {
        this.playSound(SoundEvents.ARROW_SHOOT, 1.2F, 1.5F);

        Vec3 look = this.getLookAngle();
        Vec3 flat = new Vec3(look.x, 0.0D, look.z);
        if (flat.lengthSqr() < 1.0E-4D) {
            flat = new Vec3(0.0D, 0.0D, 1.0D);
        }
        flat = flat.normalize();
        double cosLimit = Math.cos(Math.toRadians(BOUQUET_HALF_ANGLE));

        // 沿出手方向撒一串花瓣，让"花束往哪儿飞"一眼看出来
        for (int step = 1; step <= 7; step++) {
            double d = step * (BOUQUET_RANGE / 7.0D);
            level.sendParticles(ParticleTypes.HEART,
                    this.getX() + flat.x * d, this.getEyeY() - 0.3D, this.getZ() + flat.z * d,
                    3, 0.2D, 0.2D, 0.2D, 0.01D);
        }

        List<Player> victims = level.getEntitiesOfClass(Player.class,
                new AABB(this.blockPosition()).inflate(BOUQUET_RANGE),
                player -> player.isAlive() && !player.isCreative() && !player.isSpectator());

        for (Player victim : victims) {
            Vec3 to = new Vec3(victim.getX() - this.getX(), 0.0D, victim.getZ() - this.getZ());
            if (to.lengthSqr() > 1.0E-4D && flat.dot(to.normalize()) < cosLimit) {
                continue;
            }
            victim.hurt(this.damageSources().mobAttack(this), (float) BOUQUET_DAMAGE);
            victim.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SLOWDOWN, BOUQUET_SLOW_TICKS, 1));
            level.sendParticles(ParticleTypes.HAPPY_VILLAGER,
                    victim.getX(), victim.getEyeY(), victim.getZ(), 8, 0.3D, 0.3D, 0.3D, 0.02D);
        }
    }

    // ------------------------------------------------------------------ 近战：纱袖横扫

    /**
     * 提袖横抡：面前 ±75°、3 格内的非怪物目标吃 8 点伤害 + 击退 + 短缓慢。
     *
     * <p>判定用「水平朝向夹角」，与花束同一套做法 —— 玩家站高一层台阶不该因此躲过。</p>
     *
     * <p>只打非怪物（外加她当前的目标）：她身边常年挤着自己的召奬（{@link CharmedZombie}），
     * 横扫要是会打到 Monster，这个技能就变成了清场自残。反过来，「她盯着的那个」永远算数，
     * 否则她会对着一只精英怪反复抡空气。</p>
     */
    private void castVeilSwipe(ServerLevel level) {
        this.playSound(SoundEvents.PLAYER_ATTACK_SWEEP, 1.2F, 0.9F);

        Vec3 look = this.getLookAngle();
        Vec3 flat = new Vec3(look.x, 0.0D, look.z);
        if (flat.lengthSqr() < 1.0E-4D) {
            flat = new Vec3(0.0D, 0.0D, 1.0D);
        }
        flat = flat.normalize();
        double cosLimit = Math.cos(Math.toRadians(SWIPE_HALF_ANGLE));

        // 沿扇面铺一道弧：七段刚好覆盖 ±75°，让「打的是哪一片」一眼看得出来
        for (int step = -3; step <= 3; step++) {
            double rad = Math.toRadians(this.getYRot() + step * (SWIPE_HALF_ANGLE / 3.0D));
            double dx = -Math.sin(rad);
            double dz = Math.cos(rad);
            level.sendParticles(ParticleTypes.SWEEP_ATTACK,
                    this.getX() + dx * SWIPE_RADIUS * 0.75D, this.getY() + 1.0D,
                    this.getZ() + dz * SWIPE_RADIUS * 0.75D, 1, 0.0D, 0.0D, 0.0D, 0.0D);
        }

        LivingEntity target = this.getTarget();
        List<LivingEntity> victims = level.getEntitiesOfClass(LivingEntity.class,
                new AABB(this.blockPosition()).inflate(SWIPE_RADIUS),
                e -> e != this && e.isAlive() && (e == target || !(e instanceof Monster)));

        for (LivingEntity victim : victims) {
            Vec3 to = new Vec3(victim.getX() - this.getX(), 0.0D, victim.getZ() - this.getZ());
            if (to.lengthSqr() > 1.0E-4D && flat.dot(to.normalize()) < cosLimit) {
                continue;
            }
            victim.hurt(this.damageSources().mobAttack(this), (float) SWIPE_DAMAGE);
            victim.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SLOWDOWN, SWIPE_SLOW_TICKS, 0));
            Vec3 push = to.lengthSqr() > 1.0E-4D ? to.normalize() : flat;
            victim.push(push.x * SWIPE_KNOCKBACK, 0.32D, push.z * SWIPE_KNOCKBACK);
            // 击退是服务端改的速度：不标脏，客户端那具尸体还会站在原地
            victim.hurtMarked = true;
            level.sendParticles(ParticleTypes.CRIT,
                    victim.getX(), victim.getEyeY(), victim.getZ(), 6, 0.25D, 0.25D, 0.25D, 0.05D);
        }
    }

    // ------------------------------------------------------------------ 近战：纱袖下劈

    /**
     * 抬臂过顶直劈：面前 ±32°、2.2 格内的非怪物目标吃 12 点伤害 + 长缓慢。
     *
     * <p>与横扫同一套判定（水平朝向夹角 / 只打非怪物 / 她当前的目标永远算数），只是把扇面收窄、
     * 伤害调重、击退压到几乎为零 —— 垂直砸下来的力不该把玩家推开，该把他按在原地。</p>
     */
    private void castVeilChop(ServerLevel level) {
        this.playSound(SoundEvents.PLAYER_ATTACK_CRIT, 1.2F, 0.8F);

        Vec3 look = this.getLookAngle();
        Vec3 flat = new Vec3(look.x, 0.0D, look.z);
        if (flat.lengthSqr() < 1.0E-4D) {
            flat = new Vec3(0.0D, 0.0D, 1.0D);
        }
        flat = flat.normalize();
        double cosLimit = Math.cos(Math.toRadians(CHOP_HALF_ANGLE));

        // 垂直劈的轨迹：在正前方立一道「刀线」，让「她劈的是哪一条」一眼看得出来
        for (int step = 0; step < 5; step++) {
            level.sendParticles(ParticleTypes.CRIT,
                    this.getX() + flat.x * CHOP_RADIUS * 0.7D, this.getY() + 0.4D + step * 0.55D,
                    this.getZ() + flat.z * CHOP_RADIUS * 0.7D, 1, 0.0D, 0.0D, 0.0D, 0.0D);
        }

        LivingEntity target = this.getTarget();
        List<LivingEntity> victims = level.getEntitiesOfClass(LivingEntity.class,
                new AABB(this.blockPosition()).inflate(CHOP_RADIUS),
                e -> e != this && e.isAlive() && (e == target || !(e instanceof Monster)));

        for (LivingEntity victim : victims) {
            Vec3 to = new Vec3(victim.getX() - this.getX(), 0.0D, victim.getZ() - this.getZ());
            if (to.lengthSqr() > 1.0E-4D && flat.dot(to.normalize()) < cosLimit) {
                continue;
            }
            victim.hurt(this.damageSources().mobAttack(this), (float) CHOP_DAMAGE);
            victim.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SLOWDOWN, CHOP_SLOW_TICKS, 1));
            Vec3 push = to.lengthSqr() > 1.0E-4D ? to.normalize() : flat;
            victim.push(push.x * CHOP_KNOCKBACK, 0.12D, push.z * CHOP_KNOCKBACK);
            // 服务端改的速度：不标脏，客户端那具尸体会站在原地
            victim.hurtMarked = true;
            level.sendParticles(ParticleTypes.ENCHANTED_HIT,
                    victim.getX(), victim.getEyeY(), victim.getZ(), 10, 0.3D, 0.3D, 0.3D, 0.05D);
        }
    }

    // ------------------------------------------------------------------ 远程：抛花刺

    /**
     * 甩出一束走抛物线的花（{@link BouquetProjectile}）。
     *
     * <p>瞄的是目标眼睛上方一点（{@code DART_ARC_LIFT} 按距离递增）：这一发<b>有重力</b>，
     * 平着瞄中距离一定全打在地上。抬多少是按距离线性给的，不追求弹道解 —— 怪物不会算这个，
     * 而且「差一点擦过去」本来就是让玩家能躲的前提。</p>
     */
    private void castFlowerDart(ServerLevel level) {
        LivingEntity target = this.getTarget();
        if (target == null) {
            return;
        }
        this.playSound(SoundEvents.SNOWBALL_THROW, 1.2F, 1.5F);

        BouquetProjectile dart =
                new BouquetProjectile(ModEntities.BOUQUET_PROJECTILE.get(), this, level);
        double dx = target.getX() - this.getX();
        double dz = target.getZ() - this.getZ();
        double distance = Math.sqrt(dx * dx + dz * dz);
        double dy = target.getEyeY() - this.getEyeY() + DART_ARC_LIFT * distance;
        dart.shoot(dx, dy, dz, (float) DART_SPEED, DART_INACCURACY);
        level.addFreshEntity(dart);
    }

    // ------------------------------------------------------------------ 技能七：鬼嫁之吻

    /**
     * 抓住最近的一个玩家：拉到自己面前 + 吸血 + 挂虚弱。
     *
     * <p>只取最近的一个 —— 这是单体招，多点命中会把她变成比尖啸更划算的群伤，
     * 跟"贴脸高风险高收益"的定位就冲突了。</p>
     */
    private void castBridalKiss(ServerLevel level) {
        this.playSound(SoundEvents.ZOMBIE_VILLAGER_AMBIENT, 1.4F, 0.7F);

        List<Player> victims = level.getEntitiesOfClass(Player.class,
                new AABB(this.blockPosition()).inflate(KISS_RANGE + 1.0D),
                player -> player.isAlive() && !player.isCreative() && !player.isSpectator());
        if (victims.isEmpty()) {
            return;
        }
        victims.sort((a, b) -> Double.compare(this.distanceToSqr(a), this.distanceToSqr(b)));
        Player victim = victims.get(0);

        victim.hurt(this.damageSources().mobAttack(this), (float) KISS_DAMAGE);
        victim.addEffect(new MobEffectInstance(MobEffects.WEAKNESS, 100, 0));
        this.heal((float) KISS_LIFESTEAL);

        // 往她身上拽：和尖啸同一套做法，竖直方向只给一点点
        Vec3 pull = new Vec3(this.getX() - victim.getX(), 0.0D, this.getZ() - victim.getZ());
        if (pull.lengthSqr() > 1.0E-4D) {
            pull = pull.normalize().scale(1.1D);
        }
        victim.push(pull.x, 0.12D, pull.z);
        victim.hurtMarked = true;

        level.sendParticles(ParticleTypes.HEART,
                victim.getX(), victim.getEyeY(), victim.getZ(), 12, 0.3D, 0.3D, 0.3D, 0.03D);
        level.sendParticles(ParticleTypes.DAMAGE_INDICATOR,
                victim.getX(), victim.getEyeY(), victim.getZ(), 6, 0.2D, 0.2D, 0.2D, 0.02D);
        level.sendParticles(ParticleTypes.HEART,
                this.getX(), this.getEyeY(), this.getZ(), 8, 0.4D, 0.4D, 0.4D, 0.02D);
    }

    // ------------------------------------------------------------------ 技能八：血纱回春

    /**
     * 「缓慢回血」：命中瞬间给**自己**与半径内所有召奬挂上再生。
     *
     * <p>刻意用**等级 0 + 长时长**（{@link #REGEN_TICKS}）而不是一次大治疗 —— 低等级再生是
     * 「每 50 tick 回 1 点」，也就是说她回满一管血要十几秒，玩家有时间打断这场回春；
     * 直接回一大口反而会让战斗节奏崩掉（玩家刚打出的伤害被瞬间抹平，读不出自己有没有进展）。</p>
     *
     * <p>顺带给一层吸收：吸收是「上限」不是「回复」，不长血条但能挡住下一轮爆发的头几下，
     * 正好对应她在玩家下一波进攻里撑住前几秒的定位。</p>
     */
    private void castBloodRegen(ServerLevel level) {
        boolean blood = this.isBloodMoon(level);
        this.playSound(SoundEvents.BEACON_POWER_SELECT, 1.2F, 1.4F);

        this.heal(REGEN_BURST_HEAL);
        this.addEffect(new MobEffectInstance(MobEffects.REGENERATION,
                blood ? REGEN_TICKS + 200 : REGEN_TICKS, 0));
        this.addEffect(new MobEffectInstance(MobEffects.ABSORPTION,
                REGEN_ABSORPTION_TICKS, blood ? 2 : 1));

        // 她自己：一圈上升的花蜜柱，配合 castAura 的螺旋，命中这一刻明显更密
        level.sendParticles(ParticleTypes.FALLING_NECTAR,
                this.getX(), this.getY() + 1.0D, this.getZ(), 30, 0.6D, 1.0D, 0.6D, 0.02D);
        level.sendParticles(ParticleTypes.HEART,
                this.getX(), this.getEyeY(), this.getZ(), 12, 0.5D, 0.5D, 0.5D, 0.02D);

        // 召奬一起回：这是「新娘的场面」——她的队伍在她的纱下集体回血
        List<CharmedZombie> minions = level.getEntitiesOfClass(CharmedZombie.class,
                new AABB(this.blockPosition()).inflate(REGEN_MINION_RADIUS),
                CharmedZombie::isAlive);
        for (CharmedZombie minion : minions) {
            minion.addEffect(new MobEffectInstance(MobEffects.REGENERATION, REGEN_TICKS / 2, 0));
            level.sendParticles(ParticleTypes.HEART,
                    minion.getX(), minion.getEyeY(), minion.getZ(), 5, 0.3D, 0.3D, 0.3D, 0.02D);
        }
        if (!minions.isEmpty()) {
            level.sendParticles(ParticleTypes.FALLING_NECTAR,
                    this.getX(), this.getY() + 0.5D, this.getZ(),
                    6 * minions.size(), 2.5D, 0.4D, 2.5D, 0.01D);
        }
    }

    // ------------------------------------------------------------------ 召奬公用

    /**
     * 在自身周围召唤 {@code count} 只召奬，但不会突破 {@link #MINION_CAP}。
     * 三套技能的召唤全部走这里，封顶逻辑就只有一份。
     */
    private int summonMinions(ServerLevel level, CharmedZombie.Variant variant, int count, int lifetime) {
        int quota = MINION_CAP - this.minionCount();
        int summoned = 0;
        for (int i = 0; i < count && summoned < quota; i++) {
            if (this.summonMinion(level, variant, lifetime)) {
                summoned++;
            }
        }
        return summoned;
    }

    /** 找块空位放一只召奬，并把她的当前目标交接过去。 */
    private boolean summonMinion(ServerLevel level, CharmedZombie.Variant variant, int lifetime) {
        for (int attempt = 0; attempt < 8; attempt++) {
            double angle = this.random.nextDouble() * Math.PI * 2.0D;
            double distance = 2.5D + this.random.nextDouble() * 3.5D;
            BlockPos spawn = BlockPos.containing(
                    this.getX() + Math.cos(angle) * distance,
                    this.getY(),
                    this.getZ() + Math.sin(angle) * distance);
            if (!level.isEmptyBlock(spawn) || !level.isEmptyBlock(spawn.above())) {
                continue;
            }
            CharmedZombie minion = ModEntities.CHARMED.get().create(level);
            if (minion == null) {
                return false;
            }
            minion.moveTo(spawn.getX() + 0.5D, spawn.getY(), spawn.getZ() + 0.5D,
                    this.random.nextFloat() * 360.0F, 0.0F);
            minion.finalizeSpawn(level,
                    level.getCurrentDifficultyAt(minion.blockPosition()),
                    MobSpawnType.MOB_SUMMONED, null, null);
            // 放在 finalizeSpawn 之后：存活时限、成色和入场 buff 不能被原版那套随机初始化冲掉
            minion.arm(lifetime, variant, this.getTarget());
            this.armMinion(level, minion);
            this.quickenMinion(level, minion);
            if (level.addFreshEntity(minion)) {
                level.sendParticles(ParticleTypes.SCULK_SOUL,
                        minion.getX(), minion.getEyeY(), minion.getZ(), 6, 0.2D, 0.3D, 0.2D, 0.02D);
                return true;
            }
            return false;
        }
        return false;
    }

    /**
     * 有概率给召奬塞一把武器。
     *
     * <p>「手里有根管子的僵尸」和「空手僵尸」在远远一眼里就是两种威胁，这是这套召唤物里
     * 最便宜的表现力提升 —— 而且不改变它们的 AI（僵尸本来就不会开枪），只是让它们更不像背景板。</p>
     *
     * <p>两个刻意的取舍：<b>掉落概率设为 0</b>（她召出来的东西不该成为玩家的枪械补给线，
     * 想拿枪得去打别的精英）；<b>给一点近战加伤</b>（不然「持武器」纯粹是贴图上的装饰）。</p>
     */
    private void armMinion(ServerLevel level, CharmedZombie minion) {
        float chance = this.isBloodMoon(level) ? MINION_ARM_CHANCE_BLOOD : MINION_ARM_CHANCE;
        if (this.random.nextFloat() >= chance) {
            return;
        }
        minion.setItemInHand(InteractionHand.MAIN_HAND, new ItemStack(this.pickMinionWeapon()));
        minion.setDropChance(EquipmentSlot.MAINHAND, 0.0F);
        AttributeInstance damage = minion.getAttribute(Attributes.ATTACK_DAMAGE);
        if (damage != null && damage.getModifier(ARMED_DAMAGE_ID) == null) {
            damage.addTransientModifier(new AttributeModifier(ARMED_DAMAGE_ID, "bride_armed",
                    ARMED_DAMAGE_BONUS, AttributeModifier.Operation.ADDITION));
        }
        // 一点附魔光：让「这只拿到了家伙」在混战里也能被余光捕捉到
        level.sendParticles(ParticleTypes.ENCHANTED_HIT,
                minion.getX(), minion.getEyeY() - 0.4D, minion.getZ(),
                4, 0.2D, 0.3D, 0.2D, 0.02D);
    }

    /**
     * 有概率把召奬变成「迅捷」的：移速按基础值加成。
     *
     * <p>用属性修饰符而不是速度药水效果：buff 会到期、会被牛奶洗掉，而「跑得快」是它出生时
     * 抽到的成色，应当与它的存活时限同寿命。做成属性还有两个顺带好处 —— 玩家能靠观察分辨出
     * 队伍里哪只更快，服务端也能按属性判断要不要给它加脚底粒子。</p>
     *
     * <p>和 {@link #armMinion} 各自独立抽签：拿枪的和跑得快的可以同时成立，
     * 但两者用的是不同的属性 / 装备通道，互不干扰。</p>
     */
    private void quickenMinion(ServerLevel level, CharmedZombie minion) {
        float chance = this.isBloodMoon(level) ? MINION_SWIFT_CHANCE_BLOOD : MINION_SWIFT_CHANCE;
        if (this.random.nextFloat() >= chance) {
            return;
        }
        minion.makeSwift(SWIFT_SPEED_BONUS);
        // 起手那一撮尘：抽中与否当场有反馈，不必等它跑起来
        level.sendParticles(ParticleTypes.CLOUD,
                minion.getX(), minion.getY() + 0.1D, minion.getZ(),
                6, 0.25D, 0.1D, 0.25D, 0.03D);
    }

    /**
     * 抽武器：短枪常见、长枪稀有。
     *
     * <p>数字表已经搬到 {@link GunProfile#random} —— 那里是唯一来源：召奬配枪、精英配枪、
     * 子弹装订都从同一张表取，免得两处数字慢慢漂开。用<b>枪管长度</b>做威胁分级是刻意的，
     * 玩家不需要读名字，看到召奬手里那根管子长就知道该优先处理哪一只。</p>
     */
    private Item pickMinionWeapon() {
        return GunProfile.random(this.random).item();
    }

    /** 场上还活着多少只召奬。 */
    private int minionCount() {
        if (!(this.level() instanceof ServerLevel level)) {
            return 0;
        }
        return level.getEntitiesOfClass(CharmedZombie.class,
                new AABB(this.blockPosition()).inflate(32.0D), CharmedZombie::isAlive).size();
    }

    /** 当前是不是血月（含超级血月）。 */
    private boolean isBloodMoon(Level level) {
        MoonEvent moon = MoonEventManager.getMoonEvent(level);
        return moon != null && moon.isBloodMoon();
    }

    /**
     * 这套技能的粒子色板：**一处定义、三处用**（起手地圈、施法光环、命中爆发）。
     * 想给某套技能换味道只改这里，不必去搜散落的 {@code ParticleTypes.XXX}。
     */
    private SimpleParticleType auraParticle() {
        return switch (this.getAbility()) {
            case DEATH_CHIME -> ParticleTypes.HEART;
            case CONSORT -> ParticleTypes.HAPPY_VILLAGER;
            case SOUL_SHRIEK -> ParticleTypes.SCULK_SOUL;
            case VEIL_SNARE -> ParticleTypes.END_ROD;
            // 花束从「村民绿星」换成樱花叶：和「甩花」的动作对得上
            case BOUQUET -> ParticleTypes.CHERRY_LEAVES;
            case BRIDAL_KISS -> ParticleTypes.HEART;
            case SACRIFICE -> ParticleTypes.SOUL;
            case BLOOD_REGEN -> ParticleTypes.FALLING_NECTAR;
            case VEIL_SWIPE -> ParticleTypes.SWEEP_ATTACK;
            case FLOWER_DART -> ParticleTypes.SPORE_BLOSSOM_AIR;
            case VEIL_CHOP -> ParticleTypes.ENCHANTED_HIT;
            default -> null;
        };
    }

    /** 起手时在脚边撒一圈粒子，让「她要出招了」在远处也看得见。 */
    private void ambientRing() {
        if (this.level() instanceof ServerLevel level) {
            SimpleParticleType particle = this.auraParticle();
            if (particle == null) {
                return;
            }
            level.sendParticles(particle, this.getX(), this.getY() + 0.2D, this.getZ(),
                    10, 1.0D, 0.1D, 1.0D, 0.0D);
        }
    }

    /**
     * 施法**持续期间**每 {@link #AURA_PERIOD} tick 撒一圈上升的粒子。
     *
     * <p>前摇动辄 1 秒以上，只靠起手一撮粒子的话，中段在战斗中根本看不出来她在蓄哪一招；
     * 光环把「正在施法」这件事在整个前摇里持续广播出去，也让每套技能有了自己的尾迹。</p>
     */
    private void castAura() {
        if (!(this.level() instanceof ServerLevel level)) {
            return;
        }
        SimpleParticleType particle = this.auraParticle();
        if (particle == null) {
            return;
        }
        double angle = this.random.nextDouble() * Math.PI * 2.0D;
        double radius = 0.7D + this.random.nextDouble() * 0.6D;
        // 螺旋上升：y 从脚踝扫到头顶，读起来是「气在往上走」
        double rise = (this.tickCount % 20) / 20.0D;
        level.sendParticles(particle,
                this.getX() + Math.cos(angle) * radius,
                this.getY() + 0.15D + rise * 1.9D,
                this.getZ() + Math.sin(angle) * radius,
                2, 0.05D, 0.05D, 0.05D, 0.01D);
    }

    // ------------------------------------------------------------------ 声音

    @Override
    protected SoundEvent getAmbientSound() {
        return SoundEvents.ZOMBIE_VILLAGER_AMBIENT;
    }

    @Override
    protected SoundEvent getHurtSound(DamageSource source) {
        return SoundEvents.ZOMBIE_VILLAGER_HURT;
    }

    @Override
    protected SoundEvent getDeathSound() {
        return SoundEvents.ZOMBIE_VILLAGER_DEATH;
    }
}