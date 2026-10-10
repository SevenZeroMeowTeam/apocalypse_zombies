# -*- coding: utf-8 -*-
"""1.1.69：工具即指令 —— 斧→伐木 / 镐→挖矿 / 剑·弓→打怪；弓真的会放箭。"""
import re
from pathlib import Path

J = 'src/main/java/com/apocalypse/zombies/'
p = Path(J + 'entity/CatGirlEntity.java')
s = p.read_text(encoding='utf-8')

# ---------- ① 交工具分支：工具决定工种 + 收箭 + 弓的空箭袋提示 ----------
old = """        // 手里拿工具 / 武器：交给她
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
        }"""
new = """        // 箭：她放箭要用，直接进她自己的库存（砍伐/挖矿的产出也存这里）
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
                this.setJob(toolJob);
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
        }"""
assert old in s, '交工具分支没找到'
s = s.replace(old, new, 1)

# ---------- ② jobForTool + countArrows 两个帮手 ----------
anchor = """    /** 工具或武器：原版四大工具 + 剑的标签，外加「带攻击伤害属性」的自定义物品（模组武器）。 */"""
assert anchor in s, 'isToolOrWeapon 注释没找到'
helpers = '''    /**
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

''' + anchor
s = s.replace(anchor, helpers, 1)

# ---------- ③ 注册弓的远程目标：同层但排在近战之前（同优先级先注册的先赢） ----------
old = """        this.goalSelector.addGoal(2, new MeleeAttackGoal(this, 1.2D, true));"""
new = """        // 弓排在近战之前（同优先级先注册者优先）：够远 + 有箭 + 有视线时她放箭，
        // 贴脸（<=3 格）弓的 canUse 不成立，自动轮到下面的近战 —— 不需要另设优先级数字。
        this.goalSelector.addGoal(2, new CatGirlBowGoal(this));
        this.goalSelector.addGoal(2, new MeleeAttackGoal(this, 1.2D, true));"""
assert old in s, '近战目标行没找到'
s = s.replace(old, new, 1)

# import
old = "import net.minecraft.world.entity.ai.goal.FloatGoal;"
assert old in s
s = s.replace(old, "import com.apocalypse.zombies.entity.ai.CatGirlBowGoal;\n" + old, 1)

# Items 若没 import 就补
if 'import net.minecraft.world.item.Items;' not in s:
    s = s.replace("import net.minecraft.world.item.ItemStack;",
                  "import net.minecraft.world.item.ItemStack;\nimport net.minecraft.world.item.Items;", 1)

p.write_text(s, encoding='utf-8')
print('(1) CatGirlEntity：工具→工种 + 收箭 + 弓目标注册')

# ---------- ④ 弓的远程攻击目标 ----------
bow = '''package com.apocalypse.zombies.entity.ai;

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
 * 「给她一张弓，她就远程打怪」。
 *
 * <p>成立条件：工种是打怪、主手拿着弓/弩、目标活着、有视线、距离 &gt; 3 格，
 * 并且**她自己的库存里有箭**（{@code goods} 容器，砍伐/挖矿的产出也进这里；玩家把箭交给她即入袋）。
 * 缺任一条件就轮不到它，贴脸与没箭时自动退回同层的近战目标。
 *
 * <p>箭从她库存里扣，射完为止 —— 想让她持续输出，记得给她补箭。
 */
public class CatGirlBowGoal extends Goal {

    /** 两发之间的冷却：约 1.4 秒，比玩家拉满弓略慢。 */
    private static final int COOLDOWN = 28;

    private final CatGirlEntity cat;
    private int cooldown;

    public CatGirlBowGoal(CatGirlEntity cat) {
        this.cat = cat;
        this.setFlags(EnumSet.of(Goal.Flag.MOVE, Goal.Flag.LOOK));
    }

    private boolean holdingBow() {
        ItemStack held = this.cat.getMainHandItem();
        return held.is(Items.BOW) || held.is(Items.CROSSBOW);
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
        if (this.cat.getJob() != CatGirlEntity.Job.FIGHT || !this.holdingBow()) {
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
        this.cooldown = 10; // 起手稍快，之后按 COOLDOWN 走
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
        if (this.cooldown > 0) {
            this.cooldown--;
            return;
        }
        this.cooldown = COOLDOWN;

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
        // 抬高一点补偿重力，剩下的交给 6.0 的散布
        shot.shoot(dx, dy + flat * 0.12D, dz, 1.6F, 6.0F);
        level.addFreshEntity(shot);

        this.cat.playSound(SoundEvents.SKELETON_SHOOT, 1.0F,
                1.0F / (this.cat.getRandom().nextFloat() * 0.4F + 0.8F));
        this.cat.setAction(CatGirlEntity.ACTION_ATTACK, 9);
    }
}
'''
Path(J + 'entity/ai/CatGirlBowGoal.java').write_text(bow, encoding='utf-8')
print('(2) entity/ai/CatGirlBowGoal.java 新建')

