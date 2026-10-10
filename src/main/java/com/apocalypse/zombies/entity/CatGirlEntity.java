package com.apocalypse.zombies.entity;

import java.util.List;

import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.tags.BlockTags;
import net.minecraft.tags.DamageTypeTags;
import net.minecraft.tags.ItemTags;
import net.minecraft.util.Mth;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.SimpleContainer;
import net.minecraft.world.SimpleMenuProvider;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.AgeableMob;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import com.apocalypse.zombies.entity.ai.CatGirlBowGoal;
import com.apocalypse.zombies.entity.ai.CatGirlBridgeGoal;
import com.apocalypse.zombies.entity.ai.CatGirlContainerGoal;
import com.apocalypse.zombies.entity.ai.CatGirlEscortGoal;
import com.apocalypse.zombies.entity.ai.CatGirlNeedGoal;
import com.apocalypse.zombies.entity.ai.CatGirlClearWayGoal;
import com.apocalypse.zombies.entity.ai.CatGirlNavigation;
import net.minecraft.world.entity.ai.goal.FloatGoal;
import net.minecraft.world.entity.ai.goal.FollowOwnerGoal;
import net.minecraft.world.entity.ai.goal.LookAtPlayerGoal;
import net.minecraft.world.entity.ai.goal.MeleeAttackGoal;
import net.minecraft.world.entity.ai.goal.RandomLookAroundGoal;
import net.minecraft.world.entity.ai.goal.WaterAvoidingRandomStrollGoal;
import net.minecraft.world.entity.ai.goal.target.NearestAttackableTargetGoal;
import net.minecraft.world.entity.ai.goal.target.OwnerHurtByTargetGoal;
import net.minecraft.world.entity.ai.goal.target.OwnerHurtTargetGoal;
import net.minecraft.world.entity.TamableAnimal;   // 1.20.1：不在 .animal 子包（写成 .animal 会让整类变未知类型并级联炸掉菜单/渲染器）
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraftforge.common.Tags;

import software.bernie.geckolib.animatable.GeoEntity;
import software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache;
import software.bernie.geckolib.core.animation.AnimatableManager;
import software.bernie.geckolib.core.animation.AnimationController;
import software.bernie.geckolib.core.animation.AnimationState;
import software.bernie.geckolib.core.animation.RawAnimation;
import software.bernie.geckolib.core.object.PlayState;
import software.bernie.geckolib.util.GeckoLibUtil;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.ai.AllyJudge;
import com.apocalypse.zombies.entity.ai.CatGirlStationGoal;
import com.apocalypse.zombies.entity.ai.WorkBlockGoal;
import com.apocalypse.zombies.entity.menu.CatGirlTradeMenu;

/**
 * 猫耳娘 —— 可驯服的随从。
 *
 * <p>玩法闭环：喂鱼驯服 → 空手右键循环切换任务（跟随 / 伐木 / 挖矿 / 战斗）→
 * 把工具武器交到她手里（播「拿取」动画，之后静置/行走换成持物姿态）→
 * 潜行右键打开以物易物菜单（任意物品——含模组物品——都能折算成爱心币，
 * 也能用爱心币买下她伐木挖矿攒下的库存）。</p>
 *
 * <p><b>为什么继承 {@link TamableAnimal}</b>：本模组的阵营判据
 * （{@link AllyJudge#isPlayerSide}）认得「已驯服的 TamableAnimal」，
 * 于是 {@code NoInfighting}、{@code AllySafeHurtByTargetGoal} 这些
 * 友军逻辑一条都不用改 —— 她天生不会和玩家阵营互殴。</p>
 *
 * <p><b>无敌的范围</b>（按需求确认）：只对<b>敌对生物</b>（{@link AllyJudge#isHorde}，
 * 含它们射出的箭、炸弹、酸液等）完全免伤；玩家、摔落、岩浆照常结算。
 * 判定放在 {@link #isInvulnerableTo}，而不是改血量或抗性，
 * 免伤是「伤害不发生」，连击退和仇恨都一并消失。</p>
 *
 * <p><b>动画分两条控制器</b>：movement 负责 idle/walk（持物时换 idle_hold/walk_hold），
 * action 负责 equip / attack / chop / mine / hurt / death，两者互斥
 * （action 激活时 movement 返回 STOP）—— 与美女僵尸的技能做法一致，
 * 免得两条控制器抢同一根骨骼把姿势搅成四不像。</p>
 */
public class CatGirlEntity extends TamableAnimal implements GeoEntity {

    // ------------------------------------------------------------ 动画剪辑名（与 animation.json 一一对应）
    public static final String ANIM_IDLE = "idle";
    public static final String ANIM_WALK = "walk";
    public static final String ANIM_IDLE_HOLD = "idle_hold";
    public static final String ANIM_WALK_HOLD = "walk_hold";
    public static final String ANIM_EQUIP = "equip";
    public static final String ANIM_ATTACK = "attack";
    public static final String ANIM_CHOP = "chop";
    public static final String ANIM_MINE = "mine";
    public static final String ANIM_HURT = "hurt";
    public static final String ANIM_DEATH = "death";

    // ------------------------------------------------------------ action 通道取值
    public static final int ACTION_NONE = 0;
    public static final int ACTION_EQUIP = 1;
    public static final int ACTION_ATTACK = 2;
    public static final int ACTION_CHOP = 3;
    public static final int ACTION_MINE = 4;
    public static final int ACTION_HURT = 5;

    /** 她的物品栏（快捷栏）格数：存档里槽位 0–8，交易界面最下面那一行。 */
    public static final int GOODS_HOTBAR = 9;

    /** 她的背包格数：存档里槽位 9–35，交易界面上面三行。 */
    public static final int GOODS_BACKPACK = 27;

    /**
     * 她自己的库存总格数：伐木 / 挖矿的产物、她自己做的东西都堆这里，
     * 也是交易菜单里可买的那 36 格 —— 和玩家的「背包 27 + 物品栏 9」同款排布。
     *
     * <p>存档兼容：{@code CatGirlGoods} 是按槽位下标原样存的，老存档里那 9 格照旧落在 0–8，
     * 9–35 是空的，不需要任何迁移。</p>
     */
    public static final int GOODS_SIZE = GOODS_HOTBAR + GOODS_BACKPACK;

