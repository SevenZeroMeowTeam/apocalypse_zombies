# -*- coding: utf-8 -*-
"""1.1.71：全无敌不死 + 弓弩完整蓄力 + 玩家背包回到面板内（原版 9 列布局）。"""
from pathlib import Path

J = 'src/main/java/com/apocalypse/zombies/'

# ============================================================ ① Config：全无敌开关
p = Path(J + 'Config.java')
s = p.read_text(encoding='utf-8')
old = '    public static final ForgeConfigSpec.IntValue CAT_GIRL_WORK_RADIUS;'
assert old in s, 'Config 字段锚点'
s = s.replace(old, '    /** 全无敌：任何来源都不掉血、也不会死（敌对生物、玩家、爆炸、虚空都免）。 */\n'
                   '    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_INVULNERABLE;\n' + old, 1)
old = '''        CAT_GIRL_WORK_RADIUS = b.comment("伐木 / 挖矿时以她为中心的搜索半径（格）。")'''
assert old in s, 'Config 定义锚点'
s = s.replace(old, '''        CAT_GIRL_INVULNERABLE = b.comment("全无敌：任何来源都不掉血、也不会死（连 /kill 也伤不到她）。")
                .define("invulnerable", true);
''' + old, 1)
p.write_text(s, encoding='utf-8')
print('(1) Config：+ CAT_GIRL_INVULNERABLE（默认 true）')

# ============================================================ ② 实体：全无敌 / 不死
p = Path(J + 'entity/CatGirlEntity.java')
s = p.read_text(encoding='utf-8')

if 'import com.apocalypse.zombies.Config;' not in s:
    s = s.replace('import com.apocalypse.zombies.', 'import com.apocalypse.zombies.Config;\nimport com.apocalypse.zombies.', 1) \
        if 'import com.apocalypse.zombies.' in s else 'import com.apocalypse.zombies.Config;\n' + s
    print('    （补 import Config）')

old = '''    @Override
    public boolean isInvulnerableTo(DamageSource source) {
        // 直接凶手是敌对生物（近战、僵尸的枪、骷髅的箭、苦力怕爆炸都走这条）'''
assert old in s, 'isInvulnerableTo 锚点'
s = s.replace(old, '''    @Override
    public boolean isInvulnerableTo(DamageSource source) {
        // 全无敌（config，默认开）：敌对生物、玩家、爆炸、火、虚空……一律免
        if (Config.CAT_GIRL_INVULNERABLE.get()) {
            return true;
        }
        // 直接凶手是敌对生物（近战、僵尸的枪、骷髅的箭、苦力怕爆炸都走这条）''', 1)

old = '''    @Override
    public boolean hurt(DamageSource source, float amount) {
        boolean hurt = super.hurt(source, amount);'''
assert old in s, 'hurt 锚点'
s = s.replace(old, '''    @Override
    public boolean hurt(DamageSource source, float amount) {
        // 全无敌：连伤害事件都不产生（不会红屏、不会被击退、不会掉血）
        if (Config.CAT_GIRL_INVULNERABLE.get()) {
            return false;
        }
        boolean hurt = super.hurt(source, amount);''', 1)

old = '    // ------------------------------------------------------------ 无敌（敌对生物无效）'
assert old in s, '无敌段注释锚点'
s = s.replace(old, '''    // ------------------------------------------------------------ 全无敌 / 不死

    @Override
    public void aiStep() {
        super.aiStep();
        this.guardImmortal();
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

''' + old, 1)
p.write_text(s, encoding='utf-8')
print('(2) CatGirlEntity：全无敌（hurt/isInvulnerableTo/kill/aiStep 兜底）')