# ---------- ⑤ lang ----------
lang = {
    'en_us.json': [
        ("cat_girl.job.from_tool", "%s took the %s - switching to %s"),
        ("cat_girl.gave_arrows", "She stowed %s x%d in her quiver."),
        ("cat_girl.arrows", "arrows"),
        ("cat_girl.bow.need_arrows", "She has the bow but her quiver is empty - hand her some arrows."),
    ],
    'zh_cn.json': [
        ("cat_girl.job.from_tool", "%s 收下了%s，开始%s"),
        ("cat_girl.gave_arrows", "她把%d 支%s收进了自己的箭袋"),
        ("cat_girl.arrows", "箭"),
        ("cat_girl.bow.need_arrows", "她收下了弓，但箭袋是空的——把箭交给她（右键）她才能放箭"),
    ],
}
for f, kv in lang.items():
    q = Path('src/main/resources/assets/apocalypse_zombies/lang/' + f)
    t = q.read_text(encoding='utf-8')
    anchor = '  "cat_girl.trade.title"'
    assert anchor in t, f
    t = t.replace(anchor, ''.join('  "%s": "%s",\n' % (k, v) for k, v in kv) + anchor, 1)
    q.write_text(t, encoding='utf-8')
    print('(3) lang %s +%d 键' % (f, len(kv)))

# ---------- ⑥ 版本 ----------
g = Path('gradle.properties'); t = g.read_text(encoding='utf-8')
assert 'mod_version=1.1.68' in t
g.write_text(t.replace('mod_version=1.1.68', 'mod_version=1.1.69'), encoding='utf-8')
print('(4) mod_version=1.1.69')

# ---------- ⑦ 出货脚本 169 ----------
src = Path('tools/_deploy_168.py').read_text(encoding='utf-8')
src = src.replace('1.1.68', '1.1.69').replace('1.1.67', '1.1.68')
src = src.replace('"""1.1.69 出货：猫耳娘交互修复（蹲下优先开界面 + 界面只显示她的部分）',
                  '"""1.1.69 出货：猫耳娘「工具即指令」（斧→伐木 / 镐→挖矿 / 剑·弓→打怪 + 弓会放箭）')
anchor = "print('=== 3/5 不回归：柯尔特 1878（1.1.68 内容不许被冲掉） ===')"
assert anchor in src, '锚点不对（要用替换后的 1.1.68 文案）'
new_block = r'''# ---- 工具即指令：映射函数 / 弓目标 / 外显提示键都在 ----
cgsrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/CatGirlEntity.java',
             encoding='utf-8').read()
check('public static Job jobForTool(' in cgsrc, '工具→工种 映射函数在')
check('CatGirlBowGoal' in cgsrc, '弓的远程目标已注册')
check('countArrows' in cgsrc, '箭袋计数在（供「她没箭了」提示）')
check(pathlib.Path('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/ai/CatGirlBowGoal.java').exists(),
      'CatGirlBowGoal.java 在')
for lf in ('en_us.json', 'zh_cn.json'):
    ls = open('F:/mcmod/src/main/resources/assets/apocalypse_zombies/lang/' + lf, encoding='utf-8').read()
    check('"cat_girl.job.from_tool"' in ls and '"cat_girl.bow.need_arrows"' in ls,
          'lang %s 有工具→工种 / 箭袋提示键' % lf)

'''
src = src.replace(anchor, new_block + anchor, 1)
Path('tools/_deploy_169.py').write_text(src, encoding='utf-8')
import py_compile
py_compile.compile('tools/_deploy_169.py', doraise=True)
print('(5) tools/_deploy_169.py OK')
