package com.apocalypse.zombies.entity;

import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.DifficultyInstance;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraft.world.level.Level;

/**
 * 三只僵尸系特殊生物的公共骨架：同步施法状态，把推进交给 {@link EliteAbilityDriver}。
 *
 * <p>子类只回答三件事：技能是什么、什么时候能起手、命中那一 tick 干什么。</p>
 */
public abstract class AbstractEliteZombie extends Zombie implements EliteMob {

    private static final EntityDataAccessor<Byte> DATA_ABILITY =
            SynchedEntityData.defineId(AbstractEliteZombie.class, EntityDataSerializers.BYTE);
    private static final EntityDataAccessor<Integer> DATA_ABILITY_TICK =
            SynchedEntityData.defineId(AbstractEliteZombie.class, EntityDataSerializers.INT);

    /** 首次 tick 时才建：驱动器要读子类重写的方法，构造期拿不到。 */
    private EliteAbilityDriver driver;

    protected AbstractEliteZombie(EntityType<? extends Zombie> type, Level level) {
        super(type, level);
        this.xpReward = 15;
    }

    // ------------------------------------------------------------------ 子类契约

    /** 本生物的技能。 */
    protected abstract EliteAbility ability();

    /** 两次施法之间的冷却（tick）。 */
    protected abstract int abilityCooldownTicks();

    /** 现在能起手吗？距离、目标、视线之类的判断都写在这里。 */
    protected abstract boolean canStartAbility();

    /** 命中那一 tick 的效果。 */
    protected abstract void onAbilityImpact();

    /** 起手瞬间（设朝向、吼一声）。默认什么都不做。 */
    protected void onAbilityStart() {
    }

    /** 收招结束（进入冷却）。默认什么都不做。 */
    protected void onAbilityEnd() {
    }

    // ------------------------------------------------------------------ 同步状态

    @Override
    protected void defineSynchedData() {
        super.defineSynchedData();
        this.getEntityData().define(DATA_ABILITY, (byte) EliteAbility.NONE.ordinal());
        this.getEntityData().define(DATA_ABILITY_TICK, -1);
    }

    @Override
    public EliteAbility getAbility() {
        return EliteAbility.byId(this.getEntityData().get(DATA_ABILITY));
    }

    @Override
    public int getAbilityTick() {
        return this.getEntityData().get(DATA_ABILITY_TICK);
    }

    @Override
    public void setAbility(EliteAbility ability, int tick) {
        this.getEntityData().set(DATA_ABILITY, (byte) ability.ordinal());
        this.getEntityData().set(DATA_ABILITY_TICK, tick);
    }

    // ------------------------------------------------------------------ 技能推进

    private EliteAbilityDriver driver() {
        if (this.driver == null) {
            this.driver = new EliteAbilityDriver(this, this, new ZombieHooks());
        }
        return this.driver;
    }

    @Override
    protected void customServerAiStep() {
        super.customServerAiStep();
        if (this.level() instanceof ServerLevel) {
            this.driver().tick();
        }
    }

    /** 把子类的 protected 契约接到驱动器上。 */
    private final class ZombieHooks implements EliteAbilityDriver.Hooks {

        @Override
        public EliteAbility ability() {
            return AbstractEliteZombie.this.ability();
        }

        @Override
        public int cooldownTicks() {
            return AbstractEliteZombie.this.abilityCooldownTicks();
        }

        @Override
        public boolean canStart() {
            return AbstractEliteZombie.this.canStartAbility();
        }

        @Override
        public void onStart() {
            AbstractEliteZombie.this.onAbilityStart();
        }

        @Override
        public void onImpact() {
            AbstractEliteZombie.this.onAbilityImpact();
        }

        @Override
        public void onEnd() {
            AbstractEliteZombie.this.onAbilityEnd();
        }
    }

    /** 供子类复用：目标在范围内、且能看见。 */
    protected boolean hasTargetInRange(double min, double max) {
        return EliteMob.hasTargetInRange(this, min, max);
    }

    // ------------------------------------------------------------------ 精英的通用性质

    /** 精英不会在水里变溺尸——否则打着打着人没了。 */
    @Override
    protected boolean convertsInWater() {
        return false;
    }

    /** 精英无视阳光。它们在血月里出现，不该因为天亮就自己烧死。 */
    @Override
    protected boolean isSunSensitive() {
        return false;
    }

    /** 不刷幼年体：尺寸和速度修饰符会跟技能动画打架。 */
    @Override
    public boolean isBaby() {
        return false;
    }

    @Override
    public void setBaby(boolean baby) {
        // 精英恒为成年体
    }

    /** 关掉「被打就喊援军」。增援由尖啸者自己的技能负责，不靠原版那套随机概率。 */
    @Override
    protected void randomizeReinforcementsChance() {
        if (this.getAttribute(Attributes.SPAWN_REINFORCEMENTS_CHANCE) != null) {
            this.getAttribute(Attributes.SPAWN_REINFORCEMENTS_CHANCE).setBaseValue(0.0D);
        }
    }

    /**
     * 不掷随机武器。原版僵尸有 1%（困难 5%）的概率拎一把铁剑或铁锹出场，而精英的武器是模型自己长出来的，
     * 手里再插一把铁剑只会跟着挥砍动画一起乱晃。精英一旦最终确定走 {@code finalizeSpawn} 出场，
     * 这道口子就必须堵上。
     */
    @Override
    protected void populateDefaultEquipmentSlots(RandomSource random, DifficultyInstance difficulty) {
        // 精英的装备全是手工定的，不给随机数插手的机会
    }

    @Override
    public boolean removeWhenFarAway(double distance) {
        return false;
    }

    /** 供子类复用：僵尸那套属性池（含 SPAWN_REINFORCEMENTS_CHANCE 等），再往上加精英数值。 */
    public static AttributeSupplier.Builder eliteAttributes() {
        return Zombie.createAttributes();
    }
}