# ============================================================ ③ 弓弩完整蓄力
Path(J + 'entity/ai/CatGirlBowGoal.java').write_text('''package com.apocalypse.zombies.entity.ai;

import com.apocalypse.zombies.entity.CatGirlEntity;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.entity.projectile.Arrow;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;

import java.util.EnumSet;

/**
 * 「给她一张弓，她就远程打怪」—— **完整蓄力**版。
 *
 * <p>弓：拉满 20 tick（原版弓的满弦时间）才放，箭速按满蓄力 3.0 出手；
 * 弩：装填 25 tick（原版弩的装填时间）才放，箭速 3.15。放完歇 6 tick 再来一轮。
 * 也就是说她的节奏和玩家拉弓/装弩一致，不是「无脑连发」。</p>
 *
 * <p>成立条件：工种是打怪、主手拿着弓/弩、目标活着、有视线、距离 &gt; 3 格，
 * 并且**她自己的库存里有箭**（{@code goods}；玩家把箭交给她即入袋）。缺任一条件就轮不到它，
 * 贴脸与没箭时自动退回同层的近战目标。</p>
 */
public class CatGirlBowGoal extends Goal {

    /** 弓：满弦时间（tick），与原版一致。 */
    private static final int BOW_DRAW = 20;
    /** 弩：装填时间（tick），与原版一致。 */
    private static final int CROSSBOW_LOAD = 25;
    /** 放完这一轮后歇几 tick 再开始下一轮。 */
    private static final int RELOAD_GAP = 6;

    /** 满蓄力箭速（原版弓满弦是 3.0，弩是 3.15）。 */
    private static final float BOW_SPEED = 3.0F;
    private static final float CROSSBOW_SPEED = 3.15F;

    private final CatGirlEntity cat;
    /** 本轮蓄力剩余 tick；<=0 表示该出手了。 */
    private int charge;
    private boolean crossbow;

    public CatGirlBowGoal(CatGirlEntity cat) {
        this.cat = cat;
        this.setFlags(EnumSet.of(Goal.Flag.MOVE, Goal.Flag.LOOK));
    }

    private boolean isCrossbow() {
        return this.cat.getMainHandItem().is(Items.CROSSBOW);
    }

    private boolean holdingRanged() {
        ItemStack held = this.cat.getMainHandItem();
        return held.is(Items.BOW) || held.is(Items.CROSSBOW);
    }

    /** 蓄力时长：弩 25 tick，弓 20 tick。 */
    private int drawTime() {
        return this.crossbow ? CROSSBOW_LOAD : BOW_DRAW;
    }

    private ItemStack findArrow() {
        for (int i = 0; i < this.cat.getGoods().getContainerSize(); i++) {
            ItemStack s = this.cat.getGoods().getItem(i);
            if (s.is(Items.ARROW) || s.is(Items.SPECTRAL_ARROW) || s.is(Items.TIPPED_ARROW)) {
                return s;
            }
        }
        return ItemStack.EMPTY;
    }

    @Override
    public boolean canUse() {
        LivingEntity target = this.cat.getTarget();
        if (this.cat.getJob() != CatGirlEntity.Job.FIGHT || !this.holdingRanged()) {
            return false;
        }
        if (target == null || !target.isAlive() || this.cat.distanceToSqr(target) <= 9.0D) {
            return false;
        }
        return !this.findArrow().isEmpty() && this.cat.getSensing().hasLineOfSight(target);
    }

    @Override
    public boolean canContinueToUse() {
        return this.canUse();
    }

    @Override
    public void start() {
        this.crossbow = this.isCrossbow();
        this.charge = this.drawTime();
        // 蓄力期间抬臂：用攻击动作占位，看起来就是在拉弓/端弩
        this.cat.setAction(CatGirlEntity.ACTION_ATTACK, this.charge);
    }

    @Override
    public void stop() {
        this.charge = 0;
    }

    @Override
    public boolean requiresUpdateEveryTick() {
        return true;
    }

    @Override
    public void tick() {
        LivingEntity target = this.cat.getTarget();
        if (target == null) {
            return;
        }
        this.cat.getLookControl().setLookAt(target, 30.0F, 30.0F);
        this.cat.getNavigation().stop(); // 站定蓄力，别边走边放

        if (this.charge > 0) {
            this.charge--;
            return;
        }
        this.fire(target);
        this.charge = RELOAD_GAP + this.drawTime();
        this.cat.setAction(CatGirlEntity.ACTION_ATTACK, this.drawTime());
    }

    /** 满蓄力出手：扣一支箭，按弓/弩各自的满蓄力箭速射出去。 */
    private void fire(LivingEntity target) {
        ItemStack arrow = this.findArrow();
        if (arrow.isEmpty() || !(this.cat.level() instanceof ServerLevel level)) {
            return;
        }
        arrow.shrink(1);
        this.cat.getGoods().setChanged();

        Arrow shot = new Arrow(level, this.cat);
        double dx = target.getX() - this.cat.getX();
        double dy = target.getEyeY() - this.cat.getEyeY();
        double dz = target.getZ() - this.cat.getZ();
        double flat = Math.sqrt(dx * dx + dz * dz);
        // 满蓄力：抬一点点补偿重力，散布按满弦收紧（弓 1.0 / 弩 0.6）
        float speed = this.crossbow ? CROSSBOW_SPEED : BOW_SPEED;
        float spread = this.crossbow ? 0.6F : 1.0F;
        shot.shoot(dx, dy + flat * 0.12D, dz, speed, spread);
        level.addFreshEntity(shot);

        this.cat.playSound(this.crossbow ? SoundEvents.CROSSBOW_SHOOT : SoundEvents.ARROW_SHOOT,
                1.0F, 1.0F / (this.cat.getRandom().nextFloat() * 0.4F + 0.8F));
    }
}
''', encoding='utf-8')
print('(3) CatGirlBowGoal：弓 20 tick 满弦 / 弩 25 tick 装填，满蓄力箭速')

# ============================================================ ④ 菜单：玩家背包回面板内（原版布局）
p = Path(J + 'entity/menu/CatGirlTradeMenu.java')
s = p.read_text(encoding='utf-8')
old = '''    public static final int PANEL_HEIGHT = 166;'''
assert old in s
s = s.replace(old, '''    public static final int PANEL_HEIGHT = 226;''', 1)