    private static final EntityDataAccessor<Integer> DATA_JOB =
            SynchedEntityData.defineId(CatGirlEntity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_ACTION =
            SynchedEntityData.defineId(CatGirlEntity.class, EntityDataSerializers.INT);

    private final AnimatableInstanceCache geoCache = GeckoLibUtil.createInstanceCache(this);

    private final SimpleContainer goods = new SimpleContainer(GOODS_SIZE);

    /** 日常维护（换装 / 修耐久 / 自制品）的节拍计数。 */
    private int maintenanceTicks = 20;
    private int craftTicks = 40;
    private int pickupTicks = 5;

    /** 盔甲四个槽（她自己穿）。 */
    private static final net.minecraft.world.entity.EquipmentSlot[] ARMOR_SLOTS = {
            net.minecraft.world.entity.EquipmentSlot.HEAD,
            net.minecraft.world.entity.EquipmentSlot.CHEST,
            net.minecraft.world.entity.EquipmentSlot.LEGS,
            net.minecraft.world.entity.EquipmentSlot.FEET};

    /** 当前动作还剩多少 tick；服务端倒计时，到点回 NONE。 */
    private int actionTicks;

    public CatGirlEntity(EntityType<? extends CatGirlEntity> type, Level level) {
        super(type, level);
        this.setPersistenceRequired();
    }

    // ------------------------------------------------------------ 属性

    public static AttributeSupplier.Builder createAttributes() {
        return Mob.createMobAttributes()
                .add(Attributes.MAX_HEALTH, 40.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.24D)
                .add(Attributes.ATTACK_DAMAGE, 4.0D)
                .add(Attributes.ARMOR, 2.0D)
                .add(Attributes.FOLLOW_RANGE, 32.0D);
    }

    /** 自主模式：她按背包与周围环境自己挑活干（CatGirlNeedGoal）。玩家手动切过就关。 */
    private boolean autoJob = true;

    /** 她的储物点（主人绑定的容器）；null = 没绑，她一个容器都不碰。 */
    private BlockPos storage;

    // ------------------------------------------------------------ 一键挖掘订单

    /** 一键挖掘的目标方块（null = 没订单）。玩家用 /apocalypse catgirl mine 下单。 */
    private Block mineOrderBlock;
    /** 一键挖掘还差几块。 */
    private int mineOrderLeft;

    // ------------------------------------------------------------ 任务模式

    /** 玩家下达的任务。空手右键循环切换。 */
    public enum Job {
        FOLLOW,
        LUMBER,
        MINE,
        FIGHT;

        public Job next() {
            return values()[(this.ordinal() + 1) % values().length];
        }

        /** 语言文件里的模式名键，如 {@code cat_girl.job.lumber}。 */
        public String langKey() {
            return "cat_girl.job." + this.name().toLowerCase(java.util.Locale.ROOT);
        }
    }

    public Job getJob() {
        int raw = this.entityData.get(DATA_JOB);
        Job[] all = Job.values();
        return all[Mth.clamp(raw, 0, all.length - 1)];
    }

    public void setJob(Job job) {
        this.entityData.set(DATA_JOB, job.ordinal());
    }

    // ------------------------------------------------------------ 自主 / 储物点

    /** 自主模式开着时，CatGirlNeedGoal 会按需求替她挑工种。 */
    public boolean isAutoJob() {
        return this.autoJob;
    }

    public void setAutoJob(boolean auto) {
        this.autoJob = auto;
    }

    /**
     * 玩家自己切工种（给工具 / 空手右键 / 命令）：自动决策立刻让位。
     *
     * <p>不这么做的话，你刚让它去砍树，两秒后它自己又跑去挖矿了。</p>
     */
    public void applyPlayerJob(Job job) {
        this.autoJob = false;
        this.setJob(job);
    }

    /** 她的储物点（/apocalypse catgirl chest 绑定）；没绑返回 null。 */
    public BlockPos getStorage() {
        return this.storage;
    }

    public void setStorage(BlockPos pos) {
        this.storage = pos == null ? null : pos.immutable();
    }

    // ------------------------------------------------------------ action 通道

    public int getAction() {
        return this.entityData.get(DATA_ACTION);
    }

    /** 服务端设置动作（带持续时长，tick 到点自动回 NONE）。 */
    public void setAction(int action, int ticks) {
        if (this.level().isClientSide) {
            return;
        }
        this.entityData.set(DATA_ACTION, action);
        this.actionTicks = Math.max(0, ticks);
    }

    /** 劳作循环用：只要还在干活就每 tick 续上，不写结束时间。 */
    public void holdAction(int action) {
        if (this.level().isClientSide) {
            return;
        }
        this.entityData.set(DATA_ACTION, action);
        this.actionTicks = 5;
    }

    // ------------------------------------------------------------ 一键挖掘订单

    /** 有没有正在执行的「一键挖掘」订单。 */
    public boolean hasMineOrder() {
        return this.mineOrderLeft > 0 && this.mineOrderBlock != null;
    }

    /** 订单目标方块（没订单时 null）。 */
    public Block getMineOrderBlock() {
        return this.mineOrderBlock;
    }

    public int getMineOrderLeft() {
        return this.mineOrderLeft;
    }

    /**
     * 下单：去挖 {@code count} 块 {@code block}。
     *
     * <p>数量由调用方按 {@code cat_girl.mine_max_blocks} 夹好；这里只记账。
     * 下单同时把她切到挖矿工种 —— 不然她还在伐木，永远不会去碰这个目标。</p>
     */
    public void orderMine(Block block, int count) {
        this.mineOrderBlock = block;
        this.mineOrderLeft = Math.max(1, count);
        this.setJob(Job.MINE);
    }

    public void clearMineOrder() {
        this.mineOrderBlock = null;
        this.mineOrderLeft = 0;
    }

    public boolean matchesMineOrder(BlockState state) {
        return this.mineOrderBlock != null && state.is(this.mineOrderBlock);
    }

    /**
     * 记一块订单产出。挖满时清掉订单并回主人一句 —— 免得她挖完还在原地转圈，
     * 主人也不知道该不该等她。
     */
    public void minedOne(BlockState state) {
        if (!this.matchesMineOrder(state)) {
            return;
        }
        if (--this.mineOrderLeft > 0) {
            return;
        }
        String done = this.mineOrderBlock.getName().getString();
        this.clearMineOrder();
        Player owner = this.getOwner() instanceof Player player ? player : null;
        if (owner != null) {
            owner.displayClientMessage(Component.translatable("cat_girl.mine.done", done), false);
        }
    }

    // ------------------------------------------------------------ 工作方块（合成台 / 熔炉）

    /** 她当前认定的工作方块（走过去或自己放好之后写进来）。 */
    private BlockPos stationPos;
    private int stationTicksLeft;
    /** 就近找站台的扫描缓存：Goal 的 canUse 每 tick 都可能问一遍。 */
    private CatGirlStation.Kind stationScanKind;
    private long stationScanAt = -1000L;
    private BlockPos stationScanHit;

    /** 认定一个工作方块，ticks 内有效（走开 / 到期就作废）。 */
    public void setStation(BlockPos pos, int ticks) {
        this.stationPos = pos;
        this.stationTicksLeft = ticks;
    }

    /** 她是不是正站在这一类工作方块边上（4 格内，且那个方块还在）。 */
    public boolean isAtStation(CatGirlStation.Kind kind) {
        if (this.stationTicksLeft <= 0 || this.stationPos == null) {
            return false;
        }
        if (!CatGirlStation.matches(this.level(), this.stationPos, kind)) {
            return false;
        }
        return this.blockPosition().distSqr(this.stationPos) <= 16;
    }

    /** 就近找工作方块（60 tick 缓存，一次扫描同时服务 Goal 与制作门槛）。 */
    public BlockPos stationNear(CatGirlStation.Kind kind, int radius) {
        long now = this.level().getGameTime();
        if (this.stationScanKind == kind && now - this.stationScanAt < 60L) {
            return this.stationScanHit;
        }
        this.stationScanKind = kind;
        this.stationScanAt = now;
        this.stationScanHit = CatGirlStation.findNear(this, kind, radius);
        return this.stationScanHit;
    }

    /** 按条件从库存里取走一件（真扣掉）；放工作方块用。 */
    public boolean consumeOneMatching(java.util.function.Predicate<ItemStack> want) {
        for (int i = 0; i < this.goods.getContainerSize(); i++) {
            ItemStack s = this.goods.getItem(i);
            if (!s.isEmpty() && want.test(s)) {
                this.goods.removeItem(i, 1);
                return true;
            }
        }
        return false;
    }

    /** 按条件从库存里取出一件（真取走）；换工具用。 */
    public ItemStack takeBestFor(java.util.function.Predicate<ItemStack> want) {
        int bestIdx = -1;
        int best = -1;
        for (int i = 0; i < this.goods.getContainerSize(); i++) {
            ItemStack s = this.goods.getItem(i);
            if (s.isEmpty() || !want.test(s)) {
                continue;
            }
            int rank = gearRank(s);
            if (rank > best) {
                best = rank;
                bestIdx = i;
            }
        }
        return bestIdx < 0 ? ItemStack.EMPTY : this.goods.removeItem(bestIdx, 1);
    }

    /** 库存里有没有符合条件的（只看不动）。 */
    public boolean hasGoodsMatching(java.util.function.Predicate<ItemStack> want) {
        for (int i = 0; i < this.goods.getContainerSize(); i++) {
            ItemStack s = this.goods.getItem(i);
            if (!s.isEmpty() && want.test(s)) {
                return true;
            }
        }
        return false;
    }

    public SimpleContainer getGoods() {
        return this.goods;
    }

    /** 手里有没有东西（决定 idle/walk 还是 idle_hold/walk_hold）。 */
    public boolean isHoldingAnything() {
        return !this.getMainHandItem().isEmpty();
    }

    // ------------------------------------------------------------ 注册

    @Override
    protected void registerGoals() {
        this.goalSelector.addGoal(0, new FloatGoal(this));
        // 只做决策、不占执行权：按需求给她挑工种（可以关，关了就只听玩家的）
        this.goalSelector.addGoal(0, new CatGirlNeedGoal(this));
        // 走路优先级放在劳作之上：主人走出去十格，她会先跟上再继续干活
        // 速度走 Config.CAT_GIRL_FOLLOW_SPEED（默认 1.3）：原版跟班的 1.15 在主人冲刺时会被稳稳甩掉。
        // 注册期读一次，所以改完这个值要重进世界。
        this.goalSelector.addGoal(1,
                new FollowOwnerGoal(this, Config.CAT_GIRL_FOLLOW_SPEED.get(), 10.0F, 2.5F, false));
        // 弓排在近战之前（同优先级先注册者优先）：够远 + 有箭 + 有视线时她放箭，
        // 贴脸（<=3 格）弓的 canUse 不成立，自动轮到下面的近战 —— 不需要另设优先级数字。
        this.goalSelector.addGoal(2, new CatGirlBowGoal(this));
        this.goalSelector.addGoal(2, new MeleeAttackGoal(this, 1.2D, true));
        // 护卫排在近战之后：手里有仇人先打，站位的活等它打完再说
        this.goalSelector.addGoal(2, new CatGirlEscortGoal(this));
        // 开路 / 搭桥：只在「正在导航且卡住」时接管，所以排在战斗之后、劳作之前。
        this.goalSelector.addGoal(3, new CatGirlClearWayGoal(this));
        this.goalSelector.addGoal(3, new CatGirlBridgeGoal(this));
        this.goalSelector.addGoal(4, WorkBlockGoal.forOrder(this, this::isMineOrderTarget, ACTION_MINE));
        this.goalSelector.addGoal(5, new WorkBlockGoal(this, Job.LUMBER, this::isLog, ACTION_CHOP));
        this.goalSelector.addGoal(6, new WorkBlockGoal(this, Job.MINE, this::isMineTarget, ACTION_MINE));
        // 用容器排在劳作之后：先干活，多余的成品才收进箱子
        this.goalSelector.addGoal(7, new CatGirlStationGoal(this));
        this.goalSelector.addGoal(7, new CatGirlContainerGoal(this));
        this.goalSelector.addGoal(7, new WaterAvoidingRandomStrollGoal(this, 1.0D));
        this.goalSelector.addGoal(8, new LookAtPlayerGoal(this, Player.class, 8.0F));
        this.goalSelector.addGoal(9, new RandomLookAroundGoal(this));

        // 保护主人：这两种目标不分模式都会接（被打了总得还手）
        this.targetSelector.addGoal(1, new OwnerHurtByTargetGoal(this));
        this.targetSelector.addGoal(2, new OwnerHurtTargetGoal(this));
        // 「打怪」模式：主动索敌（只认敌对生物，且她驯服后算玩家阵营，不会误伤友军）
        this.targetSelector.addGoal(3, new NearestAttackableTargetGoal<LivingEntity>(this, LivingEntity.class, 10,
                true, false, target -> AllyJudge.isHorde(target)) {
            @Override
            public boolean canUse() {
                return CatGirlEntity.this.getJob() == Job.FIGHT && super.canUse();
            }
        });
    }

    /** 伐木目标：原木（保护名单 / 容器类仍然一律不碰）。 */
    private boolean isLog(BlockPos pos) {
        BlockState state = this.level().getBlockState(pos);
        return state.is(BlockTags.LOGS)
                && CatGirlHarvest.isMineable(this.level(), pos, state, CatGirlHarvest.protectedExtra());
    }

    /**
     * 自主挖矿目标：原来只认矿石；{@code mine_all} 打开后连土 / 沙 / 砾 / 石头 / 树叶都算
     * —— 但**只认自然方块**，免得她把主人的房子当成矿脉。
     */
    private boolean isMineTarget(BlockPos pos) {
        BlockState state = this.level().getBlockState(pos);
        if (!CatGirlHarvest.isMineable(this.level(), pos, state, CatGirlHarvest.protectedExtra())) {
            return false;
        }
        if (state.is(Tags.Blocks.ORES)) {
            return true;
        }
        return Config.CAT_GIRL_MINE_ALL.get() && CatGirlHarvest.isNaturalTarget(state);
    }

    /**
     * 一键挖掘订单的目标：只要是她点的那一种、且没进保护名单。
     *
     * <p>比自主挖矿宽 —— 泥土 / 木头 / 树叶 / 玻璃都接单，因为这是主人明确点的名。</p>
     */
    private boolean isMineOrderTarget(BlockPos pos) {
        if (!this.hasMineOrder()) {
            return false;
        }
        BlockState state = this.level().getBlockState(pos);
        return this.matchesMineOrder(state)
                && CatGirlHarvest.isMineable(this.level(), pos, state, CatGirlHarvest.protectedExtra());
    }

    /**
     * 换成会开门 / 会浮水的导航（{@link CatGirlNavigation}）。
     *
     * <p>原版 {@code Mob} 的默认导航把她当僵尸用：门就是墙、水就是死路，
     * 于是「走过去砍那棵树」经常变成站在门口原地抽搐。</p>
     */
    @Override
    protected net.minecraft.world.entity.ai.navigation.PathNavigation createNavigation(
            net.minecraft.world.level.Level level) {
        return new CatGirlNavigation(this, level);
    }

    // ------------------------------------------------------------ 数据同步

    @Override
    protected void defineSynchedData() {
        super.defineSynchedData();
        this.entityData.define(DATA_JOB, Job.FOLLOW.ordinal());
        this.entityData.define(DATA_ACTION, ACTION_NONE);
    }

    @Override
    public void addAdditionalSaveData(CompoundTag tag) {
        super.addAdditionalSaveData(tag);
        tag.putInt("CatGirlJob", this.getJob().ordinal());
        tag.put("CatGirlGoods", this.goods.createTag());
        tag.putBoolean("CatGirlAutoJob", this.autoJob);
        if (this.storage != null) {
            tag.putLong("CatGirlChest", this.storage.asLong());
        }
        if (this.mineOrderBlock != null && this.mineOrderLeft > 0) {
            tag.putString("CatGirlMineBlock", net.minecraft.core.registries.BuiltInRegistries.BLOCK
                    .getKey(this.mineOrderBlock).toString());
            tag.putInt("CatGirlMineLeft", this.mineOrderLeft);
        }
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag) {
        super.readAdditionalSaveData(tag);
        if (tag.contains("CatGirlJob")) {
            int raw = tag.getInt("CatGirlJob");
            Job[] all = Job.values();
            this.setJob(all[Mth.clamp(raw, 0, all.length - 1)]);
        }
        if (tag.contains("CatGirlGoods")) {
            this.goods.fromTag(tag.getList("CatGirlGoods", 10));
        }
        // 老存档没有这两个键：默认「自动 + 没绑储物点」，正好是安全的那一侧
        this.autoJob = !tag.contains("CatGirlAutoJob") || tag.getBoolean("CatGirlAutoJob");
        this.storage = tag.contains("CatGirlChest")
                ? BlockPos.of(tag.getLong("CatGirlChest")) : null;
        if (tag.contains("CatGirlMineBlock")) {
            net.minecraft.resources.ResourceLocation rl =
                    net.minecraft.resources.ResourceLocation.tryParse(tag.getString("CatGirlMineBlock"));
            this.mineOrderBlock = rl == null ? null
                    : net.minecraft.core.registries.BuiltInRegistries.BLOCK.getOptional(rl).orElse(null);
            this.mineOrderLeft = this.mineOrderBlock == null ? 0 : tag.getInt("CatGirlMineLeft");
        } else {
            this.clearMineOrder();
        }
    }

    // ------------------------------------------------------------ tick

    @Override
    public void tick() {
        super.tick();
        if (this.stationTicksLeft > 0) {
            this.stationTicksLeft--;
        }
        if (this.actionTicks > 0) {
            this.actionTicks--;
            if (this.actionTicks == 0 && this.getAction() != ACTION_NONE) {
                this.entityData.set(DATA_ACTION, ACTION_NONE);
            }
        }
    }

    // ------------------------------------------------------------ 全无敌 / 不死

    @Override
    public void aiStep() {
        super.aiStep();
        if (this.level().isClientSide) {
            return;
        }
        this.guardImmortal();
        if (Config.CAT_GIRL_PICKUP.get()) {
            this.pickupNearby();
        }
        if (--this.maintenanceTicks > 0) {
            return;
        }
        this.maintenanceTicks = 20;
        if (Config.CAT_GIRL_NO_DURABILITY.get()) {
            this.keepGearPristine();
        }
        if (Config.CAT_GIRL_AUTO_EQUIP.get()) {
            this.ensureMainHand(this.getJob());
            this.ensureArmor();
        }
        if (this.level() instanceof ServerLevel server) {
            CatGirlCrafting.tick(this, server);
        }
    }

    // ------------------------------------------------------------ 拾取

    /** 不用原版那套（它要 mobGriefing 开着）：自己扫身边 1.5 格捡。 */
    private void pickupNearby() {
        if (--this.pickupTicks > 0) {
            return;
        }
        this.pickupTicks = 5;
        net.minecraft.world.phys.AABB box = this.getBoundingBox().inflate(1.5D, 0.5D, 1.5D);
        for (net.minecraft.world.entity.item.ItemEntity item :
                this.level().getEntitiesOfClass(net.minecraft.world.entity.item.ItemEntity.class, box)) {
            if (item.isRemoved() || item.hasPickUpDelay() || item.getItem().isEmpty()) {
                continue;
            }
            if (this.wantsToPickUp(item.getItem())) {
                this.pickUpItem(item);
            }
        }
    }

    @Override
    public boolean canPickUpLoot() {
        return false; // 走自己的扫描，不受 mobGriefing 影响
    }

    @Override
    public boolean wantsToPickUp(ItemStack stack) {
        if (stack.isEmpty()) {
            return false;
        }
        for (int i = 0; i < this.goods.getContainerSize(); i++) {
            ItemStack s = this.goods.getItem(i);
            if (s.isEmpty()) {
                return true;
            }
            if (ItemStack.isSameItemSameTags(s, stack) && s.getCount() < s.getMaxStackSize()) {
                return true;
            }
        }
        return false;
    }

    @Override
    protected void pickUpItem(net.minecraft.world.entity.item.ItemEntity entity) {
        ItemStack stack = entity.getItem();
        ItemStack leftover = this.goods.addItem(stack.copy());
        if (leftover.getCount() == stack.getCount()) {
            return; // 一点也塞不进去，别动它
        }
        this.goods.setChanged();
        this.take(entity, leftover.getCount());
        stack.setCount(leftover.getCount());
        if (stack.isEmpty()) {
            entity.discard();
        }
    }

    // ------------------------------------------------------------ 按工种换装

    /** 工具打分：先看材质等级（木/金 0 < 石 1 < 铁 2 < 钻 3 < 下界 4），再看耐久上限。 */
    private static int gearRank(ItemStack stack) {
        int tier = stack.getItem() instanceof net.minecraft.world.item.TieredItem tiered
                ? tiered.getTier().getLevel() : 0;
        return tier * 10000 + stack.getMaxDamage();
    }

    /** 从库存里取出一件指定物品（真取走）。 */
    private ItemStack takeFirst(net.minecraft.world.item.Item... items) {
        for (int i = 0; i < this.goods.getContainerSize(); i++) {
            ItemStack s = this.goods.getItem(i);
            if (s.isEmpty()) {
                continue;
            }
            for (net.minecraft.world.item.Item item : items) {
                if (s.is(item)) {
                    return this.goods.removeItem(i, 1);
                }
            }
        }
        return ItemStack.EMPTY;
    }

    /** 从库存里取出一把最合适的（真取走，不是复制）。 */
    private ItemStack takeBest(net.minecraft.tags.TagKey<net.minecraft.world.item.Item> tag) {
        int bestIdx = -1;
        int best = -1;
        for (int i = 0; i < this.goods.getContainerSize(); i++) {
            ItemStack s = this.goods.getItem(i);
            if (s.isEmpty() || !s.is(tag)) {
                continue;
            }
            int rank = gearRank(s);
            if (rank > best) {
                best = rank;
                bestIdx = i;
            }
        }
        return bestIdx < 0 ? ItemStack.EMPTY : this.goods.removeItem(bestIdx, 1);
    }

    private void ensureMainHand(Job job) {
        ItemStack held = this.getMainHandItem();
        ItemStack want;
        switch (job) {
            case LUMBER -> {
                if (held.is(net.minecraft.tags.ItemTags.AXES)) {
                    return; // 手上就是斧子（比如玩家刚给她的），别动
                }
                want = this.takeBest(net.minecraft.tags.ItemTags.AXES);
            }
            case MINE -> {
                if (held.is(net.minecraft.tags.ItemTags.PICKAXES)) {
                    return;
                }
                want = this.takeBest(net.minecraft.tags.ItemTags.PICKAXES);
            }
            case FIGHT -> {
                if (held.is(net.minecraft.tags.ItemTags.SWORDS)) {
                    return;
                }
                want = this.takeBest(net.minecraft.tags.ItemTags.SWORDS);
                if (want.isEmpty()) {
                    if ((held.is(Items.BOW) || held.is(Items.CROSSBOW)) && this.countArrows() > 0) {
                        return; // 没剑但有弓且有箭，就这么打
                    }
                    if (want.isEmpty()) {
                        want = this.takeFirst(Items.BOW, Items.CROSSBOW);
                    }
                }
            }
            default -> want = ItemStack.EMPTY; // 跟随 / 没事干：收起工具
        }
        if (ItemStack.isSameItemSameTags(held, want)) {
            return;
        }
        if (!held.isEmpty()) {
            this.goods.addItem(held.copy()); // 换下来的收回库存，不丢
        }
        this.setItemSlot(net.minecraft.world.entity.EquipmentSlot.MAINHAND, ItemStack.EMPTY);
        if (!want.isEmpty()) {
            this.setItemSlot(net.minecraft.world.entity.EquipmentSlot.MAINHAND, want);
        }
    }

    private static int armorValue(ItemStack stack) {
        return stack.getItem() instanceof net.minecraft.world.item.ArmorItem armor ? armor.getDefense() : -1;
    }

    /** 库存里有更好的盔甲就换上（换下来的回库存）。 */
    private void ensureArmor() {
        for (net.minecraft.world.entity.EquipmentSlot slot : ARMOR_SLOTS) {
            ItemStack worn = this.getItemBySlot(slot);
            int bestIdx = -1;
            int best = armorValue(worn);
            for (int i = 0; i < this.goods.getContainerSize(); i++) {
                ItemStack s = this.goods.getItem(i);
                if (s.isEmpty() || !(s.getItem() instanceof net.minecraft.world.item.ArmorItem armor)) {
                    continue;
                }
                if (armor.getEquipmentSlot() != slot) {
                    continue;
                }
                if (armorValue(s) > best) {
                    best = armorValue(s);
                    bestIdx = i;
                }
            }
            if (bestIdx < 0) {
                continue;
            }
            ItemStack take = this.goods.removeItem(bestIdx, 1);
            if (!worn.isEmpty()) {
                this.goods.addItem(worn.copy());
            }
            this.setItemSlot(slot, take);
        }
    }

    /** 她的装备不吃耐久：主手、盔甲、库存里的可损物品一律修满。 */
    private void keepGearPristine() {
        ItemStack held = this.getMainHandItem();
        if (held.isDamageableItem() && held.getDamageValue() > 0) {
            held.setDamageValue(0);
        }
        for (net.minecraft.world.entity.EquipmentSlot slot : ARMOR_SLOTS) {
            ItemStack s = this.getItemBySlot(slot);
            if (s.isDamageableItem() && s.getDamageValue() > 0) {
                s.setDamageValue(0);
            }
        }
        for (int i = 0; i < this.goods.getContainerSize(); i++) {
            ItemStack s = this.goods.getItem(i);
            if (s.isDamageableItem() && s.getDamageValue() > 0) {
                s.setDamageValue(0);
            }
        }
    }

    /** 全无敌时不许死：/kill、虚空都不行。 */
    @Override
    public void kill() {
        if (!Config.CAT_GIRL_INVULNERABLE.get()) {
            super.kill();
        }
    }

    /**
     * 全无敌兜底：血线永远满格；掉出世界（虚空）就拉回主人身边。
     *
     * <p>虚空伤害（{@code OUT_OF_WORLD}）在原版里绕开无敌判定，所以要单独兜一次 ——
     * 不然「全无敌」会被一条 void 打脸。同理 {@code /kill} 也不看无敌，见 {@link #kill()}。</p>
     */
    private void guardImmortal() {
        if (this.level().isClientSide || !Config.CAT_GIRL_INVULNERABLE.get()) {
            return;
        }
        if (this.getHealth() < this.getMaxHealth()) {
            this.setHealth(this.getMaxHealth());
        }
        if (this.getY() < this.level().getMinBuildHeight() - 8.0D) {
            LivingEntity owner = this.getOwner();
            if (owner != null) {
                this.teleportTo(owner.getX(), owner.getY() + 1.0D, owner.getZ());
            } else {
                this.teleportTo(this.getX(), this.level().getMinBuildHeight() + 80.0D, this.getZ());
            }
            this.fallDistance = 0.0F;
        }
    }

    // ------------------------------------------------------------ 无敌（敌对生物无效）

    @Override
    public boolean isInvulnerableTo(DamageSource source) {
        // 全无敌（config，默认开）：敌对生物、玩家、爆炸、火、虚空……一律免
        if (Config.CAT_GIRL_INVULNERABLE.get()) {
            return true;
        }
        // 直接凶手是敌对生物（近战、僵尸的枪、骷髅的箭、苦力怕爆炸都走这条）
        if (source.getEntity() instanceof LivingEntity attacker && AllyJudge.isHorde(attacker)) {
            return true;
        }
        // 无主的投射物也算：僵尸射出的箭在命中瞬间 getEntity 可能是箭本身
        if (source.getDirectEntity() instanceof LivingEntity direct && AllyJudge.isHorde(direct)) {
            return true;
        }
        // 敌对生物造成的爆炸 / 火焰等环境型来源：凶手是怪就免掉
        if (source.is(DamageTypeTags.IS_EXPLOSION) && source.getEntity() == null && source.getDirectEntity() == null) {
            return super.isInvulnerableTo(source);
        }
        return super.isInvulnerableTo(source);
    }

    @Override
    public boolean hurt(DamageSource source, float amount) {
        // 全无敌：连伤害事件都不产生（不会红屏、不会被击退、不会掉血）
        if (Config.CAT_GIRL_INVULNERABLE.get()) {
            return false;
        }
        boolean hurt = super.hurt(source, amount);
        if (hurt && !this.level().isClientSide) {
            // 只有玩家/环境真的造成伤害时才会走到这（敌对生物在上一步就被挡了）
            this.setAction(ACTION_HURT, 7);
        }
        return hurt;
    }

    /** 宠物定位：不产经验、不掉装备（手里的东西自己还，见 {@link #dropCustomDeathLoot}）。 */
    @Override
    public boolean shouldDropExperience() {
        return false;
    }

    @Override
    protected void dropCustomDeathLoot(DamageSource source, int looting, boolean recentlyHit) {
        super.dropCustomDeathLoot(source, looting, recentlyHit);
        for (int i = 0; i < this.goods.getContainerSize(); i++) {
            ItemStack stack = this.goods.getItem(i);
            if (!stack.isEmpty()) {
                this.spawnAtLocation(stack);
            }
        }
        this.goods.clearContent();
    }

    @Override
    public float getEquipmentDropChance(EquipmentSlot slot) {
        return 1.0F;
    }

    @Override
    public boolean removeWhenFarAway(double distanceToClosestPlayer) {
        return false;
    }

    @Override
    public boolean canAttack(LivingEntity target) {
        if (target instanceof Player || target instanceof CatGirlEntity) {
            return false;
        }
        return super.canAttack(target);
    }

    @Override
    public boolean doHurtTarget(net.minecraft.world.entity.Entity target) {
        this.setAction(ACTION_ATTACK, 9);
        return super.doHurtTarget(target);
    }

    // ------------------------------------------------------------ 交互

    @Override
    public InteractionResult mobInteract(Player player, InteractionHand hand) {
        ItemStack stack = player.getItemInHand(hand);
        if (this.level().isClientSide) {
            return InteractionResult.SUCCESS;
        }

        // ---- 潜行右键：打开她自己的界面。刻意放在所有分支最前面 ----
        // 「蹲下点击」是玩家明确下达的指令，不该被「手里正好拿着把斧子」（交工具）或
        // 「正好拿着鱼」（喂食）吃掉；而且 shift 状态是每 tick 同步的，服务端有一两 tick 滞后，
        // 分支越靠前越不容易被抢 —— 这是「蹲下点击没反应 / 反而切了工种」的根因。
        if (player.isShiftKeyDown()) {
            if (!this.isTame()) {
                player.displayClientMessage(Component.translatable("cat_girl.not_tame"), true);
                return InteractionResult.CONSUME;
            }
            if (!this.isOwnedBy(player)) {
                player.displayClientMessage(Component.translatable("cat_girl.not_owner"), true);
                return InteractionResult.CONSUME;
            }
            if (player instanceof ServerPlayer serverPlayer) {
                // 1.20.1 的 ServerPlayer 只有 openMenu(MenuProvider)，没有带额外数据的 2 参重载；
                // 要把 entityId 同步给客户端菜单，得走 Forge 的 NetworkHooks.openScreen。
                net.minecraftforge.network.NetworkHooks.openScreen(serverPlayer,
                        new SimpleMenuProvider(
                                (id, inv, p) -> new CatGirlTradeMenu(id, inv, this.getId()),
                                this.getDisplayName()),
                        buf -> buf.writeVarInt(this.getId()));
            }
            return InteractionResult.CONSUME;
        }

        // ---- 未驯服：喂鱼即认主；拿别的东西点她也给一句话，不再静默无反应 ----
        if (!this.isTame()) {
            if (stack.is(ItemTags.FISHES)) {
                if (!player.getAbilities().instabuild) {
                    stack.shrink(1);
                }
                this.tame(player);
                this.navigation.stop();
                this.setTarget(null);
                this.level().broadcastEntityEvent(this, (byte) 7); // 爱心粒子
                this.playSound(SoundEvents.CAT_EAT, 1.0F, 1.0F);
                return InteractionResult.CONSUME;
            }
            player.displayClientMessage(Component.translatable("cat_girl.not_tame"), true);
            return InteractionResult.CONSUME;
        }

        // ---- 已驯服：只认主人（别人点她也要说明白）----
        if (!this.isOwnedBy(player)) {
            player.displayClientMessage(Component.translatable("cat_girl.not_owner"), true);
            return InteractionResult.CONSUME;
        }

        // 手里拿鱼：加餐回血（顺手当个治疗手段）
        if (stack.is(ItemTags.FISHES) && this.getHealth() < this.getMaxHealth()) {
            if (!player.getAbilities().instabuild) {
                stack.shrink(1);
            }
            this.heal(6.0F);
            this.playSound(SoundEvents.CAT_EAT, 1.0F, 1.0F);
            this.level().broadcastEntityEvent(this, (byte) 7);
            return InteractionResult.CONSUME;
        }

        // 箭：她放箭要用，直接进她自己的库存（砍伐/挖矿的产出也存这里）
        if (stack.is(Items.ARROW) || stack.is(Items.SPECTRAL_ARROW) || stack.is(Items.TIPPED_ARROW)) {
            ItemStack leftover = this.goods.addItem(stack.copy());
            int moved = stack.getCount() - leftover.getCount();
            if (moved > 0) {
                stack.shrink(moved);
                player.displayClientMessage(Component.translatable("cat_girl.gave_arrows",
                        Component.translatable("cat_girl.arrows"), moved), true);
                this.playSound(SoundEvents.ITEM_PICKUP, 0.6F, 1.4F);
            }
            if (!leftover.isEmpty()) {
                player.drop(leftover, false); // 她装不下的掉在脚边
            }
            return InteractionResult.CONSUME;
        }

        // 手里拿工具 / 武器：交给她。**工具即指令** —— 交什么工具就干什么活。
        if (isToolOrWeapon(stack) || stack.is(Items.BOW) || stack.is(Items.CROSSBOW)) {
            ItemStack old = this.getMainHandItem().copy();
            this.setItemSlot(EquipmentSlot.MAINHAND, stack.split(1));
            if (!old.isEmpty()) {
                // 换下来的还回玩家背包（背包满了就掉在脚边）
                if (!player.getInventory().add(old)) {
                    player.drop(old, false);
                }
            }
            this.setAction(ACTION_EQUIP, 12);
            this.playSound(SoundEvents.ARMOR_EQUIP_LEATHER, 0.8F, 1.4F);

            Job toolJob = jobForTool(this.getMainHandItem());
            if (toolJob != null && toolJob != this.getJob()) {
                this.applyPlayerJob(toolJob);
                player.displayClientMessage(Component.translatable("cat_girl.job.from_tool",
                        this.getDisplayName(),
                        this.getMainHandItem().getHoverName(),
                        Component.translatable(toolJob.langKey())), false);
            }
            // 弓：先看她箭袋里有没有箭，没有就提醒一句（不然给了弓她只能贴脸抡）
            if (this.getMainHandItem().is(Items.BOW) || this.getMainHandItem().is(Items.CROSSBOW)) {
                if (countArrows() == 0) {
                    player.displayClientMessage(Component.translatable("cat_girl.bow.need_arrows"), false);
                }
            }
            return InteractionResult.CONSUME;
        }

        if (stack.isEmpty()) {
            // 空手右键：循环切换任务模式
            Job next = this.getJob().next();
            this.applyPlayerJob(next);
            player.displayClientMessage(Component.translatable("cat_girl.job.switched",
                    this.getDisplayName(),
                    Component.translatable(next.langKey())), true);
            this.playSound(SoundEvents.CAT_PURR, 0.8F, 1.2F);
            return InteractionResult.CONSUME;
        }

        return InteractionResult.PASS;
    }

    /**
     * 工具即指令：给她什么工具，她就干什么活。
     *
     * <p>斧子 → 伐木、镐子 → 挖矿、剑/弓/弩 → 打怪。其它工具（锹/锄）与自定义武器只换装不换工种，
     * 返回 {@code null} 表示「保持她现在的活」。
     *
     * <p>判断走原版物品标签，所以模组里带相应标签的斧/镐同样认；剑/弓则按物品本身认。
     */
    public static Job jobForTool(ItemStack stack) {
        if (stack.isEmpty()) {
            return null;
        }
        if (stack.is(ItemTags.AXES)) {
            return Job.LUMBER;
        }
        if (stack.is(ItemTags.PICKAXES)) {
            return Job.MINE;
        }
        if (stack.is(ItemTags.SWORDS) || stack.is(Items.BOW) || stack.is(Items.CROSSBOW)) {
            return Job.FIGHT;
        }
        return null;
    }

    /** 她库存里有多少支箭（放箭与「箭袋空了」提示都用它）。 */
    public int countArrows() {
        int n = 0;
        for (int i = 0; i < this.goods.getContainerSize(); i++) {
            ItemStack s = this.goods.getItem(i);
            if (s.is(Items.ARROW) || s.is(Items.SPECTRAL_ARROW) || s.is(Items.TIPPED_ARROW)) {
                n += s.getCount();
            }
        }
        return n;
    }

    /** 工具或武器：原版四大工具 + 剑的标签，外加「带攻击伤害属性」的自定义物品（模组武器）。 */
    public static boolean isToolOrWeapon(ItemStack stack) {
        if (stack.isEmpty()) {
            return false;
        }
        if (stack.is(ItemTags.SWORDS) || stack.is(ItemTags.AXES) || stack.is(ItemTags.PICKAXES)
                || stack.is(ItemTags.SHOVELS) || stack.is(ItemTags.HOES)) {
            return true;
        }
        return stack.getAttributeModifiers(EquipmentSlot.MAINHAND).containsKey(Attributes.ATTACK_DAMAGE);
    }

    // ------------------------------------------------------------ 其它原版钩子

    /** 不产仔：宠物定位，繁殖这条线整个关掉。 */
    @Override
    public AgeableMob getBreedOffspring(ServerLevel level, AgeableMob otherParent) {
        return null;
    }

    @Override
    public boolean isFood(ItemStack stack) {
        return false;
    }

    @Override
    public boolean canFallInLove() {
        return false;
    }

    /** 她不需要床/睡，也不要中午变怪这类东西 —— TamableAnimal 默认已足够，这里只保留声音。 */
    @Override
    protected SoundEvent getAmbientSound() {
        return SoundEvents.CAT_PURR;
    }

    @Override
    protected SoundEvent getHurtSound(DamageSource source) {
        return SoundEvents.CAT_HURT;
    }

    @Override
    protected SoundEvent getDeathSound() {
        return SoundEvents.CAT_DEATH;
    }

    // ------------------------------------------------------------ GeckoLib 控制器

    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache() {
        return this.geoCache;
    }

    @Override
    public void registerControllers(AnimatableManager.ControllerRegistrar controllers) {
        controllers.add(new AnimationController<>(this, "movement", 4, CatGirlEntity::movementAnimation));
        controllers.add(new AnimationController<>(this, "action", 0, CatGirlEntity::actionAnimation));
    }

    /** 静置 / 行走；手里有东西就换成持物姿态。动作播放期间让位（返回 STOP）。 */
    private static PlayState movementAnimation(AnimationState<CatGirlEntity> state) {
        CatGirlEntity cat = state.getAnimatable();
        if (cat.getAction() != ACTION_NONE || !cat.isAlive()) {
            return PlayState.STOP;
        }
        state.setControllerSpeed(Mth.clamp(0.6F + 0.9F * state.getLimbSwingAmount(), 0.5F, 2.0F));
        boolean hold = cat.isHoldingAnything();
        if (state.isMoving()) {
            return state.setAndContinue(RawAnimation.begin().thenLoop(hold ? ANIM_WALK_HOLD : ANIM_WALK));
        }
        return state.setAndContinue(RawAnimation.begin().thenLoop(hold ? ANIM_IDLE_HOLD : ANIM_IDLE));
    }

    /** 动作通道：拿取 / 攻击 / 伐木 / 挖矿 / 受击 / 死亡。 */
    private static PlayState actionAnimation(AnimationState<CatGirlEntity> state) {
        CatGirlEntity cat = state.getAnimatable();
        if (!cat.isAlive()) {
            return state.setAndContinue(RawAnimation.begin().thenPlay(ANIM_DEATH));
        }
        return switch (cat.getAction()) {
            case ACTION_EQUIP -> state.setAndContinue(RawAnimation.begin().thenPlay(ANIM_EQUIP));
            case ACTION_ATTACK -> state.setAndContinue(RawAnimation.begin().thenPlay(ANIM_ATTACK));
            case ACTION_CHOP -> state.setAndContinue(RawAnimation.begin().thenLoop(ANIM_CHOP));
            case ACTION_MINE -> state.setAndContinue(RawAnimation.begin().thenLoop(ANIM_MINE));
            case ACTION_HURT -> state.setAndContinue(RawAnimation.begin().thenPlay(ANIM_HURT));
            default -> PlayState.STOP;
        };
    }

    // ------------------------------------------------------------ 交易工具

    /** 玩家给她一个爱心币价格：按价值表折算物品的售价。 */
    public static int coinValue(ItemStack stack) {
        if (stack.isEmpty()) {
            return 0;
        }
        String id = net.minecraft.core.registries.BuiltInRegistries.ITEM.getKey(stack.getItem()).toString();
        for (String entry : Config.CAT_GIRL_TRADE_VALUES.get()) {
            int eq = entry.indexOf('=');
            if (eq <= 0) {
                continue;
            }
            if (entry.substring(0, eq).trim().equals(id)) {
                try {
                    return Math.max(0, Integer.parseInt(entry.substring(eq + 1).trim()));
                } catch (NumberFormatException ignored) {
                    return Config.CAT_GIRL_TRADE_DEFAULT.get();
                }
            }
        }
        if (isToolOrWeapon(stack)) {
            return Config.CAT_GIRL_TRADE_TOOL_VALUE.get();
        }
        return Config.CAT_GIRL_TRADE_DEFAULT.get();
    }

    /** 工资产出：优先塞进她的库存，塞不下才掉在地上。 */
    public void storeOrDrop(List<ItemStack> stacks, BlockPos where) {
        for (ItemStack stack : stacks) {
            if (stack.isEmpty()) {
                continue;
            }
            ItemStack leftover = this.goods.addItem(stack);
            if (!leftover.isEmpty()) {
                net.minecraft.world.level.block.Block.popResource(this.level(), where, leftover);
            }
        }
    }

    /**
     * 「砸开挡路的」通用实现：和伐木/挖矿同一套掉落规则（含全功能工具 / always_drops），
     * 破坏后收进她的库存 —— 开路行为不能把「她砸什么都有产物」这条绕过去。
     *
     * @param axeLike 老参数：现在掉落统一由 {@link CatGirlHarvest#breakAndCollect} 按方块
     *                该用的工具决定，这个标志已经不参与判断，只为不动调用方而留着。
     */
    public void harvestBlockHard(BlockPos pos, boolean axeLike) {
        CatGirlHarvest.breakAndCollect(this, pos, state -> true);
    }

    /** 交易菜单用的催肥粒子（钱不够时的反馈）。 */
    public void angryParticles() {
        if (this.level() instanceof ServerLevel server) {
            server.sendParticles(ParticleTypes.ANGRY_VILLAGER,
                    this.getX(), this.getEyeY() + 0.4D, this.getZ(), 3, 0.2D, 0.2D, 0.2D, 0.0D);
        }
    }
}
