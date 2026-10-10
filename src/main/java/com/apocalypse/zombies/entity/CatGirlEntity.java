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
import net.minecraft.world.level.Level;
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

    /** 她自己的库存：伐木 / 挖矿的产物，也是交易菜单里可购买的那九格。 */
    public static final int GOODS_SIZE = 9;

    private static final EntityDataAccessor<Integer> DATA_JOB =
            SynchedEntityData.defineId(CatGirlEntity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_ACTION =
            SynchedEntityData.defineId(CatGirlEntity.class, EntityDataSerializers.INT);

    private final AnimatableInstanceCache geoCache = GeckoLibUtil.createInstanceCache(this);

    private final SimpleContainer goods = new SimpleContainer(GOODS_SIZE);

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
        // 走路优先级放在劳作之上：主人走出去十格，她会先跟上再继续干活
        this.goalSelector.addGoal(1, new FollowOwnerGoal(this, 1.15D, 10.0F, 2.5F, false));
        this.goalSelector.addGoal(2, new MeleeAttackGoal(this, 1.2D, true));
        this.goalSelector.addGoal(3, new WorkBlockGoal(this, Job.LUMBER, CatGirlEntity::isLog, ACTION_CHOP));
        this.goalSelector.addGoal(4, new WorkBlockGoal(this, Job.MINE, CatGirlEntity::isOre, ACTION_MINE));
        this.goalSelector.addGoal(5, new WaterAvoidingRandomStrollGoal(this, 1.0D));
        this.goalSelector.addGoal(6, new LookAtPlayerGoal(this, Player.class, 8.0F));
        this.goalSelector.addGoal(7, new RandomLookAroundGoal(this));

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

    private static boolean isLog(BlockState state) {
        return state.is(BlockTags.LOGS);
    }

    private static boolean isOre(BlockState state) {
        return state.is(Tags.Blocks.ORES);
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
    }

    // ------------------------------------------------------------ tick

    @Override
    public void tick() {
        super.tick();
        if (this.actionTicks > 0) {
            this.actionTicks--;
            if (this.actionTicks == 0 && this.getAction() != ACTION_NONE) {
                this.entityData.set(DATA_ACTION, ACTION_NONE);
            }
        }
    }

    // ------------------------------------------------------------ 无敌（敌对生物无效）

    @Override
    public boolean isInvulnerableTo(DamageSource source) {
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

        // 手里拿工具 / 武器：交给她
        if (isToolOrWeapon(stack)) {
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
            return InteractionResult.CONSUME;
        }

        if (stack.isEmpty()) {
            // 空手右键：循环切换任务模式
            Job next = this.getJob().next();
            this.setJob(next);
            player.displayClientMessage(Component.translatable("cat_girl.job.switched",
                    this.getDisplayName(),
                    Component.translatable(next.langKey())), true);
            this.playSound(SoundEvents.CAT_PURR, 0.8F, 1.2F);
            return InteractionResult.CONSUME;
        }

        return InteractionResult.PASS;
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

    /** 交易菜单用的催肥粒子（钱不够时的反馈）。 */
    public void angryParticles() {
        if (this.level() instanceof ServerLevel server) {
            server.sendParticles(ParticleTypes.ANGRY_VILLAGER,
                    this.getX(), this.getEyeY() + 0.4D, this.getZ(), 3, 0.2D, 0.2D, 0.2D, 0.0D);
        }
    }
}