old = '''    /** 快捷栏那一行在面板里的 y。 */
    public static final int HOTBAR_Y = 146;

    /** 玩家 27 格的 y 原点：远在面板之下 = 存在但不可见（shift 搬运只走槽位索引）。 */
    public static final int HIDDEN_PLAYER_Y = 10000;'''
assert old in s, 'HOTBAR/HIDDEN 锚点'
s = s.replace(old, '''    /** 玩家背包第一行的 y：她的区块下面，按原版 9 列 × 18px 排（和玩家背包同款布局）。 */
    public static final int PLAYER_ROW_Y = 142;

    /** 快捷栏那一行在面板里的 y：最后一行背包下留 4px，与原版背包一致。 */
    public static final int HOTBAR_Y = 200;''', 1)

old = '''        for (int row = 0; row < 3; row++) {
            for (int col = 0; col < 9; col++) {
                this.addSlot(new Slot(playerInventory, col + row * 9 + 9, 8 + col * 18,
                        HIDDEN_PLAYER_Y + row * 18));
            }
        }'''
assert old in s, '玩家 27 格锚点'
s = s.replace(old, '''        for (int row = 0; row < 3; row++) {
            for (int col = 0; col < 9; col++) {
                this.addSlot(new Slot(playerInventory, col + row * 9 + 9, 8 + col * 18,
                        PLAYER_ROW_Y + row * 18));
            }
        }''', 1)
p.write_text(s, encoding='utf-8')
print('(4) CatGirlTradeMenu：玩家 27 格回面板内（142/160/178 + 快捷栏 200，面板 226）')

# ============================================================ ⑤ 屏幕：分隔线跟着走
p = Path(J + 'client/gui/CatGirlTradeScreen.java')
s = p.read_text(encoding='utf-8')
old = '        guiGraphics.fill(x + 5, y + 76, x + this.imageWidth - 5, y + 77, PANEL_BORDER);'
assert old in s, '分隔线锚点'
s = s.replace(old, old + '''
        // 她的区块与下面玩家背包之间再来一条：上半屏是「她的」，下半屏是玩家的
        guiGraphics.fill(x + 5, y + CatGirlTradeMenu.PLAYER_ROW_Y - 6,
                x + this.imageWidth - 5, y + CatGirlTradeMenu.PLAYER_ROW_Y - 5, PANEL_BORDER);''', 1)
p.write_text(s, encoding='utf-8')
print('(5) CatGirlTradeScreen：+ 玩家背包分隔线')

# ============================================================ ⑥ 版本 + readme
g = Path('gradle.properties'); t = g.read_text(encoding='utf-8')
assert 'mod_version=1.1.70' in t
g.write_text(t.replace('mod_version=1.1.70', 'mod_version=1.1.71'), encoding='utf-8')
print('(6) mod_version=1.1.71')

p = Path('readme.md'); s = p.read_text(encoding='utf-8')
s = s.replace('| **当前版本** | `1.1.70` |', '| **当前版本** | `1.1.71` |', 1)
entry = """### 1.1.71 — 2026-10-10

**猫耳娘：全无敌不死 + 弓弩完整蓄力 + 她的界面与玩家背包同布局**

- **全无敌 / 不死**：新开关 `invulnerable`（默认 true）。开启时 `isInvulnerableTo` 恒真、
  `hurt` 直接返回 false（连红屏击退都没有），并且额外兜住两个原版后门 ——
  `kill()`（`/kill` 不看无敌）与虚空伤害（`OUT_OF_WORLD` 绕过无敌判定）：
  `aiStep` 每 tick 把血线补满，掉到世界外就拉回主人身边。关掉开关退回原逻辑
  （只免疫尸潮阵营的伤害）。
- **弓弩完整蓄力**：弓拉满 **20 tick** 才放、箭速 3.0、散布 1.0；弩装填 **25 tick**、箭速 3.15、
  散布 0.6，放完歇 6 tick —— 节奏与玩家拉弓/装弩一致，不是连发。蓄力时站定（停寻路）抬臂。
- **她的界面 = 玩家的布局**：玩家 27 格不再藏到面板外，回到面板内按**原版 9 列 × 18px**
  排（142 / 160 / 178 行），快捷栏在最下一行下留 4px（200 行），面板高度 166 → 226，
  并在她的区块与玩家背包之间加一条分隔线。
- **尾巴摆动**：新增 `tools/cat_girl_tail_sway.py`，把 tail1..tail4 按「逐节相位波」重算 ——
  idle 周期 2s、左右摆 20/13/11/9 度、扭转 4/5/6/7 度，四节相位依次后移 0.12 个周期
  （波从尾根走到尾尖，是猫甩尾而不是整根平移）；walk 周期 1s、摆幅略收、扭转加大。
  可复跑、`--check` 校验、自动留 `.bak.json`。

"""
if '### 1.1.70 — 2026-10-10' in s and '### 1.1.71' not in s:
    s = s.replace('### 1.1.70 — 2026-10-10', entry + '### 1.1.70 — 2026-10-10', 1)
p.write_text(s, encoding='utf-8')
print('(7) readme.md 1.1.71')
